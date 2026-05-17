# V5 Design Layer 4 — §14 Retrospective Closing Handoff

**Session:** Ships the §14 retrospective for `Layer4_Spec.md` — the fresh-eyes critical-evaluation pass deferred per §12.6 across the 4-session Layer 4 spec arc + the 5-prompt-body arc + the 3 amendment rounds. **The Layer 4 spec arc is now COMPLETE §§1–14.** Combined audit + gut-check + implementation readiness gate per Andy's 2026-05-17 three-pick selection.
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Design_Layer4_Prompts_RaceWeekBrief_Closing_Handoff_v1.md` (race-week-brief shipped + merged on main via PR #66; this session opened against the §6 forward pointers — Andy picked Layer 4 §14 retro as the next-session focus).
**Branch:** `claude/review-design-handoff-jv5Ya`.
**Status:** 🟢 1 substantive spec edit (`Layer4_Spec.md` §14 replaced — ~190 lines), 3 bookkeeping (CLAUDE.md, Project_Backlog v37 → v38, this handoff). 4 files total — under the 5-file ceiling. Same envelope as the predecessor race-week-brief session.

---

## 1. Session-start verification (Rule #9)

Predecessor race-week-brief handoff §6 forward pointer claimed: race-week-brief shipped + merged via PR #66; branch `claude/review-design-handoff-CuXt4` merged to main; `Layer4_RaceWeekBrief_v1.md` 955 lines, 14 H2 + Source-decisions header; 5 of 5 prompt bodies in `aidstation-sources/prompts/`; Backlog at v37; Layer 4 prompt-body arc COMPLETE; next-session candidates include §14 retro (recommended next per §12.6), Layer 4 implementation track, v5 onboarding implementation, Layer 4.5 spec, Layer 5 spec.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` exists, 955 lines | `wc -l` | ✅ 955 |
| All 6 prompt body files present in `prompts/` (SeamReviewer + PerPhase + SingleSession + RefreshT1 + RefreshT2 + RaceWeekBrief) | `ls prompts/` | ✅ 6 files, total 3978 lines |
| `Layer4_RaceWeekBrief_v1.md` has 15 H2 (14 numbered + Source-decisions header) | `grep -c "^## "` | ✅ 15 |
| Backlog at v37 | `ls Project_Backlog_v*.md \| sort -V \| tail` | ✅ v37 latest |
| CLAUDE.md Backlog ref reads `Project_Backlog_v37.md` | `grep -n` | ✅ |
| CLAUDE.md Layer 4 row reads "PROMPT BODIES 5/5 — **ARC COMPLETE**" | `grep -n` | ✅ |
| `Layer4_Spec.md` §14 stub present at line 1739 | `grep -n "^## 14" Layer4_Spec.md` | ✅ |
| `Layer4_Spec.md` §12.6 references §14 deferral | inline read | ✅ line 1573 |
| Branch `claude/review-design-handoff-jv5Ya` clean off main tip `9fa919c` (PR #66 merge) | `git status` + `git log` | ✅ |
| Latest predecessor handoff is race-week-brief | `ls handoffs/V5_Design_Layer4_Prompts_*` | ✅ |

**Drift found:**
- Predecessor race-week-brief handoff §1 already flagged a line-count drift in the T1/T2 predecessor handoff (claimed RefreshT2 ~750 lines; actual 570). Not new this session; surfaced again only as inherited context.
- During the §14 audit (see §3 below), 18 findings were catalogued in total (5 cosmetic + 10 load-bearing + 3 contract-gap). These were existing drift in the spec arc that the retro is meant to surface — not session-start drift in the sense of a handoff-narrative mismatch with on-disk state.

Andy picked **Layer 4 §14 retrospective** via `AskUserQuestion` at session start (rejected Layer 4 implementation track / v5 onboarding implementation / critical-review-of-race-week-brief-handoff as next-track candidates).

---

## 2. Session narrative — three architectural picks

After session-start verification + reading the full `Layer4_Spec.md` (1747 lines) + all 5 prompt body files (~3978 lines total) + cross-referencing the 3 amendment-round handoff narratives, the architect (Claude) presented three architectural picks to Andy via `AskUserQuestion`:

### 2.1 Pick 1 — Retro shape

Options presented:
- (a) **Combined: audit + gut-check + readiness gate.** §14.1 audit findings (drift / gaps / amendment ripple effects across §§1–13 + 5 prompt bodies, classified cosmetic / load-bearing / contract-gap); §14.2 gut check (what's right / risks / missing / argument against — matches 14-section template); §14.3 implementation readiness gate (what's stable, what's ambiguous, recommended sequencing, what implementation should validate early). Audit gives the retro teeth; gut-check gives directional read; readiness gate hands off to the now-unblocked implementation track. ~250–400 lines. **Architect-recommended.**
- (b) Pure gut-check §14 (4 subsections — what's right / risks / missing / argument against). Tight, matches the spec's preview text + the 14-section template style. Audit findings folded into "risks" as bullets or trickled into the backlog. Lighter touch, ~120–180 lines. Risks under-delivering on the handoff §5.1 audit ask.
- (c) Two-artifact split — pure gut-check §14 in spec + separate `Layer4_Spec_Audit_v1.md` for the consistency audit. Maximum scoping clarity but doubles file count (and `Layer4_Spec_Audit_v1.md` would be a one-off artifact category).

**Andy picked (a) — combined.** Took the architect's recommendation.

### 2.2 Pick 2 — Findings policy

Options presented:
- (a) **Catalog inline; classify; defer fixes.** Audit section enumerates each finding + classifies (cosmetic / load-bearing / contract-gap). Surgical fixes proposed inline for cosmetic ones; load-bearing flagged for follow-on spec amendments; contract gaps escalated to stop-and-ask. Retro WRITES findings, doesn't unilaterally amend other sections. Andy decides what gets fixed in-session vs follow-on. Keeps file ceiling clean. **Architect-recommended.**
- (b) Mechanically amend everything in same session. Findings get mechanical str_replace fixes against §§1–13 in this same session. Aggressive; risks scope explosion past 5-file ceiling; sweeps amendment ripple effects + cosmetic drift in one pass.
- (c) Catalog only, no classification. Enumerate findings without ranking severity. Lowest opinionation; least useful for prioritization.

**Andy picked (a) — catalog + classify + defer.** Took the architect's recommendation.

### 2.3 Pick 3 — Implementation readiness gate

Options presented:
- (a) **Include as §14.3.** Brief subsection: stable contracts / ambiguous-but-tolerable / what implementation should validate against early / recommended sequencing. Lands the retro right at the spec→code boundary. Race-week-brief handoff §5.1 already promised the implementation track "gets the benefit of the second-mind read" — readiness gate is the literal handoff artifact. **Architect-recommended.**
- (b) Defer to a separate implementation-kickoff document. §14 stays pure-evaluation; readiness gate lands as its own artifact when implementation track activates. Cleaner separation but loses the spec-arc-to-code-arc bridge.

**Andy picked (a) — include as §14.3.** Took the architect's recommendation.

### 2.4 Stop-and-ask gates honored

3 contract gaps (C1 + C2 + C3) were surfaced during the audit. Per Andy's Pick 2 (catalog + classify + defer), the retro WRITES the findings + classifications but does NOT mechanically apply fixes. C1 (§5.4 validator rule table missing rules referenced by prompt bodies) + C2 (§7.12 phase_metadata override-pass-through undefined) are spec gaps warranting follow-on amendment session. C3 (`Layer4ShapeInfeasibleError` orchestrator routing) is explicitly orchestrator-side per §12.3 + §10.2 — not a Layer 4 spec gap.

No further stop-and-ask triggers fired during execution. The audit + gut check + readiness gate all stay within "retro authoring" scope; no §§1–13 edits were mechanically applied; no prompt body files were touched.

---

## 3. What landed per file

### 3.1 `aidstation-sources/Layer4_Spec.md` — §14 replaced (~190 lines)

Replaced the 4-paragraph "Gut check — deferred to follow-on session" stub at lines 1739–1743 with substantive §14 retrospective content. Three subsections:

- **§14 header** — drafting date 2026-05-17; references §12.6 deferral; notes the 3 architectural picks (combined / catalog+classify+defer / include readiness gate); confirms findings are catalogued + classified + fixes deferred (not mechanically applied).
- **§14.1 audit findings — drift / gaps / amendment ripple effects across §§1–13 + 5 prompt bodies.** Classified by severity:
  - **§14.1.1 cosmetic** — 5 findings (A1: test scenario prefix inconsistency across prompt bodies; A2: test-scenario count miss in race-week-brief handoff §5.1; A3: `opportunities` maxItems variance; A4: `phase_synthesis_notes` JSONB consumer unwired; A5: §13 doesn't enumerate per-tier T1/T2 scenarios).
  - **§14.1.2 load-bearing** — 10 findings (B1: `StrengthExercise.coaching_flags` closed-vs-open inconsistent; B2: §13 plan_refresh scenarios don't reflect `intensity_modulated` broadening on TS-23/TS-24; B3: `RacePlan.segments` cap defined in prompt not spec; B4: cache key naming variance; B5: per-phase D9 + §13 missing validator rules pattern broader than per-phase; B6: `coaching_intent` cap inconsistency 200 vs 240; B7: race-week-brief `duration_min` 240 cap is implicit Taper ceiling; B8: race-week-brief `rest_reason` 3-value subset of §7.2's 5-value enum; B9: §11.5 cumulative cost ceilings don't account for race-week-brief daily-regen pattern; B10: extended_thinking budgets not in §11.2 token table).
  - **§14.1.3 contract gaps — stop-and-ask candidates** — 3 findings:
    - **C1** §5.4 validator rule table missing ~7 rules referenced by prompt bodies (5 from race-week-brief: `taper_phase_intent_violation_*`, `kit_manifest_inputs_incomplete`, `race_plan_segments_unordered_*`, `fueling_strategy_2e_tier_mismatch_*`, `contingency_anchor_category_missing_*`; 2 from per-phase: `phase_date_out_of_range_*`, daily-window-fit). Blocks Step 3 validator harness.
    - **C2** §7.12 `phase_metadata` override-pass-through semantics undefined. Race-week-brief is Pattern B (per §7.12 → phase_metadata=None) but it MODIFIES pre-existing Pattern-A-produced Taper sessions whose `phase_metadata` should be preserved. Prompt's interpretation is reasonable but spec doesn't sanction it. Blocks Step 4e race-week-brief integration.
    - **C3** `Layer4ShapeInfeasibleError` orchestrator routing — explicitly orchestrator-side per §12.3 + §10.2; not a Layer 4 spec gap. Resolve at implementation-track kickoff.
  - **Amendment-round ripple effects trail:** D-63 sport-unavailable amendments clean ✅; `intensity_modulated` broadening §13 ripple partial ⚠️ (TS-23 / TS-24 don't reference the flag despite broadened trigger applying); race-week-brief 0-amendment session confirmed ✅ but the session surfaced 2 pre-existing contract gaps (C1 + C2 — not introduced by race-week-brief, just exposed by it).
- **§14.2 gut check** — 4 subsections per the 14-section template:
  - §14.2.1 what this spec gets right (8 items — discriminated-union PlanSession; per-phase+seam-reviewer architecture; 4 entry points; closed-set flag taxonomy + LLM-emitted/spec-auto split; shape_override narrow + bounded; capped retry + best-effort acceptance; cache + per-call rebinding; 3 amendment rounds shipped without ripple).
  - §14.2.2 risks (8 items — sequential per-phase forecloses parallelism; seam-reviewer authority calibration unmeasured; cost projections unmeasured; intensity-distribution defaults are policy not data; §5.4 validator rule list incomplete per C1; `intensity_modulated` under-emission failure mode; closed-set flag phase-applicability is prompt-only; spec approaching 2100-line maintenance edge).
  - §14.2.3 what might be missing (9 items — joint sessions; Layer 5 contract; D-57; post-race surface; brief-diff renderer; §7.12 phase_metadata gap per C2; §5.4 rule rows per C1; opportunity expansion; seam-reviewer concurrency).
  - §14.2.4 best argument against this spec's scope (4-entry-point complexity multiplier — counter: empirically validated by the prompt-body arc — 3 different file-scope picks per prompt body would collapse into one mega-prompt rats-nest under a unified-with-mode-discriminator architecture; amendment-round empirical evidence shows surface-area boundaries held).
- **§14.3 implementation readiness gate** — 6 subsections:
  - §14.3.1 stable contracts (build against these directly) — enumerates §§3, 4, 5.1–5.5, 6, 7 (minus C2 gap), 8.1–8.7, 9, 11 + all 5 prompt bodies.
  - §14.3.2 ambiguous-but-tolerable (implementation can proceed; resolve when telemetry surfaces patterns) — 6 items (T3-intra-phase routing; race-week-brief auto-fire cadence; Layer4ShapeInfeasibleError routing per C3; StrengthExercise.coaching_flags open vs closed; phase_synthesis_notes JSONB structure; brief-diff renderer + opportunity expansion).
  - §14.3.3 what implementation should validate early (potential blockers) — C1 + C2 amendments before validator harness; cache hit-rate telemetry with cache layer; cost telemetry per §11.5; per-prompt-body regression test suite; `intensity_modulated` under-emission monitoring.
  - §14.3.4 recommended 8-step sequencing — Step 1 spec amendment session (C1 + C2; ~3-5 files under ceiling); Step 2 `plan_versions` table migration + payload schema scaffolding (parallelizable with Step 1); Step 3 deterministic validator harness (needs C1); Step 4a–4f per-entry-point call-site code (4a single-session simplest first; 4d plan_create biggest depends on Step 6; 4e race-week-brief depends on C2); Step 5 cache layer; Step 6 Pattern A orchestration; Step 7 live LLM integration; Step 8 T3-intra-phase + auto-fire policy + error routing picks.
  - §14.3.5 implementation observability requirements — per-call telemetry (§7.1 fields); cache observability per §9.6; validator observability; coaching flag emission observability (`intensity_modulated` emission rate is the load-bearing signal under refresh paths); schema-violation observability; cost observability against §11.5 cumulative ceilings.
  - §14.3.6 pre-implementation gate checklist — 5 checkboxes including C1 + C2 amendments landed; implementation team has read §14 + 5 prompt bodies + key spec sections; D-63 + D-64 caller-side designs confirmed unblocked; §K availability-window schema migration-ready; D-63/D-64/Layer-4.5 ordering confirmed by Andy.
- **§14.4 summary** — Layer 4 spec is implementation-ready with C1 + C2 amendments warranted; 5-prompt-body arc surfaced no spec contract gaps (3 amendment rounds landed cleanly with one §13 ripple gap B2); 4-entry-point + Pattern A/B architecture validated empirically; closed-set coaching flag taxonomy is most load-bearing convention; recommended next move = focused amendment session before Step 3 validator harness; Steps 1 + 2 can proceed in parallel.

Closing italics block updated to reflect §§1–14 complete + arc total (4 design sessions + 2 mid-arc calibration + 3 prompt-body-paired amendments + this fresh-eyes §14).

### 3.2 `aidstation-sources/CLAUDE.md` — narrative bump + state update

- **Layer 4 row** in layer-pipeline table updated from "SPEC v1 DONE (§§1–13 + 3 amendments; §14 retro deferred); PROMPT BODIES 5/5 — ARC COMPLETE" → "SPEC §§1–14 COMPLETE (§§1–13 + 3 amendments + §14 retrospective); PROMPT BODIES 5/5 — ARC COMPLETE. **§14 retro flags 2 contract gaps as stop-and-ask for next amendment session (C1 §5.4 / C2 §7.12).** Implementation fully unblocked."
- **Last shipped session** narrative rewritten from race-week-brief to §14 retro — full coverage of the 3 architectural picks (combined / catalog+classify+defer / include readiness gate); §14.1 audit findings summary (5 cosmetic / 10 load-bearing / 3 contract-gap; amendment ripple-effect trail); §14.2 gut check summary; §14.3 readiness gate summary; 3 contract gaps explicitly named (C1 + C2 + C3); recommended next session framing; file count (4 under ceiling).
- **Predecessor** demoted to race-week-brief (preserves the original predecessor chain — race-week-brief → T1/T2 → PR19 → PR18 → single-session → per-phase → seam-reviewer → Layer 4 spec v1 → PR17 → PR16 → PR15 → PR14).
- **"Backlog: `Project_Backlog_v37.md`"** → **"`Project_Backlog_v38.md`"**.
- **Authoritative current files** entry: "Layer 4 done (v1; §14 retro pending): `Layer4_Spec.md`" → "Layer 4 done (v1; §§1–14 COMPLETE — §14 retro shipped 2026-05-17 with C1+C2 contract-gap amendments flagged as recommended next): `Layer4_Spec.md`".
- **Next forward move** rewritten — drops the §14 retro candidate; new top candidate is the C1 + C2 amendment session (architect-recommended; ~3-5 files; 1-2 days; blocks Step 3); Layer 4 implementation track now framed with explicit 8-step sequencing reference + Steps 1+2 parallelizable note; full implementation track described as fully unblocked pending C1 + C2.

### 3.3 `aidstation-sources/Project_Backlog_v38.md` — new (v37 → v38)

v38 header revision entry: full §14 retro session narrative including 3 architectural picks, audit-findings classification summary, 3 contract gaps (C1 + C2 + C3) detailed with the specific validator rule names + override-pass-through semantics + orchestrator-routing escalation, recommended next session framing, file count (4 under ceiling), spec line count (~2100 = ~1747 before + ~350 §14 content). v37 entry moved to predecessor revisions list. Body (line 8+) byte-identical to v37 per Rule #12.

### 3.4 `aidstation-sources/handoffs/V5_Design_Layer4_Spec_Section14_Retrospective_Closing_Handoff_v1.md` — new (this file)

Session-end bookkeeping per the handoff convention.

---

## 4. Files shipped this session

All on branch `claude/review-design-handoff-jv5Ya`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Layer4_Spec.md` | Edit | §14 stub (4 paragraphs) replaced with substantive §14 retrospective (~190 lines, 3 subsections + summary). Closing italics block updated. |
| 2 | `aidstation-sources/CLAUDE.md` | Edit | Layer 4 row + last-shipped-narrative bump + Backlog ref v37 → v38 + authoritative-current-files Layer 4 entry + Next-forward-move rewrite |
| 3 | `aidstation-sources/Project_Backlog_v38.md` | New (v37 → v38) | v38 header revision entry; v37 entry moved to predecessor list; body byte-identical |
| 4 | `aidstation-sources/handoffs/V5_Design_Layer4_Spec_Section14_Retrospective_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping |

**5-file ceiling status:** 4 files (under ceiling). Same envelope as the race-week-brief session. Substantive surface area: 1 spec section replaced (~190 lines of new content). Bookkeeping is the standard 3-file pattern per spec-session cadence (CLAUDE.md + backlog v-bump + closing handoff).

**Not touched this session** (intentional per Andy's Pick 2 = catalog + classify + defer):

- `Layer4_Spec.md` §§1–13 — the audit catalogues findings against these sections but proposes fixes via a follow-on focused amendment session (C1 + C2 specifically). No mechanical str_replace edits applied during the retro authoring. Other findings (cosmetic + load-bearing) also catalogued but not fixed in-session.
- All 5 prompt body files in `aidstation-sources/prompts/` — audit reads them; no edits made. Findings A1 (test prefix), A3 (opportunities cap), B1 (StrengthExercise.coaching_flags), B6 (coaching_intent cap) would touch prompt files when fixed; deferred to follow-on prompt-body revision sessions.
- `OnDemand_Workout_D63_Design_v1.md`, `Plan_Refresh_D64_Design_v1.md` — D-63 + D-64 caller specs untouched. The §14.3 implementation readiness gate references these as orchestrator-side coordination points but doesn't amend them.
- Other layer specs (Layer 3A, Layer 3B, etc.) — untouched. Layer 4 §14 retro scope is Layer 4 only.

---

## 5. Standing items / open flags

### 5.1 C1 + C2 spec amendment session — most-load-bearing next move

§14.1.3 catalogues C1 + C2 as the two contract gaps that should block implementation. **C1**: §5.4 validator rule table missing ~7 rules referenced by prompt bodies. **C2**: §7.12 `phase_metadata` override-pass-through semantics undefined for race-week-brief's Pattern-B-output-modifying-Pattern-A-produced-sessions case.

**Mechanically applicable edit specs (per Rule #11):**

**For C1** — add the following rows to the `Layer4_Spec.md` §5.4 validator rule table (after line 829 `sport_locale_incompatible_*` row):

```
| Taper-phase intent violation | `taper_phase_intent_violation_*` | Per session (race-week-brief mode) | Race-week-brief `taper_session_overrides[]` whose modified intensity / duration / kind violates Taper phase intent per `Layer4_Spec.md` §8.5 (e.g., `intensity_summary='hard'` on `days_to_event ≤ 2` session; long-duration session within 48h of event). Severity: `blocker`. |
| Kit manifest inputs incomplete | `kit_manifest_inputs_incomplete` | Per call (race-week-brief mode) | Per `Layer4_Spec.md` §4.5 row 7 soft-warning: when `race_format != 'single_day'` AND no locale in the route has `equipment_overrides` populated. Severity: `warning` (soft — does not raise; emits `data_gap` notable_observation; kit_manifest synthesis degrades gracefully). |
| Race plan segments unordered | `race_plan_segments_unordered_*` | Per call (race-week-brief multi-day) | `RacePlan.segments[]` not chronologically ordered (segment_index gaps OR `estimated_start_offset_hr` not monotonically increasing). Severity: `blocker`. |
| Fueling strategy 2E tier mismatch | `fueling_strategy_2e_tier_mismatch_*` | Per call (race-week-brief multi-day) | `RacePlan.fueling_strategy.cho_g_per_hr_low/high` outside the 2E race-day fueling tier band; `sodium_mg_per_hr` outside tier band; `fluid_ml_per_hr` outside tier band. Severity: `blocker`. |
| Contingency anchor category missing | `contingency_anchor_category_missing_*` | Per call (race-week-brief mode) | `RaceWeekBrief.contingencies` or `RacePlan.contingencies` missing a category required by the D6 mixed-contingency anchor table for the race_format (any race: GI / hydration / mechanical-or-gear-failure; AR + ultra: nav / sleep-dep / weather; stage races: between-stage recovery; multi-day: cumulative fatigue + crew-pacing-mismatch). Severity: `warning`. |
| Phase date out of range | `phase_date_out_of_range_*` | Per session (plan_create + Pattern-A T3) | `PlanSession.date` outside `phase_start_date → phase_end_date` (inclusive) for the phase being synthesized. Severity: `blocker`. Promoted from `Layer4_PerPhase_v1.md` §11 row 14 prompt-only enforcement. |
| Daily window fit | `daily_window_fit_*` | Per session (all entry points emitting `PlanSession`) | `PlanSession.duration_min` exceeds the available `daily_availability_windows` minutes for `PlanSession.date`. Severity: `blocker`. Promoted from `Layer4_PerPhase_v1.md` §11 row 12 prompt-only enforcement. |
```

**For C2** — amend `Layer4_Spec.md` §7.12 `PlanSession.phase_metadata` schema rule (currently at line 553):

```
- `PlanSession.phase_metadata` non-None when the producer was `plan_create` or Pattern-A `plan_refresh`; None for Pattern-B refreshes (no phase decomposition) and for `single_session_synthesize`.
```

Replace with:

```
- `PlanSession.phase_metadata` non-None when the producer was `plan_create` or Pattern-A `plan_refresh`; None for Pattern-B `plan_refresh` (T1, T2, T3 intra-phase — no phase decomposition) and for `single_session_synthesize`. **Race-week-brief override-pass-through:** when `race_week_brief` modifies pre-existing Taper-phase sessions from `prior_plan_session_window`, the modified session's `phase_metadata` is preserved verbatim from the prior-plan session (which carries the original `plan_create` or Pattern-A `plan_refresh` metadata). Race-week-brief does NOT produce new `PlanSession` rows in v1 (it only modifies existing ones); if it did, those new rows would follow the Pattern-B default of `phase_metadata=None`.
```

**Estimated file count for C1 + C2 amendment session:** 4 files (1 substantive `Layer4_Spec.md` + 3 bookkeeping). Optionally bundle the load-bearing findings (B1–B10 per §14.1.2) if scoping allows — would push toward 5 files under ceiling.

**Trigger to advance:** Andy picks as next-session focus. **Recommended next move per §14.3.4 step 1.**

### 5.2 Layer 4 implementation track — fully unblocked

Per §14.3 readiness gate. Steps 1 + 2 (table migration + payload schema scaffolding) can proceed in parallel with the C1 + C2 amendment session — they don't depend on the validator rule set. Step 3 (deterministic validator harness) needs C1. Steps 4a–4f + 5 + 6 + 7 + 8 follow the 8-step sequencing in §14.3.4.

**Implementation scope to plan** (per §14.3.4):
- Step 1: spec amendment session (C1 + C2). See §5.1 above.
- Step 2: `plan_versions` table SQL migration per §7.11 + dataclass scaffolding for `Layer4Payload` / `PlanSession` / sub-blocks / `RaceWeekBrief` / `RacePlan` + canonical-JSON serialization helpers (cache key inputs). One PR.
- Step 3: deterministic validator harness per §5.4 (post-Step-1-amendment); pure-function rule set; per-rule pytest fixtures. One PR.
- Step 4 (a–f): per-entry-point call-site code. One PR per entry point. Recommended order: 4a single-session → 4b T1 → 4c T2 → 4d plan_create (depends on Step 6) → 4e race-week-brief (depends on C2 amendment) → 4f T3.
- Step 5: cache layer (orchestrator-side; per §9). One PR.
- Step 6: Pattern A orchestration (§5.2 + §6.2 + §6.3). One PR.
- Step 7: live LLM integration testing against PSS-prefix scenarios. Per-entry-point PR or combined.
- Step 8: T3-intra-phase routing decision + race-week-brief auto-fire policy + `Layer4ShapeInfeasibleError` routing (C3). Telemetry-informed.

### 5.3 NL intent parser prompt body — separate D-64-internal track

Per `Plan_Refresh_D64_Design_v1.md` §2 Decision 12 + §10 (carried from predecessor handoff §5.3): the NL parser prompt body that produces the `ParsedIntent` schema is **not** part of the 5-prompt Layer 4 arc. It's a D-64-internal prompt called upstream of Layer 4. T1/T2 + race-week-brief consume `parsed_intent` as input.

**Trigger to advance:** D-64 implementation track activates + the parser is needed for runtime NL classification.

### 5.4 §13 plan_refresh test scenarios partial ripple (finding B2)

§13.3 TS-23 (T2 schedule edit) + TS-24 (T3 intra-phase "harder") don't reference `intensity_modulated` despite the broadened §8.6 trigger applying. Worth a §13 sweep when amendments land in §5.1 above. Could be folded into the C1+C2 amendment session as a B-finding bundle.

### 5.5 Race-week-brief integration with D-64 NL refresh — coordination point

(Carried from race-week-brief handoff §5.4.) When athlete fires a race-week NL refresh ("drop tomorrow's race-rehearsal") via D-64 during race week, the brief's `taper_session_overrides[]` interacts with `plan_refresh` T1/T2's output. Coordination contract: the more-recent fire wins per `Layer4_Spec.md` §7.11 per-day pointer; brief's Taper overrides supersede T1's same-date overrides if brief fires after T1. Confirm during D-64 implementation.

### 5.6 Spec-auto Taper flag stamping timing — implementation-side verification

(Carried from race-week-brief handoff §5.5.) If the orchestrator stamps `race_rehearsal` on a session that the brief intended NOT to be a rehearsal (because the brief shifted the rehearsal to a different day), there's a mismatch. Needs implementation verification when the call-site code lands.

### 5.7 Brief-diff renderer for incremental re-fires — defer to brief UI build

(Carried from race-week-brief handoff §5.6.) Currently each daily brief regeneration is from-scratch (midnight-UTC cache invalidation forces this); an incremental "what's changed since yesterday's brief" surface would reduce athlete cognitive load. Defer until brief UI is built + telemetry shows daily-regen burden.

### 5.8 Carry-forward from prior sessions

- **PR18 §5.0 — 12 walks owed.** Unchanged; pending Vercel deploy + walk.
- **PR19 §5.0 — 11 walks owed.** Unchanged; pending Vercel deploy + walk.
- **PR11 step 6 — re-walkable + flippable ✅ once PR18 deploys** (unblocked by PR18 item B's `/retrieve` refresh).
- **Park-specific tag taxonomy follow-up** (PR18 §5.2 → carried forward) — still deferred. Trigger: Andy starts using park locales for real sessions.
- **Trip-locale taxonomy decoupling** (PR19 handoff §5.2) — still deferred. Defer-trigger: Andy wants to save specific travel destinations as locales for trip-row picking.
- **v1 coaching form replacement** (PR19 handoff §5.3) — still scheduled for v2 LLM-pipeline cutover. PR19's form-level guard + athlete-locale-aware dropdown work will be thrown away when v2 ships.
- **T1/T2 open items §5.4 / §5.5** (validator coordination for sickness-signal demotion; `overreach_test` with athlete pullback potential §8.3 amendment) — still deferred; lands when validator implementation surfaces. These could fold into the C1 + C2 amendment session as B-finding bundles.

---

## 6. Forward pointers

**Next session:** Andy's choice. With the Layer 4 spec arc COMPLETE §§1–14, the recommended next move per §14.3.4 step 1 is the C1 + C2 amendment session. Candidates:

- **Layer 4 spec amendment session — C1 + C2 (architect-recommended next per §14.3.4)** — focused amendment PR resolving the 2 contract gaps per §5.1 above. Mechanically applicable edit specs included in §5.1 for both rules. ~3-5 files under ceiling; 1-2 days. Optionally bundle the load-bearing findings (B1–B10 per §14.1.2 + finding B2's §13 ripple sweep) if scoping allows. **Blocks Step 3 of implementation sequencing.**
- **Layer 4 implementation track Steps 1 + 2** — `plan_versions` table SQL migration + payload schema scaffolding can proceed in parallel with the C1 + C2 amendment session (no validator dependency). Foundational; would start the implementation track concretely. ~2-3 PRs.
- **Layer 4 implementation track Step 4a — `llm_layer4_single_session_synthesize` (D-63)** — single-session is the simplest entry point per §14.3.4; D-63 caller is implementation-pending and now ready for the Layer 4 integration. Depends on Steps 2 + 3 landing first.
- **v5 onboarding implementation PR** — substantial code work per `Plan_Refresh_D64_Design_v1.md` §7 storage + `Athlete_Onboarding_Data_Spec_v5.md` §J locale-system carry-forwards. Independent of Layer 4 implementation; can run in parallel.
- **D-50 wiring resumption** — COROS OAuth + webhook recording (now unblocked by D-58).
- **PR18 follow-on — park-specific tag taxonomy** — defer-trigger as flagged in §5.8.
- **Layer 4.5 — Joint Session Coordinator spec** — separate file; post-pass over linked athletes' Layer 4 payloads. Lands when team-features track activates.
- **Layer 5 spec** — parallel supplemental outputs (nutrition, supplements, 7-day clothing/conditions). Consumes `PlanSession.session_notes` + `cardio_blocks` + race-week brief contents per §12.3 forward-pointer.

**Before the next session:**

1. **Read `aidstation-sources/CLAUDE.md` fully** (Rule #13). Last-shipped narrative now leads with the §14 retro session; Backlog ref now points at v38; Layer 4 row reads "SPEC §§1–14 COMPLETE" with the C1 + C2 flag visible.
2. Read this handoff in full.
3. (Optional) Re-read predecessor closing handoffs: `V5_Design_Layer4_Prompts_RaceWeekBrief_Closing_Handoff_v1.md` (immediate predecessor — race-week-brief session whose §5.1 promised the second-mind retrospective this session delivered).
4. (If picking the C1 + C2 amendment session) Read `Layer4_Spec.md` §14.1.3 + the mechanically-applicable edit specs in this handoff §5.1. Spot-check race-week-brief prompt §11.1 + per-phase prompt §11 to confirm the rule-name catalog is complete.
5. (If picking Layer 4 implementation Steps 1 + 2) Read `Layer4_Spec.md` §3 (call signatures) + §7 (payload schema; especially §7.11 `plan_versions` table SQL) + §9 (caching) + §14.3.4 sequencing.

**Rules in force, unchanged:**

- #9 session-start verification — applied (see §1 above); branch state confirmed clean off main; race-week-brief ship verified; 5 prompt bodies + 1 Layer 4 spec all on disk.
- #10 session-end verification — applied (see §7 below).
- #11 mechanically-applicable deferred edits — C1 + C2 amendment specs included in §5.1 with full new-text blocks for both new §5.4 rule rows + the §7.12 schema-rule replacement.
- #12 numeric version suffixes — Backlog now at v38; next state-changing event bumps v38 → v39. `Layer4_Spec.md` not renamed (still v1; §14 was always part of the v1 spec scope per the 14-section template; this session completes v1 rather than starting v2).
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §6 first-action explicitly names CLAUDE.md.

---

## 7. Session-end verification (Rule #10)

Final pass over each claimed file edit before composing this handoff:

| Check | Result |
|---|---|
| `Layer4_Spec.md` §14 stub replaced (no longer reads "Gut check — deferred to follow-on session") | ✅ §14 header now reads "§14 retrospective — fresh-eyes audit + gut check + implementation readiness gate" |
| `Layer4_Spec.md` §14 has subsections §§14.1, 14.2, 14.3, 14.4 | ✅ |
| `Layer4_Spec.md` §14.1 has subsections §§14.1.1 cosmetic, 14.1.2 load-bearing, 14.1.3 contract gaps | ✅ |
| `Layer4_Spec.md` §14.1.3 catalogues C1 + C2 + C3 with rule names + override-pass-through semantics + orchestrator-routing rationale | ✅ |
| `Layer4_Spec.md` §14.2 has subsections §§14.2.1 right, 14.2.2 risks, 14.2.3 missing, 14.2.4 argument-against | ✅ |
| `Layer4_Spec.md` §14.3 has 6 subsections (stable / ambiguous / validate-early / sequencing / observability / checklist) | ✅ |
| `Layer4_Spec.md` closing italics block references §§1–14 complete | ✅ |
| `CLAUDE.md` Layer 4 row reads "SPEC §§1–14 COMPLETE" with C1 + C2 mention | ✅ |
| `CLAUDE.md` last-shipped-narrative leads with §14 retro session | ✅ |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v38.md` | ✅ |
| `CLAUDE.md` Authoritative-current-files Layer 4 entry reads "§§1–14 COMPLETE" | ✅ |
| `CLAUDE.md` Next-forward-move leads with C1 + C2 amendment session as architect-recommended | ✅ |
| `Project_Backlog_v38.md` exists | ✅ |
| `Project_Backlog_v38.md` line 5 starts with `**File revision:** v38 — 2026-05-17 (**Layer 4 spec §14 retrospective shipped` | ✅ |
| `Project_Backlog_v38.md` has single `**Predecessor revisions:**` header at line 6 (not duplicated) | ✅ `grep -c` returns 1 |
| `Project_Backlog_v38.md` line 7 starts with `- v37 — 2026-05-17 (**Layer 4 race-week-brief` | ✅ |
| 1 substantive spec edit + 3 bookkeeping = 4 files this session | ✅ |
| All edits land on branch `claude/review-design-handoff-jv5Ya` | ✅ |

---

## 8. Carry-forward from PR18 + PR19 + Layer 4 arc (informational)

- **PR18 §5.0** — 12 testable steps owed; pending Vercel deploy + walk.
- **PR19 §5.0** — 11 testable steps owed; pending Vercel deploy + walk.
- **PR11 step 6** — re-walkable + flippable to ✅ once PR18 deploys (unblocked by PR18 item B).
- **Layer 4 prompt-body arc** — 5 of 5 shipped (seam-reviewer + per-phase + single-session + per-tier T1/T2 + race-week-brief). **ARC COMPLETE.**
- **Layer 4 spec arc** — §§1–14 COMPLETE as of this session. §§1–13 + 3 amendment rounds (D-63 sport-unavailable in single-session, `intensity_modulated` broadening in T1/T2, no amendment in race-week-brief) + §14 retrospective (this session).
- **Layer 4 §14 retrospective** — shipped this session; catalogues C1 + C2 + C3 contract gaps. **Recommended next move:** focused C1 + C2 amendment session before Step 3 validator harness lands. Implementation Steps 1 + 2 (table migration + payload schema scaffolding) can proceed in parallel.
- **Layer 4 implementation track** — fully unblocked pending C1 + C2 amendments per §14.3.4. 8-step sequencing in `Layer4_Spec.md` §14.3.4.
- **Park-tags follow-up** — still deferred per PR18 §5.2.

---

---

## 9. Mid-session bundle — C1 + C2 + B2 + B9 + B10 amendments applied in-session

Andy's mid-session question ("do we have room to knock out anything here") opened a Pick-2 reversal opportunity: the retro WROTE + classified the findings per Andy's earlier defer-fixes posture, but the retro authoring + bookkeeping landed at 4 files (one under the 5-file ceiling). Surfaced 4 bundle scopes via `AskUserQuestion`; Andy picked the most aggressive: **C1 + C2 + B2 + B9 + B10** — all inside `Layer4_Spec.md` (no prompt-body files touched; no new files added). Reverses Pick 2 for the 2 contract gaps + 3 load-bearing findings; the remaining cosmetic + load-bearing findings stay deferred to a future amendment session.

### 9.1 Amendments applied

**C1 — §5.4 validator rule table additions (7 new rows after the `sport_locale_incompatible_*` row):**

- `taper_phase_intent_violation_*` — race-week-brief Taper-session overrides violating Taper phase intent per §8.5 (e.g., `intensity_summary='hard'` on `days_to_event ≤ 2` session; long-duration session within 48h of event). Per session (race-week-brief mode). Severity: `blocker`.
- `kit_manifest_inputs_incomplete` — per §4.5 row 7 soft-warning: when `race_format != 'single_day'` AND no locale in the route has `equipment_overrides` populated. Per call (race-week-brief mode). Severity: `warning` (soft — does not raise; emits `data_gap` notable_observation; kit_manifest synthesis degrades gracefully).
- `race_plan_segments_unordered_*` — `RacePlan.segments[]` not chronologically ordered (segment_index gaps OR `estimated_start_offset_hr` not monotonically increasing). Per call (race-week-brief multi-day). Severity: `blocker`.
- `fueling_strategy_2e_tier_mismatch_*` — `RacePlan.fueling_strategy.cho_g_per_hr_low/high` outside the 2E race-day fueling tier band; `sodium_mg_per_hr` outside tier band; `fluid_ml_per_hr` outside tier band. Per call (race-week-brief multi-day). Severity: `blocker`.
- `contingency_anchor_category_missing_*` — `RaceWeekBrief.contingencies` or `RacePlan.contingencies` missing a category required by the race-week-brief D6 mixed-contingency anchor table for the race_format. Per call (race-week-brief mode). Severity: `warning`.
- `phase_date_out_of_range_*` — `PlanSession.date` outside `phase_start_date → phase_end_date` (inclusive) for the phase being synthesized. Per session (plan_create + Pattern-A T3). Severity: `blocker`. Promoted from `Layer4_PerPhase_v1.md` §11 row 14 prompt-only enforcement.
- `daily_window_fit_*` — `PlanSession.duration_min` exceeds the available `daily_availability_windows` minutes for `PlanSession.date`. Per session (all entry points emitting `PlanSession`). Severity: `blocker`. Promoted from `Layer4_PerPhase_v1.md` §11 row 12 prompt-only enforcement.

**C2 — §7.12 `PlanSession.phase_metadata` schema rule amended** with the race-week-brief override-pass-through clause: when race-week-brief modifies pre-existing Taper-phase sessions from `prior_plan_session_window`, the modified session's `phase_metadata` is preserved verbatim from the prior-plan session (which carries the original `plan_create` or Pattern-A `plan_refresh` metadata). Race-week-brief does NOT produce new `PlanSession` rows in v1 (it only modifies existing ones); if it did, those new rows would follow the Pattern-B default of `phase_metadata=None`. Resolves the §14.1.3 C2 contract gap surfaced by the §14 retro.

**B2 — §13.3 plan_refresh test scenarios** TS-23 / TS-24 / TS-25 expected-output language updated to reference `intensity_modulated` emission per the broadened §8.6 trigger covering refresh-path modulation against `parsed_intent` direction or 3A signals. TS-22 + TS-32 already referenced the flag pre-broadening; TS-26 / TS-31 are 3B-shape-shift / no-intent cases where the flag doesn't naturally apply.

**B9 — §11.5 cumulative ceilings** gains a race-event cumulative line item: race_week_brief daily regenerations across the race-week (midnight-UTC cache invalidation per §9.3 forces fresh synthesis each day) add a per-race-event burst pattern not captured by the daily/weekly/monthly ceilings. Typical multi-day race: ~$0.18/call × 14 daily fires ≈ ~$2.50 per race-event concentrated in the 2-week race-week window. ~$0.18/day of the $0.50 daily soft cap (well under) but ~30% of the $8 monthly soft cap from race-week-brief alone.

**B10 — §11.2 token budget table** gains an extended_thinking budget per-prompt-body table: SeamReviewer ~2000; SingleSession ~3500; RefreshT1 ~3000; RefreshT2 ~4500; PerPhase ~5000 per phase; RaceWeekBrief ~5500 (highest in pipeline). Plus the note that Sonnet 4.6 bills extended thinking against output cost — a 4-phase plan_create no-retry case carries ~26000 extended-thinking output tokens on top of the ~14400 structured output ≈ ~40400 total output-billed tokens.

### 9.2 What stays deferred

The Pick 2 defer-fixes posture stays in effect for the remaining 13 audit findings (5 cosmetic + 5 load-bearing not bundled). Specifically:

- **Cosmetic** (5 items): A1 (test scenario prefix inconsistency), A2 (handoff-narrative count miss — purely historical drift), A3 (opportunities maxItems variance), A4 (phase_synthesis_notes JSONB consumer unwired), A5 (§13 doesn't enumerate per-tier T1/T2 explicitly).
- **Load-bearing not bundled** (5 items): B1 (StrengthExercise.coaching_flags open-vs-closed inconsistent across prompts), B3 (RacePlan.segments cap defined in prompt not spec), B4 (cache key naming variance), B5 (was equivalent to C1; already covered), B6 (`coaching_intent` cap inconsistency 200 vs 240), B7 (race-week-brief duration_min 240 cap implicit Taper ceiling), B8 (race-week-brief rest_reason subset enum).
- **Contract gap not actionable as a Layer 4 amendment**: C3 (`Layer4ShapeInfeasibleError` orchestrator routing — explicitly orchestrator-side per §12.3).

These remaining findings would touch prompt-body files (B1, B6, B7, B8) or be opportunistic cleanup (A1–A5, B3, B4). They land in a follow-on cleanup session if/when prompt-body revisions happen, or get knocked off opportunistically during implementation.

### 9.3 Net impact on the implementation track

- **Step 3 validator harness** is no longer blocked by C1 — the validator rule table is now complete for the 5 prompt bodies' contract surfaces.
- **Step 4e race-week-brief integration** is no longer blocked by C2 — `phase_metadata` override-pass-through semantics are pinned.
- **Steps 4d (plan_create) + 4f (T3)** benefit from the promoted `phase_date_out_of_range_*` + `daily_window_fit_*` rules (no longer prompt-only enforcement).
- **§13.3 plan_refresh test scenarios** now correctly reflect the broadened §8.6 `intensity_modulated` trigger; per-prompt-body regression test suites can target the updated expected outputs without ambiguity.
- **§11.5 cost-monitor implementation** has the race-event burst pattern explicitly called out — orchestrator-side cost projections should factor it.
- **§11.2 token budget calculations** now include the extended_thinking line items per entry point — cost projections per §11.3 are more accurate; the existing §11.3 cost table remains accurate (the headline numbers already accounted for thinking via the per-prompt-body cost notes in each prompt body's §7).

**The recommended next session changes:** previously the C1 + C2 amendment session was the architect-recommended next move (blocking implementation Step 3). With the bundle applied, the recommended next move is now **Layer 4 implementation Step 1 + 2** — `plan_versions` table SQL migration per §7.11 + payload schema scaffolding per §7. No remaining spec amendments block implementation.

### 9.4 File count + ceiling

Still 4 files (under the 5-file ceiling). The bundle added ~70 net lines to `Layer4_Spec.md` on top of the §14's ~190 net lines (total ~270 net new lines this session across §14 + retro-bundled amendments). The other 3 files (CLAUDE.md, Backlog v38, this handoff) gained narrative updates reflecting the bundle.

### 9.5 Rule #11 — mechanically-applicable status

The mechanically-applicable edit specs originally documented in §5.1 above (for the C1 + C2 amendment session that would have followed this retro) are now **APPLIED** in this session. §5.1 above describes the SAME edits that landed in §9.1 above. The drafted text from §5.1 was the source-of-truth for the actual amendment edits; both match. Future sessions can confirm by reading `Layer4_Spec.md` §5.4 (7 new rule rows after `sport_locale_incompatible_*`) + §7.12 (amended `phase_metadata` schema rule) + §13.3 (TS-23 / TS-24 / TS-25 updated expected outputs) + §11.5 (race-event paragraph appended) + §11.2 (extended_thinking budget table appended).

---

**End of handoff.** Layer 4 spec §14 retrospective shipped + retro-bundled C1+C2+B2+B9+B10 amendments applied in-session — `Layer4_Spec.md` §14 replaced (~190 lines) + ~70 lines of surgical amendments across §5.4 (7 new validator rule rows), §7.12 (phase_metadata override-pass-through clause), §13.3 (TS-23/TS-24/TS-25 intensity_modulated language updates), §11.5 (race-event cumulative line item), §11.2 (extended_thinking budget table) — closing the §12.6-deferred retrospective with combined audit + gut check + implementation readiness gate per Andy's three architectural picks (all three architect recommendations accepted) PLUS the mid-session aggressive-bundle pick reversing Pick 2's defer-fixes posture for the 2 contract gaps + 3 load-bearing findings. **The Layer 4 spec arc is now COMPLETE §§1–14 with all retro-flagged contract gaps resolved.** 18 audit findings catalogued (5 cosmetic + 10 load-bearing + 3 contract-gap); 5 fixed in-session (C1+C2+B2+B9+B10); 13 remain deferred (5 cosmetic + 5 load-bearing not bundled + C3 orchestrator-side). 4 files this session (under the 5-file ceiling — same envelope as the race-week-brief session). Implementation track fully unblocked + ready for Step 1 (no remaining spec amendments). Next forward move: Layer 4 implementation Steps 1 + 2 — `plan_versions` migration + payload schema scaffolding (architect-recommended).
