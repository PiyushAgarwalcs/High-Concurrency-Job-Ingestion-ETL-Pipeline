"""
Unit tests for RequestGuard Safety Gate & Circuit Breaker Engine.
"""

import time
import pytest
from core.request_guard import JobSchema, CircuitBreaker, clean_url


def test_clean_url_removes_tracking_params():
    raw_url = "https://boards.greenhouse.io/openai/jobs/12345?gh_src=linkedin&utm_source=feed&utm_campaign=winter#application"
    cleaned = clean_url(raw_url)
    assert "gh_src" not in cleaned
    assert "utm_source" not in cleaned
    assert "utm_campaign" not in cleaned
    assert "#application" not in cleaned
    assert cleaned == "https://boards.greenhouse.io/openai/jobs/12345"


def test_job_schema_valid():
    data = {
        "company_name": "Google",
        "job_title": "Software Engineer, Early Career",
        "location": "Bengaluru, India",
        "apply_url": "https://careers.google.com/jobs/results/123/?utm_source=jobboard",
        "source_platform": "official",
        "ats_provider": "custom",
    }
    schema = JobSchema(**data)
    assert schema.company_name == "Google"
    assert schema.job_title == "Software Engineer, Early Career"
    assert "utm_source" not in str(schema.apply_url)


def test_job_schema_rejects_placeholder_title():
    data = {
        "company_name": "Acme Corp",
        "job_title": "test",
        "apply_url": "https://example.com/jobs/1",
    }
    with pytest.raises(ValueError, match="rejected as invalid placeholder"):
        JobSchema(**data)


def test_job_schema_rejects_invalid_url():
    data = {
        "company_name": "Acme Corp",
        "job_title": "Software Engineer",
        "apply_url": "not-a-valid-url",
    }
    with pytest.raises(ValueError, match="Invalid URL scheme"):
        JobSchema(**data)


def test_job_schema_rejects_empty_company():
    data = {
        "company_name": "   ",
        "job_title": "Software Engineer",
        "apply_url": "https://example.com/jobs/1",
    }
    with pytest.raises(ValueError, match="Company name must not be blank"):
        JobSchema(**data)


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=1)
    domain = "https://api.lever.co/v0/postings/test"

    # Initially closed (allowed)
    assert cb.can_request(domain) is True
    assert cb.can_execute(domain) is True

    # 1st failure
    cb.record_failure(domain, "HTTP 503")
    assert cb.can_request(domain) is True

    # 2nd failure
    cb.record_failure(domain, "HTTP 429")
    assert cb.can_request(domain) is True

    # 3rd failure -> Breaker trips OPEN
    cb.record_failure(domain, "HTTP 429")
    assert cb.can_request(domain) is False
    assert cb.is_blocked(domain) is True

    # Check stats
    stats = cb.get_status_summary()
    assert stats["blocked_domains_count"] == 1
    assert "api.lever.co" in stats["blocked_domains"]

    # Sleep past cooldown (1.1s)
    time.sleep(1.1)

    # Cooldown expired -> transitions to Half-Open and allows probe
    assert cb.can_request(domain) is True

    # Successful probe -> Circuit closes
    cb.record_success(domain)
    assert cb.can_request(domain) is True
    assert cb.is_blocked(domain) is False
    assert cb.get_status_summary()["blocked_domains_count"] == 0

