# Sections §I–§L + Account Configuration + Plan Management — v2 batch

**Built:** May 2026
**Slots into:** `Athlete_Onboarding_Data_Spec_v2.md` — replaces pending stubs for §I, §J, §K, §L and pending Group 2 / Group 3 blocks
**Sources:**
- `Sections_C_J_v2_Batch.md` §J.2 (race-day fueling fields for §I)
- `Sections_GHMN_v2_Batch.md` §M.1–M.4 (Profile Update Triggers for Group 3)
- `V2_spec_decisions_handoff.md` Decision 1 (Athlete Network entity; joint-training overlays on §K)
- `V2_Drafting_Handoff_post_batch3.md` (batch 4–5 agenda + locale proximity model)
- `Onboarding_Session_Handoff.md` (§J geographic model, §K date constraint enum, gym chain field)
- `Vocabulary_Audit_v2.md` §3 (equipment canonical list), §4.1 (12 sport-specific gear readiness toggles)
- `Adherence_Drop_Spec_v2.md` (cross-referenced from Plan Management group)

---

# Section I — Lifestyle & Recovery

*Was v1 §J.*

> **Section scope:** These fields describe stable athlete characteristics — how your body responds to fueling, stress, and sleep deprivation. They apply across all events and plan cycles. What changes race-to-race (aid station spacing, mandatory kit) is a plan output, not a profile input.

## I.1 Core lifestyle fields

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Average Nightly Sleep | Number (hours, 0.5 increments) + subjective quality (Poor / Fair / Good / Excellent) | 1 | Sleep deficit modelling; recovery day placement; consecutive hard-day limits | Self-report |
| Work / Life Stress Level | Enum (Low / Moderate / High / Variable) | 1 | Weekly volume ceiling; rest day frequency; hard session placement | Self-report |
| Dietary Pattern | Multi-select (Omnivore / Vegetarian / Vegan / Dairy-free / Gluten-free / Halal / Other) + free text | 2 | Nutrition recommendations; supplement suggestions that are pattern-compatible | Self-report |
| Current Supplement Protocol | Free text | 2 | Cross-reference at plan generation; avoids double-recommending what athlete already takes | Self-report |
| Caffeine Tolerance & Strategy | Enum (None / Low — 1 cup/day or less / Moderate — 2–3 cups/day / High — 4+ cups/day) + daily mg estimate (optional) | 2 | Training-day caffeine windows; pre-workout recommendations; gates race-day sub-question | Self-report |
| Altitude Acclimatization History | Y/N + altitude range (m) + approximate exposure count | 3 | Pacing adjustments for altitude events; VO2max correction (-1 to -2% per 300m above 1500m) if athlete has known acclimatization capacity | Self-report |

**Dropped from v1:** Heat Acclimatization History — replaced by system tracking via workout date + location + weather API in Plan Management (see Group 3).

---

## I.1.1 Race-day Caffeine Strategy

Sub-question on Caffeine Tolerance & Strategy. Collected when Caffeine Tolerance ≠ None.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Race-day Caffeine Strategy | Enum (Same as daily / Loaded — abstain 7–14d pre-race then peak on race day / Avoid race-day entirely / Variable by event length) | 2 | Race-week protocol: Loaded users need 10–14d abstinence window in taper; Avoid users skip caffeine planning entirely | Self-report |
| Intended race-day dose | Number (mg, optional) | 3 | Refines timing and carrier-format recommendations (pill vs. gel vs. drink) | Self-report |

**Implementation note:** The Caffeine Tolerance & Strategy field may be restructured into a record substructure (parallel to Pack Training Record) if v2 engineering decides the sub-question warrants it. Either is compatible with this spec; the field inventory is the same.

---

## I.2 Race-day fueling preferences

These fields describe physiological characteristics that are stable across events. They drive plan-gen outputs — what to carry, what to train the gut toward, what to avoid at aid stations.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Fueling Format Preference | Multi-select with priority ranking (Real food / Gels / Chews / Liquid carbs / Mix — no strong preference) + free text comments | 2 | Race nutrition planning: what the plan recommends carrying; which aid station formats to prioritize or avoid; gut-training session design (progressive real-food tolerance for AR) | Self-report |
| Known Race-day GI Triggers | Free text (foods, formats, timings that caused GI distress in past races or long training sessions) | 2 | Avoid in race nutrition recommendations; flag aid stations serving trigger foods; inform mid-race contingency plan | Self-report |
| Salt / Electrolyte Tolerance | Enum (Low — cramps even with replacement / Standard / High — heavy sweater, high salt loss) + preferred form (Capsule / Drink mix / Chew / Food-based / No preference) | 2 | Hot-weather plan adjustments; race fueling sodium target (typical range 300–1000 mg/hr scaled to tolerance band); cramping risk flag for plans with high-heat event dates | Self-report |

---

## I.3 Sleep deprivation experience

**Conditional:** collected only when §H Target Event record has Estimated Duration > 20 hr.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Sleep Deprivation Experience | Hours awake in longest prior sustained effort + notable incidents (hallucinations Y/N, decision failures Y/N, nausea Y/N, involuntary sleep Y/N) + free text context | 2 | Capacity model for overnight event planning; mandatory night-across session timing in peak phase; sleep-dep mitigation strategy (strategic napping windows, caffeine timing) | Self-report |

**Trigger logic:** When Estimated Duration is updated on any §H Target Event and crosses 20 hr, §I prompts for this field if not already collected. Remains in profile until athlete removes all >20hr events.

---

---

# Section J — Locales

*Was v1 §K. Largest single section in the spec.*

A Locale is a geographic base from which the athlete trains. Most athletes have one primary locale (home) and may add travel locales. Equipment, terrain access, and gear readiness are stored per locale.

**Proximity model (replaces v1 parent-child FK):**

Each Locale has coordinates derived from a place lookup at creation. The system computes a proximity cluster using a default radius of **26.2 mi / 42.2 km** — locales within this radius of the active locale are treated as co-accessible (their equipment and terrain pools union into the active set). The athlete can manually override: explicitly link two locales the system didn't catch, or unlink two it linked incorrectly. Manual overrides persist across proximity recalculations.

Gear readiness toggles are **not** inferred from proximity. A climbing gym two miles away does not imply the athlete has climbing hardware at that locale. Toggles are explicit per-locale.

---

## J.1 Locale-level fields

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Locale Name | Text (e.g., "Home — Austin", "Nashville hotel", "In-laws — Portland") | 1 | Display label only | Self-report |
| Location | Place lookup → lat/long (auto-filled; athlete can correct) | 1 | Proximity cluster computation; terrain defaults; weather-API heat tracking; event travel distance estimates | Place lookup |
| Gym Chain Memberships | Multi-select from chain list (e.g., Planet Fitness, LA Fitness, Anytime Fitness, YMCA) + "Independent gym" option | 2 | When athlete sets a new travel locale in the same chain, system surfaces stored gym-equipment profile as a starting point; reduces re-entry burden for frequent travelers | Self-report |
| Is Primary Locale | Boolean | 1 | Designates the home base; first locale created defaults to primary | System-set (athlete can override) |

**Dropped from v1:** Linked Primary Locale FK — replaced by proximity model above.

---

## J.2 Equipment Inventory

Equipment availability at this locale. Structured as a checklist against the canonical equipment list from `Vocabulary_Audit_v2.md` §3 (121 items across 17 categories + 9 Assumed Universal items).

**Assumed Universal items** (always present, not on the checklist): Bodyweight, Wall, Doorway, Chair, Floor, Stairs, Backpack, Timer, Tape measure.

**v2 changes vs v1 equipment list:**

| Change | Items |
|---|---|
| Added | Bench (flat), Foam pad, Incline board |
| Dropped | Jacob's Ladder, Compression boots (Normatec), Sauna access, Stretch strap |
| Renamed / consolidated | Per `Vocabulary_Audit_v2.md` §5 rename table — e.g., "Band" → "Resistance Band", "MTB" → "Mountain Bike", "Cable" → "Cable Machine" |

The full canonical equipment list is the authoritative reference. The UI checklist presents items grouped by category (Barbells & Bars / Dumbbells / Kettlebells / Machines / Bodyweight & Portable / etc.).

---

## J.3 Sport-Specific Gear Readiness Toggles

12 rolled-up sport-specific gear readiness toggles replace v1's sub-component checklists. Canonical toggle names are defined in `Vocabulary_Audit_v2.md` §4.1. Each toggle is a binary ready/not-ready state at the locale level.

| Toggle (canonical name per Vocabulary_Audit_v2 §4.1) | Tier | What it gates |
|---|---|---|
| Climbing — roped | 2 | Lead climbing, top-rope, multi-pitch exercise selection; also satisfies Rappelling / abseiling check |
| Bouldering | 2 | Bouldering-specific exercise selection |
| Rappelling / abseiling | 2 | Rappel / abseil sessions; also satisfied by Climbing — roped (roped passes rappelling) |
| Via ferrata | 2 | Via ferrata sessions |
| Mountaineering | 2 | Alpine / glacier sessions; hard gate without avalanche safety endorsement on col-type terrain |
| Whitewater paddling setup | 2 | Whitewater kayak / packraft sessions above Class II |
| Touring / AT ski setup | 2 | Ski mountaineering, randonnée sessions |
| Classic XC ski setup | 2 | Classic cross-country ski sessions |
| Skate XC ski setup | 2 | Skate cross-country ski sessions |
| Fencing setup | 2 | Fencing technical drills; modern pentathlon fencing leg |
| Shooting setup | 2 | Biathlon / modern pentathlon shooting sessions (range access implicit) |
| Snowshoeing setup | 2 | Snowshoe-specific conditioning sessions. Note: snowshoes are a single-item kit — this toggle is effectively "snowshoes present Y/N" with no sub-component rollup |

**Roped climbing passes rappelling check:** an athlete with Climbing — roped enabled is assumed to have gear sufficient for rappelling. The reverse is not true.

---

## J.4 Terrain Access

Terrain types available within practical reach of this locale. Drives session location planning and exercise selection for terrain-specific skills.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Terrain types | Multi-select from `Vocabulary_Audit_v2.md` §3 terrain canonical list (15 types — e.g., Trail access, Hill / mountain access, Flat road, Whitewater access, Snow terrain, Open water access, Indoor climbing wall) | 1 | Session planning; terrain-specific exercise eligibility; identifies gaps (e.g., no hills → hill-substitute programming) | Self-report |
| Seasonality | Per terrain type: climate-derived defaults (system infers from locale lat/long + month) + per-month athlete override | 2 | Disables terrain types in months when unavailable; adjusts to athlete's local reality (e.g., snow earlier/later than climate average) | System + self-report |

---

## J.5 Locale Capacity Metrics

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Typical session time available | Enum (< 45 min / 45–60 min / 60–90 min / 90–120 min / > 120 min) | 2 | Session length defaults when this locale is active; shorter windows prioritize compound movements and drop accessory work | Self-report |
| Max session duration (hard constraint) | Number (minutes, optional) | 3 | Hard cap applied at plan generation; no session exceeds this limit at this locale | Self-report |

---

---

# Section K — Locale Schedule

*Was v1 §L. Expanded to host joint-training overlays and recurrence templates.*

A Locale Schedule overlay is a date-range record that overrides or supplements the athlete's default weekly schedule. Three sub-types:

- **K.1 Self-overlays** — travel, blackout, locale switch, constraints
- **K.2 Joint-training overlays** — same structure as K.1 plus joint-training-specific fields when linked to an Athlete Link
- **K.3 Recurrence templates** — generates K.1 or K.2 instances on a rolling forward window

All overlay types share the base fields in K.1. Joint-training overlays add the K.2 fields on top.

---

## K.1 Self-overlays (base overlay fields — applies to all types)

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Start Date | Date | 1 | Overlay window start | Self-report |
| End Date | Date | 1 | Overlay window end | Self-report |
| Active Locale | FK to Locale (J.1) | 1 | Equipment pool and terrain available during this window; if null, inherits current primary locale | Self-report |
| Date-Specific Constraints | Multi-select (At home only / Indoor only / Short sessions only / Other) + free text when Other | 2 | Session type restrictions during overlay window; plan-gen applies these on top of the active locale's normal profile | Self-report |
| Notes | Free text | 3 | Context for planner; not machine-read | Self-report |

---

## K.2 Joint-training overlay fields

Additional fields present when the overlay is linked to an Athlete Link. Can be added to any K.1 overlay at creation or retroactively.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Joint Training Link | FK to Athlete Link (§L) | 1 | Identifies which training partner this overlay concerns; gates K.2 fields | Self-report |
| Joint Training Status | Enum (Proposed / Accepted / Declined / Expired) | 1 | Plan-gen only reads Accepted overlays for joint sessions; Declined records preserved for proposer audit trail | Self-report; updated by linked athlete |
| Proposed By | FK to user account | 1 | Identifies who initiated; system-set | System-set |
| Notes from Proposer | Free text | 3 | Context passed to linked athlete with invitation | Self-report |
| Source | Enum (Single / Generated-from-Recurring) | 1 | Identifies whether this instance was created manually or auto-generated from a K.3 template | System-set |
| Parent Recurrence | FK to K.3 Recurring template (nullable) | 1 | Set when Source = Generated-from-Recurring; null for Single instances | System-set |

**Storage model:** when User A proposes and User B accepts, two overlay records are created — one in each athlete's §K — linked by a shared joint-training-instance ID. Declined records are not deleted; they remain visible to the proposer as an audit trail.

**Plan-gen reads Accepted joint overlays as follows:** for the dates covered, each athlete's existing prescription is read; plan-gen seeks the session design most beneficial to both given their respective phases, the resolved locale's terrain and equipment, and the Proposer's Notes as tiebreaker context (not as override instruction).

---

## K.3 Recurrence templates

A Recurrence template defines a repeating joint-training pattern and generates individual K.1/K.2 instances on a rolling forward window (default 8 weeks; finalize with engineering per Deferred #10).

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Pattern | Enum (Weekly / Biweekly) + Day-of-week multi-select (Sun–Sat, 1+) | 1 | Forward-generation schedule | Self-report |
| Start Date | Date | 1 | First possible generated instance | Self-report |
| End Date | Date (nullable — open-ended if null) | 2 | Last possible generated instance; null = ongoing until cancelled | Self-report |
| Template Status | Enum (Active / Cancelled) | 1 | Cancelling halts forward generation; already-generated future instances are not auto-deleted — each requires individual handling | System-set (athlete action) |
| Inherited overlay fields | Active Locale, Date-Specific Constraints, Joint Training Link (if joint template), Notes from Proposer | — | Copied to each generated instance at generation time; instance-level overrides do not affect the template | Self-report (at template creation) |

**Instance audit trail:** generated instances carry Parent Recurrence FK and Source = Generated-from-Recurring. If the template is later cancelled, already-generated instances retain the FK to the cancelled template — the Status = Cancelled on the template is the signal, not a null FK.

**Single-instance override:** either party in a joint recurring template can modify an individual generated instance (change locale, decline that date, adjust constraints) without touching the template.

---

---

# Section L — Athlete Network

*New in v2. Takes the §N letter slot. Replaces v1's inline Training Partner record on §L and the v1 Team Composition Record on §N.*

**Sole authoritative source for this section:** `V2_spec_decisions_handoff.md` Decision 1. Do not re-incorporate fields from the deleted `Athlete_Link_Entity_v2.md` — that version is superseded.

---

## L.1 Athlete Link

One record per training partner or race teammate. A single Athlete Link can carry both relationship types simultaneously.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Partner Name | Text (display name) | 1 | Displayed in joint overlay UI, team composition view, and plan notes | Self-report |
| Linked Account | FK to user account (optional) | 2 | When set: changes to the linked athlete's profile propagate to shared plan adjustments per Plan Management spec; consent flow in Account Configuration | Consent flow (Account Config) |
| Relationship Types | Multi-select: Solo Training Partner / Race Teammate (at least one required) | 1 | Gates conditional fields below; drives §K joint-training overlay collection; for Race Teammate: drives team ceiling logic, role assignment, cross-plan alignment | Self-report |
| Partner-specific Rules | Free text | 3 | E.g., "limit hikes to 2 hours", "prefers morning sessions". Read by plan-gen as soft constraints on joint sessions | Self-report |

---

## L.2 Race Teammate conditional fields

Collected when Relationship Types includes Race Teammate.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Race Event Association | FK to §H Target Event (1 or more; same Athlete Link can cover multiple events) | 1 | Links this teammate relationship to specific events; gates discipline focus collection; drives team ceiling = slowest-member logic per associated event | Self-report |
| Discipline Focus on Team | Multi-select from the associated event's Constituent Disciplines | 2 | For relay-style events and AR with delegated legs: informs cross-training framing on joint dates; affects which teammate's baseline is the constraint for each discipline | Self-report |

**What was removed vs. earlier drafts:** Role on Team enum (Captain / Navigator / Pacer / Specialist) and Discipline-specific role notes. These were in the deleted `Athlete_Link_Entity_v2.md`. Discipline Focus on Team captures the functionally important information without the role taxonomy.

**Not modelled:** Coach, Training Group, Race Crew — out of scope. Team-training spec to revisit if evidence of need emerges post-launch.

---

---

# Group 2 — Account Configuration

Account-level entities. Not plan-gen inputs directly — they determine *what data the system can pull* and *what the athlete has consented to*.

---

## Account Config 1 — Connected Services

One record per integrated third-party service. Source of athlete activity data (FIT files, wellness sync).

| Field | Type | Notes |
|---|---|---|
| Service Name | Enum (Garmin / Strava / Apple Health / Polar / Wahoo / Suunto / COROS — extendable) | Launch tier: Garmin, Strava, Apple Health |
| Connection Status | Enum (Connected / Disconnected / Auth Error / Sync Paused) | System-set |
| Last Sync | Timestamp | System-set |
| Scopes Granted | Multi-select (Activity data / Wellness / Sleep / HR / Power / GPS track) | System-set from OAuth flow; athlete cannot grant scopes the service doesn't offer |
| Sync Direction | Enum (Pull only / Push only / Bidirectional) | System-set per service integration; Garmin = Pull at launch |

**At launch:** Connected Services are manual-upload equivalents (FIT file upload). OAuth integration is the post-launch upgrade path. Section wording at launch should reflect manual-upload-at-launch posture per v2 spec note.

**Effect side lives in Plan Management.** When a Connected Service connects, disconnects, or errors, the athlete-data effects (field auto-fill, staleness flags, re-test prompts) are handled in Group 3 (M.2 Account Config events).

---

## Account Config 2 — Gym Memberships

| Field | Type | Notes |
|---|---|---|
| Gym Chain | Text or FK to chain list | Athlete adds the chains they have active memberships at |
| Membership Active | Boolean | Inactive memberships are retained for history but not surfaced in locale setup |

**Drives:** when athlete creates a new locale in a city where a member-chain has locations, system surfaces the stored gym-equipment profile from another locale at that chain as a starting point for J.2. Does not auto-set equipment — surfaces as suggestion for athlete to confirm.

---

## Account Config 3 — Disclosure Acknowledgment Records

Storage backing for §A.1 disclosures. One record per disclosure type per acknowledgment event.

| Field | Type | Notes |
|---|---|---|
| Disclosure Type | FK to disclosure category (from §A.1) | E.g., Medical disclaimer, Data use, Injury liability |
| Acknowledged At | Timestamp | System-set on athlete confirmation |
| Version Seen | Text (disclosure version string) | Enables re-prompt when disclosure copy changes materially |
| Delivery Method | Enum (In-app / Email) | Audit trail |

**Pre-launch blocker:** disclosure copy is PLACEHOLDER — refine with product/legal before ship (Open Item #1).

---

## Account Config 4 — Privacy and Linked-Partner Sharing

One record per Athlete Link (§L) where Linked Account is set.

| Field | Type | Notes |
|---|---|---|
| Athlete Link | FK to Athlete Link (§L) | The relationship this consent applies to |
| Consent Scope | Enum (None — name only / Activity summaries — session completion, duration, discipline / Full plan access — all prescriptions visible to linked partner) | Athlete controls; defaults to None until explicitly upgraded |
| Consent Granted At | Timestamp | System-set on consent action |
| Consent Revoked At | Timestamp (nullable) | System-set on revocation; revocation strips linked-data scope immediately and flags the Athlete Link as name-only |

**Multi-partner consent (N>2):** partial-link behaviour decided (link forms, non-consenters see nothing); detailed UX deferred to team-training spec (Open Item #12).

---

---

# Group 3 — Plan Management

Lifecycle events and runtime logic. Not athlete-facing data points — these are how the system responds to data changes, plan signals, and account events.

---

## Plan Management 1 — Plan Duration and Event Prefix Logic

When §H.1 (Specific Event?) = Yes:
- Plan duration is derived from today → event date, subject to the minimum base phase for each constituent discipline (from `Sports_Framework_v6.xlsx` Discipline Library).
- If timeline is too short for a legitimate plan, system surfaces an honest assessment and does not generate a plan that sets the athlete up to fail.

When §H.1 (Specific Event?) = No:
- Athlete selects Plan Duration from enum: 8 / 12 / 16 / 20 / 24 weeks.
- Maximum 24 weeks user-facing. Generation strategy for weeks 13+ is Open Item #9 — options are (a) simpler/cheaper LLM for later weeks, (b) generate weeks 1–12 only and produce a re-gen handoff for weeks 13+. Decide pre-launch.

---

## Plan Management 2 — Profile Update Triggers (§M)

*Slotted from `Sections_GHMN_v2_Batch.md` §M.1–M.4.*

### M.1 Athlete data lifecycle triggers

| Trigger | What updates |
|---|---|
| Athlete adds new locale | Prompt for J.2–J.5 fields at new locale |
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
| New event added to §H | Recalculate periodisation; confirm event disciplines + terrain; trigger Sleep Dep prompt if Estimated Duration > 20 hr |
| Event details change (URL fetch) | Flag changes; adjust terrain-specific exercise selection |
| Season changes (inferred from weather + month) | Adjust terrain and session planning per locale seasonality |
| Athlete completes a training block | Prompt for benchmark re-test |
| **Athlete reports plan adherence dropping** *(self-reported)* | Branch to root cause: bored / busy / injured / ill / life stress. Each branch routes to its own response. Full branching logic in `Adherence_Drop_Spec_v2.md` |
| **System detects plan adherence dropping** *(4 consecutive flagged sessions)* | Fire adherence-drop prompt; route through opt-in confirmation per branch. Full detection logic, periodisation overrides, and stacking rules in `Adherence_Drop_Spec_v2.md` |

**Bolded rows are new in v2.**

### M.2 Account Config events that affect athlete data

| Account Config event | Athlete data effect |
|---|---|
| Connected Service connects | Begin pulling activity / wellness data; offer to backfill §F fields if values aren't present |
| Connected Service disconnects | Stop auto-fill; flag fields as stale at next plan generation; revert to manual-entry expectations |
| Connected Service scope reduced | Re-check which fields can still auto-fill; prompt athlete for any newly-uncovered fields |
| Connected Service auth fails / sync stops | Stale-data warning at plan generation; prompt athlete to reconnect |
| Gym membership added | Surface gym-equipment profile suggestions at any locale in that chain |
| Gym membership removed | Re-evaluate whether gym-dependent exercises remain valid at affected locales |

### M.3 Adherence-drop detection threshold

**4 consecutive flagged sessions** triggers the adherence-drop prompt. A session is flagged when: skipped, volume short (<70% of prescribed), volume over (>130%), or intensity off by >2 RPE in either direction. Full detection logic, branching, athlete-facing prompts, periodisation overrides, and stacking rules: see `Adherence_Drop_Spec_v2.md`.

### M.4 Soft Warning / Hard Gate / Profile Prompt classification

| Classification | Behaviour | Examples |
|---|---|---|
| **Hard gate** | Plan generation is blocked. Clear reason given. Athlete must resolve to proceed. | Missing HRmax when HR-zone training is planned; no pack-carry locale when pack-required event is in plan |
| **Soft warning** | Plan generates. Flag surfaces to athlete. No action required to proceed. | FTP not re-tested in >8 weeks and cycling intervals are scheduled; cycling event >4 hr without saddle endurance baseline |
| **Profile prompt** | Background nudge; no blocking. Athlete can dismiss. | "It's been 9 weeks since your last FTP test — would you like to schedule one?"; Sleep Dep field not collected for >20hr event |

Hard gates phrase as safety stops. Soft warnings phrase as flags for attention. Profile prompts phrase as nudges.

---

## Plan Management 3 — Joint Training Generation

When a §K Recurring template has Template Status = Active:

- System generates individual K.1/K.2 instances on a **rolling 8-week forward window** (finalize with engineering per Deferred #10).
- Generated instances default to Status = Proposed (joint templates) or accepted (self-templates), Source = Generated-from-Recurring, Parent Recurrence = FK.
- Either party can override a single generated instance (decline a specific date, change locale for one occurrence) without affecting the template.
- Cancelling the template halts forward generation. Already-generated future instances remain; each requires individual handling (athlete can decline, re-accept, or leave as-is).
- When both athletes in a joint template are at different locales for a generated date, system flags a locale mismatch and prompts reconciliation.

---

## Plan Management 4 — System-Tracked Heat Acclimatization

Replaces the dropped §I Heat Acclimatization History field.

- System infers heat exposure from workout date + active locale coordinates + weather API (temperature, humidity, heat index).
- Exposure accumulates toward acclimatization threshold (typically 10–14 days of training in ≥32°C / ≥90°F heat index conditions).
- Acclimatization state is not athlete-reported — it is derived and stored as a Plan Management record.
- When acclimatization is insufficient for an upcoming hot-weather event, system surfaces a soft warning and inserts heat-training sessions into the plan.

---

## Plan Management 5 — Multi-Athlete Plan Sync

**Out of scope for first v2 publish.**

How accepted joint-training overlays are read by plan generation to align prescriptions across athletes — the specifics of cross-plan coordination for linked athletes — are deferred to the team-training spec session. The data model (Athlete Link, §K joint overlays, consent scope in Account Config 4) is in place; the generation logic is not.

---

---

# Implementation checklist — batch 4+5

Replace the pending stubs in `Athlete_Onboarding_Data_Spec_v2.md` with the drafted sections above. In order:

- [ ] Replace §I stub with §I.1 (core lifestyle) + §I.1.1 (race-day caffeine sub-question) + §I.2 (race-day fueling) + §I.3 (sleep deprivation, conditional)
- [ ] Replace §J stub with J.1 (locale fields) + proximity model block + J.2 (equipment) + J.3 (toggles) + J.4 (terrain) + J.5 (capacity)
- [ ] Replace §K stub with K.1 (self-overlays) + K.2 (joint-training overlay fields) + K.3 (recurrence templates)
- [ ] Replace §L stub with L.1 (Athlete Link) + L.2 (Race Teammate conditional fields)
- [ ] Replace Group 2 stub with Account Config 1–4
- [ ] Replace Group 3 stub with Plan Management 1–5 (including §M.1–M.4 slotted in)
- [ ] Update Drafting status table — mark §I, §J, §K, §L, Group 2, Group 3 as ✅ Drafted (batch 4+5)
- [ ] Update spec version status line: "Batches 1–5 complete. Spec body complete pending Open Items."
- [ ] Confirm proximity radius (26.2 mi / 42.2 km) is acceptable or adjust
- [ ] Confirm Open Items #10 (rolling window length) can be closed once engineering confirms 8 weeks

---

# Open Items — no new items from batch 4+5

All batch 4+5 content derived from locked decisions. No new open items introduced.

Existing open items affected by this batch:

| # | Item | Status after this batch |
|---|---|---|
| 10 | Recurring §K rolling-window length | Direction set (8 weeks). Close once engineering confirms |
| 12 | Multi-partner consent rules (N>2) | Unchanged — team-training spec |
| 13 | Stale-link cleanup | Unchanged — team-training spec |
| 15 | Linked-account consent flow | Direction set in Account Config 4. Full flow in Plan Management spec |
