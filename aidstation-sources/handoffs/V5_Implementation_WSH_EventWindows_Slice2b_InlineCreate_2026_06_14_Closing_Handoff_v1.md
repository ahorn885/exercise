# V5 Implementation — WS-H: Event Windows — Slice 2b: inline-create-a-new-destination — Closing Handoff

**Session:** Built **Slice 2b** of the Event-Windows arc — the UX follow-up Slice 2a explicitly deferred. The away-window capture on `/profile/event-windows` now lets the athlete **create a not-yet-saved destination during window capture** by linking into the existing `/locales/new` Mapbox flow with a `return_to` back to the event-windows page. Pure UX over the schema 2a shipped; **no new route, no schema, no DDL.**
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice2a_AwayWindows_2026_06_14_Closing_Handoff_v1.md` (away windows + counts-follow-away, PR #600 merged + live).
**Branch:** `claude/eventwindows-away-windows-xon8mb` (PR to open).
**Spec:** `designs/Event_Windows_Slice2_AwayWindows_Spec_v1.md` §5 "Slice 2b". **Arc:** `designs/Event_Windows_Design_v1.md` §6 bullet 2 (F1/F2). **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. **Epic:** [#581](https://github.com/ahorn885/exercise/issues/581).

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the Slice-2a handoff — all green, tree clean, branch correct (`claude/eventwindows-away-windows-xon8mb`, freshly cut from `main` at #600, 0 commits ahead). Spot-checked every §8 anchor on disk and all present: `locations.cluster_locale_ids(... anchor_locale=None)`; the `away` replacement branch + `owned_crafts` kwarg in `orchestrator.py`; `EventWindowOverride.away_locale` + `EventWindowSegment.away_feasibility` in `session_feasibility.py`; the `counts_follow_away` log in `per_phase.py`; `OVERRIDE_TYPES = (…, "away")` in `athlete_event_windows_repo.py`. No drift — Slice 2a is genuinely landed, merged, and live.

---

## 2. What shipped

### The decision (made explicit before building)

The spec §5 says Slice 2b is "search-and-create-a-new-location inline, **reusing `routes/locales.py new_locale`** + the `mapbox_id` dedup." The load-bearing interpretation: **"inline" = create-during-the-capture-flow, via a link into the existing `new_locale` route**, NOT a re-implemented embedded search widget. Reasons:
- `new_locale` already owns the *entire* Mapbox flow: geocoding-consent disclosure (a legal gate), place search, chain detection, the `mapbox_id` / `gym_profiles.mapbox_id UNIQUE` dedup (differentiator #8 — two athletes' "Belfast hotel" converge into shared crowd data), the manual-entry fallback, AND a `return_to` round-trip mechanism (`_stash_return_to` / `_locale_flow_redirect`).
- The app is **strict-CSP** (`app.py:439` — nonce'd script-src, no inline JS/handlers). An embedded autocomplete search would need inline JS and would **duplicate the consent + dedup machinery** — both against simplicity-first.

So 2b is the **connecting link only**.

### Implementation

- **`templates/profile/event_windows.html`** — under the away-destination dropdown, a hint + link: *"Destination not saved yet? [Add a new location] — you'll return here to finish the window."* The link is `url_for('locales.new_locale', return_to=url_for('profile.event_windows'))` → renders `/locales/new?return_to=/profile/event-windows`. Header comment updated to document the 2b reuse approach.
- **How the round-trip works (all pre-existing plumbing):** `new_locale`'s GET calls `_stash_return_to()`, which session-stashes a safe local `return_to` (must start with `/`, not `//`). Subsequent search GETs / the disclosure-ack roundtrip don't carry `return_to`, but `_stash_return_to` only *writes* when the arg is present, so the stashed value survives. On save, both the Mapbox non-chain path (`_save_mapbox_anchored`) and the manual path (`save_manual_locale`) terminate in `_locale_flow_redirect()`, which **pops** the stashed path and redirects there → back to `/profile/event-windows`, where the freshly-created locale now appears in the away dropdown (`event_windows()` GET reloads `locale_profiles` every render). The chain-hit path detours through `nearby_instances` first, which also ends in `_locale_flow_redirect()` — the stash persists until consumed.
- **`mapbox_id` dedup is inherited for free:** because creation goes through `_save_mapbox_anchored`, the existing `_existing_locale_by_mapbox_id` create-time dedup (PR18 item C) applies — no new dedup code.

### What 2b deliberately does NOT do
- **No form-state preservation across the round-trip.** After returning, the athlete re-enters the (already-known) window dates and re-selects "away" + the now-saved destination. Preserving in-progress form values into a static link would require inline JS (CSP-forbidden) or POST-stashing machinery — out of proportion for a minimal slice. If the friction bothers Andy, it's a Slice-5 capture-UX-polish candidate, not a 2b blocker.
- No embedded search, no new route, no schema/DDL.

---

## 3. Files

| File | Kind | Change |
|---|---|---|
| `templates/profile/event_windows.html` | substantive (UI) | "Add a new location" link under the away dropdown (`return_to=url_for('profile.event_windows')`) + updated header comment. |
| `tests/test_redesign_locales_form_render.py` | tests (not counted) | +1 render-smoke test `test_event_windows_capture_renders_away_create_link`. |

**Bookkeeping:** `CURRENT_STATE.md` (new top entry, 2a demoted to predecessor), `CARRY_FORWARD.md` (2b flipped 📌→✅, slice order struck through), `designs/Event_Windows_Slice2_AwayWindows_Spec_v1.md` (status line annotated 2b built), this handoff.

**File-count:** 1 substantive (template). Smaller than the spec anticipated ("route + template + locale-builder reuse") because the `return_to` round-trip already existed — no route change was needed.

---

## 4. Tests

`tests/test_redesign_locales_form_render.py` +1: `test_event_windows_capture_renders_away_create_link` renders `profile/event_windows.html` through the booted app's Jinja env (request context + fake user, the file's existing harness) and asserts (a) the 2a pick-existing dropdown (`name="away_locale"`, a saved locale slug), (b) the 2b inline-create link (`/locales/new?return_to=`, `event-windows`, "Add a new location"), and (c) strict-CSP cleanliness (no `style="` / `onclick=`).

**Full suite: 2433 passed / 30 skipped** (+1 vs 2a's 2432). Env: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`. (Single-file collection hits the documented circular-import quirk — front-load `tests/test_layer4_event_windows.py` or run the full `tests/`.)

Also eyeballed the rendered link via a request-context render: emits exactly `<a href="/locales/new?return_to=/profile/event-windows">Add a new location</a>`.

---

## 5. Next session

### 5.1 Owed Andy's hands
- **Nothing new owed** — no DDL, reuses live routes.
- (carried) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

### 5.2 Deferred follow-ups (remaining Event-Windows slices)
- **Slice 3 — category equipment baselines (Trigger #2)** — an assumed equipment profile for a not-yet-logged away gym (commercial/hotel/climbing) + the assumed→logged **arrival-regen** loop (F6/F8). Baseline *contents* need Andy's sign-off (no-padding). **This is what makes away useful *cold*** — today an away gym with nothing logged degrades to near-strength. **Recommended next.**
- **Slice 4 — away craft (the literal WS-H #581 (b)+(c))** — craft↔locale ∪ craft↔window → populates the away env's `owned_crafts` (today hard-coded `[]`). DDL: `athlete_craft_locale` + a window craft carrier.
- **Slice 5 — capture UX polish** (nav-link to `/profile/event-windows` from the Athlete tab; plan-gen review panel; optionally the 2b round-trip form-state preservation noted in §2).
- (split out earlier) #592 race-location terrain/weather inference; #593 reduced-volume travel days.

### 5.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — top entry (WS-H Event Windows).
4. This handoff.
5. `designs/Event_Windows_Slice2_AwayWindows_Spec_v1.md` (§5 Slice-2b) + `designs/Event_Windows_Design_v1.md` (arc).
6. `./scripts/verify-handoff.sh` (from `aidstation-sources/`).

**Test env:** `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then full `tests/`.

---

## 6. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Inline-create link | `templates/profile/event_windows.html` | `url_for('locales.new_locale', return_to=url_for('profile.event_windows'))` under the `away_locale` dropdown; "Add a new location" text |
| Reuse target (route) | `routes/locales.py` | `new_locale` GET calls `_stash_return_to()`; `_save_mapbox_anchored` / `save_manual_locale` end in `_locale_flow_redirect()` (unchanged this slice) |
| return_to mechanism | `routes/locales.py` | `_stash_return_to` (writes only when `return_to` present, local-path-guarded); `_locale_flow_redirect` (pops + redirects) — unchanged this slice |
| Dedup (inherited) | `routes/locales.py` | `_existing_locale_by_mapbox_id` create-time dedup in `_save_mapbox_anchored` — unchanged, applies for free |
| Test | `tests/test_redesign_locales_form_render.py` | `test_event_windows_capture_renders_away_create_link` |
| Suite | — | 2433 passed / 30 skipped |
| No schema/DDL | — | grep confirms no `init_db.py` / repo change this slice |

---

## 7. Owed Andy's hands
- **Nothing owed** — no DDL; reuses live routes.
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify.
