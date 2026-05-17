# V5 Implementation — Layer 4 Step 3 (PR-C of E) Spec Amendments Closing Handoff

**Session:** Single chat. First of three PRs (C/D/E) closing `Layer4_Spec.md` §14.3.4 Step 3 — deterministic validator harness. PR-C ships `§5.4 spec amendments + 3 new D-rows (D-66/D-67/D-68)`; PR-D ships upstream context schemas; PR-E ships the validator code itself.
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_Layer4_Step2_PR_B_Migration_Hashing_Closing_Handoff_v1.md` (Step 2 PR-B — `plan_versions` migration + canonical-JSON + cache-key helpers).
**Branch:** `claude/layer4-migration-hashing-XYE4x` (harness-pinned — name mismatches scope per the PR-B precedent; same Andy 2026-05-17 confirm-as-is decision).
**Status:** 🟢 1 substantive spec edit + 3 bookkeeping files. 159 pytest cases still green (no code change). PR ready to open.

---

## 1. Session-start verification (Rule #9)

Predecessor (Step 2 PR-B) handoff §7 claimed: `init_db.py` `_PG_MIGRATIONS` has `plan_versions` (line 1086+); `layer4/hashing.py` exports `canonical_json` + 4 cache-key builders + 4 helpers; `layer4/__init__.py` re-exports all 9 hashing names; `tests/test_layer4_hashing.py` 94 tests pass; combined 159 tests pass; `aidstation-sources/CLAUDE.md` Backlog ref reads `Project_Backlog_v40.md`; PR-B substantive commit `2a5d221` pushed to `origin/claude/implement-payload-closing-JfYd7`; PR #69 merged into main at `c974cac`.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` `_PG_MIGRATIONS` has `plan_versions` table CREATE | grep `plan_versions` returns line 1086 | ✅ |
| `layer4/hashing.py` exists (9029 bytes) | `ls -la layer4/hashing.py` | ✅ |
| `layer4/__init__.py` re-exports 9 hashing names | grep canonical_json + compute_payload_hash + 4 cache-key builders + 3 bundle helpers | ✅ |
| `tests/test_layer4_hashing.py` exists (18915 bytes) | `ls -la tests/test_layer4_hashing.py` | ✅ |
| 159 pytest cases pass in 0.26s | `pytest tests/` after `pip install pytest pydantic` | ✅ |
| `aidstation-sources/Project_Backlog_v40.md` exists | `ls aidstation-sources/Project_Backlog_v*.md` | ✅ |
| `aidstation-sources/CLAUDE.md` reads "Backlog: Project_Backlog_v40.md" | grep | ✅ |
| PR #69 merged on `origin/main` at `c974cac` | `git log --oneline -10` | ✅ |
| Working tree clean | `git status` | ✅ |
| No drift between handoff narrative and on-disk state | Rule #9 reconciliation | ✅ |

**No drift found.** PR-B state on disk matches the handoff narrative exactly. Branch is harness-pinned `claude/layer4-migration-hashing-XYE4x` (the PR-B handoff §5 recommended `claude/layer4-validator-NEWSUFFIX` for the next session; harness override applied; Andy confirmed leaving the harness-pinned name as-is at session start — same precedent as the PR-A → PR-B transition).

---

## 2. Session narrative — Andy-driven scope expansion, two contract gaps surfaced, three D-rows added

Andy opened with a URL pointer to the PR-B closing handoff and "lets work". I followed §5 operating notes — re-read CLAUDE.md, ran Rule #9 verification, reported state + next focus + drift (none). Andy then asked me to detail the scope rather than just citing docs he can't see.

### 2.1 The plan-mode discussion that defined PR-C scope

Mid-session, what was scoped as a small "tune two validator thresholds and start the validator harness" became a meaningful scope expansion as Andy surfaced architectural gaps the spec hadn't addressed. The session sequence:

1. **Volume thresholds.** Andy bumped `volume_band_*` blocker ±15→±20%, warning ±5→±10%. Rationale: weekly endurance volume naturally fluctuates ±10% from weather/schedule/recovery; tighter thresholds produced too many false-positive blockers. Settled in one exchange.
2. **Rule 6 — nearby locations clarification.** Andy asked "is this also testing the nearby locations? it should be. but it should also test that all of the equipment is available at a single location. we don't want a workout that is mostly home gym then tosses in a leg press exercise because the local gym location has it available." My first draft replied "Nearby alternatives are NOT auto-substituted" — wrong. Andy corrected: nearby locations ARE accepted by default per the whole purpose of the locale cluster (athlete's profile holds a cluster of locales — home + nearby gym + crag + etc., and a workout proposing to use any of them is fair game); the constraint is single-locale WITHIN a session, not across sessions. EXCEPTION: if the athlete sets a per-date "at home only" restriction, that overrides. Revised PR-C rule 6 splits into 6a (resolves at picked locale) + 6b NEW (single-locale invariant within session) + 6c NEW (locale must be in athlete cluster; D-67 locale-lock when set).
3. **D-66 race-event data model.** Rule 12 `kit_manifest_inputs_incomplete` checks for `equipment_overrides` on route locales (TAs, aid stations, drop bags). I verified: v1 app has `target_event_name` + `target_event_date` text columns only; no table for race route locales, no UI to enter them. The race-week-brief design assumes inputs that don't have database backing yet. Surfaced as new D-row.
4. **D-68 hotel-gym fallback.** I raised the related gap: when athlete travels to a hotel not in our database, Layer 2C equipment view is empty, synthesizer can't propose workable exercises, rule 6a fires aggressively. Andy picked the **hybrid (a + prompt)** path: Layer 0 ships category-default equipment profiles + Layer 2C falls back to them + orchestrator nudge prompt asks athlete to confirm/edit. **Critical invariant (Andy 2026-05-17):** category defaults are transient resolution-only — they NEVER write to `locale_equipment_overrides` or persist on the locale profile. Athlete confirmation via nudge prompt is the only mechanism by which defaults become real profile data.
5. **D-67 per-date athlete restrictions.** Andy raised: "the d66 sibling SHOULD have been scoped in the original documents. Options for 'no outdoors' (for example: at home is fine, the gym is fine, but no mountain biking). 'at [current location] only' (for example, use only the home gym that day, none of the rest of the cluster." Then: "we should do the indoor only and time limitation now. not put off. single row." 4 restriction types collapse into one D-row: locale_lock + discipline_exclusions + indoor_only + max_total_minutes (per-date time cap). 4 Layer 4 validator rules absorb D-67 inputs.
6. **ACWR vs injury lookback — crossed wires resolved.** I had flagged that ACWR rule's chronic denominator window wasn't spec'd. Andy answered with injury-lookback policy (chronic conditions always; past injuries surface for as long as recovery-window literature supports; open/unresolved always count). I gently clarified — that's the injury rule (#7), settled in 3A; ACWR (#2) is workload, separate question. Andy: "1. my bad - agree w suggestion" → **28-day chronic window per Gabbett 2016** locked in.

### 2.2 Stop-and-ask triggers fired

- **Trigger #5** (schema/inter-layer-contract amendments) — fired on §5.4 rule table edits. Routed through plan-mode discussion in chat before applying. Per the Andy 2026-05-17 amendment-authoring directive, amendment authoring goes through `/plan` mode even when the substantive design pick is settled.
- **Trigger #11** (new D-rows with cross-layer scope) — fired three times (D-66 + D-67 + D-68). All three are genuinely cross-layer (Layer 0 + Layer 1 + Layer 2A + Layer 2C + Layer 4 + onboarding UI + profile UI in various combinations). Routed through the same plan-mode discussion.

### 2.3 Architectural design wave gaps acknowledged on the record

The §14 retrospective (shipped 2026-05-17, predecessor-of-predecessor) surfaced "what might be missing" as joint sessions + Layer 5 contract + D-57 + post-race surface + brief-diff renderer + §7.12 phase_metadata override-pass-through + §5.4 rule rows + opportunity expansion + seam-reviewer concurrency. **It did NOT catch the per-date-restriction or unknown-equipment seams.** Both surfaced during this session's PR-C planning exchange.

Add to gut-check learnings for the next major spec lands: locale-system seams are easy to miss because they cross the Layer 1 / Layer 2C / Layer 4 boundaries and feel like "implementation details" until they bite. Three of the eight Layer 4 validator rules touch locale-cluster semantics (6a + 6b + 6c + 11 + plus rules 6c/9/17/18 reference D-67) — that's load-bearing surface area the retrospective didn't audit. Future spec retros should specifically audit locale-system seams.

### 2.4 No silent judgment calls this session

PR-A and PR-B both had architectural deviations on the record (PR-A: pydantic v2 BaseModel + branch off main + extra='forbid' default. PR-B: sort-key extension for `compute_prior_plan_session_window_hash` + strict {a,b,c,d,e} validation in `compute_layer2_bundle_canonical_hash`). PR-C has zero — every threshold + every rule split + every D-row scope was settled with Andy in-session via the plan-mode discussion before any spec edit was applied.

---

## 3. Files shipped this session

One commit on `claude/layer4-migration-hashing-XYE4x` — substantive spec edit + bookkeeping bundled (precedented by PR-A 8-file + PR-B 7-file bundles).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Layer4_Spec.md` | Modified | §5.4 amendments: 6 surgical edits + 1 new rule row + 1 closing-tolerance-paragraph edit + 1 new D-66/67/68 summary block. See §4.1 below. |
| 2 | `aidstation-sources/Project_Backlog_v41.md` | New | Copy of v40 + new v41 file-revision-header entry + 3 new D-rows (D-66 + D-67 + D-68) appended after D-65. v40 demoted inline as most-recent predecessor. |
| 3 | `aidstation-sources/CLAUDE.md` | Modified | Layer 4 pipeline row updated ("Step 3 PR-C of E landed 2026-05-17"); last-shipped narrative replaced with PR-C summary (PR-B demoted to predecessor); Backlog ref v40 → v41; authoritative-current-files Layer 4 line updated to note §5.4 amendments + Step 3 in-progress; Next-forward-move points at Step 3 PR-D context schemas. |
| 4 | `aidstation-sources/handoffs/V5_Implementation_Layer4_Step3_PR_C_Spec_Amendments_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**4 files total. Under the 5-file ceiling.** No code changes — PR-C is spec-only.

---

## 4. What the spec now commits to

### 4.1 `Layer4_Spec.md` §5.4 amendments

The rule table now contains 18 rows (was 17 after the v38 C1 amendment; +1 new for `indoor_only_violation_*`). Two rules amended with new threshold/window values; one rule split into 3 sub-rules; four rules carry D-66 / D-67 / D-68 forward-pointer annotations; one new rule added; closing tolerance paragraph and a new D-66/67/68 summary block round out the section.

**Threshold/window changes (immediate effect — applied by the v1 validator):**

- `volume_band_*` — ±15%/±5% → **±20%/±10%** (Andy 2026-05-17). Weekly endurance volume naturally fluctuates ±10% from weather/schedule/recovery; tighter thresholds produced too many false-positive blockers. To tune post-launch per measured retry rates.
- `acwr_*` — chronic denominator clarified to **trailing 28-day window** per Gabbett 2016 (acute = trailing 7d). Spec previously didn't state the window explicitly; v1 validator now codifies it.

**Rule 6 split (was one row; now three sub-rules):**

- **6a `equipment_unavailable_*`** — Existing semantics, clarified wording: every prescribed exercise / cardio sport-equipment requirement resolves in `PlanSession.locale_id`'s effective equipment view (per 2C resolution tiers). Tier-3 proxy substitution allowed; raw unavailable is a blocker. **Pre-D-68 annotation:** locales without `equipment_overrides` resolve to empty pool and rule fires aggressively on travel paths. Post-D-68: Layer 2C falls back to the locale-category default for synthesis input only; default never persists to locale state.
- **6b NEW `session_multi_locale_*`** — All `cardio_blocks[].exercise_id` + `strength_exercises[].exercise_id` within a single `PlanSession` must resolve at the same `locale_id`. No mid-session location swaps. If a critical exercise only resolves at the local gym, the whole session moves to the local gym. Severity: `blocker`. **Important nuance:** this is the WITHIN-session invariant; the BETWEEN-session locale picking is governed by 6c.
- **6c NEW `session_locale_not_in_cluster_*`** — `PlanSession.locale_id` is in the athlete's saved locale cluster — full cluster fair game by default (athlete's primary + nearby + travel-time locales). The whole point of the nearby-locations function is letting workouts use nearby gyms, not just primary home. **Pre-D-67 annotation:** no per-date narrowing; full cluster always allowed. Post-D-67: when a date has a `locale_lock` restriction set, `locale_id` MUST equal that locked locale. Severity: `blocker`.

**Existing rules extended with D-67 branches:**

- `discipline_excluded_*` (rule 9) — Existing semantics (discipline_id must be in 2A discipline_inclusion). Extended with D-67 branch: also fails when `discipline_id` is in the date-scoped `discipline_exclusions` restriction set (athlete-set per-date "no MTB today" / "no outdoors today" filter).
- `daily_window_fit_*` (rule 17) — Existing semantics (session duration ≤ available `daily_availability_windows` minutes for the date). Extended with D-67 branch: also fails when the sum of session durations on `date` exceeds the date-scoped `max_total_minutes` restriction set by the athlete (per-date time cap, e.g., "≤30min only today").

**Existing rule with D-66 always-warn annotation:**

- `kit_manifest_inputs_incomplete` (rule 12) — Pre-D-66 (race-event data model): this rule effectively always-warns on multi-day events because athletes have no UI to populate route-locale `equipment_overrides` for transition areas / aid stations / drop bags. The warning + `data_gap` observation are correct behavior; rule remains active for forward-compatibility with D-66.

**NEW rule:**

- `indoor_only_violation_*` — When a date has D-67 `indoor_only=True` set by the athlete, the session's `locale_id` must resolve to an indoor-classified locale category (home_gym, hotel_gym, commercial_chain_gym, independent_gym, climbing_gym_chain, climbing_gym_indie, pool_indoor, other_residence) AND the session's `discipline_id` must be in the indoor-disciplines set (excludes MTB-outdoor, trail running, outdoor rock climbing, packrafting, etc.). **Pre-D-67:** no per-date restrictions; rule always passes. Severity: `blocker`. Indoor/outdoor locale-category and discipline classifications live in the D-67 design wave alongside the restriction data model.

**Closing changes:**

- Tolerance-defaults paragraph updated to reflect new ±20%/±10% volume thresholds + 28-day ACWR window.
- New summary block after the rule table enumerates the 4 D-67-dependent rule branches that ship in v1 validator harness but no-op until D-67 lands (defensive forward-compatibility — none block PR-E landing).

### 4.2 Three new D-rows (Project_Backlog_v41.md)

**D-66 — Race-event data model** (Med severity, 🟡 Deferred design wave).
- Scope: new `race_events` table (race_format enum {single_day, expedition_ar, stage_race, multi_day_ultra}, distance_km, total_elevation_gain_m, race_rules_summary, mandatory_gear_text, etl_version_set JSONB) + new `race_route_locales` table (race_event_id, locale_id FK, role enum {start, transition_area, aid_station, drop_bag_point, bivvy, finish, other}, sequence_idx, mile_marker) + onboarding step prompt + profile/race-event edit UI + per-route-locale `equipment_overrides` enabled.
- Affects: Layer 1 §H race info (extends); Layer 2C (extends with route-locale category); Layer 4 race-week-brief consumer (§3.4 + §7.13 + §7.14 inputs); onboarding §A target-race step (extends); profile/race-event edit UI (new).
- Defer trigger: lands when Step 4e race-week-brief implementation approaches per §14.3.4 — or earlier if Andy's Pocket Gopher Extreme 2026 race-week (July 17–19, 2026) pulls it forward.
- Closes the rule-12 always-warn case for multi-day events.

**D-67 — Per-date athlete restrictions** (Med severity, 🟡 Deferred design wave).
- Scope: new `daily_restrictions` table (athlete_id, date, locale_lock TEXT NULL, discipline_exclusions TEXT[] NULL, indoor_only BOOLEAN, max_total_minutes INT NULL, UNIQUE(athlete_id, date)) + locale-category indoor/outdoor classification on Layer 0 `MANUAL_CATEGORIES` + discipline indoor/outdoor classification (likely in Layer 0 `disciplines` table — extend `discipline_attributes` JSONB or new `is_indoor BOOLEAN` column) + onboarding/profile UI (schedule tab gains per-date overlay; session-card override modal) + D-64 T1 plan refresh hook fires on restriction change for impacted future dates.
- **Single D-row covers 4 restriction types** (locale_lock + discipline_exclusions + indoor_only + max_total_minutes) since they share one UX surface and one Layer 4 consumption shape. Indoor-only is the derived shortcut combining locale-category filter + discipline-category filter.
- Affects: Onboarding §G + profile schedule tab (extends — per-date restrictions UI); new `daily_restrictions` table; Layer 4 validator (4 rule branches active when restrictions present); 2C locale-category metadata (extends — needs indoor/outdoor classification); 2A discipline-classification metadata (extends — needs indoor/outdoor classification per discipline).
- Defer trigger: lands when athlete-2 onboarding pushes a real travel-week regression OR concurrent with D-66 design wave.

**D-68 — Default equipment profile per locale category — hotel-gym / unknown-equipment fallback** (Med severity, 🟡 Deferred design wave).
- Scope: new Layer 0 table `locale_category_default_equipment` (category TEXT FK to `MANUAL_CATEGORIES` enum, equipment_canonical_name TEXT FK to `layer0.equipment_items.canonical_name`, confidence enum {high, medium, low}, etl_version_set JSONB, source_evidence TEXT, UNIQUE(category, equipment_canonical_name)) + curation pass per the 8 `MANUAL_CATEGORIES` buckets (LLM drafts initial set, Andy reviews + locks per Layer 0 convention) + Layer 2C resolution update (3-tier fallback: overrides → category default → empty + `data_gap` observation) + orchestrator nudge UX on session-card render when session's equipment came from a category default.
- **Critical invariant (Andy 2026-05-17):** category defaults are transient resolution-only — they NEVER write to `locale_equipment_overrides` or persist on the locale profile. Athlete confirmation via the nudge prompt is the only mechanism by which defaults become real profile data.
- 3 sub-decisions deferred to the D-68 design wave: (a) source authority for the defaults (LLM-only / LLM + HITL like Layer 0 sport rule sets / curated table); (b) fallback gracefulness when a category default exists but is wrong for this specific locale (low-confidence flag? always emit `data_gap` even on category-default hit? user-suppressible "stop asking" toggle?); (c) prompt-UX policy (always-prompt-on-fallback / prompt-on-first-use-of-default-per-locale-per-athlete / no-prompt + passive data collection from logged sessions).
- Affects: Layer 0 reference data (new table); Layer 2C resolution algorithm; Layer 4 synthesis (consumes the richer 2C output; no code change beyond reading); orchestrator nudge prompt (new UX); D-58 nudge framework (extends — share the `account_nudges` infrastructure?).
- Defer trigger: lands when v5 onboarding implementation approaches OR when athlete-2 hotel-week regression surfaces (whichever is earlier; Andy's own travel cadence may pull it forward).

---

## 5. Next session pointers — Step 3 PR-D + PR-E

Architect-recommended next per `Layer4_Spec.md` §14.3.4 step 3 + `CLAUDE.md` "Next forward move":

### Step 3 PR-D scope: upstream-layer context schemas (5 files projected)

New `layer4/context.py` defining typed pydantic v2 `BaseModel` payloads for the 8 upstream-layer inputs the validator consumes:

1. **`Layer2APayload`** — per `Layer2A_Spec.md` §7. Fields: `disciplines: list[DisciplineAssignment]`, `discipline_inclusion: set[str]`, `phase_load_bands: dict[str, dict[Phase, LoadBand]]` (keyed by discipline_id → phase → (low_hrs, high_hrs)), `rationale: str`, `hitl_required: bool`.
2. **`Layer2CPayload`** — per `Layer2C_Spec.md` §7. Per-locale. Fields: `locale_id: str`, `effective_equipment: list[str]` (canonical equipment names), `resolved_exercises: list[ResolvedExercise]` (exercise_id, tier {1/2/3-proxy}, substitute_for), `sport_compatibility: dict[str, bool]` (discipline_id → available_at_this_locale).
3. **`Layer2EPayload`** — per `Layer2E_Spec.md` §7. Fields: `daily_calorie_target: int`, `macro_split_per_phase: dict[Phase, MacroSplit]`, `race_day_fueling: RaceDayFuelingTier` (cho_g_per_hr_low/high, sodium_mg_per_hr, fluid_ml_per_hr), `sleep_dep_overlay: SleepDepOverlay | None`, `heat_acclim_overlay: HeatAcclimOverlay | None`.
4. **`Layer3APayload`** — per `Layer3_3A_Spec.md` §7. Fields: `athlete_state: AthleteState` (readiness, fatigue, motivation), `active_injuries: list[ActiveInjury]` (body_part, restriction_text, severity — 3A handles the lookback union of chronic + still-open + recent-within-recovery-window per Andy 2026-05-17), `weak_links: list[str]`, `data_density: DataDensity`, `notable_observations: list[Observation]`.
5. **`Layer3BPayload`** — per `Layer3_3B_Spec.md` §7. Fields: `goal_viability: Viability` (realistic / stretch / unrealistic), `phase_boundaries: list[PhaseBoundary]` (phase_name, start_date, end_date), `intensity_distribution_per_phase: dict[Phase, IntensityDistribution]`, `periodization_shape: str`, `notable_observations: list[Observation]`.
6. **`DailyAvailabilityWindow`** — from onboarding §G. Fields: `day_of_week: int` (0–6), `windows: list[Window]` (start_time, end_time, max_minutes), `available: bool`.
7. **`RaceEventStub`** — minimal v1 pending D-66. Fields: `event_name: str`, `event_date: date`, `race_format: Literal['single_day','expedition_ar','stage_race','multi_day_ultra']`, `event_locale_id: str | None`, `race_rules_summary: str | None`. NOTE: `route_locales[]`, `segments[]`, `transitions[]` all deferred to D-66.
8. **`PerDateRestriction`** — placeholder pending D-67. Fields: `date: date`, `locale_lock: str | None` (locale_id), `discipline_exclusions: set[str]` (discipline_ids), `indoor_only: bool`, `max_total_minutes: int | None`. v1 always-empty until D-67 ships.

Plus `tests/test_layer4_context.py` (~30 tests — happy-path per payload × 8 + extra='forbid' rejection × 8 + JSON round-trip × 4 + cross-field validation × 6). Plus re-exports in `layer4/__init__.py`. Plus closing handoff. Plus Project_Backlog v41 → v42 bump.

**5 files projected; under ceiling.**

**Stop-and-ask risk:** None expected. Context schemas are derived directly from already-shipped upstream specs — no new design calls. If a spec field is ambiguous or a cross-field validator decision surfaces, route through `/plan` mode per the directive.

### Step 3 PR-E scope: deterministic validator harness (4 files projected)

New `layer4/validator.py` with:
- `ValidatorContext` (bundles all 8 upstream payloads from PR-D)
- `validate_layer4_payload(payload, context, pass_index=0) -> ValidatorResult` driver
- 18 rule functions (each `_rule_*(payload, ctx) -> list[RuleFailure]`):
  - `_rule_volume_band` (post-PR-C ±20/±10)
  - `_rule_acwr` (post-PR-C 28-day chronic)
  - `_rule_rest_spacing`
  - `_rule_intensity_dist`
  - `_rule_two_per_day`
  - `_rule_equipment_resolves_at_locale` (6a)
  - `_rule_single_locale_per_session` (6b NEW)
  - `_rule_session_locale_in_cluster` (6c NEW — D-67-aware)
  - `_rule_injury_violation`
  - `_rule_schedule_violation`
  - `_rule_discipline_excluded` (D-67-aware)
  - `_rule_sport_locale_incompatible`
  - `_rule_taper_phase_intent_violation`
  - `_rule_kit_manifest_inputs_incomplete` (D-66-aware)
  - `_rule_race_plan_segments_unordered`
  - `_rule_fueling_strategy_2e_tier_mismatch`
  - `_rule_contingency_anchor_category_missing`
  - `_rule_phase_date_out_of_range`
  - `_rule_daily_window_fit` (D-67-aware)
  - `_rule_indoor_only_violation` (NEW — D-67-aware)
- (That's 19 functions because rule 6 split adds two new rules + indoor_only is new — re-count: 17 from the original §5.4 post-C1 amendment + 6b + 6c + indoor_only = 20. Adjust during PR-E implementation.)

Plus `tests/test_layer4_validator.py` (~110 tests — per rule: 1 happy-path + 1 blocker case + 1 warning case where both severities exist + 1 mode-gated no-op + boundary tests on numeric thresholds; parametrized boundary tests; per-mode coverage). Plus re-exports + closing handoff.

**Mode-gating policy (settled this session):** Each rule function checks `payload.mode` at entry and returns `[]` if not applicable. Driver iterates all rules. Saves a per-mode dispatch table.

**Missing-input policy (settled this session):** Soft (`Observation(category='data_gap')`) when input is missing-but-tolerable (e.g., `ctx.layer2e is None` on a multi-day-race rule); `ValueError` when input must always be present (e.g., `ctx.layer2a.discipline_inclusion` empty is a caller bug).

**Stop-and-ask risk:** Should be low after PR-C amendments. If any rule's pseudo-code surfaces real ambiguity that wasn't resolved in PR-C, route through `/plan` mode per the directive.

### Operating notes for next session

1. **First re-read** (Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load. Rule #9 verification needs the full CLAUDE.md context.
2. **Second re-read**: this handoff.
3. **Third re-read**: `Layer4_Spec.md` §5.4 (full post-amendment rule table — this is what PR-E will implement) + §7 (payload schema PR-D context schemas plug into) + the 5 upstream-layer specs that PR-D context schemas mirror (`Layer2A_Spec.md` §7, `Layer2C_Spec.md` §7, `Layer2E_Spec.md` §7, `Layer3_3A_Spec.md` §7, `Layer3_3B_Spec.md` §7).
4. **Branch:** stay on `claude/layer4-migration-hashing-XYE4x` (harness-pinned through the Step 3 PR series — same precedent as PR-B → PR-C) OR cut a new branch off the post-PR-C merged main, whichever the harness pins.
5. **Test convention:** put `test_layer4_context.py` at top-level `tests/` alongside `test_layer4_payload.py` + `test_layer4_hashing.py` (matches PR-A + PR-B + PR-C convention; PR-C had no test changes).
6. **No D-67 / D-68 / D-66 design wave kicks off** in PR-D or PR-E — those land later. PR-D ships the placeholder shapes (`RaceEventStub` + `PerDateRestriction` minimal-v1) so the validator code can wire against them.
7. **Stop-and-ask trigger #5:** §5.4 is now amended; PR-E should NOT surface contract gaps. But if a rule's pseudo-code surfaces a real interpretation question, route through `/plan` mode per the Andy 2026-05-17 amendment-authoring directive.

---

## 6. Open items / decisions pinned this session

### 6.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | `volume_band_*` thresholds widened to ±20% blocker / ±10% warning | Andy 2026-05-17 | Weekly endurance volume naturally fluctuates ±10% from weather/schedule/recovery; tighter thresholds produced too many false-positive blockers. To tune post-launch. |
| 2 | `acwr_*` chronic denominator = trailing 28 days | Andy 2026-05-17 (settled after I clarified ACWR vs injury-lookback) | Standard per Gabbett 2016. Tune post-launch per measured retry rates. |
| 3 | Rule 6 split: 6a equipment-resolves + 6b single-locale-per-session + 6c locale-in-cluster | Andy 2026-05-17 (corrected my first draft) | Nearby locations ARE accepted by default per the locale-cluster purpose; single-locale invariant is the WITHIN-session constraint; per-date locale-lock (D-67) is the override. |
| 4 | D-67 single row covers 4 restriction types (locale_lock + discipline_exclusions + indoor_only + max_total_minutes); indoor-only + time-limit shipped now, not deferred | Andy 2026-05-17 | One UX surface, one Layer 4 consumption shape, no further deferrals. |
| 5 | D-68 hybrid (a + prompt): Layer 0 category defaults + Layer 2C fallback + orchestrator nudge | Andy 2026-05-17 | Hybrid covers near-term workout-generation gap AND data-collection upside. Pure (a) silent assumptions loses data collection; pure (b) leave-the-plan-broken kills travel-week UX. |
| 6 | D-68 critical invariant: category defaults are transient resolution-only; NEVER persist to locale state; athlete confirmation via nudge prompt is the only write path | Andy 2026-05-17 | Crowd-sourced "default" data would corrupt the locale profile over time without explicit athlete consent. Confirmation-required is the only safe path. |
| 7 | Branch stays harness-pinned `claude/layer4-migration-hashing-XYE4x` | Andy 2026-05-17 (continues PR-B precedent) | Harness override; no rename. |
| 8 | Bookkeeping bundled into PR-C (CLAUDE.md + backlog v41 + closing handoff) | Andy 2026-05-17 (continues PR-A + PR-B precedent) | 4 files total; under ceiling. |

### 6.2 Stop-and-ask trigger retrospective

- **Trigger #5 fired** on §5.4 amendments — routed through plan-mode discussion in chat before applying. Per directive: amendment authoring goes through `/plan` mode even when the substantive design pick is settled. Applied as intended.
- **Trigger #11 fired three times** (D-66 + D-67 + D-68) — routed through same plan-mode discussion. All three D-rows have genuine cross-layer scope (Layer 0 + Layer 1 + Layer 2A + Layer 2C + Layer 4 + onboarding UI + profile UI in various combinations). Applied as intended.

### 6.3 Carried forward to PR-D / PR-E

- The "indoor disciplines" set referenced by `indoor_only_violation_*` (rule new) needs definitive enumeration at PR-E implementation time. v1 candidate list (from this session's discussion): indoor = swim (pool indoor), strength (any indoor gym), indoor cycling (trainer/spin), indoor rowing, indoor climbing (climbing_gym_indie/chain). outdoor = MTB-outdoor, trail running, road running, road cycling, hiking, packrafting, outdoor rock climbing, skimo, paddle racing, swimrun. Decision deferred to PR-E implementation OR D-67 design wave — whichever lands first.
- Per-rule severity tests in PR-E: §5.4 specifies `blocker` vs `warning` per rule. The PR-E test suite must honor per-rule severity in the `RuleFailure` emission per §5.5; the capped-retry-with-best-effort path treats `blocker` as retry-triggering, `warning` as observation-bubbling.

### 6.4 Carried forward to D-66 / D-67 / D-68 design waves

- **D-66 sub-decisions:** RacePlan multi-day forecast model — does it land in race_events table or its own table? `RaceSegment.estimated_start_offset_hr` semantics (continuous vs per-segment-resets). RaceRoute geometry (GPX-import? track-pen on map? both?).
- **D-67 sub-decisions:** indoor/outdoor classification authority (Layer 0 reference data vs hard-coded in the validator). Per-session-card override modal — does a single-session override write to `daily_restrictions` table for that date or to a separate per-session override table?
- **D-68 sub-decisions:** see §4.2 above (3 sub-decisions; all deferred).

---

## 7. Session-end verification (Rule #10)

Final pass before committing:

| Check | Result |
|---|---|
| `aidstation-sources/Layer4_Spec.md` §5.4 `volume_band_*` row reads `±20%` blocker / `±10%` warning | ✅ grep |
| `aidstation-sources/Layer4_Spec.md` §5.4 `acwr_*` row references "trailing 28 days" + "Gabbett 2016" | ✅ grep |
| `aidstation-sources/Layer4_Spec.md` §5.4 has rule 6a + 6b + 6c separately | ✅ grep |
| `aidstation-sources/Layer4_Spec.md` §5.4 has `indoor_only_violation_*` row | ✅ grep |
| `aidstation-sources/Layer4_Spec.md` §5.4 has D-66/67/68 summary block | ✅ grep |
| `aidstation-sources/Project_Backlog_v41.md` exists; file-revision-header is v41; v40 inline-demoted | ✅ inspection |
| `aidstation-sources/Project_Backlog_v41.md` has D-66 + D-67 + D-68 rows | ✅ grep |
| `aidstation-sources/CLAUDE.md` Backlog ref reads `Project_Backlog_v41.md` | ✅ grep |
| `aidstation-sources/CLAUDE.md` Layer 4 row mentions "Step 3 PR-C of E landed" | ✅ grep |
| `aidstation-sources/CLAUDE.md` Last-shipped is PR-C; PR-B demoted to first Predecessor | ✅ inspection |
| `aidstation-sources/CLAUDE.md` Next-forward-move recommends PR-D context schemas | ✅ grep |
| 159 pytest cases still pass (no code change — sanity check) | ✅ `pytest tests/` |
| Working tree shows 4 files modified / created | ✅ `git status` |
| No code changes — PR-C is spec-only | ✅ inspection |

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session. Unchanged.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; no new PR §5.0 surface added (Layer 4 implementation PRs don't have a `/profile` UX walk; spec-only PR has no UI surface at all).

---

**End of handoff.**
