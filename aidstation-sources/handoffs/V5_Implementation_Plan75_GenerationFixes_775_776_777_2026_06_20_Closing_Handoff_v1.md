# V5 Implementation — Plan-75 Generation Fixes (#775 / #776 / #777) — Closing Handoff (2026-06-20)

## 1. What shipped

Investigation arc off the **plan #74/#75 generation failure** — a multi-discipline
plan was being discarded at the **final write**. Three root causes were found and
fixed; all three are **merged to `main`** and the `0019` migration is **applied to
prod Neon** (Andy, 2026-06-20). Filed as issues **#775–#780**; #775/#776/#777 are
done, **#778/#779/#780 remain open**.

- **#775 — recovery 3rd-slot `CheckViolation`.** A recovery session placed in a
  day's 3rd slot tripped a DB CHECK constraint, so the *whole* accepted plan was
  rolled back at persist time (the discard Andy saw). Fixed so the recovery slot
  satisfies the constraint and the accepted day-composition persists.
  **PR #781** (`9587a13`).
- **#776 — accepted-path day logging.** The accepted day-composition was not
  logged on the success path, so the silent discard above left no diagnostic
  trail. Added the Rule #15 accepted-day log (`/admin/logs`). **PR #781**
  (`9587a13`).
- **#777 — MTB / Packraft strength pool = 0 → 37/35.** D-008 Mountain Biking and
  D-009 Packrafting resolved a **strength substitute pool of ZERO**
  (feasibility log `strength_pool_n=0`): their
  `sport_discipline_bridge.exercise_db_sport` held FRAMEWORK sport names
  (`Adventure Racing`, `Long Distance / Endurance Cycling`, `Off-Road / Adventure
  Multisport (Non-Nav)`) that match no `sport_exercise_map` tag, so the
  per-discipline exercise JOIN in `layer2c/builder.py` matched nothing — leaving
  no strength option to break up two same-discipline cardio sessions stacked on
  one day. **PR #782** (`86a8e71`); migration `0019` applied to prod 2026-06-20.

## 2. The #777 fix (migration `0019`)

`etl/migrations/layer0/0019_map_mtb_packraft_strength_subs.sql` corrects
`exercise_db_sport` for the two disciplines to the **existing** exercise-DB tags:

- D-008 → `Mountain Biking` (37 exercises, 21 strength-type)
- D-009 → `Packrafting` (35 exercises, 20 strength-type)

**No new exercises** (strict no-padding satisfied) and **no exercise loss** (the
old framework-name values matched nothing). The change also resolves two existing
informational `vocab_alignment` warnings (these were `sport_exercise_map` tags
missing from `bridge.exercise_db_sport`); that check never fails the gate, so this
only improves alignment. The alias map in `etl/layer0/sport_name_aliases.py`
already encoded the right mapping but is read only by the vocab-alignment
validator, never by the runtime join — `0019` fixes the runtime data.

**Edit shape — SERVING-RELEVANT (README "Two edit shapes" #2).** The strength
pool goes 0 → 37/35, which changes plan-gen output, so the changed bridge rows
move to a bumped `0A-v1.6.7` → `0A-v1.6.8`; the per-table digest in
`_q_current_etl_version_set` advances and plan-gen caches invalidate. The other 54
active bridge rows stay at `0A-v1.6.7` (per-table max takes 1.6.8).
`sport_discipline_bridge` is already in `_LAYER0_TABLE_FAMILY` (0A). **No
public-schema DDL.**

**Idempotent + atomic.** The INSERT is `NOT EXISTS`-guarded on a corrected active
row, and the supersede only touches active rows whose tag is still wrong — a
re-run selects nothing (UNIQUE key `(framework_sport, discipline_id, etl_version)`
so the new 1.6.8 rows never collide with the retired 1.6.7 rows). The verification
DO block RAISEs (rolling back the whole migration) unless every active D-008 row
is tagged `Mountain Biking` and every active D-009 row `Packrafting`.

## 3. State at session close

- **Merged to `main`:** #781 (`9587a13`), #782 (`86a8e71`).
- **Prod-applied:** `0019` via the gated `layer0-apply` workflow (Andy, 2026-06-20).
- **No open PR from this work.** (The only open PR in the repo is **#783**, an
  unrelated #767 Whoop-CSV workstream from a different session — explicitly
  carrying its own "live-verify owed"; not touched here.)
- This handoff's bookkeeping (CURRENT_STATE predecessor block + CARRY_FORWARD
  operational entry) rides this doc-only branch `claude/plan-75-generation-yrgi2m`,
  since the work itself already merged before the bookkeeping was folded in (the
  intervening #307/#774 session updated CURRENT_STATE without recording #775–#777).

## 4. Owed (Andy-action)

1. **Live-verify `0019` (Rule #14).** Read-only `neon-query`: confirm active
   D-008/D-009 `sport_discipline_bridge` rows tag `Mountain Biking` / `Packrafting`
   at `0A-v1.6.8`. Then regenerate plan #75 and confirm `strength_pool_n` is
   **37 / 35** (not 0) and that a strength substitute breaks up the stacked
   same-discipline day. Until verified, the green suite does **not** prove the
   live DB half (Rule #9/#10 — the container can't reach Neon).
2. **`layer0-redump` (non-urgent housekeeping).** Fold `0019` into the baseline
   snapshot `etl/output/layer0_etl_v1.8.0.sql` so the genesis dump no longer lags
   live — same pattern as the `0006` re-dump (PR #626).

## 5. Next moves (Andy, 2026-06-20)

The remaining plan-75 follow-ups are **open** and were deliberately deferred:

- **#780 — clustering. SCHEDULED FOR A NEW SESSION.** Bring the
  per-locale-2C + cache-key-invalidation approach for sign-off *before* coding
  (architectural, Trigger #3/#5).
- **#778 — same-discipline auto-repair** and **#779 — two-hard-day auto-repair.**
  Both depend on **#777 being live** (so a 2nd MTB/packraft session has a strength
  pool to convert into) — sequence them after the #777 live-verify clears.

Recommended order: #780 (design sign-off first) → #778 → #779. Root-cause + fix
detail for all six items lives in GitHub issues #775–#780.

## 6. Operating notes for next session

### 6.1 Tier placement (4-tier order)
This was tier-1/tier-2 work (finish the in-flight plan-gen investigation +
resolve a live-functionality blocker — plans were being discarded). The remaining
#778/#779/#780 are tier-3 (complete partially-shipped behavior).

### 6.2 Branch
Doc/bookkeeping branch `claude/plan-75-generation-yrgi2m`. The code already merged
via #781/#782; their feature branches are spent.

### 6.3 Session-start reads (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus (this work is the first
   predecessor block under the #307/#774 last-shipped pointer)
3. `CARRY_FORWARD.md` — the Plan-75 operational entry (live-verify + redump owed)
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 7. Verification (Rule #10) — every claim below is on-disk / on-`main`

| Claim | Where | Check |
|---|---|---|
| #775/#776 merged | `main` `9587a13` | `git log --oneline \| grep 9587a13` → "#775 + #776 … (#781)" |
| #777 merged | `main` `86a8e71` | `git log --oneline \| grep 86a8e71` → "#777 … (#782)" |
| Migration present | `etl/migrations/layer0/0019_map_mtb_packraft_strength_subs.sql` | file exists on `main`; retags D-008→`Mountain Biking` / D-009→`Packrafting` at `0A-v1.6.8`; verify DO block |
| Prod-applied | live Neon | `layer0-apply` run (Andy, 2026-06-20) — **live-verify still owed via `neon-query`** |
| CURRENT_STATE updated | `aidstation-sources/CURRENT_STATE.md` | predecessor block "Plan-75 generation fixes …" after the #307 last-shipped block |
| CARRY_FORWARD updated | `aidstation-sources/CARRY_FORWARD.md` | "Plan-75 generation fixes — #775/#776 … #777 … (`0019`)" entry above the #307 entry |

## 8. §8 anchor table (input to next session's Rule #9 sweep)

| File | Anchor string | Method |
|---|---|---|
| `etl/migrations/layer0/0019_map_mtb_packraft_strength_subs.sql` | `0A-v1.6.8` ; `Mountain Biking` ; `Packrafting` | grep |
| `aidstation-sources/CURRENT_STATE.md` | `Plan-75 generation fixes: #775/#776 recovery DB fix` | grep |
| `aidstation-sources/CARRY_FORWARD.md` | `Plan-75 generation fixes — #775/#776 recovery DB fix` | grep |
| `aidstation-sources/handoffs/V5_Implementation_Plan75_GenerationFixes_775_776_777_2026_06_20_Closing_Handoff_v1.md` | this file | exists |

## 9. Gut check

- **Risk:** the only thing standing between "merged + applied" and "confirmed
  fixed" is the `neon-query` live-verify + a plan-#75 regen — the container can't
  do either, so this is genuinely Andy-action. A green suite is not proof the
  live bridge rows retagged (Rule #9/#10).
- **Best argument against the structure here:** #777's runtime data drift
  (framework names in `exercise_db_sport`) and the validator-only alias map mean
  the same class of drift could recur on the *next* discipline whose framework
  name doesn't match an exercise tag. A standing guard (wire the alias map into
  the runtime join, or a `validate_layer0` check that fails on an
  `exercise_db_sport` that resolves zero exercises) would prevent recurrence —
  not built this session; worth filing if #778/#779 surface more of the same.
- **#778/#779 sequencing is load-bearing:** they convert a 2nd same-discipline
  cardio session into a strength session, which only works once #777's pool is
  live. Verifying #777 in prod first is not optional before those land.
