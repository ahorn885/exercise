# V5 — #844: Layer 3C cross-node conflict detection — CN-1/CN-2 + surfaced coaching_flags (closing)

**Date:** 2026-06-23 · **Branch:** `claude/eloquent-meitner-86ebqs` · **PR:** [#911](https://github.com/ahorn885/exercise/pull/911) (open, auto-merge SQUASH armed; CI dispatched manually — see §5) · **Commits:** `f1b7a86` (Slice 1) · `181c5a0` (Slice 2) · `b7513c3` (§7.1 severity policy) · **Issues:** #844 + #216 closed (completed).

---

## 1. What shipped

Built the deferred **Layer 3C** node into the 3D gate, per the **#216 design Andy ratified 2026-06-23** (two AskUserQuestion rounds): **rules-only (no LLM)**, scope = **net-new conflict detection + surfacing the orphaned upstream `coaching_flags`**. Purely additive to `evaluate_layer3d_gate`'s §5 step-3 aggregation — **no `GateItem` / `Layer3DGate` contract change**. The `GateSource` Literal already carried `"3C"`.

**Slice 1 — `map_3c_items(layer2a, layer2c_payloads, layer2d)`.** Two **warnings**, acknowledge-able, revise → the locations list (`profile.locales`):
- **CN-1 `discipline_gated_all_locales`** — an *included* 2A discipline gated off (`toggle_off_for_discipline` / `requires_skill_capability`) at **every** locale (the cross-locale AND no single per-locale 2C payload can see).
- **CN-2 `substitute_gated_all_locales`** — a `high`/`elevated`-risk 2D discipline whose usable (not-`still_at_risk`) `suggested_substitutes` are **all** gated off at every locale; **suppressed** when 2D already emitted `no_substitute_for_high_risk` / `gap_x_high_risk_concurrent`; **mutually exclusive** with the §5.2 `cardio_modality_banned` blocker.
- Deliberately conservative — fires only on an *every-locale* intersection (under-fires, never false-fires; zero locales → skipped). `routes/plan_create.py` gained the `profile.locales → locales.list_profiles` revise surface (the registry had no per-locale equipment token; `locales.edit_profile`/`list_profiles` verified real).

**Slice 2 — `surface_orphaned_flags(...)`.** The advisory `coaching_flags` from 2A/2B/2C/2D/2E (computed today, silently discarded) surface as **informational** gate items:
- **`compute_gate_status` made informational-non-gating** — informational items are display-only, never park a plan (else surfacing would flood every plan to `needs_review`). A plan whose only items are informational stays **green** and proceeds; the flags stay in the persisted gate record but aren't shown at gate-time on a green plan. This also relaxes pre-existing **3B `informational`** hitl_surface items from gating (consistent with the display-only intent).
- **2B threaded in** — `layer2b_payload` added to `evaluate_layer3d_gate` (optional; orchestrator passes `cone.layer2b_payload`); kept **out** of the §4 etl-coherence check like 2C.
- All surfaced flags → gate-severity `informational` regardless of source-local severity (2E's own info/low/moderate/high → `evidence['flag_severity']`). **`source='3C'`** (the surfacing node — keeps `GateSource` closed, no `2B`/`2C` enum add); origin in `source_item_id='{origin}:flag:{flag_type}'`. `revise_target` per origin (2A→disciplines, 2B→`h2.*`, 2C→locales, 2D→injuries, 2E→nutrition — all already registered).
- **Suppression:** a 2C gear/skill flag already escalated to CN-1/CN-2, or a 2D flag whose discipline has a mapped 2D hitl_item, is dropped.

**Severity policy (§7.1).** All **24 builder-emitted** flag_types enumerated + dispositioned. **All-informational at v1** (Andy 2026-06-23 picked "decide at build time → react to a concrete table" → chose ship-all-informational). Promotion to gating `warning` = a one-line add to `_FLAG_WARNING` in `gate.py`. Unknown/stubbed flag_types (e.g. 2E `heat_acclim_gap`, spec'd in `Layer2E_Spec` §8.5 but §5.8-stubbed → not emitted) fall through to informational with no 3D change. ★ top warning-candidates if ever promoted: `unbridgeable_terrain`, `low_calorie_target_relative_to_rmr`.

**3C node is now complete.** The §5/§5.1 aggregation + §5.2/§5.3 feasibility detectors were already shipped (#213/#868).

---

## 2. Files touched (5 substantive + bookkeeping)

| File | Change | Anchor (Rule #9 check) |
|---|---|---|
| `layer3d/gate.py` | `map_3c_items` (CN-1/CN-2), `surface_orphaned_flags` + `_surfaced_flag_item` + `_FLAG_WARNING` + `_FLAG_REVISE_TARGET` + `_msg_disc`; `compute_gate_status` informational-non-gating; `layer2b_payload` param + `Layer2BPayload` import | `grep -n "def map_3c_items\|def surface_orphaned_flags\|_FLAG_WARNING\|severity != \"informational\"" layer3d/gate.py` |
| `layer4/orchestrator.py` | `layer2b_payload=cone.layer2b_payload` at the `evaluate_layer3d_gate` call (~line 1782) | `grep -n "layer2b_payload=cone.layer2b_payload" layer4/orchestrator.py` |
| `routes/plan_create.py` | `"profile.locales": ("locales.list_profiles", {})` in `_PROFILE_REVISE_SURFACES` | `grep -n "profile.locales" routes/plan_create.py` |
| `tests/test_layer3d_gate.py` | +21 tests (TS-3C); `_2c_flag`/`_2a_flag`/`_2b_flag`/`_2b_payload`/`_2d_flag`/`_2e_flag` builders; `coaching_flags=` added to `_layer2a/_layer2d/_layer2e` | `grep -n "def test_cn1\|def test_surface_\|_FLAG_WARNING" tests/test_layer3d_gate.py` |
| `specs/Layer3D_Spec.md` | §5 pseudocode + §5.4 NEW + §5.5 renumber + §5.1/§7 rows + **§7.1 NEW** + §9 + §13 + §14 TS-3C-1..9 | `grep -n "### 5.4 Cross-locale\|### 7.1 Surfaced" aidstation-sources/specs/Layer3D_Spec.md` |
| `CURRENT_STATE.md` | rolling-pointer update (this session as Last shipped) | bookkeeping |

---

## 3. Tests

- `tests/test_layer3d_gate.py` **+21**: CN-1/CN-2 fire + every suppress / no-false-fire branch; surfacing per source (2A/2B/2C/2D/2E); cross-source suppression; informational-non-gating (`compute_gate_status`); 2B-via-payload + skipped-when-None; the `_FLAG_WARNING` promotion mechanism (monkeypatch).
- **Full CI suite `tests/ etl/tests/` → 3571 passed / 30 skipped** (run in the scratchpad venv: `python -m venv … && pip install -r requirements.txt pytest`; `PYTHONPATH=. pytest tests/ etl/tests/`). ruff clean. `test_layer3d_wiring.py` can't run locally (Neon-block hangs the app import) — covered in CI.
- **No LIVE-VERIFY owed by Claude** — deterministic, fully stub-covered. The *value* proof is a real parked plan showing CN/flag items reading sensibly; flag `message` strings come verbatim from 2A–2E, so a poor-reading message is an upstream copy fix, not a 3C one.

---

## 4. Open / next

- **#911 merge:** auto-merge SQUASH armed; required checks dispatched via `workflow_dispatch` (§5). Confirm it merges; the subscription will surface CI failures / review comments.
- **3C future (not this slice, noted in §5.4/§7.1):** promote ★ flag_types to `warning` if prod shows misses; surface informational flags on **green** plans as plan-page coaching notes (a new UI surface — green plans don't display them at gate-time today).
- **Still Andy-owed (pre-existing):** the #213 `[Fix this]` revise-links + staleness re-kick **live-verify walk** (container can't run plan-gen).
- **Layer 3 epic #211** 3D/3C surface is now built. Next: pick the next Layer-3 issue or a v1 go-live item per the 4-tier order.

---

## 5. Operating notes (§6.3 — next-session read order, Rule #13)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — anchor sweep

**CI-trigger quirk (load-bearing):** GitHub Actions `ci.yml` did **not** auto-fire on PR-open for this branch (`actions_list list_workflow_runs` → `total_count: 0`), despite `on: pull_request` — the known web-flow quirk. Auto-merge would hang without the required checks (`Python unit suite (stubbed)` / `JS harness (jsdom)` / `Layer 0 integrity gate`), so I dispatched `ci.yml` via `actions_run_trigger run_workflow` on the branch ref to produce them against the PR head SHA. **Any future PR from a web session likely needs the same manual `ci.yml` dispatch before auto-merge can land.**

**`send_later` is NOT available** in this session — could not schedule the hourly PR self-check-in the subscription guidance asks for. Relying on webhook events (review comments / CI failures); CI-success and merge are not delivered by webhook, so the merge won't wake this session — auto-merge lands it without intervention.
