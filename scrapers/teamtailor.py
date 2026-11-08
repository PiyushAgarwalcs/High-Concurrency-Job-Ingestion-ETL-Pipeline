"""
TeamTailor ATS scraper for AI/ML Job Alert System V2.
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio
from bs4 import BeautifulSoup

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class TeamTailorScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        super().__init__("teamtailor", session, semaphore)
        self.session = session
        self.semaphore = semaphore

    async def scrape(self, company: Dict[str, Any]) -> List[JobListing]:
        jobs = []
        ats_url = company.get("ats_url", company.get("career_url"))
        if not ats_url:
            return jobs
            
        # Often teamtailor exposes jobs.json or jobs?format=json
        api_url = ats_url.rstrip("/") + "/jobs"
        headers = {"Accept": "application/json"}
        
        try:
            async with self.semaphore:
                async with self.session.get(api_url, headers=headers, timeout=10.0) as response:
                    if response.status != 200:
                        return jobs
                        
                    content_type = response.headers.get("Content-Type", "")
                    
                    if "json" in content_type:
                        data = await response.json()
                        # Parse standard JSON response
                        # Teamtailor JSON format varies by API version, attempt graceful degradation
                        job_list = data.get("data", []) if isinstance(data, dict) else data
                        if not isinstance(job_list, list):
                            return jobs
                            
                        for item in job_list:
                            attributes = item.get("attributes", item)
                            title = attributes.get("title", "")
                            url = attributes.get("careers-url", attributes.get("url", ""))
                            # Location might be in relationships
                            location = "India"
                            
                            if title and url:
                                jobs.append(JobListing(
                                    company_name=company["name"],
                                    job_title=title,
                                    location=location,
                                    apply_url=url,
                                    source_platform="teamtailor",
                                    ats_provider="teamtailor",
                                    company_prestige_score=company.get("priority", False) and 10 or 5,
                                    estimated_salary_lpa=None,
                                    company_category=company.get("category")
                                ))
                    else:
                        # Fallback to HTML parsing
                        html = await response.text()
                        soup = BeautifulSoup(html, "lxml")
                        
                        job_items = soup.find_all("li", class_="job-item")
                        for item in job_items:
                            link = item.find("a")
                            if not link: continue
                            title_elem = item.find("span", class_="job-title") or link
                            title = title_elem.get_text(strip=True)
                            url = link.get("href", "")
                            
                            jobs.append(JobListing(
                                company_name=company["name"],
                                job_title=title,
                                location="India",
                                apply_url=url,
                                source_platform="teamtailor",
                                ats_provider="teamtailor",
                                company_prestige_score=company.get("priority", False) and 10 or 5,
                                estimated_salary_lpa=None,
                                company_category=company.get("category")
                            ))
                            
        except Exception as e:
            logger.debug(f"[teamtailor] Error scraping {company['name']}: {e}")
            
        return jobs
