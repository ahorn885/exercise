# #698 Track 2 Part A follow-on — cardio_drills → other synthesizer paths: Slice C1 (single_session) + C2 (plan_refresh) — Closing Handoff

**Issue:** #698 Track 2 Part A follow-on (extend the `cardio_drills` block off the plan-create path).
**Branch:** `claude/cardio-drills-pool-jv8ghg` — commits `21d7f7e` (C1) + `6c2d58d` (C2). **PR pending Andy's go (PR-gated).**
**Predecessor:** `handoffs/V5_Implementation_CardioDrillsPool_A1.5_2CCueThreading_A2PromptRatify_Track2_698_2026_06_19_Closing_Handoff_v1.md` (Part A A1.5+A2+A3, merged via #760/#761).

> **Two slices built this session, full suite green at 2730.** Andy ratified extending `cardio_drills` to **single_session + plan_refresh** (race_week_brief deliberately skipped). C1 + C2 are wired end-to-end; only **live-verify** is owed.

---

## 1. What happened (in order)

1. **Resumed the Part-A closing handoff** ("let's keep going"). Part A is **fully MERGED** — branch == `origin/main` (0 ahead), #760/#761 (A1.5/A2/A3) + #762 (CLAUDE.md PR-gating doc) all landed. **Rule #9 clean** (`verify-handoff.sh` green; every §8 anchor on-disk). Only the Andy-action plan-create live-verify remained on Part A.
2. **Surfaced the scope decision:** `recovery_exercises` was only ever extended to plan-create + race_week_brief — never to refresh/single_session. So "extend drills to the other paths" had a real per-path value/cost split. Mapped all three paths.
3. **Andy chose scope (AskUserQuestion):** extend to **single_session + plan_refresh**; skip race_week_brief (taper drops skill drills via `_cardio_drill_phase_allows`; adding the surface would invite wrong race-week picks for ~zero benefit).
4. **C1 (single_session): Andy ratified the prompt body + the two design calls** (disciplines = locale-resolved union; phase = permissive "Base") — built.
5. **C2 (plan_refresh): surfaced that refresh renders no pool menus + its diff view shows only summaries.** Andy's call: **"do it properly so refresh uses the same wiring and fidelity as plan generation."** → built the full-fidelity version (rendered menu + enum-bind + verbatim ratified prompt section), centralized so the 3 tier modules stay untouched.

## 2. What shipped — Slice C1 (single_session, D-63 on-demand)

The on-demand analog of the plan-create A2/A3 wiring. **No cache bump** (single_session is `is_ad_hoc`, generated fresh per request, not cache-keyed). Validator membership rule is **dormant** here (`phase_metadata=None`) → the enum-bind is the sole guard (G2/G3-consistent).

- **`layer4/single_session.py`:**
  - `build_record_single_session_tool(feasible_pool_ids, cardio_drill_pool_ids=None)` — adds the `cardio_drills` block (maxItems:1; enum-bound when pool non-empty, free string when empty).
  - `_SYSTEM_PROMPT` — new `# Cardio drills` section (Andy-ratified verbatim, adapted for on-demand/one-sport/no-phase), placed after `# Equipment respect`.
  - `_render_user_prompt(..., cardio_drill_pool_lines=None)` — `=== Cardio drill pool (consider these) ===` block before `# Your task`, suppress-on-empty.
  - `_build_plan_session` — parses `cardio_drills` → `list[CardioDrill]`.
  - synth call site (`llm_layer4_single_session_synthesize`): `cardio_drill_disciplines` = union of the picked locale's `exercises_resolved[*].discipline_ids`; `phase="Base"`; reuses `per_phase.compute_cardio_drill_pool_ids` + `_format_cardio_drill_pool` (the latter handles `layer2a_payload=None`).
- **`templates/workouts/suggestion_view.html`:** `cardio_drills` render branch (correct `PlanSession` field names; Bootstrap-card style; `drill` chip). **NOTE:** the neighbouring `cardio_blocks`/`strength_exercises` branches use **stale field names** (`block_type`/`description`/`hr_target`, `reps`/`load_kg`/`notes`) that don't exist on the models — pre-existing v1 bug, **filed as #764, NOT fixed here** (surgical).
- **`tests/test_layer4_single_session.py`:** `_layer2c_with_drill` helper + `TestCardioDrillsSliceC1` (8 tests: schema cap/enum/free-string, prompt section, render show/suppress, parse, end-to-end).

## 3. What shipped — Slice C2 (plan_refresh T1/T2/T3) — "same fidelity as plan generation"

Refresh gets the **same** cardio-drill wiring as plan-create: rendered menu + enum-bind + the verbatim ratified prompt section. **Centralized in `_synthesize_refresh_tier`** so the three tier prompt modules (t1/t2/t3) stay untouched.

- **`layer4/plan_refresh.py`:**
  - `_session_schema(feasible_pool_ids, cardio_drill_pool_ids=None)` + `build_record_refresh_sessions_tool(..., cardio_drill_pool_ids=None)` — the shared `cardio_drills` block (maxItems:1; enum-bound).
  - `_CARDIO_DRILLS_PROMPT_SECTION` — **verbatim mirror** of `per_phase.py`'s ratified `# Cardio drills` SYSTEM_PROMPT section (keep in sync).
  - central wiring in `_synthesize_refresh_tier`: `drill_disciplines` = 2A included (falls back to the union of 2C-resolved disciplines if `layer2_bundle.a is None`); `drill_phase` = the periodization phase covering the refresh window — **true plan-create fidelity** (skill/transition drills drop in Peak/Taper) — = the T3 `dominant_phase_name` when known, else `phase_for_date(phase_structure_from_3b(3B, plan_start_date), refresh_scope_start)`, else permissive `"Base"` (T1/T2 with no `plan_start_date`). `system_prompt += _CARDIO_DRILLS_PROMPT_SECTION` when the pool is non-empty; the `=== Cardio drill pool ===` menu is appended to each tier's `user_prompt` after render (both suppress-on-empty). **T3 cross-phase already returns to Pattern A** (`_route_t3_cross_phase_to_pattern_a`) *before* this code — it carries its own drill pool, no double-apply.
  - `_build_plan_session` — parses `cardio_drills` → `list[CardioDrill]`.
- **`layer4/hashing.py`:** `LAYER4_PROMPT_REVISION "11" → "12"` (refresh prompts changed → cached refreshes regenerate).
- **`templates/plans/v2/refresh_view.html`:** drill line on the diff card (name + `chip accent` "drill" + prescription).
- **`tests/test_layer4_plan_refresh.py`:** `_layer2c_with_drill` + `_bundle_with_drill` + `_capturing_caller` helpers + `TestCardioDrillsSliceC2` (6 tests: schema cap/enum/free-string for all tiers, parse, end-to-end prompt-section+menu present, suppress-when-empty).

## 4. Ratified decisions (Andy, this session)

1. **Scope: single_session + plan_refresh; skip race_week_brief.**
2. **C1 prompt body + design calls ratified as-is** (disciplines = locale-resolved union; phase = "Base"; reused character tags as-is).
3. **C2: "do it properly — refresh gets the same wiring/fidelity as plan generation"** (full menu + enum-bind + verbatim prompt section, over the thin enum-only or defer options).

## 5. Validation

- **Full suite 2730 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/ -q`): +8 C1, +6 C2.
- No DDL, no migration. C1 = no cache bump; C2 = `LAYER4_PROMPT_REVISION 11→12` only.

## 6. Manual verification owed + next pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Owed (Andy-action, live-verify — container can't drive plan-gen):**
1. **Part-A plan-create live-verify (still owed, in flight as plan 74):** read `/admin/logs` (needs the `DIAG_TOKEN`) for the `compute_cardio_drill_pool_ids: phase=… pool=…` line + a `cardio_drills` drill rendered on a cardio session + no `cardio_drill_pool_membership` churn.
2. **C1:** a D-63 on-demand cardio workout (bike/swim/run at a saved locale with a drill-eligible discipline) optionally carries a drill on the suggestion card.
3. **C2:** a real plan-refresh (T1/T2/T3-intra) of a multi-discipline plan surfaces a drill on a refreshed cardio session (no membership churn); the refresh diff view shows the `drill` chip. (Cache bumped to "12" → next refresh regenerates.)

**Next moves:**
1. **PR-open (Andy's go):** 7 substantive files across the two slices is over the soft 5-file ceiling — **one-PR-vs-two is Andy's call.** Two clean commits (`21d7f7e` C1, `6c2d58d` C2) split cleanly if he wants two PRs.
2. **#764** — the pre-existing `suggestion_view.html` stale-field render bug (template-only fix; mirror `plan_create/view.html`'s field names + the `intensity_target` polymorphic shape).
3. **Optional:** the §6a-G5 soft discipline-match warning (only if wrong-discipline picks show live); #337 catalog-driven interval *structure*.

**5-file ceiling note:** C1 = 3 files (single_session.py + suggestion_view.html + tests); C2 = 4 files (plan_refresh.py + hashing.py + refresh_view.html + tests). Combined 7 — flagged; commits split per slice.

## 7. Deferred edits (Rule #11)

None — both slices are fully built. race_week_brief was **decided out** (not deferred); if ever wanted it's a clean recovery-precedent copy (phase=Taper, both pools already threaded, validator live) but low value.

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| C1 schema | `layer4/single_session.py` | `build_record_single_session_tool(..., cardio_drill_pool_ids=None)`; `"cardio_drills"` block `maxItems:1`; enum-bind on `cardio_drill_pool_ids` |
| C1 prompt | `layer4/single_session.py` | `# Cardio drills` in `_SYSTEM_PROMPT`; `=== Cardio drill pool (consider these) ===` in `_render_user_prompt`; `cardio_drill_pool_lines` param |
| C1 compute | `layer4/single_session.py` | `cardio_drill_disciplines` union of locale `exercises_resolved[*].discipline_ids`; `phase="Base"`; `compute_cardio_drill_pool_ids` + `_format_cardio_drill_pool` imported from per_phase |
| C1 parse | `layer4/single_session.py` | `raw_drills = session_data.get("cardio_drills")` → `CardioDrill`; `cardio_drills=drills` in `_build_plan_session` |
| C1 render | `templates/workouts/suggestion_view.html` | `{% if sess.kind == 'cardio' and sess.cardio_drills %}` branch + `drill` badge |
| C1 tests | `tests/test_layer4_single_session.py` | `class TestCardioDrillsSliceC1`; `_layer2c_with_drill` |
| C2 schema | `layer4/plan_refresh.py` | `_session_schema(feasible_pool_ids, cardio_drill_pool_ids=None)`; `build_record_refresh_sessions_tool(..., cardio_drill_pool_ids=None)`; `cardio_drills` block |
| C2 prompt | `layer4/plan_refresh.py` | `_CARDIO_DRILLS_PROMPT_SECTION` (verbatim per_phase mirror); appended to `system_prompt` + the `=== Cardio drill pool ===` menu appended to `user_prompt` in `_synthesize_refresh_tier`, both suppress-on-empty |
| C2 compute | `layer4/plan_refresh.py` | `drill_disciplines` (2A included / 2C-union fallback); `drill_phase` (dominant / `phase_for_date(3B,plan_start)` / "Base") |
| C2 parse | `layer4/plan_refresh.py` | `raw_drills` → `CardioDrill`; `cardio_drills=drills` in `_build_plan_session` |
| C2 cache | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "12"` |
| C2 render | `templates/plans/v2/refresh_view.html` | `{% if sess.cardio_drills %}` drill line + `chip accent` "drill" |
| C2 tests | `tests/test_layer4_plan_refresh.py` | `class TestCardioDrillsSliceC2`; `_bundle_with_drill`; `_capturing_caller` |
| Suite | `tests/` | `/tmp/venv/bin/python -m pytest tests/ -q` → 2730 passed / 30 skipped |
| Issues | #698 (commented); #764 (NEW — suggestion_view.html stale-field bug) | — |

## 9. Carry-forward

- **C1 + C2 BUILT, suite green at 2730.** PR pending Andy's go (one-vs-two his call). Only live-verify owed.
- **race_week_brief = decided out** (taper anti-pattern), not deferred.
- **#764 filed** — pre-existing single-session view render bug (orthogonal, template-only).
- **STILL OWED (carried, unchanged):** Part-A plan-create live-verify (plan 74); post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.
