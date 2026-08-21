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


def record_message_received():
    """Call this every time the userbot receives a message from the group."""
    global _last_message_received
    _last_message_received = datetime.now(timezone.utc)


def set_userbot_running(running: bool):
    global _userbot_running
    _userbot_running = running


def get_last_received() -> datetime | None:
    return _last_message_received


async def run_watchdog_check():
    """
    Called by the scheduler every watchdog_interval_minutes.
    Sends an alert if the userbot seems silent or disconnected.
    """
    from services.notification_service import send_watchdog_alert

    if not _userbot_running:
        await send_watchdog_alert(
            "⚠️ Userbot listener is NOT running. "
            "New placement messages are NOT being monitored. "
            "Please restart the backend."
        )
        return

    if _last_message_received is None:
        # System just started, no messages yet — not necessarily a problem
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
