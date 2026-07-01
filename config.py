from dataclasses import dataclass, field
from typing import List

@dataclass
class Settings:

    # ── 1. YOUR PROFILE ────────────────────────────────────────
    #    Used to rank jobs and generate cover letters
    candidate_name: str = "Your Full Name"
    candidate_skills: str = (
        "Python, Machine Learning, Deep Learning, SQL, "
        "TensorFlow, PyTorch, FastAPI, Docker, AWS, Data Analysis"
    )
    years_experience: str = "3"
    candidate_bio: str = (
        "Passionate Data Scientist and Software Engineer with 3 years "
        "of experience building ML pipelines and scalable backend systems."
    )

    # ── 2. JOB SEARCH PREFERENCES ──────────────────────────────
    job_titles: List[str] = field(default_factory=lambda: [
        "Data Scientist",
        "AI Engineer",
        "ML Engineer",
        "Python Developer",
    ])
    location: str = "Lahore"           # City to filter jobs by
    max_results_per_source: int = 10   # How many jobs to fetch per site

    # ── 3. ANTHROPIC API ───────────────────────────────────────
    #    Get your key from: https://console.anthropic.com
    anthropic_api_key: str = "xxxx-xxxx-xxxx-xxxx"  # Your API key
    claude_model: str = "claude-sonnet-4-20250514"

    # ── 4. EMAIL ALERTS ─────────────────────────────────────────
    #    Uses Gmail. Get an App Password:
    #    https://myaccount.google.com/apppasswords
    email_sender: str = "you@gmail.com"           # Your Gmail address
    email_password: str = "xxxx-xxxx-xxxx-xxxx"   # 16-char App Password
    email_receiver: str = "you@gmail.com"          # Where to send alerts

    # ── 5. SCHEDULE ─────────────────────────────────────────────
    #    When to run automatically (cron format, Asia/Karachi timezone)
    #    "0 9 * * *"    = every day at 9:00 AM
    #    "0 9 * * 1-5"  = weekdays only at 9:00 AM
    #    "0 9,18 * * *" = 9 AM and 6 PM daily
    schedule_cron: str = "0 9,13,14,15,16,17,18 * * *"
    run_on_startup: bool = True        # Run immediately when you start the script

    # ── 6. ADVANCED (leave as-is unless needed) ─────────────────
    db_path: str = "jobs.db"           # SQLite database file
    request_timeout: int = 12          # Seconds before a scrape times out
    max_retries: int = 3               # Retry attempts on failed requests
    retry_wait_seconds: int = 2        # Wait between retries
    scraper_delay: float = 1.0         # Delay between sources (be polite)


# Single instance used across all modules
settings = Settings()
