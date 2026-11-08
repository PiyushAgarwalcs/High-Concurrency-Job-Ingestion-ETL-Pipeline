"""
GitHub Job Sources Scraper for AI/ML Job Alert System V2.
Scrapes markdown files from community-maintained job lists (e.g., PittCSC, Ouckah).
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio
import re

from core.models import JobListing
from scrapers.base_scraper import BaseScraper
from database.db_manager import DBManager

logger = logging.getLogger(__name__)

class GitHubRepoScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, db_manager: DBManager):
        super().__init__("github", session, semaphore)
        self.session = session
        self.semaphore = semaphore
        self.db_manager = db_manager

    async def scrape(self, source: Dict[str, Any]) -> List[JobListing]:
        jobs = []
        repo_url = source.get("repo_url")
        if not repo_url:
            return jobs
            
        try:
            # Example API: https://api.github.com/repos/PittCSC/Summer2024-Internships/commits?path=README.md&page=1&per_page=1
            match = re.search(r'github\.com/([^/]+)/([^/]+)', repo_url)
            if not match:
                return jobs
                
            owner, repo = match.group(1), match.group(2)
            file_path = source.get("file_path", "README.md")
            
            # 1. Check commit hash
            commit_api = f"https://api.github.com/repos/{owner}/{repo}/commits?path={file_path}&per_page=1"
            headers = {"Accept": "application/vnd.github.v3+json"}
            
            async with self.semaphore:
                async with self.session.get(commit_api, headers=headers, timeout=10.0) as response:
                    if response.status != 200:
                        return jobs
                    commits = await response.json()
                    if not commits:
                        return jobs
                        
                    latest_hash = commits[0].get("sha")
                    stored_hash = await self.db_manager.get_github_commit_hash(repo_url)
                    
                    if stored_hash == latest_hash:
                        logger.info(f"Skipping {repo_url} - No new commits.")
                        return jobs
                        
                # 2. Fetch raw markdown
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{file_path}"
                async with self.session.get(raw_url, timeout=10.0) as response:
                    if response.status == 404:
                        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{file_path}"
                        async with self.session.get(raw_url, timeout=10.0) as response2:
                            if response2.status != 200:
                                return jobs
                            md_content = await response2.text()
                    elif response.status != 200:
                        return jobs
                    else:
                        md_content = await response.text()
                        
                # 3. Parse Markdown for standard table rows | Company | Role | Location | Application Link |
                # Very heuristic based, meant for typical student lists
                for line in md_content.split('\n'):
                    if "|" in line and "http" in line:
                        cols = [c.strip() for c in line.split("|")]
                        if len(cols) >= 3:
                            # Try to extract URL
                            url_match = re.search(r'\]\((https?://[^)]+)\)', line)
                            url = url_match.group(1) if url_match else ""
                            if not url:
                                # Try raw url
                                raw_url_match = re.search(r'(https?://[^\s]+)', line)
                                url = raw_url_match.group(1) if raw_url_match else ""
                                
                            if url:
                                # Extract Company Name (usually first column or linked text)
                                comp_match = re.search(r'\[([^\]]+)\]', cols[1])
                                company_name = comp_match.group(1) if comp_match else cols[1].replace("*", "")
                                if company_name:
                                    jobs.append(JobListing(
                                        company_name=company_name,
                                        job_title="Software Engineer", # Fallback, often missing in tables
                                        location="India", # Most github repos are US based, our filter engine will reject non-bangalore
                                        apply_url=url,
                                        source_platform="github",
                                        ats_provider="unknown",
                                        company_prestige_score=source.get("priority", False) and 10 or 5,
                                        estimated_salary_lpa=None,
                                        company_category=source.get("category")
                                    ))
                
                # 4. Update Commit Hash
                await self.db_manager.update_github_commit_hash(repo_url, latest_hash)
                
        except Exception as e:
            logger.debug(f"[github] Error scraping {repo_url}: {e}")
            
        return jobs
