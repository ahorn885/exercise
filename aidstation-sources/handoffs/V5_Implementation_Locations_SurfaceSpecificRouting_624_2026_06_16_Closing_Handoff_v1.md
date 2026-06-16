# V5 Implementation — Deterministic surface-specific routing within a discipline (#624) — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/v5-implementation-locations-vgk6fi`
**PR:** [#639](https://github.com/ahorn885/exercise/pull/639) — auto-merge enabled, awaiting CI (Layer 0 integrity gate + Python unit suite + JS harness).
**Design:** `designs/Layer4_SurfaceSpecificRouting_624_Design_v1.md`
**Predecessor handoff:** `handoffs/V5_Implementation_Locations_CraftsOutOfEquipment_2026_06_16_Closing_Handoff_v1.md` (#622, the prior "Locations & Gear" slice).

Picked up from the #622 closing handoff ("check it out and work"). Rule #9 sweep clean (all #622 anchors landed, tree even with `origin/main`). Led the **surface-specific-routing slice** of the "Locations & Gear" arc.

---

## 1. What shipped

### The decision (Andy ratified via `AskUserQuestion`)

Two questions: **(1) which arc slice** → Andy chose **#624 surface routing** (over #619 Locations-tab/nav-IA or #623 retire-assumed-gear). **(2) approach for #624** → Andy chose **"deterministic intent infra"** (Option C) over a prompt-only instruction (A) or closing as already-handled-by-#635.

### The gap (narrowed #624, Trigger #3 + Trigger #1)

Post-#635 (the deterministic venue pick), a multi-surface discipline still **collapses its surfaces**. Trail Running (D-001) is feasible on any of TRN-002 Groomed / TRN-003 Technical / TRN-004 Hill-Rolling; `resolve_terrain_feasibility` resolves EXACT at the **nearest** locale carrying *any* required surface (home hills, 0 km, for pv=71) and hands the synthesizer one scheduling locale. The nearby groomed-trail venue (Cleburne SP, TRN-002, 18 km) is exposed in the `terrain_venues` menu, but nothing **routes each kind of session to the surface that trains it** (long aerobic → flat/groomed; hill work → hills).

**Architectural truth found by reading the grid** (`session_grid.py`): per-session intent does NOT exist deterministically — the grid carries per-discipline counts + a week-level easy/hard `IntensityMix` only; actual session purpose is assigned by the LLM. So full end-to-end determinism needs a grid session-typing step (Slice 2, deferred). Slice 1 makes the **surface-per-purpose-per-venue** mapping deterministic — the part the LLM was editorializing.

### Key decision — derive purpose from existing terrain columns (NO new vocab, NO DDL)

`layer0.terrain_types` already carries `requires_elevation` + `technical_surface`. Purpose is **derived**, not authored:
- `requires_elevation` → **hill / vert work** (TRN-004/005/006/012)
- `technical & not elevation` → **technical / skill work** (TRN-003/007/011/013/014/015)
- else (flat, non-technical) → **easy / long aerobic** (TRN-001/002/020/008/009)
- elevation+technical (Mtn/Alpine, Fell) → **vert** (elevation dominates)

Rejected authoring a bespoke terrain→purpose table — it duplicates the attrs and would itself trip Trigger #2.

### Slice 1 — the build (3 substantive code files + design + tests)

- **`layer4/session_feasibility.py`** — `surface_purpose(requires_elevation, technical_surface)` pure classifier + `SURFACE_AEROBIC`/`SURFACE_VERT`/`SURFACE_TECHNICAL` constants + `_SURFACE_PURPOSE_ORDER`. New `TerrainResolution.surface_routes` field: `(purpose_label, terrain_name, locale_name, distance_km)` per purpose, nearest venue. Built in `enrich_resolution_display` (new optional `terrain_attrs` param) from the **same nearest-carrier rows** it already computes for `terrain_venues` — gated to **≥2 distinct purposes across ≥2 distinct locales**. EXACT `feasibility_line` renders the routing directive when `surface_routes` is set, else falls back to the existing menu/single rendering.
- **`layer4/orchestrator.py`** — `_q_terrain_attributes(db)` reader (mirrors `_q_terrain_names`, `WHERE superseded_at IS NULL`) → `_FeasibilityInputs.terrain_attrs` → passed into the `enrich_resolution_display` call in `_resolve_included_feasibility`.
- **`layer4/hashing.py`** — `LAYER4_PROMPT_REVISION` `"4"`→`"5"` (synthesis wording changed → cached plans cold re-synth).
- **`tests/test_layer4_session_feasibility.py`** — pv=71 routing (aerobic@Cleburne / vert@home / technical@Cleburne) + line render; no-attrs backward-compat (falls back to menu); all-surfaces-one-locale → no routing; `surface_purpose` classifier table.
- **`tests/test_layer4_event_windows.py`** — added `terrain_attrs={}` to the `_FeasibilityInputs` test constructor.

**pv=71 result:** easy/long aerobic → Groomed Trail at "Cleburne State Park" (18 km); hill/vert → Hill / Rolling at "509 Williams Avenue" (home); technical → Technical Trail at Cleburne. Long run lands on groomed trail, hill work at home — deterministically.

**Verification:** `tests/` **2487 passed / 30 skipped** (4 new + 1 modified, was 2483); `etl/tests/` 89 passed. **NO DDL** (reads existing columns) → Layer-0 gate unaffected; Python-only → JS harness unaffected. Vercel preview deploy green.

## 2. Deferred (documented in the design doc §4)

- **Slice 2 — grid session-typing.** `DisciplineAllocation.session_types` (e.g. 1 long / N easy / M quality from the phase intensity split + the "one long-session anchor per discipline/week" prompt rule) so the per-purpose routing binds to deterministic per-slot counts. Touches the grid contract (Layer 4) + `per_phase` rendering + tests — its own slice (kept out of Slice 1 to hold the 5-file ceiling).
- **Slice 3 — craft disciplines.** Bike/paddle keep the existing `resolve_craft_terrain_feasibility` cascade for now; surface-purpose routing there is a follow-up (the craft tier composes craft ownership with terrain, more involved).

## 3. STILL OWED

- ✅ **`layer0-apply` for `0007`** (carried from #622) — **APPLIED to prod Neon (Andy's one-tap, 2026-06-16 02:42 UTC; [`layer0-apply` run #2](https://github.com/ahorn885/exercise/actions/runs/27589849174) → success).** Log confirms real work, not a no-op: `0007` superseded 9 equipment vessels, added 3 craft aliases + 7 craft_terrain rows, de-drifted 27 exercises (`NOTICE: 0007: OK`); `0006` re-ran as a clean idempotent no-op first. The vessels are out of the equipment picker live. (Also re-verified via read-only `neon-query` in the Slice-2 session.)
- ⬜ **post-#572 live T3 *refresh* re-verify** (Rule #14) — needs a live refresh on a real plan + the diag token. Unrelated to this session. (Now the only outstanding owed item.)

## 4. NEXT STEPS — the "Locations & Gear" arc continues

- **#624 Slice 2** (grid session-typing) + **Slice 3** (craft disciplines) — the deferred follow-ups above; #624 stays OPEN, narrowed.
- **[#623](https://github.com/ahorn885/exercise/issues/623)** — retire assumed basic gear (Trigger #2; `0007` is the template; audit the 2C cascade first).
- **[#619](https://github.com/ahorn885/exercise/issues/619)** — profile Locations tab + nav IA. Pure UI/IA.

## 5. Bookkeeping done this session

- **`CURRENT_STATE.md`:** new top "Last shipped session" entry; #622 demoted to predecessor.
- **GitHub:** PR #639 opened (ready for review) + auto-merge enabled; #624 commented with the Slice-1 shipped detail, kept OPEN narrowed to Slice 2/3.
- **`CARRY_FORWARD.md`:** no edit — next-step arc lives in GitHub issues.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Purpose classifier | `layer4/session_feasibility.py` | `def surface_purpose(`; `SURFACE_AEROBIC`/`SURFACE_VERT`/`SURFACE_TECHNICAL`; `_SURFACE_PURPOSE_ORDER` |
| Resolution field | `layer4/session_feasibility.py` | `TerrainResolution` has `surface_routes`; built in `enrich_resolution_display` (new `terrain_attrs` param); EXACT `feasibility_line` renders "routed by session purpose" |
| Terrain attrs reader | `layer4/orchestrator.py` | `def _q_terrain_attributes(`; `_FeasibilityInputs` has `terrain_attrs`; `enrich_resolution_display(... terrain_attrs=fi.terrain_attrs)` |
| Prompt revision | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "5"` |
| Unit tests | `tests/test_layer4_session_feasibility.py` | `test_surface_routing_sends_each_purpose_to_its_nearest_surface`; `test_no_routing_without_attrs_falls_back_to_menu`; `test_surface_purpose_classifier` |
| Design | `designs/Layer4_SurfaceSpecificRouting_624_Design_v1.md` | Slice 1 built / Slice 2+3 deferred |
| Suite | — | tests/ 2487 passed / 30 skipped; etl/tests 89 |
| Gate | — | NO DDL (reads existing columns); Layer-0 gate + JS harness unaffected |
| Issue | #624 | OPEN, narrowed to Slice 2/3 |
| Owed | — | `layer0-apply` for 0007 (#622) **APPLIED 2026-06-16 (run #2, success)**; T3-refresh re-verify the only carried owed |
