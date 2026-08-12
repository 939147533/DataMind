"""系统管理路由：AI 配置、JDBC 驱动、系统设置。"""
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import DRIVERS_DIR
from ..database import get_db
from ..models import AIConfig, JdbcDriver, Setting, User
from ..permissions import require_permission
from ..response import ok
from ..schemas import AIConfigCreate, AIConfigTestRequest, AIConfigUpdate, SettingsUpdate
from ..security import decrypt_text, encrypt_text
from ..services.llm_providers import LLMError, get_llm_provider

router = APIRouter(prefix="/api/config", tags=["系统管理"])


def _ai_out(c: AIConfig) -> dict:
    return {
        "id": c.id,
        "provider": c.provider,
        "has_key": bool(c.api_key),
        "api_base": c.api_base,
        "model_name": c.model_name,
        "max_tokens": c.max_tokens,
        "temperature": c.temperature,
        "is_active": c.is_active,
        "is_default": c.is_default,
    }


# ---------- AI 配置 ----------
@router.post("/ai/test")
async def test_ai_connectivity(data: AIConfigTestRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    """模型连通性测试：已保存配置（config_id）或表单临时参数，均不落库。"""
    stored = None
    if data.config_id:
        stored = (await db.execute(select(AIConfig).where(AIConfig.id == data.config_id))).scalar_one_or_none()
        if stored is None:
            raise HTTPException(status_code=404, detail="AI 配置不存在")

    def _field(name, fallback):
        value = getattr(data, name, None)
        if value is None:
            return getattr(stored, name) if stored else fallback
        return value

    api_key_plain = ""
    if data.api_key:
        api_key_plain = data.api_key
    elif stored:
        api_key_plain = decrypt_text(stored.api_key)
    test_cfg = AIConfig(
        provider=_field("provider", "openai") or "openai",
        api_key=encrypt_text(api_key_plain),
        api_base=_field("api_base", "") or "",
        model_name=_field("model_name", "") or "",
        max_tokens=_field("max_tokens", 4096) or 4096,
        temperature=_field("temperature", 0.7),
        is_active=True,
    )
    if not test_cfg.model_name:
        raise HTTPException(status_code=400, detail="缺少模型名称")

    provider = get_llm_provider(test_cfg)
    validate = getattr(provider, "validate", None)
    if validate is not None:
        try:
            validate()
        except LLMError as exc:
            return ok({"success": False, "message": str(exc), "latency_ms": 0}, message="测试失败")
    start = time.perf_counter()
    try:
        result = await provider.ping()
        latency_ms = int((time.perf_counter() - start) * 1000)
        model = result.get("model") or test_cfg.model_name
        return ok(
            {"success": True, "message": f"连接成功，模型 {model} 响应正常", "latency_ms": latency_ms, "model": model},
            message="测试成功",
        )
    except LLMError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ok({"success": False, "message": str(exc), "latency_ms": latency_ms}, message="测试失败")


@router.get("/ai")
async def list_ai_configs(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    rows = (await db.execute(select(AIConfig).order_by(AIConfig.id.desc()))).scalars().all()
    return ok([_ai_out(c) for c in rows])


@router.post("/ai")
async def create_ai_config(data: AIConfigCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    if data.is_default:
        await db.execute(update(AIConfig).values(is_default=False))
    config = AIConfig(
        provider=data.provider,
        api_key=encrypt_text(data.api_key),
        api_base=data.api_base,
        model_name=data.model_name,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
        is_active=data.is_active,
        is_default=data.is_default,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return ok(_ai_out(config), "创建成功")


@router.put("/ai/{config_id}")
async def update_ai_config(config_id: int, data: AIConfigUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    config = (await db.execute(select(AIConfig).where(AIConfig.id == config_id))).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    payload = data.model_dump(exclude_unset=True)
    if "api_key" in payload:
        if payload["api_key"]:
            config.api_key = encrypt_text(payload["api_key"])
        payload.pop("api_key")
    for field, value in payload.items():
        setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return ok(_ai_out(config), "更新成功")


@router.delete("/ai/{config_id}")
async def delete_ai_config(config_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    config = (await db.execute(select(AIConfig).where(AIConfig.id == config_id))).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    await db.delete(config)
    await db.commit()
    return ok(message="删除成功")


@router.put("/ai/{config_id}/default")
async def set_default_ai(config_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    config = (await db.execute(select(AIConfig).where(AIConfig.id == config_id))).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    await db.execute(update(AIConfig).values(is_default=False))
    config.is_default = True
    await db.commit()
    return ok(message="已设为默认模型")


# ---------- JDBC 驱动 ----------
@router.get("/drivers")
async def list_drivers(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    rows = (await db.execute(select(JdbcDriver).order_by(JdbcDriver.id.desc()))).scalars().all()
    return ok(
        [
            {
                "id": d.id,
                "db_type": d.db_type,
                "driver_class": d.driver_class,
                "version": d.version,
                "file_name": d.file_name,
                "file_size": d.file_size,
                "upload_time": d.upload_time.isoformat() if d.upload_time else None,
            }
            for d in rows
        ]
    )


@router.post("/drivers")
async def upload_driver(
    file: UploadFile,
    db_type: str = "",
    driver_class: str = "",
    version: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("settings")),
):
    DRIVERS_DIR.mkdir(parents=True, exist_ok=True)
    if not (file.filename or "").lower().endswith(".jar"):
        raise HTTPException(status_code=400, detail="仅支持 JAR 文件")
    safe_name = Path(file.filename).name
    target = DRIVERS_DIR / safe_name
    content = await file.read()
    target.write_bytes(content)
    driver = JdbcDriver(
        db_type=db_type,
        driver_class=driver_class,
        version=version,
        file_path=str(Path("drivers") / safe_name),
        file_name=safe_name,
        file_size=len(content),
    )
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return ok({"id": driver.id, "file_name": safe_name, "file_size": len(content)}, "上传成功")


@router.delete("/drivers/{driver_id}")
async def delete_driver(driver_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    driver = (await db.execute(select(JdbcDriver).where(JdbcDriver.id == driver_id))).scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=404, detail="驱动不存在")
    await db.delete(driver)
    await db.commit()
    return ok(message="删除成功")


# ---------- 系统设置 ----------
DEFAULT_SETTINGS = {
    "language": "zh",
    "theme": "light",
    "editor_font_size": "14",
    "editor_tab_size": "4",
    "autocomplete": "true",
}


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    rows = (await db.execute(select(Setting))).scalars().all()
    values = {r.key: r.value for r in rows}
    merged = {**DEFAULT_SETTINGS, **values}
    return ok({"values": merged})


@router.put("/settings")
async def update_settings(data: SettingsUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("settings"))):
    for key, value in data.values.items():
        setting = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        if setting is None:
            db.add(Setting(key=key, value=str(value)))
        else:
            setting.value = str(value)
    await db.commit()
    return ok(message="设置已保存")
