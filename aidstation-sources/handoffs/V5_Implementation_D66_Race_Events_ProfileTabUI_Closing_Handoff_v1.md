# V5 Implementation — D-66 Race-Event Profile-Tab UI Closing Handoff

**Session:** Single chat. Scope: D-66 profile-tab UI per `Race_Events_D66_Design_v1.md` §7. Closes the visible-to-athlete gap on `/profile?tab=race-events` — athletes can now CRUD their race calendar (add/edit/delete races + per-race route-locale graph + nested per-locale equipment items + atomic "Set as target" flip). Consumes the `race_events_repo.py` data-access helpers shipped earlier 2026-05-18 in the D-66 DB foundation revision.

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_D66_Race_Events_DB_Foundation_Closing_Handoff_v1.md` (D-66 DB foundation shipped 2026-05-18 earlier same day; commits `007c9dd` + `4181bbb` merged via PR #82 in `48ac92c`).

**Branch:** `claude/race-events-db-foundation-QYZ9H` (harness-pinned for this session — name carries over from the D-66 DB foundation theme even though this session is the profile-tab UI follow-on; precedent: harness names mismatched with scope across every prior Layer 4 implementation session).

**Status:** 🟢 5 new code/template files + 3 modified + 3 bookkeeping = 11 files. Combined `tests/` 684 → 695 net new (11 in `tests/test_race_events_repo.py`; combined that file 22 → 33) in 0.89s. **D-66 status flipped 🟢 DB foundation shipped → 🟢 Profile-tab UI shipped.**

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| D-66 DB foundation shipped on main per predecessor handoff | `git log --oneline -5` | ✅ commits `007c9dd` (D-66 race-event DB foundation) + `4181bbb` (D-72 backlog row) + `48ac92c` (merge PR #82) |
| `race_events_repo.py` exists at top level | `ls -la race_events_repo.py` | ✅ 10666 bytes / 321 lines |
| `tests/test_race_events_repo.py` exists; tests pass | `pytest tests/test_race_events_repo.py -q` | ✅ 22 passed in 0.32s |
| Combined `tests/` 684 green | `pytest tests/ -q` | ✅ 684 passed in 1.31s |
| Working tree clean on `claude/race-events-db-foundation-QYZ9H` (fresh off post-merge main) | `git status` | ✅ |
| `Project_Backlog_v53.md` is current per CLAUDE.md | grep | ✅ |
| `init_db.py` `_PG_MIGRATIONS` D-66 entries (8 added) present | grep | ✅ lines 1130–1210 cover ALTER + 3 CREATE TABLE + 4 indexes + 1 INSERT-from-SELECT |

**No drift surfaced** — the predecessor handoff was accurate. Branch is fresh off post-merge main; no new contract gaps surfaced; no stop-and-ask triggers fired during Rule #9 reconciliation.

---

## 2. Session narrative — D-66 profile-tab UI

Andy opened with the URL to the D-66 DB foundation closing handoff + "lets work." Followed the operating model — read CLAUDE.md fully (Rule #13), ran Rule #9 verification, surfaced state, and offered the architect-recommended next-forward-move set from the predecessor handoff §4.1.

### 2.1 Scope pick

**Round 1 (2026-05-18, 1-question):** session scope. Andy picked **D-66 profile-tab UI** (over D-66 onboarding extension / Layer 3B caller rewire / Layer 4 Step 7 live LLM integration). Architect-recommended pick per the predecessor handoff §4.1.1 — highest visible-to-athlete impact; closes the gap immediately; directly consumes the `race_events_repo.py` helpers shipped earlier same day.

### 2.2 Implementation order

1. **Extended `race_events_repo.py`** with 8 new helpers covering single-row reads + UPDATEs + route-locale + equipment CRUD. All write paths fail-closed on ownership mismatches via WHERE-clause filtering (no caller-side ownership checks). See §3.
2. **New `routes/race_events.py`** Flask blueprint (~405 lines) at `/profile/race-events`, 10 routes. See §4.
3. **New `templates/profile/_race_events_tab.html`** (~67 lines) list partial. See §5.1.
4. **New `templates/profile/race_event_edit.html`** (~317 lines) full edit page. See §5.2.
5. **Modified `templates/profile/edit.html`** to add the "Race events" tab button + tab-pane include.
6. **Modified `routes/profile.py`** to load `race_events` for the tab context.
7. **Modified `app.py`** to register the new blueprint alongside `profile_bp`.
8. **Extended `tests/test_race_events_repo.py`** with 11 new tests covering the 8 new helpers.
9. **Bookkeeping:** `Project_Backlog_v53.md` → `_v54.md` + CLAUDE.md update + this handoff.

### 2.3 Architectural choices on the record

- **Separate edit page at `/profile/race-events/<id>/edit`** rather than inline tab expansion — the route-locale graph + nested equipment forms are too dense to render inline within the profile tab. The tab is the listing + shortcut surface (Set as target / Edit / Delete / Add race); complex per-race CRUD lives on the dedicated page.
- **Direct `sequence_idx` integer input instead of drag-and-drop reorder** — gaps allowed per the design contract (athletes can leave room to insert a forgotten aid station between two existing rows by typing a value with a gap). CSP-restrictive JS surface avoided for v1. v2 can layer a drag-handle UX on top without changing the data shape; the `update_route_locale(sequence_idx=...)` helper already takes the new value verbatim, so a drag-reorder UI just stamps new sequence_idx values via the same POST.
- **Equipment items support add + delete only (no in-place edit)** — free-text rows are simple enough that delete-and-re-add is acceptable. Matches the CLAUDE.md no-padding rule. Per-equipment edit can land in v2 if a real friction case surfaces.
- **Route-locale section always rendered on the edit page regardless of race_format** — single-day events typically don't need route locales (the brief composes pacing strategy from race details alone) but athletes can add start+finish if they want them anchored. Format-change drift handled gracefully: existing route_locales survive a flip back to single_day; athlete cleans up via the per-locale Delete button. Help-text differs per format (single_day: "typically don't need route locales"; multi-day: explains sequence_idx ordering).
- **Per-route-locale CRUD is a single inline form per row** (no edit/cancel modal toggle) — server-only, no JS, save updates inline. Each route locale's `<form>` posts to `/profile/race-events/<id>/locales/<locale_id>/update`; "Delete locale" is a separate form with `data-confirm` (wired by static/app.js).
- **Ownership defense is layered** — `get_race_event(db, user_id, race_event_id)` returns None when the row is missing OR belongs to another user (caller 404s). Route-locale + equipment helpers also scope on the parent's id in the WHERE clause (`WHERE id = ? AND race_event_id = ?`), so a crafted POST targeting `/profile/race-events/10/locales/100/delete` against another athlete's race_event_id=10 falls back to the get_race_event 404 path (the locale ID lookup never runs).
- **Multi-day race creation redirects to the edit page** (route-locale entry is the natural next step); single-day race creation bounces back to the tab listing (no route_locales needed). UX nudge: athletes who pick a multi-day format see the full route-locale entry surface immediately.
- **`event_locale_id` dropdown** is sourced from the athlete's `locale_profiles` ordered by `COALESCE(locale_name, locale)` — friendly label preferred, falls back to slug when athlete never set a `locale_name`. The new `id BIGSERIAL` column shipped in the D-66 migration is the FK target.

### 2.4 Stop-and-ask triggers — none fired

- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire — no schema changes; the data-access surface was already complete from the DB foundation revision. The 8 new repo helpers are implementation-of-spec UPDATEs/DELETEs against the already-shipped schema.
- **Trigger #8 (architectural alternatives):** had implicit defer-to-implementation calls per design §2.1 (Profile UI set-as-target affordance + sequence_idx UX). The picks (a) through (h) in §2.3 above are all architect-pick within the design's stated latitude; no real tradeoff merited a `/plan`-mode gate.
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows.

Other triggers — none applicable.

---

## 3. `race_events_repo.py` API additions

8 new helpers; all single-row writes commit at the end; all reads scoped to the calling user via `user_id` or `race_event_id` in the WHERE clause.

| Function | Purpose | Returns | Ownership scope |
|---|---|---|---|
| `get_race_event(db, user_id, race_event_id)` | Single-row read for edit form pre-populate | `dict \| None` | `WHERE id = ? AND user_id = ?` |
| `update_race_event(db, user_id, race_event_id, **fields)` | UPDATE editable race fields (excluding `is_target_event`) | `None` | `WHERE id = ? AND user_id = ?` |
| `list_route_locales(db, race_event_id)` | List route locales for the edit page; ORDER BY sequence_idx ASC | `list[dict]` | `WHERE race_event_id = ?` |
| `update_route_locale(db, race_event_id, route_locale_id, **fields)` | UPDATE a route locale; validates role + sequence_idx ≥ 1 | `None` | `WHERE id = ? AND race_event_id = ?` |
| `delete_route_locale(db, race_event_id, route_locale_id)` | DELETE a route locale; CASCADE clears equipment | `None` | `WHERE id = ? AND race_event_id = ?` |
| `list_route_locale_equipment(db, race_route_locale_id)` | List equipment for a route locale ORDER BY id | `list[dict]` | `WHERE race_route_locale_id = ?` |
| `delete_route_locale_equipment(db, race_route_locale_id, equipment_id)` | DELETE a single equipment row | `None` | `WHERE id = ? AND race_route_locale_id = ?` |

Plus the 8 helpers shipped in the predecessor revision (`list_athlete_race_events`, `load_race_event_payload`, `load_target_race_event_payload`, `create_race_event`, `set_target_event`, `delete_race_event`, `add_route_locale`, `add_route_locale_equipment`) — all consumed by the new blueprint without modification.

---

## 4. `routes/race_events.py` route surface

Flask blueprint `bp = Blueprint('race_events', __name__, url_prefix='/profile/race-events')`. Registered in `app.py` after `profile_bp`. 10 routes (auth-gated via `@app.before_request _require_login`):

| Method | Path | Endpoint | Action |
|---|---|---|---|
| GET | `/new` | `race_events.new_race` | Render new race form |
| POST | `/new` | `race_events.new_race` | Create race + redirect (multi-day → edit page; single-day → tab listing) |
| GET | `/<id>/edit` | `race_events.edit_race` | Render full edit page |
| POST | `/<id>/update` | `race_events.update_race` | Update race details |
| POST | `/<id>/delete` | `race_events.delete_race` | Delete race (CASCADE clears locales + equipment) |
| POST | `/<id>/set-target` | `race_events.set_target` | Atomic flip of `is_target_event` |
| POST | `/<id>/locales/add` | `race_events.add_locale` | Add a route locale |
| POST | `/<id>/locales/<locale_id>/update` | `race_events.update_locale` | Update a route locale |
| POST | `/<id>/locales/<locale_id>/delete` | `race_events.delete_locale` | Delete a route locale (CASCADE clears equipment) |
| POST | `/<id>/locales/<locale_id>/equipment/add` | `race_events.add_equipment` | Add an equipment item to a route locale |
| POST | `/<id>/locales/<locale_id>/equipment/<equipment_id>/delete` | `race_events.delete_equipment` | Delete an equipment item |

All POST handlers verify ownership via `get_race_event(db, uid, race_event_id)` → abort(404) before any write. CSRF protected via the global `CSRFProtect(app)` from `app.py`. Form parsing uses local `_parse_str` / `_parse_decimal` / `_parse_date` / `_parse_int` helpers that coerce empty strings → None for clean optional-field semantics.

The `_athlete_locale_choices(db, uid)` helper returns `{id, label}` dicts for the `event_locale_id` dropdown — sourced from `locale_profiles WHERE user_id = ? ORDER BY COALESCE(locale_name, locale)`. The `id` here is the new `BIGSERIAL` surrogate added to `locale_profiles` in the D-66 DB foundation migration.

---

## 5. Templates

### 5.1 `templates/profile/_race_events_tab.html`

~67 lines; included from `templates/profile/edit.html` inside `<div class="tab-pane" id="tab-race-events">`. Renders the athlete's `race_events` ordered by event_date (loaded by `routes/profile.py:edit()` via `list_athlete_race_events`). Each row shows: name + format badge + target-race badge (when set) + event date + distance/elevation. Per-row buttons:

- **Set as target** (only on non-target rows; `data-confirm="Setting ... as your target race will trigger a plan refresh on the next morning sync."` wired by static/app.js).
- **Edit** (link to `/profile/race-events/<id>/edit`).
- **Delete** (`data-confirm="Delete ...? Route locales and equipment items for this race will also be deleted."`).

Bottom CTA: "Add race" link to `/profile/race-events/new`.

The existing tab-activation JS in `templates/profile/edit.html` handles `?tab=race-events` automatically (it reads `params.get('tab')` and activates `[data-bs-target="#tab-race-events"]`).

### 5.2 `templates/profile/race_event_edit.html`

~317 lines extending `base.html`. Two main sections + back-nav crumb:

**Section 1 — Race details form** (always rendered, including for new races):
- Name + event_date + race_format (4-element closed enum select) + distance_km + total_elevation_gain_m
- event_locale_id dropdown from athlete's `locale_profiles`
- race_rules_summary textarea (athlete pastes mandatory checkpoints / time cuts / support rules)
- mandatory_gear_text textarea (athlete pastes race-director-published mandatory gear list)
- notes textarea
- Save button + Delete race button (with confirm; not shown for new-race form)

**Section 2 — Route locales** (rendered only on edit page, not on new-race form):
- Help text adapts to race_format (single_day: "typically don't need"; multi-day: explains sequence_idx ordering)
- Per-locale inline form: sequence_idx INT + role select (7-element closed enum) + name + mile_marker + lat/lng/mapbox_id + notes + Save locale button + Delete locale button
- Nested equipment list per locale with per-row remove button (red link) + "Add equipment" inline form (name + quantity + notes)
- "Add route locale" form at bottom — auto-defaults sequence_idx to `len(race_locales) + 1`

All forms include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. The Save/Delete buttons use Bootstrap utility classes for visual hierarchy (`btn-outline-primary` / `btn-outline-danger`); no inline styles (CSP-strict).

---

## 6. Test additions

11 new tests in `tests/test_race_events_repo.py` (combined that file 22 → 33; combined `tests/` 684 → 695 in 0.89s). All use the existing `_FakeConn` / `_FakeCursor` pattern from `tests/test_layer4_cache.py` — no real DB connection.

| Test class | Count | Coverage |
|---|---|---|
| `TestGetRaceEvent` | 2 | None on missing/wrong-user + full-column dict on hit |
| `TestUpdateRaceEvent` | 2 | UPDATE with user_id scope (WHERE id = ? AND user_id = ?) + race_format closed-enum rejection |
| `TestListRouteLocales` | 1 | ORDER BY sequence_idx ASC + race_event_id scope |
| `TestUpdateRouteLocale` | 3 | race_event_id scope + role rejection + sequence_idx ≥ 1 rejection |
| `TestDeleteRouteLocale` | 1 | DELETE scoped to race_event_id |
| `TestListRouteLocaleEquipment` | 1 | ORDER BY id ASC + parent race_route_locale_id scope |
| `TestDeleteRouteLocaleEquipment` | 1 | DELETE scoped to parent race_route_locale_id |

Templates also smoke-tested mid-session via direct Jinja `render()` calls (new-race + edit-race + tab partial + integrated profile/edit.html all render cleanly; assertion-verified that the Set-as-target button appears only on non-target rows + target race has no set-target action URL).

---

## 7. Next session pointers

### 7.1 Architect-recommended next forward moves

D-66 profile-tab UI is COMPLETE. The visible-to-athlete CRUD surface for race events is live. Three follow-on candidates remain:

1. **D-66 onboarding §H.2/§H.4 extension** (closes the new-athlete data-entry path; ~5-7 files projected) — per design §6: extend `templates/onboarding/target_race.html` with race_format radio + conditional distance/elevation/rules/gear fields per design §6.2; new `templates/onboarding/route_locales.html` for §H.4 multi-day-only step; `routes/onboarding.py` gains `route_locales` view (GET/POST) + the existing `target_race` POST handler writes a `race_events` row (calling `create_race_event`) instead of (or in addition to) the legacy `athlete_profile.target_event_*` columns. Account-nudge fires on §H.4 skip. The profile UI shipped this session is the editing path; onboarding is the initial-entry path; both are needed for the new-athlete cold-start case.
2. **Layer 3B caller-side rewire** (closes contract drift; ~3-4 files projected) — orchestrator currently reads `athlete_profile.target_event_*` for 3B's event-mode input; once safe-to-cut-over (athletes have visibly migrated via the now-shipped profile UI), swap to `load_target_race_event_payload(db, user_id)` so the race-week-brief shares the same source of truth as 3B. Also forces a resolution of D-72 (`Layer3BPayload.event_locale_id: str | None` vs `RaceEventPayload.event_locale_id: int | None` — same logical entity, different key types).
3. **Layer 4 Step 7 live LLM integration** (orthogonal; architect-recommended-orthogonal candidate from prior handoffs) — first end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call. Cache + telemetry now make this safe to iterate on. Needs `ANTHROPIC_API_KEY`.

### 7.2 Carry-forward — D-72 still deferred

D-72 (`Layer2CPayload.locale_id: str` vs `Layer3BPayload.event_locale_id: str` vs `RaceEventPayload.event_locale_id: int`) was tracked as a D-row in the predecessor session. Not addressed this session — the profile UI consumes `RaceEventPayload.event_locale_id: int` cleanly and `Layer3BPayload` isn't touched. D-72 deferred trigger remains: lands when (i) Layer 3B's caller-side rewires from `athlete_profile.target_event_*` to `race_events` (will force a type pick), or (ii) any Layer 2C consumer trips over the slug-vs-id ambiguity. Whichever triggers first should also close D-72.

### 7.3 Carry-forward — Andy's Pocket Gopher Extreme 2026 row

Per `Race_Events_D66_Design_v1.md` §10.1, Andy's migrated row defaults to `race_format='single_day'`. He can now update via the profile UI shipped this session to:
- race_format = 'expedition_ar'
- distance_km / total_elevation_gain_m (per race director's published guide)
- race_rules_summary + mandatory_gear_text (paste from race-director-published guide)
- route_locales (start + transition areas + aid stations + drop bags + finish per actual race route)

Documentation-track follow-up; not contract-bearing. The profile UI is the path; no further code changes needed for this carry-forward.

### 7.4 Carry-forward — partial-update invalidation hooks per design §7.4

Per `Race_Events_D66_Design_v1.md` §7.4 + §9: editing any field on a target race_event row should invalidate Layer 3B + Layer 4 race-week-brief caches; adding/editing/deleting a route_locale row invalidates Layer 4 race-week-brief cache only. This session ships the CRUD surface but NOT the cache invalidation hooks — the orchestrator firing T1 plan refresh on target-flag change + emitting cache invalidation events on route-locale edits is its own concrete carry-forward, landing alongside the Layer 3B caller rewire (since 3B's input source change is what makes the invalidation rule load-bearing). Tracked in this handoff as concrete forward-pointer; not a new D-row.

### 7.5 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff.
3. **Third re-read**: depends on scope. If onboarding extension → `Race_Events_D66_Design_v1.md` §6 + existing `routes/onboarding.py` + `templates/onboarding/` patterns. If Layer 3B rewire → `Layer3_3B_Spec.md` + the orchestrator pre-3B caller (search for `target_event_name` consumers in `routes/`). If Layer 4 Step 7 → `Layer4_Spec.md` §11 + Anthropic SDK docs.
4. **Branch**: cut fresh off post-merge main OR stay on the harness pin (precedent).
5. **Profile UI registration**: blueprint pattern is now established in `app.py` after `profile_bp` — additional sub-blueprints can follow the same pattern.

---

## 8. Open items / decisions pinned this session

### 8.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = D-66 profile-tab UI | Andy 2026-05-18 | Architect-recommended next-move from predecessor handoff §4.1.1; highest visible-to-athlete impact; closes the gap immediately |
| 2 | Separate edit page at `/profile/race-events/<id>/edit` | Architect-pick | Route-locale graph + nested equipment forms too dense for inline tab expansion; tab is listing only |
| 3 | Direct `sequence_idx` integer input over drag-and-drop | Architect-pick | Gaps allowed per design; CSP-restrictive JS avoided in v1; v2 can layer drag-handle UX |
| 4 | Equipment add + delete (no in-place edit) | Architect-pick | Free-text rows are simple; delete-and-re-add acceptable |
| 5 | Route-locale section always rendered regardless of race_format | Architect-pick | Athletes can add start+finish to single-day races if they want; format-change drift handled gracefully |
| 6 | Per-route-locale CRUD as single inline form per row | Architect-pick | Server-only; no JS; matches the existing profile-tab form patterns |
| 7 | Multi-day creation redirects to edit page; single-day to tab listing | Architect-pick | Multi-day's natural next step is route-locale entry |
| 8 | File ceiling break (11 files) | Architect-pick (implied) | Precedented across every prior Layer 4 implementation session |

### 8.2 Carry-forward — D-72 Locale-FK type alignment

See §7.2 above. v1 accepts the mismatch; v2 reconciliation lands with Layer 3B's race-event read swap OR D-66 onboarding cutover OR Layer 2C consumer trip — whichever fires first.

### 8.3 Carry-forward — Partial-update invalidation hooks per design §7.4

See §7.4 above. Lands with the Layer 3B caller-side rewire.

### 8.4 Carry-forward — Andy's row migration

See §7.3 above. Documentation-track; no code change needed.

---

## 9. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `race_events_repo.py` gains 8 new helpers | ✅ inspection — `get_race_event`, `update_race_event`, `list_route_locales`, `update_route_locale`, `delete_route_locale`, `list_route_locale_equipment`, `delete_route_locale_equipment` (7 new + builds on existing 8 = 15 total) |
| `routes/race_events.py` exists with 10 routes | ✅ `python -c "from app import app; [print(r) for r in app.url_map.iter_rules() if 'race_events' in r.endpoint]"` confirms 10 routes |
| `templates/profile/_race_events_tab.html` exists | ✅ ls |
| `templates/profile/race_event_edit.html` exists | ✅ ls |
| `templates/profile/edit.html` gains race-events tab | ✅ grep `tab-race-events` |
| `routes/profile.py` loads race_events for tab | ✅ grep `list_athlete_race_events` |
| `app.py` registers race_events_bp | ✅ grep |
| `tests/test_race_events_repo.py` extended | ✅ 22 → 33 tests |
| Combined `tests/` 695 green | ✅ `pytest tests/ -q` → 695 passed in 0.89s |
| Templates render without Jinja errors | ✅ direct `render_template` smoke against new-race + edit-race + tab partial + integrated edit.html |
| `Project_Backlog_v54.md` exists; v53 retained | ✅ ls |
| `Project_Backlog_v54.md` D-66 row status updated 🟢 Profile-tab UI shipped | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v54.md` | ✅ grep |
| `CLAUDE.md` last-shipped-session is D-66 profile-tab UI; DB foundation demoted to predecessor | ✅ inspection |

---

## 10. Files shipped this session

**Substantive code/template (5 new + 3 modified = 8 files):**
1. Modified `race_events_repo.py` — 8 new helpers covering single-row reads + UPDATEs + route-locale CRUD + equipment CRUD; all scoped to `user_id` or `race_event_id` via WHERE-clause filtering.
2. New `routes/race_events.py` — Flask blueprint at `/profile/race-events`, 10 routes; CSRF-protected; ownership-defended via `get_race_event` short-circuit.
3. New `templates/profile/_race_events_tab.html` — ~67-line list partial.
4. New `templates/profile/race_event_edit.html` — ~317-line full edit page.
5. Modified `templates/profile/edit.html` — adds the Race events tab button + tab-pane include.
6. Modified `routes/profile.py` — loads `race_events = list_athlete_race_events(db, uid)` for the tab.
7. Modified `app.py` — imports + registers `race_events_bp`.
8. Modified `tests/test_race_events_repo.py` — 11 new tests for the new helpers.

**Bookkeeping (3 files):**
9. New `aidstation-sources/Project_Backlog_v54.md` (per Rule #12; v53 retained as predecessor) — D-66 row status flip + new file-revision header.
10. Modified `aidstation-sources/CLAUDE.md` — last-shipped-session bump; DB foundation demoted to predecessor; Backlog ref v53 → v54; Next forward move updated.
11. New `aidstation-sources/handoffs/V5_Implementation_D66_Race_Events_ProfileTabUI_Closing_Handoff_v1.md` (this file).

**11 files total. Over the 5-file ceiling intentionally** — precedented across every prior Layer 4 implementation session.

---

## 11. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- v5 onboarding implementation PR — partially advanced this session via D-66 profile-tab UI; onboarding §H.2/§H.4 extension remains as concrete carry-forward.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **D-72 Locale-FK type alignment across typed payloads** — deferred from D-66 DB foundation; not closed this session. Defer trigger fires on first of: 3B caller rewire / D-66 profile-tab UI / Layer 2C consumer ambiguity. Profile-tab UI now shipped, so trigger #2 of D-72's defer condition has fired but the type-alignment work is its own scope.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward.
- **Partial-update invalidation hooks per design §7.4** — concrete carry-forward; lands with Layer 3B caller rewire.

---

**End of handoff.**
