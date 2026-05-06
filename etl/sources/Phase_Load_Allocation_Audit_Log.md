# Phase Load Allocation Audit Log

**Started:** 2026-05-05
**Source framework:** `Sports_Framework_v3.xlsx`
**Audit scope:** 21 sports/sub-formats across Sheet 5 (Phase Load Allocation)
**Source policy reference:** `Phase_Load_Allocation_Handoff.md` Q4

---

## Source tier reference (from handoff Q4)

- **Tier 1:** Peer-reviewed periodization studies, federation/governing-body coach education
- **Tier 2:** Established coach books (Friel, Daniels, Magness, Allen & Coggan, Pfitzinger), credentialed coach blogs
- **Tier 3:** Athlete training logs from credible competitors, reputable magazines — only with triangulation
- **Reject:** Uncredentialed blogs, AI-generated content

---

## Audit format per sport

Each entry records:
- **Sources consulted** (with tier)
- **Derivation reasoning** (why these allocations)
- **Departures from sport-group median** (where this sport diverges from family)
- **Open questions / changes recommended**

---

## Pre-audit findings (carried forward from setup)

### AR (worked example — re-validation deferred)
- Naïve sum 84–122 / 103–142 / 105–144 / 72–104
- Adjusted (paddle interchange + race-specific minors zeroed): 77–109 / 88–120 / 89–122 / 64–90
- **Real bug: Taper band cannot reach 100%** (high stack = 90)
- Conditional flag convention diverges from rest of sheet (R9, R14, R15 use `Primary*` / `Minor*` instead of canonical `(*Conditional)`)
- R7/R8 (Packrafting/Kayaking) interchangeable per notes but no conditional flag

### Group A pre-flight (Session 1)
- Marathon (Road, Trail, Ultra Road): Tight bands 93–107% all phases — typical for single-primary-discipline sport
- Marathon (Mountain), Ultra (Trail), Mountain Running, Fell Running: Wider bands 86–123% — multi-discipline
- **Fell Running has no Mobility / Recovery row** (structural gap vs. all other Group A sports)
- **Mountain Running Peak hi 123%** — widest band in Group A; check if intentional

---

## Group A — Running sports

### A.1 Marathon (Road) — VERIFIED with one open item

**Status:** Allocations and weekly hours verified against Tier-1 and Tier-2 sources. Phase load %s and hour bands fall within published norms for the sub-elite middle-volume marathoner (the implicit target user).

**Sources consulted:**
- *Tier 1:* Casado et al. (2022), "The Training Characteristics of World-Class Distance Runners" — PMC8975965 — elite marathoners run 160–220 km/wk mid-prep with ≥80% LIT, 11–14 sessions/wk
- *Tier 1:* Knaier et al. (2024), "Quantitative Analysis of 92 12-Week Sub-elite Marathon Training Plans" — PMC11065819 — analyzed 92 sub-elite plans across three volume tiers; final 12-week peak weekly volumes: low tier 43 km, middle tier 59 km, high tier 108 km
- *Tier 2:* Pfitzinger & Douglas, *Advanced Marathoning* — four plan tiers (peaks at 55, 70, 85, 100+ mi/wk); 3-phase structure (Endurance / Lactate Threshold + Endurance / Race Preparation); Chapter 4 supplementary training (strength tapering toward race)
- *Tier 2:* McMillan, "Guide to Strength Training Periodization" — periodizes strength as Stability → Strength → Power, recommending 2× 45–60 min during strength phase
- *Tier 2:* Efficient Endurance / "Periodization for Marathoners" — references taper meta-analysis recommending 40–60% mileage cut while maintaining ~80% run frequency

**Derivation reasoning:**

*Primary discipline (Road Running) at 80–94% across phases:* Marathon is functionally a single-discipline sport; the only reason this isn't 95–100% is that strength + mobility carve out time. Range stays high and stable across phases — no shifting proportions because there's nothing to shift toward. Verified against Pfitzinger plans (running ≈ all programmed time; supplementary work is brief and unscheduled in the daily grid).

*Weekly hours BASE 6–9 / BUILD 8–11 / PEAK 9–12 / TAPER 4–6 hrs (35–50 / 45–60 / 50–65 / 25–35 mi/wk):* Maps to the **sub-elite middle volume tier** in Knaier et al. (peak 59 km avg, range 65–90 km). Our 50–65 mi peak = 80–104 km, sitting at the upper end of middle tier into the lower band of high tier. Taper at 25–35 mi/wk = 40–55% of peak — fits the 40–60% meta-analysis taper recommendation. **Defensible default for a "serious recreational marathoner," not for elite or beginner.**

*Strength 10–12% Base → 3–5% Taper:* Tapering pattern is consistent with Pfitzinger (strength volume diminishes as race approaches). The Base value (10–12%) sits at the **low end** of what McMillan would prescribe (he recommends 2× 60 min/wk during strength phase, which on 7 hrs total weekly is ~17%). Acceptable because (a) McMillan's 60-min sessions are an outlier prescription, (b) Pfitzinger's plans imply less strength time, and (c) the band's high (12%) sits closer to the sport-family median.

*Mobility 3–5% Base → 6–8% Taper:* Standard "absolute-time-constant" pattern (~25–40 min stays roughly constant, % rises as volume drops). Consistent across endurance literature.

**Departures from sport-group median:** None. Marathon (Road) IS the canonical baseline against which Trail / Mountain / Ultra variants depart.

**Open questions / changes recommended:**
1. **Notes claim "Highest LIT ratio of the marathon family."** Knaier et al. found LIT proportions are roughly constant (~80% Z1+Z2) across all sub-elite volume tiers. Cross-check Marathon (Trail) and Marathon (Mountain) notes when those are audited — if any of them claim equal or higher LIT, the Road note is wrong (or trivially true for the wrong reason). **Action:** review the comparative LIT claim during A.2 / A.3 audit.
2. **Strength Base band low edge (10%) is conservative.** McMillan supports 12–15% base. If we want to broaden to match family median, expand to 10–14%. Low-priority — current band is defensible.
3. **No structural issues with sum-to-100 (93–107% all phases).**

### A.2 Marathon (Trail) — VERIFIED with two open items

**Status:** Allocations and weekly hours verified against Tier-1 epidemiological data and Tier-2 trail marathon coaching literature. The hour-band parity with Marathon (Road) is defensible given that trail running takes longer per mile; the mileage band is correctly lower (30–45 vs 35–50 mi/wk peak base).

**Sources consulted:**
- *Tier 1:* Vincent et al. (2022), "Injury Prevention, Safe Training Techniques, Rehabilitation, and Return to Sport in Trail Runners" — PubMed 35141547 — narrative review; ankle sprain is the most common acute injury, knee and ankle are top sites, >70% of trail running injuries are overuse
- *Tier 1:* Brink et al. (2021), South African trail runners cohort — PMC8656810 — overall RRI rate 19.6 per 1000 hrs; lower limb 82.9% (knee 29.8%, shin/lower leg 18.0%, foot/toes 13.7%)
- *Tier 1:* Knaier et al. (2024) — PMC11065819 — sub-elite marathon middle volume tier (peak ~59 km/wk avg); applies to time-equivalent volume
- *Tier 2:* Hart, "20-Week Trail Marathon Training Plan" (Relentless Forward Commotion) — credentialed ultra coach; recommends ~30% of weekly mileage on actual trail surface for less-experienced trail runners; 1–2 strength sessions per week
- *Tier 2:* McCormack, "16-Week Trail Marathon Training Plan" (inov8) — international athlete and coach; base of 30–40 mi/wk; 1–2 S&C sessions/week; long runs include race-specific climb percentages
- *Tier 2:* Avid Sports Med, "Trail Running Injuries" (Dec 2025) — emphasis on single-leg, lateral, balance, and core stability work; ankle proprioception specifically called out

**Derivation reasoning:**

*Trail Running (D-001) at 80–94% across phases:* Identical band shape to Marathon (Road)'s Road Running primary. Defensible because trail marathon is functionally single-discipline at the running-time level, with surface variability adding strength/proprioception demands that get met by the Strength row, not by displacing Trail Running time.

*Road Running (Cross-train) (*Conditional) at 0–10% Base, dropping to 0–6% Peak:* This row encodes Hart's 30/70 trail/road split for less-experienced trail runners and McCormack's flexibility for road substitution. The conditional flag is correct — this isn't additive volume, it's substitutable volume when trail access is unsafe (ice, deep mud) or when the athlete is using road for measurable threshold work. Notes already say `*CONDITIONAL — REPLACES portion of Trail Running volume, NOT additive.` Verified.

*Weekly hours BASE 6–9 / BUILD 8–12 / PEAK 9–13 / TAPER 5–7 hrs:* +1 hr at Build/Peak high vs Marathon (Road) and +1 hr both sides at Taper. This correctly captures that trail running takes ~10–20% longer per mile than road, so hour-equivalent training produces fewer miles. Trail mileage notes (30–45 mi/wk peak base + cross-train) match McCormack's 30–40 base recommendation.

*Strength 10–12% Base → 3–5% Taper:* Same band as Marathon (Road) with notes specifying "ankle stabilizer emphasis (single-leg balance progressions, calf raises)." Defensible. The trail-running injury epidemiology specifically supports ankle/lateral work, which is captured in the Strength row's content (not its allocation %).

*Mobility 3–5% Base → 6–8% Taper:* Identical to Marathon (Road). "Add ankle/foot mobility for technical terrain" per notes — same time budget, different content emphasis.

**Departures from sport-group median:** None significant. Marathon (Trail) is structurally a Marathon (Road) variant with surface-pace adjustment to weekly hours and trail-specific content within the Strength and Mobility rows.

**Cross-check on the LIT-ratio claim flagged in A.1:** Marathon (Road) notes claim "Highest LIT (low-intensity training) ratio of the marathon family." Marathon (Trail) notes do not make a counter-claim about LIT. **Marathon (Trail) is consistent on this dimension.** Need to check Marathon (Mountain) similarly.

**Open questions / changes recommended:**
1. **Vertical gain reference is missing.** Per handoff Q5, sports with variable vertical demand should have vertical gain in Notes column as reference (not full progression table). Marathon (Trail) is currently NOT in either Q5 list (full progression OR notes-only). Most trail marathons have meaningful vertical (typically 300–1500 m). McCormack's plan explicitly programs vertical as a percentage of race-day climb. **Recommended:** add a vertical-gain reference line to the Trail Running primary row, framed as percent-of-race-vertical (e.g., "long run accumulates 30–60% of race-day climb in build/peak"). This is a notes addition, not a band change.
2. **Strength dose math.** McCormack/Hart both recommend 1–2 S&C sessions/week. At 7 hrs/wk median, our 10–12% Base = 42–50 min total — closer to 1 session of 45 min than 2 sessions. The high-band (12%) supports 2 short sessions, the low-band (10%) supports only 1. This isn't a band defect, but the audit recommendation is to ensure strength session counts and durations are encoded somewhere downstream so the prescription doesn't collapse to "1 long session" when 2 short is what the literature recommends.
3. **Sum-to-100 OK** (93–107% all phases — same shape as Marathon (Road)).

### A.3 Marathon (Mountain) — VERIFIED with three open items

**Status:** Discipline split (Trail base / Uphill / Downhill) and weekly hour escalation over Marathon (Road) and (Trail) verified. Eccentric-strength emphasis in notes is well-supported by literature. Two structural questions worth flagging for cross-sport consistency, plus one borderline-overdosed downhill allocation.

**Sources consulted:**
- *Tier 1:* Bontemps et al. (2022), "The time course of different neuromuscular adaptations to short-term downhill running training" — PMC8927009 — 4 weeks of DR (10 sessions at 60–65% VO2max) increased knee-extensor MVT 9.7–15.2%; frames downhill as "low-intensity, high-volume eccentric exercise"
- *Tier 1 / 2:* Eston, Mickleborough & Baltzopoulos (2019) — referenced via Higher Running's Repeated Bout Effect summary; eccentric load on quadriceps during descent
- *Tier 1:* Douglas, Pearson, Ross & McGuigan (2017) — eccentric strength training reduces muscle damage in subsequent exposures
- *Tier 2:* Higher Running, "The Repeated Bout Effect & Eccentric Loading" — recommends downhill sessions every 2–2.5 weeks during the final 6 weeks; 1–2 dedicated downhill sessions in a peak block may be sufficient
- *Tier 2:* Trail Runner Magazine, "Strength Train For Better Downhill Running" — downhill-focused workouts spaced ~4 weeks apart for repeated bout adaptation without injury risk
- *Tier 2:* CTS / TrainRight, "Eccentric Strength Training Exercises for Improved Downhill Running" — gym-based eccentric prescriptions when terrain is unavailable; aerobic fitness remains highest priority over specificity
- *Tier 2:* Mountain Tactical Institute, "Mountain Marathon Training Plan" — credentialed mountain athletic prep; separate uphill (step-ups, concentric leg) and downhill (leg blaster complex, eccentric) systems
- *Tier 2:* Evoke Endurance, "Training for Mountain Running" — power hiking transition guidance; "as the grade steepens, at some point it becomes more efficient to walk"

**Derivation reasoning:**

*Trail Running base (D-001) at 55–65% Base, dropping to 47–57% Peak:* Standard periodization-shift pattern — general-trail volume reduces as specialized uphill/downhill volume rises in build/peak. Defensible.

*Uphill Mountain Running (D-022) at 12–18% Base → 17–23% Build → 18–26% Peak → 15–21% Taper:* Build/Peak escalation is correct for mountain marathon prep. The Peak high (26%) at a 13–15 hr peak week = ~3.5–3.9 hrs/wk dedicated uphill. That's roughly 2–3 sustained-grade ascent sessions per week, which matches MTI and Evoke Endurance protocols. Verified.

*Downhill Mountain Running (D-023) at 8–12% Base → 9–15% Build → 12–18% Peak → 8–14% Taper:* This is the borderline call. Bontemps et al. used 10 sessions over 4 weeks (2.5 sessions/wk) at 60–65% VO2max for eccentric adaptation — but as research subjects, not athletes layering on other volume. Higher Running and Trail Runner Mag both recommend big downhill sessions every 2–4 weeks in peak block (so 1–2 per month, not 2–3 per week). Our Peak high at 18% × 13 hr = 2.3 hrs/wk dedicated downhill — likely 2–3 sessions/wk if those are 45–60 min downhill-emphasis runs. **High-band may be overdosed.** Low-band (12% × 10 hr = 1.2 hrs/wk) = roughly one weekly downhill session, which fits the literature better. See open item #1.

*Strength 10–12% Base → 3–5% Taper:* Identical band to Marathon (Trail). Notes specify "heavier eccentric quad emphasis (slow eccentric squats, step-down progress[ions])." Per Bontemps and Douglas, eccentric strength work meaningfully reduces muscle damage in subsequent eccentric bouts — the prescription content is validated. The band % matches family median.

*Mobility 3–5% Base → 6–8% Taper:* Identical to Marathon (Road) and (Trail). See open item #2 — likely underdosed for the eccentric-load recovery profile of mountain marathon.

*Weekly hours BASE 7–10 / BUILD 9–13 / PEAK 10–15 / TAPER 5–7 hrs:* +1–2 hrs over Marathon (Trail) at every phase except Taper. Defensible — mountain trail running is even slower per mile (steep grades + technical) so hour-equivalent training is less mileage. MTI plans typically run 8–12 hrs/wk, our 10–15 Peak is on the higher end of credible range.

*Vertical gain reference 800–1500 m/wk Build, 1500–2500 m/wk Peak:* In notes column, not in a separate progression table. Per handoff Q5 this is the correct treatment. Values are consistent with mountain marathon races having 1500–3000 m total ascent — peak weekly vertical equals ~1× race vertical, which matches the same logic that peak weekly run mileage equals ~1× race distance for road marathoners.

**Departures from sport-group median:**

1. *Strength % is family-median* (10–12% Base) but Mountain Running / Skyrunning is 12–15% Base. Marathon (Mountain) sits 2–3% lower than Mountain Running. Defensible if the longer-duration nature of marathon-distance racing reduces neuromuscular peak demands relative to skyrunning, but worth surfacing as a question for the Mountain Running audit (A.6) — once both are looked at side-by-side, decide whether Mountain Running is high or Marathon (Mountain) is low.

2. *Mobility band is family-baseline* but Mountain Running / Skyrunning Base mobility is 5–8% (vs our 3–5%). Mountain Running's notes specifically cite quad mobility for eccentric DOMS recovery — that demand exists for Marathon (Mountain) too. See open item #2.

**Cross-check on the LIT-ratio claim flagged in A.1:** Marathon (Mountain) notes don't claim a higher or comparable LIT ratio. The mountain variant's mid-cycle uphill/downhill specificity work is intentionally higher-intensity than Road (LT and VO2 work translates to climbing repeats and tempo-on-trail). **Marathon (Road)'s "highest LIT ratio" claim looks defensible relative to Mountain.** Still need to check Mountain Running and Fell Running which have similar profiles.

**Open questions / changes recommended:**
1. **Downhill Peak high-band (18%) may be overdosed.** Literature recommends 1–2 dedicated downhill workouts per peak block month, with eccentric strength work supplementing. Our 18% high implies 2.3+ hrs/wk dedicated downhill — feasible but at the edge of injury risk per Trail Runner Mag's "spacing 4 weeks apart" guidance. **Recommended:** narrow Peak high from 18% to 15–16%. Low-band (12%) is well-supported.
2. **Mobility may be underdosed relative to eccentric load.** The 3–5% Base / 4–6% Build & Peak band matches Marathon (Road)/(Trail), but Mountain Running's 5–8% Base directly addresses the eccentric DOMS recovery demand that also applies here. **Recommended:** consider raising Marathon (Mountain) mobility Base to 4–7% to acknowledge the additional recovery demand without forcing parity with Mountain Running. Decide alongside Mountain Running audit (A.6).
3. **Strength % vs Mountain Running discrepancy.** 10–12% (us) vs 12–15% (Mountain Running). Worth resolving as a family-coherence question during Mountain Running audit; tentatively defensible because marathon distance is longer/lower-intensity than skyrace, reducing neuromuscular peak demand.
4. **Sum-to-100 OK** (86–114% all phases — wider band than Road/Trail variants because three primary running disciplines participate, but feasibility intact).

### A.4 Ultramarathon (Road)

[Pending verification]

### A.5 Ultramarathon (Trail)

[Pending verification]

### A.6 Mountain Running / Skyrunning

[Pending verification]

### A.7 Fell Running

[Pending verification]

---

## Group B — Triathlon family

[Session 2]

## Group C — Water sports

[Session 3]

## Group D — Snow + skill-hybrid

[Session 4]

## Group E — Cycling + cleanup

[Session 5]
