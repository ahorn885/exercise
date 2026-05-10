# Layer0 ETL Spec — Batch B Patch

**Date:** 2026-05-10
**Predecessor spec:** `Layer0_ETL_Spec_v3.md`
**Status:** Patch — apply alongside other pending §8 corrections at the next consolidated spec revision (recommended after 2D, 2E lock per `Batch_A_Done_Batches_BC_Kickoff_Handoff.md`).

This patch documents the schema and consumer changes from Batch B (technique-focus migration). It does not supersede v3; it is a delta to fold into v4 when the Layer-2-node-pass spec revision happens.

---

## §4 addition — new table

Insert as **§4.15** (after `4.14 Vocabulary tables`):

### 4.15 `layer0.discipline_technique_foci` (NEW Batch B)

One row per technique focus. A focus is a coaching emphasis applied during a session — it is not a session-creating training stimulus on its own. Foci were extracted from v19 `Technical / Skill` exercises that lacked measurable load, progression, or equipment-substitution semantics.

```sql
CREATE TABLE layer0.discipline_technique_foci (
  id                          SERIAL      PRIMARY KEY,

  focus_id                    TEXT        NOT NULL,
  focus_name                  TEXT        NOT NULL,
  description                 TEXT        NOT NULL,

  -- Selection criteria
  discipline_ids              TEXT[]      NOT NULL,    -- e.g. {'D-007','D-008a'}
  applicable_session_types    TEXT[],                  -- NULL = all session types
  applicable_terrain_ids      TEXT[],                  -- NULL = all terrains
  required_equipment          TEXT[],                  -- canonical_name in equipment_items
  required_gear_toggle        TEXT,                    -- canonical_name in sport_specific_gear_toggles

  -- Coaching metadata
  athlete_level               TEXT        NOT NULL DEFAULT 'any',  -- 'beginner'|'intermediate'|'advanced'|'any'
  priority                    TEXT        NOT NULL,                -- 'Critical'|'Standard'|'Optional'
  when_to_emphasize           TEXT,
  source_exercise_ids         TEXT[],                              -- traceability to v19 exercises

  audit_log                   TEXT,

  etl_version                 TEXT        NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (focus_id, etl_version)
);

CREATE INDEX idx_dtf_disciplines ON layer0.discipline_technique_foci USING GIN (discipline_ids);
CREATE INDEX idx_dtf_active      ON layer0.discipline_technique_foci (etl_version) WHERE superseded_at IS NULL;
```

**Selection model (read by Layer 4 — implementation in plan-gen, not in Layer 0):**

```
filter foci where:
  session.discipline ∈ discipline_ids
  AND (applicable_session_types IS NULL OR session.type    ∈ list)
  AND (applicable_terrain_ids   IS NULL OR session.terrain ∈ list)
  AND (required_equipment       IS NULL OR required_equipment       ⊆ session.locale.equipment)
  AND (required_gear_toggle     IS NULL OR athlete.toggles[gate]   = TRUE)
  AND athlete.level ∈ (focus.athlete_level, 'any')
selected = top 0–2 by priority, rotating across plan-week
```

**Population:** initial 35 rows at `etl_version = '0B-v19.B'`, derived from 52 dropped technique exercises (some collapsed multi-cue). One documented gap: TF-033 (Rowing) carries empty `discipline_ids` because Sports Framework v10 has no Rowing discipline. Resolve in framework v11 or re-tag the focus.

**Layer 4 substitution semantics:** foci are not substituted for, and they don't substitute for exercises. They are an orthogonal data type — coaching emphasis on top of an existing scheduled session.

---

## §4.12 update — exercises retypes + schema correction

**Schema correction (v4 must fix):** the v3 spec at §4.12 declares both
`exercise_id TEXT NOT NULL UNIQUE` (column-level) AND
`UNIQUE (exercise_id, etl_version)` (table-level). These are contradictory —
the column-level UNIQUE would prevent version-bumped reinserts, breaking the
§4.1 versioning pattern. Production schema (verified `\d layer0.exercises`
on 2026-05-10) deploys only the table-level constraint; the column-level
UNIQUE was never materialized. **v4 should remove `UNIQUE` from line 524**
of the v3 schema block. The deployed DB needs no change.

**Type vocabulary update:** 13 exercises previously typed `Technical / Skill` were retyped to load-bearing types in Batch B. No schema change. Document the type-vocabulary rule:

> **Rule:** `exercise_type = 'Technical / Skill'` is **deprecated** as of `0B-v19.B`. New exercises must be typed against the load-bearing vocabulary (`Aerobic / Endurance`, `Strength`, `Power`, `Plyometric`, `Core / Stability`, `Mobility / Recovery`, `Activation / Primer`, `Interval / Tempo`, `Loaded Carry`). Pure-technique entries belong in `layer0.discipline_technique_foci`, not `layer0.exercises`.

Add to v3 §4.12 as a "Type vocabulary" subsection.

---

## §8 update — consumer reference table

Two additions to the consumer table:

| Layer | Receives from Layer 0 | Tables queried |
|-------|----------------------|----------------|
| 4 (Plan Generation) | Full sport context + classifications + exercise pool (equipment + injury + condition filtered) + phase load bands + weekly hour targets + training gaps + substitution candidates **+ technique foci eligible for each scheduled session** | All tables via query layer **+ `discipline_technique_foci`** |

The Plan-Gen row already says "All tables via query layer" so this is a clarifying expansion, not a structural change.

No other consumer rows touch the new table directly. Layer 2C does not consume foci — they're orthogonal to equipment mapping.

---

## §6 (ETL run process) — no change

Foci are not produced by ETL from a source spreadsheet. They are populated by hand-curated SQL (Batch B and successors). They participate in the standard versioning pattern (etl_version + superseded_at) but do not have an ETL pipeline source.

If the team later decides to author foci in a spreadsheet, that becomes a future ETL source addition. For now, foci live in SQL alongside their source curation rationale.

---

## §7 — open items (additions)

Add:

| # | Item | Owner | Status |
|---|---|---|---|
| O | Rowing discipline missing from Sports Framework — TF-033 (Rowing drive sequence) carries empty discipline_ids as a result | Framework v11 author | Flagged |
| P | Layer 4 selection logic for foci — encode the filter/priority algorithm and integrate into plan-gen | Plan-gen design | Scoped, not started |
| Q | Foci edit workflow — when product evolves, foci will need updating; decide whether spreadsheet-sourced ETL pipeline is worth building, or hand-curated SQL is sufficient | Roadmap | Deferred |

---

## Files shipped for Batch B

| File | Purpose |
|---|---|
| `migrate_discipline_technique_foci.sql` | Create table + indexes |
| `populate_discipline_technique_foci.sql` | Insert 35 focus rows at `0B-v19.B` |
| `migrate_drop_technique_exercises.sql` | Supersede 52 rows in `exercises` and corresponding map rows |
| `update_retype_keeper_exercises.sql` | Supersede + reinsert 13 keepers with new exercise_type at `0B-v19.B` |
| `Layer0_ETL_Spec_v3_Patch_Batch_B.md` | This patch document |

**Run order:**
1. `migrate_discipline_technique_foci.sql`
2. `populate_discipline_technique_foci.sql`
3. `migrate_drop_technique_exercises.sql`
4. `update_retype_keeper_exercises.sql`

Each script contains a verify block; a failure in any step rolls the whole transaction back.

---

*End of Batch B patch.*
