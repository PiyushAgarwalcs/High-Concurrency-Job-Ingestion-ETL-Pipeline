"""
State Ledger: Deterministic State Fingerprinting & Deduplication.

This module provides two main capabilities:
1. Canonical String Normalization: Normalizes job titles (e.g., 'SDE - I' -> 'sde 1')
   and locations (e.g., 'Bengaluru, Karnataka' -> 'bangalore') so duplicate posts
   across multiple platforms produce matching text.
2. SHA-256 State Fingerprinting & SQLite Storage: Generates deterministic SHA-256
   hashes: SHA-256(company:title:location) and records them in an indexed SQLite table.

No AI / LLMs are used. Pure, deterministic, zero-cost Python code.
"""

import hashlib
import logging
import os
import re
import sqlite3
import unicodedata
from typing import List, Tuple, Set, Dict, Any

logger = logging.getLogger(__name__)

# Standard city name mapping for geographic normalization
CANONICAL_CITY_MAP = {
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

# Standard title replacements to match common variants
TITLE_STANDARD_REPLACEMENTS = [
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


class StateLedger:
    """
    Deterministic Job Deduplication & Persistent SQLite State Ledger.
    Maintains a fast index of seen job fingerprints to eliminate duplicate notifications.
    """

    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a SQLite connection configured for concurrent WAL mode."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _initialize_database(self):
        """Create the job_fingerprints table and index if they do not exist."""
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
    def normalize_text(raw_text: str) -> str:
        """
        Normalize text using Unicode NFKC standardization, lowercasing,
        and whitespace collapsing.
        """
        if not raw_text:
            return ""
        # 1. Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", str(raw_text))
        # 2. Lowercase
        normalized = normalized.lower()
        # 3. Collapse extra whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @classmethod
    def normalize_title(cls, title: str) -> str:
        """Standardize common job title patterns (e.g. 'Software Engineer - I' -> 'sde 1')."""
        clean = cls.normalize_text(title)
        for pattern, replacement in TITLE_STANDARD_REPLACEMENTS:
            clean = re.sub(pattern, replacement, clean)
        # Standardize Roman numerals commonly used in tech titles
        clean = re.sub(r"\b(i)\b", "1", clean)
        clean = re.sub(r"\b(ii)\b", "2", clean)
        clean = re.sub(r"\b(iii)\b", "3", clean)
        return clean.strip()

    @classmethod
    def normalize_location(cls, location: str) -> str:
        """Standardize location strings into canonical city names."""
        clean = cls.normalize_text(location)
        for variant, canonical in CANONICAL_CITY_MAP.items():
            if variant in clean:
                return canonical
        return clean or "remote"

    @classmethod
    def generate_fingerprint(
        cls, company: str, title: str, location: str = "", canonical_url: str = ""
    ) -> str:
        """
        Generate a unique, collision-resistant 64-character SHA-256 fingerprint.
        
        Because company, title, and location are standardized, if the same job
        is listed on Greenhouse and LinkedIn, both will generate the exact same hash.
        """
        norm_company = cls.normalize_text(company)
        norm_title = cls.normalize_title(title)
        norm_location = cls.normalize_location(location)

        composite_key = f"{norm_company}:{norm_title}:{norm_location}"
        return hashlib.sha256(composite_key.encode("utf-8")).hexdigest()

    def is_new_listing(
        self,
        fingerprint: str,
        company: str,
        title: str,
        location: str = "",
        canonical_url: str = ""
    ) -> bool:
        """
        Check if a job fingerprint is brand new.
        If new: records it in the database and returns True.
        If already seen: returns False.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM job_fingerprints WHERE hash = ?", (fingerprint,))
            if cursor.fetchone() is not None:
                return False  # Already exists in ledger

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
        self, listings: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filter a batch of listings at high speed.
        Returns: (new_unique_listings, duplicate_count)
        """
        if not listings:
            return [], 0

        # Calculate fingerprints for each candidate
        fingerprint_map: Dict[str, Dict[str, Any]] = {}
        for item in listings:
            company = item.get("company_name") or item.get("company", "")
            title = item.get("job_title") or item.get("title", "")
            location = item.get("location", "")
            url = item.get("apply_url") or item.get("job_url", "")
            
            fingerprint = self.generate_fingerprint(company, title, location, url)
            item["fingerprint"] = fingerprint
            
            # If current run has duplicate entries, keep the first one
            if fingerprint not in fingerprint_map:
                fingerprint_map[fingerprint] = item

        unique_fingerprints = list(fingerprint_map.keys())
        already_known: Set[str] = set()

        # Query in chunks of 500 to stay well within SQLite limits
        chunk_size = 500
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for i in range(0, len(unique_fingerprints), chunk_size):
                chunk = unique_fingerprints[i:i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                cursor.execute(
                    f"SELECT hash FROM job_fingerprints WHERE hash IN ({placeholders})",
                    chunk
                )
                for row in cursor.fetchall():
                    already_known.add(row[0])

            # Separate new listings from duplicates
            new_listings: List[Dict[str, Any]] = []
            records_to_insert: List[Tuple[str, str, str, str, str]] = []

            for fp, item in fingerprint_map.items():
                if fp not in already_known:
                    new_listings.append(item)
                    company = item.get("company_name") or item.get("company", "")
                    title = item.get("job_title") or item.get("title", "")
                    location = item.get("location", "")
                    url = item.get("apply_url") or item.get("job_url", "")
                    records_to_insert.append((fp, company, title, location, url))

            # Batch insert new fingerprints
            if records_to_insert:
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO job_fingerprints 
                    (hash, company, title, location, canonical_url) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    records_to_insert
                )
                conn.commit()

        duplicate_count = len(listings) - len(new_listings)
        return new_listings, duplicate_count

    def get_db_size_mb(self) -> float:
        """Return the SQLite database file size in Megabytes."""
        if os.path.exists(self.db_path):
            try:
                return os.path.getsize(self.db_path) / (1024 * 1024)
            except OSError:
                pass
        return 0.0

    def get_total_fingerprints_count(self) -> int:
        """Return the total number of tracked fingerprints in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM job_fingerprints")
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def prune_old_fingerprints(self, days: int = 90) -> int:
        """Prune fingerprints older than `days` to keep database fast and lean."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM job_fingerprints WHERE created_at < datetime('now', ?)",
                    (f"-{days} days",)
                )
                deleted_rows = cursor.rowcount
                conn.commit()
                if deleted_rows > 0:
                    conn.execute("VACUUM")
                return deleted_rows
        except Exception as e:
            logger.warning(f"Failed to prune old fingerprints: {e}")
            return 0

