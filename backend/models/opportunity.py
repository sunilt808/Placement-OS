"""
models/opportunity.py — Pydantic models for Opportunities and related data.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class OpportunityCategory(str, Enum):
    PLACEMENT_OPPORTUNITY = "PLACEMENT_OPPORTUNITY"
    PLACEMENT_UPDATE = "PLACEMENT_UPDATE"
    DEADLINE_UPDATE = "DEADLINE_UPDATE"
    ASSESSMENT = "ASSESSMENT"
    INTERVIEW = "INTERVIEW"
    SHORTLIST = "SHORTLIST"
    GENERAL_ANNOUNCEMENT = "GENERAL_ANNOUNCEMENT"
    IRRELEVANT = "IRRELEVANT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ApplicationStatus(str, Enum):
    NEW = "NEW"
    VIEWED = "VIEWED"
    NOT_APPLIED = "NOT_APPLIED"
    APPLIED = "APPLIED"
    IGNORED = "IGNORED"
    EXPIRED = "EXPIRED"


class DeadlineUrgency(str, Enum):
    EXPIRED = "EXPIRED"
    TODAY = "TODAY"
    WITHIN_24H = "WITHIN_24H"
    TOMORROW = "TOMORROW"
    WITHIN_3_DAYS = "WITHIN_3_DAYS"
    THIS_WEEK = "THIS_WEEK"
    UPCOMING = "UPCOMING"
    NO_DEADLINE = "NO_DEADLINE"


class AIExtraction(BaseModel):
    """Raw AI-extracted fields from a message."""
    category: OpportunityCategory
    is_placement_related: bool
    company: Optional[str] = None
    role: Optional[str] = None
    ctc: Optional[str] = None
    location: Optional[str] = None
    eligible_branches: Optional[List[str]] = None
    eligible_batch: Optional[str] = None
    cgpa_requirement: Optional[str] = None
    backlog_requirement: Optional[str] = None
    experience_requirement: Optional[str] = None
    deadline: Optional[datetime] = None
    assessment_date: Optional[datetime] = None
    interview_date: Optional[datetime] = None
    registration_link: Optional[str] = None
    required_skills: Optional[List[str]] = None
    action_required: bool = False
    summary: Optional[str] = None
    confidence: float = 0.0

    # ── NEW: CSE Intelligence Fields ─────────────────────────────────────────
    cse_relevance_score: int = 0          # 0–100: how relevant is this to CSE
    is_cse_relevant: bool = False         # True if score >= 50
    jd_cse_signals: Optional[List[str]] = None  # matched CSE tech keywords from JD
    source_document: Optional[str] = None       # e.g. "Accenture_JD.pdf"
    source_document_key: Optional[str] = None   # stored local attachment key
    telegram_message_date: Optional[datetime] = None  # original Telegram send time


class OpportunityCreate(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    ctc: Optional[str] = None
    location: Optional[str] = None
    eligible_branches: Optional[List[str]] = None
    eligible_batch: Optional[str] = None
    cgpa_requirement: Optional[str] = None
    backlog_requirement: Optional[str] = None
    experience_requirement: Optional[str] = None
    deadline: Optional[datetime] = None
    assessment_date: Optional[datetime] = None
    interview_date: Optional[datetime] = None
    registration_link: Optional[str] = None
    skills: Optional[List[str]] = None
    status: ApplicationStatus = ApplicationStatus.NEW
    confidence: float = 0.0
    summary: Optional[str] = None
    category: OpportunityCategory = OpportunityCategory.PLACEMENT_OPPORTUNITY
    source_message_ids: List[str] = Field(default_factory=list)

    # ── NEW fields ────────────────────────────────────────────────────────────
    cse_relevance_score: int = 0
    is_cse_relevant: bool = False
    jd_cse_signals: Optional[List[str]] = None
    source_document: Optional[str] = None
    source_document_key: Optional[str] = None
    telegram_message_date: Optional[datetime] = None


class OpportunityUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    deadline: Optional[datetime] = None
    assessment_date: Optional[datetime] = None
    interview_date: Optional[datetime] = None
    registration_link: Optional[str] = None
    ctc: Optional[str] = None
    summary: Optional[str] = None


class OpportunityOut(OpportunityCreate):
    id: str = Field(alias="_id")
    deadline_urgency: Optional[DeadlineUrgency] = None
    relevance_score: Optional[float] = None
    eligibility_status: Optional[str] = None
    eligibility_checks: Optional[List[dict]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class EventType(str, Enum):
    CREATED = "CREATED"
    DEADLINE_UPDATED = "DEADLINE_UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    REMINDER_SENT = "REMINDER_SENT"
    UPDATE_RECEIVED = "UPDATE_RECEIVED"
    SHORTLISTED = "SHORTLISTED"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"


class OpportunityEvent(BaseModel):
    opportunity_id: str
    event_type: EventType
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    message_id: Optional[str] = None
    note: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
