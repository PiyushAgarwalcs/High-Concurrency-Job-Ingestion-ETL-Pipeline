"""
Workable ATS scraper for High-Concurrency Job Ingestion & ETL System.
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class WorkableScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        super().__init__("workable", session, semaphore)
        self.session = session
        self.semaphore = semaphore

    async def scrape(self, company: Dict[str, Any]) -> List[JobListing]:
        jobs = []
        ats_url = company.get("ats_url")
        if not ats_url:
            return jobs
            
        # Workable URL format: https://apply.workable.com/api/v3/accounts/{company}/jobs
        # Extract company shortname from career_url or ats_url
        import re
        match = re.search(r'apply\.workable\.com/([a-zA-Z0-9-]+)', company.get("career_url", "") + " " + ats_url)
        if not match:
            return jobs
            
        shortname = match.group(1)
        api_url = f"https://apply.workable.com/api/v3/accounts/{shortname}/jobs"
        
        payload = {
            "query": "",
            "location": [],
            "department": [],
            "worktype": [],
            "remote": []
        }
        
        try:
            async with self.semaphore:
                async with self.session.post(api_url, json=payload, timeout=10.0) as response:
                    if response.status != 200:
                        return jobs
                        
                    data = await response.json()
                    
                    for item in data.get("results", []):
                        title = item.get("title", "")
                        location = item.get("location", {}).get("city", "Remote")
                        url = f"https://apply.workable.com/{shortname}/j/{item.get('shortcode')}"
                        
                        jobs.append(JobListing(
                            company_name=company["name"],
                            job_title=title,
                            location=location,
                            apply_url=url,
                            source_platform="workable",
                            ats_provider="workable",
                            company_prestige_score=company.get("priority", False) and 10 or 5,
                            estimated_salary_lpa=None,
                            company_category=company.get("category")
                        ))
        except Exception as e:
            logger.debug(f"[workable] Error scraping {company['name']}: {e}")
            
        return jobs
