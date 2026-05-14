# V2 Drafting — Handoff (after batch 3)

**Date:** 2026-05-04
**Purpose:** End the current thread cleanly. Hand off batches 4–5 of v2 spec drafting to a fresh thread with the decisions made this session captured.
**Status of v2 spec:** Batches 1–3 complete (structural reorg + §A through §H). Batches 4–5 pending.

---

## What this session accomplished

1. **Confirmed renumbering option (a)** — A–L, no gaps. (Was the gating decision from `V2_spec_decisions_handoff.md`.)
2. **Reconciliation pass** across v1 + the six v2 batch docs + the Decisions Handoff. Output: `V2_Reconciliation_Findings.md`. Identified 5 judgment-required findings and ~15 mechanical-update items.
3. **Drafted batches 1–3** of v2 spec — front matter + structural reorg + §A through §H. Output: `Athlete_Onboarding_Data_Spec_v2.md` (in progress).

---

## Decisions captured during drafting (beyond what was in batches and handoffs)

These are calls made during this session that aren't in any prior batch doc or handoff. Each is documented in the v2 spec where it lands; surfaced here for the next session's awareness.

### §A.1 Disclosures — split between Athlete Data and Account Config

The handoffs were ambiguous on where Disclosures live. Resolved as: **§A.1 specifies what disclosures contain (the slots: account-creation, sex-collection, health-data, HRT, Connected Service consent, linked-partner). Account Configuration stores user acknowledgment state** (timestamp, version, content_hash). A.1 is normative content; Account Config is record-keeping. Six disclosure slots specified; copy itself is product/legal, deferred.

### §C Discipline Weighting — placement and prose

Field added per `V2_spec_decisions_handoff.md` Decision 2. Placed in §C right after Secondary Sports. Defaults from Phase Load Allocation midpoints; sum-to-100; zeroed disciplines allowed. Sports Framework gap (only AR is well-populated; other 17 unverified) flagged inline with equal-weights fallback.

### §D Threshold Pace — single canonical home in §F

v1 had Threshold/Tempo Pace in §E.1 (Running baseline) AND was being asked to add Running Threshold Pace in §F. Same data point, two homes. Resolved as: **single canonical home in §F.** §D.1 keeps Easy Run Pace (different concept — zone 2 anchor, not test-derived). §F has Running Threshold Pace.

### §D Cycling FTP — single canonical home in §F

v1 split FTP weirdly (value in §E.2, test date in §G). v2 puts the full field in §F. §D.2 drops FTP entirely.

### §G Recurring Conflicts — dropped entirely

v1 had "Training Days Available" with a free-text "recurring conflicts" sub-field. Initial v2 plan was to structure it (day + time-window + recurrence + notes). Andy's call: at day-level it's redundant with Training Days Available (deselect a conflicted day). Hour-granularity isn't worth tracking. **Dropped entirely.** Time-of-Day Preferences also dropped (already decided). §G is now five fields plus Doubles Feasible promoted to Tier 1.

### §H Team Format — implicit gate, no separate Y/N

v1 §N had an explicit "Competing with team for this event" Y/N gate that was decided to be eliminated in `V2_spec_decisions_handoff.md` Decision 1. v2 makes it implicit — Team Format = Unified/Relay/Doubles is the gate. Non-Individual values activate §L Athlete Link collection (Race Teammate type, this event as Race Event Association FK). Cleaner than a separate Y/N.

### §H Sleep Deprivation trigger — explicit field collection

v1 said >20 hr "auto-flags sleep deprivation protocol (no separate field)." Per Decisions Handoff Decision 3, v2 adds Sleep Dep Experience field on §I. Made the trigger flow explicit in §H.2: Estimated Duration > 20 hr now triggers conditional field collection on §I, not just an internal flag.

### §J Locale linking — geographic proximity, not city-string

Onboarding handoff §K said "city/region tagging" — but strict city-name breaks at metro boundaries (Austin / Pflugerville / Round Rock = one cluster, three strings). Refined to **lat/long proximity model with default radius (~30–40 mi suggested, finalize in batch 4) and manual link/unlink override**. Captured in §J stub for batch 4 to draft fully.

---

## Drafting status

| Section / Group | Status | Notes |
|---|---|---|
| Front matter, structural reorg, Connected Services convention | ✅ Drafted | Batch 1 |
| §A Athlete Identity + A.1 Disclosures | ✅ Drafted | Batch 1 |
| §B Health Status (full: B, B.1, B.1.1, B.2, B.3, B.4, B.4.1, B.4.2) | ✅ Drafted | Batch 1 |
| §C Training History & Fitness Baseline (incl. C.1 Pack Training Record) | ✅ Drafted | Batch 2 |
| §D Discipline-Specific Baselines (D.1–D.7) | ✅ Drafted | Batch 2 |
| §E Strength, Core & Balance Benchmarks | ✅ Drafted | Batch 2 |
| §F Performance Testing Baselines | ✅ Drafted | Batch 3 |
| §G Schedule & Availability | ✅ Drafted | Batch 3 |
| §H Target Events (H.1, H.2, H.3) | ✅ Drafted | Batch 3 |
| §I Lifestyle & Recovery | ⏳ Pending | Batch 4 |
| §J Locales (geographic proximity model) | ⏳ Pending | Batch 4 — locale linking decision locked in stub |
| §K Locale Schedule (joint-training overlays + recurrence) | ⏳ Pending | Batch 4 |
| §L Athlete Network | ⏳ Pending | Batch 5 — drafted from Decisions Handoff alone |
| Group 2 — Account Configuration | ⏳ Pending | Batch 5 |
| Group 3 — Plan Management | ⏳ Pending | Batch 5+ |

Spec doc is currently 622 lines. Batches 4–5 will likely add 300–500 lines (§J alone is the longest single v1 section).

---

## Next session agenda

### Batch 4 — §I, §J, §K (one full session)

**§I Lifestyle & Recovery** (was v1 §J):
- Slot in v1 §J fields minus Heat Acclimatization History (dropped — system-tracked in Plan Management)
- Add `Sections_C_J_v2_Batch.md` §J.2 race-day fueling fields: Caffeine Race-Day Strategy (sub-question on existing Caffeine Tolerance & Strategy field), Fueling Format Preference, Known Race-day GI Triggers, Salt/Electrolyte Tolerance
- Add Sleep Deprivation Experience (per Decisions Handoff Decision 3 — conditional collection triggered by §H Estimated Duration > 20 hr)
- Section banner clarifying athlete-level vs event-level scope

**§J Locales** (was v1 §K) — biggest single section:
- Locale-level fields with geographic proximity model (locked in stub — finalize default radius and manual override UX)
- J.1 Locale fields (drop v1's Linked Primary Locale FK; add lat/long; add Gym Chain field per Onboarding handoff)
- J.2 Equipment Inventory (apply Vocabulary_Audit_v2 §3 canonical equipment list — additions, removals, renames; add Bench, Foam pad, Incline board; drop Jacob's Ladder, Compression boots, Sauna, Stretch strap)
- J.3 Sport-Specific Gear Readiness Toggles (replace v1 sub-component checklists with the 12 rolled-up toggles per Vocabulary_Audit_v2 §4)
- J.4 Terrain Access (carries forward; confirm seasonality is hybrid — climate-derived defaults + per-month override)
- J.5 Locale Capacity Metrics (carries forward)

**§K Locale Schedule** (was v1 §L) — needs the joint-training expansion from Decisions Handoff:
- v1 §L date-range overlay fields carry forward (Active Locale, Date-Specific Constraints — multi-select per Onboarding handoff: At home only / Indoor only / Short sessions only / Other)
- Drop v1's inline "Training Partner record" — replaced by reference to §L Athlete Network entity
- Add joint-training overlay fields per Decisions Handoff Decision 1: Joint Training Link FK, Joint Training Status, Proposed By, Notes from Proposer, Source enum, Parent Recurrence FK
- Add Recurring overlay sub-entity per Decisions Handoff: Pattern (Weekly/Biweekly + Day-of-week multi-select), Start/End Date, Status, inherited overlay fields. Applies to all overlay types (self and joint)
- Sub-headings per Decisions Handoff Risk #5: K.1 Self-overlays, K.2 Joint-training overlays, K.3 Recurrence templates

### Batch 5 — §L Athlete Network + Account Config + Plan Management (one full session, possibly two)

**§L Athlete Network** — drafted from `V2_spec_decisions_handoff.md` Decision 1 alone (no batch doc; deleted `Athlete_Link_Entity_v2.md` is stale and not to be re-read):
- Athlete Link entity (slim): Partner Name, Linked Account FK, Relationship Types (Solo Training Partner / Race Teammate, multi-select), Partner-specific Rules
- Conditional fields when Race Teammate selected: Race Event Association FK (1+ to §H events), Discipline Focus on Team

**Group 2 — Account Configuration:**
- Connected Services entity (per service: Service Name, OAuth/API key, Status, Last Sync, Scopes Granted; launch tier Garmin/Strava/Apple Health)
- Gym Memberships (Chain, Membership Active Y/N — drives city-aware gym surfacing in §J)
- Disclosure Acknowledgment Records (storage backing for §A.1 disclosures)
- Privacy / Linked-partner sharing settings (per §L Athlete Link consent scope)

**Group 3 — Plan Management:**
- Profile Update Triggers (slot in `Sections_GHMN_v2_Batch.md` §M.1–M.4 content)
- Adherence Drop (cross-ref to `Adherence_Drop_Spec_v2.md`)
- Plan Duration / Event Prefix routing logic
- Joint Training Generation (rolling-window forward instance generation from §K Recurring templates — 8 weeks suggested, finalize with engineering)
- System-Tracked Heat Acclimatization (workout date + location + weather API derivation)
- Multi-athlete plan sync (out of scope for first v2 publish — flag for team-training spec session)

---

## Files for pickup (in order)

1. **`V2_spec_decisions_handoff.md`** — authoritative for the three locked decisions (Athlete Network section, §D drop, §E.7 strength field migration). Read first.
2. **This handoff** (`V2_Drafting_Handoff_post_batch3.md`) — picks up where session 1 of v2 drafting ended.
3. **`Athlete_Onboarding_Data_Spec_v2.md`** — partial draft. Batches 1–3 complete; §I, §J, §K, §L stubs are the work-to-do.
4. **`V2_Reconciliation_Findings.md`** — the reconciliation pass output. Most findings already absorbed into batches 1–3, but §I/§J/§K reconciliation items are still relevant for batch 4.
5. **`Onboarding_Session_Handoff.md`** — needed for §I, §J, §K decisions not in v2 batch docs (esp. §J geographic model, §K date constraints enum).
6. **`Sections_C_J_v2_Batch.md`** — §J.2 race-day fueling fields for §I drafting.
7. **`Sections_GHMN_v2_Batch.md`** — §M.1–M.4 content for Plan Management group in batch 5.
8. **`Adherence_Drop_Spec_v2.md`** — cross-referenced from Plan Management group in batch 5.
9. **`Vocabulary_Audit_v2.md`** — §3 (equipment) and §4 (12 toggles) for §J Equipment Inventory and Gear Readiness drafting.
10. **`Athlete_Onboarding_Data_Spec_v1.md`** — for §J Locales (longest single section), §K Locale Schedule, and §I Lifestyle existing field text.

Optional context (not blockers):
- `V2_Spec_Prep_Handoff.md` — historical record; superseded by V2_spec_decisions_handoff for the three locked decisions.
- `Vocab_Session_Handoff.md` — predecessor to Vocabulary_Audit_v2; reference only.

---

## Open items still tracked

Carried forward from v2 spec doc Open Items + new ones surfaced this session.

| # | Item | Source / status |
|---|---|---|
| 1 | Disclosure copy (§A.1, six slots) | Product/legal; pre-launch blocker |
| 2 | Movement Components structured field on exercise DB col 9 | Layer 0 enhancement; cross-layer |
| 3 | Re-injury risk model (preventive priority on Resolved injuries) | v2 design call |
| 4 | Sheet 7 deprecation timing | Once v2 signed off |
| 5 | Migration path from current app database | Architecture handoff blocker; needs schema dump |
| 6 | Layer 1 ↔ Layer 0 query layer concrete spec | After v2 schema is built |
| 7 | Health Condition auto-population logic (§B.4.2) | v2 design |
| 8 | Sports Framework gap audit (Phase Load Allocation for all 18 sports) | Pre-launch; equal-weights fallback |
| 9 | Plan Duration weeks 13+ generation strategy | Pre-launch decision |
| 10 | §J Locale proximity radius default | Batch 4 drafting call |
| 11 | §J Locale manual link/unlink UX | Batch 4 drafting call |
| 12 | §K Recurring overlay rolling-window length (~8 weeks) | Engineering finalization |
| 13 | TA / aid station fallback behaviour | Plan-gen rule |
| 14 | Multi-partner consent rules (N>2) | Team-training spec |
| 15 | Stale-link cleanup for Athlete Links | Team-training spec |
| 16 | Coach mode | Out of scope |
| 17 | Linked-account consent flow | Plan Management spec |
| 18 | Sports_Framework_Handoff_v2 deprecation banner | Whoever owns the framework doc — flag for them |

---

## Gut check

**What we got right this session:**

The reconciliation pass paid off. The five judgment-required items it flagged (Decision-3 moves not in batches, Decision-2 additions not in batches, Athlete Network section absent, adherence threshold typo, Onboarding_Session_Handoff missing from pickup list) were all real and would have been missed in straight drafting. The drafting that followed went smoothly because the structural decisions were settled before writing started.

**Top risks for batches 4–5:**

1. **§J Locales is the densest section in the spec.** v1 §K has K.1 through K.5 with deep equipment/terrain detail. Combining the geographic proximity refactor with the equipment vocab rollup (12 toggles) and the terrain seasonality (per-month, hybrid defaults) is real work. Budget ≥60% of batch 4 on §J alone.

2. **§K joint-training overlays + Recurring template** is original drafting from the Decisions Handoff alone — no batch doc to slot in. Sub-heading discipline (K.1/K.2/K.3) is essential or §K becomes a wall of text. Decisions Handoff Risk #5 already flagged this.

3. **§L Athlete Network is also original drafting** from Decisions Handoff alone. Slim entity; should be ~30–40 lines of spec. The risk is over-specifying it (re-incorporating dead fields from the deleted batch doc that the Decisions Handoff superseded). v2 writer should treat Decisions Handoff Decision 1 as canonical and not look at any other source.

4. **Plan Management group has the most undefined surface area.** Profile Update Triggers, joint-training generation, multi-athlete plan sync, system-tracked heat acclim — these are all gestured at but not specced. Batch 5 should commit to drafting the Profile Update Triggers cleanly (it's well-sourced from Sections_GHMN §M); the rest can be stubbed with clear "TBD per [downstream spec]" markers.

**What we might be missing:**

- **The v1→v2 migration path.** This spec is being written as if there are no existing users. Open Item #5 flags it. The v2 writer should add a "Migration considerations" appendix at the end of the spec, even if it's just a list of fields that need explicit migration logic (renamed fields, dropped fields, structural moves).
- **Spec self-test / example athlete profiles.** v1 To-Do mentioned drafting test athletes. Worth doing alongside batch 5 — concrete examples surface gaps faster than re-reading the spec.
- **Cross-doc consistency check after batch 5.** The reconciliation pass at the start of this session was against pre-v2 batches. After batches 4–5 land, a parallel reconciliation pass against the v2 spec body itself is worth doing before signoff.

**Strongest argument against where we are:**

The v2 spec is becoming a long document. 622 lines after batch 3 and likely 900–1100 lines after batch 5. That's the right outcome for a canonical reference spec, but it's hostile to a first-time reader. Mitigation: the three-group reorg helps, sub-headings within §H/§J/§K help, and the front-matter "what changed vs v1" table is the orienting layer for someone diffing v1 to v2. Worth a final pass after batch 5 to add a reading-order recommendation for different audiences (engineers building schema; product designing UX; coaches reviewing logic).

---

## Recommended approach for next thread

Start the new thread with this handoff plus the three core docs (V2 spec decisions handoff, current v2 spec draft, reconciliation findings). Read those three first. Then pull in the section-specific sources as each section is drafted, not all upfront — keeps context manageable.

Batch 4 is one full session. Reassess pace after §J lands; if it eats more than half the session, defer §K to a separate batch and split batch 4 into 4a (§I + §J) and 4b (§K).
