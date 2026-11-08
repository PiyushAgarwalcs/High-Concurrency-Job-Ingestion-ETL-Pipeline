"""
Workday ATS Scraper.
"""
from scrapers.base_scraper import BaseScraper
from core.models import JobListing

class WorkdayScraper(BaseScraper):
    def __init__(self, session, semaphore):
        super().__init__("Workday", session, semaphore)

    async def scrape(self, company_config) -> list[JobListing]:
        career_url = company_config.get("career_url")
        if not career_url:
            return []

        # Typically Workday endpoints for jobs are at a specific path, e.g.,
        # https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs
        # For this generic implementation, we will try to build the endpoint.
        if "myworkdayjobs.com" not in career_url:
            # If not a standard workday URL, skip or return empty (or try alternative parsing)
            return []
            
        base = career_url.rstrip("/")
        parts = base.split("/")
        tenant = parts[-2] if len(parts) >= 2 else ""
        site = parts[-1]
        
        api_url = f"{base.split('/'+tenant)[0]}/wday/cxs/{tenant}/{site}/jobs"
        
        payload = {
            "appliedFacets": {},
            "limit": 50,
            "offset": 0,
            "searchText": ""
        }
        
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        
        async with self.semaphore:
            for attempt in range(3):
                try:
                    async with self.session.post(api_url, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            break
                        if resp.status in (404, 403):
                            return []
                except Exception:
                    if attempt == 2:
                        return []

        jobs = []
        try:
            job_postings = data.get("jobPostings", [])
            for post in job_postings:
                job = JobListing(
                    company_name=company_config["name"],
                    job_title=post.get("title", ""),
                    location=post.get("locationsText", ""),
                    apply_url=f"{base}{post.get('externalPath', '')}",
                    source_platform="workday",
                    ats_provider="workday",
                    posting_date=post.get("postedOn", ""),
                    company_category=company_config.get("category"),
                )
                jobs.append(job)
        except Exception:
            pass
            
        return jobs
