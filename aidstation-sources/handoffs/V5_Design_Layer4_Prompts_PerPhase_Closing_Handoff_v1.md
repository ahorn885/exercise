# V5 Design — Layer 4 Prompt Bodies — Per-Phase Synthesizer Closing Handoff

**Session:** Second of 5 queued Layer 4 prompt-body design sessions per `Layer4_Spec.md` §12.2 + CLAUDE.md "Next forward move" (post Layer-4-spec-v1 close). Andy picked per-phase synthesizer second after seam-reviewer landed — the largest-scope and most load-bearing prompt of the arc (governs `plan_create` end-to-end). Conventions established in the seam-reviewer session propagate forward; this session refines them for the synthesizer scope.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Design_Layer4_Prompts_SeamReviewer_Closing_Handoff_v1.md` (seam-reviewer prompt body landed v1 + 7 design decisions D1–D7; CLAUDE.md/backlog bump was deferred per the v1-commit-deferral rule). Merged via PR #59 at `3e1351a`.
**Branch:** `claude/seamreviewer-closing-handoff-PyCaU` (task-assigned; cut from `main` at `3e1351a` — the merge commit for the seam-reviewer PR #59).
**Status:** 🟢 Per-phase synthesizer prompt body drafted at `aidstation-sources/prompts/Layer4_PerPhase_v1.md` (764 lines, 14 H2 sections + 23 H3+ subsections). Stop-and-ask trigger #2 invoked + Andy approved 10 design decisions (D1=tool-use; D2=extended-thinking-max-budget ~5000 — overrode my B-recommendation of ~3500 to defensive max; D3=hybrid-input; D4=hybrid-prior-phase-rendering; D5=schema-enum-closed-set; D6=judgment+anchor-deload-cadence; D7=judgment+anchor-Taper-length; D8=hybrid-RuleFailure-retry-context; D9=schema-enforced-length-caps; D10=`prompts/` subdir per carry-forward). 🟡 3 prompt bodies still queued (per-tier T1/T2, single-session D-63, race-week-brief). 🟢 CLAUDE.md + backlog bumped this session — cadence switched to per-prompt per Andy 2026-05-16 (was end-of-arc deferral under the seam-reviewer convention; explicitly retired). v32 backlog catches up the seam-reviewer landing retroactively (previously deferred under the spec-arc v1-commit-deferral rule).
**Time-on-task:** Single chat. 1 new file (per-phase prompt body) + 1 CLAUDE.md edit + 1 new backlog file (v32) + 1 new handoff (this) = 4 substantive files. Under the 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

Predecessor's §7 close-out claimed: `Layer4_SeamReviewer_v1.md` exists at 436 lines / 14 H2 + 8 H3+ subsections; `Project_Backlog_v31.md` is the highest backlog (no v32 — v1-commit-deferral); `Layer4_Spec.md` at 1746 lines untouched; seam-reviewer + handoff merged via PR #59 at `3e1351a`; CLAUDE.md still names "Layer 4 spec v1" as last-shipped (intentional per §5.3 v1-commit-deferral).

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `Layer4_SeamReviewer_v1.md` exists at 436 lines | `wc -l prompts/Layer4_SeamReviewer_v1.md` | ✅ — 436 lines |
| 14 H2 + 8 H3+ subsections | `grep -cE "^## "` + `grep -cE "^### "` | ✅ — 14 + 8 |
| `Project_Backlog_v31.md` highest backlog (no v32) | `ls Project_Backlog_v*.md` | ✅ — v31 is highest |
| `Layer4_Spec.md` 1746 lines (untouched) | `wc -l Layer4_Spec.md` | ✅ — 1746 |
| Seam-reviewer + handoff merged via PR #59 at `3e1351a` | `git log --oneline -10` | ✅ — `3e1351a Merge pull request #59 from ahorn885/claude/design-layer-implementation-9kdCe` |
| Working tree clean | `git status` | ✅ |
| Branch `claude/seamreviewer-closing-handoff-PyCaU` cut from main post-PR-59 | `git branch --show-current` + `git log main..HEAD` | ✅ — 0 commits ahead of main pre-session |
| CLAUDE.md "Layer 4 spec v1" as last-shipped (intentional per v1-commit-deferral) | system-reminder of CLAUDE.md content | ✅ — narrative still spec-arc-only; predecessor handoff §5.3 explicitly defers the bump |

No drift. Predecessor's session-end verification + the PR landed cleanly. Branch is the new task-assigned branch (`PyCaU` per the task description's "Develop on branch `claude/seamreviewer-closing-handoff-PyCaU`" — naming is sticky from the seam-reviewer handoff that triggered this session, not a content mismatch).

---

## 2. Session narrative — per-phase synthesizer prompt body design

Chat opened with Andy linking the seam-reviewer closing handoff URL and saying "Check it out and let's work." Per the first-session checklist + Rule #9, I reconciled handoff narrative against on-disk state (§1 above; clean), summarized current state + the prompt-body arc status (1/5 shipped; 4 queued), and surfaced two questions via `AskUserQuestion`:

1. **Which track next?** Single-session synth (D-63) / per-tier T1/T2 (D-64) / per-phase synth (Pattern A) / race-week-brief.
2. **Per-prompt or end-of-arc bookkeeping?** End-of-arc batch (predecessor default per §5.3) / per-prompt cadence.

Andy picked **per-phase synth (Pattern A)** + **per-prompt cadence**. Picking the largest-scope prompt second (rather than building up from smaller scopes) is deliberate: the per-phase synthesizer is load-bearing for `plan_create` and its conventions propagate to the remaining 3 (per-tier T1/T2, single-session, race-week-brief). Picking per-prompt cadence retires the seam-reviewer handoff §5.3 end-of-arc default — Andy's reasoning was that CLAUDE.md should track arc progress in real time.

Per stop-and-ask trigger #2 ("Designing or significantly modifying an LLM prompt body"), I entered plan mode and surfaced 10 design decisions with options + tradeoffs + my recommendations + a gut check on the per-phase-first sequencing:

| # | Decision | Options | My recommendation | Andy's pick |
|---|---|---|---|---|
| D1 | Output mechanism | A) tool-use `record_phase_sessions`, B) JSON-mode | A (tool-use) — inherits seam-reviewer convention | **A** |
| D2 | Extended thinking budget | A) ~2000 (seam-reviewer parity), B) ~3500 (heavier judgment), C) ~5000 (max-defensive) | B (~3500) | **C (~5000)** — overrode my B-recommendation; max-defensive |
| D3 | Input format for upstream payloads | A) full dumps, B) abstracted summaries, C) hybrid (small payloads full, large trimmed per slice) | C (hybrid) — matches §11.2 ~8000 input budget | **C** |
| D4 | Prior-phase output rendering | A) full PlanSession verbatim, B) weekly rollup only, C) hybrid (rollup + last week verbatim) | C (hybrid) — mirrors seam-reviewer D3 | **C** |
| D5 | Coaching-flag closed-set enforcement | A) JSON-schema enum union; prompt instructs phase-appropriate use, B) prompt-only guidance | A (schema enum) — closed-set per §8.8 is load-bearing | **A** |
| D6 | Deload-week handling | A) hardcoded cadence per mode, B) coaching judgment + anchor table, C) skip prompt guidance | B (judgment + anchor) — mirrors seam-reviewer D4 | **B** |
| D7 | Taper-length picking | A) verbatim heuristic, B) coaching judgment + anchor, C) v1 default per format + override | B (judgment + anchor) — consistent with D6 + seam D4 | **B** |
| D8 | RuleFailure retry context rendering | A) verbatim text, B) constraint statements re-framed, C) hybrid | C (hybrid) — matches seam-reviewer "Observed: X. Constraint: Y" | **C** |
| D9 | `session_notes` / `coaching_intent` length caps | A) schema `maxLength`, B) prompt-only | A (schema) — defense against output-token budget runaway | **A** |
| D10 | File location | `aidstation-sources/prompts/Layer4_PerPhase_v1.md` (carry-forward) | A | **agree** |

Andy approved 9 of 10 recommendations and overrode D2 to the max-defensive ~5000 extended thinking budget. The remaining 8 were "agree" via approval.

Drafting was mechanical against the design decisions + the locked spec contracts. No new Andy decisions surfaced during drafting.

Policy choices I made without explicit Andy confirmation during drafting (all in the spirit of the 10 design decisions; flagged in §6 below):

1. **`max_tokens` = 6000** (headroom over §11.2 ~3000 output estimate + extended-thinking-counted-as-output headroom for dense 4-week phases with 2-a-day sessions).
2. **`temperature` = 0.2** (synthesizer default per §3.1; NOT lowered like the reviewer per §5.2 step 4.1 instruction).
3. **Tool name = `record_phase_sessions`** (mirrors §7.2 `PlanSession` plural; verb-form for the tool, noun-form for the schema list).
4. **JSON-schema-style tool input schema in §4** with `additionalProperties: false` (strict schema; rejects free-form fields). Full inline schema for nested `cardio_blocks` / `strength_exercises` / `coaching_flags` enum — long but the prompt is the source of truth for what the LLM emits.
5. **`phase_synthesis_notes` field (≤600 chars)** as a per-call rationale text that lands in `plan_versions.notes` JSONB per §7.11 (not in `SynthesisMetadata` — that dataclass has no such field). Flagged as forward-pointer-compatible extension.
6. **`opportunities` field (max 3)** for the §8.7 LLM-emitted `category='opportunity'` exception. Each entry ≤240 chars with `evidence_basis` field-reference list.
7. **6-flag closed-set enum for `PlanSession.coaching_flags`:** `technique_emphasis`, `long_slow_distance`, `weak_link_targeted`, `overreach_test`, `discipline_specific_intensity`, `race_pace_specific`. Excludes `intensity_modulated` (D-63-only per §8.6). `StrengthExercise.coaching_flags` stays OPEN-SET per §7.4 examples (e.g., `eccentric_emphasis`, `unilateral_focus` — no enum).
8. **Schema length caps:** `session_notes` 600 chars / `coaching_intent` 240 / `phase_synthesis_notes` 600 / `opportunities[*].text` 240 / `cardio_blocks[*].instructions` 400 / `strength_exercises[*].instructions` 400 / `strength_exercises[*].load_prescription` 120.
9. **Calibration anchor tables (§9)** — deload cadence per mode + Taper length per race format + volume ramp per `data_density`. Per D6 + D7 these are anchors not thresholds, but they need concrete numbers in the prompt for the model to ground its judgment.
10. **15 v1 PPS-prefix test scenarios in §12** mapped to existing `Layer4_Spec.md` §13.2 plan_create scenarios + §13.6 coaching-flag emit scenarios. These are LLM-output tests for the prompt itself; they slot under §13.2/§13.6 if §13 ever expands per-prompt-body.
11. **§14 deferred to Layer 4 §14 retro** per §12.6, mirroring seam-reviewer §14 pattern. 6 risks flagged for the retro to fold in (see §6.4 below).
12. **System prompt verbatim text (§5)** is long-ish (~150 lines of prompt text). v1 trade-off: explicit rules > terse prompts for combinatorial judgment tasks. Tune by ablation post-launch.

These are tuning parameters or prose-design choices; none are spec contracts. Adjustable without touching `Layer4_Spec.md`.

---

## 3. Files shipped this session

All on branch `claude/seamreviewer-closing-handoff-PyCaU`. All files commit + push at end of chat.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/prompts/Layer4_PerPhase_v1.md` | New (764 lines, 14 H2 + 23 H3+ subsections) | Per-phase synthesizer prompt body. Full breakdown in §4 below. |
| 2 | `aidstation-sources/CLAUDE.md` | Edit | Layer-pipeline-table Layer 4 row updated → SPEC v1 DONE + PROMPT BODIES 2/5 (seam-reviewer + per-phase); last-shipped-narrative bumped from "Layer 4 spec v1" → this session's per-phase synth + retroactive seam-reviewer catchup; authoritative-current-files adds `prompts/Layer4_SeamReviewer_v1.md` + `prompts/Layer4_PerPhase_v1.md` entry; Project_Backlog reference v31 → v32; Next-forward-move rewritten with 3 remaining prompt bodies + per-prompt cadence note + inherited conventions list. |
| 3 | `aidstation-sources/Project_Backlog_v32.md` | New (file revision bump) | v32 header revision entry: per-phase synth + retroactive seam-reviewer catchup + cadence switch narrative. v31 moved to predecessor revisions list. Body (D-row table + categorization rules + status legend) byte-identical to v31 per Rule #12. |
| 4 | `aidstation-sources/handoffs/V5_Design_Layer4_Prompts_PerPhase_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Not touched this session** (intentional):

- `Layer4_Spec.md` — untouched. The prompt body is a downstream consumer of the spec contracts. §12.2's "Prompt body design — deferred to dedicated sessions" forward-pointer remains accurate (now 2 of 5 sessions done).
- `Layer4_SeamReviewer_v1.md` — untouched. Sibling prompt; no cross-prompt amendments needed.
- `PR_Verification_Status.md` — no PR shipped at file-write time; PR creation deferred to chat end.
- `Control_Spec_v8.md` — unchanged; §9 doc-map stale-flag from PR16 still standing.
- All other authoritative-current-files — unchanged.

---

## 4. What the prompt body now commits to

### 4.1 Structure

14 sections + 23 H3+ subsections (matches the layer-spec depth standard from CLAUDE.md, applied here at prompt-body scope — same outline as `Layer4_SeamReviewer_v1.md`):

| # | Section | Content |
|---|---|---|
| Header | Status + decisions block | 10 design decisions D1–D10 with rationale + 4 companion spec-section references. |
| §1 | Purpose + scope | What the synthesizer produces (sessions + notes + opportunities); failure modes the prompt + retry semantics catch; out-of-scope items. |
| §2 | Pipeline placement | Per §5.2 step 3; T3 cross-phase scope; `start_phase != 'Base'` first-phase handling per §6.5. |
| §3 | Inputs (template variables) | 5 subsections — phase + plan context (8 vars), prior-phase continuity (5 vars), athlete context (8 vars), race + locale + equipment (12 vars), retry context (5 vars), + intentionally-NOT-passed list. Drives the §11.2 ~8000 input token budget realism. |
| §4 | Output schema + tool definition | Full inline JSON-schema for `record_phase_sessions` with nested `PlanSession` discriminated union + `CardioBlock` + `StrengthExercise` + closed-set `coaching_flags` enum + `phase_synthesis_notes` + `opportunities` + 16-row cross-session schema rules table. |
| §5 | System prompt (verbatim) | The actual prompt text. Phase intent anchors (Base/Build/Peak/Taper); Taper-length + deload anchors; prior-phase continuity rules; schedule + locale + equipment + injury respect; closed-set flag emission rules; spec-auto-flag forbid list; opportunities format; retry-context handling; voice rules; authority bounds; iteration discipline. |
| §6 | User prompt template (verbatim) | Mustache-style template with all `{{var}}` interpolation slots covering §3 inputs. |
| §7 | Model + sampling config | Sonnet 4.6, temperature 0.2, extended thinking 5000 budget tokens, tool_choice forced, max_tokens 6000. Token accounting: ~$0.144 per phase at v1 pricing. |
| §8 | Authority bounds — explicit forbid list | 11-row recap of §5 in-band rules + enforcement mechanism per rule. |
| §9 | Verdict calibration — coaching anchors | 3 subsections: §9.1 deload cadence per mode (4 modes); §9.2 Taper length per race format (8 formats); §9.3 volume ramp per `data_density` (4 densities). |
| §10 | `coaching_flags` closed-set rules | 6-row table (1 row per flag) with phase / emit-on / frequency / conflicts columns + StrengthExercise.coaching_flags open-set note. |
| §11 | Edge cases + invalid combinations | 14 edge cases including first phase / `start_phase != 'Base'` / single-phase Pattern A / validator retry / seam retry / injury / sparse density / custom mode / open-ended / unknown flag / two-per-day / no tool call / overflow / out-of-range date. |
| §12 | Test scenarios (v1) | 15-row PPS-prefix scenario table covering clean phases + continuity + Taper picks + deload placement + injury + sparse density + custom mode + start_phase variations + validator retry + seam retry + unknown-flag defense + open-ended + two-per-day-rule defense. |
| §13 | Open items / tuning candidates | 12 v1-default tuning candidates (extended-thinking budget, max_tokens, closed-set flag enum, deload anchors, Taper anchors, ramp anchors, length caps, equipment trim heuristic, rollup shape, retry context, phase_date validator rule, daily-window-fit validator rule, observability orphan). |
| §14 | Gut check — deferred to Layer 4 §14 retro | Folds into the spec's §14 retrospective per §12.6. 6 risks flagged for the retro: token-budget margin for multi-discipline AR, extended-thinking over-budget, flag-phase-applicability prompt-only enforcement, continuity coupling to seam reviewer, deload custom-mode judgment, `phase_synthesis_notes` orphan risk. |

### 4.2 Design decisions captured

All 10 design decisions (D1–D10) live in the file's header block as "Source decisions (this session, Andy 2026-05-16)" — analogous to `Layer4_SeamReviewer_v1.md`'s D1–D7 + `Layer4_Spec.md`'s source-decisions block. These are prompt-design choices, NOT layer-spec source decisions; they don't propagate to `Layer4_Spec.md`'s header. A v2 of this prompt file would supersede these decisions by file replacement (Rule #12 numeric version suffix).

### 4.3 What landed (spec contract-relevant)

The prompt body is faithful to all locked spec contracts:

- `record_phase_sessions` tool schema mirrors §7.2 `PlanSession` (minus orchestrator-filled metadata — `session_id`, `plan_version_id`, `is_ad_hoc`, `ad_hoc_request_payload`, `phase_metadata`).
- All 6 `PlanSession` schema rules from §7.12 are encoded in §4 cross-session schema rules table + system prompt rules.
- `CardioBlock.block_kind == 'interval_set'` triple-non-null requirement + `block_kind ∈ {warmup, main_set, cooldown, transition}` triple-null requirement per §7.12.
- `StrengthExercise.resolution_tier` invariants per §7.12 (tier 1 = both null; tier 2 = substitute_text non-null; tier 3 = proxy_origin_id non-null).
- Two-per-day rules per §7.12: max 2 sessions; not both strength; not both hard; at least one cardio.
- §5.4 deterministic validator rule set is enforced upstream by prompt rules + downstream by validator (defense-in-depth).
- §5.5 capped retry semantics honored (counter passed in as `retries_used`; cap-aware iteration discipline).
- §6.2 seam re-prompt path honored (synthesizer consumes `seam_issues` + `seam_direction`).
- §6.5 `start_phase != 'Base'` handling encoded (§11.2 edge case + first-phase synthetic prior context).
- All 6 LLM-emitted coaching flags from §§8.2–8.6 closed-set enforced via schema enum.
- All spec-auto flags excluded from the enum (synthesizer cannot emit them).
- `Observation(category='opportunity')` LLM-emitted exception per §8.7 honored via optional `opportunities` field (max 3).
- Token + latency + cost estimates align with §11.1 + §11.2 + §11.3.
- Coaching voice per CLAUDE.md.

No spec contracts modified or contradicted. The prompt body is a downstream consumer of the spec.

### 4.4 Conventions inherited from `Layer4_SeamReviewer_v1.md` (per the v1 §6.2 carry-forward list)

All 7 conventions Andy approved for the seam-reviewer landed cleanly here:

- ✅ Tool-use output mechanism (`record_phase_sessions` naming; strict JSON schema with `additionalProperties: false`; one tool call per invocation).
- ✅ Extended thinking ON (~5000 tokens per D2 max-defensive; seam-reviewer was ~2000 per its D2).
- ✅ File location convention: `aidstation-sources/prompts/Layer4_<PromptName>_v1.md` per Rule #12.
- ✅ File structure: 14 sections matching the seam-reviewer outline.
- ✅ Source-decisions block in the header.
- ✅ Coaching voice (direct, evidence-grounded, no platitudes, no hype).
- ✅ Closed-set coaching-flag taxonomy enforcement via JSON-schema enum (the seam-reviewer didn't emit `coaching_flags` so it didn't need an enum; the per-phase synth is the first prompt actually emitting flags — enum union is the v1 default and propagates to the remaining 3).

---

## 5. Next session scope

### 5.1 Default: continue the prompt-body arc — 3 remaining

Recommended ordering (subject to Andy's call):

1. **Single-session synthesizer (D-63)** — smallest scope; self-contained Pattern B; unblocks D-63 implementation gate at the LLM-call layer. Per-phase conventions established here carry forward (tool-use + extended thinking + closed-set flag enum union + 14-section structure). Differs primarily in: no phase context; `is_ad_hoc=True` output; one-session list; `intensity_modulated` flag IS emittable (D-63-specific per §8.6); much smaller input/output budget.
2. **Per-tier T1/T2 synthesizer (D-64; Pattern B refresh)** — D-64 implementation gate at LLM-call layer. May split T1 + T2 across two sessions if scope is too big for one. T1: 3A + 2A/2D + 1 + prior_plan_session_window + parsed_intent → refreshed sessions. T2: above + 2B/2C/2E. Conventions inherited; output is `list[PlanSession]` (no phase decomposition).
3. **Race-week-brief** — most cross-cutting (Pattern B with `RaceWeekBrief` + `RacePlan` output shapes); pre-race only. Distinct from the synthesizer prompts in that it produces narrative + structured race-execution data, not training sessions. Largest output shape.

Each is its own stop-and-ask trigger #2 session; each lands as one prompt file in `aidstation-sources/prompts/` under the per-prompt cadence (CLAUDE.md + backlog bump + PR after each).

Five total prompt files in this arc: `Layer4_SeamReviewer_v1.md` (done), `Layer4_PerPhase_v1.md` (done this session), `Layer4_SingleSession_v1.md` (queued), `Layer4_PerTier_T1_v1.md` + `Layer4_PerTier_T2_v1.md` (or combined, queued), `Layer4_RaceWeekBrief_v1.md` (queued).

### 5.2 Alternative: switch tracks

Per CLAUDE.md "Next forward move" candidates, Andy may want to switch:

- **Layer 4 §14 retrospective** — fresh-eyes pass over spec §§1–13. Still deferred per §12.6; doesn't block prompt-body work but should land before Layer 4 implementation begins.
- **Layer 4 implementation track** — D-63 + D-64 scaffolding (deterministic-validator harness per §5.4, `plan_versions` table per §7.11, payload schema scaffolding, orchestrator skeleton, frequency-cap interaction stubs) can land ahead of the remaining prompt bodies per CLAUDE.md "Next forward move" — the per-phase synth prompt body is the LLM-call-layer for `plan_create` which is the highest-value implementation gate.
- **v5 onboarding implementation PR** — substantial code work; independent track.
- **D-50 wiring resumption** — COROS OAuth + webhook recording; independent track.
- **Layer 4.5 — Joint Session Coordinator spec** — separate file; team-features track.
- **Layer 5 spec** — parallel supplemental outputs.

### 5.3 Per-prompt cadence (now in effect)

Per Andy's session pick: each remaining prompt body session gets its own CLAUDE.md + backlog bump + PR. The seam-reviewer's end-of-arc-batch alternative (per `Layer4_SeamReviewer_v1.md` §5.3) is explicitly retired by this cadence switch. Mid-arc bookkeeping no longer accumulates.

This means: every prompt-body closing handoff from now through arc end should ship (a) a CLAUDE.md bump capturing the new file + revised next-forward-move; (b) a backlog file-revision bump (vN → vN+1) with file-revision header narrative; (c) a closing handoff; (d) a PR with all of the above. File count per prompt session typical: 4 (1 prompt body + 3 bookkeeping).

### 5.4 PR cadence

Per the per-prompt cadence switch: PR after each prompt body. End-of-arc batch PR is retired. This session's PR title candidate: "V5 Design — Layer 4 per-phase synthesizer prompt body (2 of 5 prompt-body arc) + retroactive seam-reviewer catchup."

---

## 6. Open items / decisions pinned this session

### 6.1 v1-default prompt-design choices (flagged for Andy review)

Per §2 narrative — 12 prompt-design choices I made within the spirit of the approved D1–D10 design decisions:

1. **`max_tokens = 6000`** — output-token + extended-thinking-counted-as-output headroom. Tunable; measure actual response sizes post-launch (esp. 4-week phases with 2-a-day sessions).
2. **`temperature = 0.2`** — synthesizer default per §3.1 (NOT lowered like the reviewer). Tunable; if creativity-vs-determinism balance drifts, adjust.
3. **Tool name `record_phase_sessions`** — naming continues the `record_*` convention from `record_seam_review`. If a future variant of per-phase synth (e.g., a v2 with structurally different output) needs a different tool name, adjust here.
4. **Strict JSON schema with `additionalProperties: false`** at every nesting level — defensive against the model emitting extra fields. May reject benign extras; if telemetry shows this firing on benign output, relax.
5. **`phase_synthesis_notes` field (≤600 chars)** — lands in `plan_versions.notes` JSONB per §7.11, not in `SynthesisMetadata` dataclass. Orchestrator-side JSONB key schema (e.g., `{"phase_synthesis_notes": {"Base": "...", "Build": "...", ...}}`) is not pinned here — orchestrator-implementation concern.
6. **`opportunities` field max 3** — schema cap matches seam-reviewer's 4-entry `seam_issues` cap framing. If 4+ opportunities surface, the synthesizer should prioritize the most distinctive 3 + summarize in `phase_synthesis_notes`.
7. **6-flag closed-set enum** for `PlanSession.coaching_flags` per §§8.2–8.6 LLM-emitted entries. Excludes `intensity_modulated` (D-63-only). If a future spec amendment adds an LLM-emitted flag for per-phase synth, schema enum + system prompt + §10 table all update; not a v2 of the prompt file (just a v1 maintenance edit).
8. **Schema length caps** (600/240/600/240/400/400/120) — defense against output-token budget runaway. Measure cap-hit rates post-launch.
9. **Calibration anchor tables (§9)** — deload cadence per mode, Taper length per race format, volume ramp per data_density. Evidence-grounded starting points; tune from production telemetry.
10. **15-row v1 PPS-prefix test scenario table (§12)** — mapped to existing `Layer4_Spec.md` §13.2 + §13.6. These are LLM-output tests for the prompt itself; they slot under §13.2/§13.6 if §13 ever expands per-prompt-body.
11. **§14 deferred to Layer 4 §14 retro** — fold-in pattern matches seam-reviewer §14.
12. **System prompt length** — ~150 lines of prompt text in §5. Trade-off: explicit rules > terse prompts for combinatorial judgment tasks. Tune by ablation post-launch.

None lock spec contracts. All are prompt-design tuning parameters Andy can adjust by editing the file (Rule #12 v2 supersedes by replacement).

### 6.2 Carry-forward to remaining prompt bodies in the arc

Conventions established this session that should propagate to the remaining 3 prompts (single-session, per-tier T1/T2, race-week-brief):

- **Schema-enforced closed-set coaching-flag enum.** Every prompt that emits coaching flags MUST enumerate the allowed flag names; unknown flags raise `unknown_coaching_flag_<name>` schema violation per §5.5. The closed set varies per entry point (single-session adds `intensity_modulated`; race-week-brief flags Taper sessions which are spec-auto anyway — race-week-brief LLM-emitted flag set likely empty).
- **Schema-enforced length caps** on athlete-facing text fields (`session_notes`, `coaching_intent`, `phase_synthesis_notes` analog, narrative fields).
- **Extended thinking budget set to entry-point complexity:** ~2000 for seam-reviewer (judgment only), ~5000 for per-phase synth (judgment + combinatorial), TBD per prompt for the remaining 3 (single-session likely ~2000; per-tier T1/T2 likely ~3000–4000; race-week-brief likely ~4000–5000 given narrative + structured-output combo).
- **Anchor-based judgment for prompt-internal heuristics** (D6, D7 pattern) — when the spec defers to "coaching judgment," provide concrete anchors in the prompt to ground the model. Override-with-rationale is the v1 default.
- **Retry context as constraint statements** (D8 hybrid pattern) — `rule_failures` + any prompt-specific retry context render as `rule_name + severity + detail + suggested_constraint` so the model has both the failure context and a constraint framing.
- **Phase / mode / start_phase as read-only inputs** (synthesizer cannot mutate periodization decisions; those are 3B + §6.1/§6.4 contracts).
- **Voice rules + authority bounds + iteration discipline** sections in every prompt body — direct coaching voice, explicit forbid list, retry-cap-aware behavior.

Surface these in §1 of the next prompt-body file as "Conventions inherited from `Layer4_SeamReviewer_v1.md` + `Layer4_PerPhase_v1.md`" so future sessions don't re-derive them.

### 6.3 Tuning candidates for §12.4 fold-in

Per the spec's §12.4 "Tuning candidates — v1 defaults; measure post-launch" catch-all, the following per-phase-synth-body tuning candidates should fold in once the prompt-body arc closes:

- Extended thinking budget (D2 ~5000) — drop to 3000–4000 if quality holds.
- `max_tokens` 6000 — raise for dense AR phases if cap-hit observed.
- Closed-set flag enum — add flags via spec amendment (stop-and-ask trigger #5) when production cases surface gaps.
- Deload cadence anchors per mode (§9.1).
- Taper-length anchors per race format (§9.2).
- Volume ramp anchors per data_density (§9.3).
- Length caps (D9 600/240/600/240).
- Hybrid input trim heuristic (D3) — sharpen per-locale per-format trimming.
- Hybrid prior-phase rendering (D4) — adjust rollup shape if continuity quality drifts.
- RuleFailure retry context rendering (D8) — `suggested_constraint` field relies on orchestrator generation.

These fold as additional bullets under §12.4's existing "tune post-launch" basket; no new §12 subsections needed yet.

### 6.4 Risks flagged for Layer 4 §14 retro

Per the prompt body's §14 (deferred), 6 risks fold into the spec's §14 retrospective when it lands:

1. Token-budget margin for multi-discipline AR athletes (5+ disciplines + 4+ locales may exceed §11.2 ~8000 input estimate).
2. Extended-thinking 5000-token budget may be over-budgeted for clean Base phases.
3. Closed-set flag enum is schema-enforced but phase-applicability is prompt-only — misuse (e.g., `race_pace_specific` in Base) won't be validator-caught.
4. Continuity coupling to seam-reviewer expectations — both prompts must honor each other's calibration framing; divergent tuning will flag more re-prompts than necessary.
5. Deload-week judgment under custom mode falls back to coaching judgment with no anchor; unmeasured quality.
6. `phase_synthesis_notes` lands in `plan_versions.notes` JSONB but has no downstream consumer yet — write-only field risk.

The §14 retro is the right venue to evaluate whether the conventions established here hold up across all 5 prompts. Premature to retro a single prompt in isolation.

### 6.5 Cadence-switch implications for the arc closeout

With per-prompt cadence now in effect, the original end-of-arc closeout (per `Layer4_SeamReviewer_v1.md` §5.3) becomes a no-op — by the time prompt 5 ships, CLAUDE.md + backlog will already be current. The end-of-arc handoff at that point becomes a slim "arc complete" capstone rather than a heavy bookkeeping pass. This is a net-positive for traceability (every session's prompt-body landing is now visible in the file-revision chain) at modest cost (one more CLAUDE.md + backlog bump per prompt-body session).

---

## 7. Session-end verification (Rule #10)

Final pass over the prompt body + bookkeeping before composing this handoff:

| Check | Result |
|---|---|
| `aidstation-sources/prompts/Layer4_PerPhase_v1.md` exists (764 lines, 14 H2 + 23 H3+ subsections = 37 total `##`-prefixed lines) | ✅ `wc -l` + `grep -cE "^## "` + `grep -cE "^### "` |
| Header block lists D1–D10 with each rationale | ✅ Read header |
| §4 tool definition matches §7.2 PlanSession (minus orchestrator-filled metadata) + §7.3 CardioBlock + §7.4 StrengthExercise | ✅ Cross-checked against `Layer4_Spec.md:323-401` |
| §4 cross-session schema rules table covers §7.12 invariants | ✅ Cross-checked against `Layer4_Spec.md:539-561` |
| §4 closed-set `coaching_flags` enum lists exactly the 6 LLM-emitted flags from §§8.2–8.6 | ✅ Read §4 + §10 |
| §5 system prompt is in a verbatim code block (not paraphrased) | ✅ Read §5 |
| §5 system prompt enforces all authority bounds + iteration discipline | ✅ Read "AUTHORITY BOUNDS" + "ITERATION DISCIPLINE" subsections |
| §6 user prompt template uses `{{var}}` placeholders for all §3 input variables | ✅ Read §6 + diffed against §3 tables |
| §7 sampling config matches §11.2 ~8000 input / ~3000 output budget | ✅ Token accounting in §7 |
| §9 deload/Taper/ramp anchors are concrete tables (not narrative) | ✅ Read §9 |
| §10 closed-set rules match §§8.2–8.6 LLM-emitted entries | ✅ Read §10 + diffed against `Layer4_Spec.md:997-1046` |
| §11 edge cases cover validator-retry + seam-retry + first-phase + start_phase-shift + open-ended | ✅ Read §11 |
| §12 test scenarios PPS-1..PPS-15 cover happy path + retry + edge + defense scenarios | ✅ Read §12 |
| §14 deferred to Layer 4 §14 retro per §12.6 | ✅ Read §14 |
| `Layer4_Spec.md` not touched this session | ✅ `git diff --stat` shows only the prompt + CLAUDE.md + backlog v32 + handoff |
| `Layer4_SeamReviewer_v1.md` not touched this session | ✅ Same |
| CLAUDE.md bumped: Layer 4 row + last-shipped + authoritative-current-files + backlog ref + next-forward-move | ✅ Diffed 5 edit locations |
| `Project_Backlog_v32.md` created with v32 header revision + v31 in predecessors | ✅ Read header lines 5–7 |
| Branch ahead of `main` by 0 commits pre-session | ✅ `git log main..HEAD` |
| Working tree clean before handoff write | ✅ `git status` (will verify after handoff write at commit time) |

---

## 8. Operating notes for next session

1. **First re-read** (per Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load. Last-shipped narrative + Layer-pipeline-table + authoritative-current-files now reflect 2/5 prompt-body arc state.
2. **Second re-read**: this handoff in full.
3. **Third re-read**: `aidstation-sources/prompts/Layer4_PerPhase_v1.md` in full — establishes (along with `Layer4_SeamReviewer_v1.md`) the conventions that propagate to the remaining 3 prompts.
4. **Fourth re-read**: `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md` — sibling prompt; shared convention anchor.
5. **Fifth re-read (selective)**: `Layer4_Spec.md` sections relevant to the next prompt body —
   - Single-session (D-63): §5.3 Pattern B, §4.4 single-session input validation, §7.1 + §7.2 payload schema (single-session subset), §10.4 single-session edge cases, §11.1/§11.2/§11.3 single-session budgets.
   - Per-tier T1/T2: §5.3 Pattern B, §4.3 plan_refresh validation, §6.3 single-phase T3 special case (boundary into Pattern A), §10.3 refresh edge cases, §11 T1/T2 budgets.
   - Race-week-brief: §3.4, §4.5, §5.3, §7.13 RaceWeekBrief, §7.14 RacePlan, §10.5 race-week-brief edge cases, §11 race-week-brief budgets.
6. **Per-prompt cadence in effect** — every prompt-body session ships CLAUDE.md + backlog + PR; no end-of-arc deferral.
7. **Apply §6.2 inherited conventions** to the next prompt body — schema-enum closed-set flags, schema-enforced length caps, anchor-based judgment, hybrid retry context, read-only periodization inputs, voice + authority + iteration sections.
8. **Stop-and-ask trigger #2 still applies** — each remaining prompt body is its own design session; surface design decisions in chat before drafting.
9. **No new gating Andy decisions** queued for the next prompt body — the spec contracts (§§3 / 5 / 7 / 8 / 11) bound each prompt enough that a typical session will surface 7–10 prompt-design choices analogous to D1–D10 here, all tuning-parameter-class, not contract-class.
10. **Convention drift watch** — if a remaining prompt diverges from a convention established here (tool naming, file structure, voice, schema-enum enforcement), surface the divergence in chat with rationale rather than silently breaking the convention.
11. **5-file ceiling status** — this session shipped 4 substantive files (1 prompt body + 1 CLAUDE.md edit + 1 backlog file + 1 handoff). Per-prompt cadence means future prompt sessions will also typically ship 4 files; under the 5-file ceiling.

---

## 9. Carry-forward from PR17 + Layer 4 spec arc + seam-reviewer session (informational)

Same state as the spec-arc + seam-reviewer sessions, with the seam-reviewer landing now CLAUDE.md/backlog-acknowledged:

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — Andy confirmed pass in session 1 chat; not actioned here.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate as of `3e1351a` (main): 43 done / 21 blocked / 23 owed / 4 N/A (per the spec-arc reading). No movement this session (this is the design-track per-phase synth session).
- Seam-reviewer prompt body (PR #59) — landed cleanly; this session's CLAUDE.md/backlog catchup is the formal acknowledgment.

---

**End of handoff.**
