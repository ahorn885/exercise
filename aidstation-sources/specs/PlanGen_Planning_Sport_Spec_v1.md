# Plan-Gen — Planning-Sport Resolution & Cross-Training Fold (Spec v1)

**Status:** New spec, 2026-06-21. Closes #447 (part of #201 plan-gen reliability & convergence). Related: #338 (race-share weighting), #339 (synth substitutions), #305 (ParsedIntent re-run cascade).
**Type:** Cross-cutting plan-gen resolution rule. Spans the Layer 4 orchestrator's upstream-cone composition (`_upstream_full_cone`), the Layer 2A input boundary, Layer 3A/3B context, and the Layer 4 per-phase synth. Not a per-node spec — it constrains how an existing input (`framework_sport`) is sourced and adds one new behaviour (the cross-training fold).
**Source:** Andy walkthrough batch 2026-06-06; precedence-order confirmation 2026-06-21 ("race > athlete > standard").

---

## 1. Purpose

Pin down where the **planning sport** comes from, and stop treating the athlete-profile *primary sport* as a planning-sport override.

When an athlete has a target race, the plan is built around **that race's sport**. The athlete-profile primary sport is the athlete's *home discipline*, not the plan's organizing sport — and it serves only two narrower purposes:

1. **Cross-training selection** — when the active race is not the athlete's home discipline (e.g. an ultrarunner doing a one-off adventure race), the profile's primary sport chooses what cross-training to fold in.
2. **No-race organizing sport** — when there is no target race, the profile's primary sport is the plan's organizing sport.

This spec codifies the resolution as a three-tier precedence — **race sport › athlete primary sport › standard** — and specifies the cross-training fold rule. It does **not** implement; the implementation deltas in §8 are the follow-on build (gated on the §6 and §5 decisions below, both of which are Stop-and-ask items).

## 2. The reframe: "override" is the wrong level

Today the resolution is written as a *race-row override of the profile primary sport* (D-73 Phase 5.2 Bucket E.(b)):

> `layer4/orchestrator.py:935-944` — *"race-row override takes precedence over athlete-profile `primary_sport` … Falls back to `primary_sport` when the override is unset OR no target race exists."*

Behaviourally that two-tier fallback already lands on the right sport in the race-present and no-race cases. The defect is **conceptual and structural**, with three consequences worth fixing:

- The profile primary sport is modelled as *the* planning sport that a race happens to override. Andy's framing inverts this: the **race's sport is the planning sport**; the profile sport is the home discipline that only feeds cross-training + the no-race case.
- There is **no third tier**. When neither a race sport nor a profile primary sport exists, the cone raises `framework_sport_missing` (`orchestrator.py:945-949`) — a hard stop where a **standard** plan should be produced.
- There is **no cross-training fold**. The home discipline is dropped entirely once a race of a different sport exists, instead of being folded in as cross-training (issue checklist item 3).

## 3. The three-tier resolution rule

`planning_sport` is resolved by this precedence (highest tier that yields a value wins):

| Tier | Name | Condition | `planning_sport` source |
|---|---|---|---|
| 1 | **Race** | A target race exists **and** `race.framework_sport` is set | `race.framework_sport` |
| 2 | **Athlete** | No target race, **or** a target race with `framework_sport` unset | `profile.primary_sport` |
| 3 | **Standard** | No target race **and** no `profile.primary_sport` | the standard/general fallback (see §6) |

Notes:

- `RaceEventPayload.framework_sport` is `Optional` (`layer4/context.py:1318-1323`). A target race that carries no `framework_sport` therefore falls through to Tier 2 — same as today (`orchestrator.py:940-944` `if not framework_sport: framework_sport = primary_sport`). The reframe keeps this fall-through; it is not a separate error.
- Tier 3 replaces the current `framework_sport_missing` hard stop on the **plan-gen** path. The user-facing "Set your primary sport…" copy (`routes/plan_create.py:411`, `routes/plan_refresh.py:279`, `routes/ad_hoc_workouts.py:224`) stays only for the surfaces where a sport is genuinely required and Tier 3 does not apply (see §6 / §9).
- The resolution is **deterministic** and must be logged with its inputs and chosen tier (Rule #15): log `target_race_present`, `race.framework_sport`, `profile.primary_sport`, and the resolved `(tier, planning_sport)`.

## 4. The profile primary sport's two narrow roles

Outside the no-race Tier-2 case, the profile primary sport is **not** the planning sport. Its two jobs:

### 4.1 Cross-training selection (Tier-1 race, off-discipline)

When a target race exists and `race.framework_sport != profile.primary_sport`, the athlete is training toward a sport that is not their home discipline. The home discipline is folded in as cross-training per §5 — both to preserve the athlete's base fitness in their own sport and to give variety/relief during an off-discipline block.

### 4.2 No-race organizing sport (Tier-2)

When there is no target race, the profile primary sport *is* the planning sport (Tier 2). This is the existing no-race / open-ended plan mode (Layer 3B `non_event_goal_type` ∈ {endurance, general_fitness, strength, mixed}; `plan_duration_weeks_no_event`). No fold applies — the home discipline already *is* the plan's sport.

## 5. The cross-training fold rule

**Rule:** when a target race exists and `race.framework_sport != profile.primary_sport`, fold `profile.primary_sport` into the plan's cross-training pool.

### 5.1 What the "cross-training pool" is today

The only cross-training mechanism in the synth is the **variety carveout** (`layer4/per_phase.py:273` `VARIETY_CARVEOUT_PROMPT_SECTION`): on *easy*-typed cardio sessions only, render the content as a training-equivalent discipline **within the same locomotion mode** (foot↔foot, wheel↔wheel), and only if `Coaching memory` expresses a variety/cross-training preference. Counts, long sessions, and every quality session stay on the race-specific discipline. There is no concept today of pulling the athlete's *home discipline* into the plan when it differs from the race sport.

The fold rule is **narrower in trigger** (it fires on the structural `race.sport != primary_sport` condition, not on a coaching-memory preference) and **potentially broader in mode** (the home discipline may be a different locomotion mode than the race sport — an ultrarunner's run vs. an AR's paddle/bike/nav mix).

### 5.2 Open placement decision (Stop-and-ask: prompt design #1 + cross-layer #3)

Two viable placements; this needs Andy's call before implementation:

- **(a) Synth/prompt level (Layer 4 per-phase).** Extend the variety-carveout section so that, when the cone passes a non-empty `cross_training_sport` (= `profile.primary_sport`, set only when it differs from the planning sport), the synthesizer may render a *minority* of easy/aerobic-maintenance volume as the home discipline. Cheapest; keeps race specificity intact (counts/long/quality stay on race disciplines); no Layer 2A churn. Risk: it is an LLM-discretion rule, so dosage is soft.
- **(b) Discipline-set level (Layer 2A).** Inject the home discipline's disciplines into the classifier's set as a low-weight cross-training role, so the whole downstream cone (2B/2C/2D/3A/3B/4) sees them as first-class minor disciplines. More faithful to "fold into the pool," but it perturbs race-specific weighting (the #338 race-share work) and the included-discipline cone, and risks diluting race specificity.

**Recommendation:** start with **(a)** — it satisfies the rule (home discipline appears as cross-training) at minimum blast radius and keeps race specificity non-negotiable, matching the existing carveout's hard rules. Promote to (b) only if dogfooding shows the synth under-uses the folded sport. Either way the fold is **easy-volume only, a minority of weekly volume, race specificity preserved** — the carveout's existing guardrails (`per_phase.py:277-280`) carry over.

### 5.3 Inert cases

The fold produces nothing (no `cross_training_sport` passed) when: `race.framework_sport == profile.primary_sport`; no profile primary sport is set (Tier-1 race with an unset home discipline); or there is no target race (Tier-2/3 — the home discipline already is the planning sport, or there is none).

## 6. The "standard" tier (open architectural decision)

Tier 3 fires when there is no target race and no profile primary sport. Layer 2A *requires* a `framework_sport` to classify disciplines (`Layer2A_Spec.md` §4.1), so "standard" needs a defined behaviour. Two options (Stop-and-ask: cross-layer surface #3):

- **(a) Designate a default `framework_sport`.** Feed Layer 2A a general endurance/conditioning template sport. Requires a curated `framework_sport` row (Layer0_ETL_Spec mentions a "General Conditioning" grouping, line 1013, but there is no general *framework sport* in `sport_discipline_bridge` today) — i.e. new Layer-0 data + the no-padding gate.
- **(b) Route the standard tier through the existing no-race general-fitness path.** Tier 3 = a no-race plan with `non_event_goal_type = 'general_fitness'` (Layer 3B already supports this, `layer3b/builder.py:107`), discipline-agnostic, without a race-specific discipline cone. No new Layer-0 data.

**Recommendation:** **(b)**. It reuses the shipped no-race general-fitness machinery, needs no new vocabulary, and matches what "standard plan" means — a sensible general-fitness block when the athlete has told us neither a race nor a home discipline. (a) is heavier and drags in the padding-refusal trigger. **Andy decides** — this is the one genuinely new architectural surface in the issue.

## 7. Audit — every plan-gen read of `primary_sport`

Checklist item 1. Classification: **PLANNING** = used as the planning sport (must come from the race when one exists); **HOME** = used as the athlete's home discipline (correctly from profile).

| Location | Current use | Class | Action |
|---|---|---|---|
| `layer4/orchestrator.py:940-949` (`_upstream_full_cone`) | `framework_sport = race.framework_sport ?? primary_sport`; else raise `framework_sport_missing` | **PLANNING** | Reframe as `_resolve_planning_sport` (§3); add Tier-3 standard (§6); remove "override" framing |
| `layer1/builder.py:191,269` | Reads `primary_sport` from the DB row into `Layer1Identity.primary_sport` | HOME (source) | No change — this is the profile field's origin |
| `layer3a/builder.py:390-393` | Raises `incomplete_onboarding` when `identity.primary_sport is None` | **PLANNING (bug)** | **Loosen** — a Tier-1 race plan must generate even with no profile primary sport; gate on the resolved `planning_sport`/2A disciplines, not `primary_sport` |
| `layer3a/builder.py:453-454` | Renders `- primary_sport: {primary}` into the athlete-state prompt | HOME | No change (home-discipline context); already falls back to `"unspecified"` |
| `layer3a/builder.py:772` | Telemetry `section_a.primary_sport` | HOME | No change |
| `layer3b/builder.py:605,613` | Renders `- primary_sport: {primary}` into the viability prompt (`"unspecified"` fallback) | HOME | No change |
| `layer3b/builder.py:701` | Telemetry `c.primary_sport` | HOME | No change |
| `layer3b/builder.py:852-866` | No-event goal-type vs `primary_sport` mismatch → `goal_type_primary_sport_mismatch` observation | HOME (no-race) | No change — this is a Tier-2 home-discipline cross-check |
| `layer4/context.py:1491` | `Layer1Identity.primary_sport` field definition | HOME (schema) | No change |
| `routes/race_events.py:276-289` (`_resolve_effective_framework_sport`) | UI mirror of `race.framework_sport ?? primary_sport` for the discipline-grid render | **PLANNING** | Re-comment to "planning sport" framing; behaviour unchanged (UI render only) |
| `routes/onboarding.py:988-998` | Calls `_resolve_effective_framework_sport` for the onboarding discipline grid | **PLANNING** | Re-comment; behaviour unchanged |
| `layer4/orchestrator.py:1342-1348` (single-session) | Calls Layer 2A with `request.sport` (per-request pick), explicitly **not** `primary_sport` | n/a | **Already aligned** — athlete-overriding single-session is correct; no change |

Single source of truth: §3's resolution should live in **one** helper (`_resolve_planning_sport`) in the orchestrator; `routes/race_events.py`'s UI mirror documents that it intentionally re-implements the same order for page-load render (it cannot import the cone) and must be kept in lockstep.

## 8. Implementation delta (for the follow-on build)

Not done in this spec. When built:

1. **`layer4/orchestrator.py:935-949`** — replace the "override" comment + inline resolution with a `_resolve_planning_sport(target_race_event, layer1_payload)` helper implementing §3 (Tiers 1-3) and Rule-#15 logging. Tier 3 dispatches per the §6 decision instead of raising `framework_sport_missing`.
2. **`layer3a/builder.py:390-393`** — stop hard-requiring `primary_sport`; a race-tier plan must build without a profile primary sport. Gate on the resolved planning sport / non-empty 2A disciplines.
3. **Cross-training fold (§5)** — thread `cross_training_sport` (= `profile.primary_sport` when it differs from `planning_sport`, else `None`) through the cone to the chosen placement (recommended: Layer 4 per-phase carveout). Prompt-body change ⇒ Stop-and-ask trigger #1.
4. **Remove the "override" framing** in the comments at `routes/race_events.py:280`, `routes/onboarding.py:988`, and `orchestrator.py:935-944`. Behaviour at the UI mirrors is unchanged.
5. **No change** to the single-session path (`orchestrator.py:1342`) — already athlete-overriding by design.

## 9. Edge cases

| Case | Resolution |
|---|---|
| Target race with `framework_sport` set | Tier 1 — plan around `race.framework_sport` |
| Target race, `framework_sport` unset, profile primary set | Tier 2 — plan around `primary_sport` (existing fall-through) |
| Target race (sport set), **no** profile primary sport | Tier 1 — plan around race; fold inert (no home discipline); Layer 3A must **not** block (§8.2) |
| Target race sport **==** profile primary sport | Tier 1 — plan around race; **no fold** (race specificity already covers the home discipline) |
| No target race, profile primary set | Tier 2 — plan around `primary_sport`; no fold |
| No target race, **no** profile primary sport | Tier 3 — standard plan (§6) |
| Off-discipline race (sport ≠ home), both set | Tier 1 — plan around race; **fold** `primary_sport` as cross-training (§5) |

## 10. Test scenarios

1. Race sport set, primary sport different → plan organizes on race sport; home discipline appears as cross-training (easy volume only); counts/long/quality stay on race disciplines.
2. Race sport set, no primary sport → plan generates end-to-end (no `incomplete_onboarding`); no fold.
3. Race sport set == primary sport → plan organizes on the sport; no fold injected.
4. No race, primary sport set → Tier-2 no-race plan on primary sport; `goal_type_primary_sport_mismatch` cross-check still fires.
5. No race, no primary sport → Tier-3 standard plan produced (no `framework_sport_missing` on the plan-gen path).
6. Race with `framework_sport` unset, primary set → Tier-2 fall-through to primary sport.
7. Resolution logging: each plan-gen run logs inputs + `(tier, planning_sport, cross_training_sport)`.

## 11. Open items

- **§6 standard-tier mechanism** — default `framework_sport` (a) vs. no-race general-fitness route (b). Recommend (b). **Andy decision** (cross-layer surface, padding-refusal if (a)).
- **§5 fold placement + dosage** — synth/prompt (a) vs. Layer 2A discipline-set (b). Recommend (a). **Andy decision** (prompt-design trigger).
- **`routes/race_events.py` mirror** — keep the UI-side resolution in lockstep with `_resolve_planning_sport`; consider a shared constant/order or a comment-anchored contract test so they cannot drift.
- **Tier-3 user surfaces** — confirm which surfaces (plan_create / plan_refresh / ad_hoc) adopt the standard fallback vs. keep the "set your primary sport" gate. Single-session/ad-hoc is athlete-driven and out of scope for Tier 3.

## 12. Gut check

- **Risk — the behaviour barely moves, the framing moves a lot.** Tiers 1-2 are already what the code does; the load-bearing *new* behaviour is Tier 3 (standard) and the §5 fold. If those two are deferred, this PR is a rename + comment cleanup. That is fine for a `type:spec` issue, but don't oversell the delta.
- **Best argument against the fold (§5):** for a one-off off-discipline race, an athlete arguably wants *maximum* race specificity, not their home sport diluting the block. The mitigation is the carveout guardrails — easy volume only, minority share, race specificity untouched — but the dosage is LLM-discretion under option (a), so it could under- or over-fire. Watch this in dogfooding before trusting it.
- **What might be missing:** "standard" is under-defined until §6 is decided — Layer 2A genuinely needs *a* sport, so Tier 3 is not free. And `layer3a/builder.py:390` is a latent blocker even for the *race-present* case today (a race plan fails if the athlete left primary sport blank); §8.2 is arguably the highest-value concrete fix in here and could ship ahead of the rest.
- **Scope honesty:** #338 (race-share weighting) and #339 (synth substitutions) overlap the §5 fold's blast radius. Sequence the fold *after* those land, or coordinate, so the cross-training weighting doesn't fight race-share weighting.
