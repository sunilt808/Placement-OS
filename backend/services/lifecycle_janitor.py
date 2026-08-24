"""
services/lifecycle_janitor.py — Automatic opportunity lifecycle maintenance.

Deterministic Python-only cleanup (no AI involvement):

1. Auto-expiry: any open opportunity whose deadline passed more than
   `expiry_grace_hours` ago becomes EXPIRED (never touches APPLIED/IGNORED).
2. Zombie reminder cleanup: pending reminders of expired drives are
   cancelled so the reminder table stays honest.
3. Every transition is logged as a STATUS_CHANGED timeline event so the
   history shows *when* the system expired the drive.

Run by the scheduler (hourly) — safe to run repeatedly; already-expired
drives are never re-processed.
"""
from datetime import datetime, timedelta

from database import opportunities_col, events_col
from models.opportunity import ApplicationStatus, EventType, OpportunityEvent
from services.reminder_service import cancel_all_reminders

TERMINAL_STATUSES = [
    ApplicationStatus.APPLIED,
    ApplicationStatus.IGNORED,
    ApplicationStatus.EXPIRED,
]


async def run_lifecycle_cleanup(expiry_grace_hours: int = 12) -> int:
    """
    Expire overdue open opportunities and cancel their pending reminders.
    Returns the number of newly expired drives.
    """
    col = opportunities_col()
    cutoff = datetime.utcnow() - timedelta(hours=expiry_grace_hours)

    query = {
        "status": {"$nin": TERMINAL_STATUSES},
        "deadline": {"$ne": None, "$lt": cutoff},
    }

    expired_count = 0
    async for opp in col.find(query):
        opp_id = str(opp["_id"])
        old_status = opp.get("status", ApplicationStatus.NEW)

        await col.update_one(
            {"_id": opp["_id"]},
            {"$set": {
                "status": ApplicationStatus.EXPIRED,
                "updated_at": datetime.utcnow(),
            }}
        )

        await events_col().insert_one(OpportunityEvent(
            opportunity_id=opp_id,
            event_type=EventType.STATUS_CHANGED,
            old_value=str(old_status),
            new_value=ApplicationStatus.EXPIRED,
            note=f"Auto-expired: deadline passed more than {expiry_grace_hours}h ago",
        ).model_dump())

        await cancel_all_reminders(opp_id)
        expired_count += 1

    return expired_count
