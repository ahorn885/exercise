# V5 Implementation — Data-Pipeline Campaign, Phase 2 Close-out: #269 — Remove the D-05 Aggregator Filter now that `0034` is Live — Closing Handoff (2026-06-30)

**Branch:** `claude/data-pipeline-phase-3-6-uxcpv3` (fresh off `main`)
**Commit:** `fca0974`
**PR:** not yet opened — pushed; opens + auto-merges (merge commit) on Andy's go.
**Campaign kickoff:** `handoffs/DataPipeline_Phase1-2_Done_Phase3-6_Kickoff_Handoff.md`
**Issues:** [#269](https://github.com/ahorn885/exercise/issues/269) (closes on merge), epic [#261](https://github.com/ahorn885/exercise/issues/261) (closes once #269 lands), epic [#228](https://github.com/ahorn885/exercise/issues/228) (tracking)

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` ran clean (no ❌): predecessor §6 anchor table from the #304 Part B handoff all verified, backlog pointer intact, working tree clean. Branch was at `origin/main` HEAD (`894114f`, the #1073 merge) — correct per the campaign kickoff's "restart the phase branch from `origin/main` after #1069 merges." `#1069` (Phases 1–2) confirmed merged into `main` (commit `f052226`).

**Precondition check for #269 (the kickoff's "do first"):**
- **Andy: "Prod: 0034 applied."**
- Nightly `layer0-validate-live` is **green on `main`, 2026-06-30 10:31Z** (via `actions_list`). Since #1069 (carrying the new `phase_load_allocation_aggregators` gate check) is merged, a green live-validate run = prod has `0034` applied and **0 active aggregator rows**.
- Both safety preconditions from the kickoff §"IMMEDIATE FOLLOW-UP" are met → safe to remove the filter. (The kickoff's explicit guard: *do not remove the filter before `0034` is live* — satisfied.)

---

## 2. What shipped — #269 close-out (aggregator-filter removal)

Migration `0034_supersede_phase_load_allocation_aggregators.sql` retires the `WEEKLY TOTAL TARGET` aggregator rows at the source, so the defensive query-side filter and its matching validation exemption are now dead and removed:

- **`layer2a/builder.py`** — dropped `AND pla.discipline_name NOT LIKE '%%WEEKLY TOTAL%%'` from `_load_disciplines`' PLA `LEFT JOIN`; rewrote the module-docstring D-05 paragraph to mark it resolved (the prior text said "kept as belt-and-suspenders until 0034 confirmed").
- **`etl/layer0/validation/default_inclusion.py`** — dropped the `if disc and "WEEKLY TOTAL TARGET" in str(disc).upper(): continue` exemption. Superseded rows are already excluded by the query's `WHERE superseded_at IS NULL`, so the exemption was dead. Docstring updated.
- **`tests/test_layer2a.py`** — dropped the `assert "NOT LIKE '%%WEEKLY TOTAL%%'" in sql` assertion from the call-shape test, and removed the whole `TestLoadDisciplinesPercentEscape` class. That class guarded the psycopg2 `%%`-escape of the LIKE pattern; with the filter gone there is **no `%` left in the query at all**, so the escape concern is moot, not merely relocated (verified: the filter was the only `%` in the `_load_disciplines` SQL).
- **`specs/Layer2A_Spec.md`** — D-05 marked resolved in: §5.2 SQL block (filter line removed), §5.2 key-points list, §6 drift table (`✅ Resolved (#269)`), open-item 2A-4 (`✅ Done`), and the §gut-check bullet.
- **`specs/Control_Spec_v8.md`** — §8.2 "Standing rules": the D-05 entry is rewritten as **RESOLVED / rule withdrawn** (the former "every query touching `phase_load_allocation` MUST carry the filter" rule is gone — regression is now guarded by the gate check, so no query-side filter is owed). The §gut-check standing-rules bullet de-lists the D-05 filter.

**Scope:** the kickoff claimed the filter was "required for 2D and 2E and Layer 4" — **verified false against the code**: the `NOT LIKE '%WEEKLY TOTAL%'` filter lived **only** at `layer2a/builder.py`. 2D/2E/Layer4 read different tables (`phase_load_weekly_totals` etc.) or don't join PLA. So this is a single-call-site removal. Everything else matching `WEEKLY TOTAL` in the tree is legitimate and untouched: the xlsx extractor that *parses* the aggregator row into `phase_load_weekly_totals`, the `discipline_canon` category constant, the `phase_load_allocation_aggregators` gate check, and the `phase_load_weekly_totals` reader comment in `layer4/context.py`.

---

## 3. Verification

- Full suite: **4104 passed / 30 skipped** (`PYTHONPATH=. python -m pytest tests/ etl/tests/ -q`). The 3 warnings are the pre-existing #217 Layer3B `evidence_basis` ones — unrelated.
- `validate_layer0` CHECKS count **unchanged at 13** — I edited a check body, not the registry, so the `test_validate_layer0.py` `len(CHECKS)` guard is untouched.
- Behavior-preserving: prod already has 0 active aggregator rows post-`0034` (the gate check confirms it), so removing the filter changes no served output.

---

## 4. ⚠️ Migration-number collision (flagged — not blocking)

Two `0034_*.sql` files now coexist on `main`:
- `0034_supersede_phase_load_allocation_aggregators.sql` (#1069, this data-pipeline track)
- `0034_reclassify_gear_out_of_location_equipment.sql` (#1071, the parallel locations-gear track)

Two PRs branched off `main` independently and each grabbed `0034`. **Functionally fine** — the apply ledger (`_apply_ledger.sql` → `layer0._applied_migrations`) is keyed by **filename**, so both apply and neither re-runs; the `layer0-gate` applies all `etl/migrations/layer0/*` in sorted order (the gear file sorts first). But the kickoff's "next is `0035`" numbering is now muddied. **Recommendation for Phase 3:** take `0036` for the `TRN-021` terrain migration (skip `0035` to leave an unambiguous gap), or renumber. Worth a one-line note to Andy. *(Did the gear `0034` also get applied to prod? Separate track — not verified here; flagged for the gear-track owner.)*

---

## 5. NEXT — Phase 3: #340 off-trail / trackless terrain

Per the campaign kickoff (decision already locked, no stop-and-ask owed):
- New migration (**use `0036`**, not `0035` — see §4) inserting `TRN-021` "Off-Trail / Trackless" into `layer0.terrain_types` + proxy rows in `layer0.terrain_gap_rules`. First confirm no existing terrain already covers the trackless stimulus (no-padding rule).
- Attach to Trail Running (D-001), Trekking (D-003), Mountain Running (D-024), Mountaineering (D-018) via `_DISCIPLINE_REQUIRED_TERRAINS` in `layer4/session_feasibility.py` (~63–87).
- `terrain_types` is already in family `0C`; the gate's `terrain_types` check covers format/uniqueness.
- Its own PR. Then Phase 4 (#229 + #233), Phase 5 (#240 injury), Phase 6 (close epics #261 / #228).

---

## 6. Bookkeeping (Rule #10)

### §6 anchor table (Rule #10 — next session's Rule #9 input)

| Claim | File | Anchor / check |
|---|---|---|
| D-05 filter gone from PLA join | `layer2a/builder.py` | `grep -c "WEEKLY TOTAL" layer2a/builder.py` → 1 (the docstring mention only; no `NOT LIKE`) |
| aggregator exemption gone | `etl/layer0/validation/default_inclusion.py` | `grep -c "WEEKLY TOTAL TARGET" default_inclusion.py` → 1 (docstring only; no `if … continue`) |
| filter test removed | `tests/test_layer2a.py` | `grep -c "WEEKLY TOTAL\|PercentEscape" tests/test_layer2a.py` → 0 |
| D-05 resolved in spec | `specs/Layer2A_Spec.md` | `grep "Resolved (#269)" specs/Layer2A_Spec.md` present |
| standing rule withdrawn | `specs/Control_Spec_v8.md` | §8.2 D-05 bullet contains "RESOLVED (#269" / "withdrawn" |
| suite green | `tests/` + `etl/tests/` | `PYTHONPATH=. python -m pytest tests/ etl/tests/ -q` → 4104 passed / 30 skipped |
| gate registry intact | `etl/layer0/validate_layer0.py` | `validate_layer0` CHECKS count == 13 |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (data-pipeline campaign entry)
4. This handoff + the campaign kickoff `handoffs/DataPipeline_Phase1-2_Done_Phase3-6_Kickoff_Handoff.md`
5. `./scripts/verify-handoff.sh` — automated anchor sweep

**PR state:** not yet opened. Per the project PR-gated rule (Andy 2026-06-19/23): pushed + bookkept; **wait for Andy's "open it."** On his go: open ready (not draft) + `enable_pr_auto_merge` (merge commit). Then close #269 (`completed`, ref the merge) and close epic #261 (only open child was #269); comment on #228 per kickoff §Phase 6.
