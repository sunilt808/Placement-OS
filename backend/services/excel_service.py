"""
services/excel_service.py — Spreadsheet (Excel/CSV) handling for result sheets.

College placement cells post SHORTLIST / RESULT sheets as Excel files
containing every student's data. This service:

1. Detects spreadsheet attachments (.xlsx/.xls/.csv) on Telegram messages.
2. Parses rows locally with openpyxl (xlsx) or csv stdlib.
3. Scans EVERY cell for the hardcoded student identity:
     - USN match  (exact, normalization-insensitive) -> highest priority
     - Name match (fuzzy, rapidfuzz partial_ratio)   -> fallback
4. Stores the file permanently so results stay viewable.
5. Returns a hit report the caller turns into a Telegram alert.

Zero AI involvement — pure deterministic matching.
"""
import asyncio
import csv
import io
import re
from typing import Any, Dict, List, Optional

from config import settings
from rapidfuzz import fuzz

try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

SPREADSHEET_EXTS = (".xlsx", ".xls", ".csv")
SPREADSHEET_MIMES = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
)

NAME_FUZZ_THRESHOLD = 90


def is_spreadsheet(filename: Optional[str], mime_type: Optional[str] = "") -> bool:
    fname = (filename or "").lower()
    return fname.endswith(SPREADSHEET_EXTS) or (mime_type or "") in SPREADSHEET_MIMES


def _normalize_usn(value: str) -> str:
    """1ds24cs421 / 1DS24CS421 / 1DS 24 CS 421 -> 1DS24CS421"""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _usn_match_keys(value: str) -> List[str]:
    """
    Return the canonical USN plus tolerant variants.

    Sheets sometimes drop the leading college digit ("DS24CS421" vs
    "1DS24CS421"), so we match on the trailing distinctive part too.
    """
    norm = _normalize_usn(value)
    keys = {norm} if norm else set()
    # Variant with a leading digit stripped (1DS24CS421 -> DS24CS421)
    if len(norm) > 3 and norm[0].isdigit():
        keys.add(norm[1:])
    # Variant with an extra leading digit added (DS24CS421 -> 1DS24CS421)
    if norm and not norm[0].isdigit() and len(norm) >= 8:
        keys.add("1" + norm)
    return [k for k in keys if len(k) >= 8]


def _name_variants(full_name: str) -> List[str]:
    """
    "Sunil T" -> ["sunil t", "sunil", "t sunil", "sunil t.", "t. sunil"]
    Handles Indian name-order flips and initial forms.
    """
    base = re.sub(r"[^A-Za-z\s.]", " ", full_name).strip().lower()
    parts = [p.strip(". ") for p in base.split() if p.strip(". ")]
    variants = {base}
    if len(parts) >= 2:
        first, rest = parts[0], " ".join(parts[1:])
        variants.add(first)                    # "sunil"
        variants.add(rest)                     # "t"
        variants.add(f"{rest} {first}")        # "t sunil"
    elif parts:
        variants.add(parts[0])
    # Drop ultra-short initials-only variants to avoid false positives
    return [v for v in variants if len(v) >= 3]


def find_student_hit(rows: List[List[Any]]) -> Optional[Dict[str, Any]]:
    """
    Scan all parsed rows cell-by-cell.
    USN wins over name; earliest row wins within same priority.
    """
    usn_target = _normalize_usn(settings.student_usn)
    usn_keys = _usn_match_keys(settings.student_usn)
    name_variants = _name_variants(settings.student_name)

    name_fallback = None

    for r_idx, row in enumerate(rows):
        for c_idx, cell in enumerate(row):
            if cell is None:
                continue
            text = str(cell).strip()
            if not text or len(text) > 120:
                continue

            # ── Priority 1: USN exact containment ────────────────────────────
            if usn_keys and len(norm := _normalize_usn(text)) <= 40:
                if any(key in norm for key in usn_keys):
                    return {
                        "matched_field": "USN",
                        "matched_value": settings.student_usn,
                        "row_number": r_idx + 1,
                        "column": c_idx + 1,
                        "cell_text": text,
                        "row": [_clean(c) for c in row],
                    }

            # ── Priority 2: fuzzy name (remember best, don't return yet) ─────
            low = text.lower()
            if len(low) <= 60:
                for variant in name_variants:
                    score = fuzz.partial_ratio(variant, low)
                    if score >= NAME_FUZZ_THRESHOLD:
                        candidate = {
                            "matched_field": "NAME",
                            "matched_value": variant,
                            "score": score,
                            "row_number": r_idx + 1,
                            "column": c_idx + 1,
                            "cell_text": text,
                            "row": [_clean(c) for c in row],
                        }
                        if name_fallback is None or score > name_fallback["score"]:
                            name_fallback = candidate

    return name_fallback


def _clean(cell: Any) -> str:
    return "" if cell is None else str(cell).strip()


def _parse_xlsx(data: bytes) -> List[List[Any]]:
    if not _HAS_OPENPYXL:
        print("[Excel] openpyxl not installed — cannot parse xlsx")
        return []
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows: List[List[Any]] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            if any(c is not None and str(c).strip() for c in row):
                rows.append(list(row))
    wb.close()
    return rows


def _parse_csv(data: bytes) -> List[List[Any]]:
    text = data.decode("utf-8", errors="replace")
    return [row for row in csv.reader(io.StringIO(text)) if any(c.strip() for c in row)]


async def process_spreadsheet(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "",
    caption: str = "",
) -> Dict[str, Any]:
    """
    Full spreadsheet pipeline: store file -> parse -> scan for student.
    Never raises; returns a report dict either way.
    """
    from services.pdf_service import _store_document

    report: Dict[str, Any] = {
        "filename": filename,
        "mime_type": mime_type or "application/octet-stream",
        "size_bytes": len(file_bytes),
        "storage_key": None,
        "rows_scanned": 0,
        "hit": None,
        "caption": caption,
    }

    try:
        report["storage_key"] = await asyncio.to_thread(_store_document, file_bytes, filename)
    except Exception as e:
        print(f"[Excel] Could not store document: {e}")

    try:
        lower = (filename or "").lower()
        if lower.endswith(".csv"):
            rows = _parse_csv(file_bytes)
        else:
            rows = await asyncio.to_thread(_parse_xlsx, file_bytes)
        report["rows_scanned"] = len(rows)
        print(f"[Excel] Parsed '{filename}': {len(rows)} non-empty rows")

        if rows:
            hit = await asyncio.to_thread(find_student_hit, rows)
            if hit:
                print(f"[Excel] 🎯 STUDENT HIT in '{filename}' via {hit['matched_field']}")
                report["hit"] = hit
            else:
                print(f"[Excel] Student not present in '{filename}'")
    except Exception as e:
        print(f"[Excel] Parse error for '{filename}': {e}")

    return report


async def handle_shortlist_report(report: Dict[str, Any]) -> Optional[str]:
    """
    Act on a processed spreadsheet:
      HIT  -> attach to matching drive (fuzzy on filename+caption), log
              SHORTLISTED event, fire 🎉 Telegram alert.
      MISS -> store silently against matching drive (viewable later).
    Returns opportunity_id touched, if any.
    """
    from datetime import datetime, timedelta, timezone
    from bson import ObjectId
    from rapidfuzz import fuzz as _fuzz
    from database import opportunities_col, events_col
    from models.opportunity import OpportunityCategory, OpportunityEvent, EventType
    from services.notification_service import send_shortlist_hit_alert

    col = opportunities_col()
    context = f"{report.get('filename', '')} {report.get('caption', '')}".strip()
    if not context:
        context = "result sheet"

    # ── Find the drive this sheet belongs to (recent 90 days) ────────────────
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff -= timedelta(days=90)
    best_opp, best_score = None, 0
    async for opp in col.find({"created_at": {"$gte": cutoff}}):
        opp_text = f"{opp.get('company', '')} {opp.get('role', '')} {opp.get('summary', '')}"
        score = _fuzz.token_set_ratio(context.lower(), opp_text.lower())
        if score > best_score:
            best_score, best_opp = score, opp

    now = datetime.utcnow()

    if best_opp is None:
        # No matching drive — surface it as its own shortlist entry
        doc = {
            "company": (report.get("caption") or report.get("filename") or "Placement Cell").strip()[:60],
            "role": None,
            "status": "NEW",
            "category": OpportunityCategory.SHORTLIST,
            "summary": f"Result/shortlist sheet posted: {report.get('filename')}"
                       + (f" — {report['hit']['matched_field']} MATCH FOUND" if report.get("hit") else ""),
            "confidence": 1.0,
            "source_document": report.get("filename"),
            "source_document_key": report.get("storage_key"),
            "created_at": now,
            "updated_at": now,
            "source_message_ids": [],
        }
        result = await col.insert_one(doc)
        opp_id = str(result.inserted_id)
        await events_col().insert_one(OpportunityEvent(
            opportunity_id=opp_id,
            event_type=EventType.CREATED,
            new_value=doc["summary"],
        ).model_dump())
        best_opp = doc | {"_id": result.inserted_id}
    else:
        opp_id = str(best_opp["_id"])
        updates: Dict[str, Any] = {"updated_at": now}
        if not best_opp.get("source_document_key") and report.get("storage_key"):
            updates["source_document"] = report.get("filename")
            updates["source_document_key"] = report.get("storage_key")
        if report.get("hit"):
            updates["status"] = "VIEWED"
        await col.update_one({"_id": best_opp["_id"]}, {"$set": updates})

    # ── Timeline event ────────────────────────────────────────────────────────
    if report.get("hit"):
        hit = report["hit"]
        await events_col().insert_one(OpportunityEvent(
            opportunity_id=opp_id,
            event_type=EventType.SHORTLISTED,
            new_value=f"{hit['matched_field']} matched ({hit['cell_text']}) in {report.get('filename')}",
            note="Auto-detected in spreadsheet attachment",
        ).model_dump())

        await send_shortlist_hit_alert(
            company=best_opp.get("company"),
            filename=report.get("filename"),
            hit=hit,
            opportunity_id=opp_id,
        )

    return opp_id
