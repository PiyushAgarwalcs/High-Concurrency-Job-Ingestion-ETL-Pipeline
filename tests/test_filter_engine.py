"""
Unit tests for FilterEngine.
Verifies role acceptance, negative keyword rejection, experience boundaries,
SDE validation, and location filtering.
"""

import pytest
from core.models import JobListing
from core.filter_engine import FilterEngine


@pytest.fixture
def filter_engine():
    return FilterEngine()


def _make_job(
    title: str = "Software Engineer",
    company: str = "Test Co",
    location: str = "Bangalore",
    desc: str = "Building backend data services in Python",
    exp: str = "0-1 years",
    source: str = "greenhouse",
    salary_lpa: int = None,
) -> JobListing:
    return JobListing(
        company_name=company,
        job_title=title,
        location=location,
        apply_url="https://example.com/apply/1",
        source_platform=source,
        job_description_summary=desc,
        experience_required=exp,
        estimated_salary_lpa=salary_lpa,
    )


def test_rejects_negative_roles(filter_engine):
    # Senior / Lead roles should be dropped
    senior_job = _make_job(title="Senior Machine Learning Engineer")
    assert filter_engine._has_negative_role(senior_job) is True

    lead_job = _make_job(title="Staff Backend Engineer")
    assert filter_engine._has_negative_role(lead_job) is True

    frontend_job = _make_job(title="Frontend Engineer")
    assert filter_engine._has_negative_role(frontend_job) is True

    # Acceptable fresher/junior role should NOT trigger negative role
    fresher_job = _make_job(title="Junior AI Engineer")
    assert filter_engine._has_negative_role(fresher_job) is False


def test_role_priority_classification(filter_engine):
    # AI/ML should get priority 1
    ai_job = _make_job(title="Machine Learning Engineer")
    assert filter_engine._get_role_priority(ai_job) == 1

    genai_job = _make_job(title="Generative AI Engineer")
    assert filter_engine._get_role_priority(genai_job) == 1

    # Standard backend / software developer should get priority 2
    sde_job = _make_job(title="Backend Engineer")
    assert filter_engine._get_role_priority(sde_job) == 2

    # Irrelevant role should return None
    sales_job = _make_job(title="Account Executive")
    assert filter_engine._get_role_priority(sales_job) is None


def test_generic_sde_validation(filter_engine):
    # Generic SDE without AI/ML/DSA keywords in description should fail validation
    plain_sde = _make_job(
        title="Software Engineer",
        desc="Managing customer relations and billing paperwork."
    )
    assert filter_engine._is_generic_sde(plain_sde) is True
    assert filter_engine._has_sde_validation(plain_sde) is False

    # Generic SDE with DSA/AI keywords in description should pass validation
    ml_sde = _make_job(
        title="Software Development Engineer",
        desc="Developing high-throughput data pipelines using Python, PyTorch, and algorithms."
    )
    assert filter_engine._is_generic_sde(ml_sde) is True
    assert filter_engine._has_sde_validation(ml_sde) is True


def test_experience_filtering_boundaries(filter_engine):
    # 0-2 years should pass
    fresher_job = _make_job(exp="0-2 years")
    assert filter_engine._exceeds_experience(fresher_job) is False

    # 4+ years should be rejected
    experienced_job = _make_job(exp="4+ years of industry experience")
    assert filter_engine._exceeds_experience(experienced_job) is True

    # Substring false positive guard: 'Python 3+' in description should NOT be rejected
    python3_job = _make_job(
        exp="Fresher",
        desc="Requires experience with Python 3+ and modern SQL."
    )
    assert filter_engine._exceeds_experience(python3_job) is False


def test_location_filtering(filter_engine):
    # Bangalore, Remote, India should be accepted
    assert filter_engine._is_acceptable_location(_make_job(location="Bengaluru, India")) is True
    assert filter_engine._is_acceptable_location(_make_job(location="Remote")) is True
    assert filter_engine._is_acceptable_location(_make_job(location="")) is True

    # Foreign locations should be rejected
    assert filter_engine._is_acceptable_location(_make_job(location="San Francisco, USA")) is False
    assert filter_engine._is_acceptable_location(_make_job(location="London, UK")) is False


def test_linkedin_salary_floor(filter_engine):
    # Low salary on LinkedIn Easy Apply should be filtered out
    low_salary_job = _make_job(
        title="AI Engineer",
        desc="PyTorch models",
        source="linkedin_easy_apply",
        salary_lpa=8
    )
    filtered = filter_engine.filter_jobs([low_salary_job])
    assert len(filtered) == 0

    # High salary on LinkedIn Easy Apply should pass
    good_salary_job = _make_job(
        title="AI Engineer",
        desc="PyTorch models",
        source="linkedin_easy_apply",
        salary_lpa=16
    )
    filtered = filter_engine.filter_jobs([good_salary_job])
    assert len(filtered) == 1

