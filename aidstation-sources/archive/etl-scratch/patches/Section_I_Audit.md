# Section I — Audit Pass

**Date:** 2026-05-10
**Reviewer:** Spec audit before Layer 2E design begins
**Source under audit:** `Athlete_Onboarding_Data_Spec_v2.md` §I (slotted from `Sections_IJKL_Groups23_v2_Batch.md` 2026-05-10)
**Scope:** Field-by-field critical review of §I.1, §I.1.1, §I.2, §I.3 for 2E consumption readiness

---

## TL;DR

§I is solid v2. Found 7 items worth fixing now (mostly small additions and clarifying notes) and 10 v3 candidates worth tracking but not blocking 2E. Two structural conflations (sweat rate vs. salt loss; supplement free-text vs. structured) are real but acceptable for v2 with documented limitations.

---

## Methodology

For each field: (1) is it necessary, (2) is the type/granularity right, (3) is the tier honest, (4) does "Drives" accurately describe downstream use, (5) is it redundant with another field, (6) are there missing fields 2E will need.

Plus section-level: scope clarity, cross-section boundaries with §B and §H, free-text density.

---

## Fix-now findings

Real issues affecting 2E correctness, athlete UX, or downstream automation. Edits applied to `Athlete_Onboarding_Data_Spec_v2.md` §I in the same session.

| # | Field | Issue | Fix |
|---|---|---|---|
| 1 | I.1 Altitude Acclimatization History | "Y/N + altitude range + exposure count" is useless without recency — altitude adaptation fades over weeks. Athlete with 5 exposures all >2 years ago is functionally naive. | Add "Date of most recent exposure" to the field structure. |
| 2 | I.1 Dietary Pattern | Enum missing Pescatarian (common, no land animals); missing Kosher (parallel to Halal — odd that Halal is in but Kosher isn't); Low-FODMAP is a real GI-driven pattern but unmentioned. | Add Pescatarian, Kosher to multi-select. Add note in the field describing that Low-FODMAP and similar medical-pattern restrictions are capturable here or via §B GI conditions. |
| 3 | I.1.1 Intended race-day dose | Sub-field is shown unconditionally but only makes sense for Loaded or Same-as-daily strategies. Athletes who Avoid race-day entirely shouldn't be prompted. | Document conditional logic explicitly: "Collected when Race-day Caffeine Strategy ∈ {Same as daily, Loaded, Variable by event length}." |
| 4 | I.2 Salt/Electrolyte Tolerance | Field conflates two physiologically independent quantities — sweat *rate* (volume) and salt *concentration* in sweat. "Heavy sweater" is a rate descriptor; "high salt loss" is a concentration descriptor. They vary independently. | Add note acknowledging the conflation; v2 keeps single field for simplicity; v3 may split. Plan-gen treats the enum as a combined hot-weather risk signal. |
| 5 | I.1 Average Nightly Sleep cross-ref | High hours (≥8) reported alongside Poor quality is a sleep-disordered-breathing signal (apnea). Currently no flag/cross-ref. | Add cross-reference note: contradiction between hours and quality should prompt suggestion to add §B Respiratory or Neurological Health Condition record. |
| 6 | I.1 Work/Life Stress — Variable | "Variable" is a meta-state, not a level — plan-gen needs to know how to treat it. Currently undocumented. | Add contract note: plan-gen treats Variable as High baseline; athlete can override via Plan Management adherence input on a per-week basis. |
| 7 | I.2 GI Triggers prompt examples | Free text with no scaffolding produces empty or vague entries. Prompts with examples ("specific gel brand at hour 4; high-fiber meal night before; sucrose-only gels") raise quality materially. | Add example prompt text inline so the UX renders it. |

---

## v3 candidates (deferred, tracked)

Real improvements with material effect on plan quality but not blocking 2E. Each could be one paragraph or sub-field; collectively they'd grow §I by ~40%. v2 ships without them; v3 audit pass picks them up.

| # | Theme | Field/concept | Why deferred |
|---|---|---|---|
| V3-I-1 | Sleep variability | Sleep consistency / SD beyond mean | Mean alone is informative; SD is a polish |
| V3-I-2 | Macro preferences | Keto / fat-adapted / low-carb baseline | Most athletes are conventional carb; covered by free-text in Dietary Pattern + Current Supplement Protocol cross-ref |
| V3-I-3 | Caffeine sensitivity | CYP1A2 genetic variation flag | Few athletes know their status; daily-dose proxy works for most |
| V3-I-4 | Sweat physiology split | Sweat rate separate from salt loss (see Fix-now #4) | Single conflated enum is workable for v2 hot-weather adjustments |
| V3-I-5 | Strategic napping | AR-specific tactical napping experience | Sleep-dep section captures the worst-case data; napping skill is a refinement |
| V3-I-6 | Gut training history | Whether athlete has trained for high carb intake (90+ g/hr) | Belongs in §C training history more than §I; tracked separately |
| V3-I-7 | Supplements as multi-select | Restructure Current Supplement Protocol to common-supplement multi-select + free text other | Free text de-dup gap is real but small impact on plan output |
| V3-I-8 | Fasted training | Preference for fasted morning sessions | Refinement on pre-workout recommendations; default-OK assumption is fine for v2 |
| V3-I-9 | Daily hydration habits | Baseline water intake | Plan-gen treats hydration as race-day output; daily baseline is a refinement |
| V3-I-10 | Body weight trend | Recent significant change (>5% in 3 months) | §A captures current weight; trend matters for fueling target accuracy |

---

## Considered and explicitly not changing

| Field / concern | Why not changing |
|---|---|
| 4-point sleep quality Likert | Granularity is useful; collapsing to 3-point loses extremes. Keep. |
| "Real food" in Fueling Format Preference | Free-text comments capture sub-category detail. Enumerating bars/pastries/fruit/sandwiches/etc. adds onboarding friction with low plan-gen payoff. |
| "Variable" in Work/Life Stress (vs. forcing a single choice) | Fix-now #6 documents the contract; forcing a single choice creates worse-quality data. |
| Conflation of "Currently I work shifts" vs. "I sometimes get stressed" under Variable | Same answer: the contract note covers both cases. |
| Tier assignments | Reviewed; reasonable as drafted. Caffeine T2 is defensible (plan-gen runs without it but produces better plans with it). Supplements T2 over T3 keeps collection pressure up. |
| "Other" + free text catch-alls | Onboarding always needs these; can't pre-enumerate all dietary patterns or all GI triggers. |

---

## Cross-section boundary notes

These aren't §I bugs but worth recording for when 2E spec design lands.

**§B Food Allergies vs §I Dietary Pattern:**
Allergies = hard constraint (anaphylaxis-class through to mild GI). Patterns = preference / lifestyle. Plan-gen reads both — allergies block ingredients; patterns recommend or de-prioritize. Currently §B captures allergies, §I captures patterns. Cross-ref note added in §I.3 already does this work. ✓

**§B GI Health Condition vs §I.2 GI Triggers:**
Overlap zone. Crohn's (Status=Current, GI category in §B) and "gels nauseate me at 4hr" (§I.2) both filter aid-station food. Most athletes will use one channel or the other for the same data. Plan-gen unions them. Document this in 2E spec. Not a §I edit.

**§A Body Weight vs §I Dietary Pattern:**
§A captures current weight; §I captures pattern. Doesn't capture trend. V3-I-10 above. Not a v2 fix.

**§F Performance Testing vs §I.1 Sleep:**
RHR drift relative to baseline is an overtraining signal that combines §F's resting HR and §I's sleep quality. That's a plan-execution concern (Layer 4 / Plan Management), not an onboarding-input concern. Out of §I scope; out of 2E scope; properly handled later.

---

## Section-level verdict

§I is ready for 2E spec design after the Fix-now edits apply. Free-text density (4 fields: Supplement Protocol, GI Triggers, fueling format comments, sleep-dep context) is the largest structural concession in the section — 2E will have to handle these via LLM reasoning rather than rule-matching, which is fine if expected.

The section's stated scope ("stable athlete characteristics") doesn't quite match its actual content (Current Supplement Protocol changes monthly; Race-day Caffeine Strategy is a decision, not a characteristic). The mismatch is defensible — onboarding has to land *somewhere* — but worth a one-line acknowledgment in the section opener. (Minor; not in Fix-now.)

---

## Gut check

**What this audit gets right:**
- Field-by-field rigor rather than rubber-stamp.
- v3 candidates listed concretely with names and reasoning rather than vague "TBD" markers.
- Cross-section boundary notes flag handshakes 2E spec design will need to handle.
- Honest about what's not worth fixing now (don't ship more pristine than necessary).

**Risks:**
- Most fix-now items are notes/clarifications, not field-shape changes. Could be argued I'm being too conservative — should I have collapsed enums, split Salt/Electrolyte, restructured Supplements? Defensible counter: §I has to ship and v2 isn't the final shape. Don't bikeshed v2 polish when v3 is the right place.
- The Altitude History recency fix (Fix-now #1) is the most significant *data shape* change. Verify with Andy that "Date of most recent exposure" is the right structure (vs., e.g., "Years since last exposure" — both work).
- Cross-references I added in the original §I draft + this audit's additions risk becoming clutter. If they're not actionable for 2E, they should be in 2E spec, not §I prose.

**What might be missing:**
- I didn't critically audit the *enum values themselves* for things like Caffeine Tolerance bands. "1 cup/day or less" vs. "2-3 cups/day" — is the 1.5 cup athlete Low or Moderate? Boundary friction exists but boundary friction always exists in band enums. Not actionable.
- I didn't audit the section ordering / UX flow. §I.1 → I.1.1 → I.2 → I.3 is reasonable but Caffeine being a sub-question of Caffeine Tolerance reads awkward when scanning. UX pass concern, not data spec concern.
- I assumed the connected-services data convention (§I fields can be auto-populated from Whoop/Oura/Garmin where applicable). Not currently called out in §I — could note for fields where it applies (sleep especially).

**Best argument against this audit:**
v2 is a v2. Shipping with seven small fixes and ten v3 deferrals is exactly the right shape for an iterative product spec — but it also means §I will get one more polish pass in v3 audit. If the answer to "should we audit §I now?" was supposed to produce a clean lock-down, that's not what happened. The fix-now items are real but small; the v3 candidates dominate. Honest framing: this is more "v2.5 cleanup" than "v3 readiness audit."

Counter: 2E spec design only needs §I to be *consumable* and *honest about its limitations*. Both are now true. The v3 audit pass will happen when the §J/§K/§L drafts also land and the whole onboarding spec gets its v3 cut. Right time for that is post-2E, not now.

---

*End of audit. Seven edits applied to `Athlete_Onboarding_Data_Spec_v2.md` §I. Ten v3 candidates parked here for the future audit pass.*
