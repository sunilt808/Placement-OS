"""
api/routes/gemini.py — Optional AI chat over your placement data.

Fully opt-in: works only when a Gemini key exists AND the user toggled it
on from the Gemini page. Answers are grounded in a compact snapshot of the
opportunities currently stored in MongoDB.
"""
import asyncio
from datetime import datetime

import fastapi
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.routes.auth import require_auth
from config import settings
from database import app_settings_col, opportunities_col

router = APIRouter(prefix="/api/gemini", tags=["gemini"],
                   dependencies=[Depends(require_auth)])

_SETTINGS_KEY = "gemini_chat"


class ChatRequest(BaseModel):
    question: str


class ToggleRequest(BaseModel):
    enabled: bool


async def _chat_enabled() -> bool:
    doc = await app_settings_col().find_one({"key": _SETTINGS_KEY})
    return bool(doc and doc.get("enabled"))


@router.get("/status")
async def status():
    return {
        "enabled": await _chat_enabled(),
        "configured": bool(settings.gemini_api_key),
    }


@router.post("/toggle")
async def toggle(body: ToggleRequest):
    if body.enabled and not settings.gemini_api_key:
        raise HTTPException(400,
                            "No GEMINI_API_KEY configured. Add it to .env first.")
    await app_settings_col().update_one(
        {"key": _SETTINGS_KEY},
        {"$set": {"key": _SETTINGS_KEY, "enabled": body.enabled}},
        upsert=True,
    )
    return {"ok": True, "enabled": body.enabled}


@router.post("/chat")
async def chat(body: ChatRequest):
    if not settings.gemini_api_key:
        raise HTTPException(400, "Gemini is not configured (no API key).")
    if not await _chat_enabled():
        raise HTTPException(400, "Gemini is disabled. Enable it on this page first.")

    q = (body.question or "").strip()
    if not q:
        raise HTTPException(400, "Question required")

    col = opportunities_col()
    docs = await col.find({}, {
        "_id": 0, "company": 1, "role": 1, "deadline": 1, "status": 1,
        "category": 1, "eligibility_status": 1, "registration_link": 1,
        "has_registration_form": 1, "updated_at": 1,
    }).sort("updated_at", -1).limit(30).to_list(length=30)

    rows = []
    for d in docs:
        dl = d.get("deadline")
        rows.append(
            f"- {d.get('company') or '?'} | role: {d.get('role') or '?'} | "
            f"deadline: {dl.strftime('%d %b %Y') if dl else 'none'} | "
            f"status: {d.get('status') or 'unknown'} | "
            f"form: {'yes' if d.get('has_registration_form') else 'no'}"
        )
    context = (
        f"Today is {datetime.utcnow():%d %b %Y}.\n"
        f"The user has these placement drives tracked:\n" +
        ("\n".join(rows) if rows else "(no drives stored yet)")
    )

    prompt = (
        "You are PlacementOS Assistant, a concise helper for ONE CSE student "
        "tracking placements. Answer ONLY from the data below; if something "
        "isn't in the data, say you don't know. Keep answers under 120 words.\n\n"
        f"{context}\n\nQuestion: {q}"
    )

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_flash_model)

        def _call():
            return model.generate_content(prompt).text

        answer = await asyncio.to_thread(_call)
    except ImportError:
        raise HTTPException(500, "google-generativeai package not installed")
    except Exception as e:
        msg = str(e)
        code = getattr(e, "code", None) or getattr(
            getattr(e, "response", None), "status_code", None)
        if code == 429 or "429" in msg or "RESOURCE_EXHAUSTED" in msg \
                or "quota" in msg.lower():
            raise HTTPException(
                429, "Gemini credits are used up for now. "
                     "Please try again later.")
        raise HTTPException(502, f"Gemini call failed: {e}")

    return {"answer": (answer or "").strip(),
            "grounded_on": len(docs), "enabled": True}
