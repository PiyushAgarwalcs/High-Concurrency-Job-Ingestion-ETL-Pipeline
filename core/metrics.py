"""
OmniSight Telemetry & Metrics Instrumentation Harness.
Tracks execution timing, throughput (req/sec), upstream resilience %,
schema quarantine rates, deduplication efficiency %, and SQLite footprint.

Produces structured ASCII executive reports for stdout and GitHub Actions Step Summaries.
"""

import os
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MetricsTracker:
    """
    High-precision pipeline instrumentation tracker.
    Zero-overhead, in-memory counter and timer registry.
    """

    def __init__(self):
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.total_endpoints: int = 0
        self.successful_fetches: int = 0
        self.http_errors_isolated: int = 0
        self.circuit_breaker_trips: int = 0
        self.raw_jobs_count: int = 0
        self.schema_quarantined_count: int = 0
        self.duplicates_filtered: int = 0
        self.new_jobs_identified: int = 0
        self.notifications_dispatched: int = 0

    def start(self):
        """Start execution performance counter."""
        self.start_time = time.perf_counter()

    def stop(self):
        """Stop execution performance counter."""
        self.end_time = time.perf_counter()

    def get_duration(self) -> float:
        """Return total elapsed time in seconds."""
        if self.end_time <= self.start_time:
            return max(time.perf_counter() - self.start_time, 0.001)
        return max(self.end_time - self.start_time, 0.001)

    def get_sustained_throughput(self) -> float:
        """Calculate sustained request throughput in endpoints/second."""
        duration = self.get_duration()
        return self.total_endpoints / duration if duration > 0 else 0.0

    def get_resilience_rate(self) -> float:
        """
        Calculate upstream resilience % (percentage of endpoints fetched
        without unhandled failure or rate-limit IP ban).
        """
        total_attempts = self.successful_fetches + self.http_errors_isolated
        if total_attempts == 0:
            return 100.0
        return (self.successful_fetches / total_attempts) * 100.0

    def get_dedup_rate(self) -> float:
        """Calculate percentage of incoming listings filtered as duplicate."""
        if self.raw_jobs_count == 0:
            return 0.0
        return (self.duplicates_filtered / self.raw_jobs_count) * 100.0

    def get_schema_compliance_rate(self) -> float:
        """Calculate percentage of raw listings passing DeployGuard Pydantic schema."""
        if self.raw_jobs_count == 0:
            return 100.0
        valid_count = max(self.raw_jobs_count - self.schema_quarantined_count, 0)
        return (valid_count / self.raw_jobs_count) * 100.0

    def to_dict(self, db_size_mb: float = 0.0) -> Dict[str, Any]:
        """Serialize metrics into dictionary for persistent logs and JSON reports."""
        return {
            "duration_seconds": round(self.get_duration(), 2),
            "total_endpoints": self.total_endpoints,
            "successful_fetches": self.successful_fetches,
            "http_errors_isolated": self.http_errors_isolated,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "throughput_req_sec": round(self.get_sustained_throughput(), 2),
            "resilience_rate_pct": round(self.get_resilience_rate(), 1),
            "raw_jobs_count": self.raw_jobs_count,
            "schema_quarantined_count": self.schema_quarantined_count,
            "schema_compliance_pct": round(self.get_schema_compliance_rate(), 1),
            "duplicates_filtered": self.duplicates_filtered,
            "dedup_rate_pct": round(self.get_dedup_rate(), 1),
            "new_jobs_identified": self.new_jobs_identified,
            "notifications_dispatched": self.notifications_dispatched,
            "sqlite_db_size_mb": round(db_size_mb, 2),
        }

    def format_summary_report(self, db_size_mb: float = 0.0) -> str:
        """Format an ASCII executive telemetry report."""
        duration = self.get_duration()
        throughput = self.get_sustained_throughput()
        resilience = self.get_resilience_rate()
        dedup_rate = self.get_dedup_rate()
        compliance = self.get_schema_compliance_rate()

        border = "═" * 68
        lines = [
            f"╔{border}╗",
            f"║ 📊 PIPELINE EXECUTION TELEMETRY (DeployGuard & OmniSight V3)     ║",
            f"╠{border}╣",
            f"║ ⏱️  Total Duration          : {duration:>6.2f} seconds                            ║",
            f"║ 🚀 Sustained Throughput    : {throughput:>6.2f} req/s across {self.total_endpoints:<4} endpoints       ║",
            f"║ 🛡️  DeployGuard Resilience  : {resilience:>6.1f}% uptime ({self.http_errors_isolated:<2} isolated errors)     ║",
            f"║ ⚡ Circuit Breaker Trips   : {self.circuit_breaker_trips:>6} domains protected                  ║",
            f"║ 🔒 Schema Compliance       : {compliance:>6.1f}% ({self.schema_quarantined_count} quarantined records)      ║",
            f"║ 🔍 OmniSight Deduplication : {dedup_rate:>6.1f}% ({self.duplicates_filtered} duplicate listings)       ║",
            f"║ 🆕 Brand New Jobs Found    : {self.new_jobs_identified:>6} listings                           ║",
            f"║ 📢 Alerts Dispatched       : {self.notifications_dispatched:>6} notifications                      ║",
            f"║ 💾 SQLite Ledger Footprint : {db_size_mb:>6.2f} MB                                ║",
            f"╚{border}╝",
        ]
        return "\n" + "\n".join(lines) + "\n"

    def print_summary_report(self, db_size_mb: float = 0.0):
        """Print executive telemetry report to standard output."""
        print(self.format_summary_report(db_size_mb))

    def write_github_step_summary(self, db_size_mb: float = 0.0):
        """
        Append structured telemetry summary to GitHub Actions Step Summary
        ($GITHUB_STEP_SUMMARY) when running in CI/CD.
        """
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_file:
            return

        try:
            duration = self.get_duration()
            throughput = self.get_sustained_throughput()
            resilience = self.get_resilience_rate()
            dedup_rate = self.get_dedup_rate()
            compliance = self.get_schema_compliance_rate()

            markdown_content = f"""
### 📊 DeployGuard & OmniSight Pipeline Execution Report

| Metric | Measured Value | Operational Status |
| :--- | :--- | :--- |
| **Duration** | `{duration:.2f} s` | ✅ Completed |
| **Throughput** | `{throughput:.2f} req/s` | 🚀 {self.total_endpoints} Endpoints |
| **DeployGuard Resilience** | `{resilience:.1f}%` | 🛡️ {self.http_errors_isolated} Isolated Errors |
| **Circuit Breaker Trips** | `{self.circuit_breaker_trips}` | ⚡ Domains Quarantined |
| **Schema Compliance** | `{compliance:.1f}%` | 🔒 {self.schema_quarantined_count} Malformed |
| **OmniSight Dedup Rate** | `{dedup_rate:.1f}%` | 🔍 {self.duplicates_filtered} Filtered |
| **New Job Discoveries** | `{self.new_jobs_identified}` | 🆕 Unique Alerts |
| **Notifications Dispatched** | `{self.notifications_dispatched}` | 📢 Dispatched |
| **SQLite State Footprint** | `{db_size_mb:.2f} MB` | 💾 Persistent Cache |
"""
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write(markdown_content)
            logger.info("✓ Written telemetry metrics to GITHUB_STEP_SUMMARY")
        except Exception as e:
            logger.warning(f"Failed to write GITHUB_STEP_SUMMARY: {e}")

