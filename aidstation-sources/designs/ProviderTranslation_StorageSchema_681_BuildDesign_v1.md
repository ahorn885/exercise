# Provider Translation Layer — Storage Schema Build (#681 §4 wave) — Design v1

**Date:** 2026-06-18
**Type:** Build design (no code ships from this doc — ratify, then build in sliced PRs).
**Parent spec:** `specs/Provider_Data_Translation_Layer_Spec_v1.md` §4 (storage schema, D-8) + §8 (migration plan).
**Seed authority:** `specs/Provider_Inbound_Matrix_v2.md` (Batches 1–3 = the value-map seed rows; §1 option-C the cardio collapse; §12 the indoor-machine flag).
**Predecessor inbound slice (shipped, live):** #679 Garmin strength resolver — `provider_strength_resolve.py`. This wave generalizes its in-Python dicts into the table.

This is the "§4 build wave" the matrix-v2 closing handoff names as the next high-value move. It is **Trigger #3 (cross-layer schema)**, so it is designed here and ratified before any migration is written.

---

## 1. Problem / scope

The provider→canonical mappings live today as **scattered Python dicts** with no single store, no provenance, no raw-passthrough, and no place for the matrix-v2 seed rows the spec session just authored:

| Map | Location | Shape |
|---|---|---|
| `NAME_TO_EX_ID` | `layer0_progression.py:34` | strength name → EX-id (coarse + manual-log names) |
| `GARMIN_STRENGTH_ALIASES` | `provider_strength_resolve.py:54` | Garmin FIT subtype name → EX-id (#679) |
| `LOGGED_NAME_ALIASES` | `provider_strength_resolve.py:112` | Andy's logged-rx vocabulary → EX-id (#679) |
| `GARMIN_TYPE_TO_PLAN_SPORT` | `garmin_connect.py:49` | Garmin activity `typeKey` → coarse `_plan_sport_type` (15 rows) |
| Polar/COROS field maps | inline in `routes/polar_ingest.py` / `routes/coros_ingest.py` | provider field → core column |

Parent §1.2 ("why a layer, not scattered dicts") + §4 (D-8) call for consolidating these into three generic tables, with raw always retained (record-don't-drop) and a per-(user,metric) precedence rule. The matrix-v2 Batches 1–3 are authored in the exact `provider_value_map` column vocabulary so the build is a **transcription, not a re-derivation**.

**Out of scope (deferred to later slices / waves, see §7):** the irreversible drop of the bespoke Polar/COROS tables; the outbound serializer waves (3a/3b); the security wave (#682 / plaintext-token gap).

---

## 2. Decisions

### 2.1 Ratified by Andy (2026-06-18, this session)

- **D-A — `provider_value_map` is the canonical source of truth, now.** The scattered Python dicts are **retired into the table**; we do not keep them as a parallel authoring home. All four consumers (§5) repoint to read the table. (Andy: "table becomes canonical now.")
- **D-B — Design only this session; nothing ships until ratified.** (Andy: "just design, no build yet.")

### 2.2 Proposed (Andy to ratify before build)

- **D-C — Git authoring surface = one consolidated committed seed**, materialized into the table each deploy via `INSERT … ON CONFLICT DO UPDATE` (the live `EXERCISES`-seed pattern, `init_db.py:2786`). *Rationale:* the container can't reach Neon (CLAUDE.md), so rows can't be hand-edited in prod; a committed seed keeps reviewable git diffs (Rule #11/#12) and idempotent deploy-time sync, while the **table** is the runtime-canonical store every consumer reads. "Delete the scattered dicts" then means **consolidate five dicts into one seed surface + the table**, not "author by raw SQL." *Alternatives:* append-only `_PG_MIGRATIONS` INSERT rows (loses the single readable map; awkward to amend a row); or an admin authoring UI (a later wave; overkill now). **Rec: one consolidated seed module.**
- **D-D — Migration mechanism = public-schema `_PG_MIGRATIONS` + `init_db` CREATE/seed (auto-applies on Vercel deploy), NOT `layer0-apply`.** These are app-ingest infrastructure tables seeded from app-side Python, not layer0 ETL canon; they carry `user_id` runtime data (`provider_raw_record`, `provider_outbound_ref`). No manual gate. **Rec: public schema.**
- **D-E — Slice boundary (see §7).** Slice 1 = schema + value-map seed + consumer repoint (lowest risk, no behavior change, no drops). Cardio-fidelity upgrade and the bespoke-table consolidation are later slices. **Rec: ship Slice 1 first.**

---

## 3. Target schema (concrete DDL — refines parent §4.2–4.4)

All three are public-schema. `CREATE TABLE IF NOT EXISTS` in `init_db.py` alongside the core tables; idempotent so re-deploys are no-ops.

### 3.1 `provider_value_map` (enum/name normalization — §4.2)

```sql
CREATE TABLE IF NOT EXISTS provider_value_map (
    provider           TEXT NOT NULL,   -- 'garmin'|'polar'|'coros'|'strava'|'oura'|'whoop'|'wahoo'|'rwgps'|'trainingpeaks'|...
    data_type          TEXT NOT NULL,   -- 'strength'|'cardio'|'sleep'|'wellness'|'body'|'zone'
    direction          TEXT NOT NULL,   -- 'in'|'out'
    source_value       TEXT NOT NULL,   -- provider token (FIT name, typeKey, metric name, zone label)
    canonical_kind     TEXT NOT NULL,   -- 'ex_id'|'discipline'|'modality'|'metric_key'|'unit'|'zone'
    canonical_value    TEXT,            -- EX001 / 'running' / 'hrv_rmssd_ms' / 'Z3' ... ; NULL when no_canonical_match
    match_kind         TEXT NOT NULL,   -- 'exact'|'fuzzy'|'manual'
    confidence         REAL NOT NULL DEFAULT 1.0,
    no_canonical_match BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE → bucket-2/3, record raw, do not force-map
    notes              TEXT,
    PRIMARY KEY (provider, data_type, direction, source_value)
);
```

- The composite PK gives the upsert key for D-C's `ON CONFLICT DO UPDATE`.
- `canonical_value` is nullable so a bucket-2/3 row (e.g. Strava `suffer_score`, `Rowing`) is recorded as an *explicit* "known, deliberately unmapped" entry rather than absent.

### 3.2 `provider_raw_record` (raw passthrough — §4.3)

```sql
CREATE TABLE IF NOT EXISTS provider_raw_record (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id),
    provider      TEXT NOT NULL,
    data_type     TEXT NOT NULL,
    external_id   TEXT,             -- provider's record id (dedup; generalizes *_exercise_id / *_workout_id / *_trip_id)
    observed_at   TIMESTAMP,
    raw_payload   JSONB,            -- original value(s) verbatim (generalizes the existing raw_payload cols)
    bucket        SMALLINT,         -- 1|2|3
    canonical_ref TEXT,             -- link to the canonical row it normalized into (NULL for bucket-2)
    fetched_at    TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, provider, data_type, external_id)
);
```

This is the home for the **§12 indoor-machine flag** (Strava `VirtualRide`/`StairStepper`, RWGPS `is_stationary`, Wahoo `workout_type_location_id`) — it rides inside `raw_payload`, no registry/vocab change.

### 3.3 `provider_outbound_ref` (idempotent push — §4.4)

```sql
CREATE TABLE IF NOT EXISTS provider_outbound_ref (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER REFERENCES users(id),
    provider            TEXT NOT NULL,  -- 'google_calendar'|'outlook'|'trainingpeaks'|'garmin'|'zwift'|'wahoo'|...
    session_id          TEXT,           -- our plan-session id
    external_id         TEXT,           -- the calendar event / platform workout id we created
    tier                SMALLINT,       -- 1 (calendar) | 2 (workout)
    pushed_payload_hash TEXT,           -- detect change → upsert vs no-op
    status              TEXT,           -- 'pushed'|'updated'|'deleted'|'error'
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, provider, session_id)
);
```

**No inbound consumer exists for this table yet** — it serves the Wave-3 outbound serializers. Creating it now is cheap (empty table) and lets the schema land as one coherent unit, but **if we want strict no-speculative-surface (CLAUDE.md), defer it to the outbound wave.** Flagged as open question Q4.

---

## 4. Seed content (what populates `provider_value_map`)

Two families, both transcribed from existing on-disk authority:

1. **Strength `ex_id` rows** (`provider='garmin', data_type='strength', direction='in', canonical_kind='ex_id'`) — every key of `NAME_TO_EX_ID` ∪ `GARMIN_STRENGTH_ALIASES` ∪ `LOGGED_NAME_ALIASES`. `match_kind='manual'` (these are Andy-ratified), `confidence=1.0`. The three keyspaces are disjoint (`provider_strength_resolve._alias_map` docstring), so no PK collision. `NAME_TO_EX_ID`'s coarse names are the **category-collapse backstop targets** — keep them as ordinary `ex_id` rows; the collapse logic (§6) reads them by name exactly as `resolve_strength_ex_id` does today.
2. **Cardio rows** — Slice 1 transcribes `GARMIN_TYPE_TO_PLAN_SPORT` **as-is** (`canonical_kind='modality'`, coarse `_plan_sport_type` value) so there is **zero behavior change**. The fine-D-id authoring (matrix-v2 option C) is the Slice-2 fidelity upgrade, not Slice 1 (§6).

Polar/COROS metric rows (`canonical_kind='metric_key'`) land in Slice 3 with the ingest consolidation (they have no standalone consumer until then).

---

## 5. Consumer repoint graph (the load-bearing part of "table becomes canonical")

Deleting the dicts means repointing **four** consumers and respecting one **ordering constraint**. All are in Slice 1.

| # | Consumer | Today | After |
|---|---|---|---|
| 1 | `provider_strength_resolve._alias_map()` (`:240`) | merges the three dicts | reads the strength `ex_id` rows from `provider_value_map`, **module-level cached** (load once per process, mirror the existing `_subtype_to_category` lazy-cache at `:217`) so the hot `apply_session_outcome` write path stays off a per-call query |
| 2 | `provider_strength_resolve.resolve_strength_ex_id` category backstop (`:266`) | `NAME_TO_EX_ID.get(cat_name)` | same cached map (the coarse names are rows now) |
| 3 | `init_db.py` `current_rx` backfill (`:2359`) | iterates `{**NAME_TO_EX_ID, **GARMIN_STRENGTH_ALIASES, **LOGGED_NAME_ALIASES}` | iterates the seeded `provider_value_map` strength rows — **must run AFTER the value-map seed in the same `init_db` pass** (ordering constraint C1) |
| 4 | `garmin_connect.py:343` `_plan_sport_type` lookup | `GARMIN_TYPE_TO_PLAN_SPORT.get(garmin_type,'')` | reads the cardio `modality` rows (cached) |

**Ordering constraint C1 (Rule #11, mechanical):** in `init_db`, the `provider_value_map` seed `INSERT`s must execute **before** the `current_rx` backfill loop (consumer 3), because the backfill now sources its name→EX-id pairs from the table. Concretely: place the value-map seed in the seed phase that already precedes `_PG_MIGRATIONS`/backfill, or hoist the backfill to read post-seed. The build session verifies by asserting the seed count > 0 before the backfill query.

**Retirement:** once 1–4 read the table, delete `GARMIN_STRENGTH_ALIASES`, `LOGGED_NAME_ALIASES`, `GARMIN_TYPE_TO_PLAN_SPORT`, and the `NAME_TO_EX_ID` definition — folding all into the one seed module (D-C). *Watch-out:* `NAME_TO_EX_ID` is imported in 3 modules + tests; grep-sweep all importers in the build (`layer0_progression`, `init_db`, `garmin_connect`, `provider_strength_resolve`, test files) and repoint or delete each. This is why it's its own slice.

---

## 6. Cardio fidelity upgrade (Slice 2 — matrix-v2 option C + §12)

Matrix-v2 §1 ratified **option C**: store the fine layer0 D-id where one exists, derive coarse `_plan_sport_type` via a deterministic collapse. The wired Garmin path stores **coarse only** today, so this is a real ingest change, not a swap. Slice 2:

1. **`cardio_log` gains `discipline_id TEXT`** (`ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS discipline_id TEXT` in `_PG_MIGRATIONS`) — the fine D-id of a completed activity. `activity`/raw `typeKey` stays (record-don't-drop).
2. **Author the fine-D-id cardio rows** in `provider_value_map` (`canonical_kind='discipline'`) from the matrix-v2 per-provider cardio tables (§2 Strava, §10 Wahoo/RWGPS, §11 TP — each row already gives the fine D-id).
3. **D-id→coarse collapse table** — a small deterministic map (matrix §1 option C): `D-001/002/024→running`, `D-006/007/008/030/031→cycling`, `D-004→swimming`, `D-003/017→hiking`, etc. **Full transcription is from the matrix cardio rows at build time** (each row carries fine + coarse); not re-derived here to avoid drift. Lives as a `dict` next to the resolver, or as `canonical_kind='modality'` rows keyed by D-id — **Q3**.
4. **Indoor-machine flag (§12.3 gap 1)** — record which machine a completed indoor activity used (Strava `VirtualRide`→`Cycling trainer`, `StairStepper`→`Stair climber`; RWGPS `is_stationary`; Wahoo `workout_type_location_id`) inside `provider_raw_record.raw_payload`. No new vocab. Lets a completed indoor session corroborate the athlete's equipment pool.

Rule #15: log the resolved `(provider, typeKey) → fine D-id → coarse` decision + the indoor flag at the cardio ingest chokepoint.

---

## 7. Slicing (ceiling-respecting; reversibility front-loaded)

| Slice | Scope | Files (substantive) | Risk / gate |
|---|---|---|---|
| **1** | 3 tables (`CREATE`) + value-map **strength + coarse-cardio seed** + repoint the 4 consumers + delete the dicts | `init_db.py`, `provider_strength_resolve.py`, `garmin_connect.py`, `layer0_progression.py`, + the seed module = ~5 | **Additive, no behavior change, no drops.** Deterministic; auto-merge eligible |
| **2** | Cardio fidelity: `cardio_log.discipline_id` + fine-D-id cardio rows + collapse table + indoor flag + cardio-ingest repoint | `init_db.py`, the cardio ingest path, the collapse map, tests | New column + ingest write; reversible; deterministic |
| **3** | Polar/COROS ingest → canonical core + `provider_raw_record`; **zero-row guard** then drop bespoke tables | `routes/polar_ingest.py`, `routes/coros_ingest.py`, migration | **Irreversible drop — gated on a `neon-query` zero-row check first.** Needs explicit go-ahead |
| **4** (later) | `provider_outbound_ref` consumers — the Wave-3 outbound serializers | — | Deferred to the outbound wave |

Slice 1 alone is the ratify-and-ship target. Slices 2–3 are separate PRs/sessions.

---

## 8. Tests

- **Slice 1:** seed parity — assert every `{**NAME_TO_EX_ID, **GARMIN_STRENGTH_ALIASES, **LOGGED_NAME_ALIASES}` pair has a matching `provider_value_map` strength row (no silent loss in the dict→table move); `resolve_strength_ex_id` returns identical `(ex_id, match_kind)` for a sampled set before/after the repoint (golden test); `current_rx` backfill still heals the same rows; `_plan_sport_type` lookup unchanged for the 15 Garmin types. Cache-load is exercised (resolve twice, assert one load).
- **Slice 2:** a Garmin/Strava cardio type resolves to the expected fine D-id and collapses to the expected coarse value; an unmapped type → bucket-3 with raw kept; indoor type writes the machine flag into `raw_payload`.
- Full suite green (currently 2647 / 30 skipped).

---

## 9. Open questions for Andy (ratify before build)

- **Q1 (D-C):** consolidated seed module as the git authoring surface? (Rec: yes — mirrors `EXERCISES`.)
- **Q2 (D-D):** public-schema `_PG_MIGRATIONS` (auto-deploy), not `layer0-apply`? (Rec: yes — app infra, not layer0 canon.)
- **Q3:** the D-id→coarse collapse — a Python `dict` next to the resolver, or `provider_value_map` rows? (Rec: a `dict` — it's a fixed canon-internal mapping, not provider-authored, so a value-map row overloads the table's meaning.)
- **Q4:** create `provider_outbound_ref` now (one coherent schema landing) or defer to the outbound wave (strict no-speculative-surface)? (Rec: **defer** — no inbound consumer; Slice 1 ships the two inbound tables only.)
- **Q5:** Slice-1 PR auto-merge? It's deterministic + additive (no trigger fires once *this* design is ratified). (Rec: yes.)

---

## 10. Gut check (risks / what might be missing / best argument against)

- **Best argument against the whole wave:** the dicts work and are live (#679 dogfolds Andy's Garmin lifts today). Moving them into a table is infrastructure, not athlete-visible value, and it adds a DB read + cache to a hot write path. *Counter:* the matrix-v2 seed rows (Strava/Oura/WHOOP/Wahoo/RWGPS/TP) have **nowhere to live** without this table — the spec work is stranded until the store exists; and the dual-source risk only grows as more providers land. The table is the unlock for every subsequent inbound provider.
- **Biggest risk:** the consumer repoint (§5) is the sharp edge — `NAME_TO_EX_ID` has 4 consumers + the seed-ordering constraint C1, and a miss silently degrades resolution to bucket-3 (no crash, just lost EX-ids). Mitigation: the Slice-1 golden parity test + the seed-count-before-backfill assertion make a miss loud.
- **What might be missing:** I have not re-read `routes/polar_ingest.py` / `routes/coros_ingest.py` in detail (Slice 3 scope) — the zero-row guard assumes their bespoke tables are empty of athlete rows; that's a live `neon-query` check the build session runs, not an assumption to bank now.
- **Determinism limit (carried from matrix §1 gut check):** option C's fine-D-id authoring for cardio is the one place real judgment enters (which D-id for `BackcountrySki` vs `Kayaking`); it's transcribed from the matrix, which Andy ratified, so the judgment is already made — Slice 2 is transcription.
