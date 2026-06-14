# V5 Implementation — WS-H: Event Windows Slice 1 BUILD (subtractive home windows) — Closing Handoff

**Session:** Built **Slice 1** of the Event-Windows arc (issue [#581](https://github.com/ahorn885/exercise/issues/581) Phase H) per the build-ready spec `designs/Event_Windows_Slice1_HomeWindows_Spec_v1.md`. The athlete declares date-bounded **subtractive home windows** — `indoor_only` + `locale_unavailable` — and plan-gen resolves the affected days against the reduced home environment via the **existing cascade run per date-segment** (Andy's settled §4 model).
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Design_2026_06_14_Closing_Handoff_v1.md` (the arc design + this spec, #591+#594).
**Branch:** `claude/compassionate-keller-ej5tcx` (PR [#596](https://github.com/ahorn885/exercise/pull/596), squash-merged to `main` 2026-06-14; CI green).
**North-star plan:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the design handoff — clean except `tests/test_layer4_event_windows.py` ❌, which was the Slice-1 deliverable to create (not claimed-landed state). Working tree clean, branch correct. Spot-checked the spec §4 "existing cascade … per date-segment" + the design forks RATIFIED. No drift. **Trigger #1** (overlay prompt wording) brought to Andy before writing `per_phase` — he picked **"Proceed as drafted"** after confirming away = Slice 2 (his clarifying question: does the overlay account for a *different* location? Answer: no — that's the additive `away` override, deliberately Slice 2).

---

## 2. What shipped (the resolution model)

**Andy's §4 model held verbatim:** a window is just different `(terrain, equipment)` inputs to the **same** EXACT→PROXY→INDOOR→STRENGTH→REALLOCATE cascade; the only new element is the time dimension. Implementation:

1. **Refactor** `orchestrator._build_terrain_feasibility` → `_gather_feasibility_inputs` (reads cluster + all environment-independent inputs once) + `_resolve_included_feasibility(fi, *, locale_order, terrain_by_locale, equip_by_locale)` (the cascade against an **injected** environment). `_build_terrain_feasibility` = gather + resolve(home) + the existing detailed Rule #15 log (behavior-identical; its tests stay green).
2. **`session_feasibility.segment_window_boundaries`** (pure) cuts `[plan_start, plan_end]` into atomic date sub-ranges at every window boundary; each carries the union of overrides active across all its days (spec §8 overlap handling). `EventWindowOverride` + `EventWindowSegment` dataclasses live here (below both orchestrator + per_phase → no import cycle).
3. **`orchestrator._build_event_window_overlay`** loads the athlete's windows, keeps those overlapping the span, segments, runs `_reduced_env` (indoor_only → drop all terrain; locale_unavailable(L) → drop locale L) then `_resolve_included_feasibility` per segment, and emits a segment **only for the disciplines whose routing CHANGES** vs home (no-op segments dropped + logged). Plan span = the same deterministic `phase_structure_from_3b` the engine rebuilds, so the overlapping-window set (→ cache key) matches what renders.
4. **Cache:** `hashing.compute_event_windows_hash(overlapping_windows)` (declared `override_type`+dates+`unavailable_locale`) folded into **both** `plan_create_key` + `plan_refresh_key` — **appended only when a window overlaps**, so a no-windows key is byte-identical to the pre-Slice-1 form (regression (a)). Orchestrator computes the hash; passes it + the segments to `llm_layer4_plan_create_cached`.
5. **Synthesis:** `per_phase._format_event_window_overlay` renders the **Trigger-#1 block** (signed off) — `=== Event-window overlay (deterministic — date-scoped routing) ===` + per-segment bullets (dates clipped to the unit window) reusing `feasibility_line`, + the `Placement preference (soft)` directive. Rendered only for synthesis units (block or whole-phase) whose date window overlaps a segment.
6. **Capture UI:** `routes/profile` `/profile/event-windows` (GET list + add + delete) + `templates/profile/event_windows.html` (reuses the locale list for the `locale_unavailable` picker).
7. **DDL:** `athlete_event_windows` + `idx_aew_user` in `init_db._PG_MIGRATIONS` (idempotent).
8. **Rule #15:** `event_window_overlay: dates=… override=… tiers={…}` per segment (names the cascade-landed tier, never assumes indoor/strength).

**Threading** of `event_window_segments` mirrors the existing `terrain_feasibility` param exactly: `cached_wrappers` → `plan_create._run_pattern_a_engine` → `per_phase.synthesize_phase` → `render_user_prompt` (mechanical passthroughs).

---

## 3. Files

| File | Kind | Change |
|---|---|---|
| `athlete_event_windows_repo.py` | new substantive | load/add/delete + app-layer validation + `evict_plan_caches_on_event_windows_change` (scoped to plan_create+plan_refresh). Cache imports are **function-local** to avoid a layer4-package import cycle. |
| `layer4/session_feasibility.py` | substantive | `EventWindowOverride`/`EventWindowSegment` + pure `segment_window_boundaries`. |
| `layer4/orchestrator.py` | substantive | gather/resolve refactor + `_reduced_env` + `_build_event_window_overlay` + `orchestrate_plan_create` wiring + imports (`_compute_total_weeks`, `phase_structure_from_3b`, `compute_event_windows_hash`, repo, session_feasibility). |
| `layer4/hashing.py` | substantive | `compute_event_windows_hash` + `event_windows_hash` param on both plan keys (conditional append → byte-identical no-windows). |
| `layer4/per_phase.py` | substantive | `_format_event_window_overlay` + `_event_window_label` + thread `event_window_segments` through `render_user_prompt` + `synthesize_phase`. |
| `routes/profile.py` + `templates/profile/event_windows.html` | substantive (UI) | minimal capture surface. |
| `layer4/cached_wrappers.py`, `layer4/plan_create.py` | mechanical | passthrough of `event_window_segments` (+ `event_windows_hash` on the create wrapper), mirroring `terrain_feasibility`. |
| `init_db.py` | bookkeeping-adjacent | the DDL migration. |
| `tests/test_layer4_event_windows.py` | tests (not counted) | 29 tests. |

**File-count flag:** ~6 substantive (UI counted; the two threading files are mechanical mirrors). One over the soft 5-ceiling — flagged, consistent with the WS-B/WS-C 7-file precedent + the spec's own template-split allowance.

---

## 4. Tests

`tests/test_layer4_event_windows.py` (29): `segment_window_boundaries` (single/clamp/outside/overlap-union/empty); reduced-env routing for both override types incl. the cascade fallback "stays exact at another locale" (spec §9.4) + "only terrain source closed → degrades" (§9.5) + locale-not-in-cluster no-op; `_build_event_window_overlay` glue (changed emitted / no-op dropped / no-overlap empty); the overlay render (header + label + clipped dates + soft directive + empty cases) **and a full `render_user_prompt` integration** (overlay appears for an overlapping block, absent for a non-overlapping one); hash order-independence + the **byte-identical-key regression** on both plan keys; repo validation (unknown type, end<start, locale required+resolvable, indoor clears stray locale, delete user-scoped).

**Full suite: 2418 passed / 30 skipped** (2391 baseline + 27 new unit; the 2 integration tests reuse `test_layer4_plan_create` fixtures). Env: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

---

## 5. Decisions pinned (Andy, 2026-06-14)

| # | Decision |
|---|---|
| 1 | Build Slice 1 as drafted; away routing stays Slice 2 (his clarifying Q resolved: the overlay does NOT cover a *different* location — that's the additive `away` override). |
| 2 | Trigger-#1 overlay wording **approved as drafted** (block + soft placement directive). |
| 3 | (carried from design) §4 = existing cascade per date-segment; counts stay on home in Slice 1. |

---

## 6. Next session

### 6.1 Owed Andy's hands
- **Apply the `athlete_event_windows` DDL on Neon** (no container egress). Until applied, `/profile/event-windows` + the overlay are inert in prod. The idempotent `CREATE TABLE IF NOT EXISTS athlete_event_windows (…)` + `CREATE INDEX IF NOT EXISTS idx_aew_user …` are the last two entries in `init_db._PG_MIGRATIONS`.
- (carried) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

### 6.2 Deferred follow-ups (flagged)
- **Refresh-overlay render** — create-first this slice (mirrors #540→#557). `event_windows_hash` is a param on `plan_refresh_key` (default None → byte-identical); wire `orchestrate_plan_refresh` to compute overlapping windows over the refresh scope + feed the hash, and thread `event_window_segments` into the tier prompts (`plan_refresh_t*` `render_user_prompt`). A window edit already evicts both plan caches, so refresh won't serve stale — it just won't *render* the overlay until wired.
- **Slice 2** — away windows + destination locale (reused `locale_profiles` row + inline create) + the `away` override_type + `away_locale` column + per-environment cascade + `mapbox_id` dedup. This is where counts may shift (whole-week windows) and the grid/E2 may need the segment tiers.
- Optional Slice-5 polish: nav-link `/profile/event-windows` from the Athlete tab.

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — top entry (WS-H Slice 1 BUILT).
4. This handoff.
5. `designs/Event_Windows_Slice1_HomeWindows_Spec_v1.md` (built) + `designs/Event_Windows_Design_v1.md` (arc).
6. `./scripts/verify-handoff.sh` (from `aidstation-sources/`).

**Test env:** `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then full `tests/`.

---

## 7. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Repo | `athlete_event_windows_repo.py` | present; `load_event_windows` / `add_event_window` / `delete_event_window` / `evict_plan_caches_on_event_windows_change`; `OVERRIDE_TYPES = ("indoor_only", "locale_unavailable")` |
| Segmentation | `layer4/session_feasibility.py` | `segment_window_boundaries` + `EventWindowSegment` in `__all__` |
| Overlay builder | `layer4/orchestrator.py` | `_build_event_window_overlay` + `_reduced_env` + `_gather_feasibility_inputs` / `_resolve_included_feasibility`; `orchestrate_plan_create` passes `event_window_segments` + `event_windows_hash` |
| Hash + key | `layer4/hashing.py` | `compute_event_windows_hash`; `event_windows_hash` appended (conditional) in `plan_create_key` + `plan_refresh_key` |
| Overlay render | `layer4/per_phase.py` | `_format_event_window_overlay`; "Event-window overlay (deterministic — date-scoped routing)" + "Placement preference (soft)" |
| DDL | `init_db.py` | `CREATE TABLE IF NOT EXISTS athlete_event_windows` + `idx_aew_user` in `_PG_MIGRATIONS` |
| UI | `routes/profile.py` + `templates/profile/event_windows.html` | `/profile/event-windows` GET/add/delete |
| Tests | `tests/test_layer4_event_windows.py` | 29 pass |
| Suite | — | 2418 passed / 30 skipped |

---

## 8. Owed Andy's hands
- **`athlete_event_windows` DDL on Neon** (Neon egress blocked from the container).
- (carried, unrelated) the post-#572 live T3 *refresh* re-verify.
