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
    set_userbot_error,
)
from services.pdf_service import download_and_extract_pdf
from services.excel_service import (
    is_spreadsheet,
    process_spreadsheet,
    handle_shortlist_report,
)
from services.image_ocr import ocr_image_bytes_with_fallback

IST = pytz.timezone("Asia/Kolkata")

_client: TelegramClient | None = None


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif")
IMAGE_MIMES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp",
    "image/bmp", "image/tiff",
}


def is_image_document(filename: str, mime: str) -> bool:
    """True when a Telegram *document* is actually an image (poster/screenshot)."""
    fname = (filename or "").lower()
    return fname.endswith(IMAGE_EXTS) or (mime or "") in IMAGE_MIMES


def _doc_filename(message) -> str:
    try:
        for attr in message.media.document.attributes:
            fn = getattr(attr, "file_name", None)
            if fn:
                return fn
    except Exception:
        pass
    return ""


async def _route_media(client, message, caption: str = ""):
    """
    Single media router for every attachment type the college sends.
    Returns (pdf_info, excel_report) — at most one is non-None.
      .xlsx/.xls/.csv  -> shortlist scanner (bypasses AI pipeline)
      .pdf/.docx/html  -> text extraction into pipeline
      photo/JPG        -> offline OCR into pipeline
    """
    if not message.media:
        return None, None

    doc = getattr(message.media, "document", None)
    if doc:
        filename = _doc_filename(message)
        mime = getattr(doc, "mime_type", "") or ""
        if is_spreadsheet(filename, mime):
            try:
                data = await client.download_media(message, file=bytes)
                if data:
                    report = await process_spreadsheet(
                        data, filename or "result_sheet.csv", mime, caption
                    )
                    return None, report
            except Exception as e:
                print(f"[Userbot] Spreadsheet handling failed: {e}")
            return None, None
        if is_image_document(filename, mime):
            try:
                data = await client.download_media(message, file=bytes)
                if data:
                    ocr_text = await ocr_image_bytes_with_fallback(data)
                    if ocr_text:
                        return ({
                            "text": ocr_text,
                            "filename": filename or "image_announcement.jpg",
                            "mime_type": mime or "image/jpeg",
                            "size_bytes": len(data),
                            "storage_key": None,
                            "text_extracted": True,
                        }), None
            except Exception as e:
                print(f"[Userbot] Image document OCR failed: {e}")
            return None, None
        return await download_and_extract_pdf(client, message), None

    if getattr(message.media, "photo", None):
        try:
            data = await client.download_media(message, file=bytes)
            if data:
                ocr_text = await ocr_image_bytes_with_fallback(data)
                if ocr_text:
                    return ({
                        "text": ocr_text,
                        "filename": "photo_announcement.jpg",
                        "mime_type": "image/jpeg",
                        "size_bytes": len(data),
                        "storage_key": None,
                        "text_extracted": True,
                    }), None
        except Exception as e:
            print(f"[Userbot] Photo OCR failed: {e}")

    return None, None


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
            
            # Route media: spreadsheet -> shortlist scan, doc -> PDF, photo -> OCR
            pdf_info = None
            excel_report = None
            if message.media:
                pdf_info, excel_report = await _route_media(_client, message)
                
            if excel_report:
                await handle_shortlist_report(excel_report)
                
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
        set_userbot_error("TELEGRAM_API_ID or TELEGRAM_API_HASH is not configured")
        print(
            "[Userbot] No API credentials found — skipping userbot.\n"
            "[Userbot] Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env"
        )
        return

    # ---------------------------------------------------------
    # 2. Check session string
    # ---------------------------------------------------------

    if not settings.telegram_session_string:
        set_userbot_error("TELEGRAM_SESSION_STRING is not configured")
        print(
            "[Userbot] No session string found.\n"
            "[Userbot] Run: python setup_session.py"
        )
        return

    # ---------------------------------------------------------
    # 3. Check placement group ID
    # ---------------------------------------------------------

    if not settings.placement_group_id:
        set_userbot_error("PLACEMENT_GROUP_ID is not configured")
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
        # 5. Connect the existing session without interactive login
        # -----------------------------------------------------

        await _client.connect()
        if not await _client.is_user_authorized():
            raise RuntimeError(
                "TELEGRAM_SESSION_STRING is not authorized. "
                "Generate a fresh StringSession with setup_session.py "
                "and update the Render environment variable."
            )

        set_userbot_running(True)

        print("[Userbot] Telethon session connected.")
        print(
            f"[Userbot] Listening to group ID: "
            f"{settings.placement_group_id}"
        )
        
        # Register the live listener BEFORE the catch-up scan. Previously the
        # scan could take minutes for a busy group, leaving a window in which
        # newly posted messages were never observed.

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
                # Route media: spreadsheet -> shortlist scan,
                # document -> PDF text, photo -> offline OCR
                # ---------------------------------------------

                pdf_info = None
                excel_report = None
                if event.message.media:
                    pdf_info, excel_report = await _route_media(
                        _client, event.message, caption=text
                    )

                if excel_report:
                    await handle_shortlist_report(excel_report)

                if pdf_info:
                    text = f"{text}\n\n--- PDF CONTENT ---\n{pdf_info['text']}".strip()
                    print(f"[Userbot] Successfully extracted {len(pdf_info['text'])} characters from attachment.")

                if not text.strip():
                    print(
                        "[Userbot] Message has no text and no extractable media. Skipping."
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

        # The handler is active now, so historical processing cannot cause new
        # messages to be missed. Hash deduplication safely handles any overlap.
        await _scan_recent_history()

        print("[Userbot] Listener is ACTIVE.")
        print("[Userbot] Waiting for new messages...")

        await _client.run_until_disconnected()
        set_userbot_running(False)
        set_userbot_error("Telegram client disconnected")

    except Exception as error:
        set_userbot_running(False)
        set_userbot_error(f"{type(error).__name__}: {error}")

        print(
            f"[Userbot] FATAL ERROR ({type(error).__name__}): {error}"
        )
        raise


async def run_userbot_forever():
    """Keep the listener alive after transient Telegram/network failures."""
    retry_delay = 15

    if (
        not settings.telegram_api_id
        or not settings.telegram_api_hash
        or not settings.telegram_session_string
        or not settings.placement_group_id
    ):
        await start_userbot()
        return

    while True:
        try:
            await start_userbot()
            print(
                f"[Userbot] Listener stopped unexpectedly; "
                f"retrying in {retry_delay}s."
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(
                f"[Userbot] Listener crashed ({type(error).__name__}): {error}. "
                f"Retrying in {retry_delay}s."
            )
        await asyncio.sleep(retry_delay)


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
