"""
api/routes/opportunities.py — CRUD routes for opportunities.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional, List
from bson import ObjectId
from datetime import datetime, timedelta, timezone

from database import opportunities_col, events_col, messages_col
from models.opportunity import ApplicationStatus, OpportunityUpdate
from services.deadline_engine import get_urgency
from services.reminder_service import cancel_all_reminders, schedule_reminders
from services.opportunity_engine import get_timeline
from config import settings
from api.routes.auth import require_auth

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"],
                   dependencies=[Depends(require_auth)])


def _serialize(doc: dict) -> dict:
    """Convert MongoDB doc to JSON-serializable dict."""
    doc["_id"] = str(doc["_id"])
    for field in ["deadline", "assessment_date", "interview_date", "created_at", "updated_at"]:
        if field in doc and doc[field]:
            doc[field] = doc[field].isoformat() if isinstance(doc[field], datetime) else doc[field]
    doc["deadline_urgency"] = get_urgency(doc.get("deadline_raw") or
                                           datetime.fromisoformat(doc["deadline"]) if isinstance(doc.get("deadline"), str) else doc.get("deadline"))
    return doc


def _opp_urgency(opp: dict) -> str:
    deadline = opp.get("deadline")
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline)
        except Exception:
            deadline = None
    return get_urgency(deadline)


@router.get("")
async def list_opportunities(
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    eligibility: Optional[str] = None,
    role_class: Optional[str] = None,      # CSE_BOTH|CSE_ROLE|CSE_BRANCH|NOT_CSE|UNKNOWN
    forms_only: bool = False,              # only drives with Google Form registration
    days: Optional[int] = None,
    cse_only: bool = False,
    limit: int = Query(50, le=200),
    skip: int = 0,
):
    """List opportunities with filters."""
    col = opportunities_col()
    query = {}

    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if eligibility:
        query["eligibility_status"] = eligibility
    if role_class:
        query["role_class"] = role_class
    if forms_only:
        query["has_registration_form"] = True
    if search:
        query["$or"] = [
            {"company": {"$regex": search, "$options": "i"}},
            {"role": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
        ]
    
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        # If there's an existing $or from search, we must use $and to combine them
        days_query = {
            "$or": [
                {"telegram_message_date": {"$gte": cutoff}},
                {"created_at": {"$gte": cutoff}},
                {"updated_at": {"$gte": cutoff}}
            ]
        }
        if "$or" in query:
            query = {"$and": [{"$or": query["$or"]}, days_query]}
        else:
            query.update(days_query)

    if cse_only:
        query["is_cse_relevant"] = True

    # Urgency is a computed field (not stored), so we must evaluate it over the
    # full matched set BEFORE paginating to keep pages and totals consistent.
    cursor = col.find(query, sort=[("created_at", -1)])
    results = []
    async for opp in cursor:
        opp["_id"] = str(opp["_id"])
        for f in ["deadline", "assessment_date", "interview_date", "created_at", "updated_at", "telegram_message_date"]:
            if opp.get(f) and isinstance(opp[f], datetime):
                opp[f] = opp[f].isoformat()
        opp["deadline_urgency"] = _opp_urgency(opp)
        results.append(opp)

    if urgency:
        results = [o for o in results if o.get("deadline_urgency") == urgency]

    total = len(results)
    results = results[skip:skip + limit]
    return {"opportunities": results, "total": total, "skip": skip, "limit": limit}


@router.get("/stats")
async def get_stats():
    """Dashboard summary stats."""
    col = opportunities_col()
    from services.deadline_engine import DeadlineUrgency

    stats = {
        "total": await col.count_documents({}),
        "active": await col.count_documents({"status": {"$nin": ["IGNORED", "EXPIRED"]}}),
        "applied": await col.count_documents({"status": "APPLIED"}),
        "not_applied": await col.count_documents({"status": {"$in": ["NEW", "VIEWED", "NOT_APPLIED"]}}),
        "deadline_today": 0,
        "deadline_tomorrow": 0,
        "within_3_days": 0,
        "this_week": 0,
        "upcoming": 0,
        "expired": 0,
        "no_deadline": 0,
    }

    async for opp in col.find({"status": {"$nin": ["APPLIED", "IGNORED"]}}):
        urgency = _opp_urgency(opp)
        if urgency in ("TODAY", "WITHIN_24H"):
            stats["deadline_today"] += 1
        elif urgency == "TOMORROW":
            stats["deadline_tomorrow"] += 1
        elif urgency == "WITHIN_3_DAYS":
            stats["within_3_days"] += 1
        elif urgency == "THIS_WEEK":
            stats["this_week"] += 1
        elif urgency == "UPCOMING":
            stats["upcoming"] += 1
        elif urgency == "EXPIRED":
            stats["expired"] += 1
        else:
            stats["no_deadline"] += 1

    return stats


@router.get("/messages")
async def list_ingested_messages(
    search: Optional[str] = None,
    category: Optional[str] = None,
    placement_only: bool = False,
    has_error: bool = False,
    limit: int = Query(100, le=200),
    skip: int = 0,
):
    """Inspect raw Telegram/import messages and the result of their extraction."""
    query = {
        "message_date": {
            "$gte": datetime.utcnow() - timedelta(days=settings.message_retention_days)
        }
    }
    if category:
        query["category"] = category
    if placement_only:
        query["is_placement_related"] = True
    if has_error:
        query["processing_error"] = {"$nin": [None, ""]}
    if search:
        query["message_text"] = {"$regex": search, "$options": "i"}

    results = []
    cursor = messages_col().find(
        query, sort=[("message_date", -1), ("_id", -1)], skip=skip, limit=limit
    )
    async for message in cursor:
        message["_id"] = str(message["_id"])
        for field in ("message_date", "processed_at"):
            if isinstance(message.get(field), datetime):
                value = message[field]
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                message[field] = value.isoformat()
        source = message.get("source")
        message["source"] = source.value if hasattr(source, "value") else source
        message["attachment_available"] = bool(message.get("attachment_storage_key"))
        results.append(message)

    opportunity_ids = []
    for message in results:
        try:
            if message.get("opportunity_id"):
                opportunity_ids.append(ObjectId(message["opportunity_id"]))
        except Exception:
            continue
    extracted_by_id = {}
    if opportunity_ids:
        async for opp in opportunities_col().find({"_id": {"$in": opportunity_ids}}):
            deadline = opp.get("deadline")
            extracted_by_id[str(opp["_id"])] = {
                "company": opp.get("company"),
                "role": opp.get("role"),
                "ctc": opp.get("ctc"),
                "deadline": deadline.isoformat() if isinstance(deadline, datetime) else deadline,
                "status": opp.get("status"),
                "summary": opp.get("summary"),
                "confidence": opp.get("confidence"),
                "source_document": opp.get("source_document"),
                "source_document_available": bool(opp.get("source_document_key")),
            }
    for message in results:
        message["extraction"] = extracted_by_id.get(message.get("opportunity_id"))

    return {
        "messages": results,
        "total": await messages_col().count_documents(query),
        "skip": skip,
        "limit": limit,
    }


@router.get("/messages/{message_id}/attachment")
async def get_message_attachment(message_id: str):
    """Download a retained source attachment from the short-lived message inbox."""
    try:
        message = await messages_col().find_one({"_id": ObjectId(message_id)})
    except Exception:
        raise HTTPException(404, "Message not found")
    from services.pdf_service import stored_document_path
    path = stored_document_path(message.get("attachment_storage_key", "")) if message else None
    if not path:
        raise HTTPException(404, "Attachment not available")
    return FileResponse(path, filename=message.get("attachment_filename") or path.name,
                        media_type=message.get("attachment_mime_type") or "application/octet-stream")


@router.get("/{opp_id}/source-document")
async def get_opportunity_source_document(opp_id: str):
    """Download the retained source document for an opportunity."""
    try:
        opp = await opportunities_col().find_one({"_id": ObjectId(opp_id)})
    except Exception:
        raise HTTPException(404, "Opportunity not found")
    from services.pdf_service import stored_document_path
    path = stored_document_path(opp.get("source_document_key", "")) if opp else None
    if not path:
        raise HTTPException(404, "Source document not available")
    return FileResponse(path, filename=opp.get("source_document") or path.name,
                        media_type="application/octet-stream")


@router.get("/{opp_id}")
async def get_opportunity(opp_id: str):
    """Get single opportunity with full timeline."""
    col = opportunities_col()
    try:
        opp = await col.find_one({"_id": ObjectId(opp_id)})
    except Exception:
        raise HTTPException(404, "Invalid opportunity ID")
    if not opp:
        raise HTTPException(404, "Opportunity not found")

    opp["_id"] = str(opp["_id"])
    for f in ["deadline", "assessment_date", "interview_date", "created_at", "updated_at", "telegram_message_date"]:
        if opp.get(f) and isinstance(opp[f], datetime):
            opp[f] = opp[f].isoformat()
    opp["deadline_urgency"] = _opp_urgency(opp)
    opp["timeline"] = await get_timeline(opp_id)

    return opp


@router.patch("/{opp_id}/status")
async def update_status(opp_id: str, body: dict):
    """Update opportunity status (APPLIED, IGNORED, NOT_APPLIED, etc.)."""
    col = opportunities_col()
    new_status = body.get("status")
    if not new_status:
        raise HTTPException(400, "status required")

    try:
        obj_id = ObjectId(opp_id)
    except Exception:
        raise HTTPException(400, "Invalid ID")

    opp = await col.find_one({"_id": obj_id})
    if not opp:
        raise HTTPException(404, "Not found")

    await col.update_one(
        {"_id": obj_id},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )

    if new_status == "APPLIED":
        await cancel_all_reminders(opp_id)

    return {"ok": True, "status": new_status}


@router.get("/{opp_id}/timeline")
async def get_opp_timeline(opp_id: str):
    """Get opportunity event timeline."""
    timeline = await get_timeline(opp_id)
    return {"timeline": timeline}


@router.delete("/{opp_id}")
async def delete_opportunity(opp_id: str):
    """Delete an opportunity (admin action)."""
    col = opportunities_col()
    try:
        result = await col.delete_one({"_id": ObjectId(opp_id)})
    except Exception:
        raise HTTPException(400, "Invalid ID")
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    await cancel_all_reminders(opp_id)
    return {"ok": True}


@router.get("/meta/calendar")
async def get_calendar():
    col = opportunities_col()
    events = []
    async for opp in col.find({"status": {"$nin": ["IGNORED"]}}):
        company = opp.get("company", "Unknown")
        opp_id = str(opp["_id"])
        for field, label, color in [
            ("deadline", "Deadline", "red"),
            ("assessment_date", "Assessment", "orange"),
            ("interview_date", "Interview", "green"),
        ]:
            val = opp.get(field)
            if val:
                if isinstance(val, datetime):
                    date_str = val.date().isoformat()
                else:
                    try:
                        date_str = datetime.fromisoformat(str(val)).date().isoformat()
                    except Exception:
                        continue
                events.append({
                    "date": date_str,
                    "type": label,
                    "color": color,
                    "company": company,
                    "role": opp.get("role"),
                    "opp_id": opp_id,
                    "status": opp.get("status"),
                })
    return {"events": events}

@router.get("/meta/briefing")
async def get_briefing():
    col = opportunities_col()
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    now = datetime.now(IST)
    hour = now.hour

    greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")

    total_active = await col.count_documents({"status": {"$nin": ["APPLIED", "IGNORED"]}})
    applied = await col.count_documents({"status": "APPLIED"})

    yesterday = datetime.utcnow() - timedelta(hours=24)
    new_since_yesterday = await col.count_documents({
        "created_at": {"$gte": yesterday},
        "status": {"$nin": ["IGNORED"]}
    })

    urgent = []
    async for opp in col.find({"status": {"$nin": ["APPLIED", "IGNORED"]}, "deadline": {"$ne": None}}):
        u = _opp_urgency(opp)
        if u in ("TODAY", "WITHIN_24H", "TOMORROW"):
            urgent.append({
                "company": opp.get("company", "Unknown"),
                "role": opp.get("role"),
                "urgency": u,
                "deadline": opp["deadline"].isoformat() if isinstance(opp.get("deadline"), datetime) else opp.get("deadline"),
                "opp_id": str(opp["_id"]),
            })

    parts = []
    if new_since_yesterday:
        parts.append(f"📬 {new_since_yesterday} new drive{'s' if new_since_yesterday > 1 else ''} since yesterday")
    if urgent:
        parts.append(f"⚡ {len(urgent)} urgent deadline{'s' if len(urgent) > 1 else ''} approaching")
    if total_active:
        parts.append(f"📋 {total_active} pending")
    if applied:
        parts.append(f"✅ {applied} applied")

    return {
        "greeting": greeting,
        "message": " · ".join(parts) if parts else "All caught up! Keep checking for new drives.",
        "new_since_yesterday": new_since_yesterday,
        "urgent": urgent,
        "total_active": total_active,
        "applied": applied,
    }
