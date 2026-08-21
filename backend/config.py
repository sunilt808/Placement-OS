"""
config.py — Application settings loaded from .env
All secrets stay in environment variables; never hardcode.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telegram Bot API ──────────────────────────────────────────────────────
    # Integrations are optional. The dashboard, importer and local extractor
    # must remain usable without Telegram or Gemini credentials.
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""              # Student's personal Telegram user ID

    # ── Telethon Userbot ──────────────────────────────────────────────────────
    telegram_api_id: Optional[int] = None
    telegram_api_hash: Optional[str] = None
    telegram_session_string: Optional[str] = None
    placement_group_id: Optional[int] = None   # Group/channel to monitor

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_enabled: bool = False

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "placement_monitor"

    # ── App ───────────────────────────────────────────────────────────────────
    timezone: str = "Asia/Kolkata"
    watchdog_interval_minutes: int = 30
    daily_summary_hour: int = 8
    catchup_days: int = 10
    message_retention_days: int = 3

    # ── Gemini model names ────────────────────────────────────────────────────
    gemini_flash_model: str = "gemini-3.6-flash"
    gemini_pro_model: str = "gemini-3.1-pro-preview"

    # Confidence threshold below which we escalate to the pro model
    confidence_threshold: float = 0.70

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
