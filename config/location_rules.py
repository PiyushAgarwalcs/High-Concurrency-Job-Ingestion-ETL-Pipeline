"""
Location filtering rules for the Job Filtering Engine.
Strictly targets Indian opportunities (Bangalore primary, verified Indian cities, Remote India/Remote).
"""

from typing import List

# ─── Primary Indian Locations (Highest scoring preference) ─────────────────────
PRIMARY_INDIAN_LOCATIONS: List[str] = [
    "bangalore",
    "bengaluru",
    "karnataka",
]

# ─── Other Verified Indian Cities ─────────────────────────────────────────────
OTHER_INDIAN_LOCATIONS: List[str] = [
    "hyderabad",
    "secunderabad",
    "telangana",
    "pune",
    "mumbai",
    "maharashtra",
    "gurgaon",
    "gurugram",
    "noida",
    "greater noida",
    "delhi",
    "new delhi",
    "delhi ncr",
    "ncr",
    "chennai",
    "tamil nadu",
    "ahmedabad",
    "gujarat",
    "kochi",
    "cochin",
    "kerala",
    "coimbatore",
    "kolkata",
    "west bengal",
    "jaipur",
    "rajasthan",
    "indore",
    "madhya pradesh",
    "chandigarh",
    "mohali",
    "punjab",
    "trivandrum",
    "thiruvananthapuram",
    "nagpur",
    "bhubaneswar",
    "odisha",
    "vadodara",
    "surat",
]

# ─── Remote Indian / Generic Remote Locations ─────────────────────────────────
REMOTE_LOCATIONS: List[str] = [
    "remote india",
    "india remote",
    "work from home india",
    "wfh india",
    "anywhere in india",
    "pan india",
    "india",
    "remote",
    "work from home",
    "wfh",
    "anywhere",
]

# All accepted location tokens for substring / token matching
ALL_ACCEPTED_LOCATIONS: List[str] = (
    PRIMARY_INDIAN_LOCATIONS
    + OTHER_INDIAN_LOCATIONS
    + REMOTE_LOCATIONS
)

# ─── Explicit Foreign-Only Locations to Reject ────────────────────────────────
FOREIGN_LOCATIONS: List[str] = [
    "usa",
    "united states",
    "u.s.",
    "u.s.a.",
    "uk",
    "united kingdom",
    "canada",
    "london",
    "new york",
    "san francisco",
    "sf, ca",
    "san francisco, ca",
    "bay area",
    "california",
    "seattle",
    "austin",
    "boston",
    "chicago",
    "singapore",
    "germany",
    "berlin",
    "munich",
    "amsterdam",
    "netherlands",
    "dublin",
    "ireland",
    "sydney",
    "melbourne",
    "australia",
    "tokyo",
    "japan",
    "paris",
    "france",
    "zurich",
    "switzerland",
    "poland",
    "warsaw",
    "sweden",
    "stockholm",
    "israel",
    "tel aviv",
    "uae",
    "dubai",
]

# Foreign restriction phrases in descriptions for Remote postings
FOREIGN_RESTRICTION_PATTERNS: List[str] = [
    r"must\s+be\s+(?:legally\s+)?authorized\s+to\s+work\s+in\s+the\s+(?:us|united\s+states|uk|canada)",
    r"(?:us|u\.s\.)\s+citizens?\s+only",
    r"must\s+reside\s+in\s+the\s+(?:us|united\s+states|uk|europe|canada)",
    r"only\s+candidates\s+(?:located|based)\s+in\s+the\s+(?:us|united\s+states|uk|canada|europe)",
    r"(?:us|uk|canada)\s+timezones?\s+only",
]

