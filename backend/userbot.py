"""
userbot.py — Telethon personal-account listener (PRIMARY ingestion path).

This is Phase 0 / the core architectural fix from the revised plan.
Logs into the student's own Telegram account (not a bot) and silently
listens to every new message in the placement group in real-time.

No bot needs to be added to the group.
No manual forwarding needed.
Every message the student's account can see, the pipeline can see.

SECURITY:
- api_id, api_hash, and session_string are environment variables only.
- This is strictly READ-ONLY — never sends, joins, or modifies anything.
- Session string stored in .env; never committed to git.

USAGE:
  python userbot.py          # Start the listener standalone
  Or managed by scheduler.py / main.py lifespan.
"""
import asyncio
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import pytz

from config import settings
from models.message import MessageSource
from services.message_pipeline import ingest_message
from services.watchdog import record_message_received, set_userbot_running

IST = pytz.timezone("Asia/Kolkata")

_client: TelegramClient | None = None


async def start_userbot():
    """Initialize and start the Telethon userbot listener."""
    global _client

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("[Userbot] No API credentials found — skipping userbot. "
              "Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")
        print("[Userbot] Run setup_session.py to generate TELEGRAM_SESSION_STRING")
        return

    if not settings.telegram_session_string:
        print("[Userbot] No session string found. Run: python setup_session.py")
        return

    if not settings.placement_group_id:
        print("[Userbot] PLACEMENT_GROUP_ID not set in .env — userbot won't know which group to watch")

    try:
        _client = TelegramClient(
            StringSession(settings.telegram_session_string),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

        await _client.start()
        set_userbot_running(True)
        print("[Userbot] ✅ Telethon session connected. Listening for placement messages...")

        @_client.on(events.NewMessage(chats=settings.placement_group_id))
        async def on_new_message(event):
            """Handle every new message in the placement group."""
            record_message_received()  # Update watchdog heartbeat

            text = event.message.message or ""
            if not text.strip():
                return  # Skip media-only messages (for now)

            # Use the actual message send time, not processing time
            msg_date = event.message.date
            if msg_date.tzinfo is None:
                msg_date = IST.localize(msg_date)

            sender_name = ""
            try:
                sender = await event.get_sender()
                if sender:
                    sender_name = getattr(sender, "first_name", "") or ""
            except Exception:
                pass

            print(f"[Userbot] New message from {sender_name}: {text[:80]}...")

            await ingest_message(
                text=text,
                message_date=msg_date,
                source=MessageSource.USERBOT,
                telegram_message_id=event.message.id,
                sender_name=sender_name,
            )

        await _client.run_until_disconnected()

    except Exception as e:
        set_userbot_running(False)
        print(f"[Userbot] ❌ Error: {e}")


async def stop_userbot():
    """Gracefully disconnect the userbot."""
    global _client
    if _client:
        set_userbot_running(False)
        await _client.disconnect()
        print("[Userbot] Disconnected")


def get_userbot_client() -> TelegramClient | None:
    return _client


if __name__ == "__main__":
    asyncio.run(start_userbot())
