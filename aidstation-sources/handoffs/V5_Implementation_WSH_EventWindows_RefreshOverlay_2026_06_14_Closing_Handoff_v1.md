# V5 Implementation — WS-H: Event Windows — refresh-overlay render (create-first follow-up) — Closing Handoff

**Session:** Wired the Slice-1 event-window overlay into **plan-refresh** — the tier-3 "finish what's partially live" item flagged in the Slice-1 build handoff §6.2. Slice 1 rendered the overlay on plan-**create** only; the refresh caller had `event_windows_hash` on `plan_refresh_key` but never supplied it, so a refreshed plan correctly *evicted* caches on a window edit but never *rendered* the overlay. This closes that gap. Mirrors the #540→#557 pattern (terrain-feasibility create→refresh).
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice1_Build_2026_06_14_Closing_Handoff_v1.md` (Slice 1 BUILT + LIVE, PR #596).
**Branch:** `claude/eventwindows-slice-2-hn8yvq` (PR [#599](https://github.com/ahorn885/exercise/pull/599), squash-merged to `main` 2026-06-14; CI green).
**North-star plan:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. Arc design `designs/Event_Windows_Design_v1.md`.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the Slice-1 build handoff — **all green**, working tree clean, branch correct. Spot-checked the Slice-1 anchors (overlay builder, hash+key, per_phase render) all present on `main`. No drift.

**Scope decision (Andy, via AskUserQuestion):** the branch is named for Slice 2, but I surfaced the sequencing tension — (a) by the 4-tier order, the refresh-overlay render is a tier-3 "finish partially-live" item ahead of Slice 2 (tier-4 new functionality); (b) Slice 2 has no build-ready spec and trips Trigger #1 (new away wording) + Trigger #3 (schema). Andy picked **refresh-overlay wiring first**. No stop-and-ask trigger fired for this work: the overlay block + soft directive wording was already signed off in Slice 1, and there is no schema change.

---

## 2. What shipped

The overlay now renders on refresh for **all tiers**: T1/T2/T3-intra (Pattern B) and T3 cross-phase (Pattern A). Implementation mirrors the existing `terrain_feasibility` threading exactly:

1. **`orchestrator.orchestrate_plan_refresh`** — builds the overlay over `[refresh_scope_start, refresh_scope_end]` (only those dates are re-synthesized) via the **same** `_build_event_window_overlay` the create path uses, computes `compute_event_windows_hash(overlapping_windows)`, and passes both `event_window_segments` + `event_windows_hash` into the cached wrapper.
2. **`cached_wrappers.llm_layer4_plan_refresh_cached`** — new `event_window_segments` + `event_windows_hash` kwargs; folds the hash into `plan_refresh_key` (the param already existed → **None stays byte-identical**, Slice-1 regression preserved) and threads the segments into the synthesizer.
3. **`plan_refresh.llm_layer4_plan_refresh`** — new `event_window_segments` kwarg, threaded into the tier `render_user_prompt` call **and** the T3 cross-phase route.
4. **`plan_refresh._route_t3_cross_phase_to_pattern_a`** → **`plan_create.synthesize_pattern_a_for_refresh`** → `_run_pattern_a_engine` (which already renders via `per_phase`) — new kwarg threaded through; T3 cross-phase gets the overlay for free.
5. **`plan_refresh_t1/t2/t3.render_user_prompt`** — render the existing `per_phase._format_event_window_overlay` block (wording signed off in Slice 1) scoped to the refresh window, placed right after the `=== Session feasibility ===` block, exactly like create's per_phase.

**Rule #15:** logging is **inherited** — the shared `_build_event_window_overlay` already emits the `event_window_overlay: dates=… override=… tiers={…}` decision line per segment, so the refresh path is diagnosable with no new instrumentation.

---

## 3. Files

| File | Kind | Change |
|---|---|---|
| `layer4/orchestrator.py` | substantive | `orchestrate_plan_refresh` builds the overlay over the refresh scope + feeds `event_window_segments`/`event_windows_hash`. |
| `layer4/plan_refresh_t1.py` / `plan_refresh_t2.py` / `plan_refresh_t3.py` | substantive (render) | import + `event_window_segments` param + the `_format_event_window_overlay` block scoped to the refresh window. |
| `layer4/cached_wrappers.py` | mechanical | `event_window_segments`/`event_windows_hash` passthrough on the refresh wrapper (mirror of the create wrapper + the terrain_feasibility passthrough). |
| `layer4/plan_refresh.py` | mechanical | thread `event_window_segments` into the tier render + the T3 cross-phase route. |
| `layer4/plan_create.py` | mechanical | `synthesize_pattern_a_for_refresh` passes `event_window_segments` into `_run_pattern_a_engine`. |
| `tests/test_layer4_plan_refresh.py` + `tests/test_layer4_event_windows.py` | tests (not counted) | refresh overlay render (overlap / out-of-scope) + `plan_refresh_key` changes-with-windows. |

**File-count:** 4 substantive (orchestrator + 3 tier renderers); the other 3 are mechanical mirrors of the established `terrain_feasibility` threading. Within the 5-file ceiling. Additive-only diff (172 insertions, 0 deletions). **NO DDL, no prompt-wording change, no vocab adds.**

---

## 4. Tests

- `test_event_window_overlay_rendered_when_segment_overlaps` — overlay block present (header + `indoor-only…` label + soft directive) when a segment overlaps the refresh scope; **absent** when no segments supplied (legacy/no-window refreshes).
- `test_event_window_overlay_absent_when_segment_outside_scope` — a window 30 days past the scope renders nothing.
- `test_plan_refresh_key_changes_with_windows` — companion to the existing `…byte_identical_when_no_windows`: locks that the hash actually folds into the refresh key.

**Full suite: 2423 passed / 30 skipped.** Env: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

---

## 5. Decisions pinned (Andy, 2026-06-14)

| # | Decision |
|---|---|
| 1 | Do the **refresh-overlay wiring first** (tier-3 finish) before Slice 2. |
| 2 | (carried) Slice 1 overlay wording stays as signed off; reused verbatim on refresh. |

---

## 6. Next session

### 6.1 Owed Andy's hands
- **Nothing new this session** — no DDL, no Neon writes. Slice 1 + this refresh-overlay finish are both fully live once #599 merges (markdown/Python only; the overlay activates on the next refresh).
- (carried) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14). This session's change is now *also* worth eyeballing on that re-verify: a refresh whose scope overlaps a declared window should show the `=== Event-window overlay …===` block in the tier prompt (visible via `/admin/logs` if prompt logging is on) and route the affected days against the reduced env.

### 6.2 Deferred follow-ups (flagged)
- **Slice 2 — away windows (the next slice; design-first).** away locale destination (reused `locale_profiles` row + inline create, `mapbox_id` dedup, *"travel is how we build the crowd-sourced locations DB"* — differentiator #8), the `away` override_type + `away_locale` column, away discriminator on `locale_profiles`, per-environment cascade (the destination's terrain/equipment, not a subtraction of home). **Trips Trigger #1** (new away-overlay directive wording — the current `_event_window_label` has a defensive `else` branch for non-subtractive types but no away copy) **+ Trigger #3** (schema). **No build-ready spec exists yet** — Slice 1 had `Event_Windows_Slice1_HomeWindows_Spec_v1.md` written design-first; Slice 2 needs the same before any code. DDL will be owed-Andy's-hands (Neon egress blocked from the container). This is also where **counts may shift** (whole-week away windows) and the grid/E2 seam may need the segment tiers — the main risk Andy flagged in the arc design (F3).
- **Slice 3** — category equipment baselines (Trigger #2; commercial/hotel/climbing gyms via `routes/locales.py MANUAL_CATEGORIES`). Baseline *contents* need Andy's sign-off.
- **Slice 4** — away craft (the literal WS-H (b)+(c)): craft↔locale ∪ craft↔window. DDL: `athlete_craft_locale` + window craft carrier.
- **Slice 5 / optional polish** — nav-link `/profile/event-windows` from the Athlete tab.
- (split out earlier) #592 race-location terrain/weather inference; #593 reduced-volume / in-transit travel days.

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — top entry (WS-H Event Windows).
4. This handoff.
5. `designs/Event_Windows_Design_v1.md` (arc) + `designs/Event_Windows_Slice1_HomeWindows_Spec_v1.md` (Slice 1, for the cascade/threading model Slice 2 reuses).
6. `./scripts/verify-handoff.sh` (from `aidstation-sources/`).

**Test env:** `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then full `tests/`.

---

## 7. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Refresh overlay build | `layer4/orchestrator.py` | `orchestrate_plan_refresh` calls `_build_event_window_overlay(... plan_start=refresh_scope_start, plan_end=refresh_scope_end ...)` + passes `event_window_segments`/`event_windows_hash` to `llm_layer4_plan_refresh_cached` |
| Cached wrapper | `layer4/cached_wrappers.py` | `llm_layer4_plan_refresh_cached` has `event_window_segments` + `event_windows_hash` params; `event_windows_hash=` passed to `plan_refresh_key`; `event_window_segments=` to `llm_layer4_plan_refresh` |
| Driver | `layer4/plan_refresh.py` | `llm_layer4_plan_refresh` + `_route_t3_cross_phase_to_pattern_a` thread `event_window_segments` |
| T3 cross-phase | `layer4/plan_create.py` | `synthesize_pattern_a_for_refresh` passes `event_window_segments` into `_run_pattern_a_engine` |
| Tier render | `layer4/plan_refresh_t{1,2,3}.py` | import `_format_event_window_overlay`; `event_window_segments` param; block rendered after `=== Session feasibility ===` |
| Tests | `tests/test_layer4_plan_refresh.py` | `test_event_window_overlay_rendered_when_segment_overlaps` + `..._absent_when_segment_outside_scope` |
| Key regression | `tests/test_layer4_event_windows.py` | `test_plan_refresh_key_changes_with_windows` (+ existing `..._byte_identical_when_no_windows`) |
| Suite | — | 2423 passed / 30 skipped |

---

## 8. Owed Andy's hands
- **Nothing new this session.**
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify — now also a chance to eyeball the refresh-overlay render on a window-overlapping scope.
</content>
</invoke>
