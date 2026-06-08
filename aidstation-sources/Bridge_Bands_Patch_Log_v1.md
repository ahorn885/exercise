# Bridge Bands Patch Log v1 — Sports_Framework v11 → v12

**Date:** 2026-06-07/08
**Source:** `etl/sources/Sports_Framework_v11.xlsx`
**Target:** `etl/sources/Sports_Framework_v12.xlsx`
**Sheet patched:** Sheet 3 ("Sport × Discipline Map"), column F ("Est. % of Race Time")
**Research substrate:** `Bridge_Bands_Research_v1.md`
**Spec:** `Modality_Group_Spec_v1.md`

## Summary

- **43 rows changed** out of 73 total in Sheet 3.
- **All changes verified to parse correctly** against the ETL regex `(\d+)(?:[–-](\d+))?%` per `Layer0_ETL_Spec_v3.md:251` — the first match is the operational `race_time_pct_low/high` pair.
- **No schema changes.** Only the text values in column F change. Other columns (Applicability, Role, Sport-Specific Context, B2B Pairing Rule, Phase Load text, Default Inclusion) untouched.
- **Sheet 5 (Phase Load Allocation) NOT patched in this revision.** Deferred to a follow-up research pass (see `Bridge_Bands_Research_v1.md` next-steps §3).
- **Rows intentionally left unpatched** (no operational impact):
  - r25 (Ultramarathon Trail × Mountaineering) — `EXCLUDED`, dash band, no load_weight (excluded disciplines don't allocate).
  - r27 (Triathlon × D-007 TT bike) — text "Included in D-006 bike % — not additional time". Design choice: TT bike is a variant of D-006, not a separate allocation slot. Load_weight intentionally on D-006 only.

## Changes by sport

### Adventure Racing (rows 2–16, 7 changes)

The biggest correction. Plan #61's TR-dominant allocation traces directly to these bands being wrong for expedition AR.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 2 | D-001 Trail Running | 15–25% | **8–15%** | Expedition AR: hike-walking dominates foot share; running reserved for runnable flats. |
| 3 | D-003 Hiking (Weighted/Trek) | 10–20% | **18–30%** | Trek is the primary foot discipline; loaded hike legs of 20–50 km common. |
| 5 | D-006 XC Cycling | 25–35% | **0–15%** | XC/gravel cycling rare in expedition AR; MTB dominates. Range allows occasional road-section formats. |
| 6 | D-008 Mountain Biking | 10–20% | **35–55%** | Sea-to-Sea published 60% of distance on bike → ~35–55% of time. Materially wrong in v11. |
| 7 | D-009 Packrafting | 5–15% | **10–25%** | Typical AR paddle craft when course requires portage-friendly boat. |
| 8 | D-010 Flat-water Kayaking | 5–15% | **10–25%** | Alternates with packraft as the typical AR paddle craft. |
| 10 | D-011 Canoeing | 0–10% | **0–15%** | Race-conditional; some N. American expedition AR uses canoe. |

Rows unchanged: 4 (D-015 Nav 100% overlay), 9 (D-010 Whitewater 0–5%), 11–16 (Rock 0–5, Abseil 0–2, Via Ferrata 0–3, Swim 0–2, Snowshoe 0–5, Mountaineering 0–5).

### Triathlon (rows 17–20, 3 changes)

Olympic-distance per World Triathlon elite splits.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 17 | D-004 Open Water Swimming | 8–18% | **15–22%** | Olympic elite ~25min of ~120min = ~21%. v11 band looked sprint-tuned. |
| 19 | D-002 Road Running (Olympic) | 20–35% | **25–35%** | Olympic elite ~35min of ~120min = ~29%. Tighten. |
| 20 | D-002 Road Running (IM) | 30–40% | 30–40% | Unchanged — matches research (Blummenfelt 35%, AG 39%). |

Row 18 (D-006+D-007 Road Cycling) unchanged at 45–55% — already correct.
Row 27 (D-007 TT bike) unchanged — intentionally folded into D-006 bike share.

### Ultramarathon (Trail) (rows 21–25, 1 change)

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 21 | D-001 Trail Running + Power Hiking | 60–75% | **50–65%** | Damian Hall published ~60% running, ~40% hiking for UTMB. Sub-discipline uphill/downhill rows carry the rest. |

Rows 22 (Uphill 15–30%), 23 (Downhill 15–25%), 24 (Road cross-train 0–15%), 25 (Mountaineering EXCLUDED) unchanged.

### Ultramarathon (Road) (row 26) — unchanged

95–100% mono-discipline. Already correct.

### Duathlon (rows 28–29, 2 changes — both fix v11 parsing bug)

v11 led with "R1: ~25%" — the regex picked 25% as low=high for R1 alone, not the total. Fixed.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 28 | D-002 Road Running (R1 + R2) | First-parse 25–25% | **40–55%** | Total run dominates over bike for standard duathlon (~38–45% combined). |
| 29 | D-006 Road Cycling | 57–57% (point) | **45–60%** | Bike share for standard 10/40/5: ~50%. Range supports Powerman Zofingen long-distance variant. |

### Aquathlon (rows 30–31, 2 changes)

World Triathlon's stated equal-time design + 2014 ITU WCh splits.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 30 | D-004 Open Water Swimming | 25–40% | **35–50%** | Elite 1km swim ~11–12min vs 5km run ~15–17min → swim ~42%. v11 too low. |
| 31 | D-002 Road Running | 60–75% | **50–65%** | Complementary; run dominates by small margin for elites. |

### Aquabike (rows 32–33, 2 changes)

Derived from Olympic-distance triathlon (no run leg).

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 32 | D-004 Open Water Swimming | 10–20% | **25–35%** | Elite ~25min swim / ~60min bike → 29% swim. v11 was triathlon-tuned (too low). |
| 33 | D-006 Road Cycling | 80–90% | **65–75%** | Complementary; ~71% elite. |

### Swimrun (rows 34–35, 2 changes)

ÖTILLÖ-published 12.8% / 87.2%.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 34 | D-016 Swimming | 40–55% | **12–22%** | ÖTILLÖ published 12.8% swim for fast teams; ~20% for slower. v11 was off by ~3x. |
| 35 | D-001 Trail Running | 50–65% | **78–88%** | Complementary; ~87% for fast teams. |

Row 36 (D-020 Combined overlay) unchanged at 100% — overlaid format descriptor.

### Skimo (rows 37, 39, 2 changes)

ISMF Individual race; uphill dominates.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 37 | D-021 Uphill Skinning | 65–80% | **55–70%** | Tightened to research; descents are 20–35%, uphill should not exceed 70%. |
| 39 | D-023 Boot-packing & Transitions | 2–10% | **3–10%** | Minor; elite transitions ~15–45s × 6–8. |

Row 38 (D-022 Alpine Descent 20–35%) unchanged.

### Mountain Running / Skyrunning (rows 40–43, 1 change — base-row null-band fix)

Sub-discipline rows already match research closely (Uphill 50–65%, Downhill 35–50%, Scrambling 0–5%). The base D-001 row had no `%` band, leaving D-001 NULL-weighted for Mountain Running athletes.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 40 | D-001 Trail Running (base) | (no band; null) | **95–100%** | Umbrella mono-discipline; uphill / downhill / scrambling rows sub-allocate within. Without a band, D-001 silently dropped from Layer 2A allocation if `included_discipline_ids` referenced it. |

### Fell Running (rows 44–47, 1 change — base-row null-band fix)

Same shape as Mountain Running. Sub-discipline rows correct; base row was null.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 44 | D-001 Trail Running (base) | (no band; null) | **95–100%** | Umbrella mono-discipline; uphill / downhill / nav rows sub-allocate within. |

### Modern Pentathlon (rows 48–51, 4 changes)

UIPM 2024+ obstacle replacement format.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 48 | D-025 Epee Fencing | 20–25% | **20–30%** | Round-robin epee bouts; ~15–20min in active envelope. Widen range. |
| 49 | D-027 OCR (Obstacle) | 10–15% | **20–30%** | Replaces equestrian post-2024; ~15–20min in active envelope. Larger block than v11 assumed. |
| 50 | D-005 Pool Sprint Swimming | 12–18% | **5–10%** | 200m freestyle ~2:00–2:30 only. v11 overstated swim. |
| 51 | D-026 Laser Run | 30–40% | **30–45%** | 3.2km run + 4 shoot stops; widen upper bound. Largest single block. |

### Marathon (Road) (row 52) — 1 change

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 52 | D-002 Road Running | 100% | **98–100%** | Mono-discipline; tighten from absolute 100% to standard 98–100% band. |

### Marathon (Trail) (row 53) — 1 change

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 53 | D-001 Trail Running | 90–100% | **98–100%** | Mono-discipline; tighten upward (cross-train row covers any road bleed). |

Row 54 (Road cross-train 0–10%) unchanged.

### Marathon (Mountain) (rows 55–57) — unchanged

Uphill/downhill split preserved as useful per-discipline allocation.

### Long Distance / Endurance Cycling (rows 58–62, 5 changes — duration-descriptor null-band fix)

All five rows previously held duration text (hours/minutes) instead of `%` bands. Layer 2A parsed NULL load_weight, silently dropping D-006 / D-008 from allocation for Endurance Cycling athletes. Each row gets a 95–100% band reflecting its mono-discipline format share, while preserving the duration text as athlete-facing context.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 58 | D-006 Road Cycling (Road Long Distance) | (duration only; null) | **95–100%** | Mono-discipline for road-format athletes. Century / Ultra-endurance road. |
| 59 | D-006 Road Cycling (Gravel Racing) | (duration only; null) | **95–100%** | Mono-discipline for gravel-format athletes. 50-mi to Unbound 200. |
| 60 | D-006+D-007 Time Trial Cycling | (duration only; null) | **95–100%** | Mono-discipline for TT-format athletes. 10km TT to 100km TT. |
| 61 | D-008 Mountain Biking (XC Olympic / Short) | (duration only; null) | **95–100%** | Mono-discipline for XC-MTB-format athletes. XCO / XCS / XCM. |
| 62 | D-008 Mountain Biking (Enduro) | (duration only; null) | **95–100%** | Mono-discipline for Enduro-format athletes. Aggregate time on bike. |

**Note on duplicate discipline_ids:** rows 58 + 59 both carry D-006 with different format variants. Layer 2A's SELECT against `sport_discipline_bridge` will return both for the Endurance Cycling framework_sport; the query orders by `discipline_id` and the duplicate handling is undefined. This is a pre-existing bridge schema limitation (multiple rows per (sport, discipline_id) for sub-format variants). Worth filing as its own bug; not blocking the X1a fix.

### Off-Road / Adventure Multisport (XTERRA, rows 63–65, 3 changes)

XTERRA published 10/65/25 formula.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 63 | D-004 Open Water Swimming | first-parse 1–500% (range bug from "1.5km / Sprint: 500m") | **8–15%** | XTERRA published 10% swim. v11 parsed garbage from the distance descriptor. |
| 64 | D-008 Mountain Biking | first-parse 30–15% (range bug from "30km/Sprint:15km") | **55–70%** | XTERRA published 65% MTB. v11 also parsed garbage. |
| 65 | D-001 Trail Running | first-parse 11–5% (bug from "11km/Sprint:5km") | **20–30%** | XTERRA published 25% trail run. v11 parsed garbage. |

Note: r63–r65 all had v11 parsing bugs where the distance descriptor preceded the % band. Fixed alongside the value update.

Rows 66–68 (Quadrathlon paddle, Packraft free-format, Road cycling base) — conditional format rows, unchanged.

### Cross-Country / Nordic Skiing (row 69) — 1 change

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 69 | D-028 Cross-Country/Nordic Skiing | 100% | **98–100%** | Mono-discipline; tighten to standard band. |

### Biathlon (rows 70–71, 2 changes)

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 70 | D-028 XC Skiing - Skate | 85–90% | **80–92%** | Widen per research (IBU sprint ~25min skiing share). |
| 71 | D-029 Biathlon Shooting | 10–15% | **8–20%** | Widen per research; penalty loops vary with misses (0–5). |

### Canoe / Kayak Marathon (rows 72–73, 2 changes)

ICF marathon distance with portages.

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 72 | D-010 Flat-water Kayaking | 100% | **88–96%** | Portage time 4–12% (6–8 portages of several hundred meters each). |
| 73 | D-011 Canoeing | 100% | **88–96%** | Same — portages are a real fraction of time in C1/C2 marathons. |

### Open Water Marathon Swimming (row 74) — 1 change

| Row | Discipline | Old | New | Why |
|---|---|---|---|---|
| 74 | D-004 Open Water Swimming (Marathon Volume) | 100% | **98–100%** | Mono-discipline; tighten to standard band. |

## Validation

Every patched row was verified to:
1. **Parse correctly** with the ETL regex `(\d+)(?:[–-](\d+))?%` — the FIRST match in the text is the operational `(low, high)` pair.
2. **Pick a reasonable midpoint** = `(low + high) / 2` per `layer2a/builder.py:_compute_load_weight`. Same input → same midpoint, every time.

Validation output sampled:
```
r  6 Adventure Racing         D-008  Mountain Biking          → low= 35 high= 55 mid= 45.0  ← THE big AR fix
r 17 Triathlon                D-004  Open Water Swimming      → low= 15 high= 22 mid= 18.5
r 34 Swimrun                  D-016  Swimming                 → low= 12 high= 22 mid= 17.0
r 64 Off-Road / XTERRA        D-008  Mountain Biking          → low= 55 high= 70 mid= 62.5
```

Full table dumped at apply-time.

## Pre-existing v11 issues — fix status

- **r40, r44 base aerobic-engine rows** (Mountain Running / Fell Running × D-001) — **FIXED** in this patch (95–100% bands; preserves the aerobic-engine descriptor as inline context).
- **r58–r62 Endurance Cycling format-variant rows** — **FIXED** in this patch (95–100% bands per format; duration descriptors retained as inline context).
- **r25, r27** — intentionally null and left unpatched. `EXCLUDED` (Mountaineering in Trail Ultra) and "see D-006 for TT bike" are valid design choices, not bugs.
- **Duplicate discipline_ids in same framework_sport** (e.g., D-006 appears in r58 + r59 for Endurance Cycling) — **NOT FIXED** here. Pre-existing bridge schema limitation; Layer 2A's SELECT returns both rows and duplicate handling is undefined. Worth filing as its own bug.

## Apply this patch

1. Review this log → confirm bands.
2. Andy's-hands on Neon: re-ETL with `--version-tag 1.4.0` (or next available) using `etl/layer0/extractors/sport_discipline_bridge.py` against `etl/sources/Sports_Framework_v12.xlsx`. Sheet 5 stays at v11 values until the deferred Phase Load Allocation research pass lands.
3. Cone cache fully invalidates on `etl_version_set` change → first post-deploy plan is a cold rebuild (expected; the existing Layer 4 cone-cache rebind handles this).
4. Verify on a re-run cold plan that AR plans now allocate MTB-dominant (the load_weight midpoint for D-008 MTB in AR jumps from 15 → 45).

---

*End of Bridge_Bands_Patch_Log_v1.md.*
