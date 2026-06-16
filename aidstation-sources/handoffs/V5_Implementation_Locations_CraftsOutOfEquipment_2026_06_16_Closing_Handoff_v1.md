# V5 Implementation — Crafts out of the equipment picker, into the craft store (#622) — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/v5-terrain-feasibility-venue-pick-2iqsmu` (harness-pinned from the venue-pick session; kept per "never push to a different branch" — scope this session is #622).
**PR:** [#637](https://github.com/ahorn885/exercise/pull/637) — CI-green (Layer 0 integrity gate + Python unit suite + JS harness), squash-merged to `main`.
**Predecessor handoff:** `handoffs/V5_Implementation_TerrainFeasibility_DeterministicVenuePick_2026_06_16_Closing_Handoff_v1.md` (the deterministic venue pick; this session is the next slice of the "Locations & Gear" arc it teed up).

Picked up from a closed venue-pick handoff ("keep working"). Rule #9 sweep clean (all anchors landed, tree even with `origin/main`, #635/#636 merged). Led the **"Gear surface" slice** with **#622**, investigation-first (Rule #14).

---

## 1. What shipped

### Investigation (read-only `neon-query` vs prod) — confirmed the cause, corrected a wrong assumption

**Root cause of #622:** #586 added the athlete-level **craft store** (`athlete.BIKE_TYPES`/`PADDLE_CRAFT_TYPES` → `discipline_baseline_*` + the `craft_discipline_aliases`/`craft_terrain_compatibility` feasibility wiring) but **never removed the vessels from `layer0.equipment_items`**. The per-locale gear editor (`routes/locales._layer0_equipment`, which renders *every* active `equipment_items` row grouped by category) therefore kept listing bikes/boats under "Sport-Specific — Cycling/Paddle (top-level vessels — kept individual)". Not "migration not applied" — there was never a removal migration.

**Two mechanisms, confirmed independent:**
- **Discipline feasibility** (can you cycle/paddle at all) — craft-store-driven: `owned_crafts` → `craft_discipline_aliases` + `craft_terrain_compatibility` (`session_feasibility`). Untouched by an equipment retire.
- **Exercise resolution** (which bike/paddle *exercises* resolve) — Layer-2C `locale_equipment_pool` (= locale equipment tags; owned crafts are NOT injected). Bike/paddle exercises named vessels in `equipment_required`.

**Live-data corrections (Rule #14 paid off twice):** the genesis-snapshot grep mis-parsed the `disciplines`/`terrain_types` column order. The authoritative `neon-query` (24 active disciplines @ `0A-v1.6.8`) showed **D-032 Stand-up Paddleboard is a real active discipline** (so `sup` is a fully-functional craft, not inert as the bad grep implied) and gave the real terrain map (TRN-002 Groomed Trail, TRN-009 Flat Water, TRN-011 Whitewater, TRN-017 Moving Water, …).

### Decisions (Andy ratified via `AskUserQuestion`)

1. **Approach:** layer0 **data retirement** (not a render-side picker filter).
2. **Scope:** retire all 9 vessels, **keep accessories**, **fill the vessels missing from the craft store into it**.
3. **Exercises:** **rewrite + de-drift**.

### Fix — migration `etl/migrations/layer0/0007_retire_vessel_equipment_add_crafts.sql` (Trigger #2 vocab + Trigger #3 cross-layer)

- **(0C) Retire 9 vessels** from `layer0.equipment_items` (supersede-only): Road bike, Mountain bike, Gravel bike, TT / triathlon bike, Kayak, Canoe, Packraft, Stand-up Paddleboard, Raft. **Kept** the genuine accessories sharing those categories: Power meter, Helmet, Cycling trainer. The locale gear picker auto-excludes them (renders only active rows) — **no route/template change**.
- **(0A) Add the 3 missing vessels to the craft store** at `0A-v1.6.8` (additive, NOT-EXISTS-guarded):

  | craft | `craft_discipline_aliases` | `craft_terrain_compatibility` | mirrors |
  |---|---|---|---|
  | `tt_bike` | D-007 Time-Trial Cycling (bike) | TRN-001 Road, TRN-004 Hill/Rolling | road_bike |
  | `raft` | D-019 Paddle Rafting (paddle) | TRN-009 Flat Water, TRN-011 Whitewater, TRN-017 Moving Water | packraft |
  | `sup` | D-032 Stand-up Paddleboard (paddle) | TRN-009 Flat Water, TRN-010 Ocean/Tidal | (flatwater/ocean) |

- **(0B) De-drift 27 exercises** (supersede + reinsert at `0B-v1.6.8`, version-guarded for idempotency): drop the retired vessel tokens from `equipment_required` via an order-preserving `unnest … WITH ORDINALITY` rebuild, keeping real accessories (Cycling trainer, Backpack, Foam pad, Treadmill). Rationale: post-#586 the **discipline cascade is the craft-aware gate**, so 2C gating a bike *exercise* on vessel-equipment is redundant double-gating; an emptied `equipment_required` becomes bodyweight-always-available (the discipline cascade still gates whether the session is scheduled). EX174's one vessel substitute (`"Road bike with clip-on aero bars"` → `[["Road bike"]]`) cleaned to `[]` in the same pass. (Active rows already used canonical `"Cycling trainer"`/`"TT / triathlon bike"` — the `"Bike trainer"`/`"TT Bike"` drift lived only in superseded rows, so de-drift = token removal, no renames.)

All four tables already in `_LAYER0_TABLE_FAMILY` (0A/0B/0C) → digests advance → plan caches invalidate. No family-map change.

### App code

- `athlete.py`: `BIKE_TYPES += 'tt_bike'`; `PADDLE_CRAFT_TYPES += 'sup', 'raft'`; `CRAFT_LABELS` entries added.
- `layer4/context.py`: `CyclingBaseline.bike_types_available` Literal += `"tt_bike"`; `PaddlingBaseline.paddle_craft_types` Literal += `"sup", "raft"`.
- Tests: `tests/test_athlete_crafts_repo.py` (`_ALIAS_CRAFT_NAMES` += the 3 new aliases) + `tests/test_onboarding_skills.py` (catalog assertions).

**Verification:** reproduced the CI Layer-0 gate locally on a throwaway PG (load `v1.8.0` baseline → apply `0006`+`0007` → `validate_layer0`): `0007` applies clean, **idempotent on re-run**, `validate_layer0` → **PASS**. Data spot-checks: 0 active vessels in equipment, 3 accessories kept, 3 craft aliases + 7 terrain rows added, 0 active exercises naming a vessel, EX174 substitute cleaned. Full app suite **2483 passed / 30 skipped. CI green** (incl. Layer 0 integrity gate). **NO public-schema DDL.**

## 2. STILL OWED (this session)

- ⬜ **`layer0-apply` for `0007`** — the prod Neon apply. Triggered post-merge (`actions_run_trigger run_workflow layer0-apply.yml` on `main`); **queued, awaiting Andy's one-tap `production`-environment approval**. Idempotent — safe to re-run. The picker/feasibility change is live the moment it commits (serving reads `WHERE superseded_at IS NULL`); no redeploy.

## 3. Bookkeeping done this session

- **GitHub:** **#622 CLOSED (completed)** via the PR merge ("Closes #622").
- **`CURRENT_STATE.md`:** new top "Last shipped session" entry; venue-pick demoted to predecessor.
- **`CARRY_FORWARD.md`:** no edit — next-step arc lives in GitHub issues (#623/#619/#624-follow-up).

## 4. NEXT STEPS — the "Locations & Gear" arc continues

- **[#623](https://github.com/ahorn885/exercise/issues/623)** — retire "assumed" basic gear (backpack / headlamp / hiking boots / running shoes / trekking poles / wetsuit / swim cap & goggles / avalanche gear). **Trigger #2** vocab sign-off; **audit the 2C feasibility cascade first** so removing a gating item doesn't silently drop sessions. (Same `equipment_items`-retire mechanics as this session's 0C step — `0007` is a template.)
- **[#619](https://github.com/ahorn885/exercise/issues/619)** — profile **Locations** tab + supplements/meds tab + sidebar rearrange + Sources 3-per-row + Schedule white bg. Pure UI/IA.
- **[#624 follow-up](https://github.com/ahorn885/exercise/issues/624)** — within-discipline surface-specific routing (Trigger #3).

Minor nit surfaced, not actioned: after the retire, the `equipment_category` string "Sport-Specific — Cycling/Paddle (top-level vessels — kept individual)" is a slight misnomer (only accessories remain). Cosmetic 0C label edit if Andy wants it.

## 5. Owed / carried (unchanged)

- ⬜ **STILL OWED (carried):** the post-#572 live **T3 *refresh*** re-verify (Rule #14) — needs a live refresh on a real plan + the diag token. Unrelated to this session.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Migration | `etl/migrations/layer0/0007_retire_vessel_equipment_add_crafts.sql` | `CREATE TEMP TABLE _vessels`; supersede equipment_items; insert craft aliases @ `0A-v1.6.8`; reinsert exercises @ `0B-v1.6.8`; verify `DO $$` block |
| Bike enum | `athlete.py` | `BIKE_TYPES = ('road_bike', 'mountain_bike', 'gravel_bike', 'tt_bike')` |
| Paddle enum | `athlete.py` | `PADDLE_CRAFT_TYPES = ('kayak', 'canoe', 'packraft', 'sup', 'raft')` |
| Craft labels | `athlete.py` | `CRAFT_LABELS` has `tt_bike` / `sup` / `raft` |
| Baseline Literals | `layer4/context.py` | `CyclingBaseline` Literal has `"tt_bike"`; `PaddlingBaseline` Literal has `"sup", "raft"` |
| Alias guard test | `tests/test_athlete_crafts_repo.py` | `_ALIAS_CRAFT_NAMES` includes `sup`/`raft`/`tt_bike` |
| Catalog test | `tests/test_onboarding_skills.py` | cycling == `[..., 'tt_bike']`; paddling == `[..., 'sup', 'raft']` |
| Suite | — | 2483 passed / 30 skipped |
| Gate (local + CI) | — | `validate_layer0` PASS; CI Layer 0 integrity gate green; 0007 idempotent |
| Issue | #622 | CLOSED (completed) via #637 |
| Owed | — | `layer0-apply` for 0007 (Andy's one-tap); T3-refresh re-verify carried |
