"""
DeployGuard: Safety Gate & Upstream Isolation Engine.
Provides programmatic Pydantic v2 schema validation, URL sanitization,
and domain-aware circuit breaking to protect upstreams against 429/503 cascades.

Deterministic, zero-cost, no-LLM safety enforcement.
"""

import logging
import re
import time
from typing import Dict, Optional, Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from pydantic import BaseModel, HttpUrl, Field, field_validator, ValidationInfo

logger = logging.getLogger(__name__)

# Query parameters commonly used for tracking/referrals that degrade dedup accuracy
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "lever-origin", "lever-source", "ref", "source",
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "_hsenc", "_hsmi"
}

# Regex to detect obvious non-job or spam titles
NON_JOB_TITLE_REGEX = re.compile(
    r"^(test|testing|sample|demo|n/a|none|asdf|placeholder|untitled|internship openings?)$",
    re.IGNORECASE
)


def sanitize_url(raw_url: str) -> str:
    """
    Remove tracking query parameters from URLs to ensure consistent canonicalization.
    Example: https://jobs.lever.co/company/abc?utm_source=linkedin -> https://jobs.lever.co/company/abc
    """
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return raw_url.strip()

        # Filter out tracking query params while maintaining parameter ordering
        filtered_queries = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() not in TRACKING_PARAMS
        ]
        new_query = urlencode(filtered_queries)
        clean_url = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            new_query,
            ""  # Strip URL fragments (#...)
        ))
        return clean_url
    except Exception:
        return raw_url.strip()


class JobPayload(BaseModel):
    """
    Strict programmatic schema for incoming job listings.
    Guarantees structural validity, sanitizes URLs, and boundaries fields.
    """
    company_name: str = Field(..., min_length=1, max_length=200, description="Company name")
    job_title: str = Field(..., min_length=2, max_length=250, description="Job title / role")
    location: str = Field(default="Remote", max_length=200, description="Job location")
    apply_url: str = Field(..., min_length=10, description="Direct URL to view/apply")
    source_platform: str = Field(default="unknown", max_length=50, description="Source platform")
    ats_provider: str = Field(default="unknown", max_length=50, description="Detected or configured ATS")
    salary: Optional[str] = Field(default=None, max_length=100)
    estimated_salary_lpa: Optional[int] = Field(default=None, ge=0, le=500)
    salary_confidence: Optional[str] = Field(default=None, max_length=20)
    experience_required: Optional[str] = Field(default=None, max_length=100)
    required_skills: list[str] = Field(default_factory=list)
    job_description_summary: Optional[str] = Field(default=None, max_length=5000)
    posting_date: Optional[str] = Field(default=None, max_length=50)
    company_category: Optional[str] = Field(default=None, max_length=100)
    company_prestige_score: int = Field(default=5, ge=1, le=10)
    rank_score: float = Field(default=0.0, ge=0.0, le=100.0)
    role_priority: int = Field(default=3, ge=1, le=3)

    @field_validator("company_name", mode="before")
    @classmethod
    def clean_company_name(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Company name must be a non-empty string")
        cleaned = v.strip()
        if len(cleaned) < 1:
            raise ValueError("Company name must not be blank")
        return cleaned

    @field_validator("job_title", mode="before")
    @classmethod
    def validate_title(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Job title must be a non-empty string")
        cleaned = re.sub(r"\s+", " ", v).strip()
        if len(cleaned) < 2:
            raise ValueError("Job title must have at least 2 characters")
        if NON_JOB_TITLE_REGEX.match(cleaned):
            raise ValueError(f"Job title rejected as invalid placeholder: '{cleaned}'")
        return cleaned

    @field_validator("apply_url", mode="before")
    @classmethod
    def validate_and_clean_url(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("apply_url must be a valid string")
        cleaned = sanitize_url(v)
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme '{parsed.scheme}'; expected http or https")
        if not parsed.netloc or "." not in parsed.netloc:
            raise ValueError(f"Invalid host in apply_url: '{parsed.netloc}'")
        return cleaned

    @field_validator("location", mode="before")
    @classmethod
    def clean_location(cls, v: Any) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            return "Remote"
        return re.sub(r"\s+", " ", v).strip()

    def to_job_listing(self) -> Any:
        """Convert validated JobPayload to canonical JobListing dataclass."""
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
    def from_job_listing(cls, listing: Any) -> "JobPayload":
        """Construct and validate JobPayload from JobListing or dictionary."""
        if hasattr(listing, "to_dict"):
            data = listing.to_dict()
        elif isinstance(listing, dict):
            data = listing
        else:
            data = listing.__dict__
        return cls(**data)


class CircuitBreakerOpenException(Exception):
    """Raised when an outbound HTTP request is blocked by an open circuit breaker."""
    pass


class CircuitBreaker:
    """
    Domain-Aware Circuit Breaker with 3 States: CLOSED, OPEN, HALF-OPEN.
    
    Protects both our worker IP from rate limits and upstream ATS servers from overload.
    Operates per host/domain: e.g., 'boards.greenhouse.io' or 'jobs.lever.co'.
    """

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 900):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures: Dict[str, int] = {}
        self.opened_at: Dict[str, float] = {}

    def extract_domain(self, url_or_host: str) -> str:
        """Extract canonical host from a URL or bare domain string."""
        if not url_or_host:
            return "unknown"
        if "://" in url_or_host:
            try:
                parsed = urlparse(url_or_host)
                return (parsed.netloc or "unknown").lower()
            except Exception:
                pass
        return url_or_host.strip().lower().split("/")[0]

    def can_execute(self, domain_or_url: str) -> bool:
        """
        Check if an operation against the given domain is permitted.
        Returns True if CLOSED or HALF-OPEN (cooldown expired).
        Returns False if OPEN and cooldown is still active.
        """
        domain = self.extract_domain(domain_or_url)
        if domain in self.opened_at:
            elapsed = time.time() - self.opened_at[domain]
            if elapsed > self.cooldown_seconds:
                # Cooldown expired -> Transition from OPEN to HALF-OPEN (allow probe)
                logger.info(
                    f"🛡️  [DeployGuard] Circuit HALF-OPEN for '{domain}' "
                    f"(cooldown of {self.cooldown_seconds}s expired). Allowing probe request."
                )
                del self.opened_at[domain]
                self.failures[domain] = 0
                return True
            return False
        return True

    def record_failure(self, domain_or_url: str, reason: str = ""):
        """Record an upstream failure (429, 503, connection reset, timeout)."""
        domain = self.extract_domain(domain_or_url)
        self.failures[domain] = self.failures.get(domain, 0) + 1
        count = self.failures[domain]
        if count >= self.failure_threshold and domain not in self.opened_at:
            self.opened_at[domain] = time.time()
            logger.warning(
                f"🛡️  [DeployGuard] Circuit TRIP -> OPEN for '{domain}'. "
                f"Threshold reached ({count}/{self.failure_threshold} failures). "
                f"Cooldown: {self.cooldown_seconds}s. Reason: {reason or 'Repeated errors'}"
            )

    def record_success(self, domain_or_url: str):
        """Record an upstream success, resetting failures and closing circuit."""
        domain = self.extract_domain(domain_or_url)
        if domain in self.opened_at or self.failures.get(domain, 0) > 0:
            logger.debug(f"🛡️  [DeployGuard] Circuit CLOSED for '{domain}' after successful request.")
        self.failures[domain] = 0
        self.opened_at.pop(domain, None)

    def is_open(self, domain_or_url: str) -> bool:
        """Check if circuit is currently open for domain."""
        return not self.can_execute(domain_or_url)

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic metrics on circuit breaker states."""
        now = time.time()
        active_trips = {
            dom: round(self.cooldown_seconds - (now - ts), 1)
            for dom, ts in self.opened_at.items()
            if (now - ts) <= self.cooldown_seconds
        }
        return {
            "total_domains_tracked": len(self.failures),
            "open_circuits_count": len(active_trips),
            "open_circuits": active_trips,
            "failure_counts": {k: v for k, v in self.failures.items() if v > 0}
        }
