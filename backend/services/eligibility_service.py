"""
services/eligibility_service.py

Evaluates student eligibility for an opportunity.
"""

import re

from database import app_settings_col


# =============================================================================
# TEXT NORMALIZATION
# =============================================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for reliable case-insensitive matching.

    Examples:
        CSE                              -> cse
        cse                              -> cse
        Computer Science & Engineering  -> computer science and engineering
        AI/ML                            -> ai ml
        Full-Stack Developer             -> full stack developer
    """
    if not text:
        return ""

    text = str(text).lower()

    # Convert & to "and"
    text = text.replace("&", " and ")

    # Convert separators to spaces
    text = re.sub(r"[/_\\-]", " ", text)

    # Remove remaining punctuation
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Normalize multiple spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def matches_alias(text: str, aliases: set[str]) -> bool:
    """
    Check whether text contains any normalized alias.

    Matching is case-insensitive and ignores common separators.
    """
    normalized_text = normalize_text(text)

    if not normalized_text:
        return False

    return any(
        normalize_text(alias) in normalized_text
        for alias in aliases
    )


# =============================================================================
# CSE / COMPUTER SCIENCE BRANCH ALIASES
# =============================================================================

CSE_BRANCH_ALIASES = {
    "cse",
    "cs",
    "computer science",
    "computer science engineering",
    "computer science and engineering",
    "computer science & engineering",
}


# =============================================================================
# SOFTWARE / CSE ROLE ALIASES
# =============================================================================

CSE_ROLE_ALIASES = {
    # General software
    "software",
    "software engineer",
    "software developer",
    "software development engineer",
    "sde",

    # Developer / programmer
    "developer",
    "programmer",
    "coder",

    # Backend
    "backend",
    "backend developer",
    "backend engineer",

    # Frontend
    "frontend",
    "frontend developer",
    "frontend engineer",

    # Full stack
    "full stack",
    "fullstack",
    "full stack developer",
    "full stack engineer",
    "fsd",

    # Web
    "web developer",
    "web engineer",
    "web development",

    # AI
    "ai",
    "artificial intelligence",
    "ai engineer",
    "ai developer",

    # Machine Learning
    "ml",
    "machine learning",
    "machine learning engineer",
    "ml engineer",

    # AI + ML
    "aiml",
    "ai ml",
    "ai/ml",
    "artificial intelligence and machine learning",

    # Data
    "data scientist",
    "data science",
    "data analyst",

    # Other common software roles
    "application developer",
    "application engineer",
    "software trainee",
    "software intern",
    "development engineer",
}


# =============================================================================
# BRANCH MATCHING
# =============================================================================

def is_cse_branch(branch: str) -> bool:
    """
    Determine whether the student's branch is CSE / Computer Science.
    """
    return matches_alias(branch, CSE_BRANCH_ALIASES)


# =============================================================================
# ROLE MATCHING
# =============================================================================

def is_cse_relevant_role(role: str) -> bool:
    """
    Determine whether an opportunity role is relevant to a CSE student.
    """
    return matches_alias(role, CSE_ROLE_ALIASES)


# =============================================================================
# BATCH MATCHING
# =============================================================================

def normalize_batch(batch) -> set[str]:
    """
    Convert batch information into a normalized set.

    Supports:
        2027
        "2027"
        ["2026", "2027"]
        ["2027", "2028"]
    """
    if batch is None:
        return set()

    if isinstance(batch, (list, tuple, set)):
        values = batch
    else:
        values = [batch]

    return {
        normalize_text(str(value))
        for value in values
        if value is not None and str(value).strip()
    }


def batch_matches(profile_batch, required_batch) -> bool:
    """
    Check whether student's batch matches any required batch.
    """
    profile_batches = normalize_batch(profile_batch)
    required_batches = normalize_batch(required_batch)

    if not profile_batches or not required_batches:
        return False

    return bool(profile_batches.intersection(required_batches))


# =============================================================================
# CGPA PARSING
# =============================================================================

def parse_cgpa_requirement(requirement) -> float | None:
    """
    Extract the CGPA number from a requirement.

    Examples:
        "7.0+"       -> 7.0
        "CGPA 7.5"   -> 7.5
        "Minimum 8"  -> 8.0
        "8 CGPA"     -> 8.0
    """
    if requirement is None:
        return None

    requirement = str(requirement)

    match = re.search(r"(\d+(?:\.\d+)?)", requirement)

    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


# =============================================================================
# ELIGIBILITY
# =============================================================================

async def compute_eligibility(opportunity: dict) -> dict:
    """
    Matches the student profile against the opportunity requirements.

    Returns:
    {
        "eligibility_status":
            "ELIGIBLE" | "NOT_ELIGIBLE" | "UNCLEAR",

        "relevance_score": int (0-100),

        "checks": [
            {
                "label": str,
                "status": "pass" | "fail" | "unknown"
            }
        ]
    }
    """

    # -------------------------------------------------------------------------
    # Load student profile
    # -------------------------------------------------------------------------

    col = app_settings_col()

    profile_doc = await col.find_one({
        "key": "eligibility_profile"
    })

    profile = profile_doc or {}

    checks = []

    is_eligible = True
    has_unknowns = False

    score = 100

    # =========================================================================
    # 1. BRANCH CHECK
    # =========================================================================

    req_branches = opportunity.get("eligible_branches") or []
    prof_branch = profile.get("branch") or ""

    if req_branches and prof_branch:

        normalized_profile_branch = normalize_text(prof_branch)

        matched = False

        for required_branch in req_branches:
            if not required_branch:
                continue

            normalized_required_branch = normalize_text(
                str(required_branch)
            )

            # Direct normalized comparison
            if (
                normalized_profile_branch == normalized_required_branch
                or normalized_profile_branch in normalized_required_branch
                or normalized_required_branch in normalized_profile_branch
            ):
                matched = True
                break

            # CSE aliases
            if (
                is_cse_branch(prof_branch)
                and is_cse_branch(str(required_branch))
            ):
                matched = True
                break

        if matched:
            checks.append({
                "label": f"Branch: {prof_branch} eligible",
                "status": "pass"
            })

        else:
            checks.append({
                "label": (
                    f"Branch: {prof_branch} not in "
                    f"{', '.join(str(x) for x in req_branches)}"
                ),
                "status": "fail"
            })

            is_eligible = False
            score -= 40

    elif req_branches:

        checks.append({
            "label": "Branch: Profile branch not set",
            "status": "unknown"
        })

        has_unknowns = True
        score -= 10

    else:

        checks.append({
            "label": "Branch: Any/Unknown requirement",
            "status": "unknown"
        })

        has_unknowns = True

    # =========================================================================
    # 2. BATCH CHECK
    # =========================================================================

    req_batch = opportunity.get("eligible_batch")
    prof_batch = profile.get("batch")

    if req_batch and prof_batch:

        if batch_matches(prof_batch, req_batch):

            checks.append({
                "label": f"Batch: {prof_batch} eligible",
                "status": "pass"
            })

        else:

            checks.append({
                "label": (
                    f"Batch: {prof_batch} not matching "
                    f"{req_batch}"
                ),
                "status": "fail"
            })

            is_eligible = False
            score -= 30

    elif req_batch:

        checks.append({
            "label": "Batch: Profile batch not set",
            "status": "unknown"
        })

        has_unknowns = True
        score -= 10

    else:

        checks.append({
            "label": "Batch: Any/Unknown requirement",
            "status": "unknown"
        })

        has_unknowns = True

    # =========================================================================
    # 3. CGPA CHECK
    # =========================================================================

    req_cgpa_str = opportunity.get("cgpa_requirement")
    prof_cgpa = profile.get("cgpa")

    if req_cgpa_str and prof_cgpa is not None:

        req_cgpa = parse_cgpa_requirement(req_cgpa_str)

        if req_cgpa is not None:

            try:
                prof_cgpa_float = float(prof_cgpa)

                if prof_cgpa_float >= req_cgpa:

                    checks.append({
                        "label": (
                            f"CGPA: {prof_cgpa_float} >= "
                            f"{req_cgpa}"
                        ),
                        "status": "pass"
                    })

                else:

                    checks.append({
                        "label": (
                            f"CGPA: {prof_cgpa_float} < "
                            f"{req_cgpa}"
                        ),
                        "status": "fail"
                    })

                    is_eligible = False
                    score -= 30

            except (TypeError, ValueError):

                checks.append({
                    "label": (
                        f"CGPA: Invalid profile value "
                        f"'{prof_cgpa}'"
                    ),
                    "status": "unknown"
                })

                has_unknowns = True
                score -= 10

        else:

            checks.append({
                "label": (
                    f"CGPA: Could not parse "
                    f"'{req_cgpa_str}'"
                ),
                "status": "unknown"
            })

            has_unknowns = True

    elif req_cgpa_str:

        checks.append({
            "label": "CGPA: Profile CGPA not set",
            "status": "unknown"
        })

        has_unknowns = True
        score -= 10

    else:

        checks.append({
            "label": "CGPA: No requirement specified",
            "status": "pass"
        })

    # =========================================================================
    # 4. ROLE RELEVANCE
    # =========================================================================

    role = opportunity.get("role") or ""

    is_cse = is_cse_branch(prof_branch)

    if role and is_cse:

        is_relevant = is_cse_relevant_role(role)

        if is_relevant:

            checks.append({
                "label": f"Role: '{role}' relevant to CSE",
                "status": "pass"
            })

        else:

            checks.append({
                "label": (
                    f"Role: '{role}' may not be relevant to CSE"
                ),
                "status": "unknown"
            })

            has_unknowns = True
            score -= 10

    elif role and not is_cse:

        checks.append({
            "label": (
                f"Role: '{role}' — branch-specific relevance "
                "not evaluated"
            ),
            "status": "unknown"
        })

        has_unknowns = True

    elif not role:

        checks.append({
            "label": "Role: Not specified",
            "status": "unknown"
        })

        has_unknowns = True

    # =========================================================================
    # FINAL STATUS
    # =========================================================================

    score = max(0, min(100, score))

    if not is_eligible:

        status = "NOT_ELIGIBLE"

    elif has_unknowns:

        status = "UNCLEAR"

    else:

        status = "ELIGIBLE"

    # =========================================================================
    # RETURN
    # =========================================================================

    return {
        "eligibility_status": status,
        "relevance_score": score,
        "checks": checks
    }