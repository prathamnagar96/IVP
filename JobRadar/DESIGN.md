# JobRadar API — Technical Design Document

**Companion to:** PRD.md, ARCHITECTURE.md, RULES.md
**Last Updated:** August 2, 2026
**Scope:** This is the implementation-level document — not what to build (PRD) or how the system is shaped (ARCHITECTURE), but exactly how each piece is built: module structure, algorithms, contracts, and the reasoning behind each decision.

---

## 1. Repository Layout

```
jobradar/
├── sources.yaml                 # company -> ATS mapping (§5 of ARCHITECTURE.md)
├── pyproject.toml
├── .github/workflows/
│   └── sync-ats.yml             # every 6h, ATS-only (fast, no browser)
├── jobradar/
│   ├── config.py                # loads sources.yaml + env vars
│   ├── connectors/
│   │   ├── base.py              # Connector interface + RawJob (§2)
│   │   ├── greenhouse.py
│   │   ├── lever.py
│   │   ├── ashby.py
│   │   └── scraper.py           # fallback Playwright/BS4
│   ├── pipeline/
│   │   ├── normalize.py         # dedup hash (§5)
│   │   ├── enrich.py            # tags + salary (§6)
│   │   ├── lifecycle.py         # expiry sweep
│   │   └── run.py               # orchestrates one run (§4)
│   ├── db/
│   │   ├── models.py
│   │   ├── migrations/
│   │   └── client.py
│   ├── api/
│   │   ├── main.py              # FastAPI app
│   │   ├── routes/{jobs.py,health.py}
│   │   └── deps.py              # auth, rate limit (§9)
│   ├── alerts/webhook.py        # run summaries (§8)
│   └── source_health.py         # consecutive-failure tracking (§7)
├── tests/
│   ├── test_normalize.py
│   ├── test_enrich.py
│   ├── test_connectors.py       # fixture-based, no live network
│   └── test_api_filters.py
└── scripts/run_scraper.sh       # entrypoint for VPS cron
```

## 2. Connector Interface

Every ATS client and the fallback scraper implement the same interface, so the pipeline orchestrator never needs to know where a job came from:

```python
class Connector(ABC):
    source_id: str  # "ats:greenhouse", "ats:lever", "ats:ashby", "scrape:custom"

    @abstractmethod
    def fetch(self, company: str, token: str) -> list[RawJob]:
        """Raises ConnectorError on failure — never raises anything else."""

@dataclass
class RawJob:
    title: str
    company: str
    company_url: str | None
    location: str | None
    description: str
    salary_structured: tuple[int, int, str] | None  # (min, max, currency) if source provides it
    salary_text: str | None                          # narrative text, for regex fallback
    apply_url: str
    posted_at: datetime | None
    source: str
```

This abstraction is why adding a fifth source later never touches `pipeline/run.py` — it only means a new file in `connectors/`.

## 3. Per-Connector Design Notes

Field names below are verified against each platform's own docs (Greenhouse's `developers.greenhouse.io`, Lever's `lever/postings-api` GitHub repo, Ashby's `developers.ashbyhq.com`) as of early August 2026. Re-check against a live response before finalizing the parser — these are public APIs outside your control, and each has evolved before.

### 3.1 Greenhouse (`connectors/greenhouse.py`)

- Endpoint: `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` — `content=true` is required to get the HTML description in the same call; without it you'd need a second request per job.
- Greenhouse has **two** APIs and it's an easy mix-up: the **Job Board API** (public, unauthenticated — what we use) and the **Harvest API** (private, authenticated, for the company's own recruiters). We only ever touch the former.
- Confirmed fields: `id`, `title`, `location.name`, `absolute_url`, `updated_at`, `content` (HTML), `metadata[]` (custom fields as `{name, value, value_type}`), `departments[]`, `offices[]`
- Gotcha: some boards store the real city/country in a custom `metadata` entry (often named something like "Job Posting Location") while `location.name` holds only the work mode (Remote / Hybrid / In-Office). Check `metadata` for a location-shaped field before trusting `location.name` alone.
- No first-class salary field. If salary appears anywhere, it's inside the HTML `content` blob — treat as a low-confidence regex-fallback source, not a primary one.
- Rate limit conservatively (~1 req/sec across the whole sync) — this endpoint serves every Greenhouse customer's board, not infrastructure provisioned for you.

### 3.2 Lever (`connectors/lever.py`)

- Endpoint: `GET https://api.lever.co/v0/postings/{token}?mode=json` — `mode=json` is required, or Lever serves HTML instead.
- ⚠️ **Lever's title field is `text`, not `title`.** A connector copy-pasted from the Greenhouse client will run without errors and silently produce an empty title for every Lever job. Confirmed against Lever's own `postings-api` repo — worth a comment in the code, not just this doc, so it survives a future refactor.
- Confirmed fields: `id`, `text` (title), `hostedUrl`, `applyUrl`, `categories` (`team`, `department`, `location`, `commitment`, `allLocations`), `workplaceType` (`unspecified`/`on-site`/`remote`/`hybrid`), `description` (HTML) + `descriptionPlain`, `lists` (structured responsibilities/requirements), `createdAt` (millisecond epoch)
- `salaryRange` (`currency`, `interval`, `min`, `max`) appears when a company opts into pay transparency — structured and reliable when present. Some postings instead carry only a narrative `salaryRangeDescriptionPlain` string; route that through the same regex fallback as Greenhouse rather than writing a second parser.
- Supports server-side filtering (`team`, `department`, `location`, `commitment`, `skip`, `limit`) — worth using for companies that post a lot of non-engineering roles, to avoid pulling and discarding them client-side.

### 3.3 Ashby (`connectors/ashby.py`)

- Endpoint: `GET https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true`
- Confirmed fields (from Ashby's own docs): `apiVersion`, and per job — `title`, `location` (plain string), `secondaryLocations[]` (nested address detail), `department`, `team`, `isListed` (bool), `isRemote` (bool), `workplaceType`, `descriptionHtml`
- Filter on `isListed: true` — unlisted/draft jobs can appear in the raw response and shouldn't reach the pipeline.
- No pagination: the entire board returns in a single response, even for companies with hundreds of open roles (useful — no cursor-handling code needed here).
- Compensation attaches per job when `includeCompensation=true` is set. This is the most reliable structured salary source of the three in practice, but populated inconsistently — common on US roles (state pay-transparency laws), thinner elsewhere. Confirm the exact nested shape against one live company's response before finalizing the parser; Ashby's docs are the source of truth, not this paragraph.

### 3.4 Adapter pattern (illustrative)

```python
# connectors/greenhouse.py
def _to_raw_job(raw: dict, company: str) -> RawJob:
    return RawJob(
        title=raw["title"],
        company=company,
        location=raw.get("location", {}).get("name"),
        description=raw.get("content", ""),
        apply_url=raw["absolute_url"],
        posted_at=parse_iso(raw.get("updated_at")),
        salary_structured=None,
        salary_text=raw.get("content"),
        source="ats:greenhouse",
    )

# connectors/lever.py
def _to_raw_job(raw: dict, company: str) -> RawJob:
    return RawJob(
        title=raw["text"],              # not `title` — see §3.2
        company=company,
        location=raw.get("categories", {}).get("location"),
        description=raw.get("description", ""),
        apply_url=raw["applyUrl"],
        posted_at=parse_epoch_ms(raw.get("createdAt")),
        salary_structured=_extract_lever_range(raw.get("salaryRange")),
        salary_text=raw.get("salaryRangeDescriptionPlain"),
        source="ats:lever",
    )
```

Each connector owns its own field mapping; nothing downstream cares which platform a job came from once it's a `RawJob`.

### 3.5 Fallback scraper (`connectors/scraper.py`)

- Try a plain `httpx` GET + BeautifulSoup first; only fall back to Playwright if the page is empty or clearly JS-rendered. Saves meaningful time/resources across even a small list of targets.
- Every scraped source needs a company-specific CSS selector map — store this in `sources.yaml` per source, not hardcoded, so a broken selector is a config fix, not a code change.
- Wrap every scrape in try/except that raises `ConnectorError`; never let one bad page crash the whole run (this is what §7 depends on).

## 4. Pipeline Orchestration (`pipeline/run.py`)

1. Load `sources.yaml`
2. For each source: call the matching connector, catch `ConnectorError`, record success/failure in `source_health`
3. Collect all successfully-fetched `RawJob` records
4. Normalize (§5) → hash → dedup against DB
5. Enrich (§6) → tags, salary
6. Upsert: insert new, refresh `last_seen_at` on existing matches
7. Expiry sweep (§7 of PRD.md FR-3): flip anything not touched this run, per source, past N days to `expired`
8. Post run summary to the alert webhook (§8)

The whole function must be safely re-runnable: if step 6 fails partway through, re-running from step 1 must not create duplicates. Idempotency is guaranteed by the unique `fingerprint_hash` constraint at the **database** level, not just an app-level check — the DB is the actual source of truth for "have I seen this before."

## 5. Normalization & Dedup Algorithm

```python
def normalize_key(company: str, title: str, location: str) -> str:
    def clean(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^\w\s]", "", s)   # strip punctuation
        s = re.sub(r"\s+", " ", s)       # collapse whitespace
        return s
    return f"{clean(company)}|{clean(title)}|{clean(location)}"

def fingerprint(company: str, title: str, location: str) -> str:
    return hashlib.sha256(normalize_key(company, title, location).encode()).hexdigest()
```

**Known limitation, noted on purpose rather than hidden:** this catches exact-after-normalization duplicates, not near-duplicates — "Senior Backend Engineer" and "Sr. Backend Engineer" at the same company still produce two records. Acceptable for v1. A fuzzy-matching pass (e.g., trigram similarity) is a reasonable v2 addition if duplicate volume turns out to matter in practice — not before, since it's real added complexity for a problem exact-match hashing mostly solves.

## 6. Enrichment Design

**Tag extraction — v1 is keyword matching, deliberately not NLP**
- Maintain `TAG_KEYWORDS: dict[str, list[str]]`, canonical tag → surface forms (e.g. `"python": ["python", "py3"]`)
- Search title + first N characters of description — full-text scanning every description across every source, every run, is wasted work for the signal it adds
- A keyword table is a five-minute edit when a new stack needs tagging; an embeddings pipeline is not, and isn't justified at this scale yet

**Salary parsing — structured-first, regex-fallback**
```
1. If the source provided salary_structured (Ashby usually, Lever sometimes) → use it directly
2. Else, regex over salary_text for patterns like $XXXk-$YYYk, $XXX,XXX-$YYY,YYY, "up to $XXXk"
3. No match → leave min_salary / max_salary NULL. Do not infer a number from role or seniority.
```
A wrong salary is worse for subscriber trust than a missing one — NULL is the correct output when the source doesn't say.

## 7. Source Health & Auto-Disable (`source_health.py`)

- Table: `source_health(source_id, consecutive_failures, disabled, last_success_at, last_error)`
- On failure: increment `consecutive_failures`; at 3, set `disabled = true` and include it in the next alert
- On success: reset `consecutive_failures` to 0
- Disabled sources stay skipped until manually re-enabled — deliberately no auto-recovery, since that would silently mask a source that needs a real fix (e.g., a company switched ATS platforms entirely)

## 8. Alerting Contract (`alerts/webhook.py`)

One message per run, every run, regardless of outcome:

```
JobRadar sync — 2026-08-02 02:04 UTC
✅ 187 sources synced · 1,402 active listings (+38 / -12 expired)
⚠️ 3 sources failed: acme-corp, foo-inc, bar-startup (2/3 strikes)
🛑 1 source disabled this run: baz-io (3/3 strikes — needs a look)
```
A single webhook POST works for Discord or Slack with no branching — same payload shape. No extra noise on a clean run beyond this summary; the goal is one glance to confirm health, not a flood of pings.

## 9. API Layer Notes (`api/`)

- `deps.py` accepts `X-RapidAPI-Proxy-Secret` **or** `X-API-Key` through the same dependency function, so direct (non-RapidAPI) access keeps working if billing ever moves off RapidAPI — this is what makes the abstraction goal in ARCHITECTURE.md §3.4 actually real rather than aspirational.
- Pagination: offset-based (`page`, `limit`) is the right call at this scale (thousands of rows, not millions). Cursor pagination would solve a scale problem this product doesn't have yet.
- All query params validated with Pydantic models; invalid params return the error shape from PRD.md §9, never a raw 500.

## 10. Testing Strategy

| Area | Test type | What it catches |
|---|---|---|
| `normalize_key` / `fingerprint` | Unit | Dedup silently failing on formatting differences |
| Salary regex patterns | Unit, table-driven over real example strings | A parsing rule silently returning a wrong number |
| Tag keyword matching | Unit | A tag misfiring or never firing |
| `/api/v1/jobs` filters | Integration (test DB) | A filter combination returning wrong or no results |
| Connector adapters | Unit, against **saved fixture JSON**, no live network | An upstream schema change (Greenhouse/Lever/Ashby) breaking the adapter silently |
| Full pipeline run | Integration, temp DB | Idempotency — running twice produces no duplicates |

Fixture-based connector tests matter specifically because these are third-party APIs outside your control. A saved response fixture lets you test your own parsing logic without depending on the network, and deliberately re-recording the fixture periodically is how you catch an upstream schema change on your own terms — not in production, via a silent count-of-zero.

## 11. Database Migration Approach

- Single migrations folder, sequentially numbered (`0001_initial.sql`, `0002_add_source_status.sql`, ...)
- Prefer additive changes (new nullable column) over renames — a solo project doesn't need blue/green schema changes, but it does need migrations that can't strand old code mid-deploy
- No destructive migration (drop column/table) without a manual backup step noted in that migration file's own comment header

## 12. Rejected Alternatives

| Considered | Rejected because |
|---|---|
| Scrape everything via Playwright, skip ATS APIs entirely | The original approach — directly conflicts with the low-maintenance goal; every target site redesign becomes a maintenance event |
| One monolithic `scrape_and_save.py` script | A single bad source would crash the entire run; per-source isolation was worth the extra structure |
| Fuzzy/embedding-based dedup for v1 | Real added complexity for a problem exact-match hashing mostly solves already; revisit only if duplicate volume is empirically a problem |
| Cursor-based pagination | Solves a scale problem this product doesn't have yet |
| Self-hosted billing from day one | RapidAPI removes the need to build billing/metering/keys before validating demand; revisit only after PRD.md §16's exit trigger |
