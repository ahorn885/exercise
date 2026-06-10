# X1b.3b — Craft → Discipline Aliases + Substitution Filter — v1

Closes the X1b modality-group arc (after X1b.1 substrate, X1b.2 Layer 2A pooling,
X1b.3a Layer 2C flag). Implements `Modality_Group_Spec_v1.md` §6.

## Goal
Narrow the craft-substitution candidate set **deterministically** before the
Layer 4 LLM picks: an owned craft is offered as a training substitute for a race
discipline only if a discipline it aliases to shares a modality group with the
race discipline.

## Assumption check (Andy, 2026-06-10)
The old plan assumed the cycling split (#477) wasn't live and would map to
`D-006a/b`. **Verified false:** Vocabulary V1 (2026-06-08) already superseded
#477 by adding distinct IDs — `D-030 Gravel Cycling`, `D-031 Cross Country
Cycling`, `D-032 SUP`, `D-007 TT/Tri` — and `discipline_modality_membership`
already groups them (D-030 dual `bike_pavement`+`bike_offroad`, D-031
`bike_offroad`, D-032 `paddle_flatwater`). So X1b.3b does **no** split work — it
aliases onto the live IDs.

## Alias seed (Andy-ratified, many-to-many)
| craft slug | → disciplines |
|---|---|
| kayak | D-010 |
| canoe | D-011 |
| packraft | D-009 |
| road_bike | D-006 |
| gravel_bike | D-006, D-030, D-031 (road + gravel + XC) |
| mountain_bike | D-008, D-031 |
| cycling_trainer | D-006, D-007, D-008, D-030, D-031 (all bike) |

14 rows. Many-to-many → `UNIQUE(craft_name, discipline_id, etl_version)`.

## Changes
- **Source:** `Sports_Framework_v14.xlsx` gains a `Craft Discipline Aliases`
  sheet (added in place — additive, no consumer/test repoint; round-trip
  verified to leave the other sheets' extractor counts unchanged).
- **Schema:** `layer0.craft_discipline_aliases` (mirrors `modality_groups`).
- **Extractor:** `sports_framework.extract_craft_discipline_aliases` (validates
  `group_kind` ∈ closed enum; `[]` if sheet absent).
- **Runner:** Phase 2 insert, canon-filtered on `discipline_id`.
- **Emit:** `etl/output/layer0_etl_v1.6.6.sql` (auto-picked up by the runner path).
- **Consumer:** `resolve_training_substitution` gains `discipline_modality_groups`
  + `craft_discipline_aliases` kwargs; per craft-based discipline block, narrows
  candidates to same-group crafts, emitting `craft_substitution` (narrowed) /
  `craft_unavailable` (owns crafts, none in group). `craft_substitution` added to
  the `TrainingSubstitutionFlag` Literal.
- **Orchestrator:** `_q_modality_groups` + `_q_craft_discipline_aliases` readers
  (1 query each), threaded into the resolver call.

## Design notes
- **Craft-relevant guard:** the narrowing only fires on disciplines whose
  modality group is reachable from *some* craft in the **full** alias table
  (not just owned crafts) — so foot/swim/climb blocks pass through untouched
  (no spurious `craft_unavailable`), while a paddle-only athlete is still
  correctly `craft_unavailable` for a bike block.
- **Back-compat:** both maps absent/empty → pre-X1b.3b behavior (all owned
  crafts surfaced, no new flags). Guards the cone against an unapplied ETL.
- `cycling_trainer → all bike types` (Andy) — a smart trainer trains any bike
  discipline.

## Owed your hands
Apply `etl/output/layer0_etl_v1.6.6.sql` on Neon — single step. It runs
`CREATE TABLE IF NOT EXISTS layer0.craft_discipline_aliases` then inserts the 14
rows (0A-family); no pre-migration, no CI-name collision (new table).

## Coverage
6 substitution filter tests + 3 extractor tests; full suite green.
