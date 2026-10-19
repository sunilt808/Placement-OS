"""
main.py — PlacementOS FastAPI application entry point.
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Main] Starting PlacementOS AI Monitor...")
    await connect_db()
    await ensure_indexes()
    start_scheduler()

    userbot_task = None
    try:
        from userbot import run_userbot_forever
        userbot_task = asyncio.create_task(run_userbot_forever())
        print("[Main] Telegram userbot supervisor started")
    except Exception as e:
        print(f"[Main] Userbot error: {e}")

    if settings.startup_ping and settings.telegram_bot_token and settings.telegram_chat_id:
        async def _startup_ping():
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
        asyncio.create_task(_startup_ping())

    bot_app = None
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            from telegram_bot import build_bot_app
            bot_app = build_bot_app()
            await bot_app.initialize()
            await bot_app.start()
            await bot_app.updater.start_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"[Main] Telegram bot error: {e}")
            bot_app = None
    else:
        print("[Main] Telegram bot not configured — continuing without notifications.")

    yield

    print("[Main] Shutting down...")
    stop_scheduler()
    if userbot_task:
        userbot_task.cancel()
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
    try:
        from services.watchdog import (
            get_last_received,
            get_userbot_error,
            _userbot_running,
        )
        last = get_last_received()
        userbot_running = _userbot_running
        return {
            "status": "ok" if userbot_running else "degraded",
            "userbot_running": userbot_running,
            "last_message": last.isoformat() if last else None,
            "userbot_error": get_userbot_error(),
        }
    except Exception as error:
        print(f"[Health] Could not read userbot status: {error}")
        return {
            "status": "degraded",
            "userbot_running": False,
            "last_message": None,
            "userbot_error": f"{type(error).__name__}: {error}",
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
