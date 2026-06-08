# V5 Implementation — X1b.3a Layer 2C craft_substitution_via_group flag

**Date:** 2026-06-08
**Branch:** `claude/x1b3-layer2c-modality-substitution`
**PR:** [#480](https://github.com/ahorn885/exercise/pull/480) (merging this session)
**Predecessor handoff:** `V5_Implementation_X1b_ModalityGroups_Layer0_Layer2A_2026_06_08_Closing_Handoff_v1.md`
**Live on Neon:** 0A-v1.5.0 / 0B-v1.5.0 / 0C-v1.5.0 — re-applied this session (see §3)

---

## ⚡ Diagnostic token

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```

`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` via the Vercel MCP `web_fetch_vercel_url` tool.

---

## 1. What this session was

Three things, in order:

1. **Plan 62 + 63 triage** — Andy reported both new plans failed immediately with no processing time. Pulled diag for #62, root-caused to `psycopg2.errors.UndefinedTable: relation "layer0.discipline_modality_membership" does not exist`. X1b.1 schema landed in `etl/layer0/schema.sql` and the Neon-editor SQL was emitted at `etl/output/layer0_etl_v1.5.0.sql` (3958 lines, `BEGIN; … COMMIT;`, idempotent), but the prior session's "Andy-applied 03:31 UTC" had hit a non-prod branch.
2. **Reapply v1.5.0 to prod Neon** — Andy ran the emitted SQL through the Neon SQL editor on the prod-pinned branch. Plan 64 (cold AR) went `generating` then **`ready`** with 5 blocks / 50 sessions / 0 traceback. The X1b.1 substrate + X1b.2 Layer 2A consumer are now actually live on prod for the first time since their merge.
3. **X1b.3a shipped (PR #480)** — Layer 2C consumer integration for modality groups. The 2C side of spec §6: when a discipline's locale-equipment coverage is below threshold but a same-modality-group member is well-covered, surface that member as a substitution candidate via a new `craft_substitution_via_group` coaching flag.

X1b.3 was split mid-session into 3a + 3b. The 3b half (`resolve_training_substitution` filter + the `layer0.craft_discipline_aliases` substrate it needs) is owed.

## 2. Shipped (PR #480)

### 2.1 — Layer 2C extension

- **Reader** (`layer2c/builder.py:_load_modality_groups`): mirrors `layer2a/builder.py:_load_modality_groups`. Single `SELECT discipline_id, group_id FROM layer0.discipline_modality_membership WHERE etl_version = ? AND superseded_at IS NULL`. Returns `dict[discipline_id, list[group_id]]`. Empty result = pre-v1.5.0 substrate; the flag emitter no-ops.
- **Emitter** (`layer2c/builder.py:_emit_modality_group_substitution_flags`): iterates `discipline_coverage`. For each target with `coverage_pct < _LOW_COVERAGE_THRESHOLD` (0.50), looks up its modality groups, finds same-group included disciplines with `coverage_pct >= threshold`, emits one `Layer2CCoachingFlag(flag_type="craft_substitution_via_group", …)` per (target, candidate) pair. Candidate ordering deterministic (sort by `discipline_id`); shared-group selection deterministic (sort group_ids, pick first). Both ids carried in metadata; message names both crafts.
- **Wire** (`q_layer2c_equipment_mapper_payload`): membership load placed AFTER `_build_coverage` + `_emit_coaching_flags` so the new flags append after the spec §8 ones. Layer 2C now performs 5 DB queries per call (was 4): toggle defs + skill-capability toggles + discipline_info + exercises + modality_membership.
- **Literal extension** (`layer4/context.py`): `Layer2CCoachingFlag.flag_type` Literal gains `"craft_substitution_via_group"`.

**Pre-v1.5.0 back-compat:** identical to pre-X1b.3 — empty membership table → zero new flags. Existing `tests/test_layer2c.py` and `tests/test_layer2c_prep.py` did not need any update.

### 2.2 — Tests

New `tests/test_layer2c_modality_groups.py` — 6 tests covering §13 scenario 7 plus the variant matrix:

1. `TestNoMembership` — empty membership table → no flags emitted (pre-v1.5.0 back-compat).
2. `TestSubstitutionCandidateSurfaced` — §13 scenario 7 canonical: D-010 (kayak) coverage 0%, D-009 (packraft) coverage 100%, both in `paddle_flatwater` → one flag with both ids in metadata, message names both crafts.
3. `TestBothLowNoCandidate` — both group members below threshold → no candidate, no flag.
4. `TestDifferentGroupsNoFlag` — low target + high candidate but different modality groups → no flag.
5. `TestMultipleCandidates` — D-010 low + D-009 high + D-011 high all in `paddle_flatwater` → 2 flags, candidates sorted by id.
6. `TestTargetNotInMembership` — target discipline absent from membership map → no flag (legitimate per spec §4 "Discipline in included_discipline_ids but in zero groups: legitimate (e.g., D-015 Orienteering). Treated as its own singleton pool. NO error").

Uses the `_FakeConn` pattern from `tests/test_layer2c.py` extended with a `_membership_batches` queue pattern-matched on `discipline_modality_membership` SQL — same precedent as the existing `skill_capability_toggles` pattern-match.

**Full suite:** `pytest tests/ -q` → **2133 passed / 16 skipped** (+6 net from X1b.3a; X1b.2 baseline was 2127).

### 2.3 — Empirical proof (plan 64)

The Neon reapply + the X1b.2 pooling code that was already deployed produced a `ready` plan in one cold run after the fix. Block timing: Base:w1 212s / Build:w1 192s / Build:w2 202s / Peak:w1 207s / Taper:w1 89s — 1 retry on the first four (Engine A behavior, no `cap_hit` on Taper). The X1b.3a code itself is not exercised by plan 64 because Andy's locale presumably has all required gear; the new flag fires when locale equipment can't cover a target discipline. Empirical proof of X1b.3a awaits a locale with deliberate gear gap.

## 3. Stop-and-asks resolved this session

Two:

1. **The `resolve_training_substitution` craft-name vs discipline-id gap.** Spec §6 says "filter `athlete_crafts` to those in the same group(s)" — but `athlete_crafts` is free-text (`Literal["kayak", "canoe", "packraft", "surfski"]` for paddle; subset of EQUIPMENT_CATEGORIES for bike) and modality membership is keyed on `discipline_id`. No code-side mapping exists. Andy chose **Option (3): build a `layer0.craft_discipline_aliases` table** (ETL-loaded; proper layer0 surface). Defers the substitution-filter implementation to X1b.3b.
2. **5-file ceiling pressure on full X1b.3.** Full X1b.3 (Layer 2C + craft alias substrate + substitution filter + orchestrator wire + tests) is 8–10 substantive files. Andy chose **split into 3a + 3b**. This session ships 3a (3 substantive files); 3b is owed next session.

## 4. Owed

1. **X1b.3b — craft alias substrate + substitution filter (NEXT session).**
   - **Schema:** `etl/layer0/schema.sql` — new `layer0.craft_discipline_aliases (craft_name TEXT, discipline_id TEXT, group_kind TEXT, etl_version TEXT, ...)` with `UNIQUE (craft_name, etl_version)`.
   - **Source data:** `etl/sources/Sports_Framework_v14.xlsx` — new sheet "Craft Discipline Aliases" with rows: `kayak → D-010, paddle`; `canoe → D-011, paddle`; `packraft → D-009, paddle`; `surfski → D-010, paddle` (or its own if added); plus bike: `road bike → D-006, bike`; `mtb → D-008, bike`; `gravel bike → D-006, bike` (forward-pointer for the D-006 split per spec §3.2). Andy ratifies the bike side at session start (`bike_types_available` is `subset of EQUIPMENT_CATEGORIES['Cycling Equipment']` per `athlete.py:286` — needs auditing for which strings are in play).
   - **Extractor:** `etl/layer0/extractors/sports_framework.py` — `extract_craft_discipline_aliases`. Validate `discipline_id` exists in the canon, `group_kind` matches a value from `modality_groups.group_kind`.
   - **Runner:** `etl/layer0/run.py` — Phase 2 insert after disciplines + membership.
   - **SQL emit:** regenerate to `etl/output/layer0_etl_v1.6.0.sql`.
   - **Substitution filter** (`layer2_modality/substitution.py`): add `modality_groups: dict[str, list[str]] | None = None` + `craft_discipline_aliases: dict[str, str] | None = None` kwargs. When both supplied, for each `block` with `block.discipline_id` in `modality_groups`, filter `candidate_training_crafts` to crafts whose alias maps to a discipline sharing ≥1 group with `block.discipline_id`. Emit `craft_substitution` flag when filtered set differs from raw. Emit `craft_unavailable` when filtered set is empty.
   - **Orchestrator wire** (`layer4/orchestrator.py:436-443`): load both maps once at the upstream cone, thread to `resolve_training_substitution`.
   - **Tests:** `tests/test_layer2_substitution.py` extension (filter narrowing scenarios), `tests/test_layer2c_modality_groups.py` cross-cutting if needed.
   - **Live owed:** Andy's-hands `python -m etl.layer0.run --version-tag 1.6.0` (or paste `etl/output/layer0_etl_v1.6.0.sql` into the Neon SQL editor on the prod branch).
2. **X2 — wire `athlete_discipline_weighting` end-to-end.** Profile UI in `templates/profile/edit.html`; orchestrator unpack at both 2A call sites (`layer4/orchestrator.py:270-275` plan_create + `:656-660` plan_refresh); all-or-nothing UX. Carry-forward from X1b.2 handoff.
3. **X3 + X4 — race terrain → discipline_mix + precedence merge.** Wires the `race_discipline_overrides` kwarg X1b.2 added to `q_layer2a_discipline_classifier_payload`.
4. **Empirical proof of X1b.3a flag firing** — cold plan on a locale with a gear gap (e.g. no kayak gear but Andy has packraft). Diag's `synthesis_metadata.layer2c.coaching_flags` should include a `craft_substitution_via_group` row.
5. **Plan 64 inspection** — confirm the X1b.2 empirical-proof check (`synthesis_metadata.layer2a.modality_group_allocations[*]` should include `foot` and `paddle_flatwater` groups; allocation should be MTB-dominant per Andy's race spec). The diag JSON does not surface this; needs `/admin/plan/64/inspect`.
6. **Plan #61 quality issues** — strength miscoding (#335 follow-up), intra-day same-modality rule, race-day trim, `/plans` UI gap. Unchanged from X1b.2 handoff.
7. **#476, #477** — vocabulary canon work (D-007 row cleanup, Endurance Cycling discipline-ID variant split). Unchanged.
8. **Sheet 5 Phase Load Allocation research pass** — deferred from X1a. Unchanged.

## 5. Next move

Tier order (CLAUDE.md 4-tier): X1b.3b closes the X1b arc started in PR #478/#479. Then X2 wires the dead `athlete_discipline_weighting` half-built feature. Then X3+X4 plug the race-terrain → discipline_mix gap. Then the empirical proof (4 + 5 above).

### 5.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (X1b.3b / X2 / X3+X4 + plan #61 quality + Sheet 5 + #476 + #477)
4. This handoff (diag token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Literal extended with new flag | `layer4/context.py` | `grep -n "craft_substitution_via_group" layer4/context.py` → in `Layer2CCoachingFlag.flag_type` Literal list |
| Layer 2C reader added | `layer2c/builder.py` | `grep -n "_load_modality_groups\|_emit_modality_group_substitution_flags" layer2c/builder.py` → both defined + invoked from `q_layer2c_equipment_mapper_payload` |
| Membership SELECT runs after coverage | `layer2c/builder.py` | `grep -n "membership = _load_modality_groups" layer2c/builder.py` → after `_build_coverage` + `_emit_coaching_flags` calls |
| New test file present | `tests/test_layer2c_modality_groups.py` | `pytest tests/test_layer2c_modality_groups.py -q` → 6 passed |
| v1.5.0 actually live on Neon prod | n/a | Plan 64 diag returns `"generation_status":"ready"`, `total_sessions: 50`, no traceback. Pre-fix plans 62/63 showed `UndefinedTable: layer0.discipline_modality_membership`. |
| Suite green | n/a | `pytest tests/ -q` → 2133 passed / 16 skipped (+6 net) |
| PR merged | n/a | `gh pr view 480 --json state` → `MERGED` (this session) |

## 7. Mechanically-applicable deferred edits

### X1b.3b — substitution filter signature

Add to `layer2_modality/substitution.py:resolve_training_substitution`:

```python
def resolve_training_substitution(
    *,
    terrain_by_discipline: list[Layer2BDisciplineBlock],
    athlete_crafts: list[str],
    etl_version_set: dict[str, str],
    discipline_names: dict[str, str] | None = None,
    fidelity_floor: float = _UNTRAINABLE_FIDELITY_FLOOR,
    low_fidelity_threshold: float = _LOW_FIDELITY_THRESHOLD,
    # X1b.3b additions:
    modality_groups: dict[str, list[str]] | None = None,
    craft_discipline_aliases: dict[str, str] | None = None,
) -> TrainingSubstitutionPayload:
```

Filter logic (per spec §6 — apply per discipline block, replacing `candidate_crafts = sorted(set(athlete_crafts))` line):

```python
if modality_groups and craft_discipline_aliases:
    target_groups = set(modality_groups.get(block.discipline_id, []))
    filtered_crafts = [
        c for c in candidate_crafts
        if target_groups & set(modality_groups.get(craft_discipline_aliases.get(c, ""), []))
    ]
    if filtered_crafts != candidate_crafts:
        flags.append(TrainingSubstitutionFlag(flag_type="craft_substitution", ...))
    if not filtered_crafts:
        flags.append(TrainingSubstitutionFlag(flag_type="craft_unavailable", ...))
    block_candidates = filtered_crafts
else:
    block_candidates = candidate_crafts
```

(The `flag_type` Literal in `layer4/context.py:TrainingSubstitutionFlag` likely already carries `craft_substitution` + `craft_unavailable` — verify at implementation time.)

### Orchestrator wire (`layer4/orchestrator.py:436-443`)

```python
training_substitution_payload = resolve_training_substitution(
    terrain_by_discipline=layer2b_payload.terrain_by_discipline,
    athlete_crafts=_collect_athlete_crafts(layer1_payload),
    etl_version_set=etl_version_set,
    discipline_names={
        d.discipline_id: d.discipline_name for d in layer2a_payload.disciplines
    },
    # X1b.3b additions — load once at cone construction:
    modality_groups=_q_modality_groups(db, etl_version_set["0A"]),
    craft_discipline_aliases=_q_craft_discipline_aliases(db, etl_version_set["0A"]),
)
```

The two new readers are 1-query each, both filterable on `etl_version` + `superseded_at IS NULL`. Pattern matches `_q_locale_equipment_pool` shape.

## 8. Summary

X1b.3a Layer 2C `craft_substitution_via_group` flag shipped to `main` via PR #480. Three substantive files: `layer4/context.py` (Literal extension), `layer2c/builder.py` (reader + emitter + wire), `tests/test_layer2c_modality_groups.py` (new, 6 tests). Layer 2C now performs 5 DB queries per call (was 4). Test suite **2133 passed / 16 skipped (+6 net)**.

Also resolved this session: the X1b.1 substrate was not actually live on prod Neon — the prior session's apply hit a non-prod branch. Reapplied via `etl/output/layer0_etl_v1.5.0.sql` through the Neon SQL editor on the prod branch. Plan 64 (cold AR) went `ready` with 5 blocks / 50 sessions. The X1b.2 Layer 2A pooling is now actually executing on prod for the first time.

X1b.3b (substitution filter + `layer0.craft_discipline_aliases` substrate) is owed next session. Mechanically-applicable edits captured in §7.

*End of handoff.*
