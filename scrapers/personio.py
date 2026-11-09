"""
Personio ATS scraper for High-Concurrency Job Ingestion & ETL System.
"""

import logging
from typing import Dict, Any, List
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class PersonioScraper(BaseScraper):
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        super().__init__("personio", session, semaphore)
        self.session = session
        self.semaphore = semaphore

    async def scrape(self, company: Dict[str, Any]) -> List[JobListing]:
        jobs = []
        ats_url = company.get("ats_url", company.get("career_url"))
        if not ats_url:
            return jobs
            
        try:
            async with self.semaphore:
                # Try getting the XML feed which personio usually exposes at {company}.jobs.personio.de/xml
                import re
                match = re.search(r'([a-zA-Z0-9-]+)\.jobs\.personio\.de', ats_url)
                if match:
                    api_url = f"https://{match.group(1)}.jobs.personio.de/xml"
                    async with self.session.get(api_url, timeout=10.0) as response:
                        if response.status == 200:
                            xml_data = await response.text()
                            try:
                                root = ET.fromstring(xml_data)
                                for position in root.findall('.//position'):
                                    title_elem = position.find('name')
                                    title = title_elem.text if title_elem is not None else ""
                                    
                                    # We don't have direct URLs in some XML, need to reconstruct or look for apply_url
                                    job_id = position.get('id', '')
                                    url = f"https://{match.group(1)}.jobs.personio.de/job/{job_id}"
                                    
                                    jobs.append(JobListing(
                                        company_name=company["name"],
                                        job_title=title,
                                        location="India", # Requires more parsing if needed
                                        apply_url=url,
                                        source_platform="personio",
                                        ats_provider="personio",
                                        company_prestige_score=company.get("priority", False) and 10 or 5,
                                        estimated_salary_lpa=None,
                                        company_category=company.get("category")
                                    ))
                                return jobs
                            except Exception:
                                pass
                
                # Fallback to HTML
                async with self.session.get(ats_url, timeout=10.0) as response:
                    if response.status != 200:
                        return jobs
                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")
                    for a in soup.find_all("a", class_="job-box-link"):
                        title = a.get_text(strip=True)
                        url = a.get("href", "")
                        jobs.append(JobListing(
                            company_name=company["name"],
                            job_title=title,
                            location="India",
                            apply_url=url,
                            source_platform="personio",
                            ats_provider="personio",
                            company_prestige_score=company.get("priority", False) and 10 or 5,
                            estimated_salary_lpa=None,
                            company_category=company.get("category")
                        ))
        except Exception as e:
            logger.debug(f"[personio] Error scraping {company['name']}: {e}")
            
        return jobs
