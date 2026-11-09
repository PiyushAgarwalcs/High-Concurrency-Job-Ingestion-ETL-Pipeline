"""
Search terms, role keywords, experience filters, location filters,
and negative keywords for the High-Concurrency Job Ingestion & ETL System.

Refactored to serve as the unified compatibility layer importing from
modular configurations: role_categories, skill_keywords, experience_rules,
salary_rules, and location_rules.
"""

from config.role_categories import (
    PRIORITY_1_ROLES as _P1_ROLES,
    PRIORITY_2_ROLES as _P2_ROLES,
    PRIORITY_3_ROLES as _P3_ROLES,
    PRIORITY_4_ROLES as _P4_ROLES,
    ALL_NEGATIVE_TITLE_ROLES,
    NEGATIVE_ROLES_EXCLUSIONS,
    SENIOR_EXCLUSIONS,
)
from config.skill_keywords import (
    CORE_AI_KEYWORDS,
    LLM_AGENTIC_KEYWORDS,
    AI_APPLICATION_DEPLOYMENT_KEYWORDS,
    DSA_KEYWORDS,
    SUPPORTING_SWE_KEYWORDS,
    SDE_VALIDATION_KEYWORDS as _SDE_VALID_KWS,
)
from config.experience_rules import (
    ACCEPTED_EXPERIENCE_KEYWORDS as _ACCEPT_EXP,
    REJECTED_EXPERIENCE_KEYWORDS as _REJECT_EXP,
)
from config.location_rules import (
    PRIMARY_INDIAN_LOCATIONS,
    OTHER_INDIAN_LOCATIONS,
    REMOTE_LOCATIONS,
    ALL_ACCEPTED_LOCATIONS as _ALL_ACCEPTED_LOCS,
    FOREIGN_LOCATIONS,
)

# ─── Target Role Keywords (by Priority) ────────────────────────────────────────
PRIORITY_1_ROLES = _P1_ROLES
PRIORITY_2_ROLES = _P2_ROLES
PRIORITY_3_ROLES = _P3_ROLES
PRIORITY_4_ROLES = _P4_ROLES

ALL_ROLE_KEYWORDS = PRIORITY_1_ROLES + PRIORITY_2_ROLES + PRIORITY_3_ROLES + PRIORITY_4_ROLES

# ─── SDE/SWE Validation Keywords ──────────────────────────────────────────────
# If a job matches SDE/SWE title keywords, it must ALSO contain at least one
# of these in the title or description to be accepted (prevents generic web dev matches)
SDE_VALIDATION_KEYWORDS = _SDE_VALID_KWS

# ─── SDE Title Keywords (need validation) ──────────────────────────────────────
SDE_TITLE_KEYWORDS = PRIORITY_4_ROLES

# ─── Broad Search Keywords (for job board queries) ──────────────────────────────
SEARCH_QUERIES = [
    "machine learning engineer fresher",
    "AI engineer entry level",
    "data scientist fresher india",
    "ML engineer 0 experience",
    "artificial intelligence fresher",
    "generative AI engineer entry level",
    "LLM engineer fresher",
    "agentic AI engineer fresher",
    "forward deployed engineer fresher",
    "deep learning engineer fresher",
    "NLP engineer entry level",
    "computer vision engineer fresher",
    "data scientist entry level bangalore",
    "AI ML fresher",
    "applied AI engineer new grad",
    "SDE fresher AI ML",
    "software engineer machine learning fresher",
]

# ─── Title Keywords for ATS Filtering ──────────────────────────────────────────
# Used to filter jobs from Greenhouse/Lever APIs by title keywords
ATS_TITLE_KEYWORDS = [
    "machine learning",
    "ml ",
    " ml",
    "artificial intelligence",
    " ai ",
    " ai/",
    "ai/ml",
    "data scien",
    "deep learning",
    "nlp",
    "natural language",
    "computer vision",
    "generative ai",
    "gen ai",
    "genai",
    "llm",
    "large language model",
    "forward deployed",
    "agentic",
    "applied scientist",
    "research scientist",
    "mlops",
    "ml ops",
    "ml platform",
    "data analyst",
    "software engineer",
    "software developer",
    "sde",
    "swe",
]

# ─── Experience Keywords ───────────────────────────────────────────────────────
ACCEPT_EXPERIENCE_KEYWORDS = _ACCEPT_EXP
REJECT_EXPERIENCE_KEYWORDS = _REJECT_EXP

# ─── Location Keywords ─────────────────────────────────────────────────────────
PRIMARY_LOCATIONS = PRIMARY_INDIAN_LOCATIONS
SECONDARY_LOCATIONS = REMOTE_LOCATIONS
OPTIONAL_LOCATIONS = OTHER_INDIAN_LOCATIONS
ALL_ACCEPTED_LOCATIONS = _ALL_ACCEPTED_LOCS

# ─── Negative Keywords (reject jobs containing these in title) ──────────────────
NEGATIVE_TITLE_KEYWORDS = ALL_NEGATIVE_TITLE_ROLES

# ─── Skill Keywords (for matching and ranking) ────────────────────────────────
DESIRED_SKILLS = [
    "python", "machine learning", "deep learning",
    "tensorflow", "pytorch", "scikit-learn", "sklearn",
    "nlp", "natural language processing",
    "computer vision", "opencv",
    "data science", "data analysis",
    "pandas", "numpy", "scipy",
    "keras", "transformers", "hugging face", "huggingface",
    "llm", "large language model", "gpt", "bert",
    "generative ai", "gen ai",
    "langchain", "rag", "retrieval augmented",
    "llamaindex", "agentic", "ai agents",
    "mlops", "ml pipeline", "mlflow",
    "aws sagemaker", "gcp vertex", "azure ml",
    "sql", "statistics", "linear algebra",
    "neural network", "cnn", "rnn", "lstm",
    "reinforcement learning", "rl",
    "feature engineering", "model deployment",
    "a/b testing", "experimentation",
    "dsa", "data structures", "algorithms",
]
