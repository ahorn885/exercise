# V5 Implementation — Layer 4 slice 2c.2: deterministic terrain-feasibility cascade (core landed; wiring owed)

**Date:** 2026-06-11
**Branch:** `claude/relaxed-newton-556i1f`
**PR:** [#553](https://github.com/ahorn885/exercise/pull/553) (squash-merged to `main`)
**Issue:** [#540](https://github.com/ahorn885/exercise/issues/540) (go-live blocker — sessions prescribed at locales lacking the required terrain)

> **READ THIS FIRST IF YOU ARE CONTINUING #540.** This was a long design session that fully ratified a design with Andy, then landed the verified pure core. The remaining work is **mechanical wiring + one Trigger #1 prompt render** — §4 has the exact integration plan. Do **not** re-derive the design; it's all in §2. The next move is §4.1.

---

## 1. What this session was

The pv=65 review filed #540: plan-gen scheduled a Rock Climbing session at a home with no climbing terrain. Original framing was "slice 2c.2 = route cardio sessions to a terrain-matching locale + flag." Through a long stop-and-ask dialogue, Andy **reframed it substantially** (all decisions ratified — §2):

- **No flagging.** "We make a session that works, not propose sessions that don't work."
- **Deterministic, before the LLM.** Resolve feasibility deterministically *up front* so the synthesizer is handed a feasible instruction — not a post-hoc validator that fails.
- **Whole cluster, not just home.** Route across home + nearby saved locales.
- **Two axes:** terrain (have the terrain?) **and** craft (own the bike?). This slice ships the **terrain axis**; craft is sequenced after a craft-capture-integrity fix (§5).

Load-bearing findings that de-risked it: the terrain vocab adds the prior handoff thought were owed are **already in genesis** (v1.6.7, 19 rows; TRN-007 renamed, TRN-018 off-trail added); the "next-best terrain" + "strength-from-the-discipline's-muscles" + "road-bike-for-MTB" mechanisms **already exist in data** (`terrain_gap_rules`, `sport_exercise_map` via Layer 2C `ResolvedExercise.discipline_ids`, `modality_groups.group_kind`). So the whole cascade reuses existing layer0 data — **no padding, no Neon migration.**

## 2. The ratified design (do not re-derive)

**Per discipline the session grid wants, resolve deterministically (pre-synthesis):**

1. **EXACT** — a cluster locale carries one of the discipline's required terrains → schedule there.
2. **PROXY** — next-best terrain (`terrain_gap_rules` proxy @ fidelity ≥ 0.25) in the cluster → schedule there (e.g. MTB with no off-road → **road ride**).
3. **INDOOR** — the discipline's cardio machine (treadmill / stair climber / erg / trainer) is in a cluster locale's equipment pool → indoor session.
4. **STRENGTH** — substitute a strength session from the discipline's **own mapped exercises** (`ResolvedExercise.discipline_ids`, equip-feasible), targeting its muscles. *The climbing-no-gym fix.*
5. **REALLOCATE** — only when nothing works anywhere.

**Maps (Python constants in `layer4/session_feasibility.py`; layer0-column lift is Track-3-gated, filed as follow-up):**
- `_DISCIPLINE_REQUIRED_TERRAINS` — 22 disciplines; **D-018 Mountaineering = TRN-005/007/012** (Andy's call); D-027 OCR + unknowns = no requirement (unconstrained → resolver returns None).
- `_DISCIPLINE_INDOOR_MACHINES` — all machine tags verified present in `layer0.equipment_items` (Treadmill, Stair climber, Ski erg, Paddle ergometer, Rowing ergometer, Cycling trainer/Stationary/Spin/Assault bike). On-foot→treadmill (+stair climber for vertical); paddling→paddle/rowing erg; skiing→ski erg; cycling→trainer set. Climbing/Swimming have no machine (climbing→strength; swimming→Pool terrain).

**Craft axis (DEFERRED — §5):** terrain present ≠ craft owned (Andy's MTB-but-only-a-road-bike case). Craft substitution ladder: own same modality **group** → use it; own same **group_kind** (`bike`) → swap to that owned craft's discipline (road-bike-for-MTB is `bike_offroad`→`bike_pavement`, both `group_kind='bike'`), re-run terrain axis; else strength terminal. Deferred because **craft ownership is barely captured today** (see §5).

## 3. What shipped (PR #553, merged)

Verified, pure, load-bearing core + plumbing (no engine wiring yet — the new module is imported by nothing on `main`):

- **`layer4/session_feasibility.py`** (NEW) — the two maps + `resolve_terrain_feasibility(...)` (pure, DB-free) returning a `TerrainResolution{tier, locale_id, terrain_id, proxy_fidelity, machine, substitute_exercise_ids, note}` or `None` (unconstrained). Public helpers `required_terrains` / `indoor_machines`.
- **`locations.py`** — `cluster_terrain_by_locale(db, user_id, cluster)` + `cluster_equipment_by_locale(...)`: the per-locale terrain analogue to `cluster_effective_tags`, **keyed by locale** (routing needs to know *which* locale has the terrain/machine) + `_coerce_terrain_ids` (PG-list / SQLite-JSON / NULL tolerant).
- **`tests/test_layer4_session_feasibility.py`** — 19 tests: every cascade tier, cluster-vs-home, D-018 three-terrain match, MTB→road proxy, climbing-no-gym→strength, cascade ordering. **Green.** Existing `test_locations.py` (9) unaffected. **Full CI green** (Python suite + Layer 0 gate + JS + Vercel).

## 4. THE NEXT MOVE — remaining wiring (mechanically-applicable)

The resolver exists but **nothing calls it.** Thread it from the orchestrator through the cached `plan_create` synthesis engine into the prompt, **mirroring `training_substitution_payload` exactly** (it's the template — same threading shape end to end). This is ~5 files → it exceeds the 5-file ceiling, which is why it was checkpointed; it's a clean second PR.

### 4.1 Orchestrator — build the resolution map + a gap-rules reader
In `layer4/orchestrator.py`, `orchestrate_plan_create` (the `layer2c_payloads = {cone.primary_locale: cone.layer2c_payload}` line, ~`959`), before `llm_layer4_plan_create_cached(...)`:
- `cluster = locations.cluster_locale_ids(db, user_id)` (home first = `locale_order`).
- `terrain_by_locale = locations.cluster_terrain_by_locale(db, user_id, cluster)`; `equip_by_locale = locations.cluster_equipment_by_locale(db, user_id, cluster)`.
- **NEW reader** `_q_terrain_gap_rules(db) -> dict[str, list[tuple[str, float]]]` (mirror `_q_modality_groups`/`_q_craft_discipline_aliases`, ~line 250-280): `SELECT target_terrain_id, proxy_terrain_id, proxy_fidelity FROM layer0.terrain_gap_rules WHERE proxy_terrain_id IS NOT NULL AND superseded_at IS NULL` → group by target.
- `discipline_exercise_ids` per discipline from `cone.layer2c_payload.exercises_resolved`: `[ex.exercise_id for ex in resolved if D in ex.discipline_ids and ex.tier in (1,2,3)]`, ranked by `ex.priority_per_discipline.get(D)` (Critical>High>Medium>Low).
- For each **included** discipline (the cone's `included_disciplines`, ~line 495), call `resolve_terrain_feasibility(...)`; drop None. Build `terrain_feasibility: dict[str, TerrainResolution]`.
- Pass `terrain_feasibility=terrain_feasibility` into `llm_layer4_plan_create_cached`.

### 4.2 Thread through the cached engine (mirror `training_substitution_payload`)
- `layer4/cached_wrappers.py` — `llm_layer4_plan_create_cached`: accept `terrain_feasibility`, **fold into the cache key** (it changes the prompt → must invalidate; mirror how `training_substitution_payload` enters the key), forward to `llm_layer4_plan_create`.
- `layer4/plan_create.py` — `llm_layer4_plan_create` + `_run_pattern_a_engine`: accept + pass to each `synthesize_phase(...)` call (mirror `training_substitution_payload`).
- `layer4/per_phase.py` — add `terrain_feasibility` kwarg to `synthesize_phase` (~`1658`) → `render_user_prompt` (~`1092`) → `_format_session_grid` (~`761`).

### 4.3 Render the guidance — **TRIGGER #1 (show Andy the rendered text before shipping)**
In `_format_session_grid`, append a line per `DisciplineAllocation` from `terrain_feasibility[a.discipline_id]` (skip if absent/None). Approved prompt shapes (Andy ratified the style + examples):
```
- mountain_biking: no off-road terrain in your locales — train as a ROAD ride
    (nearest surface, fidelity 0.55) at "Home". Compose as road cycling.
- rock_climbing: no climbing terrain at any locale — substitute a STRENGTH
    session targeting climbing demands (pull, grip, core) at "Home Gym" from:
    <exercise names>. Keep the target hours; compose as strength.
- trail_running: at "Cedar Trailhead" (TRN-003).
```
The resolution's `.note` + `.tier` carry everything needed. Resolve `locale_id`→display name and `substitute_exercise_ids`→names from the cone (the 2C resolved set / locale names).

> **Reuse #336 (merged 2026-06-11, PR #551).** The skill-capability gate already added a **`[SKILL-GATED]` session-grid annotation + a "substitute strength" directive** to `per_phase.py` at this exact render site, plus the `kind=='cardio'`-blocking validator rule `_rule_skill_capability_gate` + `skill_gated_disciplines()` in `layer4/validator.py`. The #540 STRENGTH tier is the same idea (substitute strength at the session level) — model the render + any validator backstop on #336's pattern rather than inventing a parallel one. Note the two can co-fire on the same discipline (skill-gated AND terrain-infeasible); make the annotations compose, not clobber.

### 4.4 Also wire `orchestrate_plan_refresh`
Same pattern at the refresh call site (~`873`, `llm_layer4_plan_refresh_cached` passes `cone.training_substitution_payload`) for consistency — or do create-only first and note refresh as the immediate follow-up.

### 4.5 Tests
Orchestrator-level: gap-rules reader; the per-discipline exercise-pool extraction; an integration test that a climbing-no-gym cone yields a `strength` resolution and the rendered prompt contains the substitute. Re-run full suite.

## 5. Sequenced follow-ups (filed against #540)

1. **Slice 2c.2b — craft-capture integrity** (prereq for the craft axis). Per the audit: `bike_types_available` is **free-text** `list[str]` (make it a `Literal` enum + normalize casing — alias lookup is case-sensitive and silently fails otherwise); the paddle/bike capture **forms aren't wired** (tables exist, nothing writes them); **no craft capture at all** for foot/snow/swim/climb. Extend `craft_discipline_aliases` to SUP/raft/TT-bike/snow crafts. Until this lands, the craft axis has ~no real data.
2. **Slice 2c.2c — craft axis** of the cascade (the `group → group_kind` ladder; road-bike-for-MTB). Build on 2c.2b.
3. **layer0 column lift** of `_DISCIPLINE_REQUIRED_TERRAINS` + indoor-machine maps (Track-3-gated; same reason the route keeps its own `RACE_INELIGIBLE_TERRAIN_IDS`).

## 6. Owed (Andy's hands)

None for the merged core (pure logic, no DDL). The wiring (§4) ships without a migration too. A cold-plan run to confirm the rendered guidance + resolutions appear in the diag JSON belongs to the §4 wiring PR, not this one.

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. **this handoff (§2 design + §4 next move)** · 5. `./scripts/verify-handoff.sh`. **#540 is mid-flight (tier 1 of the 4-tier order — go-live blocker).** Continue at **§4.1**; the design is fully ratified in §2 — don't re-open it. The §4.3 render is a Trigger #1 prompt change → show Andy the rendered text against a real cone before shipping.

## 7. Stop-and-asks this session
The whole session was stop-and-ask (Triggers #1 prompt, #3 cross-layer, #5 alternatives, #6 status). Ratified: no-flag/make-it-work; pre-synthesis deterministic resolution; cluster-wide; two-axis (terrain now, craft later); D-018=TRN-005/007/012; cycling/foot/paddle/ski indoor machines; terrain-axis-first sequencing. All recorded in §2.

## 8. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Pure terrain-feasibility cascade landed | `layer4/session_feasibility.py` | `def resolve_terrain_feasibility`; `_DISCIPLINE_REQUIRED_TERRAINS["D-018"]` == `{TRN-005,007,012}`; `class TerrainResolution` |
| Cluster terrain/equipment readers | `locations.py` | `def cluster_terrain_by_locale`, `def cluster_equipment_by_locale`, `def _coerce_terrain_ids` |
| Tests green | `tests/test_layer4_session_feasibility.py` | 19 tests; `pytest -q` → 19 passed; `test_locations.py` 9 passed |
| Indoor machines exist (no padding) | `etl/output/layer0_etl_v1.6.7.sql` | `equipment_items` has Treadmill / Stair climber / Ski erg / Paddle ergometer / Rowing ergometer / Cycling trainer |
| Strength-substitute data exists | `layer4/context.py` | `class ResolvedExercise` carries `discipline_ids` + `priority_per_discipline` (≈ line 419-425) |
| Next move = wiring | this handoff §4 | mirror `training_substitution_payload` threading (orchestrator→cached_wrappers→plan_create→per_phase) + Trigger #1 render |
| Merged | PR [#553](https://github.com/ahorn885/exercise/pull/553) | squash-merged to `main`; CI green |
