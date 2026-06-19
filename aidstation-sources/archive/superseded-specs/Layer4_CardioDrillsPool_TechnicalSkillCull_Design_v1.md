# Layer 4 — Cardio drills "consider these" pool + Technical/Skill catalog cull — Design

**Status:** v1 — sequencing + binding ratified (Andy 2026-06-18); §6a guardrails + one-drill cap (2026-06-19); **§3a per-row audit RATIFIED + CORRECTED (2026-06-19).** ⚠ **Read §3a as authoritative over the §1–§3 body counts:** the §1/§3 "65 Technical/Skill / 13 conflation" figures are raw-snapshot estimates; the live post-migration truth (snapshot + `0006–0016`) is **68 active target rows (55 T/S + 9 I/T + 4 A/E)**, the **Technical/Skill cull was already executed by migration 0009/#644**, and Part B reduces to **hygiene only** (11 gear-toggle token strips + EX194 SEM restore).
**Issue:** #698 Track 2 (follow-on to the closed Track 1 recovery-session arc, PR #730).
**Evidence base:** `research/RecoveryMobility_RestDay_CardioDrills_EnduranceEvidence_v1.md` §3 (cardio drills vs volume) + §"Design implication".
**Differentiator:** #6 science-backed, and #4 multi-sport-first — the orphaned catalog is overwhelmingly underserved-discipline skill content (paddle, ski, swim, scramble).

---

## 1. Purpose & boundaries

Wire the **orphaned cardio/skill `0B` catalog** into cardio prescription, and **audit/cull** the Technical/Skill rows that feed it.

Today `cardio_blocks` are **free-composed** by the synthesizer from prompt zone/interval guidance; there is **no cardio analog of `_format_strength_exercise_pool`**, so the structured cardio catalog is never fed to the model (#698 comments 2026-06-17). Active rows with no prescription home:

| `exercise_type` | active | character |
|---|---|---|
| Technical / Skill | 65 | discipline skill drills — paddle strokes, ski/climb/descent technique, navigation, swim drills |
| Interval / Tempo | 8 | structured intervals — Threshold/VO2/Sweet-Spot (bike), Hill Repeats, Tempo/Marathon-pace run, Rowing/erg |
| Aerobic / Endurance | 4 | Paddling/Rowing erg, Sustained LISS, Freestyle Pull, Kicking drill |

**This design's scope:** a **`cardio_drills[]` session block** (the `recovery_exercises[]` analog) — enum-bound, discipline-weighted, Base-emphasized — plus the Part B catalog audit that cleans its source rows.

**Out of scope (named, not solved here):**
- **Cardio volume/zone composition stays LLM-composed.** This adds a drills *vocabulary*, not a volume model. We are *not* moving `cardio_blocks` onto the catalog.
- **Structured-interval prescription** (turning `EX074 VO2 Max Intervals (Bike)` into "Z5 4×4min" deterministically) overlaps **#337** and is a *larger* separate design. The Interval/Tempo rows may seed the drill pool, but catalog-driven interval *structure* is deferred (§13 open).
- The **equipment-vocab conflation** (13 rows carrying skill/discipline tokens in `equipment_required`, #698 comment 2026-06-17) is folded into Part B's hygiene pass only because it touches the same rows — see §3.

---

## 2. The two coupled parts + sequencing

Part B (cull) and Part A (pool) are **two sides of one audit**: Part A's pool draws from the surviving Technical/Skill (+ cardio) rows, so the catalog must be clean and discipline-tagged before the pool is defined over it.

**Sequencing — RATIFIED (Andy 2026-06-18): Part B first, then Part A.**

**Reframe (load-bearing):** the snapshot (`etl/output/layer0_etl_v1.8.0.sql`, active rows) shows the 65 Technical/Skill rows are **overwhelmingly legitimate, high-value, well-cued discipline drills** (e.g. `EX093 Eskimo Roll Practice`, `EX140 Open Water Sighting Drill`, `EX166 Ferry & Eddy Turn`, `EX212 Scrambling Technique`). **Part B is therefore an asset inventory + narrow hygiene cull, NOT a mass deletion.** The survivors are the product asset; the cull removes only genuinely non-prescribable/duplicate rows and fixes vocabulary conflation.

---

## 3. Part B — Technical/Skill audit & cull (Trigger #2)

A read-only audit of all 65 active `Technical / Skill` rows (+ the 8 Interval/Tempo + 4 Aerobic/Endurance), producing a per-row disposition. Output is a **layer0 migration**; every removal/edit is Andy-ratified before it lands (no-padding rule applies in reverse — no cull without review).

**Disposition buckets:**
1. **KEEP + discipline-tag (expected majority).** The row is a prescribable, discipline-relevant drill. Confirm its `sport_exercise_map` membership + `terrain_required` so the pool can discipline-weight it (§5). No content change.
2. **HYGIENE-FIX (the conflation rows).** Gear-bundle tokens mis-filed in `equipment_required` — each is an active `sport_specific_gear_toggles` entry (268/272/265), not an `equipment_items` piece. Fix = remove the toggle name from `equipment_required` (no new vocab). In the **live (post-0009) catalog** this is **11 in-scope rows**: `Climbing — roped` ×5, `Mountaineering` ×1 (EX149 — EX148/EX150 were among 0009's culls), `Touring/AT ski setup` ×5. (The earlier "13 / ×5-×3-×5" figure counted EX148/EX150 before recognising 0009 had retired them; see §3a H1–H3.)
3. **CULL.** ⚠ **Already done (see §3a).** The non-trainable Technical/Skill cull — incl. `EX094 Packraft Inflation/Deflation` and `EX123 Pack Fit Optimization` — was executed by migration **0009 (#644, Andy-ratified 2026-06-16)**, which retired 10 rows. Part B carries **no new culls**; this bucket is empty against the live (post-0009) catalog.

**Deliverable:** an audit table (`exercise_id | name | discipline | terrain | disposition | reason`) appended to this design as §3a before the migration, ratified by Andy. The migration supersedes culled rows (`superseded_at`, not hard-delete — Rule #12 history) and applies hygiene edits.

---

## 3a. Per-row audit & dispositions — RATIFIED + CORRECTED (Andy 2026-06-19)

**Status:** RATIFIED (Andy 2026-06-19), then **CORRECTED** the same day after a Rule #9 reconciliation (below). These dispositions are the spec for the **B1 hygiene migration** (§13a); nothing is applied to `etl/` until B1.

**⚠ Methodology correction (Rule #9) — the audit basis was wrong, now fixed.** The first cut of §3a parsed the **raw** baseline snapshot `etl/output/layer0_etl_v1.8.0.sql` (77 rows: 65 T/S + 8 I/T + 4 A/E). But the authoritative Layer 0 state = **baseline snapshot + the `etl/migrations/layer0/0006–0016` migrations applied on top** — exactly what the CI `layer0-gate` validates (`ls layer0_etl_v*.sql | sort -V | tail -1` + every numbered migration). Re-running that composite in a throwaway Postgres gives the true active set: **68 rows — 55 T/S + 9 I/T + 4 A/E.** The raw-snapshot 77 was stale by **−10 / +1**:

- **−10 already culled:** migration **0009 (#644, Andy-ratified 2026-06-16) already retired** EX094, EX121, EX122, EX123, EX148, EX150, EX152, EX153, EX154, EX155 as non-trainable Technical/Skill — *the same "narrow cull" Part B set out to do.* So the two rows I re-flagged (EX094, EX123) **and** the 8 I'd wrongly marked KEEP are all already retired.
- **+1 missing:** EX288 *Treadwall Intervals* (I/T, added by 0016 at `0B-v1.6.14`) — active, absent from the snapshot's active set.

**Net for Part B: the cull is already complete (0009/#644); what remains is HYGIENE ONLY.**

**Disposition tally (68 active target rows — authoritative post-migration):**

| Disposition | Count | Rows |
|---|---|---|
| **KEEP + discipline-tag** | 56 | all not listed below |
| **HYGIENE — gear-toggle token** | 11 | EX112/113/114/130/131 (climbing), EX149 (mountaineering), EX168–172 (ski) |
| **HYGIENE — SEM restore** | 1 | EX194 (restore lost Modern Pentathlon membership) |
| **CULL** | 0 | already executed by 0009/#644 |

**Audit basis:** authoritative DB = `v1.8.0` snapshot + migrations `0006–0016`, queried in a local Postgres (the gate's exact recipe). Cross-referenced against active `sport_exercise_map`, `equipment_items` (127 names), `skill_capability_toggles`, and `sport_specific_gear_toggles` (12 active — the conflation tokens live here as gear bundles: `Touring/AT ski setup` #265, `Climbing — roped` #268, `Mountaineering` #272). EX194 is the **only** target row with zero active SEM.

### Per-row table (`T/S` Technical/Skill · `I/T` Interval/Tempo · `A/E` Aerobic/Endurance; 68 active, ordered by id)

| exercise_id | name | type | discipline(s) — active Critical SEM (or count) | terrain_required | disposition |
|---|---|---|---|---|---|
| EX048 | Hill Repeats | I/T | Fell Running, Long Distance Orienteering … | Outdoor Hill | KEEP+tag |
| EX049 | Strides (Flying Sprints) | I/T | (9 SEM) | — | KEEP+tag |
| EX051 | Uphill Running Technique Drill | T/S | Fell Running, Mountain Running / Sky Running … | Outdoor Hill | KEEP+tag |
| EX052 | Downhill Running Technique Drill | T/S | Fell Running, Long Distance Orienteering … | Outdoor Hill | KEEP+tag |
| EX057 | Map Navigation Run | T/S | Long Distance Orienteering, Orienteering | — | KEEP+tag |
| EX058 | Compass Bearing Walk / Run | T/S | Long Distance Orienteering, Orienteering | — | KEEP+tag |
| EX070 | Single-Leg Cycling Drill (Trainer) | T/S | Mountain Biking, XC / AR Cycling | — | KEEP+tag |
| EX071 | Cornering Technique Drill (MTB) | T/S | (3 SEM) | Trail | KEEP+tag |
| EX072 | Pump Track / Trail Feature Technique | T/S | (1 SEM) | Pump Track | KEEP+tag |
| EX073 | Threshold Intervals (Bike) | I/T | Gravel Cycling, Mountain Biking, Road Cycling … | — | KEEP+tag |
| EX074 | VO2 Max Intervals (Bike) | I/T | Mountain Biking | — | KEEP+tag |
| EX075 | Sweet Spot Training (Bike) | I/T | Bikepacking, Gravel Cycling, Mountain Biking … | — | KEEP+tag |
| EX090 | Paddling Ergometer Session | A/E | Canoeing, Kayaking, Long Distance Paddle Racing, Packrafting | — | KEEP+tag |
| EX091 | Forward Stroke Technique Drill | T/S | Canoeing, Kayaking, Long Distance Paddle Racing, Packrafting | — | KEEP+tag |
| EX092 | Bracing Stroke Drill (High and Low) | T/S | Kayaking, Packrafting | — | KEEP+tag |
| EX093 | Eskimo Roll Practice | T/S | Kayaking | Pool or Flat Water | KEEP+tag |
| **EX112** | Belay Simulation (Device Practice) | T/S | Rock Climbing | — | HYGIENE (token) |
| **EX113** | Movement on Route (Top-Rope / Lead) | T/S | Rock Climbing | Rock Wall | HYGIENE (token) |
| **EX114** | Flagging / Hip Drop Technique Drill | T/S | (1 SEM) | — | HYGIENE (token) |
| EX116 | Mantling Technique Drill | T/S | (1 SEM) | Rock Wall | KEEP+tag |
| EX118 | Trekking Pole Push Drill | T/S | (2 SEM) | — | KEEP+tag |
| EX120 | Sustained LISS (Hiking Pace) | A/E | Bikepacking, Hiking, Long Distance Orienteering … | — | KEEP+tag |
| EX124 | Power Hiking Technique | T/S | Hiking, Long Distance Orienteering … | — | KEEP+tag |
| EX125 | Quad-Eccentric Walk (Controlled Descent) | T/S | (1 SEM) | — | KEEP+tag |
| EX126 | Freestyle Pull (With Buoy) | A/E | SwimRun, Triathlon | Pool | KEEP+tag |
| EX128 | Kicking Drill (Flutter / Frog) | A/E | (2 SEM) | Pool | KEEP+tag |
| **EX130** | Rappel Device Operation Drill | T/S | Rappelling / Abseiling | — | HYGIENE (token) |
| **EX131** | Wall Walk Descent Technique | T/S | Rappelling / Abseiling | Rock Wall | HYGIENE (token) |
| EX138 | Rest Position & Shake-Out Drill | T/S | Rock Climbing | Rock Wall | KEEP+tag |
| EX140 | Open Water Sighting Drill | T/S | SwimRun, Swimming, Triathlon | Open Water Body; Pool | KEEP+tag |
| EX142 | Bilateral Breathing Drill | T/S | (3 SEM) | Pool; Open Water | KEEP+tag |
| EX144 | Hike-a-Bike Carry Drill | T/S | Bikepacking, XC / AR Cycling | — | KEEP+tag |
| **EX149** | Ice Axe Self-Arrest | T/S | Mountaineering, SkiMo | — | HYGIENE (token) |
| EX156 | Sweep Stroke Technique Drill | T/S | Canoeing | — | KEEP+tag |
| EX157 | Draw Stroke & Pry Technique | T/S | Canoeing | — | KEEP+tag |
| EX158 | Whitewater Line Reading | T/S | Canoeing, Kayaking, Paddle Rafting | River | KEEP+tag |
| EX159 | Wet Exit & Re-entry (Kayak) | T/S | Kayaking | Pool or Flat Water | KEEP+tag |
| EX162 | Tandem Canoe Coordination Drill | T/S | Canoeing, Long Distance Paddle Racing | — | KEEP+tag |
| EX163 | Canoe Portage Yoke Carry | T/S | Canoeing, Long Distance Paddle Racing | — | KEEP+tag |
| EX164 | High-Side Command Response Drill | T/S | Paddle Rafting | — | KEEP+tag |
| EX165 | Raft Paddle Synchronisation & Power Phase | T/S | Paddle Rafting | — | KEEP+tag |
| EX166 | Ferry & Eddy Turn Technique | T/S | Canoeing, Kayaking | Moving Water | KEEP+tag |
| EX167 | Ocean / Surf Zone Entry & Exit | T/S | (1 SEM) | Ocean or Surf | KEEP+tag |
| **EX168** | Skinning Uphill Technique | T/S | SkiMo | — | HYGIENE (token) |
| **EX169** | Ski Kick-Turn on Slope | T/S | SkiMo | — | HYGIENE (token) |
| **EX170** | SkiMo Race Transition Drill | T/S | SkiMo | — | HYGIENE (token) |
| **EX171** | Touring Ski Descent Technique | T/S | SkiMo | — | HYGIENE (token) |
| **EX172** | Lateral Ski Edge Control Drill | T/S | (1 SEM) | Groomed Slope | HYGIENE (token) |
| EX175 | Brick Run Drill (Bike-to-Run Transition) | T/S | Multi-Sport Race, Run-Bike-Run Duathlon, Triathlon | — | KEEP+tag |
| EX176 | Triathlon Transition Practice (T1 & T2) | T/S | Multi-Sport Race, Triathlon | — | KEEP+tag |
| EX178 | Tempo Run (Flat / Road) | I/T | Marathon, Run-Bike-Run Duathlon | Road; Flat Trail | KEEP+tag |
| EX179 | Marathon Pace Run | I/T | Marathon | Road; Flat Trail | KEEP+tag |
| EX180 | Walk-Run Interval Method (Ultra Pacing) | T/S | Long Distance Orienteering, Ultramarathon | Trail; Road | KEEP+tag |
| EX183 | Running with Poles (Trail / Ultra) | T/S | Ultramarathon | Trail | KEEP+tag |
| EX184 | Road Cycling Descending Technique | T/S | Road Cycling | Descent Road | KEEP+tag |
| EX185 | Climb Pacing & Cadence Management | T/S | Bikepacking, Gravel Cycling, Road Cycling | — | KEEP+tag |
| EX186 | High Cadence Spin Drill | T/S | (3 SEM) | — | KEEP+tag |
| **EX194** | Laser-Run Drill (Run-to-Shoot Transition) | T/S | (0 SEM) | — | HYGIENE (SEM) |
| EX196 | Obstacle Vault & Wall Traversal | T/S | Obstacle Course Racing | — | KEEP+tag |
| EX197 | Double Brick / Run-Bike-Run Pacing Drill | T/S | Multi-Sport Race, Run-Bike-Run Duathlon | Road; Trail | KEEP+tag |
| EX199 | SwimRun Water Entry & Exit Technique | T/S | SwimRun | Open Water | KEEP+tag |
| EX200 | Rowing Drive Sequence Drill | T/S | Rowing | — | KEEP+tag |
| EX203 | Rowing Erg Interval Session | I/T | Rowing | — | KEEP+tag |
| EX212 | Scrambling Technique (Moving Terrain) | T/S | Mountain Running / Sky Running | Rocky Terrain; Steep Hill; Boulders | KEEP+tag |
| EX213 | Scree Running Descent Technique | T/S | Mountain Running / Sky Running | Scree Field; Loose Rocky Slope | KEEP+tag |
| EX214 | Fell Descent Technique (Steep Grass, Bog, Heather) | T/S | Fell Running | Fell Terrain | KEEP+tag |
| EX215 | Extreme Gradient Uphill Pacing (VK / Sky Technique) | T/S | Fell Running, Mountain Running / Sky Running | Steep Mountain | KEEP+tag |
| EX288 | Treadwall Intervals | I/T | (2 SEM) | — | KEEP+tag |

### Hygiene-fix detail (these rows KEEP; only the mis-filed token / missing SEM is fixed)

All three conflation tokens already exist as active `sport_specific_gear_toggles` (268/272/265) — gear *bundles*, not `equipment_items` pieces and not `skill_capability_toggles`. Fix = remove the toggle name from `equipment_required` (no new vocab). Genuine `equipment_items` pieces in those rows (e.g. Backpack, Snowshoes, Trekking poles) stay.

- **H1 — remove `Climbing — roped`** (gear toggle #268): EX112, EX113, EX114, EX130, EX131 (5).
- **H2 — remove `Mountaineering`** (gear toggle #272): EX149 (1 — EX148/EX150 were among 0009's culls).
- **H3 — remove `Touring/AT ski setup`** (gear toggle #265 — already exists): EX168, EX169, EX170, EX171, EX172 (5).
- **H4 — restore EX194's `sport_exercise_map` membership:** active exercise, all SEM rows superseded (last `0B-v19.0-r1`, 2026-05-25) → no active discipline tag → un-poolable. `Modern Pentathlon` sport still active. Restore the EX194 → Modern Pentathlon `Critical` row.

*(Out-of-scope aside: EX115 Foot Smear Strength [Balance/Proprioception] and EX195 Rope Climb [Strength] also carry `Climbing — roped` in `equipment_required` — same conflation, but they are not drill-pool target types, so they are noted here, not handled by B1.)*

### Discipline → weight-tier map — RATIFIED (Andy 2026-06-19)

One knob: for a discipline, how much of its matched drill pool surfaces. Form/economy drills don't move steady road run/cycle economy (LIGHT — minimal, de-emphasized); technical-discipline drills transfer (HEAVY — full pool).

- **HEAVY:** Kayaking, Canoeing, Packrafting, Paddle Rafting, Long Distance Paddle Racing, SUP, Swimming, SwimRun, SkiMo, XC Skiing, Snowshoeing, Mountaineering, Rock Climbing, Rappelling/Abseiling, Mountain Biking, XC/AR Cycling, Mountain Running/Sky Running, Fell Running, Orienteering, Long Distance Orienteering, Modern Pentathlon, Obstacle Course Racing, Rowing, **and — ratified HEAVY — Hiking + Trail Running + Ultramarathon** (pole/pack/pacing drills are efficiency skills, not run-economy form; also surfaces them in Andy's hiking-heavy PGE plan).
- **LIGHT:** Road Cycling, Gravel Cycling, Marathon, Triathlon, Run-Bike-Run Duathlon, Bikepacking.
- **Guardrail:** §5 weights per discipline; the LIGHT tier keeps the pure road-economy form drills (EX070, EX186) near-empty for road specialists (§7/§14).

### Interval/Tempo scope — RATIFIED: include now (Andy 2026-06-19)

**Andy ratified including the (now 9) Interval/Tempo rows in the v1 `cardio_drills` pool** (incl. EX288 Treadwall Intervals), over my defer-to-#337 recommendation. The pool spans all three types — matching the §5 `_CARDIO_DRILL_POOL_EXERCISE_TYPES` allowlist. Each interval row's `coaching_cue` carries the dose (e.g. EX074 "3–8 min at RPE 9; 3–5 reps"), so it renders serviceably. *(Watch-out: a structured interval is heavier than a one-cue skill drill; revisit under #337 if the `maxItems:1` framing reads oddly live.)*

### Ratified decisions (Andy 2026-06-19)

1. **CULL — N/A.** The Technical/Skill cull was **already executed** by migration 0009/#644 (EX094/EX123 + 8 others). Part B carries **no new culls**; the "cull both" ratification is satisfied by the existing 0009.
2. **Hygiene H1–H4** — 11 gear-toggle token removals + EX194 SEM restore (the entire remaining Part B scope).
3. **Gear-toggle home confirmed** — `sport_specific_gear_toggles`, no `equipment_items`/skill-cap addition.
4. **Weight-tier map** — Hiking + Trail/Ultra = HEAVY.
5. **Interval/Tempo** — included now (9 rows incl. EX288).

**NEXT = B1 hygiene migration** (12 rows: 11 `equipment_required` token strips + 1 SEM restore; no cull), built against this corrected §3a.

---

## 4. Part A — schema changes (Trigger #3) — `payload.py`

A new **session-level `cardio_drills[]` block**, the structural analog of `recovery_exercises[]` (§ Track-1 design v2 §3). It rides `kind=="cardio"` sessions alongside the free-composed `cardio_blocks`; it is **not** a new session `kind`.

```
class CardioDrill(BaseModel):
    exercise_id: str          # enum-bound to the drill pool at the tool boundary
    exercise_name: str
    prescription: str         # free text — "4×50m focus on catch", "6×30s sighting every 3rd"
    instructions: str | None
```

`PlanSession`: add `cardio_drills: list[CardioDrill] | None = None`. Invariants: `cardio_drills` only on `kind=="cardio"`; null/empty elsewhere; each `exercise_id` non-empty. `cardio_blocks` unchanged.

**One drill per session — HARD CAP (Andy 2026-06-19).** The tool-schema sets `cardio_drills` `maxItems: 1` and the pydantic invariant enforces `len ≤ 1`. We don't prescribe more than one skill/drill in a session — a session targets one technical focus, not a drill circuit. The cap is also a reliability lever (§6a-G4): a single-element bounded array is the smallest possible failure surface and removes any "how many drills?" ambiguity from the model. (Field stays a `list` not a scalar to reuse the `recovery_exercises` render/parse/validate path verbatim; the cap is the only difference.)

**Why a session block, not a `cardio_blocks` sub-item:** a drill ("Open Water Sighting") is a discrete catalog movement with its own id/cues, like a `recovery_exercises` entry — not a zone sub-block of a volume workout. Mirroring `recovery_exercises` reuses the entire shipped pattern (pool fn → enum-bind → validator membership → render).

---

## 5. Drill pool computation (deterministic) — `per_phase.py`

`compute_cardio_drill_pool_ids(layer2c_payloads, layer2d_payload, *, disciplines, phase)` — mirrors `compute_recovery_pool_ids` (per_phase.py:520) but with the drill type allowlist + **discipline weighting** + **phase periodization**:

- **Type allowlist:** `Technical / Skill`, `Interval / Tempo`, `Aerobic / Endurance` (a `_CARDIO_DRILL_POOL_EXERCISE_TYPES` frozenset, the `_RECOVERY_POOL_EXERCISE_TYPES` analog).
- **2D exclusion:** drop `layer2d.excluded_exercises` ids (wrist/injury contraindications honored — same as recovery).
- **Discipline weighting (evidence §3 — the load-bearing knob):**
  - **HEAVY** (drills transfer): swimming, paddle sports (kayak/canoe/packraft/SUP/raft), swimrun, technical MTB, ski/skimo, climbing/scrambling. Surface the full discipline-matched pool.
  - **LIGHT** (drills don't move economy — MA null): steady road running, road cycling. Surface a *minimal* set (the few rows like `EX051/052 Up/Downhill Running Technique`, `EX186 High Cadence Spin`, `EX070 Single-Leg Cycling`) and the prompt de-emphasizes them.
  - The exact discipline→tier map is §13 OPEN (ratify with the §3a audit, since both key on the same discipline tags).
- **Phase periodization (evidence §3 "front-loaded in Base, displaced toward Build/Peak/taper"):** Base → full weighted pool; Build → reduced; Peak/Taper → race-specific technical only (or empty). Implemented as a phase gate on the rendered pool, not the schema enum.

Sorted+deduped for deterministic enum ordering (cache-key stability), Rule #15 log on type/discipline-dropped rows — same contract as `compute_recovery_pool_ids`.

---

## 6. Prompt changes (Trigger #1) — `per_phase.py`

- `_format_cardio_drill_pool(...)` — the `_format_recovery_exercise_pool` analog (per_phase.py:967). Renders `=== Cardio drill pool (consider these) ===` **grouped under the athlete's discipline headers** (so the model matches `Open Water Sighting → swim session` by reading, not guessing), each row carrying its catalog **`coaching_cue`** and an inline phase-emphasis annotation. **Size-capped** like the recovery pool (≤12 rendered rows; if a multisport union exceeds it, keep the highest-weighted per discipline).
- `# Cardio drills` SYSTEM_PROMPT section: *when* to prescribe — Base-heavy, technical-discipline-heavy; **at most one drill per cardio session** (§4 cap); attach a drill **only to a session of its own discipline**; **explicitly caution against over-prescribing running/cycling form drills** (coaching-voice rendering of the null-economy finding: "form drills don't move running economy — prioritize volume + strength; use cadence cues only for injury/biomechanics"). Drills attach to existing cardio sessions; they do not add sessions or volume.
- **Pool-derived, never name-specific (§6a-G1).** The instruction body must stay generic — "*optionally* attach one drill appropriate to today's discipline, **from the pool below**" — and must **never name a specific drill or drill-type** the enum might not contain (no "prescribe a sighting drill"). All specifics come only from the rendered enum, so the prompt can never ask for something the pool lacks.

This is a Trigger #1 prompt-body change → ratify the prompt wording before it ships (per the project's stop-and-ask).

---

## 6a. LLM-reliability guardrails (de-risking the drill assignment) — RATIFIED (Andy 2026-06-19)

The enforced enum-bound mechanism is inherited verbatim from the shipped `strength_exercises`/`recovery_exercises` pattern, so the model **cannot emit an out-of-pool id** and drills carry **only one** validator blocker (membership) with **no placement rule** — i.e. *hard*-failure/correction-loop-churn is already unlikely. These guardrails target the residual risks: the *unfillable ask* (hard-fail) and the *wrong pick* (soft-stumble). Tiered by leverage.

**Tier 1 — eliminate hard-fail / churn paths.**
- **G1. Optional + pool-derived prompt (keystone).** `cardio_drills` is nullable / "consider these," **never mandatory** — an optional field cannot produce an unfillable payload. Combined with the §6 pool-derived/never-name-specific rule, the model can never be asked for a drill the enum lacks. (Contrast recovery's *assigned* placement, which could conflict with `daily_window_fit` and churn.)
- **G2. Exactly one hard constraint.** Membership (enum-backstopped) is the **only** drill blocker. Discipline-fit, phase emphasis, and dosage are steered by render+prompt, **not** added as validator rules — one hard rule = minimal deadlock surface. Explicitly **resist** a discipline-match or drill-count validator (§8).
- **G3. Validate the `cardio_drills` invariants INSIDE the per-session try/except.** The `only-on-cardio` + `≤1` checks must run where a violation becomes a `schema_violation` **retry**, not a hard 500. (Carried watch-out: the race-week-brief handoff flagged `_check_two_per_day` running *outside* the per-override try/except → a non-contiguous override 500s instead of retrying. The new invariants must not repeat that — wire them into the retryable path.)

**Tier 2 — eliminate the soft-stumble (wrong pick).**
- **G4. Legible, capped rendering (§6).** Group by the athlete's discipline, carry each row's `coaching_cue`, annotate phase-emphasis, cap the rendered pool (≤12) **and** cap per-session drills at **1** (§4). A grouped+cued+bounded menu turns selection into matching, not guessing — the dominant lever for pick-quality on a multisport athlete's large union pool.
- **G5. Discipline-scoping via prompt, not a rule.** The residual soft-risk (a swim drill on a run session, both in-pool for a multisport athlete) is handled by the grouped render + the explicit "own-discipline-only" instruction — **not** a hard discipline-match validator (which would reintroduce churn). A rare mis-attach is a quality nit, not a failure. **Open call (§13):** tighten to a soft `severity=warning` discipline-match check later *only if* it bites live.
- **G6. Part B first = a clean enum (upstream guarantee).** The worst stumble is the model dutifully picking an *in-pool* row that's junk or mis-tagged. The §3a audit guarantees every pool row is genuinely prescribable and correctly discipline-tagged **before the pool exists** — garbage-in → garbage-pick. This is an independent reason the ratified B→A sequencing is itself a de-risk.

**Tier 3 — bound the blast radius if it does churn.**
- **G7. Rule #15 instrumentation at the pool boundary.** Log the computed drill pool (`ids + discipline + phase`) per session and any membership-reject `detail`, so a live stumble is a one-read `/admin/logs` diagnosis — not a pv=69-style reverse-engineering. (Inherits `compute_recovery_pool_ids`' Rule #15 log pattern, §5.)
- **G8. Keep drills out of the volume/ACWR/band math (§8)** so a drill can't interact with the existing correction-loop pressure — they carry no `discipline_id` and add no prescribed volume.

---

## 7. Enforcement (RATIFIED: enforced enum-bound) + the free-compose reconciliation

Andy ratified **enforced enum-bound** (over the advisory option I recommended). Reconciled with "cardio stays LLM-composed" as follows, and flagged because the tension is real:

- **Enforcement binds the drill *vocabulary*, not the *presence* of drills.** The `cardio_drills[*].exercise_id` is enum-bound to `compute_cardio_drill_pool_ids(...)` at the tool boundary (mirrors `strength_exercises`/`recovery_exercises`: per_phase.py:682-686), so an out-of-catalog or wrong-discipline drill is structurally impossible. A validator membership rule (§8) backstops the injected/`model_construct` path.
- **Volume/zone composition stays free.** The LLM still decides *whether* a cardio session carries drills and how much volume — guided by the Base-emphasized prompt — and `cardio_blocks` are untouched. So "enforced" means *if you name a drill it must be a real, discipline-appropriate, phase-appropriate catalog drill*, not *every cardio session must contain drills*.
- **Empty-pool fallback (mirrors recovery):** when the pool resolves empty (no discipline match / Peak-Taper gate / all 2D-excluded), the caller passes no enum (schema falls back to free string) **and** the prompt block is suppressed — the LLM is never handed an unfillable `cardio_drills[]`. The §8 validator rule skips on empty pool (no re-freeze).

**Open tension to watch (§14):** enum-binding a *marginal-evidence* lever is stronger than the evidence strictly supports for the LIGHT tier. The phase/discipline gating keeps the LIGHT-tier pool tiny, so the binding mostly bites where evidence is strong (swim/paddle/ski).

---

## 8. Validator (`validator.py`)

- **`_rule_cardio_drill_pool_membership`** — the `_rule_recovery_pool_membership` analog (validator.py:722): every `cardio_drills[*].exercise_id` ∈ `compute_cardio_drill_pool_ids(...)`. Blocker; lazy-imports `per_phase` to dodge the cycle; **skips on no-2C / empty-pool** (empty-pool owned by suppress, blocking would re-freeze).
- **This is the ONLY drill blocker (§6a-G2).** No discipline-match rule, no drill-count rule. The `≤1`-per-session and `only-on-cardio` caps live as **pydantic invariants on the retryable path (§6a-G3)**, not as validator rules — a slip self-corrects via `schema_violation` retry rather than churning a blocker.
- **No placement rule.** Drills ride cardio sessions; they are not date-placed, so there is no `compute_recovery_placement` analog. (Phase periodization is a render gate, not a per-date constraint.)
- Drills are excluded from volume-band/ACWR/strength-count/discipline-gate by construction (they carry no `discipline_id` and add no prescribed volume) — confirm during build, same as recovery's §8 sweep.

---

## 9. Render (`templates/plan_create/view.html`)

Cardio session card gains a subordinate `cardio_drills` list (the `recovery_exercises` render branch analog, Track-1 Slice 3a §9) — drill name + prescription. CSS reuse from `.sess-recovery`.

---

## 10. Caching

`hashing.py` `LAYER4_PROMPT_REVISION` bump (current "10" → "11"): the prompt body + tool schema change, so cached plans regenerate with drills on next plan-gen. The drill-pool ids fold into the existing cache key the same way the recovery pool did.

---

## 11. Edge cases

- **Empty pool** → suppress + free-string fallback (§7).
- **No discipline match** (athlete's disciplines all LIGHT-tier, e.g. road marathoner) → minimal/empty pool; prompt de-emphasizes; acceptable (evidence says drills don't help here).
- **Peak/Taper** → race-specific technical only or empty.
- **2D wrist contraindication** (Andy's live case) → wrist-loaded drills (some climbing rows) dropped via the 2D exclusion, same as recovery.
- **Refresh / single-session paths** → no `phase`/discipline cone in some contexts → pool may no-op; validator guards on context (mirrors recovery placement-match guard).

---

## 12. Test plan

- `compute_cardio_drill_pool_ids`: type allowlist; 2D exclusion; discipline weighting (HEAVY surfaces full, LIGHT minimal); phase periodization (Base full, Peak empty); deterministic ordering; empty-pool.
- Schema: `cardio_drills` only on cardio; **`maxItems:1` — a 2-drill payload rejects (§4 / §6a-G4)**; enum-bind present when pool non-empty, free-string when empty; invariants.
- **Guardrails (§6a):** the `only-on-cardio` + `≤1` invariants raise a **retryable `schema_violation`, not a 500** (G3); membership is the only blocker — no discipline-match/count rule (G2); a wrong-discipline-but-in-pool drill is accepted by the validator (G5, render/prompt-steered).
- `_rule_cardio_drill_pool_membership`: in-pool passes, out-of-pool blocks, empty-pool skips, no-2C skips.
- Render branch; cache-key includes drill-pool hash.
- Part B: the audit migration validates against the CI layer0 gate (postgres + snapshot + `validate_layer0`); culled-row inbound proxy/substitute references repointed.

---

## 13. Decisions

**Ratified (Andy 2026-06-18 / -06-19):**
- Sequencing: **Part B (cull) → Part A (pool)**.
- Binding: **enforced enum-bound** (reconciled per §7 — binds vocabulary, not presence).
- **One drill per session — hard cap `maxItems:1`** (2026-06-19, §4).
- **§6a LLM-reliability guardrails G1–G8** (2026-06-19) — optional+pool-derived prompt; one membership blocker only; retryable invariants; legible capped render; discipline-scope via prompt not rule; clean-enum-first; Rule #15 logging.
- **§3a per-row dispositions** (2026-06-19, CORRECTED) — against the live post-migration catalog (68 active): **56 KEEP / 12 HYGIENE / 0 CULL**. The Technical/Skill cull was **already executed by 0009/#644** (EX094/EX123 + 8 others). Remaining Part B = hygiene: H1–H3 strip mis-filed gear-toggle tokens from `equipment_required` (11 rows; `sport_specific_gear_toggles`, no new vocab); H4 restore EX194's SEM row. See §3a.
- **Discipline→weight-tier map** (2026-06-19) — HEAVY technical disciplines incl. **Hiking + Trail/Ultra**; LIGHT road run/cycle. See §3a.
- **Interval/Tempo scope** (2026-06-19) — **include** the 8 Interval/Tempo rows in the v1 drill pool now (not deferred to #337). See §3a.

**Open (ratify before the respective slice lands):**
- **Prompt-body wording** (§6 / §6a-G1) — Trigger #1 ratification (before A2).
- **Tighten-later (§6a-G5):** add a soft `severity=warning` discipline-match check (drill's `sport_exercise_map` ∩ session discipline) **only if** wrong-discipline picks show up live — kept out of v1 to avoid churn.

---

## 13a. Build slices (>5 files → split per the 5-file ceiling)

- **B1 — hygiene migration** (cull already done by 0009/#644): one layer0 migration applying §3a's 12 hygiene edits — strip the 11 mis-filed gear-toggle tokens from `equipment_required` + restore EX194's Modern Pentathlon SEM row. Serving-relevant 0B edit (supersede + re-insert at a bumped version; the 0016 pattern). Bookkeeping + `etl/` only.
- **A1 — schema:** `payload.py` `CardioDrill` + field + invariants + tests. No prompt/cache.
- **A2 — pool + prompt + cache:** `per_phase.py` `compute_cardio_drill_pool_ids` + `_format_cardio_drill_pool` + `# Cardio drills` section + schema enum-bind thread; `hashing.py` revision bump. (Prompt ratified first.)
- **A3 — validator + render:** `validator.py` `_rule_cardio_drill_pool_membership`; `templates/plan_create/view.html` + CSS.

---

## 14. Gut check

**Risks / what might be missing / best argument against:**
- **The evidence is genuinely mixed and the binding is strong.** Enum-enforcing a marginal lever (LIGHT tier) over-commits relative to the science; §7's phase/discipline gating is what keeps that honest — if the gating is weak, we hard-gate something that doesn't matter. Watch the LIGHT-tier pool stays near-empty.
- **Soft-nudge risk inverted — largely closed by §6a.** With enforced binding the failure mode flips from "LLM ignores the pool" (advisory) to "LLM is blocked/retries when it names a sensible drill we didn't tag to that discipline." **§6a-G1 defuses the *freeze* form of this**: drills are *optional*, so a too-narrow/partial pool makes the model **omit** a drill, not churn a blocker — the residual is under-use (a missed nudge), not a stall. Suppress-on-empty + skip-on-empty cover the empty case; the discipline tagging in §3a (G6) still matters, but now for *coverage quality*, not for *not-freezing*.
- **Best argument against the whole track:** cardio volume stays free-composed regardless, so the *performance* delta is concentrated in technical disciplines (swim/paddle/ski) — but that is precisely AIDSTATION's underserved-discipline market and Andy's own PGE race (packraft/technical-MTB/scramble/climb), so the asset is on-target rather than incidental. The bigger near-term value is arguably **Part B's catalog hygiene** (real correctness — conflation fix + dead-row removal), which lands first regardless.
- **Open dependency:** the structured-interval question (#337) is deliberately walled off; if Andy wants catalog-driven interval *structure*, that's a separate, larger design and this drill pool should not try to absorb it.
