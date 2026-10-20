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
    expiry_grace_hours: int = 12      # Janitor: deadline passed this long -> EXPIRED

    # ── Auto-notifications ────────────────────────────────────────────────────
    auto_notify_new_opportunity: bool = True   # Telegram ping on every NEW drive
    startup_ping: bool = True                  # delivery self-test on boot

    # ── Cloud-storage guardian (Atlas M0 free tier ~512 MB) ───────────────────
    data_retention_days: int = 25     # auto-delete messages/opps older than this
    storage_limit_mb: int = 512       # provider quota
    storage_warn_mb: int = 450        # Telegram warning threshold

    # ── Student identity (hardcoded shortlist matching) ───────────────────────
    student_name: str = "Sunil T"
    student_usn: str = "1DS24CS421"

    # ── Gemini model names ────────────────────────────────────────────────────
    gemini_flash_model: str = "gemini-3.8-flash"
    gemini_pro_model: str = "gemini-3.1-pro-preview"

    # Confidence threshold below which we escalate to the pro model
    confidence_threshold: float = 0.70

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Admin auth (dashboard login) ──────────────────────────────────────────
    # MUST come from .env / environment. Empty values disable login (fail-closed).
    admin_username: str = ""
    admin_password: str = ""
    admin_security_code: str = ""
    jwt_secret: str = ""

    # ── API surface ───────────────────────────────────────────────────────────
    # Swagger UI / ReDoc / openapi.json are hidden unless explicitly enabled.
    docs_enabled: bool = False


settings = Settings()
