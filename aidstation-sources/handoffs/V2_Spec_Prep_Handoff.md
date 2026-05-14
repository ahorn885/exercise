# V2 Spec Prep — Handoff Note

**Date:** May 2026
**Status:** Five batch docs and one cross-cutting entity spec produced. v1 confirmation pass complete. v2 spec writing not yet started.
**Pickup files (in /mnt/user-data/outputs at session end):**
- `Vocabulary_Audit_v2.md` (supersedes v1)
- `Section_B_v2_Batch.md`
- `Sections_GHMN_v2_Batch.md`
- `Sections_C_J_v2_Batch.md`
- `Athlete_Link_Entity_v2.md`
- `Adherence_Drop_Spec_v2.md`

---

## What this session accomplished

Picked up from `Vocab_Session_Handoff.md`. Worked through the five-step plan locked at the start of the previous session, completing steps 1–4:

1. ✅ Confirmed Health Conditions merge
2. ✅ Revised Vocabulary Audit (now v2)
3. ✅ Executed Section B fix
4. ✅ v1 confirmation pass on G/H/M/N (and surfaced ripple-on changes to C, J, L, plus the Athlete Link merge and the Adherence Drop spec)

Step 5 (v2 spec writing in batches) is queued for the next session.

---

## Files produced — what each contains, status

| File | Replaces / supersedes | What it covers | Status |
|---|---|---|---|
| `Vocabulary_Audit_v2.md` | `Vocabulary_Audit_v1.md` | 41 canonical body parts, Health Conditions record-type field with 10-category system enum, equipment canonical list with assumed-universal items, 12 sport-specific gear-readiness toggles (XC split into Classic + Skate), col 7 / col 13 cleanup tasks for Layer 0, terrain extraction to col 7b | Locked. Slots into v2 spec as the source-of-truth vocab reference. |
| `Section_B_v2_Batch.md` | v1 §B in entirety | New B field table (Health Conditions replaces Chronic Medical Conditions), B.1 Injury Record adds Injury Type, B.2 canonical body parts, B.3 unchanged, B.4 new Health Condition Record substructure | Locked. Slots into v2 §B. |
| `Sections_GHMN_v2_Batch.md` | v1 §G/H/M/N | G adds Running Threshold Pace; H drops Time-of-Day, promotes Doubles to Tier 1; M expands triggers (Health Conditions, gear readiness toggles, Connected Service effects, adherence drop with N=4) and folds in classification table; N restructures Team Composition as reference to Athlete Link entity | Locked. Slots into v2 §G/H/M/N. |
| `Sections_C_J_v2_Batch.md` | Adds new fields to existing v1 §C and §J | C.2 Pack Load Training History with Pack Training Record substructure (athlete-level, moved from proposed E.1); J.2 race-day fueling preferences (caffeine race-day strategy as sub-question, fueling format preference, GI triggers, salt/electrolyte tolerance) | Locked. Slots into v2 §C and §J. Other fields in C and J unchanged. |
| `Athlete_Link_Entity_v2.md` | v1 §L's inline Training Partner record + proposed §N Team Composition Record | Single merged entity covering both solo training partners and race teammates. Core fields + relationship-type-conditional fields. Referenced from §L (filtered to Solo Training Partner) and §N (filtered to Race Teammate, this event). | Locked. Cross-cutting entity — placement in v2 reorg is itself an open item (see below). |
| `Adherence_Drop_Spec_v2.md` | New — referenced from v2 §M.3 trigger row | Detection logic (4 consecutive flagged sessions, 5 flag types), athlete-facing prompt copy, 8 response branches with opt-in proposal/confirm flow, periodisation context overrides (deload, post-deload, injury, taper), stacking rules with -30% volume cap, re-evaluation cadence, edge cases | Locked at design level. Conversational copy is starting-point only — flagged for product/copy review. |

---

## Decisions made this session — beyond what was in v1

### Section A
No changes this session beyond what was already in `Onboarding_Session_Handoff.md`.

### Section B
- Chronic Medical Conditions + proposed Systemic Constraints merged into single **Health Conditions record-type field**, parallel to Injury Record
- Cognitive/Mental health and Neurological merged into one system category (10 categories total: Cardiac, Respiratory, Endocrine/Metabolic, GI, Neurological/Cognitive, Musculoskeletal, Skin, Thermoregulation, Immune/Autoimmune, Other)
- Injury Type field added to B.1 substructure (9-value enum)
- Canonical body parts (41) applied to B.2

### Section C
- **Pack Load Training History** moved from proposed E.1 (running) to C as athlete-level field
- Implemented as Pack Training Record substructure (most recent long session, typical cadence, lifetime peak, notes)
- Tier 2 default; conditionally Tier 1 for AR / expedition / mountain-marathon target events at plan-gen time

### Section G
- **Running Threshold Pace** added as new field, parallel to FTP and CSS
- Standard test method: 30-min TT, average pace over final 20 min; 5K race pace as proxy
- FIT-fill language preserved at launch (manual upload); Connected Services replacement deferred post-launch
- Section banner copy reflects manual-upload-at-launch posture

### Section H
- **Time-of-Day Preferences dropped** (was Tier 3, low signal)
- **Doubles Feasible promoted to Tier 1** (multi-discipline sports cannot generate viable plan without it)
- Cross-reference paragraph linking H (typical schedule) and L (date overlays) added

### Section J
- **Race-day fueling preferences moved here from proposed Section N race-specific** (resolves handoff Open Item #12)
- Caffeine Tolerance & Strategy field gains race-day sub-question (loaded vs. abstain vs. variable)
- New fields: Fueling Format Preference, Known Race-day GI Triggers, Salt/Electrolyte Tolerance
- Heat Acclimatization History to be dropped in v2 (already in handoff — replaced by system tracking)

### Section M
- **Adherence-drop threshold confirmed at 4 consecutive flagged sessions** (down from initial 5)
- Detection expanded to flag both under-performance AND over-performance (5 flag types)
- Health Conditions lifecycle triggers added
- Gear readiness toggle change triggers added
- Connected Service effect-side triggers added (event-side lives in Account Config)
- Adherence-drop branching extracted to its own spec doc with opt-in confirmation flow
- Soft-warning / hard-gate / profile-prompt classification table folded in (was previously only in Onboarding handoff)
- Saddle endurance soft-warning trigger broadened to all cycling sports >4 hr (was AR-only implied)

### Section N
- **Team Composition Record superseded by merged Athlete Link entity**
- N now thin: Y/N gate ("Competing with team for this event") + filtered reference to Athlete Link
- Removed: race-day fueling (→ J), pack load (→ C), sleep management practiced strategy, night nav experience, chafing history (over-collection — plan night sessions for night-active sports instead of asking)

### Cross-cutting

- **Connected Services confirmed at account level** (Account Configuration in v2 reorg). Section M handles only the athlete-data effect side.
- **Athlete Link entity merge**: at the user level, race teammates and solo training partners are the same conceptual entity. Both reference the same record; relationship type is a sub-field. Plan Management owns the cross-plan sync logic; this entity provides the data.

---

## Outstanding issues / observations (from gut checks across the session)

These are flagged for v2 design or post-launch validation. Not blockers — but worth a deliberate look during v2 spec writing.

### Vocab and equipment
| # | Item | Notes |
|---|---|---|
| 1 | **Climbing—roped / Rappelling overlap** in §4 readiness toggles | Made roped-climbing-passes-rappelling-checks the matching rule. Some athletes (especially AR-only) only abseil and never lead. Worth confirming the auto-pass logic doesn't over-permit. |
| 2 | **Helmet (climbing) — own token vs. implicit** with each toggle | Currently implicit with every relevant toggle. If we ever programme helmet-only exercises (none currently), we'd need a separate token. Defer. |
| 3 | **Touring/AT vs. Alpine ski overlap** | Lumped both into "Touring/AT ski setup" toggle on the assumption that touring kit covers alpine descent. Reverse isn't true. Athletes with only alpine kit can't tour — they'd have to set toggle to N. Acceptable trade-off but flag for v2 review. |
| 4 | **60–100 exercises to update in col 7** for the sport-gear rollup pass | Layer 0 implementation work. Sequence after vocab is fully signed off. |

### Section B
| # | Item | Notes |
|---|---|---|
| 5 | **10-category Health Conditions enum** — is Neurological/Cognitive too broad? | Concussion + ADHD + epilepsy + anxiety all live in one bucket now. Drives column compensates by mentioning each. May want to split if this is unwieldy in plan generation. |
| 6 | **Concussion history path** — Health Condition (Neurological/Cognitive, History) vs. Injury History (head, Resolved) | Made it Health Condition only on the rationale that concussion has systemic/cognitive aftermath beyond a body-part injury. Defensible alternative would be both. Flag for v2 design. |
| 7 | **B.4.2 Auto-population logic** for Health Conditions from medications, allergies, RHR | Deferred — v2 design call. Auto-suggest pattern (athlete confirms before record creation) is the proposed approach. |

### Section G/H/M/N
| # | Item | Notes |
|---|---|---|
| 8 | **Connected Service split adds indirection** | Event-side in Account Config, effect-side in M. Clean conceptually but a developer reading only §M won't see the trigger source. Mitigation: M.2 explicitly names source events. |
| 9 | **Discipline-scoped vs. global adherence-drop trigger** | Spec assumes discipline-scoped where possible (volume drops on running only, not all). Real implementation needs a discipline tag on every prescribed session. Implementation non-trivial. |
| 10 | **14-day mute after adherence-drop branch** may be too long for short-cycle issues | Mild 3-day stress that resolves quickly will still suppress trigger for 14 days. Consider branch-specific mute durations (Sick = 5–10 days, Stressed = 14, Bored = 14, Busy = 14). Defer until adherence data exists. |
| 11 | **4-consecutive vs. 4-of-last-6 threshold** | Spec uses 4 consecutive. One truly off day in the middle (e.g., a holiday) resets the counter. 4-of-6 is more forgiving. Easy to switch later. |

### Athlete Link entity
| # | Item | Notes |
|---|---|---|
| 12 | **Master-definition placement in v2 reorg** | Cross-cutting entity. Could live in Athlete Data (referenced from L and N), or as a top-level entity in a new "Athlete Network" section, or in Account Configuration. Currently undecided — flagged in entity spec Open Item. |
| 13 | **Storage of unlinked-partner data** | If athlete enters partner's age / fitness / injuries on partner's behalf, partner has no awareness. Privacy concern. Recommend conservative default: free text only, no structured fields. Flagged in entity spec. |
| 14 | **Section L update to use merged entity** | Out of scope this session. Needs its own L batch when v2 writing starts. |

### Adherence drop spec
| # | Item | Notes |
|---|---|---|
| 15 | **Conversational copy review** | Proposed copy in §4 is starting-point only. Real copy needs voice review for tone, localisation, accessibility. Flagged in spec Open Item #3. |
| 16 | **Multi-week taper interaction** | 3-week taper for ultra has progressive volume drops that may trigger adherence-drop falsely. Recommend taper context behaves like deload context (suppress or inform). Flagged in spec Open Item #5. |

### Pre-existing items still deferred (unchanged from prior handoffs)

| # | Item | Why still deferred |
|---|---|---|
| 17 | Movement Components on col 9 (Layer 0 enhancement) | Cross-layer; out of vocab scope |
| 18 | Disclosure language copy (replaces Physician Clearance) | Product/legal call |
| 19 | Re-injury risk model — preventive priority boost on resolved injuries | v2 spec design decision |
| 20 | Sheet 7 deprecation timing | Once v2 spec is signed off |
| 21 | Migration path from current app database | Architecture handoff blocker |
| 22 | TA / aid station fallback behaviour | If athlete doesn't know, system tries event URL; if neither, plan defaults conservatively |
| 23 | Layer 1 ↔ Layer 0 query layer concrete spec | After schema is built |
| 24 | Multi-partner consent rules (N>2) | Deferred to team-training spec |
| 25 | Stale-link cleanup for Athlete Links | Deferred to team-training spec |

---

## Closed this session — items resolved

- ✅ #1 (vocab handoff): Vocab self-pass — locked at v2
- ✅ #2: v1 confirmation pass on G/H/M/N done
- ✅ Health Conditions merge confirmed and built (B.4)
- ✅ Sport-specific kit rolled into 12 readiness toggles, XC split into Classic + Skate
- ✅ Adherence-drop threshold (4) and full branching spec built
- ✅ Pack Load Training History placement (Section C)
- ✅ Race-day fueling placement (Section J) — closes prior handoff Open Item #12
- ✅ Heat Acclim Open Item #6 — confirmed dropped (system tracks via weather API)
- ✅ Time-of-Day Preferences Open Item #8 — dropped
- ✅ Pack Load Open Item #7 — built in C
- ✅ Running threshold pace test method canonical — 30-min TT (last 20 min)
- ✅ Connected Services scope — confirmed at account level
- ✅ Team Composition restructure → merged with Training Partner into Athlete Link entity

---

## Next session agenda

**Primary: Write v2 of `Athlete_Onboarding_Data_Spec.md`** integrating all batch docs into one canonical document.

Suggested batch order for v2 writing:
1. **Structural reorg** — apply the three-group split (Athlete Data / Account Configuration / Plan Management). This is the framing that everything else slots into.
2. **Section A** — drop gender identity, add A.1 Disclosures
3. **Section B** — slot in `Section_B_v2_Batch.md`
4. **Section C** — slot in C portion of `Sections_C_J_v2_Batch.md`
5. **Section D and E** — discipline structure questions still unresolved (handoff Open Items #9, #10)
6. **Section F (Target Race)** — apply Onboarding handoff decisions (race fueling fields move out, complications, TAs, aid stations added)
7. **Section G/H** — slot in those parts of `Sections_GHMN_v2_Batch.md`
8. **Section I and J** — slot in J portion of `Sections_C_J_v2_Batch.md`; slot in Onboarding handoff I additions
9. **Section K (Locale)** — apply Onboarding handoff K decisions (geographic model, gym memberships, seasonality)
10. **Section L (Locale Schedule)** — update to reference Athlete Link entity
11. **Athlete Link entity** — place per the §12 outstanding-issue resolution
12. **Section M** — slot in M portion of `Sections_GHMN_v2_Batch.md`; cross-link to `Adherence_Drop_Spec_v2.md`
13. **Section N** — slot in N portion of `Sections_GHMN_v2_Batch.md`

Reassess pace after the structural reorg + Sections A–B are done. The first three batches will set the tone for the rest.

**Secondary (only if time): UX flow design** — wizard structure, FIT-first prompting, conditional sub-section logic, MVP-first plan pathway. Probably gets its own session.

**Out of scope:**
- Team training spec (its own session)
- Per-user database schema (after v2 + UX flow are settled)
- Layer 1 ↔ Layer 0 query layer concrete spec (after schema is built)
- Migration spec (needs current app schema dump first)

---

## Bring to next session

- This handoff doc
- All six output files from this session (listed at top)
- `Athlete_Onboarding_Data_Spec_v1.md`
- `Onboarding_Session_Handoff.md` (still relevant — earlier decisions for sections A, D, E, F, I, K, L not covered in this session's batches)
- `Vocab_Session_Handoff.md` (historical record; mostly superseded but useful context)
- All other existing project files (architecture handoff, sports framework, exercise DB, etc.)
- Current app database schema dump (still wanted — unblocks migration planning)

---

## Final notes / risks

**The strongest argument against where we are:**

We've produced six docs that all need to integrate cleanly into a single v2 spec. There's real risk that integration surfaces inconsistencies — e.g., terminology drift between batches, fields referenced from one batch that shifted in another, tier assignments that conflict. The first hour of v2 writing should be a reconciliation pass: read all batches end-to-end, list contradictions, resolve before writing.

**What we might be missing:**

1. **Section D (Sport & Discipline Selection) and Section E (Discipline-Specific Baselines) didn't get touched this session.** Both have outstanding decisions in the prior handoff (#9 — AR/Multi-sport/Solo distinction; #10 — Movement constraints vs col 9). v2 writing will surface these and they'll need decisions.

2. **The sport-gear rollup is a 60–100 exercise touch in Layer 0.** That's database work, not spec work, but it's a prerequisite for the matching engine to work correctly with v2 vocab. Sequence it after vocab signoff but before any plan generation testing.

3. **Athlete Link entity placement is genuinely undecided.** The v2 reorg has three groups but Athlete Link doesn't fit cleanly in one. Decision needed early in v2 writing because §L and §N both reference it.

4. **Adherence drop spec depends on session-discipline-tagging that may not exist yet.** The discipline-scoped trigger logic assumes prescribed sessions are tagged with their discipline. Verify with engineering before relying on it.

**Pace reflection:**

Last session ran long because v1 was followed by ~30 unfolded refinements. This session ran more cleanly — the work was bounded (confirmation pass + adherence drop) and produced concrete deliverables. v2 spec writing is a bigger lift than this session was; budget at least one full session for the structural reorg + Sections A–B alone, and probably two more for the rest.

Recommend a fresh thread for v2 writing. This thread is at six docs and should not be extended.
