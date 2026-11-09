"""
Request Guard: Safety Gate & Upstream Rate-Limit Protection.

This module provides two main components:
1. JobSchema: Validates incoming scraped data, removes tracking/referral parameters
   from URLs, and filters out non-job spam/placeholder titles.
2. CircuitBreaker: Protects upstream ATS websites from getting hammered by too many
   requests and protects our IP address from getting blocked by 429/503 rate limits.

No AI / LLMs are used. Pure, deterministic, zero-cost Python code.
"""

import logging
import re
import time
from typing import Dict, Optional, Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Query parameters commonly used for tracking that degrade deduplication accuracy
TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "lever-origin", "lever-source", "ref", "source",
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "_hsenc", "_hsmi"
}

# Regex to detect obvious placeholder or test titles
PLACEHOLDER_TITLE_REGEX = re.compile(
    r"^(test|testing|sample|demo|n/a|none|asdf|placeholder|untitled|internship openings?)$",
    re.IGNORECASE
)


def clean_url(raw_url: str) -> str:
    """
    Remove marketing tracking parameters (like ?utm_source=...) from URLs.
    
    Example:
        Input:  https://jobs.lever.co/company/abc?utm_source=linkedin&ref=123
        Output: https://jobs.lever.co/company/abc
    """
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return raw_url.strip()

        # Keep only legitimate parameters, discard tracking parameters
        clean_query_params = [
            (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=False)
            if key.lower() not in TRACKING_QUERY_PARAMS
        ]
        rebuilt_query = urlencode(clean_query_params)
        
        # Build normalized URL without fragments (#...)
        sanitized_url = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            rebuilt_query,
            ""  # strip anchor fragment
        ))
        return sanitized_url
    except Exception:
        return raw_url.strip()


class JobSchema(BaseModel):
    """
    Strict, beginner-friendly data schema for validating incoming job postings.
    Guarantees every listing has a real company, a valid title, and a clean URL.
    """
    company_name: str = Field(..., min_length=1, max_length=200, description="Company name")
    job_title: str = Field(..., min_length=2, max_length=250, description="Job title / role")
    location: str = Field(default="Remote", max_length=200, description="Job location")
    apply_url: str = Field(..., min_length=10, description="Direct URL to view/apply")
    source_platform: str = Field(default="unknown", max_length=50)
    ats_provider: str = Field(default="unknown", max_length=50)
    salary: Optional[str] = Field(default=None, max_length=100)
    estimated_salary_lpa: Optional[int] = Field(default=None, ge=0, le=500)
    salary_confidence: Optional[str] = Field(default=None, max_length=20)
    experience_required: Optional[str] = Field(default=None, max_length=100)
    required_skills: list[str] = Field(default_factory=list)
    job_description_summary: Optional[str] = Field(default=None, max_length=5000)
    posting_date: Optional[str] = Field(default=None, max_length=50)
    company_category: Optional[str] = Field(default=None, max_length=100)
    company_prestige_score: int = Field(default=5, ge=1, le=10)
    rank_score: float = Field(default=0.0, ge=0.0, le=1000.0)
    role_priority: int = Field(default=3, ge=1, le=3)

    @field_validator("company_name", mode="before")
    @classmethod
    def validate_company(cls, value: Any) -> str:
        if not value or not isinstance(value, str):
            raise ValueError("Company name must be a non-empty string")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Company name must not be blank")
        return cleaned

    @field_validator("job_title", mode="before")
    @classmethod
    def validate_title(cls, value: Any) -> str:
        if not value or not isinstance(value, str):
            raise ValueError("Job title must be a non-empty string")
        cleaned = re.sub(r"\s+", " ", value).strip()
        if len(cleaned) < 2:
            raise ValueError("Job title must be at least 2 characters long")
        if PLACEHOLDER_TITLE_REGEX.match(cleaned):
            raise ValueError(f"Job title rejected as invalid placeholder: '{cleaned}'")
        return cleaned

    @field_validator("apply_url", mode="before")
    @classmethod
    def validate_url(cls, value: Any) -> str:
        if not value or not isinstance(value, str):
            raise ValueError("apply_url must be a valid string")
        sanitized = clean_url(value)
        parsed = urlparse(sanitized)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme '{parsed.scheme}'; expected http or https")
        if not parsed.netloc or "." not in parsed.netloc:
            raise ValueError(f"Invalid host in apply_url: '{parsed.netloc}'")
        return sanitized

    @field_validator("location", mode="before")
    @classmethod
    def validate_location(cls, value: Any) -> str:
        if not value or not isinstance(value, str) or not value.strip():
            return "Remote"
        return re.sub(r"\s+", " ", value).strip()

    def to_job_listing(self) -> Any:
        """Convert validated JobSchema model to the internal JobListing dataclass."""
        from core.models import JobListing
        return JobListing(
            company_name=self.company_name,
            job_title=self.job_title,
            location=self.location,
            apply_url=self.apply_url,
            source_platform=self.source_platform,
            ats_provider=self.ats_provider,
            salary=self.salary,
            estimated_salary_lpa=self.estimated_salary_lpa,
            salary_confidence=self.salary_confidence,
            experience_required=self.experience_required,
            required_skills=self.required_skills,
            job_description_summary=self.job_description_summary,
            posting_date=self.posting_date,
            company_category=self.company_category,
            company_prestige_score=self.company_prestige_score,
            rank_score=self.rank_score,
            role_priority=self.role_priority,
        )

    @classmethod
    def from_job_listing(cls, listing: Any) -> "JobSchema":
        """Build and validate a JobSchema from a dictionary or JobListing object."""
        import json as _json

        if hasattr(listing, "to_dict"):
            data = listing.to_dict()
        elif isinstance(listing, dict):
            data = dict(listing)          # shallow copy to avoid mutating caller
        else:
            data = dict(listing.__dict__)

        # to_dict() serialises required_skills to a JSON string for SQLite;
        # Pydantic expects list[str], so deserialise it back.
        skills = data.get("required_skills")
        if isinstance(skills, str):
            try:
                data["required_skills"] = _json.loads(skills)
            except (_json.JSONDecodeError, TypeError):
                data["required_skills"] = []

        return cls(**data)


class CircuitBreaker:
    """
    Domain-Aware Circuit Breaker (Closed -> Open -> Half-Open).
    
    Protects both upstream servers and our local scraping IP:
    - If a domain (like 'boards.greenhouse.io') fails 3 times with 429/503/timeout,
      we 'open' the circuit and skip future requests to that domain for 15 minutes.
    - After 15 minutes (cooldown), the circuit enters 'half-open' to test if the
      server has recovered.
    """

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 900):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.domain_failures: Dict[str, int] = {}
        self.opened_at: Dict[str, float] = {}

    def extract_domain(self, url_or_domain: str) -> str:
        """Extract the root domain (e.g., 'boards.greenhouse.io') from any URL."""
        if not url_or_domain:
            return "unknown"
        if "://" in url_or_domain:
            try:
                parsed = urlparse(url_or_domain)
                return (parsed.netloc or "unknown").lower()
            except Exception:
                pass
        return url_or_domain.strip().lower().split("/")[0]

    def can_request(self, domain_or_url: str) -> bool:
        """
        Check if we are allowed to make a network request to this domain.
        Returns True if allowed (Closed or Half-Open).
        Returns False if blocked (Open cooldown still active).
        """
        domain = self.extract_domain(domain_or_url)
        if domain in self.opened_at:
            time_elapsed = time.time() - self.opened_at[domain]
            if time_elapsed > self.cooldown_seconds:
                # Cooldown period expired -> enter Half-Open mode and allow trial request
                logger.info(
                    f"🛡️  [RequestGuard] Circuit HALF-OPEN for '{domain}' "
                    f"(cooldown of {self.cooldown_seconds}s expired). Allowing probe request."
                )
                del self.opened_at[domain]
                self.domain_failures[domain] = 0
                return True
            return False
        return True

    # Alias for can_request
    can_execute = can_request

    def record_failure(self, domain_or_url: str, reason: str = ""):
        """Record a failure (such as HTTP 429, 503, or timeout) for a domain."""
        domain = self.extract_domain(domain_or_url)
        self.domain_failures[domain] = self.domain_failures.get(domain, 0) + 1
        count = self.domain_failures[domain]

        if count >= self.failure_threshold and domain not in self.opened_at:
            self.opened_at[domain] = time.time()
            logger.warning(
                f"🛡️  [RequestGuard] Circuit TRIP -> OPEN for '{domain}'. "
                f"Failures: {count}/{self.failure_threshold}. "
                f"Cooldown: {self.cooldown_seconds}s. Reason: {reason or 'Repeated HTTP errors'}"
            )

    def record_success(self, domain_or_url: str):
        """Record a successful response, resetting failures and closing the circuit."""
        domain = self.extract_domain(domain_or_url)
        if domain in self.opened_at or self.domain_failures.get(domain, 0) > 0:
            logger.debug(f"🛡️  [RequestGuard] Circuit CLOSED for '{domain}' after success.")
        self.domain_failures[domain] = 0
        self.opened_at.pop(domain, None)

    def is_blocked(self, domain_or_url: str) -> bool:
        """Check whether requests to this domain are currently blocked."""
        return not self.can_request(domain_or_url)

    def get_status_summary(self) -> Dict[str, Any]:
        """Return diagnostic data about currently tracked domains."""
        now = time.time()
        active_blocked = {
            dom: round(self.cooldown_seconds - (now - ts), 1)
            for dom, ts in self.opened_at.items()
            if (now - ts) <= self.cooldown_seconds
        }
        return {
            "total_domains_tracked": len(self.domain_failures),
            "blocked_domains_count": len(active_blocked),
            "blocked_domains": active_blocked,
            "failure_counts": {k: v for k, v in self.domain_failures.items() if v > 0}
        }
