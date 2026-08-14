"""统一 LLMProvider 抽象：OpenAI 兼容 / Anthropic / Ollama。"""
from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..models import AIConfig
from ..security import decrypt_text


class LLMError(Exception):
    pass


class BaseLLMProvider(ABC):
    def __init__(self, config: AIConfig):
        self.config = config

    @property
    def model_name(self) -> str:
        return self.config.model_name or "gpt-4o-mini"

    def _api_key(self) -> str:
        return decrypt_text(self.config.api_key)

    def validate(self) -> None:
        """校验配置是否满足调用前提，缺失时快速失败而非等待 SDK 超时。"""
        if self.config.provider in ("openai", "claude") and not self._api_key():
            raise LLMError("未配置 API Key，请到 系统设置 → 大模型连接配置 中填写")
        if self.config.provider == "ollama" and not self.config.api_base:
            raise LLMError("未配置 Ollama 服务地址（api_base）")

    @abstractmethod
    async def chat(self, messages: list[dict], json_mode: bool = False) -> str: ...

    @abstractmethod
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]: ...

    @abstractmethod
    async def ping(self) -> dict:
        """最小请求验证模型连通性，返回 {"model": ...}，失败抛 LLMError。"""


class OpenAICompatProvider(BaseLLMProvider):
    """OpenAI 官方 API 与 OpenAI 兼容网关（含 Ollama /v1）。"""

    async def _client(self, timeout: float | None = None):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self._api_key() or "sk-no-key", base_url=self.config.api_base or None, timeout=timeout)

    async def chat(self, messages: list[dict], json_mode: bool = False) -> str:
        client = await self._client()
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = await client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"模型调用失败: {exc}") from exc

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        client = await self._client()
        try:
            stream = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"模型流式调用失败: {exc}") from exc

    async def ping(self) -> dict:
        client = await self._client(timeout=20)
        try:
            resp = await client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
            return {"model": getattr(resp, "model", None) or self.model_name}
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"模型连通性测试失败: {exc}") from exc


class ClaudeProvider(BaseLLMProvider):
    async def _client(self, timeout: float | None = None):
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=self._api_key(), timeout=timeout)

    def _split(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
        return system, rest

    async def chat(self, messages: list[dict], json_mode: bool = False) -> str:
        client = await self._client()
        system, rest = self._split(messages)
        try:
            resp = await client.messages.create(
                model=self.model_name,
                system=system or None,
                messages=rest,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            return "".join(b.text for b in resp.content if b.type == "text")
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"模型调用失败: {exc}") from exc

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        client = await self._client()
        system, rest = self._split(messages)
        try:
            async with client.messages.stream(
                model=self.model_name,
                system=system or None,
                messages=rest,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"模型流式调用失败: {exc}") from exc

    async def ping(self) -> dict:
        client = await self._client(timeout=20)
        try:
            await client.messages.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
            return {"model": self.model_name}
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"模型连通性测试失败: {exc}") from exc


def get_llm_provider(config: AIConfig) -> BaseLLMProvider:
    if config.provider == "claude":
        return ClaudeProvider(config)
    if config.provider == "ollama":
        if not config.api_base:
            config.api_base = "http://localhost:11434/v1"
        return OpenAICompatProvider(config)
    return OpenAICompatProvider(config)


def build_messages(system: str, history: list[dict], user_msg: str) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_msg})
    return messages
