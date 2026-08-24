"""
tests/test_storage_and_gemini.py — Storage guardian + Gemini toggle endpoints.

Same offline pattern as test_company_artifact_link: real local MongoDB,
throwaway database, external world silenced.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MONGO_URI = "mongodb://localhost:27017"
TEST_DB = "placement_monitor_test"


async def _mongo_up() -> bool:
    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=800)
        await client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def sandbox(monkeypatch):
    from motor.motor_asyncio import AsyncIOMotorClient
    import database
    import config

    if not await _mongo_up():
        pytest.skip("MongoDB not running on localhost - skipping e2e test")

    client = AsyncIOMotorClient(MONGO_URI)
    db = client[TEST_DB]
    for name in ("opportunities", "messages", "opportunity_events",
                 "reminders", "app_settings"):
        await db[name].delete_many({})

    monkeypatch.setattr(database, "_client", client)
    monkeypatch.setattr(config.settings, "mongodb_db", TEST_DB)
    monkeypatch.setattr(config.settings, "telegram_bot_token", "")
    monkeypatch.setattr(config.settings, "telegram_chat_id", "")

    yield db
    client.close()


@pytest_asyncio.fixture
async def http_app(sandbox):
    import main as app_module

    async with httpx_client(app_module.app) as c:
        yield c


from contextlib import asynccontextmanager
import httpx


@asynccontextmanager
async def httpx_client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
            transport=transport, base_url="http://test") as c:
        yield c


async def _login(client) -> dict:
    from config import settings as s

    r = await client.post("/api/auth/login", json={
        "username": s.admin_username,
        "password": s.admin_password,
        "security_code": s.admin_security_code,
    })
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_storage_stats_requires_auth(http_app):
    r = await http_app.get("/api/storage")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_storage_stats_shape(http_app):
    headers = await _login(http_app)
    r = await http_app.get("/api/storage", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("used_mb", "limit_mb", "percent", "should_warn", "collections"):
        assert key in body
    assert body["limit_mb"] == 512
    assert "opportunities" in body["collections"]


@pytest.mark.asyncio
async def test_bulk_delete_cascades(sandbox, http_app):
    headers = await _login(http_app)
    now = datetime.utcnow()
    opp_id = (await sandbox["opportunities"].insert_one({
        "company": "Bulk Corp", "role": "SDE", "status": "NEW",
        "deadline": now + timedelta(days=3), "updated_at": now,
        "source_message_ids": ["m1"],
    })).inserted_id
    await sandbox["opportunity_events"].insert_one({
        "opportunity_id": str(opp_id), "event_type": "CREATED",
        "created_at": now,
    })
    msg_id = (await sandbox["messages"].insert_one({
        "message_text": "hi", "message_date": now,
        "opportunity_id": str(opp_id),
    })).inserted_id

    r = await http_app.post(
        "/api/storage/opportunities/delete-bulk",
        headers=headers, json={"ids": [str(opp_id)]})
    assert r.status_code == 200 and r.json()["deleted"] == 1
    assert await sandbox["opportunities"].count_documents({}) == 0
    assert await sandbox["opportunity_events"].count_documents({}) == 0
    survivor = await sandbox["messages"].find_one({"_id": msg_id})
    assert survivor["opportunity_id"] is None


@pytest.mark.asyncio
async def test_purge_endpoint_validates_days(http_app):
    headers = await _login(http_app)
    r = await http_app.post("/api/storage/purge",
                            headers=headers, json={"days": 0})
    assert r.status_code == 400
    r = await http_app.post("/api/storage/purge",
                            headers=headers, json={"days": 25})
    assert r.status_code == 200 and r.json()["ok"] is True


@pytest.mark.asyncio
async def test_gemini_disabled_rejects_chat(sandbox, http_app, monkeypatch):
    from config import settings as s

    monkeypatch.setattr(s, "gemini_api_key", "fake-key")
    headers = await _login(http_app)

    r = await http_app.post("/api/gemini/chat",
                            headers=headers, json={"question": "deadlines?"})
    assert r.status_code == 400
    assert "disabled" in r.json()["detail"].lower()

    t = await http_app.post("/api/gemini/toggle",
                            headers=headers, json={"enabled": True})
    assert t.status_code == 200 and t.json()["enabled"] is True

    st = await http_app.get("/api/gemini/status", headers=headers)
    assert st.status_code == 200
    body = st.json()
    assert body["enabled"] is True and body["configured"] is True


@pytest.mark.asyncio
async def test_gemini_toggle_needs_key(sandbox, http_app, monkeypatch):
    from config import settings as s

    monkeypatch.setattr(s, "gemini_api_key", "")
    headers = await _login(http_app)

    r = await http_app.post("/api/gemini/toggle",
                            headers=headers, json={"enabled": True})
    assert r.status_code == 400
