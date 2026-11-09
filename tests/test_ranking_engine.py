"""
Unit tests for RankingEngine.
Verifies base score calculation, keyword scoring, salary bonuses,
recency decay, and overall sorting behavior.
"""

from datetime import datetime, timezone, timedelta
import pytest
from core.models import JobListing
from core.ranking_engine import RankingEngine, _recency_multiplier, _salary_bonus


@pytest.fixture
def ranking_engine():
    return RankingEngine()


def _make_job(
    title: str = "AI Engineer",
    company: str = "Acme AI",
    role_priority: int = 1,
    desc: str = "Machine Learning and Python",
    salary_lpa: int = None,
    category: str = "top_ai",
    source: str = "greenhouse",
    posting_date: str = None,
) -> JobListing:
    return JobListing(
        company_name=company,
        job_title=title,
        location="Bangalore",
        apply_url="https://example.com/job/1",
        role_priority=role_priority,
        job_description_summary=desc,
        estimated_salary_lpa=salary_lpa,
        company_category=category,
        source_platform=source,
        posting_date=posting_date,
    )


def test_role_priority_base_scores(ranking_engine):
    job_p1 = _make_job(role_priority=1, desc="", category="other", source="other")
    job_p2 = _make_job(role_priority=2, desc="", category="other", source="other")
    job_p3 = _make_job(role_priority=3, desc="", category="other", source="other")
    job_p4 = _make_job(role_priority=4, desc="", category="other", source="other")

    score_p1 = ranking_engine._calculate_score(job_p1)
    score_p2 = ranking_engine._calculate_score(job_p2)
    score_p3 = ranking_engine._calculate_score(job_p3)
    score_p4 = ranking_engine._calculate_score(job_p4)

    assert score_p1 > score_p2 > score_p3 > score_p4


def test_salary_bonus_calculation():
    job_low = _make_job(salary_lpa=10)
    assert _salary_bonus(job_low) == 0.0

    job_threshold = _make_job(salary_lpa=12)
    assert _salary_bonus(job_threshold) == 0.0

    # 18 LPA: (18 - 12) * 5.0 = 30.0
    job_high = _make_job(salary_lpa=18)
    assert _salary_bonus(job_high) == 30.0


def test_recency_multiplier_decay():
    now = datetime.now(timezone.utc)

    # Today: 1.30x
    today_str = now.isoformat()
    assert _recency_multiplier(today_str) == 1.30

    # 1 day ago: 1.20x
    one_day_ago = (now - timedelta(days=1)).isoformat()
    assert _recency_multiplier(one_day_ago) == 1.20

    # 10 days ago: 0.75x (floor)
    old_date = (now - timedelta(days=10)).isoformat()
    assert _recency_multiplier(old_date) == 0.75

    # None / Empty: 1.0x neutral
    assert _recency_multiplier("") == 1.0


def test_rank_jobs_orders_highest_score_first(ranking_engine):
    low_job = _make_job(title="Junior Developer", role_priority=2, desc="", salary_lpa=6)
    high_job = _make_job(title="AI Engineer", role_priority=1, desc="Python PyTorch Generative AI", salary_lpa=25)

    ranked = ranking_engine.rank_jobs([low_job, high_job])
    assert len(ranked) == 2
    assert ranked[0].job_title == "AI Engineer"
    assert ranked[0].rank_score > ranked[1].rank_score

