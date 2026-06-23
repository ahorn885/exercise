# V5 Implementation — #884 Unified Gear/Craft Model — Slice 1 Prod-Apply + Genesis Baseline Fold — Closing Handoff

**Date:** 2026-06-23
**Baseline branch:** `claude/layer0-baseline-v1.9.0` (redump Action output + the fold)
**Session branch (this bookkeeping):** `claude/bold-heisenberg-uoepcg`
**PR:** #915 (MERGED — squash `461be8c`) — refresh genesis baseline to v1.9.0 + fold `0006–0022`.
**Predecessor:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_Slice1_GearToggleCatalog_2026_06_23_Closing_Handoff_v1.md` (the `0022` migration build, PR #914 merged).
**Issue:** #884 (go-live blocker; unified gear/craft model). Commented with the deploy + finding.

Completed the slice-1 OWED deployment: applied migration `0022` to prod, then refreshed + reconciled the Layer 0 genesis baseline. Surfaced and fixed a latent flaw in the redump process (the re-apply-on-a-converged-baseline hazard).

---

## 1. What shipped

1. **`0022` applied to live prod Neon** via the `layer0-apply` Action ([run 28004281122](https://github.com/ahorn885/exercise/actions/runs/28004281122); Andy one-tap approved the `production` env). Log: `0022: OK — gear toggle catalog reshaped to 6 (4 orphans dropped, climbing rolled up, Touring/AT -> Skimo / AT setup); EX170/EX101 de-drifted`. The ledger correctly skipped 0006–0021 (already applied) and applied + recorded only 0022.
2. **Genesis baseline re-dumped to v1.9.0** (`layer0-redump` Action, `version=1.9.0`) → `etl/output/layer0_etl_v1.9.0.sql` (a `pg_dump` of the now-reshaped live `layer0`). Force-pushed over the stale `claude/layer0-baseline-v1.9.0` branch.
3. **Folded migrations `0006–0022` into the baseline** — archived to `etl/_archive/pre_v1.9.0_baseline/` (18 files; mirrors `0001–0005` in `pre_v1.7.0_baseline/`). `etl/migrations/layer0/` now holds only `README.md` + `_apply_ledger.sql`; the next migration is `0023`.
4. **Docs/bookkeeping:** `etl/migrations/layer0/README.md` + the `ci.yml` gate comment now state the redump-MUST-pair-with-fold rule; `CURRENT_STATE.md` slice-1 entry flipped OWED→APPLIED+folded; #884 commented.

**No app/code/schema change is coupled** to any of this — serving reads `WHERE superseded_at IS NULL`, so the live catalog reshape was already in effect the moment `0022` applied.

---

## 2. The redump-fold finding (READ before slice 4's forced redump)

**Symptom:** PR #915's first push (the raw v1.9.0 dump) **red-gated** the Layer 0 integrity gate: `0008: expected 4 non-retired survivor tokens, found 2 — de-drift over-stripped`.

**Root cause:** the `layer0-gate` loads the newest committed baseline and **re-applies the full `[0-9]*.sql` chain on top**. A fresh `pg_dump` of live is a *current-live ("ahead")* baseline — it already contains every migration's end-state. Re-applying a **verify-bearing** migration on it fails, because the migration's atomic verify asserts an *intermediate* state a later migration already moved on. Reproduced locally (pg_virtualenv): applying `0006–0022` on raw v1.9.0 fails on **7 migrations**:
- `0008` (survivor tokens 4→2 — `0009` culls EX150/EX153), `0009` (EX176 repoint), `0010` (holder reinsert count), `0014`/`0015` (new-exercise counts), `0016` (**hard `exercises_exercise_id_etl_version_key` unique-constraint collision** re-inserting a row already present), `0017` (repointed-survivor count).

**Why v1.8.0 passed and v1.9.0 didn't:** v1.8.0 was a *stale ("behind-live")* baseline (EX150/EX153 still active at `0B-v1.6.7`), so the chain still did real forward work and each verify held in-order. v1.9.0 is faithful-current, so the chain is all-redundant and the older verifies fail. The staleness was **masking** the flaw. (Newer migrations `0018–0022` are re-apply-safe — guarded re-inserts + verify-on-end-state — so only `0006–0017`'s older patterns trip.)

**Fix (the documented fold model):** once migrations are applied to live + captured in a redump, **archive them out of `etl/migrations/layer0/`** (the gate comment already said "`0001–0005` are folded into the baseline and archived… empty until the next migration"). With the dir empty, the gate applies zero numbered migrations and runs `validate_layer0` on the raw baseline (current live = valid). Patching the 7 historical migrations was rejected (not viable — `0016` is a real collision, not just a verify).

**Mandatory sequence for any future live redump (esp. slice 4's `craft_discipline_aliases → gear_discipline_aliases` rename, design finding B):**
`layer0-apply` → `layer0-redump` → **archive the now-baked migrations** → open the PR → gate validates the raw new baseline. Documented in `etl/migrations/layer0/README.md` (authoritative) + `ci.yml`.

---

## 3. Verification

- **Local (pg_virtualenv, PG16 with `PGCLIENTENCODING=UTF8` for the PG17 dump):** chain-on-v1.9.0 fails on the 7 migrations above (gate failure reproduced); raw v1.9.0 + `validate_layer0` → **`RESULT: PASS — all checks clean (or waived)`** (the 5 `sum_to_100` are the pre-existing waivers). Post-fold the numbered-migration glob is empty (gate apply step = no-op).
- **CI on PR #915 (post-fold push `3e57c85`):** Python unit suite ✓, JS harness ✓, **Layer 0 integrity gate ✓** → auto-merge (squash) landed it as `461be8c` on `main`. No test loads migration files by path (only comments reference them), so the fold broke nothing.
- **`main` post-merge:** `etl/migrations/layer0/` = `README.md` + `_apply_ledger.sql` only; newest baseline = `layer0_etl_v1.9.0.sql`.

---

## 4. Owed / next

### 4.1 Owed
- **Open the PR for this bookkeeping** (handoff + `CURRENT_STATE.md` top entry) when Andy says go — it's committed/pushed on `claude/bold-heisenberg-uoepcg`, PR deferred per the PR-gating rule. *(The apply+fold itself already merged via #915.)*

### 4.2 Next (the #884 build — Andy to pick; paused this session)
- **Slice 2 — equipment-boundary de-drift** (L0 migration `0023`, extends `0008`): strip craft/gear-covered items from `layer0.equipment_items` + exercises' `equipment_required`; keep only proxy machines + genuine gym kit (design §5.4). Low-risk, same pattern as `0022`; also the clean first test of the folded v1.9.0 baseline. Off the cascade critical path.
- **Slice 3 — athlete gear store** (design §15.3): `athlete_gear` / `athlete_gear_locale` / `brought_gear` public-schema tables (auto-apply on deploy) + backfill + collapse the craft repos into one `athlete_gear_repo` + eviction (§9). On the critical path to the live cascade (slice 4 reads it); ~5 files.
- **Slice 4** will FORCE a redump (the table rename) → **must heed §2's fold rule.**

---

## 6. Owed / operating notes

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry = this session (apply + fold).
3. `CARRY_FORWARD.md`.
4. This handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.
Then the design (`designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v2.md`, §15 slices) + `etl/migrations/layer0/README.md` (§2 fold rule) before slice 2/3/4.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Prod apply | `layer0-apply` run 28004281122 | step log `0022: OK — … reshaped to 6 … EX170/EX101 de-drifted` |
| New baseline | `etl/output/layer0_etl_v1.9.0.sql` | newest `layer0_etl_v*.sql` on `main`; contains `Skimo / AT setup` (was absent in v1.8.0), `0C-v1.6.8` ×2, `0B-v1.6.19` ×2 |
| Fold | `etl/migrations/layer0/` | only `README.md` + `_apply_ledger.sql` remain; `0006–0022` in `etl/_archive/pre_v1.9.0_baseline/` (18 files) |
| Fold rule documented | `etl/migrations/layer0/README.md` | "A re-dump that captures current-live state MUST be paired with folding the now-baked migrations" |
| Gate comment | `.github/workflows/ci.yml` | "0001-0022 are folded … a live re-dump MUST be paired with archiving the baked migrations" |
| Bookkeeping | `aidstation-sources/CURRENT_STATE.md` | top entry = "SLICE 1 DEPLOYED TO PROD + GENESIS BASELINE FOLDED TO v1.9.0"; slice-1 predecessor entry = APPLIED+folded |
| Issue | #884 | comment 4776297273 (deploy + redump-fold finding) |
| PR | #915 | MERGED squash `461be8c`; gate ✓ |

---

*End of handoff.*
