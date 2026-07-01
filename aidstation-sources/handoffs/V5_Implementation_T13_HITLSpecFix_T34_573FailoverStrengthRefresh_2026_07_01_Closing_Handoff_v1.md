# V5 Implementation — T-1.3: HITL-Escalation Spec Fix + T-3.4/#573: Failover-Strength-in-Refresh — Closing Handoff (2026-07-01)

**Session:** Continuation of `PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` §4 Global order, after T-1.1+T-1.2. Two tasks: T-1.3 (doc-only, ungated) then T-3.4 (#573, ungated, independent — went to plan mode mid-session per Trigger #1).
**Date:** 2026-07-01
**Plan doc:** [`plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md) §3 T-1.3, T-3.4
**Predecessor handoff:** [`V5_Implementation_GenerationObservations_418_ShapeOverrideCleanup_T11T12_2026_07_01_Closing_Handoff_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/handoffs/V5_Implementation_GenerationObservations_418_ShapeOverrideCleanup_T11T12_2026_07_01_Closing_Handoff_v1.md)
**Branch:** `claude/orphaned-data-partial-wiring-87rdt7` — **not yet pushed / no PR opened** (holding per the project's PR-gated operating flow; Andy hasn't said "open it" yet).
**Status:** T-1.3 committed standalone (commit `e87cd8d`, doc-only). T-3.4 committed as one working-tree change (8 substantive code files — over the nominal 5-file ceiling, but the two pieces share the same `PlanSession`/tool-schema touch and were ratified together in plan mode as one unit, mirroring the T-1.1+T-1.2 precedent). Suite: **4129 passed / 30 skipped, 0 failed**.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` — all ✅ (files exist, predecessor §8 anchors match on-disk state). Confirmed `origin/main` was already at the branch tip (`git merge-base --is-ancestor origin/main HEAD` true) — no drift to reconcile.

## 2. What shipped

### T-1.3 — Drop the unwired HITL-escalation claim (`Layer4_Spec.md`)

Doc-only, per plan. Found the false claim ("observations with `elevates_to_hitl=True`... considered for the NEXT plan invocation" / "escalate to next-run HITL gate") in **four** places, not the two (§6.2/§8.7) the plan named — also §2 boundaries and the §7.10 `Observation` field comment made the identical claim. Fixed all four plus added an explicit clarifying line at the end of §8.7. All now state: advisory metadata, surfaced on `/admin/plan/<id>/inspect` (per T-1.1), gates nothing. Did not touch the still-stale `shape_override` spec references (§6.4/§7.8/test scenarios) — that's a separate gap T-1.2's own scope never assigned to any task; flagging here, not building it.

### T-3.4 / #573 — Failover-strength trigger wiring into refresh + `strength_substitution` marker

**Investigation surfaced the plan's task text was materially wrong**, not just imprecise:
- Its file list (`layer4/plan_refresh.py`) is a dispatcher; the real renderers are the tier files.
- Its premise ("mirror the create-path behavior") implied nothing was wired — but #557 (terrain-feasibility *data* into refresh) had already shipped. What was actually still missing: the failover *trigger tag* (`grid_annotation()`'s `[TERRAIN-INFEASIBLE]`/`[NO CRAFT]` bracket strings) that `STRENGTH_PROGRAMMING_GUIDANCE` is keyed to scan for — that tag is emitted only from create's own weekly-session-grid renderer, which refresh has no equivalent of at all. All three refresh tiers instead render a different, tag-free prose block (`_format_session_feasibility`). So the failover template was still dormant on refresh, just for a more specific reason than the issue's wording.
- Issue #573 itself (checked directly via GitHub — the project's backlog source of truth) also specified a smaller "advisory-quality tail" (a `strength_substitution` marker + validator scoping) that the plan's paraphrase dropped entirely.

Because the tail requires new LLM-facing prompt wording, this went to **plan mode** per Trigger #1; Andy reviewed and approved the two-piece plan (saved plan file, now executed) before any prompt text was written.

**Piece A (mechanical — reuses existing annotation/guidance text verbatim, no new prompt authored):**
- `layer4/per_phase.py::_format_session_feasibility` — new `include_grid_tag: bool = False` param; appends `grid_annotation(...)` per discipline line when `True`. Create's own call site (`:2660-2664`) is untouched — default `False` preserves its exact output (satisfies the plan's "Do NOT change create-path behavior").
- `layer4/plan_refresh_t1.py`, `plan_refresh_t2.py` — pass `include_grid_tag=True` at their existing call.
- `layer4/plan_refresh_t3.py` — same, **plus** added the `STRENGTH_PROGRAMMING_GUIDANCE` import + splice into `SYSTEM_PROMPT`, which was missing there entirely (T3 had no strength-programming guidance block at all, unlike T1/T2).

**Piece B (`strength_substitution` marker, Trigger #1 prompt wording):**
- One new sentence, ratified in plan mode, appended to `layer4/strength_guidance.py::STRENGTH_PROGRAMMING_GUIDANCE`'s FAILOVER STRENGTH paragraph: *"Set strength_substitution: true on any session composed this way; leave it false (or omit it) for a PROGRAMMED session."*
- `layer4/payload.py::PlanSession` — new `strength_substitution: bool = False` field.
- `layer4/per_phase.py::_session_schema` + `layer4/plan_refresh.py::_session_schema` — new `"strength_substitution": {"type": "boolean"}` tool-schema property (not required).
- `layer4/validator.py::_rule_strength_frequency_band` — counting condition changed from `s.kind == "strength"` to `s.kind == "strength" and not s.strength_substitution`, so failover sessions no longer count toward the programmed-dose ±1 advisory.

No migration, no DDL, no `LAYER4_PROMPT_REVISION` bump (reserved for T-2.9 per plan R1) — this rides the existing `terrain_feasibility_hash` cache-key invalidation.

## 3. Tests

- `tests/test_layer4_plan_refresh.py` — extended `test_terrain_feasibility_block_rendered_when_present` (T1) with the bracket-tag assertion; added `test_t2_terrain_feasibility_block_carries_grid_tag`, `test_t3_terrain_feasibility_block_carries_grid_tag`; added `test_strength_substitution_property_is_optional_boolean` (refresh tool schema).
- `tests/test_layer4_terrain_feasibility_wiring.py` — new `test_format_session_feasibility_include_grid_tag_flag` (direct unit test of the new param, both branches).
- `tests/test_layer4_strength_templates.py` — new `test_guidance_instructs_strength_substitution_marker`; renamed `test_both_refresh_prompts_embed_shared_guidance` → `test_all_three_refresh_prompts_embed_shared_guidance` (now covers T3 too).
- `tests/test_layer4_payload.py` — new `test_strength_substitution_defaults_false`, `test_strength_substitution_round_trips_true`.
- `tests/test_layer4_plan_create.py` — new `test_strength_substitution_property_is_optional_boolean` (create-path tool schema).
- `tests/test_layer4_validator.py` — new `test_strength_frequency_band_excludes_substitution_sessions`, `test_strength_frequency_band_still_fires_without_substitution_flag` (via the real driver + Pydantic models).
- `tests/test_layer4_strength_frequency.py` — the dedicated duck-typed rule unit-test file needed its `_sess()` fixture updated (new attribute the rule now reads) or its **existing 3 tests failed outright** (`AttributeError: 'SimpleNamespace' object has no attribute 'strength_substitution'`) — caught by the full-suite run, not the targeted one. Added `test_substitution_sessions_excluded_from_count`.
- Full suite: **4129 passed / 30 skipped, 0 failed.** Measured the exact delta by `git stash`-ing this session's changes and re-running: baseline **4118 passed / 30 skipped** (matches the T-1.1+T-1.2 handoff's post-merge-with-passkeys figure) → **+11** net new passing tests this session (T2/T3 render-tag tests, the `include_grid_tag` unit test, the guidance-marker test, 2 payload tests, 2 schema tests, 2 validator tests, 1 duck-typed substitution test; the T1 test and the renamed all-three-tiers guidance test extend/rename existing tests rather than add new ones).

## 4. GitHub bookkeeping (this session)

- **#573 — commented + closed** (`completed`): both the root-cause wiring gap and the advisory tail landed together; see PR link once opened.
- **#418 — not touched this session** (T-1.3 doc-only; the checklist item it closes was already ticked in T-1.1+T-1.2's session).
- Plan doc updated in-place: T-1.3 and T-3.4 both flipped to **DONE** with anchor notes (including the as-built file-list correction for T-3.4, so the next session doesn't re-trust the stale `layer4/plan_refresh.py`-only file list).

## 5. Next session pointers

Per the execution plan's §4 Global order, after T-1.3 + T-3.4:

- **T-1.4 (#930) — GATE: Andy must ratify the one-sided taper anchor wording** in `layer4/week_seam_review.py`'s `SYSTEM_PROMPT` before this can build. Must land before T-1.5 (R3 ordering rule).
- **WS-5** (integrations, T-5.1…T-5.7) — fully independent, no plan-gen coupling, can run in parallel with anything above.
- **WS-2 remains GATED** on Andy ratifying the render-vs-trim table (plan §3 WS-2 header).
- **WS-3 remaining:** T-3.1 (rides the T-2.9 walk, not yet run), T-3.2 (GATED — Andy confirms the saturation-cap rule), T-3.3 (Layer-0 migration GATED).
- Flagged, not built: `Layer4_Spec.md`'s stale `shape_override` sections (§6.4/§7.8/test scenarios) post-T-1.2 removal — no task in the plan currently owns this doc cleanup.
- **Do NOT bump `LAYER4_PROMPT_REVISION`** ("20") until T-2.9 (single bump + one real-LLM walk, per plan R1).
- **Not yet pushed / no PR** — per the project's PR-gated operating flow, waiting for Andy's explicit go before opening one.

### Operating notes (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`
6. `./scripts/verify-handoff.sh`

---

## 6. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| T-1.3 spec fix | `aidstation-sources/specs/Layer4_Spec.md` | `grep -c "escalate to next-run HITL gate"` → 0 |
| Grid-tag param | `layer4/per_phase.py` | `def _format_session_feasibility(...include_grid_tag: bool = False...)` |
| T1/T2 wiring | `layer4/plan_refresh_t1.py` / `plan_refresh_t2.py` | `include_grid_tag=True` at the `_format_session_feasibility(` call |
| T3 wiring | `layer4/plan_refresh_t3.py` | `include_grid_tag=True` at its call + `from layer4.strength_guidance import STRENGTH_PROGRAMMING_GUIDANCE` + splice in `SYSTEM_PROMPT` |
| Prompt wording (ratified) | `layer4/strength_guidance.py` | `"Set strength_substitution: true on any session composed this way"` in `STRENGTH_PROGRAMMING_GUIDANCE` |
| PlanSession field | `layer4/payload.py` | `strength_substitution: bool = False` on `PlanSession` |
| Tool schemas | `layer4/per_phase.py` / `layer4/plan_refresh.py` | `"strength_substitution": {"type": "boolean"}` in both `_session_schema()` |
| Validator scoping | `layer4/validator.py` | `if s.kind == "strength" and not s.strength_substitution:` in `_rule_strength_frequency_band` |
| Tests | `tests/test_layer4_plan_refresh.py` | `test_t2_terrain_feasibility_block_carries_grid_tag`, `test_t3_terrain_feasibility_block_carries_grid_tag` |
| Tests | `tests/test_layer4_terrain_feasibility_wiring.py` | `test_format_session_feasibility_include_grid_tag_flag` |
| Tests | `tests/test_layer4_strength_templates.py` | `test_all_three_refresh_prompts_embed_shared_guidance`, `test_guidance_instructs_strength_substitution_marker` |
| Tests | `tests/test_layer4_payload.py` | `test_strength_substitution_defaults_false`, `test_strength_substitution_round_trips_true` |
| Tests | `tests/test_layer4_plan_create.py` | `test_strength_substitution_property_is_optional_boolean` |
| Tests | `tests/test_layer4_validator.py` | `test_strength_frequency_band_excludes_substitution_sessions`, `test_strength_frequency_band_still_fires_without_substitution_flag` |
| Tests (fixture fix) | `tests/test_layer4_strength_frequency.py` | `_sess(...)` includes `strength_substitution=strength_substitution` |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 4129 passed / 30 skipped |
| Neon | — | No `layer0-apply` owed — no schema change, no migration |
| GitHub | — | #573 closed `completed`; plan doc T-1.3/T-3.4 flipped to DONE in-place |
| Branch | — | `claude/orphaned-data-partial-wiring-87rdt7`; not pushed, no PR (Andy hasn't said go) |

**End of handoff.**
