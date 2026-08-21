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
from api.routes.auth import router as auth_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Main] Starting PlacementOS AI Monitor...")
    await connect_db()
    await ensure_indexes()
    start_scheduler()

    userbot_task = None
    try:
        from userbot import start_userbot
        userbot_task = asyncio.create_task(start_userbot())
    except Exception as e:
        print(f"[Main] Userbot error: {e}")

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
    else:
        print("[Main] Telegram bot not configured — continuing without notifications.")

    yield

    print("[Main] Shutting down...")
    stop_scheduler()
    if userbot_task:
        userbot_task.cancel()
    if bot_app:
        try:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
        except:
            pass
    await close_db()

app = FastAPI(
    title="PlacementOS API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(opportunities.router)
app.include_router(import_.router)
app.include_router(reminders.router)
app.include_router(settings_router.router)

@app.get("/api/health")
async def health():
    try:
        from services.watchdog import get_last_received, _userbot_running
        last = get_last_received()
        return {"status": "ok", "userbot_running": _userbot_running, "last_message": last.isoformat() if last else None}
    except:
        return {"status": "ok", "userbot_running": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
