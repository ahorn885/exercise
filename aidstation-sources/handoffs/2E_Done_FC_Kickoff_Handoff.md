# Handoff — Layer 2E Done / Layer 2 Design Complete / FC-1 Kickoff

**Date:** 2026-05-11
**Outgoing session:** Layer 2E spec design (from scratch, 14-section depth standard) + bookkeeping cleanup for prior session's drift
**Next session:** FC-1 cleanup batch (ETL bug fixes + column promotions) OR Layer 1 §J/§K/§L drafting OR jump to Layer 3 design

---

## TL;DR

Layer 2 design is now complete. All five parallel classifier nodes have consolidated specs at the depth standard:

- ✅ 2A Discipline Classification
- ✅ 2B Terrain Resolution
- ✅ 2C Equipment Mapping
- ✅ 2D Injury Risk Profile
- ✅ **2E Nutrition Baseline (this session)**

Outcome from the standing query-vs-LLM protocol: **zero LLM calls in Layer 2.** All five nodes are query nodes operating on structured Layer 0 + Layer 1 inputs. The genuine reasoning load has shifted to Layer 4 plan synthesis, which doesn't have a spec yet.

Bookkeeping from the prior session (handoff narrative claimed updates that didn't actually land in files) is now reconciled. Control_Spec §2, §3, §4, §7, §8.2, §9 all reflect Layer 2 reality. Project_Backlog has D-21 through D-35 explicit. FC-1 scope updated to include D-22, D-23, D-26 with FC-1a/FC-1b split contingency.

---

## What got accomplished this session

### Part 1 — Layer 2E spec from scratch

`Layer2E_Spec.md` drafted at the 14-section depth standard established by Layer2C_Spec.md. Pure query node, no LLM. Most opinionated of the five Layer 2 nodes — macro tables, fueling bands, multiplier bands all source-anchored inline but inherently band-recommendations.

**Eight decisions locked per 2026-05-11 scoping:**

1. **Node type:** query node. Confirmed; same protocol as 2A–2D.
2. **BMR formula:** Cunningham (1991) when `ffm_kg` is available, Mifflin-St Jeor otherwise. Automatic switch in code; FFM is currently not captured in onboarding (tracked as D-28).
3. **Activity multiplier:** BMR × phase × volume lookup from `phase_load_weekly_totals`. Phase-default fallback for D-07 affected sports. AR safe.
4. **Macros:** g/kg body weight, phase-scaled. CHO band position driven by discipline-mix endurance profile; protein band position driven by strength-weighted share. Fat floor at 1.0 g/kg with CHO shrink protection.
5. **Race-day fueling:** 5-tier duration band × sport modifier × salt-tolerance modifier × heat-acclim modifier × GI-trigger format filter × caffeine plan.
6. **HITL gates:** 5 conservative blocks (supp × cardiac, race caffeine × cardiac, pregnancy × stimulant, pregnancy × contra supp, anaphylaxis × race aid). T1D demoted from HITL to coaching flag per Andy's call.
7. **Sub-format selection (D-17 carry-through):** 2E inherits the input contract from 2A. Layer 1 §H captures sub-format; 2E receives sub-format-resolved `framework_sport`.
8. **Heat acclim:** Plan Management owns derivation. 2E reads `HeatAcclimState` and `expected_race_temp_c` as input from Plan Management state. 2E names the contract; Plan Management spec must honor it.

**Test scenarios:** 10, with 13.1 anchored on Andy's PGE 2026 race.

### Part 2 — Bookkeeping cleanup

The 2D Done / 2E Kickoff handoff (2026-05-10) narrated several file updates that didn't actually land. Reconciled this session:

**Control_Spec.md updates that finally landed:**
- §2: 2D and 2E status flipped from "not yet drafted" to drafted
- §3 inputs table: 2E row corrected (was wrongly pointing to §F nutrition prefs; now correctly lists §A + §B + §H.2 + §H restrictions + §I + supplement_vocabulary + 2A + Plan Management state)
- §4 partial-update table: rebuilt with explicit §I row, §B trigger for 2E, §H restrictions row, §H.2 estimated duration broken out, Plan Management triggers added
- §7 HITL surface: 2D and 2E both filled in with specific named triggers
- §8.2 standing rules: added D-21 reconciliation note
- §9 doc map: 2D and 2E flipped to drafted, Layer 1 §I status updated to reflect committed draft, Supplement_Vocabulary_Spec and Section_I_Audit added to doc map
- §5 cosmetic: tense fix on standing protocol prose

**Project_Backlog.md updates:**
- D-21 through D-26 added (these were claimed in prior handoff but never landed)
- D-27 through D-35 added — 2E-specific items (Plan Management contracts, FFM field, band promotions, METs table, HRT × BMR, beta blocker × cardiac inference, pregnancy capture, per-discipline GI risk)
- FC-1 scope updated to include D-22, D-23, D-26 with FC-1a / FC-1b split contingency for capacity overflow
- LEA / RED-S surveillance added to explicit out-of-scope list per Andy's call

---

## Files produced or modified this session

**New:**
- `Layer2E_Spec.md` (1324 lines, 14 sections at depth standard)
- `2E_Done_FC_Kickoff_Handoff.md` (this doc)

**Modified:**
- `Control_Spec.md` — 6 section updates + 1 cosmetic
- `Project_Backlog.md` — 15 new drift/design items; FC-1 scope updated; LEA/RED-S explicit wont-fix

---

## Agenda for next session

Three reasonable next steps. Andy's call which:

### Option A — FC-1 cleanup batch (ETL bug fixes + column promotions)

Per the long-standing Layer 2 → Layer 3 transition protocol: FC-1 + FC-2 land before Layer 3 design begins. FC-1 scope per `Project_Backlog.md` §"Session FC-1":

- **ETL bug fixes:** D-05, D-07, D-08, D-03, D-13, D-14, D-15
- **Column promotions:** D-22 (movement_components, ~600 cells), D-23 (body_parts_at_risk, ~150 cells), D-26 (supplement_vocabulary, ~25 seed rows)

D-22 is the largest single item by curation volume. Capacity contingency: split into FC-1a (ETL fixes) and FC-1b (column promotions) if one session can't hold both.

This is curation-heavy work; not design. Spec already exists for all three column promotions.

### Option B — Layer 1 §J / §K / §L drafting

Onboarding spec is partial. §J Locales, §K Locale Schedule, §L Athlete Network are still pending. 2C consumes §J inputs; 2C-level design assumed structural shape but didn't lock the spec details. These three sections would round out Layer 1 onboarding before Layer 3 design begins.

§J is the largest of the three. Source material exists in `Athlete_Onboarding_Data_Spec_v2_INTEGRATION_BLOCK.md`.

### Option C — Layer 3 design (cross-cutting evaluation + HITL gate)

The next architectural layer. Cross-references 2A–2E outputs, runs timeline viability gate, drives the hard HITL surface that blocks Layer 4. Probably involves LLM reasoning (combining outputs for athlete-facing rationale), but possibly hybrid.

**Risk of jumping to Option C without Option A:** 2D and 2E both have hard implementation blockers (D-22, D-23, D-26). Designing Layer 3 won't ship a product if Layer 2 doesn't run.

Recommended order: A first (unblocks implementation), then B (rounds out Layer 1), then C (Layer 3). But this is Andy's call.

---

## Pre-work reading order for next session

If Option A (FC-1):
1. **`Project_Backlog.md`** §"Session FC-1" — scope is locked
2. **`Layer2D_Spec.md`** §5.5 — seed for `disciplines.body_parts_at_risk` already drafted (D-23)
3. **`Supplement_Vocabulary_Spec.md`** — 25 seed entries already drafted (D-26)
4. **`Layer0_ETL_Spec_v3.md`** §4 — schema reference for new columns
5. **`Layer0_Deployed_Schema_and_Drift_Report.md`** — current deployed truth

If Option B (Layer 1 §J/§K/§L):
1. **`Athlete_Onboarding_Data_Spec_v2_INTEGRATION_BLOCK.md`** §J/§K/§L — source material
2. **`Layer2C_Spec.md`** — what 2C assumed about §J shape
3. **`Layer2B_Spec.md`** — what 2B assumed about §J locale terrain shape

If Option C (Layer 3 design):
1. **`Control_Spec.md`** §2 Layer 3 + §7 HITL surface
2. **All five Layer 2 specs** — Layer 3 consumes all five payloads
3. **`Adherence_Drop_Spec_v2.md`** — predecessor work on Plan Management subsystem

---

## Open items requiring Andy decision before or during next session

| # | Item | Status |
|---|---|---|
| 1 | **Next-session direction:** Option A (FC-1), B (Layer 1 §J/§K/§L), or C (Layer 3) | Awaiting Andy |
| 2 | **Supplement `evidence_quality` rating source** for FC-1 curator — AIS rankings, Examine.com synthesis, or other single source. (Carryover from 2D/2E session.) | Awaiting Andy if Option A |
| 3 | **D-17 sub-format selection mechanism** in §H — for non-AR sports, athlete's race goal must drive sub-format. Layer 1 race-goal capture design item. (Carryover.) | Awaiting Andy if Option B |
| 4 | **FFM field home** — §A (demographics) vs §F (performance testing) for adding `ffm_kg` capture. (D-28.) | Awaiting Andy if Option B |

---

## What NOT to do prematurely

- **Layer 4 design** — strictly post-FC-1 + post-FC-2 + post-Layer-3.
- **Plan Management spec** — Plan Management exists in name (heat acclim derivation, `current_phase` source-of-truth, weight staleness advisories) but doesn't have a spec. Tracked as D-27. Not yet scheduled.
- **Layer 0 schema changes** beyond D-22/D-23/D-26 (the three FC-1 promotions) — drift items stay deferred until FC-2.
- **§I v3 polish (D-25 items)** — 10 candidates parked; v3 onboarding pass, not now.
- **LEA / RED-S surveillance** — explicit wont-fix-for-v1.
- **2E implementation** — depends on D-26 (supplement_vocabulary) landing first. FC-1 work.
- **2D implementation** — depends on D-22 + D-23 (column promotions) landing first. FC-1 work.

---

## Critical context that must carry forward

**Standing protocols (Control_Spec §5, §8.2):**
- Query node vs. prompt node test: structured inputs + deterministic rules = query node. All Layer 2 specs validated against this.
- D-05 aggregator filter is mandatory in every query touching `phase_load_allocation`
- D-17 sub-format / top-level naming: 2A's strip logic; non-AR sports require sub-format input
- D-21 reconciliation: 2D/2E match on enum values not column names; column rename is cosmetic
- 14-section spec template at `Layer2C_Spec.md` depth
- Update Control_Spec §9 doc map at end of every spec
- Update Project_Backlog between sessions; promote 🟡 → 🔴 if next node's scope intersects

**Andy's preferences (userPreferences):**
- Direct, no praise/hype/filler
- Concise but not compressed; let ideas breathe
- Match confidence to reality; flag tradeoffs
- Tell the truth — say what's weak or flawed
- End plans with quick gut check (risks, blind spots, best argument against)
- Flag long/messy chats for handoff (this doc)

**Andy is the test athlete** for PGE 2026 (July 17–19, 48–56 hr expedition AR). Active wrist injury (Chronic-Managed, Left wrist, Pain with wrist extension + Pain with loading). PGE specifics encoded in test scenario 13.1 of `Layer2D_Spec.md` (injury risk) and 13.1 of `Layer2E_Spec.md` (nutrition baseline).

**Spec-first philosophy:** architecture → prompts → implementation. Resist shortcuts. FC-1 / FC-2 land at end of Layer 2 design before Layer 3 design starts.

---

## Files in project as of this handoff

| File | Status | Purpose |
|---|---|---|
| `Control_Spec.md` | ✅ Current (updated this session) | Architecture overview |
| `Project_Backlog.md` | ✅ Current (D-35 latest, updated this session) | Rolling tracker |
| `Layer2A_Spec.md` | ✅ Drafted | Discipline classification |
| `Layer2B_Spec.md` | ✅ Drafted | Terrain resolution |
| `Layer2C_Spec.md` | ✅ Drafted | Equipment resolution |
| `Layer2D_Spec.md` | ✅ Drafted | Injury risk profile |
| `Layer2E_Spec.md` | ✅ Drafted (this session) | Nutrition baseline |
| `Supplement_Vocabulary_Spec.md` | ✅ Drafted | Layer 0 vocab table (D-26; FC-1 implementation pending) |
| `Section_I_Audit.md` | ✅ Drafted | §I audit pass |
| `Athlete_Onboarding_Data_Spec_v2.md` | ⏳ Partial (§A-C/G-I/M/N drafted; §D-F/J-L pending) | Layer 1 onboarding |
| `Layer0_ETL_Spec_v3.md` | ✅ Current (v4 pending FC-2) | Layer 0 ETL spec |
| `Layer0_Deployed_Schema_and_Drift_Report.md` | ✅ Current | Layer 0 truth |

---

*End of handoff. Next session: open this doc, decide between Options A/B/C, then proceed with the corresponding pre-work reading order.*
