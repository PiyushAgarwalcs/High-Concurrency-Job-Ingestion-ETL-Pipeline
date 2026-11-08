"""
AI/ML Fresher Job Discovery & Automation Pipeline V3
Fuses RequestGuard (Upstream Isolation & Safety Gate) and StateLedger (State Fingerprinting & Telemetry).

100% Deterministic, Zero Cost, No LLMs.
"""

import asyncio
import argparse
import logging
import logging.config
import os
import signal
import sys
from datetime import datetime, timezone

from config.settings import (
    DB_PATH,
    TOP_N_JOBS,
    DRY_RUN,
    IST,
    LOGGING_CONFIG,
    LOGS_DIR,
    NOTIFY_ON_EMPTY,
    CIRCUIT_BREAKER_FAILURES,
    CIRCUIT_BREAKER_COOLDOWN,
    RETENTION_DAYS,
)
from database.db_manager import DBManager
from scrapers.scraper_manager import ScraperManager
from core.request_guard import CircuitBreaker
from core.state_ledger import StateLedger
from core.metrics import MetricsTracker
from core.filter_engine import FilterEngine
from core.dedup_engine import DedupEngine
from core.ranking_engine import RankingEngine
from notifiers import BaseNotifier, TelegramNotifier, ConsoleNotifier
from reports.report_generator import ReportGenerator


def setup_logging():
    """Setup structured UTF-8 logging with rotating file handler."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_file = os.path.join(LOGS_DIR, "job_alert.log")

    log_format = LOGGING_CONFIG.get(
        "format", "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    )
    date_format = LOGGING_CONFIG.get("date_format", "%Y-%m-%d %H:%M:%S")
    level = getattr(logging, LOGGING_CONFIG.get("level", "INFO"))

    import io
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    handlers = [logging.StreamHandler(utf8_stdout)]

    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LOGGING_CONFIG.get("max_bytes", 10485760),
            backupCount=LOGGING_CONFIG.get("backup_count", 5),
            encoding="utf-8"
        )
        handlers.append(file_handler)
    except Exception as e:
        print(f"Failed to setup file handler: {e}")

    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V3 Job Discovery Pipeline (RequestGuard & StateLedger)")
    parser.add_argument("--dry-run", action="store_true", help="Run without mutating DB or sending Telegram pings")
    parser.add_argument("--skip-notify", action="store_true", help="Skip dispatching alerts")
    parser.add_argument("--console-notify", action="store_true", help="Force console output for notifications")
    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> int:
    setup_logging()
    logger = logging.getLogger("main")

    is_dry_run = DRY_RUN or args.dry_run
    now_ist = datetime.now(IST)
    workflow_start = datetime.now(timezone.utc).isoformat()

    # ── Initialize Telemetry Harness ─────────────────────────────────────────
    metrics = MetricsTracker()
    metrics.start()

    logger.info("═" * 68)
    logger.info("🚀 AI/ML Fresher Job Discovery Pipeline V3")
    logger.info("   Architecture: RequestGuard Safety Gate & StateLedger Telemetry")
    logger.info(f"   Execution Timestamp : {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
    logger.info(f"   Dry Run Mode        : {is_dry_run}")
    logger.info("═" * 68)

    db_manager: Optional[DBManager] = None
    try:
        # ── Step 1: Initialize Database & StateLedger Deduplication Ledger ────
        logger.info("\n📂 Step 1: Initializing SQLite Database & StateLedger...")
        db_manager = DBManager(DB_PATH)
        await db_manager.init_db()

        state_ledger = StateLedger(DB_PATH)
        known_job_ids = await db_manager.get_all_job_ids()
        logger.info(f"   Historical known listings: {len(known_job_ids)}")

        # Prune old state to keep dedup queries fast and DB lean
        pruned_jobs = await db_manager.prune_old_jobs(days=RETENTION_DAYS)
        pruned_fps = state_ledger.prune_old_fingerprints(days=RETENTION_DAYS)
        if pruned_jobs or pruned_fps:
            logger.info(f"   Pruned {pruned_jobs} jobs and {pruned_fps} historical state fingerprints (older than {RETENTION_DAYS} days).")
            known_job_ids = await db_manager.get_all_job_ids()

        # ── Step 2: Initialize RequestGuard Circuit Breaker & Scrape ─────────
        logger.info("\n🔍 Step 2: Async Ingestion via RequestGuard Gateway...")
        circuit_breaker = CircuitBreaker(
            failure_threshold=CIRCUIT_BREAKER_FAILURES,
            cooldown_seconds=CIRCUIT_BREAKER_COOLDOWN
        )
        scraper_manager = ScraperManager(
            db_manager,
            circuit_breaker=circuit_breaker,
            metrics_tracker=metrics
        )

        raw_jobs, scrape_stats = await scraper_manager.scrape_all()
        logger.info(f"   Schema-compliant jobs ingested: {len(raw_jobs)}")

        if not raw_jobs:
            logger.warning("⚠ No jobs collected from any source this cycle!")
            metrics.stop()
            db_size_mb = state_ledger.get_db_size_mb()
            metrics.print_summary_report(db_size_mb)
            metrics.write_github_step_summary(db_size_mb)

            await db_manager.record_workflow_run({
                "started_at": workflow_start,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "runtime": metrics.get_duration(),
                "jobs_found": 0,
                "duplicates": 0,
                "notifications_sent": 0,
                "companies_checked": scrape_stats.get("total_sources", 0),
                "companies_failed": scrape_stats.get("failed_sources", 0),
            })
            return 0

        # ── Step 3: Algorithmic Filtering (Keywords & Fresher Criteria) ───────
        logger.info("\n🔧 Step 3: Applying Algorithmic Filters...")
        filter_engine = FilterEngine()
        filtered_jobs = filter_engine.filter_jobs(raw_jobs)
        logger.info(f"   Passed filtering: {len(filtered_jobs)} / {len(raw_jobs)} listings")

        # ── Step 4: StateLedger Deterministic Deduplication ───────────────────
        logger.info("\n🔄 Step 4: StateLedger Batch Deduplication & Registration...")
        candidate_dicts = [job.to_dict() for job in filtered_jobs]
        new_job_dicts, duplicate_count = state_ledger.batch_check_and_register(candidate_dicts)
        new_jobs = [JobListing.from_dict(d) for d in new_job_dicts]
        unique_jobs = filtered_jobs

        metrics.duplicates_filtered = len(raw_jobs) - len(new_jobs)
        metrics.new_jobs_identified = len(new_jobs)
        logger.info(f"   Brand new unique listings identified: {len(new_jobs)} (duplicates filtered: {duplicate_count})")

        # ── Step 6: Rank & Score Listings ────────────────────────────────────
        logger.info("\n📊 Step 6: Ranking and Scoring Listings...")
        ranking_engine = RankingEngine()
        ranked_new = ranking_engine.rank_jobs(new_jobs) if new_jobs else []
        top_jobs = ranked_new[:TOP_N_JOBS]
        logger.info(f"   Selected top {len(top_jobs)} jobs for notification dispatch")

        # ── Step 7: Strategy-Pattern Notification Dispatch ───────────────────
        logger.info("\n📱 Step 7: Dispatching Notifications via Strategy Pattern...")
        notifications_sent = 0

        # Select notification strategy
        notifier: BaseNotifier
        if args.console_notify or is_dry_run:
            logger.info("   Strategy Selected: ConsoleNotifier (Dry Run / Local Output)")
            notifier = ConsoleNotifier()
            if not top_jobs and not NOTIFY_ON_EMPTY:
                logger.info("   No new jobs and NOTIFY_ON_EMPTY=false — skipping console alert")
            else:
                if await notifier.send_job_alerts(top_jobs, scrape_stats):
                    notifications_sent = len(top_jobs)
        elif not args.skip_notify:
            logger.info("   Strategy Selected: TelegramNotifier (Production Webhook)")
            notifier = TelegramNotifier()
            if await notifier.test_connection():
                if not top_jobs and not NOTIFY_ON_EMPTY:
                    logger.info("   No new jobs and NOTIFY_ON_EMPTY=false — skipping Telegram ping")
                elif await notifier.send_job_alerts(top_jobs, scrape_stats):
                    notifications_sent = len(top_jobs)
            else:
                logger.warning("   Telegram connection test failed. Notifications skipped.")
        else:
            logger.info("   Notifications skipped via --skip-notify flag.")

        metrics.notifications_dispatched = notifications_sent

        # ── Step 8: Reports Generation ───────────────────────────────────────
        logger.info("\n📄 Step 8: Generating Markdown & CSV Reports...")
        report_gen = ReportGenerator(db_manager)
        await report_gen.generate_all()

        # ── Step 9: State Persistence into SQLite ────────────────────────────
        logger.info("\n💾 Step 9: Persisting State to SQLite...")
        if not is_dry_run:
            await db_manager.save_jobs(unique_jobs)
            for job in top_jobs:
                if not args.skip_notify:
                    await db_manager.mark_notification_sent(job.job_id)

        # ── Step 10: Telemetry Metrics Summary Report ────────────────────────
        metrics.stop()
        db_size_mb = state_ledger.get_db_size_mb()

        # Print to stdout and append to GitHub Actions Summary
        metrics.print_summary_report(db_size_mb)
        metrics.write_github_step_summary(db_size_mb)

        # Record run history in database
        await db_manager.record_workflow_run({
            "started_at": workflow_start,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "runtime": metrics.get_duration(),
            "jobs_found": len(raw_jobs),
            "duplicates": metrics.duplicates_filtered,
            "notifications_sent": notifications_sent,
            "companies_checked": scrape_stats.get("total_sources", 0),
            "companies_failed": scrape_stats.get("failed_sources", 0),
        })

        logger.info("✅ V3 Pipeline Execution Succeeded!")
        return 0

    except asyncio.CancelledError:
        logger.warning("⚠️ V3 Pipeline task was cancelled.")
        return 1
    except Exception as e:
        logger.error(f"❌ V3 Pipeline failed: {e}", exc_info=True)
        if not args.skip_notify and not is_dry_run:
            try:
                alert_notifier = TelegramNotifier()
                crash_msg = (
                    "⚠️ <b>AI/ML Job Alert Pipeline Failure</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🕐 {datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')}\n"
                    f"❌ <b>Error:</b> <code>{TelegramNotifier._escape_html(str(e)[:300])}</code>\n\n"
                    "Please check GitHub Actions workflow logs for details."
                )
                await alert_notifier._send_message(crash_msg)
            except Exception as alert_err:
                logger.warning(f"Could not dispatch crash alert to Telegram: {alert_err}")
        return 1
    finally:
        if db_manager is not None:
            await db_manager.close()


def main():
    args = parse_args()

    # Register graceful shutdown signals for containers & runner hosts
    def _sig_handler(signum, frame):
        logger.warning(f"⚠️ Termination signal ({signum}) received. Shutting down...")
        sys.exit(128 + signum)

    try:
        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)
    except (ValueError, AttributeError):
        pass

    try:
        # Wrap in a 20-minute safety timeout (GitHub Actions 25m runner limit)
        return asyncio.run(asyncio.wait_for(async_main(args), timeout=1200.0))
    except (asyncio.TimeoutError, TimeoutError):
        logger.error("🛑 Pipeline exceeded global 20-minute safety timeout. Aborted gracefully.")
        return 1
    except KeyboardInterrupt:
        logger.warning("🛑 Pipeline interrupted by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
