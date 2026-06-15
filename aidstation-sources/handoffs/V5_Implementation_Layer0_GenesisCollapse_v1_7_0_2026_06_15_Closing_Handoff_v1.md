# V5 Implementation — Layer 0 Genesis Collapse to the v1.7.0 live baseline (closing handoff)

**Date:** 2026-06-15
**Branch:** `claude/genesis-refresh-v1.7.0` (PR [#612](https://github.com/ahorn885/exercise/pull/612) — CI green, squash-merged to `main`). Closes [#604](https://github.com/ahorn885/exercise/issues/604).
**Arc:** the #604 "vocab single-source-of-truth" follow-up to the Slice-3 (#603) token mix-up.

---

## 1. What shipped

Collapsed the Layer 0 gate from a layered model (`schema.sql` + a frozen base snapshot + migrations `0001–0005`) to a **single self-contained baseline**: `etl/output/layer0_etl_v1.7.0.sql`, a full `pg_dump` of live `layer0` (schema + data; 28 tables / 34,456 rows). Andy produced the dump (Neon egress is blocked from the web container, so the `pg_dump` is owed-his-hands).

The gate (`.github/workflows/ci.yml` `layer0-gate`) now:
- loads **only** the latest baseline (`ls etl/output/layer0_etl_v*.sql | sort -V | tail -1`), **stripping the PG18 `\restrict` / `\unrestrict` psql meta-commands and the `transaction_timeout` GUC at load** so a raw `pg_dump` loads with no hand-editing of the committed file;
- runs on **`postgres:17`** (was 16) to match prod Neon;
- applies migrations `0006+` (the loop is empty until the next migration lands), then `validate_layer0`.

## 2. Decisions (Andy-ratified via `AskUserQuestion`)

- **Option A — collapse** (over B keep-layered / C consolidate-without-redump). `schema.sql` + migrations `0001–0005` (their effects are already in live) + the `batch_a`/`K`/`K2` equipment scaffolding + the old `v1.4.0–v1.6.7` snapshots → archived under `etl/_archive/pre_v1.7.0_baseline/`. **New DDL starts at migration `0006`.**
- **Family-map exceptions (Trigger #3) — keep both OUT.** Repointing the `TestLayer0TableFamilyMap` drift guard at the baseline surfaced two versioned tables absent from `_LAYER0_TABLE_FAMILY`. Andy chose to honor the existing design and keep both out (no `_LAYER0_TABLE_FAMILY` change), now locked by `_FAMILY_MAP_EXCEPTIONS` + `test_intentional_exceptions_stay_unmapped`:
  - `supplement_vocabulary` — own `supp_vocab.*` version line (never in `etl_version_set`); 2E reads the active set live, no cache-key dependency (per the existing note in `orchestrator.py`).
  - `discipline_technique_foci` — `0B`-versioned but **no reader anywhere** in app code (dead serving data).
  - *(I initially mis-framed `supplement_vocabulary` as a latent cache-staleness bug; corrected after reading the design note — surfaced to Andy before acting.)*

## 3. Drift this surfaced (what #604 was for)

- The **genesis lag** is closed: live had `Glute ham developer (GHD)` that the frozen `v1.6.7` snapshot lacked.
- `discipline_technique_foci` — a live table whose DDL lived **only** in retired `etl/sources` scaffolding, never folded into `schema.sql` or a migration — is now captured by the baseline (the gate had never validated it).

## 4. Bugs found / corrections

- **`nullglob` + `ls $glob` gate bug (CI-found, fixed).** The first CI run failed: with the migrations dir now empty, `shopt -s nullglob; ls etl/migrations/layer0/*.sql` expanded the glob to nothing and ran `ls` argument-less → it listed the repo root → the loop tried to `psql DATABASE.md` (`syntax error at or near "#"`). Latent in the original workflow; the collapse exposed it. Fixed by iterating the glob directly (`for m in etl/migrations/layer0/*.sql`).
- **K3 — resolved (Andy 2026-06-15, [#613](https://github.com/ahorn885/exercise/issues/613) closed not-planned).** Briefly over-archived mid-session then restored once I re-read the Slice-5a `CARRY_FORWARD` note — but Andy then confirmed the K3 items are **unwanted**: climbing gear was long ago consolidated into `sport_specific_gear_toggles` (`Climbing — roped` = the roped kit; `Bouldering` / `Rappelling / abseiling` / `Via ferrata` / `Mountaineering` the rest). The non-climbing K3 items (`Treadmill` / `Road bike` / `Hangboard` / `Kayak` / `Canoe`) are already in live; only the unwanted climbing ones (`Rope` / `Quickdraws` / `Harness` / `Climbing gym membership` / `Crash pad`) weren't. So K3 has nothing wanted-and-missing → in the follow-up cleanup it was **archived** and its `\ir` **dropped** from `run_owed_layer0_migrations.sql` (now a 4-include runner).

## 5. Verification

- Local gate (mirrors CI exactly): fresh `postgres:16`, load the baseline (artifacts stripped), empty migration loop (0 iterations), `validate_layer0` → **PASS** (all checks clean; the 5 `sum_to_100` pre-existing waived). PG16 is the *stricter* check for this dump (it rejects the stripped PG17 `transaction_timeout` GUC); the dump is PG17-native, so a PG16 pass implies a PG17 pass. (Couldn't install PG17 locally — the container blocks `apt.postgresql.org`.)
- Full Python suite **2476 passed / 30 skipped**.
- CI on `ef8321b` (pre-follow-ups): Layer-0 gate / Python / JS / Vercel all green.

## 6. Operating notes for next session

### 6.3 Read order
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — "Last shipped" is now this genesis collapse
3. `CARRY_FORWARD.md` — the #604 entry is ✅ DONE; K3 is ✅ resolved (#613 not-planned); the live **owed** item is `primary_movement` (see §7)
4. This handoff
5. `./scripts/verify-handoff.sh`

### Model notes (important for any future Layer 0 work)
- There is **one** genesis file now: `etl/output/layer0_etl_v1.7.0.sql` (schema + data). Don't reintroduce `schema.sql` — it's archived; the baseline embeds the DDL.
- A **future refresh** = Andy re-runs `pg_dump --schema=layer0 --column-inserts --no-owner --no-privileges "<neon_url>" > etl/output/layer0_etl_v1.8.0.sql`; the gate auto-picks the newest. No sanitization needed (the gate strips the dump artifacts at load).
- When a `0006+` migration adds a **new versioned table**, also add it to `_LAYER0_TABLE_FAMILY` (or to `_FAMILY_MAP_EXCEPTIONS` with a note) — the drift guard enforces this against the baseline.

## 7. Owed / next

- ✅ **K3 — done, do not re-pursue ([#613](https://github.com/ahorn885/exercise/issues/613) not-planned).** Items unwanted (covered by `sport_specific_gear_toggles`); K3 archived, runner de-K3'd.
- ⬜ **OWED (surfaced this cleanup, Andy's hands): `migrate_disciplines_add_primary_movement_v1.sql`.** Live `layer0.disciplines.primary_movement` is **empty (0 active rows)** — `run_owed_layer0_migrations.sql` step [1/4] is genuinely unapplied, and the header flags it a **HARD Layer-2A prereq** (2A SELECTs `primary_movement`). Confirm whether that's a real prod gap or expected, then `psql "$DATABASE_URL" -f etl/sources/run_owed_layer0_migrations.sql` (the other 3 includes are applied — idempotent).
- Resume the WS-H Slice-5b remainder (#608) / new functionality (off-plan #592 race terrain/weather, #593 reduced-volume travel days).
- **STILL OWED (carried, unrelated):** the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

## 8. Rule #9 anchor table (next-session sweep input)

| File | Anchor (grep) | Expect |
| --- | --- | --- |
| `etl/output/layer0_etl_v1.7.0.sql` | `CREATE SCHEMA layer0` | present (self-contained baseline; 28 `CREATE TABLE`) |
| `etl/layer0/schema.sql` | (path) | **absent** — moved to `etl/_archive/pre_v1.7.0_baseline/schema.sql` |
| `etl/migrations/layer0/` | `ls *.sql` | **empty** (only `README.md`) until `0006` |
| `.github/workflows/ci.yml` | `image: postgres:17` | present |
| `.github/workflows/ci.yml` | `for m in etl/migrations/layer0/*.sql` | present (no `ls $glob`) |
| `tests/test_layer4_orchestrator.py` | `_FAMILY_MAP_EXCEPTIONS` | present; `_baseline_versioned_tables` reads `etl/output/layer0_etl_v*.sql` |
| `layer4/orchestrator.py` | `supplement_vocabulary` … `intentionally\nabsent` | the note is intact; map unchanged |
| `etl/sources/populate_equipment_items_K3_additions.sql` | (path) | **absent** — archived (#613 not-planned); runner de-K3'd (4 includes, no `K3`) |
| `etl/_archive/pre_v1.7.0_baseline/` | `ls` | `schema.sql`, `0001`–`0005`, `batch_a`/`K`/`K2`, `old_snapshots/`, addendum, `README.md` |
