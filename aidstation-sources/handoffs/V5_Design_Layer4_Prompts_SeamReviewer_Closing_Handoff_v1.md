# V5 Design — Layer 4 Prompt Bodies — Seam Reviewer Closing Handoff

**Session:** First of 5 queued Layer 4 prompt-body design sessions per `Layer4_Spec.md` §12.2 + CLAUDE.md "Next forward move" (post Layer-4-spec-v1 close). Andy picked seam-reviewer first as the smallest learning vehicle, matching the §10.6 + CLAUDE.md framing.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Design_Layer4_Spec_Session4_Closing_Handoff_v1.md` (with §10 close-out addendum — landed the Layer 4 spec v1 arc + bumped CLAUDE.md + backlog v30 → v31; merged via PR #58 at `f0f592b`).
**Branch:** `claude/design-layer-implementation-9kdCe` (cut from `main` at `f0f592b` — the merge commit for the session-4 close-out PR #58).
**Status:** 🟢 Seam-reviewer prompt body drafted at `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md` (436 lines, 14 H2 sections + 8 H3+ subsections). Stop-and-ask trigger #2 invoked + Andy approved all 7 design decisions (D1=tool-use; D2=extended-thinking-on; D3=hybrid-input; D4=coaching-judgment+anchors; D5=constraint-level-only; D6=≤30-words-max-4-entries; D7=new `prompts/` subdir). 🟡 4 prompt bodies still queued (per-phase synthesizer, per-tier T1/T2, single-session D-63, race-week-brief). 🟡 No CLAUDE.md / backlog bump this session — deferred per the v1-commit-deferral precedent carried from the spec arc; lands at end-of-prompt-body-arc (or per-prompt if Andy prefers; see §5).
**Time-on-task:** Single chat. 1 new file (prompt body) + 1 new handoff (this) = 2 substantive files. Well under 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

Predecessor's §10 close-out addendum claimed: `Layer4_Spec.md` at 1746 lines / 96 H2+ headings; §12 with 6 subsections (12.1–12.6); §14 stub re-labeled to "deferred to follow-on session"; CLAUDE.md Layer-pipeline-table Layer 4 row flipped to "SPEC v1 DONE (§§1–13; §14 retro deferred to fresh-eyes session)"; `Project_Backlog_v31.md` created; D-63 + D-64 implementation gates lifted.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `Layer4_Spec.md` 1746 lines, 96 H2+ headings | `wc -l` + `grep -c "^##"` | ✅ |
| §10 (10 subsections), §11 (8), §13 (10) | `grep -cE "^### N\."` | ✅ |
| §12 6 subsections (12.1–12.6) | `grep -nE "^### 12\."` | ✅ — all 6 present at lines 1484/1496/1508/1518/1564/1572 |
| §14 re-labeled "deferred to follow-on session" | `grep -n "^## 14"` | ✅ — line 1738 |
| 84 numbered TS + 5 smoke = 89 total | `grep -cE "TS-[0-9]"` | ✅ |
| Zero "to be drafted" stubs remaining | `grep -n "to be drafted"` | ✅ — empty (exit 1, no matches) |
| `Project_Backlog_v31.md` exists with prompt-body references | `grep -nE "prompt.body"` | ✅ — D-63 + D-64 rows + file-revision narrative all reference the 5 queued prompt-body sessions |
| CLAUDE.md "Next forward move" lists 7 candidates including prompt-body sessions | (from system context) | ✅ |
| Branch `claude/design-layer-implementation-9kdCe` cut clean from `main` at `f0f592b` (PR #58 merge) | `git log` + `git branch --show-current` | ✅ — 0 commits ahead of main pre-session |
| Working tree clean | `git status` | ✅ |

No drift. Predecessor's close-out pass + the spec-arc PR landed cleanly. Branch is the fresh task-assigned branch (`9kdCe` per the task description's "Develop on branch `claude/design-layer-implementation-9kdCe`").

---

## 2. Session narrative — seam-reviewer prompt body design

Chat opened with Andy linking the session-4 closing handoff URL and saying "Check it out and let's work". Per the first-session checklist + Rule #9, I reconciled handoff narrative against on-disk state (§1 above; clean), then summarized current state + the 7 next-move candidates from CLAUDE.md and asked Andy to pick.

Andy picked **prompt-body session** (CLAUDE.md candidate #2). I surfaced the 5 queued prompts with rough complexity ordering + my recommendation of seam-reviewer first (smallest scope, learning vehicle; matches the predecessor handoff §10.6 + CLAUDE.md framing). Andy picked **seam-reviewer**.

Per stop-and-ask trigger #2 ("Designing or significantly modifying an LLM prompt body"), I entered plan mode and surfaced 7 design decisions with options + tradeoffs + my recommendations + a gut check on the seam-reviewer choice:

| # | Decision | Options | My recommendation | Andy's pick |
|---|---|---|---|---|
| D1 | Output mechanism | A) tool-use, B) JSON-mode prompt | A (tool-use) — sets convention for the v2 LLM pipeline | **A** |
| D2 | Reasoning style | A) extended thinking ON ~2000 tokens, B) thinking OFF | A — judgment task; latency fits §11.1 budget | **A** |
| D3 | Input format | A) full PlanSession dump, B) weekly rollup only, C) hybrid (rollup + last-week-prior + first-week-next) | C — matches §11.2 ~6000 input estimate; preserves seam fidelity | **C** |
| D4 | Verdict calibration | A) thresholds, B) coaching judgment, B+A) judgment with anchors | B+A — judgment with concrete anchors avoids gaming and verdict drift | **B+A** |
| D5 | `seam_issues` style | A) constraint-level, B) solution-level | A — solution-level violates §6.2 authority bounds | **A** |
| D6 | Voice + length | (CLAUDE.md voice + tight rules) | one tight sentence ≤30 words; max 4 entries; no platitudes | **agree** |
| D7 | File location | A) `aidstation-sources/Layer4_SeamReviewer_Prompt_v1.md`, B) `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md`, C) append to `Layer4_Spec.md` | A (familiar naming) | **B** (new `prompts/` subdir for the 5-file prompt arc) |

Andy approved all 7 in a single message (none of the recommendations were overridden; D7 chose the cleaner subdir option that better fits the 5-prompt arc).

Drafting was mechanical against the design decisions + the locked spec contracts. No new Andy decisions surfaced during drafting.

Policy choices I made without explicit Andy confirmation during drafting (all in the spirit of the 7 design decisions; flagged in §6 below):

1. **`max_tokens` = 1500** (headroom over §11.2 ~800 output estimate to accommodate extended-thinking tokens + worst-case 4-entry `seam_issues`).
2. **`temperature` = 0.15** (per §5.2 step 4.1 "lower `temperature`" instruction; synthesizer default is 0.2).
3. **Tool name = `record_seam_review`** (matches §7.7 dataclass name in spirit; verb-form for the tool, noun-form for the schema).
4. **JSON-schema-style tool input schema in §4** with `additionalProperties: false` (strict schema; rejects free-form fields).
5. **Calibration anchors numerics** in §5/§9 (10%/8pp/25% week-over-week drift thresholds). Per D4 these are anchors not thresholds, but they need concrete numbers in the prompt for the model to ground its judgment.
6. **§5 system prompt** verbatim text — coaching voice + verdict descriptions + calibration anchors + writing rules + authority bounds + iteration-2 instructions. Long-ish but the prompt-design rationale is that a well-rehearsed system prompt + a thin user prompt is more reliable than the inverse for judgment tasks.
7. **§6 user prompt template** uses Mustache-style `{{var}}` and `{{#if}}` / `{{#each}}` blocks as pseudo-code for the orchestrator's template engine; the actual rendering language is an implementation detail (Python f-string + conditional concat is fine for v1).
8. **15-row v1 test scenario table (§12)** mapped to existing Layer4_Spec §13 TS-15..TS-21 (Pattern A seam paths) + 8 prompt-body-specific scenarios (SR-1..SR-15). These are LLM-output tests for the prompt itself; they slot under the existing TS rows in `Layer4_Spec.md` §13 if §13 ever expands per-prompt-body.

These are tuning parameters or prose-design choices; none are spec contracts. Adjustable without touching `Layer4_Spec.md`.

---

## 3. Files shipped this session

All on branch `claude/design-layer-implementation-9kdCe`. Both files commit + push at end of chat.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md` | New (436 lines, 14 H2 sections + 8 H3+ subsections) | Seam-reviewer prompt body. Full breakdown in §4 below. New `prompts/` subdirectory created per D7. |
| 2 | `aidstation-sources/handoffs/V5_Design_Layer4_Prompts_SeamReviewer_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Not touched this session** (deferred per the v1-commit-deferral rule carried forward from the spec arc; see §5):

- `CLAUDE.md` — Layer-pipeline-table + last-shipped-narrative + authoritative-current-files + Next-forward-move — held until end-of-prompt-body-arc (or until Andy picks per-prompt cadence).
- `Project_Backlog_v31.md` → `v32.md` — held until end-of-prompt-body-arc. v31 file-revision narrative already references the 5 queued prompt-body sessions in the file-revision header + D-63 / D-64 rows; no information drift yet.
- `Layer4_Spec.md` — untouched. The prompt body is a separate deliverable per D7; the spec stays at 14 sections / 1746 lines. (§12.2's "Prompt body design — deferred to dedicated sessions" forward-pointer remains accurate after this session; it lists 5 sessions queued, and 1 is now done — but the §12.2 text is still correct as a forward-pointer until all 5 land.)
- `PR_Verification_Status.md` — no PR shipped this session (PR creation deferred; see §5).
- `Control_Spec_v8.md` — unchanged; §9 doc-map stale-flag from PR16 still standing.

---

## 4. What the prompt body now commits to

### 4.1 Structure

14 sections (matching the layer-spec depth standard from CLAUDE.md, applied here at prompt-body scope):

| # | Section | Content |
|---|---|---|
| Header | Status + decisions block | 7 design decisions D1–D7 with rationale. |
| §1 | Purpose + scope | Failure modes the reviewer catches; β authority recap; out-of-scope items. |
| §2 | Pipeline placement | Per §5.2 step 4 of the spec; T3 cross-phase variant per §6.3; single-phase Pattern A skip per §6.5. |
| §3 | Inputs (template variables) | 18-row variable table + 5-row "intentionally NOT passed" exclusion list. Drives the §11.2 ~6000 input token budget realism. |
| §4 | Output schema + tool definition | `record_seam_review` JSON-schema tool definition + 6-row invalid-combination table. |
| §5 | System prompt (verbatim) | The actual prompt text. Verdicts + calibration anchors + patch directions + `seam_issues` writing rules + authority bounds + iteration-2 behavior + voice. |
| §6 | User prompt template (verbatim) | Mustache-style template with all `{{var}}` interpolation slots. |
| §7 | Model + sampling config | Sonnet 4.6, temperature 0.15, extended thinking 2000 budget tokens, tool_choice forced, max_tokens 1500. Token accounting: ~$0.06 per seam review at v1 pricing. |
| §8 | Authority bounds — explicit forbid list | 6-row recap of §6.2 bounds + how each is enforced (input filtering vs schema vs prompt rules). |
| §9 | Verdict calibration — coaching anchors | 7-row anchor table + tuning candidates. |
| §10 | `seam_issues` writing rules | 5-row rule table + 4 example entries + 3 counter-examples (what NOT to write). |
| §11 | Edge cases + invalid combinations | 8 edge cases including iteration-2 sub-paths + schedule-violation non-handling + active-injury inference + invalid-combo defense. |
| §12 | Test scenarios (v1) | 15-row table SR-1..SR-15 covering happy + flagging + iteration-2 + edge cases + invalid-output defense + open-ended + single-phase-skip + T3-cross-phase + 4-entry-cap. |
| §13 | Open items / tuning candidates | 7 v1-default tuning candidates (anchor numerics, Haiku downgrade, thinking budget, input format token tuning, iteration-2 bias, 4-entry cap, race-format-specific anchors). |
| §14 | Gut check — deferred to Layer 4 §14 retro | Folds into the spec's §14 retrospective per §12.6. 4 risks flagged for the retro: β authority enforcement, verdict drift, input-shape coupling to synthesizer, race-format diversity. |

### 4.2 Design decisions captured

All 7 design decisions (D1–D7) live in the file's header block as "Source decisions (this session, Andy 2026-05-16)" — analogous to Layer4_Spec.md's source-decisions block. These are prompt-design choices, NOT layer-spec source decisions; they don't propagate to `Layer4_Spec.md`'s header. A v2 of this prompt file would supersede these decisions by file replacement (Rule #12 numeric version suffix).

### 4.3 What landed (spec contract-relevant)

The prompt body is faithful to all locked spec contracts:

- `record_seam_review` tool schema mirrors §7.7 `SeamReview` (minus orchestrator-filled metadata).
- All 6 verdict×direction combinations from §6.2's verdict table are encoded.
- All 6 invalid combinations raise `Layer4OutputError('seam_reviewer_invalid_verdict_combination')` per §6.2.
- Per-seam iteration cap (2) and per-phase retry-budget interaction per §6.2 are honored (the prompt's iteration-2 instructions explicitly bias toward `accept_with_observation` when cap is reached).
- All 6 authority bounds from §6.2 are enforced (4 via input filtering / schema, 2 via prompt-rules + tool_choice forcing).
- Token + latency + cost estimates align with §11.1 + §11.2 + §11.3.
- Coaching voice per CLAUDE.md.

No spec contracts modified or contradicted. The prompt body is a downstream consumer of the spec.

---

## 5. Next session scope

### 5.1 Default: continue the prompt-body arc

4 prompt bodies queued, Andy's pick on order. Recommended ordering (subject to Andy's call):

1. **Single-session synthesizer (D-63)** — self-contained; Pattern B; unblocks D-63 implementation gate at the LLM-call layer. Smaller scope than per-phase synthesizer.
2. **Per-tier T1/T2 synthesizer (Pattern B refresh)** — D-64 implementation gate at LLM-call layer. May split into T1 + T2 across two sessions if scope is too big for one.
3. **Per-phase synthesizer (Pattern A)** — load-bearing for `plan_create`. Largest scope; seam-reviewer conventions established this session carry forward (tool-use + extended thinking + coaching voice + closed-set flag taxonomy enforcement).
4. **Race-week-brief** — most cross-cutting (Pattern B but with `RaceWeekBrief` + `RacePlan` output shapes); pre-race only.

Each is its own stop-and-ask trigger #2 session; each lands as one prompt file in `aidstation-sources/prompts/`.

Five total prompt files in this arc: `Layer4_SeamReviewer_v1.md` (done), `Layer4_SingleSession_v1.md`, `Layer4_PerTier_T1_v1.md`, `Layer4_PerTier_T2_v1.md` (or combined), `Layer4_PerPhase_v1.md`, `Layer4_RaceWeekBrief_v1.md`. End-of-arc bookkeeping (CLAUDE.md + backlog bump) lands once the last one ships.

### 5.2 Alternative: switch tracks

Per CLAUDE.md "Next forward move" candidates, Andy may want to switch:

- **Layer 4 §14 retrospective** — fresh-eyes pass over spec §§1–13. Still deferred per §12.6; doesn't block prompt-body work but should land before Layer 4 implementation.
- **Layer 4 implementation track** — D-63 + D-64 scaffolding (deterministic-validator harness, `ad_hoc_workout_suggestions` schema, `plan_versions` table, frequency-cap orchestrator, diff renderer) can land ahead of prompt bodies per CLAUDE.md "Next forward move" #3.
- **v5 onboarding implementation PR** — substantial code work; independent track.
- **D-50 wiring resumption** — COROS OAuth + webhook recording; independent track.
- **Layer 4.5 — Joint Session Coordinator** spec — separate file; team-features track.
- **Layer 5** spec — parallel supplemental outputs.

### 5.3 v1-commit deferral rule for this arc

Per the spec arc's v1-commit-deferral precedent: mid-stream work; no CLAUDE.md / backlog bump until end-of-arc. End-of-arc for the prompt-body arc = after all 5 prompt bodies land.

**Alternative (Andy's call):** per-prompt-body bump cadence. Trade-off: more CLAUDE.md churn (one bump per prompt-body session); benefit: CLAUDE.md tracks "how many of the 5 are done" in real time. v1 default is the deferred-bump-at-end-of-arc; Andy can switch by request.

### 5.4 PR cadence

Per the spec arc's cadence (PR at end-of-arc, not mid-stream): no PR this session. End-of-prompt-body-arc PR title candidate: "V5 Design — Layer 4 prompt bodies (5-prompt arc)" with body referencing each prompt's design-decisions block.

**Alternative (Andy's call):** per-prompt-body PR cadence. Trade-off: more PR overhead (5 small PRs vs 1 batch); benefit: each prompt body gets focused review independently. v1 default is end-of-arc batch; Andy can switch.

---

## 6. Open items / decisions pinned this session

### 6.1 v1-default prompt-design choices (flagged for Andy review)

Per §2 narrative — 8 prompt-design choices I made within the spirit of the approved D1–D7 design decisions:

1. **`max_tokens = 1500`** — extended-thinking + output headroom estimate. Tunable; measure actual response sizes post-launch.
2. **`temperature = 0.15`** — concrete choice for "lower than synthesizer" per §5.2. Tunable; measure verdict drift in production.
3. **Tool name `record_seam_review`** — naming convention for the 5-prompt arc. If the per-phase synthesizer uses a different tool-naming convention (e.g., `synthesize_phase` vs `emit_phase_sessions`), we should align here in a future revision.
4. **Strict JSON schema** with `additionalProperties: false` — defensive against the model emitting extra fields. May reject benign extras; if telemetry shows this firing on benign output, relax.
5. **Calibration-anchor numerics** (10%/8pp/25%) — evidence-grounded starting points per D4; tune from production verdict distribution.
6. **System prompt verbosity** — long-ish (~70 lines of prompt text). v1 trade-off: explicit rules > terse prompts for judgment tasks. Tune by ablation post-launch.
7. **User prompt template uses Mustache pseudo-code** — implementation engine is TBD; current spec is template-engine-agnostic.
8. **15 v1 test scenarios** — picked-coverage not Cartesian. Maps to existing TS-15..TS-21 + 8 new prompt-body-specific. Will need golden recordings once the orchestrator scaffolding lands.

None lock spec contracts. All are prompt-design tuning parameters Andy can adjust by editing the file (Rule #12 v2 supersedes by replacement).

### 6.2 Carry-forward to other prompt bodies in the arc

Conventions established this session that should propagate to the remaining 4 prompts (per-phase synthesizer, per-tier T1/T2, single-session, race-week-brief):

- **Tool-use output mechanism** — `record_*` tool naming; strict JSON schema; one tool call per invocation.
- **Extended thinking ON** — ~2000 token budget for judgment-heavy prompts; can scale down for purely-generative prompts if quality holds.
- **File location convention** — `aidstation-sources/prompts/Layer4_<PromptName>_v1.md` per Rule #12.
- **File structure** — 14 sections matching this file's outline (header decisions block + Purpose/Placement/Inputs/Output/SystemPrompt/UserPrompt/Config/Bounds/Calibration/WritingRules/EdgeCases/TestScenarios/OpenItems/GutCheck).
- **Source decisions block** — every prompt body lists its design decisions in the header, mirroring Layer4_Spec.md's source-decisions convention.
- **Coaching voice** — direct, evidence-grounded, no platitudes, no hype. Applies to all 5 prompts.
- **Closed-set coaching-flag taxonomy enforcement** (per §8 of the spec) — every prompt that emits coaching flags MUST enumerate the allowed flag names; unknown flags raise `unknown_coaching_flag_<name>` schema violation per §5.5.

Surface these in §1 of the next prompt-body file as "Conventions inherited from `Layer4_SeamReviewer_v1.md`" so future sessions don't re-derive them.

### 6.3 Tuning candidates for §12.4 fold-in

Per the spec's §12.4 "Tuning candidates — v1 defaults; measure post-launch" catch-all, the following prompt-body tuning candidates should fold in once the prompt-body arc closes (end-of-arc bookkeeping per §5.3):

- Calibration-anchor numerics (10%/8pp/25%).
- Haiku downgrade for seam reviewer.
- Extended-thinking budget per prompt.
- Hybrid input format token tuning.
- 4-entry `seam_issues` cap.
- Race-format-specific anchor sets.

These fold as additional bullets under §12.4's existing "tune post-launch" basket; no new §12 subsections.

### 6.4 Risks flagged for Layer 4 §14 retro

Per the prompt body's §14 (deferred), 4 risks fold into the spec's §14 retrospective when it lands:

1. β authority enforcement via prose-only rules.
2. Verdict drift across calls at temperature 0.15.
3. Input-shape coupling to the per-phase synthesizer's (un-designed) output.
4. Calibration anchors may not survive race-format diversity (especially expedition AR / swimrun / modern pentathlon).

The §14 retro is the right venue to evaluate whether the conventions established here hold up across all 5 prompts. Premature to retro a single prompt in isolation.

---

## 7. Session-end verification (Rule #10)

Final pass over the prompt body before composing this handoff:

| Check | Result |
|---|---|
| `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md` exists (436 lines, 14 H2 sections + 8 H3+ subsections = 22 total `##`-prefixed lines) | ✅ `wc -l` + `grep -cE "^## "` + `grep -cE "^### "` |
| Header block lists D1–D7 with each rationale | ✅ Read header |
| §4 tool definition matches §7.7 SeamReview minus orchestrator-filled metadata | ✅ Cross-checked against `Layer4_Spec.md:444-461` |
| §4 invalid combinations table covers all 6 cases from §6.2 | ✅ Cross-checked against `Layer4_Spec.md:884-916` |
| §5 system prompt is in a verbatim code block (not paraphrased) | ✅ Read §5 |
| §5 system prompt enforces all 6 §6.2 authority bounds | ✅ Read "AUTHORITY BOUNDS" subsection |
| §6 user prompt template uses `{{var}}` placeholders for all §3 input variables | ✅ Read §6 + diffed against §3 table |
| §7 sampling config matches §11.2 ~6000 input / ~800 output budget | ✅ Token accounting in §7 |
| §12 test scenarios cover TS-15..TS-21 Pattern A seam paths from `Layer4_Spec.md` §13 | ✅ Read §12 |
| §14 deferred to Layer 4 §14 retro per §12.6 | ✅ Read §14 |
| `Layer4_Spec.md` not touched this session | ✅ `git diff --stat` shows only the prompt + handoff files |
| Branch ahead of `main` by 0 commits pre-session | ✅ `git log main..HEAD` |
| Working tree clean before handoff write | ✅ `git status` |

---

## 8. Operating notes for next session

1. **First re-read** (per Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load.
2. **Second re-read**: this handoff in full.
3. **Third re-read**: `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md` in full — establishes conventions that propagate to the remaining 4 prompts.
4. **Fourth re-read** (selective): `Layer4_Spec.md` §6 (decomposition + seam semantics) + §7 (payload schema for the targeted prompt's output) + §8 (coaching flag rules — every synthesizer prompt enumerates the closed-set flag list) + §11.2 (token budget for the targeted prompt).
5. **No CLAUDE.md / backlog bump expected** unless Andy switches to per-prompt cadence per §5.3.
6. **Apply §6.2 conventions** to the next prompt body — see this handoff §6.2 for the carry-forward list.
7. **Stop-and-ask trigger #2 still applies** — each prompt body is its own design session; surface design decisions in chat before drafting.
8. **No new gating Andy decisions** queued for the next prompt body — the spec contracts (§§3 / 5 / 6 / 7 / 8 / 9 / 11) bound each prompt enough that a typical session will surface ~5–10 prompt-design choices analogous to D1–D7 here, all tuning-parameter-class, not contract-class.
9. **PR cadence** — defaults to end-of-arc batch PR (5 prompts in one PR) per §5.4; Andy can switch to per-prompt PRs.
10. **Convention drift watch** — if the per-phase synthesizer prompt or any other prompt diverges from a convention established here (tool naming, file structure, voice), surface the divergence in chat with rationale rather than silently breaking the convention.

---

## 9. Carry-forward from PR17 + Layer 4 spec arc (informational)

Same state as the spec-arc sessions:

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — Andy confirmed pass in session 1 chat; not actioned here.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate as of `f0f592b` (main): 43 done / 21 blocked / 23 owed / 4 N/A (per the spec-arc reading). No movement this session (no PR shipped; this is the design-track prompt-body arc).

---

**End of handoff.**
