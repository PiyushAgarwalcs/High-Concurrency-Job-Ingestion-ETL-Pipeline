"""
Ashby ATS Scraper — with India/Bangalore location pre-filter.
"""
import re
from scrapers.base_scraper import BaseScraper
from core.models import JobListing

_INDIA_RE = re.compile(
    r"bangalore|bengaluru|india|remote|karnataka|hyderabad|pune|chennai|mumbai|delhi|gurugram",
    re.IGNORECASE,
)

class AshbyScraper(BaseScraper):
    def __init__(self, session, semaphore):
        super().__init__("Ashby", session, semaphore)

    async def scrape(self, company_config) -> list[JobListing]:
        board_id = company_config.get("ats_url")
        if not board_id:
            return []

        api_url = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
        payload = {
            "operationName": "ApiJobBoardWithTeams",
            "variables": {"organizationHostedJobsPageName": board_id},
            "query": (
                "query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {"
                "  jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {"
                "    jobPostings { id title locationName publishedAt jobPageUrl } } }"
            ),
        }
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

        data = None
        import aiohttp

        async with self.semaphore:
            for attempt in range(2):
                try:
                    async with self.session.post(
                        api_url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=12.0)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            break
                        if resp.status in (404, 403):
                            return []
                except Exception:
                    if attempt == 1:
                        return []

        if not data:
            return []

        try:
            postings = data["data"]["jobBoard"]["jobPostings"]
        except (KeyError, TypeError):
            return []

        jobs = []
        for post in postings:
            loc = post.get("locationName", "") or ""
            if loc and not _INDIA_RE.search(loc):
                continue

            title = post.get("title", "")
            if not title:
                continue

            job = JobListing(
                company_name=company_config["name"],
                job_title=title,
                location=loc or "India",
                apply_url=post.get("jobPageUrl", ""),
                source_platform="ashby",
                ats_provider="ashby",
                posting_date=post.get("publishedAt", ""),
                company_category=company_config.get("category"),
                company_prestige_score=company_config.get("prestige_score", 7),
            )
            jobs.append(job)

        return jobs
