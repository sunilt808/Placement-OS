"""
services/nlp_extractor.py — Advanced NLP-powered local extraction engine.

Uses:
  - spaCy NER for company / person / org recognition
  - dateparser for robust date resolution (relative + absolute)
  - rapidfuzz for smart deduplication
  - Regex + pattern matching for structured fields
  - ZERO dependency on Gemini / any external API

This replaces Gemini as the primary extractor. Gemini only runs as
an optional enhancement when quota is available.
"""
import re
from datetime import datetime, timedelta
from typing import Optional, List
import pytz

from models.opportunity import AIExtraction, OpportunityCategory

IST = pytz.timezone("Asia/Kolkata")

# ── Try loading optional NLP libraries ──────────────────────────────────────────
_nlp = None
_dateparser_available = False

try:
    import spacy
    try:
        _nlp = spacy.load("en_core_web_sm")
        print("[NLP] spaCy en_core_web_sm loaded OK")
    except OSError:
        print("[NLP] spaCy model not found — run: python -m spacy download en_core_web_sm")
except ImportError:
    print("[NLP] spaCy not installed — using regex-only extraction")

try:
    import dateparser
    _dateparser_available = True
    print("[NLP] dateparser loaded OK")
except ImportError:
    print("[NLP] dateparser not installed — using regex date extraction")


# ── KNOWN COMPANIES corpus ────────────────────────────────────────────────────
# This list is expanded for Indian placement context
KNOWN_COMPANIES = {
    # Tech giants
    "google", "microsoft", "amazon", "meta", "apple", "netflix", "adobe",
    "salesforce", "oracle", "ibm", "sap", "cisco", "intel", "nvidia",
    # Indian tech leaders
    "tcs", "infosys", "wipro", "hcl", "hcltech", "tech mahindra", "ltimindtree",
    "mphasis", "hexaware", "mindtree", "l&t technology", "persistent systems",
    "coforge", "birlasoft", "mastech", "kpit", "zensar", "cyient",
    # Startups & mid-tier
    "razorpay", "swiggy", "zomato", "ola", "paytm", "byju", "cred",
    "meesho", "freshworks", "zoho", "chargebee", "postman", "hasura",
    "browserstack", "setu", "juspay", "clevertap", "sprinklr",
    # Finance
    "goldman sachs", "jpmorgan", "morgan stanley", "deutsche bank", "ubs",
    "citibank", "hdfc", "icici", "axis bank", "kotak", "bajaj finserv",
    # Consulting
    "deloitte", "accenture", "capgemini", "cognizant", "epam", "genpact",
    "ey", "pwc", "kpmg", "mckinsey", "bain", "bcg",
    # Other frequent
    "jll", "jll technology", "keyence", "stonex", "acies global", "alteroffice",
    "rocked", "rocked", "siemens", "siemens healthcare", "bosch", "honeywell",
    "qualcomm", "ericsson", "nokia", "philips", "ntt data", "igate",
    "toyota", "tesla", "ford", "bmw", "airbus", "aerospace",
    "upgrad", "unacademy", "byjus", "great learning",
    "walmart", "target", "jp morgan", "bank of america", "wells fargo",
    "american express", "mastercard", "visa",
    "flipkart", "myntra", "nykaa", "bigbasket", "dunzo",
    "altimetrik", "sigmoid", "quantiphi", "mu sigma", "fractal analytics",
    "axtria", "analytixlabs", "latentview", "datamatics",
}

# Known false positives -- words that look like companies but aren't
COMPANY_BLACKLIST = {
    "the company", "our company", "a company", "this company",
    "students", "student", "candidates", "candidate",
    "department", "placement", "college", "university", "institute",
    "tomorrow", "today", "online", "offline", "test", "assessment",
    "round", "interview", "drive", "campus", "recruitment",
    "overview", "introduction", "note", "announcement",
    "update", "information", "details", "attached", "follow",
    "dear", "hi", "hello", "please", "kindly", "ensure",
    "important", "reminder", "notice",
    # False positives seen in practice
    "internships", "internship", "telegram", "whatsapp",
    "pre-placement talk", "pre placement talk", "superset",
    "naukri", "linkedin", "indeed", "glassdoor",
    "google", "google form", "google forms",  # unless it's google hiring
    "form", "link", "register", "apply", "application",
    "complete", "completed", "aerospace",  # too generic
    "it solutions", "technologies", "services",  # suffix only, not full name
    "& complete", "and complete",
    "non-cse", "robotics engineering",
    "associate trainee", "graduate trainee",  # these are roles, not companies
    "software engineer", "data analyst", "intern",
}

# Patterns that signal company announcement
COMPANY_INTRO_PATTERNS = [
    r"(?:company|firm|organization|organisation)\s*[:\-]\s*([A-Z][A-Za-z0-9\s&.,'-]{1,35})",
    r"([A-Z][A-Za-z0-9\s&.,'-]{2,30})\s+(?:is\s+)?(?:hiring|recruiting|offering|looking|inviting|seeking)",
    r"(?:hiring|placement|drive|recruitment)\s+(?:at|by|with|for|from)\s+([A-Z][A-Za-z0-9\s&.,'-]{2,30})",
    r"([A-Z][A-Za-z0-9\s&.,'-]{2,30})\s+(?:campus\s+)?(?:placement|drive|recruitment|hiring\s+drive)",
    r"(?:joining|joining\s+us|partner)\s+at\s+([A-Z][A-Za-z0-9\s&.,'-]{2,30})",
    r"job\s+at\s+([A-Z][A-Za-z0-9\s&.,'-]{2,30})",
    r"opportunity\s+(?:at|with|from|by)\s+([A-Z][A-Za-z0-9\s&.,'-]{2,30})",
    r"internship\s+(?:at|with|from|by|in)\s+([A-Z][A-Za-z0-9\s&.,'-]{2,30})",
    r"([A-Z][A-Za-z0-9\s&.,'-]{2,30})\s+(?:has|have|had)\s+(?:announced|scheduled|opened|started)",
    r"^([A-Z][A-Za-z0-9\s&.,'-]{2,30})\s*[-:]\s*(?:job|role|position|opening|opportunity|intern)",
    r"working\s+(?:at|with|for)\s+([A-Z][A-Za-z0-9\s&.,'-]{2,30})",
    r"(?:register|apply)\s+for\s+([A-Z][A-Za-z0-9\s&.,'-]{2,30})",
]


def _is_valid_company_name(name: str) -> bool:
    """Validate that extracted string is actually a company name."""
    if not name or len(name) < 2:
        return False
    name_lower = name.lower().strip()
    
    # Reject if it starts with lowercase (sentences, not company names)
    if name[0].islower():
        return False
    
    # Reject if it's a blacklisted word/phrase
    if name_lower in COMPANY_BLACKLIST:
        return False
    for bl in COMPANY_BLACKLIST:
        if name_lower.startswith(bl + " ") or name_lower.endswith(" " + bl):
            return False
    
    # Reject if it contains sentence-ending patterns (it's a description, not a name)
    if re.search(r'\.\s+[A-Z]', name):
        return False
    
    # Reject if longer than 50 chars
    if len(name) > 50:
        return False
    
    # Reject if it's purely a verb phrase
    verb_starts = ["is", "has", "was", "are", "were", "will", "would", "should"]
    if any(name_lower.startswith(v + " ") for v in verb_starts):
        return False
    
    return True


def _clean_company_name(name: str) -> str:
    """Clean up extracted company name."""
    # Strip trailing noise words
    name = re.sub(
        r'\s+\b(campus|drive|recruitment|hiring|online|test|interview|for|is|at|the|a|an|in|on|of|and)\b.*$',
        '', name, flags=re.IGNORECASE
    ).strip()
    # Strip leading/trailing punctuation
    name = name.strip('.,;:!? -')
    return name


def extract_company_nlp(text: str) -> Optional[str]:
    """
    Multi-strategy company name extractor:
    1. Known companies corpus (most reliable)  
    2. Regex pattern matching
    3. spaCy NER (ORG entities)
    """
    # Strategy 1: Known companies corpus — highest confidence
    text_lower = text.lower()
    best_match = None
    best_len = 0
    
    for known in KNOWN_COMPANIES:
        # Use word-boundary matching for multi-word company names
        pattern = rf'\b{re.escape(known)}\b'
        if re.search(pattern, text_lower):
            if len(known) > best_len:
                best_match = known
                best_len = len(known)
    
    if best_match:
        # Restore original casing from text if possible
        pattern = rf'\b({re.escape(best_match)})\b'
        match = re.search(pattern, text_lower)
        if match:
            start, end = match.span()
            return text[start:end]
    
    # Strategy 2: Regex patterns targeting company introduction phrases
    for pattern in COMPANY_INTRO_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            candidate = match.group(1).strip()
            candidate = _clean_company_name(candidate)
            if _is_valid_company_name(candidate) and len(candidate) >= 2:
                return candidate
    
    # Strategy 3: spaCy NER
    if _nlp:
        try:
            doc = _nlp(text[:1000])  # Process first 1000 chars
            orgs = [
                ent.text.strip() 
                for ent in doc.ents 
                if ent.label_ == "ORG"
            ]
            for org in orgs:
                cleaned = _clean_company_name(org)
                if _is_valid_company_name(cleaned):
                    return cleaned
        except Exception as e:
            print(f"[NLP] spaCy extraction failed: {e}")
    
    return None


def extract_role_nlp(text: str) -> Optional[str]:
    """
    Enhanced role extractor with broader pattern matching.
    """
    # Pattern 1: Explicitly labeled role/position
    labeled_patterns = [
        r"(?:role|designation|position|profile|job\s+title)\s*[:\-]\s*([A-Za-z][A-Za-z0-9\s&()/-]{2,50})",
        r"(?:hiring\s+for|opening\s+for|position\s+of|role\s+of)\s+([A-Za-z][A-Za-z0-9\s&()/-]{2,50})",
        r"(?:vacancy|vacancies)\s+(?:for|in)\s+([A-Za-z][A-Za-z0-9\s&()/-]{2,50})",
    ]
    for p in labeled_patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            role = m.group(1).strip().rstrip('.,;')
            if 2 <= len(role) <= 60:
                return role
    
    # Pattern 2: Scan for known role keywords
    KNOWN_ROLES = [
        # Software Engineering
        "Software Development Engineer", "Software Engineer", "Software Developer",
        "SDE-1", "SDE-2", "SDE 1", "SDE 2",
        "Full Stack Developer", "Backend Developer", "Frontend Developer",
        "Mobile Developer", "Android Developer", "iOS Developer",
        "Data Scientist", "Data Analyst", "Data Engineer",
        "ML Engineer", "Machine Learning Engineer", "AI Engineer",
        "NLP Engineer", "Computer Vision Engineer",
        "DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer",
        "Platform Engineer", "Infrastructure Engineer",
        "QA Engineer", "SDET", "Test Engineer", "Automation Engineer",
        "Product Engineer", "Solutions Engineer", "Technical Consultant",
        "Security Engineer", "Cybersecurity Analyst",
        "Systems Engineer", "Embedded Software Engineer",
        "Technology Analyst", "IT Analyst", "Technical Associate",
        "Associate Software Engineer", "Trainee Engineer",
        "Graduate Engineer Trainee", "Management Trainee",
        "Technical Program Manager", "Technical Lead",
        # Roles that commonly appear in Indian placements
        "Software Trainee", "Associate Trainee", "Systems Analyst",
        "Application Developer", "Applications Engineer",
        "Analyst", "Consultant", "Developer",
        "Intern", "Engineering Intern", "Software Intern",
        "Graduate Intern", "Technology Intern",
        # Non-CSE (tag them too for accuracy)
        "Mechanical Engineer", "Civil Engineer", "Electrical Engineer",
        "Robotics Engineer", "Process Engineer", "Design Engineer",
        # Finance tech
        "Quantitative Analyst", "Financial Analyst",
        "Associate Engineer", "Graduate Trainee",
    ]
    for role in KNOWN_ROLES:
        if re.search(rf'\b{re.escape(role)}\b', text, re.IGNORECASE):
            return role
    
    # Pattern 3: spaCy for role context
    if _nlp:
        try:
            doc = _nlp(text[:500])
            # Look for noun phrases after "as a", "for the position of"
            for chunk in doc.noun_chunks:
                if any(tok.text.lower() in {"engineer", "analyst", "developer", "intern", "trainee"} 
                       for tok in chunk):
                    role_text = chunk.text.strip()
                    if 3 <= len(role_text) <= 60:
                        return role_text
        except Exception:
            pass
    
    return None


def extract_deadline_nlp(text: str, message_date: datetime) -> Optional[str]:
    """
    Multi-strategy deadline extractor.
    1. dateparser for natural language dates
    2. Regex for common date formats
    3. Relative terms (tomorrow, today, EOD)
    """
    text_lower = text.lower()
    anchor = message_date.replace(tzinfo=None)
    
    # Look for deadline context clues
    deadline_contexts = [
        r"(?:deadline|last\s+date|apply\s+by|register\s+by|closing\s+date|due\s+(?:date|by)|fill\s+by)\s*[:\-]?\s*([^\n.]{5,40})",
        r"(?:before|by)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s*\d{4})",
        r"(?:deadline|last\s+date)\s+is\s+([^\n.]{5,35})",
        r"(?:by|before)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]
    
    # Strategy 1: dateparser with context
    if _dateparser_available:
        for pattern in deadline_contexts:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                date_str = m.group(1).strip()
                try:
                    parsed = dateparser.parse(
                        date_str,
                        settings={
                            'RELATIVE_BASE': anchor,
                            'PREFER_DATES_FROM': 'future',
                            'TIMEZONE': 'Asia/Kolkata',
                            'TO_TIMEZONE': 'Asia/Kolkata',
                            'RETURN_AS_TIMEZONE_AWARE': True,
                        }
                    )
                    if parsed:
                        return parsed.isoformat()
                except Exception:
                    pass
    
    # Strategy 2: Direct regex date matching
    date_patterns = [
        # DD Month YYYY or DD Month
        r"(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
        r"(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{4})",
        r"(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*(?:\s*,?\s*(\d{4}))?",
        # DD/MM/YYYY
        r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})",
    ]
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10,
        "november": 11, "december": 12
    }
    
    for pat in date_patterns:
        m = re.search(pat, text_lower)
        if m:
            try:
                groups = m.groups()
                if len(groups) >= 2:
                    day = int(groups[0])
                    if groups[1].isdigit():  # DD/MM/YYYY format
                        month = int(groups[1])
                        year = int(groups[2]) if len(groups) > 2 and groups[2] else anchor.year
                        if year < 100:
                            year += 2000
                    else:
                        month_str = groups[1][:3]
                        month = month_map.get(month_str, 0)
                        year = int(groups[2]) if len(groups) > 2 and groups[2] else anchor.year
                    
                    if 1 <= month <= 12 and 1 <= day <= 31 and year >= 2024:
                        dl_dt = datetime(year, month, day, 23, 59, 0)
                        ist_dt = IST.localize(dl_dt)
                        return ist_dt.isoformat()
            except Exception:
                pass
    
    # Strategy 3: Relative terms
    if "tomorrow" in text_lower:
        dl = (anchor + timedelta(days=1)).replace(hour=23, minute=59, second=0)
        return IST.localize(dl).isoformat()
    if "today" in text_lower and ("apply" in text_lower or "deadline" in text_lower or "last date" in text_lower):
        dl = anchor.replace(hour=23, minute=59, second=0)
        return IST.localize(dl).isoformat()
    
    return None


def extract_registration_link_nlp(text: str) -> Optional[str]:
    """Extract registration/apply link from text."""
    # Prioritize Google Forms, Naukri, LinkedIn, direct company links
    priority_patterns = [
        r"https?://(?:forms\.gle|docs\.google\.com/forms)[^\s<>\"']+",
        r"https?://[^\s<>\"']*(?:apply|register|form|jobs|careers|application)[^\s<>\"']*",
        r"https?://[^\s<>\"']+",
    ]
    for pat in priority_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            link = m.group(0).rstrip('.,;)')
            return link
    return None


def extract_ctc_nlp(text: str) -> Optional[str]:
    """Enhanced CTC extraction."""
    patterns = [
        r"(?:ctc|salary|stipend|package|compensation)\s*[:\-]?\s*((?:₹|rs\.?|inr)?\s*\d+(?:\.\d+)?(?:\s*[-–to]+\s*\d+(?:\.\d+)?)?\s*(?:lpa|lacs|lakhs?|k|per\s+(?:annum|month)))",
        r"((?:₹|rs\.?|inr)?\s*\d+(?:\.\d+)?(?:\s*[-–to]+\s*\d+(?:\.\d+)?)?\s*(?:lpa|lacs|lakhs?|per\s+annum))",
        r"(\d+(?:\.\d+)?\s*(?:lpa|lacs|lakhs))",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Normalize
            val = re.sub(r'\s+', ' ', val)
            return val
    return None


def extract_cgpa_nlp(text: str) -> Optional[str]:
    """Enhanced CGPA extraction."""
    patterns = [
        r"(?:cgpa|gpa)\s*(?:cutoff|criteria|requirement|should\s+be|minimum|above|of|above|>=|>|:)?\s*:?\s*(\d(?:\.\d{1,2})?)\s*(?:\+|and\s+above|or\s+above|above|minimum|min)?",
        r"minimum\s+(?:cgpa|gpa)\s*(?:of|:)?\s*(\d(?:\.\d{1,2})?)",
        r"(\d\.\d{1,2})\s*(?:cgpa|gpa)\s*(?:and\s+above|or\s+above|\+)?",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 5.0 <= val <= 10.0:
                return f"{val:.2f}+ CGPA"
    return None


def extract_summary_nlp(text: str, company: Optional[str], role: Optional[str]) -> str:
    """Generate a clean 1-2 sentence summary."""
    # Take first meaningful paragraph
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    # Try to build a meaningful sentence
    if company and role:
        return f"{company} is hiring for {role}. " + (lines[0][:100] if lines else '')
    elif company:
        return f"Placement opportunity from {company}. " + (lines[0][:80] if lines else '')
    elif role:
        return f"Hiring for {role}. " + (lines[0][:100] if lines else '')
    
    # Fallback: first non-empty line, trimmed
    if lines:
        summary = lines[0][:200]
        # Don't use if it's garbage (too short, or starts with ".")
        if len(summary) > 10 and not summary.startswith('.'):
            return summary
    
    return "Placement opportunity detected."


# ── CSE Intelligence ─────────────────────────────────────────────────────────
CSE_BRANCHES = {"CSE", "ISE", "IT", "AIML", "AIDS", "AI", "MCA", "BCA", "CS"}
NON_CSE_BRANCHES = {"MECH", "CIVIL", "EEE", "ECE", "CHEMICAL", "AUTOMOBILE", "ROBOTICS",
                    "BIOTECH", "MINING", "TEXTILE", "AGRICULTURAL", "AERONAUTICAL"}

CSE_ROLE_KEYWORDS = {
    "software engineer", "software developer", "sde", "swe", "backend", "frontend",
    "full stack", "data scientist", "data analyst", "data engineer", "ml engineer",
    "machine learning", "ai engineer", "devops", "cloud engineer", "sre",
    "qa engineer", "sdet", "automation engineer", "platform engineer",
    "security engineer", "systems engineer", "technology analyst", "it analyst",
    "technical associate", "associate software", "trainee engineer",
    "graduate engineer trainee", "get", "analyst", "consultant",
    "application developer", "web developer", "app developer",
    "technical program", "software intern", "engineering intern",
}

NON_CSE_ROLE_KEYWORDS = {
    "mechanical", "civil engineer", "electrical engineer", "chemical engineer",
    "automobile engineer", "robotics engineer", "structural engineer",
    "production engineer", "manufacturing engineer", "process engineer",
    "petroleum engineer", "agricultural engineer", "biomedical engineer",
}

CSE_TECH_KEYWORDS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "golang",
    "rust", "kotlin", "swift", "ruby", "php", "scala",
    "react", "angular", "vue", "node.js", "nodejs", "express", "django", "flask",
    "spring boot", "spring", "rest api", "restful", "graphql", "html", "css",
    "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "database", "nosql", "dynamodb",
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
    "ci/cd", "jenkins", "terraform", "ansible", "microservices",
    "machine learning", "deep learning", "artificial intelligence", "nlp",
    "data structures", "algorithms", "dsa", "pandas", "numpy", "tensorflow",
    "pytorch", "scikit", "data pipeline", "etl", "hadoop", "spark",
    "git", "github", "linux", "unix", "api", "apis", "sdk",
    "agile", "scrum", "jira",
    "object oriented", "oop", "design patterns", "system design",
    "computer networks", "dbms", "oops",
}

NON_CSE_TECH_KEYWORDS = {
    "autocad", "solidworks", "catia", "ansys", "matlab", "staad pro",
    "etabs", "revit", "primavera", "thermodynamics", "fluid mechanics",
    "strength of materials", "surveying", "plc", "scada",
    "mechanical drawing", "welding", "cnc", "casting",
    "concrete", "rcc", "structural analysis", "geotechnical",
}

STRONG_PLACEMENT_KEYWORDS = {
    "hiring", "recruitment", "campus hiring", "placement", "campus drive",
    "software engineer", "sde", "developer", "internship", "job opening",
    "job opportunity", "apply now", "registration", "job description",
    "jd", "eligible candidates", "ctc", "lpa", "campus recruitment",
    "off campus", "walk-in",
}

ELIGIBILITY_KEYWORDS = {
    "cse", "ise", "ece", "it", "branch", "batch", "graduating", "cgpa",
    "backlog", "passout", "eligible"
}

APPLICATION_KEYWORDS = {
    "apply", "registration link", "application deadline", "last date",
    "assessment", "interview", "test date", "google form", "supersets"
}


def compute_local_relevance(text: str) -> float:
    """Calculate local placement relevance score (0.0 to 1.0)."""
    if not text:
        return 0.0
    text_lower = text.lower()
    strong_hits = sum(1 for kw in STRONG_PLACEMENT_KEYWORDS if kw in text_lower)
    elig_hits = sum(1 for kw in ELIGIBILITY_KEYWORDS if kw in text_lower)
    app_hits = sum(1 for kw in APPLICATION_KEYWORDS if kw in text_lower)
    raw_score = (strong_hits * 0.25) + (elig_hits * 0.15) + (app_hits * 0.15)
    return min(1.0, raw_score)


def extract_branches_nlp(text: str) -> Optional[List[str]]:
    """Extract eligible engineering branches."""
    branches = []
    text_upper = text.upper()
    known = [
        "CSE", "ISE", "ECE", "EEE", "IT", "MECH", "CIVIL",
        "AIDS", "AIML", "MCA", "BCA", "ROBOTICS",
        "CHEMICAL", "BIOTECH", "AUTOMOBILE", "AERONAUTICAL",
    ]
    for b in known:
        if re.search(rf'\b{b}\b', text_upper):
            branches.append(b)
    if "ALL BRANCHES" in text_upper or "ALL ENGINEERING" in text_upper:
        return ["ALL"]
    return branches if branches else None


def extract_batch_nlp(text: str) -> Optional[str]:
    """Extract eligible graduation batch."""
    m = re.search(
        r'\b(20\d{2}\s*[-–]\s*20?\d{2}|20\d{2}\s+batch|20\d{2}\s+passout|20\d{2}\s+graduat\w+)\b',
        text, re.IGNORECASE
    )
    return m.group(0).strip() if m else None


def extract_skills_nlp(text: str) -> Optional[List[str]]:
    """Extract required technical skills from JD text."""
    text_lower = text.lower()
    found = []
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
        "pandas": "Pandas", "numpy": "NumPy",
        "tensorflow": "TensorFlow", "pytorch": "PyTorch",
        "scikit": "Scikit-learn",
    }
    for kw, display_name in skill_names.items():
        if len(kw) <= 3:
            if re.search(rf'\b{re.escape(kw)}\b', text_lower):
                if display_name not in found:
                    found.append(display_name)
        else:
            if kw in text_lower:
                if display_name not in found:
                    found.append(display_name)
    return found[:15] if found else None


def compute_cse_relevance_nlp(text: str, role: Optional[str], branches: Optional[List[str]]) -> dict:
    """Compute CSE relevance score (0–100)."""
    text_lower = text.lower()
    score = 0
    signals = []

    role_lower = (role or "").lower().strip()
    
    # Non-CSE role check
    for nkw in NON_CSE_ROLE_KEYWORDS:
        if nkw in role_lower or nkw in text_lower[:500]:
            score -= 30
            signals.append(f"Non-CSE role: {nkw}")
            break
    else:
        for ckw in CSE_ROLE_KEYWORDS:
            if ckw in role_lower:
                score += 40
                signals.append(f"CSE role: {ckw}")
                break
        else:
            score += 20  # neutral baseline

    if branches:
        branch_set = {b.upper() for b in branches}
        cse_overlap = branch_set & CSE_BRANCHES
        non_cse_overlap = branch_set & NON_CSE_BRANCHES
        if "ALL" in branch_set:
            score += 15
            signals.append("All branches eligible")
        elif cse_overlap and not non_cse_overlap:
            score += 40
            signals.append(f"CSE exclusively: {', '.join(sorted(cse_overlap))}")
        elif cse_overlap:
            score += 30
            signals.append(f"CSE branches: {', '.join(sorted(cse_overlap))}")
        elif non_cse_overlap and not cse_overlap:
            score -= 20
            signals.append(f"Non-CSE only: {', '.join(sorted(non_cse_overlap))}")
    else:
        score += 10

    cse_tech_hits = []
    for kw in CSE_TECH_KEYWORDS:
        if len(kw) <= 3:
            if re.search(rf'\b{re.escape(kw)}\b', text_lower):
                cse_tech_hits.append(kw)
        else:
            if kw in text_lower:
                cse_tech_hits.append(kw)

    non_cse_tech_hits = [kw for kw in NON_CSE_TECH_KEYWORDS if kw in text_lower]

    if cse_tech_hits:
        score += min(30, len(cse_tech_hits) * 5)
        signals.extend(cse_tech_hits[:10])
    if non_cse_tech_hits:
        score -= min(20, len(non_cse_tech_hits) * 5)

    final_score = max(0, min(100, score))
    return {
        "score": final_score,
        "is_relevant": final_score >= 50,
        "signals": signals,
    }


def extract_with_nlp(text: str, message_date: datetime) -> AIExtraction:
    """
    Main entry point. Extracts ALL fields using local NLP/ML techniques.
    ZERO external API calls. Fast, offline, reliable.
    """
    relevance_score = compute_local_relevance(text)
    is_placement = relevance_score >= 0.25

    company = extract_company_nlp(text)
    role = extract_role_nlp(text)
    ctc = extract_ctc_nlp(text)
    cgpa = extract_cgpa_nlp(text)
    batch = extract_batch_nlp(text)
    branches = extract_branches_nlp(text)
    link = extract_registration_link_nlp(text)
    deadline = extract_deadline_nlp(text, message_date)
    skills = extract_skills_nlp(text)
    cse_result = compute_cse_relevance_nlp(text, role, branches)
    summary = extract_summary_nlp(text, company, role)

    text_lower = text.lower()
    category = OpportunityCategory.PLACEMENT_OPPORTUNITY if is_placement else OpportunityCategory.IRRELEVANT
    if "assessment" in text_lower or ("test" in text_lower and is_placement):
        category = OpportunityCategory.ASSESSMENT
    elif "interview" in text_lower and is_placement:
        category = OpportunityCategory.INTERVIEW
    elif "shortlist" in text_lower:
        category = OpportunityCategory.SHORTLIST
    elif any(kw in text_lower for kw in ["deadline extended", "date extended", "extended"]):
        category = OpportunityCategory.DEADLINE_UPDATE
    elif is_placement and not company and not role:
        category = OpportunityCategory.PLACEMENT_UPDATE

    # Compute confidence: higher when we found more fields
    found_fields = sum([
        bool(company), bool(role), bool(ctc),
        bool(deadline), bool(link), bool(branches)
    ])
    confidence = min(0.95, max(0.40, relevance_score * 0.5 + found_fields * 0.075))

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
        summary=summary,
        confidence=confidence,
        cse_relevance_score=cse_result["score"],
        is_cse_relevant=cse_result["is_relevant"],
        jd_cse_signals=cse_result["signals"] if cse_result["signals"] else None,
        telegram_message_date=message_date,
    )
