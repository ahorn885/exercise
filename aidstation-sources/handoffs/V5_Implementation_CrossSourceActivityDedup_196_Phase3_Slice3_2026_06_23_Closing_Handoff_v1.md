# V5 Implementation — Cross-Source Activity Dedup + Merge (#196 Phase 3) — Slice 3 — Closing Handoff (2026-06-23)

**Branch:** `claude/dreamy-keller-cd9pw5` · **Suite:** 3502 passed / 30 skipped · **PR:** [#916](https://github.com/ahorn885/exercise/pull/916).
**Predecessors:** the kickoff `handoffs/V5_CrossSourceActivityDedup_196_Phase3_Kickoff_2026_06_22_v1.md` (problem, design defaults, slice sequence, Trigger-#3 gate), **Slice 1** `…Slice1_2026_06_22…` (schema substrate + `started_at`), **Slice 2** `…Slice2_2026_06_23…` (the clusterer). This is **Slice 3** — completeness scoring + canonical materialization.

---

## 1. The problem (one line)

One real-world activity reaching us via N connected providers (a Wahoo ride auto-forwarded to Strava) lands as **N `cardio_log` rows** (repro: user 1 rows 73 Wahoo + 74 Strava). Slice 1 added the substrate; Slice 2 **groups** the duplicates into one `activity_clusters` row; **Slice 3 merges each cluster into ONE best-of `canonical_activity` record** + per-field provenance. Slice 4 (next) repoints consumers so training-load/compliance count the ride once.

## 2. The decisions ratified this session (Trigger #3)

`canonical_activity` is a new table Slice-4 consumers (Layers 3A/4, dashboard, etc.) will read → an inter-layer contract change → **Trigger #3**. Brought the literal DDL + scoring weights; **Andy ratified (2026-06-23) via two AskUserQuestion rounds:**

1. **"Richest data wins"** completeness scoring (not flat field-count, not per-sport): sensor/device-grade metrics outweigh GPS/derived outweigh baseline. Weights **3 / 2 / 1** (§3).
2. **A separate `canonical_activity` record** (not an in-place flag/gap-fill on `cardio_log`) — consistent with Slice-1 **storage shape B** (`activity_clusters` table + `cardio_log.cluster_id` FK). Wide table mirroring `cardio_log`'s mergeable columns (vs a thin table + read-time coalesce-join) so Slice-4 consumers read it almost identically to a `cardio_log` row — the kickoff's "materialized merged record" intent.

## 3. What Slice 3 shipped (3 substantive files)

- **`init_db.py`** (`_PG_MIGRATIONS` tail) — additive, idempotent, public-schema (**auto-applies on Vercel deploy → no Neon apply owed**):
  - `canonical_activity` — one row per cluster. `id` / `user_id` / `cluster_id` (**UNIQUE** — the upsert key) / `primary_cardio_log_id` / `completeness_score` + the **29 mergeable columns** mirrored from `cardio_log` (4 unscored identity — `date`/`activity`/`discipline_id`/`started_at` — + 25 scored metric fields incl. `activity_name`) + `created_at`/`updated_at`. Index `canonical_activity_user_idx (user_id)`.
  - `canonical_activity_field_provenance` — `id` / `cluster_id` / `field_name` / `source_cardio_log_id` / `source_provider` / `last_updated_at`; **UNIQUE `(cluster_id, field_name)`**; index `cafp_cluster_idx (cluster_id)`. Mirrors the `athlete_profile_field_provenance` pattern; reserves a `source_provider='manual_override'` slot (no writer yet — see §4).
- **`routes/garmin.py`** (the substance) — appended after `cluster_activity`, before `_bulk_insert_cardio`:
  - **`materialize_canonical_activity(db, uid, cluster_id)`** — loads the cluster's `cardio_log` members (`SELECT … WHERE cluster_id = ? ORDER BY id`); if none, defensively clears the canonical row + provenance and returns. Else ranks members by `_primary_rank` (richest completeness first, static source order tiebreak), takes `ranked[0]` as **primary**; for each canonical field picks the value of the highest-scoring copy that carries one (`_has_value`), recording `(source_cardio_log_id, provider)` provenance; **upserts** `canonical_activity` (`ON CONFLICT (cluster_id) DO UPDATE`) and **replaces** the cluster's provenance rows wholesale. Rule #15: `[cardio-canon] cluster=… members=… primary=id…/<provider> score=… fields={field<-provider,…}`.
  - **`_METRIC_WEIGHTS`** — the 25 scored metric fields → weight. **Tier 3** (power avg/max/norm, HR avg/max, aerobic/anaerobic TE, running dynamics stride/vosc/vratio/gct/gct_balance, swim swolf/active_lengths). **Tier 2** (elev gain/loss, cadence avg/max, avg_speed, avg_pace, calories, moving_time_min). **Tier 1** (duration_min, distance_mi, activity_name). `_IDENTITY_FIELDS` (date/activity/discipline_id/started_at) are primary-wins, non-null gap-fill, **unscored**. `_CANONICAL_FIELDS = identity + metrics` (29).
  - **`_has_value(v)`** — meaningful iff non-null, non-zero numeric (a 0 avg_power/0 distance = sensor absent — same 0-is-"can't tell" posture as the Slice-2 `_metric_within`), non-empty text.
  - **`_completeness_score(row)`** — Σ weights over meaningful metric fields. **`_row_provider(row)`** — origin provider from whichever `_PROVIDER_ID_COLUMNS` id is set (`garmin`/`wahoo`/`polar`/`coros`/`rwgps`/`strava`; `unknown` if none). **`_primary_rank(row)`** — `(-score, _SOURCE_ORDER[provider])`.
  - **Wired into `cluster_activity`'s BOTH return paths** (MATCH at the attach, NEW at open) → re-materializes on **every member add**, so a late Strava/RWGPS arrival re-merges. Runs inside the same txn + per-user advisory lock the clusterer already holds (serialized, atomic).
- **`tests/test_garmin_bulk_source.py`** — `TestCompletenessScore` (×3: sensor>baseline, 0/NULL=0, weight sum), `TestRowProvider` (×1), `TestMaterializeCanonical` (×6: single-member mirror; richest-wins primary + gap-fill [the repro shape — power from Wahoo, elevation from Strava]; score-tie → source order; upsert `ON CONFLICT` + provenance-replace; no-members clears; `cluster_activity` MATCH triggers re-materialization). New fakes `_CanonConn` + `_member`/`_canon_insert`/`_prov_rows` helpers. **+10 tests.**

## 4. Decisions baked in (review these)

1. **Wide canonical table, not thin + read-time join.** `canonical_activity` duplicates ~25 metric columns so Slice-4 consumers read it like a `cardio_log` row (swap table + filter by cluster), not a coalesce-across-provenance pivot. Materialized values = the kickoff's "merged record" intent; re-materialization keeps them fresh.
2. **`0`/`NULL` = absent (scoring + merge).** A `0` numeric never scores and is never chosen as a merged value; if **all** copies are 0/NULL for a field, canonical stores **NULL**. Cost: a *legitimately* zero metric (e.g. a flat run's `elev_gain_ft=0`) lands NULL not 0 — acceptable (consumers treat NULL/0 elevation alike), and indistinguishable from "sensor absent" at the value level anyway. Mirrors the Slice-2 clusterer.
3. **Tiebreaker = provider-column order, manual-upload NOT specially ranked.** `_SOURCE_ORDER` is `garmin>wahoo>polar>coros>rwgps>strava`; it only fires on an exact score tie (rare). I dropped the kickoff-floated "manual-upload last" sub-rank — distinguishing a manual file upload from a webhook within a provider needs prefix-sniffing (`fit:`/`<provider>-file:`) and only matters on a tie-of-a-tie. Simplicity-first; flag if it ever bites.
4. **"Manual override always wins" (kickoff §4) deferred, slot reserved.** No per-field manual-edit path for cardio exists today, so nothing writes `manual_override`. The provenance `source_provider` column leaves room (mirrors `athlete_profile_field_provenance`'s `manual_override`); building the override mechanism is out of scope here. **Conscious deferral, not omission.**
5. **Singletons get a canonical row too.** A single-source activity = a 1-member cluster → a canonical_activity row materialized from that one copy. Intentional: Slice 4 reads `canonical_activity` uniformly for **all** clustered activities rather than special-casing singletons. **NULL-`started_at` rows are never clustered (Slice 2) → they have no cluster and no canonical row; Slice 4 must read those raw (tolerate NULL `cluster_id`).**
6. **Re-materialization is the only writer; provenance replaced wholesale.** `DELETE … WHERE cluster_id` then re-INSERT each field, so a field that lost its source on a re-merge can't leave a stale provenance row. Canonical upserts by `cluster_id` (idempotent; `created_at` preserved, `updated_at=NOW()`).

## 5. Tests

`SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:1/db?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3502 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217, unrelated). Touched-file run (`test_garmin_bulk_source` + `test_strava_ingest`) = **60 passed** (+10). Canonical INSERT placeholder/param parity **33/33** verified by inspection (`insert_cols` = 2 + 29 canonical + 2 = 33; `VALUES` = 33 `?` + literal `NOW()`; the fake-db tests don't validate `%s`↔param count). DDL parses (full suite imports `init_db` via `app`).

## 6. NEXT — Slice 4 (repoint consumers; kickoff §5)

Repoint the readers that must show "one activity, best-of" rather than N rows at `canonical_activity`: `routes/connections.py` (`_ACTIVITY_SQL` Files list + Manual/Synced chip), `routes/dashboard.py`, `routes/cardio.py`, `routes/training.py`, `routes/plans.py` (plan-match/compliance), `layer3a/integration.py` + `layer3a/builder.py` (recent-activity → athlete state), `layer4/context.py` (plan-gen context), `coaching.py`, `routes/profile_extractors.py` (HRmax-from-cardio). **Collapse a cluster's N `cardio_log` rows → its one `canonical_activity` row** (join through `cluster_id`, or read canonical + the unclustered remainder). **MUST tolerate NULL `cluster_id`** — pre-Slice-2 rows + NULL-`started_at` rows have no cluster/canonical and must still surface from `cardio_log`. This is the slice that makes training-load/compliance count the ride once; it's also where the per-field provenance can surface in the UI ("power from Wahoo"). #196 stays OPEN until this lands.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this Slice 3). 3. `CARRY_FORWARD.md` → *"#196 cross-source activity dedup"*. 4. This handoff + Slice 2 + Slice 1 + the kickoff. 5. `routes/garmin.py:materialize_canonical_activity` + `_METRIC_WEIGHTS`/`_completeness_score`/`_row_provider`; `init_db.py` `canonical_activity` + `canonical_activity_field_provenance` blocks; the Slice-2 `cluster_activity` call sites. 6. `./scripts/verify-handoff.sh`.

## 7. Open questions (carry from the epic / kickoff §9)
- **Conflict surfacing (Slice 5, optional)** — show the athlete when sources materially disagree on a merged field, or merge silently? The provenance table already records *which* source won each field; a disagreement view would diff the losers against the winner.
- _(Resolved this session: completeness-scoring weights — richest-data-wins 3/2/1; canonical storage — separate `canonical_activity` record, wide.)_
- _(Resolved Slice 2: dedup tolerance windows — start ±5 min, duration ±10%, distance ±10%, loose sport.)_

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Canonical table | `init_db.py` | `CREATE TABLE IF NOT EXISTS canonical_activity (` with `cluster_id INTEGER NOT NULL UNIQUE` + `primary_cardio_log_id` + `completeness_score` (grep) |
| Provenance table | `init_db.py` | `CREATE TABLE IF NOT EXISTS canonical_activity_field_provenance (` with `UNIQUE (cluster_id, field_name)`; index `cafp_cluster_idx` (grep) |
| Materializer | `routes/garmin.py` | `def materialize_canonical_activity(db, uid: int, cluster_id: int)` — `ON CONFLICT (cluster_id)`; `DELETE FROM canonical_activity_field_provenance WHERE cluster_id` (grep) |
| Scoring weights | `routes/garmin.py` | `_METRIC_WEIGHTS` with tiers `{1,2,3}`; `_IDENTITY_FIELDS`; `_CANONICAL_FIELDS` (grep) |
| Meaningful-value rule | `routes/garmin.py` | `def _has_value` — `return v != 0` for numerics (grep) |
| Primary + tiebreak | `routes/garmin.py` | `def _primary_rank` — `(-_completeness_score(row), _SOURCE_ORDER…)`; `_SOURCE_ORDER` = `garmin…strava` (grep) |
| Re-materialize wiring | `routes/garmin.py` | `materialize_canonical_activity(db, uid, cluster_id)` before BOTH `return cluster_id` in `cluster_activity` (grep — 2 call sites) |
| Tests | `tests/test_garmin_bulk_source.py` | `TestCompletenessScore` + `TestRowProvider` + `TestMaterializeCanonical` + `_CanonConn` |
| Suite | — | `… pytest tests/ -q` → 3502 passed / 30 skipped |
| Issue | #196 | comment: Phase 3 Slice 3 (scoring + canonical materialization) shipped on `claude/dreamy-keller-cd9pw5` (PR #916); stays open through Slice 4 (consumer repoint) |
