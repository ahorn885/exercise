# V5 Implementation — Canonical Daily-Wellness Layer (#196 Phase 2) — Slice 2.1 — Closing Handoff (2026-06-23)

**Branch:** `claude/cross-source-activity-dedup-7q7a3u` · **Suite:** 3543 passed / 30 skipped · **PR:** not yet opened — awaiting Andy's go (PR-gated flow).
**Design:** `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md` (ratified). **Epic:** #196 unified health-data layer. Phase 3 (activity dedup) shipped (Slices 1–4b, PRs #906/#910/#916/#921/#924). This session Andy **redirected off the #884 gear/craft thread** to **#196 Phase 4** (recovery-aware planning); scoping showed the substrate (Phase 2) was owed first, so this is **Phase 2 Slice 2.1** — the canonical daily-wellness substrate + writer.

---

## 1. The problem (one line)

Wellness from N devices (Garmin daily + Polar/COROS/Whoop/Oura) is merged field-by-field **only in the Layer-3A reader** (`layer3a/integration.py:q_layer3A_recent_wellness`), not in a shared materialized layer. The epic's **Phase 2** wants a durable canonical `(user, date)` best-of record all consumers read (the daily-metrics analog of Phase 3's `canonical_activity`). Slice 2.1 builds the substrate + writer; Slices 2.2/2.3 wire ingest + repoint the reader.

## 2. Decisions ratified this session (Andy 2026-06-23, two AskUserQuestion rounds)

1. **Phase 4 starting point → materialize the Phase-2 wellness layer first** (substrate before the recovery-aware Phase-4 consumer). Most Phase-4 plan-gen plumbing already exists (multi-source coalesce in 3A + wellness already in the 3A prompt); the missing pieces are the materialized Phase-2 layer and the Layer-4 consumption.
2. **Materialize how → table + on-ingest hooks** (not a SQL view; not lazy read-through). The epic's "materialized table recomputed on ingest" default + the Phase-3 writer idiom.
3. **Metric scope → widen for Phase 4**, honoring cross-provider semantics.
4. **(For the later Phase-4 slice, pre-ratified, out of scope here) recovery-aware mechanism → LLM-soft guidance.**

**Key finding driving the column set (per-provider payload map, Explore 2026-06-23):** only **sleep duration / HRV / resting-HR** are the *same* metric across all 5 devices → coalesced with `*_source` provenance. "Readiness" and "training load" are **semantically divergent** (Garmin `training_readiness` 0-100 ≠ Whoop `recovery_score` ≠ Polar `ans_charge`; Garmin `acute_training_load` ≠ Whoop `day_strain` ≠ Polar `daily_load`) — merging them would average unlike units, so they are **NOT coalesced**; carried as Garmin-origin single-source context fields.

## 3. What Slice 2.1 shipped (3 substantive files: 2 code + 1 test; + the design doc)

- **`init_db.py`** (`_PG_MIGRATIONS` tail, after the Phase-3 `canonical_cardio_feed` view) — `canonical_daily_wellness` table (18 cols) + index. Additive / idempotent / public-schema → **auto-applies on each Vercel deploy, no Neon apply owed.**
  - **Coalesced (carry `*_source`):** `total_sleep_hours`, `hrv_rmssd_ms`, `resting_hr`.
  - **Garmin-origin context (no `*_source` — no merge choice to record):** `hrv_7d_avg_ms`, `resting_hr_7day_avg`, `sleep_score`, `training_readiness`, `vo2max_running`, `vo2max_cycling`, `acute_training_load`.
  - `UNIQUE(user_id, date)` (the upsert key) + `canonical_daily_wellness_user_date_idx`.
- **`canonical_wellness.py`** (NEW) — `materialize_canonical_wellness(db, uid, target_date)`:
  - Reads the Garmin `daily_wellness_metrics` row (carries both the 3 coalesced fields AND the 7 context fields → one read) + the non-Garmin device rows from `provider_raw_record` (polar sleep/hrv, coros daily_summary, whoop/oura daily_summary), scoped to `target_date`.
  - Coalesces the 3 multi-source fields **freshest-non-null, garmin>whoop>oura>polar>coros tiebreak** — a **copy** of `layer3a.integration._WELLNESS_SOURCE_PRIORITY` + `_coalesce_wellness_field` (Slice 2.3 folds the two copies into one). Copies the Garmin context fields as-is.
  - **No-data day → DELETE any existing row + return** (re-materialization is the only writer; a day that lost all data must not leave a stale row).
  - Else upsert `INSERT … ON CONFLICT (user_id, date) DO UPDATE`.
  - **Rule #15:** `[wellness-canon] user=… date=… merged={sleep<-whoop, hrv<-garmin, rhr<-oura} garmin_ctx={training_readiness, vo2max_running, …}`.
- **`tests/test_canonical_wellness.py`** (NEW, +7) — fake-conn suite (no Flask import, dodges the container's Neon-egress import hang): freshest-non-null per field; priority tiebreak on equal timestamps; resting-HR int rounding; Garmin context copied; context-alone still writes a row; `ON CONFLICT (user_id, date) DO UPDATE` shape; no-data clears + skips the insert.

**Placeholder note:** `canonical_wellness.py` uses `%s` throughout. `database.py`'s wrapper translates `?`→`%s` and passes `%s` through untouched, and route-context rows are dict-like — so the writer is safe to call from any context (Slice 2.2's ingest routes) without a placeholder/row-access mismatch.

## 4. Decisions baked in (review these)

1. **Wide + inline `*_source` only on the 3 coalesced fields.** Provenance is meaningful only where a merge chose between sources; for 3 fields a separate provenance table (Phase 3's pattern, justified there by 29 fields) is over-engineering. The Garmin-context fields are Garmin-origin by definition today; when a non-Garmin equivalent is genuinely normalized to the same metric, that slice promotes the field to coalesced + adds its `*_source` column.
2. **Readiness/load NOT coalesced.** They are different quantities per provider (see §2). Carried single-source (Garmin) — honest over a misleading cross-provider average.
3. **Widened set is recovery/fitness-relevant, NOT every `daily_wellness_metrics` column.** Excluded (no-padding): respiratory rate, spo2, sleep sub-scores/stage minutes (display-only #283), steps/calories/floors/intensity-minutes (activity not recovery), ANS charge, skin temp. Each is a cheap idempotent `ADD COLUMN` later.
4. **Coalesce rule duplicated, deliberately + flagged.** Slice 2.1 touches only new code (doesn't risk the 3A cache key); Slice 2.3 repoints the reader and folds the two copies into one home.
5. **No consumer/ingest change yet.** Slice 2.1 is pure substrate — nothing calls `materialize_canonical_wellness` until Slice 2.2 hooks the ingest paths.

## 5. Tests + verification

- `SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:1/db?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3543 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217). New-file run: `pytest tests/test_canonical_wellness.py -q` → **7 passed**.
- **DDL validated without live Postgres** (Neon egress blocked): `sqlglot.parse_one(ddl, read="postgres")` parses clean; **18 columns** confirmed.
- **No Neon apply owed** (public-schema `_PG_MIGRATIONS` auto-applies on deploy).
- **LIVE-VERIFY owed (deferred to after Slice 2.2/2.3 — nothing writes the table yet):** once ingest hooks land, confirm a multi-source day materializes one row with the right per-field source picks.

## 6. NEXT

- **Slice 2.2 — ingest hooks + backfill.** Call `materialize_canonical_wellness(db, uid, date)` from the ~6 wellness ingest paths: `routes/garmin.py` (the `daily_wellness_metrics` writer, ~L1869) + the `provider_raw_record` writers in `routes/polar_ingest.py`, `routes/coros_ingest.py`, `routes/whoop_ingest.py`, `routes/whoop.py`, `routes/oura.py`. Plus a one-time backfill of existing `(user, date)` wellness. Likely its own ≤5-file slice (may split by provider family). Watch: pass the **affected date(s)** each writer just wrote; the writer is per-date.
- **Slice 2.3 — consumer repoint.** Point `q_layer3A_recent_wellness` at `canonical_daily_wellness` (a `SELECT` replacing the inline 5-source coalesce), with a **deterministic-equality test** proving the assembled `Layer3AIntegrationBundle.recent_wellness` is byte-identical (the 3A bundle hash folds into the 3A cache key — must not drift). Fold the duplicated `_WELLNESS_SOURCE_PRIORITY`/coalesce into one home (canonical_wellness.py owns it; layer3a imports it). Optionally repoint the `/wellness` charts. **Leave `coaching.get_wellness_summary`** (v1-coaching-only, low value).
- **Then Phase 4 — recovery-aware planning (LLM-soft).** Thread `recent_wellness` + `connected_providers.has_recent_*` into the Layer-4 plan-gen prompts (PerPhase / Refresh T1-3 / RaceWeekBrief) so suppressed HRV / sleep debt / poor readiness condition the plan. Trigger #1 (prompt) + #3 (cross-layer) → its own design gate + AskUserQuestion before code.
- **Parallel paused thread:** #884 gear/craft is mid-arc at slice 3a (slices 3→6 remain) — resume when Andy redirects back.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this Slice 2.1). 3. `CARRY_FORWARD.md` → *"#196 … Phase 2 — canonical daily-wellness layer"*. 4. This handoff + the design doc + the Phase-3 Slice 4a/4b handoffs (the `canonical_activity`/feed pattern this mirrors). 5. `init_db.py` `canonical_daily_wellness` block; `canonical_wellness.py:materialize_canonical_wellness`; `layer3a/integration.py:q_layer3A_recent_wellness` (the reader Slice 2.3 repoints) + `_coalesce_wellness_field`. 6. `./scripts/verify-handoff.sh`.

## 7. Open questions
- **Slice 2.2 backfill mechanics** — backfill date-by-date via the per-date writer (simple, slow for history) vs a bulk variant. Decide at 2.2 build.
- **Phase 4 design gate** — which Layer-4 surfaces first (initial PerPhase gen vs the adaptive Refresh path — the natural home for recovery signals), and the exact guardrails for LLM-soft adaptation. Open for the Phase-4 design slice.

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Canonical wellness DDL | `init_db.py` | `CREATE TABLE IF NOT EXISTS canonical_daily_wellness` with `total_sleep_hours_source`, `training_readiness`, `UNIQUE (user_id, date)` (grep); `canonical_daily_wellness_user_date_idx` index |
| Writer | `canonical_wellness.py` | `def materialize_canonical_wellness(db, uid, target_date)`; `ON CONFLICT (user_id, date) DO UPDATE`; `[wellness-canon]` Rule-#15 log; garmin>whoop>oura>polar>coros in `_WELLNESS_SOURCE_PRIORITY` |
| Readiness/load NOT coalesced | `canonical_wellness.py` | `training_readiness`/`acute_training_load` in `_GARMIN_CTX_COLS` (carried, not in the coalesce candidate lists) |
| Tests | `tests/test_canonical_wellness.py` | `TestCoalesce` (freshest/tiebreak/round) + `TestContextFields` + `TestUpsertShape` (idempotent + no-data clear) — 7 tests |
| No consumer/ingest change | `layer3a/integration.py`, `routes/*` | `q_layer3A_recent_wellness` still does the inline coalesce (unchanged); no `materialize_canonical_wellness` call site yet (grep — 0 in routes) |
| Suite | — | `… pytest tests/ -q` → 3543 passed / 30 skipped; DDL parses clean under sqlglot postgres (18 cols) |
| Design | `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md` | status RATIFIED; D1–D4 recorded; widened-set §3 D4 |
| Issue | #196 | comment owed on PR-open: Phase 2 Slice 2.1 (canonical daily-wellness substrate + writer) shipped; epic stays open (Phases 4–5 + Slices 2.2/2.3 remain) |
