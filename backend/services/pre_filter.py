"""
services/pre_filter.py — Cheap keyword-based pre-filter.

ONLY used for the historical bulk import where volume makes cost/latency
a real concern.  DO NOT use as a discard gate on the live message path.
On the live path, all messages go straight to Gemini.
"""

PLACEMENT_KEYWORDS = {
    # Company / hiring signals
    "placement", "hiring", "drive", "company", "ctc", "lpa",
    "package", "offer", "opportunity", "recruit", "recruitment",
    # Action signals
    "register", "registration", "apply", "application", "eligible",
    "eligibility", "shortlist", "shortlisted",
    # Process signals
    "deadline", "assessment", "aptitude", "interview", "test",
    "coding", "gcet", "amcat", "elitmus", "hackathon",
    # Job types
    "job", "internship", "fresher", "campus", "off-campus",
    "full-time", "fulltime", "part-time",
    # Common company terms
    "software", "engineer", "developer", "analyst", "associate",
    "consultant", "trainee",
}


def passes_pre_filter(text: str) -> bool:
    """
    Returns True if the message likely contains placement-related content.
    Uses lowercase keyword matching — fast and free.
    Only a pre-filter; final classification is always done by Gemini.
    """
    if not text or not text.strip():
        return False

    lower = text.lower()
    for keyword in PLACEMENT_KEYWORDS:
        if keyword in lower:
            return True
    return False


def keyword_highlights(text: str) -> list[str]:
    """Returns matched keywords — useful for debugging/logging."""
    lower = text.lower()
    return [kw for kw in PLACEMENT_KEYWORDS if kw in lower]
