# Modality Group — Spec v1

**Date:** 2026-06-07
**Author:** Claude + Andy
**Status:** DRAFT — design pending sign-off before implementation
**Supersedes:** N/A (new spec)
**Related specs:** `BestFitModality_Spec_v4.md` §14 (the deferred escape hatch this spec ships); `Layer2C_Spec.md` §5.1 (toggle handling — adjacent to but distinct from groups); `Layer2A_Spec.md` (consumer); `Layer0_ETL_Spec_v7.md` (ETL substrate)
**Companion docs (to be written alongside implementation):** `Bridge_Bands_Research_v1.md` (X1a research substrate)

---

## 1. Purpose

Establish a **deterministic vocabulary of training-equivalent discipline groups** ("modality groups") that:

1. Lets Layer 2A's load_weight allocation **pool** weight across training-equivalent disciplines (e.g., race specifies kayak at 20%, athlete trains packraft, both belong to `paddle` group → packraft training counts toward the 20% paddle allocation).
2. Replaces the LLM-inferred craft-family reasoning that `layer2_modality/substitution.py` currently delegates to Layer 4 synthesis (per `BestFitModality_Spec_v4.md` §14: *"if craft selection proves unreliable LLM-side, Slice 5 can add a small deterministic craft-family proximity table without disturbing the rest"*). The condition is fulfilled by Andy's directive in this session — the LLM-driven inference is being replaced by deterministic group membership.
3. Provides shared vocabulary across Layer 2A (allocation), Layer 2C (equipment routing), and Layer 2's `resolve_training_substitution` (synthesis-time substitution). One source of truth for "these N disciplines are interchangeable for training purposes."

**Scope of "training-equivalent":** Two disciplines belong to the same group if **the training stress they impose is substantially similar at the system level** (cardiopulmonary load, primary movement pattern, dominant muscle groups, injury-risk profile). The group concept is NOT about race-equivalence — a race that specifies "kayak" is not interchangeable with "packraft" from the race director's perspective — but for *training* the athlete's home-craft work transfers across the group.

---

## 2. What modality groups do NOT do

- **Not race-equivalence.** A race that specifies kayak still requires kayak craft on race day. The athlete who trains packraft is gaps-aware at race time (a coaching flag flags it). Groups are about *training stimulus transfer*, not equipment substitution at the race itself.
- **Not terrain substitution.** Terrain proxies (groomed trail → singletrack trail) are Layer 2B's domain. Groups are discipline-level; terrain stays separate.
- **Not equipment substitution at the locale level.** Layer 2C handles "this gym has these tools." Groups operate one level up: even before equipment, are these two disciplines training-equivalent?
- **Not athlete-overridable in v1.** The group vocabulary is reference data (ETL-loaded, locked by version). Athletes cannot declare custom groups. v2 may allow opt-out per-group if the LLM substitution proves to lose nuance the deterministic table can't capture.
- **Not nested or hierarchical.** A discipline belongs to zero, one, or many groups (many-to-many) but groups themselves don't contain other groups. The vocabulary is flat.

---

## 3. Data shape

### 3.1 New Layer 0 tables

```sql
CREATE TABLE layer0.modality_groups (
    group_id       TEXT PRIMARY KEY,              -- e.g. 'paddle', 'foot_trail'
    group_name     TEXT NOT NULL,                 -- athlete-facing label
    group_kind     TEXT NOT NULL,                 -- closed enum (§3.3)
    description    TEXT NOT NULL,                 -- 1-2 sentence rationale
    etl_version    TEXT NOT NULL,
    superseded_at  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE layer0.discipline_modality_membership (
    discipline_id  TEXT NOT NULL,                 -- references layer0.disciplines.discipline_id by string
    group_id       TEXT NOT NULL REFERENCES layer0.modality_groups(group_id),
    etl_version    TEXT NOT NULL,
    superseded_at  TIMESTAMPTZ,
    PRIMARY KEY (discipline_id, group_id, etl_version)
);
```

**Why two tables:**
- A single column on `layer0.disciplines` would force a one-group-per-discipline shape. A discipline like D-001 (Trail Running) is plausibly in `foot_trail` (its dominant training stress) AND `foot_running` (a broader running group). Many-to-many membership preserves both relationships.
- A single column on `layer0.sport_discipline_bridge` would scope the group to a particular sport (paddle is paddle in AR but maybe different in Triathlon). That's wrong — paddle equivalence is a property of the disciplines, not of the sport that includes them.
- Membership table at Layer 0 with `etl_version` follows the existing pattern (`disciplines`, `terrain_types`, `sport_discipline_bridge` all carry `etl_version` + `superseded_at` for the standard rebuild flow).

### 3.2 Initial vocabulary (seed for ETL v1.4.0)

Closed seed set; revisable in subsequent ETL versions only.

| group_id | group_name | group_kind | Initial member disciplines |
|---|---|---|---|
| `paddle_flatwater` | Flatwater paddle | `paddle` | D-009 Packrafting, D-010 Flat-water Kayaking, D-011 Canoeing |
| `paddle_whitewater` | Whitewater paddle | `paddle` | D-010 Whitewater Kayaking |
| `foot_trail` | Foot-on-trail | `foot` | D-001 Trail Running, D-003 Hiking (Weighted) |
| `foot_road` | Foot-on-road | `foot` | D-002 Road Running |
| `bike_pavement` | Bike on pavement | `bike` | D-006 XC Cycling (Road/Gravel) |
| `bike_offroad` | Bike off-road | `bike` | D-008 Mountain Biking |
| `snow_travel` | Snow travel (foot/snowshoe) | `snow` | D-017 Snowshoeing, D-018 Mountaineering (snow sections) |
| `snow_glide` | Snow travel (gliding) | `snow` | Skimo disciplines, Cross-Country Nordic disciplines |
| `climb_rope` | Rope-protected climbing | `climb` | D-012 Rock Climbing, D-014 Via Ferrata |
| `climb_descent` | Rope descent | `climb` | D-013 Abseiling |
| `swim_openwater` | Open-water swim | `swim` | D-004 Open Water Swimming, D-016 Swimming (in open water context) |

**Ungrouped disciplines** (intentionally — no equivalent training stimulus): D-015 Orienteering/Nav (skill overlay, not a physical stimulus), single-row disciplines in mono-sport bridges.

**Note on D-001 vs D-002:** Trail Running and Road Running are NOT in the same group. The training stresses differ (impact distribution, eccentric loading, pacing) enough that transfer is incomplete. If real plan data shows over-aggressive separation, v2 may add a `foot_running_generic` super-group; not in v1.

### 3.3 Closed-enum `group_kind`

`paddle` | `foot` | `bike` | `snow` | `climb` | `swim` | `nav` (reserved, currently empty)

`group_kind` is used for analytics + coaching-flag categorization. It does NOT influence the pooling/redistribution algorithm — that's keyed entirely on `group_id` membership.

---

## 4. Input validation (preconditions)

When Layer 2A is called and the bridge load returns rows with disciplines, the modality-group lookup runs:

1. **Vocabulary load**: `_load_modality_groups(db, etl_version_0a)` returns `dict[group_id, list[discipline_id]]` and `dict[discipline_id, list[group_id]]` (the inverse). Empty dict is valid (back-compat: if ETL hasn't loaded groups yet, Layer 2A behavior is identical to current — every discipline is its own pool).
2. **Membership FK soundness**: each `discipline_id` in `discipline_modality_membership` must exist in `layer0.disciplines` at the same `etl_version`. Validated at ETL time (`etl/layer0/...` extractor), not runtime.
3. **No empty groups**: every `group_id` in `modality_groups` must have ≥1 member at the same `etl_version`. Also ETL-time. (Empty groups would produce NaN in the redistribute step.)

Runtime failure modes:
- **Discipline in `included_discipline_ids` but in zero groups**: legitimate (e.g., D-015 Orienteering). Treated as its own singleton pool. NO error.
- **Discipline in `included_discipline_ids` not in `layer0.disciplines`**: existing Layer 2A error (`Layer2AInputError("discipline_not_in_bridge")`). Unchanged.

---

## 5. Algorithm (Layer 2A integration)

The grouping concept changes Layer 2A's load_weight computation. The current flow (`layer2a/builder.py:_compute_load_weight` + `_normalize_load_weights`) computes per-discipline load_weight independently, then normalizes. The new flow adds a pooling step.

### 5.1 Step-by-step

Given inputs to Layer 2A:
- `included_discipline_ids` — the discipline set after `discipline_id_filter` applied
- `race_discipline_overrides` — `dict[discipline_id, weight_pct]` from `_derive_race_discipline_mix` (race terrain × pct × discipline aggregation, X3)
- `athlete_discipline_overrides` — `dict[discipline_id, weight_pct]` from `Layer1Payload.training_history.discipline_weighting` (X2)
- Bridge rows — per-discipline `race_time_pct_low/high` midpoints

**Algorithm:**

```
1. For each discipline d in included_discipline_ids:
     - base_weight[d] = bridge midpoint(d)
     - race_weight[d] = race_discipline_overrides.get(d)        # None or float
     - athlete_weight[d] = athlete_discipline_overrides.get(d)  # None or float

2. For each modality group g containing 2+ disciplines in included_discipline_ids:
     a. members[g] = disciplines in g ∩ included_discipline_ids
     b. pool_race[g]    = sum(race_weight[d] for d in members[g] if race_weight[d] is not None)
        pool_athlete[g] = sum(athlete_weight[d] for d in members[g] if athlete_weight[d] is not None)
        pool_base[g]    = sum(base_weight[d] for d in members[g])
     c. # Redistribute within group per precedence:
        for d in members[g]:
            if race_weight[d] is not None:
                final[d] = race_weight[d]                              # Race tag wins per-member
            elif pool_race[g] > 0:
                # Race tagged some group members but not this one — redistribute pool fairly
                # to untagged members based on next-layer signal
                if athlete_weight[d] is not None:
                    share = athlete_weight[d] / pool_athlete_untagged
                else:
                    # No athlete signal either — even split among untagged
                    share = 1.0 / count_untagged
                final[d] = pool_race[g] * 0   # already in race-tagged members; this member gets athlete/base
                # (See §5.2 for the exact untagged-share calculation.)
            elif athlete_weight[d] is not None:
                final[d] = athlete_weight[d]
            else:
                # Pure bridge member — proportional share of group pool from base
                final[d] = base_weight[d]

3. For disciplines NOT in any multi-member group:
     - Singleton: final[d] = race_weight[d] ?? athlete_weight[d] ?? base_weight[d]

4. _normalize_load_weights:
     - rescale all final[d] so the included set sums to 1.0
     - (existing behavior; unchanged)
```

### 5.2 Worked example — your PGE plan #61

Inputs:
- `included_discipline_ids` = {D-001 TR, D-003 Trek, D-008 MTB, D-009 Packraft, D-012 Rock, D-013 Abseil}
- `race_discipline_overrides` (from race terrain × pct × discipline): {D-001: 20, D-003: 15, D-008: 45, D-009: 20}
- `athlete_discipline_overrides`: {} (empty — you haven't filled it in)
- Bridge midpoints (AR row): {D-001: 20, D-003: 15, D-008: 15, D-009: 10, D-012: 2.5, D-013: 1}

Groups (using v1 seed):
- `foot_trail` = {D-001, D-003} — both in included set, both race-tagged
- `paddle_flatwater` = {D-009} — only one member in included set → singleton, no pooling
- `bike_offroad` = {D-008} — singleton
- `climb_rope` = {D-012} — singleton (D-014 not included)
- `climb_descent` = {D-013} — singleton

Per-discipline:
- D-001 (TR): race-tagged 20 → final = 20
- D-003 (Trek): race-tagged 15 → final = 15
- D-008 (MTB): race-tagged 45 → final = 45
- D-009 (Packraft): race-tagged 20 → final = 20
- D-012 (Rock): no race/athlete → bridge fallback → final = 2.5
- D-013 (Abseil): no race/athlete → bridge fallback → final = 1

Sum before normalize: 103.5
After normalize (divide each by 103.5):
- D-001 (TR): **0.193** (19.3%)
- D-003 (Trek): 0.145 (14.5%)
- D-008 (MTB): **0.435** (43.5%) ← was 0.236 (23.6%) under old behavior
- D-009 (Packraft): 0.193 (19.3%)
- D-012 (Rock): 0.024 (2.4%)
- D-013 (Abseil): 0.010 (1.0%)

Compare to current plan #61 hour distribution: TR 31% / Trek 23% / MTB 16% / Packraft 12% / Rock 7% / Abseil <1%. New allocation: TR 19% / Trek 15% / MTB 44% / Packraft 19% / Rock 2% / Abseil 1%. MTB becomes the dominant discipline as the race spec demands.

### 5.3 Worked example — group-pooling scenario

Hypothetical: race tags D-010 Kayak at 20%, athlete owns D-009 Packraft only.

Inputs:
- `included_discipline_ids` = {D-009, D-010}
- `race_discipline_overrides` = {D-010: 20}
- `athlete_discipline_overrides` = {}
- Bridge midpoints: {D-009: 10, D-010: 10}

Groups:
- `paddle_flatwater` = {D-009, D-010}

Per-discipline (using §5.1 step 2c):
- pool_race[paddle_flatwater] = 20
- D-010: race-tagged → final = 20
- D-009: not race-tagged; pool_race > 0; no athlete signal → even-split among untagged. count_untagged = 1 (just D-009). The athlete owns D-009 (per separate Layer 2C check), so the training stress flows there.

Question for §5.4 design call: when race tags one member and athlete owns another, does the system **redirect** the race weight to the athlete-owned member, OR **add** it on top?

**Decision (recommend for v1):** REDIRECT. Race-tagged D-010 weight of 20 transfers to D-009 because that's the athlete's actual training surface. final[D-009] = 20, final[D-010] = 0. Plan generates D-009 (packraft) sessions for the 20% paddle allocation. A coaching flag emits: `training_craft_substitution: kayak training redirected to packraft (athlete owns packraft, not kayak).`

This is the cleanest interpretation of "training-equivalent group." The race specifies a 20% paddle leg; the athlete's training serves that 20% on whatever craft they own.

Alternative considered: SPLIT 50/50 between members and let athlete train both. Rejected because it forces athletes who don't own kayak to underprepare. Andy can override via athlete_discipline_overrides if they want a different split.

### 5.4 Open design call

Two redistribute behaviors when athlete signal exists but doesn't cover all group members:
- **(A)** Athlete signal is partial → use bridge midpoints for the gap members
- **(B)** Athlete signal is the full vocabulary → un-mentioned members get 0

Recommend **(A)** for v1 — athletes shouldn't have to enumerate every discipline; bridge fills gaps. Pair with a coaching flag `athlete_weighting_incomplete` if the explicit weights cover < 80% of the group pool.

---

## 6. Layer 2C integration

The existing Layer 2C equipment-routing logic uses `also_satisfies` chains from `layer0.sport_specific_gear_toggles` (per `Layer2C_Spec.md` §6). The new modality groups are CONCEPTUALLY adjacent but operationally distinct:

- `also_satisfies` = "this toggle (e.g., 'has_indoor_trainer') gives you equipment that satisfies these other toggles." Toggle-to-toggle.
- `modality_group` = "these disciplines impose training-equivalent stress." Discipline-to-discipline.

**Wiring:** Layer 2C reads `layer0.discipline_modality_membership` when resolving substitution candidates. Today's flow (`q_layer2c_equipment_mapper_payload`) checks "do I have equipment for D-009?" — if no, returns `discipline_low_coverage`. New flow: if no equipment for D-009 but yes for D-010 (same `paddle_flatwater` group), surface D-010 as a training-substitution candidate with a `craft_substitution_via_group` flag.

**`resolve_training_substitution` change** (`layer2_modality/substitution.py`):

Today's behavior: hands the full set of `athlete_crafts` to Layer 4 LLM and lets it reason about which is closest to the race craft. Per §14 of `BestFitModality_Spec_v4.md`, this was the deferred-LLM choice.

New behavior (v1):
1. Look up the race-craft's `modality_group_id` set.
2. Filter `athlete_crafts` to those in the same group(s).
3. Hand the filtered candidate set to Layer 4 (still LLM-driven for the final pick — the LLM is best at "kayak feels closest to packraft vs canoe" within the candidate set).
4. Emit `craft_substitution` if filtered set differs from raw set.
5. Emit `craft_unavailable` if filtered set is empty (athlete owns no group member).

**This narrows the LLM's input** from "all owned crafts" to "all owned crafts in the right modality group." Doesn't replace the LLM call — the LLM is still the right tool for nuanced pick within candidates — but constrains the choice to deterministic equivalence first.

---

## 7. Payload schema

No new payload types in Layer 2A. The existing `Layer2ADiscipline.load_weight.value` carries the post-group-pool, post-normalize weight. The pooling is transparent to downstream consumers; they see one weight per discipline.

For diagnostics + the diag endpoint, Layer 2A's `synthesis_metadata` (when called from orchestrator) gains a new field:

```python
class ModalityGroupAllocation(BaseModel):
    group_id: str
    members: list[str]                # discipline_ids
    pool_race: float | None           # sum of race signal for this group
    pool_athlete: float | None
    pool_base: float                  # always present
    per_member_final: dict[str, float]  # post-pool final weights
    flags: list[str]                  # e.g. "training_craft_substitution"
```

Surfaced per-cone in the orchestrator's `cone.metadata.layer2a_modality_groups: list[ModalityGroupAllocation]` for audit. NOT surfaced to athletes (internal diagnostic).

---

## 8. Coaching flag rules

New flag types emitted by Layer 2A + Layer 2's substitution path:

| Flag type | Where emitted | When | Severity |
|---|---|---|---|
| `training_craft_substitution` | `resolve_training_substitution` | race tags discipline D-X, athlete owns only D-Y in same group | info |
| `craft_substitution_via_group` | Layer 2C | Layer 2C surfaces an alternate-group-member as substitution candidate | info |
| `athlete_weighting_incomplete` | Layer 2A | athlete weighting covers <80% of a group's pool | warning |
| `modality_group_orphan` | Layer 2A | discipline in `included_discipline_ids` belongs to no group AND is also not the only included member of any singleton's group (i.e. genuinely unparented) | info |
| `modality_group_vocabulary_gap` | Layer 2A | runtime sees a discipline in 2+ groups whose redistribution rules conflict (defensive — should not fire if ETL invariants hold) | warning |

All flags carry the discipline_id(s) involved in the `target_discipline_ids` field of the flag payload.

---

## 9. Caching & determinism

- The group vocabulary is **etl_version-stable** — changes only on ETL re-run. The orchestrator's existing cone hash already includes `etl_version_set`, so a group vocabulary change naturally invalidates cones.
- Per-cone the group lookup is fully deterministic given (included_discipline_ids, race_overrides, athlete_overrides, bridge_data). No LLM in this path. Hash inputs are unchanged from current Layer 2A.
- Layer 2C's modality-group lookup adds a small SQL query (`SELECT discipline_id, group_id FROM layer0.discipline_modality_membership WHERE etl_version = ?`). Cached per-call; ~20-50 rows expected so no caching infrastructure needed.

---

## 10. Edge cases

| Case | Behavior |
|---|---|
| Discipline in 2+ groups, both have included members | Discipline contributes its base_weight share to each group's pool proportionally to group size. (Rare in v1 vocabulary; defensive design.) |
| Race tags 2+ members of the same group with overlapping percentages | Each tagged member gets its tagged %. Pool sum may exceed 100% of the group's bridge share — normalize at the final step handles this. |
| Athlete weighting names a discipline not in `included_discipline_ids` | Silently dropped (consistent with current Layer 2A behavior for the rare race-level exclusion case). |
| All members of a group are excluded by `included_discipline_ids` | Group is inert; no pooling, no flag. |
| Empty `modality_groups` table (pre-ETL state) | Every discipline is its own singleton. Layer 2A behavior identical to pre-v1. Allows phased ETL rollout. |
| Race terrain has 5 rows with discipline_id=D-008, two race-wide rows (no discipline_id) | Race-wide rows are dropped (X3 decision — confirmed by Andy in design discussion). Only tagged rows contribute. |

---

## 11. Performance budget

- One additional SQL query per Layer 2A invocation (the membership lookup). ~20-50 rows. Sub-millisecond.
- Pool computation is O(|disciplines| × |groups|) which is ~10 × ~12 = 120 ops. Negligible.
- No change to Layer 4 synthesis latency (the LLM call itself is unchanged).
- ETL: two new tables, ~20 + ~30 rows respectively. Trivial.

---

## 12. Open items / forward references

1. **The athlete-facing label question.** `craft_substitution` flag text needs to be athlete-readable. Today it's "athlete owns packraft (training surface), race specifies kayak (race surface) — your packraft training contributes to your paddle preparation." Decide whether to surface this on the plan view UI or keep internal.
2. **Stage-race / multi-format athletes.** An athlete training for both XTERRA (off-road tri) and an expedition AR simultaneously hits two framework_sports with overlapping disciplines. v1 picks one framework_sport (primary_sport). v2 may add multi-sport blending — out of scope here.
3. **Group vocabulary evolution.** v1 ships the seed in §3.2. New disciplines added in later ETL versions need group assignments. ETL extractor (`etl/layer0/extractors/modality_groups.py` — new) reads from an Excel sheet (Sports_Framework_v12.xlsx?) for the next iteration.
4. **Layer 2C `also_satisfies` consolidation.** Long-term, `also_satisfies` toggle chains and modality groups overlap conceptually. Not consolidating in v1 (different semantics — toggle-to-toggle vs discipline-to-discipline). Watch for confusion. Revisit if real plan data shows conflicts.
5. **D-010 split (Flat-water vs Whitewater Kayaking).** Today they're both D-010 in the bridge but distinct in spirit. The seed vocabulary puts them in different groups, but if the bridge keeps them as one row, the membership table can't distinguish. May need to fork into D-010a / D-010b before this ships. Cross-reference Layer 0 vocabulary plans.
6. **AR (Sprint) / AR (Expedition) format-split.** Decided this session to use "typical AR" (24-48h expedition) without splitting framework_sports. If the X1a research surfaces large band differences across AR formats, may need to revisit.

---

## 13. Test scenarios

1. **Singleton-only sport** — Marathon (Road), one discipline, no groups. Behavior identical to pre-v1; verify no regressions.
2. **All-members race-tagged** — AR race tagging TR + Trek (foot_trail group both members). Both keep their tagged %. Verify no over-counting in pool.
3. **Partial race tag** — AR race tags only Packraft (D-009) at 20%, athlete owns Kayak only. Race weight redirects to D-010 per §5.3 REDIRECT decision. Coaching flag `training_craft_substitution` emitted with both ids.
4. **Athlete weighting partial coverage** — athlete declares weights for 3 of 5 disciplines in a group. Bridge fills the 2 gaps; `athlete_weighting_incomplete` flag fires if those 2 sum to >20% of group pool.
5. **Cross-group discipline** — hypothetical D-X in both foot_trail and foot_road groups (none in v1 vocab). Verify defensive splitting.
6. **Empty group vocabulary** — pre-ETL state (no rows in `modality_groups`). Layer 2A produces identical output to current behavior; no flag noise.
7. **Layer 2C substitution narrowing** — locale doesn't have kayak, has packraft. Pre-v1: 2C returns "discipline_low_coverage" for D-010. Post-v1: 2C surfaces D-009 as `craft_substitution_via_group` candidate. Verify flag carries both ids.
8. **Bridge change invalidates cones** — change ETL group vocabulary, re-run plan_create. Verify cone cache miss, layer2a re-runs, pool allocation differs.
9. **Worked example fidelity** — implement §5.2 inputs in a unit test, assert outputs match the documented 19.3% / 14.5% / 43.5% / 19.3% / 2.4% / 1.0% distribution.

---

## 14. Gut check

- **Risk: the redirect-vs-split decision (§5.3) may not generalize.** REDIRECT is right for the common "athlete trains the close substitute" case, but a multi-craft athlete (owns kayak AND packraft) gets 100% of weight directed to one member based on athlete signal. The athlete signal becomes load-bearing. Mitigation: the `craft_substitution` flag is loud — coach (or the athlete) can see what got redirected and override via the athlete weighting UI.
- **Risk: changing Layer 2A's load_weight math is a high-blast-radius change.** Validators that read load_weight, the session_grid's shed-lowest-first ordering, and the diag endpoint all see the new values. Mitigation: §5.1 step 4's `_normalize_load_weights` step is unchanged, so the *normalized* output shape is identical — only the value distribution changes. Existing tests on per-discipline weights should still pass for singleton cases; new tests cover group cases.
- **What might be missing: the case where two race-tagged disciplines are in the same group AND the athlete also has weighting for one of them.** The §5.1 rule says race tags win per-member, so the athlete signal is ignored — but the athlete may have signaled "I want more group share than the race tags this member at." Today's design ignores this. v2 may want a "boost above race tag" mechanism. Defer.
- **Best argument against: just keep the LLM-driven craft substitution and skip the deterministic table.** The LLM is currently making reasonable craft picks at synthesis time. Counter: the LLM substitution is at synthesis (per-session), not allocation (per-week). It can pick "use packraft for this session" but it can't make the higher-level decision "the 20% paddle race allocation should map to packraft training time." That's an upstream call that lives in Layer 2A. The deterministic table is required for the allocation step regardless of whether the LLM stays in the synthesis loop.
- **Best argument against: groups are over-engineered for a 1-user product.** Counter: even for 1 user (Andy), the bridge currently doesn't reflect the race spec, which is the symptom. Whether the redistribution happens via groups or via direct discipline-level race overrides, *some* mechanism has to translate "race wants kayak at 20%, athlete trains packraft" into "20% paddle training credit." Groups make this generalizable; per-discipline coupling would not. The cost is two small tables + one query.

---

*End of Modality_Group_Spec_v1.md.*
