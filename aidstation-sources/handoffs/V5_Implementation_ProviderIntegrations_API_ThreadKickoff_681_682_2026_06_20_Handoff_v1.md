# V5 Implementation — Provider Integrations & API — Thread Kickoff (#681 / #682 / live-provider wiring) — Handoff (2026-06-20)

This is a **forward-looking thread handoff**, not a closing handoff for a shipped
slice. The #767 manual file-upload track just closed; Andy's direction (2026-06-20)
is to continue on the **provider integrations & API** thread. This doc frames it
so the next session can pick up and build.

## 1. Where we are (what just closed)

**#767 manual file-upload ingestion — COMPLETE + CLOSED.** Slices 1+2+4 merged,
3 retired (`not_planned`), **5 merged (`#785`)**, issue **#767 closed
`completed`**. Net: any device that *exports a file* — `.fit` / `.tcx` / `.gpx`
activities, Garmin wellness/daily-metric FITs, a WHOOP `physiological_cycles.csv`,
or a `.zip` of any — ingests through **one auto-detecting drop zone** on the
connections Data hub (`routes.garmin.import_bulk` classifies by extension and
routes: activities → `cardio_log`; Garmin wellness FITs → `wellness_log` /
`daily_wellness_metrics`; WHOOP CSV → `provider_raw_record`).

That solved *file* ingestion. It did **not** finish integrations. Two axes remain
unbuilt: **live two-way provider syncs** (most providers are Phase-0 stubs) and
**our own structured API** (#682, unstarted). Plus the **#681 §4 build wave** that
turns the just-authored inbound mapping into real tables.

### Live provider connection status (ground truth, from `routes/`)

| Provider | State | Route files |
|---|---|---|
| **COROS** | Live OAuth + webhook ingest ✅ | `coros.py` + `coros_ingest.py` |
| **Polar** | Live OAuth + webhook ingest ✅ | `polar.py` + `polar_ingest.py` |
| **Garmin** | **Paused** — Garmin closed their API. Manual `.fit` upload only. | `garmin.py` |
| **Strava / Whoop / TrainingPeaks / Zwift / Ride With GPS** | **Phase-0 stubs** — webhook returns 200 so the URL validates; no OAuth start, no ingest. Shown "Not available yet" on the hub. | `strava.py`, `whoop.py`, `trainingpeaks.py`, `zwift.py`, `ride_with_gps.py` |
| **Wahoo / Oura** | Not built (Wahoo files can be *uploaded* via the Source picker; no live sync). | — |

## 2. The thread — three work-streams

### (A) #681 §4 build wave — the canonical provider store  *(do first)*

The **inbound mapping is fully authored**: `specs/Provider_Inbound_Matrix_v2.md`
(PR **#723 MERGED** 2026-06-18) maps 7 providers (Strava · Oura · WHOOP · Wahoo ·
RWGPS · TrainingPeaks · Zwift) from official developer docs to the real layer0
discipline canon + the §2.3 metric registry, **in the exact column vocabulary of
the future `provider_value_map` table** — so the build is transcription, not
re-derivation.

**Ratified gating decisions (don't re-litigate):**
- **§1 cardio-discipline target = option C** — map to the fine layer0 D-id with a
  deterministic coarse `_plan_sport_type` collapse (preserves skimo/paddle/climb
  signal; mirrors #679).
- **§6 Rowing D-033 mint = REVERSED (2026-06-18).** Rowing stays **bucket-3**; no
  Rowing discipline, **no layer0 migration**, `discipline_canon.py` untouched.
  Erg-rowing as a training substitute is already covered by the `Rowing
  ergometer` machine in the Layer-4 feasibility cascade.
- **§12** generalizes it: stair-stepper / elliptical / walking / rollerski / yoga
  / HIIT / indoor rides are **training modalities or equipment, not disciplines** —
  they get homes in the equipment cascade / `CATEGORY_STRENGTH|MOBILITY` rows /
  the coarse `_plan_sport_type`, **not** a D-id. So **no `discipline_type` flag
  column** is needed (a training-only modality can't leak in as a race leg).

**Build (the actual §4 work):**
1. Stand up the canonical-store tables: **`provider_value_map`** (the mapping
   rows), **`provider_raw_record`** (already exists — record-don't-drop raw), and
   **`provider_outbound_ref`** (for Wave-3 outbound).
2. **Backfill the scattered provider dicts** (currently inline in
   `provider_value_map_seed.py` / per-route mapping dicts) into `provider_value_map`.
3. `cardio_log` carries the **fine D-id** + a **D-id → coarse collapse** table.
4. **Record the inbound indoor/machine flag** — the one real gap §12 surfaced:
   Strava `VirtualRide`/`StairStepper`, RWGPS `is_stationary`, Wahoo
   `workout_type_location_id`, currently only in `raw_payload`.
- **Multi-source precedence = freshest-timestamp-wins** (de-dup TP hub-of-hubs
  re-emits by source-of-origin). `ftp_w` now has 3 sources; `sleep_score` /
  `resting_hr_bpm` / `body_mass_kg` have 2–3 — the case *for* the unified store.
- Deferred (per matrix §7): **Batch 4 MyFitnessPal** (blocked on a Layer-2E
  nutrition model), **Batch 5 Apple/Samsung/Google Health** (native-client-gated).

**⚠️ Stop-and-ask Trigger #3** (cross-layer surface — new tables + inter-layer
contract). Put the table DDL + the backfill plan in front of Andy before building.

### (B) Live-provider OAuth/webhook wiring

Turn the Phase-0 stubs into real inbound syncs, landing data through the (A)
store. Per provider: an **OAuth app registration** (Andy's hands — external
dev-portal step), a **token-exchange + connect flow** (mirror `coros.py` /
`polar.py`), and **ingest wiring** (mirror `coros_ingest.py` / `polar_ingest.py`,
writing via the #681 translation map).
- **First targets: Strava + Whoop** — highest-value consumer wellness/cardio,
  mapping already authored (Batch 1), and the stubs + the file-upload path already
  exist. Then Wahoo / Oura / RWGPS.
- **TrainingPeaks** = real bidirectional partner API but **partner-access-gated**
  (primarily outbound, Wave 3b). **Zwift** = **no inbound API** (its activities
  arrive via Strava or a FIT export) — don't build a Zwift inbound connector.
- Touches **#251** (OAuth-first onboarding — connect a provider before sign-up).

### (C) #682 AIDSTATION API — scope it

Stub epic, unstarted. A **structured API over the canonical model** so web +
eventual native iOS/Android clients (the prerequisite for Apple/Samsung Health) +
our own ingest/read paths speak one contract. **North-star principles to spec:**
canonical keys *are* the contract (layer0 EX-ids, discipline/modality ids, metric
keys, units, zones — the same definitions #681 resolves to); **one pipeline, one
schema** (adding a provider/metric is a data/seed change, not an API change);
**record-don't-drop surfaces through the API** (bucket-3 non-prescribed activities
+ raw/by-provider metric view); **provider attribution + mapping confidence + raw
value first-class** in response shapes (so dormant data lights up later without a
breaking change). **Peer epic to #681 — design together.** Relationships: **#251**
(OAuth-first onboarding), **#268** (BYOK Anthropic key), **#279** (API token TTL).
Endpoint/route design, auth model, versioning, pagination — **all TBD**.

**⚠️ Stop-and-ask Trigger #5** (architectural alternatives with real tradeoffs) —
this is a spec/design pass; ratify the surface + auth model with Andy first.

## 3. Recommended sequencing (4-tier order)

1. **(A) #681 §4 build wave first.** It's the spine both (B) and (C) plug into:
   provider lands data → translation store → read/API. The mapping is authored, so
   it's transcription + DDL, not derivation. *(Ratify the table DDL — Trigger #3.)*
2. **(B) Strava + Whoop live wiring** onto that store — first real two-way syncs.
3. **(C) #682 API scoping** in lockstep with (A)'s contract. *(Trigger #5.)*

Smaller integration items (independent, low-pri): **#754** (no real-Postgres
integration test for the cardio-ingest write paths — current tests use fakes),
**#524/#525** (wellness-FIT polish), **#528** (persistent FIT-dump archive),
**#458** (Garmin Fenix "Unknown Exercise" labels).

## 4. Gut check

- **Biggest risk:** (A) is a Trigger-#3 schema change touching the inter-layer
  contract — easy to over-build. The matrix already constrains it; resist adding
  columns/knobs beyond what §4/§12 specify (esp. the *no* `discipline_type` flag
  decision). Ratify DDL before coding.
- **What might be missing:** the live-wiring (B) per-provider OAuth app
  registrations are **Andy-action external steps** (dev portals); the container
  can't do them. Sequence so code is ready and the registration is the only gate.
- **Best argument against doing this now:** the actual *launch* blocker is the
  compliance program (privacy/DSR/deletion/AI-training governance — ~45 high-pri
  `v1` issues), much of it legal/ops decisions only Andy can make. Integrations are
  product-completeness, not launch-gating. Worth a conscious call on whether the
  integration thread or the compliance thread is the priority before sinking build
  time here. (Andy chose the integration thread for this arc.)

## 5. This session's changes (bookkeeping only — no code)

Docs only: `CURRENT_STATE.md` (slice-5 → MERGED `#785` + #767 closed; "Next moves"
tier-4 → this thread), `CARRY_FORWARD.md` (new *"Provider integrations & API —
ACTIVE THREAD"* section; manual-upload track → CLOSED), this handoff, and the
#681 epic body reconcile (#723 merged + Rowing-mint cancelled → §4 build wave is
next). No code, no tests touched.

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped (slice 5 / #767 closed) + "Next moves" tier-4 (this thread).
3. `CARRY_FORWARD.md` — *"Provider integrations & API — ACTIVE THREAD"* (the roadmap) + the manual-upload track (closed).
4. This handoff.
5. `specs/Provider_Inbound_Matrix_v2.md` + `specs/Provider_Data_Translation_Layer_Spec` (the authored mapping + the Wave-1 §4 table spec the build wave implements).
6. `./scripts/verify-handoff.sh` — anchor sweep.

Then pick up **#681 §4 build wave** (start with the table DDL + backfill plan → Andy ratify, Trigger #3).

## 7. Anchor table (Rule #10)

| Claim | Path / ref | Check |
|---|---|---|
| Manual-upload track closed | issue #767 | state `closed` / `completed`; slice 5 = PR #785 merged |
| Inbound mapping authored | `aidstation-sources/specs/Provider_Inbound_Matrix_v2.md` | exists; PR #723 merged; v1 in `archive/superseded-specs/` |
| Rowing mint reversed | #681 epic + matrix §6 | "Rowing stays bucket-3", no D-033, `discipline_canon.py` untouched |
| Live providers | `routes/` | `coros_ingest.py` + `polar_ingest.py` present (live); `strava.py`/`whoop.py`/`trainingpeaks.py`/`zwift.py`/`ride_with_gps.py` = stubs (webhook-only) |
| Raw store exists | DB / `routes/*_ingest.py` | `provider_raw_record` already written by polar/coros/whoop ingest |
| Thread pointer | `CURRENT_STATE.md` | "Next moves" tier 4 → "ACTIVE THREAD: provider integrations & API" |
| Thread roadmap | `CARRY_FORWARD.md` | "## Provider integrations & API — ACTIVE THREAD" section present |
| Epics open | #681 (`area:integrations`), #682 (`type:spec`) | both `open` |
