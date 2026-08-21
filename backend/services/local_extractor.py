"""
services/local_extractor.py — Deterministic local rule-based, regex & NLP extractor.

Extracts structured placement details completely offline, fast, and reliably
without requiring any external API (Gemini).

CSE Intelligence:
  - Computes cse_relevance_score (0–100) based on role, branch, and JD tech keywords
  - Flags non-CSE roles (Mechanical, Civil, Robotics, etc.)
  - Extracts jd_cse_signals — matched CSE-relevant tech keywords from JD
"""
import re
from datetime import datetime, timedelta
from typing import Optional, List
import pytz

from models.opportunity import AIExtraction, OpportunityCategory

IST = pytz.timezone("Asia/Kolkata")

# Local placement keyword signals
STRONG_PLACEMENT_KEYWORDS = {
    "hiring", "recruitment", "campus hiring", "campus recruitment", "placement", 
    "software engineer", "sde", "developer", "internship", "job opening", 
    "job opportunity", "walk-in", "apply now", "registration", "job description", 
    "jd", "eligible candidates", "off campus", "campus drive", "ctc", "lpa"
}

ELIGIBILITY_KEYWORDS = {
    "cse", "ise", "ece", "it", "branch", "batch", "graduating", "cgpa", "backlog", 
    "passout", "eligible"
}

APPLICATION_KEYWORDS = {
    "apply", "registration link", "application deadline", "last date", 
    "assessment", "interview", "test date", "google form", "supersets"
}

# ── CSE Intelligence Data ────────────────────────────────────────────────────

# Roles that are strongly CSE-relevant
CSE_ROLE_KEYWORDS = {
    # Software Engineering
    "software engineer", "software developer", "sde", "swe",
    "full stack developer", "fullstack developer", "full-stack developer",
    "backend developer", "backend engineer", "frontend developer", "frontend engineer",
    "web developer", "application developer", "app developer",
    # Data & AI
    "data scientist", "data analyst", "data engineer", "ml engineer",
    "machine learning engineer", "ai engineer", "ai/ml", "deep learning",
    "nlp engineer", "computer vision",
    # DevOps & Cloud
    "devops engineer", "cloud engineer", "site reliability engineer", "sre",
    "platform engineer", "infrastructure engineer",
    # QA & Testing
    "qa engineer", "quality assurance", "sdet", "test engineer", "automation engineer",
    # Product & Design
    "product engineer", "solutions engineer", "technical consultant",
    # Security
    "security engineer", "cybersecurity", "information security",
    # Systems
    "systems engineer", "embedded software", "firmware engineer",
    # General tech
    "technology analyst", "it analyst", "technical associate",
    "associate software", "trainee engineer", "graduate engineer trainee",
    "get", "set", "analyst", "consultant",
}

# Roles that are explicitly NOT CSE
NON_CSE_ROLE_KEYWORDS = {
    "mechanical engineer", "civil engineer", "electrical engineer",
    "chemical engineer", "automobile engineer", "robotics engineer",
    "structural engineer", "piping engineer", "hvac engineer",
    "production engineer", "manufacturing engineer", "process engineer",
    "petroleum engineer", "mining engineer", "textile engineer",
    "agricultural engineer", "biomedical engineer",
    "design engineer",  # Usually mechanical design
    "core mechanical", "core civil", "core electrical",
}

# Branches that are CSE-adjacent
CSE_BRANCHES = {"CSE", "ISE", "IT", "AIML", "AIDS", "AI", "MCA", "BCA", "CS"}

# Branches that are NOT CSE
NON_CSE_BRANCHES = {"MECH", "CIVIL", "EEE", "ECE", "CHEMICAL", "AUTOMOBILE", "ROBOTICS",
                     "BIOTECH", "MINING", "TEXTILE", "AGRICULTURAL", "AERONAUTICAL"}

# CSE tech keywords — signals that the JD involves CSE-relevant work
CSE_TECH_KEYWORDS = {
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "go lang",
    "rust", "kotlin", "swift", "ruby", "php", "scala", "r programming",
    # Web
    "react", "angular", "vue", "node.js", "nodejs", "express", "django", "flask",
    "spring boot", "spring", "rest api", "restful", "graphql", "html", "css",
    # Databases
    "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "database", "nosql", "dynamodb", "cassandra", "oracle db",
    # Cloud & DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
    "ci/cd", "jenkins", "terraform", "ansible", "microservices",
    # Data & AI
    "machine learning", "deep learning", "artificial intelligence", "nlp",
    "data structures", "algorithms", "dsa", "pandas", "numpy", "tensorflow",
    "pytorch", "scikit", "data pipeline", "etl", "hadoop", "spark",
    # Tools
    "git", "github", "linux", "unix", "api", "apis", "sdk",
    "agile", "scrum", "jira",
    # Concepts
    "object oriented", "oop", "design patterns", "system design",
    "data structures and algorithms", "operating systems",
    "computer networks", "dbms", "oops",
}

# Non-CSE tech keywords — signals that the JD is for non-CSE roles
NON_CSE_TECH_KEYWORDS = {
    "autocad", "solidworks", "catia", "ansys", "matlab", "staad pro",
    "etabs", "revit", "primavera", "thermodynamics", "fluid mechanics",
    "strength of materials", "surveying", "plc", "scada",
    "mechanical drawing", "welding", "cnc", "lathe", "casting",
    "concrete", "rcc", "structural analysis", "geotechnical",
}


def compute_local_relevance(text: str) -> float:
    """Calculate a local placement relevance score (0.0 to 1.0)."""
    if not text:
        return 0.0
    
    text_lower = text.lower()
    
    strong_hits = sum(1 for kw in STRONG_PLACEMENT_KEYWORDS if kw in text_lower)
    elig_hits = sum(1 for kw in ELIGIBILITY_KEYWORDS if kw in text_lower)
    app_hits = sum(1 for kw in APPLICATION_KEYWORDS if kw in text_lower)
    
    raw_score = (strong_hits * 0.25) + (elig_hits * 0.15) + (app_hits * 0.15)
    return min(1.0, raw_score)


def compute_cse_relevance(text: str, role: Optional[str], branches: Optional[List[str]]) -> dict:
    """
    Compute CSE relevance score (0–100) based on:
    1. Role keyword matching (40 points max)
    2. Branch mentions (30 points max)
    3. JD technical keywords - CSE vs non-CSE signals (30 points max)
    
    Returns: { score: int, is_relevant: bool, signals: list[str] }
    """
    text_lower = text.lower()
    score = 0
    signals = []

    # ── 1. Role relevance (40 points) ────────────────────────────────────────
    role_lower = (role or "").lower().strip()

    # Check for explicitly non-CSE roles first
    for nkw in NON_CSE_ROLE_KEYWORDS:
        if nkw in role_lower or nkw in text_lower[:500]:
            score -= 30
            signals.append(f"Non-CSE role: {nkw}")
            break
    else:
        # Check for CSE roles
        for ckw in CSE_ROLE_KEYWORDS:
            if ckw in role_lower:
                score += 40
                signals.append(f"CSE role: {ckw}")
                break
        else:
            # Partial match — role not clearly CSE or non-CSE
            score += 20  # neutral baseline

    # ── 2. Branch relevance (30 points) ──────────────────────────────────────
    if branches:
        branch_set = {b.upper() for b in branches}
        cse_overlap = branch_set & CSE_BRANCHES
        non_cse_overlap = branch_set & NON_CSE_BRANCHES

        if "ALL" in branch_set:
            score += 15  # All branches includes CSE but not targeted
            signals.append("All branches eligible")
        elif cse_overlap and not non_cse_overlap:
            score += 40
            signals.append(f"CSE exclusively targeted: {', '.join(sorted(cse_overlap))}")
        elif cse_overlap:
            score += 30
            signals.append(f"CSE branches: {', '.join(sorted(cse_overlap))}")
        elif non_cse_overlap and not cse_overlap:
            score -= 20
            signals.append(f"Non-CSE only branches: {', '.join(sorted(non_cse_overlap))}")
    else:
        score += 10  # No branch info — assume possible

    # ── 3. JD technical keyword analysis (30 points) ─────────────────────────
    cse_tech_hits = []
    for kw in CSE_TECH_KEYWORDS:
        # Use word boundary for short keywords, substring for longer ones
        if len(kw) <= 3:
            if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                cse_tech_hits.append(kw)
        else:
            if kw in text_lower:
                cse_tech_hits.append(kw)

    non_cse_tech_hits = []
    for kw in NON_CSE_TECH_KEYWORDS:
        if kw in text_lower:
            non_cse_tech_hits.append(kw)

    if cse_tech_hits:
        tech_score = min(30, len(cse_tech_hits) * 5)
        score += tech_score
        signals.extend(cse_tech_hits[:10])  # cap signals list

    if non_cse_tech_hits:
        score -= min(20, len(non_cse_tech_hits) * 5)
        signals.append(f"Non-CSE tech: {', '.join(non_cse_tech_hits[:5])}")

    # Clamp to 0–100
    final_score = max(0, min(100, score))
    is_relevant = final_score >= 50

    return {
        "score": final_score,
        "is_relevant": is_relevant,
        "signals": signals,
    }


def extract_registration_link(text: str) -> Optional[str]:
    """Extract registration / application URL."""
    match = re.search(r"https?://[^\s>\"\']+", text)
    return match.group(0) if match else None


def extract_ctc(text: str) -> Optional[str]:
    """Extract salary / CTC details."""
    match = re.search(
        r"(\b(?:₹|rs\.?|inr)?\s*\d+(?:\.\d+)?\s*(?:-|to)?\s*\d*(?:\.\d+)?\s*(?:lpa|lacs|lakhs|ctc|per annum|fixed)\b)",
        text,
        re.IGNORECASE
    )
    return match.group(0).strip() if match else None


def extract_cgpa(text: str) -> Optional[str]:
    """Extract CGPA cutoff requirement."""
    match = re.search(
        r"\b(?:cgpa|cutoff|criteria|minimum)?\s*:?\s*(\d\.\d+|\d(?:\.0+)?)\s*(?:\+|and above|cgpa)?\b",
        text,
        re.IGNORECASE
    )
    if match:
        val = match.group(1)
        if 5.0 <= float(val) <= 10.0:
            return f"{val}+ CGPA"
    return None


def extract_batch(text: str) -> Optional[str]:
    """Extract eligible graduation batch."""
    match = re.search(
        r"\b(20\d{2}\s*[-–\u2013]\s*20?\d{2}|20\d{2}\s*batch|20\d{2}\s*passout|20\d{2}\s*graduat\w+)\b",
        text,
        re.IGNORECASE
    )
    return match.group(0).strip() if match else None


def extract_branches(text: str) -> Optional[List[str]]:
    """Extract eligible engineering branches — comprehensive list."""
    branches = []
    text_upper = text.upper()
    
    known = [
        "CSE", "ISE", "ECE", "EEE", "IT", "MECH", "CIVIL",
        "AIDS", "AIML", "MCA", "BCA", "ROBOTICS",
        "CHEMICAL", "BIOTECH", "AUTOMOBILE", "AERONAUTICAL",
    ]
    for b in known:
        if re.search(rf"\b{b}\b", text_upper):
            branches.append(b)
            
    if "ALL BRANCHES" in text_upper or "ALL ENGINEERING" in text_upper:
        return ["ALL"]
        
    return branches if branches else None


def extract_company_local(text: str) -> Optional[str]:
    """Extract company name using regex patterns."""
    patterns = [
        r"(?:company\s*name|company)\s*:?\s*([A-Za-z0-9\s.&'-]{2,30})",
        r"\b([A-Z][A-Za-z0-9\s.&'-]{1,25})\s+(?:is hiring|campus drive|recruitment drive|hiring drive|campus recruitment)\b",
        r"(?:hiring|campus drive|recruitment drive)\s+(?:at|by|for)\s+([A-Z][A-Za-z0-9\s.&'-]{1,25})",
    ]
    for p in patterns:
        match = re.search(p, text, re.MULTILINE)
        if match:
            c = match.group(1).strip()
            # Clean up common trailing words
            c = re.sub(r"\b(campus|drive|recruitment|hiring|online|test|interview|for|is)\b.*$", "", c, flags=re.IGNORECASE).strip()
            if len(c) >= 2 and len(c) <= 35:
                return c
    return None


def extract_role_local(text: str) -> Optional[str]:
    """Extract job role / designation locally — enhanced with 30+ role types."""
    # Pattern-based extraction first
    patterns = [
        r"(?:roles?|designations?|positions?|profiles?|job titles?)\s*:?\s*(?:[\n\r]*[•*-]\s*)?([A-Za-z0-9\s.&'-]{2,40})",
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if match:
            r = match.group(1).strip()
            if len(r) >= 2 and len(r) <= 45:
                return r
                
    # Fallback: scan for known roles (expanded list)
    roles = [
        "Software Development Engineer", "Software Engineer",
        "Full Stack Developer", "Backend Developer", "Frontend Developer",
        "Data Scientist", "Data Analyst", "Data Engineer",
        "ML Engineer", "Machine Learning Engineer", "AI Engineer",
        "DevOps Engineer", "Cloud Engineer", "SRE",
        "QA Engineer", "SDET", "Test Engineer", "Automation Engineer",
        "Product Engineer", "Solutions Engineer", "Technical Consultant",
        "Security Engineer", "Cybersecurity Analyst",
        "Systems Engineer", "Embedded Software Engineer",
        "Technology Analyst", "IT Analyst", "Technical Associate",
        "Associate Software Engineer", "Trainee Engineer",
        "Graduate Engineer Trainee", "Management Trainee",
        "SDE", "Analyst", "Consultant", "Developer",
        # Non-CSE roles (still detect them for proper tagging)
        "Mechanical Engineer", "Civil Engineer", "Electrical Engineer",
        "Robotics Engineer", "Process Engineer",
    ]
    for r in roles:
        if re.search(rf"\b{re.escape(r)}\b", text, re.IGNORECASE):
            return r
    return None


def extract_skills(text: str) -> Optional[List[str]]:
    """Extract required technical skills from JD text."""
    text_lower = text.lower()
    found = []
    
    # Check for CSE tech keywords that appear in the text
    skill_names = {
        "python": "Python", "java": "Java", "javascript": "JavaScript",
        "typescript": "TypeScript", "c++": "C++", "c#": "C#",
        "golang": "Go", "rust": "Rust", "kotlin": "Kotlin",
        "react": "React", "angular": "Angular", "vue": "Vue.js",
        "node.js": "Node.js", "nodejs": "Node.js",
        "django": "Django", "flask": "Flask", "spring boot": "Spring Boot",
        "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL",
        "mongodb": "MongoDB", "redis": "Redis",
        "aws": "AWS", "azure": "Azure", "gcp": "GCP",
        "docker": "Docker", "kubernetes": "Kubernetes",
        "machine learning": "Machine Learning", "deep learning": "Deep Learning",
        "data structures": "DSA", "algorithms": "Algorithms",
        "git": "Git", "linux": "Linux",
        "rest api": "REST API", "graphql": "GraphQL",
        "html": "HTML", "css": "CSS",
    }
    
    for kw, display_name in skill_names.items():
        if len(kw) <= 3:
            if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                if display_name not in found:
                    found.append(display_name)
        else:
            if kw in text_lower:
                if display_name not in found:
                    found.append(display_name)
    
    return found[:15] if found else None  # Cap at 15 skills


def extract_deadline_local(text: str, message_date: datetime) -> Optional[str]:
    """Extract and resolve relative or absolute application deadlines."""
    text_lower = text.lower()
    
    # 1. Look for explicit date strings like 24th Aug, 24/08/2026
    date_match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{4})?", text_lower)
    if date_match:
        day = int(date_match.group(1))
        month_str = date_match.group(2)[:3]
        year = int(date_match.group(3)) if date_match.group(3) else message_date.year
        months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        month = months.index(month_str) + 1
        try:
            dl_dt = datetime(year, month, day, 17, 0, 0, tzinfo=IST)
            return dl_dt.isoformat()
        except Exception:
            pass
            
    # 2. Look for relative terms ("tomorrow", "today")
    if "tomorrow" in text_lower:
        dl_dt = (message_date + timedelta(days=1)).replace(hour=17, minute=0, second=0)
        return dl_dt.isoformat()
    elif "today" in text_lower or "by eod" in text_lower:
        dl_dt = message_date.replace(hour=23, minute=59, second=0)
        return dl_dt.isoformat()
        
    return None


def extract_locally(text: str, message_date: datetime) -> AIExtraction:
    """
    Extract structured placement data using ONLY local rules, regex, and NLP.
    Never fails, never throws API errors, works completely offline.
    
    Now includes CSE intelligence: cse_relevance_score, is_cse_relevant, jd_cse_signals.
    """
    relevance_score = compute_local_relevance(text)
    is_placement = relevance_score >= 0.25
    
    company = extract_company_local(text)
    role = extract_role_local(text)
    ctc = extract_ctc(text)
    cgpa = extract_cgpa(text)
    batch = extract_batch(text)
    branches = extract_branches(text)
    link = extract_registration_link(text)
    deadline = extract_deadline_local(text, message_date)
    skills = extract_skills(text)
    
    # ── CSE Intelligence ─────────────────────────────────────────────────────
    cse_result = compute_cse_relevance(text, role, branches)

    category = OpportunityCategory.PLACEMENT_OPPORTUNITY if is_placement else OpportunityCategory.IRRELEVANT
    if "test" in text.lower() or "assessment" in text.lower():
        category = OpportunityCategory.ASSESSMENT
    elif "interview" in text.lower():
        category = OpportunityCategory.INTERVIEW
    elif "shortlist" in text.lower():
        category = OpportunityCategory.SHORTLIST

    summary_clean = text.strip().split("\n")[0][:150]
    
    return AIExtraction(
        category=category,
        is_placement_related=is_placement,
        company=company,
        role=role,
        ctc=ctc,
        location=None,
        eligible_branches=branches,
        eligible_batch=batch,
        cgpa_requirement=cgpa,
        backlog_requirement=None,
        experience_requirement=None,
        deadline=deadline,
        assessment_date=None,
        interview_date=None,
        registration_link=link,
        required_skills=skills,
        action_required=is_placement,
        summary=summary_clean if summary_clean else "Local extracted opportunity",
        confidence=min(0.85, max(0.40, relevance_score)),
        # ── CSE Intelligence fields ──────────────────────────────────────────
        cse_relevance_score=cse_result["score"],
        is_cse_relevant=cse_result["is_relevant"],
        jd_cse_signals=cse_result["signals"] if cse_result["signals"] else None,
    )
