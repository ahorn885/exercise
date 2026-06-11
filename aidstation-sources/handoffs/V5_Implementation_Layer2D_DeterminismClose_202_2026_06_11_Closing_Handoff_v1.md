# Layer 2D determinism close (#202) + injury-accommodation workflow gaps — Closing Handoff

**Session:** Closed #202 (plan-gen non-determinism) by day-anchoring Layer 2D's post-surgical recency to the cone's `today`; audited the rest of the injury-accommodation workflow and filed the remaining broken items.
**Date:** 2026-06-11
**Predecessor handoff:** `V5_Implementation_SkillCapabilityGating_336_2026_06_11_Closing_Handoff_v1.md`
**Branch:** `claude/happy-davinci-hsf02q` → **PR [#554](https://github.com/ahorn885/exercise/pull/554)** (`Closes #202`), squash-merged to `main`
**Status:** 3 substantive files (under ceiling). #202 closed; #555 filed; #242 annotated. Suite green.

---

## 1. Session-start verification (Rule #9)

This session started from a question ("is #202 still a problem?"), not a continuation, so the predecessor's §8 table wasn't the gate — but the relevant anchors were checked live while tracing the bug:

| Claim | Anchor | Result |
|---|---|---|
| `plan_create_key` folds every layer hash 1→3b | `layer4/hashing.py:147` | ✅ read |
| 2A `generated_at` already day-anchored | `layer2a/builder.py:938-940` (`.replace(hour=0,…)`) | ✅ read |
| 3A `now` is validation-only, never hashed | `layer3a/builder.py:403-408` | ✅ read |
| 3A integration fallback already day-anchored | `layer3a/integration.py:477` | ✅ read |
| loading_type_change validator skipped in v1 | `layer4/validator.py:919-922` + `test_…_skipped_silently_in_v1` | ✅ read |

**Reconciliation note:** clean — no drift.

---

## 2. Session narrative

Andy asked whether GitHub #202 (plan-gen cache-key non-determinism, parent #201) is still a problem. Traced the full chain: `plan_create_key` (`layer4/hashing.py:147`) folds in **every** layer hash 1→3b, and the per-phase/per-block keys chain off it (`compute_block_cache_key`). So any builder timestamp that reaches a payload reaches the cache key.

**Audit result — #202 was already substantially fixed; Layer 2D was the one genuine remaining instance:**
- Layers 1 / 2A / 2E: day-anchored + regression-tested (pre-existing).
- 3A `builder.py:403` (`now`): used only in the future-date validation guard, never hashed → safe.
- 3A `integration.py:477`: already day-anchored fallback + tested.
- uuid session-id prefixes (plan_create / per_phase / plan_refresh / single_session): feed output `session_id` strings only; keys chain on `prev_accepted_output_hash`, not the uuid → safe (issue's "ruled out" note holds).
- **2D `builder.py:567`**: `_is_recent_post_surgical` used wall-clock `datetime.utcnow().date()`; its recency bool drives the cross-education loading swap → 2D payload → `layer2d_hash` → `plan_create_key`. Day-granular (no sub-day thrash) but wall-clock-anchored, so it could drift the cache key across a UTC calendar boundary between resumable passes — the lone layer not anchored to the cone's `as_of`/`today`.

Andy chose: **fix 2D + close #202**, and **investigate downstream** ("if this triggers, will the LLM hang / is it deterministic?").

**Downstream finding (the substantive answer):** the post-surgical recency branch (`_apply_phase_contraindications` Rule 3) is currently **unreachable end-to-end** — `_severity_to_verdict` maps Post-surgical → `exclude` in both the body-part and movement-constraint verdict paths, which dominates `_max_verdict`, so `_recommend_accommodations` (and thus the swap) never runs for a Post-surgical driver. So the `utcnow()` never actually reached the payload; the fix is defensive/forward-looking. *If* the branch is ever made reachable, the injected `loading_type_change(unilateral_contralateral)` modality renders as a **bounded enum** in the synthesizer prompt (no LLM-hang/parse risk) — but two real soft spots surface, both now tracked (see §6).

No prompt body was touched (Trigger #1 deliberately avoided).

---

## 3. File-by-file edits

### 3.1 `layer2d/builder.py` (modified)
- `_is_recent_post_surgical(injury, today)` — added `today: date` param; replaced `datetime.utcnow().date()` with `today`. Docstring records the #202 cache-key rationale.
- Threaded `today` up the call chain it sits in: `_apply_phase_contraindications` (line ~489), `_recommend_accommodations` (~677), `_evaluate_exercise` (~714), and the public entry `q_layer2d_injury_risk_profile_payload` (~1240) which gained `today: date | None = None` with a defensive day-anchored fallback (`if today is None: today = datetime.utcnow().date()`) — mirrors the established `layer3a/integration.py:477` pattern (sole production caller always supplies it).
- `from datetime import date, datetime` (added `date`).

### 3.2 `layer4/orchestrator.py` (modified)
- Both 2D call sites (lines ~382, ~759) pass `today=today` (already in scope as the cone's day anchor).

### 3.3 `tests/test_layer2d.py` (modified)
- New `TestPostSurgicalRecencyDeterminism` (+2): `_is_recent_post_surgical` keys off the passed `today` (42-day boundary), not wall-clock; same `today` → stable `compute_payload_hash`.

---

## 4. Code / tests

Suite green: `tests/` **2265 passed / 30 skipped**, `etl/tests/` **88 passed**. New tests: `test_recency_window_keys_off_passed_today_not_wall_clock`, `test_payload_hash_stable_across_passes_for_same_today`. CI green on #554 (Python unit suite, Layer 0 integrity gate, JS harness, Vercel; Real-LLM smoke skipped).

---

## 6. Next session pointers — the remaining injury-accommodation workflow gaps (THIS SESSION'S FOCUS)

The #202 fix closed the determinism leak, but the audit surfaced three coupled gaps in the **Layer 2D → Layer 4 injury-accommodation workflow**. None is a go-live blocker today (the path that exercises them is dormant), but they're the "other broken items" to fix when this feature is next exercised. Priority order:

### 6.1 The three gaps

1. **#555 (filed) — prompt rendering drops modality params + rationale.** `layer4/per_phase.py:_format_active_injuries` (line 611) renders only `modality_type` *names*, not the params (factor / tempo tuple / `from_type`→`to_type` / cap) or `rationale`, for **all six** modality types. The LLM is told the accommodation *category* but not its *magnitude/direction/reason*, and pointed at the spec to infer the rest. **Fix = a prompt-body change → Stop-and-ask Trigger #1** (design pass + Andy sign-off first). Mechanically: extend the line-625 join to format each modality's discriminated fields + rationale.

2. **#242 (pre-existing, annotated) — validator skips `loading_type_change` enforcement.** `layer4/validator.py:919-922` returns early for `LoadingTypeChangeModality` (no implement/laterality metadata on `ResolvedExercise` in v1). Combined with #555, `loading_type_change` is the one modality that is both under-specified to the LLM **and** unenforced. Blocked on the v1→v2 laterality-metadata extension. Also covers the placeholder-threshold calibration (4×10 / 60min / 80%1RM / RPE8 sentinels).

3. **Dead-branch / design question (noted on #242, not yet its own issue).** The cross-education swap in `_apply_phase_contraindications` Rule 3 is **unreachable** because Post-surgical → `exclude` in both verdict paths. Decision needed: **(a)** remove it as dead code, or **(b)** route Post-surgical-*with-clearance* to `accommodate` (there's already a `post_surgical_clearance` HITL warn path in 2D) so the swap actually fires for cleared athletes. This is the design fork that decides whether #242 + #555's loading-type work is ever live. Surface to Andy before acting (Trigger #5).

### 6.2 Alternative pivots
The 4-tier order still puts go-live blockers **#539** (tab-closed plan-gen crawl) + **#540** (terrain-infeasible locale routing) above this workflow — #540 is the adjacent "don't prescribe what the athlete can't do" feasibility gate (terrain side). The injury-accommodation gaps above are tier-3 (open-but-not-fully-live) and dormant, so they rank below #539/#540 unless Andy wants to finish the accommodation feature end-to-end.

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. **#202 is shipped + merged (PR #554).** The injury-accommodation workflow has three open gaps (#555, #242, the dead-branch fork) — all dormant today because the post-surgical accommodate path is unreachable.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Fix 2D (anchor to `today`) + close #202 | Andy | Cleans the last wall-clock call out of a builder; consistent with every other layer's `as_of` anchor; defensive for if the verdict mapping ever changes |
| 2 | Don't touch the prompt rendering (#555) this session | Claude (Trigger #1) | Rendering params into the synthesizer prompt is an LLM-prompt-body change → needs Andy sign-off |
| 3 | File the rendering gap as its own issue (#555), annotate #242 | Claude | Distinct failure mode (prompt under-spec) from #242 (validator skip); issues are the single source of truth |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_is_recent_post_surgical(injury, today)` uses `today`, not `utcnow()` | ✅ `layer2d/builder.py` |
| Both orchestrator 2D calls pass `today=today` | ✅ `layer4/orchestrator.py:382,759` |
| New determinism tests present + pass | ✅ `TestPostSurgicalRecencyDeterminism` |
| Suite green | ✅ tests/ 2265 + etl/tests/ 88 |
| #202 closed, #555 filed, #242 annotated | ✅ GitHub |

---

## 9. Files shipped this session

**Substantive (3 files):**
1. `layer2d/builder.py`
2. `layer4/orchestrator.py`
3. `tests/test_layer2d.py`

**Bookkeeping:**
4. `aidstation-sources/CURRENT_STATE.md`
5. `aidstation-sources/CARRY_FORWARD.md`
6. this handoff

---

## 10. Carry-forward updates

Added a "Layer 2D determinism close (#202)" section to `CARRY_FORWARD.md` recording the close + the three open workflow gaps (#555 / #242 / dead-branch fork). No new owed Andy's-hands deploy (no DDL, no SQL).

---

**End of handoff.**
