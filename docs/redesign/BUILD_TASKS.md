# AIDSTATION PRO — Build Task Checklist

Per-section map: each redesign section (01–31) → the real Flask blueprint(s) + template(s) it migrates into, with notes.
Work top-to-bottom **within a phase** (phases defined in `BUILD_PLAN.md` §3). Check the box when the PR lands and the screen meets the Definition of Done (`BUILD_PLAN.md` §8).

**Legend:** `D` = desktop artboard exists · `M` = mobile artboard exists · ★ = new surface (no current template) · ⟳ = route/IA change, not just a reskin.

---

## Phase 0 — Foundation  ✅ DONE (PR #398, merged 2026-05-31)
- [x] Port `redesign/tokens.css` → `static/tokens.css`; link in shell. *(Ported **`.app`-scoped**, not verbatim — see Build status below. Linked in `base.html` after Bootstrap, before `style.css`.)*
- [x] Fold `redesign/polish.css` into `static/style.css` (focus rings, reduced-motion, print, forced-colors, light override, skip-link). *(All `.app`-scoped; `board-light`→`body.theme-light`; canvas-only `#theme-toggle`/`.dc-artboard`/`.focus-demo` dropped.)*
- [x] Build SVG icon sprite (`templates/_shell/icons.svg`) from `shell.jsx` `I` set → `<symbol id="i-home">…`. *(34 icons; included invisibly via `.sprite-host` — CSP-clean.)*
- [x] Set `CSP_REPORT_ONLY=1` in dev env. Document the flag in README. *(Documented in `DEV_SETUP.md`; entry already in `.env.example`.)*

## Phase 1 — App shell  ◀ FIRST SLICE
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| — | **Desktop shell** | D | (all) | `base.html` | New grouped **sidebar** + **top bar**. Copy current `base.html`→`base_legacy.html`. Nav map = `BUILD_PLAN.md` §5. Active state from `request.endpoint`/`nav_active`. |
| — | **Mobile shell** | M | (all) | `base.html` | 5-tab bottom bar (Today·Plan·Log[FAB]·Stats·Athlete) + overflow drawer. Same template, responsive. |
| — | **User chip / sign-out** | DM | `auth.logout`, `profile.edit`, `admin.dashboard` | base nav | Keep POST+csrf sign-out. Admin link gated `current_user.id == 1`. |
| 05 | Dashboard (proof screen) | DM | `dashboard.index` | `dashboard.html` | Render on new shell as the Phase-1 proof; full redesign in Phase 2. |

## Phase 2 — Daily loop
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| 05 | Dashboard · Today | DM | `dashboard.index` | `dashboard.html` | Hero = next workout. Skeleton/loading state TBD (HANDOFF §8 — confirm if wanted). |
| 06 | Training plan · week | DM | `plans.list_plans` / plan view | `plans/v2/*` | Week grid. No-plan → shared empty (§26). |
| 07 | Workout detail | DM | `training.session_form` / plan workout + `garmin` upload | `training/session_form.html` | "Upload completed .FIT" (not push). Rest-day variant. |
| 08 | Logging · adaptive form ⟳ | DM | `natural_log` + `cardio`/`training`/`body`/`conditions`/`injuries`/`wellness` `.new_entry` | `cardio/form.html`, `training/form.html`, `body/form.html`, `conditions/form.html`, `injuries/form.html` | **One landing, type picker swaps pane.** Six routes stay; UX is unified. Shared `onboarding/_skills_form.html` partial stays shared. |
| 09 | Wellness | DM | `wellness.index` | `wellness/index.html` | 30-day readiness. Absorbs the old Wellness→.FIT import (now in Connections §17). |

## Phase 3 — Plan lifecycle
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| 04 | Plan generation | DM | `plan_create.new_plan` / `.progress` / `.view` | `plan_create/{new_form,progress,view}.html` | Cup-pour progress = time bucket, **not** server sub-steps. Keyframes in `tokens.css`. |
| 10 | Races · event manager ★ | DM | `race_events.*` | — (no template) | A/B/C priority; editing a date re-cascades the plan. New templates. |
| 11 | Plans · history & versions | DM | `plans.list_plans` | `plans/v2/*` | Zero-plans → shared empty (§26). |
| 12 | Plan compare · diff | DM | `plans.*` (version compare) | `plans/v2/*` | Version A ↔ B diff. |
| 13 | Plan refresh ⟳ | DM | `plan_refresh.*` | — | Adapt to new context. **See §30 — consolidate with `coaching_bp`.** |
| 14 | Plan import | DM | `plans.import_plan` | `plans/import.html` | JSON paste. |

## Phase 4 — Library + Account
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| 15 | Exercises library | DM | `rx.list_entries` | `rx/list.html` | "Exercises" = `rx`. No-Rx empty state. |
| 16 | Locations | DM | `locales.list_profiles` / `.form` | `locales/{list,form}.html` | UX copy "Locations"; route stays `locales`. Empty state. |
| 17 | **Connections · hub** ★⟳ | DM | `garmin.dashboard` + `garmin.debug_fit` + provider bps (`strava`/`coros`/`polar`/`whoop`/`zwift`/`trainingpeaks`/`ride_with_gps`/`oauth_callbacks`) | `garmin/{dashboard,debug_fit}.html` | **4 surfaces → 1 hub.** Tabs: Sources / Files (FIT inspector = inline panel) / Preferences + empty. Garmin = PAUSED. **Hard-cut old URLs** (single user, no redirects). Kill "Garmin dashboard" phrasing. |
| 18 | Athlete profile | DM | `profile.edit` | `profile/edit.html` | Day-1 first-run state. Connections/dedupe prefs **move out** to §17. |
| 19 | **Account settings** ★ | DM | `profile.change_password`, `auth.logout` | (part of `profile/edit.html`) | Identity + change password + sign out. **No** billing/2FA/export/delete. |
| 20 | **Coach memory** ★ | DM | `profile.add_preference` / `.delete_preference` | — | Durable AI-coach prefs w/ `fb_source` provenance (chat/plan_review/natural_log/workout_note/manual). Each deletable; some permanent. |

## Phase 5 — System
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| 21 | Notifications & feed ★ | DM | `nudges.*` | `_account_nudges.html` (partial) | Full feed + dropdown + deep-link route map. Backed by `account_nudges`. |
| 22 | Notification settings ★ | DM | `nudges.*` / `profile` | — | Channel × category matrix. |
| 23 | Command palette · ⌘K | DM | client-only | `static/app.js` | Jump-to-anything. No route; nonced JS + `data-*`. |
| 24 | Keyboard shortcuts | D | client-only | `static/app.js` | Cheat sheet overlay. |
| 25 | **Admin** ★ (desktop-only) | D | `admin.*` (+ `admin.audit`) | `admin/dashboard.html` | Users · drill-in detail · type-to-confirm **Delete user** (cascades 25 tables) · Audit log · System telemetry. Dialog needs focus trap (§29). |

## Phase 6 — States + Polish
| § | Section | DM | Where | Migration note |
|---|---|---|---|---|
| 26 | Empty / first-run states ⟳ | DM | shared partial | **One** "You're at the start line." component reused across Dashboard/Plan/Plans-list (replaces 3 divergent headlines). |
| 27 | Error states | DM | Flask `errorhandler` + shared `templates/_error.html` | 404 "You're off trail." · plan-gen "The build stalled." · 500 "Something seized up." Diagnostic block + `mailto:help@aidstation.pro`. |
| 28 | Light mode | DM | body theme class + token swap | Already token-ready. Wire a real toggle (persist in localStorage); no per-screen CSS. |
| 29 | A11y / keyboard / motion | D | real components + `app.js` | **Port `a11y-wire.js` logic onto real elements.** Roving tab-order on nav/tabbar, `aria-current`, focus trap+restore on delete-user dialog, `role`/`aria-*` on tablists. Flip CSP REPORT_ONLY **off** and clear violations. |
| — | Print stylesheets (opt.) | — | `style.css @media print` | Plan week / workout / race-day brief. CSS hooks exist in polish. Confirm scope. |

## Phase 7 — Backend cleanup (HANDOFF §30)
- [ ] **Retire `coaching_bp`.** `plan_refresh_bp` and `coaching_bp` register routes doing the same job (re-run cascade vs existing plan). Fold `coaching/review`'s richer inputs into `plan_refresh`. Remove `routes/coaching.py` + `templates/coaching/`. Update nav + any deep links. Remove `app.register_blueprint(coaching_bp)`.

---

## Coverage notes — routes NOT in the redesign (decisions)
The redesign covers every *user-facing* surface but a few blueprints have no redesigned screen:
- `purchases` (Recommended purchases) — **KEEP.** Dropped from primary nav for now; design a proper screen later. Leave the route working; reachable via a secondary link (e.g. Athlete or a "Gear" sub-item) until then.
- `references` — **No template found in the import and no nav entry.** Likely a data/utility route (or unused). **Action for Claude Code:** open `routes/references.py` in the repo, confirm whether it renders any page; if it's data-only or dead, leave it untouched (don't surface in nav). Don't build a screen for it without confirming it's user-facing.
- `ad_hoc_workouts` — folded into Workouts/Logging? Confirm against `routes/ad_hoc_workouts.py` in the repo.
- Per-provider blueprints (`coros`/`polar`/`strava`/`whoop`/`zwift`/`trainingpeaks`/`ride_with_gps`) — their **settings UI** consolidates into Connections §17; their **webhooks stay** (CSP-exempt, unchanged).
- `status.status` — health probe, no UI. Leave as-is.

## Cross-cutting, every phase
- CSP: nonce every inline script/style; widths via `data-progress` + `app.js`. REPORT_ONLY on during build, **off** at each screen's done.
- Both shells render identical context (`current_user`, `active_nudges`, flashes, csrf, csp_nonce).
- One responsive template per screen — no separate mobile files.
- Token classes only; light mode is a free token-swap if you stay disciplined.

---

## Build status / handoff (live)

**Last updated:** 2026-05-31

### Done
- **Pre-build review** — `PLAN_REVIEW_AND_CORRECTIONS.md` (PR #397, merged). Code-verified
  corrections to these docs: the token-collision reality, the §22 backend gap, endpoint-name
  drift, the two parallel plan models (`training_plans` vs `plan_versions`), and the resolved
  `references`/`ad_hoc_workouts` coverage questions.
- **Phase 0 — Foundation** (PR #398, merged). `static/tokens.css` + polish layer + 34-icon
  sprite, **all namespaced under `.app`** so legacy screens render unchanged. Verified
  statically (Jinja compiles, CSS braces balanced, zero unscoped selectors, no inline
  `style=`/`onclick=`). The token system goes live only where a screen adds `class="app"` —
  which begins in Phase 1.
- **Phase 1 — App shell** (PR #400). New `base.html` shell (`<body class="app">`): grouped
  desktop sidebar (Train/Log/Account) + top bar (breadcrumb slot, ⌘K stub, bell) + mobile
  5-tab bottom bar + offcanvas overflow drawer. Old shell copied verbatim to `base_legacy.html`
  and all 58 legacy screens re-pointed to it; both shells render the identical Flask context.
  Nav wired with the corrected endpoint names (`PLAN_REVIEW_AND_CORRECTIONS.md` §3a). Note: a
  Jinja `{% block %}` does **not** cross an `{% include %}` — `crumbs`/`topbar_actions` are
  defined in `base.html` and handed to the topbar partial via captured `{% set %}` vars.
- **Phase 2 · §05 Dashboard · Today** (PR #400). Full redesign onto the new shell, wired to the
  real `dashboard.index` context only. Mock-only artboard widgets without backing data
  (readiness HRV/RHR, interval SVG, 4-week TSS ramp) were **not** ported; every real surface is
  (today/tomorrow/missed plan items with complete/skip/.FIT, live weather + hourly, clothing
  recs, conditions-to-log, stats strip, recent strength/cardio, plan CTAs). Layout in token
  classes under `.app` (no inline style — CSP-clean).
- **Phase 2 · §06 Plan · week** (`plans.view_plan(plan_id)` — legacy model per §3b). `plans/view.html`
  migrated to the new shell as a **7-day Mon–Sun calendar grid** (one grid per plan week). Added a
  unit-tested `_build_week_grid()` helper in `routes/plans.py` that buckets `plan_items` into 7
  weekday cells (note: the day-cell key is `workouts`, **not** `items` — `day.items` resolves to
  the dict method in Jinja). Per-workout deep detail (nutrition macros, description steps) moves to
  the workout-detail screen (§07); every plan-level function is preserved here: complete/skip/.FIT,
  bulk-edit bar, AI review, FIT-files, archive/restore/delete, plan health, daily supplements,
  injury mods, gear recs, progress, and coach chat (both nonce'd inline scripts kept; the static
  bulk-mode `<style>` moved into `style.css`).

### Known blocker (infra, not code) — Vercel **Preview** deploys 500
Preview deployments crash with `FUNCTION_INVOCATION_FAILED`: `app.py` raises at **import** when
`SECRET_KEY` is unset, and the Preview environment scope is missing it (runtime logs confirm
`could not import "app.py": …SECRET_KEY…`). **Fix (owner):** add `SECRET_KEY` and a
**Neon dev/preview-branch** `DATABASE_URL` to the Vercel project's **Preview** env scope.
Until then, PR previews can't render — verify locally or via static checks. This is unrelated
to any redesign PR (Production is unaffected).

### Next
- **Phase 2 (continue):** §06 Plan · week (`plans.view_plan(plan_id)` — legacy model per §3b),
  §07 Workout detail (`training.session_form` + `.FIT` upload), §08 Logging adaptive form
  (one landing, type picker over the six `.new_entry` routes), §09 Wellness. Migrate one
  template per slice, flipping each from `base_legacy.html` → `base.html` as it lands.
