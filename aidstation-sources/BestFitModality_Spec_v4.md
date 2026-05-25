# Best-Fit Training Modality — Spec v4 (Race-Leg Re-Model)

**Supersedes:** `BestFitModality_Spec_v3.md` (slice-status reconciliation only — the design in §§1-11 + §13-14 is unchanged from v3). v3 in turn superseded `BestFitModality_Spec_v2.md` (race-craft-aware scoring) and the relevant parts of `BestFitModality_Spec_v1.md` (resolver infra).
**Date:** 2026-05-25 (v3: 2026-05-24)
**Status:** Spec. Slice 1 (remove race-craft-aware scoring) + Slice 2 (vocab / pure-craft display-name overlay) + Slice 4 (Layer 2B per-discipline terrain gaps) + Slice 5 (resolver re-model + Layer 4 craft reasoning — race_week_brief entry point) + **Slice 6 (renderer migration onto `TrainingSubstitution` across plan_create / plan_refresh + v2 retirement, shipped 2026-05-25)** shipped. **Slice 3 (data model) is satisfied on-disk under the ratified flat-list encoding — see §0 R5 + §12.** The re-model is **complete**: the v2 `Layer2ModalityPayload` resolver + its 3 renderers are retired; `resolve_training_substitution` is the sole best-fit node, threaded into all three race-prep entry points (single_session has no Layer 2B and intentionally carries no best-fit section — see §12 Slice 6).

**v4 delta (2026-05-25 reconciliation):** A session-start Rule #9 sweep + on-disk verification found that the Slice 3 *data model* — per-discipline terrain capture — was already shipped before this re-model, in the Bucket E.(c)-C1 slice (`e38c7ca`): `RaceTerrainEntry.discipline_id` exists and is populated by both the race-event edit form and onboarding step-3c via the shared `templates/_race_terrain_editor.html` per-row discipline `<select>`, parsed by `routes/race_events.py:_parse_race_terrain` + the onboarding mirror, round-tripped through `race_events_repo.py`, and unit-tested. At the 2026-05-25 ratification gate Andy picked the **flat-list-with-`discipline_id` encoding (R5)** over the literal nested dict, so this pre-shipped form *is* the Slice 3 deliverable. The spec's earlier "`discipline_id` … currently unused" wording (§12 Slice 4) refers to Layer 2B not yet *consuming* the field — the *capture* is live. Slice 3 therefore requires no further build; see §12.

This is a re-model, not an increment. It changes the input data model (race legs become craft-specific disciplines with per-discipline terrain), reuses the deterministic terrain-gap machinery already in Layer 2B, moves craft-similarity judgment to the Layer 4 LLM, and **removes** the race-craft-aware scoring mechanism (`race_modality_hints` + the ×1.2 bump) shipped in v2.

---

## 0. Ratified decisions (AskUserQuestion gate, 2026-05-24)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| **R1** | Best-fit logic placement | **Hybrid** | Deterministic terrain proxy (reuse Layer 2B `terrain_gap_rules` fidelity) + LLM-side craft-similarity reasoning in Layer 4. Terrain proximity is already a tested, deterministic table; craft similarity ("kayak ≈ packraft") is a fuzzy judgment the LLM does well and would otherwise require new proximity data. Reverses v1's A2 "fully deterministic resolver" for the craft axis only. |
| **R2** | Race-leg data model | **Discipline-keyed terrain** | `race_terrain` becomes `{discipline_id: [{terrain_id, pct}]}`. A race terrain % only means something *within* a discipline (40% of the MTB leg is technical trail ≠ 40% of the race). |
| **R3** | Discipline granularity | **Pure-craft + separate terrain** | Disciplines are the craft (Packrafting, Kayaking, Mountain Biking); terrain is attached per discipline in the form. Un-bundles the craft+terrain disciplines (D-008a Flat-water Kayaking vs D-008b Whitewater Kayaking) and removes the discipline/terrain/race-craft triple-entry. |
| **R4** | Removed | **race-craft-aware scoring** | The race craft is *assumed* present on race day (athlete rents/borrows/race provides), so there is nothing to bump. `race_modality_hints` (column + editor + ×1.2 scoring + `race_craft_match`) is removed in Slice 1. |

**Slice 3 ratification gate (AskUserQuestion, 2026-05-25):**

| # | Decision | Pick | Rationale |
|---|---|---|---|
| **R5** | Slice 3 terrain encoding | **Flat list with `discipline_id` populated** (not the literal R2 nested dict) | `RaceTerrainEntry` already carries an optional `discipline_id` per entry; populating it satisfies R2's *intent* (terrain % is per-discipline) with no consumer break — Layer 2B/3B/4 keep reading the flat list and ignore `discipline_id` until Slice 4 groups by it. The literal `{discipline_id: [...]}` dict would break every flat-list consumer and force a messy migration of existing untagged rows. Under R5 the Slice 3 data model is already on-disk (Bucket E.(c)-C1); no further build. |
| **R6** | Two ID collapses (kayak D-008a/b, mtn-running D-022/D-023) | **Defer to a dedicated id-change session** | The collapses carry renumber-class blast radius (`Sports_Framework_v10.xlsx` edit + Neon re-extract + ~40 cross-layer consumers + the silent name-coupling that drove the Slice-2 overlay decision). Their *safety* depends on the per-discipline terrain axis being **consumed** (Slice 4), not just captured (Slice 3) — collapsing earlier would flatten differentiated data before the axis that carries it is live. Cleanest after Slice 4, riding the dedicated session the M-renum decision already reserved. |

---

## 1. Purpose

Given a race described as a set of **craft-specific disciplines**, each with its own **terrain breakdown**, and given what the athlete actually has to train with (available crafts + locale terrain + skills), produce a per-discipline **training-substitution brief**: the closest trainable craft, the terrain training emphasis (weighted by how much of that leg is on each terrain and how well the athlete can reproduce it), and explicit flags for what cannot be trained.

The classic example (Andy's words):

> Race leg = Packrafting, terrain 10% lake / 80% river / 10% whitewater. Athlete owns a kayak and a canoe; has a lake and a river at home, no whitewater. Best-fit: train on the river in the kayak (kayak is closer to a packraft than a canoe; river is the biggest *trainable* chunk and the closest proxy for whitewater), and flag that whitewater can't be trained directly so we compensate.

## 2. What this does NOT do (boundaries)

1. It does **not** model the race itself — the race craft is assumed available on race day. No "race mandates this craft" scoring (removed; see R4).
2. It does **not** pick the final per-session modality — that stays in Layer 4 with full phase/history context. This node **narrows + annotates**; it does not decide (menu-not-decision, carried from v1 §D5).
3. It does **not** invent a deterministic craft-proximity table. Craft similarity is reasoned by the Layer 4 LLM from the candidate set this node assembles (R1).
4. No phase weighting, no exercise prescription, no schedule emission, no DB writes, no injury accommodation.

## 3. Inputs / function signature

The node consumes, per included race discipline:
- the **race craft** (derived from the pure-craft discipline; R3),
- the **per-discipline terrain breakdown** `[{terrain_id, pct}]` (R2),
- the athlete's **available crafts** for that discipline family (sourced from Layer 1 discipline baselines — e.g. `paddle_craft_types` — and Layer 2C equipment),
- the athlete's **locale terrain set** + **skill-toggle states**.

```python
def resolve_training_substitution(
    db,
    *,
    race_legs: list[RaceLeg],                 # per-discipline craft + terrain breakdown
    athlete_crafts: dict[str, list[str]],     # discipline_family -> owned crafts
    cluster_locale_inputs: list[ClusterLocaleInput],
    skill_toggle_states: dict[str, bool] | None = None,
    etl_version_set: dict[str, str] | None = None,
) -> TrainingSubstitutionPayload
```

`RaceLeg`: `discipline_id`, `craft` (canonical), `terrain: list[{terrain_id, pct}]`.

The terrain-proxy computation is delegated to Layer 2B (`terrain_gap_rules`), per discipline, rather than re-derived here (avoids duplicating §1 of Layer 2B).

## 4. Input validation

1. `race_legs` non-empty; each `discipline_id` matches `^D-\d{3}[a-z]?$` and exists in `sport_discipline_bridge` for the framework sport.
2. Each leg's terrain `pct` values are in `[0, 100]`; per-leg sum within `[80, 120]` tolerance (Layer 2B owns the tolerance; mirror v1 §4). Empty terrain list is allowed (→ craft-only substitution, no terrain emphasis).
3. `terrain_id` matches `^TRN-\d{3}$`.
4. Fail loud with `Layer2ModalityInputError`.

## 5. Algorithm

Per race leg (discipline D with craft C_race and terrain mix T):

**5.1 Terrain emphasis (deterministic — reuse Layer 2B).**
For each race terrain `t ∈ T` with weight `pct_t`, ask Layer 2B for the best trainable proxy from the athlete's locale terrain: `(proxy_terrain, fidelity, gap_severity, proxy_methods, uncoverable_stimulus)`. Rank the leg's terrain training emphasis by `pct_t × fidelity` (focus the biggest *trainable* chunk). Terrains whose best proxy is `NULL`/unbridgeable or below a fidelity floor are emitted as **untrainable-terrain gaps** with their `pct_t` (so Layer 4 can say "X% can't be trained — compensate").

**5.2 Craft candidate set (assembled here; chosen LLM-side — R1).**
Assemble the athlete's owned crafts in C_race's family (e.g. for Packrafting: kayak, canoe). This node does **not** score them; it hands the candidate set + the race craft to Layer 4, which reasons about closeness ("kayak is more like a packraft than a canoe"). If the athlete owns the race craft itself, that's surfaced as the trivial top candidate. If the family is empty, emit a `craft_unavailable` flag.

**5.3 Output assembly.**
Per discipline, emit a `TrainingSubstitution` carrying: race craft, the ranked terrain emphasis (with proxies + fidelity), the untrainable-terrain gaps, the craft candidate set, and coaching flags (§8). Layer 4 turns this into prose: pick the closest craft, allocate terrain emphasis, and write the compensation guidance for the gaps.

## 6. Skill-toggle gating

Unchanged from v1 §6 / BucketC_l: a craft/terrain that requires a skill capability (e.g. `whitewater_handling`) is only offered as *trainable* when the toggle is ON. Default-OFF omits it and contributes to the untrainable-terrain narrative. The race-side craft is unaffected (assumed available).

## 7. Payload schema (pydantic `_Base`)

- `TrainingSubstitutionPayload`: `recommendations: list[TrainingSubstitution]`, `coaching_flags: list[ModalityCoachingFlag]`.
- `TrainingSubstitution`: `discipline_id`, `discipline_name`, `race_craft`, `candidate_training_crafts: list[str]`, `terrain_emphasis: list[TerrainEmphasis]`, `untrainable_terrain: list[TerrainGapRef]`.
- `TerrainEmphasis`: `race_terrain_id`, `pct`, `proxy_terrain_id`, `fidelity`, `gap_severity`, `proxy_methods`, `uncoverable_stimulus`.
- `ModalityCoachingFlag`: `flag_type` Literal (§8), metadata.

> **Slice-5 as-built (2026-05-25):** the flags type is a dedicated `TrainingSubstitutionFlag` (not the v2 `ModalityCoachingFlag` — the §8 set is disjoint from its Literal); `TerrainEmphasis` also carries `terrain_name` / `proxy_terrain_name` / `emphasis_score` (= `pct × fidelity`, ranking transparency); `TerrainGapRef` carries `terrain_name` + a `reason` string. All in `layer4/context.py`.

`ModalityOption.race_craft_match` and `RaceEventPayload.race_modality_hints` are **removed** (Slice 1).

## 8. Coaching flags

1. `craft_unavailable` — athlete owns no craft in the race discipline's family (can't train craft-specifically).
2. `craft_substitution` — athlete will train on a proxy craft, not the race craft (informational; Layer 4 names the substitute).
3. `terrain_untrainable` — a race terrain (with its `pct`) has no usable locale proxy (unbridgeable / below fidelity floor) → compensation guidance.
4. `terrain_low_fidelity` — proxy exists but low fidelity; carries `adaptation_weeks` from `terrain_gap_rules`.

## 9. Caching & determinism

The deterministic half (terrain proxies) lives on the existing Layer 1 + 2B + 2C cone and is covered by existing eviction policies (`evict_layer2b_on_terrain_change`, `evict_layer2c_on_equipment_change`, `evict_layer1_on_skill_toggle_change`, `evict_on_target_event_included_discipline_ids_change`). Because craft selection is LLM-side, the Layer 4 cache key must include a hash of the assembled craft candidate set + per-discipline terrain mix (replacing v2's `race_modality_hints_hash` slot). The new `race_terrain` shape change invalidates affected entry points once on first deploy.

> **Slice-5 as-built (2026-05-25):** `race_modality_hints_hash` was already removed in Slice 1, so the new `training_substitution_hash` is added as its **own** key slot in `race_week_brief_key`. Computed via `compute_payload_hash(training_substitution_payload)` in `llm_layer4_race_week_brief_cached`; `None → ''` for forward-compat; the new slot shifts the key once on first deploy (the expected one-time invalidation). No new eviction helper — the substitution payload derives entirely from the Layer 1 + 2B inputs already covered by the policies above.

> **Slice-6 as-built (2026-05-25):** `training_substitution_hash` slots added to `plan_create_key` (replacing the v2 `layer2_modality_hash` slot) and `plan_refresh_key` (net-new slot); the v2 `layer2_modality_hash` slot was removed from `plan_create_key` + `race_week_brief_key`, and `layer2_modality_locale_hash` from `single_session_synthesize_key`. These three key-shape changes each shift the key once on first deploy — the expected one-time invalidation. No new eviction helper (the substitution payload derives from the Layer 1 + 2B cone already covered). single_session keeps no best-fit cache slot (it has no Layer 2B → no substitution payload).

## 10. Edge cases

1. Leg with empty terrain → craft-only substitution; no terrain emphasis; no terrain flags.
2. Athlete owns the exact race craft → trivial top candidate; terrain emphasis still computed.
3. All of a leg's terrain untrainable → all-gap; Layer 4 surfaces a "no on-terrain training available" narrative.
4. Discipline absent from the athlete's locale/equipment entirely → `craft_unavailable` + all-terrain-gap.
5. Pure-craft disciplines that map to the same craft on different terrains (old D-008a/b) collapse to one craft + terrain breakdown under the new model.

## 11. Performance budget

One Layer 2B terrain-gap roundtrip per (discipline, locale) (already budgeted); pure-Python assembly otherwise. No new per-call LLM cost in this node — the craft reasoning rides inside the existing Layer 4 synthesis call.

## 12. Open items / slice sequence

- **Slice 1 (ships with this spec):** remove race-craft-aware scoring (`race_modality_hints` column + editor + ×1.2 bump + `race_craft_match` + the v2 tests/§5.0). Reverts the resolver to its pre-race-craft base. KEEP the D-008b vocab + K3 equipment ETL.
- **Slice 2 — vocab:** pure-craft disciplines + curated display names (a `display_name` surfaced to the UI, sourced from the canonical Sheet-2 names, not Sheet-3 sport-variant labels) + AR bridge coverage (e.g. decide road cycling label, whether XC skiing bridges to AR). Trigger #2 per discipline.
- **Slice 3 — data model:** ✅ **Satisfied on-disk (no build owed).** Under R5 (flat list with `discipline_id` populated), the per-discipline terrain *capture* already shipped in Bucket E.(c)-C1 (`e38c7ca`): per-row `discipline_id` `<select>` on both the race-event edit form and onboarding step-3c (shared `templates/_race_terrain_editor.html`), parsed by both routes' `_parse_race_terrain`, stored/read via `race_events_repo.py`, and unit-tested in `test_routes_race_events` / `test_onboarding_race_events` / `test_race_events_repo`. No row migration is needed (existing rows carry `discipline_id=None` = race-wide, graceful). The discipline tag is currently *optional* ("Race-wide"); whether to require it per row is deferred to Slice 4, when the field is first *consumed* and the multi-discipline-only nature of the requirement is decidable (a single-discipline race's "race-wide" == its one discipline, so a global requirement would be wrong). _The original R2 plan was a literal `{discipline_id: [{terrain_id, pct}]}` dict + discipline-centric form + row migration (Trigger #3); R5 supersedes it._
- **Slice 4 — Layer 2B per-discipline terrain gaps: ✅ SHIPPED 2026-05-25.** Layer 2B now *consumes* `RaceTerrainEntry.discipline_id`: additive `Layer2BPayload.terrain_by_discipline: list[Layer2BDisciplineBlock]` (one block per included discipline; race-wide `None` entries fold into every block, tagged wins over race-wide for the same terrain; per-block coverage/gaps/summary recomputed over the subset reusing the flat gap records — no extra SQL). `RaceTerrainOutput.discipline_id` added (pass-through on the flat list; stamped block discipline on blocks). **Discipline tag ratified OPTIONAL** (Trigger #3 gate, 2026-05-25): `None` = race-wide; NOT required per row (single-discipline races' race-wide == their one discipline, and existing rows are all `None`). **Output ratified ADDITIVE**: flat `race_terrain`/`terrain_gaps`/`summary` unchanged for backward compat (Slice 6 migrates renderers); one-time downstream cache invalidation on first deploy (§9; no new eviction helper). Files: `layer4/context.py` (+`Layer2BDisciplineBlock`, +`discipline_id` on `RaceTerrainOutput`, +`terrain_by_discipline`), `layer2b/builder.py` (`_build_discipline_blocks`), `tests/test_layer2b.py` (+10 in `TestPerDisciplineBlocks`), `Layer2B_Spec.md` (§3/§5.6/§7/§9/§10 amended in place). Trigger #3 satisfied (Layer 2B contract change; ratified at gate). The optional-vs-required question the spec deferred to this slice is now **resolved (optional)**.
- **Slice 5 — resolver re-model + Layer 4 craft reasoning: ✅ SHIPPED 2026-05-25 (race_week_brief entry point).** Trigger #1 ratified at an AskUserQuestion gate (3 decisions: full Slice 5 with a ratified ceiling break; craft candidates = all owned crafts handed to the LLM, no family table; output additive alongside the v2 `Layer2ModalityPayload`). New `resolve_training_substitution` (`layer2_modality/substitution.py`) consumes the Slice-4 `Layer2BPayload.terrain_by_discipline` blocks directly — **no `db` param, no extra SQL** (the terrain-proxy work is the delegated 2B output per §3). Per discipline it emits a `TrainingSubstitution` (race craft = pure-craft display label; `candidate_training_crafts` = the athlete's owned crafts verbatim; `terrain_emphasis` ranked by `pct × fidelity`; `untrainable_terrain` for proxies that are unbridgeable / undefined / below the fidelity floor 0.25) + flags (`terrain_untrainable`, `terrain_low_fidelity` < 0.60, `craft_unavailable` when zero crafts logged). Wired through `_upstream_full_cone` → `llm_layer4_race_week_brief_cached` (new `training_substitution_hash` cache slot in `race_week_brief_key`, one-time invalidation on first deploy per §9) → `_render_training_substitution_section` in the brief prompt body (additive — alongside the BM-3 modality section). Files: `layer4/context.py` (+5 types), `layer2_modality/substitution.py` (new) + `__init__.py` export, `layer4/orchestrator.py`, `layer4/hashing.py`, `layer4/cached_wrappers.py`, `layer4/race_week_brief.py`, tests (`tests/test_layer2_substitution.py` new + hashing/orchestrator/brief updates). **As-built deviations from this spec:** §3's `resolve_training_substitution(db, *, race_legs, athlete_crafts: dict, cluster_locale_inputs, ...)` signature is replaced by a db-less `(terrain_by_discipline, athlete_crafts: list, etl_version_set, discipline_names=None)` shape (the 2B blocks ARE the per-leg terrain; `athlete_crafts` is a flat list per gate Q2); §7's `coaching_flags: list[ModalityCoachingFlag]` is a dedicated `TrainingSubstitutionFlag` type (the §8 flag set is disjoint from the v2 `ModalityCoachingFlag` Literal); `craft_substitution` (§8.2) is surfaced LLM-side via the candidate set rather than emitted deterministically (no `discipline_id → craft-token` map under gate Q2); skill-gated terrain/craft (§6) is not deterministically gated this slice (no skill→terrain map; the untrainable narrative carries it). **Scope:** wired for the race_week_brief entry point only (the full-cone entry point that already threads the v2 modality payload + is the PGE forcing function); single_session is N/A (its cone has no Layer 2B → no terrain breakdown); plan_create / plan_refresh threading folds into Slice 6 (matches their pre-existing v2-modality threading deferral).
- **Slice 6 — renderers + remaining entry points + v2 retirement: ✅ SHIPPED 2026-05-25.** Trigger #1 ratified at an AskUserQuestion gate (2 decisions: **(1)** single_session drops its modality section entirely — full v2 retirement — because single_session's cone has no Layer 2B so it structurally cannot produce a `TrainingSubstitution`; the locale `effective_pool` + discipline coverage already in its prompt carry the raw availability signal; **(2)** full retirement in one session with a ratified ceiling break). The plan-gen renderer migrated onto `TrainingSubstitution`: `per_phase.py`'s `_format_modality_recommendations_per_phase` → `_format_training_substitution_per_phase` (compact `=== … ===` idiom; race craft + candidate crafts + `pct × fidelity` terrain emphasis + untrainable terrain + flags). The substitution payload (already on `_UpstreamFullCone`) is threaded into **plan_create** (`_run_pattern_a_engine` → `synthesize_phase` → `render_user_prompt`) and **plan_refresh** (`llm_layer4_plan_refresh` → all three tier `render_user_prompt`s T1/T2/T3, which import the shared per_phase renderer). Cache slots: `training_substitution_hash` added to `plan_create_key` (swapped in for the v2 `layer2_modality_hash`) + `plan_refresh_key` (net-new); `llm_layer4_plan_create_cached` / `llm_layer4_plan_refresh_cached` accept + hash + thread it. **v2 retired:** `resolve_best_fit_modality` + `_MODALITY_OPTIONS_PER_DISCIPLINE` + `ClusterLocaleInput` + `ModalityOptionDef` + the three `_render_modality_section_*` renderers + the `Layer2ModalityPayload`/`ModalityOption`/`ModalityRecommendation`/`ModalityCoachingFlag` types are deleted; `layer2_modality/resolver.py` is removed entirely (the surviving `Layer2ModalityInputError`, reused by `resolve_training_substitution`, moved into `substitution.py`). Files: `layer4/context.py`, `layer4/orchestrator.py`, `layer4/hashing.py`, `layer4/cached_wrappers.py`, `layer4/per_phase.py`, `layer4/plan_create.py`, `layer4/plan_refresh.py` (+ `_t1`/`_t2`/`_t3`), `layer4/race_week_brief.py`, `layer4/single_session.py`, `layer2_modality/__init__.py` + `substitution.py`; deleted `layer2_modality/resolver.py` + `tests/test_layer2_modality.py`; `tests/test_layer4_hashing.py` migrated. **Tests:** full suite 1631 passed / 16 skipped (the −49 vs Slice 5's 1680 is the deleted v2 resolver test file + the hashing-test migration; zero regressions). The re-model is now complete — one best-fit node, no parallel v2 path.

## 13. Test scenarios

1. **Packraft @ Andy's locale** — leg Packrafting 10/80/10 lake/river/whitewater; athlete owns kayak+canoe, has lake+river. Expect: candidate crafts = [kayak, canoe]; terrain emphasis ranks river top (0.80 × fidelity); whitewater → `terrain_untrainable` with pct=10; flag set includes `craft_substitution`.
2. **Owns the race craft** — athlete owns a packraft → packraft is the top candidate; no `craft_substitution`.
3. **No craft in family** — athlete owns no paddle craft → `craft_unavailable`.
4. **Empty terrain leg** — craft-only; no terrain emphasis/flags.
5. **All-terrain-untrainable** — every race terrain unbridgeable at the locale → all gaps; no emphasis.
6. **Skill-gated terrain** — whitewater requires `whitewater_handling`; OFF → contributes to untrainable narrative; ON → trainable if locale has the terrain.
7. **Pure-craft collapse** — a race historically split as D-008a/D-008b collapses to one Kayaking leg with a terrain breakdown.

## 14. Gut check

- **Risk:** 6-slice re-model that un-ships fresh work — churn. Mitigated by keeping the vocab + ETL and reusing 2B.
- **What might be missing:** the craft "family" grouping (which owned crafts count as candidates for which race craft) is implicit; if the LLM needs a hint, a coarse family tag on the discipline/equipment vocab may be needed (Slice 2 candidate). Watch for the LLM over-substituting (recommending a canoe for a packraft when it shouldn't) — the candidate set + a short rationale line should constrain it.
- **Best argument against:** the hybrid splits the best-fit logic across a deterministic node (terrain) and the LLM (craft), which is two places to reason about one decision. The counter: terrain proximity is genuinely tabular and tested; craft similarity is genuinely fuzzy and low-cardinality, so the split follows the grain of each sub-problem. If craft selection proves unreliable LLM-side, Slice 5 can add a small deterministic craft-family proximity table without disturbing the rest.

---

*End of Spec v3.*
