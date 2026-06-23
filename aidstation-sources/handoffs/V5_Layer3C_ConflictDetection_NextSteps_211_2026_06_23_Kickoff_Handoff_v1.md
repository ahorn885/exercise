# V5 — Layer 3C cross-node conflict detection (#211): next-steps kickoff handoff

**Date:** 2026-06-23. **Author context:** written right after Layer 3C Slice 1 (CN-1/CN-2 + orphaned-flag surfacing) merged — `#844` build, `#216` design, PR **#911** (now on `main`). The closing record for that work is `handoffs/V5_Implementation_Layer3C_ConflictDetection_844_2026_06_23_Closing_Handoff_v1.md`. **Purpose:** a forward map for the *next* 3C increment. This **supersedes §3 of** `handoffs/V5_Layer3_GateEpic_NextWork_211_213_2026_06_22_Kickoff_Handoff_v1.md` — that section said "decide #216 → build #844," which is now done.

> **Rule #9 first.** Every ref below was anchor-verified against `main` on 2026-06-23, but it **drifts** — re-verify before relying on it. `cd aidstation-sources && ./scripts/verify-handoff.sh`, `git fetch origin main`, and check #211 for in-flight parallel work (the #865/#881 double-build lesson) before starting.

---

## 1. Where 3C stands (shipped, #911)

Layer 3C is the rules-only (no-LLM) node that catches conflicts **no single upstream node can see** because they live only in the *intersection* of payloads 2A–2E. It drops into the 3D gate's §5 aggregation as one more source — **no `Layer3DGate` / `GateItem` contract change**. Two detectors + a flag-surfacing pass shipped:

- **CN-1 — included discipline gated off at *every* locale.** A 2A `inclusion == "included"` discipline that every locale's 2C surface gates (`toggle_off_for_discipline` or `requires_skill_capability`). Emits a `3C` **warning** (`source_item_id="discipline_gated_all_locales"`, revise → `profile.locales`).
- **CN-2 — injury substitute gated off at *every* locale.** A `high`/`elevated`-risk 2D discipline whose *usable* (not `still_at_risk`) substitutes are all gated everywhere. Emits a `3C` **warning** (`substitute_gated_all_locales`). **Suppressed** when 2D already surfaced `no_substitute_for_high_risk`/`gap_x_high_risk_concurrent`; **mutually exclusive** with the §5.2 `cardio_modality_banned` blocker.
- **Orphaned-flag surfacing.** The 24 upstream `coaching_flags` (2A/2B/2C/2D/2E) surface as `3C` items keyed `{origin}:flag:{flag_type}`. **All informational at v1** (display-only, never park a plan) — Andy 2026-06-23: keep informational, tune from prod signal.

Both detectors are deliberately **conservative — they under-fire rather than false-fire** (every-locale intersection; a discipline trainable at even one locale never trips). Keep that bias for anything new.

**Anchors** (`grep -n`): `layer3d/gate.py` → `def map_3c_items` (~315), `def surface_orphaned_flags` (~520), `_FLAG_WARNING` (~480), call site `cn_items=cn_items` (~1031). Spec: `Layer3D_Spec.md` `### 5.4` (~131), §7 taxonomy table (~236), §7.1 severity table (~240–269), §13 (~360). Tests: `tests/test_layer3d_gate.py` `test_cn1_*` / `test_cn2_*` (~953–1095).

---

## 2. The forward map

| # | Next-step item | Kind | Gate before building | Size | Priority |
|---|---|---|---|---|---|
| **A** | **§7.1 flag → `warning` promotions** (`unbridgeable_terrain`, `low_calorie_target_relative_to_rmr`, …) | config flip | **prod signal** (a real plan where the informational flag should have parked) | XS (Rule #11 edit, §5) | med — *signal-gated* |
| **B** | **Surface informational flags on *green* plans** as plan-page coaching notes | new UI surface | none (additive) | S | med |
| **C** | **New conflict rules (CN-3+)** | net-new detection | **STOP-AND-ASK** design (Trigger #5 + spec-first); §4 | M per rule | low until signal |
| **D** | **#213 live-verify walk** | manual verify | — (Andy-action; orthogonal to 3C) | — | tier-2 |

**Recommended order = the 4-tier rule (CLAUDE.md):** D (close a shipped-but-unverified function) → B (small, no design gate, completes the surfacing story) → A (the moment prod gives a miss) → C (only if prod shows CN-1/CN-2 miss a *real* class of conflict). See §7.

---

## 3. How to add a detector (the extension pattern)

3C was built to grow by appending, not refactoring. A new detector is a predicate over payloads `evaluate_layer3d_gate` already holds, emitting `GateItem`s into the same list.

1. **Add the predicate inside `map_3c_items()`** (`layer3d/gate.py:~315`) — or a sibling `map_*` helper called next to it at the §5 step-3 site (`~1023–1031`). Signature today: `map_3c_items(layer2a_payload, layer2c_payloads, layer2d_payload) -> list[GateItem]`. If a rule needs 2B/2E, widen the call (2B/2E are already in scope at the call site — mirror how `surface_orphaned_flags` takes all five).
2. **Emit via the existing template** (copy the CN-1 block, `gate.py:~378–403`): `make_item_key("3C", "<detector_id>", <entity_id>)`, `source="3C"`, `source_item_id="<detector_id>"`, `severity="warning"`, `revise_target=<one of _FLAG_REVISE_TARGET>`, `can_acknowledge=True`, `evidence={...}` (always include the IDs a reviewer needs + a `locale_count`).
3. **De-dup / suppress (§9 + §5.4).** A new rule will often restate something 2D/2E/CN-1 already say. `item_key` de-dup **cannot merge across sources**, so suppress explicitly — build a suppression set of disciplines already carried by an upstream `hitl_item` or an existing CN item (CN-2 does this at `gate.py:~406–411`; the flag pass takes `cn_items=` for exactly this). Under-fire.
4. **Test it** in `tests/test_layer3d_gate.py` with the CN pattern — a **fire**, a **no-false-fire** (the every-locale negative), and a **suppress** case. Template: `test_cn1_included_discipline_gated_at_every_locale_warns` (~953) builds minimal payloads → `_evaluate(...)` → asserts `source`/`severity`/`revise_target`/`evidence`. Add a `TS-3C-N` row to spec §12.
5. **Spec-first (layer-spec depth standard).** Any new rule is a `### 5.4` addition + a §7 taxonomy row + §12 TS rows *before* code — and rule enumeration is a **stop-and-ask** (§4).

**Run the suite (container, no Neon):**
```
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest
DATABASE_URL="postgresql://u:p@127.0.0.1:5999/none?connect_timeout=2" \
  /tmp/venv/bin/python -m pytest tests/test_layer4_orchestrator.py tests/test_layer3d_gate.py -q
```
(dead-localhost `DATABASE_URL` fast-fails the import-time Neon connect; front-load a `test_layer4_*` to dodge the single-file circular-import quirk. `dangerouslyDisableSandbox: true` + a timeout.)

---

## 4. New conflict rules (CN-3+) — STOP-AND-ASK before building

**Only CN-1/CN-2 were ever enumerated** (#216, ratified 2026-06-23). The spec reserves the pattern but lists no CN-3 (`Layer3D_Spec.md:~360`). So a new rule is **net-new design**, not unbuilt-but-specced work — Trigger #5 (architectural) + the spec-first standard. Do **not** code one before Andy ratifies the set.

**The bar (state it when you open the decision):** a rule earns its place only if it catches a contradiction that (a) **no single node already surfaces**, (b) lives in the **intersection** of ≥2 payloads, and (c) **materially changes the plan** if missed. Simplicity-first — under-fire, and don't add a rule a flag already covers.

**Candidate set to put to Andy** (seed, not a decision — each needs the de-dup check noted):

| Candidate | Cross-node | De-dup risk to check first |
|---|---|---|
| 2E calorie/fuel target below the 2A/2B race **demand** (not just below RMR) | 2E × 2A/2B | distinct from the §7.1 `low_calorie_target_relative_to_rmr` flag (that's 2E-vs-RMR, internal) — this is 2E-vs-demand |
| Race terrain demand (2B) with **no locale** offering it (2C access/equipment) at all | 2B × 2C | distinct from the `unbridgeable_terrain` flag (2B-internal, runway) — this is the cross-locale "nowhere to train it" |
| Included discipline (2A) whose **equipment_required is unsatisfiable** at every locale (2C tier-0), separate from a gear *toggle* | 2A × 2C | **likely overlaps CN-1 / 2C tier-0** — verify it's a distinct signal before speccing; may be a no-op |

Lower-conviction (raised, parked): cross-discipline shared-pool gating, cross-locale equipment incompatibility, schedule×discipline×locale time conflicts, summed-cross-locale volume vs available hours. Don't spec these without a concrete prod case.

**Recommendation:** *don't* build CN-3+ yet. There's no production signal that CN-1/CN-2 miss a real conflict class, and speculative detectors violate simplicity-first. Hold the candidate list; revisit when a real plan exposes a gap.

---

## 5. Items A & B — the signal-gated and additive work

**A — promote a flag to gating `warning` (Rule #11, mechanically-applicable).** When prod shows a plan that *should* have parked on an informational flag, flip it: in `layer3d/gate.py:~480` replace
```python
_FLAG_WARNING: set[str] = set()  # v1: empty (all flags informational)
```
with the opted-in set, e.g.
```python
_FLAG_WARNING: set[str] = {"unbridgeable_terrain", "low_calorie_target_relative_to_rmr"}
```
(the `severity` line at `~505` already reads it — `"warning" if flag_type in _FLAG_WARNING else "informational"`). Then flip those rows' severity column in the spec §7.1 table (`Layer3D_Spec.md:~250`, `~268`) from `informational` → `warning`, and add a TS row asserting the now-gating flag parks the plan. ★ in §7.1 = Andy's top promotion picks. **Gate: a real miss first** — Andy's v1 call is "all informational, tune from prod signal," so a promotion needs the signal, not a guess.

**B — surface informational flags on green plans.** Today informational flags only show on the review screen (i.e. when *something else* parks the plan); a fully-green plan never displays them. Surface them as plan-page coaching notes so the athlete sees "you're trail-running but it's gear-gated at your gym" even on a clean plan. Additive (no gate, no contract change): read the green plan's `hitl_gate` informational items in the plan-home render path and list them as notes. Keep the coaching voice (CLAUDE.md) — direct, no cheerleading. Confirm the exact render surface against `routes/plan_create.py` + the plan-home template before wiring (handoff route refs drift — the #897 work caught two wrong endpoints).

---

## 6. Operating notes (next session)

### 6.1 Session-start reads (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — top entry
3. `CARRY_FORWARD.md` — the Layer-3 live-verify bullet + the container test gotcha
4. **This handoff** + the `…Layer3C_ConflictDetection_844…` closing handoff
5. `aidstation-sources/scripts/verify-handoff.sh` — anchor sweep
Then `git fetch origin main` + check #211 for in-flight parallel work.

### 6.2 Stop-and-ask reminders
- **CN-3+ rule enumeration = Trigger #5 + spec-first** (§4). Present options + the bar + a gut check; wait.
- **Flag promotion (A) is gated on prod signal**, not a code decision you make unilaterally — it changes whether a plan parks.

### 6.3 PR-gated operating model
Work on the session branch, **commit + push**, finish bookkeeping (`CURRENT_STATE.md` / `CARRY_FORWARD.md` / closing handoff / reconcile #211), then **wait for Andy's "open it"** before opening the PR; then `enable_pr_auto_merge`. Required checks: `Python unit suite (stubbed)` / `JS harness (jsdom)` / `Layer 0 integrity gate`. **No separate doc-only PR** — bookkeeping rides the work's branch.

### 6.4 Recurring lessons
- **Parallel-build collisions** (#865/#881) were invisible until `git log origin/main` post-merge. Check #211 for an existing branch/PR/commit at session start **and** right before opening a PR.
- **Cross-source de-dup is manual** — `item_key` can't merge a 3C warning with the 2D/2C flag it restates; suppress explicitly (§3 step 3).

---

## 7. Recommended first move next session

3C's *node* is functionally complete; the next increment is **signal-driven, not more rules.** In 4-tier order:

1. **#213 live-verify** (tier-2) — Andy-action; closes the one shipped-but-unverified gate function. Not 3C code, but it's the open item blocking the gate epic's clean close.
2. **Item B — surface informational flags on green plans** (tier-3) — small, additive, no design gate, and it's the missing half of the surfacing story (today a green plan hides them). **Best first build.**
3. **Item A — flag promotions** — the moment prod hands you a miss; trivial flip (§5).
4. **CN-3+ (§4)** — only after a real conflict slips through CN-1/CN-2. Open it as a #216-style design conversation, not a build.

**Gut check.** The honest read is that **3C may be done for v1** — CN-1/CN-2 cover the every-locale cross-cuts, and Andy's "keep flags informational, tune from prod" stance means the remaining levers (A) are *deliberately* waiting on data we don't have yet. The risk in this handoff is over-investing the reader in CN-3+ candidates (§4) that simplicity-first says we shouldn't build speculatively — they're catalogued so the thinking isn't lost, **not** as a backlog to burn down. Best argument against "just do B and wait": if real athletes routinely hit cross-node conflicts CN-1/CN-2 miss, we'd want one more detector before launch — but we have zero such signal today, so building one now is guessing. Wait for the signal.
