# Layer 1 — 2A + 2B Design Session Handoff

**Date:** 2026-05-09
**Predecessor:** `Layer1_2A_Kickoff_Handoff.md`
**Status:** Node 2A locked. Node 2B locked. Layer 0 terrain tables extended and populated. Ready for 2C design.
**Next chat starts with:** Node 2C — Equipment Mapper. Apply standing protocol before designing.

---

## Standing protocol — established this session

For every node in the prompt architecture, in order:

1. **DB field audit** — scan all Layer 0 tables for fields added since original scoping that this node should consume. Do not assume the original §8 consumer table in the ETL spec is complete — it isn't.
2. **Query vs LLM** — if every operation is deterministic rule application on structured inputs, it's a query node. Only reach for LLM when there is genuine reasoning, ambiguity, or free-text interpretation that can't be reduced to set operations, comparisons, or table joins.

Both 2A and 2B dropped their LLM calls under this protocol. Apply the same pressure to every remaining node.

---

## Node 2A — Discipline Classifier — LOCKED

**Type:** Query layer operation. No LLM call.

**Function signature:**
```python
q_layer2a_discipline_classifier_payload(
    framework_sport: str,        # canonical sport name — structured enum field, no alias resolution needed
    etl_version_set: dict
) -> Layer2APayload
```

**Tables queried:** `sports`, `sport_discipline_map`, `phase_load_allocation`, `discipline_training_gaps`

**NOT queried (corrections to original §8 entry):**
- `sport_discipline_bridge` removed — that's 2C/exercise-pool territory, not discipline classification
- `disciplines` table proper (ramp rates, injury patterns) — that's 2B/2D territory
- `phase_load_allocation` was missing from original §8 — added; it's the source of `default_inclusion`, `is_conditional`, and phase load bands

**Key design decisions:**
- `resolve_sport()` pre-step eliminated — `§H.2 Target Sport / Format` is a structured enum, sport name arrives clean
- `sport_name_aliases` table not needed for any structured-input flow — only relevant for NL inputs (coach notes, future chat interface)
- `role` field (Primary / Secondary / Minor / Technical) already exists on `sport_discipline_map` and `phase_load_allocation` — no schema gap
- `stimulus_components` on disciplines NOT included in 2A payload — 2C and 2D query it themselves; passing it through 2A would bundle data 2A doesn't own
- `discipline_training_gaps` IS included — if a confirmed discipline has a training gap entry, 2A flags it in the output so downstream nodes have early warning

**Output payload key fields:**
- `disciplines[]` — each with `inclusion`, `role`, `default_inclusion`, `is_conditional`, `load_weight` (system default or athlete override), `sleep_deprivation_relevant`, `training_gap` (null or structured gap record), `rationale`
- `training_gaps_summary` — `flagged_count`, `any_no_substitute`, `any_multi_substitute_candidate`
- `hitl_required` — fires on unresolved discipline selections or `prompt_required` disciplines that can't resolve from event context; does NOT fire on training gaps alone (locale context not available at 2A)
- `unresolved_flags[]` — athlete-selected disciplines not found in canonical framework

**Rationale text quality requirement (open item):** Rationale fields must meet athlete-facing quality bar — they feed the plan confirmation UI step. "Default included for Adventure Racing" is not good enough. "Trail Running is a core Adventure Racing discipline and is included in all AR plans" is. This is a templating standard, not an LLM call.

**Invalidation triggers:** `§H.2 Target Sport / Format` changes; `§H.2 Constituent Disciplines` changes; `§H.2 Navigation Requirement` changes; `§H.2 Estimated Duration` crosses 20hr threshold; `§H.2 Team Format` changes to/from relay or relay legs change; `§C Discipline Weighting` overrides change; ETL version set changes.

**Does NOT re-run when:** fitness baselines (§D/§E/§F), injury records (§B), locale/equipment (§J/§K), or schedule (§G) change.

---

## Node 2B — Terrain Classifier — LOCKED

**Type:** Query layer operation. No LLM call.

**Function signature:**
```python
q_layer2b_terrain_classifier_payload(
    race_terrain_ids: list[str],         # from §H.2 Race Terrain Type — canonical TRN-xxx IDs
    locale_terrain_ids: list[str],       # from §J Locale terrain access — canonical TRN-xxx IDs
    included_discipline_ids: list[str],  # from 2A output — for scoping relevance
    etl_version_set: dict
) -> Layer2BPayload
```

**Tables queried:** `terrain_types`, `terrain_gap_rules`

**Original §8 entry:** listed only `terrain_types` as a vocabulary lookup with no athlete inputs — this was wrong. 2B requires athlete terrain inputs and the new `terrain_gap_rules` table to be meaningful. The original function signature `q_layer2b_terrain_classifier_payload(etl_version_set: dict)` with no athlete data was a design gap, now corrected.

**Core logic (all deterministic):**
- Set difference: `race_terrain_ids` − `locale_terrain_ids` = gap terrain IDs
- For each gap: join `terrain_gap_rules` on `target_terrain_id`; match `proxy_terrain_id` to best available in `locale_terrain_ids` by highest `proxy_fidelity`; if no proxy match, return NULL-proxy row (unbridgeable)
- Pass through `race_terrain` with `pct_of_race` breakdown for Layer 4 phase weighting

**Output payload key fields:**
- `race_terrain[]` — each terrain with `pct_of_race` and `available_locally` flag
- `terrain_gaps[]` — each gap with full gap rule data: `gap_severity`, `adaptation_weeks`, `proxy_fidelity`, `proxy_methods[]`, `uncoverable_stimulus[]`, `prescription_note`, `coaching_flag`
- `coaching_flags[]` — structured warnings surfaced in plan output (e.g., whitewater requires coached introduction); NOT HITL gates
- `summary.min_adaptation_weeks_needed` — plan-gen uses this against training window for timeline viability; feeds into 2E
- `summary.any_unbridgeable` — plan-gen surfaces explicit warning in plan for unbridgeable gaps
- `summary.worst_fidelity` — overall terrain preparation fidelity signal

**Coaching flag vs HITL distinction:** Whitewater gap (and any other "requires coached introduction" case) surfaces as a `coaching_flag` in the plan output — a note or warning the athlete sees in their plan. It is NOT a HITL gate. HITL gates are for plan generation blockers; coaching flags are for plan content advisories.

**Invalidation triggers:** `§H.2 Race Terrain Type` changes; `§J Locale terrain access` changes; ETL version set changes.

**Does NOT re-run when:** discipline list changes (2A output), fitness baselines, equipment access, or schedule change.

---

## Layer 0 additions made this session

### terrain_types extended (migrate_terrain_types.sql — EXECUTED)

Added 7 new columns to `layer0.terrain_types`:
`terrain_id`, `category`, `requires_elevation`, `technical_surface`, `environment`, `simulatable`, `simulation_note`

Superseded original 15 minimal-name rows. Inserted 16 structured rows at `etl_version = '0C-v2.0-r2'`.

Terrain IDs: TRN-001 through TRN-016. Key splits from original vocab:
- "Trail" → TRN-002 Groomed Trail + TRN-003 Technical Trail (meaningfully different for plan-gen)
- "Hill / Mountain" → TRN-004 Hill / Rolling + TRN-005 Mountain / Alpine (different gap rules)
- Added TRN-016 Indoor / Gym as explicit terrain type (proxy destination for snow/mountain gaps)

### terrain_gap_rules created and populated (populate_terrain_gap_rules.sql — EXECUTED)

New table `layer0.terrain_gap_rules`. 12 rows at `etl_version = '0C-v2.0-r2'`.

Coverage:
- Mountain / Alpine gaps: 3 rows (proxy = Road, Hill/Rolling, Indoor/Gym)
- Technical Trail gaps: 2 rows (proxy = Groomed Trail, Road)
- Fell / Moorland gap: 1 row (proxy = Groomed Trail)
- Open Water / Ocean gap: 1 row (proxy = Pool)
- Flat Water gap: 1 row (proxy = Pool)
- Whitewater gap: 1 row (proxy = Flat Water)
- Snow / Winter Alpine gap: 1 row (proxy = Indoor/Gym) — partial severity; descent flagged unbridgeable in prescription_note
- Rock Wall (Outdoor) gaps: 2 rows (proxy = Climbing Gym at 0.75; proxy = NULL at 0.00 unbridgeable)

Both scripts: idempotent, safe to re-run. Committed to `etl/sources/` in repo.

---

## ETL spec update needed (not yet done)

ETL spec v3 §8 consumer table needs two corrections:

| Node | Current (wrong) | Correct |
|---|---|---|
| 2A | `sports, sport_discipline_map, sport_discipline_bridge` | `sports, sport_discipline_map, phase_load_allocation, discipline_training_gaps` |
| 2B | `terrain_types` | `terrain_types, terrain_gap_rules` |

Also: `terrain_gap_rules` needs to be added to §4 schema list as a new table (currently only in the populate script, not the spec). Add alongside `discipline_substitutes` and `discipline_training_gaps` pattern.

Recommend batching this update with any other spec corrections that accumulate during Layer 1 design — do one spec revision pass after all Layer 2 nodes are locked rather than updating after each node.

---

## Open items from this session

| # | Item | Owner | Blocking? |
|---|---|---|---|
| A | §J Locale terrain access must use canonical TRN-xxx IDs as controlled vocabulary when drafted (batch 4). If drafted as free text, 2B breaks. | Onboarding spec drafting | Blocks 2B runtime (not 2B design) |
| B | Rationale text in 2A output must meet athlete-facing quality bar — templated strings need plain-language rewrites | Prompt build | Blocks plan confirmation UI |
| C | Plan confirmation UI step design — surface 2A discipline list + 2B terrain gaps to athlete before Layer 4 runs | Product design | Pre-Layer 4 build |
| D | ETL spec v3 §8 corrections (2A and 2B consumer table entries) + terrain_gap_rules added to §4 | Spec maintenance | Not blocking design work |
| E | §H.2 Race Terrain Type field must use TRN-xxx IDs as its controlled vocabulary (confirm this is the case when §H batch 4 lands) | Onboarding spec | Blocks 2B runtime |

---

## Node 2C — what to read before starting

From the ETL spec §8, 2C (Equipment Mapper) currently listed as consuming:
`equipment_items, sport_specific_gear_toggles, sport_exercise_map, exercises`

Before designing 2C, apply the protocol:
1. Audit all Layer 0 tables for fields added since original scoping that 2C should consume — suspect candidates: `contraindicated_conditions` on exercises (confirmed in schema), `equipment_substitutes_standard` and `equipment_substitutes_improvised` on exercises, `physical_proxies` JSONB on exercises, `progression_id` / `regression_id` on exercises
2. Query vs LLM — 2C maps athlete equipment access to exercise pool; most of this is filtering logic, but the substitution resolution (Tier 1→2→3→4 fallback) may be complex enough to warrant scrutiny

From the athlete onboarding spec, 2C inputs will draw from:
- §J Locale equipment inventory (per active locale)
- §J Sport-specific gear readiness toggles (12 toggles)
- 2A output (discipline IDs) — to scope the exercise pool to relevant disciplines

Key reference docs for 2C session:
- `Layer0_ETL_Spec_v3.md` §4.12 (equipment_items, exercises schemas)
- `Vocabulary_Audit_v2.md` Section 3 (equipment canonical list) and Section 4 (gear toggles)
- `AR_Exercise_Database_Documentation.md` (four-tier equipment fallback logic)
- `Athlete_Onboarding_Data_Spec_v2.md` §J (when batch 4 lands — currently pending)

---

## Process notes (carry-forward)

- No artifact / no document creation for explanations — read in chat; documents only for real deliverables (specs, SQL scripts)
- Don't propose Layer 0 schema changes unless the node design genuinely demands them — but DO add them when they're needed to avoid LLM calls (terrain_gap_rules is the model for this)
- Source SQL scripts to `etl/sources/` in repo, following populate_stimulus_components.sql pattern
- Sports Framework xlsx is source of truth for 0A — never reconstruct from prose
- Andy's preferences: direct, judgment-focused, gut check at end of recommendations, no praise/hype
