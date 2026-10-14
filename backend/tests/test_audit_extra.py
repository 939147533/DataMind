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


async def test_denied_sql_execution_is_audited(auth_client, demo_ds_id):
    """被拒绝的 SQL 执行也要留审计（此前只有写操作确认流程记录 denied）。"""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    resp = await auth_client.post(
        "/api/roles",
        json={"code": "audit_probe", "name": "audit_probe", "description": "test", "permissions": ["agent"]},
    )
    assert resp.status_code == 200, resp.text
    resp = await auth_client.post(
        "/api/users",
        json={
            "username": "audit_probe_user",
            "password": "test1234",
            "display_name": "probe",
            "role": "audit_probe",
            "is_active": True,
        },
    )
    assert resp.status_code == 200, resp.text

    sql = "SELECT COUNT(*) AS c FROM users"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/auth/login", json={"username": "audit_probe_user", "password": "test1234"})
        denied = await client.post("/api/sql/execute", json={"datasource_id": demo_ds_id, "sql": sql})
        assert denied.status_code == 403, denied.text

    logs = await auth_client.get("/api/audit/logs?action_type=execute_sql&status=denied&page_size=100")
    assert logs.status_code == 200, logs.text
    rows = logs.json()["data"]["list"]
    assert any(r["sql_text"] == sql and r["operation_type"] == "READ" for r in rows), rows
