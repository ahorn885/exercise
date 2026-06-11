# Best-Fit Modality Resolver — Spec v1

**Status:** First draft, 2026-05-24. Spec-only — implementation deferred to a follow-on slice.
**Type:** Pure-Python deterministic resolver. No LLM involvement. Runs after Layer 1 + Layer 2B + Layer 2C are built; consumed by Layer 4 plan generator.
**Predecessor decisions:**
- BucketC_g_TerrainEquipmentMerge (2026-05-24) — pinned the architectural principle that **terrain rows describe SURFACE only; modality (foot / bike / paddle) is captured discipline-side + equipment-side**. This spec materialises that principle.
- BucketC_l_SkillCapabilityToggles (2026-05-24) — added `Layer1Lifestyle.skill_toggle_states`, the fourth input to the resolver.
- SkillCaptureSurface (2026-05-24) — shipped the athlete-side capture surface for `skill_toggle_states`. With this slice landed, the planner now has the full input set `{locale_terrain_ids + cluster_equipment + included_disciplines + skill_toggle_states}` end-to-end.
- Trigger #5 plan-mode gate (this session) — Andy picked **A2 = algorithmic Python resolver** over A1 static mapping table / A3 LLM prompt-side reasoning / A4 hybrid. Slice shape **S1 = spec-only** picked over S2 stub / S3 full implementation.

---

## 1. Purpose

Given the inputs available to plan generation —

- `locale_terrain_ids` per locale (TRN-001..TRN-020; what surface types are accessible from each locale)
- `cluster_equipment` per locale (`Layer2CPayload.effective_pool`; equipment categories the athlete has access to)
- `included_discipline_ids` (D-001..D-028; disciplines the athlete is training)
- `skill_toggle_states` (`Layer1Lifestyle.skill_toggle_states`; capability gates the athlete has opted into)

— produce, per `(discipline_id, locale_id)` pair, a **menu of viable modalities** ranked by preference, with a **top-pick** and a short **rationale-hint** Layer 4 can surface in coach-voice copy.

Modality means "the concrete way an athlete trains a given discipline at a given locale this session." Examples: for D-006 Outdoor Road Cycling, modalities are `{outdoor_road_ride, outdoor_gravel_ride, indoor_trainer}`; for D-010 Outdoor Rock Climbing, modalities are `{outdoor_lead_climb, outdoor_top_rope, outdoor_boulder, gym_lead_climb, gym_top_rope, gym_boulder, gym_hangboard}`. The resolver doesn't decide which one to prescribe for any given session — that's Layer 4's job with phase + race + history context. The resolver narrows the option space; doesn't decide.

**Why a separate module instead of folding into 2C:** the resolver consumes outputs of Layer 1 (skill toggles), Layer 2B (locale terrain — `locale_terrain_ids` is already on Layer 2B input but the resolver also reads it directly), and Layer 2C (effective_pool). A 2C-internal placement would force the call to wait for 2C completion and would also have to re-read terrain. A separate module after 2C is cleaner: it's a downstream join, not a 2C extension.

## 2. What the resolver does NOT do

Clarifying boundaries to prevent scope creep:

- **Does not pick the per-session modality.** It returns a menu + top-pick + rationale-hint. Layer 4 picks per session with full phase / race / history / weather context.
- **Does not weight by phase.** Phase awareness (Base/Build/Peak/Taper biases) lives in Layer 4. The resolver's `preference_score` is a static base preference (outdoor > indoor; specific > generic; available-skill > requires-coached-introduction), not a phase-aware ranking.
- **Does not look up exercise prescriptions.** That's Layer 2C × Layer 4. The resolver answers "what kind of session is even possible here," not "what exercises fill the session."
- **Does not handle multi-cluster plans.** Cluster selection is Layer 4. The resolver runs per `(discipline, locale)` and Layer 4 chooses which locale's recommendation applies per session.
- **Does not consume race_terrain.** Race terrain is consumed by Layer 2B for gap analysis. The resolver only looks at `locale_terrain_ids` (what's accessible from the athlete's locale, not what the race demands).
- **Does not emit a "schedule" or "session count."** Layer 4 owns scheduling.
- **Does not handle injury accommodations.** That's Layer 2D × Layer 4. A locked-out modality (e.g. wrist injury contraindicates climbing pull-on) is filtered downstream, not at the resolver.
- **Does not write to the database.** Pure read.

## 3. Function signature

```python
def resolve_best_fit_modality(
    db,
    *,
    cluster_locale_inputs: list[ClusterLocaleInput],
    included_discipline_ids: list[str],
    skill_toggle_states: dict[str, bool] | None = None,
    etl_version_set: dict[str, str],
) -> Layer2ModalityPayload:
    ...
```

### Parameters

| Param | Type | Source | Notes |
|---|---|---|---|
| `db` | DB connection | caller (Layer 4 orchestrator) | Read-only; resolver does its own SELECTs against `layer0.disciplines` for the canonical name lookup. |
| `cluster_locale_inputs` | `list[ClusterLocaleInput]` | Layer 1 + Layer 2C | One entry per locale in the cluster. Each carries the locale id, locale name, `locale_terrain_ids`, and the `effective_pool` from that locale's Layer 2C output. |
| `included_discipline_ids` | `list[str]` | Layer 1 / Layer 2A | Disciplines being trained. Non-empty. |
| `skill_toggle_states` | `dict[str, bool] \| None` | Layer 1 (`Layer1Lifestyle.skill_toggle_states`) | Capability gating. `None` → treated as `{}` (default-OFF semantics for all toggles, mirroring the gear-toggle precedent). |
| `etl_version_set` | `dict[str, str]` | Plan-gen pin | Per Layer 2C spec §3 Decision 2. Locks Layer 0 version for the plan. Contains keys for `0A`, `0B`, `0C`. |

### Input dataclasses

```python
@dataclass(frozen=True)
class ClusterLocaleInput:
    locale_id: str
    locale_name: str | None
    locale_terrain_ids: list[str]      # TRN-001..TRN-020 accessible from this locale
    effective_pool: list[str]          # From Layer2CPayload.effective_pool for this locale
```

The caller (Layer 4 `_upstream_full_cone`) builds this list by zipping locale rows from Layer 1 with the per-locale `Layer2CPayload` outputs already on the cone.

### Return type

See §7 below (`Layer2ModalityPayload`).

## 4. Input validation (preconditions)

Fail-loud rather than fail-silent. Validation runs before any DB query.

1. `cluster_locale_inputs` non-empty.
2. Every `ClusterLocaleInput.locale_id` is a non-empty string; ids are unique across the list.
3. Every `ClusterLocaleInput.locale_terrain_ids` is a list of strings (may be empty — extreme case is valid; see §10).
4. Every `ClusterLocaleInput.effective_pool` is a list of strings (may be empty).
5. `included_discipline_ids` non-empty; every entry is a string matching the `^D-\d{3}[a-z]?$` shape (e.g. `D-001`, `D-008b`).
6. `skill_toggle_states` (if not None) keys are strings, values are bools. (Toggle-name vocab validation is upstream — `parse_skill_form` already does it.)
7. `etl_version_set` contains keys for `0A`, `0B`, `0C` at minimum.

Validation failure → raise `Layer2ModalityInputError`. The orchestrator catches and surfaces a user-facing error. This is NOT a HITL gate — HITL is for ambiguous content, not malformed inputs.

## 5. Algorithm

### 5.1 Module-level vocab

The resolver carries one module-level dict pinning, for each discipline that has a meaningful modality split, the list of `ModalityOptionDef` entries that are candidates for that discipline. Module-level (not DB-stored) per the A2 architectural pick — mirrors the gear-toggle / skill-toggle Python-rule precedent.

```python
@dataclass(frozen=True)
class ModalityOptionDef:
    modality_id: str                    # snake_case identifier; e.g. 'outdoor_gravel_ride'
    modality_name: str                  # human-readable; e.g. 'Outdoor gravel ride'
    requires_terrain_any_of: list[str]  # TRN-xxx ids; satisfied if ANY appears in locale_terrain_ids
    requires_equipment_all_of: list[str]  # equipment canonical names; satisfied if ALL appear in effective_pool
    requires_skill_toggle: str | None   # skill toggle name; satisfied if states.get(name) is True (default-OFF fires not-satisfied)
    is_outdoor: bool                    # True for outdoor venues; False for indoor / gym
    is_specific: bool                   # True when the option is sport-specific (e.g. gravel_ride for D-006 on TRN-020); False for generic substitutes (e.g. indoor_trainer)
    base_preference_score: int          # 0-100; higher wins. See §5.3.
    rationale_template: str             # Short coach-voice phrase; e.g. "gravel terrain accessible from {locale_name}, gravel bike on hand"
```

Module-level dict (representative AR subset; full population is the load-bearing artifact of the implementation slice that follows this spec):

```python
_MODALITY_OPTIONS_PER_DISCIPLINE: dict[str, list[ModalityOptionDef]] = {
    # D-001 Trail Running
    'D-001': [
        ModalityOptionDef('outdoor_trail_run', 'Outdoor trail run',
            requires_terrain_any_of=['TRN-002','TRN-003','TRN-004','TRN-005','TRN-006'],
            requires_equipment_all_of=[],
            requires_skill_toggle=None,
            is_outdoor=True, is_specific=True, base_preference_score=90,
            rationale_template='trail terrain accessible from {locale_name}'),
        ModalityOptionDef('outdoor_road_run', 'Outdoor road run',
            requires_terrain_any_of=['TRN-001'],
            requires_equipment_all_of=[],
            requires_skill_toggle=None,
            is_outdoor=True, is_specific=False, base_preference_score=60,
            rationale_template='paved surface accessible; trail unavailable at {locale_name}'),
        ModalityOptionDef('treadmill_run', 'Treadmill run (indoor)',
            requires_terrain_any_of=['TRN-016'],
            requires_equipment_all_of=['Treadmill'],
            requires_skill_toggle=None,
            is_outdoor=False, is_specific=False, base_preference_score=30,
            rationale_template='indoor substitute'),
    ],
    # D-006 Outdoor Road Cycling (and gravel-fit variants)
    'D-006': [
        ModalityOptionDef('outdoor_gravel_ride', 'Outdoor gravel ride',
            requires_terrain_any_of=['TRN-020'],
            requires_equipment_all_of=['Gravel bike'],
            requires_skill_toggle=None,
            is_outdoor=True, is_specific=True, base_preference_score=85,
            rationale_template='gravel surface accessible from {locale_name}, gravel bike on hand'),
        ModalityOptionDef('outdoor_road_ride', 'Outdoor road ride',
            requires_terrain_any_of=['TRN-001'],
            requires_equipment_all_of=['Road bike'],
            requires_skill_toggle=None,
            is_outdoor=True, is_specific=True, base_preference_score=80,
            rationale_template='paved surface accessible, road bike on hand'),
        ModalityOptionDef('indoor_trainer', 'Indoor trainer workout',
            requires_terrain_any_of=['TRN-016'],
            requires_equipment_all_of=['Bike trainer'],
            requires_skill_toggle=None,
            is_outdoor=False, is_specific=False, base_preference_score=40,
            rationale_template='trainer substitute when outdoor unavailable'),
    ],
    # D-010 Outdoor Rock Climbing (gated by climbing_roped capability for rope-based options)
    'D-010': [
        ModalityOptionDef('outdoor_lead_climb', 'Outdoor lead climb',
            requires_terrain_any_of=['TRN-013'],
            requires_equipment_all_of=['Rope','Quickdraws','Harness'],
            requires_skill_toggle='climbing_roped',
            is_outdoor=True, is_specific=True, base_preference_score=90,
            rationale_template='outdoor rock accessible, lead-climbing capability enabled'),
        ModalityOptionDef('outdoor_top_rope', 'Outdoor top-rope climb',
            requires_terrain_any_of=['TRN-013'],
            requires_equipment_all_of=['Rope','Harness'],
            requires_skill_toggle='climbing_roped',
            is_outdoor=True, is_specific=True, base_preference_score=80,
            rationale_template='outdoor rock accessible, rope capability enabled'),
        ModalityOptionDef('outdoor_boulder', 'Outdoor bouldering',
            requires_terrain_any_of=['TRN-013'],
            requires_equipment_all_of=['Crash pad'],
            requires_skill_toggle=None,
            is_outdoor=True, is_specific=True, base_preference_score=70,
            rationale_template='outdoor rock accessible; no rope skill required for bouldering'),
        ModalityOptionDef('gym_lead_climb', 'Gym lead climb',
            requires_terrain_any_of=['TRN-014'],
            requires_equipment_all_of=['Climbing gym membership'],
            requires_skill_toggle='climbing_roped',
            is_outdoor=False, is_specific=True, base_preference_score=60,
            rationale_template='climbing gym accessible, lead capability enabled'),
        ModalityOptionDef('gym_top_rope', 'Gym top-rope',
            requires_terrain_any_of=['TRN-014'],
            requires_equipment_all_of=['Climbing gym membership'],
            requires_skill_toggle=None,
            is_outdoor=False, is_specific=True, base_preference_score=55,
            rationale_template='climbing gym top-rope; no lead capability required'),
        ModalityOptionDef('gym_boulder', 'Gym bouldering',
            requires_terrain_any_of=['TRN-014'],
            requires_equipment_all_of=['Climbing gym membership'],
            requires_skill_toggle=None,
            is_outdoor=False, is_specific=True, base_preference_score=50,
            rationale_template='climbing gym bouldering substitute'),
        ModalityOptionDef('gym_hangboard', 'Hangboard finger-strength',
            requires_terrain_any_of=['TRN-016'],
            requires_equipment_all_of=['Hangboard'],
            requires_skill_toggle=None,
            is_outdoor=False, is_specific=False, base_preference_score=30,
            rationale_template='finger-strength substitute when climbing terrain unavailable'),
    ],
    # ...similar entries for D-005 / D-007 / D-008a / D-008b / D-011 / D-013 / D-014 / D-015 / D-016 / D-020
    # land in the implementation slice. D-013 Wilderness Navigation has no meaningful modality split
    # (one fundamental modality: go outside and navigate) and is intentionally absent from the dict
    # per Trigger #2 padding scrutiny — disciplines with a 1:1 modality return an empty menu and Layer 4
    # falls back to its current freeform reasoning.
}
```

Disciplines absent from `_MODALITY_OPTIONS_PER_DISCIPLINE` produce an empty menu without firing a `no_modality_recommendation` flag (silent pass-through; absence means "no meaningful modality split exists for this discipline"). The flag is reserved for disciplines that ARE in the dict but where no option satisfies the locale's terrain / equipment / skill constraints — see §8.1.

### 5.2 Resolution loop

For each `(discipline_id, locale)` pair in `included_discipline_ids × cluster_locale_inputs`:

```python
menu: list[ModalityOption] = []
for opt_def in _MODALITY_OPTIONS_PER_DISCIPLINE.get(discipline_id, []):
    terrain_ok = bool(set(opt_def.requires_terrain_any_of) & set(locale.locale_terrain_ids)) \
                 if opt_def.requires_terrain_any_of else True
    equip_ok = set(opt_def.requires_equipment_all_of).issubset(set(locale.effective_pool)) \
               if opt_def.requires_equipment_all_of else True
    skill_ok = (opt_def.requires_skill_toggle is None
                or skill_toggle_states.get(opt_def.requires_skill_toggle) is True)
    if terrain_ok and equip_ok and skill_ok:
        menu.append(ModalityOption(
            modality_id=opt_def.modality_id,
            modality_name=opt_def.modality_name,
            preference_score=opt_def.base_preference_score,
            is_outdoor=opt_def.is_outdoor,
            is_specific=opt_def.is_specific,
            rationale_hint=opt_def.rationale_template.format(locale_name=locale.locale_name or locale.locale_id),
            satisfied_terrain=list(set(opt_def.requires_terrain_any_of) & set(locale.locale_terrain_ids)),
            satisfied_equipment=list(opt_def.requires_equipment_all_of),
            satisfied_skill=opt_def.requires_skill_toggle,
        ))
menu.sort(key=lambda m: (-m.preference_score, m.modality_id))  # stable order; deterministic
```

Top-pick = `menu[0]` if non-empty, else `None`. Rationale-hint surfaces `menu[0].rationale_hint` (Layer 4 may rephrase in coach voice).

### 5.3 Preference scoring

The `base_preference_score` is a static 0-100 weight encoding three baked-in biases:

1. **Outdoor > Indoor** — outdoor venues score higher than indoor substitutes for the same discipline. Counters the "treadmill is always available so it always wins" failure mode.
2. **Specific > Generic** — a sport-specific modality (e.g. `outdoor_gravel_ride` for D-006 when on TRN-020) scores higher than a generic substitute (e.g. `indoor_trainer`). Counters the "any-bike-is-fine" failure mode.
3. **Available skill > Requires-coached-introduction** — a modality whose `requires_skill_toggle` is satisfied scores higher (implicit; modalities that aren't satisfied don't make it into the menu at all). When two satisfied modalities tie on outdoor + specific, the tiebreaker is the explicit `base_preference_score` int.

Scores are NOT phase-aware. Phase ranking is Layer 4's job: e.g. in Peak phase Layer 4 should bias toward `outdoor_lead_climb` over `gym_top_rope` even if both are in the menu; in Taper Layer 4 should bias toward `gym_top_rope` (lower stimulus) even if `outdoor_lead_climb` outranks on base score. The resolver provides the menu; Layer 4 picks with phase context.

Score conventions (suggested, refined during implementation):
- 85-95: outdoor + specific + skill-satisfied (the "ideal" modality at this locale)
- 70-84: outdoor + specific + no skill required (or skill satisfied)
- 55-69: outdoor + generic (e.g. road run for trail runner when only paved accessible)
- 40-54: indoor + specific (e.g. indoor_trainer for cyclist with smart trainer)
- 30-39: indoor + generic substitute (e.g. treadmill_run for trail runner)
- 0-29: degenerate fallback (e.g. hangboard-only when no climbing terrain at all)

### 5.4 Menu pruning

If multiple satisfied options share the same `(discipline_id, locale_id, is_outdoor)` triplet, all surface in the menu — no deduplication. Layer 4 may pick `gym_lead_climb` over `gym_top_rope` based on phase intent (strength build vs taper); both stay visible.

If a satisfied option's `is_specific=True` outranks every satisfied `is_specific=False` option, the generic options still surface (lower-ranked in the menu) so Layer 4 has the substitute available for travel days or recovery sessions. They're not stripped from the menu.

## 6. Skill-toggle gating semantics

The `requires_skill_toggle` field on `ModalityOptionDef` mirrors the existing gear-toggle / skill-toggle default-OFF semantic from `layer2b/builder.py::_emit_coaching_flags` + `layer2c/builder.py::_emit_coaching_flags` (BucketC_l). Pattern:

- `requires_skill_toggle is None` → option is always skill-eligible.
- `requires_skill_toggle = 'climbing_roped'` AND `skill_toggle_states.get('climbing_roped') is True` → option is skill-satisfied.
- `requires_skill_toggle = 'climbing_roped'` AND `skill_toggle_states.get('climbing_roped')` is False / missing → option is skill-NOT-satisfied → omitted from the menu.

This means: an athlete with `climbing_roped=False` (default for new athletes per SkillCaptureSurface) sees `outdoor_boulder` + `gym_top_rope` + `gym_boulder` + `gym_hangboard` in their D-010 menu — the un-roped subset. As soon as they enable `climbing_roped` via `/profile?tab=skills` (or onboarding Step 5), the lead-climb and top-rope rows appear in their menu on the next plan-refresh (cache eviction fires per the Layer 1 policy shipped in SkillCaptureSurface).

The orchestrator already threads `skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states` end-to-end (BucketC_l + SkillCaptureSurface). The resolver just consumes the same dict.

## 7. Payload schema

```python
@dataclass(frozen=True)
class Layer2ModalityPayload:
    etl_version_set: dict[str, str]
    recommendations: list[ModalityRecommendation]
    coaching_flags: list[ModalityCoachingFlag]

@dataclass(frozen=True)
class ModalityRecommendation:
    discipline_id: str
    discipline_name: str                 # Resolved from layer0.disciplines.canonical_name
    locale_id: str
    locale_name: str | None
    menu: list[ModalityOption]           # Ranked by preference_score DESC; empty when no option satisfies
    top_pick_modality_id: str | None     # menu[0].modality_id or None
    rationale_hint: str | None           # menu[0].rationale_hint or None

@dataclass(frozen=True)
class ModalityOption:
    modality_id: str
    modality_name: str
    preference_score: int
    is_outdoor: bool
    is_specific: bool
    rationale_hint: str
    satisfied_terrain: list[str]         # TRN-xxx ids that matched
    satisfied_equipment: list[str]       # equipment canonical names that matched
    satisfied_skill: str | None          # skill toggle name that satisfied (or None when not gated)

@dataclass(frozen=True)
class ModalityCoachingFlag:
    flag_type: str                       # See §8
    discipline_id: str
    discipline_name: str
    locale_id: str | None                # None for cluster-wide flags
    locale_name: str | None
    message: str                         # Coach-voice human-readable
    metadata: dict                       # Structured payload for Layer 4
```

## 8. Coaching flag rules

Three triggers, all surfaced in the same `coaching_flags[]` list. Layer 4 decides display priority and copy.

### 8.1 `no_modality_recommendation`

Trigger: discipline is in `_MODALITY_OPTIONS_PER_DISCIPLINE` (i.e. has a meaningful modality split) AND every option for the discipline is unsatisfied at EVERY locale in the cluster.

```python
ModalityCoachingFlag(
    flag_type='no_modality_recommendation',
    discipline_id='D-006',
    discipline_name='Outdoor Road Cycling',
    locale_id=None,
    locale_name=None,
    message=("You included Outdoor Road Cycling but none of your locales has a satisfying modality "
             "(no paved/gravel terrain, no bike equipment, no indoor trainer). "
             "Consider adding bike equipment or a locale with cycling-accessible terrain."),
    metadata={
        'missing_terrain': ['TRN-001','TRN-020','TRN-016'],
        'missing_equipment': ['Road bike','Gravel bike','Bike trainer'],
        'missing_skill': None,
    }
)
```

One flag per affected discipline. Cluster-wide (not per-locale) since the trigger fires only when EVERY locale fails.

### 8.2 `only_generic_modality_available`

Trigger: at least one locale has a satisfied modality for the discipline, but NO satisfied option has `is_specific=True` at any locale.

```python
ModalityCoachingFlag(
    flag_type='only_generic_modality_available',
    discipline_id='D-006',
    discipline_name='Outdoor Road Cycling',
    locale_id='home',
    locale_name='Home (Nerstrand MN)',
    message=("You included Outdoor Road Cycling but only the indoor-trainer substitute is available "
             "at your locales. Specific outdoor riding will be limited; consider adding paved or "
             "gravel terrain to your locale, or accept reduced outdoor-specific stimulus."),
    metadata={
        'specific_options_unavailable': ['outdoor_gravel_ride','outdoor_road_ride'],
        'generic_options_available': ['indoor_trainer'],
        'missing_terrain': ['TRN-001','TRN-020'],
        'missing_equipment': ['Road bike','Gravel bike'],
    }
)
```

One flag per discipline. `locale_id` set to the first locale where the generic-only condition holds.

### 8.3 `skill_capability_blocks_specific_modality`

Trigger: a discipline has a `requires_skill_toggle`-gated specific modality that would be satisfied on terrain + equipment, but the skill toggle is OFF — AND no other specific modality fills the same role.

Example: D-010 athlete has `Rope` + `Quickdraws` + `Harness` + TRN-013 accessible, but `climbing_roped=False`. `outdoor_lead_climb` would otherwise be satisfied (and would be the top-pick). The flag tells Layer 4 + the athlete that enabling the toggle would unlock the better option.

```python
ModalityCoachingFlag(
    flag_type='skill_capability_blocks_specific_modality',
    discipline_id='D-010',
    discipline_name='Outdoor Rock Climbing',
    locale_id='home',
    locale_name='Home (Nerstrand MN)',
    message=("Outdoor lead climbing is the best-fit modality at Home but requires the "
             "'climbing_roped' skill toggle, which is currently OFF. Enable it on your Profile "
             "→ Skills tab if you have lead-climbing experience."),
    metadata={
        'blocked_modality_id': 'outdoor_lead_climb',
        'blocking_skill_toggle': 'climbing_roped',
        'currently_resolves_to': 'outdoor_boulder',
    }
)
```

One flag per `(discipline, locale, blocking_skill)` triplet. Coordinates with the existing `requires_skill_capability` flag emitted by Layer 2C — those two flags reinforce each other (the 2C flag says "this discipline has coaching needs you've default-OFF'd"; the modality flag says "AND you'd unlock a better session option").

## 9. Caching & determinism

Per the architectural pick (A2), the resolver is deterministic given inputs. Cache strategy mirrors Layer 2C §9:

**Cache key:**

```
(athlete_id, sha256(sorted_cluster_locale_inputs), sha256(sorted(included_discipline_ids)),
 sha256(sorted(skill_toggle_states.items())), sha256(etl_version_set))
```

`athlete_id` is required because `cluster_locale_inputs` (terrain + equipment) and `skill_toggle_states` are athlete-specific.

**Invalidation triggers** (all already exist in `layer4/cache_invalidation.py` from prior slices — no new policy work required):

- Athlete's locale terrain changes → `evict_layer2b_on_terrain_change` already evicts; resolver shares the same input surface.
- Athlete's locale equipment changes → `evict_layer2c_on_equipment_change` already evicts; resolver consumes 2C's effective_pool.
- Athlete's skill toggles change → `evict_layer1_on_skill_toggle_change` (SkillCaptureSurface §3.1) already evicts the full Layer 1 cone, which transitively forces the resolver to re-run.
- `included_discipline_ids` changes (e.g. race-event discipline grid edit) → `evict_on_target_event_included_discipline_ids_change` (BucketE_B2_C1) already uses the `layer2a` policy which evicts all 4 entry points + both Layer 3 wrappers; resolver lives downstream and is forced to re-run.
- New ETL run → invalidates all entries with the old `etl_version_set` hash via the existing whole-cone eviction.

**No new cache invalidation surface required.** The resolver lives on the existing cone; existing eviction policies cover it transitively.

**Latency target:** <50ms per `(discipline, locale)` pair. Pure-Python set arithmetic against ~20-row vocab, no DB call after the single discipline-name SELECT. With typical AR cluster (3 locales × 12 disciplines = 36 pairs), total budget <2s comfortably.

## 10. Edge cases

| Case | Behavior |
|---|---|
| Empty `locale_terrain_ids` for a locale | Every modality requiring outdoor terrain fails. Indoor substitutes still satisfy if `TRN-016` is in the implied indoor-locale terrain set — but a locale with literally no terrain rows is degenerate; flag `no_modality_recommendation` fires for every meaningful-split discipline. |
| Empty `effective_pool` for a locale | Bodyweight-tier modalities (those with `requires_equipment_all_of=[]`) still resolve. Most equipment-gated options fail. Expect heavy `no_modality_recommendation` firing. |
| Discipline absent from `_MODALITY_OPTIONS_PER_DISCIPLINE` | Returns an empty menu without flag firing. Layer 4 falls back to its current freeform reasoning for that discipline. |
| `skill_toggle_states=None` | Treated as `{}`; all skill-gated options fail their gate (default-OFF). Matches existing gear-toggle / skill-toggle precedent. |
| Locale has both indoor (TRN-016) and outdoor terrain | Both indoor and outdoor modalities surface in the menu, ranked by preference. Athlete's home locale is the typical case. |
| Two locales tie on `top_pick_modality_id` for the same discipline | Both `ModalityRecommendation` rows surface independently. Layer 4 picks the locale per session. |
| `requires_equipment_all_of` references an equipment name that doesn't exist in `layer0.equipment_items` | No validation at resolver runtime — the dict is the source of truth. Adding a typo in the module-level dict produces a permanently-unsatisfied option; caught by the implementation slice's test suite (every modality's `requires_equipment_all_of` entry must round-trip against the active 0B equipment vocab — a static lint test on module load). |
| `requires_terrain_any_of` references a TRN-xxx that doesn't exist | Same as above; static lint test catches it. |
| `requires_skill_toggle` references a toggle name not in the active `layer0.skill_capability_toggles` populate | Static lint test catches it. |
| All disciplines in `included_discipline_ids` are absent from the dict (i.e. no meaningful splits anywhere) | Returns `Layer2ModalityPayload(recommendations=[], coaching_flags=[])`. Layer 4 sees empty payload; falls back to freeform reasoning. This is the legitimate "nothing to recommend" path. |

## 11. Performance budget

Per-pair: ~1-3ms (Python set operations against a list of ~5-10 ModalityOptionDef entries). Discipline-name SELECT batched outside the loop: one query per call returning `{discipline_id: canonical_name}` for all `included_discipline_ids`. Total per-call budget for a typical 3-locale × 12-discipline cluster: ~50-100ms incl. the single DB roundtrip.

Cache hit: <5ms (deserialization only).

Total Layer 4 budget impact: negligible.

## 12. Open items / forward references

| # | Item | Owner | Status |
|---|---|---|---|
| BM-1 | Full population of `_MODALITY_OPTIONS_PER_DISCIPLINE` (this spec ships 3 disciplines as representative; D-005 / D-007 / D-008a / D-008b / D-011 / D-013 / D-014 / D-015 / D-016 / D-020 land in the implementation slice) | Implementation slice author | Open |
| BM-2 | Phase-aware ranking inside Layer 4 (resolver gives a static menu; Layer 4 needs to encode "Peak bias → specific outdoor over indoor; Taper bias → lower-stimulus options") | Layer 4 design follow-on | Out of scope here; spec'd as Layer 4's responsibility (§5.3) |
| BM-3 | Layer 4 prompt-body integration — where in the plan-gen prompt do recommendations land, and how does the LLM cite them when synthesising sessions? | Layer 4 design follow-on | Open; pairs with BM-2 |
| BM-4 | `Rappelling / abseiling` — D-011 modality split (outdoor_rappel_practice / gym_simulated_rappel). Skips this spec because D-011 also has the `also_satisfies` chain from `Climbing — roped` (Layer 2C §6 one-hop) which complicates the toggle-gating logic. Resolve in implementation slice when the full dict lands. | Implementation slice author | Open |
| BM-5 | Equipment-name canonicalisation — the spec writes equipment names verbatim (`Gravel bike`, `Crash pad`) but `layer0.equipment_items.canonical_name` is the authoritative source. Static lint test (§10) catches mismatches; resolver code should reference equipment-name constants extracted from the equipment vocab. | Implementation slice author | Open |
| BM-6 | Multi-discipline modality sharing — a single outdoor session at TRN-002 might satisfy both D-001 (Trail Running) AND D-013 (Wilderness Navigation, no menu) via combined intent. Resolver returns per-discipline rows; Layer 4 picks combined sessions. Not a resolver concern but worth flagging for Layer 4 design. | Layer 4 design | Out of scope here |

## 13. Test scenarios

These are the integration scenarios the resolver must handle correctly. Spec'd here so when the implementation slice's tests are written, coverage is clear.

### 13.1 Andy at home — full AR cluster, default-OFF skill toggles

Inputs:
- `cluster_locale_inputs = [home_locale]` where `home_locale.locale_terrain_ids = ['TRN-001','TRN-002','TRN-003','TRN-004','TRN-008','TRN-016']` (per the Phase 5.1 form-refresh C carry-forward), `home_locale.effective_pool = <Andy's home gym + 'Road bike' + 'Treadmill'>`
- `included_discipline_ids = <PGE 2026 AR set>`
- `skill_toggle_states = {}` (default-OFF baseline)

Expected:
- D-001 Trail Running: top_pick = `outdoor_trail_run` (TRN-002/003/004 satisfy); menu includes `outdoor_road_run` + `treadmill_run` as lower-ranked alternates.
- D-006 Outdoor Road Cycling: top_pick = `outdoor_road_ride` (TRN-001 + Road bike satisfy); menu includes `indoor_trainer` if Andy has a trainer in effective_pool.
- D-010 Outdoor Rock Climbing: TRN-013 not in locale_terrain_ids → no outdoor climbing options resolve; if TRN-014 not in locale either, menu empty → `no_modality_recommendation` flag fires for D-010 (Andy needs to add a climbing-accessible locale).
- D-008b Outdoor Paddling: TRN-009 + Packraft in effective_pool would satisfy `outdoor_paddle_packraft`; `whitewater_handling=False` means whitewater-gated options stay out of the menu.
- Coaching flags: 0-1 `no_modality_recommendation` (D-010), 0 `only_generic_modality_available`, 0 `skill_capability_blocks_specific_modality` (no eligible-but-gated options at home for any toggle).

### 13.2 Andy enables `climbing_roped` + adds a climbing-gym locale

Same as 13.1 but `cluster_locale_inputs` gains a `climbing_gym` locale with `locale_terrain_ids=['TRN-014','TRN-016']` + `effective_pool=['Climbing gym membership','Hangboard']`, AND `skill_toggle_states={'climbing_roped': True}`.

Expected:
- D-010 at `climbing_gym`: top_pick = `gym_lead_climb` (TRN-014 + membership + roped capability); menu = [lead, top_rope, boulder, hangboard].
- D-010 at `home`: still empty menu → `no_modality_recommendation` does NOT fire because the cluster-wide check passes (climbing_gym satisfies).
- `skill_capability_blocks_specific_modality` does NOT fire (toggle is ON).

### 13.3 Andy disables `climbing_roped` after step 13.2

Same as 13.2 but `skill_toggle_states={'climbing_roped': False}`.

Expected:
- D-010 at `climbing_gym`: top_pick = `gym_top_rope` (rope-skill-NOT-required option that survived); menu = [top_rope, boulder, hangboard].
- `skill_capability_blocks_specific_modality` FIRES: blocked_modality_id=`gym_lead_climb`, blocking_skill_toggle=`climbing_roped`, currently_resolves_to=`gym_top_rope`.

### 13.4 Empty cluster — degenerate

Inputs:
- `cluster_locale_inputs=[empty_locale]` with `locale_terrain_ids=[]` + `effective_pool=[]`
- `included_discipline_ids=['D-001','D-006','D-010']`
- `skill_toggle_states={}`

Expected:
- All three menus empty.
- `no_modality_recommendation` fires for each (3 flags).
- No call failure.

### 13.5 Hotel locale — indoor-only

Inputs:
- `cluster_locale_inputs=[hotel]` with `locale_terrain_ids=['TRN-016']` + `effective_pool=['Treadmill','Dumbbells','Bench']`
- `included_discipline_ids=['D-001','D-006','D-010']`
- `skill_toggle_states={'climbing_roped': True}`

Expected:
- D-001 top_pick = `treadmill_run` (indoor + generic; preference 30). Menu = [treadmill_run].
- D-006: no bike + no bike-trainer in effective_pool → empty menu → `no_modality_recommendation`.
- D-010: TRN-013 + TRN-014 both absent → empty menu → `no_modality_recommendation`.
- `only_generic_modality_available` fires for D-001 (only generic option survived; no specific outdoor option resolved).

### 13.6 Static lint — every option references valid vocab

For each `ModalityOptionDef` in the module-level dict:
- Every `requires_terrain_any_of` entry exists in the active 0C terrain_types.
- Every `requires_equipment_all_of` entry exists in the active 0B equipment_items.canonical_name.
- Every `requires_skill_toggle` (if non-None) exists in the active 0C skill_capability_toggles.toggle_name.

This is a test, not a runtime check — it catches drift between the resolver's module-level dict and the ETL-managed vocab at CI time, NOT at orchestrator runtime. Failure mode = test red, fix the dict.

## 14. Gut check

**What this spec gets right:**
- Pins the architectural principle (terrain = SURFACE; modality = combination of terrain + equipment + skill + discipline) and gives it a runtime materialisation.
- Mirrors the existing Python-rule precedent (gear-toggle / skill-toggle) — no new architectural pattern introduced.
- No new schema; piggybacks on Layer 1 + 2C cache invalidation surfaces already shipped.
- Menu-not-decision pattern leaves Layer 4 free to apply phase awareness without re-fighting modality combinatorics.
- Edge cases enumerated; static lint test catches drift between resolver vocab and ETL vocab.
- Default-OFF skill toggle semantic stays consistent with BucketC_l + SkillCaptureSurface.

**Risks:**
- **Module-level vocab drift.** Adding a new modality requires editing a Python module, not a DB row. Tradeoff: no schema burden, but vocab evolution requires a code deploy. Counter: same tradeoff already accepted for `_TOGGLE_ALSO_SATISFIES` (Phase 2.4-Prep) + `_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS` (BucketC_g). Pattern is precedent.
- **Equipment-name string matching.** `requires_equipment_all_of=['Gravel bike']` matches by literal string against `effective_pool`. If 0B vocab renames `Gravel bike` to `Gravel bike (700c)`, the rule silently breaks. Mitigation: static lint test (§13.6) catches at CI. Stronger mitigation: extract equipment-name constants from the equipment vocab at module import time. Implementation-slice call.
- **Static preference scores oversimplify.** A score of 90 vs 85 is a guess. Pairs that should be context-dependent (e.g. trail run vs road run depends on race terrain + phase) get a static base. Counter: Layer 4 owns context; resolver owns the menu. The scores narrow the option space; they don't decide.
- **Discipline coverage is partial in v1.** Only 3 disciplines are spec'd in §5.1 dict. The implementation slice has to populate D-005/D-007/D-008a/D-008b/D-011/D-014/D-015/D-016/D-020 carefully. Trigger #2 padding scrutiny applies: disciplines without a meaningful modality split (e.g. D-013 Wilderness Navigation) stay absent.

**What might be missing:**
- **Time-of-day / weather modality biases.** A summer afternoon outdoor run at 35°C is a different modality than 6am cool. The resolver doesn't see weather. Layer 4's job; not pinning here.
- **Race-specific preference.** For an athlete training for an ultra on TRN-002, `outdoor_trail_run` should rank higher than `outdoor_road_run` when both satisfy. The static base already encodes this (90 vs 60). For mixed-terrain races, Layer 4 may want to weight differently per-session — that's phase + race intent reasoning, not modality reasoning.
- **Cross-discipline modality bundling.** A long session in the woods might satisfy both D-001 + D-013 + D-005 simultaneously. The resolver returns per-discipline rows; Layer 4 picks bundles. Flagged BM-6.
- **Equipment AND-group semantics.** `requires_equipment_all_of=['Rope','Quickdraws','Harness']` requires ALL three. No OR-groups currently; could be added (e.g. "Rope AND Harness AND (Quickdraws OR Slings)") if a real case demands it. Defer to implementation slice.

**Best argument against this spec as drafted:** The vocab fragmentation across module-level dict + ETL `equipment_items` + ETL `terrain_types` + ETL `skill_capability_toggles` is real cognitive load. Adding a new discipline modality means editing one Python module AND maintaining alignment with three Layer 0 tables. The A1 (static table) alternative would have unified everything in `layer0.modality_recommendations`. Counter: A1's row-count grows multiplicatively (every discipline × every terrain × every equipment combo → 100+ rows of mostly-sparse joins) and would have needed a populate script for every release. The Python-rule pattern is more compact at modest cognitive cost; the static lint test (§13.6) keeps drift loud.

**End of spec.**
