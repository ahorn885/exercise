# AIDSTATION PRO · App Redesign · Handoff

**Status:** Complete. 31 sections · ~95 artboards · full desktop + mobile parity (admin & dev surfaces intentionally desktop-only) · light mode (live board toggle + 16-screen showcase) · accessibility wired live (landmarks, roving tab-order, ARIA, focus management). No console errors.

**Live canvas:** `redesign/App Redesign.html` — open in this project, click any artboard to focus fullscreen. A **Theme toggle** (top-right, fixed) flips the whole board dark ⇄ light.

**Source repo:** `ahorn885/exercise` (Flask + Jinja). Reference templates + `app.py` imported into the project. The redesign covers every route registered in `app.py`. **Everything in the canvas is grounded in code that exists** — no invented features (we explicitly cut billing, human-coach surfaces, and 2FA because there's no backend for them).

**Support email used in error states:** `help@aidstation.pro` (mailto pre-fills with the diagnostic block).

---

## 0 · Build status — implementation underway (live)

The design canvas is done (everything below). **The redesign is now being built into the live Flask app**, phase by phase. Per-section status + the granular handoff lives in **`BUILD_TASKS.md`** (the live tracker) and the build rules in **`CONVENTIONS.md`**; this section is the top-line summary.

**Shipped to `main`:** Phase 0 (token CSS + polish + icon sprite, `.app`-scoped) · Phase 1 (app shell — grouped sidebar + mobile tab bar) · **Phase 2 daily-loop COMPLETE** (§05 Dashboard · §06 Plan week · §07 Workout detail · §08 unified Logging w/ all 6 panes · §09 Wellness) · **Phase 3 plan-lifecycle COMPLETE\*** (§04 Plan generation · §10 Races manager · §11 Plans history · §12 diff-via-refresh · §13 Plan refresh · §14 Import) · **Phase 4 library + account COMPLETE** (§15 Exercises · §16 Locations · §17 Connections hub · §18 Athlete profile · §19 Account settings · §20 Coach memory) · **Phase 5 system COMPLETE** (§21 Notifications feed + bell dropdown · §22 Notification settings (read-only) · §23 ⌘K command palette · §24 keyboard-shortcuts overlay · §25 Admin: users / drill-in / focus-trapped delete / audit / telemetry) · **Phase 6 polish — done** (§26 shared "start line" empty-state partial; §27 error states — trail-voice 404/500 + standalone shared `_error.html`; §28 light-mode toggle — pre-paint, persisted, no FOUC; §29 a11y sweep — roving tab-order ported onto the real nav + landmark fix, CSP enforced & clean; secondary `base_legacy.html` forms migrated onto the new shell: Edit Rx + the entire `locales/` dir). **Remaining (optional):** print stylesheets + the operator `base_legacy` forms (garmin import/sync/wellness, admin `plan_inspect`/`plan_diag`). *\*§12 standalone version A↔B compare deferred — no backend route yet; §13's §30 `coaching_bp` consolidation is **⛔ blocked** (Phase 7 — code-verified it can't be done as written; see §9 note 1).*

**Build mechanics that turned out to matter** (carry these forward):
- **CSP is enforced** — no inline `style=`/`onclick=`; every inline `<script>` is nonced. Dynamic positioning (e.g. the cup-pour letters, progress-bar widths) is set via the **DOM API** (`element.style.setProperty`) or `data-*` + `app.js`, never inline attributes.
- **All new CSS is `.app`-scoped** so legacy screens (on `base_legacy.html`) render unchanged until each is migrated. Token vocabulary only (`--bg/--fg/--accent`); light mode stays a free token-swap.
- **Cup-pour keyframes** (`letterTumble`/`cupTipping`) shipped inert in `tokens.css` at Phase 0 and went live with §04; letters carry `.letter-tumble` so the reduced-motion rule settles them statically.
- **Verification is render-test-based**: each slice adds a smoke test that boots the real app (DB stubbed — no local Postgres) and renders the route, asserting structure + CSP cleanliness. (Vercel **Preview** deploys were blocked on a missing `SECRET_KEY` env scope — an owner-side infra gap, not a code issue.)

**Next:** Phase 6+ polish — §29 a11y sweep (port `a11y-wire.js` onto the real elements, flip CSP `REPORT_ONLY` **off** and clear violations) · §28 light-mode toggle in code · §30/Phase-7 `coaching_bp` consolidation (**⛔ blocked** — needs the plan models unified first; see §9 note 1) · the remaining `base_legacy.html` surfaces (garmin import/sync/wellness pages + admin `plan_inspect`/`plan_diag`). §12 standalone A↔B compare stays deferred pending a backend route.

---


## 1 · Design system

Brand-aligned with **AidStation Brand Guide v3** (project root). Tokens in `redesign/tokens.css`; polish/accessibility CSS in `redesign/polish.css`.

| | |
|---|---|
| Type | **Inter** (300–900) body · **JetBrains Mono** (400–700) eyebrows / numerics / labels |
| Accent | `oklch(0.72 0.18 55)` — warm orange |
| Neutrals | `--ink` (dark) / `--paper` (light) — full 0–4 scales |
| Semantic | `--good` / `--warn` / `--bad` + `--accent` |
| Radius | 3 / 6 / 10 px (`--r-sm` / `--r` / `--r-lg`) |
| Borders | Hairlines via `color-mix(in oklab, var(--fg) X%, transparent)` |
| Eyebrows | Mono, 9–10px, 0.16–0.22em tracking, uppercase, prefixed `●` |
| Buttons | `.btn-primary` · `.btn-ghost` · `.btn-text` · `.btn-icon` · `.btn-sm` |
| Mode | **Dark primary.** Light mode fully working — see §6. |

**Nav structure** (replaces the flat top-bar + dropdowns in `base.html`):
- **Desktop**: grouped sidebar — Train (Today · Plan · Workouts · Exercises) / Log (Quick log · Wellness) / Account (Athlete · Locations · Connections). Single "Connections" entry (no Garmin badge).
- **Mobile**: 5-tab bottom bar (Today · Plan · Log [FAB] · Stats · Athlete) + drawer.

---

## 2 · File structure

```
redesign/
├── App Redesign.html              # The canvas — entry point + theme toggle + boot guard
├── tokens.css                     # Design tokens + cup-tumble keyframes
├── polish.css                     # Focus rings · reduced-motion · print · forced-colors ·
│                                  #   board-light token override · skip-link
├── a11y-wire.js                   # ★ Runtime accessibility layer (see §7)
├── shell.jsx                      # Sidebar, top bar, mobile chrome, icons (I), AsMark, Wordmark
│
│  — Core screens (original build) —
├── screens-desktop-a.jsx          # Dashboard · Plan week · Workout detail
├── screens-desktop-b.jsx          # Log (6 type forms) · Onboarding 2–7 · Login
├── screens-desktop-c.jsx          # Exercises · Locations · Wellness · Profile (+ legacy Connections)
├── screens-desktop-d.jsx          # Plan generate · cup-pour progress · compare · import · (legacy FIT debug)
├── screens-desktop-e.jsx          # Plan list/history · Plan empty · Exercises empty
├── screens-mobile.jsx             # Dashboard · Workout · Quick-log sheet · Plan day list
├── screens-mobile-b.jsx           # Exercises · Locations · Wellness · Profile · Plan refresh (mobile)
├── screens-mobile-c.jsx           # Empty + error states (mobile) · Plan progress · compare
├── screens-mobile-d.jsx           # Plan list · Plan empty · Exercises empty (mobile)
├── screens-mobile-onb.jsx         # Mobile onboarding 1–7
├── screens-mobile-aux.jsx         # Mobile sign-in · plan generate · import · search sheet
├── screens-states.jsx             # Desktop empty/error states (round 1)
├── screens-states-b.jsx           # Desktop empty/error states (round 2) + mobile
├── screens-notifications.jsx      # Notifications full page · dropdown · mobile feed
├── screens-gaps.jsx               # Onb step 01 · Profile empty · Wellness FIT · Notif settings ·
│                                  #   ⌘K · Shortcuts · ErrorShell + trail-voice error pages
├── screens-gaps-mobile.jsx        # Mobile parity for the gaps file + MobileErrorShell
│
│  — Consolidation & new surfaces (this engagement) —
├── screens-connections-v2.jsx     # ★ Unified Connections hub (Sources/Files/Prefs + empty)
├── screens-empty-shared.jsx       # ★ Single shared "no plan" empty state (overrides 3 originals)
├── screens-admin.jsx              # ★ Admin: Users · User detail · Delete confirm · Audit · System
├── screens-account.jsx            # ★ Account settings (identity + change password + sign out)
├── screens-coach-memory.jsx       # ★ Coach memory (durable AI-coach preferences)
├── screens-races-routes.jsx       # ★ Race events manager + notification deep-link route map
├── screens-polish.jsx             # ★ Light-mode wrappers + A11y visual-rules spec
├── screens-a11y.jsx               # ★ Tab-order diagrams + ARIA component reference
│
└── (imported reference)
    ├── templates/...              # Original Flask Jinja templates
    └── app.py                     # Route blueprint reference
```

**Architecture:** every screen is a React functional component; Babel transpiles in-browser via inline `<script type="text/babel">` tags. Files share components through `window.*` exports (`Object.assign(window, {...})` at the bottom of each file). Files are split to stay under ~1000 lines (babel-in-browser slows past that).

**Load order matters:** `screens-empty-shared.jsx` loads *after* the core screens so its exports override the three original "no plan" components. The canvas HTML has a **boot guard** that waits for sentinel components to be defined before first render (prevents a cold-load race).

---

## 3 · Sections in the canvas (01–31, in board order)

The board reads top-to-bottom as a user journey, grouped into phases.

| § | Section | D | M | Notes |
|---|---------|---|---|-------|
| **Foundation** |
| 01 | System & read-me | ✓ | — | Orientation note |
| **Entry** |
| 02 | Sign in | ✓ | ✓ | `auth.login` + forgot path |
| 03 | Onboarding · 7 steps | ✓ | ✓ | Step 01 account → 07 |
| 04 | Plan generation | ✓ | ✓ | Start + cup-pour progress |
| **Daily loop** |
| 05 | Dashboard · Today | ✓ | ✓ | Hero = next workout |
| 06 | Training plan | ✓ | ✓ | Week view; no-plan state |
| 07 | Workout detail | ✓ | ✓ | Upload-.FIT; rest-day variant |
| 08 | Logging | ✓ | ✓ | One adaptive form, 6 types |
| 09 | Wellness | ✓ | ✓ | 30-day readiness |
| **Plan lifecycle** |
| 10 | Races · event manager | ✓ | ✓ | A/B/C priority; edit date → re-cascade |
| 11 | Plans · history & versions | ✓ | ✓ | Zero-plans state |
| 12 | Plan compare · diff | ✓ | ✓ | Version A ↔ B |
| 13 | Plan refresh | ✓ | ✓ | Adapt to new context |
| 14 | Plan import | ✓ | ✓ | JSON paste |
| **Library** |
| 15 | Exercises library | ✓ | ✓ | No-Rx state |
| 16 | Locations | ✓ | ✓ | Empty state |
| **Setup / Account** |
| 17 | **Connections · hub** | ✓ | ✓ | Sources · Files · Preferences + empty |
| 18 | Athlete profile | ✓ | ✓ | Day-1 first-run state |
| 19 | **Account settings** | ✓ | ✓ | Identity + change password + sign out |
| 20 | **Coach memory** | ✓ | ✓ | Durable AI-coach preferences |
| **System** |
| 21 | Notifications & feed | ✓ | ✓ | Full feed + dropdown + deep-link map |
| 22 | Notification settings | ✓ | ✓ | Channel × category matrix |
| 23 | Command palette · ⌘K | ✓ | ✓ | Jump-to-anything |
| 24 | Keyboard shortcuts | ✓ | — | Cheat sheet |
| **Admin** (internal, desktop-only) |
| 25 | **Admin** | ✓ | — | Users · drill-in · delete confirm · audit · system |
| **Cross-cutting states** |
| 26 | Empty / first-run states | ✓ | ✓ | Collected no-data views |
| 27 | Error states | ✓ | ✓ | 404 · plan-gen · 500, trail voice |
| **Polish** |
| 28 | Light mode | ✓ | ✓ | 16 screens + global toggle |
| 29 | Accessibility, keyboard & motion | ✓ | — | Visual rules + tab-order + ARIA ref |
| **Housekeeping** |
| 30 | Code-cleanup callout | — | — | `plan_refresh` + `coaching/review` dev note |
| 31 | Roadmap · not yet | — | — | Remaining work |

---

## 4 · What changed this engagement (newest first)

This work picked up after the v11 build. Major moves:

### Accessibility wired live (not just specced) — §29 + `a11y-wire.js`
The behavioral a11y layer is **implemented**, applied to every rendered screen at runtime and re-applied as the canvas virtualizes artboards (MutationObserver). Covers landmarks (`nav`/`main`/`banner`), a focus-managed **skip link**, **roving tab-order** on nav lists + mobile tab bar (one tab stop, arrow keys within, `aria-current="page"`), `role="button"` + `aria-label` + Enter/Space on ~490 mock buttons, labelled stat-card groups, table header `scope`, `role="tablist"`/`tab` on the Connections & Admin tabs, and full `dialog`/`aria-modal`/`aria-labelledby` + inert background on the delete-user modal. `polish.css` carries the visual rules (focus-visible rings, reduced-motion, print, forced-colors). §29 documents all of it with region maps, a focus-trap diagram, a mobile swipe-order diagram, and a 21-row **ARIA component reference** that is the contract to build against.

### Light mode — §28 + board toggle
A fixed **Theme toggle** (top-right) adds `.board-light` to `<body>`; a token override in `polish.css` repaints every `.screen` to the paper palette. Persists in `localStorage`. §28 additionally shows 16 explicitly `.light`-wrapped archetypes (dashboard, plan, workout, logging form, table, feed, profile, admin, races, account + mobile). Proves the palette is theme-ready, not a reskin.

### Board reorganization → 01–31
Renumbered and reordered into a clean journey (Foundation → Entry → Daily loop → Plan lifecycle → Library → Setup/Account → System → Admin → States → Polish → Housekeeping). Removed a duplicate auth section and an out-of-order plan-list; merged strays.

### Connections unified — §17
Collapsed **four** overlapping surfaces into one hub: the old sidebar Connections page, the standalone "FIT debug" (formerly mislabeled "Garmin dashboard"), the Wellness .FIT import, and the Profile → Connections tab. Three tabs — **Sources** (providers + one smart .FIT drop zone), **Files** (history with the parsed-FIT **inspector as an inline side panel**, not a separate page), **Preferences** (dedupe/trust-order rules + pull windows, moved off the profile). Plus a zero-providers empty state. The "Garmin dashboard" phrasing is gone everywhere; the page is just **Connections**.

### Empty states consolidated — §26
Three divergent "no plan" screens (Dashboard / Plan / Plans-list, each with a different headline) became **one shared component** — "You're at the start line." with a pre-flight readiness checklist — reused across all three surfaces via `screens-empty-shared.jsx`.

### Error copy → trail voice — §27
Rewrote generic SaaS error copy into the brand's endurance voice: 404 = **"You're off trail."**, plan-gen failure = **"The build stalled."** (hit the wall on the peak block), generic 500 = **"Something seized up."**

### New account surfaces grounded in real routes
- **Admin (§25):** expanded from a lone users table to Users (clickable drill-in) · User detail (data footprint across the 25 per-user scoped tables) · type-to-confirm **Delete user** · **Audit log** (`admin.audit`) · **System/telemetry** board.
- **Account settings (§19):** identity (username/display/email/last login) + change password (`profile.change_password`) + sign out. Removed previously-invented billing/2FA/export/delete.
- **Coach memory (§20):** durable AI-coach preferences (`profile.add_preference`), auto-captured from chat / plan review / natural log / workout note (`fb_source`) or added manually; each deletable, some permanent.
- **Race events (§10):** the `race_events` manager — A/B/C priority races; editing a date re-cascades the plan.
- **Notification deep-links (§21):** route map for where each feed item type lands.

---

## 5 · Key design decisions (carried forward)

1. **Dark-mode primary**, light mode fully supported via token swap (§28). Brand mark stays one-color; orange accent is the chip inside the cup.
2. **"Locales" → "Locations"** in all UX copy (Jinja template name `locales.html` unchanged in code).
3. **"Push to Garmin watch" → "Upload completed .FIT."** Round-trip via upload, not a (non-working) push.
4. **Logging is one landing with an adaptive form** — type picker (Cardio · Strength · Body · Wellness · Conditions · Injury) swaps the right pane. Replaces six separate `/new` routes.
5. **No third-party SSO on signup.** Email/password only, strength meter + live rules + consent.
6. **`.FIT` is brand-neutral** — any device that exports .FIT (Garmin, Wahoo, COROS, Polar, Suunto, Apple Watch). Mock device is a Wahoo ELEMNT Roam 2. "Body battery" (Garmin term) → "recovery scores."
7. **Garmin shows a PAUSED state** — "API access closed," upload .FIT manually. Strava + Wahoo are the connected mocks.
8. **Plan-gen progress is graphic, not step-by-step** — cup-pour animation on a fixed time bucket; doesn't depend on server-reported phases. "Pouring you a plan."
9. **Errors are a 3-page system** (404 · plan-gen · 500) via shared `ErrorShell`/`MobileErrorShell`, each with a diagnostic block and `mailto:help@aidstation.pro` prefilled. Old per-failure screens remain in source, unwired.
10. **Coaching IS the app** — there is no human-coach surface and we don't build one. "Coach" = the AI coach. Likewise **no billing** and **no 2FA** until backend exists.

---

## 6 · Light mode — how it works

Two layers, both real:
- **Global:** `#theme-toggle` (in `App Redesign.html`) toggles `body.board-light`. `polish.css` maps the light tokens (`--bg`→`--paper`, `--fg`→`--ink`, etc.) under that class, cascading into every `.screen`. State persists in `localStorage` (`aidstation-board-theme`).
- **Per-component:** wrapping any screen in `<div className="light">` repaints just that subtree (used by §28's showcase via the `Light` wrapper + `LightX` components in `screens-polish.jsx`).

To theme a new screen: nothing required — it inherits the global toggle automatically. For a side-by-side light artboard, add `<Light><YourScreen /></Light>`.

---

## 7 · Accessibility — how it's wired

`a11y-wire.js` is the **reference implementation** of the §29 contract. It runs after the canvas mounts and enhances every `.screen` exactly once (idempotent guard), re-running via MutationObserver as artboards virtualize in/out.

What it applies:
- **Landmarks:** `.sidebar`→`nav[aria-label=Primary]`, `.page-body`→`main`, `.topbar`/`.appbar`→`banner`, `.statusbar`→`aria-hidden`.
- **Skip link:** injected per desktop screen; moves focus to `main`.
- **Roving tab-order:** sidebar items + mobile tabs are one tab stop; ↑/↓ (or ←/→) move within; `Home`/`End` jump; active item gets `tabindex=0` + `aria-current=page`.
- **Buttons:** `role=button`, `tabindex=0`, text-derived `aria-label` (icon-only controls labelled from context), Enter/Space activation.
- **Groups/tables/chips:** stat cards → labelled `group`; `<th scope>`; status chips → `role=status`.
- **Tablists** (Connections, Admin) and the **delete-user dialog** are wired at source in their JSX (`role`, `aria-selected`, `aria-modal`, `aria-labelledby`/`describedby`, `aria-hidden` backdrop).

**For engineering:** port this module's logic into the real components (the roles/labels belong on real `<button>`/`<a>`/`<nav>` elements). Programmatic focus management (trap on dialog open, restore on close) and live `.focus()` only fully exercise in a real browser — the static mockup applies the attributes; the live app drives the focus.

---

## 8 · Outstanding work (§31)

Everything code-backed is now designed. What remains is **build-time implementation** (well underway — see §0 for live status; **Phases 0–5 shipped**, Phase 6 polish in progress) and optional polish — no missing screens.

- **Implement the a11y wiring in real components** — `a11y-wire.js` is the spec; move roles/labels/tab-order onto real elements, add focus trap/restore on the dialog.
- **Light mode in code** — extend the `.light` / token-swap to the production stylesheet (design is done).
- **Loading / skeleton states** for data-dependent screens (Dashboard · Plan · Wellness · Notifications) — not yet drawn; confirm if wanted.
- **Print stylesheets** for plan week view / workout printout / race-day brief (CSS hooks exist in `polish.css`).
- **Possibly out of scope — confirm first:** race-day hero view, tablet layouts (768–1180px).

### Backend cleanup (from §30)
- **Retire `coaching_bp` — ⛔ BLOCKED** (code-verified 2026-06-02; not safe as written). The "same job, pick one" framing doesn't hold against the code: `coaching_bp` (`/coaching`) runs on the **legacy `training_plans`/`plan_items`** model, `plan_refresh_bp` (`/plans/v2/refresh`) on the **modern `plan_versions`** model — the two parallel models from `PLAN_REVIEW_AND_CORRECTIONS.md`. `coaching_bp` also **backs the already-shipped §06 plan view** (AI Review → `coaching.review`; coach-chat → `coaching.chat`; `coaching.clarify`) and owns chat/preferences/clarify/context/api-review surfaces `plan_refresh` has no equivalent for. Deleting `routes/coaching.py` + `templates/coaching/` now would break the live plan view. **Prerequisite:** unify the `training_plans` ↔ `plan_versions` models (or migrate the §06 plan view + chat/review onto `plan_versions`) first; then review folds into `plan_refresh` and chat/preferences re-home. Deferred, not dropped. Full rationale: `BUILD_TASKS.md` Phase 7.

---

## 9 · Notes for engineering

1. **Two routes — NOT one job (corrected 2026-06-02):** the §30 "pick one, retire the other" note is **⛔ blocked**. `plan_refresh_bp` runs on the modern `plan_versions` model; `coaching_bp` runs on the legacy `training_plans` model **and still backs the migrated §06 plan view** (AI Review + coach-chat) plus chat/preferences/clarify/context with no `plan_refresh` equivalent. Retiring it requires unifying the two plan models first — see §8 "Backend cleanup" and `BUILD_TASKS.md` Phase 7.
2. **Garmin is paused** — keep the paused state; mocks show Strava + Wahoo connected.
3. **`.FIT` is brand-neutral** — copy/device placeholders reflect this; avoid Garmin-specific terms.
4. **Plan-gen cascade has no sub-step progress** — the cup-pour runs on a time bucket, not server phases.
5. **Skills toggles are versioned** — `_skills_form.html` partial is shared between onboarding and the profile tab; keep that share.
6. **Connections consolidation is a real route change** — the old Connections page, FIT debug, Wellness FIT import, and Profile → Connections tab all funnel into one hub. Inspector is a panel, not a page.
7. **Coach memory uses `fb_source`** — preferences carry provenance (chat / plan_review / natural_log / workout_note / manual). Backed by `profile.add_preference` / `delete_preference`.
8. **Deleting a user cascades** across 25 per-user scoped tables; shared catalogs (exercise inventory, equipment, modalities) and the admin user (id 1) are untouched. The delete dialog is type-to-confirm.
9. **Errors hit `help@aidstation.pro`** — hardcoded in `ErrorShell` (`screens-gaps.jsx`) and `MobileErrorShell` (`screens-gaps-mobile.jsx`). One place to change.
10. **No billing / human-coach / 2FA** — these were explicitly cut as out-of-code; don't reintroduce in UI without backend.

---

## 10 · How to continue working in the canvas

1. Open `redesign/App Redesign.html`.
2. New screens → new `screens-*.jsx` (under ~1000 lines), `Object.assign(window, {...})` at the bottom, add a `<script type="text/babel" src="...">` line in the canvas. If it must override an existing component, load it **after** that file.
3. Add a `<DCSection>` with `<DCArtboard>` children — desktop `D_W×D_H` (1440×900) or `D_TALL` (1440×1080), mobile `M_W×M_H` (390×844).
4. If you add sentinel-critical components, consider adding one to the boot guard's `typeof` checks in the canvas.

### Conventions
- Eyebrow above every title: `<Eyebrow>● SECTION · CONTEXT</Eyebrow>`
- Titles: `<h1 className="page-title">`; stats: `<span className="num">`; status: `<Pill tone="good|warn|bad|accent">`
- Desktop chrome: `<Sidebar active="…" />` + `<TopBar crumbs={[…]} actions={…} />`
- Mobile chrome: `<StatusBar />` + `<AppBar />` + `<TabBar active="…" />`
- Onboarding chrome: `<OnbShell step={N}>` / `<MobileOnbShell step={N} …>`
- Icons: `<Ic d={I.name} size={N} />` (inventory in `shell.jsx`); brand: `<AsMark />` / `<Wordmark />`
- New colors: prefer `color-mix(in oklab, var(--accent) X%, transparent)` over new hex
- Don't reinvent error pages — route through `ErrorShell` / `MobileErrorShell`
- New screens are theme-free by default (inherit the board toggle); keep the `--bg`/`--fg` token vocabulary so light mode works automatically

---

## 11 · Version log

- **v15 (this engagement)** — Accessibility wired live (`a11y-wire.js` + §29 ARIA reference & tab-order diagrams). Light mode (board toggle + §28 16-screen showcase). Board reorganized to 01–31. Boot guard added.
- **v14** — Race events manager (§10) + notification deep-link map (§21). Account settings (§19). Coach memory (§20). Corrected profile (removed invented billing/export/delete).
- **v13** — Admin section fleshed out (§25): user drill-in, delete confirm, audit log, system telemetry.
- **v12** — Connections unified into one hub (§17); FIT debug / Wellness FIT / Profile→Connections folded in. "No plan" empty states consolidated (§26). Error copy → trail voice (§27).
- **v11** — full mobile parity (onboarding 1–7, sign-in, plan generate, import, ⌘K).
- **v10** — dropped SSO; 10 error artboards → 3-page system + `help@aidstation.pro`.
- **v9** — signup step, profile first-run, wellness FIT import, notif settings, ⌘K, shortcuts.
- **v8** — notifications & activity feed. **v7** — plans history. **v6** — mobile account screens.
- **v5** — empty/error round 1. **v4** — mobile core. **v3** — onboarding + cup-pour. **v1–2** — initial core screens.

**Last touched:** v15. Canvas loads clean — no console errors as of last `done` call. Verifier-confirmed: landmarks, roving tab-order, tablists, dialog semantics, light toggle, and §29 all render and behave per spec.

### Implementation log (live app build — see §0 + `BUILD_TASKS.md`)
- **Phase 6 · §29 A11y sweep** — ported `a11y-wire.js`'s behavioral layer onto the real shell. Static contract was already in place (landmarks, `aria-current`, focus-visible rings, the §25 focus-trap dialog, cmdk listbox roles); added the missing **roving tab-order** — an `app.js` controller over `[data-roving]` nav containers (sidebar vertical / tab bar horizontal): one tab stop each, arrows move within, Home/End jump, initial stop = `aria-current`. Relocated the **Primary** landmark label onto the `<nav>` (off the complementary `<aside>`). CSP already enforced in prod (REPORT_ONLY = dev-only opt-in); slices are CSP-clean. New `tests/test_redesign_a11y_render.py`.
- **Phase 6 · §28 Light mode** — wired the real toggle (topbar sun button + drawer row → `app.js`, persisted in `localStorage`), FOUC-free via a nonced `<head>` pre-paint that sets `.theme-light` on `<html>`. Fixed the dead `body.theme-light .app` selector → `.theme-light .app`. Token swap only.
- **Phase 6 · §27 Error states** — trail-voice **404 "You're off trail."** + **500 "Something seized up."** via Flask 404/500 handlers in `app.py`, rendering a new **standalone** `templates/_error.html` (no shell includes / no DB context → a 500 can't cascade). Per-request diagnostic block + pre-filled `mailto:help@aidstation.pro`; the 500's real exception is logged server-side keyed by the user-visible request_id, never shown. Plan-gen "The build stalled." stays inline in `plan_create/progress.html` (§04). New §27 CSS + `tests/test_redesign_error_render.py` (2).
- **Phase 7 · §30 investigation (no code change)** — attempted the `coaching_bp` retirement; **code-verified it's blocked.** `coaching_bp` (legacy `training_plans`) and `plan_refresh_bp` (modern `plan_versions`) run on two different, both-live plan models, and `coaching_bp` backs the migrated §06 plan view (chat + AI review) plus chat/preferences/clarify/context surfaces refresh lacks. A literal delete would break the live plan view. Documented the blocker + the "unify the plan models first" prerequisite across §8/§9/§30 + `BUILD_TASKS.md` Phase 7; left the blueprint registered.
- **Phase 6 · secondary forms** — the remaining reachable `base_legacy.html` forms moved onto the new shell: **Edit Rx** (`rx/form.html`) + the **entire `locales/` dir** (the all-3-modes equipment editor, add-location, nearby-same-chain, and the Mapbox refresh-confirm diff). Render-tested; the Mapbox save/upgrade/refresh + shared-profile save + nearby-add POST paths weren't manually exercised (worth a smoke).
- **Phase 5 · §21–25 COMPLETE** — §21 Notifications feed (`nudges.feed` over `account_nudges`) + topbar bell dropdown (unread badge, recent 5, "See all"); §22 Notification settings (read-only — no preference backend exists, honest delivery-model page, no fabricated toggles); §23 ⌘K command palette (server-rendered destinations, JS only filters/navigates); §24 keyboard-shortcuts overlay (`?`, shares the §23 partial); §25 Admin (dashboard/audit/telemetry off `base_legacy` + new `admin.user_detail` drill-in with data-footprint cards + **focus-trapped type-to-confirm Delete user**).
- **Phase 4 · §15–20 COMPLETE** — §15 Exercises library (`rx.list_entries`: current-Rx table + plateau/deload watch + catalog + No-Rx hero), §16 Locations (`locales` card grid, route name unchanged), §17 **Connections hub** (new `connections_bp` — four surfaces → one Sources/Files/Prefs hub; `garmin.dashboard`+`debug_fit` hard-cut, pipeline kept), §18 Athlete profile (Athlete/Schedule/Skills sub-tabs), §19 **Account settings** (new `profile.account_settings`; fixes the GET→POST `change_password` 405), §20 **Coach memory** (new `profile.coach_memory` with `fb_source` provenance).
- **Phase 3 · §11–14** — Plans history list (active spotlight + archived + "start line" empty), Plan refresh (T1/T2/T3 horizons + freq-cap modal), refresh diff view (updated/new badges — the real compare surface; arbitrary A↔B compare deferred, no backend route), Plan import (JSON paste).
- **Phase 3 · §10** — Races · event manager: standalone page under Plan (`race_events.index`), target-race spotlight + upcoming/past lists, reuses the existing set-target/edit/delete handlers. A/B/C priority not ported (schema has only `is_target_event`). New Train-group nav item.
- **Phase 3 · §04** — Plan generation: start form, cup-pour progress (time-bucket, CSP-clean letters), plan view.
- **Phase 2 COMPLETE** — §05 Dashboard · §06 Plan week · §07 Workout detail (+nutrition/upload-.FIT) · §08 unified Logging (6 panes) · §09 Wellness.
- **Phase 1** — app shell (grouped sidebar + top bar + mobile tab bar + drawer); legacy screens re-pointed to `base_legacy.html`.
- **Phase 0** — token CSS + polish layer + 34-icon sprite, `.app`-scoped (inert foundation).
