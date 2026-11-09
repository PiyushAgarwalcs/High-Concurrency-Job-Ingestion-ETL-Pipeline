"""
BambooHR ATS scraper for High-Concurrency Job Ingestion & ETL System.
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class BambooHRScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        super().__init__("bamboohr", session, semaphore)
        self.session = session
        self.semaphore = semaphore

    async def scrape(self, company: Dict[str, Any]) -> List[JobListing]:
        jobs = []
        ats_url = company.get("ats_url", company.get("career_url"))
        if not ats_url:
            return jobs
            
        try:
            async with self.semaphore:
                # BambooHR embeds are often located at company.bamboohr.com/jobs
                match = re.search(r'([a-zA-Z0-9-]+)\.bamboohr\.com', ats_url)
                if match:
                    # Clean XML feed exists for BambooHR
                    subdomain = match.group(1)
                    api_url = f"https://{subdomain}.bamboohr.com/jobs/view.php"
                else:
                    api_url = ats_url
                    
                async with self.session.get(api_url, timeout=10.0) as response:
                    if response.status != 200:
                        return jobs
                        
                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")
                    
                    for li in soup.find_all("li", class_="ResAts__card"):
                        link = li.find("a")
                        if not link:
                            continue
                            
                        title = link.get_text(strip=True)
                        url = link.get("href", "")
                        if url.startswith("/"):
                            url = f"https://{subdomain}.bamboohr.com" + url
                            
                        # Extract location
                        loc_div = li.find("div", class_="ResAts__card-location")
                        location = loc_div.get_text(strip=True) if loc_div else "India"
                        
                        jobs.append(JobListing(
                            company_name=company["name"],
                            job_title=title,
                            location=location,
                            apply_url=url,
                            source_platform="bamboohr",
                            ats_provider="bamboohr",
                            company_prestige_score=company.get("priority", False) and 10 or 5,
                            estimated_salary_lpa=None,
                            company_category=company.get("category")
                        ))
        except Exception as e:
            logger.debug(f"[bamboohr] Error scraping {company['name']}: {e}")
            
        return jobs
