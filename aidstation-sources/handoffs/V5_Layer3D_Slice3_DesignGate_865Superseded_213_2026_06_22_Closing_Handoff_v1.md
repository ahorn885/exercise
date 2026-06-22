# V5 — Layer 3D HITL Gate: Slice 3 design-gated + #865 (parallel Slice 2) closed as superseded (#213)

**Date:** 2026-06-22. **Branch:** `claude/eloquent-hypatia-d9igts`. **Outcome:** no feature code shipped this session — a parallel-built Slice 2 (#865) was found to duplicate already-merged work and was closed; Slice 3 was design-gated on two Andy decisions, one of which is a Trigger #3 contract change to be specced first next session. This handoff + the `CURRENT_STATE`/`CARRY_FORWARD` updates are the only thing merged.

---

## 1. What this session did

1. **Closed PR #865 as superseded (not merged).** This branch had independently built #214/#213 **Slice 2** (the §5.2/§5.3 feasibility detectors + a Layer 4 defensive raise). While rebasing onto `main` to merge it, I found a **parallel-build collision**: another session had already built and merged Slice 2 as **`0a3fd9d`** ("Layer 3D gate: add §5.2/§5.3 feasibility detectors", PR #868), plus **`28108ae`** ("Layer 4 §10.2: 3D gate is sole guard for injury-pool-empty — no defensive raise"). Main's version is a **superset** of #865 (real `cardio_modality_banned` 3D detector *with* 2D-HITL suppression; richer tests) and made the **opposite** call on the defensive raise (main removed it; #865 added it). Nothing in #865 improved on main → closed it, corrected my earlier comments on #214/#866.
2. **Design-gated Slice 3** (the revise cascade + staleness re-fire). A Plan agent mapped it against current `main`; two genuine decisions were surfaced to Andy, who chose **both heavier options** — which turns Slice 3 into a spec-first design + a 2-sub-slice build (details §3).
3. **Found + worked around a CI-trigger quirk** (commits pushed from this branch don't trigger GitHub Actions; `workflow_dispatch` is the workaround — §4).

**Net to `main`:** bookkeeping only (this handoff + `CURRENT_STATE` + `CARRY_FORWARD`). No code, no spec change, no migration.

---

## 2. The collision (why #865 was abandoned)

Two sessions took #214/#213 Slice 2 in parallel; the other merged first.

| | This branch (#865, closed) | `main` (#868, `0a3fd9d` + `28108ae`) |
|---|---|---|
| `detect_injury_pool_empty` / `detect_schedule_volume_under_target` | built | built (same) |
| §5.2 cardio case | relied on 2D `no_substitute_for_high_risk` only | **3D `cardio_modality_banned` detector** + suppresses itself when 2D already emits `no_substitute_for_high_risk`/`gap_x_high_risk_concurrent` (handles both paths) |
| Layer 4 defensive raise | **added** `Layer4ShapeInfeasibleError` + `assert_strength_pool_feasible` | **removed** — 3D gate is sole guard (`28108ae`; `layer4/errors.py` doesn't exist on main) |
| tests | 1 cardio test | superset (TS-3D-5/6/7 + edge cases) |

**Lesson (now in CARRY_FORWARD):** the collision was invisible until `git fetch origin main`. When running concurrent Claude sessions on the same epic, check for an existing PR/branch/merged commit on the issue at session start (Rule #9 spirit, extended to the remote). My session started mid-flight on this branch without re-checking main for in-flight duplicate work.

---

## 3. Slice 3 — decisions + design direction

Slice 3 = the two remaining pieces of #213: **(1) revise cascade** (edit a Layer 1 field from the review screen → existing `Control_Spec §4` invalidation re-run → gate re-check) + **(2) staleness re-fire** (§11.2). Slice 1 (PR #850) built the review screen + acknowledge path + orchestrator hook; Slice 2 (#868) the detectors.

### 3.1 Andy's two decisions (2026-06-22)

1. **Recompute runs ASYNC like plan-gen** (not synchronous-on-GET). A revise edit-save flags a background cone re-run + gate re-eval (mirroring plan-gen's off-thread model); the review screen shows a "re-evaluating" state and polls; on completion the gate + status flip (green ↔ needs_review). *Rejected:* synchronous recompute inside `plan_review` GET (would spin ~tens of seconds firing 3A/3B LLM re-derivation on a cache miss).
2. **`evaluated_against` becomes a real per-athlete upstream-version FINGERPRINT** (not the Layer-0 platform digest it is today). A cheap equality check then gates whether a recompute is owed. *This is a Trigger #3 gate-contract change (new field semantics, cross-layer)* → **must be specced first, with Andy's sign-off, before code.** *Rejected:* "always recompute / treat the digest as provenance" (the literal-but-cheaper reading).

### 3.2 Design direction (to be specced in §6.1/§11.2)

- **Fingerprint:** `evaluated_against` = composite of the upstream **input** hashes the gate depends on — `compute_payload_hash(layer1_payload)` (`layer1_hash`, already exists) + the 2A/2C/2D/2E/3B payload hashes. Cheap to compute from inputs **without** re-running any LLM node (outputs are deterministic functions of inputs + prompt version). Open design point: confirm the exact hash source for 2A/2C/2E (3B's cache key already folds `layer1_hash` + `layer3a_hash` per `layer3b/cached_wrapper.py:182`).
- **Cheap staleness check:** on review re-entry + generate-click, compute the current fingerprint from current inputs and compare to the stored one. Match → gate fresh, show it. Mismatch → stale → trigger recompute. (This is what makes the fingerprint earn its keep — no blind cone re-run.)
- **Async recompute:** edit-save (or detected staleness) → background cone re-run + `evaluate_layer3d_gate` + persist; review screen polls a "re-evaluating" state; gate + `generation_status` flip on completion. Gate-level staleness logic (resolved_status reverting a re-surfaced `revised`→`pending`, re-blocking on a new pending blocker, prior-resolution carry by `item_key`) is **already built + unit-tested** — Slice 3 is the route/async trigger around it.
- **`[Fix this]` revise links:** map `GateItem.revise_target` → the existing edit surface (`profile.injuries`→injuries list; `profile.disciplines`/`.nutrition`/`.availability`→profile edit; `h2.goal_outcome`/`h2.event_date`→the target-race editor — **confirm canonical post-onboarding race editor**, candidates `onboarding.target_race` / `routes/race_events.py`).

### 3.3 Proposed split (past the 5-file ceiling as one slice)

- **Slice 3a** — fingerprint contract + cheap staleness check + the generate-click guard + `[Fix this]` revise links. (The Trigger #3 piece; `Layer3D_Spec` §6.1/§11.2 spec update first.)
- **Slice 3b** — the full async auto-recompute + polling UI ("re-evaluating" state).

### 3.4 Plan agent's file map (current `main` line refs — re-verify before editing)

- `layer4/orchestrator.py` — extract a **`recompute_layer3d_gate(...)`** helper from the create-path hook at **`1727-1789`** (cone build + `evaluate_layer3d_gate` + `save_hitl_gate`, returns the gate, does NOT raise/synthesize; optional pre-built `cone=` param so the create path reuses the cone it already built and pays no extra cost). Keep the lazy imports. Rule #15 log (plan_version_id, gate_status, item count, fingerprint changed?). etl digest helper at `_q_current_etl_version_set` ~`1954`; gate copies it at `gate.py:720`.
- `routes/plan_create.py` — review-flow call sites: `plan_review` GET **`1508-1554`**, `resolve_review_item` POST **`1557-1606`** (acknowledge), `generate_from_review` POST **`1609-1644`**; advance-loop `Layer3DGateBlocked` catch **`796-816`**; `needs_review` short-circuit **`573-574`**; orchestrate import ~`66`.
- `templates/plan_create/review.html` — revise affordance is a **plain-text stub** at **`60-65`** (`Fix via: {{ it.revise_target }}`) → make it `[Fix this]` link(s).
- `plan_sessions_repo.py` — `save_hitl_gate` `105`, `load_hitl_gate` `122`, `load_prior_resolutions` `144` (no change needed for 3a beyond storing the new fingerprint).
- `layer3d/gate.py` — `evaluate_layer3d_gate` signature already carries `prior_resolutions` + `evaluated_against`; `resolved_status` ~`521`; `compute_gate_status`. The fingerprint change lands here (how `evaluated_against` is computed/compared).
- Invalidation machinery: injuries flow through `layer1_payload` (`layer1/builder.py:100` `_load_injuries`); **2D is a query node** rebuilt every cone call (`orchestrator.py:1063` `q_layer2d_injury_risk_profile_payload`, no cache); 3A/3B cached but keyed on `layer1_hash`. Push-eviction `evict_on_layer_change` (`layer4/cache_invalidation.py:116`) is used only for 2B/2C in `routes/locales.py:183,198` — **the revise cascade needs no new eviction for injuries/disciplines/nutrition/availability** (they self-invalidate via `layer1_hash`).
- Tests: `tests/test_layer3d_wiring.py` (route trigger — TS-3D-16 stale-on-re-entry-adds-blocker, TS-3D-17 stale-at-generate-click) + `tests/test_layer3d_gate.py` (gate-level, already covers the resolution/staleness logic).

**DB migration:** none (the `hitl_gate` JSONB + `needs_review` status exist; the fingerprint rides inside the existing JSONB `evaluated_against`).

---

## 4. CI-trigger quirk (ops — also in CARRY_FORWARD)

Commits pushed to this branch via the container's git path **did not trigger the `CI` workflow** (`.github/workflows/ci.yml`, required checks `Python unit suite (stubbed)` / `JS harness (jsdom)` / `Layer 0 integrity gate`), even though the commit reached GitHub (Vercel's webhook built it). Symptom: PR head has only the `Vercel` status; `actions_list` shows zero CI runs for the branch while *other* `claude/*` PRs trigger CI normally. Consistent with GitHub not running Actions for pushes attributed to an app/bot token. **Workaround that works:** `actions_run_trigger run_workflow` (`workflow_dispatch`) on `ci.yml` against the branch — the jobs run against the branch head and post the required check contexts on that commit (by name), satisfying branch protection; auto-merge then fires. Confirmed this session (run #763 went green on `2587cc9` before #865 was abandoned). **This bookkeeping PR will need the same dispatch.**

---

## 5. Next session

### 5.1 Start here

**Slice 3a, spec-first.** Write the `Layer3D_Spec` §6.1 (the `evaluated_against` fingerprint contract — composition + how computed/compared) + §11.2 (staleness re-fire uses the fingerprint; async recompute) **before any code**, get Andy's sign-off (Trigger #3). Then build 3a per the §3.4 file map. Then 3b (async UI). Re-verify the line refs in §3.4 against `main` first (Rule #9). Confirm the two open design points: exact 2A/2C/2E hash sources; canonical post-onboarding target-race editor for the `h2.*` revise links.

### 5.2 Operating notes — session-start read order (Rule #13)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — latest pointer (this session is the top entry)
3. `CARRY_FORWARD.md` — rolling items (note the new CI-trigger + collision entries)
4. **This handoff**
5. `./scripts/verify-handoff.sh` — anchor sweep (Rule #9)

Then: `git fetch origin main` and check #213/#214/#211 for any *new* in-flight Slice 3 work before building (the collision lesson).

---

## 6. Open items / decisions owed

- **Trigger #3 design sign-off** on the `evaluated_against` fingerprint (composition + semantics) — owed before any 3a code.
- **Two design confirmations:** exact 2A/2C/2E payload-hash sources; canonical edit surface for an already-created target race (`h2.goal_outcome`/`h2.event_date` revise targets).
- **LIVE-VERIFY owed (Andy-action, unchanged from Slice 2 #868):** create a plan whose injuries empty the strength pool / ban an only-modality discipline → parks at review with the blocker; a schedule below a phase target → the warning, acknowledge → green, generates clamped.
- **Branch hygiene:** the closed-PR branch `claude/eloquent-hypatia-d9igts` was force-reset to `main` for this bookkeeping commit; the superseded Slice 2 commits live only in closed #865.

---

## 7. Rule #9 verification table (input to next session's anchor sweep)

| File | Anchor / check | Expect |
|---|---|---|
| `aidstation-sources/handoffs/V5_Layer3D_Slice3_DesignGate_865Superseded_213_2026_06_22_Closing_Handoff_v1.md` | this file exists | ✅ new |
| `aidstation-sources/CURRENT_STATE.md` | top entry grep `SLICE 3 DESIGN-GATED` | ✅ new top entry; #868 Slice 2 demoted to predecessor |
| `aidstation-sources/CARRY_FORWARD.md` | grep `CI-trigger quirk` + `parallel-build collision` | ✅ two new rolling items |
| code | `git log origin/main..HEAD --stat` | **bookkeeping files only** — no `.py`/spec/template changes |
| PR #865 | state | closed (not merged); superseded by #868 |

---

## 8. Issue reconcile

- **#865** — closed (not merged); superseded by #868. Comments corrected.
- **#866** — closed not_planned (cardio handled on main via `0a3fd9d`'s `cardio_modality_banned` detector; my "covered by 2D" framing corrected in a comment).
- **#214** — commented (Slice 2 + cardio shipped via `0a3fd9d`; my earlier "covered by 2D" note corrected). Left open (others manage state).
- **#213** — **Slice 3 still open**; comment added recording Andy's two decisions + the 3a/3b split + this handoff. The build-tracking issue for the next session.
- **#211** epic, **#844** (3C) — untouched; 3C remains the later slice.
