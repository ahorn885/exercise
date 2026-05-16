# Layer 4 Seam-Reviewer Prompt — v1

**Status:** Draft v1, 2026-05-16. First of 5 queued Layer 4 prompt-body designs per `Layer4_Spec.md` §12.2 + CLAUDE.md "Next forward move." Sibling files (per-phase synthesizer, per-tier T1/T2, single-session, race-week-brief) will land in this directory.
**Purpose:** The LLM call that runs between adjacent-phase outputs in Layer 4 Pattern A — emits a `SeamReview` per §7.7 with β propose-patch authority per Decision 8.
**Companion spec sections:** `Layer4_Spec.md` §5.2 step 4 (call site), §6.2 (authority semantics + verdict→action table + bounds), §7.7 (output schema), §11.1 (latency target ~3–5s per seam), §11.2 (token budget ~6000 input / ~800 output).

**Source decisions (this session, Andy 2026-05-16):**

- **D1 — output mechanism:** tool-use. `record_seam_review` tool with the §7.7 schema. No free-form output.
- **D2 — reasoning style:** extended thinking ON, ~2000 budget tokens. Latency penalty absorbed by the §11.1 ~3–5s per-seam budget.
- **D3 — input format:** hybrid. Weekly rollup table covering the full prior + next phases, plus full `PlanSession` dumps for the last week of the prior phase and the first week of the next phase (the actual seam).
- **D4 — verdict calibration:** coaching-judgment-based with concrete anchors. Pure thresholds invite gaming; anchors calibrate without locking the model into a checklist.
- **D5 — `seam_issues` writing style:** constraint-level, never solution-level. Enforced by an explicit system-prompt rule. The reviewer's job is to TELL the synthesizer what's wrong; the synthesizer (not the reviewer) produces session content.
- **D6 — voice + length:** direct coaching voice per CLAUDE.md; one tight constraint statement per issue; ≤30 words per entry; max 4 issues per seam. Beyond 4, the right move is `flagged_major + accept_with_observation` to escalate to HITL.
- **D7 — file location:** `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md` (new subdirectory; sibling prompt files will sit alongside).

None of D1–D7 are spec contracts — they are prompt-design choices. Adjustable without touching `Layer4_Spec.md`.

---

## 1. Purpose + scope

Pattern A (`plan_create` + `plan_refresh` T3 cross-phase) synthesizes phases independently — one LLM call per phase, sequentially, with the prior phase's accepted output passed in as context for the next. The seam reviewer is the LLM call that runs after per-phase synthesis completes, on each adjacent-phase pair, to catch transitions where the two outputs don't fit together as one coherent training progression.

Typical failure modes the reviewer is meant to catch:

- **Volume cliffs.** Prior phase ends at 9 hr/wk Z2 endurance; next phase opens at 6 hr/wk with no taper rationale.
- **Intensity discontinuities.** Build week 4 holds Z2 dominance; Peak week 1 jumps to Z3 dominance with no progressive introduction.
- **Race-specificity gaps.** Build→Peak boundary with race-pace work absent from the first half of Peak; or Peak→Taper boundary where the taper drops race-specific intensity prematurely.
- **Phase intent drift.** A Base phase output that's running 70/20/10 instead of the intended 80/15/5 — the synthesizer's deterministic validator should have caught this, but if it slipped through (e.g., within the ±10pp tolerance of §5.4 but trending wrong), the seam between Base→Build can amplify the drift.
- **Hard-session pileup across boundary.** Last session of prior phase = hard; first session of next phase = hard. Sometimes intentional (race rehearsal); sometimes a planning artifact.

The reviewer's verdicts carry **β propose-patch authority** per Decision 8: `flagged_major` and `patched` verdicts with a `re_prompt_*` direction cause the orchestrator to re-prompt the targeted phase with the reviewer's `seam_issues` merged in as constraint statements (subject to the per-phase retry cap per §5.5).

**Out of scope for this prompt (other prompt-body sessions own these):**

- Per-phase session content generation — the synthesizer's job.
- Pattern B refresh paths (T1, T2, T3 intra-phase) — no seam reviewer fires.
- Single-session ad-hoc workouts (D-63) — no seam reviewer fires.
- Race-week brief (D-64 follow-on) — separate prompt.
- Coaching-flag emission — the orchestrator computes flags from validator output + synthesis metadata per §8.7; the reviewer does not emit flags or observations directly. The orchestrator emits `Observation(category='warning')` on `flagged_minor`, `Observation(category='warning', elevates_to_hitl=True)` on `flagged_major + accept_with_observation`, and `Observation(category='seam_unresolved')` when the per-seam cap (§6.2) or per-phase retry budget (§5.5) is exhausted.

---

## 2. Where this runs in the Layer 4 pipeline

Per `Layer4_Spec.md` §5.2 step 4, for each adjacent-phase pair `(p_i, p_{i+1})` in `phases_synthesized`:

1. Orchestrator builds the inputs per §3 below.
2. Orchestrator calls the seam reviewer (this prompt) with `model_seam_reviewer` + sampling config per §7.
3. Reviewer responds via the `record_seam_review` tool with a complete `SeamReview` record (modulo the orchestrator-filled metadata fields).
4. Orchestrator applies §6.2 verdict→action table.
5. On `flagged_major` / `patched` with `re_prompt_*`: re-synthesize the targeted phase with the reviewer's `seam_issues` merged in; re-run §5.4 validator; re-run THIS prompt exactly once (per-seam iteration cap = 2 per §6.2).

**T3 cross-phase refresh** (§6.3): same call shape; only seams between affected (re-synthesized) phases and their adjacent neighbors get reviewed. Seams between two unaffected phases are NOT re-reviewed (they were reviewed during the original `plan_create`).

**Single-phase Pattern A** (§6.5, e.g., `plan_create` with `start_phase='Taper'` 3 weeks out from a marathon): NO seam reviewer call fires; `seam_reviews == []`. This prompt is not invoked.

---

## 3. Inputs (template variables)

Orchestrator interpolates the following when building the user prompt. All values come from contracts already pinned in `Layer4_Spec.md` or upstream Layer-2/3 payloads.

| Variable | Type | Source | Notes |
|---|---|---|---|
| `prior_phase_name` | `'Base'` / `'Build'` / `'Peak'` | §7.6 `PhaseSpec` | |
| `next_phase_name` | `'Build'` / `'Peak'` / `'Taper'` | §7.6 `PhaseSpec` | |
| `prior_phase_weeks` | int | §7.6 `PhaseSpec` | |
| `next_phase_weeks` | int | §7.6 `PhaseSpec` | |
| `mode` | str | 3B `periodization_shape.mode` | One of `standard` / `compressed` / `extended` / `custom`. Drives expectation re: how aggressive the transition should be. |
| `start_phase` | str | 3B `periodization_shape.start_phase` | When `start_phase != 'Base'`, the reviewer should not flag missing earlier-phase preparation — the athlete is starting partway through. |
| `prior_phase_weekly_rollup` | table | computed from prior phase's `PlanSession` list | Per-(week, discipline): total volume (hours), zone breakdown (Z1-Z2 / Z3 / Z4-Z5 hours), session count, key per-session flag list (any `long_slow_distance`, `weak_link_targeted`, `race_pace_specific`, `peak_volume_marker`, `overreach_test`, etc.), cornerstone-session name when one is flagged `long_slow_distance`. |
| `next_phase_weekly_rollup` | table | computed from next phase's `PlanSession` list | Same shape. |
| `prior_phase_last_week_sessions` | list[PlanSession] | tail slice of prior phase output (last 7 dates) | Full session objects — the actual seam content from one side. |
| `next_phase_first_week_sessions` | list[PlanSession] | head slice of next phase output (first 7 dates) | Same from the other side. |
| `intended_prior_exit_volume_per_discipline` | dict[discipline → (low, high) hrs] | 2A `phase_load_bands[discipline][prior_phase]` | What the prior phase was supposed to land on at exit. |
| `intended_prior_exit_intensity_distribution` | dict[zone → pct] | §5.4 v1 intensity defaults for `prior_phase_name` | E.g., Build = 70/20/10. |
| `intended_next_entry_volume_per_discipline` | dict[discipline → (low, high) hrs] | 2A `phase_load_bands[discipline][next_phase]` | What the next phase was supposed to start at. |
| `intended_next_entry_intensity_distribution` | dict[zone → pct] | §5.4 v1 intensity defaults for `next_phase_name` | |
| `race_format` | str | event metadata when event mode, else `'open_ended'` | E.g., `'expedition_ar_48_72h'` / `'marathon'` / `'ironman_70_3'`. Drives race-specificity expectations especially at Build→Peak and Peak→Taper. |
| `event_date` | date \| None | event metadata | None on open-ended mode. |
| `days_to_event_at_seam` | int \| None | `event_date - seam_date` | None on open-ended. Sharpens the Peak→Taper review — a Peak→Taper seam with `days_to_event_at_seam == 28` for an expedition AR vs. `days_to_event_at_seam == 14` for a marathon are different judgment calls. |
| `discipline_mix` | list[str] | 2A `discipline_inclusion` | Drives discipline-specific seam reasoning (e.g., a 5-discipline AR athlete has more seam-coordination complexity than a single-sport runner). |
| `active_injury_summary` | list[str] | trimmed from 3A `active_injuries` | One short line per injury — body part + 1-line restriction summary. The reviewer uses this to NOT flag missing intensity if intensity is medically restricted. |
| `seam_iteration` | 1 \| 2 | orchestrator (§6.2 per-seam cap) | On iteration 2, the reviewer is re-evaluating after one re-synthesis triggered by iteration 1's `re_prompt_*` direction. |
| `prior_seam_issues` | list[str] | iteration 2 only; empty on iteration 1 | The issues from iteration 1 that triggered the re-prompt — so the reviewer can judge whether the re-synthesis addressed them. |

**Intentionally NOT passed to the reviewer** (scope discipline — reviewer's job is phase-transition shape, not session-level fitness):

- Phases beyond the two adjacent to this seam. (Reviewer cannot mutate distant phases per §6.2 bounds.)
- 2B terrain / 2C equipment / 2E nutrition / Layer 1 form payloads. (Synthesizer's job; not relevant to boundary shape.)
- §K schedule windows. (Deterministic validator's job per §5.4 `schedule_violation_*`.)
- The full coaching-flag taxonomy. (Reviewer does not emit flags; only consumes them as signal in the rollup.)
- Layer 0 reference data (exercise library, sport framework). (Synthesizer's job.)

This trimming is what keeps the §11.2 ~6000 input token estimate realistic. Adding more input either bloats the budget or pushes the reviewer toward second-guessing synthesizer decisions outside its authority.

---

## 4. Output schema + tool definition

The reviewer MUST respond by invoking the `record_seam_review` tool exactly once. No free-form output. Tool input schema mirrors §7.7 `SeamReview` minus the orchestrator-filled metadata (`seam_index`, `prior_phase_name`, `next_phase_name`, `reviewer_model`, `*_tokens`, `*_latency_ms`, `triggered_resynthesis`, `re_prompted_phase_name`).

```json
{
  "name": "record_seam_review",
  "description": "Record your seam review for this adjacent-phase pair. Call this tool exactly once. Do not emit free-form text outside the tool call.",
  "input_schema": {
    "type": "object",
    "required": ["reviewer_verdict", "seam_issues", "proposed_patch_direction"],
    "additionalProperties": false,
    "properties": {
      "reviewer_verdict": {
        "type": "string",
        "enum": ["approved", "flagged_minor", "flagged_major", "patched"]
      },
      "seam_issues": {
        "type": "array",
        "items": {"type": "string", "minLength": 1, "maxLength": 240},
        "maxItems": 4,
        "description": "Empty array on 'approved'. One constraint statement per issue. ≤30 words per entry. Constraint-level (what the synthesizer must satisfy), not solution-level (specific sessions to add/remove). See §10."
      },
      "proposed_patch_direction": {
        "type": ["string", "null"],
        "enum": ["re_prompt_prior", "re_prompt_next", "accept_with_observation", null],
        "description": "Null on 'approved' and 'flagged_minor'. Populated on 'flagged_major' and 'patched'. NEVER 'accept_with_observation' on 'patched' (invalid combination per Layer4_Spec §6.2)."
      }
    }
  }
}
```

**Invalid output combinations** — output parser raises `Layer4OutputError('seam_reviewer_invalid_verdict_combination')` per §6.2; one schema retry per §5.5, then bail out of the call:

| Combination | Why invalid |
|---|---|
| `patched` + `accept_with_observation` | `patched` implies a re-prompt direction (the reviewer is proposing a fix); accept-with-observation contradicts that. Per §6.2 verdict table. |
| `flagged_major` + null direction | `flagged_major` requires a direction per §6.2. |
| `approved` + non-empty `seam_issues` | Approval means no issues. |
| `approved` + non-null `proposed_patch_direction` | Approval means no patch. |
| `flagged_minor` + non-null `proposed_patch_direction` | Per §6.2: flagged_minor is record-only; no re-prompt. |
| `seam_issues` length > 4 | Schema cap per §6.2 + D6. Beyond 4 issues, the right verdict is `flagged_major + accept_with_observation` to escalate. |

---

## 5. System prompt (verbatim)

```
You are the seam reviewer for an endurance and multi-sport training pipeline. Your job is narrow: assess whether the transition between two adjacent periodization phases — produced independently by separate synthesizer calls — fits cleanly as a single coherent training progression.

You read two phases' session outputs plus the boundary state the synthesizer was supposed to land on (the prior phase's intended exit volume and intensity distribution, and the next phase's intended entry). You emit exactly one verdict via the `record_seam_review` tool. No free-form text.

VERDICTS:

- `approved` — the transition is clean. Volume continuity, intensity progression, and race-specificity all track. No issues. `seam_issues` empty; `proposed_patch_direction` null.

- `flagged_minor` — the transition has rough edges within typical periodization variance. The athlete would not notice; adaptation outcomes are not at risk. Record-only; no re-synthesis. `seam_issues` populated (1–4 entries) describing the rough edges; `proposed_patch_direction` null.

- `flagged_major` — the transition is meaningfully wrong. Examples: a volume cliff with no taper rationale; an intensity-zone shift that breaks the phase intent; race-specificity missing from Peak entry where the event format requires it; a deload week where one shouldn't be. Re-synthesis of one side of the seam is warranted. `seam_issues` populated; `proposed_patch_direction` is one of `re_prompt_prior` / `re_prompt_next` / `accept_with_observation`.

- `patched` — same severity as `flagged_major`, plus you are confident the re-synthesis direction you propose will resolve the issue. `seam_issues` populated; `proposed_patch_direction` is `re_prompt_prior` or `re_prompt_next` (NEVER `accept_with_observation` — that is a schema violation).

CALIBRATION ANCHORS (use coaching judgment around these, not as thresholds):

- "Within typical periodization variance" ≈ volume drift ≤10% week-over-week without rationale; zone-distribution drift ≤8pp from intended; race-specificity present where expected.
- A week-over-week volume drop >25% with no taper rationale: `flagged_major`.
- A zone shift breaking the phase intent's stated distribution (e.g., Peak starting Z3-dominant when intended Z2-dominant): `flagged_major`.
- A missing race-pace introduction in the first half of Peak when the event format requires race-pace specificity (marathon, IM-class, ultras): `flagged_major`.
- Two consecutive hard sessions across the boundary (last session of prior phase + first session of next phase both `intensity_summary == 'hard'`): `flagged_minor` if there's a logical reason (race rehearsal, overreach week), `flagged_major` otherwise.
- Intensity restricted by an active injury (see active_injury_summary): treat reduced intensity as expected, NOT as a missing element.

PATCH DIRECTION:

- `re_prompt_prior` — the problem is the prior phase's exit (e.g., prior phase ended too high in volume; should taper down).
- `re_prompt_next` — the problem is the next phase's entry (e.g., next phase opens too aggressive; should ramp in).
- `accept_with_observation` — the seam is meaningfully wrong AND re-synthesis won't help (e.g., both sides are constrained by independent factors that re-prompting can't reconcile). Escalates to HITL gate via the orchestrator.

`seam_issues` WRITING RULES (load-bearing — violations push you outside your authority):

- Each entry is one tight sentence, ≤30 words.
- Constraint-level, not solution-level. Describe the constraint the synthesizer must satisfy, NOT specific sessions to add or remove. Examples:
  - Good: "Peak week 1 must hold ≥60% Z2 with at most one Z3 introduction session; current entry is Z3-dominant."
  - Bad: "Replace Peak week 1 day 2 with a Z2 long ride." (You do not have session-mutation authority. The synthesizer produces sessions.)
- Cite the boundary observation that prompted the constraint. Example: "Observed: Build week 4 ends ~9 hr Z2; Peak week 1 starts ~6 hr Z3. Constraint: Peak week 1 entry must hold ≥60% Z2."
- No platitudes. Do not write "nice transition" or "good progression" or "consider improving X." Either there is a constraint to state or there is no issue (use `approved`).
- Max 4 entries. Beyond 4, choose `flagged_major + accept_with_observation` and let the orchestrator escalate.

AUTHORITY BOUNDS — WHAT YOU CANNOT DO:

- You cannot rewrite individual sessions. Your output is constraints, not sessions.
- You cannot change phase boundaries, mode, or start_phase. Those are fixed by Layer 3B + Layer 4 §6.4 only.
- You cannot evaluate phases beyond the two adjacent to this seam. You only see two phases per call; reason about them.
- You cannot emit coaching flags or observations directly. The orchestrator computes those downstream from your verdict.
- You cannot request changes to phases more than one hop from the seam.
- You cannot exceed 4 entries in `seam_issues`. Schema cap.

ITERATION 2 BEHAVIOR:

If `seam_iteration == 2`, you are re-evaluating after one re-synthesis triggered by your iteration-1 verdict. The `prior_seam_issues` field contains the issues you raised on iteration 1. Judge:

- Did the re-synthesis address the prior issues? If yes and the seam is now clean: `approved`. If yes but new minor edges appeared: `flagged_minor`.
- If the prior issues remain or new major issues appeared: emit a final verdict. Note that the orchestrator will NOT re-prompt again (per-seam cap is 2). Your iteration-2 `flagged_*` verdict will be recorded but no further re-synthesis happens; the orchestrator emits a `seam_unresolved` observation. Therefore on iteration 2, prefer `flagged_major + accept_with_observation` over `flagged_major + re_prompt_*` when you judge the seam is unfixable in this call — surfaces the issue to the HITL gate cleanly.

VOICE: direct, evidence-grounded. No cheerleading. No hedging. Match a real endurance coach reviewing a colleague's plan.
```

---

## 6. User prompt template (verbatim, with `{{var}}` placeholders)

```
SEAM REVIEW REQUEST — iteration {{seam_iteration}}

Adjacent phases: {{prior_phase_name}} → {{next_phase_name}}
3B periodization mode: {{mode}} (start_phase: {{start_phase}})
Discipline mix: {{discipline_mix}}
Race context: {{race_format}}{{#if event_date}}, event {{event_date}} ({{days_to_event_at_seam}} days from seam){{/if}}

ACTIVE INJURY CONSTRAINTS:
{{#each active_injury_summary}}- {{this}}
{{/each}}{{#unless active_injury_summary}}(none){{/unless}}

INTENDED BOUNDARY STATE:

{{prior_phase_name}} intended exit (per 2A phase_load_bands):
- Volume per discipline (hr/wk range): {{intended_prior_exit_volume_per_discipline}}
- Intensity distribution (Z1-Z2 / Z3 / Z4-Z5): {{intended_prior_exit_intensity_distribution}}

{{next_phase_name}} intended entry (per 2A phase_load_bands):
- Volume per discipline (hr/wk range): {{intended_next_entry_volume_per_discipline}}
- Intensity distribution (Z1-Z2 / Z3 / Z4-Z5): {{intended_next_entry_intensity_distribution}}

PRIOR PHASE — {{prior_phase_name}} ({{prior_phase_weeks}} weeks)

Weekly rollup:
{{prior_phase_weekly_rollup}}

Last week sessions (full detail — this is the seam):
{{prior_phase_last_week_sessions}}

NEXT PHASE — {{next_phase_name}} ({{next_phase_weeks}} weeks)

Weekly rollup:
{{next_phase_weekly_rollup}}

First week sessions (full detail — this is the seam):
{{next_phase_first_week_sessions}}

{{#if prior_seam_issues}}
ITERATION 1 ISSUES (these triggered the re-synthesis you are now reviewing):
{{#each prior_seam_issues}}- {{this}}
{{/each}}
{{/if}}

Review this seam. Call `record_seam_review` with your verdict.
```

Template variables interpolate as plain text. The `{{prior_phase_weekly_rollup}}` and `{{*_sessions}}` fields are rendered as Markdown tables / JSON blocks by the orchestrator at prompt-build time; the LLM reads them as plain context. Mustache-style `{{#if}}` / `{{#each}}` blocks are pseudo-code for the orchestrator's template engine — actual rendering language is an implementation detail (Python f-string + conditional concat is fine for v1).

---

## 7. Model + sampling config

| Setting | Value | Source |
|---|---|---|
| `model` | `claude-sonnet-4-6` | Layer4_Spec.md §3.1 v1 default `model_seam_reviewer`. Haiku downgrade is a post-launch tuning candidate per §11.4 + §12.4. |
| `temperature` | 0.15 | Lower than the synthesizer's 0.2 per §5.2 step 4.1 ("lower `temperature`"). Reviewer is a judgment task, not a creative one. |
| `max_tokens` | 1500 | Headroom over the §11.2 ~800 output token estimate to accommodate extended thinking tokens (counted separately by the API but contribute to output budget) + worst-case 4-entry `seam_issues` array with 240-char entries (~1000 chars + JSON envelope). |
| Extended thinking | Enabled, ~2000 budget tokens | D2. Reviewer reasoning quality matters; latency tax is ~2–4s, within the §11.1 ~3–5s per-seam budget. |
| Tool choice | `{"type": "tool", "name": "record_seam_review"}` | Forces tool use. Reviewer must respond via tool. |
| Stop sequences | (none) | Tool-use natural stop. |

Token accounting per call (rough): ~6000 input + ~2000 extended thinking + ~800 tool-use output = ~6000 input / ~2800 total output. Matches §11.2 with thinking-token caveat. Cost at v1 Sonnet 4.6 pricing ($3/MTok in + $15/MTok out): ~$0.018 + ~$0.042 = ~$0.06 per seam review. For Andy's `plan_create` case (3 seams), ~$0.18 of the $0.50–1.10 per-call envelope per §11.3.

---

## 8. Authority bounds — explicit forbid list (recap)

The system prompt §5 above carries the authority-bound rules in-band. This subsection mirrors §6.2's "what the reviewer CANNOT do" list, with prompt-design notes on how each is enforced:

| Bound (per §6.2) | Enforcement in this prompt |
|---|---|
| Cannot request changes to phases > 1 hop from seam | Inputs only contain the two adjacent phases. Reviewer literally has no information about other phases. |
| Cannot force re-synthesis of a phase whose retry budget is exhausted | Reviewer doesn't know retry budgets; the orchestrator filters per §6.2 (if cap exhausted, accept current + emit `seam_unresolved`). Reviewer's `re_prompt_*` may be recorded but not acted on. |
| Cannot insert or delete phases | Schema does not include phase-add / phase-remove fields. |
| Cannot change `mode` or `start_phase` | Same. `mode` and `start_phase` are read-only in the user prompt. |
| Cannot directly modify individual sessions outside the targeted phase's re-synthesis | `seam_issues` writing rules (D5) explicitly forbid solution-level statements; the schema records issues as text constraints, not session diffs. |
| Cannot emit coaching flags or observations | Schema does not include flag-emit fields. Orchestrator computes flags/observations from validator output + reviewer verdict downstream per §8.7. |

If the model ever attempts to violate a bound (e.g., writes a solution-level `seam_issues` entry, or attempts free-form text alongside the tool call), the orchestrator does not enforce post-hoc — the prompt's writing rules are the only enforcement. Drift is a tuning signal: surface it in §11.8 alert thresholds and adjust the prompt.

---

## 9. Verdict calibration — coaching anchors (D4)

The prompt's calibration anchors (in §5 system prompt) are NOT thresholds — they're examples that ground the reviewer's coaching judgment. Per D4, pure thresholds invite gaming ("I'm at 24.9% drop, so technically `flagged_minor`"); pure judgment without anchors invites verdict drift across calls. The combination — coaching judgment WITH concrete anchors — is the calibration v1 ships with.

**Anchors in the prompt:**

| Situation | Anchor verdict | Rationale |
|---|---|---|
| Volume drift ≤10% wk-over-wk, zone-distribution drift ≤8pp from intended, race-specificity present | `approved` | "Within typical periodization variance." |
| Volume drop >25% wk-over-wk with no taper rationale | `flagged_major` | Athlete would notice; adaptation outcomes at risk. |
| Zone shift breaking phase intent (e.g., Peak Z3-dominant when intended Z2) | `flagged_major` | Phase intent mismatch is a structural error, not variance. |
| Missing race-pace intro in first half of Peak (when format requires) | `flagged_major` | Race-specificity is a Peak deliverable. |
| Two hard sessions across boundary, with logical rationale | `flagged_minor` | E.g., race rehearsal at end of Build + tempo entry into Peak. |
| Two hard sessions across boundary, no rationale | `flagged_major` | Recovery violation. |
| Intensity reduced because of active injury restriction | NOT a flag | Reviewer reads `active_injury_summary` and adjusts expectations. |

**Tuning candidates** (post-launch; per §12.4 catch-all):

- Anchor thresholds themselves (the 10% / 8pp / 25% numbers) are evidence-grounded starting points. Telemetry on verdict distribution (how often does the reviewer emit `flagged_major` per 100 plan_create calls? How often does re-synthesis after `flagged_major` resolve to `approved` on iteration 2?) will drive recalibration.
- Race-format-specific anchors. Currently the prompt names "marathon, IM-class, ultras" as race-pace-requiring formats; an `expedition_ar_48_72h` (Andy's case) is more nuanced — race-pace is less of a Peak deliverable than race-condition-rehearsal (gear, fueling, locale). The prompt does NOT currently encode this; v1 acceptance is that the model can infer from `race_format` + `discipline_mix`.

---

## 10. `seam_issues` writing rules (D5 + D6)

Lifted into the system prompt (§5). Recap with prompt-design rationale:

| Rule | Rationale |
|---|---|
| One tight constraint statement per issue, ≤30 words | Keeps the synthesizer's re-prompt context compact; per §6.2, `seam_issues` are merged in as constraint deltas. Verbose entries dilute. |
| Constraint-level, NOT solution-level | The reviewer cannot mutate sessions per §6.2 authority bounds. Solution-level entries push the reviewer outside its authority and confuse the re-prompted synthesizer (it doesn't know whether to obey the constraint or copy the prescribed sessions). |
| Cite the boundary observation that prompted the constraint | Gives the synthesizer the WHY, which improves re-synthesis quality. Without the cite, the synthesizer may satisfy the constraint locally but break something else. |
| No platitudes | CLAUDE.md voice rule. "Nice progression" is not a constraint; it's not even an observation. |
| Max 4 entries per seam | Schema cap (per §6.2 + D6). Beyond 4 issues, the reviewer should escalate via `flagged_major + accept_with_observation`. |

**Example seam_issues entries (v1 reference set — keep in mind during prompt tuning):**

- "Observed: Build wk 4 ends ~9 hr Z2 endurance; Peak wk 1 opens ~6 hr Z3. Constraint: Peak wk 1 must hold ≥60% Z2 with one Z3 introduction session max."
- "Observed: no race-pace work in Peak wk 1–2; race is marathon-class at day 35. Constraint: introduce one race-pace cardio block by Peak wk 2."
- "Observed: Build wk 4 last session = hard MTB; Peak wk 1 day 1 = hard run. Constraint: insert ≥48h recovery between phase-boundary hard sessions or attach `overreach_test` / `race_rehearsal` rationale."
- "Observed: Peak→Taper boundary drops volume 40% in 1 wk for expedition AR (event 28d out). Constraint: Taper wk 1 should hold 75–80% of Peak peak-week volume; deeper cut starts wk 2."

**Counter-examples (what NOT to write):**

- "Peak week 1 day 2 should be a Z2 long ride." (solution-level)
- "Nice progression overall, but maybe consider a slightly more gradual transition." (platitude + non-constraint)
- "I notice the volume is high in Build week 4 and lower in Peak week 1. This could be a problem because athletes generally benefit from gradual transitions and the body adapts better when load is progressive rather than sudden. I recommend that the synthesizer adjust the volume in Peak week 1 to be closer to Build week 4." (>30 words; mostly narrative; vague constraint)

---

## 11. Edge cases + invalid combinations

### 11.1 Iteration 2 with prior issues fully resolved

Reviewer reads `prior_seam_issues`, observes that the re-synthesized phase addresses each one cleanly. Verdict: `approved`. No new `seam_issues`.

### 11.2 Iteration 2 with prior issues partially resolved + new issues

Reviewer reads `prior_seam_issues`, observes 2 of 3 prior issues resolved, but the re-synthesis introduced a new minor seam (e.g., the constraint to hold Z2 in Peak wk 1 was met, but Peak wk 2 now jumps too aggressively). Verdict: `flagged_minor` if the new issue is within variance; `flagged_major + accept_with_observation` if it's structurally wrong AND the per-seam cap (2) means no further re-prompting. Avoid `flagged_major + re_prompt_*` on iteration 2 — the cap is reached; the orchestrator records the direction but does not act.

### 11.3 Iteration 2 with prior issues unresolved

Reviewer reads `prior_seam_issues`, observes the re-synthesis did not address them. Verdict: `flagged_major + accept_with_observation`. The orchestrator will emit `seam_unresolved` per §6.2.

### 11.4 Approved seam with rough edges noted

If the seam is clean enough to approve but the reviewer notices minor edges worth recording: the schema does not have an "approved with notes" tier. Either downgrade to `flagged_minor` (which IS the "rough edges, no action" tier) or stay `approved`. The prompt instructs `flagged_minor` for "rough edges within typical periodization variance" — use it.

### 11.5 Schedule violations at the boundary

Reviewer sees a session prescribed on a date that's marked unavailable in §K. NOT a seam concern — this is the deterministic validator's job (`schedule_violation_*` per §5.4). The reviewer should NOT flag schedule violations. If the reviewer flags one anyway, the orchestrator processes the verdict normally (no special handling), but the noise pollutes the `seam_issues` log. Prompt rule (in §5): reviewer's job is phase-transition shape, not session-level validation.

### 11.6 Active injury inferring "missing intensity"

Reviewer sees Peak entry with intensity below intended distribution and is tempted to flag. But `active_injury_summary` lists "left wrist: avoid wrist-extension-loaded exercises" and the discipline mix includes climbing. The intensity reduction may be injury-driven, not phase-error-driven. Prompt rule (in §5): "Intensity restricted by an active injury (see active_injury_summary): treat reduced intensity as expected, NOT as a missing element."

### 11.7 Output parser invalid-combination handling

If the reviewer emits one of the invalid combinations from §4 (e.g., `patched + accept_with_observation`), the output parser raises `Layer4OutputError('seam_reviewer_invalid_verdict_combination')`. Per §5.5 schema-violation policy: one schema retry (counter does NOT consume the per-phase budget); on second failure, raise + bail out of the Layer 4 call. The orchestrator does not silently coerce — invalid combos surface as errors so the prompt can be tightened if they recur.

### 11.8 Reviewer emits no tool call

If the reviewer emits free-form text without invoking `record_seam_review` (e.g., explains its reasoning instead of calling the tool): parser raises `Layer4OutputError('schema_violation')`. Same retry/bail policy as 11.7. The prompt's "No free-form text. Call this tool exactly once." instructions are the primary defense; tool_choice forcing is the secondary.

---

## 12. Test scenarios (v1)

Maps to `Layer4_Spec.md` §13 TS-15 through TS-21 (Pattern A seam paths) + adds prompt-body-specific tests. These are LLM-output tests (recorded golden cases + new live runs), not deterministic logic tests.

| # | Scenario | Setup | Expected verdict |
|---|---|---|---|
| SR-1 | Clean Base→Build transition | Volume ramp +15%, intensity stays Z2-dominant per Build intent, no hard-session pileup | `approved` + empty issues |
| SR-2 | Volume cliff Build→Peak (no taper rationale) | Build wk 4 ends 9hr Z2; Peak wk 1 opens 6hr Z3 | `flagged_major` + `re_prompt_next` + 1–2 constraint statements |
| SR-3 | Zone shift Peak entry (intended Z2-dominant, got Z3-dominant) | Peak intended distribution 70/20/10; output 50/30/20 | `flagged_major` + `re_prompt_next` |
| SR-4 | Missing race-pace intro in first half of Peak | Marathon at day 35; Peak wk 1–2 zero race-pace sessions | `flagged_major` + `re_prompt_next` |
| SR-5 | Two hard sessions across boundary with race-rehearsal rationale | Both hard; prior session flagged `race_rehearsal` | `flagged_minor` (rationale visible) |
| SR-6 | Two hard sessions across boundary, no rationale | Both hard; no flags | `flagged_major` + `re_prompt_prior` |
| SR-7 | Intensity reduced by active wrist injury | Climbing-heavy mix; wrist injury active; reduced climbing intensity Peak entry | `approved` (the reduction is injury-driven, not phase-error) |
| SR-8 | Iteration 2, prior issues resolved cleanly | Iteration 1 verdict `flagged_major + re_prompt_next` with 1 constraint; iteration 2 sees the constraint satisfied | `approved` |
| SR-9 | Iteration 2, prior issues unresolved | Same iteration-1 setup; iteration 2 sees the constraint NOT met | `flagged_major` + `accept_with_observation` (cap reached; escalate) |
| SR-10 | Reviewer-emits-invalid-combo defense | Synthetic: prompt-stress test where the model emits `patched + accept_with_observation` | Output parser raises; one schema retry; bail on second |
| SR-11 | Expedition AR Peak→Taper at day 28 | Expedition AR format; Peak ends at day 28; Taper drops volume 40% wk 1 | `flagged_major` + `re_prompt_next` (Taper too aggressive for 28-day window on AR) |
| SR-12 | Open-ended mode Build→Peak | `race_format == 'open_ended'`; no event_date | `approved` if shape is clean; reviewer doesn't flag missing race-pace (no race format to anchor against) |
| SR-13 | Single-phase Pattern A (no seam) | `start_phase='Taper'` + 3-week event window | THIS PROMPT IS NOT INVOKED. Test verifies orchestrator skips the seam-review call per §6.5. |
| SR-14 | T3 cross-phase refresh, seam between unaffected and affected phase | Refresh window spans Build→Peak; only Peak re-synthesized | Reviewer runs; receives prior Build (unaffected) + new Peak. Verdict per quality. |
| SR-15 | seam_issues > 4 (model attempts) | Synthetic: prompt-stress where the model wants to emit 6 issues | Schema cap rejects; output parser raises; one schema retry; on second failure, bail. (Tuning signal — surface in §11.8.) |

These slot into `Layer4_Spec.md` §13 under the existing TS-15..TS-21 seam-path block when the next §13 expansion happens; they're prompt-body-specific tests that don't belong in the spec.

---

## 13. Open items / tuning candidates

All v1; tune post-launch per the §12.4 catch-all.

- **Calibration-anchor thresholds** (10% / 8pp / 25%). Evidence-grounded starting points; tune from production verdict distribution.
- **Race-format-specific anchor refinement.** v1 names "marathon, IM-class, ultras" as race-pace-requiring formats. Expedition AR, swimrun, modern pentathlon need their own race-specificity expectations encoded if the model under-anchors on `race_format` alone.
- **Haiku downgrade** for seam-reviewer model. Per §11.4 + §12.4; cost savings ~5x on the seam-review calls if Haiku judgment is good enough. Measure after first ~500 production seam reviews.
- **Extended-thinking budget** (2000 tokens). Tunable per D2; can drop to 1000 if quality is unaffected (latency win ~1s) or raise to 3000 if quality is uneven on tricky seams.
- **Hybrid input format token tuning** (D3). Currently: full weekly rollup + full last-week-of-prior + full first-week-of-next. If §11.2 ~6000 input budget is exceeded in practice (e.g., for 5-discipline AR athletes with many sessions/week), drop to rollup-only for the non-seam-week context.
- **Iteration-2 verdict bias.** Current prompt instruction prefers `flagged_major + accept_with_observation` over `flagged_major + re_prompt_*` on iteration 2 (since cap is reached). Verify in production that the reviewer follows this; if not, sharpen the prompt rule.
- **`seam_issues` 4-entry cap.** May be too low for genuinely complex seams (e.g., 5-discipline AR where each discipline has a different transition profile). Schema cap raise vs. escalation-via-`accept_with_observation` is a measurement-driven call.

None are spec-contract decisions — all are prompt-design choices Andy can adjust by editing this file without touching `Layer4_Spec.md`. A v2 of this file would be `Layer4_SeamReviewer_v2.md` per Rule #12.

---

## 14. Gut check — deferred to Layer 4 §14 retro

Per `Layer4_Spec.md` §12.6, the spec's §14 retrospective is deferred to a fresh-eyes follow-on session before Layer 4 implementation begins. This prompt-body's gut check folds into that retro: the seam reviewer is the smallest of 5 queued prompt bodies, and design conventions established here (tool-use output mechanism, extended thinking, hybrid input format, coaching-judgment-with-anchors calibration, constraint-level issue writing) propagate to the other 4. The retro is the right venue to evaluate whether those conventions held up across all 5 — premature to retro this one prompt in isolation.

Inline risks worth flagging here for the §14 retro to fold in:

1. **β authority is hard to teach in prose.** The "constraint-level not solution-level" rule is subtle; LLMs reliably violate subtle rules. Production telemetry on `seam_issues` content (sampling for solution-level vs constraint-level entries) is the verification mechanism. If violation rate is high, the prompt needs sharper enforcement (more examples, more explicit forbids, possibly a per-entry validation pass).
2. **Verdict drift across calls.** The same seam reviewed twice (e.g., regression test) may emit different verdicts at temperature 0.15. Acceptable variance vs. unacceptable drift is a tuning question; the §11.8 alert thresholds (cost per invocation > 2× design for 24h) catch gross drift but not subtle verdict-distribution shift.
3. **Input-shape coupling to synthesizer output.** This prompt assumes the synthesizer emits `PlanSession` with `coaching_flags` populated, `intensity_summary` set, etc. If the synthesizer prompt (queued — separate session) deviates from this assumed shape, the rollup-computation step + the user prompt's session dumps will need updating. Coupling is real but contained; the §7 schema in `Layer4_Spec.md` is the contract both prompts honor.
4. **Calibration anchors may not survive race-format diversity.** v1 anchors are tuned for endurance/multi-sport disciplines this spec serves; specific anchors for expedition AR (Andy's case) are weak. Production with Andy's plan as test case will surface gaps quickly.

---

*End of Layer 4 Seam-Reviewer Prompt v1. Next prompt body (Andy's pick from queue): per-phase synthesizer / per-tier T1/T2 / single-session / race-week-brief.*
