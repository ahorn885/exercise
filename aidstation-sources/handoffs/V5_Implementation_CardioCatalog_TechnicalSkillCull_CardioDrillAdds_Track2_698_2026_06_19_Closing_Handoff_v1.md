# #698 Track 2 — Technical/Skill cull (0017) + evidence-based cardio adds (0018) — Closing Handoff

**Session:** Data/ETL. "Where are we at?" → audited the full skill/drill catalog, Andy ratified an aggressive cull (keep 8 of 55) **plus** three evidence-based cardio additions after a deep-research pass. Shipped both as Layer 0 migrations, gate-validated locally.
**Date:** 2026-06-19
**Predecessor handoff:** `handoffs/V5_Design_CardioDrillsPool_TechnicalSkillCull_Track2_PartB_3aAudit_698_2026_06_19_Closing_Handoff_v1.md` (the corrected §3a audit basis)
**Branch/PRs:** `claude/kind-ptolemy-lv9b10`. PR [#745](https://github.com/ahorn885/exercise/pull/745) MERGED (full-catalog audit doc) · PR [#748](https://github.com/ahorn885/exercise/pull/748) MERGED (EX290–292 PROPOSED design doc) · PR [#750](https://github.com/ahorn885/exercise/pull/750) (migrations `0017` + `0018`).

---

## 1. What happened (in order)

1. **Reproduced the authoritative Layer 0 state** — baseline `etl/output/layer0_etl_v1.8.0.sql` + migrations `0006–0016` applied in a throwaway local Postgres (the CI `layer0-gate` recipe; Neon egress is blocked from the container). Dumped the **55 active `Technical / Skill` rows** (the set 0009/#644 culled 10 from) with footprint (#sports prescribing) + inbound-reference (progression/regression/physical_proxies) cost → committed as the audit artifact (PR #745, on main).
2. **Andy ratified an aggressive cull (AskUserQuestion):** keep **8**, retire **47**. Keeps = the physically-trainable transition/carry/standalone drills: **EX070, EX144, EX163, EX170, EX175, EX176, EX183, EX196**.
3. **Surfaced the blast radius before building** (read-only PG analysis): the cull supersedes **104 `sport_exercise_map` rows across 30 sports** and **zeroes Technical/Skill coverage for 17 paddle/climb/snow/pure-run disciplines**; and **7 surviving rows** reference a culled id (3 inside the keeps — EX170/EX176/EX183 — + EX173/EX201/EX203/EX288). Andy confirmed **proceed, eyes-open**.
4. **Andy then asked to also examine evidence-based ADDITIONS** "of these natures" (cardio), noting the keeps skew transition-conditional. Gap analysis (intensity × modality) of the 13-row cardio pool found three non-duplicate gaps.
5. **Deep-research evidence pass** (5-angle fan-out: VO2 run intervals · hill-vs-flat stimulus · swim CSS · bike over-unders · intensity-distribution). All five corroborated; **WebFetch was 403-blocked across academic hosts**, so figures are WebSearch extracts of the cited primaries (flagged for full-text re-verification). Specced three ratifiable entries → committed as the design doc (PR #748, on main).
6. **Andy ratified all three additions** (multiSelect) and that the **cull was un-held** — ship cull + adds as one coherent reshape.
7. **Wrote both migrations, validated locally, shipped** (PR #750).

## 2. The two migrations

**`etl/migrations/layer0/0017_cull_technical_skill_to_transition_keeps.sql`** — retire 47, keep 8 (Technical/Skill **55 → 8**).
- Supersede the 47 exercises + their 104 `sport_exercise_map` rows (supersede-only, history preserved).
- **Repoint the 7 surviving rows** that referenced a culled id, generically: null dangling `progression`/`regression` (+ name), strip culled `physical_proxies` elements (order preserved); re-insert at **`0B-v1.6.15`** (serving-relevant edit, 0009/0016 pattern). EX170 regr→null; EX176 proxy EX180→stripped; EX183 prog EX051+regr EX118+proxy EX118→nulled/stripped; EX173/EX201 prog→null; EX203 regr→null; EX288 regr EX113+proxy EX113→nulled/stripped.
- Atomic verify DO-block (culled-inactive; **exercises-FK integrity** — no active row references a culled id; no active SEM maps one; exactly 7 survivors at 0B-v1.6.15; 8 keeps active; T/S count = 8). Idempotent.

**`etl/migrations/layer0/0018_add_evidence_based_cardio_drills.sql`** — add EX290–292 (Interval/Tempo **9 → 12**), at **`0B-v1.6.16`**.
- **EX290 Flat VO2max Run Intervals** (RCT/crossover-backed; regr→EX178; 12 sport-maps).
- **EX291 Swim CSS / Threshold Intervals** (validated concept, MLSS-overestimate caveat noted; regr→EX126; 3 sport-maps).
- **EX292 Bike Over-Under Intervals** (mechanism + practitioner consensus, **no RCT** — ratified eyes-open; regr→EX073, prog→EX074; 8 sport-maps).
- + 23 `sport_exercise_map` rows. **No vocab padding** (every movement_pattern/equipment/terrain/priority token reuses existing vocab; `vocab_alignment` clean). Atomic verify (3 active at 0B-v1.6.16; new rows' FK targets active; 23 SEM rows; I/T = 12). Idempotent.

Independent of 0017 (no new row references a culled id — every FK target survives the cull).

## 3. Ratified decisions (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| U-1 | Technical/Skill cull scope | **Keep 8 (EX070/144/163/170/175/176/183/196), retire 47** |
| U-2 | Coverage cliff (17 sports → 0 T/S) | **Proceed eyes-open** — those sports keep their I/T + A/E drills; EX290/291 refill run/swim |
| U-3 | Dangling refs in survivors | **Null the broken links** (rows stand alone) |
| U-4 | Evidence-based additions to research+spec | **All three** (VO2 run / swim CSS / bike over-unders) |
| U-5 | Sequencing | **Hold cull, settle adds first → ship both together** |
| U-6 | Add which (post-research) | **All three ratified**, incl. EX292 over-unders despite its consensus-only (non-RCT) tier |

## 4. Validation

- Reproduced the full `layer0-gate` recipe locally (baseline `v1.8.0` + migrations `0006`–`0018` in a throwaway Postgres, postgres user, SQL_ASCII db + `client_encoding=utf8`):
  - Both atomic verify DO-blocks pass; **re-apply of 0017 + 0018 is a clean no-op** (idempotent).
  - `python -m etl.layer0.validate_layer0` → **`RESULT: PASS`** — all checks clean incl. **`exercises_fk` 0 violations** (dangling refs cleanly nulled) and **`vocab_alignment` 0** (no vocab padding); `sum_to_100` is the pre-existing 5-row waiver.
  - Final state: Technical/Skill **8**, Interval/Tempo **12**; EX290/291/292 present with 12/3/8 sport-maps; survivor proxies correctly stripped (EX176→`[]`, EX183 kept EX085, EX288 kept EX100).
- Data-only; **no public-schema DDL, no `LAYER4_PROMPT_REVISION` bump** (cache rides the 0B digest, same as 0007/0008/0009).

## 5. Manual verification owed (Andy — container can't reach Neon)

- **PROD APPLICATION (the one required action):** after #750 merges, trigger the **`layer0-apply`** Action (one-tap approve the `production` environment) to apply `0017` + `0018` to live Neon. Idempotent; safe to re-run.
- **Post-apply live-verify** (`neon-query`): `SELECT exercise_type, count(*) FROM layer0.exercises WHERE superseded_at IS NULL AND exercise_type IN ('Technical / Skill','Interval / Tempo') GROUP BY 1;` → expect T/S = 8, I/T = 12; and EX290/EX291/EX292 active at `0B-v1.6.16`.
- Carried, unchanged: post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #681 §4 Slice 2c indoor-machine live-verify; #732 parked.

## 6. Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **Apply 0017+0018 to prod** via `layer0-apply` (Andy one-tap), then the live-verify above. **Until applied, the catalog reshape is in-repo only.**
2. **Part A — the `cardio_drills` pool** (the original #698 Track 2 goal, now unblocked): A1 `payload.py` `CardioDrill` + `maxItems:1` → A2 `per_phase.py` pool+prompt + `hashing.py` `LAYER4_PROMPT_REVISION "10"→"11"` (prompt ratified first, Trigger #1) → A3 `validator.py` + render. **Design note carried forward:** the pool selector must **gate transition drills on a multi-sport-adjacency signal** (5 of the 8 keeps — bricks/transitions/carries — only apply when the plan schedules the two requisite sports back-to-back; otherwise it can surface "Brick Run" on a single-sport day).
3. **Data-quality nit (deferred):** EX184 (culled) is gone, but its old coaching cue referenced "MTB descending (EX052)" where EX052 is Downhill *Running* — a stale-cross-ref class worth a pass if other rows share it.
4. **Deferred:** the 13 cardio drills could later get more additions if a gap appears (over-distance/anaerobic), but the strict no-padding bar applies.

## 7. Provenance / evidence caveat (load-bearing for Part A copy)

The three additions' numeric prescriptions (interval durations, %FTP, CSS formula, etc.) are **WebSearch-extracted from the cited primaries, not full-text-fetched** (WebFetch 403-blocked). The design doc `designs/CardioDrill_EvidenceBased_Additions_EX290-292_2026_06_19.md` flags this per-claim. Before any of these numbers surface in **user-facing coaching copy**, re-verify against the primary PDFs (Billat/Daniels for EX290; Wakayoshi/Dekerle for EX291; the over-under consensus sources for EX292). Evidence tiers: EX290 strong (RCT/crossover) · EX291 good (validated concept) · EX292 weakest (mechanism + consensus, no RCT).

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Cull migration | `etl/migrations/layer0/0017_cull_technical_skill_to_transition_keeps.sql` | `_cull_exercises` 47 ids; reinsert at `'0B-v1.6.15'`; verify `expected 8 active Technical/Skill`; 7 repointed survivors |
| Adds migration | `etl/migrations/layer0/0018_add_evidence_based_cardio_drills.sql` | `EX290`/`EX291`/`EX292` inserts at `'0B-v1.6.16'`; 23 `sport_exercise_map` rows; verify `expected 12 active Interval/Tempo` |
| Full-catalog audit | `aidstation-sources/audits/TechnicalSkill_FullCatalog_Audit_55rows_2026_06_19.md` | 55 active T/S rows, footprint + InRef columns (on main via #745) |
| Additions design + citations | `aidstation-sources/designs/CardioDrill_EvidenceBased_Additions_EX290-292_2026_06_19.md` | EX290–292 schema fields + evidence tiers + the WebFetch-403 caveat (on main via #748) |
| Gate (local) | `etl/layer0/validate_layer0.py` | `python -m etl.layer0.validate_layer0` → `RESULT: PASS`; `exercises_fk` + `vocab_alignment` 0 violations |
| PR / issues | #750 (migrations); #698 (open, commented) | — |

## 9. Carry-forward

- **The catalog reshape is in-repo (PR #750) but NOT live until `layer0-apply` runs** — the green local gate + clean anchors do not prove prod applied it (the standing Rule #9/#10 lesson). Prod proof = a read-only `neon-query`.
- **Active Layer 0 totals shift:** Technical/Skill 55 → 8; Interval/Tempo 9 → 12; net active exercises −44. Latest `0B` versions: survivors `0B-v1.6.15`, new drills `0B-v1.6.16`.
- **Part A (cardio_drills pool) is now unblocked** and is the natural next slice — carry the transition-drill multi-sport-adjacency gating note into its design.
