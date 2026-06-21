# Plan-Gen — Planning-Sport Resolution & Cross-Training Fold (Spec v1)

**Status:** New spec, 2026-06-21. Closes #447 (part of #201 plan-gen reliability & convergence). Related: #338 (race-share weighting), #339 (synth substitutions), #305 (ParsedIntent re-run cascade).
**Type:** Cross-cutting plan-gen resolution rule. Spans the Layer 4 orchestrator's upstream-cone composition (`_upstream_full_cone`), the Layer 2A input boundary, and Layer 3A context. Not a per-node spec — it constrains how an existing input (`framework_sport`) is sourced and adds one new behaviour (the cross-training fold).
**Decisions baked in (Andy, 2026-06-21):** standard tier resolves to the athlete's primary sport (§6); cross-training fold is implemented at the Layer 2A discipline-set level (§5).
**Source:** Andy walkthrough batch 2026-06-06; precedence-order + decisions 2026-06-21 ("race > athlete > standard").

---

## 1. Purpose

Pin down where the **planning sport** comes from, and stop treating the athlete-profile *primary sport* as a planning-sport override.

When an athlete has a target race, the plan is built around **that race's sport**. The athlete-profile primary sport is the athlete's *home discipline*, not the plan's organizing sport — and it serves only two narrower purposes:

1. **Cross-training selection** — when the active race is not the athlete's home discipline (e.g. an ultrarunner doing a one-off adventure race), the profile's primary sport chooses what cross-training to fold in.
2. **No-race organizing sport** — when there is no target race, the profile's primary sport is the plan's organizing sport, and the plan is a *standard* (non-race-specific) one.

This spec codifies the resolution as the precedence **race sport › athlete primary sport › standard**, and specifies the cross-training fold rule. It does **not** implement; the implementation deltas in §8 are the follow-on build.

## 2. The reframe: "override" is the wrong level

Today the resolution is written as a *race-row override of the profile primary sport* (D-73 Phase 5.2 Bucket E.(b)):

> `layer4/orchestrator.py:935-944` — *"race-row override takes precedence over athlete-profile `primary_sport` … Falls back to `primary_sport` when the override is unset OR no target race exists."*

Behaviourally that fallback already lands on the right sport in the race-present and no-race cases. The defect is **conceptual and structural**, with two consequences worth fixing:

- The profile primary sport is modelled as *the* planning sport that a race happens to override. Andy's framing inverts this: the **race's sport is the planning sport**; the profile sport is the home discipline that only feeds cross-training + the no-race ("standard") case.
- There is **no cross-training fold**. The home discipline is dropped entirely once a race of a different sport exists, instead of being folded in as cross-training (issue checklist item 3).

(There is no third *sport source* to add: the no-race "standard" plan is organized around the athlete's primary sport — §6 — so the bottom of the cascade is the existing "set your primary sport" gate, not a new generic-plan mechanism.)

## 3. The resolution rule: race › athlete › standard

`planning_sport` and plan mode resolve by this precedence (highest tier that yields a value wins):

| Tier | Andy's label | Sport source | Plan mode | Condition |
|---|---|---|---|---|
| 1 | **Race** | `race.framework_sport` | race-specific | A target race exists **and** `race.framework_sport` is set |
| 2 | **Athlete → Standard** | `profile.primary_sport` | **standard** (non-race-specific) | No target race (or a target race with `framework_sport` unset) **and** `primary_sport` is set |
| 3 | *(gate)* | — | — (no plan generated) | No target race **and** no `primary_sport` → keep today's "Set your primary sport" gate |

Reading of Andy's "race > athlete > standard": tier 1 is the **race** sport; absent a race, the planning sport is the **athlete**'s primary sport and the plan is a **standard** (non-race-specific) one; below that there is no sport to plan around, so the existing gate stands. "Athlete" and "standard" are not two different sports — "standard" is the *plan style* you get when the sport source is the athlete's primary sport.

Notes:

- `RaceEventPayload.framework_sport` is `Optional` (`layer4/context.py:1318-1323`). A target race that carries no `framework_sport` falls through to Tier 2 — same as today (`orchestrator.py:940-944`). The reframe keeps this fall-through; it is not a separate error.
- **Tier 3 keeps the existing `framework_sport_missing` gate** (`orchestrator.py:945-949`; user copy at `routes/plan_create.py:411`, `routes/plan_refresh.py:279`, `routes/ad_hoc_workouts.py:224`). No generic/sportless plan is invented. We do **not** build a plan with no sport.
- The resolution is **deterministic** and must be logged with its inputs and chosen tier (Rule #15): log `target_race_present`, `race.framework_sport`, `profile.primary_sport`, and the resolved `(tier, planning_sport, cross_training_sport)`.

## 4. The profile primary sport's two narrow roles

Outside the no-race Tier-2 case, the profile primary sport is **not** the planning sport. Its two jobs:

### 4.1 Cross-training selection (Tier-1 race, off-discipline)

When a target race exists and `race.framework_sport != profile.primary_sport`, the athlete is training toward a sport that is not their home discipline. The home discipline is folded in as cross-training per §5 — to preserve the athlete's base fitness in their own sport and give variety during an off-discipline block.

### 4.2 No-race organizing sport (Tier-2, "standard")

When there is no target race, the profile primary sport *is* the planning sport (Tier 2), and the plan is a standard non-race-specific block (the existing no-race / open-ended mode: Layer 3B `non_event_goal_type` ∈ {endurance, general_fitness, strength, mixed}; `plan_duration_weeks_no_event`). No fold applies — the home discipline already *is* the plan's sport.

## 5. The cross-training fold rule

**Rule:** when a target race exists and `race.framework_sport != profile.primary_sport`, fold `profile.primary_sport` into the plan's cross-training pool.

**Decision (Andy, 2026-06-21): implement at the Layer 2A discipline-set level (option B).**

### 5.1 Mechanism

The orchestrator computes `cross_training_sport = profile.primary_sport` when it differs from the resolved `planning_sport`, else `None`. When set, its disciplines (resolved from `sport_discipline_bridge` for `cross_training_sport`) are injected into Layer 2A's classified discipline set with a **distinct cross-training role at low weight**, so the entire downstream cone (2B terrain, 2C equipment/modality, 2D injury filter, 3A/3B, 4 synth) sees them as first-class **minor** disciplines rather than relying on the synthesizer to improvise them.

Guardrails (carry over the spirit of the existing variety carveout, `layer4/per_phase.py:273-284`):

- **Low weight, minority share.** The race-specific disciplines must continue to dominate weekly volume in their mode. The fold adds maintenance/cross-training volume; it does not trade away race specificity — counts, long sessions, and quality sessions stay on the race disciplines.
- **Single source.** The fold sport and the injection happen once, in the cone (`_upstream_full_cone`), keyed off the §3 resolution — not re-derived per layer.

### 5.2 Why Layer 2A and not the synth prompt

Option A (extend the per-phase variety-carveout prompt) was considered and **not** chosen: it would keep the fold as soft LLM discretion on easy days only. Andy chose the discipline-set injection so the folded sport is a real, weighted member of the plan's discipline mix and flows through the whole cone deterministically.

**Cost / coordination (the load-bearing risk):** this touches Layer 2A's classifier output and weighting, which is exactly the surface #338 (race-share weighting) rebalances via `_apply_modality_group_pooling` (precedence: race terrain mix › athlete split › bridge midpoints). The cross-training weight must slot **below** the race-share signal so it cannot dilute race specificity. Sequence this fold **after** #338 lands, or co-design the weighting precedence so the two do not fight. This is a Layer 2A payload/algorithm change → a `Layer2A_Spec` amendment is owed in the build, and it is a cross-layer surface change (Stop-and-ask trigger #3).

### 5.3 Inert cases

The fold produces nothing (no `cross_training_sport`) when: `race.framework_sport == profile.primary_sport`; no profile primary sport is set (Tier-1 race with an unset home discipline); or there is no target race (Tier-2/3 — the home discipline already is the planning sport, or there is none).

## 6. The "standard" tier resolves to the athlete's primary sport

**Decision (Andy, 2026-06-21):** the standard (no-race) plan is organized around `profile.primary_sport`. There is **no** invented "General Fitness" framework sport and **no** sportless plan. This is the existing no-race / open-ended general plan mode, which already reads `primary_sport` as its sport via the `_upstream_full_cone` fallback.

When there is no race **and** no primary sport, the existing `framework_sport_missing` gate stands (§3 Tier 3) — Layer 2A genuinely needs a sport to classify disciplines, and we do not generate a plan from nothing. This keeps the shipped "Set your primary sport in your profile before creating a plan" copy meaningful.

## 7. Audit — every plan-gen read of `primary_sport`

Checklist item 1. Classification: **PLANNING** = used as the planning sport (must come from the race when one exists); **HOME** = used as the athlete's home discipline (correctly from profile).

| Location | Current use | Class | Action |
|---|---|---|---|
| `layer4/orchestrator.py:940-949` (`_upstream_full_cone`) | `framework_sport = race.framework_sport ?? primary_sport`; else raise `framework_sport_missing` | **PLANNING** | Reframe as `_resolve_planning_sport` (§3); behaviour kept (race ?? primary, else gate); remove "override" framing; compute `cross_training_sport` (§5) |
| `layer1/builder.py:191,269` | Reads `primary_sport` from the DB row into `Layer1Identity.primary_sport` | HOME (source) | No change — this is the profile field's origin |
| `layer3a/builder.py:390-393` | Raises `incomplete_onboarding` when `identity.primary_sport is None` | **PLANNING (bug)** | **Loosen** — a Tier-1 race plan must generate even with no profile primary sport; gate on the resolved `planning_sport` / 2A disciplines, not `primary_sport` |
| `layer3a/builder.py:453-454` | Renders `- primary_sport: {primary}` into the athlete-state prompt | HOME | No change (home-discipline context); already falls back to `"unspecified"` |
| `layer3a/builder.py:772` | Telemetry `section_a.primary_sport` | HOME | No change |
| `layer3b/builder.py:605,613` | Renders `- primary_sport: {primary}` into the viability prompt (`"unspecified"` fallback) | HOME | No change |
| `layer3b/builder.py:701` | Telemetry `c.primary_sport` | HOME | No change |
| `layer3b/builder.py:852-866` | No-event goal-type vs `primary_sport` mismatch → `goal_type_primary_sport_mismatch` observation | HOME (no-race) | No change — Tier-2 home-discipline cross-check |
| `layer4/context.py:1491` | `Layer1Identity.primary_sport` field definition | HOME (schema) | No change |
| `routes/race_events.py:276-289` (`_resolve_effective_framework_sport`) | UI mirror of `race.framework_sport ?? primary_sport` for the discipline-grid render | **PLANNING** | Re-comment to "planning sport" framing; behaviour unchanged (UI render only) |
| `routes/onboarding.py:988-998` | Calls `_resolve_effective_framework_sport` for the onboarding discipline grid | **PLANNING** | Re-comment; behaviour unchanged |
| `layer4/orchestrator.py:1342-1348` (single-session) | Calls Layer 2A with `request.sport` (per-request pick), explicitly **not** `primary_sport` | n/a | **Already aligned** — athlete-overriding single-session is correct; no change |

Single source of truth: §3's resolution should live in **one** helper (`_resolve_planning_sport`) in the orchestrator; `routes/race_events.py`'s UI mirror documents that it intentionally re-implements the same order for page-load render (it cannot import the cone) and must be kept in lockstep.

## 8. Implementation delta

**Status (2026-06-21):** items 1, 2, 4, 5 **shipped**; item 3 (the Layer 2A fold) **deferred** — it is the cross-layer weighting change entangled with #338 (§5.2) and needs a weighting-precedence decision + a `Layer2A_Spec` amendment first.

1. ✅ **`layer4/orchestrator.py`** — `_resolve_planning_sport(target_race_event, layer1_payload, user_id)` helper implements §3 (race ?? primary; Tier-3 gate unchanged) with Rule-#15 logging; `_upstream_full_cone` calls it. (`cross_training_sport` not yet computed — gated on item 3.)
2. ✅ **`layer3a/builder.py`** — dropped the hard `primary_sport is None` requirement; a race-tier plan now builds without a profile primary sport. The non-empty 2A discipline set is the real gate.
3. ⏳ **Cross-training fold (§5)** — *deferred.* Inject `cross_training_sport`'s disciplines into Layer 2A at a low cross-training weight, below the #338 race-share signal. New Layer 2A input + `Layer2A_Spec` amendment; cross-layer surface (trigger #3); sequence after / coordinate with #338.
4. ✅ **Removed the "override" framing** in `routes/race_events.py` (`_resolve_effective_framework_sport` docstring) and `orchestrator.py`. Behaviour at the UI mirror is unchanged.
5. ✅ **No change** to the single-session path — already athlete-overriding by design.
5. **No change** to the single-session path (`orchestrator.py:1342`) — already athlete-overriding by design.

## 9. Edge cases

| Case | Resolution |
|---|---|
| Target race with `framework_sport` set | Tier 1 — plan around `race.framework_sport` |
| Target race, `framework_sport` unset, primary set | Tier 2 — standard plan around `primary_sport` (existing fall-through) |
| Target race (sport set), **no** profile primary sport | Tier 1 — plan around race; fold inert (no home discipline); Layer 3A must **not** block (§8.2) |
| Target race sport **==** profile primary sport | Tier 1 — plan around race; **no fold** (race specificity already covers the home discipline) |
| No target race, profile primary set | Tier 2 — standard plan on `primary_sport`; no fold |
| No target race, **no** profile primary sport | Tier 3 — existing "set your primary sport" gate; no plan generated |
| Off-discipline race (sport ≠ home), both set | Tier 1 — plan around race; **fold** `primary_sport` into the 2A discipline set as low-weight cross-training (§5) |

## 10. Test scenarios

1. Race sport set, primary sport different → plan organizes on race sport; home discipline appears in the 2A discipline set as a low-weight cross-training role; counts/long/quality stay race-specific.
2. Race sport set, no primary sport → plan generates end-to-end (no `incomplete_onboarding`); no fold.
3. Race sport set == primary sport → plan organizes on the sport; no fold injected.
4. No race, primary sport set → Tier-2 standard plan on primary sport; `goal_type_primary_sport_mismatch` cross-check still fires.
5. No race, no primary sport → Tier-3 gate (`framework_sport_missing`); no plan.
6. Race with `framework_sport` unset, primary set → Tier-2 fall-through to primary sport.
7. Fold weight vs #338: with a race-discipline terrain mix present, the race-share signal still dominates the cross-training weight (race specificity preserved).
8. Resolution logging: each plan-gen run logs inputs + `(tier, planning_sport, cross_training_sport)`.

## 11. Open items

- **§5 fold weight + #338 interaction** — fix the exact precedence so the cross-training weight slots below the race-share signal in `_apply_modality_group_pooling`. Decide sequencing (after #338, or co-designed). Owes a `Layer2A_Spec` amendment in the build.
- **`routes/race_events.py` mirror** — keep the UI-side resolution in lockstep with `_resolve_planning_sport`; consider a shared order constant or a comment-anchored contract test so they cannot drift.
- **`layer3a/builder.py:390` fix** — confirm the loosened gate condition (resolved planning sport / non-empty 2A disciplines) and that it does not mask a genuinely empty cone.

## 12. Gut check

- **Risk — the framing moves more than the behaviour.** Tiers 1-2 are already what the code does, and Tier 3 stays a gate. The load-bearing *new* behaviour is the §5 fold and the §8.2 Layer-3A loosening. Don't oversell the delta: minus the fold, this is a rename + comment cleanup + one real bug fix.
- **The fold (§5, option B) is the genuinely risky piece.** Injecting the home discipline into the 2A set perturbs the same weighting surface #338 rebalances. If the cross-training weight isn't strictly below the race-share signal, an off-discipline plan could lose race specificity — the exact opposite of what an athlete training for a one-off race wants. This is why §5.2/§11 insist on sequencing after #338 and a contract test on the weighting precedence.
- **Highest-value shippable slice:** the `layer3a/builder.py:390` loosening (§8.2). Today a race plan fails outright when the athlete left primary sport blank — a clear bug under the new model, fixable independent of the fold or the reframe.
- **What might be missing:** "off-discipline" is treated as a clean `race.sport != primary_sport` boolean. Real multisport overlaps (an AR athlete whose primary sport is Trail Running, and AR *includes* trail running) mean the "home discipline" may already be in the race's discipline set — the fold should no-op or de-dupe against the existing 2A set rather than double-count. Worth an explicit rule in the build.
