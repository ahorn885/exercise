# Bridge Bands Research v1

**Date:** 2026-06-07
**Author:** Claude (research agent) + Andy (directive)
**Status:** DRAFT — research substrate for X1a (bridge rewrite). Pending Andy review before Excel patch.
**Companion specs:** `Modality_Group_Spec_v1.md` (X1b — discipline-modality groups)
**Source data audited:** `etl/sources/Sports_Framework_v11.xlsx` Sheet 3 (Sport × Discipline Map) — 21 framework_sports

## Why this exists

The current `layer0.sport_discipline_bridge` `race_time_pct_low/high` bands (drafted from rough estimates during initial ETL) are wrong for several sports. Most acutely:

- **Adventure Racing** says Trail Running 15-25% and Mountain Biking 10-20% — inverted from reality. MTB dominates expedition AR.
- **Off-Road / Adventure Multisport (XTERRA)** has bands not matching the XTERRA-published 10/65/25 swim/bike/run formula.

This dataset rewrites all 21 sports' `race_time_pct` bands using authoritative governing-body sources first, peer-reviewed sport science second.

---

## Per-sport bands

### 1. Adventure Racing
- **Typical format assumed:** 24-48h+ expedition AR (ARWS / USARA Nationals / Eco-Challenge-style), MTB-dominated with significant trekking and paddling.
- **Citations:**
  1. ARWS — https://arworldseries.com/world-championship/about-arwc — Sport's de facto international peak body; lists trek/run, mountain bike, packrafting/kayak as core disciplines and confirms expedition-format dominance.
  2. Wikipedia — Adventure Racing — https://en.wikipedia.org/wiki/Adventure_racing — Aggregates published course breakdowns across major expedition events; confirms trekking, MTB, paddling as principal disciplines, with bike legs typically the longest single-discipline block.
  3. Warrior Racing / Sea-to-Sea — https://www.warriorraces.com/sea-to-sea — Published 60% bike / 20% paddle / 20% trek course distance distribution for a representative US expedition AR.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Mountain Biking | 35 | 55 | Bike legs are the longest distance block in nearly every expedition course; Sea-to-Sea published 60% of distance on bike → ~35-55% of time once sleep and trek slow-down accounted for. Current bridge band of 10-20% is materially wrong. |
| Trekking / Trail Running | 25 | 45 | Trek legs are slower per km than MTB/paddle, so they consume a larger share of time than of distance. ARWS courses consistently allocate 1-3 major trek legs of 20-50km each over 24-48h+. Current 15-25% too low. |
| Paddling (Kayak/Canoe/Packraft) | 10 | 25 | Paddle legs typical 20-50km on flatwater/whitewater; 1-2 legs per course. Time share intermediate. |
| Navigation / Other (rope, transitions) | 0 | 10 | Navigation folded into moving disciplines; rope sections and transitions small but non-zero. |

### 2. Aquabike
- **Typical format assumed:** Olympic-distance aquabike (1.5km swim + 40km bike, no run); World-Triathlon-sanctioned standard.
- **Citations:**
  1. World Triathlon / Aquabike.world — https://www.aquabike.world/categories/aquabike-short-distance/ — Defines standard-distance aquabike.
  2. USA Triathlon — https://www.usatriathlon.org/about/multisport/disciplines/aquabike — National governing body confirming format.
  3. Inferred from Olympic-distance triathlon elite splits (Tri247 / T100): 25min swim, 60min bike → without the run leg, swim ~29% and bike ~71%.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Open Water Swimming | 25 | 35 | Elite ~25min swim / ~60min bike = 29% swim; age-group swim share rises as bike speed falls more than swim speed. |
| Road Cycling | 65 | 75 | Complementary; ~71% elite, slightly lower for slower fields. |

### 3. Aquathlon
- **Typical format assumed:** World Triathlon standard format, 1km swim + 5km run (continuous or swim-run-swim variants).
- **Citations:**
  1. World Triathlon — https://triathlon.org/multisports/aquathlon — Governing body, standard distances.
  2. USA Triathlon — https://www.usatriathlon.org/about/multisport/disciplines/aquathlon — National federation confirming formats.
  3. 2014 ITU Aquathlon WCh elite men results — https://www.triathlon.org/results/result/2014_edmonton_itu_aquathlon_world_championships/265278 — Empirical split source.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Open Water Swimming | 35 | 50 | Elite 1km swim ~11-12 min vs. 5km run ~15-17 min → swim ~42%. Widens for slower swimmers. |
| Trail/Road Running | 50 | 65 | Complementary; run dominates by small margin for elites, larger margin for age-groupers. |

### 4. Biathlon
- **Typical format assumed:** IBU Sprint (10km M / 7.5km W) or Individual (20km M / 15km W); skiing is the dominant time component.
- **Citations:**
  1. IBU — https://www.biathlonworld.com/inside-ibu/sports-and-event/biathlon-sprint — Sprint format spec.
  2. IBU — https://www.biathlonworld.com/inside-ibu/sports-and-event/biathlon-individual — Individual format spec.
  3. Frontiers in Sports — "Determinants of Performance in Biathlon World Cup Sprint and Individual Competitions" — https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2022.841619/full — Peer-reviewed analysis; skiing speed dominates final time.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Cross-Country Skiing | 80 | 92 | Sprint ~25 min total; ski loops 3×3.3km dominate. Range time per bout ~30-45s × 2 = ~1-2min total → skiing 85-90% of pure activity. Penalty loops (150m) add ~30s each. |
| Shooting (range time + penalty loops) | 8 | 20 | Combined range time (~1-2 min) + penalty loops (0-5 misses × ~30s) → 8-20% depending on accuracy. |

### 5. Canoe/Kayak Marathon
- **Typical format assumed:** ICF Canoe Marathon WCh distance (~22-30km), 6-8 laps with up to 7 portages of several hundred meters each.
- **Citations:**
  1. ICF Canoe Marathon Competition Rules 2025 — https://www.canoeicf.com/sites/default/files/2025_icf_competition_rules_marathon_final.pdf — Governing body rulebook.
  2. ICF Canoe Marathon discipline page — https://www.canoeicf.com/disciplines/canoe-marathon — Confirms portage structure.
  3. Wikipedia (Canoe marathon) — https://en.wikipedia.org/wiki/Canoe_marathon — Aggregates course design facts.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Paddling (Flatwater Canoe/Kayak) | 88 | 96 | Race is overwhelmingly paddling; portages are seconds to ~1-2 minutes each, repeated 6-7 times in a ~1.5-2.5h race → portages ~5-10% of time. |
| Running (Portages) | 4 | 12 | 6-8 portages of several hundred meters each, run with boat in hand. |

### 6. Cross-Country / Nordic Skiing
- **Typical format assumed:** FIS distance race (10/20/50km individual or mass-start, single technique — classic OR freestyle, NOT skiathlon).
- **Citations:**
  1. FIS Live Results — https://www.fis-ski.com/DB/cross-country/live.html — International governing body.
  2. NBC Olympics XC format — https://www.nbcolympics.com/news/cross-country-skiing-101-competition-format — Confirms distances and technique rules.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Cross-Country Skiing | 98 | 100 | Mono-discipline. Only "non-ski" time is start-zone setup; effectively 100%. |

### 7. Duathlon
- **Typical format assumed:** World Triathlon Standard (10km run + 40km bike + 5km run).
- **Citations:**
  1. World Triathlon — https://triathlon.org/multisports/duathlon — Standard-distance definition.
  2. Powerman / MyProCoach pacing guide — https://support.myprocoach.net/hc/en-us/articles/360022542851-Pacing-Your-Standard-Duathlon-10-40-5 — Standard splits source.
  3. World Triathlon Long Distance Duathlon WCh (Zofingen) results — https://triathlon.org/results/result/2023_world_triathlon_powerman_long_distance_duathlon_championships_zofingen/586479 — Empirical long-distance split.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Road/Trail Running (Run 1 + Run 2) | 40 | 55 | Standard: ~35 min run1 + ~20 min run2 = ~55min running vs. ~60-65min bike → ~45-50% run for elites; rises slightly for age-groupers. |
| Road Cycling | 45 | 60 | ~60-65min bike for elites vs. ~120min total race → ~50% bike; lower for stronger cyclists who push longer. |

### 8. Fell Running
- **Typical format assumed:** FRA short/medium category fell race (Cat AS/AM/BS/BM: 5-20km with significant ascent, 30min-2.5h duration).
- **Citations:**
  1. FRA Race Categories — https://runtimes.co.uk/an-explanation-of-the-fra-race-classification-system-and-other-abbreviations/ — Official FRA categorisation.
  2. Fellrunner.org.uk FAQ — https://www.fellrunner.org.uk/faq/frequently-asked-questions — UK fell running peak association.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Trail / Off-Road Running (including hike-up on steeps) | 98 | 100 | Mono-discipline; nav element folded into running time. |

### 9. Long Distance / Endurance Cycling
- **Typical format assumed:** Gran fondo / century event (~100mi / 160km road), 4-7h duration.
- **Citations:**
  1. Wikipedia — Gran Fondo — https://en.wikipedia.org/wiki/Gran_Fondo — Format definition.
  2. Gran Fondo Guide — https://www.granfondoguide.com/Contents/Index/931/what-is-a-century-ride — Format and duration norms.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Road Cycling | 98 | 100 | Mono-discipline; aid-station stops minimal for the band. |

### 10. Marathon (Mountain)
- **Typical format assumed:** OMM-style 2-day team navigation event with running/trekking over rough mountain terrain; ~30-60km/day with substantial ascent.
- **Citations:**
  1. OMM — https://theomm.com/the-omm/ — Sport's flagship event; defines format.
  2. Mountain Marathon — Wikipedia — https://en.wikipedia.org/wiki/Mountain_marathon — Codifies team / navigation / self-sufficient format.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Trail / Mountain Running (incl. hiking up steeps) | 95 | 100 | Mono-discipline in moving sense; navigation time folded into running/hiking. No paddle/bike legs. |

### 11. Marathon (Road)
- **Typical format assumed:** World Athletics-sanctioned 42.195km road marathon (mono-discipline).
- **Citations:**
  1. World Athletics — https://worldathletics.org/disciplines/road-running/marathon — International governing body.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Road Running | 98 | 100 | Mono-discipline. |

### 12. Marathon (Trail)
- **Typical format assumed:** 42.2km trail-surface marathon (mono-discipline, modest elevation vs. mountain marathon).
- **Citations:**
  1. ITRA — https://itra.run/ — De facto international governing body for trail running.
  2. World Athletics Mountain & Trail Running — https://worldathletics.org/disciplines/trail-running — Confirms trail marathon as a discipline.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Trail Running | 98 | 100 | Mono-discipline. |

### 13. Modern Pentathlon
- **Typical format assumed:** UIPM 2024-onwards format compressed to ~2 hours: fencing, swimming, riding (transitioning to obstacle course post-2024), and laser-run combined event.
- **Citations:**
  1. UIPM Competition Rules 2025 — https://www.uipmworld.org/sites/default/files/mp_competition_rules_and_equipment_regulations_2025_clean_final.pdf — Official rulebook.
  2. Pentathlon GB — https://www.pentathlongb.org/important-update-uipm-competition-format-changes-and-2026-uipm-calendar-confirmation/ — National federation update on format.
  3. Olympics.com Modern Pentathlon — https://www.olympics.com/en/news/whats-new-paris-2024-modern-pentathlon-competition-format — Format duration breakdown.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Fencing | 20 | 30 | Round-robin epee bouts dominate fencing block; ~15-20 min of competition time in a ~60-90min active envelope. |
| Swimming (200m freestyle) | 5 | 10 | One ~2:00-2:30 swim within the active block. |
| Riding / Obstacle (post-2024 replacement) | 20 | 30 | 20-minute equestrian block in 2024 spec; obstacle course replacement scheduled similar duration in LA28. |
| Laser-Run (combined run + pistol) | 30 | 45 | 3.2km run + 4 shooting stops, ~12-15min for elites. Largest single block in active-time terms. |

### 14. Mountain Running / Skyrunning
- **Typical format assumed:** ISF SkyRace (20-49km, ≥1200m vert, sub-3h winning time).
- **Citations:**
  1. ISF Rules — https://www.skyrunning.com/rules/ — International Skyrunning Federation rulebook.
  2. World Mountain Running Association — https://www.wmra.ch/ — Parallel governing body for classic mountain running races.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Trail / Mountain Running (incl. hands-on-knees hiking on steeps) | 95 | 100 | Mono-discipline; some races (VK / Sky-Extreme) include short technical/scramble sections but no paddle/bike. |

### 15. Off-Road / Adventure Multisport (Non-Nav)
- **Typical format assumed:** XTERRA off-road triathlon (1.5km open-water swim + ~30km MTB + ~10km trail run).
- **Citations:**
  1. XTERRA — https://www.xterraplanet.com/off-road-triathlon — Sport's flagship circuit; publishes the formula.
  2. Triathlete — https://www.triathlete.com/training/everything-you-need-to-know-about-xterra-and-off-road-triathlon/ — Confirms XTERRA published formula.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Open Water Swimming | 8 | 15 | XTERRA's published formula: 10% swim. Adds slight upward elasticity for slower fields. |
| Mountain Biking | 55 | 70 | XTERRA published formula: 65% MTB. Single largest block. |
| Trail Running | 20 | 30 | XTERRA published formula: 25% trail run. |

### 16. Open Water Marathon Swimming
- **Typical format assumed:** FINA/World Aquatics 10km open water marathon (mono-discipline; Olympic event).
- **Citations:**
  1. World Aquatics (FINA) — https://www.worldaquatics.com/swimming/open-water — International governing body.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Open Water Swimming | 98 | 100 | Mono-discipline; in-water feeding stops are seconds-long and not separately codified. |

### 17. Skimo
- **Typical format assumed:** ISMF Individual race (~1500-1600m vert, 3 ascents/3 descents, ~1h30 winning time, at least one bootpack section).
- **Citations:**
  1. ISMF — https://www.ismf-ski.org/ — International Ski Mountaineering Federation.
  2. USA Skimo formats — https://www.usaskimo.org/ski-mountaineering-racing-formats/ — National federation summarising ISMF spec.
  3. NBC Olympics Skimo 101 — https://www.nbcolympics.com/news/ski-mountaineering-101-rules — Confirms course parameters for Milan-Cortina 2026.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Skinning / Uphill (Ski Touring) | 55 | 70 | Ascents (skinning + bootpack) consume dominant share; uphill is slower than downhill on equivalent vert. Bootpack is part of this band. |
| Downhill Skiing | 20 | 35 | Descents fast (~3-5 min each × 3) in ~90min race → ~15-25%; band extended upward for less-vert events. |
| Transitions (skins on/off, bootpack switch) | 3 | 10 | Elite transitions ~15-45s each, ~6-8 per race → ~2-5 min total; ~3-6% World Cup, higher for amateurs. |

### 18. Swimrun
- **Typical format assumed:** ÖTILLÖ World Championship format (~75km total: ~10km open-water swimming + ~65km trail running, broken into 20+ alternating segments).
- **Citations:**
  1. ÖTILLÖ Swimrun (sport's founding event / de facto governing body) — https://otilloswimrun.com/races/otillo-swimrun-world-championship-sweden/ — Authoritative format definition.
  2. Wikipedia — Swimrun — https://en.wikipedia.org/wiki/Swimrun — Aggregates published distance/time breakdowns.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Open Water Swimming (in shoes/wetsuit) | 12 | 22 | ÖTILLÖ published: 12.8% of race is swimming for fast teams; rises to ~20% for slower teams as swim pace flattens vs. run pace. |
| Trail Running (in wetsuit/wet shoes) | 78 | 88 | Complementary; ~87% for fast teams. |

### 19. Triathlon
- **Typical format assumed:** Olympic-distance (1.5km/40km/10km), World Triathlon WTCS / draft-legal elite norms.
- **Citations:**
  1. World Triathlon (ITU) — https://triathlon.org/ — International governing body.
  2. Tri247 elite Olympic splits analysis — https://www.tri247.com/triathlon-news/elite/olympic-games-triathlon-paris-2024-triathletes-average-pace-swim-bike-run — Empirical elite splits.
  3. Frontiers — "Cycling is the most important predictive split discipline in professional Ironman 70.3 triathletes" — https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2024.1214929/full — Peer-reviewed long-distance split.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Open Water Swimming | 15 | 22 | Elite ~25min swim of ~120min race = ~21%; lower share for fast swimmers. |
| Road Cycling | 45 | 55 | Elite ~60min of ~120min = ~50%. Stable across athlete levels at Olympic distance. |
| Road Running | 25 | 35 | Elite ~35min of ~120min = ~29%. |

**Ironman / long-distance triathlon callout bands** (if data permits separate row):
- Swim 8-12% / Bike 50-55% / Run 30-40%. Sources: Blummenfelt 7:21 record splits (39:41 / 4:02:40 / 2:35:24 → 9% / 55% / 35%); average IM splits at age-group level (1:19 / 6:19 / 4:50 → 11% / 50% / 39%).

### 20. Ultramarathon (Road)
- **Typical format assumed:** IAU 100km road ultra (mono-discipline; flagship IAU distance).
- **Citations:**
  1. IAU (International Association of Ultrarunners) — https://iau-ultramarathon.org/ — World Athletics-recognized IGB for ultra.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Road Running | 95 | 100 | Mono-discipline; aid-station stops a few % of total at most. |

### 21. Ultramarathon (Trail)
- **Typical format assumed:** UTMB-style 100-mile mountain ultra (~170km, ~10,000m vert, ~20-46h finish time).
- **Citations:**
  1. UTMB / ITRA — https://itra.run/ — De facto IGB for trail ultra; UTMB course profile in https://utmbmontblanc.com/.
  2. iRunFar 2024 UTMB results / Marathon Handbook UTMB 2025 analysis — https://www.irunfar.com/2024-utmb-results , https://marathonhandbook.com/inside-the-data-of-tom-evans-stunning-utmb-2025-victory/ — Authoritative elite split data.

| Discipline | Low | High | Justification |
|---|---|---|---|
| Trail Running (incl. power-hiking up steeps) | 95 | 100 | Mono-discipline. Damian Hall published estimate: ~40% of UTMB finish-time is hiking, ~60% running — both fall under the single "Trail Running" discipline in this bridge schema. |

---

## Summary of changes vs. current bridge

### Sports where bands changed materially from current dubious estimates

- **Adventure Racing** — **biggest change.** Current bridge (Trail Running 15-25%, MTB 10-20%) inverts reality. New bands: **MTB 35-55%**, Trekking 25-45%, Paddling 10-25%. MTB is the dominant time consumer in expedition AR.
- **Off-Road Triathlon (XTERRA)** — XTERRA publishes the 10/65/25 formula explicitly; current bridge bands shift to match (Swim 8-15%, **MTB 55-70%**, Run 20-30%).
- **Swimrun** — ÖTILLÖ publishes 12.8% swim / 87.2% run. Bands tightly anchored to that.
- **Skimo** — uphill (skinning + bootpack) dominates time at 55-70%; descents are 20-35%, not the inverse.
- **Modern Pentathlon** — laser-run is the largest single block (30-45%), not equal-weighted across five events.

### Sports where current data was already roughly correct

- Olympic Triathlon (~20/50/30 widely accepted).
- Aquabike (Olympic 30/70 derived directly from triathlon splits).
- Duathlon (~45-55/45-55 standard).
- All mono-discipline sports (Marathon Road/Trail, Mountain Marathon, Fell Running, Sky-Race, XC Skiing, OW Marathon Swim, Endurance Cycling, Ultra Road, Ultra Trail).

### Sports where authoritative data is sparse and bands carry uncertainty

- **Canoe/Kayak Marathon** — ICF publishes course structure (6-8 laps, ~7 portages) but no time-share breakdown; portage % estimated from typical portage length (~300m) × count vs. paddle distance.
- **Biathlon** — published shooting-time data in seconds, not %; range-time % derived from typical bout durations but penalty-loop time highly accuracy-dependent.
- **Modern Pentathlon** — sport in flux (riding → obstacle for LA28); bands reflect 2024 Paris spec but may need re-evaluation post-LA28.
- **Aquathlon** — limited elite-split telemetry; bands derived from ITU 2010-2014 results and World Triathlon's stated equal-time design intent.
- **Adventure Racing** — wide variance race-to-race (some courses bike-heavy 60%, others trek-heavy 50%); bands kept wide deliberately.

---

## Next steps (X1a implementation, post-Andy review)

1. Andy reviews bands per sport; redirects any band he disagrees with (likely candidates: AR ranges given expedition vs. shorter-format variance, the AR sub-discipline split between trekking vs. trail running).
2. Excel patch — update `etl/sources/Sports_Framework_v11.xlsx` Sheet 3 (race_time_pct column) AND Sheet 5 (Phase Load Allocation, Base/Build/Peak/Taper bands) row-by-row. Sheet 5 phase bands need recalibration to match the new race_time_pct anchors.
3. Re-ETL on Neon with a new `--version-tag` (e.g. 1.4.0) — `etl/layer0/extractors/sport_discipline_bridge.py` runs the rebuild.
4. Cone cache fully invalidates on `etl_version_set` change, so first post-deploy plan is a cold rebuild (expected).
5. Sport-specific phase-load bands (Sheet 5) — a related but separate research pass. Current bands like AR Trail Running "Base 12-15% / Build 12-15% / Peak 10-14% / Taper 12-15%" need recalibration to match the new race_time_pct anchor and sport-science taper / volume / specificity literature. Recommend deferring Sheet 5 to a follow-up research pass after Sheet 3 lands — Sheet 5 bands depend on Sheet 3's relative shape.

---

*End of Bridge_Bands_Research_v1.md.*
