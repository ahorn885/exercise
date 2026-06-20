# Provider Outbound — structured-workout export (#681 Wave 3b) — Build Design v1

**Scope:** turn a Layer-4 `PlanSession` (kind=`cardio`) into a structured workout an athlete can take to a destination platform. Two delivery channels, opposite mechanics:

- **Zwift** — no push API. Outbound = a **`.zwo` XML file** the athlete downloads and drops into `Documents/Zwift/Workouts/`. No OAuth, no idempotency tracking.
- **TrainingPeaks** — real bidirectional partner API (`POST /v2/workouts/plan` with a `Structure`), but **partner-access-gated** (no personal use, reportedly paused to new partners — matrix §11.1). The connector is buildable but **untestable / un-go-liveable until partner access opens** (Andy's explicit call 2026-06-20: build it anyway, accept speculative).

Mappings are transcribed from `specs/Provider_Inbound_Matrix_v2.md` §11 + `specs/Provider_Data_Translation_Layer_Spec_v1.md` §3 (two-tier outbound) / §4.4 (`provider_outbound_ref`). This is the build design for those, not a re-derivation.

> **Why this design exists (scope honesty, recorded):** both named providers are gated and `provider_outbound_ref` has no consumer until a push connector lands. The only *unblocked* piece is the Zwift `.zwo` file export. Andy ratified building the full literal Wave 3b regardless (incl. the speculative TP connector + the table). Slicing isolates the real/testable core (Slice 1) from the gated connector (Slice 2).

---

## 1. Input data model (what we serialize from)

`plan_sessions.payload_json` holds a full `PlanSession.model_dump(mode='json')` (`layer4/payload.py`). Relevant fields:

- `kind` ∈ {cardio, strength, rest, recovery} — **only `cardio` is exportable** (a structured-workout file is meaningless for strength/rest/recovery; reject the rest with a clear message).
- `discipline_id` (fine layer0 D-id, nullable) → coarse via `provider_cardio_resolve.DISCIPLINE_TO_PLAN_SPORT` (running/cycling/swimming/hiking).
- `cardio_blocks: list[CardioBlock]`, each:
  - `block_kind` ∈ {warmup, main_set, cooldown, interval_set, transition}
  - `duration_min: int`
  - `intensity_zone` ∈ {Z1…Z5, mixed}
  - `intensity_target` — structured union (PowerTarget watts / HRTarget bpm / PaceTarget / RPETarget / …). Present but **absolute**; not a %.
  - interval fields (`repetitions`, `rest_between_min`, `rest_intensity_zone`) — set iff `block_kind == interval_set`.

**Anchor decision (load-bearing).** TP `Structure` and Zwift `.zwo` both take **percentages of a threshold**, never absolute watts/bpm. The athlete's FTP/LTHR are **not reliably available** (`profile_extractors.extract_cycling_ftp_w_*` / `extract_lactate_threshold_hr_bpm_*` are all `_EMPTY` stubs today). Therefore **the zone (`intensity_zone`) is the primary, reliable serialization input** — we map Z1–Z5 → a %-of-threshold band via fixed tables (§2). The absolute `intensity_target` is **not** used for the % (we can't normalize it without the athlete anchor); it could refine later if/when FTP/LTHR ingest lands (open item §7).

`block_kind == 'mixed'` zone and `transition` blocks: see §3 edge cases.

---

## 2. Zone → %-threshold tables (the coaching-meaningful decision)

Standard 5-zone models, encoded as `(low, high)` fractions. Single-value targets use the **midpoint**; ramps (warmup/cooldown) use the band. **Tunable module constants; verify-owed** — zone models vary by source; these are documented defaults, not gospel (kept as constants, not config knobs — simplicity-first; one edit to retune).

**Power (%FTP)** — British-Cycling / common-trainer 5-zone (Coggan 7→5 collapse):

| Zone | %FTP band | midpoint |
|---|---|---|
| Z1 (recovery) | 0.50–0.55 | 0.53 |
| Z2 (endurance) | 0.56–0.75 | 0.65 |
| Z3 (tempo) | 0.76–0.90 | 0.83 |
| Z4 (threshold) | 0.91–1.05 | 0.98 |
| Z5 (VO2max) | 1.06–1.20 | 1.13 |

**HR (%LTHR)** — Friel 5-zone:

| Zone | %LTHR band | midpoint |
|---|---|---|
| Z1 | 0.70–0.85 | 0.80 |
| Z2 | 0.85–0.89 | 0.87 |
| Z3 | 0.90–0.94 | 0.92 |
| Z4 | 0.95–0.99 | 0.97 |
| Z5 | 1.00–1.06 | 1.03 |

`mixed` → fall back to the Z2 band (steady aerobic) and tag the block instruction; no crash.

---

## 3. Canonical step model (shared intermediate)

`session_to_steps(session: dict) -> list[Step]` flattens `cardio_blocks` into a provider-agnostic list. One `Step` = `(kind, duration_s, zone, reps, rest_duration_s, rest_zone, label)`:

- non-interval block → one Step (`kind` = block_kind, `duration_s = duration_min*60`).
- `interval_set` → one Step with `reps`, `duration_s` = work-rep seconds, `rest_duration_s`, `rest_zone`. Serializers expand reps into the provider's repeat construct.
- `transition` → emitted as a steady Step at its own zone (both serializers lack a native "transition" → it serializes as steady); kept so total duration is faithful.

Both serializers consume `Step`s; the zone→% lookup (§2) happens **in the serializer** (Zwift uses %FTP, TP can use %FTP for bike / %LTHR otherwise), not in the step model.

---

## 4. Zwift `.zwo` serializer (`to_zwo`)

XML `<workout_file>` (matrix §11.2). `sportType` from coarse discipline: **cycling→`bike`, running→`run`**; any other discipline → **not exportable to Zwift** (raise a clear `ValueError`, surfaced as a 400). `Power` = **fraction of FTP** (the §2 power band).

Block mapping:
- warmup → `<Warmup Duration=s PowerLow= PowerHigh=>` (band, ramp up)
- cooldown → `<Cooldown Duration=s PowerLow= PowerHigh=>` (band, ramp down)
- main_set / transition → `<SteadyState Duration=s Power=midpoint>`
- interval_set → `<IntervalsT Repeat=reps OnDuration=s OffDuration=s OnPower=work-mid OffPower=rest-mid>`

`<name>` = session discipline + date; `<description>` = a one-line provenance + the zone→%FTP caveat. UTF-8, no external deps (stdlib `xml.etree` or hand-rolled — hand-rolled for attribute-order stability in tests).

## 5. TrainingPeaks `Structure` serializer (`to_tp_structure`) — Slice 2 consumer

Returns the `Structure` dict for `POST /v2/workouts/plan` (matrix §11.1 outbound). `Step`/`Repetition`; `Length.Unit='Second'`; `IntensityClass` per block_kind (`WarmUp`/`Active`/`CoolDown`/`Rest`); `IntensityTarget.Unit` = **`PercentOfFtp`** when coarse=cycling, else **`PercentOfThresholdHr`** (the §2 LTHR band). `interval_set` → a `Repetition` wrapping work+rest `Step`s. Built in Slice 1 (pure fn, fully unit-tested); **dispatched** in Slice 2.

---

## 6. `provider_outbound_ref` table (idempotent push ledger — §4.4)

DDL verbatim from `ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` §3.3 into `init_db.py` `_TABLES`:

```sql
CREATE TABLE IF NOT EXISTS provider_outbound_ref (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER REFERENCES users(id),
    provider            TEXT NOT NULL,
    session_id          TEXT,
    external_id         TEXT,
    tier                SMALLINT,
    pushed_payload_hash TEXT,
    status              TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, provider, session_id)
)
```

Public-schema (`_TABLES` auto-create on deploy; matrix design D-D). **No consumer in Slice 1** — Zwift is a file download with no external id to track. First writer = the Slice-2 TP push (`pushed_payload_hash` → upsert-on-change vs no-op; `status` ∈ pushed/updated/deleted/error). Created in Slice 1 so the schema lands as one unit (Andy ratified the otherwise-speculative empty table).

---

## 7. Slicing

| Slice | Scope | Substantive files | Gate |
|---|---|---|---|
| **1 (this build)** | `provider_outbound_ref` table; `routes/outbound_workout.py` serializer core (`session_to_steps` + `to_zwo` + `to_tp_structure` + zone tables); Zwift `.zwo` **download route** in `routes/zwift.py`; tests | `init_db.py`, `routes/outbound_workout.py`, `routes/zwift.py` (+ tests) | Fully testable in-container; no provider access needed |
| **1b (follow-on)** | surface the `.zwo` download button on the plan/session view | plan template + view | small; deferred to keep Slice 1 tight |
| **2 (gated)** | TrainingPeaks OAuth connect (`oauth_start`/`oauth_callback`) + `POST /v2/workouts/plan` dispatch + `provider_outbound_ref` idempotency, reusing `to_tp_structure`; hub: TP → Connect | `routes/trainingpeaks.py`, `routes/profile.py`, `routes/connections.py` | **Untestable against live TP** (partner-gated); mocked tests only; verify-owed at access-grant |

## 8. Open items
- **FTP/LTHR ingest** is stubbed → the export is zone-anchored only. When a provider lands real `cycling_ftp_w` / `lactate_threshold_hr_bpm`, the absolute `intensity_target` could refine the % (or we emit absolute watts where the platform allows). Not now.
- Zone→% tables are documented defaults (§2), tunable module constants, verify-owed.
- Zwift only does bike/run; swim/hiking/other cardio sessions are non-exportable to Zwift (TP's enum is broader).

## 9. Tests (Slice 1)
- `session_to_steps`: interval_set expands reps + rest; non-cardio raises; transition → Z1 step; durations →seconds.
- `to_zwo`: bike + run sportType; warmup/cooldown ramp bands; SteadyState midpoint; IntervalsT repeat/on/off; non-bike/run discipline raises; well-formed XML.
- `to_tp_structure`: PercentOfFtp for cycling, PercentOfThresholdHr otherwise; Repetition for intervals; Length.Unit=Second.
- Zwift route: cardio session → 200 + `application/octet-stream` `.zwo` body + filename; strength session → 400; unknown session → 404; login required.
- Full suite green.

## 10. Gut check
- **Risk:** zone→% midpoints are a coaching judgment; a too-aggressive Z4/Z5 midpoint mis-prescribes an indoor session. Mitigated by documented standard models + env-override + verify-owed flag.
- **What might be missing:** the value to *Andy's* training is thin (his race is outdoor trail/hike/MTB/packraft; Zwift = indoor bike/run). The TP connector is dead weight until partner access opens. Both accepted explicitly.
- **Best argument against:** building the gated TP connector + empty table now is speculative surface CLAUDE.md normally rejects; the lean path was Zwift-export-only. Andy chose full scope; Slice 2 is isolated so it doesn't pollute the shippable Slice 1.
