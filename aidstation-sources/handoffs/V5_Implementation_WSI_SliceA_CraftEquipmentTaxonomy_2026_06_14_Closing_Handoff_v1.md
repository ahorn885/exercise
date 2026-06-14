# V5 Implementation — WS-I Slice A: craft/equipment taxonomy + craft_terrain_compatibility seed (Closing Handoff)

**Session:** Built + shipped the data/taxonomy half of WS-I (the unified craft/equipment feasibility cascade): drop `cycling_trainer` from the craft enum, create + seed the `layer0.craft_terrain_compatibility` map, retire the stale aliases. The cascade rewrite (Slice B) is deferred.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_pv71_GearToggleValidation_AbseilGate_WSI_CraftCascadeDesign_2026_06_13_Closing_Handoff_v1.md`
**Branch / PR:** [#587](https://github.com/ahorn885/exercise/pull/587) (`claude/dreamy-wozniak-t3tifr` — harness-pinned name; scope is WS-I Slice A). Open, **CI green**, ready for review.
**North-star plan:** `aidstation-sources/plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (WS-I).
**Status:** 4 substantive files (under the 5-file ceiling). Slice A of a 2-slice split Andy ratified ("Slice A first").

---

## 1. Session-start verification (Rule #9)

Anchor-checked the pv=71 handoff's §8 table against on-disk state — **all clean, no drift**:

| Claim | Anchor | Result |
|---|---|---|
| Abseiling skill-gate | `climbing_roped` row → `ARRAY['D-012', 'D-013']` in `etl/sources/populate_skill_capability_toggles.sql` | ✅ grep (lines 48/56) |
| WS-I design present | `designs/CraftEquipment_Taxonomy_And_FeasibilityCascade_Design_v1.md` §3/§4 | ✅ read |
| Craft-STRENGTH preempt (the bug) | `layer4/orchestrator.py:437` `if craft is not None and craft.tier == "strength": … continue` | ✅ grep |
| Craft enum (fix target) | `athlete.py:320` `BIKE_TYPES = (…, 'cycling_trainer')` | ✅ grep |
| MCP allow rule | `"mcp__Vercel"` in `.claude/settings.json` | ✅ grep |

`verify-handoff.sh` ran clean (note: it lives at `aidstation-sources/scripts/verify-handoff.sh`, not `./scripts/` — run it from `aidstation-sources/`). **Reconciliation note:** clean — no gap to reconcile.

---

## 2. Session narrative

- **Scope pick.** All three rolling docs + the pv=71 handoff §6 point to **WS-I build (#586)** as the immediate next. Confirmed scope with Andy before building.
- **Design-doc correction (load-bearing).** The design's §4 instructs seeding `craft_terrain_compatibility` via the `Sports_Framework` xlsx + extractor + runner. **Andy flagged it: that path is retired (epic #488 — the `layer0.*` DB is the source of truth; reference data is authored as reviewed SQL migrations under `etl/migrations/layer0/`, gated by `validate_layer0`).** Built against the migration model instead. No xlsx, no extractor, no runner. The design §4 text is stale on the *mechanism* only — the grid + decisions are intact.
- **Split (Andy-ratified "Slice A first").** WS-I's full change surface is 6–8 substantive files (over the ceiling). Proposed splitting; Andy chose **Slice A (data + taxonomy) first**, then Slice B (cascade). This handoff is Slice A.
- **Deferred `_LAYER0_TABLE_FAMILY` + cascade to Slice B.** Refined the slice boundary so the new table's cache-digest registration lands *with* the cascade that reads it (cohesive, and avoids a deploy-ordering foot-gun where prod code queries a table not yet on Neon).
- **Validated against a real Postgres**, not just unit stubs — stood up a throwaway PG locally and ran the exact CI gate (schema + genesis snapshot + all 4 migrations + `validate_layer0`).

---

## 3. File-by-file edits

### 3.1 `athlete.py` (modified)
Drop `cycling_trainer` from `BIKE_TYPES` (`:320`) and its `CRAFT_LABELS` entry. A trainer/erg is fixed gear → equipment, not a mobile craft (design §2). `athlete_crafts_repo.load_craft_catalog()` + `replace_athlete_crafts` derive the picker and the closed-enum validation from these constants, so `cycling_trainer` leaves the UI and fails craft validation in lockstep — single source of truth. Added a comment pointing at the `0004` migration.

### 3.2 `etl/migrations/layer0/0004_craft_terrain_compat_and_drop_cycling_trainer.sql` (new)
Two changes, one `BEGIN…COMMIT`:
- **CREATE `layer0.craft_terrain_compatibility`** (shape mirrors sibling `craft_discipline_aliases`: `craft_name`/`terrain_id` + row-invalidation columns, `UNIQUE(craft_name, terrain_id, etl_version)`) + the **21-row Andy-ratified seed grid** (design §4) at `etl_version='0A-v1.6.7'`. Spec-sourced + self-contained (out of `schema.sql`), per the `0003`/`terrain_gap_rules` precedent.
- **Retire the `cycling_trainer` craft aliases** — soft-supersede the 5 genesis rows (`D-006/007/008/030/031`). **Cache-neutral** removal (same shape as `0001`): `cycling_trainer` ceases to be a capturable craft in the same change, so no serving path references the superseded rows; no `etl_version` bump.

### 3.3 `tests/test_athlete_crafts_repo.py` (modified)
Drop `cycling_trainer` from the `_ALIAS_CRAFT_NAMES` capture-coverage guard.

### 3.4 `tests/test_onboarding_skills.py` (modified)
Drop `cycling_trainer` from the expected onboarding craft-catalog (`cycling` list).

---

## 4. Code / tests

No new tests (Slice A is data + an enum narrowing; the new tier matrix belongs to Slice B's cascade). Updated 2 existing enum-pinned assertions. Affected suites green: `test_athlete_crafts_repo`, `test_onboarding_skills`, `test_layer4_craft_feasibility`, `test_layer2_substitution`, `test_layer4_orchestrator` (147 passed) + ETL gate tests (88 passed).

> The `test_layer4_craft_feasibility` / `test_layer2_substitution` synthetic fixtures still treat `cycling_trainer` as a craft. They don't import the real enum so they pass, but they're conceptually stale — **fix them in Slice B** when the cascade logic changes.

---

## 5. Manual verification

Ran the **full Layer 0 gate locally against a throwaway Postgres** (exact CI steps): schema + genesis snapshot + all 4 migrations apply clean; `validate_layer0` → PASS; **21 active** `craft_terrain_compatibility` rows (road 2 / gravel 4 / mtb 6 / kayak 4 / canoe 2 / packraft 3) with **0 dangling terrain FKs**; `cycling_trainer` aliases **all 5 superseded**; **idempotent** on re-apply. CI on #587: Layer 0 gate ✅, Python suite ✅, JS harness ✅, Vercel ✅, Real-LLM skipped.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**WS-I Slice B — the cascade rewrite** (where the live bug actually gets fixed). On a fresh branch/PR after #587 merges + `0004` is on Neon (deploy-ordering: the cascade *reads* `craft_terrain_compatibility`). Scope:
1. **`layer4/orchestrator.py`** — add `"craft_terrain_compatibility": "0A"` to `_LAYER0_TABLE_FAMILY` (so grid edits invalidate plan caches; sibling of `craft_discipline_aliases` = 0A). Add a `test_includes_out_of_schema_serving_tables`-style assertion in `tests/test_layer4_orchestrator.py`. **Remove the craft-STRENGTH short-circuit** (`:437-449`) that preempts INDOOR.
2. **`layer4/session_feasibility.py`** — replace the two non-composing axes (`resolve_craft_feasibility` OWNED→SWAP→STRENGTH + `resolve_terrain_feasibility` EXACT→PROXY→INDOOR→STRENGTH→REALLOCATE) with the single **nested cascade** (design §3): `1 exact → 2 owned-craft/other-terrain → 3 proxy-craft/desired-terrain → 4 proxy-craft/own-terrain → 5 indoor → 6 strength → 7 reallocate` (**tier 3 > tier 4**, Andy-ratified). Read `craft_terrain_compatibility` at tiers 2–4.
3. **Rule #15 logging** — per-discipline: the chosen tier + the inputs it decided on (owned crafts, candidate proxies, required vs available terrain, the craft↔terrain check result).
4. **Tests** — the new tier matrix incl. the two cases that motivated this: **craftless-with-trainer → INDOOR** (not strength — the bug), and **proxy-craft on desired terrain** (tier 3). Fix the stale synthetic fixtures (§4).
5. **Profile UI** — confirm `cycling_trainer` is gone from the craft picker (it is, derived from the enum) and that the equipment capture offers a Cycling trainer item.

### 6.2 Alternative pivots
- **STILL OWED (carried):** the post-#572 live **T3 *refresh*** re-verify (paired: needs the diag token + Andy pasting logs, Rule #14). Not done — pv=71 was a *create*.
- Lower-priority arc: [#582] retire `LOCALES` (WS-B), [#583] onboarding forced-home + craft capture (WS-C), [#584] saturation policy (WS-E2), WS-H away-craft (needs DDL, design first).

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules (incl. Rules #14/#15).
2. `CURRENT_STATE.md` — top entry = this session; focus = **WS-I Slice B**.
3. `CARRY_FORWARD.md` — top entry = this session (Slice A shipped, owed-Neon status).
4. This handoff.
5. The plan doc `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md`.
6. `aidstation-sources/scripts/verify-handoff.sh` (run from `aidstation-sources/`).

**Local Postgres gate recipe (no Neon egress needed):** Postgres binaries are in the container (`/usr/lib/postgresql/*/bin`); it won't run as root, so `useradd -m pgrunner`, `chown` a datadir + socket dir to it, `su pgrunner -c "initdb … && pg_ctl … start"`, then run the CI gate steps (`psql -f etl/layer0/schema.sql`; load the newest `etl/output/layer0_etl_v*.sql`; apply `etl/migrations/layer0/*.sql` in `sort -V`; `python -m etl.layer0.validate_layer0`). This reproduces the `layer0-gate` CI job exactly.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | WS-I built as a migration, NOT xlsx/extractor | Andy | xlsx authoring retired (epic #488); DB is source of truth. Design §4's xlsx mechanism is stale. |
| 2 | Split WS-I; **Slice A (data + taxonomy) first** | Andy | Full WS-I is 6–8 files, over the 5-file ceiling. |
| 3 | `0004` SQL bundled in the PR for Andy to run on Neon | Andy | Container has no Neon egress; matches prior owed-hands deploys. |
| 4 | `craft_terrain_compatibility` registered in the cache digest **in Slice B** (not A) | Claude (flagged) | Cohesive with the cascade that reads it; avoids prod querying a table not yet on Neon. |
| 5 | Alias removal is cache-neutral (no version bump) | Claude (flagged) | `cycling_trainer` leaves the capture enum in the same change → no serving path references the rows (`0001` shape). |
| 6 | Stop after Slice A; Slice B in a later session | Andy | — |

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Craft enum drop | `athlete.py` | `BIKE_TYPES = ('road_bike', 'mountain_bike', 'gravel_bike')` (no `cycling_trainer`); no `cycling_trainer` key in `CRAFT_LABELS` (`:320`-ish) |
| New L0 table + seed | `etl/migrations/layer0/0004_craft_terrain_compat_and_drop_cycling_trainer.sql` | `CREATE TABLE IF NOT EXISTS layer0.craft_terrain_compatibility`; 21 `INSERT … VALUES` grid rows; `UPDATE layer0.craft_discipline_aliases SET superseded_at = now() … craft_name = 'cycling_trainer'` |
| Test guards updated | `tests/test_athlete_crafts_repo.py` / `tests/test_onboarding_skills.py` | neither `_ALIAS_CRAFT_NAMES` nor the onboarding `cycling` catalog lists `cycling_trainer` |
| Cascade NOT yet touched (Slice B) | `layer4/orchestrator.py` | `_LAYER0_TABLE_FAMILY` does **not** yet contain `craft_terrain_compatibility`; the `:437` craft-STRENGTH `continue` is still present |
| PR / CI | [#587](https://github.com/ahorn885/exercise/pull/587) | open, ready-for-review; Layer 0 gate + Python suite green |
| Working tree | — | clean after the bookkeeping commit |

---

## 9. Files shipped this session

**Substantive (4 files):**
1. `athlete.py`
2. `etl/migrations/layer0/0004_craft_terrain_compat_and_drop_cycling_trainer.sql`
3. `tests/test_athlete_crafts_repo.py`
4. `tests/test_onboarding_skills.py`

**Bookkeeping (this commit):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

## 10. Owed Andy's hands (Neon — container has no egress)

1. **Apply `0004` on Neon** — ✅ **DONE this session** (Andy ran it; was briefly hitting `3F000 schema "layer0" does not exist` from the SQL editor being in the **wrong Neon project** — resolved by switching to the correct project; the migration assumes `layer0` pre-exists, never creates it).
2. **Per-athlete data fix — ✅ DONE** (Andy, 2026-06-14). Ran the `discipline_baseline_cycling.bike_types_available` strip (`array_remove` the `cycling_trainer` token) **and** ticked **Cycling trainer** in his home locale's equipment via the profile UI. Set B is now trainer-free; the trainer lives in set C, where Slice B's INDOOR tier will read it.
3. **Merge #587** when satisfied — then Slice B can build on a fresh branch. *(Only remaining owed item.)*
