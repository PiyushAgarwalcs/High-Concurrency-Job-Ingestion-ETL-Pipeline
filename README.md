<div align="center">
  
# 🚀 AI/ML & Backend Software Engineering Job Discovery Pipeline V3

**A high-concurrency, pure backend data engineering system combining Async Concurrency, the DeployGuard Isolation Safety Gate, the OmniSight State Fingerprinting Engine, and an Integrated Telemetry Harness.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.14-E92063.svg)](https://docs.pydantic.dev/)
[![Asyncio](https://img.shields.io/badge/Asyncio-Concurrency-success.svg)](https://docs.python.org/3/library/asyncio.html)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg)](https://github.com/features/actions)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20WAL-003B57.svg)](https://sqlite.org/index.html)
[![Tests Passing](https://img.shields.io/badge/Tests-16%20Passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## 📖 Overview

Traditional job platforms (LinkedIn, Indeed) suffer from severe latency, ghost jobs, and applicant saturation. To gain a major competitive edge, this pipeline bypasses third-party boards entirely.

Instead, the system directly interrogates **300+ official company APIs and Applicant Tracking Systems (ATS)** (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, etc.) using `aiohttp` and `asyncio`, processes listings through **DeployGuard** safety gates, performs deterministic state deduplication via **OmniSight**, ranks jobs algorithmically, and delivers immediate real-time alerts.

---

## 🏗️ System Architecture & Data Flow

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      1. ASYNC INGESTION GATEWAY                        │
│ • Scheduled via Serverless GitHub Actions CRON (4x Daily)              │
│ • Manages async HTTP worker pool via aiohttp + asyncio.gather          │
│ • Direct ATS JSON queries (Greenhouse, Lever, Ashby, Workday, etc.)    │
│ • Enforces domain-aware throttling: 5/host semaphore, 30 global        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    2. THE DEPLOYGUARD LAYER (Safety Gate)              │
│ • Programmatic Pydantic v2 schema validation (`JobPayload`)            │
│ • URL tracking sanitizer: Strips UTM params, referral & affiliate tags │
│ • Non-tech title & spam quarantine                                    │
│ • Custom Circuit Breaker: 15-min cooldown on 3 consecutive 429/503s    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Validated Canonical Records)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 3. THE OMNISIGHT LAYER (Deduplication Fabric)          │
│ • Unicode NFKC normalization, whitespace squashing, case standardization│
│ • Cryptographic State Fingerprint: SHA-256(company : title : location) │
│ • High-Speed SQLite Ledger: Fast primary key indexing & size telemetry │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Brand New, Unseen Unique Listings)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  4. STRATEGY-PATTERN NOTIFIER & METRICS                │
│ • Strategy pattern: `BaseNotifier` -> `TelegramNotifier`, `Console`    │
│ • Real-time Telemetry: Sustained throughput (req/s), resilience rate,   │
│   deduplication %, schema compliance %, and database disk footprint    │
│ • Automatic GitHub Actions Step Summary markdown report generation     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Core Engineering Pillars

### 1. 🛡️ DeployGuard Safety Gate (`core/deployguard.py`)
- **Pydantic v2 Validation:** Programmatically inspects every incoming listing against the `JobPayload` schema. Rejects malformed titles, broken URLs, and invalid salaries.
- **URL Sanitization:** Normalizes all apply URLs by automatically stripping tracking queries (`utm_*`, `gh_src`, `lever-origin`, `ref`, `source`, `fbclid`).
- **Domain-Aware Circuit Breaker:** Implements a finite state machine (**CLOSED -> OPEN -> HALF-OPEN**) per ATS domain. Upon 3 consecutive HTTP 429, 503, or connection timeouts, trips open for 15 minutes, isolating the failing domain and shielding your IP from bans.

### 2. 🔍 OmniSight Deduplication Fabric (`core/omnisight.py`)
- **Canonical Text Normalization:** Cleans job titles (`"Software Development Engineer - I"` -> `"sde 1"`) and maps locations (`"Bengaluru, Karnataka"` -> `"bangalore"`).
- **Deterministic SHA-256 State Fingerprinting:** Formats a canonical composite string `company:title:location` and computes a 64-character SHA-256 digest. Identical positions cross-posted on different job boards yield the exact same fingerprint.
- **Indexed SQLite Ledger:** Fast O(1) query lookup table `job_fingerprints` with persistence across runs and automatic 90-day pruning policies.

### 3. 📊 OmniSight Telemetry & Observability (`core/metrics.py`)
- **Zero-Overhead Performance Instrumentation:** Uses `time.perf_counter()` to record end-to-end execution latency.
- **Quantitative Telemetry Metrics:**
  - Sustained throughput ($\text{req/s}$)
  - Upstream resilience rate ($\%$)
  - Schema compliance rate ($\%$)
  - Deduplication ratio ($\%$)
  - SQLite disk footprint ($\text{MB}$)
- **ASCII Executive Dashboard:** Outputs a structured ASCII report to `stdout` and injects rich Markdown summary tables into `$GITHUB_STEP_SUMMARY`.

### 4. 📬 Strategy-Pattern Notifier Engine (`notifiers/`)
- Abstract base class `BaseNotifier` with concrete strategies:
  - `TelegramNotifier`: Dispatches chunked, HTML-formatted cards with exponential retries.
  - `ConsoleNotifier`: Outputs structured CLI cards for dry runs, CI testing, and local development.

---

## 🧪 Comprehensive Test Suite

The pipeline includes a unit and integration test suite:

```bash
# Run the complete test suite
python -m pytest tests/ -v
```

```text
tests/test_deployguard.py::test_sanitize_url_removes_tracking_params PASSED
tests/test_deployguard.py::test_job_payload_valid PASSED
tests/test_deployguard.py::test_job_payload_rejects_placeholder_title PASSED
tests/test_deployguard.py::test_job_payload_rejects_invalid_url PASSED
tests/test_deployguard.py::test_job_payload_rejects_empty_company PASSED
tests/test_deployguard.py::test_circuit_breaker_transitions PASSED
tests/test_metrics.py::test_metrics_tracker_calculations PASSED
tests/test_metrics.py::test_metrics_tracker_zero_division_safety PASSED
tests/test_metrics.py::test_metrics_report_formatting PASSED
tests/test_omnisight.py::test_normalize_title PASSED
tests/test_omnisight.py::test_normalize_location PASSED
tests/test_omnisight.py::test_fingerprint_equivalence_across_variations PASSED
tests/test_omnisight.py::test_is_new_listing_and_duplicate_suppression PASSED
tests/test_omnisight.py::test_batch_check_and_register PASSED
tests/test_omnisight.py::test_db_size_reporting PASSED
tests/test_pipeline_integration.py::test_full_data_engineering_pipeline_flow PASSED
```

---

## 🚀 Quick Start (Local Setup)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/PiyushAgarwalcs/aiml_jobalert_bypa.git
   cd aiml_jobalert_bypa
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Unit Tests:**
   ```bash
   python -m pytest tests/ -v
   ```

4. **Execute Local Dry Run (Console Output):**
   ```bash
   python main.py --dry-run --console-notify
   ```

5. **Production Deployment with Telegram Alerts:**
   Configure environment variables:
   ```env
   TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
   TELEGRAM_CHAT_ID="your_telegram_chat_id"
   ```
   Run live:
   ```bash
   python main.py
   ```

---

## ⚡ Serverless CI/CD Automation

Automated via `.github/workflows/job_alert.yml` on an **Ubuntu runner**:
1. Checks out repository and sets up Python 3.12.
2. Restores persistent SQLite database cache across runs (`@actions/cache`).
3. Executes `pytest tests/ -v` to ensure zero regressions.
4. Executes `python main.py` to scrape upstreams, isolate errors, and notify Telegram.
5. Emits the OmniSight Telemetry Report directly to GitHub Actions Step Summaries.
6. Uploads daily Markdown/CSV audit reports as build artifacts.

---

## 📄 License
Licensed under the [MIT License](LICENSE).
