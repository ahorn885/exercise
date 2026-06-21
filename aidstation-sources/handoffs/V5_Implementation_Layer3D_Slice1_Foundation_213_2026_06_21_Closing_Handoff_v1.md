# V5 Implementation — Layer 3D HITL Gate, Slice 1 (#213)

**Date:** 2026-06-21
**Branch:** `claude/v5-design-layer-3-4-0t0ybc` · **PR [#850](https://github.com/ahorn885/exercise/pull/850)**
**Type:** Implementation (code + tests + migration). **Full Slice 1** — the aggregation core **plus** the orchestrator hook + review/acknowledge UI + plans-list badge + one-in-flight. (The revise *cascade* is Slice 3.)
**Predecessor:** `handoffs/V5_Design_Layer3DGate_Layer4InfeasibilityRescope_213_214_2026_06_21_Closing_Handoff_v1.md` (the design pass that produced `specs/Layer3D_Spec.md`)

> **Update (same session):** this handoff was first written for the aggregation-core-only foundation; the Slice 1 wiring (orchestrator hook + review UI + badge + one-in-flight + repo accessors) was then built on the same branch/PR. §1a below records the wiring; the foundation sections (§2/§3/§4) are unchanged and still accurate.

---

## 1. What this session did

First build slice off the #213/#214 design. The handoff before this one specced the 3D gate end-to-end and named the build sequencing: **"Slice 1 — read surface + acknowledge path."** This session lands the **deterministic aggregation core that the rest of Slice 1 (and Slices 2/3) build on**, plus its DB migration, fully unit-tested without needing a live DB or running app.

Rule #9 sweep at session start: **clean** — `./scripts/verify-handoff.sh` green, `specs/Layer3D_Spec.md` present at the 14-section depth, working tree clean.

Deliverables (all committed to the branch):

1. **NEW `layer3d/` package** — `gate.py` (the gate) + `__init__.py` (re-exports).
2. **DB migration** in `init_db.py` — additive `plan_versions.hitl_gate JSONB` + `'needs_review'` added to the `generation_status` CHECK.
3. **`tests/test_layer3d_gate.py`** — +23 tests, all green.
4. **Bookkeeping** — this handoff + `CURRENT_STATE.md` lead entry (rides the work PR per the Ops flow).

## 1a. The wiring (Slice 1 remainder — built same session)

- **Orchestrator hook** (`layer4/orchestrator.py`, in `orchestrate_plan_create`): after the upstream cone + phase structure, before `llm_layer4_plan_create_cached`, it loads the athlete's prior resolutions (`load_prior_resolutions`), runs `evaluate_layer3d_gate`, persists the gate (`save_hitl_gate`), and **raises `Layer3DGateBlocked` when non-green** so the plan parks for review instead of running the minutes-long, dollar-cost synthesis. Imports are **lazy inside the function** to keep the `layer4` package import graph acyclic (`plan_sessions_repo` imports `layer4.payload`). Only plan-create is gated — refresh / race-week-brief orchestrators are untouched.
- **Advance loop** (`routes/plan_create.py`): `_advance_plan_generation_locked` catches `Layer3DGateBlocked` → flips the row to `generation_status='needs_review'` (NOT `failed`; no rollback, so the gate JSONB the orchestrator wrote in the same txn persists) and returns `{"status":"needs_review"}`. `_advance_plan_generation` short-circuits a `needs_review` row (the poller/cron never re-run the cone on it — it resumes only via [Generate plan]).
- **Review screen** (`routes/plan_create.py` + `templates/plan_create/review.html`): `GET /plans/v2/<id>/review` lists items grouped by severity (blockers first); `POST .../review/resolve` records an acknowledge (rejects a blocker — revise-only); `POST .../review/generate` is **green-gated** (refuses unless every item is resolved) and flips `needs_review → generating`, handing off to the progress poller (which re-runs the advance loop → gate re-evaluates green with the stored resolutions → synthesis proceeds). `progress.html` + the poller (`generate_plan`) redirect to the review screen on `needs_review`.
- **Plans-list badge** (`routes/plans.py` + `templates/plans/list.html`): a "Needs review" bucket + chip + a **Review** button (and a **Cancel** that voids via `delete_plan`). The query now includes `needs_review`. The single discovery surface (§11.1).
- **One-plan-in-flight** (`routes/plan_create.py:new_plan` POST): refuses a new create while one plan sits at `generating`/`needs_review`, redirecting to that plan's progress/review screen (§11.1).
- **Repo accessors** (`plan_sessions_repo.py`): `save_hitl_gate` (stamps `evaluated_at`; writes only the column — the caller owns the status transition), `load_hitl_gate` (tolerates a NULL/pre-migration column → None), `load_prior_resolutions` (`item_key → GateResolution`, resolved items only).
- **Gate fix** (`layer3d/gate.py`): added the `Layer3DGateBlocked` signal; the §4 etl-coherence check now **excludes 2C** — 2C encodes the source table in the *value* (`{'0A':'sports=v7',...}`), a different shape from the other nodes' bare `{'0A':'v7',...}`, so a literal compare wrongly tripped `etl_version_set_mismatch` (caught by `test_layer4_orchestrator`); 2C is unused by Slice 1 aggregation anyway.
- **Tests** (`tests/test_layer3d_wiring.py`, +15): repo round-trip; advance-loop parking + `needs_review` short-circuit; review routes (render / acknowledge / blocker-reject / generate-gating); one-in-flight. **Full suite 3200 passed / 30 skipped.**

**LIVE-VERIFY owed (Andy-action — the container can only reach a cold Neon, can't drive plan-gen):** create a plan for an athlete with a known upstream HITL item (e.g. a 2D post-surgical block) → the create lands on the review screen; acknowledge clears a warning; [Generate plan] enables only when green; the plans list shows the "Needs review" badge linking back. The green suite covers the routing + gate math, not the live LLM cone.

## 2. The code — `layer3d/gate.py`

A **pure, deterministic, no-LLM** function per `specs/Layer3D_Spec.md` §3/§5/§6 (no clock, no RNG, no DB access — the Control_Spec §5/§6 query-node contract). `evaluate_layer3d_gate(...)`:

- **Preconditions (§4)** — fail-fast `Layer3DGateError(code, detail)`: `plan_version_id_unset`, `missing_upstream_payload` (any of 2A/2C/2D/2E/3B None), `etl_version_set_mismatch` (the pins differ across supplied payloads, including each 2C locale).
- **Aggregation (§5 step 3 / §5.1)** — one mapper per source, each reading the upstream item verbatim and re-shaping to a uniform `GateItem`:
  - `map_2a_items` — `inclusion == 'prompt_required'` → **warning**; `unresolved_flags[].severity` `error` → **blocker**, `warning` → **warning**.
  - `map_2d_items` — `hitl_items[].severity` `block` → **blocker**, `warn` → **warning**; `revise_target='profile.injuries'` (§B injury record).
  - `map_2e_items` — `hitl_items` **+** `supplement_integration.contraindication_hitl_items`; `block_level == 'block'` → **blocker**, else **warning**.
  - `map_3b_items` — `hitl_surface[].severity` carried verbatim (`blocker`/`warning`/`informational`); `can_acknowledge` follows 3B's own contract (`acknowledge_option is None` ⇔ blocker); `revise_target` carried from 3B.
- **`item_key` (§6.4)** — `make_item_key(source, source_item_id, discriminator) = sha256(...)[:16]`, stable across rounds so a round-1 resolution still applies after an unrelated round-2 revise.
- **De-dup (§9)** — by `item_key` (a 2E contraindication item duplicating a `hitl_items` entry surfaces once).
- **Rule #15 guard (§9)** — when a source has `hitl_required=True` but emitted 0 items, log the inconsistency and **trust the empty list** (don't fabricate).
- **Resolution + status (§6.3)** — `resolved_status`: no resolution → `pending`; `acknowledged` → `acknowledged` (only when `can_acknowledge`; an acknowledge on a blocker is defensively dropped to `pending` — the route also rejects it); `revised` → `pending` when the item re-surfaces with the same key (the edit didn't clear it; a revise that *does* fix it makes the item disappear from re-aggregation, so it never reaches the function).
- **Gate status (§5 step 6)** — `compute_gate_status`: `green` when every item is resolved; `blocked` when any blocker is still pending; else `needs_review`.

Payload classes (§6): `Layer3DGate` (user_id, plan_version_id, gate_status, items, evaluated_against, evaluated_at), `GateItem`, `GateResolution`. `evaluated_at` is left `None` by the pure function and **stamped by the caller on persist** (§6.1). Built on pydantic with a local `extra='forbid'` `_Base`; imports the upstream payload types from `layer4.context`.

### 2.1 Explicitly deferred (no contract change when they land)

- **§5.2 / §5.3 feasibility detectors** (`injury_pool_empty` blocker; `schedule_volume_under_target` warning) — **Slice 2.** The §3 signature already accepts `layer1_payload` / `layer2c_payloads` / `plan_start_date` / `total_weeks` / `race_event_payload`; the §5 algorithm has the marked drop-in call sites (a commented block after aggregation). They append to the same `items` list — **no `Layer3DGate` / `GateItem` change.**
- **3C source** (`map_3c_items`) — deferred to #844; same drop-in shape.

## 3. The migration — `init_db.py`

Appended to the `_PG_MIGRATIONS` tail (after the unseen-notification index):

```sql
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS hitl_gate JSONB;
DO $$ BEGIN
  ALTER TABLE plan_versions DROP CONSTRAINT IF EXISTS plan_versions_generation_status_chk;
  ALTER TABLE plan_versions ADD CONSTRAINT plan_versions_generation_status_chk
      CHECK (generation_status IN ('generating', 'ready', 'failed', 'needs_review'));
END $$;
```

`hitl_gate` persists the whole `Layer3DGate` (items + resolutions + gate_status + evaluated_against) as one JSONB blob, read/written whole at v1 scale (§10). Drop-then-add on the CHECK is idempotent and a superset, so existing rows still satisfy it — same pattern as the layer4_cache `entry_point` + plan_sessions `session_index_in_day` realignments already in the list. Both additive and deploy-safe (a plan with no gate state reads NULL).

## 4. Tests / suite

- `tests/test_layer3d_gate.py` — **+23, all green** (`python -m pytest tests/test_layer3d_gate.py -q` → `23 passed`). Minimal valid upstream payloads built with the same fixture pattern as `tests/test_layer4_orchestrator.py`; HITL items injected per scenario.
- Coverage: **TS-3D-1** (clean → green), **TS-3D-2** (3B blocker → blocked, revise-only), **TS-3D-3** (2D block → blocker, `revise_target`→injuries), **TS-3D-4** (2E block → blocker), **TS-3D-8** (3B warning acknowledged with reasoning → green), **TS-3D-9** (blocker + warning → blocked, warning acknowledgeable), **TS-3D-10** (round-1 ack persists by `item_key` after round-2 revise clears the blocker → green), **TS-3D-11** (revise-that-doesn't-fix → pending, blocked), **TS-3D-12** (etl mismatch raises). Plus §4 preconditions (missing payload, plan_version_id 0), per-source mapping severities (2A prompt_required/unresolved error+warn; 2D warn; 2E non-block; 3B informational), §9 de-dup, `item_key` stability/scoping, acknowledge-on-blocker→pending, and the Rule #15 log.
- **No regressions** — `tests/test_routes_plan_create.py` + `tests/test_layer4_context.py` green (110 passed) after the migration edit.

**Env note for the next session:** the container ships without `pip install -r requirements.txt` applied. Run `pip install pydantic` (or the full requirements with `--ignore-installed blinker`) before pytest. Importing `layer3a.builder` *first* trips a pre-existing circular import (`test_layer3b_builder.py` collection error) — unrelated to this work; `layer4.context` (what `layer3d` imports) loads cleanly.

## 5. Commits (branch `claude/v5-design-layer-3-4-0t0ybc`)

1. `layer3d/` package (gate + __init__) + `tests/test_layer3d_gate.py` + `init_db.py` migration
2. bookkeeping (this handoff + `CURRENT_STATE.md` lead entry)

## 6. Next session — the rest of Slice 1, then 2 + 3

Per `specs/Layer3D_Spec.md` §11 + §14 gut check and the predecessor handoff §6.

### 6.1 Slice 1 remainder — ✅ DONE this session (see §1a)

All six items below shipped on this branch/PR: the `hitl_gate` repo accessor, the orchestrator hook (park at `needs_review`), the review screen (read + acknowledge), the plans-list "Needs review" badge, one-in-flight enforcement, and the `[Save as pending & exit]` (link to list, row stays `needs_review`) / `[Cancel]` (void via `delete_plan`) off-ramps. Live-verify is owed (§1a). **The next pickup is Slice 2.**

### 6.2 Slice 2 — feasibility detectors

`detect_injury_pool_empty` (blocker, §5.2 — `< 3` distinct usable strength exercises after 2D exclusions, or a discipline's only cardio modality banned) + `detect_schedule_volume_under_target` (warning, §5.3) at the marked call sites in `gate.py` §5 step 4 — uses `phase_structure_from_3b` (already in `layer4/phase_structure.py`). Plus the Layer 4 changes from the same design change-set: the **defensive raise** only + **delete** the two retired detector classes (`discipline_frequency_infeasible`, `skill_acquisition_infeasible`) per `specs/Layer4_Spec.md` §10.2.

### 6.3 Slice 3 — the revise cascade

Edit a Layer 1 field from the review screen → existing partial-update invalidation cascade re-runs affected layers → gate re-checks. Includes the staleness re-fire wiring (§11.2: re-evaluate on re-entry / upstream re-run / at `[Generate plan]` click, guarded by `evaluated_against`). The spec gut check names this the highest-risk, most-tested slice.

### 6.4 Operating notes — session-start read order
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — new lead entry (3D Slice 1 foundation) + Layer-3 rows
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — anchor sweep
6. Then read `specs/Layer3D_Spec.md` §10/§11 + `layer3d/gate.py` before wiring the orchestrator/UI.

## 7. Open items / decisions owed

- **None blocking the remainder of Slice 1.** The design resolved every v1 question. The one named (non-blocking) thin spot stays the same as the design handoff: what *wakes* a staleness re-evaluation when the athlete isn't on the screen — v1 leans on "re-check on next view / next click", with the generate-click guard as the backstop (§11.2). That's a Slice-3 concern.
- **`revise_target` strings** in the aggregation mappers (`profile.injuries` / `profile.disciplines` / `profile.nutrition`) are stable placeholders the review-UI slice will map to concrete edit surfaces; 3B's own `revise_target` is carried verbatim. Refine when the review screen lands.

## 8. Rule #9 verification table (input to next session's anchor sweep)

| Claim | File | Anchor string | Check |
|---|---|---|---|
| 3D gate module exists | `layer3d/gate.py` | `def evaluate_layer3d_gate(` | grep |
| Pure aggregation entry point | `layer3d/gate.py` | `items += map_2a_items(layer2a_payload)` | grep |
| All four source mappers present | `layer3d/gate.py` | `def map_2a_items` / `map_2d_items` / `map_2e_items` / `map_3b_items` | `grep -c 'def map_'` → 4 |
| item_key derivation §6.4 | `layer3d/gate.py` | `def make_item_key` + `[:16]` | grep |
| Gate-status rule §5 step 6 | `layer3d/gate.py` | `def compute_gate_status` | grep |
| Feasibility detectors deferred (no contract change) | `layer3d/gate.py` | `# 4. Feasibility detectors (§5.2/§5.3) — deferred` | grep |
| Package re-exports | `layer3d/__init__.py` | `from layer3d.gate import (` | grep |
| `hitl_gate` column migration | `init_db.py` | `ADD COLUMN IF NOT EXISTS hitl_gate JSONB` | grep |
| `needs_review` in status CHECK | `init_db.py` | `'generating', 'ready', 'failed', 'needs_review'` | grep |
| Tests green | `tests/test_layer3d_gate.py` | `def test_clean_athlete_is_green` | `pytest tests/test_layer3d_gate.py` → 23 passed |
| Orchestrator gate hook | `layer4/orchestrator.py` | `raise Layer3DGateBlocked(gate)` | grep |
| Advance loop parks at needs_review | `routes/plan_create.py` | `except Layer3DGateBlocked as exc:` | grep |
| Review screen route | `routes/plan_create.py` | `def plan_review(` + `def resolve_review_item(` + `def generate_from_review(` | grep |
| One-in-flight check | `routes/plan_create.py` | `generation_status IN ('generating', 'needs_review')` | grep |
| Plans-list needs_review bucket | `routes/plans.py` | `gen_needs_review` | grep |
| Repo gate accessors | `plan_sessions_repo.py` | `def save_hitl_gate` / `def load_hitl_gate` / `def load_prior_resolutions` | grep |
| Wiring tests green | `tests/test_layer3d_wiring.py` | `class TestReviewRoutes` | full suite → 3200 passed |
| CURRENT_STATE lead entry | `CURRENT_STATE.md` | `3D HITL GATE — SLICE 1 BUILT` | grep |

## 9. Issue reconcile

- **#213** — Slice 1 foundation (aggregation core + migration + tests) shipped on this branch; orchestrator/UI wiring is the next PR. Keep open `status:in-progress`.
- **#214** — unchanged (feasibility detectors land in Slice 2; the Layer 4 §10.2 re-scope is design-done).
- **#844** — unchanged (3C deferred).
