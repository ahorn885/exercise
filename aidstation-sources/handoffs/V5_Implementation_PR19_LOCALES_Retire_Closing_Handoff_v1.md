# V5 Onboarding Implementation PR19 — Retire Legacy `LOCALES` External Consumers Closing Handoff

**Session:** Ships PR18 closing handoff §5.1 deferred item — retire `LOCALES` as an external dependency from `routes/coaching.py` + `routes/references.py` + the cosmetic badge surface in `templates/references/exercises.html`. Switches both coaching + references to query the athlete's actual locale list via a new `athlete_locale_choices(db, uid)` helper in `routes/locales.py`. Per Andy's two architectural picks this session: form-level guard for coaching default-fallback (no silent rewrite to `'home'`); athlete-locale-aware references filter with category → Layer 0 bucket mapping.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Implementation_PR18_Locale_CRUD_Bundle_Closing_Handoff_v1.md` (§5.1 captured Item E as a separate PR; this is that PR).
**Branch:** `claude/locale-crud-bundle-closing-imqrG`.
**Status:** 🟢 6 substantive code files shipped (`routes/locales.py` additive helper + bucket map; `routes/coaching.py` LOCALES drop + TRIP_LOCALE_TYPES + form-level guard refactor; `routes/references.py` import swap + bucket-mapped filter; `templates/coaching/generate.html` + `templates/coaching/review.html` + `templates/references/exercises.html` dropdown/checkbox updates); 4 bookkeeping (CLAUDE.md, Project_Backlog v34 → v35, PR_Verification_Status PR19 section + aggregate refresh, this handoff). PR19 §5.0 has 11 testable steps owed for the post-merge walk.

---

## 1. Session-start verification (Rule #9)

Predecessor PR18 handoff §6 forward-pointer claimed: branch clean off the merged PR18 tip (PR #63, commit `6dc7007`); PR18 §5.0 has 12 owed steps; Item E (this PR) needs (a) `routes/coaching.py:22` `LOCALES` literal dropped, (b) `routes/references.py:5` `LOCALES` import retired, (c) `templates/references/exercises.html:56` cosmetic badge logic considered.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| Working tree clean on session branch | `git status` | ✅ |
| `Project_Backlog_v34.md` is highest | `ls Project_Backlog_v*.md \| sort -V \| tail` | ✅ |
| `mapbox_client.py` has `retrieve` (PR18 ship) | `grep -n "def retrieve" mapbox_client.py` | ✅ |
| `routes/locales.py` has `_display_address` + `_existing_locale_by_mapbox_id` + `delete_locale` + `outdoor_park` in `SHARED_PROFILE_CATEGORIES` + label swaps (PR18 ship) | grep inspection | ✅ |
| `templates/locales/list.html` + `form.html` render `display_address(es)` + delete button (PR18 ship) | grep inspection | ✅ |
| `routes/coaching.py:22` has `LOCALES = ['home','hotel','partner','airport']` literal | inline read | ✅ (pre-PR19; to be dropped) |
| `routes/references.py:5` has `from routes.locales import LOCALES` | inline read | ✅ (pre-PR19; to be dropped) |
| `routes/locales.py:15` has `LOCALES = ['home','hotel','partner','airport']` (internal-only literal) | inline read | ✅ (stays — internal consumers across `routes/locales.py`) |
| `templates/references/exercises.html:56` has 4-color badge `if loc == 'home' bg-primary elif 'hotel' bg-success ... bg-secondary` | inline read | ✅ |
| Only external `LOCALES` consumers are `routes/coaching.py` (local literal) + `routes/references.py` (import) | `grep -rn "LOCALES\b\|from routes.locales import" --include="*.py"` | ✅ — matches PR11-follow-on handoff §3.5 audit exactly |

No drift.

---

## 2. Session narrative — Item E execution

Chat opened with Andy linking the PR18 closing handoff. Track menu (`AskUserQuestion`): Layer 4 §14 retro vs. per-tier T1/T2 prompt vs. race-week-brief prompt vs. Item E PR. Andy picked **Item E PR**.

Two stop-and-ask architectural picks resolved via a second `AskUserQuestion`:

1. **Coaching default-fallback** — picked option (c) **form-level guard**: no implicit `'home'` rewrite on missing/invalid POST locale; flash + redirect to GET surfaces the error to the athlete instead of silently rewriting. Note: the "zero locales" hard-fail branch doesn't fire in practice — legacy slots (`home`/`hotel`/`partner`/`airport`) auto-render in the choice list per `routes/locales.py` design.

2. **References filter** — picked option (b) **show athlete's locales; map custom → category bucket**. Filter UI shows athlete locale names; the `where_available` match maps each selected athlete-slug to its Layer 0 bucket (legacy slug == bucket; custom slug → bucket via category lookup). The minimal-scope alternative (keep 4-bucket UI, define a local constant) was rejected — Andy wanted athletes to see their actual saved locales in the filter.

No further stop-and-ask triggers fired during execution.

---

## 3. What landed per file

### 3.1 `routes/locales.py` — additive helper + bucket-map (preserves internal `LOCALES`)

New module-level dict:

```python
CATEGORY_TO_WHERE_AVAILABLE_BUCKET = {
    'home_gym': 'home',
    'other_residence': 'home',
    'hotel_gym': 'hotel',
    'commercial_chain_gym': 'partner',
    'independent_gym': 'partner',
    'climbing_gym_chain': 'partner',
    'climbing_gym_indie': 'partner',
    'pool_indoor': 'partner',
    'pool_outdoor': 'partner',
    'outdoor_park': '',
}
```

Mapping rationale:
- Residential categories (`home_gym`, `other_residence`) → `home` bucket. Both are residence-locale variants.
- `hotel_gym` → `hotel`. Direct match.
- All third-party gym + commercial pool categories → `partner` bucket. The original `partner` enum meant "third-party gym."
- `outdoor_park` → `''`. No Layer 0 analog — parks match no exercises until the park-specific tag taxonomy lands (PR18 §5.2 deferred follow-up).

New helper:

```python
def athlete_locale_choices(db, uid: int) -> list:
    """Returns ordered list of {slug, label, bucket} dicts."""
    rows = db.execute(
        'SELECT locale, locale_name, category FROM locale_profiles '
        'WHERE user_id = ?',
        (uid,),
    ).fetchall()
    by_slug = {r['locale']: r for r in rows}

    choices = []
    for slug in LOCALES:  # legacy slots first, canonical order
        row = by_slug.get(slug)
        label = (row['locale_name'] if row and row['locale_name'] else slug.capitalize())
        choices.append({'slug': slug, 'label': label, 'bucket': slug})
    for slug in sorted(s for s in by_slug if s not in LOCALES):  # custom alpha
        row = by_slug[slug]
        label = row['locale_name'] or slug
        bucket = CATEGORY_TO_WHERE_AVAILABLE_BUCKET.get(row['category'] or '', '')
        choices.append({'slug': slug, 'label': label, 'bucket': bucket})
    return choices
```

Output shape: list of `{slug, label, bucket}` dicts, legacy slots always present (using `locale_name` if a row exists, else `slug.capitalize()`), then athlete-created locales alpha by slug.

Internal `LOCALES = ['home','hotel','partner','airport']` literal at line 15 unchanged. It's consumed by the rest of `routes/locales.py` for: `list_profiles` legacy-vs-custom split (line 321), legacy-locale auto-render (line 323), `is_deletable` gate (line 427 + 508), `delete_locale` legacy-slot rejection (line 929). Internal-only after PR19.

### 3.2 `routes/coaching.py` — LOCALES drop + TRIP_LOCALE_TYPES + form-level guard

- Drops `LOCALES = ['home', 'hotel', 'partner', 'airport']` literal (was at line 22).
- New `TRIP_LOCALE_TYPES = ('home', 'hotel', 'partner', 'airport')` constant: documented as the trip-environment-type taxonomy used by `plan_travel.locale` + Claude prompt construction. **Separate from the athlete's saved-locale list** — trip-locales are kinds of places (hotel, partner gym, airport gym) the athlete will be at during travel, not specific saved locations. The dropdown stays a type picker.
- Imports `athlete_locale_choices` from `routes.locales`.
- `generate()` GET (around line 152): queries `athlete_locale_choices(db, current_user_id())`; passes `locales=...` + `trip_locale_types=TRIP_LOCALE_TYPES` to template.
- `generate()` POST validation (around line 73): replaces `if locale not in LOCALES: locale = 'home'` silent rewrite with strict check against `{c['slug'] for c in athlete_locale_choices(db, current_user_id())}`; on miss, `flash('Select a valid current location.', 'danger')` + `redirect(url_for('coaching.generate'))`.
- `review(plan_id)` GET (around line 321): same query + template var pattern.
- `review(plan_id)` POST validation (around line 176): same strict-check pattern + flash + redirect to `coaching.review(plan_id=plan_id)`.
- `chat()` JSON endpoint at line 537 unchanged: `data.get('locale', 'home')` — API contract preserved; not a form. The `'home'` default here is fine since `'home'` is always a valid legacy slug regardless of athlete state.
- Trip-locale handling in POST handlers (`trip.get('locale', 'hotel')`) unchanged — the legacy bucket taxonomy still applies to `plan_travel.locale` writes.

### 3.3 `routes/references.py` — import swap + bucket-mapped filter

- Drops `from routes.locales import LOCALES`; imports `athlete_locale_choices`.
- `exercises()` (line 26+) queries `locale_choices` + `valid_slugs` at top; sanitizes `request.args.getlist('locale')` against the valid set (defensive against URL tampering).
- Filter logic (around line 79) rewritten:
  - **Before:** `ex_locales = set((r['where_available'] or '').split(',')); if not any(loc in ex_locales for loc in locale_filter): continue`
  - **After:** Build `selected_buckets = {c['bucket'] for c in locale_choices if c['slug'] in locale_filter and c['bucket']}`; intersect against `ex_locales`.
- Custom locales with `bucket=''` (e.g., outdoor_park) contribute nothing to the filter and correctly match 0 exercises. This is consistent with the Layer 0 taxonomy gap for outdoor environments.
- Template context passes `locales=locale_choices` instead of `locales=LOCALES`.

### 3.4 Templates

**`templates/coaching/generate.html`:**
- Line 165–168 primary "Current Location" dropdown: `{% for c in locales %}<option value="{{ c.slug }}" ...>{{ c.label }}</option>{% endfor %}`. Pre-selected: `c.slug == 'home'`.
- Line 296–299 trip-locale dropdown: `{% for t in trip_locale_types %}<option value="{{ t }}" ...>{{ t | capitalize }}</option>{% endfor %}`. Pre-selected: `t == 'hotel'`.

**`templates/coaching/review.html`:**
- Line 81–84 primary location dropdown: same `{c.slug, c.label}` pattern. Pre-selected `home`.
- Line 229–232 locale-row template trip dropdown: iterates `trip_locale_types`. Pre-selected `hotel`. The JS-clone template inherits the dropdown surface, so adding/removing locale rows produces type-picker dropdowns.

**`templates/references/exercises.html`:**
- Line 12–21 filter-checkbox loop: `{% for c in locales %}<input ... value="{{ c.slug }}" id="loc_{{ c.slug }}" {% if c.slug in locale_filter %}checked{% endif %}>...<label>{{ c.label }}</label>{% endfor %}`.
- Line 56 badge color logic **unchanged**: it iterates `r.where_available.split(',')` — Layer 0 reference data, which still uses the 4 legacy bucket values (`home`/`hotel`/`partner`/`airport`). The badge colors Layer 0 data, NOT athlete slugs. The 4-color scheme stays correct.

---

## 4. Files shipped this session

All on branch `claude/locale-crud-bundle-closing-imqrG`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `routes/locales.py` | Edit (additive +60 lines) | `CATEGORY_TO_WHERE_AVAILABLE_BUCKET` dict + `athlete_locale_choices(db, uid)` helper. Internal `LOCALES` literal preserved. |
| 2 | `routes/coaching.py` | Edit (substantive multi-region) | `LOCALES` literal dropped; `TRIP_LOCALE_TYPES` added; `athlete_locale_choices` imported; both `generate()` + `review()` GET handlers query + pass template vars; both POST handlers replace silent rewrite with form-level guard. `chat()` unchanged. |
| 3 | `routes/references.py` | Edit | `LOCALES` import dropped; `athlete_locale_choices` imported; `exercises()` queries once at top + sanitizes URL params + filter intersects via bucket-map. |
| 4 | `templates/coaching/generate.html` | Edit | Primary dropdown iterates `{c.slug, c.label}` dicts; trip-locale dropdown iterates `trip_locale_types`. |
| 5 | `templates/coaching/review.html` | Edit | Same — primary dropdown + locale-row trip template. |
| 6 | `templates/references/exercises.html` | Edit | Checkbox loop iterates dicts (slug + label). Badge color logic unchanged. |
| 7 | `aidstation-sources/CLAUDE.md` | Edit | Last-shipped narrative bumped to PR19 with full PR-scope summary; PR18 demoted to predecessor; Backlog ref v34 → v35; Next-forward-move drops the Item E candidate (now shipped). Park-tags follow-up retained. |
| 8 | `aidstation-sources/Project_Backlog_v35.md` | New (v34 → v35) | v35 header revision entry: PR19 narrative. v34 entry moved to predecessor revisions list. Body (D-row table + categorization rules + status legend + open items + going-forward rule + closed sessions list + process notes) byte-identical to v34 per Rule #12. |
| 9 | `aidstation-sources/PR_Verification_Status.md` | Edit | New PR19 section with 11 testable §5.0 steps (all 🟡 owed for the post-merge walk); Aggregate status table refreshed (PR19 row added; totals 52 ✅ / 21 ⏸ / 37 🟡 / 4 ⚪ of 114); Headlines section rewritten — post-PR19 ship state has 37 doable-now. |
| 10 | `aidstation-sources/handoffs/V5_Implementation_PR19_LOCALES_Retire_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**5-file ceiling status:** 6 substantive code files (1 over ceiling). 3 of them are 1–6-line template surgical edits (dropdown var rename); the substantive surface area is `routes/coaching.py` refactor + `routes/locales.py` additive helper + `routes/references.py` filter rewrite (3 files). 4 bookkeeping files are mandatory per Rules #11/#12/#13 + per-implementation-PR cadence. Net 10 files — comparable to PR17 (7) + PR18 (8); on the higher end but justified.

**Not touched this session** (intentional):

- `routes/locales.py:15` `LOCALES` literal — preserved as internal-only constant. Multiple internal consumers (`list_profiles`, `_save_mapbox_anchored`, edit handlers, `delete_locale`) still depend on it for the legacy-vs-custom distinction.
- Layer 0 `exercise_inventory.where_available` data — the 4-bucket taxonomy. Park-tag follow-up (PR18 §5.2) revisits this when warranted.
- `coaching.py` (module, not route) + `generate_plan` / `run_review` / `chat_with_coach` callees — they receive `locale` as a string parameter and pass it through to Claude prompt construction. No behavior change needed.
- `plan_travel.locale` column — still stores 4-bucket type values via the trip-locale dropdown. Schema unchanged.
- `chain_registry.py`, `mapbox_client.py`, `init_db.py` — unrelated to Item E.

---

## 5. Standing items / open flags

### 5.1 Park-specific tag taxonomy (still deferred)

Carries forward from PR18 §5.2 unchanged. With `outdoor_park` in `SHARED_PROFILE_CATEGORIES` (PR18) + now mapped to `''` bucket in `CATEGORY_TO_WHERE_AVAILABLE_BUCKET` (PR19), the `/references/exercises` filter shows 0 results when only outdoor_park locales are selected. This is consistent with the Layer 0 gap: gym-centric `where_available` taxonomy + gym-centric `EQUIPMENT_CATEGORIES`.

**Trigger to revisit:** Andy starts using park locales for actual sessions + the empty exercise inventory becomes a friction point. The cleanest path remains the PR18 §5.2 plan: introduce parallel `OUTDOOR_TAGS = [...]` consumed only when `category == 'outdoor_park'`; the edit form branches the rendered checkbox set on category; no schema change if outdoor tags live in the same `locale_equipment` + `equipment_items` registry (new tag rows).

### 5.2 Trip-locale taxonomy decoupling (defer-by-pattern)

PR19 split the template variable surface: `locales` (athlete saved-locale dicts) for primary location, `trip_locale_types` (4-bucket type taxonomy) for trip-environment dropdowns. This is the right split semantically — trips are about the kind of place the athlete will be at during travel, not specific saved places.

**Future trigger:** if Andy wants to save specific travel destinations as locales (e.g., "Marriott Denver" with equipment profile) and pick those for trip rows, the trip-locale dropdown could become a hybrid: saved athlete locales + the 4 generic type fallbacks. The current `plan_travel.locale` schema accepts arbitrary string values, so it's technically already supported — only the dropdown UI is constrained. Defer until the use case actually arises.

### 5.3 v1 coaching form replacement (track-level coupling)

Per CLAUDE.md "Selective rebuild": coaching + plan-generation are slated for replacement by the v2 LLM pipeline (Layer 4 implementation). The coaching form (`routes/coaching.py`) + its templates are doomed by the v2 cutover. PR19's investment in form-level guard validation + athlete-locale-aware dropdowns will be largely thrown away when v2 ships its own UI surface for plan generation + refresh.

**Why ship anyway:** the alternative was leaving `LOCALES = ['home','hotel','partner','airport']` as a hardcoded literal in `routes/coaching.py` — a tiny but real coupling between v1 coaching and the legacy 4-bucket taxonomy that PR18 already softened (custom locales display on `/locales` but were invisible to `/coaching/generate`'s "Current Location" dropdown). PR19 closes that surface area gap. Cheap to do now; cleaner code surface for v2 to replace.

### 5.4 `chat()` endpoint locale default (intentionally untouched)

`routes/coaching.py:537` has `locale = data.get('locale', 'home')` — API contract for the chat-with-coach JSON endpoint. Left unchanged because:
- It's a JSON API, not a form. Form-level guard semantics don't apply.
- `'home'` is always a valid legacy slug — chat callers that omit the field hit the same default they did pre-PR19.
- Touching this would require coordinating with any external chat consumers (none known at N=1, but defensive).

If the v2 implementation refactors the chat endpoint, this default can be revisited then.

### 5.5 PR18 §5.0 walks still owed (12 steps)

Unchanged from PR18 closing handoff §6. PR18 deploy + walk happens whenever Andy hits the Vercel deploy. PR19 doesn't gate PR18's walk — separate concerns.

After both PR18 + PR19 deploy:
- PR18 §5.0: 12 walks owed.
- PR19 §5.0: 11 walks owed.
- PR11 §5.0 step 6: re-walkable + flippable to ✅ (unblocked by PR18 item B's `/retrieve` refresh).

Total post-deploy walks: 24 substantive items (PR18 + PR19 + the PR11 step 6 free win).

---

## 6. Forward pointers

**Next session:** Andy's choice. The PR19 walk happens after Vercel deploy (Andy-driven, not in-session). Candidates for the next coding session:

- **Layer 4 prompt-body design — per-tier T1/T2 (D-64; Pattern B refresh)** — 4 of 5 in the prompt-body arc; stop-and-ask trigger #2.
- **Layer 4 prompt-body design — race-week-brief** — 5 of 5; stop-and-ask trigger #2.
- **Layer 4 §14 retrospective** — fresh-eyes critical pass before Layer 4 implementation.
- **Layer 4 implementation track** — D-63 LLM-call layer can land against `Layer4_SingleSession_v1.md`; deterministic-validator harness + payload schema scaffolding can start independently.
- **D-50 wiring resumption** — COROS OAuth + webhook recording.

**Before the PR19 walk:**

1. **Read `aidstation-sources/CLAUDE.md` fully** (Rule #13). Last-shipped narrative now leads with PR19; Backlog ref now points at v35.
2. Read this handoff in full.
3. Read `PR_Verification_Status.md` PR19 section for the 11 §5.0 steps.
4. (Optional) Re-read the predecessor handoff `V5_Implementation_PR18_Locale_CRUD_Bundle_Closing_Handoff_v1.md` §5.1 for the Item E scope — confirms the refactor is faithful to the audit findings.

**Rules in force, unchanged:**

- #9 session-start verification — `routes/locales.py` has `athlete_locale_choices` + `CATEGORY_TO_WHERE_AVAILABLE_BUCKET`; `LOCALES` literal still at line 15 (internal-only); `routes/coaching.py` no longer references `LOCALES`; `routes/references.py` no longer imports `LOCALES`.
- #10 session-end verification — applied; see §7 below.
- #11 mechanically-applicable deferred edits — park-tags taxonomy direction carries forward from PR18 §5.2; trip-locale hybrid noted in §5.2 above with defer-trigger.
- #12 numeric version suffixes — Backlog now at v35; next state-changing event bumps v35 → v36.
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §6 first-action explicitly names CLAUDE.md.

---

## 7. Session-end verification (Rule #10)

Final pass over each claimed file edit before composing this handoff:

| Check | Result |
|---|---|
| `routes/locales.py` defines `athlete_locale_choices(db, uid)` | ✅ `grep -n "def athlete_locale_choices"` |
| `routes/locales.py` defines `CATEGORY_TO_WHERE_AVAILABLE_BUCKET` dict with 10 keys | ✅ inline read; keys = all `MANUAL_CATEGORIES` enum values |
| `routes/locales.py` `LOCALES` literal preserved at line 15 (internal use) | ✅ |
| `routes/coaching.py` no `LOCALES` literal or import | ✅ `grep -n "LOCALES" routes/coaching.py` returns empty |
| `routes/coaching.py` defines `TRIP_LOCALE_TYPES` tuple | ✅ |
| `routes/coaching.py` imports `athlete_locale_choices` | ✅ |
| `routes/coaching.py` `generate()` GET passes `locales=athlete_locale_choices(...)` + `trip_locale_types=TRIP_LOCALE_TYPES` | ✅ |
| `routes/coaching.py` `generate()` POST validates locale against athlete's set + flash + redirect on miss | ✅ |
| `routes/coaching.py` `review()` GET + POST same pattern | ✅ |
| `routes/coaching.py` `chat()` unchanged (`data.get('locale', 'home')`) | ✅ |
| `routes/references.py` no `LOCALES` import | ✅ `grep -n "LOCALES" routes/references.py` returns empty |
| `routes/references.py` imports `athlete_locale_choices` | ✅ |
| `routes/references.py` `exercises()` sanitizes `?locale=` URL params against valid slug set | ✅ |
| `routes/references.py` filter logic uses bucket-mapped intersection | ✅ |
| `templates/coaching/generate.html` primary dropdown iterates `{c.slug, c.label}` dicts | ✅ |
| `templates/coaching/generate.html` trip dropdown iterates `trip_locale_types` | ✅ |
| `templates/coaching/review.html` primary + locale-row dropdowns same | ✅ |
| `templates/references/exercises.html` checkbox loop iterates dicts | ✅ |
| `templates/references/exercises.html` line 56 badge color logic unchanged (correctly keyed to Layer 0 buckets) | ✅ |
| AST parse `routes/locales.py` + `routes/coaching.py` + `routes/references.py` clean | ✅ `python3 -c "import ast; ast.parse(...)"` |
| No remaining external `LOCALES` consumers | ✅ `grep -rn "from routes.locales import LOCALES\|^LOCALES = \['home'"` returns only `routes/locales.py:15` |
| `Project_Backlog_v35.md` exists; line 5 starts with `**File revision:** v35 — 2026-05-16 (**PR19 — retire legacy` | ✅ `head -5` |
| `Project_Backlog_v35.md` line 6 = `**Predecessor revisions:**`; line 7 starts with `- v34 — 2026-05-16 (**PR18 — locale-CRUD bundle shipped` | ✅ |
| `aidstation-sources/CLAUDE.md` last-shipped narrative begins with `PR19 — retire legacy LOCALES` | ✅ |
| `aidstation-sources/CLAUDE.md` Backlog reference is `Project_Backlog_v35.md` | ✅ |
| `aidstation-sources/CLAUDE.md` Next-forward-move drops the Item E candidate | ✅ |
| `PR_Verification_Status.md` has a new `## PR19 — retire legacy LOCALES external consumers (PR18 follow-on Item E; pending merge)` section with 11 step rows | ✅ |
| `PR_Verification_Status.md` aggregate table row for PR19 = `0 / 0 / 11 / 0 / 11`; totals = `52 / 21 / 37 / 4 / 114` | ✅ |
| `PR_Verification_Status.md` headlines section reflects post-PR19 ship state (37 doable-now) | ✅ |

---

## 8. Carry-forward from PR18 + adjacent tracks (informational)

- PR18 §5.0 — 12 testable steps owed; pending Vercel deploy + walk.
- PR11 step 6 — currently 🟡 blocked on PR18 item B; unblocks once PR18 deploys (PR18 closing handoff §5.4).
- Park-tags taxonomy follow-up — still deferred per PR18 §5.2 + §5.1 above.
- Layer 4 prompt-body arc — 3 of 5 prompts shipped (seam-reviewer + per-phase + single-session); per-tier T1/T2 + race-week-brief queued.
- Layer 4 §14 retrospective — still owed; lands before Layer 4 implementation per §12.6 deferral.

---

**End of handoff.** PR19 ships the PR18 closing handoff §5.1 Item E — retires `LOCALES` as an external dependency from `routes/coaching.py` + `routes/references.py` + the references template. 6 substantive code files + 4 bookkeeping; 1 over the 5-file ceiling (3 of the 6 are tight template edits). Form-level guard on coaching POST validation (no silent rewrite). Athlete-locale-aware references filter with category → Layer 0 bucket mapping. Internal `LOCALES` in `routes/locales.py` preserved for legacy-card auto-render + deletability gate + dup-check helper. Item E story closed. PR_Verification_Status now reads 52 ✅ / 21 ⏸ / 37 🟡 / 4 ⚪ of 114 post-PR19-ship.
