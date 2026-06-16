# V5 Implementation — #648 Standing exercises-FK validator for `validate_layer0` — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/layer0-exercises-fk-validator-648`
**New file:** `etl/layer0/validation/exercises_fk_check.py`
**PR:** _(opened this session — see GitHub; auto-merges on green)_
**Predecessor handoff:** `handoffs/V5_Implementation_Locations_CullTechnicalSkill_644_2026_06_16_Closing_Handoff_v1.md` (#644, PRs #647/#650).

Session opened on the #644 closing handoff ("V5_Implementation_Locations_CullTechnicalSkill_644… let's work!"). Rule #9 sweep clean (handoff anchors all ✅; tree clean). #644 + #623 confirmed closed completed (PR #650 merged). Andy chose **#648** (exercises-FK validator) over #619 (Locations/nav IA) and the T3-refresh re-verify, via `AskUserQuestion`.

---

## 1. What shipped — #648

### The gap (found during #644)
`validate_layer0` FK-checks **only the disciplines family** (`etl/layer0/validation/fk_checks.py` — `discipline_substitutes`, `discipline_training_gaps`). **Nothing validated the exercises graph.** There was no check that, for active `layer0.exercises`:
- `progression_exercise_id` (when set) resolves to an active exercise,
- `regression_exercise_id` (when set) resolves to an active exercise,
- each `physical_proxies[].exercise_id` resolves to an active exercise,
- each active `sport_exercise_map.exercise_id` resolves to an active exercise.

(`vocab_alignment.py` checks only `sport_exercise_map.sport_name` vs the bridge and `exercises.contraindicated_parts` vs `body_parts` — not exercise_id refs.)

**Why it matters:** retiring/superseding an exercise can orphan a *kept* exercise still pointing at it. The 2C/2D readers filter `e.superseded_at IS NULL` on the **direct** exercises join (`layer2c/builder.py` ~L298, `layer2d/builder.py` ~L872), so a stale `sport_exercise_map` row goes inert on its own — but a dangling `physical_proxies`/progression/regression ref on an **active** row would surface (Tier-3 proxy resolution / progression-regression display) and the gate would not catch it. The cull migrations `0007`/`0008`/`0009` each **hand-rolled** these FK assertions in their own DO-block (fragile — the next migration author has to remember).

### The build (1 substantive new file + 2 edits)
- **`etl/layer0/validation/exercises_fk_check.py`** (NEW) — `run_exercises_fk(conn)`:
  - loads the active-exercise id set once (`SELECT exercise_id FROM layer0.exercises WHERE superseded_at IS NULL`),
  - scans active exercises for non-empty `progression_exercise_id` / `regression_exercise_id` not in that set,
  - unnests `physical_proxies` (`jsonb_array_elements`, guarded `jsonb_typeof(...) = 'array'`) and checks each `exercise_id`,
  - scans active `sport_exercise_map` rows whose `exercise_id` is not in the set,
  - returns the standard `{rows_checked, pass_count, error_count, errors}` shape; each error carries `{ref_kind, holder, holder_name, missing_id}`.
- **`etl/layer0/validate_layer0.py`** — import `run_exercises_fk`; add `_v_exercises_fk` extractor (Violation id `"{ref_kind}:{holder}->{missing_id}"`, fix-not-waive); register `Check("exercises_fk", …)` **3rd in `CHECKS`** (after the two disciplines FK checks). Registry is now **11 entries**.
- **`etl/tests/test_validate_layer0.py`** — `exercises_fk` added to `_clean_results()`; registry-count assertion 10→**11** (+`"exercises_fk" in names`); new `test_dangling_exercise_ref_fails_the_gate`; `_v_exercises_fk` id/detail assertions in `test_extractors_produce_expected_ids`.

### The validator immediately caught real corruption → migration `0010`
The validator runs wherever `validate_layer0` runs — the **CI `layer0-gate`** (baseline + `0006`–`00NN`, `python -m etl.layer0.validate_layer0`, driven by the `CHECKS` registry → **no workflow change**) and the **nightly `layer0-validate-live`** vs live prod.

Its **first gate run failed — for the right reason.** It found **11 dangling references** the #644 verification never saw (that check scanned only refs *into the cull set*; this scans the whole graph). **10 active exercises reference 5 exercise_ids that were never created** (phantom progression/regression/`physical_proxies` targets named during curation but never added as real entries; their names don't resolve to any real exercise under another id either — several carry a coaching note baked into the "name"):

| Phantom id | Name | Referenced by | Ref kind |
|---|---|---|---|
| EX059 | Neck Isometric Hold | EX057, EX058, EX069, EX140, EX158 | physical_proxy ×5 |
| EX193 | Shooting Breath Control & Stance | EX139, EX194 (proxy); EX194 (regr) | proxy ×2 + regression |
| EX141 | Wetsuit Swimming Technique | EX176 | regression |
| EX147 | Loose Surface Threshold Braking | EX184 | regression |
| EX204 | On-Water Boat Balance Drill | EX200 | progression |

**Decision (Andy via `AskUserQuestion`, 2026-06-16): STRIP all 11** (over authoring the missing exercises — Trigger #2 padding, and most names are non-exercise cues; no valid id to repoint to).

- **`etl/migrations/layer0/0010_strip_dangling_exercise_refs.sql`** — supersede + reinsert the 10 active holders at `0B-v1.6.10`→`0B-v1.6.11` with the phantom `physical_proxies` elements removed (order preserved; non-array/NULL preserved) and any phantom `progression`/`regression` id+name cleared to NULL. Serving-relevant edit (proxies feed Tier-3; progression/regression feed display) — same supersede+reinsert/digest-bump pattern as `0007`/`0008`/`0009`. Atomic DO-block RAISEs unless **0** active exercises reference a phantom AND exactly **10** rows are reinserted at `0B-v1.6.11`. Idempotent (reinsert guarded to phantom-bearing rows not already at the bumped version). **NO DDL, no `LAYER4_PROMPT_REVISION` bump** (data-only; cache rides the `0B` digest).

The gate goes green once `0010` applies in the `layer0-gate` (it strips the refs before the validator runs). Per-migration DO-blocks are now a redundant belt rather than the only guard.

### Not a Stop-and-ask Trigger
Hardening only — no vocab/exercise-DB entry (Trigger #2), no prompt body (Trigger #1), no cross-layer contract / cache-key change (Trigger #3). Executed directly.

### Verification
- **`etl/tests/` 90 passed** (was 89; +1 the dangling-ref gate test). Unit tests feed synthetic validator-result dicts through the pure `evaluate`/extract/waiver path (no DB) — the validators' live SQL is exercised by the `layer0-gate` CI job.
- Container has the **psql client only** (no local PG server) → **CI is the authoritative live-DB gate** (same constraint as the #644 session). The SQL mirrors `0009`'s proven DO-block column refs (`progression_exercise_id`/`regression_exercise_id`/`physical_proxies`→`exercise_id`/`sport_exercise_map.exercise_id`).

---

### Apply-model bug found + fixed (apply-ledger)
The first `layer0-apply` run (after #651 merged) **failed re-applying `0008`**: `0008: expected 4 non-retired survivor tokens, found 2`. Root cause is the **apply model, not `0008`'s data**: `layer0-apply` re-applied the *entire* `0006`→`0010` chain every run, but each migration's atomic verify-block asserts the state right after **itself**, which a later migration legitimately moves on:
- `0008` pins EX150/EX153 keeping survivor tokens → `0009` superseded them (snowshoe cull) → `0008` re-run finds 2, fails.
- `0009` pins EX176 at `0B-v1.6.10` → `0010` re-versions it to `0B-v1.6.11` → `0009` re-run would fail next.

The CI `layer0-gate` never sees this — it applies the chain in-order from a clean baseline, so every verify runs *before* the migration that invalidates it. The bug only bites a re-apply against a prod that already has the later migrations.

**Fix (Andy via `AskUserQuestion`): apply-ledger** — apply each migration exactly once, ever (mirrors the public-schema `_PG_MIGRATIONS` runner):
- **`etl/migrations/layer0/_apply_ledger.sql`** (NEW bootstrap) — `CREATE TABLE IF NOT EXISTS layer0._applied_migrations(filename PK, applied_at)` + one-time seed of `0006`–`0009` (already live pre-ledger) via `ON CONFLICT DO NOTHING`. Idempotent.
- **`.github/workflows/layer0-apply.yml`** — runs the bootstrap first, then loops `[0-9]*.sql`: skip if in the ledger, else apply and record (recorded only after a clean `psql -f`, so a failed migration is not marked). The data UPDATEs stay idempotent regardless.
- **`.github/workflows/ci.yml`** — gate glob narrowed `*.sql`→`[0-9]*.sql` so the underscore-prefixed bootstrap is apply-time infra only, never a gate migration.

(Note: a future `layer0-redump` captures `layer0._applied_migrations` in the baseline → add it to `_FAMILY_MAP_EXCEPTIONS` like `supplement_vocabulary`/`discipline_technique_foci`. Flagged in the bootstrap comment.)

## 2. #648 — DONE (applied + verified + closed)
- **`0010` applied to prod** via `layer0-apply` ([run 27623585346](https://github.com/ahorn885/exercise/actions/runs/27623585346)) — the apply-ledger seeded `0006`–`0009`, **skipped all four**, and applied **only `0010`** (`0010: OK — 11 dangling phantom refs stripped across 10 active exercises; reinserted at 0B-v1.6.11`), then recorded `0010` in the ledger.
- **Verified** via read-only `neon-query` ([run 27624398459](https://github.com/ahorn885/exercise/actions/runs/27624398459)): `dangling_prog=0, dangling_regr=0, dangling_proxy=0, holders_at_bump=10, ledger_rows=5`.
- **#648 CLOSED completed.** PRs #651 (validator + `0010`) and #653 (apply-ledger, closes #652) both merged.

## 3. Side-findings
- **The #644 verification's "0 dangling refs" was scoped to the cull set only** — the whole-graph scan this validator added found 11 pre-existing phantom refs that predate the cull. Worth remembering: a targeted neon-query verification proves the targeted claim, not graph-wide integrity. The standing validator now covers the gap.

## 4. NEXT STEPS — "Locations & Gear" arc
- **[#619](https://github.com/ahorn885/exercise/issues/619)** — profile Locations tab + nav/profile IA cleanup (sidebar reorg, profile tabs, supplements tab, Schedule-tab theming, Sources ~3-per-row). Pure UI/IA, `priority:med`. Multi-item — likely splits into slices.
- **Carried (unrelated):** post-#572 live **T3 *refresh*** re-verify (Rule #14 — needs Andy's live hands + diag token).

## 5. Bookkeeping done this session
- **`CURRENT_STATE.md`:** #648 "Last shipped session" entry (names this handoff + the new validator file); #644 demoted to predecessor.
- **GitHub:** #648 commented + **closed completed** on merge (PR ref). New PR opened (auto-merge on green).
- **`CARRY_FORWARD.md`:** no edit.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Validator | `etl/layer0/validation/exercises_fk_check.py` | `def run_exercises_fk(conn)`; `_load_active_exercise_ids`; checks progression/regression/`physical_proxies`/`sport_exercise_map`; returns `{rows_checked, pass_count, error_count, errors}` |
| Wiring | `etl/layer0/validate_layer0.py` | `from etl.layer0.validation.exercises_fk_check import run_exercises_fk`; `_v_exercises_fk` extractor; `Check("exercises_fk", run_exercises_fk, _v_exercises_fk)` 3rd in `CHECKS` (11 entries) |
| Tests | `etl/tests/test_validate_layer0.py` | `"exercises_fk"` in `_clean_results()`; `len(v.CHECKS) == 11`; `test_dangling_exercise_ref_fails_the_gate`; `_v_exercises_fk` id `physical_proxy:EX176->EX094` |
| Migration | `etl/migrations/layer0/0010_strip_dangling_exercise_refs.sql` | `_phantom_ids` = EX059/EX141/EX147/EX193/EX204; supersede+reinsert 10 holders at `'0B-v1.6.11'` with phantom proxy elems removed + phantom prog/regr cleared; DO-block RAISEs unless 0 dangling refs + 10 reinserted |
| Apply-ledger | `etl/migrations/layer0/_apply_ledger.sql`, `.github/workflows/layer0-apply.yml`, `.github/workflows/ci.yml` | `layer0._applied_migrations` ledger seeded `0006`–`0009`; apply loop applies `[0-9]*.sql` once each (skip if recorded); CI gate glob `[0-9]*.sql` excludes the bootstrap |
| Precedent | `etl/layer0/validation/primary_movement_check.py` | fix-not-waive validator wired into `validate_layer0` (the `0006` pattern this mirrors) |
| FK gap (now closed) | `etl/layer0/validation/fk_checks.py` | was disciplines-family only; the exercises-FK gap #648 tracked is now covered by the new check |
| CI gate | `.github/workflows/ci.yml` (`layer0-gate`) | baseline + `0006`–`0010`, `python -m etl.layer0.validate_layer0` — new check runs via the registry, no workflow edit; first run RED surfaced the 11 phantom refs, green once `0010` applies |
| Tests run | — | `etl/tests/` 90 passed (container: psql client only → CI is the authoritative live-DB gate) |
| Prod apply | — | `layer0-apply` run 27623585346 (ledger skipped 0006–0009, applied only 0010); `neon-query` run 27624398459 → `0 / 0 / 0 / 10 / 5` |
| Issue #648 | — | CLOSED completed (0010 applied + verified) |
| Issue #652 | — | NEW — apply-model bug; CLOSED via #653 (apply-ledger) |
| Owed | — | none on #648; carried: post-#572 live T3-refresh re-verify (Rule #14) |
