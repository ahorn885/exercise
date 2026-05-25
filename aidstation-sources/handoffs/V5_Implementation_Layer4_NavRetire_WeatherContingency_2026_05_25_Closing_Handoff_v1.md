# Layer 4 — `navigation_required` retirement + climate-normals weather contingency — Closing Handoff

**Session:** Follow-on from the Layer4 long-session-day handoff §6.2 open pivot ("`navigation_required` → `race_events` column"). Andy redirected the slice at the AskUserQuestion gate: **don't promote `navigation_required`; remove it entirely. Drop the nav contingency. Keep the weather contingency, but source expected weather from the race location + date (not terrain).** Designed + gated across multiple AskUserQuestion rounds (Trigger #1 prompt-body mod + Trigger #3 cross-layer surface change), then implemented as **one combined slice at Andy's explicit instruction** (the ~12-file ceiling/refactor-mix risk was surfaced and accepted).
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_Layer4_LongSessionDay_PlanGenConsumer_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/v5-layer4-closing-handoff-6zf9s`
**Status:** Implementation complete on-branch. 7 code + 3 spec + 4 test files. Full container suite green (**1796 passed / 16 skipped**). **No schema change → no deploy owed** (the A1/A2/Slice-C owed Neon deploys are unchanged by this slice). Draft PR opened.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the predecessor (Layer4 long-session-day) handoff: all `[1]` file-existence checks ✅; spot-checked every §8 anchor on-disk (`per_phase._format_daily_windows_schedule` @702/938, plan_refresh T2/T3 imports, `Layer4_Spec.md` §114, `TestDailyWindowsSchedule`) — all present, no drift. PR #163 confirmed merged on-branch.

Reconciled the `navigation_required` surface before designing: it was an **unwired** `bool | None` threaded through Layer 2A (`_resolve_conditional` D-015 auto-in/out) + Layer 3B (prompt §H.2 + cache slot), but the orchestrator never sourced a value (`orchestrator.py:266/330` omit the kwarg) — so it was always `None` at runtime. A1 had parked the removed `nav`/`weather` validator anchors for "a future slice keyed on `navigation_required` + Layer 2B terrain."

Test env: fresh web container; `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

---

## 2. Session narrative + gate picks

The handoff named "promote `navigation_required` to a `race_events` column" as the next pivot. At the gate Andy:
1. picked the pivot, then **inverted it** — "we don't need nav contingencies. remove that concept entirely. weather contingencies, keep — but source the expected weather from race location + date rather than terrain."
2. on the weather source fork, picked **real climate-normals data (Open-Meteo)** over LLM-intrinsic reasoning.
3. on the nav-code fork, picked **remove the existing nav code entirely** (not just leave it dormant).
4. on sizing, picked **one combined slice** despite the surfaced ceiling/refactor-mix risk.

So the slice became two workstreams: (A) rip out `navigation_required` end-to-end; (B) add a climate-normals weather feed + make the weather contingency universal.

---

## 3. File-by-file edits

### Workstream A — `navigation_required` retired (cross-layer)

#### 3.1 `layer2a/builder.py`
- Removed the `navigation_required` param from `_resolve_conditional`, `_render_rationale`, `_emit_coaching_flags`, and the public entry `q_layer2a_discipline_classifier_payload` (+ its 3 call-throughs).
- `_resolve_conditional`: dropped the `_NAV_DISCIPLINE_ID` race-rule branch → the navigation discipline (D-015) now falls through to `prompt_required` (athlete opt-in) like any `*Conditional`.
- `_render_rationale`: dropped the nav excluded/auto-in text branches.
- `_emit_coaching_flags`: removed the entire §8.2 `conditional_auto_resolved` block (it was nav-only; with nav gone, `race_rule_auto_in`/`race_rule_auto_out` are never produced, so the flag is dead).
- **Kept** `_NAV_DISCIPLINE_ID = "D-015"` — it still drives `sleep_deprivation_relevant` (line ~613), which is a separate concern from the retired input.

#### 3.2 `layer4/context.py`
- `Layer2ADiscipline.conditional_resolution` Literal trimmed `["race_rule_auto_in","race_rule_auto_out","athlete_opt_in"] | None` → `Literal["athlete_opt_in"] | None` (the auto-resolution values are no longer produced).

#### 3.3 `layer3b/builder.py`
- Removed `navigation_required` from `_render_block_2_goal_context` (+ its `- navigation_required: …` prompt line), `_build_prep_dict` (+ the `h2.navigation_required` evidence-basis key), `_render_user_prompt`, and the public `llm_layer3b_goal_timeline_viability` (+ both threaded call sites).

#### 3.4 `layer3b/cached_wrapper.py`
- Removed the `navigation_required` kwarg, its `section_h2_kwargs` entry (cache-key input), the underlying call pass-through, and the docstring mention.

### Workstream B — climate-normals weather contingency

#### 3.5 `weather_client.py` (NEW)
- `get_expected_conditions(lat, lng, event_date, *, today, fetcher) -> ExpectedConditions | None`. Queries Open-Meteo's open archive API (no key) for a ±3-day window around the event's calendar date across the last 5 years; aggregates mean high/low + wet-day probability (precip ≥ 1mm). **Best-effort:** missing coords / network error / empty sample → `None`. `fetcher` is dependency-injected (tests pass a fake; default does a live `requests.get` with a 6s timeout). `ExpectedConditions.summary_line()` renders the athlete-facing climate sentence.

#### 3.6 `layer4/race_week_brief.py`
- Import `from weather_client import ExpectedConditions, Fetcher, get_expected_conditions`.
- `llm_layer4_race_week_brief`: new `weather_fetcher: Fetcher | None = None` kwarg; fetches `expected_conditions` once (from `race_event_payload.event_locale_lat/lng + event_date`) before the retry loop; passes it into `_render_user_prompt`. No-op (None) when the race has no coords → existing tests stay network-free.
- `_render_user_prompt`: new `expected_conditions` param; renders an `## Expected conditions` section (climate summary + "anchor the weather contingency to these normals; historical, not a forecast") when present.
- `SYSTEM_PROMPT`: D6 anchor line rewritten — **weather moved to the universal set**, `nav` dropped, `sleep-dep` re-scoped to ultra+multi-day; added an explicit "weather contingency always required; anchor to the `## Expected conditions` block when present, else reason from location+date" paragraph.

#### 3.7 `layer4/validator.py`
- Rule 18 `_CONTINGENCY_ANCHORS_PER_FORMAT`: added `"weather"` to **all three** format tuples (universal). Replaced the A1 nav/weather-deferral comment block with the new rationale (weather universal; nav removed with `navigation_required`).

### Specs (3)
- **3.8 `Layer2A_Spec.md`** — removed the `navigation_required` param from the signature + parameter table; rewrote §5.3 (conditionals → prompt_required; added a "race-rule auto-resolution RETIRED" note); trimmed the §6 `conditional_resolution` comment; retired §8.2 (`conditional_auto_resolved`); removed `navigation_required` from the §9 cache key; updated §13.1 + retired §13.3 test scenarios.
- **3.9 `Layer3_3B_Spec.md`** — §H.2 Block-2 input list: noted the `navigation_required` input retired 2026-05-25.
- **3.10 `Layer4_Spec.md`** — §5.4 Rule-18 row: weather marked universal + sourced from `weather_client.get_expected_conditions`; nav anchor noted removed.

### Tests (4)
- **`tests/test_weather_client.py`** (NEW) — aggregation (means + wet-day %), 5-year/±3-day window query shape, graceful `None` (missing coords / all-fail / empty / partial-years), `summary_line` rendering.
- **`tests/test_layer2a.py`** — removed all `navigation_required=` kwargs; rewrote the AR baseline (`test_56h_ar_baseline_disciplines`: D-015 → prompt_required, hitl True, no `conditional_auto_resolved`); re-aimed `test_conditional_discipline_is_prompt_required` + the subset-filter `conditional_resolution` assertion at `athlete_opt_in`; updated module docstring.
- **`tests/test_layer3b_builder.py`** — removed all `navigation_required=` kwargs from `_build_prep_dict` / `_render_user_prompt` calls.
- **`tests/test_layer4_race_week_brief.py`** — 2 new render tests (`## Expected conditions` present when passed / absent when None).
- **`tests/test_layer4_validator.py`** — added `weather` to the no-fire fixture; new `test_contingency_anchor_weather_universal_warns_when_missing` (single-day, weather omitted → 1 warning).

---

## 4. Code / tests

Container suite: **1796 passed / 16 skipped** (`/tmp/venv`). Baseline (predecessor) was 1786. All 46 suites collect with no errors. No LLM run in-container (16 skipped = NL-parser + Layer-3 SDK smoke when `ANTHROPIC_API_KEY` unset). `weather_client` exercised only via injected fake fetchers — **no network touched in tests** (all fixtures use None coords).

Eyeballed `weather_client.get_expected_conditions` against a fake Open-Meteo payload (Nerstrand-shaped lat/lng, Jul 17): correct 5-year/±3-day window params + aggregation + summary line.

---

## 5. Manual §5.0 verification steps (owed — Andy's hands)

Appended to `CARRY_FORWARD.md`:
1. **Weather contingency (real LLM + live Open-Meteo):** with `ANTHROPIC_API_KEY` set, run a `race_week_brief` for a target race that has Mapbox-anchored coords (e.g. PGE 2026, Nerstrand MN, Jul 17). Confirm (a) the rendered prompt carries an `## Expected conditions` block with plausible MN-July normals, (b) the brief's `contingencies` includes a weather contingency anchored to those numbers, (c) the validator emits no `contingency_anchor_category_missing_weather`. Then run a race with **no** coords and confirm the brief still includes a weather contingency (intrinsic reasoning) + the section is absent.
2. **Live Open-Meteo reachability:** confirm the Vercel egress network policy permits `archive-api.open-meteo.com`. If blocked, the brief silently degrades to intrinsic reasoning (no error) — acceptable, but the climate grounding won't fire.

**No migration, no deploy owed for this slice** (no schema change; live external fetch only).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Run the owed Neon deploys** (unchanged by this slice; still Andy's hands): public-schema `python init_db.py` (A1 race_events remap + A2 `aid_stations` drop + Slice-C §G drops + `daily_availability_windows` 720 bump) **plus** `etl/sources/run_owed_layer0_migrations.sql` (PR #156 `primary_movement` HARD Layer-2A prereq). Then the accumulated manual §5.0 walks (incl. this slice's weather walk).

### 6.2 Open pivots
- **Climate normals → cited/grounded enrichment (optional follow-on)** — this slice ships the LLM-intrinsic + climate-normals hybrid; a future slice could surface the normals as a structured `RaceWeekBrief` field (not just prompt context) for the UI + Layer 5 conditions advisor, and/or add a closer-in forecast refresh as `days_to_event` shrinks.
- **Spec narrative sweep** — per-layer specs still cite pre-R6 discipline ids in prose; the Layer2A_Spec §13 scenarios are now partially retired-noted but the broader §13 fixture list still references the old auto-resolution world. Doc-only; no gate.
- **Manual §5.0 real-LLM walk** — accumulated scenarios in `CARRY_FORWARD.md`.

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules (read first).
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep; reconcile any ❌ first.
6. **Test env:** deps not pre-installed in fresh web containers — `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | **Retire `navigation_required` entirely** (don't promote it to a column) | Andy at gate | Nav contingencies aren't wanted; the input's only live consumer would have been the nav contingency anchor + a D-015 auto-resolution that was never wired. |
| 2 | **Keep D-015 as a discipline + keep `_NAV_DISCIPLINE_ID`** (only remove the `navigation_required` input) | this agent (within scope) | `_NAV_DISCIPLINE_ID` independently drives `sleep_deprivation_relevant`; D-015 is a Layer 0 discipline. Removal scope = the input + its auto-resolution, not the discipline. |
| 3 | **Weather contingency is universal** (added to all 3 race_format tuples) | this agent (within scope) | Every race is outdoors at a known location/date → a weather contingency always applies. Cleaner than the A1 terrain-gated design (which had no clean exposure signal). |
| 4 | **Source expected weather from climate normals (Open-Meteo), not terrain** | Andy at gate | Location + date is a more grounded signal than terrain exposure. Climate normals (not a point forecast) because the brief fires ~14 days out. |
| 5 | **Best-effort fetch, graceful degrade to intrinsic reasoning** | this agent | Keeps a network dependency out of the critical path: missing coords / blocked egress / API failure → the synthesizer still writes a weather contingency from location+date. Mirrors the existing `coaching.py` wttr.in pattern. |
| 6 | **Fetch inside the driver via injectable fetcher** (not threaded through the cache wrapper) | this agent | The brief output is deterministic from race location+date, already in the cache key via `race_event_id`; the fetch only runs on cache miss. Injectable fetcher keeps tests network-free. |
| 7 | **One combined slice despite the ~12-file ceiling + refactor-plus-feature mix** | Andy at gate | Ceiling/risk surfaced explicitly; Andy accepted. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -rn navigation_required` in code (non-test) → only the validator explanatory comment | ✅ |
| `layer2a/builder.py` — `navigation_required` gone; `_NAV_DISCIPLINE_ID` retained for sleep-dep | ✅ |
| `layer4/context.py` — `conditional_resolution: Literal["athlete_opt_in"] \| None` | ✅ |
| `layer3b/builder.py` + `cached_wrapper.py` — `navigation_required` gone | ✅ |
| `weather_client.py` — `get_expected_conditions` + `ExpectedConditions` defined | ✅ |
| `race_week_brief.py` — imports weather_client; fetches `expected_conditions`; renders `## Expected conditions`; SYSTEM_PROMPT weather-universal + nav dropped | ✅ |
| `validator.py` — `"weather"` in all 3 `_CONTINGENCY_ANCHORS_PER_FORMAT` tuples | ✅ |
| `Layer2A_Spec.md` / `Layer3_3B_Spec.md` / `Layer4_Spec.md` updated | ✅ |
| `tests/test_weather_client.py` green | ✅ |
| Full suite | ✅ 1796 passed / 16 skipped (`/tmp/venv`) |
| `init_db.py` untouched → no schema change → no deploy owed | ✅ |
| Working tree: only the intended files | ✅ git status |

---

## 9. Files shipped this session

**Code (7):** `layer2a/builder.py`, `layer3b/builder.py`, `layer3b/cached_wrapper.py`, `layer4/context.py`, `layer4/race_week_brief.py`, `layer4/validator.py`, `weather_client.py` (new).
**Specs (3):** `aidstation-sources/Layer2A_Spec.md`, `Layer3_3B_Spec.md`, `Layer4_Spec.md`.
**Tests (4):** `tests/test_weather_client.py` (new), `test_layer2a.py`, `test_layer3b_builder.py`, `test_layer4_race_week_brief.py`, `test_layer4_validator.py`.
**Bookkeeping:** this handoff; `CURRENT_STATE.md` pointer; `CARRY_FORWARD.md` §5.0 entry.

---

## 10. Carry-forward updates

- New Manual §5.0 entry (weather contingency real-LLM + live Open-Meteo walk) appended to `CARRY_FORWARD.md`.
- The owed Neon deploys (A1/A2/Slice-C public schema + layer0 runner) are **unchanged** by this slice — no new deploy debt.
- `navigation_required` is fully retired; any future "navigation as a training concern" work starts clean (D-015 remains a plain conditional discipline).

---

**End of handoff.**
