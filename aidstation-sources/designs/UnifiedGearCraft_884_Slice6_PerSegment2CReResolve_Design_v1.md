# #884 Unified Gear/Craft Model — Slice 6 (final): Per-Segment 2C Re-Resolve — Design v1

**Written:** 2026-06-30 (branch `claude/6c3-2c-resolve-mfuvo2`). **Parent design:** `Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §15/§17. **Predecessor:** slice 5 (`…Slice5_AwayOverlay…`, which deferred this as "feasibility now, 2C later"). **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3. **Issue:** [#884](https://github.com/ahorn885/exercise/issues/884).

**Andy decisions (AskUserQuestion, 2026-06-30):** (1) scope = **correctness + away coaching flags** (the full re-resolve, split into two PRs since it's over the 5-file ceiling); (2) away gear basis = **brought + standing-at-destination** (mirror the existing away-feasibility `owned_crafts` logic).

---

## 1. Purpose

When a plan spans an **away** event window, the athlete is physically at the destination that week. Today the away cascade already resolves **discipline feasibility** against the destination's terrain + equipment (slice 5), but when a discipline degrades to a **strength substitute**, the substitute exercises are drawn from the **home gym's** 2C equipment pool, not the destination's. This slice makes the away segment's strength-substitute pool (and the `toggle_off_for_discipline` coaching flags) reflect the **destination**.

## 2. Current state (and the #780 assumption this reverses)

- `_gather_feasibility_inputs` (`orchestrator.py:586`) builds `pool_by_discipline` from the **primary (home) locale's** 2C entry only. The `#780` comment is explicit and deliberate: *"the strength substitute pool reads the PRIMARY locale's 2C entry (home-gym equipment; a home-substituted strength session is done at home)."*
- `_build_event_window_overlay`'s away branch (`orchestrator.py:959`) calls `_resolve_included_feasibility(fi, locale_order=away_cluster, terrain_by_locale=<away>, equip_by_locale=<away>, owned_crafts=away_crafts, …)` — **away terrain/equipment/crafts, but the home `fi.pool_by_discipline`.**
- The destination's 2C payload is **not** in `cone.layer2c_payloads` (that dict is the *home* cluster). So the away strength pool must be **built fresh** from a destination 2C resolution.

**Why reversing #780 for away segments is correct:** #780's rationale ("the substitution is done at home") holds for *home* and for *subtractive* home windows (indoor-only days). It breaks for an **away** week, where the whole point is the athlete is not home — a strength session that week is done at the destination, on the destination's equipment. The reversal is **scoped to away segments only**; home + subtractive segments keep the home pool unchanged.

## 3. The away-2C build (shared by both PRs)

Inside `_build_event_window_overlay`'s away branch, build a destination 2C payload by mirroring the home build (`orchestrator.py:1213-1231`), reusing cone fields already in scope:

```python
from layer2c.builder import q_layer2c_equipment_mapper_payload
from athlete_gear_repo import owned_gear_toggle_states

# Andy: away gear basis = brought + standing-at-destination (all kinds, not just
# craft kinds — owned_gear_toggle_states self-filters to the toggle gear_ids).
away_gear_all = sorted(brought | standing)          # already computed at :951-954
away_gear_states = owned_gear_toggle_states(away_gear_all)

away_l2c = q_layer2c_equipment_mapper_payload(
    db,
    locale_id=away_ov.away_locale,
    locale_equipment_pool=sorted(
        locations.locale_effective_tags(
            db, user_id, away_ov.away_locale, exclude_disputed=True
        )
    ),
    cluster_locale_ids=away_cluster,
    cluster_gear_toggle_states=away_gear_states,
    included_discipline_ids=<included ids>,          # from cone.layer2a_payload
    layer2d_payload=cone.layer2d_payload,
    etl_version_set=cone.etl_version_set,
    skill_toggle_states=cone.layer1_payload.lifestyle.skill_toggle_states,
)
```

Inputs all available: `etl_version_set`, `layer2d_payload`, `layer1_payload`, `layer2a_payload` live on `cone`; `brought`/`standing`/`away_cluster` are already computed in the away branch.

`included_discipline_ids` = the same `[d.discipline_id for d in cone.layer2a_payload.disciplines if d.inclusion == "included"]` the home build uses (line 604/1154) — extract once into the overlay scope.

## 4. PR-1 — correctness: away strength pool from the destination

**No prompt-body change** (Stop-and-ask trigger #1 does NOT apply — substitutes already render via the away `TerrainResolution`).

1. Extract a reusable `_extract_pool_by_discipline(l2c_payload) -> dict[str, list[str]]` helper from the home logic at `orchestrator.py:587-601` (the tier-(1,2,3) filter + per-discipline priority-rank sort). Home build calls it; away build calls it on `away_l2c`.
2. Add an optional `pool_override: dict[str, list[str]] | None = None` kwarg to `_resolve_included_feasibility` (`orchestrator.py:630`). Where it reads `fi.pool_by_discipline.get(d_id)`, use `(pool_override or fi.pool_by_discipline).get(d_id)`.
3. In the away branch, build `away_l2c` (§3), `away_pool = _extract_pool_by_discipline(away_l2c)`, and pass `pool_override=away_pool` into the away `_resolve_included_feasibility` call. Home + subtractive callers pass nothing → byte-identical.
4. **Rule #15 log:** print the away locale, the away pool sizes per discipline, and the away gear-toggle states — the inputs that drove an away strength substitution (extends the existing `event_window_overlay` away log at ~:982).

**Behavior-neutral cases:** when the destination's effective pool equals home's (same gym chain / same logged equipment), `away_pool == home pool` → identical output. The change only bites when the destination's 2C pool differs.

**Files (PR-1):** `layer4/orchestrator.py` (helper + away-branch build + signature) + `tests/test_layer4_event_windows.py` + `tests/test_layer4_orchestrator.py`. ~1 substantive + 2 test → under ceiling.

## 5. PR-2 — away coaching flags in the synthesis overlay

**Modifies the per-phase synthesis prompt body → Stop-and-ask trigger #1. The rendered copy below is a DRAFT for Andy's sign-off before building.**

1. Add `away_toggle_flags: tuple[Layer2CCoachingFlag, ...] | None = None` (or the minimal `tuple[str, ...]` of rendered lines) to `EventWindowSegment` (`session_feasibility.py:860`).
2. In the away branch, populate it from `away_l2c.coaching_flags` filtered to `flag_type == "toggle_off_for_discipline"` (the destination-unavailable disciplines).
3. In `_format_event_window_overlay` (`per_phase.py:1661`), render the away toggle flags into the segment's overlay block.

**DRAFT prompt copy (per away segment, when away toggle flags exist):**

> _At this destination you won't have: {discipline names} (no {gear} on hand). Substitute per the feasibility lines below; don't program these disciplines for these dates._

(Coaching-voice, direct, no hedging — matches the existing overlay brief. Exact wording is the trigger-#1 decision; this is a starting point.)

**Files (PR-2):** `layer4/session_feasibility.py` (segment field + populate) + `layer4/per_phase.py` (render) + `tests/test_layer4_event_windows.py` (overlay-render assertions). ~2 substantive + 1 test.

## 6. Caching / invalidation

The away 2C build folds into the away feasibility that's already part of the segment, which already feeds `compute_event_windows_hash` via the overlapping windows. **No new cache surface.** The away pool is content-addressed through the destination's `locale_effective_tags` + gear-toggle states — when the athlete's brought/standing gear or the destination's equipment changes, the next plan create/refresh re-resolves (the existing eviction-on-write covers gear/locale changes). No `etl_version_set` pinning beyond what 2C already carries. No Neon/layer0 apply owed.

## 7. Two-PR split + branch

- **PR-1 (correctness):** §3 + §4. Behavior-changing but no prompt-body change. Ship first.
- **PR-2 (coaching flags):** §5. Trigger-#1 copy sign-off required first.
- **Branch:** both on `claude/6c3-2c-resolve-mfuvo2` (the harness-pinned branch pairs 6c-3 + 2c-resolve). Per-commit labels (`#884 slice 6 2C re-resolve PR-1 …`) keep the audit trail; Andy decides PR boundaries at go-time (one PR for the branch, or split 6c-3 out).

## 8. Edge cases

- **No away window** → `overlapping == []`, early return, untouched.
- **Away destination is "cold" (no logged equipment)** → `locale_effective_tags` returns the assumed-baseline pool (same as the existing `assumed_baseline` path at :979); the away 2C resolves against it, and the existing "log actuals on arrival" marker still fires.
- **Empty brought ∪ standing** → `away_gear_states == {}` (every toggle OFF) — the destination 2C suppresses no toggles; strength pool reflects venue equipment only. Consistent with slice-5's empty-union byte-identical path.
- **Destination 2C build fails** (DB hiccup) → wrap in the away branch's existing try/except posture (advisory; fall back to `fi.pool_by_discipline` with a Rule #15 log) so a 2C glitch never fails plan generation.

## 9. Test scenarios

1. Away segment, destination pool ⊃ a strength exercise home lacks → away strength substitute includes it; home segment unchanged.
2. Away segment, destination pool == home pool → byte-identical to pre-change output.
3. Brought climbing_gear to a destination with no standing climb gear → climbing NOT toggled-off at destination (PR-2 flag absent); without it → toggled-off flag present.
4. Empty brought ∪ standing → strength pool = destination venue equipment only; all toggles off.
5. (PR-2) Overlay renders the away toggle-off line for a destination-unavailable discipline.

## 10. Gut check

- **Risk / best argument against:** this is the only place we *reverse* a documented #780 decision. If Andy considers "strength substitutions are always a home activity (the athlete drives home to lift)" the intended product semantics even during an away week, then PR-1 is wrong and we should defer. The away-week framing (multi-day expedition AR, the athlete is at the destination) says the destination gym is correct — but it's worth one explicit confirmation, since the #780 comment is deliberate, not accidental.
- **What might be missing:** the away 2C build adds one more `q_layer2c_equipment_mapper_payload` call per away segment at plan-gen time (two SQL queries each). Negligible vs. the LLM synthesis cost (Rule #16), and only on plans that actually have an away window. Flagged, not a concern.
- **Confidence:** high on the mechanism (every input confirmed in-scope; mirrors the home build exactly). The only genuine open question is the #780 semantic reversal — surfaced for Andy.

---

**End of design v1.**
