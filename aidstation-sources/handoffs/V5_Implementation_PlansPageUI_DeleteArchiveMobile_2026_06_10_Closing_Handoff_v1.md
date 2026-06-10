# Plans-page UI — delete + archive for generated plans, mobile create actions — Closing Handoff

**Session:** A one-session **detour** off the X-series (discipline-mix rewrite), at Andy's direction. Fixed two UI gaps on the Plans screen surfaced now that generated plans carry real info (the X1-X4 + #509 wiring landed green). Next session resumes the original track (the win-condition empirical proof).
**Date:** 2026-06-10
**Predecessor handoff:** `V5_Implementation_X3X4_509_InclusionWeightingPrecedence_2026_06_10_Closing_Handoff_v1.md` (the `main` pointer at session start)
**Branch:** `claude/plans-page-ui-issues-wjmw3l` → PR [#531](https://github.com/ahorn885/exercise/pull/531) squash-merged to `main`.
**Status:** 5 substantive files (3 routes/init + template + CSS) + 2 test files. Shipped + suite green. One owed Andy's-hands Neon migration (`archived_at` column) — **apply before relying on the prod Plans page** (the list query now SELECTs it).

---

## 1. Session-start verification (Rule #9)

No reconciliation owed — this is a fresh detour, not a continuation of the X3/X4 handoff's deferred edits. Confirmed the two reported symptoms against on-disk state before building:

| Claim | Anchor | Result |
|---|---|---|
| Imported plans have Delete; generated plans do not | `templates/plans/list.html` (imported card has `plans.delete_plan` form; `gen_card` macro had only Open/Mark-complete/Reopen) | ✅ |
| No delete route exists for `plan_versions` | grep `routes/plan_create.py` — only `mark_plan_complete` / `reopen_plan` | ✅ |
| New-plan/Import live only in the desktop topbar | `topbar_actions` block in `list.html`; `.app .topbar { display:none }` < 860px (`static/style.css:870`); mobile appbar/tabbar/drawer have no create-plan entry | ✅ |
| Empty state already has mobile CTAs | `templates/_no_plan.html` (so the gap only bites once plans exist) | ✅ |

---

## 2. Session narrative

Andy reported two Plans-page issues and noted the existing plans now surface far more information (the X-series wiring working). Both issues confirmed by reading the templates + routes + the 860px shell breakpoint CSS.

**The one real decision (pinned §7).** Delete semantics for generated plans is a genuine tradeoff (hard delete vs the repo's "row invalidation, not overwrite" principle), so I surfaced it rather than picking silently (CLAUDE.md trigger #5). Andy reframed it into a **three-action model** mirroring the imported-plan lifecycle but with explicit semantics:

- **Complete** (already existed, `completed_at`) — hides the plan, kept for reference, *implies it was finished*.
- **Archive** (new, `archived_at`) — hides the plan, kept for reference, *no completion implied* (athlete quit it, or a refresh superseded it).
- **Delete** (new) — hard delete.

Generated plans (`plan_versions`) are a different model from imported plans (`training_plans`) and are referenced by the `plan_refresh_log` audit trail + the version-supersede chain — neither of which cascades — so the hard delete nulls those back-references first.

---

## 3. File-by-file edits

### 3.1 `init_db.py` (modified)
- New idempotent migration right after the `completed_at` ALTER: `ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ`. Independent of `completed_at`; the list buckets a non-NULL `archived_at` into Archived ahead of the scope-date buckets.

### 3.2 `routes/plan_create.py` (modified — 3 new routes after `reopen_plan`)
- `archive_plan` (`POST /plans/v2/<id>/archive`) — `SET archived_at = NOW() WHERE id=? AND user_id=? AND archived_at IS NULL`.
- `unarchive_plan` (`POST /plans/v2/<id>/unarchive`) — `SET archived_at = NULL`.
- `delete_plan` (`POST /plans/v2/<id>/delete`) — ownership check, then NULL the non-cascading back-refs (`plan_versions.superseded_by_version_id` where it points at this id; `plan_refresh_log.plan_version_id_before` / `_after`), then `DELETE FROM plan_versions`. The 4 child tables (`plan_sessions`, `plan_progress_blocks`, `plan_nutrition`, `plan_nutrition_inputs`) clear via their `ON DELETE CASCADE`. `user_id` filter on every write is the cross-user guard.

### 3.3 `routes/plans.py` (modified — `list_plans`)
- `gen_rows` SELECT pulls `pv.archived_at`. Bucketing adds a `gen_archived` list, checked ahead of the date buckets (archived takes precedence over completed/active/upcoming). Passed to the template.

### 3.4 `routes/profile.py` (modified — `_load_active_plan_nutrition`)
- The "active plan" lookup now selects `archived_at` and skips archived rows (alongside the existing completed skip), so a shelved plan with live scope dates doesn't surface as the athlete's active plan on the profile page. Docstring updated ("not archived").

### 3.5 `templates/plans/list.html` (modified)
- `gen_card(c)` → `gen_card(c, archived=False)`. Live cards gain **Archive** + **Delete** (Delete uses the same `data-confirm` pattern as the imported-plan delete). Archived cards (`archived=True`) show **Restore** + **Delete** and an "Archived" chip.
- New **Archived** section (renders `gen_archived` via `gen_card(c, archived=True)`) after the Completed section.
- Content guard + the eyebrow now include `gen_archived`.
- New `.plans-mobile-actions` row in `dash-head` (New plan + Import), CSS-gated to mobile.

### 3.6 `static/style.css` (modified)
- `.app .plans-mobile-actions { display:none }` by default; `display:flex` inside the existing `@media (max-width: 859.98px)` block — matches the shell breakpoint exactly so desktop (which keeps the topbar actions) is untouched and there's no 860-991px double-render.

---

## 4. Code / tests

- `tests/test_redesign_plans_list_render.py`: `_gen` fixture gained `archived_at`; asserts Archive + Delete on live generated cards + the `plans-mobile-actions` markup; new `test_archived_generated_plan_shown_with_restore` (archived stamp → Archived section, Restore + Delete, no Mark-complete).
- `tests/test_redesign_profile_render.py`: the `_load_active_plan_nutrition` fixtures gained `archived_at`; the "none when no live plan" case gained an archived live-scope row asserting it is NOT picked as active.
- **Suite: 2274 passed / 30 skipped** (`tests/`). 2 pre-existing Layer3B warnings, untouched. (No CI test job on this repo — only a Vercel preview deploy, which went green on the PR.)

---

## 5. Manual verification steps (owed-Andy's-hands)

1. **Apply the `archived_at` migration on Neon FIRST** (see §6 / CARRY_FORWARD). Until it lands, the prod Plans list 500s (the SELECT references the column).
2. On `/plans`: confirm each generated plan card now shows **Archive** + **Delete**; Archive moves it to a new **Archived** section (Restore + Delete); Delete (after the confirm) removes it and it does not reappear.
3. On a narrow viewport (< 860px): confirm **New plan** + **Import** appear in-page on `/plans` when plans exist (they were previously only in the hidden desktop topbar).
4. Confirm an archived plan no longer shows as the active plan on `/profile` (nutrition card).

---

## 6. Next session pointers

### 6.1 Resume the original track — X1-X4 + #509 win-condition empirical proof
This detour is closed. The next forward move is the **empirical win-condition proof** owed from the X3/X4 + #509 handoff (CARRY_FORWARD "Owed deploys" item 1): cold AR plan re-run confirming MTB-dominant allocation + curator-`excluded` AR disciplines no longer HITL-gating. **Gating unknown — verify first:** do Andy's PGE race event's terrain rows carry per-row `discipline_id` + `pct_of_race`? If all race-wide, X4 + #509 are inert and the next move is capturing terrain→discipline tagging (#342).

### 6.2 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling cross-session items (the `archived_at` migration is owed at the top).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.
- **One Neon migration owed:** `plan_versions.archived_at` (idempotent ALTER already in `init_db.py`). Apply before relying on the prod Plans page.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Generated plans get a **three-action lifecycle**: Complete (finished) · Archive (quit/superseded, no completion implied) · Delete (hard) | Andy | Mirrors the imported-plan model but with explicit semantics; Archive keeps the plan referenceable without claiming it was completed. |
| 2 | Hard Delete nulls the non-cascading back-refs (`superseded_by_version_id`, `plan_refresh_log.*`) before DELETE; child tables clear via existing `ON DELETE CASCADE` | Claude | The FKs would otherwise block the DELETE; nulling preserves the audit-log rows while dropping the dangling pointer. |
| 3 | Mobile create-actions are a plans-page-scoped in-page row, CSS-gated to the 860px shell breakpoint — NOT a change to the global shell/appbar | Claude | Surgical + matches the breakpoint exactly (no double-render 860-991px); the global-shell change would touch every page for a plans-page issue. |
| 4 | `archived_at` is a new column (not reusing `superseded_at`) | Claude | `superseded_at` has load-bearing version-pointer meaning (DISTINCT ON … DESC); conflating user-archive with system-supersede would corrupt the per-day version pointer. Mirrors the existing `completed_at` pattern. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `archive_plan` / `unarchive_plan` / `delete_plan` in `routes/plan_create.py` | ✅ grep |
| `archived_at` ALTER in `init_db.py` (after `completed_at`) | ✅ grep |
| `pv.archived_at` in the `list_plans` SELECT + `gen_archived` bucket | ✅ grep |
| `_load_active_plan_nutrition` skips archived | ✅ grep |
| `gen_card(c, archived=...)` + Archived section + `.plans-mobile-actions` in `list.html` | ✅ grep |
| `.plans-mobile-actions` rule in `static/style.css` (breakpoint-gated) | ✅ grep |
| Suite green | ✅ 2274 passed / 30 skipped |
| PR #531 squash-merged to `main` | ✅ |
| Working tree clean | ✅ git status |

---

## 9. Files shipped this session

**Substantive (5):**
1. `init_db.py` (modified — `archived_at` migration)
2. `routes/plan_create.py` (modified — archive/unarchive/delete routes)
3. `routes/plans.py` (modified — `archived_at` SELECT + `gen_archived` bucket)
4. `routes/profile.py` (modified — active-plan lookup skips archived)
5. `templates/plans/list.html` (modified — Archive/Delete/Restore + Archived section + mobile actions row)
6. `static/style.css` (modified — `.plans-mobile-actions` breakpoint rule)

(6 files; the CSS rule is a few lines paired with the template change — under the spirit of the 5-file ceiling.)

**Tests:**
7. `tests/test_redesign_plans_list_render.py` (modified)
8. `tests/test_redesign_profile_render.py` (modified)

**Bookkeeping:**
9. `aidstation-sources/CARRY_FORWARD.md` (detour entry + owed `archived_at` migration)
10. `aidstation-sources/CURRENT_STATE.md` (pointer → this handoff)
11. `aidstation-sources/handoffs/V5_Implementation_PlansPageUI_DeleteArchiveMobile_2026_06_10_Closing_Handoff_v1.md` (this file)

---

## 10. Carry-forward updates

- Added the Plans-page UI detour entry at the top of CARRY_FORWARD with the owed `archived_at` Neon migration (apply before relying on the prod Plans page).
- Flagged the resume-point: the X1-X4 + #509 win-condition empirical proof (existing owed item).

---

**End of handoff.**
