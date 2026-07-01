# V5 Implementation — T-5.2/#1092 (TCX/GPX single-file import parity) + T-5.3/#1093 (Wahoo full FIT stream) — Closing Handoff (2026-07-01)

**Session:** Continuation of `PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` §4 Global order, after T-5.1/#249 (Garmin → shared `provider_auth`, PR #1122 — already merged into `main` when this session started).
**Date:** 2026-07-01
**Plan doc:** [`plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md) §3 T-5.2 + T-5.3
**Predecessor handoff:** [`V5_Implementation_T51_GarminProviderAuthMigration_2026_07_01_Closing_Handoff_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/handoffs/V5_Implementation_T51_GarminProviderAuthMigration_2026_07_01_Closing_Handoff_v1.md)
**Branch:** `claude/garmin-provider-auth-migration-uzv5ov` — no PR opened yet (project rule: commit + push + bookkeep, wait for Andy's explicit go).
**Status:** T-5.2 + T-5.3 shipped as one working-tree change (4 substantive code/template files: `routes/garmin.py`, `routes/wahoo.py`, `templates/garmin/import.html`, `templates/garmin/import_preview.html` — within the 5-file ceiling). Suite: **4151 passed / 30 skipped, 0 failed** (+14).

---

## 1. Session-start verification (Rule #9)

`bash aidstation-sources/scripts/verify-handoff.sh` — all ✅ (every file the T-5.1 handoff claimed exists on disk; spot-checked its own §7 anchors directly: `grep -c garmin_auth garmin_connect.py` → 0, `grep -c 'garmin_auth\b' routes/garmin.py` → 0, `DELETE FROM provider_auth` present in `routes/admin.py`). The T-5.1 predecessor's PR **#1122 was already merged** into `main` — this session's designated branch tip was identical to `origin/main` (`git merge-base --is-ancestor HEAD origin/main` true) before any new work, so per the merged-PR protocol the branch was restarted from `origin/main` (`git checkout -B claude/garmin-provider-auth-migration-uzv5ov origin/main`) and this session's work is a fresh changeset, not stacked on old history.

## 2. What shipped

### T-5.2/#1092 — TCX/GPX single-file ingest, to parity with `.fit`

**Conflict caught before writing code (issue text vs. on-disk reality):** #1092 claimed "the dedicated single-file TCX/GPX activity ingest path... isn't wired up end-to-end," implying nothing was built. Reading `routes/garmin.py` first showed the *bulk* drop zone (`import_bulk`, posted to by both `connections/hub.html`'s main uploader and `garmin/import.html`'s own bulk section) already fully dispatches `.tcx`/`.gpx` through `tcx_gpx_parser.parse_tcx`/`parse_gpx`/`detect_source` — shipped under #767 Slice 2 (2026-06-19) and Slice 5 (2026-06-20). The plan's own §1 "Ground truth" preface ("the issues are partly stale") applied here too.

The real, narrower gap was exactly what #1092's own evidence pointed at: `routes/garmin.py:1089`'s docstring calls out `.tcx`/`.gpx`, but that's the *bulk* uploader's docstring — the **separate, single-file review-and-plan-match flow** (`import_fit` → `import_preview` → `import_confirm`, the "Single activity — review & match to a plan" section on `garmin/import.html`, explicitly named in `connections/hub.html`'s own comment as *"the single-file review-and-plan-match path"*) was still hard-restricted to `.fit`/`.zip`, both in the HTML `accept` attribute and the server-side extension check in `import_fit`.

**What changed:**
- **`routes/garmin.py` `import_fit`** — extension gate now accepts `.fit`/`.tcx`/`.gpx` (plus `.zip`, unchanged, still FIT-only inside the zip — bundling non-FIT formats into a zip stays a bulk-import concern, out of scope here). Dispatches to `parse_fit`/`parse_tcx`/`parse_gpx` by extension; for non-FIT uploads, calls `detect_source(raw, ext)` (the same #1055 auto-detection the bulk path uses) to guess which app/device exported the file, and stores that in a new `flask_session['fit_import_source']` key. The dedup id (`_fit_dedup_id`) now uses the source-specific prefix (`_source_prefix(source)`) instead of always `'fit:'`, matching the bulk path's namespacing.
- **`routes/garmin.py` `import_confirm`** — the cardio branch now passes `provider=flask_session.get('fit_import_source')` into `_record_provider_raw_cardio`, so the `provider_raw_record` corroboration row is tagged with the detected source (e.g. `'coros'`/`'polar'`) instead of the parser's generic `'manual'` fallback (which `tcx_gpx_parser.py`'s own docstring already flags as "overridden by the chosen upload source at write time" — this is that override, now actually wired for the single-file path). Both branches (cardio + strength) now also pop `fit_import_source` from the session alongside the existing `fit_import` pop.
- **`templates/garmin/import.html`** — retitled "Import activity files" (was "Import .FIT files"); both the bulk section's `data-bulk-upload`/file-input `accept` attributes AND the single-activity form's file input now accept `.fit,.tcx,.gpx,.zip` (previously `.fit,.zip` on both — a same-page, same-endpoint inconsistency: the bulk section posts to `import_bulk`, which already accepted the broader set via `connections/hub.html`'s own drop zone; this page's copy of that same uploader just hadn't been updated). Copy updated to mention all three formats; "Supported activity types" table header changed from ".FIT sport" to "Sport" (the mapping is format-agnostic).
- **`templates/garmin/import_preview.html`** — breadcrumb text updated to match the renamed page ("Import activity files" instead of "Import .FIT").

**Deliberately NOT done:**
- **No dedup-before-preview added to the single-file path.** The `.fit` single-file flow never had one either (an interactive human-reviewed confirm step, unlike the bulk backfill path's idempotency requirement) — TCX/GPX reaching parity with `.fit` means matching that existing behavior, not retrofitting a new guarantee neither format had.
- **No change to zip handling.** A `.zip` uploaded to the single-file route still only extracts a `.fit` member — a zip containing `.tcx`/`.gpx` is a bulk-import scenario (`import_bulk` already handles it), out of the single-file route's scope.
- **Left `connections/hub.html`'s "Upload .FIT" button label and `templates/plans/item.html`'s "Upload completed .FIT" link text alone** — still technically accurate (FIT is still the primary format) and touching them would have pushed past the file-count this session budgeted for a low-value copy nit.

### T-5.3/#1093 — Wahoo full FIT stream

**What changed (`routes/wahoo.py`):** `_ingest_workout_summary` now:
1. Looks for a linked FIT file via new `_wahoo_fit_url(summary)` — reads `workout.file.url` (nested, matching the live-verified nested shape `normalize_wahoo_summary` already handles for other fields) with a `summary.file.url` top-level fallback. **BEST-EFFORT/VERIFY-OWED (Rule #14):** unconfirmed against a live payload that actually carries a file link — same caveat the rest of this module's docstring already carries for the webhook shape generally.
2. If a URL is present, fetches it via new `_fetch_wahoo_fit_stream` — a fresh OAuth token from `provider_auth.get_fresh_access_token` (same pattern `routes/strava_ingest.py` uses for its REST fetch), then a GET with a Bearer header. Any failure (no token, network error, non-2xx) returns `None` and is logged, never raised.
3. On a successful fetch, new `_merge_fit_stream_fields` parses the bytes with `garmin_fit_parser.parse_fit()` **unmodified** (per the plan's explicit "do NOT extract a shared parser" — FIT is a vendor-neutral binary format, so the Garmin-authored parser reads a Wahoo-produced FIT file the same way) and overlays a fixed set of stream-level fields — `max_hr`, `moving_time_min`, `elev_loss_ft`, `max_cadence`, `max_power`, `norm_power`, `aerobic_te`, `anaerobic_te`, `swolf`, `active_lengths`, `stride_length_m`, `vert_oscillation_cm`, `vert_ratio_pct`, `gct_ms`, `gct_balance` — onto the summary dict **only where the summary itself has nothing** (never overriding a value the summary already derived).

**Deliberate design call:** discipline resolution and `_provider_raw` provider tagging stay exactly what `normalize_wahoo_summary` already computes from `workout_type_id` (the matrix-§10.2 spec'd mapping), not the FIT's own sport/sub_sport enum. The plan text ("feed `_bulk_insert_cardio` with the richer fields") reads as *enriching* the summary's averages with stream-level detail, not replacing its already-spec'd discipline/provider identity with `parse_fit`'s own resolution (which is namespaced `'garmin'` internally and untested against Wahoo's device/sport combinations) — switching would also make a FIT-enriched Wahoo activity resolve its discipline differently from a summary-only one, an inconsistency the issue never asked for. If Andy wants the FIT's own discipline resolution to win instead, that's a one-line follow-up (swap which dict is the base), flagged here rather than decided silently.

The enrichment path is best-effort end to end: no OAuth token, a network failure, a non-2xx response, a malformed FIT, or an unexpected non-cardio (e.g. strength) FIT parse all fall back silently to summary-only fields — a stream-enrichment failure must never block the base `cardio_log` import the summary alone already supports.

## 3. Tests

**T-5.2** — new `tests/test_garmin_single_file_tcx_gpx_import.py` (4 tests): the extension gate rejects an unsupported file; a `.tcx` upload dispatches to `parse_tcx` and detects its source from the file's own `<Author><Name>` metadata (dedup id carries the matching prefix); a `.gpx` upload with no service fingerprint defaults to `garmin`; `import_confirm` tags the `provider_raw_record` insert with the session's detected source (not the parser's `'manual'` default), verified against the actual bound SQL params. Also updated `tests/test_redesign_garmin_import_render.py`'s existing landing-page render test for the new copy + the widened `accept` attribute.

**T-5.3** — new tests in `tests/test_wahoo_ingest.py` (10 tests): `_wahoo_fit_url` extraction (nested under `workout`, top-level, absent); `_merge_fit_stream_fields` semantics (fills gaps, never overrides an existing summary value, no-ops on a non-cardio parse, swallows a parse exception); the full `_ingest_workout_summary` path with a stubbed fetch+parse (fields land on the `_bulk_insert_cardio` call, discipline resolution untouched), a no-token skip (no crash, no fields added), and a no-`file.url` case that asserts `get_fresh_access_token` is never even called (no wasted fetch attempt when there's nothing to fetch).

Full suite: **4151 passed / 30 skipped, 0 failed** (baseline 4137 + 14 new, 0 removed/changed net — one existing assertion updated for the renamed page copy).

## 4. Docs updated (this session)

- `PROVIDERS_SCHEMA.md` / `DATABASE.md` — **no changes needed.** Neither doc carried stale "not yet built" language for TCX/GPX single-file import or the Wahoo FIT-stream deferral (unlike T-5.1's Garmin case) — checked directly, nothing to correct.
- `plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` — T-5.2 + T-5.3 flipped to **DONE** in place with as-built notes (the #1092 staleness finding + the narrowed actual gap; the T-5.3 discipline-resolution design call). §4 Global order updated.
- `CURRENT_STATE.md` — new "Last shipped session" entry; prior top entry (T-5.1) demoted to a named predecessor entry; "Current focus" §4 active-thread bullet updated to mention both landed items.

## 5. GitHub bookkeeping (this session)

- **#1092 — commented + closed** (`completed`): the audit finding (bulk path already wired; single-file path was the real gap) + what shipped, with the commit ref.
- **#1093 — commented + closed** (`completed`): what shipped + the discipline-resolution design call flagged as a one-line follow-up if Andy wants it reversed.
- Plan doc updated in-place per above (exempt from the 5-file ceiling as bookkeeping).

## 6. Next session pointers

Per the execution plan's §4 Global order, WS-5 continues:

- **T-5.4 (#891) — Komoot connect + ingest.** Ungated, next in order. Per the plan: add a new `routes` module for Komoot (not yet created — no file exists for it today), modeled on `routes/strava.py`/`routes/polar.py` (provider_auth + a normalizer feeding `_bulk_insert_cardio(source='komoot')`).
- **T-5.5 (#1094) — Wahoo plan.json export** and **T-5.6 (#1095) — Karoo download target** after T-5.4.
- **T-5.7 (#754) — real-DB ingest test**, do last per the plan.
- Everything outside WS-5 stays exactly as prior handoffs left it: **T-1.4 (#930)** GATED on Andy ratifying taper anchor wording; **WS-2** GATED on the render-vs-trim table; **T-3.2/T-3.3** GATED (saturation-cap rule / Layer-0 migration).
- **No PR opened this session** (project rule: commit + push + bookkeep, wait for Andy's go). Once he says go: push (already done), open the PR (ready, not draft, merge-commit method), `enable_pr_auto_merge`.
- **Follow-up flagged, not built:** if Andy wants a FIT-enriched Wahoo activity to resolve its discipline via the FIT's own sport/sub_sport enum instead of Wahoo's `workout_type_id` mapping, that's a one-line swap in `_ingest_workout_summary` (use `parsed['data']` as the base dict instead of overlaying onto `normalize_wahoo_summary`'s output) — not built because it wasn't asked for and would make FIT-enriched vs. summary-only Wahoo activities resolve inconsistently.

### Operating notes (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`
6. `bash aidstation-sources/scripts/verify-handoff.sh`

---

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Single-file extension gate | `routes/garmin.py` | `import_fit`: `ext = next((e for e in _ACTIVITY_EXTS if fname.endswith(...` |
| Single-file parser dispatch | `routes/garmin.py` | `parser = {'fit': parse_fit, 'tcx': parse_tcx, 'gpx': parse_gpx}[ext]` |
| Single-file source tagging | `routes/garmin.py` | `flask_session['fit_import_source'] = source`; `import_confirm`: `provider=flask_session.get('fit_import_source')` |
| Import page copy/accept | `templates/garmin/import.html` | `accept=".fit,.tcx,.gpx,.zip"` (both sections); title "Import activity files." |
| Wahoo FIT-url extraction | `routes/wahoo.py` | `def _wahoo_fit_url(summary: dict)` |
| Wahoo FIT fetch | `routes/wahoo.py` | `def _fetch_wahoo_fit_stream(db, user_id, file_url)` — `pa.get_fresh_access_token(... 'wahoo' ...)` |
| Wahoo FIT merge | `routes/wahoo.py` | `def _merge_fit_stream_fields(data, fit_bytes)` — `from garmin_fit_parser import parse_fit` |
| Tests | `tests/test_garmin_single_file_tcx_gpx_import.py` | `test_tcx_upload_dispatches_to_parse_tcx_and_detects_source` |
| Tests | `tests/test_wahoo_ingest.py` | `TestIngestWithFitStream::test_full_path_fetches_and_merges_stream_fields` |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 4151 passed / 30 skipped |
| Plan doc | `plans/PlanGenReliability_..._v1.md` | T-5.2 + T-5.3 both show "— **DONE 2026-07-01.**" |
| GitHub | — | #1092 + #1093 closed `completed` with commit ref |
| Branch | — | `claude/garmin-provider-auth-migration-uzv5ov`; no PR yet, awaiting Andy's go |

**End of handoff.**
