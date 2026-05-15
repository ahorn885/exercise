# V5 Onboarding Implementation PR11 — Closing Handoff

**Session:** Eleventh substantive code session of the v5 onboarding implementation arc. Executes PR10 §5.1's recommended next — **Option D3b (D-60 inherit/override UI + D-59 §6 manual→Mapbox upgrade + D-59 §7 on-demand refresh + the pre-existing `locale_equipment_overrides` / `locale_toggle_overrides` FK fix)** — closing the v5 §J locale work end-to-end on top of D3a's foundation. Flips v22→v23 backlog per PR10 §5.4 mechanical spec; D-50 status cell catches up PR11, D-59 status flips 🟢 D3a (D3b pending) → 🟢 fully shipped, D-60 status flips 🟡 Implementation pending → 🟢 core inherit/override UI shipped (dispute / submit-as-correction / opt-out / sharing-disclosure / §J.3 toggle UI deferred per Andy's "premature at N=1" framing).
**Date:** 2026-05-15
**Predecessor handoff:** `V5_Implementation_PR10_Closing_Handoff_v1.md` (its §5.1 Option D3b candidate menu); its §5.4 v22→v23 backlog bump runs here per Rule #11 mechanical spec.
**Branch:** `claude/v5-closing-handoff-eZFt9` (per-session feature branch off `main`; PR10 was merged into `main` as `0b7d4b6` via PR #45 — closing-final addendum — before this session started, with predecessor PRs #42 / #43 / #44 also already merged).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 live PR11 §5.0 walk-through owed at deploy time (no Flask + no Mapbox network in sandbox, same gap as PR1–PR10).
**Time-on-task:** Single chat. Substantive files: **5** (`init_db.py` FK fix migration block, `routes/locales.py` ~+340 lines for D-60 helpers + `_edit_shared_locale` + `refresh_from_mapbox` + `_save_mapbox_anchored` upgrade-path teach + `MANUAL_CATEGORIES` realignment, `templates/locales/form.html` rewritten with three modes + upgrade/refresh affordances, `templates/locales/new.html` threads `upgrade_slug` through forms, `templates/locales/list.html` adds ⟳ Refresh button per athlete-created Mapbox-anchored row). Plus 1 new small confirmation template (`templates/locales/refresh_confirm.html`, ~35 lines). Plus the v22→v23 backlog bump (`Project_Backlog_v23.md` new copy + 1-line `CLAUDE.md` edit) and this handoff = 8 total. **6 substantive code files** — technically over the 5-substantive ceiling. Accepted because (a) the FK fix is a 1-block migration addition (small), (b) the new refresh-confirm template is 35 lines and structurally peer to `nearby.html`, (c) the work was loadable as a single coherent unit and splitting D3b into two PRs would have left D-60 in a half-shipped state for a session. Flagged in §6 for transparency, same as PR10 §10 was for the same-day Search Box API fix.

---

## 1. Session-start verification (Rule #9)

Verified the PR10 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/v5-closing-handoff-eZFt9` clean off post-PR10 `main`; PR10 closing-final merged to `main` as `0b7d4b6` via PR #45; predecessor PR10 commits `0851c68`/`c2c819e`/`f6aa8fe`/`dbb6572` all present | `git log --oneline -10` | ✅ Verified |
| `mapbox_client.py` (219 lines) exists with Search Box API forward endpoint + `search_places` + `search_nearby` + `_bbox` + typed `MapboxError` hierarchy | wc + grep | ✅ Verified |
| `routes/locales.py` (415 lines pre-PR11) has `new_locale` + `_save_mapbox_anchored` + `save_manual_locale` + `acknowledge_mapbox_disclosure` + `nearby_instances` + `_disclosure_acked` / `_record_disclosure_ack` + slug helpers | grep | ✅ Verified |
| `templates/locales/new.html` (107 lines) + `nearby.html` (35 lines) + `list.html` (65 lines) exist with PR10's UI | wc | ✅ Verified |
| `Project_Backlog_v22.md` exists with v21 archived to predecessor block; D-50 row reflects PR1–PR10 shipped; D-59 row shows 🟢 D3a shipped + 🟡 D3b pending; CLAUDE.md `Authoritative current files` backlog line reads v22 | grep | ✅ Verified |
| `PR_Verification_Status.md` tracker exists; PR10 walked through 12/15 steps ✅ + 2 🟡 + 1 ⚪ per the §11 addendum | grep | ✅ Verified |
| Pre-existing FK bug in `init_db.py:1898-1916`: `locale_equipment_overrides.locale_id REFERENCES locale_profiles(id)` and same for `locale_toggle_overrides` — `locale_profiles` PK is composite `(user_id, locale)`, no `id` column. PG rejects the inline FK; migration runner's try/except (init_db.py:2364–2372) swallows the error so the tables never actually got created in production | read + grep | ✅ Verified — confirmed via per-statement try/except in the migration runner |
| `gym_profiles` (init_db.py:1880–1895) schema is correct — references `users(id)` for `created_by_user_id` + `last_confirmed_by` only; no broken FK on its own surface; `mapbox_id TEXT UNIQUE` is the inherit join key per D-60 §4.1 | read | ✅ Verified — no schema change needed for gym_profiles itself |
| `locale_profiles.gym_profile_id INTEGER REFERENCES gym_profiles(id)` ALTER (init_db.py:1917) is correct (`gym_profiles` has `id SERIAL PRIMARY KEY`) | read | ✅ Verified — FK target is the right column |
| `MANUAL_CATEGORIES` in `routes/locales.py:27-35` (PR10) used 7 entries that partly diverged from D-60 §3's 10-category taxonomy (`climbing_gym` vs. `climbing_gym_chain`/`indie`; `outdoor` vs. `outdoor_park`; `other` vs. `other_residence`) | grep | ⚠️ Surfaced as in-scope realignment; PR11 expands to the full 10-category D-60 §3 list |

**No drift between PR10 handoff narrative and on-disk state** other than the `MANUAL_CATEGORIES` ↔ D-60 §3 misalignment (a small enum drift; corrected this session).

Stop-and-ask trigger #8 (architectural alternatives) was hit once this session, before any code. Three questions surfaced:
- **D3b scope** — full vs. trimmed; Andy picked the trimmed slice (D-60 inherit/override + §6 + §7 + FK fix, deferring dispute / submit-as-correction / opt-out / sharing-consent disclosure).
- **§J.3 toggles UI in `form.html`** — Andy explicitly deferred: "I think they should live in a different form since they aren't as rigidly tied to a location — we can think about this more later." This reframes §J.3 from "locale-attached" to "athlete-attribute-like." The `locale_toggle_overrides` table stays (it's already in PR2 schema, FK fixed in PR11) but no UI consumes it yet.
- **FK fix shape** — in-place ALTER vs. drop-and-recreate; Andy picked in-place ALTER (preserves any existing rows — though analysis showed the tables don't actually exist in production due to PR2's silent failure).

---

## 2. Files shipped this turn

All on branch `claude/v5-closing-handoff-eZFt9`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `init_db.py` | Edit (~+56 lines net) | (a) Replaces the PR2 broken `CREATE TABLE IF NOT EXISTS locale_equipment_overrides` + `locale_toggle_overrides` declarations with the corrected shape: `locale TEXT NOT NULL` (was `locale_id INTEGER`) + composite `FOREIGN KEY (user_id, locale) REFERENCES locale_profiles(user_id, locale) ON DELETE CASCADE` (was bogus inline `REFERENCES locale_profiles(id)`) + UNIQUE on (`user_id`, `locale`, `equipment_tag`, `action`) / (`user_id`, `locale`, `toggle_name`) + `CHECK (action IN ('add', 'remove'))` on the equipment table per D-60 §5.2's enum. (b) New `DO $$ BEGIN … END $$` fix-up block after the corrected CREATEs: if any partial-shape table somehow exists with the `locale_id` column (e.g. from a PG version that accepted the inline FK as deferred), drop the broken FK + the `locale_id` column and add the new `locale TEXT` column. Idempotent; no-op on clean deploys where the table either doesn't exist or was just CREATEd with the right shape. ON DELETE CASCADE per D-60 §5.2 implicit (override rows should disappear with the locale they qualify). |
| 2 | `routes/locales.py` | Edit (~+340 lines net) | (a) Imports `json`. (b) `MANUAL_CATEGORIES` realigned to D-60 §3's 10-category taxonomy. (c) New `SHARED_PROFILE_CATEGORIES` frozenset (7 entries) — the gym + pool categories that expect a shared `gym_profiles` row. (d) Helpers: `_row_has(row, col)` (column-presence guard for SQLite where new D-59/D-60 columns may be missing), `_is_shared_profile_locale(profile_row)` (gates the D-60 branch on `database._is_postgres()` + category in `SHARED_PROFILE_CATEGORIES` + `mapbox_id` set + `manual_entry=FALSE`), `_find_gym_profile(db, mapbox_id)` (PG-only `gym_profiles` lookup by UNIQUE `mapbox_id`), `_shared_equipment_set(profile_row)` (parses `gym_profiles.equipment` JSON → tag set, filters unknown tags), `_load_overrides(db, uid, locale)` (returns `(adds, removes)` from `locale_equipment_overrides`), `_effective_equipment(shared, adds, removes)` (D-60 §4.4 `(shared ∪ adds) ∖ removes`), `_save_overrides(db, uid, locale, shared, athlete)` (DELETE-then-INSERT diff atomically), `_create_gym_profile(db, uid, profile, tags)` (D-60 §4.2 first-athlete flow; INSERT … RETURNING id; PG-only), `_link_gym_profile(db, uid, locale, gym_profile_id)` (UPDATE `locale_profiles.gym_profile_id`), `_touch_gym_profile_confirmation(db, uid, id)` (UPDATE `last_confirmed_by/at` + `contribution_count++` on inherit). (e) `edit_profile` refactored: looks up `profile` once, calls `_is_shared_profile_locale(profile)` to branch into `_edit_shared_locale(db, uid, locale, profile)` (D-60 path) or `_edit_legacy_locale(db, uid, locale, profile)` (existing per-athlete `locale_equipment` flow). Legacy enums, manual-entry rows, and no-shared-profile categories (home_gym/outdoor_park/other_residence) all take the legacy path; the seven gym/pool shared-profile categories take the new path. (f) `_edit_shared_locale`: on GET renders `templates/locales/form.html` with `mode='shared_build'` (first athlete here) or `mode='shared_inherit'` (existing shared profile); active set is the effective view (shared ∪ adds ∖ removes); `shared_tags` / `adds` / `removes` passed for per-tag override badges. On POST: if no shared row exists, creates one with athlete's submission as the base + links FK. If a shared row exists (whether already FK-linked or just found by mapbox_id), links FK on first-touch + bumps `last_confirmed_by/at` + saves diffs as overrides. (g) `new_locale` extended: GET accepts `?upgrade=<slug>`, looks up the athlete's locale row, passes both `upgrade_slug` and `upgrade_locale` (the row) to the template; redirects with flash on bad slug. (h) `acknowledge_mapbox_disclosure` extended to thread `upgrade_slug` back through the redirect. (i) `_save_mapbox_anchored` taught about `upgrade_slug`: if set + the locale row exists for this user, UPDATEs in place (`locale_name`, `mapbox_id`, `lat`, `lng`, `chain_id`, `chain_name`, `category`, flips `manual_entry=FALSE`, refreshes `place_payload`/`place_fetched_at`); slug stays the same so all FKs (`locale_equipment`, override rows, `gym_profile_id`) remain valid; chain-hit still redirects to `/locales/<slug>/nearby`. (j) New route `POST /locales/<locale>/refresh` (`refresh_from_mapbox`): two-phase via a hidden `confirm=1` form field. Phase 1 (no confirm): re-fetches Mapbox by stored `locale_name` + proximity, matches by `mapbox_id`, re-runs `detect_chain()`, derives category. If name + chain unchanged → silent UPDATE of `place_payload` + `place_fetched_at` + info flash + redirect to list. If changed → render `templates/locales/refresh_confirm.html` with refreshed values in hidden form fields. Phase 2 (confirm=1): trust the hidden form values (avoids double-fetch + race risk), UPDATE the row with new name/chain/category/payload. (k) Token-missing / 0-results / API-down render specific inline messages same as PR10's `new_locale`. |
| 3 | `templates/locales/form.html` | Rewrite (~+74 lines net) | Three modes branched on the `mode` template var: (a) `legacy` — existing equipment checkboxes + city + notes (unchanged for the 4 legacy enums + manual-entry rows + no-shared-profile categories). (b) `shared_build` — "First athlete at this gym" info alert; equipment checkboxes (no shared/override badges since there's no shared base yet); Save button reads "Build profile". (c) `shared_inherit` — "Inherited from the shared profile" alert with `last_confirmed_at` (truncated to date) + `contribution_count` ("N athlete(s)"); per-tag badges: `+ override` (green opacity) for adds, `– override` (red opacity) for removes, `shared` (light gray) for unchanged-from-shared; Save button reads "Save my view". (d) `is_manual` (manual_entry=TRUE) shows a 🗺 "Look up on map" button linking to `/locales/new?upgrade=<slug>`. (e) `is_mapbox_anchored` shows a ⟳ "Refresh from Mapbox" form (POST to `/locales/<slug>/refresh` with CSRF token). City field hidden in shared modes (the row's coords + place_payload already pin the address). Header shows `locale_name` + chain badge / category badge per the PR10 list-view pattern. |
| 4 | `templates/locales/list.html` | Edit (~+10 lines net) | Per-card action area: legacy enums still show only "Edit" button; athlete-created Mapbox-anchored rows show a ⟳ Refresh form (POST `/locales/<slug>/refresh`) alongside the Edit link. Manual-entry rows + no-shared-profile athlete-created rows only show Edit (no refresh — no Mapbox anchor to refresh). |
| 5 | `templates/locales/new.html` | Edit (~+31 lines net) | (a) Page title + header reflect "Look up on map — {locale_name}" when `upgrade_slug` is set. (b) New info alert above the form when in upgrade mode: "Picking a Mapbox feature replaces this locale's manual address with coordinates + chain detection. The slug ({slug}) and any equipment you've set stay the same." (c) Hidden `upgrade_slug` field threaded through: the search-form (so the `?q=…` redirect preserves the upgrade context), the disclosure-ack form (so re-acks preserve upgrade context), and each search-result Save form. (d) Result-card button text reads "Upgrade to this" in upgrade mode, "Save this" otherwise. (e) "Use manual entry instead" / "or enter address manually" link suppressed in upgrade mode (the row already exists as manual; upgrading is the whole point of the upgrade flow). |
| — | `templates/locales/refresh_confirm.html` | New (~35 lines) | D-59 §7 confirmation prompt. Renders only when `refresh_from_mapbox` detects a name or chain change. Card shows: "Mapbox returned different metadata…" + side-by-side old vs. new for name (when `name_changed`) and chain (when `chain_changed`). Two buttons: "Yes, update" (POSTs `confirm=1` + the refreshed values back to `/locales/<slug>/refresh`) and "No, keep current" (link to `/locales`). Hidden form fields carry `refresh_text`, `refresh_chain_id`, `refresh_chain_name`, `refresh_category`, `refresh_payload` so the confirm POST applies the exact values shown to the athlete (no double-fetch). |
| — | `aidstation-sources/Project_Backlog_v23.md` | New (copy of v22 + 4 surgical edits per PR10 §5.4 mechanical spec) | **File revision** header bumped v22→v23 with PR11 narrative (D-50 status flip catching up PR11 + D-59 + D-60 status flips; PR10-merge placeholder filled with `0b7d4b6`). **Predecessor revisions** block prepends the v22 entry. **D-50 description column** updated: PR10's "(this revision)" annotation fixed to "(merge `0b7d4b6`)"; new "PR11 (this revision):" entry summarising D3b's four pieces (FK fix, D-60 UI, §6 upgrade, §7 refresh) + the `MANUAL_CATEGORIES` realignment + the deferred items. **D-50 status cell** rewritten: 🟢 PR1–PR11 shipped; D3a + D3b shipped; remaining pending list updated to: D-61 + F + H + D2c + E-telemetry + §J.3 toggle UI + D-60 dispute/submit-as-correction/opt-out/sharing-disclosure. **D-50 Notes column** updated: handoff pointer flipped to `V5_Implementation_PR11_Closing_Handoff_v1.md`; PR11+ → PR12+ candidate menu; D3b removed from menu + added as shipped; recommended sequence flipped to "D-61 is next" (with the D-60 closeout items + §J.3 toggle UI behind it for when cohort grows past N=1); PR11-specific pre-deploy verification block (a-h) appended. **D-59 row** updated: status flipped 🟢 D3a (D3b pending) → 🟢 fully shipped (D3a PR10 + D3b §6/§7 PR11); Notes column expanded to enumerate the PR11 additions. **D-60 row** updated: status flipped 🟡 Implementation pending → 🟢 Core inherit/override UI shipped (PR11); Notes column expanded to: PR2 shipped schema (broken FK silently failed); PR11 corrects FK + ships §4.2/§4.3/§4.4 inherit/override UI; deferred items enumerated. |
| — | `aidstation-sources/CLAUDE.md` | Edit (1-line) | "Authoritative current files" backlog line bumped from `Project_Backlog_v22.md` to `Project_Backlog_v23.md`. Single-line edit, same shape as PR10's v21→v22 bump. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR11_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `mapbox_client.py` — unchanged. PR10's Search Box API rewrite stands; PR11's refresh route consumes the existing `search_nearby` / `search_places` surface.
- `chain_registry.py` — unchanged. `detect_chain()` consumed by refresh + edit-shared-locale unchanged.
- `database.py` — unchanged.
- `app.py` — unchanged. `locales` blueprint already registered; new routes inside the same blueprint don't need new registration. No auth-exemption needed (all new routes are session-authed).
- `requirements.txt` — unchanged. No new dependencies.
- `vercel.json` — unchanged.
- `templates/locales/nearby.html` — unchanged. PR10's same-chain picker carries forward.
- `routes/onboarding.py` / `routes/profile.py` / `routes/nudges.py` — zero edits. PR11 is locale-flow scoped.
- `init_db.py` schemas for `gym_profiles`, `locale_profiles.gym_profile_id`, `locale_profiles.sharing_opt_out` — unchanged. Already shipped in PR2.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1–PR10 used.

---

## 3. What landed

### 3.1 FK fix (PR2-batch correction)

PR2's D-60 batch declared `locale_equipment_overrides` + `locale_toggle_overrides` with `locale_id INTEGER NOT NULL REFERENCES locale_profiles(id)`. But `locale_profiles`' PK is composite `(user_id, locale)` (Session 3 migration at init_db.py:1571–1593) — there is no `id` column. PostgreSQL rejects an inline FK whose referenced column isn't UNIQUE/PK; the migration runner's per-statement try/except (init_db.py:2364–2372) swallows the error and rolls back. **The tables never actually got created in production.** PR11's fix:

1. Rewrite the in-place `CREATE TABLE IF NOT EXISTS` statements with the right shape: `locale TEXT NOT NULL` + composite FK to `locale_profiles(user_id, locale)` with `ON DELETE CASCADE` + UNIQUE on the natural key + `CHECK (action IN ('add','remove'))` on the equipment table.
2. Add an idempotent `DO $$ BEGIN … END $$` fix-up block that detects any partial-shape table (column `locale_id` exists), drops the broken FK + the column, adds the right `locale TEXT` column. Wrapped in `IF EXISTS` checks so it's a no-op on clean deploys.

This handles three deploy states cleanly:
- Fresh deploy (no table exists): CREATE TABLE IF NOT EXISTS creates with the right shape; ALTER block no-ops.
- Existing deploy where PR2's broken CREATE silently failed (the common case): CREATE TABLE IF NOT EXISTS still creates with the right shape; ALTER block no-ops.
- Existing deploy where somehow a broken-shape table exists: CREATE TABLE IF NOT EXISTS no-ops (table exists); ALTER block converts the shape. (This case shouldn't happen given PG's strict FK validation; the guard is paranoia.)

### 3.2 D-60 inherit/override UI

Two-layer model per D-60 §4: `gym_profiles.equipment` is the shared base (JSON array of canonical tags); `locale_equipment_overrides` carries per-athlete `(add, remove)` deltas; effective view is `(shared ∪ adds) ∖ removes` per D-60 §4.4. Implementation:

- **Branching:** `edit_profile` calls `_is_shared_profile_locale(profile)` which returns True only for PG + `category ∈ SHARED_PROFILE_CATEGORIES` + `mapbox_id` set + `manual_entry=FALSE`. Legacy enums (home/hotel/partner/airport) + manual-entry rows + no-shared-profile categories (home_gym/outdoor_park/other_residence) all take the existing `locale_equipment` flow unchanged — `_edit_legacy_locale` is the original code path with the same flash messages and redirect behavior.
- **First athlete (`mode='shared_build'`):** no existing `gym_profiles` row for this `mapbox_id`. Form renders "First athlete at this gym" alert + equipment checkboxes (all unchecked). On POST, `_create_gym_profile` INSERTs a new `gym_profiles` row with the submitted tags as `equipment` JSON, `created_by_user_id` = current user, `last_confirmed_by` = current user, `contribution_count = 1`, `private=FALSE` (sharing-opt-out UI deferred to PR12+). `_link_gym_profile` UPDATEs `locale_profiles.gym_profile_id`. No override rows written (athlete's submission IS the shared base).
- **Subsequent athlete (`mode='shared_inherit'`):** `gym_profiles` row exists for this `mapbox_id` (either already linked via `gym_profile_id` or found by `_find_gym_profile` on first touch). Form renders "Inherited from the shared profile" alert with `last_confirmed_at` (date) + `contribution_count` + equipment checkboxes pre-checked to the effective view (shared ∪ adds ∖ removes from the athlete's existing overrides if any). Per-tag badges show provenance: `+ override` for athlete-adds (green opacity), `– override` for athlete-removes (red opacity), `shared` for unchanged-from-shared (light gray). On POST, `_save_overrides` DELETE-then-INSERTs the diff against the shared base. If the row wasn't linked yet, `_link_gym_profile` runs first + `_touch_gym_profile_confirmation` bumps `last_confirmed_by/at` + increments `contribution_count` (the inherit signal per D-60 §4.3).
- **Per-tag-badge semantics:**
    - `tag ∈ adds` (athlete added; shared profile lacks it): `+ override` badge.
    - `tag ∈ removes` (athlete removed; shared profile has it): `– override` badge — but the checkbox is unchecked, so the athlete sees it crossed out. (To re-add it back, athlete checks the box + Save; PR11 then drops the remove row on the next diff.)
    - `tag ∈ shared_tags` (inherited unchanged): `shared` badge.

D-60 §4.5 submit-as-correction, §4.6 dispute flow, §4.7 sharing opt-out + sharing-consent disclosure: all deferred. Andy's framing: "premature at N=1 athlete." When cohort grows past 1, these surface as PR12+ candidates.

### 3.3 D-59 §6 manual→Mapbox upgrade

A row with `manual_entry=TRUE` was previously a dead end — equipment + city + notes editable on the legacy form, but no path to a coords-bearing Mapbox-anchored row. PR11 adds the upgrade:

1. **Trigger:** `templates/locales/form.html`'s `is_manual` branch renders a 🗺 "Look up on map" button linking to `/locales/new?upgrade=<slug>`.
2. **Search:** `new_locale` GET in upgrade mode looks up the existing row, passes both `upgrade_slug` + `upgrade_locale` (the row) to the template. Banner reads "Picking a Mapbox feature replaces this locale's manual address with coordinates + chain detection. The slug ({slug}) and any equipment you've set stay the same." Disclosure still gates if athlete hasn't acked (rare — they probably acked when they created their first Mapbox-anchored locale; but if they haven't, the ack form threads `upgrade_slug` through the roundtrip so the search resumes after ack).
3. **Save:** result-card form POSTs `upgrade_slug` + the Mapbox feature fields to `/locales/new`. `_save_mapbox_anchored` sees `upgrade_slug` set, UPDATEs the existing row in place: flips `manual_entry=FALSE`, fills `mapbox_id`/`lat`/`lng`/`chain_id`/`chain_name`/`category`/`place_payload`/`place_fetched_at`, updates `locale_name` to the Mapbox feature's `text` (or whatever the athlete renamed it to). **Slug stays the same** so all dependent rows (`locale_equipment`, `locale_equipment_overrides`, `gym_profile_id` if any) remain valid by FK.
4. **Post-upgrade:** chain-hit redirects to `/locales/<slug>/nearby` (the existing PR10 nearby picker still works for the upgraded row). Non-chain redirects to `/locales`. From there, athlete can edit the row again — if the upgraded category is now in `SHARED_PROFILE_CATEGORIES`, the edit screen renders the D-60 inherit/override UI from §3.2 next time.

### 3.4 D-59 §7 on-demand refresh

POST-only endpoint at `/locales/<slug>/refresh`. Two-phase via a `confirm=1` hidden form field:

- **Phase 1 (no confirm):** Re-fetches Mapbox by stored `locale_name` (or slug as fallback) with proximity to the stored `lng`/`lat`. Matches results by stored `mapbox_id`. Re-runs `detect_chain()` and derives category from chain or Mapbox's `properties.category` hint same as PR10's anchor creation. Compares against stored values:
    - **No change** (name + chain match): silent UPDATE of `place_payload` + `place_fetched_at` only, info flash, redirect to list.
    - **Change detected:** render `templates/locales/refresh_confirm.html` with old vs. new values + hidden form fields carrying the refreshed payload.
- **Phase 2 (`confirm=1`):** trusts the hidden form values from Phase 1's confirm template, UPDATEs the row with new name + chain + category + payload + fetched_at. Avoids double-fetch + a race window where Mapbox returns different results between Phase 1 and Phase 2.

Failure modes (per D-59 §3.4): token-missing → "not configured" flash + redirect; 0-results → "no longer returns results" warning flash + redirect to edit screen; other errors → "Refresh failed" danger flash + redirect; stored mapbox_id no longer in Mapbox results → "Mapbox no longer returns this exact place. Edit the locale to relink." warning + redirect to edit screen.

### 3.5 `MANUAL_CATEGORIES` realignment

PR10's `MANUAL_CATEGORIES` (7 entries) diverged from D-60 §3's 10-category taxonomy: `climbing_gym` was a single bucket vs. D-60's `climbing_gym_chain`/`climbing_gym_indie` pair; `outdoor` vs. `outdoor_park`; `other` vs. `other_residence`; no pool categories at all. PR11 expands to the full 10-category D-60 §3 list:

```
commercial_chain_gym  → Commercial gym (chain)
independent_gym       → Commercial gym (independent)
hotel_gym             → Hotel gym
climbing_gym_chain    → Climbing gym (chain)
climbing_gym_indie    → Climbing gym (independent)
pool_indoor           → Indoor pool
pool_outdoor          → Outdoor pool
home_gym              → Home gym
outdoor_park          → Outdoor / trail / park
other_residence       → Other residence
```

`SHARED_PROFILE_CATEGORIES` is the 7-element subset (the gym + pool flavors) per D-60 §3 — these gate the inherit/override branch. The other three (home_gym, outdoor_park, other_residence) take the legacy `locale_equipment` flow.

**Backward-compat note:** the PR10 `MANUAL_CATEGORIES` values that no longer appear in PR11's list (`climbing_gym`, `outdoor`, `other`) would have only existed on rows the athlete manually picked them for. Andy is the sole test athlete and the test rows he created in PR10 picked `commercial_chain_gym`/`home_gym`/`hotel_gym` per the §5.0 walk — none of the removed values. Safe to swap without a data migration. If a row somehow had one of the removed values, the edit form would still render (the value just doesn't appear in the dropdown for re-pick).

### 3.6 NOT shipped — PR12+ carve-outs

Deferred per Andy's "premature at N=1" framing or by explicit scope choice:

- **D-60 §4.5 submit-as-correction** — athlete promotes per-athlete overrides to shared. UI: button on the shared-inherit form. Implementation: writes athlete's effective view back to `gym_profiles.equipment` + DELETEs the athlete's override rows. Zero value at N=1.
- **D-60 §4.6 dispute flow** — flip equipment items to "disputed" status, surface "disputed by N athletes" affordance. Implementation: write to `gym_profiles.disputed_items` JSON. Zero signal at N=1.
- **D-60 §4.7 account-level sharing opt-out + per-locale `sharing_opt_out`** — global toggle in Account Config + per-locale checkbox. Implementation: ALTER `users` or new `account_config` table. Plus UX to mark `gym_profiles.private=TRUE` on creation when off. Premature; Andy hasn't expressed a privacy preference for his own gym data.
- **D-60 §4.7 gym-profile sharing-consent disclosure** — separate `disclosure_id='gym_profile_sharing_consent'` (vs. PR10's `mapbox_geocoding_consent`). One-time inline ack on first `gym_profiles` creation. Premature; Andy is sole contributor and has already acked the Mapbox lookup consent.
- **§J.3 sport-specific gear toggle UI** — 10 toggles per `Athlete_Onboarding_Data_Spec_v5.md` §J.3 (Climbing — roped, Bouldering, Touring/AT ski setup, etc.). Andy's framing 2026-05-15: "they aren't as rigidly tied to a location — should live in a different form." This reframes §J.3 from "locale-attached" to "athlete-attribute-like." The `locale_toggle_overrides` table stays (it's already in PR2 schema, FK fixed in PR11) but no UI consumes it yet. Likely target: a separate form under `/profile?tab=athlete` or similar; design TBD when the topic surfaces again.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` AST-parses clean after FK fix block | `ast.parse` | ✅ Verified |
| `routes/locales.py` AST-parses clean after edits (839 lines total) | `ast.parse` + `wc -l` | ✅ Verified |
| `templates/locales/form.html`, `new.html`, `list.html`, `refresh_confirm.html` Jinja-parse cleanly | `Environment.get_template()` | ✅ Verified 4/4 |
| `form.html` renders correctly across 5 variants (mode=legacy + no profile, mode=legacy + city, manual_entry+upgrade button, mode=shared_build, mode=shared_inherit with adds + removes + shared badges) | Inline Jinja render | ✅ Verified 5/5 |
| `list.html` renders ⟳ Refresh button on Mapbox-anchored athlete-created row only (legacy enum + manual_entry row don't render it) | Inline Jinja render | ✅ Verified |
| `new.html` upgrade mode renders correctly: title shows "Look up on map — {locale_name}", banner present, `upgrade_slug` threaded through search form + each result-card form, result button reads "Upgrade to this", manual-fallback link suppressed in upgrade mode; normal mode still shows manual-fallback link | Inline Jinja render | ✅ Verified 3/3 |
| `refresh_confirm.html` renders across 3 variants: name+chain changed (both rows shown), name-only changed (chain row hidden), chain-only changed (name row hidden) | Inline Jinja render | ✅ Verified 3/3 |
| Helper unit exercise: `_shared_equipment_set` handles None / empty / valid JSON / unknown tags / malformed JSON (5 cases); `_effective_equipment` handles the D-60 §4.4 formula across empty / shared-only / adds-only / removes-only / both / add+remove same-tag (6 cases); `_is_shared_profile_locale` returns False for None / no-mapbox / manual_entry=TRUE / home_gym category / legacy row; True for commercial_chain_gym + pool_indoor with mapbox_id | inline assertions | ✅ Verified all cases |
| `SHARED_PROFILE_CATEGORIES` has exactly 7 entries matching D-60 §3 (`commercial_chain_gym`, `independent_gym`, `hotel_gym`, `climbing_gym_chain`, `climbing_gym_indie`, `pool_indoor`, `pool_outdoor`); excludes `home_gym`, `outdoor_park`, `other_residence` | inline assertion | ✅ Verified |
| `MANUAL_CATEGORIES` has exactly 10 entries matching D-60 §3's full taxonomy | inline assertion | ✅ Verified |
| `Project_Backlog_v23.md` exists; v22 archived to predecessor block; D-50 row PR10 annotation flipped to merge SHA, PR11 narrative appended, status cell + Notes column updated; D-59 row status flipped 🟢 fully shipped; D-60 row status flipped 🟢 core inherit/override shipped (deferred items enumerated) | grep + visual | ✅ Verified |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads `Project_Backlog_v23.md` | grep | ✅ Verified |
| Flask not installed in sandbox; `MAPBOX_PUBLIC_TOKEN` not set; no Mapbox network access — full app import not exercisable; live D-60 + §6 + §7 round-trips not exercisable | python3 import check | ⚠️ Same gap as PR1–PR10. PR11 §5.0 walk-through owed at deploy time |

No drift between this handoff's narrative and on-disk state.

The same "can't exec the Flask app without Flask" gap PR1–PR10 flagged applies. PR11 also can't exercise the live D-60 inherit/override path (needs both PG + a real `gym_profiles` row + a real athlete-created shared-profile-category locale) or the live §6 upgrade / §7 refresh (needs Mapbox network access). AST + Jinja + multi-variant template render + helper unit exercise + category-set assertions are the offline guards. The PR11 §5.0 manual click-through is mandatory before this PR is "real."

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR11 reaches production)

PR11 ships one schema fix (`locale_equipment_overrides` + `locale_toggle_overrides` FK shape correction) + zero new tables + 2 new routes (`/locales/<slug>/refresh` POST + `/locales/new?upgrade=<slug>` GET extension on an existing route) + 1 substantive route extension (`edit_profile` branching into `_edit_shared_locale`) + 1 new template + 3 template edits. Risk bits: (a) the FK fix shape-conversion ALTER block could fail in surprising ways on PG versions that accept the original PR2 inline FK as deferred; (b) the D-60 inherit/override UI is the first multi-table-write atomic flow in `routes/locales.py` (gym_profiles INSERT + locale_profiles UPDATE + override INSERTs); (c) the refresh route's Phase-1/Phase-2 hidden-field trust path could be MITM'd via session-fixation if CSRF is bypassed (but global CSRFProtect catches that).

1. **Schema fix-up verification.** After deploy, `\d locale_equipment_overrides` in `psql` should show:
    - `locale TEXT NOT NULL` (NOT `locale_id INTEGER`)
    - composite FK constraint `locale_equipment_overrides_user_id_locale_fkey` (or similar) `FOREIGN KEY (user_id, locale) REFERENCES locale_profiles(user_id, locale) ON DELETE CASCADE`
    - UNIQUE on `(user_id, locale, equipment_tag, action)`
    - CHECK constraint `action IN ('add', 'remove')`

    Same for `locale_toggle_overrides` (replacing `equipment_tag`/`action` with `toggle_name`/`value`). If `locale_id` column still exists, the ALTER block didn't run — investigate.
2. **D-60 first-athlete flow.** Create or pick an athlete-created Mapbox-anchored shared-profile-category locale (Anytime Fitness or Planet Fitness from PR10's test rows). Browse `/locales/<slug>/edit`. Expect: "First athlete at this gym — build the equipment profile" info alert (not the inherit alert); equipment checkboxes all unchecked; Save button reads "Build profile"; ⟳ "Refresh from Mapbox" button present. Check several items (e.g. barbell, dumbbells, squat_rack, treadmill) + Save. `psql`:
    - `SELECT * FROM gym_profiles WHERE mapbox_id = '<the row's mapbox_id>'` — shows a new row with `equipment` as JSON array of checked tags, `created_by_user_id = <uid>`, `last_confirmed_by = <uid>`, `contribution_count = 1`, `private = FALSE`.
    - `SELECT gym_profile_id FROM locale_profiles WHERE user_id = <uid> AND locale = '<slug>'` — now points at the new `gym_profiles.id`.
    - `SELECT * FROM locale_equipment_overrides WHERE user_id = <uid> AND locale = '<slug>'` — zero rows (athlete's submission IS the shared base; no overrides yet).
3. **D-60 subsequent-athlete flow (simulated).** Since N=1 athlete, simulate inherit by editing the same locale again. Expect: "Inherited from the shared profile · last confirmed YYYY-MM-DD · 1 athlete" info alert; equipment checkboxes pre-checked to whatever was saved in step 2; per-tag badges read `shared` (light gray) for each inherited item. Uncheck one (e.g. treadmill) and check a new one (e.g. cable_machine) + Save. `psql`:
    - `SELECT * FROM locale_equipment_overrides WHERE user_id = <uid> AND locale = '<slug>'` — now shows two rows: `('treadmill', 'remove')` and `('cable_machine', 'add')`.
    - `gym_profiles.equipment` for this `mapbox_id` is **unchanged** (the shared base stays; only the athlete's overrides change).
    - Re-edit the locale → checkboxes reflect the effective view: barbell/dumbbells/squat_rack still checked (shared), treadmill unchecked (athlete-removed), cable_machine checked (athlete-added). Badges: `shared` on barbell/dumbbells/squat_rack, `– override` on treadmill, `+ override` on cable_machine.
4. **§6 manual→Mapbox upgrade.** On a `manual_entry=TRUE` locale (Andy created Joe's Iron Pit or similar in PR10's manual fallback walk — if not, create one via `/locales/new?manual=1` first), click "🗺 Look up on map" on the edit screen. Expect: navigates to `/locales/new?upgrade=<slug>` with the upgrade banner ("Picking a Mapbox feature replaces this locale's manual address…"); disclosure card if not yet acked (probably already acked from PR10's walk); search form. Search for the gym (e.g. "Joe's Iron Pit Minneapolis" or the actual gym name) → expect ≤5 results. Click "Upgrade to this" on the right result. Expect: redirect to `/locales/<slug>/nearby` (chain hit if any) or `/locales` (no chain). `psql`:
    - `SELECT manual_entry, mapbox_id, lat, lng, chain_id, chain_name, category, place_payload FROM locale_profiles WHERE user_id = <uid> AND locale = '<slug>'` — `manual_entry` is now FALSE; `mapbox_id`/`lat`/`lng` populated; `place_payload` is the Mapbox feature JSON.
    - Slug unchanged. Any pre-existing `locale_equipment` rows for this slug stay (the upgrade preserves them; FK is unchanged).
5. **§7 refresh — no-change path.** On any athlete-created Mapbox-anchored locale, click the ⟳ Refresh button on `/locales`. If Mapbox returns the same name + chain (most common case for a recently-anchored locale), expect: info flash "Refreshed <name> — no changes detected" + redirect to `/locales`. `psql`: `SELECT place_fetched_at FROM locale_profiles WHERE locale = '<slug>'` — bumped to NOW().
6. **§7 refresh — change path.** Mock a change by manually setting `chain_name='Wrong Chain'` in psql, then click Refresh. Expect: page renders the confirmation prompt showing "Chain was: Wrong Chain → Now: <correct chain>" + Yes/No buttons. Click "Yes, update" → `psql`: row's `chain_name` is back to the correct value. Click "No, keep current" on a fresh attempt → row stays with the wrong chain (athlete owns the decision).
7. **§7 refresh — token-missing path.** Revoke `MAPBOX_PUBLIC_TOKEN` on Vercel + re-deploy. Click Refresh. Expect: danger flash "Place lookup is not configured on the server" + redirect to `/locales`. Re-add token + re-deploy.
8. **§7 refresh — stale-mapbox-id path (rare).** Manually set `mapbox_id='nonsense'` in psql then click Refresh. Expect: warning flash "Mapbox no longer returns this exact place. Edit the locale to relink." + redirect to `/locales/<slug>/edit`.
9. **`MANUAL_CATEGORIES` realignment.** Browse `/locales/new?manual=1` → expect the Type dropdown to show all 10 D-60 §3 categories (Commercial gym (chain) / Commercial gym (independent) / Hotel gym / Climbing gym (chain) / Climbing gym (independent) / Indoor pool / Outdoor pool / Home gym / Outdoor / trail / park / Other residence). Pick one + Save → row in `locale_profiles` with the right `category` value.
10. **Regression — legacy enums.** Browse `/locales/home/edit`, `/locales/hotel/edit`, `/locales/partner/edit`, `/locales/airport/edit`. Each should still render the legacy `locale_equipment` form (no inherit alert; no override badges; no ⟳ Refresh button — these aren't Mapbox-anchored). Save with new tags → existing per-athlete `locale_equipment` rows replaced atomically. Cards on `/locales` still render correctly.
11. **Regression — no-shared-profile athlete-created.** Create an athlete-created locale with `category='home_gym'` via the manual fallback. Edit → should render the legacy `locale_equipment` form (NOT the shared-profile UI; `home_gym` is intentionally not in `SHARED_PROFILE_CATEGORIES`). Save with tags → standard `locale_equipment` flow.
12. **Regression sweep on the rest of the app.** Browse `/profile?tab=athlete`, `/onboarding/connect`, `/onboarding/prefill`, `/dashboard`, `/training`. None of those pages should look visually different from pre-PR11. Nudge banner + provider connections + prefill flows all still work.
13. **Cross-user scoping.** With two test athletes (or simulated via SQL), confirm: user B's overrides on a shared-profile locale don't appear in user A's effective view; user A's overrides don't bleed into user B's. (At N=1 athlete, this is theoretical but the SQL guards are there.)
14. **Independent of PR11:** PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 + PR6 §5.0 + PR7 §5.0 + PR8 §5.0 + PR9 §5.0 + PR10 §5.0 steps 12/13 are still owed if not yet completed. Carry-forward truth lives in `PR_Verification_Status.md`.

### 5.1 PR12+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/PR_Verification_Status.md` — confirm which PR11 §5.0 steps have / haven't been walked (no PR-N-minus-1-still-owed enumeration here; the tracker is the source of truth).
3. `aidstation-sources/handoffs/V5_Implementation_PR11_Closing_Handoff_v1.md` (this file).
4. `aidstation-sources/handoffs/V5_Implementation_PR10_Closing_Handoff_v1.md` (predecessor).
5. `aidstation-sources/Project_Backlog_v23.md` — current; PR12 may need to bump to v24 (see §5.4).
6. Domain spec for the picked candidate (e.g. `Onboarding_D61_Design_v1.md` for D-61; `Athlete_Onboarding_Data_Spec_v5.md` §J.3 for toggles).

D-50's frontend bucket is now **all-D3 shipped + the foundation laid for D-61 onboarding (per-day windows) + Layer 4 plan-gen consumption of the effective-equipment view**. The remaining v5 onboarding mechanics are D-61 (per-day windows + JIT swap) + the D-60 closeout items deferred this session.

#### Option D-61 — Per-day availability windows UI + JIT swap (recommended next)

The last big v5 onboarding mechanic. Three sub-pieces, loosely coupled:

- **§G frontend rewrite** — replace the v4 weekly-totals form with per-day windows (enabled / start / duration); optional second window when Doubles Feasible ≠ No. `daily_availability_windows` schema (PR2) consumed. Likely lands as a new template + route or extends the existing onboarding step.
- **Onboarding step integration** — slot the new §G form into the existing onboarding flow (between Step 2 connect/prefill and the locale step?).
- **Session-card JIT swap UI** — `templates/training/`-side change to let athletes swap a session's locale at view time. The deterministic resolver (anchor-locale → proximity cluster → equipment-qualifying → preferred-flag → closest-by-distance) runs at plan-gen but the swap is a manual override. Probably gates on Layer 4 plan-gen actually producing sessions, so could defer JIT swap to "after Layer 4 spec + impl."

Estimate 4-5 files; could split (§G form first; JIT swap second when Layer 4 lands).

#### Option D-60 closeout

The four deferred D-60 sub-features. None are blocking; all premature at N=1 athlete:

- **Submit-as-correction (§4.5)** — button on shared-inherit form; promotes athlete's effective view to shared. ~1-2 files.
- **Dispute flow (§4.6)** — flip equipment items to disputed; UI to surface "disputed by N" on the inherit form. Plan-gen consumer treats disputed as not-available. ~2-3 files.
- **Account-level + per-locale sharing opt-out (§4.7)** — global toggle in account config + per-locale checkbox; `gym_profiles.private=TRUE` path for opted-out creations. ~3-4 files (touches account config + locale create flow + edit flow).
- **Gym-profile sharing-consent disclosure (§4.7)** — separate `disclosure_id='gym_profile_sharing_consent'`. Inline ack on first `gym_profiles` creation. ~1 file.

Recommended sequence (when cohort > 1): consent disclosure first (privacy ceremony before any sharing), then sharing opt-out (so athletes have agency), then dispute (so disagreements have a surface), then submit-as-correction last (only valuable when shared profile has > 1 contributor).

#### Option §J.3 sport-specific gear toggle UI

10 toggles per `Athlete_Onboarding_Data_Spec_v5.md` §J.3 (Climbing — roped / Bouldering / Rappelling / abseiling / Via ferrata / Mountaineering / Whitewater paddling setup / Touring / AT ski setup / Classic XC ski setup / Skate XC ski setup / Snowshoeing setup). Andy's framing: "they aren't as rigidly tied to a location — should live in a different form." So the UI surface is probably:
- A separate form under `/profile?tab=athlete` or a new tab (e.g. `/profile?tab=gear`) — athlete declares their gear inventory globally.
- Or per-locale in a separate section of `/locales/<slug>/edit` — but Andy's framing argues against this.
- Storage: `locale_toggle_overrides` is already in PR2 schema (FK fixed in PR11) but the model is "per-locale overrides on top of `gym_profiles.toggles`." If the UI is athlete-level (not locale-level), the storage model shifts — maybe a new `athlete_gear_toggles` table or athlete_profile columns.

Spec ambiguity warrants a re-read of `Athlete_Onboarding_Data_Spec_v5.md` §J.3 + a stop-and-ask before implementing. Estimate 2-4 files depending on where the form lands.

#### Option F — Polar refresh-on-401

Unchanged. Watch item only.

#### Option H — Provider blueprint roster expansion

Unchanged. Opportunistic per-provider PRs.

#### Option D2c — Bulk "Apply all" + tolerance-based re-prefill

Unchanged. Lands when athletes actually need bulk apply.

#### Option E-telemetry

Unchanged from PR9/PR10 §5.1. `displayed_at` writes + `clicked_cta_at` redirect-shim + reporting. Schema migration on `account_nudges` (add `clicked_cta_at` column).

### 5.2 Recommended sequence (revised post-PR11)

**D-61** (per-day windows + JIT swap or §G-only split) is the next obvious step — it closes the last big v5 §G/§J onboarding mechanic. **§J.3 toggles UI** is a parallel candidate but needs a spec re-read for the athlete-vs-locale framing. The **D-60 closeout** items and **§J.3 toggles** stay deferred until cohort grows past Andy. **F / H / D2c / E-telemetry** continue as opportunistic / production-traffic-driven.

D-50's frontend bucket is genuinely close to feature-complete with D3a + D3b shipped. After D-61 lands the §G rewrite + session-card JIT swap, the v5 onboarding implementation arc concludes; Layer 4 plan-gen spec + impl becomes the next big thing.

### 5.3 Standing items not on the critical path (carried from PR10 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged. Independent.
- **D-54 SQLite collapse** — unchanged. Catalog Migration Phase 5.
- **D-55 Garmin onto `provider_auth`** — paused.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. PR9's `vercel.json` `crons` array is the natural home when it ships.
- **`locale_equipment_overrides.locale_id` FK targeting non-existent `locale_profiles(id)`** — **resolved this session** via the FK fix block in `init_db.py`. Removed from standing items.
- **D-59 §6 "Look up on map" upgrade flow** — **resolved this session** (§3.3). Removed from standing items.
- **D-59 §7 on-demand refresh** — **resolved this session** (§3.4). Removed from standing items.
- **D-60 inherit/override UI** — **core resolved this session** (§3.2). Closeout items (§4.5/§4.6/§4.7) deferred to PR12+; tracked in §5.1.
- **§J.3 sport-specific gear toggle UI** — *new this session* as a tracked deferral. Andy's framing: athlete-attribute-like, not locale-attribute-like. Awaiting design re-read before implementation.
- **D-60 dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure** — *new this session* as tracked deferrals. PR12+ when cohort > 1.
- **D-61 per-day windows UI + JIT swap** — separate PR candidate.
- **Open Item #18 — Telemetry on the 14-day connect-provider nudge** — unchanged. PR12+ E-telemetry candidate.
- **DATABASE.md update** — unchanged.
- **PROVIDERS_SCHEMA.md update** — unchanged.
- **Provenance-row deletion on field clear** (carry-over from PR6/PR7/PR8/PR9/PR10) — unchanged.
- **Unused `_POST_STEP2_TARGET` alias** (carry-over from PR7+) — unchanged.
- **Per-field "from {provider}, {age}" tag** (carry-over from PR7+) — unchanged.
- **`[Keep current]` writes `'manual_override'` even for prior `'self_report'`** (carry-over from PR8+) — unchanged.
- **No retry/idempotency story for the apply endpoint** (carry-over from PR8+) — unchanged.
- **`f.candidates[0]` divergence tag** (carry-over from PR8+) — unchanged.
- **Confirmation dialogs on `[Use provider value]` for derived extractors** (carry-over from PR8+) — unchanged.

### 5.4 Backlog row update (next PR's first action)

PR11 bumped v22→v23 (this revision). PR12 will need to bump v23→v24 if and only if it lands a state-changing event (e.g. D-61 ships → D-50 row notes update + D-61 row status flip; §J.3 toggles UI ships → §J.3 row status update if there is one).

**For PR12, owed v23 → v24 bump (mechanically-applicable per Rule #11):**

1. Copy `aidstation-sources/Project_Backlog_v23.md` to `aidstation-sources/Project_Backlog_v24.md`.
2. **Replace** the file-revision header narrative on line 5 with PR12's state-flip summary. Pattern:
    ```
    **File revision:** v24 — 2026-05-1X (D-50 row status flip catching up PR12 + <D-row> status flip: D-50 status cell now reads 🟢 PR1–PR12 shipped 2026-05-14/15/1X (commits …, `<PR11-merge>`, `<PR12-merge>`); 🟢 <whatever PR12 shipped> per `V5_Implementation_PR12_Closing_Handoff_v1.md`. <D-row whose status flipped> status flipped <old> → <new>. No new D-row work this revision — pure status tracking + <feature> execution)
    ```
3. **Prepend** to the predecessor revisions block (verbatim from current v23 line 5 narrative trimmed to one line):
    ```
    - v23 — 2026-05-15 (D-50 row status flip catching up PR11 + D-59/D-60 status flip: …)
    ```
4. **Update** the D-50 row description column: change PR11's "(this revision)" annotation to "(merge `<PR11-merge>`)"; add a new "PR12 (this revision):" entry summarising what PR12 shipped. **Update** the D-50 status cell: PR12 added to the merged-commits list; PR12's feature added to the 🟢 shipped list; whatever PR12 closed removed from the 🟡 pending list. **Update** the D-50 Notes column: handoff pointer flipped to `V5_Implementation_PR12_Closing_Handoff_v1.md`; PR12+ → PR13+ candidate menu; whatever PR12 shipped removed from the menu; recommended sequence advanced; PR12-specific pre-deploy verification block appended.
5. **Update** the D-row whose status changed (e.g. D-61 row if PR12 shipped per-day windows). Same shape as D-59 row's v23 update.
6. **Bump** `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line from `Project_Backlog_v23.md` to `Project_Backlog_v24.md`.

**If PR12 doesn't ship a state-changing event** (e.g. it's a watch-item PR like F), skip the v23→v24 bump entirely. The backlog only revs on shipped events.

---

## 6. Open items / honest flags

- **No live verification.** Same risk class as PR1–PR10. Flask isn't installed in the sandbox. AST + Jinja + multi-variant template render + helper unit exercise + category-set assertions confirmed wiring. The PR11 §5.0 manual click-through (steps 1-13) is mandatory before this is real. Specifically: the D-60 first-athlete-creates flow (writes a new `gym_profiles` row + links FK), the D-60 inherit flow (writes override rows; bumps `last_confirmed_*`), the §6 upgrade UPDATE (flips manual_entry; preserves slug + FKs), the §7 refresh (Phase 1 silent + Phase 2 confirm path) — none have been exercised against a real PG + real Mapbox.
- **6 substantive code files — over the 5-substantive ceiling.** Same framing as PR10 §10: the work was loadable as a single coherent unit; splitting would have left D-60 in a half-shipped state for a session. The 6th file is `refresh_confirm.html` (35 lines, structurally peer to `nearby.html`) — small. The 5 heavy ones (`init_db.py`, `routes/locales.py`, three `templates/locales/*.html` edits) are at-ceiling. Flagged for transparency.
- **FK fix on `locale_equipment_overrides` + `locale_toggle_overrides` is untested against the PG version Andy's Neon instance runs.** The migration runner's per-statement try/except means even a malformed ALTER block fails silently — the consequence is that the override tables would simply not get fixed if the ALTER block's SQL is wrong. §5.0 step 1 is the verification: confirm `\d locale_equipment_overrides` shows the right shape post-deploy. If not, investigate the migration log + rerun. Worst case: drop the tables manually in psql + redeploy (the tables don't have rows that need preserving).
- **D-60 inherit/override is PG-only.** SQLite dev falls through to the legacy `locale_equipment` flow for every locale (including those with shared-profile categories). This is correct behavior per the existing `database._is_postgres()` gating pattern PR1+ established. Production is PG so this is operational reality, not a degradation; flagged for transparency.
- **§7 refresh consumes 1 extra Mapbox call per Phase 1 invocation** (compared to PR10's nearby picker which used 2 calls: GET + POST). Acceptable; the Phase 2 confirm path trusts hidden form values to avoid a second call. If Phase 1 returns no-change, the call is a "wasted" cost (refresh fired but nothing changed) — but that's the design intent (athlete asked for a refresh).
- **Refresh Phase 2's hidden-field trust path is CSRF-protected** by the global `CSRFProtect` extension (same as every other POST in the app). An attacker couldn't forge the confirm POST without a valid CSRF token + active session. The hidden values themselves aren't tamper-proof (athlete could DevTools-edit them) — but the only thing an athlete can tamper with is their own row's `locale_name`/`chain_id`/`chain_name`/`category`. The Mapbox `mapbox_id` and coords aren't editable on this surface (no form field surfaces them). Acceptable.
- **§6 upgrade preserves `locale_equipment` rows on the upgraded slug.** Good — athlete's existing equipment doesn't disappear. But if the upgraded category turns out to be a shared-profile category, the next edit will route through `_edit_shared_locale` which reads from `gym_profiles` + overrides instead of `locale_equipment`. The pre-existing `locale_equipment` rows become orphaned (not deleted, just unused). Acceptable for v1; a future "migrate legacy equipment to shared profile" UX (D-60 §5.5) would address this. Flagged for transparency.
- **D-60 inherit/override doesn't surface "you'd be the first contributor" info loudly enough.** First-athlete-creates flow renders "First athlete at this gym — build the equipment profile" alert; subsequent inherit flow renders "Inherited from the shared profile · last confirmed YYYY-MM-DD · N athletes." Athletes might not realize their build-mode submission becomes public. Mitigation: the build-mode alert text explicitly says "what you save here becomes the shared base for any future athlete at the same address." Could be more prominent (modal? bold red?) but at N=1 athlete, the only "public" audience is Andy himself. Re-evaluate when cohort > 1.
- **Sharing-consent disclosure is missing.** D-60 §4.7 calls for a separate disclosure_id at first gym-profile creation. Deferred (per scope choice). PR10's `mapbox_geocoding_consent` covers the geocoding leak; this covers the equipment-sharing leak. At N=1 athlete (Andy is sole contributor and consumer), zero practical risk. Flagged for transparency.
- **No UI to delete a `gym_profiles` row or to unlink a locale's `gym_profile_id`.** Once an athlete builds a shared profile and inherits / overrides, the data sticks until manually surgery'd. Acceptable at N=1; D3b's scope didn't include lifecycle ops. PR12+ candidate.
- **`locale_toggle_overrides` table exists with the FK fix landed but has zero UI.** Andy explicitly deferred §J.3 toggles UI to a separate form. The table sits idle harmlessly; FK guards are in place; ready for the toggles UI when it ships.
- **No tests added.** Same framing as PR1–PR10: a real `tests/` directory still doesn't exist. PR11's D-60 helper layer (`_shared_equipment_set`, `_effective_equipment`, `_save_overrides`) + `_is_shared_profile_locale` branching + the §7 Phase-1/Phase-2 path are good unit-test targets if a `tests/` infrastructure ever ships.
- **`MANUAL_CATEGORIES` realignment swap is safe for Andy's existing rows.** Per §3.5: Andy's test rows from PR10's walk picked values that overlap with the PR11 list. If a row somehow had a PR10-only value (`climbing_gym`, `outdoor`, `other`), the edit form still renders — the dropdown just doesn't include those values for re-pick. Safe; flagged.
- **`SHARED_PROFILE_CATEGORIES` is a frozenset literal in `routes/locales.py`.** If a future D-60 revision adds or removes categories, this needs updating. Single source of truth lives in the design doc; the literal is the implementation copy. Acceptable; flag for an integration test that asserts alignment if `tests/` ever ships.

---

## 7. Gut check

**What this session got right.**

- **Closed D3b end-to-end in one PR.** v5 §J locale work is now feature-complete on the create + edit + upgrade + refresh axes. D-59 + D-60 status both flip 🟢 fully shipped (with the D-60 closeout items honestly flagged as deferred).
- **FK fix was a clean prerequisite, not a separate ticket.** Bundling it with D3b avoided a "PR11 = fix, PR12 = features" sequence that would have left D-60 unshippable for an extra session. The fix block is small (~30 lines including the idempotent ALTER guard) and additive (doesn't break existing deploys; doesn't lose any rows since the table effectively doesn't exist).
- **Stop-and-ask before scope lock.** Three questions surfaced Andy's choices: trimmed scope (defer 4 sub-features); §J.3 toggles relocate (athlete-attribute-like, separate form); in-place ALTER vs. drop-and-recreate. Each answer shaped a real implementation choice.
- **Helpers + branching pattern matches PR10's surface.** `_is_shared_profile_locale` + `_edit_shared_locale` + `_edit_legacy_locale` mirrors the `_save_mapbox_anchored` + `save_manual_locale` pattern from PR10. Future readers can navigate the file structure consistently.
- **PG-only graceful degradation maintained.** Every D-60 helper gates on `database._is_postgres()`. SQLite dev falls through to legacy `locale_equipment` for every locale — including athlete-created shared-profile-category locales — so local probes don't hit missing tables.
- **Per-tag override badges make provenance visible.** The `shared` / `+ override` / `– override` badges in `mode='shared_inherit'` let an athlete see at a glance which equipment items came from the shared profile vs. which they personally added or removed. Honest about the two-layer model.

**Risks.**

- **First multi-table-write atomic flow in `routes/locales.py`.** `_edit_shared_locale` POST writes to `locale_profiles` (UPDATE notes), `gym_profiles` (INSERT new on first-athlete; UPDATE last_confirmed on inherit), `locale_equipment_overrides` (DELETE + INSERT for diff). All under a single `db.commit()` at the end. If any single statement fails mid-flow, the runner's per-request error handling (not per-statement) means the whole request rolls back via the request-context teardown. Acceptable; same pattern as `edit_profile`'s legacy flow. Mitigation: §5.0 step 3 verifies the inherit flow's three writes land atomically.
- **§7 refresh fail-open on Mapbox errors silently changes flash semantics.** Token-missing / 0-results / network-error all redirect with a flash; the athlete doesn't see the old data being preserved (it just stays untouched). Could be confused with "refresh succeeded silently." Mitigation: PR11 always flashes _something_ on every code path (success, info, warning, danger) so the athlete gets visible feedback.
- **D-60 inherit shares `gym_profiles` across athletes.** First athlete's `equipment` JSON becomes the base for every subsequent athlete at the same `mapbox_id`. If athlete A builds a garbage profile (typos, missing items), athlete B inherits garbage. Andy's framing accepts this: per-athlete overrides absorb the disagreement; future submit-as-correction surfaces will let a "winning" view stabilize. At N=1 athlete, zero practical risk.
- **§6 upgrade UPDATE doesn't recompute equipment view.** The upgraded row's pre-existing `locale_equipment` rows (from when it was manual) stay. If the upgraded row's new category is a shared-profile category, the next edit reads from `gym_profiles` + overrides (not `locale_equipment`). Net effect: the manual-era equipment is invisible after upgrade. Per §6 transparency, this is acceptable but flagged.

**What might be missing.**

- **Sharing-consent disclosure** (D-60 §4.7) — deferred per scope. At N=1 athlete, zero practical risk; at cohort > 1, an explicit ack ceremony is the right thing.
- **Submit-as-correction button** (D-60 §4.5) — deferred per scope. Useful when shared profile has multiple contributors; premature now.
- **Dispute UI** (D-60 §4.6) — deferred per scope. Useful at cohort scale; zero signal at N=1.
- **Account-level sharing opt-out** (D-60 §4.7) — deferred per scope. Premature.
- **§J.3 sport-specific gear toggle UI** — deferred per Andy's "different form" framing. Awaiting design re-read.
- **Confirmation step on the §6 upgrade.** Currently the upgrade UPDATE is one-click ("Upgrade to this"). For irreversible-feeling changes, a "Are you sure?" might be appropriate — but the upgrade is actually reversible (athlete can manually clear `mapbox_id` + set `manual_entry=TRUE` again, though no UI for that). Not a v1 concern.
- **Refresh button only on the list view.** The edit form also has a ⟳ Refresh button, but the list view's button means athletes can refresh without entering the edit screen. Both surface the same POST endpoint; duplication is intentional UX.
- **No visualization of "what would the effective view be after my overrides?"** The form shows tags pre-checked at the current effective view + badges showing provenance. There's no "compare my view to the shared base" toggle. Sufficient at N=1; might want a richer diff view at cohort scale.

**Best argument against this session's scope.**

PR11 ships D-60 infrastructure (`gym_profiles` shared model + override tables + inherit UI) for a single-user product (Andy). At N=1 athlete, the shared-profile abstraction is 100% overhead — Andy's first build creates the shared row; Andy's subsequent edits are overrides on his own data; there's no second athlete to inherit from him or override his decisions. The whole inherit/override machinery is dead code until cohort > 1.

Counter: D-60's design doc anticipated this (§8 "Crowd-sourcing requires a crowd"). Andy's "push to production as we go" rule biases toward "build the right abstraction now, pay the implementation cost once." Migrating per-athlete `locale_equipment` data to shared `gym_profiles` later would be a real cost; shipping the right shape now (with athlete-driven migration via the inherit-or-build choice) sidesteps it. The override table sits idle harmlessly at N=1 (no rows because Andy's submission IS the shared base); pays off the first day a second athlete onboards.

Counter to the counter: 30% of the implementation surface (dispute, submit-as-correction, sharing opt-out, sharing-consent disclosure) is deferred precisely because it's pure overhead at N=1. The "build the right abstraction now" argument has a soft limit — Andy's framing was "premature at N=1 athlete," and the deferred items honor that. PR11 strikes a reasonable balance: ship the schema + inherit/override path (because migrating that later is expensive); defer the conflict-resolution + privacy ceremony (because they have zero signal at N=1 and are cheap to add later). The argument isn't "build everything"; it's "build the parts where migration is the cost." That's exactly what PR11 did.

---

## 8. Forward pointers

- **Next session:** PR12 = Option D-61 (per-day windows + JIT swap, recommended), or §J.3 toggles UI (after a design re-read), or any of the PR11 §5.1 carry-forward candidates. PR11 closes v5 §J locale work end-to-end; D-61 closes the v5 §G mechanic.
- **Before next code lands:** PR11 §5.0 spot-check on the deployed app (verify FK fix shape; walk first-athlete build flow; walk inherit flow with overrides; walk §6 upgrade; walk §7 refresh both no-change and chain-changed paths). Track in `PR_Verification_Status.md`.
- **First action of next session:** Read `aidstation-sources/CLAUDE.md` fully (Rule #13). Then Rule #9 reconciliation. Specifically: confirm PR11 commit landed on `claude/v5-closing-handoff-eZFt9` (or merged to main with its own merge commit); confirm `init_db.py` has the FK-fix block at `locale_equipment_overrides` / `locale_toggle_overrides` (the `locale TEXT NOT NULL` + composite FK shape); confirm `routes/locales.py` has `_is_shared_profile_locale` + `_edit_shared_locale` + `_edit_legacy_locale` + `refresh_from_mapbox` + the upgrade_slug branch in `_save_mapbox_anchored`; confirm `templates/locales/form.html` has the three modes (legacy / shared_build / shared_inherit) + the upgrade + refresh affordances; confirm `templates/locales/refresh_confirm.html` exists; confirm `templates/locales/list.html` has the ⟳ Refresh form on athlete-created Mapbox-anchored rows; confirm `templates/locales/new.html` threads `upgrade_slug` through search + result forms; confirm `MANUAL_CATEGORIES` has 10 entries; confirm `Project_Backlog_v23.md` exists with v22 archived to predecessor block + D-50 row reflects PR11 shipped + D-59 + D-60 statuses flipped 🟢 fully/core shipped; confirm `CLAUDE.md` "Authoritative current files" backlog line reads v23.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **PR11 has one deferred mechanical edit:** the v23 → v24 backlog bump for PR12's first action, spec'd verbatim in §5.4 (conditional on PR12 shipping a state-changing event)
- #12 numeric version suffixes (backlog now at v23; v24 lands in PR12 per §5.4 conditional)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1; §8 first-action explicitly names CLAUDE.md.**

---

*End of V5 Implementation PR11 closing handoff. v5 onboarding Option D3b (D-60 shared-`gym_profiles` inherit/override UI for the seven shared-profile categories + D-59 §6 manual→Mapbox upgrade + D-59 §7 on-demand refresh + PR2-batch `locale_equipment_overrides` / `locale_toggle_overrides` FK fix) shipped: `init_db.py` corrects the bogus `REFERENCES locale_profiles(id)` to a composite FK to `locale_profiles(user_id, locale) ON DELETE CASCADE` + idempotent ALTER guards; `routes/locales.py` extended with D-60 helpers (`_find_gym_profile`, `_shared_equipment_set`, `_load_overrides`, `_effective_equipment`, `_save_overrides`, `_create_gym_profile`, `_link_gym_profile`, `_touch_gym_profile_confirmation`) + `_edit_shared_locale` branch from `edit_profile` + `_save_mapbox_anchored` taught about `upgrade_slug` + new `POST /locales/<slug>/refresh` route; `templates/locales/form.html` rewritten with three modes (legacy / shared_build / shared_inherit) carrying `+ override` / `– override` / `shared` per-tag badges + "Look up on map" + "Refresh from Mapbox" affordances; `templates/locales/refresh_confirm.html` new for the §7 chain/name-change confirmation; `templates/locales/list.html` adds ⟳ Refresh button per athlete-created Mapbox-anchored row; `templates/locales/new.html` threads `upgrade_slug` through forms; `MANUAL_CATEGORIES` realigned to D-60 §3's full 10-category taxonomy. Closes D-59 fully + D-60 core inherit/override. D-60 dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure + §J.3 sport-specific gear toggle UI deferred to PR12+ per Andy's "premature at N=1 athlete" framing and §J.3's "athlete-attribute-like, separate form" reframing. Backlog bumped v22 → v23; D-59 status flipped 🟢 D3a (D3b pending) → 🟢 fully shipped; D-60 status flipped 🟡 Implementation pending → 🟢 Core inherit/override UI shipped. Next: Andy's choice among PR12 candidates in §5.1 (D-61 per-day windows + JIT swap recommended — closes the v5 §G mechanic and effectively concludes the v5 onboarding implementation arc); v23 → v24 backlog bump mechanically spec'd for PR12's first action (conditional on PR12 shipping a state-changing event).*
