"""
Integration tests for the complete V3 Pipeline (DeployGuard + OmniSight + Strategy Notifier).
"""

import os
import tempfile
import pytest
from core.deployguard import JobPayload, CircuitBreaker
from core.omnisight import OmniSightEngine
from core.metrics import MetricsTracker
from core.models import JobListing
from notifiers.console import ConsoleNotifier


def test_full_data_engineering_pipeline_flow():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db = tf.name

    try:
        # 1. Metrics Tracker Init
        metrics = MetricsTracker()
        metrics.start()

        # 2. DeployGuard Circuit Breaker Init
        circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        assert circuit_breaker.can_execute("greenhouse.io") is True

        # 3. Raw Incoming Data
        raw_scraped_records = [
            {
                "company_name": "Acme Technologies",
                "job_title": "Software Engineer - I",
                "location": "Bengaluru, India",
                "apply_url": "https://boards.greenhouse.io/acme/jobs/101?gh_src=linkedin&utm_source=social",
                "source_platform": "greenhouse",
            },
            # Exact duplicate with different tracking params and title spacing
            {
                "company_name": "acme technologies",
                "job_title": "SDE 1",
                "location": "Bangalore",
                "apply_url": "https://boards.greenhouse.io/acme/jobs/101?utm_campaign=winter",
                "source_platform": "greenhouse",
            },
            # Malformed item to test quarantine
            {
                "company_name": "Spam Corp",
                "job_title": "test",  # rejected by non-job regex
                "location": "Remote",
                "apply_url": "https://example.com/spam",
            },
            # Unique listing
            {
                "company_name": "Zeta Labs",
                "job_title": "AI/ML Engineer",
                "location": "Remote",
                "apply_url": "https://jobs.ashbyhq.com/zeta/202",
                "source_platform": "ashby",
            }
        ]

        metrics.total_endpoints = 2
        metrics.raw_jobs_count = len(raw_scraped_records)

        # 4. DeployGuard Validation & Quarantine Gate
        validated_listings = []
        for raw in raw_scraped_records:
            try:
                payload = JobPayload(**raw)
                validated_listings.append(payload.to_job_listing())
                metrics.successful_fetches += 1
            except Exception:
                metrics.schema_quarantined_count += 1

        assert len(validated_listings) == 3  # 1 quarantined
        assert metrics.schema_quarantined_count == 1

        # 5. OmniSight Deduplication
        omnisight = OmniSightEngine(temp_db)
        candidates = [item.to_dict() for item in validated_listings]
        new_items, duplicates = omnisight.batch_check_and_register(candidates)

        metrics.duplicates_filtered = duplicates
        metrics.new_jobs_identified = len(new_items)

        # 2 unique listings: Acme Technologies + Zeta Labs
        assert len(new_items) == 2
        assert duplicates == 1

        # 6. Console Notifier Strategy
        notifier = ConsoleNotifier()
        assert notifier.test_connection() is True
        job_listings = [JobListing.from_dict(item) for item in new_items]
        notified = notifier.send_job_alerts(job_listings, {"total_sources": 2, "successful_sources": 2})
        assert notified is True
        metrics.notifications_dispatched = len(new_items)

        # 7. Telemetry Metrics Stop & Verify
        metrics.stop()
        db_size = omnisight.get_db_size_mb()
        report = metrics.format_summary_report(db_size)

        assert "DeployGuard & OmniSight V3" in report
        assert "25.0% (1 duplicate listings)" in report
        assert "75.0% (1 quarantined records)" in report

    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)
