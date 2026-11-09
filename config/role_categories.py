"""
Role categories, priorities, title normalization, and negative role definitions.
Single source of truth for job role classification in the AI Job Filtering Engine.
"""

from typing import List, Dict, Tuple

# ─── Role Category Constants ──────────────────────────────────────────────────

CATEGORY_CORE_AI_FDE = "Core AI Engineering and Forward Deployed Engineering"
CATEGORY_ML_SPECIALIZED_AI = "Machine Learning and Specialized AI"
CATEGORY_DATA_SCIENCE_APPLIED_RESEARCH = "Data Science and Applied Research"
CATEGORY_AI_RELATED_SOFTWARE_ENGINEERING = "AI-Related Software Engineering"

CATEGORY_PRIORITY_MAP: Dict[str, int] = {
    CATEGORY_CORE_AI_FDE: 1,
    CATEGORY_ML_SPECIALIZED_AI: 2,
    CATEGORY_DATA_SCIENCE_APPLIED_RESEARCH: 3,
    CATEGORY_AI_RELATED_SOFTWARE_ENGINEERING: 4,
}

# ─── Priority 1: Core AI and Forward Deployed Engineering ──────────────────────
# AI Engineering, LLM & Agentic AI, Forward Deployed Engineering
PRIORITY_1_ROLES: List[str] = [
    # Forward Deployed Engineering (specific multi-word titles first)
    "forward deployed software engineer",
    "forward deployed ai engineer",
    "forward deployed engineer",
    "applied ai solutions engineer",
    "agent deployment engineer",
    "ai implementation engineer",
    "ai integration engineer",
    "ai deployment engineer",
    # LLM and Agentic AI
    "generative ai application engineer",
    "llm application engineer",
    "agentic ai engineer",
    "ai agent engineer",
    "agent engineer",
    "ai automation engineer",
    "rag engineer",
    "llm engineer",
    # AI Engineering
    "artificial intelligence engineer",
    "applied ai engineer",
    "applied research engineer",
    "generative ai engineer",
    "genai engineer",
    "gen ai engineer",
    "ai software engineer",
    "ai application engineer",
    "ai product engineer",
    "ai research engineer",
    "founding ai engineer",
    "junior ai engineer",
    "associate ai engineer",
    "ai engineer",
]

# ─── Priority 2: Machine Learning and Specialized AI ───────────────────────────
PRIORITY_2_ROLES: List[str] = [
    "natural language processing engineer",
    "computer vision engineer",
    "machine learning engineer",
    "deep learning engineer",
    "ml research engineer",
    "ai infrastructure engineer",
    "ai platform engineer",
    "ml platform engineer",
    "ai systems engineer",
    "ai evaluation engineer",
    "llmops engineer",
    "mlops engineer",
    "ml ops engineer",
    "ml scientist",
    "nlp engineer",
    "ml engineer",
    "ai/ml engineer",
    "ai ml engineer",
]

# ─── Priority 3: Data Science and Applied Research ────────────────────────────
PRIORITY_3_ROLES: List[str] = [
    "associate data scientist",
    "junior data scientist",
    "data science associate",
    "applied scientist",
    "research scientist",
    "data scientist",
    "ai/ml analyst",
    "ai ml analyst",
    "data engineer",
    "data analyst",
]

# ─── Priority 4: AI-Related Software Engineering ──────────────────────────────
# Requires additional AI/ML/DSA relevance validation
PRIORITY_4_ROLES: List[str] = [
    "software development engineer",
    "software developer engineer",
    "backend software engineer",
    "associate software engineer",
    "graduate software engineer",
    "backend engineer",
    "backend developer",
    "python engineer",
    "python developer",
    "systems engineer",
    "platform engineer",
    "software engineer",
    "software developer",
    "sde 1",
    "sde-1",
    "sde1",
    "sde i",
    "sde",
    "swe 1",
    "swe-1",
    "swe1",
    "swe i",
    "swe",
]

# ─── Negative Role Exclusions (Title-Based) ───────────────────────────────────
# Roles to reject based on title

NEGATIVE_ROLES_FRONTEND: List[str] = [
    "frontend developer",
    "front end developer",
    "front-end developer",
    "frontend engineer",
    "front end engineer",
    "front-end engineer",
    "react developer",
    "react engineer",
    "angular developer",
    "angular engineer",
    "vue developer",
    "vue engineer",
    "ui engineer",
    "ux engineer",
    "ui developer",
    "ux developer",
    "ui designer",
    "ux designer",
    "web developer",
]

NEGATIVE_ROLES_FULLSTACK: List[str] = [
    "full stack developer",
    "full-stack developer",
    "fullstack developer",
    "full stack engineer",
    "full-stack engineer",
    "fullstack engineer",
]

NEGATIVE_ROLES_MOBILE: List[str] = [
    "android developer",
    "android engineer",
    "ios developer",
    "ios engineer",
    "flutter developer",
    "flutter engineer",
    "react native developer",
    "react native engineer",
    "mobile application developer",
    "mobile developer",
    "mobile engineer",
]

NEGATIVE_ROLES_TESTING: List[str] = [
    "qa engineer",
    "quality assurance engineer",
    "test engineer",
    "automation tester",
    "manual tester",
    "software testing engineer",
    "software test engineer",
    "qa tester",
    "qa analyst",
    "software quality engineer",
    "test automation engineer",
]

NEGATIVE_ROLES_EXCLUSIONS: List[str] = [
    "devops engineer",
    "site reliability engineer",
    "sre",
    "cloud engineer",
    "network engineer",
    "embedded engineer",
    "firmware engineer",
    "salesforce developer",
    "sap consultant",
    "technical support engineer",
    "customer support engineer",
    "sales engineer",
    "business development executive",
    "recruiter",
    "hr executive",
    "marketing executive",
    "account executive",
    "account manager",
    "graphic designer",
    "content writer",
]

# Senior level exclusions (strictly reject if present in title)
SENIOR_EXCLUSIONS: List[str] = [
    "senior",
    "sr.",
    "sr",
    "staff",
    "principal",
    "lead",
    "director",
    "manager",
    "architect",
    "head of",
    "vp",
    "vice president",
]

ALL_NEGATIVE_TITLE_ROLES: List[str] = (
    NEGATIVE_ROLES_FRONTEND
    + NEGATIVE_ROLES_FULLSTACK
    + NEGATIVE_ROLES_MOBILE
    + NEGATIVE_ROLES_TESTING
    + NEGATIVE_ROLES_EXCLUSIONS
    + SENIOR_EXCLUSIONS
)

# ─── Title Normalization Rules ────────────────────────────────────────────────
TITLE_NORMALIZATION_REPLACEMENTS: List[Tuple[str, str]] = [
    (r"\bgen[- ]?ai\b", "generative ai"),
    (r"\bai\s*/\s*ml\b", "ai/ml"),
    (r"\bml\s*/\s*ai\b", "ai/ml"),
    (r"\bml\b", "machine learning"),
    (r"\bsde[- ]?i\b", "sde 1"),
    (r"\bsde[- ]?1\b", "sde 1"),
    (r"\bswe[- ]?i\b", "swe 1"),
    (r"\bswe[- ]?1\b", "swe 1"),
    (r"\bsoftware developer engineer\b", "software development engineer"),
]
