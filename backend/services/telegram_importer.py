"""
services/telegram_importer.py — Historical Telegram export importer.

Supports:
- Telegram JSON export (preferred)
- TXT export
- HTML export (fallback)

Key rules from revised plan:
- Use keyword pre-filter ONLY here (not on live path).
- Process in batches (not one giant Gemini call).
- Timestamp-anchor all date resolution to message's original send time.
- Hash-dedup to avoid reprocessing.
- Never lose messages — store raw, retry failed AI calls.
"""
import json
import re
import asyncio
from datetime import datetime
from typing import AsyncIterator
from bs4 import BeautifulSoup
import pytz

from models.message import MessageSource
from services.pre_filter import passes_pre_filter
from services.message_pipeline import ingest_message

IST = pytz.timezone("Asia/Kolkata")
BATCH_SIZE = 10  # Process N messages at a time to avoid Gemini rate limits
BATCH_DELAY = 1.0  # Seconds between batches


def _parse_telegram_json(content: bytes) -> list[dict]:
    """Parse Telegram JSON export format."""
    data = json.loads(content.decode("utf-8", errors="replace"))
    messages = []

    # Handle both chat export formats
    msg_list = data.get("messages", [])
    if not msg_list and "chats" in data:
        for chat in data["chats"].get("list", []):
            msg_list.extend(chat.get("messages", []))

    for msg in msg_list:
        if msg.get("type") != "message":
            continue

        # Extract text — can be string or list of text entities
        text_parts = msg.get("text", "")
        if isinstance(text_parts, list):
            text = "".join(
                p["text"] if isinstance(p, dict) else p
                for p in text_parts
            )
        else:
            text = str(text_parts)

        if not text.strip():
            continue

        # Parse date — Telegram JSON uses ISO 8601
        date_str = msg.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                dt = IST.localize(dt)
        except Exception:
            dt = datetime.now(IST)

        messages.append({
            "text": text,
            "date": dt,
            "message_id": msg.get("id"),
            "sender": msg.get("from", ""),
        })

    return messages


def _parse_telegram_txt(content: bytes) -> list[dict]:
    """Parse plain text Telegram export (date-prefixed lines)."""
    text = content.decode("utf-8", errors="replace")
    messages = []
    current_date = datetime.now(IST)
    current_lines = []

    date_pattern = re.compile(
        r"\[(\d{1,2}[./]\d{1,2}[./]\d{2,4})[,\s]+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]"
    )

    for line in text.splitlines():
        match = date_pattern.search(line)
        if match:
            if current_lines:
                combined = " ".join(current_lines).strip()
                if combined:
                    messages.append({"text": combined, "date": current_date, "message_id": None, "sender": ""})
            current_lines = [re.sub(r"\[.*?\]", "", line).strip()]
            try:
                date_str = f"{match.group(1)} {match.group(2)}"
                current_date = datetime.strptime(date_str, "%d/%m/%Y %H:%M")
                current_date = IST.localize(current_date)
            except Exception:
                pass
        else:
            current_lines.append(line.strip())

    if current_lines:
        combined = " ".join(current_lines).strip()
        if combined:
            messages.append({"text": combined, "date": current_date, "message_id": None, "sender": ""})

    return messages


def _parse_telegram_html(content: bytes) -> list[dict]:
    """Parse Telegram HTML export format."""
    soup = BeautifulSoup(content, "lxml")
    messages = []

    for msg_div in soup.find_all("div", class_="message"):
        text_div = msg_div.find("div", class_="text")
        date_span = msg_div.find("span", class_="date")

        if not text_div:
            continue

        text = text_div.get_text(separator="\n").strip()
        if not text:
            continue

        dt = datetime.now(IST)
        if date_span and date_span.get("title"):
            try:
                dt = datetime.strptime(date_span["title"], "%d.%m.%Y %H:%M:%S")
                dt = IST.localize(dt)
            except Exception:
                pass

        messages.append({"text": text, "date": dt, "message_id": None, "sender": ""})

    return messages


async def import_telegram_export(
    content: bytes,
    filename: str,
    progress_callback=None,
) -> dict:
    """
    Main import function. Detects format and processes messages.
    progress_callback(stats) called after each batch.

    Returns final stats dict.
    """
    stats = {
        "total": 0,
        "prefiltered": 0,
        "ai_processed": 0,
        "placement": 0,
        "created": 0,
        "updated": 0,
        "duplicates": 0,
        "errors": 0,
    }

    # ── Detect format ──────────────────────────────────────────────────────────
    fn_lower = filename.lower()
    if fn_lower.endswith(".json"):
        messages = _parse_telegram_json(content)
    elif fn_lower.endswith(".html") or fn_lower.endswith(".htm"):
        messages = _parse_telegram_html(content)
    else:  # .txt or unknown
        messages = _parse_telegram_txt(content)

    stats["total"] = len(messages)

    # ── Pre-filter (keyword-based, historical only) ────────────────────────────
    filtered = [m for m in messages if passes_pre_filter(m["text"])]
    stats["prefiltered"] = len(filtered)

    # ── Batch process through AI pipeline ─────────────────────────────────────
    for i in range(0, len(filtered), BATCH_SIZE):
        batch = filtered[i:i + BATCH_SIZE]

        tasks = []
        for msg in batch:
            tasks.append(ingest_message(
                text=msg["text"],
                message_date=msg["date"],
                source=MessageSource.HISTORICAL,
                telegram_message_id=msg.get("message_id"),
                sender_name=msg.get("sender"),
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            stats["ai_processed"] += 1
            if isinstance(r, Exception):
                stats["errors"] += 1
            elif r:
                stats["placement"] += 1
                # Distinguish created vs updated by checking if this is a new doc
                # (simplified — opportunity_engine handles the actual logic)
                stats["created"] += 1

        if progress_callback:
            await progress_callback(stats)

        # Rate limit protection
        await asyncio.sleep(BATCH_DELAY)

    return stats
