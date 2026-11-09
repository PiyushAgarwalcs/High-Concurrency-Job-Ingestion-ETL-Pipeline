"""
Salary extraction and validation rules for the Job Filtering Engine.
Maintains LinkedIn Easy Apply minimum salary floor of 12 LPA with decimal and range support.
"""

import re

LINKEDIN_SALARY_FLOOR_LPA: float = 12.0

# ─── Regex Patterns for Salary Extraction ─────────────────────────────────────

# 1. Range in LPA / Lakhs: e.g. "12-18 LPA", "12.5 - 15 Lakhs", "8 to 15 lpa"
SALARY_RANGE_LPA_REGEX = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|\u2013)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|lacs|l\b)",
    re.IGNORECASE,
)

# 2. Single LPA / Lakhs: e.g. "12 LPA", "12.5 LPA", "20 Lakhs per annum", "15 LPA CTC"
SALARY_SINGLE_LPA_REGEX = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|lacs)(?:\s*(?:ctc|per\s*annum|p\.?a\.?|annually))?",
    re.IGNORECASE,
)

# 3. Absolute Annual INR: e.g. "₹15,00,000 per annum", "1500000 INR annually", "₹ 12,00,000 p.a."
SALARY_ABSOLUTE_ANNUAL_REGEX = re.compile(
    r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(?:inr|rs\.?)?\s*(?:per\s*annum|p\.?a\.?|annually|a\s*year|ctc\b)",
    re.IGNORECASE,
)

# 4. Standalone large INR number followed by per annum: "1500000 INR per annum"
SALARY_ABSOLUTE_NO_PREFIX_REGEX = re.compile(
    r"(\d{1,2}(?:,\d{2,3})*(?:\.\d+)?|\d{6,8})\s*(?:inr|rs\.?)\s*(?:per\s*annum|p\.?a\.?|annually|a\s*year|ctc\b)",
    re.IGNORECASE,
)

# 5. Monthly Stipend / Salary: e.g. "₹25,000 / month", "stipend of ₹50k/month", "25,000 pm"
STIPEND_MONTHLY_REGEX = re.compile(
    r"(?:(?:monthly\s+)?stipend(?:\s*(?:of|:))?\s*)?(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})*|\d+)\s*(?:k\b)?\s*(?:per\s*month|/\s*month|/\s*mo|pm\b|\s*stipend\b)",
    re.IGNORECASE,
)
