"""
api/routes/reminders.py — Reminder management routes.
"""
from fastapi import APIRouter
from services.reminder_service import get_upcoming_reminders

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("")
async def list_reminders(limit: int = 20):
    """Get upcoming reminders."""
    reminders = await get_upcoming_reminders(limit=limit)
    for r in reminders:
        if r.get("scheduled_time"):
            from datetime import datetime
            if isinstance(r["scheduled_time"], datetime):
                r["scheduled_time"] = r["scheduled_time"].isoformat()
    return {"reminders": reminders}
