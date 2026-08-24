"""
services/storage_service.py — Cloud-storage guardian.

MongoDB Atlas M0 gives ~512 MB free. This service reports usage, warns near
the ceiling, and purges stale data so the database never chokes.
"""
from datetime import datetime, timedelta

import database
from config import settings


LIMIT_MB = getattr(settings, "storage_limit_mb", 512)
WARN_MB = getattr(settings, "storage_warn_mb", 450)

EVENTS_COLL = "opportunity_events"


async def get_storage_stats() -> dict:
    """Real usage from MongoDB plus a friendly breakdown."""
    db = database.get_db()
    stats = await db.command("dbstats")
    used_bytes = stats.get("dataSize", 0) + stats.get("indexSize", 0)
    used_mb = round(used_bytes / (1024 * 1024), 1)

    breakdown = {}
    for name in ("opportunities", "messages", EVENTS_COLL,
                 "reminders", "app_settings"):
        try:
            s = await db.command("collstats", name)
            breakdown[name] = {
                "mb": round(s.get("size", 0) / (1024 * 1024), 2),
                "count": s.get("count", 0),
            }
        except Exception:
            breakdown[name] = {"mb": 0, "count": 0}

    return {
        "used_mb": used_mb,
        "limit_mb": LIMIT_MB,
        "warn_mb": WARN_MB,
        "percent": round(min(100.0, used_mb / LIMIT_MB * 100), 1),
        "should_warn": used_mb >= WARN_MB,
        "collections": breakdown,
        "checked_at": datetime.utcnow().isoformat(),
    }


def _oid(oid_str):
    from bson import ObjectId

    try:
        return ObjectId(oid_str)
    except Exception:
        return None


async def delete_opportunity_cascade(db, oid) -> int:
    """Delete one opportunity + its events, reminders and stored document."""
    from services.pdf_service import delete_stored_document

    opp = await db["opportunities"].find_one(
        {"_id": oid}, {"source_document_key": 1})
    if not opp:
        return 0
    key = opp.get("source_document_key")
    if key:
        try:
            delete_stored_document(key)
        except Exception:
            pass
    await db[EVENTS_COLL].delete_many({"opportunity_id": str(oid)})
    await db["reminders"].delete_many({"opportunity_id": str(oid)})
    await db["messages"].update_many(
        {"opportunity_id": str(oid)}, {"$set": {"opportunity_id": None}})
    res = await db["opportunities"].delete_one({"_id": oid})
    return res.deleted_count


async def delete_opportunities_bulk(ids: list[str]) -> int:
    db = database.get_db()
    deleted = 0
    for raw in ids or []:
        oid = _oid(raw)
        if oid:
            deleted += await delete_opportunity_cascade(db, oid)
    return deleted


async def delete_messages_bulk(ids: list[str]) -> int:
    from services.pdf_service import delete_stored_document

    db = database.get_db()
    oids = [o for o in (_oid(i) for i in ids or []) if o]
    if not oids:
        return 0
    for m in await db["messages"].find(
            {"_id": {"$in": oids}},
            {"attachment_storage_key": 1}).to_list(length=None):
        if m.get("attachment_storage_key"):
            try:
                delete_stored_document(m["attachment_storage_key"])
            except Exception:
                pass
    res = await db["messages"].delete_many({"_id": {"$in": oids}})
    return res.deleted_count


async def purge_older_than(days: int) -> dict:
    """
    Auto/manual retention purge:
      - messages older than `days`
      - opportunities whose deadline passed more than `days` ago
        (or EXPIRED ones untouched for `days`), with full cascade.
    """
    db = database.get_db()
    cutoff = datetime.utcnow() - timedelta(days=days)
    summary = {"messages_deleted": 0, "opportunities_deleted": 0, "days": days}

    msg_res = await db["messages"].delete_many({"message_date": {"$lt": cutoff}})
    summary["messages_deleted"] = msg_res.deleted_count

    stale = db["opportunities"].find({
        "$or": [
            {"deadline": {"$ne": None, "$lt": cutoff}},
            {"status": "EXPIRED", "updated_at": {"$lt": cutoff}},
            {"updated_at": {"$lt": cutoff - timedelta(days=days)}},
        ]
    }, {"_id": 1})
    async for doc in stale:
        summary["opportunities_deleted"] += await delete_opportunity_cascade(
            db, doc["_id"])
    return summary


_storage_alert_sent = False


async def check_storage_and_alert() -> None:
    """Scheduler hook: Telegram warning when usage crosses the warn line."""
    global _storage_alert_sent
    stats = await get_storage_stats()
    if stats["should_warn"]:
        if _storage_alert_sent:
            return  # nag once per threshold crossing, not every run
        _storage_alert_sent = True
        from services.notification_service import send_storage_alert

        await send_storage_alert(stats["used_mb"], stats["limit_mb"],
                                 stats["percent"], stats["collections"])
    else:
        _storage_alert_sent = False
