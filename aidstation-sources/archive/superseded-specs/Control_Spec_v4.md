# Control Spec — AIDSTATION Architecture

**Status:** File-revision v4 — 2026-05-13 (post-FC-4a). v3 closed 2026-05-13 (FC-3); v2 closed 2026-05-12; v1 closed 2026-05-11.
**Purpose:** Top-level architectural map of the AIDSTATION training-plan-generation system. Describes the layer pipeline, per-layer responsibilities, data flow, and cross-layer rules. **Every per-node spec doc lives below this in the hierarchy and refers up to this doc for shared concerns.**
**Maintained:** Update whenever a new layer/node spec is added or a cross-layer rule changes.

---

## What changed in v4 vs v3

1. **§9 Doc map updated:** Layer 0 spec promoted v5 → v6 (FC-4a, 2026-05-13); Control_Spec → v4 (this file); Project_Backlog → v8. v5 marked historical.
2. **Layer 0 schema fully self-consistent against deployed.** D-41 (`terrain_types` 9-column enumeration; drift report `simulatable` type corrected) closed in v6 §4.14. D-46 (`sport_name_aliases` multi-mapping audit) closed in v6 §4.16 with full multi-mapping table; intentional framework sub-format splitting confirmed.
3. **§4.11 `sport_discipline_bridge` multiplication property documented.** Direct consequence of D-46 closure. Consumer queries joining through the bridge must dedup post-query by `exercise_id`; pattern documented with reference SQL. Layer 2D §5.2 already compliant (D-47 tracks the rationale-comment update).
4. **One small carry-forward:** D-21 (`health_condition_categories` column name) — separate `information_schema.columns` query needed. Listed in `Project_Backlog_v8` FC-4b tentative scope.
5. **No other section changes.** §§1–8 and §§10–11 unchanged from v3.

---

## What changed in v3 vs v2

1. **§9 Doc map updated:** Layer 0 spec promoted v4 → v5 (FC-3, 2026-05-13). Control_Spec → v3 (this file). Project_Backlog → v7. v4 marked historical.
2. **Layer 0 §5 query layer narrative refreshed.** v5 §5.2 mirrors per-layer 2A–2E spec signatures verbatim (D-45 closed); §5.3 canonical Layer 4 payload updated for `movement_components` + `common_injury_patterns` + `body_parts_at_risk` surfacing (post-FC-1b column promotions); §5.4 D-15 variant-key semantics made explicit.
3. **Layer 0 schema corrections (FC-3 Neon-verified):** §4.8 `cross_sport_properties.confidence` type corrected `NUMERIC` → `TEXT` (D-42); §4.16 `sport_name_aliases` UNIQUE corrected 2-col → 3-col with "one-to-one inverse" claim retracted (D-44); §4.17 `terrain_gap_rules` placeholder replaced with full 12-column deployed schema (D-40).
4. **One verification carried forward:** §4.14 `terrain_types` schema dump retry (D-41) — Neon `\d` query failed on a client-side quoting artifact; `information_schema.columns` retry queued for FC-4.
5. **No other section changes.** §§1–8 and §§10–11 unchanged from v2.

---

## What changed in v2 vs v1

1. **§9 Doc map updated:** Layer 0 spec promoted v3 → v4 (FC-2, 2026-05-12). Layer2D_Spec promoted unversioned → v1 (FC-2). Vocabulary_Audit promoted v2 → v3 (FC-2, D-39 closure). Control_Spec → v2 (this file). Project_Backlog → v6.
2. **Layer 2 family marked spec-complete through 2D.** 2D set-intersect paths now read from deployed structured columns (`exercises.movement_components`, `disciplines.body_parts_at_risk`) — the keyword-map fallbacks documented in v1 of this doc are now historical only.
3. **No other section changes.** §§1–8 and §§10–11 unchanged from v1.

---

## 1. The pipeline

```
┌─────────┐   ┌─────────┐   ┌─────────────────────────────┐   ┌────────────┐   ┌─────────┐   ┌─────────┐
│ Layer 0 │ → │ Layer 1 │ → │ Layer 2                     │ → │ Layer 3    │ → │ Layer 4 │ → │ Layer 5 │
│ Static  │   │ Athlete │   │ Sport / Equipment /         │   │ Athlete    │   │ Plan    │   │ Supple- │
│ Data    │   │ Profile │   │ Terrain / Injury /          │   │ Evaluation │   │ Gen     │   │ mental  │
│         │   │         │   │ Nutrition Classifiers (5)   │   │ + HITL     │   │         │   │ Outputs │
└─────────┘   └─────────┘   └─────────────────────────────┘   └────────────┘   └─────────┘   └─────────┘
   ETL          Onboarding      2A 2B 2C 2D 2E (parallel)        Gate           Synth          Parallel
```

Data flows left-to-right. Layer 0 is the canonical reference data; Layers 1-5 reason against it. No layer writes back to Layer 0 in normal operation (Layer 0 updates come from ETL runs against authoritative xlsx sources, not from athlete-facing flows).

---

## 2. Per-layer responsibilities

### Layer 0 — Platform reference data

**Owns:** Sports, disciplines, exercises, terrain types, equipment vocabulary, gear toggles, phase-load allocations, substitution maps, training gaps, technique foci.

**Spec docs:**
- `Layer0_ETL_Spec_v6.md` (the canonical doc; FC-4a, 2026-05-13; folds v5 + D-41 terrain_types schema enumeration + D-46 multi-mapping audit + §4.11 bridge multiplication property)
- `Layer0_Deployed_Schema_and_Drift_Report.md` (current state of truth; consulted in parallel)
- Patches `Layer0_ETL_Spec_v3_Patch_Batch_B/C/D/B_Correction.md` — folded into v4 / carried in v5 (kept for audit history)

**Source data:**
- `Sports_Framework_v10.xlsx` (0A)
- `AR_Exercise_Database_v19.xlsx` (0B)
- `Vocabulary_Audit_v3.md` (0C)

**Versioning:** `etl_version` on every row. New ETL run inserts new rows + sets `superseded_at` on prior. No overwrites. `etl_version_set = {0A: vX, 0B: vY, 0C: vZ}` is pinned at plan-generation time and threaded through every downstream call.

**21 tables** in `layer0` schema. See drift report §2 for the authoritative deployed schema.

### Layer 1 — Athlete profile + onboarding

**Owns:** Capturing everything about a specific athlete — demographics, health conditions, injuries, fitness baselines, equipment per locale, gear toggles per cluster, race goals, schedule, preferences.

**Spec docs:**
- `Athlete_Onboarding_Data_Spec_v2.md` (the canonical doc; partially complete — sections H/I/J/K/L still pending)
- `Adherence_Drop_Spec_v2.md` (Plan Management subsystem)

**Source:** Athlete-facing UI; written to per-athlete records.

**Versioning:** Per-athlete record versioning by section. Section updates trigger downstream re-computation (partial-update model — see §4).

**HITL surface:** Layer 1 is where most user input happens. HITL gates can be configured here but most plan-time HITL fires in Layer 3.

### Layer 2 — Classifier nodes (5 parallel)

All five run in parallel after Layer 1 completes. All five are query nodes (no LLM) — the **standing protocol** (see §5) drove every node away from LLM during design when the operation reduced to deterministic rule application.

**2A — Discipline Classifier** (`Layer2A_Spec.md`): athlete's framework_sport → set of disciplines with roles, weights, conditional flags, training gaps.

**2B — Terrain Classifier** (`Layer2B_Spec.md`): race terrain × locale terrain → covered set + gaps with proxies and adaptation requirements.

**2C — Equipment Mapper** (`Layer2C_Spec.md`): per-locale equipment pool × cluster gear toggles × disciplines → resolved exercise availability (Tier 1/2/3).

**2D — Injury Risk Profile** (`Layer2D_Spec.md` — drafted 2026-05-10): athlete injuries + health conditions × discipline injury patterns → exclude/downgrade exercise verdicts, per-discipline risk levels, substitute recommendations, HITL items.

**2E — Nutrition Baseline** (`Layer2E_Spec.md` — drafted 2026-05-11): athlete profile × race format × phase load → BMR + activity multiplier, daily calorie/macro targets, race-day fueling per event, supplement integration, HITL items.

**Why parallel:** No 2X depends on another 2Y's output. They all consume Layer 0 + Layer 1 directly. Plan-gen consumes all five.

### Layer 3 — Athlete Evaluation + HITL gate

**Owns:** Cross-cutting evaluation of athlete readiness — timeline viability, periodization alignment, conflict detection between 2A-2E outputs.

**Spec docs:** Not yet drafted (`Layer3_Spec.md` planned).

**HITL gate:** Required before Layer 4 runs. Any unresolved ambiguity from Layer 2 (e.g., 2A.hitl_required, 2C unresolvable equipment, 2D injury severity unclear) surfaces here for athlete confirmation.

**Output:** Either green-light to Layer 4 with confirmed inputs, or list of clarifications needed.

### Layer 4 — Plan Generation

**Owns:** Building the actual day-by-day training plan. Synthesizes 2A discipline weights + 2B terrain adaptations + 2C exercise pool + 2D filters + 2E nutrition targets into a periodized schedule.

**Spec docs:** Not yet drafted (`Layer4_Spec.md` planned).

**Type:** LLM-driven (the synthesis step is genuine reasoning, not rule application). Has a periodization validator with capped correction loop.

**HITL:** Validator may surface plan-quality issues to athlete for review.

### Layer 5 — Supplemental parallel outputs

**Owns:** Plan-adjacent advisory content — daily nutrition, supplements, 7-day clothing/conditions advisor.

**Spec docs:** Not yet drafted (`Layer5_Spec.md` planned).

**Type:** Mix of query nodes and LLM nodes. Runs in parallel with each other; consumes Layer 4 output.

---

## 3. Data flow contract

Every node produces a typed payload. Downstream consumers read it as a structured object — no free-text-parsing across layer boundaries.

### Layer 0 → Layer 2 (read-only, versioned)

Every Layer 2 node queries Layer 0 via the **query layer** — 11 typed Python functions (`q_layerXN_*_payload`), one per consumer node. The LLM never writes SQL. Query layer pattern documented in `Layer0_ETL_Spec` §5; per-layer signatures live in each `Layer2X_Spec` §3 and are mirrored in §5.2 of the canonical Layer 0 spec.

### Layer 1 → Layer 2 (per-section)

Each Layer 2 node consumes specific Layer 1 sections:

| Node | Layer 1 sections consumed |
|---|---|
| 2A | §H.2 (sport/format), §C (weighting overrides) |
| 2B | §H.2 (race terrain), §J (locale terrain) |
| 2C | §J (equipment, gear toggles), 2A output (disciplines) |
| 2D | §B (injury records, health condition records), 2A output (included disciplines) |
| 2E | §A demographics (incl. optional `ffm_kg`), §B (conditions, allergies, medications), §H.2 target events (incl. `estimated_duration_hr`, `race_specific_nutrition_restrictions`), §I lifestyle & recovery (structured form: dietary_pattern, supplements via FK to `supplement_vocabulary`, caffeine, fueling format prefs, GI triggers, salt tolerance, sleep_dep when duration > 20 hr, altitude_acclim), 2A output (disciplines + framework_sport sub-format-resolved), Plan Management state (current_phase, heat_acclim_state, expected_race_temp_c per event) |

### Layer 2 → Layer 3 (typed payloads)

All five payloads land in Layer 3. Layer 3 cross-references them for consistency (e.g., 2A includes D-010 Rock Climbing + 2C says no climbing equipment + 2D says no climbing injury history = surface as "discipline included without supporting equipment" warning).

### Layer 3 → Layer 4 (gated)

Either green-light + all 5 payloads, or HITL gate with clarifications. Layer 4 only runs after green.

### Layer 4 → Layer 5

Layer 4 plan → Layer 5 advisors. Layer 5 modules run in parallel.

---

## 4. Partial update model

Plans are not regenerated whole on every change. Each downstream node has explicit **invalidation triggers** documented in its spec (§9 in per-node specs).

| Layer 1 section change | Triggers re-run of |
|---|---|
| §A demographics (weight, height, FFM, DOB, sex) | 2E (BMR + macro targets) |
| §B injuries / current conditions | 2D, then Layer 3 + 4 |
| §B allergies / medications | 2E (supplement integration, HITL gates), then Layer 4 + 5 |
| §C weighting overrides | 2A, then Layer 3 + 4 |
| §H.2 sport/format (framework_sport) | 2A, 2B, 2E, then everything downstream |
| §H.2 race terrain | 2B, then Layer 4 |
| §H.2 estimated_duration_hr | 2E (race-day fueling tier; gates sleep_dep capture in §I), then Layer 4 + 5 |
| §H.2 race_specific_nutrition_restrictions | 2E (race-day fueling format filter), then Layer 4 + 5 |
| §I lifestyle & recovery (supplements, fueling prefs, GI triggers, caffeine, salt tolerance, sleep_dep, altitude_acclim) | 2E, then Layer 4 + 5 |
| §J equipment | 2C (only the affected locale), then Layer 4 |
| §J gear toggles | 2C (all cluster locales), then Layer 4 |
| §J locale terrain | 2B, then Layer 4 |
| §K schedule | Layer 4 only |
| §L Athlete Network | Layer 4 only (joint sessions) |

| Plan Management state change | Triggers re-run of |
|---|---|
| `current_phase` (Base/Build/Peak/Taper) | 2E (activity multiplier, macro phase scaling) |
| `heat_acclim_state` per event | 2E (race-day fueling fluid + salt adjustments) |
| `expected_race_temp_c` per event | 2E (heat acclim event adjustments) |
| Weight staleness advisory | 2E (BMR + macro targets re-run when athlete confirms new weight) |

Each layer's spec documents its own invalidation rules. Cross-layer correctness requires every spec to be honest about what it depends on.

---

## 5. The standing protocol (query-vs-LLM)

Established during Layer 2 design. For every node in the architecture, before deciding implementation:

1. **DB field audit.** Scan all Layer 0 tables for fields added since original scoping that this node should consume. Original consumer tables in spec are often incomplete.
2. **Query vs LLM.** If every operation is deterministic rule application on structured inputs (table joins, set operations, comparisons), it's a query node. Reach for LLM only when there is genuine reasoning, ambiguity, or free-text interpretation that can't be reduced to those primitives.

Nodes 2A, 2B, and 2C all dropped to query nodes under this protocol. 2D and 2E will face the same pressure during their design sessions.

**Implication:** the original spec architecture assumed 10+ LLM calls. Current state: 0-2 LLM calls in Layer 2, with main LLM work concentrated in Layer 4 (plan synthesis) and selectively in Layer 5.

---

## 6. Versioning & determinism

### etl_version_set

Pinned at plan-generation time. Every downstream call receives the same set. Prevents Frankenstein states (mid-flight version drift).

```json
{
  "0A": "v10.0",
  "0B": "v19.C",
  "0C": "v2.0-r3"
}
```

### Per-node caching

Each node spec defines a cache key including all inputs that affect output. Caching not built at launch (handful-of-athletes scale, indexed queries fast enough) but every node is **designed cache-friendly**:

- Pure read, no side effects
- Deterministic given inputs
- No implicit time/state dependencies (`NOW()` forbidden)
- All inputs explicit in function signature

When caching becomes necessary (real signal: query >500ms), add a thin wrapper layer that intercepts calls and caches results keyed by the spec's cache-key formula. Invalidation triggers (per §4) drop affected entries.

---

## 7. HITL surface

HITL gates are explicit, not implicit. The places where the system stops and waits for an athlete:

| Layer / Node | HITL trigger |
|---|---|
| Layer 1 onboarding | Standard form-completion flow |
| 2A | `prompt_required` disciplines that can't auto-resolve; unresolved sport/discipline names |
| 2B | None — terrain gaps are coaching flags, not gates |
| 2C | None — equipment unresolvability surfaces as low coverage, not a gate |
| 2D | Post-surgical injury without parseable clearance date; current Cardiac × high-load disciplines (sustained Z3+); current concussion (Neurological + 'concussion' in name); HIGH-risk discipline with no available substitute; training-gap × HIGH-risk concurrent |
| 2E | Supplement × Cardiac contraindication; race-day caffeine × Cardiac; pregnancy × stimulant supplement; pregnancy × contraindicated supplement; anaphylaxis allergy × race aid station food |
| Layer 3 | Required cross-cutting review before Layer 4 (consumes all 2D / 2E HITL items + cross-node conflicts) |
| Layer 4 | Plan validator failures that exceed the correction loop cap |
| Layer 5 | None — supplemental, advisory only |

The distinction between **coaching flag** (informational, shown in plan but doesn't gate) and **HITL gate** (system stops, athlete must respond) is documented in every node spec that produces either.

---

## 8. Cross-layer concerns

### 8.1 Drift management

`Project_Backlog.md` is the single rolling tracker for cross-layer drift, deferred items, and cleanup tasks. Updated at every layer/node boundary. Categories: Blocker / Deferred / Cleanup. See `Project_Backlog` for current state.

Final-cleanup batches (FC-1 ETL fixes, FC-2 spec v4 rewrite) run at end of Layer 2 before Layer 3 design begins. Bounded scope; if FC work exceeds 2 sessions, split.

### 8.2 Standing rules (don't violate these)

- **D-05 aggregator filter** (`AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`): every query touching `layer0.phase_load_allocation` MUST include this filter until ETL fix lands (FC-1). Currently applied in 2A; required for 2D and 2E and Layer 4. **2026-05-11 update:** cleanup half of D-05 ran in FC-1a (all 33 aggregator rows already superseded in deployed); ETL extractor code patch still pending. Standing rule stays in force until ETL patch + next clean run confirm no regression.
- **Sport naming convention** (D-17): for non-AR sub-format sports, framework_sport in queries against `phase_load_allocation` uses the sub-format ("Triathlon (Standard / Olympic)") while queries against `sport_discipline_map` use the top-level ("Triathlon"). Code-side strip logic in 2A §5.1.
- **D-21 reconciliation** (`health_condition_categories` column name): 2D and 2E match on enum *values* (system_category strings like 'Cardiac', 'Neurological'), not on column names. Whether the deployed column is called `category_name` or `system_category` is housekeeping, not correctness. Defer rename to FC-1/FC-2.
- **No FKs anywhere in layer0:** all relationships are TEXT-based by design. Be careful when superseding rows — nothing prevents orphaned references in denormalized columns.
- **Pre-flight introspection before any Layer 0 migration:** verify column existence + types before INSERT/UPDATE. Pattern established in Batch B `update_retype_keeper_exercises.sql` v2.

### 8.3 Spec doc rule

Every layer and sublayer (Layer 0, Layer 1, Layer 2A-E, Layer 3, Layer 4, Layer 5) gets its own consolidated spec doc named `LayerNX_Spec.md`. Depth standard set by `Layer2C_Spec`:

1. Purpose
2. What this node does NOT do
3. Function signature
4. Input validation
5. Algorithm (with SQL pseudocode)
6. Drift items affecting this node
7. Payload schema
8. Coaching flag rules
9. Caching & determinism
10. Edge cases
11. Performance budget
12. Open items / forward references
13. Test scenarios
14. Gut check

Design decisions do NOT live only in handoff docs. Handoffs are session bookkeeping; specs are the source of truth.

---

## 9. Doc map

Where things currently live, what's pending. **Cross-references in this map use logical names without file-revision suffix; resolve to the highest-N version present in project knowledge.**

### Layer 0
- ✅ `Layer0_ETL_Spec_v6` — canonical (shipped FC-4a 2026-05-13; D-41 terrain_types 9-column schema + D-46 multi-mapping audit findings + §4.11 bridge multiplication property; schema version still v3, file revision v6)
- 🟢 `Layer0_ETL_Spec_v5` — historical predecessor (FC-3 schema corrections + §5 query-layer rewrite; superseded by v6)
- 🟢 `Layer0_ETL_Spec_v4` — historical predecessor (FC-2 consolidation)
- 🟢 `Layer0_ETL_Spec_v3` — historical predecessor
- ✅ `Layer0_Deployed_Schema_and_Drift_Report` — current truth (still consulted; pairs with v6)
- ✅ Batch B, B-Correction, D-v1, D-v2 patches — folded into v4 / carried in v5–v6
- 🟢 Batch A and Batch C patches — referenced in v1's doc map and Batch D v2 companion-docs line, but absent from project knowledge. Reconstructed from drift report. Tracked as D-43 in Project_Backlog (archive-if-recovered, no spec change expected).
- 🟢 `Vocabulary_Audit_v3` (referenced as 0C source by v6) — Collarbone added, total 51 (D-39, FC-2)

### Layer 1
- ✅ `Athlete_Onboarding_Data_Spec_v2` — partial (§§A-C/G-H/M/N + §§I/J/K/L complete; §§D-F pending)
- ✅ `Section_I_Audit` — §I structured form audit (drafted; 10 v3 polish candidates parked as D-25)
- ✅ `Supplement_Vocabulary_Spec` — Layer 0 `supplement_vocabulary` table schema + 25 seed entries (drafted; D-26 deployed 2026-05-11 — table live in Neon dev with 25 active rows at `supp_vocab.v1.FC1`)
- ✅ `Vocabulary_Audit_v3` — canonical body parts (51) + health condition system enum + equipment categories (D-39 closed FC-2)
- ✅ `Adherence_Drop_Spec_v2` — Plan Management subsystem (predecessor work; Plan Management spec proper is D-27)
- ⏳ Remaining onboarding sections (§§D-F) — pending

### Layer 2
- ✅ `Layer2A_Spec` — backfilled 2026-05-10
- ✅ `Layer2B_Spec` — backfilled 2026-05-10
- ✅ `Layer2C_Spec` — drafted 2026-05-10
- ✅ `Layer2D_Spec_v1` — promoted to v1 in FC-2 (2026-05-12); §5.3.3 set-intersect on `movement_components` (D-22); §5.4 set-intersect on `body_parts_at_risk` (D-23); §5.5 Decision Point B locked + deployed. Keyword-map fallbacks demoted to historical.
- ✅ `Layer2E_Spec` — drafted 2026-05-11

### Layer 3+
- ⏳ `Layer3_Spec` — not yet started (HITL gate design)
- ⏳ `Layer4_Spec` — not yet started (plan generation)
- ⏳ `Layer5_Spec` — not yet started (supplemental outputs)

### Cross-cutting
- ✅ `Control_Spec_v4` — this doc (file-revision v4, 2026-05-13)
- 🟢 `Control_Spec_v3` — historical predecessor (FC-3)
- 🟢 `Control_Spec_v2` — historical predecessor
- ✅ `Project_Backlog_v8` — rolling tracker (file-revision v8, 2026-05-13; FC-4a closures D-41/D-46 + new cleanup D-47; D-21 carried to FC-4b)
- 🟢 `Project_Backlog_v7` — historical predecessor (FC-3)
- 🟢 `Project_Backlog_v6` — historical predecessor

### Architecture predecessors (historical context)
- `Training_App_Architecture_Handoff` — original architecture notes
- `Layer0_to_PlanGen_Contract_Preview` — early contract sketch
- `Query_Layer_Spec_Handoff` — query layer design
- Various `*_Handoff` files — session bookkeeping

---

## 10. Process notes

- **Spec-first philosophy.** Architecture → prompts → implementation. Resist shortcuts to code before spec lands.
- **Handoff docs are not specs.** They're session bookkeeping. Once a node is "locked," migrate the decisions to its `LayerNX_Spec` doc.
- **Handoffs that defer file edits include the edits as mechanically-applicable instructions** — str_replace-style `old_string` / `new_string` blocks, or "replace section X with verbatim content [...]". Narrative summaries like "update §3 of Control_Spec" without the new text are not acceptable. Failure mode is loud (str_replace mismatch) rather than silent drift. See memory rule #11; companion to rules #9 (session-start verification) and #10 (session-end verification).
- **File versioning convention (Option H, confirmed 2026-05-11).** Materially revised files save with a numeric revision suffix (`_v1.md`, `_v2.md`...). Each revision bumps `N` from the highest existing version. Andy uploads the new file under the bumped name — no rename, no overwrite. Old versions accumulate in project knowledge as natural history; optionally pruned. Cross-references cite the logical name without revision suffix (e.g., "see `Control_Spec` §8.2"); Claude resolves to the highest-N file via `view` at read time, not via `project_knowledge_search` (which can surface stale fragments from old revisions). **Exception:** files whose name encodes a semantic version (`Layer0_ETL_Spec_v3.md`, `AR_Exercise_Database_v19.xlsx`, etc.) bump the *semantic* version on material content changes rather than adding a file-revision suffix. Memory rule #12; companion to rules #9 / #10 / #11.
- **Project_Backlog is the only deferred-work tracker.** Per-spec open items reference back to it.
- **No artifact creation for explanations.** Specs and code only.
- **Sports Framework xlsx is source of truth for 0A.** Never reconstruct from prose.
- **etl_version increments on every Layer 0 row change; never overwrite rows.** This is the data-row rule, separate from file-versioning above.
- **Idempotent SQL with verify blocks is house style.** See Batch B/C migration scripts.

---

## 11. Gut check

**What this doc gets right:**
- One place to see the whole system. Currently scattered across 50+ docs.
- Explicit standing rules (D-05 filter, naming convention, no-FK reality, pre-flight introspection) called out so they don't get re-discovered the hard way.
- Doc map shows what exists vs what's pending — easy to see the spec-debt at a glance.
- HITL surface table is the kind of cross-cutting view that's hard to derive from per-node specs alone.

**Risks:**
- This doc is now a maintenance burden. Every new spec → update §9 doc map. Every new standing rule → update §8.2. Easy to forget.
- The "partial update model" §4 table is hard to keep correct as new sections get added to onboarding. If a new section's invalidation isn't documented, plans go stale silently.
- I've represented Layers 3, 4, 5 with placeholders. Their actual scopes may differ once they get designed. Reserve the right to revise this doc when those land.

**What might be missing:**
- Error handling / observability strategy. Not currently in any spec. Probably belongs here once we start implementing.
- Deployment model — dev vs prod environments, ETL run scheduling, etc. Currently in scattered handoff docs.
- Security / privacy boundaries — what athlete data crosses which layer boundaries. Probably matters once we have multiple athletes.

**Best argument against:** another spec doc to maintain. Counter: without it, system-level decisions either get re-litigated every session or get made implicitly without visibility. This is the meta-spec — it earns its keep by making the architectural choices legible.
