# AIDSTATION PRO — Redesign Build Conventions

Persistent rules for porting the `redesign/` mockup into the live app.
**Reference this from the repo's existing `CLAUDE.md`** (e.g. "For redesign work, follow `redesign/CONVENTIONS.md`"). Don't duplicate it into CLAUDE.md — link to it.

Companion docs: `BUILD_PLAN.md` (strategy/phases) · `BUILD_TASKS.md` (31-section map) · `PHASE0.md` (current PR) · `HANDOFF.md` (design rationale).

---

## A · Architecture truth
- Deploys to **Vercel + Neon (Postgres)**. TrueNAS/self-host is retired — ignore local-only assumptions.
- Local dev uses the **SQLite fallback** (`database.py`); **prod is Postgres**. Test any schema change against Postgres before merge (`init_postgres()` runs `IF NOT EXISTS` on cold start).
- **Single user (owner only)** right now — no back-compat, no redirect shims. Route consolidations may **hard-cut** old URLs.
- The `redesign/*.jsx` files are a **spec to read, not code to ship.** No React, no build step. Screens become **Jinja templates + token CSS**; interactivity is vanilla JS in `static/app.js`.

## B · CSP is enforced — build CSP-clean by default
The response header (`app.py` `_set_security_headers`) nonces all scripts/styles and drops `'unsafe-inline'`. Therefore:
- **No inline `style="…"`.** Use token classes. Dynamic values (progress bars, bar heights) use `data-progress="…"` + a JS init pass in `app.js`. Positioning helpers go in `style.css` (e.g. `.sprite-host`).
- **No inline event handlers** (`onclick=`…). Use `data-action="…"` + delegated listeners in `app.js`.
- **Every inline `<script>`/`<style>` renders `nonce="{{ csp_nonce() }}"`.** Prefer external files over inline blocks.
- Third-party origins already allowed: `cdn.jsdelivr.net` (Bootstrap), `fonts.googleapis.com`/`fonts.gstatic.com`. Don't add new external origins without updating the CSP directives in `app.py`.
- **Dev workflow:** `CSP_REPORT_ONLY=1` to iterate; flip **off (enforced)** before marking any screen done. Zero console violations is part of done.

## C · Design system
- **Source of truth:** `static/tokens.css` (ported from `redesign/tokens.css`). Speak the `--bg/--fg/--accent` token vocabulary on every screen.
- **Bootstrap stays loaded but fades** — keep it for grid/modals/form resets; build new components with token classes (`.btn-primary`, `.card`, `.chip`, `.sidebar-item`…), not Bootstrap's `.btn.btn-primary`.
- **No new hex.** Derive colors via `color-mix(in oklab, var(--accent) X%, transparent)`. Statuses map to `--good/--warn/--bad/--info`. This keeps light mode a free token-swap.
- **Type:** Inter (body) + JetBrains Mono (eyebrows/numerics/labels) — already loaded in `base.html`.
- **Icons:** the `_shell/icons.svg` `<symbol>` sprite. `<svg class="icon"><use href="#i-<name>"></use></svg>`. No icon font.
- **Vertical rhythm:** wrap a page's stacked sections in `.stack` (flex column, `gap: 16px`) rather than hanging per-block `margin-top`/`margin-bottom` — bare sibling cards under `.page-body` otherwise touch with no spacing. Use `.row`/`.col`/`.col-side` for horizontal splits (they collapse to a stacked column under the 859px breakpoint).
- **Bootstrap-override gotchas** (it loads *before* the token CSS, so its base rules leak unless overridden — all handled in `tokens.css`, don't reintroduce):
  - Don't rely on inherited text colour inside a `.card` — Bootstrap's `.card`/`body` set a dark `--bs-body-color`. Bare `h1–h6` are likewise re-asserted to `var(--fg)`; component headings shouldn't need their own colour.
  - `.app .row` zeroes Bootstrap's `--bs-gutter-x` (its negative margins + `.row > *` padding); don't add Bootstrap grid classes (`.g-3`, `.col-md-*`) on redesign rows.

## D · JSX → Jinja translation
| Redesign (JSX) | Live app |
|---|---|
| `<Sidebar active="home" />` | `{% include "_shell/sidebar.html" %}` + per-page `nav_active` |
| `<TopBar crumbs=… actions=… />` | `{% include "_shell/topbar.html" %}` + `{% block crumbs %}` / `{% block topbar_actions %}` |
| `<Eyebrow>● …</Eyebrow>` | `<p class="eyebrow accent">● …</p>` |
| `<h1 className="page-title">` | `<h1 class="page-title">` |
| `<Pill tone="good">` / `<Chip>` | `<span class="chip good">` |
| `<Ic d={I.home}/>` | `<svg class="icon"><use href="#i-home"></use></svg>` |
| `<AsMark/>` / `<Wordmark/>` | reuse the brand SVG already in `base.html` |
| `style={{width: pct}}` | `data-progress="{{ pct }}"` + `app.js` |
| `onClick` | `data-action="…"` + delegated `app.js` |
| `<Light>` wrapper | `body.theme-light` (global) — no per-screen CSS |
| component state (tabs/modals) | `data-*` + `app.js`; reuse Bootstrap JS where convenient |

**Mobile:** one **responsive** template per screen (sidebar ⇄ bottom-tab-bar via media queries). Do **not** fork separate mobile templates. Match the 390px artboard.

## E · Product guardrails (do not relitigate in UI)
1. **No billing, no 2FA, no human-coach surface** — cut for lack of backend. Don't reintroduce.
2. **"Coach" = the AI coach.** Coaching is the app.
3. **Garmin = PAUSED** ("API access closed, upload .FIT manually"). Strava + Wahoo are the connected mocks.
4. **`.FIT` copy is brand-neutral** — any device exporting .FIT. No Garmin-isms ("body battery" → "recovery scores"). "Push to Garmin" → "Upload completed .FIT."
5. **Logging = one adaptive form** (type picker: Cardio · Strength · Body · Wellness · Conditions · Injury). The six `/new` routes stay; the UX is unified.
6. **"Locales" stays the route/code name; "Locations" is UX copy only.**
7. **Connections = one hub** (Sources / Files / Preferences). FIT inspector is an **inline panel, not a page**.
8. **Errors = 3-page system** (404 "You're off trail." · plan-gen "The build stalled." · 500 "Something seized up.") via a shared error template + `mailto:help@aidstation.pro`.
9. **Plan-gen progress = time-bucket cup-pour**, not server sub-steps.
10. **Coach memory** preferences carry `fb_source` provenance (chat/plan_review/natural_log/workout_note/manual) via `profile.add_preference`/`delete_preference`.
11. **Deleting a user cascades 25 per-user tables**; type-to-confirm dialog; admin (id 1) + shared catalogs untouched.

## F · Accessibility contract
- `a11y-wire.js` (in `redesign/`) is the **reference implementation** — port its roles/labels/tab-order onto **real** `<button>`/`<a>`/`<nav>` elements as you build each screen (structure is cheap when you're already in the file).
- Landmarks: `nav[aria-label="Primary"]`, `main`, `banner`. Skip-link moves focus to `main`.
- Roving tab-order on the sidebar + mobile tab bar (one tab stop, arrow keys within, `aria-current="page"` on active).
- Tablists (Connections, Admin): `role="tablist"`/`tab`/`aria-selected`.
- Delete-user dialog: `role="dialog"` + `aria-modal` + `aria-labelledby` + focus **trap on open / restore on close** + inert background.
- **Defer only** the live focus-management choreography to the §29 hardening pass — semantic markup ships with each screen.

## G · Per-screen Definition of Done
- [ ] Extends new `base.html`; legacy template deleted only after parity confirmed.
- [ ] Responsive: correct at 1440 desktop **and** 390 mobile.
- [ ] CSP enforced, **zero violations** (no inline style/handler; widths via `data-*`; scripts nonced).
- [ ] Semantic landmarks + labels; `aria-current` on active nav.
- [ ] Token classes only; no new hex; light mode works via `body.theme-light` with no extra CSS.
- [ ] Flask context intact (csrf, flashes, `active_nudges`, `current_user`).
- [ ] Tested against Postgres if schema touched. No console errors.
