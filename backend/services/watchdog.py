"""
services/watchdog.py — Monitor userbot session health.

The revised plan identified this as the most dangerous failure mode:
the Telethon session silently goes offline while everything looks normal.

This watchdog:
1. Tracks the last time a live message was received.
2. If gap > watchdog_interval_minutes → sends a Telegram DM alert.
3. Also checks if the Telethon client is still connected.
"""
from datetime import datetime, timezone, timedelta
from config import settings

# Shared state — updated by the userbot on every received message
_last_message_received: datetime | None = None
_userbot_running: bool = False
_started_at: datetime | None = None
_selfheal_done: bool = False
_userbot_error: str | None = None


def mark_started():
    """Record backend startup — enables the deaf-listener self-heal check."""
    global _started_at
    if _started_at is None:
        _started_at = datetime.now(timezone.utc)


def record_message_received():
    """Call this every time the userbot receives a message from the group."""
    global _last_message_received
    _last_message_received = datetime.now(timezone.utc)


def set_userbot_running(running: bool):
    global _userbot_running, _userbot_error
    _userbot_running = running
    if running:
        _userbot_error = None


def set_userbot_error(error: str):
    """Record the latest listener failure for logs and the health endpoint."""
    global _userbot_error
    _userbot_error = error


def get_userbot_error() -> str | None:
    return _userbot_error


def get_last_received() -> datetime | None:
    return _last_message_received


async def run_watchdog_check():
    """
    Called by the scheduler every watchdog_interval_minutes.
    Sends an alert if the userbot seems silent or disconnected.
    """
    global _selfheal_done
    from services.notification_service import send_watchdog_alert

    if not _userbot_running:
        await send_watchdog_alert(
            "⚠️ Userbot listener is NOT running. "
            "New placement messages are NOT being monitored. "
            "Please restart the backend."
        )
        return

    if _last_message_received is None:
        # Dangerous silent case: listener claims to run but has NEVER received
        # anything. After 2x the watchdog interval, alert once and auto-heal by
        # re-running the catch-up history scan (covers downtime + dead sessions).
        if (
            _started_at is not None
            and not _selfheal_done
            and datetime.now(timezone.utc) - _started_at
                > timedelta(minutes=settings.watchdog_interval_minutes * 2)
        ):
            _selfheal_done = True
            await send_watchdog_alert(
                "⚠️ No live message received since startup. The listener may be "
                "deaf (stale session / quiet group). Auto-running a catch-up "
                "history scan now."
            )
            try:
                from userbot import trigger_manual_history_scan

                await trigger_manual_history_scan(days=settings.catchup_days)
            except Exception as heal_err:
                print(f"[Watchdog] Self-heal scan failed: {heal_err}")
        return

    now = datetime.now(timezone.utc)
    gap = now - _last_message_received
    threshold = timedelta(minutes=settings.watchdog_interval_minutes * 2)

    if gap > threshold:
        await send_watchdog_alert(
            f"⚠️ Userbot has been silent for {int(gap.total_seconds() / 60)} minutes.\n"
            f"Last message received: {_last_message_received.strftime('%d %b %Y %H:%M IST')}\n\n"
            "The session may have expired or the placement group may be quiet. "
            "Please check manually."
        )
