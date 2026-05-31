# AIDSTATION PRO — Build Plan for Claude Code

**Purpose:** instructions for porting the `redesign/` mockup into the live Flask app (`ahorn885/exercise`).
**Pair this with:** `BUILD_TASKS.md` (the per-section → route/template checklist) and `HANDOFF.md` (the design rationale).

---

## 0 · The one thing to understand first

The redesign canvas is **React/Babel-in-browser mockups**. The live app is **server-rendered Flask + Jinja on Bootstrap 5.3.3 behind a strict Content-Security-Policy.**

> **Do not port the JSX as React.** There is no build step and we are not adding one. The `.jsx` files are a **visual + behavioral spec to read**, not code to ship. Every screen becomes a **Jinja template** styled with the redesign's **token CSS**, with the small amount of interactivity living in `static/app.js` (CSP-nonced, event-delegated — never inline).

Translation, not transplant. Internalize this before writing a line.

---

## 1 · Target stack (decided)

| Layer | Decision |
|---|---|
| Templating | **Stay Jinja.** No SPA, no build tooling. |
| Design source of truth | **`tokens.css` + `polish.css`** become the app's primary CSS. Port them into `static/` and make every new screen speak the `--bg/--fg/--accent` token vocabulary. |
| Bootstrap | **Keep it loaded, let it fade.** It stays for the grid, modals, and form resets so we don't rewrite everything at once. New components use token classes (`.btn-primary`, `.card`, `.chip`, `.sidebar-item`…), not `.btn.btn-primary` Bootstrap. Over the migration, Bootstrap usage shrinks; don't rip it out mid-flight. |
| JS | Vanilla, in `static/app.js`, **CSP-nonced and event-delegated** (`data-*` hooks, never `onclick=`). The redesign's `a11y-wire.js` is the behavioral spec for roles/tab-order. |

**Deploy target:** `ahorn885/exercise` ships to **Vercel + Neon (Postgres)**. TrueNAS/self-host is retired — ignore any local-only assumptions. Claude Code's local run-loop uses the **SQLite dev fallback** (`database.py`), but production is Postgres, so any schema/migration touched during the build must be **tested against Postgres (Neon branch or local PG) before merge** — the cold-start `init_postgres()` runs `IF NOT EXISTS` statements, so verify new columns/tables land there too.

**Single user (owner only) for now** — no back-compat or redirect burden. Route consolidations (e.g. Connections) can **hard-cut** old URLs; no migration shims needed.
| Icons | Inline SVG `<symbol>` sprite ported from `shell.jsx`'s `I` set — referenced via `<svg><use href="#i-home"></use></svg>`. No icon-font dependency. |

### Why these choices
- **Incremental rollout was requested.** A token-CSS layer can sit *alongside* Bootstrap and old templates; each screen migrates independently with the old one untouched until its replacement ships.
- **CSP is enforced at the response header** (`app.py` `_set_security_headers`), so any inline `style="…"` or `onclick=` is blocked *by the browser at runtime*, not just by review. The token-class approach avoids inline styles by construction.

---

## 2 · The CSP reality (read before you "just get it working")

The chosen posture was *"get it working first, harden CSP + a11y at the end."* The honest version of that, given this app:

1. **You cannot defer CSP by using inline styles** — the live header (`script-src`/`style-src` are nonce-only, `'unsafe-inline'` is dropped) will visibly break them. Dynamic widths in the mockups (progress bars, sparkline heights) **must** use the existing pattern: `data-progress="…"` + a JS init pass in `app.js` (see the comment block in `app.py` describing exactly this).
2. **To move fast during the build**, set `CSP_REPORT_ONLY=1` in dev. The header flips to `Content-Security-Policy-Report-Only`, so violations are logged, not enforced — you iterate without fighting the browser. **Flip it back off before each screen is marked done.**
3. **Every inline `<script>`/`<style>` you add must render `nonce="{{ csp_nonce() }}"`** (template helper already exists). Prefer external `app.js`/`style.css` over inline blocks.
4. **a11y** (roles, `aria-*`, roving tab-order, focus trap on the delete-user dialog) is the legitimate fast-follow. `a11y-wire.js` did this at runtime over mock divs; in real code the roles belong on real `<button>`/`<a>`/`<nav>` elements. Land the markup semantically correct as you build each screen (cheap when you're already in the file); save the *focus-management* polish (trap/restore, live `.focus()`) for the §29 hardening pass.

**Rule of thumb:** semantic HTML + token classes + `data-*` JS hooks = CSP-clean and a11y-friendly *by default*. You only "defer" the focus-management choreography, not the structure.

---

## 3 · Rollout strategy — incremental, shell-first

```
Phase 0  Foundation        Port tokens.css + polish.css → static/. Build SVG sprite. CSP_REPORT_ONLY=1 in dev.
Phase 1  App shell  ◀ FIRST New base.html: desktop sidebar + mobile bottom-tab bar + top bar.
                           Old base.html kept as base_legacy.html; screens opt in to the new shell.
Phase 2  Daily loop        Dashboard → Plan week → Workout detail → Logging → Wellness.
Phase 3  Plan lifecycle    Races → Plans history → Compare → Refresh → Import.
Phase 4  Library + Account  Exercises → Locations → Connections hub → Profile → Account → Coach memory.
Phase 5  System            Notifications + settings → ⌘K → Shortcuts → Admin.
Phase 6  States + Polish   Empty/error states → Light mode → a11y hardening → print stylesheets.
Phase 7  Cleanup           Retire coaching_bp into plan_refresh (§30).
```

### The migration mechanism (how "old templates stay" works in practice)
- New shell lives in **`templates/base.html`**; the current one is copied to **`templates/base_legacy.html`** verbatim. Not-yet-migrated screens keep `{% extends "base_legacy.html" %}`; migrated screens switch to the new `base.html`. **Both shells render the same Flask context** (`current_user`, `active_nudges`, flashes, csrf, csp_nonce) so no route changes are needed to flip a screen.
- Migrate one template per PR. A screen is "done" when it: renders on the new shell, is CSP-clean (REPORT_ONLY back off), has semantic landmarks/labels, and matches the artboard at desktop (1440) **and** mobile (390) widths.
- **Sidebar/tab-bar active state** is driven by `request.endpoint` (or a `{% set nav_active = "…" %}` per template), so the new shell highlights correctly regardless of which screens have migrated.

### First slice (Phase 1) — exact scope
Build the **app shell only**, wired to real routes, no screen redesigns yet:
- Desktop **sidebar** (grouped: Train / Log / Account) replacing the flat navbar + dropdowns. Use `url_for(...)` for every item (see nav map in §5).
- **Top bar** with breadcrumbs slot + search affordance (⌘K hook can be a no-op stub this phase).
- Mobile **5-tab bottom bar** (Today · Plan · Log[FAB] · Stats · Athlete) + a drawer for overflow.
- User chip in the sidebar foot → Account/Profile/Sign out (sign out stays a POST form with `csrf_token`, as today).
- Admin link visible only when `current_user.id == 1` (preserve existing gate).
- Render the **dashboard** on the new shell as the proof screen; everything else stays on `base_legacy.html` until Phase 2+.

---

## 4 · Design-system port (Phase 0 specifics)

Copy these into the app and treat as canonical:
- `redesign/tokens.css`  → `static/tokens.css` (the `:root` tokens, `.light` variant, atoms: `.btn*`, `.chip`, `.card`, `.sidebar*`, `.topbar`, `.tabbar`, `.stat-card`, `.eyebrow`, `.kv`…). The cup-tumble keyframes only matter for Phase 3 plan-gen.
- `redesign/polish.css` → fold into `static/style.css` (focus-visible rings, reduced-motion, print, forced-colors, the `.board-light` token override → repurpose as the real light-mode class, skip-link).
- Fonts already match (Inter + JetBrains Mono are loaded in `base.html`). Keep them.

**Token discipline:** new colors come from `color-mix(in oklab, var(--accent) X%, transparent)` — never new hex. Statuses map to `--good/--warn/--bad/--info`. This is what makes light mode a free token-swap instead of a reskin.

---

## 5 · Navigation map (new shell → real routes)

The new IA collapses `base.html`'s flat bar + 5 dropdowns into a grouped sidebar. Wire each item to its existing `url_for`:

**Train**
- Today → `dashboard.index`
- Plan → `plans.list_plans` (active plan; week view is Phase 2)
- Workouts → `training.list_entries`  *(badge = count, optional)*
- Exercises → `rx.list_entries`

**Log**
- Quick log → `natural_log.index` (the adaptive form landing; see §8 of HANDOFF — one form, 6 types)
- Wellness → `wellness.index`

**Account**
- Athlete → `profile.edit`
- Locations → `locales.list_profiles`  *(UX copy "Locations"; route name stays `locales`)*
- Connections → **new consolidated hub** (Phase 4; currently `garmin.dashboard` + `garmin.debug_fit` + provider blueprints)

**Top-bar / user chip**
- Notifications → `nudges.*` (feed) — Phase 5
- Account settings → `profile.change_password` surface — Phase 4
- Admin → `admin.dashboard` (only if `current_user.id == 1`)
- Sign out → POST `auth.logout` (keep csrf form)

**Dropped from nav** (still reachable, deliberately demoted — confirm before deleting routes): `purchases.list_purchases` ("Recommended purchases"), `references.*`, the separate Strength/Cardio/Body/Conditions/Injuries top-level entries (folded into Workouts + the adaptive Log). See coverage notes in `BUILD_TASKS.md`.

---

## 6 · Conventions: reading the JSX, writing the Jinja

| Redesign (JSX) | Live app (Jinja + CSS) |
|---|---|
| `<Sidebar active="home" />` | `{% include "_shell/sidebar.html" %}` with `nav_active` set per page |
| `<TopBar crumbs={[…]} actions={…} />` | `{% include "_shell/topbar.html" %}`, `{% block crumbs %}`, `{% block topbar_actions %}` |
| `<Eyebrow>● SECTION · CONTEXT</Eyebrow>` | `<p class="eyebrow accent">● …</p>` |
| `<h1 className="page-title">` | `<h1 class="page-title">` (unchanged class) |
| `<Pill tone="good">` / `<Chip>` | `<span class="chip good">` |
| `<Ic d={I.home} />` | `<svg class="icon"><use href="#i-home"></use></svg>` (sprite) |
| `<AsMark/>` / `<Wordmark/>` | reuse the inline brand SVG already in `base.html` |
| inline `style={{width: pct}}` | `data-progress="{{ pct }}"` + `app.js` init (CSP) |
| React `onClick` | `data-action="…"` + delegated listener in `app.js` |
| `<Light>` wrapper | `class="light"` on the subtree, or the global body theme class |
| component state (tabs, modals) | `data-*` + `app.js`; modals can reuse Bootstrap's JS where convenient |

**Mobile parity:** the `screens-mobile*.jsx` files show the 390px layouts. Don't build separate mobile templates — use **one responsive template** per screen with the sidebar→bottom-tab-bar swap handled by the shell's media queries. Match the mobile artboard, don't pixel-fork it.

---

## 7 · Guardrails (carried from HANDOFF §5/§9 — do not relitigate in UI)

1. **No billing, no 2FA, no human-coach surface.** Cut for lack of backend. Don't reintroduce.
2. **"Coach" = the AI coach.** Coaching *is* the app.
3. **Garmin shows a PAUSED state** ("API access closed, upload .FIT manually"). Strava + Wahoo are the connected mocks. `.FIT` copy is **brand-neutral** — no Garmin-specific terms ("body battery" → "recovery scores").
4. **"Push to Garmin" → "Upload completed .FIT."** Round-trip via upload.
5. **Logging is one adaptive form**, type picker swaps the pane (Cardio · Strength · Body · Wellness · Conditions · Injury) — replaces the six `/new` routes in UX while the routes stay.
6. **"Locales" stays the code/route name; "Locations" is UX copy only.**
7. **Connections is a real route consolidation** (4 surfaces → 1 hub, inspector is a panel not a page). Treat as a routing change, not just a template. **Single-user app (owner only) — hard-cut old URLs; no redirects/back-compat needed.**
8. **Errors are a 3-page system** (404 · plan-gen · 500) via a shared error template, each with a diagnostic block + `mailto:help@aidstation.pro`.
9. **Plan-gen progress is a time-bucket cup-pour**, not server sub-steps.
10. **Deleting a user cascades 25 per-user tables**; the dialog is type-to-confirm; admin (id 1) and shared catalogs are untouched.

---

## 8 · Definition of done (per migrated screen)

- [ ] Extends new `base.html`; old template deleted **only** once parity is confirmed.
- [ ] Renders correctly at **1440px desktop** and **390px mobile** (responsive, not forked).
- [ ] **CSP enforced** (REPORT_ONLY off) with **zero violations** — no inline style/handler; widths via `data-*`; scripts nonced.
- [ ] Semantic landmarks + labels present (`nav`/`main`/`banner`, `aria-current` on active nav, labelled controls). Focus-management polish may defer to the §29 pass but structure ships now.
- [ ] Token classes only; no new hex; light mode works via the body theme class with no extra CSS.
- [ ] Existing Flask context still wired (csrf, flashes, `active_nudges`, `current_user`).
- [ ] No console errors.

---

## 9 · Suggested repo additions

- `templates/base.html` (new shell) + `templates/base_legacy.html` (current, verbatim).
- `templates/_shell/` → `sidebar.html`, `topbar.html`, `mobile_tabbar.html`, `mobile_drawer.html`, `icons.svg` (sprite).
- `static/tokens.css` (ported) + extend `static/style.css` with polish rules.
- `templates/_error.html` shared error shell (Phase 6) wired into Flask `errorhandler`s.
- **Optional but recommended:** a `CLAUDE.md` at repo root capturing §7 guardrails + §6 conventions + the CSP rules, so every Claude Code session starts with them in context.

---

## 10 · How to use BUILD_TASKS.md

It lists all 31 sections in board order, each mapped to the real blueprint(s) + template(s), with the migration note and dependencies. Work **top-to-bottom within a phase**; the phases in §3 group the sections. Check items off there as PRs land.
