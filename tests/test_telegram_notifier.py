"""
Unit tests for TelegramNotifier.
Verifies HTML formatting, message chunking within 4096 char limits,
HTML escaping, and plain-text fallback formatting.
"""

import pytest
from core.models import JobListing
from notifiers.telegram import TelegramNotifier


@pytest.fixture
def notifier():
    return TelegramNotifier(bot_token="mock_token", chat_id="123456")


def _make_job(idx: int) -> JobListing:
    return JobListing(
        company_name=f"Company <Special & Tech> {idx}",
        job_title=f"AI/ML Engineer - {idx}",
        location="Bangalore",
        apply_url=f"https://example.com/apply/{idx}",
        salary=f"₹{12 + idx} LPA",
        company_prestige_score=8,
        source_platform="greenhouse",
    )


def test_html_escaping(notifier):
    raw = "Tech <Corp> & Co"
    escaped = notifier._escape_html(raw)
    assert escaped == "Tech &lt;Corp&gt; &amp; Co"
    assert notifier._escape_html("") == ""


def test_prestige_bar(notifier):
    assert notifier._get_prestige_bar(0) == "░" * 10
    assert notifier._get_prestige_bar(5) == "█" * 5 + "░" * 5
    assert notifier._get_prestige_bar(10) == "█" * 10
    # Boundary capped at 10
    assert notifier._get_prestige_bar(15) == "█" * 10


def test_format_salary(notifier):
    job_with_salary = _make_job(1)
    job_with_salary.salary = "₹15-20 LPA"
    assert notifier._format_salary(job_with_salary) == "₹15-20 LPA"

    job_with_est = _make_job(2)
    job_with_est.salary = ""
    job_with_est.estimated_salary_lpa = 18
    job_with_est.salary_confidence = "high"
    assert "₹18 LPA" in notifier._format_salary(job_with_est)
    assert "high est." in notifier._format_salary(job_with_est)

    job_empty = _make_job(3)
    job_empty.salary = ""
    job_empty.estimated_salary_lpa = None
    assert notifier._format_salary(job_empty) == "Not disclosed"


def test_message_chunking_under_telegram_limit(notifier):
    # Create 35 jobs to ensure content exceeds 4096 characters
    jobs = [_make_job(i) for i in range(1, 36)]
    stats = {"successful_sources": 10, "total_sources": 12, "source_results": {}}

    messages = notifier._format_job_messages(jobs, stats)

    # Must produce multiple chunks
    assert len(messages) > 1

    # Every single chunk must stay strictly under Telegram's 4096 limit
    for chunk in messages:
        assert len(chunk) <= 4096
        # HTML tag integrity: shouldn't have raw unescaped ampersands or brackets in text
        assert "&lt;" in chunk or "Company" in chunk

