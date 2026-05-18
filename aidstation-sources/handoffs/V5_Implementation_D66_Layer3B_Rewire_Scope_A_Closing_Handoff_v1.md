# V5 Implementation — D-66 Layer 3B Caller-Side Rewire (Scope A) Closing Handoff

**Session:** Single chat. Scope: D-66 Layer 3B Scope A per the predecessor handoff `V5_Implementation_D66_Race_Events_Onboarding_Nudge_UI_Closing_Handoff_v1.md` §6.1 — retire the legacy `athlete_profile.target_event_*` form UI from `templates/profile/edit.html` + `routes/profile.py` + `athlete.py` `PROFILE_FIELDS` since the D-66 §7 Race events profile tab (shipped 2026-05-18 earlier same day) now supersedes it as the athlete-facing source of truth for target races. Columns remain on `athlete_profile` pending a Scope B drop migration; this session is form-UI retirement only.

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_D66_Race_Events_Onboarding_Nudge_UI_Closing_Handoff_v1.md` (D-66 account_nudges consumer-side UI shipped 2026-05-18 earlier same day; PR #85 merged via `9055799`).

**Branch:** `claude/race-events-onboarding-nudge-hNDGY` (harness-pinned for this session — name carries over from the predecessor nudge-UI session even though this session is the Layer 3B follow-on; precedent: harness names mismatched with scope across the entire D-66 family).

**Status:** 🟢 6 files (3 substantive code + 3 bookkeeping). Combined `tests/` 736 → 736 (zero deltas — no existing test coverage referenced the retired fields per grep). **D-66 status flipped 🟢 Profile-tab UI + onboarding §H.2/§H.4 + account_nudges consumer-side UI shipped → 🟢 Profile-tab UI + onboarding §H.2/§H.4 + account_nudges consumer-side UI + Layer 3B Scope A shipped.** Layer 3B caller-side rewire Scope B (column drop) + Scope C (partial-update invalidation hooks per design §7.4) + D-72 type-alignment remain as carry-forwards.

**1 over the 5-file ceiling** — first slip in the post-D-66-nudges-UI cadence. Justified by the substantive edits being pure retirement deletions (no new logic surface) paired with the mandatory bookkeeping floor (Backlog bump per Rule #12 + CLAUDE.md last-shipped narrative bump + handoff).

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| D-66 account_nudges consumer-side UI shipped on main per predecessor handoff | `git log --oneline -5` | ✅ `7826a7b` (merge PR #85) + `9055799` (D-66 account_nudges consumer-side UI) |
| `routes/nudges.py` extended with `target_race_skipped` + `route_locales_incomplete` + `display_delay_days` + `_past_display_delay` | grep | ✅ matches at lines 76, 86, 100, 152, 158 |
| `tests/test_nudges.py` has 19 tests | `grep -c "def test_"` | ✅ 19 |
| `Project_Backlog_v56.md` exists with D-66 row flipped to 🟢 | `ls` + grep | ✅ |
| `routes/onboarding.py` `_write_account_nudge` wires both new nudges at skip-time | grep | ✅ matches at lines 691, 811, 949, 968 |
| Combined `tests/` 736 green (baseline post-PR #85) | `pytest tests/ -q` | ✅ 736 passed in 2.93s |
| Working tree clean on `claude/race-events-onboarding-nudge-hNDGY` | `git status` | ✅ |
| Predecessor handoff §6.1 Scope A targets verified — `templates/profile/edit.html:73-81` + `routes/profile.py:242-243` + `athlete.py:21-22` | grep | ✅ all 3 anchors present on disk |
| Exhaustive grep for legacy field references — `target_event_name` + `target_event_date` across all `.py` / `.html` / `.md` | grep | ✅ exactly the predecessor-handoff-identified scope-A surfaces + `init_db.py` schema/migration (Scope B) + `DATABASE.md:311` schema doc (Scope B) + `routes/onboarding.py:710` docstring reference (informational; no code impact) — no surprises |
| No existing test coverage for the retired form fields | `grep tests/` | ✅ zero matches — no test deltas owed |
| `Project_Backlog_v56.md` D-66 row narrative + structure preserved + ready for v57 bump | Explore agent read | ✅ |

**Environmental drift surfaced (not code drift):** same as predecessor — the fresh container started without `pytest`/`pydantic`/`flask`/etc. installed in the active Python interpreter. Resolved by re-running the predecessor's `uv tool install` command at session start. Baseline 736 passed before any edits.

**Rule #9 reconciliation:** all predecessor handoff claims match on-disk state. No drift to fix; proceeded directly to scope pick.

---

## 2. Session narrative — D-66 Layer 3B Scope A

Andy opened with the URL to the D-66 nudge UI closing handoff + "lets work." Followed the operating model — read CLAUDE.md fully via Explore-agent delegation (Rule #13), ran Rule #9 verification (all green), surfaced state + the architect-recommended next-forward-move set from the predecessor handoff §6.1.

### 2.1 Scope pick (1-question gate)

Q1 (2026-05-18, 1-question gate): session scope. Andy picked **Layer 3B rewire — Scope A only** over Scope B (column-drop migration; Trigger #5 fires), Layer 4 Step 7 live LLM, and manual §5.0 walkthrough. The predecessor handoff §6.1 had recommended Scope A as the smallest cleanest D-66 sub-step that doesn't force a /plan-mode gate (no schema change, no invalidation-hook wiring).

### 2.2 Scope reality (no Round 2)

Before starting code, scoped Scope A against on-disk reality via two parallel greps + 3 target-file reads:

- **Predecessor handoff said:** "Drop from `templates/profile/edit.html:73-81` + `routes/profile.py:242-243` + `athlete.py:21-22` `KNOWN_PROFILE_FIELDS`. Add forward-pointer comment in `race_events_repo.py:load_target_race_event_payload`. ~3 files."
- **On-disk reality matched:** exhaustive grep across `.py` / `.html` / `.md` for `target_event_name` / `target_event_date` returned exactly the 3 scope-A surfaces + `init_db.py` schema/migration (Scope B; untouched) + `DATABASE.md:311` schema doc (Scope B; untouched) + `routes/onboarding.py:710` docstring reference (informational; describes how target rows could exist via the one-time migration; no code impact).
- **Architect-pick deviation:** dropped the predecessor-recommended `race_events_repo.py:load_target_race_event_payload` forward-pointer comment. The existing docstring "Convenience for the Layer 4 orchestrator — returns the athlete's current target race event payload" is already forward-pointing; adding "no caller wires this today; Scope B + C will land the rewire" is comment-rot waiting to happen (the comment would need to be deleted as soon as the Layer 3B caller lands). Moved that detail into this handoff §6.1 instead, where it lives without polluting the function docstring.
- **Test coverage check:** zero existing tests reference the legacy fields (`grep tests/` for `target_event_name` / `target_event_date` returns no matches). No test deltas owed. Adding a "form no longer renders these fields" regression test would be overkill — the visual regression is caught by §5 walkthrough, and the upstream behavior (helper silently drops unknown keys via `{k: fields[k] for k in PROFILE_FIELDS if k in fields}`) means no crash path exists even if a stale-tab POST submits the legacy field names.

No Q2 needed — Scope A was unambiguously specced; the only architect-pick was dropping the optional forward-pointer comment.

### 2.3 Implementation order

1. **Edit `templates/profile/edit.html`** — dropped the two `<div class="col-md-{8,4}">` form-field blocks (target event name + target event date) between the training-window selector and the Performance Baselines section. Replaced with an inline `{# #}` Jinja comment pointing at the race-events tab as the source of truth + noting the pending Scope B column drop. See §3.1.
2. **Edit `routes/profile.py`** — dropped `target_event_name=_str('target_event_name')` + `target_event_date=_str('target_event_date')` kwargs from the `upsert_athlete_profile(...)` call in the `profile.edit` POST handler. See §3.2.
3. **Edit `athlete.py`** — dropped `'target_event_name'` + `'target_event_date'` from the `PROFILE_FIELDS` tuple. Added a multi-line comment explaining the registry's downstream effects (it drives both `get_athlete_profile()`'s SELECT column list + `upsert_athlete_profile()`'s INSERT/UPDATE clean-key filter) + the Scope B follow-on plan, so future devs reading the tuple don't mistake the absence for an oversight. See §3.3.
4. **Bookkeeping:** `Project_Backlog_v56.md` → `_v57.md` + CLAUDE.md update (line 52 last-shipped narrative + line 254 First-session-checklist Backlog ref) + this handoff. See §9.

### 2.4 Architectural choices on the record

- **Scope A boundary holds — columns stay on disk.** Only the form UI + the registry pointer + the call-site write are retired this session. The columns will be dropped in Scope B (Trigger #5 will fire then). The D-66 one-time backfill migration in `init_db.py:1185` already copied any pre-D-66 values into `race_events`, so no athlete loses data even though the columns are now write-frozen from the athlete-facing surface. The next time a row is INSERTed into `athlete_profile`, the two columns will simply default to NULL — they remain readable for any consumer that still references them (currently none in production code paths) until Scope B drops them.
- **`PROFILE_FIELDS` is the registry that drives both reads + writes.** `get_athlete_profile()` does `SELECT user_id, {', '.join(PROFILE_FIELDS)}, updated_at FROM athlete_profile`; `upsert_athlete_profile()` does `clean = {k: fields[k] for k in PROFILE_FIELDS if k in fields}` before constructing the INSERT/UPDATE. Removing entries from the tuple is therefore sufficient to make both helpers ignore the legacy columns — no `SELECT *` shenanigans that would surface them anyway. The `upsert_athlete_profile` kwargs drop in `routes/profile.py` is technically redundant (the helper silently filters unknown keys) but call-site clarity is worth the redundant explicit removal — future devs reading the POST handler shouldn't see kwargs for fields the form no longer collects.
- **Inline Jinja `{# #}` comment in the template.** The template's existing structure (row container with `col-md-*` divs) made the absence of the target-event fields between training-window and Performance Baselines visually jarring. A 5-line Jinja comment explains why those inputs aren't present + where the athlete enters target races now. Future devs editing the Athlete-tab form won't add them back without context.
- **Multi-line Python comment in `athlete.py` `PROFILE_FIELDS`.** The tuple's downstream effects on `get_athlete_profile`'s SELECT + `upsert_athlete_profile`'s INSERT/UPDATE are non-obvious from the tuple alone. The comment explains the retirement + the Scope B follow-on so future devs reading the tuple know why `target_event_*` aren't present even though `init_db.py` + `DATABASE.md` still list them as columns.
- **Did NOT touch `race_events_repo.py:load_target_race_event_payload`.** Predecessor handoff §6.1 recommended a forward-pointer comment about the future Layer 3B caller. The existing docstring "Convenience for the Layer 4 orchestrator — returns the athlete's current target race event payload, or None when no race row has is_target_event=true (open-ended mode per Layer 3B §8.3)" is forward-pointing enough; adding a "no caller wires this today" comment would be rot waiting to happen (it'd need deletion as soon as the Scope C wire-up lands). The detail lives in this handoff §6.1 instead.
- **Did NOT touch `init_db.py` or `DATABASE.md`.** Both still reflect on-disk column reality — columns still exist; the D-66 one-time backfill migration is still active for any pre-D-66 row. Scope B updates both (column drop + DATABASE.md schema-section trim).
- **Did NOT touch D-72 row.** D-72's defer trigger (ii) explicitly says "D-66 profile-tab UI follow-on lands (will force the legacy `target_event_*` column retirement)" — Scope A retires the form UI but NOT the columns; D-72 still waits for Scope B (column drop) OR (i) Layer 3B caller rewire OR (iii) Layer 2C consumer-side trip. Touching D-72 prematurely would falsely claim its blocker is resolved.

### 2.5 Stop-and-ask triggers — none fired

- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire — `athlete_profile` schema unchanged; columns stay on disk. Scope B fires Trigger #5 (column drop migration is a cross-layer schema change since multiple specs document the columns).
- **Trigger #7 (new partial-update invalidation rule):** did NOT fire — Scope A is form-UI retirement only; the partial-update hooks per design §7.4 land with Scope C.
- **Trigger #8 (architectural alternatives with real tradeoffs):** the Scope A vs B vs C tradeoff was the architectural choice. Resolved via the session-start 1-question gate (CLAUDE.md operating model treats 1-question gates as the equivalent of /plan-mode for scope picks); no mid-session /plan gate needed.
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows. D-66 + D-72 unchanged; D-72 still waits for its trigger.

Other triggers — none applicable.

---

## 3. File-by-file substantive edits

### 3.1 `templates/profile/edit.html`

Dropped two form-field divs (target_event_name + target_event_date) between the training-window selector div (closing at original line 71) and the Performance Baselines comment block (original line 85). Replaced with an inline Jinja comment:

```jinja
{# Target event name + date live in the Race events tab now
   (D-66 §7 `race_events` table is the source of truth). The
   prior `athlete_profile.target_event_*` columns are vestigial
   pending column-drop in a follow-on session; existing rows
   were one-time-migrated into `race_events` by
   `init_db.py:1185`. #}
```

The template now flows training-window → comment → Performance Baselines without the legacy target-event inputs.

### 3.2 `routes/profile.py`

Dropped two kwargs from the `upsert_athlete_profile(...)` call in `profile.edit` POST handler:

```python
# Before (lines 240-244):
            primary_sport=_str('primary_sport'),
            target_event_name=_str('target_event_name'),
            target_event_date=_str('target_event_date'),
            weekly_hours_target=_num('weekly_hours_target'),
            training_window=window,

# After:
            primary_sport=_str('primary_sport'),
            weekly_hours_target=_num('weekly_hours_target'),
            training_window=window,
```

The kwargs drop is technically redundant (the helper silently filters unknown keys via the `PROFILE_FIELDS` registry — see §2.4) but call-site clarity is worth the explicit removal.

### 3.3 `athlete.py`

Dropped `'target_event_name'` + `'target_event_date'` from the `PROFILE_FIELDS` tuple + added an explanatory comment:

```python
PROFILE_FIELDS = (
    'date_of_birth',
    'sex',
    'height_cm',
    'primary_sport',
    # `target_event_name` + `target_event_date` retired from the form per
    # D-66 Layer 3B Scope A (race_events table is the source of truth via
    # the profile Race events tab + onboarding §H.2). The columns remain
    # on `athlete_profile` pending a Scope B drop migration; the one-time
    # backfill in `init_db.py:1185` copied any pre-D-66 values into
    # `race_events`. PROFILE_FIELDS drives the SELECT/UPDATE column list,
    # so removing them here stops the upsert helper + reader from touching
    # the vestigial columns even though they still exist on disk.
    'weekly_hours_target',
    'training_window',
    'notes',
    # ... unchanged ...
)
```

The downstream effects: `get_athlete_profile()`'s SELECT no longer fetches the legacy columns; `upsert_athlete_profile()`'s INSERT/UPDATE no longer touches them. `routes/profile.py:profile.edit` GET handler still passes `profile = get_athlete_profile(db, uid) or {}` to the template — `profile` dict no longer has the legacy keys, but the template also no longer references them, so consistency holds.

---

## 4. Test additions

**Zero test deltas this session.** Combined `tests/` 736 → 736 in 1.52s.

- Pre-edit grep across `tests/` for `target_event_name` / `target_event_date`: zero matches.
- Post-edit pytest run: 736 passed.

No test coverage was added because:
- The retirement is pure deletion (form fields, kwargs, registry entries) — no new behavior to exercise.
- The `upsert_athlete_profile` helper's silent unknown-key filter means even a stale-browser POST submitting the legacy field names produces no crash (the form action just discards them).
- Visual regression on the form is captured in §5 manual walkthrough.
- A regression test for "POST `/profile/` with legacy field names succeeds" would test the helper's pre-existing filter behavior, not Scope A's retirement — out of scope.

---

## 5. Manual §5.0 verification steps for Andy's walkthrough

Run on `https://aidstation-pro.vercel.app/` (or local dev) after PR merge. Layers on top of the D-66 onboarding 12-scenario suite (predecessor's predecessor handoff §6) + 6-scenario nudge UI suite (predecessor handoff §5).

1. **Athlete tab no longer renders target-event form fields.** Visit `/profile?tab=athlete` (or `/profile`). Confirm the form flows DOB / sex / height → primary sport / weekly hours / training window → Performance Baselines (no "Target event name" / "Target event date" inputs between training window and Performance Baselines).
2. **Race events tab is the only target-event entry surface.** Click the "Race events" tab. Confirm the existing race-event CRUD UI renders (per D-66 §7 profile-tab UI). Add or edit a race; flip its `is_target_event` flag. Confirm the change persists via page reload.
3. **POST `/profile/` ignores legacy form-field names (regression).** Manually craft a POST against `/profile/` including `target_event_name=foo&target_event_date=2026-09-01` in the body (curl or browser devtools). Confirm: (a) the POST succeeds (HTTP 302 redirect to `/profile/`), (b) `athlete_profile.target_event_name` + `target_event_date` are NOT written for this user (psql spot-check: `SELECT target_event_name, target_event_date FROM athlete_profile WHERE user_id = <Andy>;` returns the prior values, not "foo" / "2026-09-01"). This verifies the silent-filter behavior of `upsert_athlete_profile`.
4. **Pre-existing legacy data still readable in DB.** psql spot-check: `SELECT user_id, target_event_name, target_event_date FROM athlete_profile WHERE target_event_name IS NOT NULL;` — pre-D-66 rows (if any) still have their original values. Scope A doesn't drop or null them; Scope B will.
5. **Race events tab still pulls from `race_events` not the legacy columns.** Open devtools network tab on `/profile?tab=race-events`; confirm the rendered race list matches `SELECT name, event_date, is_target_event FROM race_events WHERE user_id = <Andy>` — independent of `athlete_profile.target_event_*` values.
6. **Onboarding §H.2 unaffected.** Walk a fresh-athlete onboarding through `/onboarding/target-race`. Save a target race. Confirm: (a) row written to `race_events` with `is_target_event=TRUE`, (b) no row written to `athlete_profile.target_event_*` (those columns stay NULL for new athletes), (c) the Race events tab on `/profile` shows the just-created row.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward moves

D-66 is one step closer to fully complete. Two follow-on candidates remain for D-66:

1. **Layer 3B caller-side rewire Scope B + Scope C** (closes D-66 family + clears D-72 trigger). Sub-scopes for the next-session 1-question gate:
   - **Scope B alone:** column-drop migration in `init_db.py:_PG_MIGRATIONS` (drops `athlete_profile.target_event_name` + `target_event_date` columns; safe because Scope A write-froze them + the D-66 backfill in `init_db.py:1185` preserved any values in `race_events`). Plus the matching `DATABASE.md:311` schema-section trim. **Trigger #5 fires** (cross-layer schema change; columns documented in DATABASE.md + referenced in init_db.py CREATE TABLE + backfill). Needs `/plan`-mode gate before implementing — the column drop is irreversible in production (PG ALTER TABLE DROP COLUMN). Plan considerations: (a) gate the DROP behind a check for any non-NULL values not already in `race_events` (defense-in-depth even though the backfill should have caught all); (b) confirm no orchestrator/Layer 4 path reads the columns (current grep says none; re-verify in case anything landed since); (c) update `DATABASE.md` schema-section + the `init_db.py:22-23` CREATE TABLE column list (test schema) + `init_db.py:666` test seed if it lists the columns; (d) decide whether to also retire the backfill migration in `init_db.py:1190-1213` (probably yes — it's a no-op once columns are dropped). ~4-5 files.
   - **Scope C alone:** wire partial-update invalidation hooks per design §7.4. The hooks need new web-handler → `Layer4Cache` facade glue (the cache lives in `layer4/cache.py` but isn't currently accessible from `routes/race_events.py` writers). Plus the actual eviction rule wiring. **Trigger #7 fires** (new partial-update invalidation rule). The rules themselves are designed in `Race_Events_D66_Design_v1.md` §9 but the wiring is new — needs an orchestrator helper or direct import depending on architectural choice (Trigger #8 also fires implicitly). ~3-5 files on its own.
   - **Scope B + C combined:** ~7-9 files — over the ceiling. Strongly recommend splitting.

   Recommendation: Scope B next session (smaller; clears D-72; unblocks Scope C); Scope C in a session after.

2. **Layer 3B caller-side orchestrator integration** (the original predecessor-of-predecessor handoff's framing of "Layer 3B rewire" before scope-reality analysis showed there's no orchestrator code yet). Lands when the Layer 4 orchestrator is implemented — currently neither orchestrator nor any Layer 3B input pathway exists, so `load_target_race_event_payload` has no caller outside its own tests. Orthogonal to Scope B + C.

Orthogonal candidates:

3. **Layer 4 Step 7 live LLM integration** — orthogonal to D-66. First end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call. Cache + telemetry from Steps 5/6 make it safer. Needs `ANTHROPIC_API_KEY` in the environment.

4. **Manual §5.0 walkthrough** of the accumulated D-66 family scenarios — 12 onboarding scenarios (predecessor-of-predecessor handoff §6) + 6 nudge UI scenarios (predecessor handoff §5) + 6 Scope A scenarios (§5 above). 24 scenarios total. Could be split across multiple Andy walkthrough sessions.

### 6.2 Carry-forward — D-72 still deferred

D-72 (`Layer2CPayload.locale_id: str` vs `Layer3BPayload.event_locale_id: str` vs `RaceEventPayload.event_locale_id: int`) — unchanged. D-72's defer trigger (ii) calls out "D-66 profile-tab UI follow-on lands (will force the legacy `target_event_*` column retirement)" — Scope A retires the form UI but NOT the columns; D-72 still waits for Scope B (column drop forces the question), OR (i) Layer 3B caller rewire, OR (iii) Layer 2C consumer-side trip.

### 6.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully. (Delegate to Explore agent — it's 100k+ tokens.)
2. **Second re-read**: this handoff.
3. **Third re-read**: depends on scope.
   - Scope B → `init_db.py:1185-1213` (one-time backfill migration; Scope B may want to retire it) + `init_db.py:22-23` (test schema CREATE TABLE) + `init_db.py:666` (test seed if any) + `DATABASE.md:311` (schema section listing the columns). Plus `_PG_MIGRATIONS` patterns for past column-drop migrations as precedent.
   - Scope C → `Race_Events_D66_Design_v1.md` §7.4 + §9 (partial-update invalidation rules) + `layer4/cache.py` (Layer4Cache facade) + `layer4/cache_invalidation.py` (existing eviction patterns) + `routes/race_events.py` (writer side; needs new glue to reach the facade).
   - Manual walkthrough → §5 above + predecessor handoff §5 + predecessor-of-predecessor handoff §6.
4. **Branch**: cut fresh off post-merge main OR stay on the harness pin (precedent: this session stayed harness-pinned from the predecessor's nudge-UI branch).
5. **Scope A is complete**: athlete enters target races only via `/profile?tab=race-events` (CRUD UI) or `/onboarding/target-race` (Step 3c onboarding). The Athlete tab no longer carries the legacy form fields. The legacy columns remain on disk pending Scope B but are write-frozen from the athlete-facing surface.

---

## 7. Open items / decisions pinned this session

### 7.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Q1 scope = Layer 3B rewire Scope A only | Andy 2026-05-18 | Architect-recommended from predecessor handoff §6.1; smallest cleanest D-66 sub-step; no Triggers fire |
| 2 | Drop the predecessor-recommended `race_events_repo.py:load_target_race_event_payload` forward-pointer comment | Architect-pick | Existing docstring is forward-pointing enough; "no caller yet" detail is rot waiting to happen (delete-on-Scope-C); lives in this handoff §6.1 instead |
| 3 | Inline Jinja `{# #}` comment in `templates/profile/edit.html` explaining the absent target-event inputs | Architect-pick | Visual gap in the form between training-window and Performance Baselines would otherwise look like an oversight; comment points future devs at the race-events tab |
| 4 | Multi-line Python comment in `athlete.py` `PROFILE_FIELDS` | Architect-pick | Registry drives both SELECT + UPDATE column lists; future devs reading the tuple need to know why `target_event_*` aren't present even though `init_db.py` / `DATABASE.md` still list them |
| 5 | Keep `init_db.py` + `DATABASE.md` untouched | Architect-pick | Scope B scope; columns still exist on disk; documentation matches on-disk reality |
| 6 | Keep D-72 row untouched | Architect-pick | D-72's trigger (ii) is column retirement, not form-UI retirement; Scope A doesn't fire D-72 |
| 7 | Drop kwargs from `upsert_athlete_profile(...)` call (technically redundant with the helper's silent-filter) | Architect-pick | Call-site clarity outweighs the technically-redundant explicit removal |
| 8 | No test deltas | Architect-pick | Zero existing tests reference the legacy fields; retirement is pure deletion; helper's silent-filter means no crash path |
| 9 | 6 files total (1 over the 5-file ceiling) | Necessitated | 3 substantive code + 3 bookkeeping; bookkeeping floor is non-negotiable (Backlog bump per Rule #12 + CLAUDE.md last-shipped + handoff); substantive edits are deletion-only |

### 7.2 Carry-forward — Layer 3B rewire Scope B (next session)

See §6.1. Trigger #5 fires; needs `/plan`-mode gate.

### 7.3 Carry-forward — Layer 3B rewire Scope C

See §6.1. Trigger #7 (+ implicit Trigger #8) fires; partial-update invalidation hooks per design §7.4.

### 7.4 Carry-forward — D-72 type-alignment

Unchanged from prior sessions. Forced by Scope B column drop OR Layer 3B caller rewire OR Layer 2C consumer-side trip.

### 7.5 Carry-forward — D-66 §5.0 walkthrough (accumulating)

24 scenarios total now: 12 onboarding (predecessor-of-predecessor handoff §6) + 6 nudge UI (predecessor handoff §5) + 6 Scope A (§5 above). Andy walks on Vercel after PR merge.

### 7.6 Carry-forward — `_v56.md` retained per Rule #12

`Project_Backlog_v56.md` preserved alongside the new `_v57.md` per the numeric-version-suffix rule. The historical chain stays intact.

---

## 8. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `athlete.py` `PROFILE_FIELDS` no longer contains `'target_event_name'` / `'target_event_date'` as string literals | ✅ grep `'target_event_(name\|date)'` returns no matches in `athlete.py` (the only `target_event_*` mention is the new explanatory comment) |
| `routes/profile.py` `upsert_athlete_profile(...)` no longer passes `target_event_name=` / `target_event_date=` | ✅ grep `target_event_name\|target_event_date` returns no matches in `routes/profile.py` |
| `templates/profile/edit.html` no longer renders `name="target_event_*"` form inputs | ✅ grep `name="target_event` returns no matches; only the new Jinja comment mentions the field names in backticks |
| `templates/profile/edit.html` new Jinja comment explains the absence + points at the race-events tab | ✅ inspection — 6-line `{# #}` block between training-window and Performance Baselines |
| `athlete.py` new multi-line comment explains the registry's downstream effects + Scope B follow-on | ✅ inspection — 7-line comment above `weekly_hours_target` entry |
| Combined `tests/` 736 green | ✅ `pytest tests/ -q` → 736 passed in 1.52s |
| `Project_Backlog_v57.md` exists; v56 retained | ✅ `ls -la` |
| `Project_Backlog_v57.md` D-66 row status updated to "🟢 Profile-tab UI + onboarding §H.2/§H.4 + account_nudges consumer-side UI + Layer 3B Scope A shipped" | ✅ grep `+ Layer 3B Scope A 2026-05-18 (this revision: retired legacy` returns 1 match |
| `Project_Backlog_v57.md` file revision header bumped to v57 with Scope A narrative | ✅ grep `File revision:\*\* v57` returns 1 match |
| `Project_Backlog_v57.md` v56-revision parenthetical replaced with v57-revision parenthetical | ✅ grep `extended .routes/nudges.py. .NUDGE_REGISTRY. with .target_race_skipped` returns 0 matches (the v56-revision content was replaced surgically) |
| `CLAUDE.md` line 52 last-shipped narrative bumped to D-66 Layer 3B Scope A | ✅ inspection — line head reads "Last shipped session: **D-66 Layer 3B Scope A — retired the legacy..." |
| `CLAUDE.md` line 254 First-session-checklist Backlog ref bumped to v57 | ✅ grep `Project_Backlog_v57` returns 1 match at line 254 |
| `CLAUDE.md` other 52+ lines (older predecessor history) untouched | ✅ line-length profile unchanged for lines 54+ |
| `init_db.py` + `DATABASE.md` untouched (Scope B) | ✅ no edits made |
| `routes/onboarding.py:710` docstring reference to "legacy athlete_profile.target_event_*" untouched (informational; describes how target rows could exist via the one-time migration) | ✅ no edits made |
| D-72 row in v57 backlog untouched | ✅ inspection — D-72 still reads "🟡 Deferred" + same defer-trigger language |

---

## 9. Files shipped this session

**Substantive code (3 modified = 3 files):**
1. Modified `templates/profile/edit.html` — dropped two `<div class="col-md-{8,4}">` form-field blocks (target_event_name + target_event_date); replaced with an inline Jinja comment pointing at the race-events tab.
2. Modified `routes/profile.py` — dropped `target_event_name=_str(...)` + `target_event_date=_str(...)` kwargs from the `upsert_athlete_profile(...)` call in `profile.edit` POST handler.
3. Modified `athlete.py` — dropped `'target_event_name'` + `'target_event_date'` from `PROFILE_FIELDS` tuple; added multi-line comment explaining the registry's downstream effects + Scope B follow-on plan.

**Bookkeeping (3 files):**
4. New `aidstation-sources/Project_Backlog_v57.md` (per Rule #12; v56 retained as predecessor) — file revision header rewritten for Scope A; D-66 row status flipped to include "+ Layer 3B Scope A 2026-05-18" + v57-revision parenthetical narrative.
5. Modified `aidstation-sources/CLAUDE.md` — last-shipped-session narrative bump (line 52: D-66 account_nudges UI → D-66 Layer 3B Scope A; demotes nudges UI to "Predecessor —" tail reference); First-session-checklist Backlog ref bumped (line 254: v56 → v57).
6. New `aidstation-sources/handoffs/V5_Implementation_D66_Layer3B_Rewire_Scope_A_Closing_Handoff_v1.md` (this file).

**6 files total. 1 over the 5-file ceiling.** First slip in the post-D-66-nudges-UI cadence. Justified by the substantive edits being pure retirement deletions (no new logic surface) paired with the mandatory bookkeeping floor.

---

## 10. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **D-72 Locale-FK type alignment across typed payloads** — still deferred; Scope A doesn't fire its trigger (column retirement); Scope B will.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward; needs `ANTHROPIC_API_KEY`.
- **Partial-update invalidation hooks per design §7.4** — concrete carry-forward; lands with Scope C.
- **D-66 §5.0 walkthrough (24 scenarios accumulating)** — 12 onboarding + 6 nudge UI + 6 Scope A. Andy walks on Vercel after PR merges.

---

**End of handoff.**
