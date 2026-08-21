"""
models/message.py — Pydantic models for raw ingested messages.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class MessageSource(str, Enum):
    USERBOT = "USERBOT"           # Telethon live listener
    BOT_FORWARD = "BOT_FORWARD"  # Manual forward via Bot API
    HISTORICAL = "HISTORICAL"     # Telegram JSON/HTML/TXT import


class MessageIn(BaseModel):
    """Message coming into the pipeline."""
    text: str
    message_date: datetime           # ORIGINAL send time, not processing time
    source: MessageSource
    telegram_message_id: Optional[int] = None
    sender_name: Optional[str] = None
    media_type: Optional[str] = None  # "photo", "document", etc.


class MessageOut(MessageIn):
    id: str = Field(alias="_id")
    content_hash: str
    category: Optional[str] = None
    is_placement_related: Optional[bool] = None
    processed_at: Optional[datetime] = None
    opportunity_id: Optional[str] = None
    processing_error: Optional[str] = None

    class Config:
        populate_by_name = True


class ReminderType(str, Enum):
    THREE_DAYS = "THREE_DAYS"
    TWENTY_FOUR_HOURS = "TWENTY_FOUR_HOURS"
    THREE_HOURS = "THREE_HOURS"
    DAILY_SUMMARY = "DAILY_SUMMARY"
    CUSTOM = "CUSTOM"
