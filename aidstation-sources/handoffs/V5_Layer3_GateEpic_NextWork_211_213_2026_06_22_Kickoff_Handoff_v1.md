# V5 — Layer 3 gate epic (#211): next-work kickoff handoff

**Date:** 2026-06-22. **Author context:** written right after the #213 staleness `[Fix this]` revise links merged (PR #897). **Purpose:** a forward map for continuing the Layer-3 evaluation / HITL-gate epic (#211). This is a *kickoff* handoff (what to build next), not a closing one — the closing record for the just-merged work is `handoffs/V5_Implementation_Layer3D_ReviseLinks_213_2026_06_22_Closing_Handoff_v1.md`.

> **Rule #9 first.** Every file/line/symbol ref below was accurate at this date but **drifts** — re-verify against `main` before relying on it. Run `aidstation-sources/scripts/verify-handoff.sh` (from `aidstation-sources/`) + `git fetch origin main` + check the named issue for in-flight parallel work (the collision lesson — #865/#881 both got built twice).

---

## 1. Where the 3D gate stands (shipped)

The Layer 3D HITL gate is functionally complete end-to-end:

- **Slice 1** (#850) — the no-LLM aggregation core (`layer3d/gate.py` `evaluate_layer3d_gate`), orchestrator hook (`orchestrate_plan_create` raises `Layer3DGateBlocked`), review screen (`GET /plans/v2/<id>/review` + acknowledge + green-gated generate), plans-list "Needs review" badge, one-in-flight.
- **Slice 2** (#868) — the two §5.2/§5.3 feasibility detectors (`detect_injury_pool_empty` blocker, `detect_schedule_volume_under_target` warning).
- **Slice 3 / staleness** (#880 Reading-B, consolidated; #881 Reading-A reverted) — `compute_gate_input_fingerprint` (SHA-256 over raw leaf inputs, no LLM) + the on-view consumer (`routes/plan_create.py` `_gate_inputs_changed` / `_rekick_stale_gate` re-kick to `generating` so the poller re-evaluates).
- **Revise links** (#897, this arc) — `plan_create._build_revise_urls` turns each item's `revise_target` into a `[Fix this]` link; Rule #15 re-kick telemetry; 3A/3B prompt-rev pointer comments.

**3.5 "resolution gate"** is effectively shipped *inside* 3D (the review screen + green-gated `[Generate plan]`); there is no separate 3.5 node to build.

**The one owed item on the shipped work:** `#213` **live-verify** (Andy-action — the container can't run plan-gen). Park a plan at `needs_review`, edit a profile/race field, re-enter `/review` → it re-kicks (progress screen) + re-evaluates against the edit, each item shows a working **Fix this** link, and `/admin/logs` shows the `_rekick_stale_gate:` line. **#213 stays open until this walk.**

---

## 2. The remaining work map (open issues under #211 + Layer-3)

| Issue | What | Status | Size | Priority |
|---|---|---|---|---|
| **#216** | 3C: **decide** rules-only vs LLM + **enumerate** the conflict rules | designed/deferred (open design decision) | spec pass | med |
| **#844** | 3C: **build** the `map_3c_items()` cross-node detector feeding the gate | designed (drops in, no contract change) | 1 slice | med |
| **#217** | flip the 3B evidence-basis **warning → hard error** | ✅ **SHIPPED 2026-06-22** (mode-discriminator only → `Layer3BOutputError`; name-existence kept warn-only) — `handoffs/V5_Implementation_Layer3B_EvidenceBasisHardError_217_2026_06_22_Closing_Handoff_v1.md` | — | done |
| **#302** | surface/trim **orphaned** Layer-3 analysis (notable_observations, viability adj., periodization rationale, sleep_quality) | deferred | med | med |
| **#219** | 3A refinements (≥3 sources for 'high', completeness override, Haiku cost test) | deferred | small-med | low |
| **#393** | confirm the **health-screening data contract** (blocks L3 spec) | deferred | contract decision | high (v1/compliance) |
| **#213** | the gate umbrella | open — live-verify + 3C pending | — | high |

**Recommended sequencing (4-tier order from CLAUDE.md):**
1. **Live-verify #213** (tier-2, closes a shipped-but-unverified function) — Andy-action.
2. ~~**#217** (flip 3B evidence-basis to a hard error)~~ — ✅ **SHIPPED 2026-06-22** (only the §7 mode-discriminator flipped; name-existence stays warn-only for 3A parity; Rule #15 FAIL log added). Closing handoff: `handoffs/V5_Implementation_Layer3B_EvidenceBasisHardError_217_2026_06_22_Closing_Handoff_v1.md`.
3. **3C: #216 design → #844 build** (tier-4, the headline remaining *node*). #216 is a **stop-and-ask** (see §3). **← next.**
4. **#302** (tier-3/4 — newly attractive: the gate can now consume the orphaned 3A/3B observations).
5. **#219 / #393** as priority allows (#393 is a compliance contract, not gate code).

---

## 3. 3C cross-node conflict detection (the headline) — #216 then #844

**The gate was designed for this drop-in.** `specs/Layer3D_Spec.md` §5 aggregation loop + §7 item taxonomy reserve a 3C row; 3C lands as one more `map_3c_items(...)` source emitting the same `GateItem` shape — **no `Layer3DGate`/`GateItem` contract change.** (Re-read `Layer3D_Spec.md` §5/§7/§13/§14.)

**#216 is a STOP-AND-ASK (do this first).** Two open decisions, both Andy's call:
- **Rules-only vs LLM.** A deterministic rules pass is cheaper, testable, and matches the gate's "no-LLM" character (the rest of 3D is pure). An LLM step would be Trigger #1 (prompt design) **and** Trigger #5 (architectural). **Recommend rules-only** unless the conflict set proves to need semantic judgment — but present both with the tradeoff and let Andy decide before building.
- **Enumerate the conflict rules.** The cross-node contradictions to detect across 2A–2E, e.g.:
  - a discipline **included in 2A** with **no supporting equipment in 2C** (can't train it where the athlete is),
  - an **injury/exclusion in 2D** that contradicts a **2A inclusion** (already partly covered by the Slice-2 cardio-modality-banned detector — *de-dupe against it*),
  - a **2E nutrition constraint** vs a **2A/2B demand** mismatch,
  - terrain (2B) the athlete has no access/equipment for (2C).
  Enumerate the full set with Andy; each becomes one rule emitting a `GateItem` (source `"3C"`, a stable `item_key`, a `revise_target`).

**#844 build shape (after #216):** a pure `layer3d/` function `map_3c_items(layer2a, layer2b, layer2c_payloads, layer2d, layer2e) -> list[GateItem]` wired into `evaluate_layer3d_gate`'s aggregation (mirror `map_2d_items`/`map_3b_items`). Add `TS-3C-*` to `tests/test_layer3d_gate.py`. **Watch the §9 de-dup** — 3C may restate a finding 2D/2E already emit; use the explicit-suppression pattern Slice 2 used for cardio-modality-banned (the `item_key` de-dup can't merge across sources).

---

## 4. #217 — flip 3B evidence-basis warning → hard error (mechanically-applicable; Rule #11)

`layer3b/builder.py`: `Layer3BEvidenceBasisWarning(UserWarning)` (def ~line 81) is raised via `warnings.warn(...)` at **3 sites** (~1039, ~1051, ~1059). `Layer3BOutputError(RuntimeError)` already exists (~line 66). The flip = convert each `warnings.warn(<msg>, Layer3BEvidenceBasisWarning)` to `raise Layer3BOutputError(<msg>)` (the issue says it's gated on §H.2 goal capture, which has shipped — confirm that's still true).

**Before flipping (Rule #9 + #14):** re-read each of the 3 sites — confirm what each guards and that a hard failure is the intended behavior for all three (some may be advisory and should stay warnings). Update `tests/test_layer3b_builder.py` (the `Layer3BEvidenceBasisWarning` cases → expect `Layer3BOutputError`; there are existing `pytest.warns` assertions to flip to `pytest.raises`). **This is a plan-failing change** — a bad evidence_basis now fails the plan instead of warning, so be sure that's wanted across all 3 sites (raise it with Andy if any looks advisory). No migration/contract change.

---

## 5. #302 — orphaned Layer-3 analysis (gate tie-in)

3A/3B compute analysis that nothing reads: `Layer3APayload.notable_observations` + `Layer3BPayload.notable_observations` (write-only), `GoalViability.suggested_adjustments`/`.confidence`, `PeriodizationShape.reasoning_text`, and the captured-but-unthreaded `SleepRecord.sleep_quality` (1–5 vs 1–10 scale mismatch noted). **New tie-in:** the 3D gate now exists, so `notable_observations` could surface as informational gate items (or into a Layer-4 prompt). Checklist is in the issue body. Med priority; coordinate with the gate so it doesn't double-surface 3B's `hitl_surface` (already consumed).

---

## 6. Operating notes

### 6.1 Session-start read order (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — top entry (the #897 revise-links session)
3. `CARRY_FORWARD.md` — the Layer-3 Slice-3 bullet (now "review-screen UX remainder SHIPPED") + the container test-run gotcha
4. **This handoff** (for what to build next) + the `…ReviseLinks…` closing handoff (for what just shipped)
5. `aidstation-sources/scripts/verify-handoff.sh` — anchor sweep
Then `git fetch origin main` + check #216/#844/#217 for in-flight parallel work.

### 6.2 Container test recipe (no Neon)
`DATABASE_URL="postgresql://u:p@127.0.0.1:5999/none?connect_timeout=2" /tmp/venv/bin/python -m pytest tests/test_layer4_orchestrator.py tests/test_layer3d_gate.py tests/test_layer3d_wiring.py -q` with `dangerouslyDisableSandbox: true` + a `timeout`. The dead-localhost `DATABASE_URL` fast-fails the import-time Neon connect (else app-importing suites hang on collection); front-load a `test_layer4_*` to dodge the single-file circular-import quirk. Set up the venv once: `python3 -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

### 6.3 Two recurring lessons
- **Parallel-build collisions** (#865, #881) were invisible until `git log origin/main` *after* merge. Check the epic/issue for an existing branch/PR/merged commit **at session start AND right before opening a PR**.
- **Handoff route refs drift** — the #897 work caught two wrong endpoints in the prior handoff (`locales.edit_profile`→`profile.edit`; `race_event_edit`→`race_events.edit_race`). Verify endpoints/symbols against on-disk routes before wiring; a wrong link/ref is worse than a TODO.

### 6.4 PR-gated operating model
Work on the session branch, commit + push, finish bookkeeping, **wait for Andy's "open it"** before opening the PR; then `enable_pr_auto_merge`. This overrides the harness "always open a PR" default. Required checks: `Python unit suite (stubbed)` / `JS harness (jsdom)` / `Layer 0 integrity gate`. If a container push doesn't trigger CI, `actions_run_trigger run_workflow` (`workflow_dispatch`) on `ci.yml` against the branch.

---

## 7. Recommended first move next session
~~Start **#217** (fast, ready-to-flip, low-risk)~~ — ✅ **DONE 2026-06-22** (mode-discriminator → hard error; see §4). Next: open the **#216** 3C design conversation with Andy (rules-only vs LLM + the conflict-rule enumeration) since that gate decision blocks the largest remaining piece (#844). Don't start #844 before #216 is ratified. **#302** (orphaned 3A/3B observations → gate items) is the secondary option.
