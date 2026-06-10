# X3/X4 + #509 — Race-derived discipline mix wired into both Layer 2A axes — Closing Handoff

**Session:** Shipped the final slice of the discipline-mix rewrite (X1a → X1b → X2 → **X3/X4**) and its inclusion-axis follow-up (**#509**). Both wire the same race-terrain-derived `{discipline_id: pct}` signal — X3/X4 into the **weighting** axis, #509 into the **inclusion** axis — completing the `race > athlete > bridge/curator` precedence on both.
**Date:** 2026-06-10
**Predecessor handoff:** `V5_Implementation_X2_AthleteDisciplineWeighting_2026_06_10_Closing_Handoff_v1.md` (the `main` pointer at session start)
**Branch:** `claude/elegant-lovelace-tmt93d` → PR [#520](https://github.com/ahorn885/exercise/pull/520) squash-merged to `main` (`7944ff9`); `claude/509-layer2a-inclusion-precedence` → PR [#523](https://github.com/ahorn885/exercise/pull/523) squash-merged to `main` (`fa663ad`). This handoff closes from `claude/x3x4-509-handoff-close`.
**Status:** 2 substantive files (X3/X4) + 3 substantive files (#509) across two PRs — under ceiling each. Both shipped + green on `main`. The 4-slice discipline-mix rewrite is **complete**; #509 closed.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the X2 §8 table — all green (`verify-handoff.sh` clean, working tree clean off the X2 merge tip).

| Claim | Anchor | Result |
|---|---|---|
| `_athlete_discipline_overrides` in orchestrator | grep (3 hits) | ✅ |
| `race_discipline_overrides` kwarg seam live | `layer2a/builder.py:739` + `_apply_modality_group_pooling` consumes it (precedence already built+tested) | ✅ |
| X3 boundary (terrain stripped to `terrain_id`) | `orchestrator.py:419-420` (was 372-373) | ✅ |

**Reconciliation note:** One piece of **stale planning drift** found and corrected: `CARRY_FORWARD.md`'s X3/X4 note described X4 as "merge race+athlete in the orchestrator → pass as `athlete_discipline_overrides`." That plan **predated X1b.2**, which already built the full 3-way precedence inside `_apply_modality_group_pooling` consuming a live `race_discipline_overrides` kwarg. Following the stale plan would have discarded `race_override` source attribution and duplicated precedence. Used the live seam instead (handoff §6.1 approach). Drift recorded in CARRY_FORWARD with the superseded plan struck through.

---

## 2. Session narrative

**Scope-pick gate.** Andy directed continuing from X2 into the payoff slice. Read issue **#509** first (Andy's call) before building — it reframed the work cleanly into **two axes sharing one signal**:
- **Weighting axis** (the %s): `race ?? athlete ?? bridge`. athlete+bridge live since X1b.2; **race = X3/X4**, this session.
- **Inclusion axis** (in/out/ask): `race ?? athlete ?? curator-default`. Was broken (column ignored); **= #509**, this session.

The shared seam is X3's `_derive_race_discipline_mix → {discipline_id: pct}`; both axes read it (weighting reads the values, inclusion reads the keys). Per the issue: *"both inclusion and weighting consume the same `race_discipline_overrides` signal."*

**Two PRs, deliberately.** X4 fires no stop-and-ask trigger (pure wiring of an already-specced+built+tested seam) → clean PR #520. #509 fires Trigger #3 (Layer 0→2A contract) + #4 (HITL) + #5 (the athlete-signal call) → spec-first, §5.3 rewrite + sign-off → PR #523. Bundling would have mixed a clean wiring change with a contract/HITL change.

**The one real decision (#509, pinned §7).** What is the "athlete" inclusion signal? Andy chose **Option A — the athlete's weighting is the *complete* membership list**: weighted → in, unweighted → out. Consistent with X2's all-or-nothing sum-to-100 design (weight the mix and you own the whole mix; weight nothing and defer to curator defaults). Race still wins over athlete.

---

## 3. File-by-file edits

### 3.1 `layer4/orchestrator.py` (modified — X3/X4, PR #520)
- `_derive_race_discipline_mix(target_race_event) → {discipline_id: pct}` (after `_athlete_discipline_overrides`, ~line 218) — groupby-sum `pct_of_race` over terrain rows carrying a `discipline_id`; drops race-wide (`discipline_id is None`) rows per Modality_Group_Spec §10; raw sums (downstream `_normalize_load_weights` rescales); `{}` when no event / no tagged terrain. Standalone helper so #509 reuses it.
- Threaded as `race_discipline_overrides=` at the **cone** 2A call site (`_upstream_full_cone`, ~line 351). Single-session site (`orchestrate_single_session`) is off-race by definition → unchanged.

### 3.2 `layer2a/builder.py` (modified — #509, PR #523)
- SELECT now pulls `pla.default_inclusion` (was absent — the root cause: serving never read the column).
- `_default_inclusion` (notes-text heuristic, could never emit `excluded`) **retired** → `_curator_default_inclusion(row)` reads the column; NULL / no-PLA-row → `included`. `_INCLUSION_VALUES` constant added.
- `_resolve_conditional` **replaced** by `_resolve_inclusion(row, race_overrides, athlete_overrides)` — the `race > athlete > curator-default` chain (see §7). Build-loop call site updated to pass `race_discipline_overrides`.
- `_apply_modality_group_pooling` member set scoped to `inclusion == "included"` (was all built disciplines) — under #509 Option A exclusion is common, and an excluded discipline must not contribute its bridge midpoint to a group pool.
- `_build_phase_load` None-guard + `PhaseLoadBands.default_inclusion` now key off the column.
- `team_format` is now validated-but-unused for inclusion (it already was — the retired resolver ignored it; left as a public param).

### 3.3 `aidstation-sources/Layer2A_Spec.md` (modified — #509)
- §5.2: corrected the stale "**`default_inclusion` is not a column**" claim (it is, schema v10; serving now reads it).
- §5.3: retitled "Conditional resolution" → "**Inclusion resolution (race > athlete > curator-default)**"; documents `_resolve_inclusion`; reframes the 2026-05-25 race-rule retirement note.
- §5.6: HITL now narrows — `excluded` rows stop gating; `prompt_required` still gates when unresolved.

---

## 4. Code / tests

- **X3/X4** (`tests/test_layer4_orchestrator.py`): `TestDeriveRaceDisciplineMix` (5 unit — group-sum, drop race-wide, empty cases) + `TestRaceDisciplineMixWireUp` (1 — derived mix reaches the 2A call as `race_discipline_overrides`).
- **#509** (`tests/test_layer2a.py`): `TestInclusionPrecedence` (6 — curator column honored on the 4 AR rows / NULL→included / `prompt_required` gates HITL / race beats curator-`excluded` / athlete list is authoritative (unlisted curator-included → excluded) / race beats athlete). `_row` fixture gained a `default_inclusion` param; the D-015 conditional fixture row set to `prompt_required` (column-authoritative).

**Suite: 2238 passed / 30 skipped** (`tests/`) + 185 (`etl/tests/`). CI green on both `7944ff9` and `fa663ad`.

---

## 5. Manual §5.0 verification steps

The win-condition proof is **owed** and gated on data (appended to `CARRY_FORWARD.md`):

1. Confirm Andy's PGE race event's terrain rows carry per-row `discipline_id` + `pct_of_race` (race-events form / `race_terrain` JSONB). **If they're all race-wide (`discipline_id` NULL), both X4 and #509 are inert** — allocation falls back to bridge bands (weighting) / curator defaults (inclusion).
2. With tagged terrain: re-run a cold AR plan (or `/admin/plan/<id>/inspect`) and confirm `modality_group_allocations` / per-discipline `load_weight` reflect the **race mix** (MTB-dominant ~45% per Andy's spec), and that curator-`excluded` AR disciplines (Canoeing/Snowshoeing/Mountaineering) are no longer `prompt_required` / no longer trip HITL.
3. If Andy sets discipline weights on `/profile?tab=athlete`: confirm Option A — only the weighted disciplines appear in the plan; unweighted ones are excluded (race-demanded ones still included).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move — **empirical win-condition proof**

The whole 4-slice rewrite + #509 is **built**; the one thing never verified end-to-end is whether it actually fixes plan #61's TR-dominant AR allocation. Tier-2 (validate already-shipped behavior) before more building. Steps in §5 above. **The gating unknown is the race terrain data** (per-row `discipline_id` + `pct_of_race`) — verify that first; if absent, the fix is correct but inert, and the next move becomes *capturing* that terrain→discipline tagging (race-events form / onboarding — see #342, which is exactly "athlete can associate a discipline with a race terrain without that discipline being included," now relevant since inclusion consumes it).

### 6.2 Alternative pivots
- **Layer 0 Slice 2** — `etl/migrations/layer0/` convention + first proof migration (owed from Slice 1, epic #488).
- **#296** (Layer 2A athlete weight-overrides rationale/flags unconsumed) — partially addressed by X2; the Layer-4 consumption side remains.
- Vocabulary cleanup #476/#477 (deferred behind the X-series, now shipped — unblocked).

### 6.3 Operating notes for next session
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.
- No Neon migration owed for either slice — X3/X4 is orchestrator logic; #509's `default_inclusion` column already exists (schema v10) and is populated on prod, enforced by the Slice 1 `validate_layer0` gate.
- `_derive_race_discipline_mix` is the shared seam — any future race-driven signal (e.g. #342 terrain capture) feeds both axes through it.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | X4 wires the **live `race_discipline_overrides` seam** (handoff §6.1), NOT the CARRY_FORWARD "merge into `athlete_discipline_overrides`" plan | Claude (flagged; CARRY_FORWARD plan was pre-X1b.2 stale) | The 3-way precedence is already built+tested in `_apply_modality_group_pooling`; merging would discard `race_override` provenance + duplicate precedence. |
| 2 | X3/X4 and #509 ship as **two separate PRs**, X3/X4 first | Andy | X4 fires no trigger (clean wiring); #509 fires #3+#4+#5 (spec-first, sign-off). Keeps each PR surgical. |
| 3 | #509 athlete inclusion signal = **Option A: weighting is the complete membership list** (weighted→in, unweighted→out) | Andy | Consistent with X2's all-or-nothing sum-to-100 (own the whole mix or defer). Race wins over athlete. |
| 4 | `conditional_resolution` Literal left unchanged (`athlete_opt_in` \| None); race provenance rides on `load_weight.source == "race_override"` | Claude | Avoids a contract change for a secondary diagnostics field. |
| 5 | `default_inclusion` NULL / no-PLA-row → `included` | Claude | Preserves the historical non-conditional default; the gate guarantees populated values on real PLA rows, so this only catches no-PLA-row disciplines. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_derive_race_discipline_mix` in `layer4/orchestrator.py` | ✅ grep |
| `_resolve_inclusion` + `_curator_default_inclusion` in `layer2a/builder.py`; `_default_inclusion`/`_resolve_conditional` gone | ✅ grep |
| `pla.default_inclusion` in the SELECT | ✅ grep |
| `TestInclusionPrecedence` + `TestDeriveRaceDisciplineMix` exist | ✅ grep |
| PR #520 (`7944ff9`) + #523 (`fa663ad`) merged to `main` | ✅ `git log origin/main` |
| Issue #509 closed (completed, ref #523) | ✅ |
| Suite green | ✅ 2238 passed / 30 skipped + CI |
| Working tree clean | ✅ git status |

---

## 9. Files shipped this session

**Substantive (X3/X4, PR #520 — 2 files):**
1. `layer4/orchestrator.py` (modified — `_derive_race_discipline_mix` + cone 2A wire)
2. `tests/test_layer4_orchestrator.py` (modified — 6 tests)

**Substantive (#509, PR #523 — 3 files):**
3. `layer2a/builder.py` (modified — column-authoritative inclusion + pooling scope)
4. `tests/test_layer2a.py` (modified — `TestInclusionPrecedence` + fixture)
5. `aidstation-sources/Layer2A_Spec.md` (modified — §5.2/5.3/5.6)

**Bookkeeping:**
6. `aidstation-sources/CARRY_FORWARD.md` (X3/X4 + #509 status flips)
7. `aidstation-sources/CURRENT_STATE.md` (pointer → this handoff)
8. `aidstation-sources/handoffs/V5_Implementation_X3X4_509_InclusionWeightingPrecedence_2026_06_10_Closing_Handoff_v1.md` (this file)

---

## 10. Carry-forward updates

- X3/X4 flipped ⬜→✅ (with the superseded merge-plan struck through + the live-seam correction recorded).
- #509 added as ✅ under the discipline-mix rewrite tracker.
- Win-condition empirical proof restated as the live owed item, with the **race-terrain-data gating unknown** called out explicitly.

---

**End of handoff.**
