# V5 Implementation — Garmin Wellness Bulk Import NameError Fix (#933) — Closing Handoff (2026-06-28)

**Branch:** `claude/fix-wellness-bulk-import-namerror` · **Suite:** 3585 passed / 30 skipped · **PR:** pending (Andy authorized open + merge this session) · **Issue:** #933.
**Context:** discovered while verifying the #196 Phase 2 **Slice 2.2** backfill (merged #931). The backfill correctly returned 0 rows — which surfaced this latent bug. This is a standalone Tier-2 (live-functionality) fix that **unblocks the #196 wellness layer end-to-end**; the #196 thread resumes at **Slice 2.3** (§6).

> **▶ IMMEDIATE NEXT: (1) after this deploys, Andy re-uploads his Garmin wellness zips → daily metrics land → the Slice-2.2 hook materializes `canonical_daily_wellness`; (2) then the multi-source LIVE-VERIFY is finally exercisable; (3) Slice 2.3 — repoint the Layer-3A reader (full kickoff in §6).**

---

## 1. The problem (one line)

`POST /garmin/import-wellness/bulk` raised `NameError: '_iter_fit_blobs' is not defined` on **every** upload from 2026-06-19 onward, so no Garmin wellness FIT made it into `daily_wellness_metrics` — which is why the Slice-2.2 backfill had nothing to materialize.

## 2. Root cause + evidence

- **Rename missed one call site.** #767 Slice 2 (manual TCX/GPX upload, 2026-06-19; handoff `…767_ManualUpload_TCXGPXParser_Slice2…`) renamed the zip-extraction helper `_iter_fit_blobs` → `_iter_activity_blobs` and changed its yield shape from a 3-tuple `(name, raw, err)` to a 4-tuple `(name, bytes, ext, err)`. The unified activity importer was updated (`routes/garmin.py:1125`); the **wellness** importer (`import_wellness_bulk`, ~L2089) was **not** — it kept calling `_iter_fit_blobs(files)`, a name that no longer exists. Grep-confirmed: the only reference in code was that one dead call.
- **Prod data confirms the blast radius** (read-only `neon-query` diagnostics, 2026-06-28):
  - `daily_wellness_metrics` = **0** (and the pre-rename `garmin_daily_metrics` = 0 → no orphaned data).
  - `wellness_log` = **802** rows, source `wellness_fit`, dated **only Feb 22–23** (uploaded *before* the rename, when the endpoint worked) — nothing since.
  - `provider_raw_record` for garmin = only `cardio` (activity dedup), no wellness data_types.
  - So every wellness-zip upload since 2026-06-19 → 500 → silently dropped. The Feb per-second data is the last time the path worked.
- **Why it was invisible:** the wellness bulk path was `print`-silent (no Rule #15 logging), so the 500s never showed a reason in `/admin/logs`.

## 3. What shipped (2 substantive files)

- **`routes/garmin.py` — `import_wellness_bulk`:** call `_iter_activity_blobs`, unpack the 4-tuple `(name, raw, ext, err)`, and **gate `ext == 'fit'`** (the endpoint is Garmin-wellness-FIT only — a stray `.tcx`/`.gpx`/`.csv` in the drop or zip is skipped with a clear detail). Plus **Rule #15** instrumentation: a per-file `[wellness-import] user=… skipped/error: <name> — <detail>` line for the silent-drop branches + a `[wellness-import] user=… files=… metrics_days=… imported=… dup=… skipped=… errors=…` summary, so a future failure is diagnosable from the log drain.
- **`tests/test_redesign_garmin_import_render.py` (+2):** `test_wellness_bulk_extracts_every_fit_in_zip` — posts a zip of 3 FITs, mocks `fit_file_meta` + `_ingest_wellness_fit`, asserts 200 + one ingest call per FIT (a **500 before the fix** — this is the regression guard); `test_wellness_bulk_skips_non_fit_entries` — a `.csv` is skipped, not ingested (the `ext == 'fit'` gate).

## 4. Notes / decisions

1. **`ext == 'fit'` gate, not csv passthrough.** The unified `/garmin/import/bulk` handles WHOOP CSV; this dedicated wellness-FIT endpoint stays FIT-only (its prior behaviour). A csv dropped here is skipped honestly rather than silently ignored.
2. **Logging added because the silence *was* the bug's camouflage.** Per Rule #15, the branches that can drop a file now say so.
3. **No data migration / backfill in this fix.** The fix only restores the importer. The wellness data itself returns when Andy re-uploads (the FITs were never stored — they 500'd).

## 5. Tests + verification

- `SECRET_KEY=x DATABASE_URL='…connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3585 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217). Targeted: `pytest tests/test_redesign_garmin_import_render.py -q` → 7 passed.
- The fix is static-verifiable: `_iter_fit_blobs` no longer appears in code (grep); `import_wellness_bulk` uses `_iter_activity_blobs` + the 4-tuple.
- **OWED (Andy, post-deploy):** re-upload one Garmin wellness zip; confirm the UI reports `metrics_days > 0` and `/admin/logs` shows the new `[wellness-import]` summary; then verify `daily_wellness_metrics` + `canonical_daily_wellness` populate (the Slice-2.2 hook fires on the metrics upsert). If history is wanted, re-run the `backfill-canonical-wellness` Action.

## 6. NEXT — resume the #196 thread at Slice 2.3 (kickoff)

**Prereq:** wellness data must be flowing (Andy re-uploads post-fix; optionally re-run the backfill) so 2.3's reader repoint has rows to read and the live spot-check is meaningful. The unit work below does **not** need live data.

**Slice 2.3 — repoint the Layer-3A reader at the canonical table.**
- **Target:** `layer3a/integration.py:q_layer3A_recent_wellness` — today it does an inline 5-source coalesce (the merge `canonical_daily_wellness` now materializes). Replace that with a `SELECT … FROM canonical_daily_wellness WHERE user_id = %s AND date >= %s` (the recent window), mapping columns back to the `recent_wellness` shape the 3A bundle expects.
- **Hard constraint — cache-key stability:** the assembled `Layer3AIntegrationBundle.recent_wellness` feeds the 3A bundle hash, which folds into the 3A cache key. The repoint must be **byte-identical** to the current output for the same underlying data, or it silently invalidates 3A caches. Build a **deterministic-equality test**: feed a fake conn known multi-source wellness for a few days, run the OLD inline-coalesce path and the NEW canonical-read path, assert the produced `recent_wellness` structures are identical. (Unit-level — no live DB.)
- **Fold the duplicated coalesce into one home:** Slice 2.1 deliberately *copied* `_WELLNESS_SOURCE_PRIORITY` + `_coalesce_wellness_field` from `layer3a.integration` into `canonical_wellness.py` (flagged for 2.3). Now make `canonical_wellness.py` the single owner and have `layer3a` import from it (or delete the layer3a copy entirely once the reader no longer coalesces — it just SELECTs the materialized row). Watch the 3A cache-key test while doing this.
- **Optional:** repoint the `/wellness` charts (`routes/wellness.py`) at the canonical table. **Leave `coaching.get_wellness_summary`** (v1-coaching-only, low value — explicitly out of scope).
- **Scale:** ≤5 files (layer3a/integration.py + canonical_wellness.py + the equality test + maybe routes/wellness.py). Its own slice.

**Then Phase 4 — recovery-aware planning (LLM-soft):** thread `recent_wellness` + `connected_providers.has_recent_*` into the Layer-4 plan-gen prompts (PerPhase / Refresh T1-3 / RaceWeekBrief). Trigger #1 (prompt) + #3 (cross-layer) → its own design gate + AskUserQuestion before code.

**Parallel paused thread:** #884 gear/craft is mid-arc at slice 3b (slices 4→6 remain, design-v3 §15) — resume when Andy redirects.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this fix). 3. `CARRY_FORWARD.md` → *"#196 … Phase 2 — canonical daily-wellness layer"* (the Slice 2.2 + this-fix bullets). 4. This handoff + the Slice 2.1 / 2.2 handoffs + the design doc `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md`. 5. `layer3a/integration.py:q_layer3A_recent_wellness` + `_coalesce_wellness_field` (the reader 2.3 repoints); `canonical_wellness.py` (`materialize_canonical_wellness` + `_WELLNESS_SOURCE_PRIORITY`/`_coalesce` — the copy to fold). 6. `./scripts/verify-handoff.sh`.

## 7. Open questions
- **Did Andy upload only `_WELLNESS` files before, or all four types?** Moot for the fix (the importer was dead regardless), but it affects how much history returns on re-upload. Confirm by re-uploading one zip and reading the `[wellness-import]` summary + `daily_wellness_metrics` count.
- **Slice 2.3 `/wellness` chart repoint** — in-scope or deferred? Low-risk either way; decide at build.

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Fix | `routes/garmin.py` | `import_wellness_bulk` loops `for name, raw, ext, err in _iter_activity_blobs(files)`; `if ext != 'fit':` skip branch; **no `_iter_fit_blobs` *call*** remains (grep → only the explanatory comment at ~L2092 mentions the old name) |
| Logging | `routes/garmin.py` | `[wellness-import]` per-file skip/error lines + the `files=… metrics_days=… imported=… skipped=… errors=…` summary print before the `jsonify` return |
| Tests | `tests/test_redesign_garmin_import_render.py` | `test_wellness_bulk_extracts_every_fit_in_zip` + `test_wellness_bulk_skips_non_fit_entries` |
| Suite | — | `… pytest tests/ -q` → 3585 passed / 30 skipped |
| Issue | #933 | open → comment shipped + PR ref → close `completed` on merge |
| Unblocks | `canonical_wellness.py` / Slice 2.2 | once wellness re-uploads, the materialize hook fills `canonical_daily_wellness`; LIVE-VERIFY then exercisable |
