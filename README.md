
# LinkedIn Jobs Scraper (Selenium) — Setup & Run Guide

> **Heads‑up:** Automating LinkedIn can violate their Terms of Service and may trigger login challenges or account restrictions. Use on your own account, at your own risk, and respect robots/terms.

## What this project does
A Python script that logs into LinkedIn, searches job listings (configurable keywords/location), scrapes each posting (title, company, location, workplace type, posted date, schedule, description, URL), and writes everything to a single CSV.

---

## Requirements
- **Python** 3.9+ (3.10/3.11 recommended)
- **Google Chrome** installed (Selenium Manager auto‑installs the matching driver)
- A **LinkedIn** account (credentials supplied via environment variables)

---

## 1) Create & activate a virtual environment

### macOS / Linux (Bash/Zsh)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel
```

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
```

---

## 2) Install dependencies

Create a `requirements.txt` with:
```txt
selenium>=4.23
python-dotenv>=1.0
pandas>=2.0
```

Then install:
```bash
pip install -r requirements.txt
```

> If you don't want `.env` support, you can omit `python-dotenv` and set environment variables directly in your shell/CI.

---

## 3) Provide credentials securely

The script expects **environment variables** (preferred) and *optionally* a local `.env` for development.

### Option A — `.env` file (dev convenience)
Create a file named `.env` in your project root:
```dotenv
LINKEDIN_USER=youremail@example.com
LINKEDIN_PASS=super-secret-password
```

### Option B — Set variables in your shell

**macOS/Linux:**
```bash
export LINKEDIN_USER="youremail@example.com"
export LINKEDIN_PASS="super-secret-password"
```

**Windows (PowerShell, current session):**
```powershell
$env:LINKEDIN_USER="youremail@example.com"
$env:LINKEDIN_PASS="super-secret-password"
```

**Windows (PowerShell, persist):**
```powershell
setx LINKEDIN_USER "youremail@example.com"
setx LINKEDIN_PASS "super-secret-password"
# Restart terminal to pick up the new vars
```


---

## 4) Run the scraper

Basic run:
```bash
python selenium-linkedin.py
```

Common options:
```bash
python selenium-linkedin.py   --keywords "junior data analyst"   --location "Spain"   --geoId 105646813   --pages 10   --out job_offers.csv   --headless
```

- `--keywords` — search terms
- `--location` — human‑readable location (city/country)
- `--geoId` — LinkedIn internal geo id (optional but helps targeting)
- `--pages` — how many search result pages to crawl
- `--out` — CSV output path (default: `job_offers.csv`)
- `--headless` — run Chrome without a visible window

Output: a CSV with one row per job, including full **job_description** and **url**.

---

## 5) Recommended `.gitignore`
```gitignore
# Python
.venv/
__pycache__/
*.pyc

# Local env
.env
user_credentials.txt

# OS
.DS_Store
```

---

## Troubleshooting

- **Login/CAPTCHA challenges:** LinkedIn may prompt for extra verification. There’s no reliable automated bypass. Try again later, reduce scraping rate, and keep runs short.
- **No results / selectors fail:** LinkedIn’s HTML can change regionally. Update the CSS selectors/XPaths in the script if needed.
- **Chrome/driver errors:** Ensure Chrome is installed. Selenium Manager should fetch the proper driver automatically; upgrading `selenium` often helps.
- **Empty CSV:** If the run was short or no cards were found, increase `--pages` and ensure you’re logged in (no interstitials blocking content).

---

## Notes on responsible use
- Respect website policies and rate limits.
- Prefer official job feeds/ATS APIs (e.g., Greenhouse/Lever) when possible.
- Keep credentials out of source control and rotate them if exposed.

---

## Quick start (copy/paste)

**macOS/Linux:**
```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip wheel
printf "selenium>=4.23
python-dotenv>=1.0
pandas>=2.0
" > requirements.txt
pip install -r requirements.txt
printf "LINKEDIN_USER=you@example.com
LINKEDIN_PASS=super-secret
" > .env
python selenium-linkedin.py --keywords "junior data analyst" --location "Spain" --pages 5 --headless
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
@"selenium>=4.23
python-dotenv>=1.0
pandas>=2.0
"@ | Out-File -Encoding utf8 requirements.txt
pip install -r requirements.txt
@"LINKEDIN_USER=you@example.com
LINKEDIN_PASS=super-secret
"@ | Out-File -Encoding utf8 .env
python selenium-linkedin.py --keywords "junior data analyst" --location "Spain" --pages 5 --headless
```
