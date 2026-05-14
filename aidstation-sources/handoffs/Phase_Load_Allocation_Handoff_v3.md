# Phase Load Allocation Handoff v3

**Date:** 2026-05-05
**Predecessor:** `Phase_Load_Allocation_Handoff.md` (v2)
**Scope:** Structural foundation fixes + first 3 of 7 Group A audits complete; 4 audits + Session 5 + cross-sport consistency remaining

---

## State summary

Group A audit started under v2 handoff. Pre-flight surfaced two foundation issues that needed fixing before further audit work: AR's non-canonical conditional flag convention, and Layer 0 ETL spec incompatibilities with the new numeric Sheet 5 schema. Both fixed this thread along with Fell Running's missing Mobility row and a limited-scope LDC R99/R100 (formerly R98/R99) normalization.

Three Group A sports verified at full rigor: Marathon (Road), Marathon (Trail), Marathon (Mountain). All passed verification with open items recorded but not yet applied to the xlsx — those are batched for end-of-Group-A and resolved against cross-sport coherence questions in the mountain-running family.

Andy's sequencing call: finish Group A in subsequent threads (2 sports per thread at full rigor), then do Session 5 (LDC sub-format expansion), then Group B onwards.

---

## Files and their roles

| File | Role | Current state |
|---|---|---|
| `Sports_Framework_v3.xlsx` | Authoritative framework data | Structural fixes applied (AR conditionals, AR taper bands, Fell Running Mobility row, LDC R99/R100 placeholder); audit-finding deltas NOT yet applied |
| `Layer0_ETL_Spec.md` | ETL schema reference | Updated to v2-compatible: §3.4 drops phase_load cols, §3.6 uses Low/High pairs + is_conditional, new §3.6.1 weekly totals table, §6.2 run order updated, §7 open items #7 (LDC) and #8 (sport count) added |
| `Phase_Load_Allocation_Audit_Log.md` | Per-sport audit findings with sources | A.1, A.2, A.3 complete; A.4–A.7 + Groups B–E pending |
| `Phase_Load_Allocation_Handoff.md` (v2) | Predecessor handoff | Superseded by this doc |

---

## Structural fixes applied (xlsx)

### AR conditional flag canonicalization

R8 Kayaking, R9 Canoeing, R14 Snowshoeing, R15 Mountaineering all converted from `Primary*` / `Minor*` to canonical `Primary (*Conditional)` / `Minor (*Conditional)` role suffix. Notes prefixed with `*CONDITIONAL — ...` per sheet-wide convention used by Ultramarathon (Trail), Marathon (Trail), and Off-Road Multisport.

R8 specifically: now flagged conditional with Packraft as default — interchangeable when race uses kayak. Captures the actual "athlete picks one paddle discipline based on race" pattern that was previously implicit only in notes.

### AR Taper band feasibility patch (placeholder values)

Pre-fix sum (with conditionals zeroed): Taper 64–90, infeasible. Post-fix: 69–101, feasible.

5 rows touched in AR Taper column only. **All flagged `[TAPER feasibility patch — pending AR audit]` in notes.** Values are not source-derived; they are minimum-touch lifts to achieve sum-to-100 feasibility:

- R2 Trail Running: 10–12 → 12–15
- R3 Hiking Weighted: 12–15 → 12–17
- R5 XC Cycling: 15–20 → 17–22
- R6 Mountain Biking: 8–10 → 8–12
- R18 Mobility/Recovery: 5–8 → 6–10

**The AR audit session must re-derive these from authoritative sources.** The flag text in notes is the marker for which rows need re-verification.

### Fell Running Mobility row inserted (R62)

Structural gap surfaced by sanity check — every other Group A sport had a Mobility/Recovery row, Fell Running did not. Inserted with values approximated from Mountain Running family (4–6 / 4–6 / 4–6 / 6–9). Subsequent row numbers shifted +1.

Flagged in notes as "approximate Mountain Running family — pending Fell Running audit verification." The Fell Running audit (A.7) needs to confirm whether these values match authoritative fell-running sources or need adjustment.

### LDC R99/R100 limited normalization

These rows (XC MTB and Enduro sub-formats) had no numeric values — the data was embedded as text in the Notes column expressing per-sub-format D-005/D-006 splits. Limited fix:

- Numeric placeholder values populated (combined cycling totals, ~86–95% across phases)
- "AWAITING NORMALIZATION" replaced with "PENDING SUB-FORMAT EXPANSION (Session 5)"
- Per-sub-format discipline split preserved as structured text in Notes
- ETL spec §3.6 explicitly skips PENDING-flagged rows

The structural problem (R96–R100 are sub-format alternatives summing to ~270% if treated additively) **is not fixed** — only Session 5's sub-format-as-sport-entry expansion can fix it. Logged as ETL Open Item #7.

---

## Structural fixes applied (ETL spec)

### §3.4 sport_discipline_map

- Dropped `phase_load_*_pct` numeric columns (Sheet 3 col 9 is now text-only summary)
- Added `applicability` column (Sheet 3 col 4)
- Added explicit ETL filter: skip rows where `applicability = 'EXCLUDED'`
- Added Sheet 3 col 9 to excluded-from-ETL list with rationale

### §3.6 phase_load_allocation

- Replaced 4 single-numeric phase columns with 8 Low/High pair columns
- Added `is_conditional BOOLEAN` (detected via `(*Conditional)` in role OR `*CONDITIONAL` prefix in notes)
- Documented row filtering: skip aggregator rows, skip PENDING rows, skip EXCLUDED rows
- Documented that Layer 4.5 owns sum-to-100 validation (advisory, not blocker)

### §3.6.1 phase_load_weekly_totals (new table)

Aggregator-row data into its own table with optional `duration_bucket` field for ultra and LDC sports (the latter until Session 5 normalizes them).

### §4.3 output payload

- Phase load fields now expose `{low, high}` ranges
- `is_conditional` exposed per discipline
- Weekly hours moved from per-discipline to sport-level (with optional duration_bucket)

### §6.2, §7

- Run order updated to include `phase_load_weekly_totals` as step 6
- Open Items #7 (LDC sub-format expansion blocking sum-to-100) and #8 (sport count update from 19 to 21) added
- Sheet 3 col references updated from col 7 to col 8 (Applicability column shift)

---

## Audit progress

| Sport | Status | Open items requiring xlsx changes | Cross-sport questions |
|---|---|---|---|
| A.1 Marathon (Road) | VERIFIED | None blocking; strength Base low edge (10%) is conservative vs McMillan but defensible | "Highest LIT ratio of marathon family" claim survives Trail/Mountain check; needs cross-check vs Mountain Running, Fell Running |
| A.2 Marathon (Trail) | VERIFIED | (1) Add vertical-gain reference to notes per Q5 convention. (2) Strength session count vs duration prescription needs downstream check (audit log #2) | None |
| A.3 Marathon (Mountain) | VERIFIED | (1) Narrow Downhill Peak high from 18% to 15–16% (literature supports 1–2 sessions/peak block, not 2–3/wk). (2) Strength % (10–12%) is 2–3% lower than Mountain Running's 12–15%. (3) Mobility Base (3–5%) may be underdosed for eccentric DOMS recovery vs Mountain Running's 5–8% | Strength % and Mobility % both deferred to mountain-family batch resolution after A.6, A.7 |
| A.4 Ultramarathon (Road) | PENDING | — | — |
| A.5 Ultramarathon (Trail) | PENDING | — | — |
| A.6 Mountain Running / Skyrunning | PENDING | Pre-flight: Peak high band 123% (widest in Group A — feasible but check intentional) | Anchors mountain-family strength/mobility coherence |
| A.7 Fell Running | PENDING | Pre-flight: inserted Mobility row needs source verification | Anchors mountain-family strength/mobility coherence |

### Source tier reference (carried from v2)

- **Tier 1:** Peer-reviewed periodization studies, federation/governing-body coach education
- **Tier 2:** Coach books (Friel, Daniels, Magness, Allen & Coggan, Pfitzinger), credentialed coach blogs
- **Tier 3:** Athlete training logs from credible competitors, reputable magazines — only with triangulation
- **Reject:** Uncredentialed blogs, AI-generated content

---

## Cross-sport coherence questions (Mountain family — resolve in batch)

Three questions surfaced from A.3 Marathon (Mountain) audit that should NOT be resolved against Marathon (Mountain) in isolation. Resolve all four mountain-leaning sports together when A.6 and A.7 are done.

The four sports in scope: Marathon (Mountain), Ultramarathon (Trail), Mountain Running / Skyrunning, Fell Running.

### Q-MF1: Strength %

Current values:
- Marathon (Mountain) Base: 10–12%
- Ultramarathon (Trail) Base: 8–10%
- Mountain Running / Skyrunning Base: 12–15%
- Fell Running Base: 10–12%

Spread is 4 percentage points. Resolve: should the family converge on a band, or are these intentional differences justified by event duration / peak intensity differences? My initial read: shorter/more intense events (Mountain Running, Fell Running) get higher strength % allocation, longer events (Ultra Trail) get lower because endurance demand crowds out strength time. If that logic holds, the current spread is correct. But Marathon (Mountain) at 10–12% sitting below Fell Running at 10–12% (similar duration, less intensity) is hard to justify. Possible action: bump Marathon (Mountain) to 11–13%.

### Q-MF2: Mobility/Recovery Base %

Current values:
- Marathon (Mountain) Base: 3–5%
- Ultramarathon (Trail) Base: 4–6%
- Mountain Running / Skyrunning Base: 5–8%
- Fell Running Base: 4–6% (placeholder, pending A.7 verification)

Mountain Running's 5–8% Base is the family outlier on the high side. Question: is high mobility Base justified by skyrunning's eccentric-load profile (very steep descents at race intensity), or should the rest of the family rise toward it? My read: Marathon (Mountain) and Fell Running likely need to rise to 4–6% Base minimum given their similar eccentric demand. Mountain Running's 5–8% may stay distinct because skyrace descents are more aggressive than marathon-distance mountain races.

### Q-MF3: LIT ratio claim

Marathon (Road) notes claim "Highest LIT ratio of the marathon family." Verified against Marathon (Trail) and Marathon (Mountain) — claim survives. **Still need to validate against Mountain Running and Fell Running.** If either has a higher LIT ratio than Marathon (Road), the claim is wrong and needs editing. My expectation: Mountain Running has more intentional high-intensity work (climbing repeats, race-pace surges on grade) than Marathon (Road), so LIT ratio is lower. Fell Running varies by event but tends toward more all-out efforts in shorter races.

---

## Pending recommendations NOT yet applied to xlsx

These come from completed audit log entries. Hold them until end of Group A so cross-sport coherence can be resolved in batch rather than touching the same rows multiple times.

| Source | Recommendation | Action |
|---|---|---|
| A.2 audit | Add vertical-gain reference to Marathon (Trail) Trail Running primary row notes (e.g., "long run accumulates 30–60% of race-day climb in build/peak") | Edit Sheet 5 R85 (Trail Running primary) notes |
| A.3 audit | Narrow Marathon (Mountain) Downhill Peak high from 18% to 15–16% | Edit Sheet 5 R93 column 10 (Peak_High) |
| A.3 audit | Marathon (Mountain) strength %, mobility % — defer to Q-MF1, Q-MF2 batch resolution | Apply alongside A.6/A.7 close |
| A.1 audit | Verify "Highest LIT ratio" claim vs Mountain Running, Fell Running | Apply alongside Q-MF3 resolution |

---

## Remaining work

### Group A — 4 sports remaining

Suggested pairing (carries from end of v3 thread):
- **Pair 2:** Ultramarathon (Road) + Ultramarathon (Trail) — shared IAU/ITRA literature, Krissy Moehl, CTS ultra coaching materials
- **Pair 3:** Mountain Running / Skyrunning + Fell Running — shared skyrunning/fell coach materials, anchors mountain-family coherence resolution

After Pair 3, apply pending recommendations table above and close Group A.

### Session 5 — own thread (3–4 hrs estimated)

Per Andy's sequencing decision: do Session 5 BEFORE Group B because Triathlon will hit the same sub-format-as-sport-entry pattern.

Scope:
- LDC sub-format expansion: split into 5 sport entries (Road / Gran Fondo, Gravel, TT, XC MTB, Enduro). Updates needed across Sheets 1, 3, 5.
- Off-Road / Adventure Multisport (Non-Nav) verification
- Cross-sport consistency pass (Q8 from v2 handoff): shared disciplines (Trail Running, Road Cycling, Mountain Biking, Strength) should have coherent allocation patterns across sports

### Groups B–E

- Group B: Triathlon family (Sprint, Olympic, 70.3, IM) — needs sub-format expansion if Session 5 establishes that pattern
- Group C: Water sports (Kayak, Canoe, Packraft, SUP, etc.)
- Group D: Snow + skill-hybrid (XC Skiing, Skimo, Modern Pentathlon, etc.)
- Group E: Cycling + cleanup (anything LDC didn't already cover)

---

## Risks and blind spots

**1. AR Taper feasibility patch values aren't sourced.** They're band-aid lifts to achieve sum-to-100. The AR audit session (whenever it lands) must re-derive from sources. The flag text is the marker, but if a downstream consumer reads from xlsx before AR audit happens, they'll be reading lightly-grounded values.

**2. LDC sub-format expansion is the single biggest piece of unfixed structural debt.** Until Session 5 runs, LDC's data has known issues:
   - R96–R100 sum to ~270% (alternatives treated as additive)
   - R99/R100 numeric values are placeholders
   - Schema-level UNIQUE(sport, discipline) implicitly violated by R95–R98 all using D-005
   ETL spec correctly skips PENDING rows but loads R96–R98 with their existing single-row values, which still suffer from the alternatives-as-additive interpretation. **Anyone running validation against LDC during Group A audits will see false positives.** Group A doesn't reference LDC, so this isn't blocking — but flag if it surfaces.

**3. Mountain Running Peak high band 123% (pre-existing).** Wide but feasible. Carry into A.6 audit as a structural question — is it intentional or a band-overflow that should be tightened?

**4. Fell Running Mobility row values are placeholders.** Inserted to fill structural gap. A.7 audit must verify.

**5. Cross-sport pattern decisions ossify.** Whatever sub-format pattern Session 5 establishes for LDC will be the precedent Group B Triathlon follows. If Session 5 chooses poorly, Group B inherits the bad pattern. Session 5 should explicitly evaluate alternative patterns and document the choice.

**6. The audit verification is grounded but not exhaustive.** Each sport entry uses 4–8 sources. Where Tier 1 peer-reviewed data exists, I cite it. Where only Tier 2 coach materials exist, I triangulate across multiple coaches. But for any given audit conclusion, an additional 2–3 hours of source-hunting could surface contradictions. Confidence is "well-supported, not bulletproof."

**7. The audit log entries describe what's defensible, not what's optimal.** "VERIFIED" means the current values fall within the credible band per sources. It does not mean the values are the best choice — that's a more-aggressive claim requiring controlled empirical comparison. For an MVP framework, defensible-within-band is the right bar.

---

## First instructions for next thread

Read these files in order:
1. This handoff (`Phase_Load_Allocation_Handoff_v3.md`)
2. `Phase_Load_Allocation_Audit_Log.md` — focus on A.1, A.2, A.3 entries to internalize the audit format and the cross-sport questions in flight
3. `Sports_Framework_v3.xlsx` — Sheet 5 specifically for the sport(s) you're auditing

Then start with **Pair 2: Ultramarathon (Road) + Ultramarathon (Trail)**.

Working approach:
- Source-grounded verification per sport (Tier 1 priority, Tier 2 acceptable, Tier 3 only with triangulation)
- Run sum-to-100 pre-flight on each sport before sourcing
- 2 sports per thread at full rigor, then handoff to next thread
- Hold pending recommendations in audit log; don't touch xlsx until end of Group A batch (so cross-sport coherence can be resolved together)
- Andy prefers concise/direct, full rigor over speed, honest "this is uncertain" framing over false confidence

If during Pair 2 work you discover the ultras need their own cross-sport coherence resolution (likely — both ultras share trail running, road cross-train, and similar mobility profiles), surface that and add a Q-UF (ultra family) section to this handoff before next handoff.

Final note: Andy is currently doing his own AR training for Pocket Gopher Extreme 2026 (July 17–19). The framework work is parallel to his personal training and uses the same xlsx schemas conceptually but different data files. Don't conflate them.
