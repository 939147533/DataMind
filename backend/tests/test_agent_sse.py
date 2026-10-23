"""SSE 包装：响应头设置与「停止生成」的取消传播。

`/api/agent/chat` 的流式响应在客户端 abort 后必须真正停下来，
否则模型会继续生成、继续消耗 token，而用户界面上已经点了「停止」。
"""
import asyncio

import pytest


def test_sse_sets_no_buffering_headers():
    """必须显式关闭缓冲，否则代理会把断开的连接缓冲住，服务端察觉不到。"""
    from app.routers.agent import sse

    async def gen():
        yield {"type": "done"}

    resp = sse(gen())
    assert resp.media_type == "text/event-stream"
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"


async def test_sse_cancel_stops_generator():
    """取消（客户端断开）后生成器不得继续产出后续事件。"""
    from app.routers.agent import sse

    reached_after_cancel = False

    async def gen():
        nonlocal reached_after_cancel
        yield {"type": "thought", "content": "思考中"}
        await asyncio.sleep(30)  # 模拟在途的 LLM 调用
        reached_after_cancel = True
        yield {"type": "text", "content": "不该出现"}

    resp = sse(gen())
    chunks: list[str] = []

    async def consume():
        async for chunk in resp.body_iterator:
            chunks.append(chunk)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert chunks and chunks[0].startswith("data: ")
    assert '"type": "thought"' in chunks[0]
    assert reached_after_cancel is False
