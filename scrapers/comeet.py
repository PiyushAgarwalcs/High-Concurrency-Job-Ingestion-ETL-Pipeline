"""
Comeet ATS scraper for High-Concurrency Job Ingestion & ETL System.
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class ComeetScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        super().__init__("comeet", session, semaphore)
        self.session = session
        self.semaphore = semaphore

    async def scrape(self, company: Dict[str, Any]) -> List[JobListing]:
        jobs = []
        ats_url = company.get("ats_url", company.get("career_url"))
        if not ats_url:
            return jobs
            
        try:
            async with self.semaphore:
                # Comeet API: https://www.comeet.co/careers-api/2.0/company/X/jobs
                import re
                match = re.search(r'comeet\.co/careers-api/[^/]+/company/([^/]+)/', ats_url)
                if not match:
                    # Fallback structural gracefully
                    return jobs
                    
                api_url = f"https://www.comeet.co/careers-api/2.0/company/{match.group(1)}/jobs"
                
                async with self.session.get(api_url, timeout=10.0) as response:
                    if response.status != 200:
                        return jobs
                        
                    data = await response.json()
                    
                    for job in data:
                        title = job.get("name", "")
                        url = job.get("url_active_page", "")
                        location = job.get("location", {}).get("name", "India")
                        
                        jobs.append(JobListing(
                            company_name=company["name"],
                            job_title=title,
                            location=location,
                            apply_url=url,
                            source_platform="comeet",
                            ats_provider="comeet",
                            company_prestige_score=company.get("priority", False) and 10 or 5,
                            estimated_salary_lpa=None,
                            company_category=company.get("category")
                        ))
        except Exception as e:
            logger.debug(f"[comeet] Error scraping {company['name']}: {e}")
            
        return jobs
