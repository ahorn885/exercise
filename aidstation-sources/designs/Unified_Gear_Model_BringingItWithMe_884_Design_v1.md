# Unified Gear Model + "Bringing It With Me" — Design v1

**Date:** 2026-06-22
**Issue:** #884 (go-live blocker — user-facing). Sibling system-review notes: #894 (Profile IA), #887 (Locations→Log nav), #298 (starved 2C gear-toggle subsystem), #582 (one-source-of-truth theme).
**Status:** DESIGN — AWAITING ANDY SIGN-OFF. No code this session (Andy: design-first, sign off, build in slices). The §14 open items must be ratified before the build slices start.

**Andy decisions ratified this session (2026-06-22):**
1. **"Gear kits" = the gear-toggle subsystem** — the "do you own ski gear / do you own climbing gear" per-sport ownership flags (`layer0.sport_specific_gear_toggles`, the #298 starved path). NOT the skill-capability toggles and NOT the per-locale gym-equipment lists.
2. **Full one-table merge** — one athlete-side gear store (kind ∈ {craft, kit}) replacing the craft CSV columns + the (today-missing) gear-ownership store + `athlete_craft_locale`. Migrate everything.
3. **Design-first** — this doc, then build in slices.

---

## 1. The problem

"Athlete-owned equipment" is modeled and edited **three different ways** today, and only one of them is wired all the way through:

| | **Crafts** (bikes/boats) | **Gear kits** (= gear toggles, #298) | Skill toggles *(reference only — not merged)* |
|---|---|---|---|
| Meaning | "I own this vessel" | "I own the **gear** for sport X" (ski gear, climbing rack) | "I have the **skill** for X" |
| Athlete store | CSV in `discipline_baseline_cycling.bike_types_available` + `discipline_baseline_paddling.paddle_craft_types` (closed enums `BIKE_TYPES`/`PADDLE_CRAFT_TYPES`) | **none — no athlete store exists** | `athlete_skill_toggles` rows |
| Layer-0 defs | `layer0.craft_discipline_aliases` + `layer0.craft_terrain_compatibility` | `layer0.sport_specific_gear_toggles` (`paired_equipment_categories`, `also_satisfies`, `gated_discipline_ids`) | `layer0.skill_capability_toggles` |
| Capture surface | ✅ profile (athlete tab) + onboarding + per-locale "keep here" | ❌ **none** (deferred — `init_db.py:~2308`) | ✅ `/profile/skills` + onboarding |
| Fed to plan-gen | ✅ feasibility cascade (`_collect_athlete_crafts` → `_gather_feasibility_inputs.owned_crafts`) | ❌ **starved** — both 2C call sites pass `cluster_gear_toggle_states={}` (`orchestrator.py:~1098` full cone, `:~1530` single-session) | ✅ `skill_toggle_states` |
| "Bringing it with me" | ✅ `athlete_craft_locale` (standing) + `athlete_event_windows.brought_craft` (per-window) | ❌ | ❌ (a skill always travels) |

Three consequences:
- **Inconsistent UX.** A craft is captured/edited one way (multi-select against a closed enum, in two places); the gear kits have no capture at all; they look nothing alike even though "do I own a gravel bike" and "do I own ski gear" are the same question.
- **The gear-kit subsystem is dead in prod (#298).** The Layer-2C effective-pool expansion (`_build_effective_pool`, `builder.py:309`), the one-hop `also_satisfies`, the `gated_discipline_ids`, and the `toggle_off_for_discipline` coaching flag (`builder.py:566`) can never fire because nothing ever feeds `cluster_gear_toggle_states`. An athlete who owns ski gear gets no ski training; an athlete who doesn't gets no "you included skiing but own no ski gear" warning.
- **"Bringing it with me" is craft-only.** The away-segment overlay (`_build_event_window_overlay`, `orchestrator.py:~835`) unions standing `athlete_craft_locale` + per-window `brought_craft` into the away cluster's `owned_crafts`. There is no equivalent for kits — you can't tell the system "I'm bringing my climbing rack to the race."

## 2. Scope & boundaries

**In scope (this design):**
- One unified athlete-owned **gear** model with two kinds: `craft` (mobile vessel) and `kit` (sport gear bundle). Same "I own / I have access" semantics, one capture surface.
- One **"bringing it with me"** mechanism that works for both kinds: attach a gear item to a saved locale (standing) or to an event window (per-trip), so the away environment's effective pool / feasibility cascade counts it as present there.
- **Un-starve #298**: feed `cluster_gear_toggle_states` from owned kits, making the 2C expansion + `toggle_off_for_discipline` flag live.

**Explicitly out of scope (separate axes — stated so we don't accidentally merge them):**
- **Skill-capability toggles** (`skill_capability_toggles` / `athlete_skill_toggles`) — a *capability* ("can I do X"), not gear. They keep their own table and fed path. They share the **profile UI group** with gear per #894, and they *compose* with gear in 2C (a sport can need both the skill AND the kit), but they are not part of the one-table merge.
- **Per-locale gym equipment** (`gym_profiles.equipment`) — location-bound, shared/inherited, and moving out to "Log" per #887. A kit *expands the same effective pool* a gym does, but a kit is athlete-portable and a gym is fixed to a place. Reconciled in §5, not merged.

**Coordinates with:** #894 (where gear/crafts/skills/pack-load live in the profile IA), #887 (Locations nav), #582 (drives the picker off real rows — same one-source-of-truth theme), #622 + WS-I/#586 (craft taxonomy + the unified feasibility cascade — already shipped; this design builds on it, doesn't redo it).

## 3. Target model — the unified "gear" concept

**Gear** = athlete-owned/accessible **portable** equipment. Two kinds, distinguished by how they feed plan-gen:

- **`craft`** — a mobile vessel (road/mtb/gravel/tt bike; kayak/canoe/packraft/sup/raft). Feeds the **craft-terrain feasibility cascade** (tiers 1–4 of `resolve_craft_terrain_feasibility`) via `craft_discipline_aliases` + `craft_terrain_compatibility`. Unchanged downstream behavior.
- **`kit`** — a sport gear bundle ("ski gear", "climbing gear", "alpine/glacier kit"). Feeds the **Layer-2C effective pool** via `paired_equipment_categories` (an owned kit's equipment becomes available cluster-wide), and gates disciplines via `gated_discipline_ids` (no kit → `toggle_off_for_discipline`).

Both kinds share:
- **Ownership/access semantics** — a single "I own / I have access to this" state (see §6 on the `access` field).
- **Portability** — owned gear is available across the athlete's whole **home cluster** (this is exactly the existing `cluster_gear_toggle_states` semantics — *cluster*-scoped, not per-locale). "Bringing it with me" extends that to an **away cluster or event window**.

This is the conceptual unification: a craft and a kit are the same noun ("portable gear I own"), differing only in which Layer-0 def table describes their plan-gen effect.

## 4. Data model — full one-table merge

### 4.1 Athlete-side store (NEW, public schema → auto-applies on deploy)

```
athlete_gear (
  user_id     INTEGER NOT NULL REFERENCES users(id),
  gear_id     TEXT    NOT NULL,          -- catalog key (see §4.4)
  gear_kind   TEXT    NOT NULL,          -- 'craft' | 'kit'  (app-validated, no DB CHECK — project convention)
  access      TEXT    NOT NULL DEFAULT 'own',  -- 'own' | 'access'  (see §6)
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (user_id, gear_id)
)
```

Replaces, as the single source of truth for *what the athlete owns*:
- `discipline_baseline_cycling.bike_types_available` (CSV) — migrated to `gear_kind='craft'` rows.
- `discipline_baseline_paddling.paddle_craft_types` (CSV) — migrated to `gear_kind='craft'` rows.
- the **missing** gear-kit ownership store — kits are now first-class rows (`gear_kind='kit'`).

`gear_kind` is stored (not derived) so the read paths (§5) don't have to join the catalog just to route a row to the craft path vs the kit path; the catalog is the validator.

**Disposition of the retired craft columns:** the two `discipline_baseline_*` craft CSV columns are dropped from the *write* path. Keep the *sibling* baseline fields (`mtb_skill`, `longest_ride_*`, `ow_experience`, …) — those are unrelated discipline baselines, not gear. (Decision flag §14-D: drop the columns outright vs leave them dormant for one release. Recommend drop — v1 has no users but Andy, strangler-fig allows it.)

### 4.2 Standing "keep it here" (generalize the craft-locale table)

`athlete_craft_locale (user_id, craft_slug, locale)` → **`athlete_gear_locale (user_id, gear_id, locale)`**. Same shape, generalized column name; migrate the rows 1:1 (a craft slug is a `gear_id`). Drives "this gear is kept at this away locale," unioned into the away cluster (§5.3).

### 4.3 Per-window "I'm bringing it" (generalize brought_craft)

`athlete_event_windows.brought_craft` (CSV) → **`brought_gear`** (CSV/array; keep CSV to match the existing stable-sorted convention and `compute_event_windows_hash`). Migrate the column; brought-craft slugs are gear_ids. Captured on the event-windows form for `away` windows (§8).

### 4.4 Layer-0 catalog — the one real architecture fork (§14-A)

The athlete store references a `gear_id`. That id must resolve to a kind-specific Layer-0 definition. Two ways:

- **Option A (recommended) — one registry over the typed def tables.** Add `layer0.gear_catalog (gear_id, gear_kind, display_label, sort_order, etl_version, …)` as the single enumerable source for the picker + validation. The **kind-specific maps stay in their typed tables, re-keyed to `gear_id`**: crafts keep `craft_discipline_aliases` + `craft_terrain_compatibility`; kits keep `sport_specific_gear_toggles` (`paired_equipment_categories` / `also_satisfies` / `gated_discipline_ids`). Rationale: a terrain-compatibility grid is meaningless for a kit and a paired-equipment list is meaningless for a craft — forcing both kinds into one wide table creates a half-null schema. The registry gives "one source of truth" for *what gear exists* (the picker, #582's theme) without pretending the two kinds have the same plan-gen shape.
  - Today's craft "catalog" is the `BIKE_TYPES`/`PADDLE_CRAFT_TYPES`/`CRAFT_LABELS` constants in `athlete.py`; today's kit catalog is `sport_specific_gear_toggles`. Option A folds the craft constants into DB rows (`gear_catalog`), retiring the `athlete.py` enums as the source of truth (they can stay as a frozen mirror or be dropped — §14-A2).
- **Option B — fully merged Layer-0 table.** One wide `layer0.gear_defs` with nullable per-kind columns (terrain_ids for crafts, paired_equipment_categories for kits). Maximal literal "one table" but the half-null schema + a single ETL sheet mixing two grammars is harder to author/validate and buys nothing the cascade reads differently.

**Recommendation: Option A.** It satisfies "one model" where it matters (athlete store §4.1 is genuinely one table; one registry/picker) while respecting that the two kinds drive two different cascades. Flagged for Andy because "full one-table merge" *could* be read as Option B.

### 4.5 What does NOT change

`skill_capability_toggles` / `athlete_skill_toggles` stay exactly as-is (out of scope, §2). `gym_profiles.equipment` stays as-is.

## 5. Cascade integration

### 5.1 Owned crafts (re-home the read, behavior unchanged)

`_collect_athlete_crafts(layer1_payload)` (`orchestrator.py:~215`) today reads `discipline_baselines.cycling.bike_types_available` + `paddling.paddle_craft_types`. Re-point it to read `athlete_gear` where `gear_kind='craft'`. Everything downstream (`_gather_feasibility_inputs.owned_crafts` → `resolve_craft_terrain_feasibility` tiers 1–4) is unchanged. (See §7 for the invalidation consequence of moving crafts off the Layer-1 baseline payload.)

### 5.2 Owned kits → un-starve Layer 2C (#298)

Build `cluster_gear_toggle_states` from `athlete_gear` where `gear_kind='kit'`: `{kit_gear_id: True for each owned kit}` (default-OFF semantics preserved — unowned kits are simply absent → treated False, exactly as `_build_effective_pool`/`_emit_coaching_flags` already expect). Pass it at **both** call sites that currently hard-code `{}`:
- full cone `orchestrator.py:~1098` (per-locale 2C fan-out across the home cluster),
- single-session `orchestrator.py:~1530`.

Effect, with zero change to `builder.py`: `_build_effective_pool` (`builder.py:309`) now expands the pool with each owned kit's `paired_equipment_categories` + one-hop `also_satisfies`; `_emit_coaching_flags` (`builder.py:566`) now emits a real `toggle_off_for_discipline` for an included discipline whose kit the athlete doesn't own. This is the #298 fix — feed it, don't drop it.

> Note: `cluster_gear_toggle_states` is **cluster-scoped**, not per-locale — owning ski gear makes it available at every locale in your home cluster. That matches "I own it, it travels with me locally," and is why §5.3's away path injects at the cluster level too.

### 5.3 "Bringing it with me" — generalize the away overlay to kits

`_build_event_window_overlay` (`orchestrator.py:~835`) already, for an `away` window:
```
away_cluster = cluster_locale_ids(anchor=away_locale)
brought      = set(away_ov.brought_craft)                       # (c) per-window
standing     = {c for loc in away_cluster for c in craft_locale_map.get(loc, ())}  # (b) standing
away_crafts  = sorted(brought | standing)
reduced = _resolve_included_feasibility(..., owned_crafts=away_crafts, locale_order=away_cluster, ...)
```

Generalize so the same union runs for **kits**, splitting the merged stores by kind:
- standing: `athlete_gear_locale` rows for locales in `away_cluster`, split into away-crafts (kind=craft) and away-kits (kind=kit).
- per-window: `brought_gear` split by kind.
- away-crafts → `owned_crafts=` (as today).
- away-kits → `cluster_gear_toggle_states=` for the away environment's 2C resolution, so the brought kit's equipment enters the away effective pool (and suppresses the `toggle_off_for_discipline` flag there).

**Implementation dependency (§14-C):** the away segment today does **not** re-invoke Layer 2C per away locale — it reuses the home/primary 2C entry for exercise-tier lookups (the agent-verified limitation; `orchestrator.py:~528`). For brought *crafts* this is fine (crafts route through the feasibility cascade, which IS re-resolved for the away cluster). For brought *kits* to actually change the away effective pool, either (i) re-invoke 2C once for the away environment with the away `cluster_gear_toggle_states` (cost: a few extra queries per away window), or (ii) apply the kit's `paired_equipment_categories` to the away pool post-hoc. Recommend (i) for correctness + reuse of the existing builder; flag the cost. This is the single biggest build-effort item.

### 5.4 Now-live coaching flag

`toggle_off_for_discipline` (#298 part C, `builder.py:566`) becomes a real signal: "You included Skiing but you don't own ski gear — no ski-equipment exercises will be programmed for it." Wire it into the same coaching-flag surface the other 2C flags use. (The rest of #298 part C — the unused `DisciplineCoverage`/`ResolvedExercise`/`ResolutionDetail` sub-fields — is orthogonal; not pulled into this design.)

## 6. Ownership vs access ("I own / I have access to this")

The issue asks for "same 'I own / I have access to this' semantics." Two readings:
- **6a (recommended): a presence + `access` enum.** A row in `athlete_gear` means "available to me"; `access ∈ {own, access}` records *how* (I own it / I can borrow-or-rent it) for coaching nuance, but **both feed plan-gen identically** (the cascade only cares whether the gear is available). Cheap, future-proofs the "rental at destination" case.
- **6b: presence only.** A row = available; drop the nuance. Simpler.

Either way "have access" must not be confused with the standing locale binding (§4.2) — `access='access'` is "I can get this gear" (athlete-global); `athlete_gear_locale` is "this specific gear lives at locale X." Recommend 6a; it's one nullable column and matches the issue's wording. (§14-B.)

## 7. Caching / invalidation

The merged store feeds **two layers**, so a naïve "evict everything on any gear change" is wrong-but-safe; precise eviction is better:

- **Craft rows** are a Layer-1 input today (owned crafts ride in the Layer-1 payload via `_collect_athlete_crafts`). Two choices:
  - **7a (recommended): re-home owned crafts to a cone-input read, not a Layer-1 field.** `_collect_athlete_crafts` reads `athlete_gear` directly in the cone (it already runs in `_gather_feasibility_inputs`, off the Layer-1 hash), so a craft change evicts `plan_create`/`plan_refresh` (where feasibility is consumed) — the same scope event windows already use. Removes crafts from the Layer-1 hash entirely → simpler, narrower eviction, and unifies craft + kit eviction (both become "feasibility/2C inputs," not Layer-1 fields).
  - 7b: keep crafts in Layer 1 → a craft change still does the broad `evict_on_layer_change('layer1')`. Works, but keeps the split.
- **Kit rows** feed Layer 2C → a kit change evicts the 2C-consuming entry points (every entry point, since 2C is in the full cone + single-session). Mirror `_evict_layer2c_on_equipment_change`.
- **Standing (`athlete_gear_locale`) + per-window (`brought_gear`)** changes evict `plan_create`/`plan_refresh` only (exactly today's `evict_plan_caches_on_craft_locale_change` / event-windows eviction).

Recommend 7a. It's the cleaner end state and makes the merged store have one coherent eviction story per kind.

## 8. UX / IA (coordinate with #894, #887)

**One capture surface — "Gear."** A single list of the athlete's gear, grouped by kind (Crafts / Kits), each row: name, own/have-access, and a **"Bring it with me"** affordance. Drives off real catalog rows (#582 theme), replacing:
- the two craft pickers (`templates/onboarding/_crafts_form.html` reused on the profile athlete tab + onboarding),
- the (nonexistent) kit picker.

**"Bring it with me" affordance** — per gear item, two bindings (matching §4.2/§4.3):
- *Keep at a locale* → writes `athlete_gear_locale` (standing). Lives on the locale editor today ("Craft you keep here", `templates/locales/form.html`); generalize to "Gear you keep here."
- *Bring to a trip* → writes `brought_gear` on an `away` event window (`templates/profile/event_windows.html`, generalize the existing brought-craft checkboxes).

**IA placement (per #894):** the Gear surface lives in the new **"gear / crafts / skills / pack-load"** profile group alongside the skill toggles (which stay a distinct sub-section — capability, not gear) and pack-load experience. This design supplies the *gear* half; #894 owns the grouping/headings. **Sequencing call (§14-E):** do we land #884's unified Gear surface first and let #894 reflow it, or land #894's shell first? Recommend #884 first (the model has to exist before IA can place it); #894 then slots it.

Onboarding parity: the onboarding "skills" step today saves crafts + skill toggles together (`onboarding.skills_save`); it gains the kit picker via the same shared partial.

## 9. Migration

- **Public schema (auto-applies on Vercel deploy via `_PG_MIGRATIONS`):** create `athlete_gear`, `athlete_gear_locale`; add `brought_gear`; one-time backfill:
  - `bike_types_available` + `paddle_craft_types` CSVs → `athlete_gear(gear_kind='craft', access='own')`.
  - `athlete_craft_locale` rows → `athlete_gear_locale` (1:1).
  - `brought_craft` → `brought_gear` (copy).
  - Drop the old craft columns / table **after** backfill verifies (idempotent; same drop-then-verify pattern as prior realignments). Andy's own craft data is the live test row.
- **Layer 0 (via the gated `layer0-apply` Action — container can't reach Neon):** create `gear_catalog` (Option A) + seed it (crafts from the existing `craft_*` keys; kits from `sport_specific_gear_toggles` + the §10 new vocab); re-key `craft_*` / `sport_specific_gear_toggles` to `gear_id` if needed.
- **No interaction with the WS-I `cycling_trainer` migration** (already shipped — trainer is equipment, not craft; it never enters the gear store).

## 10. Vocab — the kit catalog (Trigger #2 — needs Andy ratification)

`sport_specific_gear_toggles` today is nearly empty (`Climbing — roped`; `Bouldering` superseded). Andy's framing ("do you own ski gear / climbing gear") implies a real per-sport kit catalog. **PROPOSED candidates — do NOT seed without Andy's sign-off (no-padding rule):**

| Proposed kit `gear_id` | Display | Gates discipline(s) | `paired_equipment_categories` (illustrative — needs equipment-vocab check) |
|---|---|---|---|
| `climbing_gear` | Climbing gear (rope, harness, rack) | D-012 / D-013 (roped) | climbing protection / rope / harness categories |
| `ski_gear` | Ski gear (skis, boots, poles) | XC/skimo disciplines | ski equipment categories |
| `alpine_gear` | Alpine / glacier kit (crampons, axe) | D-018 / D-022 | mountaineering equipment categories |
| `via_ferrata_kit` | Via ferrata kit (lanyard set) | D-014 | via-ferrata equipment |

**Two vocab decisions for Andy (§14-F):**
1. **Which kits exist** (the grid above — add/remove/rename) and their exact `paired_equipment_categories` against the live `layer0.equipment_items` vocab.
2. **The craft/skill/kit overlap.** Roped climbing appears as a *skill* toggle (`climbing_roped`), a *gear* toggle (`Climbing — roped`), and would gain a *kit*. These are three genuinely different facts (can I climb / do I own the rack / —), but the naming collision is confusing and must be reconciled (rename the gear one to `climbing_gear`, keep the skill one). Same for whitewater (skill) vs a paddling kit, if any.

This section is the main reason for design-first: the catalog is judgment-dense and is a Trigger #2 sign-off, exactly like the craft↔terrain grid was.

## 11. Edge cases

- **Own a kit but no gym/locale equipment for it** — kit `paired_equipment_categories` enter the *effective pool* regardless of locale (cluster-scoped), so kit-gated exercises resolve even at a bare locale. Correct (you brought your own).
- **Bring a craft to an away locale whose cluster also has it standing** — `brought | standing` de-dupes (set union). Unchanged.
- **Kit owned but discipline not included** — no flag, no pool change for that discipline (nothing references it). Fine.
- **Discipline included, kit not owned, gym has the equipment anyway** — the gym's `locale_equipment_pool` already covers it; the kit toggle is additive, so the exercises still resolve. `toggle_off_for_discipline` should suppress when the gym already supplies the gear (check before emitting — the flag is "you have no way to train this," not "you personally don't own it"). §14 note.
- **Access='access' (borrowable) but never actually obtained** — feeds plan-gen as available (athlete's assertion); same trust model as today's self-reported equipment.
- **Stale gear_id after a catalog supersede** — `_build_effective_pool` already skips unknown toggle names silently; the picker drives off active catalog rows, so stale athlete rows are inert (mirror the craft-enum-validation posture).

## 12. Performance budget

- Owned-gear reads: two indexed `athlete_gear` selects per cone (craft kind, kit kind) — negligible, replaces the current baseline-CSV parse.
- The away-kit path (§5.3 option i) adds **one 2C invocation per away window** (re-resolve the away environment). Bounded by the (small) number of `away` windows; comparable to the existing per-away-locale feasibility re-resolution. Acceptable; flag if an athlete has many away windows.
- No new LLM calls (gear is deterministic capture → deterministic 2C/feasibility). No prompt-revision bump.

## 13. Build slices (post-sign-off; each ≤5 substantive files)

1. **L0 catalog + vocab** — `gear_catalog` (Option A) + the ratified kit grid (§10) + extractor/runner; `layer0-apply`. *(Trigger #2/#3 — ratified at sign-off.)*
2. **Athlete store + migration + repos** — `athlete_gear` / `athlete_gear_locale` / `brought_gear`; backfill; collapse `athlete_crafts_repo` + `athlete_craft_locale_repo` (+ the gear-toggle athlete read) into one `athlete_gear_repo`; eviction per §7.
3. **Capture UX** — one Gear surface + onboarding parity (shared partial); generalize the locale "keep here" + event-window "bring" forms.
4. **Cascade wiring** — re-home `_collect_athlete_crafts` (§5.1); feed `cluster_gear_toggle_states` at both 2C sites (§5.2); `toggle_off_for_discipline` surfacing (§5.4).
5. **Away-kit overlay** — generalize `_build_event_window_overlay` to split by kind + re-resolve the away env with brought/standing kits (§5.3 — the heaviest slice).
6. **IA placement** — coordinate with #894 (may be #894's slice, not this one).

## 14. Open items — Andy sign-off before build

- **A. Layer-0 catalog shape** — Option A (registry over typed def tables) vs Option B (one wide half-null table). *Recommend A.*
  - **A2.** Retire the `athlete.py` craft enums as source of truth in favor of `gear_catalog` rows, or keep them as a frozen mirror?
- **B. Ownership model** — `own`/`access` enum (6a, recommended) vs presence-only (6b).
- **C. Away-kit injection** — re-invoke 2C for the away env (i, recommended) vs post-hoc pool patch (ii).
- **D. Old craft columns** — drop outright on migrate (recommended) vs leave dormant one release.
- **E. #884 vs #894 sequencing** — land the Gear model first, #894 reflows it (recommended) vs #894 shell first.
- **F. Kit vocab (Trigger #2)** — ratify the §10 grid (which kits, their `paired_equipment_categories`) **and** resolve the roped-climbing skill/gear/kit naming collision.
- **G. `toggle_off_for_discipline` suppression** — suppress when a cluster gym already supplies the gear (recommended) vs always emit on non-ownership.

## 15. Gut check

- **Biggest risk: blast radius of the full merge.** Crafts are wired into Layer 1 (baseline payload), the feasibility cascade, the away overlay, the locale editor, onboarding, and the X1b.3b substitution path. The migration touches all of them. Mitigation: the craft *cascade* is unchanged — only the *read source* and *eviction* move (§5.1, §7a); slice 2's migration is a mechanical backfill with Andy's own data as the live check; slices land behind the existing feasibility test suite (reproduce → green).
- **What might be missing:** the kit catalog is thin and judgment-dense (§10) — getting `paired_equipment_categories` wrong silently mis-expands the pool (the same failure class the craft↔terrain grid had). That's why §10 is a hard sign-off gate, not a build-time guess.
- **Best argument against this scope:** the *minimal* win (feed `cluster_gear_toggle_states` from a small kit store + reuse the craft "bring" plumbing) would close the live #298 starvation and deliver "bring my ski gear" without the full one-table migration. Andy chose the full merge for one-source-of-truth; this design honors that, but slice 2 (the migration) is the part to cut first if go-live pressure forces a trim — slices 1/4/5 alone (kit store + un-starve + bring) deliver the user-visible behavior even if crafts stay in baselines for one more release.
- **Coupling to land cleanly:** #894 (IA) and #298 (this closes its part A + part-C `toggle_off_for_discipline`). Comment both at build time.
