# V5 Implementation — Cross-Source Activity Dedup + Merge (#196 Phase 3) — Slice 1 — Closing Handoff (2026-06-22)

**Branch:** `claude/admiring-albattani-pp6zqi` · **Commit:** `221d96a` (+ merge `f876a4b`) · **Suite:** 3446 passed / 30 skipped (post-merge) · **PR:** [#906](https://github.com/ahorn885/exercise/pull/906) — **MERGED 2026-06-22** (squash `80b071b`).
**Predecessor:** the kickoff `handoffs/V5_CrossSourceActivityDedup_196_Phase3_Kickoff_2026_06_22_v1.md` (the problem, the design defaults, the slice sequence, the Trigger-#3 DDL gate). This handoff is **Slice 1** of that plan.

**Merge note (parallel collision, resolved).** While #906 awaited CI, `main` advanced with #885/#892 (race event type) + #905 (#886/#893), which also appended to `init_db.py:_PG_MIGRATIONS` and touched `CURRENT_STATE.md` → #906 went conflicted. Both conflicts were **additive**: kept this slice's `_PG_MIGRATIONS` block alongside the #892 `framework_sport` heal; took main's `CURRENT_STATE.md` and re-applied this slice's pointer on top. Merge `f876a4b`, full suite re-verified **3446 passed / 30 skipped**, auto-merged as squash `80b071b`. (The CARRY_FORWARD parallel-build lesson again — check `origin/main` before/at PR time.)

---

## 1. The problem (one line)

One real-world activity reaching us via N connected providers (a Wahoo ride auto-forwarded to Strava) lands as **N `cardio_log` rows** — verified repro: user 1 rows 73 (Wahoo) + 74 (Strava), same ride. Per-source `*_uidx` idempotency works; **nothing recognizes the two rows are the same activity.** Phase 3 adds a clustering + canonical-merge layer *above* per-source dedup.

## 2. Trigger-#3 ratification (what Andy decided before any code)

`cardio_log` is read by Layers 3A + 4 → a new cluster/canonical shape is an inter-layer contract change (Trigger #3). Brought options A/B + a recommendation; **Andy chose:**

- **Storage shape B** — a real `activity_clusters` table + `cardio_log.cluster_id` FK (NOT the kickoff's recommended option A flag-on-`cardio_log`). Cleaner domain separation; the cost is more consumer rewiring at Slice 4 + keeping `canonical_activity` in sync at Slice 3.
- **A UTC `started_at TIMESTAMP`** on `cardio_log` as the fingerprint's comparable start instant.

Then ratified the concrete Slice-1 DDL (the literal columns below) before the migration was written.

## 3. What Slice 1 shipped (5 substantive files)

The **schema substrate + the `started_at` ingest population**. No matching logic, no canonical materialization, no consumer repoint — those are Slices 2/3/4.

- **`init_db.py`** (`_PG_MIGRATIONS` tail) — additive, idempotent, public-schema (auto-applies on Vercel deploy; **no manual Neon apply owed**):
  - `cardio_log.started_at TIMESTAMP` — the UTC fingerprint instant. **Distinct from the existing `start_time TEXT`** (D-56 race/time-of-day display, local `HH:MM:SS` paired with the TEXT date).
  - `activity_clusters` table — one row per real-world activity: `id` / `user_id` / `sport_class TEXT` / `started_at TIMESTAMP` / `duration_min` / `distance_mi` / `created_at` / `updated_at`. The fingerprint anchor (coarse class + start + duration/distance — match the **coarse** `activity`/`plan_sport_type`, not the fine `discipline_id`, per kickoff §6). **EMPTY until Slice 2's clusterer** (its immediate first writer).
  - `cardio_log.cluster_id INTEGER REFERENCES activity_clusters(id)` — the link; stays NULL until Slice 2. (Table migration ordered before the FK migration so the reference resolves.)
  - Indexes: `activity_clusters_user_start_idx (user_id, started_at)` (Slice-2 candidate lookup); `cardio_log_cluster_idx (cluster_id) WHERE cluster_id IS NOT NULL`.
- **`routes/garmin.py`** — `_normalize_started_at(data)` (NEW): resolves one **naive-UTC `datetime`** from `data['started_at']` else `_provider_raw.observed_at`; accepts ISO-8601 with `Z` / numeric offset / date-only / a `datetime` object; converts aware→UTC; returns `None` (never raises) on absent/unparseable, logging the miss. `_bulk_insert_cardio` writes `started_at` (column + value added; placeholders 32→33) and Rule #15-logs the resolved instant (`[cardio-insert] … started_at=…`). Imports widened: `from datetime import date, datetime, timedelta, timezone`.
- **`routes/strava_ingest.py`** — `normalize_strava_activity` now sets `'started_at': a.get('start_date')` (Strava's **true UTC**). Its `_provider_raw.observed_at` prefers `start_date_local` (local wall-clock) — correct for its existing contract, but wrong as a cross-source fingerprint, so the UTC value is passed explicitly. Surgical: `observed_at` untouched.
- **`tests/test_garmin_bulk_source.py`** — `TestNormalizeStartedAt` (Z / fractional-Z / offset→UTC / date-only→midnight / explicit-wins / aware-datetime / absent→None / unparseable→None) + `TestCardioInsertStartedAt` (column present + resolved value in params; NULL start doesn't break the insert).
- **`tests/test_strava_ingest.py`** — `test_started_at_uses_utc_start_date_not_local` (started_at = `start_date`; observed_at still = `start_date_local`).

## 4. Decisions baked in (review these)

1. **Strava UTC split** — only `started_at` uses `start_date`; `observed_at`'s local-preferring contract is untouched (surgical).
2. **Manual FIT/TCX/GPX carry date-only starts today** (`garmin_fit_parser.py:_fit_timestamp_to_date` → `observed_at` = `data['date']`; `tcx_gpx_parser.py` `observed_at` = `activity_date`), so their `started_at` lands at **00:00 UTC**. Acceptable for Slice 1 — manual single-source uploads are least likely to cross-source-dup. Finer extraction (both parsers DO compute a full start datetime internally — FIT `session.start_time`, TCX/GPX `start_dt` — before truncating) is a **Slice-2 follow-up only if the clusterer needs sub-day precision**.
3. **`canonical_activity` + per-field provenance deferred to Slice 3** — they land with their first writer (materialization), not created speculatively now (avoids the `provider_outbound_ref` "table built with no consumer" smell). Option B still holds; only the timing moved.
4. **No backfill** of existing rows' `started_at` — it's a data `UPDATE` (not DDL; would need the Neon-write Action), and rows 73/74 are disposable test data. The Slice-2 clusterer must tolerate NULL `started_at` (kickoff §6 fallback).

## 5. Tests

`SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:1/db?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3425 passed / 30 skipped** (pre-existing skips; 2 pre-existing Layer3B warnings, unrelated). Touched-file run (`test_garmin_bulk_source` + `test_strava_ingest`) = 38 passed. INSERT column/placeholder/param parity verified **33/33/33** at runtime (the fake-db tests don't validate `%s`↔param count, so this was checked separately).

## 6. NEXT — Slice 2 (the clusterer; kickoff §5)

A pure-ish function `cluster_activity(db, user_id, new_row) -> cluster_id` called by `_bulk_insert_cardio` (and the manual path) right after insert: compute the fingerprint, find same-user `activity_clusters` candidates within tolerance (the `(user_id, started_at)` index is the lookup), attach to an existing cluster or open a new one, set `cardio_log.cluster_id`. **Must be idempotent + re-entrant** — re-runs and late arrivals (RWGPS cron-deferred up to 24h; Strava lags minutes) must not fork clusters; this is the riskiest part. Match on the **coarse** sport class; fall back to `(sport-class, start±, duration±)` when distance is 0/NULL (indoor — the repro). Instrument per Rule #15 (inputs + match/no-match + cluster id). Open tolerance/scoring questions carried in §9.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this Slice 1). 3. `CARRY_FORWARD.md` → *"#196 cross-source activity dedup"*. 4. This handoff + the kickoff (`…196_Phase3_Kickoff…`). 5. `routes/garmin.py:_bulk_insert_cardio` + `_normalize_started_at`; `init_db.py` `activity_clusters` block. 6. `./scripts/verify-handoff.sh`.

## 7. Open questions (carry from the epic / kickoff §9 — decide with Andy at Slice 2/3)
- Completeness-scoring weights (Slice 3) — what makes one source "more robust" for a given activity (power? HR? GPS? sample density?).
- Dedup tolerance windows (Slice 2) — start-time ± minutes; duration/distance ± %.
- Conflict surfacing (Slice 5, optional) — show the athlete when sources materially disagree, or merge silently?

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| `started_at` column | `init_db.py` | `ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS started_at TIMESTAMP` (grep) |
| Clusters table | `init_db.py` | `CREATE TABLE IF NOT EXISTS activity_clusters (` with `sport_class` / `started_at` / `duration_min` / `distance_mi` (grep) |
| Cluster FK + index | `init_db.py` | `cluster_id INTEGER REFERENCES activity_clusters(id)` + `cardio_log_cluster_idx` + `activity_clusters_user_start_idx`; table migration precedes the FK migration (grep) |
| UTC normalizer | `routes/garmin.py` | `def _normalize_started_at` — reads `data['started_at']` ∥ `_provider_raw.observed_at`; `astimezone(timezone.utc).replace(tzinfo=None)`; returns None on miss (grep) |
| Cardio writer wiring | `routes/garmin.py` | `_bulk_insert_cardio`: `started_at = _normalize_started_at(data)`; `started_at` in the INSERT column list; `[cardio-insert] … started_at=` Rule #15 print (grep) |
| Strava UTC start | `routes/strava_ingest.py` | `'started_at': a.get('start_date')` in `normalize_strava_activity` (grep) |
| Tests | `tests/test_garmin_bulk_source.py` / `tests/test_strava_ingest.py` | `TestNormalizeStartedAt` + `TestCardioInsertStartedAt`; `test_started_at_uses_utc_start_date_not_local` |
| Suite | — | `… pytest tests/ -q` → 3446 passed / 30 skipped (post-merge, incl. #885/#892/#905 tests) |
| Issue | #196 | comment: Phase 3 Slice 1 (schema + started_at) shipped + MERGED via #906 (squash `80b071b`); stays open through Slice 4 (consumer repoint) |
