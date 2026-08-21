"""
services/deadline_engine.py — Converts a deadline datetime to an urgency state.
All computation is done in Python (deterministic), never delegated to AI.
Stored and computed in UTC; displayed in IST.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz

from models.opportunity import DeadlineUrgency

IST = pytz.timezone("Asia/Kolkata")


def now_ist() -> datetime:
    """Current time in IST."""
    return datetime.now(IST)


def now_utc() -> datetime:
    """Current time in UTC."""
    return datetime.now(timezone.utc)


def get_urgency(deadline: Optional[datetime]) -> DeadlineUrgency:
    """
    Compute urgency state from a deadline datetime.
    Input deadline can be UTC or timezone-aware; comparison is done correctly.
    """
    if deadline is None:
        return DeadlineUrgency.NO_DEADLINE

    now = datetime.now(timezone.utc)

    # Ensure deadline is timezone-aware (assume IST if naive)
    if deadline.tzinfo is None:
        deadline = IST.localize(deadline)

    # Convert both to UTC for comparison
    deadline_utc = deadline.astimezone(timezone.utc)
    diff = deadline_utc - now

    if diff.total_seconds() <= 0:
        return DeadlineUrgency.EXPIRED
    elif diff.total_seconds() <= 3 * 3600:   # ≤ 3 hours
        return DeadlineUrgency.TODAY
    elif diff.total_seconds() <= 24 * 3600:  # ≤ 24 hours
        return DeadlineUrgency.WITHIN_24H
    elif diff.total_seconds() <= 48 * 3600:  # ≤ 48 hours
        return DeadlineUrgency.TOMORROW
    elif diff.total_seconds() <= 72 * 3600:  # ≤ 3 days
        return DeadlineUrgency.WITHIN_3_DAYS
    elif diff.total_seconds() <= 7 * 24 * 3600:  # ≤ 7 days
        return DeadlineUrgency.THIS_WEEK
    else:
        return DeadlineUrgency.UPCOMING


def format_deadline_ist(deadline: Optional[datetime]) -> Optional[str]:
    """Format deadline for display in IST."""
    if deadline is None:
        return None
    if deadline.tzinfo is None:
        deadline = IST.localize(deadline)
    ist_dt = deadline.astimezone(IST)
    return ist_dt.strftime("%d %b %Y, %I:%M %p IST")


def reminder_times(deadline: datetime) -> list[datetime]:
    """
    Returns the UTC datetimes at which reminders should be sent:
    - 3 days before deadline
    - 24 hours before deadline
    - 3 hours before deadline
    """
    if deadline.tzinfo is None:
        deadline = IST.localize(deadline)
    deadline_utc = deadline.astimezone(timezone.utc)
    return [
        deadline_utc - timedelta(days=3),
        deadline_utc - timedelta(hours=24),
        deadline_utc - timedelta(hours=3),
    ]


def time_remaining_str(deadline: Optional[datetime]) -> str:
    """Human-readable time remaining string."""
    if deadline is None:
        return "No deadline"
    if deadline.tzinfo is None:
        deadline = IST.localize(deadline)
    now = datetime.now(timezone.utc)
    diff = deadline.astimezone(timezone.utc) - now
    if diff.total_seconds() <= 0:
        return "Expired"
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h remaining"
    elif hours > 0:
        return f"{hours}h {minutes}m remaining"
    else:
        return f"{minutes}m remaining"
