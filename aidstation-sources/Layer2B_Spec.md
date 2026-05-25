# Layer 2B — Terrain Classifier (Query Node)

**Status:** Consolidated spec, backfilled 2026-05-10 from design notes in `Layer1_2B_Done_2C_Kickoff_Handoff.md` §"Node 2B — Terrain Classifier — LOCKED".
**Type:** Query node. Pure read, deterministic given inputs, no LLM involvement.
**Predecessor decisions:** All design calls from the 2B locking session are folded in.

---

## 1. Purpose

Given the terrain types the athlete's target race involves and the terrain types accessible from each of their training locales, compute the **terrain gap** — which terrain types from the race cannot be trained on locally, and what the best proxy is for each. Surface gap severity, adaptation timeline, proxy fidelity, and unbridgeable warnings so Layer 4 can build a plan that prepares the athlete as well as possible given their geographic reality.

For AR specifically: if the race has technical trail + mountain alpine terrain and the athlete trains in flat plains, 2B identifies which gaps exist, what their best proxy is (Hill / Rolling at fidelity 0.6, say), and whether any gaps are unbridgeable (e.g., alpine descent skill cannot be developed off-snow).

## 2. What 2B does NOT do

Clarifying boundaries:

- **Does not enumerate exercises.** That's 2C. 2B doesn't touch `exercises`.
- **Does not select disciplines.** That's 2A. 2B accepts 2A's discipline list as input for scoping.
- **Does not resolve equipment.** That's 2C.
- **Does not assess injury / health risk.** That's 2D. (Though Layer 4 may cross-reference 2B output with 2D output for terrain-injury combinations.)
- **Does not gate plan generation.** Terrain gaps surface as `coaching_flags` and `adaptation_weeks_needed` summaries, not HITL blockers. (Exception: a terrain gap that makes the entire race unsafe would surface as `summary.any_unbridgeable=True` and let plan-gen decide whether to gate — 2B itself doesn't gate.)
- **Does not handle terrain weather variations.** 2B is about terrain TYPE access (trail, mountain, water, etc.), not conditions. Weather is its own concern (Layer 5 advisor).

## 3. Function signature

```python
def q_layer2b_terrain_classifier_payload(
    race_terrain: list[RaceTerrainEntry],
    locale_terrain_ids: list[str],
    included_discipline_ids: list[str],
    etl_version_set: dict[str, str]
) -> Layer2BPayload:
    ...

@dataclass
class RaceTerrainEntry:
    terrain_id: str       # Canonical TRN-xxx ID
    pct_of_race: float    # 0.0 – 100.0; estimated percentage of race time on this terrain
    discipline_id: str | None = None  # Captured 2026-05-24 (Bucket E); CONSUMED 2026-05-25 (re-model Slice 4). None = race-wide.
```

**Discipline tagging (re-model Slice 4, 2026-05-25).** `discipline_id` is
**optional** — `None` means race-wide (the terrain row counts against every
included discipline). It is *not* required per row: a single-discipline race's
"race-wide" terrain is exactly that one discipline's terrain, so a global
requirement would be wrong, and existing captured rows are all `None`. Layer 2B
keys an additive per-discipline view off this tag (§5.6 + §7 `terrain_by_discipline`);
the flat top-level `race_terrain`/`terrain_gaps`/`summary` are unchanged.

### Parameters

| Param | Type | Source | Notes |
|---|---|---|---|
| `race_terrain` | list[RaceTerrainEntry] | `§H.2 Race Terrain Type` | Each terrain in the race + its estimated percentage. Must use canonical TRN-xxx IDs (Open Item E from 2B locking — `§H.2` field must be a controlled vocabulary at onboarding time). |
| `locale_terrain_ids` | list[str] | `§J Locale terrain access` (unioned across athlete's cluster) | Canonical TRN-xxx IDs. Unioned because locales in a cluster are reachable; if athlete has access to mountain terrain from any locale in their cluster, they have access to it for training. |
| `included_discipline_ids` | list[str] | 2A output | Used for scoping gap relevance — e.g., a swim-terrain gap is irrelevant if the athlete isn't training swim disciplines. |
| `etl_version_set` | dict[str, str] | Plan-gen pin | Locks Layer 0 version. |

### Return type

See §7 below.

## 4. Input validation (preconditions)

1. `race_terrain` is a list (may be empty — empty surfaces as a
   `race_terrain_unset` coaching flag per §8.4 rather than failing).
   Amended 2026-05-20 (Phase 5.1 form-refresh C) to loosen from the
   prior "non-empty list" requirement: the §H.2 capture surface is now
   optional + skippable; athletes who haven't captured terrain still get
   a working orchestrator end-to-end with the missing input surfaced as
   a data-gap flag.
2. Each entry's `terrain_id` matches the pattern `TRN-\d{3}`. (Checked
   only when `race_terrain` is non-empty.)
3. Each entry's `pct_of_race` is in [0.0, 100.0]. (Non-empty only.)
4. Sum of `pct_of_race` across entries is in [80.0, 120.0] (lenient — race breakdowns are estimates, perfect 100% is unrealistic). (Non-empty only.)
5. `locale_terrain_ids` is a list (may be empty — extreme case is valid).
6. Each `locale_terrain_id` matches `TRN-\d{3}` pattern.
7. `included_discipline_ids` non-empty.
8. `etl_version_set` contains `0C` at minimum.

Validation failure → raise `Layer2BInputError`.

## 5. Algorithm

### 5.1 Gap identification (set difference)

```python
race_terrain_id_set = {t.terrain_id for t in race_terrain}
locale_terrain_id_set = set(locale_terrain_ids)

gap_terrain_ids = race_terrain_id_set - locale_terrain_id_set
covered_terrain_ids = race_terrain_id_set & locale_terrain_id_set
```

Pure set ops. Terrain in race that's not in locale → gap. Terrain in race that IS in locale → covered (no further action needed, just report).

### 5.2 Proxy resolution per gap

For each `gap_terrain_id`, look up gap rules and find best proxy:

```sql
SELECT
  gap.target_terrain_id,
  gap.target_terrain_name,
  gap.proxy_terrain_id,
  gap.proxy_terrain_name,
  gap.gap_severity,
  gap.adaptation_weeks_low,
  gap.adaptation_weeks_high,
  gap.proxy_fidelity,
  gap.proxy_methods,
  gap.uncoverable_stimulus,
  gap.prescription_note
FROM layer0.terrain_gap_rules gap
WHERE gap.target_terrain_id = %(gap_id)s
  AND gap.etl_version = %(version_0c)s
  AND gap.superseded_at IS NULL
  AND (
    gap.proxy_terrain_id IS NULL                      -- unbridgeable case
    OR gap.proxy_terrain_id = ANY(%(locale_ids)s)     -- proxy must be in athlete's locale set
  )
ORDER BY
  gap.proxy_fidelity DESC NULLS LAST,                 -- best proxy first
  gap.gap_severity                                    -- ties broken by less severe
LIMIT 1;
```

**Resolution logic:**

- If a row returns with `proxy_terrain_id` matching one of athlete's locale terrain IDs → that's the best proxy. Use its fidelity, adaptation weeks, methods, note.
- If only rows with `proxy_terrain_id = NULL` exist (unbridgeable) → the gap is officially unbridgeable. Use those values.
- If NO rows return from the query (target_terrain_id has no gap rule entries at all) → the gap is "undefined" — neither bridgeable nor unbridgeable per data model. Treat as warning case: log it, return a partial gap entry with `gap_severity='undefined'`, `proxy_fidelity=None`, recommend plan-gen surface as data-gap warning.

### 5.3 Discipline relevance scoping

Each gap is scoped to the included disciplines for which it's relevant. A water-terrain gap (Flat Water → Pool) is only relevant if athlete includes paddling disciplines.

The terrain → discipline relevance map currently lives in the `proxy_methods` and `prescription_note` fields (free text) of `terrain_gap_rules`. For v1, parse those fields for discipline references. **Open candidate:** add a `relevant_discipline_ids TEXT[]` column to `terrain_gap_rules` for structured relevance. Tracked as 2B-1 below.

For v1, the relevance check is loose: a gap is reported regardless, and Layer 4 decides whether to surface it based on discipline overlap. The flag `discipline_relevance_assessed=False` indicates this.

### 5.4 Race-terrain pass-through with coverage flags

For each entry in `race_terrain`, build the output entry:

```python
for rt in race_terrain:
    covered = rt.terrain_id in locale_terrain_id_set
    out.race_terrain.append(RaceTerrainOutput(
        terrain_id=rt.terrain_id,
        terrain_name=lookup_name(rt.terrain_id, etl_version_set['0C']),
        pct_of_race=rt.pct_of_race,
        available_locally=covered,
        gap=gap_records.get(rt.terrain_id)  # gap data if not covered
    ))
```

`terrain_name` lookup is a small JOIN to `terrain_types.canonical_name` keyed by `terrain_id`.

### 5.5 Summary aggregation

```python
gaps_only = [g for g in gap_records.values() if g.proxy_terrain_id is not None or g.gap_severity == 'unbridgeable']

summary = SummaryBlock(
    total_race_terrain_count=len(race_terrain),
    covered_count=len(covered_terrain_ids),
    gap_count=len(gap_terrain_ids),
    bridgeable_count=sum(1 for g in gaps_only if g.proxy_terrain_id is not None),
    unbridgeable_count=sum(1 for g in gaps_only if g.proxy_terrain_id is None),
    min_adaptation_weeks_needed=max([g.adaptation_weeks_high for g in gaps_only if g.adaptation_weeks_high] or [0]),
    worst_fidelity=min([g.proxy_fidelity for g in gaps_only if g.proxy_fidelity is not None] or [1.0]),
    pct_of_race_uncovered=sum(rt.pct_of_race for rt in race_terrain if rt.terrain_id in gap_terrain_ids)
)
```

`min_adaptation_weeks_needed` uses MAX of adaptation_weeks_high across gaps — because the athlete needs enough time to adapt to the worst-case gap. Plan-gen uses this against training window for timeline viability and feeds it into 2E for nutrition periodization.

### 5.6 Per-discipline grouping (re-model Slice 4, 2026-05-25)

Additive to §5.4/§5.5: after the flat aggregate is built, emit one
`Layer2BDisciplineBlock` per `included_discipline_id`. A discipline's terrain
subset = entries tagged with that `discipline_id` PLUS race-wide (`None`)
entries folded in; a tagged entry wins over a race-wide entry for the same
`terrain_id`. Coverage / gaps / summary are recomputed over the subset via the
same §5.4/§5.5 logic. **No extra SQL:** proxy resolution (§5.2) is keyed by
`(terrain_id, locale set)` and is discipline-independent, so the per-block gaps
are sliced from the already-computed gap records. Block rows stamp the block's
`discipline_id` (folded-in race-wide rows are attributed to the discipline);
the flat top-level `race_terrain` preserves the captured tag verbatim.

```python
for did in included_discipline_ids:
    subset = dedup_by_terrain(tagged_to(did) + race_wide_entries)  # tagged wins
    if not subset:
        continue                                                   # no block
    block = Layer2BDisciplineBlock(
        discipline_id=did,
        race_terrain=[RaceTerrainOutput(..., discipline_id=did) for e in subset],
        terrain_gaps=[gap_records[t] for t in subset_gap_ids],
        summary=build_summary(subset, ...),
    )
```

A discipline with no tagged rows AND no race-wide rows emits no block. Entries
tagged to a discipline outside `included_discipline_ids` are excluded from the
blocks but remain in the flat aggregate. This is the first slice to *consume*
`discipline_id`; the per-discipline resolver + Layer-4 craft reasoning that
read these blocks are re-model Slice 5 (see `BestFitModality_Spec_v4.md` §12).

## 6. Drift items affecting 2B

| ID | Description | Status |
|---|---|---|
| D-10 | `terrain_types` has 7 deployed columns not in spec v3. Spec says 2 cols; deployed has 9. Schema is hand-curated post-spec. | Spec rewrite; non-blocking |
| D-11 | `terrain_gap_rules` not in spec v3 §4 at all. Schema lives only in populate script. | Spec rewrite; non-blocking |
| D-08, D-05, D-17 | None affect 2B. 2B doesn't touch SDM, PLA, or sport-level naming. | Not relevant to 2B |

## 7. Payload schema

```python
@dataclass
class Layer2BPayload:
    race_terrain: list[RaceTerrainOutput]
    terrain_gaps: list[TerrainGap]
    coaching_flags: list[CoachingFlag]
    summary: SummaryBlock
    etl_version_set: dict[str, str]
    terrain_by_discipline: list[Layer2BDisciplineBlock] = []  # re-model Slice 4 (2026-05-25); additive, [] for empty race_terrain

@dataclass
class Layer2BDisciplineBlock:                # re-model Slice 4 (2026-05-25) — per §5.6
    discipline_id: str
    race_terrain: list[RaceTerrainOutput]    # subset rows, stamped with discipline_id
    terrain_gaps: list[TerrainGap]           # sliced from the flat gap records
    summary: SummaryBlock                    # recomputed over the subset

@dataclass
class RaceTerrainOutput:
    terrain_id: str
    terrain_name: str
    pct_of_race: float
    available_locally: bool
    gap: TerrainGap | None              # Populated if not available locally
    discipline_id: str | None = None    # re-model Slice 4; pass-through on flat list (None=race-wide), block discipline on blocks

@dataclass
class TerrainGap:
    target_terrain_id: str
    target_terrain_name: str
    proxy_terrain_id: str | None        # None = unbridgeable
    proxy_terrain_name: str | None
    gap_severity: str                   # From terrain_gap_rules; e.g., 'critical' | 'high' | 'medium' | 'low' | 'unbridgeable' | 'undefined'
    adaptation_weeks_low: int | None
    adaptation_weeks_high: int | None
    proxy_fidelity: float | None        # 0.0–1.0; NULL if unbridgeable or undefined
    proxy_methods: list[str]            # Free-text methods array from gap rule
    uncoverable_stimulus: list[str]     # What the proxy can't replicate
    prescription_note: str              # Plan-gen consumes for athlete-facing copy
    discipline_relevance_assessed: bool # False for v1; True when 2B-1 lands

@dataclass
class SummaryBlock:
    total_race_terrain_count: int
    covered_count: int
    gap_count: int
    bridgeable_count: int
    unbridgeable_count: int
    min_adaptation_weeks_needed: int
    worst_fidelity: float               # 0.0–1.0; 1.0 = no gaps
    pct_of_race_uncovered: float
    any_unbridgeable: bool              # Derived: unbridgeable_count > 0
    any_undefined: bool                 # Derived: any gap with severity='undefined'

@dataclass
class CoachingFlag:
    flag_type: str                      # see §8
    target_terrain_id: str | None
    message: str
    metadata: dict
```

## 8. Coaching flag rules

Three triggers in 2B:

### 8.1 Unbridgeable gap

Trigger: any gap with `proxy_terrain_id IS NULL` (e.g., Alpine Descent off-snow per terrain_gap_rules data).

```python
CoachingFlag(
    flag_type='unbridgeable_terrain',
    target_terrain_id=gap.target_terrain_id,
    message=f"{gap.target_terrain_name} cannot be replicated with your current locale terrain. {gap.prescription_note}",
    metadata={
        'pct_of_race': pct_of_race,
        'uncoverable_stimulus': gap.uncoverable_stimulus
    }
)
```

This flag fires per unbridgeable gap. Plan-gen surfaces it prominently to athlete.

### 8.2 High-fidelity gap requires coached introduction

Trigger: gap with `proxy_fidelity >= 0.5` but `prescription_note` mentions coached intro (currently: whitewater).

```python
CoachingFlag(
    flag_type='requires_coached_introduction',
    target_terrain_id=gap.target_terrain_id,
    message=gap.prescription_note,
    metadata={'fidelity': gap.proxy_fidelity, 'adaptation_weeks_high': gap.adaptation_weeks_high}
)
```

Note: this is the example from the 2B locking handoff — "Whitewater gap (and any other 'requires coached introduction' case) surfaces as a coaching_flag in the plan output — a note or warning the athlete sees in their plan. It is NOT a HITL gate."

### 8.3 Undefined gap (data hole)

Trigger: race has a terrain_id with no `terrain_gap_rules` row at all.

```python
CoachingFlag(
    flag_type='undefined_gap',
    target_terrain_id=terrain_id,
    message=f"Terrain '{terrain_name}' has no gap rule data — plan-gen will treat as unbridgeable by default.",
    metadata={'severity_assumed': 'unbridgeable'}
)
```

Surfaces as warning for spec maintainers — indicates terrain_gap_rules needs a new row.

### 8.4 Race terrain unset (data gap)

Added 2026-05-20 (Phase 5.1 form-refresh C — paired with the §4 condition 1
loosen).

Trigger: `race_terrain` is empty (athlete hasn't completed §H.2 capture).
The payload returns with empty `race_terrain` + empty `terrain_gaps` and
this single flag — Layer 4 / plan-gen consumes the flag as a data-gap
warning rather than failing on the empty input.

```python
CoachingFlag(
    flag_type='race_terrain_unset',
    target_terrain_id=None,
    message=(
        "Race terrain breakdown not captured — terrain gap analysis "
        "skipped. Capture race terrain in onboarding §H.2 or the "
        "race-event edit form."
    ),
    metadata={},
)
```

When this flag fires, the other §8 triggers (§8.1 / §8.2 / §8.3) cannot
fire — no race terrain → no gaps → no proxy resolutions. The flag is
mutually exclusive with the gap-driven flags.

## 9. Caching & determinism

**Cache key:**
```
(athlete_id, hash(race_terrain), hash(sorted(locale_terrain_ids)), hash(sorted(included_discipline_ids)), hash(etl_version_set))
```

**Invalidation triggers:**
- `§H.2 Race Terrain Type` changes (any terrain or pct_of_race change — includes the per-row `discipline_id` tag, re-model Slice 4)
- `§J Locale terrain access` changes (any locale in cluster adds/removes terrain)
- ETL version set changes
- `included_discipline_ids` from 2A changes (affects relevance scoping AND the per-discipline block set, re-model Slice 4)

**Re-model Slice 4 note (2026-05-25):** adding `terrain_by_discipline` (and
`RaceTerrainOutput.discipline_id`) is an *additive* payload-shape change. The
default `[]` keeps old cached payloads deserializable; the one-time payload-hash
change naturally invalidates downstream Layer 3B/4 cone entries on first deploy
(anticipated by `BestFitModality_Spec_v4.md` §9). No new eviction helper — the
per-discipline grouping derives from inputs already covered by the triggers
above.

**Does NOT re-run when:**
- Equipment changes (§J equipment) — that's 2C
- Fitness baselines change
- Injury records change
- Schedule changes

**Latency target:** <100ms per call. Set operations + a single small query.

## 10. Edge cases

| Case | Behavior |
|---|---|
| All race terrain available locally | `gap_count=0`, `worst_fidelity=1.0`, no gaps in payload, `any_unbridgeable=False`. Empty `coaching_flags[]`. |
| All race terrain UN-available | Many gaps. Athlete-side reality check needed; plan-gen decides. 2B reports honestly. |
| Empty `race_terrain` (added 2026-05-20, Phase 5.1 form-refresh C) | Payload returns empty `race_terrain[]` + empty `terrain_gaps[]` + summary with all zero counts + `worst_fidelity=1.0` + `pct_of_race_uncovered=0.0` + a single `race_terrain_unset` coaching flag per §8.4. Validation accepts (loosened from §4 condition 1's prior "non-empty list" requirement); discipline + ETL checks still fire. |
| Empty `locale_terrain_ids` | Everything in race terrain is a gap. Same as above, more aggressive. |
| Race-terrain pct sums to 95% (slight under) | Validated as in [80, 120]. Pass through. |
| Race-terrain pct sums to 60% (well under) | Validation failure. |
| Race terrain entry with `pct_of_race=0.0` | Allowed — caller's choice. Treated normally; appears in output with `pct_of_race=0.0`. Not filtered out. |
| Terrain ID in race that doesn't exist in `terrain_types` | `terrain_name` lookup returns None. Surface in output with `terrain_name=None` and `coaching_flag` of type `undefined_gap`. Don't crash. |
| Multiple gap rules for same target_terrain_id with different proxies | §5.2 ORDER BY picks best (highest fidelity); other rows ignored for this call. |
| Gap rule with `proxy_terrain_id` that's NOT in any active `terrain_types` row | Log ERROR (data integrity); skip that rule. |
| `adaptation_weeks_high` is NULL for an unbridgeable gap | Summary `min_adaptation_weeks_needed` ignores NULLs in the MAX. |
| Race terrain doesn't include any water but athlete includes D-007 Packrafting | Discipline-relevance check might fire as warning. Currently v1 spec is permissive — gap is reported anyway, relevance flagged false. |
| All terrain race-wide (`discipline_id=None`), N included disciplines (re-model Slice 4) | Each discipline block folds in the full race-wide terrain set; flat aggregate stays deduped (no double-count). The common case for existing captured rows. |
| Same `terrain_id` tagged to two disciplines at different `pct_of_race` (re-model Slice 4) | Each block keeps its own pct (the flat `pct_by_target` collapse no longer loses the per-leg value). Flat `total_race_terrain_count` still counts both rows; `covered_count` counts the unique terrain id. |
| Discipline in `included_discipline_ids` with no tagged + no race-wide rows (re-model Slice 4) | No block emitted for it (Slice 5 treats as craft-only / no terrain emphasis). |
| Entry tagged to a discipline NOT in `included_discipline_ids` (re-model Slice 4) | Excluded from `terrain_by_discipline`; still present in the flat aggregate. Forms source the tag `<select>` from the included set, so this is a defensive case. |

## 11. Performance budget

- Set differences: <1ms
- Per-gap proxy lookup: ~5ms × N gaps (typically 1–5 gaps) = <25ms
- Terrain name lookup (single query for all race terrain): <20ms
- Summary computation: <5ms
- Serialization: <20ms

**Total: ~75ms typical, <100ms even with many gaps.** Easily within budget.

## 12. Open items / forward references

| # | Item | Owner | Status |
|---|---|---|---|
| 2B-1 | Add `relevant_discipline_ids TEXT[]` column to `terrain_gap_rules` for structured discipline-relevance | FC-1 | Not blocking; current relevance check is loose |
| 2B-2 | `§J Locale terrain access` field must use TRN-xxx IDs as controlled vocabulary | Layer 1 onboarding spec | Open Item A from 2B locking; ✅ **Resolved 2026-05-20** (Phase 5.1 form-refresh C). `locale_profiles.locale_terrain_ids TEXT[] NOT NULL DEFAULT '{}'` migrated via `init_db.py` `_PG_MIGRATIONS`; `routes/locales.py` exposes a multi-checkbox widget keyed on canonical TRN-xxx (`_terrain_choices(db)` + `_parse_locale_terrain(form)` + `_hydrate_locale_terrain_ids(row)` + `_evict_layer2b_on_terrain_change(db, uid)`); `templates/locales/form.html` renders the checkbox grid on both legacy + shared-locale edit branches; orchestrator's `_q_locale_terrain_ids(db, uid, primary_locale)` reads the home-locale row and threads into `q_layer2b_terrain_classifier_payload`. Multi-locale cluster union (§3 spec text) remains v1 future work — home-only matches the existing `_q_locale_equipment_pool` pattern. Paired loosen on `_validate_inputs` empty-race_terrain landed in the same slice. |
| 2B-3 | `§H.2 Race Terrain Type` field must use TRN-xxx IDs as controlled vocabulary | Layer 1 onboarding spec | Open Item E from 2B locking; ✅ **Resolved 2026-05-20** (Phase 5.1 form-refresh A + B). Form-refresh A 2026-05-20 captured terrain on the race-event edit path; Form-refresh B 2026-05-20 closed the §H.2 onboarding step-3c surface (`routes/onboarding.py:target_race_save()` threads `race_terrain` + `aid_stations` through to `create_race_event` / `update_race_event`; `templates/onboarding/target_race.html` renders the same TRN-xxx + percentage editor as the post-onboarding edit surface via the shared `templates/_race_terrain_editor.html` partial). Layer 2B `_validate_inputs` still rejects empty race_terrain loudly (separate loosen-for-empty follow-on; paired with form-refresh C). |
| 2B-4 | Plan confirmation UI step — surface terrain gaps to athlete before Layer 4 runs | Product design | Open Item C from 2B locking |

## 13. Test scenarios

### 13.1 AR PGE 2026 — Minnesota terrain

PGE happens in Minnesota (Nerstrand, MN). Likely race terrain:
- Groomed Trail (TRN-002): 35%
- Technical Trail (TRN-003): 30%
- Hill / Rolling (TRN-004): 15%
- Flat Water (TRN-009): 15%
- Indoor / Gym (TRN-016 — rappel anchor location): 5%

Andy's locale terrain (estimated):
- Dallas-area trails: Groomed Trail (TRN-002), Hill / Rolling (TRN-004)
- Partner's home area: Groomed Trail, Technical Trail (TRN-003), Hill / Rolling, Mountain / Alpine (TRN-005)
- Various: Indoor / Gym (TRN-016)

Expected:
- Covered: TRN-002, TRN-003, TRN-004, TRN-016 ✓
- Gap: TRN-009 Flat Water (15% of race)
- TRN-009 gap → look up rule → proxy=Pool (TRN-008)? If Pool not in locale either, gap stays open. Likely Pool IS available somewhere → proxy resolves at high fidelity.
- `summary.gap_count = 1`, `bridgeable_count = 1`, `unbridgeable_count = 0`, `pct_of_race_uncovered = 15.0`
- `coaching_flags = []` (no unbridgeable, no coached-intro)

### 13.2 Alpine race — unbridgeable case

Race terrain includes Snow / Winter Alpine (TRN-014) with 30%. Athlete's locale has no snow terrain.

Expected:
- Gap on TRN-014
- Proxy = Indoor / Gym at partial severity per `populate_terrain_gap_rules.sql` (descent flagged unbridgeable)
- `coaching_flags` includes `unbridgeable_terrain` for descent stimulus
- `summary.any_unbridgeable = True`
- Layer 4 surfaces "alpine descent skill cannot be developed off-snow" warning

### 13.3 Empty locale — extreme degenerate

`locale_terrain_ids = []`. Race has 4 terrain types.

Expected:
- All 4 race terrains are gaps
- Each gets proxy resolution attempt; most will hit `undefined_gap` if their target_terrain_id has no rules with NULL proxy
- `summary.pct_of_race_uncovered = 100.0`
- Many coaching flags
- No crash

### 13.4 Race with controlled-vocab gap (Open Items 2B-2, 2B-3)

Race terrain field has a free-text entry that doesn't match any TRN-xxx ID.

Expected: validation failure per §4 precondition 2. This is the explicit failure mode for the controlled-vocabulary requirement — the spec doesn't try to fuzzy-match terrain names.

## 14. Gut check

**What this spec gets right:**
- Discipline relevance scoping is honestly flagged as v1-loose (`discipline_relevance_assessed=False`). Doesn't pretend to be more rigorous than it is.
- Undefined-gap case is handled gracefully — surfaces as warning rather than crashing.
- Adaptation-weeks aggregation uses MAX (worst-case for athlete planning) rather than SUM or MEAN — defensible choice for the use case.

**Risks:**
- Set-difference semantics on terrain assume each TRN-xxx is atomic. If terrain has hierarchy (e.g., Technical Trail is a kind of Trail), the set-difference may miss partial overlaps. Currently `terrain_types` doesn't model hierarchy; if it ever does, 2B logic needs an update.
- Multi-locale union for `locale_terrain_ids` is correct for a cluster where the athlete can drive between locales, but if an athlete has a remote locale they only visit a few times, treating that locale's terrain as always-available is wrong. Currently no remote-locale model exists — flagged for future locale-spec work.
- Proxy methods are free text. Layer 4 has to parse them. If the format isn't consistent across rules, that's a Layer 4 problem.

**What might be missing:**
- No "terrain seasonality" handling. Open water access in winter MN is zero even if a lake is in the locale set. Currently not modeled. Tradeoff: keep 2B simple, push seasonality to Layer 5 (clothing/conditions advisor). Worth a note when designing 2E and 5.
- The `proxy_fidelity` numbers are coarse (one per gap rule row, not per athlete-locale combination). If two locales both offer a proxy, fidelity might differ — currently we just take the first. Acceptable for v1.

**Best argument against:** the spec is more thorough than the deterministic algorithm warrants. The whole node is "set difference + table lookup + summary stats." Counter: the complexity isn't in the algorithm, it's in the failure modes (undefined gap, missing proxy, controlled-vocab violations). Spec earns its length in the edge cases section.
