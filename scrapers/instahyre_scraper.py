"""
Instahyre Optional Scraper for High-Concurrency Job Ingestion & ETL System.
Gracefully degrades if blocked.
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class InstahyreScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        super().__init__("instahyre", session, semaphore)
        self.session = session
        self.semaphore = semaphore

    async def scrape(self, company: Dict[str, Any]) -> List[JobListing]:
        # Instahyre API is at https://www.instahyre.com/api/v1/job_search
        # We need to gracefully fail because they block heavily
        jobs = []
        if not company.get("enabled", True):
            return jobs
            
        api_url = "https://www.instahyre.com/api/v1/job_search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json"
        }
        
        # Example search parameters
        params = {
            "locations": "Bangalore",
            "job_types": "0", # Full time
            "experience": "0",
            "skills": "python,machine learning,backend"
        }
        
        try:
            async with self.semaphore:
                async with self.session.get(api_url, headers=headers, params=params, timeout=10.0) as response:
                    if response.status != 200:
                        logger.warning(f"[instahyre] HTTP {response.status}. Gracefully degrading.")
                        return jobs
                        
                    data = await response.json()
                    
                    for item in data.get("objects", []):
                        job_title = item.get("title", "")
                        comp = item.get("employer", {}).get("company_name", "")
                        url = f"https://www.instahyre.com/job-{item.get('id')}"
                        location = item.get("locations", [{}])[0].get("name", "Bangalore")
                        
                        jobs.append(JobListing(
                            company_name=comp,
                            job_title=job_title,
                            location=location,
                            apply_url=url,
                            source_platform="instahyre",
                            ats_provider="instahyre",
                            company_prestige_score=company.get("priority", False) and 10 or 5,
                            estimated_salary_lpa=None,
                            company_category=company.get("category")
                        ))
                        
        except Exception as e:
            logger.debug(f"[instahyre] Error scraping: {e}. Gracefully degrading.")
            
        return jobs
