# Locations Consolidation — Design Spec v1

**Status:** DRAFT — awaiting sign-off (Andy)
**Date:** 2026-06-05
**Track:** 1 of 2 (this = locations/equipment model; Track 2 = determinism-first Layer 4 synthesis, separate spec)
**Supersedes the deferred D-60 §5.5 decision** ("`locale_equipment` deprecation is not a v1 concern") — promoted to active per Andy 2026-06-05.

---

## 1. Purpose

Collapse the **two** equipment/location models into one, and wire plan generation to read it. Today:

- **Legacy:** `locale_equipment` table + `locale_profiles.equipment` free-text + the hardcoded `home/hotel/partner/airport` enum + `_edit_legacy_locale()`. Used by `home_gym` / `other_residence` (private categories).
- **New (D-59/D-60):** `gym_profiles` (shared, crowd-sourced) + `locale_equipment_overrides` (per-athlete deltas) + Mapbox-anchored `locale_profiles`. Used by shared categories (gyms/pools/parks).

Plan-gen reads **only the legacy path** (`orchestrator._q_locale_equipment_pool` → `locale_equipment`; `_q_primary_locale` → hardcoded `locale='home'`). This split is the root cause of the empty-`home`-pool failure that blocks every strength session (`equipment_unavailable_*` blockers on pv=59).

**Goal:** every locale — private or public — uses the **same** equipment model (`gym_profiles` + overrides); the athlete marks one locale `home`; `private=TRUE` excludes a locale from crowd-sourcing only; plan-gen reads the unified model across a **multi-locale cluster** (home + nearby).

## 2. Locked decisions (Andy, 2026-06-05)

1. **Drop legacy entirely. No data migration.** Andy is the sole athlete; he re-enters equipment in the new model (consistent with the CLAUDE.md strangler-fig "no back-compat shims" rule).
2. **Unified equipment store:** all locales (incl. `home_gym`/`other_residence`) use `gym_profiles` + `locale_equipment_overrides`. Private locales get the **same equipment picker** as public ones.
3. **`home` flag = reuse `locale_profiles.preferred`** (one TRUE per athlete). Replaces the hardcoded `locale='home'`.
4. **`private` flag = `gym_profiles.private=TRUE`** → excluded from crowd-source discovery/dispute/visibility; otherwise identical storage + picker.
5. **Multi-locale cluster now:** plan-gen resolves a cluster (home + nearby) and 2C produces a per-locale pool for each member. (Session→locale *assignment* is Track 2.)
6. **Out of scope:** `public.exercise_inventory` / `layer0.*` catalog unification = the separate **D-52** migration (`exercise_inventory` is live — `rx_engine` + 7 v1 routes depend on it; NOT orphaned). Not touched here.

## 3. Target data model

### 3.1 KEEP / EXTEND
- `locale_profiles` (composite PK `(user_id, locale)`) + all D-59/D-60 columns: `mapbox_id`, `lat`, `lng`, `category`, `manual_entry`, `gym_profile_id`, `preferred`, `sharing_opt_out`, `locale_terrain_ids`, `place_payload`.
- `gym_profiles` (`equipment` JSON, `toggles` JSON, `private`, `created_by_user_id`, `mapbox_id` nullable-UNIQUE, provenance cols). **Nullable-UNIQUE `mapbox_id` means manual/private locales need no synthetic key** (Postgres allows multiple NULLs).
- `locale_equipment_overrides`, `locale_toggle_overrides` (per-athlete deltas; composite FK `ON DELETE CASCADE`).

### 3.2 DROP
- Table `locale_equipment`.
- Column `locale_profiles.equipment` (legacy free-text).
- The `home/hotel/partner/airport` legacy enum semantics (rows become ordinary athlete-named locales; one carries `preferred=TRUE`).
- Code: `_edit_legacy_locale()` and the legacy branch of `edit_profile()`'s dispatch; the `_is_shared_profile_locale` gate (every locale now uses the shared path).

### 3.3 ADD (DDL — idempotent, in `_PG_MIGRATIONS`)
```sql
-- exactly-one-home enforced in app logic + a partial unique index
CREATE UNIQUE INDEX IF NOT EXISTS locale_profiles_one_home_idx
  ON locale_profiles (user_id) WHERE preferred;             -- ≤1 preferred per athlete
-- (no new columns: private lives on gym_profiles, home on locale_profiles.preferred)
```
DROP statements run **after** the new path is live (sequence in §8). No `INSERT…SELECT` backfill (decision 1).

## 4. Unified equipment read (replaces `_q_locale_equipment_pool`)

A single resolver, used by plan-gen, references, single-session, and the locale list:

```
def locale_effective_tags(db, user_id, locale) -> set[str]:
    profile = locale_profiles[user_id, locale]
    shared  = json(gym_profiles[profile.gym_profile_id].equipment) if linked else set()
    adds    = {t for t,a in overrides[user_id, locale] if a == 'add'}
    removes = {t for t,a in overrides[user_id, locale] if a == 'remove'}
    return (shared | adds) - removes
```

This is exactly `_effective_equipment()` already in `routes/locales.py:352` — promote it to a shared helper (e.g. `locales_equipment.py`) and call it everywhere. **One code path for private and public** (private differs only in discovery/visibility, §6).

## 5. Home + multi-locale cluster resolution

### 5.1 Home (primary)
- `_q_primary_locale` → `SELECT locale FROM locale_profiles WHERE user_id=? AND preferred LIMIT 1`. Error `primary_locale_missing` if none (onboarding must set one).
- Rewire the `WHERE locale='home'` readers (`plans.py`, `dashboard.py`, `coaching.py`, `ad_hoc_workouts.py` city/default lookups) to the `preferred` locale.

### 5.2 Cluster (home + nearby)
- `cluster_locale_ids(db, user_id)` = the home locale **+ every saved locale within `_CLUSTER_RADIUS_KM` of home** by `lat`/`lng` (reuse D-59's `42.2 km` nearby radius). Manual-entry locales (no coords) are included only if explicitly the home or flagged in-cluster.
- Plan-gen passes the full `cluster_locale_ids` to Layer 2C (today stubbed to `[primary_locale]`); 2C already accepts a list and produces one `effective_pool` per locale. **Session→locale assignment stays in Track 2** — Track 1 only guarantees 2C sees every cluster locale's pool.
- **Open decision D-1 (see §11):** cluster = radius-based (proposed) vs. all-saved-locales vs. an explicit per-locale "in training cluster" checkbox.

## 6. Private flag + crowd-sourcing exclusion
- A locale is private when its `gym_profiles.private=TRUE` (residential default; any locale can be marked private at creation).
- **Excluded from:** `nearby_instances` discovery, dispute/`disputed_items`, `contribution_count` provenance, and any cross-athlete `gym_profiles` lookup (all such queries add `WHERE private = FALSE OR created_by_user_id = :uid`).
- **Identical for:** the equipment picker, `equipment`/`toggles` storage, overrides, and the §4 read.
- Residential categories (`home_gym`, `other_residence`) default `private=TRUE` on create; the existing `sharing_opt_out` lets an athlete privatize a normally-shared category too.

## 7. Code changes (file-by-file)

| File | Change |
|---|---|
| `init_db.py` | Add §3.3 index; append DROP `locale_equipment` + DROP COLUMN `locale_profiles.equipment` (end of `_PG_MIGRATIONS`, after rewire ships). |
| `routes/locales.py` | Delete `_edit_legacy_locale`, the dispatch branch, `_is_shared_profile_locale`; route **all** locales through the shared path; default residential `private=TRUE`; `list_profiles` equipment counts via §4. |
| `layer4/orchestrator.py` | `_q_primary_locale` → `preferred`; `_q_locale_equipment_pool` → §4 helper; `cluster_locale_ids` → §5.2 (drop the `[primary_locale]` stub). |
| `routes/references.py` | Equipment union via §4 across selected locales (drop `locale_equipment` join). |
| `routes/plans.py`, `dashboard.py`, `coaching.py`, `ad_hoc_workouts.py` | `locale='home'` city/default lookups → `preferred`. |
| new `locales_equipment.py` | Home of the §4 `locale_effective_tags` + `cluster_locale_ids` helpers (shared by routes + orchestrator). |

**5-file ceiling:** this is ~6 substantive files — propose splitting into **1a** (helper + orchestrator rewire + drop legacy read path; unblocks plan-gen) and **1b** (routes/UI cleanup + DROP DDL).

## 8. Migration / rollout sequence (no data migration)
1. Ship the §4 helper + orchestrator/references rewire reading the **new** model (legacy table still present, now unread).
2. Andy re-enters Home equipment via the (now unified) picker → `gym_profiles` row (`private=TRUE`) + overrides; marks Home `preferred`.
3. Verify plan-gen reads a populated pool (the `effective_pool` shows barbell/rack) — the pv=59 failure is gone.
4. Ship 1b: delete legacy code + DROP `locale_equipment` / `locale_profiles.equipment`.

Neon DDL is Andy's-hands (container egress blocked) — both the index and the DROPs run on his `init_db.py` deploy.

## 9. Partial-update / caching
- Equipment edits already fire `_evict_layer2c_on_equipment_change` (eviction policy `_ALL_ENTRY_POINTS`); keep it. Extend the eviction trigger to the shared-path save (currently it lives in the legacy branch) so the unified picker invalidates 2C.
- Marking `preferred` (home) or cluster membership change must evict Layer 2C (pool inputs changed) — add an eviction on those saves.

## 10. Edge cases
- **No home set:** `primary_locale_missing` → onboarding gate must require one `preferred` locale.
- **Private locale, no Mapbox:** `gym_profiles` row with `mapbox_id=NULL`, `private=TRUE` (nullable-UNIQUE permits it).
- **Two homes:** prevented by the partial unique index + app sets the prior home `preferred=FALSE` on change.
- **Cluster with a far-away saved locale (travel):** excluded by the radius rule (§5.2) so a hotel gym 1,000 km away doesn't inflate a home-week pool.
- **Empty pool (no equipment saved):** synthesis must degrade to bodyweight/Tier-3 proxies (Track 2 concern; note here so the validator demotion accounts for it).

## 11. Open items / decisions
- **D-1 — cluster membership rule** (§5.2): radius-based (proposed) vs all-saved vs explicit checkbox. Drives whether multi-locale needs new UI.
- **D-2 — Track 2 dependency:** session→locale assignment + the per-cluster pool union semantics belong to the synthesis spec; Track 1 stops at "2C sees every cluster locale."
- **D-3 — `exercise_inventory`/D-52:** confirm kept out of this track (recommended).

## 12. Gut check
- **Biggest risk:** the cluster (multi-locale) piece is the only genuinely *new* surface — everything else is delete-legacy + rewire-to-existing-tables. If cluster scope balloons (per-session locale assignment, travel weeks), it could swamp the simple win (one clean home pool). Mitigation: ship 1a (single home pool, unblocks pv=59) before the cluster union lands; gate cluster behind D-1.
- **What might be missing:** the v1 strength UI (`routes/training.py`, `rx.py`) reads `exercise_inventory`, not locales — unaffected — but the v1 `/references/exercises` *does* read `locale_equipment`; it must move to §4 in the same pass or it 500s after the DROP.
- **Best argument against:** doing the full migration now (vs. a 1-line legacy patch) is more work up front — but a patch to a table we're deleting is throwaway, and the split model is itself the bug, so consolidating is the actual fix.
