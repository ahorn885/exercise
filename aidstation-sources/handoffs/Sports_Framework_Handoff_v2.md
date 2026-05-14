# Sports Framework v3 — Handoff Document (v2)
**File:** `Sports_Framework_v3.xlsx`  
**Previous handoff:** `Sports_Framework_Handoff.md` — superseded by this document  
**Status:** Active. All 18 sports fully populated. Athlete Profile revised per product design session.  
**Built:** Claude + Andy, April–May 2026

---

## What This Is

A multi-sport endurance training rule set database. It encodes coaching logic, research evidence, and training protocols across 18 endurance sports and 32 disciplines in a structured format that LLM prompts can read to generate sport-specific, athlete-specific training plans.

**This is not a training plan generator itself.** It is the reference database that training plan prompts pull from. Other sessions handle: UX flow design, actual prompt construction, plan output formatting, and database/app integration. This session focuses exclusively on the data model.

---

## Product Context

The framework is being built to support a training plan app with three distinct data layers:

**1. Athlete Profile** — Who the person is, what they've done, their physical and discipline baselines. Collected once at onboarding, updated periodically. Documented in Sheet 7 (Sections A–I).

**2. Locale Profile** — Location-specific training context: equipment available, terrain accessible, water/snow access, training partner availability. Multiple locales supported per athlete. At least one (home) required at account creation. Documented in Sheet 7 (Section J). Equipment and environment data live here, not on the athlete profile.

**3. Event Profile** — Target race specifics. Optional — users without a specific event get a time-based fitness plan instead. Documented in Sheet 7 (Section F).

**Why three layers matter for prompt design:** When generating a training plan for a given week, the LLM prompt receives the Athlete Profile (static) plus the *active Locale* for each training day (dynamic). The athlete who is home on Monday has access to their home gym; the same athlete traveling Thursday has access to their hotel locale. The plan adapts per-day based on active locale, not a single static equipment list.

---

## File Structure — 7 Sheets

```
Sheet 1: Sports Index              ← One row per sport (metadata)
Sheet 2: Discipline Library        ← One row per discipline (universal training rules)
Sheet 3: Sport × Discipline Map    ← Join table (sport + discipline + sport-specific context)
Sheet 4: Discipline Pairing Matrix ← Which disciplines pair well/poorly on the same day
Sheet 5: Phase Load Allocation     ← % of weekly training hours per discipline per phase
Sheet 6: Team Format Cross-Reference ← How team racing formats affect training
Sheet 7: Athlete Profile Data Points ← Data model for athlete onboarding and plan generation
```

The schema is **normalized**: discipline facts are stored once in Sheet 2. Sport-specific context is stored in Sheet 3. No fact is duplicated across sheets. Updating a research finding means editing one cell, not hunting through 18 sport entries.

---

## Sheet 1: Sports Index

**19 rows** (header + 18 sports). **12 columns.**

| Col | Field | Notes |
|-----|-------|-------|
| 1 | Sport | Join key used across all sheets |
| 2 | Governing Bodies | Authoritative race organizations |
| 3 | Race/Event Formats | All sub-formats and distances |
| 4 | Typical Duration Range | Shortest to longest |
| 5 | Team vs. Solo | Format options |
| 6 | Navigation Required? | YES/NO/PARTIAL — activates D-013 training |
| 7 | Sleep Deprivation Training? | YES/NO — activates overnight session requirement |
| 8 | Pack/Load Carry? | YES/NO — affects energy expenditure calculations |
| 9 | Transition Training Required? | YES/NO — activates brick session scheduling |
| 10 | # Primary Disciplines | |
| 11 | # Secondary/Minor Disciplines | |
| 12 | Status | All 18 are ACTIVE |

**The 18 sports:**
1. Adventure Racing
2. Triathlon
3. Ultramarathon (Road and Trail)
4. Long Distance / Endurance Cycling *(covers road gran fondo, gravel, TT, XC MTB, Enduro)*
5. Duathlon
6. Aquathlon
7. Aquabike
8. Swimrun
9. Skimo (Ski Mountaineering Racing)
10. Mountain Running / Skyrunning
11. Fell Running
12. Modern Pentathlon *(post-2025 format: Fencing, OCR, Swimming, Laser Run)*
13. Marathon (Road and Trail)
14. Off-Road / Adventure Multisport (Non-Nav) *(XTERRA, Quadrathlon, free-format)*
15. Cross-Country / Nordic Skiing
16. Biathlon
17. Canoe / Kayak Marathon
18. Open Water Marathon Swimming

**Planning flags that drive decisions:**

- **Navigation = YES or PARTIAL:** D-013 (navigation) becomes a training discipline. For Fell Running specifically, nav is tagged Primary (not cross-discipline) because GPS is explicitly prohibited (disqualification offense) and fatalities have occurred from nav errors. For AR, nav is primary and the most cognitively demanding discipline under sleep deprivation (ES -2.12 — strongest effect of any discipline).
- **Sleep Deprivation = YES:** Plan must include intentional overnight/sleep-limited training sessions. AR, 100-mile ultra, fell mountain marathon, canoe marathon ultra. *Note: in the Athlete Profile (Section F), "sleep deprivation expected" is no longer asked directly — it is auto-inferred when race duration >20 hours.*
- **Pack Carry = YES:** Weighted vest or loaded pack training simulates race conditions. Energy expenditure calculations include pack weight. AR (~25–35 lb race pack), Skimo (mandatory kit weight), Mountain Running (mandatory safety kit).
- **Transition = YES:** Brick sessions are required. Handoff mechanics are a specific trainable skill.

---

## Sheet 2: Discipline Library

**33 rows** (header + 32 disciplines). **13 columns.**

| Col | Field |
|-----|-------|
| 1 | Discipline ID (D-001, D-002, etc.) |
| 2 | Discipline Name |
| 3 | Discipline Category |
| 4 | Sports It Appears In |
| 5 | Min Base Phase Before Technical Work |
| 6 | Periodization Phases & Durations |
| 7 | Max Safe Weekly Volume Ramp (ACWR 0.8–1.3) |
| 8 | Age-Adjusted Ramp (40–44 / 45–54 / 55+) |
| 9 | Taper Norms |
| 10 | Common Overuse Injury Patterns |
| 11 | Training Behaviors Preceding Injuries |
| 12 | Recovery Priority & Key Modalities |
| 13 | Evidence Quality |

**Complete discipline list:**
```
D-001  Trail Running
D-002  Road Running
D-003  Hiking (Weighted / Loaded)
D-004  Open Water Swimming
D-004b Pool Sprint Swimming (200m — variant for Modern Pentathlon)
D-005  Road Cycling (Road / Gravel / Tri / TT)
D-005a Road Cycling — TT / Tri Bike Variant (equipment variant, not a new discipline)
D-006  Mountain Biking (Technical Trail / MTB)
D-007  Packrafting
D-008  Kayaking (Flat / Whitewater / Ocean)
D-009  Canoeing
D-010  Rock Climbing (Fixed Route / AR Context)
D-011  Abseiling / Rappelling
D-012  Fixed Rope / Via Ferrata
D-013  Orienteering / Navigation
D-014  Swimming (Open Water / River Crossing)
D-015  Snowshoeing
D-016  Mountaineering (Glacier / Crampon Travel)
D-017  Paddle Rafting (Team Raft)
D-018  Swimrun (Swimming + Running — Combined)
D-019  Uphill Skinning (Skimo Ascent)
D-020  Alpine Descent (Skimo Downhill)
D-021  Boot-packing & Transitions (Skimo Technique)
D-022  Uphill Mountain Running (Extreme Vertical Ascent)
D-023  Downhill Mountain Running (Technical Descent / Eccentric Load)
D-024  Épée Fencing (Combat Sport — Modern Pentathlon)
D-025  Laser Run (Shooting + Running — Combined, Modern Pentathlon)
D-026  Obstacle Course Racing (Ninja/OCR — Modern Pentathlon)
D-028  Cross-Country / Nordic Skiing (Classic + Skate)
D-029  Biathlon Shooting (Rifle at 50m — Prone + Standing)
D-030  Marathon Paddling (Long-Distance Canoe / Kayak)
D-031  Open Water Distance Swimming (10km+ Marathon)
```

*Note: D-027 was not created — numbering skipped intentionally during build. Not an error.*

**Architecture decisions encoded in the library:**

- **Equipment variants ≠ new disciplines.** TT/tri bike = D-005a. Pool sprint swimming = D-004b. The test: does the training methodology differ enough to warrant separate periodization? If yes, new discipline. Same methodology + different kit = variant.
- **Swimrun = D-018 (combined entry).** Swimrun is genuinely different — athletes run in wetsuits and swim in shoes, and cannot separate the two disciplines. It warrants its own entry rather than forcing it into D-004 + D-001.
- **D-026 (OCR) is explicitly flagged as evidence-limited.** OCR replaced equestrian in Modern Pentathlon at senior level from 2025. No peer-reviewed sport science exists for it in this context yet. The entry draws from ninja training principles and UIPM specifications. This is the only discipline in the library built primarily on practitioner consensus. Review annually as research accumulates.

**The most consequential rules in the library (for prompt design):**

| Discipline | Rule | Evidence |
|------------|------|----------|
| D-004 (OW Swim) | Paddle use in swim training significantly associated with shoulder overuse (p=0.014). Limit paddles to 1×/week max. | PMC5983428 |
| D-007/D-008 (Paddle sports) | Tendons lag muscle by 4–8 weeks. Max 3 hard grip/paddle sessions per week regardless of fitness. | Tendon physiology literature |
| D-010 (Climbing) | Min 5 strict pull-ups before structured climbing. 8–12 week grip base before heavy climbing. A2 pulley is the most common injury site. | Climbing injury literature |
| D-013 (Navigation) | Sleep deprivation effect on nav performance: ES -2.12. Strongest effect of any discipline. | PMC study |
| D-019/D-022 (Skimo/Mountain uphill) | **Vertical gain per week (metres) is the primary load metric**, not hours or distance. | Practitioner consensus; Uphill Athlete methodology |
| D-023 (Downhill running) | **Prior exposure is the ONLY proven preventive strategy for EIMD.** 30 min at -20% grade causes quad strength decrements lasting 4 days. Final steep session must be ≥10 days before race — hard rule, not guideline. | PMC11129977; PMC7674385 |
| D-028 (XC Skiing) | **Never combine elevated volume AND elevated intensity in the same day.** Only 5% of world-class training days do both. | PMC12094961 |
| D-029 (Biathlon Shooting) | Primary performance differentiator is HR management skill (lowering HR from 170-180 bpm to shooting accuracy threshold in 20–30 seconds), not raw shooting accuracy. | IBU coaching literature |
| D-031 (OW Marathon Swim) | Feeding adequacy and thermoregulation are the two primary determinants of success — not swimming fitness. Target 90g carbs/hr. 8–10 weeks cold water acclimatization mandatory before cold-water races. | PMC2694459; PubMed 24667305 |

---

## Sheet 3: Sport × Discipline Map

**62 rows** (header + join entries). **8 columns.**

| Col | Field |
|-----|-------|
| 1 | Sport |
| 2 | Discipline ID |
| 3 | Discipline Name |
| 4 | Role in This Sport (Primary / Secondary / Minor / Technical) |
| 5 | Est. % of Race Time |
| 6 | Sport-Specific Context ← **the critical column** |
| 7 | B2B Pairing Rule (preferred/acceptable next discipline) |
| 8 | Phase Load (% of weekly training hours: Base / Build / Peak / Taper) |

**Column 6 is where normalized discipline facts get layered with sport-specific nuance.** Example: D-004 (OW Swimming) appears in both Triathlon and OW Marathon Swimming. The library holds universal facts (paddle caution, shoulder patterns, ACWR). The sport-specific context explains: in Triathlon, the swim is 15–20 minutes and mass start management is the key skill; in OW Marathon Swimming, it is 2 hours and feeding from pontoons every 2.5km is mandatory and tactical. Same discipline, completely different race implications.

**Phase load percentages are ranges, not targets.** They reflect typical allocations for a well-constructed plan, not formulas to apply mechanically. Course-specific adjustments are significant — a rolling trail marathon is ~80–90% D-001; a mountain trail marathon with 5000+ ft gain is ~50% D-001 + 25% D-022 + 20% D-023.

---

## Sheet 4: Discipline Pairing Matrix

A **17×17 grid** covering D-001 through D-017. Each cell: PREFERRED / ACCEPTABLE / AVOID / N/A with a rationale note.

**How to read it:** Row discipline + Column discipline = recommendation for training both on the same day.

**Known gap:** The matrix covers D-001 through D-017 only. Disciplines D-018 through D-031 are not yet represented. This is a pending extension — the pairing logic for those disciplines is documented in the Sport × Discipline Map (column 7) but not in the grid.

---

## Sheet 5: Phase Load Allocation

**98 rows** — one sport's complete phase allocation broken into rows per discipline, with a summary total row. **9 columns.**

| Col | Field |
|-----|-------|
| 1 | Sport |
| 2 | Discipline ID |
| 3 | Discipline |
| 4 | Role |
| 5–8 | Base / Build / Peak / Taper (% of weekly hrs) |
| 9 | Notes / Conditions |

**Total rows** are formatted dark blue (1F4E79) and provide weekly hour targets alongside the split. These are the actionable anchors for plan generation.

**Two metrics run in parallel for mountain sports:** For Skimo (D-019), Mountain Running (D-022), and XC Skiing (D-028), vertical gain per week (metres) is tracked alongside hours. The Notes column includes vertical gain progression tables for these sports.

**Taper logic varies significantly by sport — not uniform:**
- Road marathon: 2–3 weeks, 40–60% volume cut (Bosquet et al. 2007 meta-analysis)
- Mountain running: 2–3 weeks, but final steep descent session ≥10 days before race
- XC MTB: reduce technical volume 10–12 days before race (CNS recovery longer than aerobic)
- Enduro MTB: reduce high-commitment descent training 14 days before multi-day event
- OW marathon swimming: 1–2 weeks (shorter than running tapers)
- Biathlon/Modern Pentathlon: never fully eliminate shooting or fencing in taper — skill regression is rapid

**Ultra nutrition gap embedded in Notes:** Finishers of 100-mile races average ~70g carbs/hr and 250–333 kcal/hr. Non-finishers: <45g carbs/hr and <200 kcal/hr. Gut training is flagged as mandatory on every long run over 2 hours — this is a physiological adaptation, not just nutrition advice.

---

## Sheet 6: Team Format Cross-Reference

Documents how team racing formats affect training logic across all 18 sports. Four paradigms defined:

**UNIFIED TEAM:** All members complete every discipline together. Team moves as a unit, cannot separate. Team's pace in each discipline is bounded by the slowest member. Training implication: every member trains all disciplines, no specialization. Examples: Adventure Racing (primary format), Swimrun (mandatory pairs), Fell Mountain Marathon (mandatory pairs), Skimo Team.

**RELAY / SPECIALIST:** Members each do a subset of disciplines; others sit out. Training implication: each athlete trains assigned leg(s) only, deep specialization is the strategy. Examples: Triathlon relay, XC Ski relay, XTERRA relay, Quadrathlon relay.

**DOUBLES / PAIRS:** Two athletes share the same craft simultaneously. Both train the same discipline. Cannot separate or specialize. Stroke synchronization is a specific additional co-training requirement. Examples: K2 kayak, C2 canoe.

**AGGREGATE:** All members race individually, scores combined. Training is individual. Examples: some marathon and ultra team categories.

**Non-obvious cases worth flagging to any session working with this:**

- **Biathlon relay is not a relay in training terms.** Every relay member must ski AND shoot. No skiing specialist, no shooting specialist. Training demands are identical to individual biathlon.
- **Modern Pentathlon Mixed Relay:** Each relay leg IS itself multi-discipline. Both relay athletes need full 5-discipline preparation.
- **Ragnar-style events** get a dedicated concept note: the primary preparation challenge is sleep deprivation management and running from a cramped van, not running fitness. Athletes are typically over-trained for the running and under-prepared for the logistics.

The sheet also includes a 5-row strategic decisions section covering: format identification, role assignment, unified team co-training, transition/handoff mechanics, and the weakest-link principle.

---

## Sheet 7: Athlete Profile Data Points (Revised)

**143 rows.** The most recently updated sheet. **8 columns** per data row:

| Col | Field |
|-----|-------|
| 1 | Section (A–J) |
| 2 | Data Point Name |
| 3 | Description / What to Capture |
| 4 | Data Type |
| 5 | Priority Tier (1/2/3) |
| 6 | Framework Decision Driven |
| 7 | Sport Applicability |
| 8 | Collection Method |

**Priority tiers:**
- **Tier 1** = Required — cannot generate a meaningful plan without it
- **Tier 2** = Important — significantly improves plan specificity
- **Tier 3** = Optional — fine-tuning or sport-specific

Change notes appear inline as yellow merged rows explaining what was removed, merged, or moved and why. These are intentionally preserved — they document the design rationale.

### The 10 sections:

**A — Athlete Identity (7 data points)**
Name, date of birth (month/year only — not full date), sex (M/F only — hormone treatments captured under medications), height (cm or ft/in both accepted), body weight (kg or lbs both accepted — FIT file parse option), primary training location (seeds the required home locale), home altitude (auto-filled from location).

**B — Health Status (5 data points + 1 change note)**
Combined injury history (current + 3-year history in one prompt, not two separate questions), chronic medical conditions (multi-select of performance-affecting types only — not full medical history), current medications (multi-select of types that affect training prescription only), food allergies and intolerances (nutrition-focused multi-select only, not environmental), resting heart rate (FIT file parse option from wellness FIT).

Removed: Physician clearance. Replaced by disclosure/acknowledgment language at account creation.

**C — Training History (9 data points)**
Years of structured training, primary sport (single select), secondary sports with experience tier (<1yr / 1–3yr / 3+ yr per discipline — not open text years), current weekly training volume, peak historical volume, longest event completed, most recent race results (FIT file upload preferred), training consistency (last 12 months), previous training plans/coaching.

**D — Discipline-Specific Baselines (7 sub-sections, ~35 data points)**
Running, Cycling, Swimming, Paddling, Skiing, Navigation, Strength/Technical.

Key simplifications from original version:
- Night running: Y/N only (removed hours and headlamp model)
- Bike types: type only, no suspension/wheel/gearing specs
- Wetsuit: Y/N + transition comfort (removed own vs. rental — wetsuit ownership goes to locale equipment)
- Packraft: removed PFD tracking (assumed)
- Abseiling: 3-tier (None / 1–3 guided sessions / 4+ or self-directed) rather than Y/N
- Fencing: removed competition ranking
- Shooting: removed certification level; range access moved to locale
- Navigation: only Map & Compass Proficiency remains — GPS prohibition comfort, night nav experience, and route choice decision making all removed

Items moved to Locale (Section J): power meter, indoor trainer, paddle erg, roller skiing equipment, ski erg, shooting range access.

**E — Performance Testing (5 data points + 1 change note)**
HRmax (FIT file parse preferred — Tanaka formula fallback), lactate threshold HR (FIT file derivable), VO2max estimate (FIT file or wearable), cycling FTP test date, critical swim speed.

Section opens with a FIT file guidance banner: prompt for FIT upload first, auto-populate what's derivable, manual entry only as fallback.

Removed: Single-leg balance assessment (lower limb stability addressed through prescribed strength work in the plan, not pre-assessed at onboarding).

**F — Target Race / Event (10 data points + 2 change notes)**
Target sport/format, specific race name and date, race distance and estimated duration (note: sleep deprivation protocol auto-flagged when duration >20 hours — no separate question), race elevation gain/loss, terrain type (multi-select with % breakdown), pack weight/mandatory kit, navigation requirement (4-option: fully marked / checkpoints marked / checkpoints must be plotted / fully self-directed), team format, goal outcome, previous attempts.

Section opens with a banner: event profile is optional — users without a specific event get a time-based plan.

Removed: Sleep deprivation expected (inferred from race duration). Travel frequency (covered by locale setup — hotel locale activates substitution protocols automatically).

**G — Training Environment & Constraints (2 data points + several change notes)**
Available training hours per week, training days available.

Everything else moved: travel frequency → covered by locale setup; home training equipment, terrain access, water access, snow/ski access, training partner availability → all moved to Locale (Section J). Coaching availability removed entirely — app is assumed self-coached; specialist coaching recommendations surfaced as plan notes.

**H — Lifestyle & Recovery (6 data points + 2 change notes)**
Sleep duration, work/life stress level, dietary pattern and concerns (multi-select diet type + optional free text — eating disorder history not collected), supplement protocol, caffeine tolerance and strategy, altitude acclimatization history (prior camps and AMS history — current residence altitude is on the locale).

Removed: Food intolerances as separate question (merged into Section B allergies and Section H dietary concerns). Alcohol use (no framework training decision depends on it directly).

**I — Sport-Specific Additional Data (3 data points + 8 change notes)**
AR team composition profile (account linking for app users; manual entry for non-users; linking and training day synchronization handled post-plan-generation), ultra documented carb tolerance (g/hr), ultra sleep deprivation experience (hours awake + incident history).

Removed: AR previous AR experience (duplicate of Section C race history). Biathlon range access (locale). Pentathlon fencing coach access (eliminated — app is self-coached). Modern Pentathlon OCR facility access (locale). XC skiing technique certification (not actionable). OWS cold water acclimatization status (duplicate of D3). Canoe marathon portage assessment (duplicate of D4). Fell running mandatory kit familiarity (locale equipment + plan note).

**J — Locale Profile Data Points (14 data points)**
This is a new section documenting the Locale schema. It lives in the Athlete Profile sheet because this sheet is the LLM data model reference — having locale schema here means prompts can reference it without loading a separate document.

Locale fields:
1. Locale Name (user-defined label)
2. Locale Type (Primary or Secondary — secondary locales are linked to and only accessible from a primary)
3. Location (country, state/city — seeds altitude auto-fill, climate, terrain lookup)
4. Altitude (auto-filled from location, overridable)
5. Associated Locales (linked secondary locales, e.g., "Gym A accessible when at Home")
6. General Training Equipment (multi-select: barbell, squat rack, dumbbells, kettlebells, pull-up bar, resistance bands, weighted vest, treadmill, rowing machine, smart cycling trainer, basic cycling trainer, kayak/paddle erg, ski erg, climbing wall/hangboard, OCR apparatus)
7. Specialty / Sport-Specific Equipment (multi-select: road bike, gravel bike, MTB hardtail, MTB full-sus, TT/tri bike, kayak/canoe, packraft, rifle/laser pistol, wetsuit, roller skis skate, roller skis classic, power meter)
8. Terrain Access — Running/Hiking (multi-select: road, groomed trail, moderate technical trail, highly technical trail, mountain/alpine, moorland/bog/fell, treadmill only)
9. Max Vertical Gain Available (metres achievable in single session — flags when mountain travel is needed)
10. Water Access (multi-select type + months/year seasonality: pool, flatwater, calm river, moving river, open ocean/large lake, none)
11. Snow Access (months/year)
12. XC Ski Trail Access (Y/N + months per season)
13. Shooting Range Access (Y/N + type + sessions/month available)
14. Training Partner Availability (calendar-based + account linking)

---

## How to Generate a Training Plan Using This Framework

### Step 1 — Identify sport and sub-format
Pull the Sports Index row. Check the four planning flags: Navigation? Sleep deprivation? Pack carry? Transitions? Each flag activates specific plan requirements.

### Step 2 — Collect athlete data
From the Athlete Profile (Sheet 7), minimum Tier 1 data points for the relevant sections. Section F (target race) first — this establishes timeline and scope. Then Section C (training history) for the starting volume. Then relevant Section D sub-sections for the disciplines the race requires.

### Step 3 — Determine active locale
What location will the athlete be training from? Pull that locale's equipment and terrain profile. This determines which exercises and sessions are executable and which require substitution.

### Step 4 — Pull Sport × Discipline Map rows
Filter for the target sport. This gives disciplines to train, their roles (Primary/Secondary/Minor), sport-specific context notes, and phase load percentages.

### Step 5 — Pull Phase Load Allocation
Get the sport's complete phase allocation. Total row gives weekly hour targets. Multiply total hours × discipline % to get hours per discipline per week. For mountain sports, also apply vertical gain targets from the Notes column.

### Step 6 — Apply Discipline Library rules
For each discipline: pull the library row. Minimum base phase, age-adjusted ramp rate, taper norms, injury prevention rules. Apply the athlete's age to column 8 (Age-Adjusted Ramp) if athlete is 40+.

### Step 7 — Apply athlete-specific modifications
- **Age:** Masters ramp rates (8% max for 45–54; 6% for 55+)
- **Current volume:** Never start above athlete's current weekly volume
- **Injuries:** Apply substitution logic per affected movements
- **Downhill adaptation status:** D-023 — if no recent steep downhill training, start at -5% grade max regardless of fitness level
- **Vertical gain baseline:** For mountain sports, apply 10% weekly increase cap from athlete's documented starting point
- **Team format:** Unified team = athlete trains all disciplines; relay = athlete trains assigned leg only

### Step 8 — Apply sleep deprivation protocol (if triggered)
Auto-triggered when race duration >20 hours. Include at least one intentional night-across training session in peak phase. For AR: mandatory sleep planning. For ultra: short naps in second half of night are most effective (58% of 100-mile finishers use sleep management).

### Step 9 — Apply nutrition overlays
- Ultra carbohydrate target: 70g/hr minimum (finisher benchmark)
- Cycling long events: 60–90g/hr
- Gut training: every long session >2 hours is a mandatory gut training session
- Collagen + Vit C: 15g + 50mg, 30–60 min before tendon-loading sessions (climbing, paddle)
- Tart cherry: post-session for high-EIMD disciplines (D-023, D-020)
- Caffeine: use athlete's documented tolerance and strategy from Section H

---

## FIT File Integration

Several data points in the Athlete Profile support auto-population from Garmin (or other GPS/wearable) FIT files:

| Data Point | Source |
|------------|--------|
| Body Weight | Garmin wellness FIT (Garmin Index scale) |
| Resting Heart Rate | Garmin wellness FIT (5-day rolling average) |
| HRmax | Activity FIT from hard race or interval effort (peak HR) |
| Lactate Threshold HR | Activity FIT from 30-min hard effort (average HR) |
| VO2max Estimate | Garmin wearable estimate (wellness or activity FIT) |
| Recent Race Results | Activity FIT files from race efforts |
| Longest Ride | Activity FIT |
| Longest Paddle | Activity FIT |

**Design principle:** Prompt for FIT file upload first. Auto-populate what can be derived. Ask for manual entry only when FIT data is absent or insufficient for a given field. This is especially important for Section E (Performance Testing) — the section opens with a guidance banner reinforcing this sequence.

---

## Team Account Linking (Design Intent — Not Yet Implemented)

The AR team composition profile (Section I) and training partner availability (Section J) reference an account linking system that is designed but out of scope for this data model session. For any session implementing or referencing team features:

- User can indicate they are on a team, training with a partner, or solo
- App offers "search for friend among users" or "my friend doesn't have an account" (invite)
- Training day availability is set per-locale via a date/day selector
- If friend has no account: plan favors team-based skills, no assumptions about friend's fitness
- If friend has an account: they must opt in to sharing their profile data; plan generation with team sync occurs post-opt-in, not immediately
- Training day invitations trigger plan re-normalization between linked accounts — this runs as a batch update (with next plan T1/T2/T3 run), not in real-time, to manage LLM costs
- If friend has no existing plan: their fitness level from their athlete profile is used for effort calibration; plan follows the current user's progression

---

## Research Quality

Evidence quality is rated in column 13 of the Discipline Library:

- **Strong:** Multiple RCTs or meta-analyses with consistent findings
- **Moderate:** 1–2 good studies or consistent moderate-quality evidence
- **Limited:** Very few studies, small samples, or indirect extrapolation
- **Practitioner Consensus:** No peer-reviewed evidence; established coaching practice

**Claims with Strong evidence and specific numbers (use with confidence):**
- ACWR 0.8–1.3 as injury-safe range (27-study SR, Maupin 2020)
- D-023: 30 min at -20% grade → quad MVIC decrement lasting 4 days (PMC11129977)
- D-023: Prior exposure is the only proven EIMD prevention strategy (PMC7674385)
- D-023: CWI has strongest effect size for eccentric EIMD (Moore et al. 2023, 28 RCTs)
- D-013: Sleep deprivation → ES -2.12 for nav/skill performance (strongest discipline effect)
- OW marathon: Feeding and thermoregulation are primary success determinants (PMC2694459)
- Ultra nutrition: Finishers ~70g/hr vs. non-finishers <45g/hr
- Marathon taper: 40–60% progressive volume cut, 2–3 weeks (Bosquet et al. 2007)
- XC skiing: Only 5% of world-class days combine high volume AND high intensity (PMC12094961)
- Triathlon: Cycling performance predicts Sprint/70.3 outcome (PMC8131838, n=16,667)
- Biathlon: No significant shooting difference between elite/non-elite; running is the differentiator (PMC8124855 equivalent)

**Claims to use as guidelines only (Moderate or Consensus):**
- 10% weekly volume rule (weak direct evidence; ACWR preferred)
- Power hiking faster than running above ~25% grade (coaching consensus + biomechanics)
- Portage as performance variable in canoe marathon (practitioner consensus)
- Aero position reduces FTP 3–8% vs. road position

---

## Known Gaps and Pending Extensions

**Discipline Pairing Matrix:** Currently covers D-001 through D-017 only. D-018 through D-031 not yet represented in the grid. Pairing logic for those disciplines exists in Sport × Discipline Map column 7 as a workaround.

**D-027 gap:** Numbering skips from D-026 to D-028. Not an error — was skipped during build.

**OCR evidence:** D-026 (OCR in Modern Pentathlon) is the only discipline built primarily on practitioner consensus. Senior-level OCR only exists from 2025. Review annually as sport science accumulates.

**Locale system:** Section J documents the Locale schema as it needs to exist. The linked-locale concept (secondary locales accessible from primary locales) and the equipment union logic are defined but implementation is outside this data model session.

**Evidence dates:** Research citations reflect evidence available as of April 2026.

---

## File Handling Instructions

**Working copy:** Always copy from outputs to working directory before editing.
```
cp /mnt/user-data/outputs/Sports_Framework_v3.xlsx /home/claude/Sports_Framework_v3.xlsx
```
Work on `/home/claude/` copy. Copy back when done:
```
cp /home/claude/Sports_Framework_v3.xlsx /mnt/user-data/outputs/Sports_Framework_v3.xlsx
```

**Always use Python/openpyxl for edits.** The file uses merged cells, specific font styles, color fills, and borders that cannot be maintained via bash tools. Do not attempt `cat`, `sed`, or any text-mode editing.

**Read before writing.** Always `view` relevant rows before any str_replace or Python edit. Stale context causes errors.

**Preserve the normalized schema.** Discipline facts belong in the Discipline Library (Sheet 2). Sport-specific context belongs in the Sport × Discipline Map (Sheet 3). Do not duplicate discipline-level facts into sport entries.

**Adding a new sport:**
1. Add row to Sports Index (Sheet 1)
2. Add any genuinely new disciplines to Discipline Library (Sheet 2)
3. Add sport × discipline rows to Sport × Discipline Map (Sheet 3)
4. Add phase allocation rows to Phase Load Allocation (Sheet 5)
5. Note in Team Format Cross-Reference (Sheet 6) if the sport has team formats
6. Research before building — always search for sport-specific injury data and protocols first

**Adding or modifying athlete profile data points:**
- Keep Tier 1 minimal — only what's truly required for plan generation
- Equipment and environment data belongs in Section J (Locale), not Sections A–I
- Eliminations should appear as change notes (yellow merged rows) so design rationale is preserved
- FIT file parse options should be noted in the Collection Method column

---

*Handoff document v2. Supersedes Sports_Framework_Handoff.md. April–May 2026.*
