# V5 Onboarding Implementation PR10 — Closing Handoff

**Session:** Tenth substantive code session of the v5 onboarding implementation arc. Executes PR9 §5.1's recommended next — **Option D3a (Mapbox-anchored locale creation + chain detection + nearby same-chain picker + manual fallback + privacy disclosure)** — closing the first half of D-59. Ships a new `mapbox_client.py` module wrapping the Mapbox Geocoding API + extends `routes/locales.py` with five new routes + adds two new templates and updates the locales list template to render athlete-created rows. Flips v21→v22 backlog per PR9 §5.4 mechanical spec; D-59 status cell flips 🟡 → 🟢 D3a (D3b for D-60 inherit/override + D-59 §7 refresh stays pending).
**Date:** 2026-05-15
**Predecessor handoff:** `V5_Implementation_PR9_Closing_Handoff_v1.md` (its §5.1 Option D3 carved out into D3a (this PR) + D3b (deferred); its §5.4 v21→v22 backlog bump runs here per Rule #11 mechanical spec).
**Branch:** `claude/review-v5-pr9-handoff-Xdt7Q` (per-session feature branch off `main`; PR9 was merged into `main` as `7cb786a` via PR #41 before this session started).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 live Mapbox round-trip + chain-detect + nearby picker + dismiss/manual flows + 401-on-no-token + Vercel `MAPBOX_PUBLIC_TOKEN` env-var setup owed at deploy time (no Flask + no Mapbox network in sandbox, same gap as PR1–PR9).
**Time-on-task:** Single chat. Substantive files: **5** (`mapbox_client.py` new, `routes/locales.py` edit ~+200 lines, `templates/locales/new.html` new, `templates/locales/nearby.html` new, `templates/locales/list.html` edit). Plus the v21→v22 backlog bump (`Project_Backlog_v22.md` new copy + 1-line `CLAUDE.md` edit) and this handoff = 7 total. At the substantive-file ceiling.

---

## 1. Session-start verification (Rule #9)

Verified the PR9 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/review-v5-pr9-handoff-Xdt7Q` clean off post-PR9 `main`; PR9 merged to `main` as `7cb786a` via PR #41 (PR9 commit `5f5b41b`) | `git status` + `git log --oneline -10` | ✅ Verified |
| `routes/nudges.py` exists (185 lines) with `scan_connect_provider_14d` + `dismiss` + `get_active_nudges` + `_cron_authorized` + `NUDGE_REGISTRY` | wc + grep | ✅ Verified |
| `templates/_account_nudges.html` exists (28 lines) with the dismiss form | wc + grep | ✅ Verified |
| `templates/base.html:122` includes `_account_nudges.html` between flashes and `{% block content %}` | grep | ✅ Verified |
| `app.py:151,181,232,307` imports `nudges_bp` + `get_active_nudges`, registers blueprint, exempts `nudges.scan_connect_provider_14d`, defines `_inject_active_nudges` | grep | ✅ Verified |
| `vercel.json` has `crons` array with path=`/cron/nudges/connect_provider_14d`, schedule=`0 14 * * *` | cat + grep | ✅ Verified |
| `Project_Backlog_v21.md` exists with v20 archived to predecessor block; D-50 row reflects PR1–PR9 shipped; CLAUDE.md `Authoritative current files` backlog line reads v21 | grep | ✅ Verified |
| `chain_registry.py` (PR2) exists with `GYM_CHAINS` (32 entries) + `detect_chain(text)` helper | cat | ✅ Verified |
| `disclosure_acknowledgments` table in `init_db.py:_PG_MIGRATIONS` (PR1 D-58 batch); shape matches D-59 §8 needs (`disclosure_id`, `version_id`, `delivery_method`, `acknowledged_at`) | grep + read | ✅ Verified — no schema change needed for PR10 |
| `locale_profiles` Mapbox columns (`locale_name`, `mapbox_id`, `lat`, `lng`, `chain_id`, `chain_name`, `category`, `manual_entry`, `place_payload`, `place_fetched_at`) all in `_PG_MIGRATIONS` (PR2 D-59 batch) | grep | ✅ Verified — no schema change needed for PR10 |
| `routes/locales.py` (pre-PR10) has only the legacy `LOCALES = ['home','hotel','partner','airport']` enum-bound `list_profiles` + `edit_profile` routes | cat | ✅ Verified |
| Pre-existing PR1 bug noted: `locale_equipment_overrides.locale_id REFERENCES locale_profiles(id)` (init_db.py:1901) targets a column that doesn't exist on `locale_profiles` (composite PK is `(user_id, locale)`) | grep | ⚠️ Surfaced as Open Item; out of scope for PR10 |

**No drift between PR9 handoff narrative and on-disk state** (other than the pre-existing FK bug, which is independent of D-50 wiring).

Stop-and-ask trigger #8 (architectural alternatives) was hit twice this session, both before any code: (a) privacy disclosure handling — Andy chose "build it properly" via the existing `disclosure_acknowledgments` table (no new schema, just write rows with `disclosure_id='mapbox_geocoding_consent'`); (b) nearby-instance discovery — Andy chose to include in D3a rather than defer to D3b. Both choices pushed substantive file count to exactly 5 (the ceiling) but kept the work coherent.

---

## 2. Files shipped this turn

All on branch `claude/review-v5-pr9-handoff-Xdt7Q`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `mapbox_client.py` | New (~170 lines) | New module — Mapbox Geocoding API wrapper. Public surfaces: (a) typed exception hierarchy `MapboxError` → `MapboxTokenMissing` / `MapboxAPIError` / `MapboxNoResults` so routes can render specific inline messages without parsing exception strings. (b) `search_places(query, limit=5)` → forward geocoding for /locales/new search box (D-59 §3.1 row 1; `autocomplete=true, types=poi,address`). (c) `search_nearby(query, lng, lat, radius_km=42.2, limit=10)` → proximity search for nearby chain instances (D-59 §3.1 row 2 + §5; `proximity={lng},{lat}, bbox={derived}, types=poi`). (d) `_normalize_feature(feature)` → projects raw Mapbox JSON down to `{mapbox_id, text, place_name, lng, lat, category, raw_payload}` so callers never touch raw JSON except via `raw_payload` for audit storage on `locale_profiles.place_payload`. (e) `_bbox(lng, lat, radius_km)` → computes Mapbox bbox string from radius using rough degrees-per-km math (`1° lat ≈ 111 km`, `1° lng ≈ 111 × cos(lat) km`). Token via `MAPBOX_PUBLIC_TOKEN` env var (D-59 §3.2; PR9 §5.1 names this var). 1-retry on 5xx with 1s backoff per D-59 §3.4 row 3; 4xx + persistent 5xx + network errors raise `MapboxAPIError`; 0-results raises `MapboxNoResults`; missing env var raises `MapboxTokenMissing` before any HTTP call. 5-second request timeout. |
| 2 | `routes/locales.py` | Edit (~+200 lines net) | (a) Imports `mapbox_client`, `chain_registry.{GYM_CHAINS, detect_chain}`, `database` (for `_is_postgres()` guard). (b) Constants: `MAPBOX_DISCLOSURE_ID = 'mapbox_geocoding_consent'`, `MAPBOX_DISCLOSURE_VERSION = 'v1'`, `MANUAL_CATEGORIES` tuple (7 entries from D-60 §3 taxonomy). (c) Helpers: `_slugify(name)` (alnum-only lowercase + `_` separator, 48-char cap), `_unique_slug(db, uid, base)` (collision-suffix on `(user_id, locale)` PK), `_disclosure_acked(db, uid)` (PG-only SELECT against `disclosure_acknowledgments`; SQLite returns True so dev doesn't gate), `_record_disclosure_ack(db, uid)` (PG-only INSERT — re-acks write fresh rows per init_db.py:1842 comment). (d) `list_profiles` extended: builds `displayed_locales = list(LOCALES) + sorted(set(profiles.keys()) - set(LOCALES))` so athlete-created rows appear alongside the 4 legacy enums; passes both `locales` (display order) and `legacy_locales` (set) to template. (e) `edit_profile` extended: legacy enums still auto-create on UPSERT; non-enum slugs require an existing row for the user (existing-row check before redirect-with-flash on miss). (f) `GET /locales/new` (`new_locale`): renders `templates/locales/new.html` with branches for disclosure / manual fallback / search form / search results. Calls `mapbox_client.search_places(query)` when `?q=...` is set and disclosure is acked; catches `MapboxTokenMissing` / `MapboxNoResults` / `MapboxError` with specific inline error strings. (g) `POST /locales/new` (`_save_mapbox_anchored`): INSERTs `locale_profiles` row from selected Mapbox feature; runs `chain_registry.detect_chain(text)`; chain-hit → category from registry, redirect to `/locales/<slug>/nearby`; no-chain → category derived from Mapbox `properties.category` hint per D-59 §4.2 step 3 (`gym`/`fitness`/`climbing` → `'independent_gym'` else NULL); always redirects (POST-redirect-GET pattern preserved). (h) `POST /locales/new/manual` (`save_manual_locale`): D-59 §6 — INSERT with `manual_entry=TRUE`, `mapbox_id IS NULL`, no coords, athlete-picked category (validated against `MANUAL_CATEGORIES` whitelist). (i) `POST /locales/new/acknowledge` (`acknowledge_mapbox_disclosure`): records consent row, redirects back to `/locales/new?q=<original-query>` so the search resumes. (j) `GET /locales/<locale>/nearby` (`nearby_instances`): re-fetches Mapbox via `search_nearby(canonical_name, anchor.lng, anchor.lat)`; filters same-chain via `detect_chain()` re-application; excludes anchor by `mapbox_id` match (D-59 §5 step 4); renders `templates/locales/nearby.html`. Fail-open on Mapbox error: anchor row already saved, just skip the surface. (k) `POST /locales/<locale>/nearby`: re-runs the search + same-chain filter; INSERTs one `locale_profiles` row per opt-in checkbox (`request.form.getlist('mapbox_id')` matched against re-fetched feature list). |
| 3 | `templates/locales/new.html` | New (~110 lines) | One template, three branches via {% if manual %} / {% elif not acked %} / {% else %} : (a) Manual: form with `locale_name` (required) + `address` (optional textarea) + `category` dropdown from `MANUAL_CATEGORIES`. (b) Disclosure card: D-59 §8 disclosure copy + Acknowledge form (POST to `/locales/new/acknowledge` with hidden `q` field carrying the search input through the ack roundtrip) + "Use manual entry instead" link. (c) Search: GET form for the `q` parameter; "or enter address manually" link; conditional `error` alert; conditional results section with one card per Mapbox feature, each containing all hidden mapbox_id/lat/lng/text/place_name/mapbox_category/raw_payload fields + an editable `locale_name` text input prefilled with `feature.text` + a "Save this" submit button. No JS. CSRF token in every form per CSRFProtect global. |
| 4 | `templates/locales/nearby.html` | New (~30 lines) | Renders header naming the chain + anchor name; intro paragraph reading "We found N other {chain} location(s) within 42 km of {anchor}"; one Bootstrap form-check per same-chain candidate with the `mapbox_id` as the checkbox value + `text` (place name) + `place_name` (full breadcrumb) as label; "Add selected" submit + "Skip — done" link. Empty-list path renders a plain "No same-chain matches" with a back link. |
| 5 | `templates/locales/list.html` | Edit (~+15 lines) | Adds "+ New locale" button to the header row. Adapts the per-card header to either show the legacy enum name (capitalised, `text-capitalize`) for `is_legacy = locale in legacy_locales` or render `locale_name` + chain badge / category badge / "manual" badge for athlete-created rows. Existing equipment-tag rendering + city + updated-at + notes preserved verbatim. |
| — | `aidstation-sources/Project_Backlog_v22.md` | New (copy of v21 + 4 surgical edits per PR9 §5.4 mechanical spec) | **File revision** header bumped v21→v22 with PR10 narrative (D-50 status flip catching up PR10 + D-59 status flip; PR9-merge placeholder filled with `7cb786a`). **Predecessor revisions** block prepends the v21 entry verbatim. **D-50 description column** updated: PR9's "(this revision)" annotation fixed to "(merge `7cb786a`)"; new "PR10 (this revision):" entry summarising D3a including `mapbox_client.py` + chain detection + manual fallback + nearby picker + disclosure path + the existing-row gate change in `edit_profile`. **D-50 status cell** rewritten: 🟢 PR1–PR10 shipped; D3a listed as shipped; D3b/F/H/D2c/E-telemetry kept pending; `<PR9-merge-pending>` replaced with `7cb786a`. **D-50 Notes column** rewritten: handoff pointer flipped to `V5_Implementation_PR10_Closing_Handoff_v1.md`; PR10+ → PR11+ candidate menu; D3 split into "D3a shipped" (removed from menu) + "D3b pending" (added); recommended sequence flipped to "D3b is the next D-50 step"; PR10-specific pre-deploy verification block (j-step) appended. **D-59 row** updated: status cell flipped 🟡 Implementation pending → 🟢 D3a shipped (D3b pending); Notes column expanded to enumerate what PR10 shipped vs what D3b owes. |
| — | `aidstation-sources/CLAUDE.md` | Edit (1-line) | Per PR9 §5.4 step 5: "Authoritative current files" backlog line bumped from `Project_Backlog_v21.md` to `Project_Backlog_v22.md`. Single-line edit, same shape as the v20→v21 bump PR9 did. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR10_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `init_db.py` — unchanged. `disclosure_acknowledgments` (PR1 D-58 batch, init_db.py:1848) and the 10 Mapbox/chain columns on `locale_profiles` (PR2 D-59 batch, init_db.py:1865-1874) are already in `_PG_MIGRATIONS`. **Pre-existing bug surfaced but not fixed:** `locale_equipment_overrides.locale_id REFERENCES locale_profiles(id)` (init_db.py:1901) targets a column that doesn't exist (composite PK is `(user_id, locale)`). Fresh PG schema applies would fail; existing deploys with the table already created don't validate the FK. Out of scope for D3a — flagged for D3b or a follow-on fix PR.
- `app.py` — unchanged. `locales` blueprint already registered at app.py:161; no auth-exemption needed (all new routes are session-authed).
- `chain_registry.py` — unchanged. PR2-shipped; `detect_chain()` consumed verbatim.
- `database.py` — unchanged. Standard `?` placeholder + `_is_postgres()` guard pattern.
- `requirements.txt` — unchanged. `requests>=2.31` already present.
- `vercel.json` — unchanged. PR9's `crons` block stays as-is.
- `routes/onboarding.py` / `routes/profile.py` / `routes/nudges.py` — zero edits. PR10 is locale-flow scoped.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1–PR9 used.

---

## 3. What landed

### 3.1 `mapbox_client.py` — Mapbox Geocoding wrapper

D-59 §3 spec: forward geocoding only (no reverse); two endpoints differ only by query params; `MAPBOX_PUBLIC_TOKEN` env var; 5xx + network errors retry once with 1s backoff; 4xx fails fast; 0-results raises typed exception so caller can render specific message.

```python
def search_places(query: str, limit: int = 5) -> list[dict]:
    payload = _request(query, {
        'autocomplete': 'true',
        'types': 'poi,address',
        'limit': str(limit),
    })
    features = payload.get('features') or []
    if not features:
        raise MapboxNoResults(f'no matches for {query!r}')
    return [_normalize_feature(f) for f in features]


def search_nearby(query, lng, lat, radius_km=42.2, limit=10):
    payload = _request(query, {
        'proximity': f'{lng},{lat}',
        'bbox': _bbox(lng, lat, radius_km),
        'types': 'poi',
        'limit': str(limit),
    })
    # … same shape as search_places
```

`_normalize_feature(f)` returns `{mapbox_id, text, place_name, lng, lat, category, raw_payload}` — `raw_payload` is `json.dumps(f)` so the route can stuff it straight into `locale_profiles.place_payload` for audit. Caller never touches raw Mapbox JSON otherwise.

`_bbox(lng, lat, radius_km)` math: `lat_delta = radius_km / 111.0`, `lng_delta = radius_km / (111.0 × cos(radians(lat)))`. Square overshoots the circular radius at the corners but undershoots nothing — chain instances inside the radius are guaranteed inside the bbox. Verified against Minneapolis (lat=44): 42.2 km → ±0.380° lat, ±0.529° lng.

`_get_token()` raises `MapboxTokenMissing` before any HTTP call so a misconfigured deploy fails loud + fast (the route catches this and renders "Place lookup is not configured on the server"). 5-second request timeout per call; 1-retry on 5xx with 1s backoff; both retries exhausted → `MapboxAPIError`.

### 3.2 Disclosure path (D-59 §8)

PR1's D-58 batch already shipped `disclosure_acknowledgments` (init_db.py:1848-1857) — single shared table for OAuth scope acks + Mapbox consent. Schema:

```sql
CREATE TABLE disclosure_acknowledgments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    disclosure_id TEXT NOT NULL,
    version_id TEXT,
    scopes_granted TEXT,
    delivery_method TEXT NOT NULL DEFAULT 'in_app',
    acknowledged_at TIMESTAMP NOT NULL DEFAULT NOW()
)
```

PR10 writes `(user_id, 'mapbox_geocoding_consent', 'v1', NULL, 'in_app', NOW())` on first ack. The check is `SELECT 1 WHERE user_id=? AND disclosure_id=? AND version_id=?` — if any row exists for the current `(user, version)`, the disclosure is treated as acked. Re-acks write fresh rows; no UPDATE; the comment at init_db.py:1842 explicitly says "Re-acknowledgment writes a new row; query MAX(acknowledged_at) per (user_id, disclosure_id) to find current state."

Bumping `MAPBOX_DISCLOSURE_VERSION` from `'v1'` to `'v2'` (e.g. when the disclosure copy materially changes) re-prompts every athlete because the LIMIT 1 SELECT filters on version. No additional code needed for re-prompt.

PG-only — `_disclosure_acked` returns True on SQLite so dev doesn't gate. Disclosure ack writes are PG-only no-ops on SQLite.

### 3.3 Mapbox-anchored creation flow (D-59 §3 + §4)

Three-stage UX:

1. **GET /locales/new** — disclosure card if not acked (D-59 §8), else search form. If `?q=...` is set + acked, calls `mapbox_client.search_places(query)` and renders results below the form. Token-missing → inline "not configured" message; 0-results → inline "no matches" guidance; other errors → inline "place lookup unavailable".
2. **POST /locales/new** — selected feature's hidden fields (`mapbox_id`, `text`, `place_name`, `lng`, `lat`, `mapbox_category`, `raw_payload`) + an editable `locale_name` (default = `feature.text`). Server-side: `_slugify(locale_name)` → `_unique_slug` (collision-suffix on `(uid, slug)` PK); `chain_registry.detect_chain(text)` for category; INSERT row with `manual_entry=FALSE`, `place_payload=raw_payload`, `place_fetched_at=NOW()`. Chain-hit → redirect to `/locales/<slug>/nearby`; no-chain → redirect to `/locales`.
3. **GET/POST /locales/<slug>/nearby** — see §3.5.

D-59 §4.2 step 3 implementation: when `detect_chain()` returns None, derive `category` from Mapbox `properties.category` hint:
- `'gym'` / `'fitness'` / `'climbing'` substring → `'independent_gym'`
- otherwise → NULL (the locale isn't a gym at all — could be home, hotel, park, etc.)

This is exactly the spec's "no-defaults case" for D-60 to later read.

### 3.4 Manual fallback (D-59 §6)

`POST /locales/new/manual` writes `manual_entry=TRUE`, `mapbox_id=NULL`, `lat=NULL`, `lng=NULL`, athlete-typed category from `MANUAL_CATEGORIES` whitelist (server-side validation rejects unknown values). Address goes into `city` (existing column reused — no new migration).

UI path: `/locales/new?manual=1` renders the manual form instead of the search form. Cross-link from each branch lets athletes flip back to the other ("Use place lookup instead" / "enter address manually").

D-59 §6 step 3 ("Athlete edits the locale and clicks Look up on map" upgrade path) is **deferred to D3b** — the upgrade flow needs to UPDATE an existing row's columns from NULL → coords, which means either a separate route or extending `edit_profile`. PR10 ships the create-only path.

### 3.5 Nearby-instance picker (D-59 §5)

After a chain-anchored save, athlete redirects to `/locales/<slug>/nearby`. Server flow:

1. Look up the anchor row by `(user_id, locale)` PK.
2. Resolve canonical chain name from `chain_registry.GYM_CHAINS` (fallback to stored `chain_name` if registry entry missing — the `_canonical_name(chain_id)` helper handles this).
3. Call `mapbox_client.search_nearby(canonical, anchor.lng, anchor.lat)` — Mapbox proximity query with `bbox` from `_bbox()` over the 42.2 km marathon-radius (D-59 §3 row 3).
4. Filter results: keep only same-chain matches (re-run `detect_chain(f.text)` per result); exclude the anchor itself by `mapbox_id` match (D-59 §5 step 4).
5. Render `templates/locales/nearby.html` with one checkbox per same-chain candidate.
6. POST: `request.form.getlist('mapbox_id')` → set of opted-in IDs; re-fetch the same proximity result list (1 extra Mapbox call vs. encoding all feature data in hidden fields — picked for cleanliness over hidden-field bloat); INSERT one `locale_profiles` row per opt-in match with `chain_id`/`chain_name`/`category` inherited from the anchor.

Fail-open on Mapbox error: the anchor row is already saved; if nearby search fails, we flash an info message and redirect to `/locales`. Athletes can re-attempt the nearby flow later via a route revisit (deferred — no UI link today; D3b candidate).

### 3.6 List-view extension (athlete-created locales)

`/locales` list previously iterated `LOCALES = ['home', 'hotel', 'partner', 'airport']` only — athlete-created rows from `/locales/new` would have rendered as ghost rows (in `profiles` dict but not iterated). PR10 builds:

```python
custom_locales = [k for k in profiles.keys() if k not in LOCALES]
custom_locales.sort()
displayed_locales = list(LOCALES) + custom_locales
```

Template renders all entries in one grid. Per-card header logic differentiates legacy enums (`text-capitalize` of the slug) from athlete-created rows (`locale_name` if set + chain badge `bg-info` / category badge `bg-secondary` / "manual" badge `bg-light`).

`edit_profile(<locale>)` extended to accept athlete-created slugs alongside the enum. The legacy gate `if locale not in LOCALES: redirect` is replaced by `if locale not in LOCALES and not _row_exists(uid, locale): redirect`. Athlete-created rows must already exist (created via /new) before they can be edited.

### 3.7 NOT shipped — D3b carve-outs

Carved out of D3a per the 5-file ceiling:

- **D-60 inherit/override/dispute UI** — shared `gym_profiles` + `locale_equipment_overrides` + `locale_toggle_overrides` already shipped as PR2 schema; UI to read/write them is a fresh template + route work. ~3-4 files.
- **D-59 §7 "Refresh from Mapbox"** — per-locale link on the list view that re-fetches `place_payload` and offers Yes/No on chain-name change. ~1-2 files.
- **D-59 §6 "Look up on map" upgrade** — flip a `manual_entry=TRUE` row to Mapbox-anchored. ~1 file extending `edit_profile`.
- **D-61 per-day availability windows UI** — `daily_availability_windows` schema shipped PR2; §G frontend rewrite + JIT swap UI is open. ~3-5 files.

D3b spec recommends bundling the three D-59 closeouts (§6 upgrade + §7 refresh + D-60 UI) into one PR; D-61 likely warrants its own PR.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| `mapbox_client.py` AST-parses clean | `ast.parse` | ✅ Verified |
| `routes/locales.py` AST-parses clean after edits | `ast.parse` | ✅ Verified |
| `templates/locales/new.html`, `templates/locales/nearby.html`, `templates/locales/list.html` Jinja-parse cleanly | `Environment.get_template()` | ✅ Verified 3/3 |
| `mapbox_client.search_places('')` raises `MapboxNoResults`; `search_nearby('', 0, 0)` raises `MapboxNoResults`; `search_places('test')` raises `MapboxTokenMissing` when env var unset | Inline 3-case test | ✅ Verified 3/3 |
| `_bbox(-93.0, 44.0, 42.2)` produces lat_delta=0.7604 (=2·42.2/111), lng_delta=1.0570 (=2·42.2/(111·cos(44°))) | Inline math check | ✅ Verified |
| `_normalize_feature` extracts mapbox_id/text/place_name/lng/lat/category correctly + handles missing `center` array | Inline 2-case stub | ✅ Verified 2/2 |
| `_slugify` handles 8 cases (basic / unicode-strip / apostrophes / whitespace-only / punctuation-only / 60-char-truncation / uppercase / multi-space) | Inline 8-case stub | ✅ Verified 8/8 |
| `chain_registry.detect_chain` returns the right entry for known chains (Planet Fitness, YMCA, Movement) and None for unknown text + empty input | Inline 5-case stub | ✅ Verified 5/5 |
| `templates/locales/new.html` renders correctly across 5 variants: (1) disclosure path with Acknowledge + manual fallback link, (2) acked search form with no query, (3) acked with results showing 2 cards + hidden mapbox_id/lng/lat fields + "Save this" buttons, (4) acked with error showing alert-warning, (5) manual fallback with category dropdown + "use place lookup instead" link | Inline Jinja render | ✅ Verified 5/5 |
| `templates/locales/nearby.html` renders correctly across 3 variants: 2-candidate (correct grammar + checkboxes + per-instance mapbox_id values), empty-list (correct empty-state copy + back link), 1-candidate (singular grammar) | Inline Jinja render | ✅ Verified 3/3 |
| `Project_Backlog_v22.md` exists; v21 archived to predecessor block; D-50 row narrative + status cell + Notes column updated per PR9 §5.4 mechanical spec; PR9-merge placeholder filled with `7cb786a`; D-59 status flipped 🟡 → 🟢 D3a + 🟡 D3b pending | grep + visual | ✅ Verified |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads `Project_Backlog_v22.md` | grep | ✅ Verified |
| Flask not installed in sandbox + `MAPBOX_PUBLIC_TOKEN` not set + no Mapbox network access — full app import not exercisable; live Mapbox round-trips not exercisable | python3 import check | ⚠️ Same gap as PR1–PR9 + new dependency on Mapbox network. Live search + nearby + manual + disclosure round-trips owed at deploy time |

No drift between this handoff's narrative and on-disk state.

The same "can't exec the Flask app without Flask" gap PR1–PR9 flagged applies. PR10 also can't exercise the live Mapbox API — even with Flask, the sandbox has no `MAPBOX_PUBLIC_TOKEN` and would not have outbound HTTPS to Mapbox. AST + Jinja + Mapbox-client unit exercise + chain-registry unit exercise + slug exercise + multi-variant template render are the offline guards. The PR10 §5.0 live-checks below are mandatory before this PR is "real."

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR10 reaches production)

PR10 ships zero schema changes + 1 new external API dependency (Mapbox) + 5 new endpoints (4 session-authed POSTs + 2 GETs) + 2 new templates + 1 template extension. The risky bits are (a) the Mapbox token leak surface (D-59 §3.2 — public-scope `pk.*` tokens are intentionally less sensitive than secret-scope `sk.*` but should still be set per-environment, not committed), (b) the disclosure ack path (writes a row each time — exercise the version-bump scenario), and (c) the nearby-instance UX (re-fetches Mapbox on POST so cost-doubles per chain-anchor save).

1. **Schema is unchanged.** No migration to verify. `disclosure_acknowledgments` (PR1) + `locale_profiles` Mapbox columns (PR2) are already deployed.
2. **Env var setup.** Generate a Mapbox public token at mapbox.com (Account → Tokens → "Create a token", default scopes are fine, name it `aidstation-prod`). On Vercel: Project Settings → Environment Variables → add `MAPBOX_PUBLIC_TOKEN = pk.eyJ...`. Redeploy. Optional but recommended: same token on TrueNAS via `.env` so manual smoke can hit the dev path.
3. **Disclosure card on first visit.** Browse `/locales/new` while logged in. Expect: blue card with "Place lookup uses Mapbox" header + disclosure copy + "Acknowledge & continue" button + "Use manual entry instead" button. No search box yet.
4. **Acknowledge flow.** Click Acknowledge. Expect: page reloads to `/locales/new` (with `?q=` empty); now the search box appears (no card). `psql`: `SELECT * FROM disclosure_acknowledgments WHERE disclosure_id = 'mapbox_geocoding_consent'` shows one row for current user with `version_id='v1'`, `delivery_method='in_app'`, `acknowledged_at=NOW()`.
5. **Search happy path.** Type "Planet Fitness Minneapolis" → Search. Expect: ≤5 result cards; each shows feature `text` (bold) + `place_name` (small text) + Mapbox category badge if any + a "Locale name" input prefilled with the feature `text` + "Save this" button.
6. **Save chain-anchored.** Click "Save this" on a Planet Fitness result. Expect: redirect to `/locales/<slug>/nearby`. `psql`: `SELECT locale_name, mapbox_id, lat, lng, chain_id, chain_name, category, manual_entry, place_payload FROM locale_profiles WHERE user_id=<uid> AND locale=<slug>` shows the row with `chain_id='planet_fitness'`, `chain_name='Planet Fitness'`, `category='commercial_chain_gym'`, `manual_entry=FALSE`, `place_payload` is the JSON of the Mapbox feature.
7. **Nearby picker.** On the redirect target, expect: header "Nearby Planet Fitness locations" + intro "We found N other Planet Fitness location(s) within 42 km of <anchor>" + N checkbox rows (each with feature text + place_name); "Add selected" + "Skip — done" buttons. Click 2 checkboxes + Add. `psql`: 2 new `locale_profiles` rows with `chain_id='planet_fitness'`, distinct `mapbox_id`, distinct slugs (collision-suffix if same `text`).
8. **Save non-chain.** Search for a hotel name (e.g. "Marriott Minneapolis"). Click Save this. Expect: no nearby-redirect (back to `/locales` directly). `psql`: row with `chain_id IS NULL`, `chain_name IS NULL`, `category` is either `independent_gym` (if Mapbox category contains gym/fitness/climbing) or NULL (otherwise).
9. **Manual entry happy path.** Click "enter address manually" → fill Locale name + Address + pick "Hotel gym" → Save. Expect: redirect to `/locales` with success flash. `psql`: row with `manual_entry=TRUE`, `mapbox_id IS NULL`, `lat IS NULL`, `lng IS NULL`, `category='hotel_gym'`.
10. **List view.** `/locales` shows: 4 legacy enum cards (home/hotel/partner/airport) at top + N athlete-created rows below, sorted alphabetically by slug. Athlete-created cards show `locale_name` + chain badge / category badge / "manual" badge as appropriate. Edit on athlete-created row works (no "Unknown location" redirect).
11. **0-results path.** Search "asdfqwer noresults". Expect: inline "No matches for 'asdfqwer noresults'. Try a broader search or use manual entry." in alert-warning. No DB write.
12. **Token-missing path.** Temporarily revoke `MAPBOX_PUBLIC_TOKEN` on Vercel (or set to a clearly-invalid value). Re-deploy. Browse `/locales/new` (already-acked athlete) → search anything. Expect: inline "Place lookup is not configured on the server. Use the manual entry option below." Manual fallback still works. Re-add token + re-deploy.
13. **Disclosure version bump.** `psql`: `UPDATE disclosure_acknowledgments SET version_id='v0' WHERE user_id=<uid> AND disclosure_id='mapbox_geocoding_consent'` (simulate athlete acked an older version). Reload `/locales/new` → expect disclosure card re-appears (version mismatch on the LIMIT 1 SELECT). Re-acknowledge → new row with `version_id='v1'`. Old row stays (no DELETE).
14. **Cross-user scoping.** `curl -X POST -b <session-cookie-for-user-A> .../locales/<slug-belonging-to-user-B>/nearby` (with valid CSRF token) → expect "Unknown location." redirect — the route's `(user_id, locale)` lookup returns no row.
15. **Regression sweep on the rest of the app.** Browse `/profile?tab=athlete`, `/onboarding/connect`, `/onboarding/prefill`, `/dashboard`, `/training`. None of those pages should look visually different from pre-PR10. The 4-card legacy locales list still works.
16. **Independent of PR10:** PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 + PR6 §5.0 + PR7 §5.0 + PR8 §5.0 + PR9 §5.0 are still owed if not yet completed.

### 5.1 PR11+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR10_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR9_Closing_Handoff_v1.md` (predecessor).
4. `aidstation-sources/Project_Backlog_v22.md` — current; PR11 may need to bump to v23 (see §5.4).
5. Domain spec for the picked candidate (e.g. `Onboarding_D60_Design_v1.md` for D3b inherit/override; `Onboarding_D61_Design_v1.md` for per-day windows; `Onboarding_D58_Design_v1.md` §6 for E-telemetry).

D-50's frontend bucket — D1 + D2a + D2b + E + D3a — is now **all but D3b shipped**. The remaining v5 onboarding mechanics are D-60 inherit/override + D-59 §7 refresh + D-59 §6 manual→Mapbox upgrade + D-61 per-day windows.

#### Option D3b — D-60 inherit/override + D-59 §6 upgrade + §7 refresh (recommended next)

The natural follow-on to D3a. Three loosely-coupled sub-pieces, all on the same template/route surfaces:

- **D-60 inherit/override UI** — `gym_profiles` (PR2 schema) gets a "default equipment" / "default toggles" view per-locale with per-athlete add/remove overrides via `locale_equipment_overrides` + `locale_toggle_overrides`. UI: extend `templates/locales/form.html` (the existing edit screen) with a section for "Inherited from {chain_name} crowd-sourced profile" + per-tag override checkboxes. Last-writer-wins; disputed-flag promotion path. ~3-4 files.
- **D-59 §7 "Refresh from Mapbox"** — per-locale link on `/locales` list view that re-fetches `place_payload` and re-runs chain detection. If chain changed, prompt "This was X, Mapbox now reports Y. Update?" with Yes/No. ~1-2 files.
- **D-59 §6 manual → Mapbox upgrade** — flip a `manual_entry=TRUE` row to Mapbox-anchored. UI: "Look up on map" link on the edit screen for manual rows. ~1 file extending `edit_profile`.

Bundling D-60 + §7 + §6 keeps the locale work coherent. ~4-5 files; right at the ceiling.

#### Option D-61 — Per-day availability windows UI + JIT swap

Carries forward from PR9 §5.1 (and was always in the v5 onboarding scope but not D-50-bucketed). Scope:

- **§G frontend rewrite** — replace the v4 weekly-totals form with per-day windows (enabled / start / duration); optional second window when Doubles Feasible ≠ No. `daily_availability_windows` schema (PR2) consumed.
- **Onboarding step integration** — slot the new §G form into the existing onboarding flow.
- **Session-card JIT swap UI** — `templates/training/`-side change to let athletes swap a session's locale at view time (deterministic resolver runs at plan-gen but the swap is a manual override).

Larger PR. Estimate 5+ files. Likely needs splitting (§G form first; JIT swap second).

#### Option E-telemetry — `displayed_at` writes + `clicked_cta_at` redirect-shim + reporting

Unchanged from PR9 §5.1. PR10 didn't touch nudges. Schema migration on `account_nudges` (add `clicked_cta_at` column).

#### Option F — Polar refresh-on-401

Unchanged. Watch item only.

#### Option H — Provider blueprint roster expansion

Unchanged. Opportunistic per-provider PRs.

#### Option D2c — Bulk "Apply all" + tolerance-based re-prefill

Unchanged from PR8/PR9 §5.1. Lands when athletes actually need bulk apply.

#### Pre-existing locale_equipment_overrides FK bug

Surfaced this session; out of scope for D3a. PR1's D-58 batch shipped `locale_equipment_overrides.locale_id INTEGER NOT NULL REFERENCES locale_profiles(id)` (init_db.py:1901) but `locale_profiles` has no `id` column (composite PK is `(user_id, locale)`). On a fresh PG schema apply the FK declaration would fail; on existing deploys with the table already created the FK isn't validated. Either:
- (a) Rewrite the FK to match the composite PK: `FOREIGN KEY (user_id, locale_id) REFERENCES locale_profiles(user_id, locale)` (and rename `locale_id` → `locale`), or
- (b) Add an `id SERIAL UNIQUE` column to `locale_profiles` while keeping the composite PK.

D3b will need this resolved before it can write `locale_equipment_overrides` rows. **Recommend (a)** — adding an unused `id` column for FK compatibility doesn't pay for itself. Mechanical fix: drop the bad FK, add a new ALTER renaming `locale_id` → `locale` + the right composite FK.

### 5.2 Recommended sequence (revised post-PR10)

**D3b** (D-60 inherit/override + D-59 §6/§7), with the locale_equipment_overrides FK fix as a prerequisite (one-line fix bundled into the same PR), then **D-61** (per-day windows + JIT swap), then **F** as a watch item, **H** providers as opportunistic adds, **D2c** + **E-telemetry** as production-traffic-driven follow-ons.

D3b is the next obvious step — it closes the v5 onboarding §J locale work end-to-end on top of D3a's Mapbox foundation.

### 5.3 Standing items not on the critical path (carried from PR9 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged. Independent.
- **D-54 SQLite collapse** — unchanged. Catalog Migration Phase 5.
- **D-55 Garmin onto `provider_auth`** — paused.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. **Cross-cutting note carries forward:** PR9's `vercel.json` `crons` array is the natural home for the D-62 prune cron when it ships — same pattern (token-gated endpoint + Vercel Cron entry).
- **`locale_equipment_overrides.locale_id` FK targeting non-existent `locale_profiles(id)`** — *new this session*. Pre-existing PR1 bug; surfaced by PR10's locale work. Mechanical fix spec'd in §5.1 D3b. Out of scope for D3a; tractable in a small follow-on or bundled with D3b.
- **D-59 §6 "Look up on map" upgrade flow** — *new this session*. Documented in §3.4. PR10 ships create-only; the `manual_entry=TRUE` → Mapbox-anchored UPDATE path is D3b candidate.
- **D-59 §7 on-demand refresh** — *new this session*. Documented in §3.5. D3b candidate.
- **D-60 inherit/override/dispute UI** — D3b candidate.
- **D-61 per-day windows UI + JIT swap** — separate PR candidate.
- **Open Item #18 — Telemetry on the 14-day connect-provider nudge** — unchanged. PR11+ E-telemetry candidate.
- **DATABASE.md update** — unchanged.
- **PROVIDERS_SCHEMA.md update** — unchanged.
- **Provenance-row deletion on field clear** (carry-over from PR6/PR7/PR8/PR9) — unchanged.
- **Unused `_POST_STEP2_TARGET` alias** (carry-over from PR7/PR8/PR9) — unchanged.
- **Per-field "from {provider}, {age}" tag** (carry-over from PR7/PR8/PR9) — unchanged.
- **`[Keep current]` writes `'manual_override'` even for prior `'self_report'`** (carry-over from PR8/PR9) — unchanged.
- **No retry/idempotency story for the apply endpoint** (carry-over from PR8/PR9) — unchanged.
- **`f.candidates[0]` divergence tag** (carry-over from PR8/PR9) — unchanged.
- **Confirmation dialogs on `[Use provider value]` for derived extractors** (carry-over from PR8/PR9) — unchanged.

### 5.4 Backlog row update (next PR's first action)

PR10 bumped v21→v22 (this revision). PR11 will need to bump v22→v23 if and only if it lands a state-changing event (e.g. D3b ships → D-50 row notes update + D-59 row status flip again; D-60 row status flip).

**For PR11, owed v22 → v23 bump (mechanically-applicable per Rule #11):**

1. Copy `aidstation-sources/Project_Backlog_v22.md` to `aidstation-sources/Project_Backlog_v23.md`.
2. **Replace** the file-revision header on line 5:
   - Old text:
     ```
     **File revision:** v22 — 2026-05-15 (D-50 row status flip catching up PR10 + D-59 status flip: D-50 status cell now reads 🟢 PR1–PR10 shipped 2026-05-14/15 (commits …, `7cb786a` PR9-merge, `<PR10-merge-pending>`); 🟢 D3a locale-creation + Mapbox chain detection shipped PR10 — … per `V5_Implementation_PR10_Closing_Handoff_v1.md`. No new D-row work this revision — pure status tracking + D3a execution)
     ```
   - New text (assuming PR11 = D3b):
     ```
     **File revision:** v23 — 2026-05-1X (D-50 row status flip catching up PR11 + D-59/D-60 status flip: D-50 status cell now reads 🟢 PR1–PR11 shipped 2026-05-14/15/1X (commits …, `<PR10-merge>`, `<PR11-merge>`); 🟢 D3b shipped PR11 — D-60 shared-`gym_profiles` inherit/override/dispute UI + D-59 §6 manual→Mapbox upgrade + D-59 §7 on-demand refresh + locale_equipment_overrides FK fix per `V5_Implementation_PR11_Closing_Handoff_v1.md`. D-59 + D-60 status flipped to 🟢 D3 fully shipped. No new D-row work this revision — pure status tracking)
     ```
3. **Prepend** to the predecessor revisions block:
   ```
   - v22 — 2026-05-15 (D-50 row status flip catching up PR10 + D-59 status flip: …)  [verbatim from current v22 line 5 narrative]
   ```
4. **Update** the D-50 row status cell from PR1–PR10 → PR1–PR11 shipped, mark D3b as shipped, leave F/H/D2c/E-telemetry pending. Update Notes column "PR11+ candidate menu" → "PR12+ candidate menu" and shift the D3b entry from pending → shipped. Update D-59 row status to fully shipped (no more "D3b pending"). Update D-60 row status to shipped.
5. **Bump** `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line from `Project_Backlog_v22.md` to `Project_Backlog_v23.md`.

**If PR11 is something other than D3b** (e.g. D-61 per-day windows, E-telemetry, D2c, F, H), the narrative text changes but the file mechanics are identical (copy → header replace → predecessor prepend → D-50 row update → CLAUDE.md bump). Write the v23 header narrative to reflect what actually shipped.

---

## 6. Open items / honest flags

- **No live verification.** Same risk class as PR1–PR9 + new Mapbox dependency. Flask isn't installed in the sandbox; Mapbox isn't reachable from the sandbox. AST + Jinja + JSON parse + Mapbox-client unit exercise + chain-registry unit exercise + slug exercise + multi-variant template render confirmed wiring. The PR10 §5.0 manual click-through is mandatory before this is real. Specifically, none of the live Mapbox round-trips have been exercised — `search_places` and `search_nearby` work against a live API in the spec but only against mocked-input return-shape contracts in this session.
- **`MAPBOX_PUBLIC_TOKEN` must be set before first locale creation.** If the env var is unset on Vercel after deploy, every search returns the inline "not configured" error. Manual fallback still works. Mitigation: §5.0 step 2 documents the requirement; D-59 §3.4 row 1 spec'd this as "manual entry is the only option" — exact behavior we ship.
- **Mapbox dependency adds an external failure mode.** Mapbox API outage → no chain-anchored creation; only manual fallback works. Mapbox rate-limit (HTTP 429) → same. D-59 §3.4 row 4 says "if we hit 429s, switch to per-user request token bucket" but PR10 doesn't implement this — for the 1-test-athlete state, even pathological re-creation patterns stay well inside the 100K/month free tier.
- **Pre-existing `locale_equipment_overrides` FK bug.** Surfaced but not fixed. Documented in §5.1 D3b candidate; mechanical fix spec'd. D3a doesn't write to this table so the bug doesn't bite PR10; D3b will need it resolved.
- **Nearby picker re-fetches Mapbox on POST.** Cleaner code than encoding all feature data in hidden form fields, but doubles the Mapbox call count per chain-anchored save (1 GET + 1 POST). Acceptable for the free-tier ceiling. If volume scales up, encode-in-hidden-fields is the optimization.
- **`disclosure_acknowledgments` table doesn't enforce uniqueness.** Re-acks write fresh rows. Per init_db.py:1842 comment this is intentional (`MAX(acknowledged_at)` is the current-state query). No mitigation needed; flagged for transparency.
- **Disclosure check is PG-only.** SQLite dev short-circuits to "acked" — local probes don't gate on a missing table. Production is always PG so the disclosure prompt always fires for un-acked athletes.
- **No JS path for Mapbox autocomplete.** The search is form-submit-driven (POST → results render in the same template). Athletes type → Search button → wait for round-trip → see results. No live typeahead. Matches PR5–PR9's no-JS posture; trade-off is one extra click per search.
- **Manual fallback uses existing `city` column for the address.** The D-59 schema doesn't have a separate `address` field. Acceptable reuse — both are user-supplied freeform location text. If a separate `address` column is wanted later (maybe to differentiate "city" coarse vs. "address" fine), that's a small migration.
- **No upgrade path from `manual_entry=TRUE` row to Mapbox-anchored.** D-59 §6 step 3 spec calls for it; PR10 ships the create-only path. D3b candidate.
- **No on-demand refresh from Mapbox.** D-59 §7 spec calls for a per-locale link; PR10 doesn't ship it. D3b candidate.
- **No tests added.** Inline `python3` exercises for AST + Jinja + JSON parse + Mapbox-client unit + slug unit + chain-registry unit + multi-variant template render were the offline guards. Same framing as PR1–PR9: a real `tests/` directory still doesn't exist. PR10's Mapbox boundary + the disclosure-version flow + the unique-slug logic + the same-chain filter are good unit-test targets if a `tests/` infrastructure ever ships.
- **5 substantive code files + 2 bookkeeping (v22 + CLAUDE.md) + 1 handoff = 8 total.** At the 5-substantive ceiling. Tight — Andy's "build disclosure properly + include nearby in D3a" choice ate the ceiling. PR10 deliberately deferred D3b (D-60 inherit/override + D-59 §6/§7) per the ceiling.
- **Slug collisions possible if athlete reuses a slug after deletion.** Unlikely (no UI for delete today); the unique-slug helper would catch the collision and add a numeric suffix.

---

## 7. Gut check

**What this session got right.**

- **Closed D3a cleanly.** v5 §A.2 + D-59's create-side mechanics are end-to-end wired: search → disclosure → result-pick → chain-detect → INSERT → nearby-pick → INSERT-many → list-render. Manual fallback is a first-class peer.
- **Two stop-and-asks before any code.** Disclosure handling + nearby inclusion both got Andy's call surfaced before scope locked. He chose "build it properly" + "include nearby" — both pushed file count to the ceiling but kept the work coherent.
- **No new schema.** PR1's D-58 + PR2's D-59 batches already shipped the disclosure_acknowledgments + locale_profiles columns we needed. PR10 is pure code on top of existing schema. Smaller blast radius.
- **Re-uses existing patterns.** Disclosure check mirrors PR8's `_record_self_report_provenance` PG-only guard pattern. Slug collision-suffix mirrors `_unique_slug` patterns in onboarding routes. CSRF tokens on every POST per CSRFProtect global (no exemptions).
- **Failure modes are typed.** `MapboxError` hierarchy lets the route layer render specific inline messages (token-missing vs. zero-results vs. API-down) without parsing exception strings. Each branch in the template is bound to a specific failure class.
- **PG-only graceful degradation.** SQLite dev returns "acked=True" so local probes don't gate; the scanner returns features-or-raises but the route catches gracefully.
- **Came in at the ceiling.** 5 substantive files, exactly. No scope creep into D3b.

**Risks.**

- **First Mapbox-driven write path in the app.** Until live verification runs, the contract between `_normalize_feature` shape + chain-detect + the route's INSERT params is only validated by inline mock tests. A bug in the Mapbox response shape (Mapbox changing their API) would surface at first real search. Mitigation: the §5.0 step 5+6 manual smoke tests against a live Planet Fitness search are the integration-level guard.
- **Nearby picker doubles the Mapbox call cost per chain-anchored save.** GET fetches results; POST re-fetches to validate selected mapbox_ids. Cost-acceptable at the 1-athlete state but becomes a cost concern at scale. Encode-in-hidden-fields is the cheap optimization.
- **Manual entry + Mapbox entry produce the same `locale_profiles` table — schema-level confusion if athlete edits a row.** Per-row `manual_entry` flag distinguishes them; UI relies on this flag to show appropriate badges. A bug in the flag-flip on the upgrade path (D3b candidate) could leave a row half-Mapbox-half-manual.
- **`MAPBOX_PUBLIC_TOKEN` env var management is manual.** No code to enforce it's set. If a future Vercel project rebuild forgets the env var, chain-anchored creation silently falls back to "not configured" inline message. Mitigation: §5.0 step 2 documents the requirement.

**What might be missing.**

- **Manual → Mapbox upgrade flow** (D-59 §6 step 3) — D3b candidate. Documented as missing.
- **On-demand "Refresh from Mapbox" link** (D-59 §7) — D3b candidate. Documented as missing.
- **D-60 inherit/override UI** (the whole D-60 spec) — D3b candidate. Documented as missing.
- **Privacy-policy link target.** Disclosure card mentions "Mapbox's privacy policy" but doesn't link to it. Production should add the actual URL (privacy-policy text owns this; spec says "legal/product owns").
- **No success route after locale creation other than back-to-list.** Athletes who want to immediately edit equipment for the new locale get back-to-list and have to click Edit. Tolerable; "after-create → straight to edit" is a UX iteration.
- **No way to delete an athlete-created locale.** Out of scope. D3b candidate.
- **No "default name suggestions" for nearby instances.** Currently they keep `feature.text` as their `locale_name`. Athletes can edit later via the (not-yet-existing) edit-name UI. D3b candidate.

**Best argument against this session's scope.**

PR10 ships infrastructure (Mapbox client + disclosure + nearby picker) for a single use case (Andy creating one or two locales) against a population of one. The cost-per-call to Mapbox is well within the free tier; the immediate user-visible win is "Andy can now create a locale via place lookup instead of a 4-enum dropdown."

Counter: the v5 §J locale design is the foundation for D-60 (gear from proximity), D-61 (session→locale resolver), and Layer 4 plan-gen's locale-aware session assignment. Shipping the create-side now means the consumer sides have schema to read against. The infrastructure also pays for itself on the first non-Andy athlete (the disclosure + Mapbox path is the same code, no per-tenant changes).

Counter to the counter: shipping infrastructure ahead of users means the Mapbox round-trip will run against an empty result set for the foreseeable future. The cost is negligible (one Mapbox call per locale Andy creates; Andy creates locales rarely) but the value is zero until population grows. Mitigation: this is the right kind of pre-built infrastructure — small, low-risk, no migration, no athlete-facing change for existing data. Sits idle harmlessly; pays off when D3b + D-61 ship and Andy starts creating real locales.

---

## 8. Forward pointers

- **Next session:** PR11 = Option D3b (D-60 inherit/override + D-59 §6 upgrade + §7 refresh, recommended) or any of the PR10 §5.1 carry-forward candidates. PR10 closes D-59's create side; D3b closes the rest of the v5 §J locale work.
- **Before next code lands:** PR10 §5.0 spot-check on the deployed app (set `MAPBOX_PUBLIC_TOKEN`, browse `/locales/new`, walk disclosure → search → save → nearby → save flows). PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 + PR6 §5.0 + PR7 §5.0 + PR8 §5.0 + PR9 §5.0 are still owed if not yet completed.
- **First action of next session:** Read `aidstation-sources/CLAUDE.md` fully (Rule #13). Then Rule #9 reconciliation. Specifically: confirm PR10 commit landed on `claude/review-v5-pr9-handoff-Xdt7Q` (or merged to main with its own merge commit); confirm `mapbox_client.py` exists with `search_places` + `search_nearby` + `_bbox` + `MapboxError` hierarchy; confirm `routes/locales.py` has `new_locale` + `_save_mapbox_anchored` + `save_manual_locale` + `acknowledge_mapbox_disclosure` + `nearby_instances` + the slug + disclosure helpers; confirm `templates/locales/new.html` + `templates/locales/nearby.html` exist and `templates/locales/list.html` shows athlete-created rows; confirm `Project_Backlog_v22.md` exists with v21 archived to predecessor block + D-50 row reflects PR10 shipped + D-59 status flipped 🟢 D3a; confirm `CLAUDE.md` "Authoritative current files" backlog line reads v22.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **PR10 has one deferred mechanical edit:** the v22 → v23 backlog bump for PR11's first action, spec'd verbatim in §5.4
- #12 numeric version suffixes (backlog now at v22; v23 lands in PR11 per §5.4)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1; §8 first-action explicitly names CLAUDE.md.**

---

## 9. Mid-session addendum — `PR_Verification_Status.md` tracker added

Late in this session Andy surfaced a gap: each PR's §5.0 "still owed" carry-forward had grown monotonically across PR1–PR10, conflating "genuinely owed," "blocked on external creds," and "already done." No session was tracking which steps had actually been walked.

Added `aidstation-sources/PR_Verification_Status.md` — single-file per-PR/per-step tracker with a 4-state legend (✅ Done / ⏸ Blocked / 🟡 Owed / ⚪ N/A). Seeded with what Andy reported in this session:

- **PR9** — 14/14 ✅ Done (Andy walked all banner / cron / dismiss steps).
- **PR6** — 6/7 ✅ Done; step 7 (COROS webhook ON CONFLICT) ⏸ blocked.
- **PR7** — 5/7 ✅ Done; step 3 ⏸ blocked on COROS data; step 7 ⚪ N/A (superseded by PR8).
- **PR5** — steps 1-2 ✅; steps 3-4 ⏸ blocked on COROS OAuth; steps 5-7 🟡 owed.
- **PR1** — step 4 ✅ (D-58 schema verified implicitly by PR6+PR9 working); steps 1-3 ⏸ blocked on COROS creds.
- **PR3** — step 5 (index spot-check) 🟡 owed; steps 1-4 ⏸ blocked on Polar creds.
- **PR4** — step 1 (page render) 🟡 owed; steps 2-6 ⏸ blocked on at least one of COROS/Polar.
- **PR2** — schema-only; one 🟡 owed spot-check on locale tables.
- **PR8** — step 1 ✅; steps 2-6 ⏸ blocked on COROS data; steps 7-9 (defensive guards + 404 + CSRF) 🟡 owed.
- **PR10** — `MAPBOX_PUBLIC_TOKEN` env var ✅ set (Andy confirmed); 14 walk-through steps 🟡 pending merge + deploy.

Aggregate: 31 ✅, 21 ⏸ (all on COROS/Polar partner credentials), 23 🟡 owed, 2 ⚪ N/A across 77 step-rows.

**Future sessions** read `PR_Verification_Status.md` at session start (CLAUDE.md First-session checklist step 4 extended). Future handoffs no longer need to enumerate "PR<N-1> §5.0 still owed if not completed" carry-forward — the tracker is the source of truth.

**File count update:** original PR10 count was 5 substantive + 2 bookkeeping + 1 handoff = 8 total. Adding the tracker (`PR_Verification_Status.md` new) + 2-line CLAUDE.md edit + this addendum = +1 bookkeeping, no substantive code change. Still at the 5-substantive ceiling.

---

*End of V5 Implementation PR10 closing handoff. v5 onboarding Option D3a (Mapbox-anchored locale creation + chain detection + nearby same-chain picker + manual fallback + privacy disclosure) shipped: `mapbox_client.py` Mapbox Geocoding wrapper (typed exceptions, 1-retry on 5xx, bbox math) + `routes/locales.py` extended with `GET/POST /locales/new` (search + chain-detect + INSERT), `POST /locales/new/manual` (manual fallback per D-59 §6), `POST /locales/new/acknowledge` (disclosure ack into existing `disclosure_acknowledgments` table — no schema change), `GET/POST /locales/<slug>/nearby` (D-59 §5 same-chain proximity picker) + new `templates/locales/new.html` + `templates/locales/nearby.html` + `templates/locales/list.html` extension to render athlete-created rows. Closes D-59 create-side; D3b (D-60 inherit/override UI + D-59 §6 upgrade + §7 refresh) carried forward as PR11+ candidate. Backlog bumped v21 → v22; D-59 status flipped 🟡 → 🟢 D3a (D3b pending). Next: Andy's choice among PR11 candidates in §5.1 (D3b recommended — closes the rest of the v5 §J locale work end-to-end on top of D3a's foundation); v22 → v23 backlog bump mechanically spec'd for PR11's first action.*
