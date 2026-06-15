# V5 Implementation — Layer 0 `primary_movement` backfill (migration `0006`) + standing guard — Closing Handoff

**Date:** 2026-06-15
**Branch:** `claude/intelligent-euler-hjggno` (PR OPEN — CI pending).
**Predecessor handoffs (Andy linked both, "lets keep working"):** `V5_Implementation_WSH_EventWindows_Slice5b_OnboardingPanelF5_2026_06_14_Closing_Handoff_v1.md` (#608 done/closed) + `V5_Implementation_Layer0_GenesisCollapse_v1_7_0_2026_06_15_Closing_Handoff_v1.md` (#604 done/closed). Both arcs are merged + closed; this picks up the genesis collapse's freshest owed item.
**Arc:** the `primary_movement` line of the #604 genesis-collapse follow-up.

---

## 1. Session-start verification (Rule #9)

Clean. `./scripts/verify-handoff.sh` flagged 3 "missing" paths — all **expected absences** per the genesis handoff (`etl/layer0/schema.sql` archived; `…v1.8.0.sql` is a future-refresh example, not a file; the K3 additions archived #613). No real drift. Both linked arcs verified merged (`main` at `2c83a5e` #614; #608 + #604 closed; no open PRs).

## 2. What I found (the drift the handoff didn't catch)

The genesis handoff's §7 #1 owed action was: confirm the `primary_movement` gap, then `psql … -f etl/sources/run_owed_layer0_migrations.sql`. Verified against the committed v1.7.0 baseline (a full live `pg_dump`):

- **Real prod gap, confirmed.** All **24 active** `layer0.disciplines` rows have `primary_movement` NULL (`endurance_profile` populated on all 24, `primary_movement` NULL on all 24 — the tell-tale asymmetry). **Live effect:** Layer 2E `_movement_sport_profile` (layer2e/builder.py) returns the generic `multi_sport` for *every* discipline and the `climbing`→protein bump (`_STRENGTH_MOVEMENTS`) never fires — already-shipped plans get movement-blind fuelling, including Andy's PGE plan. Tier-2 live-functionality degradation.
- **The owed migration was STALE and would have FAILED.** `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` hardcoded UPDATEs for a `D-001..D-029` keyspace that has since drifted: the active canon now includes **D-030/D-031/D-032** (added 2026-06-08, uncovered) and renamed/removed ids. Its own `every active row populated` verify block would RAISE on the three uncovered new disciplines → rollback. So "just run the runner" would not have worked.
- **Root cause:** `primary_movement` is set only by a post-hoc migration, but a full ETL re-extraction of the disciplines dimension (`0A-v1.6.0`→`0A-v1.6.7`, 2026-06) replaced the active rows without it. `endurance_profile` survives because the canon normalizer (`discipline_canon.normalize_dimension_rows`) stamps it on every extracted row; `primary_movement` is not stamped, so it clobbers to NULL on every re-extraction.

## 3. Decision (Andy-ratified via `AskUserQuestion`)

- **Focus:** fix the `primary_movement` gap (over new functionality #592/#593 or the T3-refresh re-verify).
- **Delivery:** a **`0006` migration + a `validate_layer0` guard** (over patching the etl/sources migration, or also curating a map into `discipline_canon.py`).

## 4. What shipped

- **`etl/migrations/layer0/0006_populate_disciplines_primary_movement.sql`** (new) — backfills the 24-discipline canon (`discipline_canon.CANONICAL_NAMES`) with `ENUM_MOVEMENTS` values via a temp `_pm_map` (single source of the id→movement map). **Serving-relevant Shape-2 edit** (README §"Two edit shapes" #2): `primary_movement` is read by Layer 2E, so it supersedes the movement-less active rows and **re-inserts at a bumped `disciplines` version `0A-v1.6.7`→`0A-v1.6.8`** so the per-table `etl_version` digest advances and the movement-blind plan-gen caches invalidate. `disciplines` is already in `_LAYER0_TABLE_FAMILY` (0A) → no family-map change. **Idempotent:** only backfills active rows that still lack a movement (so a re-run after the baseline is next re-dumped is a clean no-op; no `(discipline_id, etl_version)` UNIQUE collision because nothing re-inserts). Atomic verify DO block RAISEs on any leftover NULL / non-enum.
- **`etl/layer0/validation/primary_movement_check.py`** (new) + wired into **`etl/layer0/validate_layer0.py`** (import + `_v_primary_movement` extractor + `Check("primary_movement", …)` in the registry, placed after `discipline_canon`). Every active discipline must carry an `ENUM_MOVEMENTS` value; fix-not-waive (no waiver). This is the standing guard so the clobber can't silently recur.
- **Retired the stale migration:** deleted `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` and dropped its `\ir` from `etl/sources/run_owed_layer0_migrations.sql` (now 3 includes `[1/3]..[3/3]`, header updated to point at 0006).
- **Tests** (`etl/tests/test_validate_layer0.py`): `primary_movement` added to `_clean_results`; registry count 9→**10**; new `test_missing_primary_movement_fails_the_gate`; extractor assertion added to `test_extractors_produce_expected_ids`.

**The id→movement map (24 canon):** running = D-001/002/024/027; hiking = D-003/017; cycling = D-006/007/008/030/031; swimming = D-004; paddling = D-009/010/011/019/032; climbing = D-012/013/014/018; skiing = D-021/022/028. (No surviving discipline maps to `navigation`/`other_skill` — Orienteering merged into Trekking; Fencing/Rifle removed.)

## 5. Verification

- **Real-Postgres gate (mirrors CI exactly), via `pg_virtualenv` + PG16:** load v1.7.0 baseline (artifacts stripped) → apply `0006` → `validate_layer0` → **PASS** (all 10 checks clean; the 5 `sum_to_100` pre-existing waived). Post-0006: **24 active, 0 NULL, single version `0A-v1.6.8`**; the 24 old movement-less rows correctly kept as superseded history at `0A-v1.6.7`.
- **Idempotency:** applied `0006` 3× on the loaded baseline → still 24 active / 0 NULL / single version; total disciplines rows 401 (377 baseline + 24 from apply #1; applies #2/#3 inserted nothing) — no UNIQUE collision, no error.
- **Map vs canon:** programmatically confirmed the 0006 map == `discipline_canon.CANONICAL_NAMES` (24/24, no extras/missing), all values ∈ `ENUM_MOVEMENTS`, all 24 active ids covered.
- **Full Python suite: 2565 passed / 30 skipped** (the 2 `Layer3BEvidenceBasisWarning`s are pre-existing/unrelated). validate_layer0 unit tests: 13 (was 11).
- Note: my first local gate run hit a `UnicodeDecodeError` in `sum_to_100.py` — a `pg_virtualenv` ASCII-locale artifact (the dump has en-dashes), not a code issue; cleared by `PGCLIENTENCODING=UTF8`. CI's `postgres:17`/UTF8 doesn't hit it.

## 6. Owed Andy's hands

- ⬜ **On merge (Neon egress blocked from the container):** `psql "$DATABASE_URL" -f etl/migrations/layer0/0006_populate_disciplines_primary_movement.sql` — the standard post-merge migration apply (README §"Edit flow" step 4). The app picks it up immediately (serving reads `WHERE superseded_at IS NULL`). Then **ideally re-dump** → `etl/output/layer0_etl_v1.8.0.sql` so the baseline absorbs it (the gate auto-picks the newest; 0006 then becomes a historical no-op).
- ⬜ (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

## 7. Next session

- New functionality (off-plan): **#592** race-location terrain/weather inference; **#593** reduced-volume / in-transit travel days. (The WS-H Event-Windows arc and #604 are both fully closed.)
- The high-priority **determinism-first plan-gen redesign epic (#427/#428/#429)** and **#316** plan-gen latency remain the larger open v2 tracks (see CURRENT_STATE "Next moves").

### 7.1 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — the `primary_movement` bullet under the #604 genesis entry (now FIXED-in-code / owed-apply). 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Migration | `etl/migrations/layer0/0006_populate_disciplines_primary_movement.sql` | present; `CREATE TEMP TABLE _pm_map`; `'0A-v1.6.8'`; verify DO block RAISEs on NULL/non-enum |
| Validator | `etl/layer0/validation/primary_movement_check.py` | `def run_primary_movement(conn)`; `ENUM_MOVEMENTS` frozenset (9 tokens) |
| Gate wiring | `etl/layer0/validate_layer0.py` | `from …primary_movement_check import run_primary_movement`; `def _v_primary_movement`; `Check("primary_movement", …)` in `CHECKS` |
| Tests | `etl/tests/test_validate_layer0.py` | `len(v.CHECKS) == 10`; `test_missing_primary_movement_fails_the_gate`; `"primary_movement"` in `_clean_results` |
| Stale migration retired | `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` | **absent** (deleted) |
| Runner de-referenced | `etl/sources/run_owed_layer0_migrations.sql` | no `migrate_disciplines_add_primary_movement`; `[1/3]..[3/3]` |
| Suite | — | 2565 passed / 30 skipped; validate_layer0 unit = 13 |
| Gate | — | local PG gate PASS (10 checks); 24 active / 0 NULL / `0A-v1.6.8`; idempotent 3× |
| Owed | — | Andy applies `0006` to Neon on merge, then re-dump to v1.8.0; T3-refresh re-verify carried |
