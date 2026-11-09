"""
Telegram Bot Notifier implementing the BaseNotifier strategy.
Dispatches formatted HTML job alerts via the Telegram Bot API with exponential backoff retries.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

import aiohttp

from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_API_URL,
    TELEGRAM_MAX_MESSAGE_LENGTH,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    IST,
)
from core.models import JobListing
from notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class TelegramNotifier(BaseNotifier):
    """
    Production Telegram Bot Notifier.
    Formats and chunks new job alerts using HTML and sends them with retry handling.
    """

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.api_url = TELEGRAM_API_URL.format(token=self.bot_token)

    @property
    def _is_dry_run(self) -> bool:
        """Check dry run mode at runtime so CLI flag takes precedence."""
        return os.environ.get("DRY_RUN", "false").lower() == "true"

    async def test_connection(self) -> bool:
        """Test the Telegram bot credentials and network connection."""
        if self._is_dry_run:
            logger.info("[DRY RUN] Skipping Telegram connection test")
            return True

        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not configured in environment!")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_name = data.get("result", {}).get("username", "Unknown")
                        logger.info(f"Telegram bot connected: @{bot_name}")
                        return True
                    else:
                        resp_text = await response.text()
                        logger.error(f"Telegram bot connection failed: {resp_text}")
                        return False
        except Exception as e:
            logger.error(f"Telegram connection test error: {e}")
            return False

    async def send_job_alerts(
        self,
        new_jobs: List[JobListing],
        stats: Dict[str, Any],
    ) -> bool:
        """
        Send formatted job alert messages to Telegram chat.
        Splits messages that exceed Telegram's 4096 character limit.
        """
        if not new_jobs:
            logger.info("No new jobs to send.")
            return await self._send_no_jobs_message(stats)

        messages = self._format_job_messages(new_jobs, stats)
        all_succeeded = True

        for index, message in enumerate(messages):
            if not await self._send_message(message):
                all_succeeded = False
                logger.error(f"Failed to send message chunk {index + 1}/{len(messages)}")
            else:
                logger.info(f"Sent message chunk {index + 1}/{len(messages)}")
                await asyncio.sleep(1)  # Respect Telegram rate limit of 1 msg/sec

        return all_succeeded

    def _format_job_messages(
        self,
        jobs: List[JobListing],
        stats: Dict[str, Any],
    ) -> List[str]:
        """Format jobs into clean HTML Telegram message chunks."""
        now_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

        header = (
            "🚀 <b>High-Concurrency Job Ingestion Alert</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {now_ist}\n"
            f"📊 New Jobs Since Last Run: <b>{len(jobs)}</b>\n"
            f"🔍 Sources: {stats.get('successful_sources', '?')}/{stats.get('total_sources', '?')} active\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        job_blocks = []
        for index, job in enumerate(jobs, 1):
            prestige_bar = self._get_prestige_bar(job.company_prestige_score)
            source_emoji = self._get_source_emoji(job.source_platform)
            salary_display = self._format_salary(job)
            date_display = self._format_date(job.posting_date)

            easy_badge = " ⚡ <b>Easy Apply</b>" if job.source_platform == "linkedin_easy_apply" else ""
            block = (
                f"<b>{index}. {self._escape_html(job.company_name)}</b>{easy_badge}\n"
                f"   📋 {self._escape_html(job.job_title)}\n"
                f"   📍 {self._escape_html(job.location)}{date_display}\n"
                f"   💰 {salary_display}\n"
                f"   🏅 {prestige_bar} ({job.company_prestige_score}/10)\n"
                f"   {source_emoji} {self._escape_html(job.source_platform)}\n"
                f"   🔗 <a href=\"{job.apply_url}\">Apply Now</a>\n\n"
            )
            job_blocks.append(block)

        # Build summary
        summary = ""
        if jobs:
            top_salary = max((j.estimated_salary_lpa or 0 for j in jobs), default=0)
            top_companies = ", ".join(sorted(set(j.company_name for j in jobs[:5])))

            source_health = []
            for src_name, src_data in stats.get("source_results", {}).items():
                count = src_data.get("jobs_found", 0)
                status = src_data.get("status", "unknown")
                if count > 0:
                    source_health.append(f"✅ {src_name}: {count}")
                elif "success" in status:
                    source_health.append(f"⚪ {src_name}: 0")
                else:
                    source_health.append(f"❌ {src_name}")

            summary = (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📈 <b>Summary</b>\n"
                f"• Total New Jobs: {len(jobs)}\n"
                f"• Highest Est. Salary: ₹{top_salary} LPA\n"
                f"• Top Companies: {self._escape_html(top_companies)}\n\n"
                "🔍 <b>Source Health</b>\n"
                + "\n".join(source_health) + "\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Powered by High-Concurrency ETL Pipeline</i> 🤖"
            )

        # Chunk into messages strictly under Telegram's 4096 character limit
        messages = []
        current_chunk = header

        for block in job_blocks:
            if len(current_chunk) + len(block) > TELEGRAM_MAX_MESSAGE_LENGTH - 500:
                messages.append(current_chunk)
                current_chunk = "🏆 <b>Jobs (continued)</b>\n\n"
            current_chunk += block

        current_chunk += summary

        if len(current_chunk) > TELEGRAM_MAX_MESSAGE_LENGTH:
            messages.append(current_chunk[:TELEGRAM_MAX_MESSAGE_LENGTH - 100])
            remaining = current_chunk[TELEGRAM_MAX_MESSAGE_LENGTH - 100:]
            while remaining:
                messages.append(remaining[:TELEGRAM_MAX_MESSAGE_LENGTH - 100])
                remaining = remaining[TELEGRAM_MAX_MESSAGE_LENGTH - 100:]
        else:
            messages.append(current_chunk)

        return messages

    def _format_date(self, date_str: str) -> str:
        if not date_str:
            return ""
        try:
            d = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return f"\n   📅 Posted: {d.strftime('%d %b %Y')}"
        except Exception:
            return f"\n   📅 Posted: {self._escape_html(str(date_str)[:10])}"

    def _format_salary(self, job: JobListing) -> str:
        if job.salary:
            return self._escape_html(job.salary)
        if job.estimated_salary_lpa:
            confidence = job.salary_confidence or "medium"
            conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🟠"}.get(confidence, "⚪")
            return f"~₹{job.estimated_salary_lpa} LPA {conf_emoji} ({confidence} est.)"
        return "Not disclosed"

    def _get_prestige_bar(self, score: int) -> str:
        filled = min(score, 10)
        return "█" * filled + "░" * (10 - filled)

    async def _send_no_jobs_message(self, stats: Optional[Dict[str, Any]] = None) -> bool:
        now_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
        message = (
            "📭 <b>Job Ingestion Alert — No New Jobs</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {now_ist}\n\n"
            "No new AI/ML fresher opportunities found since the last run.\n"
            "All discovered jobs were already reported in previous alerts.\n\n"
            "The system will check again at the next scheduled cycle.\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Powered by High-Concurrency ETL Pipeline</i> 🤖"
        )
        return await self._send_message(message)

    async def _send_message(self, text: str) -> bool:
        if self._is_dry_run:
            logger.info(f"[DRY RUN] Would send Telegram message ({len(text)} chars)")
            return True

        if not self.bot_token or not self.chat_id:
            logger.error("Telegram bot token or chat ID not configured!")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        for attempt in range(RETRY_ATTEMPTS):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    async with session.post(self.api_url, json=payload) as response:
                        if response.status == 200:
                            return True

                        resp_text = await response.text()
                        # If HTML parsing fails, fallback to plain text
                        if response.status == 400 and "parse" in resp_text.lower():
                            logger.warning("HTML parse failed, attempting plain text fallback")
                            return await self._send_plain_text(text)

                        logger.warning(
                            f"Telegram API response (attempt {attempt + 1}): {response.status} - {resp_text}"
                        )
            except Exception as e:
                logger.warning(f"Telegram network error (attempt {attempt + 1}): {e}")

            await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        logger.error("Failed to send Telegram message after all retries")
        return False

    async def _send_plain_text(self, html_text: str) -> bool:
        import re
        plain_text = re.sub(r"<[^>]+>", "", html_text)
        payload = {
            "chat_id": self.chat_id,
            "text": plain_text,
            "disable_web_page_preview": True,
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(self.api_url, json=payload) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Telegram plain text fallback failed: {e}")
            return False

    @staticmethod
    def _escape_html(text: str) -> str:
        if not text:
            return ""
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _get_source_emoji(source: str) -> str:
        emojis = {
            "greenhouse": "🌱",
            "lever": "🔧",
            "linkedin": "💼",
            "linkedin_easy_apply": "⚡",
            "naukri": "🇮🇳",
            "wellfound": "🚀",
            "foundit": "🔍",
            "google_jobs": "🔎",
            "careers_page": "🏢",
            "custom_career": "🏢",
            "cutshort": "✂️",
            "instahyre": "📱",
            "ashby": "🎯",
            "workday": "🏦",
            "smartrecruiters": "🔵",
        }
        return emojis.get(source, "📌")


# Backwards compatibility alias
TelegramBot = TelegramNotifier
