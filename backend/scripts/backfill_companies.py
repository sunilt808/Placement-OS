"""
scripts/backfill_companies.py — One-shot repair for junk company names.

Re-extracts the company from the ORIGINAL Telegram message text for every
opportunity whose stored company is sign-off noise ("Thanks & Regards", etc.)
or missing, then refreshes role_class / relevance fields.

Run:  python scripts/backfill_companies.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import opportunities_col, messages_col, connect_db, close_db
from services.nlp_extractor import extract_company_nlp, extract_with_nlp
from services.eligibility_service import classify_cse_signal

JUNK_HINTS = ("regard", "thanks", "thank you", "subject", "dear ")


def is_junk(company: str | None) -> bool:
    if not company or not company.strip():
        return True
    c = company.lower()
    return any(h in c for h in JUNK_HINTS)


async def main():
    await connect_db()
    col = opportunities_col()
    fixed = skipped = 0
    cursor = col.find({})
    async for opp in cursor:
        if not is_junk(opp.get("company")):
            continue
        msg = await messages_col().find_one({"opportunity_id": str(opp["_id"])})
        if not msg:
            skipped += 1
            continue
        text = msg.get("message_text") or ""
        new_company = extract_company_nlp(text)
        if not new_company:
            skipped += 1
            continue

        fresh = extract_with_nlp(text, msg.get("message_date"))
        signal = classify_cse_signal(
            fresh.role if fresh.role else opp.get("role"),
            fresh.eligible_branches or opp.get("eligible_branches"),
        )
        await col.update_one(
            {"_id": opp["_id"]},
            {"$set": {
                "company": new_company,
                "role": fresh.role or opp.get("role"),
                "cse_relevance_score": max(fresh.cse_relevance_score,
                                           opp.get("cse_relevance_score") or 0),
                "is_cse_relevant": fresh.is_cse_relevant or bool(opp.get("is_cse_relevant")),
                "role_class": signal["role_class"],
                "role_class_reason": signal["role_class_reason"],
                "confidence": max(fresh.confidence, opp.get("confidence") or 0),
                "updated_at": __import__("datetime").datetime.utcnow(),
            }},
        )
        print(f"[FIXED] {opp.get('company')!r} -> {new_company!r} "
              f"({signal['role_class']})")
        fixed += 1
    print(f"Done. fixed={fixed} skipped={skipped}")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
