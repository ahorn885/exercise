# D-73 Phase 5.2 Caller-Side D-64 — NL Parser Prompt Body — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side D-64 — Trigger #2 LLM-prompt-design gate cleared for the D-64 plan-refresh NL parser per `Plan_Refresh_D64_Design_v1.md` Decision #12 deferral. Pure prompt-body design session; **1 substantive file** (well under 5-file ceiling): NEW `aidstation-sources/prompts/NLParser_v1.md`. No code, no schema, no routes, no test count delta — runtime + Flask route land in the paired follow-on session under Triggers #1 + #5.
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_CallerSide_D63_PlanCreate_Routes_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/implement-caller-routes-RlmPU`
**Status:** 1 substantive file. Tests 1235 → 1235 (no delta — pure design session). Container-runnable subset 568 → 568. 4 SDK smoke tests still skip cleanly.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (D-63 + plan-create routes) handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` has `ad_hoc_workout_suggestions` migration | `grep -n "CREATE TABLE IF NOT EXISTS ad_hoc_workout_suggestions" init_db.py` | ✅ |
| `routes/ad_hoc_workouts.py` exists with `/workouts/*` Blueprint | grep | ✅ |
| `routes/ad_hoc_workouts.py` has 4 routes + 9 helpers | grep | ✅ both |
| `routes/plan_create.py` exists with `/plans/v2/*` Blueprint | grep | ✅ |
| `routes/plan_create.py` has 2 routes + 5 helpers | grep | ✅ both |
| Templates exist (`workouts/build_form.html`, `workouts/suggestion_view.html`, `plan_create/new_form.html`, `plan_create/view.html`) | ls | ✅ |
| `tests/test_routes_ad_hoc_workouts.py` has 8 classes + 29 tests | grep | ✅ |
| `tests/test_routes_plan_create.py` has 4 classes + 16 tests | grep | ✅ |
| `app.py` registers 2 new blueprints | grep | ✅ |
| Container-runnable subset green at 568 | pytest | ✅ |
| `CURRENT_STATE.md` last-shipped pointer → Phase 5.2 caller-side D-63 + plan-create | grep | ✅ |
| `CARRY_FORWARD.md` D-63 + plan-create entries struck | grep | ✅ |

`./scripts/verify-handoff.sh` flagged 3 ❌ at session start — `aidstation-sources/prompts/NLParser_v1.md` + `routes/plan_refresh.py` + `templates/plans/v2/refresh.html`. All 3 are pre-explained forward-pointers from the predecessor handoff §1 reconciliation note (queued D-64 caller-side route + NL parser body, both deferred per D-64 Decision #12 to a paired prompt-design + runtime session).

**Reconciliation note:** Clean. No drift. This session closes 1 of the 3 forward-pointers (`prompts/NLParser_v1.md` lands here). 2 remain — `routes/plan_refresh.py` + `templates/plans/v2/refresh.html` — both queued for the paired D-64 runtime session.

---

## 2. Session narrative

Andy picked the **D-64 prompt-body design session** at the AskUserQuestion gate over (b) D-64 route + NL parser glue jumping past the prompt-design step, (c) Dashboard CTAs, or (d) Log-this slice. Per CLAUDE.md Trigger #2 (LLM prompt design), the session entered the design gate before drafting.

Pre-design surface survey checked:

- `Plan_Refresh_D64_Design_v1.md` §5 — input/output contract locked: `IntentParserInput(nl_text, tier, athlete_locales, athlete_active_injuries)` → `ParsedIntent` (5 trigger flags + 3 soft signals + raw_text + parser_confidence + ambiguity_notes). §5.3 caching: `(athlete_id, sha256(nl_text_normalized), parser_prompt_version)`. §5.4 failure mode: degraded `ParsedIntent` with `parser_confidence='low'`.
- `layer4/context.py:1176` — `ParsedIntent` pydantic model already shipped; schema target for the tool's `additionalProperties: false` mirror.
- `layer4/plan_refresh.py:1207` — `_default_parsed_intent()` already implements the D-64 §5.4 degraded fallback; the route layer substitutes this on `NLParserError`.
- `aidstation-sources/prompts/Layer3A_v1.md` — 707-LOC 13-section structure precedent for the document shape; Layer4_SingleSession_v2.md (528 LOC) as the lighter precedent for a less-interpretive surface.
- `aidstation-sources/prompts/`: 14 existing prompt bodies — no NL-parser-shaped precedent; this is a new prompt shape (classification, not synthesis).

14 D-decisions surfaced + ratified at the AskUserQuestion gate before drafting:

- **D1: Model = Sonnet 4.6.** Haiku 4.5 migration tracked as §12 NL-1 open item, gated on a smoke-eval harness. NL parsing is classic Haiku territory but parser is load-bearing (wrong classification → wrong cascade); ship Sonnet for accuracy parity with the rest of the L3/L4 family; revisit when evals exist.
- **D2: No extended thinking** (budget 0 tokens). Classification is shallow; no reasoning chain. Matches single-session also at 0.
- **D3: Forced tool-use, strict schema.** Single tool `record_parsed_intent`; `tool_choice={"type":"tool","name":"record_parsed_intent"}`; `additionalProperties: false` at every nesting level. L3/L4 family precedent.
- **D4: Full `ParsedIntent` mirror MINUS `raw_text` (driver-stamped per D7).** Tool schema covers the 10 fields the LLM actually decides (5 triggers + 3 soft signals + parser_confidence + ambiguity_notes). L3A D5 precedent for driver-stamped metadata.
- **D5: Middle-path injury disambiguation.** New-injury keywords ("tweaked", "hurt", "strained", "sharp", "sudden", "twisted") → `triggers_2d_injury=TRUE`. Update-on-existing ("feels better", "healing", "less pain") → FALSE. Ambiguous → TRUE + `ambiguity_notes` populated. Conservative bias toward firing 2D (cheap query node) + ambiguity surfaced via diff per D-64 Decision #9.
- **D6: Strict closed-vocabulary locale matching.** `triggers_2c_equipment` may contain only slugs present in `athlete_locales` input. Out-of-vocab locations ("hotel gym") → leave list empty + populate `ambiguity_notes`. Layer 2C only knows configured slugs; closed-vocab + ambiguity escape is the right contract.
- **D7: Driver-stamped `raw_text` post-hoc.** LLM doesn't echo input. Matches L3A D5 metadata convention.
- **D8: Single retry on schema violation + `NLParserError` raise.** Route catches the error + substitutes `_default_parsed_intent()` per D-64 §5.4 (already implemented at `layer4/plan_refresh.py:1207`).
- **D9: Classification-only voice.** No CLAUDE.md coaching-voice inheritance. System prompt = classification rules + decision criteria + ambiguity-notes guidance. Parser doesn't write athlete-facing copy.
- **D10: `temperature=0`** for deterministic output + cache contract per D-64 §5.3.
- **D11: 13-section document structure** mirroring Layer3A_v1.md / Layer4_SingleSession_v2.md (Source decisions / 1. Purpose / 2. Pipeline placement / 3. Inputs / 4. Tool schema / 5. System prompt / 6. User prompt / 7. Sampling / 8. Post-LLM transforms / 9. Performance budget / 10. Caching / 11. Test scenarios / 12. Open items / 13. Gut check). ~580 LOC — lighter than Layer3A (707) because classification has fewer prep transforms + less voice content.
- **D12: `NL_PARSER_PROMPT_VERSION = 1` constant lives in `nl_parser.py` runtime module**, NOT in the markdown. D-64 §5.3 cache key includes parser_prompt_version; runtime module is the canonical source. Markdown is a design doc.
- **D13: Performance budget** ~150-300 input tokens / ~100-200 output tokens / ~500-800ms wall-clock cached / ~1-2s cold; ~$0.003-$0.005/cold call (~10× Haiku migration savings tracked as §12 NL-1).
- **D14: Smoke-eval harness deferred to paired runtime session.** ~10-15 hand-labeled NL→ParsedIntent fixtures from Andy's PGE 2026 + AR vocab; lands as `tests/test_nl_parser_smoke.py` (env-gated `@requires_anthropic_api_key`) when the runtime ships.

Implementation flow:

1. **Pre-flight context gathering** — read `Plan_Refresh_D64_Design_v1.md` (§5 contract + §11 forward-pointer test scenarios) + `layer4/context.py:1176` `ParsedIntent` model + `layer4/plan_refresh.py:1207` `_default_parsed_intent()` + existing prompt-body precedents (Layer3A_v1.md / Layer4_SingleSession_v2.md / Layer3B_v1.md / Layer4_RefreshT1_v2.md / Layer4_PerPhase_v2.md).

2. **AskUserQuestion gate** — surfaced 4 design questions to Andy (model choice / injury disambig rule / locale matching strictness / overall design ratification); Andy ratified the recommended set verbatim.

3. **Document drafting** — NEW `aidstation-sources/prompts/NLParser_v1.md` (~580 LOC). 13 sections + Source decisions header. Section sizing decisions:
   - §4 tool schema with full `additionalProperties: false` mirror of 10 emit-fields (excluding `raw_text` per D7).
   - §5 system prompt as 10 hard rules covering: output mechanism / conservative-bias on triggers / 5 per-trigger flag rules / 3 soft-signal rules per closed enum / parser_confidence calibration / ambiguity_notes guidance + 240-char cap / tier-mismatch policy / empty-input short-circuit / forbidden output / classification-only voice.
   - §6 user prompt template (4 input variables — `nl_text` wrapped in triple-backtick block / `tier_label` rendered with horizon context / `athlete_locales_block` one-per-line / `athlete_active_injuries_block` one-per-line) + retry augmentation block.
   - §7 sampling config table: model=`claude-sonnet-4-6` / temp=0 / max_tokens=1024 / no extended thinking / capped_retries=1 / forced tool_choice.
   - §8 post-LLM transforms: `_enforce_closed_locale_vocab` strip per D6 + telemetry note to `ambiguity_notes`; explicit "no confidence-floor clamp" + "no evidence-basis cross-check" rationale.
   - §10 caching per D-64 §5.3 with `_normalize_nl_text(text) = " ".join(text.lower().split())` + cache scope `"nl_parser"` outside `LAYER4_ENTRY_POINTS` (parser cache is athlete-scoped, not Layer-4-scoped).
   - §11 test scenarios — 15 stub-LLM fixtures across TS1-TS15 + closed-vocab violation test + env-gated real-LLM smoke harness deferral.
   - §12 8 open items (NL-1 Haiku migration / NL-2 athlete-level invalidation / NL-3 out-of-vocab auto-add CTA / NL-4 multi-signal density telemetry / NL-5 tier-mismatch v2 / NL-6 soft-signal granularity / NL-7 prompt-version dev-override / NL-8 streaming infeasibility).
   - §13 gut check covering accuracy risk + Sonnet cost at scale + vernacular drift + tier-mismatch softness + existing-injury phrasing ambiguity + 4 "what might be missing" items + best-arg-against (prompt-engineering without evals).

4. **No code, no schema, no tests.** Pure design session — by definition no test count delta. Runtime + route session pairs the smoke-eval harness with the route implementation.

5. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count unchanged (1235); current-focus arc refocused on D-64 caller-side runtime session as the remaining unblocked surface (with Trigger #2 cleared). `Upstream_Implementation_Plan_v1.md` §4 new row `5.2.Caller-D64-Prompt`. `CARRY_FORWARD.md` D-64 caller-side entry updated to reflect prompt-body landing + remaining runtime work. This closing handoff.

Only `/plan` Trigger #2 (LLM prompt design) fired this session — exactly the trigger this session was scoped against. No #1 / #3 / #5 triggers since no form copy, no schema, no route shape work landed.

---

## 3. File-by-file edits

### 3.1 NEW `aidstation-sources/prompts/NLParser_v1.md` (~580 LOC)

- 13-section structure mirroring Layer3A_v1.md (707 LOC) / Layer4_SingleSession_v2.md (528 LOC).
- Source decisions header documents 14 D-decisions with rationale.
- §1 Purpose + scope — what the prompt produces (10 fields), what it does NOT (no coaching, no diagnosis, no out-of-vocab slug invention, no soft-signal expansion, no tier override), failure modes + retry semantics.
- §2 Pipeline placement — call site `nl_parser.parse_intent(input) -> ParsedIntent`; 5-step internal flow (short-circuit empty / render user prompt / LLM call / schema validate + driver-stamp `raw_text` / return).
- §3 Inputs — 4 template variables rendered from `IntentParserInput`.
- §4 Tool schema — `record_parsed_intent` tool with 10 required emit-fields. Includes the rationale for why `ambiguity_notes` is LLM-emitted (not driver-stamped) + the locale-slug closed-vocab constraint enforcement strategy (post-LLM strip).
- §5 System prompt (verbatim ~120 tokens) — 10 hard rules covering output mechanism, conservative-bias, 5 trigger rules, 3 soft-signal closed enums with example keyword phrases for each level, parser_confidence calibration, ambiguity_notes guidance, tier-mismatch policy, empty-input short-circuit, forbidden output, voice for ambiguity_notes.
- §6 User prompt template (verbatim with Mustache-style placeholders) + retry augmentation block.
- §7 Sampling config table.
- §8 Post-LLM transforms: `_enforce_closed_locale_vocab(parsed, allowed_slugs)` snippet with model_copy + 240-char cap respect + telemetry note append.
- §9 Performance budget table — Sonnet vs Haiku cost comparison line.
- §10 Caching — cache key shape + `_normalize_nl_text` impl + scope outside `LAYER4_ENTRY_POINTS` + v1 athlete-level invalidation deferral note.
- §11 Test scenarios — 15 stub-LLM fixture table (TS1-TS15) + closed-vocab violation transform test + env-gated smoke harness deferral.
- §12 Open items — 8 tracked tuning candidates.
- §13 Gut check — risks + what might be missing + best argument against + counter-counter.

---

## 4. Code / tests

**No code or test changes this session.** Pure design / prompt-body work.

**Test count delta:** 1235 → 1235 (no change). 4 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

**Container-runnable subset:** 568 → 568 (no change).

Run reproducer for the predecessor's tests (no new tests this session):

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                                tests/test_race_events_repo.py \
                                tests/test_race_events_invalidation.py \
                                tests/test_onboarding_race_events.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py \
                                tests/test_plan_sessions_repo.py \
                                tests/test_routes_ad_hoc_workouts.py \
                                tests/test_routes_plan_create.py
# 568 passed in ~1.0s
```

**No-regression confirmation:** No code touched; no regression risk. Test suite is unchanged from the predecessor session.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + all 7+ predecessor handoffs §4).

---

## 5. Manual §5.0 verification steps

**No new §5.0 walkthrough scenarios this session.** Pure prompt-body design is not §5.0-walkable until the paired runtime session lands the parser + route; at that point the smoke-eval harness (§11.3 of the prompt body) becomes the §5.0 walk.

**Forward-pointer for the paired runtime session §5.0:**

**Step 1: Stub-LLM unit tests pass.** Run `pytest tests/test_nl_parser.py -q` — reports 16 passed (15 stub-LLM TS1-TS15 fixtures + 1 closed-vocab violation transform test).

**Step 2: Real-LLM smoke harness against Andy's vocab.** With `ANTHROPIC_API_KEY` set, run `pytest tests/test_nl_parser_smoke.py -q` — reports 10-15 hand-labeled fixtures passed. Real-LLM cost: ~$0.05 per smoke run.

**Step 3: D-64 route E2E against Andy's PGE 2026 context.**
- Log in as Andy.
- Navigate to `/plans/v2/refresh` (direct URL — dashboard CTA is a follow-on).
- Pick tier=T1, NL text="I'm tired"; click Refresh.
- Confirm parser routes `fatigue_signal='tired'` + all triggers FALSE + `parser_confidence='high'` + `ambiguity_notes=None`.
- Confirm a `plan_refresh_log` row lands with `parsed_intent` JSONB populated + `layers_run=['3A', '3B', 'Layer4']` + `success=TRUE`.
- Confirm a new `plan_versions` row + scoped `plan_sessions` rows for `[today, today+1]` land atomically.
- Real-LLM cost: ~$0.30-$0.50 per refresh (parser + 3A + 3B + Layer 4 Pattern B cascade).

These scenarios pair with the runtime session's `CARRY_FORWARD.md` §5.0 entries.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**D-64 caller-side runtime + route session.** Composes the NL parser prompt body shipped this session into the runtime + Flask route. Trigger #2 (NL parser prompt design) is CLEARED this session; remaining `/plan` gates are **Trigger #1 (form copy on the refresh-trigger card)** + **Trigger #5 (route shape — dashboard vs plan-view entry points + redirect-after-refresh UX)**.

Files (est. 5-7 substantive):

1. NEW `nl_parser.py` (~250-350 LOC) — LLM-backed parser runtime. Anthropic SDK adapter mirroring Layer3A/B builder shape but lighter (no extended thinking, no 8 prep helpers — just `_short_circuit_empty` + `_render_user_prompt` + `_default_llm_caller` + `_enforce_closed_locale_vocab` post-LLM transform + `NL_PARSER_PROMPT_VERSION = 1` constant). Module exports: `parse_intent` + `IntentParserInput` + `NLParserError` + `NL_PARSER_PROMPT_VERSION` + `build_record_parsed_intent_tool`.

2. NEW `routes/plan_refresh.py` (~250-350 LOC) — Blueprint `/plans/v2/refresh/*`. Reads tier + nl_text from the form, looks up athlete_locales from `locale_profiles` + athlete_active_injuries from `injury_log`, allocates `plan_versions` row (via `allocate_plan_version_row(created_via='plan_refresh_t1/t2/t3')`), queries prior window via `load_prior_plan_session_window(tier=tier)`, runs NL parser → ParsedIntent (catching `NLParserError` → `_default_parsed_intent()` per D-64 §5.4), invokes `orchestrate_plan_refresh`, persists via `persist_layer4_sessions`, commits atomically per D-64 §6.2. Writes a `plan_refresh_log` row.

3. NEW `templates/plans/v2/refresh.html` — tier-picker radio (T1/T2/T3 with horizon labels per D-64 §3) + NL text textarea (~500 char soft cap per D-64 §4.2) + Refresh button. Includes the "Refreshing your plan…" toast per D-64 §4.3 (Andy can iterate on this).

4. NEW `tests/test_nl_parser.py` (~300-400 LOC) — stub-LLM unit tests for the 15 fixtures in NLParser_v1.md §11.1 (TS1-TS15) + the closed-vocab violation transform test in §11.2 + `_short_circuit_empty` test + `_FakeAnthropicCaller` fixture pattern from Layer3A precedent.

5. NEW `tests/test_nl_parser_smoke.py` (~300-400 LOC) — env-gated `@requires_anthropic_api_key` real-LLM smoke harness against Sonnet 4.6 with ~10-15 hand-labeled fixtures derived from Andy's PGE 2026 + AR + multi-sport vocab. Fixtures must cover: clean signals / re-aggravation ambiguity / out-of-vocab location / extreme fatigue / sickness signal / nutrition shift / tier mismatch / empty input. Skips cleanly when key unset.

6. NEW `tests/test_routes_plan_refresh.py` (~250-350 LOC) — helper-level pytest matching the precedent of `tests/test_routes_ad_hoc_workouts.py` + `tests/test_routes_plan_create.py`. Covers: tier parsing + form validation + parser-error fallback to `_default_parsed_intent()` + atomic transaction shape (no commit on orchestrator exception) + plan_refresh_log row writes.

7. POSSIBLY `init_db.py` migration for `plan_refresh_log` table per D-64 §7.1 — depends on whether the runtime session opts to ship telemetry in v1 or defer.

**`/plan` gate sequence:** Trigger #1 (form copy on refresh card) + Trigger #5 (route shape — dashboard CTA vs plan-view button entry points + redirect-after-refresh UX) BEFORE implementation. Trigger #2 (NL parser prompt design) ALREADY CLEARED this session.

**Optional pair:** add `plan_refresh_log` migration + telemetry write OR defer to a follow-on. D-64 §7.1 specifies the table; v1 can ship without telemetry if cost-pressure dictates, but the analytics signal is named load-bearing in D-64 Decision #11. Recommend including in the runtime session.

### 6.2 Alternative pivots

- **Log-this slice + D-63 T1 plan-check hook** — pairs with D-64 caller-side. Adds `is_ad_hoc` + `ad_hoc_request_payload` + `ad_hoc_suggestion_id` extensions to `cardio_log` + `training_log` per D-63 §5.1/§5.2; wires `[Log this workout]` button on `templates/workouts/suggestion_view.html`; surfaces T1 refresh CTA. Gated on D-64 caller-side landing first (T1 hook needs the refresh route). ~5-7 files.
- **Dashboard CTAs** — `/workouts/build` + `/plans/v2/new` + (now) `/plans/v2/refresh` cards on `templates/dashboard.html`. ~1-2 files. Pair with manual §5.0 walkthrough.
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1 + #3 + #5).
- **Layer 3A + 3B caching policy modules at orchestrator level** — with 4 entry points + 2 of 3 caller-side routes shipped + NL parser shipping next, the orchestrator-level cache is increasingly load-bearing. ~4-6 files.
- **Layer 3B None-tolerant kwargs L3B-P-2** consumer migration. ~3-4 files.
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — ~1-2 files; doc-sweep nit from form-refresh C.
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Manual §5.0 walkthrough** of D-63 + plan-create routes E2E on Neon (once dashboard CTAs land for findability). Real-LLM ~$0.50-$1.00 per pass.
- **Real-LLM Layer 4 regression** parity to plan_create (~$0.30-$0.50 per cold synthesis on Pattern A's per-phase loop).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_CallerSide_D64_NLParser_Prompt_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `aidstation-sources/prompts/NLParser_v1.md` — the prompt body shipped this session; load-bearing input for the runtime session.
6. `aidstation-sources/Plan_Refresh_D64_Design_v1.md` — input/output contract + cascade rules + telemetry schema.
7. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Model = `claude-sonnet-4-6`; Haiku 4.5 migration as §12 NL-1 candidate gated on smoke-eval harness | Andy ratified at AskUserQuestion gate | NL parsing is classic Haiku territory but the parser is load-bearing (wrong classification routes the wrong cascade). Ship Sonnet for accuracy parity with the L3/L4 family. Document Haiku migration as a cost-optimization tuning candidate once evals exist. Cost gain ~10× ($0.0003-$0.0005 vs $0.003-$0.005 per cold call). |
| **D2** | No extended thinking (budget 0 tokens) | Andy | Classification is shallow; no reasoning chain required. Matches single-session also at 0. Cost + latency win. |
| **D3** | Forced tool-use with strict `additionalProperties: false` schema | Andy | L3/L4 family precedent. JSON-mode text output would force regex parsing; forced tool-use is the established contract. |
| **D4** | Full `ParsedIntent` mirror MINUS `raw_text` (driver-stamped per D7) | Andy | L3A D5 precedent — metadata fields the LLM doesn't add value re-emitting are post-hoc stamped. `raw_text` is just the input echoed. Halves output tokens on the trivial passthrough. |
| **D5** | Middle-path injury disambiguation rule | Andy | New-injury keywords ("tweaked"/"hurt"/"strained"/"sharp"/"sudden"/"twisted") → TRUE / update-on-existing ("feels better"/"healing"/"less pain") → FALSE / ambiguous → TRUE + `ambiguity_notes`. Conservative bias toward firing 2D (cheap query node) + ambiguity surfaced via diff per D-64 Decision #9 (athlete spots mis-routing and reverts). |
| **D6** | Strict closed-vocabulary locale matching | Andy | `triggers_2c_equipment` may contain only slugs in `athlete_locales` input. Out-of-vocab locations surface via `ambiguity_notes`. Layer 2C only knows configured slugs; emitting unknown slugs would silently no-op downstream. Closed-vocab + ambiguity escape is the right contract. |
| **D7** | Driver-stamped `raw_text` post-hoc | Andy | Same precedent as L3A D5 metadata fields. LLM doesn't need to echo the input. |
| **D8** | Single retry on schema violation + `NLParserError` raise; route substitutes `_default_parsed_intent()` per D-64 §5.4 | Andy | Schema-violation retry matches L3A precedent (§5.3 step 1). D-64 §5.4 mandates degraded fallback rather than raise-to-caller; the route layer is the seam where the substitution happens. |
| **D9** | Classification-only voice — no CLAUDE.md coaching voice inheritance | Andy | Parser doesn't write athlete-visible copy. `ambiguity_notes` is single-sentence-flag style, not coaching tone. |
| **D10** | `temperature=0` for deterministic output | Andy | Classification + cache contract per D-64 §5.3 require identical input → identical output. |
| **D11** | 13-section document structure mirroring Layer3A_v1.md / Layer4_SingleSession_v2.md | Andy | Consistency with existing prompt-body docs. The 13-section depth standard is named in CLAUDE.md Working Principles. ~580 LOC — lighter than Layer3A (707) because classification has fewer prep transforms + less voice content. |
| **D12** | `NL_PARSER_PROMPT_VERSION = 1` constant lives in `nl_parser.py` runtime module, NOT in this markdown | Andy | D-64 §5.3 cache key includes parser_prompt_version; runtime module is the canonical source. Markdown is a design doc. The next session that touches the prompt bumps the constant. |
| **D13** | Performance budget ~150-300 input tokens / ~100-200 output tokens / ~$0.003-$0.005/cold call | Andy | Empirical estimate based on Sonnet 4.6 classification calls of similar shape (Layer 2A discipline classifier neighborhood). Haiku migration would be ~10× cheaper if evals support it. |
| **D14** | Smoke-eval harness (~10-15 hand-labeled fixtures from Andy's PGE 2026 + AR vocab) deferred to paired runtime session | Andy | Spec-first sequencing: design the prompt; build evals when there's a route to feed traffic into. The runtime session pairs the harness with the route implementation, so v1 prompt edits can be measured before v2 ships. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| NEW `aidstation-sources/prompts/NLParser_v1.md` exists | ✅ `ls aidstation-sources/prompts/NLParser_v1.md` |
| `NLParser_v1.md` has 13 top-level sections + Source decisions | ✅ `grep -c "^## " aidstation-sources/prompts/NLParser_v1.md` returns 14 |
| `NLParser_v1.md` is ~580 LOC | ✅ `wc -l aidstation-sources/prompts/NLParser_v1.md` returns 578 |
| `NLParser_v1.md` documents 14 D-decisions | ✅ `grep -cE "^\| D[0-9]+ \|" aidstation-sources/prompts/NLParser_v1.md` returns 14 |
| `NLParser_v1.md` §4 tool schema mirrors 10 emit-fields (sans raw_text) | ✅ grep for the 10 field names in §4 |
| `NLParser_v1.md` §5 system prompt has 10 hard rules | ✅ grep `^[0-9]+\. ` in §5 |
| `NLParser_v1.md` §11 documents 15 stub-LLM fixtures (TS1-TS15) | ✅ grep `^\| TS[0-9]+ \|` returns 15 |
| `NLParser_v1.md` §12 documents 8 open items (NL-1..NL-8) | ✅ grep `^\| NL-[0-9]+ \|` returns 8 |
| Container-runnable subset still green at 568 | ✅ no test changes this session — pre-existing 568 unchanged |
| `Upstream_Implementation_Plan_v1.md` §4 has new row `5.2.Caller-D64-Prompt` → ✅ Shipped 2026-05-21 | ✅ `grep "5.2.Caller-D64-Prompt" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 caller-side D-64 NL parser prompt handoff | ✅ |
| `CURRENT_STATE.md` tests count unchanged at 1235 (no code/test delta) | ✅ |
| `CURRENT_STATE.md` Layer 4 status row updated to reflect prompt-body landing | ✅ |
| `CARRY_FORWARD.md` D-64 caller-side entry updated to reflect prompt-body shipped + remaining runtime work | ✅ |

---

## 9. Files shipped this session

**Substantive (1 file; well under 5-file ceiling):**

1. NEW `aidstation-sources/prompts/NLParser_v1.md` (~580 LOC) — 13-section prompt body for the D-64 plan-refresh NL parser.

**Bookkeeping (4 files):**

2. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flip + current-focus arc refocused on D-64 caller-side runtime session as the remaining unblocked surface + Layer 4 status row note for prompt-body landing.
3. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — D-64 caller-side route entry updated to reflect prompt-body landed; remaining runtime work + Triggers #1 + #5 gates clarified; Trigger #2 marked CLEARED.
4. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row `5.2.Caller-D64-Prompt`.
5. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_CallerSide_D64_NLParser_Prompt_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- "D-64 caller-side route + NL parser glue" entry updated — prompt-body landed (sub-item ✅ Shipped 2026-05-21); remaining runtime + route work itemized; Trigger #2 marked CLEARED; remaining gates Triggers #1 + #5.

**Phase 5.2 caller-side D-64 prompt body complete; D-64 caller-side runtime + route remain (gated on `/plan` Triggers #1 form copy + #5 route shape — Trigger #2 cleared this session). 4 of 4 Layer 4 entry-point orchestrators wired; 2 of 3 caller-side routes E2E-reachable from v1 UI (single_session + plan_create); D-64 plan_refresh route is the last unblocked caller-side surface. NL parser prompt body is the structural prerequisite shipped here; runtime + route session pairs the smoke-eval harness with the route implementation.**

---

**End of handoff.**
