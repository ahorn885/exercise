# V5 Implementation — Cross-Source Activity Dedup + Merge (#196 Phase 3) — Slice 2 — Closing Handoff (2026-06-23)

**Branch:** `claude/stoic-albattani-n771ef` · **Suite:** 3491 passed / 30 skipped · **PR:** pending Andy's go (PR-gated operating flow).
**Predecessors:** the kickoff `handoffs/V5_CrossSourceActivityDedup_196_Phase3_Kickoff_2026_06_22_v1.md` (problem, design defaults, slice sequence, Trigger-#3 gate) and **Slice 1** `handoffs/V5_Implementation_CrossSourceActivityDedup_196_Phase3_Slice1_2026_06_22_Closing_Handoff_v1.md` (the schema substrate + `started_at` ingest). This handoff is **Slice 2** of that plan — the clusterer.

---

## 1. The problem (one line)

One real-world activity reaching us via N connected providers (a Wahoo ride auto-forwarded to Strava) lands as **N `cardio_log` rows** — repro: user 1 rows 73 (Wahoo) + 74 (Strava), same indoor ride, `distance=0.0`, start ~06:28:56Z. Slice 1 added the substrate (`started_at`, `activity_clusters`, `cardio_log.cluster_id`); **Slice 2 is the matching logic that actually groups the duplicates** — a layer *above* the per-source `*_uidx` idempotency, never replacing it.

## 2. The one decision ratified this session

Slice 2's open question from the kickoff (§9) / Slice 1 (§7) was the **dedup tolerance windows**. **Andy chose (2026-06-23):**
- **start ±5 min, duration ±10%, distance ±10%** — and explicitly **"a little more loose on the event type. some apps may not have categories which match perfectly"** → the coarse-sport match is a canonical-family resolve with a wildcard for the unclassifiable, not exact-string equality.

Everything else in Slice 2 follows the kickoff §5 + §6 design (coarse-class match, distance fallback for indoor, idempotent + re-entrant, instrument per Rule #15). No new Trigger fired — Slice 1 already ratified the storage shape (Trigger #3); Slice 2 only *writes* to those tables.

## 3. What Slice 2 shipped (2 substantive files)

The clusterer, wired into the single shared cardio writer so **every** path (all provider webhooks + the manual uploader) runs through it.

- **`routes/garmin.py`** (the substance):
  - **`cluster_activity(db, uid, cardio_id, data, started_at)`** — called from `_bulk_insert_cardio` right after the insert (and after the existing Rule #15 `[cardio-insert]` print, before `_record_provider_raw_cardio`). Computes the coarse family; if `started_at` is `None`, leaves the row **unclustered** (can't time-fingerprint → never false-merge; kickoff §6 NULL tolerance) and returns `None`. Else: takes `pg_advisory_xact_lock(196, user_id)` (serialize find-or-create), selects same-user `activity_clusters` where `started_at BETWEEN start-5min AND start+5min` (the Slice-1 `(user_id, started_at)` index), picks the first `_fingerprint_match`, and either **attaches** (`UPDATE cardio_log SET cluster_id`; `UPDATE activity_clusters SET updated_at = NOW()`) or **opens** a new cluster (`INSERT … RETURNING id`; then set `cluster_id`). Rule #15: `[cardio-cluster] … → MATCH/NEW cluster=… (N candidate(s))` carries the fingerprint inputs + the decision.
  - **`_coarse_sport(data)`** — canonical coarse family from `discipline_id` via the **reused** `provider_cardio_resolve.DISCIPLINE_TO_PLAN_SPORT` (provider-independent — Strava/Wahoo/RWGPS/Garmin all collapse the same ride to one family), else the freetext `activity` folded through `_SPORT_FAMILY_ALIASES` (Polar `_SPORT_MAP` / COROS `_SPORT_MODE` set no `discipline_id`: `cycle→cycling`, `run→running`, `trail_run→running`, `swim→swimming`, `hike→hiking`, `walk→walking`, plus `bike/biking/jog/trek`). Unmapped passes through; empty → `'other'`.
  - **`_sport_matches(a, b)`** — loose equality: same family, **or either side in `{'', 'other', 'unknown'}`** (an unclassified row must not block a start+metric-corroborated merge — Andy's "looser on event type").
  - **`_metric_within(a, b, tol)`** — tri-state: `True` (both present, non-zero, within ±tol → corroborates), `False` (both present, outside ±tol → disqualifies), `None` (missing on a side, or both ~zero, e.g. an indoor ride's 0 distance).
  - **`_fingerprint_match(data, started_at, family, cand)`** — start within window **AND** loose sport **AND** no metric `False` **AND** ≥1 metric `True`. The "≥1 corroborator" rule means a bare start coincidence (0 distance + unknown duration) never merges; the indoor repro clusters on **duration** (distance is `None`/skipped).
  - Constants `_CLUSTER_START_TOL` (5 min) / `_CLUSTER_DURATION_TOL` / `_CLUSTER_DISTANCE_TOL` (0.10) / `_CLUSTER_LOCK_NS` (196). Import added: `from provider_cardio_resolve import DISCIPLINE_TO_PLAN_SPORT`.
- **`tests/test_garmin_bulk_source.py`** — `TestCoarseSport` (×4: canonical-discipline wins; provider freetext folds; discipline > activity priority; unmapped/empty/fine-only→`other`) + `TestClusterActivity` (×8: open-new; indoor-dup-attaches [the repro]; cross-provider label mismatch still clusters; duration-disagreement opens new; known-sport mismatch opens new; start-outside-window opens new; NULL-start unclustered; `_bulk_insert_cardio` invokes the clusterer). Shared `_FakeCursor` gained a `fetchall()→[]` (the cluster candidate query now runs on every started-at-resolving insert); new `_ClusterConn` fake feeds queued candidate rows + `RETURNING` id.

## 4. Decisions baked in (review these)

1. **Loose sport via canonical family, not a synonym ontology.** Reuse `DISCIPLINE_TO_PLAN_SPORT` (already canonical, no padding) for the resolver-backed providers; a *small* alias fold only for the two resolver-less providers' actual vocab (Polar/COROS singulars). `'other'`/unknown is a wildcard. This is the minimal thing that satisfies "apps' categories don't match perfectly" without a hand-maintained sport taxonomy.
2. **No-fork via `pg_advisory_xact_lock`.** The handoff called late-arrival/concurrency "the riskiest part." A per-user **txn-scoped** advisory lock around find-or-create makes two near-simultaneous same-ride webhooks serialize, so they can't both miss and open duplicate clusters. Relies on **autocommit being off** (verified in `database.py` — explicit `commit()`/`rollback()`); the lock releases at the caller's commit. If a future write path ever runs autocommit-on, this guarantee weakens — flag it.
3. **≥1 numeric corroborator required.** Start + sport alone don't merge; duration *or* distance must agree within tolerance and neither may clearly disagree. Keeps two distinct same-time indoor sessions of different lengths apart while still clustering the repro (duration agrees, distance both 0).
4. **NULL `started_at` → unclustered**, not best-effort merged. Manual date-only uploads land at 00:00 UTC (not NULL — Slice 1), so they still fingerprint; only a genuinely missing start is skipped. (No backfill of pre-Slice-2 rows — they keep `cluster_id` NULL; Slice 4 consumers must tolerate NULL.)
5. **Cluster anchor left stable.** A new cluster stores its first member's `(sport_class, started_at, duration_min, distance_mi)`; attaching a member bumps only `updated_at` (the Slice-3 re-materialization signal), it does not re-anchor. Canonical/primary selection is Slice 3.

## 5. Tests

`SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:1/db?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3491 passed / 30 skipped** (the 30 skips pre-exist; the 3 Layer3B `evidence_basis` warnings are from #217, unrelated). Touched-file run (`test_garmin_bulk_source` + `test_strava_ingest`) = **50 passed** (+12 new). New-SQL placeholder/param parity verified by inspection: cluster `INSERT` **5/5/5**, advisory lock **2/2**, candidate `SELECT` **3/3**, the two `UPDATE`s **2/2** and **1/1** (the fake-db tests don't validate `%s`↔param count).

## 6. NEXT — Slice 3 (completeness scoring + canonical materialization; kickoff §5)

Score each row in a cluster, pick the primary (completeness, not a fixed device order; static order only as tiebreaker — kickoff §4), gap-fill from secondaries, write the merged/`canonical_activity` record + per-field provenance. **Re-materialize whenever a cluster gains/loses a member** — `activity_clusters.updated_at` already bumps on attach (Slice 2), so it's the trigger signal; a late Strava/RWGPS arrival attaching to an existing cluster must re-run materialization. The `canonical_activity` + provenance tables are the deferred shape-B tables — **create them with this first writer** (Slice 1 decision #3: don't build tables with no consumer). Open scoring-weight question carried in §7. **Stop-and-ask:** completeness-scoring weights are an Andy decision (kickoff §9); `canonical_activity` is a new table read by Slice-4 consumers → confirm the DDL with Andy (Trigger #3) as Slice 1 did.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this Slice 2). 3. `CARRY_FORWARD.md` → *"#196 cross-source activity dedup"*. 4. This handoff + Slice 1 + the kickoff. 5. `routes/garmin.py:cluster_activity` + `_coarse_sport`/`_fingerprint_match`; `provider_cardio_resolve.DISCIPLINE_TO_PLAN_SPORT`; `init_db.py` `activity_clusters` block. 6. `./scripts/verify-handoff.sh`.

## 7. Open questions (carry from the epic / kickoff §9 — decide with Andy at Slice 3/5)
- **Completeness-scoring weights (Slice 3)** — what makes one source "more robust" for a given activity (power? HR? GPS? sample density? elevation?).
- **Conflict surfacing (Slice 5, optional)** — show the athlete when sources materially disagree, or merge silently?
- _(Resolved this session: dedup tolerance windows — start ±5 min, duration ±10%, distance ±10%, loose sport.)_

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Clusterer | `routes/garmin.py` | `def cluster_activity(db, uid` — `pg_advisory_xact_lock`; `BETWEEN ? AND ?` candidate SELECT; attach `UPDATE cardio_log SET cluster_id` / open `INSERT INTO activity_clusters … RETURNING id` (grep) |
| Coarse sport family | `routes/garmin.py` | `def _coarse_sport` — `DISCIPLINE_TO_PLAN_SPORT.get(...)` then `_SPORT_FAMILY_ALIASES`; `_sport_matches` wildcard `{'', 'other', 'unknown'}` (grep) |
| Tolerances | `routes/garmin.py` | `_CLUSTER_START_TOL = timedelta(minutes=5)`; `_CLUSTER_DURATION_TOL = 0.10`; `_CLUSTER_DISTANCE_TOL = 0.10` (grep) |
| Corroborator rule | `routes/garmin.py` | `def _fingerprint_match` — `if dur is False or dist is False: return False` then `return dur is True or dist is True` (grep) |
| Wiring (one call site) | `routes/garmin.py` | `cluster_activity(db, uid, rec_id, data, started_at)` inside `_bulk_insert_cardio`, before `_record_provider_raw_cardio` (grep) |
| Import reuse | `routes/garmin.py` | `from provider_cardio_resolve import DISCIPLINE_TO_PLAN_SPORT` (grep) |
| Tests | `tests/test_garmin_bulk_source.py` | `class TestCoarseSport` + `class TestClusterActivity` + `_ClusterConn`; `_FakeCursor` has `fetchall` |
| Suite | — | `… pytest tests/ -q` → 3491 passed / 30 skipped |
| Issue | #196 | comment: Phase 3 Slice 2 (the clusterer) shipped on `claude/stoic-albattani-n771ef`; stays open through Slice 4 (consumer repoint) |
