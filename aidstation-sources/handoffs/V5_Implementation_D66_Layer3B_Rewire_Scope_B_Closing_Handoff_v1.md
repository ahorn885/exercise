# V5 Implementation — D-66 Layer 3B Caller-Side Rewire (Scope B) Closing Handoff

**Session:** Single chat. Scope: D-66 Layer 3B Scope B per the predecessor handoff `V5_Implementation_D66_Layer3B_Rewire_Scope_A_Closing_Handoff_v1.md` §6.1 — drop the legacy `athlete_profile.target_event_name` + `target_event_date` columns from on-disk Postgres via `init_db.py` `_PG_MIGRATIONS` + trim the matching `DATABASE.md:311` schema bullet. Closes the schema-debt tail left over from Scope A (which write-froze the columns from the athlete-facing surface but kept them on disk); `race_events` is now the sole on-disk source of truth for target races.

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_D66_Layer3B_Rewire_Scope_A_Closing_Handoff_v1.md` (D-66 Layer 3B Scope A shipped 2026-05-18 earlier same day; PR #86 merged via `6898652`).

**Branch:** `claude/v5-layer3b-rewire-LuOi2` (harness-pinned for this session — name carries over from the harness-assigned Scope A branch even though Scope A's PR already merged to main; precedent: harness names mismatched with scope across the entire D-66 family).

**Status:** 🟢 5 files (2 substantive code/doc + 3 bookkeeping). Combined `tests/` 736 → 736 (zero deltas — no existing test coverage referenced the retired fields). **D-66 status flipped 🟢 Profile-tab UI + onboarding §H.2/§H.4 + account_nudges consumer-side UI + Layer 3B Scope A shipped → 🟢 ... + Scope A + Scope B shipped.** Layer 3B caller-side rewire Scope C (partial-update invalidation hooks per design §7.4) + D-72 type-alignment (trigger (ii) now fires) + manual §5.0 walkthrough remain as carry-forwards.

**Exactly at the 5-file ceiling.** First ceiling-hit (not breach) since the post-D-66-nudges-UI cadence resumed.

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| D-66 Layer 3B Scope A shipped on main per predecessor handoff | `git log --oneline -10` | ✅ `6898652` (merge PR #86) + `9354ce0` (D-66 Layer 3B Scope A) |
| `athlete.py` `PROFILE_FIELDS` no longer contains legacy literals | `grep "target_event_(name\|date)" athlete.py` | ✅ only the explanatory comment at line 21 remains |
| `routes/profile.py` `upsert_athlete_profile(...)` no longer passes legacy kwargs | grep | ✅ no matches |
| `templates/profile/edit.html` no longer renders legacy form inputs | grep `name="target_event` | ✅ no matches; Jinja pointer comment at line 72 |
| `Project_Backlog_v57.md` exists with D-66 row reflecting Scope A | grep | ✅ "+ Layer 3B Scope A 2026-05-18" |
| `CLAUDE.md` line 52 last-shipped narrative + line 254 First-session-checklist v57 ref | inspection | ✅ both bumped to Scope A / v57 |
| Cross-repo grep for `target_event_name\|target_event_date` in active code | grep | ✅ only the expected Scope B surfaces remain (`init_db.py` PG_SCHEMA + catch-up CREATE + backfill block + `DATABASE.md:311` schema doc) + spec docs (informational) + historical handoffs |
| Combined `tests/` 736 green baseline | `pytest tests/` | ✅ 736 passed after restoring `uv tool install pytest --with pydantic --with flask --with anthropic ...` (predecessor's env-drift workaround) |
| Working tree clean on `claude/v5-layer3b-rewire-LuOi2` | `git status` | ✅ |

**Rule #9 reconciliation:** all predecessor handoff claims match on-disk state. No drift to fix; proceeded directly to scope pick.

**Environmental drift surfaced (not code drift):** same recurrence as predecessors — the fresh container started without `pytest`/`pydantic`/`flask`/etc. installed in the uv-isolated pytest interpreter. Resolved by re-running `uv tool install --force pytest --with pydantic --with flask --with anthropic --with psycopg2-binary --with bcrypt --with zxcvbn --with openpyxl --with garth --with garminconnect --with fit-tool --with requests --with Flask-WTF --with Flask-Limiter --with pydantic-settings --with logfire`, then `PYTHONPATH=. pytest tests/`. Baseline 736 passed before any edits.

---

## 2. Session narrative — D-66 Layer 3B Scope B

Andy opened with the URL to the D-66 Scope A closing handoff + "lets work." Followed the operating model — read CLAUDE.md fully via Explore-agent delegation (Rule #13), ran Rule #9 verification (all green), surfaced state + the architect-recommended next-forward-move set from the predecessor handoff §6.1.

### 2.1 Scope pick (1-question gate)

Q1 (2026-05-18, 1-question gate): session scope. Andy picked **Scope B — column-drop migration** over Scope C (partial-update invalidation hooks; Trigger #7+#8 fire), Layer 4 Step 7 live LLM, and manual §5.0 walkthrough. The predecessor handoff §6.1 recommended Scope B next as "smaller; clears D-72; unblocks Scope C"; Scope B fires Trigger #5 (cross-layer schema change; PG DROP COLUMN is irreversible in production) so it needs a /plan-mode gate before any edits.

### 2.2 Plan-mode gate (Trigger #5 routing)

Surfaced the on-disk Scope B reality before composing the plan: confirmed three init_db.py surfaces (PG_SCHEMA top-of-file CREATE; catch-up CREATE in `_PG_MIGRATIONS` "Session 4 — athlete profile" at line 666; one-time backfill SQL string at lines 1185-1211) + DATABASE.md:311 schema doc + prior DROP COLUMN precedent at `init_db.py:1014`/`1028` (D-58 locale-FK migrations using `DO $$ ... END $$` only because they needed FK-name existence checks first). Confirmed **zero production read-paths** — the only `target_event_*` reference outside spec/handoff docs is the Scope A explanatory comment in `athlete.py:21`; no orchestrator, no Layer 4, no Layer 3B caller, no template reads the columns. The backfill migration is the only remaining reader.

Composed a 4-option plan with concrete rationale:
- **Option 1 (recommended):** PG_SCHEMA + catch-up CREATE trim + backfill retirement + 2 idempotent DROP COLUMN appends + DATABASE.md trim. 5 files exactly.
- **Option 2:** Option 1 + defense-in-depth SELECT-count gate before DROP. Rated NOT WORTH IT — gate can't fire in practice (Scope A write-froze the columns + backfill is idempotent + ran on every init).
- **Option 3:** Option 1 + flip D-72 status same session. Rated WORSE — pushes to 6 files, couples two unrelated decisions (D-72 is a typed-payload alignment question, not a schema change).
- **Option 4:** Defer DATABASE.md trim to a doc-sweep session. Rated WORSE — schema doc and actual schema must agree per DATABASE.md's own preamble.

Q2 (2026-05-18, /plan-mode gate): Andy picked **Option 1 as specced** — straight column drop + backfill retirement + DATABASE.md trim + D-72 status flip deferred to its own session.

### 2.3 Implementation order

1. **Edit `init_db.py` four spots in one file:**
   - Trim `PG_SCHEMA` `CREATE TABLE athlete_profile` (top of file, lines 21-23) — remove the two `target_event_*` column lines. Fresh PG deployments now never carry these columns.
   - Trim the matching catch-up `CREATE TABLE IF NOT EXISTS athlete_profile` in `_PG_MIGRATIONS` "Session 4 — athlete profile" (around line 666) — remove the two column names from the inline list. (This statement is `CREATE TABLE IF NOT EXISTS` — only runs on fresh DBs that somehow miss PG_SCHEMA; trimming is doc-consistency with PG_SCHEMA, not behavior-bearing.)
   - Retire the D-66 §10 one-time backfill SQL string (lines 1185-1211) — replace with a 7-line retirement-marker comment explaining the backfill is now retired (already ran on every init since the D-66 DB foundation PR + Scope A write-froze the only write surface so no row can carry a non-migrated value + the SELECT would error after the drop).
   - Append two new idempotent migrations at the end of `_PG_MIGRATIONS`:
     - `ALTER TABLE athlete_profile DROP COLUMN IF EXISTS target_event_name`
     - `ALTER TABLE athlete_profile DROP COLUMN IF EXISTS target_event_date`
   - Bare-statement `DROP COLUMN IF EXISTS` form (no `DO $$ ... END $$` wrapper) — the prior D-58 wrapper was only needed because it checked FK-name existence first; plain column drops don't need it.
2. **Edit `DATABASE.md:311`** — drop the two column names from the `athlete_profile` Columns bullet + add a retirement-marker sentence pointing future readers to the `race_events` section as the live source of truth.
3. **Bookkeeping:** `Project_Backlog_v57.md` → `_v58.md` (Rule #12; v57 retained) + CLAUDE.md update (line 52 last-shipped narrative + line 254 First-session-checklist Backlog ref) + this handoff. See §9.

### 2.4 Architectural choices on the record

- **Bare-statement `ALTER TABLE ... DROP COLUMN IF EXISTS ...` form.** Postgres `DROP COLUMN IF EXISTS` is idempotent at the statement level — `IF EXISTS` makes a second run a no-op without needing transaction-control wrappers. The prior D-58 `DO $$ ... END $$` wrapper was only necessary because the FK-rename migrations checked `pg_constraint` for constraint-name existence before dropping; plain column drops have no such precondition. Simpler is better.
- **Backfill retirement in the same revision as the column drop.** Keeping the backfill SQL string in `_PG_MIGRATIONS` after the columns are dropped would crash every subsequent init (the SELECT references `target_event_name` / `target_event_date::date` which no longer exist on the table). Retiring the string + leaving a 7-line retirement-marker comment is loud-over-silent for future devs reading the migration history. The comment preserves the chain-of-evidence: backfill ran for ~24h between D-66 DB foundation and Scope B; Andy's row was migrated to `race_events`; backfill is idempotent via the `NOT EXISTS` guard on `is_target_event=TRUE` so re-running it on a non-empty `race_events` was a no-op.
- **No defense-in-depth pre-drop gate.** The handoff §6.1 floated "gate the DROP behind a check for any non-NULL values not already in `race_events` (defense-in-depth even though the backfill should have caught all)." Rated NOT WORTH IT after on-disk audit: the gate condition can never fire in practice — Scope A write-froze the columns from the athlete-facing surface (no new athlete-profile rows can carry non-NULL legacy values), the backfill is idempotent + ran on every init since the D-66 DB foundation PR, and there's no other write path. Adding defensive code that physically cannot trigger is comment-rot dressed as caution + becomes dead code future devs have to reason about. Skip it.
- **DATABASE.md trim now (not deferred to a doc-sweep session).** The schema doc and the actual schema must agree per DATABASE.md's own preamble: "Live source of truth: `init_db.py`'s `PG_SCHEMA`." Leaving DATABASE.md:311 listing `target_event_name` + `target_event_date` as `athlete_profile` columns post-drop would make the doc a stale claim — fail-loud failure mode is broken; would persist as a subtle trap for the next dev reading DATABASE.md before init_db.py. The trim adds a retirement-marker sentence ("dropped in D-66 Layer 3B Scope B; target races now live in `race_events`") so future readers don't think the columns are still present + know where to look for the live source of truth.
- **D-72 status flip deferred to its own future session.** D-72 ("Locale-FK type alignment across typed payloads — `Layer2CPayload.locale_id: str` vs `Layer3BPayload.event_locale_id: str` vs `RaceEventPayload.event_locale_id: int`") is a typed-payload alignment question, not a schema change. D-72's defer trigger (ii) now fires post-Scope B ("D-66 profile-tab UI follow-on lands (will force the legacy `target_event_*` column retirement)") so D-72 is now a concrete active carry-forward. But bundling its status flip + initial scope into this session would breach the 5-file ceiling AND couple the schema-drop decision (settled) with the typed-payload alignment decision (still has 3 plausible paths per the row text). D-72 deserves its own scope-pick session.
- **Did NOT touch the `routes/onboarding.py:710` docstring reference to "legacy athlete_profile.target_event_*".** The docstring is informational — describes how target rows could have existed via the one-time migration. Post-Scope B it's slightly past-tense-out-of-sync but not load-bearing; rewording belongs in a follow-on doc-sweep session, not Scope B.

### 2.5 Stop-and-ask triggers retrospective

- **Trigger #5 (schema/inter-layer-contract amendments):** ✅ FIRED — PG column drop is irreversible in production. Routed via the /plan-mode AskUserQuestion gate in §2.2; Andy picked Option 1.
- **Trigger #7 (new partial-update invalidation rule):** did NOT fire — Scope B is a schema drop only; the partial-update hooks land with Scope C.
- **Trigger #8 (architectural alternatives with real tradeoffs):** ✅ FIRED IMPLICITLY (Options 1-4 + defense-in-depth gate + D-72 disposition). Resolved in the same /plan-mode gate.
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows. D-66 status flips; D-72 already exists and now has its defer-trigger (ii) firing.

---

## 3. File-by-file substantive edits

### 3.1 `init_db.py`

Four spots edited in one file:

#### 3.1.1 `PG_SCHEMA` `CREATE TABLE athlete_profile` (lines 21-23)

Before:

```python
        primary_sport TEXT,
        target_event_name TEXT,
        target_event_date TEXT,
        weekly_hours_target REAL,
```

After:

```python
        primary_sport TEXT,
        weekly_hours_target REAL,
```

Fresh PG deployments now never carry the legacy columns.

#### 3.1.2 `_PG_MIGRATIONS` catch-up `CREATE TABLE IF NOT EXISTS athlete_profile` (line 666)

Before:

```python
    # Session 4 — athlete profile.
    """CREATE TABLE IF NOT EXISTS athlete_profile (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        date_of_birth TEXT, sex TEXT, height_cm REAL,
        primary_sport TEXT, target_event_name TEXT, target_event_date TEXT,
        weekly_hours_target REAL, training_window TEXT, notes TEXT,
        ...
```

After:

```python
    # Session 4 — athlete profile.
    """CREATE TABLE IF NOT EXISTS athlete_profile (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        date_of_birth TEXT, sex TEXT, height_cm REAL,
        primary_sport TEXT,
        weekly_hours_target REAL, training_window TEXT, notes TEXT,
        ...
```

This catch-up statement is `CREATE TABLE IF NOT EXISTS` — only fires on fresh DBs that somehow miss `PG_SCHEMA` (defensive). Trimming here is doc-consistency with the trimmed `PG_SCHEMA` above, not behavior-bearing.

#### 3.1.3 Backfill retirement (lines 1185-1211 replaced)

Before:

```python
    "CREATE INDEX IF NOT EXISTS race_route_locale_equipment_locale_idx ON race_route_locale_equipment (race_route_locale_id)",
    # D-66 §10 one-time migration of legacy athlete_profile.target_event_*
    # rows into race_events. Idempotent via the NOT EXISTS guard. race_format
    # defaults to 'single_day' — Andy will update his Pocket Gopher Extreme
    # row to 'expedition_ar' via the profile UI when that ships. The athlete_profile
    # columns are kept in place per §3.4 deprecation note; a future cleanup
    # PR drops them once all rows have migrated cleanly. target_event_date
    # is TEXT in the legacy schema; the empty-string + NULL guards skip rows
    # where it was never set.
    """INSERT INTO race_events
        (user_id, name, event_date, race_format, is_target_event, etl_version_set)
        SELECT
            user_id,
            target_event_name,
            target_event_date::date,
            'single_day',
            TRUE,
            '{"race_events_v1": "migration_from_athlete_profile_row"}'::jsonb
        FROM athlete_profile
        WHERE target_event_name IS NOT NULL
          AND target_event_name <> ''
          AND target_event_date IS NOT NULL
          AND target_event_date <> ''
          AND NOT EXISTS (
              SELECT 1 FROM race_events
              WHERE race_events.user_id = athlete_profile.user_id
                AND race_events.is_target_event = TRUE
          )""",
]
```

After:

```python
    "CREATE INDEX IF NOT EXISTS race_route_locale_equipment_locale_idx ON race_route_locale_equipment (race_route_locale_id)",
    # D-66 Layer 3B Scope B — drop the legacy athlete_profile.target_event_*
    # columns. The one-time backfill that lived here previously (INSERT INTO
    # race_events SELECT FROM athlete_profile WHERE target_event_name IS NOT
    # NULL ...) ran on every init since the D-66 DB foundation PR and is now
    # retired: Scope A write-froze the columns from the athlete-facing surface
    # so no row can arrive with a non-migrated value, and `DROP COLUMN IF
    # EXISTS` is idempotent for the columns themselves.
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS target_event_name",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS target_event_date",
]
```

The retirement-marker comment preserves the chain-of-evidence so future devs reading migration history understand what happened. Idempotence is preserved across init runs: existing Vercel-prod DB has Andy's target-race row already in `race_events`; the DROP COLUMN drops the legacy columns once + no-ops on every subsequent init.

### 3.2 `DATABASE.md:310-318`

Before:

```markdown
- Columns: `user_id` (PK + FK), `date_of_birth`, `sex`, `height_cm`,
  `primary_sport`, `target_event_name`, `target_event_date`,
  `weekly_hours_target`, `training_window`, `notes`, `updated_at`.
```

After:

```markdown
- Columns: `user_id` (PK + FK), `date_of_birth`, `sex`, `height_cm`,
  `primary_sport`, `weekly_hours_target`, `training_window`, `notes`,
  `updated_at`. (The legacy `target_event_name` + `target_event_date`
  columns were dropped in D-66 Layer 3B Scope B; target races now live
  in `race_events` as their sole source of truth — see the
  `race_events` section.)
```

Retirement-marker sentence points future readers at `race_events` so the doc stops misleading anyone who reads DATABASE.md before init_db.py.

---

## 4. Test additions

**Zero test deltas this session.** Combined `tests/` 736 → 736 in 2.21s.

- Pre-edit grep across `tests/` for `target_event_name` / `target_event_date`: zero matches (same as Scope A).
- Post-edit `PYTHONPATH=. pytest tests/`: 736 passed.

No test coverage was added because:
- The column drop is pure schema deletion — no new behavior to exercise.
- `DROP COLUMN IF EXISTS` is idempotent both on fresh-DB inits (PG_SCHEMA already excludes the columns; DROP runs against absent columns + no-ops) and on existing-DB Vercel-prod migrations (DROP runs once + drops the columns; subsequent inits no-op).
- The `_FakeConn`/`_FakeCursor` test pattern used by `tests/test_race_events_repo.py` + `tests/test_onboarding_race_events.py` doesn't exercise the migration runner — adding a "DROP COLUMN migration runs" regression test would test psycopg2 + Postgres behavior, not Scope B's retirement.
- Visual regression on the DATABASE.md trim is caught by §5 doc-walk.

---

## 5. Manual §5.0 verification steps for Andy's walkthrough

Run on `https://aidstation-pro.vercel.app/` (or local dev) after PR merge. Layers on top of the D-66 onboarding 12-scenario suite (predecessor-of-predecessor handoff §6) + 6-scenario nudge UI suite (Scope A predecessor handoff §5) + 6-scenario Scope A suite (`V5_Implementation_D66_Layer3B_Rewire_Scope_A_Closing_Handoff_v1.md` §5).

1. **Vercel init runs the DROP COLUMN migration cleanly.** After the PR merges + Vercel deploys, check the deploy logs for `_PG_MIGRATIONS` execution; confirm no error on either `ALTER TABLE athlete_profile DROP COLUMN IF EXISTS target_event_name` or `... target_event_date`. psql spot-check: `\d athlete_profile` should no longer show `target_event_name` / `target_event_date` columns. (Andy's row in `race_events` is unaffected — preserved by the now-retired backfill which ran in prior inits.)
2. **Second Vercel init is a clean no-op.** Re-trigger an init (e.g., redeploy on Vercel or `flask init-db` locally); confirm both DROP COLUMN statements no-op silently via the `IF EXISTS` guard.
3. **Fresh-DB local init succeeds.** Drop your local PG DB + re-run init from scratch; confirm (a) `CREATE TABLE athlete_profile` from `PG_SCHEMA` doesn't include the legacy columns (so the DROP COLUMN migrations don't trip the `IF EXISTS` guard in any user-visible way), (b) `init_db.py` completes without error.
4. **POST `/profile/` with legacy form-field names still ignored.** Manually craft a POST against `/profile/` including `target_event_name=foo&target_event_date=2026-09-01` in the body. Confirm HTTP 302 redirect to `/profile/` (Scope A's `PROFILE_FIELDS` silent-filter still works; no crash because the helper drops unknown keys before composing the INSERT/UPDATE SQL). psql spot-check: `\d athlete_profile` confirms the legacy columns are physically gone, so even if `PROFILE_FIELDS` were ever extended to include them again, the INSERT/UPDATE would error rather than write the stale slug values.
5. **Race events tab still pulls from `race_events`.** Open devtools network tab on `/profile?tab=race-events`; confirm the rendered race list matches `SELECT name, event_date, is_target_event FROM race_events WHERE user_id = <Andy>` — Andy's pre-existing target-race row from the backfill is still visible.
6. **DATABASE.md schema doc agrees with on-disk reality.** Open root `DATABASE.md` at line 305-318; confirm the `athlete_profile` Columns bullet no longer lists `target_event_name` / `target_event_date` + the retirement-marker sentence is present + points at the `race_events` section.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward moves

D-66 is now one substantial step closer to fully complete. The athlete-facing surface (profile-tab UI + onboarding + nudges) was closed by prior sessions; the form retirement was Scope A; the schema cleanup is Scope B (this session). Remaining D-66 follow-on:

1. **Layer 3B caller-side rewire Scope C** — wire partial-update invalidation hooks per `Race_Events_D66_Design_v1.md` §7.4 + §9. **Trigger #7 fires** (new partial-update invalidation rule) + **Trigger #8 fires implicitly** (the hooks need new web-handler → `Layer4Cache` facade glue; the cache lives in `layer4/cache.py` but isn't currently accessible from `routes/race_events.py` writers — multiple architectural options for the glue surface). Needs `/plan`-mode gate before implementing. ~3-5 files. Plan considerations: (a) decide the glue surface (direct import vs orchestrator helper vs blueprint-level wrapper); (b) confirm the invalidation rules per design §9 (target-flag flip → T1 plan refresh cascade; route-locale CRUD → race-week-brief cache invalidation; race-event field edits → re-run scope depends on which field); (c) decide which writer routes get hooks — `routes/race_events.py` has 10 write routes; only some need invalidation triggers. **D-72 trigger (i) would also fire here** ("Layer 3B's caller-side rewires from `athlete_profile.target_event_*` to `race_events WHERE is_target_event=true` per `Race_Events_D66_Design_v1.md` §8.1") but Scope C's narrower framing — invalidation-hook wiring only, not full caller-side rewire — may not fully discharge it. Worth clarifying scope at the /plan-mode gate.

2. **D-72 Locale-FK type alignment across typed payloads** (now actively triggered) — Scope B fired D-72's defer trigger (ii). D-72 is the question: `Layer2CPayload.locale_id: str` vs `Layer3BPayload.event_locale_id: str` vs `RaceEventPayload.event_locale_id: int` — three payloads, two key types for the same logical entity (FK to `locale_profiles` row). v1 accepts the mismatch but it's now a concrete carry-forward. Three plausible paths per the row text: (a) **int SERIAL id everywhere** (Layer 2C + Layer 3B swap str → int; cleaner FKs; smaller in memory; stable across slug renames); (b) **slug everywhere** (RaceEventPayload swaps int → str; revert the D-66 path-2 SERIAL id pick or keep the id column but reference via slug; matches PR18's composite-PK refactor more directly; human-readable in logs); (c) **document the split + pick per-payload**. **Trigger #5 fires** (cross-layer schema change touching `Layer2C_Spec.md` §7 + `Layer3_3B_Spec.md` §7 + `layer4/context.py` typed payload contracts). Needs `/plan`-mode gate. ~5-8 files depending on path.

Recommendation: Scope C next session (closes the D-66 family completely + may or may not discharge D-72 (i) depending on framing); D-72 in a session after.

### 6.2 Orthogonal candidates

3. **Layer 4 Step 7 live LLM integration** — orthogonal to D-66. First end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call. Cache + telemetry from Steps 5/6 make it safer. Needs `ANTHROPIC_API_KEY` in the environment.

4. **Manual §5.0 walkthrough** of the accumulated D-66 family scenarios — 12 onboarding scenarios + 6 nudge UI + 6 Scope A + 6 Scope B = 30 scenarios total now. Could be split across multiple Andy walkthrough sessions.

### 6.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully. (Delegate to Explore agent — it's now ~110k+ tokens.)
2. **Second re-read:** this handoff.
3. **Third re-read:** depends on scope.
   - Scope C → `Race_Events_D66_Design_v1.md` §7.4 + §9 (partial-update invalidation rules) + `layer4/cache.py` (Layer4Cache facade) + `layer4/cache_invalidation.py` (existing eviction patterns per `evict_on_layer_change` / `policy_for_layer`) + `routes/race_events.py` (writer side; needs new glue to reach the facade) + `routes/onboarding.py` Step 3c/3d target-race + route-locales POST handlers (also writer surfaces; should land hooks consistently with `routes/race_events.py`).
   - D-72 → `layer4/context.py:337` (Layer2CPayload.locale_id) + `:795` (Layer3BPayload.event_locale_id) + `:933` (RaceEventPayload.event_locale_id) + `Layer2C_Spec.md` §7 + `Layer3_3B_Spec.md` §7 + the D-58 SERIAL id migration story at `init_db.py:1014`-`1028` for prior precedent.
   - Manual walkthrough → §5 above + Scope A predecessor §5 + nudge UI predecessor §5 + onboarding predecessor §6.
4. **Branch:** cut fresh off post-merge main OR stay on the harness pin (precedent: every D-66 session including this one has stayed harness-pinned).
5. **Scope B is complete:** the columns are physically gone from on-disk Postgres + DATABASE.md agrees with reality. Athletes enter target races only via `/profile?tab=race-events` (CRUD UI) or `/onboarding/target-race` (Step 3c onboarding). Layer 3B's orchestrator still hasn't been rewired to consume `race_events` at read-time (no orchestrator code exists yet) — that lands when the Layer 4 orchestrator is implemented; the existing `load_target_race_event_payload(db, user_id)` helper in `race_events_repo.py` is ready for it.

---

## 7. Open items / decisions pinned this session

### 7.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Q1 scope = Layer 3B rewire Scope B (column-drop migration) | Andy 2026-05-18 | Handoff §6.1-recommended next; smaller than Scope C; clears D-72 trigger (ii); unblocks Scope C |
| 2 | Q2 plan = Option 1 as specced (column drop + backfill retirement + DATABASE.md trim, NO defense-in-depth gate, D-72 status flip deferred) | Andy 2026-05-18 | /plan-mode gate (Trigger #5 fired); other options ruled WORSE per §2.2 |
| 3 | Bare-statement `DROP COLUMN IF EXISTS` form (over `DO $$ ... END $$` wrapper) | Architect-pick | Simpler; prior `DO $$` precedent was only for FK-existence checks; plain DROP doesn't need it |
| 4 | Retire the D-66 §10 one-time backfill SQL string in the same revision as the column drop | Architect-pick | Keeping the backfill would crash subsequent inits post-DROP (SELECT references dropped columns); retirement-marker comment preserves chain-of-evidence |
| 5 | NO defense-in-depth pre-drop SELECT-count gate | Architect-pick | Gate can never fire (Scope A write-froze the columns + backfill is idempotent + ran on every init); adding dead-branch defensive code is comment-rot |
| 6 | DATABASE.md:311 trim in the same revision | Architect-pick | Schema doc and actual schema must agree per DATABASE.md's own "Live source of truth: init_db.py's PG_SCHEMA" preamble |
| 7 | D-72 status flip deferred to its own session | Architect-pick | D-72 is a typed-payload alignment question, not a schema change; bundling would breach 5-file ceiling + couple unrelated decisions |
| 8 | Did NOT touch `routes/onboarding.py:710` docstring reference to "legacy athlete_profile.target_event_*" | Architect-pick | Informational past-tense out-of-sync but not load-bearing; doc-sweep follow-on nit |
| 9 | No test deltas | Architect-pick | Column drop is pure schema deletion + `DROP COLUMN IF EXISTS` is idempotent + no existing tests reference the legacy fields; a regression test would test psycopg2 + Postgres behavior, not Scope B |
| 10 | 5 files total (2 substantive code/doc + 3 bookkeeping) | Necessitated | Exactly at the 5-file ceiling — first ceiling-hit (not breach) since the post-D-66-nudges-UI cadence resumed |

### 7.2 Carry-forward — Layer 3B rewire Scope C (next session)

See §6.1 item 1. Trigger #7 + #8 fire; needs `/plan`-mode gate.

### 7.3 Carry-forward — D-72 type-alignment (now actively triggered)

D-72's defer trigger (ii) fired with Scope B. D-72 is now a concrete next-step candidate (own scope-pick session). Trigger #5 will fire; needs `/plan`-mode gate.

### 7.4 Carry-forward — D-66 §5.0 walkthrough (accumulating)

30 scenarios total now: 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B (§5 above). Andy walks on Vercel after PR merge.

### 7.5 Carry-forward — `_v57.md` retained per Rule #12

`Project_Backlog_v57.md` preserved alongside the new `_v58.md` per the numeric-version-suffix rule. The historical chain stays intact (v55 → v56 → v57 → v58).

### 7.6 Carry-forward — `routes/onboarding.py:710` docstring tense

Informational past-tense out-of-sync after Scope B (references "legacy athlete_profile.target_event_*" as if columns still exist). Not load-bearing; doc-sweep follow-on nit.

---

## 8. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `init_db.py` `PG_SCHEMA` no longer has `target_event_name TEXT` / `target_event_date TEXT` | ✅ inspection — the 2 lines are gone between `primary_sport TEXT,` and `weekly_hours_target REAL,` |
| `init_db.py` `_PG_MIGRATIONS` catch-up CREATE no longer has those columns | ✅ inspection — `primary_sport TEXT,` followed by `weekly_hours_target REAL, ...` |
| `init_db.py` D-66 §10 backfill SQL string retired; retirement-marker comment in place | ✅ inspection — 7-line comment ending with the two DROP COLUMN appends |
| `init_db.py` two new DROP COLUMN migrations appended at end of `_PG_MIGRATIONS` | ✅ grep `DROP COLUMN IF EXISTS target_event` returns 2 matches |
| `DATABASE.md:310-318` `athlete_profile` Columns bullet no longer lists legacy columns; retirement-marker sentence present | ✅ inspection |
| Combined `tests/` 736 green | ✅ `PYTHONPATH=. pytest tests/` → 736 passed in 2.21s |
| Cross-repo grep for `target_event_name\|target_event_date` returns only the expected surfaces (new init_db.py comment + 2 DROP COLUMN statements + new DATABASE.md retirement marker + Scope A explanatory comment in `athlete.py:21` + spec docs + historical handoffs) | ✅ no surprises |
| `Project_Backlog_v58.md` exists; v57 retained | ✅ `ls -la` |
| `Project_Backlog_v58.md` D-66 row status updated to "🟢 ... + Layer 3B Scope A + Scope B shipped" | ✅ grep returns 1 match |
| `Project_Backlog_v58.md` file revision header bumped to v58 with Scope B narrative | ✅ grep `File revision:\*\* v58` returns 1 match |
| `Project_Backlog_v58.md` D-66 row notes "DROPPED 2026-05-18 in Scope B" in the v1-schema-was-only sentence | ✅ inspection |
| `CLAUDE.md` line 52 last-shipped narrative bumped to D-66 Layer 3B Scope B | ✅ inspection — line 52 head reads "Last shipped session: **D-66 Layer 3B Scope B — dropped the legacy..." |
| `CLAUDE.md` Scope A demoted to "Predecessor — D-66 Layer 3B Scope A: ..." | ✅ inspection |
| `CLAUDE.md` line 254 First-session-checklist Backlog ref bumped to v58 | ✅ grep `Project_Backlog_v58` returns 1 match at line 254 |
| `athlete.py:21` Scope A explanatory comment unchanged | ✅ inspection — text intact |
| `routes/onboarding.py:710` docstring untouched (deferred doc-sweep nit) | ✅ inspection |
| `Race_Events_D66_Design_v1.md` §10 backfill design language untouched (spec doc; historical context) | ✅ inspection |

---

## 9. Files shipped this session

**Substantive code/doc (2 modified):**
1. Modified `init_db.py` — four-spot edit in one file: trimmed `PG_SCHEMA` `CREATE TABLE athlete_profile` (lines 21-23) + trimmed catch-up `CREATE TABLE IF NOT EXISTS athlete_profile` in `_PG_MIGRATIONS` "Session 4 — athlete profile" (line 666) + retired the D-66 §10 one-time backfill SQL string (lines 1185-1211, replaced with retirement-marker comment) + appended two idempotent `ALTER TABLE athlete_profile DROP COLUMN IF EXISTS target_event_{name,date}` migrations at end of `_PG_MIGRATIONS`.
2. Modified `DATABASE.md:310-318` — trimmed the two legacy column names from the `athlete_profile` Columns bullet + added a retirement-marker sentence pointing future readers at the `race_events` section as the live source of truth.

**Bookkeeping (3 files):**
3. New `aidstation-sources/Project_Backlog_v58.md` (per Rule #12; v57 retained as predecessor) — file revision header rewritten for Scope B; D-66 row status flipped to include "+ Scope B 2026-05-18" + v58-revision parenthetical narrative; D-72 trigger (ii) firing flagged in the Scope B narrative.
4. Modified `aidstation-sources/CLAUDE.md` — last-shipped-session narrative bump (line 52: D-66 Layer 3B Scope A → D-66 Layer 3B Scope B; demotes Scope A to "Predecessor —" tail reference); First-session-checklist Backlog ref bumped (line 254: v57 → v58).
5. New `aidstation-sources/handoffs/V5_Implementation_D66_Layer3B_Rewire_Scope_B_Closing_Handoff_v1.md` (this file).

**5 files total. Exactly at the 5-file ceiling.** First ceiling-hit (not breach) since the post-D-66-nudges-UI cadence resumed; justified by the substantive edits being concentrated in one large file (`init_db.py` four-spot edit) + one small doc file (`DATABASE.md`) + the mandatory bookkeeping floor (Backlog bump per Rule #12 + CLAUDE.md last-shipped narrative bump + handoff).

---

## 10. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **D-72 Locale-FK type alignment across typed payloads** — defer trigger (ii) FIRED this session; now an active carry-forward awaiting scope-pick session.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward; needs `ANTHROPIC_API_KEY`.
- **Partial-update invalidation hooks per design §7.4 (Scope C)** — concrete carry-forward; recommended next D-66 follow-on.
- **D-66 §5.0 walkthrough (30 scenarios accumulating)** — 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B. Andy walks on Vercel after PR merges.
- **`routes/onboarding.py:710` docstring tense** — informational past-tense out-of-sync after Scope B; doc-sweep follow-on nit.

---

**End of handoff.**
