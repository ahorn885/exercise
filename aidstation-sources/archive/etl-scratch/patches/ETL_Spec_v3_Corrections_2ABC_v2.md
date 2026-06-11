# ETL Spec v3 Corrections — Layers 2A/2B/2C

**Supersedes:** `ETL_Spec_v3_Corrections_2ABC.md` (v1, this session earlier)
**Status:** Ready to merge into `Layer0_ETL_Spec_v3.md`
**Scope:** Schema corrections, §8 consumer table corrections, function signatures, and Open Item resolutions discovered during Layer 1 Node 2A/2B/2C design.

---

## Summary of changes from v1 of this corrections doc

- **Open Item H** previously resolved as "pass-through to Layer 4 LLM as free text." **Now resolves structurally at 2C** because Open Item K is being completed in this session, producing the new `equipment_substitutes_structured` JSONB field. 2C does Tier 2 resolution against structured data — no LLM dependency for substitution.
- **Open Item K** previously deferred. **Now completed in this session.** Heuristic parser auto-classified all 510 substitute entries (154 exercises). Final breakdown: 199 equipment-tagged (39%), 282 improvised (55%), 13 both (improvised setup with specific equipment, e.g., hotel door-mount pull-up bar), 42 pure bodyweight variants (8%). Borderline cases listed in companion doc `K_borderline_cases_for_review.md`.

---

## §4.10a Add `terrain_gap_rules` table to schema spec

The `terrain_gap_rules` table was created and populated via `populate_terrain_gap_rules.sql` but never documented in the spec markdown. Add immediately after §4.10 `terrain_types`:

```markdown
### §4.10a terrain_gap_rules

| Column                | Type        | Notes |
|-----------------------|-------------|-------|
| terrain_required      | TEXT        | The terrain token an exercise wants (FK-conceptual to terrain_types.token) |
| terrain_available     | TEXT        | The terrain token the athlete has access to |
| satisfies             | BOOLEAN     | TRUE if available terrain satisfies required terrain |
| substitution_quality  | TEXT        | One of: 'exact', 'close', 'partial', 'unrelated' |
| notes                 | TEXT        | Coaching context for partial/close matches |

PK: (terrain_required, terrain_available)

Used by Layer 1 Node 2B (Terrain Mapper) to determine whether the athlete's
terrain access satisfies what each exercise requires. Populated by
populate_terrain_gap_rules.sql with curated coaching judgments
(e.g., "Trail" available + "Outdoor Hill" required = 'partial', not 'exact').
```

---

## §4.12 Add new fields to `exercises` table schema

Two columns added during Layer 1 design that need spec documentation:

```markdown
| Column                            | Type    | Notes |
|-----------------------------------|---------|-------|
| terrain_required                  | TEXT[]  | Terrain tokens the exercise needs (e.g., ['Pump Track'], ['Climbing Gym']). Populated by ETL via vocabulary_transforms.split_equipment_column() returning the second tuple element. Empty array for indoor/equipment-only exercises. |
| equipment_substitutes_structured  | JSONB   | Parsed structured form of equipment_substitutes_standard[] and equipment_substitutes_improvised[]. Schema: array of `{substitute_text, equipment_required, is_improvised}`. The `equipment_required` field uses **CNF (AND-OR) semantics**: `list[list[str]]` where outer list is OR (any group satisfies) and inner list is AND (all items in group required). Source of truth for Layer 1 Node 2C Tier 2 resolution. |
```

Schema migrations:
- `migrate_exercises_terrain_required.sql` (terrain_required column)
- `migrate_exercises_substitutes_structured.sql` (structured substitutes column)

Population:
- terrain_required: re-run ETL after applying `vocabulary_transforms_J_patch.md` to extract terrain tokens from col 7.
- equipment_substitutes_structured: run `populate_substitutes_structured.py` once after migration.

The original `equipment_substitutes_standard[]` and `equipment_substitutes_improvised[]` TEXT[] columns are retained as reference data. They are no longer the source of truth for 2C.

---

## §5.2 Layer 1 Node 2C function signature correction

Original spec showed:

```python
q_layer2c_equipment_mapper_payload(
    framework_sport: str,
    disciplines: list[str],
    etl_version_set: dict
) -> Layer2CPayload
```

This signature is missing the athlete's equipment context — 2C cannot perform its core job without it. Corrected signature:

```python
q_layer2c_equipment_mapper_payload(
    framework_sport: str,
    disciplines: list[str],            # from Node 2A output
    equipment_available: list[str],    # from §J locale equipment, canonical tokens
    gear_toggles: dict[str, bool],     # from §J, 12 readiness toggles
    etl_version_set: dict
) -> Layer2CPayload
```

---

## §5.2 Layer 1 Node 2C — internal logic spec

Replace the original 2C logic description with the following:

### Tables queried
- `layer0.sport_discipline_bridge` — discipline IDs → exercise_db_sport names
- `layer0.sport_exercise_map` — discipline-scoped exercise pool (joined to bridge output)
- `layer0.exercises` — equipment[], terrain_required[], equipment_substitutes_structured (JSONB)

### Tables NOT queried at runtime
- `layer0.equipment_items` — vocabulary reference for §J UI options only
- `layer0.sport_specific_gear_toggles` — vocabulary reference for §J UI only

### Equipment tier classification (per exercise)

For each candidate exercise from the discipline pool:

```
assumed_pass_set =
    assumed_universal_items
    ∪ equipment_available
    ∪ {gear toggle tokens where toggle is TRUE}

Tier 1 (direct pass):
  exercises.equipment[] ⊆ assumed_pass_set
  → exercise prescribed as written

Tier 2 (structured substitute available):
  EXISTS sub IN equipment_substitutes_structured WHERE
    (sub.equipment_required is empty AND sub.is_improvised = TRUE)
    OR
    EXISTS group IN sub.equipment_required WHERE group ⊆ assumed_pass_set
  → exercise prescribed using sub.substitute_text
  → first matching substitute wins (preference order: pure equipment match,
    then improvised setup with equipment, then improvised-only)

Tier 3 (improvised-only substitute):
  Subset of Tier 2 where the only matching substitutes have is_improvised = TRUE
  AND equipment_required is empty
  → flagged separately so Layer 4 can note "improvised setup required"

Tier 4 (physical proxy required):
  No substitute matches but exercises.physical_proxies[] is non-empty
  → return proxy EX IDs; Layer 4 prescribes a different exercise pattern

Blocked:
  None of the above → exercise excluded from pool with reason
```

**Note on AND-OR semantics:** `equipment_required` is `list[list[str]]` (CNF). Outer list is OR (any group satisfies); inner list is AND (all items in group must be in pool). Examples:
- `[["Dumbbell"]]` → needs Dumbbell
- `[["Dumbbell"], ["Kettlebell"]]` → needs DB OR KB
- `[["Stairs", "Backpack"], ["Stairs", "Weighted vest"]]` → needs Stairs + (Backpack OR Vest)

`is_improvised = TRUE` is no longer a bypass — it's a coaching signal indicating the substitute uses improvised setup or technique. Equipment requirements still apply unless `equipment_required` is empty.

### Output payload

```python
{
  "exercise_pool": [
    {
      "exercise_id": "EX001",
      "exercise_name": "Back Squat (Barbell)",
      "availability_tier": "tier_2",
      "tier_1_match": false,
      "tier_2_substitute": {
        "substitute_text": "Safety Bar Squat",
        "equipment_required": ["Safety squat bar"],
        "is_improvised": false
      },
      "tier_3_improvised_only": false,
      "tier_4_proxy_ids": null,
      "priority_by_sport": [
        {"sport": "Strength Training", "priority": 1},
        ...
      ],
      "highest_priority": 1,
      "terrain_required": [],            // annotation, not filter
      "gear_toggle_tokens": []
    },
    ...
  ],
  "pool_summary": {
    "total_candidates": 245,
    "tier_1": 87,
    "tier_2": 41,
    "tier_3": 14,
    "tier_4": 22,
    "blocked": 81
  },
  "assumed_universal_items": ["Bodyweight", "Floor", "Wall", ...]
}
```

### Layer-4 contract
2C annotates `terrain_required` but does NOT filter on it. Layer 4 cross-references 2B's terrain gap output with 2C's per-exercise `terrain_required` to make final inclusion calls.

### Invalidation triggers
- §J `equipment_available` changes
- §J `gear_toggles` changes
- 2A discipline list changes
- ETL version set changes (specifically: changes to `exercises`, `sport_exercise_map`, or `sport_discipline_bridge`)

NOT invalidated by: 2B terrain gap output, 2D injury filter, 2E fitness, schedule.

---

## §8 Consumer table corrections

The §8 consumer table maps tables to layer-1 nodes. Three corrections from the original v3 spec:

### 2A consumer entry — add `sport_discipline_bridge`
**Before:** `sports`, `disciplines`
**After:** `sports`, `disciplines`, `sport_discipline_bridge`

Reason: 2A needs the bridge to resolve framework_sport → constituent discipline IDs.

### 2B consumer entry — add `terrain_gap_rules`
**Before:** `terrain_types`
**After:** `terrain_types`, `terrain_gap_rules`

Reason: 2B uses gap rules to determine which exercises' terrain requirements are
satisfied by the athlete's terrain access (per §4.10a).

### 2C consumer entry — full revision
**Before:** `exercises`, `sport_exercise_map`
**After:** `exercises`, `sport_exercise_map`, `sport_discipline_bridge`

Reason:
- 2C needs the bridge to resolve discipline IDs to exercise_db_sport names.
- `equipment_items` and `sport_specific_gear_toggles` are vocabulary references for §J UI, not 2C runtime tables — explicitly listed as "NOT consumed at runtime" to prevent confusion.

---

## Open Item resolutions (final state)

| ID | Status        | Resolution |
|----|---------------|------------|
| F  | ✅ RESOLVED   | `terrain_required TEXT[]` column added to exercises. ETL routes terrain tokens from col 7 via `split_equipment_column()` returning a tuple. 2C annotates but does not filter; Layer 4 cross-references with 2B output. |
| G  | ✅ CLOSED     | Equipment options confirmed structured (no free text in §J). No work needed. |
| H  | ✅ RESOLVED   | **Structural resolution at 2C** using `equipment_substitutes_structured` JSONB. No LLM dependency for substitute reasoning. Tier 2 picks the first substitute whose `equipment_required ⊆ athlete pool` OR `is_improvised = TRUE`. |
| I  | ✅ RESOLVED   | This document (v2). All §4 / §5.2 / §8 corrections batched. |
| J  | ✅ RESOLVED   | `vocabulary_transforms_J_patch.md` — split_equipment_column() returns (equipment, terrain) tuple; situational tokens discarded. |
| K  | ✅ RESOLVED   | Heuristic parser produced 510 structured entries with 0 unresolved. 13 borderline cases flagged in `K_borderline_cases_for_review.md` for spot-check. |

---

## Run sequence (when ready, all files in etl/sources/)

```bash
# 1. Schema migrations
psql $DATABASE_URL -f etl/sources/migrate_exercises_terrain_required.sql
psql $DATABASE_URL -f etl/sources/migrate_exercises_substitutes_structured.sql

# 2. Apply J patch to etl/sources/vocabulary_transforms.py
#    (manual edit per vocabulary_transforms_J_patch.md)

# 3. Re-run ETL to populate terrain_required from existing source data
python etl/run_etl.py  # or whatever the existing runner is

# 4. Populate structured substitutes
DATABASE_URL=$DATABASE_URL python etl/sources/populate_substitutes_structured.py
```

Verification queries embedded in each migration's DO block run automatically.

---

## Vocabulary alignment confirmation

All `equipment_required[]` tokens emitted by the parser into `equipment_substitutes_structured` are now aligned with `layer0.equipment_items` canonical vocabulary, contingent on accepting the 11 new vocab entries proposed in `vocab_patch_K_new_entries.md`.

- 53 unique equipment tokens emitted across 510 substitute entries
- 42 align directly to existing Vocabulary_Audit_v2.md Section 3 entries
- 11 require new vocab entries (proposed in vocab patch)
- 0 orphan tokens after applying both

Parser-side normalizations baked in (no further spec changes needed):
- 8 simple renames (e.g., `Rack` → `Squat rack`, `TRX` → `TRX / suspension trainer`)
- 4 functional collapses to existing vocab (e.g., `Prowler` → `Weighted sled`)

## Future work (out of scope this session)

- **Future K extension:** Some bodyweight-bucket entries are borderline (e.g., "Goblet squat" classified as bodyweight but actually needs DB/KB load). Manual review needed — see `K_borderline_cases_for_review.md`.
- **Vocab v3 cut:** Once the 11 new entries are approved, formalize as Vocabulary_Audit_v3.md and re-populate `layer0.equipment_items`. Companion populate script not yet produced; can be bundled with the K migration sequence on request.
- **`Hyperextension bench` is currently collapsed to `Glute ham developer (GHD)`.** Functional but technically wrong. Future vocab expansion should split these into separate entries.
- **Team racing architecture:** Acknowledged gap, scoped out as long-term roadmap item.
