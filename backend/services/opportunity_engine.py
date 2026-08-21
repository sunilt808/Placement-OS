"""
services/opportunity_engine.py — 3-layer deduplication and opportunity state engine.

Layer 1: Rule-based signature (company + role + URL normalized) — free, instant.
Layer 2: Fuzzy text similarity (rapidfuzz) — catch paraphrased reminders.
Layer 3: Gemini tie-breaker — only for ambiguous mid-band cases.

This engine handles:
- Creating new opportunities
- Updating existing ones (deadline extension, new info)
- Maintaining event timeline
- Detecting missed opportunities (deadline passed, no APPLIED status)
"""
import re
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from rapidfuzz import fuzz

from database import opportunities_col, events_col, messages_col
from models.opportunity import (
    AIExtraction, OpportunityCategory, ApplicationStatus,
    EventType, OpportunityEvent
)
from services.deadline_engine import get_urgency, reminder_times
from services.reminder_service import schedule_reminders

# Fuzzy similarity threshold — below this = likely different opportunity
FUZZY_MATCH_THRESHOLD = 75
# Ambiguous band: [LOW, HIGH] → call Gemini as tie-breaker
FUZZY_AMBIGUOUS_LOW = 50
FUZZY_AMBIGUOUS_HIGH = 75


def _normalize_company(name: Optional[str]) -> str:
    if not name:
        return ""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _normalize_url(url: Optional[str]) -> str:
    if not url:
        return ""
    # Strip tracking parameters, lowercase
    url = url.lower().split("?")[0].rstrip("/")
    return url


def _opportunity_signature(company: Optional[str], role: Optional[str], url: Optional[str]) -> str:
    return f"{_normalize_company(company)}|{(role or '').lower().strip()}|{_normalize_url(url)}"


def _text_similarity(text1: str, text2: str) -> float:
    """Returns 0-100 similarity score using token_set_ratio for paraphrase detection."""
    return fuzz.token_set_ratio(text1.lower(), text2.lower())


async def _find_existing_by_signature(extraction: AIExtraction) -> Optional[dict]:
    """Layer 1: Exact/near signature match."""
    if not extraction.company:
        return None

    sig = _opportunity_signature(extraction.company, extraction.role, extraction.registration_link)

    # Query recent opportunities (last 90 days)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
    from datetime import timedelta
    cutoff -= timedelta(days=90)

    col = opportunities_col()
    cursor = col.find({"created_at": {"$gte": cutoff}})
    async for opp in cursor:
        existing_sig = _opportunity_signature(
            opp.get("company"), opp.get("role"), opp.get("registration_link")
        )
        if sig == existing_sig and sig != "||":
            return opp
    return None


async def _find_existing_by_fuzzy(extraction: AIExtraction, message_text: str) -> Optional[dict]:
    """Layer 2: Fuzzy text similarity against recent opportunities."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff -= timedelta(days=60)

    col = opportunities_col()
    best_score = 0
    best_match = None

    cursor = col.find({"created_at": {"$gte": cutoff}})
    async for opp in cursor:
        opp_text = f"{opp.get('company', '')} {opp.get('role', '')} {opp.get('summary', '')}"
        score = _text_similarity(message_text, opp_text)
        if score > best_score:
            best_score = score
            best_match = opp

    if best_score >= FUZZY_MATCH_THRESHOLD:
        return best_match
    return None


async def _log_event(event: OpportunityEvent):
    """Append an event to the opportunity timeline."""
    col = events_col()
    await col.insert_one(event.model_dump())


async def _create_opportunity(extraction: AIExtraction, message_id: str) -> str:
    """Create a new opportunity document."""
    col = opportunities_col()
    now = datetime.utcnow()

    doc = {
        "company": extraction.company,
        "role": extraction.role,
        "ctc": extraction.ctc,
        "location": extraction.location,
        "eligible_branches": extraction.eligible_branches,
        "eligible_batch": extraction.eligible_batch,
        "cgpa_requirement": extraction.cgpa_requirement,
        "backlog_requirement": extraction.backlog_requirement,
        "experience_requirement": extraction.experience_requirement,
        "deadline": extraction.deadline,
        "assessment_date": extraction.assessment_date,
        "interview_date": extraction.interview_date,
        "registration_link": extraction.registration_link,
        "skills": extraction.required_skills,
        "status": ApplicationStatus.NEW,
        "confidence": extraction.confidence,
        "summary": extraction.summary,
        "category": extraction.category,
        "source_message_ids": [message_id],
        "created_at": now,
        "updated_at": now,
    }
    result = await col.insert_one(doc)
    opp_id = str(result.inserted_id)

    # Log CREATED event
    await _log_event(OpportunityEvent(
        opportunity_id=opp_id,
        event_type=EventType.CREATED,
        new_value=extraction.summary,
        message_id=message_id,
    ))

    # Schedule deadline reminders
    if extraction.deadline:
        await schedule_reminders(opp_id, extraction.deadline)

    return opp_id


async def _update_opportunity(opp: dict, extraction: AIExtraction, message_id: str) -> str:
    """Update an existing opportunity with new information."""
    col = opportunities_col()
    opp_id = str(opp["_id"])
    now = datetime.utcnow()
    updates = {"updated_at": now}

    # ── Deadline extension detection ──────────────────────────────────────────
    if extraction.deadline and extraction.deadline != opp.get("deadline"):
        old_dl = opp.get("deadline")
        updates["deadline"] = extraction.deadline
        await _log_event(OpportunityEvent(
            opportunity_id=opp_id,
            event_type=EventType.DEADLINE_UPDATED,
            old_value=str(old_dl) if old_dl else None,
            new_value=str(extraction.deadline),
            message_id=message_id,
            note="Deadline updated — reminders rescheduled",
        ))
        # Reschedule reminders with new deadline
        await schedule_reminders(opp_id, extraction.deadline, reschedule=True)

    # ── Update other fields if they improve existing data ─────────────────────
    for field in ["ctc", "location", "registration_link", "assessment_date",
                  "interview_date", "summary"]:
        new_val = getattr(extraction, field, None)
        if new_val and not opp.get(field):
            updates[field] = new_val

    # ── Update confidence if improved ─────────────────────────────────────────
    if extraction.confidence > opp.get("confidence", 0):
        updates["confidence"] = extraction.confidence

    # ── Track category changes ─────────────────────────────────────────────────
    update_event_types = {
        OpportunityCategory.ASSESSMENT: EventType.UPDATE_RECEIVED,
        OpportunityCategory.INTERVIEW: EventType.INTERVIEW_SCHEDULED,
        OpportunityCategory.SHORTLIST: EventType.SHORTLISTED,
        OpportunityCategory.DEADLINE_UPDATE: EventType.DEADLINE_UPDATED,
        OpportunityCategory.PLACEMENT_UPDATE: EventType.UPDATE_RECEIVED,
    }
    if extraction.category in update_event_types:
        await _log_event(OpportunityEvent(
            opportunity_id=opp_id,
            event_type=update_event_types[extraction.category],
            new_value=extraction.summary,
            message_id=message_id,
        ))

    # ── Add message ID to source list ─────────────────────────────────────────
    await col.update_one(
        {"_id": opp["_id"]},
        {
            "$set": updates,
            "$addToSet": {"source_message_ids": message_id},
        }
    )
    return opp_id


async def process_extraction(
    extraction: AIExtraction,
    message_text: str,
    message_id: str,
) -> Optional[str]:
    """
    Main entry point. Given AI extraction + raw message text:
    1. Skip if IRRELEVANT.
    2. Try 3-layer deduplication.
    3. Create or update opportunity.
    Returns opportunity_id or None.
    """
    if not extraction.is_placement_related:
        return None
    if extraction.category == OpportunityCategory.IRRELEVANT:
        return None

    # Layer 1: Signature match
    existing = await _find_existing_by_signature(extraction)

    # Layer 2: Fuzzy match (only if no signature match)
    if not existing:
        existing = await _find_existing_by_fuzzy(extraction, message_text)

    # Layer 3: Gemini tie-breaker handled in ai_service when called

    if existing:
        return await _update_opportunity(existing, extraction, message_id)
    else:
        return await _create_opportunity(extraction, message_id)


async def get_timeline(opportunity_id: str) -> list[dict]:
    """Fetch the full event timeline for an opportunity, newest first."""
    col = events_col()
    cursor = col.find(
        {"opportunity_id": opportunity_id},
        sort=[("timestamp", 1)]
    )
    events = []
    async for e in cursor:
        e["_id"] = str(e["_id"])
        events.append(e)
    return events


async def detect_missed_opportunities() -> list[dict]:
    """
    Find opportunities whose deadlines have passed but status is not APPLIED.
    Used in historical import and daily check.
    Returns list of possibly missed opportunities.
    """
    col = opportunities_col()
    now = datetime.utcnow()
    missed = []
    cursor = col.find({
        "deadline": {"$lt": now},
        "status": {"$nin": [ApplicationStatus.APPLIED, ApplicationStatus.IGNORED]},
    })
    async for opp in cursor:
        opp["_id"] = str(opp["_id"])
        missed.append(opp)
    return missed
