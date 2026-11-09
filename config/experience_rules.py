"""
Experience parsing and validation rules for the Job Filtering Engine.
Strict 0-2 years experience policy targeting freshers and early-career candidates.
"""

from typing import List

MAX_EXPERIENCE_YEARS: float = 2.0

# ─── Explicit Accept Keywords ─────────────────────────────────────────────────
ACCEPTED_EXPERIENCE_KEYWORDS: List[str] = [
    "fresher",
    "freshers",
    "fresh graduate",
    "entry level",
    "entry-level",
    "new grad",
    "new graduate",
    "recent graduate",
    "graduate engineer",
    "graduate trainee",
    "campus hiring",
    "campus hire",
    "university graduate",
    "0 years",
    "0-1 years",
    "0 to 1 year",
    "0-2 years",
    "0 to 2 years",
    "1-2 years",
    "1 to 2 years",
    "1 year",
    "2 years",
    "0-2 years of relevant experience",
    "0-2 years experience",
    "no experience required",
    "zero experience",
    "2027 passout",
    "2027 batch",
    "class of 2027",
    "2026 passout",
    "2026 batch",
    "class of 2026",
]

# ─── Explicit Reject Keywords ─────────────────────────────────────────────────
REJECTED_EXPERIENCE_KEYWORDS: List[str] = [
    "3+ years",
    "4+ years",
    "5+ years",
    "6+ years",
    "7+ years",
    "8+ years",
    "9+ years",
    "10+ years",
    "3+ yrs",
    "4+ yrs",
    "5+ yrs",
    "6+ yrs",
    "7+ yrs",
    "8+ yrs",
    "9+ yrs",
    "10+ yrs",
    "3-5 years",
    "4-6 years",
    "5-7 years",
    "minimum 3 years",
    "at least 3 years",
    "minimum of 3 years",
    "at least 4 years",
    "minimum 4 years",
    "at least 5 years",
    "minimum 5 years",
]

# ─── Company / Organization Experience False-Positive Masks ──────────────────
# Matches statements about company history or team tenure that should NOT be
# attributed to candidate experience requirements.
COMPANY_EXPERIENCE_REGEXES: List[str] = [
    r"(?:our\s+team|the\s+team|our\s+company|the\s+company|we|our\s+firm|the\s+firm)\s+(?:has|have|brings|with)\s+(?:over\s+|more\s+than\s+)?\d+\+?\s*(?:years?|yrs?)",
    r"(?:over|more\s+than)\s+\d+\+?\s*(?:years?|yrs?)\s+of\s+(?:industry\s+|company\s+)?(?:experience|history|expertise|track\s*record|leadership|service)",
    r"(?:serving|supporting)\s+(?:clients|customers)\s+for\s+(?:over\s+)?\d+\+?\s*(?:years?|yrs?)",
    r"(?:founded|established)\s+(?:in\s+\d{4}|\d+\+?\s*(?:years?|yrs?)\s+ago)",
    r"\b\d+\+?\s*(?:years?|yrs?)\s+in\s+business\b",
    r"(?:backed\s+by|with)\s+\d+\+?\s*(?:years?|yrs?)\s+of\s+combined\s+experience",
]

# ─── Candidate Requirement Section Headers ────────────────────────────────────
# When scanning description text, prioritize paragraphs under requirement sections.
REQUIREMENT_SECTION_REGEX: str = (
    r"(?:requirements|qualifications|eligibility|what\s+you(?:'ll)?\s+need|"
    r"what\s+we(?:'re)?\s+looking\s+for|who\s+you\s+are|candidate\s+profile|"
    r"experience\s+required|minimum\s+qualifications|basic\s+qualifications)"
)

