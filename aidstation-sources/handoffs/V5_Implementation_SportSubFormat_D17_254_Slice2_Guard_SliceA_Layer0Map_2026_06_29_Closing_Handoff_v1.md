# V5 Implementation — #254 / D-17 Sport Sub-Format Capture — Slice 2 (Layer 2A guard) + Slice A (Layer 0 map) — Closing Handoff

**Date:** 2026-06-29
**Branch:** `claude/issue-254-cd81r3`
**Issue:** [#254](https://github.com/ahorn885/exercise/issues/254) — Onboarding: map a race goal to the correct sport sub-format (D-17 Sheet 3 / Sheet 5 naming mismatch). Parent #246.
**Design:** `aidstation-sources/designs/Onboarding_SportSubFormat_D17_254_Design_v1.md` (ratified by Andy 2026-06-29).

## 0. Thread continuity — NEXT SESSION CONTINUES #254 → SLICE B

This session shipped the **design** + **slice 2** (Layer 2A guard) + **slice A** (Layer 0 `sport_sub_format_map`). **Slice B (serving/capture) is NOT done — it is the next session's work**, and it is gated on the Layer-0 apply of slice A (§6.1). Do §6.1 (apply 0033) BEFORE building slice B.

## 1. The problem (confirmed in live Layer 0 data)

Five sports name themselves **top-level** in `sport_discipline_map` + `sport_discipline_bridge` (`"Triathlon"`) but **sub-format** in `phase_load_allocation` + `phase_load_weekly_totals` (`"Triathlon (Standard / Olympic)"`): Triathlon, Skimo, Long Distance / Endurance Cycling, Canoe / Kayak Marathon, Open Water Marathon Swimming. The onboarding "Race event type" select is sourced from the bridge (top-level), so an athlete picks the bare parent → Layer 2A's PLA join finds **zero rows** → every phase-load band is NULL → a **silent no-volume plan**. AR is identical in both tables → unaffected (why this sat in the icebox).

## 2. What shipped

### Slice 2 — Layer 2A loud guard (`layer2a/builder.py`)
`q_layer2a_discipline_classifier_payload` now detects a bare sub-format parent (exactly a `_SUB_FORMAT_SPORTS` key) that loaded SDM disciplines but joined zero PLA bands, and emits an `error` `UnresolvedFlag` + forces `hitl_required` + logs (Rule #15). A correctly-resolved sub-format name carries the parenthetical and is not in the whitelist, so the guard fires only on the bug case. **Behavior change:** a mismatched onboarding now *fails loudly (HITL)* instead of silently — strictly better, but NOT the full fix (that's slice B).

### Slice A — Layer 0 `sport_sub_format_map` (the option source + curated default)
`layer0.sport_sub_format_map(parent_sport, sub_format_sport, is_default, display_label, …)`, 17 rows across the 5 parents, one `is_default` each (Triathlon→Standard/Olympic, Skimo→Individual/Team, LDC→Road/Gran Fondo, Canoe/Kayak→ICF Competition, OWMS→10km/Olympic — ratified). Migration `0033` self-validates via a DO block; a `validate_layer0` check guards against later vocab drift. **NOT registered in `orchestrator._LAYER0_TABLE_FAMILY`** — the athlete's *chosen* sub-format (stored on `race_events`, slice B) drives the plan, so the table default is a lookup, not a cached plan input → no cache-version coordination, no deploy-order coupling.

## 3. KEY FINDING — storage model reversed D1 → D1′ (two-column)

The design's original D1 stored the resolved sub-format name in `race_events.framework_sport`. Implementation surfaced that `framework_sport` is consumed **as the top-level key** by `routes/race_events.py:_disciplines_for_framework_sport` and the `_race_terrain_editor.html` discipline endpoint — both look it up in `sport_discipline_bridge` (top-level-keyed). Storing a sub-format name there returns `[]` → collapses the discipline grid + per-row terrain selects → **re-introduces the #892 data-loss bug**. Reversed (ratified) to the **two-column model (D1′)**: `framework_sport` stays top-level (all consumers untouched); a new `race_events.sport_sub_format` column holds the pick; the orchestrator composes the Layer 2A input. Smaller blast radius (one compose point vs. N strip sites).

## 4. File-by-file edits

### 4.1 `layer2a/builder.py` (modified) — slice 2
D-17 guard block before the HITL gate (`sub_format_unresolved`). `_strip_sub_format` + `_SUB_FORMAT_SPORTS` retained.

### 4.2 `tests/test_layer2a.py` (modified) — slice 2
`TestTriathlonD17`: 5-parent parametrized guard-fires + resolved-subformat-inert + parent-with-PLA-inert.

### 4.3 `etl/migrations/layer0/0033_sport_sub_format_map.sql` (new) — slice A
CREATE + 17 rows (`0A-v1.10.1`) + DO-block verify: 17 active rows; exactly-one-default per parent; every `sub_format_sport` ∈ active PLA `sport_name`; parent set == bridge-framework_sports-without-a-same-named-PLA-row (drift-proof).

### 4.4 `etl/layer0/validation/sport_sub_format_map.py` (new) — slice A
`run_sport_sub_format_map`: the same 3 invariants as the migration verify; tolerates the table's absence on a pre-0033 baseline (clean pass).

### 4.5 `etl/layer0/validate_layer0.py` (modified) — slice A
Import + `_v_sport_sub_format_map` extractor + `CHECKS` entry (now 12).

### 4.6 `etl/tests/test_validate_layer0.py` (modified) — slice A
Added `"sport_sub_format_map"` to `_clean_results()`; count 11→12; a violation-fails-gate test.

### 4.7 `aidstation-sources/specs/Layer2A_Spec.md` (modified) — slice 2
§5.1 #254 paragraph; §6 D-17 row + §12 2A-3 row → "in progress" (guard shipped; capture remaining).

### 4.8 `aidstation-sources/designs/Onboarding_SportSubFormat_D17_254_Design_v1.md` (new + revised)
Design; storage reversed to D1′; slices re-cut A/B; open questions resolved.

## 5. Code / tests validation

- `tests/test_layer2a.py` → 40 passed. `etl/tests/test_validate_layer0.py` → 15 passed. Import smoke of the new validate module OK (`CHECKS=12`).
- Migration `0033` NOT run locally (no container Neon egress + no local PG this session) — relies on the **`layer0-gate` CI job** (Postgres + genesis snapshot) to apply `0023…0033` + run `validate_layer0`. **Watch that job on the PR.**

## 6. Next session pointers

### 6.1 OWED on merge — Layer-0 ops sequence (do in this order, BEFORE slice B)
1. **`layer0-apply`** (gated; Andy one-tap `production`) — applies `0033` to prod Neon. Idempotent.
2. **`layer0-redump`** (`version` = next, e.g. `v1.10.1`) → snapshot includes `sport_sub_format_map`; then **archive the now-baked migrations** per `etl/migrations/layer0/README.md` (re-dump must be paired with folding).
3. Only then is slice B's table read live.

### 6.2 Next session — BUILD SLICE B (serving/capture)
Per design §8 "Slice B": (a) `race_events.sport_sub_format` column via `_PG_MIGRATIONS` (public; auto-applies on deploy) + backfill (D5, set default for the 5 parents where NULL); (b) thread the column through `race_events_repo.py` create/update + `RaceEventPayload`; (c) orchestrator compose — `framework_sport_for_2a = sport_sub_format or <parent default from sport_sub_format_map> or framework_sport` — at the `_resolve_planning_sport`→`q_layer2a` boundary (`layer4/orchestrator.py` ~1065/1089); (d) second `<select>` + parent→options JSON blob in `templates/onboarding/target_race.html` + `templates/profile/race_event_edit.html`, default pre-selected, shown only for the 5 parents; (e) submit wiring in `routes/onboarding.py` + `routes/race_events.py` + `_framework_sport_choices`/options helper; (f) invalidation (D6) — fire `evict_on_target_event_framework_sport_change` on a `sport_sub_format`-only change; (g) `Athlete_Onboarding_Data_Spec_v6.md` §H.2 row (design §7.4) — distinguish from the `race_format` periodization enum. Tests: helper-level (repo + orchestrator compose + options helper) per the route-test convention.

### 6.3 Operating notes (Rule #13 — read order)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this; #254). 3. `CARRY_FORWARD.md` (#254 rolling item). 4. This handoff + the design doc (§8 Slice B). 5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

- **D1′ two-column storage** (reversed from D1; ratified) — `framework_sport` top-level + new `sport_sub_format`; orchestrator composes the 2A input.
- **D2 Layer 0 defaults** (`sport_sub_format_map`, ratified "layer 0") — shipped slice A.
- **Defaults** (§2.1) — ratified; seeded in 0033.
- **Default-change propagation** — existing rows keep their stored `sport_sub_format` when the Layer-0 default later moves (athlete intent wins).
- **Not in `_LAYER0_TABLE_FAMILY`** — table default is a lookup, not a cached plan input.

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Layer 2A guard | `layer2a/builder.py` | grep `sub_format_unresolved` — guard block + HITL OR + Rule-#15 print |
| Guard tests | `tests/test_layer2a.py` | grep `test_bare_parent_flags_unresolved_and_hitl` (parametrized 5 parents) |
| Layer 0 map migration | `etl/migrations/layer0/0033_sport_sub_format_map.sql` | grep `CREATE TABLE IF NOT EXISTS layer0.sport_sub_format_map`; 17 VALUES rows; `0A-v1.10.1` |
| Validate check | `etl/layer0/validation/sport_sub_format_map.py` | `def run_sport_sub_format_map`; tolerates absent table |
| Check registered | `etl/layer0/validate_layer0.py` | grep `sport_sub_format_map` in imports + `CHECKS` |
| Check test + count | `etl/tests/test_validate_layer0.py` | grep `len(v.CHECKS) == 12` + `test_sport_sub_format_map_violation_fails_the_gate` |
| Spec in-progress | `aidstation-sources/specs/Layer2A_Spec.md` | grep `#254 resolution (2026-06-29, in progress)` |
| Tests green | (local venv) | `tests/test_layer2a.py` 40 + `etl/tests/test_validate_layer0.py` 15 |
| Layer-0 ops OWED | — | `layer0-apply` (`0033`) then `layer0-redump` — NOT yet run (§6.1) |
| Slice B OWED | — | serving/capture not started (§6.2) |

## 9. Files shipped this session

**Substantive (2 code + 2 test + 1 migration + 1 validation module + 1 spec + 1 design):**
1. `layer2a/builder.py` — D-17 guard (slice 2)
2. `tests/test_layer2a.py` — guard tests (slice 2)
3. `etl/migrations/layer0/0033_sport_sub_format_map.sql` — Layer 0 map (slice A)
4. `etl/layer0/validation/sport_sub_format_map.py` — validate runner (slice A)
5. `etl/layer0/validate_layer0.py` — register check (slice A)
6. `etl/tests/test_validate_layer0.py` — check test (slice A)
7. `aidstation-sources/specs/Layer2A_Spec.md` — §5.1/§6/§12 in-progress
8. `aidstation-sources/designs/Onboarding_SportSubFormat_D17_254_Design_v1.md` — design

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue #254 update.

## 10. Carry-forward updates

`CARRY_FORWARD.md` #254: design ratified; **slice 2 (Layer 2A guard) + slice A (Layer 0 `sport_sub_format_map`) done + merged**; storage model = two-column (D1′). **OWED on merge: `layer0-apply` 0033 + redump. NEXT: slice B (serving/capture) — gated on the apply.**
