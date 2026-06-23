# V5 Implementation — Cross-Source Activity Dedup + Merge (#196 Phase 3) — Slice 4a — Closing Handoff (2026-06-23)

**Branch:** `claude/charming-babbage-lq41yj` · **Commit:** `0f8f1ec` · **Suite:** 3532 passed / 30 skipped · **PR:** not yet opened — awaiting Andy's go (per the PR-gated operating flow).
**Predecessors:** the kickoff `handoffs/V5_CrossSourceActivityDedup_196_Phase3_Kickoff_2026_06_22_v1.md` (problem, slice sequence, Trigger-#3 gate), **Slice 1** `…Slice1_2026_06_22…` (schema substrate + `started_at`), **Slice 2** `…Slice2_2026_06_23…` (the clusterer), **Slice 3** `…Slice3_2026_06_23…` (completeness scoring + `canonical_activity` materialization). This is **Slice 4a** — the *math* consumer repoint (training-load + plan-compliance + coaching context).

---

## 1. The problem (one line)

One real-world activity reaching us via N connected providers (a Wahoo ride auto-forwarded to Strava) lands as **N `cardio_log` rows** (repro: user 1 rows 73 Wahoo + 74 Strava). Slices 1–3 group the duplicates into a cluster and merge each cluster into ONE best-of `canonical_activity` row. **Slice 4 repoints the consumers so they read the merged record and count the ride once.** Slice 4a does the **math** half (the surfaces that double-count training load / compliance); **Slice 4b** (next) does the **display** half.

## 2. The decisions ratified this session (Andy 2026-06-23, two AskUserQuestion rounds, in plain language)

Slice 4 repoints readers across layers → an inter-layer surface change (Trigger #3) AND the kickoff §6 consumer list is ~8 substantive files (over the 5-file ceiling) → both demand a stop-and-ask. Ratified:

1. **One shared dedup read surface, not per-consumer surgical edits.** Build the "show each workout once" logic once, in a single place every math consumer reads from — chosen over editing each consumer's SQL to merge copies itself. → a SQL **view** (§3).
2. **The literal cardio-LOG list/edit pages keep showing every imported copy.** The raw activity-log + edit pages still surface both the Wahoo and Strava rows (so a stray duplicate stays visible and deletable); only the summary / coaching / training-load / compliance surfaces collapse to one best-of row. (Provider-coverage + HRmax-by-provider stay raw regardless — they *need* per-source rows.)
3. **Split 4a math-first, 4b display-next.** 4a = the slice that makes training-load + compliance count the ride once (the real point of #196); 4b = the cosmetic display surfaces.

## 3. What Slice 4a shipped (6 substantive files: 4 code + 2 test)

- **`init_db.py`** (`_PG_MIGRATIONS` tail, after the Slice-3 `canonical_activity` blocks) — the shared read surface. Additive, idempotent (`CREATE OR REPLACE VIEW`), public-schema (**auto-applies on Vercel deploy → no Neon apply owed**):
  - **`canonical_cardio_feed`** — returns each real activity EXACTLY once via two `UNION ALL` branches over a clean partition:
    - **clustered branch** — `FROM canonical_activity ca JOIN cardio_log cl ON cl.id = ca.primary_cardio_log_id`: one row per cluster = `canonical_activity`'s 29 merged best-of columns, carrying the cluster's PRIMARY `cardio_log` copy's `id`/`notes`/`created_at` + the 6 provider-id columns (so `_detect_workout_source` resolves to the richest copy's device), and `plan_item_id` from a correlated subquery picking **any member that is plan-matched** (robust to which copy the matcher linked, not just the primary).
    - **unclustered branch** — `FROM cardio_log cl WHERE cl.cluster_id IS NULL`: raw rows that were never grouped (pre-Slice-2 rows + NULL-`started_at` rows). Carries `plan_item_id`/`notes` directly.
  - **41 columns**, identical order in both branches (UNION ALL is positional). Partition is clean: a `cardio_log` row is either in a cluster (and represented by its one `canonical_activity` row) or has `cluster_id IS NULL` — no overlap, no double-count. Invariant relied on: `materialize_canonical_activity` always sets `primary_cardio_log_id` to a live member id, so the clustered branch's INNER JOIN never drops a cluster.
- **`layer3a/integration.py`** (the training-load fix — the headline of #196) — repointed `FROM cardio_log` → `FROM canonical_cardio_feed` in:
  - **`q_layer3A_recent_workouts`** — feeds `bundle.recent_workouts` → `recent_workouts_count` + the trajectory floors (`<5 → low`, `<10`) that gate athlete state. Duplicates inflated the count. Docstring updated (source-tag now names the merged record's primary device).
  - **`q_layer3A_combined_load`** — sums each row's hours into acute/chronic ACWR load; duplicates inflated load N-fold. Added a Rule-#15-style comment at the repoint.
  - **Left raw, DELIBERATELY (commented):** `q_layer3A_connected_providers`' workout-coverage `COUNT(*) FILTER (WHERE garmin_activity_id IS NOT NULL) …` — counts per-provider coverage, so it needs the un-merged rows; the feed carries only the primary copy's ids and would under-count secondaries.
- **`routes/plans.py`** — `_plan_health` compliance JOIN `JOIN cardio_log cl ON cl.plan_item_id = pi.id` → `JOIN canonical_cardio_feed cl …`. When both copies match the same plan item, every copy carries that `plan_item_id`; the raw JOIN surfaced the completed item N× (LIMIT 10 → fewer real items shown + N× compliance). The feed collapses each cluster to one row → one actual-vs-target comparison per item.
- **`coaching.py`** — `get_coaching_context` recent-cardio (90-day, LIMIT 75) `FROM cardio_log` → `FROM canonical_cardio_feed`. Context now shows a synced ride once (best-of metrics + the primary copy's `notes`), not N near-duplicates. **`_get_performance_delta` left untouched** — it's already Postgres-broken (`GROUP_CONCAT` + non-aggregated `GROUP BY`), filed as **#920**; its compliance repoint waits on that fix.
- **`tests/test_canonical_cardio_feed.py`** (NEW) — view present + both branches; `UNION ALL` branch column-count parity (41==41, paren-aware top-level-comma split so the `plan_item_id` subquery's internal text doesn't miscount); the any-member `plan_item_id` rule; and source-level assertions that each math consumer now reads the feed (and that `_get_performance_delta` stays on raw `cardio_log`, by design). Reads files as text → no Flask-app import (dodges the container's Neon-egress import hang).
- **`tests/test_layer3a_integration.py`** — +3: `recent_workouts` + `combined_load` issue SQL `FROM canonical_cardio_feed`; coverage count stays `FROM cardio_log`.

## 4. Decisions baked in (review these)

1. **Shared view, not per-consumer SQL.** The view duplicates `cardio_log`'s column shape so a math consumer swaps `FROM cardio_log` → `FROM canonical_cardio_feed` with no other change. One place encodes the collapse + the NULL-`cluster_id` tolerance.
2. **The view can't be a drop-in for EVERY reader — two gaps, handled:** (a) `canonical_activity` doesn't store `notes`/`plan_item_id`/provider-ids, so the clustered branch sources those from the **primary** `cardio_log` row (notes) and a **plan-matched member** (plan_item_id); a note that lives only on a *secondary* copy is dropped on a merged row — acceptable (the primary is the richest copy). (b) The per-provider coverage count + the literal log/CRUD pages genuinely need un-merged rows → they stay on `cardio_log` (decision 2 + commented).
3. **`plan_item_id` from any matched member, not just the primary.** A correlated subquery picks the lowest-`id` member with a non-null `plan_item_id`. This is the only place the clustered branch reaches past the primary — chosen so compliance still resolves if the matcher linked a secondary copy. The clean fix for the double-count is the one-row-per-cluster shape; the subquery just makes sure that row carries the link.
4. **Singletons + unclustered both covered.** Every clustered activity (incl. a 1-member singleton cluster, per Slice 3) has a `canonical_activity` row → clustered branch. NULL-`started_at`/pre-Slice-2 rows have NULL `cluster_id` → unclustered branch. Union = every activity once.
5. **`_get_performance_delta` (#920) left as-is.** Pre-existing SQLite-ism, Postgres-broken independent of #196. Repointing a broken query is pointless; flagged, not fixed (surgical-changes rule). Its compliance JOIN should move to the feed when #920 is fixed.

## 5. Tests + verification

- `SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:1/db?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3532 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217, unrelated). Touched-file run (front-load a `test_layer4_*` to dodge the isolated-collection circular-import quirk): `pytest tests/test_layer4_plan_create.py tests/test_layer3a_integration.py tests/test_canonical_cardio_feed.py -q` → **170 passed** (+9 new).
- **View DDL validated without live Postgres** (container can't reach Neon): `sqlglot.parse_one(ddl, read="postgres")` parses clean (no syntax error); AST confirms a `Union` of two branches with **41 == 41** output columns, `UNION ALL`. This is the Slice-3-precedent "verified by inspection," upgraded to a real-parser check.
- **LIVE-VERIFY owed (Andy-action — container can't run plan-gen / reach Neon):** with a cross-source duplicate present (the rows-73-Wahoo/74-Strava repro), confirm **ACWR combined load**, **`recent_workouts_count`**, and **plan-compliance** each count the ride ONCE (not twice), and that an unclustered/legacy (`cluster_id IS NULL`) row still surfaces in all three. The unit tests prove the consumers *read the feed*; only prod proves the view *collapses* correctly.

## 6. NEXT — Slice 4b (display surfaces; kickoff §6 remainder)

Repoint the **display** readers at `canonical_cardio_feed` so the UI shows a cross-source ride once:
- `routes/connections.py` — `_ACTIVITY_SQL` (the Data-hub Files list, lines ~44-48) + the `SELECT COUNT(*) FROM cardio_log` (line ~108). Swap both `FROM cardio_log` → `FROM canonical_cardio_feed`.
- `routes/dashboard.py` — the "recent cardio" `SELECT … LIMIT 5` (line ~326) + the `SELECT COUNT(*)` stat (line ~236) + the unconditioned-cardio LEFT JOIN (line ~349, `cl` aliased) → feed.
- **STAYS RAW (decision 2 — do NOT repoint):** `routes/cardio.py` list/edit/distinct, `routes/training.py` list, `routes/conditions.py` prefill (the literal log/CRUD pages); `routes/profile_extractors.py` HRmax-by-provider + `layer3a` provider-coverage (per-source); `routes/admin.py` counts (low-stakes, optional).
- These display reads **already tolerate NULL `cluster_id`** for free via the view's unclustered branch.
- 4b is small (~2 files) → its own ≤5-file slice. #196 stays OPEN until it lands. (Slice 5, optional = conflict-surfacing UI.)

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this Slice 4a). 3. `CARRY_FORWARD.md` → *"#196 cross-source activity dedup"*. 4. This handoff + Slice 3 + Slice 2 + Slice 1 + the kickoff. 5. `init_db.py` `canonical_cardio_feed` view; `layer3a/integration.py` `q_layer3A_recent_workouts`/`q_layer3A_combined_load` (repointed) + `q_layer3A_connected_providers` (deliberately raw); `routes/plans.py:_plan_health`; `coaching.py:get_coaching_context`. 6. `./scripts/verify-handoff.sh`.

## 7. Open questions (carry from the epic / kickoff §9)
- **Conflict surfacing (Slice 5, optional)** — show the athlete when sources materially disagree on a merged field, or merge silently? The provenance table already records *which* source won each field.
- **#920** — `coaching._get_performance_delta` Postgres incompatibility (`GROUP_CONCAT` + non-aggregated `GROUP BY`); fix, then repoint its compliance JOIN at the feed.
- _(Resolved this session: shared view vs per-consumer edits → shared `canonical_cardio_feed` view; log list/edit pages stay raw; 4a-math / 4b-display split.)_
- _(Resolved Slice 3: completeness-scoring weights — richest-data-wins 3/2/1; canonical storage — separate wide `canonical_activity` record.)_
- _(Resolved Slice 2: dedup tolerance windows — start ±5 min, duration ±10%, distance ±10%, loose sport.)_

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Dedup view | `init_db.py` | `CREATE OR REPLACE VIEW canonical_cardio_feed AS` with `FROM canonical_activity ca`, `UNION ALL`, `WHERE cl.cluster_id IS NULL` (grep) |
| View parity | `init_db.py` | both UNION branches list 41 columns, identical order; clustered branch carries `(SELECT m.plan_item_id … m.cluster_id = ca.cluster_id … LIMIT 1)` (grep + `tests/test_canonical_cardio_feed.py`) |
| Load repoint | `layer3a/integration.py` | `q_layer3A_recent_workouts` + `q_layer3A_combined_load` read `FROM canonical_cardio_feed` (grep — 2 hits) |
| Coverage stays raw | `layer3a/integration.py` | `q_layer3A_connected_providers` workout-coverage still `FROM cardio_log` with `FILTER (WHERE garmin_activity_id IS NOT NULL) AS garmin_n` (grep) |
| Compliance repoint | `routes/plans.py` | `_plan_health` → `JOIN canonical_cardio_feed cl ON cl.plan_item_id = pi.id` (grep; old `JOIN cardio_log cl ON cl.plan_item_id` gone) |
| Coaching context | `coaching.py` | `get_coaching_context` recent-cardio `FROM canonical_cardio_feed`; `_get_performance_delta` still `LEFT JOIN cardio_log cl ON cl.plan_item_id = pi.id` (grep) |
| Tests | `tests/test_canonical_cardio_feed.py` | `TestCanonicalCardioFeedView` (parity 41) + `TestMathConsumersReadFeed`; `tests/test_layer3a_integration.py` `test_reads_canonical_dedup_feed` ×2 + `test_coverage_count_stays_on_raw_cardio_log` |
| Suite | — | `… pytest tests/ -q` → 3532 passed / 30 skipped; view DDL parses clean under sqlglot postgres dialect (41==41) |
| Issue | #196 | comment: Phase 3 Slice 4a (math repoint via `canonical_cardio_feed`) shipped on `claude/charming-babbage-lq41yj` (`0f8f1ec`); stays open through Slice 4b (display repoint) |
| New bug | #920 | filed: `coaching._get_performance_delta` SQLite `GROUP_CONCAT` + non-aggregated GROUP BY → Postgres-broken; left untouched |
