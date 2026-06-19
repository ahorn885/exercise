# V5 Implementation — Provider Translation: Indoor-Machine Flag (Slice 2c, #681 §4) — Closing Handoff v1

**Date:** 2026-06-19
**Type:** Build (v1 app, provider FIT/Connect cardio ingest). PRs: **#751** (slice) + **#752** (same-day hotfix) — both MERGED (squash). Branch `claude/kind-fermi-ygkavu` (slice) + `claude/slice2c-rawrecord-import-hotfix` (hotfix). **Shipped + LIVE-VERIFIED ✅.**
**Predecessor handoff:** `handoffs/V5_Implementation_FITImport_ProdIncident_HubUploaderUnify_2026_06_19_Closing_Handoff_v1.md` (its §6 next-move #1 = this slice).

---

## §1 — Session-start verification (Rule #9)

Continued the #681 §4 provider-translation thread ("i think we're up for slice 2c"). Ran the read order (CLAUDE.md → CURRENT_STATE → CARRY_FORWARD → the FIT-import predecessor handoff) + `verify-handoff.sh` — **all ✅, tree clean, branch `claude/kind-fermi-ygkavu`.** Predecessor anchors spot-checked on-disk: `provider_raw_record` DDL present in `init_db.py` (table exists, **empty — no writer yet**), the cardio resolver (`resolve_cardio_discipline`) + `_garmin_disc_token` in place, the 3 `routes/garmin.py` cardio_log INSERT sites balanced. **No drift.**

## §2 — What shipped

Slice 2c = design `ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` §6 **step 4** + matrix-v2 §12.3 **gap 1**: the **inbound indoor-machine flag** into `provider_raw_record.raw_payload`. This is the **first writer** to `provider_raw_record` (created empty in Slice 1; live in prod since #742). It records *which* machine a completed activity used, so an indoor session can corroborate the athlete's equipment pool — the inbound symmetric of the Layer-4 cascade's outbound `_DISCIPLINE_INDOOR_MACHINES`.

**Andy scope call (AskUserQuestion, U-1):** write a `provider_raw_record` row for **EVERY** Garmin cardio ingest (record-don't-drop), with the indoor-machine flag set only when applicable — i.e. `provider_raw_record` becomes a **general raw passthrough now**, over the narrower indoor-only write.

## §3 — Files (substantive)

- **`provider_cardio_resolve.py`** — `INDOOR_MACHINE_MAP` + pure `resolve_indoor_machine(provider, token)`. The inbound analog of `_DISCIPLINE_INDOOR_MACHINES`. Garmin FIT sub_sports (`indoor_cycling`/`spin`/`treadmill`/`indoor_rowing`) **and** Connect typeKeys (`virtual_ride`/`treadmill_running`/`indoor_running`/`stair_climbing`) → `Cycling trainer` / `Treadmill` / `Stair climber` / `Rowing ergometer`. **No new vocab** — every value is an existing canonical `equipment_items` machine.
- **`garmin_fit_parser.py`** (`parse_fit`) + **`garmin_connect.py`** (`normalize_activity`) — attach a `_provider_raw` passthrough dict (raw token + discipline + indoor flag + bucket + observed_at) and a Rule #15 `machine=…` log line.
- **`routes/garmin.py`** — `_record_provider_raw_cardio` helper: idempotent `INSERT … ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE`, wired at all **3** live cardio ingest sites (`import_confirm` single-file, `_bulk_insert_cardio` bulk, `_import_activity` Connect sync). `external_id` dedups on the FIT content hash / `activityId`; `import_fit` now stashes `result['fit_dedup_id']` so the single-file confirm path shares the **same** dedup key the bulk path uses.
- **`tests/test_provider_raw_record_cardio.py`** (NEW) — the resolver map, the **no-new-vocab guard** (every machine ∈ `_DISCIPLINE_INDOOR_MACHINES` values), `normalize_activity` attach (indoor + outdoor), and the writer (idempotent INSERT params, broad-scope outdoor row, falsy-payload no-op).

**Bookkeeping (ceiling-exempt):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, #681 comment.

## §3a — Hotfix (#752, same day — the slice broke FIT uploads)

Andy bulk-uploaded right after #751 deployed and **every file errored**. Root-caused by reproducing the exact write path against a **local Postgres** (the slice's tests used a *fake* DB connection, so the real SQL never ran in CI — that's the coverage gap).

- **Root cause:** `_record_provider_raw_cardio` reads `observed_at` from the parsed activity date; a FIT whose session timestamp doesn't parse yields `date=''`, and `''` is not a valid `TIMESTAMP` → `psycopg2.errors.InvalidDatetimeFormat`. Because the raw write **shares the import's transaction**, the error aborted the whole `cardio_log` import → the per-file handler reported every file as `error`.
- **Fix (`routes/garmin.py` only):** (1) coerce an empty `observed_at` to `NULL`; (2) wrap the write in a `SAVEPOINT` so the corroboration write is **best-effort** — a failure logs `[provider-raw] … SKIPPED (…)` and rolls back to the savepoint, never aborting the athlete's import.
- **Verified against real Postgres:** empty date stores `NULL` + commits; a forced raw-write error is swallowed while the preceding `cardio_log` insert in the same transaction survives + commits. Test file extended (empty-date→NULL, savepoint wrap, error-swallowed-and-rolled-back).

## §4 — Code / tests / verification

- Full Python suite **2683 passed / 30 skipped** (2671 baseline + 10 slice + 2 hotfix). Imports clean (`routes.garmin`, `garmin_connect`, `garmin_fit_parser`, `provider_cardio_resolve`).
- **No migration** — the table already exists in prod (Slice 1, applied via #742); `init_db.py` untouched.
- **Additive** — no change to `cardio_log` writes or discipline resolution; the discipline path (Slice 2a/2b) is unchanged.

## §5 — Live verification — DONE ✅ (read-only `neon-query`, 2026-06-19)

Andy bulk-uploaded (post-#752); `provider_raw_record` holds **6 rows**, all `provider='garmin'`/`data_type='cardio'`, dedup keys = FIT content hashes:

| id | date | bucket | canonical_ref | machine |
|---|---|---|---|---|
| 5 | 2026-06-03 | 1 | D-006 | **Cycling trainer** |
| 4 | 2026-06-02 | 1 | D-002 | **Treadmill** |
| 3 | 2026-06-01 | 1 | D-006 | **Cycling trainer** |
| 2 | 2026-05-31 | 1 | D-006 | **Cycling trainer** |
| 1, 6 | — | 3 | — | — (non-indoor: bucket-3, NULL machine) |

The 4 indoor activities carry the correct machine + fine D-id; the 2 non-indoor rows confirm the **broad scope** (a row for every cardio ingest, machine NULL when not indoor). The hotfix held (no failures, dates populated). **Both prior §5 items closed.**

- Carried, unchanged: post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **Slice 3** — Polar/COROS ingest consolidation into core + `provider_raw_record`; then the **zero-row-guarded** bespoke-table drops (irreversible; live `neon-query`-gated). `provider_outbound_ref` waits for the outbound wave. This closes the #681 §4 storage build wave.
2. **`cardio_log.discipline_id` AND `provider_raw_record` both still have no downstream consumer** — populated by the Garmin paths; consumers (Layer-1 fidelity, completed-history, multi-source precedence, equipment-pool corroboration) land in later waves.
3. **#747 residual hardening** (low-priority): brittle `PG_SCHEMA.split(';')` + unguarded post-migration seeds.
4. **Deferred (matrix §7):** Batch 4 MyFitnessPal (Layer-2E-blocked); Batch 5 Apple/Samsung/Google Health (native-client-gated).

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| U-1 | `provider_raw_record` write-trigger scope (Slice 2c) | **Every cardio ingest** — a raw record for all Garmin cardio, indoor flag set when applicable (general raw passthrough now) over indoor-only |

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Indoor-machine resolver | `provider_cardio_resolve.py` | `INDOOR_MACHINE_MAP['garmin']` + `resolve_indoor_machine`; `treadmill`→`Treadmill`, `indoor_cycling`/`spin`/`virtual_ride`→`Cycling trainer`, `indoor_rowing`→`Rowing ergometer`, `stair_climbing`→`Stair climber` |
| FIT attach | `garmin_fit_parser.py` | `parse_fit` sets `result['data']['_provider_raw']` with `payload.indoor_machine`; Rule #15 log carries `machine=` |
| Connect attach | `garmin_connect.py` | `normalize_activity` returns a `_provider_raw` key; Rule #15 log carries `machine=` |
| Writer | `routes/garmin.py` | `_record_provider_raw_cardio`: `INSERT INTO provider_raw_record … ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE`; called at `import_confirm` + `_bulk_insert_cardio` + `_import_activity` |
| Dedup key | `routes/garmin.py` | `import_fit` sets `result['fit_dedup_id'] = _fit_dedup_id(raw)` |
| No new vocab | `tests/test_provider_raw_record_cardio.py` | `test_no_new_vocab_every_machine_is_canonical` (machine ∈ `_DISCIPLINE_INDOOR_MACHINES` values) |
| Hotfix (#752) | `routes/garmin.py` | `_record_provider_raw_cardio`: `observed_at = raw.get('observed_at') or None`; body wrapped in `SAVEPOINT provider_raw_cardio` / `ROLLBACK TO SAVEPOINT` on failure (best-effort) |
| Hotfix tests | `tests/test_provider_raw_record_cardio.py` | `test_empty_observed_at_coerced_to_null` + `test_db_error_is_swallowed_and_rolled_back` |
| Live state | prod `neon-query` | `provider_raw_record` 6 rows; indoor rows carry `Cycling trainer`(D-006)/`Treadmill`(D-002); non-indoor bucket-3/NULL machine |
| Tests | full suite | 2683 passed / 30 skipped |
| PRs / issues | #751 + #752 (MERGED); #681 (open, commented) | — |

## §9 — Carry-forward

- **`provider_raw_record` now has its first writer** — Garmin cardio, every ingest, indoor-machine flag when applicable; **live-verified** (§5). **No downstream consumer yet** — consumers (Layer-1 fidelity, completed-history, multi-source precedence, equipment-pool corroboration) land in later waves.
- **No new vocab; no migration** (the table pre-existed in prod since #742). `init_db.py` untouched.
- **Coverage gap (follow-up, low-pri):** the route-level cardio write paths (`_record_provider_raw_cardio`, `_bulk_insert_cardio`, `_import_activity`, `import_confirm`) have **no real-Postgres integration test** — which is why the `''`-timestamp SQL error (#752) wasn't caught pre-merge. A fake-DB unit test cannot catch a live SQL fault. Consider a small Postgres-backed ingest test (the `layer0-gate` already runs Postgres in CI).
- **Lesson re-applied (twice this arc):** a green local/CI run does not prove the prod DB behaves — the prod write was confirmed only via read-only `neon-query` (container can't reach Neon), and the `''`-timestamp bug was found only by running the real SQL against a local Postgres.
