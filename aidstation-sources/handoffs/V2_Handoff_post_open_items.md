# V2 — Handoff (after open items review)

**Date:** 2026-05-05
**Purpose:** Hand off to a fresh thread after the open items review session. Captures the 18 resolutions, their integration targets, and recommends ordering for batch 4 + the Phase Load Allocation audit.
**Status of v2 spec:** Batches 1–3 still the latest drafted content (structural reorg + §A through §H). Batches 4–5 still pending. Open Items table cleaned up; placeholder disclosure copy added; sister handoff doc (Sports Framework) deprecated.

---

## What this session accomplished

1. **Walked the 18 open items** from `V2_Drafting_Handoff_post_batch3.md`. Every item resolved — full list in §A.1 of this doc and in the **Resolved decisions log** at the bottom of `Athlete_Onboarding_Data_Spec_v2.md`.
2. **Executed three edits in-thread** rather than deferring:
   - Drafted six placeholder disclosure blurbs under new §A.1.1 of the spec (flagged "PLACEHOLDER — refine with product/legal").
   - Added a deprecation banner to `Sports_Framework_Handoff_v2.md`. The xlsx it describes is still active; the handoff doc is now superseded as primary reference for athlete-facing fields.
   - Rewrote the Open Items table in the v2 spec — collapsed from 15 items to 7 genuinely-open ones, with a new "Resolved decisions log" capturing all 18 decisions and per-item integration targets.
3. **Did not draft any new spec sections.** No batch 4 progress.

---

## Files updated this session (need swap-in to project)

| File | Change |
|---|---|
| `Athlete_Onboarding_Data_Spec_v2.md` | §A.1.1 placeholder copy added; status line updated; Open Items table replaced with trimmed list + resolved decisions log. 634 → 702 lines |
| `Sports_Framework_Handoff_v2.md` | Deprecation banner inserted at top; status line updated. ~510 lines |

Both are in `/mnt/user-data/outputs/` from the prior session — replace the project copies before the next thread starts, otherwise the new thread will read stale Open Items.

---

## A.1 Decisions made (consolidated)

Full table is in the Resolved decisions log at the bottom of the v2 spec. This is the per-item summary plus where each lands.

### Closed (no further work)

| # | Item | Decision |
|---|---|---|
| 2 | Movement Components on exercise DB col 9 | Keep free text; no structural change |
| 16 | Coach mode | Out of scope; the app is the coach. Removed from Open Items |
| 18 | Sports_Framework_Handoff_v2 deprecation banner | Done this session |

### Resolved with placeholder; still tracked as open for completion

| # | Item | Decision | Status |
|---|---|---|---|
| 1 | Disclosure copy | Six placeholder blurbs drafted; refine with legal pre-launch | Open Item #1 (legal review) |
| 4 | Sheet 7 deprecation timing | Mark superseded post-v2 signoff | Open Item #5 (mechanical action) |

### Decided — needs spec body integration in upcoming batches

| # | Item | Decision | Integration target |
|---|---|---|---|
| 3 | Re-injury risk model | Walk Status History; if ever Chronic-Managed or Structural-Permanent → permanent preventive priority post-resolution. Otherwise 12-month decay then neutral | §B re-injury rule note + Plan Management filter logic |
| 7 | Health Condition auto-population (§B.4.2) | Ship all three named rules at launch (anaphylaxis → GI/Immune; condition-specific meds → matching system category; RHR outliers → Cardiac with athlete-bradycardia caveat) | §B.4.2 — promote from "deferred" to "launch behaviour" |
| 9 | Plan Duration weeks 13+ generation | Split-model: stronger LLM weeks 1–12, cheaper LLM weeks 13+ | §H Plan Duration note + Plan Management spec |
| 10 | §J Locale proximity radius default | 26.2 mi (km users: 42.2 km) | Batch 4 §J |
| 11 | §J Locale manual link/unlink UX | Two buttons per locale: "Link to existing locale" picker + "Unlink from group" | Batch 4 §J |
| 12 | §K Recurring overlay rolling-window length | Match Plan Duration (8 / 12 / 16 / 20 / 24 weeks) | Batch 4 §K |
| 13 | TA / aid station fallback | Conservative default (assume sparse aid; full self-sustainment for max segment) | Plan Management spec; cross-ref §H Number of Aid Stations |
| 14 | Multi-partner consent (N>2) | Partial-link: link forms; non-consenters see nothing. Full UX deferred to team-training spec | Batch 5 §L; tracked in Open Item #6 |
| 15 | Stale-link cleanup | Never auto-archive; manual user action only. Team-training spec to confirm | Batch 5 §L; tracked in Open Item #7 |
| 17 | Linked-account consent flow | Each athlete owns own plan; joint sessions appear on both with shared metadata; either can decline a proposed joint session | Batch 5 Plan Management |

### Deferred — no work this round

| # | Item | Reason |
|---|---|---|
| 5 | Migration path from current app database | Sequenced: finish v2 rewrite first, then schema dump, then migration |
| 6 | Layer 1 ↔ Layer 0 query layer concrete spec | After v2 schema is built |

### Active work — committed, multi-session

| # | Item | Decision |
|---|---|---|
| 8 | Sports Framework Phase Load Allocation audit | Full pre-launch audit, all 17 unverified sports. 30–60 min per sport ≈ 9–18 hrs of focused work. Track in dedicated audit thread(s); ~3–4 sports per session |

---

## Next session agenda — two parallel tracks

After this session, there are two workstreams. They don't block each other.

### Track A — Batch 4 spec drafting

**§I Lifestyle & Recovery, §J Locales, §K Locale Schedule.** Per `V2_Drafting_Handoff_post_batch3.md` agenda, with these decisions baked in from this session:

- §J: 26.2 mi default radius; two-button manual link/unlink UX (decisions #10, #11)
- §K: rolling-window matches Plan Duration (decision #12)
- §I: ship the three Health Condition auto-suggest rules at launch — promote §B.4.2 from "deferred" to "launch behaviour" while we're in the area (decision #7); also add the re-injury rule note for §B per decision #3

Recommendation from prior handoff still stands: split into 4a (§I + §J) and 4b (§K) if §J eats more than half the session.

### Track B — Phase Load Allocation audit

Andy committed to full pre-launch audit (decision #8). Three-step approach:

1. **Scope confirmation session** (~30 min). Read `Sports_Framework_v3.xlsx` Phase Load Allocation sheet. Confirm AR's structure (Base/Build/Peak/Taper × discipline %). Inventory the 17 unverified sports. Pick a per-session batch size (recommend 3–4 sports).
2. **Audit sessions** (4–5 sessions × 3–4 sports each). Per sport: review training literature, derive Phase Load Allocation midpoints with ranges, document reasoning in a side doc, update xlsx.
3. **§C re-touch session.** After audit lands, the Discipline Weighting defaults footnote in §C currently says "AR is well-populated; the other 17 are unverified pre-launch. Fallback equal weights." Update once audit is done.

### Recommended ordering

Run them in parallel, in separate threads. They don't read the same files heavily.

If forced to sequence: **Track A first, Track B second.** Reason: batch 4 plus batch 5 are the gating work for v2 spec signoff. Phase Load Allocation audit is launch-blocking but not v2-spec-blocking — it can land before launch even if it lands after batch 5.

If Andy wants the audit started immediately for momentum, the scope-confirmation session is short and worth doing first regardless. It produces the audit plan; actual sport-by-sport work can interleave with batch 4.

---

## Files for pickup (in order)

For the **batch 4 thread:**

1. **This handoff** (`V2_Handoff_post_open_items.md`) — captures decisions made in the open items review.
2. **`V2_Drafting_Handoff_post_batch3.md`** — original batch 4 agenda. Most of it still applies; this handoff augments rather than replaces.
3. **`Athlete_Onboarding_Data_Spec_v2.md`** — partial draft. Read the Resolved decisions log at the bottom for context on what's already decided.
4. **`V2_spec_decisions_handoff.md`** — three locked decisions (Athlete Network, §D drop, §E.7 strength field migration).
5. **`Onboarding_Session_Handoff.md`** — needed for §I, §J, §K decisions not in v2 batch docs.
6. **`Sections_C_J_v2_Batch.md`** — §J.2 race-day fueling fields for §I drafting.
7. **`Sections_GHMN_v2_Batch.md`** — §M.1–M.4 content for batch 5.
8. **`Vocabulary_Audit_v2.md`** — §3 (equipment) and §4 (12 toggles) for §J.
9. **`Athlete_Onboarding_Data_Spec_v1.md`** — for §J Locales (longest single section), §K Locale Schedule, §I Lifestyle existing field text.
10. **`Adherence_Drop_Spec_v2.md`** — cross-referenced from Plan Management group in batch 5.

For the **Phase Load Allocation audit thread:**

1. **This handoff** — for context on why the audit was committed.
2. **`Sports_Framework_v3.xlsx`** — Phase Load Allocation sheet is the target. Sheet 1 has the 18-sport list.
3. **`Sports_Framework_Handoff_v2.md`** — explains how the framework was built. Read for AR's Phase Load Allocation as the worked example.
4. **`Athlete_Onboarding_Data_Spec_v2.md`** §C — confirm the Discipline Weighting field's expectations of what Phase Load Allocation provides.

---

## Open items still tracked (post-resolution)

The 7 in the v2 spec Open Items table:

1. Disclosure copy refinement (legal review) — placeholder drafted, copy not legally vetted
2. Migration path from current app database
3. Layer 1 ↔ Layer 0 query layer concrete spec
4. Sports Framework Phase Load Allocation audit (active)
5. Sheet 7 deprecation execution (mechanical, post-v2 signoff)
6. Multi-partner consent rules (N>2) — direction set; team-training spec to formalize
7. Stale-link cleanup — direction set; team-training spec to confirm

---

## Gut check

**What we got right this session:**

The open items walkthrough was the right move before batch 4 started. Without it, batch 4 would have re-asked questions that already had latent answers (e.g., the radius default, the link/unlink UX), and §B.4.2 would have stayed in the awkward "deferred" state when shipping the three rules at launch is the obvious call. Item 16 (coach mode) sitting in Open Items was actively misleading — closing it removes a phantom workstream.

**Top risks for the next thread:**

1. **Batch 4 thread risks loading too many decisions cold.** The Resolved decisions log in the spec is long now (18 entries). A drafter reading it in sequence might miss that decisions #10–#13 specifically affect batch 4 sections. Mitigation: this handoff's table calls them out by integration target, but the next thread should re-confirm decisions #10, #11, #12 before drafting §J/§K.

2. **Phase Load Allocation audit scope is real.** 9–18 hours of focused work split across 4–5 sessions is a meaningful commitment. Easy to under-scope. The scope-confirmation session is non-optional — without it, audits drift in depth and consistency across sessions.

3. **§B.4.2 promotion (decision #7) hasn't been integrated yet.** The current spec text still reads "Auto-suggest rules are a v2 design decision — flagged in Open Items, not specced here." That's now wrong. The next batch 4 thread should re-write §B.4.2 to specify the three rules as launch behaviour, *before* getting into §I/§J/§K. It's a 10-minute edit but easy to forget.

4. **Re-injury rule (decision #3) is a §B + Plan Management spec change.** Status History walk logic belongs in Plan Management; the §B record can stay as-is. Make sure batch 5 picks this up — it's not in the original post-batch3 agenda.

**What we might be missing:**

- **No one owns the Phase Load Allocation audit dependencies.** Each sport's audit pulls from training literature. Who maintains the source list? Worth establishing a "sources consulted" column in the audit side doc so the next maintainer can audit the audit.
- **The split-model decision (#9) is an architecture choice masquerading as a spec choice.** "Stronger LLM weeks 1–12, cheaper LLM weeks 13+" implies routing logic that isn't a Plan Management spec concern alone — it's an inference-pipeline concern. Worth a note in the architecture handoff (separate doc) so the engineering thread doesn't miss it.
- **Batch 4 itself is 300–500 lines of new spec.** Combined with the open-items absorption above, the next thread will be context-heavy. Splitting into 4a (§I + §J + §B.4.2 promotion + §B re-injury rule) and 4b (§K + integration polish) is more conservative than the prior handoff's 4a/4b split.

**Strongest argument against where we are:**

We made 18 decisions in one session. Some of them — especially #3 (re-injury rule), #9 (split-model), #14 (partial-link), #17 (linked-account consent) — deserved more deliberation than they got. The session prioritized closing the loop on Open Items over stress-testing each decision. Mitigation: the integration step in batch 4/5 will surface implementation-time concerns; if any decision turns out to be wrong, it can be revisited then. None of the decisions above are irreversible.

---

## Recommended approach for next thread

**For batch 4:** Start the new thread with this handoff plus the prior post-batch3 handoff plus the v2 spec. Do the §B.4.2 promotion and §B re-injury rule integration *first* (10–20 min), then move to §I, §J, §K. Re-confirm decisions #10, #11, #12 inline before drafting §J/§K — surface them so the user can adjust if wanted.

**For Phase Load Allocation:** Start a separate thread. First message should be the scope-confirmation session: open the xlsx, list the sports, propose batch order. Don't try to combine with batch 4 — context budget will not absorb both.

**For both:** When either thread is wrapping, write a short handoff before the context window forces it.
