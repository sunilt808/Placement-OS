"""
main.py — FastAPI application entry point.

Startup sequence:
1. Connect MongoDB
2. Ensure indexes
3. Start APScheduler
4. Start Telethon userbot (in background)
5. Start Bot API polling (in background)

Shutdown:
1. Stop scheduler
2. Disconnect userbot
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import connect_db, close_db, ensure_indexes
from scheduler import start_scheduler, stop_scheduler
from api.routes import opportunities, import_, reminders, settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # ── Startup ───────────────────────────────────────────────────────────────
    print("[Main] Starting AI Placement Monitor...")
    await connect_db()
    await ensure_indexes()
    start_scheduler()

    # Start Telethon userbot in background
    userbot_task = None
    try:
        from userbot import start_userbot
        userbot_task = asyncio.create_task(start_userbot())
        print("[Main] Userbot task launched")
    except Exception as e:
        print(f"[Main] Userbot could not start: {e}")

    # Start Bot API polling in background
    bot_app = None
    try:
        from telegram_bot import build_bot_app
        bot_app = build_bot_app()
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        print("[Main] Telegram bot polling started")
    except Exception as e:
        print(f"[Main] Bot could not start: {e}")

    print("[Main] All systems running")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    print("[Main] Shutting down...")
    stop_scheduler()

    if userbot_task:
        userbot_task.cancel()
        try:
            await userbot_task
        except asyncio.CancelledError:
            pass

    if bot_app:
        try:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
        except Exception:
            pass

    await close_db()
    print("[Main] Shutdown complete")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Placement Monitor",
    description="Personal AI-powered placement monitoring system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(opportunities.router)
app.include_router(import_.router)
app.include_router(reminders.router)
app.include_router(settings_router.router)


@app.get("/api/health")
async def health():
    from services.watchdog import get_last_received, _userbot_running
    last = get_last_received()
    return {
        "status": "ok",
        "userbot_running": _userbot_running,
        "last_message": last.isoformat() if last else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
