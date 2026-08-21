"""
scripts/fix_company_names.py -- One-time DB cleanup for hallucinated company/role fields.
Run: cd backend && python scripts/fix_company_names.py
"""
import asyncio
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import connect_db, opportunities_col, messages_col
from services.nlp_extractor import extract_company_nlp, extract_role_nlp, _is_valid_company_name


def is_bad_company(name):
    """Check if company name is a garbage/hallucinated value."""
    if not name:
        return False
    if len(name) > 50:
        return True
    if name[0].islower():
        return True
    # Contains a sentence break (". Capitalized")
    if re.search(r'\.\s+[A-Z]', name):
        return True
    # Ends with a period (fragment mid-sentence)
    if name.rstrip().endswith('.'):
        return True

    # Words that indicate this is a sentence fragment, not a company name
    bad_starts = [
        "the ", "a ", "an ", "this ", "that ", "our ", "their ", "is ", "has ",
        "was ", "are ", "were ", "will ", "overview", "students", "candidates",
        "please", "dear", "hi ", "before ", "after ", "during ", "based on",
        "people have", "hires ", "has scheduled", "specializes", "arranged",
        "norms", "graduate intern tesla", "tomorrow", "before registering",
        "technology built", "and assessment", "has not disclosed",
        "has scheduled", "before completing", "only to register",
        "s are open", "s are ", "graduate intern", "'s premise",
        "technology\nbuilt", "technology built",
    ]
    name_lower = name.lower().strip()
    for bs in bad_starts:
        if name_lower.startswith(bs):
            return True

    # Contains only verbs/generic words
    DEFINITELY_NOT_COMPANY = {
        "tomorrow", "students", "candidates", "placement", "college",
        "university", "department", "round", "overview", "announcement",
        "notification", "important", "reminder", "update",
        "internships", "pre-placement talk", "telegram", "& complete"
    }
    if name_lower in DEFINITELY_NOT_COMPANY:
        return True

    # Has possessive 's suggesting it's a fragment ("Tomorrow's")
    if re.match(r"^\w+\'s\s+\w", name):
        return True

    # Starts with a common English verb in past tense (fragment detection)
    verb_fragments = [
        "hires", "hired", "schedules", "scheduled", "specializes", "arranged",
        "disclosed", "completed", "reached", "started", "opened",
    ]
    first_word = name_lower.split()[0] if name_lower.split() else ""
    if first_word in verb_fragments:
        return True

    return False


def is_bad_role(role):
    """Check if role is a garbage/hallucinated value."""
    if not role:
        return False
    if len(role) > 60:
        return True
    if re.search(r'\.\s+[A-Z]', role):
        return True
    bad_starts = [
        "in the hackathon", "across technology", "only to register",
        "before completing", "before registering", "based on performance",
        "overview.", "bandwidth requirements", "open but due to",
        "ai in content creation", "learners before", "s are open",
    ]
    role_lower = role.lower().strip()
    for bs in bad_starts:
        if role_lower.startswith(bs):
            return True
            
    # Check for newline fragments
    if "\n" in role:
        return True
        
    return False


async def fix_records():
    await connect_db()
    col = opportunities_col()
    msg_col = messages_col()

    total = 0
    fixed_company = 0
    fixed_role = 0
    cleared_company = 0
    cleared_role = 0

    print("Scanning all opportunities for bad company/role names...")
    print("=" * 60)

    async for opp in col.find({}):
        updates = {}
        opp_id = opp["_id"]
        current_company = opp.get("company")
        current_role = opp.get("role")

        # Fetch original message text
        source_ids = opp.get("source_message_ids", [])
        message_text = ""
        for mid in source_ids[:3]:
            try:
                from bson import ObjectId
                msg = await msg_col.find_one({"_id": ObjectId(mid)})
                if msg and msg.get("message_text"):
                    message_text = msg["message_text"]
                    break
            except Exception:
                pass

        # Fix bad company names
        if is_bad_company(current_company):
            if message_text:
                new_company = extract_company_nlp(message_text)
                if new_company and _is_valid_company_name(new_company):
                    updates["company"] = new_company
                    fixed_company += 1
                    old_trunc = (current_company or "")[:40]
                    print(f"  FIXED: '{old_trunc}' -> '{new_company}'")
                else:
                    updates["company"] = None
                    cleared_company += 1
                    old_trunc = (current_company or "")[:40]
                    print(f"  CLEARED: '{old_trunc}' -> None")
            else:
                updates["company"] = None
                cleared_company += 1

        # Fix bad role names
        if is_bad_role(current_role):
            if message_text:
                new_role = extract_role_nlp(message_text)
                if new_role and len(new_role) <= 60:
                    updates["role"] = new_role
                    fixed_role += 1
                    old_trunc = (current_role or "")[:40]
                    print(f"  ROLE FIXED: '{old_trunc}' -> '{new_role}'")
                else:
                    updates["role"] = None
                    cleared_role += 1
            else:
                updates["role"] = None
                cleared_role += 1

        if updates:
            await col.update_one({"_id": opp_id}, {"$set": updates})
            total += 1

    print("")
    print("=" * 60)
    print("DB CLEANUP COMPLETE")
    print(f"  Total records fixed  : {total}")
    print(f"  Company names fixed  : {fixed_company}")
    print(f"  Company names cleared: {cleared_company}")
    print(f"  Role names fixed     : {fixed_role}")
    print(f"  Role names cleared   : {cleared_role}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(fix_records())
