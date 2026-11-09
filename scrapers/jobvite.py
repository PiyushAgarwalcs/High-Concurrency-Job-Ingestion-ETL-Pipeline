"""
Jobvite ATS scraper for High-Concurrency Job Ingestion & ETL System.
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio
from bs4 import BeautifulSoup

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class JobviteScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        super().__init__("jobvite", session, semaphore)
        self.session = session
        self.semaphore = semaphore

    async def scrape(self, company: Dict[str, Any]) -> List[JobListing]:
        jobs = []
        ats_url = company.get("ats_url", company.get("career_url"))
        if not ats_url:
            return jobs
            
        try:
            async with self.semaphore:
                async with self.session.get(ats_url, timeout=10.0) as response:
                    if response.status != 200:
                        return jobs
                        
                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")
                    
                    # Jobvite typically uses td classes for job titles
                    job_rows = soup.find_all("td", class_="jv-job-list-name")
                    if not job_rows:
                        # Alternative layout
                        job_rows = soup.find_all("div", class_="jv-job-list-name")
                        
                    for row in job_rows:
                        link = row.find("a")
                        if not link:
                            continue
                            
                        title = link.get_text(strip=True)
                        url = link.get("href", "")
                        if url.startswith("/"):
                            # Simple base URL extraction
                            from urllib.parse import urlparse
                            parsed = urlparse(ats_url)
                            base = f"{parsed.scheme}://{parsed.netloc}"
                            url = base + url
                            
                        # Try to find location (often in next sibling td)
                        location = "India"
                        loc_td = row.find_next_sibling("td", class_="jv-job-list-location")
                        if loc_td:
                            location = loc_td.get_text(strip=True)
                            
                        jobs.append(JobListing(
                            company_name=company["name"],
                            job_title=title,
                            location=location,
                            apply_url=url,
                            source_platform="jobvite",
                            ats_provider="jobvite",
                            company_prestige_score=company.get("priority", False) and 10 or 5,
                            estimated_salary_lpa=None,
                            company_category=company.get("category")
                        ))
        except Exception as e:
            logger.debug(f"[jobvite] Error scraping {company['name']}: {e}")
            
        return jobs
