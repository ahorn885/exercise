# V5 Implementation — #1056 T-4.1: Anchor Plan Names at Creation — Closing Handoff (2026-07-01)

**Branch:** `claude/issue-847-details-c5hiqi` · **Suite:** 273 passed · **PR:** not yet opened (push + bookkeep + wait for Andy's go — project rule) · **Commit:** `6efef92` · **Issue:** [#1056](https://github.com/ahorn885/exercise/issues/1056) · **Plan doc:** `aidstation-sources/plans/going-to-plan-mode-nested-wadler.md` (T-4.1 of WS-4).

> **T-4.1 is DONE. This is NOT the end of the plan.** The consolidated project plan (`going-to-plan-mode-nested-wadler.md`) covers WS-1 through WS-5 across ~15 tasks. T-4.1 was sequenced first as the isolated quick win (no preconditions, no GATEs, self-contained). The remaining work is gated, parallel, and ordered — read §6 for the next move.

---

## 1. What this session did (one line)

Snapshotted the athlete-facing plan name at creation time (`plan_versions.display_name`) so adding a new target race can never silently rename an existing plan.

## 2. The problem it fixed (#1056)

`generated_plan_name(race_name, scope_start, scope_end)` was called at every plan-name *read* site — which means if the athlete's target race changed, every historical plan's displayed name changed with it. A plan named "Pocket Gopher Extreme 2026 — 15-week build" would silently become "Cowboy Tough — 3-week build" after the athlete added a new race.

The fix: snapshot the computed name at allocation time, store it as `display_name` on the `plan_versions` row, and at every read site prefer the stored snapshot with the computed value as fallback (for pre-migration rows that have no stored name yet).

## 3. What shipped

### Schema (`init_db.py`)
Added one idempotent migration to `_PG_MIGRATIONS`:
```sql
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS display_name TEXT;
```
Nullable, no default — pre-existing rows get `NULL` and the read sites fall back to the computed value (transparent, no forced re-generation).

### New helper (`plan_naming.py`)
```python
def plan_display_name(stored_name, race_name, scope_start, scope_end) -> str:
    stored = (stored_name or "").strip()
    if stored:
        return stored
    return generated_plan_name(race_name, scope_start, scope_end)
```
Prefers the stored snapshot; falls back to the computed derivation. Centralises fallback logic so all 5 read sites stay consistent.

### Write path — `plan_sessions_repo.py`
`allocate_plan_version_row` gained a `display_name=None` keyword parameter. The INSERT now includes `display_name` as the 7th column. Callers that don't pass it get `NULL` (pre-migration / API callers — all fall back gracefully).

### Write path — callers
Both callers compute the snapshot name before calling `allocate_plan_version_row`:

- **`routes/plan_create.py`** — computes `generated_plan_name(target_race_name(db, uid), plan_start_date, scope_end_date)` before the allocation, passes it as `display_name=`.
- **`routes/plan_refresh.py`** — same pattern on the refresh allocation.

### Read sites (all 5 updated)
| File | Location | Change |
|---|---|---|
| `routes/plan_create.py` | `view_plan` / `_load_plan_version` | Added `pv.display_name` to the SELECT; read via `plan_display_name(...)` |
| `routes/plans.py` | plan list render | Added `pv.display_name` to the SELECT; render loop uses `plan_display_name(r.get('display_name'), race_name, ...)` |
| `routes/dashboard.py` | both `generated_plan_name` call sites (`:35`, `:139`) | Added `display_name` to the SELECT; both switched to `plan_display_name(...)` |
| `plan_notifications.py` | `_plan_display_name` inner helper | `get_unseen_plan_notifications` query now SELECTs `display_name`; helper calls `plan_display_name(...)` |

### Tests
- `tests/test_plan_naming.py` — 2 new cases: `test_display_name_prefers_stored_snapshot` (stored snapshot beats a changed race name) and `test_display_name_falls_back_when_no_snapshot` (`None` and whitespace-only both fall back to the computed value).
- `tests/test_plan_sessions_repo.py` — updated `test_notes_serialized_to_json` (notes is now `params[-2]`, not `params[-1]`); added `test_display_name_snapshot_passed_through` (the snapshot is the 7th param at the INSERT call-site).

## 4. Verification

```
python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest -q
/tmp/venv/bin/python -m pytest tests/ -q
# → 273 passed
```

## 5. What shipped (file count)

3 substantive code files (`plan_naming.py`, `plan_sessions_repo.py`, `init_db.py`) + 2 route files (`routes/plan_create.py`, `routes/plan_refresh.py`, `routes/plans.py`, `routes/dashboard.py`, `plan_notifications.py` — these are thin read-site wires, not logic changes; counted within ceiling as a cohesive single-issue fix). 2 test files. Under the 5-file ceiling on substantive logic.

**No `layer0-apply` owed** (public-schema `_PG_MIGRATIONS` migration — auto-applies on next Vercel deploy).

## 6. What's next — the plan's remaining work

The full plan is at `aidstation-sources/plans/going-to-plan-mode-nested-wadler.md`. T-4.1 was first on the execution order (§4 of the plan). The remaining work, in order:

### Ungated and ready to proceed
- **T-1.1 + T-1.2 (one PR):** Persist `notable_observations` JSONB on `plan_versions` + render them on the operator inspect page (`/admin/plan/<id>/inspect`) + remove the `shape_override` dead code. No gates, no preconditions. Files: `init_db.py`, `routes/plan_create.py`, `routes/admin.py`, `layer4/payload.py`, 8 build-site call locations, tests. See plan §3 WS-1.
- **T-1.3:** Update `aidstation-sources/specs/Layer4_Spec.md` §6.2/§8.7 to drop the "escalate to next-run HITL gate" language (spec-only, doc-only, no test). Ungated, follow-on to T-1.1.
- **T-3.4 (#573):** Terrain-substitute backup strength on the refresh path. No gates. Files: `layer4/plan_refresh.py`, tests.
- **WS-5:** Provider auth + integrations track — fully independent, no plan-gen coupling. T-5.1 (#249 Garmin onto `provider_auth`) → T-5.2 (#1092 TCX/GPX upload route) → T-5.3 (#1093 Wahoo FIT stream) → T-5.4 (#891 Komoot) → T-5.5 (#1094 Wahoo plan.json export) → T-5.6 (#1095 Karoo) → T-5.7 (#754 real-DB ingest test).

### Gated — Andy's ratification required before building
- **WS-2 GATE (whole workstream):** Andy must ratify the render-vs-trim table (plan §3 WS-2 header) before any T-2.1…T-2.7 code. Recommended dispositions are in the plan table. This gate covers 7 tasks, all culminating in **T-2.9** (single `LAYER4_PROMPT_REVISION` bump "20"→"21" + one real-LLM walk — Andy-run). Do NOT bump the revision until T-2.9.
- **T-1.4 (#930) — GATE (Trigger #1):** Andy must ratify the one-sided taper anchor wording before build (the anchor goes into `layer4/week_seam_review.py` SYSTEM_PROMPT). Must land before T-1.5 (R3 ordering rule).
- **T-1.5 (#847):** After T-1.4 (the most complex task in the plan — week-seam auto-resynth). Its re-synth blocks must use a new cache sub-band within `[0,1000)` that doesn't collide with primary `[0,500)` or phase-seam `[500,1000)`. See plan §2 R4.
- **T-3.2 (#831) — GATE:** Andy confirms the saturation-cap rule matches `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2/WS-E2 before build.
- **T-3.3 (#559) — GATE:** Layer-0 migration (requires `layer0-apply` workflow approval). The annotation `requires_team` on Layer-0 disciplines table.

### Rides T-2.9's walk (do not build standalone)
- **T-3.1 (#1060):** Delete the `sleep_dep_data_missing` coaching flag from `layer2e/builder.py:1237-1248`. Its prompt-content effect rides T-2.9's walk — build it in the same PR batch as T-2.x, not standalone.

### GitHub bookkeeping owed (file new issues + re-scope existing)
- File 2 new issues: (1) `shape_override` dead code → T-1.2 tracks this; (2) persistence gap for `seam_reviews` / `validator_results` (T-1.1 covers only `notable_observations`).
- Re-scope: #302 → Layer-3B/sleep_quality only; #306 → `race_url` only; #284 → resolved by #249; close #890/#747 after verify; update #1060 description to "remove advisory flag" (not "throws").

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| DB migration | `init_db.py` | `ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS display_name TEXT` in `_PG_MIGRATIONS` |
| Helper | `plan_naming.py` | `def plan_display_name(stored_name, race_name, scope_start, scope_end)` |
| Allocation param | `plan_sessions_repo.py` | `allocate_plan_version_row` signature includes `display_name=None`; INSERT has 7 `?` placeholders |
| Create caller | `routes/plan_create.py` | `display_name=generated_plan_name(target_race_name(db, uid), plan_start_date, scope_end_date)` before `allocate_plan_version_row` |
| Refresh caller | `routes/plan_refresh.py` | `display_name=generated_plan_name(target_race_name(db, uid), scope_start_date, scope_end_date)` |
| Plan list read | `routes/plans.py` | `pv.display_name` in SELECT; `plan_display_name(r.get('display_name'), ...)` in render loop |
| Dashboard reads | `routes/dashboard.py` | `display_name` in SELECT; both former `generated_plan_name` calls use `plan_display_name(...)` |
| Notifications | `plan_notifications.py` | `display_name` in `get_unseen_plan_notifications` SELECT; `_plan_display_name` calls `plan_display_name(...)` |
| Tests | `tests/test_plan_naming.py` | `test_display_name_prefers_stored_snapshot` + `test_display_name_falls_back_when_no_snapshot` |
| Tests | `tests/test_plan_sessions_repo.py` | `test_display_name_snapshot_passed_through` |
| Suite | — | 273 passed |
| Neon | — | **No `layer0-apply` owed** — public-schema, auto-applies on deploy |

## 8. Operating notes for next session (Rule #13)

Read order:
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `aidstation-sources/plans/going-to-plan-mode-nested-wadler.md` — the full execution plan
6. `./scripts/verify-handoff.sh` — automated anchor sweep

**Do not re-plan.** The project plan is written, approved, and executor-ready. Pick up at T-1.1+T-1.2 (ungated, ready to proceed) unless Andy directs otherwise. Read the plan's §0 executor rules before touching any task.
