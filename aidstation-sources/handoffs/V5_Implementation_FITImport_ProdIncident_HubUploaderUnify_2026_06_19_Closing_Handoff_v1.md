# V5 Implementation — FIT-Import Prod Incident Fix + Hub Uploader Unify — Closing Handoff v1

**Date:** 2026-06-19
**Type:** Build / prod-incident fix (v1 app, provider FIT ingest). Three PRs, all **MERGED** (squash):
- **#742** — fix `init_postgres` aborting on a `;` inside a `PG_SCHEMA` comment (the prod incident).
- **#744** — Connections-hub `.FIT` drop zone → real multi-file uploader + window-level drag guard.
- **#746** — unify the hub uploader to route **both** workout and wellness FITs in one drop zone.

**Branch:** `claude/sharp-davinci-8vg872` (one branch, all three PRs).
**Predecessor handoff:** `handoffs/V5_Implementation_ProviderTranslation_CardioFidelity_Slice2_681_2026_06_19_Closing_Handoff_v1.md` (its §5 = the live-verify that triggered this session).

---

## §1 — Session-start verification (Rule #9)

Continued the #681 provider-translation thread ("get up to speed … I will upload a fit file to test as requested"). Ran the read order (CLAUDE.md → CURRENT_STATE → CARRY_FORWARD → the Slice-2 handoff) + `verify-handoff.sh` — **all ✅, tree clean, branch `claude/sharp-davinci-8vg872`.** Slice-2 anchors spot-checked on-disk: `provider_cardio_resolve` (`DISCIPLINE_TO_PLAN_SPORT` + `resolve_cardio_discipline`), `garmin_fit_parser._garmin_disc_token` + `parse_fit` sets `discipline_id`, `routes/garmin.py` 3 INSERTs balanced, seed `CARDIO_DISCIPLINE_MAP['garmin']`, migration `init_db.py` ADD COLUMN. Cardio resolver tests 19/19. PRs #738/#739 merged. **No on-disk drift** — but the live-verify (below) exposed a prod-vs-disk gap the anchor sweep can't see (the DB had silently not applied the migration).

## §2 — What happened (the incident)

Andy uploaded a real Garmin **MTB** FIT to do the Slice-2 §5 live-verify and hit **`500 on POST /garmin/import/confirm`** (req_6ef7da755d). Traceback (Andy pasted `/admin/logs`, Rule #14):

    psycopg2.errors.UndefinedColumn: column "discipline_id" of relation "cardio_log" does not exist

The Slice-2b route code (which writes `discipline_id`) had deployed, but the **column was never created in prod**.

**Root cause.** `init_postgres()` runs `PG_SCHEMA` via `PG_SCHEMA.split(';')` — a char-based split that doesn't understand SQL comments. The comment above `provider_raw_record` read `-- Slice 1; its first writers …`; that `;` split the comment mid-line into the bare-text fragment `its first writers (…)`, a **syntax error** in the **unguarded** schema loop. So `init_postgres()` aborted on **every cold start since Slice 1 (#733, 2026-06-18)** — caught only by `app.py`'s broad `except Exception` ("DB init skipped"). Consequence: **nothing added to the schema/migrations from #733 onward reached prod** — `provider_value_map`, `provider_raw_record` (Slice 1) AND `cardio_log.discipline_id` (Slice 2a).

**Diagnosis path (Rule #14, all via the read-only `neon-query` Action — container can't reach Neon):**
- `cardio_log` columns: everything through the #694 cull (2026-06-17) present; `discipline_id` absent.
- probes at lines 2127/2144/2253/2275/2364 all present; index 2365 + backfill (111 rows) + cull (0 remaining) present → loop reached line 2399.
- `provider_value_map` → **`relation does not exist`** — the decisive clue: a Slice-1 *table* (in `PG_SCHEMA`, not a migration) was also missing → init aborts in the PG_SCHEMA phase, before committing anything new. Reproduced the bad split locally (`init_db.PG_SCHEMA.split(';')` yields the malformed fragment).

## §3 — Files (substantive)

**#742 (init_postgres fix):**
- `init_db.py` — removed the `;` from the `provider_raw_record` comment; **hardened the `PG_SCHEMA` loop** (per-statement `try/except` → `commit`/`rollback` + Rule #15 log, mirroring the migration loop) so one malformed fragment can't silently abort all schema init.
- `tests/test_init_db_schema.py` (NEW) — asserts no `PG_SCHEMA.split(';')` fragment is non-statement (i.e. no `;` in a comment) + the provider tables survive as their own CREATE fragments.

**#744 (hub uploader real + drag guard):**
- `templates/connections/hub.html` — the fake single-file drop card → the proven bulk uploader (`data-bulk-*` → `app.js`, posts to `import_bulk`).
- `static/app.js` — window-level file-drop guard (a file dropped outside any zone is swallowed, not opened by the browser); scoped to file drags.
- `tests/js/app_ui.test.mjs` — +3 jsdom tests (stray drop/dragover prevented; non-file drag untouched).

**#746 (unify workout + wellness):**
- `routes/garmin.py` — `import_bulk` now classifies each file by FileId kind (`fit_file_meta`) and routes BOTH: workouts → cardio/strength; `_WELLNESS`/`_METRICS`/`_SLEEP_DATA`/`_HRV_STATUS` → `wellness_log`/`garmin_daily_metrics`. Extracted shared `_ingest_wellness_fit` helper (used by `import_bulk` + `import_wellness_bulk`; the wellness endpoint's loop is now a one-line call — behavior-preserving). Activity path falls back to wellness ingestion if `parse_fit` finds no session.
- `templates/connections/hub.html` — copy updated ("workouts and wellness/daily-metric files").

**Bookkeeping (ceiling-exempt):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, issue #747 (residual), #681 comment.

## §4 — Code / tests / verification

- Full Python suite **2671 passed / 30 skipped** (2669 baseline + 2 new schema tests); JS harness **15/15** (12 + 3 new). `routes.garmin` imports clean; `node --check static/app.js` clean; Jinja parse of `hub.html` clean.
- **Prod, post-#742 deploy (`neon-query`):** `provider_value_map` = **263 rows**, `provider_raw_record` present, `cardio_log.discipline_id` present.
- **§5 Slice-2 MTB live-verify — DONE:** re-import succeeded (302, not 500); `cardio_log` newest row = `Mountain Biking · discipline_id=D-008` (older rows NULL — additive, as designed). The `[cardio-ingest] garmin-fit … D-008` Rule #15 line prints during `POST /garmin/import` (buried under `fit_tool` field-not-defined warnings — filter `/admin/logs?q=cardio-ingest`).

## §5 — Manual verification owed (Andy)

- **Optional:** the trail-run half of Slice-2 §5 (import a trail run → expect `discipline_id=D-001`). MTB half is done.
- **Optional:** drop a mixed workout+wellness folder on the hub uploader and confirm the per-file result lines route each correctly (the dedicated wellness page still works too).
- Carried, unchanged: post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **Resume the #681 §4 provider-translation main path — Slice 2c:** the §12 indoor-machine flag into `provider_raw_record.raw_payload` (that table's first writer; it now actually exists in prod). Strava `VirtualRide`/`StairStepper`, RWGPS `is_stationary`, Wahoo `workout_type_location_id`, Garmin indoor sub_sports. No new vocab. Design §6 step 4 + matrix §12.3 gap 1.
2. **Slice 3** — Polar/COROS ingest consolidation into core + `provider_raw_record`; then the **zero-row-guarded** bespoke-table drops (irreversible; live `neon-query`-gated). `provider_outbound_ref` waits for the outbound wave.
3. **#747 residual hardening** (low-priority): brittle `PG_SCHEMA.split(';')` + unguarded post-migration seeds.
4. **Deferred (matrix §7):** Batch 4 MyFitnessPal (Layer-2E-blocked); Batch 5 Apple/Samsung/Google Health (native-client-gated).

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| U-1 | Hub uploader scope for mixed FITs | **Unify — one drop zone auto-routes both workout + wellness** (over two side-by-side zones) |

The init_postgres fix + the hub-uploader-is-a-fake-drop-zone fix were straight bug fixes (executed, not balloted). The "the single uploader supported both" premise was reconciled: it never did — activity and wellness FITs always had separate importers; #746 is the new unified wiring.

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Schema-loop fix | `init_db.py` | comment reads `-- Slice 1. First writers …` (no `;`); the `PG_SCHEMA` loop body is `try: cur.execute(stmt); conn.commit() except: conn.rollback(); print("[init_db] schema stmt failed…")` |
| Schema regression test | `tests/test_init_db_schema.py` | `test_pg_schema_has_no_mid_comment_semicolon_split` + `test_provider_tables_present_in_schema` |
| Hub uploader | `templates/connections/hub.html` | `data-bulk-upload data-endpoint="{{ url_for('garmin.import_bulk') }}"` + `data-bulk-drop`/`data-bulk-files multiple`; copy mentions "wellness/daily-metric files" |
| Drag guard | `static/app.js` | "Window-level file-drop guard" IIFE; `['dragover','drop']` → `window.addEventListener` → `if (isFileDrag(e)) e.preventDefault()` |
| Unified routing | `routes/garmin.py` | `import_bulk` has "Phase 0 — classify each file by its FileIdMessage kind"; `_ingest_wellness_fit` defined once, called by `import_bulk` + `import_wellness_bulk` |
| Prod state | `neon-query` | `provider_value_map` 263 rows; `provider_raw_record` exists; `cardio_log.discipline_id` exists; newest `cardio_log` row D-008 |
| Tests | full suite | 2671 passed / 30 skipped; JS 15/15 |
| PRs / issues | #742, #744, #746 (MERGED); #747 (open, residual); #681 (open, commented) | — |

## §9 — Carry-forward

- **Slice 2c is the next #681 §4 deliverable** — first `provider_raw_record` writer; the table now exists in prod (it didn't before #742). No new vocab.
- **#747** — `init_postgres` residual hardening (brittle split + unguarded seeds). Low-priority; acute bug fixed + regression-tested.
- **`cardio_log.discipline_id` still has no downstream consumer** — populated by the Garmin paths; consumers (Layer-1 fidelity, completed-history, multi-source precedence) land in later waves.
- **Lesson:** a green `verify-handoff.sh` + clean on-disk anchors do **not** prove prod applied them. When a handoff claims a migration shipped, a prod `neon-query` is the only proof for the DB half (the container can't reach Neon, so this is the standing check for any schema change claimed "live").
