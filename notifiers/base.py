"""
Abstract Strategy Interface for Job Alert Notifiers.
Enables pluggable alert dispatchers (Telegram, Console, Webhooks, Slack, Email).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from core.models import JobListing


class BaseNotifier(ABC):
    """Abstract base class for all notification providers."""

    @abstractmethod
    async def send_job_alerts(
        self,
        new_jobs: List[JobListing],
        stats: Dict[str, Any],
    ) -> bool:
        """
        Dispatch formatted job alerts.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify network reachability and credentials."""
        pass

