"""
services/reminder_service.py — Schedule and manage deadline reminders.

Rules (from plan):
- 3 reminders per opportunity: 3 days before, 24 hours before, 3 hours before.
- Send each reminder only once.
- Stop reminders once status = APPLIED.
- On deadline extension, cancel old reminders and schedule new ones.
"""
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId

from database import reminders_col, opportunities_col
from models.message import ReminderType
from services.deadline_engine import reminder_times


async def schedule_reminders(
    opportunity_id: str,
    deadline: datetime,
    reschedule: bool = False,
):
    """
    Schedule 3-day, 24h, and 3h reminders for a deadline.
    If reschedule=True, cancel any existing unsent reminders first.
    """
    col = reminders_col()

    if reschedule:
        # Cancel existing unsent reminders for this opportunity
        await col.update_many(
            {"opportunity_id": opportunity_id, "sent": False},
            {"$set": {"cancelled": True}}
        )

    times = reminder_times(deadline)
    reminder_type_map = [
        ReminderType.THREE_DAYS,
        ReminderType.TWENTY_FOUR_HOURS,
        ReminderType.THREE_HOURS,
    ]

    now = datetime.now(timezone.utc)
    for scheduled_time, reminder_type in zip(times, reminder_type_map):
        # Only schedule if the reminder time is in the future
        if scheduled_time > now:
            await col.insert_one({
                "opportunity_id": opportunity_id,
                "reminder_type": reminder_type,
                "scheduled_time": scheduled_time.replace(tzinfo=None),
                "sent": False,
                "sent_at": None,
                "cancelled": False,
            })


async def get_due_reminders() -> list[dict]:
    """
    Returns all reminders that are due (scheduled_time <= now) and not yet sent.
    Called by the scheduler every 15 minutes.
    """
    col = reminders_col()
    now = datetime.utcnow()

    reminders = []
    cursor = col.find({
        "scheduled_time": {"$lte": now},
        "sent": False,
        "cancelled": False,
    })
    async for r in cursor:
        # Check if the opportunity is still open (not APPLIED or IGNORED)
        opp = await opportunities_col().find_one({"_id": ObjectId(r["opportunity_id"])})
        if opp and opp.get("status") not in ["APPLIED", "IGNORED", "EXPIRED"]:
            r["_id"] = str(r["_id"])
            r["opportunity"] = opp
            reminders.append(r)

    return reminders


async def mark_reminder_sent(reminder_id: str):
    """Mark a reminder as sent."""
    col = reminders_col()
    await col.update_one(
        {"_id": ObjectId(reminder_id)},
        {"$set": {"sent": True, "sent_at": datetime.utcnow()}}
    )


async def cancel_all_reminders(opportunity_id: str):
    """Cancel all pending reminders for an opportunity (e.g., when APPLIED)."""
    col = reminders_col()
    await col.update_many(
        {"opportunity_id": opportunity_id, "sent": False},
        {"$set": {"cancelled": True}}
    )


async def get_upcoming_reminders(limit: int = 20) -> list[dict]:
    """Get upcoming reminders for dashboard display."""
    col = reminders_col()
    now = datetime.utcnow()
    reminders = []
    cursor = col.find(
        {"scheduled_time": {"$gte": now}, "sent": False, "cancelled": False},
        sort=[("scheduled_time", 1)],
        limit=limit,
    )
    async for r in cursor:
        opp = await opportunities_col().find_one({"_id": ObjectId(r["opportunity_id"])})
        r["_id"] = str(r["_id"])
        if opp:
            r["company"] = opp.get("company")
            r["role"] = opp.get("role")
        reminders.append(r)
    return reminders
