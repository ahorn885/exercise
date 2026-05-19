# Layer 1 — Athlete Profile Aggregation (Query Node)

**Status:** 🟢 v1 spec consolidation + typed payload + runtime builder shipped 2026-05-19 (D-73 Phase 1.3).

**Predecessor:** `Layer1_D51_Design_v1.md` (storage design wave shipped 2026-05-19; Phase 1.2A/B/C migrations shipped 2026-05-19).

**Source-of-truth split closed by this spec:** previously Layer 1 was described across `Athlete_Onboarding_Data_Spec_v5.md` (§A–§L form fields) + `Athlete_Data_Integration_Spec_v5.md` §7 (storage gap inventory) + `Layer1_D51_Design_v1.md` (storage decisions). This file is the consolidation: one place that names purpose, function signature, validation, algorithm, payload schema, and test scenarios.

---

## 1. Purpose

Layer 1 reads the persisted athlete profile (D-51 §3 storage shipped in D-73 Phase 1.2A/B/C plus existing companion tables) and assembles a single typed `Layer1Payload` for downstream consumers (Layer 2A–E + Layer 3A + Layer 3B + Layer 4 orchestrator). It is a **query node** — pure aggregation, no LLM, no judgment.

The typed payload contract is the long-deferred promotion of `Layer1Payload` from `dict[str, Any]` opaque pass-through (the v1 shape Layer 4 was built against in PR-D) to a pydantic-v2 typed mirror that documents every field Layer 1 actually surfaces.

---

## 2. What Layer 1 does NOT do

- **No LLM judgment.** Free-text fields (`longest_event_completed`, `gi_triggers_known`, `training_consistency_cause`, `gut_training_issues`, etc.) are passed through verbatim. If §C Longest Event Completed parsing turns out to need LLM judgment in v2, Layer 1 expands to an LLM-driven node — deferred per `Layer1_D51_Design_v1.md` §1 out-of-scope.
- **No derivation of `experience_level` / `coaching_voice_preferences` / `travel_constraint`.** These are top-level convenience fields that Layer 4 reads via `.get(...)` today; the builder leaves them `None` in v1. The derivation rules (e.g., `years_structured_training` → experience tier) are a future enhancement; see §12.
- **No partial-update invalidation logic.** D-73 §M.1 triggers re-evaluate against the new columns automatically when the route layer wires them up; Layer 1 itself is stateless.
- **No write-path validation of closed-enum integrity.** The form layer + `athlete.py` constants own write-side validation. Layer 1 reads what's there; the pydantic Literal types document the consumer-side contract but the builder will raise `ValidationError` if storage drifts outside the closed set (defensive — should not happen with the form layer correct).
- **No backfill or migration logic.** Storage migrations are owned by `init_db.py` `_PG_MIGRATIONS`.

---

## 3. Function signature

```python
# layer1/__init__.py
from layer1 import build_layer1_payload

def build_layer1_payload(db, user_id: int) -> Layer1Payload:
    ...
```

**Inputs:**
- `db` — `database._PgConn`-shaped connection (anything with `execute(sql, params) -> cursor` + `cursor.fetchone()` / `cursor.fetchall()`). The `_FakeConn` test fixture from `tests/test_race_events_repo.py` matches the shape.
- `user_id: int` — non-None required. `None` raises `ValueError`.

**Output:** a fully-populated `Layer1Payload` (`layer4/context.py`) — never `None`. Missing 1:1 sub-table rows surface as `None` on the corresponding section sub-model; missing multi-row companions surface as empty lists. Missing `athlete_profile` row surfaces as section sub-models with all-None scalars.

**Layer 4 dict compatibility:** Layer 4 entry points currently consume `layer1_payload: dict[str, Any]` and read 6 keys via `.get(...)` (`experience_level`, `coaching_voice_preferences`, `available_days_per_week`, `travel_constraint`, `sleep_baseline`, `daily_availability_windows`). These keys live at the top level of `Layer1Payload` so `.model_dump()` produces a dict the Layer 4 code paths read unchanged. Per `Upstream_Implementation_Plan_v1.md` §6 item 3 + §8 mitigation, the entry-point signature swap (`dict[str, Any]` → `Layer1Payload`) is deferred to v2 to avoid ~10-15 test fixture rewrites.

---

## 4. Input validation

| Rule | Action on violation |
|---|---|
| `user_id is None` | `ValueError("user_id required")` |
| Storage row carries a closed-enum value outside the pydantic `Literal` set (e.g., `sex='other'`, `medication_class='unknown_drug'`) | `pydantic.ValidationError` from the section sub-model constructor (defensive; form layer should prevent) |
| `athlete_discipline_weighting` rows exist but `SUM(weight_pct) != 100` | `pydantic.ValidationError` from `Layer1TrainingHistory._check_weighting_sum` |
| `DailyAvailabilityWindow` invariants (disabled-with-populated-window, paired-second-window-non-null) violated | `pydantic.ValidationError` from existing context.py validator |
| `food_allergies.severity='anaphylaxis'` present but no matching `health_conditions_log.system_category='gi_immune'` row | **Not validated here.** v5 §B.4.2 calls for an "auto-populate" rule that the Layer 1 builder COULD enforce, but the design wave §3.2 placed the responsibility on the write-path (not the read-path) — Layer 1 reflects storage as-is. v2 may surface this as a coaching flag once the seam stabilises. |

No silent fallbacks. The builder surfaces storage drift as a hard error so the form layer + tests catch it.

---

## 5. Algorithm

24 SELECTs in fixed order (so `_FakeConn` test responses can queue deterministically). Each SELECT is keyed on `user_id`; no JOINs across sub-tables (sparse-friendly). Per-section assembly is straightforward — the pydantic constructors validate as the builder threads in.

### 5.1 Read order

| # | Table | Shape | Builder helper |
|---|---|---|---|
| 1 | `athlete_profile` | 1:1 (1 row) | `_load_athlete_profile` |
| 2 | `body_metrics` (latest row with `resting_hr IS NOT NULL`) | 1 row | `_load_resting_hr` |
| 3 | `wellness_self_report` (latest row with `sleep_hours IS NOT NULL`) | 1 row | `_load_sleep_baseline` |
| 4 | `daily_availability_windows` | ≤14 rows (7 days × ≤2 windows) | `_load_daily_windows` |
| 5 | `injury_log` | multi | `_load_injuries` (split by `status`) |
| 6 | `health_conditions_log` | multi | `_load_health_conditions` (split by `status`) |
| 7 | `medications_log` | multi | `_load_medications` (split by `stopped_at IS NULL`) |
| 8 | `food_allergies` | multi | `_load_food_allergies` |
| 9 | `athlete_secondary_sports` | multi | `_load_secondary_sports` |
| 10 | `athlete_discipline_weighting` | multi | `_load_discipline_weighting` |
| 11 | `recent_race_results` | multi | `_load_recent_race_results` |
| 12 | `pack_load_history` | multi | `_load_pack_load_history` |
| 13 | `strength_benchmarks` | 1:1 | `_load_strength_benchmarks` |
| 14 | `discipline_baseline_running` | 1:1 | `_load_running_baseline` |
| 15 | `discipline_baseline_cycling` | 1:1 | `_load_cycling_baseline` |
| 16 | `discipline_baseline_swimming` | 1:1 | `_load_swimming_baseline` |
| 17 | `discipline_baseline_paddling` | 1:1 | `_load_paddling_baseline` |
| 18 | `discipline_baseline_skiing` | 1:1 | `_load_skiing_baseline` |
| 19 | `discipline_baseline_navigation` | 1:1 | `_load_navigation_baseline` |
| 20 | `discipline_baseline_technical` | 1:1 | `_load_technical_baseline` |
| 21 | `race_events` (target row) | 1 row | `_load_target_race_event_id` |
| 22 | `athlete_network_links` | multi | `_load_network_links` |
| 23 | `linked_partner_consents` | multi | `_load_linked_partner_consents` |
| 24 | `disclosure_acknowledgments` (latest per `disclosure_id`) | multi | `_load_disclosures` (window function: `ROW_NUMBER() OVER (PARTITION BY disclosure_id ORDER BY acknowledged_at DESC)`) |

### 5.2 Comma-separated columns → typed lists

Per `Layer1_D51_Design_v1.md` §3.x, several columns store comma-separated subsets of a closed enum or framework slug set:

- `athlete_profile.long_session_days`, `preferred_rest_days`, `dietary_pattern`, `fueling_format_preference`
- `discipline_baseline_running.trail_experience_terrain`
- `discipline_baseline_cycling.bike_types_available`
- `discipline_baseline_paddling.paddle_craft_types`
- `discipline_baseline_skiing.ski_disciplines`
- `athlete_network_links.relationship_types`

`_split_csv(value)` (builder helper) splits on `,`, strips whitespace, drops empty tokens. Empty / whitespace-only / `None` storage → `[]`.

### 5.3 Day-of-week numbering convention

**Sunday = 0** per `Layer1_D51_Design_v1.md` §6 #1 (Andy 2026-05-19). Matches `athlete.DAY_TOKENS` (`'sun', 'mon', ..., 'sat'`) + the v5 §G.1 schema comment + the `daily_availability_windows.day_of_week` SMALLINT storage. The builder maps `0..6` → `"Sun".."Sat"` (Title-case three-letter tokens per the existing `DailyAvailabilityWindow.day_of_week` Literal in `layer4/context.py`).

### 5.4 Per-week capacity denormalization onto `DailyAvailabilityWindow`

`DailyAvailabilityWindow` (existing in `layer4/context.py`; D-61 design wave shape) carries both per-day window times AND per-week capacity flags (`long_session_available`, `long_session_max_duration`, `doubles_feasible`, `preferred_rest_day`). The builder denormalizes `athlete_profile.long_session_*` + `doubles_feasible` + `preferred_rest_days` onto each of the 7 day rows so the typed model carries everything Layer 4 expects.

- `long_session_available`: `True` on every day when `athlete_profile.long_session_available = TRUE`; `None` otherwise (typed model accepts None as "not configured").
- `long_session_max_duration`: from `athlete_profile.long_session_max_hr` (Literal `2 | 3 | 4 | 5 | 6 | 8`).
- `doubles_feasible`: from `athlete_profile.doubles_feasible`; **default `"no"` when the column is NULL** (typed model requires non-null Literal; interpretation: "no doubles when not configured").
- `preferred_rest_day`: `True` only when the day's token is in `athlete_profile.preferred_rest_days`.

### 5.5 `available_days_per_week` derivation

`Layer1Payload.available_days_per_week` = `sum(1 for w in daily_availability_windows if w.enabled)`. Layer 4 reads this top-level via `.get(...)`.

---

## 6. Toggle handling — top-level convenience fields vs section sub-models

Top-level `Layer1Payload` carries **6 convenience fields** that mirror Layer 4's current `.get(...)` consumption pattern. These are NOT duplicates of section sub-models; they're a flat-dict-compatible view:

| Top-level field | Source / derivation | Sub-model equivalent |
|---|---|---|
| `experience_level` | Not derived in v1 (left `None`); see §12 for v2 derivation rule | — |
| `coaching_voice_preferences` | Not stored anywhere in v1 (`None`); see §12 | — |
| `available_days_per_week` | `count(daily_availability_windows where enabled)` | derived from `daily_availability_windows` |
| `travel_constraint` | Not stored anywhere in v1 (`None`); see §12 (Layer 4 reads `plan_travel`) | — |
| `sleep_baseline` | latest `wellness_self_report.sleep_hours` | mirrors `lifestyle.sleep_baseline_hours` |
| `daily_availability_windows` | 7 entries Sun..Sat per §5.4 | — (sole carrier; not under `availability.*`) |

Section sub-models (`identity`, `health_status`, `training_history`, `discipline_baselines`, `strength_benchmarks`, `performance`, `availability`, `event_goal`, `lifestyle`, `network`, `disclosures`) carry the full §A-§L mirror. **Layer 4 does not read these in v1.** Phase 5 orchestrator + future Layer 2A-E builders read them directly via the typed attribute path.

---

## 7. Payload schema

Canonical typed contract: `layer4/context.py` — `Layer1Payload` + 11 section sub-models + 11 record-type sub-models. Reproduced here as a tree summary; the typed file is the source of truth.

```
Layer1Payload
├── user_id: int
├── as_of: datetime
├── experience_level: Literal["novice","developing","intermediate","advanced","elite"] | None
├── coaching_voice_preferences: str | None
├── available_days_per_week: int | None  (0..7)
├── travel_constraint: str | None
├── sleep_baseline: float | None  (hours, ≥0)
├── daily_availability_windows: list[DailyAvailabilityWindow]  (7 entries)
│
├── identity: Layer1Identity
│   ├── date_of_birth: date | None
│   ├── sex: Literal["male","female"] | None
│   ├── height_cm, primary_sport, weekly_hours_target, notes
│
├── health_status: Layer1HealthStatus
│   ├── current_injuries: list[InjuryRecord]   (status='Active')
│   ├── injury_history: list[InjuryRecord]      (status in 'Resolved','Inactive')
│   ├── health_conditions_active / history: list[HealthConditionRecord]
│   ├── medications_active / history: list[MedicationRecord]   (split by stopped_at IS NULL)
│   ├── food_allergies: list[FoodAllergyRecord]
│   └── resting_hr_bpm: int | None
│
├── training_history: Layer1TrainingHistory  (§C scalars + 4 multi-row companions)
│   ├── years_structured_training, peak_weekly_volume_*, longest_event_completed
│   ├── training_consistency_*, previous_coaching
│   ├── secondary_sports, discipline_weighting (sum=100 invariant)
│   ├── recent_race_results, pack_load_history
│
├── discipline_baselines: Layer1DisciplineBaselines  (7 × 1:1; None when absent)
│   └── running / cycling / swimming / paddling / skiing / navigation / technical
│
├── strength_benchmarks: Layer1StrengthBenchmarks | None
│
├── performance: Layer1Performance  (§F scalars + sources + test_dates)
│
├── availability: Layer1Availability  (per-week capacity; daily windows at top level)
│   ├── long_session_available, long_session_days, long_session_max_hr
│   ├── doubles_feasible, preferred_rest_days
│
├── event_goal: Layer1EventGoal
│   ├── target_race_event_id: int | None
│   ├── plan_duration_weeks_no_event: Literal[8,12,16,20,24] | None
│   └── non_event_goal_type: Literal["endurance","general_fitness","strength","mixed"] | None
│
├── lifestyle: Layer1Lifestyle  (§I scalars + sleep_baseline carried from wellness)
│
├── network: Layer1Network
│   ├── network_links: list[AthleteNetworkLink]
│   └── linked_partner_consents: list[LinkedPartnerConsent]
│
└── disclosures: Layer1Disclosures
    └── acknowledgments: list[DisclosureAck]  (latest per disclosure_id)
```

All `extra='forbid'` (per `_Base` config in context.py) — untrusted upstream extension would raise. List defaults are `default_factory=list` to keep `Layer1Payload(**minimal_args)` constructable.

---

## 8. Coaching flag rules

**None in v1.** Layer 1 is a pure aggregation node; it does not emit coaching flags. Layer 2A-E, Layer 3A, Layer 3B carry coaching-flag emission per their respective specs.

A "data hygiene observation" surface (e.g., "no strength benchmarks ever recorded", "discipline_weighting rows missing for active disciplines") is a candidate for v2 enhancement — would land in a `Layer1Observations` section sub-model mirroring the Layer 3 observation pattern. Deferred until first real-athlete read surfaces the need.

---

## 9. Caching & determinism

**Not cached in v1.** Per `Upstream_Implementation_Plan_v1.md` §5.3 "cache-agnostic" architect-pick, the Layer 4 orchestrator (Phase 5) computes the Layer 4 cache key from `Layer1Payload`'s `model_dump()` via `compute_payload_hash` (`layer4/hashing.py`). The builder is pure — same DB state → same payload (modulo `as_of` timestamp which is excluded from cache hashing via the existing hasher's omit-list pattern, if needed; see open item §12 #1).

**Determinism caveats:**
- `as_of: datetime` is `datetime.utcnow()` at build time. Excluding it from cache hashes is a Phase 5 orchestrator concern (mirrors how Layer 3A/3B handle `as_of` per their specs).
- Multi-row ORDER BY clauses are deterministic (`event_date DESC, id DESC` style) so repeated builds against the same DB state produce identical lists.
- Disclosure dedup uses `ROW_NUMBER() OVER (PARTITION BY disclosure_id ORDER BY acknowledged_at DESC)` — deterministic per PG semantics.

---

## 10. Edge cases

| Case | Behavior |
|---|---|
| `user_id` has no `athlete_profile` row | section sub-models all-None-scalar; `Layer1Payload` constructable; `available_days_per_week=0`. |
| `daily_availability_windows` empty | 7 entries surfaced with `enabled=False`; `doubles_feasible='no'` (default per §5.4). |
| `daily_availability_windows` has rows for only some days | Missing days surface `enabled=False`. |
| `daily_availability_windows.window_index=1` exists but primary (`window_index=0`) doesn't for the same day | Primary day surfaces `enabled=False`; secondary fields populated. Edge case — should not happen under D-61 write-path conventions but builder tolerates. |
| `athlete_discipline_weighting` rows sum != 100 | `ValidationError` per §4 (intermediate edit states should not reach Layer 1 reads). |
| `food_allergies.severity='anaphylaxis'` present but no `gi_immune` condition row | Surfaces verbatim — no auto-populate (§4 + Layer1_D51_Design_v1.md §3.2). |
| `discipline_baseline_*` row exists but every column is NULL except `user_id` + `updated_at` | Sub-model surfaces with every field None — valid (Layer 1 doesn't enforce "at least one field set"). Acceptable per v5 §D "every field is nullable; null means 'not asked.'" |
| `race_events` has multiple `is_target_event=TRUE` rows | The partial UNIQUE index on `(user_id) WHERE is_target_event=TRUE` prevents this at the DB layer; if it ever happens (manual SQL), `LIMIT 1` picks one arbitrarily. |
| `linked_partner_consents` references `link_id` not in `athlete_network_links` | Surfaces verbatim — defensive (FK is `ON DELETE CASCADE` so this shouldn't happen). |
| `disclosure_acknowledgments` has ties on `acknowledged_at` for the same `disclosure_id` | `ROW_NUMBER()` picks one arbitrarily; downstream consumers tolerate (no rule needs the exact one). |
| `body_metrics.resting_hr` only ever NULL despite rows existing | Builder query filters `WHERE resting_hr IS NOT NULL`; returns None. |
| Closed-enum drift (storage carries value outside Literal set) | `ValidationError` — defensive surface; form layer + `athlete.py` write-path validators are the prevention. |

---

## 11. Performance budget

- **24 SELECTs per build.** All are `WHERE user_id = ?` against indexed columns (PK or `(user_id, ...)` btree). Expected cold latency: ~5-15ms per SELECT on Neon under normal load. **Budget: ~150-300ms total per `build_layer1_payload` call.** Well under any LLM-call budget.
- **No JOINs.** Each SELECT is independent. Trade-off: more round-trips for sparse-row-set tolerance + builder simplicity. Could be optimized via a single CTE-joined SELECT if profiling shows latency budget overruns; not warranted in v1.
- **Cache:** see §9. Phase 5 orchestrator caches downstream of Layer 1; rebuild on each Layer 4 entry is acceptable until first profile-read latency telemetry lands.

---

## 12. Open items / forward references

1. **`as_of` exclusion from cache-key hashing.** Phase 5 orchestrator will need to either omit `Layer1Payload.as_of` from the cache-key hash OR round it to a coarser granularity (e.g., date precision) so non-mutating builds within a window produce the same cache key. Layer 4 `hashing.py` precedent omits `computed_at` from Layer 2E's hash — same pattern applies here.

2. **`experience_level` derivation rule.** v2 candidate: `years_structured_training` + `peak_weekly_volume_hrs` → `novice / developing / intermediate / advanced / elite`. Tentative thresholds (no architectural ratification yet):
   - `years_structured_training < 1` → novice
   - `1 ≤ years < 3` → developing
   - `3 ≤ years < 6` → intermediate
   - `6 ≤ years < 10` → advanced
   - `years ≥ 10` AND `peak_weekly_volume_hrs ≥ 15` → elite
   Leave None until v2; Layer 4 tolerates None and defaults to `"unknown"` in its prompts.

3. **`coaching_voice_preferences` derivation.** No v1 storage. v2 candidate: a `coaching_preferences` table query (already exists per `init_db.py:190`) joined to category='coaching_voice'. Defer.

4. **`travel_constraint`.** No v1 storage at the field level. v2 candidate: read `plan_travel` rows overlapping the current plan window and surface a `summary: str` if any exist. Defer to Phase 5 orchestrator (which already reads `plan_travel` for the Layer 3B builder).

5. **Layer 4 entry-point signature swap.** Per `Upstream_Implementation_Plan_v1.md` §6 item 3 + §8 mitigation, keep `dict[str, Any]` for v1; promote in v2. ~10-15 test fixture rewrites avoided.

6. **§3.10 §J locale terrain access structured storage.** Out of D-51 design wave scope per `Layer1_D51_Design_v1.md` §3.10; Layer 1 currently does not surface locale data (Phase 5 orchestrator reads `locale_profiles` directly for Layer 2C). May fold into Layer 1 in v2 if Layer 4 needs a unified athlete-context bundle.

7. **§3.11 §K Locale Schedule richer modeling.** Out of D-51 scope; `plan_travel` remains the v1 storage. Same Phase 5 orchestrator pattern as #6.

8. **§4 food_allergies → gi_immune auto-populate.** v5 §B.4.2 calls for an auto-populate rule that Layer 1 could enforce. Design wave §3.2 placed responsibility on the write-path; if v2 surfaces inconsistency from real-athlete data, Layer 1 builder can be amended to emit a `Layer1Observation` (would land alongside §8 coaching-flag work).

9. **Layer 1 prompt body necessity.** §C free-text parsing (`longest_event_completed`, etc.) may need LLM judgment in v2 — see §2 boundaries. Defer to first real-athlete parsing case.

---

## 13. Test scenarios

Coverage shipped in `tests/test_layer1_builder.py` (19 tests, all green at 2026-05-19):

| Scenario | Test |
|---|---|
| Empty user — every section None or default | `TestEmptyUser.test_returns_layer1_payload_with_section_defaults` |
| Builder issues exactly 24 SELECTs | `TestEmptyUser.test_24_selects_issued` |
| `user_id=None` raises | `TestEmptyUser.test_user_id_required` |
| Identity scalars wire through | `TestFullyPopulated.test_identity_populated` |
| Injuries / medications split by status / stopped_at | `TestFullyPopulated.test_health_status_split_by_status` |
| `discipline_weighting` sum-to-100 invariant | `TestFullyPopulated.test_training_history_weighting_sum_validates` |
| Per-day windows + denormalized per-week capacity + Sunday=0 mapping + preferred-rest-day | `TestFullyPopulated.test_daily_windows_denormalize_per_week_capacity` |
| Sparse discipline baselines (some present, some None) | `TestFullyPopulated.test_discipline_baselines_partial` |
| Event-mode target wired | `TestFullyPopulated.test_event_goal_event_mode` |
| Multi-select CSV columns split (dietary_pattern, fueling_format_preference) | `TestFullyPopulated.test_lifestyle_multi_select_split` |
| Network links + linked-partner consents | `TestFullyPopulated.test_network_and_consents` |
| Disclosures latest-per-id dedup wires | `TestFullyPopulated.test_disclosures` |
| `.model_dump()` produces Layer-4-compatible dict | `TestFullyPopulated.test_layer4_dict_compatibility` |
| Strength benchmarks 1:1 populated | `TestFullyPopulated.test_strength_benchmarks_populated` |
| Performance scalars + test_dates | `TestFullyPopulated.test_performance_populated` |
| CSV edge cases (empty / whitespace / commas-only) | `TestCsvSplitting` |
| Weighting non-summing raises | `TestWeightingSumInvariant.test_non_summing_weights_raise` |
| Empty weighting valid | `TestWeightingSumInvariant.test_no_weighting_rows_is_valid` |

---

## 14. Gut check

**What this spec gets right:**
- Honest about scope: aggregation only, no judgment, no auto-populate, no caching.
- Reuses the existing `DailyAvailabilityWindow` typed shape from D-61 instead of inventing a parallel daily-window type.
- Keeps Layer 4 entry-point signatures unchanged (`dict[str, Any]`) — defers the typed-promotion blast radius to v2.
- Top-level convenience fields match exactly what Layer 4 reads today; section sub-models cover everything else without coupling to the current consumer.
- Closed-enum drift surfaces as a hard error, not a silent skip.

**Risks:**
- **24 SELECTs per build is more round-trips than strictly necessary.** A single CTE-joined SELECT would cut this to 1. Trade-off taken: builder simplicity + sparse-row tolerance + per-table test isolation. If Layer 4 entry-point latency telemetry (Step 8 carry-forward) shows Layer 1 read time dominating, revisit.
- **`available_days_per_week` derivation is by `enabled` count, not by intent.** A day with `enabled=True` + `window_duration_min=30` counts the same as one with 4-hour windows. Layer 4 reads this as a coarse signal; if downstream consumers need duration-weighted availability, the field should be renamed or supplemented.
- **`doubles_feasible` defaulting to `"no"` when storage is NULL** is an interpretation, not a verified rule. If a user has never filled the `daily_availability_windows` form (e.g., legacy account pre-D-61), `doubles_feasible='no'` may not match their actual capacity. Acceptable for v1; the form layer ensures `doubles_feasible` is set at onboarding completion.
- **Layer 1 prompt body deferral** is a real risk if `longest_event_completed` parsing turns out to need LLM judgment in real-athlete data. If it does, Layer 1 expands to an LLM-driven node and this spec's "pure aggregation" framing breaks.

**Best argument against this design:**
The 11 section sub-models add structural complexity that v1 Layer 4 doesn't consume. A minimal `Layer1Payload` with only the 6 top-level keys + opaque `dict[str, Any]` for the rest would ship cleaner. Counter: Phase 2 (Layer 2A-E builders) WILL consume the section sub-models; typing the full surface now saves a downstream typed-promotion later. The blast radius is contained to `layer4/context.py` extension; no Layer 4 callers change.

**What might be missing:**
- **No coverage of `body_metrics.vo2_max` observation-grade reads** — `Layer1Performance.vo2max` reads from `athlete_profile.vo2max` only. `body_metrics.vo2_max` is a separate observation-grade column that the spec doesn't currently surface; if Layer 3A wants observation-grade fitness signals, this is a gap. Defer until Layer 3A spec'd integration surfaces the need.
- **No coverage of `wellness_log` (live HRV / stress / body_battery samples)** — Layer 1 reads only the daily `wellness_self_report`. Provider-feed wellness data (`polar_continuous_hr_samples`, `coros_hrv_samples`, etc.) is consumed by Layer 3A's recent-trajectory window, not Layer 1.
- **No coverage of `training_log` / `cardio_log` aggregation** — current-weekly-volume (§C row 4) is described in the design wave as "derived at read time by Layer 1 builder" but this v1 implementation doesn't compute it (no consumer demands it yet). If Phase 5 orchestrator surfaces the need, fold into Layer 1.
- **No coverage of `coaching_preferences`** — v1 storage exists but Layer 1 doesn't read it. v2 derivation of `coaching_voice_preferences` (open item §12 #3) would surface this.

---

*End of `Layer1_Spec.md`.*
