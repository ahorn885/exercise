# V5 Implementation — Track 2 Determinism-First Layer 4 Synthesis: slice 2c shipped (rest + STRENGTH locale assign + LLM substitute fallback)

**Date:** 2026-06-06
**Branch:** `claude/sharp-euler-nGoV2`
**PR:** pending (this session)
**Issues:** Track 2 (#429) of the 3-track redesign epic #427. Spec `Layer4_DeterminismFirst_Synthesis_Design_v1.md` v1 (APPROVED). Slice 2c shipped this session; 2c.2 (cardio routing) + 2d + layer0 vocab adds still owed (see §5).

---

## ⚡ Diagnostic token (read first — every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` — WebFetch 403s (Vercel deployment protection); fetch via the **Vercel MCP `web_fetch_vercel_url`** tool. Untruncated runtime logs: Vercel dashboard (team `team_rkZGxltBw2ykWtrIPCYy16JZ`, project `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`); the runtime-log MCP truncates the message column (Rule #14).

---

## 1. What this session was

Andy named slice 2c as the next move after 2a + 2b shipped (PR #433, merged). Two key scope expansions happened mid-session via stop-and-ask:
1. **Andy directed cardio routing AND the §5.5 step 6 small-call LLM substitute both stay in 2c.** I implemented that scope, then discovered the cardio routing path required layer0 vocabulary adds Andy flagged (off-trail/bush; rename TRN-007). At that gate Andy approved pulling cardio routing back out → 2c.2 follow-up. Strength locale assignment + small-call LLM + rest detection + validator demotions shipped end-to-end.
2. Two stop-and-ask design gates resolved during execution (§3 below).

Suite 2024 → 2051 passed / 16 skipped (+27 new tests, two existing validator severity-assertion tests updated from blocker→warning).

## 2. Shipped

### 2.1 — `layer4/session_grid.py` extended with rest detection (§5.4)

```python
def expected_rest_count(phase_name: str, weekly_capacity_days: int | None = None) -> int:
def detect_insufficient_rest(sessions_in_week, expected, disabled_dates=None) -> InsufficientRestWarning | None:
```

- **Phase defaults** (`_PHASE_EXPECTED_REST_DAYS`): Base 2 / Build 2 / Peak 1 / Taper 2 — midpoints of the spec §5.4 ranges (Build 1–2, Taper 2–3).
- **Capacity clamp:** when `weekly_capacity_days` is supplied (the count of *enabled* days from `daily_availability_windows`), `expected_rest_count` subtracts already-disabled days from the phase target. Disabled days cover that portion of the rest contract automatically — no double-counting.
- **`detect_insufficient_rest`** treats the input as a 7-day calendar week regardless of how many sessions the LLM placed; days without non-rest sessions count as rest. Explicit `kind='rest'` sessions don't count as workload.
- **Tests:** 11 unit tests (`TestExpectedRestCount` × 6, `TestDetectInsufficientRest` × 5) covering phase defaults, capacity clamp, rest-session semantics, workload-density edge cases.

### 2.2 — `layer4/locale_assign.py` NEW (§5.5 pipeline)

Per-strength-session pipeline:

1. **Majority-fit locale pick** (§5.5 step 2-3): iterate cluster locales; pick the one where the most of the session's ideal-set `exercise_id`s are resolved at that locale. Ties → home; second tie → lowest-slug alphabetical (deterministic; haversine variant deferred until cardio routing lands).
2. **3-tier substitution ladder** per non-fitting exercise:
   - (a) **Pattern-match substitute** (`_pattern_match_substitute`) — finds tier-1/2 resolved exercise in chosen locale's pool sharing a movement_pattern with the original. Tier-3 (bodyweight) candidates filtered out — they're the next rung's job.
   - (b) **Tier-3 bodyweight proxy** (`_tier3_bodyweight_proxy`) — finds tier-0/3 resolved exercise sharing a movement_pattern. Mutates to `resolution_tier=3` + `proxy_origin_id` set.
   - (c) **Small-call LLM substitute** (`_invoke_llm_substitute`) — single-purpose Haiku call with enum-bounded `pick_substitute_exercise` tool (`substitute_exercise_id` enum = `locale_pool ∖ excluded_ids`; `preserves_intent` boolean signals when Haiku is reaching). Budget: ≤1 call per `assign_locales` invocation. In-memory cache key `(exercise_id, locale_id, hash(excluded_ids + pool_ids))`. Out-of-pool returns fall through to the next step. Model: `claude-haiku-4-5-20251001`.
   - (d) **Coaching-flag tail** — append `substitution_no_candidate` to the exercise's `coaching_flags`, keep the original (resolution_tier stays 1).

- **Pattern lookup correction:** the payload `StrengthExercise` does NOT carry `movement_patterns` (that's on the 2C `ResolvedExercise` side). `_build_cluster_resolved_index` builds a one-shot id→ResolvedExercise map across ALL locales in `layer2c_payloads`; the original exercise's patterns are looked up there (locale-agnostic per spec §5.5 step 1).
- **`LocaleAssignDiagnostic`** (Rule #14 observability): per-session `SessionAssignment`s + per-exercise `ExerciseSubstitution`s + `llm_calls` + `llm_total_latency_ms` + cluster IDs + home id. `to_metadata()` returns a JSON-safe dict for `synthesis_metadata` inclusion. Every decision is grep-prefixed `assign_locales:` in the logger.
- **LLM-substitute prompt** (Trigger #1 sign-off Andy 2026-06-06): tight system prompt; no periodization/week framing; states original's `movement_patterns` + `sport_priority` + excluded ids; instructs `preserves_intent=true` only when genuinely targeting the original's pattern.
- **Degraded pass-through:** any exception in `_apply_locale_assign` (e.g., db hiccup) logs a warning and returns the original payload unchanged. Locale-assign defects can never wedge plan generation.

### 2.3 — `layer4/orchestrator.py` wire-in

NEW `_apply_locale_assign(db, user_id, payload, layer2c_payloads)` runs OUTSIDE the cached engine on both `orchestrate_plan_create` and `orchestrate_plan_refresh`, taking the synthesized payload and returning a model_copy with assigned sessions. Locale edits already evict Layer 2C → Layer 4 cache → re-runs (per spec §9). Same call shape on both entry points.

**Note on the call site choice:** the spec §10 row implied `plan_create.py` + `plan_refresh.py` as call sites, but the orchestrator is the architectural fit — it's the only level that has both `db` and `user_id` in scope without expanding the synthesizer signatures. Documented in the spec §10 update.

### 2.4 — `layer4/validator.py` demotions + insufficient-rest emission

- `_rule_rest_spacing` (Rule 3): severity blocker → warning across both consecutive-hard cases.
- `_rule_schedule_violation` (Rule 11): severity blocker → warning.
- NEW `_append_insufficient_rest_warnings(out, payload, ctx)`: groups payload sessions by `(phase_name, ISO-year, ISO-week)`, computes `expected_rest_count(phase, enabled_days_from_ctx)`, runs `detect_insufficient_rest` per week. Emits one warning per (phase, ISO-week) with rest count below expected; rule_name format `insufficient_rest_<phase>_<iso_year>_<iso_week>`. Invoked at the top of `_rule_rest_spacing` — Rule 3 now covers both consecutive-hards and insufficient-rest under the same namespace, per spec §10 ("Rule 3 now wraps the deterministic `detect_insufficient_rest` warning").

### 2.5 — `layer4/__init__.py` re-exports

New public names: `assign_locales`, `LocaleAssignDiagnostic`, `SessionAssignment`, `ExerciseSubstitution`, `expected_rest_count`, `detect_insufficient_rest`, `InsufficientRestWarning`.

### 2.6 — Tests

- **NEW `tests/test_layer4_locale_assign.py`** — 14 tests:
  - `TestPickLocaleByMajorityFit` × 4 (single locale, higher fit wins, tie→home, alphabetical secondary tiebreak)
  - `TestSubstitutionLadder` × 4 (pattern-match substitute, tier-3 proxy when no pattern match, pattern-match preferred over proxy, coaching-flag tail when no candidate)
  - `TestLLMSubstituteFallback` × 4 (LLM called when pattern + tier-3 miss; budget=1 respected; out-of-pool defense; caller=None skips to flag)
  - `TestNonStrengthUntouched` × 1 (cardio session pass-through)
  - `TestDiagnosticMetadata` × 1 (to_metadata shape)
- **Extended `tests/test_layer4_session_grid.py`** — 11 tests for rest detection (above).
- **Updated `tests/test_layer4_validator.py`** — 2 severity-assertion tests renamed `_blocker` → `_warning` to reflect the demotions.
- **Final suite: 2051 passed / 16 skipped (+27 new tests).**

## 3. Stop-and-asks this session

1. **§5.5 step 6 small-call LLM substitute scope** (Andy 2026-06-06, CLAUDE.md Trigger #1): I presented "defer to 2c.2" vs "include in this slice" with prompt-design proposal. Andy picked "include in this slice." Then presented prompt-body options: I proposed a tight draft with `preserves_intent` honesty signal; Andy approved the draft.
2. **Cardio-session route-locale routing scope** (Andy 2026-06-06): originally pulled into 2c per Andy's first-pass call. Mid-implementation I surfaced two real issues that pushed it out: (a) no canonical TRN-xxx for off-trail/bush — the closest TRN-006 Fell/Moorland is heather/bog-specific; (b) TRN-007 should be renamed "Technical Rock/Scree" for clarity. Both are layer0 vocabulary changes (Trigger #3 cross-layer). Plus an open snow-sports semantics design call. Andy then directed pull cardio routing back out → 2c.2.
3. **Discipline→terrain map sign-off** (Andy 2026-06-06, Trigger #2-adjacent): I drafted a 17-of-21 disciplines map with 4 defaulting to home (D-002 Road Running, D-006 Road Cycling, D-007 TT Cycling, D-027 OCR). Surfaced uncertainty on TRN-011 / TRN-014 / TRN-017 (I had hallucinated TRN-017 as snow originally; canonical is 16-row set). Andy then directed the cardio pull-out (above), making the map an open table for 2c.2.
4. **Pattern-match exclusion of tier-3 candidates** (mid-implementation correctness fix): my first cut had pattern-match accepting any pattern-sharing exercise including tier-3 bodyweight; that collapsed the tier-3 proxy rung. Fixed by filtering tier-3 candidates out of `_pattern_match_substitute` — bodyweight is the next rung's job. Caught by `test_pattern_match_preferred_over_proxy`.
5. **Movement-pattern lookup path** (mid-implementation correctness fix): `StrengthExercise` payload doesn't carry `movement_patterns` (it's on the `ResolvedExercise` side). First cut returned empty patterns for every original → ladder collapsed to coaching-flag tail. Fixed by building `cluster_resolved_index` from the union of all `layer2c_payloads` and looking up the original's patterns there (locale-agnostic per spec §5.5 step 1). Caught by 4 substitution-ladder tests at once.

## 4. Owed (Andy's hands)

> Slice 2c is pure-function + post-synth — no schema DDL. The slice-2a/2b cold PGE plan run (owed since the 2a+2b session) is the same proof + now ALSO covers 2c. New addition: confirm the `synthesis_metadata.track2_slice2c_locale_assign` block appears in the diag JSON.

1. **Re-run a cold PGE plan.** The same win condition Tracks 1 + slices 2a + 2b owed PLUS slice 2c's:
   - **From slice 2c (NEW):** the diag JSON's per-block `synthesis_metadata` should include the `track2_slice2c_locale_assign` block with `session_count`, `cluster_locale_ids`, `home_locale_id`, and `assignments[]`. Most strength sessions should show `path=kept` (your equipment fits); any substitutions should show the path taken (`pattern_match` / `tier3_proxy` / `llm_substitute` / `no_candidate`). The `llm_substitute_calls` counter should be 0 or very low (the deterministic ladder catches the typical case).
   - **From slice 2c rest detection:** if a week's rest count is below expected for the phase, the validator's `validator_failures_by_rule` should show an `insufficient_rest_<phase>_<iso_year>_<iso_week>` row with `severity=warning`.
   - **From slice 2c demotions:** any `rest_spacing_*` or `schedule_violation_*` rows in the diag should be `severity=warning`, not blocker.
2. **(Optional)** poke the per-phase `_PHASE_EXPECTED_REST_DAYS` in `layer4/session_grid.py` if the rest contract feels off in practice for PGE phases — these are coach-estimate defaults.

## 5. Next move

- **Slice 2d (final slice of Track 2):** `rx_engine` post-hoc wiring (`layer4/rx_wire.py` NEW; first-exposure deterministic RPE template) + the remaining §8 validator demotions (Rules 2 / 7 / 7b). Per spec §7. Track 3 dependency note: `rx_engine` reads `public.exercise_inventory`; Track 3 moves to `layer0.*`. Until Track 3 ships, rx lookups limited to the public catalog subset — layer0-only exercises fall through to first-exposure (acceptable v1 behavior).
- **Slice 2c.2 (parallel/after layer0 vocab):** cardio-session route-locale routing. Extend `assign_locales` with `_DISCIPLINE_REQUIRED_TERRAINS` map + nearest-cluster-locale lookup. Gated on the layer0 vocab adds below.
- **Layer 0 vocab adds (Andy 2026-06-06, slice 2c follow-up):**
  - NEW `TRN-017` row "Off-Trail / Bush" — overland nav through unmaintained brush.
  - RENAME `TRN-007` "Technical Rock" → "Technical Rock/Scree".
  - Trigger #3 cross-layer. Own micro-PR: `etl/layer0/extractors/vocabulary.py` + ETL migration + Neon re-run + Layer0_ETL_Spec edit.
- **Snow-sports routing semantics** (Andy 2026-06-06, open design call): D-018 Mountaineering route on Mountain/Alpine (TRN-005) OR Snow/Winter Alpine (TRN-012), or snow-only? Resolve before 2c.2 locks the map.
- **Track 3 (#430) — D-52 catalog migration** (parallel/after Track 2): retire `public.exercise_inventory`/`exercise_equipment`/`equipment_items` → `layer0.*`; restores the v1 references/purchases surfaces degraded in Track 1. Also unblocks the discipline→required_terrain layer0 column lift.

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (slice 2c.2 + 2d + layer0 vocab pending)
4. This handoff (diagnostic token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Slice 2c shipped, spec status updated | `aidstation-sources/Layer4_DeterminismFirst_Synthesis_Design_v1.md` | `grep -n "Slice 2a + 2b + 2c shipped" Layer4_DeterminismFirst_Synthesis_Design_v1.md` |
| Locale-assign pipeline | `layer4/locale_assign.py` | `grep -n "def assign_locales\|def _pick_locale_by_majority_fit\|def _pattern_match_substitute\|def _tier3_bodyweight_proxy\|def _invoke_llm_substitute" layer4/locale_assign.py` |
| Small-call LLM tool schema + prompt | `layer4/locale_assign.py` | `grep -n "pick_substitute_exercise\|_llm_substitute_tool_schema\|_build_llm_substitute_prompt\|claude-haiku-4-5-20251001" layer4/locale_assign.py` |
| Rest detection extensions | `layer4/session_grid.py` | `grep -n "def expected_rest_count\|def detect_insufficient_rest\|_PHASE_EXPECTED_REST_DAYS\|class InsufficientRestWarning" layer4/session_grid.py` |
| Validator demotions | `layer4/validator.py` | `grep -n "Track 2 slice 2c: demoted to warning" layer4/validator.py` (2 hits expected — Rules 3 and 11) |
| Insufficient-rest emission wired into Rule 3 | `layer4/validator.py` | `grep -n "_append_insufficient_rest_warnings\|insufficient_rest_" layer4/validator.py` |
| Orchestrator wire-in | `layer4/orchestrator.py` | `grep -n "_apply_locale_assign" layer4/orchestrator.py` (3 hits expected — def + 2 call sites) |
| `__init__.py` re-exports | `layer4/__init__.py` | `grep -n "assign_locales\|expected_rest_count\|InsufficientRestWarning" layer4/__init__.py` |
| Test coverage | `tests/test_layer4_locale_assign.py`, `tests/test_layer4_session_grid.py` | full suite 2051 passed / 16 skipped (+27) |

## 7. Mechanically-applicable deferred edits

None at slice-2c scope. The 2c.2 cardio routing requires the layer0 vocab adds first; that's a separate spec-first session.

## 8. Cardio routing map (drafted, NOT locked — slice 2c.2 input)

For the next session that picks up 2c.2, the v1 draft of `_DISCIPLINE_REQUIRED_TERRAINS` (17 of 21 mapped; 4 default to home):

| Discipline | Required terrains |
|---|---|
| D-001 Trail Running | TRN-002 Groomed Trail, TRN-003 Technical Trail, TRN-004 Hill/Rolling |
| D-002 Road Running | *(default home — treadmill-OK)* |
| D-003 Trekking | TRN-002, TRN-003, TRN-004, TRN-005 Mountain/Alpine |
| D-004 Swimming | TRN-008 Pool, TRN-009 Flat Water, TRN-010 Open Water/Ocean |
| D-006 Road Cycling | *(default home — trainer OK)* |
| D-007 TT Cycling | *(default home — trainer OK)* |
| D-008 Mountain Biking | TRN-002, TRN-003, TRN-015 Pump Track |
| D-009 Packrafting | TRN-009, TRN-010, TRN-011 Whitewater |
| D-010 Kayaking | TRN-009, TRN-010, TRN-011 |
| D-011 Canoeing | TRN-009, TRN-011 |
| D-012 Rock Climbing | TRN-013 Rock Wall (Outdoor), TRN-014 Climbing Gym |
| D-013 Abseiling | TRN-013, TRN-014 |
| D-014 Via Ferrata | TRN-005, TRN-013 |
| D-017 Snowshoeing | TRN-012 Snow/Winter Alpine |
| D-018 Mountaineering | TRN-005, TRN-012 *(snow-sports semantics open — see §5)* |
| D-019 Paddle Rafting | TRN-009, TRN-011 |
| D-021 Uphill Skinning | TRN-012 |
| D-022 Alpine Descent | TRN-012 |
| D-024 Mountain Running | TRN-002, TRN-003, TRN-004, TRN-005 |
| D-027 OCR | *(default home)* |
| D-028 Cross-Country Skiing | TRN-012 |

**Gaps to resolve before locking** (named in §3 / §5):
- Add **TRN-017 "Off-Trail / Bush"** to layer0; potentially extend D-003 Trekking, D-018 Mountaineering rows.
- Rename **TRN-007 → "Technical Rock/Scree"**; potentially extend D-018 Mountaineering, D-024 Mountain Running rows.
- Resolve **D-018 Mountaineering snow-vs-rock OR-match** semantics.
