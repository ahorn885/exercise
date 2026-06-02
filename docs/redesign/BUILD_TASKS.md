# AIDSTATION PRO — Build Task Checklist

Per-section map: each redesign section (01–31) → the real Flask blueprint(s) + template(s) it migrates into, with notes.
Work top-to-bottom **within a phase** (phases defined in `BUILD_PLAN.md` §3). Check the box when the PR lands and the screen meets the Definition of Done (`BUILD_PLAN.md` §8).

**Legend:** `D` = desktop artboard exists · `M` = mobile artboard exists · ★ = new surface (no current template) · ⟳ = route/IA change, not just a reskin · ✅ = shipped to `main`.

---

## Phase 0 — Foundation  ✅ DONE (PR #398, merged 2026-05-31)
- [x] Port `redesign/tokens.css` → `static/tokens.css`; link in shell. *(Ported **`.app`-scoped**, not verbatim — see Build status below. Linked in `base.html` after Bootstrap, before `style.css`.)*
- [x] Fold `redesign/polish.css` into `static/style.css` (focus rings, reduced-motion, print, forced-colors, light override, skip-link). *(All `.app`-scoped; `board-light`→`body.theme-light`; canvas-only `#theme-toggle`/`.dc-artboard`/`.focus-demo` dropped.)*
- [x] Build SVG icon sprite (`templates/_shell/icons.svg`) from `shell.jsx` `I` set → `<symbol id="i-home">…`. *(34 icons; included invisibly via `.sprite-host` — CSP-clean.)*
- [x] Set `CSP_REPORT_ONLY=1` in dev env. Document the flag in README. *(Documented in `DEV_SETUP.md`; entry already in `.env.example`.)*

## Phase 1 — App shell  ◀ FIRST SLICE
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| — | ✅ **Desktop shell** | D | (all) | `base.html` | New grouped **sidebar** + **top bar**. Copy current `base.html`→`base_legacy.html`. Nav map = `BUILD_PLAN.md` §5. Active state from `request.endpoint`/`nav_active`. *(PR #400)* |
| — | ✅ **Mobile shell** | M | (all) | `base.html` | 5-tab bottom bar (Today·Plan·Log[FAB]·Stats·Athlete) + overflow drawer. Same template, responsive. *(PR #400)* |
| — | ✅ **User chip / sign-out** | DM | `auth.logout`, `profile.edit`, `admin.dashboard` | base nav | Keep POST+csrf sign-out. Admin link gated `current_user.id == 1`. *(PR #400)* |
| 05 | ✅ Dashboard (proof screen) | DM | `dashboard.index` | `dashboard.html` | Render on new shell as the Phase-1 proof; full redesign in Phase 2. *(PR #400)* |

## Phase 2 — Daily loop
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| 05 | ✅ Dashboard · Today | DM | `dashboard.index` | `dashboard.html` | Hero = next workout. Live weather + hourly, plan CTAs, stats, recents. Mock-only widgets (readiness/interval/TSS) not ported. *(PR #400)* |
| 06 | ✅ Training plan · week | DM | `plans.view_plan(plan_id)` (legacy model, §3b) | `plans/view.html` | 7-day Mon–Sun calendar grid (`_build_week_grid`). Bulk-edit, coach chat, gear, supplements preserved. *(PR #401)* |
| 07 | ✅ Workout detail | DM | `plans.view_item` (+ `.FIT` up/download, garmin push) | `plans/item.html` | Targets + block-by-block + rest-day variant + context rail. "Upload completed .FIT"; inline edit/complete/skip preserved. *(PR #403)* |
| 08 | ✅ Logging · adaptive form ⟳ | DM | `natural_log` + `cardio`/`training`/`body`/`conditions`/`injuries`/`wellness` `.new_entry` | `cardio/form.html`, `training/form.html`, `body/form.html`, `conditions/form.html`, `injuries/form.html` | **One landing, type picker swaps pane.** Six routes stay; UX is unified. Strength session form migrated; Wellness tile deep-links to §09 self-report card. *(PR #407 + Strength/Wellness follow-up)* |
| 09 | ✅ Wellness | DM | `wellness.index` | `wellness/index.html` | 30-day readiness on new shell. Self-report card is the Log picker's Wellness deep-link target (`#self-report`); charts re-skinned to the dark `.app` token palette; "body battery"→"recovery" copy. |

## Phase 3 — Plan lifecycle
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| 04 | ✅ Plan generation | DM | `plan_create.new_plan` / `.progress` / `.view` | `plan_create/{new_form,progress,view}.html` | Cup-pour progress = time bucket, **not** server sub-steps. Keyframes in `tokens.css`; letters injected + positioned via JS (`element.style`, CSP-clean). Failed state uses §27 "The build stalled." copy. *(in-flight PR)* |
| 10 | ✅ Races · event manager ★ | DM | `race_events.*` | — (no template) | Standalone page under Plan: target-race spotlight + upcoming/past lists. Editing a target's date re-cascades the plan (existing eviction in `update_race`). A/B/C priority **not ported** — the schema has a single `is_target_event` boolean, not a priority column. *(this PR)* |
| 11 | ✅ Plans · history | DM | `plans.list_plans` | `plans/list.html` | Active cards (status='active' spotlight) + archived rows on the new shell; real progress via `data-progress`. Grounded in the legacy `training_plans` model — the artboard's version-history table belongs to `plan_versions`, not rendered. Zero-plans → "You're at the start line." (§26 copy). *(this PR)* |
| 12 | ◑ Plan compare · diff | DM | `plan_refresh.view_refresh` | `plans/v2/refresh_view.html` | **Diff via refresh** (refresh-vs-parent, updated/new badges) migrated. Standalone arbitrary version **A↔B compare has no backend route** — deferred to a future backend slice (don't fabricate). *(this PR)* |
| 13 | ✅ Plan refresh ⟳ | DM | `plan_refresh.refresh` | `plans/v2/refresh.html` | Horizon picker (T1/T2/T3) + current-version card + no-plan empty; Bootstrap freq-cap modal kept (nonce'd). **Still see §30 — consolidate with `coaching_bp`** (Phase 7). *(this PR)* |
| 14 | ✅ Plan import | DM | `plans.import_plan` | `plans/import.html` | JSON-paste form + token-styled schema reference. *(this PR)* |

## Phase 4 — Library + Account
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| 15 | ✅ Exercises library | DM | `rx.list_entries` | `rx/list.html` | "Exercises" = `rx`. Current Rx data-table + plateau/deload watch + real GET filters; catalog (inventory w/ no current Rx) below; No-Rx "No Rx yet." hero. *(this PR)* |
| 16 | ✅ Locations | DM | `locales.list_profiles` / `.form` | `locales/{list,form}.html` | UX copy "Locations"; route stays `locales`. Card grid (legacy enums + custom) w/ equipment chips, refresh/edit/delete; "Where do you train?" hero when nothing configured. `form.html`/`new.html` left on legacy. *(this PR)* |
| 17 | ✅ **Connections · hub** ★⟳ | DM | NEW `connections.hub` / `.inspect` (folds `garmin.dashboard`+`garmin.debug_fit`; providers via `profile.load_connections`) | NEW `connections/hub.html` | **4 surfaces → 1 hub.** Tabs: Sources (providers + Garmin PAUSED + drop zone→`garmin.import_fit`) / Files (`cardio_log` history + inline FIT inspector) / Preferences (grounded read-only behavior — no fabricated toggles). Old URLs **hard-cut**, "Garmin dashboard" phrasing gone. *(this PR)* |
| 18 | ✅ Athlete profile | DM | `profile.edit` | `profile/edit.html` | Reskinned: Athlete/Schedule/Skills sub-tabs (`?tab=`). Day-1 first-run banner. Race-events→§10, Connections→§17, Account→§19, Coach-memory→§20 split out. *(this PR)* |
| 19 | ✅ **Account settings** ★ | DM | NEW `profile.account_settings`; `profile.change_password`, `auth.logout` | NEW `profile/account.html` | Identity + change password + sign out. **No** billing/2FA/export/delete. Fixes the latent GET→POST `change_password` nav 405. *(this PR)* |
| 20 | ✅ **Coach memory** ★ | DM | NEW `profile.coach_memory`; `profile.add_preference` / `.delete_preference` | NEW `profile/coach_memory.html` | Durable AI-coach prefs w/ `fb_source` provenance (chat/plan_review/natural_log/workout_note/manual). Each deletable; some permanent. *(this PR)* |

## Phase 5 — System
| § | Section | DM | Blueprint / route | Current template | Migration note |
|---|---|---|---|---|---|
| 21 | ✅ Notifications & feed ★ | DM | `nudges.feed` (NEW `/notifications`) | `nudges/feed.html` + bell dropdown | **DONE.** New `nudges.feed` over `account_nudges` (`get_feed_nudges` → New/Earlier, registry CTA deep-links, inline dismiss). Topbar bell → Bootstrap dropdown (unread badge, recent 5, "See all"); mobile drawer link. Fail-open to empty on SQLite. 2 render tests. *(PR after #410)* |
| 22 | ✅ Notification settings ★ | DM | `nudges.settings` (NEW `/notifications/settings`) | `nudges/settings.html` | **DONE (read-only).** No preference backend exists (confirmed: no settings table / channel store) — per the §17 precedent, an honest read-only page documenting the delivery model (In-app + transactional Email) + the live `NUDGE_REGISTRY` reminder list, **no fabricated toggles**. Linked from feed action + account menus. 1 render test. |
| 23 | ✅ Command palette · ⌘K | DM | client-only | `_shell/cmdk.html` + `static/app.js` | **DONE.** ⌘K/Ctrl-K opens a jump-to-anything palette; destination list is server-rendered (`url_for`, admin-gated) so it can't drift; JS only filters (type-ahead) + arrow/Enter navigates. Topbar search affordance opens it too. Nonced JS, `data-*` hooks, no inline handlers. |
| 24 | ✅ Keyboard shortcuts | D | client-only | `_shell/cmdk.html` + `static/app.js` | **DONE.** `?` opens a cheat-sheet overlay (⌘K · ? · ↑↓ · ↵ · esc). Esc/backdrop-click closes. Shares the §23 partial. 1 shell render test covers both. |
| 25 | ✅ **Admin** ★ (desktop-only) | D | `admin.*` (+ NEW `admin.user_detail`) | `admin/{dashboard,user_detail,audit,telemetry_refresh}.html` | **DONE.** Dashboard/audit/telemetry migrated off `base_legacy` → new shell. NEW `admin.user_detail` drill-in: data-footprint stat-cards (counts mirror the 25 cascaded tables) + admin-audit trail + **type-to-confirm Delete user** in a **focus-trapped dialog** (§29; submit disabled until the username is typed exactly — app.js `data-typeconfirm`). 5 render tests. `plan_inspect`/`plan_diag` stay legacy (operator deep-debug, out of §25 scope). |

## Phase 6 — States + Polish
| § | Section | DM | Where | Migration note |
|---|---|---|---|---|
| 26 | ✅ Empty / first-run states ⟳ | DM | shared partial | "You're at the start line." extracted to **`templates/_no_plan.html`** (single source). The new IA already collapsed the design's 3 divergent no-plan headlines: Plan = `plans.list_plans` (uses the partial); the dashboard's no-plan state is a purpose-built daily-hub hero ("No session scheduled"), intentionally distinct. *(this PR)* |
| 27 | ✅ Error states | DM | Flask `errorhandler` + shared `templates/_error.html` | 404 "You're off trail." (way-back quicklinks) · 500 "Something seized up." (retry) via 404/500 handlers in `app.py`. Per-request diagnostic block + `mailto:help@aidstation.pro` pre-filled. `_error.html` is **standalone** (no shell includes / no DB context) so a 500 can't cascade. Plan-gen "The build stalled." already lives inline in `plan_create/progress.html` (§04). *(this PR)* |
| 28 | ✅ Light mode | DM | body theme class + token swap | Real toggle wired (topbar sun button + drawer row, `data-theme-toggle` → `app.js`), persisted in `localStorage`; **FOUC-free** via a nonced `<head>` pre-paint that sets `.theme-light` on `<html>`. Token swap only — no per-screen CSS. Fixed the dead `body.theme-light .app` selector (`body` *is* `.app`) → `.theme-light .app`. *(this PR)* |
| 29 | ✅ A11y / keyboard / motion | D | real components + `app.js` | `a11y-wire.js` ported onto real elements: **roving tab-order** on sidebar + tab bar (`[data-roving]`/`[data-roving-item]` → `app.js`), `aria-current` (macros), focus-trap+restore on the delete-user dialog (§25), tablist/listbox roles (cmdk/§17/§25), focus-visible rings + reduced-motion (polish.css). Primary landmark relocated onto the `<nav>`. CSP already **enforced** in prod (REPORT_ONLY is a dev-only opt-in); all slices CSP-clean → no violations to clear. *(this PR)* |
| — | Print stylesheets (opt.) | — | `style.css @media print` | Plan week / workout / race-day brief. CSS hooks exist in polish. Confirm scope. |

## Phase 7 — Backend cleanup (HANDOFF §30)
- [ ] **Retire `coaching_bp`. — ⛔ BLOCKED (code-verified 2026-06-02; do NOT delete as written).** The original note assumed `plan_refresh_bp` and `coaching_bp` "do the same job." Reading the code, they don't — and a literal `rm routes/coaching.py` + `templates/coaching/` would **break an already-shipped redesign screen.** Findings:
  - **Two different, both-live plan models.** `coaching_bp` (`/coaching`) operates on the **legacy `training_plans`/`plan_items`** model; `plan_refresh_bp` (`/plans/v2/refresh`) operates on the **modern `plan_versions`** model (the two parallel models flagged in `PLAN_REVIEW_AND_CORRECTIONS.md`). Only `coaching.review` *conceptually* overlaps refresh, and even it can't fold in cleanly without **unifying the plan models** — a much larger effort that conflicts with the redesign's own decision to keep `training_plans` live (the migrated §06 week view runs on it).
  - **`coaching_bp` is load-bearing for the migrated §06 plan view (`plans/view.html`, on `main`):** the "AI Review" button → `coaching.review`; the coach-chat panel → `coaching.chat` (GET history + POST, 5 refs); `coaching.clarify` backs `coaching/review.html`.
  - **`coaching_bp` owns surfaces `plan_refresh` has no equivalent for:** `/chat`, `/preferences` (+`/preferences/<id>/delete`), `/clarify`, `/context`, headless `/api/review`. `context`/`api_review`/`delete_preference` have 0 *internal* refs but are intentional external/JSON APIs, not dead code.
  - **Unblock prerequisite:** unify the `training_plans` ↔ `plan_versions` plan models (or migrate the §06 plan view + chat/review onto `plan_versions`) *first*; only then can review fold into `plan_refresh` and chat/preferences re-home. Until that backend slice exists, keep `coaching_bp` registered. Deferred, not dropped.

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

**Last updated:** 2026-06-02

**Progress:** Phase 0 ✅ · Phase 1 shell ✅ · **Phase 2 COMPLETE** (§05–§09 ✅) · **Phase 3 COMPLETE\*** (§04 ✅ · §10 ✅ · §11 ✅ · §12 ◑ diff-via-refresh · §13 ✅ · §14 ✅) · **Phase 4 COMPLETE** (§15 ✅ · §16 ✅ · §17 ✅ · §18 ✅ · §19 ✅ · §20 ✅) · **Phase 5 COMPLETE** (§21 ✅ · §22 ✅ read-only · §23 ✅ · §24 ✅ · §25 ✅) · **Phase 6 polish — done** (§26 ✅ shared empty-state · §27 ✅ error states · §28 ✅ light-mode toggle · §29 ✅ a11y sweep) — **remaining (optional/low-priority): print stylesheets, the operator `base_legacy` forms (garmin import/sync/wellness, admin `plan_inspect`/`plan_diag`)**. *\*§12 standalone A↔B compare deferred (no backend route); §13's §30/Phase-7 `coaching_bp` consolidation is **⛔ BLOCKED** — code-verified it can't be done as written (two live plan models; `coaching_bp` backs the migrated §06 plan view). See Phase 7 above.*
Merged to `main`: PR #397 (review), #398 (Phase 0), #399 (docs), #400 (Phase 1 + §05),
#401 (§06), #403 (§07), #404 (§07 follow-up), #406 (redesign card/grid Bootstrap-leak fix),
#407 (§08 unified Log landing + 4 panes).
In flight: PR for §08 Strength pane + §09 Wellness (completes Phase 2) **and** Phase 3 §04
(plan-gen start form + cup-pour progress + plan view).

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
- **Phase 2 · §07 Workout detail** (`plans.view_item` → `plans/item.html`). The plan-workout
  detail the dashboard hero and §06 week grid link to (this is the artboard's "Today's Workout";
  the §07 note's `training.session_form` is the strength-logging form, deferred to §08). Two-column
  layout: workout body (targets strip, block-by-block step list from `description | workout_steps`,
  notes callout, **rest-day variant**) + sticky context rail. Preserves every function — inline
  edit (PATCH `api_patch_plan_item`), complete/skip with optional notes, download .FIT, Garmin
  push (auth-gated → shows **paused** when not authed) + workout-JSON details. Applies HANDOFF §4:
  adds **"Upload completed .FIT"** alongside download; per-workout detail §06 deferred now lives here.
- **Phase 2 · §07 follow-up** (PR #404, on top of #403). Closes the two gaps #403 left vs the
  §07 spec: (1) the **nutrition macros** §06 explicitly deferred to this screen — `view_item` now
  passes `_workout_nutrition(...)` and the rail gains a **Fuel & nutrition** card (carb/protein/fat
  %, daily energy, session fueling); (2) honors the **"Upload completed .FIT" (not push)** directive
  + §17 Garmin = PAUSED — the rail's "Upload completed .FIT" now targets the real importer
  (`garmin.import_fit`, was `garmin.dashboard`), and the on-screen **Garmin push card + workout-JSON
  dump are removed** (the `push_to_garmin` *route* is left intact for §17). `view_item` no longer
  fetches `garmin_workouts`/auth status. Reuses #403's class vocabulary; CSP-clean (no inline style).
- **Phase 2 · §06/§07 polish** (PR #406). Fixed a Bootstrap-leak that affected every `.app` screen:
  `.app .card` never reset `color` (inherited Bootstrap's dark `--bs-body-color`) and `.app .row`
  kept Bootstrap's gutter (negative margins + `.row > *` padding). Re-asserted `color: var(--fg)`,
  zeroed `--bs-gutter-x`, and made mobile column stacking explicit (`flex-basis: 100%`).
- **Phase 2 · §08 Logging — unified landing (partial: 4 of 6 panes).** New `log` blueprint
  (`/log` → `log.index`, redirects to the default cardio pane) + shared `log/_shell.html`
  (type-picker left rail via `log/_picker.html`, form pane right) + `log/_picker.html` (6 type
  tiles + "log via text" CTA → `natural_log.index`). The six entry **routes are unchanged**; the
  picker just navigates between them (server-rendered panes — CSP-clean, no SPA) and each form
  renders inside the shell so the picker is always present. Migrated to the shell + token CSS:
  **Cardio, Body, Conditions, Injury** (every input `name`, POST action, and field-toggle JS
  preserved; cardio bike/paddle/run toggles + injury constraint-narrowing + conditions
  indoor/session-link all intact). Nav "Quick log" (sidebar/drawer/mobile-FAB) now points at
  `log.index`. **Deferred:** the **Strength** tile links to `training.new_entry` (the 325-line
  JSON/JS session form — migrate next) and the **Wellness** tile links to `wellness.index` (the
  dashboard, owned by §09); both still land on legacy-styled pages until then. Also fixed a latent
  redesign bug surfaced here: legacy base CSS colours bare `h1–h6` with `--ink` (dark), invisible
  on the dark app theme — added `.app h1–h6 { color: var(--fg) }`, which also un-hides the §07
  workout title and the dashboard greeting. Also spaced the **dashboard's stacked blocks** (they
  were bare siblings under `.page-body` and touched with no gap) by wrapping the content in
  `.stack`. Codified both lessons in `CONVENTIONS.md §C` (vertical rhythm via `.stack`;
  Bootstrap-override gotchas for card colour / row gutter).
- **Phase 2 · §08 Strength pane + §09 Wellness — completes Phase 2.**
  - **§08 Strength.** `training/session_form.html` (`training.new_entry`) now extends
    `log/_shell.html` (`log_type='strength'`), so the type picker frames the strength
    session form like every other pane. The 325-line dynamic-row/RX-fetch JS is preserved
    verbatim; only the **injected** Bootstrap markup was re-skinned to token classes
    (`badge`→`chip`, `card mb-2`→`card card-pad ex-summary`, outline buttons→`btn-ghost`/
    `btn-mini`) and the set-log moved into a token `table.data`. Every input `name`, the
    `/training/session` JSON POST, RX target lookups, RPE/per-exercise notes, and the
    post-save **activity-FIT** card all unchanged (FIT copy is brand-neutral). New CSS:
    `.set-log*`, `.ex-summary*`, `.set-chips`, `.fit-card-row` under the §08 block.
  - **§09 Wellness.** `wellness/index.html` migrated off `base_legacy.html` onto the new
    shell (`nav_active='insights'`). Self-report entry card carries `id="self-report"`; the
    Log picker's **Wellness tile deep-links to it** (`url_for('wellness.index', _anchor=…)`)
    — resolving the §08 "decide the Wellness pane" question by folding it into §09 rather
    than duplicating the entry form. Chart.js series re-keyed from the legacy `--ink/--orange`
    palette to the redesign tokens (`--fg/--accent/--info/--good/--hairline`) so they read on
    the dark theme and re-skin for free under `body.theme-light`; charts laid out in a token
    `.chart-grid` (no Bootstrap `.row g-3`). Garmin-ism scrubbed ("body battery"→"recovery").
  - **Verified:** new `tests/test_redesign_log_wellness_render.py` boots the real app (DB
    stubbed) and renders `/training/new` + `/wellness` + the picker — asserts shell present,
    strength tile active, `#self-report` anchor, self-report field names, picker deep-link,
    and no inline `style=`/`onclick=`. Full suite green (1867 passed, 16 skipped); CSS braces
    balanced.
- **Phase 3 · §04 Plan generation** — all three `plan_create` templates onto the new shell.
  - **Start form** (`new_form.html`, `plan_create.new_plan`). "Build me a plan." — real start-date
    picker + target-race **anchor card** (or the open-plan branch when no race), an illustrative
    Base→Build→Peak→Taper phase band (clearly framed as the *typical* shape, not the generated
    plan — the mock pre-flight checklist from the artboard was **not** ported, no backing data),
    Generate / Import-JSON / Cancel actions.
  - **Progress** (`progress.html`, `plan_create.plan_progress`). The signature **cup-pour**:
    "Pouring you a plan." Honors BUILD_PLAN §9 — **time-bucket, not server sub-steps**, so the
    legacy 6-message client cycle is gone. The cup outline is inline SVG; the tumbling letters are
    **built and positioned in JS** (`element.style.setProperty('--x/--y/--r')` + per-letter
    `animation` delay) so nothing trips the CSP nonce gate — the `letterTumble`/`cupTipping`
    keyframes already shipped in `tokens.css` (Phase 0). Letters carry `.letter-tumble` so the
    existing reduced-motion rule settles them statically in the cup. **The resumable poll loop is
    preserved verbatim** (consecutive-failure cap, cache-resume on 5xx, CSRF from the meta tag).
    Failed state adopts the §27 **"The build stalled."** headline + Retry.
  - **View** (`view.html`, `plan_create.view_plan`). Generated plan grouped by date with phase-seam
    headers (phase · week-in-phase · volume band) and per-session cards (discipline · duration ·
    intensity chip · coaching intent · notes), rest-day variant kept.
  - New `.app` CSS under a **§04** block (`.plan-gen*`, `.phase-band`, `.gen-cup*`, `.gen-letter`,
    plan-view atoms). **Verified:** render tests extended to cover all three screens (start form,
    cup-pour wired + no message-cycle + stalled copy, plan view with a phase-seam session). Full
    suite green (1870 passed, 16 skipped); CSS braces balanced; zero inline `style=`/handlers.
- **Phase 3 · §10 Races · event manager** — new standalone page promoting the race calendar
  out of the buried `/profile?tab=race-events` tab into a first-class surface under **Plan**.
  - **New route** `race_events.index` (`GET /profile/race-events/`) + template
    `templates/profile/race_events.html` on the new shell (`nav_active='races'`). Buckets the
    `list_athlete_race_events` rows into **target / upcoming / past** (event_date vs today,
    weeks-out computed in the route via a `_coerce_event_date` helper that handles both the
    Postgres `date` and the SQLite ISO-string shapes). Past list reads most-recent-first.
  - **Target spotlight** = the `is_target_event` row (accent-bordered card, weeks-out, an
    illustrative Base→Build→Peak→Taper `.phase-band` framed as the *typical* shape — same
    grounding discipline as §04). The mockup's **A/B/C priority was NOT ported**: the schema
    has a single `is_target_event` boolean, no priority column — inventing one would be
    ungrounded. Upcoming/past rows reuse the existing **set-target / edit / delete** POST
    handlers; `_tab_redirect()` now lands on the new manager instead of the profile tab.
  - **Nav:** added a **Races** item (icon `i-shoe`) to the Train group in both the desktop
    sidebar and the mobile drawer. Empty state ("Add the race you're training for.") when no
    races exist.
  - New `.app` CSS under a **§10** block (`.races-stats`, `.race-row`, `.race-spotlight`,
    `.spot-*`, responsive stacking). **Verified:** new `tests/test_redesign_races_render.py`
    (3 tests: spotlight+lists, empty state, no-target-still-lists) + the existing
    `test_routes_race_events.py` (47) all green; CSS braces balanced; zero inline
    `style=`/`onclick=`. (Suite-wide, the only reds are the date-sensitive
    `test_layer4_plan_create.py::TestMissingSessionsRetry` cases — their hardcoded
    `plan_start_date=2026-06-01` is now in the past; pre-existing, unrelated to this slice.)
- **Phase 3 · §11 Plans · history** — `templates/plans/list.html` onto the new shell
  (`nav_active='plan'`). Active plans as cards (`status='active'` gets an accent spotlight)
  with real progress (`item_count`/`completed_count` via `data-progress`, CSP-clean), archived
  plans as dimmed view/restore rows, and a shared **"You're at the start line."** empty state
  (§26 copy) with Generate + Import paths. Grounded in the legacy `training_plans` model — the
  artboard's version-history table belongs to the separate `plan_versions` model and is
  intentionally not rendered. New §11 CSS + `tests/test_redesign_plans_list_render.py` (2).
- **Phase 3 · §13/§14 + §12-diff** — remaining plan-lifecycle surfaces onto the new shell.
  - **§14 Import** (`plans/import.html`): JSON-paste form + token-styled schema reference (the
    real `garmin_workout_json` column + sport-type IDs kept as a developer reference).
  - **§13 Refresh** (`plans/v2/refresh.html`): horizon picker (T1/T2/T3) with active-tier
    highlighting, current-version card, no-plan empty state; the Bootstrap frequency-cap modal
    (nonce'd) preserved. The §30/Phase-7 `coaching_bp` consolidation it pointed at is now **⛔ BLOCKED** (see Phase 7).
  - **§12 diff** (`plans/v2/refresh_view.html`): refreshed-plan sessions grouped by date with
    updated/new diff badges + left-border accents — the app's **real** compare surface
    (refresh-vs-parent). Standalone arbitrary version A↔B compare has **no backend route**; not
    fabricated, deferred to a future backend slice.
  - New §12/§13/§14 CSS + `tests/test_redesign_plan_refresh_import_render.py` (5). Existing
    `test_routes_plan_refresh.py` (64) still green; CSS braces balanced; CSP-clean.

- **Phase 4 · §15 Exercises library** — `templates/rx/list.html` onto the new shell
  (`nav_active='library'`). "Exercises" = the `rx` blueprint (current_rx joined to
  exercise_inventory). **Current Rx** renders as a token `table.data` (Exercise · Disc. ·
  Type · Pattern · Sets · Reps · Weight · Last done · Outcome · actions) with outcome chips
  (↑ good / → warn / ↓ bad), `n/3` failure counter, and the **plateau/deload watch** — a
  warn-tinted alert when `deload_pending`, plus a per-row **−10%** button on flagged rows
  (real `rx.deload_entry` POST, `data-confirm`, CSP-clean). The real **GET filters**
  (discipline · status · location) are preserved as a token filter bar; an active filter that
  matches nothing shows a "no matches → Clear" note (not the hero). The **catalog**
  (inventory exercises with no current Rx) lists below in a second `table.data`. Zero
  prescribed Rx → a **"No Rx yet."** hero whose CTAs stay grounded in real routes: *Generate
  plan* → `plan_create.new_plan`; *View catalog* anchors to the inline `#catalog` list (there
  is **no** add/import endpoint for `rx`, so the artboard's "Add exercise"/"Import" top
  actions were **not** ported). `rx/form.html` (edit) left on `base_legacy.html` for now —
  still reachable from the row **Edit** link. New §15 CSS block + new
  `tests/test_redesign_rx_list_render.py` (3: current-Rx+catalog+deload, no-Rx hero,
  filtered-empty). Full redesign suite green (18); CSS braces balanced; zero inline
  `style=`/`onclick=`. (Suite-wide, the only reds remain the pre-existing date-sensitive
  `test_layer4_plan_create.py` cases — unrelated.)

- **Phase 4 · §16 Locations** — `templates/locales/list.html` onto the new shell
  (`nav_active='locations'`). UX copy is "Locations"; the route/blueprint stays `locales`
  (CONVENTIONS §E.6). Two-column **card grid**: the four legacy enums (home/hotel/partner/
  airport) plus athlete-created rows, each card showing the equipment chips (first 8 + "+N
  more"), the notes callout, the chain/category/manual chips, and a footer with the item
  count · city · `updated_at` (str-coerced for both backends). Real actions only — per-card
  **Edit** (`locales.edit_profile`), **Refresh** (custom + mapbox-anchored →
  `locales.refresh_from_mapbox`), **Delete** (custom → `locales.delete_locale`,
  `data-confirm`), and a dashed **Add-another** tile + top-bar **Add location** →
  `locales.new_locale`. The artboard's **★ primary** badge and global **Find nearby** action
  were **not** ported (no primary flag in the schema; `nearby_instances` is per-locale, not a
  global search). When nothing is configured (no `locale_profiles` rows and no saved
  equipment), a **"Where do you train?"** hero replaces the four blank enum cards — each enum
  offers a set-up shortcut (`edit_profile`) plus a search-by-address card → `new_locale`.
  `locales/form.html` + `new.html` + `nearby.html` left on `base_legacy.html` for now (still
  reachable). New §16 CSS block + `tests/test_redesign_locales_list_render.py` (2: populated
  grid, empty hero). Existing `test_locales.py` (142) still green; redesign suite green (20);
  CSS braces balanced (570/570); zero inline `style=`/`onclick=`.

- **Phase 4 · §17 Connections hub** — the big consolidation: a **new `connections`
  blueprint** (`/connections`) replaces four surfaces with one tabbed hub
  (`connections/hub.html`, `nav_active='link'`), tabs server-rendered via `?tab=` (CSP-clean,
  no SPA).
  - **Sources** — OAuth providers via the reused `profile.load_connections` (COROS/Polar with
    real `provider_auth` status → Connect / Re-authorise + Revoke `profile.disconnect_provider`);
    **Garmin = PAUSED** (CONVENTIONS §E.3) with an "upload .FIT" path; the webhook-only stubs
    (Strava/Whoop/TrainingPeaks/Zwift/RideWithGPS) shown as "not available yet" (no OAuth start
    route → no dead button); a `.FIT` **drop zone** posting to the real `garmin.import_fit`
    pipeline.
  - **Files** — recent imported activities from `cardio_log` (real), tagged **manual vs synced**
    by the `fit:`-prefixed dedup-id scheme, plus the **inline FIT inspector** (`connections.inspect`
    reuses `garmin_fit_parser._dump_fit`) — the artboard's inline side panel, replacing the
    standalone debug-fit page.
  - **Preferences** — a **grounded, read-only** explainer of how ingestion actually behaves
    today (content-hash SHA-256 dedup, plan matching, sport sniffing, manual+auto one log,
    Garmin paused, provider-management link). The artboard's configurable trust-order /
    pull-window / retention toggles have **no backend** and are intentionally **not fabricated**
    (same discipline as §10 priority / §12 A↔B compare) — a note says they arrive with a
    settings backend.
  - **Hard-cut:** removed `garmin.dashboard` + `garmin.debug_fit` routes **and** their templates;
    repointed every referrer (sidebar + mobile drawer nav, `base_legacy.html` dropdown, the
    `garmin/{import,sync,wellness_log,import_wellness}.html` back-links, and the `sync_confirm`
    redirect) at `connections.hub`. "Garmin dashboard" phrasing is gone. The `.FIT`
    import/sync/wellness/auth **pipeline stays** (the hub feeds it). `connections_bp` registered
    in `app.py`.
  - New §17 CSS block + `tests/test_redesign_connections_render.py` (5: sources, files+inspector,
    files-empty, prefs-grounded, bad-tab fallback). Existing garmin + profile suites green;
    redesign suite green (25); CSS braces balanced (627/627); CSP-clean.

- **Phase 4 · §18–§20 Profile decomposition** — the 7-tab `profile/edit.html` monolith split
  into three new-shell surfaces (Race-events→§10 and Connections→§17 already moved out):
  - **§18 Athlete** (`profile.edit`, reskinned `profile/edit.html`, `nav_active='athlete'`) —
    **Athlete / Schedule / Skills** as server-rendered sub-tabs (`?tab=`, reusing the §17
    `.conn-tabs` styling). Every field name + POST action preserved (`profile.edit`,
    `.save_schedule`, `.save_skills`); Schedule/Skills reuse the shared onboarding partials so
    those flows stay in lockstep. Day-1 **first-run banner** when nothing's saved. The legacy
    Bootstrap tab-activation inline `<script>` is gone (tabs are plain links).
  - **§19 Account** (NEW `profile.account_settings` → `profile/account.html`) — identity
    (read-only from `users`) + change password (`profile.change_password`) + sign out
    (`auth.logout`). **No** billing/2FA/export/delete (CONVENTIONS §E.1). Also fixes a latent
    bug: the nav "Account settings" link pointed at the **POST-only** `change_password` (a GET
    405) — now lands on the real settings page.
  - **§20 Coach memory** (NEW `profile.coach_memory` → `profile/coach_memory.html`) — durable
    AI-coach preferences with `fb_source` provenance (captured-from vs added-manually), manual
    add (`add_preference`) + delete (`delete_preference`); permanent chip; empty state. The
    add/delete/change-password routes now redirect to their new homes.
  - Nav (sidebar dropdown + mobile drawer) gains **Coach memory** and a working **Account
    settings** link. Also de-CSP'd the shared `onboarding/_schedule_form.html` (moved five
    inline `style="width:18%"` to a `.sched-col` class — fixes onboarding too).
  - New §18/§19/§20 CSS + `tests/test_redesign_profile_render.py` (7). Existing profile +
    onboarding + password/preference suites green; redesign suite green (32); braces balanced
    (669/669); CSP-clean.

- **Phase 6 · §27 Error states** — the brand "trail-voice" error pages, grounded in real Flask
  errorhandlers. New **shared `templates/_error.html`** — deliberately **standalone** (does NOT
  extend `base.html`: no sidebar/topbar/nudges/cmdk includes, no DB-dependent context of its
  own) so a 500 can't cascade into a second failure while rendering its own error page (models
  the existing `auth/_shell.html` standalone pattern, `.app`-themed via tokens + sprite). Two
  handlers in `app.py`: **404 "You're off trail."** (Today/Plan/Workouts way-back quicklinks, no
  retry) and **500 "Something seized up."** (retry = reload for GET, else home). Each carries a
  per-request **diagnostic block** (request_id · path/action · status · timestamp) and an
  **`mailto:help@aidstation.pro`** with that diagnostic **pre-filled** — the 500 handler logs the
  real exception server-side keyed by the request_id the user sees; the exception text never
  reaches the page. Plan-gen **"The build stalled."** already lives inline in
  `plan_create/progress.html` (§04), so no third handler. New §27 CSS block (`.error-*`, token
  only, `.app`-scoped, responsive) + `tests/test_redesign_error_render.py` (2: 404 + 500 render,
  copy/diag/mailto/quicklinks/retry, CSP-clean). Suites green (redesign + auth-gate + admin =
  79); braces balanced (814/814); zero inline `style=`/`onclick=`/`<script>` on the page. The
  existing `CSRFError` handler (plain 400) left as-is.

- **Phase 6 · §28 Light mode** — wired the real toggle for the token-swap theme.
  A nonced `<head>` **pre-paint bootstrap** (`base.html`) reads `localStorage['aidstation-theme']`
  and sets `.theme-light` on `<html>` before first paint (no FOUC). Toggle controls:
  a `data-theme-toggle` **sun icon** in the topbar + a **"Light mode"** row in the mobile
  drawer; `app.js` flips `.theme-light` on `<html>`, persists, and syncs each control's
  `aria-pressed`/`aria-label`. Fixed a latent bug: the light override keyed on the dead
  `body.theme-light .app` (the shell `<body>` **is** `.app`, so a descendant combinator never
  matched it) → now `.theme-light .app`. No per-screen CSS (token swap only); the new §28 CSS
  is just the two control affordances + a `<button>.drawer-item` reset. New
  `tests/test_redesign_theme_toggle_render.py` (1). Redesign + auth suites green (58); braces
  balanced (817/817); CSP-clean (the pre-paint script is nonced).

- **Phase 6 · §26 Empty / first-run states** — extracted the "You're at the start line." block
  to a shared partial **`templates/_no_plan.html`** (single source for the headline + copy + the
  two grounded ways-in: `plan_create.new_plan` / `plans.import_plan`); `plans/list.html` now
  `{% include %}`s it (byte-identical render — the existing empty-state test still passes). The
  design's "3 divergent no-plan headlines" had **already** been consolidated by the new IA: the
  "Plan" nav item *is* `plans.list_plans`, so Plan-page and Plans-list are one surface, and the
  dashboard's no-plan state is a purpose-built daily-hub hero ("No session scheduled") that is
  intentionally distinct (not forced onto this component).
- **Phase 6 · §29 A11y sweep** — ported `a11y-wire.js`'s behavioral layer onto the real shell.
  The static contract was already in place (landmarks, `aria-current` via the nav macros,
  focus-visible rings on `.sidebar-item`/`.tab`, the §25 focus-trap dialog controller, cmdk
  listbox roles); the missing piece was **roving tab-order**. New `app.js` controller over
  `[data-roving]` containers (sidebar = vertical, tab bar = horizontal): each is **one** page
  tab stop, arrow keys move between `[data-roving-item]`s, Home/End jump, initial stop = the
  `aria-current` item. Real `<a>` links, so Enter follows the href natively. Also relocated the
  **Primary** landmark label off the `<aside class="sidebar">` (a complementary region) onto the
  inner `<nav class="sidebar-nav">` (the actual navigation landmark). **CSP:** production already
  enforces (`REPORT_ONLY` is a dev-only opt-in, default off) and every slice has been CSP-clean,
  so there are no enforced-mode violations to clear. New `tests/test_redesign_a11y_render.py`
  (1). Redesign + auth suites green (59); `app.js` syntax-checks; CSP-clean.

### Known blocker (infra, not code) — Vercel **Preview** deploys 500
Preview deployments crash with `FUNCTION_INVOCATION_FAILED`: `app.py` raises at **import** when
`SECRET_KEY` is unset, and the Preview environment scope is missing it (runtime logs confirm
`could not import "app.py": …SECRET_KEY…`). **Fix (owner):** add `SECRET_KEY` and a
**Neon dev/preview-branch** `DATABASE_URL` to the Vercel project's **Preview** env scope.
Until then, PR previews can't render — verify locally or via static checks. This is unrelated
to any redesign PR (Production is unaffected).

### Next — Phase 6+ (polish + remaining migrations)
**Phase 5 COMPLETE** (§21 Notifications feed + bell dropdown · §22 Notification settings (read-only,
honest — no preference backend) · §23 ⌘K command palette · §24 keyboard-shortcuts overlay · §25 Admin:
users / drill-in detail / focus-trapped type-to-confirm delete / audit / telemetry). All five phases
of the core surface map are now on the new shell.

Remaining work, lower priority:
- **§29 a11y sweep** — the focus-trap pattern now exists (`app.js` dialog controller); audit the rest
  of the shell (skip links, modal/offcanvas focus, reduced-motion) against it.
- **§30 / Phase 7** — `coaching_bp` consolidation: **⛔ BLOCKED** (code-verified 2026-06-02). Can't be done as written — `coaching_bp` (legacy `training_plans`) and `plan_refresh_bp` (modern `plan_versions`) run on two different, both-live plan models, and `coaching_bp` is load-bearing for the migrated §06 plan view (chat + AI review). Prerequisite: unify the plan models first. Full rationale in **Phase 7** above.
- **§12** standalone A↔B plan compare (needs a backend route; deferred).
- **Secondary `base_legacy.html` forms still reachable:** ✅ `rx/form.html` (Edit Rx) · ✅ **entire
  `locales/` dir** (`form` editor all-3-modes · `new` add-location · `nearby` same-chain · `refresh_confirm`
  Mapbox diff) — all migrated. Remaining — the garmin import/sync/wellness pages and admin
  `plan_inspect.html`/`plan_diag` (operator deep-debug). The Mapbox **save/upgrade/refresh** + shared-profile
  **save** + nearby-**add** POST paths weren't manually exercised here (render-tested only) — worth a manual smoke.

Carry the established slice discipline: one responsive template, token classes only, CSP enforced
(nonce'd scripts, no inline `style=`/`onclick=`), flip `base_legacy.html` → `base.html`, and add a
render smoke test per the §08/§09 precedent.
