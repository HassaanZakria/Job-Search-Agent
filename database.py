import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List
from loguru import logger

from config import settings


# ── Table definitions ────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    source          TEXT,
    title           TEXT,
    company         TEXT,
    location        TEXT,
    salary          TEXT,
    description     TEXT,
    score           INTEGER DEFAULT 5,
    remote_friendly INTEGER DEFAULT 0,
    highlight       TEXT,
    red_flag        TEXT,
    first_seen      TEXT,
    last_seen       TEXT
);

CREATE TABLE IF NOT EXISTS cover_letters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_url    TEXT NOT NULL REFERENCES jobs(url),
    content    TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,
    finished_at TEXT,
    jobs_found  INTEGER DEFAULT 0,
    new_jobs    INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'running',
    error       TEXT
);
"""


# ── Connection ───────────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist yet."""
    with get_conn() as conn:
        conn.executescript(DDL)
    logger.info("Database ready at '{}'", settings.db_path)


# ── Jobs ─────────────────────────────────────────────────────────────────────

def upsert_jobs(jobs: list[dict]) -> int:
    """
    Save jobs to DB. New jobs are inserted; existing ones just get
    their last_seen and score updated. Returns count of NEW jobs only.
    """
    now = datetime.utcnow().isoformat()
    new_count = 0

    with get_conn() as conn:
        for job in jobs:
            exists = conn.execute(
                "SELECT id FROM jobs WHERE url = ?", (job["url"],)
            ).fetchone()

            if exists:
                conn.execute(
                    """UPDATE jobs
                       SET last_seen=?, score=?, highlight=?, red_flag=?, remote_friendly=?
                       WHERE url=?""",
                    (
                        now,
                        job.get("score", 5),
                        job.get("highlight", ""),
                        job.get("red_flag", ""),
                        int(job.get("remote_friendly", False)),
                        job["url"],
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO jobs
                       (url, source, title, company, location, salary, description,
                        score, remote_friendly, highlight, red_flag, first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        job["url"],
                        job.get("source", ""),
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        job.get("salary", "Not listed"),
                        job.get("description", ""),
                        job.get("score", 5),
                        int(job.get("remote_friendly", False)),
                        job.get("highlight", ""),
                        job.get("red_flag", ""),
                        now,
                        now,
                    ),
                )
                new_count += 1

    return new_count


def get_seen_urls() -> set:
    """Return all job URLs already in the database."""
    with get_conn() as conn:
        rows = conn.execute("SELECT url FROM jobs").fetchall()
    return {r["url"] for r in rows}


def get_top_jobs(limit: int = 10) -> List[dict]:
    """Fetch top-scored jobs from the database."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY score DESC, first_seen DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Cover letters ────────────────────────────────────────────────────────────

def save_cover_letter(job_url: str, content: str):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO cover_letters (job_url, content, created_at) VALUES (?,?,?)",
            (job_url, content, now),
        )


# ── Run tracking ─────────────────────────────────────────────────────────────

def start_run() -> int:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO runs (started_at, status) VALUES (?, 'running')", (now,)
        )
        return cur.lastrowid


def finish_run(run_id: int, jobs_found: int, new_jobs: int, error: Optional[str] = None):
    now = datetime.utcnow().isoformat()
    status = "error" if error else "success"
    with get_conn() as conn:
        conn.execute(
            """UPDATE runs
               SET finished_at=?, jobs_found=?, new_jobs=?, status=?, error=?
               WHERE id=?""",
            (now, jobs_found, new_jobs, status, error, run_id),
        )
