# Handoff — Reconciliation Closed / §J §K §L Integration Kickoff

**Date:** 2026-05-11
**Outgoing session:** Drift audit + Layer 2D/2E bookkeeping reconciliation; D-27→D-35 research; §J/§K/§L scope discovery + design decisions
**Next session:** §J/§K/§L review-and-integrate — merge existing batch drafts into `Athlete_Onboarding_Data_Spec_v2.md`, apply 4 deltas, update Control_Spec

---

## TL;DR

1. Layer 2D/2E bookkeeping reconciliation is **closed**. `Project_Backlog.md` and `Control_Spec.md` have been updated and uploaded; stale `Layer0_Drift_Backlog.md` deleted.
2. **Memory rules #9 (session-start verification) and #10 (session-end verification — companion)** are in effect. Verify on disk; never write a handoff claiming an edit landed unless it actually did.
3. **Scope discovery this session:** §J, §K, §L are substantively drafted in `Sections_IJKL_Groups23_v2_Batch.md` but not merged into the canonical onboarding spec. Option B is **review-and-integrate**, not draft-from-scratch.
4. **Four deltas to apply** during integration are locked below. Zero open design decisions for the next session.

---

## Work completed this session

### Drift audit (session-start rule)
Spot-checked 2E handoff's claimed file updates against on-disk state. Found:
- `Layer2E_Spec.md` (1324 lines) — real, landed ✓
- `Control_Spec.md` updates (§2/§3/§4/§7/§8.2/§9) — **not landed**, frozen at post-2C state
- `Project_Backlog.md` updates (D-21→D-35, FC-1 scope, LEA/RED-S wont-fix) — **not landed**, stopped at D-17

Pattern: the 2D-Done handoff claimed reconciliation that never landed; the 2E-Done handoff inherited that as "already reconciled" and added its own claims, also undocumented. Two layers of drift. Memory rule #10 added to prevent recurrence.

### Reconciliation
Updated both bookkeeping files to current reality:
- **`Project_Backlog.md`** — added D-21 through D-35 (15 items: D-21-D-26 from 2D session, D-27-D-35 from 2E session); FC-1 scope updated with D-22/D-23/D-26 promotions + FC-1a/FC-1b split contingency; LEA/RED-S explicit wont-fix; numbering gap (D-18/19/20) documented
- **`Control_Spec.md`** — §2 (2D/2E drafted status), §3 (2E inputs row corrected — §F nutrition prefs removed, §B + §I + Plan Management state added), §4 (partial-update table rebuilt with §I row + §B trigger expansion + §H.2 broken into terrain/duration/restrictions + new Plan Management state-change table), §7 (2D/2E HITL triggers named), §8.2 (D-21 reconciliation rule added), §9 (doc map updated with §I honest status + Supplement_Vocabulary_Spec + Section_I_Audit + 2D/2E drafted)

Both files uploaded by Andy. Stale `Layer0_Drift_Backlog.md` deleted from project.

### D-27 → D-35 research
Searched 6 prior chats back to 2026-05-09. Confirmed:
- **D-21–D-26**: explicitly enumerated in the 2D session (2026-05-10 / chat a7f5ba3a) with full descriptions; reconstruction matched original work
- **D-27–D-35**: **never enumerated individually in any prior chat or doc**. Only committed to as a topic cluster in the 2E handoff narrative. The current Project_Backlog entries are this session's best-effort interpretation against `Layer2E_Spec.md` §12 (open items 2E-1 through 2E-16). Per Andy's call this session: accepted as-is, reconciliation closed.

### §J/§K/§L scope discovery
Searched for existing §J/§K/§L draft material. Found `Sections_IJKL_Groups23_v2_Batch.md` has substantive drafts for all three sections (lines 76–270). These were never merged into `Athlete_Onboarding_Data_Spec_v2.md` (where §I/§J/§K/§L still show DRAFTING PENDING placeholders).

This reframes Option B: not "draft three sections from scratch" but "review existing batch drafts, reconcile against locked decisions, identify gaps, merge."

---

## Locked decisions for §J §K §L integration

### Already matched in the batch — confirm during integration

| Decision | Batch location | Status |
|---|---|---|
| §J equipment references `equipment_items.canonical_name` | J.2 | Already drafted ✓ |
| Each locale has terrain set via `terrain_types.canonical_name` | J.4 Terrain Access | Already drafted ✓ |
| Cluster proximity at **26.2 mi / 42.2 km** with manual link/unlink override | J.1 proximity model | Already drafted ✓ — Andy confirmed |
| Resolve every day from pattern (not pattern + exceptions) | K.3 Recurrence templates | Already drafted ✓ |
| One location per day, no mid-day travel | K.1/K.2/K.3 single Active Locale field | Already drafted ✓ |
| §L drives plan adjustments (not coaching tone only) | L.1 Partner-specific Rules + L.2 team ceiling logic | Already drafted ✓ |

### New deltas to apply

**Δ-1: J.2 weight range sub-field**
- Scope: **variable-weight equipment only** (dumbbells, kettlebells, plate sets, resistance bands; final curated list during integration)
- Schema: **flat fields**
  - `weight_min_kg` (required when sub-field present)
  - `weight_max_kg` (required when sub-field present)
  - `increment_kg` (optional)
- Universally optional on every J.2 entry; populated only for variable-weight items in the curated list

**Δ-2: K.1 Date-Specific Constraints enum extension**
- Current enum: `At home only / Indoor only / Short sessions only / Other`
- Add: **`Exclude specific locale(s)`** — multi-select sub-field referencing FK to locale(s) being excluded that day
- Rationale: covers "specific gym closed today" case which the current enum can't structure

**Δ-3: Drop §J.5 entirely**
- Andy: "I don't think this needs to be tracked"
- Locale Capacity Metrics (Typical session time / Max session duration) removed from §J
- Confirm during integration that nothing downstream (2B, 2C, Layer 4) was relying on J.5

**Δ-4: Icebox L.2 Role on Team for post-launch consideration**
- Add to Project_Backlog as **D-36** with explicit post-launch status (⚪ Wont-Fix for v1, with reason)
- Note that AR Navigator role has distinct training implications (navigation prep, mental load) — relevant for AR athletes specifically
- Per Andy this session: do not track for v1; revisit post-launch only if evidence of need emerges

---

## Files to update in next session

| File | What changes |
|---|---|
| `Athlete_Onboarding_Data_Spec_v2.md` | Replace §J/§K/§L DRAFTING PENDING placeholders with merged batch content + 4 deltas |
| `Control_Spec.md` §3 inputs table | Verify 2B / 2C input rows match actual §J shape (terrain set, equipment canonical refs); add §K + §L rows for downstream consumers if not present |
| `Control_Spec.md` §4 partial-update model | Audit existing §J/§K/§L rows; verify they reflect integrated structure |
| `Control_Spec.md` §9 doc map | Flip §J/§K/§L to drafted; cross-reference batch source |
| `Project_Backlog.md` | Add **D-36** (Role on Team icebox); raise any gap items if 2B/2C assumed shapes don't match final §J |

---

## Pre-work reading order

1. **`Sections_IJKL_Groups23_v2_Batch.md`** — full read, lines 76–270 are §J/§K/§L
2. **`Athlete_Onboarding_Data_Spec_v2.md`** §J/§K/§L — current DRAFTING PENDING placeholders, to know what's being replaced
3. **`Layer2C_Spec.md`** §3 + §5 — what 2C assumed about §J equipment + gear toggle shape
4. **`Layer2B_Spec.md`** §3 + §5 — what 2B assumed about §J locale terrain shape
5. **`Vocabulary_Audit_v2.md`** §3 (equipment canonical list: 121 items, 17 categories) + §4 (12 gear toggle canonical names)
6. **`Athlete_Onboarding_Data_Spec_v2_INTEGRATION_BLOCK.md`** §J/§K/§L — predecessor material; may have context the batch file consolidated. Check for divergence.

---

## What NOT to do prematurely

- Draft §J/§K/§L from scratch — batch drafts are the starting point
- Relitigate locked decisions (26.2 mi cluster, single locale per day, no mid-day travel, drop J.5, icebox Role on Team)
- Extend the K.1 constraint enum beyond Δ-2 without clear evidence
- Start FC-1 work — still pending after §J/§K/§L
- Start Layer 3 design — strictly post-§J/§K/§L + post-FC-1 + post-FC-2

---

## Critical context

**Standing rules (Control_Spec §5, §8.2):**
- Query node vs. prompt node test: structured inputs + deterministic rules = query node
- D-05 aggregator filter (`AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`) mandatory in every query touching `phase_load_allocation`
- D-17 sub-format / top-level naming logic: 2A's strip pattern
- D-21 reconciliation: 2D/2E match on enum values not column names
- 14-section spec template at `Layer2C_Spec.md` depth (Layer 1 sections follow their own format)
- Update Control_Spec §9 doc map at end of every spec change
- Update Project_Backlog between sessions; promote 🟡 → 🔴 if next node's scope intersects

**Memory rules in effect:**
- #9 — Session-start verification: spot-check prior handoff's claimed file updates against on-disk state; reconcile gaps before continuing
- #10 — Session-end verification (companion): don't write a handoff claiming an edit landed unless the edit is actually in the file

**Andy's preferences (userPreferences):**
- Direct, no praise/hype/filler
- Match confidence to reality; flag tradeoffs
- End plans with quick gut check (risks, blind spots, best argument against)
- Flag long/messy chats for handoff

**Andy is the test athlete** for PGE 2026 (July 17–19, 48–56 hr expedition AR). Active wrist injury (Chronic-Managed, Left wrist).

**Spec-first philosophy.** Architecture → prompts → implementation. FC-1 / FC-2 land at end of Layer 2 design before Layer 3 design starts.

---

## State of files in project as of this handoff

| File | Status |
|---|---|
| `Control_Spec.md` | ✅ Current (reconciled this session) |
| `Project_Backlog.md` | ✅ Current (D-35 latest; D-36 pending in next session) |
| `Layer2A_Spec.md` through `Layer2E_Spec.md` | ✅ All drafted |
| `Supplement_Vocabulary_Spec.md` | ✅ Drafted (FC-1 implementation pending — D-26) |
| `Section_I_Audit.md` | ✅ Drafted |
| `Athlete_Onboarding_Data_Spec_v2.md` | ⏳ Partial — §A-C/G-H/M/N drafted; **§I/§J/§K/§L still DRAFTING PENDING** despite batch material existing |
| `Sections_IJKL_Groups23_v2_Batch.md` | ✅ Source material for next session |
| `Layer0_Drift_Backlog.md` | ✅ Deleted (stale predecessor) |
| `Layer0_ETL_Spec_v3.md` | ✅ Current (v4 pending FC-2) |
| `Layer0_Deployed_Schema_and_Drift_Report.md` | ✅ Current |

---

## Open items requiring Andy decision before or during next session

| # | Item | When |
|---|---|---|
| 1 | Final curated list of variable-weight equipment items for Δ-1 (J.2 weight range sub-field) | Propose during integration; Andy approves |
| 2 | Any gap items raised if 2B/2C assumed §J shape diverges from integrated §J | Surface inline if found |

All design-level decisions are locked. Integration session opens to zero litigation.

---

## Gut check

**What this handoff gets right:**
- Locked the scope reframe (review-and-integrate, not draft-from-scratch). Saves the next session from re-discovering this.
- Four deltas are concrete and self-contained — Δ-1 through Δ-4 are mechanically applicable without further design.
- Memory rules #9 + #10 now form a closed loop on the drift problem.

**Risks:**
- The batch material in `Sections_IJKL_Groups23_v2_Batch.md` may have decisions baked in that conflict with locked decisions discovered this session. The integration session needs to actively check, not blindly merge.
- §I/§J/§K/§L are all "DRAFTING PENDING" in the canonical spec but §I has a committed input contract via `Layer2E_Spec.md` §3 + `Section_I_Audit.md`. §I might need its own integration pass (separate from §J/§K/§L) if the batch material doesn't fully match what Layer2E expects.
- Dropping J.5 (Δ-3) — Andy hasn't verified that 2C/2B aren't relying on session-length info from J.5. Should be a quick check during integration; could promote to a real gap if found.

**What might be missing:**
- §K Joint Training (K.2) and §K Recurrence templates (K.3) intersect with §L Athlete Link records. The integration should verify the cross-references work consistently — partner FKs from K.2 should resolve to L.1 records, etc.
- The dropped §J.5 might leave a real coverage gap if any locale has hard time constraints. Worth checking that K.1's `Short sessions only` constraint adequately covers all session-length signaling needs.

**Best argument against the plan:**
The session-start rule has now caught two consecutive handoffs of drift. If this handoff itself drifts (e.g., the next session reads it, applies the 4 deltas, but skips one of the Control_Spec updates), the rule still works — but the failure mode keeps repeating. Worth Andy thinking about whether there's a structural fix beyond the verify rule. One option: handoffs include explicit "file diff to apply" sections that future sessions execute mechanically rather than narratively.

---

*End of handoff. Next session: open this doc, read the 6 pre-work files, apply Δ-1 through Δ-4 to the batch material, merge into canonical spec, update Control_Spec accordingly, add D-36 to Project_Backlog.*
