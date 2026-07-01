import asyncio
import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from loguru import logger

from config import settings


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Retry helper ─────────────────────────────────────────────────────────────

def with_retry():
    return retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_wait_seconds, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=True,
    )


# ── LinkedIn ─────────────────────────────────────────────────────────────────

@with_retry()
async def scrape_linkedin(client: httpx.AsyncClient, query: str, location: str) -> list[dict]:
    jobs = []
    try:
        resp = await client.get(
            "https://www.linkedin.com/jobs/search/",
            params={"keywords": query, "location": location, "f_TPR": "r86400"},
            timeout=settings.request_timeout,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("div.base-card")[: settings.max_results_per_source]:
            title   = card.select_one("h3.base-search-card__title")
            company = card.select_one("h4.base-search-card__subtitle")
            loc     = card.select_one("span.job-search-card__location")
            link    = card.select_one("a.base-card__full-link")
            jobs.append({
                "source":      "LinkedIn",
                "title":       title.get_text(strip=True) if title else query,
                "company":     company.get_text(strip=True) if company else "N/A",
                "location":    loc.get_text(strip=True) if loc else location,
                "salary":      "Not listed",
                "url":         link["href"] if link else "https://linkedin.com/jobs",
                "description": "",
            })
        logger.info("LinkedIn → {} jobs for '{}'", len(jobs), query)
    except Exception as e:
        logger.warning("LinkedIn failed for '{}': {}", query, e)
    return jobs


# ── Indeed ───────────────────────────────────────────────────────────────────

@with_retry()
async def scrape_indeed(client: httpx.AsyncClient, query: str, location: str) -> list[dict]:
    jobs = []
    try:
        resp = await client.get(
            "https://www.indeed.com/jobs",
            params={"q": query, "l": location, "limit": settings.max_results_per_source},
            timeout=settings.request_timeout,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("div.job_seen_beacon")[: settings.max_results_per_source]:
            title   = card.select_one("h2.jobTitle span")
            company = card.select_one("span[data-testid='company-name']")
            loc     = card.select_one("div[data-testid='text-location']")
            salary  = card.select_one("div[data-testid='attribute_snippet_testid']")
            link_el = card.select_one("h2.jobTitle a")
            href    = link_el["href"] if link_el else ""
            jobs.append({
                "source":      "Indeed",
                "title":       title.get_text(strip=True) if title else query,
                "company":     company.get_text(strip=True) if company else "N/A",
                "location":    loc.get_text(strip=True) if loc else location,
                "salary":      salary.get_text(strip=True) if salary else "Not listed",
                "url":         ("https://www.indeed.com" + href) if href else "https://indeed.com",
                "description": "",
            })
        logger.info("Indeed → {} jobs for '{}'", len(jobs), query)
    except Exception as e:
        logger.warning("Indeed failed for '{}': {}", query, e)
    return jobs


# ── Rozee.pk ─────────────────────────────────────────────────────────────────

@with_retry()
async def scrape_rozee(client: httpx.AsyncClient, query: str) -> list[dict]:
    jobs = []
    try:
        resp = await client.get(
            f"https://www.rozee.pk/job/jsearch/q/{query.replace(' ', '+')}",
            timeout=settings.request_timeout,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("div.job-listing")[: settings.max_results_per_source]:
            title   = card.select_one("h3.title a")
            company = card.select_one("span.comp-name")
            loc     = card.select_one("span.loc")
            salary  = card.select_one("span.salary")
            jobs.append({
                "source":      "Rozee.pk",
                "title":       title.get_text(strip=True) if title else query,
                "company":     company.get_text(strip=True) if company else "N/A",
                "location":    loc.get_text(strip=True) if loc else "Pakistan",
                "salary":      salary.get_text(strip=True) if salary else "Not listed",
                "url":         ("https://www.rozee.pk" + title["href"]) if title else "https://rozee.pk",
                "description": "",
            })
        logger.info("Rozee.pk → {} jobs for '{}'", len(jobs), query)
    except Exception as e:
        logger.warning("Rozee.pk failed for '{}': {}", query, e)
    return jobs


# ── RemoteOK ─────────────────────────────────────────────────────────────────

@with_retry()
async def scrape_remoteok(client: httpx.AsyncClient, query: str) -> list[dict]:
    jobs = []
    try:
        resp = await client.get(
            "https://remoteok.com/api",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=settings.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        keywords = query.lower().split()
        count = 0
        for job in data[1:]:  # first item is metadata
            if count >= settings.max_results_per_source:
                break
            # tags can be a list or string — handle both
            tags = job.get("tags", [])
            tags_str = " ".join(tags) if isinstance(tags, list) else str(tags or "")
            text = (job.get("position", "") + " " + tags_str).lower()
            if any(k in text for k in keywords):
                jobs.append({
                    "source":      "RemoteOK",
                    "title":       job.get("position", query),
                    "company":     job.get("company", "N/A"),
                    "location":    "Remote",
                    "salary":      str(job.get("salary") or "Not listed"),
                    "url":         job.get("url", "https://remoteok.com"),
                    "description": (job.get("description") or "")[:300],
                })
                count += 1
        logger.info("RemoteOK → {} jobs for '{}'", len(jobs), query)
    except Exception as e:
        logger.warning("RemoteOK failed for '{}': {}", query, e)
    return jobs


# ── WeWorkRemotely ───────────────────────────────────────────────────────────

@with_retry()
async def scrape_weworkremotely(client: httpx.AsyncClient, query: str) -> list[dict]:
    jobs = []
    try:
        resp = await client.get(
            "https://weworkremotely.com/remote-jobs/search",
            params={"term": query},
            timeout=settings.request_timeout,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("ul.jobs li")[: settings.max_results_per_source]:
            title   = card.select_one("span.title")
            company = card.select_one("span.company")
            link    = card.select_one("a")
            if not title:
                continue
            jobs.append({
                "source":      "WeWorkRemotely",
                "title":       title.get_text(strip=True),
                "company":     company.get_text(strip=True) if company else "N/A",
                "location":    "Remote",
                "salary":      "Not listed",
                "url":         ("https://weworkremotely.com" + link["href"]) if link else "https://weworkremotely.com",
                "description": "",
            })
        logger.info("WeWorkRemotely → {} jobs for '{}'", len(jobs), query)
    except Exception as e:
        logger.warning("WeWorkRemotely failed for '{}': {}", query, e)
    return jobs


# ── Main async entry ─────────────────────────────────────────────────────────

async def fetch_all_jobs() -> list[dict]:
    """Run all scrapers concurrently for every job title. Returns deduplicated list."""
    all_jobs: list[dict] = []

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        tasks = []
        for title in settings.job_titles:
            tasks.append(scrape_linkedin(client, title, settings.location))
            tasks.append(scrape_indeed(client, title, settings.location))
            tasks.append(scrape_rozee(client, title))
            tasks.append(scrape_remoteok(client, title))
            tasks.append(scrape_weworkremotely(client, title))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
            else:
                logger.error("A scraper task crashed: {}", result)

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[dict] = []
    for job in all_jobs:
        if job["url"] not in seen:
            seen.add(job["url"])
            unique.append(job)

    logger.info("Total unique jobs scraped: {}", len(unique))
    return unique
