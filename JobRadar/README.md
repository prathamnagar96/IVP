# JobRadar API

Remote software engineering jobs at YC- and VC-backed startups, sourced from ATS public APIs.

## Overview

JobRadar API provides a clean, tagged, and fresh feed of remote SWE job postings from funded startups. Unlike generalist job aggregators, JobRadar focuses on:

- **Primary sourcing from ATS APIs** (Greenhouse, Lever, Ashby) - not fragile HTML scraping
- **Tech stack tagging** - keyword-based extraction from titles and descriptions
- **Salary parsing** - structured compensation data where available (Ashby, Lever)
- **Deduplication** - SHA-256 fingerprint hashing across sources
- **Low maintenance** - designed to run with <30 min/week attention

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Greenhouse │     │    Lever     │     │   Ashby     │
│    API      │     │    API       │     │   API       │
└──────┬──────┘     └──────┬───────┘     └──────┬──────┘
       │                   │                    │
       └───────────────────┼────────────────────┘
                           ▼
              ┌────────────────────────┐
              │   GitHub Actions       │
              │   (every 6 hours)      │
              └───────────┬────────────┘
                          ▼
              ┌────────────────────────┐
              │   Pipeline             │
              │  Normalize → Enrich →  │
              │  Dedup → Expire        │
              └───────────┬────────────┘
                          ▼
              ┌────────────────────────┐
              │   Supabase (PostgreSQL)│
              └───────────┬────────────┘
                          ▼
              ┌────────────────────────┐
              │   FastAPI (Render/     │
              │   Railway paid tier)   │
              └───────────┬────────────┘
                          ▼
              ┌────────────────────────┐
              │   RapidAPI Gateway     │
              └────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Supabase account (free tier)
- RapidAPI account (for distribution)
- GitHub repository (for Actions)

### Installation

```bash
# Clone and enter directory
cd jobradar-api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install --with-deps chromium
```

### Configuration

1. Copy `.env.example` to `.env` and fill in your values:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. Set up Supabase:
   - Create a new Supabase project
   - Run the migration in `jobradar/db/migrations/0001_initial.sql` via Supabase SQL editor
   - Get your project URL and service role key from Settings → API

3. Configure sources in `sources.yaml`:
   - Add companies with their ATS type and board token
   - See `sources.yaml` for examples

4. Set up GitHub Actions secrets:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `ALERT_WEBHOOK_URL` (optional, for Discord/Slack alerts)
   - `RAPIDAPI_PROXY_SECRET`
   - `API_KEYS`

### Running Locally

```bash
# Run ATS sync once
python -m jobradar.cli sync-ats

# Run scraper sync once
python -m jobradar.cli sync-scrape

# Run both
python -m jobradar.cli sync-full

# Start API server
uvicorn jobradar.api.main:app --reload
```

### API Usage

```bash
# List jobs (requires auth)
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/jobs

# Filter by tag
curl -H "X-API-Key: your-api-key" "http://localhost:8000/api/v1/jobs?tag=python"

# Filter by company
curl -H "X-API-Key: your-api-key" "http://localhost:8000/api/v1/jobs?company=stripe"

# Filter by minimum salary
curl -H "X-API-Key: your-api-key" "http://localhost:8000/api/v1/jobs?min_salary=150000"

# Pagination
curl -H "X-API-Key: your-api-key" "http://localhost:8000/api/v1/jobs?limit=20&page=2"

# Health check (no auth required)
curl http://localhost:8000/health
```

### Response Format

```json
{
  "status": "success",
  "page": 1,
  "limit": 50,
  "total_records": 1420,
  "data": [
    {
      "id": "e8a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
      "title": "Backend Software Engineer (FastAPI)",
      "company": "DataPulse",
      "company_url": "https://datapulse.io",
      "location": "Remote (Worldwide)",
      "tags": ["python", "fastapi", "postgresql", "docker"],
      "salary": { "min": 120000, "max": 150000, "currency": "USD" },
      "apply_url": "https://datapulse.io/careers/backend-dev",
      "source": "ats:greenhouse",
      "posted_at": "2026-07-31T10:30:00Z"
    }
  ]
}
```

### Rate Limit Headers

All API responses include:
- `X-RateLimit-Limit`: Request limit per window
- `X-RateLimit-Remaining`: Remaining requests in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Deployment

### API Hosting (Render/Railway)

1. Create a new Web Service on Render or Railway
2. Connect your GitHub repository
3. Build command: `pip install -e .`
4. Start command: `uvicorn jobradar.api.main:app --host 0.0.0.0 --port $PORT`
5. **Important**: Use a **paid tier** (Render Starter ~$7/mo or Railway Hobby ~$5/mo)
   - Free tiers spin down after inactivity, causing 30-60s cold starts
   - This fails the <150ms latency target

### Environment Variables

Set all variables from `.env.example` in your hosting provider's dashboard.

### RapidAPI Integration

1. Create a new API on RapidAPI Provider Dashboard
2. Set base URL to your deployed API (e.g., `https://jobradar-api.onrender.com`)
3. Add authentication: Header `X-RapidAPI-Proxy-Secret` with your secret
4. Configure pricing tiers per PRD.md §14
5. Subscribe to your own API to test

### VPS for Scraper (Optional)

For fallback HTML scraping, set up a $5/mo VPS:

```bash
# On VPS
git clone your-repo
cd jobradar-api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install --with-deps chromium

# Add to crontab (runs daily at 2 AM)
crontab -e
# 0 2 * * * /path/to/scripts/run_scraper.sh
```

### Git Setup

To create or update a git repository for this project on Windows, run:

```powershell
.\scripts\publish_to_git.ps1 -RemoteUrl https://github.com/<you>/jobradar-api.git
```

The script initializes git if needed, adds `origin`, commits the current tree, and pushes to `main`.

## Project Structure

```
jobradar-api/
├── sources.yaml                 # Company → ATS mappings
├── pyproject.toml               # Python project config
├── .env.example                 # Environment template
├── .github/workflows/
│   └── sync-ats.yml             # GitHub Actions (every 6h)
├── jobradar/
│   ├── config.py                # Settings & source loading
│   ├── cli.py                   # CLI entry points
│   ├── connectors/
│   │   ├── base.py              # Connector interface
│   │   ├── greenhouse.py        # Greenhouse API client
│   │   ├── lever.py             # Lever API client
│   │   ├── ashby.py             # Ashby API client
│   │   └── scraper.py           # Fallback HTML scraper
│   ├── pipeline/
│   │   ├── normalize.py         # Dedup hashing
│   │   ├── enrich.py            # Tags + salary parsing
│   │   ├── lifecycle.py         # Expiry sweep
│   │   └── run.py               # Orchestration
│   ├── db/
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── client.py            # Async DB client
│   │   └── migrations/          # SQL migrations
│   ├── api/
│   │   ├── main.py              # FastAPI app
│   │   ├── deps.py              # Auth, rate limiting
│   │   └── routes/
│   │       ├── health.py        # /health endpoint
│   │       └── jobs.py          # /api/v1/jobs endpoints
│   ├── alerts/
│   │   └── webhook.py           # Run summary alerts
│   └── source_health.py         # Failure tracking
├── scripts/
│   └── run_scraper.sh           # VPS cron entrypoint
└── tests/
    ├── test_normalize.py
    ├── test_enrich.py
    ├── test_connectors.py
    └── test_api_filters.py
```

## Adding New Sources

1. Check if the company uses Greenhouse, Lever, or Ashby
2. Find their board token (usually in the careers page URL)
3. Add to `sources.yaml`:
   ```yaml
   - company: "New Startup"
     ats: "greenhouse"  # or lever, ashby
     token: "newstartup"
     enabled: true
     tags: ["ai", "saas"]
   ```
4. Commit and push - GitHub Actions will pick it up on next run

## Monitoring

- **Run summaries**: Posted to Discord/Slack via webhook after every sync
- **Health endpoint**: `/health` for uptime monitoring (UptimeRobot, etc.)
- **Source health**: Sources auto-disabled after 3 consecutive failures
- **Logs**: GitHub Actions logs for ATS sync; VPS logs for scraper

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=jobradar --cov-report=html

# Run specific test file
pytest tests/test_normalize.py -v
```

## License

MIT License - see LICENSE file for details.