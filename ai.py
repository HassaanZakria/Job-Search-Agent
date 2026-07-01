import re
import json
import anthropic
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _api_retry():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        reraise=True,
    )


# ── Job ranking ───────────────────────────────────────────────────────────────

@_api_retry()
def rank_jobs(jobs: list[dict]) -> list[dict]:
    """Score each job 1-10 for relevance. Returns jobs sorted best-first."""
    if not jobs:
        return []

    jobs_text = "\n\n".join([
        f"[{i+1}] Source: {j['source']}\n"
        f"Title: {j['title']}\n"
        f"Company: {j['company']}\n"
        f"Location: {j['location']}\n"
        f"Salary: {j['salary']}"
        for i, j in enumerate(jobs)
    ])

    prompt = f"""You are a job search assistant for a Data Scientist, ML/AI, Data Engineer and Python Developer role candidate based in Lahore, Pakistan.

Candidate profile:
- Name: {settings.candidate_name}
- Skills: {settings.candidate_skills}
- Experience: {settings.years_experience} years
- Preferred location: {settings.location} or Remote

Here are the job listings to evaluate:

{jobs_text}

Score each job 1-10 for relevance to this candidate.
Return ONLY a JSON array — no markdown, no extra text, nothing else:
[{{"index": 1, "score": 8, "remote_friendly": true, "highlight": "Strong ML role with PyTorch", "red_flag": ""}}]
"""

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        scores = json.loads(raw)

        for s in scores:
            idx = s["index"] - 1
            if 0 <= idx < len(jobs):
                jobs[idx]["score"]          = s.get("score", 5)
                jobs[idx]["remote_friendly"] = s.get("remote_friendly", False)
                jobs[idx]["highlight"]       = s.get("highlight", "")
                jobs[idx]["red_flag"]        = s.get("red_flag", "")

        logger.info("Claude ranked {} jobs", len(jobs))

    except Exception as e:
        logger.error("Ranking failed: {}. Defaulting all scores to 5.", e)
        for job in jobs:
            job.setdefault("score", 5)
            job.setdefault("remote_friendly", False)
            job.setdefault("highlight", "")
            job.setdefault("red_flag", "")

    return sorted(jobs, key=lambda x: x.get("score", 0), reverse=True)


# ── Cover letter ──────────────────────────────────────────────────────────────

@_api_retry()
def generate_cover_letter(job: dict) -> str:
    """Write a tailored cover letter for the given job."""
    prompt = f"""Write a professional, concise cover letter (max 250 words) for this job:

Job Title : {job['title']}
Company   : {job['company']}
Location  : {job['location']}

Candidate:
- Name      : {settings.candidate_name}
- Skills    : {settings.candidate_skills}
- Experience: {settings.years_experience} years
- Bio       : {settings.candidate_bio}

Guidelines:
- Open with a strong hook — no "I am writing to apply..."
- Highlight 2-3 skills most relevant to this specific role
- Show genuine enthusiasm for the company and role
- End with a clear call to action
- Tone: professional but human, not robotic

Return only the cover letter text. No subject line, no formatting."""

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        letter = response.content[0].text.strip()
        logger.info("Cover letter generated for {} @ {}", job["title"], job["company"])
        return letter
    except Exception as e:
        logger.error("Cover letter generation failed: {}", e)
        return f"[Cover letter generation failed: {e}]"
