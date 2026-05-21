# D-73 Phase 5.2 Caller-Side D-64 — NL Parser Runtime + plan_refresh Route — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side D-64 — runtime + Flask route. Composes the NL parser prompt body shipped earlier same-day (`NLParser_v1.md`) with the runtime + Flask route, closing the D-64 caller-side surface end-to-end. **8 substantive files** (ceiling break ratified at the scope-selection AskUserQuestion gate; precedented by 5.1.A=8 / 5.1.C=8 / 5.2.Caller-D63+PlanCreate=9).
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_CallerSide_D64_NLParser_Prompt_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/implement-caller-routes-PciAJ`
**Status:** 8 substantive files. Tests 1235 → 1331 (+96 across 3 NEW test files). Container-runnable subset 568 → 664 in ~1.0s. 12 new env-gated NL parser smoke tests skip cleanly when `ANTHROPIC_API_KEY` unset; default `pytest tests/` reads "1331 passed, 16 skipped" (4 prior Layer 3 SDK smoke + 12 new NL parser smoke).

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (D-64 NL parser prompt body) handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `aidstation-sources/prompts/NLParser_v1.md` exists | `ls aidstation-sources/prompts/NLParser_v1.md` | ✅ |
| `NLParser_v1.md` has 13 top-level sections + Source decisions | grep `^## ` returns 14 | ✅ |
| `NLParser_v1.md` ~580 LOC | `wc -l` returns 578 | ✅ |
| `NLParser_v1.md` documents 14 D-decisions | grep `^\| D[0-9]+ \|` returns 14 | ✅ |
| `NLParser_v1.md` §11 documents 15 stub-LLM fixtures (TS1-TS15) | grep `^\| TS[0-9]+ \|` returns 15 | ✅ |
| Container-runnable subset still green at 568 | pytest | ✅ |
| `CURRENT_STATE.md` last-shipped pointer → Phase 5.2 caller-side D-64 NL parser prompt | grep | ✅ |
| `CARRY_FORWARD.md` D-64 caller-side entry reflects prompt-body shipped | grep | ✅ |

`./scripts/verify-handoff.sh` flagged 4 ❌ at session start — `routes/plan_refresh.py` + `templates/plans/v2/refresh.html` + `tests/test_nl_parser.py` + `tests/test_nl_parser_smoke.py`. All 4 are pre-explained forward-pointers from the predecessor handoff §6.1 (queued D-64 caller-side runtime + route + tests, paired session per the prompt-body D14 deferral).

**Reconciliation note:** Clean. No drift. This session closes all 4 of the predecessor's forward-pointers + adds a 5th file (NEW `templates/plans/v2/refresh_view.html` for the diff view per Andy's D3 pick).

---

## 2. Session narrative

Andy ratified scope at the AskUserQuestion gate: **D-64 runtime + route + `plan_refresh_log` telemetry** over (a) bare runtime, (c) telemetry-only-no-table, (d) pivot to different work. ~7-8 substantive files; ceiling break pre-ratified per the predecessor precedent.

The 4 design questions surfaced at the AskUserQuestion gate per Trigger #5 (architectural alternatives) — none were `/plan` Trigger #2 (NL parser prompt design already cleared in the predecessor session):

- **D1: No-prior-plan policy = "Tier buttons hidden when no prior plan exists; render empty-state CTA to `/plans/v2/new`; POST defensive-redirect to plan_create when parent_plan is None."** Picked over (b) T3-no-plan auto-routes to plan_create + (c) block all tiers if no plan. Andy's framing: "the options for T1/2/3 shouldn't even be visible to a user if they do not have an active plan." Honors `orchestrate_plan_refresh`'s required `plan_version_id_parent` kwarg cleanly; D-64 §3.3's "T3 as initial-plan-gen path" is a separate UX promise the dashboard CTA layer can satisfy later by routing T3-without-plan to plan_create.
- **D2: Tier UX = 3 named submit buttons (one-click flow).** Picked over (a) radio buttons (D-64 §4.1 spec) + (c) dropdown. Buttons named `submit_t1` / `submit_t2` / `submit_t3` posted with a hidden tier field; `_parse_tier` accepts both `tier=T1` direct form field + the named-submit pattern. Lower friction than radio + click-submit; matches the spirit of the spec (athlete-explicit tier pick) without forcing two clicks.
- **D3: Redirect target = NEW `/plans/v2/refresh/<id>` diff view with 'updated' / 'new' / 'unchanged' badges per D-64 §9.** Picked over (a) reuse plan_create view (loses §9 diff promise) + (c) stay on form with summary card (loses "land on the result" UX). Adds 1 file (`templates/plans/v2/refresh_view.html`) + ~80 LOC of route helper for the diff resolver. Diff signature excludes rebound `plan_version_id` + `session_id` identity fields so structurally identical sessions across versions compare as 'unchanged'.
- **D4: plan_refresh_log telemetry shipped per D-64 §7.1 + frequency caps per D-64 §8 deferred.** Picked over (b) both shipped + (c) telemetry-only-no-table. Caps are anti-cohort guard and N=1 athlete doesn't warrant the modal-confirm UX yet; `cap_overridden` column deferred to the caps follow-on. Telemetry write is INSERT-once-post-orchestrate inside the same transaction (success path) or in a fresh sub-transaction (failure path) so the failure-row log always lands even when the orchestrator rolled back the plan_versions allocation.

Pre-design surface survey:

- `aidstation-sources/prompts/NLParser_v1.md` — full ratified prompt body (system prompt + user prompt template + tool schema + post-LLM transforms + caching + open items). Implementation reads §5 system prompt + §6 user prompt template verbatim into the runtime module; tool schema mirrored in `build_record_parsed_intent_tool()` per D4.
- `aidstation-sources/Plan_Refresh_D64_Design_v1.md` — §5.1 input dataclass + §5.2 output dataclass + §5.3 caching + §5.4 failure mode + §6.2 atomic write + §6.3 per-day version pointer + §7.1 telemetry table schema + §11 test scenarios.
- `layer4/orchestrator.py:509` — `orchestrate_plan_refresh` signature (`tier`, `refresh_scope_start`, `refresh_scope_end`, `plan_version_id`, `plan_version_id_parent`, `prior_plan_session_window`, `cache`, `parsed_intent=None`, `plan_start_date=None`, `today=None`). Required kwargs drive the route's compose order.
- `layer4/plan_refresh.py:1207` — `_default_parsed_intent()` returns the degraded fallback per D-64 §5.4.
- `layer4/context.py:1176` — `ParsedIntent` pydantic model; schema target for the tool's `additionalProperties: false` mirror.
- `plan_sessions_repo.py:45` — `allocate_plan_version_row(db, user_id, *, created_via, scope_start_date, scope_end_date, pattern, notes=None) -> int`. Caller owns transaction.
- `plan_sessions_repo.py:162` — `load_prior_plan_session_window(db, user_id, *, today, tier=None, days=None) -> list[PlanSession]`. Used to pass the prior-window kwarg to `orchestrate_plan_refresh`.
- `routes/plan_create.py` + `routes/ad_hoc_workouts.py` — caller-side route precedents (compose-and-commit pattern, inline-helpers style, helper-level pytest density).
- `layer3a/builder.py:126` — `_default_llm_caller` Anthropic SDK adapter; mirror this shape for the parser's SDK adapter (no extended thinking for the parser per D2).
- `layer3a/cached_wrapper.py` — non-Layer-4 cache-scope precedent. The parser cache extends `VALID_ENTRY_POINTS` with `"nl_parser_parse_intent"` per NLParser_v1.md §10.2 + stays out of `LAYER4_ENTRY_POINTS`.
- `init_db.py:1602` — `_PG_MIGRATIONS` is the migration-list pattern; append the `plan_refresh_log` CREATE TABLE + index.

Implementation flow:

1. **NEW `nl_parser.py`** (~530 LOC) — runtime module. Defines `IntentParserInput` frozen dataclass + `NLParserError` exception (code: `"schema_violation"` / `"network"` / `"input_validation"`) + `LLMCaller` type alias + `_LLMOutput` dataclass (mirrors layer3a) + `_default_llm_caller` Anthropic SDK adapter (forced tool-use single tool `record_parsed_intent`, no extended thinking) + `build_record_parsed_intent_tool()` mirroring `ParsedIntent` MINUS `raw_text` per D4 + D7 + `_SYSTEM_PROMPT` (verbatim from NLParser_v1.md §5) + `_USER_PROMPT_TEMPLATE` + `_RETRY_AUGMENTATION` (verbatim from §6) + helpers (`_normalize_nl_text`, `_short_circuit_empty`, `_render_tier_label`, `_render_block`, `_render_user_prompt`, `_enforce_closed_locale_vocab`, `nl_parser_cache_key`) + `parse_intent(IntentParserInput, *, user_id, cache_backend=None, llm_caller=None, ...) -> ParsedIntent` entry point. Pipeline per NLParser_v1.md §2: short-circuit empty → cache lookup → LLM call → pydantic validate → single retry on schema violation → `_enforce_closed_locale_vocab` → driver-stamp `raw_text` → cache write. Module-level `NL_PARSER_PROMPT_VERSION = 1` per D12.

2. **`layer4/cache.py`** — extend `VALID_ENTRY_POINTS` superset with `"nl_parser_parse_intent"` (athlete-scoped cache scope; kept out of `LAYER4_ENTRY_POINTS` per NLParser_v1.md §10.2 — parser cache stays out of Layer-4-scoped invalidation cascades per the `LAYER4_ENTRY_POINTS` invariant).

3. **NEW `init_db.py` `_PG_MIGRATIONS` entry for `plan_refresh_log`** per D-64 §7.1 (BIGSERIAL PK + user_id FK + tier CHECK + nl_text + parsed_intent JSONB + layers_run TEXT[] DEFAULT '{}' + scope_start_date/scope_end_date DATE + plan_version_id_before/after BIGINT FK to plan_versions + duration_ms + sessions_changed + success BOOLEAN NOT NULL + failure_reason TEXT) + index on `(user_id, triggered_at DESC)`. `cap_overridden` column deferred per D4.

4. **NEW `routes/plan_refresh.py`** (~360 LOC) Blueprint `/plans/v2/refresh/*`. 10 inline helpers (`_build_layer4_cache`, `_latest_plan_version`, `_load_plan_version`, `_athlete_locale_slugs`, `_athlete_active_injury_summary`, `_parse_tier`, `_resolve_scope_dates`, `_orchestration_error_message`, `_run_parser`, `_write_refresh_log`, `_diff_signature`, `_diff_sessions_against_parent`, `_latest_parent_for_refresh`) + 2 routes (`refresh` GET/POST + `view_refresh` GET). Atomic per D-64 §6.2: success path = allocate plan_versions row → parse (degraded fallback per D-64 §5.4 on `NLParserError`) → orchestrate → persist → log → commit. Failure path = catch `OrchestrationError` / `Layer4InputError` / `Layer4OutputError` → rollback → write failure-row log INSERT in a fresh sub-transaction → commit the failure-row so telemetry still lands.

5. **NEW `templates/plans/v2/refresh.html`** — 3-button picker per D-64 §4.1 ("Refresh next 2 days" / "Refresh week" / "Refresh next 4 weeks") + nl_context textarea (~500 char soft cap) + empty-state alert when `parent_plan is None` linking to `/plans/v2/new`. Parent-plan summary card renders when prior plan exists.

6. **NEW `templates/plans/v2/refresh_view.html`** — diff view; updated/new/unchanged badges with per-card border highlighting per badge.

7. **NEW `tests/test_nl_parser.py`** (~600 LOC; 60 tests across 11 classes) — stub-LLM unit tests for the 15 fixtures in NLParser_v1.md §11.1 + closed-vocab violation transform + retry semantics (first-attempt-invalid-second-valid + second-failure-raises + zero-retries-on-first-failure) + network error + cache (miss-then-hit + short-circuit-skips-cache + cache-round-trip-preserves) + tool-schema shape + raw_text driver-stamping. `_FakeLLMCaller` mirrors layer3a test precedent; `_FakeCacheBackend` is a minimal in-memory implementation.

8. **NEW `tests/test_nl_parser_smoke.py`** (~150 LOC; 12 env-gated `@requires_anthropic_api_key` real-LLM tests against Sonnet 4.6) — Andy PGE 2026 vocab covering clean signals (im_tired / cooked_from_race / flu / motivated) + injury disambig (tweaked / strained / feels_better) + locale vocab (in-laws / hotel-gym out-of-vocab) + upstream triggers (kayaking / gi_issues) + empty short-circuit. Skips cleanly when key unset.

9. **NEW `tests/test_routes_plan_refresh.py`** (~450 LOC; 36 tests across 9 classes) — exercises every inline helper directly. Mirrors `tests/test_routes_plan_create.py` test-double patterns for the in-memory `_FakeConn` substrate. `_rest_session(...)` factory builds valid `PlanSession` instances for diff tests.

10. **Bookkeeping** — `app.py` registers `plan_refresh_bp`; `CURRENT_STATE.md` last-shipped pointer + Layer 4 status + current focus + tests count updated; `CARRY_FORWARD.md` D-64 caller-side entry struck + 8 new NL parser tuning candidates section added + new manual §5.0 walkthrough scenario added; `Upstream_Implementation_Plan_v1.md` §4 new row `5.2.Caller-D64-Runtime`; this closing handoff.

Mid-session bug fix: first version of `_diff_sessions_against_parent` compared full `model_dump_json()` which includes the rebound `plan_version_id` + `session_id` fields — every session would appear as 'updated' in production because both identity fields change on every refresh. Fixed by introducing `_diff_signature(session)` which excludes `_DIFF_EXCLUDE_FIELDS = {"plan_version_id", "session_id"}`. Pinned in `test_diff_ignores_rebound_plan_version_id`.

`/plan` Trigger #5 (architectural alternatives) fired this session — exactly the trigger this session was scoped against. Trigger #1 (form copy) is iterative + Trigger #2 (NL parser prompt design) already cleared in the predecessor. Trigger #3 fires for the `plan_refresh_log` schema add (mechanical implementation of D-64 §7.1 spec contract — schema shape was already pre-ratified).

---

## 3. File-by-file edits

### 3.1 NEW `nl_parser.py` (~530 LOC)

- 14 D-decision compliance from NLParser_v1.md verbatim:
  - D1: model `claude-sonnet-4-6` (default; `_DEFAULT_MODEL`).
  - D2: extended_thinking_budget 0 (default; `_DEFAULT_THINKING_BUDGET`).
  - D3: forced tool-use single tool `record_parsed_intent`; `tool_choice` enforced in `_default_llm_caller`.
  - D4: tool schema mirrors `ParsedIntent` MINUS `raw_text`; 10 required fields per `build_record_parsed_intent_tool()`.
  - D5: middle-path injury disambig — encoded in system prompt rule 3 (verbatim from prompt body §5).
  - D6: strict closed-vocab locale matching — encoded in system prompt rule 3 + post-LLM `_enforce_closed_locale_vocab` transform per §8.2.
  - D7: driver-stamped `raw_text` — pydantic validate `tool_args | {"raw_text": input.nl_text}` after the LLM call returns.
  - D8: single capped retry on schema violation + `NLParserError("schema_violation")` raise on second-fail; network error → `NLParserError("network")` with no retry.
  - D9: classification-only voice in system prompt; no CLAUDE.md coaching voice.
  - D10: `temperature=0` default.
  - D11: prompt body markdown is the design doc; this module is the runtime per D11/D12 split.
  - D12: `NL_PARSER_PROMPT_VERSION = 1` constant lives here, not in the markdown.
  - D13: performance budget honored by sampling defaults (~1024 max tokens).
  - D14: smoke-eval harness lands in `tests/test_nl_parser_smoke.py`.
- Exports: `IntentParserInput`, `LLMCaller`, `NL_PARSER_PROMPT_VERSION`, `NLParserError`, `build_record_parsed_intent_tool`, `nl_parser_cache_key`, `parse_intent`.
- Spec deviation flagged in `nl_parser_cache_key` docstring: per NLParser_v1.md §10.1, `tier` is intentionally omitted from the cache key. Tier-mismatch ambiguity_notes (system prompt rule 7) could in principle differ per tier on identical NL text; the v1 cache leaks across tiers per the ratified design. Tracked as NL-2 tuning candidate in `CARRY_FORWARD.md`.

### 3.2 NEW `routes/plan_refresh.py` (~360 LOC)

- Module docstring documents the atomic-write contract per D-64 §6.2 + degraded-fallback contract per D-64 §5.4.
- Inline helpers:
  - `_build_layer4_cache()` — `Layer4Cache(PostgresCacheBackend(lambda: get_db()))` matches `routes/plan_create.py:91` precedent.
  - `_latest_plan_version(db, user_id)` — most recent `plan_versions` row for user, ordered by `(created_at DESC, id DESC)`. Returns None when athlete has no plan. Drives the empty-state CTA per D1.
  - `_load_plan_version(db, user_id, plan_version_id)` — single-row fetch scoped to user_id; cross-user defense.
  - `_athlete_locale_slugs(db, user_id)` — tuple of slugs from `locale_profiles` for the parser's `athlete_locales` input.
  - `_athlete_active_injury_summary(db, user_id)` — tuple of `"<body_part> — <description>"` strings from `injury_log WHERE status='Active'` for the parser's `athlete_active_injuries` input. Drops missing body_part rows; description fallback when empty.
  - `_parse_tier(form)` — accepts both `tier=T1` direct field + named submit buttons (`submit_t1` / `submit_t2` / `submit_t3`) per D2.
  - `_resolve_scope_dates(tier, today)` — T1 = (today, today+1), T2 = (today, today+6), T3 = (today, today+27) per D-64 §3.
  - `_orchestration_error_message(err)` — translation table for `OrchestrationError.code` → athlete-facing copy.
  - `_run_parser(db, user_id, *, nl_text, tier)` — runs `nl_parser.parse_intent`; on `NLParserError` returns `(_default_parsed_intent(), True)` for the route to flash the degraded-warning.
  - `_write_refresh_log(...)` — INSERT one `plan_refresh_log` row. Caller owns the transaction.
  - `_diff_signature(session)` + `_diff_sessions_against_parent(new, parent) -> (badges, sessions_changed)` — diff resolver excludes rebound `plan_version_id` + `session_id` per `_DIFF_EXCLUDE_FIELDS`.
  - `_latest_parent_for_refresh(db, user_id, plan_version_id)` — resolves the parent plan_version_id from `plan_refresh_log` (primary source) with fallback to "immediately-prior plan_versions row for this user" (defensive against pre-telemetry refreshes or test fixtures).
- 2 routes:
  - `refresh` GET: render `templates/plans/v2/refresh.html` (empty state OR tier picker).
  - `refresh` POST: parse tier → run parser → allocate plan_versions row → load prior window → orchestrate → persist → log → commit (success). On error: rollback → log INSERT in fresh sub-transaction → commit failure-row → flash + redirect.
  - `view_refresh` GET: load new plan version + sessions + parent sessions → compute diff + badges → render `templates/plans/v2/refresh_view.html`.

### 3.3 `init_db.py` — `plan_refresh_log` migration

- 1 CREATE TABLE entry in `_PG_MIGRATIONS` per D-64 §7.1 (matches the schema in the design doc verbatim except for the deferred `cap_overridden` + `reverted_at` columns per D4 + tracked-as-NL-6 deferral).
- 1 CREATE INDEX on `(user_id, triggered_at DESC)`.

### 3.4 NEW `templates/plans/v2/refresh.html`

- `{% extends 'base.html' %}` Bootstrap.
- Empty-state branch when `parent_plan is none`: alert + "Create a plan" button → `/plans/v2/new`.
- Tier-picker branch: parent-plan summary card + nl_context textarea (~500 char soft cap) + 3 named submit buttons + tip-text footer.
- CSRF token on the form.

### 3.5 NEW `templates/plans/v2/refresh_view.html`

- Plan header (Pattern badge + created_via badge + scope dates + session count + sessions-changed line + parent vN pointer).
- Per-date sessions grouped by `sessions_by_date` (list of `(date, [{session, badge}])` tuples).
- Per-session card with badge ('updated' yellow-border / 'new' green-border / 'unchanged' default), session header (kind + duration + intensity), coaching_intent + session_notes.

### 3.6 `app.py` — register `plan_refresh_bp`

- Single import line + single `register_blueprint` call after the existing `plan_create_bp` registration.

### 3.7 `layer4/cache.py` — extend `VALID_ENTRY_POINTS`

- Add `"nl_parser_parse_intent"` to `VALID_ENTRY_POINTS` superset (NOT `LAYER4_ENTRY_POINTS`) with a 5-line comment per the existing layer3a/layer3b precedent.

### 3.8 NEW `tests/test_nl_parser.py` (~600 LOC; 60 tests across 11 classes)

- Test classes:
  - `TestParseIntentFixtures` 16 — TS1..TS15 from NLParser_v1.md §11.1 + an extra whitespace-only short-circuit test.
  - `TestClosedLocaleVocabViolation` 1 — §11.2 closed-vocab violation post-LLM transform.
  - `TestParseIntentRetry` 3 — first-attempt-invalid-second-valid + second-failure-raises + zero-retries-on-first-failure.
  - `TestParseIntentNetworkError` 1 — caller exception propagates as `NLParserError("network")`.
  - `TestParseIntentCache` 3 — miss-then-hit + short-circuit-skips-cache + cache-round-trip-preserves.
  - `TestShortCircuitEmpty` 3 — empty returns default + whitespace-only returns default + nonempty returns None.
  - `TestNormalizeNLText` 4 — lowercase + collapse + empty + pure-whitespace.
  - `TestNLParserCacheKey` 5 — deterministic + whitespace-irrelevant + user-id-scoped + different-text-different-key + sha256-hex-shape.
  - `TestRenderUserPrompt` 10 — tier labels + unknown tier rejection + NL text in backtick block + empty/non-empty locales + empty/non-empty injuries + retry augmentation.
  - `TestEnforceClosedLocaleVocab` 5 — all-valid-passthrough + strips unknown + appends to existing ambiguity_notes + respects 240-char cap + empty-list-strips-all.
  - `TestBuildRecordParsedIntentTool` 7 — tool name + 10 required fields (raw_text excluded) + additionalProperties false + soft-signal enums + parser_confidence enum + ambiguity_notes nullable+cap + prompt-version constant.
  - `TestRawTextStamping` 2 — raw_text stamped verbatim (no normalization) + short-circuit raw_text stamped.

### 3.9 NEW `tests/test_nl_parser_smoke.py` (~150 LOC; 12 env-gated tests)

- `pytestmark = requires_anthropic_api_key` module-level marker; skips all 12 when `ANTHROPIC_API_KEY` unset.
- Fixtures use Andy-derived `_ANDY_LOCALES = ("home", "in_laws_mn", "lake_cabin")` + `_ANDY_ACTIVE_INJURIES = ("left wrist — painful + weak with wrist extension under load",)` (matches CLAUDE.md athlete context).
- Test classes: `TestCleanSignals` 4 / `TestInjuryDisambiguation` 3 / `TestLocaleVocab` 2 / `TestUpstreamTriggers` 2 / `TestEmptyShortCircuit` 1.
- Assertions are mixed strict (trigger flags, soft-signal enums) + allowlist-set (parser_confidence, fatigue intensity) to absorb minor Sonnet variance.

### 3.10 NEW `tests/test_routes_plan_refresh.py` (~450 LOC; 36 tests across 9 classes)

- Mirrors `tests/test_routes_plan_create.py` test-double pattern (`_FakeRow` / `_FakeCursor` / `_FakeConn` with queued responses + commits/rollbacks counters).
- `_rest_session(...)` factory builds valid `PlanSession` instances for diff-resolver tests (`kind='rest'` + `duration_min=0` + `rest_reason='planned_recovery'` is the lightest happy-path session).
- Test classes:
  - `TestParseTier` 6 — direct field + normalized + named submit + named-preferred-over-empty-field + unknown rejected + empty-form rejected.
  - `TestResolveScopeDates` 3 — T1/T2/T3 horizons.
  - `TestOrchestrationErrorMessage` 2 — known code + unknown fallback.
  - `TestLatestPlanVersion` 3 — dict on hit + None on miss + user_id scoping.
  - `TestAthleteLocaleSlugs` 3 — happy + empty + drops empty.
  - `TestAthleteActiveInjurySummary` 5 — body_part with description + without + drops missing body_part + SQL filters status='Active' + empty.
  - `TestRunParser` 2 — success path + parser error falls back to default.
  - `TestWriteRefreshLog` 3 — success INSERT shape + empty nl_text stored as null + failure row shape.
  - `TestDiffSessionsAgainstParent` 6 — unchanged + updated + new + mixed slots + session_index_in_day distinguishes + diff ignores rebound plan_version_id (PINNED — caught a real bug in v1 of the resolver).
  - `TestLatestParentForRefresh` 3 — uses refresh log when present + falls back to prior plan_versions row + returns None.

---

## 4. Code / tests

**Tests 1235 → 1331 (+96 net new across 3 NEW test files):**

- `tests/test_nl_parser.py` 60 tests
- `tests/test_nl_parser_smoke.py` 12 tests (env-gated; skip when `ANTHROPIC_API_KEY` unset)
- `tests/test_routes_plan_refresh.py` 36 tests

**Container-runnable subset 568 → 664 in ~1.0s.**

12 new env-gated smoke tests + 4 pre-existing Layer 3 SDK smoke tests = 16 total skipped when key unset. Default `pytest tests/` reads "1331 passed, 16 skipped" once the pre-existing `layer1`/`layer4` circular-import is resolved.

Run reproducer for the container-runnable subset:

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
                                tests/test_routes_plan_create.py \
                                tests/test_nl_parser.py \
                                tests/test_routes_plan_refresh.py \
                                tests/test_nl_parser_smoke.py
# 664 passed, 12 skipped in ~1.0s
```

**No-regression confirmation:** All 568 pre-existing container-subset tests pass unchanged. No edits to `layer4/`, `layer4/orchestrator.py`, repos, or any other shipped module (only `layer4/cache.py` extended `VALID_ENTRY_POINTS` with a new label — fully additive).

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + all 8+ predecessor handoffs §4).

---

## 5. Manual §5.0 verification steps

Forward-pointer for the next manual walkthrough pass:

**Step 1: `init_db.py` migration spot-check on Neon.** `\d plan_refresh_log` shows BIGSERIAL PK + user_id FK + tier CHECK in (T1, T2, T3) + nl_text TEXT nullable + parsed_intent JSONB + layers_run TEXT[] NOT NULL DEFAULT '{}' + scope_start_date/scope_end_date DATE + plan_version_id_before/after BIGINT FK to plan_versions + duration_ms INTEGER + sessions_changed INTEGER + success BOOLEAN NOT NULL + failure_reason TEXT + created_at + index on `(user_id, triggered_at DESC)`.

**Step 2: D-64 empty-state.** Fresh athlete with no `plan_versions` rows, navigate to `/plans/v2/refresh`, confirm the page renders an empty-state alert ("You don't have a plan yet") + a "Create a plan" button linking to `/plans/v2/new`; no tier buttons rendered.

**Step 3: D-64 happy-path against Andy's PGE 2026 context.** Assumes plan-create walkthrough completed first so Andy has at least one `plan_versions` row. Log in, navigate to `/plans/v2/refresh`, confirm the page renders the parent-plan summary card (vN + created_via + Pattern + scope dates) + an nl_context textarea (~500 char soft cap) + 3 named submit buttons; type "I'm tired" + click "Refresh next 2 days" (T1); confirm: (a) a new `plan_versions` row lands with `created_via='plan_refresh_t1'` + `pattern='B'` + scope_start=today + scope_end=today+1; (b) NL parser fires against real Sonnet 4.6 returning `fatigue_signal='tired'` + all flags FALSE + `parser_confidence='high'`; (c) `orchestrate_plan_refresh` fires with `tier='T1'` + the parsed_intent threaded + parent plan_version_id + prior_plan_session_window from yesterday + day-before; (d) `plan_sessions` rows land for [today, today+1]; (e) `plan_refresh_log` row lands with `success=TRUE` + `parsed_intent` JSONB populated + `layers_run={'3A','3B','Layer4'}` + `sessions_changed` count + `duration_ms` ~1500-3000ms; (f) page redirects to `/plans/v2/refresh/<new_plan_version_id>` rendering the 2-day window with 'updated' / 'unchanged' / 'new' badges + per-card border highlighting per D-64 §9; (g) re-run the same refresh with the same nl_text — confirm parser cache hits via `plan_refresh_log.duration_ms` shrinking + no second NL parser cost; (h) NL parser cache row visible in `layer4_cache WHERE entry_point='nl_parser_parse_intent' AND user_id=<andy>`. Real-LLM cost: ~$0.30-$0.50 per T1 refresh (parser ~$0.003 + 3A + 3B + Layer 4 Pattern B cascade).

**Step 4: D-64 degraded-parser path.** Temporarily clear `ANTHROPIC_API_KEY` on Vercel (or simulate parser failure another way), POST a T1 refresh from Andy's session; confirm: (a) the route still completes successfully (degraded fallback per D-64 §5.4); (b) `plan_refresh_log.failure_reason='parser_degraded'` + `success=TRUE`; (c) `parsed_intent` row reflects `_default_parsed_intent()` shape (`parser_confidence='low'` + `ambiguity_notes='Parser unavailable; running default cascade only.'`); (d) the flash warning surfaces on the diff view ("NL parser unavailable — refresh ran on the default cascade only."). Restore the env var after the test.

Captured in `CARRY_FORWARD.md` manual walkthrough section.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Dashboard CTAs for `/workouts/build` + `/plans/v2/new` + `/plans/v2/refresh`.** All 3 caller-side routes are now E2E-reachable but only via direct URL navigation; D-63 §3.1 + D-64 §4.1 both spec dashboard CTA cards. ~1-2 files (`templates/dashboard.html` edit + maybe a small helper in `routes/dashboard.py`). Pair with the manual §5.0 walkthrough so Andy can E2E-verify all 3 routes from the dashboard.

**`/plan` gate sequence:** Trigger #1 (form copy on the 3 CTA cards) + maybe Trigger #5 (card placement on the dashboard layout — top vs bottom, single-row vs separate-rows).

### 6.2 Alternative pivots

- **Log-this slice + D-63 T1 plan-check hook** — pairs with D-64 caller-side (already shipped). Adds `is_ad_hoc` + `ad_hoc_request_payload` + `ad_hoc_suggestion_id` extensions to `cardio_log` + `training_log` per D-63 §5.1/§5.2; wires `[Log this workout]` button on `templates/workouts/suggestion_view.html` → POST `/workouts/suggestions/<id>/log` allocates a cardio_log/training_log row + flips suggestion status to `logged` + surfaces the T1 refresh CTA (which fires D-64 with NL context auto-filled per §5.4). ~5-7 files.
- **NL parser frequency caps per D-64 §8** — deferred this session per D4. Specifies soft caps + override: T1 ≤3/24h, T2 ≤1/48h, T3 ≤1/7d. Server-side count against `plan_refresh_log` rows within the window; modal-confirm UI when exceeded; `cap_overridden=TRUE` logged. ~3-4 files including the `cap_overridden` column add + a `/plans/v2/refresh/confirm` intermediate page.
- **NL parser smoke-eval harness expansion + Haiku 4.5 migration eval per NL-1** — ~5-6 files; need ~20-30 hand-labeled fixtures + a Haiku-vs-Sonnet agreement comparison harness. Cost gain ~10× ($0.0003-$0.0005/call vs $0.003-$0.005/call) if Haiku holds ≥95% agreement.
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1+#3+#5).
- **Layer 3A + 3B caching policy at orchestrator level** — all 4 entry points call `llm_layer3a_athlete_state` + `llm_layer3b_goal_timeline_viability` uncached. With 4 entry points sharing user-scoped 3A outputs, the orchestrator-level cache is near-load-bearing. ~4-6 files.
- **Manual §5.0 walkthrough** of D-64 + D-63 + plan_create E2E on Neon (real-LLM ~$1.00 per pass across the 3 routes).
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — ~1-2 files; doc-sweep nit from form-refresh C.
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Real-LLM Layer 4 regression** parity to plan_refresh (~$0.30-$0.50 per cold synthesis on Pattern B + ~$0.50-$1.00 on Pattern A).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_CallerSide_D64_Runtime_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.
6. `aidstation-sources/prompts/NLParser_v1.md` — the prompt body now wired into the runtime.
7. `aidstation-sources/Plan_Refresh_D64_Design_v1.md` — design contract still relevant.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | No-prior-plan policy = GET hides tier buttons + renders empty-state CTA to `/plans/v2/new`; POST defensive-redirect when parent_plan is None | Andy ratified at AskUserQuestion gate | Andy's framing: "the options for T1/2/3 shouldn't even be visible to a user if they do not have an active plan." Honors `orchestrate_plan_refresh`'s required `plan_version_id_parent` kwarg cleanly without UI confusion. D-64 §3.3's "T3 as initial-plan-gen" promise can be satisfied later by the dashboard CTA layer routing T3-without-plan to plan_create. |
| **D2** | Tier UX = 3 named submit buttons (one-click flow) | Andy | Picked over radio + dropdown. Buttons named `submit_t1` / `submit_t2` / `submit_t3`; `_parse_tier` accepts both `tier=T1` direct field + named-submit. Lower friction than radio + click-submit. |
| **D3** | Redirect target = NEW `/plans/v2/refresh/<id>` diff view with 'updated' / 'new' / 'unchanged' badges per D-64 §9 | Andy | Honors D-64 §9 diff-visibility promise in v1. Diff signature excludes rebound `plan_version_id` + `session_id` identity fields so structurally identical sessions across versions compare as 'unchanged' (caught a real bug in v1 of the resolver; pinned via test). |
| **D4** | plan_refresh_log telemetry per D-64 §7.1 shipped; frequency caps per D-64 §8 deferred | Andy | Caps are anti-cohort guard, N=1 athlete doesn't warrant the modal-confirm UX yet. `cap_overridden` + `reverted_at` columns deferred to the caps follow-on. Telemetry write is INSERT-once-post-orchestrate inside the same transaction (success) or in a fresh sub-transaction (failure) so the failure-row log always lands even when the orchestrator rolled back the plan_versions allocation. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| NEW `nl_parser.py` exists | ✅ `ls nl_parser.py` |
| NEW `routes/plan_refresh.py` exists | ✅ `ls routes/plan_refresh.py` |
| NEW `templates/plans/v2/refresh.html` exists | ✅ `ls templates/plans/v2/refresh.html` |
| NEW `templates/plans/v2/refresh_view.html` exists | ✅ `ls templates/plans/v2/refresh_view.html` |
| NEW `tests/test_nl_parser.py` exists | ✅ `ls tests/test_nl_parser.py` |
| NEW `tests/test_nl_parser_smoke.py` exists | ✅ `ls tests/test_nl_parser_smoke.py` |
| NEW `tests/test_routes_plan_refresh.py` exists | ✅ `ls tests/test_routes_plan_refresh.py` |
| `init_db.py` `_PG_MIGRATIONS` includes `plan_refresh_log` CREATE TABLE | ✅ `grep "CREATE TABLE IF NOT EXISTS plan_refresh_log" init_db.py` |
| `init_db.py` `_PG_MIGRATIONS` includes `plan_refresh_log_user_triggered_idx` | ✅ `grep "plan_refresh_log_user_triggered_idx" init_db.py` |
| `app.py` imports + registers `plan_refresh_bp` | ✅ `grep "plan_refresh_bp" app.py` returns 2 lines (import + register) |
| `layer4/cache.py` `VALID_ENTRY_POINTS` includes `"nl_parser_parse_intent"` | ✅ `grep nl_parser_parse_intent layer4/cache.py` |
| `nl_parser.py` exports `NL_PARSER_PROMPT_VERSION = 1` | ✅ `grep "NL_PARSER_PROMPT_VERSION = 1" nl_parser.py` |
| `nl_parser.py` `build_record_parsed_intent_tool` mirrors 10 emit-fields (sans raw_text) | ✅ grep for the 10 field names in the schema; `raw_text` absent |
| Container-runnable subset 568 → 664 (+96 net new) | ✅ pytest run returns "664 passed, 12 skipped" |
| Tests 1235 → 1331 (+96 net new across 3 NEW test files) | ✅ Counted via new test files: 60 + 12 + 36 |
| 12 new NL parser smoke tests skip cleanly when ANTHROPIC_API_KEY unset | ✅ `pytest tests/test_nl_parser_smoke.py -q` returns "12 skipped" |
| `Upstream_Implementation_Plan_v1.md` §4 has new row `5.2.Caller-D64-Runtime` → ✅ Shipped 2026-05-21 | ✅ `grep "5.2.Caller-D64-Runtime" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 caller-side D-64 Runtime handoff | ✅ |
| `CURRENT_STATE.md` tests count flipped to 1331 + 16 skipped | ✅ |
| `CURRENT_STATE.md` Layer 4 status row updated to reflect runtime + route landing (all 3 caller-side routes E2E-reachable) | ✅ |
| `CARRY_FORWARD.md` D-64 caller-side entry struck (✅ Shipped) + new manual §5.0 walkthrough scenario added + NL parser tuning-candidate section added | ✅ |

---

## 9. Files shipped this session

**Substantive (8 files; ceiling break ratified per scope-selection AskUserQuestion gate):**

1. NEW `nl_parser.py` (~530 LOC) — D-64 NL parser runtime per NLParser_v1.md.
2. NEW `routes/plan_refresh.py` (~360 LOC) — Blueprint `/plans/v2/refresh/*` with atomic compose-and-commit per D-64 §6.2.
3. `init_db.py` — 1 new migration in `_PG_MIGRATIONS` for `plan_refresh_log` per D-64 §7.1 + 1 index.
4. NEW `templates/plans/v2/refresh.html` — 3-button tier picker per D-64 §4.1 + empty-state CTA per D1.
5. NEW `templates/plans/v2/refresh_view.html` — diff view with updated/new/unchanged badges per D-64 §9 + D3.
6. NEW `tests/test_nl_parser.py` (~600 LOC) — 60 stub-LLM unit tests across 11 classes.
7. NEW `tests/test_nl_parser_smoke.py` (~150 LOC) — 12 env-gated real-LLM smoke tests against Sonnet 4.6.
8. NEW `tests/test_routes_plan_refresh.py` (~450 LOC) — 36 helper-level route tests across 9 classes.

**Bookkeeping (5 files):**

9. MODIFIED `app.py` — registers `plan_refresh_bp`.
10. MODIFIED `layer4/cache.py` — extends `VALID_ENTRY_POINTS` superset with `"nl_parser_parse_intent"`.
11. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + Layer 4 status + current focus + tests count.
12. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — D-64 caller-side entry struck + new manual §5.0 walkthrough + NL parser tuning-candidate section.
13. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row `5.2.Caller-D64-Runtime`.
14. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_CallerSide_D64_Runtime_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- "D-64 caller-side route + NL parser runtime" entry → ✅ Shipped 2026-05-21 (`claude/implement-caller-routes-PciAJ`).
- New "D-64 NL parser tuning candidates" section with 8 follow-on items (NL-1 Haiku migration eval / NL-2 tier-conditional cache key / NL-3 athlete-level invalidation / NL-4 out-of-vocab auto-add CTA / NL-5 tier-mismatch v2 policy / NL-6 frequency caps per D-64 §8 / NL-7 dashboard CTA / NL-8 telemetry analytics surface).
- New manual §5.0 walkthrough scenario for D-64 (4 steps: migration spot-check + empty-state + happy-path T1 with Andy's PGE 2026 + degraded-parser path).

**Phase 5.2 caller-side arc complete; all 3 of 3 Layer 4 entry-point caller-side routes now E2E-reachable from v1 UI (single_session via `/workouts/build` + plan_create via `/plans/v2/new` + plan_refresh via `/plans/v2/refresh`). The D-64 closing handoff named "log-this slice + D-63 T1 plan-check hook" as the next-up alternative to dashboard CTAs; both pair naturally with the D-64 refresh route shipped this session.**

---

**End of handoff.**
