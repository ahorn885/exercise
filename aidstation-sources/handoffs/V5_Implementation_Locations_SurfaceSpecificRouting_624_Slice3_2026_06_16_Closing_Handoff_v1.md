# V5 Implementation — #624 Slice 3: craft-discipline surface routing (completes #624) — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/aidstation-surface-routing-ddhuyv`
**PR:** [#642](https://github.com/ahorn885/exercise/pull/642) — opened ready-for-review, auto-merge enabled, awaiting CI (Layer 0 integrity gate + Python unit suite + JS harness).
**Design:** `designs/Layer4_SurfaceSpecificRouting_624_Design_v3.md` (bumped from v2 — Slice 3 as-built; v2 archived under `archive/superseded-specs/`).
**Predecessor handoff:** `handoffs/V5_Implementation_Locations_SurfaceSpecificRouting_624_Slice2_2026_06_16_Closing_Handoff_v1.md` (#624 Slice 2, PR #641 merged).

Picked up straight from Slice 2 ("let's do slice 3 here"). Reset the working branch to the freshly-merged `origin/main` (the #641 squash diverged it), confirmed Slice 2 present, then built Slice 3 — the last #624 slice.

---

## 1. What shipped — Slice 3

### The finding that scoped it
Craft tier-1 resolutions (own the discipline's craft, ride a required terrain) carry `craft_tier == ""` + `tier == "exact"`, so they **already passed the Slice-1 routing gate** (`tier=="exact" and craft_tier==""`). But `enrich_resolution_display` built `surface_routes` / `terrain_venues` from `required_terrains(discipline_id)` **without** intersecting what the owned craft can actually ride. A multi-required-terrain craft discipline whose craft rides only a subset was therefore routed to a surface its craft can't traverse — a latent Slice-1 over-reach.

**Confirmed by repro:** D-008 MTB (requires TRN-002 Groomed / TRN-003 Technical / TRN-015 Pump Track), owned `mountain_bike` rides {TRN-002, TRN-003} only → Slice-1 routing emitted `hill / vert work → Pump Track @ Faraway (80 km)` even though the bike can't ride a pump track.

### The build (3 substantive code files + design + tests)
- **`layer4/session_feasibility.py`** — `enrich_resolution_display` gains an optional `craft_terrain: dict[str, set[str]] | None = None` param. The candidate surface set is now `required_terrains(discipline_id)` **intersected with `craft_terrain[resolution.owned_craft]`** when both are present (non-craft callers — `owned_craft is None` or `craft_terrain is None` — are byte-identical to before). The EXACT routing/menu gate widens from `craft_tier == ""` to `craft_tier in ("", "proxy")` so **tier 1** (own craft on required terrain) and **tier 3** (proxy craft on required terrain) both get the per-purpose routing, constrained to the resolved craft's rideable terrains. The **SWAP** tier (tier 4 — the sport itself changes to the proxy's discipline) is left untouched (routing the original discipline's purposes would be wrong). Field-comments on `terrain_venues`/`surface_routes` updated.
- **`layer4/orchestrator.py`** — `_resolve_included_feasibility` passes `craft_terrain=fi.craft_terrain` (already loaded for the cascade) into the `enrich_resolution_display` call.
- **`layer4/hashing.py`** — `LAYER4_PROMPT_REVISION` `"6"`→`"7"` (craft synthesis output changes → cached craft plans cold re-synth).
- **`tests/test_layer4_session_feasibility.py`** — new `TestCraftSurfaceRouting` (4 tests): own-craft routing excludes the unrideable surface; proxy tier gets constrained routing; swap tier gets no routing/menu; non-craft byte-identical with/without `craft_terrain`.

**No DDL, no prompt-body wording change** — the Slice-1 routing directive (`feasibility_line` EXACT branch) renders for craft EXACT too. Only applicability broadened + a correctness constraint added.

**Verification:** `tests/` **2496 passed / 30 skipped** (was 2492; +4 new); `etl/tests/` **89 passed**. Python-only → Layer-0 gate + JS harness unaffected.

## 2. #624 is now COMPLETE
All three slices shipped: Slice 1 (surface-per-purpose deterministic, PR #639) → Slice 2 (grid session-typing binds the per-slot counts, PR #641) → Slice 3 (craft disciplines, this PR). **#624 should be CLOSED (completed)** once #642 merges.

## 3. STILL OWED
- ⬜ **post-#572 live T3 *refresh* re-verify** (Rule #14) — needs a live refresh on a real plan + the diag token. Unrelated to this arc.

## 4. NEXT STEPS — the "Locations & Gear" arc continues
- **[#623](https://github.com/ahorn885/exercise/issues/623)** — retire assumed basic gear (Trigger #2; `0007` is the template; audit the 2C cascade first).
- **[#619](https://github.com/ahorn885/exercise/issues/619)** — profile Locations tab + nav IA. Pure UI/IA.

## 5. Bookkeeping done this session
- **`CURRENT_STATE.md`:** new top "Last shipped session" entry (Slice 3); Slice 2 demoted to predecessor; design refs repointed to v3.
- **Design:** `Layer4_SurfaceSpecificRouting_624_Design_v3.md` (Slice 3 as-built; status, §4b, §6, §7 updated); v2 archived under `archive/superseded-specs/`.
- **GitHub:** PR #642 opened (ready for review) + auto-merge; #624 to be commented + CLOSED completed on merge.
- **`CARRY_FORWARD.md`:** no edit.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Craft constraint | `layer4/session_feasibility.py` | `enrich_resolution_display(... craft_terrain=...)`; `craft_tier in ("", "proxy")`; `cand_terrains = ... & craft_terrain.get(resolution.owned_craft, set())` |
| Orchestrator wiring | `layer4/orchestrator.py` | `craft_terrain=fi.craft_terrain` in the `_resolve_included_feasibility` enrich call |
| Prompt revision | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "7"` |
| Unit tests | `tests/test_layer4_session_feasibility.py` | `class TestCraftSurfaceRouting`; `test_own_craft_routing_excludes_unrideable_surface`; `test_proxy_craft_tier_gets_constrained_routing`; `test_swap_tier_gets_no_routing`; `test_noncraft_unchanged_when_craft_terrain_supplied` |
| Design | `designs/Layer4_SurfaceSpecificRouting_624_Design_v3.md` | All 3 slices BUILT; §4b Slice 3 as-built; v2 archived |
| Suite | — | tests/ 2496 passed / 30 skipped; etl/tests 89 |
| Gate | — | NO DDL (Python-only); Layer-0 gate + JS harness unaffected |
| Issue | #624 | COMPLETE across all 3 slices → CLOSE on merge |
| Owed | — | post-#572 live T3-refresh re-verify carried (Rule #14) |
