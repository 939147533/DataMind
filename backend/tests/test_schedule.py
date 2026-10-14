"""定时导出测试。"""
from sqlalchemy import select


async def test_schedule_crud_and_run(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/schedule",
        json={
            "name": "每日订单导出",
            "datasource_id": demo_ds_id,
            "sql_text": "SELECT id, status FROM orders LIMIT 5",
            "format": "csv",
            "interval_minutes": 60,
            "enabled": True,
        },
    )
    assert resp.status_code == 200
    sid = resp.json()["data"]["id"]

    lst = await auth_client.get("/api/schedule")
    assert any(s["id"] == sid for s in lst.json()["data"])

    run = await auth_client.post(f"/api/schedule/{sid}/run")
    assert run.status_code == 200
    assert run.json()["data"]["file"]

    dl = await auth_client.get(f"/api/schedule/{sid}/file")
    assert dl.status_code == 200
    assert b"id" in dl.content and b"status" in dl.content

    upd = await auth_client.put(f"/api/schedule/{sid}", json={"enabled": False})
    assert upd.json()["data"]["enabled"] is False

    dele = await auth_client.delete(f"/api/schedule/{sid}")
    assert dele.status_code == 200


async def test_concurrent_replicas_claim_task_only_once(demo_ds_id):
    """多副本同时读到同一批到期任务时，条件 UPDATE 保证只有一个进程执行。"""
    from datetime import datetime, timedelta

    from app.database import SessionLocal
    from app.models import ScheduledExport
    from app.services.schedule_service import claim_schedule

    async with SessionLocal() as db:
        task = ScheduledExport(
            name="抢占验证",
            datasource_id=demo_ds_id,
            sql_text="SELECT 1",
            format="csv",
            interval_minutes=60,
            enabled=True,
            next_run_at=datetime.now() - timedelta(minutes=1),
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = task.id

    now = datetime.now()
    async with SessionLocal() as replica_a, SessionLocal() as replica_b:
        assert await claim_schedule(replica_a, task_id, now) is True
        assert await claim_schedule(replica_b, task_id, now) is False, "同一到期任务不应被第二个副本重复认领"

    async with SessionLocal() as db:
        refreshed = (
            await db.execute(select(ScheduledExport).where(ScheduledExport.id == task_id))
        ).scalar_one()
        assert refreshed.next_run_at > now, "认领后应顺延到下一个周期"
