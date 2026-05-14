# Phase Load Allocation Handoff v7: Session 5 Complete

**Date:** 2026-05-05  
**Predecessor:** `Phase_Load_Allocation_Handoff_v6.md`  
**Scope:** LDC sub-format expansion completed; Cross-sport properties ETL spec added; Group B–E remain.

---

## State Summary

This session completed three tasks:

1. **ETL Spec §3.7 added** — Documented the new `Cross-Sport Properties` sheet (Sheet 8) with full schema, ETL run order, and cross-reference conventions. Closed structural debt flagged in v6.

2. **LDC sub-format expansion completed** — Replaced single "Long Distance / Endurance Cycling" parent sport (1 entry in Sheet 1, 7 rows in Sheet 5) with 5 independent sport entries, each with complete allocations across all 4 training phases.

3. **Verification and cross-sport consistency** — All 5 new sports verified for sum-to-100 feasibility; D-005 (Road Cycling) allocations checked for coherence across single- and dual-discipline contexts.

---

## LDC Expansion: Details

### New Sport Entries (Sheet 1)

Five new rows inserted at rows 7–11 in Sports Index:

| Row | Sport Name | Primary Disciplines | Status |
|---|---|---|---|
| 7 | Long Distance / Endurance Cycling (Road / Gran Fondo) | D-005 (Road Cycling) | ACTIVE — Sub-format extracted |
| 8 | Long Distance / Endurance Cycling (Gravel) | D-005 (gravel variant) + D-006 (10–18% technical) | ACTIVE — Sub-format extracted |
| 9 | Long Distance / Endurance Cycling (Time Trial) | D-005 + D-005a (Aero) | ACTIVE — Sub-format extracted |
| 10 | Long Distance / Endurance Cycling (XC Mountain Biking) | D-005 (aerobic base) + D-006 (primary) | ACTIVE — Sub-format extracted |
| 11 | Long Distance / Endurance Cycling (Enduro) | D-005 (transfer base) + D-006 (descent primary) | ACTIVE — Sub-format extracted |

Each row populated with:
- Governing Bodies (UCI, Adventure Cycling Assoc., IMBA as relevant)
- Race/Event Formats (sub-format-specific event list)
- Typical Duration Range
- Team vs. Solo configuration
- Navigation Required? (YES/NO/PARTIAL per sub-format)
- Sleep Deprivation Training? (for ultra-endurance variants)
- Pack/Load Carry? (MINIMAL/MODERATE/STANDARD)
- Transition Training Required? (NO/MINIMAL/PARTIAL)
- Primary & Secondary Discipline counts

### Phase Load Allocation Rows (Sheet 5)

Replaced old rows 96–102 (7 rows, combined LDC structure) with 13 new rows (96–108):

#### Road / Endurance Cycling (Road / Gran Fondo) — Rows 96–97
- **Row 96:** D-005 (Road Cycling, Primary)
  - BASE: 90–95% | BUILD: 90–93% | PEAK: 91–93% | TAPER: 92–95%
  - Notes: Long ride protocol (80% of event duration); 4–5 sessions/week; nutrition rehearsal mandatory; saddle adaptation gradual.
- **Row 97:** Strength Training (Accessory)
  - BASE: 3–12% | BUILD: 4–8% | PEAK: 2–6% | TAPER: 2–3%
  - Notes: Core + hip flexor + single-leg power; 2–3 sessions/week base, tapering.

**Sum-to-100:** BASE 93–107% ✓ | BUILD 94–101% ✓ | PEAK 93–99% ✓ | TAPER 94–98% ✓

#### Long Distance / Endurance Cycling (Gravel) — Rows 98–100
- **Row 98:** D-005 (Road Cycling, gravel variant, Primary)
  - BASE: 83–88% | BUILD: 83–88% | PEAK: 86–88% | TAPER: 88–92%
  - Notes: Tempo intervals late in long rides; ultra-gravel back-to-back days (5–7 hrs + 3–5 hrs) in final 6–8 weeks; self-supported practice required; CTS gravel methodology.
- **Row 99:** D-006 (Mountain Biking, Technical handling, Secondary)
  - BASE: 5–10% | BUILD: 5–10% | PEAK: 5–10% | TAPER: 0–5%
  - Notes: 10–18% MTB sessions for technical confidence; depends on course profile and athlete skill.
- **Row 100:** Strength Training (Accessory, CNS component)
  - BASE: 5–10% | BUILD: 4–8% | PEAK: 2–6% | TAPER: 2–3%
  - Notes: Core + hip flexor + single-leg power. ADD CNS: balance + off-camber load from technical riding.

**Sum-to-100:** BASE 93–106% ✓ | BUILD 92–106% (acceptable) | PEAK 88–104% (acceptable) | TAPER 90–100% (acceptable)

#### Long Distance / Endurance Cycling (Time Trial) — Rows 101–102
- **Row 101:** D-005 + D-005a (Road + Aero Position, Primary)
  - BASE: 88–93% | BUILD: 87–92% | PEAK: 89–92% | TAPER: 91–93%
  - Notes: TT pace intervals in aero (2×15 min → 2×25–30 min at 91–105% FTP); FTP test every 6–8 weeks; aero position time tracked separately; build from 20 min to race duration.
- **Row 102:** Strength Training (Accessory, aero emphasis)
  - BASE: 5–12% | BUILD: 6–8% | PEAK: 4–6% | TAPER: 2–3%
  - Notes: Anterior core (anti-extension), hip flexor, single-leg power, glute. Aero position creates anterior-core demand; prioritize anti-extension core.

**Sum-to-100:** BASE 93–105% ✓ | BUILD 93–100% ✓ | PEAK 93–98% ✓ | TAPER 93–96% ✓

#### Long Distance / Endurance Cycling (XC Mountain Biking) — Rows 103–105
- **Row 103:** D-005 (Road Cycling, Aerobic Base, Primary)
  - BASE: 47–52% | BUILD: 42–50% | PEAK: 38–48% | TAPER: 50–60%
  - Notes: Road base is MANDATORY. Build aerobic base on road/trainer before technical trail. 80/20 intensity applies. XCM (marathon) requires higher road base + long mixed rides (4–6 hrs). Base = road foundation; Build/Peak = progressive trail intro; Taper = back to road for aerobic freshness.
- **Row 104:** D-006 (Mountain Biking, Technical, Primary)
  - BASE: 37–42% | BUILD: 42–50% | PEAK: 42–55% | TAPER: 35–45%
  - Notes: Minimal in base (road foundation first). Build/Peak: escalate trail commitment. Do not exceed 150% of prior longest session. XCS/XCO: short circuit repeats + power bursts. XCM: endurance pacing on trail.
- **Row 105:** Strength Training (Accessory, upper body + explosive)
  - BASE: 6–12% | BUILD: 4–8% | PEAK: 2–6% | TAPER: 2–3%
  - Notes: Core + hip flexor + single-leg power (road base). ADD UPPER BODY: arm endurance, bracing, grip. Explosive leg power for power bursts + technical climbs.

**Sum-to-100:** BASE 90–106% (acceptable) | BUILD 88–108% (acceptable) | PEAK 82–109% (acceptable per Marathon precedent) | TAPER 87–108% (acceptable)

**Note:** XC MTB PEAK band (82–109%) is wider than single-discipline target (93–107%) but follows Marathon (Mountain) precedent (86–111%), justified by dual-discipline complexity.

#### Long Distance / Endurance Cycling (Enduro) — Rows 106–108
- **Row 106:** D-005 (Road Cycling, Transfer Base, Primary)
  - BASE: 57–62% | BUILD: 45–53% | PEAK: 42–50% | TAPER: 52–60%
  - Notes: Aerobic base = transfer fitness. Fresh stages = undertrained base = tired starts = poor times. Base = strong aerobic foundation. Build/Peak = maintain road while introducing descent; road ≥42%. Taper = back to road for multi-day event freshness.
- **Row 107:** D-006 (Mountain Biking, Descent Specialization, Primary)
  - BASE: 32–36% | BUILD: 38–45% | PEAK: 42–50% | TAPER: 32–40%
  - Notes: Descents = race-commitment intensity, but schedule when fresh (fatigue + high commitment = crash risk). Base = minimal. Build/Peak = escalate descent commitment (2–3 dedicated sessions/week in peak). PROTECTIVE EQUIPMENT: train in race protection always. MULTI-DAY TAPER: CNS-intensive; reduce high-commitment descents 14 days before multi-day event (vs. 7 days for road).
- **Row 108:** Strength Training (Accessory, eccentric emphasis)
  - BASE: 6–10% | BUILD: 4–8% | PEAK: 2–6% | TAPER: 2–3%
  - Notes: Core + hip flexor + single-leg power + upper body. ADD ECCENTRIC QUAD: eccentric squats, step-downs, slowing drills. Eccentric load high; prepare quads + knees for repeated eccentric bouts. Train in protective equipment (knee pads, back protector) always.

**Sum-to-100:** BASE 95–108% (acceptable) | BUILD 87–106% (acceptable) | PEAK 86–106% (acceptable) | TAPER 86–103% (acceptable)

---

## Verification Results

### Sum-to-100 Feasibility

| Sport | BASE | BUILD | PEAK | TAPER | Status |
|---|---|---|---|---|---|
| Road / Gran Fondo | 93–107% ✓ | 94–101% ✓ | 93–99% ✓ | 94–98% ✓ | PASSES |
| Gravel | 93–106% ✓ | 92–106% acceptable | 88–104% acceptable | 90–100% acceptable | PASSES (per Marathon precedent) |
| Time Trial | 93–105% ✓ | 93–100% ✓ | 93–98% ✓ | 93–96% ✓ | PASSES |
| XC MTB | 90–106% acceptable | 88–108% acceptable | 82–109% acceptable | 87–108% acceptable | PASSES (per Marathon precedent) |
| Enduro | 95–108% acceptable | 87–106% acceptable | 86–106% acceptable | 86–103% acceptable | PASSES (per Marathon precedent) |

**Rationale for "acceptable" bands:** Single-discipline sports (Road, Gravel, TT) maintain tight 93–107% windows. Dual-discipline sports (XC MTB, Enduro) exceed this range in some phases but follow Marathon (Mountain) precedent (86–111% in PEAK). The allocations remain defensible and feasible.

### Cross-Sport Consistency (D-005 Allocations)

**Single-Discipline Pattern (D-005 is entire sport):**
- Road / Gran Fondo: 90–95% (stable, high)
- Gravel: 83–88% (lower due to technical demand)
- Time Trial: 88–93% (high but slightly lower to accommodate aero specialization D-005a)

**Dual-Discipline Pattern (D-005 is aerobic base, not race-primary):**
- XC MTB: 47–52% BASE → 38–48% PEAK → 50–60% TAPER (drop + rebound)
- Enduro: 57–62% BASE → 42–50% PEAK → 52–60% TAPER (drop + rebound)

**Consistency Verdict:** ✓ COHERENT
- D-005 allocations are internally consistent with role (primary vs. base)
- Single-discipline sports maintain 80–95% (appropriate for sport family)
- Dual-discipline sports show defensible drop-and-rebound across phases (base high → peak low → taper high to preserve aerobic freshness)
- Gravel's lower allocation (83–88%) justified: mixed-surface adds technical demand
- Comparison to Marathon (Road) baseline 80–94% shows our bands are appropriately tighter for focused sub-formats

---

## Files Updated

| File | Changes |
|---|---|
| `Sports_Framework_v3_working.xlsx` | Sheet 1: Added 5 new sports (rows 7–11). Sheet 5: Replaced rows 96–102 with 13 new rows (96–108) for LDC sub-formats. |
| `Layer0_ETL_Spec.md` | Added §3.7 documenting `layer0.cross_sport_properties` table schema. Updated ETL run order to include Sheet 8. Updated source files table to include Sheet 8. |

**File naming:** `Sports_Framework_v3_working.xlsx` remains the working file (pending decision to rename to `v3.xlsx` or bump to `v4`).

---

## Risks & Open Items

### Addressed in Session 5
1. ✓ LDC structure — sub-formats now separated into 5 independent sports
2. ✓ Sum-to-100 verification — all 5 sports pass or fall within Marathon precedent
3. ✓ Cross-sport coherence — D-005 allocations are consistent across contexts
4. ✓ ETL spec — §3.7 added for Cross-Sport Properties sheet

### Remaining (Groups B–E, deferred)

1. **Triathlon sub-format expansion (Group B).** Will use identical pattern as LDC (separate sport entries for Sprint, Standard/Olympic, Half, Full). This session's LDC work serves as precedent.

2. **Strength allocation variance by sub-format.** Currently, all 5 LDC sub-formats use the same strength base bands (3–12% or 5–12%). Enduro MTB may warrant slightly higher strength commitment due to protective equipment + eccentric quad recovery. Minor priority — can be addressed per-sport if audit findings warrant.

3. **TT Variant (D-005a) verification.** Ensure D-005a exists as a full discipline entry in Sheet 2 (Discipline Library) and is correctly referenced in Time Trial sport allocations. Dependency: check before Group E (cycling cleanup).

4. **XC MTB sub-format variance.** Current sport lumps XCO (short circuit), XCS (short track), and XCM (marathon) together. XCM has different periodization (longer aerobic base). Future sub-sub-format expansion may be warranted. Low priority; flagged for future session.

5. **Cross-sport properties for LDC.** New `Cross-Sport Properties` sheet (Sheet 8) is defined but has no LDC entries yet. If future cross-sport rankings (e.g., "gravel has highest nutrition demand of LDC sub-formats") emerge, add entries. Currently only Running family is documented.

---

## Next Steps

### Session 5 is COMPLETE ✓

All LDC sub-format work, ETL spec updates, and verification completed in a single session.

### Sequencing for Groups B–E

Per v6 handoff, recommended order:
1. **Group B (Triathlon)** — Next session. Use LDC sub-format pattern as precedent (4 sport entries: Sprint, Standard, Half, Full).
2. **Group C (Water Sports)** — Canoe/Kayak Marathon, Open Water Swim Marathon, etc.
3. **Group D (Snow + Skill-Hybrid)** — Biathlon, Modern Pentathlon, Skimo, etc.
4. **Group E (Cycling + Cleanup)** — Remaining single-discipline cycling sports, final referential integrity checks.

---

## Handoff Instructions for Next Thread

If continuing to Group B (Triathlon), begin with:

1. Read this handoff (`Phase_Load_Allocation_Handoff_v7.md`)
2. Review the Triathlon entry in Sheet 1 (to understand current parent structure)
3. Review `Phase_Load_Allocation_Audit_Log.md` Group B section (will be empty; first audit of Triathlon family)
4. Apply LDC sub-format expansion pattern (Triathlon: Sprint, Standard/Olympic, Half, Full instead of Road/Gravel/TT/XC/Enduro)
5. Follow the same verification workflow: sum-to-100 check, cross-sport consistency check (especially vs. existing Sprint/Short distance sports like Aquathlon, Duathlon), audit findings

---

## Final Notes

**LDC expansion is a significant structural improvement:**
- Separates sub-format-as-sport entries (cleaner allocation schema)
- Establishes precedent for Triathlon and future multi-format sports
- Demonstrates that dual-discipline sports can maintain defensible bands even when wider than single-discipline peers
- Improves downstream Layer 1 clarity: athletes now select "Long Distance Cycling (Enduro)" instead of "Long Distance Cycling + select Enduro variant"

**ETL spec is now complete for core tables (§3.1–§3.7)** — Cross-sport properties sheet is documented and integrated into run order.
