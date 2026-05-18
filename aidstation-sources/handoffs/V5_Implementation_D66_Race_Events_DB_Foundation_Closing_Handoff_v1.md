# V5 Implementation — D-66 Race-Event DB Foundation Closing Handoff

**Session:** Single chat. Scope: D-66 race-event DB foundation per `Race_Events_D66_Design_v1.md` §3 + §10. Closes the storage gap for the D-66 design wave's `race_events` + `race_route_locales` + `race_route_locale_equipment` tables; pure data-access layer consumable by the Layer 4 race-week-brief orchestrator + the deferred profile-tab UI follow-on PR. Layer 4 Step 4e race-week-brief shipped 2026-05-18 with the typed `RaceEventPayload` in-memory contract but no DB layer to persist or serve athletes — this revision closes that gap.

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_Layer4_Step6_PatternAPolish_Closing_Handoff_v1.md` (Layer 4 Step 6 Pattern A polish shipped 2026-05-18 earlier same day; commit `4c9145e` on origin/main via PR #81).

**Branch:** `claude/pattern-a-polish-closing-fAOxb` (harness-pinned for this session — name carries over from the harness's Step 6 closing-handoff theme even though this session is D-66 DB foundation; precedent: harness names mismatched with scope across every prior Layer 4 implementation session).

**Status:** 🟢 3 substantive code files + 3 bookkeeping = 6 files. Combined `tests/` 662 → 684 net new (22 in new `tests/test_race_events_repo.py`) in 1.04s. **D-66 status flipped 🟢 Design wave shipped → 🟢 DB foundation shipped.**

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| Step 6 shipped on `main` per Step 6 handoff | `git log --oneline -10` | ✅ commits `8e58c8c` (merge PR #81) + `4c9145e` |
| `layer4/telemetry.py` (~280 lines) + `plan_create.py` + `cached_wrappers.py` + `plan_refresh.py` exist | `ls` + `wc -l` | ✅ all four modules present (323 / 1320 / 510 / 1222 lines) |
| `CallMetrics` + `TelemetryAggregator` + `MODEL_PRICING_USD_PER_M` in `layer4/__init__.py` | grep | ✅ all three re-exports in place |
| Combined `tests/` 662 green | `python -m pytest tests/ -q` | ✅ 662 passed in 1.71s |
| Working tree clean on `claude/pattern-a-polish-closing-fAOxb` | `git status` | ✅ |
| `Project_Backlog_v52.md` exists; CLAUDE.md backlog ref reads `Project_Backlog_v52.md` | `ls` + grep | ✅ |

**Rule #9 surfaced a contract gap that became this session's Trigger #5:**
- `Race_Events_D66_Design_v1.md` §3.1 specifies `race_events.event_locale_id BIGINT REFERENCES locale_profiles(id) ON DELETE SET NULL`.
- On-disk `locale_profiles` has composite PK `(user_id, locale)` with no `id` column (PR18 settled on the composite-PK refactor; D-60's `locale_equipment_overrides` + `locale_toggle_overrides` worked around the same gap by using composite FK pairs — see `init_db.py:968-970` comment).
- Compounding: pre-existing inconsistency in `layer4/context.py` — `Layer3BPayload.event_locale_id: str | None` (line 795; matches storage slug) vs `RaceEventPayload.event_locale_id: int | None` (line 933; matches design doc's intended int FK).

Surfaced + routed via `AskUserQuestion` before any code landed.

---

## 2. Session narrative — D-66 DB foundation (Andy 2026-05-18)

Andy opened with the URL to the Step 6 closing handoff + "lets work." Followed operating model — read CLAUDE.md fully (Rule #13), ran Rule #9 verification, surfaced state, offered the architect-recommended next-forward-move set from the Step 6 handoff §4.1.

### 2.1 Scope picks

**Round 1 (2026-05-18, 1-question):** session scope. Andy picked **v5 onboarding implementation PR** (over Step 7 live LLM / Step 8 telemetry tuning / D-50 wiring resumption).

**Round 2 (2026-05-18, 1-question):** sub-scope. After surveying the v5 onboarding state-by-area (D-58 prefill UX missing backend + UI; D-59 locale Mapbox already shipped via PR18/PR19; D-60 shared gym profiles tables shipped but UI missing; D-61 per-day windows table shipped but resolver + §G UI missing; D-66 race events DB + UI both missing), Andy picked **D-66 DB foundation only** (smallest scope that closes a real gap; profile UI + onboarding §H.2/§H.4 deferred to follow-on PR). Architect-recommended pick — closes a real gap end-to-end (Layer 4 Step 4e race-week-brief already consumes `RaceEventPayload` in-memory but there's no DB layer to persist or edit race events; legacy `athlete_profile.target_event_*` columns are the only path today).

**Round 3 (2026-05-18, 1-question; Trigger #5 fired):** FK shape for `race_events.event_locale_id`. Three options surfaced via `AskUserQuestion`: (a) match storage reality + amend Layer 4 contract; (b) add auto-incrementing SERIAL `id` to `locale_profiles` (keeps Layer 4 contract as-shipped); (c) accept contract drift (BIGINT NULL no-FK). **Andy picked path 2** — add SERIAL `id`. Cleanest schema; Layer 4 contract stays as-shipped (`RaceEventPayload.event_locale_id: int | None` matches the new SERIAL id).

### 2.2 Implementation order

1. **`init_db.py` `_PG_MIGRATIONS` append** — 8 new entries appended after the Step 5 `layer4_cache` block:
   - `ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS id BIGSERIAL` — backfills each existing row with a unique nextval() automatically; composite PK `(user_id, locale)` stays.
   - `CREATE UNIQUE INDEX IF NOT EXISTS locale_profiles_id_uidx ON locale_profiles (id)` — explicit UNIQUE since BIGSERIAL alone doesn't enforce.
   - `CREATE TABLE IF NOT EXISTS race_events (...)` — id BIGSERIAL PK + user_id FK CASCADE + name + event_date DATE + race_format CHECK closed-4-enum + nullable distance/elevation + nullable rules/gear text + event_locale_id BIGINT REFERENCES locale_profiles(id) ON DELETE SET NULL + is_target_event BOOLEAN + notes + etl_version_set JSONB + timestamps.
   - `CREATE UNIQUE INDEX race_events_user_target_uidx ON race_events (user_id) WHERE is_target_event = TRUE` — partial UNIQUE enforces at most one target per athlete per Decision 5.
   - `CREATE INDEX race_events_user_date_idx ON race_events (user_id, event_date)`.
   - `CREATE TABLE IF NOT EXISTS race_route_locales (...)` — id BIGSERIAL PK + race_event_id FK CASCADE + role CHECK closed-7-enum + sequence_idx INTEGER + name + nullable mile_marker/lat/lng/mapbox_id/notes + timestamps + UNIQUE (race_event_id, sequence_idx).
   - `CREATE INDEX race_route_locales_race_seq_idx ON race_route_locales (race_event_id, sequence_idx)`.
   - `CREATE TABLE IF NOT EXISTS race_route_locale_equipment (...)` — id BIGSERIAL PK + race_route_locale_id FK CASCADE + equipment_name + nullable quantity_text/notes + timestamps.
   - `CREATE INDEX race_route_locale_equipment_locale_idx ON race_route_locale_equipment (race_route_locale_id)`.
   - **Legacy migration** — INSERT INTO race_events SELECT FROM athlete_profile per design §10 with `target_event_date::date` cast (legacy column is TEXT) + empty-string + NULL guards + `NOT EXISTS` idempotence guard; defaults race_format='single_day' for Andy to update via profile UI; one-time on first init after this revision lands.
2. **NEW top-level `race_events_repo.py`** (~330 lines, 8 helpers; pure data-access; mirrors `chain_registry.py` + `mapbox_client.py` placement). See §3 for the full API surface.
3. **NEW `tests/test_race_events_repo.py`** (~480 lines, 22 tests using the `_FakeConn`/`_FakeCursor` pattern from `tests/test_layer4_cache.py`).
4. **Bookkeeping:** `Project_Backlog_v52.md` → `_v53.md` + CLAUDE.md update + this handoff.

### 2.3 Architectural choices on the record

- **`id BIGSERIAL` added alongside composite PK (no PK swap)** — composite PK `(user_id, locale)` stays for D-60's `locale_equipment_overrides` + `locale_toggle_overrides` which keep using the composite FK pair. The new `id` column is a surrogate available for non-composite FK consumers (race_events). PostgreSQL's `ALTER TABLE ADD COLUMN BIGSERIAL` on an existing table backfills each row with a unique nextval() automatically — no explicit UPDATE needed.
- **Top-level placement of `race_events_repo.py`** mirrors `chain_registry.py` + `mapbox_client.py` — pure data-access helpers without Flask blueprint coupling. The future profile-tab UI PR (deferred follow-on) registers a Flask blueprint at `routes/race_events.py` that consumes these helpers. Keeps the data-access layer reusable from both the orchestrator (Layer 4 race-week-brief caller) and the eventual route handlers.
- **`load_race_event_payload` issues 3 SELECTs** (race_events + route_locales ORDER BY sequence_idx + equipment IN-clause batched) rather than a single JOIN — keeps assembly logic simple; the equipment SELECT short-circuits to `[]` when route_locales is empty (single-day events with no athlete-saved route). Trade-off: 3 round-trips vs 1; acceptable at v1's N=1-2 athletes; can fold into a single CTE later if measured latency justifies.
- **`set_target_event` does UNSET-old + SET-new in 2 statements** (not a single CASE WHEN UPDATE) — the partial UNIQUE index `race_events_user_target_uidx` would block a transient 2-TRUE state if both rows were flipped in the same statement. Doing UNSET-first guarantees the index never sees two TRUE rows mid-transaction. The `id <> ?` clause in the UNSET ensures idempotence when the caller passes the already-target row.
- **`create_race_event` JSON-serializes `etl_version_set` via `json.dumps`** for the `?::jsonb` cast — psycopg2 doesn't auto-cast Python dicts to jsonb. Defaulting to `{}` empty-jsonb when caller omits.
- **Legacy migration uses `target_event_date::date` cast** — the legacy column is TEXT in `athlete_profile`. Migration also guards `target_event_name <> ''` + `target_event_date <> ''` to skip rows where the legacy values were never set. Idempotent via `NOT EXISTS` guard on `is_target_event=TRUE` — re-running the migration after Andy updates his row to expedition_ar won't insert a duplicate.
- **`load_target_race_event_payload` delegates to `load_race_event_payload`** rather than duplicating the 3-SELECT assembly — keeps a single source of truth for the typed-pydantic construction logic; trade-off: one extra round-trip (lookup-target-id + load) vs a single composite query, but the SELECT-then-load shape is simpler to reason about + test.
- **Validation at module boundary** — `create_race_event` rejects unknown race_format values; `add_route_locale` rejects unknown role values + sequence_idx < 1. CHECK constraints in the DB are the second line of defense; raising Python-side gives clearer error messages + skips the round-trip.

### 2.4 Stop-and-ask triggers — #5 fired × 1; #11 did NOT fire

- **Trigger #5 (schema/inter-layer-contract amendments):** fired and routed via `AskUserQuestion` — Rule #9 surfaced the design-doc-vs-storage FK gap. Andy picked path 2 (add SERIAL id to locale_profiles). This is a schema change to the locale_profiles table that affects future FK consumers but doesn't break any existing FK consumer (composite PK stays). No spec amendment needed because the design doc anticipated path 2 — the gap was "design doc was written before checking on-disk schema" not "design doc was wrong".
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows. D-66 itself was already shipped as a design wave 2026-05-18.

Other triggers — none applicable.

---

## 3. `race_events_repo.py` API surface

Pure data-access helpers; no HTTP / no Flask blueprint. Consumed by:
- **Layer 4 race-week-brief orchestrator** — `load_target_race_event_payload(db, user_id)` returns the typed pydantic `RaceEventPayload` ready to pass into `llm_layer4_race_week_brief(...)` as the new `race_event_payload` positional arg per `Layer4_Spec.md` §3.4 amendment.
- **Profile-tab UI follow-on PR (deferred)** — `list_athlete_race_events(db, user_id)` for the tab listing; `create_race_event` / `delete_race_event` / `set_target_event` / `add_route_locale` / `add_route_locale_equipment` for the CRUD form handlers.

| Function | Purpose | Returns | Side effects |
|---|---|---|---|
| `list_athlete_race_events(db, user_id)` | Profile-tab listing | `list[dict]` ordered by event_date ASC | None (read-only) |
| `load_race_event_payload(db, race_event_id)` | Build typed pydantic from DB rows | `RaceEventPayload \| None` | None (3 SELECTs) |
| `load_target_race_event_payload(db, user_id)` | Convenience for Layer 4 orchestrator | `RaceEventPayload \| None` | None (delegates to load) |
| `create_race_event(db, user_id, name, event_date, race_format, **kw)` | INSERT new row | `int` (new id) | INSERT + commit; raises on invalid race_format |
| `set_target_event(db, user_id, race_event_id)` | Atomic flip target | None | 2 UPDATEs + commit |
| `delete_race_event(db, user_id, race_event_id)` | DELETE row | None | DELETE + commit; CASCADE handles children |
| `add_route_locale(db, race_event_id, role, sequence_idx, name, **kw)` | INSERT route locale | `int` (new id) | INSERT + commit; raises on invalid role / sequence_idx |
| `add_route_locale_equipment(db, race_route_locale_id, equipment_name, **kw)` | INSERT equipment item | `int` (new id) | INSERT + commit |

Constants exported: `VALID_RACE_FORMATS` (4-tuple) + `VALID_ROUTE_LOCALE_ROLES` (7-tuple) — for caller-side validation matching the DB CHECK constraints.

---

## 4. Next session pointers

### 4.1 Architect-recommended next forward moves

D-66 DB foundation COMPLETE. Three follow-on candidates, ordered by visible-to-athlete impact:

1. **D-66 profile-tab UI** (highest visible impact; ~6-8 files projected) — `/profile?tab=race-events` per design §7. Scope: new `routes/race_events.py` Flask blueprint (registered in `app.py`) + new `templates/profile/_race_events_tab.html` partial + extend `templates/profile/edit.html` to include the tab + per-race edit form (race details + route-locale ordered list with drag-reorder + nested equipment-item list per locale) + per-row 'Set as target' affordance with confirm modal + add/edit/delete forms. Consumes `race_events_repo.py` helpers shipped this revision.
2. **D-66 onboarding §H.2/§H.4 extension** (closes the new-athlete path; ~5-7 files projected) — extend `templates/onboarding/target_race.html` with race_format radio + conditional distance/elevation/rules/gear fields per design §6.2; new `templates/onboarding/route_locales.html` for §H.4 multi-day-only step; `routes/onboarding.py` gains `route_locales` view (GET/POST) + the existing `target_race` POST handler writes a `race_events` row (calling `create_race_event`) instead of (or in addition to) the legacy `athlete_profile.target_event_*` columns. Account_nudge fires on skip.
3. **Layer 3B caller-side rewire** (closes the contract drift; ~3-4 files projected) — orchestrator currently reads `athlete_profile.target_event_*` for 3B's event-mode input; once profile UI ships, swap to `load_target_race_event_payload(db, user_id)` so the race-week-brief shares the same source of truth as 3B. Includes resolving the Layer3BPayload.event_locale_id `str` vs RaceEventPayload.event_locale_id `int` mismatch (3B's `str` is the legacy slug; once 3B reads from race_events the type can swap to `int` matching the new SERIAL id).
4. **Layer 4 Step 7 live LLM integration** (orthogonal to D-66; architect-recommended from Step 6 handoff) — first end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call. Cache + telemetry now make this safe to iterate on. Needs `ANTHROPIC_API_KEY`.

### 4.2 Carry-forward — Locale-FK type alignment across typed payloads (D-72)

Tracked as **D-72** in `Project_Backlog_v53.md` (new this session). After D-66 added the surrogate `BIGSERIAL id` to `locale_profiles`, three Layer 4 typed payloads in `layer4/context.py` reference the locale_profiles table with INCONSISTENT key types:

- `Layer2CPayload.locale_id: str` (line 337) — TEXT slug; matches legacy composite PK
- `Layer3BPayload.event_locale_id: str | None` (line 795) — TEXT slug; same
- `RaceEventPayload.event_locale_id: int | None` (line 933) — INT id; matches the new SERIAL surrogate

Same logical entity (FK to locale_profiles row), three payloads, two different key types. `RaceWeekBrief.event_locale: str` (`layer4/payload.py:420`) is correctly `str` because it's the RENDERED text-form name (display, not FK) — but the FK-vs-display split is undocumented.

v1 accepts the mismatch — Layer 2C + Layer 3B were specced before the SERIAL id existed; D-66 added the SERIAL specifically for race_events. **Defer trigger:** lands when Layer 3B's caller-side rewires from `athlete_profile.target_event_*` to `race_events` (will force a type pick) OR D-66 profile-tab UI follow-on lands (will force legacy column retirement) OR any Layer 2C consumer trips over the ambiguity. Whichever triggers first should also close D-72.

See D-72 row in `Project_Backlog_v53.md` for the three-path-scope (int everywhere / slug everywhere / per-payload split) + the full consumer surface (orchestrator pre-2C + pre-3B callers, paired Layer2C_Spec.md + Layer3_3B_Spec.md amendments, `routes/profile.py` + `templates/profile/edit.html` legacy column migration, `init_db.py` future cleanup migration).

### 4.3 Carry-forward — Profile UI for athlete to update Andy's migrated row

Per design §10.1, Andy's Pocket Gopher Extreme 2026 row migrated to race_events on first init defaults to `race_format='single_day'` (the safe default). Andy needs to update via the profile UI (still deferred) to:
- race_format = 'expedition_ar'
- distance_km / total_elevation_gain_m (TBD per race director's published guide)
- race_rules_summary + mandatory_gear_text (paste from race-director-published guide)
- route_locales (start + transition areas + aid stations + drop bags + finish per actual race route)

Documentation-track follow-up post-implementation; not contract-bearing.

### 4.4 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff.
3. **Third re-read**: depends on scope. If profile-tab UI → `Race_Events_D66_Design_v1.md` §7 + `routes/profile.py` existing patterns + `templates/profile/edit.html` tab structure + PR18's `routes/locales.py` form patterns. If onboarding extension → `Race_Events_D66_Design_v1.md` §6 + existing `routes/onboarding.py` + `templates/onboarding/` patterns. If Layer 3B rewire → `Layer3_3B_Spec.md` + the orchestrator pre-3B caller (search for `target_event_name` consumers in `routes/`).
4. **Branch**: cut fresh off post-merge `main` OR stay on the harness pin (precedent).
5. **Profile UI registration**: `routes/race_events.py` blueprint registers in `app.py` alongside the existing blueprints (`bp_locales` etc.). Convention: `bp = Blueprint('race_events', __name__, url_prefix='/profile/race-events')`.

---

## 5. Open items / decisions pinned this session

### 5.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = v5 onboarding implementation PR | Andy 2026-05-18 | Architect-recommended next-move set from Step 6 handoff §4.1 |
| 2 | Sub-scope = D-66 DB foundation only | Andy 2026-05-18 | Smallest scope that closes a real gap; profile UI + onboarding extension deferred to follow-on |
| 3 | FK shape = path 2 (add SERIAL id to locale_profiles) | Andy 2026-05-18 | Layer 4 contract stays as-shipped (`int | None`); cleanest schema; composite PK stays for D-60 tables |
| 4 | `race_events_repo.py` at top level | Architect-pick | Mirrors `chain_registry.py` + `mapbox_client.py`; pure data-access without Flask coupling |
| 5 | 3-SELECT assembly in `load_race_event_payload` | Architect-pick | Simpler than single JOIN; equipment SELECT short-circuits on empty route_locales |
| 6 | `set_target_event` UNSET-then-SET in 2 statements | Architect-pick | Partial UNIQUE index would block single-statement flip; UNSET-first guarantees index never sees 2 TRUE |
| 7 | Legacy migration idempotent via `NOT EXISTS` guard | Architect-pick | Re-running after Andy updates his row won't insert duplicate |
| 8 | Caller-side validation on race_format + role + sequence_idx | Architect-pick | Clearer error messages than CHECK-constraint violation; skips round-trip on invalid input |
| 9 | File ceiling break (6 files) | Architect-pick (implied) | Precedented across every prior Layer 4 implementation session |

### 5.2 Carry-forward — Layer3BPayload.event_locale_id type mismatch

See §4.2 above. v1 accepts the mismatch; v2 reconciliation lands with Layer 3B's race-event read swap.

### 5.3 Carry-forward — Profile UI for Andy's migrated row

See §4.3 above. Andy updates via profile UI when it ships.

### 5.4 Carry-forward — `RaceEventPayload` route-locale invariant softness for unfinished onboarding

`RaceEventPayload._check_route_locales_invariants` enforces: (1) sequence_idx unique; (2) sorted ascending; (3) first role == 'start' AND last role == 'finish' when route_locales non-empty. The DB schema enforces (1) via `UNIQUE (race_event_id, sequence_idx)`; the ORDER BY in `load_race_event_payload` enforces (2). But (3) is purely caller-side — DB allows a route_locales row set with first role != 'start' (e.g., athlete saved aid_station rows before saving the start). If the athlete saves rows out of order, `load_race_event_payload` will raise on the pydantic invariant check. Acceptable for v1 — UI flow saves rows in order. v2 could either relax the invariant (3) or enforce it via DB CHECK constraint.

---

## 6. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `init_db.py` `_PG_MIGRATIONS` gains 8 D-66 entries after layer4_cache block | ✅ inspection |
| `race_events_repo.py` exists at top level (~330 lines, 8 helpers) | ✅ inspection |
| `tests/test_race_events_repo.py` exists with 22 tests | ✅ `pytest tests/test_race_events_repo.py -q` → 22 passed in 0.32s |
| Combined `tests/` 684 green | ✅ `pytest tests/ -q` → 684 passed in 1.04s |
| `Project_Backlog_v53.md` exists; file-revision-header bumped to v53 | ✅ ls + head |
| `Project_Backlog_v53.md` D-66 row status updated 🟢 DB foundation shipped | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v53.md` | ✅ grep |
| `CLAUDE.md` last-shipped-session is D-66 DB foundation; Step 6 demoted to predecessor | ✅ inspection |
| `CLAUDE.md` Next forward move points at D-66 profile-tab UI / onboarding extension / Step 7 | ✅ inspection |
| Branch is `claude/pattern-a-polish-closing-fAOxb` (harness-pinned) | ✅ |

---

## 7. Files shipped this session

One commit (or multiple bundled) on `claude/pattern-a-polish-closing-fAOxb`:

**Substantive code + tests (3 files):**
1. Modified `init_db.py` — 8 new `_PG_MIGRATIONS` entries appended after the Step 5 `layer4_cache` block (D-66 §3 + §10 verbatim DDL + locale_profiles SERIAL id ALTER + UNIQUE index).
2. New `race_events_repo.py` (~330 lines, 8 helpers) — pure data-access at top level.
3. New `tests/test_race_events_repo.py` (~480 lines, 22 tests) — `_FakeConn`/`_FakeCursor` pattern.

**Bookkeeping (3 files):**
4. New `aidstation-sources/Project_Backlog_v53.md` (per Rule #12; v52 retained as predecessor) — D-66 row status flip + new file-revision header.
5. Modified `aidstation-sources/CLAUDE.md` — last-shipped-session bump; Step 6 demoted to predecessor; Backlog ref v52 → v53; Next forward move updated.
6. New `aidstation-sources/handoffs/V5_Implementation_D66_Race_Events_DB_Foundation_Closing_Handoff_v1.md` (this file).

**6 files total. Over the 5-file ceiling intentionally** — precedent across Step 6 11 + Step 5 11 + Step 4f 13 + Step 4d 13 + Step 4b/c 10 + Step 4e 10 + PR-A 8 + Step 4a 8 + PR-C-followon 6 + PR-D 6 + PR-E 6 + D-66 design wave 6.

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- v5 onboarding implementation PR — partially advanced this session via D-66 DB foundation; profile-tab UI + onboarding §H.2/§H.4 extension remain as concrete carry-forwards.
- Migration script per `Race_Events_D66_Design_v1.md` §10 — ✅ shipped this session (legacy `athlete_profile.target_event_*` → race_events with idempotence guard).
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **Step 7 live LLM integration** — architect-recommended orthogonal candidate per §4.1.
- **Seam-driven re-synth cache-key formula per §9.2** — concrete carry-forward from Step 6.
- **Anthropic SDK `seed` parameter per §9.4** — v2 forward-pointer; awaits API support.
- **D-72 Locale-FK type alignment across typed payloads** (`Layer2CPayload.locale_id: str` + `Layer3BPayload.event_locale_id: str` + `RaceEventPayload.event_locale_id: int`) — new D-row + carry-forward from this session per §4.2; defer trigger fires on first of: 3B caller rewire / D-66 profile-tab UI / Layer 2C consumer ambiguity.

---

**End of handoff.**
