# V2 Spec Decisions — Handoff

**Date:** 2026-05-04
**Purpose:** Resolves the three structural decisions that gated v2 drafting per `V2_Spec_Prep_Handoff.md`. With these locked, v2 drafting can begin.

---

## What this session resolved

1. **Decision 1 — Athlete Network section.** Athlete Link entity placement and what it covers.
2. **Decision 2 — Section D status.** Kept, dropped, or refolded.
3. **Decision 3 — §E.7 strength fields and §N residuals.** Placement cleanup.

All three locked. One packaging decision recommended below (renumbering).

---

## Decision 1: Athlete Network section

### Section header & placement

**"Athlete Network"** — Athlete Data group, takes the §N letter slot (post-renumber: §L; see Renumbering section).

Contains one entity: **Athlete Link** (slim).

### Athlete Link entity

| Field | Type | Tier | Notes |
|---|---|---|---|
| Partner Name | Text | 1 | Display name; required even if account is linked |
| Linked Account | FK to user account (optional) | 2 | Consent flow lives in Plan Management spec |
| Relationship Types | Multi-select: Solo Training Partner / Race Teammate | 1 | At least one required |
| Partner-specific Rules | Free text (optional) | 3 | E.g., "limit hikes to 2 hours" |

**Conditional fields when Relationship Type includes Race Teammate:**

| Field | Type | Tier | Notes |
|---|---|---|---|
| Race Event Association | FK to Target Event (1+) | 1 | Per-event; same Athlete Link can cover multiple events |
| Discipline Focus on Team | Multi-select from event's constituent disciplines | 2 | For relay-style events; drives cross-training framing on joint dates |

**Removed from earlier `Athlete_Link_Entity_v2.md` batch:** Role on Team enum (Captain/Navigator/Pacer/Specialist) and Discipline-specific role notes. Replaced by Discipline Focus on Team.

**Not included:** Coach (out of scope — app is the coach), Training Group, Race Crew. See Deferred Items.

### Joint training lives on §L (Locale Schedule), not on Athlete Link

§L expands to host joint-training as overlays. Existing §L overlay fields (Date Range, Active Locale, Constraints) gain joint-training-specific fields:

| Field | Type | Notes |
|---|---|---|
| Joint Training Link | FK to Athlete Link (optional) | When set: this overlay is a joint-training overlay |
| Joint Training Status | Enum: Proposed / Accepted / Declined / Expired | Only when Joint Training Link is set; **declined records preserved** for proposer audit |
| Proposed By | FK to user | Only when Joint Training Link is set |
| Notes from Proposer | Free text (optional) | Only when Joint Training Link is set |
| Source | Enum: Single / Generated-from-Recurring | New on §L; identifies template-generated instances |
| Parent Recurrence | FK to Recurring §L template (optional) | Set when Source = Generated-from-Recurring |

**Storage model:** when User A proposes and User B accepts, two records are created (one per user's §L), linked by a shared joint-training-instance ID. Each user "owns" their own overlay on their own schedule.

**Location reconciliation:** uses existing §L UX. If both athletes' Locale Schedules already match on the date, the Active Locale field auto-resolves. If not, existing "where will you be" prompt asks them to reconcile (one updates locale OR they confirm remote-aligned). **No new field for this** — same UX as logging travel/indoor-only/etc.

### §L constraint flag semantics (existing fields, with v2 explicitness)

| Constraint | Meaning |
|---|---|
| At home only | No leaving residence area; no outdoor sessions; no driving to gym |
| Indoor only | No outdoor sessions; indoor gym is acceptable |
| Short sessions only | Duration ceiling |
| Other | Free text |

### Recurring overlays (sub-entity of §L)

Applies to **all** §L overlay types — self-overlays (e.g., "at home only every other weekend due to childcare") and joint-training overlays equally.

| Field | Type | Notes |
|---|---|---|
| Pattern | Enum: Weekly / Biweekly + Day-of-week multi-select | Monthly and Custom deferred |
| Start Date | Date | |
| End Date | Date (optional) | Null = ongoing |
| Status | Enum: Active / Cancelled | |
| (Inherits all §L overlay fields) | | Locale, constraints, joint training link, proposer notes, etc. |

**Behavior:**

- For joint-training Recurring: invitation/acceptance happens at the template level. On Accept, system generates individual §L instances forward on a rolling window (suggest 8 weeks; finalize with engineering — see Deferred #8).
- Generated instances default to Status = Accepted, Source = Generated-from-Recurring, Parent Recurrence = FK.
- Either party can override a single generated instance (decline a date, change locale for one weekend) without touching the template.
- Cancelling the template halts forward generation; already-generated future instances remain for individual handling.

### §M (Profile Update Triggers) additions for Athlete Network + §L

When v2 §M is written (in Plan Management group, not Athlete Data), add:

- Athlete creates §L overlay (any kind)
- Athlete sets up Recurring §L template
- Recurring template generates new instances (rolling window refresh)
- Athlete overrides a single generated instance
- Athlete cancels Recurring template
- Joint training invitation: proposed / accepted / declined / expired
- Locale-mismatch detected for accepted joint date (prompts reconciliation)
- Athlete adds Athlete Link
- Athlete updates Relationship Types on existing Link
- Athlete adds Race Event Association to existing Link
- Linked party revokes consent (strip linked-data scope; flag link as name-only)
- Athlete removes Athlete Link (soft-delete, retain for plan history)
- Event-end → system prompts athlete for new plan

### Cross-spec note for Plan Management

When a §L overlay has Joint Training Status = Accepted and a Joint Training Link, plan-gen reads each athlete's existing prescription for that date and seeks the alignment most beneficial to all parties given respective phases, terrain access at the resolved locale, and current load. Proposer notes are read as tiebreaker context, not as override instructions.

---

## Decision 2: Section D dropped

### What disappears

§D entirely — Training Target, Constituent Disciplines, Discipline Weighting fields all moved or eliminated.

### Where each concept lands

| Concept | Resolution |
|---|---|
| "Are you training for an event?" | Prefix gate on §I. Yes → fill §I. No → pick Plan Duration. |
| Plan Duration (no-event branch) | New §I field. Enum: 8 / 12 / 16 / 20 / 24 weeks. **Max 24 weeks**; LLM strategy for weeks 13+ deferred (Deferred #1). |
| Constituent Disciplines | Stays on §I per-event (already exists in v1). For non-event athletes, derive from §C.Primary Sport defaults + §C.Secondary Sports. |
| Discipline Weighting | New §C field — single athlete-level set of weights. Defaults pulled from `Sports_Framework_v3.xlsx` → **Phase Load Allocation sheet, midpoint of % range** per discipline. User-adjustable; sum-to-100 validation; zeroed disciplines allowed. |
| Event Format | **No new field.** Sport metadata in Sports Framework declares primary measurement. Existing v1 §I fields (Race Distance + Estimated Duration) cover what athlete enters. AR with cutoff time → athlete enters cutoff as Estimated Duration, with help text. |

### §I additions

| Field | Type | Tier | Notes |
|---|---|---|---|
| Specific event Y/N | Y/N | 1 | Prefix gate |
| Plan Duration | Enum: 8/12/16/20/24 weeks | 1 | Only when Specific event Y/N = No |

Existing v1 §I fields stay. Race Distance + Estimated Duration cover the format question implicitly.

### §C additions

| Field | Type | Tier | Notes |
|---|---|---|---|
| Discipline Weighting | Per-discipline % (slider/numeric, sum=100) | 2 | Defaults from Sports Framework Phase Load Allocation midpoints for athlete's Primary Sport. Editable; validation. |

### §E gating cleanup

§E gating language re-sources from §C.Primary Sport + §C.Secondary Sports + §I.per-event-disciplines (union). Remove any "Constituent Disciplines from D" references.

---

## Decision 3: §E.7 strength fields → §F; §N residuals dispositioned; §N eliminated

### Field moves

| Field | From | To | Notes |
|---|---|---|---|
| Pull-Up Maximum (strict) | §E.7 | §F | General strength benchmark; climbing prereq logic in §E.7 reads from §F |
| Dead Hang Duration | §E.7 | §F | Same |
| Grip Strength | §E.7 | §F | Same |
| Carb Tolerance | §N | (no move) | **Already in §E.1 as Gut Training History.** v1 §N entry is a duplicate the spec author missed. Delete §N's version. |
| Sleep Dep Experience | §N | §J | Conditional collection; trigger remains §I.Estimated Duration > 20 hr |
| AR Team Composition | §N | §N (Athlete Network — Athlete Link) | Per Decision 1 |

### Section result

| Section | After v2 |
|---|---|
| §E.7 | Renamed "Technical Disciplines." Contains: Rock Climbing, Abseiling, Fencing, Shooting experience. |
| §F | Adds Pull-Up, Dead Hang, Grip to existing Plank/Push-up/Squat fields. Drops "don't double-collect" footnote. |
| §J | Adds Sleep Dep Experience (conditional, triggered by §I.Estimated Duration > 20 hr). |
| §N (old) | **Eliminated.** Letter freed for Athlete Network. |

---

## Renumbering — recommendation: (a) Renumber A–L

**Grep result (2026-05-04):** Only `Sports_Framework_Handoff_v2.md` references section letters in cross-docs, and its letter scheme doesn't match v1's anyway (it has "Section J = Locale" and "Section F = Target Race" — an older/different scheme). No other cross-doc (`Training_App_Architecture_Handoff`, `Layer0_ETL_Spec`, `AR_Exercise_Database_Documentation`, `AR_Athlete_Onboarding_Schema`) references letters at all.

**Implication:** renumbering to A–L doesn't break anything that isn't already broken. Sports_Framework_Handoff_v2.md needs an update pass regardless.

**v2 letter scheme (renumbered):**

| Letter | Section | Was in v1 |
|---|---|---|
| A | Athlete Identity | A |
| B | Health Status | B |
| C | Training History & Fitness Baseline | C |
| D | Discipline-Specific Baselines | E |
| E | Strength, Core & Balance Benchmarks | F |
| F | Performance Testing Baselines (Aerobic & Lab) | G |
| G | Schedule & Availability | H |
| H | Target Events | I |
| I | Lifestyle & Recovery | J |
| J | Locales | K |
| K | Locale Schedule | L |
| L | Athlete Network | (new; replaces N) |

Plus §M (Profile Update Triggers) moves to **Plan Management group**, no longer a Section in Athlete Data.

**If renumbering is rejected**, keep gaps (no D, no M, §N = Athlete Network). Defensible but leaves the spec with visible gaps for no benefit since cross-docs don't depend on v1 letters.

**Recommendation: (a) Renumber.** Confirm in next session before drafting begins.

---

## Deferred items log

| # | Item | Notes |
|---|---|---|
| 1 | Plan generation strategy beyond 12 weeks | User-facing Plan Duration max = 24 weeks. Generation strategy for weeks 13+: (a) simpler/cheaper LLM, OR (b) don't generate, leave handoff notes for re-gen as plan progresses. Decide before ship. |
| 2 | Multi-event periodization | v2: athlete-level §C Discipline Weighting wins. Post-launch: revisit if data shows mixed multi-event athletes are common. |
| 3 | Per-event Discipline Weighting override | If multi-event handling is built, per-event override on §I (renumbered §H) becomes the natural mechanism. |
| 4 | AR cutoff time vs. expected duration UX | Help text needed: "If your race has a cutoff time and you don't know your expected finish, enter the cutoff." |
| 5 | Event Format edge cases | Sport metadata declares primary measurement, but mixed-format events may need explicit handling. Defer until evidence of misuse. |
| 6 | Plan-gen Discipline Weighting tunable | Confirm plan-gen surfaces the §C-level weighting as user-adjustable post-onboarding. |
| 7 | Sports Framework gap audit | v2 §C Discipline Weighting reads from Phase Load Allocation. Verify all 18 sports + sub-formats are covered before v2 ship. Fallback: equal weights as default. AR is well-populated; other 17 not yet verified. |
| 8 | Recurring §L generation rolling window length | 8 weeks suggested; finalize with engineering. |
| 9 | Multi-Athlete-Link conflict detection | If athlete has Recurring with one partner on Saturdays and someone else proposes a single Saturday joint date, system should warn. UX/plan-gen behavior, not data field. |
| 10 | Recurring + Race Teammate combo | Race Teammate is per-event; Recurring isn't event-bound. v2 spec writer should make explicit that Recurring attaches to the Athlete Link, not to the Race Event Association. |
| 11 | UX flow for sum-to-100 sliders | Discipline Weighting sliders rebalance on movement; can be fiddly. UX flow design concern. |
| 12 | §J (renumbered §I) section internal complexity | Multiple conditional-collection fields (Sleep Dep, Altitude, Caffeine sub-question, Heat Acclim). v2 writer should design conditional collection consistently across J fields, not field-by-field. |
| 13 | Training Groups | Out of scope. If multi-athlete group dynamics ever become a feature, slots into Athlete Network. |
| 14 | Race crew sharing | Separate one-time link feature; not part of training plan. |
| 15 | Coach mode | Out of scope; app is the coach. Separate workspace if ever shipped. |
| 16 | Linked-account consent flow | Belongs in Plan Management spec. Granularity, revocation mid-plan. |
| 17 | Multi-partner alignment when N>2 | Mechanically handled by N pairwise links + aggregation logic in Plan Management. Spec the aggregation later. |
| 18 | Reschedule flow for joint-training dates | Currently: decline + new invite. Add Cancelled state if pattern emerges. |
| 19 | Fencing and shooting in MVP | Modern Pent + Biathlon are extremely niche. Worth asking whether to defer to post-launch with placeholders. Not a v2 spec blocker. |
| 20 | Event-end transition | System prompts user for new plan when event ends. Plan Management lifecycle concern. |
| 21 | Joint training proposer notes alignment hierarchy | Plan-gen reads each athlete's prescription, seeks alignment beneficial to all, treats proposer notes as tiebreaker. Plan Management owns ranking. |
| 22 | "Skip a recurring instance" UX terminology | Current model: decline that one generated instance. UX may want a "skip" verb separate from "decline." Flag for product. |

---

## Next session agenda

This thread should end. Start a fresh thread for v2 drafting.

**Sequence:**

1. **Confirm renumbering** (a vs. b). Recommendation in this doc is (a). 5 min.
2. **Reconciliation pass** — read all six v2 batch docs end-to-end against v1 + this handoff. Flag contradictions, terminology drift, cross-references that point at fields that shifted. ~30–60 min. Per `V2_Spec_Prep_Handoff` recommendation, this happens before drafting.
3. **Drafting begins** — structural reorg into Athlete Data / Account Configuration / Plan Management groups, then §A (drop gender, add A.1 Disclosures), then §B. One full session for these three. Re-assess pace after.
4. **Subsequent sessions** — proceed through sections in renumbered order. The new §C gets Discipline Weighting; new §D (was §E) gets the slimmed §E.7 (renamed Technical Disciplines); new §E (was §F) gets the migrated strength fields; new §H (was §I) gets the prefix gate + Plan Duration; new §I (was §J) gets Sleep Dep; new §K (was §L) gets the joint-training overlay expansion + Recurring template; new §L (was §N) is Athlete Network.

**Files to read on pickup (in order):**

1. **This document** (`V2_Decisions_Handoff.md`) — authoritative for everything resolved this session
2. `Athlete_Onboarding_Data_Spec_v1.md` — foundational doc
3. `V2_Spec_Prep_Handoff.md` — parent handoff that scoped these decisions
4. `Vocabulary_Audit_v2.md` — controlled vocab
5. `Section_B_v2_Batch.md`
6. `Sections_C_J_v2_Batch.md`
7. `Sections_GHMN_v2_Batch.md`
8. `Adherence_Drop_Spec_v2.md`
9. `Athlete_Link_Entity_v2.md` — **stale** per Decision 1; this handoff supersedes it

**Note on `Athlete_Link_Entity_v2.md`:** that batch doc is now superseded by Decision 1. Specifically: Joint Training Date is no longer a sub-entity (moved to §L overlays), Discipline Focus replaces Role on Team, recurrence is a §L template not an Athlete Link template. v2 writer should treat this handoff as authoritative; don't re-read the batch doc as a source of truth for Athlete Link.

---

## Gut check

**Top risks for the v2 draft session:**

1. **Renumbering decision shouldn't drift.** Recommendation is (a) but Andy hasn't confirmed. Settle in the first 5 min of next session; don't let it linger.

2. **`Athlete_Link_Entity_v2.md` is stale.** Decision 1 changes its shape substantively. v2 writer treats this handoff as authoritative — flag prominently to avoid re-incorporating dead fields (Role on Team, etc.).

3. **Sports Framework gap audit (Deferred #7) is the real dependency.** v2 §C Discipline Weighting assumes Phase Load Allocation covers all 18 sports + sub-formats. Sample showed AR is well-populated; the other 17 are unverified. Audit before v2 ship; fallback is equal weights as default.

4. **§I (renumbered §H) Target Events is becoming the most complex section.** Adds prefix gate, Plan Duration enum, Race Event Association reference from Athlete Link, possible per-event override later. v2 writer should structure §I carefully — sub-headings (H.1 Event mode gate, H.2 Event details, H.3 No-event mode) help.

5. **§L (renumbered §K) Locale Schedule does a lot of conceptual work** — location overrides, constraint flags, joint training, recurrence templates. Right consolidation, but a reader of v2 spec encountering §K will need clear sub-headings (K.1 Self-overlays, K.2 Joint-training overlays, K.3 Recurrence templates) to navigate. Otherwise §K becomes a wall of text.

**What we might be missing:**

- **Generated §L instance audit trail.** When a Recurring template generates instances, then the template is cancelled, then the user manually edits one of the already-generated future instances — does that instance still know its parent template was cancelled? Probably stores the FK to the cancelled template. Worth being explicit in v2.
- **Multi-locale joint training.** What if two athletes both travel to a third locale to train together? Currently Active Locale on the overlay is one of the existing Locales. If the joint locale is new, the athlete adds it as a Locale first. Workable but worth confirming the UX flow handles this gracefully.

**Strongest argument against the package:** all three decisions converge on consolidating fields into fewer, wider sections (§I and §L especially). That's the right tradeoff for data model purity, but the v2 spec's readability depends on whoever drafts it doing strong sub-section structure. If the next thread skimps on hierarchy inside sections, the consolidation backfires — readers can't find what they need. Mitigation: enforce sub-headings (X.1, X.2, X.3) in §C, §I, §L from first draft.
