# V5 Implementation — #619 Navigation & profile information-architecture cleanup — Closing Handoff

**Date:** 2026-06-16
**Issue:** [#619](https://github.com/ahorn885/exercise/issues/619) — CLOSED completed.
**PRs (all MERGED to `main`):** [#655](https://github.com/ahorn885/exercise/pull/655) sidebar/nav · [#656](https://github.com/ahorn885/exercise/pull/656) supplements tab + Save spacing · [#657](https://github.com/ahorn885/exercise/pull/657) Data page + Schedule theming · [#658](https://github.com/ahorn885/exercise/pull/658) Locations tab.
**Branches:** `claude/jolly-noether-hdom2m` (#655), `claude/jolly-noether-profile-tabs` (#656), `claude/jolly-noether-data-polish` (#657), `claude/jolly-noether-locations-tab` (#658).

---

## 1. What shipped

Pure UI/IA cleanup from Andy's 2026-06-15 walkthrough — no schema/prompt/HITL triggers. Andy chose **whole issue, sliced into PRs** (`AskUserQuestion`). Sliced by **file boundary** (cleaner than the issue's literal grouping), so each PR stayed under the file ceiling and self-merged on green.

**(1) Sidebar / nav IA — #655.** `_shell/sidebar.html`: **Athlete** → the profile chit dropdown (first item); **Data** → the **Log** section (after Wellness); the **Account** section now holds **Locations** only. `_shell/mobile_drawer.html`: **Data** → the drawer's **Log** section (Athlete already sat with the profile-menu items in the drawer's Account section — the mobile equivalent of the desktop chit). The mobile tabbar's Athlete tab is the 5-tab bar, not the Account grouping — left untouched. `cmdk.html` is a flat searchable palette (not an IA grouping) — left as-is.

**(2) Profile supplements tab + Save spacing — #656.** The structured **Current supplements**, **Health conditions**, and **Medications** capture cards moved out of the Athlete tab into a new **Supplements** sub-tab (`?tab=supplements`), extracted to `templates/profile/_health_tab.html`. `profile.edit` already loads all those context vars on every tab, so **no route change**. The **Nutrition & fueling** card (part of the main profile `<form>`) and the **active-plan daily baseline** stay on the Athlete tab. Added `.app .pf-form + .pf-form { margin-top: 16px }` so the main profile form's *Save profile* button no longer butts against the discipline-weighting card (consecutive `<form>`s don't share the flex gap).

**(3) Data page + Schedule theming — #657.** Removed the read-only **Preferences** tab (`connections/hub.html` + `routes/connections.py` `VALID_TABS` → `('sources','files')`; the Files branch became the `{% else %}` so Sources stays default; `?tab=prefs` now falls back to Sources; the prefs section + its now-orphaned `.conn-prefs`/`.pref-facts` CSS removed). **Sources providers ~3-per-row**: `.provider-list` became an auto-fill grid `repeat(auto-fill, minmax(260px, 1fr))` (≈3 across desktop, 1 column narrow). **Schedule "jarring white background"**: root-caused as native form controls (checkboxes/radios + native `time`/`number` inputs) ignoring token colors and painting in the UA's *light* scheme against the dark-primary `.app` theme — fixed in `static/tokens.css` with `color-scheme: dark` + `accent-color: var(--accent)` on `.app` and `color-scheme: light` under `.theme-light .app`. This is a **global theme-correctness** change (all native controls/scrollbars now match the active theme); the Schedule tab is just where it was most glaring.

**(4) Locations as a profile tab — #658.** New `?tab=locations` embeds the **full** locales surface (card grid with edit/refresh/make-home/delete + the "Add another location" card, or the empty "Where do you train?" hero) — Andy chose **embed full surface** (`AskUserQuestion`). Extracted `routes.locales.build_locales_list_context(db, uid)` (shared by the standalone `locales.list_profiles` view + the profile tab) and `templates/locales/_list_body.html` (included by both `locales/list.html` and `profile/edit.html`'s locations branch — one source of truth). `profile.edit` builds the locales context **only when `?tab=locations` is active** (avoids the per-locale equipment-tag queries on every profile view); local import dodges a `routes.locales`⇄`routes.profile` cycle. Per-card actions still navigate to the existing `locales` edit/new pages.

**NO DDL, no prompt/vocab/cache-key changes, no changed route behavior** beyond the prefs-tab removal. Tests stayed green across the affected suites (216 / 143 / 394 passed locally per slice).

## 2. Profile tab order (as shipped)

`Athlete · Supplements · Schedule · Skills · Locations` (`?tab=` server-rendered, CSP-clean). Validation set in `templates/profile/edit.html` line 11.

## 3. GitHub issues

- **#619** — CLOSED completed (the 4 PRs above).
- No new issues filed (clean UI work; nothing discovered mid-session).

## 4. Owed / next

- ⬜ **STILL OWED (carried, unrelated):** the post-#572 live **T3 *refresh*** re-verify (Rule #14 — needs Andy to paste prod logs / the diag token).
- ⬜ **Eyeball the Schedule `color-scheme` fix on the live preview** — couldn't screenshot in-session. Confirm native controls (checkboxes/radios/date-time/number, scrollbars) read right in **both** themes and that no other screen's native controls now look off (the change is global on `.app`).
- The "Locations & Gear" arc is effectively complete. New functionality remaining: #592 race terrain/weather, #593 reduced-volume travel days; larger v2 tracks #427/#428/#429 (determinism-first plan-gen epic), #316 (plan-gen latency).

## 6.3 Operating notes (Rule #13 read order)

1. `CLAUDE.md` — stable rules + Environment → Ops automation reference. 2. `CURRENT_STATE.md` — top entry = this session (#619). 3. `CARRY_FORWARD.md` — Ops automation / operating model section + carried items. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Sidebar IA | `templates/_shell/sidebar.html` | chit dropdown 1st item `profile.edit` "Athlete"; `nav-log` `<ul>` includes `connections.hub` "Data"; `nav-account` `<ul>` = `locales.list_profiles` "Locations" only |
| Mobile drawer | `templates/_shell/mobile_drawer.html` | `dnav-log` includes `connections.hub` "Data"; Athlete stays in `dnav-account` |
| Supplements tab | `templates/profile/edit.html` | `sub` set includes `'supplements'` + `'locations'`; tablist has both; `{% elif sub == 'supplements' %}{% include 'profile/_health_tab.html' %}` |
| Health partial | `templates/profile/_health_tab.html` | Current supplements / Health conditions / Medications cards (the 3 add/delete forms) |
| Save spacing | `static/style.css` | `.app .pf-form + .pf-form { margin-top: 16px; }` |
| Prefs removed | `routes/connections.py` | `VALID_TABS = ('sources', 'files')` |
| Prefs removed (tmpl) | `templates/connections/hub.html` | no `('prefs', …)` tab; no `conn-prefs`; Files is the `{% else %}` |
| 3-per-row | `static/style.css` | `.app .provider-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); … }` |
| Schedule theming | `static/tokens.css` | `.app { … color-scheme: dark; accent-color: var(--accent); }`; `.theme-light .app { … color-scheme: light; }` |
| Locations tab — ctx | `routes/locales.py` | `def build_locales_list_context(db, uid)`; `@bp.route('/locales')` directly precedes `def list_profiles` |
| Locations tab — route | `routes/profile.py` | `if request.args.get('tab') == 'locations':` builds `locales_ctx`; `**locales_ctx` in `render_template` |
| Locations tab — body | `templates/locales/_list_body.html` | loc-grid / empty hero; `locales/list.html` + `profile/edit.html` both `{% include %}` it |
| Tests | `tests/test_redesign_profile_render.py`, `…connections_render.py` | supplements/health tests query `?tab=supplements`; `test_profile_locations_tab_embeds_locales_surface`; prefs test → fallback-to-sources |
| Issue | #619 | CLOSED completed (4 PR refs) |
| Owed | — | T3-refresh re-verify carried; eyeball Schedule color-scheme on live preview |
