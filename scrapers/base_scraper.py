"""
Async Base Scraper for High-Concurrency Job Ingestion & ETL System.
Provides retry logic, timeout, rate limiting, and HTTP error handling using aiohttp.
"""

import aiohttp
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from core.models import JobListing
from config.settings import (
    DEFAULT_HEADERS, JSON_HEADERS, REQUEST_TIMEOUT, 
    RETRY_ATTEMPTS, RETRY_DELAY
)

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Abstract async base class for all job scrapers."""

    def __init__(self, source_name: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
        self.source_name = source_name
        self.session = session
        self.semaphore = semaphore

    async def _get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None, json_response: bool = False) -> Any:
        """Make an async GET request with retry and error handling."""
        headers = headers or DEFAULT_HEADERS
        
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                async with self.semaphore:
                    async with self.session.get(
                        url,
                        headers=headers,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                    ) as response:
                        if response.status == 200:
                            if json_response:
                                return await response.json()
                            return await response.text()
                            
                        if response.status in (429, 500, 502, 503, 504):
                            logger.warning(f"[{self.source_name}] HTTP {response.status} fetching {url}. Attempt {attempt}/{RETRY_ATTEMPTS}")
                            if attempt < RETRY_ATTEMPTS:
                                await asyncio.sleep(RETRY_DELAY * (2 ** (attempt - 1)))  # Exponential backoff
                                continue
                                
                        if response.status in (403, 404):
                            logger.warning(f"[{self.source_name}] HTTP {response.status} (Permanent) fetching {url}. Skipping.")
                            return None
                            
                        logger.error(f"[{self.source_name}] Unhandled HTTP {response.status} for {url}")
                        return None

            except asyncio.TimeoutError:
                logger.warning(f"[{self.source_name}] Timeout fetching {url}. Attempt {attempt}/{RETRY_ATTEMPTS}")
                if attempt < RETRY_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY)
                    
            except aiohttp.ClientError as e:
                logger.warning(f"[{self.source_name}] ClientError: {e} for {url}")
                if attempt < RETRY_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY)
                    
            except Exception as e:
                logger.error(f"[{self.source_name}] Unexpected error: {e}", exc_info=True)
                return None
                
        logger.error(f"[{self.source_name}] Failed to fetch {url} after {RETRY_ATTEMPTS} attempts.")
        return None

    async def _get_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict | List]:
        return await self._get(url, headers=JSON_HEADERS, params=params, json_response=True)

    @abstractmethod
    async def scrape(self, company_config: Dict[str, Any]) -> List[JobListing]:
        """Scrape and return job listings for a single company configuration."""
        pass

    async def safe_scrape(self, company_config: Dict[str, Any]) -> List[JobListing]:
        """Wrapper to catch all exceptions."""
        try:
            return await self.scrape(company_config)
        except Exception as e:
            logger.error(f"[{self.source_name} - {company_config.get('name')}] Scraper crashed: {e}", exc_info=True)
            return []
