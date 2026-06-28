# V5 Implementation — Canonical Daily-Wellness Layer (#196 Phase 2) — Slice 2.2 — Closing Handoff (2026-06-28)

**Branch:** `claude/festive-allen-lupbey` · **Suite:** 3556 passed / 30 skipped · **PR:** not yet opened — awaiting Andy's go (PR-gated flow).
**Design:** `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md` (ratified). **Epic:** #196 unified health-data layer. Predecessor: Slice 2.1 (substrate + writer, commit `be3e606`, PR #928). This session = **Phase 2 Slice 2.2** — wire the writer into every wellness ingest path + a one-time backfill.

> **▶ IMMEDIATE NEXT STEPS: (1) run the backfill — trigger the `backfill-canonical-wellness` Action (Andy one-taps the `production` gate) once this merges; (2) LIVE-VERIFY a multi-source day; (3) Slice 2.3 — repoint the 3A reader (full detail in §6).** Slice 2.2 makes every NEW wellness ingest materialize the canonical row, and the backfill catches history. Nothing READS the table until Slice 2.3.

---

## 1. The problem (one line)

Slice 2.1 built `canonical_daily_wellness` + `materialize_canonical_wellness(db, uid, target_date)` but **nothing called it** — the table stayed empty. Slice 2.2 hooks the writer into the ~6 wellness ingest paths so the canonical `(user, date)` row (re)builds on each write, and backfills the existing history.

## 2. Decisions ratified this session (Andy 2026-06-28, two AskUserQuestion rounds)

1. **Scope → one slice** (all 6 providers + the gating helper + tests in one PR). The per-route hooks are trivial 1-line gated calls, and **nothing reads `canonical_daily_wellness` until Slice 2.3** (confirmed: only the writer, the DDL, and the test reference it) — so a "half-wired" intermediate state has zero functional impact, removing the main argument for splitting by provider family.
2. **Backfill → include now** (a backfill helper + a gated GitHub Action, run against prod). Not deferred to 2.3.

## 3. What Slice 2.2 shipped (7 substantive: 1 writer-module + 6 routes; + 1 workflow + 3 test-double fixes + 1 new-test block)

- **`canonical_wellness.py`** — three additive entry points after the Slice-2.1 writer:
  - **`materialize_wellness_for_provider(db, uid, provider, data_type, target_date)`** — the ingest-hook gate. Re-materializes **only** when the just-written `provider_raw_record` row is one the canonical layer reads: `_WELLNESS_FEED_DATA_TYPES = {polar:{sleep,hrv}, coros:{daily_summary}, whoop:{daily_summary}, oura:{daily_summary}}`. A non-wellness write (polar `cardio_load`, whoop `workout`) is a no-op (no canonical read/write). Garmin is **not** in the map — its `daily_wellness_metrics` write always feeds canonical, so the Garmin hooks call `materialize_canonical_wellness` directly.
  - **`backfill_canonical_wellness(db, uid=None)`** + **`_wellness_backfill_targets(db, uid=None)`** — the work-list UNIONs the Garmin `daily_wellness_metrics` days with the non-Garmin `provider_raw_record` wellness days (`date::text` so the union types line up), then materializes each. Idempotent; caller owns the commit; returns the count.
  - **`_main()` / `__main__`** — `python canonical_wellness.py --backfill [--user N]`. Connects via `database._PgConn(_connect())` off `DATABASE_URL`. **`database` is imported lazily inside `_main`** so importing the library stays Flask-free (the unit tests import this module and must dodge the container's Neon-egress import hang).
- **6 route hooks** (each runs in the caller's transaction → canonical lands atomically with the raw write; a fault rolls both back, consistent with the existing webhook re-dispatch contract):
  - **`routes/garmin.py`** `_ingest_wellness_fit` — **2 sites**, each before its per-file `db.commit()`. Path 1 (`_METRICS`/`_SLEEP_DATA`/`_HRV_STATUS` → `_upsert_garmin_daily_metrics`): materialize right after the upsert. Path 2 (`_WELLNESS` per-second + daily extras): capture `extras_date` and materialize **OUTSIDE the best-effort `try/except: pass`** harvest — a materialize fault must surface (the outer `except` rolls back the whole file) rather than be swallowed by `pass` and then poison the wellness_log `db.commit()` below.
  - **`routes/polar_ingest.py`** / **`routes/coros_ingest.py`** / **`routes/whoop.py`** — in each `_record_raw`, gated via the helper. `whoop.py`'s also covers the **Garmin bulk-upload CSV path** (`routes/garmin.py:_ingest_wellness_csv` → `ingest_whoop_csv` → `_record_raw`), so no separate Garmin-CSV hook is owed.
  - **`routes/whoop_ingest.py`** / **`routes/oura.py`** — in each `_merge_daily` (always `daily_summary`). NOT in whoop_ingest's `_record_raw` (that path is workouts only).
- **`.github/workflows/backfill-canonical-wellness.yml` (NEW)** — `workflow_dispatch`, **`environment: production`** (the one-tap gate, same as `layer0-apply`), optional `user_id` input. setup-python 3.11 + `pip install -r requirements.txt`, runs `python canonical_wellness.py --backfill` with `DATABASE_URL=${{ secrets.NEON_DATABASE_URL }}`. Idempotent; result echoed to the run summary.

**Rule #15:** the writer's existing `[wellness-canon] user=… date=… merged={…} garmin_ctx={…}` per-date line covers each hook fire; `backfill_canonical_wellness` adds `[wellness-canon] backfill[…] materialized N (user,date) pairs`.

## 4. Decisions baked in (review these)

1. **Hook at the lowest shared chokepoint, gated by data_type.** One uniform pattern (`_record_raw` / `_merge_daily` / the 2 Garmin sites) over per-call-site edits. Gating lives in **one** place (`_WELLNESS_FEED_DATA_TYPES`), so "which writes feed canonical" is a single source of truth.
2. **Per-write materialization, not per-batch.** A polar day writes `sleep` + `hrv` as two `_record_raw` calls → 2 materialize calls for that date (idempotent, cheap for one athlete). Collecting affected dates and materializing once per batch was rejected as more invasive per-file for negligible benefit at this data scale.
3. **Atomic with the raw write; errors propagate.** Same transaction → canonical + raw land together (or roll back together). Consistent with the existing `_record_raw` contract ("a raise propagates so the `webhook_events` row stays for re-dispatch"). The one place this needed care is Garmin path 2 (see §3) — there the materialize is placed so a fault can't be swallowed into a half-commit.
4. **Backfill reuses the writer, not a SQL re-derivation.** The Action runs the Python `materialize_canonical_wellness` so backfilled rows are byte-identical to on-ingest materialization (no coalesce drift).
5. **Test-doubles updated, deliberately (my mess to clean).** The hook made `_merge_daily`/`_record_raw`/`ingest_whoop_csv` transitively call materialize, so their unit-test fakes (`test_whoop_ingest`, `test_oura_ingest`, `test_redesign_connections_render`) had to model materialize's two reads (return empty → no-data path). The discriminator for materialize's `_prr` read is `startswith('SELECT raw_payload, fetched_at')` — a looser `in` substring also matches the `DO UPDATE SET … raw_payload = EXCLUDED.raw_payload, fetched_at = NOW()` clause in every provider INSERT (the bug I hit and fixed mid-session).

## 5. Tests + verification

- `SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:1/db?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3556 passed / 30 skipped** (pre-change baseline on this commit was 3551 — drift up from the handoff's 3543 via merges since; +5 new). The 3 Layer3B `evidence_basis` warnings pre-exist (#217).
- New tests in `tests/test_canonical_wellness.py` (**+5**): `TestProviderHook` (5 wellness pairs fire; 5 non-wellness/unknown pairs are no-ops with zero DB calls); `TestBackfill` (union-discovery parsing; materialize runs once per discovered target; `--user` scope binds the filter to both union halves).
- **Discovery SQL validated without live Postgres** (Neon egress blocked): `sqlglot.parse_one(sql, read="postgres")` parses clean for both the all-users and per-user branches (`date::text` cast + row-value `IN` list both OK).
- **CLI smoke:** no-args → exit 2 (`error: nothing to do — pass --backfill`); `--backfill` reaches `database._connect()` and raises `OperationalError` on the fast-fail DSN (proves the argparse→backfill→connect path is wired).
- **No Neon apply owed** (no DDL — the table shipped in 2.1).
- **OWED (Andy-action):** (a) **run the backfill** — trigger `backfill-canonical-wellness` (one-tap the `production` gate) after merge; (b) **LIVE-VERIFY** — on a multi-source day, confirm one canonical row with the right per-field source picks (the deferred check carried over from Slice 2.1 §5).

## 6. NEXT

- **Run the backfill (immediate, post-merge).** `backfill-canonical-wellness` Action → Andy one-taps `production`. Idempotent; re-runnable. Optional `user_id` to scope to one athlete first.
- **Slice 2.3 — consumer repoint.** Point `q_layer3A_recent_wellness` (`layer3a/integration.py`) at `canonical_daily_wellness` (a `SELECT` replacing the inline 5-source coalesce), with a **deterministic-equality test** proving the assembled `Layer3AIntegrationBundle.recent_wellness` is byte-identical (the 3A bundle hash folds into the 3A cache key — must not drift). Fold the duplicated `_WELLNESS_SOURCE_PRIORITY`/`_coalesce_wellness_field` into one home — `canonical_wellness.py` owns it; `layer3a` imports it. The backfill (above) is a 2.3 prerequisite: the reader needs historical canonical rows. Optionally repoint the `/wellness` charts. **Leave `coaching.get_wellness_summary`** (v1-coaching-only, low value).
- **Then Phase 4 — recovery-aware planning (LLM-soft).** Thread `recent_wellness` + `connected_providers.has_recent_*` into the Layer-4 plan-gen prompts (PerPhase / Refresh T1-3 / RaceWeekBrief) so suppressed HRV / sleep debt / poor readiness condition the plan. Trigger #1 (prompt) + #3 (cross-layer) → its own design gate + AskUserQuestion before code.
- **Parallel paused thread:** #884 gear/craft is mid-arc at slice 3a (slices 3→6 remain) — resume when Andy redirects back.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this Slice 2.2). 3. `CARRY_FORWARD.md` → *"#196 … Phase 2 — canonical daily-wellness layer"*. 4. This handoff + the Slice 2.1 handoff + the design doc. 5. `canonical_wellness.py` (`materialize_wellness_for_provider`, `backfill_canonical_wellness`, `_main`); the 6 route hooks (grep `materialize_wellness_for_provider|materialize_canonical_wellness` in `routes/`); `layer3a/integration.py:q_layer3A_recent_wellness` + `_coalesce_wellness_field` (the reader Slice 2.3 repoints). 6. `./scripts/verify-handoff.sh`.

## 7. Open questions
- **Backfill volume / commit granularity** — the CLI commits once at the end. For one test athlete (small history) that's fine; if history ever grows large, switch to periodic commits. Not worth complicating now.
- **Phase 4 design gate** — which Layer-4 surface first (initial PerPhase gen vs the adaptive Refresh path) + the LLM-soft guardrails. Open for the Phase-4 design slice.

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Gating helper | `canonical_wellness.py` | `def materialize_wellness_for_provider(db, uid, provider, data_type, target_date)`; `_WELLNESS_FEED_DATA_TYPES` with `polar: frozenset({"sleep", "hrv"})` |
| Backfill | `canonical_wellness.py` | `def backfill_canonical_wellness`; `def _wellness_backfill_targets` (UNION of `daily_wellness_metrics` + `provider_raw_record`, `date::text`); `if __name__ == "__main__"` → `_main` with lazy `from database import _PgConn, _connect` |
| Garmin hooks | `routes/garmin.py` | 2× `materialize_canonical_wellness(db, uid, …)` in `_ingest_wellness_fit`; path-2 call guarded by `if extras_date:` and placed AFTER the `except Exception: pass`, before `db.commit()` |
| Provider hooks | `routes/{polar_ingest,coros_ingest,whoop}.py` | `materialize_wellness_for_provider(db, user_id, '<provider>', data_type, external_id)` at the tail of each `_record_raw` |
| Merge hooks | `routes/{whoop_ingest,oura}.py` | `materialize_wellness_for_provider(db, user_id, '<provider>', 'daily_summary', day)` at the tail of each `_merge_daily` |
| Backfill Action | `.github/workflows/backfill-canonical-wellness.yml` | `environment: production`; `python canonical_wellness.py --backfill`; `DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}` |
| Tests | `tests/test_canonical_wellness.py` | `TestProviderHook` + `TestBackfill` (+5) |
| Suite | — | `… pytest tests/ -q` → 3556 passed / 30 skipped; discovery SQL parses clean under sqlglot postgres |
| No DDL / no apply owed | `init_db.py` | unchanged this slice (table shipped in 2.1) |
| Issue | #196 | comment owed on PR-open: Phase 2 Slice 2.2 (ingest hooks + backfill) shipped; epic stays open (Phases 4–5 + Slice 2.3 remain) |
