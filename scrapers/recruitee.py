"""
Recruitee ATS scraper for AI/ML Job Alert System V2.
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class RecruiteeScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        super().__init__("recruitee", session, semaphore)
        self.session = session
        self.semaphore = semaphore

    async def scrape(self, company: Dict[str, Any]) -> List[JobListing]:
        jobs = []
        career_url = company.get("career_url", "")
        ats_url = company.get("ats_url", "")
        
        # Recruitee API: https://{company}.recruitee.com/api/offers
        import re
        match = re.search(r'([a-zA-Z0-9-]+)\.recruitee\.com', career_url + " " + ats_url)
        if not match:
            return jobs
            
        subdomain = match.group(1)
        api_url = f"https://{subdomain}.recruitee.com/api/offers"
        
        try:
            async with self.semaphore:
                async with self.session.get(api_url, timeout=10.0) as response:
                    if response.status != 200:
                        return jobs
                        
                    data = await response.json()
                    offers = data.get("offers", [])
                    
                    for offer in offers:
                        title = offer.get("title", "")
                        url = offer.get("careers_url", "")
                        location = offer.get("location", "India")
                        
                        jobs.append(JobListing(
                            company_name=company["name"],
                            job_title=title,
                            location=location,
                            apply_url=url,
                            source_platform="recruitee",
                            ats_provider="recruitee",
                            company_prestige_score=company.get("priority", False) and 10 or 5,
                            estimated_salary_lpa=None,
                            company_category=company.get("category")
                        ))
        except Exception as e:
            logger.debug(f"[recruitee] Error scraping {company['name']}: {e}")
            
        return jobs
