# V5 Implementation — Track 1 Locations Consolidation: canonical-direct equipment model (1a + 1b)

**Date:** 2026-06-05
**Branch:** `claude/practical-wozniak-WSKk4`
**PR:** (open to `main`)
**Issue:** Track 1 of the 3-track redesign (`Locations_Consolidation_Design_v1.md`, now **APPROVED**). Fixes the pv=59 `equipment_unavailable` vocabulary-mismatch root cause.

---

## ⚡ Diagnostic token (read first — every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` — WebFetch 403s (Vercel deployment protection); fetch via the **Vercel MCP `web_fetch_vercel_url`** tool. Untruncated runtime logs: Vercel dashboard (team `team_rkZGxltBw2ykWtrIPCYy16JZ`, project `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`); the runtime-log MCP truncates the message column (Rule #14).

---

## 1. What this session was

Continued from the prior handoff's named next move. Andy **approved the Track 1 design** and directed "build all of Track 1." Implemented Track 1 end to end (the design's own 1a→1b split) as two commits on `claude/practical-wozniak-WSKk4`. One mid-session stop-and-ask resolved a genuine cross-track conflict (see §3). Container can't reach Neon/run the live app, so live UI + the DDL are owed-Andy's-hands (the design's §8 already gates 1b's DROP behind his run).

## 2. Shipped

### 2.1 — 1a: canonical-direct equipment pool (commit 1)
- **`locations.py`** (NEW) — the authoritative domain module the design demands:
  - `primary_locale(db, uid)` — home = `locale_profiles.preferred` (raises `PrimaryLocaleMissing`).
  - `locale_effective_tags(db, uid, locale)` — `(shared gym_profiles.equipment ∪ adds) ∖ removes`, **layer0 canonical names**.
  - `cluster_locale_ids(db, uid)` — home + saved locales within **42.2 km** (great-circle haversine); home first.
  - `cluster_effective_tags(db, uid, cluster)` — sorted union pool for 2C.
- **`layer4/orchestrator.py`** — `_q_primary_locale` → `locations.primary_locale` (reads `preferred`, not the hardcoded `locale='home'`); `_q_locale_equipment_pool` → `locations.locale_effective_tags`; the full cone now passes the **real cluster** to 2C (un-stubs `cluster_locale_ids=[primary_locale]`).
- This removes the snake_case-`public.equipment_items.tag` vs Title-case-canonical mismatch at the source: the pool 2C resolves `equipment_required` against is now the same canonical vocabulary.
- **Tests:** new `tests/test_locations.py` (9); `tests/test_layer4_orchestrator.py` fake-DB queue sequence updated for the new query path.

### 2.2 — 1b: unify the locale equipment model (commit 2)
- **`routes/locales.py`** — picker reads `layer0.equipment_items` (`_layer0_equipment` → canonical names grouped by `equipment_category`, value==label==canonical); **unified `_edit_locale`** (build new / own-edit / peer-inherit) replaces the `_edit_legacy_locale`/`_edit_shared_locale` split + `_is_shared_profile_locale` dispatch; store holds canonical names (gym_profiles.equipment + `locale_equipment_overrides.equipment_tag`); **home management** — atomic `_set_home` (route `POST /locales/<l>/home`), `_ensure_home` first-locale-auto-home wired into all create paths; residential categories (`RESIDENTIAL_CATEGORIES`) default `gym_profiles.private=TRUE`; `list_profiles` counts via `locations`; `delete_locale` no longer touches `locale_equipment`.
- **`routes/references.py` + `routes/purchases.py`** — **degraded** (Andy approved 2026-06-05): the equipment-availability filter (`/references/exercises`) + the "you already own this" hint (purchases) need the public int-id catalog (`exercise_equipment`), which is retired-vs-canonical until **Track 3** migrates the catalog to layer0. References keeps the `where_available` bucket filter + counts via `locations`; purchases' owned-hint is off. Both flagged in-code.
- **`coaching.py`** — equipment list = canonical names via `locations`; locale resolves to `preferred` when the passed slug isn't a real row. **`routes/plans.py` + `routes/dashboard.py`** — home-city lookups `locale='home'` → `preferred`. **`routes/admin.py`** — dropped the `locale_equipment` wipe (overrides cascade on the `locale_profiles` delete).
- **`init_db.py`** — at the `_PG_MIGRATIONS` tail: `CREATE UNIQUE INDEX locale_profiles_one_home_idx ON locale_profiles(user_id) WHERE preferred` + `DROP TABLE IF EXISTS locale_equipment` + `ALTER TABLE locale_profiles DROP COLUMN IF EXISTS equipment`; removed the `locale_equipment` seed/backfill (Phase 4). (Public `equipment_items` table physically kept — `exercise_equipment`/purchases still FK it; Track 3 retires it.)
- **`templates/locales/list.html`** — Home (★) badge + "Make home" action. `form.html` unchanged (variable shapes preserved: `equipment_categories` same `(cat,[(value,label)])` shape, `active`/`adds`/`removes`/`shared_tags` now canonical-name sets, `mode` ∈ {`legacy`,`shared_inherit`}).
- **Tests:** `tests/test_locales.py` + `tests/test_redesign_locales_list_render.py` rewired for the unified path; **full suite 1998 passed / 16 skipped**.
- Design spec marked **APPROVED**.

## 3. The one stop-and-ask (cross-track conflict)

Design decision 8 ("public equipment vocab retires entirely in Track 1") **conflicts** with decision 6/§12 ("the exercise-catalog bulk incl. `exercise_equipment` is Track 3"): three v1 strength-UI surfaces (`/references/exercises` availability filter, purchases owned-hint, coaching equipment list) depend on the public int-id vocabulary that can't be canonical-ized without Track 3. Andy chose **"Degrade now"** — these are v1 pages slated for replacement (CLAUDE.md "revisit later: v1 strength UI"); degrade cleanly rather than build a throwaway canonical→public-id bridge. Coaching works directly on canonical names (prompt text). Restored properly in Track 3.

## 4. Owed (Andy's hands — Neon egress + live app blocked from the container)

> These are the design's §8 rollout steps. 1b's code reads the new model; the DROP + the live proof are Andy's-hands.

1. **Run A0 first if not yet done** — `etl/sources/dedupe_layer0_equipment_items.sql` on Neon (prior handoff §5.1; the canonical picker reads the deduped catalog).
2. **`python init_db.py` on Neon** — applies `locale_profiles_one_home_idx`, `DROP TABLE locale_equipment`, `DROP COLUMN locale_profiles.equipment` (all idempotent, tail of `_PG_MIGRATIONS`). Container egress to Neon is blocked, so this can't run from a web session.
3. **Re-enter Home gear in the unified canonical picker** (`/locales/home/edit` or a new locale), **mark it Home** (★ Make home). The legacy enum no longer carries equipment; `preferred` is now the home flag and the orchestrator requires one (else `primary_locale_missing`).
4. **Re-run a cold PGE plan.** Win: **no `equipment_unavailable` blockers** (the pv=59 root cause), no `volume_band` blockers on Build/Peak/Taper, no Engine-A 504, blocks → `ready`. Read the diag endpoint's `effective_pool` — it should show barbell/rack/etc. (canonical names), not empty.
5. **Live UI smoke** (container can't run the Flask app): `/locales` list + edit + Make-home + a public-gym inherit; `/references/exercises` (bucket filter works, availability filter intentionally off); `/purchases` (owned-hint off).

## 5. Next move

- **File the 3-track program as a GitHub epic** (still owed from the prior handoff).
- **Track 2 — determinism-first Layer 4 synthesis** (NOT yet specced; spec just-in-time): make the feasible pool authoritative (tool-schema-constrain `exercise_id` ∈ pool ∖ 2D-excluded), deterministic session-allocation + intensity stages, wire `rx_engine`, demote feasibility validator rules to warnings. **Session→locale assignment + per-cluster pool union semantics live here** (Track 1 stops at "2C sees every cluster locale's pool").
- **Track 3 — D-52 catalog migration** (parallel/after): retire `public.exercise_inventory`/`exercise_equipment`/`equipment_items` → `layer0.*`; **restores the references/purchases surfaces degraded in §3**.
- **Engine A (#423)** is in from the prior session (PR #425 merged); the next cold plan with both #423 + Track 1 is the real grid + equipment test.

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (owed Neon deploys updated this session)
4. This handoff (diagnostic token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Authoritative resolver (canonical names) | `locations.py` | `grep -n "def locale_effective_tags\|def cluster_locale_ids\|def primary_locale" locations.py` |
| Orchestrator reads preferred + cluster | `layer4/orchestrator.py` | `grep -n "locations.primary_locale\|locations.cluster_locale_ids\|cluster_effective_tags" layer4/orchestrator.py` |
| Picker reads layer0 canonical | `routes/locales.py` | `grep -n "def _layer0_equipment\|FROM layer0.equipment_items" routes/locales.py` |
| Unified edit path (no legacy/shared split) | `routes/locales.py` | `grep -n "def _edit_locale\|def make_home\|RESIDENTIAL_CATEGORIES" routes/locales.py` |
| One-home index + legacy DROP | `init_db.py` | `grep -n "locale_profiles_one_home_idx\|DROP TABLE IF EXISTS locale_equipment\|DROP COLUMN IF EXISTS equipment" init_db.py` |
| v1 surfaces degraded | `routes/references.py` / `routes/purchases.py` | `grep -n "Track 3\|degrad" routes/references.py routes/purchases.py` |
| Design approved | `aidstation-sources/Locations_Consolidation_Design_v1.md` | `grep -n "APPROVED" Locations_Consolidation_Design_v1.md` |

---

## 7. Test / verification state
- Container: **full `tests/` suite 1998 passed / 16 skipped** (incl. new `tests/test_locations.py` ×9; rewired `test_locales.py`, `test_redesign_locales_list_render.py`, `test_layer4_orchestrator.py`). `app.py` imports + the `make_home` route registers. **No DB/LLM/live-app run from the container** (Neon egress + no Flask runtime) — the cold re-run + UI smoke (§4) after the owed Neon work is the real proof.

*End of handoff.*
