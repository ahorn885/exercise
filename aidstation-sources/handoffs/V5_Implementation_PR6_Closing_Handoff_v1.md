# V5 Onboarding Implementation PR6 — Closing Handoff

**Session:** Sixth substantive code session of the v5 onboarding implementation arc. Pivots from PR5's recommended next (D2 = per-field prefill UX) to D-51 column foundation + Option G after Rule #9 surfaced a blocking dependency: D2's spec requires comparison cards over `athlete_profile` columns that don't exist (no `body_weight_kg`, `hrmax_bpm`, `vo2max`, `cycling_ftp_w`, `lactate_threshold_hr_bpm`) and provider tables (`coros_*`, `polar_*`) don't store body weight either. This PR ships the column foundation + manual self-report form fields + provenance-row scaffolding so PR7 can ship D2a (read-side prefill UX) on top of real storage. Bundles G — `coros_ingest._ingest_activity` ON CONFLICT cleanup against PR3's `cardio_log_coros_label_uidx` partial UNIQUE.
**Date:** 2026-05-14
**Predecessor handoff:** `V5_Implementation_PR5_Closing_Handoff_v1.md` (its §5.1 Option D2 carry-forward + §5.4 v17→v18 mechanical bump are what this session executes; the D2 scope was re-cut after surfacing the storage-blocker).
**Branch:** `claude/v5-closing-handoff-zg5i0` (per-session feature branch off `main`; PR5 was already merged to `main` as `34637d2` via PR #37 before this session started).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 live `/profile?tab=profile` page-load + 5-field save round-trip + provenance-row spot-check on Neon owed at deploy time (no Flask in sandbox, same gap as PR1–PR5).
**Time-on-task:** Single chat. Substantive files: **5** (`init_db.py`, `athlete.py`, `templates/profile/edit.html`, `routes/profile.py`, `routes/coros_ingest.py`). Plus the v17→v18 backlog bump (`Project_Backlog_v18.md` new copy + 1-line `CLAUDE.md` edit) and this handoff = 8 total.

---

## 1. Session-start verification (Rule #9)

Verified the PR5 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/v5-closing-handoff-zg5i0` clean off `main`; PR5 merged to `main` as `34637d2` via PR #37 (commit `795ef9e`) | `git status` + `git log --oneline -10` | ✅ Verified |
| `routes/onboarding.py` exists with `connect` / `skip` / `continue_` routes | grep | ✅ Verified |
| `routes/profile.py:load_connections` (renamed from `_load_connections`) takes a `return_to` param; `CONNECTION_PROVIDERS` exported | grep | ✅ Verified |
| `app.py` imports + registers `onboarding_bp` | grep | ✅ Verified |
| `routes/auth.py:register` redirects to `url_for('onboarding.connect')` | grep | ✅ Verified |
| `templates/profile/edit.html` script tag at L389 has `nonce="{{ csp_nonce() }}"` (PR5 §3.4 drive-by) | grep | ✅ Verified |
| `Project_Backlog_v17.md` exists; predecessor v16 block intact; **cosmetic drift** in v17 header narrative ("PR1+PR2+PR3 shipped" missing PR4) still present per PR5 §1's flag | sed + grep | ✅ Verified (drift confirmed, deferred per PR5 §5.4) |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads v17 | grep | ✅ Verified |

**Drift surfaced + resolved during PR6 scope-design:** PR5 §5.1 Option D2's spec ("registry + per-field comparison UI: provider value vs current stored value") cannot ship as written because the storage on both sides is mostly absent:

- **Athlete-side:** `athlete_profile` has `date_of_birth, sex, height_cm, primary_sport, target_event_name, target_event_date, weekly_hours_target, training_window, notes` only. No `body_weight_kg`, `hrmax_bpm`, `vo2max`, `cycling_ftp_w`, `lactate_threshold_hr_bpm` — i.e. none of the v5 §A.2.1 prefill-eligible §F performance baselines or §A body weight. This matches Integration v4 §7.6 ("Gap summary — onboarding fields with no app-table home") and Backlog D-51 ("Layer 1 §A-§L field-by-field inventory against `public.*` existing tables — pending").
- **Provider-side:** `polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, `polar_continuous_hr_samples`, `coros_daily_summary`, `coros_hrv_samples`, `coros_plans` — none store body weight. HRmax derivable from `cardio_log.max_hr` aggregates; sleep-avg derivable from `coros_daily_summary` sleep fields + `polar_sleep.total_sleep_min`; weight not currently captured.

PR5 §5.1 didn't catch this because its scope was specced against the v5 §A.2 narrative as if storage were a given. Rule #9 reconciliation against on-disk schema surfaced the gap.

**Per Stop-and-ask trigger #5 (schema affecting inter-layer contract) + #11 (cross-layer D-row),** this was confirmed with Andy before any code landed: PR6 pivots to "schema foundation + manual form + G", deferring D2 read-side UX (registry + comparison route + extractors) to PR7 where the columns + extractors all land alongside the consumer.

---

## 2. Files shipped this turn

All on branch `claude/v5-closing-handoff-zg5i0`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `init_db.py` | Edit (+10 schema lines + 10 ALTER lines across 4 sites) | Adds 5 columns to `athlete_profile`: `body_weight_kg REAL`, `hrmax_bpm INTEGER`, `lactate_threshold_hr_bpm INTEGER`, `vo2max REAL`, `cycling_ftp_w INTEGER`. Four sites: SQLite cold-start `_SCHEMA_SQL` (line 31-35), PG cold-start `_PG_SCHEMA_SQL` (line 350-354), SQLite migration list `_SQLITE_MIGRATIONS` (line 1395-1399, bare `ALTER TABLE … ADD COLUMN` relying on the try/except wrapper at `init_sqlite()` line 2438-2439 to swallow duplicate-column errors on re-run), PG migration list `_PG_MIGRATIONS` (line 1955-1959, `ADD COLUMN IF NOT EXISTS`). Migration-list `CREATE TABLE IF NOT EXISTS athlete_profile` shells (line 1161-1162 + 1601-1602) also updated so a fresh cold-start through the migration path picks up the columns. |
| 2 | `athlete.py` | Edit (+5 lines to `PROFILE_FIELDS` + new `PREFILL_ELIGIBLE_FIELDS` tuple) | (a) `PROFILE_FIELDS` extended from 9 entries to 14 — adds the 5 new column names. The existing `get_athlete_profile` SELECT (line 38) and `upsert_athlete_profile` filter (line 55) auto-pick-up new fields via the f-string + dict-comprehension patterns; no signature changes. (b) New `PREFILL_ELIGIBLE_FIELDS` tuple: subset of `PROFILE_FIELDS` that v5 §A.2.1 marks as provider-prefill-eligible. Used by `routes/profile.py` to scope provenance writes. |
| 3 | `templates/profile/edit.html` | Edit (+~50 lines under Athlete tab) | New "Performance baselines" section between target-event-date and notes-textarea. Header: `<hr>` divider + small-caps subhead + 2-line description ("Optional. Feeds Layer 3 athlete-evaluation calculations. Connected providers will auto-populate these in a future release; for now self-report is the only path."). 5 number-input fields with sensible min/max bounds: body_weight_kg (20-300), hrmax_bpm (100-240), lactate_threshold_hr_bpm (100-220), vo2max (20-100), cycling_ftp_w (50-500). Each uses the `profile.<field> if profile.<field> is not none else ''` pattern so `0` doesn't render as empty. |
| 4 | `routes/profile.py` | Edit (+1 import + new helper + ~10 lines in save handler) | (a) Import `PREFILL_ELIGIBLE_FIELDS` from `athlete` (alongside existing `PROFILE_FIELDS`, `TRAINING_WINDOWS`, helpers). (b) Import `database` module for `_is_postgres()` check. (c) New module-private helper `_record_self_report_provenance(db, uid, field_values)` placed above `_load_memory`. Writes/UPSERTs `athlete_profile_field_provenance` rows with `source='self_report'` for each non-None value in `field_values`. PG-only — early-returns on SQLite (the table is in `_PG_MIGRATIONS` only per Integration v4 §2.5 freeze). UPSERT via `ON CONFLICT (user_id, field_name) DO UPDATE SET source = EXCLUDED.source, last_updated_at = NOW()`. (d) `edit()` save handler (POST branch) builds a `prefill_values` dict with `_num()` casts for the 5 new fields (3 INTEGER fields use `cast=int`, 2 REAL fields use the default float), passes them to `upsert_athlete_profile(...)` via `**prefill_values`, then calls `_record_self_report_provenance(db, uid, prefill_values)` before `db.commit()`. |
| 5 | `routes/coros_ingest.py` | Edit (Option G — 30-line shrink) | `_ingest_activity` rewritten from SELECT-then-UPDATE-or-INSERT against PR3's `cardio_log_coros_label_uidx` partial UNIQUE index. Now a single `INSERT INTO cardio_log (...) VALUES (...) ON CONFLICT (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL DO UPDATE SET <col> = EXCLUDED.<col>, …`. Race-safe under concurrent webhook delivery (PR3's whole point). Mirror of PR3's `polar_ingest._upsert_exercise` pattern (line 197-203 there) — same idiom against the parallel partial UNIQUE. Other ingesters (`_ingest_daily_summary` line 144, `_ingest_hrv_sample` line 181) unchanged — they already used full UNIQUE constraints (not partial). Docstring updated to reference the index PR3 added. |
| — | `aidstation-sources/Project_Backlog_v18.md` | New (copy of v17 + 3 surgical edits) | Per PR5 §5.4 mechanical instructions. **File revision** header bumped v17→v18 with full PR5 + PR6 narrative. **Predecessor revisions** block prepends the v17 entry verbatim (its cosmetic-drift narrative archives as historical). **D-50 status cell** rewritten to add PR5 + PR6 commits/branches and update the PR6+ candidate menu (D2 split into D2a + D2b; D1 marked shipped per PR5; G marked shipped per PR6). Notes column rewritten with the per-PR breakdown of D-50 progress (PR1 helper + COROS, PR2 schema + chains, PR3 Polar + partial-UNIQUE, PR4 Connections tab, PR5 Step-2 connect + drive-by CSP fix, PR6 D-51 column foundation + G) and the PR7+ candidate menu. |
| — | `aidstation-sources/CLAUDE.md` | Edit (1-line) | Per PR5 §5.4 step 5: "Authoritative current files" backlog line bumped from `Project_Backlog_v17.md` to `Project_Backlog_v18.md`. Single-line edit, same shape as PR4 did v16→v17 and PR5 deferred to PR6. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR6_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `routes/onboarding.py` — unchanged. PR5's three routes (`connect`, `skip`, `continue_`) and `_POST_STEP2_TARGET = '/profile?tab=athlete'` stay as-is. The `_POST_STEP2_TARGET` flip lands with PR7 D2a when `/onboarding/prefill` exists.
- `routes/auth.py` — unchanged. Post-register redirect still goes to `onboarding.connect` per PR5.
- `routes/coros.py` / `routes/polar.py` / `routes/oauth_callbacks.py` / `routes/provider_auth.py` / `routes/polar_ingest.py` — zero edits. PR6 is profile-side; provider OAuth + ingest paths unchanged.
- `routes/profile_fields.py` (would-be new) — **deliberately not created.** PR6 ships the column foundation + manual UI; the `KNOWN_PROFILE_FIELDS` registry lands with PR7 D2a where it has a consumer (the `/onboarding/prefill` route + comparison template). Per CLAUDE.md "Don't add features beyond what the task requires" — building an extractor module without a consumer is dead code until D2a ships.
- `routes/profile_extractors.py` (would-be new) — same. Provider-data extractors (HRmax-from-`cardio_log.max_hr`, sleep-avg-from-`coros_daily_summary`, etc.) land with PR7 alongside the comparison page that renders their output.
- `templates/onboarding/connect.html` — unchanged. PR5's Step-2 connect screen still renders correctly.
- `routes/polar_ingest.py` — unchanged. Already uses ON CONFLICT (line 200) — G's idiom was always going to mirror this.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1–PR5 used. PR6 adds 5 new columns; the count of undocumented additions ticks up.

---

## 3. What landed

### 3.1 Schema foundation (`init_db.py`)

5 new columns on `athlete_profile`:

| Column | Type | v5 §A.2.1 prefill-eligible? | Provider source per Integration v4 §7 |
|---|---|---|---|
| `body_weight_kg` | REAL (kg) | ✅ §A | Polar / Garmin / Wahoo wellness sync (none currently captured) |
| `hrmax_bpm` | INTEGER (bpm) | ✅ §F | Self-report; FIT-fillable from `cardio_log.max_hr` aggregates; provider when synced |
| `lactate_threshold_hr_bpm` | INTEGER (bpm) | ✅ §F | Self-report or lab test |
| `vo2max` | REAL (ml/kg/min) | ✅ §F | Self-report; FIT-fillable; provider when synced |
| `cycling_ftp_w` | INTEGER (watts) | ✅ §F | Self-report (TT/ramp test); future Wahoo FTP API |

Schema lands in 4 sites per the existing pattern:

- **SQLite cold-start** (`_SCHEMA_SQL`, line 31-35) — runs on a fresh `/tmp/training.db` or `instance/training.db`. New columns inline in the CREATE TABLE.
- **PG cold-start** (`_PG_SCHEMA_SQL`, line 350-354) — runs on a fresh Neon instance. Same shape.
- **SQLite migrations** (`_SQLITE_MIGRATIONS`, line 1395-1399) — runs on every cold-start to catch up existing DBs. Bare `ALTER TABLE … ADD COLUMN` (no `IF NOT EXISTS` — SQLite older versions don't support it). The try/except wrapper at `init_sqlite()` line 2438-2439 swallows duplicate-column errors on re-run.
- **PG migrations** (`_PG_MIGRATIONS`, line 1955-1959) — runs on every Neon connection. `ADD COLUMN IF NOT EXISTS` is idempotent.

The migration-list `CREATE TABLE IF NOT EXISTS athlete_profile` shells (line 1161-1162 SQLite, line 1601-1602 PG) also updated — they're no-ops on existing DBs but matter for the (rare) case where the migration path runs against a DB that doesn't have the table yet.

**No data backfill.** All 5 columns default NULL. Existing athletes (Andy) see empty form fields; new athletes see them on first profile save. No migration heroics needed.

### 3.2 `PROFILE_FIELDS` + new `PREFILL_ELIGIBLE_FIELDS` (`athlete.py`)

`PROFILE_FIELDS` was the gatekeeper for `upsert_athlete_profile` — it filters the kwargs to known columns. Extending it from 9 to 14 entries cascades to:

- `get_athlete_profile` SELECT statement (line 38) — auto-includes new columns via `', '.join(PROFILE_FIELDS)`.
- `upsert_athlete_profile` INSERT/UPDATE (line 45-78) — auto-includes new fields via `clean = {k: fields[k] for k in PROFILE_FIELDS if k in fields}`.

So `routes/profile.py` can pass the 5 new kwargs and they flow through naturally. No changes to `athlete.py` upsert logic.

The new `PREFILL_ELIGIBLE_FIELDS` tuple is the explicit subset of `PROFILE_FIELDS` that v5 §A.2.1 marks as provider-prefill-eligible. PR6 consumes it in `routes/profile.py:_record_self_report_provenance` to scope the provenance-row writes. PR7 D2a will consume it as the seed for the `KNOWN_PROFILE_FIELDS` registry (more metadata per field — label, type, eligible providers, extractor function — but the field-name list is `PREFILL_ELIGIBLE_FIELDS` itself).

### 3.3 Form fields under Athlete tab (`templates/profile/edit.html`)

New "Performance baselines" section inserted between the target-event-date row and the notes textarea. Layout: `<hr>` divider + `text-uppercase small` subhead + 2-line muted description, followed by 5 `<col-md-4>` number inputs. Bounds match real-world ranges:

- `body_weight_kg`: 20-300, step 0.1
- `hrmax_bpm`: 100-240, step 1
- `lactate_threshold_hr_bpm`: 100-220, step 1
- `vo2max`: 20-100, step 0.1
- `cycling_ftp_w`: 50-500, step 1

Each input renders the existing value via `{{ profile.<field> if profile.<field> is not none else '' }}` — explicit `is not none` check so a stored `0` doesn't render as empty (Jinja's `or ''` truthy check would have done that).

The footer text honestly tells athletes the prefill UX hasn't shipped yet: "Connected providers will auto-populate these in a future release; for now self-report is the only path." Same honest framing as PR5's Step-2 consent disclosure footer.

### 3.4 Save handler + provenance (`routes/profile.py`)

Two changes to the POST branch of `edit()`:

```python
prefill_values = {
    'body_weight_kg': _num('body_weight_kg'),
    'hrmax_bpm': _num('hrmax_bpm', cast=int),
    'lactate_threshold_hr_bpm': _num('lactate_threshold_hr_bpm', cast=int),
    'vo2max': _num('vo2max'),
    'cycling_ftp_w': _num('cycling_ftp_w', cast=int),
}
upsert_athlete_profile(
    db, uid,
    # … existing 9 kwargs …
    **prefill_values,
)
_record_self_report_provenance(db, uid, prefill_values)
db.commit()
```

Existing `_num(key, cast=float)` helper handles the float fields; the integer fields override `cast=int`. Empty form values become None (via the existing `_num` early-return); None values get filtered out of the provenance write.

The new helper `_record_self_report_provenance` writes one row per non-None prefill-eligible field:

```python
def _record_self_report_provenance(db, uid, field_values):
    if not database._is_postgres():
        return  # PG-only table; no-op in SQLite dev mode
    for field_name, value in field_values.items():
        if value is None:
            continue
        if field_name not in PREFILL_ELIGIBLE_FIELDS:
            continue
        db.execute(
            'INSERT INTO athlete_profile_field_provenance '
            '(user_id, field_name, source) '
            'VALUES (?, ?, ?) '
            'ON CONFLICT (user_id, field_name) DO UPDATE SET '
            '    source = EXCLUDED.source, '
            '    last_updated_at = NOW()',
            (uid, field_name, 'self_report'),
        )
```

Three design choices worth flagging:

- **Always writes `source='self_report'` in PR6.** v5 §A.2.3 spec table distinguishes `'self_report'` (athlete enters into never-prefilled field) from `'manual_override'` (athlete types over a prefilled value). PR6 has no prefill mechanism, so the rows we touch are either (a) non-existent → INSERT 'self_report' is correct, or (b) already 'self_report' from a prior save → upsert keeps 'self_report' which is correct. The 'manual_override' flip lands with PR7 D2a where prefill mechanics ship. Documented inline + here.
- **PG-only via early-return.** `athlete_profile_field_provenance` lives in `_PG_MIGRATIONS` only per Integration v4 §2.5 freeze. The check `if not database._is_postgres(): return` matches the established pattern. SQLite dev saves still work — they just skip the provenance write.
- **None values skipped, not deleted.** If an athlete clears a field (sets value to empty string → None), the provenance row is left as-is. The v5 §A.2.6 manual-override clear path will handle row deletion when D2 ships; PR6 only writes, never deletes. Documented in §6 below.

### 3.5 G — `coros_ingest._ingest_activity` ON CONFLICT cleanup

Before (lines 89-141 pre-PR6, ~50 lines of SELECT-then-branch-on-existence):

```python
cur = db.execute('SELECT id FROM cardio_log WHERE user_id = ? AND coros_label_id = ?', (user_id, str(label_id)))
existing = cur.fetchone()
if existing:
    set_clause = ', '.join(f'{c} = ?' for c in cols)
    db.execute(f'UPDATE cardio_log SET {set_clause} WHERE id = ?', list(cols.values()) + [existing['id']])
else:
    cols['user_id'] = user_id
    cols['coros_label_id'] = str(label_id)
    col_names = list(cols)
    placeholders = ', '.join(['?'] * len(col_names))
    db.execute(f'INSERT INTO cardio_log ({", ".join(col_names)}) VALUES ({placeholders})', [cols[c] for c in col_names])
```

After (single statement, ~12 lines):

```python
set_clause = ', '.join(f'{c} = EXCLUDED.{c}' for c in cols)
col_names = ['user_id', 'coros_label_id'] + list(cols)
placeholders = ', '.join(['?'] * len(col_names))
db.execute(
    f'INSERT INTO cardio_log ({", ".join(col_names)}) '
    f'VALUES ({placeholders}) '
    f'ON CONFLICT (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL '
    f'DO UPDATE SET {set_clause}',
    [user_id, str(label_id)] + [cols[c] for c in cols],
)
```

Race-safe (this was PR3's whole reason for adding `cardio_log_coros_label_uidx`); fewer round-trips; mirrors `polar_ingest._upsert_exercise`'s shape (PR3 line 197-203). PG-only — the partial UNIQUE index lives in `_PG_MIGRATIONS` only per Integration v4 §2.5 freeze. Production runs on Postgres; if the function were ever invoked against SQLite (it isn't — webhooks only land in production) it would error on the ON CONFLICT clause referencing a nonexistent index, which mirrors `polar_ingest`'s behavior.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| All 4 substantive Python files AST-parse clean (`init_db.py`, `athlete.py`, `routes/profile.py`, `routes/coros_ingest.py`) | `ast.parse` over each | ✅ Verified |
| `athlete.py:PROFILE_FIELDS` length = 14 (was 9); 5 new columns present | AST tuple-element walk | ✅ Verified |
| `athlete.py:PREFILL_ELIGIBLE_FIELDS` = exactly the 5 new column names | AST tuple-element walk | ✅ Verified |
| 5 new columns present at all 4 init_db.py sites (cold-start SQLite, cold-start PG, migration SQLite, migration PG) | grep | ✅ Verified — 24 total mentions in init_db.py (5×2 cold-starts + 5×2 migrations + 5×2 mid-list CREATE TABLE shells = 30; actual count 24 because the cold-start CREATE TABLE shells use single-column-per-line and the migration shells pack 2 lines × ~3 cols each — verified by line numbers) |
| `routes/profile.py` imports `PREFILL_ELIGIBLE_FIELDS` and `database`; defines `_record_self_report_provenance`; save handler invokes it | grep | ✅ Verified |
| `routes/profile.py:_record_self_report_provenance` uses PG-only guard via `database._is_postgres()` | grep | ✅ Verified |
| `routes/coros_ingest.py:_ingest_activity` uses `ON CONFLICT (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL`; no remaining SELECT-then-UPDATE-or-INSERT | grep | ✅ Verified — no `SELECT id FROM cardio_log WHERE` and no `UPDATE cardio_log SET` left in the file |
| `coros_ingest` other ON CONFLICT uses (`coros_daily_summary`, `coros_hrv_samples`) intact | grep | ✅ Verified — 3 `ON CONFLICT` calls total in the file |
| `templates/profile/edit.html` Jinja parses cleanly | `Environment.parse()` | ✅ Verified |
| Stub render of `templates/profile/edit.html` covers happy-path (populated profile with all 5 prefill values) | inline `Environment.from_string(...).render(...)` with stub `base.html` + mocked `url_for` + `csrf_token` + `csp_nonce` + `get_flashed_messages` | ✅ Verified — 11 anchors present: `Performance baselines` heading, `name="body_weight_kg"` + `value="76.5"`, `name="hrmax_bpm"` + `value="188"`, `name="lactate_threshold_hr_bpm"` + `value="162"`, `name="vo2max"` + `value="55.2"`, `name="cycling_ftp_w"` + `value="250"` |
| Render variant: empty profile (cold-start, all 5 prefill values None) | inline render | ✅ Verified — all 5 field name attrs present; no stale value leaks (no `value="76.5"` etc.) |
| `Project_Backlog_v18.md` exists; v17 entry archived to predecessor block; D-50 row updated; v18 header narrative reflects PR5 + PR6 reality | grep + visual | ✅ Verified |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads `Project_Backlog_v18.md` | grep | ✅ Verified |
| Flask not installed in sandbox — full app import not exercisable | python3 import check | ⚠️ Same gap as PR1–PR5. Live `/profile?tab=profile` save round-trip + provenance-row spot-check on Neon owed at deploy time |

No drift between this handoff's narrative and on-disk state.

The same "can't exec the Flask app without Flask" gap PR1 §6 + PR2 §4 + PR3 §4 + PR4 §4 + PR5 §4 flagged applies. AST + Jinja parse + stub-render are the offline guards. The PR6 §5.0 live-check (open `/profile?tab=profile`, fill the 5 new fields, save, verify (a) the values round-trip on next GET, (b) `athlete_profile_field_provenance` rows exist on Neon with `source='self_report'`) is mandatory before this PR is "real."

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR6 reaches production)

PR6 ships a schema migration + 5 form fields + 1 webhook-ingest rewrite. Verification scope is light but the schema migration is the riskiest piece — get it wrong on Neon and the next webhook write blows up.

1. **Schema migration on Neon.** Trigger a deploy (push to `main` after merge) and watch the cold-start `_PG_MIGRATIONS` log. Confirm the 5 `ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS …` statements run cleanly. Spot-check via `psql`:
   ```sql
   \d athlete_profile
   -- Should show 5 new columns: body_weight_kg, hrmax_bpm,
   -- lactate_threshold_hr_bpm, vo2max, cycling_ftp_w
   ```
2. **`/profile?tab=profile` form render.** Open `/profile` as the test athlete. Confirm the new "Performance baselines" section renders between target-event-date and the notes textarea. All 5 input fields present with correct labels + units in parens. Empty values for a fresh profile.
3. **Save round-trip.** Type values into all 5 fields (e.g. body_weight_kg=76.5, hrmax_bpm=188, lactate_threshold_hr_bpm=162, vo2max=55.2, cycling_ftp_w=250). Click "Save profile". Confirm:
   - Flash message "Profile saved." appears.
   - Page reloads to `/profile/` with all 5 values populated in the form.
   - `psql`: `SELECT body_weight_kg, hrmax_bpm, lactate_threshold_hr_bpm, vo2max, cycling_ftp_w FROM athlete_profile WHERE user_id = <andys-uid>` returns the values.
4. **Provenance row spot-check.** On Neon:
   ```sql
   SELECT field_name, source, last_updated_at
   FROM athlete_profile_field_provenance
   WHERE user_id = <andys-uid>
   ORDER BY field_name;
   -- Expect 5 rows, all source='self_report', last_updated_at recent.
   ```
5. **Edit + re-save.** Change one value (e.g. body_weight_kg from 76.5 to 76.0), save. Confirm:
   - The row in `athlete_profile` updates.
   - The corresponding `athlete_profile_field_provenance` row has its `last_updated_at` bumped (`source` stays `'self_report'`).
6. **Clear field.** Empty the body_weight_kg input, save. Confirm:
   - `athlete_profile.body_weight_kg` becomes NULL.
   - `athlete_profile_field_provenance` row for body_weight_kg is **left intact** (PR6 doesn't delete on clear; D2's manual-override clear path will handle deletion). This is intentional — flagged in §6.
7. **G ON CONFLICT cleanup.** Trigger a COROS webhook delivery (or wait for the next sync). Confirm:
   - First delivery: row inserted into `cardio_log` with `coros_label_id` set.
   - Second delivery for the same `labelId`: row UPDATEd in place (no duplicate). Spot-check via `psql`: `SELECT id, date, distance_mi FROM cardio_log WHERE user_id=<uid> AND coros_label_id='<labelId>'` should return exactly one row.
   - No exceptions in the webhook log.
8. **Independent of PR6:** PR1 §5.0 COROS pre-deploy + PR3 §5.0 Polar pre-deploy + PR4 §5.0 Connections-tab spot-check + PR5 §5.0 onboarding spot-check are still owed if not yet completed.

### 5.1 PR7+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR6_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR5_Closing_Handoff_v1.md` (predecessor; carries the §5.1 candidate menu PR6 partially executed).
4. `aidstation-sources/Project_Backlog_v18.md` — current; PR7 may need to bump to v19 (see §5.4).
5. `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` §A.2 (prefill mechanics) — D2a needs this in working memory.

The candidate menu carries forward from PR5 §5.1 with one slot newly filled (D-51 column foundation = PR6) and the D2 candidate now split into D2a/D2b given PR6's scope re-cut.

#### Option D2a — Read-side prefill UX (recommended next)

Now unblocked by PR6's column foundation. Scope:

- **`KNOWN_PROFILE_FIELDS` registry** (Open Item #17, Closes With This PR Family): canonical list of profile fields eligible for provider prefill, keyed by `athlete_profile_field_provenance.field_name`. Seed from `athlete.PREFILL_ELIGIBLE_FIELDS` + per-field metadata (label for UI, unit, eligible-provider list, extractor function reference). Lives in new `routes/profile_fields.py` (single-purpose; matches PR2's `chain_registry.py` pattern).
- **Provider-data extractors** in new `routes/profile_extractors.py`: per-(field × provider) lookup functions. Each returns `(value, synced_at)` or `(None, None)`. Implementable today against existing data:
  - `extract_hrmax_coros(db, user_id)` → `MAX(cardio_log.max_hr) WHERE coros_label_id IS NOT NULL` over the last 90 days.
  - `extract_hrmax_polar(db, user_id)` → same shape against `polar_exercise_id`-scoped rows.
  - `extract_avg_nightly_sleep_coros(db, user_id)` → average derived from `coros_daily_summary.sleep_start_ms` / `sleep_end_ms` over the last 30 days.
  - `extract_avg_nightly_sleep_polar(db, user_id)` → `AVG(polar_sleep.total_sleep_min)` over the last 30 days.
  - `extract_body_weight_*` — currently None for both providers (no ingest captures it). Stub returns. Documented as "implement when wellness sync expands."
- **`/onboarding/prefill` route** in `routes/onboarding.py`: GET-only. Per-field cards rendering current value vs provider value(s) with provenance tag, plus stub `[Use provider]` / `[Keep current]` buttons that don't yet POST anywhere (D2b).
- **`templates/onboarding/prefill.html`** template: single-column comparison page; reuses the consent-disclosure pattern from `connect.html` for visual consistency.
- **Flip `_POST_STEP2_TARGET`** in `routes/onboarding.py` from `/profile?tab=athlete` to `/onboarding/prefill`. Single-line change. Continue / Skip from Step-2 lands on the prefill page next.

5+ files. Probably right at the ceiling. If overage, split write-side button wiring to D2b explicitly and ship D2a as read-only-with-stub-buttons.

#### Option D2b — Write-side prefill (clear path + manual_override flip)

Lands after D2a. Scope:

- **POST handler** for the per-field opt-in: `[Use provider]` writes `athlete_profile.<col>` = provider value + `athlete_profile_field_provenance.source = 'provider_<X>'` + bumps `last_updated_at`.
- **Manual-override flip in `_record_self_report_provenance`**: when the existing source is `'provider_*'` and the athlete saves a different value via `/profile?tab=profile`, flip source to `'manual_override'` instead of `'self_report'`. Today's PR6 always writes `'self_report'`; this requires reading the existing source first.
- **Manual-override clear path** (v5 §A.2.6): popover on the provenance tag with "Use provider value (X, last synced N days ago) instead." Restores prefill behavior + deletes the `manual_override` provenance row.
- **Tolerance-based re-prefill** (v5 §A.2.7): when a provider sync delivers a new value within tolerance of the stored value, silent update; outside tolerance, surface as passive notification. Probably ships as part of D2b's write-side or bundled with the next provider-sync ingest PR.

#### Option D3 — Locale-creation flow with Mapbox chain detection

Carries forward from PR5 §5.1 unchanged. Independent of D2 / D-51 work.

#### Option E — 14-day connect-provider nudge background job

Carries forward unchanged. Now even better-positioned: PR5's `/onboarding/connect` is the deep-link target.

#### Option F — Polar refresh-on-401

Carries forward unchanged. Watch item only.

#### Option H — Provider blueprint roster expansion

Carries forward unchanged.

### 5.2 Recommended sequence (revised post-PR6)

**D2a → D2b → E → D3**, with **F** as a watch item; **H** providers as opportunistic adds whenever an integration partner is ready.

D2a is the natural next step — the column foundation is now in place; both onboarding paths (PR4 management + PR5 Step 2) flash a "the prefill walkthrough ships next release" promise; D2a fulfills the *read-side* of that promise. D2b closes the loop by making the comparison-page buttons actually do something. After D2b ships, E (14-day nudge) becomes the highest-priority remaining v5 gap.

### 5.3 Standing items not on the critical path (carried from PR5 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged. Independent.
- **D-54 SQLite collapse** — unchanged. Catalog Migration Phase 5.
- **D-55 Garmin onto `provider_auth`** — paused. Onboarding screen + connect tab silently skip Garmin (not in `CONNECTION_PROVIDERS`); when Garmin reopens, the one-tuple append lights up both surfaces.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. Two real webhook handlers (COROS + Polar) write to `webhook_events`. PR6 doesn't touch the webhook path's persistence layer (G is on `cardio_log`, not `webhook_events`).
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — *storage blocker resolved by PR6*; the registry itself lands with D2a (now critical-path).
- **DATABASE.md update** — unchanged. PR6 adds 5 columns; the 8+ undocumented additions count holds (tracking the trend without bumping per-PR).
- **PROVIDERS_SCHEMA.md update** — unchanged. Two real providers visible on TWO surfaces now (Connections tab + onboarding); "Phase 1+ planned" framing increasingly stale.
- **lat/lng precision** (carry-over) — unchanged.
- **Polar refresh-on-401** — Option F. Watch item.
- **`coros_ingest._ingest_activity` ON CONFLICT cleanup** — *closed by PR6 §3.5*. Removed from carry-forward.
- **Provider-agnostic OAuth-start signature** (carry-over from PR5 §5.3) — unchanged. Lands with H.
- **`_POST_STEP2_TARGET` hardcoded to `/profile?tab=athlete`** (carry-over from PR5 §5.3) — unchanged. Single line in `routes/onboarding.py` that D2a flips to `/onboarding/prefill`.
- **Manual-override flip** (new this PR) — `_record_self_report_provenance` always writes `source='self_report'` because PR6 has no prefill mechanism; D2 PRs need to (a) read the existing source first, (b) flip `'provider_*'` → `'manual_override'` when an athlete edits a value that came from a provider sync. Documented inline + here.
- **Provenance-row deletion on field clear** (new this PR) — when an athlete clears a previously-set field (sets value to NULL), PR6 leaves the provenance row intact. v5 §A.2.6 manual-override clear path will handle deletion when D2 ships. Documented inline + here.
- **v17 backlog header cosmetic drift** (carry-over from PR5 §5.3) — *now archived*: v17 moved to predecessor block in v18, where its drift narrative is historical record only. No further action needed.
- **G ON CONFLICT cleanup against `cardio_log_polar_exercise_uidx` already done in PR3.** PR6's G mirrors that pattern for COROS. Wahoo-side cleanup is N/A — there's no Wahoo ingest path yet.

### 5.4 Backlog row update (next PR's first action)

PR6 bumped v17→v18 (this revision). PR7 will need to bump v18→v19 if and only if it lands a state-changing event (e.g. D2a ships → closes the read-side prefill UX bucket; would update D-50 row notes; might also touch Open Item #17 closure narrative).

**For PR7, owed v18 → v19 bump (mechanically-applicable per Rule #11):**

1. Copy `aidstation-sources/Project_Backlog_v18.md` to `aidstation-sources/Project_Backlog_v19.md`.
2. **Replace** the file-revision header on line 5:
   - Old text:
     ```
     **File revision:** v18 — 2026-05-14 (D-50 row status flip catching up PR5 + PR6: D-50 status cell now reads 🟢 PR1 + PR2 + PR3 + PR4 + PR5 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, `f4d2e75` PR4-merge, `34637d2` PR5-merge); 🟢 PR6 shipped 2026-05-14 on branch `claude/v5-closing-handoff-zg5i0`; 🟢 frontend Option D1 (Step-2 connect screen) shipped PR5; 🟡 D2 prefill UX (registry + comparison UI) deferred to PR7 — PR6 lays the column foundation. PR5 ships `/onboarding/connect` … PR6 (D-51 column foundation) adds 5 new `athlete_profile` columns … per `V5_Implementation_PR6_Closing_Handoff_v1.md`. No new D-row work this revision — pure status tracking)
     ```
   - New text (assuming PR7 = D2a):
     ```
     **File revision:** v19 — 2026-05-14 (D-50 row status flip catching up PR7: D-50 status cell now reads 🟢 PR1 + PR2 + PR3 + PR4 + PR5 + PR6 + PR7 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, `f4d2e75`, `34637d2`, `<PR6-merge>`, `<PR7-merge>`); 🟢 frontend Option D2a (read-side prefill UX) shipped PR7 closing Open Item #17; 🟡 D2b write-side button wiring + manual_override flip + clear-popover deferred. PR7 ships `KNOWN_PROFILE_FIELDS` registry (`routes/profile_fields.py`) + provider extractors (`routes/profile_extractors.py`) + `/onboarding/prefill` route + comparison template + `_POST_STEP2_TARGET` flip per `V5_Implementation_PR7_Closing_Handoff_v1.md`. No new D-row work this revision — pure status tracking)
     ```
3. **Prepend** to the predecessor revisions block (line 7-ish):
   ```
   - v18 — 2026-05-14 (D-50 row status flip catching up PR5 + PR6: …)  [verbatim from current v18 line 5 narrative]
   ```
4. **Update** the D-50 row (search for `D-50 ` near the body of the table) status cell from:
   ```
   🟢 PR1 + PR2 + PR3 + PR4 + PR5 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, `f4d2e75` PR4-merge, `34637d2` PR5-merge); 🟢 PR6 shipped 2026-05-14 on branch `claude/v5-closing-handoff-zg5i0`; 🟢 frontend Option D1 (Step-2 connect screen) shipped PR5; 🟡 D2 prefill UX (registry + comparison UI) deferred to PR7 — PR6 lays the column foundation; 🟡 D3 locale-creation pending
   ```
   to:
   ```
   🟢 PR1 + PR2 + PR3 + PR4 + PR5 + PR6 + PR7 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, `f4d2e75`, `34637d2`, `<PR6-merge>`, `<PR7-merge>`); 🟢 frontend D1 (Step-2 connect) + D2a (read-side prefill UX) shipped; 🟡 D2b write-side + D3 locale-creation + E nudge + F refresh-on-401 + H more providers pending
   ```
5. **Update** the "PR6+ candidate menu" narrative inside the D-50 Notes column to "PR8+ candidate menu" and shift the D2a entry from pending → shipped, leaving D2b at the top of the pending list.
6. **Bump** `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line from `Project_Backlog_v18.md` to `Project_Backlog_v19.md` (single-line edit).

**If PR7 is something other than D2a**, the narrative text changes but the file mechanics are identical (copy → header replace → predecessor prepend → D-50 row update → CLAUDE.md bump). Write the v19 header narrative to reflect what actually shipped.

---

## 6. Open items / honest flags

- **No live page-render or migration verification.** Same risk class as PR1 / PR2 / PR3 / PR4 / PR5. Flask isn't installed in the sandbox, so `/profile?tab=profile` can only be exercised at deploy time. The schema migration on Neon is similarly unobservable until deploy. AST-parse + Jinja-parse + stub-render with mocked `url_for` + `csrf_token` + `csp_nonce` + `get_flashed_messages` confirmed all template variables wire and the new fields render in both populated and empty states. The PR6 §5.0 manual click-through + `psql` spot-checks are mandatory before this is real.
- **`_record_self_report_provenance` always writes `'self_report'` in PR6.** Correct for PR6's reality (no prefill mechanism exists yet, so the `'provider_*'` source state never exists). Incorrect for D2's future world where provider syncs write `'provider_*'` rows and the manual-override flip is required. D2b will add the read-existing-source-first path. Documented inline in the helper docstring + here. Not a regression today.
- **Provenance row not deleted on field clear.** When an athlete clears a previously-set field (sets it to NULL via the form), `athlete_profile.<col>` becomes NULL but the corresponding `athlete_profile_field_provenance` row stays. v5 §A.2.6 manual-override clear path will handle deletion semantics when D2 ships; PR6 ships only the write-when-set-to-non-null path. Tactically: the stale provenance row doesn't hurt — D2a's read-side rendering will see the `source='self_report'` row and render an empty current-value cell, which is honest. D2b's write-side will tidy up.
- **5 provider-extractor functions in PR7's scope but currently impossible for body_weight.** Of the 5 prefill-eligible columns, body_weight has no provider source today (neither COROS nor Polar's existing ingest captures it). HRmax + lactate-threshold-HR + VO2max + cycling-FTP can be derived/sourced from existing data; body_weight extractor stub-returns None until Wahoo / Garmin wellness sync expands or a new wellness-pull endpoint ships. Documented in §5.1 D2a above.
- **Schema `vo2max` is a unit-less REAL.** Production convention is ml/kg/min; the column header in the form template names the unit. Storage doesn't enforce. If the field grows more user-visible (e.g. exposed in coaching context to Claude), consider renaming to `vo2max_ml_per_kg_min` or splitting into value + unit. Out of PR6 scope.
- **No tests added.** Inline `python3` execution of Jinja stub-render against two context variants + AST inspection of `PROFILE_FIELDS` + grep anchor checks are the closest this PR comes to test infrastructure. Same framing as PR1–PR5: a real `tests/` directory still doesn't exist; the right time to add one is whichever PR first hits a non-trivial integration test surface (probably D2b — write-side opt-in form processor against `athlete_profile_field_provenance` source-flip semantics is the first PR where unit tests are clearly higher-value than offline inline exercises).
- **5 substantive code files + 2 bookkeeping (v18 + CLAUDE.md) + 1 handoff = 8 total.** At the substantive ceiling (5). Same one-over pattern PR1, PR3, PR4, PR5 ran (5 substantive + handoff overhead). The athlete.py edit (5-line tuple extension + new `PREFILL_ELIGIBLE_FIELDS` constant) is genuinely a substantive coordinating change — `upsert_athlete_profile` filters kwargs by `PROFILE_FIELDS`, so without the tuple update the new kwargs would be silently dropped. The alternative (inline the field list in `routes/profile.py` save handler instead of extending `PROFILE_FIELDS`) would have been worse — it would split the canonical field-list across two files. Flagged for transparency.
- **G's ON CONFLICT path is PG-only.** Mirrors `polar_ingest._upsert_exercise` (PR3). The COROS webhook handler only runs in production (Postgres); local SQLite dev has no COROS webhook. If someone ever calls `_ingest_activity` in a SQLite test context (not currently a thing), it would error on the ON CONFLICT clause referencing the nonexistent partial UNIQUE index. Not a regression today.
- **D-51 row in backlog is broader than PR6 ships.** The D-51 row enumerates ~20+ fields across §A–§L that need new storage. PR6 lands the §A.2.1 prefill-eligible §F + §A subset (5 columns) — the slice that v5 §A.2 mechanics actually need. The remaining D-51 fields (Years of Training, Secondary Sports, Discipline Weighting, Peak Volume, Pack Load History, Previous Coaching, all §E benchmarks, §G schedule, §H multi-event substructure, most §I lifestyle, §L Athlete Network) are still pending. PR6 didn't update the D-51 status because (a) the row is too coarse for partial-completion tracking and (b) the v5 §A.2 storage is the actually-blocking subset. A future PR that tackles the remaining D-51 fields can update its status then. Not on the critical path; flagged for visibility.
- **`PREFILL_ELIGIBLE_FIELDS` placement in `athlete.py`.** Could have lived in `routes/profile.py` (where `_record_self_report_provenance` consumes it) or in a new `routes/profile_fields.py` (anticipating PR7's `KNOWN_PROFILE_FIELDS` registry). Placed in `athlete.py` because it's a subset of `PROFILE_FIELDS` which lives there — keeping the canonical field list and its prefill-eligible subset in the same module avoids the "what's the source of truth?" question. PR7 may pull both into `routes/profile_fields.py` or leave them; either is defensible.

---

## 7. Gut check

**What this session got right.**

- **Surfaced D2's blocking dependency before writing any code.** PR5 §5.1 D2 was scoped against the v5 spec narrative as if `athlete_profile.body_weight_kg` etc. existed. Rule #9 reconciliation against on-disk schema caught the gap before code landed. The Stop-and-ask trigger #5 (schema affecting inter-layer contract) loop with Andy resulted in a cleaner scope (D-51 foundation first, then D2a on top) instead of a half-broken D2 PR.
- **Picked the smallest defensible D-51 slice.** The D-51 row in the backlog is broad (~20+ fields). PR6 lands only the v5 §A.2.1 prefill-eligible §F + §A subset (5 columns) — precisely what D2 needs. Remaining D-51 fields stay pending until they're on the critical path. No premature schema heroics.
- **Bundled G as a free win.** ~30-line mechanical rewrite, lives in a different file area (`routes/coros_ingest.py`), no budget competition with the schema work, mirrors the PR3-shipped `polar_ingest` pattern exactly. The kind of cleanup that should ride the next PR that touches the area, not get a dedicated PR.
- **Honest "future release" footer on the form.** Same pattern as PR5's consent disclosure footer: the per-field prefill UX hasn't shipped; the form text says so. Athletes save manual values today; PR7 D2a lights up the prefill comparison flow on top.

**Risks.**

- **Live migration on Neon unexercised offline.** Same risk profile as every prior v5 PR. The 5 `ALTER TABLE ADD COLUMN IF NOT EXISTS` statements should be no-op-safe even on re-run, but the first-deploy run is the only real test. The §5.0 step 1 spot-check is the protection.
- **Provenance writes are PG-only and the table is in `_PG_MIGRATIONS` only.** SQLite dev path skips the write entirely (PG-only guard). If a test athlete ever runs locally against SQLite (Andy's dev path is Neon, but this could change), `athlete_profile.<col>` saves would persist but the corresponding provenance rows wouldn't — meaning the SQLite DB drifts from production schema state. Not a regression (the SQLite dev path was already in this state per Integration v4 §2.5 freeze) but worth being aware of.
- **Manual-override flip ships in PR6 as a permanent `'self_report'` write.** D2b will need to refactor `_record_self_report_provenance` to read the existing source first and conditionally flip. That refactor is straightforward (one extra query) but it's a planned-evolution, not a stable surface. Code comment + this section flag it.
- **Form bounds (e.g. body_weight_kg: 20-300) are heuristic.** No client-side validation means a bad value just round-trips to None via the `_num()` helper's try/except (a stringified non-number → None → silently drops the field). Aggressive bounds would be `min`/`max` HTML attrs — present, but browsers don't enforce them at form-submit on all platforms. Production validation is the floats-and-ints coercion in `_num`; for an athlete entering reasonable values this is fine.

**What might be missing.**

- **`hrmax_bpm` could be `INTEGER` or `SMALLINT`.** PR6 picks INTEGER (matches existing schema patterns: `cardio_log.avg_hr INTEGER`, etc.). SMALLINT would save bytes (2 vs 4) but the existing pattern is INTEGER so PR6 stays consistent. Cosmetic.
- **No `extracted_provider_value` column on `athlete_profile_field_provenance`.** v5 §A.2 spec doesn't require it — the comparison cards re-query the provider extractor at render time per A.2.2. But if the provider extractor is expensive (multi-table aggregate), caching the last-seen provider value on the provenance row would speed render. Out of PR6 scope; might surface as a perf optimization in PR7 D2a.
- **No `unit_label` column on `athlete_profile_field_provenance`.** Field labels and units live in the (future) `KNOWN_PROFILE_FIELDS` registry, not in the row. Right call — units are static metadata, not per-write data. Confirming the design choice was deliberate, not omitted.
- **No backfill for Andy's existing profile.** Andy's `athlete_profile` row exists; the 5 new columns will be NULL on first read post-migration. He has to manually fill them in via the form. For a sole-test-athlete app this is fine; for a launched product a "we noticed you haven't filled these out yet" prompt would be appropriate. Out of PR6 scope.

**Best argument against this session's scope.**

PR6 chose to pivot to D-51 column foundation + G after Andy's option-1 selection in the scoping question. The counter: the original PR5 §5.1 D2 specification *would* have shipped a usable surface even with mostly-empty comparison cards (each row reading `current value: — | provider value: —`). It would have been honest about the empty state and the column-foundation work could have followed in PR7. The trade-off: D2 with mostly-empty cards is genuinely useless and would have set a bad expectation; PR6 ships the foundation + immediately useful manual-entry surface (Andy can set his HRmax / FTP / weight today, which feeds Layer 3 calculations now), and PR7 D2a builds on real storage.

Counter to the counter: PR7 D2a now has more dependencies (registry + extractors + route + template, all needing real data to render meaningfully). It's a bigger PR than D2 would have been in the original spec. The risk is that PR7 hits the ceiling and has to split into D2a-extractors-only + D2a-UI. Acceptable risk — splitting is what the ceiling is for.

Alternatively, PR6 could have skipped G to keep substantive-files at 4. Counter: G is one file edit, lives in a different area, mirrors a pattern PR3 already shipped, and closes a PR5 §5.1 carry-forward item cleanly. The bookkeeping cost of a separate PR for a 30-line mechanical rewrite is multiple orders of magnitude greater than the cost of bundling. Drive-by absorbed.

---

## 8. Forward pointers

- **Next session:** PR7 = Option D2a (read-side prefill UX, recommended) or any of the other PR5/PR6 §5.1 carry-forward candidates. PR6 unblocks D2a by laying the column foundation; D2a flips PR5's `_POST_STEP2_TARGET` redirect.
- **Before next code lands:** PR6 §5.0 spot-check on the deployed app (schema migration on Neon + 5-field save round-trip + provenance row write + G ON CONFLICT cleanup). PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 are still owed if not yet completed.
- **First action of next session:** Rule #9 reconciliation. Specifically: confirm PR6 commit landed on `claude/v5-closing-handoff-zg5i0` (or merged to main with its own merge commit); confirm `init_db.py` has 5 new columns at all 4 sites; confirm `athlete.py:PROFILE_FIELDS` length is 14 and `PREFILL_ELIGIBLE_FIELDS` has the 5 expected names; confirm `routes/profile.py:_record_self_report_provenance` exists and is invoked from `edit()`; confirm `templates/profile/edit.html` has the 5 new form inputs under "Performance baselines"; confirm `routes/coros_ingest.py:_ingest_activity` uses ON CONFLICT (no remaining SELECT-then-UPDATE-or-INSERT); confirm `Project_Backlog_v18.md` exists with v17 archived to predecessor block; confirm `CLAUDE.md` "Authoritative current files" backlog line reads v18.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **PR6 has one deferred mechanical edit:** the v18 → v19 backlog bump for PR7's first action, spec'd verbatim in §5.4
- #12 numeric version suffixes (backlog now at v18; v19 lands in PR7 per §5.4)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR6 closing handoff. v5 onboarding D-51 column foundation (5 new `athlete_profile` columns: `body_weight_kg`, `hrmax_bpm`, `lactate_threshold_hr_bpm`, `vo2max`, `cycling_ftp_w`) shipped under `/profile?tab=profile` Performance Baselines section + `_record_self_report_provenance` writes to `athlete_profile_field_provenance` (PG-only, scaffolding for D2's manual_override flip). G — `coros_ingest._ingest_activity` ON CONFLICT cleanup against PR3's `cardio_log_coros_label_uidx` partial UNIQUE — bundled in. Backlog bumped v17 → v18. Next: Andy's choice among PR7 candidates in §5.1 (D2a recommended, now unblocked); v18 → v19 backlog bump mechanically spec'd for PR7's first action.*
