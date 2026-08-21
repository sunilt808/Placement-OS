"""
services/ai_service.py — Gemini AI integration for classification and extraction.

Strategy (from revised plan):
- Flash model (gemini-1.5-flash) for all live messages — fast, cheap.
- Pro model (gemini-1.5-pro) for ambiguous cases (confidence < threshold).
- Content-hash caching — never re-process identical messages.
- Timestamp-anchored date resolution — CRITICAL for historical import.
  Always pass original message send time so relative dates resolve correctly.
"""
import json
import hashlib
import asyncio
from datetime import datetime
from typing import Optional
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from config import settings
from models.opportunity import AIExtraction, OpportunityCategory

# ── Configure Gemini ──────────────────────────────────────────────────────────
genai.configure(api_key=settings.gemini_api_key)

_flash_model = genai.GenerativeModel(settings.gemini_flash_model)
_pro_model = genai.GenerativeModel(settings.gemini_pro_model)

# In-memory cache for content hashes (also persisted in MongoDB)
_hash_cache: dict[str, AIExtraction] = {}

EXTRACTION_SCHEMA = """
{
  "category": "one of: PLACEMENT_OPPORTUNITY | PLACEMENT_UPDATE | DEADLINE_UPDATE | ASSESSMENT | INTERVIEW | SHORTLIST | GENERAL_ANNOUNCEMENT | IRRELEVANT | NEEDS_REVIEW",
  "is_placement_related": true or false,
  "company": "string or null",
  "role": "string or null",
  "ctc": "string or null (preserve original format, e.g. '12 LPA', '₹8-10 LPA')",
  "location": "string or null",
  "eligible_branches": ["CSE", "ISE"] or null,
  "eligible_batch": "string or null (e.g. '2024-2027')",
  "cgpa_requirement": "string or null (e.g. '7.0+', '6.5 and above')",
  "backlog_requirement": "string or null (e.g. 'No backlogs', '0 active backlogs')",
  "experience_requirement": "string or null",
  "deadline": "ISO 8601 datetime string with timezone offset or null",
  "assessment_date": "ISO 8601 datetime string with timezone offset or null",
  "interview_date": "ISO 8601 datetime string with timezone offset or null",
  "registration_link": "URL string or null",
  "required_skills": ["Python", "SQL"] or null,
  "action_required": true or false,
  "summary": "1-2 sentence human readable summary of what this message says",
  "confidence": 0.0 to 1.0
}
"""

SYSTEM_PROMPT = """You are a placement monitoring assistant for an Indian engineering college student.
Your job is to classify and extract structured information from Telegram messages about campus placements.

CRITICAL RULES:
1. NEVER invent or hallucinate: company names, CTC, deadlines, eligibility, links, or dates.
   If information is not explicitly present → use null.
2. Preserve original format for CTC (e.g., "12 LPA", "₹8-10 LPA per annum").
3. For all dates/deadlines: resolve relative terms ("tomorrow", "next Monday", "by EOD")
   STRICTLY relative to the message's ORIGINAL SEND TIME provided below.
   Do NOT use today's date. Use the message timestamp as the anchor.
4. Store all datetimes in ISO 8601 format with IST offset (+05:30).
5. When uncertain, prefer PLACEMENT_RELATED classification over IRRELEVANT.
   A false positive is acceptable; a missed opportunity is not.
6. If confidence is below 0.70, set category to NEEDS_REVIEW — still extract what you can.
7. For IRRELEVANT messages, return is_placement_related: false and confidence: 0.95+.

Return ONLY valid JSON matching the schema below. No markdown, no explanation.

SCHEMA:
{schema}
"""


def _content_hash(text: str) -> str:
    """SHA-256 hash of message text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_prompt(text: str, message_date: datetime) -> str:
    """Build the extraction prompt with timestamp anchor."""
    ist_time = message_date.strftime("%Y-%m-%d %H:%M:%S IST (UTC+05:30)")
    return f"""MESSAGE ORIGINAL SEND TIME: {ist_time}
(Use this as the anchor for ALL relative date expressions like "tomorrow", "next week", "in 3 days")

MESSAGE TEXT:
{text}

Extract structured placement information from the message above.
"""


async def _call_gemini(model, prompt: str, system: str) -> dict:
    """Call Gemini model and parse JSON response."""
    full_prompt = f"{system}\n\n{prompt}"
    response = await asyncio.to_thread(
        model.generate_content,
        full_prompt,
        generation_config=GenerationConfig(
            temperature=0.1,          # Low temp for deterministic extraction
            response_mime_type="application/json",
        ),
    )
    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


async def classify_and_extract(
    text: str,
    message_date: datetime,
    force_pro: bool = False,
    cached_hash: Optional[str] = None,
) -> tuple[AIExtraction, str]:
    """
    Main AI extraction function.
    Returns (AIExtraction, content_hash).

    Steps:
    1. Check content hash cache.
    2. Call flash model.
    3. If confidence < threshold, escalate to pro model.
    """
    content_hash = cached_hash or _content_hash(text)

    # ── Cache hit ─────────────────────────────────────────────────────────────
    if content_hash in _hash_cache:
        return _hash_cache[content_hash], content_hash

    system = SYSTEM_PROMPT.format(schema=EXTRACTION_SCHEMA)
    prompt = _build_prompt(text, message_date)

    try:
        model = _pro_model if force_pro else _flash_model
        data = await _call_gemini(model, prompt, system)
        extraction = AIExtraction(**data)

        # ── Escalate to pro if low confidence ─────────────────────────────────
        if (
            not force_pro
            and extraction.confidence < settings.confidence_threshold
            and extraction.category != OpportunityCategory.IRRELEVANT
        ):
            data = await _call_gemini(_pro_model, prompt, system)
            extraction = AIExtraction(**data)

        _hash_cache[content_hash] = extraction
        return extraction, content_hash

    except Exception as e:
        # ── Fail gracefully — never lose the message ──────────────────────────
        print(f"[AI] Extraction error: {e}")
        fallback = AIExtraction(
            category=OpportunityCategory.NEEDS_REVIEW,
            is_placement_related=True,
            confidence=0.0,
            summary=f"AI extraction failed: {str(e)[:100]}",
        )
        return fallback, content_hash
