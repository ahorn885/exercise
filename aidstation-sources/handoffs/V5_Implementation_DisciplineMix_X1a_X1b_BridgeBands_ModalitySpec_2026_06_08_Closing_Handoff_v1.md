# V5 Implementation — Discipline Mix architecture: X1a shipped (bridge bands rewrite) + X1b specced (modality groups)

**Date:** 2026-06-07/08
**Branch:** `claude/jolly-mayer-a0K3Q`
**PR:** #475 (squash-merged to `main`)
**Issues:** #476 (D-007 row cleanup, Tier-3 cleanup), #477 (Endurance Cycling discipline-ID variant split, Tier-3 schema bug). Both deferred — folded into a future vocabulary-canon slice.
**Live cone-cache invalidation:** `etl_version_set` flipped 1.3.1 → 1.4.0; next plan-gen cold-rebuilds the cone.

---

## ⚡ Diagnostic token (read first — every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```

`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` — WebFetch/curl 403 (Vercel deployment protection); fetch via the **Vercel MCP `web_fetch_vercel_url`** tool. The token diag carries the control row + block-level `synthesis_metadata` + the stall traceback — NOT session bodies / per-rule validator severities (those need `/admin/plan/<id>/inspect`, admin-login, no token bypass).

---

## 1. What this session was

Monitored cold PGE plan **#61**. It reached `ready` — first cold AR plan to complete in ~15 sessions — but the **discipline mix was wrong**: Trail Running ~31% by hours, MTB ~16%, despite the race spec saying MTB 45% / TR 20%. Plus 5 separate quality issues Andy flagged from his read of the synthesized plan: same-discipline-twice on one day, same-modality on one day (trek+TR), no strength sessions, plan extends into race days, plan not appearing on `/plans` page.

Investigation root-caused the discipline-mix problem to **two compounding architectural defects**:

1. **The orchestrator strips race terrain's per-row `discipline_id` + `pct_of_race` at the 3B boundary** (`layer4/orchestrator.py:372-373` — `race_terrain: [e.terrain_id for e in target_race_event.race_terrain]`). Andy's careful per-discipline race-terrain rows (Road 10% MTB / Groomed 25% MTB / Technical 10% MTB / Groomed 20% TR / Flat-water 20% Packraft / Mountain-Alpine 15% Trekking) reach 3B as a flat `[TRN-002, TRN-004, ...]` list. The race spec has no path to influence load_weight.
2. **The AR bridge bands themselves are wrong for expedition AR** — `layer0.sport_discipline_bridge` says TR 15-25% and MTB 10-20% for Adventure Racing, inverted from reality. So even without (1), the bridge-driven discipline mix was TR-skewed. The midpoint of the AR bridge band IS the operational load_weight (per `layer2a/builder.py:_compute_load_weight` line 343 — `(low+high)/2`). Plan #61 inherited the wrong defaults.

Andy directed a 4-slice fix:
- **X1a** — rewrite the bridge bands for all 21 sports using authoritative governing-body data
- **X1b** — modality groups (a deterministic vocabulary of training-equivalent discipline groupings, fulfilling the deferred `BestFitModality_Spec_v4.md` §14 escape hatch)
- **X2** — wire `athlete_discipline_weighting` end-to-end (UI + orchestrator unpack)
- **X3 + X4** — race terrain → discipline_mix derivation + precedence merge at the orchestrator's 2A call site

**Precedence rule** (Andy 2026-06-07): race specifics (top) > athlete weighting (middle) > bridge defaults (bottom). Fall-through per-discipline.

**This session shipped X1a and specced X1b.** The empirical proof — a cold AR plan post-X1a that allocates MTB-dominant — is owed-Andy's-hands re-run gate.

## 2. Shipped (X1a — PR #475)

### 2.1 — `aidstation-sources/Bridge_Bands_Research_v1.md`

Research substrate. 21 framework_sports researched per the typical-race-format assumption per sport, with 1-3 cited sources each (governing body → peer-reviewed). Authoritative bodies cited: ARWS, World Triathlon, FIS, FRA, IBU, ICF, ISMF, ITRA, UIPM, World Athletics, WMRA, ÖTILLÖ, XTERRA, plus Frontiers / IRunFar / Marathon Handbook elite-split analyses. **Material corrections:** AR (MTB 10-20 → 35-55), XTERRA (MTB 40-55 → 55-70 per published 10/65/25 formula), Swimrun (swim 40-55 → 12-22 per ÖTILLÖ 12.8%/87.2%), Skimo (uphill 65-80 → 55-70), Modern Pentathlon (OCR 10-15 → 20-30 post-2024-obstacle), Aquabike (swim 10-20 → 25-35). Determinism note: bands document source uncertainty; runtime picks midpoint via `(low+high)/2`.

### 2.2 — `etl/sources/Sports_Framework_v12.xlsx`

Sheet 3 (Sport × Discipline Map) — 43 of 73 rows rewritten:
- 36 rows: the band corrections per the research doc.
- 7 rows: fixes for pre-existing v11 null-band rows (Mountain Running r40, Fell Running r44, Endurance Cycling r58-r62 — duration-descriptor text replaced by leading `95-100%` so the ETL regex picks it).
- Intentionally null left as-is: r25 (Ultramarathon Trail × Mountaineering EXCLUDED), r27 (Triathlon × D-007 TT Bike "see D-006" pointer) — filed for cleanup (#476).

Sheet 5 (Phase Load Allocation) NOT touched in this slice. Deferred to a follow-up research pass — per-phase bands depend on Sheet 3's relative shape settling first.

### 2.3 — `aidstation-sources/Bridge_Bands_Patch_Log_v1.md`

Per-row patch log: every row's old → new + rationale. 43 changes documented, 2 intentional null rows documented as "leave alone" with explanation.

### 2.4 — `etl/layer0/run.py`

`SPORTS_XLSX` constant flipped from v11 → v12. Provenance comment updated.

### 2.5 — `etl/layer0/db.py` (Andy's fix, mid-session)

Andy's first ETL run hit a UniqueViolation on `equipment_items_active_ci_name_idx` because `insert_versioned` was inserting new active rows BEFORE superseding prior versions, briefly creating two active rows with the same canonical_name. Fix: reorder DELETE → UPDATE supersede → INSERT, so two active rows of the same key never coexist within a transaction. Affects any future Layer 0 ETL with non-trivial vocabulary churn — not just v1.4.0.

### 2.6 — `etl/layer0/emit_sql.py` + `etl/output/layer0_etl_v1.4.0.sql`

Variant of `run.py` that reuses the same parsing + canon transforms but swaps the psycopg2 connection for a fake one that captures every SQL statement with parameters inlined. Output: a 3,884-line / 1.1 MB `.sql` file pastable into the Neon SQL editor. Regenerated post-Andy's db.py fix to ensure the file has the corrected ordering. Andy's live run used the Python path (`python -m etl.layer0.run`); the SQL file is repo-archival.

### 2.7 — `aidstation-sources/Modality_Group_Spec_v1.md` (X1b spec)

Modality groups — 14-section spec per the layer spec depth standard. Closes the deferred design from `BestFitModality_Spec_v4.md` §14 ("if craft selection proves unreliable LLM-side, Slice 5 can add a small deterministic craft-family proximity table without disturbing the rest"). Expands the original deferred design's "hint to LLM at synthesis time" purpose into a **first-class allocation primitive used at load_weight time**.

Key decisions captured (Andy 2026-06-07):
- **9 group vocabulary** (paddle_flatwater / paddle_whitewater / foot / bike_pavement / bike_offroad / snow_travel / snow_glide / climb / swim_openwater). One unified `foot` group containing TR + Road Running + Hiking/Trekking + Orienteering + sport-specific running disciplines. D-009 Packraft in both paddle groups. One unified `climb` group for rock + abseil + via ferrata.
- **§5.3 REDIRECT** confirmed — race tags kayak at 20%, athlete owns packraft → all 20% redirects to packraft training. `craft_substitution` coaching flag fires.
- **No partial coverage** — athlete weighting UI is all-or-nothing (cover all `included_discipline_ids` summing to 100, or no weighting at all). Eliminates the `athlete_weighting_incomplete` flag.
- **No orphans** — every discipline must belong to ≥1 group. ETL extractor raises on orphan. Eliminates the `modality_group_orphan` flag.
- **No race-wide rows** — race terrain rows with `discipline_id=None` are dropped from discipline-mix derivation. They still drive Layer 2B terrain coverage analysis.
- **Athlete-facing label kept internal** — `craft_substitution` flag is diagnostic, not surfaced to athlete UI.

Open items: only the bike D-006 forward-pointer (road / gravel discipline split — see #477).

### 2.8 — Issues filed

- **#476** — D-007 TT bike row in Triathlon is a documentation-only pointer to D-006. Tier-3 cleanup. Will fold into #477's vocabulary work (D-006c TT subsumes D-007).
- **#477** — Endurance Cycling bridge has duplicate `discipline_id` per framework_sport (D-006 in r58 + r59 as Road and Gravel format variants). Layer 2A's SELECT returns both; iteration creates duplicate Layer2ADiscipline objects; D-006 gets ~3x its intended share. Andy's decision: **Option 2 — split into format-specific discipline IDs** (D-006a / D-006b / D-006c / D-008a / D-008b). Deferred until after X1/X2/X3/X4 sequence ships.

### 2.9 — Andy-applied ETL on Neon

`python -m etl.layer0.run --version-tag 1.4.0` succeeded on Andy's local machine (Windows / `C:\Users\Mar43\exercise`). Active versions verified:

| Table | Active version |
|---|---|
| `layer0.body_parts` | 0C-v1.4.0 (54) |
| `layer0.equipment_items` | 0C-v1.4.0 (121) + unchanged 0A/0B legacy rows |
| `layer0.sports` | 0A-v1.4.0 (36) |
| `layer0.exercises` | 0B-v1.4.0 (211) |

Validation passed with expected WARNs (5 sports' phase loads not summing to 100; 1 vocab/parse warning). Report at `etl/reports/run-1.4.0-20260608-025453.md` on Andy's local.

## 3. Stop-and-asks this session

- **(Trigger #3, cross-layer surface change)** modality-group design — Andy chose: 9 groups, `foot` unified, packraft in both paddle groups, single `climb` group, no orphans / no partial / no race-wide / REDIRECT semantics. Specced in `Modality_Group_Spec_v1.md` before implementation.
- **(Trigger #5, architectural alternatives)** X1b "OR feature" placement — Andy chose Layer 2A allocation (the load_weight pool) over Layer 2C equipment substitution (which already exists). The 2A path is the right home because race-spec for kayak is a load-allocation question, not an equipment-availability question.
- **(Trigger #5)** Bridge fix shape — Andy chose Option (a) "typical AR" single standard, not duration-format splits. Athlete inputs drive nuance, not the bridge itself.
- **(Trigger #5)** Athlete weighting fate — Andy chose Wire, not Remove. Schema half-built already; UI + orchestrator wiring will complete the half-built feature (X2 slice).
- **(Trigger #5)** Endurance Cycling duplicate-discipline_id fix shape (#477) — Andy chose Option 2 (split into format-specific discipline IDs). Deferred to its own slice.

## 4. Owed

1. **The cold AR plan re-run is Andy's-hands** (needs the merge → prod deploy, then trigger a cold plan). Generation is behind the login wall, I can't trigger it. **Win condition:** in `/admin/plan/<id>/diag`, the bridge midpoints land as `D-008 MTB = 45` (was 15) → plan output should be MTB-dominant. With X3 race-terrain wiring still owed, the race spec doesn't yet override the bridge — but the new AR bridge bands are close enough to Andy's race spec (45% MTB / ~35 trek+TR / ~17.5 paddle midpoints) that the re-run NOW should already shift the allocation materially. Full race-spec override comes after X3.
2. **X1b implementation** — the modality_group tables + ETL extractor + Layer 2A pool-and-redistribute logic. Spec in §2.7. Implementation slice scope: 2 new Layer-0 tables (`modality_groups`, `discipline_modality_membership`), seed vocabulary, ETL extractor that reads from a new Excel sheet (Sheet 11), `_load_modality_groups` in 2A, group-aware `_compute_load_weight` algorithm per spec §5.1, ModalityGroupAllocation diagnostic for `synthesis_metadata`.
3. **X2 — athlete_discipline_weighting end-to-end.** UI under the Athlete tab in `templates/profile/edit.html`. Repo writes against `athlete_discipline_weighting`. Orchestrator unpack `Layer1Payload.training_history.discipline_weighting` → `athlete_discipline_overrides` kwarg at both 2A call sites (`layer4/orchestrator.py:270-275` and `:656-660`).
4. **X3 + X4 — race terrain → discipline_mix derivation + precedence merge.** Deterministic groupby-sum `discipline_mix[D] = Σ pct_of_race where discipline_id == D` from race_terrain (drop race-wide rows per spec §10). Merge function `_merge_discipline_overrides(race_mix, athlete_mix)` per the precedence rule. Pass merged dict as `athlete_discipline_overrides` to Layer 2A.
5. **Sheet 5 Phase Load Allocation research pass.** Deferred from this slice. Per-phase Base/Build/Peak/Taper bands need recalibration to match the new Sheet 3 race_time_pct anchors and sport-science taper/specificity literature.
6. **`/plans` page doesn't surface ready plans** (UI bug Andy flagged from plan #61 read). Separate UI fix; out of scope for X1-X4 series.
7. **Race-day session trim** (Andy's idea: post-synth clamp dropping any session with `scheduled_date >= event_date`). Separate slice from X1-X4.
8. **#476, #477** — vocabulary canon work, deferred until X1-X4 ships.

## 5. Next move

Tier order (CLAUDE.md 4-tier): **X1b implementation** is the gating item — completes the architectural foundation for X2/X3/X4. Then X2 (athlete UI wire). Then X3/X4 (race-spec merge). Then the empirical proof — cold AR plan run with race-spec MTB 45% landing as MTB-dominant allocation.

Parallel to the X-series: Sheet 5 phase-load research pass + the deferred quality issues from plan #61 (strength discipline miscoding, intra-day modality variety rule, race-day trim, `/plans` UI gap).

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (X1b-X4 + #476 + #477 + Sheet 5 + plan #61 quality issues)
4. This handoff (diag token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Bridge bands rewritten in v12 | `etl/sources/Sports_Framework_v12.xlsx` | `python -c "import openpyxl; wb=openpyxl.load_workbook('etl/sources/Sports_Framework_v12.xlsx',data_only=True); ws=wb['Sport × Discipline Map']; print([r[5].value for r in ws.iter_rows(min_row=2,max_row=7)])"` → AR rows 2-6 first %s should be `8-15`/`18-30`/`100`/`0-15`/`35-55` |
| ETL runner points at v12 | `etl/layer0/run.py` | `grep "SPORTS_XLSX = " etl/layer0/run.py` → `SOURCES / "Sports_Framework_v12.xlsx"` |
| ETL framework fix (supersede before insert) | `etl/layer0/db.py` | `grep -n "Supersede\|UPDATE.*superseded_at" etl/layer0/db.py` → UPDATE comes BEFORE the execute_values INSERT |
| Modality group spec written | `aidstation-sources/Modality_Group_Spec_v1.md` | file exists; `grep "^## " Modality_Group_Spec_v1.md` → 14 numbered sections |
| Bridge bands research doc | `aidstation-sources/Bridge_Bands_Research_v1.md` | file exists; `grep "Adventure Racing" Bridge_Bands_Research_v1.md` → "MTB 35-55" entry |
| Bridge bands patch log | `aidstation-sources/Bridge_Bands_Patch_Log_v1.md` | file exists; `grep "43 rows changed" Bridge_Bands_Patch_Log_v1.md` |
| SQL emitter + output | `etl/layer0/emit_sql.py` + `etl/output/layer0_etl_v1.4.0.sql` | both exist; SQL file lines ~3884; `grep "Adventure Racing','D-008','Mountain Biking'" etl/output/layer0_etl_v1.4.0.sql` → `35.0,55.0` literal |
| Neon at 0A-v1.4.0 (Andy-verified) | n/a | Andy's local PowerShell session showed `layer0.sports active: [('0A-v1.4.0', 36)]` and `layer0.exercises active: [('0B-v1.4.0', 211)]` |
| Issues filed | GitHub | #476 (D-007 cleanup), #477 (Endurance Cycling discipline-ID variant split) — both OPEN |

## 7. Mechanically-applicable deferred edits

None for X1a (shipped). X1b implementation files when ready (next session):
- `etl/layer0/schema.sql` — add `modality_groups` + `discipline_modality_membership` table DDL (CREATE TABLE IF NOT EXISTS)
- `etl/layer0/extractors/sports_framework.py` — add `extract_modality_groups` + `extract_discipline_modality_membership` parsers reading from a new Sheet (Sports_Framework_v13 — "Modality Groups" sheet to be added)
- `etl/layer0/run.py` — call the new extractors in Phase 1 (after vocabularies); seed initial vocabulary
- `etl/layer0/validation/modality_group_orphan.py` — new validator that errors on any discipline not in `discipline_modality_membership`
- `layer2a/builder.py` — `_load_modality_groups(db, etl_version_0a)`; group-aware `_compute_load_weight` per Modality_Group_Spec §5.1 algorithm

## 8. Summary

X1a's two corrections (bridge bands per research + ETL framework supersede-before-insert) landed. Active Layer 0 etl_version is `0A-v1.4.0` / `0B-v1.4.0` / `0C-v1.4.0` on Neon. The AR bridge now reads MTB 35-55 (midpoint 45) vs the v11 MTB 10-20 (midpoint 15) — the smoking-gun fix for plan #61's TR-dominant allocation. X1b is fully specced; implementation is the next slice. The empirical proof — a cold AR plan that lands MTB-dominant — is the win condition gating X1b kickoff.

Also retired in this slice (Andy 2026-06-07): the "dead third path" of `athlete_discipline_weighting` (table exists, Layer 1 reads it, Layer 2A docstring claims to use it, but the orchestrator never passes it). X2 wires it properly with full UI + orchestrator unpack + all-or-nothing UI invariant.

*End of handoff.*
