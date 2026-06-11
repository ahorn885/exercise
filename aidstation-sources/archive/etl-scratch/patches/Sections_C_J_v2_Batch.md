# Sections C & J — v2 batch (additions only)

**Built:** May 2026
**Slots into:** `Athlete_Onboarding_Data_Spec_v2.md` (when v2 is written)
**Replaces:** Adds new fields to existing Sections C and J of `Athlete_Onboarding_Data_Spec_v1.md`. Other fields unchanged.
**Source decisions:**
- Pack Load Training History moved from proposed E.1 to Section C (athlete-level, per v1 confirmation pass)
- Race-day fueling preferences moved from proposed Section N race-specific to Section J lifestyle (athlete-level, per v1 confirmation pass — resolves handoff Open Item #12)

---

# Section C — Training History & Fitness Baseline

## C.1 Existing fields (unchanged from v1)

Years of Structured Training · Primary Sport · Secondary Sports / Disciplines · Current Weekly Training Volume · Peak Historical Weekly Volume · Longest Event Completed · Most Recent Race Results · Training Consistency · Previous Coaching/Plans

## C.2 New field — Pack Load Training History

**Resolves v1 Open Item #7.** Originally proposed for E.1 (Running baseline); confirmed athlete-level.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Pack Load Training History | Pack Training Record (see C.2.1) | 2 | Pack-load ramp rate; race-pack tolerance gate; chafing/blister/hot-spot risk flagging at high prescribed pack weights | Self-report |

**Tier rationale:** Tier 2 by default. Effectively Tier 1 for athletes with AR / expedition / mountain-marathon target events (pack >20 lb is mandatory). Conditional elevation handled at plan-gen time, not at onboarding.

### C.2.1 Pack Training Record substructure

| Field | Type | Notes |
|---|---|---|
| Most recent pack-loaded long session | Weight (lb/kg) + duration (hrs) + date | Anchors current pack-tolerance baseline |
| Typical pack training cadence | Enum (Never / Occasional / 1×/wk / 2+×/wk) | Drives ramp aggressiveness — Never = start at 10 lb / 30 min; 2+×/wk = start at current weight |
| Heaviest pack sustained for >2 hours (lifetime peak) | Weight (lb/kg) + approximate date | Proven physiological ceiling; never target >20% above prior peak without extended ramp |
| Notes | Free text | Discomfort patterns, chafing locations, gear adjustments that helped |

**Why a record substructure rather than three separate fields:** all four pieces describe one capability (pack-loaded endurance). Keeping them grouped means the athlete updates them together when they re-test, and the plan generator reads them as one logical unit.

**Re-test trigger (Section M):** Profile prompt every 8 weeks if athlete has any pack-required target event in the next 16 weeks; otherwise on athlete demand.

---

# Section J — Lifestyle & Recovery

## J.1 Existing fields (unchanged from v1)

Average Nightly Sleep · Work/Life Stress Level · Dietary Pattern · Current Supplement Protocol · Caffeine Tolerance & Strategy · Altitude Acclimatization History · Heat Acclimatization History (note: this was newly-added in v1 and is being **dropped** per Onboarding handoff Section J decision — replaced by system tracking via workout date + location + weather API)

## J.2 New fields — Race-day Fueling Preferences

**Resolves handoff Open Item #12** (Race-specific fueling preferences vs. lifestyle dietary). Confirmed at athlete level — these describe stable athlete characteristics, not event characteristics.

The existing **Caffeine Tolerance & Strategy** field already covers daily/training caffeine. Race-day caffeine is a sub-question on that field rather than a new field. The other race-day fueling characteristics get new fields.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| **Race-day Caffeine Strategy** *(sub-question on existing Caffeine Tolerance & Strategy)* | Enum (Same as daily / Loaded — abstain 7–14d pre-race / Avoid race-day entirely / Variable by event) + intended race-day mg dose | 2 | Race-week protocol: regular users need 10–14d abstinence to amplify race-day boost; abstainers skip caffeine planning entirely | Self-report |
| **Fueling Format Preference** | Multi-select with priority ranking (Real food / Gels / Chews / Liquid carbs / Mix) + free text comments | 2 | Race nutrition planning — determines what the plan recommends carrying and what aid stations should provide; affects gut-training session design | Self-report |
| **Known Race-day GI Triggers** | Free text (foods, formats, timings that caused GI distress in past races/long sessions) | 2 | Avoid in race nutrition recommendations; flag aid stations serving trigger foods; inform mid-race contingency plan | Self-report |
| **Salt / Electrolyte Tolerance** | Enum (Low — cramps even with replacement / Standard / High — heavy sweater, high salt loss) + preferred form (capsule / drink / chew / food-based) | 2 | Hot-weather plan adjustments; race fueling sodium target (typically 300–1000 mg/hr scaled by tolerance); cramping risk flag | Self-report |

**Why these aren't event-specific:** the athlete's gut, caffeine response, and salt loss rate are stable physiological characteristics. They don't change race-to-race. What CAN change race-to-race is the *specific implementation* (bring caffeine pills vs. coffee at start; pack X gels vs Y bars) — but those are plan-generation outputs, not athlete profile inputs.

**What stays event-specific (Section I — Target Events, not here):**
- Race-day weather expectation
- Aid station stocking and spacing (event characteristic)
- Mandatory kit fueling rules
- Cup vs. soft-flask vs. own-bottle aid station handling

**Section banner (UX guidance):**

> "These are about your body, not any specific race. We'll combine these with your target event details to recommend race-day nutrition."

---

# Open Items (Sections C and J)

| # | Item | Status |
|---|---|---|
| 1 | Whether Pack Training Record should auto-update from logged training when sessions are tagged with pack weight | Deferred — depends on session-tagging schema in plan-execution layer |
| 2 | Whether Salt / Electrolyte Tolerance should sub-question into "with replacement" vs "without" history | Defer — current enum captures the operational distinction |
| 3 | Caffeine Tolerance & Strategy field structure — adding the race-day sub-question may justify restructuring as a record substructure (parallel to Pack Training Record) | Recommend yes; minor schema lift; v2 design call |

---

# Implementation checklist (for v2 spec writer)

## Section C
- [ ] Add new C.2 row "Pack Load Training History" to Section C field table
- [ ] Add C.2.1 Pack Training Record substructure (new)
- [ ] Add re-test trigger to Section M (profile prompt every 8 weeks if pack-required event in next 16 weeks)

## Section J
- [ ] Drop Heat Acclimatization History row (per Onboarding handoff — replaced by system tracking)
- [ ] Modify Caffeine Tolerance & Strategy to include Race-day Caffeine Strategy sub-question
- [ ] Add Fueling Format Preference field (new)
- [ ] Add Known Race-day GI Triggers field (new)
- [ ] Add Salt / Electrolyte Tolerance field (new)
- [ ] Add J banner copy clarifying athlete-level vs event-level scope

## Cross-section
- [ ] Update v2 Open Items list — close handoff Open Items #6 (Heat Acclim — drop), #7 (Pack Load — built in C), #12 (race-day fueling — built in J)
- [ ] Update Section N to remove its references to race-day fueling and pack load (already done in `Sections_GHMN_v2_Batch.md`)
- [ ] Update Section E.1 (Running baseline) to remove the proposed Pack Load Training History row (was never built in v1 — just confirm not present)
