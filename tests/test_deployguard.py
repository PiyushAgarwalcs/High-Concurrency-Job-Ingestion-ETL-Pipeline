"""
Unit tests for DeployGuard Safety Gate & Circuit Breaker Engine.
"""

import time
import pytest
from core.deployguard import JobPayload, CircuitBreaker, sanitize_url


def test_sanitize_url_removes_tracking_params():
    raw_url = "https://boards.greenhouse.io/openai/jobs/12345?gh_src=linkedin&utm_source=feed&utm_campaign=winter#application"
    clean = sanitize_url(raw_url)
    assert "gh_src" not in clean
    assert "utm_source" not in clean
    assert "utm_campaign" not in clean
    assert "#application" not in clean
    assert clean == "https://boards.greenhouse.io/openai/jobs/12345"


def test_job_payload_valid():
    data = {
        "company_name": "Google",
        "job_title": "Software Engineer, Early Career",
        "location": "Bengaluru, India",
        "apply_url": "https://careers.google.com/jobs/results/123/?utm_source=jobboard",
        "source_platform": "official",
        "ats_provider": "custom",
    }
    payload = JobPayload(**data)
    assert payload.company_name == "Google"
    assert payload.job_title == "Software Engineer, Early Career"
    assert "utm_source" not in str(payload.apply_url)


def test_job_payload_rejects_placeholder_title():
    data = {
        "company_name": "Acme Corp",
        "job_title": "test",
        "apply_url": "https://example.com/jobs/1",
    }
    with pytest.raises(ValueError, match="rejected as invalid placeholder"):
        JobPayload(**data)


def test_job_payload_rejects_invalid_url():
    data = {
        "company_name": "Acme Corp",
        "job_title": "Software Engineer",
        "apply_url": "not-a-valid-url",
    }
    with pytest.raises(ValueError, match="Invalid URL scheme"):
        JobPayload(**data)


def test_job_payload_rejects_empty_company():
    data = {
        "company_name": "   ",
        "job_title": "Software Engineer",
        "apply_url": "https://example.com/jobs/1",
    }
    with pytest.raises(ValueError, match="Company name must not be blank"):
        JobPayload(**data)


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=1)
    domain = "https://api.lever.co/v0/postings/test"

    # Initially closed
    assert cb.can_execute(domain) is True

    # 1st failure
    cb.record_failure(domain, "HTTP 503")
    assert cb.can_execute(domain) is True

    # 2nd failure
    cb.record_failure(domain, "HTTP 429")
    assert cb.can_execute(domain) is True

    # 3rd failure -> Breaker trips OPEN
    cb.record_failure(domain, "HTTP 429")
    assert cb.can_execute(domain) is False
    assert cb.is_open(domain) is True

    # Check stats
    stats = cb.get_stats()
    assert stats["open_circuits_count"] == 1
    assert "api.lever.co" in stats["open_circuits"]

    # Sleep past cooldown (1.1s)
    time.sleep(1.1)

    # Cooldown expired -> transitions to Half-Open and allows probe
    assert cb.can_execute(domain) is True

    # Successful probe -> Circuit closes
    cb.record_success(domain)
    assert cb.can_execute(domain) is True
    assert cb.is_open(domain) is False
    assert cb.get_stats()["open_circuits_count"] == 0

