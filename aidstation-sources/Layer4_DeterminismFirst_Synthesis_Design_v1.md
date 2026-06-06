# Layer 4 Determinism-First Synthesis — Design Spec v1

**Status:** APPROVED (Andy, 2026-06-06). Slice 2a + 2b + 2c shipped; 2d follows per §10. Slice 2c cardio-routing pulled out → 2c.2 follow-up (depends on layer0 vocab work).
**Date:** 2026-06-06
**Track:** 2 of 3 (#429, parent epic #427). Track 1 (Locations Consolidation, #428) shipped (PRs #426 + #431). Track 3 (D-52 catalog migration, #430) parallel/after.
**Closes / addresses:** #335 #336 #338 #339 #341 #337 (the plan-gen quality issues #429 says Track 2 subsumes).

---

## 1. Purpose

Move feasibility OUT of the LLM. Today's synthesizer makes every decision — what exercise, how many sessions, what intensity, which day is rest, which locale — through prose reasoning, then the validator rejects what doesn't fit, then the loop retries until the budget exhausts. The result is **fragile** (a single fumble can kill an otherwise-valid plan) and **low-quality** (loads are made up, weeks drift off the periodization curve, sessions land at no specific place).

**Goal:** deterministic stages produce a feasible, pre-computed input set; the LLM organizes the week from a ranked pool, never failing on a feasibility class. The validator's feasibility rules become defensive asserts/warnings, not retry-driving blockers.

This is the second half of Andy's 2026-06-05 redesign decision. Track 1 made the equipment vocabulary canonical; Track 2 makes the synthesis structurally feasible.

## 2. Locked decisions (Andy, 2026-06-06)

1. **Tool-schema enum on `exercise_id`** (D1). Cluster-union pool, scoped per block. The LLM can't write an `exercise_id` outside the resolved feasible set. Deletes the `equipment_unavailable` validator rule entirely.

2. **Deterministic session-count grid** (D2). Per-discipline per-week counts derived from `phase_load_allocation` % × `phase_load_weekly_totals` hours ÷ typical session hours. LLM places (which day, when of day) only.
   - **Maintenance-cadence rule:** if `count_per_week < 0.5`, schedule one session every `ceil(1 / count_per_week)` weeks instead of rounding to 1/wk. (A discipline at 3% of `phase_load` → ~1 session every 3–4 weeks, not weekly. Honest to race share; prevents over-allocation of small-share disciplines.)

3. **AR / continuous_multi_day extensions** (D2 sub):
   - **Race-sim long days:** when `race_format = continuous_multi_day`, the grid reserves 1× race-sim day per Peak week and 1× in Taper-1. Multi-discipline, 4–8h, weekend-anchored by default.
   - **Brick / transition pairing:** the grid can mark two same-day sessions as paired (e.g., MTB → trail run) via a shared `coaching_intent`. No new payload field; pair detection is metadata on the existing `session_index_in_day` slots.
   - Nav-as-modifier and skill-capability-bias deferred (3 / 4 from the D2 sub-options; cleaner to ship the grid first and tune via real plan output).

4. **Phase-dependent intensity split** (D3). Polarized defaults per phase (cite Seiler):
   - Base: 90% easy / 10% hard
   - Build: 80% easy / 20% hard
   - Peak: 70% easy / 30% hard
   - Taper: 90% easy / 10% hard
   - Per-discipline ratio tuning deferred to v1.1. Edge-case risk handled via coach-note overrides where needed.

5. **Deterministic rest detection** (D4). Phase-dependent **expected** rest count (not required); a deterministic post-check counts actual rest days in the synthesized week and emits a `insufficient_rest` warning + coaching flag when the count is below expected. LLM keeps placement freedom; the deterministic layer monitors and surfaces. `daily_availability_windows` disabled days remain hard rest (schema invariant; already the case).

6. **Locale assignment process** (D5 + D6, Andy's reframe):
   1. LLM picks the ideal exercise set per session, **locale-agnostic**, from the cluster-union enum (§4).
   2. Deterministic: for each session, find the cluster locale where the **majority** of the ideal set fits (highest `equipment_required ⊆ effective_pool` coverage; ties → home; second tie → closest by `lat`/`lng`).
   3. Deterministic: assign that `locale_id` to the session.
   4. Deterministic substitution: any exercise from the ideal set that doesn't fit the chosen locale is swapped via the existing `_strength_pattern_match` infrastructure (movement-pattern overlap + matching `sport_priority` rank). Fall back to Tier-3 bodyweight proxy if no pattern-match candidate exists.
   5. LLM substitution only as a final fallback — pattern-match returns no candidate AND no Tier-3 proxy exists. **Dedicated small call, not a re-invocation of the big synthesizer.** Single-purpose tool: input = `(exercise_id, movement_patterns, sport_priority, locale.effective_pool, excluded_ids)`; output = single `substitute_exercise_id` bounded by an enum on the locale pool. Haiku-class model, no periodization context, no week framing. Cache key `(exercise_id, locale_id, excluded_ids_hash) → substitute_id` (stable, highly reusable across athletes/blocks). One extra round-trip only when truly stuck.

7. **rx_engine post-hoc wiring** (D7). Synthesizer emits `load_prescription` as advisory text. A deterministic post-step looks up `current_rx[(user_id, exercise_id)]` and rewrites the field with the precise rx (`"185 lbs × 5, RPE 7"` — weight + reps + RPE target, all three useful: weight = the actual load to put on the bar, RPE = how it should feel for autoregulation). **First-exposure exercises** (no `current_rx` row) get a **deterministic RPE-only template** keyed off the exercise's category (compound barbell: `"calibration set — pick a weight that feels RPE 6 for 8 reps; log to set baseline"`; DB / bodyweight / cable variants: analogous) + a `first_exposure` coaching flag. No LLM in the first-exposure path — the template is a lookup off the exercise's category, not creative work.

8. **Validator demotion sweep** (D8). Per-rule mapping in §8. Followed by a **quality-assurance audit** (deferred follow-up) once 3–4 plans have run on the new contract: review the warnings stream for false negatives, re-promote any rule whose demotion proved unsafe.

9. **PR slicing** (D9, D10). Four slices, shippable independently:
   - **2a:** D1 (tool-schema enum) + delete Rule 6a.
   - **2b:** D2 (session-count grid) + D3 (intensity split).
   - **2c:** D4 (rest placement) + D5 (locale assignment + substitution).
   - **2d:** D7 (rx_engine wiring) + the rest of the §8 validator sweep.
   - Ship 2a first; verify against a cold PGE plan; then 2b / 2c / 2d in order.

## 3. Determinism boundary

| Decision | Today | After Track 2 |
|---|---|---|
| Which exercises exist (catalog) | Layer 0 (deterministic) | unchanged |
| Which exercises are feasible (equipment, injury, capability) | Layer 2C + 2D filter; synthesizer picks freely; validator rejects | **2C/2D filter is authoritative; synth schema enum bounds the pick** |
| How many sessions per discipline per week | LLM (prose reasoning) | **Deterministic grid from `phase_load`** |
| Easy / moderate / hard ratio | LLM (per-session feel) | **Deterministic phase-dependent default; LLM places** |
| Rest days | LLM (modulo `daily_availability_windows`) | **Deterministic count + adjacency rule** |
| Session→locale | Synthesizer-implicit (no locale_id post-Track-1) | **Deterministic majority-fit + travel optimizer** |
| Exercise selection within a session | LLM | **LLM (the genuine synthesis question)** |
| Exercise loads / reps / sets | LLM (advisory; often vague) | **Deterministic from `rx_engine`; LLM text fallback for first-exposure** |
| Day-of-week placement of given sessions | LLM | **LLM (the genuine scheduling question)** |
| Coaching intent / instructions / flags | LLM | **LLM** |

The LLM keeps the genuinely-creative work (exercise selection within constraints, placement, prose intent). Everything else moves to code.

## 4. Tool-schema constraint (D1)

The four LLM tool schemas that emit `strength_exercises.exercise_id` change the field from a free string to an **enum bounded by the per-block resolved feasible pool**:

| Tool | File | Caller |
|---|---|---|
| `record_phase_sessions` | `layer4/per_phase.py` | Pattern A fresh-plan synth |
| `record_refresh_sessions` | `layer4/plan_refresh.py` | T1 / T2 / T3 plan patches |
| `record_single_session` | `layer4/single_session.py` | D-63 on-demand workout |
| `record_race_week_brief` | `layer4/race_week_brief.py` | Taper-week overrides |

```python
# Canonical helper in layer4/per_phase.py; imported by the other three modules.
def compute_feasible_pool_ids(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
) -> list[str]:
    """Cluster-union of resolved exercise_ids minus 2D-excluded; sorted+deduped."""

# Each tool builder accepts feasible_pool_ids: list[str] | None = None
"exercise_id": (
    {"type": "string", "enum": feasible_pool_ids}
    if feasible_pool_ids
    else {"type": "string"}
),
```

`feasible_pool_ids` is the cluster-union of `Layer2CPayload.exercises_resolved[].exercise_id` across every locale in the bundle, minus `Layer2DPayload.excluded_exercises[].exercise_id`. The list is already computed; the schema reads from the same source as the prompt. Sorted+deduped for deterministic enum ordering (cache-key stability + diff legibility).

**Empty-pool semantics:** when the helper returns `[]` (no resolvable strength surface — e.g. cardio-only locale, all candidates 2D-excluded), callers pass `feasible_pool_ids=None` so the schema reverts to free string (avoids an invalid empty-enum). The athlete-facing "no_strength_feasible" escape is a §11 edge case spec'd separately.

**Size bound:** Anthropic's tool-use schema accepts large enums; per_phase logs a warning at 200 (would indicate a 2C/2D mis-filter). Per-block scoping keeps real-world cases well under (~10 disciplines × 10 cap = 100 typical).

**Validator consequence:** Rule 6a (`equipment_unavailable`) is deleted — out-of-pool picks are structurally impossible at the SDK boundary across all four synthesis paths.

## 5. Deterministic stages

### 5.1 Session-count grid (D2)

New module `layer4/session_grid.py` (parallel to `periodization.py`):

```python
def session_counts(
    layer1: Layer1Payload,
    layer2a: Layer2APayload,
    phase: str,
    week_in_phase: int,
    race_format: str,
) -> dict[str, SessionAllocation]:
    """Returns per-discipline {count, typical_minutes, cadence} for this week."""
```

Algorithm per discipline:
1. `share = phase_load_allocation[(sport, phase, discipline)].mid_pct / 100`
2. `weekly_hours = min(layer1.weekly_capacity_h, phase_load_weekly_totals[(sport, phase)].mid)`
3. `discipline_hours = share × weekly_hours`
4. `typical_session_h` from a per-discipline lookup (running ≈ 1h easy / 2h long; MTB ≈ 1.5h; paddle ≈ 1.5h; strength ≈ 1h; climbing ≈ 1h)
5. `raw_count = discipline_hours / typical_session_h`
6. **If `raw_count < 0.5`:** `cadence = ceil(1 / raw_count)` weeks; emit 1 session this week only if `week_in_phase % cadence == 0`
7. **Else:** `count = round(raw_count)`, floor at 1 if `share > 0`

### 5.2 AR / continuous_multi_day extensions

When `race_format == 'continuous_multi_day'`:
- **Peak weeks:** grid inserts 1× `race_sim_long_day` slot, duration `min(8h, race_duration_h / 8)`, weekend-anchored, multi-discipline. The LLM fills the slot with the actual session contents from the available disciplines.
- **Taper-1:** 1× race_sim long day, ~60% Peak duration. Taper-final: no long day.
- **Brick pairing:** any same-day pair (e.g., MTB Saturday morning + trail run Saturday afternoon) gets a shared `paired_with_session_id` metadata; coaching intent rendered as "transition practice."

### 5.3 Intensity split (D3)

The grid annotates each session with a target `intensity_summary` (`easy` / `moderate` / `hard` / `mixed` / `rest`) drawn from the phase's polarized distribution:

| Phase | Easy : Hard | Notes |
|---|---|---|
| Base | 90 : 10 | one hard / week max |
| Build | 80 : 20 | progressive density |
| Peak | 70 : 30 | race-specific intensity |
| Taper | 90 : 10 | volume drops, sharpness retained (Bosquet 2007) |

The LLM places which day is which but cannot deviate from the count.

### 5.4 Rest detection (D4)

```python
def expected_rest_count(phase: str, weekly_capacity_d: int) -> int:
    """Coach-expected rest-day count for the week. Advisory."""

def detect_insufficient_rest(week: SynthesizedWeek, expected: int) -> Warning | None:
    """Post-synthesis check. Counts actual rest days (sessions=0 days, ignoring
    daily_availability_windows-disabled days which are hard-rest already).
    Returns Warning('insufficient_rest', expected=N, actual=M) when actual < expected."""
```

Expected rest count per phase (advisory): Base 2 / Build 1–2 / Peak 1 / Taper 2–3. LLM places sessions freely; the deterministic post-check flags weeks below the expected count. Rendered as a `coaching_flag` on the affected week.

### 5.5 Locale assignment + substitution (D5 / §2.6)

Post-synthesis pipeline `layer4/locale_assign.py`:

```python
def assign_locales(payload: Layer4Payload, layer2c: Layer2CPayload,
                   locations_module) -> Layer4Payload:
    """For each strength session: assign locale_id by majority-fit;
    substitute any non-fitting exercises via pattern-match."""
```

Step-by-step (per session):
1. `ideal_set = {ex.exercise_id for ex in session.strength_exercises}`
2. For each cluster locale `L`, compute `fit_count = |{ex for ex in ideal_set if ex.equipment_required ⊆ L.effective_pool}|`
3. Pick the `L` with max `fit_count`. Ties → home; second tie → closest by haversine.
4. Substitute each non-fitting exercise via `_strength_pattern_match(ex, L.effective_pool, excluded_ids)`; mark `resolution_tier = 2` (substitute).
5. If no pattern-match candidate, swap to Tier-3 bodyweight proxy; mark `resolution_tier = 3`.
6. If neither (impossible-to-fulfill), invoke the **small-call LLM substitution** (architecture in §2.6.5): tight prompt, Haiku-class model, single-purpose `substitute_exercise_id` tool enum-bounded by the locale pool. Cache key `(exercise_id, locale_id, excluded_ids_hash)`. Last-resort path; ≤1× per block budget.

Cardio sessions: locale defaults to home unless the discipline requires a route-locale (e.g., MTB needs trail access) — then nearest cluster locale with `discipline_id ∈ locale_terrain_ids`.

## 6. Pool semantics + the synth prompt (D6 superseded)

The synthesizer prompt renders **one cluster-union pool** (not per-locale). The substitution pipeline (§5.5) handles per-locale fit afterward. This effectively reverts D6 to the "union" position originally proposed; the safety the per-locale view was meant to provide now comes from the deterministic substitution step.

`_format_strength_exercise_pool` (currently in `per_phase.py:600`) keeps its existing format; the only change is the source set (`locations.cluster_effective_tags` is already what feeds it post-Track-1).

## 7. rx_engine wiring (D7)

Post-synthesis step in `layer4/rx_wire.py`:

```python
def apply_current_rx(payload: Layer4Payload, db, user_id: int) -> Layer4Payload:
    """Overwrite load_prescription with current_rx where available;
    deterministic RPE-only template + first_exposure flag where not."""
```

For each `StrengthExercise`:
- `rx = rx_engine.current_rx(db, user_id, exercise_id)` — returns `{sets, reps, load_kg|load_lbs, rir|rpe}` or `None`
- If `rx`: format as `f"{rx.load_lbs} lbs × {rx.reps} @ RPE {rx.rpe}"` and overwrite (weight + reps + RPE all rendered — weight is the actual bar load, RPE is the autoregulation target)
- If `None` (first exposure): apply a **deterministic RPE-only template** keyed off the exercise's category — no LLM in this path:
  - `compound_barbell` → `"Calibration set — pick a weight that feels RPE 6 for 8 reps; log to set baseline"`
  - `compound_dumbbell` → `"Calibration — pick DBs that feel RPE 6 for 10 reps; log to set baseline"`
  - `accessory_dumbbell` / `accessory_cable` → `"Calibration — RPE 7 for 12 reps; log to set baseline"`
  - `bodyweight` → `"3 sets × max reps with 2 reps in reserve; log to set baseline"`
  - Append `first_exposure` to `coaching_flags` so the UI can render the "calibration" framing.

Weight is omitted in the first-exposure path because it's genuinely unknown; rendering an LLM-guessed pound number would be misleading. The athlete sets the baseline via the calibration set; subsequent sessions read `current_rx` and become precise.

`rx_engine.current_rx` is the existing strength-tracker read (currently called only from `routes/training.py`); exposes it as a layer4-callable interface. **Track 3 dependency:** `rx_engine` currently reads `public.exercise_inventory`; Track 3 moves this to `layer0.*`. Until Track 3 ships, rx lookups are limited to the exercises in the public catalog (subset of layer0); a layer0-only exercise emitted by the synthesizer falls through to first-exposure. Acceptable v1 behavior; full coverage with Track 3.

## 8. Validator demotion sweep (D8)

| Rule | Today | After Track 2 | Rationale |
|---|---|---|---|
| 1 `volume_band` | BLOCKER | **warning** | D2 grid makes weekly volume self-consistent |
| 2 `acwr` | BLOCKER | warning | Heuristic; the deterministic ramp + Bosquet taper handle the real cases |
| 3 `rest_spacing` | BLOCKER | warning | D4 detects insufficient rest deterministically; LLM keeps placement freedom; rule becomes the surface for the detected warning |
| 4 `intensity_dist` | BLOCKER | warning | D3 enforces the distribution; warning catches LLM placement drift |
| 5 `two_per_day` | structural | **structural (keep)** | Real schema invariant; not synthesis quality |
| 6a `equipment_unavailable` | BLOCKER | **DELETE** | D1 makes it structurally impossible |
| 6b `session_multi_locale` | BLOCKER | **structural (keep)** | Real integrity violation; D5 assigns single locale per session |
| 6c `session_locale_not_in_cluster` | BLOCKER | **structural (keep)** | Real integrity violation |
| 7 `injury_violation` | BLOCKER | warning | 2D-exclusion in D1 enum handles it; warning catches edge cases |
| 7b `injury_accommodation_violation` | BLOCKER | warning | Same as 7 |
| 11 `schedule_violation` | BLOCKER | warning | D4 + `daily_availability_windows` covered |
| 12 `discipline_excluded` | BLOCKER | **structural (keep)** | Layer 2A explicit exclusion is authoritative |
| 13 `sport_locale_incompatible` | warning (PR #413) | unchanged | Already correctly demoted Phase 1 |
| 18 `kit_manifest_inputs_incomplete` | data_gap | unchanged | Race-week-brief only |

After 2d ships: only **6b / 6c / 5 / 12** remain as retry-driving blockers. The retry loop's failure surface shrinks from ~10 classes to 4 — and those 4 are real integrity violations, not heuristic misses.

## 9. Caching / invalidation

- `phase_load_allocation` and `phase_load_weekly_totals` are layer0 (etl-versioned); already in the cache-key via `etl_version_set`.
- The session-count grid is a pure function of `(layer1, layer2a, phase, week_in_phase, race_format)`; folds into the layer4 cache key the same way `periodization.phase_week_volume_bands_hours` already does — no new key surface.
- `current_rx` reads in §7 are **not** cached into the block synthesis (per-athlete state changes between cold and warm runs); the rx-wire step runs on the hydrated payload, not the cache key. A `current_rx` edit therefore doesn't invalidate Layer 4 blocks — it only changes the rendered `load_prescription` on the next read. Correct: the synthesis was right; the prescription updates.
- Locale assignment (§5.5) similarly runs post-hydrate; locale edits already evict Layer 2C (Track 1 eviction policy `_ALL_ENTRY_POINTS`), which transitively invalidates Layer 4.

## 10. Code changes (file-by-file) + PR slicing

### Slice 2a — schema enum (all 4 paths) + delete Rule 6a (5 substantive files)
| File | Change |
|---|---|
| `layer4/per_phase.py` | NEW `compute_feasible_pool_ids()` helper (cluster-union of resolved ids ∖ 2D-excluded; canonical, imported by the other 3); `_session_schema` + `build_record_phase_sessions_tool` accept `feasible_pool_ids` parameter; caller computes + passes. |
| `layer4/plan_refresh.py` | `_session_schema` + `build_record_refresh_sessions_tool` accept `feasible_pool_ids`; caller computes from `layer2_bundle.c` / `.d` + passes. |
| `layer4/single_session.py` | `build_record_single_session_tool` accepts `feasible_pool_ids`; caller wraps single-locale `layer2c_payload_for_locale` as `{locale_id: l2c}` for the helper + passes. |
| `layer4/race_week_brief.py` | `_taper_override_session_schema` + `build_record_race_week_brief_tool` accept `feasible_pool_ids`; caller computes + passes. |
| `layer4/validator.py` | Delete `_rule_equipment_unavailable` + remove from `_ALL_RULES`; retire-stub comment in place; update stale 6a references in adjacent comments. |

Non-substantive (test files): `tests/test_layer4_plan_create.py` adds `TestComputeFeasiblePoolIds` (4 tests) + `test_feasible_pool_enum*` (3 tests on the tool builder); `tests/test_layer4_validator.py` deletes the 3 Rule 6a tests + updates stale comments. `layer4/__init__.py` re-exports `compute_feasible_pool_ids`.

**Scope expansion from the original spec** (single-file per_phase only): the original §10 listed per_phase + validator only. During implementation we discovered 3 other tool schemas (`record_refresh_sessions`, `record_single_session`, `record_race_week_brief`) that also emit `exercise_id` — deleting Rule 6a without enum-bounding those paths would create a feasibility-gating hole. Expanded to all 4 paths to keep §3's "structurally impossible" guarantee honest. Andy 2026-06-06 approved option A over the conservative-demotion option B.

### Slice 2b — session-count grid + intensity split + prompt rewrite (≤5 files)
| File | Change |
|---|---|
| `layer4/session_grid.py` | NEW — §5.1 + §5.2 + §5.3. |
| `layer4/per_phase.py` | **Prompt rewrite** (load-bearing): today the SYSTEM_PROMPT + USER_PROMPT ask the LLM to **allocate** the week (decide counts, intensities, rest). After 2b the prompt **hands the LLM a pre-filled grid** (per-discipline session counts + intensity targets + race-sim slot when applicable) and asks for **placement + content** only — which day, which time-of-day, which exercise selection within the constraints, coaching intent. The `render_user_prompt` + the SYSTEM_PROMPT framing both change; the grid-rendering template is new. Estimate ~150–200 line delta in `per_phase.py` for the rewrite, separate from the new `session_grid.py` consumption call. |
| `layer4/validator.py` | Demote `_rule_volume_band` to warning; demote `_rule_intensity_dist` to warning. |
| `tests/test_layer4_session_grid.py` | NEW. |
| `tests/test_layer4_per_phase.py` | Add prompt-rewrite tests: assert pre-filled grid appears verbatim in rendered prompt; assert old "allocate" language is gone. |

### Slice 2c — rest detection + STRENGTH locale assignment + substitution (5 files, shipped 2026-06-06)

Cardio routing pulled out → 2c.2 follow-up. See "**Slice 2c.2 follow-up**" below.

| File | Change |
|---|---|
| `layer4/session_grid.py` | Extended with `expected_rest_count(phase, weekly_capacity_d)` + `detect_insufficient_rest(sessions, expected, disabled_dates)` (§5.4); returns `InsufficientRestWarning` consumed by validator Rule 3. |
| `layer4/locale_assign.py` | NEW — §5.5 pipeline (majority-fit → pattern-match substitute → tier-3 bodyweight proxy → small-call LLM substitute → coaching_flag tail). `_LLM_SUBSTITUTE_CALLS_PER_INVOCATION = 1` budget. Returns `LocaleAssignDiagnostic` for `synthesis_metadata` (Rule #14 observability). Cardio + rest sessions pass through untouched. |
| `layer4/orchestrator.py` | NEW `_apply_locale_assign(db, user_id, payload, layer2c_payloads)` runs post-cached engine on `orchestrate_plan_create` + `orchestrate_plan_refresh`. Pass-through degrade on exception (non-fatal). The natural call site is the orchestrator (already has `db` + `user_id`), not `plan_create.py` / `plan_refresh.py` as the original §10 row implied. |
| `layer4/validator.py` | Demoted Rules 3 / 11 to warning. Added `_append_insufficient_rest_warnings` invoked from `_rule_rest_spacing` — emits one warning per (phase, ISO-week) with rest count below expected. |
| `tests/test_layer4_locale_assign.py` | NEW. 14 tests covering majority-fit, ties→home, pattern-match substitute (tier-1/2 preferred over tier-3), tier-3 proxy fallback, LLM small-call budget, hallucination defense, coaching-flag tail, cardio/rest pass-through, diagnostic serialization. |

**Slice 2c.2 follow-up (NOT shipped): cardio-session route-locale routing** (§5.5 final ¶). Pulled out 2026-06-06 because it depends on layer0 vocab work not yet done:

- **Layer 0 vocab adds (Andy 2026-06-06):** new TRN-017 row "Off-Trail / Bush" for overland navigation (currently no canonical terrain covers this), and rename TRN-007 from "Technical Rock" → "Technical Rock/Scree" for clarity. Both are layer0 vocabulary changes that need `etl/layer0/extractors/vocabulary.py` updates + ETL migration + Neon re-run + spec edit. Trigger #3 cross-layer surface change; track in its own micro-spec.
- **Snow-sports semantics decision (Andy 2026-06-06):** Mountain/Alpine (TRN-005) ≠ Snow access (TRN-012). Need a ratified rule for D-018 Mountaineering routing (current OR-match has the LLM/athlete handle seasonality; alternative is snow-only routing for mountaineering with athlete editing for non-snow seasons). Open design call.
- **Discipline→required_terrain map drafted, NOT locked:** 17 of 21 disciplines mapped; 4 default to home (D-002 Road Running, D-006 Road Cycling, D-007 TT Cycling, D-027 OCR). Full table in the slice 2c handoff §3.

**Persistent-cache follow-up:** the small-call LLM substitute uses an in-memory cache scoped to one `assign_locales` invocation. The spec §5.5 step 6 calls out a persistent `(exercise_id, locale_id, excluded_ids_hash) → substitute_id` cache reusable across athletes; that requires extending `cache.VALID_ENTRY_POINTS` + the `layer4_cache.entry_point` CHECK constraint to add a new `llm_locale_substitute` label. Defer until real-world telemetry shows the LLM substitute firing often enough to warrant the persistence cost.

### Slice 2d — rx_engine wiring + remaining validator demotion (≤4 files)
| File | Change |
|---|---|
| `layer4/rx_wire.py` | NEW — §7. |
| `rx_engine.py` | Add `current_rx(db, user_id, exercise_id) -> Rx | None` if not already exported. |
| `layer4/plan_create.py` + `layer4/plan_refresh.py` | Call `apply_current_rx()` after `assign_locales()`. |
| `layer4/validator.py` | Demote Rules 2 / 7 / 7b to warning. |

Each slice fits the 5-file substantive ceiling; each is independently verifiable against a cold PGE plan.

## 11. Edge cases

- **Empty feasible pool** (athlete has no equipment, all bodyweight excluded by 2D). D1 enum is empty → tool call would fail. Pre-check: if pool size < 3, skip strength synthesis for the block, emit `coaching_flags=['no_strength_feasible']` warning. Already the Track-1 §10 precedent.
- **Cardio-only week with insufficient hours.** Grid would emit 0 sessions for a discipline. Fine — the discipline is honestly absent that week.
- **Race-sim long day exceeds `daily_availability_windows`.** Override: race-sim takes precedence in Peak (athlete chose this race; the spec assumes weekend availability). Document in the rendered coaching_intent: "race-sim day overrides usual Saturday off."
- **`current_rx` exists but is stale** (athlete hasn't logged the exercise in 3+ months). Use as a baseline + add `stale_rx` coaching flag; the LLM-emitted load_prescription remains visible as a fallback for the athlete to judge.
- **Locale `effective_pool` is empty** (athlete added a locale but hasn't set equipment yet). Skip that locale in majority-fit consideration; fall through to next.
- **Cluster of 1 locale (home only).** All sessions assign to home; majority-fit collapses to "does home cover it" — substitute or Tier-3 proxy as needed.
- **Athlete travelling without a defined locale** (no cluster locale in range; week falls outside the home 26.2-mile cluster). Use the existing `hotel_gym` shared-profile default (`Athlete_Onboarding_Data_Spec_v6.md` §H.5 — treadmill + basic DBs + bench) as a synthetic `default_hotel` locale for assignment purposes. The LLM is told "you're training out of a default hotel set this week — basic equipment only"; the deterministic assigner uses the default pool for fit + substitution. Athlete sees a `traveling_default_hotel` coaching flag. (When the athlete pre-adds a hotel locale with detail, that takes precedence — this fallback only fires when nothing else is in range.)
- **Multi-day brick that crosses midnight.** Out of scope for v1; document as a v1.1 follow-up. Single-day brick (two sessions one date) covered.

## 12. Open items / decisions

- **D-1 — RESOLVED:** AR extensions = race-sim long days + brick pairing only. Nav-modifier and skill-cap-bias deferred.
- **D-2 — RESOLVED:** D6 reverts to cluster-union prompt; D5 is the locale-assignment process (Andy's reframe).
- **D-3 — DEFERRED:** per-discipline intensity ratios (running ≠ MTB at the same phase). Document baseline polarized ratios; revisit after 2–3 plans show whether the single-ratio default is hurting.
- **D-4 — DEFERRED:** validator-demotion QA audit. After 3–4 plans on the new contract, review the warnings stream; re-promote rules whose demotion proved unsafe.
- **D-5 — DEFERRED:** multi-day brick crossing midnight (§11 edge case).
- **D-6 — DEPENDENCY:** Track 3 (#430) catalog migration moves `rx_engine` to `layer0.*`. Until then, rx lookups are limited to the public-catalog subset; layer0-only exercises fall through to first-exposure (§7). Acceptable.

## 13. Test plan

### Per-slice unit tests
- 2a: enum constraint rejects out-of-pool `exercise_id` at the SDK boundary; Rule 6a no longer fires when an exercise is missing.
- 2b: session-count grid produces expected counts for Andy's PGE mix (manual reference: trail run 4–5/wk, MTB 1/wk, paddle 1/wk Build:w4); maintenance cadence correct for climbing at 3% phase_load.
- 2c: rest placed adjacent to heaviest day; locale assigner picks home when home covers majority; substitution chain pattern-match → Tier-3.
- 2d: rx-wire overwrites with `current_rx` where present; first_exposure flag added where absent.

### End-to-end (live)
- **After 2a:** cold PGE plan. Win = no `equipment_unavailable` blockers anywhere in the run (the class is structurally impossible). Pull diag JSON for the `validator_failures_by_rule` distribution.
- **After 2b:** cold PGE plan. Win = no `volume_band` blockers, weekly counts match the grid, intensity ratios match phase defaults.
- **After 2c:** cold PGE plan. Win = every session has a `locale_id`; no `session_multi_locale` or `session_locale_not_in_cluster` integrity violations; rest days place adjacent to the long-run day.
- **After 2d:** cold PGE plan. Win = strength sessions have precise loads (`"185 lbs × 5, RPE 7"`) for exercises Andy has logged; `first_exposure` flag on new exercises only.

### Regression
- Full `tests/` suite green at each slice (Track 1 baseline: 1998 passed / 16 skipped).
- Each slice should not change the cache hashing surface beyond what its declared inputs imply; verify with `cached_wrappers.py` HIT/MISS logging on a re-run.

## 14. Gut check

- **Biggest risk:** the session-count grid (D2 / §5.1) encodes assumptions that are correct for road-marathon-shape sports but may produce odd output for the genuinely-multi-disciplinary cases (PGE itself, swimrun, modern triathlon). Typical-session-hour lookups especially are coach-estimate, not measured. Mitigation: ship 2a first (which fixes the equipment failure mode independently); land 2b under the §13 e2e win condition; if the grid produces visibly-wrong allocations for any one discipline, the file is one constants table to tune.

- **Biggest unknown:** whether the deterministic locale-assignment (§5.5) handles the cases I haven't seen yet — multi-locale travel patterns where the athlete bounces between 2–3 destinations in a single block, partial-week locale switches, locale priority signals. The greedy majority-fit + `hotel_gym` default-pool fallback (§11) cover the simple travel cases; complex multi-destination weeks we can only design against once they exist. Track-2.5 follow-up: revisit assigner after the first 3 multi-locale plans.

- **Best argument against the whole approach:** Track 2 is a big bet on "feasibility is solvable deterministically." If a real edge case proves otherwise (e.g., a session's ideal exercise set has no majority-fit locale AND no pattern-match substitute AND no Tier-3 proxy), the LLM fallback in step 5.5.6 is the only escape valve — and if it fires often, we've added complexity without removing the LLM-as-feasibility-decider role. Mitigation: instrument the fallback heavily; if it fires > 1% of sessions across 3 plans, re-think §5.5.

- **What this spec consciously doesn't cover:**
  - Layer 2A `phase_load` data hygiene for AR (the `verify_drift_specifics.sql` checks reference). Spec assumes the data is correct; if not, fix at the layer0 level, not here.
  - The seam-review / cross-phase coherence pieces — those are #333 / #418 territory, separate.
  - Validator quality assurance audit (deferred per §2.8).

---

*End of spec — pending Andy sign-off.*
