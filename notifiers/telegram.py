"""
Telegram Bot Notifier implementing the BaseNotifier strategy.
"""

import logging
from typing import List, Dict, Any
from core.models import JobListing
from notifiers.base import BaseNotifier
from notifications.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)


class TelegramNotifier(BaseNotifier):
    """Dispatches formatted HTML job alerts via Telegram Bot API with exponential retries."""

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot = TelegramBot(bot_token=bot_token, chat_id=chat_id)

    def test_connection(self) -> bool:
        """Verify bot credentials and Telegram API availability."""
        return self.bot.test_connection()

    def send_job_alerts(
        self,
        new_jobs: List[JobListing],
        stats: Dict[str, Any],
    ) -> bool:
        """Send formatted job alerts to Telegram chat."""
        return self.bot.send_job_alerts(new_jobs, stats)

