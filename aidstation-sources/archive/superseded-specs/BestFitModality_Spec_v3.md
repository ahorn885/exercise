# Best-Fit Training Modality — Spec v3 (Race-Leg Re-Model)

**Supersedes:** `BestFitModality_Spec_v2.md` (race-craft-aware scoring) and the relevant parts of `BestFitModality_Spec_v1.md` (resolver infra).
**Date:** 2026-05-24
**Status:** Spec. Slice 1 (remove race-craft-aware scoring) ships alongside this doc; the rest is sequenced in §12.

This is a re-model, not an increment. It changes the input data model (race legs become craft-specific disciplines with per-discipline terrain), reuses the deterministic terrain-gap machinery already in Layer 2B, moves craft-similarity judgment to the Layer 4 LLM, and **removes** the race-craft-aware scoring mechanism (`race_modality_hints` + the ×1.2 bump) shipped in v2.

---

## 0. Ratified decisions (AskUserQuestion gate, 2026-05-24)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| **R1** | Best-fit logic placement | **Hybrid** | Deterministic terrain proxy (reuse Layer 2B `terrain_gap_rules` fidelity) + LLM-side craft-similarity reasoning in Layer 4. Terrain proximity is already a tested, deterministic table; craft similarity ("kayak ≈ packraft") is a fuzzy judgment the LLM does well and would otherwise require new proximity data. Reverses v1's A2 "fully deterministic resolver" for the craft axis only. |
| **R2** | Race-leg data model | **Discipline-keyed terrain** | `race_terrain` becomes `{discipline_id: [{terrain_id, pct}]}`. A race terrain % only means something *within* a discipline (40% of the MTB leg is technical trail ≠ 40% of the race). |
| **R3** | Discipline granularity | **Pure-craft + separate terrain** | Disciplines are the craft (Packrafting, Kayaking, Mountain Biking); terrain is attached per discipline in the form. Un-bundles the craft+terrain disciplines (D-008a Flat-water Kayaking vs D-008b Whitewater Kayaking) and removes the discipline/terrain/race-craft triple-entry. |
| **R4** | Removed | **race-craft-aware scoring** | The race craft is *assumed* present on race day (athlete rents/borrows/race provides), so there is nothing to bump. `race_modality_hints` (column + editor + ×1.2 scoring + `race_craft_match`) is removed in Slice 1. |

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

`ModalityOption.race_craft_match` and `RaceEventPayload.race_modality_hints` are **removed** (Slice 1).

## 8. Coaching flags

1. `craft_unavailable` — athlete owns no craft in the race discipline's family (can't train craft-specifically).
2. `craft_substitution` — athlete will train on a proxy craft, not the race craft (informational; Layer 4 names the substitute).
3. `terrain_untrainable` — a race terrain (with its `pct`) has no usable locale proxy (unbridgeable / below fidelity floor) → compensation guidance.
4. `terrain_low_fidelity` — proxy exists but low fidelity; carries `adaptation_weeks` from `terrain_gap_rules`.

## 9. Caching & determinism

The deterministic half (terrain proxies) lives on the existing Layer 1 + 2B + 2C cone and is covered by existing eviction policies (`evict_layer2b_on_terrain_change`, `evict_layer2c_on_equipment_change`, `evict_layer1_on_skill_toggle_change`, `evict_on_target_event_included_discipline_ids_change`). Because craft selection is LLM-side, the Layer 4 cache key must include a hash of the assembled craft candidate set + per-discipline terrain mix (replacing v2's `race_modality_hints_hash` slot). The new `race_terrain` shape change invalidates affected entry points once on first deploy.

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
- **Slice 3 — data model:** `race_terrain` → discipline-keyed dict; form becomes discipline-centric (add a discipline → attach its terrain %); migrate existing rows. Trigger #3 (shape change consumed by Layer 2B).
- **Slice 4 — Layer 2B per-discipline terrain gaps:** key the terrain-gap output by discipline (the `RaceTerrainEntry.discipline_id` field already exists, currently unused).
- **Slice 5 — resolver re-model + Layer 4 craft reasoning:** implement §5; thread the craft candidate set + terrain emphasis into the Layer 4 prompt; update the cache key (§9). Trigger #1 (prompt change).
- **Slice 6 — renderers:** the 3 plan-gen prompt renderers consume `TrainingSubstitution` instead of the v2 modality payload.

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
