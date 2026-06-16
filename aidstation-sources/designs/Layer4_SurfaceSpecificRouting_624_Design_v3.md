# Layer 4 Surface-Specific Routing Within a Discipline — Design Spec v3

**Status:** APPROVED-approach (Andy via `AskUserQuestion`, 2026-06-16 — chose "deterministic intent infra" over a prompt-only instruction or closing). **All three slices BUILT** (Slice 1 PR #639; Slice 2 PR #641; Slice 3 this session). Slice 2 binding depth: "count-deterministic, LLM picks vert/technical." Slice 3 extends the routing to craft disciplines, constrained to the resolved craft's rideable terrains. **#624 fully shipped — ready to close.**
**Date:** 2026-06-16 (v3: Slice 3 built)
**Issue:** [#624](https://github.com/ahorn885/exercise/issues/624) (narrowed) — surface-specific routing within a discipline.
**Predecessor:** the deterministic venue pick (PR #635) — `terrain_venues` menu + bar-invention. This design is its next layer.
**Governing doc:** `designs/Layer4_DeterminismFirst_Synthesis_Design_v2.md` (the grid + feasibility cascade this extends).
**Trigger:** #3 (cross-layer feasibility contract) + #1 (synthesis-prompt wording → prompt-revision bump).

---

## 1. Purpose

A multi-surface discipline collapses its surface varieties. Trail Running (D-001) is feasible on *any* of Groomed Trail (TRN-002) / Technical Trail (TRN-003) / Hill-Rolling (TRN-004); the feasibility cascade resolves EXACT at the **nearest** locale carrying *any* required surface — for pv=71 that's home (hills, TRN-004, 0 km) — and hands the synthesizer one scheduling locale. The nearby groomed-trail venue (Cleburne State Park, TRN-002, 18 km) is exposed in the `terrain_venues` menu (PR #635) but the system does not **route each kind of session to the surface that trains it**: a long aerobic run should land on groomed/flat trail; hill repeats on the home hills.

**Goal:** make the surface-for-each-session-purpose decision **deterministic** — the system computes which surface serves which training purpose and which (nearest) venue carries it, rather than leaving the surface↔purpose judgment to the LLM.

## 2. Key decision — derive purpose from existing terrain attributes (no new vocab)

`layer0.terrain_types` already carries the columns that determine a surface's training purpose:

| col | meaning |
|---|---|
| `requires_elevation` | the surface delivers a climb/vert stimulus |
| `technical_surface` | the surface delivers a skill/technical stimulus |

So purpose is **derived**, not authored — **no new layer0 table, no Trigger-#2 vocab sign-off.** The classifier (pure):

```
requires_elevation        → "hill / vert work"          (TRN-004 Hill, TRN-005 Mtn/Alpine, TRN-006 Fell, TRN-012 Snow)
technical & not elevation  → "technical / skill work"    (TRN-003 Technical Trail, TRN-007 Technical Rock, TRN-011 Whitewater, TRN-015 Pump Track, TRN-013/014 climbing)
else (flat, non-technical) → "easy / long aerobic"       (TRN-001 Road, TRN-002 Groomed, TRN-020 Gravel, TRN-009 Flat Water, TRN-008 Pool)
```

A surface that is both elevation AND technical (Mountain/Alpine, Fell) routes to **vert** — the elevation stimulus dominates the session's purpose. (Considered: author a bespoke terrain→purpose table; rejected — it duplicates information the attrs already encode, and adding a vocab table would itself trip Trigger #2 for no benefit. The attrs are read live, `WHERE superseded_at IS NULL`, mirroring `_q_terrain_names`.)

## 3. Slice 1 (this session) — deterministic surface-purpose venue routing in the feasibility resolution

Additive, backward-compatible contract change on the **non-craft** terrain cascade (`resolve_terrain_feasibility` → `enrich_resolution_display` → `feasibility_line`). Craft disciplines (bike/paddle) keep the existing cascade — a documented Slice-3 follow-up.

- **`TerrainResolution.surface_routes`** (new field, default `()`): for an EXACT non-craft resolution, the nearest carrying venue **per training purpose** present among the discipline's required surfaces in the cluster, as `(purpose_label, terrain_name, locale_name, distance_km)`, in coaching order (aerobic → vert → technical).
- **Built in `enrich_resolution_display`** from the same nearest-carrier rows it already computes for `terrain_venues`, plus a new `terrain_attrs` input (`{terrain_id: {requires_elevation, technical_surface}}`). Reuses the distance-sorted rows: the first carrier seen per purpose is that purpose's nearest venue.
- **Gated to "meaningful":** emitted only when **≥2 distinct purposes** map to **≥2 distinct locales**. A single-purpose discipline, or one whose surfaces all sit at one locale, falls back to the existing `terrain_venues` menu — **no behavior change** for those.
- **Rendered in `feasibility_line` (EXACT branch):** a routing directive — *"real terrain in your saved locales, routed by session purpose — easy / long aerobic on "Cleburne State Park" (18 km away) (Groomed Trail); hill / vert work on "509 Williams Avenue" (home) (Hill / Rolling); … . Match each session to the surface its purpose calls for; do not collapse every session onto the nearest one. Train at these named locales only; never name or suggest a location not in this list."* When `surface_routes` is empty the existing menu/single-venue rendering is unchanged.
- **Orchestrator:** new `_q_terrain_attributes(db)` reader (mirrors `_q_terrain_names`); threaded through `_FeasibilityInputs.terrain_attrs` into the `enrich_resolution_display` call.
- **Cache:** `hashing.LAYER4_PROMPT_REVISION` `4`→`5` — the synthesis directive wording changes, so cached plans cold re-synthesize (Trigger #1, approach ratified).

### pv=71 worked example
Required {TRN-002, TRN-003, TRN-004}; cluster home={TRN-001,TRN-004}, Cleburne(18 km)={TRN-002,TRN-003,TRN-004}.
- aerobic → Groomed Trail @ Cleburne (18 km) — home carries no flat trail
- vert → Hill / Rolling @ 509 Williams (home)
- technical → Technical Trail @ Cleburne (18 km)

3 purposes across 2 locales → meaningful. The long run lands on Cleburne groomed trail; hill work at home. Defect fixed deterministically.

## 4. Slice 2 (BUILT this session) — grid session-typing (the per-slot binding)

Slice 1 made the *surface per purpose* deterministic; the LLM still mapped its session slots to purposes (bounded only by the week easy/hard `IntensityMix` + the LSD-anchor prompt rule). Slice 2 types each cardio discipline's sessions into purpose slots so the surface routing binds to deterministic per-slot counts.

**Binding depth (Andy ratified via `AskUserQuestion`):** *count-deterministic* — the per-discipline long/easy/quality **counts** are fixed deterministically; the LLM still picks which `surface_route` (vert vs technical) each quality session uses. Rejected: a fully-deterministic vert-vs-technical split (fabricates a coaching rule with no basis when both surfaces are present) and a prompt-only no-op (leaves the per-purpose counts non-deterministic — the gap Slice 2 exists to close).

**The build:**
- **`session_grid.SessionTypeSplit`** (new frozen model: `long` / `easy` / `quality` + `total`) + **`DisciplineAllocation.session_types`** (`SessionTypeSplit | None`, default `None` — set only on cardio allocations with ≥1 session; strength + zero-session rows stay `None`).
- **`session_grid._type_sessions(allocations, phase_name, intensity)`**, run inside `build_session_grid` right after `_intensity_mix`. The week `intensity.hard_count` is the authority on quality count; it's distributed across cardio disciplines proportional to their session counts (largest-remainder, capped per discipline) so **`sum(quality) == hard_count` exactly**. Each discipline's remaining (aerobic) sessions are `easy`, except the **primary** (highest-load-weight) discipline carves one `long` LSD cornerstone in every phase but **Taper** (`aerobic >= 1` guard). Consequently **`sum(long + easy) == easy_count`** — the per-discipline typing and the week-level polarized mix are consistent by construction.
- **`per_phase._format_session_grid`** renders the per-discipline typing line (`Session types (deterministic): 1× long (LSD, aerobic) + 5× easy (aerobic) + 1× quality (vert/technical).`); the week-level mix line is reworded to "aggregate cross-check." The Rule #15 `build_session_grid` log line gains the per-discipline `(L#/E#/Q#)` typing so the decision is attributable in prod.
- **Prompt body (Trigger #1):** the `=== Session grid ===` guidance now lists per-discipline typing as authoritative and directs **long + easy → the aerobic surface; quality → the vert/technical surface** (from the feasibility surface routing), matching each quality session's intent to its surface; the race-sim long day counts as one quality session.
- **Cache:** `hashing.LAYER4_PROMPT_REVISION` `5`→`6`.

Contained to `session_grid.py` + `per_phase.py` + `hashing.py` + tests (the T2/T3 refresh prompts already carry the LSD-anchor rule as prose and don't call `build_session_grid`, so they're untouched). The validator's `intensity_dist` rule is zone-hours-based and orthogonal.

## 4b. Slice 3 (BUILT this session) — craft-discipline surface routing

**Finding that scoped it:** craft tier-1 resolutions (own the discipline's craft on a required terrain) carry `craft_tier == ""` + `tier == "exact"`, so they *already* passed the Slice-1 routing gate — but `enrich_resolution_display` built `surface_routes`/`terrain_venues` from `required_terrains(discipline_id)` **without** intersecting what the owned craft can actually ride. A multi-required-terrain craft discipline whose craft rides only a subset (e.g. an MTB that can't ride a pump track) was therefore routed to a surface its craft can't traverse — a latent Slice-1 over-reach. Slice 3 both **fixes** that and **extends** routing to the proxy tier.

**The build:**
- **`session_feasibility.enrich_resolution_display`** gains an optional `craft_terrain: dict[str, set[str]] | None = None` param. The candidate surface set is now `required_terrains(discipline_id)`, intersected with `craft_terrain[resolution.owned_craft]` when both are present. Non-craft callers (`owned_craft is None` or `craft_terrain is None`) are byte-identical to before.
- The EXACT routing/menu gate widens from `craft_tier == ""` to `craft_tier in ("", "proxy")` — so **tier 1** (own craft on required terrain) and **tier 3** (proxy craft on required terrain) both get the per-purpose routing, constrained to the resolved craft's rideable terrains. The **SWAP** tier (tier 4 — the sport itself changes to the proxy's discipline) is deliberately left untouched: routing the *original* discipline's purposes would be wrong.
- **`orchestrator._resolve_included_feasibility`** passes `craft_terrain=fi.craft_terrain` into the enrich call (already loaded for the cascade).
- **Cache:** `hashing.LAYER4_PROMPT_REVISION` `6`→`7`.

No DDL, no prompt-body wording change (the Slice-1 routing directive renders for craft EXACT too); the synthesis output for craft disciplines changes → cached craft plans cold re-synth. Contained to `session_feasibility.py` + `orchestrator.py` + `hashing.py` + tests.

**#624 fully shipped across all three slices — ready to CLOSE.**

## 5. Edge cases

- **terrain_attrs empty / table unreachable** → `surface_routes` stays `()`, renders the existing menu (degrades, never crashes) — mirrors `_q_terrain_names`.
- **All required surfaces at one locale** → not meaningful; existing single/menu rendering.
- **Craft disciplines** → `enrich` only builds routes for `tier=="exact" and craft_tier==""`; craft EXACT is untouched (Slice 3).
- **Event-window segments** reuse the same `enrich_resolution_display`, so routing applies in reduced/away environments for free.

## 6. Test scenarios

1. pv=71 EXACT with attrs → `surface_routes` = aerobic@Cleburne / vert@home / technical@Cleburne; line renders the routing directive; no slug/TRN leak.
2. Single-purpose discipline (e.g. Road Running, TRN-001 only) → `surface_routes == ()`, menu rendering unchanged.
3. All surfaces at one locale → `surface_routes == ()`.
4. `terrain_attrs=None` (bare caller) → backward-compatible, existing menu test still green.
5. `surface_purpose` classifier unit table (elevation > technical > aerobic precedence).

**Slice 2 (`tests/test_layer4_session_grid.py::TestSessionTypes`):**
6. `sum(quality) == week hard_count` and each discipline's `session_types.total == sessions_this_week`.
7. Primary discipline carves exactly one `long`; secondaries carry none.
8. Taper drops the long anchor.
9. Strength is not typed (`session_types is None`).
10. `quality <= sessions_this_week` and `easy >= 0` across all phases (no negative carve).

**Slice 3 (`tests/test_layer4_session_feasibility.py::TestCraftSurfaceRouting`):**
11. Own-craft (tier 1) routing **excludes** a required surface the craft can't ride (MTB → Pump Track dropped from routes + menu).
12. Proxy-craft (tier 3) now gets the per-purpose routing, constrained the same way.
13. SWAP tier (tier 4) gets no routing/menu (sport changes).
14. A non-craft resolution (`owned_craft is None`) is byte-identical whether or not `craft_terrain` is supplied.

## 7. Gut check

- **Risk:** routing + typing stay a synthesis *directive*, not a post-synthesis validator — the LLM can still ignore them. Slice 1+2 make the surface↔purpose↔venue mapping AND the per-purpose counts deterministic (the parts the LLM was editorializing); enforcing them would need a surface-aware validator rule, out of scope and probably overkill for a one-athlete product. The existing `intensity_dist` validator still backstops the polarized split at the zone-hours level.
- **Best argument against (Slice 2):** the per-discipline typing constrains the synthesizer more tightly; if the deterministic long/easy/quality counts are ever wrong for a phase, the LLM now has less room to correct them (it's told "do not deviate"). Mitigation: the counts derive from the same phase-science split (`_PHASE_INTENSITY_SPLIT`) + LSD rule the system already trusts for the week-level mix — Slice 2 only distributes that existing total per-discipline, it doesn't invent a new periodization model. The `phase_synthesis_notes` escape hatch ("if the grid is genuinely wrong, call it out") remains.
- **Best argument against (Slice 3):** craft tier-1 was already routing (unconstrained) since Slice 1, so most of Slice 3 is a correctness fix rather than new capability — one could argue it should have been a Slice-1 follow-up patch. Counter: the constraint needs the `craft_terrain` map threaded into `enrich`, and extending to the proxy tier is genuinely new — a coherent slice, not a one-liner.
- **Missing:** the vert-vs-technical choice per quality session is intentionally left to the LLM (the ratified Slice-2 binding depth). #624 is now complete across all three slices.
