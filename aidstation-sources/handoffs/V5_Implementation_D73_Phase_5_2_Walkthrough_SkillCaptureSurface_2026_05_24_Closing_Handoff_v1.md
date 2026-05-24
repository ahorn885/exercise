# D-73 Phase 5.2 Walkthrough — Skill-Capability Capture Surface + Athlete-Locales Onboarding Step — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side. Ships the Bucket C (l) capture-surface follow-on named at the predecessor BucketC_l_SkillCapabilityToggles slice's §6.1, expanded mid-gate per Andy's observation that the athlete-locales setup is currently outside the onboarding flow — so this slice ALSO inserts an onboarding step for locations review. NEW `/onboarding/locales` (Step 4) + NEW `/onboarding/skills` (Step 5) + NEW Skills tab on `/profile?tab=skills` + shared `_skills_form.html` partial + Layer 1 cache eviction on save. Renumbers the downstream onboarding step indicators (schedule 4→6, target-race 5→7, route-locales 6→8). Closes the "default-OFF nuisance flags" gap left by BucketC_l: Andy can now toggle climbing_roped + whitewater_handling ON via the UI rather than via direct DB UPDATE.

**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_l_SkillCapabilityToggles_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/skill-capability-toggles-MfWJQ` (harness-pinned; the scope name still fits since this is the capture-surface follow-on to the same Bucket C (l) thread, no rename needed per CLAUDE.md branch-naming rule)
**Status:** 12 substantive files (5 NEW + 5 MOD + 2 NEW test). Ceiling break ratified at gate (precedent BucketC_i=12, BucketC_l=12). Predecessor reproducer subset 949 → 969 (+20 net new tests: 18 in test_onboarding_skills.py + 2 in test_routes_profile_skills.py). `test_layer1_builder.py` standalone unchanged at 22. ETL `etl/tests/` unchanged at 139. No regressions across any prior surface.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: `CLAUDE.md` → `CURRENT_STATE.md` (line 9 → predecessor BucketC_l handoff) → `CARRY_FORWARD.md` → predecessor handoff → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep confirms predecessor §8 anchor table all ✅ on disk: `layer0.skill_capability_toggles` CREATE present in `etl/layer0/schema.sql`; populate file with 5 rows + `ON CONFLICT DO NOTHING` + verify block present; `athlete_skill_toggles` migration present in `init_db._PG_MIGRATIONS`; Layer 1/2B/2C/orchestrator threading present at all anchor lines; TRN-011 prescription_note no longer mentions keyword-match triggers + credits `whitewater_handling` toggle; tests at 949 reproducer subset + 22 test_layer1_builder + 139 etl. Working tree clean on `claude/skill-capability-toggles-MfWJQ` (PR #141 already merged to main; the harness branch is at the same ref). The 4 ❌ anchor sweep entries on `tests/test_extractor_parsers.py` etc. remain known false-positives — those files live under `etl/tests/`, not `tests/`.

Andy picked **Skill-capability capture surface combined with onboarding integration** at the first AskUserQuestion gate over #8 locales→locations rename + best-fit modality cross-reference + Layer 2B per-discipline gap reasoning. Per Trigger #5 architectural-alternatives gate, 3 nested decisions ratified:

| # | Gate | Andy's pick | Notes |
|---|---|---|---|
| G1 | Onboarding step placement | **Between 3a and 3b**, with locales-onboarding-step ALSO inserted before skills | Over post-route-locales + profile-tab-only. Locales setup is currently outside the onboarding flow (`/locales` is its own blueprint, never linked from the onboarding chain) — Andy named this gap at the gate so this slice inserts BOTH steps. |
| G2 | Cache eviction policy | **`evict_on_layer_change(cache, uid, 'layer1')`** | Over no-eviction-natural-miss. Honest categorization — skill toggles live in `Layer1Lifestyle.skill_toggle_states`, so the Layer 1 policy (all 4 entry points + both Layer 3 wrappers) is the right routing. Cache stays clean; metric emitted. Matches predecessor §6.1 stated intent. |
| G3 | Form template structure | **Shared partial `_skills_form.html`** | Mirrors `_schedule_form.html` precedent. Single source of truth for checkbox layout; label / help-text changes don't drift between profile-tab and onboarding surfaces. |

---

## 2. Session narrative

The predecessor BucketC_l shipped the runtime contract — Layer 1/2B/2C reading the new tables — but left the athlete-side capture surface deferred. Without UI, every athlete gets `requires_skill_capability` flags by default on every included gated discipline / race-terrain entry. Andy's PGE 2026 brief shows ~4 nuisance flags (D-004 swim_open_water + D-016 + D-020 mountaineering + D-008b whitewater_handling) until he sets toggles ON via direct DB UPDATE. This slice fixes that.

Two surfaces, both backed by a shared form partial:

**`/onboarding/skills` (Step 5):** new onboarding step inserted between prefill (Step 3) and schedule (was 4, now 6). Renders the 5 toggle checkboxes (climbing_roped, mountaineering, swim_open_water, via_ferrata, whitewater_handling — alphabetical) with `display_label` as the bold label and `description` as the help text. Default-OFF semantics: athletes opt in. Save persists state + advances to schedule; Skip-for-now link advances without writing.

**`/profile?tab=skills`:** new "Skills" tab on the existing `/profile` page, between Schedule and Race events. Includes the same `_skills_form.html` partial. POST handler at `routes/profile.py::save_skills` upserts + evicts + redirects back to the tab. Matches the `save_schedule` precedent shape.

**`/onboarding/locales` (Step 4):** the gap-fill Andy requested at the gate. Read-only summary of the athlete's locale_profiles rows + the 4 legacy slots (home / hotel / partner / airport), with edit links pointing at the existing `/locales` blueprint (which owns the Mapbox picker, terrain grid, equipment editor). Continue button advances to `/onboarding/skills` regardless of locale count — the step educates and provides a CTA, not a gate. Custom locations from `routes.locales._unique_slug` flow are surfaced in a separate card so athletes see what's already on file.

**Cache eviction:** both POST handlers call `evict_layer1_on_skill_toggle_change(db, uid)` which builds a transient `Layer4Cache(PostgresCacheBackend(lambda: db))` and fires `evict_on_layer_change(cache, uid, 'layer1')`. The Layer 1 policy at `layer4/cache_invalidation.py:104` covers all 4 entry points + both Layer 3 wrappers. Mirrors `routes/locales.py::_evict_layer2b_on_terrain_change` precedent.

**Onboarding step renumbering:** inserting two steps between prefill (3) and schedule (was 4) means renumbering the indicator chrome on schedule.html (now Step 6), target_race.html (now Step 7), route_locales.html (now Step 8). The indicator is hardcoded per-template boilerplate — no shared component — so each affected template gets a small surgical edit. Connect.html and prefill.html were unchanged (they show only Steps 1-3 in their indicators).

**Behavior on athletes with empty vocab:** if the populate script hasn't been applied to the deployed DB, `load_active_skill_capability_toggle_vocab(db)` returns `[]`. The form partial renders an "ETL populate script not yet applied" warning; the POST handler no-ops the upsert + skips the eviction + still redirects forward. Defensive against early-deploy timing.

---

## 3. File-by-file edits

### 3.1 NEW `athlete_skill_toggles_repo.py` — repository helpers

5 module-level helpers:

- `load_active_skill_capability_toggle_vocab(db) -> list[dict]` — SELECT against `layer0.skill_capability_toggles` filtered on `superseded_at IS NULL`, ordered by `toggle_name`. Returns list of dicts with `toggle_name`, `display_label`, `description`. Used by both onboarding GET and profile GET.
- `get_athlete_skill_toggles(db, user_id) -> dict[str, bool]` — SELECT against `athlete_skill_toggles WHERE user_id = ?`. Returns `{toggle_name: enabled_bool}`. Public mirror of `layer1.builder._load_skill_toggle_states` for the route handlers.
- `upsert_athlete_skill_toggles(db, user_id, states: dict[str, bool])` — UPSERTs one row per (user_id, toggle_name) using the `ON CONFLICT (user_id, toggle_name) DO UPDATE SET enabled = EXCLUDED.enabled` shape against the UNIQUE constraint shipped in `init_db._PG_MIGRATIONS`. Caller commits.
- `evict_layer1_on_skill_toggle_change(db, user_id)` — builds transient `Layer4Cache(PostgresCacheBackend(lambda: db))` + fires `evict_on_layer_change(cache, user_id, 'layer1')`. Mirrors `routes.locales._evict_layer2b_on_terrain_change` precedent.
- `parse_skill_form(form, vocab) -> dict[str, bool]` — checkbox keys are `skill__<toggle_name>`. Returns ALL vocab toggles (presence True / absence explicit False) so explicit-OFF rows persist instead of being collapsed to absent. Unknown form keys are ignored (defensive).

### 3.2 MOD `routes/onboarding.py` — new routes + constants

**Imports** extended with `from routes.locales import LOCALES as LEGACY_LOCALES` (the 4-element `['home', 'hotel', 'partner', 'airport']` tuple) + 5 names from `athlete_skill_toggles_repo`.

**Constants** updated: `_POST_STEP3_TARGET` flipped from `/onboarding/schedule` to `/onboarding/locales`. NEW `_POST_STEP_LOCALES_TARGET = '/onboarding/skills'` + NEW `_POST_STEP_SKILLS_TARGET = '/onboarding/schedule'`. Old downstream constants (`_POST_STEP3B_TARGET` etc.) untouched.

**NEW Section "Step 4 — Locations review"** inserted before the existing Schedule section. Adds:
- `_athlete_locales_for_review(db, uid) -> list` — single SELECT against `locale_profiles WHERE user_id = ?` + assembly into 4 legacy slots (always present, `is_custom=False`, `configured=row_exists`) + N custom slots (athlete-created rows where slug not in LEGACY_LOCALES).
- `@bp.route('/locales', methods=['GET']) def locales()` — calls the helper + renders `onboarding/locales.html` with `athlete_locales` + `post_step_locales_target`.
- `@bp.route('/locales/continue', methods=['POST']) def locales_continue()` — pure redirect to `/onboarding/skills` (no DB write).

**NEW Section "Step 5 — Skills capture"** added right after. Adds:
- `@bp.route('/skills', methods=['GET']) def skills()` — calls `load_active_skill_capability_toggle_vocab` + `get_athlete_skill_toggles` + renders `onboarding/skills.html` with `toggle_defs` + `current_states` + `post_step_skills_target`.
- `@bp.route('/skills', methods=['POST']) def skills_save()` — load vocab, `parse_skill_form(request.form, vocab)`, upsert if non-empty, commit, evict, flash, redirect to `_POST_STEP_SKILLS_TARGET`.

### 3.3 MOD `routes/profile.py` — Skills tab data + save handler

**Imports** extended with 5 names from `athlete_skill_toggles_repo`.

**`edit()` GET** extended: loads `skill_toggle_defs` + `skill_toggle_states` before the render_template call; passes both as kwargs to the template.

**NEW `save_skills` POST** added before `disconnect_provider`. Mirrors `save_schedule` shape: load vocab, parse, upsert if non-empty, commit, evict, flash, redirect to `url_for('profile.edit', tab='skills')`. Empty-vocab path no-ops the upsert but still redirects (defensive).

### 3.4 MOD `templates/profile/edit.html` — Skills tab in nav + tab-pane

**Nav** extends with `<li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-skills" type="button">Skills</button></li>` inserted between Schedule and Race events.

**Tab-pane** added: `<div class="tab-pane fade" id="tab-skills" role="tabpanel">` includes the shared `_skills_form.html` partial wrapped in a POST form pointing at `url_for('profile.save_skills')`. Intro paragraph cites Bucket C (l) ratification + default-OFF semantic.

### 3.5 NEW `templates/onboarding/_skills_form.html` — shared form partial

Iterates `toggle_defs` rendering one `form-check` per row with `id="skill__<toggle_name>"` + `name="skill__<toggle_name>"`. The `checked` attribute reads `current_states.get(toggle_name)`. Empty `toggle_defs` (populate script not yet applied) renders an explanatory warning instead of an empty form.

### 3.6 NEW `templates/onboarding/skills.html` — onboarding wrapper

5-step indicator chrome (Steps 1-4 ✓ + Step 5 current). Intro copy explains the coaching-flag firing semantic. Includes the shared `_skills_form.html` partial wrapped in a POST form pointing at `url_for('onboarding.skills_save')`. Footer has Skip-for-now link → `post_step_skills_target` + Save & continue button.

### 3.7 NEW `templates/onboarding/locales.html` — onboarding wrapper

4-step indicator chrome (Steps 1-3 ✓ + Step 4 current). Intro copy explains locations + their role in plan reasoning. Two cards rendered conditionally:
- "Your custom locations" — only renders when athletes have non-legacy rows.
- "Legacy slots" — always renders the 4 default slots with `(not configured)` small print for unset rows.

Each row has an Edit link to `url_for('locales.edit_profile', locale=loc.slug)`. Footer has "Add or manage locations" button → `url_for('locales.list_profiles')` (existing blueprint) + Continue button POSTing to `url_for('onboarding.locales_continue')`.

### 3.8 MOD `templates/onboarding/schedule.html` — step indicator renumbered

Was: Step 4 — Schedule & availability (current). Now: Steps 1-5 ✓ + Step 6 — Schedule & availability (current). Inserted Step 4 — Locations + Step 5 — Skills as ✓ entries.

### 3.9 MOD `templates/onboarding/target_race.html` — step indicator renumbered

Was: Step 5 — Target race (current). Now: Steps 1-6 ✓ + Step 7 — Target race. Inserted Step 4 + Step 5 ✓; bumped Schedule from 4 → 6.

### 3.10 MOD `templates/onboarding/route_locales.html` — step indicator renumbered

Was: Step 6 — Route locales (current). Now: Steps 1-7 ✓ + Step 8 — Route locales. Inserted Step 4 + Step 5; bumped Schedule 4→6, Target race 5→7.

### 3.11 NEW `tests/test_onboarding_skills.py` — onboarding + repo tests (18 tests)

- `TestLoadActiveSkillCapabilityToggleVocab` (2 tests) — SQL shape (filter on `superseded_at IS NULL`, table name); empty result on no-rows.
- `TestGetAthleteSkillToggles` (2 tests) — return dict keyed by toggle_name; empty athlete → empty dict.
- `TestUpsertAthleteSkillToggles` (2 tests) — one INSERT per state with ON CONFLICT shape; empty dict no-ops.
- `TestParseSkillForm` (3 tests) — checked rows True, unchecked False (explicit), unknown keys ignored, empty vocab → empty.
- `TestEvictLayer1OnSkillToggleChange` (1 test) — fires `evict_on_layer_change(cache, uid, 'layer1')` via monkeypatch.
- `TestAthleteLocalesForReview` (3 tests) — empty athlete → 4 unconfigured legacy slots; configured Home uses locale_name; custom locale appended with `is_custom=True`.
- `TestLocalesRoute` (2 tests) — GET captures correct template + kwargs via `render_template` monkeypatch (full base.html template can't render in test app without registering every blueprint); Continue POST redirects to `/onboarding/skills`.
- `TestSkillsRoute` (3 tests) — GET captures vocab + states + post_step_skills_target; POST upserts + commits + fires Layer 1 eviction + redirects to schedule; empty-vocab POST no-ops but still redirects.

### 3.12 NEW `tests/test_routes_profile_skills.py` — profile-tab tests (2 tests)

- `TestSaveSkillsRoute.test_post_upserts_state_evicts_and_redirects_to_skills_tab` — checks one toggle, asserts 1 vocab SELECT + 2 upserts + 1 commit + 1 eviction + redirect with `tab=skills` query param.
- `TestSaveSkillsRoute.test_empty_vocab_no_ops_but_still_redirects` — vocab SELECT returns empty → no upsert / commit / eviction; redirect still happens.

Both use the same `_FakeConn` substrate from `tests/test_onboarding_race_events.py`.

---

## 4. Code / tests

**Tests:** predecessor reproducer subset 949 → 969 (+20 net new: 18 in test_onboarding_skills.py + 2 in test_routes_profile_skills.py). `test_layer1_builder.py` standalone unchanged at 22. ETL `etl/tests/` unchanged at 139. Whole tests/ directory: 1550 passed, 16 skipped — no regressions across any prior surface (the 16 skipped are the 12 NL parser smoke + 4 Layer 3 SDK smoke when ANTHROPIC_API_KEY unset, plus 0 additional).

Reproducer (predecessor's exact subset + my new files):

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
  tests/test_race_events_repo.py tests/test_race_events_invalidation.py \
  tests/test_onboarding_race_events.py tests/test_layer4_context.py \
  tests/test_layer4_payload.py tests/test_layer4_hashing.py tests/test_layer4_cache.py \
  tests/test_layer4_race_week_brief.py tests/test_plan_sessions_repo.py \
  tests/test_routes_ad_hoc_workouts.py tests/test_routes_plan_create.py \
  tests/test_nl_parser.py tests/test_routes_plan_refresh.py tests/test_nl_parser_smoke.py \
  tests/test_routes_dashboard.py tests/test_routes_admin.py \
  tests/test_layer3_cached_wrappers.py tests/test_routes_race_events.py \
  tests/test_layer2a.py tests/test_layer2b.py tests/test_layer2c.py \
  tests/test_bucket_c_terrain_vocab_audit.py \
  tests/test_onboarding_skills.py tests/test_routes_profile_skills.py
# 969 passed, 12 skipped in ~3.1s
```

Layer 1 builder standalone (untouched but rerun for safety):

```
PYTHONPATH=. python3 -m pytest tests/test_layer1_builder.py
# 22 passed in 0.37s
```

ETL: `PYTHONPATH=. python3 -m pytest etl/tests/ # 139 passed in 0.58s`.

**py_compile:** all changed Python files (`athlete_skill_toggles_repo.py`, `routes/onboarding.py`, `routes/profile.py`) pass `python3 -m py_compile`. Same for `routes/locales.py` (read by the new import) + `app.py` (uses Flask version-agnostic).

---

## 5. Manual §5.0 verification — owed step

NEW 5-step walkthrough scenario added to `CARRY_FORWARD.md` §5.0 list. Summarized:

1. **`/onboarding/locales` renders** — fresh signup, complete connect + prefill → land on `/onboarding/locales` (formerly land on `/onboarding/schedule`). Confirm: 4 legacy slots show in the "Legacy slots" card with "(not configured)" small print; "Your custom locations" card absent (no rows); "Add or manage locations" links to `/locales`; Continue button advances to `/onboarding/skills`.
2. **`/onboarding/skills` renders the 5 toggles** — confirm 5 checkboxes (alphabetical: climbing_roped, mountaineering, swim_open_water, via_ferrata, whitewater_handling) with `display_label` as bold label and `description` as the help text below; all unchecked by default for a fresh athlete; Skip-for-now link goes to `/onboarding/schedule`.
3. **Save-and-continue persists state + advances** — check climbing_roped + whitewater_handling, click Save & continue → confirm 5 `athlete_skill_toggles` rows land (2 True + 3 False) + redirect to `/onboarding/schedule`; rerun race-week brief for Andy → confirm `requires_skill_capability` flags for D-010 + D-008b disappear (still fires for D-004 + D-016 + D-020 since those toggles remain OFF).
4. **`/profile?tab=skills` round-trip** — navigate to `/profile?tab=skills`. Confirm: Skills tab present in the nav between Schedule and Race events; tab content shows 5 checkboxes with step-3 state (climbing + whitewater checked); flip swim_open_water ON, click Save skills → confirm flash "Skills saved." + redirect lands back on `/profile?tab=skills` with the new state.
5. **Cache eviction fires** — query `layer4_cache` after the step 4 save → confirm 0 cached rows remain for Andy. Tail logs (or query `cache.metrics`) → confirm an `evict_layer1_on_skill_toggle_change` event was emitted tagged with `layer=layer1`. Spot-check: if Andy had a cached race-week brief before the save, that row's gone post-save and next call re-derives Layer 2B+2C with the new skill state, surfacing the right (now-reduced) `requires_skill_capability` flag set.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Best-fit modality cross-reference design** is the natural follow-on. Open from BucketC_g + BucketC_l. Now that `skill_toggle_states` is captured in the UI, the planner has the full input set to reason `{locale_terrain_ids + cluster_equipment + included_disciplines + skill_toggle_states} → recommended modality per session`. Concrete shape TBD (mapping table vs derived join vs Layer 4 prompt-side reasoning). Plan-mode gate required (Trigger #1 if prompt-side; Trigger #3 if schema-side; Trigger #5 either way).

Alternative: **#8 "locales" → "locations" terminology rename** remains the lowest-risk mechanical slice (carried forward through every recent handoff; ~9 templates, no /plan triggers). Note: this slice will now touch some of my new files too since I labeled the Step 4 page "Locations" in the indicator but the URL is `/onboarding/locales`. The terminology rename would unify these.

### 6.2 Alternative pivots

- **Layer 2B per-discipline gap reasoning** — Trigger #1 prompt-body update. ~3-5 files including spec + prompt + tests.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **#2b race-URL LLM site-parse pre-fill** — Trigger #2 prompt design session first; then ~4-6 files runtime.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 de-stub. LARGE ~6-8 files; plan-mode gate required.
- **Bucket D — legacy hardcoded locales (a + b)** — unblocked (Bucket C fully closed since BucketC_l).
- **"Bounce back from `/locales/new` to `/onboarding/locales`"** — small UX follow-on. Athletes who click "Add or manage locations" from `/onboarding/locales` currently navigate to `/locales` and have to return manually. Adding a `return_to` param to `/locales/new` + `/locales/<slug>/edit` POST handlers would let them auto-bounce back. ~1-2 files.
- **Manual §5.0 walkthrough** — 100 scenarios pending; this slice's 5-step scenario joins the list.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket C (l) capture surface now ✅ shipped; 100 §5.0 scenarios pending).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_SkillCaptureSurface_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Backward-compat note for next deploy:** all changes are additive. The new `/onboarding/locales` + `/onboarding/skills` routes only fire when an athlete walks the onboarding flow OR clicks the Skills tab on `/profile`. Existing athletes who never re-enter onboarding keep their current state (no `athlete_skill_toggles` rows = every toggle treated as default-OFF, identical to today). The `_POST_STEP3_TARGET` constant change (`/onboarding/schedule` → `/onboarding/locales`) only affects athletes hitting `/onboarding/prefill` for the first time — existing in-flight onboardings landing directly on schedule are unaffected by URL.

**Production rollout dependency:** the `layer0.skill_capability_toggles` populate script (`etl/sources/populate_skill_capability_toggles.sql`) must be applied before the new Skills tab + onboarding step render usefully. Until then, both surfaces show the "ETL populate script not yet applied" warning. Operators apply the populate manually after the BucketC_l ETL migration runs (this is documented in the BucketC_l handoff §6.3).

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Onboarding step placement = between prefill (3) and schedule (4-was, 6-now) | Andy at first AskUserQuestion gate | Over post-route-locales (would make schedule + race-related steps come BEFORE skills/locations, which is backwards mentally) + profile-tab-only (skips the onboarding surface entirely). Inserting between 3 and 4 keeps the conceptual flow: connect → review prefilled values → set athletic context (locations + skills) → set training capacity (schedule) → pick race → map route. |
| **D2** | Athlete-locales onboarding step ALSO inserted (Step 4) | Andy at first AskUserQuestion gate (gap observation) | The existing `/locales` blueprint is currently only accessible from a logged-in athlete navigating directly — never linked from the onboarding chain. Andy named this gap when reviewing the step placement question. Adding the locations review step closes the gap without touching the `/locales` blueprint itself (the new step links out for management; it doesn't reimplement the Mapbox picker / terrain grid / equipment editor). |
| **D3** | Cache eviction = `evict_on_layer_change(cache, uid, 'layer1')` | Andy at second AskUserQuestion gate | Over no-eviction-natural-miss. Honest categorization (skill_toggle_states is Layer 1 data) + the Layer 1 policy already covers all the right entry points. Cache hygiene; emits an eviction metric the operator can monitor. ~2 LOC vs no-eviction's 0 LOC, but the maintainability + observability win is worth it. |
| **D4** | Shared form partial `_skills_form.html` | Andy at third AskUserQuestion gate (recommended; ratified by selection) | Mirrors `_schedule_form.html` precedent exactly. Single source of truth for checkbox layout; label / help-text changes don't drift between profile-tab and onboarding surfaces. |
| **D5** | 12-file ceiling break ratified | Implied at proceed gate | 12 substantive files (5 NEW code/template + 5 MOD + 2 NEW test). Precedents: BucketC_i=12, BucketC_l=12, BucketE_B2_C1=11+5, RaceLocaleMapbox=13. |
| **D6** | "Bounce back from /locales/new" deferred to follow-on | Architect at code-time | Athletes who click "Add or manage locations" from `/onboarding/locales` navigate to the existing `/locales` blueprint, then have to return manually. Implementing the bounce-back would require adding a `return_to` query param to `/locales/new` + `/locales/<slug>/edit` POST handlers (~3-6 LOC). Deferred to keep this slice's scope bounded; named as a follow-on forward-pointer. |
| **D7** | Locales onboarding step is read-only (no add-form embedded) | Architect at code-time | Embedding the locale-add form in the onboarding step would duplicate the Mapbox picker / terrain grid / equipment editor that the `/locales/new` flow already owns. Instead, the step shows a summary + a CTA button linking out. Trades off "single-step onboarding completion" for "single source of truth for locale-add UI". Acceptable since the slice's primary goal is the skill-capability surface, not a locales-flow redesign. |
| **D8** | Form key prefix `skill__<toggle_name>` for checkbox names | Architect at code-time | Distinguishes skill-toggle fields from other form fields when the POST handler picks them out of a mixed form payload. The double-underscore prefix is unusual enough that it won't collide with any future form fields named `skill_*` (single-underscore variant). |
| **D9** | `parse_skill_form` returns ALL vocab toggles (explicit False for unchecked) | Architect at code-time | Preserves the distinction between "athlete saw this toggle + deliberately left it OFF" and "athlete never saw this toggle". Layer 2B/2C currently treat absent and explicit-False the same (both default-OFF), but the distinction is preserved at the boundary in case future consumers care. Same call as Layer 1's `test_explicit_off_rows_preserved` test from BucketC_l. |
| **D10** | Step indicator chrome renumbered in 3 downstream templates | Architect at code-time | Each onboarding template has a hardcoded `<ol>` step indicator (no shared component). Inserting 2 new steps requires renumbering schedule (4→6), target-race (5→7), route-locales (6→8). Surgical edits per template; could not be done with a shared component without a bigger refactor. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `athlete_skill_toggles_repo.py` defines 5 helpers (load_active + get + upsert + evict + parse) | ✅ `grep -E "^def " athlete_skill_toggles_repo.py` returns 5 hits |
| `routes/onboarding.py` imports from `athlete_skill_toggles_repo` + `routes.locales`'s LOCALES | ✅ `grep -n "from athlete_skill_toggles_repo\|LEGACY_LOCALES" routes/onboarding.py` returns both lines |
| `_POST_STEP3_TARGET` flipped to `/onboarding/locales` | ✅ `grep -n "_POST_STEP3_TARGET\s*=" routes/onboarding.py` returns `/onboarding/locales` |
| NEW `_POST_STEP_LOCALES_TARGET` + `_POST_STEP_SKILLS_TARGET` constants | ✅ `grep -E "_POST_STEP_(LOCALES\|SKILLS)_TARGET" routes/onboarding.py` returns both |
| `/onboarding/locales` GET + `/onboarding/locales/continue` POST routes defined | ✅ `grep -n "@bp\.route.'/locales'" routes/onboarding.py` returns 2 |
| `/onboarding/skills` GET + POST routes defined | ✅ `grep -n "@bp\.route.'/skills'" routes/onboarding.py` returns 2 |
| `_athlete_locales_for_review` helper present | ✅ `grep -n "def _athlete_locales_for_review" routes/onboarding.py` |
| `routes/profile.py` defines `save_skills` POST handler | ✅ `grep -n "def save_skills" routes/profile.py` |
| `routes/profile.py` passes `skill_toggle_defs` + `skill_toggle_states` to render | ✅ `grep -n "skill_toggle_defs=\|skill_toggle_states=" routes/profile.py` returns both kwargs |
| `templates/profile/edit.html` has Skills tab + tab-pane | ✅ `grep -c "tab-skills" templates/profile/edit.html` returns ≥2 |
| `templates/onboarding/_skills_form.html` exists | ✅ `ls templates/onboarding/_skills_form.html` |
| `templates/onboarding/skills.html` exists with step 5 indicator | ✅ `grep "Step 5 — Skills" templates/onboarding/skills.html` |
| `templates/onboarding/locales.html` exists with step 4 indicator | ✅ `grep "Step 4 — Locations" templates/onboarding/locales.html` |
| `templates/onboarding/schedule.html` step indicator renumbered to Step 6 | ✅ `grep "Step 6 — Schedule" templates/onboarding/schedule.html` |
| `templates/onboarding/target_race.html` step indicator renumbered to Step 7 | ✅ `grep "Step 7 — Target race" templates/onboarding/target_race.html` |
| `templates/onboarding/route_locales.html` step indicator renumbered to Step 8 | ✅ `grep "Step 8 — Route locales" templates/onboarding/route_locales.html` |
| NEW `tests/test_onboarding_skills.py` (18 tests) | ✅ pytest 18 passed |
| NEW `tests/test_routes_profile_skills.py` (2 tests) | ✅ pytest 2 passed |
| Predecessor reproducer subset 949 → 969 + 12 skipped | ✅ 969 passed, 12 skipped |
| `test_layer1_builder.py` unchanged at 22 | ✅ 22 passed |
| ETL `etl/tests/` unchanged at 139 | ✅ 139 passed |
| All edited Python files pass `py_compile` | ✅ clean |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Bucket C (l) capture-surface line flipped ✅ shipped + §5.0 walkthrough scenario added (5 steps) + scenario count 95 → 100 | ✅ |

---

## 9. Files shipped this session

**Substantive (12 files; ceiling break ratified at gate; precedent BucketC_i=12, BucketC_l=12):**

1. NEW `athlete_skill_toggles_repo.py` — 5 helpers (load_active vocab + get + upsert + evict + parse_form).
2. MOD `routes/onboarding.py` — 4 new routes (locales GET + locales/continue POST + skills GET + skills POST), `_athlete_locales_for_review` helper, 2 new redirect-chain constants, 1 constant flipped, imports extended.
3. MOD `routes/profile.py` — Skills-tab data loaded in `edit()` GET, NEW `save_skills` POST handler, imports extended.
4. MOD `templates/profile/edit.html` — Skills tab in nav + tab-pane with intro copy + shared partial include.
5. NEW `templates/onboarding/_skills_form.html` — shared 5-checkbox form partial.
6. NEW `templates/onboarding/skills.html` — Step 5 onboarding wrapper.
7. NEW `templates/onboarding/locales.html` — Step 4 onboarding wrapper.
8. MOD `templates/onboarding/schedule.html` — step indicator renumbered (4 → 6).
9. MOD `templates/onboarding/target_race.html` — step indicator renumbered (5 → 7).
10. MOD `templates/onboarding/route_locales.html` — step indicator renumbered (6 → 8).
11. NEW `tests/test_onboarding_skills.py` — 18 tests (repo helpers + onboarding routes).
12. NEW `tests/test_routes_profile_skills.py` — 2 tests (profile-tab POST handler).

**Bookkeeping (3 files; do not count against ceiling per CLAUDE.md):**

13. MOD `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor BucketC_l line preserved.
14. MOD `aidstation-sources/CARRY_FORWARD.md` — Bucket C (l) capture-surface line flipped ✅ shipped; NEW 5-step Manual §5.0 walkthrough scenario added; scenario count 95 → 100.
15. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_SkillCaptureSurface_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket C (l) capture-surface follow-on closed end-to-end** ✅ — profile-edit Skills tab + onboarding Step 5 Skills + onboarding Step 4 Locations + Layer 1 cache eviction on save + shared `_skills_form.html` partial.
- **NEW 5-step Manual §5.0 walkthrough scenario** — onboarding/locales renders / onboarding/skills renders + 5 toggles / save-and-continue persists + advances / profile?tab=skills round-trip / cache eviction fires.
- **NEW best-fit modality cross-reference forward-pointer** (open from BucketC_g + BucketC_l) gains the now-captured `skill_toggle_states` as input. Design slice will reason `{locale_terrain_ids + cluster_equipment + included_disciplines + skill_toggle_states} → recommended modality per session`.
- **NEW "bounce back from /locales/new to /onboarding/locales" forward-pointer** — small UX follow-on. ~1-2 files.
- **Pre-existing forward-pointers carried** — #8 locales→locations rename remains lowest-risk mechanical slice; Layer 2B per-discipline gap reasoning still queued; #6 + #4 injury form refresh / #2b race-URL site-parse / §I.1 structured supplements / Bucket D legacy hardcoded locales (still unblocked) all carry.

**End of handoff.**
