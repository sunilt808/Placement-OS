"""
services/ai_service.py — Gemini AI integration for classification and extraction.

Strategy:
- Local rule-based extraction ALWAYS runs first (fast, offline, reliable).
- Gemini API runs as OPTIONAL enhancement layer.
- If Gemini fails, system continues with local intelligence.
- Content-hash caching — never re-process identical messages.
- Timestamp-anchored date resolution — CRITICAL for historical import.
"""
import json
import hashlib
import asyncio
from datetime import datetime
from typing import Optional

from config import settings
from models.opportunity import AIExtraction, OpportunityCategory
from services.nlp_extractor import extract_with_nlp

# ── Configure Gemini (optional) ───────────────────────────────────────────────
_flash_model = None
_pro_model = None

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    if (settings.gemini_enabled and settings.gemini_api_key
            and settings.gemini_api_key != "YOUR_GEMINI_API_KEY"):
        genai.configure(api_key=settings.gemini_api_key)
        _flash_model = genai.GenerativeModel(settings.gemini_flash_model)
        _pro_model = genai.GenerativeModel(settings.gemini_pro_model)
except Exception as e:
    print(f"[AI] Gemini init failed: {e} — local-only mode")

# In-memory cache for content hashes
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
  "confidence": 0.0 to 1.0,
  "cse_relevance_score": "0 to 100 based on JD technical keywords, role and branch",
  "is_cse_relevant": "true or false",
  "jd_cse_signals": "[\"list of CSE-related technical keywords matched from the JD\"] or null",
  "source_document": "string filename or null"
}
"""

SYSTEM_PROMPT = """You are a placement monitoring assistant for an Indian engineering college CSE student.
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
8. Evaluate CSE relevance strictly from JD content (role, branches, tech skills).

CSE RELEVANCE RULES (MOST IMPORTANT):
8. cse_relevance_score (0-100): How relevant is this specific job/JD to a CSE student?
   - 90-100: Strong CSE opportunity (Software Engineer, SDE, Developer, AI/ML, Data roles)
   - 70-89: Likely CSE relevant (tech-adjacent roles with software responsibilities)
   - 50-69: Possibly relevant (Graduate Engineer Trainee with some coding in JD)
   - Below 50: Not CSE relevant (Robotics, Mechanical, Civil, Sales, non-technical roles)
9. Do NOT base score on company fame (TCS is NOT always CSE — check the specific role/JD).
10. A "Graduate Engineer Trainee" at Keyence for Robotics Engineering = score 15 (NOT CSE).
11. A "Graduate Engineer Trainee" at Infosys writing Python/Java = score 85 (CSE relevant).
12. Analyze the ACTUAL JD content for tech keywords: Python, Java, APIs, databases, cloud, etc.
13. is_cse_relevant = true only if cse_relevance_score >= 50.
14. jd_cse_signals: list the actual tech keywords found in the JD (Python, SQL, REST API, etc.)

Return ONLY valid JSON matching the schema below. No markdown, no explanation.

SCHEMA:
{schema}
"""


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_prompt(text: str, message_date: datetime) -> str:
    ist_time = message_date.strftime("%Y-%m-%d %H:%M:%S IST (UTC+05:30)")
    return f"""MESSAGE ORIGINAL SEND TIME: {ist_time}
(Use this as the anchor for ALL relative date expressions like "tomorrow", "next week", "in 3 days")

MESSAGE TEXT:
{text}

Extract structured placement information. Pay special attention to CSE relevance scoring.
Analyze the actual role and JD content — not just the company name.
"""


async def _call_gemini(model, prompt: str, system: str) -> dict:
    """Call Gemini model with retry on rate limits and parse JSON response."""
    full_prompt = f"{system}\n\n{prompt}"
    for attempt in range(3):
        try:
            from google.generativeai.types import GenerationConfig
            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt,
                generation_config=GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "ResourceExhausted" in err_str or "quota" in err_str.lower()) and attempt < 2:
                if "perday" in err_str.lower() or "limit: 20" in err_str.lower() or "daily" in err_str.lower():
                    print("[AI] Daily quota exhausted, aborting retries.")
                    raise e
                wait = 15 * (attempt + 1)
                print(f"[AI] Rate limited (429), waiting {wait}s before retry (attempt {attempt+1}/3)...")
                await asyncio.sleep(wait)
            else:
                raise e

def _validate_gemini_company(candidate: Optional[str], local_company: Optional[str]) -> Optional[str]:
    """
    Guard against Gemini hallucinating descriptions as company names.
    Rules:
    - Max 50 chars (a real company name isn't a sentence)
    - Must not start with lowercase
    - Must not contain sentence-ending patterns like ". "
    - Must not be a verb phrase or description
    """
    if not candidate:
        return local_company
    
    REJECT_STARTS = [
        "the ", "a ", "an ", "this ", "that ", "our ", "their ",
        "is ", "has ", "was ", "are ", "were ", "will ", "overview",
        "students", "candidates", "please", "dear", "hi ",
    ]
    REJECT_PATTERNS = [
        r'\.\s+[A-Z]',          # Contains a sentence break
        r',\s+[A-Z][a-z]+ [A-Z]',  # Looks like a list/description
        r'\b(students?|candidates?|department|placement|college)\b',
    ]
    
    c_lower = candidate.lower().strip()
    
    if len(candidate) > 50:
        return local_company
    
    if candidate[0].islower():
        return local_company
    
    for rs in REJECT_STARTS:
        if c_lower.startswith(rs):
            return local_company
    
    for rp in REJECT_PATTERNS:
        if re.search(rp, candidate):
            return local_company
    
    return candidate


def _validate_gemini_role(candidate: Optional[str], local_role: Optional[str]) -> Optional[str]:
    """Guard against Gemini returning full sentences as roles."""
    if not candidate:
        return local_role
    if len(candidate) > 60:
        return local_role
    if re.search(r'\.\s+[A-Z]', candidate):
        return local_role
    return candidate



def merge_extractions(local: AIExtraction, gemini: AIExtraction) -> AIExtraction:
    """
    Merge Gemini's optional enhancement with our NLP local extraction.
    - Local (NLP) wins on company/role via validation guards
    - Gemini contributes semantic fields (location, better summary)
    - Strict validation prevents Gemini hallucinations
    """
    validated_company = _validate_gemini_company(gemini.company, local.company)
    validated_role = _validate_gemini_role(gemini.role, local.role)

    return AIExtraction(
        category=gemini.category if gemini.category != OpportunityCategory.IRRELEVANT else local.category,
        is_placement_related=gemini.is_placement_related or local.is_placement_related,
        company=validated_company,
        role=validated_role,
        ctc=gemini.ctc or local.ctc,
        location=gemini.location or local.location,
        eligible_branches=gemini.eligible_branches or local.eligible_branches,
        eligible_batch=gemini.eligible_batch or local.eligible_batch,
        cgpa_requirement=gemini.cgpa_requirement or local.cgpa_requirement,
        backlog_requirement=gemini.backlog_requirement or local.backlog_requirement,
        experience_requirement=gemini.experience_requirement or local.experience_requirement,
        deadline=gemini.deadline or local.deadline,
        assessment_date=gemini.assessment_date or local.assessment_date,
        interview_date=gemini.interview_date or local.interview_date,
        registration_link=local.registration_link or gemini.registration_link,
        required_skills=gemini.required_skills or local.required_skills,
        action_required=gemini.action_required or local.action_required,
        summary=gemini.summary if gemini.summary and len(gemini.summary) > 20 else local.summary,
        confidence=max(gemini.confidence, local.confidence),
        cse_relevance_score=max(gemini.cse_relevance_score, local.cse_relevance_score),
        is_cse_relevant=gemini.is_cse_relevant or local.is_cse_relevant,
        jd_cse_signals=gemini.jd_cse_signals or local.jd_cse_signals,
        source_document=gemini.source_document or local.source_document,
        telegram_message_date=local.telegram_message_date or gemini.telegram_message_date,
    )


async def classify_and_extract(
    text: str,
    message_date: datetime,
    force_pro: bool = False,
    cached_hash: Optional[str] = None,
) -> tuple[AIExtraction, str]:
    """
    Main extraction function.

    Architecture:
    1. Local rule-based & regex extraction ALWAYS runs first (fast, offline, reliable).
    2. Gemini API runs as OPTIONAL enhancement layer.
    3. If Gemini fails or API key is missing, falls back smoothly to local intelligence.
    4. System NEVER fails — always returns a result.
    """
    content_hash = cached_hash or _content_hash(text)

    # ── Cache hit ──────────────────────────────────────────────────────────────
    if content_hash in _hash_cache:
        return _hash_cache[content_hash], content_hash

    # ── STEP 1: Advanced NLP extraction (ALWAYS runs, ZERO API calls) ──────────
    local_result = extract_with_nlp(text, message_date)
    local_result.telegram_message_date = message_date

    # ── STEP 2: Check Gemini API availability ─────────────────────────────────
    if not _flash_model:
        print("[AI] Gemini unavailable — proceeding with local extraction only")
        _hash_cache[content_hash] = local_result
        return local_result, content_hash

    if (not settings.gemini_enabled or not settings.gemini_api_key
            or settings.gemini_api_key == "YOUR_GEMINI_API_KEY"):
        print("[AI] Gemini disabled/unconfigured — proceeding with local extraction")
        _hash_cache[content_hash] = local_result
        return local_result, content_hash

    # ── STEP 3: Gemini optional enhancement ───────────────────────────────────
    system = SYSTEM_PROMPT.format(schema=EXTRACTION_SCHEMA)
    prompt = _build_prompt(text, message_date)

    try:
        model = _pro_model if force_pro else _flash_model
        data = await _call_gemini(model, prompt, system)

        # Handle Gemini not returning new fields gracefully
        data.setdefault("cse_relevance_score", 0)
        data.setdefault("is_cse_relevant", False)
        data.setdefault("jd_cse_signals", None)
        data.setdefault("source_document", None)
        data.setdefault("telegram_message_date", None)

        gemini_result = AIExtraction(**data)

        # ── Escalate to pro if low confidence ─────────────────────────────────
        if (
            not force_pro
            and gemini_result.confidence < settings.confidence_threshold
            and gemini_result.category != OpportunityCategory.IRRELEVANT
        ):
            try:
                data = await _call_gemini(_pro_model, prompt, system)
                data.setdefault("cse_relevance_score", 0)
                data.setdefault("is_cse_relevant", False)
                data.setdefault("jd_cse_signals", None)
                data.setdefault("source_document", None)
                data.setdefault("telegram_message_date", None)
                gemini_result = AIExtraction(**data)
            except Exception:
                pass  # keep flash result

        final_result = merge_extractions(local_result, gemini_result)
        _hash_cache[content_hash] = final_result
        return final_result, content_hash

    except Exception as e:
        # ── Fail gracefully — NEVER lose the message ───────────────────────────
        print(f"[AI] Gemini unavailable/failed ({type(e).__name__}: {e}) — continuing with local intelligence")
        _hash_cache[content_hash] = local_result
        return local_result, content_hash
