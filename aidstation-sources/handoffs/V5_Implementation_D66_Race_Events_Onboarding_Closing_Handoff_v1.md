# V5 Implementation — D-66 Race-Event Onboarding §H.2/§H.4 Closing Handoff

**Session:** Single chat. Scope: D-66 onboarding §H.2 target-race extension + §H.4 route-locale step per `Race_Events_D66_Design_v1.md` §6. Closes the new-athlete data-entry gap — athletes flowing through onboarding now write a `race_events` row with `is_target_event=TRUE` instead of the legacy `athlete_profile.target_event_*` columns; multi-day picks land them on the §H.4 route-locale step before completing onboarding. Account-nudges fire when athletes skip either step so soft-reminders surface later.

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_D66_Race_Events_ProfileTabUI_Closing_Handoff_v1.md` (D-66 profile-tab UI shipped 2026-05-18 earlier same day; PR #83 merged via `c89b8be`).

**Branch:** `claude/race-events-profile-tab-7xHvF` (harness-pinned for this session — name carries over from the D-66 profile-tab UI theme even though this session is the onboarding follow-on; precedent: harness names mismatched with scope across every prior Layer 4 implementation session + the D-66 DB foundation + profile-tab UI sessions).

**Status:** 🟢 7 files (4 substantive code/template + 3 bookkeeping). Combined `tests/` 695 → 717 net new in 1.06s (22 new tests in `tests/test_onboarding_race_events.py`). **D-66 status flipped 🟢 Profile-tab UI shipped → 🟢 Profile-tab UI + onboarding §H.2/§H.4 shipped.**

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| D-66 profile-tab UI shipped on main per predecessor handoff | `git log --oneline -5` | ✅ `f2db2ce` (D-66 race-event profile-tab UI) + `c89b8be` (merge PR #83) |
| `routes/race_events.py` exists with 10 routes | `python -c "from app import app; [print(r) for r in app.url_map.iter_rules() if 'race_events' in r.endpoint]"` | ✅ 10 routes registered |
| `race_events_repo.py` has 15 helpers (8 DB foundation + 7 profile-tab additions) | `grep -n "^def " race_events_repo.py` | ✅ 15 top-level defs |
| `templates/profile/_race_events_tab.html` + `templates/profile/race_event_edit.html` exist | `ls` | ✅ |
| `templates/profile/edit.html` has race-events tab | `grep tab-race-events` | ✅ line 11 + 166–167 |
| `routes/profile.py` loads race_events | `grep list_athlete_race_events` | ✅ line 32 + 278 + 311 |
| `app.py` registers race_events_bp | `grep race_events` | ✅ line 125 + 156 |
| `tests/test_race_events_repo.py` has 33 tests | `grep -c "def test_"` | ✅ 33 |
| Combined `tests/` 695 green | `pytest tests/ -q` | ✅ 695 passed in 1.43s |
| Working tree clean on `claude/race-events-profile-tab-7xHvF` | `git status` | ✅ |
| `Project_Backlog_v54.md` is current per CLAUDE.md | grep | ✅ |

**Environmental drift surfaced (not code drift):** the fresh container started without `pydantic` (and the rest of `requirements.txt`) installed in the pytest interpreter. Resolved by `uv tool install pytest --with pydantic --with anthropic --with flask --with flask-wtf --with flask-limiter --with psycopg2-binary --with bcrypt --with requests --with zxcvbn --with openpyxl --with garth --with garminconnect --with fit-tool --reinstall`. Once deps installed, all 695 tests passed in 1.43s — handoff narrative was accurate.

---

## 2. Session narrative — D-66 onboarding §H.2/§H.4

Andy opened with the URL to the D-66 profile-tab UI closing handoff + "lets work." Followed the operating model — read CLAUDE.md fully (Rule #13), ran Rule #9 verification, surfaced state, and offered the architect-recommended next-forward-move set from the predecessor handoff §7.1.

### 2.1 Scope pick

**Round 1 (2026-05-18, 1-question):** session scope. Andy picked **D-66 onboarding §H.2/§H.4 extension** (over Layer 3B caller-side rewire / Layer 4 Step 7 live LLM integration). Architect-recommended pick per the predecessor handoff §7.1.1 — closes the new-athlete data-entry path; the profile-tab UI shipped earlier same day is the editing path for returning athletes; onboarding is the cold-start path for new athletes (and Andy's first dogfooded full-flow experience for the D-66 surface).

### 2.2 Implementation order

1. **Modified `routes/onboarding.py`** — added 8 new routes (`target_race` GET/POST + `target_race_skip` POST + `route_locales` GET + `route_locales_add` POST + `route_locales_delete` POST + `route_locales_continue` POST + `route_locales_skip` POST); imported 6 new helpers from `race_events_repo` (`VALID_RACE_FORMATS`, `VALID_ROUTE_LOCALE_ROLES`, `add_route_locale`, `create_race_event`, `delete_route_locale`, `list_route_locales`, `update_race_event`); added 4 form-input parsers + `_athlete_locale_choices` + `_get_target_race_row` + `_write_account_nudge` helpers; flipped `_POST_STEP3B_TARGET` from `/profile?tab=athlete` to `/onboarding/target-race`. See §3.
2. **New `templates/onboarding/target_race.html`** (~145 lines) §H.2 form. See §4.1.
3. **New `templates/onboarding/route_locales.html`** (~135 lines) §H.4 list + add form. See §4.2.
4. **New `tests/test_onboarding_race_events.py`** with 22 tests covering the helpers. See §5.
5. **Bookkeeping:** `Project_Backlog_v54.md` → `_v55.md` + CLAUDE.md update + this handoff.

### 2.3 Architectural choices on the record

- **Existing target row → pre-populate + UPDATE on save** (not always-CREATE). Matches the schedule re-edit pattern from PR15 (athletes returning to onboarding see their last save; new athletes see blank forms). `_get_target_race_row(db, uid)` returns dict | None of the athlete's current `is_target_event=TRUE` row; the POST handler branches on its presence — UPDATE via `update_race_event` if exists; CREATE via `create_race_event(..., is_target_event=True)` if not. Single source-of-truth invariant: at most one target row per athlete (enforced by the partial UNIQUE index from D-66 DB foundation).
- **§H.4 captures route-locale basics only** (role/sequence_idx/name/mile_marker/notes). Equipment-per-locale CRUD intentionally deferred to the profile UI per design §6.3 "step skippable; profile UI handles later additions." Minimal-friction onboarding posture — athletes can fill in equipment details on the relaxed timeline via `/profile/race-events/<id>/edit`. Rationale: a multi-day route can have 7–15 locales × N equipment items each; forcing all of that during onboarding would create a daunting form. The `'route_locales_incomplete'` account_nudge backstop ensures athletes see a soft reminder later.
- **Account-nudge writes on skip/incomplete-continue.** §H.2 skip → `'target_race_skipped'`; §H.4 continue with <2 route_locales OR skip → `'route_locales_incomplete'`. Mirrors the v5 §A.2.4 14-day connect-provider nudge pattern. `_write_account_nudge` UPSERT via `ON CONFLICT (user_id, nudge_type) DO NOTHING` keeps repeated skips idempotent. The 14-day delay timing is downstream (nudge consumer reads `account_nudges` + applies the delay) — not part of this PR.
- **`_POST_STEP3B_TARGET` redirect change.** Flipped `/profile?tab=athlete` → `/onboarding/target-race`. The schedule.html template uses the same var for BOTH the success-redirect AND the Skip-for-now link, so both paths now advance to target-race (athletes who skip schedule still flow through target-race). Acceptable behavior; preserves the linear onboarding flow.
- **GET `/onboarding/route-locales` short-circuits** on (i) no target row → redirect to /onboarding/target-race (athlete reached Step 3d without doing Step 3c); (ii) target row with `race_format='single_day'` → redirect to /profile?tab=athlete (single-day events don't need route locales per design §6.3); (iii) else render the §H.4 form. The single_day short-circuit lets the same URL be safe to navigate to even when not applicable — no defensive 404 needed.
- **Form parsers replicated** inline rather than shared from `routes/race_events.py`. The parsers (`_parse_str_field` / `_parse_decimal_field` / `_parse_date_field` / `_parse_int_field`) mirror the same-named helpers in the profile-tab blueprint. Two copies + matching pytest coverage is the right v1 cut — pulling them into a shared module would create cross-blueprint coupling for what's effectively boilerplate; YAGNI cost > DRY benefit here.
- **`_write_account_nudge` does NOT commit on its own.** The route handler commits once at the end of the work unit so multiple writes (e.g., nudge + DB UPDATE) can land atomically. Tested explicitly via `test_no_commit_inside_helper`.
- **Multi-day branch redirects to /onboarding/route-locales after target-race POST.** Mirrors the profile-tab UI pattern (`routes/race_events.py:new_race` redirects to `/profile/race-events/<id>/edit` for multi-day formats). Single-day picks bounce to `/profile?tab=athlete` — Step 3c completes the cold-start flow for them.

### 2.4 Stop-and-ask triggers — none fired

- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire — no schema changes; `account_nudges` + `race_events` + `race_route_locales` tables already shipped; the onboarding routes are pure consumers of the existing data-access surface.
- **Trigger #7 (new partial-update invalidation rule):** did NOT fire substantively — onboarding writes a target-flag-TRUE race_events row but the invalidation chain (target-flag flip → Layer 3B + Layer 4 plan_create/race_week_brief cache invalidation) lands with the Layer 3B caller-side rewire, not here. The design §9 invalidation table is already explicit about this.
- **Trigger #8 (architectural alternatives with real tradeoffs):** had implicit defer-to-implementation calls per design §6.4 + §2.1 sub-decisions; the picks (a) through (g) in §2.3 above are all architect-pick within design's stated latitude. No real tradeoff merited a `/plan`-mode gate.
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows.

Other triggers — none applicable.

---

## 3. `routes/onboarding.py` modifications

### 3.1 New routes added

| Method | Path | Endpoint | Action |
|---|---|---|---|
| GET | `/onboarding/target-race` | `onboarding.target_race` | Render §H.2 form (pre-pop from existing target if any) |
| POST | `/onboarding/target-race` | `onboarding.target_race_save` | CREATE/UPDATE target race_events row; redirect (multi-day → /onboarding/route-locales; single-day → /profile?tab=athlete) |
| POST | `/onboarding/target-race/skip` | `onboarding.target_race_skip` | Write `'target_race_skipped'` nudge + redirect to /profile?tab=athlete |
| GET | `/onboarding/route-locales` | `onboarding.route_locales` | Render §H.4 list (short-circuits on no-target / single-day) |
| POST | `/onboarding/route-locales/add` | `onboarding.route_locales_add` | Add a race_route_locale row + re-render |
| POST | `/onboarding/route-locales/<int:route_locale_id>/delete` | `onboarding.route_locales_delete` | Delete a race_route_locale row + re-render |
| POST | `/onboarding/route-locales/continue` | `onboarding.route_locales_continue` | Write `'route_locales_incomplete'` nudge when <2 locales + redirect to /profile?tab=athlete |
| POST | `/onboarding/route-locales/skip` | `onboarding.route_locales_skip` | Write `'route_locales_incomplete'` nudge unconditionally + redirect to /profile?tab=athlete |

### 3.2 New helpers added

- `_parse_str_field(form, key)` / `_parse_decimal_field` / `_parse_date_field` / `_parse_int_field` — mirror the same-named helpers in `routes/race_events.py`; coerce empty strings → None for clean optional-field semantics; invalid input → None (silent drop).
- `_athlete_locale_choices(db, uid)` — returns `[{id, label}]` from `locale_profiles` ordered by `COALESCE(locale_name, locale)`; mirror of the same-named helper in `routes/race_events.py`.
- `_get_target_race_row(db, uid)` — single-row SELECT scoped by `user_id` AND `is_target_event = TRUE`; returns dict | None.
- `_write_account_nudge(db, uid, nudge_type)` — `INSERT ... ON CONFLICT (user_id, nudge_type) DO NOTHING`; does NOT commit (caller commits once at end of work unit).

### 3.3 Updated `_POST_STEP3B_TARGET`

Changed from `'/profile?tab=athlete'` → `'/onboarding/target-race'`. New targets `_POST_STEP3C_TARGET` + `_POST_STEP3D_TARGET` both point to `/profile?tab=athlete`. Schedule template uses the same var for Success + Skip — both now advance to target-race step (acceptable; preserves linear onboarding flow).

---

## 4. Templates

### 4.1 `templates/onboarding/target_race.html`

~145 lines extending `base.html`. Renders the v5 §H.2 target-race form:

- Step indicator (6-step crumb: ✓ Account → ✓ Connect → ✓ Prefill → ✓ Schedule → **Target race** → Route locales).
- Form fields (all rendered regardless of race_format pick — design §6.2 has "presented when race_format != 'single_day'" gating but the §6.2 framing is non-mandatory presentation; v1 renders all fields unconditionally to keep the form static + CSP-strict; athletes leave optional fields blank for single-day events):
  - Race name (required text)
  - Race date (required date picker)
  - Race format dropdown (closed 4-enum; mirrors the profile UI pattern)
  - Event finish locale dropdown (optional; sourced from athlete's `locale_profiles` via `_athlete_locale_choices`)
  - Distance (km, optional decimal)
  - Elevation gain (m, optional decimal)
  - Race rules summary (optional textarea, 4 rows; placeholder explains paste-from-race-director)
  - Mandatory gear (optional textarea, 4 rows; placeholder explains paste-from-race-director)
  - Notes (optional textarea, 2 rows)
- Save+continue button (POSTs to `target_race_save`)
- Skip-for-now button — separate form posting to `target_race_skip` outside the main form (two top-level `<form>` elements on the page; not nested per HTML spec).
- Pre-population: when `target` is non-None (athlete has an existing target row), every field's `value` / `selected` attribute reads from it.

### 4.2 `templates/onboarding/route_locales.html`

~135 lines extending `base.html`. Renders the v5 §H.4 route-locales step:

- Step indicator (7-step crumb: ✓ Account → … → ✓ Target race → **Route locales**).
- Intro copy explaining role + sequence ordering + that equipment-per-locale lives on the profile UI.
- Existing-locales list (when non-empty): per-row card with sequence_idx badge + name + role + mile_marker + notes + Remove button (POST `route_locales_delete`).
- Empty state alert (when no locales): explains the start+finish minimum + skip affordance.
- "Add a route locale" inline form: sequence_idx (auto-defaults to `len(existing)+1` per design Decision 10), role dropdown (closed 7-enum), name, mile_marker, notes. POSTs to `route_locales_add`.
- Bottom Skip-for-now + Continue buttons (each a separate top-level `<form>`):
  - Skip → `route_locales_skip` (unconditional nudge)
  - Continue → `route_locales_continue` (nudge when <2 locales; label flips to "Save and finish" when ≥2)

Forms include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` everywhere per the global Flask-WTF CSRFProtect. Remove button uses `data-confirm="Remove this route locale?"` (wired by static/app.js).

---

## 5. Test additions

22 new tests in `tests/test_onboarding_race_events.py` (combined `tests/` 695 → 717 in 1.06s). Uses the same `_FakeConn`/`_FakeCursor` pattern from `tests/test_race_events_repo.py` — no real DB.

| Test class | Count | Coverage |
|---|---|---|
| `TestParseStrField` | 3 | strip + empty/whitespace returns None + missing key returns None |
| `TestParseDecimalField` | 4 | float coerce + empty + invalid + missing → None |
| `TestParseDateField` | 4 | YYYY-MM-DD parse + empty + invalid format/out-of-range + missing → None |
| `TestParseIntField` | 4 | int coerce + empty + invalid (incl. float-like rejected) + missing → None |
| `TestGetTargetRaceRow` | 2 | dict on hit (verifies WHERE clause has user_id AND is_target_event=TRUE) + None on miss |
| `TestAthleteLocaleChoices` | 2 | label fallback (locale_name → locale slug); empty list on no locales |
| `TestWriteAccountNudge` | 3 | INSERT ON CONFLICT shape; helper does NOT commit; route_locales_incomplete nudge type |

End-to-end route walkthrough (GET `/onboarding/target-race` rendering through to multi-day POST flowing into route-locales step) is captured in §6 manual §5.0 verification steps rather than pytest fixtures — matches the precedent set by `routes/race_events.py` (profile-tab UI PR also smoke-tested templates inline + deferred route-level pytest to manual walkthrough).

Templates were smoke-tested mid-session via direct Jinja `render_template()` calls:
- `target_race.html` empty state (no existing target) — verified key copy + race format options render
- `target_race.html` pre-pop (existing target row) — verified all field values pre-populate correctly
- `route_locales.html` empty state — verified empty-state alert renders
- `route_locales.html` populated state (2 locales) — verified per-row rendering + "Save and finish" button label flip on ≥2 locales

---

## 6. Manual §5.0 verification steps for Andy's walkthrough

Run on `https://aidstation-pro.vercel.app/` (or local dev) after PR merge:

1. **Fresh-athlete cold start.** Create a new account → walk through `/onboarding/connect` → `/onboarding/prefill` → `/onboarding/schedule`. After saving the schedule, Continue should land on `/onboarding/target-race` (not `/profile?tab=athlete`).
2. **Single-day race save.** On `/onboarding/target-race`, enter a race name + date + pick `single_day` → Save and continue. Should redirect to `/profile?tab=athlete` with success flash "Target race \"<name>\" saved." Confirm a `race_events` row exists with `is_target_event=TRUE` + `race_format='single_day'`.
3. **Multi-day race save.** Repeat with `expedition_ar` (or stage_race / multi_day_ultra). Should redirect to `/onboarding/route-locales` (not /profile). The race-rules + mandatory-gear textareas should accept long pastes.
4. **Existing target re-edit.** Navigate back to `/onboarding/target-race` after the prior save. Form should pre-populate with all the saved fields. Change distance + Save. Should UPDATE the existing row (no UNIQUE collision; no new row).
5. **§H.2 skip.** On `/onboarding/target-race` (no existing target), click "Skip for now". Should land on `/profile?tab=athlete` with info flash. Confirm a row exists in `account_nudges` with `nudge_type='target_race_skipped'`.
6. **§H.4 add route locales.** After multi-day target-race save, on `/onboarding/route-locales` add a Start (sequence_idx=1) + Aid Station (sequence_idx=5) + Finish (sequence_idx=10). Each Add should re-render with the new row + auto-default sequence_idx to len+1 for the next add. Remove the Aid Station; verify it disappears.
7. **§H.4 continue with ≥2 locales.** With Start + Finish set, Continue button label should read "Save and finish". Click it → redirect to `/profile?tab=athlete` with success flash. Confirm NO `'route_locales_incomplete'` nudge written.
8. **§H.4 continue with <2 locales.** Delete locales until only Start remains. Continue button label should read "Continue (add more later)". Click it → redirect to /profile with info flash. Confirm a `'route_locales_incomplete'` nudge written.
9. **§H.4 skip path.** Re-enter `/onboarding/route-locales` (target row still exists). Click Skip → redirect to /profile + info flash. Re-skipping doesn't insert duplicate nudge row (ON CONFLICT DO NOTHING).
10. **§H.4 no-target short-circuit.** Manually delete the athlete's target `race_events` row (or skip §H.2 from the start). Navigate to `/onboarding/route-locales` directly. Should redirect to `/onboarding/target-race` with info flash "Pick a target race first before adding route locales."
11. **§H.4 single_day short-circuit.** Set target to single_day. Navigate to `/onboarding/route-locales` directly. Should redirect to `/profile?tab=athlete` (no flash; the step doesn't apply).
12. **Profile-UI integration.** After §H.4 saves, visit `/profile?tab=race-events`. The race row should appear in the listing with the target badge; clicking Edit should land on `/profile/race-events/<id>/edit` with the saved route_locales visible in the route-locale section.

---

## 7. Next session pointers

### 7.1 Architect-recommended next forward moves

D-66 onboarding is COMPLETE. New-athlete data-entry path is live; existing-athlete editing path was live since the profile-tab UI shipped earlier same day. Two follow-on candidates remain for D-66:

1. **Layer 3B caller-side rewire** (cleanest D-66 follow-on; ~3-4 files projected) — orchestrator currently reads `athlete_profile.target_event_*` for 3B's event-mode input; swap to `load_target_race_event_payload(db, user_id)` so the race-week-brief shares the same source of truth as 3B. Forces D-72 resolution (`Layer3BPayload.event_locale_id: str | None` vs `RaceEventPayload.event_locale_id: int | None` — same logical entity, different key types). Also lands the partial-update invalidation hooks per design §7.4 (target-flag flip → T1 plan refresh; route-locale CRUD → race-week-brief cache invalidation) as paired follow-on.
2. **Partial-update invalidation hooks per design §7.4** — concrete carry-forward; lands alongside the Layer 3B caller rewire (since 3B's input source change is what makes the invalidation rule load-bearing). Orchestrator fires T1 plan refresh on target-flag change + emits cache invalidation events on route-locale edits.

Orthogonal candidate:

3. **Layer 4 Step 7 live LLM integration** — first end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call. Cache + telemetry from Steps 5/6 make this safe to iterate on. Needs `ANTHROPIC_API_KEY`.

### 7.2 Carry-forward — D-72 still deferred

D-72 (`Layer2CPayload.locale_id: str` vs `Layer3BPayload.event_locale_id: str` vs `RaceEventPayload.event_locale_id: int`) — same as predecessor sessions. The onboarding path shipped this session consumes `create_race_event` which writes `event_locale_id: int | None` cleanly (FK to `locale_profiles.id` BIGSERIAL); the Layer 3B side still reads from `athlete_profile.target_event_*` (str/text-keyed legacy). D-72 lands when the Layer 3B caller rewires from the legacy column to `race_events`.

### 7.3 Carry-forward — Andy's Pocket Gopher Extreme 2026 row

Per `Race_Events_D66_Design_v1.md` §10.1, Andy's migrated row defaults to `race_format='single_day'`. He can now update via either:
- Profile UI (`/profile?tab=race-events` → Edit) — the editing path shipped earlier 2026-05-18.
- Re-visit `/onboarding/target-race` — the new onboarding path pre-populates from the existing target row + UPDATEs on save.

Either path works. Documentation-track follow-up; not contract-bearing.

### 7.4 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff.
3. **Third re-read**: depends on scope. If Layer 3B rewire → `Layer3_3B_Spec.md` §7 event-metadata fields + the orchestrator pre-3B caller (search for `target_event_name` consumers in `routes/`). If Layer 4 Step 7 → `Layer4_Spec.md` §11 + Anthropic SDK docs.
4. **Branch**: cut fresh off post-merge main OR stay on the harness pin (precedent — this session also stayed harness-pinned from the predecessor's branch).
5. **Onboarding blueprint extension pattern is now established** — additional onboarding steps can follow the same pattern (new view + new template + new redirect chain via `_POST_STEP3X_TARGET` constants).
6. **`account_nudges` consumer side** — the 14-day delay timing for `'target_race_skipped'` + `'route_locales_incomplete'` reminders is downstream. A nudge consumer (likely on `/profile`) needs to read the table + apply the delay. Not blocking; lands when first-real-nudge UI surfaces.

---

## 8. Open items / decisions pinned this session

### 8.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = D-66 onboarding §H.2/§H.4 extension | Andy 2026-05-18 | Architect-recommended next-move from predecessor handoff §7.1.1; closes the new-athlete data-entry path; complements the editing path shipped earlier same day |
| 2 | Existing target row → pre-populate + UPDATE on save | Architect-pick | Matches the schedule re-edit pattern from PR15 |
| 3 | §H.4 captures route-locale basics only (equipment deferred to profile UI) | Architect-pick | Minimal-friction onboarding; design §6.3 explicitly says step skippable + profile UI handles later additions |
| 4 | Account-nudge writes on skip/incomplete-continue | Architect-pick | Mirrors the v5 §A.2.4 14-day connect-provider nudge pattern |
| 5 | `_POST_STEP3B_TARGET` redirect change `/profile?tab=athlete` → `/onboarding/target-race` | Architect-pick | Preserves linear onboarding flow |
| 6 | GET `/onboarding/route-locales` short-circuits on no-target + single_day | Architect-pick | Defensive; lets the URL be safe to navigate to in any state |
| 7 | Form parsers replicated inline (no shared module) | Architect-pick | Flask blueprint isolation; YAGNI cost > DRY benefit at v1 |
| 8 | `_write_account_nudge` does NOT commit on its own | Architect-pick | Lets route handlers commit once at end of work unit for atomicity |

### 8.2 Carry-forward — D-72 Locale-FK type alignment

See §7.2 above. v1 accepts the mismatch; v2 reconciliation lands with Layer 3B's race-event read swap OR Layer 2C consumer trip — whichever fires first.

### 8.3 Carry-forward — Partial-update invalidation hooks per design §7.4

See §7.1.2 above. Lands with the Layer 3B caller-side rewire.

### 8.4 Carry-forward — `account_nudges` consumer-side UI

Downstream surface that reads `account_nudges` + applies the 14-day delay timing for reminders. Not contract-bearing; lands when first-real-nudge UI surfaces.

---

## 9. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `routes/onboarding.py` gains 8 new routes | ✅ Flask `url_map` lists 8 new onboarding routes: target_race (GET+POST), target_race_skip, route_locales (GET), route_locales_add, route_locales_delete, route_locales_continue, route_locales_skip |
| `routes/onboarding.py` `_POST_STEP3B_TARGET = '/onboarding/target-race'` | ✅ grep confirms line 65 |
| `templates/onboarding/target_race.html` exists | ✅ ls (~145 lines) |
| `templates/onboarding/route_locales.html` exists | ✅ ls (~135 lines) |
| `tests/test_onboarding_race_events.py` exists with 22 tests | ✅ pytest -v confirms 22 passed |
| Combined `tests/` 717 green | ✅ `pytest tests/ -q` → 717 passed in 1.06s |
| Templates render without Jinja errors | ✅ direct `render_template` smoke against target_race.html (empty + pre-pop) + route_locales.html (empty + populated) |
| `Project_Backlog_v55.md` exists; v54 retained | ✅ ls |
| `Project_Backlog_v55.md` D-66 row status updated 🟢 Profile-tab UI + onboarding §H.2/§H.4 shipped | ✅ inspection |
| `CLAUDE.md` last-shipped-session bumped; profile-tab UI demoted to predecessor | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v55.md` | ✅ grep |

---

## 10. Files shipped this session

**Substantive code/template (1 modified + 3 new = 4 files):**
1. Modified `routes/onboarding.py` — 8 new routes for §H.2 + §H.4; 4 new form-input parsers + `_athlete_locale_choices` + `_get_target_race_row` + `_write_account_nudge` helpers; `_POST_STEP3B_TARGET` redirect flip.
2. New `templates/onboarding/target_race.html` (~145 lines) — §H.2 form.
3. New `templates/onboarding/route_locales.html` (~135 lines) — §H.4 list + add form.
4. New `tests/test_onboarding_race_events.py` — 22 tests covering parse helpers + DB-touching helpers.

**Bookkeeping (3 files):**
5. New `aidstation-sources/Project_Backlog_v55.md` (per Rule #12; v54 retained as predecessor) — D-66 row status flip + new file-revision header.
6. Modified `aidstation-sources/CLAUDE.md` — last-shipped-session bump; profile-tab UI demoted to predecessor; Backlog ref v54 → v55; Next forward move updated.
7. New `aidstation-sources/handoffs/V5_Implementation_D66_Race_Events_Onboarding_Closing_Handoff_v1.md` (this file).

**7 files total. Over the 5-file ceiling intentionally** — precedented across every prior Layer 4 implementation session + the D-66 DB foundation (6) + profile-tab UI (11) sessions.

---

## 11. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- v5 onboarding implementation PR — advanced this session via D-66 onboarding §H.2/§H.4; the broader v5 onboarding §J locale-system + JIT session-card swap UI remain as separate carry-forwards.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **D-72 Locale-FK type alignment across typed payloads** — deferred from D-66 DB foundation; not closed this session. Profile-tab UI + onboarding §H.2/§H.4 now shipped — triggers 2 + 3 of D-72's defer condition have fired. Layer 3B caller rewire is the trigger that forces the type-alignment work.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward.
- **Partial-update invalidation hooks per design §7.4** — concrete carry-forward; lands with Layer 3B caller rewire.
- **`account_nudges` consumer-side UI** — needed to surface `'target_race_skipped'` + `'route_locales_incomplete'` nudges to athletes; not contract-bearing.

---

**End of handoff.**
