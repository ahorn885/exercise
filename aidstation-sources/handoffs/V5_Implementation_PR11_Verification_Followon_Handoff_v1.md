# V5 Onboarding Implementation PR11 Verification + Follow-on Planning — Handoff

**Session:** Post-PR11-merge verification walk + locale-CRUD follow-on planning. Not a code-shipping session — only tracker bookkeeping landed (PRs #53 + #55, both merged). The deliverable is decision capture so the next session can ship the bundle PR without re-deriving from chat.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Implementation_PR11_Closing_Handoff_v1.md` (closed D3b — D-60 inherit/override UI + D-59 §6 upgrade + §7 refresh + PR2 FK fix).
**Branch:** `claude/pr11-walk-pr12-planning-handoff` (this handoff's branch; this file is the only change).
**Status:** 🟢 PR11 §5.0 walked end-to-end (10/14 ✅); 5 follow-on items captured; next bundle PR scoped and ready for a fresh session.
**Adjacent work:** Layer 4 spec v1 + 2/5 prompt bodies shipped in parallel threads (PRs #56–60). Independent of the locale-CRUD track — neither blocks the other. SQLite retirement (PR13) stripped the `database._is_postgres()` gating PR11 had inserted; current `routes/locales.py` runs the D-60 helpers unconditionally, which is correct under the PG-only architecture.

---

## 1. What this session did

1. **Wrote a runbook** for the 13 owed PR11 §5.0 verification steps (slug-lookup, psql one-liners, expected outputs per step).
2. **Andy walked the steps** against the deployed app + Neon. 10/14 ✅, 3 🟡 (1 blocked on an item we surfaced; 2 skipped as low-priority), 1 ⚪ N/A.
3. **Captured 5 follow-on items** (A–E) surfaced during the walk; for each, classified as bug vs. UX gap vs. design question + chose direction.
4. **Audited consumers of legacy `LOCALES`** before agreeing to retire them — found hard coupling to `routes/coaching.py` + `routes/references.py` that requires a separate refactor.
5. **Reclassified `outdoor_park`** from "no shared profile" to "has shared profile" in `SHARED_PROFILE_CATEGORIES` — clarifies the privacy boundary as residence-vs-public rather than gym-vs-non-gym.
6. **Updated PR_Verification_Status.md** via PR #53 (step 1) + PR #55 (steps 2–5, 9–12, 14); aggregate now reads **52 ✅ / 21 ⏸ / 14 🟡 / 4 ⚪** of 91.

---

## 2. PR11 walk results (Rule #10 anchoring)

Full per-step state lives in `PR_Verification_Status.md`. Headline:

| Step | What it verified | Result |
|---|---|---|
| 1 | FK fix shape (`locale TEXT NOT NULL` + composite FK to `locale_profiles(user_id, locale) ON DELETE CASCADE`) | ✅ |
| 2 | D-60 first-athlete: `gym_profiles` INSERT + `gym_profile_id` link | ✅ |
| 3 | D-60 inherit + overrides: `locale_equipment_overrides` writes; `last_confirmed_*` + `contribution_count` bumped | ✅ |
| 4 | §6 manual→Mapbox upgrade: `manual_entry` flips false; slug preserved | ✅ (with bugs surfaced) |
| 5 | §7 refresh — no-change path: silent payload bump | ✅ |
| 6 | §7 refresh — change path: confirm template + Yes applies | 🟡 blocked on item B |
| 7 | §7 refresh — token-missing path | 🟡 skipped (PR10 step 12 equivalent already skipped) |
| 8 | §7 refresh — stale mapbox_id path | 🟡 skipped (low-priority edge) |
| 9 | `MANUAL_CATEGORIES` shows 10 D-60 §3 entries | ✅ |
| 10 | Regression — legacy enum edit forms unchanged | ✅ |
| 11 | Regression — no-shared-profile athlete-created categories take legacy flow | ✅ |
| 12 | Regression sweep on /profile, /onboarding/connect, etc. | ✅ |
| 13 | Cross-user scoping | ⚪ N/A at N=1 |
| 14 | PR2 FK silent-failure pattern closed end-to-end | ✅ (implicit in step 1 + 3) |

**Findings during the walk:**

- Step 2 surfaced **A** (address invisible): athlete has three Anytime Fitness rows that look identical because Mapbox's `properties.full_address` is stored in `place_payload` JSON but no template extracts it.
- Step 4 surfaced **B** (refresh broken for renamed locales), **C** (no duplicate detection), **D** (no delete UI), **E** (legacy enums should retire).
- Step 9 surfaced label UX feedback ("Home gym" / "Other residence" wording).

---

## 3. Follow-on bundle (PR18 candidate) — decisions

Five items surfaced; four bundle into the next locale-CRUD PR; one becomes its own PR.

### 3.1 Item A — surface address on `/locales` + edit views

**What:** athletes can't distinguish two Mapbox-anchored rows with the same `locale_name` because the full address is hidden inside `place_payload` JSON.

**Decision:** extract `properties.full_address` from `place_payload` at render time; show it under the locale name on `/locales` cards + as a small caption on the edit form header.

**Mechanics:** one new helper in `routes/locales.py` (e.g. `_display_address(profile_row)` that JSON-parses `place_payload` and returns the `properties.full_address` string, falling back to `properties.place_formatted` then empty). Used by `list.html` per-card render + `form.html` header. Falls through cleanly when `place_payload` is absent or malformed.

### 3.2 Item B — fix §7 refresh for renamed locales (🔴 real bug)

**What:** `refresh_from_mapbox` uses `profile['locale_name']` as the Mapbox search query. Athletes rename locales freely ("Horn's House" instead of "123 Main St"), so the search returns no matches and the refresh fails with "Mapbox no longer returns results."

**Decision (Andy's pick — option 2 of two):** use Mapbox Search Box `/retrieve` endpoint directly with the stored `mapbox_id`. No name search; eliminates the rename failure mode entirely.

**Mechanics:**

1. Add `mapbox_client.retrieve(mapbox_id, session_token=None)` calling `GET /search/searchbox/v1/retrieve/{mapbox_id}`. Returns the same normalized feature shape (`mapbox_id`, `text`, `place_name`, `lng`, `lat`, `category`, `raw_payload`). Same typed exception hierarchy.
2. Session token plumbing: Search Box `/retrieve` accepts an optional `session_token` to bill the call against the prior suggest/forward session. Since our refresh isn't tied to a prior suggest call, generate a fresh UUID per refresh (one-shot session). Send as `session_token=<uuid>` query param.
3. Rewrite `refresh_from_mapbox` Phase 1: replace `search_nearby(locale_name, lng, lat)` + match-by-id with a single `retrieve(stored_mapbox_id)` call. If the call raises `MapboxNoResults` (id no longer exists), keep the existing "Mapbox no longer returns this exact place" warning flash + edit-screen redirect. Otherwise compute `refreshed` directly from the returned feature — no list filtering needed.
4. Phase 2 (confirm-apply) unchanged.

**Why not option 1 (parse place_payload for original Mapbox text):** would work for 95% of cases but doesn't handle "Mapbox renamed/recategorized the place since first lookup" — and that's exactly what §7 refresh is supposed to catch. Option 2 always queries Mapbox's live state.

### 3.3 Item C — duplicate-mapbox_id detection

**What:** athletes can create multiple `locale_profiles` rows pointing at the same `mapbox_id` (e.g. searching for the same place twice). The D-60 inherit machinery handles it gracefully (both link to the same `gym_profile`), but the UX is confusing.

**Decision (Andy's pick):** block at create-time. If user already has a row with the same `mapbox_id`, redirect to edit the existing one instead of inserting a duplicate.

**Mechanics:**

1. In `_save_mapbox_anchored`, after extracting form fields and before `INSERT`, run `SELECT locale FROM locale_profiles WHERE user_id = ? AND mapbox_id = ?`. If a row exists, flash "You already have a locale at this address. Edit it instead." + redirect to `/locales/<existing-slug>/edit`. Apply equally to the new-create and upgrade-slug paths (upgrade should be allowed to fill a mapbox_id even when another row has a different one).
2. In `nearby_instances` POST handler, filter `selected` against an existing-`mapbox_id` SELECT for this user — skip with a per-row info note. Athletes opting into 5 nearby instances where 2 are duplicates get 3 new rows + a flash like "Skipped 2 already-saved locations."
3. The `locale_profiles` table doesn't currently have a UNIQUE on `(user_id, mapbox_id)`. Could add one as a defense-in-depth ALTER, but the application-level check is sufficient at N=1; defer the migration to a quieter PR.

### 3.4 Item D — delete with split rule

**What:** no UI to delete a locale. The handoff §6 of PR11 flagged this as deferred; bringing forward.

**Decision (Andy's framing):** delete the row from the athlete's view always; for residential categories (`home_gym`, `other_residence`), also delete the `gym_profiles` row if one happens to be linked (privacy — residences shouldn't be in the enterprise DB). For chain / shared categories, leave the `gym_profiles` row intact (enterprise data preserved for other athletes).

**Mechanics:**

1. New route `POST /locales/<locale>/delete` in `routes/locales.py`:
   - Look up the row by `(user_id, locale)`. 404 if not found.
   - Capture `gym_profile_id` + `category` before deletion.
   - `DELETE FROM locale_profiles WHERE user_id = ? AND locale = ?` — FK CASCADE handles `locale_equipment` (PR1) + `locale_equipment_overrides` + `locale_toggle_overrides` (PR11) automatically.
   - If `category IN ('home_gym', 'other_residence')` AND `gym_profile_id IS NOT NULL`: `DELETE FROM gym_profiles WHERE id = ? AND created_by_user_id = ?` (created_by guard so we don't nuke a profile created by someone else even if the athlete's row pointed at it). This is defensive — in the current data model, residential categories shouldn't have a `gym_profile_id` set at all.
   - Flash + redirect to `/locales`.
2. UI:
   - **Delete button on the edit form** with a CSRF-protected POST form. Either inline next to Save (red `btn-outline-danger`) or below in a "Danger zone" section. Browser confirm via `onclick="return confirm('...')"` or a hidden second-page confirmation form. I'd default to browser confirm — simpler, matches the lo-fi UX everywhere else.
   - **No delete button on the list view** for now — too easy to misclick. Edit screen only.
3. Cascade verification: confirm via psql post-deploy that the FK cascade on `locale_equipment_overrides` + `locale_toggle_overrides` (PR11) + `locale_equipment` (PR1 — also has the composite FK to `(user_id, locale)`) actually runs on delete. Walk by creating an athlete-created locale, building equipment, then deleting; expect zero leftover rows in any of the dependent tables for that `(user_id, locale)` pair.

### 3.5 Item E — retire legacy enums (separate PR)

**What:** `home/hotel/partner/airport` enum cards always render on `/locales` even when athletes have zero rows for them. Andy wants them gone in favor of athlete-created locales only.

**Decision:** separate PR, not bundled with A–D. Audit found two hard consumers that block a quick removal:

1. **`routes/coaching.py`** has its own `LOCALES = ['home', 'hotel', 'partner', 'airport']` literal (line 22). The coaching form (v1 feature) takes a locale field, validates against this hardcoded list (`if locale not in LOCALES: locale = 'home'`), and passes the list as the dropdown choice to the template. **Hard dependency.**
2. **`routes/references.py`** imports `LOCALES` from `routes/locales` (line 5). Powers the exercise-references page's multi-select locale filter. Less brittle but still a consumer.
3. **`templates/references/exercises.html:56`** has cosmetic badge color logic keyed to the 4 enum values. Cosmetic only.

**The refactor:** switch coaching + references to query the athlete's actual locales (legacy + athlete-created) instead of the hardcoded list. Coaching default-fallback (`'home'` when invalid) needs replacement — probably default to the athlete's `preferred=TRUE` locale per D-61, or the most-recently-updated, or empty + form-level "you need at least one locale" guard.

**Why separate PR:** the coaching form is the v1 coaching feature being progressively replaced by the v2 LLM pipeline (per CLAUDE.md "Selective rebuild" section). Doing the legacy-enum retire alongside the locale-CRUD bundle would mix two different concerns. Better to ship CRUD fixes first, then do a focused "v1 coaching coupling cleanup" PR.

**Scope estimate for the E PR:** `routes/coaching.py` substantive edit (~30 lines), `routes/references.py` smaller edit (~10 lines), `templates/references/exercises.html` color-logic update, possibly `routes/locales.py` to drop the `LOCALES` literal export. ~4 files, well under ceiling.

### 3.6 Outdoor_park reclassification + label tweaks

**What:** in D-60 §3 the "no shared profile" bucket conflated two reasons — privacy (residences) and "equipment doesn't apply" (parks). Parks with verifiable Mapbox addresses are publicly shareable; the privacy concern is residence-only.

**Decision (Andy's pick):** move `outdoor_park` to `SHARED_PROFILE_CATEGORIES`. The privacy boundary becomes residence-vs-public, cleanly.

**Updated category split:**

| Bucket | Members |
|---|---|
| **`SHARED_PROFILE_CATEGORIES`** (8) — verifiable public addresses, enterprise shareable | commercial_chain_gym, independent_gym, hotel_gym, climbing_gym_chain, climbing_gym_indie, pool_indoor, pool_outdoor, **outdoor_park** |
| **Private** (2) — residential, never enterprise-shareable | home_gym, other_residence |

**Label tweaks** (`MANUAL_CATEGORIES` display strings; enum values stay):

| Enum value | New label |
|---|---|
| `home_gym` | **Home (primary residence)** |
| `other_residence` | **Other residence (in-laws / friend / AirBnB)** |
| `outdoor_park` | (unchanged: "Outdoor / trail / park") |

**Known limitation flagged:** the existing `EQUIPMENT_CATEGORIES` list is gym-centric (barbell, dumbbells, racks, etc.). When athletes inherit/build a shared profile for a park, the form renders gym equipment checkboxes that mostly don't apply. Athletes will leave most unchecked; shared profile is effectively just "this park exists, anchored here." **Park-specific tags (water fountain, restroom, shelter, parking, trailhead signage) are a known follow-up** — out of scope for the CRUD bundle PR; capture in next handoff §6 as a tracked item.

**Mechanics for the bundle PR:** one-line change to `SHARED_PROFILE_CATEGORIES` in `routes/locales.py` (add `'outdoor_park'`); two string swaps in `MANUAL_CATEGORIES`. Plus a one-line addition to PR18 closing handoff §6 about the park-tags follow-up.

---

## 4. PR18 (next locale-CRUD bundle) — mechanically-applicable scope

A fresh session executing the bundle:

**Files (estimate ~4–5 substantive):**

1. `mapbox_client.py` — add `retrieve(mapbox_id, session_token=None)` function (item B). ~30 lines.
2. `routes/locales.py` — `_display_address` helper (A); `_save_mapbox_anchored` + `nearby_instances` duplicate-check (C); new `delete_locale` route (D); `SHARED_PROFILE_CATEGORIES` outdoor_park addition + `MANUAL_CATEGORIES` label swaps; rewrite `refresh_from_mapbox` to use `retrieve()` instead of `search_nearby`+match-by-id (B).
3. `templates/locales/list.html` — render `_display_address` under each card's locale name.
4. `templates/locales/form.html` — render `_display_address` as caption on header; add "Delete" button bottom (with browser-confirm); show "primary residence" / "in-laws / friend / AirBnB" labels through normal `MANUAL_CATEGORIES` flow.
5. Maybe `templates/locales/delete_confirm.html` if Andy prefers a confirmation page over browser-confirm — small (~25 lines, peer to `refresh_confirm.html`).

**Backlog bump:** v32 → v33. D-50 row gets PR18 narrative entry; D-59 + D-60 rows already 🟢 fully shipped per PR11, no change. New status note for the park-tags follow-up (D-NN row, or D-60 row addendum).

**Walk-through:** standard §5.0 checklist — exercise A (address visible across 3+ locales), B (refresh a renamed locale, expect it to work now), C (try to create a second locale with the same Mapbox feature, expect redirect-to-edit), D (delete a chain locale, confirm `gym_profiles` row stays; delete a home_gym locale, confirm both rows go), outdoor_park (build shared profile for a park, expect inherit/override UI to render even though equipment list looks weird), labels (verify "Home (primary residence)" + "Other residence (in-laws / friend / AirBnB)" copy renders).

**Stop-and-ask candidates the PR18 session may hit:**

- **Session-token UUID generation for `/retrieve`** — Python `uuid.uuid4()` is fine; if Andy prefers a tracked session token (one per athlete per day for billing visibility), capture in a `mapbox_session_tokens` table. Premature at N=1; default to fresh UUID per call.
- **Delete confirmation UX** — browser `confirm()` vs. dedicated confirmation page. I'd default to browser-confirm for the lo-fi consistency; if Andy wants the safer two-page flow, that's an extra template.
- **Cascade verification scope** — the FK CASCADE on `locale_equipment_overrides` (PR11) + `locale_toggle_overrides` (PR11) is guaranteed by the schema. `locale_equipment` (PR1) has a composite FK too. But `gym_profiles` doesn't cascade — that's intentional (enterprise data preservation). The delete route's manual `DELETE FROM gym_profiles WHERE … AND created_by_user_id = ?` guard is sufficient.

---

## 5. Standing items / open flags

- **Park-specific tags follow-up** — `EQUIPMENT_CATEGORIES` is gym-centric. Outdoor_park shared profiles render the gym list. Athletes leave most unchecked. Real fix: category-aware tag taxonomy (or new `OUTDOOR_TAGS` literal). Capture in PR18 closing handoff §6 once shipped.
- **Item B's option-1 fallback** — if `/retrieve` returns no results, the current "edit to relink" warning still fires. Reasonable; Mapbox-side place deletions are rare.
- **Coaching/references refactor scope** (Item E PR) — when it lands, decide whether to also collapse the `LOCALES = ['home', 'hotel', 'partner', 'airport']` literal in `routes/locales.py` (still used for `is_legacy` branch detection on the edit form). Simplest: keep the literal as a "legacy migration helper" — athletes with `home/hotel/partner/airport` slugs still get the legacy `locale_equipment` flow; new athletes never see those slugs because the auto-display is gone. Athletes can rename their legacy rows to whatever they want; the slug doesn't auto-rename, but that's purely cosmetic.
- **D-61 JIT swap session-card UI** still pending Layer 4 spec landing — out of scope here, on the Layer 4 implementation track.
- **D-60 deferred items** (dispute, submit-as-correction, sharing opt-out, sharing-consent disclosure, §J.3 gear toggle UI) — all still deferred per PR11 §6 "premature at N=1." No change.
- **Legacy enum retire (Item E)** — its own PR. Spec'd in §3.5 above; scope-bounded.

---

## 6. Forward pointers

- **Next session:** ship the PR18 bundle per §4. Estimated 4–5 substantive files.
- **Before that session:** confirm with Andy whether delete UX = browser-confirm or dedicated confirm template (one-line scope question).
- **First action of the PR18 session:** Read `aidstation-sources/CLAUDE.md` fully (Rule #13). Then Rule #9 reconciliation against this handoff: confirm `PR_Verification_Status.md` PR11 section shows 10 ✅ / 3 🟡 / 1 ⚪; confirm `routes/locales.py` still has `MANUAL_CATEGORIES` at 10 entries + `SHARED_PROFILE_CATEGORIES` at 7 entries (this PR's bundle adds outdoor_park to make 8); confirm `mapbox_client.py` exists with `search_places` + `search_nearby` + `MapboxError` hierarchy (this PR's bundle adds `retrieve`); confirm `templates/locales/refresh_confirm.html` exists.

**Rules in force, unchanged:**

- #9 session-start verification — this handoff IS the verification anchor for the bundle PR's start
- #10 session-end verification — pure-bookkeeping session, no code claims to verify
- #11 mechanically-applicable deferred edits — §3 + §4 above ARE the bundle's mechanical spec
- #12 numeric version suffixes — backlog now at v32; next bump goes v32 → v33 only if PR18 ships a state-changing event
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §6 first-action explicitly names CLAUDE.md

---

*End of PR11 verification + follow-on planning handoff. PR11 §5.0 walked end-to-end (10 ✅ / 3 🟡 / 1 ⚪ of 14); 5 items surfaced (A address-invisible, B refresh-broken-on-rename 🔴, C no-duplicate-check, D no-delete, E retire-legacy-enums) — A/B/C/D bundle into the next locale-CRUD PR per §3.1–§3.4 and §3.6; E is its own PR per §3.5 because of `routes/coaching.py` + `routes/references.py` consumers. Outdoor_park reclassified into `SHARED_PROFILE_CATEGORIES` (8 total now) — privacy boundary becomes residence-vs-public; label tweaks on `home_gym` + `other_residence`. Park-specific tag taxonomy flagged as follow-up. Layer 4 design arc proceeded in parallel (PRs #56–60); independent track, no interaction. Tracker now at 52 ✅ / 21 ⏸ / 14 🟡 / 4 ⚪ of 91. Next: PR18 bundle (A+B+C+D + labels + outdoor_park) per §4 mechanical scope.*
