# Unified Gear/Craft Model + `gear/craft (+skill)` Feasibility — Design v3

**Date:** 2026-06-23
**Issue:** #884 (go-live blocker — user-facing). Closes the live part of #298 (starved gear-toggle subsystem).
**Status:** RATIFIED. v3 amends the ratified v2 with three Andy decisions (2026-06-23) taken while planning the store slice: **(D1) ordinal fidelity rank** (so rollerskis sit between skate-XC and the ski-erg), **(D2) gear can enable cardio drills/workouts but never strength exercises** (swim gear), and **(D3) a pinned `gear_id` keyspace** the store/alias/picker share. Slice list re-sequenced (§15). Build-ready.
**Supersedes:** `Unified_GearCraft_Model_And_Feasibility_884_Design_v2` (archived). v2's body is preserved below; the v3 amendments are Decisions 10–12, §5.3 (rank type), §5.5 (keyspace), §6a (drill gate), the §15 re-slice, and the §16 2026-06-23 sign-offs.

## Ratified decisions (Andy, 2026-06-22, amended 2026-06-23)

1. **Treat gear toggles exactly like crafts.** Gear managed by a "toggle" is athlete-owned and **portable** — usually at home, but can be taken along. Same model, same "available at this locale / during this event window" plumbing crafts already have.
2. **Full one-table merge.** One athlete-owned **gear/craft** concept; merge the stores and the Layer-0 alias relation; migrate everything.
3. **Gym equipment is the *proxy* tier, not the gear itself.** A bike is a craft, not gym equipment; if you own the ski setup you don't also need skis "at a gym." Gym equipment that's a real proxy (ski-erg, trainer, paddle-erg) **degrades** a missing gear/craft before strength does.
4. **Gate at the toggle level, never on individual equipment** that's part of a toggle.
5. **Feasibility = `gear/craft (+ skill where applicable)`.** Running gates on neither; cycling on craft only; climbing on gear **and** skill.
6. **Gear gets discipline aliases, no terrain** (terrain stays craft-only) — **except** a substitute gear whose terrain differs from the discipline's (rollerskis; §6/Decision 10), which the cascade resolves at the PROXY tier on the gear's own terrain.
7. **Catalog:** delete bouldering/fencing/shooting toggles (orphans) + whitewater (it's a craft); roll climbing+abseiling+via-ferrata into one climbing-gear toggle; add a skimo/AT setup toggle; wire the survivors. *(Shipped — migration `0022`, slice 1.)*
8. **(REVISED v3 — ordinal.)** Gear options for a discipline are **ordinally fidelity-ranked** via an **integer `fidelity_rank`** (0 = best/primary; higher = more degraded), *not* a binary primary/degraded flag. D-028 Cross-Country Skiing carries three owned-gear fidelities: **Classic XC `0` → Skate XC `1` → Rollerskis `2`**. The gym **ski-erg stays the gear-independent INDOOR fallback** below all owned gear (Decision 3), so "rollerski before ski-erg" falls out of the existing PROXY-over-INDOOR tier order.
9. **Pack-load is out of scope** — a coaching-LLM concern.
10. **(NEW v3.)** **Rollerskis are owned gear**, a degraded **dryland** substitute for D-028 ranked above the ski-erg — *not* a discipline (no D-id; aliases to D-028) and *not* a gym machine. This **promotes** rollerskis from the "training-modality/machine" treatment in `Provider_Inbound_Matrix_v2` §12 (which lumped them with stair/erg/treadmill). Reconciliation: the provider matrix's *inbound-classification* call is unchanged (a `RollerSki` activity still maps to D-028, dryland, raw-flagged); v3 adds the *ownership/feasibility* treatment the matrix didn't cover. Footnote the matrix §12 so the two docs don't drift.
11. **(NEW v3.)** **Gear can enable cardio drills/workouts, never strength exercises.** A discipline that's feasible on its own (swimming, D-004, gates on water alone) can still have **gear-gated drill variants**: pull buoy → pull sets, paddles → paddle sets, kickboard → kick sets. This is membership in the live `cardio_drills[]` pool (§6a), **not** a discipline-feasibility gate and **not** an `equipment_required` gate on the EX row (Decision 4).
12. **(NEW v3 — `gear_id` keyspace.)** One stable closed keyspace for `gear_id` across `athlete_gear`, `gear_discipline_aliases`, and the picker (§5.5).

---

## 1. Problem

Athlete-owned equipment is modelled three ways, only one wired through:

| | Crafts (bikes/boats) | Gear toggles (#298) | Skill toggles *(separate axis — not merged)* |
|---|---|---|---|
| Athlete store | `discipline_baseline_{cycling,paddling}` CSV cols | **none** | `athlete_skill_toggles` |
| Layer-0 def | `craft_discipline_aliases` + `craft_terrain_compatibility` | `sport_specific_gear_toggles` | `skill_capability_toggles` |
| Capture UI | ✅ profile + onboarding + per-locale | ❌ none | ✅ |
| Fed to plan-gen | ✅ feasibility cascade | ❌ both 2C sites pass `{}` | ✅ |
| "Bring it" | ✅ `athlete_craft_locale` + `brought_craft` | ❌ | n/a (a skill travels) |

Consequences: (a) gear is uncapturable and dead in prod; (b) of the 12 gear toggles only 3 even have a `gated_discipline_ids`, and an OFF toggle today only emits a 2C coaching flag — it never actually gates feasibility the way a missing bike does; (c) "bring it" is craft-only; (d) crafts and toggle-gear still pollute the per-locale gym-equipment list, and exercises hard-gate on individual gear items (#623 began retiring these).

## 2. Scope & boundaries

**In:** one athlete-owned **gear/craft** model (portable; locale + event-window availability); one Layer-0 gear→discipline alias relation (ordinally fidelity-ranked); a unified `gear/craft (+skill)` feasibility cascade that un-starves the toggle subsystem; gear-gated cardio drills (§6a); the catalog cleanup (§4); the gym-equipment boundary cleanup (§5.4).

**Out:** skill-capability toggles (compose, don't merge); per-locale gym equipment (settled, except §5.4); pack-load.

## 3. The unified concept

**Gear/craft** = an athlete-owned, **portable** thing whose presence unlocks training for one or more disciplines.
- *Craft* (bike/boat): unlocks disciplines **and** carries terrain compatibility.
- *Gear* (ski setup, climbing rack, mountaineering kit, snowshoes, skimo/AT setup, rollerskis): unlocks disciplines; **no terrain** (except a substitute gear on its own terrain — Decision 6/10).

Both are athlete-scoped, available across the whole **home cluster** by default, and made available **away** by attaching to a saved locale (standing) or an event window (per-trip). Gym equipment is a separate, location-bound thing that can act as a **proxy** for an absent gear/craft.

## 4. Catalog (ratified) — refine, don't invent

| Toggle (current) | Action | Disciplines unlocked | Rank |
|---|---|---|---|
| Bouldering, Fencing setup, Shooting setup | **DELETE** | — (no discipline) | — |
| Whitewater paddling setup | **DELETE** | handled by the craft | — |
| Climbing — roped **+** Rappelling/abseiling **+** Via ferrata | **ROLL UP → "Climbing gear"** | D-012, D-013, D-014 | 0 |
| Classic XC ski setup | keep + wire | D-028 | **0 (primary)** |
| Skate XC ski setup | keep + wire | D-028 | **1 (degraded)** |
| **Rollerskis** | **ADD (new gear — Decision 10)** | D-028 (dryland) | **2 (degraded)** |
| Mountaineering | keep + wire | D-018 | 0 |
| Snowshoeing setup | keep (wired) | D-017 | 0 |
| Skimo / AT setup | ADD (shipped slice 1) | D-021, D-022 | 0 |

Crafts keep their existing aliases (kayak→D-010; canoe→D-011; packraft→D-009; road_bike→D-006; gravel_bike→D-006/030/031; mountain_bike→D-008/031; tt_bike→D-007; sup→D-032; raft→D-019) **plus** their terrain compatibility, migrating into `gear_discipline_aliases` at `fidelity_rank = 0`.

Disciplines with **no** gear/craft gate: D-001 Trail Running, D-002 Road Running, D-024 Mountain Running, D-003 Trekking, **D-004 Swimming**, D-027 OCR. (D-004 stays ungated — swim gear gates *drills*, not feasibility — §6a.)

**Skill composition** (unchanged): climbing/abseiling/via-ferrata (D-012/013/014) + mountaineering (D-018) gate on gear **and** skill; ski/snowshoe/cycling/paddling on gear/craft only; running on neither.

## 5. Data model — full one-table merge

### 5.1 Athlete store (NEW public-schema table; auto-applies on deploy)

```
athlete_gear (
  user_id    INTEGER NOT NULL REFERENCES users(id),
  gear_id    TEXT    NOT NULL,            -- catalog key (§5.5)
  group_kind TEXT    NOT NULL,            -- 'bike'|'paddle'|'ski'|'snow'|'climbing'|'alpine'
  access     TEXT    NOT NULL DEFAULT 'own',  -- 'own' | 'access'
  PRIMARY KEY (user_id, gear_id)
)
```
Replaces `discipline_baseline_cycling.bike_types_available` + `discipline_baseline_paddling.paddle_craft_types` (→ craft rows) and is the first-ever store for owned gear toggles (→ gear rows). `group_kind` is stored so read paths route without a catalog join.

### 5.2 Portable availability (generalize the craft tables)
- `athlete_craft_locale (user_id, craft_slug, locale)` → **`athlete_gear_locale (user_id, gear_id, locale)`**.
- `athlete_event_windows.brought_craft` → **`brought_gear`** (CSV, preserving the stable-sort + `compute_event_windows_hash` convention).

### 5.3 Layer 0 — extend `craft_discipline_aliases`, don't add a parallel table (long-term)

Target: **`gear_discipline_aliases (gear_id, discipline_id, group_kind, fidelity_rank)`**:
- existing craft rows migrate 1:1 (`fidelity_rank = 0`);
- gear toggles become rows here (the §4 mapping);
- **`fidelity_rank INTEGER NOT NULL DEFAULT 0`** (REVISED v3): an **ordinal** rank, `0` = best/primary, higher = more degraded. Exercised today by **D-028 (Classic 0 / Skate 1 / Rollerskis 2)**; every other gear/craft defaults `0`. Integer, not a `{primary,degraded}` enum, so a discipline can carry >2 substitute fidelities without a schema change (the rollerski case forces this; the table is unbuilt so the column type is free to choose now).

**Migration staging (v3):** `gear_discipline_aliases` is **created and populated alongside** the live `craft_discipline_aliases` (slice 3a / migration `0023`); the orchestrator read paths cut over in slice 4 and `craft_discipline_aliases` retires then. Temporary craft-row duplication across the two tables during 3a→4 is expected and harmless (nothing reads the new table until the cutover).

Other Layer-0 changes:
- `craft_terrain_compatibility` stays (craft-only; gear has none — Decision 6).
- `sport_specific_gear_toggles`: the catalog folds into the unified **gear registry** (slice 6); `gated_discipline_ids` migrates into `gear_discipline_aliases`; **`paired_equipment_categories` is dropped** (unused); `also_satisfies` is subsumed by multi-row aliases.

### 5.4 Gym-equipment boundary cleanup (extends #623) — **DONE (#919, slice 2)**
Removed craft/gear-covered items from `equipment_items` + `equipment_required`. Gating is purely at the gear/craft (toggle) level; gym equipment retains only proxy machines (ski-erg, trainer, paddle-erg, treadmill, rower) and genuine gym kit. **Snowshoes + Rollerskis kept** (Andy 2026-06-23) — they are cardio-enabling gear, not strength-exercise gates (Snowshoes already enables D-017 via its toggle; Rollerskis enables D-028 per Decision 10).

### 5.5 `gear_id` keyspace (NEW v3 — Decision 12)

One closed, stable, snake_case keyspace shared by `athlete_gear`, `gear_discipline_aliases`, `athlete_gear_locale`, `brought_gear`, and the picker. Stable across Layer-0 re-versioning (never the toggle integer `id`).

| gear_id | group_kind | source |
|---|---|---|
| `road_bike`, `gravel_bike`, `mountain_bike`, `tt_bike` | `bike` | existing craft slugs (unchanged) |
| `kayak`, `canoe`, `packraft`, `raft`, `sup` | `paddle` | existing craft slugs (unchanged) |
| `classic_xc_ski` | `ski` | toggle "Classic XC ski setup" |
| `skate_xc_ski` | `ski` | toggle "Skate XC ski setup" |
| `rollerskis` | `ski` | **new (Decision 10)** |
| `snowshoes` | `snow` | toggle "Snowshoeing setup" |
| `climbing_gear` | `climbing` | rolled-up climbing toggle |
| `mountaineering` | `alpine` | toggle "Mountaineering" |
| `skimo_at` | `alpine` | toggle "Skimo / AT setup" |

`group_kind` is the substitute-grouping discriminator the cascade + UI use; the fidelity walk for a discipline gathers **all** gear aliasing to it regardless of `group_kind` and picks the lowest `fidelity_rank` owned. (Rollerskis share `group_kind='ski'` with the XC setups so they group together in the picker and as D-028 substitutes.)

## 6. Feasibility cascade — `gear/craft (+skill)` (the core — slice 4)

Per included discipline `D`, in `_gather_feasibility_inputs` / `resolve_*_feasibility`:

1. **Skill gate** (if `D` has a `skill_capability_toggles` row): skill absent → STRENGTH. Present → continue.
2. **Gear/craft gate** — gather the athlete's owned/available gear+craft that aliases to `D`, and walk **ascending `fidelity_rank`**:
   - lowest-rank owned gear/craft **and** the discipline's required terrain present → full-fidelity (**EXACT**).
   - else a higher-`fidelity_rank` owned gear/craft, or real gear on a gap-rule proxy terrain → substitute (**PROXY**). *Rollerskis (rank 2, dryland) resolve here on their own pavement terrain even when D-028's snow terrain is absent — the off-season XC path.*
   - else a **gym proxy machine** for `D` (`session_feasibility._DISCIPLINE_INDOOR_MACHINES` — the ski-erg path) → degraded cardio (**INDOOR**). Gear-independent.
   - else → STRENGTH.
3. Disciplines with no gear/craft alias and no skill gate (running) → feasible on terrain alone.

Maps onto the existing 4 tiers (EXACT/PROXY/INDOOR/STRENGTH); only the *inputs* change (gear participates; the ordinal rank chooses among same-discipline gear). The un-starving: feed `cluster_gear_toggle_states` (+away set) from `athlete_gear` at both 2C call sites.

### 6a. Gear-gated cardio drills (NEW v3 — Decision 11; slice 3b)

The live `cardio_drills[]` block (`0017`/`0018`, PR #750) is pool-derived: `compute_cardio_drill_pool_ids` (per_phase.py) already gates drills on athlete context (the **constituent-sport gate** — brick drills appear only with both cycling + running disciplines). Gear-gating is the same shape:

- **New relation `cardio_drill_gear_requirements (exercise_id, gear_id)`** (Layer 0) — a drill requires the listed gear.
- `compute_cardio_drill_pool_ids` reads it and **drops a drill from the pool when the athlete lacks the gear** (reads `athlete_gear`, like the constituent-sport gate reads disciplines). A paddle-set drill never enters the pool without `paddles` owned.
- **Not** a discipline-feasibility gate (D-004 stays feasible on water) and **not** `equipment_required` (Decision 4/§5.4 stripped gear from there).
- Interplay: D-004 already carries an evidence-based **paddle-use injury caution** (limit paddle sets to ~1×/wk, PMC5983428); gating on real paddle ownership lets that caution key off actual gear rather than assume it.
- Swim gear vocab to seed: `pull_buoy`, `paddles`, `kickboard`, `fins`/`snorkel` as needed (Trigger #2 — confirm the minimal set against the active swim-drill EX rows before seeding; no padding).

## 7. "Bring it with me" (slice 5)
Generalize `_build_event_window_overlay`: union standing `athlete_gear_locale` + `brought_gear`, split by `group_kind`, into the away environment's gear/craft inputs, and **re-resolve the away environment's feasibility + 2C** for that segment.

## 8. Validation
Closed-set `gear_id` against the §5.5 keyspace / active registry; `group_kind` from the catalog; `access ∈ {own, access}`; `locale` must be an athlete locale; `fidelity_rank` integer ≥ 0. Stale `gear_id` rows are inert (picker/cascade read active catalog rows only).

## 9. Caching / invalidation (Trigger #3)
- `athlete_gear` change → evict the feasibility/2C entry points (`plan_create`/`plan_refresh`); re-home `_collect_athlete_crafts` to read `athlete_gear` so craft + gear share one eviction story.
- `athlete_gear_locale` / `brought_gear` change → `plan_create`/`plan_refresh`.
- Catalog/alias change (Layer 0) → rides the `0A/0C` digest bump.

## 10. UX / IA (slice 6)
One **"Your gear"** surface (crafts + gear together, grouped by `group_kind`), each row own/have-access + a **"bring it"** affordance. The unified **gear registry** (folding `sport_specific_gear_toggles` catalog + craft labels, keyed by §5.5) is the picker + validator source. Replaces the two craft pickers; first capture for gear.

## 11. Migration
- **Public (auto):** create `athlete_gear`, `athlete_gear_locale`; add `brought_gear`; backfill from the craft CSVs + `athlete_craft_locale` + `brought_craft`; drop the old columns after verify.
- **Layer 0 (`layer0-apply`):** `0023` builds `gear_discipline_aliases` (+`fidelity_rank`; craft rows rank 0; gear toggles; D-028 ladder incl. rollerskis); later, drop `paired_equipment_categories`; `cardio_drill_gear_requirements` + swim seeds (3b).

## 12. Coaching flags
- `toggle_off_for_discipline` (#298) becomes real and moves from flag-only to feasibility.
- New: a **degraded-fidelity** note when a session runs on degraded gear or a gym proxy (e.g. "XC programmed on rollerskis — no snow available" / "…on the ski-erg — you don't have ski gear here"), reusing the PROXY/INDOOR substitute-flag surface.

## 13. Edge cases
- Own Classic+Skate+Rollerskis, snow present → Classic (rank 0, EXACT). Snow absent → Rollerskis (rank 2, PROXY, dryland). Own only rollerskis → rollerskis PROXY year-round. None + gym ski-erg → INDOOR. None → strength.
- Climbing with skill but no gear (or gear but no skill) → strength.
- Swim drill needing paddles, paddles not owned → drill absent from the pool; swimming itself still feasible.
- Bring gear already standing in the away cluster → set-union de-dupes.

## 14. Performance
Two indexed `athlete_gear` reads per cone (replacing the CSV parse). Away path adds one feasibility+2C re-resolve per away window. No new LLM calls.

## 15. Build slices (re-sequenced v3; each ≤5 substantive files)
1. **L0 catalog + aliases (toggle fold)** — **DONE** (`0022`).
2. **Equipment boundary de-drift** — **DONE** (#919).
3. **Public athlete store + repo + backfill** — `athlete_gear`/`athlete_gear_locale`/`brought_gear`; backfill from the craft CSVs/locale/brought; new unified `athlete_gear_repo` (collapses `athlete_crafts_repo` + `athlete_craft_locale_repo`); eviction (§9). *(Old craft path stays live; cutover is slice 4.)*
3a. **L0 `gear_discipline_aliases` + ordinal fidelity + rollerski ladder** — migration `0023` (this PR): create the table with integer `fidelity_rank`; migrate craft aliases (rank 0); seed gear-toggle rows + the D-028 ladder (Classic 0 / Skate 1 / Rollerskis 2) per §5.5.
3b. **Swim-gear cardio-drill gate** — `cardio_drill_gear_requirements` + the `compute_cardio_drill_pool_ids` gear gate (§6a); swim-gear vocab seed.
4. **Cascade wiring** — re-home `_collect_athlete_crafts`/`_q_craft_*` onto `athlete_gear`/`gear_discipline_aliases`; feed gear into both 2C sites; ascending-`fidelity_rank` walk + skill composition (§6); retire `craft_discipline_aliases`.
5. **Away overlay** — generalize `_build_event_window_overlay` + away re-resolve (§7).
6. **Capture UX + unified gear registry** — the "Your gear" surface + onboarding parity + the picker/validator registry (§10).

## 16. Sign-offs
- **v2 (Andy 2026-06-22):** §4 catalog table; skimo toggle; deletions; §5/§9 schema + invalidation; proxy map (`_DISCIPLINE_INDOOR_MACHINES` covers every gear discipline; Elliptical added as a stride proxy). *(All resolved; carried.)*
- **v3 (Andy 2026-06-23) — Trigger #2 + #3:**
  - **D1 ordinal `fidelity_rank`** (integer, 0=best) ratified; D-028 ladder Classic 0 / Skate 1 / Rollerskis 2; ski-erg stays gear-independent INDOOR.
  - **D2 gear→cardio-drill gate** ratified: swim gear gates `cardio_drills[]` pool membership (a new `cardio_drill_gear_requirements` relation read by `compute_cardio_drill_pool_ids`), never discipline feasibility, never `equipment_required`.
  - **D3 `gear_id` keyspace** (§5.5) pinned — snake_case craft slugs + toggle-derived slugs + new `rollerskis`.
  - **Rollerski promotion + `Provider_Inbound_Matrix_v2` §12 reconciliation** ratified (Decision 10) — footnote owed on the matrix.

## 17. Test scenarios
- Owns Classic XC → D-028 EXACT (snow); Skate only → PROXY; **rollerskis only → PROXY dryland** (snow or not); none + gym ski-erg → INDOOR; none → strength.
- Owns climbing gear + skill → D-012 EXACT; gear xor skill → strength.
- Brings climbing gear to an away window → D-012 feasible in that segment only.
- Swim-drill-needs-paddles + paddles owned → in pool; paddles absent → not in pool; swimming feasible either way.
- Deleted toggles appear nowhere; no exercise gates on a deleted item.

## 18. Gut check
- **Strength:** ordinal rank is one integer column on an unbuilt table (free now); the drill-gear gate clones a live, tested gate; no new tier, no new session kind, no prompt change.
- **Biggest risk:** the slice-4 away re-resolve + confirming the gym proxy rows exist (§16); the public backfill (slice 3) has quiet failure modes (group_kind misroute, dropped craft) — reuse the #623 verify pattern, and stage it as its own PR since it auto-applies to prod.
- **What to watch:** rollerski's dryland-terrain carve-out (Decision 6 exception) must be handled in the slice-4 PROXY resolution, not silently demanded snow.
- **Best argument against scope:** slices 3/3a are inert until slice 4 wires the cascade; if behaviour is wanted fastest, 3a+4 deliver "rollerski before ski-erg" without the full store migration. Andy chose the full merge for one-source-of-truth; 3a is built first as the foundation that encodes the freshly-ratified fidelity decision.
