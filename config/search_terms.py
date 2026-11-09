"""
Search terms, role keywords, experience filters, location filters,
and negative keywords for the High-Concurrency Job Ingestion & ETL System.
"""

# ─── Target Role Keywords (by Priority) ────────────────────────────────────────

PRIORITY_1_ROLES = [
    "machine learning engineer",
    "ml engineer",
    "ai engineer",
    "applied ai engineer",
    "generative ai engineer",
    "gen ai engineer",
    "llm engineer",
    "ai research engineer",
    "ml research engineer",
    "artificial intelligence engineer",
    "forward deployed engineer",
    "forward deployed software engineer",
    "forward deployed ai engineer",
    # Core SDE/SWE roles (will be further validated against AI/DSA skills)
    "software development engineer",
    "software developer engineer",
    "sde ",
    "sde-",
    "sde1",
    "sde 1",
    "sde i",
    "software engineer",
    "software developer",
]

PRIORITY_2_ROLES = [
    "data scientist",
    "associate data scientist",
    "junior data scientist",
    "ai ml analyst",
    "ai/ml analyst",
    "data analyst",
    "ml scientist",
    "applied scientist",
    "research scientist",
]

PRIORITY_3_ROLES = [
    "nlp engineer",
    "natural language processing engineer",
    "computer vision engineer",
    "deep learning engineer",
    "mlops engineer",
    "ml ops engineer",
    "ml platform engineer",
]

ALL_ROLE_KEYWORDS = PRIORITY_1_ROLES + PRIORITY_2_ROLES + PRIORITY_3_ROLES

# ─── SDE/SWE Validation Keywords ──────────────────────────────────────────────
# If a job matches SDE/SWE title keywords, it must ALSO contain at least one
# of these in the title or description to be accepted (prevents generic web dev matches)
SDE_VALIDATION_KEYWORDS = [
    "machine learning", "ml", "artificial intelligence", "ai",
    "data science", "data scientist", "deep learning",
    "nlp", "natural language", "computer vision",
    "dsa", "data structures", "algorithms",
    "python", "model", "neural",
    "generative ai", "gen ai", "llm", "genai",
    "research", "applied scientist",
]

# ─── SDE Title Keywords (need validation) ──────────────────────────────────────
SDE_TITLE_KEYWORDS = [
    "software development engineer",
    "software developer engineer",
    "software engineer",
    "software developer",
    "sde ",
    "sde-",
    "sde1",
    "sde 1",
    "sde i",
]

# ─── Broad Search Keywords (for job board queries) ──────────────────────────────

SEARCH_QUERIES = [
    "machine learning engineer fresher",
    "AI engineer entry level",
    "data scientist fresher india",
    "ML engineer 0 experience",
    "artificial intelligence fresher",
    "generative AI engineer entry level",
    "LLM engineer fresher",
    "deep learning engineer fresher",
    "NLP engineer entry level",
    "computer vision engineer fresher",
    "data scientist entry level bangalore",
    "AI ML fresher",
    "machine learning intern full time",
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
    "applied scientist",
    "research scientist",
    "mlops",
    "ml ops",
    "ml platform",
    "data analyst",
    "software engineer",
    "software developer",
    "sde",
]

# ─── Experience Keywords ───────────────────────────────────────────────────────

ACCEPT_EXPERIENCE_KEYWORDS = [
    "fresher", "freshers", "fresh graduate",
    "entry level", "entry-level",
    "new graduate", "new grad",
    "campus hiring", "campus hire",
    "university graduate", "recent graduate",
    "0 years", "0-1 years", "0 to 1 year",
    "0+ years", "zero experience",
    "no experience required",
    "graduate engineer", "graduate trainee",
    "associate", "junior", "jr.",
    "intern to full time", "intern to fte",
    "2027 passout", "2027 batch", "class of 2027", "2027 graduates",
]

REJECT_EXPERIENCE_KEYWORDS = [
    "senior", "sr.", "sr ",
    "lead", "principal", "staff",
    "manager", "director", "head of",
    "vp ", "vice president",
    "3+ years", "4+ years", "5+ years",
    "6+ years", "7+ years", "8+ years",
    "3-5 years", "5-7 years", "4-6 years",
    "10+ years",
]

# ─── Location Keywords ─────────────────────────────────────────────────────────

PRIMARY_LOCATIONS = [
    "bangalore", "bengaluru", "karnataka",
]

SECONDARY_LOCATIONS = [
    "remote", "work from home", "wfh",
    "india", "anywhere in india",
    "pan india",
]

OPTIONAL_LOCATIONS = [
    "hyderabad", "telangana",
    "pune", "maharashtra",
    "gurugram", "gurgaon",
    "noida", "greater noida",
    "chennai", "tamil nadu",
    "mumbai",
    "delhi", "new delhi",
]

ALL_ACCEPTED_LOCATIONS = PRIMARY_LOCATIONS # Strictly restricted to Bangalore as per requirement

# ─── Negative Keywords (reject jobs containing these in title) ──────────────────

NEGATIVE_TITLE_KEYWORDS = [
    "full stack",
    "fullstack",
    "front end",
    "frontend",
    "front-end",
    "react developer",
    "angular developer",
    "vue developer",
    "backend developer",
    "back end developer",
    "back-end developer",
    "node.js developer",
    "nodejs developer",
    "express.js",
    "spring boot",
    "mobile developer",
    "ios developer",
    "android developer",
    "flutter developer",
    "react native",
    "devops engineer",
    "site reliability",
    "sre ",
    "salesforce developer",
    "sap consultant",
    "qa engineer",
    "test engineer",
    "manual testing",
    "php developer",
    "wordpress",
    ".net developer",
    "java developer",
    "ui developer",
    "ux designer",
    "graphic designer",
    "content writer",
    "hr ",
    "human resource",
    "recruiter",
    "sales",
    "marketing",
    "business development",
    "account manager",
    "customer success",
    "support engineer",
    "technical support",
]

# ─── Skill Keywords (for matching) ─────────────────────────────────────────────

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
    "mlops", "ml pipeline", "mlflow",
    "aws sagemaker", "gcp vertex", "azure ml",
    "sql", "statistics", "linear algebra",
    "neural network", "cnn", "rnn", "lstm",
    "reinforcement learning", "rl",
    "feature engineering", "model deployment",
    "a/b testing", "experimentation",
    "dsa", "data structures", "algorithms",
]
