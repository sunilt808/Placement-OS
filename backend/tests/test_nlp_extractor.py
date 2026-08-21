from datetime import datetime
from pathlib import Path
import sys

# Backend modules use the project-root import style.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.nlp_extractor import extract_company_nlp, extract_with_nlp


def test_extracts_unknown_company_from_a_label():
    text = "Company: Blue Orbit Labs\nRole: Data Analyst\nCTC: 7 LPA"
    assert extract_company_nlp(text) == "Blue Orbit Labs"


def test_known_company_requires_placement_context():
    text = "Google Forms link is attached. Company: Blue Orbit Labs\nRole: Data Analyst"
    assert extract_company_nlp(text) == "Blue Orbit Labs"


def test_known_company_is_preserved_when_it_is_the_hirer():
    assert extract_company_nlp("Microsoft is hiring Software Engineers. Apply now.") == "Microsoft"


def test_does_not_turn_generic_announcement_into_a_company():
    assert extract_company_nlp("Dear students, please register for the assessment tomorrow.") is None


def test_local_extraction_builds_a_usable_opportunity_without_gemini():
    result = extract_with_nlp(
        "Company: Acme Technologies Pvt Ltd\nRole: Software Engineer\nCTC: 8 LPA\nApply by 30 Aug 2026",
        datetime(2026, 8, 20),
    )
    assert result.company == "Acme Technologies Pvt Ltd"
    assert result.role == "Software Engineer"
    assert result.is_placement_related is True
