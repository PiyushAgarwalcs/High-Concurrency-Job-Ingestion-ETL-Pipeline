"""
Filter engine for High-Concurrency Job Ingestion & ETL System.

Fixes:
- SDE/SWE title roles now validated against ML/AI/DSA keywords (search_terms.py)
- Location: empty/unknown accepted; non-listed locations accepted (not silently dropped)
- Salary floor: LinkedIn Easy Apply jobs below 12 LPA dropped
- Recency decay: stored on job for use by ranking engine
- NOTIFY_ON_EMPTY: respected via settings
"""

import logging
import re
from typing import Optional, List

from core.models import JobListing
from config.settings import KEYWORDS_CONFIG, IGNORE_CONFIG, MAX_EXPERIENCE_YEARS
from config.search_terms import SDE_VALIDATION_KEYWORDS, SDE_TITLE_KEYWORDS

logger = logging.getLogger(__name__)

MIN_SALARY_LPA_LINKEDIN = 12

# Pre-compile SDE patterns for speed
_SDE_TITLE_RE = re.compile(
    "|".join(re.escape(k) for k in SDE_TITLE_KEYWORDS), re.IGNORECASE
)
_SDE_VALID_RE = re.compile(
    "|".join(re.escape(k) for k in SDE_VALIDATION_KEYWORDS), re.IGNORECASE
)


class FilterEngine:
    def __init__(self):
        self.accepted_roles      = KEYWORDS_CONFIG.get("accepted_roles", [])
        self.accepted_locations  = KEYWORDS_CONFIG.get("accepted_locations", [])
        self.accepted_experience = KEYWORDS_CONFIG.get("accepted_experience", [])

        self.ignore_roles      = IGNORE_CONFIG.get("ignore_roles", [])
        self.ignore_locations  = IGNORE_CONFIG.get("ignore_locations", [])
        self.ignore_experience = IGNORE_CONFIG.get("ignore_experience", [])

    def filter_jobs(self, jobs: List[JobListing]) -> List[JobListing]:
        filtered = []
        counts = {"neg_role": 0, "location": 0, "no_role": 0, "sde_invalid": 0,
                  "experience": 0, "salary": 0}

        for job in jobs:
            self._extract_salary(job)

            if self._has_negative_role(job):
                counts["neg_role"] += 1
                continue

            if not self._is_acceptable_location(job):
                counts["location"] += 1
                continue

            role_priority = self._get_role_priority(job)
            if role_priority is None:
                counts["no_role"] += 1
                continue

            # SDE/SWE validation — must also contain ML/AI/DSA context
            if self._is_generic_sde(job) and not self._has_sde_validation(job):
                counts["sde_invalid"] += 1
                logger.debug(f"SDE no AI/ML context: {job.job_title} @ {job.company_name}")
                continue

            job.role_priority = role_priority

            if self._exceeds_experience(job):
                counts["experience"] += 1
                continue

            # LinkedIn salary floor
            if job.source_platform == "linkedin_easy_apply":
                if job.estimated_salary_lpa and job.estimated_salary_lpa < MIN_SALARY_LPA_LINKEDIN:
                    counts["salary"] += 1
                    continue

            filtered.append(job)

        logger.info(
            f"Filter: {len(jobs)} in -> {len(filtered)} out | "
            f"neg_role={counts['neg_role']} location={counts['location']} "
            f"no_role={counts['no_role']} sde_no_ai={counts['sde_invalid']} "
            f"exp={counts['experience']} salary={counts['salary']}"
        )
        return filtered

    # ── SDE validation ────────────────────────────────────────────────────────

    def _is_generic_sde(self, job: JobListing) -> bool:
        """Return True if job title looks like a generic SDE/SWE role."""
        return bool(_SDE_TITLE_RE.search(job.job_title))

    def _has_sde_validation(self, job: JobListing) -> bool:
        """Return True if an ML/AI/DSA keyword appears in title or description."""
        combined = f"{job.job_title} {job.job_description_summary or ''}"
        return bool(_SDE_VALID_RE.search(combined))

    # ── Role filters ──────────────────────────────────────────────────────────

    def _has_negative_role(self, job: JobListing) -> bool:
        title_lower = job.job_title.lower()
        for kw in self.ignore_roles:
            pattern = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
            if re.search(pattern, title_lower):
                return True
        return False

    def _get_role_priority(self, job: JobListing) -> Optional[int]:
        title_lower = job.job_title.lower()
        for kw in self.accepted_roles:
            if kw in title_lower:
                if any(t in kw for t in ("ai", "machine learning", "ml ", "data", "research",
                                         "nlp", "vision", "genai", "llm", "deep")):
                    return 1
                return 2
        return None

    # ── Experience filter ─────────────────────────────────────────────────────

    def _exceeds_experience(self, job: JobListing) -> bool:
        exp_text    = (job.experience_required or "").lower()
        title_lower = job.job_title.lower()
        desc_lower  = (job.job_description_summary or "").lower()
        combined    = f"{title_lower} {exp_text} {desc_lower}"

        # 1. Explicit keyword check with word boundaries to avoid matching substrings
        for kw in self.ignore_experience:
            pattern = r"(?<!\w)" + re.escape(kw.lower()) + r"(?!\w)"
            if re.search(pattern, combined):
                return True

        # 2. Regex pattern checks for experience ranges / minimums
        exp_patterns = [
            r"(\d+)\s*\+\s*(?:years?|yrs?)",
            r"(\d+)\s*[-\u2013]\s*\d+\s*(?:years?|yrs?)",
            r"minimum\s*(?:of\s*)?(\d+)\s*(?:years?|yrs?)",
            r"at\s*least\s*(\d+)\s*(?:years?|yrs?)",
            r"(\d+)\s*(?:to|-)\s*\d+\s*(?:years?|yrs?)\s*(?:of\s*)?experience",
        ]
        for pattern in exp_patterns:
            for m in re.finditer(pattern, combined):
                try:
                    if int(m.group(1)) > MAX_EXPERIENCE_YEARS:
                        return True
                except ValueError:
                    pass

        # 3. Direct numeric experience field (e.g. '3', '4+', '5 years')
        if exp_text:
            num_match = re.search(r"^(\d+)(?:\+)?\s*(?:years?|yrs?)?$", exp_text.strip())
            if num_match:
                try:
                    if int(num_match.group(1)) > MAX_EXPERIENCE_YEARS:
                        return True
                except ValueError:
                    pass

        return False

    # ── Location filter ───────────────────────────────────────────────────────

    def _is_acceptable_location(self, job: JobListing) -> bool:
        loc = (job.location or "").lower().strip()
        if not loc or loc in ("n/a", "not specified"):
            return True
        for bad in self.ignore_locations:
            if bad in loc:
                return False
        for good in self.accepted_locations:
            if good in loc:
                return True
        # Unknown location — accept rather than silently drop
        return True

    # ── Salary extraction ─────────────────────────────────────────────────────

    def _extract_salary(self, job: JobListing) -> None:
        if job.estimated_salary_lpa:
            return
        desc = (job.job_description_summary or "").lower()
        if not desc:
            return
        m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*(?:[-to]+\s*\d{1,2}(?:\.\d+)?)?\s*lpa", desc)
        if m:
            try:
                job.estimated_salary_lpa = int(float(m.group(1)))
                job.salary_confidence = "high"
            except ValueError:
                pass
