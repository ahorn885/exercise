# Phase 0 — Foundation PR (groundwork, no screen changes)

**Goal:** land the design-system plumbing so every later screen migration is a thin template + token-class job. This PR changes **no user-facing screens** — it adds CSS, an icon sprite, and a dev flag, all unused until Phase 1 opts in.

**Definition of done:** app runs unchanged (every existing screen renders exactly as before), new assets are loaded but inert, CSP still clean.

---

## 1 · Port the token CSS

**Add `static/tokens.css`** — copy `redesign/tokens.css` verbatim, then:
- Keep the `:root` token block (brand, ink/paper scales, semantic `--bg/--fg/--accent`, status, radii, font vars).
- Keep the `.light` variant block — this becomes real light mode in Phase 6, free if we stay token-disciplined now.
- Keep the atoms: `.btn*`, `.chip`, `.card`, `.eyebrow`, `.mono`, `.num`, `.kv`, `.stat-card`, `.sidebar*`, `.topbar`, `.page*`, `.statusbar`, `.appbar`, `.tabbar`, `.avatar`, `.hairline*`, `.pulse-dot`, `.bars`, `.spark`.
- Keep the `letterTumble` / `cupTipping` keyframes (used by Phase 3 plan-gen; harmless now).
- **Scope check:** `tokens.css` styles `.screen` as the artboard frame. In the real app there is no `.screen` wrapper — the equivalent is `<body>`. Either (a) add `class="screen"` semantics to the app shell in Phase 1, or (b) lift the `.screen` base rules onto `body`/a `.app` wrapper. **Recommended:** rename `.screen` → `.app` here and apply `.app` to `<body>` in Phase 1. Document the choice at the top of the file.

**Link it** in `templates/base.html` `<head>`, **after** Bootstrap, **before** `style.css`:
```html
<link href="{{ url_for('static', filename='tokens.css') }}" rel="stylesheet">
```
Loading it now is safe — the token classes aren't applied to any current markup, so nothing visually changes.

---

## 2 · Fold polish rules into `static/style.css`

Append `redesign/polish.css` rules to the existing `static/style.css` (don't add a separate file — keep the link count down). Bring over:
- `:focus-visible` ring rules (token-based outline).
- `@media (prefers-reduced-motion: reduce)` — kill the cup-tumble + transitions.
- `@media print` hooks (used in Phase 6; harmless now).
- `@media (forced-colors: active)` fallbacks.
- The **light-mode token override** — but rename the selector from the mockup's `.board-light` to the production class you'll toggle in Phase 6 (suggest `body.theme-light`). Leave it defined-but-unused now.
- The **skip-link** styles (the link itself ships in Phase 1's shell).

**Watch for collisions:** `polish.css` was written to override mock markup. Diff against current `style.css` selectors before pasting; resolve any clashes in favor of not changing current screens. If unsure, namespace the new rules under `.app` so they only bite once Phase 1 adds that class.

---

## 3 · Build the icon sprite

**Add `templates/_shell/icons.svg`** — an inline SVG `<symbol>` sprite ported from `shell.jsx`'s `I` map. Each icon: `viewBox="0 0 24 24"`, stroke-based, `id="i-<name>"`.

Names to port (from `shell.jsx`): `home plan workout log library gear link athlete insights bell search plus check x arrow download chevR chevL chevD clock flame heart pin cloud weight shoe menu more bolt upload body pulse bandage sun`.

Pattern:
```html
{# _shell/icons.svg — included once, near top of <body> in base.html (Phase 1) #}
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="i-home" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
    <path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1V11z"/>
  </symbol>
  <!-- …one <symbol> per icon… -->
</svg>
```
Usage later: `<svg class="icon"><use href="#i-home"></use></svg>`.
**Note:** the `style="position:absolute"` above is an inline style — under the enforced CSP it'll be dropped. Use a class (`.sprite-host { position:absolute; width:0; height:0 }` in `style.css`) instead. This is the canonical "no inline style" workaround; get it right here as the template for the rest of the build.

**Don't include the sprite in `base.html` yet** unless you can do it without touching current rendering — it's fine to add the file now and wire the `{% include %}` in Phase 1. (An invisible sprite host is harmless if you do include it, but keep Phase 0 truly inert if you prefer.)

---

## 4 · Dev CSP flag

- Confirm `CSP_REPORT_ONLY` is read in `app.py` (it is — `_CSP_HEADER_NAME` branch). **Document it in the repo README / dev notes:** set `CSP_REPORT_ONLY=1` locally during the migration so violations log instead of block; **must be unset (enforced) before any screen PR is marked done.**
- No code change needed — just docs + a `.env.example` entry if one exists.

---

## 5 · Acceptance checklist

- [ ] `static/tokens.css` added; linked in `base.html` after Bootstrap, before `style.css`.
- [ ] `.screen`→`.app` rename decided & noted (or `.screen` base lifted to body in Phase 1 plan).
- [ ] polish rules merged into `style.css`; light override renamed + inert; no current screen changes appearance.
- [ ] `templates/_shell/icons.svg` sprite created (file present; include deferred to Phase 1 or added invisibly).
- [ ] `.sprite-host` class replaces any inline positioning style (CSP-clean).
- [ ] `CSP_REPORT_ONLY` documented for dev; enforced in prod.
- [ ] **Regression:** every existing route renders byte-for-byte as before (token CSS is loaded but unapplied). Spot-check dashboard, a form, the plan view.
- [ ] No new CSP violations in the browser console (enforced mode).
- [ ] Tested against **Postgres** (not just SQLite dev) since this is the Vercel/Neon deploy path — though Phase 0 touches no schema, confirm the app still cold-starts cleanly.

---

## 6 · What Phase 0 explicitly does NOT do
- No new shell, no sidebar, no nav change (that's Phase 1).
- No screen redesigns.
- No route changes.
- No light-mode toggle wired (Phase 6).

Keep the PR small and boring. Its whole job is to make Phase 1 a layout-only change.
