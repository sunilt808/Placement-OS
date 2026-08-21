"""
database.py — Async MongoDB connection via Motor.
Collections: opportunities, messages, opportunity_events, reminders, settings
"""
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

_client: AsyncIOMotorClient | None = None


async def connect_db():
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    # Verify connection
    await _client.admin.command("ping")
    print(f"[DB] Connected to MongoDB: {settings.mongodb_db}")


async def close_db():
    global _client
    if _client:
        _client.close()
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
    """Create indexes for efficient querying."""
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
