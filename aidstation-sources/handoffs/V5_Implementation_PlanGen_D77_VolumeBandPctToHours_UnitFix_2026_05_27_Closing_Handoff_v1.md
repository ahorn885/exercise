# Plan-Gen D-77 — Volume-Band Percent→Hours Unit Fix — Closing Handoff

**Session:** Investigation close. The PGE plan still failed after the block-mode `max_tokens` work — per-block synthesis was rejected with 19–24 `volume_band_below` blockers and produced clinically over-dense weeks (~14 sessions, 2/day, no rest). Tracing the volume path found the real root cause is upstream of Layer 4 entirely: the per-discipline `phase_load` bands are **percentages** but were compared/labeled as **hours**. Shipped the conversion.
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_BlockMaxTokens_SchemaViolationFix_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/layer2e-cache-key-determinism-dlKSm`
**PR:** #293
**Status:** 7 code files + 2 test files. Suite **1799 passed / 16 skipped**. **No migration** (catalog data is correct; only the code misread it). One prompt-text change (band section now labeled/valued in hours).

---

## 1. The finding (one bug, every symptom)

The Layer 2A `phase_load` bands are **percentage shares**, not hours. Confirmed by reading the source spreadsheet `etl/sources/Sports_Framework_v11.xlsx`, sheet "Phase Load Allocation": the column headers literally read `BASE Low %`, `BASE High %`, …, and the per-discipline values sum to ~100% per sport (Trail Running 12–15%, XC Cycling 20–25%, Hiking 15–20%, …). The actual hours live in a **separate** `WEEKLY TOTAL TARGET` row (`"WEEKLY TARGET HOURS: BASE: ~18 hrs"`), extracted to `layer0.phase_load_weekly_totals`.

The intended model is `discipline_hours = weekly_total_hours × (pct/100)`, bounded by the athlete's available hours (the onboarding spec is explicit: *"Available Training Hours per Week → Hard ceiling on phase load allocation"*). **But the volume path never multiplied.** `validator._rule_volume_band` compared the raw percentage (e.g. `12`) directly against actual session hours (e.g. `2.4h`), and the synthesizer prompt rendered the raw percentage labeled `hr/wk`. `phase_load_weekly_totals` was consumed **only by Layer 2E nutrition**, never by the volume path.

Consequences, all from this one mismatch:
- **`volume_band_below` on every discipline** — `2.4h < 12×0.8` fires systematically.
- **Over-prescription / token blowout** — the synthesizer read an implied ~80h/week target (each discipline's % as hours), packed ~14 sessions trying to reach it, and blew the output-token / 300s budget. The earlier `max_tokens` truncation was a *downstream* symptom of this over-dense target, not the disease.

The earlier "each discipline gets full solo volume / no total budget" theory was **wrong** — the catalog %s already sum to 100; the only defect was failing to convert them to hours.

## 2. What shipped

One shared helper, `validator.phase_volume_bands_hours(layer2a, phase, capacity_hours)`, is the single source of truth for both the validator and the synthesizer prompt:
1. `effective = min(capacity_hours, framework_weekly_total_high)` for the phase.
2. Renormalize the **included** disciplines' `phase_load` %s so their midpoints sum to 100 (fills the athlete's capacity; mirrors the existing `_normalize_load_weights`).
3. `band_hours_i = renorm_pct_i/100 × effective`.

`validator.weekly_capacity_hours(layer1)` computes `capacity = min(available, goal)` — available = Σ enabled daily-window minutes / 60; goal = `identity.weekly_hours_target`. Wired into **every** entry point that runs the rule. Absent inputs (no capacity / no weekly-total row) → `{}` → open-ended band (prior no-op behavior), so partial/legacy payloads never crash.

## 3. Code / tests

| File | Change |
| :--- | :----- |
| `layer4/validator.py` | `phase_volume_bands_hours` + `weekly_capacity_hours`; `_rule_volume_band` compares hours (per-phase cache); `ValidatorContext.capacity_hours`; removed now-dead `_phase_band_for_discipline`. |
| `layer2a/builder.py` + `layer4/context.py` | Surface `Layer2APayload.weekly_total_hours_by_phase` (2nd SELECT against `layer0.phase_load_weekly_totals`). |
| `layer4/per_phase.py` | `_format_phase_load_bands` renders real hour bands via the shared helper; passes `capacity_hours` to the validator context. |
| `layer4/plan_create.py`, `plan_refresh.py`, `race_week_brief.py` | Wire `capacity_hours` into each `ValidatorContext` (the final composed-plan pass, refresh, race-week). |
| `tests/test_layer4_validator.py` | New regression tests using **real catalog percentages** (Trail 12–15%, etc.) asserting the hour conversion + that a realistic week lands inside the band; existing boundary tests migrated to the hours model. |
| `tests/test_layer2a.py` | Asserts the second `phase_load_weekly_totals` query. |

Suite: **1799 passed, 16 skipped.**

## 4. Owed actions + manual verification

- **Prod re-run on the PGE plan is owed.** DB egress to Neon is blocked in the dev container, so this is verified by the unit/regression suite only. Re-run the PGE plan and confirm: `volume_band_below` blockers gone; `synthesize_phase: … done — accepted=True` fires per block; session density drops to a realistic shape.
- **Cache invalidation on deploy (expected).** Adding `weekly_total_hours_by_phase` to `Layer2APayload` changes `layer2a_hash` → existing per-phase cache rows orphan and re-synthesize once. Values are deterministic/catalog-derived, so this is a one-time reset, not drift.

## 5. Decisions pinned

| | Decision | Who | Rationale |
| :--- | :----- | :--- | :----- |
| **D1** | Treat the pct-vs-hours mismatch as the root cause (not a token-budget problem) | Claude + Andy | Confirmed from the source spreadsheet (`… Low %` headers; values Σ≈100). The over-prescription + token blowout are downstream of the over-dense target this produced. |
| **D2** | `effective = min(capacity, framework_total_high)`, proportional split | Andy (default) | Athlete's available/goal hours are the hard ceiling; proportional scaling preserves the catalog's periodization shape. Isolated in `phase_volume_bands_hours` — trivial to change. |
| **D3** | Renormalize included disciplines' %s to sum to 100 | Andy (default) | An athlete training a subset should fill their capacity; precedent in `_normalize_load_weights`. Isolated; flippable. |
| **D4** | Wire capacity into all 4 volume-rule entry points (not just per_phase) | Claude | They share the same bug; leaving refresh/race-week/final-pass no-oping would be incoherent. `single_session` is mode-gated off → untouched. |
| **D5** | No migration | Claude | The catalog `*_pct_*` columns are correctly named and populated; only the code misread them. |

## 6. Next session — deferred follow-ons (now better-scoped)

These were the larger "Option A/B/C" pieces; the unit fix subsumes much of the urgency:
- **Discipline taxonomy → training stimuli** (Andy's reframe): replace Hiking/Trail-Running/Orienteering with **trail running** vs **trekking** in `layer0.sport_discipline_map`, dissolving the need for stimulus clustering. Catalog/ETL change.
- **Feasibility gate (`Layer4ShapeInfeasibleError`)** — largely subsumed by the `min(capacity, …)` cap now; revisit only if a feasible-but-dense plan still needs a pre-synthesis bounce.
- **Rest-day / load-variation structure** (≥1 rest day, long single-session days) — synthesis-shape polish; prompt-body (stop-and-ask).
- **Block-mode latency levers** (thinking-budget trim / sub-week split) — likely **moot** once the over-dense target is gone; keep as defense-in-depth only if a re-run still rides the 300s cap.

## 7. Operating notes for next session

- Read order: this handoff → its predecessor → `CURRENT_STATE.md` §5.0.
- The volume model now lives in `validator.phase_volume_bands_hours` (+ `weekly_capacity_hours`). Both consumers (validator rule 1, `per_phase._format_phase_load_bands`) call it — change the formula there, not in two places.
- `phase_load` (`PhaseLoadBands`) values are **percentages**; the `*_pct_*` catalog columns are the source of truth. Don't reintroduce a raw-vs-hours comparison — `tests/test_layer4_validator.py::test_volume_band_uses_hours_not_raw_percentages` guards it.
