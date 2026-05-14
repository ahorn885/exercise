# §5 Query Layer Decisions + Sports Framework Restructure — Session Handoff

**Date:** 2026-05-07
**Predecessor:** `Query_Layer_Spec_Handoff.md`
**Status:** All five §5 query layer structural decisions locked. Substantial Sports Framework restructure done as supporting work (D-008 split; D-030 + D-031 removed). Substitution table populated for all substitutable disciplines (91 entries). Spec rewrite (`Layer0_ETL_Spec_v3.md`) and tactical populate work remain for next session.
**Next chat starts with:** Tactical populate (steps 1a-1d in Next Session Plan), then `Layer0_ETL_Spec_v3.md` drafting.

---

## TL;DR

This session was supposed to lock §5 query layer structural decisions and produce a v3 spec rewrite. Decisions all locked. Spec rewrite deferred to next session because two upstream pieces of work surfaced and ate the time:

1. **Onboarding spec patches** from the prior session needed application — done. v2.0 → v2.5 across the session (joint mechanical split, bone split added on top).
2. **Sports Framework restructure** — Andy's domain insights surfaced two real data-model issues during substitution work: D-008 needed splitting into flat-water vs whitewater kayaking, and D-030/D-031 (marathon paddling/swimming) weren't really distinct training disciplines. Restructured. Then real values populated for new D-008b in pairing matrix and AR phase load.
3. **Substitution table populated** as a parallel sheet in Sports Framework — 91 substitution rows + 3 training gaps. Ready for ETL into `layer0.discipline_substitutes`.

What's left: small populate tasks (~1-3 hours) + the actual `Layer0_ETL_Spec_v3.md` draft + ETL re-run. Sequence locked: populate → spec → ETL.

---

## Files at end of session

| File | Latest version | Project status | Action needed |
|---|---|---|---|
| `Athlete_Onboarding_Data_Spec_v2.md` | v2.5 (in `/mnt/user-data/outputs`) | v2.0 in project | Upload v2.5 to overwrite |
| `Sports_Framework_v9.xlsx` | v9 (in `/mnt/user-data/outputs`) | v6 in project | Upload v9 to project |
| `Layer0_ETL_Spec_v2.md` | v2 (in project) | unchanged | No change this session; v3 to be drafted next |

Predecessor handoff `Query_Layer_Spec_Handoff.md` is still accurate for the §5 architecture starting point but is now superseded by this doc for current state.

---

## §5 Query Layer architecture — five decisions locked

### 1. Interface shape: per-consumer typed functions over shared primitives

One typed function per downstream consumer in §9 of Layer0_ETL_Spec_v2 (eleven consumers — 2A, 2B, 2C, 2D, 2E, 3D, 4, 4.5, 5A, 5B, 5C). Each function knows exactly what its consumer needs and returns a typed payload. Underneath, shared primitives handle common operations (sport-context loader, exercise-pool filter, ramp resolver, family resolver) so logic isn't duplicated.

Reasoning: clarity for prompt design, containment of changes, eleven small contracts is bounded cost. Stored procedures rejected (deployment friction). Single catch-all rejected (opaque, accidental cross-consumer breakage).

### 2. ETL version pinning: per plan-generation pin

When a plan starts generating, the system records `etl_version_set` in the plan row. Every subsequent query for that plan uses those versions, even if a newer ETL run lands. Required for consistency within a plan, reproducibility, and the partial-update model.

Implementation note: version-set covers every source file the ETL pulls from (sport framework, exercise DB, etc.). Pinning one source but not another would be a Frankenstein.

### 3. Caching: defer build, design for it

Caching not built at launch — at handful-of-athletes scale, indexed Postgres queries are fast enough. But the query layer **must be designed cache-friendly** from day one:
- Same inputs → same outputs (deterministic)
- No side effects (pure read)
- All inputs explicit (no hidden time/state dependencies)

When caching becomes necessary (real signal: launch query >500ms), add a thin wrapper layer that intercepts function calls. Two natural invalidation triggers: ETL refresh completes (discard old version-keyed entries) and athlete profile mutates (discard athlete-keyed entries). No time-based expiration.

Tracked as launch+later Open Item.

### 4. Missing filters: three additions

- **4A — Health condition filter** mirrors injury filter. Uses `contraindicated_conditions` field on exercises (already populated post-ETL per prior handoff). Simple yes/no filter for v1; severity nuance deferred.
  - **UI gap also tracked:** there's no add/view UX for Health Conditions today (only injuries). Same UX surface, two database tables. Launch-blocker open item.
- **4B — Sport classifications** instead of single family column. Add four columns to `layer0.sports`:
  - `constituent_movements` — multi-select (running, cycling, swimming, paddling, skiing, climbing, hiking, etc.)
  - `endurance_profile` — enum (Pure endurance / Mixed / Technical-dominant)
  - `participation_format` — enum (Individual / Team / Both)
  - `multi_discipline` — boolean (or derived from `len(constituent_movements) > 1`)
  - Per Andy: only classifications that "actually matter to the way our system works" — these four do. Race format, terrain type, season are per-event or per-locale, not per-sport.
- **4C — Discipline Weighting**: return both system defaults AND athlete-overridden values. Prompt resolves and can explain.

### 5. Phase Load shape: five sub-decisions

- **A** — Disciplines return name/role/conditional flag/low-high % per phase. Bands not points.
- **B** — Strength + Mobility return as separate `accessory_load` block, NOT in `disciplines[]` array.
- **C** — Weekly Total Target parsed by ETL from free text into structured `{base: {low, high}, build, peak, taper}` hours. Original text kept as fallback.
- **D** — Notes column split into `prescription_note` (short, user-facing) and `audit_log` (sources, citations, math). Query returns prescription_note by default; audit_log on demand.
- **E** — Conditional disciplines flag in payload. Substitution + race-driven resolution lives in plan-gen, NOT query layer.
  - **Plus new field:** `default_inclusion` per sport-discipline. Three values: `included` / `excluded` / `prompt_required`. AR locked: Trail Run / Orienteering / MTB / Kayak `included`; all other AR conditionals `excluded`. Other sports still need this populated.

Math note for plan-gen: discipline percentages don't sum to 100 (AR Build = 103-142%). Bands are intentionally flexible. Query returns honestly with a note; prompt resolves to weekly-hours target, not to 100%.

---

## Sports Framework restructure (v6 → v7 → v8 → v9)

### v7: Discipline Library structural changes

**D-008 split into two distinct disciplines:**
- D-008a — Kayaking — Flat-water (Lake / Sea / Calm River). Touring and distance variants subsumed here.
- D-008b — Kayaking — Whitewater (Class II+ technical). Brace, eddy, roll prerequisites.

**D-030 Marathon Paddling — removed.** Was a sport-format classification, not a training-stimulus discipline. Canoe / Kayak Marathon sport now uses D-008a (K1/K2 variant) + D-009 (C1/C2 variant). Race-format elements (portage, drafting, ultra-distance feeding) noted on the sport row.

**D-031 OW Distance Swimming — removed.** Same logic — sport-format, not training-stimulus distinction. OW Marathon Swimming sport now uses D-004 with marathon-volume + cold-tolerance notes.

Updated everywhere: Discipline Library, Sports Index, Sport × Discipline Map, Discipline Pairing Matrix, Phase Load Allocation, Athlete Profile Data Points.

### v8: Real values for D-008b

D-008b's pairing matrix row + column originally inherited D-008a defaults. Refined with whitewater-specific values:
- ROW (after whitewater): Hiking PRE→ACC; OW Swim ACC→AVO; Road Cycle ACC→PRE (active recovery); Packraft/Canoe/Flat-water ACC→AVO (paddle stacking); Swim AR ACC→AVO; Raft ACC→AVO
- COLUMN (before whitewater): Hiking ACC→AVO; OW Swim ACC→AVO; Packraft/Canoe/Flat-water ACC→AVO; Swim AR ACC→AVO; Raft ACC→AVO
- Cross-paddle fix: R18 C10 (After D-008a → D-008b) was N/A (carried from same-discipline default), corrected to AVO

AR D-008b phase load values: BASE 0% (whitewater is technique work, not base — D-008a builds base) / BUILD 1-3% / PEAK 3-5% / TAPER 1-2%. Conditional — fires only when race specifies whitewater. When active, reduce D-008a proportionally.

### v9: Substitution data persisted

Two new sheets in Sports_Framework_v9.xlsx:

**Discipline Substitution Map** — 91 substitution rows. Schema: `Target ID | Target Name | Substitute ID | Substitute Name | Fidelity | Constraints | Category`. Flat structure ready for ETL into `layer0.discipline_substitutes`.

Coverage: 29 of 30 disciplines have substitutes. D-024 Épée Fencing has zero (training gap). D-016 Mountaineering has the most (9 substitutes — multi-component discipline).

**Discipline Training Gaps** — 3 rows. D-018 Swimrun, D-020 Alpine Descent, D-024 Fencing flagged as "no good single substitute." Plan-gen surfaces these as explicit warnings when athlete has restricted access.

---

## Substitution data model (key principles)

- **Sport-agnostic for v1.** One fidelity per (target, substitute) pair, not per-sport-context. Constraints text flags where context shifts the score. Per-sport-context overrides deferred to v2 if plan-gen testing shows too coarse.
- **Asymmetric pairings allowed** (e.g., D-026 → D-010 at 0.6 vs D-010 → D-026 at 0.45). Direction matters; both directions stored.
- **Inclusion threshold ~0.3** with commonality + equipment-access soft override. Per Andy on Nordic skiing — not a strict cutoff rule, judgment call. Cross-training fallbacks <0.3 belong in plan-gen logic, not the substitution table.
- **Multi-substitute composition** is a real gap in the model. For some disciplines (D-016 Mountaineering, D-018 Swimrun), no single substitute is good enough — composing multiple substitutes is the right answer. Open Item: plan-gen needs to recognize this.

---

## Onboarding Spec changes (Athlete_Onboarding_Data_Spec_v2.md → v2.5)

- v2.1: Header patches + integration block (§I, §J, §K, §L, Group 2, Group 3)
- v2.2: §B.1.2 re-injury decay rule (literature-grounded, per-Injury-Type)
- v2.3: §B.4.2 Auto-population launch behaviour with sex-adjusted RHR thresholds
- v2.4: §B.1.1 Joint (mechanical) split into surgical / non-surgical
- v2.5: §B.1.1 Bone split into stress fracture / non-stress

All Open Items #3 and #7 marked Integrated. Only #13 (TA / aid station fallback) remains "(integrate) — pending" and was explicitly scoped out per prior handoff.

---

## Next session plan (in order)

### Step 1: Tactical populate (~1-3 hours)

**1a. Sport classifications populate (4B implementation).** Add four columns to Sports Index. Define enum values for each. Populate per sport (~15 sports). My rec: I propose values per sport, Andy reviews and adjusts. Probably 30-45 min.

**1b. `default_inclusion` column on Phase Load Allocation (5E implementation).** Populate per sport-discipline. AR locked in this session. Apply same logic to remaining ~15 sports. 30 min.

**1c. D-004b Pool Sprint Swimming substitute.** Naming collision in my draft caused this entry to be skipped. Add 1 row to Discipline Substitution Map: D-004b → D-004 at 0.5 with constraints (covers stroke + aerobic base; loses sprint-specific intensity / pool turns / starts). 5 min.

**1d. Verify `contraindicated_conditions` on exercises.** Post-ETL handoff said this was populated during ETL. Spot-check the actual exercise DB. 5 min.

### Step 2: Layer0_ETL_Spec_v3.md drafting

Full §5 rewrite per the locked structural decisions. Plus §4 schema additions for new tables/columns:
- `layer0.discipline_substitutes` (new table)
- `layer0.discipline_training_gaps` (new table)
- `layer0.sports.constituent_movements` (new column, multi-value)
- `layer0.sports.endurance_profile` (new column, enum)
- `layer0.sports.participation_format` (new column, enum)
- `layer0.sports.multi_discipline` (new column, boolean)
- `layer0.phase_load_allocation.default_inclusion` (new column, enum)
- `layer0.exercises.contraindicated_conditions` (verify exists; add to schema doc if missing)
- `layer0.sports.sport_family` — wait, this was superseded by the four classification columns. Confirm taxonomy in 1a covers what `sport_family` would have done.

Plus §3 pre-ETL prep updates if any new transforms needed (Weekly Total Target free-text parsing per 5C; Notes column split per 5D).

Plus §2 source files list update: Sports_Framework_v9.xlsx becomes the source.

Plus §9 downstream consumption reference verification — make sure the eleven consumers still reflect the current Layer 1+ design.

Several hours of careful drafting.

### Step 3: ETL re-run

After spec v3 lands, rebuild Layer 0 with new structure. Quick if existing ETL implementation handles the new sheets cleanly; medium effort if new transforms (5C free-text parsing, 5D notes split) need new code.

---

## Open items / known unresolveds

- **Multi-substitute composition** at plan-gen layer (not query layer). Some disciplines have no good single substitute; composing multiple is the right answer. Decide treatment at plan-gen design.
- **Pairing matrix D-008b values** — refined with judgment, not whitewater-coaching expertise. A focused 30-min review by someone with actual whitewater paddle background would tighten. Not blocking.
- **AR D-008b phase load percentages** — set conservatively based on flat-water dominance assumption. Worth confirming with actual whitewater AR race data if available.
- **Sport-context substitution overrides** — substitution is sport-agnostic in v1. Add per-sport-context overrides in v2 if plan-gen testing shows too coarse.
- **Health Conditions UI gap** — no add/view UX for Health Conditions today (only injuries). Launch-blocker; tracked.
- **D-020 Alpine Descent training gap** — no off-snow substitute exists for downhill ski skill. Plan-gen flags this when athlete has no snow access.
- **D-024 Épée Fencing training gap** — no discipline-level substitutes. Plan-gen flags this when athlete cannot access fencing coach.
- **D-018 Swimrun training gap** — no good single substitute. Multi-substitute composition is the answer; tracked under that Open Item.
- **D-016 Mountaineering** explicitly appears in BOTH Vertical and Winter substitute lists in our discussion (per Andy). The data model handles this naturally — D-016 has one substitute list with 9 entries that span both contexts.
- **Naming convention for new sub-IDs** — used `D-008a` / `D-008b` for the kayak split (matching D-005a precedent, but with different semantics — D-005a was equipment variant of D-005; D-008a/b are genuinely separate disciplines). Worked fine for this case. If more splits emerge, decide whether to keep suffix style or assign sequential new IDs (e.g., D-032).

---

## Other process notes

- **Andy's preferences in active use:** concise direct responses, judgment-focused analysis, gut-check sections at end of recommendations, plain-English explanation when topics get technical (he's "not a serious coder"). Follow these in the next session.
- **No artifact / no document creation for explanations.** Andy reads in chat. Documents only when there's a real artifact to share (specs, files).
- **Restructure caution.** When restructuring data (like the D-008 split or D-030/D-031 removal), survey impact across all affected sheets first, plan operations bottom-up to avoid row-shift issues, verify orphan references are zero before declaring done. Pattern worked well in v7.
- **Substitution work is curation, not derivation.** Fidelity scores reflect informed judgment based on Discipline Library descriptions + cross-discipline transfer reasoning. Andy reviewed each category. Future-Claude: don't re-derive; trust the table unless Andy asks for refinement.

---

## Quick orientation for next-session opening message

When Andy opens the next session, it's likely with something like "let's keep going" or "let's start the populate." Suggested first move:

1. Confirm current state: `Sports_Framework_v9.xlsx` should be in project (Andy uploads it). `Athlete_Onboarding_Data_Spec_v2.md` v2.5 should be in project (Andy uploads it).
2. Start with **Step 1a — Sport classifications.** Propose enum values for `endurance_profile`, `participation_format`. List `constituent_movements` enum values (running, cycling, swimming, paddling, skiing, climbing, hiking — confirm with Andy). Then for each of the ~15 sports in Sports Index, propose values. Andy reviews chunk-by-chunk like the substitution work.
3. Move to 1b, 1c, 1d. Then transition to Step 2 (`Layer0_ETL_Spec_v3.md` drafting).
