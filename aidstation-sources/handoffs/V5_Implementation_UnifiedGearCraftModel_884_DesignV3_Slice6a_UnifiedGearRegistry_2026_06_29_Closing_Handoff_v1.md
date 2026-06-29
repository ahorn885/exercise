# #884 Unified Gear/Craft Model — Slice 6a (unified gear registry + consolidated "Your gear" surface) — Closing Handoff v1

**Session:** 2026-06-29 · branch `claude/884-slice-6-capture-ux-buq44b` · commit `1b6f050` · PR not yet opened (push + bookkeep + wait for Andy's go).
**Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 (6a). **Design:** `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §10 (UX/IA), §5.5 (gear_id keyspace). **Predecessor:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice5_AwayOverlay_2026_06_29_Closing_Handoff_v1.md`.

---

## 1. Session-start verification (Rule #9)

Verified the slice-5 handoff §8 claims against on-disk state before starting:
- `layer4/orchestrator.py` reads `load_gear_locales` + `GEAR_REGISTRY.get(g) in _CRAFT_ALIAS_GROUP_KINDS` — present; no `load_craft_locales` remains. ✅
- `routes/locales.py` uses `replace_gear_locale`/`load_gear_locales`/`evict_plan_caches_on_gear_locale_change` — present. ✅
- Branch is fresh off `origin/main` (slice 5 merged via PR #1023, `2504739`); no stacked commits. ✅
- Full suite green at HEAD before edits. ✅

## 2. Session narrative

Slice 6a is the first sub-PR of the RATIFIED slice 6. Goal: fold the two profile pickers (owned-craft form + gear-toggle form on the Gear & skills tab) into **one grouped-by-`group_kind` "Your gear" surface**, backed by a **runtime gear registry (D2)** keyed by the §5.5 `gear_id` keyspace — the single picker + validator source.

**Open architectural fork resolved up front (Trigger #3 / #5).** Design §10 wants each row to be **own / have-access**, but today both pickers are owned-only checkboxes, and crafts (bike/paddle) store their truth in the `discipline_baseline_*` CSV columns (which feed the Layer 1 hash) with no access concept — only forward-syncing to `athlete_gear` as `'own'`. So a real own-vs-access toggle for crafts had no store without a change. Asked Andy (AskUserQuestion): **"full own/have-access now."**

Chose the mechanism that **avoids a cross-layer schema change**: make `athlete_gear` the access authority for ALL kinds (it already has the `access` column, in-set `{own, access}`). The craft baseline CSVs keep holding the full **available** set (own ∪ access) — which is exactly what Layer 1 substitution consumes; it does not distinguish access. **Verified `access` is read NOWHERE in `layer1/`/`layer4/`** (grep): `layer1.builder._load_owned_gear` returns a sorted gear_id list, the cascade's `_collect_athlete_crafts` reads `owned_gear` gear_ids — neither branches on access. So flipping own↔access changes no plan output today; the existing Layer-1 eviction is conservatively correct.

**Swim gear excluded** from the registry: group_kind `swim` (pull_buoy/kickboard/paddles/fins) has no presentation label and no capture surface yet (drill-gating, separate from the discipline-unlocking registry). The plan's "fold `load_craft_catalog` + `load_gear_toggle_catalog`" scope is exactly the 6 craft+toggle kinds.

## 3. File-by-file edits

### 3.1 `athlete_gear_repo.py` (modified)
- Import `CRAFT_LABELS` from `athlete`.
- New `_CRAFT_KINDS = {"bike","paddle"}` (next to `_GEAR_TOGGLE_KINDS`).
- New section "unified gear registry + 'Your gear' surface (slice 6a)":
  - `_GROUP_KIND_LABELS` — group_kind → display heading + render order (bike, paddle, ski, snow, climb, alpine).
  - `load_gear_registry()` → `[{gear_id, group_kind, label, source}]` in `_GEAR_IDS` order; `source` ∈ {'craft','toggle'}; swim omitted. Labels: crafts from `CRAFT_LABELS`, toggles from `GEAR_TOGGLE_LABELS`.
  - `load_gear_registry_grouped()` → `[{group_kind, label, rows:[{gear_id,label}]}]`. **Key is `rows`, NOT `items`** — Jinja resolves `grp.items` to the dict method, not the key (hit this bug; renamed).
  - `get_gear_access_map(db, uid)` → `{gear_id: access}` from `get_athlete_gear` (covers crafts + toggles uniformly, since crafts sync into `athlete_gear`).
  - `parse_gear_registry_form(form)` → `{gear_id: access}`; each row posts `gear__<gear_id>` ∈ {'', 'own', 'access'}; only registry gear_ids with an in-set access kept (drops blank/swim/unknown/junk).

### 3.2 `athlete_crafts_repo.py` (modified)
- `replace_athlete_crafts(...)` gains optional `access_by_slug: dict[str,str] | None`. Baseline CSV writes unchanged (still the full available set). The `athlete_gear` forward-sync now writes `{slug: access.get(slug, "own")}` instead of hardcoded `'own'` — an unmapped slug (the onboarding own-only path) defaults to `'own'`; out-of-set access is rejected by `replace_owned_gear_for_kinds`.

### 3.3 `routes/profile.py` (modified)
- Imports: dropped `get_athlete_crafts`, `get_owned_gear_toggles`, `load_gear_toggle_catalog` (now orphaned); added `get_gear_access_map`, `load_gear_registry`, `load_gear_registry_grouped`, `parse_gear_registry_form`. `load_craft_catalog` kept (still used by the `event_windows` brought picker — that's 6b).
- `edit()`: replaced the 4 craft/toggle template loads with `gear_registry = load_gear_registry_grouped()` + `gear_access = get_gear_access_map(db, uid)`; render context updated.
- New `save_gear()` route (`POST /profile/gear`): `parse_gear_registry_form` → classify chosen by registry → `replace_athlete_crafts(bike_types, paddle_crafts, access_by_slug=craft_access)` + `replace_owned_gear_for_kinds(toggle_access, _GEAR_TOGGLE_KINDS)` → commit → one `evict_layer1_on_gear_change` → Rule #15 `[your-gear-capture]` log.
- **Old `save_crafts` / `save_gear_toggles` routes RETAINED** (UI-detached — the template no longer references them). Plan §3 6a says keep until the 6c cleanup. Their tests still pass.

### 3.4 `templates/profile/edit.html` (modified)
- Gear & skills tab: the two old forms (craft picker include + gear-toggle form) replaced by one `save_gear` form rendering `gear_registry` grouped, each row a label + `<select>` (Don't have / Own / Have access), pre-selected from `gear_access`.

### 3.5 `static/style.css` (modified)
- `.gear-group` / `.gear-row` / `.gear-row-label` / `.gear-row-access` — flex row layout (label grows, select capped at 140px). CSP-clean (no inline styles).

## 4. Code / tests

- New repo tests (`tests/test_athlete_gear_repo.py::TestGearRegistry`): fold/order + source/label provenance; grouped section order + `rows` key (asserts no `items` key); parse keeps own/access & drops blank/swim/unknown/junk; access-map reads all kinds.
- `tests/test_athlete_crafts_repo.py`: `access_by_slug` syncs per-craft access, unmapped → 'own', baselines unchanged.
- `tests/test_routes_profile_skills.py::TestSaveGearRoute`: split crafts+toggles + access + swim ignored + one eviction; empty form clears all registry kinds.
- `tests/test_redesign_profile_render.py::test_profile_gear_skills_tab`: repointed from `/profile/crafts` → `/profile/gear`, `Gear you own` → `Your gear`, + asserts the `Have access` control.
- **VERIFIED:** full `tests/ etl/tests/` suite **3931 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings). Ruff clean on all changed files (the 3 `routes/profile.py` F401s — bcrypt / PROFILE_FIELDS / DEFAULT_UNIT_PREFERENCE — confirmed HEAD-pre-existing via stash, untouched).

## 5. Manual §5.0 verification steps

On the deployed app, **Profile → Gear & skills**:
1. The old two-form layout (separate "Gear you own" craft checkboxes + "Sport-specific gear you own" toggles) is replaced by one **"Your gear"** card grouped Bikes / Paddle craft / Skis & rollerskis / Snow / Climbing / Mountaineering–ski-mo, each row a Don't-have / Own / Have-access select.
2. Set a bike to **Have access** and a ski to **Own**, Save → reload → selections round-trip.
3. Confirm a saved craft still drives plan-gen craft substitution as before (baselines unchanged) — own vs have-access does not change plan output yet (by design; the distinction is captured for later "bring it" semantics).

## 6. Next session pointers

### 6.1 Architect-recommended next forward move — slice 6b
Generalize the **standing** (`routes/locales.py`) and **brought** (event-windows) pickers from the craft-only catalog to the **unified registry** (all kinds), and **cut the brought read `brought_craft` → `brought_gear`** (`add_event_window` dual-write/migrate; `layer4/orchestrator.py` away path; `layer4/session_feasibility.py` `EventWindowOverride.brought_craft`; `layer4/hashing.py` folds `brought_gear` — byte-identical today). **This is the slice that makes slice-5's plumbing observable** (station/bring ski/climbing gear → feasible away; design §17 climbing-at-away scenario; add the end-to-end test). **Watch the `replace_gear_locale` replace-all trap** (slice-5 §6.1): the standing picker must submit the full owned-at-locale set or switch to a kind-scoped replace so a partial save can't wipe other-kind gear.

### 6.2 Alternative pivots
- **6c** (onboarding gear-toggle parity via the unified registry + retire the app-dead `athlete_craft_locale_repo` + legacy craft columns via a redump-fold — slice-4.3 pattern). Naturally last (needs redump coordination).
- The deferred **per-segment 2C re-resolve** (slice-5 §2 / §6.1) also lives in slice 6.

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — last-shipped (this 6a) + #884 predecessors. 3. `CARRY_FORWARD.md` — the #884 rolling item + ops gotchas. 4. This handoff + the slice-6 plan + design v3 §10/§17. 5. `./scripts/verify-handoff.sh`.
- Slice 6a is at the **5-file ceiling** — 6b and 6c are separate sub-PRs; do not stack them onto one diff.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Full own/have-access in 6a (not a behavior-preserving own-only fold) | Andy 2026-06-29 (AskUserQuestion) | Design §10 wants the control; build it now |
| 2 | `athlete_gear` is the access authority for ALL kinds; no baseline schema change | Claude | `access` is read nowhere in the layers; baselines keep the full available set (own ∪ access) which is all Layer 1 consumes — avoids a cross-layer hash change |
| 3 | Swim gear excluded from the registry | Claude | No label / no capture surface (drill-gating); plan's "fold the two catalogs" = the 6 craft+toggle kinds |
| 4 | Old `save_crafts` / `save_gear_toggles` routes retained (UI-detached) | Plan §3 6a | Retire in the 6c cleanup; minimizes 6a churn |

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Unified registry + grouped + parse + access-map | `athlete_gear_repo.py` | grep `load_gear_registry`, `load_gear_registry_grouped`, `get_gear_access_map`, `parse_gear_registry_form`; grouped emits key `rows` (not `items`) |
| Craft access sync | `athlete_crafts_repo.py` | `replace_athlete_crafts` has `access_by_slug`; sync uses `access.get(slug, "own")` |
| Consolidated save route | `routes/profile.py` | `save_gear` route present; old `save_crafts`/`save_gear_toggles` retained; `edit()` passes `gear_registry`/`gear_access` |
| Unified template form | `templates/profile/edit.html` | one `profile.save_gear` form, grouped `grp.rows`, own/have-access select; no `save_crafts`/`save_gear_toggles` refs |
| Suite green | (local) | `tests/ etl/tests/` 3931 passed / 30 skipped |
| No Neon/layer0 apply owed | — | public-schema reads only; `athlete_gear.access` live since slice 3 |

## 9. Files shipped this session

**Substantive (5, at ceiling):** `athlete_gear_repo.py`, `athlete_crafts_repo.py`, `routes/profile.py`, `templates/profile/edit.html`, `static/style.css`.
**Tests (not counted):** `tests/test_athlete_gear_repo.py`, `tests/test_athlete_crafts_repo.py`, `tests/test_routes_profile_skills.py`, `tests/test_redesign_profile_render.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue #884 comment.

---

**End of handoff.**
