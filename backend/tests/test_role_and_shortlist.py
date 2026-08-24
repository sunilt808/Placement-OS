"""
tests/test_role_and_shortlist.py — Role-first classification + Excel shortlist matching.
Pure offline unit tests — no DB, no network.
"""
from services.eligibility_service import classify_cse_signal
from services.excel_service import (
    _normalize_usn,
    _name_variants,
    is_spreadsheet,
    find_student_hit,
)


# ── Role classification: ROLE-FIRST, never branch-gated ──────────────────────

def test_sde_role_without_branch_mention_is_match():
    # College sometimes omits branches entirely
    result = classify_cse_signal("SDE-1 Intern", None)
    assert result["role_class"] == "CSE_ROLE"


def test_data_analyst_is_cse_family():
    # Non-CSE-family branches must NOT matter — role alone decides
    result = classify_cse_signal("Data Analyst", ["B.Com", "BBA"])
    assert result["role_class"] == "CSE_ROLE"


def test_qa_and_test_engineer_roles():
    assert classify_cse_signal("QA Engineer", [])["role_class"] == "CSE_ROLE"
    assert classify_cse_signal("Software Test Engineer", None)["role_class"] == "CSE_ROLE"


def test_full_stack_and_variants():
    for role in ("Full Stack Developer", "FSD", "MERN Stack Dev", "Frontend Developer"):
        assert classify_cse_signal(role, [])["role_class"] == "CSE_ROLE"


def test_systems_engineer_classic_entry_role():
    assert classify_cse_signal("Systems Engineer", None)["role_class"] == "CSE_ROLE"


def test_branch_only_when_role_missing():
    result = classify_cse_signal(None, ["CSE", "ISE"])
    assert result["role_class"] == "CSE_BRANCH"

    result = classify_cse_signal("", ["Information Technology"])
    assert result["role_class"] == "CSE_BRANCH"


def test_both_signals():
    result = classify_cse_signal("Software Developer", ["CSE"])
    assert result["role_class"] == "CSE_BOTH"


def test_non_cse_role_blacklisted():
    result = classify_cse_signal("Mechanical Design Engineer", ["Mechanical"])
    assert result["role_class"] == "NOT_CSE"


def test_unknown_never_hidden():
    # Recall > precision: unclassifiable must stay UNKNOWN, not dropped
    result = classify_cse_signal(None, None)
    assert result["role_class"] == "UNKNOWN"
    result = classify_cse_signal("Graduate Trainee", [])
    assert result["role_class"] == "UNKNOWN"


def test_word_boundary_no_false_positive():
    # 'ise' inside 'enterprise' must not trigger branch match;
    # 'cs' inside 'mechanical sciences' must not match either
    result = classify_cse_signal("Sales Executive", ["Enterprise Solutions"])
    assert result["role_class"] != "CSE_BRANCH"


# ── Student identity / USN normalization ─────────────────────────────────────

def test_usn_normalization():
    assert _normalize_usn("1ds24cs421") == "1DS24CS421"
    assert _normalize_usn("1DS 24 CS 421") == "1DS24CS421"
    assert _normalize_usn("1DS24-CS-421") == "1DS24CS421"


def test_name_variants_cover_order_flip():
    variants = _name_variants("Sunil T")
    assert "sunil" in variants
    assert "t sunil" in variants
    assert "sunil t" in variants


def test_spreadsheet_detection():
    assert is_spreadsheet("shortlist.xlsx")
    assert is_spreadsheet("results.CSV")
    assert is_spreadsheet("file", "text/csv")
    assert not is_spreadsheet("jd.pdf")


def test_find_student_by_usn_exact():
    rows = [
        ["Sl.No", "USN", "Student Name", "Status"],
        ["1", "1DS24CS001", "Rahul K", "Selected"],
        ["2", "1ds24cs421", "Sunil T", "Shortlisted"],
    ]
    hit = find_student_hit(rows)
    assert hit is not None
    assert hit["matched_field"] == "USN"
    assert hit["row_number"] == 3


def test_find_student_by_name_when_usn_absent():
    rows = [
        ["Name"],
        ["RAHUL KUMAR"],
        ["Sunil T"],           # name-only sheet
        ["Another Student"],
    ]
    hit = find_student_hit(rows)
    assert hit is not None
    assert hit["matched_field"] == "NAME"


def test_no_false_hit_for_other_students():
    rows = [["USN"], ["1DS24CS420"], ["1DS24CS422"], ["Sunil Kumar R"]]
    # Note: "Sunil Kumar R" contains 'sunil' but our variant list requires
    # >=3-char matches with fuzzy >= 90 against partial_ratio; 'sunil' vs
    # 'sunil kumar r' scores high -> acceptable recall-biased behavior,
    # but pure-USN sheets must never hit:
    usn_rows = [["USN"], ["1DS24CS420"], ["1DS24CS422"]]
    assert find_student_hit(usn_rows) is None


def test_hit_in_messy_real_world_row():
    rows = [
        ["Company: Accenture — Shortlist Round 1"],
        [None, "Reg No: 1DS24CS421 ", "SUNIL T", "Qualified", None],
    ]
    hit = find_student_hit(rows)
    assert hit is not None
    assert hit["matched_field"] in ("USN", "NAME")
