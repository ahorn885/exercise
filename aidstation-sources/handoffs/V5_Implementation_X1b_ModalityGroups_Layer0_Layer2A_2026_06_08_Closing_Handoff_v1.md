# V5 Implementation — X1b modality groups: Layer 0 substrate (X1b.1) + Layer 2A consumer (X1b.2)

**Date:** 2026-06-08
**Branches:** `claude/x1b-modality-groups-layer0` (X1b.1), `claude/x1b2-layer2a-modality-pooling` (X1b.2)
**PRs:** [#478](https://github.com/ahorn885/exercise/pull/478) squash-merged to `main`; [#479](https://github.com/ahorn885/exercise/pull/479) squash-merged to `main`
**Predecessor handoff:** `V5_Implementation_DisciplineMix_X1a_X1b_BridgeBands_ModalitySpec_2026_06_08_Closing_Handoff_v1.md` (X1a bands rewrite + X1b spec)
**Live on Neon:** 0A-v1.5.0 / 0B-v1.5.0 / 0C-v1.5.0 — Andy-applied at 03:31 UTC

---

## ⚡ Diagnostic token

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```

`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` via the Vercel MCP `web_fetch_vercel_url` tool.

---

## 1. What this session was

Built the first 2 of 3 X1b implementation slices off `Modality_Group_Spec_v1.md` (specced in the predecessor handoff). The 3rd slice (X1b.3) is the Layer 2C + `resolve_training_substitution` filter — owed to the next session.

The cumulative arc since plan #61's TR-dominant allocation:
- **X1a (PR #475, prior session)** — bridge bands rewrite (43 of 73 Sheet 3 rows). AR MTB 10-20 → 35-55 the smoking-gun fix.
- **X1b.1 (PR #478, this session)** — Layer 0 modality groups substrate.
- **X1b.2 (PR #479, this session)** — Layer 2A consumer integration.
- **X1b.3 (next session)** — Layer 2C alternate-group-member surfacing + `resolve_training_substitution` candidate-set narrowing.
- **X2 (owed)** — wire `athlete_discipline_weighting` end-to-end.
- **X3 + X4 (owed)** — race terrain → discipline_mix derivation + precedence merge.

## 2. Shipped

### 2.1 — X1b.1 substrate (PR #478)

- **Schema** (`etl/layer0/schema.sql`): two new tables — `layer0.modality_groups` (group_id PK, group_kind closed-enum, description) + `layer0.discipline_modality_membership` (many-to-many discipline_id × group_id with optional note).
- **Source data** (`etl/sources/Sports_Framework_v13.xlsx`): two new sheets on v12 — "Modality Groups" (9 rows per spec §3.2) + "Discipline Modality Membership" (26 seeded rows covering all 24 surviving disciplines post-canon).
- **Extractors** (`etl/layer0/extractors/sports_framework.py`): `extract_modality_groups` validates `group_kind` against closed enum `{paddle, foot, bike, snow, climb, swim, nav}`; `extract_discipline_modality_membership` reads many-to-many rows.
- **Runner** (`etl/layer0/run.py`): SPORTS_XLSX bumped v12 → v13. Phase 2 inserts groups + membership after disciplines so canon-filtered membership is filtered against `disc_rows`. 3 membership rows pointing at canon-removed disciplines silently dropped (D-005, D-015, D-016 — consolidated by `normalize_dimension_rows`).
- **Validator** (`etl/layer0/validation/modality_group_orphan.py`): ERROR severity, every active discipline must have ≥1 active membership. Wired into Phase 5 + report extras.
- **SQL emit** (`etl/output/layer0_etl_v1.5.0.sql`): regenerated for Neon SQL editor compat.
- **Live on Neon (Andy-applied):** `python -m etl.layer0.run --version-tag 1.5.0` clean exit 0. 9 modality_groups + 23 memberships landed. Validators passed; expected WARNs only (5 sports' phase loads not summing to 100, 1 vocab/parse warning).

### 2.2 — X1b.2 Layer 2A consumer (PR #479)

- **Payload types** (`layer4/context.py`):
  - New `ModalityGroupAllocation` (group_id, members, pool_race/athlete/base, per_member_final, flags).
  - `Layer2APayload.modality_group_allocations: list[ModalityGroupAllocation]` — one entry per multi-member group; empty for singleton groups and for the pre-v1.5.0 no-membership state.
  - `WeightResult.source` Literal expanded with `"race_override"` so X3 can stamp redirected weights.
- **Reader** (`layer2a/builder.py:_load_modality_groups`): SELECT against `layer0.discipline_modality_membership` at the current 0A version. Returns `dict[discipline_id, list[group_id]]`. Empty result = pre-v1.5.0 substrate — `_apply_modality_group_pooling` immediately returns `[]`, behavior identical to pre-X1b.
- **Algorithm** (`layer2a/builder.py:_apply_modality_group_pooling`) — implements spec §5.1:
  - Per-discipline base weight from existing `_compute_load_weight`.
  - Group pool sums race/athlete/base for each group with ≥2 included members.
  - Per-member final assignment per precedence: race tag → athlete weighting → bridge midpoint.
  - **REDIRECT (§5.3):** race tag pointing at non-included discipline re-attributes to first included same-group member; `craft_substitution_via_group` flag emitted on the allocation.
  - Mutates `load_weight.value` + `.source` in place; returns per-group diagnostics.
- **Public entry point** (`q_layer2a_discipline_classifier_payload`): new optional `race_discipline_overrides: dict[str, float] | None = None` kwarg. X3 will wire it; default `None` preserves backwards compat for all current callers.
- **Pooling runs AFTER** `_compute_load_weight` + `_emit_coaching_flags` + `_build_training_gaps_summary`, and **BEFORE** `_normalize_load_weights`. Normalization step unchanged — same final shape on the wire.
- **Layer 2A now performs 3 DB queries** (was 2): disciplines join + modality_group membership + weekly_total_hours.

### 2.3 — Tests

- New `tests/test_layer2a_modality_groups.py` — 7 tests covering spec §13 scenarios: no-membership no-op, singleton-group skip, multi-member bridge-only, race per-member wins, REDIRECT for non-included tags, athlete-in-group, race-vs-athlete per-member precedence.
- `tests/test_layer2a.py::TestARBaseline` query-count assertion updated `2 → 3`, added membership-query assertion at `calls[1]`.
- **Full suite: 2127 passed / 16 skipped (+7 net from X1b.2 tests).**

## 3. Stop-and-asks this session

None new. X1b.1 + X1b.2 are spec-execution slices off the already-signed-off `Modality_Group_Spec_v1.md` (decisions captured in the predecessor handoff).

## 4. Owed

1. **X1b.3 — Layer 2C consumer integration (NEXT session).** Per spec §6:
   - `layer2c/builder.py`: extend `q_layer2c_equipment_mapper_payload` to surface alternate-group-member substitution candidates via `craft_substitution_via_group` coaching flag when locale equipment can't satisfy the race-craft but does satisfy a same-group member.
   - `layer2_modality/substitution.py`: `resolve_training_substitution` filters `athlete_crafts` to same-group members BEFORE handing to Layer 4 LLM. Replaces the deferred §14 escape hatch path that was relying on the LLM for craft-family reasoning. Narrows the LLM's input from "all owned crafts" to "all owned crafts in the right modality group."
   - Tests covering §13 scenario 7 (Layer 2C substitution narrowing).
2. **X2 — wire `athlete_discipline_weighting` end-to-end.** UI under Athlete tab in `templates/profile/edit.html`. Orchestrator unpack at both 2A call sites (`layer4/orchestrator.py:270-275` plan_create + `:656-660` plan_refresh). All-or-nothing UI invariant (no partial coverage).
3. **X3 + X4 — race terrain → discipline_mix + precedence merge.** Deterministic `_derive_race_discipline_mix(race_terrain)` groupby-sum (drop race-wide rows). New `_merge_discipline_overrides(race_mix, athlete_mix)` at the orchestrator's 2A call site. Pass merged dict as the `race_discipline_overrides` kwarg added in X1b.2.
4. **Cold AR plan re-run (Andy's-hands).** v1.5.0 ETL is live; X1b.2 will pool the new bridge bands across modality groups. Bridge-only (no race-spec override yet) should already shift AR allocation MTB-dominant because the new AR bridge midpoints (MTB 45 / Trek+TR ~35 / Paddle ~17.5) align with Andy's race spec. Diag check: `synthesis_metadata.layer2a.modality_group_allocations[*]` should include the `foot` and `paddle_flatwater` groups for an AR athlete.
5. **Sheet 5 Phase Load Allocation research pass** — deferred from X1a.
6. **Plan #61 quality issues** — strength discipline miscoding (#335 follow-up), intra-day same-modality rule, race-day trim, `/plans` UI gap.
7. **#476, #477** — vocabulary canon work (D-007 row cleanup, Endurance Cycling discipline-ID variant split).

## 5. Next move

Tier order (CLAUDE.md 4-tier): X1b.3 closes the modality-groups arc (substrate + 2A consumer already shipped). Then X2 wires the dead `athlete_discipline_weighting` half-built feature. Then X3+X4 plug the race-terrain → discipline_mix gap that was the original plan #61 root cause. Then the empirical proof — cold AR plan with race-spec MTB 45% landing as MTB-dominant.

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (X1b.3 / X2 / X3+X4 + plan #61 quality + Sheet 5 + #476 + #477)
4. This handoff (diag token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Modality groups schema added | `etl/layer0/schema.sql` | `grep -n "CREATE TABLE IF NOT EXISTS layer0.modality_groups\|CREATE TABLE IF NOT EXISTS layer0.discipline_modality_membership" etl/layer0/schema.sql` → both present |
| v13 xlsx has the two new sheets | `etl/sources/Sports_Framework_v13.xlsx` | `python -c "import openpyxl; print(sorted(openpyxl.load_workbook('etl/sources/Sports_Framework_v13.xlsx').sheetnames))"` → includes "Modality Groups" + "Discipline Modality Membership" |
| ETL runner points at v13 | `etl/layer0/run.py` | `grep "SPORTS_XLSX = " etl/layer0/run.py` → `SOURCES / "Sports_Framework_v13.xlsx"` |
| Orphan validator wired | `etl/layer0/run.py` + `etl/layer0/validation/modality_group_orphan.py` | `grep -n "run_modality_group_orphan" etl/layer0/run.py` → import + call in Phase 5 |
| Layer 2A pooling implemented | `layer2a/builder.py` | `grep -n "_load_modality_groups\|_apply_modality_group_pooling" layer2a/builder.py` → defined + invoked |
| ModalityGroupAllocation payload type | `layer4/context.py` | `grep -n "^class ModalityGroupAllocation\|modality_group_allocations" layer4/context.py` → defined + on Layer2APayload |
| race_discipline_overrides kwarg added | `layer2a/builder.py` | `grep -n "race_discipline_overrides" layer2a/builder.py` → in signature |
| Live on Neon at 1.5.0 (Andy-verified) | n/a | Andy's PowerShell session: `layer0.sports active: [('0A-v1.5.0', 36)]`, `layer0.exercises active: [('0B-v1.5.0', 211)]`, all 3 phases passed validation |
| Suite green | n/a | `pytest tests/ -q` → 2127 passed / 16 skipped (+7 net) |

## 7. Mechanically-applicable deferred edits

X1b.3 implementation files when ready:
- `layer2c/builder.py` — extend `q_layer2c_equipment_mapper_payload`: when a discipline's locale-equipment coverage is below threshold, look up its modality groups via `discipline_modality_membership` (read at call time or thread via 2A payload), surface alternate same-group members already covered by locale equipment as substitution candidates. Emit `craft_substitution_via_group` coaching flag with both ids.
- `layer2_modality/substitution.py` — `resolve_training_substitution(... athlete_crafts: list[str], race_craft_discipline_id: str, modality_groups: dict[str, list[str]] ...)`: filter `athlete_crafts` to disciplines sharing ≥1 modality group with `race_craft_discipline_id` BEFORE handing the candidate set to Layer 4 LLM.
- Tests `tests/test_layer2c_modality_groups.py` covering §13 scenario 7 (locale equipment can't satisfy D-010 kayak but covers D-009 packraft → D-009 surfaced as candidate).

## 8. Summary

X1b.1 substrate + X1b.2 Layer 2A consumer integration shipped to `main`. Active Layer 0 etl_version is `0A-v1.5.0` / `0B-v1.5.0` / `0C-v1.5.0` on Neon. Layer 2A now pools per-discipline `load_weight` by modality group and redistributes per the precedence rule (race > athlete > bridge), with REDIRECT semantics for race tags on non-included crafts. The architecture supports race-spec discipline overrides via a new `race_discipline_overrides` kwarg on `q_layer2a_discipline_classifier_payload` — wiring lives in X3 (still owed). Test suite **2127 passed / 16 skipped (+7 net)**.

The empirical proof — a cold AR plan running through the v1.5.0 bridge + X1b.2 pooling and producing MTB-dominant allocation — is the gating measurement before X1b.3 / X2 / X3+X4.

*End of handoff.*
