# Layer 2C — Equipment Mapper (Query Node)

**Status:** Consolidated spec, first draft 2026-05-10. Supersedes design notes scattered across `Batch_A_Done_Batches_BC_Kickoff_Handoff.md`, `ETL_Spec_v3_Corrections_2ABC_v2.md`, and `Layer0_to_PlanGen_Contract_Preview.md`.
**Type:** Query node. Pure read, deterministic given inputs, no LLM involvement.
**Predecessor decisions:** All design calls from prior sessions are folded in. Open items flagged inline.

---

## 1. Purpose

Given an athlete's equipment at a specific locale (e.g., their home gym, a hotel, a partner's house) plus the gear toggles currently enabled across their training cluster, decide which exercises from the active Layer 0 exercise pool are available, at what tier, with what substitute or proxy detail. Hand the result to Layer 4 plan generation so it can prescribe exercises with named variants ("threshold intervals on Mountain bike", "DB Bench Press") rather than generic placeholders.

Per-locale, not per-cluster. A single 2C call answers one question: "for THIS locale's equipment, what's available?" Layer 4 invokes 2C once per locale in a cluster and picks per-session which output applies.

## 2. What 2C does NOT do

Clarifying boundaries to prevent scope creep:

- **Does not filter by injury or health condition.** That's 2D / pool filter. 2C returns a comprehensive equipment-resolved view; downstream filters reduce it.
- **Does not schedule exercises.** Layer 4 picks what to prescribe.
- **Does not resolve terrain.** Layer 2B owns terrain. 2C returns `terrain_required` on each resolved exercise as pass-through metadata; Layer 4 cross-references with 2B output to decide per-session terrain fit.
- **Does not consume `discipline_technique_foci`.** Foci are orthogonal coaching emphasis, picked by Layer 4 from a separate query.
- **Does not pick between Tier 2 and Tier 3** when both resolve. It surfaces both so Layer 4 can render "Try improvised X, OR proxy Y" per the documented athlete-facing UX.
- **Does not handle multi-cluster plans.** Each cluster's 2C runs independently. Layer 4 / plan-gen handles cluster selection per session.

## 3. Function signature

```python
def q_layer2c_equipment_mapper_payload(
    locale_id: str,
    locale_equipment_pool: list[str],
    cluster_locale_ids: list[str],
    cluster_gear_toggle_states: dict[str, bool],
    included_discipline_ids: list[str],
    etl_version_set: dict[str, str]
) -> Layer2CPayload:
    ...
```

### Parameters

| Param | Type | Source | Notes |
|---|---|---|---|
| `locale_id` | str | Layer 1 (§J Locales) | Unique identifier for the specific locale being mapped |
| `locale_equipment_pool` | list[str] | Layer 1 (§J Equipment Inventory for this locale) | Canonical equipment names from `layer0.equipment_items.canonical_name`. Must already include any `is_universal=true` items the locale has. |
| `cluster_locale_ids` | list[str] | Layer 1 (§J cluster definition) | All locales in this athlete's cluster. Context only — not used for equipment union (equipment is locale-scoped). |
| `cluster_gear_toggle_states` | dict[str, bool] | Layer 1 (§J Gear Readiness) | Each toggle_name → on/off. Toggles unioned across cluster ("climbing kit travels"). |
| `included_discipline_ids` | list[str] | Layer 1 / 2A | Disciplines the athlete is training. Drives which exercises are considered. |
| `etl_version_set` | dict[str, str] | Plan-gen pin | Per spec v3 §5.1 Decision 2. Locks Layer 0 version for the plan. |

### Return type

See §7 below.

## 4. Input validation (preconditions)

Fail-loud rather than fail-silent on bad inputs. The validation happens before any DB query.

1. `locale_id` non-empty string.
2. `locale_equipment_pool` is a list (may be empty — extreme case is valid; see §10).
3. Every token in `locale_equipment_pool` is a string. (No canonical-name validation against `equipment_items` at runtime — that's UI-side validation per §J vocab decision.)
4. `cluster_locale_ids` non-empty; contains `locale_id`.
5. `cluster_gear_toggle_states` keys are strings, values are bools. (Toggle-name vocab validation is UI-side.)
6. `included_discipline_ids` non-empty.
7. `etl_version_set` contains keys for `0A`, `0B`, `0C` at minimum.

Validation failure → raise `Layer2CInputError`. Plan-gen catches and surfaces a user-facing error. This is NOT a HITL gate — HITL is for ambiguous content, not malformed inputs.

## 5. Algorithm

### 5.1 Effective pool construction

The "effective pool" is the equipment universe 2C reasons against. It's wider than `locale_equipment_pool` because cluster-scoped gear toggles add equipment.

```
effective_pool = set(locale_equipment_pool)
for toggle_name, enabled in cluster_gear_toggle_states.items():
    if enabled:
        toggle_def = lookup_toggle(toggle_name, etl_version_set['0C'])
        effective_pool.update(toggle_def.paired_equipment_categories)
        effective_pool.update(toggle_def.also_satisfies)
```

**[DECISION POINT — toggle definition lookup at runtime vs pre-resolved by Layer 1]**

Two paths:

- **(A) Runtime lookup** (drafted above). 2C queries `layer0.sport_specific_gear_toggles` at runtime for `paired_equipment_categories[]` and `also_satisfies[]` per active toggle. Simple, no extra Layer 1 storage. Adds 1 query per 2C call.
- **(B) Pre-resolved by Layer 1.** `cluster_gear_toggle_states` becomes `dict[str, ToggleState]` where `ToggleState` has `enabled: bool` plus `implied_equipment: list[str]` already expanded. Layer 1 does the lookup once at toggle-state-change time. 2C doesn't query the toggles table at all.

Prior session notes said `sport_specific_gear_toggles` is "NOT consumed at runtime" but didn't address the implied-equipment lookup specifically. Recommend (A) for simplicity — the extra query is cheap (11 rows, indexed) and (B) duplicates state. **Andy decision needed before implementation.**

If (A), the consumer table in spec §8 gets a footnote: "2C consumes `sport_specific_gear_toggles.paired_equipment_categories` and `also_satisfies` only — not display/description fields." If (B), Layer 1 §J spec needs an `implied_equipment` field on the toggle state record.

### 5.2 Discipline → exercise enumeration

For each `discipline_id` in `included_discipline_ids`, resolve to the set of exercises relevant via `sport_discipline_bridge` and `sport_exercise_map`:

```sql
SELECT
  sxm.exercise_id,
  sxm.exercise_name,
  sxm.exercise_type,
  sxm.sport_name,
  sxm.priority,
  e.equipment_required,
  e.equipment_substitutes_structured,
  e.physical_proxies,
  e.terrain_required,
  e.contraindicated_parts,
  e.contraindicated_conditions
FROM layer0.sport_discipline_bridge sdb
JOIN layer0.sport_exercise_map sxm
  ON sxm.sport_name = sdb.exercise_db_sport
JOIN layer0.exercises e
  ON e.exercise_id = sxm.exercise_id
WHERE sdb.discipline_id = ANY(%s)              -- included_discipline_ids
  AND sdb.etl_version = %s                     -- etl_version_set['0A']
  AND sxm.etl_version = ANY(%s)                -- all 0B versions active
  AND e.etl_version = ANY(%s)                  -- all 0B versions active
  AND sdb.superseded_at IS NULL
  AND sxm.superseded_at IS NULL
  AND e.superseded_at IS NULL;
```

Notes on the query:

- `sport_discipline_bridge` resolves discipline_id → exercise_db_sport (the naming used in the exercise DB, which differs from the framework_sport naming used in 0A; this is the bridge's whole job).
- Exercise DB uses multiple active etl_versions concurrently (currently `0B-v1.3.1`, `0B-v19.B`, `0B-v19.C`). The query uses `= ANY` against the set of active 0B versions resolved from `etl_version_set['0B']` — pin-by-version-set, not pin-by-single-version. Same for sport_exercise_map.
- Aggregator-row defensive filter from D-05 is **not needed here** — 2C doesn't touch `phase_load_allocation`.
- An exercise may appear under multiple disciplines (e.g., a strength exercise sport-mapped to both Trail Running and Hiking). Deduplicate by `exercise_id` in post-processing; track `discipline_ids[]` per exercise for later reporting.

### 5.3 Tier 1 resolution

```
tier_1(exercise, effective_pool):
  required = set(exercise.equipment_required or [])
  return required.issubset(effective_pool)
```

`equipment_required[]` is a flat TEXT[] — AND semantics, all items required. Post-Batch C, this is clean (no implicit-OR alternatives mixed in).

Empty `equipment_required[]` → Tier 1 = TRUE (bodyweight exercise, always available).

### 5.4 Tier 2 resolution

If Tier 1 fails, iterate `equipment_substitutes_structured` JSONB:

```python
def tier_2(exercise, effective_pool):
    subs = exercise.equipment_substitutes_structured or []
    for sub in subs:
        if sub.get('is_improvised', False):
            return Tier2Result(
                substitute_text=sub['substitute_text'],
                substitute_equipment=sub.get('equipment_required', []),
                is_improvised=True
            )
        # CNF resolution: outer OR of inner AND groups
        equipment_groups = sub.get('equipment_required', [])
        for group in equipment_groups:
            if set(group).issubset(effective_pool):
                return Tier2Result(
                    substitute_text=sub['substitute_text'],
                    substitute_equipment=[group],   # the matching group only
                    is_improvised=False
                )
    return None
```

**Key rules:**

- Iteration order is array order (preserved from Batch C 3-bucket sort: equipment variants → cross-modal → improvised).
- First match wins. The Batch C merge order ensures stimulus-proximity priority.
- `is_improvised: true` always resolves — improvised substitutes assume household items the athlete has by default (backpack, gallon jugs, stairs, etc.). No equipment check needed.
- CNF semantics: `equipment_required: [[a, b], [c]]` means `(a AND b) OR (c)`. Match against pool with set-issubset on each inner group.
- An empty `equipment_required` on a non-improvised substitute means "no additional equipment needed" — auto-resolves (this matches the K-parser data for bodyweight-variant subs).
- The returned `substitute_equipment` is the matching group only, not the full CNF. Layer 4 needs to know which specific items to use.

### 5.5 Tier 3 resolution

If Tier 2 also fails, iterate `physical_proxies` JSONB:

```python
def tier_3(exercise, effective_pool, exercise_index):
    proxies = exercise.physical_proxies or []
    for proxy in proxies:
        proxy_id = proxy.get('exercise_id')
        if proxy_id not in exercise_index:
            continue  # broken reference; log and skip
        proxy_ex = exercise_index[proxy_id]
        if tier_1(proxy_ex, effective_pool):
            return Tier3Result(
                proxy_exercise_id=proxy_id,
                proxy_exercise_name=proxy.get('exercise_name', proxy_ex.exercise_name)
            )
    return None
```

**Key rules:**

- Only Tier 1 is checked on proxies — no cascading. A proxy whose own primary equipment fails is not considered. Rationale: proxies are already a fallback concept; cascading their substitutes muddles "what does Layer 4 actually prescribe?"
- `physical_proxies` JSONB shape (per ETL spec v3 §4.12): `[{"exercise_id": "EX020", "exercise_name": "Nordic Hamstring Curl"}, ...]`.
- The `exercise_index` is a dict built from the §5.2 query results (`{exercise_id: row}`). Proxies pointing to exercises not in the index for this discipline set are skipped silently — proxies can reference any exercise in Layer 0, not just discipline-relevant ones, but if a proxy isn't pre-loaded we don't fetch it on the fly. Performance.
- Iteration order is array order. First proxy whose primary works wins.

### 5.6 Per-discipline coverage aggregation

After every exercise in the §5.2 query result is resolved to a tier (1, 2, 3, or unavailable), compute coverage per included discipline:

```python
for discipline_id in included_discipline_ids:
    exercises_for_discipline = [r for r in resolved if discipline_id in r.discipline_ids]
    total = len(exercises_for_discipline)
    by_tier = Counter(r.tier for r in exercises_for_discipline)
    coverage_pct = (by_tier[1] + by_tier[2] + by_tier[3]) / total if total else 0.0
    yield DisciplineCoverage(
        discipline_id=discipline_id,
        total_exercises=total,
        tier_1_count=by_tier[1],
        tier_2_count=by_tier[2],
        tier_3_count=by_tier[3],
        unavailable_count=by_tier[0],
        coverage_pct=coverage_pct
    )
```

## 6. Toggle handling — `also_satisfies` chains

Batch A added `also_satisfies TEXT[]` to `sport_specific_gear_toggles` for transitive implications. Currently populated only for:

- `Climbing — roped` → `also_satisfies = ['Rappelling / abseiling']`

When `Climbing — roped` toggle is ON, the effective pool gains both:

- All items in `paired_equipment_categories[]` for `Climbing — roped`
- All items in `paired_equipment_categories[]` for `Rappelling / abseiling`

So an athlete with the climbing toggle ON can do rappelling exercises even if the rappelling toggle is OFF. This mirrors the real-world fact that climbing-kit ownership implies the means to rappel.

**No cascade beyond one hop.** `also_satisfies` only expands one level. If toggle X also_satisfies Y, and Y also_satisfies Z, X does NOT imply Z transitively. (Currently moot — only one toggle uses also_satisfies — but stating the rule prevents future surprise.)

## 7. Payload schema

```python
@dataclass
class Layer2CPayload:
    locale_id: str
    etl_version_set: dict[str, str]
    effective_pool: list[str]            # Sorted, deduplicated
    discipline_coverage: list[DisciplineCoverage]
    exercises_resolved: list[ResolvedExercise]
    coaching_flags: list[CoachingFlag]

@dataclass
class DisciplineCoverage:
    discipline_id: str
    discipline_name: str
    exercise_db_sport: str               # From bridge, useful for downstream cross-ref
    total_exercises: int
    tier_1_count: int
    tier_2_count: int
    tier_3_count: int
    unavailable_count: int
    coverage_pct: float                  # (t1+t2+t3) / total

@dataclass
class ResolvedExercise:
    exercise_id: str
    exercise_name: str
    exercise_type: str
    discipline_ids: list[str]            # Which included disciplines this exercise serves
    sport_relevance_notes: dict[str, str]  # discipline_id → sport_relevance_note from sxm
    priority_per_discipline: dict[str, str]  # discipline_id → priority string
    tier: int                            # 0 (unavailable), 1, 2, or 3
    resolution_detail: ResolutionDetail | None
    terrain_required: list[str]          # Pass-through for Layer 4 cross-ref with 2B
    contraindicated_parts: list[str]     # Pass-through for 2D
    contraindicated_conditions: list[str]  # Pass-through for 2D

@dataclass
class ResolutionDetail:
    # Set when tier == 2
    substitute_text: str | None = None
    substitute_equipment: list[str] | None = None  # The matching AND-group
    is_improvised: bool | None = None
    # Set when tier == 3
    proxy_exercise_id: str | None = None
    proxy_exercise_name: str | None = None
    # tier 1: resolution_detail is None (no substitution needed)
    # tier 0: resolution_detail is None (nothing resolved)

@dataclass
class CoachingFlag:
    flag_type: str                       # 'low_coverage' | 'critical_dropped' | 'toggle_off_for_discipline'
    discipline_id: str | None
    discipline_name: str | None
    affected_exercise_ids: list[str]
    message: str                         # Human-readable for Layer 4 to surface
    metadata: dict                       # flag-specific structured data
```

## 8. Coaching flag rules

Three triggers, all surfaced in the same `coaching_flags[]` list. Layer 4 decides display priority and copy.

### 8.1 Low coverage

Trigger: `coverage_pct < 0.50` for any included discipline.

```python
CoachingFlag(
    flag_type='low_coverage',
    discipline_id=cov.discipline_id,
    discipline_name=cov.discipline_name,
    affected_exercise_ids=[ex.exercise_id for ex in unavailable_for_this_discipline],
    message=f"Only {cov.coverage_pct:.0%} of {cov.discipline_name} exercises are available at this locale.",
    metadata={'coverage_pct': cov.coverage_pct, 'tier_1': cov.tier_1_count, 'tier_2': cov.tier_2_count, 'tier_3': cov.tier_3_count, 'unavailable': cov.unavailable_count}
)
```

Threshold rationale: <50% means more than half the relevant exercises are unavailable. Athlete should know before plan-gen starts so they can decide to skip this locale for that discipline or accept reduced variety.

### 8.2 Critical priority dropped

Trigger: any exercise with `priority = 'Critical'` in `sport_exercise_map` resolves to tier 0 (unavailable).

```python
CoachingFlag(
    flag_type='critical_dropped',
    discipline_id=ex.discipline_ids[0],  # primary discipline if multiple
    discipline_name=...,
    affected_exercise_ids=[ex.exercise_id],
    message=f"Critical exercise '{ex.exercise_name}' for {ex.discipline_name} cannot be performed at this locale.",
    metadata={'exercise_type': ex.exercise_type, 'discipline_ids': ex.discipline_ids}
)
```

One flag per critical-dropped exercise. May fire multiple times.

### 8.3 Toggle OFF for included discipline

Trigger: discipline in `included_discipline_ids` is gated by a sport-specific toggle, and that toggle is OFF in `cluster_gear_toggle_states`.

Requires a mapping of discipline → gating toggle. This mapping isn't currently in any Layer 0 table — it lives in the Vocab Audit and the toggle docstrings. **[DECISION POINT — discipline-to-toggle mapping]**: either (a) hard-code in 2C code (`{'D-010': 'Climbing — roped', 'D-015': 'Snowshoeing', ...}`), or (b) add a column on `sport_specific_gear_toggles` (`gated_discipline_ids TEXT[]`) and load from there. Recommend (b) for traceability; would add to FC-1 work.

For first implementation, use (a) hard-coded mapping. Add (b) during FC-1 spec v4 work.

```python
CoachingFlag(
    flag_type='toggle_off_for_discipline',
    discipline_id=d_id,
    discipline_name=d_name,
    affected_exercise_ids=[],  # All exercises for this discipline are effectively unavailable
    message=f"You included {d_name} but '{toggle_name}' is off. No gear means no equipment-based exercises for this discipline.",
    metadata={'toggle_name': toggle_name}
)
```

This flag fires BEFORE 5.2 query — if a toggle-gated discipline has its toggle OFF, 2C still runs the full resolution but all exercise-rows for that discipline will hit Tier 0 unless they're pure-bodyweight. The flag tells Layer 4 why coverage will be low.

## 9. Caching & determinism

Per spec v3 §5.1 Decision 3: 2C is deterministic and cache-friendly. Cache not built at launch but the interface is designed for it.

**Cache key:**

```
(athlete_id, locale_id, sha256(etl_version_set), sha256(sorted(cluster_gear_toggle_states.items())))
```

`athlete_id` is required because `locale_equipment_pool` and `cluster_gear_toggle_states` are athlete-specific.

**Invalidation triggers:**

- Athlete's locale equipment changes → invalidate all `(athlete_id, locale_id, *, *)` entries for that locale
- Athlete's cluster gear toggles change → invalidate all `(athlete_id, *, *, *)` entries for that athlete
- New ETL run → invalidate all entries with the old `etl_version_set` hash

No time-based expiration. Sticky until invalidated.

**Latency target:** <2s for a single 2C call. With ~211 exercises in the v19 pool and indexed queries, well within budget.

## 10. Edge cases

| Case | Behavior |
|---|---|
| Empty `locale_equipment_pool` | Effective pool starts empty (no universals — see note below). Tier 1 only resolves for bodyweight exercises (`equipment_required = []`). Tier 2 still resolves any `is_improvised: true` sub. Most exercises will hit Tier 0; expect low_coverage flags everywhere. |
| Discipline in `included_discipline_ids` has zero exercises after bridge resolution | `DisciplineCoverage.total_exercises = 0`, `coverage_pct = 0.0`. Generates a low_coverage flag (special case: divide-by-zero handled by setting coverage_pct=0.0). |
| All `cluster_gear_toggle_states` keys OFF | Effective pool = `locale_equipment_pool` only. Toggle-gated disciplines surface `toggle_off_for_discipline` flags. |
| Exercise has both legacy `equipment_substitutes` (JSONB) and new `equipment_substitutes_structured` | Use `equipment_substitutes_structured` exclusively. Legacy field is reference data only per Batch C decision. |
| Exercise with NULL `equipment_substitutes_structured` | Tier 2 returns None. Skip to Tier 3. |
| Exercise with NULL `physical_proxies` | Tier 3 returns None. Exercise → Tier 0. |
| Proxy references an `exercise_id` not in the per-discipline query result | Skip that proxy. Log at DEBUG. Not an error — proxies can point to any exercise in the DB. |
| Exercise appears under multiple disciplines | Dedupe by `exercise_id`. `discipline_ids[]` lists all of them. Tier resolution happens once per exercise, not per discipline-pair. |
| `included_discipline_ids` contains a discipline with no row in `sport_discipline_bridge` for any ETL version in the set | Log ERROR. Skip the discipline. Do NOT fail the whole call — partial result is better than none for cluster planning. |
| `locale_id` not in `cluster_locale_ids` | Validation failure (precondition #4). |
| `etl_version_set` missing a required key | Validation failure. |
| Locale has equipment tokens not in `equipment_items` canonical vocab | Pass through silently — 2C trusts the input (UI-side validation). Unknown tokens just won't match any exercise's `equipment_required`. No harm. |

**Note on `is_universal=true` items:** these (Wall, Doorway, Floor, etc.) are NOT auto-added by 2C. Layer 1 §J onboarding pre-populates them into `locale_equipment_pool` for every locale. 2C is dumb about it — it just unions what it's given.

## 11. Performance budget

Per Batch A handoff: "<2s for a single cluster's 2C run + cache write."

For a single locale call:
- §5.2 query: 1 JOIN on indexed columns, ~211 rows max in v19. <100ms.
- Per-exercise tier resolution: pure Python set ops on small lists. <10ms total for ~211 rows.
- Aggregate + coaching flags: <10ms.
- Payload serialization: <50ms.

**Per-locale budget: ~200ms. Per-cluster budget (typical 1–3 locales): 200–600ms.** Headroom for 2s budget is comfortable.

If a cluster has many locales (e.g., athlete travels regularly to 5+ places), the cluster-level call parallelizes across locale calls. Each locale call is independent.

## 12. Open items / forward references

| # | Item | Owner | Status |
|---|---|---|---|
| 2C-1 | **Toggle definition lookup at runtime vs pre-resolved** (§5.1 decision point) | Andy | Awaiting decision |
| 2C-2 | **Discipline-to-toggle mapping location** (§8.3 decision point) | Andy / FC-1 | Hard-code for v1; add structured column in FC-1 |
| 2C-3 | Layer 4 selection logic — how plan-gen picks Tier 2 vs Tier 3 when both resolve | Layer 4 design | Out of scope here; surfaced in payload |
| 2C-4 | Foci selection (orthogonal to 2C) | Layer 4 design | Already tracked as Open Item P in Batch B handoff |
| 2C-5 | D-08 follow-up: Long Distance / Endurance Cycling missing 2 disciplines from `sport_discipline_map` — when those sports come online, verify 2C still works | FC-1 | Not AR-blocking |

## 13. Test scenarios

These aren't unit tests yet — they're the integration scenarios that 2C must handle correctly. Spec'd here so when tests are written, the coverage is clear.

### 13.1 Andy at home — full AR cluster

Inputs:
- `locale_id` = "home"
- `locale_equipment_pool` = athlete's home gym (TBD from Layer 1 data)
- `cluster_gear_toggle_states` = AR cluster toggles
- `included_discipline_ids` = all 15 AR disciplines from Check A verification

Expected:
- Coverage >70% on running, MTB, hiking, strength
- Coverage <50% on rope-based disciplines if climbing toggle OFF → `toggle_off_for_discipline` flag
- Coverage <50% on snowshoeing if no snowshoe equipment → low_coverage flag
- Bike workouts (EX073/074/075/185/186/197) resolve via Tier 1 on Road bike if present, Tier 2 to MTB/Gravel/Trainer otherwise

### 13.2 Andy at hotel — limited gym

Inputs:
- `locale_id` = "hotel"
- `locale_equipment_pool` = typical hotel gym (treadmill, dumbbells, bench, often a Smith machine)
- Same cluster toggles + disciplines as 13.1

Expected:
- Coverage <50% on all bike disciplines → low_coverage flag for D-005 and D-006 (no bike at hotel)
- EX229 Bench Press resolves via Tier 1 (Barbell+Bench+Squat rack at the hotel from Andy's Nashville note) or Tier 2 to DB Bench Press
- Bodyweight + DB exercises resolve cleanly Tier 1

### 13.3 Empty pool — extreme degenerate

Inputs:
- `locale_equipment_pool` = []
- All toggles OFF
- 1 discipline included

Expected:
- Only bodyweight exercises resolve Tier 1
- Improvised substitutes (backpack/jugs/stairs) resolve Tier 2
- Most exercises hit Tier 0
- low_coverage flag fires
- No call failure — graceful degradation

### 13.4 Multi-discipline exercise dedup

A core/strength exercise mapped to both Trail Running and Hiking under AR.

Expected:
- Single ResolvedExercise entry
- `discipline_ids = [D-001, D-003]`
- Tier resolved once
- Counts toward both disciplines in `DisciplineCoverage`

## 14. Gut check

**What this spec gets right:**
- Algorithm is fully specified — no ambiguity on tier cascade
- Edge cases enumerated rather than waved at
- Performance budget is concrete and headroom-positive
- Distinction between "what 2C does" and "what comes downstream" is clean

**Risks:**
- The two `[DECISION POINT]` markers (toggle runtime lookup, discipline-toggle mapping) are real choices that affect implementation. If you pick the runtime-lookup options for both, 2C is a clean read-only query node consuming `exercises`, `sport_exercise_map`, `sport_discipline_bridge`, and (light) `sport_specific_gear_toggles`. If you pick pre-resolution, Layer 1 spec needs additions.
- Discipline-to-toggle mapping (§8.3) being hard-coded for v1 is a small tech debt. Acceptable but tracked in 2C-2.
- I'm trusting that proxies are stored as `[{"exercise_id": "...", "exercise_name": "..."}, ...]` per spec — if deployed shape is different, §5.5 query reading is off. Worth a quick spot-check on a couple rows when implementing.

**What might be missing:**
- 2C doesn't filter by `contraindicated_parts` / `contraindicated_conditions`. Those go to 2D. But should 2C surface them in the payload alongside each exercise? I've done so (§7 ResolvedExercise) — pass-through. If you want them excluded, easy change.
- No explicit "exercise type distribution" reporting. Layer 4 might want to know "you have 50% strength coverage but 20% endurance coverage." Currently the payload makes this derivable but doesn't surface it directly. Tradeoff: more output ≠ better. Leave it derivable.
- I haven't specified how `terrain_required` interacts with Layer 4 yet — 2C passes it through, 2B owns terrain. The hand-off is clean but Layer 4's spec needs to document the cross-reference rule. Tracked as 2C-3.

**Best argument against this spec as drafted:** It's verbose. Maybe too verbose for what's ultimately a 150-line Python function. Counter: the spec exists to lock decisions before code, and the edge cases section in particular pays for itself when implementation hits weird inputs. Worth the length.
