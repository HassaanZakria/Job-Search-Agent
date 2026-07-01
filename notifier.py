import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from loguru import logger

from config import settings


def send_alert(top_jobs: list[dict], new_count: int, total_found: int):
    """Send a formatted job alert email."""
    sender   = settings.email_sender
    password = settings.email_password
    receiver = settings.email_receiver

    # Skip silently if email isn't configured
    if not sender or not password or "xxxx" in password:
        logger.warning("Email not configured — skipping alert. "
                       "Fill in email_sender / email_password in config.py to enable.")
        return

    subject = (
        f"[Job Alert] {new_count} new match{'es' if new_count != 1 else ''} found"
        f" — {datetime.now().strftime('%a %b %d')}"
    )

    lines = [
        f"Job Search Report — {datetime.now().strftime('%A, %B %d %Y at %H:%M')}",
        f"Scraped: {total_found} jobs  |  New this run: {new_count}",
        "",
        "══ TOP MATCHES ═══════════════════════════════════════════",
    ]

    for i, job in enumerate(top_jobs[:5], 1):
        score = job.get("score", "-")
        loc   = "Remote" if job.get("remote_friendly") else job.get("location", "")
        lines += [
            f"",
            f"  #{i}  [{score}/10]  {job['title']}",
            f"  Company  : {job['company']}",
            f"  Location : {loc}",
            f"  Salary   : {job.get('salary', 'Not listed')}",
            f"  Source   : {job.get('source', '')}",
        ]
        if job.get("highlight"):
            lines.append(f"  Highlight: {job['highlight']}")
        if job.get("red_flag"):
            lines.append(f"  ⚠ Warning: {job['red_flag']}")
        lines.append(f"  Link     : {job['url']}")

    lines += [
        "",
        "══════════════════════════════════════════════════════════",
        "Sent by your Job Search Agent. Edit config.py to change preferences.",
    ]

    body = "\n".join(lines)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = receiver
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())

        logger.info("Email alert sent to {}", receiver)

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Email authentication failed. "
            "Make sure you're using a Gmail App Password, not your regular password. "
            "Get one at: https://myaccount.google.com/apppasswords"
        )
    except Exception as e:
        logger.error("Email sending failed: {}", e)
