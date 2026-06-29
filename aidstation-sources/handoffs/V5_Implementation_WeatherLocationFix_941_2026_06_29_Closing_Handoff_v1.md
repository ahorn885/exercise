# V5 Implementation — Weather/Clothing Location Fix + city Retirement (#941) — Closing Handoff (2026-06-29)

**Branch:** `claude/issue-941-hbsbzt` · **PR:** [#980](https://github.com/ahorn885/exercise/pull/980) (open, Vercel green) · **Issue:** #941 (priority:high, type:bug) · **Suite:** targeted suites green (locales + event-windows + render = 138 passed); full suite not run in this container (deps installed ad-hoc), CI/Vercel deploy green on the PR head.
**Context:** Andy's feedback checklist (Plan-82 #1, Today-view #2, Equipment #4). Weather/clothing rendered for the **wrong place** — home conditions while the athlete was at a travel/event-window location.

> **▶ IMMEDIATE NEXT: merge #980 (merge commit, per #985 convention). The `DROP COLUMN city` + manual-address backfill are public-schema (`init_db._PG_MIGRATIONS`) → auto-apply on deploy, NO Neon/layer0 apply owed. Legacy manual-entry locales (no geocode) resolve no weather until re-anchored via the `?upgrade=<slug>` flow.**

---

## 1. The problem (one line)

Weather/clothing resolved off the free-text `locale_profiles.city`, which travel locales routinely left blank, so the `away` event-window logic's empty-city fall-through silently deferred to the **home** city.

## 2. Root cause

- `resolve_weather_city()` (event-windows repo) and the dashboard/plan clothing read-sites keyed on `locale_profiles.city` (free text). An `away` window whose destination had no typed `city` fell through to the preferred-home city by design — so a Mapbox-anchored travel locale with no typed city showed home weather.
- The Mapbox-anchored `lat`/`lng` are captured on every geocoded locale (and `race_events` already resolves race-week weather off `event_locale_lat/lng` via Open-Meteo), so the precise location was already on the row — just unused for the locale/event-window weather path.

## 3. What shipped

**A — Repoint weather/clothing onto Mapbox lat/lng (the bug fix).**
- `athlete_event_windows_repo.py`: `resolve_weather_city` → **`resolve_weather_location(db, uid, on_date) -> str`**, returning a bare `"lat,lng"` token (wttr.in + Open-Meteo accept it; `_latlng_token` formats to 4 dp). Away-window destination's `lat`/`lng` wins; else preferred-home coords; else `''` (caller's `WEATHER_LOCATION` env fallback). The home fall-through now only fires when a destination has **no coordinates at all** (rare — e.g. a legacy manual row), not a blank typed city.
- `routes/dashboard.py` (`_get_weather` + the clothing block) and `routes/plans.py` thread the location token through; `coaching.get_coaching_context` exposes `locale_weather_location` (from the review locale's `lat`/`lng`) and `run_review` / `get_clothing_context` consume it (param renamed `city`→`location`).
- `race_events` weather path unchanged — already on Mapbox coords.

**B — Retire the redundant `city` field (Equipment #4).**
- `routes/locales.py`: dropped `city` from the edit-profile upsert + render; `coaching.py` no longer reads it.
- `init_db.py`: `ALTER TABLE locale_profiles DROP COLUMN IF EXISTS city`, preceded by an idempotent `DO $$` backfill that lifts any manual-entry row's typed `city` into `place_payload` (Mapbox-feature shape) so `_display_address` still renders it. Public-schema → auto-applies on deploy.
- `templates/locales/form.html` + `_list_body.html`: city field + list cell removed. `DATABASE.md` updated.

**C — Force Mapbox-anchored locations; retire coordinate-less manual entry (Andy 2026-06-29).**
- Manual entry was the only path that created a locale with no `lat`/`lng` — the exact "empty location" that can't resolve weather. Removed the `save_manual_locale` route and the manual-entry state from `locales/new.html` (form, the search-form + disclosure-gate "manual" links, and the manual-only privacy `<script>`); dropped the `?manual=1` branch in `new_locale`; error copy no longer points at a manual fallback.
- **Kept** the `?upgrade=<slug>` flow so any legacy manual rows can be re-anchored to Mapbox.

## 4. Notes / decisions

1. **Scope (Andy, AskUserQuestion):** "Full fix" — repoint **and** retire the column (not deprecate-in-place), accepting that un-geocoded locales degrade to the env weather default.
2. **All-Mapbox (Andy, AskUserQuestion):** "Retire manual entry entirely" rather than geocode-the-typed-address. Trade-off accepted: if Mapbox is down/unconfigured or can't find a place, there's no add-location fallback until it's reachable. The geocode-the-address path is the natural escape hatch if this ever bites.
3. **`MANUAL_CATEGORIES`** stays defined (it's the canonical category-slug set `locations.py` references); only its consumer (the manual form) was removed.

## 5. Tests + verification

- `tests/test_athlete_event_windows_repo.py` rewritten: resolver now asserts lat/lng precedence (away beats home), the missing-coordinate fall-through, and the `''` no-coords case. `tests/test_locales.py` upsert-param-shape assertions retuned (city dropped). `tests/test_redesign_locales_form_render.py` — manual-render test removed; the gate + search tests now assert **no** manual path. `tests/test_redesign_locales_list_render.py` city fixtures dropped.
- After merging `origin/main` (10 commits incl. #982–#985) into the branch — **clean auto-merge, no conflicts** — targeted suites pass: `test_athlete_event_windows_repo` + `test_locales` + `test_layer4_event_windows` = 118 passed; the two redesign render suites = 20 passed.
- **No Neon/layer0 apply owed** (public-schema migration auto-applies on deploy).
