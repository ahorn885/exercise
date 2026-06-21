# V5 Design — Layer 3D HITL Gate + Layer 4 §10.2 Infeasibility Re-scope (#213 / #214)

**Date:** 2026-06-21
**Branch:** `claude/issue-214-roh9iy`
**Type:** Design-only (spec-first; no code, no migration, no test delta)
**Stop-and-ask:** Trigger #4 (HITL gate design) — Andy approved "design only this session; build in slices next."

---

## 1. What this session did

Spec-first design pass on the Layer 3 human-review gate, plus the Layer 4 re-scope that feeds it. Two deliverables, both committed + pushed to the branch:

1. **NEW `specs/Layer3D_Spec.md`** — the 3D HITL aggregation + gate node, at the 14-section depth standard.
2. **REVISED `specs/Layer4_Spec.md` §10.2** — shape-infeasibility detectors re-scoped per Andy's four calls on #214.

No implementation. The build is the next session's work (see §6).

## 2. The design — Layer 3D gate (`specs/Layer3D_Spec.md`)

A **deterministic, no-LLM** node that runs after 3B and before Layer 4. Three jobs:

- **Aggregate** the human-review items the upstream nodes already emit and that are currently produced and **silently discarded** — 2A (`prompt_required` disciplines + `unresolved_flags`), 2D (`hitl_items`), 2E (`hitl_items` + `supplement_integration.contraindication_hitl_items`), 3B (`hitl_surface`). This closes a **live safety gap** (e.g. a 2D `post_surgical_clearance` block never reaching the athlete). All items normalize to one `GateItem` shape (source / severity / athlete-message / fix-affordance / evidence / resolution).
- **Detect** the two surviving #214 feasibility findings (they need 3B's phase structure × 2A bands × 2D exclusions × §K — exactly 3D's input set): `injury_pool_empty` (**blocker**) and `schedule_volume_under_target` (**warning**).
- **Gate** Layer 4: `gate_status ∈ {green, needs_review, blocked}`. Generation runs only on `green`. Blockers are **revise-only** (no acknowledge escape hatch); warnings/informational are **acknowledge-or-revise**.

**Andy's review-calls, all specced:**
- **Blocker UX (§5.1, §11):** a blocker card shows title + coaching-voice reason + a `[Fix this]` button to the `revise_target` (the Layer 1 field driving it); no acknowledge button. On save, the existing partial-update cascade re-runs the affected layers and the gate re-checks.
- **Parked-plan lifecycle (§11.1):** off-ramps are `[Save as pending & exit]` (plan stays `needs_review`, state persisted) or `[Cancel]` (voids the row, D-64). Re-entry via the **plans list "Needs review" badge** (the single discovery surface — no separate pending view). **One plan in flight at a time** — starting a new plan-create while one is parked is refused.
- **Staleness re-fire (§11.2):** a parked plan can go stale (provider sync → 3A → 3B re-runs → items change). The gate re-evaluates on re-entry, on any upstream re-run, and **at the `[Generate plan]` click**, guarded by `evaluated_against` (the `etl_version_set`). Resolutions survive recompute by stable `item_key` (§6.4); a stale-green plan that recomputes non-green reverts to `needs_review`.
- **Injury-blocker floor (§5.2):** a phase with `< 3` distinct usable strength exercises after 2D exclusions is the blocker threshold (Andy: 3, not 2).
- **Storage (§10):** new `plan_versions.generation_status='needs_review'` value + a `hitl_gate` JSONB column. No new table at v1 scale.

**Scope cut:** **3C cross-node conflict detection is deferred** → new sub-issue **#844** (parented to #211). The §5 aggregation loop is written so 3C drops in as one more `map_3c_items()` source with **no `Layer3DGate`/`GateItem` contract change**. The 3.5 hard gate **folds into 3D** (no standalone node, per Control_Spec §2).

## 3. The design — Layer 4 §10.2 re-scope (`specs/Layer4_Spec.md`)

Andy's four calls on the original four `Layer4ShapeInfeasibleError` detectors:

| Original detector | Disposition |
|---|---|
| `schedule_volume_infeasible` | **Demoted to a warning** (`schedule_volume_under_target`, owned by 3D). Layer 4 already clamps prescribed volume to available hours, so it builds + warns; never blocks. "Trim to the hours they have and tell them it's probably not enough, but allow it through." |
| `discipline_frequency_infeasible` | **Deleted** — "not every discipline trains every week." |
| `skill_acquisition_infeasible` | **Deleted** — "we don't train skills." |
| `cumulative_load_injury_infeasible` | **Kept** — the one real blocker. Detection moved to the 3D gate (`injury_pool_empty`); Layer 4 keeps a **defensive** raise only (fires only if synthesis is somehow reached on the infeasible shape). |

Also **closed the long-open routing question** (§12.3 finding C3 + §12 open item): `Layer4ShapeInfeasibleError` routes to the **3D gate**, not an inline error. Swept every cross-reference: §3.5, §6.4, §10.2, §10.10, §12.3/§12.4, §13 (TS-10..13 struck/demoted, TS-75), §14, header changelog.

## 4. Tests / suite

None — design artifacts only. No code touched, no migration, no `LAYER4_PROMPT_REVISION` bump. Test scenarios are **specified** (Layer3D §14 TS-3D-1..17; Layer4 §13 TS rows updated) for the build session to implement against.

## 5. Commits (branch `claude/issue-214-roh9iy`)

1. `Layer3D_Spec.md` create + `Layer4_Spec.md` §10.2 rewrite + cross-ref sweep
2. 3D parked-plan lifecycle §11.1 + staleness re-fire §11.2 + TS-3D-13..17
3. injury-blocker strength-pool floor 2 → 3 (both specs)
4. bookkeeping (this handoff + `CURRENT_STATE.md`) — rides the work PR per the Ops operating flow

## 6. Next session — the build-slice plan

The whole point now is **implementation of the 3D gate** (#213). Andy's flagged sequencing (Layer3D §14 gut check):

1. **Slice 1 — read surface + acknowledge path.** Aggregate the already-emitted upstream items, render the review screen, support acknowledge (warnings) + the `needs_review`/`hitl_gate` DB state + the plans-list "Needs review" badge + one-in-flight enforcement. **This alone closes the silent-discard safety gap** and is low-risk (no cascade).
2. **Slice 2 — the two feasibility detectors** (`injury_pool_empty` blocker + `schedule_volume_under_target` warning) + the Layer 4 defensive raise + deleting the two retired Layer-4 detector classes.
3. **Slice 3 — the revise cascade** (the riskiest piece: edit Layer 1 field → invalidation cascade re-runs affected layers → gate re-checks). Most testing. Includes the staleness re-fire wiring (§11.2).
4. **Later — 3C** (#844): cross-node conflict detection as one more aggregation source.

Each slice is its own PR. Slice 1 is the natural next pickup.

### 6.3 Operating notes for next session — session-start read order
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — the new lead entry (3D gate design) + Layer-3 status rows
3. `CARRY_FORWARD.md` — rolling cross-session items (unchanged this session)
4. This handoff
5. `./scripts/verify-handoff.sh` — anchor sweep
6. Then read `specs/Layer3D_Spec.md` end-to-end + `specs/Layer4_Spec.md` §10.2 before writing any gate code.

## 7. Open items / decisions still owed from Andy

- None blocking the build. The design is fully resolved for v1 (Andy answered all four Layer-4 calls + all three 3D UX questions + the threshold).
- **Thin spot (named, not blocking):** what *wakes* a staleness re-evaluation when the athlete isn't on the screen — v1 leans on "re-check on next view / next click" rather than a push the instant a sync lands. Fine at handful-of-athletes scale; the generate-click guard is the backstop (Layer3D §14).

## 8. Rule #9 verification table (input to next session's anchor sweep)

| Claim | File | Anchor string | Check |
|---|---|---|---|
| 3D spec exists, 14 sections | `specs/Layer3D_Spec.md` | `## 14. Test scenarios + gut check` | `grep -c '^## ' specs/Layer3D_Spec.md` → 14 |
| Parked-plan lifecycle specced | `specs/Layer3D_Spec.md` | `### 11.1 Parked-plan lifecycle` + `Save as pending & exit` | grep |
| Staleness re-fire specced | `specs/Layer3D_Spec.md` | `### 11.2 Staleness re-fire` | grep |
| Injury floor = 3 | `specs/Layer3D_Spec.md` | `` `< 3` distinct usable exercises `` | grep |
| Layer 4 §10.2 re-scoped | `specs/Layer4_Spec.md` | `### 10.2 Shape-infeasibility detection — moved to the 3D gate` | grep |
| Frequency/skill detectors deleted | `specs/Layer4_Spec.md` | `**Deleted.**` ×2 in §10.2 table | grep |
| Routing C3 resolved | `specs/Layer4_Spec.md` | `routing — RESOLVED (2026-06-21)` | grep |
| CURRENT_STATE lead entry | `CURRENT_STATE.md` | `3D HITL GATE DESIGNED + LAYER 4 §10.2 INFEASIBILITY RE-SCOPED` | grep |
| 3C sub-issue filed | GitHub | issue #844, parent #211 | `gh`/MCP issue_read |

## 9. Issue reconcile (done this session)

- **#214** — commented the re-scope + routing resolution; design refined (4→1 blocker + 1 warning; 2 deleted; routing → 3D gate). Kept open `status:designed` — implementation folds into the 3D gate build.
- **#213** — commented: 3D gate now has a full per-node spec; 3C carved out to #844; 3.5 folds into 3D. Kept open `status:designed` (spec done, build not started).
- **#844** — NEW, filed for the deferred 3C cross-node conflict detection; parented to epic #211.
