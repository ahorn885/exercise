# V5 Design Layer 4 — Race-Week Brief Synthesizer Prompt Body Closing Handoff

**Session:** Ships the race-week brief synthesizer prompt body (fifth and last of 5 in the Layer 4 prompt-body arc per the predecessor T1/T2 handoff §6 forward pointers). **The Layer 4 prompt-body arc is now COMPLETE.** Unified file with multi-day branch per Andy's Pick 1 (option (a) — accepted the architect's recommendation; rejected the two-file split).
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Design_Layer4_Prompts_RefreshT1T2_Closing_Handoff_v1.md` (T1/T2 shipped + merged on main via PR #65; this session opened against the §6 forward pointers — Andy picked race-week-brief as the final prompt body).
**Branch:** `claude/review-design-handoff-CuXt4`.
**Status:** 🟢 1 substantive prompt body file shipped (`Layer4_RaceWeekBrief_v1.md` — 955 lines), 3 bookkeeping (CLAUDE.md, Project_Backlog v36 → v37, this handoff). 4 files total — under the 5-file ceiling. No spec amendments this session (broke the spec-amendment precedent from single-session §10.4 + T1/T2 §8.6/§8.7 — race-week-brief consumes the v1 spec contract without surfacing any contract gap).

---

## 1. Session-start verification (Rule #9)

Predecessor T1/T2 handoff §6 forward pointer claimed: T1/T2 session shipped via PR #65 (merged on main; `9e1ef43` then `d70492c` merge commit); branch `claude/review-design-handoff-CuXt4` sits at the same commit as main; next session candidates include Layer 4 §14 retro, race-week-brief (1 remaining prompt body), Layer 4 implementation track.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` exists | `ls` | ✅ 664 lines |
| `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` exists | `ls` | ✅ 570 lines |
| `Layer4_Spec.md` §8.6 broadened `intensity_modulated` trigger | `grep -n` line 1045 | ✅ |
| `Layer4_Spec.md` §8.7 references broadened §8.6 | `grep -n` line 1057 | ✅ |
| Backlog at v36 | `ls Project_Backlog_v*.md \| sort -V \| tail` | ✅ |
| CLAUDE.md Backlog ref reads `Project_Backlog_v36.md` | `grep -n` | ✅ line 58 |
| Latest handoff is T1/T2 | `ls handoffs/V5_Design_Layer4_Prompts_*` | ✅ |
| Branch clean off main tip `d70492c` | `git status` + `git log` | ✅ |

**Drift found:**
- T1/T2 handoff §7 claimed `Layer4_RefreshT2_v1.md` is ~750 lines; actual is 570 lines (~24% short of claim). Substantively complete (all 14 numbered sections + decision table); the drift is a line-count-claim issue, not a missing-content issue. Flagged for awareness; not blocking.
- T1/T2 handoff §7 + §3.x claimed "14 H2 sections" for both files; actual is 15 H2 (one for "Source decisions" header + 14 numbered §§1–14). Cosmetic count mismatch.

Andy picked **race-week-brief prompt body (5 of 5)** via `AskUserQuestion` at session start (rejected Layer 4 §14 retro / critical review of T1/T2 handoff / Layer 4 implementation as next-track candidates).

---

## 2. Session narrative — three architectural picks

After session-start verification + reading the relevant input files (`Layer4_Spec.md` §3.4 race-week-brief entry point + §4.5 input validation + §5.1 pattern routing + §5.4 race-week-brief validator scope + §7.13 RaceWeekBrief schema + §7.14 RacePlan schema + §8.5 Taper spec-auto coaching flags + §9.1 race-week-brief cache key + §9.3 midnight-UTC invalidation + §11.1 latency expectation), and skimming the prior prompt bodies for inherited conventions (`Layer4_SingleSession_v1.md` for the Pattern B single-call structure + closed-set flag enforcement; `Layer4_PerPhase_v1.md` for the anchor-table-based judgment for prompt-internal heuristics + token budget framing; `Layer4_RefreshT1_v1.md` for inputs structure on multi-payload Pattern B; `Layer4_RefreshT2_v1.md` for the full verbatim-window precedent), the architect (Claude) presented three load-bearing architectural picks to Andy via `AskUserQuestion`:

### 2.1 Pick 1 — File scope

Options presented:
- (a) **Unified file with multi-day branch** (`Layer4_RaceWeekBrief_v1.md`) — one file; Mustache-style `{{#multi_day}}…{{/multi_day}}` block at the RacePlan emission slot in §6; coaching logic is shared (Taper modulation, kit-check cadence, fueling, contingencies); multi-day extension is structurally additive (segment + transition + night-section reasoning) not conceptually different. ~750–900 lines. **Architect-recommended.**
- (b) Two files — `Layer4_RaceWeekBriefSingleDay_v1.md` + `Layer4_RaceWeekBriefMultiDay_v1.md`. Distinct §9 guidance; multi-day adds segment + transition + night-section reasoning that doesn't fit cleanly under conditional logic. ~500 + ~700 lines = ~1200 total. 6–7 files over the ceiling (1 more than unified).
- (c) Three files split by race_format depth (single_day / stage_race / expedition_ar+multi_day_ultra). Most surface area; tightest per-format tuning. Aggressively over-decomposed for v1.

**Andy picked (a) — unified file.** Took the architect's recommendation. Rationale: coaching surface is shared across single-day + multi-day; multi-day extension is structurally additive (segment + transition + night-section reasoning) not conceptually different. Carries the single-session unified-prompt precedent (Mustache branch at the equipment-injection slot for locale/quick_equipment). Rejects T1/T2's two-file precedent — single-day vs multi-day race-week share more coaching surface than T1 vs T2 (T2 has weekly-volume-as-validator load-bearing constraints that don't apply to T1; race-week-brief single-day vs multi-day differ only in whether RacePlan is emitted).

### 2.2 Pick 2 — Pacing strategy depth

Options presented:
- (a) **Hybrid — hard where 3A supports, heuristic otherwise.** Concrete pace/HR/power targets where 3A's recent training data supports them; RPE + qualitative guidance where it doesn't (expedition AR night sections, terrain-variable segments). Per-segment `pacing_target` uses whichever measure the discipline supports. **Architect-recommended.**
- (b) Hard numeric targets across the board. Every segment + pacing_strategy_summary carries concrete numbers (pace per km, HR zone, power W). Athlete sees specificity. Risks breaking in long multi-day events where fatigue + conditions degrade hard targets early.
- (c) RPE + heuristic guidance only. Qualitative pacing ("Z2 dominant", "conservative on climbs"). Robust to multi-day fatigue + condition variance. Loses 3A's data leverage for short single-day races where athlete has measurable race-pace data.

**Andy picked (a) — hybrid.** Took the architect's recommendation. Rationale: leverages 3A's data for races where athlete has measurable race-pace history (single-day road events; well-trained disciplines); falls back to RPE for expedition AR night sections, technical terrain, and any segment where conditions degrade hard targets early. The decision rule per D5 in the file header: hard numeric targets when 3A `data_density ∈ {rich, moderate}` AND discipline supports it natively; RPE + qualitative heuristic when data is thin OR conditions degrade hard targets (night sections, technical terrain, multi-day fatigue past hour N).

### 2.3 Pick 3 — Contingency depth

Options presented:
- (a) **Mixed — anchor table for must-haves + synthesizer expands.** Short anchor table of must-have contingency categories per race_format + LLM expands within each + adds athlete-specific (2D injury re-aggravation; 3A weak_links). Ensures must-have coverage; allows discretion. **Architect-recommended.**
- (b) Synthesizer-derived only. LLM picks 4–8 contingencies from 2D injuries + 2E fueling + race format constraints; no fixed list. Maximum context-sensitivity. Risks missing must-have categories (e.g., AR brief without a nav-error plan).
- (c) Fixed anchor list per race_format. Closed-set contingency taxonomy per race_format. Most predictable. Misses athlete-specific cases.

**Andy picked (a) — mixed.** Took the architect's recommendation. Rationale: carries the anchor-table precedent from per-phase (deload cadence per mode; Taper-length per race format). Anchor table per race_format: any race → GI / hydration / mechanical-or-gear-failure; outdoor AR + ultra → navigation / sleep-dep / weather; stage races → between-stage recovery; multi-day → cumulative fatigue + crew-pacing-mismatch. LLM expands within each + adds athlete-specific (Andy's wrist re-aggravation; known weak links).

### 2.4 No paired spec amendment this session

Unlike single-session (§3.5 / §4.4 / §10.4 / §13.4 amendments) and T1/T2 (§8.6 / §8.7 amendments), race-week-brief consumes the existing v1 spec contract without surfacing any contract gap. Spec sections §3.4 (call signature), §4.5 (input validation rules), §5.1 (pattern routing), §5.3 (Pattern B algorithm), §5.4 (validator scope), §7.13–§7.14 (RaceWeekBrief + RacePlan schemas), §8.5 (Taper spec-auto coaching flags), §8.6 (`intensity_modulated` LLM-emittable), §9.1 (cache key), §9.3 (midnight-UTC invalidation), §11.1–§11.3 (performance budget) all already cover race-week-brief without modification.

No further stop-and-ask triggers fired during execution.

---

## 3. What landed per file

### 3.1 `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` — new (955 lines)

14 H2 sections + Source-decisions header following the inherited prompt-body convention:

- **Header** — name + entry point + Pattern + caller + status + position in arc (5th of 5 — ARC COMPLETE).
- **Source decisions D1–D13** — full decision table with Andy's three picks (D5 hybrid pacing, D6 mixed contingency, D7 unified file). D1 tool-use (`record_race_week_brief` with three arguments); D2 extended thinking ~5500 (highest in pipeline — broadest reasoning surface); D3 full payloads verbatim (all 5 Layer 2 + 3A + 3B + Taper window + event metadata); D4 full verbatim Taper window; D5/D6/D7 = Andy's three picks; D8 closed 2-flag LLM-emittable + 5 spec-auto Taper flags orchestrator-stamps; D9 hybrid kit_manifest resolution; D10 hybrid RuleFailure retry context; D11 tight per-field length caps matched to max_tokens=6000 budget; D12 direct/no-platitudes coaching voice with explicit forbidden-phrasing list for `mental_prep_cues`; D13 file location per `prompts/` subdir convention.
- **§1 Purpose + scope** — 1.1 what produced (3 coordinated outputs: taper_session_overrides + race_week_brief + race_plan); 1.2 NOT produced (new Taper sessions; phase re-decomposition; race-day FIT/TCX files; post-race recovery; observations beyond `opportunity` exception; goal-viability re-assessment); 1.3 failure modes (taper_phase_intent_violation_blocker; kit_manifest_inputs_incomplete soft; race_plan_segments_unordered_blocker; fueling_strategy_2e_tier_mismatch_blocker; contingency_anchor_category_missing_warning).
- **§2 Pipeline placement** — call site `llm_layer4_race_week_brief`; Pattern B per `Layer4_Spec.md` §5.1 (B for both single-day + multi-day); 6-step algorithm; out-of-pipeline cases (cache hit + midnight-UTC rollover; §4.5 input validation failures pre-LLM raise).
- **§3 Inputs** — 10 sub-sections covering event metadata (3.1), athlete + race-week context (3.2), athlete state — drives Taper modulation (3.3), periodization context — Taper phase intent (3.4), multi-locale equipment views (3.5 — load-bearing for race-week specifically), prior plan Taper window full verbatim (3.6), race-day fueling tier 2E load-bearing (3.7), terrain + environment 2B (3.8), retry context (3.9), intentionally NOT passed (3.10).
- **§4 Output schema + tool definition** — strict JSON-schema `record_race_week_brief` tool with three top-level arguments: `taper_session_overrides` (list of modified PlanSessions; max 42; 2-flag enum on session-level coaching_flags); `race_week_brief` (RaceWeekBrief object — always emitted; per-field maxLength + minItems on `contingencies` + `mental_prep_cues`); `race_plan` (RacePlan object — multi-day events only; segments minItems=2; transitions; pacing_strategy + fueling_strategy + contingencies minItems=4). §4.2 has 15 cross-output schema rules covering single-day vs multi-day branch logic + kit-check date anchor + contingency anchor-category coverage + segment chronological ordering + 2E fueling band enforcement + forbidden-phrasing prompt-rule.
- **§5 System prompt** — direct voice; race-week brief synthesizer role; three-output discipline; coaching-voice section with explicit forbidden phrasings (no "you've got this", "crush it", "trust the process" generic, "race day magic", "mind over matter", emoji); Taper-session modulation guidance per days_to_event bands (≤2, [3,5], ==7, weekly race-rehearsal anchor); race-week-brief synthesis field-by-field guidance; race-plan synthesis multi-day guidance (segments + transitions + pacing_strategy + fueling_strategy + contingencies); iteration discipline; output discipline.
- **§6 User prompt template** — Mustache variables for event metadata, athlete profile, current state (3A), periodization phase (3B Taper context), race-day fueling tier (2E), terrain + environment (2B), multi-locale equipment views (2C), prior plan Taper sessions verbatim table, retry context, task instructions with coverage requirements. Two distinct `{{#multi_day}}…{{/multi_day}}` blocks (one for sleep-dep strategy line; one for race_plan emission instructions + multi-day-specific coverage requirements).
- **§7 Sampling configuration** — Sonnet 4.6, temp 0.2, `max_tokens=6000`, extended thinking budget 5500, forced tool_choice on `record_race_week_brief`.
- **§8 Coaching flag emission rules** — closed-set 2-flag LLM-emittable enum (`intensity_modulated`, `discipline_specific_intensity`) on `taper_session_overrides[]`; 5 spec-auto Taper flags handled orchestrator-side per §8.5 (contract: prompt produces session content; orchestrator stamps); `opportunity` observation LLM-emitted exception via `opportunities[]` field.
- **§9 Coaching guidance** — 6 sub-sections covering Taper-session modulation policy (anchor signals + non-modulators); hybrid pacing depth operational rule; mixed contingency depth anchor table per race_format + athlete-specific expansion + multi-day-only contingencies; kit manifest resolution policy step-by-step; mental_prep_cues evidence-grounded examples + forbidden phrasings; race-day fueling plan derivation from 2E.
- **§10 Edge cases** — 15 rows covering single-day no-rehearsal travel week; weather forecast unpopulated; overtrained state pullback; active illness pullback; missing 2C equipment view; rehearsal session on travel day; days_to_event=1 manual fire; 3B goal_viability=unrealistic; race-rules-mandated gear not in registry; thin Taper window; multi-day with >12 segments; stage race ≤4 stages; double-fire refresh case (days_to_event=14 then 7); discipline not in 2A inclusion; night section with unpopulated sleep-dep strategy.
- **§11 Validator + retry contract** — 12 validator rules with severity (blocker / warning / soft); retry context rendering format per D10; cap-hit behavior.
- **§12 Test scenarios** — 20 PSS-RWB-prefix v1 scenarios covering Andy's Pocket Gopher Extreme baseline + single-day road marathon + single-day trail 50K + multi-day 3-stage race + 24h multi-day ultra + overtrained pullback + active illness + missing 2C + 4 validator retry cases + cap-hit + forecast unavailable + day-before fire + goal_viability=unrealistic + missing mandatory gear + thin Taper + 13-segments cap + 2D wrist contingency + very-sparse-data RPE fallback.
- **§13 Performance budget** — latency p50 ~8s single-day / p50 ~12s multi-day (p95 ~12s / ~18s); input ~4500-6500; extended thinking 5500; output ~1500 single-day / ~5000 multi-day; cost ~$0.08-0.22 typical / ~$0.35 worst-case multi-day with cap-hit retries; cache hit rate ≈ 0% over multi-day windows (midnight-UTC rollover invalidates daily); cumulative ~$2.50 per race-event.
- **§14 Open items + gut check** — 7 open items (brief-diff renderer; per-segment athlete check-in shape; race-week refresh integration with D-64 NL parser; multi-day pacing_milestones validation; kit_manifest free-text aggregation; athlete-stated goal override; forecast-driven kit refinement); gut check (what's right / risks / what's missing / best argument against each pick).

### 3.2 `aidstation-sources/CLAUDE.md` — narrative bump + forward-pointer update

- "Last shipped session" rewritten from T1/T2 to race-week-brief (covers Andy's three picks + 5-of-5 framing + arc COMPLETE).
- T1/T2 demoted to predecessor (preserves the original predecessor chain — T1/T2 → PR19 → PR18 → single-session → per-phase → seam-reviewer → Layer 4 spec v1 → PR17 → PR16 → PR15 → PR14).
- Layer 4 row in the layer-pipeline table — "PROMPT BODIES 4/5" → "PROMPT BODIES 5/5 — ARC COMPLETE".
- "Backlog: `Project_Backlog_v36.md`" → "`Project_Backlog_v37.md`".
- "Layer 4 prompt bodies (4 of 5 shipped; 1 queued — race-week-brief)" → "(5 of 5 shipped — arc COMPLETE)" + filename list adds `Layer4_RaceWeekBrief_v1.md`.
- "Next forward move" list — drops the race-week-brief candidate; reframes with "the Layer 4 prompt-body arc is now COMPLETE; remaining Layer 4 work is the §14 retrospective + implementation track"; expands the implementation track candidate with scope details (call-site code, payload schemas, validator harness, `plan_versions` table, caching layer).

### 3.3 `aidstation-sources/Project_Backlog_v37.md` — new (v36 → v37)

v37 header revision entry: full race-week-brief session narrative (the same content captured in CLAUDE.md last-shipped-narrative, with the source-decision table reference + arc-COMPLETE framing + 4 files total + companion contract sections + token/cost budget + test scenario count). v36 entry moved to predecessor revisions list. Body (line 8+) byte-identical to v36 per Rule #12.

### 3.4 `aidstation-sources/handoffs/V5_Design_Layer4_Prompts_RaceWeekBrief_Closing_Handoff_v1.md` — new (this file)

Session-end bookkeeping per the handoff convention.

---

## 4. Files shipped this session

All on branch `claude/review-design-handoff-CuXt4`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` | New | 955 lines; race-week-brief synthesizer prompt body |
| 2 | `aidstation-sources/CLAUDE.md` | Edit | Last-shipped-narrative bump + Layer 4 row PROMPT BODIES 5/5 ARC COMPLETE + Backlog ref v36 → v37 + prompt-body listing adds RaceWeekBrief + Next-forward-move reframed with arc-complete |
| 3 | `aidstation-sources/Project_Backlog_v37.md` | New (v36 → v37) | v37 header revision entry; v36 entry moved to predecessor list; body byte-identical |
| 4 | `aidstation-sources/handoffs/V5_Design_Layer4_Prompts_RaceWeekBrief_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping |

**5-file ceiling status:** 4 files (well under ceiling). Substantive surface area: 1 prompt body file (955 lines). Bookkeeping is the standard 3-file pattern per prompt-body cadence (CLAUDE.md + backlog v-bump + closing handoff). Smaller file count than prior prompt-body sessions (single-session was 6, T1/T2 was 6) because no spec amendment was needed.

**Not touched this session** (intentional):

- `Layer4_Spec.md` — race-week-brief consumes the existing v1 spec contract without surfacing any contract gap. §3.4 (call signature), §4.5 (input validation), §5.1 (pattern routing), §5.3 (Pattern B algorithm), §5.4 (validator scope), §7.13 (RaceWeekBrief schema), §7.14 (RacePlan schema), §8.5 (Taper spec-auto coaching flags), §8.6 (intensity_modulated LLM-emittable), §9.1 (cache key), §9.3 (midnight-UTC invalidation), §11.1–§11.3 (performance budget) all already cover race-week-brief. **Broke the spec-amendment precedent set by single-session §10.4 + T1/T2 §8.6/§8.7** — this is OK; the precedent was situational, not a convention.
- `OnDemand_Workout_D63_Design_v1.md` — D-63-specific spec; untouched.
- `Plan_Refresh_D64_Design_v1.md` — D-64-specific spec; untouched. Race-week-brief is its own entry point, distinct from D-64 plan-refresh.
- Other prior prompt bodies (`Layer4_SeamReviewer_v1.md`, `Layer4_PerPhase_v1.md`, `Layer4_SingleSession_v1.md`, `Layer4_RefreshT1_v1.md`, `Layer4_RefreshT2_v1.md`) — untouched.
- Layer 3 specs (`Layer3_3A_Spec.md`, `Layer3_3B_Spec.md`) — untouched. Race-week-brief reads 3A + 3B payloads as input; no contract change.

---

## 5. Standing items / open flags

### 5.1 Layer 4 §14 retrospective — still owed (now load-bearing for implementation)

The Layer 4 §14 retrospective is now the next most-load-bearing Layer 4 spec work. With all 5 prompt bodies shipped + Layer 4 spec v1 + 3 amendment rounds (D-63 sport-unavailable in single-session, `intensity_modulated` broadening in T1/T2, no amendment in race-week-brief), the retro has a complete picture to audit.

**Expected scope:** fresh-eyes critical-evaluation pass over `Layer4_Spec.md` §§1–13. The retro should:
- Audit consistency between spec contracts + prompt-body implementations (5 prompt bodies should all clear validator contracts per §5.4; tool-use mechanisms should all match §8 closed-set flag enforcement; caching keys per §9.1 should match per-prompt input sets).
- Check the 3 amendment rounds (sport-unavailable; intensity_modulated broadening) for consistency with downstream sections that may not have been touched (§13 test scenarios, §10 edge cases, §11 performance budget).
- Test scenario consistency: 84 Layer 4 spec scenarios + 15 (PerPhase) + 15 (SingleSession) + 15 (T1) + 18 (T2) + 20 (RaceWeekBrief) = 167 PSS-prefix test scenarios total. Audit for overlap, gaps, contradictions.
- Performance budget per §11.3 for race-week-brief: cumulative $2.50 per race-event for 14 daily regenerations is a new line item; cross-check against the §11.3 cumulative ceilings.
- §14 itself was deferred per `Layer4_Spec.md` §12.6 — lands as the close-out of the Layer 4 spec arc.

**Trigger to advance:** Andy picks it as next-session focus per the §6 forward pointers. Recommended ordering per `Layer4_Spec.md` §12.6: retro before implementation.

### 5.2 Layer 4 implementation track — fully unblocked

All 4 Layer 4 entry points now have prompt bodies ready for implementation:
- `plan_create` (Pattern A — composes `Layer4_PerPhase_v1.md` per-phase calls + `Layer4_SeamReviewer_v1.md` seam reviews).
- `plan_refresh` T1/T2 (Pattern B — `Layer4_RefreshT1_v1.md` / `Layer4_RefreshT2_v1.md`).
- `single_session_synthesize` (Pattern B — `Layer4_SingleSession_v1.md`).
- `race_week_brief` (Pattern B — `Layer4_RaceWeekBrief_v1.md`).

**Implementation scope to plan:**
- `llm_layer4_*` call-site code (4 functions per `Layer4_Spec.md` §3.1–§3.4 signatures).
- Payload schema scaffolding per `Layer4_Spec.md` §7 (Layer4Payload + PlanSession + sub-blocks + PhaseStructure + SeamReview + ShapeOverride + ValidatorResult + Observation + RaceWeekBrief + RacePlan + KitItem + RaceSegment + TransitionSpec + PacingStrategy + FuelingStrategy + Contingency).
- Deterministic-validator harness per §5.4 with per-entry rule sets.
- `plan_versions` table migration per §7.11.
- Caching layer per §9 with per-entry cache key formulas + midnight-UTC invalidation for race-week-brief.
- Cross-call orchestration for Pattern A (per-phase sequential + LLM seam review with β propose-patch authority per Decision 8).

**T3-intra-phase routing decision** is still implementation-time per `Layer4_Spec.md` §5.1 + `Layer4_RefreshT2_v1.md` §14.1: own prompt vs subsume T2 with extended scope vs defer. v1 spec contract allows all three; production telemetry will reveal whether T3-intra-phase is frequent enough to justify its own prompt body.

### 5.3 NL intent parser prompt body — separate D-64-internal track

Per `Plan_Refresh_D64_Design_v1.md` §2 Decision 12 + §10: the NL parser prompt body that produces the `ParsedIntent` schema is **not** part of the 5-prompt Layer 4 arc. It's a D-64-internal prompt called upstream of Layer 4. T1/T2 + race-week-brief consume `parsed_intent` as input (race-week-brief reads `parsed_intent` indirectly when athlete-triggered via D-64 NL refresh during race week per `Layer4_RaceWeekBrief_v1.md` §14.1); the parser itself is its own prompt design.

**Trigger to advance:** D-64 implementation track activates + the parser is needed for runtime NL classification.

### 5.4 Race-week-brief integration with D-64 NL refresh — coordination point

`Layer4_RaceWeekBrief_v1.md` §14.1 flags: when athlete fires a race-week NL refresh ("drop tomorrow's race-rehearsal") via D-64 during race week, the brief's `taper_session_overrides[]` interacts with `plan_refresh` T1/T2's output. Coordination contract: the more-recent fire wins per `Layer4_Spec.md` §7.11 per-day pointer; brief's Taper overrides supersede T1's same-date overrides if brief fires after T1. Confirm during D-64 implementation. Possible spec amendment if telemetry shows coaching-narrative inconsistencies emerging from this seam.

### 5.5 Spec-auto Taper flag stamping timing — implementation-side verification

`Layer4_RaceWeekBrief_v1.md` §14.2 risk: if the orchestrator stamps `race_rehearsal` on a session that the brief intended NOT to be a rehearsal (because the brief shifted the rehearsal to a different day), there's a mismatch. The contract assumes orchestrator stamping is deterministic per `Layer4_Spec.md` §8.5; needs implementation verification when the call-site code lands.

### 5.6 Brief-diff renderer for incremental re-fires — defer to brief UI build

`Layer4_RaceWeekBrief_v1.md` §14.1 open item: currently each daily brief regeneration is from-scratch (midnight-UTC cache invalidation forces this); an incremental "what's changed since yesterday's brief" surface would reduce athlete cognitive load. Defer until brief UI is built + telemetry shows daily-regen burden.

### 5.7 Carry-forward from prior sessions

- **PR18 §5.0 — 12 walks owed.** Unchanged; pending Vercel deploy + walk.
- **PR19 §5.0 — 11 walks owed.** Unchanged; pending Vercel deploy + walk.
- **PR11 step 6 — re-walkable + flippable ✅ once PR18 deploys** (unblocked by PR18 item B's `/retrieve` refresh).
- **Park-specific tag taxonomy follow-up** (PR18 §5.2 → carried in PR19 + T1/T2 handoffs) — still deferred. Trigger: Andy starts using park locales for real sessions.
- **Trip-locale taxonomy decoupling** (PR19 handoff §5.2) — still deferred. Defer-trigger: Andy wants to save specific travel destinations as locales for trip-row picking.
- **v1 coaching form replacement** (PR19 handoff §5.3) — still scheduled for v2 LLM-pipeline cutover. PR19's form-level guard + athlete-locale-aware dropdown work will be thrown away when v2 ships.
- **T1/T2 open items §5.4 / §5.5** (validator coordination for sickness-signal demotion; `overreach_test` with athlete pullback potential §8.3 amendment) — still deferred; lands when validator implementation surfaces.

---

## 6. Forward pointers

**Next session:** Andy's choice. With the Layer 4 prompt-body arc COMPLETE, the remaining Layer 4 work is the §14 retrospective + implementation track. Candidates:

- **Layer 4 §14 retrospective** — fresh-eyes critical-evaluation pass over `Layer4_Spec.md` §§1–13 (including all 3 amendment rounds — D-63-sport-unavailable in single-session, intensity_modulated broadening in T1/T2, no amendment in race-week-brief). All 5 prompt bodies are stable v1 input to the retro; the retro can audit consistency between spec contracts + prompt-body implementations. Lands before Layer 4 implementation per §12.6 deferral. Spec work, not code.
- **Layer 4 implementation track** — fully unblocked by the now-complete prompt-body arc. All 4 entry points have prompt bodies ready; T3-intra-phase routing decision is still implementation-time. Implementation scope per §5.2 above (call-site code + payload schemas + validator harness + `plan_versions` table + caching layer). Substantial code work; per-PR cadence in effect.
- **v5 onboarding implementation PR** — substantial code work per `Plan_Refresh_D64_Design_v1.md` §7 storage + `Athlete_Onboarding_Data_Spec_v5.md` §J locale-system carry-forwards.
- **D-50 wiring resumption** — COROS OAuth + webhook recording (now unblocked by D-58).
- **PR18 follow-on — park-specific tag taxonomy** — defer-trigger as flagged in §5.7.
- **Layer 4.5 — Joint Session Coordinator spec** — separate file; post-pass over linked athletes' Layer 4 payloads. Lands when team-features track activates.
- **Layer 5 spec** — parallel supplemental outputs (nutrition, supplements, 7-day clothing/conditions). Consumes `PlanSession.session_notes` + `cardio_blocks` + race-week brief contents per §12.3 forward-pointer.

**Before the next session:**

1. **Read `aidstation-sources/CLAUDE.md` fully** (Rule #13). Last-shipped narrative now leads with the race-week-brief session; Backlog ref now points at v37; Layer 4 row reads "PROMPT BODIES 5/5 — ARC COMPLETE".
2. Read this handoff in full.
3. (Optional) Re-read predecessor closing handoffs that build on this session's work: `V5_Design_Layer4_Prompts_RefreshT1T2_Closing_Handoff_v1.md` (immediate predecessor — Andy's T1/T2 picks established the file-scope-pick precedent that race-week-brief reversed); `V5_Design_Layer4_Prompts_SingleSession_Closing_Handoff_v1.md` (single-session is the unified-prompt precedent that race-week-brief carried).
4. (If picking Layer 4 §14 retro) Read `Layer4_Spec.md` in full + all 5 prompt body files in `aidstation-sources/prompts/` (~3500 lines of inputs total).
5. (If picking Layer 4 implementation track) Read `Layer4_Spec.md` §3 (call signatures) + §5 (algorithm) + §7 (payload schema) + §9 (caching) + §11 (performance budget) carefully — the implementation contracts. Read all 5 prompt body files for the LLM-side specifications.

**Rules in force, unchanged:**

- #9 session-start verification — applied (see §1 above); branch state confirmed clean off main; T1/T2 ship verified.
- #10 session-end verification — applied (see §7 below).
- #11 mechanically-applicable deferred edits — Layer 4 §14 retro scope captured in §5.1 above with mechanical scope outline.
- #12 numeric version suffixes — Backlog now at v37; next state-changing event bumps v37 → v38.
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §6 first-action explicitly names CLAUDE.md.

---

## 7. Session-end verification (Rule #10)

Final pass over each claimed file edit before composing this handoff:

| Check | Result |
|---|---|
| `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` exists | ✅ `ls` returns file |
| `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` is 955 lines | ✅ `wc -l` |
| `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` has 14 numbered H2 sections + Source-decisions header | ✅ `grep "^## "` (15 total H2 = 14 numbered + 1 decisions header, matching single-session + T1/T2 convention) |
| `Layer4_RaceWeekBrief_v1.md` decision table covers D1–D13 | ✅ inline read |
| `Layer4_RaceWeekBrief_v1.md` §4.1 tool schema is strict JSON schema with `additionalProperties: false` at every nesting level | ✅ inline read |
| `Layer4_RaceWeekBrief_v1.md` §4.1 has three top-level arguments: `taper_session_overrides`, `race_week_brief`, `race_plan` | ✅ inline read |
| `Layer4_RaceWeekBrief_v1.md` §8.1 has 2-flag LLM-emittable enum | ✅ inline read |
| `Layer4_RaceWeekBrief_v1.md` §8.2 references the 5 spec-auto Taper flags handled orchestrator-side per §8.5 | ✅ inline read |
| `Layer4_RaceWeekBrief_v1.md` §9.5 has explicit forbidden-phrasing list for mental_prep_cues | ✅ inline read |
| `Layer4_RaceWeekBrief_v1.md` §12 has 20 PSS-RWB-prefix test scenarios | ✅ inline count |
| `Layer4_RaceWeekBrief_v1.md` §11.1 has 12 validator rules | ✅ inline count |
| `CLAUDE.md` last-shipped-narrative leads with race-week-brief session | ✅ |
| `CLAUDE.md` Layer 4 row reads "PROMPT BODIES 5/5 (seam-reviewer + per-phase synth + single-session synth + per-tier T1/T2 refresh synth + race-week-brief synth) — **ARC COMPLETE**" | ✅ |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v37.md` | ✅ |
| `CLAUDE.md` Layer 4 prompt-bodies bullet lists 5 shipped — arc COMPLETE + adds Layer4_RaceWeekBrief_v1.md filename | ✅ |
| `CLAUDE.md` Next-forward-move reframed: race-week-brief candidate dropped; arc-complete framing | ✅ |
| `Project_Backlog_v37.md` exists | ✅ |
| `Project_Backlog_v37.md` line 5 starts with `**File revision:** v37 — 2026-05-17 (**Layer 4 race-week-brief synthesizer prompt body shipped` | ✅ |
| `Project_Backlog_v37.md` has single `**Predecessor revisions:**` header at line 6 (not duplicated) | ✅ `grep -c` returns 1 |
| `Project_Backlog_v37.md` line 7 starts with `- v36 — 2026-05-17 (**Layer 4 per-tier T1/T2` | ✅ |
| `Project_Backlog_v37.md` line 8 starts with `- v35 — 2026-05-16 (**PR19 — retire legacy `LOCALES`` | ✅ |
| 1 prompt body file + 3 bookkeeping = 4 files this session | ✅ |

---

## 8. Carry-forward from PR18 + PR19 + Layer 4 arc (informational)

- **PR18 §5.0** — 12 testable steps owed; pending Vercel deploy + walk.
- **PR19 §5.0** — 11 testable steps owed; pending Vercel deploy + walk.
- **PR11 step 6** — re-walkable + flippable to ✅ once PR18 deploys (unblocked by PR18 item B).
- **Layer 4 prompt-body arc** — 5 of 5 shipped (seam-reviewer + per-phase + single-session + per-tier T1/T2 + race-week-brief). **ARC COMPLETE.** Per-prompt cadence retired; the next prompt body would be a v2 surface (e.g., post-race recovery, brief-diff renderer) and is not currently on the roadmap.
- **Layer 4 §14 retrospective** — still owed; covers all 3 amendment rounds (D-63 sport-unavailable in single-session, `intensity_modulated` broadening in T1/T2, no amendment in race-week-brief) + all 5 prompt bodies.
- **Layer 4 implementation track** — fully unblocked; all 4 entry points have prompt bodies ready. Recommended sequencing per `Layer4_Spec.md` §12.6: §14 retro before implementation.
- **Park-tags follow-up** — still deferred per PR18 §5.2.

---

**End of handoff.** Race-week-brief synthesizer prompt body shipped — `Layer4_RaceWeekBrief_v1.md` (955 lines) — 5 of 5 in the Layer 4 prompt-body arc. **The Layer 4 prompt-body arc is now COMPLETE.** Andy's three architectural picks: (a) unified file with multi-day branch, (a) hybrid pacing depth, (a) mixed contingency depth (took all three architect recommendations). No spec amendments this session — race-week-brief consumes the v1 spec contract without surfacing any gap. 4 files this session (under the 5-file ceiling). All 4 Layer 4 entry points now have prompt bodies ready for implementation. Next forward move: Layer 4 §14 retrospective (recommended next per §12.6 deferral) OR Layer 4 implementation track (fully unblocked).
