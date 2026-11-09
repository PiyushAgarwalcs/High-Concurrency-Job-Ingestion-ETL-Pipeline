"""
Ranking Engine for High-Concurrency Job Ingestion & ETL System.

Improvements:
- Salary bonus: +5 per LPA above 12 LPA
- Recency decay: jobs posted today 1.3x, decay over 7 days to 0.8x
- Indian Product and FinTech multipliers corrected for Bangalore market
- linkedin_easy_apply source multiplier added
"""

import logging
from datetime import datetime, timezone
from typing import List
from core.models import JobListing
from config.settings import SCORING_CONFIG

logger = logging.getLogger(__name__)

_MIN_SALARY_BONUS_LPA = 12
_SALARY_BONUS_PER_LPA = 5.0

# Recency: age_days -> multiplier
_RECENCY_TABLE = [
    (0,  1.30),
    (1,  1.20),
    (2,  1.10),
    (3,  1.00),
    (5,  0.90),
    (7,  0.80),
]


def _recency_multiplier(posting_date_str: str) -> float:
    if not posting_date_str:
        return 1.0
    try:
        dt = datetime.fromisoformat(str(posting_date_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - dt).days
        for max_age, mult in _RECENCY_TABLE:
            if age_days <= max_age:
                return mult
        return 0.75
    except Exception:
        return 1.0


def _salary_bonus(job: JobListing) -> float:
    lpa = job.estimated_salary_lpa
    if not lpa:
        return 0.0
    excess = max(0, lpa - _MIN_SALARY_BONUS_LPA)
    return excess * _SALARY_BONUS_PER_LPA


class RankingEngine:
    def __init__(self):
        self.resume_keywords       = SCORING_CONFIG.get("resume_keywords", {})
        self.category_multipliers  = SCORING_CONFIG.get("category_multipliers", {})
        self.source_multipliers    = SCORING_CONFIG.get("source_multipliers", {})

    def rank_jobs(self, jobs: List[JobListing]) -> List[JobListing]:
        for job in jobs:
            job.rank_score = self._calculate_score(job)
        return sorted(jobs, key=lambda x: x.rank_score, reverse=True)

    def _calculate_score(self, job: JobListing) -> float:
        score = 0.0

        # 1. Role priority base
        if job.role_priority == 1:
            score += 50.0
        elif job.role_priority == 2:
            score += 30.0
        elif job.role_priority == 3:
            score += 15.0

        # 2. Resume keyword match
        text = f"{job.job_title} {job.job_description_summary or ''}".lower()
        for kw, kw_score in self.resume_keywords.items():
            if kw.lower() in text:
                score += kw_score

        # 3. Salary bonus
        score += _salary_bonus(job)

        # 4. Source & category multipliers
        cat_mult = self.category_multipliers.get(job.company_category or "", 1.0)
        src_mult = self.source_multipliers.get(job.source_platform or "", 1.0)
        score = score * cat_mult * src_mult

        # 5. Recency multiplier applied last
        score = score * _recency_multiplier(job.posting_date or "")

        return round(score, 2)
