# JobRadar API — Product Requirements Document

**Version:** 2.0 (Revised)
**Status:** Draft for Review
**Supersedes:** v1.0
**Last Updated:** August 1, 2026

---

## 0. What Changed From v1.0, and Why

| Area | v1.0 | v2.0 | Why |
|---|---|---|---|
| Primary data source | Scrape 200+ career pages directly (Playwright/BeautifulSoup) | Pull first from ATS public JSON APIs (Greenhouse, Lever, Ashby, Workable); scrape only as fallback | HTML scrapers break on every redesign. JSON endpoints don't. This is the single biggest lever for actually staying low-maintenance. |
| Wellfound / AngelList | Treated as a core scrape target | Optional, out of scope for v1 | Actively defended with bot-detection. Fighting that is fragile, costly, and raises the risk profile for little coverage gain once ATS sourcing exists. |
| Legal/compliance | Not addressed | Dedicated section + source onboarding checklist | Scraping ToS exposure is real business risk. A proper PRD names it instead of hoping it doesn't come up. |
| Competitive landscape | Not addressed | Added — JSearch, JobsPipe, and similar already exist | Pricing and positioning only make sense once you know who else sells job data on RapidAPI. |
| Monitoring/alerting | Not addressed | Now a functional requirement | "Low maintenance" is impossible without knowing when something breaks — the alternative is silent data rot. |
| Cost vs. latency | "<$10/month" and "<150ms" stated together | Shown to be in tension; realistic budget given | Free-tier hosting sleeps after inactivity with 30-60s cold starts, which fails a 150ms target outright. |
| Timeline | "3-Day MVP" | 3-day core build + ~1 week hardening before calling it live | A pipeline that breaks on day 4 isn't income, it's a demo. |
| Pricing tiers | Basic / Pro / Ultra | Added a low-cost Starter tier | The Newsletter persona's real usage doesn't need Pro's 5,000 requests/month — the jump from free to $29 was too wide. |

---

## 1. Executive Summary

JobRadar API is a niche B2B data feed of remote software-engineering job postings at YC- and VC-backed startups, distributed as a subscription JSON API through RapidAPI. It targets a narrow, underserved buyer — solo and small-team operators (niche job board owners, newsletter authors, boutique recruiters) — who need fresh, tagged, startup-specific listings and can't justify enterprise data contracts or the engineering time to build their own pipeline.

The product isn't trying to out-cover JSearch or Indeed. It's trying to be the smallest, freshest, best-tagged feed for one specific slice of the job market, sourced primarily from first-party ATS data rather than fragile HTML scraping, so it can run with near-zero ongoing attention.

## 2. Problem Statement & Market Reality

Niche job board owners and newsletter authors currently either hand-curate listings (slow, doesn't scale) or pay for generalist aggregator APIs built for breadth, not depth. Several of those already exist on RapidAPI:

- **JSearch** (OpenWeb Ninja) — the most-subscribed jobs endpoint on RapidAPI. Aggregates a handful of consumer job boards (LinkedIn, Indeed, ZipRecruiter, Glassdoor, Bayt), largely via Google for Jobs results. Broad, but not startup-specific and not deeply enriched.
- **JobsPipe** — a smaller, production-positioned competitor that, like the architecture below, pulls directly from ATS platforms and normalizes compensation and dedup. This is the closest thing to a direct competitor on approach, and worth watching.
- **FlyByAPIs** and similar Google-Jobs wrappers — cheap, high-volume, generic.

This means JobRadar can't win on "we have an API." It has to win on **who the jobs are for** (remote SWE at funded startups, specifically) and **how clean the enrichment is** (tech-stack tags, real salary bands where the ATS publishes them — Ashby often does).

## 3. Goals & Non-Goals

**Goals for v1**
- Ship a working, monetized feed within roughly 1-2 weeks (fast core build, honest hardening pass)
- Validate willingness to pay before investing further
- Design the pipeline so a normal week requires under ~30 minutes of manual attention

**Explicit non-goals for v1**
- Non-engineering roles
- In-house billing (ride RapidAPI's billing rails to start; see §12 for the exit plan if that changes)
- Any public-facing website, job-seeker product, or candidate features
- Full coverage of Wellfound/AngelList or any source that requires active anti-bot evasion
- More than a small, curated set of scraped (non-ATS) fallback sources at launch

## 4. Target Personas

1. **Niche Job Board Owners** — need a fresh feed pushed automatically instead of manual entry. Likely Pro-tier, pulling a few times a day.
2. **Newsletter Authors** — need a periodic (daily/weekly) pull of high-paying remote roles. Realistically a **low-volume** user, which is why v2.0 adds a Starter tier (§13).
3. **Recruitment Agencies** — want hiring signals by tech stack to pitch staffing services. Highest volume, most likely Ultra tier.

## 5. Success Metrics

- **Freshness:** ≥95% of active listings reflect a state seen within the last 24h
- **Coverage stability:** ATS-sourced companies maintain >98% sync success per run (fallback scrapers are expected to be flakier and shouldn't count against this number)
- **Maintenance load:** <30 minutes/week of hands-on attention in steady state
- **Business:** first paying subscriber within 30 days of launch
- **Reliability:** 99% monthly API uptime (generous, appropriate for hobby-tier infra)

## 6. Data Sourcing Strategy (Core Revision)

This is the most consequential change from v1.0, and it exists to serve one goal: make "low maintenance" actually true, not just written down.

### 6.1 Primary source: ATS public job board APIs

Most YC- and VC-backed startups post jobs through a small number of Applicant Tracking Systems that expose public, unauthenticated JSON endpoints built for exactly this kind of syndication:

| ATS | Endpoint pattern | Notes |
|---|---|---|
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs` | Most common among YC/tech startups. Salary field frequently empty — many companies don't publish it here. |
| Lever | `GET https://api.lever.co/v0/postings/{token}?mode=json` | Common at growth-stage startups. Flatter schema than Greenhouse. |
| Ashby | `GET https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true` | Increasingly common at newer, salary-transparent startups. Frequently *does* publish structured compensation — a genuinely good source for `min_salary`/`max_salary` instead of regex-parsing free text. |
| Workable | Public careers API, per-account | Less common in venture-backed tech, more common in SMB/agency hiring. Lower priority. |

Because these are JSON, not rendered HTML: no CSS selectors to maintain, no headless browser needed, no layout-change breakage, and materially lower legal exposure than scraping a site that's actively trying to keep scrapers out (see §11).

**Practical implication:** build one small, typed client per ATS (four total), driven by a `sources.yaml` mapping `company → ATS type → board token`. Adding a company becomes a one-line config change, not new scraper code — this is the actual mechanism by which the pipeline stays low-maintenance.

### 6.2 Fallback source: targeted HTML scraping

For companies that don't use one of the above ATS platforms, keep the original Playwright/BeautifulSoup scraper, but scope it down:
- Only for a curated, small list of high-value companies without an ATS API
- Isolated from the ATS pipeline so a broken scraper never blocks the ATS sync
- Tracked per-source: after 3 consecutive failures, auto-disable + alert rather than error the whole run

### 6.3 Deprioritized: Wellfound / AngelList direct scraping

Wellfound is actively defended — third-party scrapers targeting it commonly report needing residential proxies and anti-detection browser tooling to get past its Cloudflare and bot-detection layers. That's a signal, not a challenge. Treat it as **out of scope for v1**: fighting an actively-defended site is the opposite of low-maintenance, and most Wellfound-listed startups also post directly to Greenhouse/Lever/Ashby anyway. If Wellfound coverage is worth pursuing later, do it through licensed data or a partnership, not scraper evasion.

## 7. Functional Requirements

**FR-1: Source Sync Pipeline**
- FR-1.1: ATS sources sync on a short cycle (e.g., every 6 hours) — cheap, fast JSON calls
- FR-1.2: Fallback HTML scrapers run on a slower cycle (e.g., daily) since they're heavier
- FR-1.3: Extract Job Title, Company, Company URL, Location/Remote Eligibility, Description, Salary (if present), Apply URL, Posted Date, and Source (`ats:greenhouse`, `ats:lever`, `ats:ashby`, `scrape:custom`)
- FR-1.4: Filter recruiter/agency spam, non-technical roles, and dead apply links

**FR-2: Normalization & Deduplication**
- FR-2.1: `fingerprint_hash = SHA-256(normalized_company + normalized_title + normalized_location)`; normalize (lowercase, strip whitespace/punctuation) before hashing so near-identical strings from different sources still collide correctly
- FR-2.2: Keyword-match tech-stack tags from title + description; treat as a v1 heuristic, not NLP — there's an upgrade path later if needed
- FR-2.3: Parse salary into `min_salary`/`max_salary` (USD); prefer structured ATS compensation fields (Ashby) over regex-parsed free text when both are available

**FR-3: Listing Lifecycle**
- FR-3.1: Mark listings `status = active | expired`
- FR-3.2: Auto-expire any listing not seen in its source's latest sync after N days (keeps data honest and the database small)

**FR-4: API Serving Layer**
- FR-4.1: `GET /api/v1/jobs` with filters (`tag`, `company`, `min_salary`, `limit`, `page`)
- FR-4.2: Auth via `X-RapidAPI-Proxy-Secret` or `X-API-Key`
- FR-4.3: Tier-based rate limiting
- FR-4.4: `GET /health` — lightweight endpoint for uptime monitoring, independent of the jobs table

**FR-5: Monitoring & Alerting** *(new)*
- FR-5.1: Every pipeline run emits a summary (sources succeeded/failed, records added/expired) to a webhook (Discord/Slack/email) — no manual log-checking required
- FR-5.2: A source that fails 3 syncs in a row is auto-disabled and flagged, not silently zeroed out
- FR-5.3: A free external uptime monitor watches the public `/health` endpoint

**FR-6: Source Governance** *(new)*
- FR-6.1: Every source recorded in a registry (method, date added, ToS notes)
- FR-6.2: A documented process to honor a takedown/opt-out request from a listed company

## 8. Data Model

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, `gen_random_uuid()` | Internal ID |
| fingerprint_hash | TEXT | Unique, Not Null | SHA-256 dedup hash on normalized inputs |
| title | TEXT | Not Null | Job title |
| company | TEXT | Not Null | Hiring company |
| company_url | TEXT | Nullable | Company domain |
| location | TEXT | Default `'Remote'` | Geographic/remote region |
| tags | TEXT[] | Default `'{}'` | Extracted tech tags |
| min_salary | INTEGER | Nullable | Minimum annual USD salary |
| max_salary | INTEGER | Nullable | Maximum annual USD salary |
| apply_url | TEXT | Not Null | Direct application link |
| source | TEXT | Not Null | `ats:greenhouse`, `ats:lever`, `ats:ashby`, `scrape:custom` *(new)* |
| status | TEXT | Default `'active'` | `active` / `expired` *(new)* |
| posted_at | TIMESTAMPTZ | Default `NOW()` | Original post timestamp |
| last_seen_at | TIMESTAMPTZ | Default `NOW()` | Updated on every sync that still finds this listing — drives auto-expiry *(new)* |
| created_at | TIMESTAMPTZ | Default `NOW()` | Record creation timestamp |

**Indexes:** unique on `fingerprint_hash` (dedup); GIN on `tags` (tag filtering); btree on `posted_at` (pagination/sorting); btree on `(status, last_seen_at)` (expiry sweep + active-only queries).

## 9. API Specification

**`GET /api/v1/jobs`** — paginated list of active listings.

Query parameters: `tag` (string, optional), `company` (string, optional), `min_salary` (int, optional), `limit` (int, default 50, max 100), `page` (int, default 1).

Sample response (200 OK):
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

Error response shape:
```json
{ "status": "error", "message": "min_salary must be a positive integer", "code": "invalid_parameter" }
```

Rate-limit headers on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

**`GET /health`**
```json
{ "status": "ok", "last_successful_sync": "2026-08-01T02:15:00Z" }
```

## 10. Non-Functional Requirements

- **Latency:** <150ms for `/api/v1/jobs`. **Requires always-on, paid hosting** — free-tier Render/Railway web services sleep after ~15 minutes idle with 30-60s cold starts, which breaks this target outright.
- **Freshness:** ATS sources refreshed at least every 6h; fallback sources at least every 24h
- **Maintainability:** <30 min/week hands-on in steady state (see RULES.md)
- **Reliability:** 99% monthly uptime target
- **Cost:** see §11 below — realistically ~$12/month pre-revenue, not $10, once a paid hosting tier is included

*Note on Supabase's free tier: projects auto-pause after 7 days with zero database activity. In practice a daily pipeline keeps this from ever triggering — but it means a silently-broken pipeline has two costs, not one: stale data now, and a paused database later. Another reason FR-5 isn't optional.*

## 11. Legal & Compliance Considerations *(new)*

*This is general information, not legal advice. Talk to a lawyer before scaling revenue meaningfully.*

- Scraping publicly accessible web data is broadly permitted in many jurisdictions, but that's a separate question from a website's Terms of Service, which is a contract matter, not a criminal one. Violating a site's ToS can still mean a cease-and-desist, an IP ban, or in rare cases a civil claim, even where the scraping itself isn't independently illegal.
- The sourcing strategy in §6 is designed around this: ATS job-board endpoints are public, unauthenticated, and intended for syndication — meaningfully lower-risk than scraping a site that's actively trying to keep scrapers out.
- Baseline hygiene regardless of source: respect `robots.txt`, identify your bot with a descriptive User-Agent, keep request rates reasonable, and don't build features whose sole purpose is evading detection.
- Keep the apply link pointing at the original source (already in the schema) — good practice for legitimacy and goodwill with the companies being aggregated.
- Maintain a real opt-out process. If a company asks to be removed, honor it quickly — cheap insurance against a complaint turning into anything more.

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Source site redesign breaks a scraper | Stale/missing data for that source | ATS-first sourcing means this mostly can't happen for the majority of sources; fallback scrapers are isolated and monitored |
| A source adds anti-bot protection | Wasted engineering time fighting it | Treat a block as a signal to deprioritize, not a challenge |
| RapidAPI dependency | Distribution/billing outage or policy change is a single point of failure | Keep auth/billing logic behind an internal abstraction so a future move to self-hosted Stripe billing (or another marketplace) doesn't require rebuilding the API |
| Free-tier infra limits hit unexpectedly | Downtime or a paused database | Usage/billing alerts on every provider |
| Market is more crowded than assumed | Harder to convert trial → paid | Validate cheaply first; lead with the niche + enrichment angle, not "we have a jobs API" |
| Takedown/complaint from a listed company | Reputational/legal friction | Documented opt-out process, always link back to source |

## 13. Cost Breakdown

| Component | Provider | Tier | Cost |
|---|---|---|---|
| Database | Supabase | Free → Pro once revenue exists | $0 → $25/mo |
| ATS sync jobs | GitHub Actions | Free (unlimited on public repo; 2,000 min/mo free on private) | $0 |
| Fallback scraper runner | VPS | Existing $5/mo tier | $5/mo |
| API hosting | Render/Railway | Paid entry tier (needed for latency target) | ~$7/mo |
| Distribution/billing | RapidAPI | Marketplace commission on paid-tier revenue | Confirm current rate before finalizing prices |
| **Total, pre-revenue** | | | **~$12/mo** |
| **Total, with paying subscribers** | | | **~$32-37/mo** |

*Verified against provider pricing pages and community reports as of late July 2026 — these terms change; recheck supabase.com/pricing, render.com/pricing, and docs.github.com before finalizing a budget.*

## 14. Pricing & Monetization

| Plan | Price | Quota | Best for |
|---|---|---|---|
| Basic | $0/mo | 50 requests | Sandbox / testing |
| **Starter** *(new)* | **$9/mo** | **500 requests** | **Newsletter authors doing a periodic digest pull — the old jump from free to $29/5,000 didn't match this persona's actual usage** |
| Pro | $29/mo | 5,000 requests | Niche job boards syncing several times a day |
| Ultra | $79/mo | 50,000 requests | Recruiting agencies / SaaS tools |

This space isn't empty — JSearch and similar Google-Jobs wrappers already sell cheaper, higher-volume generic access on RapidAPI. Market and price this on curation quality (startup-specific, tech-tagged, ATS-fresh), not a per-request price war against a five-source generalist.

## 15. Implementation Roadmap

**Days 1-3 (core build, matches original ambition)**
- Day 1: Supabase schema, Greenhouse client (highest coverage first), dedup logic
- Day 2: Lever + Ashby clients, FastAPI endpoints, GitHub Actions sync workflow
- Day 3: Deploy API, connect RapidAPI, configure pricing tiers, soft-launch

**Days 4-7 (hardening — the part that actually makes this low-maintenance)**
- Monitoring/alerting (FR-5)
- Source registry + opt-out process (FR-6)
- A small curated fallback-scraper list for a handful of non-ATS companies, if desired
- Populate `sources.yaml` with enough companies to make the feed genuinely useful — start with a few hundred well-known YC/VC-backed companies on Greenhouse/Lever/Ashby, expand over time

**Ongoing (steady state)**
- Weekly: skim the alert channel, glance at billing dashboards (~15-30 min)
- Monthly: revisit the source list, re-check ToS on top sources, review any disabled sources

## 16. Out of Scope / Future Ideas

- Slack/Discord bot for new-listing alerts
- Expanding beyond software-engineering roles
- Self-hosted billing (Stripe) to avoid marketplace commission, once revenue justifies the engineering time
- Embeddings-based tagging instead of keyword matching
- Additional ATS coverage (Workable, Recruitee, Personio, SmartRecruiters) if buyer demand shows up outside the current niche
