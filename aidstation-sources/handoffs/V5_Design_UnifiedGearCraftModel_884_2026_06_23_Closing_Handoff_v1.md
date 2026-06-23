# V5 Design — #884 Unified Gear/Craft Model + `gear/craft (+skill)` Feasibility — Closing Handoff

**Date:** 2026-06-23
**Branch:** `claude/eager-cannon-6493be`
**Design (the deliverable):** `aidstation-sources/designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v2.md` (RATIFIED)
**Superseded:** `archive/superseded-specs/Unified_Gear_Model_BringingItWithMe_884_Design_v1.md`
**PR:** none yet — pending Andy's go (per the PR-gated operating model). Bookkeeping committed to the branch to ride the PR when it opens.
**Issue:** #884 (go-live blocker, user-facing); closes the live part of #298 (starved gear-toggle subsystem).

Design-only session. **No code, no migration, no test delta.** This is a spec-first pass (Andy: "design doc first, sign off, then build").

---

## 1. What this is

Crafts (bikes/boats) and "gear toggles" (`sport_specific_gear_toggles`) are the same thing — athlete-owned **portable** equipment — but only crafts are wired through. #884 merges them into one **gear/craft** concept. The session iterated through several wrong framings (v1 assumed gear toggles expand an *equipment pool*; the live data disproved it) before landing the ratified model below.

## 2. The ratified model (Andy, 2026-06-22 → 2026-06-23)

1. **Gear = crafts.** Athlete-owned, portable, home-by-default, made available away by attaching to a **locale** (standing) or **event window** (per-trip) — gear gets the exact plumbing crafts have.
2. **Gym equipment is the PROXY tier, not the gear.** Own the ski setup → real skiing; no setup but a gym **ski-erg** → degraded; neither → strength. (A bike is a craft, not gym equipment.)
3. **Gate at the toggle level, never on individual equipment** that's part of a toggle (extends #623's de-drift).
4. **Feasibility = `gear/craft (+ skill where applicable)`**, over the existing 4 tiers EXACT/PROXY/INDOOR/STRENGTH. Running gates on neither; cycling on craft; climbing on gear **and** skill.
5. **Gear gets discipline aliases, no terrain** (terrain stays craft-only — a craft picks terrain *within* a discipline; gear has no such split).
6. **Gear options are fidelity-ranked** (Classic XC = primary, Skate = degraded). The rank slots onto the existing tiers: primary gear = EXACT, degraded gear = PROXY, gym machine = INDOOR, none = STRENGTH.
7. **Pack-load is out** (coaching-LLM concern).

## 3. The catalog (canon-backed; all deletions verified against `discipline_canon.py`)

| Toggle | Action | Disciplines | Rank |
|---|---|---|---|
| Bouldering, Fencing setup, Shooting setup | **DELETE** (orphans — D-025/026/029 removed May 2026) | — | — |
| Whitewater paddling setup | **DELETE** (→ craft) | — | — |
| Climbing—roped + Rappelling/abseiling + Via ferrata | **ROLL UP → one "Climbing gear"** | D-012, D-013, D-014 | primary |
| Classic XC ski setup | keep + wire | D-028 | **primary** |
| Skate XC ski setup | keep + wire | D-028 | **degraded** |
| Mountaineering | keep + wire | D-018 | primary |
| Snowshoeing setup | keep (already wired) | D-017 | primary |
| **"Skimo / AT setup"** (alpine-touring skis, climbing skins, AT bindings, AT boots) | **ADD (new vocab — Trigger #2 ratified)** | D-021, D-022 | primary |

Crafts keep their existing `craft_discipline_aliases` + terrain rows unchanged. The **Elliptical** (only unused `Machines - Cardio` item) is added to `_DISCIPLINE_INDOOR_MACHINES` as a stride proxy: D-001/002 (after Treadmill), D-003/017/024 (after Stair climber), D-028 (after Ski erg).

## 4. Schema (Trigger #3 — approved)
- **NEW public-schema (auto-applies on deploy):** `athlete_gear (user_id, gear_id, group_kind, access)`; `athlete_gear_locale (user_id, gear_id, locale)` (generalizes `athlete_craft_locale`); `brought_gear` (generalizes `athlete_event_windows.brought_craft`).
- **Layer 0 (via `layer0-apply` Action):** extend `craft_discipline_aliases` → **`gear_discipline_aliases (gear_id, discipline_id, group_kind, fidelity_rank)`** (migrate craft rows at `primary`; add the gear rows from §3); **drop `paired_equipment_categories`** (unused — all 12 toggles carry `{}`); the gear-toggle catalog folds into the unified gear catalog (picker/validator source).
- Re-home owned crafts off the Layer-1 baseline payload → a cone/feasibility input read directly from `athlete_gear` (so craft + gear share one eviction story: `plan_create`/`plan_refresh`).

## 5. Build plan — 6 slices (design §15), each ≤5 substantive files
1. **L0 catalog + aliases** — delete/roll-up/add-skimo; `gear_discipline_aliases (+fidelity_rank)`; drop `paired_equipment_categories`. New `etl/migrations/layer0/NNNN_*.sql` (**check `etl/migrations/layer0/` for the next number — 0012 was the last referenced**); apply via `layer0-apply`. Mirror #623's `0008` / #622's `0007` migration + verify-DO-block pattern.
2. **Equipment boundary de-drift** — strip craft/gear items from `equipment_items` + exercises' `equipment_required` (extends `0008`); reuse #623's verify pattern.
3. **Athlete store + migration + repo** — the three public tables; backfill from `bike_types_available`/`paddle_craft_types` CSVs + `athlete_craft_locale` + `brought_craft`; collapse the craft repos into one `athlete_gear_repo`; eviction.
4. **Cascade wiring** — re-home `_collect_athlete_crafts` to read `athlete_gear`; feed gear into both 2C call sites (`orchestrator.py` full-cone + single-session, today hard-coded `cluster_gear_toggle_states={}`); the fidelity-rank walk + skill composition in `session_feasibility.resolve_*`; the Elliptical map edit.
5. **Away overlay** — generalize `_build_event_window_overlay` (union standing `athlete_gear_locale` + `brought_gear`, split by `group_kind`) + re-resolve the away env's feasibility + 2C.
6. **Capture UX** — one "Your gear" surface (crafts + gear) in the #894 profile group (already shipped) + onboarding parity; generalize the per-locale "kept here" + event-window "bring" controls.

## 6. Open items — NONE (all Trigger #2/#3 sign-offs cleared, design §16). Build-ready.

### 6.1 OWED (not blocking the build)
- Open the PR on Andy's go; then comment #884 (+ #298) with the PR ref and close #298's live part when slice 4 lands.

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md`. 4. This handoff. 5. `./scripts/verify-handoff.sh`. Then read the **design doc** (it carries the full 18-section detail — model, schema, cascade algorithm §6, migration §11, test scenarios §17, gut check §18).

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Design v2 (deliverable) | `aidstation-sources/designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v2.md` | header `Status: RATIFIED`; §4 catalog table; §6 `gear/craft (+skill)` cascade; §15 six slices; §16 "ALL RESOLVED" |
| v1 archived | `aidstation-sources/archive/superseded-specs/Unified_Gear_Model_BringingItWithMe_884_Design_v1.md` | present (git mv); not in `designs/` |
| CURRENT_STATE | `aidstation-sources/CURRENT_STATE.md` | top entry "DESIGN — #884 UNIFIED GEAR/CRAFT MODEL"; prior #213 entry demoted to "### Predecessor — #213 3D gate revise links" |
| Catalog facts | `etl/output/layer0_etl_v1.8.0.sql` | 12 active `sport_specific_gear_toggles` rows; all `paired_equipment_categories = '{}'`; only D-012/013/017 have `gated_discipline_ids` |
| Deletions backed | `etl/layer0/discipline_canon.py` | `REMOVED_IDS` = D-020/023/025/026/029 (fencing/shooting/laser-run already gone) |
| Proxy map | `layer4/session_feasibility.py` | `_DISCIPLINE_INDOOR_MACHINES` (lines ~96-119); `Elliptical` is the only unused `Machines - Cardio` item |
| No code | — | NO DDL, NO migration, NO test change this session (design-only) |
| Build start | `etl/migrations/layer0/` | slice 1 = next migration number after the highest present |
