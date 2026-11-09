"""
Async SQLite Database Manager for High-Concurrency Job Ingestion & ETL System.
Provides connection pooling and handles schema creation and queries.
"""

import aiosqlite
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from core.models import JobListing

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def get_connection(self) -> aiosqlite.Connection:
        """Get or initialize the persistent SQLite connection in WAL mode."""
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path, timeout=30.0)
            await self._conn.execute("PRAGMA journal_mode=WAL;")
            await self._conn.execute("PRAGMA synchronous=NORMAL;")
        return self._conn

    async def close(self) -> None:
        """Close the persistent SQLite connection if open."""
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception as e:
                logger.warning(f"Error closing DB connection: {e}")
            finally:
                self._conn = None

    async def init_db(self):
        """Initialize the database schema."""
        async with self._lock:
            db = await self.get_connection()
            # 1. Jobs Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    company_name TEXT,
                    job_title TEXT,
                    location TEXT,
                    apply_url TEXT,
                    source_platform TEXT,
                    ats_provider TEXT,
                    salary TEXT,
                    estimated_salary_lpa INTEGER,
                    salary_confidence TEXT,
                    experience_required TEXT,
                    required_skills TEXT,
                    job_description_summary TEXT,
                    posting_date TEXT,
                    company_category TEXT,
                    company_prestige_score INTEGER,
                    discovery_timestamp TEXT,
                    last_seen TEXT,
                    rank_score REAL,
                    role_priority INTEGER,
                    notification_sent BOOLEAN,
                    status TEXT
                )
            ''')
            # Indexes for jobs
            await db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_name)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen)')

            # 2. Companies Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    career_url TEXT,
                    ats TEXT,
                    ats_url TEXT,
                    priority BOOLEAN,
                    enabled BOOLEAN,
                    bangalore BOOLEAN,
                    category TEXT
                )
            ''')

            # 3. Applications Tracker Table (Linked to jobs)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE,
                    status TEXT,
                    applied_date TEXT,
                    notes TEXT,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
            ''')

            # 4. Notifications Log Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    sent_at TEXT,
                    telegram_message_id TEXT,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
            ''')

            # 5. History Table (General historical events)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    description TEXT,
                    timestamp TEXT
                )
            ''')
            
            # 6. Source Health Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS source_health (
                    source_name TEXT PRIMARY KEY,
                    last_success TEXT,
                    last_failure TEXT,
                    average_runtime REAL DEFAULT 0.0,
                    average_jobs REAL DEFAULT 0.0,
                    consecutive_failures INTEGER DEFAULT 0,
                    total_runs INTEGER DEFAULT 0,
                    disabled BOOLEAN DEFAULT 0,
                    retry_after TEXT
                )
            ''')
            
            # Safe migrations for existing DB
            for col, col_type in [("disabled", "BOOLEAN DEFAULT 0"), ("retry_after", "TEXT")]:
                try:
                    await db.execute(f'ALTER TABLE source_health ADD COLUMN {col} {col_type}')
                except Exception:
                    pass
                    
            # Safe migrations for jobs table
            for col, col_type in [
                ("estimated_salary_lpa", "INTEGER"), 
                ("salary_confidence", "TEXT"),
                ("posting_date", "TEXT")
            ]:
                try:
                    await db.execute(f'ALTER TABLE jobs ADD COLUMN {col} {col_type}')
                except Exception:
                    pass

            # 7. Workflow Runs Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT,
                    finished_at TEXT,
                    runtime REAL,
                    jobs_found INTEGER,
                    duplicates INTEGER,
                    notifications_sent INTEGER,
                    companies_checked INTEGER,
                    companies_failed INTEGER,
                    errors TEXT
                )
            ''')
            
            # 8. GitHub Sources Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS github_sources (
                    repo_url TEXT PRIMARY KEY,
                    last_commit_hash TEXT,
                    last_checked TEXT
                )
            ''')

            await db.commit()

    def _dict_factory(self, cursor, row):
        """Convert aiosqlite rows to dicts."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    async def get_all_job_ids(self) -> set[str]:
        """Fetch all known job hashes to prevent duplicates across runs."""
        async with self._lock:
            db = await self.get_connection()
            async with db.execute('SELECT job_id FROM jobs') as cursor:
                rows = await cursor.fetchall()
                return {row[0] for row in rows}
                
    async def get_job_by_id(self, job_id: str) -> Optional[JobListing]:
        """Fetch a specific job by its ID."""
        async with self._lock:
            db = await self.get_connection()
            db.row_factory = self._dict_factory
            async with db.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return JobListing.from_dict(row)
                return None

    async def save_jobs(self, jobs: List[JobListing]) -> None:
        """Save new jobs or update last_seen for existing jobs."""
        if not jobs:
            return
            
        async with self._lock:
            db = await self.get_connection()
            now = datetime.now(timezone.utc).isoformat()
            
            for job in jobs:
                job.last_seen = now
                data = job.to_dict()
                
                # Check if job exists
                async with db.execute('SELECT job_id FROM jobs WHERE job_id = ?', (job.job_id,)) as cursor:
                    exists = await cursor.fetchone()
                    
                if exists:
                    # Update last_seen
                    await db.execute(
                        'UPDATE jobs SET last_seen = ? WHERE job_id = ?', 
                        (now, job.job_id)
                    )
                else:
                    # Insert new job
                    columns = ', '.join(data.keys())
                    placeholders = ', '.join(['?' for _ in data])
                    values = tuple(data.values())
                    
                    await db.execute(
                        f'INSERT INTO jobs ({columns}) VALUES ({placeholders})',
                        values
                    )
            
            await db.commit()
            
    async def mark_notification_sent(self, job_id: str, telegram_msg_id: str = None) -> None:
        """Mark a job as notified and log it."""
        now = datetime.now(timezone.utc).isoformat()
        async with self._lock:
            db = await self.get_connection()
            await db.execute(
                'UPDATE jobs SET notification_sent = ? WHERE job_id = ?', 
                (True, job_id)
            )
            await db.execute(
                'INSERT INTO notifications (job_id, sent_at, telegram_message_id) VALUES (?, ?, ?)',
                (job_id, now, telegram_msg_id)
            )
            await db.commit()

    async def record_workflow_run(self, stats: Dict[str, Any]) -> None:
        """Record the statistics of a workflow run."""
        async with self._lock:
            db = await self.get_connection()
            await db.execute('''
                INSERT INTO workflow_runs (
                    started_at, finished_at, runtime, jobs_found, 
                    duplicates, notifications_sent, companies_checked, 
                    companies_failed, errors
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stats.get('started_at'),
                stats.get('finished_at'),
                stats.get('runtime', 0.0),
                stats.get('jobs_found', 0),
                stats.get('duplicates', 0),
                stats.get('notifications_sent', 0),
                stats.get('companies_checked', 0),
                stats.get('companies_failed', 0),
                json.dumps(stats.get('errors', []))
            ))
            await db.commit()
            
    async def update_source_health(self, source_name: str, success: bool, runtime: float, jobs_found: int) -> None:
        """Update health metrics for a given source/company."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        
        async with self._lock:
            db = await self.get_connection()
            db.row_factory = self._dict_factory
            async with db.execute('SELECT * FROM source_health WHERE source_name = ?', (source_name,)) as cursor:
                row = await cursor.fetchone()
                
            if not row:
                # First time seeing this source
                await db.execute('''
                    INSERT INTO source_health (
                        source_name, last_success, last_failure, average_runtime, 
                        average_jobs, consecutive_failures, total_runs, disabled, retry_after
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    source_name, 
                    now_str if success else None, 
                    None if success else now_str, 
                    runtime, jobs_found, 0 if success else 1, 1, 0, None
                ))
            else:
                # Update moving averages
                total_runs = row.get('total_runs', 0) + 1
                avg_runtime = row.get('average_runtime', 0.0) + ((runtime - row.get('average_runtime', 0.0)) / total_runs)
                avg_jobs = row.get('average_jobs', 0.0) + ((jobs_found - row.get('average_jobs', 0.0)) / total_runs)
                consecutive_failures = 0 if success else row.get('consecutive_failures', 0) + 1
                
                last_success = now_str if success else row.get('last_success')
                last_failure = None if success else now_str
                
                disabled = 0
                retry_after = None
                
                # FIX #7/#14: raise threshold to 5 consecutive failures before disabling;
                # retry window extended to 72 h so sources get a chance to recover.
                if consecutive_failures >= 5:
                    disabled = 1
                    retry_after = (now + timedelta(hours=72)).isoformat()
                
                await db.execute('''
                    UPDATE source_health 
                    SET last_success = ?, last_failure = ?, average_runtime = ?, 
                        average_jobs = ?, consecutive_failures = ?, total_runs = ?,
                        disabled = ?, retry_after = ?
                    WHERE source_name = ?
                ''', (last_success, last_failure, avg_runtime, avg_jobs, consecutive_failures, total_runs, disabled, retry_after, source_name))
                
            await db.commit()

    async def is_source_disabled(self, source_name: str) -> bool:
        """
        Check if a source is currently disabled and should be skipped.
        FIX: uses proper datetime objects for comparison (not ISO string comparison,
        which breaks across UTC-offset formats).
        """
        now = datetime.now(timezone.utc)
        async with self._lock:
            db = await self.get_connection()
            db.row_factory = self._dict_factory
            async with db.execute(
                'SELECT disabled, retry_after FROM source_health WHERE source_name = ?',
                (source_name,)
            ) as cursor:
                row = await cursor.fetchone()

            if row and row.get('disabled'):
                retry_after_str = row.get('retry_after')
                if retry_after_str:
                    try:
                        retry_after_dt = datetime.fromisoformat(retry_after_str)
                        # Make timezone-aware if naive
                        if retry_after_dt.tzinfo is None:
                            retry_after_dt = retry_after_dt.replace(tzinfo=timezone.utc)
                        if now < retry_after_dt:
                            return True
                    except (ValueError, TypeError):
                        pass
                # Retry window expired — re-enable
                await db.execute(
                    'UPDATE source_health SET disabled = 0, consecutive_failures = 0, retry_after = NULL WHERE source_name = ?',
                    (source_name,)
                )
                await db.commit()
                return False
        return False


    async def prune_old_jobs(self, days: int = 90) -> int:
        """Delete job records, notifications, and workflow telemetry older than `days` days to keep the DB lean.
        Returns the number of job rows deleted.
        """
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        async with self._lock:
            db = await self.get_connection()
            # 1. Prune jobs
            cursor = await db.execute(
                "DELETE FROM jobs WHERE discovery_timestamp < ? AND notification_sent = 1",
                (cutoff,)
            )
            deleted = cursor.rowcount

            # 2. Prune old notifications logs
            await db.execute(
                "DELETE FROM notifications WHERE sent_at < ?",
                (cutoff,)
            )

            # 3. Prune old workflow run history
            await db.execute(
                "DELETE FROM workflow_runs WHERE started_at < ?",
                (cutoff,)
            )

            # 4. Prune old general history events
            await db.execute(
                "DELETE FROM history WHERE timestamp < ?",
                (cutoff,)
            )

            await db.commit()
        if deleted:
            logger.info(f"Pruned {deleted} jobs and associated telemetry logs older than {days} days from DB")
        return deleted

    async def get_github_commit_hash(self, repo_url: str) -> Optional[str]:
        async with self._lock:
            db = await self.get_connection()
            db.row_factory = self._dict_factory
            async with db.execute('SELECT last_commit_hash FROM github_sources WHERE repo_url = ?', (repo_url,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row.get('last_commit_hash')
        return None
        
    async def update_github_commit_hash(self, repo_url: str, commit_hash: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self._lock:
            db = await self.get_connection()
            await db.execute('''
                INSERT INTO github_sources (repo_url, last_commit_hash, last_checked) 
                VALUES (?, ?, ?)
                ON CONFLICT(repo_url) DO UPDATE SET 
                last_commit_hash=excluded.last_commit_hash, 
                last_checked=excluded.last_checked
            ''', (repo_url, commit_hash, now))
            await db.commit()
