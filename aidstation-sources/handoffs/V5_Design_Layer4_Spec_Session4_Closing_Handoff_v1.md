# V5 Design — Layer 4 Spec Session 4 Closing Handoff

**Session:** Single-stage. No Andy decisions teed up — §§10/11/13 are mechanical fleshing-out of session-1/2/3 contracts per the session-3 handoff §5 recommendation. One spec-file commit (`9f6957f`); this handoff is the second commit on the branch.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Design_Layer4_Spec_Session3_Closing_Handoff_v1.md` (session 3's §5 named "§10 (edge cases) + §11 (performance budget) + §13 (test scenarios)" as session 4 scope, all flagged as mechanical and fittable in a single session unless Andy wanted to redesign the latency budget envelope or add new validator rules — Andy went "proceed as planned" with no redesign).
**Branch:** `claude/v5-design-layer-implementation-4bQNk` (cut from `main` at `4eeab78` — the merge commit for session-3 PR #57).
**Status:** 🟢 §§10/11/13 drafted with the §6.4 `Layer4ShapeInfeasibleError` detection algorithms session 3 calibration round-2 flagged forward. 🟡 Spec near-complete: §§12 + 14 still stubbed; session 5 lands them + end-of-arc bookkeeping + PR. 🟡 No CLAUDE.md / backlog bump this session — held per the v1-commit deferral rule carried forward from sessions 1/2/3 ("lands at end-of-PR once §§12 + 14 are also drafted"). PR will be created after session-5 handoff lands; same end-of-arc cadence.
**Time-on-task:** Single chat. 4 surgical Edits to one file. Files this session: **1 substantive** (Layer4_Spec.md, 1264 → 1667 lines; +411 / -8) + **1 bookkeeping** (this handoff). Well under 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

Session-3 closing handoff §10.4 claimed Layer4_Spec.md was at 1247 lines after the §§8–9 main draft + ~17 lines from the two calibration commits (round 1: Peak intensity 70/20/10 + 12-week open-ended horizon + Taper bounds removed + ACWR threshold ≥ 1.25; round 2: §6.4 4th trigger + escalation table + §8.2 `long_slow_distance` + `recovery_day_after_long` + §8.6 `recovery_week`). Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| Layer4_Spec.md 1264 lines pre-session-4 (1247 base + ~17 calibration) | `wc -l` | ✅ |
| 62 H2+ headings (`grep -c "^##"`) | `grep` | ✅ |
| `seam_unresolved` in §7.10 enum at line 507 + 6 narrative spots | `grep -n "seam_unresolved"` | ✅ — 7 hits total |
| §§8.1–8.8 + §§9.1–9.6 all present | `grep -nE "^### [89]\."` | ✅ |
| §§10/11/12/13/14 stub labels read "to be drafted in a later session" (5 entries) | `grep -n "to be drafted"` | ✅ |
| Calibration round 1 edits landed (Peak 70/20/10 line 822; 12-week horizon line 863; ACWR ≥ 1.25 line 1015) | `grep -n` | ✅ |
| Calibration round 2 edits landed (long_slow_distance line 1005; recovery_day_after_long line 1006; recovery_week line 1045; §6.4 4th trigger line 939) | `grep -n` | ✅ |
| Session-3 PR #57 merged at `4eeab78`; branch `claude/v5-design-layer-implementation-4bQNk` cut clean from `main` | `git log` | ✅ |
| Working tree clean | `git status` | ✅ |

No drift. Session-3 narrative + both calibration rounds reconciled cleanly against on-disk state.

---

## 2. Session narrative — §§10/11/13 mechanical drafting

The chat opened with Andy linking the session-3 closing handoff URL and saying "let's work!". Per the session-3 handoff §5 + §8, the scope was §10 (edge cases) + §11 (performance budget) + §13 (test scenarios), all flagged as mechanical with no Andy decisions teed up. I confirmed scope with Andy ("proceed with §§10/11/13, or different scope?") and got "proceed as planned."

No new Andy decisions surfaced during drafting. Policy choices I picked without explicit Andy confirmation (warrant flagging in §6 below):

1. **§10.2 shape-infeasibility detection tolerances.** Picked v1 defaults for each of the four `Layer4ShapeInfeasibleError` classes: `schedule_volume_infeasible` at 0.85 × `phase_load_bands.low` (sub-band-low by ≤15% downgrades to warning, not raise); `skill_acquisition_infeasible` at 4-week Base minimum for skill-heavy disciplines (swim/MTB/packraft/rock climbing/skimo per Layer 2A `requires_skill_acquisition=True` tag); `discipline_frequency_infeasible` is strict (no tolerance); `cumulative_load_injury_infeasible` is strict. These tighten the §6.4 carry-forward by making detection algorithms concrete; numbers are evidence-grounded starting points.
2. **§11.2 token budget estimates.** Picked per-call input/output token estimates (~8000/3000 per-phase synthesizer; ~6000/800 per seam reviewer; etc.) by scaling from typical Sonnet 4.6 structured-output cases. These are unmeasured v1 budgets — production telemetry per §9.6 drives true measurement post-launch.
3. **§11.3 cost framing at Sonnet 4.6 pricing ($3/MTok input + $15/MTok output).** Derived per-invocation costs + the headline $0.50–1.10 `plan_create` range. Pricing as of 2026-05; subject to vendor changes.
4. **§11.4 cache hit-rate assumptions.** Picked: `plan_create` <5%, T1 ~10%, T2 ~15%, T3 ~5%, single-session ~25%, race_week_brief <5%; per-phase Pattern A within-call ~10%; across-call ~<5%. Yielded ~$14/yr/athlete amortized cost vs. ~$40–60 no-cache. Hit-rate numbers are design assumptions; flagged for re-measurement.
5. **§11.5 cumulative cost ceilings.** Picked soft/hard ceilings per athlete: $0.50/$2.00 day, $2/$10 week, $8/$30 month. These are guardrails for the orchestrator to enforce, not Layer 4 contracts; Andy can adjust without touching the spec.
6. **§11.8 alert thresholds.** Picked: p95 > 2× design for 5 measurements; retry rate > 20%; cost per invocation > 2× design for 24h; cache hit rate < 50% of assumed for 7 days. Operational defaults; tuneable.
7. **§13 coverage approach.** Picked ~84 numbered TS rows organized by entry point + cross-cutting categories (cache + flag + edge) rather than a full Cartesian matrix. Cartesian would be impractical (~thousands of cells); the 84-row picked-coverage set hits high-signal cases across every axis. Added 5 smoke tests gating CI specifically.

Also folded in the session-3 carry-forward from §10 of the spec stub: tightened the 8-case stub paragraph into the §10.1 + §10.3 + §10.4 + §10.5 + §10.7 + §10.8 + §10.10 tables (every original stub case has a row in the new table, plus all the new cases the session-3 handoff §5 named — joint-session day on refresh boundary, race_week_brief with no Taper sessions, locale equipment changed mid-request, ETL drift mid-synthesis, cache-hit-rebind collision, per-phase chain miss after phase 0 hit). And the §11 stub paragraph's numbers were preserved as the baseline in §11.1 + §11.3 + tightened with token-budget detail in §11.2 + cache amortization in §11.4.

No other Andy decisions this session — the rest was mechanical drafting against the session-1/2/3 contracts.

---

## 3. Files shipped this session

All on branch `claude/v5-design-layer-implementation-4bQNk`. Spec commit `9f6957f` pushed at end of chat per the standard mechanic; this handoff commit follows.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Layer4_Spec.md` | Edit (1264 → 1667 lines; +411 / -8) | Full breakdown in §4 below. |
| 2 | `aidstation-sources/handoffs/V5_Design_Layer4_Spec_Session4_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Not touched this session** (deferred per the v1-commit rule):

- `CLAUDE.md` — no last-shipped-narrative bump; stays pointed at PR17.
- `Project_Backlog_v30.md` — no version bump.
- `PR_Verification_Status.md` — no PR shipped this session.
- `Control_Spec_v8.md` — §9 doc-map stale-flag from PR16 still standing; Layer 4 entry lands at end-of-arc.

---

## 4. What the spec now commits to (post-session-4)

### 4.1 Newly-drafted sections (§§10/11/13)

| Section | Subsections | Content |
|---|---|---|
| §10 Edge cases | 10 (§§10.1–10.10) | §10.1 degenerate timelines (single-phase Pattern A, two-phase, open-ended at horizon decay, single-day event). §10.2 **shape-infeasibility detection algorithms** for the four `Layer4ShapeInfeasibleError` classes the calibration round-2 flagged forward — concrete pure-function rules with v1 tolerance defaults. §10.3 refresh edge cases (Pattern-B-prior reconstruction, 3B-shifted-start_phase mid-refresh, refresh predates start_phase, empty prior window, orphaned retired discipline, parsed_intent vs validator conflict, concurrent refresh + plan_create). §10.4 D-63 single-session edge cases (sport unavailable, equipment changed mid-request, wrist-injury substitution chain, locale XOR violations, intensity modulation, two-D-63-same-day). §10.5 race-week brief (no Taper in window, fires too early, post-race fire, multi-day with no equipment data, midnight UTC rollover, single-day vs multi-day routing). §10.6 cache + concurrency (cache-hit-with-rebind collision, per-phase chain miss after phase 0 hit, seam re-prompt invalidates chain, stale upstream defense, concurrent overlapping windows, backend transient failures). §10.7 validator + retry (seam reviewer self-disagreement, retry budget exhausted by seam path, best-effort blocker, cross-phase rule failure on final pass, schema-violation cap, unknown coaching flag, defensive missing-flag check). §10.8 ETL + version drift (mismatch, mid-call bump, stale 3A, clock skew). §10.9 Layer 4.5 boundary cases (joint session day on refresh boundary, linked athletes simultaneous refresh, §L toggle mid-plan). §10.10 misc catch-all (all-days-unavailable, 26-week event, zero historical data, race-day on §K-unavailable day, 3B suggestions vs validator, orphaned-account no-locales). |
| §11 Performance budget | 8 (§§11.1–11.8) | §11.1 latency targets per entry point + composition + p50/p95 + latency hygiene rules. §11.2 token budget per entry point with retry-tax framing. §11.3 cost per invocation at Sonnet 4.6 pricing ($3/MTok in + $15/MTok out) with no-retry vs. cap-hit ranges + per-athlete annual cost framing. §11.4 cache hit-rate assumptions per entry point + per-phase + amortized cost worked example (~$14/yr/athlete with cache vs. $40–60 without). §11.5 cumulative cost ceilings (soft + hard per day/week/month). §11.6 D-64 §6 frequency-cap interaction. §11.7 concurrency + scale assumptions for v1 single-tenant + v2 path forward. §11.8 performance-regression detection thresholds + alert rules. |
| §13 Test scenarios | 10 (§§13.1–13.10) | §13.1 coverage matrix across 8 axes. §§13.2–13.5 entry-point scenario tables: TS-1..TS-21 plan_create (Andy's case, all 4 shape modes, all 4 shape-override triggers, all 4 shape-infeasibility classes, validator retry paths, seam paths, degenerate); TS-22..TS-32 plan_refresh (T1/T2/T3 intra-phase/T3 cross-phase + 3B shift + parsed_intent + prior_session_orphaned); TS-33..TS-40 single_session_synthesize (sport unavailable, wrist injury substitution, intensity modulation, validation errors, happy path, cache hit); TS-41..TS-48 race_week_brief (Andy's case multi-day, single-day, too-early, wrong mode, equipment-incomplete, midnight rollover, no-Taper-in-window). §13.6 coaching-flag emit (TS-49..TS-66, every spec-auto and LLM-emitted trigger from §§8.2–8.6 + the §8.7 LLM-emit exception + unknown-flag schema violation + defensive missing-flag). §13.7 cache hit/miss (TS-67..TS-74). §13.8 edge-case cross-references (TS-75..TS-84). §13.9 5 CI smoke tests (TS-S1..TS-S5). §13.10 coverage gaps tracked forward. |

### 4.2 Header updates

- Status line: bumped from "Session 3" framing to "Session 4 (this update) covers §10 Edge cases, §11 Performance budget, and §13 Test scenarios — including concrete detection algorithms for the four `Layer4ShapeInfeasibleError` classes that the session-3 calibration round-2 flagged forward."
- Source-decisions block: unchanged (no new Andy decision).

### 4.3 Stub headings re-labeled

Sections §§12 + §14 still bear the "to be drafted in a later session" suffix (2 entries; was 5). The session-3 §§10–14 set narrows to session-5 §§12 + 14.

### 4.4 v1-commit deferral rule still standing

Per session-1's commit-message convention (carried through sessions 2/3): mid-stream work; no CLAUDE.md / backlog bump yet. They land at end-of-PR once §§12 + 14 are also drafted. This handoff respects that rule — no CLAUDE.md or `Project_Backlog_v30.md` bump.

---

## 5. Session 5 scope

Session-3 handoff §5's recommended order still stands: §12 (open items) + §14 (gut check) + end-of-arc CLAUDE.md / backlog bump + PR. Concretely:

### Session 5 (next): §12 + §14 + end-of-arc bookkeeping + PR

- **§12** — prune resolved items (substantial pruning: the §11 cost framing now anchors the "cost-cap interaction with D-64 frequency caps" item; the §10.6 stale-cache defense paragraph addresses the orchestrator-trust point; the §11.4 cache hit-rate framing addresses the amortized-cost open item). Tighten still-open items; pin forward to Layer 4.5 + Layer 5 specs. Fold the three session-3 tuning-candidate items into the "v1 defaults; tune post-launch" basket. Add any new tuning-candidates that surfaced during §11 (cost ceilings, alert thresholds — flag as v1 defaults; tune post-launch).
- **§14** — end-of-spec retrospective per 14-section template. Topics for the retro per the session-3 §13 stub's framing: what this spec gets right (discriminated-union session shape; per-phase + seam-reviewer architecture; four entry points keep expensive Pattern A out of cheap paths; closed-set flag taxonomy + spec-auto vs LLM-emitted split forces design clarity; cache spec is comprehensive even if not all assumptions are measured). Risks (per-phase decomposition coupling preventing parallelism — flagged in §5.2 + §11.7; seam-reviewer authority semantics single most likely over/under-spec; cost is real and unmeasured — §11.4 estimates are unverified; intensity-distribution defaults across phases are policy not data; the §10.2 shape-infeasibility detection tolerances are unmeasured starting points). Missing (joint session coordinator entirely — Layer 4.5; Layer 5 consumption contract; the prompt bodies themselves per stop-and-ask trigger #2; D-57 scheduled re-eval that would un-block several §11 + §10 paths). Best argument against scope (the four-entry-point shape is a complexity multiplier — a unified entry point with a `mode` discriminator would be simpler if per-mode prompts can be parameterized; counter: Andy explicitly picked separate functions per Decision 2, and the prompts ARE the per-mode complexity that separation makes inspectable).
- **CLAUDE.md** + **Project_Backlog_v30.md → v31.md** — end-of-PR bookkeeping bump per the deferral rule. CLAUDE.md "Last shipped session" line bumps to Layer 4 spec draft v1 (4-session arc + 2 calibration commits). Backlog adds the §12 forward-pointers as backlog items where appropriate.
- **PR**.

This keeps the original 3–5-session estimate intact (session 1 + 2 + 3 + 4 + 5 = 5 total).

### Alternative chunking

If Andy wants to front-load a prompt-body session (per-phase synthesizer prompt for Pattern A, or the seam-reviewer prompt), that's an explicit `stop-and-ask trigger #2` carve-out and can slot anywhere; it would slip the v1 spec arc by one session. Session 5 doesn't have to be the LAST session — if a prompt-body design session lands between, the arc becomes 6 sessions; the CLAUDE.md / backlog bump still defers to the actual end-of-arc PR commit.

---

## 6. Open items / decisions pinned this session

### 6.1 v1-default policy items (flagged for Andy review post-session-4)

Per §2 narrative — seven policy items I picked without explicit Andy confirmation, all with conservative defaults and inline "v1 / tune post-launch" framing:

1. **§10.2 shape-infeasibility detection tolerances** — `schedule_volume_infeasible` at 0.85 × `phase_load_bands.low`; `skill_acquisition_infeasible` at 4-week Base minimum for skill-heavy disciplines; the other two strict. Adjustable without restructuring; numbers may need tuning once production cases surface.
2. **§11.2 token budget estimates** — per-call input/output estimates by scaling from typical Sonnet 4.6 cases; unmeasured. Re-derive from telemetry post-launch.
3. **§11.3 cost framing** — Sonnet 4.6 pricing snapshot ($3/$15 per MTok); subject to vendor changes. Headline `plan_create` $0.50–1.10 is the load-bearing claim.
4. **§11.4 cache hit-rate assumptions** — five per-entry-point + per-phase rates; yields ~$14/yr/athlete amortized cost. All flagged for re-measurement; the amortization math is sensitive to T1/T2 refresh frequency assumptions (~100 T1 + ~50 T2 per athlete-year).
5. **§11.5 cumulative cost ceilings** — soft/hard ceilings per day/week/month. Orchestrator-enforced; not in Layer 4 spec contract. Andy can adjust without touching this spec.
6. **§11.8 alert thresholds** — operational defaults; tuneable.
7. **§13 TS coverage approach** — 84 numbered scenarios + 5 smoke tests, picked-coverage not Cartesian. Cartesian would be ~thousands of cells; the picked set hits high-signal cases.

None are load-bearing schema decisions; all are tuning parameters or test-strategy choices Andy can adjust without restructuring the spec. Flagged here so they don't slip past review.

**Carry-forward from session-3 §10.1 + §10.2:** all 10 policy items resolved in the calibration rounds. Nothing carries forward.

### 6.2 §12 open-items state (post-session-4)

Several §12 items are now substantially addressed and should be pruned in session 5:

- "Validator's `intended_intensity_distribution` per-phase defaults" — resolved in §5.4 (session 3 calibration round 1 set Peak to 70/20/10); fully closed.
- "Cost-cap interaction with D-64 frequency caps — if validator hits cap on a Pattern A plan, the cost of that one call exceeds expected; should the soft-cap warning factor expected vs. actual cost? Defer." — §11.5 + §11.6 now spec the interaction concretely (cumulative cost ceilings independent of frequency caps; cap-hit cost surfaces in `latency_ms_total` + `input_tokens_total` + `output_tokens_total` per §11.8). Close.
- "`Layer4ShapeInfeasibleError` routing — does this surface as a 3D gate item for the next run, or as an inline athlete-facing error in the current run? Defer." — §10.2 + §3.5 now reference the routing decision still as orchestrator's call but with concrete detection inputs. Keep open as a forward-pointer to orchestrator spec; the routing isn't Layer 4's call.
- "Seam-reviewer model downgrade (Haiku for cheaper reviewing) — measure post-launch." — §11.4 amortized-cost math + §11.8 alert thresholds now provide the measurement framework. Keep open as a post-launch tuning item.

Seven new tuning-candidate items generated this session (all v1-default flags noted inline; should fold into §12 in session 5):

- §10.2 four shape-infeasibility detection tolerances.
- §11.2 token budget estimates (re-derive from telemetry).
- §11.4 six cache hit-rate assumptions per entry point (re-measure post-launch).
- §11.5 cumulative cost ceilings per day/week/month.
- §11.8 four alert thresholds.

13 items still open in §12 (unchanged count from sessions 2/3 — three resolved + several new tuning items that fold into existing "v1 defaults; tune post-launch" basket rather than separate items).

---

## 7. Session-end verification (Rule #10)

Final pass over the file before composing this handoff:

| Check | Result |
|---|---|
| Layer4_Spec.md 1667 lines | ✅ `wc -l` |
| 90 H2+ headings (was 62 pre-session; +28 new sub-sections: 10 in §10 + 8 in §11 + 10 in §13) | ✅ `grep -c "^##"` |
| §10 sub-sections §§10.1–10.10 all present | ✅ `grep -nE "^### 10\."` |
| §11 sub-sections §§11.1–11.8 all present | ✅ `grep -nE "^### 11\."` |
| §13 sub-sections §§13.1–13.10 all present | ✅ `grep -nE "^### 13\."` |
| 84 TS rows (TS-1..TS-84) + 5 smoke tests (TS-S1..TS-S5) | ✅ `grep -E "TS-[0-9]"` + `grep -E "TS-S[0-9]"` |
| Header status line bumped to "Session 4" | ✅ Read line 3 |
| End-of-spec footer mentions session 4 + drafted §§10/11/13 + counts | ✅ Read line 1667 |
| §§12 + §14 stub labels still read "to be drafted in a later session" (2 entries; was 5) | ✅ `grep -n "to be drafted"` |
| No CLAUDE.md / Backlog bump (per v1-commit deferral rule) | ✅ `git diff --stat HEAD~1..HEAD` shows only Layer4_Spec.md |
| Branch ahead of `main` by 1 commit (`9f6957f`) pre-handoff; will be 2 commits after this handoff | ✅ `git log main..HEAD` |
| Working tree clean before handoff write | ✅ `git status` |

---

## 8. Operating notes for session 5

1. **First re-read** (per CLAUDE.md Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load.
2. **Second re-read**: this handoff in full.
3. **Third re-read**: `Layer4_Spec.md` in full, with extra attention to §10 + §11 + §13 (just-drafted; §14 retro will reference them) and §12 (about to be pruned; current state of open items needs full re-read).
4. **Bump CLAUDE.md AND backlog this session** — the end-of-arc deferral rule from sessions 1/2/3/4 ends here. CLAUDE.md "Last shipped session" line bumps to "Layer 4 spec draft v1 (4-session arc + 2 calibration commits)" pointing at session 5's PR. Backlog bumps Project_Backlog_v30.md → v31.md with any §12 items folding into the backlog.
5. **No new gating Andy-decisions teed up for session 5** as currently scoped. §12 is item-pruning + tightening; §14 is retrospective drafting. If Andy wants to fold a redesign call into the §14 retro (e.g., "the seam-reviewer authority needs revisit before v1 ships" or "the four-entry-point shape should collapse to one"), that's a stop-and-ask trigger #5 — surface in chat and pause.
6. **Policy defaults from session 4** (§10.2 four shape-infeasibility tolerances, §11.2 token budgets, §11.3 cost framing, §11.4 six cache hit-rate assumptions, §11.5 cost ceilings, §11.8 alert thresholds, §13 picked-coverage approach) — none lock anything; Andy can adjust at any time. Surface them in session 5 if drafting §14 makes them feel wrong.
7. **Stop-and-ask trigger #2 still applies**: per-phase / per-tier / single-session / seam-reviewer / race-week-brief prompt bodies are explicitly OUT of session 5 (and §§12 + 14 in general). Session 5 closes the contract sections; prompt bodies are downstream.
8. **Cost/latency numbers** in §11 should stay informal until Andy has measured production retry rates + cache-hit rates. The §11.4 amortized $14/yr/athlete estimate is sensitive to the unmeasured assumptions; surface that caveat in the §14 retro.
9. **§§10/11/13 interactions to keep consistent in §12/§14:** the §10.2 detection algorithms add tuning-candidate items to fold into §12; the §11.4 cache hit-rate assumptions add measurement-candidate items; the §13 coverage-gaps-tracked-forward (§13.10) maps to specific §12 forward-pointers (live-LLM tests, multi-athlete, cost telemetry, prompt-body regression tests). Don't duplicate — §13.10 IS the §12 entry for those items, just rendered as a test-coverage view.
10. **PR creation per session-3 §5 + §8 cadence**: after §§12 + 14 land + CLAUDE.md/backlog bump commit + this session's handoff commit lands, create the PR with title like "V5 Design — Layer 4 spec draft v1 (4-session arc)" or similar. Body should reference the 5-session arc + the 2 mid-arc calibration commits + the 4 closing handoffs.

---

## 9. Carry-forward from PR17 (informational)

Same state as sessions 1/2/3:

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — Andy mentioned in session-1 chat that it passed; not actioned this session (no CLAUDE.md / backlog touch).
- PR15 `/profile?tab=schedule` round-trip from PR15 §5.0 — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate as of `4eeab78` (main): same totals as session-3's reading (43 done / 21 blocked / 23 owed / 4 N/A). No movement this session (no PR shipped; this session is design-track).

---

---

## 10. Post-handoff close-out pass (Andy 2026-05-16, same chat)

After this handoff was committed (`a50bcbb`) and the spec commit (`9f6957f`) was pushed, I checked in with Andy on whether we had room for more work this session. My recommendation was to start a new session for session 5 (§12 + §14 + bookkeeping + PR) because §14 is best done with fresh eyes — author confirmation bias on a critical-evaluation pass is real. Andy redirected: do the §12 pruning now and ship the v1 arc as a PR + merge in this same chat; §14 retro stays deferred to a follow-on session.

This is consistent with the CLAUDE.md "push to production as we go" rule (Andy 2026-05-14): prefer shipping over accumulating more design ahead of implementation. The §12 pruning IS mechanical and benefits from fresh memory of what just landed in §§10/11/13. §14 retro doesn't block implementation — D-63 / D-64 implementation gates on the contract sections (§§1–13), which are complete.

### 10.1 §12 drafted in this close-out pass

Six subsections per the new structure (replacing the flat bullet-list stub):

- **§12.1 Resolved this arc** — table of 7 items closed across sessions 1–4 + calibration rounds (seam-reviewer authority Decision 8; intensity-distribution defaults locked; open-ended horizon at 12 weeks; Taper hard bounds removed; cost-cap interaction with D-64 frequency caps spec'd in §11.5/§11.6/§11.8; §6.4 trigger set completeness; `Layer4ShapeInfeasibleError` detection algorithms in §10.2).
- **§12.2 Prompt body design — deferred to dedicated sessions** — 5 sessions queued per stop-and-ask trigger #2 (per-phase synthesizer, per-tier T1/T2, single-session, seam-reviewer, race-week-brief). Andy picks order; seam-reviewer is the smallest and may slot first.
- **§12.3 Forward-pointers to downstream / sibling specs** — Layer 4.5 (Joint Session Coordinator), Layer 5 (consumption contract), D-57 (scheduled re-eval), plan-revert UX, multi-day race plan post-race analytics, `race_week_brief` trigger policy, `Layer4ShapeInfeasibleError` routing to athlete surface.
- **§12.4 Tuning candidates — v1 defaults; measure post-launch** — validator tolerances; coaching-flag thresholds; shape-infeasibility detection tolerances; token budgets; cost framing; cache hit-rate assumptions; cumulative cost ceilings; regression detection alert thresholds; model + temperature defaults. None block implementation.
- **§12.5 Substantive direction holds** — D7 tiered tight/loose plan horizon (HELD); `opportunity` observation expansion; seam reviewer concurrency.
- **§12.6 §14 retrospective deferred** — explicit deferral rationale: author confirmation bias on the critical-evaluation pass; retro lands before Layer 4 implementation begins.

### 10.2 §14 stub re-labeled

Changed from "## 14. Gut check — to be drafted in a later session" to "## 14. Gut check — deferred to follow-on session" with a 1-paragraph body explaining the §12.6 deferral. Section header retains its place in the 14-section depth standard per CLAUDE.md "Layer specs follow a depth standard."

### 10.3 Header + footer updates

- Status line: reframed from session-4-only to a 4-session-arc summary; explicit "Contract sections (§§1–13) complete; §14 retrospective deferred to a follow-on session" + Andy 2026-05-16 ship-now framing.
- End-of-spec footer: reframed to a full arc summary across all 13 contract sections + the §14 deferral + arc total (4 chat sessions + 2 mid-arc calibration commits + this close-out pass).

### 10.4 CLAUDE.md + backlog bumps (end-of-arc per v1-commit deferral rule)

End-of-arc bookkeeping now lands in this close-out pass since the PR ships the v1 spec arc:

- **CLAUDE.md:**
  - Layer-pipeline table: Layer 4 status `Not yet specced` → `SPEC v1 DONE (§§1–13; §14 retro deferred to fresh-eyes session)`.
  - Last-shipped-narrative: full Layer 4 spec arc summary replacing the PR17 line (PR17 carries forward as the predecessor).
  - Authoritative current files: `Layer4_Spec.md` added under "Layer 4 done (v1; §14 retro pending)"; backlog reference bumped v30 → v31.
  - Next forward move: rewritten with §14 retro + 5 prompt-body sessions + Layer 4 implementation + Layer 4.5 + Layer 5 as the new candidate set.
- **Project_Backlog_v30.md → v31.md:**
  - New top-line file-revision entry for v31 capturing the full 4-session arc + close-out.
  - D-63 row status note: "🟡 Implementation pending — Layer 4 spec v1 landed 2026-05-16 (gates lifted); ready for implementation" + body detail on what implementation can land pre-prompt-body (deterministic-validator harness + `ad_hoc_workout_suggestions` schema + UX scaffold).
  - D-64 row status note: same status flip + body detail (plan_versions table per §7.11 + per-day pointer resolver per §7.12 + frequency-cap orchestrator + diff renderer + `plan_refresh_log` schema can land pre-prompt-body).

### 10.5 Bookkeeping

- Close-out spec commit (this commit) covers: §12 (6 subsections), §14 stub re-label, header status line rewrite, end-of-spec footer rewrite, CLAUDE.md edits, Project_Backlog_v31.md (new file), this handoff addendum.
- No new Decision 9+ in the source-decisions block — §12 / §14 framing are spec-internal choices, not source decisions.
- File count for the close-out pass: 4 substantive files (Layer4_Spec.md, CLAUDE.md, Project_Backlog_v31.md, this handoff). Session 4 total across both passes: 1 substantive spec + 1 calibration round + 1 handoff + 1 close-out pass touching 3 distinct files + this addendum = 4 distinct files. Under 5-file ceiling.

### 10.6 Next session pointers (post-merge)

Andy's choice from the new "Next forward move" candidate set in CLAUDE.md:

1. **Layer 4 §14 retrospective** — fresh-eyes pass; lands before implementation per §12.6.
2. **Layer 4 prompt-body design sessions** — five queued; seam-reviewer is smallest and may slot first.
3. **Layer 4 implementation track** — D-63 / D-64 gates removed; implementation can start with scaffolding ahead of prompt bodies.
4. **v5 onboarding implementation PR** — substantial code work; unchanged from prior CLAUDE.md.
5. **D-50 wiring resumption** — unchanged from prior CLAUDE.md.
6. **Layer 4.5 — Joint Session Coordinator spec** — separate file; lands when team-features track activates.
7. **Layer 5 spec** — parallel supplemental outputs.

---

**End of handoff.**
