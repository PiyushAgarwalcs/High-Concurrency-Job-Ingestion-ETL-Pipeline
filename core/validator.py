"""
Company Validator for High-Concurrency Job Ingestion & ETL System.
Validates career page URLs and automatically detects ATS providers.
"""

import asyncio
import logging
import aiohttp
from typing import Dict, Any, Tuple
from bs4 import BeautifulSoup
import re

from config.settings import VALIDATION_TIMEOUT

logger = logging.getLogger(__name__)

# ATS URL signature mappings for auto-detection
ATS_SIGNATURES = {
    "greenhouse": [r"boards\.greenhouse\.io", r"greenhouse\.io/embed/job_board"],
    "lever": [r"jobs\.lever\.co", r"jobs\.lever\.co/embed"],
    "ashby": [r"jobs\.ashbyhq\.com"],
    "workday": [r"myworkdayjobs\.com"],
    "workable": [r"apply\.workable\.com"],
    "smartrecruiters": [r"careers\.smartrecruiters\.com", r"jobs\.smartrecruiters\.com"],
    "teamtailor": [r"careers\.teamtailor\.com", r"jobs\.teamtailor\.com"],
    "jobvite": [r"jobs\.jobvite\.com"],
    "bamboohr": [r"bamboohr\.com/jobs"],
    "recruitee": [r"recruitee\.com"],
    "personio": [r"jobs\.personio\.de", r"personio\.com"],
    "comeet": [r"comeet\.com/jobs", r"comeet\.co"],
    "icims": [r"icims\.com/jobs"],
    "oracle": [r"oraclecloud\.com"],
    "sap": [r"successfactors\.com", r"successfactors\.eu"]
}

# Domains known to use Cloudflare/bot-protection that always return 403.
# These are skipped at validation to avoid wasting time on unscrapable pages.
# The ATS-specific scraper will still attempt to fetch the structured API endpoint.
_KNOWN_PROTECTED_DOMAINS = {
    "cloudflare", "just a moment",  # Cloudflare challenge page markers
}


class CompanyValidator:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        
    async def validate_and_detect(self, company: Dict[str, Any]) -> Tuple[bool, str, str, str]:
        """
        Validates the official career page and attempts to auto-detect ATS or RSS feed.
        Uses a short timeout to avoid blocking the pipeline on slow/dead career pages.
        Returns: (is_reachable, detected_ats, feed_url, error_message)
        """
        career_url = company.get("career_url")
        if not career_url:
            return False, company.get("ats", "unknown"), "", "No career_url provided"

        configured_ats = company.get("ats") or "unknown"
        
        # Fast-path: If the career_url itself is an ATS URL, we can skip the
        # expensive GET validation — the ATS scraper will handle it directly.
        url_ats = self._detect_ats_from_url(career_url)
        if url_ats:
            return True, url_ats, "", ""

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1"
            }
            async with self.session.get(
                career_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=VALIDATION_TIMEOUT),
                allow_redirects=True,
            ) as response:
                if response.status in (404, 403, 500, 502, 503, 504):
                    # Read only a small snippet for diagnostics — don't download the full body
                    body_snippet = ""
                    try:
                        body_bytes = await response.content.read(512)
                        body_snippet = body_bytes.decode("utf-8", errors="replace")[:200]
                    except Exception:
                        pass
                    logger.warning(
                        f"[{company.get('name','?')}] HTTP {response.status} from {career_url} | snippet: {body_snippet!r}"
                    )
                    return False, configured_ats, "", f"HTTP {response.status}"

                # Read only the first 32KB of HTML — enough for ATS detection and feed links,
                # avoids downloading megabytes of JavaScript-heavy career pages.
                html_bytes = await response.content.read(32768)
                html = html_bytes.decode("utf-8", errors="replace")

                # 1. Check for RSS/Atom feeds first
                feed_url = self._detect_rss_feed(html, career_url)

                # 2. Auto-detect ATS from HTML or final URL
                detected_ats = self._detect_ats(html, str(response.url), configured_ats)
                if not detected_ats:
                    detected_ats = configured_ats

                return True, detected_ats, feed_url, ""
                
        except asyncio.TimeoutError:
            return False, configured_ats, "", "Timeout"
        except Exception as e:
            err_msg = str(e) if str(e) else e.__class__.__name__
            return False, configured_ats, "", err_msg

    def _detect_ats_from_url(self, url: str) -> str:
        """Fast ATS detection purely from URL patterns — no HTTP request needed."""
        if not url:
            return ""
        url_lower = url.lower()
        for ats_name, signatures in ATS_SIGNATURES.items():
            for sig in signatures:
                if re.search(sig, url_lower, re.IGNORECASE):
                    return ats_name
        return ""
            
    def _detect_rss_feed(self, html: str, base_url: str) -> str:
        """Parse HTML for RSS or Atom feed links."""
        try:
            soup = BeautifulSoup(html, 'lxml')
            link = soup.find('link', type=re.compile(r'application/(rss|atom)\+xml'))
            if link and link.get('href'):
                href = link['href']
                if href.startswith('/'):
                    # Basic relative URL resolution
                    if base_url.endswith('/'):
                        base_url = base_url[:-1]
                    return f"{base_url}{href}"
                return href
        except Exception:
            pass
        return ""
        
    def _detect_ats(self, html: str, final_url: str, configured_ats: str) -> str:
        """
        Detect ATS from URL or HTML source.
        FIX #4: Always returns a non-None, non-empty string.
        """
        text_to_search = final_url + " " + html

        for ats_name, signatures in ATS_SIGNATURES.items():
            for sig in signatures:
                if re.search(sig, text_to_search, re.IGNORECASE):
                    return ats_name

        # Fall back to the config value; guard against None
        return configured_ats or "unknown"
