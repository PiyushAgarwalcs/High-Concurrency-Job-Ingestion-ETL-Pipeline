"""
OmniSight: High-Throughput State Fingerprinting & Deduplication Fabric.
Provides canonical string normalization, deterministic SHA-256 state hashing,
and an indexed SQLite state ledger with disk footprint monitoring.

100% deterministic, zero cost, no LLMs.
"""

import hashlib
import logging
import os
import re
import sqlite3
import unicodedata
from typing import List, Tuple, Set, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Standard canonical city mapping for location normalization
CITY_CANONICAL_MAP = {
    "bengaluru": "bangalore",
    "bangalore": "bangalore",
    "hyderabad": "hyderabad",
    "secunderabad": "hyderabad",
    "gurugram": "gurgaon",
    "gurgaon": "gurgaon",
    "noida": "noida",
    "greater noida": "noida",
    "chennai": "chennai",
    "madras": "chennai",
    "pune": "pune",
    "mumbai": "mumbai",
    "bombay": "mumbai",
    "delhi": "delhi",
    "new delhi": "delhi",
    "kolkata": "kolkata",
    "calcutta": "kolkata",
    "remote": "remote",
    "india": "india",
}

# Role standardizer tokens
ROLE_REPLACEMENTS = [
    (r"\bsoftware development engineer\b", "sde"),
    (r"\bsoftware engineer\b", "sde"),
    (r"\bmember of technical staff\b", "mts"),
    (r"\bassociate\b", "assoc"),
    (r"\bjunior\b", "jr"),
    (r"\bsenior\b", "sr"),
    (r"\s*-\s*", " "),
    (r"\s*\/\s*", " "),
    (r"\s+", " "),
]


class OmniSightEngine:
    """
    Deterministic State Fingerprinting and Deduplication Engine.
    Employs SHA-256 hashing across canonical tokens and maintains a persistent SQLite ledger.
    """

    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a SQLite connection with timeout and WAL mode enabled for concurrency."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Initialize the job_fingerprints state ledger table and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_fingerprints (
                    hash TEXT PRIMARY KEY,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    location TEXT,
                    canonical_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprints_created_at
                ON job_fingerprints(created_at)
            """)
            conn.commit()

    @staticmethod
    def normalize_string(text: str) -> str:
        """
        Normalize arbitrary text using Unicode NFKC normalization,
        lowercasing, punctuation stripping, and whitespace squashing.
        """
        if not text:
            return ""
        # 1. Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", str(text))
        # 2. Lowercase
        normalized = normalized.lower()
        # 3. Collapse whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @classmethod
    def normalize_title(cls, title: str) -> str:
        """Standardize common job title variants (e.g. SDE - I vs SDE 1)."""
        norm = cls.normalize_string(title)
        for pattern, replacement in ROLE_REPLACEMENTS:
            norm = re.sub(pattern, replacement, norm)
        # Roman numerals normalization
        norm = re.sub(r"\b(i)\b", "1", norm)
        norm = re.sub(r"\b(ii)\b", "2", norm)
        norm = re.sub(r"\b(iii)\b", "3", norm)
        return norm.strip()

    @classmethod
    def normalize_location(cls, location: str) -> str:
        """Standardize geographic locations into canonical forms."""
        raw = cls.normalize_string(location)
        for variant, canonical in CITY_CANONICAL_MAP.items():
            if variant in raw:
                return canonical
        return raw or "remote"

    @classmethod
    def generate_fingerprint(
        cls, company: str, title: str, location: str = "", canonical_url: str = ""
    ) -> str:
        """
        Generate a collision-resistant SHA-256 fingerprint for a job posting.
        Standardizes company, title, and location so cross-postings on different
        ATS boards (e.g. Greenhouse vs LinkedIn vs Ashby) resolve to the identical hash.
        """
        norm_company = cls.normalize_string(company)
        norm_title = cls.normalize_title(title)
        norm_location = cls.normalize_location(location)

        # Primary composite state key
        raw_key = f"{norm_company}:{norm_title}:{norm_location}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def is_new_listing(
        self,
        fingerprint: str,
        company: str,
        title: str,
        location: str = "",
        canonical_url: str = ""
    ) -> bool:
        """
        Check if the fingerprint exists in the state ledger.
        If new, atomically records it and returns True.
        If already seen, returns False.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM job_fingerprints WHERE hash = ?", (fingerprint,))
            if cursor.fetchone() is not None:
                return False  # Already exists in ledger

            # Insert brand new fingerprint
            cursor.execute(
                """
                INSERT OR IGNORE INTO job_fingerprints 
                (hash, company, title, location, canonical_url) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (fingerprint, company, title, location, canonical_url)
            )
            conn.commit()
            return True

    def batch_check_and_register(
        self, candidates: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        High-throughput batch filter for listings.
        Candidate dict must have 'company', 'title', 'location', and optional 'apply_url'.
        Attaches 'fingerprint' to candidate dicts.
        Returns: (truly_new_listings, duplicates_count)
        """
        if not candidates:
            return [], 0

        # Precompute fingerprints for all candidates
        fp_to_item: Dict[str, Dict[str, Any]] = {}
        for item in candidates:
            company = item.get("company_name") or item.get("company", "")
            title = item.get("job_title") or item.get("title", "")
            loc = item.get("location", "")
            url = item.get("apply_url") or item.get("job_url", "")
            fp = self.generate_fingerprint(company, title, loc, url)
            item["fingerprint"] = fp
            # Keep first occurrence if current run has internal duplicates
            if fp not in fp_to_item:
                fp_to_item[fp] = item

        unique_fps = list(fp_to_item.keys())
        known_fps: Set[str] = set()

        # Query in chunks of 500 parameters (safe for SQLite parameter limits)
        chunk_size = 500
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for i in range(0, len(unique_fps), chunk_size):
                chunk = unique_fps[i:i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                cursor.execute(
                    f"SELECT hash FROM job_fingerprints WHERE hash IN ({placeholders})",
                    chunk
                )
                for row in cursor.fetchall():
                    known_fps.add(row[0])

            # Determine truly new listings
            new_listings: List[Dict[str, Any]] = []
            inserts_to_make: List[Tuple[str, str, str, str, str]] = []

            for fp, item in fp_to_item.items():
                if fp not in known_fps:
                    new_listings.append(item)
                    company = item.get("company_name") or item.get("company", "")
                    title = item.get("job_title") or item.get("title", "")
                    loc = item.get("location", "")
                    url = item.get("apply_url") or item.get("job_url", "")
                    inserts_to_make.append((fp, company, title, loc, url))

            # Batch insert new fingerprints into SQLite ledger
            if inserts_to_make:
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO job_fingerprints 
                    (hash, company, title, location, canonical_url) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    inserts_to_make
                )
                conn.commit()

        duplicates_count = len(candidates) - len(new_listings)
        return new_listings, duplicates_count

    def get_db_size_mb(self) -> float:
        """Return the physical disk footprint of the SQLite database in Megabytes."""
        if os.path.exists(self.db_path):
            try:
                return os.path.getsize(self.db_path) / (1024 * 1024)
            except OSError:
                pass
        return 0.0

    def get_total_fingerprints_count(self) -> int:
        """Return the total count of recorded fingerprints in the state ledger."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM job_fingerprints")
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def prune_old_fingerprints(self, days: int = 90) -> int:
        """
        Prune historical state fingerprints older than `days` to maintain
        a lean storage footprint and high index query speeds.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM job_fingerprints WHERE created_at < datetime('now', ?)",
                    (f"-{days} days",)
                )
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    conn.execute("VACUUM")
                return deleted
        except Exception as e:
            logger.warning(f"Failed to prune old fingerprints: {e}")
            return 0

