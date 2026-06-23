# Unified Gear/Craft Model + `gear/craft (+skill)` Feasibility — Design v2

**Date:** 2026-06-22
**Issue:** #884 (go-live blocker — user-facing). Closes the live part of #298 (starved gear-toggle subsystem).
**Status:** RATIFIED (Andy, 2026-06-22 → 2026-06-23) — all Trigger #2/#3 sign-offs cleared (§16). Build-ready; six slices in §15, slice 1 (L0 catalog + aliases) first.
**Supersedes:** `Unified_Gear_Model_BringingItWithMe_884_Design_v1` (archived). v1's premise (gear toggles expand an *equipment pool*) was wrong — the live data shows all 12 toggles carry `paired_equipment_categories = {}`; gear unlocks *disciplines*, not equipment. v2 is built on that correction.

## Ratified decisions (Andy, 2026-06-22)

1. **Treat gear toggles exactly like crafts.** Gear managed by a "toggle" is athlete-owned and **portable** — usually at home, but can be taken along. Same model, same "available at this locale / during this event window" plumbing crafts already have.
2. **Full one-table merge.** One athlete-owned **gear/craft** concept; merge the stores and the Layer-0 alias relation; migrate everything.
3. **Gym equipment is the *proxy* tier, not the gear itself.** A bike is a craft, not gym equipment; if you own the ski setup you don't also need skis "at a gym." Gym equipment that's a real proxy (ski-erg, trainer, paddle-erg) **degrades** a missing gear/craft before strength does.
4. **Gate at the toggle level, never on individual equipment** that's part of a toggle.
5. **Feasibility = `gear/craft (+ skill where applicable)`.** Running gates on neither; cycling on craft only; climbing on gear **and** skill. This uniformity is the whole point of merging craft + gear.
6. **Gear gets discipline aliases, no terrain** (terrain stays craft-only — a craft picks terrain *within* a discipline; gear has no such split).
7. **Catalog:** delete bouldering/fencing/shooting toggles (orphans — their disciplines were removed May 2026) + whitewater (it's a craft); roll climbing+abseiling+via-ferrata into one climbing-gear toggle; **add a skimo/AT setup** toggle; wire the survivors.
8. **Classic XC is primary; Skate XC is a degraded option** → gear options for a discipline are **fidelity-ranked**.
9. **Pack-load is out of scope** — a coaching-LLM concern, unrelated to gear/craft.

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

Consequences: (a) gear is uncapturable and dead in prod; (b) of the 12 gear toggles only 3 even have a `gated_discipline_ids`, and an OFF toggle today only emits a 2C coaching flag — it never actually gates feasibility the way a missing bike does; (c) "bring it" is craft-only; (d) crafts and toggle-gear still pollute the per-locale gym-equipment list (#622-class bug), and exercises hard-gate on individual gear items (#623 began retiring these).

## 2. Scope & boundaries

**In:** one athlete-owned **gear/craft** model (portable; locale + event-window availability); one Layer-0 gear→discipline alias relation (fidelity-ranked); a unified `gear/craft (+skill)` feasibility cascade that un-starves the toggle subsystem; the catalog cleanup (§4); the gym-equipment boundary cleanup (§5.4).

**Out:**
- **Skill-capability toggles** — a *capability* axis, kept as its own table/path. It **composes** with gear in feasibility (climbing needs gear **and** skill) and shares the profile UI group (#894), but is not part of the merge.
- **Per-locale gym equipment** — settled; stays as-is *except* the boundary cleanup (§5.4) that removes craft/gear-covered items from it.
- **Pack-load** — coaching-LLM concern (Decision 9).

## 3. The unified concept

**Gear/craft** = an athlete-owned, **portable** thing whose presence unlocks training for one or more disciplines.
- *Craft* (bike/boat): unlocks disciplines **and** carries terrain compatibility.
- *Gear* (ski setup, climbing rack, mountaineering kit, snowshoes, skimo/AT setup): unlocks disciplines; **no terrain.**

Both are athlete-scoped, available across the whole **home cluster** by default, and made available **away** by attaching to a saved locale (standing) or an event window (per-trip). Gym equipment is a separate, location-bound thing that can act as a **proxy** for an absent gear/craft.

## 4. Catalog (ratified) — refine, don't invent

The discipline canon (`etl/layer0/discipline_canon.py`) already removed D-025 Fencing / D-026 Laser Run / D-029 Rifle Shooting ("Modern Pentathlon & Biathlon dropped as sports — Andy, May 2026"). The matching gear toggles are therefore **orphans pointing at deleted disciplines** — deleting them is cleanup, not a scope change.

| Toggle (current) | Action | Disciplines unlocked | Rank |
|---|---|---|---|
| Bouldering, Fencing setup, Shooting setup | **DELETE** | — (no discipline) | — |
| Whitewater paddling setup | **DELETE** | handled by the craft (kayak/canoe/packraft) | — |
| Climbing — roped **+** Rappelling/abseiling **+** Via ferrata | **ROLL UP → one "Climbing gear"** | D-012 Rock Climbing, D-013 Abseiling, D-014 Via Ferrata | primary |
| Classic XC ski setup | keep + wire | D-028 Cross-Country Skiing | **primary** |
| Skate XC ski setup | keep + wire | D-028 Cross-Country Skiing | **degraded** |
| Mountaineering | keep + wire | D-018 Mountaineering | primary |
| Snowshoeing setup | keep (wired) | D-017 Snowshoeing | primary |
| **Skimo / AT setup** | **ADD (new)** | D-021 Uphill Skinning, D-022 Alpine Descent | primary |

Crafts keep their existing `craft_discipline_aliases` rows unchanged (road_bike→D-006; gravel_bike→D-006/030/031; mountain_bike→D-008/031; kayak→D-010; canoe→D-011; packraft→D-009; tt_bike→D-007; sup→D-032; raft→D-019) **plus** their terrain compatibility.

Disciplines with **no** gear/craft gate (feasible on terrain/skill alone): D-001 Trail Running, D-002 Road Running, D-024 Mountain Running, D-003 Trekking, D-004 Swimming, D-027 OCR.

**Skill composition** (existing `skill_capability_toggles`, unchanged): climbing/abseiling/via-ferrata (D-012/013/014) and mountaineering (D-018) gate on **both** gear and skill; ski/snowshoe/cycling/paddling gate on gear/craft only; running on neither.

## 5. Data model — full one-table merge

### 5.1 Athlete store (NEW public-schema table; auto-applies on deploy)

```
athlete_gear (
  user_id    INTEGER NOT NULL REFERENCES users(id),
  gear_id    TEXT    NOT NULL,            -- catalog key (craft slug or toggle id)
  group_kind TEXT    NOT NULL,            -- 'bike'|'paddle'|'ski'|'climbing'|'snow'|'alpine'… (the craft_discipline_aliases discriminator, extended)
  access     TEXT    NOT NULL DEFAULT 'own',  -- 'own' | 'access'
  PRIMARY KEY (user_id, gear_id)
)
```
Replaces `discipline_baseline_cycling.bike_types_available` + `discipline_baseline_paddling.paddle_craft_types` (→ craft rows) and is the first-ever store for owned gear toggles (→ gear rows). `group_kind` is stored so read paths route without a catalog join.

### 5.2 Portable availability (generalize the craft tables)
- `athlete_craft_locale (user_id, craft_slug, locale)` → **`athlete_gear_locale (user_id, gear_id, locale)`** — "kept at this away locale."
- `athlete_event_windows.brought_craft` → **`brought_gear`** (CSV, preserving the stable-sort + `compute_event_windows_hash` convention) — "bringing it to this trip."

### 5.3 Layer 0 — extend `craft_discipline_aliases`, don't add a parallel table

Generalize `craft_discipline_aliases (craft_name, discipline_id, group_kind)` → **`gear_discipline_aliases (gear_id, discipline_id, group_kind, fidelity_rank)`**:
- existing craft rows migrate 1:1 (`fidelity_rank = primary`);
- gear toggles become rows here (the §4 mapping), so the gear→discipline relation lives in **one** table with crafts;
- **`fidelity_rank`** (`primary` | `degraded`) is the new column carrying Decision 8 — exercised today only by D-028 (Classic primary / Skate degraded), default `primary` everywhere else.

Other Layer-0 changes:
- `craft_terrain_compatibility` stays (craft-only; gear has none — Decision 6).
- `sport_specific_gear_toggles`: the catalog (id, label, description, the gear it represents) folds into the unified **gear catalog** (the registry the picker + validator read); `gated_discipline_ids` migrates into `gear_discipline_aliases`; **`paired_equipment_categories` is dropped** (unused — Decision 3/4); `also_satisfies` is subsumed by multi-row aliases (the climbing roll-up replaces the Climbing→Rappelling one-hop).

### 5.4 Gym-equipment boundary cleanup (extends #623)
Per Decision 3/4: remove craft/gear-covered items from the per-locale gym-equipment vocab (`layer0.equipment_items`) and strip them from exercises' `equipment_required`, so nothing gates on individual gear/craft items. Gating is purely at the gear/craft (toggle) level; gym equipment retains only **proxy machines** (ski-erg, trainer, paddle-erg, treadmill, rower) and genuine gym kit.

## 6. Feasibility cascade — `gear/craft (+skill)` (the core)

Per included discipline `D`, in `_gather_feasibility_inputs` / `resolve_*_feasibility` (the existing craft-terrain cascade, generalized):

1. **Skill gate** (if `D` has a `skill_capability_toggles` row): skill absent → **STRENGTH** (today's behaviour; safety substitution, #336). Skill present → continue.
2. **Gear/craft gate** — gather the athlete's owned/available gear+craft that aliases to `D` (home cluster, or the away set in an event window — §7), and walk fidelity:
   - **primary** gear/craft owned **and** the discipline's required terrain present → full-fidelity real session (**EXACT**). Terrain is the *discipline's*, not the gear's (Decision 6): XC skiing needs skis **and** snow for EXACT, exactly as cycling needs the bike **and** the terrain.
   - else **degraded**-rank gear/craft, or real gear on a gap-rule proxy terrain → substitute (**PROXY**).
   - else a **gym proxy machine** for `D` in the locale's pool → degraded cardio (**INDOOR**). This tier is **gear-independent** — the existing `session_feasibility._DISCIPLINE_INDOOR_MACHINES` map (the "ski-erg when you don't own skis" path).
   - else → **STRENGTH**.

   The INDOOR map already covers the gear disciplines (ski/snowshoe/mountaineering), so the merge only adds the **gear-ownership condition to the EXACT/PROXY (real-terrain) tiers** — the INDOOR/STRENGTH fallbacks are unchanged.
3. Disciplines with no gear/craft alias and no skill gate (running) → feasible on terrain alone (unchanged).

This **maps onto the existing 4 tiers** (EXACT/PROXY/INDOOR/STRENGTH), so plan-gen handling, the saturation cap (#590), and the coaching surfaces need no new tier logic — only the *inputs* change (gear now participates; fidelity rank chooses among same-discipline gear). The un-starving: feed `cluster_gear_toggle_states` (and the away set) from `athlete_gear` at both 2C call sites (`orchestrator.py` full-cone + single-session, today hard-coded `{}`), and route gear through the cascade above rather than the flag-only path.

## 7. "Bring it with me"
`_build_event_window_overlay` already unions standing `athlete_craft_locale` + per-window `brought_craft` into the away cluster's `owned_crafts`. Generalize: union standing `athlete_gear_locale` + `brought_gear`, split by `group_kind`, into the away environment's gear/craft inputs, and **re-resolve the away environment's feasibility + 2C** for that segment (the away segment currently reuses the home 2C — fine for crafts via the re-resolved cascade, but gear needs the away 2C re-run so a brought ski setup actually unlocks D-028 there).

## 8. Validation
Closed-set `gear_id` against the active gear catalog; `group_kind` from the catalog; `access ∈ {own, access}`; `locale` must be an athlete locale; `fidelity_rank ∈ {primary, degraded}`. Stale `gear_id` rows are inert (picker/cascade read active catalog rows only — mirrors the craft-enum posture).

## 9. Caching / invalidation (Trigger #3)
- `athlete_gear` change → evict the **feasibility/2C-consuming** entry points (`plan_create`/`plan_refresh`), same scope event windows use. (Owned gear/craft is a cone input, not a Layer-1 field — re-home `_collect_athlete_crafts` to read `athlete_gear` directly, so craft + gear share one eviction story.)
- `athlete_gear_locale` / `brought_gear` change → `plan_create`/`plan_refresh` (today's craft-locale / event-window eviction).
- Catalog/alias change (Layer 0) → rides the `0A/0C` digest bump → plan caches invalidate (same as #623/0007).

## 10. UX / IA
One **"Your gear"** surface (crafts + gear together, grouped by `group_kind`), each row own/have-access + a **"bring it"** affordance (keep-at-locale / bring-to-trip). Replaces the two craft pickers and is the first capture for gear. Lives in the existing #894 profile group ("gear/crafts/skills/pack-load" — #894 shipped). Per-locale "Gear kept here" generalizes the craft control; onboarding gains gear via the shared partial.

## 11. Migration
- **Public schema (auto):** create `athlete_gear`, `athlete_gear_locale`; add `brought_gear`; backfill from the craft CSVs + `athlete_craft_locale` + `brought_craft`; drop the old columns after verify (Andy's data is the live check).
- **Layer 0 (via `layer0-apply` Action):** delete orphan/whitewater toggles; roll up climbing; add skimo; build `gear_discipline_aliases` (migrate craft rows + gear `gated_discipline_ids` + ranks); drop `paired_equipment_categories`; the §5.4 equipment de-drift (extends `0008`).

## 12. Coaching flags
- `toggle_off_for_discipline` (#298) becomes real and **moves from flag-only to feasibility**: an included discipline whose gear/craft the athlete lacks now degrades per §6 (with the existing substitute/proxy flags), instead of silently no-opping.
- New: a **degraded-fidelity** note when a session runs on degraded gear or a gym proxy ("XC skiing programmed on the ski-erg — you don't have ski gear available here"), reusing the existing PROXY/INDOOR substitute-flag surface.

## 13. Edge cases
- Own both Classic + Skate → use Classic (primary). Own only Skate → Skate (degraded). Neither, gym has ski-erg → erg (INDOOR). None → strength.
- Climbing with skill but no gear (or gear but no skill) → strength (both required).
- Bring a craft/gear already standing in the away cluster → set-union de-dupes.
- Gym lists a ski-erg but athlete owns the ski setup → primary wins; erg ignored.
- `access='access'` (borrowable) feeds plan-gen as available (athlete's assertion; same trust model as self-reported gear).

## 14. Performance
Two indexed `athlete_gear` reads per cone (replacing the CSV parse). Away path adds one feasibility+2C re-resolve per away window (bounded; comparable to today's per-away-locale terrain re-resolve). No new LLM calls — deterministic capture → deterministic cascade; no prompt-revision bump.

## 15. Build slices (post-sign-off; each ≤5 substantive files)
1. **L0 catalog + aliases** — delete/roll-up/add-skimo; `gear_discipline_aliases` (+rank); drop `paired_equipment_categories`; `layer0-apply`. *(Trigger #2 wording ratified at sign-off.)*
2. **Equipment boundary de-drift** — strip craft/gear items from `equipment_items` + `equipment_required` (extends `0008`).
3. **Athlete store + migration + repo** — `athlete_gear`/`athlete_gear_locale`/`brought_gear`; backfill; collapse the craft repos into one `athlete_gear_repo`; eviction (§9).
4. **Cascade wiring** — re-home `_collect_athlete_crafts`; feed gear into both 2C sites; fidelity-rank walk + skill composition (§6).
5. **Away overlay** — generalize `_build_event_window_overlay` + away re-resolve (§7).
6. **Capture UX** — the "Your gear" surface + onboarding parity (§10).

## 16. Sign-offs — ALL RESOLVED (Andy, 2026-06-22 → 2026-06-23); design is build-ready
- **Trigger #2 (vocab) — ✅ ratified:** §4 table approved. Skimo toggle = **"Skimo / AT setup"** (alpine-touring skis, climbing skins, AT bindings, AT boots) → D-021/D-022. Deletions (bouldering, fencing, shooting, whitewater) confirmed to extend to **all** app mentions (disciplines already removed May 2026; toggles + any remaining template/test strings to purge).
- **Trigger #3 (cross-layer) — ✅ approved:** the §5/§9 schema + invalidation (re-home crafts off the Layer-1 baseline; `craft_discipline_aliases` → `gear_discipline_aliases (+fidelity_rank)`; `brought_gear` hash; drop `paired_equipment_categories`).
- **Proxy map — ✅ examined + ratified:** `session_feasibility._DISCIPLINE_INDOOR_MACHINES` already covers every discipline incl. the gear ones (running/trekking/mtn-running→Treadmill+Stair climber; snowshoe/mountaineering→Stair climber+Treadmill; ski→Ski erg+Stair climber; cycling→trainer/Assault; paddling→Paddle/Rowing erg; climbing→none by design). "Stairmaster" = `Stair climber` (already mapped). **Elliptical** (the only unused cardio machine) added as a stride proxy: D-001/002 (after Treadmill), D-003/017/024 (after Stair climber), D-028 (after Ski erg). No new machines (no-padding).

## 17. Test scenarios
- Athlete owns road bike only → D-006 EXACT, D-008 (no MTB) → strength (or trainer INDOOR if present).
- Owns Classic XC → D-028 EXACT; owns Skate only → D-028 PROXY; neither + gym ski-erg → INDOOR; none → strength.
- Owns climbing gear + has climbing skill → D-012 EXACT; gear but no skill → strength; skill but no gear → strength.
- Brings climbing gear to an away window → D-012 feasible in that segment, not at home.
- Skimo/AT setup owned → D-021/D-022 feasible; absent → strength (no ski-erg proxy for descent).
- Deleted toggles (bouldering/fencing/shooting/whitewater) appear nowhere; no exercise gates on a deleted item.
- No-gear athlete: running/trekking still feasible (no gate).

## 18. Gut check
- **Strength:** the model is now genuinely uniform (`gear/craft (+skill)`), every deletion is backed by the canon, and the new mechanics (fidelity rank, gear-in-cascade) reuse the existing 4-tier machinery rather than adding tiers — low architectural risk.
- **Biggest effort + risk:** the away re-resolve (§7) and confirming the gym **proxy** rows exist (§16) — the ski-erg/paddle-erg→discipline proxy is what makes "degrade before strength" real; if those rows are missing the INDOOR tier silently falls through to strength. Verify before building slice 4.
- **What to watch:** the equipment de-drift (slice 2) is a data change with quiet failure modes (an exercise losing its last gate → always-available, or keeping a now-dead token) — same class #623 handled carefully; reuse that verify pattern.
- **Best argument against scope:** the minimal win (feed gear into the cascade + reuse craft "bring" plumbing) closes #298 and "bring my ski gear" without the full store migration; if go-live pressure bites, slices 1+4+5 deliver the behaviour and the store/UX migration (3+6) can follow. Andy chose the full merge for one-source-of-truth; this honours it but slice 3 is the trim point.
