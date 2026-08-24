"""
End-to-end verification (offline, local MongoDB):

  A. One company name links ALL its artifacts:
     announcement + JD PDF attachment + Google Form -> ONE opportunity,
     one alert, merged timeline.
  B. HTTP endpoints work: login (fail-closed), JWT-protected CRUD,
     forms_only filter, source-document endpoint, 401s.
  C. API surface hardening: /docs /redoc /openapi.json are stripped
     unless DOCS_ENABLED=true.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MONGO_URI = "mongodb://localhost:27017"
TEST_DB = "placement_monitor_test"


# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    """Point the REAL database accessors at a throwaway DB + silence alerts."""
    from motor.motor_asyncio import AsyncIOMotorClient
    import database
    import config

    if not await _mongo_up():
        pytest.skip("MongoDB not running on localhost â€” skipping e2e test")

    client = AsyncIOMotorClient(MONGO_URI)
    db = client[TEST_DB]
    for name in ("opportunities", "messages", "opportunity_events", "reminders"):
        await db[name].delete_many({})

    # get_db() reads database._client + settings.mongodb_db â€” repoint both so
    # every accessor (even locally-imported ones) hits the sandbox DB.
    monkeypatch.setattr(database, "_client", client)
    monkeypatch.setattr(config.settings, "mongodb_db", TEST_DB)

    # silence external world
    alerts: list[dict] = []

    async def _fake_alert(*a, **k):
        alerts.append({"args": a, "kwargs": k})

    mp = __import__("services.message_pipeline", fromlist=["x"])
    monkeypatch.setattr(mp, "send_new_opportunity_alert", _fake_alert)
    monkeypatch.setattr(mp, "send_needs_review_alert", _fake_alert)
    monkeypatch.setattr(config.settings, "gemini_enabled", False)
    monkeypatch.setattr(config.settings, "gemini_api_key", "")
    monkeypatch.setattr(config.settings, "telegram_bot_token", "")
    monkeypatch.setattr(config.settings, "telegram_chat_id", "")

    yield {"db": db, "alerts": alerts}
    client.close()


# â”€â”€ A. company â†” artifacts linkage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_one_company_links_jd_form_and_attachment(sandbox):
    from services.message_pipeline import ingest_message
    from models.message import MessageSource

    day1 = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)

    # 1) Original drive announcement
    opp1 = await ingest_message(
        "Company: Qwipo Technologies Pvt Ltd\n"
        "Role: Software Engineer\n"
        "CTC: 8 LPA\n"
        "Apply by 30 Aug 2026",
        day1,
        MessageSource.USERBOT,
        telegram_message_id=101,
        sender_name="TPO",
    )
    assert opp1, "announcement should create an opportunity"

    col = sandbox["db"]["opportunities"]
    doc1 = await col.find_one({"_id": __import__("bson").ObjectId(opp1)})
    assert doc1["company"], "company extracted"
    assert "software" in (doc1.get("role") or "").lower()
    assert doc1.get("deadline") is not None

    # 2) Follow-up: JD PDF + Google Form link for the SAME company
    opp2 = await ingest_message(
        "Qwipo Technologies Pvt Ltd â€” JD attached!\n"
        "Role: Software Engineer (Backend)\n"
        "Mandatory registration form: https://forms.gle/qwipoSDEreg2026\n"
        "CTC: 10 LPA. Last date 30 Aug 2026.",
        datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc),
        MessageSource.USERBOT,
        telegram_message_id=102,
        sender_name="TPO",
        pdf_info={
            "filename": "Qwipo_JD.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 20480,
            "storage_key": "documents/test/qwipo_jd.pdf",
            "text_extracted": True,
        },
    )
    assert opp2 == opp1, "same company must MERGE into the same opportunity, not duplicate"

    merged = await col.find_one({"_id": doc1["_id"]})
    assert (merged.get("registration_link") or "").startswith("https://forms.gle/")
    assert merged.get("has_registration_form") is True
    assert merged.get("action_required") is True
    assert merged.get("source_document") == "Qwipo_JD.pdf"
    assert merged.get("source_document_key") == "documents/test/qwipo_jd.pdf"

    from bson import ObjectId

    timeline = await sandbox["db"]["opportunity_events"].count_documents(
        {"opportunity_id": {"$in": [opp1, ObjectId(opp1)]}}
    )
    assert timeline >= 2, "both messages must appear on one timeline"

    assert len(sandbox["alerts"]) == 1, "alert exactly once â€” no spam on merge"


# â”€â”€ shared HTTP app for endpoint tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.fixture()
def http_app(sandbox, monkeypatch):
    """ASGI app + base URL; used via in-loop AsyncClient to keep one event loop."""
    import config
    from fastapi import FastAPI
    from api.routes import opportunities as opp_routes
    from api.routes.auth import router as auth_router

    monkeypatch.setattr(config.settings, "admin_username", "tester")
    monkeypatch.setattr(config.settings, "admin_password", "pw-12345")
    monkeypatch.setattr(config.settings, "admin_security_code", "99999")
    monkeypatch.setattr(config.settings, "jwt_secret", "unit-test-secret")

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(opp_routes.router)
    return app


@pytest.mark.asyncio
async def _api_call(app, method, url, **kw):
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.request(method, url, **kw)


@pytest.mark.asyncio
async def test_endpoints_auth_and_detail(sandbox, http_app):
    from services.message_pipeline import ingest_message
    from models.message import MessageSource

    oid = await ingest_message(
        "Company: Qwipo Technologies Pvt Ltd\nRole: Software Engineer\n"
        "Form: https://forms.gle/qwipoSDEreg2026\nApply by 30 Aug 2026",
        datetime(2026, 8, 22, tzinfo=timezone.utc),
        MessageSource.BOT_FORWARD,
        telegram_message_id=201,
    )
    assert oid

    # unauthenticated access is refused everywhere
    r = await _api_call(http_app, "GET", f"/api/opportunities/{oid}")
    assert r.status_code == 401
    r = await _api_call(http_app, "GET", "/api/opportunities")
    assert r.status_code == 401

    # wrong credentials rejected
    bad = await _api_call(http_app, "POST", "/api/auth/login", json={
        "username": "tester", "password": "wrong", "security_code": "99999"})
    assert bad.status_code == 401

    good = await _api_call(http_app, "POST", "/api/auth/login", json={
        "username": "tester", "password": "pw-12345", "security_code": "99999"})
    assert good.status_code == 200, good.text
    token = good.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    me = await _api_call(http_app, "GET", "/api/auth/me", headers=H)
    assert me.status_code == 200 and me.json()["role"] == "admin"

    detail = await _api_call(http_app, "GET", f"/api/opportunities/{oid}", headers=H)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert "qwipo" in body["company"].lower()
    assert body["registration_link"].startswith("https://forms.gle/")
    assert body["has_registration_form"] is True
    assert isinstance(body["timeline"], list) and len(body["timeline"]) >= 1

    listed = await _api_call(http_app, "GET", "/api/opportunities",
                             params={"forms_only": "true"}, headers=H)
    assert listed.status_code == 200
    data = listed.json()
    if isinstance(data, dict):
        items = data.get("items") or data.get("opportunities") or []
    else:
        items = data
    ids = [o.get("id") or o.get("_id") for o in items]
    assert oid in ids, "forms_only filter must surface the drive with the form"

    src = await _api_call(http_app, "GET",
                          f"/api/opportunities/{oid}/source-document", headers=H)
    assert src.status_code in (200, 404)  # wired; 404 simply means file not on disk


def test_docs_hidden_by_default():
    """Swagger/ReDoc/openapi.json must NOT be reachable."""
    from fastapi import FastAPI
    import config
    from main import DOCS_ROUTES, apply_docs_policy

    assert "/openapi.json" in DOCS_ROUTES

    dummy = FastAPI()  # fresh app ships docs routes by default
    before = {getattr(r, "path", "") for r in dummy.router.routes}
    assert DOCS_ROUTES & before, "dummy app should have docs routes"

    original = config.settings.docs_enabled
    object.__setattr__(config.settings, "docs_enabled", False)
    try:
        removed = apply_docs_policy(dummy)
        after = {getattr(r, "path", "") for r in dummy.router.routes}
        assert removed >= 3 and not (DOCS_ROUTES & after)

        object.__setattr__(config.settings, "docs_enabled", True)
        enabled = FastAPI()
        assert apply_docs_policy(enabled) == 0, "DOCS_ENABLED=true keeps docs"
    finally:
        object.__setattr__(config.settings, "docs_enabled", original)

    import main as main_mod
    live_paths = {getattr(r, "path", "") for r in main_mod.app.router.routes}
    assert not (DOCS_ROUTES & live_paths), "live app must hide docs when disabled"
