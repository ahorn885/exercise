# Evidence-based cardio-drill additions — EX290–292 (PROPOSED, awaiting ratification)

**Date:** 2026-06-19 · **Track 2 / #698 follow-on.** Companion to the held 47-row Technical/Skill cull (`0017`) and the full-catalog audit (`TechnicalSkill_FullCatalog_Audit_55rows_2026_06_19.md`).

**Why:** the 47-cull leaves a transition-heavy skill set; the everyday-applicable pool is the 13 cardio drills (`Interval/Tempo` + `Aerobic/Endurance`). Andy asked to examine evidence-based additions "of these natures." Gap analysis (intensity × modality) surfaced three genuine, non-duplicate gaps. These would ship as `etl/migrations/layer0/0018_*.sql` **after** ratification, sequenced with the held cull so the reshaped catalog lands coherently.

## Provenance & evidence-quality caveat

Researched via a 5-angle deep-research fan-out (VO2 run intervals · hill-vs-flat stimulus · swim CSS · bike over-unders · interval programming/intensity-distribution). **WebFetch was HTTP-403 blocked on every academic host**, so all figures are WebSearch extracts of the cited primaries, not full-text reads — convergence across independent sources carries confidence, but **exact numerics must be re-verified against the primary PDFs before they are treated as published fact.** Citations below are to verifiable author/title/journal + URL.

| Drill | Distinct-stimulus case | Evidence tier |
|---|---|---|
| EX290 Flat VO2max Run Intervals | Pure aerobic-power at racing velocity; Hill Repeats loads posterior-chain strength-endurance at lower velocity/impact | **Strong — RCT/crossover-backed** |
| EX291 Swim CSS / Threshold Intervals | First structured swim *fitness* set; Pull/Kick are aerobic-technique only | **Good — validated concept (study), prescription consensus** |
| EX292 Bike Over-Under Intervals | Variable-power threshold trains lactate clearance/buffering; steady Threshold/Sweet-Spot don't | **Weakest — textbook mechanism + practitioner consensus, NO RCT isolating it** |

---

## EX290 — Flat VO2max Run Intervals

| Field | Value |
|---|---|
| exercise_type | `Interval / Tempo` |
| movement_patterns | `{Locomotion}` |
| primary_muscles | `{"Aerobic System", Glutes, Hamstrings, "Hip Flexors"}` |
| secondary_muscles | `{Calves, Core, "Tibialis Anterior"}` |
| equipment_required | `{Treadmill}` |
| terrain_required | `{Road, "Flat Trail"}` (400 m track is the canonical venue — noted in cue; no `Track` terrain token exists, not padding the vocab) |
| injury_flags_text | `Hamstring — terminal-swing eccentric strain at vVO2max velocity; Achilles — high impact/loading rate vs hill reps; IT Band — if gait breaks down under fatigue` |
| contraindicated_parts | `{Hamstring, Achilles, "IT Band"}` |
| regression | EX178 Tempo Run (Flat / Road) — *sub-threshold before max aerobic power* |
| progression | *(none — top of the run aerobic-power ladder)* |
| physical_proxies | EX048 Hill Repeats · EX074 VO2 Max Intervals (Bike) |

**Coaching cue (the dose):** *3–5 min reps at ~95–100% vVO2max (≈ current 3K–5K race pace; HRmax only reached late in each rep); jog recovery ≈ the work bout (~1:1); 4–6 reps. Cap total quality volume at the lesser of 10 km or 8% of weekly mileage. Use 3–5 min reps, not 30-30s — long reps bank more true time at VO2max. 1×/week, ≥48 h from the next hard session. This is the flat aerobic-power complement to Hill Repeats, which loads strength-endurance at lower impact.*

**Evidence:** vVO2max integrates aerobic power + economy and predicts distance performance (Billat & Koralsztein, *Sports Med* 1996, [PMID 8775363](https://pubmed.ncbi.nlm.nih.gov/8775363/)). Intermittent vVO2max work ~tripled time-at-VO2max vs continuous (Billat et al., *Eur J Appl Physiol* 2000, [PMID 10638376](https://pubmed.ncbi.nlm.nih.gov/10638376/)). I-pace = 95–100% VO2max, 3–5 min reps, ≤10 km or 8% weekly cap (Daniels, *Running Formula*). A 2025 crossover (n=12) found **4×3 min @95% vVO2max accumulates more time >90% VO2max than 24×30 s** ([PMID 39835194](https://pubmed.ncbi.nlm.nih.gov/39835194/)) — basis for the long-rep prescription. Overtraining guardrail: 3 vVO2max sessions/wk for 4 wk raised stress markers with no performance gain (Billat et al., *MSSE* 1999, [PMID 9927024](https://pubmed.ncbi.nlm.nih.gov/9927024/)).

**Proposed sport_exercise_map:** Marathon (Critical) · Mountain Running / Sky Running (High) · Fell Running (High) · Trail Running (High) · Orienteering (High) · Obstacle Course Racing (High) · Multi-Sport Race (High) · Run-Bike-Run Duathlon (High) · Triathlon (High) · Long Distance Orienteering (Medium) · Ultramarathon (Medium) · SwimRun (Medium).

---

## EX291 — Swim CSS / Threshold Intervals

| Field | Value |
|---|---|
| exercise_type | `Interval / Tempo` |
| movement_patterns | `{Pull-H, Rotation}` |
| primary_muscles | `{"Aerobic System", "Latissimus Dorsi", Triceps, "Anterior Deltoid"}` |
| secondary_muscles | `{Core, Obliques, "Rotator Cuff"}` |
| equipment_required | `{}` (optional Finis Tempo Trainer Pro — in cue, no token added) |
| terrain_required | `{Pool}` (open-water adaptation in cue) |
| injury_flags_text | `Shoulder — subacromial impingement / rotator-cuff overuse with high-volume short-rest threshold sets; Wrist — entry stress` |
| contraindicated_parts | `{Shoulder, Wrist}` |
| regression | EX126 Freestyle Pull (With Buoy) — *aerobic-technique base before threshold* |
| progression | *(none — top swim fitness set)* |
| physical_proxies | EX090 Paddling Ergometer Session |

**Coaching cue (the dose):** *Set CSS first: best 400 m + best 200 m TT same session (full recovery). CSS pace per 100 m = (t400 − t200) ÷ 2; retest every 4–6 wk. Threshold set: 100–400 m reps at/just above CSS (CSS to CSS−1–2 s/100 m), short rest 10–20 s; ~800–2000 m threshold volume (e.g. 8–10×100, 5×200, 3×400); 1–2×/week. CSS slightly overestimates true MLSS, so literal-CSS pace sits a hair above threshold — intended. Open-water/swimrun: add ~2–5 s/100 m for no wall push-offs + sighting (wetsuit offsets some).*

**Evidence:** CSS = (400−200)/(t400−t200); validated as a swimming-performance index and ≈MLSS in the origin work (Wakayoshi et al., *Eur J Appl Physiol* 1992 [PMID 1555562](https://pubmed.ncbi.nlm.nih.gov/1555562/); 1993 [PMID 8425518](https://pubmed.ncbi.nlm.nih.gov/8425518/)). **Key caveat:** CSS *overestimates* directly-measured MLSS by a few % — not interchangeable (Dekerle et al., *Int J Sports Med* 2005, [PMID 16195984](https://pubmed.ncbi.nlm.nih.gov/16195984/)); modern consensus = "robust proxy, slight overestimate." Contraindication: shoulder-pain prevalence rises with swim volume (Swimmer's Shoulder, StatPearls [NBK470589](https://www.ncbi.nlm.nih.gov/books/NBK470589/); volume–pain review [PMC6961642](https://pmc.ncbi.nlm.nih.gov/articles/PMC6961642/)). Prescription set structure is practitioner-consensus (Swim Smooth / TrainingPeaks / USMS).

**Proposed sport_exercise_map:** Swimming (Critical) · Triathlon (Critical) · SwimRun (Critical).

---

## EX292 — Bike Over-Under Intervals

| Field | Value |
|---|---|
| exercise_type | `Interval / Tempo` |
| movement_patterns | `{Locomotion}` |
| primary_muscles | `{"Aerobic System", Quads, Glutes}` |
| secondary_muscles | `{Core, "Hip Flexors"}` |
| equipment_required | `{"Cycling trainer"}` |
| terrain_required | `{}` |
| injury_flags_text | `Knee — patellofemoral stress at supra-FTP power; Hip Flexor — fatigue at/above threshold` |
| contraindicated_parts | `{Knee, "Hip Flexor"}` |
| contraindicated_conditions | *(none — but cue gates to build phase / sweet-spot durability first)* |
| regression | EX073 Threshold Intervals (Bike) — *steady threshold before variable-power* |
| progression | EX074 VO2 Max Intervals (Bike) |
| physical_proxies | EX178 Tempo Run (Flat / Road) |

**Coaching cue (the dose):** *Variable-power threshold rep: alternate "under" 90–95% FTP for 2–4 min with "over" 105–110% FTP for 1–2 min; 3+ cycles per rep; 2–3 reps of 10–20 min; ~2:1 work:rest between reps (~8–10 min easy). 1×/week, late-base/build only — establish 2×20 sweet-spot durability first. Trains lactate clearance/buffering at race intensity (produce on the over, clear on the under) — distinct from steady threshold/sweet-spot. Don't make the over too long/hard or the under too short to clear.*

**Evidence:** Mechanism is textbook — lactate shuttle (Brooks, *Cell Metab* 2018) + training-induced MCT1/MCT4 lactate-transporter upregulation and faster clearance (Benítez-Muñoz et al., *Acta Physiol* 2024, [doi 10.1111/apha.14083](https://onlinelibrary.wiley.com/doi/10.1111/apha.14083); Dubouchaud et al., *Am J Physiol* 2000, [PMID 10751188](https://pubmed.ncbi.nlm.nih.gov/10751188/)) — but these use general endurance/HIIT, **not over-unders**. Prescription converges across TrainerRoad / FasCat / INSCYD / EVOQ / TrainingPeaks. **No RCT isolates over-unders**; the strongest nearby RCT (Stöggl & Sperlich, *Front Physiol* 2014, [PMC3912323](https://pmc.ncbi.nlm.nih.gov/articles/PMC3912323/)) is about intensity *distribution* and cautions that threshold-zone emphasis underperforms polarized training in trained athletes. **Lowest evidence tier of the three.**

**Proposed sport_exercise_map:** Road Cycling (Critical) · Gravel Cycling (Critical) · Triathlon (High) · Run-Bike-Run Duathlon (High) · Mountain Biking (High) · XC / AR Cycling (High) · Bikepacking (Medium) · Multi-Sport Race (Medium).

---

## Coverage effect & open ratification points

- **Partial refill of the cull's coverage cliff:** EX290 restores a cardio prescription to several disciplines the 47-cull zeroed for `Technical/Skill` (Fell/Trail Running, Marathon, Orienteering); EX291 does the same for Swimming/SwimRun. Paddle/climb/snow remain thin (already carry their own A/E session).
- **Pool fit:** all three are `Interval/Tempo`, so they enter the Part A `cardio_drills` pool as everyday-applicable (non-transition) options.

**Ratify:** (1) which of the three to add; (2) EX292 specifically — does the consensus-grade (non-RCT) evidence clear your bar; (3) any field edits — names, the proposed sport/priority maps, progression/regression targets. On ratification these + the held cull are written as `0017` (cull) + `0018` (adds), validated via the local-PG gate recipe + CI `layer0-gate`, applied via the gated `layer0-apply` Action.
