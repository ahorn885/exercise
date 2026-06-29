# Crowd-Sourced Gym/Hotel Profiles (#971) — Slice 3: Admin Review of Peer Corrections — Closing Handoff

**Session:** Third slice of #971 — build the issue's "allow user-based updates, with an administrative review step." Activates the dormant `gym_profiles.disputed_items` column as a peer-correction proposal store + an admin approve/reject queue.
**Date:** 2026-06-29
**Predecessor handoff:** `handoffs/V5_Implementation_CrowdSourcedGymHotelProfiles_971_Slice1_NameGeoDedup_2026_06_29_Closing_Handoff_v1.md` (#971 Slice 1 — name+geo dedup; merged PR #1009).
**Branch:** `claude/971-name-geo-dedup-hfnko6`
**Status:** 5 code/template substantive files + 3 test files (one edit is a 1-line dashboard nav link; the explicit "report as wrong" flag was added mid-review at Andy's request — §7 #2). **PR opening + auto-merge (merge commit) on Andy's go (2026-06-29).** Full suite green locally (3775 passed, 30 skipped). **#971 is PAUSED after this slice (Andy 2026-06-29) — Slices 1 + 3 shipped; the committed next step is Slice 2 (photos), storage backend = Vercel Blob (§6.1).**

---

## 1. Session-start verification (Rule #9)

Verified Slice 1 actually landed before opening Slice 3 (it's the precondition this slice builds beside).

| Claim | Anchor | Result |
|---|---|---|
| Slice 1 (`_address_fingerprint` / `_find_gym_profile_by_fingerprint`) on-disk + merged | `grep -n` `routes/locales.py` → present at `:384`/`:411`; `git log` shows PR #1009 merged (e970a52) | ✅ |
| `verify-handoff.sh` clean | `aidstation-sources/scripts/verify-handoff.sh` → working tree clean, no ❌ | ✅ |
| `gym_profiles.disputed_items` column exists, dormant | `grep -rn disputed_items` → only `init_db.py:1240` (DDL) + design docs; never written/read in code | ✅ dormant |
| `/admin/curation-flags` queue pattern to mirror | `routes/admin.py:693` + `templates/admin/curation_flags.html` + `evidence_repo` helpers | ✅ |
| D-60 defines `disputed_items` semantics | `designs/Onboarding_D60_Design_v1.md` §5 (row 5 of decision table) + §10 — curator-review deferred as TBD | ✅ |

**Reconciliation note:** clean. Slice 3 is the curator-review mechanism the D-60 design explicitly left as TBD (§10: "Avoids voting/curator-review overhead at v1… resolution TBD").

---

## 2. Session narrative

**Scope-pick gate.** With Slice 1 merged, "keep working on 971" means the next slice. Two remained: **Slice 2 (photos)** — architect-recommended, but blocked on a storage-backend choice (Vercel Blob vs URL field) that's a mandatory stop-and-ask (Andy decision) — and **Slice 3 (admin review)** — self-contained, mirrors the existing `/admin/curation-flags` queue, no new infra decision. An `AskUserQuestion` to confirm the slice + storage didn't go through (tool error); Andy said "continue." Picked **Slice 3** because it's fully within execution authority and doesn't gamble on the storage decision Slice 2 needs. Slice 2 stays available the moment Andy picks a backend.

**Key grounding finding (shaped the design).** Two things: (1) peer edits to a shared profile today only write **personal** `locale_equipment_overrides` — there was **no** mechanism for a peer to propose a change to the *shared* profile, so crowd-sourced corrections never propagated. (2) `disputed_items` is **dormant** (declared at D-60 §5 for exactly this, never written/read — the same shape of move as Slice 1's dormant `address_fingerprint`). So Slice 3 = activate `disputed_items` as the proposal store + build the admin review loop the D-60 design deferred.

**The capture insight + the explicit-flag amendment.** The inherit path already computes the peer's shared-vs-submitted delta (for `_save_overrides`); that same delta **is** the crowd-sourced correction. The first cut recorded it automatically on any divergence. **Andy reviewed and asked for an explicit flag (2026-06-29)** so routine personal overrides don't flood the admin queue — the original D-60 design's instinct (it separated "personal override" from "dispute" for exactly this reason). Final behavior: the inherit-mode form carries a **"the shared profile is wrong — submit for review" checkbox**; the delta becomes a proposal **only when it's ticked**. An unflagged save (or a view that matches the shared base) withdraws any prior proposal; the box is pre-checked when the peer already has one pending, so re-saving doesn't silently retract it.

**Cross-layer line held.** The D-60 design also calls for plan-gen to treat disputed items as not-available (a Layer-2C change). That's a **cross-layer surface change (stop-and-ask trigger #3)** — explicitly **deferred** to a follow-up slice. Approving a proposal in this slice updates the shared `equipment` set, which flows to every inheritor through the **existing** `_shared_equipment_set` resolution — so approvals take effect entirely through the already-shipped contract, touching no inter-layer surface.

---

## 3. File-by-file edits

### 3.1 `routes/locales.py` (modified)

- **import** `from datetime import datetime, timezone` (proposal timestamp).
- **`_parse_profile_edits(payload)`** (new): tolerant JSON→`list[dict]` parse of `disputed_items` (NULL/empty/malformed → `[]`).
- **`_load_profile_edits(db, gym_profile_id)`** (new): current proposals for one profile.
- **`_record_profile_edit(db, gym_profile_id, proposer_uid, shared_tags, athlete_tags, valid_names, *, report, now=None)`** (new): the capture. Records a proposal **only when `report` is truthy** (the peer ticked the flag); an unflagged save records nothing and withdraws any prior proposal. When flagged: diff = `athlete_tags` vs `shared_tags` (filtered to `valid_names`); upserts one proposal per (profile, peer) as `{by, adds, removes, at}`; a flagged-but-empty diff also withdraws; writes `disputed_items` whole (NULL when none remain). Rule #15 `print()` of flag + inputs + outcome.
- **`_list_pending_profile_edits(db, limit=500)`** (new): admin queue — non-private profiles with non-empty `disputed_items`, each with shared equipment + parsed proposals; skips rows whose proposals don't parse.
- **`_review_profile_edit(db, gym_profile_id, proposer_uid, approve)`** (new): approve folds `adds`/`removes` into the shared `equipment` set (`(shared ∪ adds) − removes`) + advances `last_confirmed_by`/`_at` to the proposer; reject leaves equipment untouched; either way removes the proposal. Returns the applied proposal or `None` (no such open proposal / missing profile). Rule #15 `print()`.
- **`_edit_locale`** (modified): inherit branch reads `report_correction = request.form.get('report_correction') == '1'` and calls `_record_profile_edit(..., report=report_correction)` after `_save_overrides`; the GET path computes `reported` (does this peer have a pending proposal on `shared['id']`?) and passes it to the template so the checkbox reflects pending state.

### 3.2 `routes/admin.py` (modified)

- **import** `_list_pending_profile_edits`, `_review_profile_edit` from `routes.locales` (consistent with admin already importing `from routes.auth`).
- **`GET /admin/gym-profile-edits`** (`gym_profile_edits`, new): admin-only; renders the queue.
- **`POST /admin/gym-profile-edits/<int:gym_profile_id>/review`** (`review_gym_profile_edit`, new): `action` ∈ {`approve`,`reject`} + `proposer_id`; calls `_review_profile_edit`; writes an `admin_audit` row in the same transaction (mirrors `resolve_flag`); flashes + redirects.

### 3.3 `templates/admin/gym_profile_edits.html` (new)

Mirrors `curation_flags.html` (extends `base.html`, redesign shell). One card per profile (name + category + shared equipment), a row per proposal (proposer → `admin.user_detail`, add chips, remove chips, when) with Approve/Reject forms (CSRF + `proposer_id` hidden). Empty state when no proposals.

### 3.4 `templates/admin/dashboard.html` (modified)

One-line nav link "Gym profile reviews" → `admin.gym_profile_edits`, between "Curation gaps" and "Evidence sources".

### 3.5 `templates/locales/form.html` (modified)

Inherit-mode only (`{% if mode == 'shared_inherit' %}`), after the Notes field: the **"the shared profile is wrong — submit my changes for review"** checkbox (`name="report_correction"`, `value="1"`), pre-checked when `reported`. Copy makes the default ("leave unchecked to keep your edits to yourself") explicit.

---

## 4. Code / tests

**`tests/test_locales.py` (+12 → 64 passing in the file):**
- `TestRecordProfileEdit` (6): records delta as proposal **when flagged**; **unflagged edit records nothing**; **unflagged save withdraws a prior proposal**; flagged-but-empty delta withdraws; upsert replaces same-peer + keeps others; invalid names dropped.
- `TestListPendingProfileEdits` (2): SQL shape excludes private + parses shared tags + proposals; skips rows with empty/malformed proposals.
- `TestReviewProfileEdit` (4): approve folds into shared equipment (`(Barbell,Squat rack ∪ Treadmill) − Squat rack` → `[Barbell, Treadmill]`) + clears + `last_confirmed_by`=proposer; reject leaves equipment untouched; unknown proposal → `None`; missing profile → `None`.

Imports added: `_list_pending_profile_edits`, `_record_profile_edit`, `_review_profile_edit`.

**`tests/test_redesign_admin_render.py` (+2):**
- `test_gym_profile_edits_renders`: `_GymEditConn` routes the `FROM gym_profiles` query to a seeded proposal; asserts the queue page renders the proposal + the `/admin/gym-profile-edits/77/review` actions + `User #2`.
- `test_dashboard_links_to_gym_profile_edits`: the dashboard nav link resolves.

**`tests/test_redesign_locales_form_render.py` (+1 assertion):** `test_form_shared_inherit_shows_override_chips` now also asserts `name="report_correction"` renders in inherit mode.

**Verification:** **full `tests/` → 3775 passed, 30 skipped** (skips are API-key-gated real-LLM). `import routes.admin, routes.locales` clean (no circular-import regression from the new cross-module import).

---

## 5. Manual §5.0 verification steps

Exercisable on Vercel once ≥2 accounts exist:

1. Account A: add a hotel, log equipment, save (creates a shared `gym_profiles` row).
2. Account B: add the **same** hotel (resolves to A's shared profile via mapbox_id or the Slice-1 name+geo fallback), inherit it, change the equipment view (add one item, remove one), **tick the "the shared profile is wrong — submit for review" box**, and save.
3. Negative-A: B makes the same edit but **leaves the box unchecked** → it's a personal override only; **no** proposal appears in the admin queue.
4. Admin (`/admin` → "Gym profile reviews" → `/admin/gym-profile-edits`): B's flagged proposal shows (proposer, +adds, −removes). **Approve** → A's shared profile equipment updates (A and every other inheritor now resolve the corrected set). **Reject** → shared set unchanged, proposal cleared.
5. Negative-B: B re-saves a view that **matches** the (current) shared profile, or saves again with the box **unchecked** → B's proposal **withdraws** (disappears from the queue). Re-opening the editor with a proposal pending shows the box **pre-checked**.

(Recorded in `CARRY_FORWARD.md` under the #971 entry as an owed live exercise.)

---

## 6. Next session pointers

**#971 is PAUSED here (Andy 2026-06-29).** Slices 1 + 3 are shipped; the work below is the committed next step when #971 resumes — not started this session.

### 6.1 The committed next step — #971 Slice 2: photos (storage = Vercel Blob)
**Decided (Andy 2026-06-29): build Slice 2 with the Vercel Blob backend** (real in-app photo upload, not a paste-a-URL field). Scope:
- **New `gym_profile_photos` table** — FK to `gym_profiles(id)`, uploader `user_id`, the Blob storage ref (URL/pathname returned by the Blob put), `created_at`. Public-schema migration in `init_db._PG_MIGRATIONS` (auto-applies on deploy — no `layer0-apply` owed).
- **Upload plumbing** — add the Vercel Blob SDK + a `BLOB_READ_WRITE_TOKEN` (Andy provisions in Vercel + as a container/CI secret if tests need it); an upload route (or a direct-to-Blob client-upload handshake) that writes the blob then inserts the `gym_profile_photos` row.
- **Capture + display** — a file input in the locale equipment form (`templates/locales/form.html`) and a thumbnail strip; wire capture/read through `routes/locales._edit_locale`. The issue's scope asks for photos both at first-capture and on user updates.
- **Decisions still owed before/while building:** whether photos attach to the shared `gym_profiles` row (visible to every inheritor) or per-athlete; max count/size + content-type allowlist; whether to gate display behind the same `private` rule the equipment uses. Surface these as you scope — they affect the table shape.

### 6.2 Also approved for a later slice — plan-gen disputed-item treatment
**Approved (Andy 2026-06-29): a disputed item should be treated as not-available for plan generation** (D-60 §5). This is the Slice-3 follow-up: a **Layer-2C slice** that derives disputed *tags* from open proposals' `removes` on a locale's shared profile and removes them from the equipment set Layer 2C resolves. It's a **cross-layer change (stop-and-ask trigger #3)** — its own slice, scoped + confirmed before building. *(The explicit "report as wrong" affordance, once listed here as deferred, was built this session.)*

### 6.3 Operating notes for next session
(1) Rule #13 read order: `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`. (2) Postgres-only repo (`get_db()` raises without `DATABASE_URL`); the `_FakeConn` substrate in `tests/test_locales.py` and the `_Conn`/`_GymEditConn` substrate in `tests/test_redesign_admin_render.py` are how route logic is unit-tested without a live DB. (3) **No Neon/layer0 apply owed by Slices 1+3** — both columns already exist; Slice 2 will owe a public-schema migration for `gym_profile_photos` (auto-applies on deploy). (4) This slice's PR opened + auto-merged on Andy's go (2026-06-29); #971 paused after it.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Ship **Slice 3 (admin review)**, not Slice 2 (photos), this session | Claude (under "continue", AskUserQuestion failed) | Slice 2 is blocked on a storage-backend Andy decision; Slice 3 is self-contained + mirrors an existing pattern + needs no new infra decision. Reversible — Slice 2 still open. |
| 2 | **Explicit "report as wrong" flag** required for a peer edit to become a proposal | **Andy (2026-06-29)** | First cut auto-recorded any divergence; Andy asked for the flag so routine personal overrides don't flood the queue. The flag separates "this is a factual correction to the shared truth" from "this is my personal tweak" — the D-60 design's original instinct. Inherit-mode checkbox, pre-checked when a proposal is pending; unflagged save (or matching view) withdraws. |
| 3 | **Reuse the dormant `disputed_items` column**, enriched from "array of tags" to proposal objects `{by, adds, removes, at}` | Claude (grounded) | No migration (column already exists, never read → no back-compat). Forward-compatible with the D-60 plan-gen intent: a future "disputed tag ⇒ not-available" slice derives disputed *tags* from open proposals' `removes`. |
| 4 | **Defer the cross-layer plan-gen treatment** (disputed ⇒ not-available, D-60 §5) | Claude | It's a Layer-2C inter-layer change (stop-and-ask trigger #3). Approvals already take effect through the existing shared-equipment contract, so this slice ships value without crossing that surface. |
| 5 | Approve folds into shared `equipment` + advances `last_confirmed_by`; **does not** bump `contribution_count` | Claude | The proposer already bumped `contribution_count` on inherit (`_touch_gym_profile_confirmation`); bumping again on approve would double-count. `last_confirmed_by`=proposer is the right provenance for "their correction is now the confirmed state." |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_record_profile_edit` / `_list_pending_profile_edits` / `_review_profile_edit` present | ✅ grep `routes/locales.py` |
| `_record_profile_edit` gated on `report` flag; `report_correction` read from form; `name="report_correction"` in `form.html` | ✅ grep `routes/locales.py` + `templates/locales/form.html` |
| `_edit_locale` inherit branch calls `_record_profile_edit` | ✅ `routes/locales.py` inherit branch |
| `/admin/gym-profile-edits` GET + `/review` POST present; audited | ✅ `routes/admin.py` |
| `templates/admin/gym_profile_edits.html` exists; dashboard nav link added | ✅ both templates |
| `tests/test_locales.py` 62 passed; `tests/test_redesign_admin_render.py` +2; full suite 3773 passed / 30 skipped | ✅ pytest |
| No circular-import regression (`import routes.admin, routes.locales`) | ✅ |
| Bookkeeping (`CURRENT_STATE.md` + `CARRY_FORWARD.md` + this handoff) committed with the slice | ✅ git |

---

## 9. Files shipped this session

**Substantive (5 code/template + 3 test):**
1. `routes/locales.py`
2. `routes/admin.py`
3. `templates/admin/gym_profile_edits.html` (new)
4. `templates/admin/dashboard.html` (1-line nav link)
5. `templates/locales/form.html` (report-as-wrong checkbox — added in the explicit-flag amendment)
6. `tests/test_locales.py`
7. `tests/test_redesign_admin_render.py`
8. `tests/test_redesign_locales_form_render.py` (1 assertion)

Over the ~5 soft ceiling (one edit is a 1-line nav link, three are test files; the explicit-flag amendment added the `form.html` surface + its render assertion mid-review at Andy's request) — noted, not split.

**Bookkeeping (3 files, outside the count):**
- `aidstation-sources/CURRENT_STATE.md`
- `aidstation-sources/CARRY_FORWARD.md`
- this handoff

---

## 10. Carry-forward updates

`## #971` section in `CARRY_FORWARD.md` updated: Slices 1 + 3 DONE, Slice 2 (photos) the only remaining slice (storage backend = Andy decision); the one Slice-3 deferred follow-up (plan-gen disputed treatment) recorded (the explicit opt-in affordance was built this session, so it's no longer deferred); the Slice-3 §5.0 walkthrough — now including the flagged-vs-unflagged paths — recorded as an owed live exercise.

---

**End of handoff.**
