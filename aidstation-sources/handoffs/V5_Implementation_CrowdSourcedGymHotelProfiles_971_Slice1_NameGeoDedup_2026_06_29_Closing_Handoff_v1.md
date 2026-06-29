# Crowd-Sourced Gym/Hotel Profiles (#971) — Slice 1: Name+Geo Dedup — Closing Handoff

**Session:** First slice of #971 (crowd-sourced hotel/gym equipment profiles) — activate the dormant `gym_profiles.address_fingerprint` column so crowd-source dedup no longer depends on an exact `mapbox_id` match.
**Date:** 2026-06-29
**Predecessor handoff:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice4_3_RedumpRetire_EquipmentStrip_2026_06_29_Closing_Handoff_v1.md` (a different thread — #884; this session is a fresh start on #971 at Andy's direction).
**Branch:** `claude/issue-971-hmi0ro`
**Status:** 2 substantive files (`routes/locales.py` + `tests/test_locales.py`) — under the 5-file ceiling. PR [#1009](https://github.com/ahorn885/exercise/pull/1009). CI green.

---

## 1. Session-start verification (Rule #9)

This session is a fresh start on a new thread (#971), not a continuation of the #884 predecessor, so §1 anchor-checks the **on-disk preconditions this slice depends on** rather than the predecessor's §8.

| Claim | Anchor | Result |
|---|---|---|
| `gym_profiles.address_fingerprint` column + index exist | `grep -n address_fingerprint init_db.py` → col `init_db.py:1235`, index `:1249` | ✅ |
| `address_fingerprint` was never populated or read pre-session | `grep -rn address_fingerprint *.py routes/` → only `init_db.py` (DDL) | ✅ dormant |
| Dedup was `mapbox_id`-only | `_find_gym_profile` (`routes/locales.py`) keys on `mapbox_id` only | ✅ |
| `gym_profiles` has no lat/lng (coords live on `locale_profiles`) | `grep -n` the CREATE TABLE block (`init_db.py:1232`) | ✅ (drove the no-SQL-backfill decision, §7) |

**Reconciliation note:** clean — the schema hooks the issue's spec calls for (`address_fingerprint` + its partial index) were already present from the D-60 locations-consolidation work; this slice is the first code to use them.

---

## 2. Session narrative

**Scope-pick gate.** #971 is a 3-part feature on top of the existing `gym_profiles` crowd-source backbone (keyed on `mapbox_id`; cold-start-after-first-athlete; peer inherit/suggest; `private` opt-out — all already live from the locations funnel): (1) **name+geo dedup**, (2) **photos**, (3) **admin review** of user-submitted updates. The issue itself flags it as the hotel/gym analog of the crowd-sourced locations funnel and the sibling of #856 (race-profile store) — "mirror its pattern: stable identity key, capture-then-aggregate, cold-start-after-first-athlete."

**Andy decision (AskUserQuestion 2026-06-29):** ship **Slice 1 — name+geo dedup only** (the stable identity key the issue and #856 both call the foundation). Photos + admin review are deferred to follow-up slices, consistent with the repo's focused-PR convention.

**Key grounding finding (shaped the design):** `gym_profiles` stores **no coordinates** — lat/lng live on `locale_profiles`. So the fingerprint is computed at write time from the locale row's name+coords (available to `_create_gym_profile` via its `profile_row` arg), and a SQL backfill of legacy rows is awkward (would need a join to a linking locale). Decision: **fingerprint-on-write, no migration** — going-forward profiles dedup by name+geo; legacy rows keep prior `mapbox_id`-only behavior (no regression). See §7.

**Positional-param hazard (avoided).** The route tests assert exact positional params on the `gym_profiles` INSERT (`private` at index 6). Appending `address_fingerprint` as the **last** column keeps those positions stable → existing tests untouched. The new lookup also short-circuits on a `None` fingerprint so no extra query is consumed in the existing test flows.

---

## 3. File-by-file edits

### 3.1 `routes/locales.py` (modified)

- **`_address_fingerprint(display_name, lat, lng) -> str | None`** (new, above `_shared_equipment_set`): the dedup key. Name lowercased with punctuation collapsed to single spaces (`re.sub(r'[^a-z0-9]+', ' ', …).strip()`); coords snapped to a ~111 m grid (`f'{name}|{float(lat):.3f}|{float(lng):.3f}'`). Returns `None` when name normalizes empty or either coord is missing/non-numeric → row stays `mapbox_id`-matchable only.
- **`_find_gym_profile_by_fingerprint(db, fingerprint)`** (new, beside it): the mapbox-miss fallback. `WHERE address_fingerprint = ? AND COALESCE(private, FALSE) = FALSE ORDER BY id DESC LIMIT 1` — excludes private profiles exactly as `_find_gym_profile` does (#446); newest-wins on a rare bucket collision; short-circuits to `None` on a falsy fingerprint (no query).
- **`_create_gym_profile`** (modified): pulls `lat`/`lng` off `profile_row` (guarded by `_row_has`), computes `fingerprint = _address_fingerprint(display, lat, lng)`, and appends `address_fingerprint` as the **last** INSERT column/param (keeps `private` at param index 6).
- **`_resolve_shared_profile`** (modified): after the existing `_find_gym_profile(mapbox_id)` miss, falls back to `_find_gym_profile_by_fingerprint(_address_fingerprint(name, lat, lng))` (name/lat/lng read off `profile` with `_row_has` guards). No-ops to `None` when name/coords absent → coordinate-less locales match exactly as before. This is the single chokepoint both the build and inherit paths flow through.

---

## 4. Code / tests

**`tests/test_locales.py` (+12 → 52 passing in the file):**
- `TestAddressFingerprint` (6): name normalization + geo bucketing; punctuation/case collapse to one key; same-hotel minor-coord-drift → same bucket; same-chain far-apart → distinct buckets; missing name/coords → `None`; non-numeric coords → `None`.
- `TestFindGymProfileByFingerprint` (2): SQL shape excludes private + carries the key; `None` fingerprint short-circuits (no query).
- `TestCreateGymProfileStampsFingerprint` (2): INSERT includes `address_fingerprint` as the last param + the pre-existing positional contract (display=1, category=2, private=6) is intact; missing coords → `NULL` fingerprint.
- `TestResolveSharedProfileFingerprintFallback` (2): falls back to the fingerprint lookup when mapbox misses (and passes the computed key); **no** fingerprint query when mapbox hits.

Imports added: `_address_fingerprint`, `_create_gym_profile`, `_find_gym_profile_by_fingerprint`, `_resolve_shared_profile`.

**Verification:** `python -m pytest tests/test_locales.py` → **52 passed**; `tests/test_locations.py` + the two redesign-locales render suites → **32 passed**. CI on PR #1009 green (Python unit suite, Layer 0 gate, JS harness, Vercel; Real-LLM smoke skipped — API-key-gated). No review comments.

---

## 5. Manual §5.0 verification steps

The going-forward dedup is exercisable on Vercel once ≥2 accounts exist:

1. Account A: add a hotel via the Mapbox search→pick flow, log its equipment, save (creates a `gym_profiles` row — now stamped with `address_fingerprint`).
2. Account B: add the **same** hotel; if Mapbox returns a **different feature id** (POI vs address hit), the `mapbox_id` lookup misses but the name+geo fallback should surface A's profile → B sees/inherits A's equipment instead of starting cold.
3. Negative: two **different** same-chain hotels (e.g. two Marriotts in different cities) must **not** collide — distinct geo buckets keep them apart.

(Appended to `CARRY_FORWARD.md` under the #971 entry.)

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**#971 Slice 2 — photos.** Add a `gym_profile_photos` table (FK to `gym_profiles`, uploader `user_id`, storage ref, created_at) and capture/display in the locale edit flow (`templates/locales/form.html` + `routes/locales._edit_locale`). Decide the storage backend up front (Vercel Blob vs. a URL field) — that's an Andy decision.

### 6.2 Alternative pivots
- **#971 Slice 3 — admin review** of user-submitted equipment updates: the `gym_profiles.disputed_items` column already exists; mirror the `/admin/curation-flags` queue pattern (`routes/admin.py` + `evidence_repo`-style helpers) for a review/approve/reject flow on peer edits to shared profiles.
- Back to the **#884** thread (slice 5 away overlay) if Andy redirects — see the #884 predecessor handoff.

### 6.3 Operating notes for next session
(1) Rule #13 — first re-read is `aidstation-sources/CLAUDE.md`; (2) read `CURRENT_STATE.md` + `CARRY_FORWARD.md`; (3) read this handoff; (4) `./scripts/verify-handoff.sh` for the anchor sweep. Note: this repo is **Postgres-only** (`get_db()` raises without `DATABASE_URL`); the `_FakeConn` substrate in `tests/test_locales.py` is how route logic is unit-tested without a live DB.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Ship **name+geo dedup only** this slice | Andy (AskUserQuestion 2026-06-29) | The stable identity key #971/#856 call the foundation; photos + admin review are separable follow-up slices; matches the focused-PR convention. |
| 2 | **Fingerprint-on-write, no migration** | Architect (grounded) | `gym_profiles` has no coords (they're on `locale_profiles`), so a SQL backfill is awkward; new profiles get the key on create, legacy rows keep `mapbox_id`-only behavior → no regression. |
| 3 | Geo bucket = **3 decimals (~111 m)**, name = lowercase + punct-collapsed | Architect | Tolerates the small coordinate drift Mapbox returns for one feature across lookups while keeping distinct same-name venues (rare within 111 m) apart. |
| 4 | Append `address_fingerprint` **last** in the INSERT | Architect | Keeps the positional params the route tests assert (`private`=6) stable → existing tests untouched. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_address_fingerprint` / `_find_gym_profile_by_fingerprint` present | ✅ grep `routes/locales.py` |
| INSERT carries `address_fingerprint` as final param | ✅ `_create_gym_profile` |
| `tests/test_locales.py` 52 passed; `test_locations` + redesign render 32 passed | ✅ pytest |
| CI green on PR #1009 (unit suite / Layer 0 gate / JS harness / Vercel) | ✅ check-runs |
| Handoff + bookkeeping committed with the slice | ✅ git |

---

## 9. Files shipped this session

**Substantive (2 files):**
1. `routes/locales.py`
2. `tests/test_locales.py`

**Bookkeeping (3 files):**
3. `aidstation-sources/CURRENT_STATE.md`
4. `aidstation-sources/CARRY_FORWARD.md`
5. this handoff

The 5-file ceiling applies to substantive files only; bookkeeping is outside the count.

---

## 10. Carry-forward updates

New `## #971` section in `CARRY_FORWARD.md`: Slice 1 shipped (name+geo dedup, no migration owed); Slices 2 (photos) + 3 (admin review) are the remaining work; the §5.0 two-account walkthrough recorded as an owed live exercise.

---

**End of handoff.**
