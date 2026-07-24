# Job Search Agent 
AI-powered job search agent that scrapes LinkedIn, Indeed, Rozee.pk, RemoteOK, and WeWorkRemotely daily — ranks results using Claude, generates tailored cover letters, and sends email alerts for new matches.

## Setup

### 1. Open folder in VS Code
File → Open Folder → select the `job_agent` folder

### 2. Create a virtual environment
Open the VS Code terminal (Ctrl + `) and run:
```
python -m venv venv
```
Then select the interpreter:
- Press `Ctrl+Shift+P`
- Type: `Python: Select Interpreter`
- Choose: `.\venv\Scripts\python.exe`

### 3. Install packages
```
pip install -r requirements.txt
```

### 4. Edit config.py
Open `config.py` and fill in:
- `anthropic_api_key` — from https://console.anthropic.com
- `email_sender` / `email_password` / `email_receiver` — Gmail + App Password
- `candidate_name`, `candidate_skills`, etc. — your profile

---

## Running

### Option A — F5 (Recommended)
Press **F5** in VS Code, then pick from the dropdown:
- **"Run Once (Test)"** — runs the agent once and shows results in terminal
- **"Run Scheduler (Daily)"** — keeps running, fires automatically on your cron schedule

### Option B — Terminal
```bash
# Single test run
python main.py --once

# Daily scheduled mode (keep terminal open)
python main.py
```

---

## What you'll see in the terminal

```
2026-03-31 09:00:00 | INFO     | Searching for: ['Data Scientist', 'AI Engineer', ...]
2026-03-31 09:00:04 | INFO     | LinkedIn → 8 jobs for 'Data Scientist'
2026-03-31 09:00:04 | INFO     | RemoteOK → 3 jobs for 'Data Scientist'
...
2026-03-31 09:00:12 | INFO     | Total unique jobs scraped: 47
2026-03-31 09:00:12 | INFO     | After location filter: 23 jobs
2026-03-31 09:00:12 | INFO     | 23 new jobs not seen before
2026-03-31 09:00:14 | INFO     | Claude ranked 23 jobs

─── TOP MATCHES ─────────────────────────────────────────────
  #1  [9/10]  AI Engineer
       Company : Cybernef Technologies
       Location: Lahore  |  Source: LinkedIn
       ✓ Strong ML role, uses PyTorch
       URL     : https://linkedin.com/...
  ...

─── COVER LETTER ────────────────────────────────────────────
  Generating for: AI Engineer @ Cybernef Technologies
  ...

─── EMAIL ALERT ─────────────────────────────────────────────
  Email sent to you@gmail.com

  Done! Found 23 new jobs this run.
```

---

## Gmail App Password setup
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification (required)
3. Go to https://myaccount.google.com/apppasswords
4. Create a new App Password → select "Mail"
5. Copy the 16-character password into `config.py`

---

## Changing the schedule
Edit `schedule_cron` in `config.py`:
```python
schedule_cron: str = "0 9 * * *"     # 9 AM daily
schedule_cron: str = "0 9 * * 1-5"   # weekdays only
schedule_cron: str = "0 9,18 * * *"  # 9 AM and 6 PM daily
```
