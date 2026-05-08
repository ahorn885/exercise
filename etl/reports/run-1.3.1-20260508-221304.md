# Layer 0 ETL run report — version 1.3.1

**Run at:** 2026-05-08T22:13:04.575366+00:00

## Insert summary

- layer0.body_parts: 54
- layer0.health_condition_categories: 12
- layer0.equipment_items: 121
- layer0.terrain_types: 15
- layer0.sport_specific_gear_toggles: 12
- layer0.sport_name_aliases: 123
- layer0.sports: 38
- layer0.disciplines: 31
- layer0.sport_discipline_map: 70
- layer0.discipline_pairing: 325 (324 matrix + 1 fallback)
- layer0.phase_load_allocation: 195
- layer0.phase_load_weekly_totals: 116
- layer0.team_formats: 26
- layer0.cross_sport_properties: 1
- layer0.discipline_substitutes: 91
- layer0.discipline_training_gaps: 3
- layer0.sport_discipline_bridge: 69
- layer0.exercises: 245
- layer0.sport_exercise_map: 1065

## Validation — sum_to_100

**Sports checked:** 33  ·  **PASS:** 33  ·  **WARN:** 0

Adjusted stack: rows whose `role` contains `(*Conditional)` (or equals `Conditional`) are zeroed; among paddle disciplines (Packrafting, Kayaking, Canoeing, SUP, Rowing, Sea Kayak) only the maximum per-phase contribution is counted (athlete picks one for race day). Per-phase HIGH-band thresholds: BASE / BUILD / PEAK ≥ 100%; TAPER ≥ 90% (taper-band undershoot is expected behavior, not a curation error).

## Validation — vocab_alignment

**(a) Exercises × body_parts:** 245 checked  ·  PASS 245  ·  WARN 0

**(b) Sport_exercise_map sport_name × bridge:** 36 unique sport names checked  ·  PASS 36  ·  WARN 0
## Validation — substitution_fks

**Rows checked:** 91  ·  **PASS:** 91  ·  **ERROR:** 0

## Validation — training_gap_fks

**Rows checked:** 3  ·  **PASS:** 3  ·  **ERROR:** 0

## Validation — contraindicated_conditions

**Exercises checked:** 245  ·  **PASS:** 245  ·  **WARN:** 0

## Validation — default_inclusion

**Rows checked:** 195  ·  **PASS:** 195  ·  **ERROR:** 0

## v10 extractor diagnostics

**Discipline pairing matrix:** scanned R11–R28, 18 header discipline IDs.

Header IDs: D-001, D-002, D-003, D-004, D-005, D-006, D-007, D-008a, D-008b, D-009, D-010, D-011, D-012, D-013, D-014, D-015, D-016, D-017

**Phase Load Notes split:** 195/195 rows yielded a non-NULL `prescription_note` (100.0%).

**Weekly Total Target parser failures:**

- R65 Swimrun → 'WEEKLY TARGET HOURS: BASE: Sprint (10–25km): 4–6 hrs World Series (25–40km): 8–12 hrs ÖTILLÖ (75km): 12–16 hrs BUILD: Sp'…
- R167 Off-Road / Adventure Multisport (Non-Nav) → 'WEEKLY TARGET HOURS: BASE: XTERRA: 8–12 hrs Quadrathlon: 9–13 hrs Free-format: 8–14 hrs BUILD: XTERRA: 10–15 hrs Quadrat'…
- R192 Open Water Marathon Swimming (10km / Olympic Distance) → 'WEEKLY TARGET VOLUME (km/wk): BASE: 30–45 km | BUILD: 40–55 km | PEAK: 45–60 km | TAPER: 20–30 km  Volume measured in km'…
- R196 Open Water Marathon Swimming (25km / Ultra Distance) → 'WEEKLY TARGET VOLUME (km/wk): BASE: 35–50 km | BUILD: 45–65 km | PEAK: 55–75 km | TAPER: 25–35 km  SESSIONS/WEEK: Base 6'…

## Source-data drops

### `sport_discipline_map`

Rows in `Sport × Discipline Map` (Sheet 3) with a duplicate `(sport_name, discipline_id)` key were dropped (first-seen wins) to satisfy the spec's UNIQUE constraint. The Triathlon D-002 case is a true duplicate; the Long Distance / Endurance Cycling D-005/D-006 cases are sub-format splits the spec's schema doesn't model.

| Source row | Sport | Discipline ID | Discipline name | Role |
|---:|---|---|---|---|
| 20 | Triathlon | D-002 | Road Running | Primary |
| 59 | Long Distance / Endurance Cycling | D-005 | Road Cycling (Gravel Racing — Mixed Surface) | Primary — Gravel |
| 62 | Long Distance / Endurance Cycling | D-006 | Mountain Biking (Enduro — EWS Format) | Primary — Enduro MTB |

### `sport_exercise_map`

Rows in `Sport-Exercise Map` (0B) with a duplicate `(exercise_id, sport_name)` key were dropped. These appear to be accidental rephrasings during DB curation — the same exercise relevance was logged twice with slightly different wording.

| Source row | Exercise ID | Sport | Exercise name | Priority |
|---:|---|---|---|---|
| 387 | EX163 | Canoeing | Canoe Portage Yoke Carry | Critical |
| 669 | EX023 | Fencing | Lateral Lunge (DB or BW) | High |
| 822 | EX207 | XC Skiing | Double Pole Technique (XC Skiing) | Critical |
