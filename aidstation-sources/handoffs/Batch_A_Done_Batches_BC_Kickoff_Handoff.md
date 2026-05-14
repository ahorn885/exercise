# Layer 1 — Batch A Done, Batches B/C Kickoff Handoff

**Date:** 2026-05-09
**Predecessor:** `Layer1_2B_Done_2C_Kickoff_Handoff.md`
**Status:** Batch A shipped. 2C design progressed but not yet consolidated. Batches B and C scoped, ready for execution.
**Next chat starts with:** Batch B execution (technique-focus migration), or 2C spec consolidation — Andy's call which first.

---

## TL;DR

This session locked the 2C per-locale model, made multiple Layer 0 cleanup decisions, and shipped Batch A. The 2C node design is substantively done but not yet written up as a final spec. Batches B (technique-focus migration) and C (bike/load curation) are fully scoped pending execution.

Two self-inflicted bugs surfaced and got fixed mid-session (ON CONFLICT regression, parser-fix misdiagnosis). Lessons-learned captured at bottom.

---

## Batch A — DONE

Five files shipped, all run cleanly:

| File | Purpose | Status |
|---|---|---|
| `Vocab_Audit_v2_Batch_A_Patch.md` | Vocab Audit edits | Apply to source doc |
| `migrate_gear_toggles_also_satisfies.sql` | Schema: add `also_satisfies TEXT[]` to `sport_specific_gear_toggles` | Run |
| `populate_gear_toggles_batch_a.sql` | Climbing — roped → Rappelling implication; supersede Bouldering | Run |
| `populate_equipment_items_batch_a.sql` | Add `Bench press rack` canonical item | Run (after ON CONFLICT fix) |
| `cleanup_sport_exercise_map_header_residue.sql` | DELETE residue rows where `sport_name = 'Sport'` | Run (cleared all rows incl. historical) |

`ETL_Parser_Fix_Header_Offset.md` was drafted but not shipped — root-cause analysis was wrong (extractor was already correct). Issue was historical residue at stale etl_version, not a current parser bug. The cleanup SQL handled it. Parser fix doc dropped.

Net Layer 0 state changes:
- `sport_specific_gear_toggles`: +1 column (`also_satisfies`); 1 row populated; 1 row superseded (Bouldering)
- `equipment_items`: +1 row (Bench press rack)
- `sport_exercise_map`: -N rows (all `sport_name = 'Sport'` residue removed; both active and historical)

---

## 2C design — locked decisions this session

### Per-locale model (was per-cluster)

2C runs **per locale**, not per cluster. Equipment is locale-scoped (bench press at Home ≠ bench press at Partner's). Gear toggles are cluster-scoped (climbing kit travels with the athlete). A single session is locale-bound (no mixing equipment across locales). A single training day can split disciplines across cluster locales.

Function signature:
```python
q_layer2c_equipment_mapper_payload(
    locale_id: str,
    locale_equipment_pool: list[str],            # this locale only
    cluster_locale_ids: list[str],               # for context
    cluster_gear_toggle_states: dict[str, bool], # unioned across cluster
    included_discipline_ids: list[str],          # from 2A
    etl_version_set: dict
) -> Layer2CPayload
```

2C runs N times per athlete where N = number of locales in cluster + travel overlays. Layer 4 picks per-session which 2C output applies.

Caching key: `(athlete_id, locale_id, etl_version_set, cluster_toggle_state_hash)`.

### Multi-cluster plans confirmed

Plan-gen handles known clusters at gen time; plan updates handle unknown clusters discovered on arrival (hotel-gym flow). Latency target for plan-update path: <2s for a single cluster's 2C run + cache write. Bounded scope (one cluster, ~211 exercises, deterministic Postgres) makes this trivially achievable.

### HITL adjustment

Equipment-vocab HITL dropped — structured input via Layer 0-sourced dropdowns makes unresolved-name impossible by construction. Same for toggle vocab. `unresolved_flags[]` becomes a logged ETL-drift error, not a HITL gate.

### Coaching flags vs HITL (following 2B pattern)

HITL only fires on truly unresolvable input (won't happen with structured input). Coverage warnings (discipline < 50%, all Critical-priority dropped, gear toggle OFF for included discipline) are coaching flags surfaced in plan output, not blockers.

### Tier 2 vs Tier 3 split preserved

Migration spec collapsed Tier 2 (standard substitute) and Tier 3 (improvised) into one mechanism. 2C design preserves the distinction — Layer 4 needs both to render the documented athlete-facing UX ("Try improvised X, OR do proxy Y").

### Generic equipment rejected

No `Bike (generic)` token, no `satisfied_by_any[]` column. Specific tokens only. v19 had no generic-bike tokens (cleanup pass already done). Surfaced 16 rows with implicit-OR semantics on multi-token `equipment[]` arrays — fixed via primary/substitute curation in Batch C.

### Toggle implication via data path

`sport_specific_gear_toggles.also_satisfies TEXT[]` column added (Batch A). Populated only with Climbing — roped → `[Rappelling / abseiling]`. Bouldering removed (not a sport in v19). Mountaineering, ski setups, all others stand alone.

### Bouldering dropped from toggles

Not a sport in v19 (zero exercise mappings, zero gated exercises). Toggle removed from `sport_specific_gear_toggles`. Vocab Audit §4.1 renumbered (10 active toggles + 1 note).

---

## Batches B and C — SCOPED, NOT YET EXECUTED

### Batch B — Technique-focus migration

**Drop** 41 pure-technique-no-load rows from `exercises` + `sport_exercise_map`. Includes the 6 paddle drills already identified (EX091, EX092, EX156, EX157, EX158, EX166) plus 35 others spanning navigation, MTB skill, climbing technique, trekking pole drills, pack handling, mountaineering technique, snowshoe technique, swim technique, transition drills, and others. Full list in this session's transcript under "Skill/technique sweep — 65 candidates classified".

**Create** new Layer 0 table `layer0.discipline_technique_foci` with schema:
```sql
focus_id, focus_name, description,
discipline_ids[], applicable_session_types[], applicable_terrain_ids[],
required_equipment[], required_gear_toggle,
athlete_level, priority, when_to_emphasize, source_exercise_id,
+ standard versioning fields
```

**Populate** ~30-35 focus rows from the dropped exercises (some collapse — three trekking pole drills merge into one focus with multi-cue description). Each focus row carries `source_exercise_id` for traceability.

**Retype** 12 keepers from `Technical / Skill` to better-fitting types:
- EX051, EX052, EX124, EX150, EX168 → `Aerobic / Endurance`
- EX070, EX125 → `Strength`
- EX185 (locked Aerobic / Endurance per Andy)
- EX159 → `Activation / Primer`
- EX180, EX186, EX197, EX215 → `Interval / Tempo`

**Layer 4 selection logic** (read but not encoded yet — Layer 4 design owns):
```
candidates = filter foci where:
  session.discipline ∈ discipline_ids
  AND (applicable_session_types NULL OR session.type ∈ list)
  AND (applicable_terrain_ids NULL OR session.terrain ∈ list)
  AND (required_equipment NULL OR required_equipment ⊆ session.locale.equipment)
  AND (required_gear_toggle NULL OR athlete.toggles[gate] = TRUE)
  AND athlete.level ∈ (focus.athlete_level, 'any')
selected = top 0-2 by priority, rotating across plan-week
```

### Batch C — Exercise DB curation (10 rows)

Primary/substitute split for OR-logic exercises:

| ID | Primary equipment[] | Tier 2 substitutes |
|---|---|---|
| EX073 | `[Road bike]` | Mountain bike, Gravel bike, TT Bike, Bike trainer (each named) |
| EX074 | `[Road bike]` | same set |
| EX075 | `[Road bike]` | same set |
| EX174 | `[TT Bike]` | "On road bike with clip-on aero bars" → `[Road bike]`; "On bike trainer in aero" → `[TT Bike, Bike trainer]` |
| EX185 | `[Road bike]` | Mountain bike, Gravel bike, TT Bike, Bike trainer. **Treadmill removed entirely.** |
| EX186 | `[Road bike]` | same as EX185 |
| EX197 | `[Road bike]` | same as EX185 |
| EX117 | `[Plyo box, Dumbbell]` | KB variant, Vest variant |
| EX119 | `[Plyo box, Dumbbell]` | KB variant, Vest variant. **Barbell removed.** Authoring fix: add Plyo box (currently missing). |
| EX229 | `[Barbell, Bench, Squat rack]` | "On bench press station" → `[Barbell, Bench press rack]`; "DB Bench Press" → `[Dumbbell, Bench]` |

Sequencing: Batch C runs after Batch B settles to avoid touching rows that may have been retyped.

---

## Open items carrying forward

| # | Item | Owner | Status |
|---|---|---|---|
| F | ~~Generic-bike `satisfied_by_any[]`~~ | — | RESOLVED (rejected; specific tokens only) |
| G | `sport_specific_gear_toggles.also_satisfies[]` | — | DONE (Batch A) |
| H | Post-ETL token-resolution validator | ETL maintenance | Approved, not yet implemented |
| I | §J onboarding spec uses Layer 0 vocab tables | Onboarding spec drafting (batch 4) | Confirmed; enforce when §J drafts |
| J | ~~Proximity-cluster union semantics~~ | — | RESOLVED (per-locale equipment, cluster toggles) |
| K | Skill-drill sweep follow-on (other disciplines beyond the 41) | Andy's review | Likely none — the sweep covered all `Technical / Skill` rows |
| L | UI design phase | Separate track | Not scoped; recommend dedicated session |
| M | Hotel-as-shared-entity feature | Roadmap | Deferred; out of scope |
| N | 2C spec consolidation (final write-up) | Next 2C session | Scoped, not yet written |

---

## Standing protocol — unchanged from prior handoff

For every node in the prompt architecture, in order:

1. **DB field audit** — scan all Layer 0 tables for fields added since original scoping that this node should consume. Original §8 consumer table in the ETL spec is incomplete.
2. **Query vs LLM** — if every operation is deterministic rule application on structured inputs, it's a query node. Only reach for LLM when there is genuine reasoning, ambiguity, or free-text interpretation that can't be reduced to set operations, comparisons, or table joins.

2A, 2B, and 2C all dropped to query nodes under this protocol. Apply the same pressure to 2D, 2E.

---

## ETL spec §8 corrections (still pending — batch with all Layer 1 corrections after 2D, 2E lock)

| Node | Current (wrong) | Correct |
|---|---|---|
| 2A | `sports, sport_discipline_map, sport_discipline_bridge` | `sports, sport_discipline_map, phase_load_allocation, discipline_training_gaps` |
| 2B | `terrain_types` | `terrain_types, terrain_gap_rules` |
| 2C | `equipment_items, sport_specific_gear_toggles, sport_exercise_map, exercises` | Same — but `also_satisfies` column on toggles, `equipment_substitutes_structured / physical_proxies / terrain_required` columns on exercises now in scope. |

`terrain_gap_rules` table needs to be added to §4 schema list (currently only in populate script, not the spec).

Recommend single spec revision pass after all Layer 2 nodes lock.

---

## Lessons-learned (carry-forward to future sessions)

1. **Trust schema spec over precedent.** Existing files can be wrong; the documented constraint is the source of truth. Caused the ON CONFLICT regression in `populate_equipment_items_batch_a.sql` — initially wrote it correctly per spec, then changed to match K2's pattern. K2 had the same bug and was patched before running. Should have stayed with the spec-aligned version.

2. **When proposing changes to a codebase I don't have access to, verify current state first.** Caused the parser-fix misdiagnosis. Wrote a structural fix doc for an extractor I'd never seen, based on a symptom that turned out to be historical residue, not a current bug. Should have asked the over-there session to check the current code before drafting.

3. **Cleanup scripts default to preserving audit trail.** The cleanup SQL had no `superseded_at IS NULL` guard, so it cleared both active and historical rows. Fine for junk header strings (no audit value) but wrong default for semantically meaningful data. Future cleanup scripts should explicitly state which case they handle.

---

## Process notes — unchanged

- No artifact / no document creation for explanations — read in chat; documents only for real deliverables (specs, SQL scripts, handoffs).
- Don't propose Layer 0 schema changes unless the node design genuinely demands them.
- Source SQL scripts to `etl/sources/` in repo, following established naming pattern.
- Sports Framework xlsx is source of truth for 0A; never reconstruct from prose.
- Andy's preferences: direct, judgment-focused, gut check at end of recommendations, no praise/hype.
- This isn't an AR-only app. The platform supports multi-sport endurance training across the 36+ sports in the DB. AR is a pilot use case, not the framing.
