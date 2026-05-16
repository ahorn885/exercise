# V5 Design — Layer 4 Prompt Bodies — Single-Session (D-63) Synthesizer Closing Handoff

**Session:** Third of 5 queued Layer 4 prompt-body design sessions per `Layer4_Spec.md` §12.2 + CLAUDE.md "Next forward move" (per-prompt cadence in effect post-seam-reviewer session). Andy picked single-session synth (D-63) third per the per-phase handoff §5.1 smallest-to-largest recommended ordering — the smallest-scope prompt of the remaining 3, useful for converging conventions before tackling per-tier T1/T2 and race-week-brief. **Coupled `Layer4_Spec.md` §10.4 amendment this session** retiring rest-shape repurposing for the sport-unavailable case — Andy's architectural call broke the "prompt-body sessions don't touch spec" convention from the per-phase session per his option-2 fold-in pick.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Design_Layer4_Prompts_PerPhase_Closing_Handoff_v1.md` (per-phase synth prompt body landed v1 + 10 design decisions D1–D10; CLAUDE.md/backlog/PR shipped per per-prompt cadence). Merged via PR #60 at `bbbb6fe`.
**Branch:** `claude/design-layer-prompts-A0IXT` (task-assigned; cut from `main` at `bbbb6fe` — the merge commit for the per-phase PR #60).
**Status:** 🟢 Single-session synthesizer prompt body drafted at `aidstation-sources/prompts/Layer4_SingleSession_v1.md` (589 lines, 14 H2 file-structure sections + 13 H3+ subsections). Stop-and-ask trigger #2 invoked + Andy approved 12 design decisions (D1=tool-use; D2=extended-thinking-~3500 — Andy overrode my B-recommendation of ~2000 to mid-defensive C; D3=full-payloads-verbatim; D4=hybrid-prior-session-window; D5=3-flag-D-63-only-enum; D6=judgment+anchor+must-explain; **D7=γ pre-LLM precondition path — sport-unavailable becomes a §4.4 input validation raise, NOT a rest-shape repurpose; rest-shape stays reserved for genuine coaching-chosen rest days**; D8=hybrid-RuleFailure-retry-context; D9=tight-schema-length-caps; **D10=verbatim-respect-unless-safety + overreach-warning + D6 three-tier interaction** — Andy overrode my A-recommendation; D11=unified-prompt-with-conditional-equipment-block; D12=`prompts/` subdir per carry-forward). 🟡 2 prompt bodies still queued (per-tier T1/T2 D-64, race-week-brief). 🟢 CLAUDE.md + backlog v33 + spec amendments shipped this session per per-prompt cadence + Andy's option-2 fold-in pick. **`Layer4_Spec.md` amended this session** (§3.5 + §4.4 + §10.4 + §13.4) — first time the spec has been touched in the prompt-body arc; convention breach intentional + scoped to one D-63-specific contract issue.
**Time-on-task:** Single chat. 1 new prompt body + 2 spec amendments (Layer 4 + D-63) + 1 CLAUDE.md edit + 1 new backlog file (v33) + 1 new handoff (this) = 6 substantive files. **5-file ceiling broken intentionally** (Andy pre-approved option-2 fold-in knowing file count would be ~6). Spec amendments are surgical — 4 edits in Layer4_Spec.md, 2 edits in D-63 design doc.

---

## 1. Session-start verification (Rule #9)

Predecessor's §7 close-out claimed: `Layer4_PerPhase_v1.md` exists at 764 lines / 14 H2 + 23 H3+ subsections; `Project_Backlog_v32.md` is the highest backlog; `Layer4_Spec.md` at 1746 lines untouched; per-phase + handoff merged via PR #60 at `bbbb6fe`; per-prompt cadence in effect; CLAUDE.md last-shipped narrative bumped to "Layer 4 prompt-body arc — 2 of 5 prompts shipped."

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `Layer4_PerPhase_v1.md` exists at 764 lines | `wc -l prompts/Layer4_PerPhase_v1.md` | ✅ — 764 lines |
| 14 H2 + 23 H3+ subsections | `grep -cE "^## "` + `grep -cE "^### "` | ✅ — 14 + 23 |
| `Project_Backlog_v32.md` highest | `ls Project_Backlog_v*.md` | ✅ — v32 is highest |
| `Layer4_Spec.md` 1746 lines (untouched) | `wc -l Layer4_Spec.md` | ✅ — 1746 |
| Per-phase + handoff merged via PR #60 at `bbbb6fe` | `git log --oneline -10` | ✅ — `bbbb6fe Merge pull request #60 from ahorn885/claude/seamreviewer-closing-handoff-PyCaU` |
| Working tree clean | `git status` | ✅ |
| Branch `claude/design-layer-prompts-A0IXT` cut from main post-PR-60 | `git branch --show-current` + `git log main..HEAD` | ✅ — 0 commits ahead of main pre-session |
| CLAUDE.md "Layer 4 prompt-body arc — 2 of 5 prompts shipped" | system-reminder of CLAUDE.md content | ✅ — matches |

No drift. Predecessor's session-end verification + the PR landed cleanly.

---

## 2. Session narrative — single-session (D-63) prompt body design + coupled §10.4 amendment

Chat opened with Andy linking the per-phase closing handoff URL and saying "check it out and let's work." Per the first-session checklist + Rule #9, I reconciled handoff narrative against on-disk state (§1 above; clean), summarized current state + the prompt-body arc status (2/5 shipped; 3 queued), and surfaced one question via `AskUserQuestion`: which of the 4 remaining-track candidates to work on (single-session synth, per-tier T1/T2, race-week-brief, §14 retro).

Andy picked **single-session synth (D-63)** — the smallest-scope prompt and per the per-phase handoff §5.1 recommended smallest-to-largest ordering.

Per stop-and-ask trigger #2, I entered plan mode and surfaced 12 design decisions with options + tradeoffs + my recommendations + D-63-specific deltas:

| # | Decision | Options | My recommendation | Andy's pick |
|---|---|---|---|---|
| D1 | Output mechanism | A) tool-use `record_single_session`, B) JSON-mode | A | **A** |
| D2 | Extended thinking budget | A) OFF, B) ~2000, C) ~3500 | B (~2000) | **C (~3500)** — Andy overrode my B to mid-defensive |
| D3 | Input format | A) full verbatim, B) hybrid trim, C) abstracted summaries | A (full) | **A** |
| D4 | Prior-session-window rendering | A) full verbatim, B) summary stats only, C) hybrid | C (hybrid) | **C** |
| D5 | Closed-set coaching-flag enum | A) D-63-only 3-flag, B) per-phase 6 + intensity_modulated (7), C) open-set | A (3-flag) | **A** |
| D6 | Intensity-modulation policy | A) hard guard, B) judgment + anchor + must-explain, C) prompt-only | B (judgment + anchor) | **B** |
| D7 | Sport-unavailable handling | α) rest-shape (current spec), β) distinct error shape in Layer4Payload, γ) pre-LLM precondition raise + D-63 caller-side handling | (initial rec α/C from earlier menu; pivoted to γ after Andy's pushback on rest-shape repurposing) | **γ — pre-LLM precondition path** |
| D8 | RuleFailure retry context | A) verbatim, B) constraint statements, C) hybrid | C (hybrid) | **C** |
| D9 | Schema length caps | A) tight 240/200/120/240, B) per-phase caps, C) prompt-only | A (tight) | **A** |
| D10 | `notes_for_synthesizer` handling | A) honor-as-soft-preference, B) verbatim-respect-unless-safety + overreach warning, C) prompt-only mention | A | **B + overreach warning + D6 three-tier interaction** — Andy overrode my A |
| D11 | Locale vs quick_equipment branching | A) unified prompt with conditional, B) two prompt files, C) one prompt + code-side switch | A (unified) | **A** |
| D12 | File location | `aidstation-sources/prompts/Layer4_SingleSession_v1.md` | A | **agree** |

Andy approved 10 of 12 recommendations + overrode D2 to ~3500 mid-defensive + overrode D10 to verbatim-respect-with-overreach-warning. D7 surfaced as a sub-decision when Andy pushed back on the rest-shape repurposing — see §2.1 below for the architecture decision narrative.

### 2.1 D7 — pivot from rest-shape repurpose to pre-LLM precondition raise

My initial D7 menu offered three options for representing the sport-unavailable case in the LLM tool schema:
- A) `oneOf` union in tool schema (two output shapes; LLM picks)
- B) two separate tools (`record_single_session` + `record_unavailable_session`)
- C) reuse `kind='rest'` + `rest_reason='athlete_unavailable'` per the existing `Layer4_Spec.md` §10.4 contract

I recommended C (matched the spec's current contract). Andy pushed back: "I think we need an error form. ... Your profile shows you don't have access to a MTB today" with options to ignore-and-override or describe-new-workout.

I clarified the choice as α/β/γ:
- α — keep §10.4 contract (rest-shape + `rest_reason` marker; UI affordances derive from rest_reason)
- β — amend Layer4Payload to add a distinct `unavailable_response` shape (LLM tool schema gains oneOf)
- γ — move sport-unavailable to a pre-LLM precondition; orchestrator/D-63 caller pre-checks; Layer 4 raises `Layer4InputError('request_sport_unavailable_at_locale')` if pre-check missed; the LLM is never invoked on impossible requests

Andy: rest-shape would cause confusion elsewhere — coaching artifacts (rest days affect training summaries, weekly load calcs, ACWR, calendar rendering) shouldn't carry system-error semantics. Andy picked γ.

The architectural reasoning: γ is the cleanest because (a) coaching = LLM, system errors = orchestrator/caller — separation of concerns; (b) saves an LLM call (~$0.02 + ~3s) on impossible requests; (c) no oneOf in the tool schema; (d) `Layer4Payload` contract stays "produce workouts" only; (e) the unavailable response shape (with frontend affordances) lives where it belongs — in D-63 §6.3 — not in Layer 4.

Andy also picked **option 2** for session-scoping: fold the coupled `Layer4_Spec.md` §10.4 amendment into this session rather than spin a separate spec-amendment session. This breaks the convention from the per-phase session ("prompt-body sessions don't touch spec") but Andy pre-approved knowing file count would be ~6 (over the 5-file ceiling). Decision rationale: spec amendment is surgical (4 small edits in Layer4_Spec.md + 2 in D-63 design doc), and shipping the prompt body without the amendment would leave the spec contradicting the prompt's authority-bounds rules.

Per stop-and-ask trigger #5 (schema change affecting inter-layer contract) — Andy's γ pick triggers a spec amendment that I executed this session.

### 2.2 D10 — three-tier intensity-modulation policy (Andy override on `notes_for_synthesizer`)

My initial D10 recommendation A was "honor as soft preference; coaching judgment trumps." Andy overrode to B (verbatim respect unless safety blocker) plus an explicit "warning if overreaching" addendum. This produces a three-tier policy when interacting with D6:

- **Tier 1 — Full honor:** Anchor signals neutral; honor the athlete's structural intent at the picked intensity; no flag emitted.
- **Tier 2 — Honor with warning:** Mild overreach risk; honor the athlete's intent; surface the overreach risk in `session_notes`; no `intensity_modulated` flag (intensity wasn't modulated).
- **Tier 3 — Modulate with explanation:** Clear-cut overreach; modulate one tier down (hard→moderate; moderate→easy); emit `intensity_modulated`; explain modulation in `session_notes` referencing the athlete's stated intent.

Concrete anchor thresholds (v1 defaults; tunable):
- Tier 1: ACWR ≤ 1.10, last-hard-session > 36h ago, neutral fatigue markers, 7d load within ±15% of 28d baseline
- Tier 2: ACWR 1.10–1.25, last-hard-session 24–48h ago, mild fatigue markers, 7d load up to +25%
- Tier 3: ACWR > 1.25, last-hard-session ≤ 24h ago (same-sport amplifies), strong fatigue markers, 7d load > +25%

Safety blockers (injury exclusion, validator hard-constraint failures) always override regardless of tier. The athlete's `notes_for_synthesizer` text never overrides safety, only intensity-tier judgments.

### 2.3 Drafting + policy choices made without explicit Andy confirmation (in the spirit of D1–D12)

1. **`max_tokens` = 1500** (per `Layer4_Spec.md` §3.3 default; not raised — tight cap discourages output bloat in a small-budget entry).
2. **`temperature` = 0.3** (per `Layer4_Spec.md` §3.3 default — higher than Pattern A's 0.2; athlete-facing [Regenerate] benefits from variation).
3. **Tool name = `record_single_session`** (mirrors `record_phase_sessions` and `record_seam_review`; `_session` singular reflects the `len(sessions)==1` invariant).
4. **JSON-schema-style tool input schema in §4** with `additionalProperties: false`. Full inline schema for `cardio_blocks` / `strength_exercises` / closed-set `coaching_flags` enum + optional `opportunities` field (max 2 entries).
5. **`opportunities` field (max 2)** for the §8.7 LLM-emitted `category='opportunity'` exception. Smaller cap than per-phase's 3 — single-session has narrower scope.
6. **3-flag closed-set enum** for `PlanSession.coaching_flags` per D5: `intensity_modulated` + `technique_emphasis` + `discipline_specific_intensity`. `StrengthExercise.coaching_flags` stays OPEN-SET per `Layer4_Spec.md` §7.4 examples.
7. **Schema length caps:** `session_notes` 240 / `coaching_intent` 200 / `load_prescription` 120 / `instructions` 240 / `opportunities[*].text` 200.
8. **Anchor tables (§9.1, §9.2, §9.3):** intensity-modulation tier signals per D6/D10; `notes_for_synthesizer` interaction with the three-tier policy per D10; Tier 1/2/3 substitution decision anchors for strength exercises.
9. **15 v1 PSS-prefix test scenarios in §12** mapped to existing `Layer4_Spec.md` §13.4 + §13.6 + §13.7. These are LLM-output tests for the prompt itself; they slot under §13.4/§13.6/§13.7 if §13 ever expands per-prompt-body.
10. **§14 deferred to Layer 4 §14 retro** per `Layer4_Spec.md` §12.6, mirroring seam-reviewer + per-phase §14 pattern. 6 risks flagged for the retro to fold in (see §6.4 below).
11. **System prompt verbatim text (§5)** is ~160 lines of prompt text — slightly longer than per-phase's because the three-tier intensity-modulation policy + injury-exclusion + equipment-respect + authority-bounds + iteration-discipline all need explicit instructions. v1 trade-off: explicit rules > terse prompts.
12. **`'race_pace'` intensity treatment:** Layer 4 §3.3 + D-63 §4.3 list `'race_pace'` as a possible intensity value. v1 prompt treats `'race_pace'` as `'hard'` + emits `discipline_specific_intensity` flag when the sport matches the athlete's primary discipline. A future spec amendment could add `race_pace` as a distinct intensity tier with its own prescription pattern.

These are tuning parameters or prose-design choices; none are spec contracts. Adjustable without touching `Layer4_Spec.md`.

---

## 3. Files shipped this session

All on branch `claude/design-layer-prompts-A0IXT`. All files commit + push at end of chat.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/prompts/Layer4_SingleSession_v1.md` | New (589 lines, 14 H2 file-structure + 13 H3+ subsections) | Single-session synthesizer prompt body. Full breakdown in §4 below. |
| 2 | `aidstation-sources/Layer4_Spec.md` | Edit (4 surgical amendments) | §3.5 (new error code), §4.4 (new precondition row), §10.4 (sport-unavailable row rewritten), §13.4 TS-33 (expected output updated). |
| 3 | `aidstation-sources/OnDemand_Workout_D63_Design_v1.md` | Edit (2 surgical amendments) | §6.3 (caller-side pre-check wording), §9 scenario 5 (matching update). |
| 4 | `aidstation-sources/CLAUDE.md` | Edit | Layer-pipeline-table Layer 4 row updated → PROMPT BODIES 3/5 + §3.5/§4.4/§10.4/§13.4 amendments noted; last-shipped-narrative bumped from "2 of 5 prompts shipped" → "3 of 5 prompts shipped + coupled §10.4 spec amendment"; authoritative-current-files adds `prompts/Layer4_SingleSession_v1.md`; Project_Backlog reference v32 → v33; Next-forward-move rewritten with 2 remaining prompt bodies + D-63 LLM-call-layer-can-now-land note. |
| 5 | `aidstation-sources/Project_Backlog_v33.md` | New (file revision bump) | v33 header revision entry: single-session synth + coupled §10.4 amendment narrative. v32 moved to predecessor revisions list. Body (D-row table + categorization rules + status legend + open items + going-forward rule) byte-identical to v32 per Rule #12. |
| 6 | `aidstation-sources/handoffs/V5_Design_Layer4_Prompts_SingleSession_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**5-file ceiling broken intentionally** — Andy pre-approved option-2 fold-in knowing file count would be ~6. The two spec amendments (files #2 and #3) are surgical (4 + 2 edits respectively); the prompt body (file #1) is the substantive deliverable.

**Not touched this session** (intentional):

- `Layer4_SeamReviewer_v1.md` — untouched. Sibling prompt; no cross-prompt amendments needed.
- `Layer4_PerPhase_v1.md` — untouched. Sibling prompt; the §10.4 amendment doesn't affect per-phase (per-phase doesn't emit `rest_reason='athlete_unavailable'`).
- `PR_Verification_Status.md` — no PR shipped at file-write time; PR creation deferred to chat end.
- `Control_Spec_v8.md` — unchanged; §9 doc-map stale-flag from PR16 still standing.
- All other authoritative-current-files — unchanged.

---

## 4. What the prompt body now commits to

### 4.1 Structure

14 file-structure sections + 13 H3+ subsections. (Note: a raw `grep -cE "^## "` returns 20 because the user-prompt template inside §6 contains content-level `## Curated equipment view` / `## Athlete-supplied equipment` / `## Summary statistics` / `## Last 7 days verbatim` subheadings inside the Mustache template code block — those are part of the prompt template content, not file structure.)

| # | Section | Content |
|---|---|---|
| Header | Status + decisions block | 12 design decisions D1–D12 with rationale + 4 companion spec-section references. |
| §1 | Purpose + scope | What the synthesizer produces (one PlanSession); what it does NOT produce; failure modes the prompt + retry semantics catch. |
| §2 | Pipeline placement | Per `Layer4_Spec.md` §5.3 Pattern B; out-of-pipeline cases (cache hit, sport-unavailable pre-check, §4.4 input validation failure). |
| §3 | Inputs (template variables) | 5 subsections — request payload (6 vars), athlete + locale context (7 vars), recent training context (7 vars), retry context (2 vars), intentionally-NOT-passed list (5 items). |
| §4 | Output schema + tool definition | Full inline JSON-schema for `record_single_session` with strict `additionalProperties: false` at every nesting level + `PlanSession`-shape + nested `CardioBlock` + `StrengthExercise` + closed-set `coaching_flags` enum + optional `opportunities` field (max 2) + 12-row cross-session schema rules table. |
| §5 | System prompt (verbatim) | The actual prompt text. ~160 lines. Coaching voice rules; three-tier intensity-modulation policy with concrete phrasing; injury exclusions; equipment respect (locale + quick_equipment paths); discipline-specific intensity flag rule; technique emphasis flag rule; 8-item authority-bounds forbid list; iteration discipline on retry; output discipline. |
| §6 | User prompt template (verbatim) | Mustache-style template with all `{{var}}` interpolation slots + the §3 inputs + Mustache `{{#request.locale_slug}}…{{/}}` conditional branch at the equipment-injection slot per D11. |
| §7 | Model + sampling config | Sonnet 4.6, temperature 0.3, extended thinking 3500 budget tokens, tool_choice forced, max_tokens 1500. Token accounting: ~$0.075/invocation worst-case. |
| §8 | Authority bounds — explicit forbid list | 11-row recap of §5 in-band rules + enforcement mechanism per rule. |
| §9 | Verdict calibration — coaching anchors | 3 subsections: §9.1 intensity-modulation anchor signals (3-tier table); §9.2 `notes_for_synthesizer` interaction with the three-tier policy; §9.3 substitution decision anchors (Tier 1/2/3 strength substitution). |
| §10 | `coaching_flags` closed-set rules | 3-row table (1 row per flag) with phase tie / emit-on / frequency / conflicts columns + StrengthExercise.coaching_flags open-set note + excluded phase-tied flags rationale. |
| §11 | Edge cases + invalid combinations | 14 edge cases including injury-conflicts-intensity, somewhere-else-insufficient-equipment, Tier 3 modulation, Tier 2 honor-with-warning, race_pace intensity, validator retries (equipment + duration), retry cap exhaust, cache hit, recent-discipline-mismatch, mid-Peak-week easy session, out-of-scope notes, sparse Layer 3A, schema malformed first pass. |
| §12 | Test scenarios (v1) | 15-row PSS-prefix scenario table covering happy paths (locale + quick_equipment) + Tier 1/2/3 modulation + notes_for_synthesizer technique + discipline_specific + injury substitution + injury-retry-exhaust + equipment-fallback + retry-on-duration + race_pace + brand-new athlete + Tier 3 modulation with note pushing back + opportunities emit + cache-hit verification. |
| §13 | Open items / tuning candidates | 12 v1-default tuning candidates (extended-thinking budget, max_tokens, closed-set flag enum, anchor thresholds, schema length caps, overreach-warning phrasing, Tier 2 calibration, same-sport vs cross-sport weighting, race_pace handling, cache-key composition, off-plan-day awareness, equipment-resolution telemetry). |
| §14 | Gut check — deferred to Layer 4 §14 retro | Folds into spec's §14 retrospective per `Layer4_Spec.md` §12.6. 6 risks flagged for the retro: three-tier policy generalizes? + anchor thresholds calibration + race_pace simplification + notes-vs-modulation policy intricacy + cache hit rate realism + LSD-look-alike flag-loss. |

### 4.2 Design decisions captured

All 12 design decisions (D1–D12) live in the file's header block as "Source decisions (this session, Andy 2026-05-16)" — analogous to `Layer4_SeamReviewer_v1.md`'s D1–D7 + `Layer4_PerPhase_v1.md`'s D1–D10. These are prompt-design choices, NOT layer-spec source decisions; they don't propagate to `Layer4_Spec.md`'s header. A v2 of this prompt file would supersede these decisions by file replacement (Rule #12 numeric version suffix).

### 4.3 What landed (spec contract-relevant)

The prompt body is faithful to all locked spec contracts (including the amended ones this session):

- `record_single_session` tool schema mirrors `Layer4_Spec.md` §7.2 `PlanSession` (minus orchestrator-filled metadata — `session_id`, `plan_version_id`, `is_ad_hoc`, `ad_hoc_request_payload`, `phase_metadata`).
- All applicable `PlanSession` schema rules from §7.12 are encoded in §4 cross-session schema rules table + system prompt rules.
- `CardioBlock.block_kind == 'interval_set'` triple-non-null requirement + `block_kind ∈ {warmup, main_set, cooldown, transition}` triple-null requirement per §7.12.
- `StrengthExercise.resolution_tier` invariants per §7.12 (tier 1 = both null; tier 2 = substitute_text non-null; tier 3 = proxy_origin_id non-null).
- §5.3 Pattern B algorithm honored (single LLM call + deterministic validator + capped retry).
- §5.4 minimal validator scope for single-session: duration, intensity, locale equipment availability, injury exclusions; no weekly-volume / ACWR / phase-shape checks.
- §5.5 capped retry semantics honored (counter passed in as `retries_used`; cap-aware iteration discipline).
- §3.3 + §3.5 contracts: `len(sessions)==1`, `is_ad_hoc=True`, `suggestion_id` populated; `Layer4InputError` raised on precondition failures.
- **§4.4 + §10.4 (this-session amendments):** sport-availability precondition raises `request_sport_unavailable_at_locale`; rest-shape repurposing retired.
- §8.6 D-63-only `intensity_modulated` flag honored; phase-tied flags excluded.
- §8.7 `opportunity` LLM-emitted exception via optional `opportunities` field (max 2).
- §11.1 / §11.2 / §11.3 budget targets aligned (~3s latency, ~3500 input + ~800 output, ~$0.02–0.075/invocation).
- Coaching voice per CLAUDE.md.

No spec contracts violated. Two spec sections amended this session per D7 architectural decision.

### 4.4 Conventions inherited from `Layer4_SeamReviewer_v1.md` + `Layer4_PerPhase_v1.md`

All conventions Andy approved for the prior two prompts landed here:

- ✅ Tool-use output mechanism (`record_single_session` naming; strict JSON schema with `additionalProperties: false`; one tool call per invocation).
- ✅ Extended thinking ON (~3500 tokens per D2 mid-defensive; sits between seam-reviewer's ~2000 and per-phase's ~5000).
- ✅ File location convention: `aidstation-sources/prompts/Layer4_<PromptName>_v1.md` per Rule #12.
- ✅ File structure: 14 sections matching the seam-reviewer + per-phase outline.
- ✅ Source-decisions block in the header.
- ✅ Coaching voice (direct, evidence-grounded, no platitudes, no hype).
- ✅ Closed-set coaching-flag taxonomy enforcement via JSON-schema enum (3-flag D-63-only set per D5).
- ✅ Schema-enforced length caps on athlete-facing text fields (D9; tighter than per-phase's caps due to smaller `max_tokens` budget).
- ✅ Anchor-based judgment for prompt-internal heuristics (D6 + D10) — when the spec defers to "coaching judgment," provide concrete anchors in the prompt to ground the model.
- ✅ Hybrid `RuleFailure` retry context (D8) — `rule_name + severity + detail + affected_session_id + suggested_constraint`.
- ✅ Voice rules + authority bounds + iteration discipline sections in every prompt body.

---

## 5. Next session scope

### 5.1 Default: continue the prompt-body arc — 2 remaining

Recommended ordering (subject to Andy's call):

1. **Per-tier T1/T2 synthesizer (D-64; Pattern B refresh)** — D-64 implementation gate at LLM-call layer. May split T1 + T2 across two sessions if scope is too big for one. T1: 3A + 2A/2D + 1 + `prior_plan_session_window` + `parsed_intent` → refreshed sessions. T2: above + 2B/2C/2E. Conventions inherited (tool-use + closed-set flag enum + 14-section structure + schema length caps); output is `list[PlanSession]` covering the refresh scope window.
2. **Race-week-brief** — most cross-cutting (Pattern B with `RaceWeekBrief` + `RacePlan` output shapes); pre-race only. Distinct from synthesizer prompts in that it produces narrative + structured race-execution data, not training sessions. Largest output shape.

Each is its own stop-and-ask trigger #2 session; each lands as one prompt file in `aidstation-sources/prompts/` under the per-prompt cadence (CLAUDE.md + backlog bump + PR after each).

Five total prompt files in this arc: `Layer4_SeamReviewer_v1.md` (done), `Layer4_PerPhase_v1.md` (done), `Layer4_SingleSession_v1.md` (done this session), `Layer4_PerTier_T1_v1.md` + `Layer4_PerTier_T2_v1.md` (or combined, queued), `Layer4_RaceWeekBrief_v1.md` (queued).

### 5.2 Alternative: switch tracks

Per CLAUDE.md "Next forward move" candidates, Andy may want to switch:

- **Layer 4 §14 retrospective** — fresh-eyes pass over spec §§1–13 (including the §3.5/§4.4/§10.4/§13.4 amendments from this session). Still deferred per §12.6; doesn't block prompt-body work but should land before Layer 4 implementation begins.
- **Layer 4 implementation track** — D-63 LLM-call layer can now land against `Layer4_SingleSession_v1.md`. D-64 prompt body (per-tier T1/T2) still queued; deterministic-validator harness + payload schema scaffolding + D-63 orchestrator + sport-availability pre-check (per the new §4.4 precondition + D-63 §6.3 amendment) can start independently of the remaining prompt bodies.
- **v5 onboarding implementation PR** — substantial code work; independent track.
- **D-50 wiring resumption** — COROS OAuth + webhook recording; independent track.
- **Layer 4.5 — Joint Session Coordinator spec** — separate file; team-features track.
- **Layer 5 spec** — parallel supplemental outputs.

### 5.3 Per-prompt cadence (still in effect)

Per Andy's session-2 pick: each remaining prompt body session gets its own CLAUDE.md + backlog bump + PR. This session ships under that cadence as the third prompt body landing. The cadence + per-prompt PR pattern is now well-established (3 of 5 PRs shipped).

### 5.4 PR cadence

Per the per-prompt cadence: PR after each prompt body. This session's PR title candidate: "V5 Design — Layer 4 single-session synthesizer prompt body (3 of 5 prompt-body arc) + coupled §10.4 sport-unavailable amendment."

---

## 6. Open items / decisions pinned this session

### 6.1 v1-default prompt-design choices (flagged for Andy review)

Per §2.3 narrative — 12 prompt-design choices I made within the spirit of the approved D1–D12 design decisions:

1. **`max_tokens = 1500`** — per `Layer4_Spec.md` §3.3 default; tight cap. Tunable; measure cap-hit rates post-launch, esp. on multi-block cardio sessions (5+ blocks) or detailed strength prescriptions (8+ exercises).
2. **`temperature = 0.3`** — per `Layer4_Spec.md` §3.3 default. Tunable.
3. **Tool name `record_single_session`** — continues the `record_*` convention. If a future variant needs a different tool name, adjust here.
4. **Strict JSON schema with `additionalProperties: false`** at every nesting level. Defensive against extra fields.
5. **`opportunities` field max 2** — smaller cap than per-phase's 3; narrower scope of single-session.
6. **3-flag closed-set enum** for `PlanSession.coaching_flags`. Phase-tied flags excluded; D-63-only set per §8.6.
7. **Schema length caps** (240/200/120/240) — tight against the 1500 `max_tokens` budget. Measure cap-hit rates post-launch.
8. **Anchor tables (§9.1, §9.2, §9.3)** — intensity-modulation tier signals, notes interaction with three-tier policy, substitution decision anchors. Evidence-grounded starting points; tune from production telemetry.
9. **15-row v1 PSS-prefix test scenario table (§12)** — mapped to existing `Layer4_Spec.md` §13.4 + §13.6 + §13.7.
10. **§14 deferred to Layer 4 §14 retro** — fold-in pattern matches seam-reviewer + per-phase §14.
11. **System prompt length** — ~160 lines of prompt text in §5. Trade-off: explicit rules > terse prompts for combinatorial judgment tasks. Tune by ablation post-launch.
12. **`'race_pace'` intensity treatment** — v1 collapses to `'hard'` + `discipline_specific_intensity` flag when sport matches discipline. A future spec amendment could add as a distinct tier.

None lock spec contracts. All are prompt-design tuning parameters Andy can adjust by editing the file.

### 6.2 Carry-forward to remaining prompt bodies in the arc

Conventions established + reinforced this session that should propagate to the remaining 2 prompts (per-tier T1/T2, race-week-brief):

- **Schema-enforced closed-set coaching-flag enum.** Every prompt that emits coaching flags MUST enumerate the allowed flag names. Per-tier T1/T2 likely uses a similar set to per-phase (6 LLM-emitted flags); race-week-brief likely empty (Taper-session flag emission is spec-auto via `race_day`).
- **Schema-enforced length caps on athlete-facing text fields.** Per-tier T1/T2 likely caps similar to per-phase (600/240/...); race-week-brief likely larger caps given the narrative shape of `RaceWeekBrief`.
- **Extended thinking budget set to entry-point complexity:** seam-reviewer ~2000, per-phase ~5000, single-session ~3500. Per-tier T1/T2 likely ~3000–4000; race-week-brief likely ~4000–5000 given narrative + structured-output combo.
- **Anchor-based judgment for prompt-internal heuristics** (D6 + D10 pattern) — provide concrete anchors when the spec defers to coaching judgment.
- **Retry context as constraint statements** (D8 hybrid pattern).
- **Read-only periodization inputs** (synthesizer cannot mutate periodization decisions).
- **Voice rules + authority bounds + iteration discipline** sections in every prompt body.
- **Three-tier policy framing** — if the next prompt has an intensity-modulation analog, consider whether the same three-tier framing applies; per the §14 retro flag #1, generalize back to per-phase only if cross-prompt utility surfaces.

Surface these in §1 of the next prompt-body file as "Conventions inherited from `Layer4_SeamReviewer_v1.md` + `Layer4_PerPhase_v1.md` + `Layer4_SingleSession_v1.md`" so future sessions don't re-derive them.

### 6.3 Tuning candidates for `Layer4_Spec.md` §12.4 fold-in

Per the spec's §12.4 "Tuning candidates — v1 defaults; measure post-launch" catch-all, the following single-session-body tuning candidates should fold in once the prompt-body arc closes:

- Extended thinking budget (D2 ~3500) — drop to ~2000 if quality holds; bump to ~5000 if Tier-3 calls rushed.
- `max_tokens` 1500 — bump to 2000 if cap-hits observed.
- Closed-set flag enum (D5 3-flag) — re-evaluate at 3-month telemetry checkpoint.
- Intensity-modulation anchor thresholds (§9.1) — ACWR cut-offs, lookback windows, load deltas.
- Schema length caps (D9 240/200/120/240).
- Overreach-warning phrasing (Tier 2 + Tier 3).
- Tier 2 honor-with-warning calibration (1.10–1.25 ACWR band).
- Same-sport vs cross-sport hard-session weighting (§9.1).
- `'race_pace'` intensity handling (§11 row 5).
- Cache-key composition for D-63 (per `Layer4_Spec.md` §9.1).
- Off-plan-day awareness (D-63 §6.4 orchestrator-side vs LLM-side framing).
- Equipment-resolution telemetry (Tier 1 / Tier 2 / Tier 3 distribution).

These fold as additional bullets under §12.4's existing "tune post-launch" basket.

### 6.4 Risks flagged for Layer 4 §14 retro

Per the prompt body's §14 (deferred), 6 risks fold into the spec's §14 retrospective when it lands:

1. Three-tier intensity-modulation policy (D10 + §9.1) is a new pattern in the prompt-body arc. Seam-reviewer + per-phase don't have a "honor + warn" middle ground (modulation is binary). Worth checking whether the three-tier policy generalizes back to per-phase intensity decisions or stays D-63-only.
2. Intensity-modulation anchor thresholds (ACWR 1.10/1.25, lookback windows, load deltas) are v1 defaults with no production calibration. Per-session anchors will likely need tuning sooner than per-phase deload/Taper anchors (more granular, more athletes fire D-63 than `plan_create`).
3. `'race_pace'` intensity collapses to `'hard'` + flag is a v1 simplification; athletes wanting race-pace work outside Peak/Taper may friction. v2 could split.
4. `notes_for_synthesizer` honor-vs-modulate policy is intricate (§9.2 + D10 three-tier). Risk that athletes feel the synthesizer is ignoring their note when modulation fires. Consider frontend-side affordance ("the system softened your request because of recent load — override?").
5. Cache-key composition includes 3A snapshot which changes daily. Effective cache hit rate for D-63 will be low (most fires unique). Confirm in production that the orchestrator-side cache lookup overhead doesn't dominate the LLM-call cost.
6. D-63 fires that look like phase-tied work (e.g., a 4hr easy run that's effectively LSD) silently lose the flag since phase-tied flags are excluded. Some downstream consumers may benefit from a "looks like LSD" inference outside phase context — push to per-phase synth domain instead of widening D-63's flag set.

The §14 retro is the right venue to evaluate whether the conventions established here hold up across all 5 prompts.

### 6.5 §10.4 spec amendment fallout

The §10.4 amendment retires the rest-shape repurposing for sport-unavailable. Knock-on effects to track:

- **D-63 implementation** — when the D-63 caller code lands, it MUST pre-check sport availability before invoking Layer 4. The new §4.4 precondition is the defensive backstop; the caller-side pre-check is the primary path. D-63 needs an `UnavailableResponse` shape (not yet defined in the D-63 design doc beyond the §6.3 frontend-affordance description). Decide whether `UnavailableResponse` is a D-63-internal type or lifts to a shared cross-spec type when D-63 implementation lands.
- **`Observation(category='sport_unavailable_at_locale', ...)`** — per `Layer4_Spec.md` §8.7, this observation category is still listed. Under the amended §10.4, it's no longer emitted (Layer 4 doesn't run on the unavailable case). The §8.7 row could be removed in a follow-up amendment, OR it stays as a "for forward-compat / parallel use" listing. Andy can decide on §14 retro pass.
- **`PR_Verification_Status.md`** — no changes; the §10.4 amendment doesn't affect PR §5.0 step state.

---

## 7. Session-end verification (Rule #10)

Final pass over the prompt body + spec amendments + bookkeeping before composing this handoff:

| Check | Result |
|---|---|
| `aidstation-sources/prompts/Layer4_SingleSession_v1.md` exists (589 lines, 14 H2 file-structure + 13 H3+ subsections) | ✅ `wc -l` + `grep -cE "^## "` (raw count 20 includes prompt-template subheadings; file structure is 14) |
| Header block lists D1–D12 with each rationale | ✅ Read header |
| §4 tool definition matches `Layer4_Spec.md` §7.2 PlanSession (minus orchestrator-filled metadata) | ✅ Cross-checked |
| §4 closed-set `coaching_flags` enum lists exactly the 3 D-63-only flags | ✅ Read §4 + §10 |
| §5 system prompt is in a verbatim code block (not paraphrased) | ✅ Read §5 |
| §5 system prompt enforces three-tier intensity-modulation policy per D10 | ✅ Read intensity-modulation section |
| §6 user prompt template uses `{{var}}` placeholders + Mustache conditional for locale-vs-quick_equipment per D11 | ✅ Read §6 |
| §7 sampling config matches `Layer4_Spec.md` §11.2 ~3500 input / ~800 output budget | ✅ Token accounting in §7 |
| §9 anchor signal tables are concrete (not narrative) | ✅ Read §9.1 |
| §10 closed-set rules match D5 + §8.6 D-63-only set | ✅ Read §10 |
| §11 edge cases cover injury-retry-exhaust + somewhere-else-fallback + Tier 3 mod + race_pace + cache hit | ✅ Read §11 |
| §12 test scenarios PSS-1..PSS-15 cover happy paths + edge + retry + cache-hit | ✅ Read §12 |
| §14 deferred to Layer 4 §14 retro per `Layer4_Spec.md` §12.6 | ✅ Read §14 |
| `Layer4_Spec.md` §3.5 amended (new `request_sport_unavailable_at_locale` error code) | ✅ `grep "request_sport_unavailable_at_locale" Layer4_Spec.md` returns 4 hits (§3.5 + §4.4 + §10.4 + §13.4 TS-33) |
| `Layer4_Spec.md` §4.4 amended (new precondition row "Sport equipment-resolvable at request locale or via `quick_equipment`") | ✅ Read §4.4 |
| `Layer4_Spec.md` §10.4 amended (sport-unavailable row 1 rewritten to point at §4.4 precondition) | ✅ Read §10.4 row 1 |
| `Layer4_Spec.md` §13.4 TS-33 amended (expected output updated) | ✅ Read §13.4 TS-33 |
| `OnDemand_Workout_D63_Design_v1.md` §6.3 amended (caller-side pre-check wording) | ✅ Read §6.3 |
| `OnDemand_Workout_D63_Design_v1.md` §9 scenario 5 amended | ✅ Read §9 |
| CLAUDE.md bumped: Layer 4 row + last-shipped + authoritative-current-files + backlog ref + next-forward-move | ✅ Diffed 5 edit locations |
| `Project_Backlog_v33.md` created with v33 header revision + v32 in predecessors | ✅ 430 lines (vs v32 429 lines — net +1 line for v32 entering predecessor list); first predecessor revision line begins with `- v32 — 2026-05-16` |
| Branch ahead of `main` by 0 commits pre-session | ✅ `git log main..HEAD` at session start |
| Working tree clean before handoff write | ✅ verified |

---

## 8. Operating notes for next session

1. **First re-read** (per Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load. Last-shipped narrative + Layer-pipeline-table + authoritative-current-files now reflect 3/5 prompt-body arc state + §10.4 amendment.
2. **Second re-read**: this handoff in full.
3. **Third re-read**: `aidstation-sources/prompts/Layer4_SingleSession_v1.md` in full — establishes (along with the prior two prompts) the conventions that propagate to the remaining 2 prompts. The three-tier intensity-modulation policy (D10 + §9.1) is the most novel pattern in this prompt body; flag it explicitly for the §14 retro to evaluate cross-prompt utility.
4. **Fourth re-read**: `aidstation-sources/prompts/Layer4_PerPhase_v1.md` + `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md` — sibling prompts; shared convention anchor.
5. **Fifth re-read (selective)**: `Layer4_Spec.md` sections relevant to the next prompt body — including the §3.5 / §4.4 / §10.4 / §13.4 TS-33 amendments from this session —
   - Per-tier T1/T2: §5.3 Pattern B, §4.3 plan_refresh validation, §6.3 single-phase T3 special case (boundary into Pattern A), §10.3 refresh edge cases, §11 T1/T2 budgets.
   - Race-week-brief: §3.4, §4.5, §5.3, §7.13 RaceWeekBrief, §7.14 RacePlan, §10.5 race-week-brief edge cases, §11 race-week-brief budgets.
6. **Per-prompt cadence still in effect** — every prompt-body session ships CLAUDE.md + backlog + PR; no end-of-arc deferral.
7. **Apply §6.2 inherited conventions** to the next prompt body — schema-enum closed-set flags, schema-enforced length caps, anchor-based judgment, hybrid retry context, read-only periodization inputs, voice + authority + iteration sections. Consider whether the three-tier policy framing applies (likely not for refresh / race-week-brief since their judgment surface is different).
8. **Stop-and-ask trigger #2 still applies** — each remaining prompt body is its own design session.
9. **Convention drift watch** — this session broke the "prompt-body sessions don't touch spec" convention from the per-phase session. The breach was Andy-approved and scoped to one D-63-specific contract issue. If a remaining prompt body surfaces a similar contract gap, surface the divergence + option-1 (defer spec amendment to separate session) vs option-2 (fold-in) choice in chat with rationale.
10. **5-file ceiling status** — this session shipped 6 substantive files (1 prompt body + 2 spec amendments + 3 bookkeeping). Per-prompt cadence means future prompt sessions typically ship 4 files. If a spec amendment is needed, propose split (option-1) by default; only fold-in (option-2) when amendment is surgical and intertwined.

---

## 9. Carry-forward from PR17 + Layer 4 spec arc + seam-reviewer + per-phase sessions (informational)

Same state as predecessors, with the per-phase landing now CLAUDE.md/backlog-acknowledged:

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — Andy confirmed pass in session 1 chat; not actioned here.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate as of `bbbb6fe` (main): unchanged this session (this is the design-track single-session synth session, not an implementation PR).
- Per-phase synth (PR #60) — landed cleanly; v32 CLAUDE.md/backlog catchup was the formal acknowledgment.

---

**End of handoff.**
