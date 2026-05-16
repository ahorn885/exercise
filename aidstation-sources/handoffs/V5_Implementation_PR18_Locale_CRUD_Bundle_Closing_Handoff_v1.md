# V5 Onboarding Implementation PR18 — Locale-CRUD Bundle Closing Handoff

**Session:** Ships the PR11-follow-on locale-CRUD bundle per the mechanical scope spec'd in `V5_Implementation_PR11_Verification_Followon_Handoff_v1.md` §3 + §4. Four bundle items (A address-display, B 🔴 refresh-broken-on-rename fix, C duplicate-mapbox_id detection, D delete with privacy split rule) plus the outdoor_park reclassification + `home_gym`/`other_residence` label tweaks. Item E (retire legacy `LOCALES` enum cards) stays its own PR per the predecessor handoff §3.5 because of `routes/coaching.py` + `routes/references.py` hard consumers.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Implementation_PR11_Verification_Followon_Handoff_v1.md` (PR11 §5.0 walked 10/14 ✅; 5 follow-on items captured A–E).
**Branch:** `claude/review-handoff-docs-SiQAY`.
**Status:** 🟢 4 substantive code files shipped (`mapbox_client.py` + `routes/locales.py` + `templates/locales/list.html` + `templates/locales/form.html`); 4 bookkeeping files (CLAUDE.md, Project_Backlog v33 → v34, PR_Verification_Status PR18 section + aggregate refresh, this handoff). PR18 §5.0 has 12 testable steps owed for the post-merge walk.
**Adjacent work:** Layer 4 prompt-body design arc proceeded in parallel sessions; independent track, no interaction. Layer 4 single-session prompt body shipped this same date (per `V5_Design_Layer4_Prompts_SingleSession_Closing_Handoff_v1.md`). Both tracks share the date; no cross-track dependencies.

---

## 1. Session-start verification (Rule #9)

The predecessor PR11-follow-on handoff §6 forward-pointer claimed: branch state clean; `Project_Backlog_v33.md` is highest; `prompts/Layer4_SingleSession_v1.md` exists at 589 lines; `Layer4_Spec.md` 1747 lines with 4 hits on `request_sport_unavailable_at_locale`; `routes/locales.py` has `MANUAL_CATEGORIES` at 10 entries + `SHARED_PROFILE_CATEGORIES` at 7 entries (PR18 to bump to 8); `mapbox_client.py` has `search_places` + `search_nearby` + the `MapboxError` hierarchy (PR18 to add `retrieve`); `templates/locales/refresh_confirm.html` exists.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| Working tree clean on session branch | `git status` | ✅ |
| `Project_Backlog_v33.md` is highest | `ls Project_Backlog_v*.md \| sort -V \| tail` | ✅ |
| `Layer4_SingleSession_v1.md` at 589 lines | `wc -l` | ✅ |
| `Layer4_Spec.md` at 1747 lines (1 over the 1746 the SingleSession handoff §7 cited — net +1 from the §4.4 precondition row insert) | `wc -l` | ✅ (1747 — handoff §7 cited 1746 pre-amendment) |
| `request_sport_unavailable_at_locale` appears 4× in spec | `grep -c` | ✅ |
| `routes/locales.py` `MANUAL_CATEGORIES` has 10 entries | inline read | ✅ |
| `routes/locales.py` `SHARED_PROFILE_CATEGORIES` has 7 entries (pre-PR18) | inline read | ✅ |
| `routes/locales.py` `LOCALES = ['home','hotel','partner','airport']` | inline read | ✅ |
| `mapbox_client.py` has `search_places` + `search_nearby` + no `retrieve` | grep | ✅ |
| `templates/locales/` has `form.html`, `list.html`, `nearby.html`, `new.html`, `refresh_confirm.html` | `ls` | ✅ |

No drift.

---

## 2. Session narrative — bundle execution per predecessor handoff §3 + §4

Chat opened with Andy linking the PR11-follow-on handoff + the Layer 4 SingleSession handoff. Both tracks were live candidates. Per the First-session checklist + Rule #9, I reconciled handoff narrative against on-disk state (§1 above; clean), then surfaced the track choice via `AskUserQuestion`: PR18 locale-CRUD bundle vs. per-tier T1/T2 prompt vs. race-week-brief prompt vs. Layer 4 §14 retrospective.

Andy picked **PR18 locale-CRUD bundle**. Second `AskUserQuestion` resolved the only stop-and-ask pre-question Andy hadn't already decided in the predecessor handoff: delete UX = **browser `confirm()`** (vs. dedicated confirm template), matching the lo-fi consistency of the rest of the app.

No stop-and-ask triggers fired during execution — the bundle's mechanical scope was fully specified in the predecessor handoff §3 + §4. Items A/B/C/D + outdoor_park + label swaps + the delete UX pick covered every degree of freedom.

---

## 3. What landed per item

### 3.1 Item A — display address on `/locales` + edit views

**Helper:** `_display_address(profile_row)` in `routes/locales.py`. JSON-parses `place_payload` and returns `properties.full_address` (preferred), then `properties.place_formatted` (fallback), then `''`. Defensive against absent payload, malformed JSON, non-dict deserialization. Matches the Mapbox Search Box API normalization shape (the same shape `_normalize_feature` returns in `mapbox_client.py`).

**Render — list view (`templates/locales/list.html`):** new muted small-text `<div>` under each non-legacy card title, gated on non-empty `display_addresses[locale]`. The route passes `display_addresses = {loc: _display_address(p) for loc, p in profiles.items()}` to template context.

**Render — edit view (`templates/locales/form.html`):** new muted small-text `<p>` under the H4 header, gated on non-empty `display_address`. Both `_edit_legacy_locale` and `_edit_shared_locale` pass `display_address=_display_address(profile)` to template context. Manual-entry rows without a `place_payload` render the empty placeholder div (which preserves the spacing — `<div class="mb-3"></div>`).

### 3.2 Item B 🔴 — fix §7 refresh for renamed locales

**`mapbox_client.py`** gains:

- `MAPBOX_RETRIEVE_URL` constant pointing at `https://api.mapbox.com/search/searchbox/v1/retrieve`.
- `_request_retrieve(mapbox_id, params)` — same 1-retry-on-5xx semantics as `_request()` for the forward endpoint, but with the id in the URL path instead of `q` parameter. Same `MapboxAPIError` / `MapboxTokenMissing` raising.
- `retrieve(mapbox_id, session_token=None) -> dict` — public surface. Passes optional `session_token` query param when supplied. Raises `MapboxNoResults` on empty `features` array (mapbox_id deleted/merged upstream). Reuses `_normalize_feature` so the return shape is identical to `search_places` / `search_nearby` (same field names: `mapbox_id`, `text`, `place_name`, `lng`, `lat`, `category`, `raw_payload`).

**`routes/locales.py:refresh_from_mapbox`** — Phase 1 rewritten:

- **Old:** `search_nearby(locale_name, lng, lat, limit=10)` (or `search_places` when coords absent) + `next((f for f in results if f['mapbox_id'] == stored_mapbox_id), None)` filter.
- **New:** `mapbox_client.retrieve(stored_mapbox_id, session_token=uuid.uuid4().hex)`. Single call, name-agnostic, queries Mapbox's live state for the exact feature.

Failure modes:
- `MapboxTokenMissing` — flash "Place lookup is not configured on the server." (unchanged).
- `MapboxNoResults` — flash "Mapbox no longer returns this exact place. Edit the locale to relink." + edit redirect (folds the two prior failure modes — the original "Mapbox no longer returns results for X" name-search failure is impossible now; the only `MapboxNoResults` path remaining is genuine "Mapbox-side deletion").
- Generic `MapboxError` — flash "Refresh failed: {e}." + list redirect (unchanged).

The Phase 2 (confirm-apply) path is untouched. `templates/locales/refresh_confirm.html` doesn't change — the contract is `refreshed.text`, `refreshed.raw_payload`, `new_chain_*`, `new_category` — all still produced by the rewritten Phase 1.

**Session token:** fresh `uuid.uuid4().hex` per refresh invocation. Mapbox treats it as a one-shot session and bills accordingly. No tracked-token table at N=1 — defer the `mapbox_session_tokens` table to a later session if billing visibility becomes needed.

Cleanup: the now-unused `stored_lng` / `stored_lat` reads in `refresh_from_mapbox` are dropped.

### 3.3 Item C — duplicate-mapbox_id detection

**Helper:** `_existing_locale_by_mapbox_id(db, uid, mapbox_id, exclude_slug=None)` — returns the existing `(locale, locale_name)` row pointing at the same mapbox_id for this user, or `None`. `exclude_slug` lets the upgrade path skip the row being upgraded (which doesn't have a `mapbox_id` set yet, but defensive).

**Three call sites:**

1. **`_save_mapbox_anchored` new-row INSERT path** — before slug generation, dup-check. If hit: flash "You already have a locale at this address ({existing_label}). Edit it instead." + redirect to `edit_profile(locale=dup['locale'])`. No new row inserted.

2. **`_save_mapbox_anchored` upgrade path** — between the existing-row lookup and the UPDATE. If hit (with `exclude_slug=upgrade_slug`): same warning + redirect. The manual_entry=TRUE row stays unchanged.

3. **`nearby_instances` POST handler** — filters `selected` features against the set of existing `mapbox_id` values for this user. Counts skipped. After the INSERT loop, if `skipped > 0`, flash "Skipped {n} already-saved location(s)." This handles the edge case where the athlete opts into 5 nearby instances, 2 of which they'd already saved.

### 3.4 Item D — delete with split rule

**Route:** `POST /locales/<locale>/delete` (new) → `delete_locale(locale)` in `routes/locales.py`.

**Logic:**

1. Reject legacy enum slugs (`home`/`hotel`/`partner`/`airport`) early with a warning flash + redirect to edit. Legacy slots auto-render on `/locales` independent of any row; deleting them would just bring them right back, so the route guards.
2. Look up the row by `(user_id, locale)`. 404 → "Unknown location." flash + list redirect.
3. Capture `category`, `gym_profile_id`, `locale_name` before deletion.
4. `DELETE FROM locale_profiles WHERE user_id = ? AND locale = ?` — FK CASCADE handles `locale_equipment` (PR1 composite FK), `locale_equipment_overrides` (PR11), `locale_toggle_overrides` (PR11) automatically.
5. **Split rule:** if `category IN ('home_gym', 'other_residence')` AND `gym_profile_id IS NOT NULL`, also `DELETE FROM gym_profiles WHERE id = ? AND created_by_user_id = ?`. The `created_by_user_id = uid` guard prevents nuking a shared profile that originated with another athlete (defensive — residential categories under the current taxonomy don't enter the shared-profile flow at all, but the guard hardens against future bugs).
6. Commit + flash "Deleted {display}." + list redirect.

**UI:**

- New `is_deletable` template var (`locale not in LOCALES`) passed by both `_edit_legacy_locale` and `_edit_shared_locale`.
- `templates/locales/form.html` adds a bottom Delete button — POST form with `onsubmit="return confirm('Delete this locale? Your equipment overrides for it will be removed too. This cannot be undone.');"`. Gated on `is_deletable` (legacy enum edit screens render no button).
- No delete affordance on `/locales` list — too easy to misclick. Edit screen only.

### 3.5 outdoor_park reclassification + label tweaks

**`SHARED_PROFILE_CATEGORIES`:** `frozenset` adds `'outdoor_park'`. Now 8 members: the 7 prior + outdoor_park. Privacy boundary becomes residence-vs-public; the only remaining private categories are `home_gym` + `other_residence`.

**`MANUAL_CATEGORIES`:** label swaps (enum values unchanged):

| Enum value | Old label | New label |
|---|---|---|
| `home_gym` | `Home gym` | `Home (primary residence)` |
| `other_residence` | `Other residence` | `Other residence (in-laws / friend / AirBnB)` |
| `outdoor_park` | `Outdoor / trail / park` | (unchanged) |

**Doc comment updates:** the `MANUAL_CATEGORIES` block comment now reads "eight shared-profile categories" and notes the residence-vs-public boundary. The `_is_shared_profile_locale` docstring no longer enumerates `outdoor_park` as a non-shared category — only `home_gym` + `other_residence`.

---

## 4. Files shipped this session

All on branch `claude/review-handoff-docs-SiQAY`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `mapbox_client.py` | Edit (+62 lines) | `MAPBOX_RETRIEVE_URL` constant; `_request_retrieve` helper; `retrieve(mapbox_id, session_token=None)` public function. |
| 2 | `routes/locales.py` | Edit (substantive multi-region) | `import uuid`; `MANUAL_CATEGORIES` label swaps; `SHARED_PROFILE_CATEGORIES` outdoor_park add; doc comment updates; `_display_address` + `_existing_locale_by_mapbox_id` helpers; `list_profiles` passes `display_addresses`; `_save_mapbox_anchored` dup-check on both INSERT + upgrade paths; `nearby_instances` dup-filter + skipped flash; `refresh_from_mapbox` Phase 1 rewrite to use `retrieve`; both edit-form render calls pass `display_address` + `is_deletable`; new `delete_locale` route. |
| 3 | `templates/locales/list.html` | Edit | Address caption `<div>` under each non-legacy card title, gated on `display_addresses[locale]`. |
| 4 | `templates/locales/form.html` | Edit | Header layout split — H4 + Back row, then optional address `<p>`; new bottom Delete button with browser `confirm()` gated on `is_deletable`. |
| 5 | `aidstation-sources/CLAUDE.md` | Edit | Last-shipped-narrative bumped to PR18 with full mechanical-scope summary; Layer 4 single-session demoted to predecessor; Backlog ref v33 → v34; Next-forward-move adds Item E retire + park-tags follow-ons. Layer 4 row in the layer-pipeline table unchanged (still "PROMPT BODIES 3/5"). |
| 6 | `aidstation-sources/Project_Backlog_v34.md` | New (v33 → v34) | v34 header revision entry: PR18 narrative. v33 entry moved to predecessor revisions list. Body (D-row table + categorization rules + status legend + open items + going-forward rule + closed sessions list + process notes) byte-identical to v33 per Rule #12. |
| 7 | `aidstation-sources/PR_Verification_Status.md` | Edit | New PR18 section with 12 testable §5.0 steps (all 🟡 owed for the post-merge walk); Aggregate status table refreshed (PR18 row added; totals 52 ✅ / 21 ⏸ / 26 🟡 / 4 ⚪ of 103); Headlines section rewritten — pre-PR18 14 doable-now + 12 new PR18 §5.0 steps = 26 doable-now post-deploy. |
| 8 | `aidstation-sources/handoffs/V5_Implementation_PR18_Locale_CRUD_Bundle_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**5-file ceiling status:** 4 substantive code files (well under the ceiling); the 4 bookkeeping files are mandatory per Rules #11/#12/#13 + per-implementation-PR cadence (CLAUDE.md bump, backlog version, PR_Verification_Status section, closing handoff). Net 8 files — consistent with prior implementation PRs (PR11, PR15, PR17 each shipped 6–7 files).

**Not touched this session** (intentional):

- `routes/coaching.py` — Item E (retire legacy `LOCALES`) is a separate PR per the predecessor handoff §3.5. The hardcoded `LOCALES = ['home','hotel','partner','airport']` at line 22 is a v1-coaching-form dependency.
- `routes/references.py` — same; imports `LOCALES` at line 5.
- `templates/references/exercises.html` — cosmetic badge color logic at line 56 keyed to the 4 enum values; same Item E PR.
- `templates/locales/refresh_confirm.html` — Phase 2 (confirm-apply) is untouched; the rewritten Phase 1 still produces the same `refreshed` dict shape.
- `templates/locales/new.html` — search box + manual entry form; no UX changes needed for items A/B/C/D.
- `templates/locales/nearby.html` — the nearby picker UI doesn't need to change; only the POST handler's dup-filter behavior shifts.
- `init_db.py` — no schema changes. The `gym_profiles.created_by_user_id` column is already present; FK CASCADE on the override tables is already in place from PR2/PR11. No migration needed.
- `Layer4_Spec.md` / prompts — Layer 4 design arc is independent; PR18 is implementation-track.

---

## 5. Standing items / open flags

### 5.1 Item E — retire legacy `LOCALES` enum cards (its own PR)

**Scope** per the predecessor handoff §3.5 audit:

- `routes/coaching.py:22` — `LOCALES = ['home','hotel','partner','airport']` literal; v1 coaching form dropdown + invalid-locale fallback. Hard consumer. The coaching-form replacement is also the v1-coaching-v2-LLM-pipeline replacement track per CLAUDE.md "Selective rebuild," so this PR's coaching edits should be tight.
- `routes/references.py:5` — `from routes.locales import LOCALES`; powers the exercise-references multi-select locale filter. Less brittle; replace with a query against the athlete's actual locales (legacy + athlete-created).
- `templates/references/exercises.html:56` — cosmetic badge color logic keyed to the 4 enum values. Cosmetic only.

**The refactor:** switch coaching + references to query the athlete's actual locales instead of the hardcoded list. Coaching default-fallback decision pending: (a) athlete's `preferred=TRUE` locale per D-61, (b) most-recently-updated locale, or (c) form-level guard "you need at least one locale." Andy's call when the PR session opens.

**Scope estimate:** `routes/coaching.py` substantive edit (~30 lines), `routes/references.py` smaller (~10 lines), `templates/references/exercises.html` badge logic update, possibly `routes/locales.py` to drop the `LOCALES` literal export. ~4 files, well under ceiling.

**Why separate:** legacy-enum retire bundled with the locale-CRUD fixes would mix two different concerns. Better to ship CRUD first (this PR), then a focused "v1 coaching coupling cleanup" PR.

### 5.2 Park-specific tag taxonomy (deferred until usage exercises the seam)

`EQUIPMENT_CATEGORIES` is gym-centric (barbell, dumbbells, racks, machines). With outdoor_park now in `SHARED_PROFILE_CATEGORIES`, the inherit/override form renders the gym equipment list for parks — athletes leave most boxes unchecked; the "shared profile" effectively becomes just "this park exists, anchored here." The substantive content the park needs (water fountain, restroom, shelter, parking, trailhead signage, fixed pull-up bars) doesn't exist in the taxonomy.

**Defer rationale:** Andy is N=1; parks aren't load-bearing yet. When park usage actually exercises the seam — multiple parks saved with overlapping equipment, athletes wanting to distinguish "park with pull-up bars" from "park without" — that's the trigger to introduce a category-aware tag taxonomy or new `OUTDOOR_TAGS` literal.

**Pre-work suggestion when the time comes:** the cleanest split is probably (a) keep `EQUIPMENT_CATEGORIES` as gym/strength-focused (it's used by every other locale category appropriately), and (b) introduce a parallel `OUTDOOR_TAGS = [...]` consumed only when `category == 'outdoor_park'`. The edit form would branch the rendered checkbox set on category. No schema change needed if outdoor tags live in the same `locale_equipment` table + `equipment_items` registry (just new tag rows).

### 5.3 Session-token UUID generation for `/retrieve` — defer billing visibility

Current implementation: `uuid.uuid4().hex` generated per refresh call. Mapbox bills the call against that one-shot session. Per the predecessor handoff §3.2 "Mechanics" rationale, this is fine at N=1; the `mapbox_session_tokens` table option is a defer.

When the time comes (multi-athlete production, billing-by-athlete needed): a `mapbox_session_tokens(user_id, session_token, created_at, expires_at)` table with one row per athlete per day would let the orchestrator reuse a session token across multiple refresh calls in a window (Mapbox session tokens are usable for up to 60 minutes per session boundary — see Mapbox Search Box billing docs).

### 5.4 PR11 step 6 unblock — re-walkable after PR18 deploy

PR11 §5.0 step 6 (§7 refresh change-path confirm template) was marked "🟡 blocked on B" in the PR11 walk. PR18's Item B fix is exactly what unblocks it. After PR18 deploys:

1. Walk PR11 step 6 against a renamed locale (the prior failure mode).
2. Flip PR11 step 6 from 🟡 → ✅ in `PR_Verification_Status.md`.

This is a free PR11-walk win once PR18 lands.

### 5.5 Cascade verification — confirm in production

PR2 + PR11 established the composite FK CASCADE relationships on `locale_equipment` + `locale_equipment_overrides` + `locale_toggle_overrides`. The delete route relies on these cascades. Post-deploy verification:

1. Create an athlete-created shared-profile locale (e.g., a commercial gym).
2. Build the equipment profile (writes `gym_profiles` row + `locale_profiles.gym_profile_id` link).
3. Switch the gym profile to inherit mode + add some `locale_equipment_overrides`.
4. Add some `locale_toggle_overrides` if there's UI for that, else inject via psql.
5. Delete the locale.
6. Verify in psql: zero rows in `locale_equipment` / `locale_equipment_overrides` / `locale_toggle_overrides` for that `(user_id, locale)`; `gym_profiles` row for that mapbox_id **still present** (chain category, shared data preserved).
7. Repeat with a `home_gym` locale + force-linked `gym_profiles` row: confirm both go.

This is PR18 §5.0 steps 8 + 9 in `PR_Verification_Status.md`.

---

## 6. Forward pointers

**Next session:** Andy's choice. The PR18 walk happens after Vercel deploy (Andy-driven, not in-session). Candidates for the next coding session:

- **Layer 4 prompt-body design — per-tier T1/T2 (D-64; Pattern B refresh)** — 4 of 5 in the prompt-body arc; stop-and-ask trigger #2. May split T1 + T2 across two sessions if scope is too large.
- **Layer 4 prompt-body design — race-week-brief** — 5 of 5; stop-and-ask trigger #2.
- **Layer 4 §14 retrospective** — fresh-eyes critical pass over `Layer4_Spec.md` §§1–13 including the §3.5/§4.4/§10.4/§13.4 amendments shipped this same date.
- **Layer 4 implementation track** — D-63 LLM-call layer can now land against `Layer4_SingleSession_v1.md`; deterministic-validator harness + payload schema scaffolding can start independently.
- **Item E PR — retire legacy `LOCALES`** — per §5.1 above; ~4 files; needs Andy's call on coaching-form default-fallback (D-61 preferred locale vs. most-recently-updated vs. form-level guard).
- **D-50 wiring resumption** — COROS OAuth + webhook recording.

**Before the PR18 walk:**

1. **Read `aidstation-sources/CLAUDE.md` fully** (Rule #13). The last-shipped narrative now leads with PR18; Backlog ref now points at v34.
2. Read this handoff in full.
3. Read `PR_Verification_Status.md` PR18 section for the 12 §5.0 steps.
4. (Optional) Re-read the predecessor handoff `V5_Implementation_PR11_Verification_Followon_Handoff_v1.md` §3.2 for the Item B mechanics — confirms the rewrite is faithful to the option-2 retrieve-based approach Andy picked.

**Rules in force, unchanged:**

- #9 session-start verification — `routes/locales.py` `MANUAL_CATEGORIES` now at 10 entries with two new labels; `SHARED_PROFILE_CATEGORIES` at 8 entries (+ outdoor_park); `mapbox_client.py` has `retrieve` defined; `templates/locales/list.html` + `form.html` render `display_address(es)`; `delete_locale` route exists.
- #10 session-end verification — applied; see §7 below.
- #11 mechanically-applicable deferred edits — Item E PR scope spec'd in §5.1; park-tags taxonomy direction spec'd in §5.2.
- #12 numeric version suffixes — Backlog now at v34; next state-changing event bumps v34 → v35.
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §6 first-action explicitly names CLAUDE.md.

---

## 7. Session-end verification (Rule #10)

Final pass over each claimed file edit before composing this handoff:

| Check | Result |
|---|---|
| `mapbox_client.py` has `retrieve` function with signature `(mapbox_id, session_token=None)` | ✅ `grep "def retrieve" mapbox_client.py` |
| `mapbox_client.py` has `MAPBOX_RETRIEVE_URL` constant | ✅ |
| `mapbox_client.py` has `_request_retrieve` helper | ✅ |
| `routes/locales.py` imports `uuid` | ✅ |
| `routes/locales.py` `MANUAL_CATEGORIES['home_gym']` label = `'Home (primary residence)'` | ✅ AST verified |
| `routes/locales.py` `MANUAL_CATEGORIES['other_residence']` label = `'Other residence (in-laws / friend / AirBnB)'` | ✅ AST verified |
| `routes/locales.py` `SHARED_PROFILE_CATEGORIES` contains `'outdoor_park'` (8 total) | ✅ AST verified |
| `routes/locales.py` defines `_display_address` | ✅ AST verified |
| `routes/locales.py` defines `_existing_locale_by_mapbox_id` | ✅ AST verified |
| `routes/locales.py` defines `delete_locale` route at `POST /locales/<locale>/delete` | ✅ AST verified + bp.route inspection |
| `routes/locales.py` `_save_mapbox_anchored` has dup-check on both INSERT + upgrade paths | ✅ read |
| `routes/locales.py` `nearby_instances` filters selections against existing mapbox_ids | ✅ read |
| `routes/locales.py` `refresh_from_mapbox` Phase 1 calls `retrieve()` (not `search_nearby`/`search_places`) | ✅ read |
| `routes/locales.py` `list_profiles` passes `display_addresses` to template | ✅ read |
| `routes/locales.py` both edit-form render calls pass `display_address` + `is_deletable` | ✅ read |
| `templates/locales/list.html` renders address caption from `display_addresses[locale]` | ✅ read |
| `templates/locales/form.html` renders address caption from `display_address` | ✅ read |
| `templates/locales/form.html` has Delete button with `onsubmit="return confirm(...)"` gated on `is_deletable` | ✅ read |
| `Project_Backlog_v34.md` exists; line 5 starts with `**File revision:** v34 — 2026-05-16 (**PR18 — locale-CRUD bundle shipped` | ✅ `head -5` |
| `Project_Backlog_v34.md` line 6 = `**Predecessor revisions:**`; line 7 starts with `- v33 — 2026-05-16 (**Layer 4 single-session synthesizer` (demoted from v33's file-revision slot) | ✅ |
| `aidstation-sources/CLAUDE.md` last-shipped narrative begins with `PR18 — locale-CRUD bundle` | ✅ |
| `aidstation-sources/CLAUDE.md` Backlog reference is `Project_Backlog_v34.md` | ✅ |
| `aidstation-sources/CLAUDE.md` Next-forward-move adds Item E + park-tags candidates | ✅ |
| `PR_Verification_Status.md` has a new `## PR18 — locale-CRUD bundle (PR11 follow-on; pending merge)` section with 12 step rows | ✅ |
| `PR_Verification_Status.md` aggregate table row for PR18 = `0 / 0 / 12 / 0 / 12`; totals = `52 / 21 / 26 / 4 / 103` | ✅ |
| `PR_Verification_Status.md` headlines section reflects post-PR18 ship state (26 doable-now) | ✅ |
| Python AST parse of `routes/locales.py` + `mapbox_client.py` clean | ✅ `python -c "import ast; ast.parse(...)"` |
| Working tree shows the expected files modified + 2 new (backlog v34 + handoff) | (verified pre-commit) |

---

## 8. Carry-forward from PR11 + adjacent tracks (informational)

- PR11 step 6 — currently 🟡 blocked on Item B; unblocks once PR18 deploys (§5.4 above).
- PR11 step 12 (PR10 token-missing equivalent) — still 🟡 skipped; no change.
- PR11 step 13 — ⚪ N/A at N=1; no change.
- Layer 4 single-session prompt body shipped this same date in a parallel session; independent track; CLAUDE.md last-shipped reflects PR18 as the most recent shipped session, with Layer 4 single-session demoted to predecessor.

---

**End of handoff.** PR18 ships items A/B/C/D + outdoor_park reclass + label tweaks per the PR11-follow-on handoff §3 + §4 mechanical scope. 4 substantive code files + 4 bookkeeping; 5-file ceiling not breached on substantive code. Item E retire + park-tags taxonomy stay tracked as own-PR / deferred follow-ups. PR_Verification_Status now reads 52 ✅ / 21 ⏸ / 26 🟡 / 4 ⚪ of 103 post-PR18-ship.
