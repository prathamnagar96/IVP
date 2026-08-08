# JobRadar API — Engineering & Operating Rules

**Companion to:** PRD.md, ARCHITECTURE.md
**Last Updated:** August 1, 2026

---

These exist for one reason: to keep this project genuinely low-maintenance, not just labeled that way. If you use an AI coding agent to help build or maintain this project, keep a copy of this file at the repo root and point your agent's project instructions at it so these constraints get applied automatically.

## 1. Scope Discipline

- No new data source without going through the onboarding checklist in §4
- No feature beyond the roadmap in PRD.md §15 without writing down, in one sentence, what it costs in ongoing attention
- Prefer boring, well-documented tools over novel ones — you're optimizing for "still works in 6 months without you thinking about it," not for interesting engineering
- If a task can't be described in one sentence, break it down before starting it

## 2. Code & Repo Conventions

- Pin dependency versions; note why when you deviate from latest
- Keep collection, processing, and API as separate modules — a break in one shouldn't require touching the others
- All tunable values (source list, failure thresholds, expiry windows) live in version-controlled config, never hardcoded
- Minimum test coverage: dedup hashing, salary parsing, and API filters — these are the three places a silent bug corrupts data without anyone noticing
- Write commit messages like someone else (future you, six months from now) has to debug this from git history alone

## 3. Data Handling

- Store only the fields defined in the schema — don't accumulate "might be useful later" data
- Every write is idempotent — re-running a job after a partial failure must never create duplicates or corrupt state
- Any one-off manual database change gets written as a script and committed, not run once from a SQL console and forgotten
- Auto-expire listings per FR-3 in the PRD — don't let the database grow unbounded with dead postings

## 4. Source Onboarding Checklist

Before adding **any** new source, confirm:

- [ ] Checked whether the company uses an ATS with a public API (Greenhouse/Lever/Ashby/Workable) before considering scraping
- [ ] Checked `robots.txt` and, where practical, the site's terms
- [ ] Set a conservative request rate and a descriptive User-Agent
- [ ] Logged the source in a registry (method, date added, any ToS notes)
- [ ] Confirmed you have a way to remove this source quickly if asked

## 5. Automation & Alerting Rules

- Every pipeline run posts a summary to the alert channel — success counts, failures, nothing silent
- 3 consecutive failures for a single source → auto-disable that source + alert; don't let it keep erroring or silently return nothing
- Put a recurring 15-30 minute calendar reminder (weekly) to skim the alert channel and glance at billing dashboards — this *is* the maintenance loop. If it's regularly taking longer than that, something upstream needs fixing, not more of your time.

## 6. Cost Guardrails

- Set a billing/usage alert on every provider that offers one (Supabase, hosting, RapidAPI)
- Only reconsider your infra tier after being consistently near a free-tier limit for 2+ months straight — don't preemptively upgrade for hypothetical scale

## 7. Legal & Ethical Guardrails

- A source that actively blocks you (Cloudflare, DataDome, etc.) is a signal to deprioritize it, not a problem to engineer around
- Always keep the original `apply_url` in every record — good practice, and it keeps you on good terms with the companies you're aggregating
- Respond to takedown/opt-out requests within a few business days — write down an actual number and stick to it
- Re-check ToS on your top sources roughly twice a year; they change

## 8. If You're Using an AI Coding Agent

- Treat this file and ARCHITECTURE.md as the source of truth — ask the agent to re-read them if it proposes something that contradicts either
- The agent should ask before adding a new paid dependency, new external service, or new scraped source
- The agent should never quietly remove the dedup/idempotency logic to "simplify" a change — it should flag that explicitly if it thinks the logic should change
- The agent should run existing tests before considering any change complete

## 9. What "Low Maintenance" Actually Means Here

A concrete, checkable definition, not a vibe:

- Under 30 minutes/week of hands-on time in steady state
- No single failure mode that silently corrupts data without surfacing an alert within 24 hours
- Adding a new ATS-based source takes under 10 minutes
- You could ignore this project for two weeks and come back to a working (if slightly stale) feed, not a broken one
