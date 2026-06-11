# V5 Implementation — Layer 0 migration `0002`: de-orphan `supplement_vocabulary`

**Date:** 2026-06-11
**Branch:** `claude/eloquent-albattani-6ksbxb` · **Epic [#488](https://github.com/ahorn885/exercise/issues/488)**

## 1. What this session was

Picked up off the phase-4 DB-export closing handoff. Andy: *"keep going on the next slice of the migration."* Epic #488's **only** remaining checklist item is the §6.4 freeze (archive extractors + workbooks), and it is **gated on "2–3 migrations going through cleanly" — only `0001` had**. Last session was emphatic about not pulling the freeze forward (the export was built to make it *safe*, not to clear the gate). So "the next slice" forked: do the gated freeze, or **advance the gate** with the next real migration. I surfaced the fork; Andy chose **advance the gate** (`AskUserQuestion`, "Land migration 0002").

The named candidate was the owed supplement-vocab contraindication retag. Investigating it surfaced two facts that reshaped the slice:

1. **The retag is the wrong vehicle.** `layer0.supplement_vocabulary` is **not in `schema.sql` and not in the genesis snapshot** — it's a *spec-sourced* (not ETL-emitted) table that only ever existed as the one-shot `etl/sources/migrate_supplement_vocabulary.sql`. The CI gate (schema + genesis + migrations) never sees it, so a `0002` that `UPDATE`s it would fail. And the retag is a **no-op against the canonical seed** (the seed file already carries the post-retag lowercase §B tokens) — it was a one-time prod fix for a legacy-token DB, history not forward history.
2. **The orphan table *is* the gate-advancing work.** A Layer 0 table managed entirely by ad-hoc SQL outside the gate is exactly the hole the freeze can't safely close over (you can't retire the authoring loop while tables live in untracked SQL). So `0002` = **de-orphan `supplement_vocabulary` into the gate-covered model**, which also discharges the owed Neon apply and subsumes the retag.

Session start clean: `verify-handoff.sh` all-green, working tree clean, phase-4 export (`#545`) at the tip of `main`. No Rule #9 drift.

## 2. What shipped (code)

- **`etl/layer0/schema.sql`** — folded in `CREATE TABLE IF NOT EXISTS layer0.supplement_vocabulary` (+ the active-row partial index + the two CHECK constraints), matching the existing "folded from `migrate_terrain_types.sql`" precedent in the file's tail. **Shape mirrors the live one-shot DDL exactly** (bare `TIMESTAMP superseded_at`, no `etl_run_at`) — deliberately *not* normalized to the 22-table `TIMESTAMPTZ`+`etl_run_at` convention, to stay drift-free with any copy already on Neon. (Normalizing is a separate, ALTER-bearing change.)
- **`etl/migrations/layer0/0002_seed_supplement_vocabulary.sql`** (new) — the 25-row canonical seed as a **self-contained** migration (`CREATE TABLE IF NOT EXISTS` + `INSERT … ON CONFLICT (supplement_id) DO NOTHING` + a verify `DO` block), so a standalone Neon SQL-editor paste provisions the table without a separate schema step. The `contraindications[]` already carry the canonical §B tokens, so it **subsumes both** legacy one-shots (`migrate_supplement_vocabulary.sql` base seed + `migrate_supplement_vocab_contraindication_retag_v1.sql` D-21 retag). Idempotent — provisions-or-no-ops on a fresh DB, a legacy-token prod DB, or an already-canonical prod DB.
- **`etl/migrations/layer0/README.md`** — new "Tables that are not in the genesis snapshot (spec-sourced, not ETL-emitted)" section documenting the DDL-→-schema.sql / seed-→-migration absorption pattern, with `0002` as the worked example and `terrain_gap_rules` named as the next one.
- **`Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md`** (in-place edit, slice-3b/phase-4 precedent — no version bump): §6 item 4 records `0001`+`0002` through cleanly + a spec-sourced-orphan-tables sub-note; §9 checklist marks `0002` `[x]`, adds `0003` (`terrain_gap_rules`) as owed, and updates the freeze-gate count.

**The legacy one-shots** (`etl/sources/migrate_supplement_vocabulary.sql`, `…_retag_v1.sql`) are left in place (only doc references, no code/CI dep) — superseded by `0002`, sweep them at the freeze.

## 3. Verification

Replicated the `layer0-gate` CI job locally against a throwaway Postgres 16 (Docker daemon was down + Neon egress blocked, so ran `postgres:16`'s server binaries as the unprivileged `postgres` user over a unix socket — same sequence as `ci.yml`):

- `schema.sql` → genesis `v1.6.7` → `0001` → `0002` all apply clean.
- `0002` verify `DO` block fires: **25 active rows**. Distinct contraindication tokens are all canonical; the legacy-token probe (`Cardiac`/`GI`/`Endocrine/Metabolic`/`allergen:dairy`/`rx:PDE5-inhibitors`/`rx:SSRIs`/`rx:blood-pressure medications`/`rx:thyroid medications`) returns **0** — retag fully subsumed.
- **`validate_layer0` → PASS** (exit 0): all checks clean, the 5 known `sum_to_100` waivers waived, 0 unwaived. (The validator doesn't reference `supplement_vocabulary`, so adding the table is gate-neutral.)
- Idempotency: re-applying `0002` → still 25 rows, no dupes.
- **`etl/tests/` 197 passed** (no Python touched — pure SQL + schema DDL). Main `tests/` suite untouched (no app-code change).

## 4. Owed / next move

1. **Andy's-hands — apply `0002` on Neon.** One idempotent paste of `etl/migrations/layer0/0002_seed_supplement_vocabulary.sql` in the Neon SQL editor. Replaces the old supplement-vocab two-step (base seed + retag). Until applied, the live vocab keeps the legacy tokens → Layer 2E contraindication screening stays inert on prod. Verify query in CARRY_FORWARD item A.
2. **`0003` (owed) — de-orphan `terrain_gap_rules`** the same shape (DDL → `schema.sql`, seed → migration). It's the **last spec-sourced orphan**, and landing it brings the freeze gate to 3 migrations through cleanly — i.e. `0003` clears the §6.4 freeze gate. Natural next slice.
3. **Phase-4 §6.4 freeze — still owed, gate now 2/3.** Freeze `etl/layer0/extractors/`, `run.py`, `emit_sql.py` + v14/v19 once the gate clears (after `0003`). Don't pull forward.
4. **Carried (unchanged):** cold-plan post-deploy verify (slice 3b / #521 — terrain non-empty + real exercise pool). Off-track go-live blockers **#539** (tab-closed plan-gen crawl) + **#540** (terrain-infeasible locale routing) remain higher on the 4-tier order than the rest of phase 4.

## 5. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Table DDL folded into canonical schema | `etl/layer0/schema.sql` | `CREATE TABLE IF NOT EXISTS layer0.supplement_vocabulary` near EOF + the `D-26 / FC-1` fold comment |
| `0002` migration exists, self-contained + idempotent | `etl/migrations/layer0/0002_seed_supplement_vocabulary.sql` | `CREATE TABLE IF NOT EXISTS` + `ON CONFLICT (supplement_id) DO NOTHING` + `0002 verify OK` `DO` block |
| Seed carries canonical §B tokens (subsumes retag) | `etl/migrations/layer0/0002_seed_supplement_vocabulary.sql` | `ARRAY['cardiac','pregnancy']` (caffeine), `ARRAY['rx:ssri','rx:beta_blocker','rx:diuretic']` (melatonin) — no `Cardiac`/`rx:SSRIs` |
| Absorption pattern documented | `etl/migrations/layer0/README.md` | "Tables that are not in the genesis snapshot (spec-sourced, not ETL-emitted)" section |
| Gate count / orphan note synced | `aidstation-sources/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` | §6 item 4 "`0001` + `0002`" + spec-sourced-orphan sub-note; §9 `[x] 0002`, `[ ] 0003` |
| Owed apply collapsed to one paste | `aidstation-sources/CARRY_FORWARD.md` | item A "apply Layer 0 migration `0002` … one idempotent paste" |

### 5.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. Then epic #488 + `Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` (§6.4 freeze gated on 2–3 migrations — now 2/3; `0003` = `terrain_gap_rules` de-orphan clears it).

## 6. Stop-and-ask status

One fork surfaced and resolved at session start (`AskUserQuestion`): advance the gate vs. do the gated freeze — Andy chose advance. The candidate then shifted (retag → de-orphan) on a technical finding (table absent from the gate; retag no-op vs canonical seed); recorded here + in the README/design-doc edits. No LLM / HITL / cross-layer-contract surface touched — `supplement_vocabulary` schema is additive and already live; the change is a data seed + its DDL's canonical home. No trigger fired.

## 7. Summary

The migration epic's only open item is the §6.4 freeze, gated on 2–3 clean migrations (only `0001` had). Rather than pull the gated freeze forward, this slice **advanced the gate**: it de-orphaned `layer0.supplement_vocabulary` — a spec-sourced, non-ETL table that lived entirely in ad-hoc `etl/sources/` SQL the CI gate never saw — into the gate-covered model. DDL folded into `schema.sql`; the 25-row canonical seed became `0002_seed_supplement_vocabulary.sql`, a self-contained idempotent migration that **subsumes** both the legacy base seed and the D-21 contraindication retag (its tokens are already canonical). Proven against a local throwaway-Postgres replica of the `layer0-gate`: schema + genesis + `0001` + `0002` apply clean, 25 active rows, 0 legacy tokens, `validate_layer0` PASS, idempotent on re-apply; `etl/tests/` 197 green. Freeze gate now 2/3 — `terrain_gap_rules` as `0003` is the last orphan and clears it. Only owed-hands item is the one idempotent Neon paste of `0002`.
