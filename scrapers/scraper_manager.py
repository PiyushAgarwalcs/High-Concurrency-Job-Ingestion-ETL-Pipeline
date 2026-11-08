"""
Scraper Manager for AI/ML Job Alert System V3.
Orchestrates async scraping based on configuration, Priority Queue,
and DeployGuard Domain-Aware Circuit Breaking and Concurrency Throttling.
"""
import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Tuple, Optional
import time

from core.models import JobListing
from config.settings import (
    MAX_CONCURRENT_REQUESTS,
    PER_HOST_CONCURRENCY,
    CIRCUIT_BREAKER_FAILURES,
    CIRCUIT_BREAKER_COOLDOWN,
    COMPANIES_LIST,
)
from database.db_manager import DBManager
from core.validator import CompanyValidator
from core.request_guard import CircuitBreaker, JobSchema
from core.metrics import MetricsTracker
from scrapers.linkedin_scraper import LinkedInEasyApplyScraper

logger = logging.getLogger(__name__)

# ATS name -> scraper class (lazily imported to keep startup fast)
_ATS_MAP = {
    "greenhouse":     ("scrapers.greenhouse",           "GreenhouseScraper"),
    "lever":          ("scrapers.lever",                "LeverScraper"),
    "ashby":          ("scrapers.ashby",                "AshbyScraper"),
    "workday":        ("scrapers.workday",              "WorkdayScraper"),
    "smartrecruiters":("scrapers.smartrecruiters",      "SmartRecruitersScraper"),
    "workable":       ("scrapers.workable",             "WorkableScraper"),
    "jobvite":        ("scrapers.jobvite",              "JobviteScraper"),
    "teamtailor":     ("scrapers.teamtailor",           "TeamTailorScraper"),
    "bamboohr":       ("scrapers.bamboohr",             "BambooHRScraper"),
    "recruitee":      ("scrapers.recruitee",            "RecruiteeScraper"),
    "personio":       ("scrapers.personio",             "PersonioScraper"),
    "comeet":         ("scrapers.comeet",               "ComeetScraper"),
    "icims":          ("scrapers.icims",                "ICIMSScraper"),
    "oracle":         ("scrapers.oracle",               "OracleScraper"),
    "sap":            ("scrapers.sap",                  "SAPScraper"),
    "instahyre":      ("scrapers.instahyre_scraper",    "InstahyreScraper"),
    "github":         ("scrapers.github_scraper",       "GitHubRepoScraper"),
    "custom":         ("scrapers.company_career_scraper", "CustomCareerScraper"),
    "custom_career":  ("scrapers.company_career_scraper", "CustomCareerScraper"),
}


def _build_scraper(ats: str, session, semaphore, db_manager=None):
    """Instantiate the correct scraper for a given ATS name. Returns None if unknown."""
    if ats not in _ATS_MAP:
        return None
    module_path, class_name = _ATS_MAP[ats]
    import importlib
    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        # GitHubRepoScraper needs db_manager
        if ats == "github" and db_manager is not None:
            return cls(session, semaphore, db_manager)
        return cls(session, semaphore)
    except Exception as e:
        logger.error(f"Failed to import scraper for ATS '{ats}': {e}", exc_info=True)
        return None


class ScraperManager:
    def __init__(
        self,
        db_manager: DBManager,
        circuit_breaker: Optional[CircuitBreaker] = None,
        metrics_tracker: Optional[MetricsTracker] = None,
    ):
        self.db_manager = db_manager
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=CIRCUIT_BREAKER_FAILURES,
            cooldown_seconds=CIRCUIT_BREAKER_COOLDOWN,
        )
        self.metrics_tracker = metrics_tracker or MetricsTracker()
        self._domain_semaphores: Dict[str, asyncio.Semaphore] = {}

    def _get_domain_semaphore(self, domain: str) -> asyncio.Semaphore:
        """Get or initialize a host-level concurrency semaphore (RequestGuard isolation)."""
        if domain not in self._domain_semaphores:
            self._domain_semaphores[domain] = asyncio.Semaphore(PER_HOST_CONCURRENCY)
        return self._domain_semaphores[domain]

    # ─────────────────────────────────────────────────────────────────────────
    # Per-company processing with RequestGuard & StateLedger Gates
    # ─────────────────────────────────────────────────────────────────────────

    async def _process_company(
        self,
        session: aiohttp.ClientSession,
        global_semaphore: asyncio.Semaphore,
        company: Dict[str, Any],
    ) -> Tuple[str, bool, float, List[JobListing], str]:
        """
        Process a single company source through RequestGuard circuit breaker
        and dual-semaphore concurrency throttles.
        """
        start_time = time.time()
        company_name = company.get("name", "Unknown")
        career_url = company.get("career_url") or company.get("ats_url", "")
        domain = self.circuit_breaker.extract_domain(career_url)

        # 1. RequestGuard Circuit Breaker Gate
        if not self.circuit_breaker.can_request(domain):
            logger.warning(
                f"🛡️  [RequestGuard] Circuit Breaker OPEN for domain '{domain}' - Isolating '{company_name}'"
            )
            self.metrics_tracker.http_errors_isolated += 1
            self.metrics_tracker.circuit_breaker_trips += 1
            return company_name, False, 0.0, [], f"RequestGuard: Circuit Breaker OPEN for '{domain}'"

        host_semaphore = self._get_domain_semaphore(domain)

        try:
            # Enforce dual-level rate limiting: Global + Domain-Specific
            async with global_semaphore:
                async with host_semaphore:
                    # 2. Skip disabled sources (with auto-recovery after retry window)
                    is_disabled = await self.db_manager.is_source_disabled(company_name)
                    if is_disabled:
                        logger.info(f"⏭  Skipping {company_name} (temporarily disabled due to consecutive failures)")
                        return company_name, False, 0.0, [], "Source disabled"

                    # 3. Validate career page + auto-detect ATS
                    validator = CompanyValidator(session)
                    is_reachable, detected_ats, feed_url, error_msg = await validator.validate_and_detect(company)

                    if not is_reachable:
                        logger.warning(f"[{company_name}] Career page unreachable: {error_msg}")
                        # Record failure against circuit breaker for status 429/503/timeout
                        if any(err_code in error_msg for err_code in ("429", "503", "Timeout")):
                            self.circuit_breaker.record_failure(domain, error_msg)
                        self.metrics_tracker.http_errors_isolated += 1

                        await self.db_manager.update_source_health(
                            company_name, False, time.time() - start_time, 0
                        )
                        return company_name, False, time.time() - start_time, [], error_msg

                    # 4. Resolve ATS
                    ats = (detected_ats or company.get("ats", "")).strip().lower()
                    if not ats:
                        ats = company.get("ats", "unknown").strip().lower()

                    company["ats"] = ats

                    if feed_url:
                        logger.info(f"[{company_name}] RSS feed detected: {feed_url} (using ATS: {ats})")

                    # 5. Build scraper
                    scraper = _build_scraper(ats, session, global_semaphore, self.db_manager)
                    if scraper is None:
                        msg = f"No scraper for ATS '{ats}'"
                        logger.warning(f"[{company_name}] {msg}")
                        await self.db_manager.update_source_health(
                            company_name, False, time.time() - start_time, 0
                        )
                        return company_name, False, time.time() - start_time, [], msg

                    # 6. Scrape
                    raw_jobs = await scraper.safe_scrape(company)
                    runtime = time.time() - start_time

                    # 7. RequestGuard Schema Validation & Quarantine
                    validated_jobs: List[JobListing] = []
                    for raw in raw_jobs:
                        try:
                            payload = JobSchema.from_job_listing(raw)
                            validated_jobs.append(payload.to_job_listing())
                        except Exception as val_err:
                            self.metrics_tracker.schema_quarantined_count += 1
                            logger.debug(
                                f"🛡️  [RequestGuard] Quarantined invalid record from '{company_name}': {val_err}"
                            )

                    # Mark success in Circuit Breaker and DB Manager
                    self.circuit_breaker.record_success(domain)
                    self.metrics_tracker.successful_fetches += 1

                    await self.db_manager.update_source_health(
                        company_name, True, runtime, len(validated_jobs)
                    )

                    if validated_jobs:
                        logger.info(f"[{company_name}] ✓ {len(validated_jobs)} valid jobs in {runtime:.1f}s")
                    else:
                        logger.debug(f"[{company_name}] 0 open positions ({runtime:.1f}s) — not a failure")

                    return company_name, True, runtime, validated_jobs, ""

        except Exception as e:
            runtime = time.time() - start_time
            err_str = str(e) or e.__class__.__name__
            logger.error(
                f"[{company_name}] Unhandled exception during scraping: {err_str}",
                exc_info=True,
            )
            self.circuit_breaker.record_failure(domain, err_str)
            self.metrics_tracker.http_errors_isolated += 1

            try:
                await self.db_manager.update_source_health(
                    company_name, False, runtime, 0
                )
            except Exception:
                pass
            return company_name, False, runtime, [], err_str

    # ─────────────────────────────────────────────────────────────────────────
    # LinkedIn Easy Apply (with RequestGuard validation)
    # ─────────────────────────────────────────────────────────────────────────

    async def _scrape_linkedin(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
    ) -> List[JobListing]:
        """Run LinkedIn Easy Apply scraper and enforce RequestGuard schema validation."""
        domain = "linkedin.com"
        if not self.circuit_breaker.can_request(domain):
            logger.warning("🛡️  [RequestGuard] Circuit breaker OPEN for linkedin.com - Skipping LinkedIn.")
            self.metrics_tracker.http_errors_isolated += 1
            return []

        try:
            scraper = LinkedInEasyApplyScraper(session, semaphore)
            raw_jobs = await scraper.safe_scrape({})
            validated_jobs: List[JobListing] = []
            for raw in raw_jobs:
                try:
                    payload = JobSchema.from_job_listing(raw)
                    validated_jobs.append(payload.to_job_listing())
                except Exception as val_err:
                    self.metrics_tracker.schema_quarantined_count += 1
                    logger.debug(f"🛡️  [RequestGuard] Quarantined LinkedIn job: {val_err}")

            self.circuit_breaker.record_success(domain)
            self.metrics_tracker.successful_fetches += 1
            logger.info(f"[LinkedIn Easy Apply] Collected {len(validated_jobs)} validated jobs")
            return validated_jobs
        except Exception as e:
            logger.error(f"[LinkedIn Easy Apply] Scraper failed: {e}", exc_info=True)
            self.circuit_breaker.record_failure(domain, str(e))
            self.metrics_tracker.http_errors_isolated += 1
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────

    async def scrape_all(self) -> Tuple[List[JobListing], Dict[str, Any]]:
        """Run all scrapers through DeployGuard concurrency and isolation gateway."""

        if not COMPANIES_LIST:
            logger.error(
                "❌ STARTUP ERROR: No company configurations found in config/companies/. "
                "Pipeline will only run LinkedIn Easy Apply this cycle."
            )

        logger.info(
            f"Starting async scrape for {len(COMPANIES_LIST)} configured company sources + LinkedIn Easy Apply."
        )

        unique_companies: Dict[str, Dict] = {}
        for c in COMPANIES_LIST:
            if not c.get("enabled", True):
                continue
            name = c.get("name", "")
            if not name:
                continue
            if name not in unique_companies or c.get("priority", False):
                unique_companies[name] = c

        sorted_companies = sorted(
            unique_companies.values(),
            key=lambda c: (not c.get("priority", False), c.get("name", "")),
        )

        all_jobs: List[JobListing] = []
        stats: Dict[str, Any] = {
            "total_sources": len(sorted_companies) + 1,
            "successful_sources": 0,
            "failed_sources": 0,
            "source_results": {},
        }

        # Initialize global semaphore and connection pool
        global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        connector = aiohttp.TCPConnector(ssl=False, limit=MAX_CONCURRENT_REQUESTS)
        timeout = aiohttp.ClientTimeout(total=45, connect=15)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [
                self._process_company(session, global_semaphore, company)
                for company in sorted_companies
            ]

            for coro in asyncio.as_completed(tasks):
                try:
                    name, success, runtime, jobs, error_msg = await coro
                except Exception as e:
                    logger.error(f"Unexpected task error: {e}", exc_info=True)
                    stats["failed_sources"] += 1
                    continue

                if success:
                    stats["successful_sources"] += 1
                else:
                    stats["failed_sources"] += 1

                stats["source_results"][name] = {
                    "jobs_found": len(jobs),
                    "time_seconds": round(runtime, 2),
                    "status": "success" if success else "failed",
                    "error": error_msg,
                }
                all_jobs.extend(jobs)

            # LinkedIn Easy Apply
            li_jobs = await self._scrape_linkedin(session, global_semaphore)
            if li_jobs:
                stats["successful_sources"] += 1
            else:
                stats["failed_sources"] += 1

            stats["source_results"]["LinkedIn Easy Apply"] = {
                "jobs_found": len(li_jobs),
                "time_seconds": 0,
                "status": "success" if li_jobs else "no_results",
                "error": "",
            }
            all_jobs.extend(li_jobs)

        # Update metrics tracker counters
        self.metrics_tracker.total_endpoints = stats["total_sources"]
        self.metrics_tracker.raw_jobs_count = len(all_jobs)

        logger.info(
            f"Scraping complete — {stats['successful_sources']}/{stats['total_sources']} sources OK, "
            f"{len(all_jobs)} total schema-compliant jobs"
        )
        return all_jobs, stats
