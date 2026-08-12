"""系统管理路由：AI 配置、JDBC 驱动、系统设置。"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import DRIVERS_DIR
from ..database import get_db
from ..deps import get_current_user
from ..models import AIConfig, JdbcDriver, Setting, User
from ..response import ok
from ..schemas import AIConfigCreate, AIConfigUpdate, SettingsUpdate
from ..security import decrypt_text, encrypt_text

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
@router.get("/ai")
async def list_ai_configs(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(select(AIConfig).order_by(AIConfig.id.desc()))).scalars().all()
    return ok([_ai_out(c) for c in rows])


@router.post("/ai")
async def create_ai_config(data: AIConfigCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
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
async def update_ai_config(config_id: int, data: AIConfigUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
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
async def delete_ai_config(config_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    config = (await db.execute(select(AIConfig).where(AIConfig.id == config_id))).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    await db.delete(config)
    await db.commit()
    return ok(message="删除成功")


@router.put("/ai/{config_id}/default")
async def set_default_ai(config_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    config = (await db.execute(select(AIConfig).where(AIConfig.id == config_id))).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    await db.execute(update(AIConfig).values(is_default=False))
    config.is_default = True
    await db.commit()
    return ok(message="已设为默认模型")


# ---------- JDBC 驱动 ----------
@router.get("/drivers")
async def list_drivers(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
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
    user: User = Depends(get_current_user),
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
async def delete_driver(driver_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
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
async def get_settings(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(select(Setting))).scalars().all()
    values = {r.key: r.value for r in rows}
    merged = {**DEFAULT_SETTINGS, **values}
    return ok({"values": merged})


@router.put("/settings")
async def update_settings(data: SettingsUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    for key, value in data.values.items():
        setting = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        if setting is None:
            db.add(Setting(key=key, value=str(value)))
        else:
            setting.value = str(value)
    await db.commit()
    return ok(message="设置已保存")
