# V5 Implementation — Layer 0: Open item E (live 2B/2C version-discovery bug) + `etl/migrations/layer0/` convention

**Date:** 2026-06-11
**Branch:** `claude/pensive-wozniak-uvw1hi` · **PR [#521](https://github.com/ahorn885/exercise/pull/521)** (2B/2C fix) + **PR [#533](https://github.com/ahorn885/exercise/pull/533)** (migrations convention) · **Epic [#488](https://github.com/ahorn885/exercise/issues/488)** · closed **[#476](https://github.com/ahorn885/exercise/issues/476)**

## 1. What this session was

Picked up the Layer 0 xlsx→DB migration from the Slice 1 (`validate_layer0` gate) handoff. The next move was the `etl/migrations/layer0/` convention + first proof migration, gated on **Open item E** ("confirm nothing downstream assumes Layer 0 versions only advance via a full ETL run" — Trigger #3). Investigating Open item E surfaced a **live serving bug**, which became the first deliverable; then the migration convention itself.

## 2. Open item E → the live 2B/2C bug → PR #521 (merged `32e55fd`)

**Finding.** `_q_current_etl_version_set` (`layer4/orchestrator.py`) discovered the Layer 0 version set by reading **only** `layer0.sports` and broadcasting its `0A-`prefixed version to all three family keys (its own docstring: "v1 approximation … promote to per-sub-arc when independent versioning ships"). Andy confirmed via prod query that the live DB stores **family-prefixed** versions:

```
sports        0A-v1.6.7
exercises     0B-v1.6.7
terrain_types / body_parts   0C-v1.6.7
```

Layer 2B and 2C **exact-match** `etl_version` (`WHERE etl_version = ?` / `= ANY(?)`), so the broadcast `0A-`prefixed string matched **zero** `0B-`/`0C-`prefixed rows: **terrain (2B) and the exercise/equipment pool (2C) were resolving empty in production** — degraded silently because both fail soft to empty (plans still reached `ready`, with no terrain analysis and an empty exercise pool). Layer 2A was unaffected (it queries 0A tables with the 0A string). The contradiction that flushed it out: `insert_versioned`'s supersede uses `etl_version LIKE '0A-v%'` (requires family prefixes) while the broadcast requires uniform versions — both can't hold, so one subsystem was mis-serving; the prod query showed it was serving.

**Fix.** `_q_current_etl_version_set` now reads each family's own highest active version from a representative table (`sports`/0A, `exercises`/0B, `terrain_types`/0C) — no broadcast. Repairs the live bug **and** clears Open item E: a single-family migration is now *observable* to cache invalidation and routes the builders to the right version. Regression guard `tests/test_layer4_orchestrator.py::TestQCurrentEtlVersionSet`. Suite green (2235 / 30 at merge time). One-time full cache invalidation on deploy (cache key shape changed; correct, since it held the poisoned empty payloads).

## 3. `etl/migrations/layer0/` convention + first proof migration → PR #533 (merged `8bd0691`)

The DB-native authoring loop (design §6 phase 3):

- **`etl/migrations/layer0/README.md`** — the convention: `NNNN_<slug>.sql` naming, the §5.1 edit flow, the row-invalidation versioning model, and the **two edit shapes**: *cache-neutral structural edit* (no version bump) vs *serving-relevant edit* (bump the family version → re-stamp the whole family, ~14 tables for 0A; documented as a template, **not yet exercised**, to be made surgical by slice 3b).
- **`etl/migrations/layer0/0001_remove_triathlon_d007_noop_rows.sql`** — first proof migration (#476). Supersedes the **zero-weight Triathlon × D-007 (TT-bike)** rows in `sport_discipline_bridge` (1), `sport_discipline_map` (1), `phase_load_allocation` (4). **Verified D-007 is NOT junk first:** it stays a real discipline (its `disciplines` row, a real 95–100% band under "Long Distance / Endurance Cycling", both `discipline_substitutes`, the D-007→D-002 pairing, modality membership, `cycling_trainer` craft alias). Only the 0.0/0.0 Triathlon pointers go — cache-neutral, no version bump.
- **`.github/workflows/ci.yml`** — the `layer0-gate` job now applies `etl/migrations/layer0/*.sql` (sort -V) **after** the genesis snapshot, then runs `validate_layer0`. The gate went green applying `0001` — the migration applies cleanly and stays integrity-valid. (Container has no Postgres, so CI is where apply+gate run, per Slice 1.)

## 4. Owed / next move

1. **Andy's-hands:** apply `etl/migrations/layer0/0001_remove_triathlon_d007_noop_rows.sql` in the Neon SQL editor (CARRY_FORWARD owed-deploys). No version bump, so no cache impact. *Independently:* #521's per-family fix needs a cold-plan live check — terrain should now resolve non-empty and the exercise pool real (and may quiet the recent 2B/2C-flavored plan-quality complaints).
2. **Slice 3b (next session):** the per-table version-resolution re-architecture (Andy's "re-architect the lookup" call). Change serving to resolve `etl_version` per-table instead of per-family, so a serving-relevant migration bumps only the changed table — no ~14-table family re-stamp. ~20 builder query sites + the version-set discovery + cache + tests. Then update the README's serving-relevant-edit recipe.
3. **Phase 4** (design §6): freeze the extractors + remaining workbooks once 2–3 migrations have gone through; **DB→xlsx export** (decision B).

## 5. Stop-and-ask status

None pending. The two Trigger #3 calls this session (the per-family fix, the migration convention's edit-shape model) were signed off by Andy before implementing.

### 5.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. Then read epic #488 + `Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` (§5.3 + §8 record the Open item E resolution) before slice 3b.

## 7. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Per-family version discovery | `layer4/orchestrator.py` | `def _q_current_etl_version_set` → `representatives = (` (3 entries, no broadcast) |
| 2B/2C fix regression guard | `tests/test_layer4_orchestrator.py` | `class TestQCurrentEtlVersionSet` |
| Migration convention | `etl/migrations/layer0/README.md` | "Two edit shapes" + `NNNN_<slug>.sql` |
| First proof migration | `etl/migrations/layer0/0001_remove_triathlon_d007_noop_rows.sql` | 3× `UPDATE … SET superseded_at = now()`; `discipline_id = 'D-007'` |
| Gate applies migrations | `.github/workflows/ci.yml` | `Apply Layer 0 migrations` step (after snapshot, before `validate_layer0`) |
| Open item E resolved | `aidstation-sources/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` | §8 "Open item E … RESOLVED 2026-06-10" + §5.3 |
| #476 closed | GitHub | issue #476 closed `completed` (PR #533 / migration 0001) |

## 8. Summary

Open item E was not a clean pass — it surfaced a live Layer 2B/2C empty-result bug (`_q_current_etl_version_set` broadcasting `layer0.sports`'s `0A-` version to the 0B/0C keys against a family-prefixed prod DB). Fixed by per-family version discovery (#521), which both repairs serving and clears the migration prerequisite. The `etl/migrations/layer0/` authoring loop is now established and CI-proven (#533): reviewed SQL migrations stack on the frozen genesis snapshot, are integrity-gated before Neon, and the first proof migration (#476) cleanly retired the zero-weight Triathlon×D-007 pointers. Next: slice 3b — per-table version resolution, so serving-relevant edits stop re-stamping whole families.
