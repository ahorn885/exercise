# Best-Fit Modality Resolver — Spec v2

**Status:** v2 amendment, 2026-05-24. Race-craft-aware scoring + D-008b Outdoor Paddling vocab population.
**Predecessor:** `BestFitModality_Spec_v1.md` (representative-disciplines vocab + static `base_preference_score`). v2 is additive — v1 contracts are preserved; default-None kwarg + default-False payload field keep v1-shaped callers identical at runtime.
**Predecessor decisions (this session):**
- BM-3 Layer 4 prompt-body integration (2026-05-24) — `Layer2ModalityPayload` renders into all 3 plan-gen prompts (single_session + per_phase + race_week_brief). The renderer prints `(score N)` per option, so any score change is LLM-visible.
- Drift audit (this session) — Andy's design check surfaced that the static `base_preference_score` is the wrong abstraction for paddling: D-008b's top-pick should depend on which craft the target race specifies (PGE 2026 = Packraft; a different AR might be Kayak-primary). Path A picked over Path B (LLM-side reasoning) / Path C (defer D-008b) / Path D (ship D-008b with static scores + document gap). Sequencing 3 = big batched ship (~15-18 files; ratified ceiling break ~G4 precedent).
- Per Trigger #3 (cross-layer surface change — new race_events column + resolver kwarg) + Trigger #5 (architectural alternatives) plan-mode gate, 3 nested decisions ratified at AskUserQuestion gates:
  - **Score math = multiplicative *1.2** (over additive +15 / tier promotion to 95+). Cap at 100. Preserves relative ordering across base-score bands without an "additive blows past 100" edge case.
  - **Form UX = add-row builder** (over per-discipline checkboxes / no-form-this-slice). Mirrors `_race_terrain_editor.html` pattern; gives Andy flexibility to add (discipline, equipment) pairs ad-hoc.
  - **Lint scope = add missing names to canonical 0B** (over static-set-in-test-file / skip-lint). Half of BM-5's equipment canonicalisation work landed inline.

---

## §A — Function signature delta

v1 signature (preserved):

```python
def resolve_best_fit_modality(
    db,
    *,
    cluster_locale_inputs: list[ClusterLocaleInput],
    included_discipline_ids: list[str],
    skill_toggle_states: dict[str, bool] | None = None,
    etl_version_set: dict[str, str],
) -> Layer2ModalityPayload:
```

v2 signature:

```python
def resolve_best_fit_modality(
    db,
    *,
    cluster_locale_inputs: list[ClusterLocaleInput],
    included_discipline_ids: list[str],
    skill_toggle_states: dict[str, bool] | None = None,
    race_modality_hints: dict[str, list[str]] | None = None,  # NEW
    etl_version_set: dict[str, str],
) -> Layer2ModalityPayload:
```

`race_modality_hints` shape: `{<discipline_id>: [<equipment_canonical_name>, ...], ...}`. Empty/None → no bumps (v1-identical behavior).

Caller (orchestrator) sources from `target_race_event_payload.race_modality_hints` (new JSONB column on `race_events`; see §C). Single-session orchestrator threads the same hint dict when a target event exists for the user; if not, hints are None.

## §B — Scoring math delta

v1 §5.3 (preserved): `base_preference_score` is 0-100 static per `ModalityOptionDef`. Outdoor > Indoor; Specific > Generic; Available-skill > Requires-coached-introduction.

v2 augmentation: when computing per-option preference at resolution time, the resolver computes:

```python
race_craft_match = (
    race_modality_hints is not None
    and discipline_id in race_modality_hints
    and bool(set(opt_def.requires_equipment_all_of) & set(race_modality_hints[discipline_id]))
)
effective_score = min(100, int(round(opt_def.base_preference_score * 1.2))) if race_craft_match else opt_def.base_preference_score
```

The match condition: ANY equipment in the option's `requires_equipment_all_of` appears in the hint list for that discipline. (Set intersection non-empty.) Options with empty `requires_equipment_all_of` never match (no equipment to bump on — e.g. `outdoor_trail_run` with `requires_equipment_all_of=[]` is exempt).

Cap: `min(100, ...)` prevents blow-past. `int(round(...))` keeps the score int for stable hashing + cache-key determinism.

The bump preserves relative ordering within a discipline's menu: if option A has base 80 and option B has base 70 and both match the hint, A=96 still outranks B=84. If only A matches, A=96 outranks B=70 (gap widens). If only B matches, B=84 outranks A=80 (relative flip — the intended behavior).

## §C — Source-of-truth for hints (race_events column)

New JSONB column on `race_events`:

```sql
ALTER TABLE race_events
  ADD COLUMN IF NOT EXISTS race_modality_hints JSONB NOT NULL DEFAULT '{}'::jsonb;
```

Shape stored: `{<discipline_id>: [<equipment_canonical_name>, ...], ...}`. Empty dict `{}` = no hints (v1-identical resolver behavior). Pre-v2 rows backfill to `{}` via the column default.

Edited via the race-event edit form. Form-side parse: add-row builder (mirrors `_race_terrain_editor.html`). Each row pairs a discipline-id `<select>` (options from `_disciplines_for_framework_sport`) with an equipment-canonical-name `<select>` (options from the active 0B `equipment_items.canonical_name` set). Multiple rows per discipline allowed (e.g. PGE 2026 could specify both Packraft AND Kayak for D-008b → the resolver bumps both options). Empty rows silently drop. Unknown discipline-id or equipment-name silently drops (no validation error; matches resolver's silent-pass-through-on-unknown contract).

Server-side parser (`_parse_race_modality_hints`) returns dict shape; collapses duplicate discipline rows by extending the equipment list per discipline.

## §D — RaceEventPayload + Orchestrator wire

`layer4.context.RaceEventPayload` gains `race_modality_hints: dict[str, list[str]] = {}` (Pydantic default empty dict; v1-shape callers identical at construct time).

`race_events_repo.load_race_event_payload(...)` SELECT extends to fetch the new column; `update_race_event(...)` accepts a `race_modality_hints` kwarg; INSERT/UPDATE writes the JSONB column.

`layer4.orchestrator` threads the hint dict to all 3 `resolve_best_fit_modality(...)` call sites:
- `orchestrate_race_week_brief` — pulls `target_event.race_modality_hints`.
- `orchestrate_plan_create` — pulls `target_event.race_modality_hints`.
- `orchestrate_single_session_synthesize` — pulls `target_event.race_modality_hints` if a target event exists; None otherwise.

When the resolver receives `race_modality_hints=None` (no target event) or an empty dict, behavior is v1-identical.

## §E — Cache-key extension

New optional hash component in all 3 cache keys (mirrors the BM-3 `layer2_modality_hash` pattern, same forward-compat None → '' collapse):

- `plan_create_key(..., race_modality_hints_hash: str | None = None)` — None → '' collapse for pre-v2 cache hit compat.
- `single_session_synthesize_key(..., race_modality_hints_hash: str | None = None)`.
- `race_week_brief_key(..., race_modality_hints_hash: str | None = None)`.

Cached wrappers compute `race_modality_hints_hash = compute_payload_hash(race_modality_hints) if race_modality_hints else None`. Threaded into the key alongside `layer2_modality_hash`.

## §F — ModalityOption transparency field

`layer4.context.ModalityOption` gains `race_craft_match: bool = False`. Resolver sets True when the bump applied; default False preserves v1 payload shape. Renderers may cite this field in coach-voice copy in a follow-on slice (out of scope for v2 implementation; spec-only forward-pointer).

Rationale for shipping the field but not the renderer change: the LLM already sees the bumped score (e.g. `(score 96)` vs `(score 80)`) and the rationale_hint, which is enough signal for the synthesis pass to prefer the bumped option. Explicit `[race-craft match]` rendering is a nice-to-have that adds 3 more renderer-files of edits to an already 15-file slice. Deferred to follow-on slice BM-7-Render (Open Items v2 §M-2).

## §G — Cache invalidation policy

A change to `race_events.race_modality_hints` evicts the 3 entry points the resolver feeds:
- `plan_create`
- `single_session_synthesize`
- `race_week_brief`

`plan_refresh` is NOT evicted (plan_refresh tier renderers don't consume resolver output post-BM-3 G1=A3).

New policy function `evict_on_target_event_modality_hints_change(db, user_id, cache=None)` in `race_events_invalidation.py`. Field-change comparison in the route's update path adds the existing prior-vs-new check pattern.

## §H — D-008b Outdoor Paddling vocab population

BM-1 D-008b slice. Per Andy's S2 = 6-option pragmatic pick (over S1 4-option canonical-clean / S3 3-option minimal):

```python
'D-008b': [
    # Flat-water / lake paddling — packraft (canonical 0B)
    ModalityOptionDef(
        modality_id='outdoor_paddle_packraft',
        modality_name='Outdoor packraft (flat / lake)',
        requires_terrain_any_of=['TRN-009', 'TRN-010'],
        requires_equipment_all_of=['Packraft'],
        requires_skill_toggle=None,
        is_outdoor=True, is_specific=True,
        base_preference_score=75,
        rationale_template='flat or open water accessible from {locale_name}, packraft on hand',
    ),
    # Flat-water / lake paddling — kayak
    ModalityOptionDef(
        modality_id='outdoor_paddle_kayak',
        modality_name='Outdoor kayak (flat / lake)',
        requires_terrain_any_of=['TRN-009', 'TRN-010'],
        requires_equipment_all_of=['Kayak'],
        requires_skill_toggle=None,
        is_outdoor=True, is_specific=True,
        base_preference_score=75,
        rationale_template='flat or open water accessible from {locale_name}, kayak on hand',
    ),
    # Flat-water / lake paddling — SUP
    ModalityOptionDef(
        modality_id='outdoor_paddle_sup',
        modality_name='Outdoor SUP (flat / lake)',
        requires_terrain_any_of=['TRN-009', 'TRN-010'],
        requires_equipment_all_of=['SUP'],
        requires_skill_toggle=None,
        is_outdoor=True, is_specific=True,
        base_preference_score=65,
        rationale_template='flat or open water accessible from {locale_name}, SUP on hand',
    ),
    # Whitewater / moving-water paddling — packraft (skill-gated)
    ModalityOptionDef(
        modality_id='outdoor_whitewater_packraft',
        modality_name='Outdoor packraft (whitewater / moving)',
        requires_terrain_any_of=['TRN-011', 'TRN-017'],
        requires_equipment_all_of=['Packraft'],
        requires_skill_toggle='whitewater_handling',
        is_outdoor=True, is_specific=True,
        base_preference_score=80,
        rationale_template='moving water accessible from {locale_name}, packraft + whitewater capability enabled',
    ),
    # Whitewater / moving-water paddling — kayak (skill-gated)
    ModalityOptionDef(
        modality_id='outdoor_whitewater_kayak',
        modality_name='Outdoor kayak (whitewater / moving)',
        requires_terrain_any_of=['TRN-011', 'TRN-017'],
        requires_equipment_all_of=['Kayak'],
        requires_skill_toggle='whitewater_handling',
        is_outdoor=True, is_specific=True,
        base_preference_score=80,
        rationale_template='moving water accessible from {locale_name}, kayak + whitewater capability enabled',
    ),
    # Pool drill (indoor substitute; no equipment requirement)
    ModalityOptionDef(
        modality_id='pool_paddle_drill',
        modality_name='Pool paddle drill (indoor substitute)',
        requires_terrain_any_of=['TRN-008'],
        requires_equipment_all_of=[],
        requires_skill_toggle=None,
        is_outdoor=False, is_specific=False,
        base_preference_score=30,
        rationale_template='pool drill substitute when outdoor water unavailable',
    ),
],
```

Race-craft awareness: PGE 2026 sets `race_modality_hints = {'D-008b': ['Packraft']}` → resolver bumps `outdoor_paddle_packraft` 75 → 90 and `outdoor_whitewater_packraft` 80 → 96. Kayak / SUP options stay at base. A different AR with `{'D-008b': ['Kayak']}` flips the menu order: kayak options bump above packraft.

## §I — Equipment canonicalisation (BM-5 partial close)

To support race_modality_hints' equipment-name dropdown (which sources from canonical 0B `equipment_items.canonical_name`) and to close the equipment-lint gap for the new D-008b vocab AND the existing D-001/D-006/D-010 vocab, the following 12 equipment names are added to canonical 0B in this slice:

- `Treadmill` (D-001 treadmill_run)
- `Gravel bike` (D-006 outdoor_gravel_ride; may already be present — idempotent insert)
- `Road bike` (D-006 outdoor_road_ride)
- `Bike trainer` (D-006 indoor_trainer)
- `Rope` (D-010 lead + top-rope)
- `Quickdraws` (D-010 outdoor_lead_climb)
- `Harness` (D-010 lead + top-rope)
- `Crash pad` (D-010 outdoor_boulder)
- `Climbing gym membership` (D-010 gym options) — flagged as a non-equipment-but-equipment-like marker
- `Hangboard` (D-010 gym_hangboard)
- `Kayak` (D-008b kayak options) — NEW canonical
- `Canoe` (reserved for future D-008b canoe options; not used in v2 vocab but added to canonical for completeness)

Already-canonical: `Packraft`, `SUP`.

ETL append lands in `etl/sources/populate_equipment_items_K2_additions.sql` (or a new K3 file if Andy prefers; choice deferred to slice implementation). Static lint test extended with `_KNOWN_EQUIPMENT` set covering canonical 0B names; the test catches resolver-vs-canonical drift at CI time. (Per Andy's L2 pick.)

## §J — Test scenarios (additions to v1 §13)

### v2 §13.7 Race-craft bump fires for D-008b at Andy's PGE 2026

Inputs:
- `cluster_locale_inputs = [home_locale]` with `locale_terrain_ids=['TRN-001','TRN-002','TRN-003','TRN-004','TRN-008','TRN-009','TRN-016']` + `effective_pool=['Packraft','Kayak','SUP']`
- `included_discipline_ids=['D-008b']`
- `skill_toggle_states={}` (default-OFF)
- `race_modality_hints={'D-008b': ['Packraft']}`

Expected:
- D-008b menu: `outdoor_paddle_packraft` top-pick at effective_score=90 (75 base × 1.2 → 90); `race_craft_match=True`.
- `outdoor_paddle_kayak` second at 75; `race_craft_match=False`.
- `outdoor_paddle_sup` third at 65; `race_craft_match=False`.
- whitewater options absent (TRN-011/017 not in locale).
- No skill-block flag (whitewater toggle OFF + no whitewater options eligible).

### v2 §13.8 Race-craft hint with no match — silent ignore

Inputs as 13.7 but `race_modality_hints={'D-008b': ['NonexistentCraft']}`.

Expected: identical to 13.7 with `race_modality_hints=None`. No options bumped. No error raised.

### v2 §13.9 Race-craft hint for absent discipline — silent ignore

Inputs as 13.7 but `race_modality_hints={'D-099-not-in-dict': ['Packraft']}`.

Expected: identical to v1 baseline. No bump (D-008b not in hint dict).

### v2 §13.10 Whitewater hint with toggle ON

Inputs:
- `cluster_locale_inputs = [river_locale]` with `locale_terrain_ids=['TRN-011','TRN-017']` + `effective_pool=['Packraft','Kayak']`
- `included_discipline_ids=['D-008b']`
- `skill_toggle_states={'whitewater_handling': True}`
- `race_modality_hints={'D-008b': ['Packraft']}`

Expected: `outdoor_whitewater_packraft` top at effective_score=96 (80 × 1.2); `outdoor_whitewater_kayak` second at 80 (no bump). `race_craft_match=True` for packraft option.

### v2 §13.11 Static lint — equipment names canonical

Per Andy's L2 pick: extend `TestStaticLint` with `test_every_required_equipment_is_canonical` that verifies every `requires_equipment_all_of` entry in the resolver dict appears in the test file's `_KNOWN_EQUIPMENT` set (which mirrors canonical 0B after the ETL additions in §I).

## §K — Performance budget (delta)

v1 §11 perf bound: O(disciplines × locales × options).

v2: identical bound. Race-craft check is a single set intersection per option per (discipline, locale) iteration. No new DB queries. Hint dict is passed in by the orchestrator; resolver doesn't fetch.

## §L — Edge cases (additions to v1 §10)

- **Empty hint dict `{}`**: no bumps. Identical to None.
- **Hint dict with empty equipment list per discipline `{'D-008b': []}`**: no match possible (empty set intersection with empty set is empty); no bump.
- **Hint references discipline absent from `_MODALITY_OPTIONS_PER_DISCIPLINE`**: silent (the discipline produces no menu rows anyway).
- **Hint references equipment not in any option's `requires_equipment_all_of`**: silent.
- **Multiple disciplines in hint**: each discipline's options scored independently.
- **Option's `requires_equipment_all_of` is empty**: option exempt from bump (no equipment to match against). E.g., `outdoor_trail_run` for D-001 never gets a race-craft bump.
- **Score at base 84 (or higher)** + bump: capped at 100 (84 × 1.2 = 100.8 → 100).
- **Score at base 0** + bump: 0 × 1.2 = 0. (Theoretical edge; no option in the vocab is at 0.)

## §M — Open items v2 (new + carried)

| # | Item | Status |
|---|---|---|
| M-1 | D-006 cycling scoring backfill — D-006's static scoring works for Andy today (gravel=85 > road=80 aligns with PGE), but a kayak-style race-context flip (a road-cycling race that mandates `Road bike`) would have the same gap as D-008b had. Backfill: lower D-006 base scores to neutral (gravel=75, road=75, trainer=40) and rely on race_modality_hints to differentiate. Pairs naturally with the D-006 follow-on (out of scope here). | Open (BM-7-D006Backfill) |
| M-2 | Renderer transparency — 3 prompt renderers cite `[race-craft match]` tag on options where `ModalityOption.race_craft_match=True`. Trivial 3-file slice; deferred to keep v2 batched ship at ~15 files. | Open (BM-7-Render) |
| M-3 | Equipment-name fuzzy match — race_modality_hints today does exact-string-match on equipment names. A user-typo or pre-canonical name would silently drop. Form-side dropdown sourcing from canonical 0B mitigates user-side drift; resolver-side drift (resolver references a name that canonical 0B doesn't carry) remains BM-5's body of work. | Open (BM-5 carry) |
| M-4 | Multi-discipline hints — orchestrator could surface hints inferred from `framework_sport` + `included_discipline_ids` (e.g., "this is an AR race with a known paddle leg → hint Packraft + Kayak"). Today hints are 100% athlete-edited. Inference is a separate slice. | Open (BM-8-Inferred) |
| M-5 (carried) | Vocab population for D-005 / D-007 / D-008a / D-011 / D-014 / D-015 / D-016 / D-020 — 8 deferred AR disciplines remaining post-D-008b. Same shape as BM-1 D-008b slice; each follow-on slice ~2 files. | Open (BM-1 carry) |
| M-6 (carried) | Phase-aware ranking inside Layer 4 (BM-2) — per_phase prompt copy includes a Peak/Taper hint guidance line, but structured prompt copy operationalizing the bias per phase remains the next refinement. | Open (BM-2 carry) |
| M-7 (carried) | Multi-locale cluster ingestion — orchestrator feeds primary locale only; resolver internally handles `list[ClusterLocaleInput]`. Wire-side aggregation pairs with Layer 2C's broader cluster expansion. | Open (BM-Cluster carry) |
| M-8 (carried) | plan_refresh tier renderers modality wire — explicitly excluded from BM-3 + v2. If/when modality cite material is needed in mid-plan refresh prompts, separate slice. | Open (BM-3-PR carry) |

## §N — Backward-compat note

v2 is fully additive:
- Resolver `race_modality_hints` kwarg defaults to None → v1-identical behavior.
- `ModalityOption.race_craft_match` defaults to False → v1-identical payload shape.
- `race_events.race_modality_hints` JSONB column defaults to `'{}'` → pre-v2 rows behave as if no hints set.
- Cache keys' `race_modality_hints_hash` slot collapses None → '' → pre-v2 cache entries continue to hit on default-None callers.

First POST-v2 deploy will see fresh keys for any orchestrator-driven call that supplies a non-empty hint dict; cache misses trigger one round of re-synthesis with the bumped scoring + race_craft_match field, then settle on the new keys.

## §O — Gut check (v2)

**What v2 gets right:**
- Closes a real abstraction gap Andy caught in the design review (static scoring is wrong for race-craft-specific disciplines).
- Multiplicative bump preserves intra-discipline ordering while flipping inter-craft preference.
- Source of truth (race_events column) is the right place — race-craft is a race-property, not an athlete-property or a locale-property.
- Spec-first sequencing maintained even at Sequencing 3's batched ship — the spec amendment is the architectural anchor for the 15-file diff.

**Risks / what might be missing:**
- The +20% bump magnitude is hand-tuned. If Andy adds a discipline where the spec-vs-generic gap is wider than 20%, the bump might not flip the order. Tests at §J §13.7 lock the magnitude to the current shape; future vocab additions might need a re-tune.
- D-006 cycling has the same gap but isn't backfilled in v2. M-1 carries it. If Andy adds a road-cycling-mandated race before backfill, the LLM might cite gravel as top despite race mandate. Workaround: set `race_modality_hints={'D-006': ['Road bike']}` and the bump fires for road=80 → 96 over gravel=85 → 85 (no bump). Works.
- Equipment-name string match is fragile. Form-side dropdown from canonical 0B is the primary defense; the static lint (§I) catches resolver-side drift. Edge case: an athlete-edited `race_modality_hints` JSONB with a typo (bypassing the form) silently drops. Acceptable for a v1 product target.
- The slice batches 15 files. Quality-degradation risk acknowledged. The ratification gate (Sequencing 3) made the cost-benefit explicit.

**Best argument against:**
- Path D (ship D-008b with static scores + flag race-craft as future work) would have been a 2-file slice today. Andy picked Path A explicitly. The architectural cost is paid for a real abstraction win — race-context-aware scoring is the right shape for any equipment-split discipline going forward.

---

**End of v2 amendment.**
