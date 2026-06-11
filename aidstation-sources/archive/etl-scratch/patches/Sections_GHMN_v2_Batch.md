# Sections G, H, M, N — v2 batch

**Built:** May 2026
**Slots into:** `Athlete_Onboarding_Data_Spec_v2.md` (when v2 is written)
**Replaces:** Sections G, H, M, N of `Athlete_Onboarding_Data_Spec_v1.md`
**Source decisions:** v1 confirmation pass review (May 2026 chat).

---

## What changed vs v1 — summary

| Section | v1 → v2 |
|---|---|
| G — Performance Testing | Add **Running threshold pace** field. FIT-fill language unchanged at launch (manual upload); Connected Services replacement deferred post-launch. Soft-warning linkage cross-referenced to §M classification table. |
| H — Schedule | **Drop Time-of-Day Preferences.** **Doubles Feasible promoted Tier 1.** Confirm scheduling fields cross-reference Section L (Locale Schedule) for travel/blackout dates. |
| M — Profile Update Triggers | **Add Health Conditions triggers** (parallel to Injury Record). **Add Gear/Readiness change triggers** explicit. **Add Connected Service triggers** for athlete-data effects. **Adherence-drop trigger** (athlete-reported OR system-detected). Rephrase FIT-sync language. **Fold in soft-warning/hard-gate/profile-prompt classification table** (per handoff). |
| N — Sport-Specific Additional Data | **Restructure Team Composition** as Y/N gate plus filtered reference to merged **Athlete Link entity** (covers both race teammates and solo training partners — see `Athlete_Link_Entity_v2.md`). **Move race-day fueling preferences to Section J.** **Drop sleep management / night nav fields** (over-collection). **Move Pack Load Training History to Section C.** **Drop chafing.** **Saddle endurance unchanged** — applies to all cycling, ramp-up trigger via §M classification table. |

---

# Section G — Performance Testing Baselines (Aerobic & Lab)

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Maximum Heart Rate (HRmax) | Number (bpm) + source (measured/estimated) | 1 | All HR zone calculations; beta blockers invalidate — RPE only | Manual entry from FIT export at launch; Connected Service post-launch; Tanaka (208 - 0.7×age) fallback |
| Lactate Threshold HR | Number (bpm) + method | 2 | Primary intensity anchor for threshold zones | Manual entry from FIT export (30-min hard effort avg HR) or lab test |
| VO2max Estimate | Number (ml/kg/min) + source | 3 | Aerobic capacity ceiling; -1 to -2% per 300m above 1500m altitude | Manual entry from wearable export or Cooper test |
| Cycling FTP | Number (W) + test date | 2 | FTP decays 5–7% over 6–8 wk without maintenance — re-test cadence; **soft warning at plan gen if cycling intervals scheduled** (see §M) | Manual entry; previous test record |
| Running Threshold Pace | Pace (min/km or min/mi) + test date | 2 | Run interval prescription; parallels FTP for cycling; **soft warning at plan gen if running threshold intervals scheduled** (see §M) | **NEW IN v2.** Standard threshold test: 30-min time trial, average pace over the final 20 min = threshold pace. (5K race pace is an acceptable proxy when no recent TT exists.) |
| Critical Swim Speed (CSS) | Time (min:sec/100m) + test date | 2 | Pool interval prescription; re-test every 8–10 wk; **soft warning at plan gen if pool intervals scheduled** (see §M) | 400m TT + 200m TT |

**FIT-fill / Connected Services note:**

At launch, all values are manually entered or imported from FIT files the athlete uploads themselves. Post-launch, these will be supplied automatically by Connected Services (e.g., Garmin, Strava, Apple Health). The Source column language stays "manual entry" for v2; the upgrade path is documented in the Account Config section.

**Section banner (UX guidance):**

> "Upload your most recent activity FIT file or your wellness FIT and we'll auto-populate what we can. Otherwise enter manually below. We'll prompt you to update these as you re-test."

**Soft-warning linkage:** Each field's plan-generation behaviour when missing is captured in the §M classification table. Linkage is now explicit (was implicit in v1) — see §M.4.

---

# Section H — Schedule & Availability

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Available Training Hours per Week | Number (hrs) + variability note | 1 | Hard ceiling on phase load allocation | Self-report + lifestyle audit |
| Training Days Available | Day-of-week multi-select + recurring conflicts | 1 | Long workout placement; recovery day; doubles feasibility | Self-report |
| Preferred Rest Day(s) | Day-of-week single or multi-select | 1 | Hard constraint on rest day | Self-report |
| Typical Session Duration | Enum (30/45/60/90 min / 2 hr / 3+ hr) | 1 | Determines exercise count and warm-up allocation | Self-report |
| Long Session Available | Y/N + day + max duration (2/3/4/5/6/8+ hr) | 1 | Long run/ride/hike ceiling per week | Self-report |
| Doubles Feasible | Enum (Regularly / Occasionally / No) | **1** *(promoted from 2 in v1)* | Two-discipline days; brick scheduling. Tier 1 because multi-discipline sports (AR, triathlon, multi-sport) cannot generate a viable plan without this | Self-report |

**Removed from v1:**
- ~~Time-of-Day Preferences~~ — eliminated per v1 confirmation pass. Was Tier 3, low signal-to-effort.

**Cross-reference to Section L:**

Section H captures the athlete's *typical weekly* availability. Section L (Locale Schedule) overlays specific date ranges for travel, blackout periods, alternate locales, and date-bound training partners. Plan generation reads H first (default schedule), then applies L overlays for any covered dates. Document this layering in v2's flow narrative.

---

# Section M — Profile Update Triggers

These are not data points but **lifecycle events** that trigger re-collection or re-evaluation. v2 expands M in three ways: (a) explicit triggers for new record-types added in v2 (Health Conditions, gear readiness toggles), (b) Connected Service event handling (where the source is Account Config but the effect lands on athlete data), (c) folding in the soft-warning/hard-gate/profile-prompt classification table that previously lived only in the handoff.

## M.1 Athlete data lifecycle triggers

| Trigger | What updates |
|---|---|
| Athlete adds new locale | Prompt for K.2–K.4 fields at new locale |
| Athlete flags existing locale as changed | Re-prompt equipment at that locale only |
| Athlete switches to previously-configured locale | No prompt — use stored profile |
| Athlete switches to unconfigured travel locale | Default to bodyweight-only; prompt to configure when ready |
| **Athlete updates equipment availability at a locale** | Re-evaluate exercise pool for that locale |
| **Athlete toggles a sport-specific gear readiness state** (acquires or loses kit) | Re-evaluate exercise pool for that locale; flag any in-flight plan sessions affected |
| Athlete reports new injury | Create injury record; immediately apply filtering |
| Athlete updates injury status | Update record; relax/tighten filtering |
| Athlete reports injury resolved | Move to history; retain for preventive priority |
| **Athlete reports new health condition** | Create Health Condition record; apply system-category filtering |
| **Athlete updates health condition status** | Update record; apply Current vs History filtering rules |
| **Athlete reports health condition resolved / inactive** | Set Status = History; retain for context |
| Athlete completes benchmark reassessment | Update benchmarks; unlock progressions |
| New event added | Recalculate periodisation; confirm event disciplines + terrain |
| Event details change (URL fetch) | Flag changes; adjust terrain-specific exercise selection |
| Season changes (inferred from weather + month) | Adjust terrain and session planning |
| Athlete completes a training block | Prompt for benchmark re-test |
| **Athlete reports plan adherence dropping** *(self-reported)* | Branch to root cause: bored / busy / injured / ill / life stress. Each branch routes to its own response (variety injection, volume drop, injury record, etc.) |
| **System detects plan adherence dropping** *(4 consecutive flagged sessions — see `Adherence_Drop_Spec_v2.md`)* | Fires the adherence-drop prompt; routes through opt-in confirmation per branch. All branch logic, periodisation overrides, and stacking rules in the adherence-drop spec |
| ~~FIT sync detects fitness change~~ → **Connected Service reports fitness change** | Auto-update aerobic benchmarks; flag significant changes; surface re-test recommendation if delta exceeds threshold |

**Bolded rows are new in v2.**

## M.2 Account Config events that affect athlete data

These events originate in Account Configuration but their effects ripple into athlete data. M owns the *effect side*; Account Config owns the *event side*.

| Account Config event | Athlete data effect |
|---|---|
| Connected Service connects | Begin pulling activity / wellness data; offer to backfill Section G fields if values aren't present |
| Connected Service disconnects | Stop auto-fill; flag fields as stale at next plan generation; revert to manual-entry expectations |
| Connected Service scope reduced | Re-check which fields can still auto-fill; prompt athlete for any newly-uncovered fields |
| Connected Service auth fails / sync stops | Stale-data warning at plan generation; prompt athlete to reconnect |
| Gym membership added/removed | Re-evaluate locale equipment; surface or remove gym-equipment-dependent exercises |

## M.3 Adherence-drop detection threshold

**Confirmed: 4 consecutive flagged sessions** triggers the adherence-drop prompt. A session is flagged when skipped, volume short (<70%), volume over (>130%), OR intensity off by >2 RPE in either direction. Full detection logic, branching, athlete-facing prompts, periodisation overrides, and stacking rules live in the dedicated spec: see `Adherence_Drop_Spec_v2.md`.

## M.4 Soft Warning / Hard Gate / Profile Prompt classification

Folded in from Onboarding handoff. Pre-classification of Tier 2/3 fields by trigger model.

| Field | Model | Trigger |
|---|---|---|
| Cycling FTP | Soft warning at plan gen | Cycling intervals scheduled |
| **Running Threshold Pace** | Soft warning at plan gen | Running threshold intervals scheduled |
| CSS | Soft warning at plan gen | Pool intervals scheduled |
| LTHR | Soft warning at plan gen | Threshold work scheduled |
| VO2max | Profile prompt | None — informational |
| Caffeine strategy | Soft warning at race week | Race within 14 days |
| Supplement protocol | Profile prompt | 90 days since update |
| Benchmark re-test | Profile prompt | 8+ weeks since last |
| Nearby gym (secondary locale) | Profile prompt | At primary location, no secondary linked |
| Heat acclim history | DROPPED | Replaced by system tracking |
| Avalanche training | Hard gate | Backcountry skinning in plan |
| Crevasse training | Hard gate | Glacier travel in plan |
| Climbing belay partner | Hard gate | Roped climbing in plan |
| OW marathon feeding experience | Soft warning at plan gen | OW marathon race within 12 wk |
| Wetsuit experience | Soft warning at plan gen | OW swim race scheduled |
| Cold water experience | Soft warning at plan gen | Cold-water race scheduled OR locale water access is outdoor-only AND climate likely <18°C |
| Aero position endurance | Soft warning at plan gen | TT/tri bike race scheduled OR TT/tri bike is only bike type |
| Saddle endurance | Soft warning at plan gen | **Any** cycling event >4 hr scheduled (was previously implied AR-only — confirmed as all cycling sports per v1 confirmation pass) |

**Soft warnings phrase as informational, not blocking:** "Your intervals may be off if you don't input this." Plan still generates; flagged for athlete attention.

**Hard gates phrase as safety stops:** "We can't program backcountry skinning sessions without avalanche safety training. Please complete training and return, or accept terrain-substituted sessions."

**Profile prompts phrase as nudges:** "It's been 9 weeks since your last FTP test — would you like to schedule one?"

---

# Section N — Sport-Specific Additional Data

These fields apply only to specific sport contexts. Conditional collection — only show if relevant.

| Field | Type | Tier | When asked | Drives |
|---|---|---|---|---|
| **Competing with team for this event** | Y/N | 1 | Target Event has team format (AR Unified, Relay, Doubles) | Gates collection of Athlete Link records with Race Teammate relationship type for this event |
| **Race Teammates** | Athlete Link records (1+, see Athlete_Link_Entity_v2.md) filtered to Relationship Type = Race Teammate AND Event FK = this event | 1 | Above = Y | Team ceiling = slowest member per discipline; role assignment; joint-training scheduling; cross-plan alignment per team-training spec |
| Ultra Documented Carb Tolerance | g/hr + context (training run >3 hr) | 1 | Primary Sport or Target Event is Ultra/AR/Long Cycling | Gut-training duration to bridge to 70 g/hr finisher target |
| Ultra Sleep Deprivation Experience | Hours awake + incidents (hallucinations, decision failures) | 2 | Primary Sport or Target Event is Ultra (100M+) / AR (24hr+) / Mountain Marathon (2-day) / Canoe Marathon (ultra) | Capacity to predict degradation; mandatory night-across session in peak phase |

**Removed from v1 (or never added — confirmed not added):**
- ~~Race-day fueling preferences (caffeine, real-food vs. gels, GI triggers)~~ → moved to **Section J** as athlete-level lifestyle data per v1 confirmation pass. See `Sections_C_J_v2_Batch.md`. Resolves handoff Open Item #12.
- ~~Sleep management practiced strategy~~ — over-collection. For sports requiring nighttime activity, plan generation schedules night sessions directly; no separate strategy field needed.
- ~~Night navigation experience~~ — same as above.
- ~~Chafing history~~ — over-collection. Not modelled.
- ~~Pack Load Training History (was proposed in E.1)~~ → moved to **Section C** (Training History & Fitness Baseline) per v1 confirmation pass. Athlete-level, not sport-specific. See `Sections_C_J_v2_Batch.md`.
- ~~Saddle endurance as AR-specific~~ — confirmed as **all cycling sports**, soft warning via §M classification table when any cycling event >4 hr is scheduled.
- (Sports_Framework_Handoff_v2 removals confirmed unchanged: AR previous experience, biathlon range access, fencing coach, MP OCR facility, XC technique cert, OWS cold water, canoe portage, fell mandatory kit.)

## N.1 Team Composition restructure — superseded

The proposed v2 Team Composition Record is **superseded by the merged Athlete Link entity** (see `Athlete_Link_Entity_v2.md`). Race teammates and solo training partners are the same conceptual entity — both are linked athletes whose plans need to align with this athlete's plan. The split was a v1 artifact.

Section N's role is now just the Y/N gate plus the filtered reference to Athlete Link records. The actual record fields, relationship types, and joint-training scheduling all live in the Athlete Link entity spec.

**Section L (Locale Schedule) similarly supersedes its inline "Training Partner record" with a reference to the same Athlete Link entity.** L's update is out of scope for this batch — flagged for a future Section L batch.

---

# Open Items (sections G/H/M/N specific)

| # | Item | Status |
|---|---|---|
| 1 | ~~Pack Load Training History placement~~ | **Resolved.** Moved to Section C — see `Sections_C_J_v2_Batch.md` |
| 2 | ~~Adherence-drop "N consecutive sessions" threshold~~ | **Resolved — N=5.** Branching logic still being designed (see #6 below) |
| 3 | Connected Services detail (OAuth flows, scope handling, sync cadence, refresh failures) | Lives in **Account Configuration spec** — confirmed at account level, out of scope for Athlete Data sections. Flagged in handoff Open Item #4. |
| 4 | ~~Team Composition record placement (N vs Plan Management)~~ | **Resolved.** Team Composition Record superseded by merged **Athlete Link entity** (see `Athlete_Link_Entity_v2.md`). Both N (race teammates) and L (training partners) reference the same entity. Plan Management still owns cross-plan sync logic. |
| 5 | ~~Running Threshold Pace test method canonical~~ | **Resolved.** Standard 30-min TT, average pace over final 20 min = threshold. 5K race pace acceptable proxy. |
| 6 | ~~Adherence-drop root-cause branching design~~ | **Resolved.** Full spec at `Adherence_Drop_Spec_v2.md` — covers detection logic, opt-in proposal/confirm flow per branch, periodisation context overrides, stacking rules, re-evaluation cadence, and edge cases. |
| 7 | Section L (Locale Schedule) update to reference Athlete Link entity | Flagged for separate Section L batch — out of scope here |

---

# Implementation checklist (for v2 spec writer)

## Section G
- [ ] Replace v1 §G field table with G table above
- [ ] Add Running Threshold Pace as new row (Tier 2)
- [ ] Update Source language to "manual entry from FIT export at launch; Connected Service post-launch" for HRmax/LTHR/VO2max
- [ ] Add explicit cross-reference to §M classification table for soft-warning behaviour
- [ ] Update banner copy to reflect manual-upload-at-launch posture

## Section H
- [ ] Replace v1 §H field table with H table above
- [ ] Drop Time-of-Day Preferences row
- [ ] Promote Doubles Feasible to Tier 1
- [ ] Add cross-reference paragraph linking H (typical schedule) and L (date overlays)

## Section M
- [ ] Replace v1 §M trigger table with M.1 above (note bolded new rows)
- [ ] Add §M.2 Account Config events table (new)
- [ ] Add §M.3 adherence threshold open item (new)
- [ ] Add §M.4 classification table (folded in from handoff)
- [ ] Update language: "FIT sync detects fitness change" → "Connected Service reports fitness change"

## Section N
- [ ] Replace v1 §N field table with N table above
- [ ] Add §N.1 Team Composition Record substructure (new)
- [ ] Document removals (race-day fueling, sleep mgmt, night nav, chafing, pack load, saddle endurance scope-broadening) in §N change notes
- [ ] Confirm race-day fueling preferences land in Section J v2 batch (not here)
- [ ] Confirm Pack Load Training History lands in Section C v2 batch (not here)
- [ ] Add section-placement note re: team training spec / Plan Management

## Cross-section
- [ ] Update v2 Open Items list with the 5 items above (and remove #8 Time-of-Day Preferences — resolved)
- [ ] Resolve handoff Open Item #12 (race-specific fueling vs lifestyle dietary) — closed by N → J move
