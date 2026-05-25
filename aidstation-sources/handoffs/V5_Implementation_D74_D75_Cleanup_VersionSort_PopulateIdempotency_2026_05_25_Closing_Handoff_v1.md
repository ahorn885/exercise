# D-74 + D-75 Cleanup — Populate-Script Idempotency + ETL Version-Sort — Closing Handoff

**Session:** The two Cleanup follow-ons opened during the R6 deploy. **D-75** — fix `_q_current_etl_version_set`'s lexical string-`MAX` so it picks the highest ETL version by numeric component (the digit-width landmine: `0A-v9.0` lexically outranks `0A-v11.0`). **D-74** — give the standalone versioned-INSERT populate scripts a `DELETE`-by-version prefix so re-running rebuilds each version's rows from the file and removed rows can't linger as active orphans. Andy picked both at a next-move gate; approach confirmed at a second gate (D-75 is `etl_version_set`-resolution territory → Trigger #3/#5).

**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_DisciplineID_Renumber_R6_Collapses_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/beautiful-ptolemy-7wnHU` (PR draft)
**Status:** Shipped. D-75 fixed + 6 unit tests; D-74 DELETE prefix on 3 `etl/sources/` scripts (owed-deploy on next Neon run — no DATABASE_URL in the build container). New **D-76** opened (divergent terrain_gap_rules migrations copy). Tests **1630 → 1636**.

---

## 1. Session-start verification (Rule #9)

Read order per §6.4: `CLAUDE.md` / `CURRENT_STATE.md` / `CARRY_FORWARD.md` / R6 handoff / `PR_Verification_Status.md`. Ran `scripts/verify-handoff.sh`: 3 ❌ paths, all benign — `tests/test_layer2_modality.py` (intended Slice-6 deletion, commit `9d14a79`) + `tests/test_v10/v11_parsers.py` (the script naively prepends `tests/`; the files live at `etl/tests/`, where `test_v11_parsers.py` exists and `test_v10_parsers.py` was renamed in `89a7d90`). Verified on disk — no code drift.

**One real bookkeeping drift found + reconciled:** the R6 session updated CURRENT_STATE's "Last shipped session" block (correctly: R6 shipped, 1630 tests) but left **`## Current focus`** Slice-6-framed (listing R6 as a *future* next move) and **`## Tests`** saying **1631** (contradicting the same file's 1630). Both reconciled this session (focus now R6+cleanup shipped; tests → 1636).

## 2. D-75 — `_q_current_etl_version_set` numeric version ordering

`layer4/orchestrator.py` resolved the active Layer-0 version via `SELECT MAX(etl_version) FROM layer0.sports WHERE superseded_at IS NULL`. Lexical `MAX` mis-ranks `0A-v11.0` below `0A-v9.0` at the single→double-digit boundary. Today exactly one 0A version is active post-re-extract so it resolved correctly, but it's a latent landmine the moment two version lines coexist.

**Fix (in-code, no schema change):**
- New pure helper `_max_etl_version(versions: list[str]) -> str` — `max(versions, key=lambda v: tuple(int(n) for n in re.findall(r"\d+", v)))`. `0A-v11.0` → `(0,11,0)`; a `-rN` revision suffix extends the tuple so it correctly outranks the un-revised base of the same version.
- `_q_current_etl_version_set` now does `SELECT DISTINCT etl_version` + `fetchall()`, filters NULL/empty, raises the same `etl_version_set_undiscoverable` on empty, else returns `{0A/0B/0C: _max_etl_version(...)}`.
- **Why Python-side, not SQL regex:** the orchestrator test `_FakeConn` echoes queued rows without executing SQL, so SQL-side ordering can't be unit-tested; a pure helper is directly testable at the boundary. The backlog's "monotonic integer column" alternative is overkill for a Low item.

**Test ripple:** `_queue_etl_version_set` flipped `row=` → `rows=`; the undiscoverable test now queues `rows=[]` (faithful to "no non-superseded rows"). New `TestMaxEtlVersion` (6 cases): double-digit > single-digit, low double > low single, revision-suffix > base, higher-revision wins, single passthrough, minor-version compare.

## 3. D-74 — populate-script DELETE-by-version idempotency

Added `DELETE FROM layer0.<table> WHERE etl_version = '<ver>';` inside the existing `BEGIN`, before the INSERT, on the **3 versioned-INSERT + `ON CONFLICT DO NOTHING`** scripts under `etl/sources/`:

| Script | Table | etl_version |
|---|---|---|
| `populate_terrain_gap_rules.sql` | `layer0.terrain_gap_rules` | `0C-v2.0-r2` |
| `populate_skill_capability_toggles.sql` | `layer0.skill_capability_toggles` | `0C-v2.0-r2` |
| `populate_discipline_technique_foci.sql` | `layer0.discipline_technique_foci` | `0B-v19.B` |

Each DELETE's version string matches that script's own INSERT version + verify-block version. The `ON CONFLICT DO NOTHING` clauses are kept as belt-and-suspenders (redundant after the DELETE within one run; harmless). This mirrors `etl/layer0/db.py:insert_versioned`'s DELETE-then-INSERT.

**Scope correction (deviation from backlog text):** the D-74 entry named "stimulus," but `populate_stimulus_components.sql` is **column UPDATEs on `layer0.disciplines`**, not versioned INSERTs — it cannot accumulate orphans, so DELETE-by-version doesn't apply. **Excluded.** Confirmed at the approach gate with Andy.

## 4. The migrations-copy finding → new D-76

`aidstation-sources/migrations/populate_terrain_gap_rules.sql` is a **frozen, divergent** copy: 12 rows, pre-Bucket-C `bridgeable/partial/unbridgeable` enum, "Open Water / Ocean" naming, `<> 12` verify — while `etl/sources/` has the live 16-row version (post-Phase-2.3 fidelity bands + Bucket-C gravel/moving-water rows). **Both declare `etl_version = '0C-v2.0-r2'`.** R6 mechanically renumbered ids in both but never reconciled the migrations copy's data; the 16-row `etl/sources/` copy is the deployed one (the R6 `<> 16` verify confirms).

**This is why D-74's DELETE prefix was withheld from the migrations copy** — adding `DELETE ... WHERE etl_version='0C-v2.0-r2'` there would turn a harmless no-op file into a footgun (it would wipe the live 16 rows and re-insert only its stale 12). The other two in-scope scripts have **no** migrations copy. Logged as **D-76** (Cleanup) — needs Andy's canonical-source call (reconcile / delete duplicate / re-version). Until resolved: deploy only the `etl/sources/` copy.

## 5. Code / test results

- **Full suite `python -m pytest tests/`: 1636 passed / 16 skipped** (1630 R6 baseline + 6 new `TestMaxEtlVersion`; zero regressions). `tests/test_layer4_orchestrator.py`: 63 passed.
- D-74 SQL is **not** runnable here (no `DATABASE_URL`) — mechanical edit, owed-deploy. DELETE placement verified to precede each INSERT with matching version strings.
- **Sandbox:** `python -m pip install -r requirements.txt --ignore-installed blinker && python -m pip install pytest`, then `python -m pytest tests/`.

## 6. Next session pointers

### 6.1 Owed to Andy — D-74 SQL deploy (next Neon run)
The 3 `etl/sources/populate_*.sql` edits apply on the next Layer-0 deploy. Re-running them is now idempotent (DELETE-by-version). No urgency — they're correctness/hygiene, not a behavior change; the current Neon state already has the right rows from the R6 deploy.

### 6.2 D-76 awaits a canonical-source decision (§4)
Pick: (a) reconcile the migrations copy to the live 16-row content, (b) delete the stale duplicate if `etl/sources/` is the sole deploy path, or (c) bump the migrations copy to its own etl_version if it's a deliberate snapshot. Data decision — needs Andy.

### 6.3 Carried items (unchanged from R6 §6.2/§6.3)
Spec narrative sweep (per-layer specs still cite old discipline ids in prose); stale `generate_body_parts_at_risk_migration.py` authoring artifact; kayak whitewater regression watch; K3 equipment ETL deploy on Neon (owed); deferred form-feedback batch; M-7 multi-locale; #8 locales→locations rename; BM-5 equipment-canon tail; Best-fit §14 craft-family escape hatch. Plus the 37 doable-now §5.0 manual walks in `PR_Verification_Status.md`.

### 6.4 Operating notes — read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `Project_Backlog_v62.md` (D-74/D-75 ✅, D-76 open) 6. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **scope** | Do both D-74 + D-75 as scoped | Andy at gate | Over D-75-only / D-74-only / include-stimulus. |
| **D-75 approach** | Python pure-helper numeric-tuple max (no schema change) | Andy at gate | Testable against the fake-db (SQL-side regex isn't); integer-column alternative overkill for a Low item. |
| **D-74 scope** | Exclude `populate_stimulus_components.sql` | Andy at gate (correction) | It's column UPDATEs, not versioned INSERTs — can't accumulate orphans. |
| **migrations copy** | Do NOT add DELETE to the stale terrain_gap_rules migrations copy; log D-76 instead | this agent | Adding DELETE to a 12-row file sharing the live etl_version would wipe the live 16 rows. Reconciliation is a data decision for Andy. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_max_etl_version` exists + numeric ordering | ✅ `layer4/orchestrator.py`; `re.findall` int-tuple key |
| `_q_current_etl_version_set` uses DISTINCT + helper, same error on empty | ✅ |
| D-75 unit tests cover digit-width boundary + revision | ✅ `TestMaxEtlVersion` (6) in `tests/test_layer4_orchestrator.py` |
| Test-helper + undiscoverable test updated for `fetchall` | ✅ `_queue_etl_version_set` → `rows=`; undiscoverable → `rows=[]` |
| D-74 DELETE prefix on the 3 versioned-INSERT scripts | ✅ each DELETE precedes its INSERT; version matches verify block |
| Stimulus correctly excluded from D-74 | ✅ (UPDATE-based) |
| Stale migrations copy NOT given DELETE; D-76 logged | ✅ Backlog D-76 |
| Full suite green | ✅ 1636 passed / 16 skipped |
| Backlog D-74/D-75 → ✅ Resolved + changelog | ✅ `Project_Backlog_v62.md` |
| CURRENT_STATE R6 drift reconciled (focus + tests) | ✅ |

## 9. Files shipped this session

**Code:** `layer4/orchestrator.py` (`import re`; `_max_etl_version`; `_q_current_etl_version_set` rewrite). **Tests:** `tests/test_layer4_orchestrator.py` (`_max_etl_version` import; `TestMaxEtlVersion`; `_queue_etl_version_set` + undiscoverable test). **SQL (owed-deploy):** `etl/sources/populate_terrain_gap_rules.sql`, `etl/sources/populate_skill_capability_toggles.sql`, `etl/sources/populate_discipline_technique_foci.sql`. **Bookkeeping:** `Project_Backlog_v62.md` (D-74/D-75 ✅ + D-76 + changelog), `CURRENT_STATE.md`, this handoff.

## 10. Carry-forward updates

- **D-74 + D-75 SHIPPED.** D-75 fully in production-ready code (suite green); D-74 SQL is owed-deploy on the next Neon run (idempotent, no behavior change).
- **D-76 opened** — divergent terrain_gap_rules migrations copy at a shared etl_version; needs a canonical-source decision before that copy is ever deployed.

**End of handoff.**
