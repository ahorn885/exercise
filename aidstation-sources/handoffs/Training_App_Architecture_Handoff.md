# Training Plan App — Architecture Session Handoff
**Session date:** May 2026  
**Next session focus:** User onboarding flow design → database gap analysis  
**Status:** Layer 0 ETL spec complete. Layer 1 prompt design blocked pending onboarding flow clarity.

---

## What This Project Is

A SaaS training plan app for endurance and multi-sport athletes. The core problem being solved: the current app works but stuffs all athlete data into a single LLM prompt — too much room for error, too little precision. The rebuild decomposes this into a layered prompt architecture where each layer receives only the data it needs, outputs are stored and versioned, and plan updates re-run only the affected layers.

The full system architecture is documented in the project file: **Training Plan App — Full System Architecture (consolidated design document).** That is the authoritative reference for the overall system. This handoff covers what was decided in this session on top of that document.

---

## What Was Decided This Session

### Layer 0 is reference data, not user data
Layer 0 = platform-level sport rule sets (0A) and exercise library (0B). Same for every user. Built and maintained by the app team, not collected from athletes. Stored in a dedicated `layer0` PostgreSQL schema. Never overwritten — versioned with `superseded_at` timestamps.

The Athlete Onboarding Schema (AR_Athlete_Onboarding_Schema.md) and the Sports Framework Sheet 7 are **Layer 1 territory** — user-specific data collected at onboarding. They were designed in the same session as the framework files but belong to a different layer. Do not conflate them with Layer 0.

### Storage architecture: PostgreSQL with JSONB
Chosen for early-stage SaaS. Rationale: queryable without loading full blobs, versioning is native to the schema pattern, clean migration path to document store later if needed. Every table — Layer 0 and per-user — carries `etl_version` / `created_at` / `superseded_at` fields. Queries always filter `WHERE superseded_at IS NULL`.

### Layer 0 ETL spec is complete
Full spec is in the output file: **Layer0_ETL_Spec.md**. Key decisions:

**Source files:**
- `Sports_Framework_v3.xlsx` → Layer 0A (sport rule sets)
- `AR_Exercise_Database_v17.xlsx` → Layer 0B (exercise library)

**Tables generated:**
| Table | Source |
|-------|--------|
| `layer0.sports` | Sheet 1, Sports Framework |
| `layer0.disciplines` | Sheet 2, Sports Framework |
| `layer0.sport_discipline_map` | Sheet 3, Sports Framework |
| `layer0.discipline_pairing` | Sheet 4, Sports Framework (+ Sheet 3 col 7 fallback) |
| `layer0.phase_load_allocation` | Sheet 5, Sports Framework |
| `layer0.team_formats` | Sheet 6, Sports Framework |
| `layer0.sport_discipline_bridge` | Derived at ETL time from Sheet 3 |
| `layer0.exercises` | Exercise Master, Exercise DB |
| `layer0.sport_exercise_map` | Sport-Exercise Map, Exercise DB |

**Explicitly excluded from ETL:**
- Sport Summary sheet (human nav only)
- Legend sheet (human ref only)
- Sheet 7 of Sports Framework (Layer 1 territory)
- Governing Bodies column (tabled — future FAQ feature)
- Race/Event Formats column (tabled — review after Layer 1 design)
- "Sports It Appears In" column (replaced by bridge table)
- Novelty column (no athlete preference signal to act on)
- B2B Pairing Rule column (consolidated into Sheet 4, then deprecated)
- Evidence Quality (stored, not injected into prompts)
- Coaching Cues (stored, surfaced in UI per-exercise — not in plan generation prompts)

**The bridge table** (`layer0.sport_discipline_bridge`) is the critical join between 0A and 0B. It maps framework sport names ("Adventure Racing") to exercise database sport vocabulary ("Trail Running," "Mountain Biking," etc.) via the discipline ID. This many-to-many mapping must be manually verified for vocabulary alignment between the two source files before ETL runs.

**The query layer** sits between the database and prompts. Accepts structured parameters (sport, disciplines, phase, athlete age, equipment list, injury flags), runs filtered queries, returns a pre-built JSON payload. The LLM never writes SQL. Full input/output spec is in Layer0_ETL_Spec.md Section 4.

### What each downstream layer receives from Layer 0
| Layer | What it gets |
|-------|-------------|
| 2A | Sport planning flags, discipline list with roles and race time % |
| 2B | Nothing directly |
| 2C | Exercise pool filtered by discipline only |
| 2D | Injury patterns and preceding behaviors per discipline |
| 2E | Nothing directly |
| 3D | Contraindicated parts and injury flags per exercise |
| 4 | Full sport context + equipment/injury-filtered exercise pool |
| 4.5 | Ramp rates, phase durations, pairing rules, taper norms |
| 5A–5C | Nothing directly |

---

## Open Items from This Session

| # | Item | Context |
|---|------|---------|
| 1 | Governing Bodies | Table for future FAQ feature. No action needed now. |
| 2 | Race/Event Formats | Review after Layer 1 prompt design. Bring handoffs from both chats together. |
| 3 | Discipline Pairing Matrix gap (D-018–D-031) | Sheet 4 needs to be completed using Sheet 3 col 7 data before ETL runs. Being worked in separate chat. |
| 4 | Vertical Gain field in Layer 1 | Athlete onboarding must capture current vertical gain capacity so Layer 0A vertical gain rules have a baseline. Flag when designing onboarding flow. |
| 5 | exercise_db_sport vocabulary alignment | Manually confirm framework discipline names (0A) match exercise DB sport names (0B) exactly. Resolve mismatches in bridge table before ETL. |
| 6 | Sheet 3 col 7 deprecation | Once Sheet 4 is complete and ETL'd, remove col 7 from ETL source. Note deprecation in sheet. |
| 7 | Seasonality handling | Not a Layer 0 problem. Handled at query layer: intersect discipline requirements against locale availability (months available for water/snow access). Verify that the locale profile fields in the onboarding schema are month-granular, not just yes/no. |
| 8 | Age-adjusted ramp rates | Query layer is athlete-aware. Pre-selects the correct ramp rate (standard / 40–44 / 45–54 / 55+) using athlete age from Layer 1 before building the payload. No selection logic needed in the prompt. |

---

## What Is Not Yet Designed

### Output storage tables (Layers 1–5)
Each prompt layer produces a structured output that needs to be stored and versioned. The per-user storage schema has not been designed. Tables needed:

```
per_user_data
├── athlete_profiles          Layer 1 output
├── race_context              Layer 2 output, per user per race
├── layer_3_evaluations       One row per user per sub-prompt (3A–3F)
├── training_plans            Layer 4 output, versioned per user
├── supplemental_outputs      Layer 5A, 5B, 5C per user
└── hitl_decision_log         All decisions + dismissals, append-only
```

These are net-new tables with no conflict risk against existing app schema. Can be specced independently of the onboarding gap analysis.

### User profile / onboarding tables
Cannot be specced without knowing:
1. What the current app database already has (need schema export or table list)
2. What the onboarding flow collects and in what order
3. What needs to extend existing tables vs. replace them

**This is the blocker for next session.**

### Layer 1–5 prompts
None written yet. Correct sequencing: onboarding flow → database gap analysis → schema spec → prompt design. Prompts reference specific field names; writing them before the schema is locked causes rework.

---

## Files in This Project (Reference)

| File | What it is | Layer |
|------|-----------|-------|
| `Sports_Framework_v3.xlsx` | Sport rule sets — periodization, discipline library, pairing matrix, phase loads, team formats | 0A |
| `Sports_Framework_Handoff_v2.md` | Full documentation of Sports_Framework_v3.xlsx schema and decisions | 0A |
| `AR_Exercise_Database_v17.xlsx` | Exercise library — 245 exercises × 16 columns, 1,068 sport mappings | 0B |
| `AR_Exercise_Database_Documentation.md` | Full schema documentation for the exercise database | 0B |
| `AR_Athlete_Onboarding_Schema.md` | Structured data model for athlete onboarding — what gets collected, why, and how it maps to database queries | Layer 1 |
| `Training Plan App — Full System Architecture` | Consolidated system design document — the authoritative reference for all layers | All |
| `Layer0_ETL_Spec.md` | Output from this session — full ETL spec for Layer 0 | 0A + 0B |

---

## Next Session Agenda

**Primary goal:** Design the user onboarding flow.

This matters before touching the database because:
- The onboarding flow determines what data is collected, in what order, and what's required vs. optional
- That determines what tables are needed and what columns are mandatory
- Without that, any database schema work is guesswork that will need to be redone

**Specific questions to answer in the next session:**

1. What does a new user see and do from account creation through first plan generation? Step by step.
2. What is collected upfront at account creation vs. deferred to plan setup?
3. What is collected via form vs. pulled from connected services (Garmin, Strava, FIT files)?
4. What is the minimum viable data set to generate a first plan? What's optional?
5. How does a returning user update their profile — inline editing, a dedicated settings flow, or prompted updates?
6. How does travel / locale switching work from the user's perspective? Is it self-managed or does the app prompt?

**Secondary goal:** Once the onboarding flow is clear, do a gap analysis against the current database schema. For that, bring:
- Current database table list and key columns (schema dump preferred)
- Current data format for the "single prompt" that is being replaced

**Do not start prompt design until the above is resolved.** Prompts reference field names. Field names come from the schema. Schema comes from the onboarding flow.
