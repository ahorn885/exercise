# Layer 3D — HITL Aggregation + Gate (query/orchestration, no LLM)

**Status:** v1, 2026-06-21. **Slices 1 + 2 implemented** in `layer3d/gate.py` (Slice 1 = aggregation + gate, PR #850 merged; Slice 2 = the two §5.2/§5.3 feasibility detectors). The revise-cascade + staleness re-fire (§11/§11.2) are Slice 3 (next); 3C cross-node conflict (§13) is a later slice. Scopes the 3D human-review gate that sits between Layer 3B and Layer 4: it collects the human-review items the upstream nodes already emit (and that are currently produced + silently discarded), runs two pre-synthesis feasibility detectors, and **gates Layer 4** — plan generation runs only when every item is resolved. Per `Control_Spec_v8.md` §2 (Layer 3 — 4 nodes) + §7 (HITL surface). The `.5` resolution gate collapses into this node per Control_Spec §2 (no standalone row).

**Scope cut for v1 (Andy 2026-06-21):** this spec covers aggregation of the **already-emitted** upstream items (2A `prompt_required` / `unresolved_flags`, 2D `hitl_items`, 2E `hitl_items` + `contraindication_hitl_items`, 3B `hitl_surface`) **plus** the two surviving Layer-4 feasibility findings (the injury-empties-the-pool blocker + the schedule-volume-under-target warning). **3C cross-node conflict detection is deferred** — the node isn't built; §13 names it as the next slice. The aggregator is written so 3C items drop in as one more source with no contract change.

---

## 1. Purpose

Three jobs, all deterministic (no LLM):

1. **Aggregate** every human-review item produced upstream into one typed list with a uniform shape (source, severity, athlete-facing message, resolution affordance), so the athlete sees one review surface instead of nothing.
2. **Detect** the two pre-synthesis plan-feasibility conditions that can only be computed once 3B's periodization shape exists (they need `phase_structure_from_3b()` × 2A bands × 2D exclusions × §K availability):
   - **injury-empties-the-pool** (blocker) — 2D exclusions leave a phase with no workable strength pool, or ban a discipline's only cardio modality.
   - **schedule-volume-under-target** (warning) — the athlete's available weekly hours fall below the phase's target band. The plan is **not** blocked; Layer 4's volume math already clamps to available capacity, and 3D just warns.
3. **Gate** Layer 4: compute a `gate_status` and refuse to advance to synthesis until every item resolves to `acknowledged` or `revised`.

**Why this exists / why now.** 2D, 2E, and 3B compute review items today and **nothing reads them** — they're attached to payloads and dropped on the floor. That's a live safety gap (e.g. a 2D `post_surgical_clearance` block never reaches the athlete). 3D is the consumer that finally surfaces them, and the home for the #214 injury blocker.

---

## 2. What Layer 3D does NOT do

- **No LLM call.** Pure aggregation + deterministic rules. If a decision needs reasoning it belongs upstream (3A/3B) or in Layer 4, not here.
- **Does not re-derive upstream judgments.** It does not re-evaluate viability (3B), re-score injury risk (2D), or re-classify disciplines (2A). It reads their emitted items verbatim and re-shapes them; the upstream node remains the authority for severity and message.
- **Does not rewrite the plan to dodge a finding.** The schedule-volume warning is the only "adjust + proceed" path, and even that adjustment (clamp-to-capacity) is Layer 4's existing volume math, not a 3D edit. 3D never silently rearranges the athlete's choices — surfacing the choice to the athlete is the entire point (per the §6.4 "athlete is making a real choice" calibration, Andy 2026-05-16).
- **Does not own the upstream re-run.** When an item is resolved by **revise**, the athlete edits a Layer 1 field and the existing partial-update invalidation cascade (`Control_Spec` §4) re-runs the affected layers. 3D re-aggregates against the fresh payloads; it does not itself decide which layers to re-run.
- **Not a Layer 4 validator.** Plan-quality issues found *during* synthesis (validator cap-hit, seam-unresolved, best-effort) remain Layer 4's `notable_observations` surface (`Layer4_Spec.md` §8/§5.5). 3D is strictly *pre*-synthesis.

---

## 3. Function signature

```python
def evaluate_layer3d_gate(
    *,
    user_id: int,
    plan_version_id: int,
    layer1_payload: dict[str, Any],        # §K availability + the revise-target fields
    layer2a_payload: Layer2APayload,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3b_payload: Layer3BPayload,
    plan_start_date: date,
    total_weeks: int | None,
    race_event_payload: RaceEventPayload | None = None,
    prior_resolutions: dict[str, GateResolution] | None = None,
) -> Layer3DGate: ...
```

- **Pure + deterministic** given inputs (no `NOW()`, no DB writes) per the Control_Spec §5/§6 query-node contract. The caller (orchestrator) persists the returned `Layer3DGate` and re-invokes on each resolution round.
- `prior_resolutions` carries the athlete's acknowledge/revise choices from earlier rounds (keyed by `GateItem.item_key`, the stable per-item identity from §6.4). On the first evaluation it is empty/None.
- 2B is intentionally absent — terrain gaps are coaching flags, never gates (Control_Spec §7). 3A is absent — it produces no gate items (its judgments feed 3B, which does).

---

## 4. Input validation (preconditions)

Fail-fast; raises `Layer3DGateError(code, detail)`:

- `missing_upstream_payload` — any required payload (2A/2C/2D/2E/3B) is None. The gate cannot aggregate a payload it doesn't have.
- `etl_version_set_mismatch` — the `etl_version_set` pins differ across the supplied payloads (same fail-fast as `Layer4_Spec.md` §4.1). The gate must evaluate a single coherent version set.
- `plan_version_id_unset` — `plan_version_id <= 0` (the caller must have allocated the row the gate state attaches to).

These mirror Layer 4's §4.2 preconditions so the gate fails the same way the synthesis step would on the same bad inputs, one step earlier and cheaper.

---

## 5. Algorithm

```
evaluate_layer3d_gate(...):
  1. Validate preconditions (§4).
  2. items = []
  3. # --- Aggregation: read each source's emitted items verbatim ---
     items += map_2a_items(layer2a_payload)      # prompt_required disciplines + unresolved_flags(error|warning)
     items += map_2d_items(layer2d_payload)       # hitl_items: severity 'block'->blocker, 'warn'->warning
     items += map_2e_items(layer2e_payload)       # hitl_items + supplement_integration.contraindication_hitl_items
     items += map_3b_items(layer3b_payload)       # hitl_surface: 'blocker'->blocker, 'warning'/'informational' kept
     items += map_3c_items(layer2a, layer2c_payloads, layer2d)  # §5.4 CN-1/CN-2 cross-locale/cross-source conflicts
  4. # --- Feasibility detectors (need the phase structure) ---
     phase_structure = phase_structure_from_3b(layer3b_payload, plan_start_date, total_weeks)
     items += detect_injury_pool_empty(phase_structure, layer2a, layer2c_payloads, layer2d)   # blocker(s)
     item  = detect_schedule_volume_under_target(phase_structure, layer2a, layer1_payload)     # warning|None
     if item: items.append(item)
  5. # --- Apply prior resolutions + recompute per-item status ---
     for it in items:
       it.resolution = prior_resolutions.get(it.item_key)   # acknowledged | revised | None(pending)
       it.status = resolved_status(it)                       # §6.3
  6. gate_status = green if all(it.status == resolved) else (
                     blocked if any pending blocker else needs_review)
  7. return Layer3DGate(items=items, gate_status=gate_status, evaluated_against=etl_version_set, ...)
```

### 5.1 Severity normalization

| Source | Source field → severity |
|---|---|
| 2A | `inclusion == 'prompt_required'` → **warning**; `unresolved_flags[].severity` `error` → **blocker**, `warning` → **warning** |
| 2D | `Layer2DHitlItem.severity` `block` → **blocker**, `warn` → **warning** |
| 2E | `Layer2EHitlItem.block_level == 'block'` → **blocker** (other levels → **warning** until 2E adds finer levels per its §7 note) |
| 3B | `Layer3BHITLItem.severity` `blocker` → **blocker**, `warning` → **warning**, `informational` → **informational** |
| 3C | CN-1 (discipline gated off everywhere) / CN-2 (substitute gated off everywhere) → **warning** (acknowledge-able); surfaced upstream `coaching_flags` → **informational** (Slice 2, §5.4) |
| 3D feasibility | injury-pool-empty → **blocker**; schedule-volume-under-target → **warning** |

`blocker` items can be resolved **only by revise** (never acknowledged) — carried straight from each source's own contract (3B already sets `acknowledge_option = None` when `severity == 'blocker'`; 2D `block` and 2E `block` are likewise revise-only). `warning` / `informational` items accept **acknowledge or revise**.

### 5.2 Feasibility detector — injury-empties-the-pool (blocker)

`detect_injury_pool_empty(phase_structure, layer2a, layer2c_payloads, layer2d)`. Two blocker classes:

- **Strength pool empty.** The usable strength pool is the union of resolvable strength-type, equipment-feasible (`tier > 0`) exercises across locales, minus 2D `excluded_exercises` — i.e. `per_phase.compute_feasible_pool_ids(layer2c, layer2d)`, the *exact* surface synthesis prescribes from (reused so the gate's notion of "usable strength" can't drift from Layer 4's). The detector fires when that pool drops **below 3** (a workable strength session needs ≥3 distinct exercises; v1 floor — Andy 2026-06-21) **and** was ≥3 *before* the exclusions — i.e. an injury, not a structurally strength-light plan, emptied it. The pool is plan-wide (phase-invariant), so this is **one blocker**, not one-per-phase; the phases that program strength (≥1 included discipline with a non-zero phase band) ride in `evidence`. A plan that never had ≥3 strength exercises (e.g. pure MTB/climbing) is **not** flagged — its sport sessions cover it, matching `per_phase._format_strength_exercise_pool`'s "no resolved exercises → no blocker" behavior. This is the one #214 detector that survives as a hard stop.
- **Cardio modality banned.** Cardio sessions are free-composed in Layer 4 (no 2C exercise pool to "empty"), so this reads 2D's **`discipline_risk_profiles`**: an *included* discipline with `risk_level == 'high'` and **no usable substitute** (every `suggested_substitutes` entry `still_at_risk`, or none) is untrainable with nothing to replace it → one blocker per such discipline (Andy 2026-06-21: compute it in 3D). **Suppressed** when 2D already surfaced the same finding via a `no_substitute_for_high_risk` / `gap_x_high_risk_concurrent` `hitl_item` for that discipline (that 2D item already carries it; the §9 `item_key` de-dup can't merge across sources, so the suppression is explicit).

`evidence` carries the phase(s)/discipline, the count of usable exercises after exclusion (`usable_count` / `pool_before_count`), and the 2D exclusion ids that emptied the pool (`excluding_2d_ids`). Resolution = **revise** (`revise_target` → the Layer 1 §B injury record, so the athlete relaxes the injury input or drops the discipline). Both classes are revise-only blockers (`can_acknowledge = False`).

### 5.3 Feasibility detector — schedule-volume-under-target (warning)

`detect_schedule_volume_under_target(phase_structure, layer2a, layer1_payload)`. Compute the athlete's bounded available weekly hours (`weekly_capacity_hours(layer1_payload)` — Σ enabled §K daily windows, capped by `weekly_hours_target`); for each phase, compare it to the phase's **whole-sport target low band** (2A `weekly_total_hours_by_phase[phase][0]`). If available `< target_low` for any phase, emit **one** warning item (not per-phase spam — the worst phase, i.e. the one with the highest target low edge, carries the message; the rest list in `evidence`). Returns None when capacity is unknown (`weekly_capacity_hours` is None — no §K windows and no `weekly_hours_target`) or no phase is under target.

> **Decision (Andy 2026-06-21): phase-total band, not dominant-discipline.** The comparison uses the *phase's whole-sport weekly total* (`weekly_total_hours_by_phase`), not the per-discipline `phase_volume_bands_hours` low edge for the dominant discipline. The dominant-discipline band rarely trips for a multi-discipline athlete even when total weekly time is well under what the block demands (each discipline's slice looks individually fitable while the sum doesn't fit) — so the per-discipline reading would under-warn exactly the multi-sport athletes this product targets. The phase total is the figure the athlete experiences as "hours per week," which is what the warning is about.

This does **not** block and does **not** raise. Layer 4's existing volume math already clamps the prescribed volume to `min(capacity, band)` (`validator.phase_volume_bands_hours` effective-hours bound), so the plan is automatically trimmed to fit the athlete's real schedule. 3D's only job is to *tell the athlete* the schedule is below target so the trim isn't silent: athlete acknowledges → proceed. Message (coaching voice): "Your schedule gives about **{avail} h/week**; this block targets **{low}–{high} h**. The plan will be built to the time you have, but expect it to under-prepare you for the demand — add training days or a longer runway if you can."

### 5.4 Cross-locale / cross-source conflict detectors — 3C (`map_3c_items`)

3C is the Layer-3 node that catches conflicts **no single upstream node can see**, because they exist only in the *intersection* of several already-built payloads. It is **rules-only** (no LLM, no new query): a deterministic pass over the 2A/2C/2D payloads `evaluate_layer3d_gate` already holds, appended at §5 step 3 — **no `Layer3DGate` / `GateItem` contract change, no gate signature change**. The decision to keep it rules-only (vs. an LLM conflict-reasoner) and to scope it to net-new detection **plus** surfacing the orphaned upstream `coaching_flags` is Andy's (2026-06-23, issue #216).

**Slice 1 — net-new conflict detectors (shipped).** Two findings, both **warnings**, both acknowledge-able (the athlete can fix the input, add a location, or accept the trade-off), revise → the locations list (`profile.locales` → `locales.list_profiles`):

- **CN-1 — included discipline gated off at every location.** An *included* (race-relevant, 2A `inclusion == 'included'`) discipline that **every** locale's 2C surface gates via `toggle_off_for_discipline` (gear toggle off) or `requires_skill_capability` (athlete-skill capability off). Each per-locale 2C payload only knows its own locale, so none can distinguish "off here" from "off everywhere" — the cross-locale AND is genuinely new signal. `evidence`: `discipline_id`, `locale_count`, `role`.
- **CN-2 — injury substitute gated off at every location.** A `high`/`elevated`-risk 2D discipline whose `suggested_substitutes` are **all** (counting only the usable, not-`still_at_risk` ones) gated off across **every** locale — 2D, looking only at injury risk, recommends a fallback that 2C, looking only at locale gear/skill, has made un-trainable. **Suppressed** when 2D already surfaced a `no_substitute_for_high_risk` / `gap_x_high_risk_concurrent` `hitl_item` for the discipline (that item already carries the gap; §9 `item_key` de-dup can't merge across sources). **Mutually exclusive** with the §5.2 `cardio_modality_banned` blocker, which fires only when *no* usable substitute exists. `evidence`: `discipline_id`, `risk_level`, `gated_substitutes`, `locale_count`.

Both are deliberately **conservative**: they fire only on an *every-locale* intersection, so a discipline trainable at even one location never trips. They **under-fire rather than false-fire** — the safe bias for a gate the athlete sees, and the right posture for a v1 detector whose precision we'll tune from production signal. With zero locales the detectors are skipped (an "everywhere" claim is vacuous).

**Slice 2 — surface the orphaned `coaching_flags` (deferred; §13).** The upstream advisory `coaching_flags` from 2A/2B/2C/2D/2E are computed today and silently discarded. Slice 2 surfaces them into the gate as **informational** items so they ride the review screen without parking a plan. This requires one primitive change — `compute_gate_status` must treat `informational` as **display-only / non-gating** (today any unresolved item, informational included, forces `needs_review`; surfacing a flood of advisory flags under that rule would park every plan) — plus threading `layer2b_payload` into the gate signature (2B is the one flag source not yet passed; `cone.layer2b_payload` is already in hand at the orchestrator call site, kept **out** of the §4 etl-coherence check exactly like 2C). The per-flag severity mapping (which advisory flags, if any, warrant `warning` vs `informational`) and cross-source suppression are designed in §13.

### 5.5 Determinism

The whole node is a pure function of its inputs + `prior_resolutions`. No clock, no RNG, no DB read inside the function. `item_key` (§6.4) is a stable hash of `(source, source_item_id, plan-relevant discriminator)` so the same finding keeps the same key across re-evaluation rounds — that is what lets a resolution from round 1 still apply in round 2 after an unrelated revise.

---

## 6. Payload schema

### 6.1 `Layer3DGate`

| Field | Type | Notes |
|---|---|---|
| `user_id` | `int` | |
| `plan_version_id` | `int` | the row the gate state attaches to |
| `gate_status` | `Literal['green','needs_review','blocked']` | `green` = advance to Layer 4; `needs_review` = warnings pending (resolvable by acknowledge); `blocked` = ≥1 pending blocker (revise-only) |
| `items` | `list[GateItem]` | possibly empty (→ `green`) |
| `evaluated_against` | `dict[str,str]` | the `etl_version_set` the gate was computed against — provenance only (it does *not* move on an athlete edit, so it can't carry the staleness signal; that's `input_fingerprint`) |
| `input_fingerprint` | `str \| None` | Reading-B staleness fingerprint (§6.1.1): a SHA-256 over the gate's raw leaf inputs, stamped by the caller when it parks a non-green gate; `None` on a green gate (proceeds to synthesis, never re-checked) or one parked before this shipped |
| `evaluated_at` | `datetime` | stamped by the **caller** on persist, not inside the pure function |

#### 6.1.1 `input_fingerprint` — the staleness fingerprint (Reading B)

`input_fingerprint` lets the review routes detect cheaply — **without an LLM call** — whether an athlete edit (or a provider sync) changed the gate's inputs since it was parked, so a stale verdict re-evaluates against current reality (§11.2). Computed by `layer4.orchestrator.compute_gate_input_fingerprint`, stamped on the gate when the orchestrator parks it non-green, and recomputed by the routes on re-entry / acknowledge / `[Generate]`.

**Reading A vs Reading B.** The signal could hash either the gate's *outputs* (the computed 2A/2C/2D/2E/3B payloads — "Reading A") or its *raw leaf inputs* ("Reading B"). Reading A is a non-starter for a cheap re-check: re-deriving 2E/3B would re-run the LLM stages 3A/3B just to learn whether anything changed. **Reading B is what shipped** — fingerprint the raw inputs those stages consume, so the re-check is a handful of indexed reads and no LLM:

| Leaf input | Source |
|---|---|
| athlete profile | `build_layer1_payload` |
| target race | the `RaceEventPayload` |
| equipment / terrain | per-cluster-locale effective tags + terrain ids |
| incoming training data | `assemble_layer3a_integration_bundle` (the 3A input bundle) |
| declared availability | `load_event_windows` |
| platform-data version | `_q_current_etl_version_set` |
| 3A/3B prompt revision | `LAYER3_GATE_PROMPT_REVISION` |
| plan start date | the plan's scope start |

The leaf set is a deliberate **superset** of the gate's true determinants: a **false "stale"** (an edit to a field the gate ignores, or the training-data window sliding a day) is harmless — it only triggers a re-evaluation that mostly replays from cache; a **false "fresh"** (missing a real change) is the bug this closes, so when in doubt an input is included. `evaluated_against` (the etl-version stamp) stays for provenance — it does not move on athlete edits, which is exactly why it can't carry the staleness signal on its own.

### 6.2 `GateItem`

| Field | Type | Notes |
|---|---|---|
| `item_key` | `str` | stable identity across rounds (§6.4) |
| `source` | `Literal['2A','2D','2E','3B','3D_feasibility']` | (`'3C'` reserved) |
| `source_item_id` | `str \| None` | the upstream item's own id/label (e.g. 3B `item_label`, 2E `item_id`) |
| `severity` | `Literal['blocker','warning','informational']` | per §5.1 |
| `title` | `str` | short athlete-facing label |
| `message` | `str` | athlete-facing detail, coaching voice; sourced from the upstream item's athlete-facing field (3B `description`, 2D `message`, 2E `rationale_for_athlete`) |
| `resolution_options` | `list[str]` | carried from the source (`suggested_resolutions` / `resolution_options` / `recommended_action`) |
| `revise_target` | `str \| None` | the Layer 1 field / form surface the athlete edits to fix it (3B `revise_target`; 3D feasibility points at §B injury or the 2A toggle) |
| `can_acknowledge` | `bool` | `False` for blockers; `True` for warning/informational |
| `evidence` | `dict[str,Any]` | machine-readable inputs that triggered it (esp. for the 3D feasibility detectors) |
| `status` | `Literal['pending','acknowledged','revised']` | computed per §6.3 |
| `resolution` | `GateResolution \| None` | the athlete's choice + timestamp + optional reasoning |

### 6.3 `GateResolution` + resolved-status rule

```python
class GateResolution(_Base):
    kind: Literal['acknowledged', 'revised']
    reasoning: str | None        # optional athlete note; only for 'acknowledged'
    resolved_at: datetime
```

`status` from `resolution`:
- no resolution → `pending`
- `acknowledged` → `acknowledged` (allowed only when `can_acknowledge` — the route rejects an acknowledge on a blocker)
- `revised` → `revised` **iff** the item no longer re-appears after the upstream re-run (the cascade cleared it). If the re-aggregation still surfaces the same `item_key`, it reverts to `pending` (the athlete's edit didn't actually fix it).

A blocker is only ever cleared by a **revise that makes it disappear** — there is no acknowledge escape hatch, matching every upstream source's own blocker contract.

### 6.4 `item_key` derivation

`item_key = sha256(source | source_item_id | discriminator)[:16]` where `discriminator` is the plan-relevant scope (e.g. phase name for the injury-pool detector, discipline_id for a per-discipline 2D item). Stable across rounds so a round-1 acknowledgment of an unrelated warning still holds after a round-2 revise of a different item.

---

## 7. Item taxonomy (the closed source set)

| Source | Items surfaced | Authority |
|---|---|---|
| **2A** | `prompt_required` disciplines; `unresolved_flags` | `Layer2A_Spec` §7 |
| **2D** | `hitl_items` (post_surgical_clearance, cardiac_high_load_review, concussion_current, no_substitute_for_high_risk, gap_x_high_risk_concurrent) | `Layer2D_Spec` §7 |
| **2E** | `hitl_items` + `supplement_integration.contraindication_hitl_items` (supplement×cardiac, raceday caffeine×cardiac, pregnancy×stimulant, anaphylaxis×aid-station-food) | `Layer2E_Spec` §7 |
| **3B** | `hitl_surface` (unrealistic_goal, first_time_competitive_goal, dnf_recurrence_risk, compressed_on_fatigued_athlete) | `Layer3_3B_Spec` §6.1 |
| **3D feasibility** | injury_pool_empty (blocker); schedule_volume_under_target (warning) | this spec §5.2/§5.3 |
| **3C** | CN-1 discipline_gated_all_locales (warning); CN-2 substitute_gated_all_locales (warning). *Slice 2 (deferred, §13): surfaced upstream `coaching_flags` (informational).* | this spec §5.4 |

The set is **closed** (Control_Spec §7). A new gate-item source requires a spec amendment here — the aggregator must not silently invent items.

---

## 8. Caching

3D is cheap (a handful of list comprehensions + one `phase_structure_from_3b()` call). No cache at launch, consistent with the Control_Spec §6 "caching not built at launch" posture. It is **designed** cache-friendly (pure, deterministic, inputs explicit). Invalidation, when added, is automatic: any upstream re-run that changes a 2A/2D/2E/3B payload changes the inputs and forces a fresh gate evaluation — which is exactly the resolution-round re-evaluation the gate already does, so there is nothing extra to invalidate. Staleness of a *persisted* gate (a parked plan whose inputs move later) is made explicit by the `input_fingerprint` (§6.1.1), recomputed on review re-entry, acknowledge, and the generate click to re-kick a fresh evaluation (§11.2).

---

## 9. Edge cases

| Case | Behavior |
|---|---|
| No items at all | `gate_status='green'`; orchestrator advances straight to Layer 4. The common path for a clean athlete. |
| Only warnings, all acknowledged | `green`. |
| A blocker present, unresolved | `blocked`; Layer 4 never invoked; plan row sits at `needs_review` (status name §10). |
| Athlete acknowledges, then an unrelated upstream re-run changes inputs | The acknowledged item keeps its `item_key` (§6.4) → its acknowledgment persists; only newly-appearing items are `pending`. |
| Revise that doesn't actually fix the blocker | Re-aggregation re-surfaces the same `item_key` → reverts to `pending` (§6.3); gate stays `blocked`. The athlete sees it's still open. |
| Schedule-volume-under-target on every phase | One warning item (worst phase headline; others in `evidence`) — not per-phase spam (§5.3). |
| Injury-pool-empty AND schedule warning together | Both items surface; `gate_status='blocked'` (the blocker dominates); the warning rides along and is acknowledgeable but the gate can't go green until the blocker is revised away. |
| Upstream `hitl_required=True` but `hitl_items=[]` | Trust the items list, not the flag — if there are no items, there's nothing to gate on. Log the inconsistency (Rule #15) but don't fabricate an item. |
| 2E `contraindication_hitl_items` duplicates a `hitl_items` entry | De-dup by `item_key`; the same finding surfaces once. |

---

## 10. Storage + state model (DB)

v1, minimal (handful-of-athletes scale):

- **`plan_versions.generation_status`** gains a value: `'needs_review'` (alongside `generating`/`ready`/`failed`). A plan that hits a non-green gate parks at `needs_review` instead of advancing to `generating`.
- **`plan_versions.hitl_gate` JSONB** — the persisted `Layer3DGate` (items + resolutions + `gate_status` + `evaluated_against`). One column, no new table; the gate is small and always read/written whole. (A normalized `plan_hitl_items` table is the obvious v2 move if items need per-row querying — named in §13, not built now.)

The `revise` cascade reuses the existing partial-update invalidation machinery (`Control_Spec` §4) — no new mechanism. The gate column is rewritten on each evaluation round. **`[Cancel]`** voids the row (D-64 atomic-write; nothing was written to unwind). **At most one** plan may sit in `generating`/`needs_review` per athlete (one-in-flight, §11.1) — enforced at plan-create. The parked-plan lifecycle + staleness re-fire are §11.1/§11.2.

---

## 11. Resolution flow + UI surface

The athlete-facing review screen (the "screen" Andy asked for):

1. Plan creation runs the pipeline to 3B, then 3D. If `gate_status != green`, the plan parks at `needs_review` and the athlete lands on **`GET /plans/v2/<id>/review`**.
2. The screen lists items grouped by severity (blockers first). Each shows `title`, `message` (coaching voice), and its affordance:
   - **warning/informational** → `[Acknowledge]` (optional reasoning text) or `[Fix this]` (→ the `revise_target` edit surface).
   - **blocker** → `[Fix this]` only (no acknowledge button; the screen states why it can't be waved through).
3. `POST /plans/v2/<id>/review/resolve` records a `GateResolution` and re-evaluates the gate (re-running upstream layers when the resolution was a revise). On `green`, the screen offers `[Generate plan]`, which flips the row to `generating` and resumes the existing Layer-4 advance loop.

Copy tone follows the coaching voice (direct, evidence-grounded, no cheerleading) per `CLAUDE.md`.

### 11.1 Parked-plan lifecycle (Andy 2026-06-21)

The athlete does not have to resolve everything in one sitting. Two ways off the review screen:

- **`[Save as pending & exit]`** — the plan stays at `generation_status='needs_review'` with its `hitl_gate` state (items + any resolutions made so far) persisted. Non-destructive; they can come back and pick up where they left off.
- **`[Cancel]`** — discards the in-flight plan attempt. The `plan_versions` row is voided per D-64 atomic-write semantics (no sessions were ever written; nothing to unwind). Use when the athlete decides not to pursue this plan at all.

**Re-entry.** A parked plan appears in the athlete's **plans list with a "Needs review" badge**; the badge links back to `GET /plans/v2/<id>/review`. That list is the single discovery surface — there is no separate "pending plans" view.

**One in flight at a time (v1).** An athlete may have **at most one** plan in `generating`/`needs_review` at once. Starting a new plan-create while one is parked is refused with a prompt to either resume or cancel the parked plan first. Keeps the model simple at handful-of-athletes scale; revisit if multi-plan drafting is ever needed.

### 11.2 Staleness re-fire (Andy 2026-06-21; shipped as Reading-B, 2026-06-22)

A parked plan can go stale: while it sits at `needs_review`, a profile edit, a target-race edit, or a provider sync can change an upstream input (e.g. new training data shifts 3A → 3B), adding, removing, or changing gate items. The gate must never act on a verdict computed against inputs that no longer hold.

**The guard is the `input_fingerprint` (§6.1.1).** The orchestrator stamps it when it parks a non-green gate; the review routes recompute it from current inputs — **cheap, no LLM** (`compute_gate_input_fingerprint` is indexed reads) — and compare. A changed digest means the athlete edited something (or new data synced) since parking, so the verdict is stale. The check runs at three points:

1. **On review re-entry** (`GET …/review`) — stale ⇒ re-kick (below); fresh ⇒ render the stored gate.
2. **On acknowledge** (`POST …/review/resolve`) — stale ⇒ bounce back to the review screen rather than record a resolution against an item that may no longer exist.
3. **At `[Generate plan]`** (`POST …/review/generate`) — stale ⇒ re-kick regardless of the stored verdict; only when fresh does the "every item resolved" guard hold. This closes the bug where a stale stored-non-green blocked an athlete who'd already fixed the issue.

**Re-kick = the async recompute.** A stale gate flips the row back to `generation_status='generating'` (guarded on `needs_review`, so concurrent re-kicks are idempotent); the resumable poller then re-runs the pipeline off the request path and re-evaluates the gate against current reality — re-parking with fresh findings, or proceeding to synthesis if the edit cleared the gate. The athlete sees the progress screen poll, not a blocked GET (this is the "recompute async like plan-gen" decision — the existing poller *is* the async worker). Synchronous recompute inside the review GET was rejected: on a cache miss it would spin tens of seconds firing 3A/3B re-derivation while the athlete waits.

**Resolutions survive recompute by `item_key` (§6.4):** an already acknowledged/revised item that still applies keeps its resolution; one that no longer applies drops off; a newly-surfaced item is `pending`. So a stale-but-since-fixed warning clears itself, and a newly-introduced blocker correctly re-blocks a plan the athlete thought was ready.

**Fail-safe.** The staleness probe must never 500 the review screen: any error recomputing the fingerprint (e.g. the athlete deleted their home locale while parked) is swallowed and treated as fresh — the next `[Generate]` re-evaluates against current inputs and surfaces any such gap there. A gate with no stored `input_fingerprint` (green, or parked before this shipped) is likewise treated as fresh.

**`[Fix this]` revise links (shipped 2026-06-22).** Each item's `revise_target` renders as a link to the edit surface that owns the input: `profile.injuries` → the injuries editor (`injuries.list_entries`); `profile.disciplines` / `profile.nutrition` / `profile.availability` → the athlete profile editor (`profile.edit`, where all three are edited); 3B `h2.*` (target-race inputs) → the target race editor (`race_events.edit_race`). The map is built in `plan_create._build_revise_urls` and is **fail-safe** — a target with no edit surface (e.g. 3B `h3.plan_duration_weeks` on an open-ended plan) or one that can't be resolved (no target race, an endpoint rename) falls back to naming the target, never a 500. After the athlete edits and returns to the review screen, the §11.2 staleness re-fire re-evaluates the gate against the edit. *(Note: the earlier design draft routed the locale-scoped profile inputs to the per-locale editor; on build they were found to live on the single athlete profile page — `_build_revise_urls` is the source of truth for the mapping.)*

---

## 12. Performance budget

Deterministic, no LLM, no network. Target **< 50 ms** per evaluation (a few list passes + one pure `phase_structure_from_3b()`). Re-evaluation after a revise is dominated by the upstream re-run it triggers (2D/2E/3B regen), not by 3D itself. No latency risk; the gate is strictly cheaper than the synthesis it guards (and *saves* the 20–30 min synthesis when it blocks).

---

## 13. Open items / forward references

- **3C — Slice 1 net-new detectors (shipped, §5.4).** `map_3c_items()` with CN-1 / CN-2 lands as one more source feeding §5 step 3 — rules-only, no aggregator/signature contract change. Tracked under epic #211 (build #844, design ratified #216, Andy 2026-06-23).
- **3C — Slice 2: surface the orphaned `coaching_flags` (next slice).** Surface the upstream advisory flags (2A `training_gap` / `weight_override_divergence`; 2B `unbridgeable_terrain` / `requires_skill_capability` / `undefined_gap`; 2C `low_coverage` / `critical_dropped` / `craft_substitution_via_group`; 2D `elevated_discipline_risk` / `recurring_injury_pattern` / etc.; 2E `dietary_pattern_deficiency_risk` / `heat_acclim_gap` / `low_calorie_target_relative_to_rmr` / etc.) into the gate as **informational** items. Mechanically-applicable build steps (Rule #11):
  1. **`layer3d/gate.py` — `compute_gate_status`:** make `informational` non-gating. Replace the body with: filter `gating = [it for it in items if it.severity != "informational"]`, then `green` when all `gating` items are resolved, `blocked` when any `gating` blocker is pending, else `needs_review`. (Without this, surfaced advisory flags would park every plan — today an unresolved informational item forces `needs_review`.)
  2. **`layer3d/gate.py` — `evaluate_layer3d_gate` signature:** add `layer2b_payload: Layer2BPayload | None` (the one flag source not yet passed); thread it into `map_3c_items`. Keep 2B **out** of `_coherent_etl_version_set` (like 2C — it isn't an aggregation-contract source).
  3. **`layer4/orchestrator.py`** (gate call ~line 1777): pass `layer2b_payload=cone.layer2b_payload` (already in hand).
  4. **`map_3c_items` / a `surface_orphaned_flags` sibling:** emit one informational `GateItem` per flag with `can_acknowledge=True`, `revise_target` per source (2A→`profile.disciplines`; 2B→`h2.*` race editor; 2C equipment→`profile.locales`; 2D→`profile.injuries`; 2E→`profile.nutrition`), and **suppress** any flag already covered by a CN-1/CN-2 item or a mapped hitl_item for the same discipline (e.g. a 2C `toggle_off_for_discipline` already escalated to CN-1).
  5. **Per-flag severity decision (open — needs Andy):** default **all** surfaced flags to `informational`; promote only a named few to `warning` if any warrant parking a plan. Recommend keeping them all informational at first (advisory by nature) and tuning from production signal. This is the one Slice-2 product call to confirm before building.
  6. Tests in `tests/test_layer3d_gate.py` + spec: flip §7's 3C row + §5.4 Slice-2 note to "shipped", add the severity-mapping table.
- **Normalized `plan_hitl_items` table** — v2, if per-item querying/analytics is needed. v1 uses the JSONB column (§10).
- **Revise-cascade wiring depth** — v1 routes the athlete to the Layer 1 edit surface and leans on the existing invalidation cascade; the exact re-run scope per item source is implementation-slice detail (named, not fully spec'd here).
- **Layer 4 defensive raise.** With detection owned by 3D, the surviving `Layer4ShapeInfeasibleError` (injury-pool-empty) becomes a **defensive** raise in Layer 4 — fired only if synthesis is somehow reached on an infeasible shape the gate should have caught (mirrors Layer 4's §4 "caller pre-checks; Layer 4 raises defensively"). The schedule/frequency/skill classes are **removed** from Layer 4 entirely (see `Layer4_Spec.md` §10.2 revision, same change-set).
- **2E `block_level` granularity** — 2E currently emits `block_level='block'`; finer levels (warn vs block) would let 3D map 2E warnings as acknowledgeable. Deferred to 2E's own spec.

---

## 14. Test scenarios + gut check

### Test scenarios

| ID | Scenario | Expected |
|---|---|---|
| TS-3D-1 | Clean athlete, no upstream items, feasible shape | `gate_status='green'`; 0 items; Layer 4 runs |
| TS-3D-2 | 3B `viability='unrealistic-as-stated'` (blocker) | 1 blocker item from 3B; `blocked`; revise-only; Layer 4 not invoked |
| TS-3D-3 | 2D `post_surgical_clearance` (severity `block`) | 1 blocker; `blocked`; `revise_target` → §B injury record |
| TS-3D-4 | 2E supplement×cardiac contraindication | 1 blocker; `blocked` |
| TS-3D-5 | Injury empties a phase's strength pool (the #214 survivor) | 1 `3D_feasibility` blocker; `evidence` carries phase + post-exclusion count + 2D ids |
| TS-3D-6 | All-running-banned removes a discipline's only cardio modality | 1 `3D_feasibility` blocker for that discipline |
| TS-3D-7 | Available 4 h/wk, Build targets 10–12 h | 1 `schedule_volume_under_target` **warning**; `needs_review`; acknowledge → `green`; plan still generates (clamped) |
| TS-3D-8 | 3B `first_time_competitive_goal` (warning) acknowledged with reasoning | item `acknowledged`; reasoning stored; `green` |
| TS-3D-9 | Blocker present + warning present | `blocked`; warning acknowledgeable but gate stays blocked until blocker revised |
| TS-3D-10 | Athlete acknowledges warning (round 1), revises an unrelated blocker (round 2) | round-1 acknowledgment persists via stable `item_key`; gate goes `green` after round 2 clears |
| TS-3D-11 | Revise that doesn't fix the blocker | same `item_key` re-surfaces → `pending`; gate stays `blocked` |
| TS-3D-12 | `etl_version_set` mismatch across payloads | `Layer3DGateError('etl_version_set_mismatch')` |
| TS-3D-13 | `[Save as pending & exit]` then return | plan still `needs_review`; `hitl_gate` (items + prior resolutions) intact; re-entry via plans-list "Needs review" badge (§11.1) |
| TS-3D-14 | `[Cancel]` on the review screen | `plan_versions` row voided (D-64); no sessions written; plan leaves the plans list |
| TS-3D-15 | Start a new plan-create while one is parked at `needs_review` | refused; prompt to resume or cancel the parked plan first (one-in-flight, §11.1) |
| TS-3D-16 | Parked plan goes stale — provider sync re-runs 3B, adding a new blocker | on re-entry the gate re-kicks (`input_fingerprint` mismatch, §6.1.1); prior resolutions persist by `item_key`; new blocker is `pending`; gate reverts to `blocked` (§11.2) |
| TS-3D-17 | `green` plan goes stale, athlete clicks `[Generate plan]` | staleness guard recomputes at the click; if now non-`green`, generation refused → back to `needs_review` (§11.2) |
| TS-3C-1 (CN-1) | Included discipline gated `toggle_off_for_discipline` at **every** locale | 1 `3C` warning `discipline_gated_all_locales`; `needs_review`; acknowledge-able; revise → `profile.locales` |
| TS-3C-2 (CN-1 negative) | Same discipline gated at one locale but trainable at another | no `3C` item (every-locale intersection not met) |
| TS-3C-3 (CN-1) | Gate is `requires_skill_capability` (not gear) at every locale | fires identically to the gear case |
| TS-3C-4 (CN-2) | `high`-risk discipline; its only usable substitute gated off at every locale | 1 `3C` warning `substitute_gated_all_locales`; `gated_substitutes` in `evidence` |
| TS-3C-5 (CN-2 suppress) | Same, but 2D already emitted `no_substitute_for_high_risk` for the discipline | no `3C` item (2D already carries it) |
| TS-3C-6 (CN-2 negative) | Substitute trainable at ≥1 locale, or every substitute `still_at_risk` (no usable sub) | no `substitute_gated_all_locales` item (CN-2 is mutually exclusive with the §5.2 no-substitute blocker) |

### Gut check

- **Biggest risk: the revise cascade.** "Athlete edits a Layer 1 field → affected layers re-run → gate re-evaluates" leans entirely on the partial-update invalidation machinery being correct and reachable from the review screen. That machinery exists (Control_Spec §4) but has never been driven from an athlete-facing mid-plan-creation edit. If it's flaky, a blocker could be un-fixable from the screen. **Mitigation:** v1 can ship the *acknowledge* path + the *read* surface first (closes the silent-discard safety gap immediately) and treat the full revise-cascade-from-screen as the slice that needs the most testing. Flagging for the build-slice plan.
- **Staleness — now specced (§11.2).** The earlier gap (a parked plan going stale when a provider sync changes 3A→3B days later) is closed: the gate re-evaluates on re-entry, on any upstream re-run, and at the `[Generate plan]` click, guarded by `evaluated_against`; resolutions survive by `item_key`. Remaining thin spot: *what wakes the re-evaluation* when the athlete isn't on the screen — v1 leans on "re-check on next view / next click" rather than a push the instant a sync lands. Fine at this scale; if a stale-green plan could auto-generate from a background trigger, the guard at the generate click is the backstop.
- **Best argument against this design:** folding the #214 feasibility detectors into 3D (rather than leaving them in Layer 4) moves logic across a layer boundary. Counter: the detectors *need* 3B's phase structure + all of 2A/2C/2D, which is exactly 3D's input set, and the gate is the natural home for "stop before synthesis" — keeping a thin defensive raise in Layer 4 preserves defense-in-depth without duplicating the detection.
- **Scope honesty:** this is the design for the *first* gate slice. 3C and the deepest revise-cascade wiring are explicitly deferred. The spec is written so they bolt on without reshaping the `Layer3DGate` / `GateItem` contract.
