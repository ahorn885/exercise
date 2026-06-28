# #884 Slice 4 — Cascade Cutover + S6 Write-Path Forward — Implementation Plan v1

**Design:** `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` (§5.3, §6, §9, §15.4)
**Predecessors:** S1–S3b MERGED (PR #932, `42216e1`, 2026-06-28); `0025` applied (run #17).
**Branch:** `claude/gear-gated-cardio-drills-xd9q0l` (harness-pinned; kept).
**Decisions (Andy 2026-06-28):** close the read/write authority gap by **pulling the S6 write
path forward** (option b) — capture writes `athlete_gear` directly; **write-path only**, no new
"Your gear" UX surface (that stays S6 proper).

This is a cross-layer change (stop-and-ask trigger). Sub-sliced so each unit is reviewable and
the cascade never reads a store the capture surface isn't writing.

---

## Grounding (verified file:line)

**Read path (today, legacy):**
- `layer4/orchestrator.py:215` `_collect_athlete_crafts(layer1_payload)` — reads
  `layer1_payload.discipline_baselines.{paddling.paddle_craft_types, cycling.bike_types_available}`.
  Returns sorted craft slugs. Callers: `_gather_feasibility_inputs` (`:513`), the substitution
  call (`:1229`).
- `layer4/orchestrator.py:335` `_q_craft_discipline_aliases` → `layer0.craft_discipline_aliases`
  (`{craft_name:[discipline_id]}`); `:362` `_q_craft_group_kind` (DISTINCT craft_name,group_kind);
  `:374` `_q_craft_terrain_compatibility` → `craft_terrain_compatibility` (**stays**).
- `layer4/session_feasibility.py:365` `resolve_craft_terrain_feasibility` — 7-tier cascade, gated
  to `_CRAFT_GROUP_KINDS = {bike, paddle}` (`:362`); **no fidelity_rank**. Non-craft kinds return
  `None` → caller runs `resolve_terrain_feasibility` (terrain-only).
- `layer4/orchestrator.py:1098` 2C call passes `cluster_gear_toggle_states={}` (always empty today).

**New store (S3, staged, unread):**
- `athlete_gear_repo.py:85` `get_athlete_gear(db,uid)` → `[{gear_id,group_kind,access}]`.
- `:104` `replace_athlete_gear(db,uid,owned:{gear_id:access})`; `:155` `replace_gear_locale`.
- `GEAR_REGISTRY` (`:51`): bikes/paddles + `classic_xc_ski/skate_xc_ski/rollerskis`(ski),
  `snowshoes`(snow), `climbing_gear`(climbing), `mountaineering/skimo_at`(alpine), + swim (drill).
- `gear_discipline_aliases` (0024): the 22-row map incl. the D-028 ladder ranks 0/1/2
  (classic/skate/rollerskis) and climbing_gear→{D-012,D-013,D-014}, snowshoes→D-017,
  mountaineering→D-018, skimo_at→{D-021,D-022}.

**Write path (today):**
- Crafts: `routes/profile.py:691` `/profile/crafts` + `routes/onboarding.py:509` →
  `athlete_crafts_repo.replace_athlete_crafts` (`:62`, writes `discipline_baseline_{cycling,paddling}`).
- Per-locale crafts: `athlete_craft_locale_repo.replace_craft_locale` (`:49`).
- Gear toggles (climbing/ski/snow/alpine): **#298 starved** — `sport_specific_gear_toggles` is
  read-only at runtime, no active capture. The skill tab writes `athlete_skill_toggles` for the
  *skill* vocab (climbing_roped, mountaineering-skill, via_ferrata, whitewater, open-water) — that
  is the SKILL gate (cascade §6 step 1), separate from gear.

**Backfill (S3) seeded crafts only** → `athlete_gear` holds bikes/paddles, NOT the gear toggles.

---

## The fidelity-rank cascade (§6 — the new algorithm, 4.1b)

Generalize `resolve_craft_terrain_feasibility` from `{bike,paddle}` to every gear-aliased
`group_kind`, driven by `gear_discipline_aliases` (gear_id → discipline_id, group_kind,
fidelity_rank). Per included discipline D:

1. **Skill gate** (unchanged, §6 step 1): D has a `skill_capability_toggles` row and the skill is
   absent → STRENGTH. Present (or no skill row) → continue.
2. **Gear gate** — gather owned gear aliasing to D (via `athlete_gear` ∩ `gear_discipline_aliases`
   for D), **walk ascending `fidelity_rank`**:
   - lowest-rank owned gear **and** D's required terrain present in-cluster → **EXACT**.
   - else a higher-rank owned gear on required terrain, **or** owned gear on a gap-rule proxy
     terrain → **PROXY**. *Rollerskis (rank 2, dryland): resolve on their own pavement terrain
     even when D-028 snow is absent — the carve-out; do NOT silently demand snow.*
   - else a gym proxy machine for D (`_DISCIPLINE_INDOOR_MACHINES`, gear-independent) → **INDOOR**.
   - else → **STRENGTH**.
3. Disciplines with no gear alias and no skill gate (running) → terrain-only cascade (unchanged).

Maps onto the existing 4 tiers (EXACT/PROXY/INDOOR/STRENGTH); only the *inputs* change. The bike/
paddle path must produce **identical** results to today (the rank-0 single-tier case == current
tiers 1–4) — regression tests pin this.

**Rollerski terrain:** D-028 required terrain = snow (TRN-012). Rollerskis need a dryland/pavement
terrain. Encode via `craft_terrain_compatibility` rows for rollerskis (pavement) so the existing
"own craft, ride alternate terrain it's compatible with" PROXY branch fires — verify those rows
exist or add them in 4.3's Layer-0 work; until then rollerskis PROXY only if dryland terrain is in
the gap-rule/terrain set. (Confirm against `craft_terrain_compatibility` before coding 4.1b.)

---

## Sub-slices

### 4.1a — Read cutover (safe; behavior-preserving) — SHIPPABLE FIRST
Repoint the three readers onto the new store, keeping bike/paddle behavior identical.
- `_collect_athlete_crafts`: read `get_athlete_gear(db,uid)`, filter to discipline-unlocking
  group_kinds (exclude swim), return sorted gear_ids. Needs `db`+`user_id` (currently pure on
  `layer1_payload`) — thread them at both call sites. Until 4.2 backfills toggles, only bikes/
  paddles are present, so output == today.
- `_q_craft_discipline_aliases` / `_q_craft_group_kind`: read `gear_discipline_aliases`
  (filter `group_kind != 'swim'`); keep return shapes. `_q_craft_terrain_compatibility` unchanged.
- Tests: existing `test_layer4_craft_feasibility.py`, `test_layer4_terrain_feasibility_wiring.py`,
  `test_layer2c.py`, `test_layer2_substitution.py` stay green (repoint their patches/fixtures).
- Files: `layer4/orchestrator.py` (+ the substitution call site), `layer2_modality/substitution.py`
  (param doc), tests. ~3–4 substantive.

### 4.1b — Cascade extension (new behavior) — needs the rank walk above
- `session_feasibility.py`: expand `_CRAFT_GROUP_KINDS` to all gear kinds; thread `fidelity_rank`
  (new `_q_gear_aliases` returning rank); implement the ascending-rank walk + rollerski carve-out.
- Feed `cluster_gear_toggle_states` from `athlete_gear` at `orchestrator.py:1098` (un-starve 2C).
- Tests: rank-walk (classic>skate>rollerski), rollerski-dryland, climbing gear+skill matrix.
- Files: `session_feasibility.py`, `orchestrator.py`, `layer2c/builder.py`, tests. ~4 substantive.

### 4.2 — Write-path forward (close the gap; un-starve capture)
- Repoint craft capture (`/profile/crafts`, onboarding) to `replace_athlete_gear`; add a capture
  path for the discipline-unlocking gear toggles writing `athlete_gear` (reuse the existing
  checkbox-form pattern; no new surface). One-time backfill of any pre-existing toggle state.
- Decide the fate of `discipline_baseline_{cycling,paddling}.{bike_types_available,
  paddle_craft_types}`: find all readers; if `athlete_gear` is now authoritative, stop writing
  them (or keep in sync) — mechanical, resolve at build.
- Files: `routes/profile.py`, `routes/onboarding.py`, repos, backfill, tests.

### 4.3 — Layer-0 redump + equipment strip (clean follow-up)
- Retire `craft_discipline_aliases` (forced redump, `layer0-redump` → new baseline → gate → apply).
- Strip `pull_buoy`/`kickboard`/`Swim fins` from `equipment_items` + EX126/EX128
  `equipment_required` (0B supersede+re-insert; global cache invalidation). New migration `0026`.
- `craft_terrain_compatibility` rollerski/pavement rows if 4.1b needs them.

---

## Resolved decisions (Andy 2026-06-28)
- **Order:** 4.2 (write-path forward) before 4b (cascade extension).
- **Rollerski dryland terrain (4b/4.3 Layer-0):** **reuse an existing paved terrain** — map
  `rollerskis` to the road/paved `TRN-xxx` `road_bike` already rides (no new terrain vocab).
  Verify the exact paved `TRN` id from `craft_terrain_compatibility` (road_bike rows) before
  seeding the ski-gear terrain rows; classic/skate → snow `TRN-012`.
- **4.2 gear-toggle capture:** reuse the profile gear tab's checkbox pattern (no new "Your gear"
  UX); expose the discipline-unlocking GEAR_REGISTRY set (climbing_gear, snowshoes, mountaineering,
  skimo_at, classic/skate/rollerskis). Gear toggles were #298-starved (never captured) → no
  backfill owed; capture starts going forward. Crafts (bikes/paddles) repoint to write athlete_gear.

**End of plan v1.**
