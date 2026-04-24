# AidStation — Session Handoff

**Date:** 2026-04-24
**Branch merged:** `claude/review-handoff-file-681Tv` → `main`

---

## What Was Done This Session

### 1. Branding — AR Training → AidStation
- `templates/base.html`: brand name, page title format (dropped `— PGE 2026` suffix)
- Nav: `Current Rx` + `Exercises` merged into single `Exercises` link (`/rx`)
- Nav: `Log via Text (AI)` → `Log via Text`
- Garmin `Auth Settings` hidden on mobile (`d-none d-md-block`)

### 2. Dashboard Rework (`routes/dashboard.py`, `templates/dashboard.html`)
- Shows today's and tomorrow's scheduled plan workouts with ✓/✕/⬇ action forms
- Weather card via wttr.in (no API key required)
  - Location priority: active `plan_travel` trip city → `locale_profiles WHERE locale='home'` city → `WEATHER_LOCATION` env var → IP auto-detect
  - 30-minute in-memory cache
- Missed workouts alert (last 7 days, collapsible)
- Stats row condensed above recent strength/cardio tables

### 3. Exercises Page (`routes/rx.py`, `templates/rx/list.html`)
- Joined `current_rx` with `exercise_inventory` — exercise names link to `video_reference` if set
- Second table shows all exercises in inventory with no current Rx entry
- Added locale filter (`where_available` column)

### 4. Filters Added
| Page | Filters |
|---|---|
| Cardio (`/cardio`) | Date, activity type |
| Conditions (`/conditions`) | Date, activity text search |
| Injuries (`/injuries`) | Status dropdown, body part text search |

### 5. Body Metrics Mobile (`templates/body/list.html`, `templates/body/form.html`)
- Body Fat % and Notes columns hidden on mobile (`d-none d-md-table-cell`)
- Delete button removed from list table; added to edit form with confirm dialog

### 6. Plans Mobile UX
**List page** (`templates/plans/list.html`):
- Sport and Progress columns hidden on mobile
- Status badge shown inline with plan name on mobile
- Archive/Delete buttons hidden on mobile (View only)

**View page** (`templates/plans/view.html`, `routes/plans.py`):
- Desktop/mobile split header (`d-none d-md-flex` / `d-md-none`)
- Days-to-race badge in header (computed in `view_plan()` as `days_to_race`)
- Week labels changed from `Week {{ week }}, {{ year }}` to `Week {{ loop.index }}` (plan-relative)
- Duration column hidden on mobile; duration shown inline in date cell
- Status badge stacked above action buttons in last column

### 7. Coaching Text Cleanup
- `templates/coaching/generate.html`: button `Generate Plan with Claude` → `Generate Plan`; plan name badges switched from `<span class="badge">` to plain links for proper wrapping
- `templates/coaching/review.html`: button `Run Review with Claude` → `Run Review`
- `templates/natural_log/index.html`: emptied `#chat-hint` div text

### 8. Garmin Dashboard (`templates/garmin/dashboard.html`)
- Removed Sync button from header
- Removed Garmin Connect status card
- Two remaining cards resized to `col-md-6`

---

## Known Gaps / Follow-Up Items

- **`requests` added to `requirements.txt`** — run `pip install -r requirements.txt` on the server after deploy if weather fetch errors
- **Weather**: wttr.in fetch has a 3s timeout; if it's down the card simply doesn't render
- **`plan_travel` table** is populated by the coaching generate flow. If no active trip, weather falls back to `locale_profiles WHERE locale='home'` city, then `WEATHER_LOCATION` env var
- **Plans view week numbering**: uses `loop.index` over ordered `weeks` dict — rest weeks with no items are omitted, numbering stays sequential
- **`references.exercises` route** (old separate Exercises page) still exists; no longer linked from nav. Can be removed if not needed

---

## Files Changed

```
requirements.txt
routes/dashboard.py
routes/cardio.py
routes/conditions.py
routes/injuries.py
routes/plans.py
routes/rx.py
templates/base.html
templates/body/form.html
templates/body/list.html
templates/cardio/list.html
templates/coaching/generate.html
templates/coaching/review.html
templates/conditions/list.html
templates/dashboard.html
templates/garmin/dashboard.html
templates/injuries/list.html
templates/natural_log/index.html
templates/plans/list.html
templates/plans/view.html
templates/rx/list.html
```
