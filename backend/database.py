"""
database.py — Async MongoDB connection via Motor.
Collections: opportunities, messages, opportunity_events, reminders, settings

Hardened for serverless/free-tier hosts (Render):
  * Explicit, short timeouts so a slow/paused Atlas cluster can never hang a
    request or the app startup for the default 30s.
  * `retryWrites`/`retryReads` so transient Atlas blips auto-recover.
  * A background reconnect loop keeps the client healthy after restarts.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

_client: AsyncIOMotorClient | None = None
_db_ready: bool = False
_reconnect_task: asyncio.Task | None = None


def _build_client() -> AsyncIOMotorClient:
    """Create a Motor client with free-tier-safe timeouts.

    serverSelectionTimeoutMS is deliberately short (8s) so a paused/overloaded
    Atlas M0 surfaces an error quickly instead of blocking the whole app.
    """
    return AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=8000,
        connectTimeoutMS=8000,
        socketTimeoutMS=20000,
        maxPoolSize=20,
        minPoolSize=1,
        retryWrites=True,
        retryReads=True,
        appname="placementos",
    )


async def connect_db(retries: int = 3, delay: float = 2.0) -> bool:
    """Connect to MongoDB. Never raises — returns True/False.

    Startup must survive a temporarily unreachable Atlas so the web service
    still boots (health endpoint reachable) and can recover on its own.
    """
    global _client, _db_ready
    for attempt in range(1, retries + 1):
        try:
            if _client is None:
                _client = _build_client()
            await _client.admin.command("ping")
            _db_ready = True
            print(f"[DB] Connected to MongoDB: {settings.mongodb_db}")
            return True
        except Exception as e:
            print(f"[DB] Connect attempt {attempt}/{retries} failed: "
                  f"{type(e).__name__}: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
    _db_ready = False
    print("[DB] MongoDB not reachable yet — will keep retrying in background.")
    return False


async def ensure_connection() -> bool:
    """Ping the DB, reconnecting if the pool went stale. Safe to call often."""
    global _client, _db_ready
    try:
        if _client is None:
            return await connect_db(retries=1)
        await _client.admin.command("ping")
        _db_ready = True
        return True
    except Exception as e:
        _db_ready = False
        print(f"[DB] Connection lost ({type(e).__name__}: {e}) — reconnecting...")
        try:
            if _client is not None:
                _client.close()
        except Exception:
            pass
        _client = None
        return await connect_db(retries=2, delay=1.0)


async def _reconnect_loop():
    """Background watchdog: keep the DB client healthy without user action."""
    while True:
        try:
            await asyncio.sleep(60)
            if not _db_ready:
                await ensure_connection()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[DB] Reconnect loop error: {e}")


def start_db_watchdog():
    """Start the background reconnect loop (idempotent)."""
    global _reconnect_task
    if _reconnect_task is None or _reconnect_task.done():
        _reconnect_task = asyncio.create_task(_reconnect_loop())


def is_db_ready() -> bool:
    return _db_ready


async def close_db():
    global _client, _reconnect_task, _db_ready
    if _reconnect_task:
        _reconnect_task.cancel()
        _reconnect_task = None
    if _client:
        _client.close()
        _db_ready = False
        print("[DB] MongoDB connection closed")



def get_db():
    return _client[settings.mongodb_db]


# ── Collection accessors ──────────────────────────────────────────────────────

def opportunities_col():
    return get_db()["opportunities"]


def messages_col():
    return get_db()["messages"]


def events_col():
    return get_db()["opportunity_events"]


def reminders_col():
    return get_db()["reminders"]


def app_settings_col():
    return get_db()["app_settings"]


# ── Index setup ───────────────────────────────────────────────────────────────

async def ensure_indexes():
    """Create indexes for efficient querying. Non-fatal if DB is unreachable."""
    if not _db_ready:
        print("[DB] Skipping index setup — DB not ready.")
        return
    try:
        db = get_db()

        # opportunities
        await db["opportunities"].create_index([("company", 1), ("role", 1)])
        await db["opportunities"].create_index([("deadline", 1)])
        await db["opportunities"].create_index([("status", 1)])
        await db["opportunities"].create_index([("created_at", -1)])

        # messages
        await db["messages"].create_index([("content_hash", 1)], unique=True)
        await db["messages"].create_index([("telegram_message_id", 1)])
        await db["messages"].create_index([("message_date", -1)])

        # events
        await db["opportunity_events"].create_index([("opportunity_id", 1), ("timestamp", 1)])

        # reminders
        await db["reminders"].create_index([("opportunity_id", 1)])
        await db["reminders"].create_index([("scheduled_time", 1), ("sent", 1)])

        print("[DB] Indexes ensured")
    except Exception as e:
        print(f"[DB] Index setup failed (non-fatal): {e}")
