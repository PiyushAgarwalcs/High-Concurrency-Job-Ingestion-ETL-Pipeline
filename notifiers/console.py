"""
Console / Terminal Notifier implementing the BaseNotifier strategy.
Outputs clean Markdown / text tables for dry runs and local execution.
"""

import logging
from typing import List, Dict, Any
from core.models import JobListing
from notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class ConsoleNotifier(BaseNotifier):
    """Outputs job listings directly to stdout in a clean structured format."""

    async def test_connection(self) -> bool:
        """Always reachable."""
        return True

    async def send_job_alerts(
        self,
        new_jobs: List[JobListing],
        stats: Dict[str, Any],
    ) -> bool:
        """Format and print alerts to console."""
        print("\n" + "=" * 65)
        print("📢 [Console Notifier] NEW JOB DISCOVERIES ALERT")
        print("=" * 65)
        if not new_jobs:
            print("ℹ️  No new listings identified in this cycle.")
            print("=" * 65 + "\n")
            return True

        for idx, job in enumerate(new_jobs, 1):
            salary = job.salary or (f"~{job.estimated_salary_lpa} LPA" if job.estimated_salary_lpa else "Not specified")
            print(f"[{idx:>2}] {job.company_name} | {job.job_title}")
            print(f"     📍 Location: {job.location} | 💰 Salary: {salary}")
            print(f"     🔗 Apply: {job.apply_url}")
            print(f"     🏷️  Platform: {job.source_platform} ({job.ats_provider})")
            print("-" * 65)
        print("=" * 65 + "\n")
        return True

