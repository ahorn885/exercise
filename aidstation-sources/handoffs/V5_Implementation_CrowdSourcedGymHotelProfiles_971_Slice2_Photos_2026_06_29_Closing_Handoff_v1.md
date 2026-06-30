# Crowd-Sourced Gym/Hotel Profiles (#971) — Slice 2: Profile Photos (Vercel Blob) — Closing Handoff

**Session:** Second slice of #971 (built after Slices 1+3) — the issue's photo affordance. Real in-app photo upload for shared gym/hotel profiles, backed by Vercel Blob, gated behind an admin review step.
**Date:** 2026-06-29
**Predecessor handoff:** `handoffs/V5_Implementation_CrowdSourcedGymHotelProfiles_971_Slice3_AdminReview_2026_06_29_Closing_Handoff_v1.md` (§6.1 = this slice's recipe; storage decision Vercel Blob already pinned there).
**Branch:** `claude/slice-2-implementation-287yr7`
**Status:** 6 substantive files (2 new templates incl. a 1-line dashboard nav; `requirements.txt` 1-line) + 3 test files. **PR opening + auto-merge (merge commit) on Andy's go.** Full suite green locally (3846 passed, 30 skipped).

---

## 1. Session-start verification (Rule #9)

Verified the Slice-3 substrate this slice builds beside is on-disk before starting.

| Claim | Anchor | Result |
|---|---|---|
| `verify-handoff.sh` clean | `aidstation-sources/scripts/verify-handoff.sh` → working tree clean, 0 ❌ | ✅ |
| `gym_profiles` table + Slice-3 `disputed_items` review live | `init_db.py:1232` DDL; `routes/admin.py` `gym_profile_edits` + `review_gym_profile_edit` | ✅ |
| Slice-2 was the committed next step, storage = Vercel Blob | Slice-3 handoff §6.1 + `CARRY_FORWARD.md` #971 | ✅ |
| No existing Blob/upload util to reuse | `grep` `BLOB_READ_WRITE`/`vercel_blob` → none; uploads use `request.files`+`secure_filename` (garmin/admin) | ✅ greenfield |

**Reconciliation note:** clean. Slice 2 is the photo affordance the Slice-3 handoff §6.1 left as the committed next step.

---

## 2. Session narrative

**Scope + the two owed decisions.** The storage backend (Vercel Blob) was already Andy's decision (Slice-3 §6.1). Two table-shape decisions were flagged as owed — they materially change the schema, so I surfaced them via `AskUserQuestion` before building rather than picking silently (CLAUDE.md "think before coding" / Stop-and-ask #5):

1. **Photo scope → SHARED PROFILE (Andy 2026-06-29).** A photo attaches to the shared `gym_profiles` row, so every athlete who inherits that profile sees it — matching the crowd-sourced intent and the existing shared-equipment model, not a per-athlete personal note.
2. **Moderation → ADMIN-APPROVED BEFORE PEER-VISIBLE (Andy 2026-06-29).** Crowd-sourced photos are user-generated content visible to peers (an abuse vector). Each upload is `pending` until an admin approves it, reusing the Slice-3 review-queue pattern. The uploader sees their own pending photo meanwhile; peers don't.

**Defaults I picked (stated, not asked — sensible + reversible):** JPEG/PNG/WebP only; ≤8 MB/file; ≤8 non-rejected photos per profile. Private profiles never reach peers, so their photos skip the admin queue (the uploader still sees their own).

**Why a separate upload form, not the equipment form.** The equipment editor is one big `<form method="post">` (equipment + terrain + craft + notes + privacy) with no `enctype`. Folding a file input into it would intermix a multipart photo with the equipment-save transaction. Instead the photo strip + upload control is its **own** `multipart/form-data` form posting to a dedicated route — the equipment-save flow is untouched (surgical-change principle).

**Why photos require a backing profile first.** Photos hang off `gym_profiles(id)`. A brand-new locale with no profile yet has nothing to attach to, so the photo section only renders once `_resolve_shared_profile` returns a row (`photo_profile_id`). The athlete saves equipment once (which creates the profile), then photos are offered. The issue wants photos "at first-capture and on updates"; first-capture here = the visit after the profile is created.

**Reject deletes outright.** There's no appeal flow, so a rejected photo's row + blob are deleted rather than tombstoned — `status` only ever holds `pending`/`approved`. The blob delete runs after the DB commit, best-effort (a leaked blob is harmless storage, a failed request is not).

---

## 3. File-by-file edits

### 3.1 `init_db.py` (modified)
New `gym_profile_photos` table + index appended to `_PG_MIGRATIONS` right after the `gym_profiles` indexes (auto-applies on deploy — no layer0 owed). Columns: `id`, `gym_profile_id` FK `gym_profiles(id) ON DELETE CASCADE`, `uploaded_by_user_id` FK `users`, `blob_url` (NOT NULL, public URL), `blob_pathname` (store key for delete), `content_type`, `status` `CHECK IN ('pending','approved') DEFAULT 'pending'`, `created_at`, `reviewed_by_user_id`, `reviewed_at`. Index `gym_profile_photos_profile_idx (gym_profile_id, status)`.

### 3.2 `routes/locales.py` (modified)
- `import os` (token presence check).
- **Constants:** `_PHOTO_ALLOWED_TYPES` ({jpeg→jpg, png, webp}), `_PHOTO_MAX_BYTES` (8 MB), `_PHOTO_MAX_PER_PROFILE` (8).
- **`_photo_blob_configured()`** — `BLOB_READ_WRITE_TOKEN` present?
- **`_put_photo_blob(data, pathname, content_type)`** — lazy `import vercel_blob`; `vercel_blob.put(...)`; returns the store response (`url`, `pathname`). Isolated so tests stub it + the SDK/token aren't needed off the upload path.
- **`_delete_photo_blob(url)`** — lazy `vercel_blob.delete`, best-effort (try/except + Rule-#15 log; never fails the request).
- **`_count_active_photos(db, gym_profile_id)`** — `COUNT(*)` (rejected rows are deleted, so all count).
- **`_insert_profile_photo(...)`** — INSERT a `pending` row. Rule-#15 log.
- **`_list_profile_photos(db, gym_profile_id, viewer_uid)`** — `status='approved' OR uploaded_by=viewer`; each entry `{id, url, is_own, pending}`.
- **`_delete_profile_photo(db, photo_id, uid)`** — uploader-only; DELETE; returns `{blob_url}` for cleanup or `None`.
- **`_list_pending_profile_photos(db, limit=200)`** — JOIN `gym_profiles`; `status='pending' AND COALESCE(private,FALSE)=FALSE`; oldest first.
- **`_review_profile_photo(db, photo_id, approve, reviewer_uid=None)`** — approve → `status='approved'`+`reviewed_by/at`; reject → DELETE; returns `{id, gym_profile_id, blob_url}` or `None` (missing / already reviewed). Rule-#15 log.
- **`_edit_locale` GET** — computes `photo_profile_id` (= `shared['id']` or None) + `photos` (`_list_profile_photos`) and passes both to the template.
- **Routes:** `upload_locale_photo` (`POST /locales/<locale>/photos`) — verifies the locale + a backing profile, token-config, file present, type/size/count guards, `_put_photo_blob` (try/except → flash), `_insert_profile_photo`, commit, flash. `delete_locale_photo` (`POST /locales/<locale>/photos/<int:photo_id>/delete`) — `_delete_profile_photo` then commit + best-effort blob delete.

### 3.3 `routes/admin.py` (modified)
- Import `_delete_photo_blob`, `_list_pending_profile_photos`, `_review_profile_photo` from `routes.locales`.
- **`GET /admin/gym-profile-photos`** (`gym_profile_photos`) — admin-only; renders the queue.
- **`POST /admin/gym-profile-photos/<int:photo_id>/review`** (`review_gym_profile_photo`) — `action` ∈ {approve,reject}; `_review_profile_photo` + an `admin_audit` row in the same transaction (mirrors `review_gym_profile_edit`); on reject, `_delete_photo_blob` after commit; flash + redirect.

### 3.4 `templates/admin/gym_profile_photos.html` (new)
Mirrors `gym_profile_edits.html` (extends `base.html`). A photo-strip grid of pending photos (thumbnail + profile name/category + uploader link + when) with Approve/Reject forms (CSRF + `action`). Empty state when none.

### 3.5 `templates/admin/dashboard.html` (modified)
One-line nav link "Gym photo reviews" → `admin.gym_profile_photos`, between "Gym profile reviews" and "Evidence sources".

### 3.6 `templates/locales/form.html` (modified)
After the main form (gated on `photo_profile_id`): a Photos `<section>` — a thumbnail strip (approved ∪ own-pending; own photos carry a "Pending review" chip + a Remove form; peers' aren't deletable) and a `multipart/form-data` upload form (`name="photo"`, `accept="image/jpeg,image/png,image/webp"`).

### 3.7 `requirements.txt` + `.env.example` (modified)
`vercel_blob>=0.4` added. `.env.example` documents `BLOB_READ_WRITE_TOKEN` (optional; without it the photo form reports "not configured", equipment editing unaffected).

---

## 4. Code / tests

**`tests/test_locales.py` (+~22):** `TestInsertProfilePhoto` (pending row shape), `TestCountActivePhotos` (COUNT shape + no-row=0), `TestListProfilePhotos` (approved ∪ own-pending, `is_own`/`pending` flags), `TestDeleteProfilePhoto` (uploader deletes own / non-owner blocked / missing→None), `TestListPendingProfilePhotos` (excludes private + joins profile), `TestReviewProfilePhoto` (approve sets status + reviewer; reject deletes; already-reviewed→None; missing→None). Imports added for the six new helpers.

**`tests/test_redesign_admin_render.py` (+2):** `_GymPhotoConn` routes `FROM gym_profile_photos` to a seeded pending photo; `test_gym_profile_photos_renders` asserts the queue page renders the photo + `/admin/gym-profile-photos/7/review` + `User #2`; `test_dashboard_links_to_gym_profile_photos`.

**`tests/test_redesign_locales_form_render.py` (+2):** `test_form_offers_photo_upload_when_profile_backed` (multipart input + own-only delete + peer not deletable) and `test_form_hides_photos_without_backing_profile`.

**Verification:** full `tests/` → **3846 passed, 30 skipped**. `import routes.admin, routes.locales` clean (no circular-import regression from the new cross-module imports); `import vercel_blob` resolves.

---

## 5. Manual §5.0 verification steps

Exercisable on Vercel **once `BLOB_READ_WRITE_TOKEN` is set** (and ≥2 accounts for the peer-visibility leg):

1. Account A: build a hotel's equipment profile (creates the shared `gym_profiles` row), reopen the editor → the **Photos** section appears.
2. A uploads a JPEG/PNG/WebP → it shows with a **"Pending review"** chip; it is NOT yet visible to account B inheriting the same profile.
3. Admin (`/admin` → "Gym photo reviews" → `/admin/gym-profile-photos`): A's photo shows. **Approve** → A and B both see it on the editor strip. **Reject** (on a different photo) → it disappears (row + blob deleted).
4. Negative: a non-image (or >8 MB, or the 9th photo) is refused with a flash; with no token set, the upload flashes "not configured."
5. A's own **Remove** on a photo drops it (row + blob); B cannot remove A's photo (no Remove control on peers' photos).

(Recorded in `CARRY_FORWARD.md` under the #971 entry as an owed live exercise, gated on the token.)

---

## 6. Next session pointers

**#971 after this slice:** Slices 1 (name+geo dedup) + 2 (photos) + 3 (admin review) are all shipped + merged. The **only remaining #971 piece** is the cross-layer plan-gen follow-up that descends from the Slice-3 design — **that is the committed next step (Andy 2026-06-29):**

### 6.1 THE COMMITTED NEXT STEP — plan-gen treats a disputed item as not-available (Layer 2C)
**Approved (Andy 2026-06-29): a disputed item should be treated as not-available for plan generation** (D-60 §5). Build a **Layer-2C slice** that, for a locale's shared profile, derives the **disputed tags** from the open correction proposals on `gym_profiles.disputed_items` (the `removes` set Slice 3 records) and **removes them from the equipment set Layer 2C resolves** — so a tag a peer flagged as wrong stops driving plan prescriptions while it's under review. It is a **cross-layer change (stop-and-ask trigger #3)** — scope it, surface options/tradeoffs, and get Andy's explicit confirmation before building.

Concrete starting points:
- Slice 3's `_parse_profile_edits` / `_load_profile_edits` (`routes/locales.py`) already parse the proposal objects `{by, adds, removes, at}` — the disputed-tag set for a profile is the union of open proposals' `removes`.
- Layer 2C equipment resolution flows through `_shared_equipment_set` + the overrides cascade; the disputed-tag subtraction is the new step. Confirm the exact resolution seam in `layer2c/` (and whether to subtract pre- or post-override) as part of scoping.
- Decide the semantics with Andy: subtract disputed tags for **all** athletes inheriting that shared profile (every inheritor), and whether an *approved* correction (already folded into `equipment`) needs any further handling (it shouldn't — approval mutates the shared set directly).
- It touches Layer 2C's input contract → spec the change (14-section depth standard) before code; likely a `Layer2C_Spec` cross-ref and an invalidation/eviction touch when `disputed_items` changes.

### 6.2 Operating notes for next session
(1) Rule #13 read order: `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`. (2) **`BLOB_READ_WRITE_TOKEN` is DEPLOYED** as a Vercel env var (Andy 2026-06-29; manually added after the auto-connect was disrupted by an accidental first token) — photo upload is live in prod; no longer owed. (3) Postgres-only repo; the `_FakeConn` substrate in `tests/test_locales.py` and `_Conn`/`_GymPhotoConn` in `tests/test_redesign_admin_render.py` unit-test route/helper logic without a live DB. (4) `gym_profile_photos` is a public-schema migration (auto-applies on deploy) — **no layer0-apply owed.** (5) Admin moderation covers approve/reject of *pending* photos; removing an *already-approved* photo is uploader-only today — admin-removes-approved would be a small follow-up if needed.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Photo **scope = shared profile** (on `gym_profiles`, every inheritor sees an approved photo) | **Andy (2026-06-29, AskUserQuestion)** | Matches #971's crowd-sourced intent + the shared-equipment model; per-athlete would defeat the purpose (peers never benefit). |
| 2 | **Admin-approved before peer-visible** (`pending`→`approved`, reusing the Slice-3 review pattern) | **Andy (2026-06-29, AskUserQuestion)** | Crowd-sourced photos are UGC visible to peers — an abuse vector. The uploader sees their own pending photo; peers only see approved. |
| 3 | **Separate multipart upload form/route**, not folded into the equipment save | Claude (surgical) | The equipment form is a single large non-multipart POST; intermixing a file upload risks the save flow. Its own route keeps the equipment path untouched. |
| 4 | **Reject deletes the row + blob** (no `rejected` tombstone) | Claude | No appeal flow, so `status` only holds `pending`/`approved`; deleting reclaims blob storage. Blob delete is post-commit best-effort. |
| 5 | Defaults: **JPEG/PNG/WebP, ≤8 MB, ≤8 photos/profile**; private-profile photos skip the queue | Claude (stated, reversible) | Sensible caps to bound storage + abuse; a private profile never reaches peers, so its photos need no review (uploader still sees them). |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `gym_profile_photos` DDL + index in `_PG_MIGRATIONS` | ✅ `init_db.py` |
| Photo helpers present (`_put_photo_blob`/`_delete_photo_blob`/`_count_active_photos`/`_insert_profile_photo`/`_list_profile_photos`/`_delete_profile_photo`/`_list_pending_profile_photos`/`_review_profile_photo`) | ✅ grep `routes/locales.py` |
| `upload_locale_photo` + `delete_locale_photo` routes; `_edit_locale` passes `photos`+`photo_profile_id` | ✅ `routes/locales.py` |
| `/admin/gym-profile-photos` GET + `/review` POST present; audited | ✅ `routes/admin.py` |
| `templates/admin/gym_profile_photos.html` exists; dashboard nav link added; `form.html` photo section | ✅ all three templates |
| `vercel_blob` in `requirements.txt`; `BLOB_READ_WRITE_TOKEN` in `.env.example` | ✅ |
| Full suite 3846 passed / 30 skipped; no circular-import regression | ✅ pytest + import |
| Bookkeeping (`CURRENT_STATE.md` + `CARRY_FORWARD.md` + this handoff) committed with the slice | ✅ git |

---

## 9. Files shipped this session

**Substantive (6 incl. 1-line nav + 1-line dep; + 3 test):**
1. `init_db.py`
2. `routes/locales.py`
3. `routes/admin.py`
4. `templates/admin/gym_profile_photos.html` (new)
5. `templates/admin/dashboard.html` (1-line nav link)
6. `templates/locales/form.html`
7. `requirements.txt` (1-line dep) + `.env.example` (doc)
8. `tests/test_locales.py`
9. `tests/test_redesign_admin_render.py`
10. `tests/test_redesign_locales_form_render.py`

Over the ~5 substantive ceiling like Slice 3 — a cohesive capture+review feature (table + capture route + admin review + the two templates). Noted, not split.

**Bookkeeping (3 files, outside the count):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

## 10. Carry-forward updates

`## #971` section in `CARRY_FORWARD.md` updated: Slice 2 DONE (heading + a Slice-2 bullet); the owed `BLOB_READ_WRITE_TOKEN` provisioning recorded as live carry-state; the Slice-2 §5.0 walkthrough (token-gated) added to the walkthrough ledger; the Layer-2C plan-gen follow-up flagged as the only remaining #971 slice.

---

**End of handoff.**
