# Layer 4 Surface-Specific Routing Within a Discipline — Design Spec v1

**Status:** APPROVED-approach (Andy via `AskUserQuestion`, 2026-06-16 — chose "deterministic intent infra" over a prompt-only instruction or closing). Slice 1 built this session; Slice 2 (grid session-typing) documented as the follow-up.
**Date:** 2026-06-16
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

## 4. Slice 2 (follow-up) — grid session-typing (the per-slot binding)

Slice 1 makes the *surface per purpose* deterministic; the LLM still maps its session slots to purposes (bounded by the existing week easy/hard `IntensityMix` + the "one long-session anchor per discipline/week" prompt rule). For full end-to-end determinism, `session_grid` types each discipline's sessions into purpose slots (`DisciplineAllocation.session_types`: e.g. 1 long / N easy / M quality from the phase intensity split + LSD-anchor rule), and the per-purpose venue routing binds to those deterministic counts. That touches the grid contract (Layer 4) + `per_phase` rendering + tests — its own slice, kept out of Slice 1 to hold the 5-file ceiling. Filed as the #624 follow-up.

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

## 7. Gut check

- **Risk:** routing stays a synthesis *directive*, not a post-synthesis validator — the LLM can still ignore it. Slice 1 makes the surface↔purpose↔venue mapping deterministic (the part the LLM was editorializing); enforcing it would need a surface-aware validator rule, out of scope and probably overkill for a one-athlete product.
- **Best argument against:** PR #635's menu may already be enough grounding; Slice 1 adds the explicit purpose→venue binding so the synthesizer can't collapse to home — the gap the narrowed #624 names.
- **Missing:** craft disciplines (Slice 3) and the grid session-typing (Slice 2) are deferred; documented above.
