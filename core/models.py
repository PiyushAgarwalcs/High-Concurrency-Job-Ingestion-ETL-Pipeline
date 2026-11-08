"""
Data models for the AI/ML Job Alert System V2.
JobListing dataclass with serialization, hashing, and utility methods.
"""

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class JobListing:
    """Represents a single job opportunity."""

    # ─── Required Fields ────────────────────────────────────────────────────
    company_name: str
    job_title: str
    location: str
    apply_url: str
    source_platform: str           # 'official', 'greenhouse', 'lever', 'linkedin', etc.
    
    # ─── New V2 Fields ──────────────────────────────────────────────────────
    ats_provider: str = "unknown"
    status: str = "new"            # 'new', 'applied', 'interview', 'rejected', etc.
    notification_sent: bool = False

    # ─── Optional Fields ────────────────────────────────────────────────────
    salary: Optional[str] = None
    estimated_salary_lpa: Optional[int] = None
    salary_confidence: Optional[str] = None      # 'high', 'medium', 'low'
    experience_required: Optional[str] = None
    required_skills: list[str] = field(default_factory=list)
    job_description_summary: Optional[str] = None
    posting_date: Optional[str] = None
    company_category: Optional[str] = None
    company_prestige_score: int = 5

    # ─── Computed / System Fields ───────────────────────────────────────────
    discovery_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    job_id: str = ""                # SHA256 hash, computed after init
    rank_score: float = 0.0        # Computed by ranking engine
    role_priority: int = 3          # 1, 2, or 3 based on role match

    def __post_init__(self):
        """Generate job_id hash after initialization."""
        self.company_name = self.company_name.strip()
        self.job_title = self.job_title.strip()
        self.location = self.location.strip()
        if not self.job_id:
            self.job_id = self.generate_hash()

    def generate_hash(self) -> str:
        """Generate collision-resistant canonical SHA-256 state fingerprint via StateLedger."""
        try:
            from core.state_ledger import StateLedger
            return StateLedger.generate_fingerprint(
                self.company_name,
                self.job_title,
                self.location,
                self.apply_url
            )
        except Exception:
            raw = (
                self.company_name.lower().strip()
                + self.job_title.lower().strip()
                + self.apply_url.lower().strip()
            )
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _normalize_location(self) -> str:
        """Normalize location for filtering using canonical StateLedger rules."""
        from core.state_ledger import StateLedger
        return StateLedger.normalize_location(self.location)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization or SQLite insertion."""
        d = asdict(self)
        # SQLite cannot store lists natively, so convert required_skills to JSON string
        import json
        d['required_skills'] = json.dumps(d['required_skills'])
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "JobListing":
        """Create a JobListing from a dictionary."""
        import json
        # Handle JSON strings from SQLite
        if 'required_skills' in data and isinstance(data['required_skills'], str):
            try:
                data['required_skills'] = json.loads(data['required_skills'])
            except json.JSONDecodeError:
                data['required_skills'] = []
                
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def display_salary(self) -> str:
        """Return salary display string."""
        if self.salary:
            return self.salary
        if self.estimated_salary_lpa:
            confidence = self.salary_confidence or "medium"
            return f"Estimated ₹{self.estimated_salary_lpa}+ LPA ({confidence})"
        return "Not disclosed"

    def __eq__(self, other):
        if not isinstance(other, JobListing):
            return False
        return self.job_id == other.job_id

    def __hash__(self):
        return hash(self.job_id)

    def __repr__(self):
        return f"JobListing({self.company_name} | {self.job_title} | {self.location})"
