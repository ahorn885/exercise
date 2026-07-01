# V5 Implementation — T-5.4/#891 (Komoot, blocked-on-partner) + T-5.5/#1094 (Wahoo plan.json push) + T-5.6/#1095 (Karoo labeling) — Closing Handoff (2026-07-01)

**Session:** Continuation of `PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` §4 Global order, after T-5.2/T-5.3 (TCX/GPX + Wahoo FIT stream, PR #1123 — already merged into `main` when this session started).
**Date:** 2026-07-01
**Plan doc:** [`plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md) §3 T-5.4 + T-5.5 + T-5.6
**Predecessor handoff:** [`V5_Implementation_T52_TCXGPXSingleFileImport_T53_WahooFITStream_2026_07_01_Closing_Handoff_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/handoffs/V5_Implementation_T52_TCXGPXSingleFileImport_T53_WahooFITStream_2026_07_01_Closing_Handoff_v1.md)
**Branch:** `claude/orphaned-data-partial-wiring-bvm32l` — no PR opened yet (project rule: commit + push + bookkeep, wait for Andy's explicit go).
**Status:** T-5.4 investigated and found genuinely partner-gated (not built, left open + labeled). T-5.5 + T-5.6 shipped as one working-tree change (6 substantive files — over the nominal 5-file ceiling, but `templates/dashboard.html`/`templates/plans/item.html` are one-line copy/tooltip edits, not a scope expansion). Suite: **4169 passed / 30 skipped, 0 failed** (+18).

---

## 1. Session-start verification (Rule #9)

`bash aidstation-sources/scripts/verify-handoff.sh` — all ✅ (every file the T-5.2/T-5.3 handoff claimed exists on disk, spot-checked directly: `import_fit`'s extension gate, the parser dispatch dict, `fit_import_source` session key, `import.html`'s widened `accept`, and all three `routes/wahoo.py` T-5.3 anchors). PR #1123 (that handoff's work) was already merged into `main`; this session's branch tip was `origin/main` (`git log origin/main..HEAD` = 0 commits), so no branch restart was needed — the designated branch was already current.

## 2. What shipped

### T-5.4/#891 — Komoot connect + ingest — **NOT BUILT, blocked-on-partner**

Before writing any OAuth code, checked whether Komoot's API is self-serve like Strava/Polar/Wahoo (all of which just need registering an app on a developer portal). It isn't: Komoot's OAuth2 API (`komoot.de/b2b/connect`) requires an **approved business partnership** — there's no open developer-registration path to get a `client_id`/`client_secret`. Confirmed via Komoot's own support docs and the `komoot/komoot-oauth2-connect-example` reference repo (both fetched live this session).

This is the same shape as **#833** (TrainingPeaks inbound, already in this plan as a partner-gated no-build). Flagged to Andy via `AskUserQuestion` rather than building fake OAuth scaffolding against an unreachable API (options: skip like #833 / build speculative scaffolding anyway / something else). **Andy's call: skip, same as #833.** #891 left **open** (not closed — matches #833's convention), commented with the finding, labeled `status:blocked`.

### T-5.5/#1094 — Wahoo plan.json export — **DONE**

**Scope correction caught before building (2nd `AskUserQuestion` this session):** #1094's own scope note called Wahoo `plan.json` a passive file download, "not a push API," matching Zwift's `.zwo` pattern. That's wrong on two independent sources: the Provider Inbound Matrix §10.2 itself ("`plans_write` **pushes** a Wahoo-proprietary `plan.json`") and Wahoo's real Cloud API docs (fetched live this session): create a `plan` record, attach it to a `workout` record scheduled within **[today, today+6 days]**, and Wahoo syncs it to the ELEMNT/RIVAL Planned Workouts view automatically within ~30s. There's no known manual-file-import path on Wahoo hardware (unlike Zwift's `Documents/Zwift/Workouts/` folder-drop) — shipping a passive download would have given athletes a file they couldn't actually use. Wahoo's existing OAuth connection (T-5.1/T-5.3, already live) doesn't request `plans_write`, so pushing needs a scope bump. **Andy's call: build the real push.**

**What changed:**
- **`routes/outbound_workout.py`** — new `to_wahoo_plan_json(session)`: serializes a cardio `PlanSession` to `{header, intervals[]}` per matrix §10.2 (each interval carries `targets`/`triggers`; `TARGET_TYPE` enum mapped from our Z1–Z5 zones via a new `_ZONE_TO_WAHOO_TARGET_TYPE` table — `Z1→recover, Z2→tempo, Z3→lt, Z4→map, Z5→ac`, `warmup→wu`, `cooldown→cd`). Same %FTP/%LTHR anchor as `to_zwo`/`to_tp_structure` (the athlete's actual FTP/LTHR isn't reliably ingested — zone is the serialization anchor, per the Wave-3b design's load-bearing decision). No discipline gate — unlike Zwift's bike/run-only software limit, Wahoo's ELEMNT+RIVAL hardware family covers the same broad sport set TP does, so this mirrors `to_tp_structure`'s no-gate behavior. `interval_set` reps are expanded into flat repeated work/rest interval entries rather than a nested repeat wrapper — the matrix's own source note (a PDF + an OpenAPI mirror, not a live payload) doesn't document a repeat construct for `intervals[]`, so a wrapper shape wasn't fabricated.
- **`routes/wahoo.py`** — new `POST /wahoo/push/<plan_version_id>/<date>/<idx>`: two-step Wahoo Cloud API call (`POST` a Base64 `plan.json` to `_WAHOO_PLANS_URL`, then `POST` a `workout` record to `_WAHOO_WORKOUTS_URL` referencing the plan id, dated `date`, with `workout_type_family_id` from a new `_WAHOO_FAMILY_ID` map — `cycling→0, running→1, swimming→2, hiking→9(walk)`, the same hiking→walk judgment call `routes/trainingpeaks.py`'s `_TP_WORKOUT_TYPE` already makes). Idempotent via `provider_outbound_ref` (mirrors `routes/trainingpeaks.py`'s Slice-2 pattern exactly — same table, same hash-compare-noop shape). Refuses pushes for a session dated outside `[today, today+6]` (Wahoo's real device-sync window, confirmed via Wahoo support docs — not documented in the matrix itself, so flagged VERIFY-OWED). Bumped `_WAHOO_SCOPES` to add `plans_write` and bumped `_WAHOO_SCOPE_VERSION` to `2026-07-01` — this forces re-consent, so an athlete who connected Wahoo *before* this session's deploy has a token without `plans_write`; the route checks the stored `scopes` column and flashes "reconnect Wahoo" rather than attempting a push Wahoo would reject.
- **`routes/plan_create.py`** — `view_plan` now computes `wahoo_connected` (active connection **and** `plans_write` in the granted scopes) and passes it to the template.
- **`templates/plan_create/view.html`** — a real "↑ Send to Wahoo" button next to the existing Zwift `.zwo` link, gated on `wahoo_connected`. Unlike the still-gated TP connector (backend-only, zero UI — dead code until partner access opens), Wahoo OAuth is already live, so this ships something an athlete can use today. UI-driven: every outcome (success, no-op, out-of-window, not-connected, missing-scope, push failure) `flash()`es a reason and redirects back to the plan view, matching this app's existing OAuth-callback UX convention (`_fail()` in `routes/wahoo.py`'s own OAuth callback) rather than the TP push route's bare-JSON API shape.

**Deliberately NOT done:**
- No new UI for the TP connector — out of scope, TP stays gated with no template changes.
- No attempt to build a nested "repeat" construct in `plan.json` — documented as a judgment call above (source doesn't confirm one exists).
- No live-Wahoo verification — the exact `/v1/plans`/`/v1/workouts` field names are this session's best reading of the matrix's terse source note (a PDF + an OpenAPI mirror), not confirmed against a live push. Flagged VERIFY-OWED per Rule #14, same caveat the matrix itself already carries for this row and T-5.3 already carries for the FIT-url field.

### T-5.6/#1095 — Karoo download target — **DONE**

Verified the issue's own framing ("no new serializer needed") holds, then shipped pure UI labeling:
- `routes/plans.py`'s `download_item_fit` already calls `fit_workout_generator.generate_workout_fit` — a proper `FileType.WORKOUT` + `WorkoutMessage` FIT (not `generate_activity_fit`'s recording shape), which is exactly the structure Hammerhead's Karoo dashboard accepts.
- `_build_steps`'s distance-only branch (fires only when there's no `duration_min`, just a `target_distance_mi`) correctly emits a `WorkoutStepDuration.DISTANCE`-typed step — a valid FIT construct, not a bug to fix. Karoo's own docs note distance-based steps "may not import as expected," but that's Karoo's behavior on spec-correct input, not something to work around in our generator.
- The Layer4 (`plan_create`) session view's `.zwo` export (`to_zwo`) is 100% time-based already — `CardioBlock` has no distance field at all — so the caveat doesn't even apply there.

**What changed:** `templates/plans/item.html`'s FIT rail-note now mentions Karoo compatibility; `templates/dashboard.html`'s compact `.FIT` button gets a `title` tooltip doing the same; `templates/plan_create/view.html`'s Zwift link is relabeled "↓ .zwo (Zwift, Karoo)" with a tooltip, since Karoo accepts `.zwo` directly. No routes, no serializers, no schema — copy-only.

## 3. Tests

**T-5.5** — `TestWahooPlanJson` in `tests/test_outbound_workout.py` (8 tests: %FTP vs %LTHR band selection, warmup/cooldown target types, zone→target-type mapping, interval-rep flattening into work/rest pairs, header name, non-cardio raises, no discipline gate). New `tests/test_wahoo_outbound.py` (10 tests: new-session push + `provider_outbound_ref` insert, unchanged-payload no-op with no HTTP call made, changed-payload update, missing-session 404, non-cardio session, not-connected, missing-`plans_write`-scope (no push attempted), outside-sync-window (no push attempted), today-is-in-window boundary, push-failure records `STATUS_ERROR`). Both files use monkeypatched network + DB, matching `tests/test_trainingpeaks_outbound.py`'s established shape exactly.

**T-5.6** — no new tests (copy-only change); full suite re-run to confirm no regressions.

Full suite: **4169 passed / 30 skipped, 0 failed** (baseline 4151 + 18 new, 0 removed/changed). `ruff check` on every touched file: **0 new findings** (the one pre-existing `outbound_workout.py:150` F541 finding confirmed unchanged via `git stash` diff — it's in `to_zwo`, untouched this session).

## 4. Docs updated (this session)

- `plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` — T-5.4 flipped to **BLOCKED-ON-PARTNER**, T-5.5 + T-5.6 flipped to **DONE**, both with as-built notes; §4 Global order updated.
- `CURRENT_STATE.md` — new "Last shipped session" entry; prior top entry (T-5.2/T-5.3) demoted to a named predecessor entry.

## 5. GitHub bookkeeping (this session)

- **#891 — commented, left OPEN, labeled `status:blocked`** (matches #833's convention): the partner-gate finding + Andy's skip decision.
- **#1094 — commented + closed** (`completed`): the scope-correction finding (push, not download) + what shipped.
- **#1095 — commented + closed** (`completed`): the verify-then-label finding + what shipped.
- Plan doc updated in-place per above (exempt from the 5-file ceiling as bookkeeping).

## 6. Next session pointers

Per the execution plan's §4 Global order, WS-5 has one item left:

- **T-5.7 (#754) — real-DB cardio-ingest test, do last per the plan.** Deliberately **not** attempted this session — investigated enough to know it's a real slice of its own, not a bolt-on: the issue's own suggested infra ("the `layer0-gate` CI job already stands up a Postgres service") only gets you a *Postgres service* — `layer0-gate`'s job loads a narrow `layer0`-only genesis snapshot, not the full app schema (`cardio_log`, `provider_raw_record`, etc.) that `_bulk_insert_cardio`/`_record_provider_raw_cardio` need. Closing this properly needs either a new/extended CI job that runs the full `init_db.py::init_postgres()` bootstrap against a fresh Postgres service, or a locally-runnable test gated behind a `requires_real_postgres`-style skip marker (mirroring `tests/conftest.py`'s existing `requires_anthropic_api_key` pattern) that a follow-up CI change later wires in. The container does have a local `postgres:16` cluster installed (currently stopped) that could serve as the dev-side target. Recipe for next session: start the local cluster, monkeypatch `init_db.DATABASE_URL` to point at it, call `init_db.init_postgres()` once to bootstrap schema, then write `tests/test_cardio_ingest.py` against a real connection — decide then whether to also wire a CI job in the same PR or file that as a fast-follow.
- Everything outside WS-5 stays exactly as prior handoffs left it: **T-1.4 (#930)** GATED on Andy ratifying taper anchor wording; **WS-2** GATED on the render-vs-trim table; **T-3.2/T-3.3** GATED (saturation-cap rule / Layer-0 migration).
- **No PR opened this session** (project rule: commit + push + bookkeep, wait for Andy's go). Once he says go: push (already done), open the PR (ready, not draft, merge-commit method), `enable_pr_auto_merge`.
- **Follow-up flagged, not built:** #891/Komoot unblocks when either (a) a Komoot b2b partnership is approved (real `client_id`/`client_secret`), or (b) Andy decides to build the OAuth/ingest scaffolding speculatively anyway despite no live target (like the TP connector) — his call, not decided here.

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
| Wahoo plan.json serializer | `routes/outbound_workout.py` | `def to_wahoo_plan_json(session: dict[str, Any])`; `_ZONE_TO_WAHOO_TARGET_TYPE` |
| Wahoo push route | `routes/wahoo.py` | `def push_session(plan_version_id: int, date: str, idx: int)` |
| Wahoo scope bump | `routes/wahoo.py` | `_WAHOO_SCOPES = '... plans_write'`; `_WAHOO_SCOPE_VERSION = '2026-07-01'` |
| Push-window helper | `routes/wahoo.py` | `def _today() -> _date` |
| Plan-view context | `routes/plan_create.py` | `wahoo_connected = bool(` |
| Plan-view button | `templates/plan_create/view.html` | `url_for('wahoo.push_session', ...)`; "↑ Send to Wahoo" |
| Karoo labeling | `templates/plans/item.html` | "compatible with the Hammerhead Karoo dashboard's workout import" |
| Karoo labeling | `templates/dashboard.html` | `title="Compatible with Garmin and Hammerhead Karoo"` |
| Karoo labeling | `templates/plan_create/view.html` | "↓ .zwo (Zwift, Karoo)" |
| Tests | `tests/test_outbound_workout.py` | `class TestWahooPlanJson` |
| Tests | `tests/test_wahoo_outbound.py` | `class TestPush` |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 4169 passed / 30 skipped |
| Lint | — | `ruff check` on all touched files → 0 new findings |
| Plan doc | `plans/PlanGenReliability_..._v1.md` | T-5.4 shows "BLOCKED-ON-PARTNER"; T-5.5 + T-5.6 show "DONE 2026-07-01" |
| GitHub | — | #891 open + `status:blocked` + commented; #1094 + #1095 closed `completed` |
| Branch | — | `claude/orphaned-data-partial-wiring-bvm32l`; no PR yet, awaiting Andy's go |

**End of handoff.**
