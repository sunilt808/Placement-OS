"""
services/eligibility_service.py - Evaluates student eligibility for an opportunity.
"""
from database import app_settings_col

# Known software engineering roles for CSE matching
CSE_ROLES = {
    "sde", "software", "engineer", "developer", "backend", "frontend", 
    "full stack", "fullstack", "ai", "ml", "data scientist", 
    "data science", "analyst", "programmer", "coder", "web"
}

async def compute_eligibility(opportunity: dict) -> dict:
    """
    Matches the student profile against the opportunity requirements.
    Returns: {
        "eligibility_status": "ELIGIBLE" | "NOT_ELIGIBLE" | "UNCLEAR",
        "relevance_score": int (0-100),
        "checks": [ {"label": str, "status": "pass" | "fail" | "unknown"} ]
    }
    """
    col = app_settings_col()
    profile_doc = await col.find_one({"key": "eligibility_profile"})
    profile = profile_doc or {}

    checks = []
    is_eligible = True
    has_unknowns = False
    score = 100

    # 1. Branch check
    req_branches = opportunity.get("eligible_branches") or []
    prof_branch = profile.get("branch", "").upper()
    
    if req_branches and prof_branch:
        # Check if prof_branch is in the requested branches (case insensitive)
        matched = any(prof_branch in rb.upper() for rb in req_branches)
        if matched:
            checks.append({"label": f"Branch: {prof_branch} eligible", "status": "pass"})
        else:
            checks.append({"label": f"Branch: {prof_branch} not in {', '.join(req_branches)}", "status": "fail"})
            is_eligible = False
            score -= 40
    elif req_branches:
        checks.append({"label": "Branch: Profile branch not set", "status": "unknown"})
        has_unknowns = True
        score -= 10
    else:
        checks.append({"label": "Branch: Any/Unknown requirement", "status": "unknown"})
        has_unknowns = True

    # 2. Batch check
    req_batch = opportunity.get("eligible_batch")
    prof_batch = profile.get("batch")
    
    if req_batch and prof_batch:
        if prof_batch in req_batch:
            checks.append({"label": f"Batch: {prof_batch} eligible", "status": "pass"})
        else:
            checks.append({"label": f"Batch: {prof_batch} not matching {req_batch}", "status": "fail"})
            is_eligible = False
            score -= 30
    elif req_batch:
        checks.append({"label": "Batch: Profile batch not set", "status": "unknown"})
        has_unknowns = True
        score -= 10
    else:
        checks.append({"label": "Batch: Any/Unknown requirement", "status": "unknown"})
        has_unknowns = True

    # 3. CGPA check
    req_cgpa_str = opportunity.get("cgpa_requirement")
    prof_cgpa = profile.get("cgpa")
    
    if req_cgpa_str and prof_cgpa is not None:
        import re
        # Try to extract a float from the requirement string (e.g. "7.0+" -> 7.0)
        match = re.search(r"(\d+(\.\d+)?)", req_cgpa_str)
        if match:
            req_cgpa = float(match.group(1))
            if prof_cgpa >= req_cgpa:
                checks.append({"label": f"CGPA: {prof_cgpa} >= {req_cgpa}", "status": "pass"})
            else:
                checks.append({"label": f"CGPA: {prof_cgpa} < {req_cgpa}", "status": "fail"})
                is_eligible = False
                score -= 30
        else:
            checks.append({"label": f"CGPA: Could not parse '{req_cgpa_str}'", "status": "unknown"})
            has_unknowns = True
    elif req_cgpa_str:
        checks.append({"label": "CGPA: Profile CGPA not set", "status": "unknown"})
        has_unknowns = True
        score -= 10
    else:
        checks.append({"label": "CGPA: No requirement specified", "status": "pass"})

    # 4. Role relevance
    # If the user is a CSE student, check if the role is a software role
    role = opportunity.get("role", "").lower()
    is_cse = "CS" in prof_branch or "COMPUTER" in prof_branch
    
    if role and is_cse:
        # Check if role contains any of the CSE_ROLES
        is_relevant = any(cr in role for cr in CSE_ROLES)
        if is_relevant:
            checks.append({"label": "Role: Relevant to CSE", "status": "pass"})
        else:
            checks.append({"label": "Role: May not be relevant to CSE", "status": "unknown"})
            has_unknowns = True
            score -= 10

    # Determine final status
    if not is_eligible:
        status = "NOT_ELIGIBLE"
    elif has_unknowns:
        status = "UNCLEAR"
    else:
        status = "ELIGIBLE"

    return {
        "eligibility_status": status,
        "relevance_score": max(0, score),
        "checks": checks
    }
