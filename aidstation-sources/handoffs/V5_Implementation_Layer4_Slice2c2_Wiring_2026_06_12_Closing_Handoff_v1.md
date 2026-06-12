# V5 Implementation — Layer 4 slice 2c.2: terrain-feasibility WIRING into plan-create (shipped)

**Date:** 2026-06-12
**Branch:** `claude/eloquent-gates-1jvhj7`
**PR:** [#556](https://github.com/ahorn885/exercise/pull/556) (squash-merged to `main`)
**Issue:** [#540](https://github.com/ahorn885/exercise/issues/540) (go-live blocker — sessions prescribed at locales lacking the required terrain)
**Predecessor:** [#553](https://github.com/ahorn885/exercise/pull/553) (the pure core) — handoff `V5_Implementation_Layer4_Slice2c2_TerrainFeasibility_2026_06_11_Closing_Handoff_v1.md` (§2 = ratified design, §4 = the wiring plan this session executed).

> **Continuing #540?** The cascade design is ratified (#553 handoff §2 — do not re-open it). This session executed the §4 wiring for the **create path**. **Next is slice 2c.2b (craft-capture integrity)** — Andy's call 2026-06-12. The refresh-path wiring is filed as **[#557](https://github.com/ahorn885/exercise/issues/557)** and is sequenced behind the refresh route going live (#208), not next.

---

## 1. What this session was

The pure terrain-feasibility cascade (`resolve_terrain_feasibility`, PR #553) was **imported by nothing** on `main`. This session wired it into plan-create, per the #553 handoff §4 plan, and shipped it. The §4.3 render is a Trigger #1 prompt change — the rendered text was reviewed with Andy against a representative cone before the push (he signed off; the strength-locale fix below was his one change request).

## 2. What shipped (PR #556, merged)

`terrain_feasibility: dict[str, TerrainResolution]` threads orchestrator → cached `plan_create` engine → per-phase synthesis prompt + cache key, **mirroring `training_substitution_payload` end-to-end**. Create-only (refresh = #557, §5).

- **`layer4/orchestrator.py`** — `_q_terrain_gap_rules(db)` reader (mirrors `_q_modality_groups`); `_build_terrain_feasibility(db, user_id, cone)` builds the per-discipline resolution map: reads the cluster terrain/equipment maps (`locations.cluster_*`), extracts each discipline's tier-1/2/3 strength pool from `cone.layer2c_payload.exercises_resolved` ranked by `priority_per_discipline` (Critical→Low via `_PRIORITY_RANK`), **excludes skill-gated disciplines** (`skill_gated_disciplines({primary_locale: l2c})`) so #336 and #540 partition rather than clobber, drops `None` (unconstrained). Passed into `llm_layer4_plan_create_cached(..., terrain_feasibility=...)`.
- **`layer4/hashing.py`** — `compute_terrain_feasibility_hash` (dataclass→`asdict`→`canonical_json`); folded into `plan_create_key` as a new trailing component (collapses to `''` when absent).
- **`layer4/cached_wrappers.py`** — `llm_layer4_plan_create_cached` accepts `terrain_feasibility`, hashes it into the key, forwards into the engine kwargs.
- **`layer4/plan_create.py`** — `llm_layer4_plan_create` + `_run_pattern_a_engine` accept + thread `terrain_feasibility` to both `synthesize_phase` call sites.
- **`layer4/per_phase.py`** — `synthesize_phase` + `render_user_prompt` accept it; `render_user_prompt` derives `exercise_names` from `layer2c_payloads` and renders a dedicated **`=== Session feasibility ===`** directive block (`_format_session_feasibility`) after the skill-gate block, plus a short inline tag on the session-grid count line (`_format_session_grid`) for the kind-changing tiers only.
- **`layer4/session_feasibility.py`** — pure render helpers `feasibility_line(resolution, *, discipline_name, exercise_names)` + `grid_annotation(resolution)`. **STRENGTH-tier fix (Andy):** the resolver now places the strength session at the first cluster locale (home-first) that carries equipment — the gym — falling back to `locale_order[0]` only when none lists equipment, instead of always naming home.
- **`tests/test_layer4_terrain_feasibility_wiring.py`** (NEW, 12) + 2 strength gym-locale tests in `test_layer4_session_feasibility.py`. Reader, pool extraction + ranking, skill-gated exclusion, per-tier render, cache-key fold, climbing-no-gym integration. **Full suite 2296 passed / 30 skipped; CI green** (Python + Layer 0 gate + JS + Vercel). **No DDL.**

## 3. Design decisions (ratified with Andy this session)

1. **Two-surface render**, not "one full line per allocation in the grid" (the #553 handoff §4.3 literal wording). A full sentence repeated per-week-per-block would bloat the prompt — so the full guidance lives in one `=== Session feasibility ===` block (rendered once), and only the tiers that change the session *kind* (strength) or drop it (reallocate) also get a short inline `[TERRAIN-INFEASIBLE: …]` tag on the authoritative count line. This is exactly #336's structure → the two compose. **Andy: ok.**
2. **Skill-gated disciplines are excluded from the terrain cascade** (the §4.3 compose-not-clobber concern). If the athlete isn't cleared for a skill, #336 already substitutes strength at the session level; running the terrain cascade on it too would emit a second, conflicting directive. Partitioned in `_build_terrain_feasibility`. **Andy: ok.**
3. **STRENGTH tier names the equipment-bearing locale.** Was `locale_order[0]` (home) regardless of where the gear is; now the first cluster locale with a non-empty equipment pool. **Andy: "fix strength now" → done.**

## 4. The rendered prompt (Trigger #1 — reviewed before ship)

Dedicated block (road@Home, trail@Cedar Trailhead, gear@Home Gym):
```
=== Session feasibility (deterministic — terrain routing, #540) ===
- Trail Running: real terrain available at "Cedar Trailhead" (TRN-004) — train it for real there.
- Mountain Biking: no required terrain in your locales — train as the nearest surface (TRN-001, fidelity 0.55) at "Home". Compose for that surface.
- Rock Climbing: no terrain, proxy, or machine in your locales — substitute a STRENGTH session targeting this discipline's demands at "Home Gym" from: Weighted Pull-up, Hangboard Repeaters, Hanging Leg Raise. Keep the target hours; compose as strength.
```
INDOOR + REALLOCATE (gym-only cluster):
```
- Road Running: no outdoor terrain in your locales — train indoors on the Treadmill at "Home Gym".
- Swimming: infeasible anywhere in your locale cluster — do NOT prescribe this session; reallocate its time to feasible disciplines.
```
Inline grid tag (kind-changing tiers only; composes with `[SKILL-GATED]`):
```
  - Rock Climbing (D-012): 2 session(s) × ~75 min, target 2.5 hours. [TERRAIN-INFEASIBLE: no terrain/machine in your locales — prescribe as a STRENGTH substitution, NOT a cardio session]
```

## 5. THE NEXT MOVE — slice 2c.2b (craft-capture integrity)

Andy's call (2026-06-12): **2c.2b is next**, ahead of the refresh-path wiring. 2c.2b is the prereq for the craft axis (own-the-bike). Per the #553 handoff §5 audit:
- `Layer1.discipline_baselines.cycling.bike_types_available` is **free-text `list[str]`** → make it a `Literal` enum + normalize casing (the `craft_discipline_aliases` lookup is case-sensitive and silently fails otherwise).
- The paddle/bike capture **forms aren't wired** (tables exist, nothing writes them); **no craft capture at all** for foot/snow/swim/climb.
- Extend `layer0.craft_discipline_aliases` to SUP / raft / TT-bike / snow crafts.
- This is a capture-integrity + Layer-1 slice (touches onboarding forms + Layer 1 reader + a small layer0 alias add). **A `craft_discipline_aliases` add fires Trigger #2 (data padding) and/or #3 (cross-layer) — surface the add before writing it.** Until 2c.2b lands, the craft axis (2c.2c) has ~no real data.

**Filed follow-ups against #540 (sub-issues / linked):**
- **[#557](https://github.com/ahorn885/exercise/issues/557) — refresh-path wiring.** Mirror this session's create wiring at `orchestrate_plan_refresh` → `llm_layer4_plan_refresh_cached` (fold into `plan_refresh_key`) → `plan_refresh_t1/t2/t3.py` renders. **Sequenced, not urgent:** the plan_refresh *engine* exists and is already wired for `training_substitution_payload`, but the refresh *route* is deferred ([#208](https://github.com/ahorn885/exercise/issues/208) — no async/resumable parity) and its re-run triggers gate nothing ([#305](https://github.com/ahorn885/exercise/issues/305)), so it isn't a live surface. ~4 files; all helpers already exist. Do it alongside/after #208.
- 2c.2c craft axis (`group → group_kind` ladder; road-bike-for-MTB) — build on 2c.2b.
- layer0 column lift of `_DISCIPLINE_REQUIRED_TERRAINS` + the indoor-machine map (Track-3-gated).

## 6. Owed (Andy's hands)

None for this PR (pure logic + wiring, no DDL, no migration). A cold-plan run to confirm the `=== Session feasibility ===` guidance + the inline tags appear in the synthesis prompt / diag JSON is a nice-to-have verification, not a blocker. (The #336 owed `layer0.skill_capability_toggles` Neon apply is still load-bearing for the skill gate — see CARRY_FORWARD; unrelated to this PR but adjacent.)

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` (the #540 section — updated) · 4. **this handoff** · 5. `./scripts/verify-handoff.sh`. **#540 create-path is now live (terrain feasibility wired into plan-create).** Next is **slice 2c.2b** (§5) — a capture-integrity slice; lead the `craft_discipline_aliases` add with a Trigger #2/#3 stop-and-ask. Do **not** start the #557 refresh wiring as "next" — it's sequenced behind #208.

## 7. Stop-and-asks this session
Trigger #1 (the §4.3 render): showed Andy the rendered `=== Session feasibility ===` block + inline tags against a representative cone before pushing; he approved the two-surface render + the skill-gated exclusion, and requested the strength-locale fix (§3.3), which shipped before merge.

## 8. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Orchestrator gather + reader | `layer4/orchestrator.py` | `def _q_terrain_gap_rules`, `def _build_terrain_feasibility`, `_PRIORITY_RANK`; `terrain_feasibility=terrain_feasibility` in `orchestrate_plan_create` |
| Cache-key fold | `layer4/hashing.py` | `def compute_terrain_feasibility_hash`; `terrain_feasibility_hash` param in `plan_create_key` |
| Threaded through engine | `layer4/cached_wrappers.py`, `layer4/plan_create.py` | `terrain_feasibility` kwarg on `llm_layer4_plan_create_cached` / `llm_layer4_plan_create` / `_run_pattern_a_engine` |
| Render (block + inline tag) | `layer4/per_phase.py` | `def _format_session_feasibility`; `grid_annotation(...)` call in `_format_session_grid`; `=== Session feasibility` header |
| Pure render + strength fix | `layer4/session_feasibility.py` | `def feasibility_line`, `def grid_annotation`; STRENGTH tier `next((loc for loc in locale_order if cluster_equipment_by_locale.get(loc)), ...)` |
| Tests green | `tests/test_layer4_terrain_feasibility_wiring.py` | 12 tests; `test_strength_routes_to_the_equipment_bearing_locale` in `test_layer4_session_feasibility.py`; full suite 2296 passed / 30 skipped |
| Refresh wiring filed | [#557](https://github.com/ahorn885/exercise/issues/557) | sub-issue of #540; refs #208/#305 |
| Merged | PR [#556](https://github.com/ahorn885/exercise/pull/556) | squash-merged to `main`; CI green |
