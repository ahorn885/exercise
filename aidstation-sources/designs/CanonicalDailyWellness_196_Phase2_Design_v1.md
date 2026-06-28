# Design — Canonical Daily-Wellness Layer (#196 Phase 2) — v1 (2026-06-23)

**Status:** Decisions RATIFIED (Andy 2026-06-23, two AskUserQuestion rounds) — implementing Slice 2.1 next. Trigger #3 (schema / cross-layer surface) cleared. The widened metric set (D4) is being finalized against a per-provider payload-availability map before the Slice-2.1 DDL is written.
**Epic:** #196 "Unified athlete health-data layer." This is **Phase 2** (canonical daily-wellness layer), chosen by Andy 2026-06-23 (AskUserQuestion) as the next #196 work after Phase 3 (activity dedup) shipped. The recovery-aware *planning* consumer (the epic's Phase 4) is a **later** slice; Andy pre-ratified its mechanism as **LLM-soft guidance**, but it is out of scope here.

---

## 1. Problem / current state

The epic's Phase 2 calls for a **canonical, deduplicated daily-wellness layer all consumers read**, with per-field provenance — the daily-metrics analog of what Phase 3 built for activities (`canonical_activity` + the `canonical_cardio_feed` view).

It was **never built as a materialized layer.** Instead the field-by-field merge lives in the **reader**: `layer3a/integration.py:q_layer3A_recent_wellness` (lines 201-391) gathers candidates for 3 metrics — `total_sleep_hours`, `hrv_rmssd_ms`, `resting_hr` — across 5 sources and coalesces each field with `_coalesce_wellness_field` (lines 182-198):

- **Sources:** Garmin `daily_wellness_metrics` (sleep span, `hrv_overnight_avg_ms`, `resting_hr`); Polar/COROS/Whoop/Oura via `provider_raw_record` (data_type `sleep`/`hrv`/`daily_summary`).
- **Rule:** *freshest-non-null* — among sources carrying a non-null value for a `(date, field)`, the newest ingest timestamp (`daily_wellness_metrics.updated_at` / `provider_raw_record.fetched_at`) wins; ties break on `_WELLNESS_SOURCE_PRIORITY` (garmin 5 > whoop 4 > oura 3 > polar 2 > coros 1).
- **Output:** one `DailyWellnessRecord` per day with per-field `*_source` provenance (`layer4/context.py:970-992`).

**Consequences of coalesce-at-reader:**
1. The merge recomputes on every 3A bundle assembly (fine today — small windows — but not "a layer all consumers read").
2. The only consumer that gets the merged view is Layer 3A. `coaching.get_wellness_summary` (coaching.py:1190) still reads raw Garmin `wellness_log` per-second aggregates and is multi-source-blind. The `/wellness` charts re-implement their own coalesce (`routes/wellness.py`, `test_wellness_multisource.py`).
3. No durable provenance record — "which source won sleep on 2026-06-20" exists only transiently in the reader.

## 2. Goal (this design)

Materialize a **canonical daily-wellness layer**: one durable per-`(user, date)` best-of record + per-field provenance, recomputed on ingest, that becomes the single read surface for wellness — replacing the inline coalesce in the 3A reader and (optionally) feeding `get_wellness_summary` + the charts. Behavior must be **identical** to today's coalesce so the 3A bundle hash (which folds into the 3A cache key) does not drift.

## 3. Design decisions (the forks needing ratification)

### D1 — Table shape: **wide + inline `*_source` columns** (recommended) vs separate provenance table vs long `(user,date,metric,source)`
- **Recommended — wide, mirroring `DailyWellnessRecord`:** columns `total_sleep_hours`, `total_sleep_hours_source`, `hrv_rmssd_ms`, `hrv_rmssd_ms_source`, `resting_hr`, `resting_hr_source`, keyed `UNIQUE(user_id, date)`. The inline `*_source` columns **are** the per-field provenance — for 3 fields a separate provenance table (Phase 3's pattern, justified there by 29 merged fields) is over-engineering. Consumers `SELECT` columns directly and map straight to the Pydantic record.
- **Alternative A — separate `canonical_daily_wellness_field_provenance` table** (Phase-3 parity): warranted only if we expect many metrics + want a uniform provenance surface across domains. Rejected for now (3 fields; YAGNI).
- **Alternative B — long `(user, date, metric, metric_source, value)`** (the epic's literal wording): maximally extensible (new metric = new row, no migration) but every consumer must pivot. Rejected — the metric set is small + stable; a new metric is a cheap idempotent `ALTER TABLE ADD COLUMN` (exactly how `daily_wellness_metrics` already grows, init_db.py:1026-1060).
- **Gut check:** if we later materialize the *full* ~30-column daily_wellness_metrics surface (readiness, VO₂max, training load, sleep sub-scores) into the canonical layer, wide gets unwieldy and Alt-A/B get more attractive. Recommendation: start wide/3-field (matches what's actually consumed), revisit if the surfaced metric set grows materially.

### D2 — Recompute trigger: **on-ingest via a shared helper** (recommended) vs SQL view vs lazy read-through
This is the **main cost**, because wellness ingest has ~6 write sites (no single chokepoint, unlike Phase 3's `cluster_activity`):
`routes/garmin.py:1869` (daily_wellness_metrics), `routes/polar_ingest.py:359`, `routes/coros_ingest.py:185`, `routes/whoop_ingest.py:195`/`routes/whoop.py:294`, `routes/oura.py:389` (provider_raw_record).
- **Recommended — `materialize_canonical_wellness(db, uid, target_date)`**, reusing the existing `_coalesce_wellness_field` rule, called from each ingest path with the affected date(s); upsert `ON CONFLICT (user_id, date)`. Matches the epic's "materialized table recomputed on ingest" default and Phase 3's writer idiom. Cost: ~6 call-site hooks + a one-time backfill.
- **Alternative A — a SQL view** (like `canonical_cardio_feed`): zero ingest hooks, always fresh. But *freshest-non-null per field across 5 heterogeneous sources* (one wide table + JSONB `provider_raw_record` rows) is gnarly in pure SQL — a per-metric lateral/`DISTINCT ON` over a UNION of 6 candidate subqueries — and the epic explicitly preferred a table ("simpler for coaching/queries than a live view"). Higher query cost on every read.
- **Alternative B — lazy read-through** (materialize a date the first time it's read, cache): fewer hooks, but it's really coalesce-at-reader with write-back — doesn't give "fresh on ingest," and complicates the cache-key invariant.
- **Gut check:** the 6 hooks are the real smell. If that surface feels too broad, Alt-A (view) trades it for SQL complexity. I lean table+hooks because it matches the ratified "materialize" intent and the proven Phase-3 pattern, and because the per-field-freshest SQL is genuinely unpleasant to get right + test.

### D4 — Widened metric set (RATIFIED: widen for Phase 4) — but honor cross-provider semantics
A per-provider payload-availability map (Explore 2026-06-23) shows the metrics fall into three honesty tiers:
- **Tier 1 — genuinely the SAME metric across providers → coalesce (best-of):** sleep duration, resting HR, HRV (all 5 sources); respiratory rate (whoop/oura/polar only).
- **Tier 2 — semantically DIVERGENT across providers → do NOT coalesce:** "readiness/recovery" (Garmin `training_readiness` 0-100 ≠ Whoop `recovery_score` ≠ Polar `ans_charge`) and "training load" (Garmin `acute_training_load` ≠ Whoop `day_strain` ≠ Polar `daily_load`). Merging these under one column would average unlike quantities. Treat each as a **single-source Garmin field** today (the non-Garmin equivalents are corroboration-only / un-normalized).
- **Tier 3 — single-source / specialty:** VO₂max, sleep quality score (Garmin only); steps/calories (COROS only); ANS charge (Polar only); skin temp (Whoop only).

**Ratified canonical column set** (recovery-aware-planning-relevant; deliberately NOT every column `daily_wellness_metrics` stores):
- **Coalesced, carry `*_source` provenance** (Tier 1): `total_sleep_hours`, `hrv_rmssd_ms`, `resting_hr`.
- **Single-source context (Garmin-origin today, stored plain — NO per-field source column, since there is no choice to record):** `hrv_7d_avg_ms` + `resting_hr_7day_avg` (the baselines recovery logic compares against — high value), `sleep_score` (sleep quality), `training_readiness` (Garmin's composite recovery signal), `vo2max_running` + `vo2max_cycling` (fitness trajectory), `acute_training_load` (device load).
- **Deliberately EXCLUDED (no-padding):** respiratory rate (niche; multi-source but marginal for planning), spo2, sleep sub-scores / stage minutes (display-only, #283), steps/calories/floors/intensity-minutes (activity, not recovery), ANS charge, skin temp. Adding any later is a cheap idempotent `ADD COLUMN`.

**Provenance honesty note:** `*_source` columns exist only on the 3 coalesced fields — provenance is meaningful only where a merge chose between sources. The single-source fields are Garmin-origin by definition today; when a non-Garmin equivalent is genuinely normalized to the same metric, that slice promotes the field to coalesced + adds its `*_source` column.

### D3 — Consumer repoints (which readers move to the canonical layer)
- **Required:** `q_layer3A_recent_wellness` → read the canonical table instead of coalescing inline. **Must be byte-identical** to preserve the 3A bundle hash / cache key (a deterministic-equality test gates this).
- **Optional / lower value:** `coaching.get_wellness_summary` (legacy v1 coaching — being replaced; modernizing it is low long-term value) and the `/wellness` charts (already have a working coalesce). Recommend: repoint the charts for consistency *if cheap*; leave `get_wellness_summary` for a separate call (or skip).

## 4. Proposed slice plan (5-file ceiling forces a split — mirrors Phase 3's substrate→writer→repoint)

| Slice | Scope | Substantive files |
|---|---|---|
| **2.1 — substrate + writer** | `init_db.py` DDL (`canonical_daily_wellness`) + `materialize_canonical_wellness` writer reusing the coalesce (extract the per-source candidate-gather + `_coalesce_wellness_field` into a shared helper) + Rule #15 log + unit tests. **No consumer or ingest change** — pure additive substrate, auto-applies on deploy (public-schema, no Neon apply owed). | ~3 (init_db.py, the writer module, tests) |
| **2.2 — ingest hooks + backfill** | Call the writer from the ~6 wellness ingest paths with the affected date(s) + a one-time backfill of existing `(user,date)` wellness. | ~5-6 route files + a backfill — **likely its own ≤5-file slice; may split by provider family** |
| **2.3 — consumer repoint** | Point `q_layer3A_recent_wellness` (and optionally the charts) at the canonical table; deterministic-equality test proving the 3A bundle is unchanged. | ~2-3 |

#196 stays OPEN through the Phase-2 slices; Phase 4 (recovery-aware planning, LLM-soft) follows.

## 5. Edge cases / invariants
- **Determinism:** the writer must produce the same pick as `_coalesce_wellness_field` (freshest-non-null, priority tiebreak) so the repoint in 2.3 is behavior-preserving and the 3A cache key is stable.
- **No-source day:** a date with no non-null candidate for any field → no canonical row (don't write all-NULL rows); the reader already tolerates missing days.
- **Idempotent re-materialize:** upsert `ON CONFLICT (user_id, date)`; a later/fresher provider write for the same date re-runs and overwrites (matches the "freshest wins" rule).
- **Manual override:** the epic says manual entry always wins; no manual daily-wellness edit path exists today → reserve the semantics (a future `source='manual'` with top priority), build nothing now (parity with Phase 3's reserved `manual_override` slot).
- **Provenance honesty (Rule #15):** the writer logs `[wellness-canon] user=… date=… fields={sleep<-whoop, hrv<-garmin, rhr<-oura}` so a surprising pick is diagnosable from `/admin/logs`.

## 6. Test scenarios
- Writer picks freshest-non-null per field; priority tiebreak on equal/missing timestamps; all-NULL day → no row; idempotent re-run; upsert overwrites on fresher ingest.
- 2.3: `q_layer3A_recent_wellness` reading the canonical table returns a `list[DailyWellnessRecord]` **equal** to the pre-repoint inline-coalesce output across a multi-source fixture (the cache-key-stability gate).

## 7. Gut check / risks
- **Biggest risk:** the 2.2 ingest-hook surface (6 sites) is broader than Phase 3's single chokepoint — easy to miss a path, leaving a stale canonical row. Mitigation: the 2.3 reader still *falls back* to nothing-stale because the writer is deterministic, plus the backfill + a "writer called from every wellness ingest path" source-level test.
- **Value question:** Phase 2 is mostly an *internal consistency / substrate* play — it doesn't change athlete-visible behavior by itself (the 3A merge is already correct). Its payoff is (a) a durable provenance record, (b) one read surface so `get_wellness_summary`/charts can stop re-implementing the merge, and (c) a clean foundation for Phase 4's recovery-aware planning. If the goal is athlete-visible value *fastest*, Phase 4 (recovery-aware planning) would deliver more — but Andy chose to lay the canonical substrate first, which is the more architecturally disciplined order and de-risks Phase 4.
- **Smallest-viable alternative:** if the 6-hook materialization feels heavy for an internal-only win, the SQL **view** (D2-Alt-A) gives "one read surface all consumers share" with zero ingest hooks — at the cost of per-read SQL complexity. Worth a deliberate yes/no before committing to the table+hooks path.

## 8. Decisions — RATIFIED (Andy 2026-06-23, two AskUserQuestion rounds)
1. **D1 — wide + inline `*_source` columns** (no separate provenance table for 3 fields). *(default accepted)*
2. **D2 — materialized table + on-ingest hooks** (not the SQL view; not lazy read-through).
3. **D3 — repoint only the 3A reader** (required); leave the legacy `get_wellness_summary` (low value, v1-coaching-only); charts optional/later.
4. **D4 — widen for Phase 4**, honoring cross-provider semantics (§3 D4): 3 coalesced Tier-1 fields + the Garmin-origin recovery/fitness context fields; Tier-2 divergent metrics stay single-source; padding fields excluded.

Mechanism for the *later* Phase-4 recovery-aware planning slice (out of scope here): **LLM-soft guidance** (pre-ratified).
