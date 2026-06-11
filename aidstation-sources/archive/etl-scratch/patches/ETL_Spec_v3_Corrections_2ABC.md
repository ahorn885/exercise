# ETL Spec v3 — Correction Batch: 2A + 2B + 2C + terrain_required

**Date:** 2026-05-09
**Applies to:** `Layer0_ETL_Spec_v3.md`
**Status:** Apply to spec at next revision pass (v4 or v3.1, whichever comes first).
**Session origin:** Layer 1 design — nodes 2A, 2B, 2C locked.

---

## §4.12 `layer0.exercises` — add terrain_required column

Add the following field to the exercises schema block, after `physical_proxies`:

```sql
terrain_required            TEXT[],   -- terrain tokens stripped from col 7 by
                                      -- vocabulary_transforms.py. NOT equipment.
                                      -- 2C annotates; Layer 4 cross-references
                                      -- against 2B terrain gap output.
```

**Full corrected CREATE TABLE block (add column only — rest unchanged):**

Between:
```sql
  physical_proxies            JSONB,                   -- [{id, name}, ...]
```
Insert:
```sql
  terrain_required            TEXT[],                  -- terrain access requirements;
                                                       -- not athlete equipment; not a
                                                       -- 2C filter input; Layer 4 uses
                                                       -- this with 2B output
```

**ETL derivation rule:** `vocabulary_transforms.split_equipment_column()` already
separates terrain tokens from equipment tokens. Update: instead of discarding terrain
tokens, write them to `terrain_required[]`. Situational tokens (`Darkness`,
`Group Riding Environment`, `Partner or Visual Cue`, `Tandem Partner`, `Team`) are
still discarded — they are neither terrain nor equipment.

**Null policy:** NULL is valid and common (most strength/plyometric exercises have
no terrain requirement). ETL writes `[]` or NULL consistently — downstream consumers
treat both as "no terrain requirement."

---

## §4 — Add terrain_gap_rules to table list

Between `§4.10 discipline_training_gaps` and `§4.11 sport_discipline_bridge`, add:

### 4.10a `layer0.terrain_gap_rules` — NEW (0C-v2.0-r2)

One row per (target terrain, proxy terrain) gap pair. 12 entries. Source: populated
by `populate_terrain_gap_rules.sql` (executed). Not extracted from xlsx — curated
directly by app team.

```sql
CREATE TABLE layer0.terrain_gap_rules (
  id                    SERIAL PRIMARY KEY,
  target_terrain_id     TEXT NOT NULL,     -- TRN-xxx from terrain_types
  target_terrain_name   TEXT NOT NULL,
  proxy_terrain_id      TEXT,              -- NULL = unbridgeable
  proxy_terrain_name    TEXT,
  proxy_fidelity        NUMERIC,           -- 0.0 – 1.0; NULL if proxy_terrain_id NULL
  gap_severity          TEXT NOT NULL,     -- 'low' / 'moderate' / 'high' / 'critical'
  adaptation_weeks      INTEGER,
  proxy_methods         TEXT[],
  uncoverable_stimulus  TEXT[],
  prescription_note     TEXT,
  coaching_flag         TEXT,

  etl_version           TEXT NOT NULL,
  etl_run_at            TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ,

  UNIQUE (target_terrain_id, proxy_terrain_id, etl_version)
);
```

**Status:** Table created and populated at `etl_version = '0C-v2.0-r2'`.
Scripts: `migrate_terrain_types.sql` + `populate_terrain_gap_rules.sql` — both
executed and idempotent.

---

## §8 Downstream prompt consumption — corrected entries

### Node 2A (Discipline Classifier)

| | Current (wrong) | Correct |
|---|---|---|
| Tables queried | `sports, sport_discipline_map, sport_discipline_bridge` | `sports, sport_discipline_map, phase_load_allocation, discipline_training_gaps` |

Notes:
- `sport_discipline_bridge` removed — 2C/exercise-pool territory, not discipline classification.
- `phase_load_allocation` added — source of `default_inclusion`, `is_conditional`, phase load bands.
- `discipline_training_gaps` added — 2A flags training gaps for confirmed disciplines so downstream nodes have early warning.
- `disciplines` table (ramp rates, injury patterns) — 2B/2D territory; not 2A.

---

### Node 2B (Terrain Classifier)

| | Current (wrong) | Correct |
|---|---|---|
| Tables queried | `terrain_types` | `terrain_types, terrain_gap_rules` |

Notes:
- Original entry treated 2B as a vocabulary lookup with no athlete inputs. Corrected:
  2B receives `race_terrain_ids` and `locale_terrain_ids` and computes gap set using
  `terrain_gap_rules`. The original function signature with no athlete data was a design gap.
- `terrain_gap_rules` is now also in §4 (see above).

---

### Node 2C (Equipment Mapper)

| | Current (wrong) | Correct |
|---|---|---|
| Tables queried | `equipment_items, sport_specific_gear_toggles, sport_exercise_map, exercises` | `sport_discipline_bridge, sport_exercise_map, exercises` |

Notes:
- `equipment_items` removed — vocabulary reference only. Athlete equipment arrives
  pre-canonical from §J structured input. No runtime lookup needed.
- `sport_specific_gear_toggles` removed — vocabulary reference only. Toggle matching
  is done by checking `exercises.equipment[]` for toggle tokens against the athlete's
  `gear_toggles` dict. The table itself is not queried at runtime.
- `sport_discipline_bridge` added — required join hop to translate discipline IDs
  (D-001 etc.) to `exercise_db_sport` names (the join key used by `sport_exercise_map`).
  Original §8 entry missed this entirely.

**Function signature correction** (update §5.2):

Current (wrong):
```python
q_layer2c_equipment_mapper_payload(framework_sport: str, disciplines: list[str], etl_version_set: dict) -> Layer2CPayload
```

Correct:
```python
q_layer2c_equipment_mapper_payload(
    framework_sport: str,
    disciplines: list[str],             # from 2A output — canonical discipline IDs
    equipment_available: list[str],     # from §J locale — canonical equipment tokens
    gear_toggles: dict[str, bool],      # from §J — 12 sport-specific readiness toggles
    etl_version_set: dict
) -> Layer2CPayload
```

Original signature was missing `equipment_available` and `gear_toggles`. Without them,
the function cannot perform equipment matching — which is its entire job.

**Tier 2 substitution — v1 contract note (add to §5 or a new §5.4):**

`equipment_substitutes_standard[]` and `equipment_substitutes_improvised[]` on
`layer0.exercises` are free text (exercise name strings, not EX IDs). Structured
resolution (find substitute → check its equipment against athlete inventory) requires
ETL normalization of these fields to EX IDs, which is deferred.

v1 contract: 2C passes raw substitute text through in the pool output. Layer 4's LLM
reads it as a coaching note and makes substitution decisions from natural language.
Future ETL enhancement: normalize substitute entries to EX IDs → enables clean
structured Tier 2 resolution at 2C.

---

## Open items updated

| # | Item | Status after this batch |
|---|---|---|
| A (prior) | §J Locale terrain access must use TRN-xxx IDs | Unchanged — still pending batch 4 |
| B (prior) | Rationale text quality in 2A output | Unchanged |
| C (prior) | Plan confirmation UI step design | Unchanged |
| D (prior) | ETL spec v3 §8 corrections for 2A + 2B | **RESOLVED — in this batch** |
| E (prior) | §H.2 Race Terrain Type must use TRN-xxx IDs | Unchanged |
| F (new) | terrain_required field on exercises | **RESOLVED — SQL migration written; vocab_transforms.py update noted** |
| G (new) | §J equipment_available must be canonical (no free text) | **RESOLVED — §J uses structured input; no change needed** |
| H (new) | Tier 2 resolution at 2C vs Layer 4 | **RESOLVED — v1: pass-through raw text; LLM handles. Future ETL normalization deferred.** |
| I (new) | ETL spec §8 corrections for 2C + terrain_required in §4 | **RESOLVED — in this batch** |

**New open item from this batch:**

| # | Item | Blocking? |
|---|---|---|
| J | `vocabulary_transforms.py` update: route terrain tokens to `terrain_required[]` instead of dropping. Companion to `migrate_exercises_terrain_required.sql`. Required before ETL re-run populates the new field correctly. | Blocks correct terrain annotation in exercise pool |
| K | Future ETL enhancement: normalize `equipment_substitutes_standard[]` and `equipment_substitutes_improvised[]` entries to EX IDs. Enables structured Tier 2 resolution at 2C. Not blocking v1. | Not blocking |

---

*Apply this correction batch when ETL spec v3 is revised to v3.1 or v4. Do not
overwrite v3 — supersede per established convention.*
