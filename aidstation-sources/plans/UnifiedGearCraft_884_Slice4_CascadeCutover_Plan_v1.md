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
- **Rollerski dryland terrain (4b Layer-0):** **reuse existing paved terrain, no new vocab.**
  Resolved ids: `road_bike` rides `TRN-001` (Road / Paved) + `TRN-004` (Hill / Rolling); D-028's
  required terrain is `TRN-012` (snow). So the ski-gear `craft_terrain_compatibility` seed (new
  migration `0026`): `classic_xc_ski`→`TRN-012`, `skate_xc_ski`→`TRN-012`, `rollerskis`→`TRN-001`.
  rollerskis on `TRN-001` (≠ the required snow) resolves via the existing "own craft, ride an
  alternate compatible terrain" PROXY tier — the carve-out falls out of the structure.
- **4.2 gear-toggle capture:** reuse the profile gear tab's checkbox pattern (no new "Your gear"
  UX); expose the discipline-unlocking GEAR_REGISTRY set (climbing_gear, snowshoes, mountaineering,
  skimo_at, classic/skate/rollerskis). Gear toggles were #298-starved (never captured) → no
  backfill owed; capture starts going forward. Crafts (bikes/paddles) repoint to write athlete_gear.

**End of plan v1.**

---

## Slice 4b execution addendum (2026-06-28)

Written while picking the next #884 build after #196 Phase 4 Slice 2 merged. Grounds the
remaining 4b work in on-disk + on-`main` state and records two findings that reshape how 4b
must be sub-sliced. **No 4b code shipped this session** — 4b is Andy's-go-gated (cross-layer +
over-ceiling-as-one-unit); this addendum is the spec-first "propose splitting before starting"
step (5-file-ceiling rule).

### Status reconciliation (on `main`)
- **4.1a (read cutover) + 4.2 (craft write-sync) are MERGED** — PR **#937**, commit `e70e520` on
  `main`. (CARRY_FORWARD's slice-4 PROGRESS line was written pre-merge and still said
  "DONE+pushed / PR gated"; reconciled this session.)
- **Remaining 4b** = the gear-toggle **capture** surface + the **cascade extension**
  (fidelity-rank walk + rollerski carve-out + 2C `cluster_gear_toggle_states` feed) + **migration
  `0026`** (ski-gear `craft_terrain_compatibility` rows). Then **4.3** (redump retiring
  `craft_discipline_aliases` + the EX126/EX128 equipment strip).

### Finding 1 — migration `0026` is version-digest-coupled to the cascade (do NOT ship it standalone)
`craft_terrain_compatibility` is **already a live-read Layer-0 table** and is in
`_LAYER0_TABLE_FAMILY` → "0A" (`layer4/orchestrator.py:2003`), so it feeds
`_q_current_etl_version_set` (`:2031`). That digest is built from the **DISTINCT `etl_version` per
table** (`SELECT DISTINCT … etl_version … WHERE superseded_at IS NULL`, `:2051-2056`), not row
contents. So:
- Stamping `0026`'s rows with a **fresh** `etl_version` adds a DISTINCT value → the **0A digest
  changes → a global plan-gen cache invalidation** (every plan folding `etl_version_set`
  re-synthesizes) — *even though nothing reads the new ski rows until the cascade extension lands*
  (cascade still gated to `{bike,paddle}`, `session_feasibility.py:362`).
- Stamping them with an **existing** `etl_version` dodges the invalidation but muddies provenance
  and breaks the `0024`/`0025` "delete-this-version-then-insert" idempotency isolation — a hack.
- **Therefore `0026` must co-land with the cascade extension that reads it (4b-ii)** so the one
  (justified) invalidation coincides with the behavior change. This differs from `0024`/`0025`,
  which created *new, unread* tables (no family-map coupling). It is a Trigger #3 (cross-layer
  serving) event when it lands → Andy's go on the invalidation.

### Finding 2 — the capture surface needs a slug→label decision (not a mechanical mirror)
The gear-toggle capture form writes the discipline-unlocking `GEAR_REGISTRY` slugs
(`classic_xc_ski`, `skate_xc_ski`, `rollerskis`, `snowshoes`, `climbing_gear`, `mountaineering`,
`skimo_at`) via `replace_owned_gear_for_kinds(..., {ski,snow,climbing,alpine})`. The
`_skills_form.html` precedent sources checkbox copy from a Layer-0 vocab table — but
`sport_specific_gear_toggles` keys its rows by **human strings** ("Classic XC ski setup",
"Touring/AT ski setup", "Climbing — roped", "Snowshoeing setup", "Mountaineering") that **do not
map 1:1 to the slugs**, and there is **no `rollerskis` row at all** (new §5.5 slug). So capture
needs either a small slug→label display map + net-new rollerski copy, or a vocab add — **user-facing
copy (coaching voice) / possible Trigger #2** → Andy's decision, not a unilateral pick.

### Ceiling-respecting decomposition
Full 4b (capture + cascade + `0026`) is ~6 substantive files. Andy's pinned decision #4 ("capture
must write the store before the gate bites") forbids shipping the cascade extension first (it would
re-resolve ski/climbing disciplines from today's terrain-only fallthrough to strength/indoor on
empty owned-gear). Split:
- **4b-i — gear-toggle capture (behavior-INERT, ~3-4 files).** New `/profile/gear-toggles` POST
  mirroring `save_crafts` (`routes/profile.py:691`) → `replace_owned_gear_for_kinds(..., {ski,snow,
  climbing,alpine})` + `evict_layer1_on_gear_change`; a `_gear_toggles_form.html` partial mirroring
  `_crafts_form.html` on the profile gear tab (`edit.html:319`); tests; onboarding mirror optional.
  **Public-schema `athlete_gear` only → no migration, no version digest, no cache invalidation.**
  Output-inert: the cascade ignores ski/climbing/snow/alpine owned-gear until 4b-ii, so the
  eviction only forces an identical re-synth on the athlete's *own* explicit save (expected).
  Satisfies decision #4. **Blocked on Finding 2** (the slug→label copy decision).
- **4b-ii — cascade extension + `0026` co-landed (behavior-CHANGE, ~5 files).**
  `session_feasibility.py` (expand `_CRAFT_GROUP_KINDS`; thread `fidelity_rank`; ascending-rank
  walk; rollerski carve-out falls out of the existing Tier-2 "own craft, ride alternate compatible
  terrain"); `orchestrator.py` (a `fidelity_rank`-returning gear-alias reader + un-starve the 2C
  `cluster_gear_toggle_states` feed at `:1098`); **migration `0026`** co-landed (Finding 1); tests
  (rank-walk classic>skate>rollerski; rollerski-dryland PROXY; **bike/paddle regression identical
  to today**; climbing gear+skill matrix). Carries the Trigger #3 invalidation + `layer0-apply`.
- **4.3 — redump + equipment strip.** Unchanged from the plan body above.

### Recommendation
Build **4b-i first** (after Andy rules on the Finding-2 copy/vocab approach), then **4b-ii**. Each
PR ≤ 5 files and reviewable; the digest foot-gun (Finding 1) is resolved by co-landing `0026` with
its consumer. **Open decisions for Andy:** (i) resume #884 4b now vs. pivot to #196 Phase 5;
(ii) the 4b-i slug→label copy/vocab approach; (iii) acknowledge the 4b-ii cross-layer cache
invalidation when `0026` lands.

**End of plan (v1 body + 2026-06-28 4b addendum).**
