# Handoff — Layer 2D Done / §I Structured / Layer 2E Kickoff

**Date:** 2026-05-10
**Outgoing session:** Layer 2D spec design, §I drafting + audit + structuring pass
**Next session:** Layer 2E — Nutrition Baseline spec design

---

## Status at handoff

**Layer 2 spec design progress:**
- ✅ 2A Discipline Classification — drafted
- ✅ 2B Terrain Resolution — drafted
- ✅ 2C Equipment Resolution — drafted
- ✅ 2D Injury Risk Profile — drafted this session
- ⏳ **2E Nutrition Baseline — next**

**Layer 1 onboarding progress (relevant to 2E):**
- ✅ §A Demographics — drafted
- ✅ §B Health Status (including food allergies, GI/Endocrine/Cardiac conditions, medications) — drafted
- ✅ §H Target Events (including race-specific nutrition restrictions, estimated duration) — drafted
- ✅ §I Lifestyle & Recovery — drafted + audited + structured this session
- ⏳ §J Locales — still pending (NOT blocking 2E)
- ⏳ §K Locale Schedule — still pending (NOT blocking 2E)
- ⏳ §L Athlete Network — still pending (NOT blocking 2E)

**FC-1 column-promotion blockers stacking up:**
- D-22 — `exercises.movement_components TEXT[]` (~600 cells curation)
- D-23 — `disciplines.body_parts_at_risk TEXT[]` (~150 cells curation; seed drafted in Layer2D_Spec.md §5.5)
- D-26 — `supplement_vocabulary` Layer 0 table (~30-45 min; schema + 25 seed entries in Supplement_Vocabulary_Spec.md)

All three are FC-1 work, blocking 2D + 2E implementation (NOT design).

---

## What got accomplished this session

### Part 1 — Layer 2D spec from scratch

Designed Layer 2D Injury Risk Profile at the 14-section depth standard established by Layer2C_Spec.md. Pure query node, no LLM. Replaces the unbuildable v3 stub `q_layer2d_injury_risk_profile_payload(disciplines, etl_version_set)`.

**Four decisions locked:**
1. **Severity → verdict mapping:** Acute=Exclude, Recovering=Downgrade, Chronic-Managed=Downgrade, Post-surgical=Exclude+HITL, Structural-Permanent=Downgrade. Conservative defaults. Revisit after first-cohort feedback.
2. **Body-part keyword map location:** new structured column `disciplines.body_parts_at_risk TEXT[]` (D-23 promoted to 🔴 Blocker for FC-1). Removes false-negative risk of substring matching against authored free text.
3. **Movement-constraint keyword map location:** new structured column `exercises.movement_components TEXT[]` (D-22 promoted to 🔴 Blocker for FC-1). Set-intersect against B.3 enum tokens; mathematically exact.
4. **Medications interactions:** deferred to future work, not v1 (D-24 added).

**Algorithm:** three independent verdict signals per exercise (body-part contraindication, condition contraindication, movement-component contraindication), strongest verdict wins. Per-discipline risk via set-intersect against `body_parts_at_risk`. Discipline substitution via `discipline_substitutes` lookup with back-check tagging substitutes that share at-risk body parts. HITL gates: post-surgical without clearance, current cardiac × high-load disciplines, current concussion, HIGH-risk discipline with no substitute, training-gap × HIGH-risk concurrent.

**Andy's left-wrist injury was test scenario 13.1** — concrete acceptance criteria documented.

### Part 2 — §I drafting + audit + structuring

§I Lifestyle & Recovery was slotted into the onboarding spec from `Sections_IJKL_Groups23_v2_Batch.md` material. Then audited (Section_I_Audit.md) with 7 fix-now items applied and 10 v3 candidates parked.

Then a second pass restructured the four free-text fields so 2E doesn't depend on LLM interpretation:
- **Supplements** — now a record set with FK to new `supplement_vocabulary` Layer 0 table (25 seed entries; D-26 promoted to FC-1 Blocker)
- **Fueling Format comments** — replaced with structured Fueling Shift Triggers multi-select (Hour-based / Intensity-based / GI-state-based / Temperature-based / None) with structured sub-fields
- **GI Triggers** — multi-select common categories + per-category structured "specifics" free-text sub-field (2E reads categories; Layer 4 reads specifics)
- **Sleep Deprivation** — split into 6 structured fields (Hours Awake, Notable Incidents, Coping Strategies Tried/Effective/Failed) + small Brief Context free text explicitly contracted as Layer 4 / journaling only, NOT 2E input

Net result: 2E has zero LLM-interpretation dependency on §I.

### Part 3 — Control_Spec corrections

- §2: 2D blurb removed "not yet drafted"
- §3 Layer 1 → Layer 2 table: 2E row corrected — was pointing to "§F nutrition prefs" (wrong — §F is Performance Testing); now correctly lists §A demographics + §H.2 race format/duration + §B (food allergies, GI/endocrine) + §H race-specific nutrition restrictions + §I (full list of sub-fields including supplements) + `supplement_vocabulary` + 2A output
- §4 partial-update table: same §F → §I rename; added §B trigger for 2E (food allergies + GI/endocrine conditions feed nutrition); added §H race-specific nutrition restrictions as its own row; added §I as its own row; broke out §H.2 estimated duration as its own row (triggers 2A conditional disciplines + 2E fueling baseline)
- §7 HITL surface: 2D row filled in with specific named triggers
- §8.2 standing rules: added D-21 reconciliation note
- §9 doc map: added Supplement_Vocabulary_Spec, Section_I_Audit, Layer2D_Spec; updated Layer 1 status

### Part 4 — Project_Backlog updates

New items added:
- D-21 — `health_condition_categories` column name reconciliation (deferred for FC-1)
- D-22 — `exercises.movement_components TEXT[]` (🔴 Blocker for 2D implementation, FC-1)
- D-23 — `disciplines.body_parts_at_risk TEXT[]` (🔴 Blocker for 2D implementation, FC-1)
- D-24 — Medications interaction surface (deferred, future work)
- D-25 — §I v3 polish candidates (pointer to Section_I_Audit.md)
- D-26 — `supplement_vocabulary` Layer 0 table (🔴 Blocker for 2E implementation, FC-1)

FC-1 scope updated to include D-22, D-23, D-26 as required (no longer optional). Added capacity note: D-22 is the largest item; may force FC-1a/FC-1b split.

---

## Files produced or modified this session

**New:**
- `Layer2D_Spec.md` — Layer 2D Injury Risk Profile spec
- `Supplement_Vocabulary_Spec.md` — new Layer 0 vocab table
- `Section_I_Audit.md` — audit pass on onboarding §I

**Modified:**
- `Athlete_Onboarding_Data_Spec_v2.md` — §I drafted + audited + structured
- `Control_Spec.md` — 6 sections updated (§2, §3, §4, §7, §8.2, §9)
- `Project_Backlog.md` — 6 new drift items (D-21 through D-26); FC-1 scope updated

---

## Agenda for next session

### Layer 2E — Nutrition Baseline spec design

**What 2E probably does** (subject to design refinement):
- Daily calorie target (BMR + activity multiplier from sport/format + training load)
- Macro split (CHO/protein/fat g/day, scaled to phase and discipline mix)
- Race-day fueling baseline (g CHO/hr, mg Na/hr, fluid mL/hr scaled to event duration + temperature + athlete tolerances)
- Supplement integration (athlete's current protocol cross-referenced; race-day-specific supplements integrated; contraindication coaching flags)
- Dietary-pattern adjustments (Vegan: B12 + iron flags; Low-FODMAP: race fueling adjustments; allergies blocked)
- Sleep-deprivation fueling overlay for >20hr events
- Cross-reference outputs from 2A (disciplines drive activity multiplier) and Layer 1 (athlete data drives everything else)

**What 2E probably does NOT do:**
- Generate meals or recipes (Layer 4 or out of scope)
- Real-time fueling adjustments mid-race (Plan Management / Layer 4)
- Hydration tracking during training (Plan Management)
- Body composition recommendations (potential ethical concerns; defer)

**Design questions to resolve in 2E spec:**
- Calorie calculation method: Harris-Benedict / Mifflin-St Jeor / Cunningham (best for athletes)? Activity multiplier source?
- Macro split: which method (g/kg body weight, % calories, periodized by phase)?
- Race-day fueling band defaults — by event duration tier? By sport?
- Coaching flag thresholds for supplement contraindications
- Output structure — analogous to 2C `ResolvedExercise` records
- HITL gate triggers — disordered eating signals from athlete inputs? Severe caloric mismatches?
- Type: query node, prompt node, or hybrid?

### Pre-work reading order

1. **`Control_Spec.md`** — architectural framing, especially §3 (Layer 1 → Layer 2 inputs for 2E), §4 (partial-update model for §I/§B/§H changes), §7 (HITL surface)
2. **`Layer2C_Spec.md`** — depth standard for spec format
3. **`Layer2D_Spec.md`** — most recent analog; uses similar structured-data set-intersect pattern that 2E may borrow
4. **`Athlete_Onboarding_Data_Spec_v2.md`** — read §A (demographics), §B (food allergies + GI/endocrine + cardiac conditions), §H (target events + race-specific nutrition restrictions + estimated duration), and especially **§I (full)** including the consumption-split notes
5. **`Supplement_Vocabulary_Spec.md`** — read §4 (how §I.1 records consume it) and §5 (how 2E and Layer 4 consume the metadata)
6. **`Layer0_Deployed_Schema_and_Drift_Report.md`** — note any 2E-relevant Layer 0 tables (`phase_load_allocation`, `phase_load_weekly_totals`, `cross_sport_properties` for LIT ratios, `sports.endurance_profile`)
7. **`Project_Backlog.md`** — D-21, D-22, D-23, D-26 status; any 2E-relevant open items
8. **`Section_I_Audit.md`** — v3 candidates to be aware of (don't try to address; documented for future)
9. **Reference materials in project root** — strength training, nutrition/hydration articles from various sources (BendRacing, WLDNCO fueling guides, TrainRight nutrition pieces)

### Probable 2E scope sketch

Like 2D, 2E is likely a query node (or hybrid query + small prompt for race-day fueling rationale). Structured data on both sides — athlete data is structured per §I restructure; Layer 0 sport/discipline data drives multipliers. The LLM-interpretation dependency was the worry; that's been removed with the structuring pass.

If 2E ends up being a prompt node (genuine reasoning required for some calculation), pin down exactly what the LLM is doing and why a rule wouldn't suffice — same discipline applied to 2D.

---

## Open items requiring Andy decision before or during next session

| # | Item | Status |
|---|---|---|
| 1 | **Supplement `evidence_quality` rating source** for FC-1 curator — anchor on AIS rankings, Examine.com synthesis, or other single source for consistency. Not 2E spec blocking but FC-1 will need the answer. | Awaiting Andy |
| 2 | **Sub-format selection mechanism** (D-17 / sport naming convention mismatch) — for 2E to pull the right `phase_load_allocation` row, athlete's race goal needs to map to a sub-format (e.g., Triathlon → Standard / Olympic / Half Ironman / Ironman). This is a Layer 1 §H design question that may surface during 2E spec work. Not currently captured. | May surface in 2E |
| 3 | **2E type** — query node, prompt node, or hybrid? Default presumption: query node (consistent with 2A-2D). Confirm during spec design. | Decide during 2E |
| 4 | **Calorie calculation method** — Mifflin-St Jeor is most common; Cunningham is best-for-athletes if FFM is known. §A captures body weight but not FFM. | Decide during 2E |

---

## What NOT to do prematurely

- **D-22, D-23, D-26** — all 🔴 Blockers but for *implementation*, not design. FC-1 owns them. Don't pre-curate; the spec-first sequencing is intentional.
- **§J, §K, §L drafting** — not blocking 2E. If they get touched, it's because something else is broken.
- **Layer 0 schema changes** beyond what the three blockers spec out — drift items D-21 and others stay parked.
- **Layer 3 / 4 / 5 design work** — strictly post-Layer-2 + post-FC-1 + post-FC-2.
- **Implementation of any spec'd layer** — design-first is the standing discipline.

---

## Critical context that must carry forward

**Standing protocols:**
- Query node vs. prompt node test: structured data inputs + deterministic rules = query node. Don't reach for LLM where rules suffice.
- 14-section spec template per Layer2C_Spec.md depth standard
- Update Control_Spec §9 doc map at end of every spec
- Update Project_Backlog between sessions; promote 🟡 → 🔴 if next node's scope intersects

**Andy's preferences (from userPreferences):**
- Direct, no praise/hype/filler
- Concise but not compressed; let ideas breathe
- Match confidence to reality; flag tradeoffs
- Tell the truth — say what's weak or flawed
- End plans with quick gut check (risks, blind spots, best argument against)
- Flag long/messy chats for handoff (this doc)

**Andy is the test athlete** for PGE 2026 (July 17-19, 48-56hr expedition AR). Active wrist injury (Chronic-Managed, Left wrist, Pain with wrist extension + Pain with loading). PGE specifics encoded in test scenario 13.1 of Layer2D_Spec.md.

**Spec-first philosophy:** architecture → prompts → implementation. Resist shortcuts. FC-1 / FC-2 land at end of Layer 2 design before Layer 3 design starts.

---

## Files in project as of this handoff (relevant subset)

| File | Status | Purpose |
|---|---|---|
| `Control_Spec.md` | ✅ Current | Architecture overview |
| `Project_Backlog.md` | ✅ Current (D-26 latest) | Rolling tracker |
| `Layer2A_Spec.md` | ✅ Drafted | Discipline classification |
| `Layer2B_Spec.md` | ✅ Drafted | Terrain resolution |
| `Layer2C_Spec.md` | ✅ Drafted | Equipment resolution |
| `Layer2D_Spec.md` | ✅ Drafted | Injury risk profile |
| `Layer2E_Spec.md` | ⏳ NEXT | Nutrition baseline |
| `Supplement_Vocabulary_Spec.md` | ✅ Drafted | Layer 0 vocab table |
| `Section_I_Audit.md` | ✅ Drafted | §I audit pass |
| `Athlete_Onboarding_Data_Spec_v2.md` | ✅ §A-C/G-I/M/N drafted | Layer 1 onboarding |
| `Layer0_ETL_Spec_v3.md` | ✅ Current (v4 pending FC-2) | Layer 0 ETL spec |
| `Layer0_Deployed_Schema_and_Drift_Report.md` | ✅ Current | Layer 0 truth |

---

*End of handoff. Next session: open with this doc, then move to Layer2E_Spec.md design.*
