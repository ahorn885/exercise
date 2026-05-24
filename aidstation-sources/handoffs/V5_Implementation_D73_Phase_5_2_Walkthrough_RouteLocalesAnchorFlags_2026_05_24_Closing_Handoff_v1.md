# D-73 Phase 5.2 Walkthrough — Route-Locales Anchor Flags (companion to PR #131) — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — closes the §6.1 architect-recommended forward-pointer carried since the RouteLocalesValidatorHotfix slice (PR #131, 2026-05-23). PR #131 loosened `RaceEventPayload._check_route_locales_invariants` to silently accept missing start/finish role anchors so Andy's PGE 2026 target race could traverse the payload boundary; the loosen comment explicitly flagged "moved to a coaching-flag emission downstream (forward-pointer; not yet wired)." This slice wires it.
**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_ETLTerrainVocabDriftFix_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/zealous-heisenberg-mphVd`
**Status:** 2 substantive files (well under 5-file ceiling — architect-recommended minimal slice). Container-runnable subset 805 → 815 (+10 net: 9 new tests in `tests/test_layer4_race_week_brief.py` + 1 existing test extended); ETL `etl/tests/` 139 → 139 unchanged. No regressions.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: CLAUDE.md → CURRENT_STATE.md → CARRY_FORWARD.md → predecessor handoff → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep returned ✅ across all 29 substantive references; the 4 ❌ entries (`tests/test_extractor_parsers.py`, `tests/test_sum_to_100.py`, `tests/test_v10_parsers.py`, `tests/test_vocabulary_md.py`) are a false-positive in the verify script — it does not know to look under `etl/tests/` where those files actually live. Confirmed via direct `ls etl/tests/`. Working tree clean on `claude/zealous-heisenberg-mphVd`; backlog pointer stable at `Project_Backlog_v62.md`; predecessor §8 table claims spot-checked (4 substantive files landed; `_TERRAIN_STRUCTURED_ROWS` present with 16 dicts; `test_terrain_count` = 16; migration warning lifted). No drift between predecessor handoff narrative and on-disk state.

---

## 2. Session narrative

Andy picked **"Coaching-flag emission for missing anchors"** at the AskUserQuestion gate from the predecessor handoff's §6.1 / §6.2 menu (4 options offered: this slice / Bucket E.(b)-B2+E.(c)-C1 / Bucket C (a)-(j) / #8 locales→locations rename).

The investigation traced the surface area:

- **PR #131 root cause comment** (`layer4/context.py:1135-1143`) explicitly flagged the downstream coaching-flag emission as not-yet-wired forward-pointer: *"Whether start/finish anchors are present is a content/data-quality concern, not a structural one — moved to a coaching-flag emission downstream (forward-pointer; not yet wired)."*
- **Andy's PGE 2026 case**: route_locales is non-empty (athletes capture transition areas, aid stations, bivvy points, etc.) but no entry has `role='start'` or `role='finish'`. The brief synthesizer would otherwise infer the start from `route_locales[0]` and the finish from `route_locales[-1]`, fabricating anchor narration off non-anchor data.
- **Where to emit**: the existing `_emit_data_gap_observations` pattern in `layer4/race_week_brief.py` is the canonical surface for orchestrator-side observations on content-quality data gaps (mirrors `kit_manifest_inputs_incomplete_*` precedent). The Layer4Payload's `notable_observations: list[Layer3Observation]` field carries the data_gap categories down to the brief UI surface; the synthesizer also reads the user prompt directly so the prompt augmentation gives the LLM the same signal.
- **By-role-anywhere vs first/last-position**: chose by-role-anywhere semantics. A list like `[transition_area, start, ..., finish]` correctly satisfies (the start role IS present, just not at first position). The original validator semantic that PR #131 loosened was first/last-position; the data_gap signal should reflect the more conservative "no start anchor was marked AT ALL" rather than "first position isn't start" — closer match to what the LLM needs to know about content completeness.

`/plan` Triggers DID NOT fire — handoff §6.1 explicitly called this out as "No /plan triggers fire" and the implementation is mechanical (mirrors an existing pattern, no architectural alternatives in play).

`/plan` Triggers DEFERRED to follow-on slices (carried verbatim from predecessor):

- **Bucket C sub-items (a)-(j)** — terrain/locale vocab cleanup design conversation. Each item needs Trigger #2 + #5 design pass.
- **Bucket E.(b)-B2 + E.(c)-C1** — specs already pinned in `CARRY_FORWARD.md`; ~6-9 files; needs ceiling-break ratification.
- **#8 "locales" → "locations" rename** — ~9 templates, mechanical. Lowest-risk next-slice candidate per architect recommendation.

---

## 3. File-by-file edits

### 3.1 `layer4/race_week_brief.py` — helper + wire-in + prompt augmentation

**NEW `_emit_route_locales_anchor_observations(race_event_payload: RaceEventPayload) -> list[Observation]`** — inserted directly after `_emit_data_gap_observations`. Mirrors the data_gap pattern verbatim:

```python
def _emit_route_locales_anchor_observations(
    race_event_payload: RaceEventPayload,
) -> list[Observation]:
    """Companion to PR #131 (RaceLocalesValidatorHotfix). When the athlete
    captured route_locales but didn't mark an explicit `start` and/or
    `finish` role anywhere in the list, surface a `data_gap` observation
    so the LLM has explicit signal rather than fabricating an anchor
    from first/last position inference. Skipped when route_locales is
    empty (already covered by `kit_manifest_inputs_incomplete_no_route_locales`)."""
    out: list[Observation] = []
    if not race_event_payload.route_locales:
        return out
    roles = {rl.role for rl in race_event_payload.route_locales}
    if "start" not in roles:
        out.append(Observation(category="data_gap", text="route_locales_missing_start_anchor: ...", evidence_basis=["Race_Events_D66_Design_v1.md §4.2", "PR #131 validator loosen 2026-05-23"], elevates_to_hitl=False))
    if "finish" not in roles:
        out.append(Observation(category="data_gap", text="route_locales_missing_finish_anchor: ...", ...))
    return out
```

Each observation's `text` field is constructed via a string literal then sliced `[:240]` to honor the `Observation.text = Field(max_length=240)` constraint (defensive — the literals are well under 240 chars but the slice locks in the guarantee). `elevates_to_hitl=False` since this is content-quality, not HITL-blocking. `evidence_basis` cites both the design doc anchor and the PR #131 loosen commit so reviewers can trace the lineage.

**Wire-in inside `llm_layer4_race_week_brief`** — appended after the existing `_emit_data_gap_observations(validator_results[-1])` extend call (around line 1660):

```python
# Route-locales missing-anchor data_gap (companion to PR #131
# validator loosen 2026-05-23). Emitted whenever route_locales is
# captured but explicit start / finish role anchors are missing.
notable_observations.extend(
    _emit_route_locales_anchor_observations(race_event_payload)
)
```

**Prompt augmentation in `_render_user_prompt`** — the Route locales section (around line 874) now computes `roles_present` from the in-list `RouteLocale.role` values and appends an explicit "do not infer" note when either anchor is missing:

```python
roles_present = {rl.role for rl in race_event_payload.route_locales}
missing_anchors = [
    anchor for anchor in ("start", "finish") if anchor not in roles_present
]
if missing_anchors:
    parts.append("")
    parts.append(
        f"**Note:** no entry has role={' or role='.join(repr(a) for a in missing_anchors)}. "
        "Treat the corresponding anchor(s) as unknown — do not infer from "
        "first/last sequence_idx position."
    )
```

Renders as one of three shapes (start-only / finish-only / both) depending on what's missing. The note line is gated inside the existing `if race_event_payload.route_locales:` block so empty `route_locales` (already covered by `kit_manifest_inputs_incomplete_no_route_locales`) does not produce a missing-anchor note.

Net delta: ~52 lines added (35 helper + 5 wire-in + 12 prompt augmentation), ~0 lines removed. No signature changes.

### 3.2 `tests/test_layer4_race_week_brief.py` — direct + end-to-end + prompt coverage

**Import extension** — adds `_emit_route_locales_anchor_observations` to the `layer4.race_week_brief` import line so direct-helper tests can exercise the function without firing the full orchestrator.

**NEW `TestRouteLocalesAnchorObservations` class** — 7 direct-helper tests:

1. `test_empty_route_locales_emits_nothing` — empty list short-circuits.
2. `test_both_anchors_present_emits_nothing` — start + aid_station + finish → 0 observations.
3. `test_start_missing_finish_present_emits_one` — Andy's PGE 2026 shape (transition_area + finish) → 1 observation, text contains `route_locales_missing_start_anchor`, `elevates_to_hitl=False`, evidence_basis cites PR #131.
4. `test_finish_missing_start_present_emits_one` — start + aid_station → 1 observation, text contains `route_locales_missing_finish_anchor`.
5. `test_both_anchors_missing_emits_two` — aid_station + transition_area → 2 observations (one for each missing anchor).
6. `test_start_anywhere_in_list_counts` — locks in the by-role-anywhere semantic (start in the middle of the list still satisfies — no observation emitted).
7. `test_observation_text_under_240_chars` — defensive check that the helper-emitted text honors `Observation.text = Field(max_length=240)`.

**NEW `test_route_locales_missing_start_anchor_emits_observation`** in `TestObservationEmission` — end-to-end via `llm_layer4_race_week_brief` with Andy's PGE 2026-shaped `race_event_payload` (transition_area + finish, no start). Confirms the helper fires through the orchestrator-side observation chain (`notable_observations` carries exactly one start-anchor data_gap + zero finish-anchor data_gaps).

**NEW 2 prompt-rendering tests** in `TestPromptRendering`:

- `test_route_locales_missing_anchors_note_rendered` — both missing → prompt contains `role='start'`, `role='finish'`, and `first/last sequence_idx`.
- `test_route_locales_missing_start_only_note_rendered` — start missing only → prompt contains `role='start'` but NOT `role='finish'` (asymmetric path).

**EXTENDED `test_route_locales_rendered_structured`** — added `assert "no entry has role=" not in prompt` to lock in the "no note when both anchors are present" guarantee. Prevents regression where the note accidentally renders for happy-path lists.

Net delta: +124 lines (~7 new tests + 1 end-to-end test + 2 prompt tests + 1 import extension + 1 existing-test assertion). 0 lines removed.

---

## 4. Code / tests

**Tests:** `tests/test_layer4_race_week_brief.py` 56 → 65 (+9 net new: 7 in NEW `TestRouteLocalesAnchorObservations` + 1 in `TestObservationEmission` + 2 in `TestPromptRendering`; 1 existing test extended). Container-runnable subset 805 → 815 (+10 net). No regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin / layer3 cached-wrappers / layer2a surfaces. ETL `etl/tests/` 139 → 139 unchanged.

Reproducer (changed file only):

```
PYTHONPATH=. pytest tests/test_layer4_race_week_brief.py
# 65 passed in 0.47s
```

Full container subset (matches predecessor's exact invocation):

```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                    tests/test_race_events_repo.py tests/test_race_events_invalidation.py \
                    tests/test_onboarding_race_events.py tests/test_layer4_context.py \
                    tests/test_layer4_payload.py tests/test_layer4_hashing.py \
                    tests/test_layer4_cache.py tests/test_layer4_race_week_brief.py \
                    tests/test_plan_sessions_repo.py tests/test_routes_ad_hoc_workouts.py \
                    tests/test_routes_plan_create.py tests/test_nl_parser.py \
                    tests/test_routes_plan_refresh.py tests/test_nl_parser_smoke.py \
                    tests/test_routes_dashboard.py tests/test_routes_admin.py \
                    tests/test_layer3_cached_wrappers.py tests/test_routes_race_events.py \
                    tests/test_layer2a.py
# 815 passed, 12 skipped in 1.28s
```

Combined with ETL: **954 passed, 12 skipped** in ~1.7s.

**Python syntax check:** `python3 -m py_compile layer4/race_week_brief.py` passes.

**No-regression confirmation:** All 21 container-subset test files still pass with identical counts on the 20 untouched files; the only count change is `test_layer4_race_week_brief.py` 56 → 65.

---

## 5. Manual §5.0 verification — owed step

**1 RouteLocalesAnchorFlags step.** Once Andy's PGE 2026 target race reaches the race-week-brief orchestrator window (today < event_date ≤ today+14 → 2026-07-03..2026-07-17, or a manual `UPDATE race_events SET event_date = ?` for earlier spot-test), run:

```python
from datetime import date
from layer4 import Layer4Cache, InMemoryCacheBackend
from layer4.orchestrator import orchestrate_race_week_brief

payload = orchestrate_race_week_brief(
    db, user_id=<andy>, today=date(YYYY, MM, DD),
    cache=Layer4Cache(InMemoryCacheBackend()),
)
```

Confirm:

- `payload.notable_observations` contains exactly one `Observation(category='data_gap', text=startswith('route_locales_missing_start_anchor'))` — Andy's PGE 2026 captured `route_locales` with a `transition_area` at sequence_idx=1, no `start` row. If finish is also missing, expect a second `..._missing_finish_anchor` observation; if present (PGE 2026 should have `finish` set), expect only the start observation.
- `payload.race_week_brief.race_plan.segments` does NOT fabricate a start segment off `route_locales[0]` — the synthesizer should either omit a start anchor in the segments list or surface the absence in `mental_prep_cues` / `contingencies` / `pacing_strategy`.
- Audit the rendered user prompt for the `**Note:** no entry has role='start'...` line under the `# Route locales (D-66 structured graph)` section. The note should match whichever anchors are missing (start-only / finish-only / both).
- If Andy then edits the PGE 2026 row to add an explicit `RouteLocale(role='start', sequence_idx=0, ...)` and re-invokes the orchestrator (after `evict_on_target_event_brief_field_change`), confirm the `route_locales_missing_start_anchor` observation no longer appears AND the prompt note no longer references `role='start'`.

Captured in `CARRY_FORWARD.md` Manual §5.0 walkthrough section as a 1-step scenario alongside the PR #131 step.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Bucket C sub-items (a)-(j) terrain/locale vocab cleanup** — the predecessor ETLTerrainVocabDriftFix slice closed sub-item (k); (a)-(j) remain. Each item needs a Trigger #2 + #5 design pass before implementation. Best done as a paired design + implementation slice; ratify scope at AskUserQuestion gate. Sub-items cover: Time-of-Day / Social / Partner-team-presence not terrain factors; "Generic" useless; Climbing gym-vs-outdoor split; water-type expansion; locale-terrain vs Outdoor-Terrain merge (crosses `layer0.terrain_types` vs `layer0.equipment_items` schema boundary — Trigger #3); Cycling Trainer dedup; Mapbox free-text removal; Layer 2B classifier audit.

### 6.2 Alternative pivots

- **#8 "locales" → "locations" rename** — ~9 templates, mechanical. URL paths + blueprint names stay unchanged. No /plan triggers. Lowest-risk next-slice candidate.
- **Bucket E.(b)-B2 + E.(c)-C1 follow-on slice** — specs already pinned in `CARRY_FORWARD.md` (race_events.included_discipline_ids TEXT[] NULL + RaceTerrainEntry.discipline_id: str | None). ~6-9 files; needs ceiling-break ratification at scope gate.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on the body-part-to-movement-constraints mapping.
- **#2b race-URL LLM site-parse pre-fill** — Trigger #2 prompt design session first; then ~4-6 files runtime. New `race_url_parser.py` + caller-side integration.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 supplement-integration de-stub against `supplement_vocabulary`. LARGE ~6-8 files; architectural choice on schema shape requires plan-mode gate before kickoff. Closes Layer 2E §5.5 stub.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (RouteLocalesAnchorFlags forward-pointer in §5.0 walkthrough; predecessor ETL terrain-vocab drift fix forward-pointer still owed).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_RouteLocalesAnchorFlags_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep. Note: the script does not know about `etl/tests/` and will false-positive ❌ on the 4 ETL test files referenced; verify those exist under `etl/tests/` via `ls etl/tests/`.

**No outstanding production warnings.** ETL terrain-vocab drift warning lifted by the predecessor; route-locales validator loosen + downstream coaching-flag emission now closed end-to-end.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Anchor presence is by-role-anywhere not by first/last position | Architect (informally; no AskUserQuestion gate — architect-recommended slice with explicit spec) | Andy's PGE 2026 case has zero `role=='start'` rows anywhere; the by-role-anywhere semantic correctly fires the data_gap signal. A list like `[transition_area, start, ..., finish]` should NOT fire (start is present, just not first) — by-first-position would over-emit on legitimate captures. Reflects what the LLM needs to know about content completeness ("no start anchor was marked") not positional shape ("first row isn't a start row"). |
| **D2** | Observation surface is `notable_observations` via the existing `data_gap` pattern, not a new `coaching_flags` field on `RaceWeekBrief` | Architect | Mirrors the `kit_manifest_inputs_incomplete_*` precedent in `_emit_data_gap_observations` verbatim. No new surface area; no schema migration; no downstream consumer changes. Brief UI already renders `notable_observations` per Layer4_Spec.md §7.10. |
| **D3** | Skip emission when `route_locales` is empty | Architect | The empty case is already covered by the `kit_manifest_inputs_incomplete_no_route_locales` validator rule + corresponding orchestrator-emitted data_gap observation. Emitting both would be redundant noise. |
| **D4** | Prompt augmentation lives inside the existing `if race_event_payload.route_locales:` gated section in `_render_user_prompt` | Architect | The Route locales section already short-circuits on empty list (consistent with D3). The missing-anchor note renders only when route_locales is non-empty AND start/finish is missing — matches the helper's emission semantics 1:1. |
| **D5** | 2-file slice (race_week_brief.py + test file; no orchestrator changes) | Architect | The existing `notable_observations.extend(...)` chain in `llm_layer4_race_week_brief` is the composition point; orchestrator.py just wraps the returned `Layer4Payload`. No need to touch `layer4/orchestrator.py` despite the handoff §6.1's "orchestrator OR context.py" guess — the cleanest surface is the brief module that owns the observation composition. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/race_week_brief.py` `_emit_route_locales_anchor_observations` defined | ✅ `grep -n "def _emit_route_locales_anchor_observations" layer4/race_week_brief.py` returns 1 hit |
| `_emit_route_locales_anchor_observations` wired into `notable_observations.extend(...)` chain | ✅ `grep -n "_emit_route_locales_anchor_observations(race_event_payload)" layer4/race_week_brief.py` returns 1 hit inside `llm_layer4_race_week_brief` body |
| `_render_user_prompt` augmented with missing-anchor note | ✅ `grep -n "first/last sequence_idx" layer4/race_week_brief.py` returns 1 hit |
| `tests/test_layer4_race_week_brief.py` import extended for `_emit_route_locales_anchor_observations` | ✅ `grep -A3 "from layer4.race_week_brief import" tests/test_layer4_race_week_brief.py` shows the 3-line multi-import block |
| NEW `TestRouteLocalesAnchorObservations` class with 7 tests | ✅ `grep "class TestRouteLocalesAnchorObservations\\|def test_empty_route_locales_emits_nothing\\|def test_both_anchors_present_emits_nothing\\|def test_start_missing_finish_present_emits_one\\|def test_finish_missing_start_present_emits_one\\|def test_both_anchors_missing_emits_two\\|def test_start_anywhere_in_list_counts\\|def test_observation_text_under_240_chars" tests/test_layer4_race_week_brief.py` returns 8 hits (1 class + 7 tests) |
| NEW end-to-end test in `TestObservationEmission` | ✅ `grep "def test_route_locales_missing_start_anchor_emits_observation" tests/test_layer4_race_week_brief.py` returns 1 hit |
| NEW 2 prompt-rendering tests in `TestPromptRendering` | ✅ `grep "def test_route_locales_missing_anchors_note_rendered\\|def test_route_locales_missing_start_only_note_rendered" tests/test_layer4_race_week_brief.py` returns 2 hits |
| Existing `test_route_locales_rendered_structured` extended with happy-path assertion | ✅ `grep -A1 "test_route_locales_rendered_structured" tests/test_layer4_race_week_brief.py` and the body now contains `assert "no entry has role=" not in prompt` |
| `layer4/race_week_brief.py` passes `python3 -m py_compile` | ✅ |
| `tests/test_layer4_race_week_brief.py` 56 → 65 passed | ✅ pytest run in 0.47s |
| Container-runnable subset 805 → 815 passed + 12 skipped | ✅ pytest run in 1.28s |
| ETL `etl/tests/` 139 → 139 passed | ✅ pytest run in 0.44s |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` PR #131 annotation updated + new §5.0 walkthrough scenario added | ✅ |

---

## 9. Files shipped this session

**Substantive (2 files; well under 5-file ceiling):**

1. `layer4/race_week_brief.py` — NEW `_emit_route_locales_anchor_observations` helper + wire-in into `notable_observations.extend(...)` chain inside `llm_layer4_race_week_brief` + `_render_user_prompt` missing-anchor note augmentation. +52 / -0.
2. `tests/test_layer4_race_week_brief.py` — Import extension + NEW `TestRouteLocalesAnchorObservations` (7 tests) + NEW end-to-end test in `TestObservationEmission` + NEW 2 prompt-rendering tests + 1 existing-test assertion extension. +124 / -0.

**Bookkeeping (3 files; do not count against ceiling):**

3. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor line preserved.
4. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket B PR #131 annotation updated to reflect the downstream coaching-flag emission shipped; NEW Manual §5.0 walkthrough scenario added under the existing PR #131 step.
5. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_RouteLocalesAnchorFlags_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **RouteLocalesAnchorFlags shipped end-to-end** ✅ — 2 substantive files; closes the §6.1 forward-pointer carried since the RouteLocalesValidatorHotfix slice (PR #131, 2026-05-23). `notable_observations` now carries `route_locales_missing_start_anchor` / `route_locales_missing_finish_anchor` data_gap observations whenever route_locales is non-empty but the corresponding role anchor is missing; `_render_user_prompt` surfaces the same signal explicitly so the LLM doesn't fabricate an anchor from first/last sequence_idx position.
- **Manual §5.0 walkthrough §5 step added** — verify the orchestrator surfaces the observation on Andy's PGE 2026 context and the prompt note renders correctly when anchors are missing.
- **Bucket C still carries sub-items (a)-(j)** — terrain/locale vocab cleanup design conversation deferred (each item needs Trigger #2 + #5 design pass).
- **ETL terrain-vocab drift §5.0 step still owed** — predecessor's forward-pointer; verify first post-merge prod Neon `etl.layer0.run` writes 16 structured rows + supersedes Andy's manual-fix `0C-v2.0-r2` cleanly.

**End of handoff.**
