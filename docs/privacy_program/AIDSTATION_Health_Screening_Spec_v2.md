# AIDSTATION Health Screening Specification

**Document type:** Internal spec
**Status:** v2 — Active
**Last Updated:** May 19, 2026
**Owner:** Product / Architecture
**Companion documents:** Terms and Conditions §6; Privacy Policy §2.3, §4, §7; Acceptable Use Policy; Health and Safety Notice

---

## 1. Purpose

Defines the in-product health screening flow shown to all athletes at onboarding and on annual reassessment. The flow:

- Surfaces conditions and symptoms for which the user should consult a medical professional before training
- Records the user's acknowledgment that AIDSTATION is not a medical service and that they accept responsibility for participation
- Produces structured flag data consumed as input by Layer 3 athlete evaluation (coaching context, not medical risk stratification)
- Establishes evidence for liability defense in the event of an adverse health event during use of the Service

## 2. Scope and Boundaries

### 2.1 In scope
- Question set, scoring, and flag taxonomy
- Acknowledgment flow and recordkeeping
- Data contract to Layer 3
- Consent model (bifurcated per Privacy Policy §2.3)
- Reassessment cadence
- In-context micro-disclaimer placement

### 2.2 Out of scope
- Medical risk stratification (AIDSTATION does not perform this)
- Plan-generation gating based on flags (acknowledgment-only model)
- Diagnostic or clinical decision support
- Pregnancy-specific coaching (excluded by T&C §6)
- Pediatric users (Service is 18+ per T&C)

### 2.3 Legal posture
AIDSTATION is an information and training-guidance service. It is not a medical service, does not provide medical advice, and does not perform risk stratification. The screening flow exists to:

1. Inform the user when their reported conditions or symptoms warrant medical consultation
2. Capture the user's acknowledgment of that recommendation
3. Provide Layer 3 with context for coaching judgments (e.g., starting volume, recovery emphasis), framed as endurance-coaching choices and not as medical-safety decisions

No flag set in this screening prevents plan generation. The user always proceeds to a plan on acknowledgment.

## 3. Flow

### 3.1 Trigger points
- **Onboarding** — after account creation and the sensitive-data opt-in panel (Privacy Policy §2.3), before Layer 3 athlete evaluation runs
- **Annual reassessment** — 12 months from the most recent `last_assessed_at` timestamp
- **Voluntary** — from Settings → Health Profile → "Update health screening"

### 3.2 Screen sequence

**Screen 1 — Intro**
> Before we build your training plan, we ask a short set of questions about your health and any medical conditions you have. AIDSTATION is not a medical service and our recommendations are not medical advice.
>
> Your answers help us tailor your training and tell you when you should consult a physician before proceeding. You can update these answers at any time from Settings.

Buttons: **Continue** | **Why we ask** (link to Health and Safety Notice)

**Screen 2 — Questions (single page, 10 items, see §4)**

Each item is a yes/no question. For items where the user answers "yes" and the sensitive-data opt-in toggle for "Medical conditions that affect training" (Privacy Policy §2.3) is enabled, an optional free-text follow-up appears: "If you wish, you can share more detail. Skip if you prefer."

If the toggle is off, no free-text field is shown for that item.

**Screen 3 — Acknowledgment**

Content depends on whether any flag was set.

*If no flag set:*
> No items in this screening require physician consultation before training. AIDSTATION recommendations remain general training guidance and are not medical advice. By continuing, you accept responsibility for your participation in any training activity.

Button: **I acknowledge and continue**

*If any flag set:*
> Based on your responses, we recommend you consult a physician before starting or continuing a training plan.
>
> Specifically, you indicated:
> - [plain-language description of each flag]
>
> AIDSTATION is not a medical service and we cannot evaluate your medical status. By continuing, you confirm that you have read this recommendation and accept responsibility for your participation. If you have not already done so, we strongly suggest you speak with a qualified medical professional about your fitness for endurance training.

Button: **I acknowledge and continue**
Secondary link: **Read the Health and Safety Notice**

*If the PREGNANCY flag is set, the acknowledgment text includes an additional paragraph:*
> AIDSTATION does not provide pregnancy-specific coaching. Plans you receive will not be modified for pregnancy. Consult a qualified prenatal exercise specialist or your obstetric provider for pregnancy-appropriate exercise guidance.

### 3.3 What gets recorded on acknowledgment
- Full set of flag codes (always, under contract necessity)
- Free-text detail per flag (only if sensitive-opt-in for medical conditions is on)
- `acknowledged: true`
- `acknowledged_at` timestamp
- `last_assessed_at` timestamp
- `reassessment_due_at` (= `last_assessed_at` + 365 days)
- `screening_version` (currently "v1")

## 4. Question Set

The set draws on the public-domain PAR-Q+ 2024 framework and maps onto T&C §6 condition categories. Questions are deliberately written as plain English yes/no rather than clinical language.

| # | Question | Flag code on "yes" |
|---|---|---|
| Q1 | Have you had chest pain or discomfort at rest, or pain that gets worse with activity? | `CARDIO_CHEST_PAIN` |
| Q2 | Have you lost balance because of dizziness, or lost consciousness, in the past 12 months? | `CARDIO_SYNCOPE` |
| Q3 | Have you been diagnosed with a heart condition, high blood pressure, or do you have a family history of early cardiac events? | `CARDIO_CONDITION` |
| Q4 | Do you have diabetes, kidney disease, liver disease, or another metabolic disorder? | `METABOLIC_CONDITION` |
| Q5 | Do you have a bone, joint, soft tissue, or chronic pain condition currently affected by exercise, or have you had surgery in the past 6 months? | `MSK_CONDITION` |
| Q6 | Do you have, or have you had, an eating disorder, or do you currently have concerns about disordered eating? | `ED_CONDITION` |
| Q7 | Are you currently being treated for a mental health condition, including depression or anxiety? | `MH_CONDITION` |
| Q8 | Are you currently pregnant, or within 6 months postpartum? | `PREGNANCY` |
| Q9 | Do you take prescription medication for any condition not already noted above? | `PRESCRIPTION_OTHER` |
| Q10 | Is there any other condition for which you believe you should consult a physician before exercise? | `OTHER_CONDITION` |

Plain-language strings for each flag (used in the acknowledgment screen) are maintained in a separate localization table; this spec defines the codes only.

## 5. Flag Codes — Reference

The following codes are the canonical taxonomy. Any change requires a `screening_version` bump.

| Code | Source | Acknowledgment text token |
|---|---|---|
| `CARDIO_CHEST_PAIN` | PAR-Q+ Q1 / T&C §6 cardiovascular | "Chest pain at rest or worsened by activity" |
| `CARDIO_SYNCOPE` | PAR-Q+ Q2 | "Dizziness causing loss of balance, or loss of consciousness, in the past 12 months" |
| `CARDIO_CONDITION` | T&C §6 cardiovascular | "Diagnosed heart condition, high blood pressure, or family history of cardiac events" |
| `METABOLIC_CONDITION` | T&C §6 metabolic | "Diabetes, kidney disease, liver disease, or other metabolic disorder" |
| `MSK_CONDITION` | PAR-Q+ Q3 / T&C §6 MSK | "Bone, joint, soft tissue, or chronic pain condition, or recent surgery" |
| `ED_CONDITION` | T&C §6 eating disorders | "Current or past eating disorder, or current concerns about disordered eating" |
| `MH_CONDITION` | T&C §6 mental health | "Mental health condition currently being treated" |
| `PREGNANCY` | T&C §6 pregnancy | "Currently pregnant or within 6 months postpartum" |
| `PRESCRIPTION_OTHER` | T&C §6 prescription medication | "Prescription medication for a condition not already noted" |
| `OTHER_CONDITION` | Catch-all | "Other condition warranting medical consultation" |

## 6. Data Contract to Layer 3

This contract is **provisional**. The output shape will be reviewed and finalized when Layer 3 athlete evaluation design lands. Until then, Layer 3 design should anchor against this shape and flag breaking changes back into this spec.

### 6.1 Output schema

```json
{
  "health_screening": {
    "screening_version": "v1",
    "flags": ["CARDIO_CONDITION", "MSK_CONDITION"],
    "details": {
      "CARDIO_CONDITION": "<user-provided free text or null>",
      "MSK_CONDITION": "<user-provided free text or null>"
    },
    "acknowledged": true,
    "acknowledged_at": "2026-05-19T14:30:00Z",
    "last_assessed_at": "2026-05-19T14:30:00Z",
    "reassessment_due_at": "2027-05-19T14:30:00Z",
    "reassessment_overdue": false
  }
}
```

### 6.2 Field semantics
- `flags` — full set of structured codes. Always populated for any completed screening. Stored under Art 6(1)(b) contract necessity.
- `details` — free-text per flag. Keys present only if the user has the sensitive opt-in for "Medical conditions that affect training" enabled AND provided text. If the opt-in is later disabled, all keys in this object are deleted on next data lifecycle pass per Privacy Policy §7.
- `acknowledged` — always `true` for any returned screening (incomplete screenings are not returned at all).
- `reassessment_overdue` — `true` when current time > `reassessment_due_at` AND the user has not yet completed reassessment. Triggers the in-app reassessment prompt but does not block plan updates.

### 6.3 Layer 3 usage expectations
Layer 3 treats flags as coaching context, not medical gates. Examples of acceptable Layer 3 behavior:
- Use of any cardiovascular or metabolic flag as input to conservative starting volume and progression rate
- Use of MSK flag as input to lower-impact discipline emphasis in early phases
- Use of MH flag as input to adherence and motivational framing choices (not as medical management)
- Use of ED flag to suppress aggressive calorie deficit recommendations and trigger nutrition framing that avoids restriction targets

Layer 3 does NOT:
- Prescribe specific intensity caps tied to medical conditions
- Recommend medication or supplement adjustments based on flags
- Make claims that the plan is "medically safe" or "cleared for" any condition
- Decline to generate a plan based on flags

## 7. Consent Model

Bifurcated per Andy's decision and consistent with Privacy Policy §2.3.

### 7.1 Binary flag outputs — Art 6(1)(b) contract necessity
The flag codes themselves (`CARDIO_CHEST_PAIN`, `MSK_CONDITION`, etc.) are necessary for the Service to provide tailored training guidance and to satisfy AIDSTATION's duty of care under T&C §6. They are stored under contract-execution necessity (GDPR Art 6(1)(b)) and do not require separate opt-in beyond agreement to the Terms.

A user who refuses the screening cannot use the Service, by the same logic that applies to any required intake step.

### 7.2 Sensitive detail (free text per flag) — Art 9(2)(a) explicit consent
The free-text detail fields constitute health data in the sensitive-category sense under GDPR Art 9. They are stored only when:

1. The user has the Privacy Policy §2.3 toggle for "Medical conditions that affect training" enabled (explicit opt-in), AND
2. The user has voluntarily provided text in the field (it is not required)

If the opt-in toggle is disabled at any time, all previously stored `details` entries are deleted per Privacy Policy §7 and the `details` object becomes empty on the next sync.

The binary flag codes are not affected by toggle state — those remain stored under §7.1.

## 8. Storage and Retention

### 8.1 Storage
- Flags, acknowledgment timestamps, and reassessment timestamps: `health_screening` table or JSONB field on the user record (Postgres / Neon)
- Free-text details: stored when present, gated by toggle state

### 8.2 Retention
- Screening data is retained for the lifetime of the account
- On account deletion (per Deletion Flow Spec v2), all health screening data is deleted alongside other account data
- Historical acknowledgment timestamps are retained for liability defense purposes during the account lifetime; they do not persist beyond account deletion

### 8.3 Liability defense use
Acknowledgment timestamps and flag history serve as evidence that the user was informed of the recommendation to consult a physician at the relevant point in time. They are accessed only on legal request and treated as confidential per the Privacy Policy.

## 9. Reassessment Cadence

### 9.1 Default
12 months from `last_assessed_at`. The system computes `reassessment_due_at = last_assessed_at + 365 days` at the time of acknowledgment.

### 9.2 Prompting
- 14 days before due: soft in-app notification — "Your health screening is due for annual update. Takes about a minute."
- On due date: in-app banner appears on dashboard until completed
- After due date: `reassessment_overdue` flag set to `true`; banner persists; plan updates continue but include a one-line note in plan output that reassessment is overdue

Plan generation and plan updates are **not** blocked by overdue reassessment.

### 9.3 Voluntary reassessment
The user can re-run the screening at any time from Settings. A voluntary reassessment resets `last_assessed_at` and `reassessment_due_at`.

### 9.4 Plan-update event trigger (deferred)
Mid-cycle plan invalidation triggered by reported new condition or new medication is not in v1. Currently the only path for a mid-cycle health profile update is voluntary reassessment. See Open Item D-82.

## 10. Micro-Disclaimer Placement (In-Context)

The screening acknowledgment is upfront; micro-disclaimers reinforce the non-medical-advice posture at points where AIDSTATION output most directly touches health.

### 10.1 Locations and text

**Location 1: High-intensity session detail**
Trigger: a session prescribes RPE ≥ 8, HR zone 4 or 5, threshold or VO2max efforts, or any duration > 6 hours.
Placement: small footer below the session card.
Text: *"AIDSTATION is not a medical service. If you have any concern about exercising at this intensity, consult your physician."*

**Location 2: Nutrition recommendations**
Trigger: any daily nutrition card with calorie or macro targets.
Placement: small footer below the nutrition card.
Text: *"Nutrition recommendations are general training guidance, not medical advice. For personalized nutrition counsel, consult a registered dietitian or your physician."*

**Location 3: Supplement recommendations**
Trigger: any supplement recommendation (daily or ad hoc).
Placement: persistent header on the supplement panel.
Text: *"AIDSTATION does not recommend or prescribe medications. Supplements can interact with medications and medical conditions. Consult your physician or pharmacist before taking any new supplement."*

**Location 4: Return-from-injury or condition-aware plan adjustment**
Trigger: any plan adjustment that responds to user-reported injury or symptom.
Placement: inline note above the adjusted block.
Text: *"AIDSTATION's adjustments are general training guidance, not medical rehabilitation. If you are recovering from injury or a medical condition, work with a qualified healthcare provider on your recovery; we adjust around what your provider has cleared you to do."*

### 10.2 Style and density
Micro-disclaimers are small, persistent, and consistent in placement. They are not modals and do not interrupt flow. Tone matches the rest of the AIDSTATION voice — direct, no hedging beyond the disclaimer text itself. They are not repeated within a single screen.

### 10.3 Linkage
Each micro-disclaimer is an internal link to the Health and Safety Notice for users who want the full picture.

## 11. Edge Cases

| Case | Handling |
|---|---|
| User refuses to complete screening | Cannot proceed to plan generation. Screening completion is a service-necessary step under T&C. |
| User answers all "no" but later self-reports a condition (e.g., in chat) | No automatic flag write from chat in v1. User must voluntarily update screening from Settings. See D-82. |
| User toggles sensitive opt-in OFF mid-cycle | `details` is wiped; `flags` retained; coaching continues using flag codes only. |
| User toggles sensitive opt-in ON after initial screening (no details) | Free-text fields appear if/when user voluntarily re-runs screening. Not retroactively prompted. |
| User changes screening answer from "yes" to "no" on reassessment | Flag is removed; corresponding `details` entry is deleted; reassessment_due_at resets. |
| User changes a "no" to "yes" on reassessment | Flag added; user shown the full acknowledgment screen with the new flag; recordkeeping captures both old and new acknowledgment timestamps. |
| User account deletion | All screening data deleted per Deletion Flow Spec v2; liability defense access expires with account. |
| Pregnancy flag in combination with active training plan | Acknowledgment screen includes the pregnancy-specific paragraph (§3.2). Plan continues without pregnancy modification. User is informed by the acknowledgment text that the plan is not pregnancy-modified. |

## 12. Open Items

| ID | Description | Priority |
|---|---|---|
| D-79 | Locale-aware terminology — "physician" vs "doctor" vs "GP" vs locale equivalents in plain-language strings | Low; cosmetic until international rollout |
| D-80 | Free-text detail prompt UX — explicit indicator that the field is sensitive and storage is gated by opt-in (e.g., a "this field is private and only stored if your medical-conditions opt-in is on" hint near the input) | Medium; affects user trust |
| D-81 | Layer 3 design confirmation — once L3 athlete evaluation spec is drafted, confirm the data contract in §6 aligns; revise this spec if needed | High; gates Layer 3 |
| D-82 | Self-reported condition update outside annual reassessment — voluntary path exists (§9.3); auto-detection from chat or other inputs deferred to post-v1 | Medium |
| D-83 | Reassessment overdue UX — banner persistence model; whether the user can permanently dismiss | Low |
| D-84 | Pre-acknowledgment skim/no-read pattern — guard against users blowing through the acknowledgment without reading; possible mitigation is a brief delay before the button activates on flagged screens | Low; behavioral, not legally required |
| D-85 | Aggregated flag visibility in Settings — can the user see their current health profile summary without re-running? Probably yes. Define the read view. | Low |

## 13. Test Scenarios

| # | Scenario | Expected outcome |
|---|---|---|
| T1 | New user, all "no" to Q1–Q10 | No flags stored; "no flags" acknowledgment shown; user proceeds to plan generation; `reassessment_due_at` set to T+365 days |
| T2 | New user, 1 flag (`CARDIO_CONDITION`), sensitive opt-in off | Flag stored; no `details` entry; acknowledgment shown with that flag's plain-language string; user proceeds |
| T3 | New user, 1 flag, sensitive opt-in on, user enters free text | Flag stored; `details["CARDIO_CONDITION"]` stored; acknowledgment shown; user proceeds |
| T4 | New user, `PREGNANCY` flag set | Acknowledgment screen includes pregnancy paragraph; user proceeds; plan generates without pregnancy modification |
| T5 | Returning user, day 350 since last screening | No reassessment prompt yet (14-day prompt is at day 351) |
| T6 | Returning user, day 365 | Reassessment prompt visible; banner shown; user can dismiss; plan continues to update |
| T7 | Returning user, day 400, has not reassessed | `reassessment_overdue: true`; banner persists; plan updates include overdue note; not blocked |
| T8 | Returning user, day 400, completes reassessment | `last_assessed_at` updated; `reassessment_due_at` reset; `reassessment_overdue: false`; banner clears |
| T9 | User toggles sensitive opt-in from on to off | All `details` keys deleted on next lifecycle pass; `flags` retained; coaching continues |
| T10 | User updates screening voluntarily | Same acknowledgment flow; previous acknowledgment timestamp retained in history; new one added; due date resets |
| T11 | User account deleted | All screening data deleted per Deletion Flow Spec v2 |
| T12 | User changes flag from "yes" to "no" on reassessment, `details` was previously stored | Flag removed from `flags` array; corresponding `details` key deleted; acknowledgment captured |

## 14. Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial spec. Acknowledgment-only model per Andy's decision (no hard-block, no conservative-route). Question set adapted from PAR-Q+ 2024 + T&C §6 categories. Bifurcated consent model (Art 6(1)(b) for flag codes; Art 9(2)(a) for sensitive detail). Annual reassessment cadence. Micro-disclaimer placement defined for four locations. | Product / Architecture |

## 15. Gut Check

### 15.1 Risks
- Acknowledgment-only is legally more exposed than tiered hard-blocking. The defense rests on: T&C §6 disclosure, the screening's explicit recommendation language, the user's recorded acknowledgment, and the in-context micro-disclaimers. This model is industry-standard for fitness apps (TrainingPeaks, Strava, etc.) and the failure modes are well-litigated, but jurisdiction matters — EU product-liability framework is stricter than US tort law.
- Without a self-reported new-condition trigger, a user who develops a condition mid-cycle has no path to update their profile until annual reassessment or voluntary update. This means coaching continues without the new signal. The annual cadence is on the lenient end of industry norms (some apps prompt at 6 months).
- The flag-as-coaching-input pattern in Layer 3 risks blurring into implicit medical decision-making if not carefully framed. The line is: "we coach conservatively when in doubt" (acceptable) vs. "we cap intensity because of your condition" (medical). Layer 3 implementation needs to be reviewed against this line.

### 15.2 What might be missing
- **No screening for current symptoms during a plan.** The screening is point-in-time at onboarding and annually. If a user develops chest pain in week 3, there's no mid-cycle interrupt unless they self-report. Some apps include a daily "are you feeling OK to train?" check.
- **No medication-list capture.** Q9 captures the binary fact of taking prescription medication; the medication itself isn't captured. This means supplement recommendations can't programmatically check for interactions. A future version could capture medication names under sensitive opt-in.
- **No physician-clearance upload path.** A user with a flag who has actual clearance has no way to record that beyond the acknowledgment. A "I have spoken with my physician and been cleared to train" attestation could be added — would shift more liability to the user and document the consultation.

### 15.3 Best argument against acknowledgment-only
A small hard-block on a tightly scoped red-flag set (chest pain at rest right now, syncope in past 12 months, active uncontrolled cardiac symptoms) would be cheap, defensible, and lose almost no real users — the population that genuinely answers "yes, I have active chest pain at rest" and proceeds anyway is small and exactly the population where acknowledgment-only fails worst in court. The counter-argument that holds is: AIDSTATION shouldn't perform medical decision-making at all, and any hard-block is a medical decision in legal characterization, so the cleanest posture is uniform acknowledgment-only with the strongest possible disclosure. That position is defensible; it is also the riskier of the two.

This is a residual exposure worth re-revisiting once the actual deployment is closer and counsel has weighed in. Not changing the spec now — flagging for the legal review.

---

*End of Health Screening Spec.*

---

*Cross-reference cleanup (v2, 2026-05-30): inline references to companion documents converted to unversioned logical names per Rule #12 (this document was outside the earlier cross-reference unversioning batch). No substantive content changes.*
