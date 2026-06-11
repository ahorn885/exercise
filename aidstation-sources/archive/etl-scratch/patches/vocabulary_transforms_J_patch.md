# vocabulary_transforms_J_patch.md

**Patch for:** `etl/sources/vocabulary_transforms.py`
**Resolves:** Open Item J (route terrain tokens to terrain_required[] instead of dropping)
**Companion to:** `migrate_exercises_terrain_required.sql`
**Run order:** Apply this patch BEFORE the next ETL re-run. The migration adds the
column; this patch populates it.

---

## Required changes

### 1. Add `TERRAIN_TOKENS` and `SITUATIONAL_TOKENS` constants near top of file

```python
# Terrain tokens that must be moved out of equipment[] into terrain_required[].
# Source: Vocabulary_Audit_v2.md §3 Terrain table.
TERRAIN_TOKENS = frozenset({
    # Foot terrains
    'Outdoor Hill', 'Steep Hill', 'Steep Mountain', 'Steep Track',
    'Trail', 'Flat Trail', 'Gravel or Dirt Trail',
    'Road', 'Descent Road', 'Gravel Road',
    # MTB-specific
    'Pump Track',
    # Water
    'Pool', 'Open Water', 'Open Water Body', 'Pool or Flat Water',
    'Open Water or Ocean', 'Ocean or Surf', 'Flat or Choppy Water',
    'Whitewater', 'Moving Water', 'River',
    # Snow
    'Snow Slope', 'Groomed Slope', 'Groomed Track', 'Deep Snow or Sand',
    # Rock / scrambling
    'Rocky Terrain', 'Boulders', 'Scree Field', 'Loose Rocky Slope',
    # Fell
    'Fell Terrain', 'Steep Grass', 'Moorland', 'Heather', 'Bog',
    # Climbing surfaces
    'Climb', 'Rock Wall', 'Climbing Gym',
    # Generic
    'Varied Terrain',
})

# Situational tokens — neither terrain nor equipment. Discarded entirely.
# These describe race conditions or training partners, not what the athlete
# needs to perform the exercise as written.
SITUATIONAL_TOKENS = frozenset({
    'Darkness',
    'Group Riding Environment',
    'Partner or Visual Cue', 'Tandem Partner', 'Team',
})
```

### 2. Update `split_equipment_column()` (or equivalent function)

**Before:**
```python
def split_equipment_column(raw: str) -> list[str]:
    """Parse col 7 Equipment string into canonical token list."""
    if not raw:
        return []
    tokens = [t.strip() for t in raw.split(',') if t.strip()]
    # Filter out terrain and situational tokens — they don't belong in equipment[]
    equipment = [
        t for t in tokens
        if t not in TERRAIN_TOKENS and t not in SITUATIONAL_TOKENS
    ]
    return equipment
```

**After:**
```python
def split_equipment_column(raw: str) -> tuple[list[str], list[str]]:
    """Parse col 7 Equipment string into (equipment_tokens, terrain_tokens).

    Returns:
        equipment_tokens: items that go to exercises.equipment[]
        terrain_tokens:   items that go to exercises.terrain_required[]

    Situational tokens (Darkness, Group Riding Environment, Partner/Team)
    are discarded — they belong in neither field.
    """
    if not raw:
        return [], []

    tokens = [t.strip() for t in raw.split(',') if t.strip()]

    equipment = [
        t for t in tokens
        if t not in TERRAIN_TOKENS and t not in SITUATIONAL_TOKENS
    ]
    terrain = [
        t for t in tokens
        if t in TERRAIN_TOKENS
    ]
    # Situational tokens silently dropped (neither equipment nor terrain).

    return equipment, terrain
```

### 3. Update ETL writer — caller of `split_equipment_column()`

Find the loader code that writes exercise rows. Replace the single-return call site:

**Before:**
```python
equipment = split_equipment_column(row['Equipment'])
cursor.execute(
    "INSERT INTO layer0.exercises (..., equipment, ...) VALUES (..., %s, ...)",
    (..., equipment, ...)
)
```

**After:**
```python
equipment, terrain_required = split_equipment_column(row['Equipment'])
cursor.execute(
    "INSERT INTO layer0.exercises (..., equipment, terrain_required, ...) "
    "VALUES (..., %s, %s, ...)",
    (..., equipment, terrain_required, ...)
)
```

---

## Verification after ETL re-run

```sql
-- Should return non-zero count if terrain extraction worked
SELECT COUNT(*) AS terrain_annotated
FROM layer0.exercises
WHERE terrain_required IS NOT NULL AND array_length(terrain_required, 1) > 0
  AND superseded_at IS NULL;

-- Spot check: a known terrain-gated exercise (e.g., Scree Running Descent)
SELECT exercise_id, exercise_name, equipment, terrain_required
FROM layer0.exercises
WHERE exercise_name ILIKE '%scree%'
  AND superseded_at IS NULL;
-- Expect: equipment[] = [] or [Bodyweight], terrain_required[] = ['Scree Field'] or similar

-- No exercise should have terrain tokens in equipment[]
SELECT exercise_id, exercise_name, equipment
FROM layer0.exercises
WHERE superseded_at IS NULL
  AND EXISTS (
    SELECT 1 FROM unnest(equipment) AS e
    WHERE e IN (
      'Trail', 'Pool', 'Whitewater', 'Rocky Terrain', 'Pump Track',
      'Rock Wall', 'Climbing Gym', 'Fell Terrain', 'Snow Slope'
      -- (full list = TERRAIN_TOKENS)
    )
  );
-- Expect: 0 rows
```
