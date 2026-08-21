"""
api/routes/settings.py — Eligibility profile and app configuration.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from database import app_settings_col

router = APIRouter(prefix="/api/settings", tags=["settings"])


class EligibilityProfile(BaseModel):
    branch: Optional[str] = "CSE"
    batch: Optional[str] = None
    cgpa: Optional[float] = None
    min_ctc_lpa: Optional[float] = None
    preferred_locations: Optional[List[str]] = None
    preferred_roles: Optional[List[str]] = None


@router.get("/profile")
async def get_profile():
    col = app_settings_col()
    doc = await col.find_one({"key": "eligibility_profile"})
    if doc:
        doc.pop("_id", None)
        doc.pop("key", None)
        return doc
    return {}


@router.post("/profile")
async def save_profile(profile: EligibilityProfile):
    col = app_settings_col()
    await col.update_one(
        {"key": "eligibility_profile"},
        {"$set": {"key": "eligibility_profile", **profile.model_dump()}},
        upsert=True,
    )
    return {"ok": True}


@router.get("/system")
async def get_system_status():
    """Get system health status."""
    from services.watchdog import get_last_received, _userbot_running
    last = get_last_received()
    return {
        "userbot_running": _userbot_running,
        "last_message_received": last.isoformat() if last else None,
    }
