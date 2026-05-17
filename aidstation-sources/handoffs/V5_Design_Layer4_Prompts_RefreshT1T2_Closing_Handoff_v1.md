# V5 Design Layer 4 — Per-Tier T1/T2 Refresh Synthesizer Prompt Bodies Closing Handoff

**Session:** Ships the per-tier T1/T2 plan-refresh synthesizer prompt bodies (fourth + fourth-and-a-half of 5 in the Layer 4 prompt-body arc per the predecessor single-session handoff §6 forward pointers). Two separate files per Andy's Pick 1 (option (b) — rejected the architect's recommendation of a unified file). Coupled `Layer4_Spec.md` §8.6 + §8.7 amendment broadening the `intensity_modulated` flag trigger from D-63-only to also cover `plan_refresh` paths (paired amendment precedent set by the single-session session's §3.5/§4.4/§10.4/§13.4 sport-unavailable amendments).
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_PR19_LOCALES_Retire_Closing_Handoff_v1.md` (PR19 shipped + merged on the main branch; this session opened against the §6 forward pointers — Andy picked per-tier T1/T2 prompt body).
**Branch:** `claude/retire-closing-handoff-locales-4rmiD`.
**Status:** 🟢 2 substantive prompt body files shipped (`Layer4_RefreshT1_v1.md` ~700 lines + `Layer4_RefreshT2_v1.md` ~750 lines), 1 substantive spec amendment (`Layer4_Spec.md` §8.6 + §8.7 broadening), 3 bookkeeping (CLAUDE.md, Project_Backlog v35 → v36, this handoff). 6 files total — 1 over the 5-file ceiling, precedented by the single-session session (also 6 files via paired spec amendment).

---

## 1. Session-start verification (Rule #9)

Predecessor PR19 handoff §6 forward pointer claimed: PR19 shipped via PR #64 (merged `84c11c8` on main); branch `claude/retire-closing-handoff-locales-4rmiD` sits at the same commit as main; PR19's 11 §5.0 walks still owed (Andy-driven post-deploy task); next session candidates include the four remaining-arc items (Layer 4 §14 retro, per-tier T1/T2, race-week-brief, implementation track).

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `routes/coaching.py` has no `LOCALES` references (PR19 ship) | `grep -n "LOCALES" routes/coaching.py` | ✅ (empty) |
| `routes/coaching.py` has `TRIP_LOCALE_TYPES = ('home', 'hotel', 'partner', 'airport')` | inline read | ✅ line 27 |
| `routes/locales.py:15` has internal `LOCALES = ['home','hotel','partner','airport']` literal | inline read | ✅ |
| `routes/locales.py` has `CATEGORY_TO_WHERE_AVAILABLE_BUCKET` + `athlete_locale_choices(db, uid)` | inline read | ✅ lines 63, 77 |
| `routes/references.py` imports `athlete_locale_choices`, no `LOCALES` | inline read | ✅ lines 5, 30 |
| Backlog at v35 | `ls Project_Backlog_v*.md \| sort -V \| tail` | ✅ |
| Latest handoff is PR19 | `ls handoffs/V5_Implementation_PR* \| sort -V \| tail` | ✅ |
| Branch clean off main tip `84c11c8` | `git status` + `git log` | ✅ |

No drift. Andy picked **per-tier T1/T2 prompt body (D-64; Pattern B refresh)** via `AskUserQuestion` at session start (rejected Layer 4 §14 retro / race-week-brief / Layer 4 implementation as next-track candidates).

---

## 2. Session narrative — three architectural picks

After session-start verification + reading the relevant input files (`Plan_Refresh_D64_Design_v1.md` §§2–6 for tier definitions / cascade / NL intent contract, `Layer4_Spec.md` §§3.2 / 4.3 / 5.1 / 5.3 / 5.4 for refresh entry point + Pattern B + validator, `Layer4_SingleSession_v1.md` for inherited conventions, `Layer4_Spec.md` §§8.2–8.7 for coaching flag taxonomy), the architect (Claude) presented three load-bearing architectural picks to Andy via `AskUserQuestion`:

### 2.1 Pick 1 — File scope

Options presented:
- (a) **Unified `Layer4_Refresh_v1.md`** covering T1 + T2 with Mustache branches at payload-injection + scope-length slots (recommended by architect — smallest surface area capturing shared coaching logic; ~700–900 lines).
- (b) Two files (`Layer4_RefreshT1_v1.md` + `Layer4_RefreshT2_v1.md`) — separate prompts per tier; two design passes; T1 + T2 drift independently as they tune.
- (c) T1 only this session; T2 next session (smaller per-session scope; consistent with one-prompt-per-session cadence).
- (d) Unified file covering T1 + T2 + T3-intra-phase (all three Pattern-B refresh paths).

**Andy picked (b) — two files.** Rationale per Andy's pick description: "Separate prompt files per tier; two design passes; T1+T2 drift independently as they tune." Rejected the architect's unified-file recommendation. The two-file approach allows T2's longer scope to have distinct §9 guidance (weekly volume band + intensity distribution as load-bearing validator constraints; LSD anchor as the weekly cornerstone decision; deload + overreach week handling) that doesn't fit cleanly under conditional logic with T1's short-horizon scope.

T3-intra-phase deferred: Pattern B's "long-window prompt" per `Layer4_Spec.md` §5.1 is queued as a follow-up decision — could subsume T2 with extended scope, or could be its own prompt body. Defer to implementation time per `Layer4_RefreshT2_v1.md` §14.1 open item.

### 2.2 Pick 2 — NL `parsed_intent` weighting policy

Options presented:
- (a) **Verbatim-respect-unless-safety-blocker + must-explain when modulating** (recommended by architect — carries the single-session D10 pattern; honor athlete-stated intent; 3A overrides only on hard-safety).
- (b) Coaching judgment with anchor signals — synthesizer weighs 3A + parsed_intent equally; coaching reasoning picks the modulation.
- (c) Strong-bias — when parsed_intent is non-None, it dominates 3A.

**Andy picked (c) — strong-bias toward intent.** Rationale: athlete-explicit framing of D-64 (`Plan_Refresh_D64_Design_v1.md` §2 Decision 2 — athlete owns the decision to refresh, including the direction) supports the athlete's NL signals dominating 3A objective signals on prescription direction. 3A grounds the magnitude (e.g., ACWR pulls back to keep weekly volume inside the blocker band even when athlete says "push") but never overrides direction. Hard-safety constraints (active injuries, equipment availability, schedule) are still never overridden.

This is a meaningful philosophical pick distinct from the single-session prompt — single-session uses "coaching judgment with anchors" (D6) where the synthesizer modulates intensity per coaching reasoning. T1/T2 explicitly subordinate that reasoning to the athlete's stated direction, reserving coaching judgment for magnitude calibration.

### 2.3 Pick 3 — Continuity-with-adjacent-sessions policy

Options presented:
- (a) **Match surrounding training shape unless refresh trigger justifies a shift** (recommended by architect — minimally disruptive default; only shift when 3A or parsed_intent gives explicit signal).
- (b) Treat the refresh window as a clean slate — only honor 3B phase intent; adjacent sessions are context, not constraint.
- (c) Tier-conditional — T1 strict (2 days can't shift periodization); T2 looser (7 days may shift weekly structure).

**Andy picked (a) — match surrounding shape unless triggered.** The recommended option. Rationale: refresh-window-after sessions are the load-bearing continuity constraint; the synthesizer's job is to land its output cleanly into them. Reshaping is allowed when refresh trigger justifies (sickness week, overreach pullback, travel adjustment) but the default is minimal disruption.

### 2.4 Paired spec amendment decision

After picks 2 + 3 landed, the architect flagged the need for a paired `Layer4_Spec.md` §8.6 + §8.7 amendment: `intensity_modulated` flag is currently D-63-scoped, but strong-bias-toward-intent (Pick 2) means the refresh synthesizer needs to emit this flag whenever modulating against the natural periodization-shape + continuity reading due to intent or 3A signal. Without the broadening, the refresh would have no audit-trail mechanism for "the system did something different than periodization called for, here's why" — which is precisely the kind of behavior `intensity_modulated` was designed to flag.

The architect proposed the amendment as a paired in-session edit (precedent: single-session session's §3.5/§4.4/§10.4/§13.4 amendments) rather than spinning a separate spec amendment session. No additional ask of Andy — the amendment is a small surgical edit consistent with the precedent.

No further stop-and-ask triggers fired during execution.

---

## 3. What landed per file

### 3.1 `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` — new (~700 lines)

14 H2 sections following the inherited prompt-body convention:

- **Header** — name + entry point + Pattern B + caller + status + position in arc (4th of 5).
- **Source decisions D1–D11** — full decision table with Andy's three picks (D5 strong-bias, D7 match-surrounding, file-scope-Pick-1 informs the two-file split itself but isn't a D-row of its own); D2 extended thinking budget ~3000 (sits between single-session's 3500 and per-phase's 5000 — T1 has fewer combinatorics than per-phase but more continuity-checking than single-session); D6 full per-phase + cross-phase LLM-emittable coaching-flag set (7 flags); D9 schema-enforced length caps (240/200/120/240 chars matching single-session).
- **§1 Purpose + scope** — 1.1 what produced (0–4 PlanSession records covering 2-day refresh window); 1.2 NOT produced (phase decomposition; periodization re-shape; sessions outside refresh window; multi-week commitment; NL intent re-classification; observations beyond `opportunity` exception); 1.3 failure modes caught by validator + retry.
- **§2 Pipeline placement** — call site `llm_layer4_plan_refresh(tier='T1', ...)`; Pattern B per `Layer4_Spec.md` §5.3 step 1 sub-bullet (T1); 6-step algorithm; out-of-pipeline cases (cascade pre-LLM failure; validator pre-LLM failure; `parser_confidence='low'` degraded path).
- **§3 Inputs** — 8 sub-sections covering refresh request (3.1), NL context + parsed_intent (3.2), athlete + locale context (3.3), athlete state — drives modulation (3.4), periodization shape inherited from adjacent-session metadata (3.5 — T1 doesn't re-run 3B), prior plan session window (3.6 — ±7d split into refresh-window-prior summary + refresh-window-during-prior verbatim + refresh-window-after verbatim), retry context (3.7), intentionally NOT passed (3.8).
- **§4 Output schema + tool definition** — strict JSON-schema `record_refresh_sessions` tool with `sessions: list[PlanSession]` (0..4 entries; max 4 per T1 scope); 7-flag closed enum on `coaching_flags`; `notable_observations` restricted to `opportunity`. §4.2 output invariants (per-date max 2; no strength+strength; no two hard; at least one cardio; etc.); `intensity_modulated` mandatory-when-applicable rule.
- **§5 System prompt** — direct voice; 5-point job statement; process walkthrough; tool-call-only output constraint.
- **§6 User prompt template** — Mustache variables for refresh request, athlete's words + parsed_intent, athlete profile, inherited periodization phase, locale + equipment per day, athlete state, recent training, sessions being replaced, sessions planned for days 3-9, retry context. Explicit POLICY block stating the strong-bias-toward-intent rule.
- **§7 Sampling configuration** — Sonnet 4.6, temp 0.4, `max_tokens=2000`, extended thinking budget 3000, forced tool_choice.
- **§8 Coaching flag emission rules** — closed-set 7-flag enum with triggers per `Layer4_Spec.md` §§8.2–8.6; spec-auto flag list (orchestrator-side); `intensity_modulated` mandatory-when-applicable.
- **§9 Coaching guidance** — 6 sub-sections covering strong-bias-toward-intent operational meaning (anchor table mapping athlete-says + 3A → prescription); sickness as hard constraint; continuity hand-off; volume band + intensity distribution as soft constraints on T1; exercise + cardio block selection (Tier 1/2/3 per locale); don't-over-explain.
- **§10 Edge cases** — 11 rows covering raw_text-contradicts-parsed_intent; parser_confidence-low cases; race-rehearsal-imminent Taper modulation; mid-refresh locale change; intent-references-non-existent-locale; empty refresh-window-after (end-of-plan); missing phase metadata fallback; multiple sessions same date; today's-session-already-complete.
- **§11 Validator + retry contract** — full §5.4 rule set applies; T1-specific continuity cross-validation (rest_spacing extends across refresh / refresh-window-after boundary; acwr_* projects forward through refresh-window-after for chronic-load denominator); retry context rendering with `suggested_constraint`; cap=2.
- **§12 Test scenarios** — 15 PSS-T1-prefix v1 scenarios covering: empty NL baseline; tired/wiped fatigue; high motivation + elevated ACWR cap; injury parser-caught vs missed; sick (rest-shape); long-ride continuity protection; travel locale shift; validator retry passes + cap-hit; ambiguous parser_confidence-low text; race-rehearsal-imminent Taper; end-of-plan empty refresh-window-after; missing phase metadata.
- **§13 Performance budget** — latency p50 ~5s / p95 ~9s; input ~4500 typical / ~6500 worst; extended thinking ~3000; output ~1500; cost ~$0.05 typical / ~$0.10 worst-case; cache key with normalized NL hash + 3A pulse.
- **§14 Open items + gut check** — `intensity_modulated` trigger broadening (the paired amendment this session); `intended_intensity_distribution` athlete-specific inheritance gap; NL parser failure cascade; empty-sessions output validation; gut check (what's right / risks / what's missing / best argument against).

### 3.2 `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` — new (~750 lines)

Same 14-section structure as T1 with T2-specific calibrations. Key differences from T1 documented inline in the source-decision table (D2 thinking ~4500 vs 3000; D3 adds 3B + optional 2B/2C/2E; D9 max_tokens 4000 vs 2000) and in the §9 guidance sections (weekly volume band + intensity distribution as load-bearing validator constraints; LSD anchor as load-bearing weekly decision in Base/Build; deload week recognition via 3B's `deload_cadence_anchor`; overreach week handling with athlete-pullback path; cross-phase week handling via per-day phase mapping + weighted-blend distribution targets).

T2-specific edge cases (§10) add: cross-phase week (refresh spans phase boundary); deload-cadence-alignment; overreach-week-with-athlete-pullback; 3B-flipped-periodization-mode; data_density='very_sparse' conservative prescription.

T2 test scenarios (§12) add: PSS-T2-09 cross-phase week; PSS-T2-10 volume_band_blocker retry; PSS-T2-11 intensity_dist_blocker retry; PSS-T2-12 cap-hit; PSS-T2-15 periodization mode shift; PSS-T2-17 very-sparse data density. 18 PSS-T2-prefix scenarios total.

T2 §14.1 open items add: cross-phase weighted-blend distribution targets need telemetry validation; weekly-volume validator under sickness signal (validator may fire warnings the orchestrator needs to demote; coordination point for implementation); `overreach_test` flag interaction with athlete pullback (may need §8.3 spec amendment to formalize "overreach can be skipped by intent").

### 3.3 `aidstation-sources/Layer4_Spec.md` — surgical amendment to §8.6 + §8.7

**§8.6 row 2 — `intensity_modulated` trigger broadened:**

Before:
> Synthesizer modulated athlete's picked D-63 intensity per §6.2 of D-63 | The synthesized single session | `intensity_modulated` | LLM-emitted

After:
> Synthesizer modulated session intensity from what natural periodization-shape + adjacent-session continuity would call for, due to athlete signal — covers (a) D-63 single-session modulation per §6.2 of D-63, AND (b) `plan_refresh` T1/T2 modulation against `parsed_intent` direction or 3A signals per `Layer4_RefreshT1_v1.md` §8 / `Layer4_RefreshT2_v1.md` §8 | The synthesized session(s); on a whole-week modulation (e.g., T2 pulled back due to sickness), every session in the refresh window | `intensity_modulated` | LLM-emitted (trigger broadened 2026-05-17 from D-63-only to also cover plan_refresh paths — paired amendment with `Layer4_RefreshT1_v1.md` / `Layer4_RefreshT2_v1.md`)

**§8.7 `intensity_modulated` observation row** — trigger column updated to reference the broadened §8.6 (was "Synthesizer emitted the `intensity_modulated` session flag per §8.6 (D-63 path)"; now "Synthesizer emitted the `intensity_modulated` session flag per §8.6 — covers D-63 single-session path AND `plan_refresh` T1/T2 paths per the broadened §8.6 trigger (2026-05-17 amendment)").

Spec sections NOT touched this session: §3.2 (call signature already supports T1/T2/T3 via `tier` parameter); §4.3 (input validation rules already cover refresh tiers); §5.1 (pattern routing already covers T1/T2 → B); §5.3 (Pattern B algorithm already covers refresh paths); §5.4 (validator rule set already applies to refresh output); §5.5 (capped retry already covers Pattern B); §7.2–7.5 (PlanSession + sub-blocks already discrim-union'd); §7.12 (schema rule "phase_metadata=None on Pattern B refresh" already present).

### 3.4 `aidstation-sources/CLAUDE.md` — narrative bump + forward-pointer update

- "Current state (as of 2026-05-16)" → "2026-05-17".
- Last-shipped-narrative rewritten from PR19 to the per-tier T1/T2 prompt-body session (covers Andy's three picks + the paired §8.6/§8.7 amendment + 4 of 5 prompt bodies + 1 remaining).
- PR19 demoted to predecessor.
- Layer 4 row in the layer-pipeline table — "PROMPT BODIES 3/5" → "4/5"; spec status notes both amendments (D-63 sport-unavailable + intensity_modulated broadening).
- "Backlog: `Project_Backlog_v35.md`" → "`Project_Backlog_v36.md`".
- "Layer 4 prompt bodies (3 of 5 shipped; 2 queued)" → "4 of 5 shipped; 1 queued — race-week-brief" + filename list adds `Layer4_RefreshT1_v1.md` + `Layer4_RefreshT2_v1.md`.
- Next-forward-move list — bullet 2 ("Layer 4 prompt-body design sessions (2 remaining)") narrows to "1 remaining — race-week-brief"; bullet 3 (Layer 4 implementation track) notes that D-64 T1/T2 LLM-call layer can now be implemented.

### 3.5 `aidstation-sources/Project_Backlog_v36.md` — new (v35 → v36)

v36 header revision entry: full T1/T2 session narrative (the same content captured in CLAUDE.md last-shipped-narrative, with the source-decision table reference + paired spec amendment detail + companion contract sections + token/cost budget + test scenario count + 6-file-ceiling status). v35 entry moved to predecessor revisions list. Body (line 32+) byte-identical to v35 per Rule #12.

### 3.6 `aidstation-sources/handoffs/V5_Design_Layer4_Prompts_RefreshT1T2_Closing_Handoff_v1.md` — new (this file)

Session-end bookkeeping per the handoff convention.

---

## 4. Files shipped this session

All on branch `claude/retire-closing-handoff-locales-4rmiD`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` | New | ~700 lines; T1 refresh synthesizer prompt body |
| 2 | `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` | New | ~750 lines; T2 refresh synthesizer prompt body |
| 3 | `aidstation-sources/Layer4_Spec.md` | Edit (2 surgical broadens) | §8.6 `intensity_modulated` trigger row broadened from D-63-only to also cover `plan_refresh` paths; §8.7 spec-auto observation row updated to reference the broadened §8.6 |
| 4 | `aidstation-sources/CLAUDE.md` | Edit | Narrative bump + Layer 4 row status + Backlog ref v35 → v36 + prompt-body listing 4/5 + Next-forward-move 1-remaining |
| 5 | `aidstation-sources/Project_Backlog_v36.md` | New (v35 → v36) | v36 header revision entry; v35 entry moved to predecessor list; body byte-identical |
| 6 | `aidstation-sources/handoffs/V5_Design_Layer4_Prompts_RefreshT1T2_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping |

**5-file ceiling status:** 6 files (1 over ceiling). Precedented by single-session session (also 6 files via paired spec amendment). Substantive surface area: 2 prompt body files (~1450 lines combined) + 1 small spec amendment (~2 rows). Bookkeeping is the standard 3-file pattern per prompt-body cadence (CLAUDE.md + backlog v-bump + closing handoff). Justified because shipping T1 alone this session + T2 next would have doubled the bookkeeping cost (2 × CLAUDE.md bump + 2 × backlog v-bump + 2 × closing handoff = 6 bookkeeping files vs 3 this session) — net file count is lower with both this session.

**Not touched this session** (intentional):

- `Layer4_Spec.md` §3.2 (refresh call signature) — already supports T1/T2 via `tier` parameter; no contract change.
- `Layer4_Spec.md` §4.3 (refresh input validation) — already covers tier_invalid + refresh_scope_* + tier_scope_mismatch + plan_version_id_parent_missing.
- `Layer4_Spec.md` §5.1 (pattern routing) — already routes T1/T2 to Pattern B.
- `Layer4_Spec.md` §5.3 step 1 sub-bullets — already lists T1 / T2 / T3 intra-phase / single-session / race-week-brief context-build conventions.
- `Layer4_Spec.md` §5.4 (deterministic validator rule set) — full rule set already applies to refresh output.
- `Layer4_Spec.md` §7.2–7.5 (PlanSession + sub-blocks) — already supports refresh paths (phase_metadata nullable per §7.12 schema rule).
- `Layer4_Spec.md` §8.2–8.5 (per-phase coaching flag tables) — unchanged; LLM-emitted vs spec-auto split already correct.
- `Plan_Refresh_D64_Design_v1.md` — design doc untouched; T1/T2 prompt bodies consume the contract per §3 tier definitions + §5 ParsedIntent shape. The NL intent parser prompt body remains separately queued per `Plan_Refresh_D64_Design_v1.md` §2 Decision 12 (stop-and-ask trigger #2 deferred to its own session; not part of the 5-prompt Layer 4 arc — it's a D-64-internal parser prompt).
- `Layer3_3A_Spec.md` + `Layer3_3B_Spec.md` — Layer 3 specs untouched. T1/T2 prompts read 3A + 3B payloads as input; no contract change.

---

## 5. Standing items / open flags

### 5.1 Race-week-brief prompt body (1 of 5 remaining)

The arc's final prompt body. Per `Layer4_Spec.md` §3.4: event-mode-only entry point, fires when `days_to_event ≤ 14`, Pattern B with longer `max_tokens` (6000 default) for `RaceWeekBrief` + (multi-day events only) `RacePlan` schemas. Inherits the conventions from the 4 prior prompt bodies.

**Expected scope:** ~700–900 lines following the 14-section structure. Source decisions D1–D~12 covering: tool-use mechanism (likely `record_race_week_brief` with `taper_session_overrides` + `race_week_brief` + optional `race_plan` arguments); extended thinking budget (~5000+ — race-week reasoning is the most context-heavy); input format (all 5 Layer 2 payloads + 3A + 3B + Taper-phase prior sessions + event metadata); RaceWeekBrief field-level prescription guidance; multi-day RacePlan segment + transition + fueling + contingency guidance; Taper-phase coaching-flag spec-auto integration (race_rehearsal / fueling_practice / kit_check / pacing_lock / pre_race_taper per §8.5 are orchestrator-side; the prompt prescribes the underlying session content); kit_manifest free-text vs equipment-registry resolution policy.

**Trigger to advance:** Andy picks it as next-session focus per the §6 forward pointers.

### 5.2 T3-intra-phase prompt body — undecided shape

Per `Layer4_Spec.md` §5.1 routing table: T3 intra-phase routes to Pattern B with "a long-window prompt." This could be:
- (a) Its own prompt body file (`Layer4_RefreshT3IntraPhase_v1.md`), making 6 total prompt bodies in the arc.
- (b) Subsumed by `Layer4_RefreshT2_v1.md` with `scope_length` parameter extension (T2 + T3-intra-phase share the same algorithm, only scope differs).
- (c) Deferred — most T3 refreshes span phase boundaries (Pattern A); T3-intra-phase is an edge case that could route to T2 with a wider scope cap as a v1 stopgap.

Listed in `Layer4_RefreshT2_v1.md` §14.1 + CLAUDE.md Next-forward-move bullet 3 as an implementation-time decision. v1 spec contract allows all three; production telemetry will reveal whether T3-intra-phase is frequent enough to justify its own prompt body.

### 5.3 NL intent parser prompt body — separate D-64-internal track

Per `Plan_Refresh_D64_Design_v1.md` §2 Decision 12 + §10: "Prompt body design deferred to its own spec session" — the NL parser prompt body that produces the `ParsedIntent` schema is **not** part of the 5-prompt Layer 4 arc. It's a D-64-internal prompt called upstream of Layer 4. T1/T2 + race-week-brief consume `parsed_intent` as input; the parser itself is its own prompt design.

**Trigger to advance:** D-64 implementation track activates + the parser is needed for runtime NL classification. The contract (`IntentParserInput` + `ParsedIntent` shapes) is already defined in `Plan_Refresh_D64_Design_v1.md` §5; the prompt body design lands when implementation needs it.

### 5.4 Validator coordination — sickness-signal demotion + `volume_band` warning behavior

`Layer4_RefreshT2_v1.md` §14.1 flags: when `parsed_intent.sickness_signal == 'active'`, the synthesizer prescribes <30% normal volume (rest-shape week). The `volume_band_*` validator rule will fire warnings/blockers because the weekly volume is far below band. The expected behavior is that orchestrator demotes the warning to observation given the sickness signal — but this coordination logic isn't yet spec'd. Lands as a validator-implementation followup (likely in `Layer4_Spec.md` §5.4 or a new §5.6 "input-signal-aware validator severity" section).

Same applies to T1's smaller surface but is less likely to fire (2-day window's contribution to weekly volume is small).

### 5.5 `overreach_test` flag with athlete pullback — potential §8.3 amendment

`Layer4_RefreshT2_v1.md` §14.1 flags: when the inherited periodization cadence indicates the refresh week IS the overreach week, but the athlete's `fatigue_signal` triggers pullback (PSS-T2-08 scenario), the synthesizer pulls back the overreach + does NOT emit `overreach_test`. Current `Layer4_Spec.md` §8.3 wording assumes overreach is synthesizer-prescribed + athlete-honored; it doesn't explicitly allow "athlete can opt out of overreach via intent signal."

Defer to telemetry. v1 T2 prompt handles the case correctly via `intensity_modulated` + `opportunity` observation; if Andy wants the §8.3 trigger formalized (similar to this session's §8.6 broadening), it's a small surgical amendment.

### 5.6 Carry-forward from prior sessions

- **PR18 §5.0 — 12 walks owed.** Unchanged; pending Vercel deploy + walk.
- **PR19 §5.0 — 11 walks owed.** Unchanged; pending Vercel deploy + walk.
- **PR11 step 6 — re-walkable + flippable ✅ once PR18 deploys** (unblocked by PR18 item B's `/retrieve` refresh).
- **Park-specific tag taxonomy follow-up** (PR18 §5.2 → carried in PR19 handoff §5.1) — still deferred. v5 §J `EQUIPMENT_CATEGORIES` is gym-centric; outdoor_park shared profiles render irrelevant gym checkboxes. Trigger: Andy starts using park locales for real sessions.
- **Trip-locale taxonomy decoupling** (PR19 handoff §5.2) — still deferred. Defer-trigger: Andy wants to save specific travel destinations as locales for trip-row picking.
- **v1 coaching form replacement** (PR19 handoff §5.3) — still scheduled for v2 LLM-pipeline cutover. PR19's form-level guard + athlete-locale-aware dropdown work will be thrown away when v2 ships.
- **Layer 4 §14 retrospective** — still owed. Lands before Layer 4 implementation per `Layer4_Spec.md` §12.6 deferral. Now covers both the D-63-sport-unavailable amendments + the intensity_modulated broadening from this session.

---

## 6. Forward pointers

**Next session:** Andy's choice. The 5 candidates with Layer 4 spec v1 + 4/5 prompt bodies landed:

- **Layer 4 §14 retrospective** — fresh-eyes critical-evaluation pass over §§1–13 (including both amendment rounds — D-63 sport-unavailable in single-session, intensity_modulated broadening this session). Lands before Layer 4 implementation per §12.6 deferral. Spec work, not code.
- **Race-week-brief prompt body** — 5 of 5 in the prompt-body arc. Pattern B; pre-race only; longer max_tokens for `RaceWeekBrief` + multi-day `RacePlan`. Stop-and-ask trigger #2 will fire on architectural picks.
- **Layer 4 implementation track** — D-63 + D-64 T1/T2 LLM-call layers can now be implemented against `Layer4_SingleSession_v1.md` + `Layer4_RefreshT1_v1.md` + `Layer4_RefreshT2_v1.md`. T3-intra-phase routing decision (own prompt vs subsume T2 vs defer) is implementation-time; T3 cross-phase + race-week-brief still need their prompt bodies. Deterministic-validator harness + payload schema scaffolding can start independently.
- **v5 onboarding implementation PR** — substantial code work per `Plan_Refresh_D64_Design_v1.md` §7 storage + `Athlete_Onboarding_Data_Spec_v5.md` §J locale-system carry-forwards.
- **D-50 wiring resumption** — COROS OAuth + webhook recording (now unblocked by D-58).
- **PR18 follow-on — park-specific tag taxonomy** — defer-trigger as flagged in §5.6.

**Before the next session:**

1. **Read `aidstation-sources/CLAUDE.md` fully** (Rule #13). Last-shipped narrative now leads with the T1/T2 session; Backlog ref now points at v36; Layer 4 row notes both spec amendment rounds.
2. Read this handoff in full.
3. (Optional) Re-read predecessor closing handoffs that build on this session's work: `V5_Implementation_PR19_LOCALES_Retire_Closing_Handoff_v1.md` (immediate predecessor — context on the branch + main state) and `V5_Design_Layer4_Prompts_SingleSession_Closing_Handoff_v1.md` (single-session is the Pattern B precedent that T1/T2 inherit conventions from).
4. (If picking Layer 4 implementation track) Read `Layer4_Spec.md` §5.3 + §5.4 + §5.5 + §7 + §11 carefully — the implementation contracts.
5. (If picking race-week-brief) Read `Layer4_Spec.md` §3.4 + §7.13 + §7.14 + §5.4 race-week-brief sub-bullet — the entry-point spec + RaceWeekBrief + RacePlan schemas + validator scope.

**Rules in force, unchanged:**

- #9 session-start verification — applied (see §1 above); branch state confirmed clean off main; PR19 ship verified.
- #10 session-end verification — applied (see §7 below).
- #11 mechanically-applicable deferred edits — race-week-brief design picks captured in §5.1 above with mechanical scope outline.
- #12 numeric version suffixes — Backlog now at v36; next state-changing event bumps v36 → v37.
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §6 first-action explicitly names CLAUDE.md.

---

## 7. Session-end verification (Rule #10)

Final pass over each claimed file edit before composing this handoff:

| Check | Result |
|---|---|
| `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` exists | ✅ `ls` returns file |
| `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` has 14 H2 sections | ✅ `grep -c "^## "` |
| `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` decision table covers D1–D11 | ✅ inline read |
| `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` §4.1 tool schema has 7-flag `coaching_flags` enum | ✅ inline read |
| `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` §12 has 15 PSS-T1 test scenarios | ✅ inline count |
| `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` exists | ✅ `ls` returns file |
| `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` has 14 H2 sections | ✅ |
| `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` decision table covers D1–D11 with T2-vs-T1 differences | ✅ inline read |
| `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` §12 has 18 PSS-T2 test scenarios | ✅ |
| `Layer4_Spec.md` §8.6 `intensity_modulated` trigger row broadened to cover plan_refresh paths | ✅ inline read line 1045 |
| `Layer4_Spec.md` §8.7 `intensity_modulated` observation row references broadened §8.6 | ✅ inline read line 1057 |
| `CLAUDE.md` last-shipped-narrative leads with T1/T2 session | ✅ |
| `CLAUDE.md` Layer 4 row reads "PROMPT BODIES 4/5" | ✅ |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v36.md` | ✅ |
| `CLAUDE.md` Layer 4 prompt-bodies bullet lists 4 shipped + 1 queued + adds T1/T2 filenames | ✅ |
| `CLAUDE.md` Next-forward-move "Layer 4 prompt-body design sessions" reads "1 remaining" | ✅ |
| `Project_Backlog_v36.md` exists | ✅ |
| `Project_Backlog_v36.md` line 5 starts with `**File revision:** v36 — 2026-05-17 (**Layer 4 per-tier T1/T2 refresh synthesizer prompt bodies` | ✅ |
| `Project_Backlog_v36.md` line 6 = `**Predecessor revisions:**` (single occurrence) | ✅ `grep -c` returns 1 |
| `Project_Backlog_v36.md` line 7 starts with `- v35 — 2026-05-16 (**PR19 — retire legacy LOCALES external consumers` | ✅ |
| Two prompt body files + spec amendment + 3 bookkeeping = 6 files this session | ✅ |

---

## 8. Carry-forward from PR18 + PR19 + Layer 4 arc (informational)

- **PR18 §5.0** — 12 testable steps owed; pending Vercel deploy + walk.
- **PR19 §5.0** — 11 testable steps owed; pending Vercel deploy + walk.
- **PR11 step 6** — re-walkable + flippable to ✅ once PR18 deploys (unblocked by PR18 item B).
- **Layer 4 prompt-body arc** — 4 of 5 shipped (seam-reviewer + per-phase + single-session + per-tier T1/T2); 1 remaining (race-week-brief). Per-prompt cadence in effect.
- **Layer 4 §14 retrospective** — still owed; covers both amendment rounds now (D-63 sport-unavailable + intensity_modulated broadening).
- **Layer 4 implementation track** — D-63 + D-64 T1/T2 LLM-call layers ready for implementation against the prompt bodies + spec contracts. T3 + race-week-brief still partially blocked on the final prompt body.
- **Park-tags follow-up** — still deferred per PR18 §5.2.

---

**End of handoff.** Per-tier T1/T2 refresh synthesizer prompt bodies shipped — `Layer4_RefreshT1_v1.md` (~700 lines) + `Layer4_RefreshT2_v1.md` (~750 lines) — 4 of 5 in the Layer 4 prompt-body arc. Andy's three architectural picks: (b) two files per tier, (c) strong-bias toward NL intent, (a) match-surrounding-shape continuity. Paired spec amendment to `Layer4_Spec.md` §8.6 + §8.7 broadens the `intensity_modulated` flag trigger from D-63-only to also cover `plan_refresh` paths — provides the audit-trail mechanism for refresh-path modulation against natural periodization-shape reading. 6 files this session (1 over ceiling; precedented by single-session). One prompt body left in the arc: race-week-brief.
