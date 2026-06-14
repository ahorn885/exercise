# V5 Implementation — WS-H: Event Windows — Slice 2a: away windows + counts-follow-away — Closing Handoff

**Session:** Built **Slice 2a** of the Event-Windows arc — the third `override_type='away'`: a date-bounded window where the athlete trains from a *different* location whose environment **replaces** the home cluster (vs Slice 1's two *subtractive* home types). Includes **counts-follow-away** (a fully-away week is counted against the destination). Design-first spec written + ratified in-session (Andy made all three open decisions live), then built, tested, and merged.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_RefreshOverlay_2026_06_14_Closing_Handoff_v1.md` (refresh-overlay render, PR #599 merged).
**Branch:** `claude/eventwindows-refresh-overlay-lbw9y6` (PR [#600](https://github.com/ahorn885/exercise/pull/600), squash-merged to `main` 2026-06-14; CI green).
**Spec:** `designs/Event_Windows_Slice2_AwayWindows_Spec_v1.md` (build-ready; Andy's decisions locked in §10). **Arc:** `designs/Event_Windows_Design_v1.md` §6 bullet 2. **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. **Epic:** [#581](https://github.com/ahorn885/exercise/issues/581) (Phase H away-craft; away *windows* are its foundation).

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the refresh-overlay handoff — all green, tree clean, branch correct. Spot-checked the refresh-overlay anchors (`#599` at HEAD `b02e88d`; `orchestrate_plan_refresh` builds the overlay; the T1/T2/T3 renderers carry `event_window_segments`) — all present. No drift.

---

## 2. What shipped

### Decisions ratified in-session (Andy 2026-06-14)
1. **Counts-follow-away** (vs counts-on-home) — a *fully-away* week is counted against the destination. The grounding win: the session grid is **already per-week** and **already consumes** a per-week `strength_feasibility_tiers` dict (WS-E2 reallocation), so this is "pick the right dict per week" — **no new count machinery, no `session_grid.py` change**. **Whole-week threshold** (partial/mixed weeks keep home counts + per-day composition; the grid's unit is the week and a mixed week spans two environments).
2. **Away wording APPROVED** (Trigger #1) — the away `_event_window_label` + the away-aware overlay block intro.
3. **Inline-create** chosen → re-sliced: **2a** (this — resolution + counts + *pick-existing* capture) + **2b** (inline-create-a-new-destination UX, separate PR).

Plus two earlier-in-session corrections folded into the spec: away env = the destination's **own radius cluster** (re-anchored `cluster_locale_ids`, same logic as home — the `locale_profiles` discriminator I first proposed was **dropped**); and confirmed there is **one unified feasibility cascade**, not two (WS-I Slice B #588) — away reuses it with `owned_crafts=[]`.

### Implementation
- **`away` replaces the home env with the destination's radius cluster.** `cluster_locale_ids(db, user_id, anchor_locale=None)` generalized: `None` → the `preferred` home anchor (byte-identical to the old signature, every existing caller unaffected); a supplied anchor → re-anchor the 26.2 mi sweep at that locale. The away path passes `anchor_locale=away_locale`.
- **Same cascade, `owned_crafts=[]`** (F4 — home craft doesn't travel). `_resolve_included_feasibility` gained an optional `owned_crafts` kwarg (default `None` → `fi.owned_crafts`, byte-identical for home + the Slice-1 subtractive segments; away passes `[]`). The craft tiers simply find nothing and the walk degrades through INDOOR→STRENGTH→REALLOCATE — the same craftless degradation #588 already runs.
- **Precedence:** when an `away` window co-occurs with a subtractive override on the same dates, `away` **wins** (it's a replacement) and the subtractive override is ignored (logged).
- **Counts-follow-away:** `EventWindowSegment` carries the **full** away feasibility (`away_feasibility`) alongside the terse `resolutions` diff; `_format_session_grid` resolves each week's date range (`phase.start_date + (w-1)*7 .. +6d`) and, for a week **fully** inside an away segment, feeds `away_feasibility` to the grid → WS-E2 reallocates the weekly counts toward what the destination supports.
- **Render + cache:** away-aware `_event_window_label` + overlay intro (Trigger-#1, approved); `away_locale` folded into `compute_event_windows_hash`.
- **Capture:** an `away` row type on `/profile/event-windows` with a *pick-existing* destination dropdown (inline-create is 2b).
- **Rule #15:** the shared overlay builder logs the away env + `owned_crafts=[]`; `_format_session_grid` logs `counts_follow_away: <phase>:w<W> … fully-away → grid counted against the away env tiers={…}`.

---

## 3. Files

| File | Kind | Change |
|---|---|---|
| `layer4/session_feasibility.py` | substantive | `EventWindowOverride` gains `'away'` + `away_locale`; `EventWindowSegment` gains `away_feasibility`. |
| `layer4/orchestrator.py` | substantive | `_build_event_window_overlay` away replacement branch (re-anchored cluster + precedence + `away_feasibility` capture); `_resolve_included_feasibility` optional `owned_crafts`. |
| `locations.py` | substantive | `cluster_locale_ids(anchor_locale=None)` — re-anchorable radius sweep. |
| `layer4/per_phase.py` | substantive | counts-follow-away per-week env selection in `_format_session_grid`; away `_event_window_label` + away-aware overlay intro. |
| `athlete_event_windows_repo.py` | substantive | `'away'` in `OVERRIDE_TYPES`; `EventWindow.away_locale` + load/add validation (required+resolvable iff away; clears the other locale field). |
| `layer4/hashing.py` | mechanical | `away_locale` into `compute_event_windows_hash`. |
| `routes/profile.py` | mechanical | thread `away_locale` from the form. |
| `templates/profile/event_windows.html` | mechanical (UI) | away option + destination dropdown + away row render. |
| `init_db.py` | DDL (bookkeeping) | `away_locale` column on `athlete_event_windows` (CREATE + idempotent ALTER). |
| `tests/test_layer4_event_windows.py` | tests (not counted) | +9 (see §4). |

**File-count:** 5 substantive core + thin mechanical (hashing one-field, 1-line route, template, DDL) — consistent with Slice 1's ~6, flagged. Inline-create deliberately deferred to 2b to hold the ceiling.

---

## 4. Tests

`tests/test_layer4_event_windows.py` +9:
- `TestAwayWindows` — away degrades when the destination lacks terrain (+ `away_feasibility` captured); stays exact when it has terrain; `away` wins over a same-date subtractive override.
- `TestCountsFollowAway` — a **fully-away** week logs `counts_follow_away` (fed the away tiers); a **partial** week does not; no away segment never logs.
- `TestOverlayRender::test_away_segment_renders_away_label` — the approved away wording renders.
- `TestHashAndKey::test_hash_changes_with_away_locale`; `TestRepo` away validation (`away` requires a resolvable destination; clears `unavailable_locale`).

Updated 5 Slice-1 tests for the new `away_locale` column (positional `EventWindow(...)`, fake-row dict, insert-tuple, the unknown-type test repointed to `"teleport"` since `"away"` is now valid).

**Full suite: 2432 passed / 30 skipped.** Env: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

---

## 5. Decisions pinned (Andy, 2026-06-14)

| # | Decision |
|---|---|
| 1 | **Counts-follow-away** for fully-away weeks (whole-week threshold); via the existing WS-E2 per-week reallocation. |
| 2 | Away env = the destination's **own radius cluster** (re-anchored `cluster_locale_ids`); **no `locale_profiles` discriminator.** |
| 3 | Away wording **approved** (Trigger #1). |
| 4 | **Inline-create** wanted → re-sliced 2a (pick-existing) + 2b (inline-create). |
| 5 | (carried) one unified cascade, not two — away reuses it with `owned_crafts=[]`. |

---

## 6. Next session

### 6.1 Owed Andy's hands
- **DONE this session:** the `away_locale` ALTER on Neon (`ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS away_locale TEXT`) — **applied by Andy 2026-06-14** → Slice 2a is **fully live** in prod (away capture + the away plan-gen resolution + counts-follow-away are active).
- (carried) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

### 6.2 Deferred follow-ups (the remaining Event-Windows slices)
- **Slice 2b — inline-create-a-new-destination UX** (F1/F2). The away capture currently picks an *existing* saved locale; 2b adds search-and-create-a-new-location inline, reusing `routes/locales.py new_locale` + the `mapbox_id`/`gym_profiles.mapbox_id UNIQUE` dedup (*"travel is how we build the crowd-sourced locations DB"*, differentiator #8). Pure UX over the **same** schema 2a shipped — no resolution risk.
- **Slice 3 — category equipment baselines (Trigger #2)** — an assumed equipment profile for a not-yet-logged away gym (commercial/hotel/climbing) + the assumed→logged **arrival-regen** loop (F6/F8). Baseline *contents* need Andy's sign-off (no-padding). This is what makes away useful *cold* (today an away gym with nothing logged degrades to near-strength).
- **Slice 4 — away craft (the literal WS-H #581 (b)+(c))** — craft↔locale ∪ craft↔window → populates the away env's `owned_crafts` (today hard-coded `[]`). DDL: `athlete_craft_locale` + a window craft carrier. The away-env surface 2a built is exactly where this attaches.
- **Slice 5 — capture UX polish** (nav-link, plan-gen review panel).
- (split out earlier) #592 race-location terrain/weather inference; #593 reduced-volume travel days.

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — top entry (WS-H Event Windows).
4. This handoff.
5. `designs/Event_Windows_Slice2_AwayWindows_Spec_v1.md` (Slice-2 spec) + `designs/Event_Windows_Design_v1.md` (arc).
6. `./scripts/verify-handoff.sh` (from `aidstation-sources/`).

**Test env:** `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then full `tests/`.

---

## 7. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Re-anchorable cluster | `locations.py` | `def cluster_locale_ids(db, user_id, anchor_locale=None)` — `None` → `preferred` row; else `WHERE locale = anchor_locale` |
| Away env build | `layer4/orchestrator.py` | `_build_event_window_overlay` — `away_ov = next(... "away" ...)`; `cluster_locale_ids(..., anchor_locale=away_ov.away_locale)`; `_resolve_included_feasibility(..., owned_crafts=[])`; `away_feasibility=` on the emitted segment |
| Owned-crafts override | `layer4/orchestrator.py` | `_resolve_included_feasibility(..., owned_crafts: list[str] | None = None)` → `crafts = fi.owned_crafts if owned_crafts is None else owned_crafts` |
| Segment payload | `layer4/session_feasibility.py` | `EventWindowOverride.away_locale`; `EventWindowSegment.away_feasibility` |
| Counts-follow-away | `layer4/per_phase.py` | `_format_session_grid(..., event_window_segments=...)`; `counts_follow_away:` log; `strength_feasibility_tiers` fed `week_feasibility` for a fully-away week |
| Away wording | `layer4/per_phase.py` | `_event_window_label` away branch (`away at "..."`); overlay intro "reduced … or replaced" |
| Hash | `layer4/hashing.py` | `compute_event_windows_hash` includes `away_locale` |
| Repo | `athlete_event_windows_repo.py` | `OVERRIDE_TYPES = (..., "away")`; `away` requires resolvable `away_locale`; clears `unavailable_locale` |
| DDL | `init_db.py` | `... away_locale TEXT ...` in CREATE + `ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS away_locale TEXT` — **applied on Neon (Andy)** |
| Tests | `tests/test_layer4_event_windows.py` | `TestAwayWindows`, `TestCountsFollowAway`, away render/hash/repo |
| Suite | — | 2432 passed / 30 skipped |

---

## 8. Owed Andy's hands
- **Nothing new owed** — the `away_locale` ALTER is **applied** (Andy 2026-06-14); Slice 2a is fully live.
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify.
