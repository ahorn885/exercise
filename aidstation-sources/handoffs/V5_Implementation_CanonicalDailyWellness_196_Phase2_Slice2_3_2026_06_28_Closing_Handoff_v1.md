# V5 Implementation — #196 Phase 2 Slice 2.3: Repoint the Layer-3A Wellness Reader at `canonical_daily_wellness` — Closing Handoff (2026-06-28)

**Branch:** `claude/wellness-bulk-import-name-error-6o9dir` · **Commit:** `fded20d` · **Suite:** 3582 passed / 30 skipped · **PR:** not yet opened (awaiting Andy's go) · **Design:** `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md` · **Epic:** #196 (stays OPEN — Phase 4–5 remain).

> **▶ IMMEDIATE NEXT:** Phase 4 — recovery-aware planning (LLM-soft). It's a **STOP-AND-ASK** (Trigger #1 prompt design + #3 cross-layer): design gate + AskUserQuestion before any code. Prereq for its live spot-check (not its unit work): wellness data must flow — Andy re-uploads Garmin wellness zips after the #934 deploy → `daily_wellness_metrics` fills → the Slice-2.2 hook materializes `canonical_daily_wellness` → this reader has rows.

---

## 1. What this slice did (one line)

`q_layer3A_recent_wellness` stopped re-deriving the per-day multi-source wellness merge inline and now reads the **materialized** `canonical_daily_wellness` row Slice 2.2 writes — folding the duplicated coalesce into one home (`canonical_wellness.py`) and keeping the 3A bundle hash / cache key **byte-identical** across the repoint.

## 2. Context

The #196 Phase 2 plan (design §, and the Slice 2.1/2.2 handoffs): 2.1 built the `canonical_daily_wellness` table + writer; 2.2 hooked the writer into every wellness ingest path + backfill; **2.3 (this) repoints the first reader at the table** and retires the inline coalesce so the merge logic lives in exactly one place. Slice 2.1 deliberately *copied* `_WELLNESS_SOURCE_PRIORITY` + the coalesce into `canonical_wellness.py` and flagged the dedup for 2.3.

The #933 wellness-import bug (separate, merged PR #934) is what kept prod wellness empty; this slice's unit work did **not** need that data, but the live spot-check does.

## 3. What shipped (4 substantive files)

- **`layer3a/integration.py` — `q_layer3A_recent_wellness`:** replaced the ~190-line inline six-source coalesce (garmin `daily_wellness_metrics` + polar/coros/whoop/oura `provider_raw_record`, freshest-non-null per field) with a single `SELECT date, total_sleep_hours, total_sleep_hours_source, hrv_rmssd_ms, hrv_rmssd_ms_source, resting_hr, resting_hr_source FROM canonical_daily_wellness WHERE user_id=%s AND date >= %s ORDER BY date DESC`. Maps the **TEXT** `date` back to a `date` via `_as_date`; **skips context-only rows** — a canonical row that carries only Garmin context (training_readiness/vo2max, all three coalesced device fields NULL) is skipped in Python (`if sleep_h is None and hrv_v is None and rhr_v is None: continue`), because the old coalesce only emitted a record for days with ≥1 device sleep/HRV/resting-HR value. Deleted the now-dead helpers `_WELLNESS_SOURCE_PRIORITY`, `_WellnessCandidate`, `_coalesce_wellness_field`, and the orphaned `WellnessSource` import.
- **`init_db.py` — `canonical_daily_wellness` columns widened `REAL → DOUBLE PRECISION`:** `total_sleep_hours`, `hrv_rmssd_ms`, `hrv_7d_avg_ms`, `vo2max_running`, `vo2max_cycling`. Done in the CREATE DDL (fresh DBs) **and** as 5 idempotent `ALTER TABLE … ALTER COLUMN … TYPE DOUBLE PRECISION` entries appended to the same `_PG_MIGRATIONS` block (existing DBs). Public-schema → **auto-applies on each Vercel deploy; no Neon apply owed.** (See §4 for why this was load-bearing.)
- **`tests/test_layer3a_integration.py`:** rewrote `TestRecentWellness` to the canonical-read shape (new `_canon_well_row` helper; tests for single-SELECT-against-canonical, the 14d cutoff param, full-field mapping, partial-field pass-through, **context-only-row skip**, query-order preservation). The coalesce/tiebreak/freshness tests it used to hold now live in `canonical_wellness`' `TestCoalesce`. Fixed the 3 `TestAssembleBundle` tests that assumed wellness = 6 queries (now 1 → the bundle issues **12** reads, `1+1+1+2+7`).
- **`tests/test_wellness_reader_equality.py` (NEW):** the deterministic-equality guard the design called for. Keeps the pre-2.3 inline reader **verbatim** as `_old_inline_recent_wellness`; drives one fixture set (garmin + whoop/coros/oura provider rows, deliberately non-single-precision values, plus a context-only day) through both the OLD path and the NEW path (`materialize_canonical_wellness` into an in-memory canonical store → `q_layer3A_recent_wellness` reads it back) and asserts the two `recent_wellness` lists are **identical**. Plus a shape-pin (so the equality can't pass vacuously on `[] == []`) and a both-paths-skip-the-context-only-day test.

`canonical_wellness.py` is comment-only (it's now the documented sole owner of the coalesce) — not counted against the ceiling.

## 4. Key decision — REAL → DOUBLE PRECISION (Andy ratified via AskUserQuestion)

The repoint's hard constraint (design): the new path must be **byte-identical** to the inline path for the same data, or it silently invalidates 3A caches. `Layer3AIntegrationBundle.recent_wellness` folds into `integration_bundle_hash = compute_payload_hash(bundle)` → `canonical_json` → `json.dumps` with **Python's full float repr** → the 3A cache key (`layer3a_athlete_state_key`).

The snag the design didn't catch: `canonical_daily_wellness` stored `total_sleep_hours`/`hrv_rmssd_ms` as **`REAL`** (single precision), but the inline reader emitted full **doubles** (it does not even round HRV). A REAL round-trip turns `54.7` into `54.70000076293945` → a different hash → cache invalidation. (Garmin-sourced HRV happens to be stable because its source column is already REAL, but provider HRV/sleep from JSONB `::float` are true doubles, and sleep-hours is always a rounded double.)

Options put to Andy: (A) widen the canonical numeric cols to DOUBLE PRECISION, then repoint losslessly; (B) just repoint, keep REAL (safe in practice — inline path retired, prod has no wellness-bearing 3A caches today — but OLD≠NEW by ~1e-7 across the deploy); (C) defer. **Andy chose A.** The table is empty in prod (the Slice-2.2 backfill returned 0 rows), so the ALTER is a trivial, zero-risk rewrite, and it makes OLD==NEW literally true.

## 5. Tests + verification

- `SECRET_KEY=x DATABASE_URL='…connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3582 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217). Run the **full** `tests/` — isolated single-file collection hits the documented circular-import quirk.
- Static-verifiable: `q_layer3A_recent_wellness` issues one `canonical_daily_wellness` SELECT and no longer references `_coalesce_wellness_field`/`_WELLNESS_SOURCE_PRIORITY` (deleted); `init_db.py` shows the 5 columns as DOUBLE PRECISION + the 5 ALTERs.
- **OWED (Andy, post-#934-deploy + re-upload):** the multi-source LIVE-VERIFY — confirm a day with ≥2 sources materializes one canonical row with the right per-field source picks, and that 3A reads it. Unit-covered; this is live proof only.

## 6. NEXT — Phase 4: recovery-aware planning (LLM-soft) — STOP-AND-ASK

Phase 2 is now consumer-ready (substrate + writer + hooks + the first reader repoint). Phase 4 threads `recent_wellness` (suppressed HRV / sleep debt / poor readiness) + `connected_providers.has_recent_*` into the **Layer-4** plan-gen prompts — PerPhase synthesis, the Refresh T1-3 prompts, RaceWeekBrief — so the plan conditions on recovery state. The mechanism is **LLM-soft guidance** (pre-ratified, design §). This is **Trigger #1 (prompt design) + #3 (cross-layer)** → enter `/plan`, present the prompt-body changes + the threading surface, AskUserQuestion, and wait. Do **not** code first.

Deferred/optional within Phase 2: the `/wellness` chart repoint (`routes/wellness.py` → `canonical_daily_wellness`) — low-risk, decide at build; `coaching.get_wellness_summary` stays out of scope (v1-coaching-only).

**Parallel paused thread:** #884 gear/craft is mid-arc at slice 3b (slices 4→6 remain, design-v3 §15) — resume when Andy redirects.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this slice). 3. `CARRY_FORWARD.md` → *"#196 … Phase 2 — canonical daily-wellness layer"* (the 2.1/2.2/2.3 bullets). 4. This handoff + the Slice 2.1/2.2 handoffs + `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md`. 5. `layer3a/integration.py:q_layer3A_recent_wellness` (the repointed reader) + `canonical_wellness.py` (`materialize_canonical_wellness` + the sole-owner coalesce). 6. `./scripts/verify-handoff.sh`.

## 7. Open questions
- **`/wellness` chart repoint** — in-scope for a Phase-2 cleanup or leave on the inline path? Low-risk either way; decide at build.
- **Backfill vs let-it-ride** — once Andy re-uploads, on-ingest materialization fills canonical for new days automatically; only re-run `backfill-canonical-wellness` if historical days are wanted.

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Reader repoint | `layer3a/integration.py` | `q_layer3A_recent_wellness` issues one `SELECT … FROM canonical_daily_wellness WHERE user_id = %s AND date >= %s ORDER BY date DESC`; skips rows where sleep+hrv+rhr all None; **no `_coalesce_wellness_field` / `_WELLNESS_SOURCE_PRIORITY` / `WellnessSource`** remain (grep → 0) |
| Schema widen | `init_db.py` | `canonical_daily_wellness` CREATE shows `total_sleep_hours … DOUBLE PRECISION` (×5 cols) + 5 `ALTER TABLE canonical_daily_wellness ALTER COLUMN … TYPE DOUBLE PRECISION` in `_PG_MIGRATIONS` |
| Sole-owner coalesce | `canonical_wellness.py` | module docstring + `_WELLNESS_SOURCE_PRIORITY` comment say "single home / sole owner since Slice 2.3" |
| Equality test | `tests/test_wellness_reader_equality.py` | `TestReaderEquality::test_new_path_equals_old_inline` (+ `test_expected_shape`, `test_context_only_day_skipped_both_paths`) |
| Reader tests | `tests/test_layer3a_integration.py` | `TestRecentWellness` uses `_canon_well_row` / single canonical SELECT; `TestAssembleBundle` queues 12 (not 17) |
| Suite | — | `… pytest tests/ -q` → 3582 passed / 30 skipped |
| Neon | — | **No apply owed** — DDL + ALTERs are public-schema, auto-apply on Vercel deploy |
| Epic | #196 | OPEN — comment Slice 2.3 shipped (commit/PR ref); Phases 4–5 remain |
