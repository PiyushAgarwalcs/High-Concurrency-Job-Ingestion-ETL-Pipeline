"""
LinkedIn Easy Apply job scraper for High-Concurrency Job Ingestion & ETL System.
Targets Bangalore jobs with 12+ LPA salary using LinkedIn public job search API.
Filters for Easy Apply listings only.

Note: LinkedIn actively defends against scraping. This implementation uses
public guest APIs with respectful rate limits and graceful degradation.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from core.models import JobListing
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# LinkedIn public guest job search endpoint (no login required)
LINKEDIN_GUEST_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

# f_AL=true  => Easy Apply only
# f_E=1,2    => Entry level + Associate
# f_TPR=r604800 => Posted in last 7 days
# geoId for Bangalore / Bengaluru = 105214831
BANGALORE_GEO_ID = "105214831"
MIN_SALARY_LPA = 12

EASY_APPLY_QUERIES = [
    "machine learning engineer",
    "AI engineer",
    "data scientist",
    "software engineer",
    "backend engineer",
    "deep learning engineer",
    "NLP engineer",
    "computer vision engineer",
    "GenAI engineer",
    "LLM engineer",
    "ML engineer",
]

LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.linkedin.com/",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}


class LinkedInEasyApplyScraper(BaseScraper):
    """Scrapes LinkedIn Easy Apply jobs in Bangalore (12+ LPA) for freshers."""

    def __init__(self, session, semaphore):
        super().__init__("linkedin_easy_apply", session, semaphore)

    async def scrape(self, company_config: Dict[str, Any]) -> List[JobListing]:
        return await self._scrape_all_queries()

    async def _scrape_all_queries(self) -> List[JobListing]:
        all_jobs: List[JobListing] = []
        seen_ids: set = set()

        for query in EASY_APPLY_QUERIES:
            try:
                jobs = await self._search_query(query)
                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        all_jobs.append(job)
                await asyncio.sleep(2.0)
            except Exception as e:
                logger.warning(f"[linkedin] Query {repr(query)} failed: {e}")
                continue

        logger.info(f"[linkedin] Total Easy Apply jobs collected: {len(all_jobs)}")
        return all_jobs

    async def _search_query(self, keyword: str) -> List[JobListing]:
        params = {
            "keywords": keyword,
            "location": "Bengaluru, Karnataka, India",
            "geoId": BANGALORE_GEO_ID,
            "f_AL": "true",
            "f_E": "1,2",
            "f_TPR": "r604800",
            "start": "0",
            "count": "25",
        }
        url = f"{LINKEDIN_GUEST_SEARCH}?{urlencode(params)}"
        html = await self._get(url, headers=LINKEDIN_HEADERS)
        if not html:
            logger.warning(f"[linkedin] No response for query {repr(keyword)}")
            return []
        return self._parse_search_results(html, keyword)

    def _parse_search_results(self, html: str, query: str) -> List[JobListing]:
        jobs = []
        try:
            soup = BeautifulSoup(html, "lxml")
            cards = soup.find_all("div", class_="base-card")
            if not cards:
                cards = soup.find_all("li")
            for card in cards:
                try:
                    job = self._parse_card(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"[linkedin] Card parse error: {e}")
            logger.info(f"[linkedin] {repr(query)} => {len(jobs)} jobs parsed")
        except Exception as e:
            logger.warning(f"[linkedin] Error parsing results for {repr(query)}: {e}")
        return jobs

    def _parse_card(self, card) -> Optional[JobListing]:
        title_elem = (
            card.find("h3", class_="base-search-card__title")
            or card.find("h3")
        )
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        if not title:
            return None

        company_elem = (
            card.find("h4", class_="base-search-card__subtitle")
            or card.find("h4")
        )
        company = company_elem.get_text(strip=True) if company_elem else "Unknown"

        loc_elem = card.find("span", class_="job-search-card__location")
        location = loc_elem.get_text(strip=True) if loc_elem else "Bangalore, India"

        link_elem = (
            card.find("a", class_="base-card__full-link")
            or card.find("a", href=re.compile(r"linkedin\.com/jobs"))
        )
        if not link_elem or not link_elem.get("href"):
            return None
        apply_url = link_elem["href"].split("?")[0]

        time_elem = card.find("time")
        posting_date = None
        if time_elem and time_elem.get("datetime"):
            posting_date = time_elem["datetime"]

        salary_text = ""
        salary_elem = card.find("span", class_=re.compile(r"salary|compensation", re.I))
        if salary_elem:
            salary_text = salary_elem.get_text(strip=True)

        estimated_lpa = self._extract_lpa(salary_text)

        if estimated_lpa is not None and estimated_lpa < MIN_SALARY_LPA:
            logger.debug(
                f"[linkedin] Skipping {repr(title)} at {company} => {estimated_lpa} LPA < {MIN_SALARY_LPA} LPA"
            )
            return None

        return JobListing(
            company_name=company,
            job_title=title,
            location=location,
            apply_url=apply_url,
            source_platform="linkedin_easy_apply",
            ats_provider="linkedin",
            posting_date=posting_date,
            salary=salary_text or None,
            estimated_salary_lpa=int(estimated_lpa) if estimated_lpa else None,
            salary_confidence="high" if estimated_lpa else "low",
            company_prestige_score=6,
            job_description_summary=(
                f"LinkedIn Easy Apply | Bangalore | {title} at {company}"
                + (f" | {salary_text}" if salary_text else "")
            ),
        )

    def _extract_lpa(self, text: str) -> Optional[float]:
        if not text:
            return None
        text_lower = text.lower()
        match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*(?:[-to]+\s*\d+)?\s*lpa", text_lower)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None


class LinkedInScraper(LinkedInEasyApplyScraper):
    """Backward-compatible alias."""
    pass
