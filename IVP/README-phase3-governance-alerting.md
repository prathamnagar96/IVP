# Phase 3 — Governance, Human Validation & Alerting

> Part of the [Landslide EWP build guide](README.md). Safety-critical: SLAs, thresholds and mappings below are placeholders until agreed with the responsible civil authority and signed off by a qualified expert.

## At a glance

| | |
|---|---|
| **Goal** | Turn machine-generated triggers into expert-validated, authority-approved, standards-based alerts, and close the loop with de-escalation, audit and learning |
| **Inputs** | `BreachEvent` (Phase 2A), `RegionalAdvisory` and queue/exposure/runout data (Phase 1), evidence products (Phase 2B), ops notifications |
| **Outputs** | Alert decisions, CAP v1.2 messages and channel deliveries, all-clear messages, audit trail, KPIs, post-event reviews |
| **Cadence** | Real time; reviews and drills on a schedule |
| **Depends on** | Decisions D4 (SLAs), D5 (pre-authorised local actions), D10 (threshold sign-off) |
| **Build early** | M3: other phases need somewhere to send events |

## 1. Purpose and principles

1. **Default mode: no machine-only path to the public.** Every public alert requires an expert decision *and* an authority approval.
2. **Fail-safe, explicitly.** What happens when people do not respond is defined, tested and agreed, not assumed.
3. **Isolated alerting plane.** The workflow, expert UI and CAP builder run on a small, multi-AZ stack with minimal dependencies (root README §3).
4. **Auditable.** Every transition, evidence snapshot, approval and message is recorded and tamper-evident.
5. **People-centred.** An alert is only as good as the response; readiness work (§9) is part of the system.

## 2. Interfaces

| Direction | Data |
|---|---|
| In | `BreachEvent` (proposed level, triggers, IVM window, rain context, health) |
| In | `RegionalAdvisory` candidates, queue items, runout footprints, exposure counts |
| In | Drone evidence (STAC), sensor-health and feed-staleness ops notifications |
| Out | Decisions and approvals; CAP messages (Alert / Update / Cancel); channel delivery receipts |
| Out | Confirmed events → Phase 1 inventory and Phase 2A backtest library; threshold change requests |

## 3. Roles and responsibilities

| Role | Responsibilities |
|---|---|
| **Duty Geotechnical Expert (DGE)** | Reviews evidence, confirms / rejects / downgrades proposals, recommends level and area |
| **Backup Expert** | Takes over on SLA expiry or conflict of interest |
| **Civil Authority Duty Officer (CADO)** | Approves public broadcast, owns the decision to evacuate or close roads |
| **Dissemination Officer** | Reviews message text, languages and channel selection |
| **Platform Operator (SRE)** | Availability, feed health, incident response for the system itself |
| **Field Team Lead** | Site checks, verification flights, sensor repairs |
| **Community Focal Points** | Local relay, confirmation of receipt, feedback |

**RACI (R = responsible, A = accountable, C = consulted, I = informed)**

| Activity | DGE | CADO | Dissemination | SRE | Field |
|---|---|---|---|---|---|
| Review breach | **R/A** | I | I | I | C |
| Approve public broadcast | C | **R/A** | C | I | I |
| Compose / send CAP | C | A | **R** | C | I |
| Release all-clear | R | **A** | R | I | C |
| Change thresholds | **R** | **A** | I | C | C |
| Post-event review | R | A | R | R | R |

**Staffing:** a 24/7 expert SLA needs a rota. Plan roughly 5+ qualified people per on-call role plus a backup tier, handover procedures and fatigue limits.

## 4. Alert levels, triggers and governance

### 4.1 Levels

| Level | Meaning | Typical triggers | Standard actions | Notified |
|---|---|---|---|---|
| `ADVISORY` | Elevated conditions | Regional rain matrix `ADVISORY`; low-level creep above `k × noise` | Increase sampling; brief duty team | Duty team, authority duty officer |
| `WARNING` | Developing hazard | `WARNING_CANDIDATE`; acceleration on ≥ 2 sensors; scarp expansion in drone data; pore-pressure threshold | Notify responders and authority; prepare; consider verification flight | Responders, authority |
| `CRITICAL` | Failure likely | IVM window short; `v_crit`; critical pore pressure / rain threshold | Fast-lane expert review → authority approval → public alert | Authority → public |
| `ALL_CLEAR` | Hazard stood down | Quantified clearing conditions (§4.3) | Cancel/Update message; restore services | All previously notified |

### 4.2 Rules
- **Escalate immediately** on trigger (to *proposed* level; broadcast still requires approval).
- **De-escalate only by rule and approval**, one level at a time (`CRITICAL → WARNING → ADVISORY → CLEAR`), unless an expert override is recorded.
- **Hysteresis and minimum dwell** times prevent flapping.
- Regional advisories (Phase 1) and site-level proposals (Phase 2A) can both open events; the highest proposed level wins for a given area.

### 4.3 De-escalation / all-clear criteria (placeholders)
All triggers below `ADVISORY` for `T_clear_h`; no rain-threshold exceedance and none forecast within the horizon; sensors `NOMINAL`; verification by drone or field check; expert recommendation + authority approval; message sent as `Update` with `responseType = AllClear` (or `Cancel`, per authority convention).

### 4.4 Threshold change control
Thresholds are versioned configuration. Every change has proposer → expert reviewer → authority approver, effective date, rollback plan and change log. **No threshold edits during an active Warning/Critical** except through the emergency procedure (two approvers, recorded rationale).

## 5. Workflow state machine and SLAs

```
 MONITORING ──(trigger)──► TRIGGERED ──(auto)──► UNDER_REVIEW ──(expert confirms)──► AWAITING_AUTHORITY
     ▲                          │                    │ (reject / downgrade)                  │ (approve)
     │                          │                    ▼                                       ▼
     │                          └─(SLA expiry)─► ESCALATED ──► (backup expert → duty officer,  BROADCAST ──► ACTIVE
     │                                              flagged UNREVIEWED)                          │
     └────────────── CLOSED ◄──────────── DE_ESCALATING ◄───────────────────────────────────────┘
```

**Latency budget (capture → public)**

| Stage | Budget | Source |
|---|---|---|
| Data → trigger → event created | `T_detect` | D4 (placeholder) |
| Acknowledge | `T_ack` | D4 |
| Expert review | **≤ 15 min** | Source architecture |
| Authority decision | `T_authority` | **D4: undefined in source, must be agreed** |
| Message build and dissemination | `T_broadcast` | D4 |

**Escalation ladder:** primary expert → backup expert → authority duty officer (with an `UNREVIEWED` flag). Authority SLA expiry → next-level authority.

**Fail-safe direction (decide in D4/D5):**
- *Default mode:* the system **never broadcasts to the public by itself**. Expiry escalates people and notifies authorities; it does not bypass them.
- *Optional (D5):* for rapid-onset hazards where a human chain cannot meet the available lead time, a **pre-authorised, rule-based local action** may be configured: physical-sensor triggers only (not ML outputs), local devices only (road gate, local siren, signal) at a defined site, signed off by the authority, tested in Exercise mode, with a kill switch and automatic notification of the duty team.

## 6. Expert interface (WebGIS)

**Views:** region map (slope units, queue, advisories); site page (telemetry with noise-floor bands, IVM window and validity, rainfall vs thresholds, latest change maps, health); event timeline; decision panel; alert history; audit viewer.

**Evidence pack** (auto-assembled, hashed and stored with the event): triggering series, IVM output, rain context, drone change, Phase 1 risk/runout/exposure, population and assets in the footprint, **draft CAP message** and area polygon.

**Decision panel:** Confirm / Reject / Downgrade / Request verification / Escalate, with **mandatory comment**. Works on mobile; offline fallback shows the last evidence pack with its age.

## 7. CAP v1.2 and dissemination

**Mapping (suggestion; the authority's policy overrides)**

| Level | `urgency` | `severity` | `certainty` | `responseType` |
|---|---|---|---|---|
| `ADVISORY` | Future | Minor | Possible | Monitor / Prepare |
| `WARNING` | Expected | Moderate–Severe | Likely | Prepare |
| `CRITICAL` | Immediate | Severe–Extreme | Likely / Observed | Evacuate |
| `ALL_CLEAR` | Past | Minor | Observed | AllClear (`msgType = Update` or `Cancel`) |

```xml
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>EWP-R01-2026-000123</identifier>
  <sender>ewp@example.org</sender>
  <sent>2026-10-10T08:30:00+00:00</sent>
  <status>Exercise</status>               <!-- Actual only in live mode -->
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <category>Geo</category>
    <event>Landslide</event>
    <responseType>Evacuate</responseType>
    <urgency>Immediate</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <expires>2026-10-10T20:30:00+00:00</expires>
    <senderName>Regional Landslide Warning Centre</senderName>
    <headline>Landslide danger: leave the marked area now</headline>
    <description>Ground movement on the slope above the area is accelerating.</description>
    <instruction>Move to the designated shelter. Do not return until an all-clear is issued.</instruction>
    <area>
      <areaDesc>Zone A (below the northern slope)</areaDesc>
      <polygon>LAT1,LON1 LAT2,LON2 LAT3,LON3 LAT1,LON1</polygon>
    </area>
  </info>
</alert>
```

**Builder rules**
- Area polygons come from Phase 1 runout footprints plus a buffer approved by the expert.
- One `<info>` block per language; plain-language templates with explicit actions; no jargon.
- Updates reference earlier messages (`references`); all-clear is an `Update`/`Cancel`.
- `status = Exercise` / `Test` for drills; `Actual` only in live mode.
- Digital signature if the gateway requires it; message text frozen and hashed at approval.

**Channels (adapters behind one interface):** cell broadcast via the national/operator gateway, SMS, sirens via the authority's control system, radio/TV, apps, community networks (loudspeakers, messaging groups). CAP is the message *format*; each channel needs an adapter and a delivery receipt. Use ≥ 2 channels for Critical alerts, with retry policy and reach metrics.

## 8. Security, audit and availability

**Access:** OIDC SSO + MFA; RBAC; **two-person rule** for Critical broadcasts (expert and authority are distinct identities); signed approvals; short sessions; logged break-glass accounts.

**Audit:** append-only, hash-chained log of every transition, evidence-pack hash, message as sent, recipients, timestamps and approver identities. Retention per law.

**Availability:** alerting plane isolated and multi-AZ; no dependency on analytics; if the DB or UI is down, **out-of-band notification** (SMS/voice through ≥ 2 providers) pages the duty team with a minimal evidence link. Daily synthetic end-to-end canary (`Test` message to an internal sink). Define RPO/RTO with the authority (minutes for this plane).

**Security:** network segmentation, WAF, secrets in KMS/Vault, signed images, dependency scanning, **penetration test before the pilot**, least-privilege service accounts.

**Privacy:** minimal contact data, encryption at rest and in transit.

## 9. Operational readiness and feedback loop

**People-centred warning (four elements)**
1. *Risk knowledge:* Phase 1 maps, exposure, runout footprints
2. *Monitoring and warning service:* Phases 1–3
3. *Dissemination and communication:* CAP channels, community focal points, local-language messages
4. *Response capability:* SOPs, evacuation routes and shelters, drills

**Readiness checklist:** SOP per level and contact tree; community workshops; siren/signal meanings and signage; **drills at least twice a year** using `Exercise`-mode CAP; tabletop exercises for experts and officers; accessibility (language, literacy, disability).

**Post-event review (after every Warning/Critical and every missed event)**
- Timeline, data, decisions, delays against SLAs
- Alert accuracy, false alarms, near misses
- Actions: threshold review (§4.4), model recalibration, process fixes
- **Feedback:** confirmed events → Phase 1 inventory (with dates), time series → Phase 2A backtest library, lessons → SOPs

**KPIs**

| KPI | Definition |
|---|---|
| Time to acknowledge / decide / broadcast | Per stage vs the latency budget |
| Proposal precision | Expert-confirmed ÷ proposed |
| Missed events | Landslides without a prior Warning/Critical in the area |
| False alarms | Public alerts not followed by a confirmed hazard |
| Lead time | Alert time → event time |
| Reach | Delivered ÷ targeted, per channel |
| Sensor uptime / `BLIND` hours | From Phase 2A |
| Drill performance | Time and errors in exercises |

## 10. Data model

| Table | Key columns |
|---|---|
| `events` | `event_id`, `site_id` / `area_id`, `source`, `created_at`, `proposed_level`, `state` |
| `event_transitions` | `event_id`, `from`, `to`, `at`, `actor`, `reason` |
| `approvals` | `event_id`, `role`, `user_id`, `decision`, `comment`, `signed_at`, `evidence_hash` |
| `alerts`, `cap_messages` | `alert_id`, `event_id`, `level`, `status`, `msg_type`, `xml`, `hash`, `references` |
| `deliveries` | `alert_id`, `channel`, `sent_at`, `receipt`, `reach` |
| `contacts`, `areas`, `templates` | rota and recipients; polygons and geocodes; multilingual text |
| `audit_log` | append-only, hash chain |
| `threshold_versions` | `version`, `site_id`, `config`, `proposer`, `reviewer`, `approver`, `effective_at` |
| `kpi_snapshots` | per period |

## 11. Configuration (excerpt)

```yaml
sla:
  ack_min: null
  expert_review_min: 15          # source architecture
  authority_decision_min: null   # D4
  broadcast_min: null            # D4
escalation:
  expert: [primary, backup]
  authority: [duty_officer, next_level]
  on_expiry: escalate_notify     # default mode: never auto-broadcast
local_actuation:                 # D5, disabled by default
  enabled: false
  sites: []
cap:
  sender: ewp@example.org
  languages: [en]
  channels: {critical: [cell_broadcast, sms, sirens], warning: [sms, radio]}
deescalation: {min_dwell_h: null, clear_h: null, step_down_one_level: true}
```

## 12. Repository layout

```
phase3-governance-alerting/
├── README.md
├── config/                 # sla.yaml, escalation.yaml, cap.yaml, templates/
├── src/ewp_p3/
│   ├── workflow/           # state machine, timers, escalation
│   ├── cap/                # builder, validation, signing, templates
│   ├── channels/           # adapters: cell_broadcast, sms, siren, radio, apps
│   ├── api/                # FastAPI: events, decisions, evidence
│   ├── audit/              # hash-chained log
│   └── kpi/
├── ui/                     # WebGIS expert interface (MapLibre GL / Deck.gl)
├── sql/
├── runbooks/               # incident, failover, drills, post-event review
└── tests/
```

## 13. Testing and drills

- **State machine:** property tests: no path to `BROADCAST` without both approvals unless `local_actuation` is explicitly enabled; timers and escalation behave per config.
- **CAP:** schema validation; round-trip tests; polygon closure; multilingual blocks.
- **Contract tests:** `BreachEvent` and `RegionalAdvisory` from real producers.
- **Chaos / failover:** DB down, UI down, channel down, clock skew; out-of-band paging works.
- **Load:** burst of events during a storm.
- **Exercise-mode end-to-end** at least quarterly; **tabletop exercises** twice a year; **penetration test** before pilot.

## 14. Acceptance criteria

- [ ] D4 SLAs and D5 decision signed by the authority
- [ ] End-to-end drill: synthetic breach → expert → authority → CAP `Exercise` to internal sink within latency budget
- [ ] Two-person rule and audit chain verified by test
- [ ] Failover and out-of-band paging verified
- [ ] 24/7 rota staffed and trained; SOPs and contact trees published
- [ ] De-escalation and all-clear flow tested
- [ ] Penetration test passed; findings closed
- [ ] KPI dashboard live

## 15. Risks and mitigations

| Risk | Mitigation |
|---|---|
| No response within SLA | Escalation ladder; out-of-band paging; explicit fail-safe (D4/D5) |
| Lead time shorter than the human chain (debris flows) | Fast lane; optional pre-authorised local action (D5) |
| False alarms erode trust | Corroboration upstream; expert gate; precision KPI; post-event review |
| Alert fatigue from advisories | Level discipline; hysteresis; separate ops vs public channels |
| Single-channel failure | ≥ 2 channels for Critical; delivery receipts |
| Staff burnout | Rota size, backup tier, handovers |
| Threshold drift or tampering | Change control, versioning, audit |
| System outage during storm | Isolated plane, multi-AZ, out-of-band path |

## 16. Open decisions (Phase 3)

- **D4** SLAs (expert, authority, total), false-alarm budget, fail-safe behaviour
- **D5** Pre-authorised local actions for rapid-onset hazards
- **D10** Threshold sign-off authority and change-control process
- Which national/regional alert gateway and channels apply; languages; siren protocols
- Who owns evacuation orders and all-clear decisions
