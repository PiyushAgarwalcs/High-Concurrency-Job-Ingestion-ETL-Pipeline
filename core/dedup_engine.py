"""
Deduplication Engine for High-Concurrency Job Ingestion & ETL System.
Uses the new V2 SHA256 hashing (Company + Role + Apply URL) and checks against SQLite database.
"""

import logging
from typing import List, Set
from core.models import JobListing

logger = logging.getLogger(__name__)

class DedupEngine:
    def deduplicate(self, jobs: List[JobListing]) -> List[JobListing]:
        """
        Deduplicate within the current run's results.
        If a job with the same hash appears multiple times (e.g., from different sources),
        keep the first one (which is generally the higher priority source due to sorting).
        """
        unique_jobs = []
        seen_hashes = set()

        for job in jobs:
            if job.job_id not in seen_hashes:
                unique_jobs.append(job)
                seen_hashes.add(job.job_id)

        logger.info(f"Deduplicated current run: {len(jobs)} -> {len(unique_jobs)}")
        return unique_jobs

    def find_new_jobs(self, current_jobs: List[JobListing], known_job_ids: Set[str]) -> List[JobListing]:
        """
        Compare current deduplicated jobs against all historical known jobs.
        Returns only the truly NEW jobs.
        """
        new_jobs = []
        
        for job in current_jobs:
            if job.job_id not in known_job_ids:
                new_jobs.append(job)
                
        return new_jobs
