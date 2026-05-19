# Race Events Data Model — D-66 Design

**Version:** 1.0
**Date:** 2026-05-18
**Status:** Design decisions locked. Spec amendments paired this session: `Layer4_Spec.md` §3.4 + §4.5 (new `race_event_payload` arg + `kit_manifest_inputs_incomplete` post-D-66 activation note); `Athlete_Onboarding_Data_Spec_v5.md` §H.2 target-event step extended for race_format + multi-day branch + new §H.4 route-locale step. Implementation (DDL + RaceEventPayload pydantic model + onboarding/profile UI) follows in a subsequent PR; Layer 4 implementation Step 4e race-week-brief consumes this design as the unblocking contract.
**Backlog row:** D-66 (surfaced 2026-05-17 during Layer 4 Step 3 PR-C planning; design wave shipped 2026-05-18 this session).
**Track:** Race-week brief unblock. Step 4e of `Layer4_Spec.md` §14.3.4 implementation sequencing was queued behind D-66; this design wave is the unblocker.
**Affects:** Layer 1 (athlete profile reads target-race FK pointer); Layer 3B (reads race-event metadata for `mode='event'` periodization decisions); Layer 4 (`llm_layer4_race_week_brief` consumes `RaceEventPayload` as new positional arg per §3.4 amendment; rule `kit_manifest_inputs_incomplete` activates non-trivially); onboarding §H.2 target-event extension + new §H.4 route-locale step; profile UI (new `/profile?tab=race-events` tab); new PG migrations (`race_events`, `race_route_locales`, `race_route_locale_equipment` tables).
**Cross-references:**
- `Project_Backlog_v47.md` D-66 row (sketch) — extended this session.
- `Layer4_Spec.md` §3.4 (signature; amended this session) + §4.5 (race-week-brief preconditions) + §7.13 (`RaceWeekBrief` schema) + §7.14 (`RacePlan` schema) + §5.4 `kit_manifest_inputs_incomplete` rule (PR-C-stated always-warn pre-D-66; activates non-trivially post-D-66).
- `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` — consumer prompt body; ~955 lines; references kit_manifest items + RacePlan.segments + route locales throughout.
- `Athlete_Onboarding_Data_Spec_v5.md` §H.2 target-event step (extended this session) + new §H.4 route-locale step.
- `layer4/context.py` `RaceEventStub` (v1 placeholder; replaced by `RaceEventPayload` in subsequent implementation PR).

---

## 1. Purpose

Layer 4's race-week brief synthesizer (`llm_layer4_race_week_brief`, shipped as prompt body 2026-05-17 + queued as Step 4e implementation 2026-05-18) produces three coordinated artifacts: modified Taper-phase PlanSession overrides, a structured `RaceWeekBrief` (§7.13), and for multi-day events a structured `RacePlan` (§7.14). All three reference inputs the v1 app has no schema or UI for:

- **Race format** (`single_day` / `expedition_ar` / `stage_race` / `multi_day_ultra`) — drives whether RacePlan is produced + the contingency anchor table per `Layer4_RaceWeekBrief_v1.md` D6.
- **Distance, elevation gain** — referenced in pacing-strategy summary + segment pacing.
- **Race rules summary** — referenced in kit_manifest (mandatory gear inferences) + contingencies (rule-based DQ avoidance).
- **Mandatory gear text** — referenced in kit_manifest construction.
- **Route locale graph** — start → transition areas → aid stations → drop bag points → bivvy points → finish — load-bearing for `RacePlan.segments` chronological ordering, per-segment kit_manifest, and the validator rule `kit_manifest_inputs_incomplete` which is currently always-warn pre-D-66 because athletes have no UI to populate route-locale data.

Today's v1 schema has only `athlete.target_event_name TEXT` + `athlete.target_event_date DATE` columns. Layer 3B currently reads these alongside athlete-entered free-text fields to emit `mode='event'` periodization decisions; the same fields are insufficient for Layer 4's brief synthesis.

D-66 closes this gap by:

1. Adding three new PG tables (`race_events`, `race_route_locales`, `race_route_locale_equipment`) that capture the full race-event surface multi-day brief synthesis needs.
2. Defining a typed `RaceEventPayload` pydantic v2 model that replaces the v1 `RaceEventStub` placeholder in `layer4/context.py` and becomes a new positional arg on `llm_layer4_race_week_brief` per `Layer4_Spec.md` §3.4 amendment.
3. Extending onboarding §H.2's target-race step to capture race_format, distance, elevation, race-rules summary, mandatory gear (when multi-day); adding a new §H.4 route-locale step that follows §H.2 when the athlete picked a multi-day race_format.
4. Specifying a `/profile?tab=race-events` CRUD surface for post-onboarding edits (add new races, set target, edit route locales, dispose of past races).
5. Activating the always-warn `kit_manifest_inputs_incomplete` rule per `Layer4_Spec.md` §5.4 (currently decorative pre-D-66) by giving the validator real route-locale equipment data to reconcile against.

**Scope-bounded to v1 race-week brief unblock.** D-66 does NOT specify race-segment athlete-checkin shape (Layer 4 §7.14 explicitly leaves per-segment athlete-checkin to session 2 v2 work; D-66 ships the static input surface only); does NOT extend to Layer 5 (downstream supplemental outputs; Layer 5 will consume `RaceEventPayload` when speced); does NOT impose a structured mandatory-gear taxonomy (free-text per Andy 2026-05-18 Pick 3); does NOT support race re-routing mid-event (out of v1 scope).

---

## 2. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Scope of this design wave | **Full design wave: design doc + spec amendments + Layer 4 §3.4 input contract amendment + onboarding/profile UI design (described, not implemented).** Step 4e implementation deferred to subsequent PR; v5 onboarding implementation PR consumes the UI design when it lands. | Andy 2026-05-18 Pick 1. Single substantial session that produces a stable contract for Step 4e against; matches the Onboarding D-58/59/60/61 design-wave pattern. The "tight" alternative (DDL + Layer 4 contract only) would defer the data-entry surface to a later session — that's the gap that triggered D-66 in the first place. |
| 2 | Race-event count per athlete | **Multiple races in `race_events` table; one `is_target_event=true` at a time enforced via DB partial UNIQUE index.** Onboarding/profile UI lets athlete add upcoming races; "set as target" flips the flag. Layer 3B + 4 read the target row. | Andy 2026-05-18 Pick 5. Endurance athletes typically have 2–3 races on their calendar at once (an A race + a tuneup + maybe a future-year goal). The single-race alternative would force in-place editing when switching focus; the no-target-flag alternative would be ambiguous for co-target races. Single target row is unambiguous + cheap. |
| 3 | Gear + rules format | **Free-text** — `mandatory_gear_text TEXT NULL` + `race_rules_summary TEXT NULL` columns. LLM consumes raw text in the race-week-brief prompt + extracts items into `kit_manifest` per the existing D9 hybrid (layer0 canonical preferred + free-text fallback flagged with `data_gap` observation). | Andy 2026-05-18 Pick 3. Race directors publish PDFs / web pages; athletes paste/summarize. The structured alternative would force athlete transcription of every gear item into a structured form — significant friction for v1's single-athlete reality (Andy himself). Matches CLAUDE.md no-padding rule + push-to-production-as-we-go posture. v2 may add structured forward-pointer if the LLM's gear extraction proves unreliable. |
| 4 | Layer 4 input wiring | **New `race_event_payload: RaceEventPayload \| None = None` keyword arg on `llm_layer4_race_week_brief` §3.4 signature.** Required (non-None) for race-week-brief mode; Layer 3B continues to expose race_format/event_date/event_locale/time_to_event_weeks for periodization decisions; the new arg carries route-locale graph + mandatory_gear + race_rules_summary + distance/elevation. Clean separation: 3B = periodization-relevant; race_event_payload = brief-rendering-relevant. | Andy 2026-05-18 Pick 4. Trigger #5 fires; routed through this design wave's AskUserQuestion gate per the Step 4a/4b/c/4d precedent. The extend-Layer 3B alternative was rejected — 3B's responsibility is periodization; piling route-locale + mandatory_gear into 3B's payload conflates periodization-relevant data with brief-rendering data + makes the 3B cache invalidate on every route-locale edit. The read-from-DB-inside-synthesizer alternative breaks the pure-function-over-typed-payloads pattern Step 4a–4d locked in. |
| 5 | Per-route-locale equipment storage | **Dedicated `race_route_locale_equipment` table** (route_locale_id FK + equipment_name TEXT + quantity_text TEXT + notes TEXT). Does NOT FK to `locale_profiles` or `exercise_inventory`. Per Andy: "these are ephemeral and won't have any use outside of the race for which they were generated." | Andy 2026-05-18 Pick 6. Reuse-locale_profiles was rejected because race-route locales (aid stations, drop bag points, transition areas) are race-scoped + ephemeral — they don't belong in the athlete's saved locale cluster (which is the system the locale_profiles table is built for). The free-text alternative would leave rule-12 always-warn even post-D-66. Dedicated table is the middle path: structured per-locale equipment for validator reconciliation + zero pollution of the athlete's gym/home-locale list. |
| 6 | Data-entry posture | **Onboarding + Profile.** Onboarding §H.2 target-event step extends to capture race_format + (when multi-day) distance + elevation + rules + mandatory_gear; a new §H.4 route-locale step follows §H.2 only when race_format != 'single_day'. Profile retains full CRUD via a new `/profile?tab=race-events` tab. Athletes who haven't fully scoped their race at onboarding time (common for races 6+ months out) can complete fields later via the profile tab. | Andy 2026-05-18 Pick 2. The profile-only alternative was rejected — athletes who never visit /profile after onboarding get no race-week brief. The onboarding-required-for-multi-day alternative was rejected — over-eager; blocks athletes 6+ months out who legitimately don't know their drop-bag-point GPS yet. The Onboarding + Profile path captures the load-bearing race_format pick early (drives periodization in Layer 3B) while letting full route-locale entry happen on a relaxed timeline. |
| 7 | Layer 3B race-metadata source | **Layer 3B reads from `race_events WHERE user_id=? AND is_target_event=true LIMIT 1` (orchestrator-side; passed into Layer 3B as input).** When no target row exists, 3B emits `mode='open_ended'` per §6.1; v1 athlete.target_event_name + target_event_date free-text columns are deprecated (kept on the table for v1 app legacy compatibility; new athlete onboarding writes `race_events` instead). | Architect-pick; aligns with the strangler-fig sequencing in CLAUDE.md. The athlete-profile-extension alternative was rejected — it duplicates fields between athlete row and race_events; loud-over-silent prefers a single source of truth. Migration of existing v1 data (Andy's Pocket Gopher Extreme row) per §10 below. |
| 8 | Locale role enum | **Closed set: `start`, `transition_area`, `aid_station`, `drop_bag_point`, `bivvy`, `finish`, `other`.** Matches the backlog D-66 sketch. `other` is the relief valve for race-format-specific edges (e.g., crew checkpoints in stage races). | Architect-pick; matches what `Layer4_RaceWeekBrief_v1.md` D6 contingency anchor table + `RacePlan.segments` already consume. 7 values; closed; extensible to 8 in v2 if a real edge surfaces. |
| 9 | Distance + elevation nullable | **`distance_km NUMERIC NULL`, `total_elevation_gain_m NUMERIC NULL`** — nullable because athletes booking a race 8+ months out often don't have exact route specs yet; race directors publish the route closer to the date. Race-week-brief degrades gracefully when unset (pacing strategy emits `data_gap` observation; RacePlan segments rely on mile_marker where set). | Architect-pick; reflects athlete reality. Required-at-onboarding would block athletes who haven't picked the exact race variant (e.g., 50K vs 50mi). |
| 10 | Route-locale ordering | **`sequence_idx INT NOT NULL`; UNIQUE per `race_event_id`.** 1-indexed (1 = start). Profile UI lets athlete reorder via drag handles; orchestrator passes sequence_idx ordered list to Layer 4. Gaps allowed (sequence_idx 1, 2, 5, 8 valid — lets athlete leave room to insert later). | Architect-pick; mirrors `Layer4_Spec.md` §7.14 RacePlan.segments segment_index convention. Gaps-allowed avoids cascading reorder writes when athlete inserts a forgotten aid station between two existing rows. |

### 2.1 Sub-decisions deferred to implementation PR

These are explicit non-decisions held for the implementation PR (subsequent session). Each carries enough context for that session to make the call inline without re-routing through `/plan` mode.

- **Profile UI affordance for "set as target".** Likely a button or radio-button-style selector per race-event card; one click flips the flag + DB-side trigger ensures only one is_target_event=true per user. UX detail; not contract-bearing.
- **Onboarding §H.4 skip semantics.** Athlete picks multi-day race_format in §H.2 → §H.4 (route-locale step) is presented → athlete may either fill in 2+ route locales (start + finish minimum recommended) or skip with a "fill in later" affordance. Skip writes 0 route_locale rows; profile UI handles later additions. Validator rule `kit_manifest_inputs_incomplete` emits `data_gap` observation when route_locale count < 2 on race-week-brief invocation.
- **Mapbox anchoring on race_route_locales.** Optional `lat NUMERIC NULL`, `lng NUMERIC NULL`, `mapbox_id TEXT NULL` columns per §3.2 — athlete may anchor a route locale via Mapbox search (same flow as `locale_profiles`) for GPX export / map rendering downstream. v1 doesn't consume the coordinates in Layer 4 synthesis (the race-week-brief prompt body doesn't reference GPS); they're carried as data-payload columns for v2 map-rendering surfaces.
- **`route_locale.notes TEXT NULL` content.** Free-text; LLM consumes verbatim in prompt. Athletes describe terrain/access details ("crew can drive here", "boat launch only", "1 mile inland on Trail 7"). No schema enforcement.

---

## 3. Schema additions

Three new PG tables. All write `created_at TIMESTAMPTZ DEFAULT NOW()`, `updated_at TIMESTAMPTZ` per v5 convention. All migrations land in `init_db.py` `_PG_MIGRATIONS` with `IF NOT EXISTS` guards.

### 3.1 `race_events` table

```sql
CREATE TABLE IF NOT EXISTS race_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    event_date DATE NOT NULL,
    race_format TEXT NOT NULL CHECK (race_format IN ('single_day', 'expedition_ar', 'stage_race', 'multi_day_ultra')),
    distance_km NUMERIC NULL,
    total_elevation_gain_m NUMERIC NULL,
    race_rules_summary TEXT NULL,
    mandatory_gear_text TEXT NULL,
    event_locale_id BIGINT NULL REFERENCES locale_profiles(id) ON DELETE SET NULL,
    is_target_event BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT NULL,
    etl_version_set JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS race_events_user_target_uidx
    ON race_events (user_id) WHERE is_target_event = TRUE;

CREATE INDEX IF NOT EXISTS race_events_user_date_idx
    ON race_events (user_id, event_date);
```

**Columns:**
- `id` — PK.
- `user_id` — FK to users (athlete owning the row).
- `name` — race name as published by race director (e.g., "Pocket Gopher Extreme 2026").
- `event_date` — race day (first day for multi-day events).
- `race_format` — closed 4-element enum per `Layer4_Spec.md` §7.13. `single_day` covers marathons, 50K trail, single-day adventure races, single-day ultras up to 24h. `expedition_ar` covers multi-day adventure races (Andy's Pocket Gopher Extreme 2026 lands here). `stage_race` covers multi-day races with daily restarts (Tour de France-style; trail-running stage races). `multi_day_ultra` covers continuous ultras spanning 36–72h+ that aren't adventure races (e.g., Bigfoot 200, Tor des Géants).
- `distance_km` — total race distance in kilometers; NULL when athlete hasn't picked variant yet OR race director hasn't published route.
- `total_elevation_gain_m` — total cumulative elevation gain in meters; NULL conditions same as `distance_km`.
- `race_rules_summary` — free-text athlete-pasted/summarized race rules (mandatory checkpoints, time cuts, support rules, gear inspections); LLM consumes verbatim.
- `mandatory_gear_text` — free-text athlete-pasted/summarized mandatory gear list; LLM consumes verbatim + extracts to `RaceWeekBrief.kit_manifest` per existing race-week-brief D9.
- `event_locale_id` — FK to `locale_profiles` for the race finish/HQ (used by Layer 4 §4.5 row 6 `event_locale_resolves`). NULL allowed for races without an athlete-saved finish locale; brief degrades by treating event_locale as text-only.
- `is_target_event` — boolean; exactly one row per user has TRUE at a time per the partial UNIQUE index. Drives Layer 3B's read.
- `notes` — free-text athlete notes about the race (training context, travel logistics, family attending, etc.).
- `etl_version_set` — JSONB pin per existing convention (race_events_v1 entry + any external feeds linked).
- `created_at` / `updated_at` — timestamps.

**`event_locale_id` FK note:** Race finish locales are typically race-specific (finish line at a town center, expedition AR finish at a remote campground). Athletes may or may not have an existing `locale_profiles` row for the location; if they do, FK it; if they don't, leave NULL + the brief synthesizer treats `event_locale` as the text-only event name. Difference from §3.3 race_route_locale_equipment which is always race-scoped: `event_locale_id` is optionally cross-referenced to the broader locale system because the race finish/HQ might also serve as a regular training locale for the athlete (e.g., Pocket Gopher finishes near Nerstrand which Andy may visit for other training).

### 3.2 `race_route_locales` table

```sql
CREATE TABLE IF NOT EXISTS race_route_locales (
    id BIGSERIAL PRIMARY KEY,
    race_event_id BIGINT NOT NULL REFERENCES race_events(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN (
        'start', 'transition_area', 'aid_station', 'drop_bag_point',
        'bivvy', 'finish', 'other'
    )),
    sequence_idx INT NOT NULL,
    name TEXT NOT NULL,
    mile_marker NUMERIC NULL,
    lat NUMERIC NULL,
    lng NUMERIC NULL,
    mapbox_id TEXT NULL,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (race_event_id, sequence_idx)
);

CREATE INDEX IF NOT EXISTS race_route_locales_race_seq_idx
    ON race_route_locales (race_event_id, sequence_idx);
```

**Columns:**
- `id` — PK.
- `race_event_id` — FK to race_events; CASCADE delete (deleting a race deletes its route).
- `role` — closed 7-element enum per Decision 8.
- `sequence_idx` — 1-indexed ordering; UNIQUE per race_event_id (no two route locales at the same index); gaps allowed.
- `name` — free-text locale name as known to the athlete ("Aid Station 3", "TA1 — Lake Mary Trailhead", "Drop bag at the swim entry").
- `mile_marker` — race-distance offset in miles from start; NULL when athlete doesn't know yet or race-director hasn't published. Used by `RacePlan.segments` ordering when distance_km on race_events is also known.
- `lat` / `lng` / `mapbox_id` — optional Mapbox anchoring for downstream map/GPX surfaces (v1 doesn't consume in Layer 4 synthesis per §2.1 sub-decision).
- `notes` — free-text per-route-locale notes (terrain, crew-access rules, mandatory-gear-check-here flag, water-availability).
- `created_at` / `updated_at` — timestamps.

**Single-day events** typically have 1–2 route locales (start + finish) or 0 (athlete fills in nothing; brief synthesizes a single-segment pacing strategy). **Multi-day events** typically have 5–15 route locales (start + 2–5 TAs + 2–5 aid stations + 1–3 drop bags + finish). The `RacePlan.segments` length cap of 13 per `Layer4_Spec.md` §7.14 line 707 maps to the multi-day case — segments derive from adjacent route-locale pairs (a segment goes from one locale to the next), so 13 segments means up to 14 route locales. Defensive validator schema cap aligns.

### 3.3 `race_route_locale_equipment` table

```sql
CREATE TABLE IF NOT EXISTS race_route_locale_equipment (
    id BIGSERIAL PRIMARY KEY,
    race_route_locale_id BIGINT NOT NULL REFERENCES race_route_locales(id) ON DELETE CASCADE,
    equipment_name TEXT NOT NULL,
    quantity_text TEXT NULL,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS race_route_locale_equipment_locale_idx
    ON race_route_locale_equipment (race_route_locale_id);
```

**Columns:**
- `id` — PK.
- `race_route_locale_id` — FK to race_route_locales; CASCADE delete.
- `equipment_name` — free-text equipment item name ("6L water cache", "spare batteries — 4× AAA", "dry socks + base layer", "first-aid kit"). Free-text per Decision 5 — race-route equipment doesn't reconcile against layer0 `exercise_inventory` (gym-oriented) or any structured registry.
- `quantity_text` — optional free-text quantity / measure ("6 liters", "2 pair", "1 charged"). Free-text not numeric because units vary across items.
- `notes` — optional free-text caveats ("for the 4pm leg only", "shared with team", "pre-position by crew Friday").
- `created_at` / `updated_at` — timestamps.

**Layer 4 consumption shape:** synthesizer renders all race_route_locale_equipment rows for a given race_event_id grouped by route locale (sequence_idx ordered) into the `route_locales` block of the prompt body. Validator rule `kit_manifest_inputs_incomplete` activates non-trivially: per-route-locale equipment count is non-zero on at least one route locale for the kit-manifest to be reconcilable; rule fires `data_gap` warning otherwise. The PR-C spec §5.4 line referring to "athletes have no UI to populate route-locale equipment_overrides" becomes historical post-D-66; the always-warn annotation is retired in the paired `Layer4_Spec.md` amendment.

### 3.4 athlete-row deprecation note

The existing v1 columns `athlete.target_event_name TEXT` + `athlete.target_event_date DATE` are kept on the row for legacy/migration purposes (existing PG rows aren't dropped; new INSERT paths can leave them NULL) but become **deprecated**. New athlete onboarding writes to `race_events`; existing athletes are migrated per §10. Layer 3B's `mode='event'` decision reads from `race_events WHERE is_target_event=true` (orchestrator-side); the athlete-row columns are no longer authoritative.

A future cleanup PR can drop the columns once all v1 athlete rows have been migrated; until then they're forward-compatible (NULL when race_events row exists; populated when the legacy onboarding path was used).

---

## 4. `RaceEventPayload` typed contract

Replaces the v1 `RaceEventStub` placeholder in `layer4/context.py`. Mirrors the PR-D context-schemas convention: pydantic v2 `BaseModel` with `extra='forbid'`; bounds enforced at leaf-model level; JSON round-trip via `model_dump_json` / `model_validate_json` round-trips cleanly.

### 4.1 Pydantic model shape

```python
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

RaceFormat = Literal['single_day', 'expedition_ar', 'stage_race', 'multi_day_ultra']
RouteLocaleRole = Literal[
    'start', 'transition_area', 'aid_station',
    'drop_bag_point', 'bivvy', 'finish', 'other'
]


class RouteLocaleEquipment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    equipment_name: str = Field(..., min_length=1, max_length=160)
    quantity_text: str | None = Field(None, max_length=80)
    notes: str | None = Field(None, max_length=400)


class RouteLocale(BaseModel):
    model_config = ConfigDict(extra='forbid')
    route_locale_id: int  # FK back to race_route_locales(id)
    role: RouteLocaleRole
    sequence_idx: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=160)
    mile_marker: Decimal | None = Field(None, ge=0)
    lat: Decimal | None = None
    lng: Decimal | None = None
    mapbox_id: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=800)
    equipment: list[RouteLocaleEquipment] = Field(default_factory=list)


class RaceEventPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    race_event_id: int
    user_id: int
    name: str = Field(..., min_length=1, max_length=200)
    event_date: date
    race_format: RaceFormat
    distance_km: Decimal | None = Field(None, ge=0)
    total_elevation_gain_m: Decimal | None = Field(None, ge=0)
    race_rules_summary: str | None = Field(None, max_length=8000)
    mandatory_gear_text: str | None = Field(None, max_length=8000)
    event_locale_id: str | None = None    # slug per D-72 (2026-05-19)
    is_target_event: bool
    notes: str | None = Field(None, max_length=2000)
    route_locales: list[RouteLocale] = Field(default_factory=list)
```

### 4.2 Structural invariants

Enforced via pydantic `model_validator(mode='after')`:

1. **Route-locale sequence_idx unique within payload.** Defensive idempotent of the DB UNIQUE constraint; catches model_construct bypass + tests that build payloads without going through DB.
2. **Route-locale sequence_idx sorted ascending.** payload's `route_locales` list is sorted by sequence_idx ascending; raises on out-of-order construction. Layer 4 synthesizer can iterate route_locales in order without re-sorting.
3. **First/last role anchors when route_locales non-empty.** If route_locales is non-empty, the lowest-sequence_idx entry has role `start` and the highest-sequence_idx entry has role `finish`. Single-day events that fill in start + finish only meet this trivially. Multi-day events that haven't completed onboarding §H.4 may have route_locales empty; the validator rule `kit_manifest_inputs_incomplete` catches this case + emits `data_gap`. Defensive — caller-side check at Layer 4 §4.5 row 7.
4. **Multi-day events require non-zero route_locales for validator-reconcilable kit_manifest.** Soft invariant — empty list is structurally legal (race-week-brief degrades with `data_gap`) but flagged via §4.5 row 7 precondition.

**D-72 type-alignment resolution (2026-05-19):** `RaceEventPayload.event_locale_id` is `str | None` (the locale slug — i.e., the TEXT half of the `locale_profiles` composite PK `(user_id, locale)`), aligning with `Layer2CPayload.locale_id: str` + `Layer3BPayload.event_locale_id: str | None` + the `dict[str, Layer2CPayload]` key contract in `layer2c_payloads` + `PlanSession.locale_id: str` + the slug-based cache-key formulas in `layer4/hashing.py`. The DB column `race_events.event_locale_id` stays `BIGINT REFERENCES locale_profiles(id) ON DELETE SET NULL` — the surrogate `id BIGSERIAL` added to `locale_profiles` 2026-05-18 is correct for that FK shape and is a pure DB-internal surrogate. The repo helper `race_events_repo.load_race_event_payload` issues a `LEFT JOIN locale_profiles lp ON lp.id = re.event_locale_id` to surface the slug at the typed-payload boundary; the surrogate id never crosses the typed contract. `list_athlete_race_events` + `get_race_event` + `create_race_event` + `update_race_event` (write/listing surfaces consumed by `routes/race_events.py` + `routes/onboarding.py` + the profile-tab edit form) keep working with the int FK because their consumer is the form-input chain (dropdown values are `locale_profiles.id`). D-72 row → ✅ Resolved.

### 4.3 Replace `RaceEventStub` placeholder

The v1 `layer4/context.py` carries `RaceEventStub` as a forward-pointer placeholder (per PR-D handoff). Implementation PR removes the stub + adds `RouteLocaleEquipment` + `RouteLocale` + `RaceEventPayload` (3 new types + 2 new Literal aliases) to `layer4/context.py`; re-exports added to `layer4/__init__.py`.

### 4.4 ValidatorContext extension

`ValidatorContext` (frozen dataclass in `layer4/validator.py`) currently carries `RaceEventStub | None`. Implementation PR extends to `RaceEventPayload | None` (same field name `race_event` — backwards-compatible). Validator rules `kit_manifest_inputs_incomplete` + `race_plan_segments_unordered` + `fueling_strategy_2e_tier_mismatch` + `contingency_anchor_category_missing` gain real input data to reconcile against; the rule bodies update to read `ctx.race_event.route_locales` instead of returning `[]`.

---

## 5. Layer 4 §3.4 amendment (paired this session)

### 5.1 Signature change

`Layer4_Spec.md` §3.4 `llm_layer4_race_week_brief` gains a new positional arg `race_event_payload: RaceEventPayload` (non-optional). Inserted between `layer3b_payload` (last existing positional arg before kwargs) and `prior_plan_session_window`:

```python
def llm_layer4_race_week_brief(
    user_id: int,
    layer1_payload: Layer1Payload,
    layer2a_payload: Layer2APayload,
    layer2b_payload: Layer2BPayload,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload,    # NEW D-66 amendment
    prior_plan_session_window: list[PlanSession],
    plan_version_id: int,
    etl_version_set: dict[str, str],
    *,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens: int = 6000,
    capped_retries: int = 2,
) -> Layer4Payload:
    ...
```

### 5.2 New parameter table row

| `race_event_payload` | `RaceEventPayload` | Orchestrator (read from `race_events WHERE user_id=? AND is_target_event=true`) | **Added 2026-05-18 (D-66 amendment).** Carries race-event surface load-bearing for `RaceWeekBrief.kit_manifest` (mandatory_gear_text + route_locale equipment), `RaceWeekBrief.contingencies` + `RacePlan.contingencies` (race_rules_summary + per-route-locale notes), `RacePlan.segments` (route_locales ordered by sequence_idx; adjacent pairs form segments), pacing-strategy summary (distance_km + total_elevation_gain_m). Required non-None per §4.5 row 8 (new precondition). Layer 3B continues to expose race_format/event_date/event_locale/time_to_event_weeks for periodization decisions; race_event_payload carries the brief-rendering-relevant surface. |

### 5.3 §4.5 precondition table extension

Two new precondition rows added to the §4.5 race-week-brief input validation table:

| `race_event_payload` non-None | `race_event_payload_missing` | **Added 2026-05-18 (D-66 amendment).** Required when `mode='race_week_brief'`. Orchestrator passes the typed RaceEventPayload built from `race_events` + `race_route_locales` + `race_route_locale_equipment` joined per §10. Severity: blocker. |
| `race_event_payload.event_date == layer3b_payload.event_date` | `race_event_date_mismatch_3b` | **Added 2026-05-18 (D-66 amendment).** Defensive consistency check — orchestrator passes both payloads; race-day shifts must propagate to both. Severity: blocker. |

The existing row 7 `kit_manifest_inputs_incomplete` precondition annotation is updated:

| Kit data prerequisites (soft) | `kit_manifest_inputs_incomplete` | When `race_format != 'single_day'`: at least one route locale (via `race_event_payload.route_locales[].equipment`) has equipment populated. **Soft warning** — does not raise; emits a `data_gap` notable_observation; kit_manifest synthesis degrades gracefully with free-text items. **D-66 activation note (2026-05-18 amendment):** pre-D-66 this rule always-warned because athletes had no UI to populate route-locale equipment; post-D-66 the warning fires only when the athlete legitimately hasn't filled in route-locale equipment (e.g., race-week brief auto-fires before athlete completes onboarding §H.4 route-locale step). |

### 5.4 Validator rule rebinding

The §5.4 rule `kit_manifest_inputs_incomplete` body changes from "pre-D-66 always-warn" to:
- Read `ctx.race_event.route_locales` (now `RaceEventPayload`, was `RaceEventStub | None`).
- If `ctx.race_event is None` OR `ctx.race_event.race_format == 'single_day'`: skip rule (returns []).
- If `len(ctx.race_event.route_locales) == 0`: emit `RuleFailure(severity='warning', code='kit_manifest_inputs_incomplete_no_route_locales')`.
- If all route_locales have empty `equipment`: emit `RuleFailure(severity='warning', code='kit_manifest_inputs_incomplete_no_route_locale_equipment')`.
- Otherwise (at least one route locale has equipment populated): pass.

Validator rule `race_plan_segments_unordered_*` body unchanged structurally but reads from `ctx.race_event.route_locales` ordered by sequence_idx (already enforced by RaceEventPayload's `model_validator`).

### 5.5 §7 schema additions (optional v2)

`Layer4_Spec.md` §7.13 `RaceWeekBrief` references `event_locale: str` — a single locale name. Post-D-66 the value can be filled from `race_event_payload.route_locales` (last entry with role='finish') OR from `race_event_payload.event_locale_id` resolved to the linked locale_profile's display name. v1 keeps the field as-is + leaves source resolution to the synthesizer prompt body's existing logic; no v2-amendment of the §7.13 schema this session.

---

## 6. Onboarding §H.2 target-event step extension

### 6.1 Existing v5 §H.2 target-event step shape

`Athlete_Onboarding_Data_Spec_v5.md` §H.2 target-event step currently captures (v5 paraphrase): event name (text), event date (date picker), discipline-mix free-text. The step is part of §H.2 "Athlete identity + target race + discipline mix" — load-bearing for Layer 3B's `mode='event'` vs `mode='open_ended'` decision.

### 6.2 D-66 extension (this session)

`Athlete_Onboarding_Data_Spec_v5.md` §H.2 target-event step extended to capture:
- **race_format** (required) — radio button or dropdown; 4 values per §3.1. Default: `single_day`.
- **distance_km** (optional; presented when race_format set) — numeric input; km units.
- **total_elevation_gain_m** (optional; presented when race_format set) — numeric input; meter units.
- **race_rules_summary** (optional; multi-line textarea; presented when race_format != 'single_day') — free-text paste field with placeholder text like "Paste or summarize the race rules from the race director's published guide. Time cuts, mandatory checkpoints, support rules, gear inspections.".
- **mandatory_gear_text** (optional; multi-line textarea; presented when race_format != 'single_day') — free-text paste field with placeholder text like "Paste or summarize the mandatory gear list. We'll use this to build your race-week kit manifest closer to the event.".

When race_format == 'single_day': only race_format radio is shown above the existing v5 fields; rules/gear/route-locale extensions hidden. When race_format != 'single_day': all extension fields shown + onboarding flow advances to new §H.4 route-locale step after §H.2 completes.

### 6.3 New §H.4 route-locale step (multi-day only)

New §H.4 section in `Athlete_Onboarding_Data_Spec_v5.md` titled **"Route locales (multi-day events only)"**. Shown only when race_format != 'single_day' was picked in §H.2. Captures:
- For each route locale: role (dropdown — 7 values), name (text), mile_marker (numeric, optional), notes (text, optional).
- For each route locale: 0..N equipment items (each: equipment_name TEXT required, quantity_text TEXT optional, notes TEXT optional).
- Sequence ordering: athlete-drag-handle reorder; UI assigns sequence_idx 1, 2, 3, … as the athlete saves.
- Mapbox anchoring (optional per-row): athlete can search Mapbox for the route locale's location, same flow as locale_profiles per PR18; sets lat/lng/mapbox_id.

Step is **skippable** ("I'll fill this in later") — the athlete may have a confirmed race date + race_format at onboarding time but not yet have the route published or planned. Profile UI handles later additions.

When skipped: 0 race_route_locales rows are written; the athlete sees a soft account_nudge similar to D-58's "no provider connected" 14-day nudge: "You picked a multi-day race. Add your race route locales when you have them to enable race-week brief generation."

### 6.4 Onboarding UI implementation note

Implementation PR will add the §H.2 extension fields as conditional renders within the existing target-race template + add a new `templates/onboarding/route_locales.html` for §H.4. `routes/onboarding.py` gains a `route_locales` view (GET/POST) + the existing `target_race` view's POST handler writes the new race_events row instead of (or in addition to) the athlete-row legacy columns.

The §H.4 step is presented after §H.2 and before whatever currently follows §H.2 in v5 (likely §B athlete state). v5 spec amendment surgical edit text: see §11.1 below.

---

## 7. Profile UI: `/profile?tab=race-events` tab

### 7.1 New tab

`templates/profile/edit.html` gains a "Race events" tab alongside the existing Athlete / Schedule tabs (latter per PR15). Tab renders:
- List of athlete's race_events ordered by event_date ascending. Each row shows: name, date, race_format, target-event badge if is_target_event=true, edit + delete buttons.
- "Add race" button → form for new race_event (same fields as onboarding §H.2 extension).
- Per-row "Set as target" affordance — radio-style; flipping unset triggers a confirm modal ("Setting [name] as your target race will trigger a plan refresh tomorrow morning.").

### 7.2 Edit form

Per-race edit form expanding to two sections:
- **Race details** — name, date, race_format, distance_km, total_elevation_gain_m, race_rules_summary, mandatory_gear_text, event_locale_id (dropdown of athlete's locale_profiles + "none" option), is_target_event, notes.
- **Route locales** (presented only when race_format != 'single_day') — ordered list with drag-reorder; per-row edit modal opens per-locale form with role + name + mile_marker + lat/lng/mapbox_id + notes + nested equipment-item list.

### 7.3 Route-locale CRUD

Per-route-locale CRUD operations:
- Add: open form, athlete fills in fields, save writes race_route_locales row + 0..N race_route_locale_equipment rows.
- Edit: same form pre-filled; save UPDATE.
- Delete: confirm modal ("Delete [name]? Equipment items for this locale will also be deleted."); CASCADE delete handles equipment rows.
- Reorder: drag-handle UI; save POST rewrites sequence_idx column for affected rows. Gaps allowed (no compacting).

### 7.4 Partial-update invalidation on race-event edit

Per the partial-update model in `Control_Spec_v8` §4: editing any field on a target race_event row invalidates Layer 3B (mode/event_date changes drive periodization) + Layer 4 (race-week-brief cache key includes race_event_payload hash). Adding/editing/deleting a route_locale row invalidates Layer 4 race-week-brief cache only (Layer 3B doesn't read route_locales). The orchestrator fires a T1 plan refresh on target-flag change + emits a race-week-brief cache invalidation event on route-locale edits.

This is a **new partial-update invalidation rule** per stop-and-ask trigger #7; routed through this design wave's AskUserQuestion gate per the trigger-#5 + trigger-#11 precedent.

---

## 8. Layer 3B integration

### 8.1 3B reads race_event row

Layer 3B's `mode='event'` decision currently reads `athlete.target_event_name` + `athlete.target_event_date`. Post-D-66, 3B reads from `race_events WHERE user_id=? AND is_target_event=true LIMIT 1`. Orchestrator (Layer 1 caller pre-3B) joins the row + passes it through into Layer 3B's input shape.

The fields 3B consumes:
- `race_format` — drives periodization mode choice (single_day → standard 50/30/15/5; multi_day_* → judgment based on event distance).
- `event_date` — drives time_to_event_weeks calculation.
- `event_locale_id` — links to locale_profiles for Layer 2C locale resolution.

The fields 3B does NOT consume (left to Layer 4 via `race_event_payload`):
- `route_locales` + equipment
- `mandatory_gear_text` + `race_rules_summary` + `distance_km` + `total_elevation_gain_m` + `notes`

### 8.2 3B output shape unchanged

`Layer3BPayload` shape per PR-D `layer4/context.py` is unchanged. The existing fields (`mode`, `event_date`, `event_locale_id`, `race_format`, `time_to_event_weeks`, `periodization_shape`) all remain — their input source moves from athlete-row to race_events row.

### 8.3 No-target case

When no race_events row has is_target_event=true (no race scheduled): 3B emits `mode='open_ended'` per §6.1 v1 default. Plan generation proceeds in open-ended mode (12-week default horizon per `Layer4_Spec.md` §6.1).

---

## 9. Invalidation rules (partial-update model)

Per `Control_Spec_v8` §4. Stop-and-ask trigger #7 fires on this section — invalidation rules surfaced via this design wave's AskUserQuestion gate are:

| Edit | Invalidates | Notes |
|---|---|---|
| `race_events.is_target_event` flip TRUE → FALSE | Layer 3B (mode flips event → open_ended); Layer 4 (plan_create + race_week_brief caches) | Athlete dispatches target to a different race. |
| `race_events.is_target_event` flip FALSE → TRUE on another row | Layer 3B (mode flips); Layer 4 (plan_create + race_week_brief caches) | Coupled with the above for atomic target switch (single transaction). |
| `race_events.event_date` change (target row) | Layer 3B (time_to_event_weeks recalculates; periodization_shape may shift); Layer 4 (plan_create + race_week_brief caches) | Race date moves. |
| `race_events.race_format` change (target row) | Layer 3B (periodization shape mode); Layer 4 (plan_create + race_week_brief caches; race_plan triggered/not triggered) | Athlete switches between event distances/formats. |
| `race_events.distance_km` / `total_elevation_gain_m` / `race_rules_summary` / `mandatory_gear_text` / `notes` change (target row) | Layer 4 (race_week_brief cache only) | Brief-rendering-relevant; doesn't affect periodization. |
| `race_events.event_locale_id` change (target row) | Layer 2C (locale resolution for event_locale); Layer 4 (race_week_brief cache) | Cascading per existing Layer 2C invalidation. |
| Any race_route_locales INSERT/UPDATE/DELETE on target race | Layer 4 (race_week_brief cache only) | Brief-rendering-relevant only. |
| Any race_route_locale_equipment INSERT/UPDATE/DELETE on target race | Layer 4 (race_week_brief cache only) | Kit-manifest content; same scope. |
| Any change on a non-target race_events row | None | Race not in scope of any active plan; no invalidation. |

These rules become forwarded into `Control_Spec_v8` as part of the v9 bump in the v5 onboarding implementation PR. This design doc captures them as the contract; not landed in Control_Spec this session (out of D-66 scope).

---

## 10. Migration of existing v1 data

Andy's current Pocket Gopher Extreme 2026 row in the athlete table needs to migrate to `race_events`. Migration script lands in implementation PR:

```python
# init_db.py _PG_MIGRATIONS append
def migrate_athlete_target_events_to_race_events(conn):
    """One-time migration of legacy athlete.target_event_* columns to race_events."""
    conn.execute("""
        INSERT INTO race_events
            (user_id, name, event_date, race_format, is_target_event, etl_version_set)
        SELECT
            user_id,
            target_event_name,
            target_event_date,
            'single_day',                 -- safe default; athlete updates via profile
            TRUE,
            '{"race_events_v1": "migration_from_athlete_row"}'::jsonb
        FROM athlete
        WHERE target_event_name IS NOT NULL
          AND target_event_date IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM race_events
              WHERE race_events.user_id = athlete.user_id
                AND race_events.is_target_event = TRUE
          );
    """)
```

The migration:
1. Inserts a `race_events` row for each athlete with a target_event_name + target_event_date.
2. Defaults race_format to `single_day` — Andy will update his Pocket Gopher row to `expedition_ar` via the profile UI; other test athletes (none currently) will see `single_day` as the safe initial value.
3. Sets is_target_event=true.
4. The athlete-row columns are left in place; future cleanup PR drops them once all rows have migrated cleanly.

### 10.1 Post-migration manual update for Andy's row

Andy will need to update his migrated Pocket Gopher Extreme 2026 row to:
- race_format = 'expedition_ar'
- distance_km = TBD (TBD via race director's published guide)
- total_elevation_gain_m = TBD
- race_rules_summary = (paste from race-director-published guide)
- mandatory_gear_text = (paste from race-director-published guide)
- route_locales (start + transition areas + aid stations + drop bags + finish per the actual race route)

This is a documentation-track follow-up post-implementation-PR, not a contract-bearing item.

---

## 11. Spec amendments paired this session

### 11.1 `Athlete_Onboarding_Data_Spec_v5.md` surgical edits

Surgical edits within v5 (per Rule #12 — v5 stays as the authoritative version since this is an extension, not a redesign):

1. **§H.2 target-event step expansion** — add race_format radio + conditional distance/elevation/rules/gear fields per §6.2 above. Note added inline: "Race format radio + conditional fields per D-66 amendment 2026-05-18."

2. **New §H.4** — entire new section after §J (or current last §) titled "Route locales (multi-day events only)" describing the §H.4 route-locale entry step per §6.3 above. Forward-pointer notes "Race-route locales per D-66 amendment 2026-05-18. Step skippable; profile UI handles later additions."

3. **§H.2.1 disclosure list** — add a new disclosure row for race-rules-summary acknowledgment ("I confirm the race rules I've pasted are from the official race director's published guide; AIDSTATION uses these to generate my race-week brief and accepts no responsibility for AI-misinterpretation of pasted text.") — soft disclosure; v5 §H.2.1 already lists ~5 disclosures so this is additive not restructuring.

Note that the v5 onboarding implementation PR is the substantive code consumer of these amendments. v5 spec stays v5 (extension, not redesign) per Rule #12 numeric-version-suffix rule.

### 11.2 `Layer4_Spec.md` surgical edits

Per §5 above:
1. §3.4 signature gains `race_event_payload: RaceEventPayload` positional arg.
2. §3.4 parameter table gains the corresponding row.
3. §4.5 precondition table gains two new rows (`race_event_payload_missing` + `race_event_date_mismatch_3b`).
4. §4.5 row 7 `kit_manifest_inputs_incomplete` annotation updated to reflect D-66 activation.

§7.13 + §7.14 schemas unchanged this session — the consumer-side fields (`event_locale`, `kit_manifest`, `segments`) read from the new `RaceEventPayload` via the synthesizer prompt body's existing logic; no schema amendment needed.

### 11.3 `Project_Backlog_v47.md` → `_v48.md` per Rule #12

- D-66 status flip 🟡 Deferred (design wave) → 🟢 **Design wave shipped 2026-05-18** + full sub-decisions captured.
- D-66 row narrative replaced with the picks above + reference to this design doc.
- File-revision-header bumped to v48 with full Step 4d carry-forward + this session's narrative.
- No new D-rows this session (D-66's sub-decisions all land inside this design; no new cross-layer scope surfaces).

---

## 12. Test scenarios

PSS-RE-prefix test scenarios for the implementation PR. Each maps to a specific D-66 surface; implementation PR will encode these as pytest cases against the new tables + the RaceEventPayload model.

### 12.1 Race event CRUD

- PSS-RE-01 — Insert race_events row with race_format='single_day'; expect is_target_event default FALSE; no route_locales required.
- PSS-RE-02 — Insert race_events row with race_format='expedition_ar', is_target_event=TRUE; expect partial UNIQUE index satisfied; only one row per user with this flag.
- PSS-RE-03 — Attempt to set is_target_event=TRUE on a second row for the same user; expect UNIQUE violation.
- PSS-RE-04 — Update event_date forward; expect Layer 3B + Layer 4 cache invalidation events.
- PSS-RE-05 — Delete a race_events row; expect CASCADE delete of all race_route_locales + race_route_locale_equipment for that race.
- PSS-RE-06 — Insert race_events row with all optional fields NULL except required name/date/race_format; expect success (graceful degradation per §9 Decision 9).

### 12.2 Route-locale CRUD

- PSS-RE-07 — Insert race_route_locale row at sequence_idx=1 for an existing race_events row; expect success.
- PSS-RE-08 — Insert second race_route_locale row at sequence_idx=1 for same race; expect UNIQUE violation.
- PSS-RE-09 — Insert race_route_locale rows at sequence_idx 1, 2, 5, 8 (gaps allowed); expect success.
- PSS-RE-10 — Update sequence_idx to a value taken by another row in same race; expect UNIQUE violation.
- PSS-RE-11 — Insert race_route_locale with role NOT IN closed enum; expect CHECK violation.
- PSS-RE-12 — Insert race_route_locale with mile_marker NULL; expect success (nullable per §3.2).
- PSS-RE-13 — Delete a race_route_locale; expect CASCADE delete of all race_route_locale_equipment for that locale.

### 12.3 RaceEventPayload pydantic validation

- PSS-RE-14 — Construct RaceEventPayload with route_locales empty list; expect success.
- PSS-RE-15 — Construct RaceEventPayload with route_locales non-empty + first sequence_idx=1 with role='start' + last with role='finish'; expect success.
- PSS-RE-16 — Construct RaceEventPayload with route_locales non-empty + first role != 'start'; expect validator error.
- PSS-RE-17 — Construct RaceEventPayload with route_locales out of sequence_idx order (idx 2 before idx 1); expect validator error.
- PSS-RE-18 — Construct RaceEventPayload with duplicate sequence_idx values; expect validator error.
- PSS-RE-19 — JSON round-trip RaceEventPayload via model_dump_json + model_validate_json; expect identical structure.
- PSS-RE-20 — Construct RaceEventPayload with extra field; expect extra='forbid' validator error.

### 12.4 Layer 4 §4.5 precondition activation

- PSS-RE-21 — Call `llm_layer4_race_week_brief` without race_event_payload; expect `Layer4InputError('race_event_payload_missing')`.
- PSS-RE-22 — Call with race_event_payload.event_date != layer3b_payload.event_date; expect `Layer4InputError('race_event_date_mismatch_3b')`.
- PSS-RE-23 — Call with race_format='expedition_ar' + route_locales empty; expect success + `Observation(category='data_gap', code='kit_manifest_inputs_incomplete_no_route_locales')`.
- PSS-RE-24 — Call with race_format='expedition_ar' + route_locales populated but all equipment lists empty; expect success + `Observation(category='data_gap', code='kit_manifest_inputs_incomplete_no_route_locale_equipment')`.
- PSS-RE-25 — Call with race_format='expedition_ar' + at least one route_locale has equipment populated; expect success + no kit_manifest data_gap observation.
- PSS-RE-26 — Call with race_format='single_day' + route_locales empty; expect success + no kit_manifest data_gap observation (rule skips per §5.4 mode-gating).

### 12.5 Onboarding flow

- PSS-RE-27 — Athlete picks race_format='single_day' in §H.2; expect §H.4 route-locale step skipped + onboarding proceeds to next section.
- PSS-RE-28 — Athlete picks race_format='expedition_ar' in §H.2; expect §H.4 route-locale step presented.
- PSS-RE-29 — Athlete completes §H.2 + skips §H.4; expect race_events row created + 0 race_route_locales rows + account_nudge emitted 14 days later.
- PSS-RE-30 — Athlete completes §H.2 + §H.4 with 5 route_locales; expect race_events row created + 5 race_route_locales rows + 0 race_route_locale_equipment rows (athlete left equipment blank).

### 12.6 Migration

- PSS-RE-31 — Run migration against athlete row with target_event_name='X' + target_event_date='Y'; expect race_events row inserted with name='X' + event_date='Y' + race_format='single_day' + is_target_event=TRUE.
- PSS-RE-32 — Run migration twice; expect second run inserts 0 rows (WHERE NOT EXISTS guard).
- PSS-RE-33 — Run migration against athlete row with both columns NULL; expect 0 race_events rows inserted (WHERE filter).

---

## 13. Open items deferred to v2

- **Race-segment athlete-checkin shape.** `Layer4_Spec.md` §7.14 line 737 forward-pointer "session 2 may add per-segment athlete-checkin shape for post-race analysis"; D-66 covers static input surface only; downstream actual logging surface is v2 work.
- **Multi-race team coordination.** Layer 4.5 (Joint Session Coordinator) consumes RaceEventPayload when linked athletes' target_events are the same race. Outside D-66 scope; lands when team-features track activates per CLAUDE.md.
- **Structured mandatory_gear taxonomy.** Free-text per Decision 3. If the LLM's race-week-brief D9 hybrid extraction proves unreliable in production telemetry, v2 may layer a structured mandatory_gear_items: list[GearItem] alongside the free-text column.
- **Race-route GPX import.** When athletes have a GPX of their race route, future v2 surface can parse + auto-populate route_locales. v1 is athlete-typed-fields-only.
- **External race-event catalog.** v2 may consume race-director-published metadata via API (UltraSignup, RunSignup, Adventure Race series APIs) to auto-populate race_format + distance + elevation + rules + mandatory_gear. v1 is athlete-typed-fields-only; no external integration.
- **Race-day weather / forecast integration.** Race-week brief's pacing/contingency reasoning ideally consumes 7-day forecast for the event_locale; current `Layer4_RaceWeekBrief_v1.md` D6 references forecast availability in test scenario list but no schema slot for it. v2 design wave (D-XX) will spec a weather-feed integration.

---

## 14. Gut check

### What's right

- **The contract surfaces are tight + load-bearing.** RaceEventPayload's three nested models (RouteLocale + RouteLocaleEquipment + RaceEventPayload itself) mirror exactly what `Layer4_RaceWeekBrief_v1.md` consumes — no padding, no speculative fields.
- **Free-text gear + rules + notes match v1 reality.** Race directors don't publish in structured formats; forcing athletes to transcribe everything is friction. Free-text + LLM extraction is the right v1 cut.
- **Dedicated equipment table per Andy's pick is the right call.** Aid-station equipment is genuinely ephemeral; reusing locale_profiles would have leaked race-route into the locales list page.
- **Onboarding + Profile entry posture matches athlete reality.** Athletes booking races 6+ months out can't fully scope route + gear at onboarding time; profile-only would lose discoverability; onboarding-only would block. The skippable §H.4 is the right path.
- **Backwards compatibility on athlete-row deprecation is graceful.** Existing v1 athlete rows migrate cleanly; new onboarding writes race_events; the cleanup is decoupled from this design.

### Risks

- **Multi-day race onboarding friction is real.** Athletes who hit §H.4 may face a daunting form (7+ route locales, each with optional equipment). The skippable affordance is the relief valve but creates a new failure mode: athletes start §H.4, fill in 1–2 locales, abandon, then later don't return. Profile UI discoverability becomes load-bearing.
- **Free-text mandatory_gear + race_rules_summary is LLM-extraction-dependent.** Race-week-brief D9 hybrid (layer0 canonical preferred + free-text fallback with data_gap observation) is the existing fallback contract; LLM may misextract obscure gear items ("Petzl headlamp with 200 lumens AND backup batteries" parses cleanly; "Adventure-grade helmet certified to UIAA-106" may not). Mitigation: synthesize kit_manifest items WITH source-text quotes so athlete can self-verify.
- **`race_format` enum is closed to 4 values.** Hybrid events that don't cleanly fit (a 24h adventure race that's faster than `expedition_ar` but longer than `single_day`) will force athletes to pick the closest match. Closed enum was Andy's existing pick from `Layer4_Spec.md` §7.13; preserving consistency.
- **Layer 3B + Layer 4 cache-invalidation surface is wide.** Per §9 invalidation table, target-flag flips invalidate plan_create caches — significant compute cost on every "set as target" click. Mitigation: orchestrator fires T1 refresh first (cheap), then T3 if athlete confirms.
- **Migration safety on athlete-row defaulting to `single_day`.** Andy's row will migrate as `single_day` and Andy will need to manually update to `expedition_ar`. Until he does, Layer 3B emits single-day periodization for his Pocket Gopher prep — wrong for 2 weeks until he updates. Mitigation: post-migration documentation step in implementation PR's §5.0 checklist asks Andy to log in and update his row.

### Best argument against

The strongest case against D-66 as currently scoped is: **the schema is over-built for the v1 athlete (Andy)**. Andy is the only test athlete; he's training for one race; he can hand-type a kit list once. A v1-tight cut could ship just: `race_events.race_format` + `race_events.mandatory_gear_text` + `race_events.race_rules_summary` columns on the existing athlete table, with no separate tables, no route-locale graph, no equipment-per-locale storage. The race-week brief would degrade to whole-race kit + free-text route notes.

**Counter:** the route-locale graph is load-bearing for `RacePlan.segments` chronological ordering, kit_manifest per-locale items, and the validator rule `kit_manifest_inputs_incomplete`. Without it, the rule stays decorative (always-warn) and the RacePlan synthesizer can't produce segment-level kit decisions — which is the primary value-add of race-week-brief for multi-day events (the differentiator from a generic "here's your race-week strategy" surface). Shipping a stripped v1 would force a v2 redesign with non-trivial migration cost.

The chosen scope is the minimum needed to make race-week brief deliver multi-day value. v2 can extend (structured mandatory_gear; GPX import; weather feed); v1 contracts hold.

---

## 15. Forward pointers / next session

### Next forward move

**Layer 4 implementation Step 4e — `llm_layer4_race_week_brief` D-66 caller integration.** Consumes the now-defined RaceEventPayload contract + the already-shipped `Layer4_RaceWeekBrief_v1.md` prompt body. ~3-4 files projected:

1. New `layer4/race_week_brief.py` (~700 lines) — driver + input validation + tool schema builder + prompt rendering + capped-retry loop.
2. `layer4/context.py` modifications — replace `RaceEventStub` with `RouteLocaleEquipment` + `RouteLocale` + `RaceEventPayload`.
3. `layer4/validator.py` modifications — rebind `kit_manifest_inputs_incomplete` rule body from always-warn to D-66-active logic per §5.4 above.
4. `layer4/__init__.py` re-exports (3–4 new symbols).
5. `tests/test_layer4_race_week_brief.py` — ~40 tests covering input validation + happy-path + capped retry + observation emission + Layer4Payload composition + RaceEventPayload pydantic validation.

**Subsequent moves:**
- v5 onboarding implementation PR consumes §H.2 + §H.4 extensions + profile UI per §6 + §7 above.
- Migration script per §10 lands in implementation PR.
- Step 4f `plan_create` Pattern A orchestration — heaviest remaining; per-phase synthesizer + seam reviewer wiring.

### Carry-forward for next session

None mechanically-spec'd. Step 4e implementation is self-contained against this design doc + the existing `Layer4_RaceWeekBrief_v1.md` prompt body. Trigger #5 fires on the v1 RaceEventStub → RaceEventPayload type swap in `layer4/context.py` — routed via implementation-session AskUserQuestion gate per the Step 4a/4b/c/4d precedent.

---

**End of D-66 design.**
