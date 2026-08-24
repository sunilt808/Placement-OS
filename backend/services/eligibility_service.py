"""
services/eligibility_service.py

Evaluates student eligibility for an opportunity.
"""

import re
from typing import Optional

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
# ROLE-FIRST CSE SIGNAL CLASSIFICATION
# -----------------------------------------------------------------------------
# Design rule (user requirement): do NOT gate on "CSE branch" mentions.
# Colleges often omit branches entirely. Priority:
#   1. CSE-family ROLE match (sde/fsd/qa/data analyst/...)  -> relevant
#   2. CSE-family BRANCH match (cse/ise/it/aiml)            -> relevant
#   3. Explicit non-CSE role blacklist                      -> quiet-log only
#   4. Anything else                                        -> UNKNOWN (still shown;
#      recall > precision — never silently hide)
# =============================================================================

CSE_FAMILY_BRANCHES = {
    "cse", "cs", "computer science",
    "ise", "is", "information science",
    "it", "information technology",
    "aiml", "ai ml", "artificial intelligence and machine learning",
    "ai and data science", "cse ai ml", "data science",
    "bca", "mca",
}

CSE_ROLE_DB = {
    # Software engineering core
    "software", "software engineer", "software developer",
    "software development engineer", "sde", "sde 1", "sde 2", "sdet",
    "developer", "programmer", "coder", "member of technical staff",
    "technical staff", "product engineer", "systems engineer",
    "system engineer", "platform engineer", "application developer",
    "application engineer",

    # Full stack / web
    "full stack", "fullstack", "fsd", "mern", "mean stack",
    "web developer", "web development", "web engineer",
    "frontend", "front end", "backend", "back end",
    "api developer", "rest api",

    # Language-specific dev
    "java developer", "python developer", "php developer",
    "node js developer", "react developer", "angular developer",
    "dotnet developer", "net developer", "sql developer", "pl sql",

    # Mobile
    "mobile developer", "android developer", "ios developer",
    "flutter developer", "react native developer", "app developer",

    # QA / Testing
    "qa", "qa engineer", "quality assurance", "quality analyst",
    "quality engineer", "test engineer", "testing engineer",
    "automation tester", "automation test engineer", "test analyst",
    "manual tester", "selenium", "performance engineer",
    "release engineer", "build engineer",

    # Data roles
    "data analyst", "data scientist", "data science", "data engineer",
    "analytics", "analytics consultant", "business intelligence",
    "bi analyst", "bi developer", "big data", "hadoop developer",
    "etl developer", "database administrator", "dba",

    # AI / ML
    "ai engineer", "artificial intelligence", "machine learning",
    "ml engineer", "deep learning", "nlp engineer", "computer vision",
    "generative ai", "genai", "prompt engineer", "ai ml engineer",

    # Cloud / DevOps / Infra
    "cloud engineer", "devops", "devops engineer", "site reliability",
    "sre", "aws engineer", "azure engineer", "cloud architect",
    "infrastructure engineer", "system administrator", "sysadmin",
    "network engineer",

    # Security
    "cybersecurity", "cyber security", "security analyst",
    "security engineer", "penetration tester", "soc analyst",

    # Enterprise / niche tech
    "salesforce developer", "sap abap", "mainframe developer",
    "embedded software", "game developer", "unity developer",
    "unreal developer", "blockchain developer",

    # Trainee / intern variants that imply coding
    "software trainee", "trainee software engineer",
    "it trainee", "graduate engineer trainee it",
    "software intern", "intern software", "digital technology trainee",
}

NON_CSE_ROLE_TERMS = {
    "mechanical", "mech design", "mechanical design", "civil",
    "civil site", "structural", "site engineer", "electrical",
    "electrician", "autocad", "catia", "solidworks", "hvac",
    "production supervisor", "quality control", "welder", "surveyor",
    "safety officer", "technician", "diploma trainee",
    "sales", "marketing", "business development", "telecalling",
    "hr executive", "human resources", "finance", "accounts",
    "accountant", "operations executive", "receptionist",
}


def _word_contains(text: str, term: str) -> bool:
    """Word-boundary substring match so 'cs' doesn't hit 'enterprise'."""
    if not text or not term:
        return False
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def classify_cse_signal(role: Optional[str], eligible_branches) -> dict:
    """
    Role-first relevance verdict for an opportunity.

    Returns:
        {
          "role_class": "CSE_BOTH" | "CSE_ROLE" | "CSE_BRANCH" | "NOT_CSE" | "UNKNOWN",
          "role_class_reason": human-readable explanation,
        }
    """
    role_norm = normalize_text(role or "")
    branches_norm = [normalize_text(b) for b in (eligible_branches or []) if b]

    role_hit = bool(role_norm) and any(
        _word_contains(role_norm, alias) for alias in CSE_ROLE_DB
    )
    role_blacklisted = bool(role_norm) and any(
        _word_contains(role_norm, term) for term in NON_CSE_ROLE_TERMS
    )
    branch_hit = any(
        any(_word_contains(branch, fam) for fam in CSE_FAMILY_BRANCHES)
        for branch in branches_norm
    )

    if role_hit and branch_hit:
        return {"role_class": "CSE_BOTH",
                "role_class_reason": f"Role '{role}' is a CSE role AND CSE-family branch mentioned"}
    if role_hit:
        return {"role_class": "CSE_ROLE",
                "role_class_reason": f"CSE-family role: '{role}'"}
    if branch_hit:
        return {"role_class": "CSE_BRANCH",
                "role_class_reason": f"No specific role, but CSE-family branches listed: {', '.join(str(b) for b in (eligible_branches or []))}"}
    if role_blacklisted:
        return {"role_class": "NOT_CSE",
                "role_class_reason": f"Non-CSE role: '{role}'"}
    if not role_norm and not branches_norm:
        return {"role_class": "UNKNOWN",
                "role_class_reason": "No role or branch information in message"}
    return {"role_class": "UNKNOWN",
            "role_class_reason": f"Could not classify role '{role}' / branches {eligible_branches}"}


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