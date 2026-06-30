# Crowd-Sourced Gym/Hotel Profiles (#971) — Disputed-Item Follow-Ups A+B — Closing Handoff

**Session intent:** Pick up the three optional, non-owed follow-ups flagged when the Layer-2C disputed-item plan-gen slice shipped. Built **A** (athlete "under review" chip) + **B** (admin inheritor-count); **parked C** (proactive eviction) on Andy's call.
**Date:** 2026-06-30
**Branch:** `claude/disputed-chip-followups-vrngyq` (PR not yet opened — push + bookkeep + wait for Andy's go)
**Kickoff this extends:** `handoffs/V5_NextWork_CrowdSourcedProfiles_971_DisputedItemFollowUps_2026_06_30_Kickoff_Handoff_v1.md`
**Design:** `designs/CrowdSourcedProfiles_DisputedItemPlanGen_971_Design_v1.md` (§9 lists A/B/C as out-of-scope/possible follow-ups).

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` ✅ clean (file existence + backlog pointers + §8 table of the predecessor disputed-item-plan-gen handoff). Spot-checked the reusable seam: `locations.disputed_equipment_tags(db, gym_profile_id)` exists (`locations.py:53`) and `locale_effective_tags(..., exclude_disputed=…)` exists (`:84`) — both as the kickoff described. No drift.

---

## 2. Session narrative

The kickoff scoped three follow-ups, none a blocker. A and B are cheap, independent, UI-only wins and **not** stop-and-ask triggers; built both. C (proactive cross-inheritor cache eviction) **re-litigates the ratified lazy-invalidation decision → stop-and-ask trigger #3**, and the kickoff requires a real "lazy is too slow" signal before building. Surfaced the options/tradeoffs to Andy via AskUserQuestion; **Andy chose to park C** (keep lazy; revisit only on a real complaint). While scoping C, confirmed the kickoff's open question: the admin **approve** path (`routes/admin.review_gym_profile_edit` → `_review_profile_edit`) mutates the shared `equipment` set but does **not** fan out cache eviction to inheritors — a pre-existing lazy behavior, consistent with the ratified decision, in C's scope if it's ever built (not a new gap).

---

## 3. File-by-file edits

### 3.1 `routes/locales.py` (modified) — both follow-ups' backend
- **Follow-up A** — `_edit_locale` GET path computes `disputed = locations.disputed_equipment_tags(db, shared['id'])` for the **inherit path only** (`inherit and shared is not None`; own/build modes get `set()` — a dispute exists only against a shared base) and passes `disputed=disputed` to `render_template`.
- **Follow-up B** — `_list_pending_profile_edits` attaches `inheritor_count` to each queue entry via **one grouped query** over the queued profile ids: `SELECT gym_profile_id, COUNT(DISTINCT user_id) AS n FROM locale_profiles WHERE gym_profile_id IN (<placeholders>) GROUP BY gym_profile_id` (distinct *users* = the honest blast radius, not locale links; not a per-row N+1). Profiles absent from the result default to 0.

### 3.2 `templates/locales/form.html` (modified) — follow-up A chip
After the existing `+ override` / `– override` / `shared` chip chain inside the `mode == 'shared_inherit'` block, added: `{% if tag in disputed and tag not in removes %}<span class="chip warn" title="A peer flagged this as wrong; it's under admin review and won't drive your plan meanwhile">under review</span>{% endif %}`. The `tag not in removes` guard suppresses the chip for the viewer who disputed it themselves (their `– override` already says it's gone for them) — the kickoff §2 gut check.

### 3.3 `templates/admin/gym_profile_edits.html` (modified) — follow-up B chip
A `chip` next to the profile-name header rendering `{{ p.inheritor_count }} inheritor(s)`, with `warn` styling at `inheritor_count >= 10`.

### 3.4 Tests (3 files touched)
- `tests/test_locales.py` — `TestListPendingProfileEdits.test_attaches_distinct_user_inheritor_count` (asserts the grouped `COUNT(DISTINCT user_id)` query, both queued ids in params, and the 12/0 attach).
- `tests/test_redesign_locales_form_render.py` — `test_form_shared_inherit_shows_under_review_chip` (chip shows for a disputed-not-removed tag; suppressed when `tag in removes`; absent in legacy mode); added `disputed=set()` to the `_form_ctx` default.
- `tests/test_redesign_admin_render.py` — `_GymEditConn` routes the new count query; `test_gym_profile_edits_renders` asserts `5 inheritors` renders.

---

## 4. Verification
- Full suite **3961 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings).
- `ruff check routes/locales.py` → All checks passed.
- Touched files individually: `test_locales.py` 78 passed; `test_redesign_locales_form_render.py` 24 passed; `test_redesign_admin_render.py` 16 passed.

---

## 5. Next session pointers

### 5.1 #971 status
All four pieces (dedup + photos + admin-review + disputed-plan-gen) shipped; follow-ups A+B now shipped. **Only C remains, parked** behind a real-world signal + Andy re-confirm (see §6 decisions). If no signal surfaces, #971 is simply done.

### 5.2 Live threads (unchanged priority)
The standing **#884** (slice 6c tail — `brought_craft` column DROP after 6c-1 deploys; 6c-3 legacy retirement) and **#971** has nothing owed. **#939-blocked:** race-day-7d + share-with-crew.

### 5.3 Operating notes for next session (read order — Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (#971 carry-state item (4) now records A+B shipped / C parked)
4. This handoff (or the kickoff it extends)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

---

## 6. Decisions pinned
- **Follow-up B counts distinct *users*** (`COUNT(DISTINCT user_id)`), not locale links — the more honest blast radius (kickoff §3 gut check); one grouped query, not per-row.
- **Follow-up A suppresses "under review" when `tag in removes`** for the viewer (they disputed it themselves; the `– override` already covers it) — kickoff §2 gut check.
- **Follow-up C PARKED (Andy 2026-06-30, AskUserQuestion).** Keep lazy invalidation; do not build proactive cross-inheritor eviction until a real "stale disputed tag in a live plan" complaint appears (reverses the ratified lazy decision = stop-and-ask trigger #3). The admin approve path also relies on lazy fan-out — pre-existing, consistent, in C's scope if ever built.

---

## 7. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `disputed = locations.disputed_equipment_tags(db, shared['id'])` + `disputed=disputed` render arg in `_edit_locale` | ✅ `routes/locales.py` |
| `inheritor_count` via grouped `COUNT(DISTINCT user_id)` in `_list_pending_profile_edits` | ✅ `routes/locales.py` |
| "under review" `chip warn` with `tag in disputed and tag not in removes` | ✅ `templates/locales/form.html` |
| `{{ p.inheritor_count }} inheritor(s)` chip (warn at ≥10) | ✅ `templates/admin/gym_profile_edits.html` |
| New tests: inheritor-count / under-review chip + suppression / admin inheritor chip | ✅ 3 test files |
| Full suite 3961 passed / 30 skipped | ✅ pytest |
| Bookkeeping (`CURRENT_STATE.md` + `CARRY_FORWARD.md` + this handoff) committed with the slice | ✅ git |

---

## 8. Files shipped this session
- `routes/locales.py` (modified)
- `templates/locales/form.html` (modified)
- `templates/admin/gym_profile_edits.html` (modified)
- `tests/test_locales.py` / `tests/test_redesign_locales_form_render.py` / `tests/test_redesign_admin_render.py` (modified)
- Bookkeeping: `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
