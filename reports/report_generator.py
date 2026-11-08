"""
Report Generator for AI/ML Job Alert System V2.
Generates Markdown and CSV reports for Jobs, Health, and Broken Pages.
"""

import os
import csv
from datetime import datetime, timezone, timedelta
from typing import List

from database.db_manager import DBManager
from core.models import JobListing

class ReportGenerator:
    def __init__(self, db_manager: DBManager, output_dir: str = "reports"):
        self.db_manager = db_manager
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_all(self):
        """Generate all required reports."""
        await self._generate_job_summaries()
        await self._generate_health_report()
        await self._generate_broken_pages_report()

    async def _generate_job_summaries(self):
        """Generate Daily and Weekly job summaries."""
        now = datetime.now(timezone.utc)
        daily_threshold = (now - timedelta(days=1)).isoformat()
        weekly_threshold = (now - timedelta(days=7)).isoformat()
        
        daily_jobs = []
        weekly_jobs = []
        
        db = await self.db_manager.get_connection()
        db.row_factory = self.db_manager._dict_factory
        
        async with db.execute('SELECT * FROM jobs WHERE discovery_timestamp >= ? ORDER BY discovery_timestamp DESC', (daily_threshold,)) as cursor:
            rows = await cursor.fetchall()
            daily_jobs = [JobListing.from_dict(r) for r in rows]
            
        async with db.execute('SELECT * FROM jobs WHERE discovery_timestamp >= ? ORDER BY discovery_timestamp DESC', (weekly_threshold,)) as cursor:
            rows = await cursor.fetchall()
            weekly_jobs = [JobListing.from_dict(r) for r in rows]
                
        self._write_job_report(daily_jobs, "daily_summary")
        self._write_job_report(weekly_jobs, "weekly_summary")

    def _write_job_report(self, jobs: List[JobListing], name: str):
        # Markdown
        md_path = os.path.join(self.output_dir, f"{name}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {name.replace('_', ' ').title()}\n\n")
            f.write(f"Total Jobs Found: {len(jobs)}\n\n")
            f.write("| Company | Title | Location | Platform | Apply |\n")
            f.write("|---------|-------|----------|----------|-------|\n")
            for j in jobs:
                f.write(f"| {j.company_name} | {j.job_title} | {j.location} | {j.source_platform} | [Link]({j.apply_url}) |\n")
                
        # CSV
        csv_path = os.path.join(self.output_dir, f"{name}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Company", "Title", "Location", "Platform", "Apply URL", "Discovered"])
            for j in jobs:
                writer.writerow([j.company_name, j.job_title, j.location, j.source_platform, j.apply_url, j.discovery_timestamp])

    async def _generate_health_report(self):
        db = await self.db_manager.get_connection()
        db.row_factory = self.db_manager._dict_factory
        async with db.execute('SELECT * FROM source_health ORDER BY consecutive_failures DESC, average_runtime DESC') as cursor:
            health_data = await cursor.fetchall()
                
        # Markdown
        md_path = os.path.join(self.output_dir, "source_health_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Source Health Report\n\n")
            f.write("| Source | Avg Runtime (s) | Avg Jobs | Fails | Disabled |\n")
            f.write("|--------|-----------------|----------|-------|----------|\n")
            for h in health_data:
                f.write(f"| {h['source_name']} | {h['average_runtime']:.2f} | {h['average_jobs']:.1f} | {h['consecutive_failures']} | {h['disabled']} |\n")
                
        # CSV
        csv_path = os.path.join(self.output_dir, "source_health_report.csv")
        if health_data:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=health_data[0].keys())
                writer.writeheader()
                writer.writerows(health_data)

    async def _generate_broken_pages_report(self):
        db = await self.db_manager.get_connection()
        db.row_factory = self.db_manager._dict_factory
        async with db.execute('SELECT source_name, consecutive_failures, last_failure FROM source_health WHERE consecutive_failures > 0 ORDER BY consecutive_failures DESC') as cursor:
            broken_data = await cursor.fetchall()
                
        # Markdown
        md_path = os.path.join(self.output_dir, "broken_pages_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Broken Career Pages\n\n")
            f.write("Sources that failed in recent runs:\n\n")
            f.write("| Source | Consecutive Fails | Last Failure |\n")
            f.write("|--------|-------------------|--------------|\n")
            for b in broken_data:
                f.write(f"| {b['source_name']} | {b['consecutive_failures']} | {b['last_failure']} |\n")
                
        # CSV
        csv_path = os.path.join(self.output_dir, "broken_pages_report.csv")
        if broken_data:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["source_name", "consecutive_failures", "last_failure"])
                writer.writeheader()
                writer.writerows(broken_data)
