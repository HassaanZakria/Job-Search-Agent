import sys
import asyncio
from datetime import datetime
from pathlib import Path

from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from database import (
    init_db,
    upsert_jobs,
    get_seen_urls,
    get_top_jobs,
    save_cover_letter,
    start_run,
    finish_run,
)
from scrapers import fetch_all_jobs
from ai import rank_jobs, generate_cover_letter
from notifier import send_alert


# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging():
    logger.remove()

    # Pretty coloured output in VS Code terminal
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{message}</cyan>"
        ),
        level="INFO",
        colorize=True,
    )

    # Rotating log file (14 days of history kept)
    logger.add(
        "logs/agent_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="14 days",
        serialize=True,   # JSON format for easy parsing
        level="DEBUG",
        encoding="utf-8",
    )


# ── Agent pipeline ────────────────────────────────────────────────────────────

def run_agent():
    run_id = start_run()

    print()
    print("=" * 60)
    print("  JOB SEARCH AGENT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Run #{run_id}")
    print("=" * 60)

    try:
        # ── Step 1: Scrape all sources in parallel ────────────────
        logger.info("Searching for: {}", settings.job_titles)
        all_jobs = asyncio.run(fetch_all_jobs())
        logger.info("Scraped {} unique jobs across all sources", len(all_jobs))

        # ── Step 2: Filter by location ────────────────────────────
        filtered = [
            j for j in all_jobs
            if settings.location.lower() in j.get("location", "").lower()
            or j.get("location", "").lower() == "remote"
        ]
        logger.info(
            "After location filter ({} / Remote): {} jobs",
            settings.location, len(filtered)
        )

        if not filtered:
            logger.warning("No jobs found after filtering. Try broadening your search.")
            finish_run(run_id, jobs_found=0, new_jobs=0)
            return []

        # ── Step 3: Skip jobs already seen in previous runs ───────
        seen_urls = get_seen_urls()
        new_jobs  = [j for j in filtered if j["url"] not in seen_urls]
        logger.info("{} new jobs not seen before", len(new_jobs))

        # ── Step 4: Rank new jobs with Claude ─────────────────────
        if new_jobs and settings.anthropic_api_key and not settings.anthropic_api_key.startswith("sk-ant-..."):
            logger.info("Ranking {} new jobs with Claude...", len(new_jobs))
            ranked = rank_jobs(new_jobs)
        else:
            ranked = new_jobs
            if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("sk-ant-..."):
                logger.warning(
                    "Anthropic API key not set — skipping AI ranking. "
                    "Add your key to config.py to enable ranking and cover letters."
                )

        # ── Step 5: Save to database ──────────────────────────────
        new_count = upsert_jobs(ranked)
        logger.info("Saved {} new jobs to database", new_count)

        # ── Step 6: Show top results ──────────────────────────────
        top_jobs = get_top_jobs(limit=10)

        print()
        print("─── TOP MATCHES " + "─" * 44)
        for i, job in enumerate(top_jobs, 1):
            score = job.get("score", "?")
            loc   = "Remote" if job.get("remote_friendly") else job.get("location", "")
            print(f"\n  #{i}  [{score}/10]  {job['title']}")
            print(f"       Company : {job['company']}")
            print(f"       Location: {loc}  |  Source: {job['source']}")
            print(f"       Salary  : {job.get('salary', 'Not listed')}")
            if job.get("highlight"):
                print(f"       ✓ {job['highlight']}")
            if job.get("red_flag"):
                print(f"       ⚠ {job['red_flag']}")
            print(f"       URL     : {job['url']}")

        # ── Step 7: Generate cover letter for best new match ──────
        best_new = next(
            (j for j in ranked if j.get("score", 0) >= 7),
            ranked[0] if ranked else None
        )

        if (
            best_new
            and settings.anthropic_api_key
            and not settings.anthropic_api_key.startswith("sk-ant-...")
        ):
            print()
            print("─── COVER LETTER " + "─" * 43)
            print(f"  Generating for: {best_new['title']} @ {best_new['company']}")
            print()

            letter = generate_cover_letter(best_new)
            save_cover_letter(best_new["url"], letter)

            # Save to a timestamped file in cover_letters/
            safe_company = best_new["company"].replace(" ", "_").replace("/", "-")
            fname = Path("cover_letters") / f"{safe_company}_{datetime.now().strftime('%Y%m%d')}.txt"
            fname.write_text(
                f"Job  : {best_new['title']} @ {best_new['company']}\n"
                f"URL  : {best_new['url']}\n"
                f"Date : {datetime.now().strftime('%Y-%m-%d')}\n\n"
                + letter,
                encoding="utf-8",
            )

            print(letter)
            print()
            logger.info("Cover letter saved to {}", fname)

        # ── Step 8: Email alert (only when new jobs found) ────────
        print("─── EMAIL ALERT " + "─" * 44)
        if new_count > 0:
            send_alert(top_jobs, new_count, len(all_jobs))
        else:
            logger.info("No new jobs this run — skipping email alert")

        finish_run(run_id, jobs_found=len(filtered), new_jobs=new_count)

        print()
        print(f"  Done! Found {new_count} new jobs this run.")
        print("=" * 60)
        print()

        return top_jobs

    except Exception as e:
        logger.exception("Agent crashed on run #{}: {}", run_id, e)
        finish_run(run_id, jobs_found=0, new_jobs=0, error=str(e))
        raise


# ── Scheduler ────────────────────────────────────────────────────────────────

def start_scheduler():
    scheduler = BlockingScheduler(timezone="Asia/Karachi")
    trigger   = CronTrigger.from_crontab(settings.schedule_cron)

    scheduler.add_job(
        run_agent,
        trigger=trigger,
        id="job_search",
        name="Job Search Agent",
        misfire_grace_time=300,
        coalesce=True,
    )

    logger.info("Scheduler started — will run on schedule: {}", settings.schedule_cron)
    logger.info("Keep this terminal open. Press Ctrl+C to stop.")

    if settings.run_on_startup:
        logger.info("Running immediately (run_on_startup=True)...")
        run_agent()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Create required folders
    Path("logs").mkdir(exist_ok=True)
    Path("cover_letters").mkdir(exist_ok=True)

    setup_logging()
    init_db()

    if "--once" in sys.argv:
        # python main.py --once
        run_agent()
    else:
        # python main.py
        start_scheduler()
