"""
Central configuration for the AI/ML Job Alert System V2.
Loads settings from JSON files and sets environment constants.
"""

import os
import json
from datetime import timezone, timedelta
from typing import Dict, Any, List

# ─── Base Paths ─────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Ensure directories exist
for d in [DATA_DIR, LOGS_DIR, REPORTS_DIR]:
    os.makedirs(d, exist_ok=True)

# ─── Timezone ───────────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ─── Helper Functions ──────────────────────────────────────────────────────────
def load_json(path: str) -> Any:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_all_companies() -> List[Dict[str, Any]]:
    companies_dir = os.path.join(CONFIG_DIR, "companies")
    all_companies = []
    if os.path.exists(companies_dir):
        for filename in os.listdir(companies_dir):
            if filename.endswith(".json"):
                data = load_json(os.path.join(companies_dir, filename))
                if isinstance(data, list):
                    all_companies.extend(data)
    return all_companies

# ─── Load Configurations ───────────────────────────────────────────────────────
KEYWORDS_CONFIG = load_json(os.path.join(CONFIG_DIR, "keywords.json"))
IGNORE_CONFIG = load_json(os.path.join(CONFIG_DIR, "ignore_keywords.json"))
SCORING_CONFIG = load_json(os.path.join(CONFIG_DIR, "scoring.json"))
LOGGING_CONFIG = load_json(os.path.join(CONFIG_DIR, "logging.json"))
COMPANIES_LIST = load_all_companies()

# ─── Telegram Configuration ────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# ─── Scraping & DeployGuard Concurrency Configuration ───────────────────────────
REQUEST_TIMEOUT = 30          # Maximum request timeout in seconds
RETRY_ATTEMPTS = 3            # Retry up to 3 times on transient failures
RETRY_DELAY = 2               # Base backoff delay in seconds
MAX_CONCURRENT_REQUESTS = 30  # Global concurrency limit
PER_HOST_CONCURRENCY = 5      # Domain-aware concurrency cap (DeployGuard isolation)

# ─── DeployGuard Circuit Breaker Thresholds ─────────────────────────────────────
CIRCUIT_BREAKER_FAILURES = 3   # Consecutive 429/503/timeout failures to trip breaker
CIRCUIT_BREAKER_COOLDOWN = 900 # 15-minute cooldown window before half-open probe

# ─── OmniSight Deduplication & State Ledger ─────────────────────────────────────
OMNISIGHT_DB_PATH = os.path.join(DATA_DIR, "jobs.db")
FINGERPRINT_HASH_ALGO = "sha256"

# ─── HTTP Headers ───────────────────────────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1"
}

JSON_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"'
}

# ─── Filtering Configuration ───────────────────────────────────────────────────
MAX_EXPERIENCE_YEARS = 2      # Accept 0-2 years only

# ─── Output Configuration ──────────────────────────────────────────────────────
DB_PATH = os.path.join(DATA_DIR, "jobs.db")
TOP_N_JOBS = 50               # Max new jobs to send in one run

# ─── Dry Run Mode ──────────────────────────────────────────────────────────────
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# ─── Notification Configuration ───────────────────────────────────────────────
NOTIFY_ON_EMPTY = os.environ.get("NOTIFY_ON_EMPTY", "false").lower() == "true"
# Set NOTIFY_ON_EMPTY=true in GitHub Secrets if you want a ping even when no new jobs found
