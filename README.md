<div align="center">
  
# 🚀 High-Concurrency Job Ingestion & ETL Pipeline

**An autonomous, zero-cost data engineering pipeline that continuously extracts, filters, deduplicates, and dispatches high-signal fresher AI/ML & Backend engineering roles across 1,050+ company career portals.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.14-E92063.svg?style=flat&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Asyncio](https://img.shields.io/badge/Asyncio-Concurrent%20I%2FO-2BA640.svg?style=flat)](https://docs.python.org/3/library/asyncio.html)
[![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg?style=flat&logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![Database](https://img.shields.io/badge/Storage-SQLite%20(WAL%20Mode)-003B57.svg?style=flat&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Test Suite](https://img.shields.io/badge/Test%20Suite-30%20Passed%20(100%25)-brightgreen.svg?style=flat&logo=pytest&logoColor=white)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](https://opensource.org/licenses/MIT)

</div>

---

## 📖 Overview

Third-party job boards (LinkedIn, Indeed, Naukri) suffer from significant indexing delays, aggressive rate limits, applicant saturation, and ghost postings. Applying within the first 30 minutes of a job being posted offers a massive response-rate advantage.

This project bypasses aggregators entirely. It is a pure, zero-cost backend pipeline that directly queries **1,050+ enterprise career portals across 18 Applicant Tracking Systems (ATS)**, extracts raw listings concurrently, enforces rigorous schema validation and circuit breaking via **RequestGuard**, executes deterministic deduplication with **StateLedger**, and delivers sub-minute alerts directly to Telegram.

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      1. HIGH-CONCURRENCY INGESTION                     │
│ • Scheduled via GitHub Actions CRON (4x Daily: 06:00, 12:00, 18:00 IST)│
│ • Parallel worker pool via aiohttp & asyncio.Semaphore                 │
│ • 18 ATS Handlers: Greenhouse, Lever, Ashby, Workday, SmartRecruiters  │
│ • Per-domain rate limiting: 5 concurrent/host, 30 global pool          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   2. REQUESTGUARD (Safety Gateway)                     │
│ • Strict Pydantic v2 runtime validation (JobSchema)                    │
│ • URL sanitization: Strips UTM, referral, tracking, & affiliate params │
│ • Non-tech title and spam quarantine                                   │
│ • Finite-state Circuit Breaker (Closed -> Open -> Half-Open)           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Validated Canonical Records)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  3. FILTERING & HEURISTIC RANKING                      │
│ • Word-boundary regex validation (prevents "Python 3+" false positives)│
│ • Fresher scope: 0–2 years experience limits                           │
│ • SDE title validation: Requires DSA/AI/ML/Systems context             │
│ • Dynamic scoring: Role priority + tech match + recency decay (1.3x)   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Eligible Listings)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│              4. STATELEDGER (Deduplication & Storage)                  │
│ • Text normalization: Unicode NFKC standardization + city aliasing     │
│ • Deterministic State Fingerprinting: SHA-256(company:title:location)  │
│ • Chunked SQLite WAL batch queries & insertions                        │
│ • Automated 90-day rolling data pruning & physical VACUUM defrag       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Brand New Listings)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│              5. ASYNC NOTIFICATION & OBSERVABILITY                     │
│ • Pluggable BaseNotifier: TelegramNotifier (async aiohttp) & Console   │
│ • Chunked HTML message formatting strictly under Telegram's 4096-char  │
│ • Real-time crash alerting via Telegram webhook if pipeline fails      │
│ • Execution telemetry written to $GITHUB_STEP_SUMMARY & Markdown/CSV   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Engineering Features

### 1. 🛡️ RequestGuard Ingestion Gateway (`core/request_guard.py`)
- **Pydantic v2 Schema Enforcement:** Validates every incoming scraped listing against [`JobSchema`](file:///d:/Final%20Projects/JOB_ALERT/core/request_guard.py), quarantining malformed records, placeholder titles (`"test"`, `"null"`), or missing URLs.
- **URL Sanitization:** Strips marketing, referral, and tracking query parameters (`utm_*`, `gh_src`, `lever-origin`, `ref`, `source`, `fbclid`).
- **Domain-Aware Circuit Breaker:** Implements a finite state machine (**CLOSED -> OPEN -> HALF-OPEN**) per ATS domain. Upon 3 consecutive HTTP 429/503 errors, trips open for 15 minutes to prevent IP blocks and preserve upstream availability.

### 2. 🔍 StateLedger Deduplication Fabric (`core/state_ledger.py`)
- **Deterministic SHA-256 Fingerprinting:** Generates `SHA-256(company:title:location)` hashes from normalized strings. Cross-posted roles across Greenhouse, LinkedIn, and Lever yield identical hashes.
- **Unicode NFKC & City Normalization:** Converts title variations (`"Software Engineer - I"` -> `"sde 1"`) and maps city synonyms (`"Bengaluru, Karnataka"` -> `"bangalore"`).
- **Batch Processing:** Uses `batch_check_and_register()` to query existing hashes in 500-item chunks and execute bulk WAL-mode inserts in a single transaction.
- **Automated Rolling Pruning & VACUUM:** Automatically deletes jobs, fingerprints, and telemetry logs older than 90 days on every run, followed by `VACUUM` to reclaim physical disk pages.

### 3. 🎯 Algorithmic Filter & Scoring Engine (`core/filter_engine.py`, `core/ranking_engine.py`)
- **Word-Boundary Experience Guard:** Matches experience requirements using regex boundary guards (`r"(?<!\w)" + kw + r"(?!\w)"`), ensuring tech mentions like `"Python 3+"` or `"Web3"` are not mistaken for `"3+ years experience"`.
- **SDE Context Validation:** Generic Software Engineer titles are validated against ML/AI/DSA keyword matrices (`search_terms.py`) to filter out non-technical or unrelated IT roles.
- **Recency Decay:** Newly posted listings receive a 1.30x score multiplier that gradually decays over 7 days down to 0.75x.
- **Salary Floor:** Low-paying roles (< ₹12 LPA) on open platforms are filtered out.

### 4. 📱 Async Strategy-Pattern Notifier (`notifiers/`)
- Fully asynchronous [`TelegramNotifier`](file:///d:/Final%20Projects/JOB_ALERT/notifiers/telegram.py) built on `aiohttp` with connection pooling and rate-limit delays (`1 msg/sec`).
- Automatically splits large batches into clean HTML chunks under Telegram's 4,096-character limit, with fallback to sanitized plain text on parse errors.
- Dispatches emergency crash alerts to Telegram if an unhandled exception occurs during pipeline execution.

---

## 🌐 Supported ATS Providers (18 Handlers, 1,050+ Portals)

The pipeline dynamically detects and scrapes career listings from:

| ATS Provider | Protocol | ATS Provider | Protocol |
| :--- | :--- | :--- | :--- |
| **Greenhouse** | REST API & Embedded Boards | **Workday** | CXS / Wday Search APIs |
| **Lever** | Postings JSON API | **SmartRecruiters** | Public Career API |
| **Ashby** | Public Job Board API | **BambooHR** | XML Feed & Directory |
| **Workable** | JSON Endpoint | **Comeet** | Widget API |
| **Recruitee** | Careers API | **Teamtailor** | Public JSON Feed |
| **Personio** | XML/JSON Career API | **Jobvite** | Search Feed |
| **iCIMS** | Portal Scraper | **Oracle Cloud HCM** | Requisition API |
| **SuccessFactors** | Career Portal API | **Instahyre / Wellfound** | Custom Gateway |

---

## 🧪 Test Suite

The codebase includes comprehensive unit and integration tests with **100% pass rate**:

```bash
python -m pytest tests/ -v
```

```text
tests/test_filter_engine.py::test_rejects_negative_roles PASSED
tests/test_filter_engine.py::test_role_priority_classification PASSED
tests/test_filter_engine.py::test_generic_sde_validation PASSED
tests/test_filter_engine.py::test_experience_filtering_boundaries PASSED
tests/test_filter_engine.py::test_location_filtering PASSED
tests/test_filter_engine.py::test_linkedin_salary_floor PASSED
tests/test_metrics.py::test_metrics_tracker_calculations PASSED
tests/test_metrics.py::test_metrics_tracker_zero_division_safety PASSED
tests/test_metrics.py::test_metrics_report_formatting PASSED
tests/test_pipeline_integration.py::test_full_data_engineering_pipeline_flow PASSED
tests/test_ranking_engine.py::test_role_priority_base_scores PASSED
tests/test_ranking_engine.py::test_salary_bonus_calculation PASSED
tests/test_ranking_engine.py::test_recency_multiplier_decay PASSED
tests/test_ranking_engine.py::test_rank_jobs_orders_highest_score_first PASSED
tests/test_request_guard.py::test_clean_url_removes_tracking_params PASSED
tests/test_request_guard.py::test_job_schema_valid PASSED
tests/test_request_guard.py::test_job_schema_rejects_placeholder_title PASSED
tests/test_request_guard.py::test_job_schema_rejects_invalid_url PASSED
tests/test_request_guard.py::test_job_schema_rejects_empty_company PASSED
tests/test_request_guard.py::test_circuit_breaker_transitions PASSED
tests/test_state_ledger.py::test_normalize_title PASSED
tests/test_state_ledger.py::test_normalize_location PASSED
tests/test_state_ledger.py::test_fingerprint_equivalence_across_variations PASSED
tests/test_state_ledger.py::test_is_new_listing_and_duplicate_suppression PASSED
tests/test_state_ledger.py::test_batch_check_and_register PASSED
tests/test_state_ledger.py::test_db_size_reporting PASSED
tests/test_telegram_notifier.py::test_html_escaping PASSED
tests/test_telegram_notifier.py::test_prestige_bar PASSED
tests/test_telegram_notifier.py::test_format_salary PASSED
tests/test_telegram_notifier.py::test_message_chunking_under_telegram_limit PASSED

============================= 30 passed in 1.60s ==============================
```

---

## 🚀 Getting Started

### 1. Clone & Install
```bash
git clone https://github.com/PiyushAgarwalcs/aiml_jobalert_bypa.git
cd aiml_jobalert_bypa
python -m pip install -r requirements.txt
```

### 2. Configure Environment
Copy the example environment template:
```bash
cp .env.example .env
```

Edit `.env` with your Telegram credentials:
```env
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
TELEGRAM_CHAT_ID="-1001234567890"
DRY_RUN="false"
NOTIFY_ON_EMPTY="false"
TOP_N_JOBS="10"
RETENTION_DAYS="90"
```

### 3. Local Dry Run (Console Output)
Run the pipeline locally without notifying Telegram or mutating the database:
```bash
python main.py --dry-run --console-notify
```

### 4. Production Run
Execute the full async ingestion and notification pipeline:
```bash
python main.py
```

---

## ⚙️ Automated CI/CD (GitHub Actions)

The pipeline runs automatically via [`.github/workflows/job_alert.yml`](file:///d:/Final%20Projects/JOB_ALERT/.github/workflows/job_alert.yml):
- **Schedule:** 4 times daily (`00:30`, `06:30`, `12:30`, `18:30` UTC = `06:00`, `12:00`, `18:00`, `00:00` IST).
- **State Caching:** Uses `actions/cache@v4` to restore and save the SQLite `jobs.db` across runs.
- **Fail-Safe CI:** Runs `pytest tests/ -v` before ingestion.
- **Audit Reports:** Generates Markdown/CSV job summaries and health logs, attached as run artifacts.
- **Manual Dispatch:** Supports `workflow_dispatch` with optional `dry_run` toggle.

---

## 📁 Repository Structure

```text
├── config/
│   ├── companies/           # 1,050+ company configurations across ATS providers
│   ├── keywords.json        # Target role and location definitions
│   ├── ignore_keywords.json # Exclusion lists (negative roles, foreign locations)
│   ├── scoring.json         # Heuristic ranking weights & multipliers
│   └── settings.py          # Central configuration & environment parser
├── core/
│   ├── filter_engine.py     # Algorithmic filtering & SDE validation
│   ├── metrics.py           # Latency, throughput, and error telemetry
│   ├── models.py            # Canonical JobListing dataclass
│   ├── ranking_engine.py    # Scoring, tech stack matching, and recency decay
│   ├── request_guard.py     # Pydantic validation & domain circuit breakers
│   ├── state_ledger.py      # SHA-256 fingerprinting & SQLite WAL storage
│   └── validator.py         # Career page reachability & auto-detection
├── database/
│   └── db_manager.py        # Connection-pooled async SQLite manager
├── notifiers/
│   ├── base.py              # Strategy-pattern abstract notifier
│   ├── console.py           # CLI table output formatter
│   └── telegram.py          # Async Telegram Bot API dispatcher
├── reports/
│   └── report_generator.py  # Markdown and CSV report generator
├── scrapers/
│   ├── base_scraper.py      # Abstract async HTTP base class with retry logic
│   ├── scraper_manager.py   # Concurrency orchestrator & host rate limiter
│   └── *.py                 # 18 dedicated ATS scrapers (Greenhouse, Lever, etc.)
├── tests/                   # 30 unit and integration tests
├── .env.example             # Template environment variables
├── .gitattributes           # Cross-platform LF line ending normalization
└── requirements.txt         # Pinned dependency specifications
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
