# Phase Load Allocation Handoff v6

**Date:** 2026-05-05
**Predecessor:** `Phase_Load_Allocation_Handoff_v5.md`
**Scope:** Group A CLOSED. New Cross-Sport Properties sheet established. Session 5 + Groups B–E remaining.

---

## State summary

This thread executed the v5 batch-application work. All pending Group A audit recommendations are now applied to `Sports_Framework_v3.xlsx`:

- **2 band changes:** Marathon (Mountain) Downhill Peak high 18 → 15; Marathon (Mountain) Mobility Base 3–5 → 4–6.
- **12 notes-only fixes:** Q-UF1, Q-UF2, Q-MF1, Q-MF2, Q-MF3 explanatory notes added; Fell Running Mobility placeholder flag removed; vertical-gain reference added to Marathon (Trail); structural notes added for Mountain Running's wide bands and Mobility phase shape.
- **All 7 Group A sports re-verified for sum-to-100 feasibility** post-application. All pass.

A new sheet, `Cross-Sport Properties`, was created to capture comparative rankings that don't fit per-row in Sheet 5. Initial entry `LIT_RATIO_001` documents the global LIT-ratio ranking across the running family. Marathon (Road)'s family-scoped claim ("Highest LIT ratio of the marathon sub-formats") survives globally as the running-family leader by a small margin, with Ultramarathon (Road) likely sitting slightly higher. The new sheet is extensible for future entries (eccentric load, strength primacy, navigation demand, etc.).

**Group A is CLOSED.** Audit log has a Group A close summary entry. Next thread is Session 5.

One reconciliation finding from this thread: the v5 handoff's row numbers for Marathon (Mountain) were approximate (R93/R94/R96 referenced wrong rows — actual rows are R92/R93/R94). Caught and corrected before any data was misapplied. The v5 handoff explicitly instructed "verify row numbers before editing" — that worked.

---

## Files and their roles

| File | Role | Current state |
|---|---|---|
| `Sports_Framework_v3_working.xlsx` | Authoritative framework data — POST-AUDIT | All Group A audit-finding deltas applied. New `Cross-Sport Properties` sheet added. 8 sheets total. |
| `Layer0_ETL_Spec.md` | ETL schema reference | v3-compatible. NEEDS UPDATE for the new `Cross-Sport Properties` sheet (see Open Items). |
| `Phase_Load_Allocation_Audit_Log.md` | Per-sport audit findings | A.1–A.7 complete; Group A close summary added; Groups B–E pending |
| `Phase_Load_Allocation_Handoff_v5.md` | Predecessor handoff | Superseded by this doc |

The renamed file `Sports_Framework_v3_working.xlsx` should replace `Sports_Framework_v3.xlsx` as the canonical framework data file. Andy may wish to rename it back to `Sports_Framework_v3.xlsx` (or bump the version to v4) — naming is his call.

---

## Group A — final state (CLOSED)

| Sport | Rows | Sum-to-100 (post-application) |
|---|---|---|
| A.1 Marathon (Road) | R81–R84 | 93–107 / 93–107 / 93–107 / 93–107 |
| A.2 Marathon (Trail) | R85–R89 | 93–107 / 93–107 / 93–107 / 93–107 |
| A.3 Marathon (Mountain) | R90–R95 | 89–113 / 87–113 / 86–111 / 87–113 |
| A.4 Ultramarathon (Road) | R77–R80 | 93–107 / 93–107 / 93–107 / 93–107 |
| A.5 Ultramarathon (Trail) | R70–R76 | 87–111 / 87–113 / 88–114 / 86–112 |
| A.6 Mountain Running / Skyrunning | R51–R56 | 87–111 / 87–120 / 89–123 / 79–103 |
| A.7 Fell Running | R57–R63 | 92–116 / 91–122 / 91–124 / 86–110 |

All 7 sports VERIFIED. All pre-flight feasibility intact. All cross-sport coherence questions (Q-MF1, Q-MF2, Q-MF3, Q-UF1, Q-UF2) closed.

Marathon (Mountain) was the only sport with phase-band shifts during application:
- BASE 88–112 → 89–113 (Mobility Base raise)
- PEAK 86–114 → 86–111 (Downhill Peak high narrow)

---

## New: Cross-Sport Properties sheet

Schema:

| Column | Description |
|---|---|
| Property ID | Stable identifier (e.g., LIT_RATIO_001) |
| Property Name | Human-readable name |
| Description | What the property captures |
| Scope | Family or "All endurance" |
| Ranking (high to low) | Ordered list of sports |
| Estimated Values | Concrete numerical anchors per sport |
| Source(s) | Tier 1/2 references |
| Confidence | Low/Medium/High |
| Notes | Caveats, individual variation, edge cases |

Initial entry: `LIT_RATIO_001` for the running family. Schema is intentionally simple and will absorb future cross-sport rankings without structural change.

---

## Risks and blind spots

(Carried forward from v5 with updates from this thread.)

**1. AR Taper feasibility patch values aren't sourced.** Unchanged. Defer to AR audit.

**2. LDC sub-format expansion is the single biggest piece of unfixed structural debt.** Unchanged.

**3. NEW — `Cross-Sport Properties` sheet is not yet in the ETL spec.** The Layer 0 ETL spec defines schemas for Sheets 1–7. The new Sheet 8 needs an `etl_spec` section added. Without this, downstream consumers won't know to look there. **Recommended:** add a §3.7 (or similar) to `Layer0_ETL_Spec.md` covering the new sheet. Could be done quickly in any thread; small fix.

**4. The cross-reference from R81 to the new sheet is informal.** Marathon (Road) R81 notes now mention "see sheet 'Cross-Sport Properties' entry LIT_RATIO_001". This is a textual reference, not a foreign-key relationship. If any other Sheet 5 row eventually references a Cross-Sport Properties entry, the convention needs to stay consistent. Recommended convention: `[Cross-Sport: PROPERTY_ID]` as a tag in Sheet 5 notes for machine-grep-ability. Not blocking; revisit when second cross-reference appears.

**5. Cross-sport pattern decisions ossify.** Unchanged.

**6. Audit verification grounded but not exhaustive.** Unchanged.

**7. "VERIFIED" means defensible, not optimal.** Unchanged.

**8. NEW — File naming.** This thread saved to `Sports_Framework_v3_working.xlsx`. Andy may want to rename to `Sports_Framework_v3.xlsx` (overwriting) or bump to `v4`. The `_working` suffix is provisional.

---

## Remaining work

### Session 5 — own thread (3–4 hrs estimated, unchanged)

Per Andy's sequencing: Session 5 BEFORE Group B because Triathlon will hit the same sub-format-as-sport-entry pattern.

Scope:
- LDC sub-format expansion: 5 sport entries (Road / Gran Fondo, Gravel, TT, XC MTB, Enduro). Updates across Sheets 1, 3, 5.
- Off-Road / Adventure Multisport (Non-Nav) verification.
- Cross-sport consistency pass: shared disciplines (Trail Running, Road Cycling, Mountain Biking, Strength) should have coherent allocation patterns across sports.
- **NEW:** add ETL spec §3.7 for the `Cross-Sport Properties` sheet (small task, can fit at start or end of Session 5).
- **NEW (optional):** revisit Marathon (Road) R81 cross-reference convention — should the textual reference become a structured tag like `[Cross-Sport: LIT_RATIO_001]`?

### Groups B–E (carried unchanged)

- Group B: Triathlon family
- Group C: Water sports
- Group D: Snow + skill-hybrid
- Group E: Cycling + cleanup (anything LDC didn't already cover)

---

## First instructions for next thread (Session 5)

Read these files in order:
1. This handoff (`Phase_Load_Allocation_Handoff_v6.md`)
2. `Phase_Load_Allocation_Audit_Log.md` — Group A close summary at the end of Group A section establishes the verified state
3. `Sports_Framework_v3_working.xlsx` — focus on Sheet 5 LDC rows and Sheet 1 LDC entry
4. `Layer0_ETL_Spec.md` — note that §3.7 for the new Cross-Sport Properties sheet is missing

Then proceed with Session 5 work as scoped in v3/v4/v5 (LDC sub-format expansion, Off-Road/Adventure Multisport (Non-Nav) verification, cross-sport consistency pass).

Suggested early task to keep handoff short: add the ETL spec §3.7 for `Cross-Sport Properties` as the first 30-min task. This closes the immediate structural debt from this thread.

Working approach unchanged from prior handoffs:
- Source-grounded verification (Tier 1 priority, Tier 2 acceptable, Tier 3 with triangulation)
- Run sum-to-100 pre-flight before sourcing
- Hold pending recommendations in audit log; apply in batch at end of Session 5 work
- Andy prefers concise/direct, full rigor over speed, honest uncertainty over false confidence

Final note: Andy is currently doing his own AR training for Pocket Gopher Extreme 2026 (July 17–19). The framework work is parallel; same xlsx schemas conceptually but different data files. Don't conflate them.
