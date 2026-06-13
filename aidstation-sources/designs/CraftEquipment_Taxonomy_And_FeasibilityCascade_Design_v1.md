# Craft / Equipment Taxonomy + Unified Feasibility Cascade — Design v1

**Date:** 2026-06-13
**Status:** DESIGN — Andy-ratified cascade ordering + explicit craft↔terrain data (2026-06-13). Awaiting sign-off on the remaining open items before build.
**Origin:** the pv=69→71 feasibility-saturation arc. Watching pv=71 (the gear-toggle profile test) surfaced two coupled structural problems that the set-B craft-population fix (#581/WS-G) masks but does not solve.
**Arc:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (new workstream — see §7).
**Supersedes the secondary note in:** that plan's §6a WS-G "Verify (G) Secondary" + the WS-E2/V "degenerate INDOOR-preempt" line — this design is the general case.

---

## 1. The two problems (proven on pv=70/71)

**(a) Taxonomy inconsistency.** Trainers/ergs are split across two models:
```
athlete.py:320  BIKE_TYPES         = ('road_bike','mountain_bike','gravel_bike','cycling_trainer')
athlete.py:329  PADDLE_CRAFT_TYPES = ('kayak','canoe','packraft')
```
`cycling_trainer` is captured as a **craft** (set B, athlete-owned) **and** exists as the `'Cycling trainer'` **indoor machine** in the gym equipment pool (set C) — double-modeled. The **paddle ergometer** is *only* equipment (no erg in `PADDLE_CRAFT_TYPES`). Per Andy's rule — *a trainer/erg is not mobile → it is equipment* — both belong in equipment, and craft = mobile vessels only.

**(b) The cascade can't express the desired ordering.** Feasibility is **two non-composing axes**:
- Craft axis (`session_feasibility.resolve_craft_feasibility`): `OWNED → SWAP → STRENGTH`. Runs *ahead* of terrain and **short-circuits**.
- Terrain axis (`resolve_terrain_feasibility`): `EXACT → PROXY → INDOOR → STRENGTH → REALLOCATE`, where INDOOR = trainer/erg from equipment.

When the craft axis returns `strength` (craftless), `orchestrator.py:437-449` emits a STRENGTH resolution and `continue`s — it **never calls the terrain axis**, so the INDOOR tier (the trainer/erg the athlete actually has) is skipped. A craftless athlete with a Cycling trainer + Paddle ergometer gets *strength*, not *trainer/erg sessions*. This is the live bug behind pv=70's MTB/packraft→strength saturation; owning the craft (pv=71) only hides it by reaching the OWNED tier first.

---

## 2. Target model — taxonomy

- **Craft = mobile, athlete-owned vessel.** `BIKE_TYPES = (road_bike, mountain_bike, gravel_bike)`; `PADDLE_CRAFT_TYPES = (kayak, canoe, packraft)`. Drop `cycling_trainer` from the craft enum.
- **Equipment = fixed gear, incl. all indoor machines.** Trainer, spin/stationary/assault bike, paddle/rowing ergometer, treadmill, stair climber — captured per locale in `gym_profiles.equipment` (set C), already the INDOOR-tier source.
- **Indoor is craft-independent** (Andy 2026-06-13: "not all smart trainers require a bike… we assume they figure out the trainer"). The INDOOR tier fires whenever the machine is in the equipment pool, regardless of craft ownership.

---

## 3. Target model — unified feasibility cascade (craft disciplines)

A craft discipline is one whose modality `group_kind ∈ {bike, paddle}`. Non-craft disciplines (foot/swim/climb) keep the existing terrain-only cascade untouched. For a craft discipline, walk one ordered cascade (first match wins):

| # | Tier | Match condition | Session rendered as |
|---|------|-----------------|---------------------|
| 1 | **Exact** | own the discipline's craft **AND** the discipline's exact required terrain is in-cluster | the sport on its terrain |
| 2 | **Owned craft, alternate terrain** | own the craft; exact terrain absent; **other terrain this craft can use** is in-cluster | the sport on substitute terrain |
| 3 | **Proxy craft on desired terrain** | don't own the craft; own a **same-group proxy craft**; the **desired** terrain is in-cluster **AND the proxy craft can be used on it** | proxy craft, desired terrain |
| 4 | **Proxy craft on its own terrain** | own a same-group proxy craft; ride it on **terrain suited to the proxy** if in-cluster | proxy craft, its native terrain |
| 5 | **Indoor proxy** | a trainer/erg for this discipline is in the equipment pool (craft-independent) | indoor machine session |
| 6 | **Strength** | none of the above; a mapped strength pool exists | strength substitution |
| 7 | **Reallocate** | nothing available | volume redistributed |

**Ratified (Andy 2026-06-13):** tier 3 ranks **above** tier 4 — desired-terrain-on-a-proxy-craft beats proxy-craft-on-its-own-terrain (we'd rather put you on the trail with a road bike, *if the road bike can ride that trail*, than send you to the road).

**Structure:** this is a **nested** cascade — for each candidate craft in priority order `[owned craft, …proxy crafts]`, run a terrain sub-check (exact → other-usable), then fall through to indoor → strength → reallocate only when no owned craft/proxy yields a rideable terrain. "Craftless" (nothing in the group) is not a special branch: tiers 1–4 simply all miss and the walk lands on indoor (tier 5). That *is* the "check a few things first" before indoor — and the bug fix falls out for free.

---

## 4. Target model — craft↔terrain data (DECIDED: explicit)

Tiers 2–4 need to know **which terrains each craft can be used on**. Today only `craft→disciplines` (`layer0.craft_discipline_aliases`) and `discipline→terrain` exist, so craft→terrain is only *derivable* via the discipline graph.

**Decision (Andy 2026-06-13): declare it explicitly, not derive it.** A craft's terrain range should be settable independent of how its disciplines are wired — e.g. a road bike can't ride singletrack but a gravel bike can, even though both alias to road/XC disciplines. Add a Layer-0 map:

```
layer0.craft_terrain_compatibility(craft_name, terrain_id, etl_version)   -- many-to-many
```
seeded in the `Sports_Framework` xlsx (new sheet, additive — mirrors the `Craft Discipline Aliases` precedent in `X1b3b_CraftDisciplineAliases_v1.md`). The cascade reads it to answer "can craft C ride terrain T" at tiers 2 (own-craft/other-terrain), 3 (proxy-craft/desired-terrain gate), and 4 (proxy-craft/own-terrain).

**Open (needs Andy):** the seed rows themselves — the craft→terrain grid for `road_bike / mountain_bike / gravel_bike / kayak / canoe / packraft` against the TRN-* set. This is **Trigger #2** (vocabulary/data) — bring the proposed grid for sign-off before authoring the sheet.

---

## 5. Change surface

| Layer / file | Change |
|---|---|
| **L1 capture** `athlete.py` | drop `cycling_trainer` from `BIKE_TYPES` + its `CRAFT_LABELS` entry |
| **L0 data** `layer0.craft_discipline_aliases` | remove the `cycling_trainer → (all bike)` rows (it's no longer a craft) |
| **L0 data (new)** `layer0.craft_terrain_compatibility` | new table + xlsx sheet + extractor + runner insert (mirrors craft-aliases pattern) |
| **Cascade** `layer4/session_feasibility.py` | replace the two-axis `resolve_craft_feasibility` / `resolve_terrain_feasibility` split with the single nested cascade (§3); read craft↔terrain |
| **Cascade** `layer4/orchestrator.py:425-470` | remove the craft-STRENGTH short-circuit; drive the unified cascade; **Rule #15** — log the chosen tier + the inputs it decided on (per-discipline, as today) |
| **Profile UI** `routes/profile.py` + Gear template | `cycling_trainer` leaves the craft picker; it's an equipment item (gym profile) — confirm the equipment capture already offers it |
| **Tests** `tests/test_layer4_terrain_feasibility*.py` + craft tests | new tier matrix incl. the craftless-with-trainer case that motivated this |

---

## 6. Migration (owed Andy's hands — Neon egress blocked from the container)

1. Apply the new `craft_terrain_compatibility` ETL SQL on Neon.
2. Re-run `craft_discipline_aliases` without the `cycling_trainer` rows.
3. **Data fix for existing athletes:** anyone (Andy included) who selected `cycling_trainer` as a bike type — move it out of `discipline_baseline_cycling.bike_types_available` and ensure `'Cycling trainer'` is in their home `gym_profiles.equipment`. One-row UPDATE; bundle into the migration. (Andy currently has `cycling_trainer` in set B — pv=71 logs.)

---

## 7. Plan-arc placement + sequencing

New workstream in `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md`:

> **WS-I — Craft/equipment taxonomy + unified feasibility cascade.** Subsumes the WS-G "Secondary" + WS-E2/V "degenerate INDOOR-preempt" notes. DECIDED: cascade ordering (§3), explicit craft↔terrain (§4). OPEN: the craft→terrain seed grid (Trigger #2). Build after the grid is signed off.

Sequence: lands after #581/WS-G (already populates set B) and is independent of WS-H (away craft). The crash-guard (#579) keeps any residual saturation from crashing while this is in flight.

---

## 8. Open items (Andy sign-off before build)

1. **The craft→terrain seed grid** (§4) — Trigger #2. The load-bearing missing data.
2. **Tier-2 vs tier-5 edge:** if an athlete owns the craft but neither exact nor other-usable terrain is in-cluster (tier 1+2 miss) **and** an indoor machine exists — do we prefer indoor (tier 5) over dropping to strength? Per §3 yes (tiers 3–4 also miss for the *owned*-craft-no-terrain case, so the walk reaches indoor). Confirm that's intended: an owned-bike athlete with no ridable terrain but a trainer gets trainer sessions, not strength.
3. **Reallocate vs strength interplay** stays as the existing per-discipline preference; the weekly saturation cap (WS-E2) is orthogonal and still queued.

---

## 9. Gut check

- **Risk:** the unified cascade is a rewrite of the hottest deterministic path in Layer 4. The mitigation is the existing feasibility test suite green before/after **plus** new craftless-with-trainer + proxy-craft-terrain cases — this is a `reproduce → green` change, not a free-form refactor.
- **What might be missing:** the craft→terrain grid is judgment-dense (which bike rides which TRN), and getting it wrong silently re-introduces a saturation or, worse, prescribes a road bike on singletrack. That's exactly why §4 chose *explicit* data over derive — but it shifts the correctness burden onto the seed grid, which needs Andy's eyes (open item 1).
- **Best argument against:** scope. The set-B fix (#581) already unblocks Andy's live plan; this is a correctness/quality redesign, not a live blocker. Counter: it's the *general* bug (any craftless-but-equipped athlete saturates to strength), and the taxonomy split will keep generating these until it's resolved — so it's the right next structural piece once #581 deploys, not net-new scope.
