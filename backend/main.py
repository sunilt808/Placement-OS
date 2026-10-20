"""
main.py — PlacementOS FastAPI application entry point.

Free-tier hardening (Render):
  * `/api/health` is intentionally lightweight and NEVER touches the DB, so it
    answers instantly and the platform health check passes during cold start.
  * Heavy init (DB, scheduler, Telegram) runs in a background task so the app
    starts responding immediately instead of blocking on external services.
  * A self-ping keep-alive job keeps the service warm while it is awake.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import connect_db, close_db, ensure_indexes
from scheduler import start_scheduler, stop_scheduler
from api.routes import opportunities, import_, reminders, settings as settings_router
from api.routes import storage as storage_router, gemini as gemini_router
from api.routes.auth import router as auth_router

# Tracks how far background initialization has progressed (for /api/health).
_boot_state = {"db": False, "userbot": False, "bot": False, "started_at": None}


async def _background_init(userbot_container: dict, bot_container: dict):
    """Run all slow startup work off the request path."""
    import datetime as _dt
    _boot_state["started_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()

    # 1. Database — retry loop already handles Atlas cold starts.
    connected = await connect_db()
    _boot_state["db"] = connected
    if connected:
        await ensure_indexes()
        # Start the background reconnect watchdog once we have a client.
        from database import start_db_watchdog
        start_db_watchdog()

    # 2. Scheduler (in-process timer jobs)
    try:
        start_scheduler()
    except Exception as e:
        print(f"[Main] Scheduler start error: {e}")

    # 3. Telegram userbot supervisor
    try:
        from userbot import run_userbot_forever
        userbot_container["task"] = asyncio.create_task(run_userbot_forever())
        _boot_state["userbot"] = True
        print("[Main] Telegram userbot supervisor started")
    except Exception as e:
        print(f"[Main] Userbot error: {e}")

    # 4. Optional startup self-test ping
    if settings.startup_ping and settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            from services.notification_service import _send_message
            await _send_message(
                "🟢 <b>PlacementOS is online</b> — auto-notifications are active. "
                "You'll be alerted here the moment a new drive drops."
            )
            print("[Main] Startup ping delivered — notification channel OK")
        except Exception as e:
            print(f"[Main] STARTUP PING FAILED: {e}\n"
                  f"       → Auto-notifications will NOT arrive until this is fixed.\n"
                  f"       → Open the bot in Telegram, press START, then verify "
                  f"TELEGRAM_CHAT_ID in .env matches your numeric user id.")

    # 5. Telegram bot polling
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            from telegram_bot import build_bot_app
            bot_app = build_bot_app()
            await bot_app.initialize()
            await bot_app.start()
            await bot_app.updater.start_polling(drop_pending_updates=True)
            bot_container["app"] = bot_app
            _boot_state["bot"] = True
        except Exception as e:
            print(f"[Main] Telegram bot error: {e}")
    else:
        print("[Main] Telegram bot not configured — continuing without notifications.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Main] Starting PlacementOS AI Monitor...")
    userbot_container: dict = {}
    bot_container: dict = {}
    init_task = asyncio.create_task(_background_init(userbot_container, bot_container))

    yield

    print("[Main] Shutting down...")
    init_task.cancel()
    try:
        stop_scheduler()
    except Exception:
        pass
    task = userbot_container.get("task")
    if task:
        task.cancel()
    bot_app = bot_container.get("app")
    if bot_app:
        try:
            await asyncio.wait_for(bot_app.updater.stop(), timeout=10)
            await asyncio.wait_for(bot_app.stop(), timeout=10)
            await asyncio.wait_for(bot_app.shutdown(), timeout=10)
        except Exception as e:
            print(f"[Main] Bot shutdown note: {e}")
    await close_db()

app = FastAPI(
    title="PlacementOS API",
    version="2.0.0",
    lifespan=lifespan,
)

# ── API surface hardening ─────────────────────────────────────────────────
# Swagger/ReDoc/openapi.json are stripped unless settings.docs_enabled=True.
DOCS_ROUTES = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}

def apply_docs_policy(application: FastAPI) -> int:
    """Remove interactive-docs routes. Returns how many were removed."""
    if settings.docs_enabled:
        return 0
    kept = [r for r in application.router.routes if getattr(r, "path", None) not in DOCS_ROUTES]
    removed = len(application.router.routes) - len(kept)
    application.router.routes[:] = kept
    return removed

cors_origins = list(dict.fromkeys([
    *settings.cors_origins,
    "https://placement-os-rust.vercel.app",
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response

app.include_router(auth_router)
app.include_router(opportunities.router)
app.include_router(import_.router)
app.include_router(reminders.router)
app.include_router(settings_router.router)
app.include_router(storage_router.router)
app.include_router(gemini_router.router)

apply_docs_policy(app)

@app.get("/api/health")
async def health():
    """Ultra-light liveness probe — must NEVER block on the DB.

    Used by Render's health check and by free uptime pingers. Returning
    quickly even during cold start prevents the platform from killing the
    container before background init finishes.
    """
    try:
        from services.watchdog import get_last_received, get_userbot_error, _userbot_running
        last = get_last_received()
        userbot_running = _userbot_running
        userbot_error = get_userbot_error()
    except Exception:
        last, userbot_running, userbot_error = None, False, None

    # "ok" as soon as the web process is up; everything else is informational.
    return {
        "status": "ok",
        "db_ready": _boot_state["db"],
        "userbot_running": userbot_running,
        "bot_ready": _boot_state["bot"],
        "boot_started_at": _boot_state["started_at"],
        "last_message": last.isoformat() if last else None,
        "userbot_error": userbot_error,
    }


@app.get("/api/health/deep")
async def health_deep():
    """Detailed status including a live DB ping — for diagnostics only."""
    from database import is_db_ready, ensure_connection
    db_reachable = await ensure_connection()
    try:
        from services.watchdog import get_last_received, get_userbot_error, _userbot_running
        last = get_last_received()
        userbot_running = _userbot_running
        userbot_error = get_userbot_error()
    except Exception:
        last, userbot_running, userbot_error = None, False, None

    return {
        "status": "ok" if (db_reachable and userbot_running) else "degraded",
        "db_reachable": db_reachable,
        "db_ready": is_db_ready(),
        "userbot_running": userbot_running,
        "bot_ready": _boot_state["bot"],
        "boot_started_at": _boot_state["started_at"],
        "last_message": last.isoformat() if last else None,
        "userbot_error": userbot_error,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
