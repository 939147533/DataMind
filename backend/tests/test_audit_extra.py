"""审计导出与保留策略测试。"""
from datetime import datetime, timedelta

from sqlalchemy import select


async def test_audit_export_csv(auth_client):
    resp = await auth_client.get("/api/audit/export?format=csv")
    assert resp.status_code == 200
    assert b"action_type" in resp.content


async def test_audit_export_excel(auth_client):
    resp = await auth_client.get("/api/audit/export?format=xlsx")
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"


async def test_audit_retention_cleanup(auth_client):
    from app.database import SessionLocal
    from app.models import AuditLog
    from app.services.audit_service import cleanup_old_logs

    async with SessionLocal() as db:
        db.add(AuditLog(user_id=None, action_type="test_old", status="success", created_at=datetime.now() - timedelta(days=999)))
        await db.commit()
    async with SessionLocal() as db:
        removed = await cleanup_old_logs(db, 180)
    assert removed >= 1
    async with SessionLocal() as db:
        rows = (await db.execute(select(AuditLog).where(AuditLog.action_type == "test_old"))).scalars().all()
        assert not rows
