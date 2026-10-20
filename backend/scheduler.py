"""
scheduler.py — APScheduler background jobs.

Jobs:
  1. Reminder check — every 15 minutes
  2. Daily summary — every day at configured hour (default: 8 AM IST)
  3. Watchdog check — every watchdog_interval_minutes
  4. Missed opportunity check — daily
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from config import settings

IST = pytz.timezone(settings.timezone)
_scheduler: AsyncIOScheduler | None = None


async def _run_reminder_check():
    """Check for due reminders and send Telegram alerts."""
    from services.reminder_service import get_due_reminders, mark_reminder_sent
    from services.notification_service import send_reminder
    from database import opportunities_col
    from bson import ObjectId

    reminders = await get_due_reminders()
    for reminder in reminders:
        try:
            opp = reminder.get("opportunity")
            opp_id = reminder["opportunity_id"]
            reminder_id = reminder["_id"]
            reminder_type = reminder.get("reminder_type", "")

            if opp:
                await send_reminder(opp, opp_id, reminder_type)
                await mark_reminder_sent(reminder_id)
                print(f"[Scheduler] Sent {reminder_type} reminder for {opp.get('company')}")
        except Exception as e:
            print(f"[Scheduler] Reminder error: {e}")


async def _run_daily_summary():
    """Send daily placement summary at configured hour."""
    from database import opportunities_col
    from services.notification_service import send_daily_summary
    from services.deadline_engine import get_urgency, DeadlineUrgency
    from datetime import datetime, timezone

    col = opportunities_col()
    now = datetime.now(timezone.utc)

    active = await col.count_documents({"status": {"$nin": ["IGNORED", "EXPIRED"]}})
    applied = await col.count_documents({"status": "APPLIED"})
    not_applied = await col.count_documents({"status": {"$in": ["NEW", "VIEWED", "NOT_APPLIED"]}})

    # Count by urgency
    deadline_today = 0
    deadline_tomorrow = 0
    this_week = 0
    upcoming = 0

    async for opp in col.find({"status": {"$nin": ["APPLIED", "IGNORED", "EXPIRED"]}}):
        urgency = get_urgency(opp.get("deadline"))
        if urgency in (DeadlineUrgency.TODAY, DeadlineUrgency.WITHIN_24H):
            deadline_today += 1
        elif urgency == DeadlineUrgency.TOMORROW:
            deadline_tomorrow += 1
        elif urgency in (DeadlineUrgency.WITHIN_3_DAYS, DeadlineUrgency.THIS_WEEK):
            this_week += 1
        elif urgency == DeadlineUrgency.UPCOMING:
            upcoming += 1

    stats = {
        "active": active,
        "applied": applied,
        "not_applied": not_applied,
        "deadline_today": deadline_today,
        "deadline_tomorrow": deadline_tomorrow,
        "this_week": this_week,
        "upcoming": upcoming,
    }
    await send_daily_summary(stats)


async def _run_watchdog():
    from services.watchdog import run_watchdog_check
    await run_watchdog_check()


async def _run_message_cleanup():
    from services.message_retention import purge_expired_messages
    await purge_expired_messages(settings.message_retention_days)


async def _run_lifecycle_cleanup():
    """Auto-expire overdue drives + cancel zombie reminders."""
    from services.lifecycle_janitor import run_lifecycle_cleanup
    try:
        expired = await run_lifecycle_cleanup(settings.expiry_grace_hours)
        if expired:
            print(f"[Scheduler] Lifecycle janitor expired {expired} stale drive(s)")
    except Exception as e:
        print(f"[Scheduler] Lifecycle cleanup error: {e}")


async def _run_retention_purge():
    """Cloud-storage guardian: delete messages/drives past the retention window."""
    from services.storage_service import purge_older_than
    try:
        summary = await purge_older_than(settings.data_retention_days)
        if summary["opportunities_deleted"] or summary["messages_deleted"]:
            print(f"[Scheduler] Retention purge ({summary['days']}d): "
                  f"{summary['messages_deleted']} messages, "
                  f"{summary['opportunities_deleted']} drives deleted")
    except Exception as e:
        print(f"[Scheduler] Retention purge error: {e}")


async def _run_storage_check():
    """Telegram warning when the database nears its free-tier quota."""
    from services.storage_service import check_storage_and_alert
    try:
        await check_storage_and_alert()
    except Exception as e:
        print(f"[Scheduler] Storage check error: {e}")


async def _run_self_ping():
    """Hit our own public /api/health to keep Render's free instance warm.

    While the service is awake this resets the idle timer so it is not spun
    down mid-day. (A fully asleep instance needs an external pinger.)
    """
    if not settings.self_ping_enabled or not settings.public_base_url:
        return
    url = settings.public_base_url.rstrip("/") + "/api/health"
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            print(f"[SelfPing] {resp.status_code} {url}")
    except Exception as e:
        print(f"[SelfPing] failed: {e}")


async def _run_db_health():
    """Ensure the Mongo client stays connected; reconnect if it went stale."""
    from database import ensure_connection
    try:
        await ensure_connection()
    except Exception as e:
        print(f"[Scheduler] DB health error: {e}")


def start_scheduler():
    """Initialize and start the APScheduler."""
    global _scheduler
    from services.watchdog import mark_started

    mark_started()
    _scheduler = AsyncIOScheduler(timezone=IST)

    # Reminder check every 15 minutes
    _scheduler.add_job(
        _run_reminder_check,
        trigger=IntervalTrigger(minutes=15),
        id="reminder_check",
        replace_existing=True,
    )

    # Raw messages are an inspection inbox, not permanent storage. Source PDFs
    # linked to an opportunity remain available after this cleanup.
    _scheduler.add_job(
        _run_message_cleanup,
        trigger=CronTrigger(hour=3, minute=15, timezone=IST),
        id="message_cleanup",
        replace_existing=True,
    )

    # Daily summary at configured hour (IST)
    _scheduler.add_job(
        _run_daily_summary,
        trigger=CronTrigger(hour=settings.daily_summary_hour, minute=0, timezone=IST),
        id="daily_summary",
        replace_existing=True,
    )

    # Watchdog check
    _scheduler.add_job(
        _run_watchdog,
        trigger=IntervalTrigger(minutes=settings.watchdog_interval_minutes),
        id="watchdog",
        replace_existing=True,
    )

    # Lifecycle janitor — hourly auto-expiry + reminder hygiene
    _scheduler.add_job(
        _run_lifecycle_cleanup,
        trigger=IntervalTrigger(hours=1),
        id="lifecycle_cleanup",
        replace_existing=True,
    )

    # Storage guardian — daily retention purge + quota check every 6 hours
    _scheduler.add_job(
        _run_retention_purge,
        trigger=CronTrigger(hour=3, minute=45, timezone=IST),
        id="retention_purge",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_storage_check,
        trigger=IntervalTrigger(hours=6),
        id="storage_check",
        replace_existing=True,
    )

    # Self-ping keep-alive + DB health (keeps free instance warm & connected)
    _scheduler.add_job(
        _run_self_ping,
        trigger=IntervalTrigger(minutes=settings.self_ping_interval_minutes),
        id="self_ping",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_db_health,
        trigger=IntervalTrigger(minutes=5),
        id="db_health",
        replace_existing=True,
    )

    _scheduler.start()
    print(f"[Scheduler] Started. Reminder check: every 15min | Daily summary: {settings.daily_summary_hour}:00 IST | Watchdog: every {settings.watchdog_interval_minutes}min | Janitor: hourly")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped")
