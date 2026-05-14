# Onboarding Data Model Session — Handoff
**Session date:** May 2026
**Inputs:** `Training_App_Architecture_Handoff.md`, `AR_Athlete_Onboarding_Schema.md`, `Sports_Framework_Handoff_v2.md`, `Sports_Framework_v3.xlsx` (Sheet 7), `Layer0_ETL_Spec.md`, `AR_Exercise_Database_v17.xlsx`, `AR_Exercise_Database_Documentation.md`
**Output:** `Athlete_Onboarding_Data_Spec_v1.md` (in project)
**Status:** v1 spec complete. v2 spec pending — multiple refinements decided this session not yet folded in. Equipment vocab alignment pass deferred. Team training is its own work item.

---

## What this session accomplished

Reconciled `AR_Athlete_Onboarding_Schema.md` and `Sports_Framework_v3.xlsx` Sheet 7 into a single canonical Layer 1 reference: `Athlete_Onboarding_Data_Spec_v1.md`. ~120 data points across 14 sections (A–N). Every field has type, tier, drives, and FIT-fillability marker.

After v1 was delivered, the rest of the session was a multi-batch refinement pass that produced ~30 additional decisions and several new fields/concepts that need to be incorporated into v2.

**Recommended posture:** treat v1 as "structural draft, not final." It's ~80% right. v2 should be written in a fresh session with this handoff + v1 + the project files as input.

---

## Decisions made in this session — beyond what's in v1

### Section A — Identity

| Decision | Action for v2 |
|---|---|
| Drop gender identity field entirely | Remove Section A gender row |
| Sex stays TIER 1, M/F | No change |
| HRT effects on training are captured via Medications (Section B), not via gender | Add note in B that HRT presence affects programming independently of biological sex |
| Add account-creation disclosure language as design note | Add Section A.1 "Disclosures" subsection: account-creation legal/medical acknowledgment + contextual inline disclosures on sensitive questions ("we ask sex because...") |

### Section B — Health Status

| Decision | Action for v2 |
|---|---|
| Use common-name body part vocabulary, not medical | Apply proposed list (see "Body Part Vocab" below); align to exercise DB col 13 in equipment-vocab-style audit |
| Add Injury Type as new field in B.1 substructure | TIER 1, single-select. Enum: Acute soft tissue (strain/sprain/tear), Tendinopathy/overuse, Joint (mechanical), Bone (fracture/stress fracture/contusion), Skin/surface (burn/abrasion/laceration), Nerve, Inflammatory (bursitis/fasciitis), Post-surgical, Other/uncertain |
| Movement components on exercise side (col 9) need structured upgrade | Cross-layer To-Do: Layer 0 enhancement — exercise DB col 9 should add a structured "Movement Components" field per exercise. Athlete movement constraints map directly to it without keyword guessing |

### Section J — Lifestyle & Recovery

| Decision | Action for v2 |
|---|---|
| Drop the Heat Acclimatization onboarding field entirely | Replace with system tracking — workout date + location + weather API lookup. Onboarding does not collect this. |
| Connected Services framework (broader than FIT-fill) | Add a new "Connected Services" data entity at account level. Replace generic "FIT-fill" markers with specific service capabilities |

### Section I — Target Events (race-specific additions)

These are net-new fields from the final batch:

| Field | Notes |
|---|---|
| Known event complications | Free text + system-suggested via URL fetch. Examples: Heartbreak Hill, river crossings, altitude. Pre-fetch from event URL where possible. |
| Number of transition areas | Multi-sport races only. Drives brick training cadence and transition drill volume. |
| Number of aid stations | Drives self-sustainment pack weight calculation and fueling spacing strategy. |
| Race-specific nutrition restrictions | DISTINCT from Section J lifestyle dietary pattern. Example: vegan (J) at race with non-vegan aid → must pack everything. |
| Race fueling preferences | Race-day caffeine tolerance (separate from daily caffeine), real-food vs. gels/chews/liquid preference, known race-day GI triggers. |

### Section K — Locales

| Decision | Action for v2 |
|---|---|
| Geographic locale model, NOT parent-child | Rewrite Section K. Locales are tagged by city/region. When primary locale is in City X, all locales tagged "City X" become accessible. Reusing "Gym A in Dallas" works regardless of which Dallas hotel is active. |
| New city = zero secondaries by default | Adding new gym/secondary in new city is enrichment prompt, not blocking. |
| Gym memberships via Chain field on Locale | Add optional `Chain` field + `Membership Active Y/N` per Locale. When entering new city, system surfaces locales matching active chain memberships. No separate Memberships entity. |
| Seasonality elicitation = hybrid | Climate-derived defaults shown to user → user confirms or overrides. Per-water-type and per-winter-terrain seasonality is multi-select Jan–Dec, with smart defaults. |
| Gear readiness at locale = NOT inferable from city presence | Climbing gear at home doesn't mean climbing on a trip even if Austin has climbing gyms. Explicit toggles per locale. Don't try to infer cross-locale. |

### Section L — Locale Schedule

| Decision | Action for v2 |
|---|---|
| Date-specific constraints enum | Multi-select: At home only · Indoor only · Short sessions only · Other (free text). Combined "can't leave home" + "no gym" into "At home only." Removed "no driving" and "recovery week." |

### Section H — Schedule

No changes from v1.

### Cross-cutting

| Decision | Action for v2 |
|---|---|
| Structural reorganization | Restructure v2 into three top-level groups: **Athlete Data** (current Sections A–N), **Account Configuration** (connected services, gym memberships, social-share settings, disclosures), **Plan Management** (stub pointing to team-training spec) |
| Deferred-when-needed strategy | Soft warnings (not blocks) for performance data; hard gates only for safety; profile-prompts for stale data. See classification table below. |
| Vertical gain | Race-specific terrain wins for ramp targets when training for an event. Default to maintaining current capacity when no event. |
| Tier system applied to first-plan MVP | Define MVP data set explicitly (~25–30 fields). See "MVP for First Plan" below. |
| Safety gates retained | Avalanche training, crevasse training, climbing belay partner = hard gates. Performance data = soft warnings. |

---

## Soft Warning / Hard Gate / Profile Prompt classification

Pre-classification of TIER 2/3 fields by trigger model. Folds into v2 Section M (Profile Update Triggers).

| Field | Model | Trigger |
|---|---|---|
| Cycling FTP | Soft warning at plan gen | Cycling intervals scheduled |
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
| Saddle endurance | Soft warning at plan gen | Cycling event >4 hr scheduled |

Soft warnings should phrase as "your intervals may be off if you don't input this" — informational, not blocking.

---

## Body Part Vocabulary (proposed, common-name)

For v2 Section B.2. Aligns to exercise DB col 13 (vocabulary alignment audit pending).

| Region | Parts |
|---|---|
| Head/Neck | Neck · Jaw |
| Shoulder | Shoulder · Rotator cuff · AC joint · Shoulder blade |
| Arm | Elbow · Forearm · Wrist · Hand · Fingers · Thumb |
| Back | Upper back · Lower back · SI joint |
| Hip | Hip · Groin · Hip flexor · Glute |
| Upper leg | Quad · Hamstring · IT band |
| Knee | Knee · Kneecap · Meniscus · ACL · PCL · MCL · LCL |
| Lower leg | Calf · Soleus · Shin · Achilles · Peroneal |
| Foot/Ankle | Ankle · Plantar fascia · Foot · Toes |

Side picker (L/R/Both/N/A) separate.

Items left semi-medical because no good common alternative exists: Soleus, Peroneal, Plantar fascia, ACL/PCL/MCL/LCL, Meniscus. Athletes with these injuries know the terms because their PT uses them.

---

## MVP Data Set for First Plan

Working hypothesis — to be validated in UX flow design. ~25–30 fields, achievable in 5–7 minutes with good UX.

**Required upfront:**
- A: Name, DOB, sex, body weight, training location
- B: Current injuries (defaultable to "none")
- C: Years training, primary sport, current weekly volume
- D/I: Target event OR explicit "time-based fitness" choice
- F: Plank, dead bug, push-ups, BW squat, single-leg squat (5 quick benchmarks)
- H: Hours/week, training days, rest day
- K: One home Locale + minimum equipment + terrain

**Everything else deferred** — collected via:
- Soft warnings at plan gen (when missing field would degrade specific session quality)
- Profile prompts on visit ("while you're here, want to fill in...")
- Hard gates only for safety-critical features

This MVP definition should be the starting point for next session's UX flow design — it tells us where the 80/20 line is.

---

## Connected Services entity (new for v2)

Account-level entity, not athlete-data. Captures third-party integrations.

**Fields per connection:**
- Service name (Garmin Connect, Strava, Apple Health, Wahoo, Whoop, MyFitnessPal, etc.)
- OAuth/API key reference
- Status (active / expired / revoked)
- Last sync timestamp
- Scopes granted (activities / wellness / nutrition / etc.)

**Recommended launch tiers:**

| Tier | Services |
|---|---|
| MVP at launch | Garmin Connect, Strava, Apple Health |
| Fast-follow | Wahoo, Whoop, MyFitnessPal |
| Later | COROS, Samsung Health, Google Fit, Polar, Fitbit |

Rationale: Garmin + Strava cover ~70% of endurance athletes. Apple Health covers iPhone users without dedicated wearables. Each connected service eliminates 3–10 manual entry fields — highest-leverage UX element in onboarding.

Onboarding flow implication: a "Connect your services" wizard early in onboarding can prefill many fields.

---

## Team Training — its own work item

Separate spec session. Material captured here for that session's input.

### Scope of team training

| Concept | Layer | Status |
|---|---|---|
| Race team (training for team event) | Onboarding (Section I) | In v1 |
| Training partner (regular shared training) | Onboarding (Section K) | In v1, will expand in v2 |
| Plan-coordinated training (linked plans, joint workouts) | Plan management | Out of scope for onboarding spec |
| Asymmetric collaboration (partner is non-user or no-plan) | Plan generation rule | Commentary-only, no onboarding data |

Important: Training Partner and Race Teammate can be the same person. Single Person entity with multiple roles per athlete.

### Logic captured (for next session to flesh out)

**Pattern 1 — A creates first, B creates later:**
1. B sees A's proposed shared training days during B's plan creation
2. B accepts → both plans sync/normalize on those days
3. Focus order: team efforts (team canoe) → sync-able solo (trail run together) → asymmetric where unavoidable
4. If sync requires changes B doesn't accept → "couldn't sync, training solo this day" flag

**Pattern 2 — A creates with existing user B:**
1. A's plan generation queries B's plan
2. A defaults to align with B (less disruptive — B already committed)
3. If alignment requires changes to B → those changes go to B as proposals
4. B accepts → both plans update; B declines or times out → A's plan flags as "intended team day, not confirmed"

**Unifying principle:** newer plan bends to existing plan. Changes to existing plans require explicit consent. Defaults are decline if no response.

### Decisions made

- Conflict resolution: explicit user-response step in both patterns. Decline or timeout = "couldn't sync"
- Re-sync: no automatic ripple from partner's actuals. Notification only ("A missed Tuesday's swim, you may want to adjust").
- Departure: prompt-driven, triggered by N consecutive missed planned-team events. User asked "do you want to unlink?"
- Multi-partner: support up to 5 partners.

### Open questions for the team training session

1. **Departure threshold N** — first instinct is 3 missed shared sessions, but it's a guess. Validate.
2. **Multi-partner consent rule** — for N>2 partners, "all must consent to changes" is impractical. Likely needs majority-or-captain rule. Decide.
3. **Conflict-resolution UX** — what does the in-app accept/decline experience look like? Notification? Modal? In-line in plan view?
4. **Stale-link cleanup** — separate from departure prompt. If a linked partner goes silent for X weeks (no logged workouts at all, regardless of shared events), how is that handled?
5. **Team formation flow** — invitation, accept/decline, reciprocal linking. Detailed flow design needed.
6. **Cross-plan visibility** — when partners link, does each see the other's full plan, or only shared days? Privacy implications.
7. **Captain/owner role** — for AR teams of 3–5, is there a designated planner, or is it peer-to-peer?

---

## Open Items (for v2 spec or later sessions)

| # | Item | Status |
|---|---|---|
| 1 | Equipment vocabulary self-pass | Deferred. Single consolidated list with renames flagged, against AR Schema + exercise DB col 7 + col 11. |
| 2 | Body part vocab alignment audit | Run after vocab is locked. |
| 3 | MVP data set validation | Validate proposed MVP in next session's UX flow design. |
| 4 | Connected Services entity detail | Spec the OAuth flows, scope handling, sync cadence. |
| 5 | Disclosure language copy | Product/legal call. |
| 6 | Re-injury risk model | If past hamstring strain affects current programming, how is that weighted? Possibly a "preventive priority boost" tag on resolved injuries. |
| 7 | v2 structural reorganization | Athlete Data / Account Configuration / Plan Management top-level grouping. |
| 8 | Sheet 7 deprecation timing | Once v2 spec is signed off, mark Sheet 7 as superseded. |
| 9 | Movement components on exercise DB col 9 | Cross-layer: Layer 0 enhancement to add structured movement components per exercise. |
| 10 | Migration path from current app database | Architecture handoff blocker. Bring schema dump to next session. |
| 11 | "Number of TAs / aid stations" — when not user-known? | If user doesn't know, system tries event URL; if neither, plan defaults conservatively. Confirm fallback behaviour. |
| 12 | Race-specific fueling preferences vs. lifestyle dietary | Confirm separation in v2. Same data type, different sections. |

---

## Next session agenda

**Primary:** Write v2 of `Athlete_Onboarding_Data_Spec.md` incorporating all decisions in this handoff. Preserve v1 structure where unchanged; restructure into Athlete Data / Account Configuration / Plan Management.

**Secondary:** Equipment vocabulary self-pass — single consolidated list with renames flagged.

**Tertiary:** UX flow design for onboarding — wizard structure, FIT-first prompting, conditional sub-section logic, MVP-first plan pathway. Use the MVP data set from this handoff as the starting point.

**Out of scope for next session:**
- Team training spec (its own session)
- Per-user database schema (after v2 + UX flow are settled)
- Layer 1 ↔ Layer 0 query layer concrete spec (after schema is built)
- Migration spec (needs current app schema dump first)

**Bring to next session:**
- This handoff doc
- `Athlete_Onboarding_Data_Spec_v1.md`
- All existing project files (architecture handoff, sports framework, exercise DB, etc.)
- Current app database schema dump (if available — unblocks migration planning)

---

## Final notes

The session ran long. v1 was delivered cleanly; what followed was a series of refinement batches that improved the spec but accumulated faster than they could be folded in. v2 needs a fresh session for accuracy.

The biggest single improvement v2 should make is the structural reorganization (Athlete Data / Account Config / Plan Management). v1's 14-section flat structure made sense as a reconciliation of two source docs, but it doesn't reflect how the data is actually used downstream. Account Config (integrations, memberships, disclosures) and Plan Management (team training, joint plans) are different concerns from Athlete Data (what drives plan generation). Splitting them clarifies what's onboarding-blocking, what's account-level, and what's deferred entirely.
