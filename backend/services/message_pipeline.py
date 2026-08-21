"""
services/message_pipeline.py — Core message ingestion pipeline.

Used by BOTH the Telethon userbot AND the Bot API forwarding bot.
Both paths feed the same pipeline; downstream code doesn't know the source.

Pipeline:
  raw message
    → content hash check (dedup)
    → save raw message to DB
    → AI extraction (local first, Gemini enhancement optional)
    → opportunity engine (3-layer dedup)
    → Telegram alert
"""
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

from database import messages_col, opportunities_col
from models.message import MessageIn, MessageSource
from models.opportunity import OpportunityCategory
from services.ai_service import classify_and_extract
from services.opportunity_engine import process_extraction
from services.notification_service import (
    send_new_opportunity_alert,
    send_needs_review_alert,
)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def ingest_message(
    text: str,
    message_date: datetime,
    source: MessageSource,
    telegram_message_id: Optional[int] = None,
    sender_name: Optional[str] = None,
    pdf_info: Optional[Dict[str, Any]] = None,  # NEW: {filename, mime_type, size_bytes}
) -> Optional[str]:
    """
    Full ingestion pipeline for a single message.

    Args:
        text: Combined message text (caption + extracted PDF/doc text).
        message_date: ORIGINAL Telegram send timestamp — used as temporal anchor.
        source: MessageSource enum (USERBOT / BOT / IMPORT).
        telegram_message_id: Telegram message ID for reference.
        sender_name: Sender display name.
        pdf_info: Dict with filename/mime info if a document was attached.

    Returns:
        opportunity_id if one was created/updated, else None.
    """
    if not text or not text.strip():
        return None

    # Include the attachment key so different PDF-only messages do not share a
    # hash merely because their extracted text is empty.
    content_hash = _content_hash(f"{text}\n{pdf_info.get('storage_key', '')}" if pdf_info else text)
    col = messages_col()

    # ── 1. Content hash dedup — never process identical messages twice ─────────
    existing_msg = await col.find_one({"content_hash": content_hash})
    if existing_msg:
        print(f"[Pipeline] Duplicate message detected (hash={content_hash[:8]}...), skipping")
        return existing_msg.get("opportunity_id")

    # ── 2. Save raw message ────────────────────────────────────────────────────
    msg_doc = {
        "telegram_message_id": telegram_message_id,
        "message_text": text,
        "message_date": message_date.replace(tzinfo=None) if message_date.tzinfo else message_date,
        "source": source,
        "sender_name": sender_name,
        "content_hash": content_hash,
        "processed_at": None,
        "opportunity_id": None,
        "processing_error": None,
        # Store attachment info on the raw message
        "attachment_filename": pdf_info.get("filename") if pdf_info else None,
        "attachment_mime_type": pdf_info.get("mime_type") if pdf_info else None,
        "attachment_storage_key": pdf_info.get("storage_key") if pdf_info else None,
        "attachment_text_extracted": pdf_info.get("text_extracted") if pdf_info else None,
    }
    result = await col.insert_one(msg_doc)
    message_id = str(result.inserted_id)

    # ── 3. AI extraction ───────────────────────────────────────────────────────
    try:
        extraction, _ = await classify_and_extract(
            text=text,
            message_date=message_date,
            cached_hash=content_hash,
        )

        if pdf_info and pdf_info.get("filename"):
            extraction.source_document = pdf_info["filename"]
            extraction.source_document_key = pdf_info.get("storage_key")

        # Always preserve the original Telegram message timestamp
        extraction.telegram_message_date = message_date

        await col.update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "category": extraction.category,
                "is_placement_related": extraction.is_placement_related,
                "cse_relevance_score": extraction.cse_relevance_score,
                "processed_at": datetime.utcnow(),
            }}
        )

        # ── 4. Opportunity engine ──────────────────────────────────────────────
        opportunity_id = await process_extraction(
            extraction=extraction,
            message_text=text,
            message_id=message_id,
        )

        if opportunity_id:
            await col.update_one(
                {"_id": result.inserted_id},
                {"$set": {"opportunity_id": opportunity_id}}
            )

            # ── 5. Send Telegram alert ─────────────────────────────────────────
            from bson import ObjectId
            opp = await opportunities_col().find_one({"_id": ObjectId(opportunity_id)})

            if opp:
                try:
                    if extraction.category == OpportunityCategory.NEEDS_REVIEW:
                        await send_needs_review_alert(opp, opportunity_id, text)
                    else:
                        await send_new_opportunity_alert(opp, opportunity_id)
                except Exception as alert_err:
                    print(f"[Pipeline] Could not send Telegram bot alert: {alert_err}")

        return opportunity_id

    except Exception as e:
        print(f"[Pipeline] Error processing message {message_id}: {e}")
        await col.update_one(
            {"_id": result.inserted_id},
            {"$set": {"processing_error": str(e)}}
        )
        # Never lose the message — it's safely stored, can be retried
        return None
