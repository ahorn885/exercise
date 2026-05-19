# V5 Implementation — D-72 Locale-FK Type Alignment Closing Handoff

**Session:** Single chat. Scope: D-72 locale-FK type alignment per the predecessor handoff `V5_Implementation_D66_Layer3B_Rewire_Scope_C_Closing_Handoff_v1.md` §6.1 + §6.2 — resolve the inconsistent locale-FK key types across the three Layer 4 typed payloads via slug-everywhere (Option 1 of the 4 paths surfaced at the /plan-mode gate).

**Date:** 2026-05-19

**Predecessor handoff:** `V5_Implementation_D66_Layer3B_Rewire_Scope_C_Closing_Handoff_v1.md` (Scope C shipped 2026-05-18; PR #88 merged via `e0715a8`). D-72 became an active carry-forward there with two of three defer-triggers fired and one partially advanced.

**Branch:** `claude/v5-layer3b-rewire-S9o19` (harness-pinned for this session — name carries over from the D-66 Layer 3B Scope A/B/C branch family even though this session is the D-72 follow-on rather than another Layer 3B scope; precedent: harness names mismatched with scope across the entire D-66 + D-72 chain).

**Status:** 🟢 8 files (2 substantive code + 2 test + 4 bookkeeping/spec). Combined `tests/` 749 → 751 (2 new tests in `tests/test_race_events_repo.py` + 1 fixture update in `tests/test_layer4_race_week_brief.py`). **D-72 status flipped 🟡 Deferred → ✅ Resolved 2026-05-19.** Layer 3B caller-side rewire still awaits a Layer 4 orchestrator build but the typed-payload contract surface that the orchestrator would consume is now consistent end-to-end.

**Over the 5-file ceiling by 3** — precedent across the D-66 / D-72 family.

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| D-66 Layer 3B Scope C shipped on main per predecessor handoff | `git log --oneline -15` | ✅ `e0715a8` (merge PR #88) + `11c67af` (Scope C commit) |
| `race_events_invalidation.py` exists at repo root with 3 helpers + cache builder | inspection | ✅ |
| `RaceEventPayload.event_locale_id: int \| None` (line 933 in `layer4/context.py`) | grep | ✅ pre-edit baseline |
| `Layer2CPayload.locale_id: str` (line 337) + `Layer3BPayload.event_locale_id: str \| None` (line 795) — the slug-shaped peers | grep | ✅ |
| `race_events.event_locale_id BIGINT NULL REFERENCES locale_profiles(id) ON DELETE SET NULL` per D-66 DB foundation | grep `init_db.py:1146` | ✅ |
| `locale_profiles.id BIGSERIAL` surrogate column added 2026-05-18 (D-66 path-2 pick) | grep `init_db.py:1134` | ✅ |
| `Project_Backlog_v59.md` exists; v58 retained per Rule #12 | `ls` | ✅ |
| `CLAUDE.md` line 52 last-shipped narrative reads Scope C + line 258 backlog ref reads v59 | grep | ✅ |
| Working tree clean on `claude/v5-layer3b-rewire-S9o19` | `git status` | ✅ |

**Rule #9 reconciliation:** all predecessor handoff claims match on-disk state. No drift. Proceeded directly to scope pick.

**Environmental drift surfaced (not code drift):** same recurrence as predecessors — the fresh container started without `pytest`/`pydantic`/`flask`/etc. installed in the uv-isolated pytest interpreter. Resolved via `uv tool install --force pytest --with pydantic --with flask --with anthropic --with psycopg2-binary --with bcrypt --with zxcvbn --with openpyxl --with garth --with garminconnect --with fit-tool --with requests --with Flask-WTF --with Flask-Limiter --with pydantic-settings --with logfire` (one retry on the first attempt — network timeout on a single package metadata fetch). Baseline 749 passed before any edits; final 751 passed at session end.

---

## 2. Session narrative — D-72 type-alignment

Andy opened with the URL to the Scope C closing handoff + "lets work." Followed the operating model — Rule #9 verification (all green), surfaced state + the carry-forward set from the predecessor handoff §6.

### 2.1 Scope pick (1-question gate)

Q1 (2026-05-19, 1-question gate): session scope. Andy picked **D-72 locale-FK type alignment** over Layer 4 Step 7 live LLM, the `routes/onboarding.py:710` docstring tense nit, and the manual §5.0 walkthrough. D-72 was the most concrete carry-forward — two of three defer-triggers had already fired (Scope B fully fired trigger (ii) via column drop; Scope C partially advanced trigger (i) via invalidation hooks). The Scope C handoff §6.1 framed it as "now a more concrete carry-forward but still doesn't have a forcing function until either a Layer 4 orchestrator lands OR a Layer 2C consumer trips on the slug-vs-id ambiguity"; Andy chose to land the resolution proactively rather than wait for the forcing function.

D-72 fires Trigger #5 (cross-layer schema/contract amendment across the typed payload surface) + Trigger #8 (architectural alternatives — 3 paths surfaced by the D-72 row itself: int-everywhere / slug-everywhere / per-payload split) so it needs a /plan-mode gate before any edits.

### 2.2 Reconnaissance (5 surfaces)

Read in parallel:
- `layer4/context.py` lines 320-340 (Layer2CPayload.locale_id), 780-840 (Layer3BPayload + event-metadata fields), 904-970 (RouteLocale + RouteLocaleEquipment + RaceEventPayload).
- `init_db.py` lines 1090-1180 (race_events DDL + locale_profiles BIGSERIAL id ADD COLUMN + race_route_locales + race_route_locale_equipment).
- All call sites: `grep -n "locale_id\|event_locale_id" layer4/*.py race_events_repo.py tests/*.py` → 30+ references mapped.
- `aidstation-sources/Race_Events_D66_Design_v1.md` §4 (RaceEventPayload typed contract) + §7 (profile UI) + §8 (Layer 3B integration) + §9 (invalidation matrix).
- `aidstation-sources/Layer2C_Spec.md` §7 + `Layer3_3B_Spec.md` §7 (paired locale_id field specs).

Findings:
- **Layer 2C dict-key contract is structurally load-bearing.** `layer2c_payloads: dict[str, Layer2CPayload]` is consumed in `layer4/hashing.py:83` (cache key derivation), `layer4/per_phase.py:792`, `layer4/single_session.py:417` (matches `request.locale_slug`), `layer4/single_session.py:988`, `layer4/cached_wrappers.py:67-68`, `layer4/validator.py:528/569/603/933`. Plus `PlanSession.locale_id: str` (output session locale identifier) is consumed in 7+ validator rules + the prompt-rendering surface.
- **`RaceEventPayload.event_locale_id: int` is the outlier** — 1 of 3 typed payloads carries int; the other 2 carry slug; `RaceWeekBrief.event_locale: str` (`layer4/payload.py:420`) is already slug-shaped (display surface).
- **The DB surrogate `locale_profiles.id BIGSERIAL`** was added solely for the `race_events.event_locale_id BIGINT REFERENCES locale_profiles(id) ON DELETE SET NULL` FK shape — composite PK `(user_id, locale)` cannot be referenced with a `ON DELETE SET NULL` clause because partial NULLability on a composite isn't expressible. The surrogate id has no other consumer.
- **Writers + listing helpers use int FK directly.** Form dropdown values are `locale_profiles.id`; `routes/race_events.py:edit_race` + `update_race` + `routes/onboarding.py:target_race_save` all submit int. `list_athlete_race_events` returns lightweight dicts for the profile-tab listing with `event_locale_id` as int — but the consumer template doesn't render it directly (it renders the parent dropdown selection state via `selected if locale.id == race.event_locale_id else ''`).

### 2.3 /plan-mode gate (Trigger #5/#8 routing)

Composed a 4-option plan with concrete rationale:

- **Option 1 (recommended): Slug everywhere.** Flip `RaceEventPayload.event_locale_id: int | None → str | None`. JOIN in `race_events_repo.load_race_event_payload` to surface slug. DB column stays BIGINT FK. Write/listing helpers + routes untouched. Paired `Race_Events_D66_Design_v1.md` §4.2 amendment documenting the int-DB / slug-payload split. ~7-8 files (at/over ceiling). Closes D-72.
- **Option 2: Int everywhere.** Flip Layer2CPayload.locale_id + Layer3BPayload.event_locale_id + PlanSession.locale_id `str → int`. Swap `layer2c_payloads: dict[str, ...] → dict[int, ...]`. Cache keys hash int. ~15+ files; backwards-incompatible cache keys (every cached row missed; one-time eviction needed). Closes D-72.
- **Option 3: Document the split + helpers.** Docstrings on each field; `slug_to_id` + `id_to_slug` helpers. ~2-3 files. Doesn't close D-72.
- **Option 4: Hold for forcing function.** Zero files. D-72 stays active carry-forward.

Q2 (2026-05-19, /plan-mode gate): Andy picked **Option 1 — Slug everywhere**.

### 2.4 Architectural choices on the record

- **Slug everywhere because RaceEventPayload is the outlier.** 1 of 3 typed payloads carried int; the rest of the pipeline structurally uses slug (dict-key contract + cache-key formulas + PlanSession output + RaceWeekBrief display). Inverting the majority (Option 2) would have touched 15+ files vs 7-8.
- **The DB BIGSERIAL `id` is the right shape for `ON DELETE SET NULL` — but that's a DB-internal concern.** A surrogate id added for a FK clause shouldn't necessarily bleed up into the typed-payload boundary. The `RaceWeekBrief.event_locale: str` precedent already had the slug-shaped display pattern; D-72's resolution simply applies that same pattern at the input boundary (RaceEventPayload).
- **Repo helper does the JOIN, not the orchestrator.** `race_events_repo.load_race_event_payload` issues `LEFT JOIN locale_profiles lp ON lp.id = re.event_locale_id` so the slug is surfaced at the data-access boundary. The orchestrator consumes a clean typed payload with no awareness of the surrogate id. Alternative (orchestrator-side resolution before Layer 4 invocation) was already the Layer4_Spec.md §4.5 framing pre-D-72; moving the resolution into the repo helper is structurally cleaner (the orchestrator doesn't need to know about locale_profiles at all).
- **Write/listing helpers keep int FK.** `list_athlete_race_events` + `get_race_event` + `create_race_event` + `update_race_event` are consumed by writer-side surfaces (profile-tab edit form + onboarding routes); form dropdowns submit `locale_profiles.id`. Switching them to slug would force a parallel JOIN on every read + a slug→id resolution on every write, with no consumer benefit. The dict surface returned by these helpers carries the int as a form-input-chain pass-through.
- **LEFT JOIN (not INNER JOIN).** `event_locale_id` is nullable in the schema (some races have no athlete-saved finish locale); INNER JOIN would drop those races. ON DELETE SET NULL also requires LEFT JOIN to preserve the row with NULL slug.
- **DB column type unchanged.** Would have required a separate migration + risk of FK breakage + a backfill. The type misalignment was a typed-payload concern, not a DB-shape concern; the DB stays BIGINT FK with the same ON DELETE SET NULL behavior.
- **Did NOT amend `Layer4_Spec.md` §4.5.** The source-pointer note line about "caller-side orchestrator resolves race_event_payload.event_locale_id against locale_profiles" is now semantically obsolete (resolution moved to repo load helper) but the spec line still holds — the payload arrives with `event_locale_id` already resolved to slug, just by a different mechanism. Wording-tightening is a doc-sweep follow-on nit, not load-bearing.
- **Did NOT amend `Layer2C_Spec.md` §7 or `Layer3_3B_Spec.md` §7.** Both already specify `locale_id: str` / `event_locale_id: str | None` — D-72's resolution aligns RaceEventPayload to that existing contract, so the 2C/3B specs are already correct.
- **Did NOT amend the `RaceEventPayload.model_validator`.** The slug shape doesn't change any structural invariant (sequence_idx unique + sorted ascending + first/last role anchors still all about route_locales). `event_locale_id` doesn't appear in any cross-field check.
- **Did NOT amend `init_db.py`.** No DDL change; the DB stays the same.

### 2.5 Stop-and-ask triggers retrospective

- **Trigger #5 (schema/inter-layer-contract amendments):** ✅ FIRED — the typed-payload boundary is a cross-layer contract surface. Routed via the /plan-mode AskUserQuestion gate in §2.3; Andy picked Option 1.
- **Trigger #8 (architectural alternatives with real tradeoffs):** ✅ FIRED — Options 1-4 each carry concrete tradeoffs (file-count + dict-key impact + cache-key compatibility + does-it-close-D-72). Resolved via the same gate.
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows; D-72 closes this session.
- **Trigger #7 (new partial-update invalidation rule):** did NOT fire — invalidation hooks landed in Scope C; the typed-payload shape change doesn't introduce new invalidation rules.

---

## 3. File-by-file substantive edits

### 3.1 `layer4/context.py` — RaceEventPayload type swap + docstring (line 933)

```python
    # D-72 resolved 2026-05-19 — slug everywhere across the typed pipeline.
    # The DB column race_events.event_locale_id is BIGINT FK to
    # locale_profiles(id); race_events_repo.load_race_event_payload JOINs
    # locale_profiles to surface the slug here. Aligns with
    # Layer2CPayload.locale_id + Layer3BPayload.event_locale_id + the dict
    # key in layer2c_payloads + PlanSession.locale_id + the slug-based
    # cache-key formulas in layer4/hashing.py. The DB surrogate id stays
    # the right shape for ON DELETE SET NULL behavior; it just doesn't
    # cross the typed-payload boundary.
    event_locale_id: str | None = None
```

### 3.2 `race_events_repo.py:load_race_event_payload` — LEFT JOIN

SELECT rewritten:

```sql
SELECT re.id, re.user_id, re.name, re.event_date, re.race_format,
       re.distance_km, re.total_elevation_gain_m,
       re.race_rules_summary, re.mandatory_gear_text,
       lp.locale AS event_locale_slug,
       re.is_target_event, re.notes
  FROM race_events re
  LEFT JOIN locale_profiles lp ON lp.id = re.event_locale_id
 WHERE re.id = ?
```

Construction: `event_locale_id=race_row["event_locale_slug"]`.

Docstring extended with a "D-72 type-alignment resolution (2026-05-19)" paragraph explaining the JOIN's purpose + the DB-int / payload-slug split.

### 3.3 `tests/test_race_events_repo.py` — fixture update + 2 new tests

- `_race_row` fixture: `"event_locale_id": 5 → "event_locale_slug": "nerstrand_finish"` (mirrors the JOIN'd column alias). Updated docstring noting the D-72 resolution + that write-path helper tests still seed int.
- `test_loads_payload_with_empty_route_locales`: `payload.event_locale_id == 5 → payload.event_locale_id == "nerstrand_finish"`.
- **NEW** `test_race_events_select_joins_locale_profiles_for_slug` — asserts `"LEFT JOIN locale_profiles"` AND `"lp.locale AS event_locale_slug"` in the SELECT SQL.
- **NEW** `test_payload_event_locale_id_is_none_when_fk_unresolved` — seeds `event_locale_slug=None` (simulates ON DELETE SET NULL + races with no FK), asserts `payload.event_locale_id is None`.

### 3.4 `tests/test_layer4_race_week_brief.py` — fixture update (line 400)

`_race_event_payload` factory: `event_locale_id=1 → event_locale_id="L-finish"` (slug shape matching the typed contract).

### 3.5 `aidstation-sources/Race_Events_D66_Design_v1.md` — §4.1 + §4.2 amendments

§4.1 RaceEventPayload code block: `event_locale_id: int | None = None` → `event_locale_id: str | None = None    # slug per D-72 (2026-05-19)`.

§4.2 gains a new "D-72 type-alignment resolution (2026-05-19)" paragraph documenting:
- The slug shape aligns with Layer 2C + Layer 3B + dict-key contract + PlanSession + cache-key formulas.
- DB column stays BIGINT FK with ON DELETE SET NULL.
- `race_events_repo.load_race_event_payload` issues the LEFT JOIN.
- Write/listing surfaces (`list_athlete_race_events` + `get_race_event` + `create_race_event` + `update_race_event` + `routes/race_events.py` + `routes/onboarding.py` + the profile-tab edit form) keep int FK because their consumer is the form-input chain.
- D-72 row flipped ✅ Resolved.

### 3.6 `aidstation-sources/Project_Backlog_v60.md` (new; v59 retained per Rule #12)

- File revision header rewritten for D-72.
- D-72 row body extended with the RESOLVED 2026-05-19 narrative.
- D-72 status flipped 🟡 Deferred → ✅ Resolved 2026-05-19.

### 3.7 `aidstation-sources/CLAUDE.md` — line 52 + line 258

- Line 52 last-shipped narrative bumped (Scope C → D-72; demotes Scope C to "Predecessor — D-66 Layer 3B Scope C: ..." tail reference).
- Line 258 First-session-checklist backlog ref bumped (v59 → v60).

### 3.8 `aidstation-sources/handoffs/V5_Implementation_D72_Locale_FK_Type_Alignment_Closing_Handoff_v1.md` (new — this file)

---

## 4. Test additions + combined run

**2 new tests in `tests/test_race_events_repo.py` + 1 fixture update in `tests/test_layer4_race_week_brief.py`. Combined `tests/` 749 → 751 in 1.21s.**

- Pre-edit baseline: 749 passed (after env restore).
- Post-edit: 751 passed; 0 failures; 0 errors; 0 warnings of concern.

No existing test files were modified beyond the fixture seam (the renamed dict key + 1 assertion bump). All 2 new tests live inside the existing `TestLoadRaceEventPayload` class per the existing repo convention (one test class per helper function).

---

## 5. Manual §5.0 verification steps for Andy's walkthrough

Run on `https://aidstation-pro.vercel.app/` (or local dev) after PR merge. Layers on top of the D-66 family 35-scenario suite. **1 new D-72 scenario** (36 scenarios accumulated total).

1. **Race-week-brief payload carries slug after race-event locale is set.** Log in. On `/profile?tab=race-events`, edit the target race + set `event_locale_id` to an existing athlete locale (dropdown selection). Save. Trigger a race-week-brief invocation OR call `load_target_race_event_payload(db, andy_uid)` from a Python shell against prod. Inspect: `payload.event_locale_id` should be the slug string (e.g., `"nerstrand_finish"`) — NOT the int id. Verify against `SELECT locale FROM locale_profiles WHERE id = <int_id>` matches the surfaced slug. If event_locale_id is unset on the race row OR the locale_profiles row was deleted via ON DELETE SET NULL: `payload.event_locale_id is None`.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward moves

D-72 is now closed. Remaining carry-forwards:

1. **Layer 3B caller-side rewire — the actual orchestrator build.** The `athlete_profile.target_event_*` columns are physically dropped (Scope B); the invalidation hooks are wired (Scope C); the typed-payload contract is consistent (D-72). What's missing is the orchestrator code path that reads `race_events WHERE is_target_event=true` for 3B's event-mode input and threads `RaceEventPayload` through to `llm_layer4_race_week_brief`. No Layer 4 orchestrator currently exists; this is the longest forward-pointer and lands as Layer 4 Step 7 or Step 8 (post-cache-layer; the orchestrator wires the per-entry-point cached wrappers + the invalidation hooks together). **Trigger #5 + #8 likely to fire** — needs `/plan`-mode gate at session start.

2. **Manual §5.0 walkthrough** of the accumulated D-66 + D-72 family scenarios — 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72 = 36 scenarios total now. Could be split across multiple Andy walkthrough sessions.

### 6.2 Orthogonal candidates

3. **Layer 4 Step 7 live LLM integration** — orthogonal to D-66/D-72. First end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call. Cache + telemetry from Steps 5/6 + the now-wired invalidation hooks from Scope C + the now-consistent payload shape from D-72 make it safer. Needs `ANTHROPIC_API_KEY` in the environment.

4. **`routes/onboarding.py:710` docstring tense + `Layer4_Spec.md` §4.5 source-pointer wording.** Two doc-sweep follow-on nits:
   - `routes/onboarding.py:710` past-tense docstring still references "legacy athlete_profile.target_event_*" after Scope B + Scope C.
   - `Layer4_Spec.md` §4.5 row 5 + line 803 reference "caller-side orchestrator resolves race_event_payload.event_locale_id against locale_profiles" — now semantically obsolete after D-72 (resolution lives in the repo load helper). Wording-tightening only; not load-bearing.

### 6.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully. (Delegate to Explore agent — it's now ~115k+ tokens.)
2. **Second re-read:** this handoff.
3. **Third re-read:** depends on scope.
   - Layer 3B caller orchestrator → `Layer4_Spec.md` §5.1-5.3 + §9.1-9.6 (cache + invalidation surfaces) + `layer4/cached_wrappers.py` (orchestrator-side entry points already shipped Step 5) + `race_events_repo.py` (data-access boundary) + the now-shipped `race_events_invalidation.py` (Scope C invalidation glue) + the now-consistent `RaceEventPayload` from this session.
   - Layer 4 Step 7 live LLM → `layer4/single_session.py:_default_llm_caller` (existing Anthropic SDK adapter, fully wired, awaiting environment-side `ANTHROPIC_API_KEY`) + `tests/test_layer4_single_session.py`.
   - Manual walkthrough → §5 above + Scope C predecessor §5 + Scope B predecessor §5 + Scope A predecessor §5 + nudge UI predecessor §5 + onboarding predecessor §6.
4. **Branch:** cut fresh off post-merge main OR stay on the harness pin (precedent: every D-66 / D-72 session including this one has stayed harness-pinned).

---

## 7. Open items / decisions pinned this session

### 7.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Q1 scope = D-72 locale-FK type alignment | Andy 2026-05-19 | Most concrete carry-forward; two of three defer-triggers had already fired; landing proactively closes the typed-payload contract surface before the orchestrator build |
| 2 | Q2 plan = Option 1 — Slug everywhere | Andy 2026-05-19 | /plan-mode gate; smallest surgery that actually resolves D-72; RaceEventPayload is the outlier (1 of 3); aligns with dict-key + cache-key + display surfaces |
| 3 | Repo helper does the JOIN, not orchestrator | Architect-pick | Keeps typed-payload boundary clean; orchestrator doesn't need to know about locale_profiles surrogate id |
| 4 | LEFT JOIN (not INNER) | Architect-pick | Preserves event_locale_id=None for races with no FK set + ON DELETE SET NULL targets |
| 5 | Write/listing helpers keep int FK | Architect-pick | Consumed by writer surfaces (form dropdowns submit `locale_profiles.id`); changing them would force a parallel JOIN on every read with no consumer benefit |
| 6 | DB column type unchanged | Architect-pick | Type misalignment was a typed-payload concern; DB shape doesn't need to change; saves a migration + FK breakage risk |
| 7 | Did NOT amend Layer4_Spec.md §4.5 source-pointer | Architect-pick | Wording-tightening only; spec line still holds (payload arrives with slug, just resolved by a different mechanism) |
| 8 | Did NOT amend Layer2C_Spec.md / Layer3_3B_Spec.md | Architect-pick | Both already specify slug shape; D-72 aligns RaceEventPayload to existing contract |
| 9 | 8 files total (2 substantive code + 2 test + 4 bookkeeping/spec) | Necessitated | 3 over the 5-file ceiling; precedent across the D-66 / D-72 family |

### 7.2 Carry-forward — Layer 3B caller-side rewire (orchestrator build)

The actual 3B read-path swap from `athlete_profile.target_event_*` (physically dropped per Scope B) to `race_events WHERE is_target_event=true` lands when a Layer 4 orchestrator is built. D-72's resolution gives that orchestrator a stable typed contract to build against (RaceEventPayload + Layer3BPayload now both surface slug-shaped event_locale_id, so 3B can read the target race row via `load_target_race_event_payload` and pass it through coherently).

### 7.3 Carry-forward — Manual §5.0 walkthrough (accumulating)

36 scenarios total: 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72 (§5 above). Andy walks on Vercel after PR merge.

### 7.4 Carry-forward — `_v59.md` retained per Rule #12

`Project_Backlog_v59.md` preserved alongside the new `_v60.md`. The historical chain stays intact (v55 → v56 → v57 → v58 → v59 → v60).

### 7.5 Carry-forward — `routes/onboarding.py:710` docstring tense

Still references "legacy athlete_profile.target_event_*" as if columns still exist. Doc-sweep follow-on nit; not load-bearing.

### 7.6 Carry-forward — `Layer4_Spec.md` §4.5 source-pointer wording

Row 5 + line 803 reference "caller-side orchestrator resolves race_event_payload.event_locale_id" — now semantically obsolete (resolution lives in repo load helper). Wording-tightening only; not load-bearing.

---

## 8. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `layer4/context.py:933` reads `event_locale_id: str \| None = None` with D-72 docstring | ✅ inspection |
| `race_events_repo.py:load_race_event_payload` SELECT contains `LEFT JOIN locale_profiles` + `lp.locale AS event_locale_slug` | ✅ inspection |
| `race_events_repo.py` writers + listing helpers unchanged (int FK preserved) | ✅ grep `event_locale_id: int` returns the unchanged write/update signatures |
| `tests/test_race_events_repo.py` `_race_row` fixture keys on `event_locale_slug` | ✅ inspection |
| `tests/test_race_events_repo.py` has 2 new tests: `test_race_events_select_joins_locale_profiles_for_slug` + `test_payload_event_locale_id_is_none_when_fk_unresolved` | ✅ grep |
| `tests/test_layer4_race_week_brief.py` `_race_event_payload` fixture: `event_locale_id="L-finish"` | ✅ inspection |
| Combined `tests/` 749 → 751 green | ✅ `PYTHONPATH=. pytest tests/` → 751 passed in 1.21s |
| `Race_Events_D66_Design_v1.md` §4.1 code block: `event_locale_id: str \| None = None` | ✅ inspection |
| `Race_Events_D66_Design_v1.md` §4.2 has "D-72 type-alignment resolution (2026-05-19)" paragraph | ✅ grep |
| `Project_Backlog_v60.md` exists; v59 retained | ✅ `ls -la` |
| `Project_Backlog_v60.md` D-72 row status reads `✅ Resolved 2026-05-19` | ✅ grep |
| `Project_Backlog_v60.md` file revision header reads `v60 — 2026-05-19` with D-72 narrative | ✅ grep |
| `CLAUDE.md` line 52 last-shipped narrative reads D-72 locale-FK type alignment | ✅ inspection |
| `CLAUDE.md` line 258 First-session-checklist Backlog ref reads `Project_Backlog_v60` | ✅ grep |

---

## 9. Files shipped this session

**Substantive code (2 modified + 2 modified tests):**
1. Modified `layer4/context.py` — `RaceEventPayload.event_locale_id: int | None → str | None` + inline D-72 docstring block.
2. Modified `race_events_repo.py` — `load_race_event_payload` SELECT rewritten with LEFT JOIN to locale_profiles + docstring extension.
3. Modified `tests/test_race_events_repo.py` — `_race_row` fixture key swap + assertion bump + 2 new tests in TestLoadRaceEventPayload.
4. Modified `tests/test_layer4_race_week_brief.py` — `_race_event_payload` fixture event_locale_id slug swap.

**Spec + bookkeeping (4 files):**
5. Modified `aidstation-sources/Race_Events_D66_Design_v1.md` — §4.1 code block type swap + §4.2 D-72 resolution paragraph.
6. New `aidstation-sources/Project_Backlog_v60.md` (per Rule #12; v59 retained) — file revision header rewritten + D-72 row body extended + D-72 status flipped to ✅ Resolved 2026-05-19.
7. Modified `aidstation-sources/CLAUDE.md` — last-shipped narrative bump (line 52: Scope C → D-72; demotes Scope C to "Predecessor — D-66 Layer 3B Scope C: ..." tail reference); First-session-checklist Backlog ref bumped (line 258: v59 → v60).
8. New `aidstation-sources/handoffs/V5_Implementation_D72_Locale_FK_Type_Alignment_Closing_Handoff_v1.md` (this file).

**8 files total. 3 over the 5-file ceiling — precedent across the D-66 / D-72 family** (DB foundation 6 + profile-tab UI 11 + onboarding §H.2/§H.4 7 + nudges UI 6 + Scope A 6 + Scope B 5 + Scope C 8 + this 8). Justified by the substantive edits forming a single architectural contract surface (typed-payload type swap + paired repo helper JOIN + paired test updates + paired design-doc amendment + bookkeeping floor) that splitting would artificially fracture.

---

## 10. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **Layer 3B caller-side rewire (orchestrator build)** — now the cleanest D-66 / D-72 follow-on; awaits Layer 4 orchestrator.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward; needs `ANTHROPIC_API_KEY`.
- **Manual §5.0 walkthrough (36 scenarios accumulating)** — 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72. Andy walks on Vercel after PR merges.
- **`routes/onboarding.py:710` docstring tense + `Layer4_Spec.md` §4.5 source-pointer wording** — doc-sweep follow-on nits; not load-bearing.

---

**End of handoff.**
