"""
Unit tests for Pipeline Metrics Tracker & Telemetry Harness.
"""

import time
import pytest
from core.metrics import MetricsTracker


def test_metrics_tracker_calculations():
    tracker = MetricsTracker()
    tracker.start()
    time.sleep(0.05)
    tracker.stop()

    tracker.total_endpoints = 50
    tracker.successful_fetches = 48
    tracker.http_errors_isolated = 2
    tracker.circuit_breaker_trips = 1
    tracker.raw_jobs_count = 200
    tracker.schema_quarantined_count = 10
    tracker.duplicates_filtered = 150
    tracker.new_jobs_identified = 40
    tracker.notifications_dispatched = 20

    duration = tracker.get_duration()
    assert duration >= 0.04

    throughput = tracker.get_throughput()
    assert throughput > 0.0

    resilience = tracker.get_resilience_rate()
    # 48 / 50 = 96.0%
    assert resilience == pytest.approx(96.0, rel=1e-2)

    dedup = tracker.get_dedup_rate()
    # 150 / 200 = 75.0%
    assert dedup == pytest.approx(75.0, rel=1e-2)

    compliance = tracker.get_schema_compliance_rate()
    # (200 - 10) / 200 = 95.0%
    assert compliance == pytest.approx(95.0, rel=1e-2)


def test_metrics_tracker_zero_division_safety():
    empty_tracker = MetricsTracker()
    # No calls made yet
    assert empty_tracker.get_throughput() == 0.0
    assert empty_tracker.get_resilience_rate() == 100.0
    assert empty_tracker.get_dedup_rate() == 0.0
    assert empty_tracker.get_schema_compliance_rate() == 100.0


def test_metrics_report_formatting():
    tracker = MetricsTracker()
    tracker.total_endpoints = 20
    tracker.successful_fetches = 20
    tracker.raw_jobs_count = 100
    report = tracker.format_summary_report(db_size_mb=1.25)
    assert "PIPELINE EXECUTION METRICS" in report
    assert "RequestGuard Resilience" in report
    assert "1.25 MB" in report

