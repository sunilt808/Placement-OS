"""
services/message_pipeline.py — Core message ingestion pipeline.

Used by BOTH the Telethon userbot AND the Bot API forwarding bot.
Both paths feed the same pipeline; downstream code doesn't know the source.

Pipeline:
  raw message
    → content hash check (dedup)
    → save raw message to DB
    → AI extraction (flash → pro if needed)
    → opportunity engine (3-layer dedup)
    → Telegram alert
"""
import hashlib
from datetime import datetime
from typing import Optional

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
) -> Optional[str]:
    """
    Full ingestion pipeline for a single message.
    Returns opportunity_id if one was created/updated, else None.
    """
    if not text or not text.strip():
        return None

    content_hash = _content_hash(text)
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

        await col.update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "category": extraction.category,
                "is_placement_related": extraction.is_placement_related,
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
            opp = await opportunities_col().find_one_and_update(
                {"_id": __import__('bson').ObjectId(opportunity_id)},
                {"$set": {}},  # no-op update to retrieve doc
            )
            if not opp:
                from bson import ObjectId
                opp = await opportunities_col().find_one({"_id": ObjectId(opportunity_id)})

            if opp:
                if extraction.category == OpportunityCategory.NEEDS_REVIEW:
                    await send_needs_review_alert(opp, opportunity_id, text)
                else:
                    await send_new_opportunity_alert(opp, opportunity_id)

        return opportunity_id

    except Exception as e:
        print(f"[Pipeline] Error processing message {message_id}: {e}")
        await col.update_one(
            {"_id": result.inserted_id},
            {"$set": {"processing_error": str(e)}}
        )
        # Never lose the message — it's safely stored, can be retried
        return None
