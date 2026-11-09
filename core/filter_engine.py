"""
Advanced Job Filtering Engine for the AI-Focused Job Ingestion & ETL System.

Implements structured 4-tier role priority classification, AI relevance detection,
comprehensive negative role exclusions, strict 0-2 year experience validation,
India-focused location filtering, decimal and range-aware salary extraction with
LinkedIn Easy Apply floor enforcement, and explainable audit decisions.
"""

import logging
import re
from typing import Optional, List, Dict, Any, Tuple

from core.models import JobListing
from config.settings import KEYWORDS_CONFIG, IGNORE_CONFIG, MAX_EXPERIENCE_YEARS
from config.role_categories import (
    CATEGORY_CORE_AI_FDE,
    CATEGORY_ML_SPECIALIZED_AI,
    CATEGORY_DATA_SCIENCE_APPLIED_RESEARCH,
    CATEGORY_AI_RELATED_SOFTWARE_ENGINEERING,
    PRIORITY_1_ROLES,
    PRIORITY_2_ROLES,
    PRIORITY_3_ROLES,
    PRIORITY_4_ROLES,
    ALL_NEGATIVE_TITLE_ROLES,
    SENIOR_EXCLUSIONS,
    TITLE_NORMALIZATION_REPLACEMENTS,
)
from config.skill_keywords import (
    CORE_AI_KEYWORDS,
    LLM_AGENTIC_KEYWORDS,
    AI_APPLICATION_DEPLOYMENT_KEYWORDS,
    DSA_KEYWORDS,
    AI_RELEVANCE_KEYWORDS,
)
from config.experience_rules import (
    ACCEPTED_EXPERIENCE_KEYWORDS,
    REJECTED_EXPERIENCE_KEYWORDS,
    COMPANY_EXPERIENCE_REGEXES,
    REQUIREMENT_SECTION_REGEX,
)
from config.salary_rules import (
    LINKEDIN_SALARY_FLOOR_LPA,
    SALARY_RANGE_LPA_REGEX,
    SALARY_SINGLE_LPA_REGEX,
    SALARY_ABSOLUTE_ANNUAL_REGEX,
    SALARY_ABSOLUTE_NO_PREFIX_REGEX,
    STIPEND_MONTHLY_REGEX,
)
from config.location_rules import (
    ALL_ACCEPTED_LOCATIONS,
    FOREIGN_LOCATIONS,
    FOREIGN_RESTRICTION_PATTERNS,
)

logger = logging.getLogger(__name__)

MIN_SALARY_LPA_LINKEDIN = 12.0


def _build_word_boundary_regex(keywords: List[str]) -> re.Pattern:
    """Precompile regex matching any keyword with word boundaries, sorted by length descending."""
    sorted_kws = sorted(keywords, key=len, reverse=True)
    patterns = []
    for kw in sorted_kws:
        escaped = re.escape(kw)
        patterns.append(rf"(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])")
    return re.compile("|".join(patterns), re.IGNORECASE)


# ─── Precompiled Regexes ──────────────────────────────────────────────────────

# Negative roles in title
_NEGATIVE_TITLE_RE = _build_word_boundary_regex(ALL_NEGATIVE_TITLE_ROLES)
_SENIOR_TITLE_RE = _build_word_boundary_regex(SENIOR_EXCLUSIONS)

# Priority 4 SDE title pattern
_SDE_TITLE_RE = _build_word_boundary_regex(PRIORITY_4_ROLES)

# AI relevance keyword pattern
_AI_RELEVANCE_RE = _build_word_boundary_regex(AI_RELEVANCE_KEYWORDS)

# DSA keyword pattern
_DSA_RE = _build_word_boundary_regex(DSA_KEYWORDS)

# Combined SDE validation regex
_SDE_VALID_RE = _build_word_boundary_regex(AI_RELEVANCE_KEYWORDS + DSA_KEYWORDS)

# Company experience masks
_COMPANY_EXP_RES = [re.compile(p, re.IGNORECASE) for p in COMPANY_EXPERIENCE_REGEXES]
_REQ_SECTION_RE = re.compile(REQUIREMENT_SECTION_REGEX, re.IGNORECASE)

# Foreign remote restriction patterns
_FOREIGN_RESTRICTION_RES = [re.compile(p, re.IGNORECASE) for p in FOREIGN_RESTRICTION_PATTERNS]

# Title normalization regexes
_TITLE_NORM_RES = [
    (re.compile(pattern, re.IGNORECASE), repl)
    for pattern, repl in TITLE_NORMALIZATION_REPLACEMENTS
]

# Explicit FDE abbreviations and titles
_FDE_STANDALONE_RE = re.compile(r"(?<![a-zA-Z0-9])fde(?![a-zA-Z0-9])", re.IGNORECASE)
_FDE_CONTEXT_RE = _build_word_boundary_regex([
    "forward deployed", "deployment", "integration", "customer facing",
    "client facing", "ai", "ml", "llm", "models", "agent", "solutions"
])

# Candidate experience patterns (ordered and specific)
_EXP_RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|to|\u2013)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)(?:\s*(?:of\s*)?experience)?",
    re.IGNORECASE,
)
_EXP_MINIMUM_RE = re.compile(
    r"(?:minimum\s*(?:of\s*)?|at\s*least\s*)(\d+(?:\.\d+)?)\s*(?:years?|yrs?)(?:\s*(?:of\s*)?experience)?",
    re.IGNORECASE,
)
_EXP_PLUS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)(?:\s*(?:of\s*)?experience)?",
    re.IGNORECASE,
)
_EXP_MONTHS_RE = re.compile(
    r"(\d+)\s*(?:months?|mos?)(?:\s*(?:of\s*)?experience)?",
    re.IGNORECASE,
)
_EXP_SINGLE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*(?:of\s*)?experience",
    re.IGNORECASE,
)


class FilterEngine:
    """
    High-accuracy, auditable filtering engine for AI/ML/SWE job opportunities.
    Evaluates listings against role taxonomy, AI/DSA relevance, experience limits,
    geographic eligibility, and salary thresholds.
    """

    def __init__(self):
        self.accepted_roles = KEYWORDS_CONFIG.get("accepted_roles", [])
        self.accepted_locations = KEYWORDS_CONFIG.get("accepted_locations", ALL_ACCEPTED_LOCATIONS)
        self.accepted_experience = KEYWORDS_CONFIG.get("accepted_experience", ACCEPTED_EXPERIENCE_KEYWORDS)

        self.ignore_roles = IGNORE_CONFIG.get("ignore_roles", ALL_NEGATIVE_TITLE_ROLES)
        self.ignore_locations = IGNORE_CONFIG.get("ignore_locations", FOREIGN_LOCATIONS)
        self.ignore_experience = IGNORE_CONFIG.get("ignore_experience", REJECTED_EXPERIENCE_KEYWORDS)

        # Aggregate statistics tracker
        self.stats = {
            "total_processed": 0,
            "accepted": 0,
            "rejected": 0,
            "rejections_by_stage": {
                "role_filter": 0,
                "relevance_filter": 0,
                "experience_filter": 0,
                "location_filter": 0,
                "salary_filter": 0,
            },
            "rejections_by_reason": {},
        }
        self.last_decisions: List[Dict[str, Any]] = []

    def get_statistics(self) -> Dict[str, Any]:
        """Return aggregate statistics of filtering operations."""
        return self.stats

    # ── Main Entrypoint ───────────────────────────────────────────────────────

    def filter_jobs(self, jobs: List[JobListing]) -> List[JobListing]:
        """
        Filter a batch of JobListing instances.
        Populates metadata and filtering_decision on jobs and returns accepted listings.
        """
        filtered = []
        self.last_decisions.clear()

        for job in jobs:
            decision = self.evaluate_job(job)
            self.last_decisions.append(decision)

            self.stats["total_processed"] += 1

            if decision["accepted"]:
                self.stats["accepted"] += 1
                job.role_priority = decision["role_priority"]
                job.role_category = decision["role_category"]
                job.matched_role = decision["matched_role"]
                job.filtering_decision = decision
                filtered.append(job)
            else:
                self.stats["rejected"] += 1
                stage = decision.get("filtering_stage", "role_filter")
                reason = decision.get("rejection_reason", "unknown")
                self.stats["rejections_by_stage"][stage] = self.stats["rejections_by_stage"].get(stage, 0) + 1
                self.stats["rejections_by_reason"][reason] = self.stats["rejections_by_reason"].get(reason, 0) + 1

        stage_counts = self.stats["rejections_by_stage"]
        logger.info(
            f"FilterEngine: {len(jobs)} in -> {len(filtered)} out | "
            f"role_filter={stage_counts.get('role_filter', 0)} "
            f"relevance_filter={stage_counts.get('relevance_filter', 0)} "
            f"exp_filter={stage_counts.get('experience_filter', 0)} "
            f"location_filter={stage_counts.get('location_filter', 0)} "
            f"salary_filter={stage_counts.get('salary_filter', 0)}"
        )
        return filtered

    def evaluate_job(self, job: JobListing) -> Dict[str, Any]:
        """
        Auditably evaluate a single job listing through all filtering stages.
        Returns a structured decision dictionary.
        """
        # 1. Salary extraction
        self._extract_salary(job)

        # 2. Negative role check on title
        if self._has_negative_role(job):
            matched_kw = self._get_negative_role_keyword(job)
            return {
                "accepted": False,
                "rejection_reason": "negative_role",
                "matched_keyword": matched_kw,
                "filtering_stage": "role_filter",
                "relevant_extracted_values": {
                    "job_title": job.job_title,
                },
            }

        # 3. Role classification
        role_category, role_priority, matched_role, class_reason = self._classify_role(job)
        if role_priority is None:
            return {
                "accepted": False,
                "rejection_reason": "no_role_match",
                "matched_keyword": None,
                "filtering_stage": "role_filter",
                "relevant_extracted_values": {
                    "job_title": job.job_title,
                },
            }

        # 4. Relevance validation for Priority 4 SDE/SWE roles
        if role_priority == 4:
            is_valid, relevance_info = self._validate_priority_4_relevance(job)
            if not is_valid:
                return {
                    "accepted": False,
                    "rejection_reason": "generic_sde_missing_ai_dsa_context",
                    "matched_keyword": None,
                    "filtering_stage": "relevance_filter",
                    "relevant_extracted_values": {
                        "job_title": job.job_title,
                        "relevance_info": relevance_info,
                    },
                }

        # 5. Experience verification
        exp_eval = self._evaluate_experience(job)
        if not exp_eval["experience_match"]:
            return {
                "accepted": False,
                "rejection_reason": exp_eval["rejection_reason"] or "exceeds_experience",
                "matched_keyword": exp_eval.get("matched_keyword"),
                "filtering_stage": "experience_filter",
                "relevant_extracted_values": {
                    "minimum_experience": exp_eval["minimum_experience"],
                    "maximum_experience": exp_eval["maximum_experience"],
                    "experience_confidence": exp_eval["experience_confidence"],
                },
            }

        # 6. Location verification
        loc_eval = self._evaluate_location(job)
        if not loc_eval["location_match"]:
            return {
                "accepted": False,
                "rejection_reason": loc_eval["rejection_reason"] or "location_not_accepted",
                "matched_keyword": loc_eval.get("matched_keyword"),
                "filtering_stage": "location_filter",
                "relevant_extracted_values": {
                    "location": job.location,
                    "matched_location": loc_eval["matched_location"],
                },
            }

        # 7. Salary floor validation for LinkedIn Easy Apply
        salary_eval = self._evaluate_salary_floor(job)
        if not salary_eval["eligible"]:
            return {
                "accepted": False,
                "rejection_reason": salary_eval["rejection_reason"] or "salary_below_floor",
                "matched_keyword": salary_eval.get("matched_keyword"),
                "filtering_stage": "salary_filter",
                "relevant_extracted_values": {
                    "estimated_salary_lpa": job.estimated_salary_lpa,
                    "min_salary_lpa": job.min_salary_lpa,
                    "max_salary_lpa": job.max_salary_lpa,
                    "source_platform": job.source_platform,
                },
            }

        # 8. All stages passed -> Accepted
        ai_rel = self._detect_ai_relevance(job)
        return {
            "accepted": True,
            "role_category": role_category,
            "role_priority": role_priority,
            "matched_role": matched_role,
            "location_match": loc_eval["matched_location"] or job.location or "Unknown",
            "experience_match": True,
            "salary_eligibility": salary_eval["status"],
            "AI_relevance": ai_rel["has_ai_relevance"],
            "classification_reason": class_reason,
            "extracted_salary_lpa": job.estimated_salary_lpa,
            "min_experience": exp_eval["minimum_experience"],
            "max_experience": exp_eval["maximum_experience"],
        }

    # ── Title Normalization & Role Classification ─────────────────────────────

    def _normalize_title(self, title: str) -> str:
        """Normalize job title for canonical rule matching."""
        if not title:
            return ""
        norm = title.lower().strip()
        # Standardize punctuation
        norm = re.sub(r"[\t\r\n]+", " ", norm)
        norm = re.sub(r"[\-–—_/]+", " ", norm)
        # Apply standard domain replacements
        for reg, repl in _TITLE_NORM_RES:
            norm = reg.sub(repl, norm)
        # Collapse whitespace
        return re.sub(r"\s+", " ", norm).strip()

    def _classify_role(
        self, job: JobListing
    ) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
        """
        Classify role into one of the four priorities using normalized matching.
        Matches specific multi-word titles before generic single-word titles.
        Returns: (role_category, role_priority, matched_role, classification_reason)
        """
        raw_title = job.job_title
        norm_title = self._normalize_title(raw_title)
        desc = (job.job_description_summary or "").lower()

        # Check Forward Deployed Engineer abbreviations (e.g. 'FDE')
        if _FDE_STANDALONE_RE.search(raw_title) or _FDE_STANDALONE_RE.search(norm_title):
            # Validate context against FDE/AI terms to avoid unrelated acronym collision
            combined_context = f"{raw_title} {desc}"
            if _FDE_CONTEXT_RE.search(combined_context):
                return (
                    CATEGORY_CORE_AI_FDE,
                    1,
                    "forward deployed engineer",
                    "FDE abbreviation validated with deployment/AI context",
                )

        # Match specific roles in Priority 1 first
        for role in sorted(PRIORITY_1_ROLES, key=len, reverse=True):
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(role)}(?![a-zA-Z0-9])"
            if re.search(pattern, norm_title) or re.search(pattern, raw_title.lower()):
                return (
                    CATEGORY_CORE_AI_FDE,
                    1,
                    role,
                    f"Matched Priority 1 role '{role}'",
                )

        # Match specific roles in Priority 2 (Machine Learning & Specialized AI)
        for role in sorted(PRIORITY_2_ROLES, key=len, reverse=True):
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(role)}(?![a-zA-Z0-9])"
            if re.search(pattern, norm_title) or re.search(pattern, raw_title.lower()):
                return (
                    CATEGORY_ML_SPECIALIZED_AI,
                    2,
                    role,
                    f"Matched Priority 2 specialized AI role '{role}'",
                )

        # Match specific roles in Priority 3 (Data Science & Applied Research)
        for role in sorted(PRIORITY_3_ROLES, key=len, reverse=True):
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(role)}(?![a-zA-Z0-9])"
            if re.search(pattern, norm_title) or re.search(pattern, raw_title.lower()):
                return (
                    CATEGORY_DATA_SCIENCE_APPLIED_RESEARCH,
                    3,
                    role,
                    f"Matched Priority 3 data science/research role '{role}'",
                )

        # Match Priority 4 (AI-Related Software Engineering)
        for role in sorted(PRIORITY_4_ROLES, key=len, reverse=True):
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(role)}(?![a-zA-Z0-9])"
            if re.search(pattern, norm_title) or re.search(pattern, raw_title.lower()):
                return (
                    CATEGORY_AI_RELATED_SOFTWARE_ENGINEERING,
                    4,
                    role,
                    f"Matched Priority 4 software engineering role '{role}' (requires AI/DSA validation)",
                )

        return None, None, None, None

    def _get_role_priority(self, job: JobListing) -> Optional[int]:
        """Legacy helper: returns role priority (1, 2, 3, 4) or None."""
        _, priority, _, _ = self._classify_role(job)
        return priority

    # ── Negative Role Filtering ───────────────────────────────────────────────

    def _has_negative_role(self, job: JobListing) -> bool:
        """
        Check if the job title matches an excluded role (Frontend, Fullstack, Mobile, QA, DevOps, Senior).
        Exceptions: Does not reject accepted AI roles whose description mentions supporting skills.
        """
        title = job.job_title
        if not title:
            return False

        # Strictly check senior level indicators in title
        if _SENIOR_TITLE_RE.search(title):
            return True

        # Check negative roles in title
        if _NEGATIVE_TITLE_RE.search(title):
            # Exception guard: If the title is explicitly an accepted AI/ML/FDE role,
            # protect it against false positive exclusions.
            # e.g., "AI Platform Engineer" should not be dropped by platform/cloud exclusions.
            norm_title = self._normalize_title(title)
            for protected in PRIORITY_1_ROLES + PRIORITY_2_ROLES:
                if protected in norm_title or protected in title.lower():
                    # Title is an explicit AI role. Only reject if senior.
                    return False

            return True

        return False

    def _get_negative_role_keyword(self, job: JobListing) -> Optional[str]:
        """Retrieve the specific negative keyword that matched the title."""
        title = job.job_title
        m_senior = _SENIOR_TITLE_RE.search(title)
        if m_senior:
            return m_senior.group(0)
        m_neg = _NEGATIVE_TITLE_RE.search(title)
        if m_neg:
            return m_neg.group(0)
        return None

    # ── AI Relevance & Priority 4 SDE Validation ──────────────────────────────

    def _detect_ai_relevance(self, job: JobListing) -> Dict[str, Any]:
        """Detect and categorize AI relevance keywords across title, summary, and skills."""
        title = job.job_title or ""
        desc = job.job_description_summary or ""
        skills_text = " ".join(job.required_skills)
        combined = f"{title} {desc} {skills_text}".lower()

        core_matches = [kw for kw in CORE_AI_KEYWORDS if re.search(rf"(?<![a-zA-Z0-9]){re.escape(kw)}(?![a-zA-Z0-9])", combined)]
        llm_matches = [kw for kw in LLM_AGENTIC_KEYWORDS if re.search(rf"(?<![a-zA-Z0-9]){re.escape(kw)}(?![a-zA-Z0-9])", combined)]
        app_matches = [kw for kw in AI_APPLICATION_DEPLOYMENT_KEYWORDS if re.search(rf"(?<![a-zA-Z0-9]){re.escape(kw)}(?![a-zA-Z0-9])", combined)]
        dsa_matches = [kw for kw in DSA_KEYWORDS if re.search(rf"(?<![a-zA-Z0-9]){re.escape(kw)}(?![a-zA-Z0-9])", combined)]

        has_ai = bool(core_matches or llm_matches or app_matches)
        has_dsa = bool(dsa_matches)

        return {
            "has_ai_relevance": has_ai,
            "has_dsa_relevance": has_dsa,
            "core_ai_matches": core_matches,
            "llm_matches": llm_matches,
            "app_matches": app_matches,
            "dsa_matches": dsa_matches,
        }

    def _is_generic_sde(self, job: JobListing) -> bool:
        """Return True if job title represents a generic SDE/SWE role requiring validation."""
        priority = self._get_role_priority(job)
        return priority == 4 or bool(_SDE_TITLE_RE.search(job.job_title))

    def _has_sde_validation(self, job: JobListing) -> bool:
        """Return True if an AI/ML or DSA keyword validates the SDE role."""
        rel = self._detect_ai_relevance(job)
        return rel["has_ai_relevance"] or rel["has_dsa_relevance"]

    def _validate_priority_4_relevance(self, job: JobListing) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate Priority 4 SDE/SWE roles.
        Must have meaningful AI/ML or DSA context. Python alone or basic API development does not qualify.
        """
        rel = self._detect_ai_relevance(job)
        valid = rel["has_ai_relevance"] or rel["has_dsa_relevance"]
        return valid, rel

    # ── Experience Filtering ──────────────────────────────────────────────────

    def _exceeds_experience(self, job: JobListing) -> bool:
        """Legacy helper: returns True if candidate experience requirement exceeds 2 years."""
        eval_result = self._evaluate_experience(job)
        return not eval_result["experience_match"]

    def _evaluate_experience(self, job: JobListing) -> Dict[str, Any]:
        """
        Evaluate candidate experience requirement against the strict 0-2 years limit.
        Distinguishes candidate requirements from company/team history.
        """
        exp_text = (job.experience_required or "").lower().strip()
        desc = (job.job_description_summary or "")

        # 1. Evaluate structured experience_required field if provided
        if exp_text:
            parsed = self._parse_experience_string(exp_text)
            if parsed["found"]:
                min_exp, max_exp = parsed["min_exp"], parsed["max_exp"]
                # Strict 0-2 rule: evaluate upper bound
                if max_exp is not None and max_exp > MAX_EXPERIENCE_YEARS:
                    return {
                        "experience_match": False,
                        "minimum_experience": min_exp,
                        "maximum_experience": max_exp,
                        "experience_confidence": "high",
                        "rejection_reason": "exceeds_experience",
                        "matched_keyword": f"{max_exp} years (structured: '{exp_text}')",
                    }
                if min_exp is not None and min_exp > MAX_EXPERIENCE_YEARS:
                    return {
                        "experience_match": False,
                        "minimum_experience": min_exp,
                        "maximum_experience": max_exp,
                        "experience_confidence": "high",
                        "rejection_reason": "exceeds_experience",
                        "matched_keyword": f"{min_exp}+ years (structured: '{exp_text}')",
                    }
                # Explicit check for accepted fresher keywords
                for kw in self.accepted_experience:
                    if kw in exp_text:
                        return {
                            "experience_match": True,
                            "minimum_experience": min_exp or 0.0,
                            "maximum_experience": max_exp or min_exp or 1.0,
                            "experience_confidence": "high",
                            "rejection_reason": None,
                            "matched_keyword": kw,
                        }
                # If parsed bounds are within 0-2
                return {
                    "experience_match": True,
                    "minimum_experience": min_exp,
                    "maximum_experience": max_exp,
                    "experience_confidence": "high",
                    "rejection_reason": None,
                    "matched_keyword": exp_text,
                }

        # 2. Check description text for experience requirements
        if desc:
            cleaned_desc = self._mask_company_experience(desc)

            # Prioritize candidate requirement section if present
            req_section = self._extract_requirement_section(cleaned_desc)
            target_text = req_section if req_section else cleaned_desc

            # Check explicit reject phrases in target text
            for kw in self.ignore_experience:
                pattern = rf"(?<![a-zA-Z0-9]){re.escape(kw.lower())}(?![a-zA-Z0-9])"
                if re.search(pattern, target_text.lower()):
                    return {
                        "experience_match": False,
                        "minimum_experience": 3.0,
                        "maximum_experience": None,
                        "experience_confidence": "medium",
                        "rejection_reason": "exceeds_experience",
                        "matched_keyword": kw,
                    }

            # Parse regex experience patterns from target text
            parsed = self._parse_experience_string(target_text)
            if parsed["found"]:
                min_exp, max_exp = parsed["min_exp"], parsed["max_exp"]
                if max_exp is not None and max_exp > MAX_EXPERIENCE_YEARS:
                    return {
                        "experience_match": False,
                        "minimum_experience": min_exp,
                        "maximum_experience": max_exp,
                        "experience_confidence": "medium",
                        "rejection_reason": "exceeds_experience",
                        "matched_keyword": f"Upper bound {max_exp} years > {MAX_EXPERIENCE_YEARS}",
                    }
                if min_exp is not None and min_exp > MAX_EXPERIENCE_YEARS:
                    return {
                        "experience_match": False,
                        "minimum_experience": min_exp,
                        "maximum_experience": max_exp,
                        "experience_confidence": "medium",
                        "rejection_reason": "exceeds_experience",
                        "matched_keyword": f"Minimum {min_exp} years > {MAX_EXPERIENCE_YEARS}",
                    }

                return {
                    "experience_match": True,
                    "minimum_experience": min_exp,
                    "maximum_experience": max_exp,
                    "experience_confidence": "medium",
                    "rejection_reason": None,
                    "matched_keyword": parsed.get("raw_match"),
                }

        # 3. If experience is unspecified, allow with caution (unknown confidence)
        return {
            "experience_match": True,
            "minimum_experience": None,
            "maximum_experience": None,
            "experience_confidence": "unknown",
            "rejection_reason": None,
            "matched_keyword": None,
        }

    def _mask_company_experience(self, text: str) -> str:
        """Mask out phrases referencing company history or team tenure."""
        masked = text
        for reg in _COMPANY_EXP_RES:
            masked = reg.sub("[COMPANY_HISTORY_MASKED]", masked)
        return masked

    def _extract_requirement_section(self, text: str) -> Optional[str]:
        """Extract text following requirement/qualification section headers."""
        m = _REQ_SECTION_RE.search(text)
        if m:
            start_pos = m.start()
            # Capture up to 1000 characters from the section start
            return text[start_pos : start_pos + 1000]
        return None

    def _parse_experience_string(self, text: str) -> Dict[str, Any]:
        """
        Extract numeric experience bounds from text.
        Handles ranges (1-3 yrs), minimums (at least 3 yrs), months (24 months), and pluses (3+ yrs).
        """
        # Range: "1-3 years", "0 to 2 yrs"
        m_range = _EXP_RANGE_RE.search(text)
        if m_range:
            try:
                min_v = float(m_range.group(1))
                max_v = float(m_range.group(2))
                return {
                    "found": True,
                    "min_exp": min_v,
                    "max_exp": max_v,
                    "raw_match": m_range.group(0),
                }
            except ValueError:
                pass

        # Minimum: "at least 3 years", "minimum 3 years"
        m_min = _EXP_MINIMUM_RE.search(text)
        if m_min:
            try:
                val = float(m_min.group(1))
                return {
                    "found": True,
                    "min_exp": val,
                    "max_exp": None,
                    "raw_match": m_min.group(0),
                }
            except ValueError:
                pass

        # Plus: "3+ years", "4+ yrs"
        m_plus = _EXP_PLUS_RE.search(text)
        if m_plus:
            try:
                val = float(m_plus.group(1))
                return {
                    "found": True,
                    "min_exp": val,
                    "max_exp": None,
                    "raw_match": m_plus.group(0),
                }
            except ValueError:
                pass

        # Months: "24 months" -> 2.0 yrs
        m_months = _EXP_MONTHS_RE.search(text)
        if m_months:
            try:
                months = float(m_months.group(1))
                years = round(months / 12.0, 2)
                return {
                    "found": True,
                    "min_exp": years,
                    "max_exp": years,
                    "raw_match": m_months.group(0),
                }
            except ValueError:
                pass

        # Single: "2 years of experience"
        m_single = _EXP_SINGLE_RE.search(text)
        if m_single:
            try:
                val = float(m_single.group(1))
                return {
                    "found": True,
                    "min_exp": val,
                    "max_exp": val,
                    "raw_match": m_single.group(0),
                }
            except ValueError:
                pass

        # Standalone numeric field like '0', '1', '2', '3+'
        num_m = re.search(r"^(\d+(?:\.\d+)?)(?:\+)?\s*(?:years?|yrs?)?$", text.strip())
        if num_m:
            try:
                val = float(num_m.group(1))
                return {
                    "found": True,
                    "min_exp": val,
                    "max_exp": val,
                    "raw_match": text.strip(),
                }
            except ValueError:
                pass

        return {"found": False, "min_exp": None, "max_exp": None, "raw_match": None}

    # ── Location Filtering ────────────────────────────────────────────────────

    def _is_acceptable_location(self, job: JobListing) -> bool:
        """Legacy helper: returns True if location is acceptable."""
        eval_result = self._evaluate_location(job)
        return eval_result["location_match"]

    def _evaluate_location(self, job: JobListing) -> Dict[str, Any]:
        """
        Validate location against Indian cities and unrestricted Remote postings.
        Rejects strictly foreign locations. Unspecified location is accepted with caution.
        """
        loc = (job.location or "").lower().strip()
        desc = (job.job_description_summary or "")

        # 1. Empty or unspecified location -> accept as unknown
        if not loc or loc in ("n/a", "not specified", "unknown", "none"):
            return {
                "location_match": True,
                "matched_location": "Unknown",
                "rejection_reason": None,
                "matched_keyword": None,
            }

        # 2. Check for explicit foreign locations
        has_foreign_match = False
        matched_foreign_loc = None
        for foreign_loc in self.ignore_locations:
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(foreign_loc.lower())}(?![a-zA-Z0-9])"
            if re.search(pattern, loc):
                has_foreign_match = True
                matched_foreign_loc = foreign_loc
                break

        # 3. Check for specific Indian cities and regions (excluding generic standalone remote)
        has_indian_match = False
        matched_indian_city = None
        indian_tokens = [
            c for c in self.accepted_locations
            if c.lower() not in ("remote", "work from home", "wfh", "anywhere")
        ]
        for indian_loc in indian_tokens:
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(indian_loc.lower())}(?![a-zA-Z0-9])"
            if re.search(pattern, loc):
                has_indian_match = True
                matched_indian_city = indian_loc
                break

        # If foreign only (without an Indian city match), reject
        if has_foreign_match and not has_indian_match:
            return {
                "location_match": False,
                "matched_location": matched_foreign_loc,
                "rejection_reason": "foreign_location",
                "matched_keyword": matched_foreign_loc,
            }

        # If an Indian city was explicitly matched, accept
        if has_indian_match:
            return {
                "location_match": True,
                "matched_location": matched_indian_city,
                "rejection_reason": None,
                "matched_keyword": matched_indian_city,
            }

        # 4. Check if location is Remote
        if "remote" in loc or "work from home" in loc or "wfh" in loc:
            # Verify description does not restrict eligibility to a foreign country
            for reg in _FOREIGN_RESTRICTION_RES:
                if reg.search(desc):
                    return {
                        "location_match": False,
                        "matched_location": "Foreign-Restricted Remote",
                        "rejection_reason": "foreign_restricted_remote",
                        "matched_keyword": reg.pattern,
                    }
            return {
                "location_match": True,
                "matched_location": "Remote",
                "rejection_reason": None,
                "matched_keyword": "remote",
            }

        # 5. Non-matching specified location: if not recognized as Indian/Remote, reject
        return {
            "location_match": False,
            "matched_location": loc,
            "rejection_reason": "non_indian_location",
            "matched_keyword": loc,
        }

    # ── Salary Extraction & Floor Filtering ───────────────────────────────────

    def _extract_salary(self, job: JobListing) -> None:
        """
        Extract salary values from description or salary fields.
        Populates min_salary_lpa, max_salary_lpa, estimated_salary_lpa, and salary_confidence.
        """
        # If job already has estimated_salary_lpa, preserve it
        if job.estimated_salary_lpa and not job.min_salary_lpa:
            job.min_salary_lpa = float(job.estimated_salary_lpa)
            job.max_salary_lpa = float(job.estimated_salary_lpa)
            if not job.salary_confidence:
                job.salary_confidence = "medium"

        text_to_search = f"{job.salary or ''} {job.job_description_summary or ''}".lower()
        if not text_to_search.strip():
            return

        # 1. Range LPA pattern: "12-18 LPA", "12.5 - 15 Lakhs"
        m_range = SALARY_RANGE_LPA_REGEX.search(text_to_search)
        if m_range:
            try:
                min_val = float(m_range.group(1))
                max_val = float(m_range.group(2))
                job.min_salary_lpa = min_val
                job.max_salary_lpa = max_val
                job.estimated_salary_lpa = min_val
                job.salary_confidence = "high"
                return
            except ValueError:
                pass

        # 2. Single LPA pattern: "12.5 LPA", "20 Lakhs per annum"
        m_single = SALARY_SINGLE_LPA_REGEX.search(text_to_search)
        if m_single:
            try:
                val = float(m_single.group(1))
                job.min_salary_lpa = val
                job.max_salary_lpa = val
                job.estimated_salary_lpa = val
                job.salary_confidence = "high"
                return
            except ValueError:
                pass

        # 3. Absolute Annual INR pattern: "₹15,00,000 per annum", "1500000 INR annually"
        m_abs = SALARY_ABSOLUTE_ANNUAL_REGEX.search(text_to_search)
        if m_abs:
            try:
                num_str = m_abs.group(1).replace(",", "")
                annual_inr = float(num_str)
                lpa = round(annual_inr / 100000.0, 2)
                job.min_salary_lpa = lpa
                job.max_salary_lpa = lpa
                job.estimated_salary_lpa = lpa
                job.salary_confidence = "high"
                return
            except ValueError:
                pass

        m_abs_no_prefix = SALARY_ABSOLUTE_NO_PREFIX_REGEX.search(text_to_search)
        if m_abs_no_prefix:
            try:
                num_str = m_abs_no_prefix.group(1).replace(",", "")
                annual_inr = float(num_str)
                lpa = round(annual_inr / 100000.0, 2)
                job.min_salary_lpa = lpa
                job.max_salary_lpa = lpa
                job.estimated_salary_lpa = lpa
                job.salary_confidence = "high"
                return
            except ValueError:
                pass

        # 4. Monthly Stipend: "₹25,000 / month", "stipend of ₹50k/month"
        m_stipend = STIPEND_MONTHLY_REGEX.search(text_to_search)
        if m_stipend:
            try:
                num_str = m_stipend.group(1).replace(",", "")
                monthly = float(num_str)
                # If 'k' followed, multiply
                if "k" in m_stipend.group(0).lower():
                    monthly = monthly * 1000.0
                annual_inr = monthly * 12.0
                lpa = round(annual_inr / 100000.0, 2)
                job.min_salary_lpa = lpa
                job.max_salary_lpa = lpa
                job.estimated_salary_lpa = lpa
                job.salary_confidence = "medium"
                return
            except ValueError:
                pass

    def _evaluate_salary_floor(self, job: JobListing) -> Dict[str, Any]:
        """
        Enforce the 12 LPA minimum salary floor for LinkedIn Easy Apply postings.
        Handles ranges and undisclosed salaries according to system policy.
        """
        is_linkedin_easy_apply = job.source_platform == "linkedin_easy_apply"

        # Undisclosed salary is allowed through across all platforms
        if job.estimated_salary_lpa is None and job.max_salary_lpa is None:
            return {
                "eligible": True,
                "status": "undisclosed",
                "rejection_reason": None,
                "matched_keyword": None,
            }

        if is_linkedin_easy_apply:
            max_val = job.max_salary_lpa if job.max_salary_lpa is not None else job.estimated_salary_lpa
            min_val = job.min_salary_lpa if job.min_salary_lpa is not None else job.estimated_salary_lpa

            # If maximum salary is below the 12 LPA floor, reject
            if max_val is not None and max_val < LINKEDIN_SALARY_FLOOR_LPA:
                return {
                    "eligible": False,
                    "status": "below_floor",
                    "rejection_reason": "salary_below_floor",
                    "matched_keyword": f"{max_val} LPA < {LINKEDIN_SALARY_FLOOR_LPA} LPA",
                }

            # If minimum salary meets the floor, accept
            if min_val is not None and min_val >= LINKEDIN_SALARY_FLOOR_LPA:
                return {
                    "eligible": True,
                    "status": "eligible",
                    "rejection_reason": None,
                    "matched_keyword": f"{min_val} LPA",
                }

            # If the range crosses 12 LPA (e.g. 8-15 LPA), mark uncertain and accept
            return {
                "eligible": True,
                "status": "uncertain_range",
                "rejection_reason": None,
                "matched_keyword": f"Range {min_val}-{max_val} LPA",
            }

        return {
            "eligible": True,
            "status": "eligible",
            "rejection_reason": None,
            "matched_keyword": None,
        }
