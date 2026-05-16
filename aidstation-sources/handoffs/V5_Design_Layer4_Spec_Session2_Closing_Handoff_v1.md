# V5 Design — Layer 4 Spec Session 2 Closing Handoff

**Session:** Single-stage. One Andy decision (seam-reviewer authority — Decision 8) teed up at session start, picked early, then folded in alongside the §§4–6 draft. One spec-file commit (`9ba96e7`); this handoff is the second commit on the branch.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Design_Layer4_Spec_Session1_Closing_Handoff_v1.md` (session 1's §5 named "§§4–6 (preconditions, algorithm Pattern A, algorithm Pattern B)" as session 2 scope, with the seam-reviewer authority question explicitly teed up as the gating decision before drafting §6).
**Branch:** `claude/v5-design-layer-implementation-7Hhr5` (cut from `main` at `cd00d6f` — the merge commit for session-1 PR #54).
**Status:** 🟢 §§4–6 drafted + Decision 8 (seam-reviewer authority = β propose-patch) committed and pushed. 🟡 Spec mid-stream: §§8–14 still stubbed; sessions 3+ land them. 🟡 No CLAUDE.md / backlog bump this session — held per the v1-commit deferral rule from session 1 ("lands at end-of-PR once §§8–14 are also drafted"). PR will be created after this handoff lands; same end-of-arc cadence.
**Time-on-task:** Single chat. ~5 surgical Edits to one file + one Bash sed for the §§8–14 stub-label cleanup. Files this session: **1 substantive** (Layer4_Spec.md, 736 → 1013 lines; +293 / -16) + **1 bookkeeping** (this handoff). Well under 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

Session-1 closing handoff §7 claimed Layer4_Spec.md was 736 lines + 33 H2 headings + all Stage A/B edits on disk. Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| Layer4_Spec.md 736 lines pre-session-2 | `wc -l` | ✅ |
| 33 H2+ headings (`grep -c "^##"`) | `grep` | ✅ |
| `race_week_brief` entry point + `RaceWeekBrief` + `RacePlan` schemas all on disk | `grep -n` for the names | ✅ — 30+ matches across header, §3.4, §7.13, §7.14, §8 stub, §12 stub |
| `session_index_in_day` + `time_of_day` fields on `PlanSession` | `grep -n` | ✅ |
| Header source-decisions block lists D1–D7 with Andy 2026-05-16 attribution | Read lines 11–19 | ✅ |
| §12 forward-pointer for "LLM seam-reviewer authority semantics" present | `grep -n` | ✅ — this is the explicit decision point session 2 was supposed to resolve |
| Branch `claude/v5-design-layer-implementation-7Hhr5` ahead of `main` by 0 commits (clean start) | `git log main..HEAD` | ✅ — main contains session-1 merge `cd00d6f` |
| Working tree clean | `git status` | ✅ |
| `PR_Verification_Status.md` reflects PR11 step 1 ✅ Done (per the most recent main commit `cd00d6f`) | Read | ✅ |

No drift in the Rule #9 sense. Session-1 narrative reconciled cleanly against on-disk state.

---

## 2. Session narrative — Decision 8 and §§4–6 fold-in

The chat opened with Andy asking me to look at the session-1 handoff and "let's work." Per the operating notes (session-1 handoff §8 note 4), the gating action was to tee up the seam-reviewer-authority decision as a single AskUserQuestion before drafting §6. I did that, with four options:

| # | Authority | Summary |
|---|---|---|
| β (recommended) | Propose-patch | Reviewer emits structured patch (verdict + free-text seam_issues + direction); orchestrator applies as a re-prompt of the targeted phase iff retry budget remains. |
| α | Flag-only | Reviewer emits verdicts only; orchestrator decides retry. Cheap but pushes seam-resolution logic upstream. |
| γ | Force-re-prompt | Reviewer can mandate phase re-synthesis with constraint deltas. Most powerful, fattest latency tail. |
| Mixed | Verdict-tier-drives-action | Minor = observation; major = patch; catastrophic = force-re-prompt. Captures all three at the cost of moving parts. |

Andy picked **β — propose-patch**. The decision lives in the header source-decisions block as Decision 8 with attribution + alternatives + rejection rationale; §6.2 fleshes out the per-verdict action table + per-seam iteration cap (2) + authority bounds.

With β picked, I drafted §§4–6 in place over the session-1 stubs. Decision 8 cross-references: header status line, header source-decisions block (Decision 8), §6.2 ("Per Andy 2026-05-16 (Decision 8 — recorded in header)"), §12 forward-pointer marked resolved with strikethrough, end-of-spec footer.

No other Andy decisions this session — the rest was mechanical drafting against the session-1 contract.

**Policy defaults I picked (without separate Andy confirmation) that warrant explicit flagging for session-3+ review:**

1. **§5.4 deterministic-validator tolerances.** Volume-band ±15% blocker / ±5% warning; ACWR safe-band 0.8–1.3 (blocker outside 0.7–1.4); intensity-distribution ±10pp tolerance per zone. Evidence-grounded starting points; tune per measured retry rates in production. Inline note: "v1 defaults; tune post-launch."
2. **§5.4 intensity-distribution defaults per phase.** Base 80/15/5 (Z1-Z2/Z3/Z4-Z5); Build 70/20/10; Peak 60/25/15; Taper 75/15/10. Per-phase tunable; flagged in §12 (already-open item from session 1).
3. **§6.1 open-ended-mode total horizon.** v1 defaults to 16 weeks rolling forward; revisit per D7-held tiered-horizon decision.
4. **§6.1 Taper bounds.** Floor 1 week, ceiling 4 weeks regardless of mode. Race-prep evidence base.
5. **§6.4 shape_override trigger set.** Three narrow rules (standard + <8wk → compressed; compressed + <4wk → extended/Peak; Base + high_aero + <12wk → Build). Picked conservatively. Inline note: "v1 defaults; revisit only if production cases surface a fourth trigger."
6. **§5.4 rule-set scope.** 10 rules. The list might be incomplete — e.g., no explicit "joint session sport compatibility" rule (deferred to Layer 4.5); no "kit-manifest item resolves in layer0 equipment registry" rule (called out in §5.3 race-week-brief validator but not in the §5.4 generic table).

Andy should sanity-check items 1–5 at his leisure; item 6 is fine to revisit in the §§8–14 drafting sessions when more rule additions surface.

---

## 3. Files shipped this session

All on branch `claude/v5-design-layer-implementation-7Hhr5`. Spec commit `9ba96e7` pushed at end of chat per the standard mechanic; this handoff commit follows.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Layer4_Spec.md` | Edit (736 → 1013 lines; +293 / -16) | Full breakdown in §4 below. |
| 2 | `aidstation-sources/handoffs/V5_Design_Layer4_Spec_Session2_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Not touched this session** (deferred per the v1-commit rule):
- `CLAUDE.md` — no last-shipped-narrative bump; stays pointed at PR17.
- `Project_Backlog_v30.md` — no version bump.
- `PR_Verification_Status.md` — no PR shipped this session.
- `Control_Spec_v8.md` — §9 doc-map stale-flag from PR16 still standing; Layer 4 entry lands at end-of-arc.

---

## 4. What the spec now commits to (post-session-2)

### 4.1 Newly-drafted sections (§§4–6)

| Section | Status | Content |
|---|---|---|
| §4 Input validation | ✅ | §4.1 cross-entry rules (5 rules — user scope, etl_version_set, staleness, locale resolution, active-injury surface). §4.2–4.5 per-entry-point rule tables with typed `Layer4InputError(code)` per row. Fail-fast first-rule-wins semantics; implementation lives in `_validate_<entry_point>_inputs()` helpers. |
| §5 Algorithm | ✅ | §5.1 routing table (8 (mode, tier, scope) → pattern mappings). §5.2 Pattern A — 6-step algorithm (compute phase structure → determine phases → per-phase synthesis loop with capped retry → seam review loop with β propose-patch → final cross-phase validator pass → compose payload). §5.3 Pattern B — 6-step algorithm (build context per entry point → single LLM call → parse → validate → capped retry → compose payload). §5.4 deterministic-validator rule set (10 rules: volume_band / acwr / rest_spacing / intensity_dist / two_per_day / equipment_unavailable / injury_violation / schedule_violation / discipline_excluded / sport_locale_incompatible). §5.5 capped-retry semantics (per-phase cap default 2 shared across validator + seam-driven retries; best-effort acceptance; schema-violation separate budget). |
| §6 Periodization decomposition + seam-review semantics | ✅ | §6.1 `phase_structure_from_3b()` per 3B mode (proportions for standard/compressed/extended; custom dict verbatim; Taper bounds). §6.2 seam-reviewer authority = β propose-patch with full per-verdict action table + per-seam iteration cap (2) + authority bounds. §6.3 single-phase T3 special case. §6.4 `shape_override` path (3 narrow triggers; plan_create-time only). §6.5 `start_phase != 'Base'` handling + `refresh_predates_start_phase` error. |

### 4.2 Header updates

- Status line: bumped from "Session 1" framing to "Session 2 (this update) covers §4 Input validation, §5 Algorithm, §6 Periodization decomposition + seam-review semantics."
- Source-decisions block: added Decision 8 (seam-reviewer authority = β propose-patch).

### 4.3 Stub headings re-labeled

Sections §§8–14 still bear the "to be drafted in a later session" suffix (the session-1 "to be drafted in session 2" labels would be misleading now that session 2 is shipping).

### 4.4 §12 forward-pointer cleanup

The session-1 §12 stub had "LLM seam-reviewer authority semantics (decision point flagged in §6 stub above)" as the first forward-pointer. That bullet is now ~~struck through~~ with a "Resolved 2026-05-16 (session 2, Decision 8): propose-patch / β. See §6.2." trailer.

### 4.5 v1-commit deferral rule still standing

Per session-1's commit-message convention (carried forward): mid-stream work; no CLAUDE.md / backlog bump yet. They land at end-of-PR once §§8–14 are also drafted. This handoff respects that rule — no CLAUDE.md or `Project_Backlog_v30.md` bump.

---

## 5. Session 3+ scope

The remaining §§8–14 split naturally into chunks. My recommendation is the following order, which front-loads the load-bearing content:

### Session 3 (recommended): §8 (coaching flag rules) + §9 (caching & determinism)

- **§8** — full per-mode flag-trigger rule set. Existing Taper auto-emit table from session 1 (5 rows: `race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) is in place; needs sibling tables for: Base-phase flags (e.g., `first_introduction_to_<discipline>`); Build-phase flags (e.g., `weak_link_targeted`, `overreach_test`); Peak-phase flags (e.g., `race_pace_specific`, `tune_up_race`); cross-phase flags (e.g., `best_effort_plan`, `shape_override`, `intensity_modulated`, `seam_unresolved`, `data_gap`). LLM-emitted vs. spec-auto-emitted convention also needs explicit definition.
- **§9** — cache-key formulae already exist in stub form. Cleanup pass: validate the per-entry cache-key composition per Control_Spec §4 partial-update model; lock down per-phase cache for Pattern A; specify invalidation triggers per upstream-layer change.

Both are mechanical; should fit a single session unless Andy wants to redesign the flag taxonomy.

### Session 4 (recommended): §10 (edge cases) + §11 (performance budget) + §13 (test scenarios)

- **§10** — existing stub already enumerates ~8 edge cases. Tighten + add a few (joint-session day on a refresh boundary; race_week_brief triggered with no Taper-phase sessions; D-63 single-session when locale's effective equipment changes between request and synthesis; ETL-version-set drift mid-synthesis).
- **§11** — Pattern A / B latency numbers already in stub; cost estimates likewise. Per-phase + per-seam cost-cap interaction with D-64 §6 frequency caps. Tighten.
- **§13** — full TS-1..TS-N table. Stub names ~7 scenarios; expand to coverage matrix across (entry_point × periodization_shape × tier × validator_pass/fail).

### Session 5 (recommended): §12 (open items maintenance) + §14 (gut check) + end-of-arc CLAUDE.md + backlog bump

- **§12** — prune resolved items (Decision 8 already done); tighten the still-open items; pin forward to Layer 4.5 + Layer 5 specs.
- **§14** — end-of-spec retrospective per 14-section template.
- **CLAUDE.md** + **Project_Backlog_v30.md → v31.md** — end-of-PR bookkeeping bump per the deferral rule.
- **PR**.

This gets the full v1 spec in by 3 more sessions (within the original 3–5 estimate; session 1 + 2 + 3 + 4 + 5 = 5 total).

### Alternative chunking

If Andy wants to front-load a prompt-body session (e.g., the per-phase synthesizer prompt for Pattern A), that's an explicit `stop-and-ask trigger #2` carve-out and can slot anywhere; it would slip the v1 spec arc by one session.

---

## 6. Open items / decisions pinned this session

### 6.1 v1-default policy items (flagged for Andy review post-session-2)

Per §2 narrative above — five policy items I picked without explicit Andy confirmation, all with conservative defaults and inline "v1 / tune post-launch" framing:

1. §5.4 validator tolerance thresholds (±15%/±5% volume; ±10pp intensity zone; ACWR 0.7–1.3 / 0.8–1.3).
2. §5.4 intensity-distribution defaults per phase (Base 80/15/5 → Taper 75/15/10).
3. §6.1 open-ended mode total horizon = 16 weeks (pre D7-held tiered-horizon decision).
4. §6.1 Taper bounds: floor 1wk, ceiling 4wk.
5. §6.4 shape_override trigger set (3 narrow rules).

None are load-bearing schema decisions — all are tuning parameters or narrow rule-set additions that Andy can adjust without restructuring the spec. Flagged here so they don't slip past his review.

### 6.2 §12 open-items state (post-session-2)

| Item | Status |
|---|---|
| LLM seam-reviewer authority | ✅ Resolved (Decision 8 — β propose-patch) |
| Per-phase synthesizer prompt body | Deferred per stop-and-ask trigger #2 |
| Per-tier T1/T2 synthesizer prompt body | Deferred per stop-and-ask trigger #2 |
| Single-session synthesizer prompt body | Deferred per stop-and-ask trigger #2 |
| Seam-reviewer prompt body | Deferred per stop-and-ask trigger #2 |
| Race-week-brief prompt body | Deferred per stop-and-ask trigger #2 |
| Plan-revert UX | Deferred to UX session |
| Layer 4.5 — Joint Session Coordinator | Its own spec; lands when team-features track activates |
| Tiered tight/loose plan horizon (D7) | HELD; revisit post-launch with cost/quality data |
| Multi-day race plan post-race analytics | Out of v1; add when race-execution surface designed |
| Layer 5 consumption contract | Defers to Layer 5 spec |
| Per-phase intensity-distribution defaults | v1 defaults landed (§5.4); flagged for tuning |
| Cost-cap × D-64 frequency cap interaction | Deferred to §11 in session 4 |
| `Layer4ShapeInfeasibleError` routing | Deferred to §10 in session 4 |
| Seam-reviewer model downgrade (Haiku) | Measure post-launch |
| `race_week_brief` trigger policy (cadence within ≤14 days) | Currently "single fire at 14 + athlete-triggerable re-runs"; tune post-launch |

13 items still open (down from 14 — Decision 8 resolved).

---

## 7. Session-end verification (Rule #10)

Final pass over the file before composing this handoff:

| Check | Result |
|---|---|
| Layer4_Spec.md 1013 lines | ✅ `wc -l` |
| 48 H2+ headings (was 33 pre-session; +15 new sub-sections in §§4–6) | ✅ `grep -c "^##"` |
| Header source-decisions block lists Decision 8 with Andy 2026-05-16 attribution + rejected-alternatives rationale | ✅ Read |
| §4 sub-sections §§4.1–4.5 all present | ✅ `grep -nE "^### 4\."` |
| §5 sub-sections §§5.1–5.5 all present | ✅ `grep -nE "^### 5\."` |
| §6 sub-sections §§6.1–6.5 all present | ✅ `grep -nE "^### 6\."` |
| §6.2 fully documents β authority semantics: per-verdict action table + per-seam cap + authority bounds | ✅ Read |
| §12 LLM-seam-reviewer-authority forward-pointer marked resolved with strikethrough + 2026-05-16 attribution | ✅ `grep -n "propose-patch"` |
| End-of-spec footer mentions session 2 + drafted §§4–6 + Decision 8 | ✅ Read line 1013 |
| §§8–14 stub labels updated from "session 2" → "a later session" | ✅ `grep -n "to be drafted"` |
| No CLAUDE.md / Backlog bump (per v1-commit deferral rule) | ✅ `git diff --stat HEAD~1..HEAD` shows only Layer4_Spec.md |
| Branch ahead of `main` by 1 commit (`9ba96e7`) pre-handoff; will be 2 commits after this handoff | ✅ `git log main..HEAD` |
| Working tree clean before handoff write | ✅ `git status` |

---

## 8. Operating notes for session 3

1. **First re-read** (per CLAUDE.md Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load.
2. **Second re-read**: this handoff in full.
3. **Third re-read**: `Layer4_Spec.md` in full, with extra attention to §6.2 (seam-reviewer authority semantics — the load-bearing decision from session 2) and the §§5.4 validator rule set + §§4.1–4.5 precondition tables (the contracts §§8–14 will reference).
4. **Do not bump CLAUDE.md or backlog** until §§8–14 are also drafted. The bump lands at end-of-arc per the session-1 deferral rule.
5. **No new gating Andy-decisions teed up for session 3** as currently scoped. §8 coaching-flag rule set is mechanical; §9 caching is mostly already in stub form. If Andy wants to reshape the flag taxonomy or change cache-key composition, that's a stop-and-ask trigger #5 (schema change affecting inter-layer contract) — surface it then.
6. **Policy defaults from session 2** (§5.4 tolerances, §5.4 intensity-distribution defaults, §6.1 horizon defaults, §6.1 Taper bounds, §6.4 shape_override triggers) — none lock anything; Andy can adjust at any time. Surface them in session 3 if drafting §8 or §9 makes them feel wrong.
7. **Stop-and-ask trigger #2 still applies**: per-phase / per-tier / single-session / seam-reviewer / race-week-brief prompt bodies are explicitly OUT of session 3 (and §§8–14 in general). Each defers to its own focused session. Session 3 expands the contract sections (§8 flag rules, §9 cache keys); prompt bodies are downstream.
8. **Cost/latency numbers** in §11 should stay informal until Andy has measured production retry rates + cache-hit rates. Same posture as session 2 ("design well, cut later if too costly").

---

## 9. Carry-forward from PR17 (informational)

Same state as session 1:

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — Andy mentioned in session-1 chat that it passed; not actioned this session (no CLAUDE.md / backlog touch).
- PR15 `/profile?tab=schedule` round-trip from PR15 §5.0 — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate as of `cd00d6f` (main): 43 done / 21 blocked / 23 owed / 4 N/A. No movement this session (no PR shipped; this session is design-track).

---

**End of handoff.**
