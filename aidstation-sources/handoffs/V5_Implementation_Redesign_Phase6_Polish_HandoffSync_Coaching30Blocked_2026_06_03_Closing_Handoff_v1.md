# V5 Implementation — Redesign Phase 6 Polish (§26–§29) + HANDOFF Build-Status Sync + §30 coaching_bp BLOCKED — Closing Handoff

**Session:** Redesign track. Brought `docs/redesign/HANDOFF.md` current with `BUILD_TASKS.md`, investigated the Phase 7 §30 `coaching_bp` retirement (found it blocked, documented why), then shipped the four remaining Phase 6 polish sections — §27 error states, §28 light mode, §29 a11y sweep, §26 shared empty-state. One PR (#412), squash-merged to `main`.
**Date:** 2026-06-03
**Predecessor handoff:** `V5_Implementation_DiagAuthGateFix_ComplianceIssueTree_Plan48_504Triage_2026_05_31_Closing_Handoff_v1.md`
**Branch:** `claude/live-tracker-design-handoff-5A9HS`
**Status:** PR #412 — 18 files (+681/−51), 10 commits, `mergeable_state: clean`, Vercel preview green. Redesign + auth render suites green (59); `app.js` syntax-checks; CSS braces balanced (817/817).

---

## 1. Session-start verification (Rule #9)

This session is on the **redesign track** (`docs/redesign/` + the v1 app shell/UI), orthogonal to the predecessor's plan-gen/Layer-4 chain, so the predecessor's §8 plan-gen anchors weren't the relevant target. The verification that mattered here was reconciling the **redesign trackers against on-disk code**:

| Claim | Anchor | Result |
|---|---|---|
| `HEAD` == `origin/main` (local `main` ref stale) | `git rev-parse HEAD origin/main` | ✅ both `5b545d1` |
| `BUILD_TASKS.md` current through Phase 6 locales/rx | read; commits #410/#411 + §21–25 present | ✅ |
| `HANDOFF.md` §0/§11 stale at Phase 3 | grep "Next: Phase 4", "Phases 0–2 + §04" | ✅ confirmed stale → fixed |
| §30 premise ("two routes, one job") | read `routes/coaching.py` + `routes/plan_refresh.py` + refs | ❌ false — see §2 |

**Reconciliation note:** clean on the redesign track. The plan-gen chain was untouched this session (no Layer-0–5 / `routes/plan_*` logic changes).

---

## 2. Session narrative

1. **HANDOFF sync.** `HANDOFF.md` §0 build-status + §11 implementation log had drifted (stopped at Phase 3) while `BUILD_TASKS.md` was current through Phase 6. Brought HANDOFF level (Phase 4 & 5 COMPLETE, Phase 6 in progress; §0 "Next" repointed; §8 line corrected).
2. **§30 `coaching_bp` — picked it, found it blocked.** The doc said retire `coaching_bp` as a duplicate of `plan_refresh_bp`. Code says otherwise: `coaching_bp` (`/coaching`) runs on the **legacy `training_plans`/`plan_items`** model; `plan_refresh_bp` (`/plans/v2/refresh`) on the **modern `plan_versions`** model — the two parallel models from `PLAN_REVIEW_AND_CORRECTIONS.md`. `coaching_bp` is **load-bearing for the already-shipped §06 plan view** (`plans/view.html`: AI Review → `coaching.review`, coach-chat → `coaching.chat`, `coaching.clarify`) and owns chat/preferences/clarify/context surfaces `plan_refresh` has no equivalent for. A literal `rm routes/coaching.py` would break a live screen. Stop-and-ask (Trigger #5): Andy chose **defer + document the blocker**. Recorded across `BUILD_TASKS.md` Phase 7 + `HANDOFF.md` §8/§9/§30. No code touched.
3. **§27 → §28 → §29 → §26**, one slice per PR-commit pair (slice + tracker bump), each with a render test, each Vercel-green before the next.

---

## 3. File-by-file edits

### 3.1 `templates/_error.html` (new) — §27
Standalone (does **not** extend `base.html`) `.app`-themed error page so a 500 can't cascade while rendering its own page. Tone glyph + eyebrow code + title + message + optional way-back quicklinks + per-request diagnostic block + pre-filled `mailto:help@aidstation.pro`.

### 3.2 `app.py` (modified) — §27
Added `@errorhandler(404)` "You're off trail." + `@errorhandler(500)` "Something seized up." after the existing `CSRFError` handler. The 500 handler logs the real exception server-side keyed by the user-visible `request_id`; the exception text never reaches the page. New imports: `datetime`, `urllib.parse.quote`, `render_template`.

### 3.3 `templates/base.html` (modified) — §28
Nonced `<head>` pre-paint bootstrap: reads `localStorage['aidstation-theme']`, adds `.theme-light` to `<html>` before first paint (no FOUC). CSP-clean.

### 3.4 `static/tokens.css` (modified) — §28
Fixed the dead global-toggle selector `body.theme-light .app` (the shell `<body>` **is** `.app`, so a descendant combinator never matched it) → `.theme-light .app`.

### 3.5 `templates/_shell/topbar.html` + `mobile_drawer.html` (modified) — §28
`[data-theme-toggle]` sun-icon button (topbar) + "Light mode" row (drawer).

### 3.6 `static/app.js` (modified) — §28 + §29
§28: theme-toggle module (flip `.theme-light` on `<html>`, persist, sync `aria-pressed`). §29: roving-tab-order controller over `[data-roving]` nav containers (sidebar vertical / tab bar horizontal) — one tab stop each, arrows move, Home/End jump, initial stop = `aria-current`.

### 3.7 `templates/_shell/sidebar.html` + `mobile_tabbar.html` + `_nav_macros.html` (modified) — §29
Roving containers + `[data-roving-item]` markers; relocated the **Primary** landmark label off the `<aside>` (complementary) onto the inner `<nav class="sidebar-nav">` (the actual navigation landmark).

### 3.8 `static/style.css` (modified) — §27 + §28
§27 `.error-*` block; §28 toggle-control affordances + a `<button>.drawer-item` reset. Braces balanced (817/817).

### 3.9 `templates/_no_plan.html` (new) + `templates/plans/list.html` (modified) — §26
Extracted the "You're at the start line." block to a shared partial (single source); `plans/list.html` now `{% include %}`s it — byte-identical render.

---

## 4. Code / tests

Three new render tests (boot the real app, fake DB, assert structure + CSP-cleanliness):
- `tests/test_redesign_error_render.py` (2: 404 + 500 — copy, diagnostic, mailto, quicklinks/retry).
- `tests/test_redesign_theme_toggle_render.py` (1: pre-paint bootstrap + both toggles + default pressed-state).
- `tests/test_redesign_a11y_render.py` (1: roving containers + item markers + relocated Primary `<nav>` label + `aria-current`).
§26 reused the existing `test_redesign_plans_list_render.py` (output is byte-identical). Redesign + auth-gate sweep: **59 green**.

---

## 5. Manual §5.0 verification steps

Render-tested only; worth a manual smoke on Vercel after the merge deploy:
1. Hit a bad URL while logged in → "You're off trail." 404 with way-back cards + a working `mailto:`.
2. Toggle light mode (topbar sun / drawer row) → whole app repaints; reload → theme persists, no dark flash.
3. Keyboard: Tab to the sidebar → it's one stop; ↓/↑ move between items, Home/End jump; Enter follows the link.
4. (Can't easily force a real 500 in prod safely — leave the 500 page to the render test unless a genuine error surfaces.)

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
Redesign Phase 6 core (§26–§29) is **done**; the core surface map is fully on the new shell. Per the 4-tier order, the next redesign work is **tier-3 finish-the-open**: the remaining operator `base_legacy.html` forms (garmin import/sync/wellness + admin `plan_inspect`/`plan_diag`) and the optional print stylesheets (design says "confirm scope"). None are launch blockers.

### 6.2 Alternative pivots
Return to the **plan-gen go-live board** (the predecessor's thread: #350/#316 latency + the §14 coherence read), which is the higher-priority tier-2 track. **§30 / Phase 7** (`coaching_bp` retirement) stays blocked until the `training_plans` ↔ `plan_versions` models unify — and that unification is the same prerequisite as the parked "Plan-refresh surface redesign" track in `CARRY_FORWARD.md`.

### 6.3 Operating notes for next session
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — what just shipped + focus. 3. `CARRY_FORWARD.md` — rolling items. 4. This handoff. 5. `./scripts/verify-handoff.sh` — anchor sweep. Redesign build rules: `docs/redesign/CONVENTIONS.md`; live tracker: `docs/redesign/BUILD_TASKS.md`; design handoff: `docs/redesign/HANDOFF.md`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Defer §30 `coaching_bp` retirement; document the blocker | Andy | Code-verified the "two routes, one job" premise is false — `coaching_bp` runs on the legacy plan model and backs the live §06 plan view; retirement needs the two plan models unified first. |
| 2 | Error page is standalone (no `base.html` shell) | Claude (noted) | A 500 must not cascade into a second failure while rendering its own error page; mirrors `auth/_shell.html`. |
| 3 | Light-mode class on `<html>` via nonced pre-paint | Claude (noted) | FOUC-free; CSP-clean. Fixed the dead `body.theme-light .app` selector en route. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `templates/_error.html` exists, standalone (no `{% extends %}`) | ✅ |
| `app.py` has `@app.errorhandler(404)` + `(500)` | ✅ grep |
| `.theme-light .app` selector live; dead `body.theme-light .app` gone | ✅ grep `static/tokens.css` |
| `[data-roving]` + `[data-roving-item]` in shell partials | ✅ grep |
| `templates/_no_plan.html` exists; `plans/list.html` includes it | ✅ grep |
| 3 new tests present; redesign+auth sweep green (59) | ✅ pytest (throwaway venv) |
| CSS braces balanced (817/817) | ✅ |
| Working tree clean after push | ✅ git status |

---

## 9. Files shipped this session

**Substantive (redesign UI/code):**
1. `templates/_error.html` (new, §27)
2. `app.py` (404/500 handlers, §27)
3. `static/style.css` (§27 + §28 blocks)
4. `static/tokens.css` + `templates/base.html` + `templates/_shell/topbar.html` + `mobile_drawer.html` (§28 toggle)
5. `static/app.js` (§28 theme + §29 roving)
6. `templates/_shell/sidebar.html` + `mobile_tabbar.html` + `_nav_macros.html` (§29)
7. `templates/_no_plan.html` (new) + `templates/plans/list.html` (§26)
8. `tests/test_redesign_{error,theme_toggle,a11y}_render.py` (3 new)

*(Multi-slice session; exceeded the 5-substantive-file guideline, but shipped incrementally as four independent slices each with its own test and green CI — quality held.)*

**Bookkeeping:** `docs/redesign/BUILD_TASKS.md`, `docs/redesign/HANDOFF.md`, `aidstation-sources/CURRENT_STATE.md`, `aidstation-sources/CARRY_FORWARD.md`, this handoff.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md`: cross-referenced the §30 code-verified finding onto the existing "Plan-refresh surface redesign (parked track)" item — `coaching_bp` can't be retired until the `training_plans` ↔ `plan_versions` models unify (same prerequisite as that parked track), and it backs the live §06 plan view. Noted redesign Phase 6 (§26–§29) shipped via PR #412 with **no owed deploys / no migration**.

---

**End of handoff.**
