# V5 Implementation — D-66 Layer 3B Caller-Side Rewire (Scope C) Closing Handoff

**Session:** Single chat. Scope: D-66 Layer 3B Scope C per the predecessor handoff `V5_Implementation_D66_Layer3B_Rewire_Scope_B_Closing_Handoff_v1.md` §6.1 — wire the partial-update Layer 4 cache invalidation hooks per `Race_Events_D66_Design_v1.md` §7.4 + §9 into the writer-side surfaces (`routes/race_events.py` 10 routes + `routes/onboarding.py` 3 race-event routes). Closes the D-66 family architectural contract: race-event writes now correctly evict the Layer 4 cache entries that consume the changed fields per the §9 invalidation matrix.

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_D66_Layer3B_Rewire_Scope_B_Closing_Handoff_v1.md` (Scope B shipped 2026-05-18 earlier same day; PR #87 merged via `a88999f`).

**Branch:** `claude/v5-layer3b-rewire-WsOvi` (harness-pinned for this session — name carries over from the harness-assigned Scope A/B branch family even though Scope A's PR #86 + Scope B's PR #87 both already merged to main; precedent: harness names mismatched with scope across the entire D-66 family).

**Status:** 🟢 8 files (4 substantive code + 1 test + 3 bookkeeping). Combined `tests/` 736 → 749 (13 new tests in `tests/test_race_events_invalidation.py`). **D-66 family architecturally complete.** D-66 status flipped 🟢 Profile-tab UI + onboarding §H.2/§H.4 + nudges + Layer 3B Scope A + Scope B shipped → 🟢 Profile-tab UI + onboarding §H.2/§H.4 + nudges + Layer 3B Scope A + Scope B + Scope C shipped. **D-72 (i) trigger partially advances** (invalidation hooks wired; 3B read-path swap awaits Layer 4 orchestrator). D-72 type-alignment + manual §5.0 walkthrough (35 scenarios total now) remain as carry-forwards.

**Over the 5-file ceiling by 3** — precedent across the D-66 family.

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| D-66 Layer 3B Scope B shipped on main per predecessor handoff | `git log --oneline -10` | ✅ `a88999f` (merge PR #87) + `078f855` (Scope B commit) |
| `init_db.py` PG_SCHEMA + catch-up CREATE no longer carry legacy columns | grep `target_event_name\|target_event_date` init_db.py | ✅ shows only the retirement-marker comment + 2 DROP COLUMN appends |
| `DATABASE.md:310-318` athlete_profile bullet trimmed with retirement-marker | inspection | ✅ verbatim per Scope B handoff §3.2 |
| `Project_Backlog_v58.md` exists; v57 retained | `ls` | ✅ both present |
| `CLAUDE.md` line 52 last-shipped narrative bumped to Scope B + line 254 backlog ref bumped to v58 | grep | ✅ |
| Working tree clean on `claude/v5-layer3b-rewire-WsOvi` | `git status` | ✅ |

**Rule #9 reconciliation:** all predecessor handoff claims match on-disk state. No drift. Proceeded directly to scope pick.

**Environmental drift surfaced (not code drift):** same recurrence as predecessors — the fresh container started without `pytest`/`pydantic`/`flask`/etc. installed in the uv-isolated pytest interpreter. Resolved by re-running `uv tool install --force pytest --with pydantic --with flask --with anthropic --with psycopg2-binary --with bcrypt --with zxcvbn --with openpyxl --with garth --with garminconnect --with fit-tool --with requests --with Flask-WTF --with Flask-Limiter --with pydantic-settings --with logfire`. Baseline 736 passed before any edits; all 749 passed at end.

---

## 2. Session narrative — D-66 Layer 3B Scope C

Andy opened with the URL to the Scope B closing handoff + "lets work." Followed the operating model — read CLAUDE.md fully via the system-reminder load, ran Rule #9 verification (all green), surfaced state + the architect-recommended next-forward-move set from the predecessor handoff §6.1.

### 2.1 Scope pick (1-question gate)

Q1 (2026-05-18, 1-question gate): session scope. Andy picked **Scope C — partial-update invalidation hooks** over D-72 type-alignment, Layer 4 Step 7 live LLM, and manual §5.0 walkthrough. The predecessor handoff §6.1 recommended Scope C next as "closes the D-66 family completely + may discharge D-72 (i)." Scope C fires Trigger #5 (cross-layer schema change is the invalidation contract surface) + Trigger #7 (new partial-update invalidation rule per design §9) + Trigger #8 (architectural alternatives for the glue surface) so it needs a /plan-mode gate before any edits.

### 2.2 Reconnaissance (5 surfaces per CLAUDE.md §6.3 operating notes)

Read the 5 surfaces in parallel:
- `Race_Events_D66_Design_v1.md` §7.4 + §9 — the 9-row invalidation matrix.
- `layer4/cache.py` — `Layer4Cache` facade with `invalidate_user(uid, layer, entry_points)` + `invalidate_entry_point(entry_point, layer, user_id)` primitives.
- `layer4/cache_invalidation.py` — `evict_on_layer_change(cache, uid, layer)` keyed on upstream-layer name + `_EVICTION_POLICY` dict; `layer3b` policy = `_NON_SINGLE_SESSION` = plan_create + plan_refresh + race_week_brief (= "periodization-grade").
- `routes/race_events.py` — 10 writer routes.
- `routes/onboarding.py` — 4 race-event-relevant writer routes (target_race_save + route_locales_add/delete + skip/continue handlers that write nudges only).

Found infrastructure complete (Step 5 cache layer shipped 2026-05-18) + zero call sites of the eviction primitives outside `layer4/` and `tests/`. The cache exists but no writer ever evicts.

### 2.3 §9 matrix → 3 helpers

Mapped the design §9 matrix's 9 row-types to 3 narrowest-cut Layer 4 cache evictions reusing existing primitives:

| §9 matrix row | Helper | Underlying eviction | Policy |
|---|---|---|---|
| Target-flag flip TRUE→FALSE; FALSE→TRUE on another row; target-row `event_date` change; target-row `race_format` change; target-row deletion | `evict_on_target_event_periodization_change(db, uid)` | `evict_on_layer_change(cache, uid, 'layer3b')` | `_NON_SINGLE_SESSION` = plan_create + plan_refresh + race_week_brief |
| Target-row `distance_km`/`total_elevation_gain_m`/`race_rules_summary`/`mandatory_gear_text`/`notes` change; route_locales INSERT/UPDATE/DELETE on target race; route_locale_equipment INSERT/UPDATE/DELETE on target race | `evict_on_target_event_brief_field_change(db, uid)` | `cache.invalidate_entry_point('race_week_brief', layer='race_events_brief_field', user_id=user_id)` | race_week_brief only |
| Target-row `event_locale_id` change | `evict_on_target_event_locale_change(db, uid)` | `evict_on_layer_change(cache, uid, 'layer2c')` | `_ALL_ENTRY_POINTS` |
| Any change on a non-target race_events row | (no helper — writer skips the call) | No invalidation | — |

The periodization-grade helper reuses `evict_on_layer_change(cache, uid, 'layer3b')` because target-flag flips + event_date/race_format changes change Layer 3B's input set semantically; the policy is symmetric.

### 2.4 Plan-mode gate (Trigger #5/#7/#8 routing)

Composed a 4-option plan with concrete rationale:
- **Option 1 (recommended):** Full Scope C — new top-level `race_events_invalidation.py` (3 helpers + injectable cache builder) + all 10 race_events.py writer sites + all 3 onboarding.py writer sites + tests. 7-8 files. D-66 family closes. Single contract surface.
- **Option 2:** Scope C-1 only — glue module + race_events.py + tests. Defer onboarding writers to Scope C-2 next session. 6 files. Functional gap: onboarding-set targets won't evict until natural cache miss; acceptable at zero users but loud-over-silent.
- **Option 3:** Inline cache calls — each writer imports Layer4Cache + PostgresCacheBackend + cache_invalidation directly. 5 files. Spreads the §9 matrix across 13 inline call sites; no single source of truth.
- **Option 4:** Wrap writes in race_events_repo.py — promote repo helpers to internally evict. ~5 files. Tightest coupling; breaks the Flask-blueprint-decoupled pure-data-access shape of repo.

Q2 (2026-05-18, /plan-mode gate): Andy picked **Option 1 — Full Scope C**.

### 2.5 Implementation order

1. **New `race_events_invalidation.py` (top-level)** — 3 helpers + injectable cache builder. Co-located with `race_events_repo.py` for discovery symmetry.
2. **Modified `routes/race_events.py`** — wire 9 call sites: set_target (always periodization); update_race (before/after diff with 3-helper precedence); delete_race (periodization iff was_target); locale + equipment CRUD (brief-only iff target).
3. **Modified `routes/onboarding.py`** — wire 3 call sites: target_race_save (CREATE → periodization always; UPDATE → 3-helper diff); route_locales_add + delete (brief-only always — parent is target by construction).
4. **New `tests/test_race_events_invalidation.py`** — 13 tests using `InMemoryCacheBackend`.
5. **Bookkeeping:** Project_Backlog_v58.md → _v59.md (Rule #12; v58 retained) + CLAUDE.md (line 52 last-shipped narrative + line 254 backlog ref) + this handoff. See §9.

### 2.6 Architectural choices on the record

- **3 narrowest-cut helpers per §9 matrix row-type.** Periodization-grade reuses existing `evict_on_layer_change(cache, uid, 'layer3b')` since 3B's input set is what changes; brief-only narrowest cut via `invalidate_entry_point('race_week_brief', ...)`; locale broadest cut via `evict_on_layer_change(cache, uid, 'layer2c')` since 2C cascade triggers all 4 entry points (heavier than design §9's "Layer 2C; Layer 4 race-week-brief" abbreviation but defensible — 2C re-deriving for the event locale cascades to all 4 entry points per the existing §9.3 matrix).
- **Top-level placement of `race_events_invalidation.py`.** Mirrors `race_events_repo.py` for discoverability. This is writer-side coupling glue; not part of the `layer4/cache_invalidation.py` surface which is keyed on upstream-layer names. Top-level placement signals "discovered alongside `race_events_repo.py`" — the data-access + invalidation glue live as siblings.
- **Cache lifecycle = transient per-request.** Vercel is stateless serverless, so each request gets a fresh process; each helper invocation builds a fresh `Layer4Cache` wrapping a `PostgresCacheBackend` over the current Flask request-scoped `db`. The closure `lambda: db` captures the request-scoped connection at helper invocation time. Tests bypass via `cache=` kwarg injecting `InMemoryCacheBackend`. Alternative (process-local singleton cache) ruled out — Vercel multi-process surface defeats it + no observed performance benefit since the eviction operations are write-only DELETE statements not warm-cache reads.
- **`update_race` before/after diff.** Captures the existing `race` dict via `get_race_event` (already loaded for ownership check) + diffs against new form values. Precedence: periodization > locale > brief-only. Brief-only skipped when periodization OR locale already fired since both broader evictions already cover race_week_brief (avoids redundant DELETE round-trips).
- **Skip-firing on non-target row writes.** The §9 matrix's "Any change on a non-target race_events row → None" row is handled by gating the helper calls on `race['is_target_event']` (or `was_target` for delete_race after the row is gone). Race not in scope of any plan = no invalidation work + no metrics noise. Saves a round-trip when athletes edit non-target races.
- **Onboarding `target_race_save` CREATE path always fires periodization.** Mode flips open_ended → event for Layer 3B; periodization-grade is correct. UPDATE path applies the same 3-helper before/after diff as the race_events update flow for symmetry — pre-existing target rows can have their event_date/race_format/locale/brief-fields edited via onboarding the same way they can via the profile tab.
- **Onboarding `route_locales_add` + `route_locales_delete` unconditionally brief-only.** Parent is target by construction since `_get_target_race_row` filters on `is_target_event=TRUE`. No need to re-check inside the helper; the route handler's `_get_target_race_row` short-circuit guarantees it.
- **Did NOT wire `target_race_skip` or `route_locales_skip` or `route_locales_continue`.** These write account_nudges only, not race_events rows. No Layer 4 cache invalidation needed.
- **Did NOT wire `new_race` POST.** The form always creates `is_target_event=FALSE` rows. If v2 ever exposes an `is_target_event` checkbox the call site will need a conditional helper call paired with the existing `set_target_event` route.
- **Did NOT modify `race_events_repo.py`.** The data-access layer stays Flask-blueprint-decoupled per its design; coupling repo helpers to the Layer 4 cache facade would invalidate that abstraction. Option 4 in the /plan-mode gate was rated WORSE for this reason.
- **Did NOT add a Postgres-backed integration test.** The per-helper unit tests via `InMemoryCacheBackend` + `PostgresCacheBackend`'s own 10 tests from Step 5 (covering get/put/evict_for_user/evict_entry_point via `_FakeConn`) already exercise the chain. A true end-to-end Postgres test would test psycopg2 + PG behavior, not Scope C's routing.
- **Helpers accept `cache: Layer4Cache | None = None` kwarg.** Matches the `_default_llm_caller` dependency-injection pattern across `single_session.py` / `plan_refresh.py` / `race_week_brief.py`. Tests pass an `InMemoryCacheBackend`-wrapped Layer4Cache; production omits the kwarg + falls back to `_build_default_cache(db)`.

### 2.7 Stop-and-ask triggers retrospective

- **Trigger #5 (schema/inter-layer-contract amendments):** ✅ FIRED — the invalidation contract surface is cross-layer (Layer 4 cache eviction rules). Routed via the /plan-mode AskUserQuestion gate in §2.4; Andy picked Option 1.
- **Trigger #7 (new partial-update invalidation rule):** ✅ FIRED (the load-bearing trigger for Scope C). Same gate.
- **Trigger #8 (architectural alternatives with real tradeoffs):** ✅ FIRED IMPLICITLY (Options 1-4 + glue-module-placement vs inline-calls vs repo-coupling). Resolved in the same /plan-mode gate.
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows; D-72 already exists.

---

## 3. File-by-file substantive edits

### 3.1 New `race_events_invalidation.py` (top-level, ~115 lines)

Three helpers + injectable cache builder. Helper signatures:

```python
def evict_on_target_event_periodization_change(
    db, user_id: int, *, cache: Layer4Cache | None = None
) -> int:
    if cache is None:
        cache = _build_default_cache(db)
    return evict_on_layer_change(cache, user_id, 'layer3b')

def evict_on_target_event_brief_field_change(
    db, user_id: int, *, cache: Layer4Cache | None = None
) -> int:
    if cache is None:
        cache = _build_default_cache(db)
    return cache.invalidate_entry_point(
        'race_week_brief',
        layer='race_events_brief_field',
        user_id=user_id,
    )

def evict_on_target_event_locale_change(
    db, user_id: int, *, cache: Layer4Cache | None = None
) -> int:
    if cache is None:
        cache = _build_default_cache(db)
    return evict_on_layer_change(cache, user_id, 'layer2c')
```

Cache builder:

```python
def _build_default_cache(db) -> Layer4Cache:
    return Layer4Cache(PostgresCacheBackend(lambda: db))
```

Module-level docstring carries the full §9 matrix → helper mapping table verbatim so future devs reading the file see the contract reference.

### 3.2 `routes/race_events.py` — 9 call sites + new import block

Import added at top:

```python
from race_events_invalidation import (
    evict_on_target_event_brief_field_change,
    evict_on_target_event_locale_change,
    evict_on_target_event_periodization_change,
)
```

Call sites:
- **`update_race`** — captures before-state via existing `get_race_event` call, runs the update, then diffs against new form values. Periodization-grade fires on event_date OR race_format change; locale-grade on event_locale_id change; brief-only on other-field change BUT skipped if periodization or locale already fired. All gated on `race['is_target_event']`.
- **`delete_race`** — captures `was_target = bool(race['is_target_event'])` before delete; fires periodization-grade after if was_target.
- **`set_target`** — always fires periodization-grade after `set_target_event(db, uid, race_event_id)` returns.
- **`add_locale` / `update_locale` / `delete_locale`** — each rebinds the previously-bare `if not get_race_event(...)` ownership check to `race = get_race_event(...)` so we can read `race['is_target_event']`; fires brief-only iff target.
- **`add_equipment` / `delete_equipment`** — same pattern; fires brief-only iff parent race is target.

### 3.3 `routes/onboarding.py` — 3 call sites + new import block

Import added alongside the existing `race_events_repo` import:

```python
from race_events_invalidation import (
    evict_on_target_event_brief_field_change,
    evict_on_target_event_locale_change,
    evict_on_target_event_periodization_change,
)
```

Call sites:
- **`target_race_save`** — pre-captures form values to local variables (so the before/after diff in the UPDATE branch can compare against them). CREATE branch fires periodization-grade after `create_race_event(..., is_target_event=True)` returns (mode flips open_ended → event). UPDATE branch applies the same 3-helper before/after diff as `routes/race_events.py:update_race` against the existing `target` row.
- **`route_locales_add`** — fires brief-only after `add_route_locale(...)` returns (parent is target by construction).
- **`route_locales_delete`** — fires brief-only after `delete_route_locale(...)` returns.

`target_race_skip` + `route_locales_skip` + `route_locales_continue` intentionally untouched (write nudges only).

### 3.4 New `tests/test_race_events_invalidation.py` (13 tests, ~210 lines)

Coverage:
- `TestPeriodizationChange × 4` — evicts plan_create + plan_refresh + race_week_brief preserving single_session; zero count when no user rows; scoped to user (other user's rows survive); metrics tagged with `layer3b`.
- `TestBriefFieldChange × 4` — evicts race_week_brief only; zero count when no brief rows; scoped to user; metrics tagged with `race_events_brief_field`.
- `TestLocaleChange × 3` — evicts all 4 entry points (broadest cut); scoped to user; metrics tagged with `layer2c`.
- `TestBuildDefaultCache × 2` — verifies the production path constructs a `Layer4Cache` wrapping a `PostgresCacheBackend`; verifies the helper falls back to `_build_default_cache(db)` when `cache=` kwarg is omitted (via monkeypatched builder injection).

All tests use `InMemoryCacheBackend` directly + seed cache rows for the test user + (optionally) another user to verify scope isolation. The `_seed_all_entry_points(backend, user_id)` helper centralizes the fixture pattern.

---

## 4. Test additions + combined run

**13 new tests in `tests/test_race_events_invalidation.py`. Combined `tests/` 736 → 749 in 2.34s.**

- Pre-edit baseline: 736 passed (after env restore).
- Post-edit: 749 passed; 0 failures; 0 errors; 0 warnings of concern.

No existing test files were modified — all 13 new tests live in a new test module per the existing repo convention (one test file per substantive module).

---

## 5. Manual §5.0 verification steps for Andy's walkthrough

Run on `https://aidstation-pro.vercel.app/` (or local dev) after PR merge. Layers on top of the D-66 onboarding 12-scenario suite + 6-scenario nudge UI + 6-scenario Scope A + 6-scenario Scope B. **5 new Scope C scenarios** (35 D-66 scenarios accumulated total).

1. **Setting a target race fires periodization eviction.** Log in, navigate to `/profile?tab=race-events`, click "Set as target" on a non-target race. Inspect the `layer4_cache` table (psql or admin route): rows for the user with `entry_point IN ('plan_create','plan_refresh','race_week_brief')` should be gone post-click; rows with `entry_point='single_session_synthesize'` should survive. Repeat for the reverse direction (unset target by setting a different race as target — atomic flip should evict both rows' worth).
2. **Editing brief-only fields on the target race fires race_week_brief eviction only.** Open `/profile/race-events/<target-id>/edit`, change only `distance_km` (or `race_rules_summary` or `mandatory_gear_text` or `notes` or `total_elevation_gain_m`) and Save. psql: `SELECT entry_point FROM layer4_cache WHERE user_id=<andy>;` — `race_week_brief` row gone; other 3 entry-points' rows survive.
3. **Changing event_locale_id on target race fires locale (all-4-entry-point) eviction.** From the same edit page, change the `event_locale_id` dropdown to a different locale. psql: all 4 entry-points' rows for the user gone.
4. **Editing a non-target race fires nothing.** Set a different race as target (so the original isn't target anymore), then edit any field on the now-non-target race. psql: all cache rows for the user survive.
5. **Onboarding target-race save fires periodization eviction.** With no existing target, walk through `/onboarding/target-race` and save a new target. psql: rows for plan_create/plan_refresh/race_week_brief gone; single_session row survives. Repeat the flow editing an existing target row — only the diff-relevant helper(s) should fire.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward moves

D-66 family is now architecturally complete. Remaining D-66 forward-pointers:

1. **D-72 Locale-FK type alignment** — defer trigger (i) partially advances post-Scope C (invalidation hooks wired; 3B read-path swap awaits a Layer 4 orchestrator which doesn't exist yet). D-72 is now a more concrete carry-forward but still doesn't have a forcing function until either a Layer 4 orchestrator lands OR a Layer 2C consumer trips on the slug-vs-id ambiguity. Three plausible paths per the row text remain: (a) int SERIAL id everywhere; (b) slug everywhere; (c) per-payload split. ~5-8 files. **Trigger #5 fires** (cross-layer schema change touching `Layer2C_Spec.md` §7 + `Layer3_3B_Spec.md` §7 + `layer4/context.py` typed payload contracts). Needs `/plan`-mode gate.

2. **Manual §5.0 walkthrough** of the accumulated D-66 family scenarios — 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C = 35 scenarios total now. Could be split across multiple Andy walkthrough sessions.

### 6.2 Orthogonal candidates

3. **Layer 4 Step 7 live LLM integration** — orthogonal to D-66. First end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call. Cache + telemetry from Steps 5/6 + the now-wired invalidation hooks from Scope C make it safer. Needs `ANTHROPIC_API_KEY` in the environment.

4. **`routes/onboarding.py:710` docstring tense** — informational past-tense out-of-sync (still references "legacy athlete_profile.target_event_*") after Scope B + Scope C. Doc-sweep follow-on nit; not load-bearing.

### 6.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully. (Delegate to Explore agent — it's now ~115k+ tokens.)
2. **Second re-read:** this handoff.
3. **Third re-read:** depends on scope.
   - D-72 → `layer4/context.py:337` (Layer2CPayload.locale_id) + `:795` (Layer3BPayload.event_locale_id) + `:933` (RaceEventPayload.event_locale_id) + `Layer2C_Spec.md` §7 + `Layer3_3B_Spec.md` §7 + the D-58 SERIAL id migration story at `init_db.py:1014`-`1028` for prior precedent.
   - Layer 4 Step 7 live LLM → `layer4/single_session.py:_default_llm_caller` (existing Anthropic SDK adapter, fully wired, awaiting environment-side `ANTHROPIC_API_KEY`) + `tests/test_layer4_single_session.py` (existing tests use stub callers; live integration test needs separate env-gated test or repl session).
   - Manual walkthrough → §5 above + Scope B predecessor §5 + Scope A predecessor §5 + nudge UI predecessor §5 + onboarding predecessor §6.
4. **Branch:** cut fresh off post-merge main OR stay on the harness pin (precedent: every D-66 session including this one has stayed harness-pinned).
5. **Scope C is complete:** the 3 helpers route cleanly through the existing Step 5 cache infrastructure; all 13 race-event writer call sites fire the correct §9-matrix helper; non-target writes correctly skip invalidation. The D-66 family architectural contract is closed end-to-end (DB foundation → profile-tab UI → onboarding § H.2/§H.4 → nudges UI → Scope A form retirement → Scope B column drop → Scope C invalidation hooks).

---

## 7. Open items / decisions pinned this session

### 7.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Q1 scope = Layer 3B Scope C (partial-update invalidation hooks) | Andy 2026-05-18 | Handoff §6.1-recommended next; closes D-66 family completely; may partially discharge D-72 (i) |
| 2 | Q2 plan = Option 1 — Full Scope C (glue module + all 10 race_events.py + all 3 onboarding.py + tests) | Andy 2026-05-18 | /plan-mode gate (Triggers #5/#7/#8 fired); other options ruled WORSE per §2.4 |
| 3 | 3 narrowest-cut helpers per §9 matrix row-type (periodization-grade / brief-only / locale-grade) | Architect-pick | Maps the 9-row matrix to 3 helpers; reuses existing primitives via layer3b + layer2c policies; matches §9 invalidation scope |
| 4 | Top-level placement of `race_events_invalidation.py` | Architect-pick | Mirrors `race_events_repo.py` for discoverability; writer-side glue isn't part of `layer4/cache_invalidation.py` surface which is upstream-layer-name-keyed |
| 5 | Transient per-request cache lifecycle | Architect-pick | Vercel = stateless serverless; no shared instance across requests; closure captures Flask request-scoped db |
| 6 | `update_race` before/after diff with periodization > locale > brief-only precedence | Architect-pick | Avoid redundant DELETE round-trips when broader evictions already cover race_week_brief |
| 7 | Skip-firing on non-target row writes | Architect-pick | §9 matrix's "Any change on a non-target row → None" row; saves a round-trip when athletes edit non-target races |
| 8 | Onboarding `target_race_save` CREATE always fires periodization | Architect-pick | Mode flips open_ended → event for Layer 3B |
| 9 | Did NOT wire skip/continue handlers + `new_race` POST | Architect-pick | Skip/continue write nudges only; new_race always creates is_target_event=FALSE rows |
| 10 | Did NOT modify `race_events_repo.py` | Architect-pick | Repo stays Flask-blueprint-decoupled per its original design; Option 4 ruled WORSE |
| 11 | Helpers accept `cache: Layer4Cache | None = None` kwarg for test injection | Architect-pick | Matches `_default_llm_caller` DI pattern across single_session.py / plan_refresh.py / race_week_brief.py |
| 12 | 8 files total (4 substantive code + 1 test + 3 bookkeeping) | Necessitated | 3 over the 5-file ceiling; precedent across the D-66 family (DB foundation 6 + profile-tab UI 11 + onboarding §H.2/§H.4 7 + nudges UI 6 + Scope A 6 + Scope B 5) |

### 7.2 Carry-forward — D-72 type-alignment (partially advanced)

D-72's defer trigger (ii) fired with Scope B (column retirement); trigger (i) partially advances with Scope C (invalidation hooks wired). The actual 3B read-path swap awaits a Layer 4 orchestrator. D-72 is now an active carry-forward awaiting its own scope-pick session OR a Layer 4 orchestrator build.

### 7.3 Carry-forward — D-66 §5.0 walkthrough (accumulating)

35 scenarios total now: 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C (§5 above). Andy walks on Vercel after PR merge.

### 7.4 Carry-forward — `_v58.md` retained per Rule #12

`Project_Backlog_v58.md` preserved alongside the new `_v59.md` per the numeric-version-suffix rule. The historical chain stays intact (v55 → v56 → v57 → v58 → v59).

### 7.5 Carry-forward — `routes/onboarding.py:710` docstring tense

Still references "legacy athlete_profile.target_event_*" as if columns still exist. Doc-sweep follow-on nit; not load-bearing.

---

## 8. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| New `race_events_invalidation.py` exists at repo root with 3 helpers + cache builder | ✅ inspection |
| `routes/race_events.py` imports the 3 helpers at top; 9 call sites wired (set_target / update_race [3 conditional helpers] / delete_race / 5 route-locale + equipment routes) | ✅ inspection |
| `routes/onboarding.py` imports the 3 helpers; 3 call sites wired (target_race_save [CREATE periodization + UPDATE 3-helper diff] / route_locales_add / route_locales_delete) | ✅ inspection |
| `new_race` POST + `target_race_skip` + `route_locales_skip` + `route_locales_continue` untouched | ✅ inspection |
| `race_events_repo.py` untouched | ✅ inspection |
| `tests/test_race_events_invalidation.py` exists with 13 tests | ✅ `PYTHONPATH=. pytest tests/test_race_events_invalidation.py` → 13 passed |
| Combined `tests/` 736 → 749 green | ✅ `PYTHONPATH=. pytest tests/` → 749 passed in 2.34s |
| `Project_Backlog_v59.md` exists; v58 retained | ✅ `ls -la` |
| `Project_Backlog_v59.md` D-66 row status updated to include Scope C | ✅ grep returns 1 match |
| `Project_Backlog_v59.md` D-72 row defer-trigger annotated with Scope C partial advance | ✅ inspection |
| `Project_Backlog_v59.md` file revision header bumped to v59 with Scope C narrative | ✅ grep `File revision:\*\* v59` returns 1 match |
| `CLAUDE.md` line 52 last-shipped narrative bumped to D-66 Layer 3B Scope C | ✅ inspection |
| `CLAUDE.md` Scope B demoted to "Predecessor — D-66 Layer 3B Scope B: ..." | ✅ inspection |
| `CLAUDE.md` line 254 First-session-checklist Backlog ref bumped to v59 | ✅ grep `Project_Backlog_v59` returns 1 match at line 254 |

---

## 9. Files shipped this session

**Substantive code (3 new/modified + 1 new test):**
1. New top-level `race_events_invalidation.py` — 3 helpers + injectable cache builder + module-level §9 matrix → helper mapping docstring.
2. Modified `routes/race_events.py` — new import block + 9 call sites wired (set_target / update_race / delete_race / 5 route-locale + equipment routes; some routes also rebound their `get_race_event` ownership check from bare-`if not` to `race = ...` so they can read `is_target_event`).
3. Modified `routes/onboarding.py` — new import block + 3 call sites wired (target_race_save CREATE + UPDATE branches with 3-helper diff; route_locales_add + delete).
4. New `tests/test_race_events_invalidation.py` — 13 tests using `InMemoryCacheBackend` covering all 3 helpers + the `_build_default_cache` production path + the helper default-cache-fallback via monkeypatched builder injection.

**Bookkeeping (3 files):**
5. New `aidstation-sources/Project_Backlog_v59.md` (per Rule #12; v58 retained as predecessor) — file revision header rewritten for Scope C; D-66 row status flipped to include Scope C + the §9 matrix → helper mapping narrative; D-72 row defer-trigger annotated with the partial advance.
6. Modified `aidstation-sources/CLAUDE.md` — last-shipped-session narrative bump (line 52: Scope B → Scope C; demotes Scope B to "Predecessor — D-66 Layer 3B Scope B: ..." tail reference); First-session-checklist Backlog ref bumped (line 254: v58 → v59).
7. New `aidstation-sources/handoffs/V5_Implementation_D66_Layer3B_Rewire_Scope_C_Closing_Handoff_v1.md` (this file).

**8 files total. 3 over the 5-file ceiling — precedent across the D-66 family** (DB foundation 6 + profile-tab UI 11 + onboarding §H.2/§H.4 7 + nudges UI 6 + Scope A 6 + Scope B 5 + this 8). Justified by the substantive edits forming a single architectural contract surface (invalidation hooks + all writer-side call sites + tests) that splitting would artificially fracture.

---

## 10. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **D-72 Locale-FK type alignment across typed payloads** — defer trigger (i) partially advanced this session; defer trigger (ii) fully fired (Scope B). Active carry-forward awaiting scope-pick session OR Layer 4 orchestrator build.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward; needs `ANTHROPIC_API_KEY`.
- **D-66 §5.0 walkthrough (35 scenarios accumulating)** — 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C. Andy walks on Vercel after PR merges.
- **`routes/onboarding.py:710` docstring tense** — informational past-tense out-of-sync after Scope B + Scope C; doc-sweep follow-on nit.

---

**End of handoff.**
