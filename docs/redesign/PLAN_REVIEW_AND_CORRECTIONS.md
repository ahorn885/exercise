# Redesign Build Plan — Review & Corrections

**Status:** Pre-build evaluation. No app code has been changed.
**Scope:** Reconciles the redesign build docs (`BUILD_PLAN.md`, `BUILD_TASKS.md`,
`PHASE0.md`, `CONVENTIONS.md`, `HANDOFF.md`) against the **actual state of the
live Flask app** in this repo, as of the merge that brought the `redesign/`
source assets (`tokens.css`, `polish.css`, `shell.jsx`, `screens-*.jsx`,
`App Redesign.html`) into `docs/redesign/`.

Read this **alongside** the existing docs. Where this file and an existing doc
disagree on a buildable fact, **this file wins** — it was verified against the
code. Where they disagree on product intent (guardrails, voice, IA), the
existing docs win; nothing here relitigates design decisions.

---

## 0 · Verdict

The redesign is **~90% executable as written.** The architecture decisions
(stay Jinja, token CSS alongside Bootstrap, CSP-clean by construction,
incremental shell-first rollout) are sound, the nav map points almost entirely
at real routes, and the CSP-clean JS pattern the plan assumes **already exists**
in `static/app.js`. The redesign source assets are now in the repo, so Phase 0
is a genuine **port**, not a reconstruction.

Three things in the docs are wrong or incomplete for *this* repo. They are all
fixable and none changes the overall strategy:

1. **Phase 0 is not inert.** `static/style.css` already ships its own design
   system that collides with `tokens.css`. A verbatim copy will visibly change
   existing screens. → §1.
2. **§22 Notification settings has no backend.** Every other section is backed
   by existing tables/routes; §22 needs net-new schema. → §2.
3. **Endpoint-name drift + two plan models.** A handful of `url_for` targets in
   the nav map don't match real endpoint names, and the app has *two* parallel
   plan systems the docs treat as one. → §3.

Plus three dangling "Action for Claude Code" items from `BUILD_TASKS.md` are now
resolved. → §4.

---

## 1 · Correction: Phase 0 is NOT inert — reconcile the token collision first

`PHASE0.md` §1 says to copy `redesign/tokens.css` into `static/` verbatim, link
it **before** `style.css`, and that "the token classes aren't applied to any
current markup, so nothing visually changes," with an acceptance criterion of
*"every existing route renders byte-for-byte as before."*

**That is not true here.** `static/style.css` already defines a `:root` token
block **and** atom classes with the **same names** as `tokens.css`, but
different values. Current screens use those classes. Verified collisions:

| Token / class | `static/style.css` (live, in use) | `docs/redesign/tokens.css` (incoming) |
|---|---|---|
| `--ink` | `oklch(0.16 0.005 250)` | `oklch(0.13 0.005 250)` |
| text vars | uses `--ink-2/3` directly for text | introduces semantic `--fg/--fg-2/3/4` |
| `.btn-sm` | `padding:6px 11px; font-size:13px` | `padding:6px 10px; font-size:10px`, mono, uppercase |
| `.eyebrow` | `var(--font-mono)` / `--ink-3` | `var(--mono)` / `--fg-3` |
| `.btn`, `.card`, `.wordmark`, `:root` | defined, used by current screens | redefined with different rules |

Because `tokens.css` sets properties `style.css` doesn't (e.g. `.btn`
`text-transform`/`letter-spacing`/mono `font-family`), those leak into existing
buttons/cards/eyebrows regardless of link order. Load order only decides which
side wins on *shared* properties; it can't prevent the *new* properties from
applying. So a naïve port is a visible regression, not a no-op.

### Required Phase 0 change — pick ONE reconciliation strategy

**Recommended — Option A: scope the new system under `.app`.**
- Wrap every **migrated** screen's `<body>` (or shell root) in `class="app"`
  (this is also the `.screen`→`.app` rename `PHASE0.md` §1 already floats).
- Namespace the ported atoms so they only bite inside the new shell:
  `.app .btn`, `.app .card`, `.app .eyebrow`, `.app :root`-equivalent tokens via
  `.app { --bg: …; --fg: … }`. Legacy screens (no `.app`) keep `style.css`
  untouched.
- Net effect: Phase 0 *is* inert for legacy screens (the acceptance criterion
  becomes true again), and the new tokens are live only where a migrated screen
  opts in. This matches the plan's "both shells render in parallel" model.

**Option B: unify the token vocabularies.**
- Promote `tokens.css` to the single `:root`, delete the duplicate token block
  from `style.css`, and migrate `style.css`'s direct `--ink-3`-for-text usages
  to the semantic `--fg-3`. Higher blast radius (touches every current screen at
  once), defeats the incremental rollout. Not recommended for Phase 0.

**Token value reconciliation** (either option): the two `:root` blocks differ
(`--ink` 0.16 vs 0.13, etc.). Treat **`tokens.css` as canonical** (it mirrors
Brand Guide v3) and note the delta in the file header so the slight darkening of
existing surfaces under Option B is a deliberate, recorded choice — not drift.

**Updated Phase 0 DoD:** "legacy (non-`.app`) screens render byte-for-byte as
before; token system is live only under `.app`; CSP clean; no console errors."

---

## 2 · Correction: §22 Notification settings needs net-new backend

`BUILD_TASKS.md` lists §22 (Notification settings — channel × category matrix)
as a `★ new surface` but doesn't flag that **there is no storage behind it.**

Verified: the notifications feature is backed by `account_nudges`
(`init_db.py:1015`) — `(user_id, nudge_type, created_at, displayed_at,
dismissed_at)`. That records nudge **instances**; there is **no** table for
per-user channel/category **preferences**, and no route reads or writes such
prefs. So §21 (feed) is buildable today, but §22's matrix would be a UI with
nothing to persist to.

### Options
- **Defer §22** to a later phase and ship §21 (feed) alone in Phase 5. Lowest
  risk; the matrix is the one genuinely-unbacked screen in the whole redesign.
- **Add backend** before building §22: a small additive migration, e.g.
  `notification_preferences (user_id, category TEXT, channel TEXT,
  enabled BOOLEAN, updated_at timestamptz, PRIMARY KEY(user_id, category,
  channel))`, plus get/set routes on `nudges` or `profile`. Per `CONVENTIONS.md`
  §A this must be additive/reversible and **tested against Postgres** (Neon
  branch), since cold-start `init_postgres()` runs `IF NOT EXISTS`.

**Recommendation:** defer §22 to its own PR after the feed (§21) ships; treat
the schema above as the design when it's picked up. Do not build the matrix UI
against a non-existent store.

---

## 3 · Correction: endpoint-name drift + two plan models

### 3a · `url_for` targets that don't match real endpoints
The nav map (`BUILD_PLAN.md` §5) and `BUILD_TASKS.md` are accurate except:

| Doc reference | Real endpoint (verified) | Notes |
|---|---|---|
| `plan_create.progress` | `plan_create.plan_progress` | route `/<id>/progress` |
| `plan_create.view` | `plan_create.view_plan` | route `/<id>` |
| "plan week view" / `plans.*` | `plans.view_plan(plan_id)` | week grouping already done server-side (`week_key`) |

Everything else in the nav map resolves: `dashboard.index`,
`plans.list_plans`/`import_plan`, `training.list_entries`, `rx.list_entries`,
`natural_log.index`, `wellness.index`, `profile.edit`/`change_password`/
`add_preference`/`delete_preference`, `locales.list_profiles`,
`garmin.dashboard`/`debug_fit`/`auth`, `admin.dashboard`/`audit`,
`auth.login`/`logout`, `race_events.*`, `nudges.*`.

### 3b · There are TWO plan systems — the redesign treats them as one
This is the most important architectural nuance the docs miss:

- **Legacy:** `training_plans` + `plan_items`, served by `plans_bp`
  (`plans.view_plan(plan_id)`, week-grouped). This is what §06 "Plan week" and
  §11 "Plans history" point at.
- **v2:** `plan_versions` + `layer4_cache`, served by `plan_create_bp`
  (`new_plan` → `generate_plan` → `plan_progress` → `view_plan(plan_version_id)`).
  This is what §04 "Plan generation" (the cup-pour) and the diagnostic query
  `SELECT … FROM plan_versions WHERE generation_status='generating'` operate on.

Note both blueprints define a `view_plan` with **different argument names**
(`plan_id` vs `plan_version_id`). The redesign's "Plan" surfaces (§04/06/11/12/13)
silently span both models. **Before building Phase 3 (plan lifecycle), confirm
which model each screen targets** — the week view (§06) and the generation
progress (§04) are not the same plan object. Mixing them up will produce broken
deep links. This deserves its own short spike at the start of Phase 3.

---

## 4 · Resolved: dangling "Action for Claude Code" items

`BUILD_TASKS.md` "Coverage notes" left three routes unresolved. Verified:

- **`references`** — **user-facing, keep it.** `references.exercises` renders
  `templates/references/exercises.html`: an equipment-filtered exercise-
  availability catalog (distinct from `rx`, the user's personal prescriptions).
  It is *not* dead/data-only as the doc guessed. **Decision:** fold into the
  Exercises library (§15) as a "browse all / availability" view, or keep as a
  secondary link. Do not delete.
- **`ad_hoc_workouts`** — **user-facing, real surface.** Renders
  `workouts/build_form.html` + `workouts/suggestion_view.html`: a build-a-single-
  session flow with AI suggestion, log/dismiss/regenerate actions. **Decision:**
  surface under Workouts (§07/§15 area) or the mobile Log FAB; it is its own
  generate-one-workout flow, not folded into the six logging forms.
- **`purchases`** — confirmed reachable, dropped from primary nav per plan;
  leave the route working (no change needed).

---

## 5 · What the docs get RIGHT (verified — build on these with confidence)

- **CSP plumbing** exactly as described: `csp_nonce()` template helper,
  `CSP_REPORT_ONLY` env flag (`app.py`), nonce'd `script-src`/`style-src` with
  `'unsafe-inline'` dropped. The "build CSP-clean by default" rule is real and
  enforced at the response header.
- **The CSP-clean JS pattern already exists** in `static/app.js`: `data-progress`
  width-init on DOM-ready and delegated `submit`/`click`/`change` listeners.
  New screens **extend** this file; they don't introduce a new pattern.
- **Current shell** is the flat Bootstrap navbar + dropdowns in `base.html` —
  exactly the IA the redesign replaces. No `_shell/` dir yet; the sidebar/topbar/
  tabbar are net-new (Phase 1), as planned.
- **Route consolidations are real:** `coaching_bp` + `plan_refresh_bp` both
  registered (Phase 7 cleanup is warranted); the 4 Connections surfaces
  (`garmin.dashboard`, `garmin.debug_fit`, provider settings, profile tab) exist
  and single-user means old URLs can be hard-cut.
- **Backed sections** confirmed against schema/routes: §20 Coach memory
  (`coaching_preferences` carries `source_feedback_id` → `feedback_log`, surfaced
  as `fb_source` via join in `profile.py`), §25 Admin delete-cascade (27 per-user
  tables in `routes/admin.py`), §21 Notifications feed (`account_nudges` +
  `nudges_bp` + `_account_nudges.html`).
- **Canvas is read-only by design** (React 18 + Babel-standalone from `unpkg`,
  inline `<style>`/`text/babel`). It cannot be served under the app CSP — which
  is exactly why the rule is "translate to Jinja, don't transplant the JSX."

---

## 6 · Corrected phase sequence

Unchanged from `BUILD_PLAN.md` §3 except for the annotations below.

| Phase | Original | Correction applied |
|---|---|---|
| 0 — Foundation | port tokens/polish, sprite, CSP flag | **Add the token-collision reconciliation (§1). Update DoD: inert for legacy, not byte-for-byte after a naïve copy.** |
| 1 — App shell | sidebar/topbar/tabbar; dashboard proof | Use real endpoint names (§3a). Build sprite from `shell.jsx`'s `I` set (33 icons enumerated there). |
| 2 — Daily loop | dashboard, plan week, workout, log, wellness | §06 plan week = `plans.view_plan(plan_id)` (legacy model). |
| 3 — Plan lifecycle | gen, races, history, compare, refresh, import | **Spike first: map each screen to legacy vs v2 plan model (§3b).** §04 uses `plan_versions`/`plan_create`. |
| 4 — Library + Account | exercises, locations, connections, profile, account, coach memory | Decide `references`/`ad_hoc_workouts` placement (§4). |
| 5 — System | notifications, **settings**, ⌘K, shortcuts, admin | **§21 feed: build. §22 settings: defer until backend added (§2).** |
| 6 — States + Polish | empty, error, light mode, a11y, print | Light mode = the `.app`/token vocabulary from §1; `polish.css`'s `body.board-light` → production `body.theme-light`. |
| 7 — Cleanup | retire `coaching_bp` into `plan_refresh` | Confirmed both blueprints exist; valid cleanup. |

---

## 7 · Recommended first PR (Phase 0, corrected)

1. Add `static/tokens.css` (ported), **namespaced under `.app`** per §1 Option A;
   header documents the `.screen`→`.app` rename and the `--ink` value delta.
2. Fold `polish.css` into `static/style.css`, namespaced under `.app`; rename
   `body.board-light` → `body.theme-light` (defined, inert until Phase 6).
3. Add `templates/_shell/icons.svg` sprite from `shell.jsx`'s `I` set
   (`.sprite-host` class for positioning — no inline style, CSP-clean).
4. Document `CSP_REPORT_ONLY=1` for dev in the README (the `.env.example` entry
   already exists).
5. **DoD:** legacy screens unchanged (spot-check dashboard, a form, plan view);
   token system live only under `.app`; CSP enforced, zero console violations;
   app cold-starts clean against Postgres.

Keep it small and boring — its only job is to make Phase 1 a layout-only change,
**without** disturbing any screen still on the legacy shell.
