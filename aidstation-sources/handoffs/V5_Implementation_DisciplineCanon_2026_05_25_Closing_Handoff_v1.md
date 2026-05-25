# Discipline Canon — single source of truth for discipline ids + names — Closing Handoff

**Session:** Establish the **discipline canon**. Triggered by a DB audit Andy
ran showing one `discipline_id` carrying up to ten different `discipline_name`
labels across the layer0 denorm tables. Designed conversationally at the gate
(not from a prior handoff in this convention) and shipped as two PRs.
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_SpecNarrativeSweep_R6_PostRenumber_2026_05_25_Closing_Handoff_v1.md`
**Branch:** bookkeeping on `claude/canon-bookkeeping`; the code shipped on `claude/lucid-ptolemy-KX1Bc` (#166) and `claude/canon-composite-share-fix` (#167).
**Status:** **Both PRs merged to `main`** (#166 `5ddc0ac`, #167 `ee0756f`). Migration + first loader run already executed by Andy against Neon. **One owed action remains: re-run the loader to apply #167's fixes** (the live Neon data is the #166-era load — see §5).

> **Process note (honest record):** This is a **Trigger #3 cross-layer change**
> (layer0 schema column add + discipline-id/name contract consumed by
> Layers 2/3/4) that was driven conversationally rather than through a
> `/plan` gate, and merged before this bookkeeping landed. The decisions were
> all ratified by Andy in-thread (§7); this handoff + the rolling-state
> updates are the retroactive bookkeeping the protocol owes.

---

## 1. Session-start verification (Rule #9)

This session did **not** start from the prior handoff — it started from Andy's
DB audit output. No `verify-handoff.sh` reconciliation was run at the top. The
load-bearing grounding instead was a **source-side audit**: the canon was built
against the live `Sports_Framework_v11.xlsx` via the real extractors (no DB), so
every distinct `(discipline_id, discipline_name)` the ETL emits is provably
accounted for (see `etl/tests/test_discipline_canon.py::test_every_source_id_is_accounted_for`).

---

## 2. Session narrative

The audit showed `discipline_name` drift: the layer0 ETL extracts the name
**literally** from `Sports_Framework_v11.xlsx`, so per-sport context smeared into
the name field (one id → up to ten labels), and a parallel app-layer overlay
(`discipline_display_names.py`) had itself drifted into mislabels (e.g. "Alpine
Skiing" for the skimo descent leg). Composite keys (`D-006 + D-007`), a pseudo-id
(`D-014 (Ref)`), and two dash sentinels for non-discipline rows compounded it.

Decided the **canon** (25 disciplines, one clean name each) and the structural
rules, then located the correct fix seam: the repo already normalizes
vocabulary at ETL time without touching the source xlsx (`sport_name_aliases.py`,
`vocabulary_transforms.py`). The canon belongs there — a one-off table `UPDATE`
would re-drift on the next ETL run, and the ETL even resolves ids *by name*
(`run.py:name_to_id`), which is what spawned the composite/orphan keys.

**#166** shipped the canon + ETL application + a conformance validator + the
migration + the display-overlay re-export. While tracing how plan-gen consumes
the canon, found that the composite split was **duplicating the race-time/load
share onto both legs** (Triathlon cycling 90.5→140.5; `load_weight` derives from
`race_time_pct` with no normalization in layer2a, and there's a `≈1.0` gate at
`plan_create.py:172`). **#167** fixed that (share to the primary leg only) and
folded in the **Swimrun run-leg override** (sport-scoped: Swimrun's run leg is
road D-002, not the source's trail D-001). Both merged. Andy ran the
`row_category` migration + the first loader pass in Neon after #166.

---

## 3. File-by-file edits (as merged on `main`)

### New
- **`etl/layer0/discipline_canon.py`** — the single source of truth.
  `CANONICAL_NAMES` (25 ids→names), `ID_REMAP` (D-005/D-016→D-004),
  `REMOVED_IDS` (D-020, D-023), `SPORT_DISCIPLINE_OVERRIDES`
  (`("Swimrun","D-001")→"D-002"`), `CATEGORY_*` + `CATEGORY_DISPLAY`,
  and resolution + row-normalization helpers (`resolve_ids`, `canonical_name`,
  `classify_non_discipline`, `normalize_dimension_rows`, `normalize_named_rows`
  with `share_fields`/`sport_field`, `normalize_substitute_rows`,
  `normalize_pairing_rows`).
- **`etl/layer0/validation/discipline_canon_check.py`** —
  `run_discipline_canon_conformance(conn)`: fails the load (ERROR) if any
  non-superseded row carries a non-canonical id or a name ≠ `CANONICAL_NAMES[id]`.
- **`etl/tests/test_discipline_canon.py`** — 32 tests: static canon shape,
  full source-coverage against the real xlsx, per-table normalization, composite
  primary-leg share attribution + Triathlon/Off-Road total preservation, Swimrun
  swim+road, override scoping.
- **`aidstation-sources/migrations/migrate_discipline_canon_2026_05_25.sql`** —
  adds `phase_load_allocation.row_category` (PART 1, required before the loader);
  optional PART 2 retires canon-dropped rows (abort-proof — only sets
  `superseded_at`). Runbook header: the **ETL re-run is the authoritative data
  step**; in-place renames are avoided (the table is `UNIQUE(sport_name,
  discipline_name)` so collapsing variants in place can collide).

### Modified
- **`etl/layer0/run.py`** — applies the canon to every discipline-bearing table
  (`normalize_dimension_rows` for disciplines; `normalize_named_rows` for
  sport_discipline_map [`share_fields`=race_time_pct_*, `sport_field`],
  phase_load_allocation [`keep_non_discipline`, share_fields=*_pct_*,
  `sport_field`], discipline_training_gaps; `normalize_substitute_rows`;
  `normalize_pairing_rows`). Added `row_category` to `pl_columns`. Wired the
  conformance validator into the validation phase + report extras.
- **`discipline_display_names.py`** — now a thin **re-export** of the canon
  (`from etl.layer0.discipline_canon import CANONICAL_NAMES as DISCIPLINE_DISPLAY_NAMES, …`);
  public `discipline_display_name(id, fallback)` API preserved (callers:
  `routes/race_events.py`, `layer2_modality/substitution.py`).
- **`etl/layer0/schema.sql`** — `phase_load_allocation` gains `row_category TEXT`
  (fresh installs; existing Neon got it via the migration).
- **`layer2d/builder.py`** — `_KNOWN_GAP_DISCIPLINES` doc constant updated
  `{D-020,D-022,D-025}`→`{D-022,D-025}` (D-020 removed; constant is documentation
  only — the live set is built from the DTG table).
- **`tests/test_discipline_display_names.py`** — rewritten for the 25-canon
  (count 29→25, merge/remove absences, merged-id resolution, overlay corrections).

---

## 4. Code / tests

`python -m pytest etl/tests/test_discipline_canon.py tests/test_discipline_display_names.py`
→ **32 passed** (in-container, `pip install pytest openpyxl`). The canon tests
run the real extractors over the xlsx (slow, ~2–3 min; no DB).

The **main app suite was not re-run** for this work — the canon tests live in
`etl/tests/` and the app-suite impact is limited to `discipline_display_names.py`
(re-export, API unchanged) and the `layer2d` doc-constant. DB-backed tests and
the full ETL (`etl/layer0/run.py`) are **not runnable in-container** (no
`DATABASE_URL`); validated against the source workbook instead. Confirm the
canonical-env app-suite count on next deploy.

---

## 5. Manual verification owed (Andy's hands)

Appended to `CARRY_FORWARD.md` as the **Discipline canon (2026-05-25)** entry.
The migration + first loader pass were already run after #166; what remains is a
**re-run to apply #167** (composite-share fix + Swimrun). No new migration —
#167 is code-only.

```bash
git checkout main && git pull          # both #166 + #167
set -a; . ./.env; set +a               # DATABASE_URL → Neon
python -m etl.layer0.run --version-tag 1.3.1
```

Confirm `discipline_canon: N rows, N PASS, 0 ERROR`. Spot-checks (Neon SQL):
- Triathlon `sport_discipline_map`: D-006 carries the bike `race_time_pct`,
  **D-007 = 0** (share on the primary leg only).
- Swimrun `sport_discipline_map`: maps to **D-004 (Swimming) + D-002 (Road
  Running)**; no D-001, no D-020.
- `layer0.disciplines` (non-superseded): **25 rows**; no D-005/D-016/D-020/D-023.

`sum_to_100: … 5 WARN` is expected/cosmetic (see §7 #11).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Re-run the loader (§5)** to push #167 into Neon, then the 3 spot-checks. This
stacks alongside the other owed Neon deploys already tracked in `CARRY_FORWARD.md`
(A1/A2/Slice-C `init_db.py` + the layer0 `run_owed_layer0_migrations.sql`).

### 6.2 Open pivots / residuals
- **`tests/test_layer2d.py` §13.7** uses `D-020` (now a removed discipline) as a
  *mock* fixture for the generic gap×HIGH-risk→HITL path. Still passes; re-point
  at `D-022`/`D-025` for realism if you touch that file. (Cleanup, not a blocker.)
- **`load_weight` ≈1.0 gate vs raw 0–100 scale** — `_compute_load_weight`
  (`layer2a/builder.py`) returns the raw `race_time_pct` midpoint (no
  normalization), yet `plan_create.py:172` checks the included sum is `≈1.0`.
  There is a normalization path not fully traced. The canon is now
  **weighting-neutral** for the composite sports (post == pre race-share totals,
  asserted in the tests), so it introduces no regression — but trace this before
  changing `_compute_load_weight` or the gate.
- **5 `sum_to_100` WARN sports** — cosmetic, decided to leave (see §7 #11).

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules (read first).
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep; reconcile any ❌ first.
6. **Test env:** deps not pre-installed in fresh containers — `pip install -r requirements.txt pytest` (or just `pytest openpyxl` for the canon tests) into a venv.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | **Canon lives at ETL time** in `etl/layer0/discipline_canon.py`, source xlsx untouched | this agent → Andy | Matches `sport_name_aliases`/`vocabulary_transforms`. A table `UPDATE` re-drifts on next ETL; the ETL resolves ids by name. |
| 2 | **Merge** D-005 (Pool Sprint) + D-016 (Swimming) → D-004 **"Swimming"** | Andy | One swim category; pool-sprint distinction dropped. |
| 3 | **Remove** D-020 Swimrun (→ a sport) and D-023 Ski Transitions (untracked) | Andy | Swimrun is swim+run, not its own discipline. |
| 4 | **Composite split** into atomic legs; **share on the primary leg only** | Andy ("yes fix it") | Splitting for skill/pairing is fine, but the legs are one physical race segment — duplicating `race_time_pct` double-counted Triathlon cycling / Off-Road paddle. |
| 5 | **Swimrun run leg = road (D-002)**, not the source's trail (D-001); sport-scoped override | Andy | Domain call. Scoped via `SPORT_DISCIPLINE_OVERRIDES` so D-001 stays trail everywhere else. |
| 6 | **Non-discipline rows** (Strength/Mobility/Weekly Total) → `discipline_id=NULL` + `row_category` | Andy | They aren't disciplines; stop them masquerading under a dash id. |
| 7 | **Orphans dropped** (Portage Running, Technical Scrambling `D-014 (Ref)`) | Andy | Not real disciplines. |
| 8 | Name reversions kept: **D-025 "Fencing"**, **D-029 "Rifle Shooting"** | Andy | Reverted my proposed "Épée"/"Biathlon" qualifiers. |
| 9 | Name corrections: **D-021 "Uphill Skinning"**, **D-022 "Alpine Descent"** | Andy | Overlay had drifted to "Ski Touring"/"Alpine Skiing". |
| 10 | Migration = schema + abort-proof retire; **ETL re-run is the authoritative data step** | this agent | The store is ETL-versioned; in-place renames risk `UNIQUE(sport,name)` collisions. |
| 11 | **Leave the 5 `sum_to_100` WARNs** (Swimrun, Canoe/Kayak Ultra, Marathon (Mtn), Skyrunning, Ultra Trail) | Andy ("check plan-gen first") | Those phase-load %s become **LLM prompt guidance bands** (`per_phase._format_phase_load_bands`), not arithmetic. Variant-merge/removal collapse leaves stacks a few points under 100 — cosmetic. |

---

## 8. Session-end verification (Rule #10)

Anchors verified on `main` (post-merge). Re-grep from repo root:

| Check | Result |
|---|---|
| `etl/layer0/discipline_canon.py` exists; `grep -c "D-0" → 25` canonical name entries; `SPORT_DISCIPLINE_OVERRIDES` has `("Swimrun","D-001"): "D-002"` | ✅ |
| `grep -n "share_fields" etl/layer0/run.py` → present on the `sport_discipline_map` + `phase_load_allocation` calls; `sport_field="sport_name"` on both | ✅ |
| `grep -n "row_category" etl/layer0/schema.sql` → column on `phase_load_allocation`; `etl/layer0/run.py pl_columns` includes it | ✅ |
| `discipline_display_names.py` imports `CANONICAL_NAMES as DISCIPLINE_DISPLAY_NAMES` from `etl.layer0.discipline_canon` (no hand-maintained dict) | ✅ |
| `layer2d/builder.py` `_KNOWN_GAP_DISCIPLINES == frozenset({"D-022","D-025"})` (no D-020) | ✅ |
| `etl/layer0/validation/discipline_canon_check.py` exists; wired in `run.py` validation phase + report extras | ✅ |
| `aidstation-sources/migrations/migrate_discipline_canon_2026_05_25.sql` exists (ADD COLUMN + retire) | ✅ |
| `python -m pytest etl/tests/test_discipline_canon.py tests/test_discipline_display_names.py` | ✅ 32 passed (in-container) |
| Both PRs merged to `main` (#166 `5ddc0ac`, #167 `ee0756f`) | ✅ |

---

## 9. Files shipped this session

**Substantive (merged #166/#167):** `etl/layer0/discipline_canon.py` (new),
`etl/layer0/validation/discipline_canon_check.py` (new), `etl/layer0/run.py`,
`etl/layer0/schema.sql`, `discipline_display_names.py`, `layer2d/builder.py`.
**Tests:** `etl/tests/test_discipline_canon.py` (new),
`tests/test_discipline_display_names.py`.
**Migration:** `aidstation-sources/migrations/migrate_discipline_canon_2026_05_25.sql` (new).
**Bookkeeping (this PR):** this handoff; `CURRENT_STATE.md` pointer + focus +
layer-status note; `CARRY_FORWARD.md` owed-loader entry; `PR_Verification_Status.md` entry.

---

## 10. Carry-forward updates

- New **Discipline canon (2026-05-25)** entry in `CARRY_FORWARD.md` — the owed
  loader re-run (#167) + the 3 Neon spot-checks.
- The 5 `sum_to_100` WARNs are recorded as **cosmetic / no-action** (decision §7 #11).
- `PR_Verification_Status.md` gains the canon row (migration + first loader =
  done; #167 re-run = owed).

---

**End of handoff.**
