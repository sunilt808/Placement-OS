"""
userbot.py — Telethon personal-account listener.

Listens to the configured Telegram placement group in real time
and sends incoming text messages to the ingestion pipeline.
"""

import asyncio
from datetime import datetime
from typing import Optional

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import pytz

from config import settings
from models.message import MessageSource
from services.message_pipeline import ingest_message
from services.watchdog import (
    record_message_received,
    set_userbot_running,
)
from services.pdf_service import download_and_extract_pdf

IST = pytz.timezone("Asia/Kolkata")

_client: TelegramClient | None = None


async def _scan_recent_history(days: Optional[int] = None):
    """Scan recent messages to catch up on missed placement posts."""
    from datetime import timedelta
    
    if not settings.placement_group_id or not _client:
        return
        
    if days is None:
        # Get dynamic catchup_days from DB
        from database import app_settings_col
        col = app_settings_col()
        sys_conf = await col.find_one({"key": "system_config"})
        days = sys_conf.get("catchup_days", settings.catchup_days) if sys_conf else settings.catchup_days
    
    limit_date = datetime.now(IST) - timedelta(days=days)
    
    print(f"[Userbot] Scanning last {days} days of history for missed posts (Newest first)...")
    
    count = 0
    try:
        # iter_messages defaults to newest first
        async for message in _client.iter_messages(settings.placement_group_id):
            message_date = message.date
            if message_date.tzinfo is None:
                message_date = IST.localize(message_date)
                
            if message_date < limit_date:
                break
                
            # Only process if it has text or document
            text = message.message or ""
            
            # Check for PDF
            pdf_info = None
            if message.media and getattr(message.media, "document", None):
                pdf_info = await download_and_extract_pdf(_client, message)
                
            if pdf_info:
                text = f"{text}\n\n--- PDF CONTENT ---\n{pdf_info['text']}".strip()
                
            if not text.strip():
                continue
                
            count += 1
                
            sender_name = ""
            try:
                sender = await message.get_sender()
                if sender:
                    sender_name = getattr(sender, "first_name", "") or ""
            except Exception:
                pass
                
            await ingest_message(
                text=text,
                message_date=message_date,
                source=MessageSource.USERBOT,
                telegram_message_id=message.id,
                sender_name=sender_name,
                pdf_info=pdf_info,
            )
            
            # Sleep slightly to stay well within free tier Gemini rate limits (5 RPM)
            await asyncio.sleep(3.0)
            
    except Exception as e:
        print(f"[Userbot] Error during historical scan: {e}")
        
    print(f"[Userbot] Historical scan complete. Processed {count} messages.")

async def start_userbot():
    """Initialize and start the Telethon userbot listener."""

    global _client

    # ---------------------------------------------------------
    # 1. Check Telegram API credentials
    # ---------------------------------------------------------

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print(
            "[Userbot] No API credentials found — skipping userbot.\n"
            "[Userbot] Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env"
        )
        return

    # ---------------------------------------------------------
    # 2. Check session string
    # ---------------------------------------------------------

    if not settings.telegram_session_string:
        print(
            "[Userbot] No session string found.\n"
            "[Userbot] Run: python setup_session.py"
        )
        return

    # ---------------------------------------------------------
    # 3. Check placement group ID
    # ---------------------------------------------------------

    if not settings.placement_group_id:
        print(
            "[Userbot] ERROR: PLACEMENT_GROUP_ID is not set in .env"
        )
        return

    print(
        f"[Userbot] Target placement group ID: "
        f"{settings.placement_group_id}"
    )

    try:
        # -----------------------------------------------------
        # 4. Create Telegram client
        # -----------------------------------------------------

        _client = TelegramClient(
            StringSession(settings.telegram_session_string),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

        # -----------------------------------------------------
        # 5. Connect existing session
        # -----------------------------------------------------

        await _client.start()

        set_userbot_running(True)

        print("[Userbot] Telethon session connected.")
        print(
            f"[Userbot] Listening to group ID: "
            f"{settings.placement_group_id}"
        )
        
        # -----------------------------------------------------
        # 5.5. Scan history
        # -----------------------------------------------------
        await _scan_recent_history()

        print("[Userbot] Waiting for new Telegram messages...")

        # -----------------------------------------------------
        # 6. Register new-message handler
        # -----------------------------------------------------

        @_client.on(
            events.NewMessage(
                chats=settings.placement_group_id
            )
        )
        async def on_new_message(event):
            """Handle every new message in the placement group."""

            try:
                # ---------------------------------------------
                # Watchdog heartbeat
                # ---------------------------------------------

                record_message_received()

                # ---------------------------------------------
                # Get message text
                # ---------------------------------------------

                text = event.message.message or ""

                # ---------------------------------------------
                # Message information
                # ---------------------------------------------

                message_id = event.message.id
                message_date = event.message.date

                if message_date.tzinfo is None:
                    message_date = IST.localize(message_date)

                # ---------------------------------------------
                # Get sender
                # ---------------------------------------------

                sender_name = ""

                try:
                    sender = await event.get_sender()

                    if sender:
                        sender_name = (
                            getattr(sender, "first_name", "")
                            or ""
                        )

                except Exception as sender_error:
                    print(
                        f"[Userbot] Could not get sender: "
                        f"{sender_error}"
                    )

                # ---------------------------------------------
                # Log EVERY message received
                # ---------------------------------------------

                print("=" * 60)
                print("[Userbot] NEW TELEGRAM MESSAGE RECEIVED")
                print(f"[Userbot] Group ID: {event.chat_id}")
                print(f"[Userbot] Message ID: {message_id}")
                print(f"[Userbot] Sender: {sender_name}")
                print(f"[Userbot] Text: {text[:500]}")
                print("=" * 60)

                # ---------------------------------------------
                # Ignore media-only messages without extractable text
                # ---------------------------------------------

                pdf_info = None
                if event.message.media and getattr(event.message.media, "document", None):
                    print("[Userbot] Document detected, attempting PDF extraction...")
                    pdf_info = await download_and_extract_pdf(_client, event.message)
                    
                if pdf_info:
                    text = f"{text}\n\n--- PDF CONTENT ---\n{pdf_info['text']}".strip()
                    print(f"[Userbot] Successfully extracted {len(pdf_info['text'])} characters from PDF.")

                if not text.strip():
                    print(
                        "[Userbot] Message has no text and no extractable PDF. Skipping."
                    )
                    return

                # ---------------------------------------------
                # Send message to AI ingestion pipeline
                # ---------------------------------------------

                print("[Userbot] Sending message to ingestion pipeline...")

                await ingest_message(
                    text=text,
                    message_date=message_date,
                    source=MessageSource.USERBOT,
                    telegram_message_id=message_id,
                    sender_name=sender_name,
                    pdf_info=pdf_info,
                )

                print(
                    "[Userbot] Message successfully sent "
                    "to ingestion pipeline."
                )

            except Exception as error:
                print(
                    f"[Userbot] ERROR processing message: {error}"
                )

        # -----------------------------------------------------
        # 7. Keep Telegram connection alive
        # -----------------------------------------------------

        print("[Userbot] Listener is ACTIVE.")
        print("[Userbot] Waiting for new messages...")

        await _client.run_until_disconnected()

    except Exception as error:
        set_userbot_running(False)

        print(
            f"[Userbot] FATAL ERROR: {error}"
        )


async def stop_userbot():
    """Gracefully disconnect the userbot."""

    global _client

    if _client:
        set_userbot_running(False)

        await _client.disconnect()

        print("[Userbot] Disconnected")


def get_userbot_client() -> TelegramClient | None:
    """Return the active Telethon client."""

    return _client


async def trigger_manual_history_scan(days: int):
    """Trigger a manual background history scan for the last X days."""
    asyncio.create_task(_scan_recent_history(days=days))


if __name__ == "__main__":
    asyncio.run(start_userbot())