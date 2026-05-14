# D-22 Pass 2 Done — Migration SQL + D-23 Kickoff Handoff

**Date:** 2026-05-12
**Predecessor:** `FC1a_Closing_Handoff_v1.md` + `D22_Curation_Reference.md`
**Scope of this session:** D-22 Pass 2 curation (102 remaining rows of `exercises.injury_flags_text` → `movement_components TEXT[]`)
**Status:** D-22 Pass 2 closed. 159/159 active exercise rows now have locked movement_components mappings.
**Next-session scope:** D-22 migration SQL → D-23 curation → D-23 migration SQL. FC-1b not closed until both D-22 and D-23 migrations deploy.

---

## §1. Scope summary

FC-1b Pass 2 was a curation-only session. The remaining 102 rows of `layer0.exercises.injury_flags_text` were classified into `movement_components TEXT[]` arrays per the 11 canonical tokens locked in Pass 1.

Combined with the 57 Pass 1 rows already locked in `D22_Curation_Reference.md`, the full 159-row active population now has proposed mappings.

**Token coverage validation:** all 11 canonical tokens plus empty array `{}` fired at least once across the 159-row population. No degenerate-mapping pattern observed.

**Remaining FC-1b work:**
1. `migrate_exercises_add_movement_components_v1.sql` — schema migration + populate + index (next session)
2. D-23 curation (`disciplines.body_parts_at_risk TEXT[]`, ~150 cells)
3. `migrate_disciplines_add_body_parts_at_risk_v1.sql` — schema migration + populate + index

---

## §2. Pass 2 baseline — 102 classified rows

Edits applied per Andy review across 6 batches (2026-05-12). These are the locked Pass 2 mappings; they go into the migration SQL together with the Pass 1 baseline from `D22_Curation_Reference.md`.

**EX024 retroactive correction (2026-05-12):** Originally locked as `{Angle, Load}` in Batch 5. Updated to `{Angle, Load, Impact}` for consistency with EX119 (nearly identical flag text; heavy-load unilateral plant triggers Impact). The corrected value below is the migration baseline.

### Activation / Primer (13)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX013 | Hip Circle (Band) | {Angle} |
| EX017 | Lateral Band Walk | {Instab} |
| EX039 | Glute Bridge (Double-Leg) | {Angle, Instab} |
| EX040 | Clamshell (Band) | {Angle, Instab} |
| EX041 | Monster Walk (Band) | {Instab} |
| EX042 | Donkey Kick / Fire Hydrant | {Rot, Instab, Angle} |
| EX062 | Banded Hip Flexion (Standing) | {Angle, Instab} |
| EX063 | Terminal Knee Extension (TKE) | {Instab} |
| EX081 | Band Face Pull | {Angle, Instab} |
| EX082 | External Rotation (Band / Cable) | {Load} |
| EX105 | Finger Extension (Band) | {Load} |
| EX109 | Scapular Pull-Up | {Overhead} |
| EX127 | Band Swimming Shoulder Prehab (Y-T-W-L) | {Overhead, Angle, Load, Instab} |

### Aerobic / Endurance (6)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX051 | Uphill Running Technique Drill | {Vol, Impact} |
| EX052 | Downhill Running Technique Drill | {Ecc, Load, Instab} |
| EX090 | Paddling Ergometer Session | {Instab, Vol, Rot} |
| EX124 | Power Hiking Technique | {Vol, Angle} |
| EX126 | Freestyle Pull (With Buoy) | {Overhead, Instab, Angle} |
| EX128 | Kicking Drill (Flutter / Frog) | {Angle, ROM, Vol} |

### Agility (2)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX053 | Agility Ladder Drill | {Instab} |
| EX056 | Reactive Direction Change Drill | {Instab, Rot, Impact} |

### Balance / Proprioception (2)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX043 | Single-Leg Balance Hold | {Instab} |
| EX044 | BOSU Single-Leg Squat | {Instab, ROM} |

### Flexibility / Stretching (4)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX015 | Pigeon Pose | {Rot, Instab} |
| EX076 | Couch Stretch (Cyclist Hip Flexor) | {Angle, Instab} |
| EX077 | Doorway Pec Stretch | {Overhead, Angle, Instab} |
| EX097 | Pec Minor Stretch (Low Doorway) | {Angle, Instab} |

### Interval / Tempo (8)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX048 | Hill Repeats | {Load, Impact, Vol, Angle} |
| EX049 | Strides (Flying Sprints) | {Instab, Load, Impact} |
| EX073 | Threshold Intervals (Bike) | {Load, Vol} |
| EX074 | VO2 Max Intervals (Bike) | {Load} |
| EX075 | Sweet Spot Training (Bike) | {Vol, Load} |
| EX179 | Marathon Pace Run | {Vol, Impact, Load} |
| EX186 | High Cadence Spin Drill | {Vol} |
| EX203 | Rowing Erg Interval Session | {Vol, Instab, Load, Angle} |

### Isometric (15)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX005 | Dead Hang | {Overhead, WristExt, Load, Grip} |
| EX011 | Pallof Press (Band/Cable) | {Instab, Rot} |
| EX012 | Copenhagen Plank | {Load, Angle, Instab} |
| EX037 | Wall Sit | {Angle, Load} |
| EX038 | Split Squat ISO Hold | {Angle, Load} |
| EX067 | MTB Attack Position Hold | {Vol, Angle, WristExt, Load} |
| EX084 | Scapular Depression Hold | {Instab} |
| EX089 | Hollow Body Hold | {Instab, Vol, Angle} |
| EX100 | Hangboard Half-Crimp Hold | {Grip, WristExt, Load, Overhead} |
| EX101 | Hangboard Open-Hand Hold | {Grip, Angle, Overhead} |
| EX102 | Pinch Grip (Plate / Block) | {Load, WristExt, Vol, Grip} |
| EX106 | Lock-Off Hold (90°, 120°) | {Vol, Load, Angle, Overhead, Grip} |
| EX107 | One-Arm Assisted Hang | {Overhead, Load, Grip, Instab} |
| EX173 | Tuck Position ISO Hold (SkiMo Descent) | {Load, Vol, Angle} |
| EX227 | Compression Tuck Hold | {Angle, Vol, Load} |

### Loaded Carry (4)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX009 | Farmer Carry | {Instab, Load, Grip} |
| EX010 | Rucking (Weighted Hike) | {Vol, Load, Ecc} |
| EX050 | Treadmill Incline Walk (Loaded Pack) | {Vol, Load} |
| EX095 | Portage Carry Simulation | {Overhead, Instab, Load, Vol} |

### Mobility (2)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX014 | World's Greatest Stretch | {Angle, WristExt, Load} |
| EX016 | Thoracic Rotation Drill | {Rot, ROM} |

### Plyometric (4)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX007 | Box Jump | {Impact, Instab, Load} |
| EX008 | Broad Jump | {Impact, Angle, Instab} |
| EX033 | Depth Drop (Eccentric Landing Practice) | {Load, Ecc, Impact} |
| EX036 | Running Bounds (Exaggerated Stride) | {Angle, ROM, Impact, Vol} |

### Power (6)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX029 | Sled Push | {Angle, Load, Impact} |
| EX031 | Kettlebell Swing (Two-Hand) | {Angle, WristExt, Load} |
| EX032 | Jump Squat (BW or Light Load) | {Impact, Instab, Load} |
| EX085 | Med Ball Rotational Throw (Wall) | {Rot, Load, Ecc, Impact} |
| EX086 | Landmine Rotation | {Rot, Load, Angle} |
| EX108 | Foot-On Campus Board Move | {Load, Impact, Ecc, Angle, Overhead, Grip} |

### Strength (36)

| exercise_id | exercise_name | movement_components |
|---|---|---|
| EX001 | Back Squat (Barbell) | {Instab, Angle, Load, ROM} |
| EX002 | Goblet Squat (DB/KB) | {Instab, Angle, Load, Grip} |
| EX003 | Romanian Deadlift (Barbell) | {Angle, Load, ROM, Grip} |
| EX004 | Single-Leg RDL (DB) | {Instab, Rot, Load, Grip} |
| EX006 | Pull-Up (BW) | {Angle, Overhead, Grip, Load} |
| EX019 | Barbell Hip Thrust | {Angle, Load} |
| EX020 | Nordic Hamstring Curl | {Angle, Ecc, Load} |
| EX021 | Bulgarian Split Squat (DB) | {Angle, Instab, Load} |
| EX022 | Reverse Lunge (DB or BW) | {Instab, Angle, Load} |
| EX023 | Lateral Lunge (DB or BW) | {Angle, Instab, Load} |
| EX024 | Step-Up High Box (Loaded) | {Angle, Load, Impact} |
| EX025 | Single-Leg Calf Raise (Loaded) | {Load} |
| EX026 | Seated Calf Raise | {Load} |
| EX027 | Tibialis Raise (Wall or Machine) | {ROM} |
| EX028 | Pistol Squat / Assisted Pistol | {Load, Angle, ROM, Instab} |
| EX030 | Reverse Sled Drag | {Load} |
| EX060 | Single-Leg Press (Machine) | {Instab, Angle, Load} |
| EX061 | Good Morning (Barbell) | {Angle, Load, ROM} |
| EX064 | Reverse Nordic Curl | {Load, Angle, Ecc} |
| EX068 | Wrist Pronation / Supination (DB) | {WristExt, Angle, Load, Rot} |
| EX069 | Neck Extension Strengthening (Plate / Band) | {Load, Angle, ROM} |
| EX070 | Single-Leg Cycling Drill (Trainer) | {Instab} |
| EX078 | Single-Arm DB Row | {Rot, Instab, Angle, Load} |
| EX079 | Seated Cable Row (Narrow Grip) | {Angle, Load} |
| EX080 | Lat Pulldown (Wide Grip) | {Overhead, WristExt, Load, Angle} |
| EX087 | Cable High-to-Low Chop | {Rot, Load, Angle, Overhead} |
| EX088 | Russian Twist (DB / Med Ball) | {Rot, Load, Angle} |
| EX099 | External Rotation to Press (Band / Cable) | {Load, WristExt, Overhead} |
| EX103 | Wrist Roller | {Load, WristExt, Grip} |
| EX104 | Rice Bucket Drill | {Grip} |
| EX111 | Reverse Wrist Curl (DB) | {WristExt, Load} |
| EX117 | Loaded Step-Down (Eccentric Box) | {Load, Ecc, Instab, Impact} |
| EX119 | Weighted Step-Up (High Box, Heavy Load) | {Angle, Load, Impact} |
| EX125 | Quad-Eccentric Walk (Controlled Descent) | {Ecc, Vol, Load, Instab} |
| EX129 | Swim-Specific Rotational Core (Dry Land) | {Rot, Load} |
| EX235 | Tricep Pushdown / Extension (Cable / Band) | {Angle, Load} |

**Pass 2 row count:** 13 + 6 + 2 + 2 + 4 + 8 + 15 + 4 + 2 + 4 + 6 + 36 = **102 ✓**

---

## §3. Pass 2 calibrations — four new house rules

Four calibrations crystallized during Pass 2 from Andy edits, not Claude proposals. They resolve cases Pass 1 didn't surface and are consistent with Pass 1's existing house rules.

### Calibration A — Contingent-failure framing → no Instab

When a flag reads *"[issue] if [skill/form/setup] is lost/wrong/breaks/disengages"*, the contingent failure mode doesn't add Instab unless instability IS the activity's primary property.

**When Instab still applies:**
- Anti-rotation work (Pallof Press) → Rot + Instab are direct properties
- Balance training (BOSU work) → Instab direct
- Asymmetric loaded carries (Suitcase, Farmer) → Instab via Rule 11
- Unilateral row/press (anti-rotation property) → Rot + Instab direct
- Explicit canonical Instab keywords in flag (valgus, subluxation, gives way, lateral drop, inversion)

**Reference cases:**
- EX186 High Cadence Spin Drill → no Instab despite "mechanics break" framing (activity is Vol-dominant)
- EX173 Tuck Position ISO → no Instab despite "if core disengages" (activity is sustained position hold)
- EX011 Pallof Press → Instab + Rot kept (anti-rotation IS the activity)

### Calibration B — Vol is endurance/explicit-overuse only

"Under fatigue" within a normal set ≠ Vol. Vol applies for:
- Inherently sustained/endurance activities (running beyond drill duration, rowing intervals, rucking, sustained athletic positions like aero/TT, MTB attack hold)
- Explicit "overuse / accumulated / progressive shortening / chronic / repeated" language
- **NOT** for "fatigues quickly" or "under fatigue" or "to fatigue" in strength flags (these describe intra-set tiredness, not the high-volume pain pattern the token names)

**Reference cases:**
- EX002 Goblet Squat → no Vol despite "grip discomfort under fatigue" (intra-set)
- EX004 Single-Leg RDL → no Vol despite "rotation under fatigue" (intra-set)
- EX009 Farmer Carry → no Vol (loaded short-duration carry, not endurance)
- EX125 Quad-Eccentric Walk → Vol kept ("repeated downhill" = inherent training pattern, multiple descents per session)

### Calibration C — Overhead is intended-mechanism only

Overhead applies when the *intended* movement is "above shoulder / overhead / abduction past 90° / behind body plane", not when "if arms get too high" is a contingent failure of an otherwise-not-overhead exercise.

**Reference cases:**
- EX031 KB Swing → no Overhead despite "if arms too high" (target position is shoulder height; "too high" is form breakdown)
- EX099 External Rotation to Press → Overhead direct (press portion IS overhead)
- EX080 Lat Pulldown (Wide Grip) → Overhead direct ("behind neck" variant is canonical "behind body plane")
- EX109 Scapular Pull-Up → Overhead direct (hanging mechanism is above shoulder)

### Calibration D — Inherent-mechanism extensions allowed with Pass 1 precedent

Tokens can fire when not flag-explicit if the exercise mechanism inherently invokes them AND Pass 1 set the precedent. Used sparingly across 7 Pass 2 rows. **Do not extend further without Pass 1 precedent justification.**

**Allowed extensions used in Pass 2:**
- Grip for hanging exercises with no explicit grip flag → EX005 Dead Hang, EX009 Farmer Carry (Pass 1 EX195 Rope Climb, EX226 L-Sit precedents)
- Instab for inherently asymmetric/unilateral exercises → EX023 Lateral Lunge frontal-plane, EX028 Pistol Squat balance, EX078 Single-Arm DB Row anti-rotation (Pass 1 EX243 Suitcase Carry, EX242 Single-Arm DB Bench precedents)
- WristExt for exercises that load wrist extensors despite flag silence → EX103 Wrist Roller, EX111 Reverse Wrist Curl (no direct Pass 1 precedent; inherent-mechanism only — flag for review if disputed)

---

## §4. D-22 migration SQL — next-session deliverable

**File to produce:** `etl/sources/migrate_exercises_add_movement_components_v1.sql`

**Spec:**

```
-- Pre-flight introspection block (matches house style from update_retype_keeper_exercises.sql v2)

-- Verify column doesn't exist
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'layer0' AND table_name = 'exercises'
  AND column_name = 'movement_components';
-- Expected: 0 rows

-- Verify active row count
SELECT COUNT(*) FROM layer0.exercises WHERE superseded_at IS NULL;
-- Expected: 159

-- Verify all 159 baseline IDs exist
WITH baseline_ids AS (
  SELECT unnest(ARRAY[
    -- Pass 1 (57 IDs) from D22_Curation_Reference.md §"Pass 1 baseline"
    -- Pass 2 (102 IDs) from this handoff §2
    -- combined 159 IDs here
  ]) AS exercise_id
)
SELECT COUNT(*) FROM baseline_ids b
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.exercises e
  WHERE e.exercise_id = b.exercise_id AND e.superseded_at IS NULL
);
-- Expected: 0 (every baseline ID exists in deployed active rows)

-- Migration steps (idempotent)

-- Step 1: ALTER TABLE
ALTER TABLE layer0.exercises ADD COLUMN IF NOT EXISTS movement_components TEXT[];

-- Step 2: UPDATE statements, grouped by exercise_type matching curation order
-- 159 UPDATE statements: one per active exercise
-- Pattern: UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading','Instability'] WHERE exercise_id = 'EX001' AND superseded_at IS NULL;
-- IMPORTANT: write full canonical token names ('Pain with loading'), not abbreviations ('Load')

-- Step 3: GIN index for set-intersect performance
CREATE INDEX IF NOT EXISTS idx_exercises_movement_components
  ON layer0.exercises USING GIN (movement_components);

-- Step 4: Validation block (non-blocking; report violations)

-- 4a: every active row has non-NULL movement_components
SELECT exercise_id, exercise_name FROM layer0.exercises
WHERE superseded_at IS NULL AND movement_components IS NULL;
-- Expected: 0 rows

-- 4b: token values from canonical 11-token set only
WITH canonical AS (
  SELECT unnest(ARRAY[
    'Pain with loading',
    'Pain with impact',
    'Pain above specific joint angle',
    'Pain on descent / eccentric',
    'Pain on rotation',
    'Pain with grip / sustained hold',
    'Pain with wrist extension',
    'Pain with overhead movement',
    'Instability',
    'Reduced ROM',
    'Pain at high volume only'
  ]) AS token
),
deployed_tokens AS (
  SELECT DISTINCT unnest(movement_components) AS token
  FROM layer0.exercises WHERE superseded_at IS NULL
)
SELECT token FROM deployed_tokens
WHERE token NOT IN (SELECT token FROM canonical);
-- Expected: 0 rows

-- 4c: no duplicate tokens within a single row's array
SELECT exercise_id, exercise_name, movement_components
FROM layer0.exercises
WHERE superseded_at IS NULL
  AND array_length(movement_components, 1) <> array_length(ARRAY(SELECT DISTINCT unnest(movement_components)), 1);
-- Expected: 0 rows
```

**Canonical token name mapping for abbreviations used in §2 baseline:**

| Abbrev (in §2 tables) | Canonical token (for SQL ARRAY values) |
|---|---|
| Load | Pain with loading |
| Impact | Pain with impact |
| Angle | Pain above specific joint angle |
| Ecc | Pain on descent / eccentric |
| Rot | Pain on rotation |
| Grip | Pain with grip / sustained hold |
| WristExt | Pain with wrist extension |
| Overhead | Pain with overhead movement |
| Instab | Instability |
| ROM | Reduced ROM |
| Vol | Pain at high volume only |

**Source authority:** `D22_Curation_Reference.md` §"The 11 canonical values" — the exact strings stored in the array.

**Idempotency requirement:** Re-running the migration must be a no-op against current state. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` handle schema idempotency; UPDATE statements with hardcoded values are naturally idempotent.

**Layer2D_Spec impact:** §5.5 / §6 already specify the set-intersect against this column. No spec changes needed post-migration.

---

## §5. D-23 kickoff scope (after D-22 migration deploys)

**File to produce:** `etl/sources/migrate_disciplines_add_body_parts_at_risk_v1.sql`

**Curation scope:**
- Source column: `disciplines.common_injury_patterns` (free text)
- Target column: `disciplines.body_parts_at_risk TEXT[]` (structured)
- Vocabulary: canonical body parts list — see `Vocabulary_Audit_v2.md` (Knee, Ankle, Hip, Lower back, Shoulder, Wrist, Elbow, etc.)
- Population: ~150 cells across the disciplines table
- Seed already drafted in `Layer2D_Spec.md` §5.5

**House rules to lock during D-23 curation (proposed):**
- Body-part-only mapping — no movement-constraint logic (orthogonal to movement_components)
- Canonical body parts only — surface ambiguous cases inline
- Empty array `{}` is valid for disciplines without injury patterns
- If a flag mentions a body part not on the canonical list, surface for Andy's call — likely a vocabulary gap to fix

**Pace estimate:** smaller table than D-22 + cleaner source data → 1–2 hours of focused curation. Likely no need for a sampling Pass 1; can be done in one batch with the canonical body parts list as the lookup.

**FC-1b not closed until both D-22 and D-23 migrations deploy and Project_Backlog reflects both as ✅ Resolved.**

---

## §6. Project_Backlog edits — apply at next session start

Per memory rule #11: mechanically-applicable str_replace blocks. Apply these to `Project_Backlog_v2.md` (the canonical version) at the start of the migration SQL session, **before** writing the migration SQL.

### Edit 1 — D-22 status update

```
old_string:
| D-22 | **`exercises.injury_flags_text` → structured `movement_components TEXT[]` promotion.** Free text in this column is the only source of "movement constraint × exercise" overlap for 2D. Keyword matching is heuristic with known false-negative risk. Promotion to structured TEXT[] enables set-intersect against B.3 enum tokens (mathematically exact). **Population: 159 active rows** (per Neon `layer0.exercises` query 2026-05-11). Cross-layer note exists in `Athlete_Onboarding_Data_Spec_v2` §B.3. | High | 🔴 **Blocker for 2D implementation (FC-1b)** | 2D | **Pass 1 sampling complete 2026-05-11:** 57 rows classified (36% of population), house rules locked, edits applied per Andy review. Remaining 102 rows + migration SQL pending FC-1b. House rules + Pass 1 baseline live in `D22_Curation_Reference.md`. Spec'd in Layer2D_Spec §5.5 / §6. |

new_string:
| D-22 | **`exercises.injury_flags_text` → structured `movement_components TEXT[]` promotion.** Free text in this column is the only source of "movement constraint × exercise" overlap for 2D. Keyword matching is heuristic with known false-negative risk. Promotion to structured TEXT[] enables set-intersect against B.3 enum tokens (mathematically exact). **Population: 159 active rows.** | High | 🟡 **Curation complete; migration SQL pending** | 2D | **2026-05-12: D-22 Pass 2 closed.** 159/159 rows classified (57 Pass 1 + 102 Pass 2). Pass 2 calibrations (A–D) in `D22_Pass2_Done_MigSQL_D23_Kickoff_Handoff_v1.md` §3. Combined baseline in `D22_Curation_Reference.md` (Pass 1) + same handoff §2 (Pass 2). EX024 retroactively updated to `{Angle, Load, Impact}` for consistency with EX119. Migration SQL `migrate_exercises_add_movement_components_v1.sql` pending (next-session deliverable). |
```

### Edit 2 — Add D-38 entry for wrist-deviation token gap

Locate the highest-numbered D-entry row in the Open items table (D-37 at time of writing) and insert D-38 immediately after it. Match the table's existing pipe-column format:

```
new_row_to_insert:
| D-38 | **Wrist deviation under load** — canonical token gap. The 11 `movement_components` tokens cover wrist *extension* (WristExt) but not wrist *deviation* (ulnar/radial). Surfaced twice in D-22 Pass 2: EX126 Freestyle Pull (ulnar deviation stress at hand entry) and EX235 Tricep Pushdown/Extension (wrist deviation if grip angle wrong). Both force-mapped to `Pain above specific joint angle` (Angle), analogous to Pass 1's Rule 11 lateral-flexion-→-Instab force-mapping. | Low | 🟢 Cleanup | 2D, future v2 vocabulary | Two data points across 159 rows is below threshold for adding a 12th canonical token. Track for Layer 2 v2 vocabulary review. Current force-mapping to Angle documented in `D22_Pass2_Done_MigSQL_D23_Kickoff_Handoff_v1.md` §3 Calibration D-precedent / §2 Aerobic-Endurance + Strength sections. |
```

**Application instructions:** apply Edit 2 as an insertion (not str_replace), since it adds a new row rather than replacing an existing one. Locate the D-37 row in the Open items table and insert the D-38 row on the line immediately after.

---

## §7. Files to upload

| File | Action | Versioning notes |
|---|---|---|
| `D22_Pass2_Done_MigSQL_D23_Kickoff_Handoff_v1.md` | **Upload** | This doc — session bookkeeping |
| `D22_Curation_Reference.md` (or `_v2.md`) | **Append Pass 2 baseline** | Decision point: if you just append §2 of this handoff to the existing doc, file name stays. If you reorganize (e.g., merge Pass 1 + Pass 2 into a unified baseline section), bump to `_v2.md` per rule #12. Recommendation: **bump to v2** since adding 102 rows is structurally significant. Old `D22_Curation_Reference.md` stays in project as history. |

**No spec docs change.** No SQL files in this handoff (migration SQL is next-session deliverable).

**Note on rule #12 application:** This is the second handoff written under rule #12 (versioning by suffix). The naming pattern matches `FC1a_Closing_Handoff_v1.md`. Future revisions of this handoff (if any) bump to `_v2.md`.

---

## §8. Files NOT changed (do not upload as new versions)

- `Project_Backlog_v2.md` → edits applied at next session start (§6), not in this handoff
- `Control_Spec_v1.md` → no changes; D-22 still tracked through Project_Backlog
- `Layer2D_Spec.md` → no changes; deployed state will catch up to spec when migration runs
- `FC1a_Closing_Handoff_v1.md` → predecessor doc, not modified
- All Pass 1 / FC-1a deliverables → unchanged

---

## §9. Next-session checklist (memory rule #9 — session-start verification)

When kicking off the migration SQL session, **before writing any SQL**:

1. **Verify uploads landed:**
   - `D22_Pass2_Done_MigSQL_D23_Kickoff_Handoff_v1.md` present in project knowledge
   - `D22_Curation_Reference.md` (or `_v2.md`) shows Pass 2 baseline appended
   - Spot-check that EX024 in the baseline reads `{Angle, Load, Impact}`, not `{Angle, Load}` (this is the retroactive correction; if it didn't land, the migration is wrong)
2. **Apply Project_Backlog edits** per §6 of this handoff. Verify edits land before proceeding.
3. **Pre-flight Neon introspection** before writing the migration SQL:
   - Confirm `layer0.exercises` does NOT yet have `movement_components` column
   - Confirm 159 active rows (`superseded_at IS NULL`)
   - Confirm all 159 baseline IDs from Pass 1 + Pass 2 match deployed exercise_ids exactly
4. **Read the combined 159-row baseline** — Pass 1 (57 rows) from `D22_Curation_Reference.md`, Pass 2 (102 rows) from §2 of this handoff. Note EX024 correction.
5. **Write the migration SQL** per §4 spec. Use full canonical token names (`'Pain with loading'`, not `'Load'`).
6. **Run the migration in Neon** via Andy's standard workflow (Claude writes, Andy executes).
7. **Verify validation block** returns expected counts. If any check fails, do NOT proceed to D-23 — diagnose first.
8. **Update Project_Backlog** with D-22 ✅ Resolved status only after migration verifies clean.
9. **D-23 curation** starts only after D-22 is fully resolved.

---

## §10. Open audit items (track but not blocking)

| Item | Where | Action |
|---|---|---|
| Wrist deviation gap (D-38) | This handoff §3 + new Project_Backlog row | Track. Third surfacing in any future curation crosses threshold for canonical token addition. |
| EX024/EX119 consistency precedent | This handoff §2, §3 | Worth a 10-min audit at migration SQL session start: are there OTHER pairs of near-identical-flag exercises across the 159-row baseline with divergent movement_components? Cheap insurance before migration. |
| CHECK constraint vs trigger for token-set enforcement | §4 spec | Not included in v1 migration. Worth adding in v2 if validation block surfaces issues, but UPDATE-statement source-of-truth is fine for v1. |
| DOMS / pack-fit / saddle-bounce flags in `injury_flags_text` | Pass 2 observation | Data-hygiene issue, not vocabulary gap. Belongs in D-37 source-data cleanup work, not in D-22. |

---

## §11. Gut check

**What this session got right:**
- Full 102-row curation finished in one thread with sustained calibration discipline
- 4 new calibration rules (A–D in §3) emerged from Andy edits, not Claude proposals — they capture real distinctions, not theoretical ones
- Consistency check on EX024 surfaced before migration baseline was locked, not after — caught the right way
- All 11 canonical tokens validated in production data; empty array also represented; no degenerate-mapping pattern
- Memory rule #11 followed: §6 contains str_replace blocks + insertion instructions, not narrative

**Risks:**
- **EX024/EX119 consistency** — Option A (retroactive Impact) was applied. If there are OTHER pairs of near-identical-flag exercises across the 159-row baseline with divergent movement_components, they're not surfaced. The migration baseline is locked but a quick consistency audit at session start is cheap insurance (§10 first item).
- **D-38 (wrist deviation)** is the second token-gap force-map we've accepted (Rule 11 lateral-flexion → Instab was the first). Two data points across 159 rows is sub-threshold for a new canonical token but the pattern is now real. If a third surfaces in D-23 or later work, the case for adding the 12th token strengthens.
- **Migration SQL idempotency** — house style requires re-runnable migrations. UPDATE statements with hardcoded values re-run naturally; ALTER TABLE needs `IF NOT EXISTS`; index creation needs `IF NOT EXISTS`. The pattern is established (`update_retype_keeper_exercises.sql` v2 is the reference) but verify against that file directly when writing v1.
- **Calibration D scope** — "inherent-mechanism extensions allowed with Pass 1 precedent" is a flexible rule. Applied 7× in Pass 2; mostly defensible. The riskiest case is EX103 Wrist Roller + EX111 Reverse Wrist Curl getting WristExt without direct Pass 1 precedent — applied on "this is what the exercise mechanically does" grounds. If Andy disagrees on either when reviewing the baseline pre-migration, those two rows are the most likely to flip.

**What might be missing:**
- **No automated test for movement_components values being in the canonical set.** §4 validation block catches this at migration time (one-shot). A CHECK constraint or trigger would enforce it for future writes. Not strictly required for v1, but cheap to add at migration time. Worth flagging at session start; could be Calibration-E-style decision.
- **D-37 categories** — Pass 2 didn't surface new D-37 categories beyond Pass 1's set (cardiac, cognitive, surface-tissue, equipment-criticism). But the data-hygiene observation that `injury_flags_text` contains DOMS language, equipment criticism, and surface-tissue contact in addition to actual movement constraints is now well-documented across 159 rows.
- **D-23 dependency on D-22 deploy** — D-23 curation is unblocked from a workflow standpoint, but starting D-23 before D-22 migration deploys risks lost work if the D-22 baseline needs revision based on migration-time discoveries. The §9 checklist enforces sequencing.

**Best argument against this handoff structure:**

The handoff splits "FC-1b" into multiple sub-sessions (Pass 2 done; migration SQL pending; D-23 pending). FC-1a was closed in a single handoff after multiple sub-batches because the SQL ran in the same session. FC-1b is splitting at the SQL boundary — which makes context-budget sense but means three handoffs span what was originally scoped as one session. The risk is handoff fatigue: each handoff is overhead, and the "drift mode" memory rules guard against accumulates faster with more handoffs.

Mitigation: each handoff is tight and machine-applicable per rule #11. This one is. Each subsequent handoff (post-migration SQL, post-D-23) should be similarly bounded — Pass 2's complexity was the spike, not the norm.

---

*End of D-22 Pass 2 Done Handoff. Next session: migration SQL → D-23 curation → D-23 migration. Apply §6 Project_Backlog edits first.*
