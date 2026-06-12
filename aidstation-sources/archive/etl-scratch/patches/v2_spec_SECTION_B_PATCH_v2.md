# §B patches v2 — literature-grounded revisions

**Supersedes:** the prior `v2_spec_SECTION_B_PATCH.md` content for §B.1.2 and §B.4.2.

This file replaces those two sub-sections with literature-grounded versions. The rest of the prior patch (Patch A's §B.1 Status History row tweak, Patch C's Open Items / Resolved decisions log updates) still applies as-is.

**Bump version:** v2.2 (or v2.3 if v2.2 already shipped with the original B patch).

---

## §B.1.2 — Re-injury preventive priority rule (revised)

**Replace** the §B.1.2 sub-section from the prior patch with the following:

```
#### B.1.2 Re-injury preventive priority rule

When an injury record is set to Severity = Resolved, plan generation continues to apply preventive priority for that body part / injury type. The duration and shape of the priority decay depend on (a) the injury's lifecycle history and (b) its Injury Type.

**Override rule (applies first, regardless of Injury Type):**

If the Status History ever included **Chronic-Managed or Structural-Permanent** at any point in the injury's lifecycle → **permanent preventive priority**. Plan-gen continues to apply protective adjustments (extra warm-up, capped impact volume on the affected body part, preferred substitutions) indefinitely. Rationale: tissue that earned a Chronic-Managed or Structural-Permanent label has structural changes that don't reverse with symptom resolution.

**Default decay model by Injury Type (applies when override does not):**

| Injury Type (per §B.1.1) | Decay model | Evidence basis |
|---|---|---|
| Acute soft tissue (strain / sprain / tear) | Stepped exponential decay over 12 months: full priority (1.0) months 0–3; half (0.5) months 3–6; quarter (0.25) months 6–12; neutral after 12 months | Hamstring strain literature: ~59% of recurrences occur in the first month after return to play; ~25% in the first week; 12-month reinjury rate plateaus around 17% (Jiménez-Rubio et al.; multicentre Qatar/NL prospective cohort, n=330) |
| Tendinopathy / overuse | **Permanent** elevated priority, even after symptom resolution | Achilles tendinopathy 10-yr follow-up: 19% report persisting symptoms; 41% develop bilateral overuse symptoms in the initially uninvolved tendon; recurrence rate up to 44% even after surgery (Lagas et al. 2023; Paavola et al.) |
| Joint (mechanical) — non-surgical | Stepped exponential decay over 18 months: full (1.0) months 0–6; half (0.5) months 6–12; quarter (0.25) months 12–18; neutral after 18 months | Ankle sprain proxy: 2-fold increased risk in year 1; recurrence may happen up to 8 years after initial; chronic symptoms ≥12 months in ~40% (Doherty et al.; Pourkazemi et al.) |
| Joint (mechanical) — surgical | **Permanent** elevated priority | ACL graft rupture: 18% by 5 yr; 47% of those in year 1, 74% by year 2; 23–36% second-ACL injury rate in young athletes (Webster & Feller; NACOX cohort). Surgical joint repair never returns to native tissue mechanics |
| Bone (fracture / contusion) — non-stress | Through documented healing window (typically 6–8 wk minimum) + 6-month residual decay (full first 3 mo, half last 3 mo); neutral after | Standard bone healing timeline; minimal residual structural risk after remodeling complete |
| Bone — stress fracture | Through healing window + 18-month residual decay (full 0–6 mo, half 6–12 mo, quarter 12–18 mo); neutral after | Stress fracture literature shows elevated refracture risk extending well beyond initial healing; bone remodeling and restoration of mechanical properties takes 12–18 months |
| Skin / surface | None — neutral immediately on Resolved | Skin/surface injuries heal without lasting structural change to load-bearing tissue |
| Nerve | Stepped exponential decay over 12 months as for Acute soft tissue, **unless** ever Chronic-Managed (then permanent per override rule) | Acute neural compression typically resolves; chronic radiculopathy / neuropathy is captured by the override rule |
| Inflammatory (bursitis / fasciitis) | Stepped exponential decay over 6 months: full (1.0) months 0–2; half (0.5) months 2–4; quarter (0.25) months 4–6; neutral after | Inflammatory injuries typically resolve quickly; recurrent inflammatory injuries get the Chronic-Managed label and trigger the override rule |
| Post-surgical | Layered: (a) hard gate through surgeon's clearance date; (b) underlying injury type's decay model after clearance; (c) override rule applies if Chronic-Managed or Structural-Permanent at any point | Post-surgical alone does not imply permanent priority — many surgical cases (clean meniscectomy, isolated fracture fixation) recover fully. The underlying injury type drives residual decay |
| Other / uncertain | Conservative default = Acute soft tissue model (stepped decay over 12 months) | Default to the most-studied curve when the type is unclear |

**Status History walk:** the override determination is made by reading the full Status History timeline — not the current Severity value. A record currently at Resolved that *previously* held Chronic-Managed status is treated under the permanent rule, even though the current value is Resolved.

**What "preventive priority weight" means operationally:**

Plan generation reads the priority weight (between 0.0 and 1.0) for each resolved injury at each plan generation event. The weight modulates the strength of preventive adjustments — at weight 1.0, full preventive treatment applies (extra warm-up sets, capped impact volume, preferred low-stress exercise substitutions for the affected body part). At weight 0.5, the same adjustments apply at reduced intensity (e.g., warm-up additions but no impact volume cap). At weight 0.25, only the lowest-cost preventive measures persist (e.g., preferred substitution available but not enforced). At 0 (neutral), no preventive treatment is applied.

The exact mapping from weight to specific plan-gen behaviour is owned by the Plan Management spec; this section defines the weight signal and the decay curve.

**Edge cases:**
- Re-injuries to the same body part / type create a new injury record with its own Status History and decay timer; the existing record's decay continues independently.
- Athlete-edited Status History (correcting a mis-entry) recomputes the override rule and decay weight from the corrected timeline at the next plan generation.
- Multiple resolved injuries on the same body part: weights stack additively, capped at 1.0 (athlete with two separate hamstring strains in the past 6 months still gets full preventive treatment, not 1.5x).
- The decay model treats months as discrete steps for implementation simplicity. A continuous exponential function is no more defensible given the precision of the underlying epidemiological data.

**Confidence note:**

Decay shapes for tendinopathy (permanent), ACL/surgical joint (permanent), and acute soft tissue (12-mo stepped) are well-supported by long-term cohort data. Decay shapes for non-surgical joint mechanical (18-mo) and stress fracture (18-mo) are extrapolated from related literature with less direct evidence and should be revisited if better data emerges. Inflammatory and Nerve decay shapes are clinical heuristics, not literature-derived.
```

---

## §B.4.2 — Auto-population (revised, operational thresholds)

**Replace** the §B.4.2 sub-section from the prior patch with the following:

```
#### B.4.2 Auto-population (launch behaviour)

Three Health Condition auto-suggest rules ship at launch. All are auto-suggest, not auto-create — the athlete confirms before any record is added. Suggestions are non-blocking; an athlete can dismiss any suggestion and proceed with onboarding or training.

##### Rule 1 — Anaphylaxis flag → suggest GI or Immune / Autoimmune record

| Trigger | Suggested record | Notes |
|---|---|---|
| A Food Allergy & Intolerances entry has the anaphylaxis flag set | New Health Condition record, System category = Immune / Autoimmune (default) or GI (if the trigger is ingestion-only with no systemic component) | Suggested at the moment the anaphylaxis flag is set. Pre-fills Name from the allergy entry; athlete edits System category and Notes as desired. Suggestion is suppressed if a record matching the same allergen already exists |

##### Rule 2 — Condition-specific medication → suggest matching system category record

| Trigger | Suggested record | Notes |
|---|---|---|
| A Current Medications entry contains a drug from the launch reference list (insulin, beta blocker, levothyroxine, methotrexate, biologics, antiepileptics, others on the launch list) | New Health Condition record, System category matching the drug's primary indication (e.g., insulin → Endocrine / Metabolic; beta blocker → Cardiac; levothyroxine → Endocrine / Metabolic; antiepileptic → Neurological / Cognitive) | Suggested at the moment the medication is added. Drug-to-category mapping is a launch reference table maintained as part of the medication enum; expand post-launch as new drug classes are added. Suggestion is suppressed if a record in the matching system category already exists |

##### Rule 3 — RHR outlier → suggest Cardiac record

This is the most nuanced rule. Operational thresholds depend on whether the athlete has an established RHR baseline and on whether symptoms are present.

**Trigger conditions** (any one fires the suggestion):

| Condition | Threshold | Notes |
|---|---|---|
| **Sustained tachycardia at rest** | 7-day rolling average RHR > 100 bpm | Suppressed if any of the following is logged within the same 7-day window: illness, fever, recent caffeine spike, ACWR > 1.5 (training overload), severe sleep deprivation. AHA standard tachycardia threshold |
| **Symptomatic bradycardia** | RHR < 40 bpm AND athlete has logged within the past 14 days any of: dizziness, syncope, unexplained fatigue, exercise intolerance, chest discomfort, palpitations | RHR < 40 bpm alone is normal in trained endurance athletes (up to 80% of endurance athletes develop sinus bradycardia). The trigger is the symptom pairing, not the rate |
| **Sustained baseline shift upward** | 30-day rolling average RHR > 10 bpm above the prior 90-day baseline | Only fires after a 90-day baseline is established (≥60 days of data in the last 90). Suppressed if illness, ACWR > 1.5, or recent significant detraining is logged |
| **First-entry extreme outlier** | Initial RHR > 100 bpm or < 35 bpm AND no training history sufficient to explain the value (Years of Structured Training < 1 in primary endurance discipline, OR primary discipline is non-endurance) | One-time check at first RHR entry. Above 100 bpm: suggests evaluation regardless of training. Below 35 bpm: suggests evaluation when not explained by endurance training history |

**Per-trigger context shown to the athlete:**

Each trigger surfaces its own specific copy explaining what was detected and why a Cardiac Health Condition record might be appropriate. The copy explicitly invites athlete dismissal if the elevation/depression has a known cause not captured in the system.

For Rule 3, the suggestion always includes the standard caveat: "Athlete bradycardia from endurance training is normal and not a cardiac condition. Only add a record here if you have symptoms or a clinical concern."

**Suggestion suppression and dismissal memory:**

Dismissed suggestions are remembered for that specific trigger event — the system does not re-suggest the same record on subsequent edits to the same triggering field unless the trigger condition materially changes (e.g., new medication added; allergy upgraded to anaphylaxis; new symptom logged with existing bradycardia). Re-prompts on the same trigger require either a new triggering event or 90+ days elapsed since dismissal.

**Out of scope for launch:**

- Auto-suggestion from Connected Service signals (e.g., wearable-derived AFib detection, HRV crash patterns). Deferred — depends on signal-quality validation per service.
- Auto-suggestion from injury patterns (e.g., recurring tendinopathy → suggest Musculoskeletal chronic record). Deferred — needs separate review of false-positive risk.
- Auto-suggestion from §H Target Event characteristics (e.g., first cold-water swim event → suggest Thermoregulation record). Deferred — collects signal that the athlete may not yet have evidence for.
- Sex-specific or age-specific RHR band refinements (e.g., adjusting upper threshold downward for athletes >50). Defer until enough launch data confirms the symmetric thresholds above are not generating excess false positives in any demographic.

**Confidence note:**

The 60-100 bpm general adult range is AHA standard (well-established). The athlete-specific lower bound (40 bpm normal for endurance athletes; <30 bpm reported in elite) is well-supported by sports cardiology literature. The +10 bpm baseline shift threshold for tachycardia trigger is consistent with the existing §B Resting Heart Rate field's overtraining-flag heuristic. The 14-day symptom-pairing window for bradycardia is a clinical default — could tighten with usage data.
```

---

## After applying

- Bump version. Save. Upload.
- The Open Items table and Resolved decisions log changes from the prior patch (Patch C, items #3 and #7 marked Integrated) still apply unchanged.
