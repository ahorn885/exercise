"""Profile-tab race-event CRUD (D-66 §7).

Surfaces `/profile/race-events/...` routes for the athlete to manage
their race calendar — list lives in the `/profile?tab=race-events` tab
(rendered via `routes/profile.py:edit()` + the `_race_events_tab.html`
partial); add/edit/delete + route-locale + equipment CRUD ships here.

All routes are scoped to `current_user_id()` — every helper from
`race_events_repo` takes `user_id` and filters in the WHERE clause so a
crafted POST can't reach another user's row.

Route-locale ordering uses a direct `sequence_idx` integer input (no
drag-and-drop in v1 — gaps allowed per the design contract; v2 can layer
a drag-reorder UX on top once the v5 onboarding implementation PR lands
the JS surface area).
"""

from __future__ import annotations

import re
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify

import mapbox_client
from athlete import get_athlete_profile
from database import get_db
from discipline_display_names import discipline_display_name
from race_events_invalidation import (
    evict_on_target_event_brief_field_change,
    evict_on_target_event_framework_sport_change,
    evict_on_target_event_included_discipline_ids_change,
    evict_on_target_event_periodization_change,
)
from race_events_repo import (
    VALID_DNF_CAUSES,
    VALID_GOAL_OUTCOMES,
    VALID_PREVIOUS_ATTEMPT_OUTCOMES,
    VALID_RACE_FORMATS,
    VALID_ROUTE_LOCALE_ROLES,
    add_route_locale,
    add_route_locale_equipment,
    create_race_event,
    delete_race_event,
    delete_route_locale,
    delete_route_locale_equipment,
    get_race_event,
    list_athlete_race_events,
    list_route_locale_equipment,
    list_route_locales,
    set_target_event,
    update_race_event,
    update_race_event_locale,
    update_route_locale,
)
from routes.auth import current_user_id
from routes.locales import (
    MAPBOX_DISCLOSURE_VERSION,
    _disclosure_acked,
    _record_disclosure_ack,
)
from race_url_parser import (
    DisciplineOption,
    RaceURLParseError,
    RaceURLParseInput,
    TerrainVocabEntry,
    fetch_and_reduce,
    parse_race_url,
)
from race_terrain_inference import (
    TerrainInferenceError,
    TerrainInferenceInput,
    infer_terrain,
)
from weather_client import get_expected_conditions


bp = Blueprint('race_events', __name__, url_prefix='/profile/race-events')


_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")

# Issue #445 — training-only environments (climbing gym, pump track, indoor
# gym) never host a real race, so they're filtered out of the race-event
# terrain selector. Mirrors the `race_eligible: False` terrain rows in
# `etl/layer0/extractors/vocabulary.py` (its `RACE_INELIGIBLE_TERRAIN_IDS`).
# Kept route-side rather than imported from the ETL layer to preserve the
# app/ETL separation; a consistency test pins it to the vocab source so the
# two can't drift. The same terrains stay visible on the locale/training
# pickers (`routes/locales.py`), which are NOT filtered — they're real
# training venues. Promoting the flag to a `layer0.terrain_types.race_eligible`
# column (schema + ETL + a `WHERE race_eligible` clause) is the clean
# follow-up; until then these stable TRN ids carry it code-side.
RACE_INELIGIBLE_TERRAIN_IDS = frozenset({'TRN-014', 'TRN-015', 'TRN-016'})


def _terrain_choices(db) -> list[dict]:
    """Return `{id, label, description}` dicts for race-eligible
    `layer0.terrain_types` rows.

    Used by the race-event edit template to populate the per-row terrain
    dropdown. `id` is the canonical TRN-xxx slug; `label` is the
    `canonical_name`; `description` is the row `notes` (rendered as a hover
    tooltip so opaque labels like "Technical Rock" are self-explanatory —
    issue #444). Training-only terrains are dropped (issue #445). ORDER BY
    terrain_id for stable rendering; ~16 rows so no caching.
    """
    # D-73 Phase 5.2 Bucket E.(a) — defensive `terrain_id IS NOT NULL`
    # filter. The original pre-r2 `layer0.terrain_types` rows (canonical
    # names only, no TRN-xxx ID) are superseded by `migrate_terrain_types.sql`,
    # but production Neon DBs that haven't run the standalone migration
    # script surface those rows here with `terrain_id IS NULL`. The
    # template renders `{{ tc.id }}` for each row, so NULL ids show as
    # literal "None" prepended to the canonical name in the dropdown.
    # Filtering at the query keeps the dropdown clean regardless of the
    # migration's run-state on each environment.
    cur = db.execute(
        'SELECT terrain_id, canonical_name, notes FROM layer0.terrain_types '
        'WHERE superseded_at IS NULL AND terrain_id IS NOT NULL '
        'ORDER BY terrain_id'
    )
    return [
        {'id': r['terrain_id'], 'label': r['canonical_name'],
         'description': r['notes']}
        for r in cur.fetchall()
        if r['terrain_id'] not in RACE_INELIGIBLE_TERRAIN_IDS
    ]


def _parse_race_terrain(form) -> list[dict]:
    """Parse the repeating `race_terrain[N][...]` form fields into a list
    of `{"terrain_id": str, "pct_of_race": float, "discipline_id": str|None}`
    dicts.

    Empty rows (no terrain_id selected OR no percent entered) are silently
    dropped — athletes adding a row then leaving it blank shouldn't fail
    the save. Invalid terrain_id (not matching TRN-\\d{3}) or invalid
    percent (non-numeric / out of [0, 100]) drops the row and skips it.

    D-73 Phase 5.2 Bucket E.(c)-C1 — optional per-row `discipline_id`
    coupling. Blank string parses as None (race-wide terrain); any
    non-empty value is stored verbatim (validation against the race's
    `included_discipline_ids` is enforced by Layer 2A's bridge — invalid
    IDs simply produce no match and the terrain row falls through as
    race-wide for downstream consumers).
    """
    out: list[dict] = []
    # Discover the row indices used by the template (form names like
    # `race_terrain[0][terrain_id]`, `race_terrain[1][pct_of_race]`,
    # `race_terrain[1][discipline_id]`).
    indices: set[int] = set()
    for key in form.keys():
        m = re.match(
            r"^race_terrain\[(\d+)\]\[(terrain_id|pct_of_race|discipline_id)\]$",
            key,
        )
        if m:
            indices.add(int(m.group(1)))
    for idx in sorted(indices):
        terrain_id = (form.get(f'race_terrain[{idx}][terrain_id]') or '').strip()
        pct_raw = (form.get(f'race_terrain[{idx}][pct_of_race]') or '').strip()
        if not terrain_id or not pct_raw:
            continue
        if not _TRN_PATTERN.match(terrain_id):
            continue
        try:
            pct = float(pct_raw)
        except (ValueError, TypeError):
            continue
        if not (0.0 <= pct <= 100.0):
            continue
        discipline_id = (
            form.get(f'race_terrain[{idx}][discipline_id]') or ''
        ).strip() or None
        out.append({
            'terrain_id': terrain_id,
            'pct_of_race': pct,
            'discipline_id': discipline_id,
        })
    return out


def _parse_discipline_id_filter(form) -> list[str] | None:
    """Parse the repeating `included_discipline_ids` form fields into a
    canonical-id list, or None when no boxes are checked.

    Form renders as a Bootstrap checkbox grid keyed on
    `included_discipline_ids` (same name for every checkbox; Flask's
    `request.form.getlist` returns the checked subset). Empty selection
    returns None so Layer 2A reverts to bridge defaults (pre-B2 behavior);
    a non-empty subset narrows the classifier output. Whitespace stripped
    + empty strings filtered defensively.
    """
    if hasattr(form, 'getlist'):
        raw = form.getlist('included_discipline_ids')
    else:
        raw = []
    values = [v.strip() for v in raw if isinstance(v, str) and v and v.strip()]
    return values or None


def _terrain_discipline_mismatches(
    race_terrain: list[dict], included_discipline_ids: list[str] | None
) -> list[str]:
    """Return the sorted, de-duplicated discipline IDs that terrain rows
    scope to but that are *not* among the race's included disciplines.

    Issue #342 — the terrain editor's per-row discipline `<select>` offers
    every discipline mapped to the race's `framework_sport` (the full
    `sport_discipline_bridge` set), not just the athlete's included subset,
    so a row can be scoped to a discipline the race doesn't actually
    include. Layer 2A then silently ignores that terrain row (no bridge
    match → falls through as race-wide), creating a confusing mismatch
    ("terrain says road cycling matters here" while the discipline list
    says the athlete doesn't do road cycling in this race). The save routes
    treat any mismatch as a blocking validation error.

    When `included_discipline_ids` is None/empty the athlete hasn't narrowed
    the set — Layer 2A falls back to the full `framework_sport` bridge, so
    every discipline the per-row select could offer is in scope and there
    is no mismatch. An empty result means "no mismatch".
    """
    if not included_discipline_ids:
        return []
    included = set(included_discipline_ids)
    offending = {
        entry['discipline_id']
        for entry in race_terrain
        if entry.get('discipline_id') and entry['discipline_id'] not in included
    }
    return sorted(offending)


def _terrain_discipline_mismatch_flash(mismatches: list[str]) -> str:
    """Build the athlete-facing flash copy for an issue #342 mismatch.

    Centralised so the wording stays identical across the new-race,
    update-race, and onboarding target-race save paths.
    """
    ids = ', '.join(mismatches)
    plural = len(mismatches) > 1
    return (
        f'Terrain is scoped to discipline{"s" if plural else ""} '
        f'({ids}) that {"are" if plural else "is"} not in this race’s '
        f'included disciplines. Either add {"them" if plural else "it"} to '
        'the discipline list above, or set the terrain row’s discipline '
        'back to "Race-wide".'
    )


def _disciplines_for_framework_sport(db, framework_sport: str) -> list[dict]:
    """Return `{id, label}` dicts for disciplines mapped to a
    `framework_sport` via `layer0.sport_discipline_bridge`.

    Mirrors `_terrain_choices` shape. Used by the B2 checkbox grid (and
    the C1 per-row terrain `<select>`) to render the discipline set for
    the race's chosen sport. Empty list when the framework_sport doesn't
    resolve in the bridge — the template renders a "Discipline filtering
    not available for this sport" empty state rather than failing.

    The bridge directly answers "for this framework_sport, what
    canonical disciplines are in scope," which is the same set Layer 2A's
    classifier surfaces post-filter. Filters `superseded_at IS NULL` to
    use the current canonical mapping; runtime pinning is handled
    separately by Layer 2A's `etl_version_set`.

    The label is the curated pure-craft `discipline_display_name`; the
    bridge's own `discipline_name` (the sport-variant Sheet-3 label) is
    the fallback for ids not yet curated.
    """
    if not framework_sport:
        return []
    cur = db.execute(
        """
        SELECT discipline_id, discipline_name
          FROM layer0.sport_discipline_bridge
         WHERE framework_sport = ?
           AND superseded_at IS NULL
         ORDER BY discipline_id
        """,
        (framework_sport,),
    )
    return [
        {'id': r['discipline_id'],
         'label': discipline_display_name(r['discipline_id'], r['discipline_name'])}
        for r in cur.fetchall()
    ]


# ─── #892 — discipline persistence across a sport/event-type change ──────────
# The "race event type" (framework_sport) gates which disciplines the bridge
# considers "included." Changing it used to WIPE the race's discipline picks
# (and silently orphan per-terrain-row couplings), so the picker collapsed to
# "Race-wide" / "not included in disciplines." These helpers keep the race's
# own disciplines rendering, and re-map (rather than wipe) the narrowing when
# the sport changes. Paired with the #885 structured select (which stops new
# free-text drift) + the init_db normalize-match backfill (which heals existing
# case/whitespace drift).


def _race_saved_discipline_ids(race: dict | None) -> list[str]:
    """Canonical discipline IDs a race already references.

    Its `included_discipline_ids` narrowing plus any per-terrain-row
    `discipline_id` couplings, de-duplicated with order preserved (included
    first, then terrain couplings). Empty list for a new / None race.
    """
    if not race:
        return []
    out: list[str] = []
    for did in (race.get('included_discipline_ids') or []):
        if did and did not in out:
            out.append(did)
    for entry in (race.get('race_terrain') or []):
        did = entry.get('discipline_id') if isinstance(entry, dict) else None
        if did and did not in out:
            out.append(did)
    return out


def _discipline_choices_for_race(db, framework_sport, race) -> list[dict]:
    """`{id, label}` discipline choices for the race-form pickers (#892).

    The `framework_sport` bridge set UNION the race's already-saved
    disciplines. Surfacing the saved disciplines keeps the checkbox grid + the
    per-row terrain `<select>` rendering the race's own disciplines instead of
    collapsing to "Race-wide" when the sport is blank, doesn't resolve in the
    bridge, or maps to a set that no longer contains a previously-saved pick.
    Bridge order first; saved-but-unlisted IDs append in id order for stable
    rendering. For a healthy race (every saved id is in the bridge) the union
    equals the bridge set, so this is a no-op there.
    """
    choices = _disciplines_for_framework_sport(db, framework_sport or '')
    present = {c['id'] for c in choices}
    extras = sorted(
        did for did in _race_saved_discipline_ids(race) if did not in present
    )
    choices.extend(
        {'id': did, 'label': discipline_display_name(did)} for did in extras
    )
    return choices


def _remap_discipline_filter_on_sport_change(
    db, new_framework_sport, submitted_filter, prior_filter
) -> tuple[list[str] | None, list[str]]:
    """Carry the discipline narrowing across a framework_sport change instead
    of wiping it (#892).

    Canonical discipline IDs are global, so a prior pick can stay valid for the
    new sport. Keep the subset that resolves in the new sport's bridge and drop
    the rest. Prefer the freshly-submitted grid (the athlete may have re-picked
    for the new sport) but fall back to the prior selection when the grid
    round-tripped empty — e.g. the new sport didn't resolve client-side and the
    picker collapsed — so editing the sport alone never silently clears the
    disciplines. When the new sport doesn't resolve in the bridge at all there
    is no set to validate against, so the selection is kept verbatim (Layer 2A
    surfaces `no_disciplines_for_sport` for the sport itself — the
    resolvable-sport concern #885 owns, not data loss).

    Returns `(new_filter, dropped_ids)`:
      - new_filter: the re-mapped narrowing list, or None meaning "use the new
        sport's full bridge defaults" (empty intersection / nothing selected).
      - dropped_ids: prior picks that did not survive, for the flash hint.
    """
    source = list(submitted_filter) if submitted_filter else list(prior_filter or [])
    valid_ids = {
        d['id'] for d in _disciplines_for_framework_sport(db, new_framework_sport or '')
    }
    if not valid_ids:
        kept = source
        dropped: list[str] = []
    else:
        kept = [d for d in source if d in valid_ids]
        dropped = [d for d in (prior_filter or []) if d not in valid_ids]
    deduped: list[str] = []
    for d in kept:
        if d not in deduped:
            deduped.append(d)
    return (deduped or None), dropped


def _rescope_terrain_to_included(race_terrain, included_filter):
    """Drop per-row terrain discipline couplings that fall outside the
    effective included set (#892 / #342).

    Preserves each row's `terrain_id` + `pct_of_race`; only resets
    `discipline_id` to None (race-wide) when it isn't in `included_filter`, so
    a sport change re-scopes an orphaned coupling instead of tripping the #342
    mismatch block on a simple edit. A falsy `included_filter` means "use
    bridge defaults" (no narrowing), so couplings are left untouched.
    """
    if not included_filter:
        return race_terrain
    allowed = set(included_filter)
    return [
        {**row, 'discipline_id': (
            row['discipline_id'] if row.get('discipline_id') in allowed else None
        )}
        for row in race_terrain
    ]


def _framework_sport_choices(db) -> list[str]:
    """Canonical race/event types for the structured "Race event type" select.

    Issue #885 — the field was a free-text `<input>`; an athlete could save a
    value that didn't exactly match any `layer0.sport_discipline_bridge`
    `framework_sport`, so `_disciplines_for_framework_sport` returned [] and the
    discipline grid (plus every per-row terrain `<select>`) collapsed to empty /
    "Race-wide" — the data-loss bug #892. Sourcing the options from the DISTINCT
    `framework_sport` values in the same bridge table the discipline grid reads
    keeps the event type and its disciplines in lockstep: every selectable
    option resolves to a non-empty discipline set by construction.

    `superseded_at IS NULL` uses the current canonical mapping (runtime pinning
    is Layer 2A's `etl_version_set` concern, same as `_disciplines_for_…`).
    """
    cur = db.execute(
        """
        SELECT DISTINCT framework_sport
          FROM layer0.sport_discipline_bridge
         WHERE superseded_at IS NULL
           AND framework_sport IS NOT NULL
         ORDER BY framework_sport
        """
    )
    return [r['framework_sport'] for r in cur.fetchall() if r['framework_sport']]


# ─── #256/#592 race-detail auto-fill (parse a race URL + terrain fallback) ───
# Build spec: aidstation-sources/designs/Race_URL_Parser_Spec_v1.md. The two
# JSON endpoints further down (parse_url + infer_terrain_suggestion) back the
# "Fetch details from URL" button + the location->terrain fallback; the
# testable cores are the run_* helpers below (helper-level pytest per this
# module's convention — full route integration is manual-walkthrough).


def _all_disciplines(db) -> list[dict]:
    """`{id, label}` for every canonical discipline in the bridge (one per id).
    The race-URL parse passes this as the discipline catalogue the model may
    pick `included_discipline_ids` from — it infers the sport, so the catalogue
    can't be pre-filtered to one framework_sport."""
    cur = db.execute(
        'SELECT DISTINCT ON (discipline_id) discipline_id, discipline_name '
        'FROM layer0.sport_discipline_bridge '
        'WHERE superseded_at IS NULL ORDER BY discipline_id'
    )
    return [
        {'id': r['discipline_id'],
         'label': discipline_display_name(r['discipline_id'], r['discipline_name'])}
        for r in cur.fetchall()
    ]


def _terrain_vocab_entries(db) -> tuple[TerrainVocabEntry, ...]:
    """Race-eligible terrain vocab as the parser/inference value type."""
    return tuple(TerrainVocabEntry(c['id'], c['label']) for c in _terrain_choices(db))


def _discipline_options(rows: list[dict]) -> tuple[DisciplineOption, ...]:
    return tuple(DisciplineOption(d['id'], d['label']) for d in rows)


_PARSE_FAIL_HINT = "Couldn't read race details from that page — fill the form in by hand."


def _url_parse_payload(r) -> dict:
    """Map a RaceURLParseResult to the JSON the form JS pre-fills from."""
    return {
        'ok': True,
        'fields': {
            'name': r.name,
            'event_date': r.event_date.isoformat() if r.event_date else None,
            'race_format': r.race_format,
            'total_elevation_gain_m': r.total_elevation_gain_m,
            'location_text': r.location_text,
            'framework_sport': r.framework_sport,
            'included_discipline_ids': r.included_discipline_ids,
            'rules_notes': r.rules_notes,
        },
        'distance_options': [
            {'label': o.label, 'distance_km': o.distance_km,
             'event_date': o.event_date.isoformat() if o.event_date else None,
             'elevation_gain_m': o.elevation_gain_m}
            for o in r.distance_options
        ],
        'terrain': (
            {'entries': [{'terrain_id': e.terrain_id, 'pct_of_race': e.pct_of_race,
                          'discipline_id': e.discipline_id} for e in r.race_terrain],
             'pct_basis': r.terrain_pct_basis}
            if r.race_terrain else None
        ),
        'confidence': r.confidence,
        'summary': r.summary,
    }


def run_url_parse(db, url: str, *, today=None, fetcher=None, parser=None) -> dict:
    """Testable core of the parse-url endpoint: fetch+reduce -> parse -> JSON
    payload. Best-effort: a fetch failure or an unrecoverable parse error
    returns `{ok: False, hint}` so the form is left for manual entry."""
    reduced = fetch_and_reduce(url, fetcher=fetcher)
    if reduced is None:
        return {'ok': False, 'hint': _PARSE_FAIL_HINT}
    inp = RaceURLParseInput(
        reduced_page_text=reduced.text, source_url=url,
        terrain_vocab=_terrain_vocab_entries(db),
        sport_bridge=_discipline_options(_all_disciplines(db)),
        today=today or date.today(),
    )
    parse = parser or parse_race_url
    try:
        result = parse(inp)
    except RaceURLParseError:
        return {'ok': False, 'hint': _PARSE_FAIL_HINT}
    return _url_parse_payload(result)


def run_terrain_inference(
    db, *, lat, lng, place_name=None, event_date=None, race_name=None,
    distance_km=None, elevation_gain_m=None, race_format=None,
    framework_sport=None, notes=None, race_url=None, today=None,
    infer=None, weather=None,
) -> dict:
    """Testable core of the infer-terrain endpoint (the #592 subordinate
    fallback). Runs the terrain inference (only with coords) + the deterministic
    climate-normals nudge. Best-effort: an inference failure returns terrain
    None (the athlete sees the empty editor); the conditions half is
    independent (a page never carries climate normals)."""
    weather_fn = weather or get_expected_conditions
    conditions = None
    if lat is not None and lng is not None and event_date is not None:
        ec = weather_fn(lat, lng, event_date)
        conditions = ec.summary_line() if ec else None

    terrain = None
    if lat is not None and lng is not None:
        disciplines = _discipline_options(
            _disciplines_for_framework_sport(db, framework_sport or '')
        )
        inp = TerrainInferenceInput(
            place_name=place_name, lat=lat, lng=lng, race_name=race_name,
            distance_km=distance_km, elevation_gain_m=elevation_gain_m,
            race_format=race_format, event_date=event_date, disciplines=disciplines,
            notes_context=notes, race_url=race_url,
            terrain_vocab=_terrain_vocab_entries(db), today=today or date.today(),
        )
        infer_fn = infer or infer_terrain
        try:
            res = infer_fn(inp)
            terrain = {'entries': res.as_race_terrain(),
                       'confidence': res.confidence, 'summary': res.summary}
        except TerrainInferenceError:
            terrain = None
    return {'ok': True, 'terrain': terrain, 'conditions': conditions}


def _resolve_effective_framework_sport(db, user_id: int, race: dict | None) -> str | None:
    """Resolve the framework_sport to use for initial discipline-grid render.

    Mirrors the orchestrator's planning-sport resolution
    (`layer4/orchestrator.py` `_resolve_planning_sport`, #447): the race's
    `framework_sport` is the planning sport when a target race carries one;
    otherwise fall back to the athlete-profile `primary_sport` (home
    discipline / no-race case). Returns None when neither is set — the
    template then renders an empty discipline grid with helper copy pointing
    the athlete at the framework_sport field.
    """
    race_sport = (race or {}).get('framework_sport') if race else None
    if race_sport:
        return race_sport
    profile = get_athlete_profile(db, user_id) or {}
    return profile.get('primary_sport') or None


def _run_mapbox_search(query: str) -> tuple[list[dict], str | None]:
    """Fire a Mapbox Search Box API forward call for the race-location picker.

    Mirrors the `/locales/new` GET-side flow at `routes/locales.py:766-774`.
    Returns `(results, error_text)` — error is human-readable copy ready
    for inline display. Empty query short-circuits to ([], None) without
    a Mapbox call.
    """
    if not query:
        return [], None
    try:
        results = mapbox_client.search_places(query, limit=5)
    except mapbox_client.MapboxTokenMissing:
        return [], (
            'Place lookup is not configured on the server. '
            'Save the race without a location for now; an admin will need to '
            'set MAPBOX_PUBLIC_TOKEN on the server.'
        )
    except mapbox_client.MapboxNoResults:
        return [], f'No matches for {query!r}. Try a broader search.'
    except mapbox_client.MapboxError as e:
        return [], f'Place lookup unavailable ({e}). Try again.'
    return results, None


def _extract_mapbox_locale_from_form(form) -> dict:
    """Extract the 5 Mapbox-anchored race-location hidden fields from a form.

    Returns a dict keyed on the canonical column names. Blank strings coerce
    to None; non-numeric lat/lng coerce to None so a malformed POST cannot
    set NaN coords. Used by `new_race` POST + `update_race` POST so the
    Mapbox fields ride alongside the rest of the race form per the
    JS-result-click design — picking a search result populates the hidden
    inputs, and the next form submit carries them through.
    """
    name = (form.get('event_locale_name') or '').strip() or None
    mapbox_id = (form.get('event_locale_mapbox_id') or '').strip() or None
    place_name = (form.get('event_locale_place_name') or '').strip() or None

    def _coerce_coord(raw):
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    return {
        'event_locale_name': name,
        'event_locale_mapbox_id': mapbox_id,
        'event_locale_place_name': place_name,
        'event_locale_lat': _coerce_coord(form.get('event_locale_lat')),
        'event_locale_lng': _coerce_coord(form.get('event_locale_lng')),
    }


def _parse_race_url(form) -> str | None:
    """D-73 Phase 5.2 walkthrough #2a — parse the race-director site URL.

    Trims whitespace; collapses empty to None. Athletes paste whatever they
    have so the column is stored verbatim (no scheme normalization). 1000-char
    cap matches `RaceEventPayload.race_url` Field max.
    """
    v = (form.get('race_url') or '').strip()
    if not v:
        return None
    return v[:1000]


def _parse_str(form, key: str) -> str | None:
    v = (form.get(key) or '').strip()
    return v or None


def _parse_decimal(form, key: str):
    v = (form.get(key) or '').strip()
    if not v:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_date(form, key: str):
    v = (form.get(key) or '').strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_int(form, key: str) -> int | None:
    v = (form.get(key) or '').strip()
    if not v:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _parse_estimated_duration_hr(form):
    """Parse `estimated_duration_hr` (hours). Non-positive / non-numeric
    coerce to None so a stray 0 can't trip the DB CHECK (> 0) or the
    `RaceEventPayload` Field(gt=0) backstop. Blank = None (athlete left it
    unset; orchestrator falls back to the format-keyed estimate).
    """
    v = _parse_decimal(form, 'estimated_duration_hr')
    if v is None or v <= 0:
        return None
    return v


def _parse_primary_metric(form) -> str | None:
    """Parse the `primary_metric` selector ('distance' | 'duration').
    Anything outside the closed set (incl. blank) coerces to None — the
    repo layer validates again, and a None round-trips as "no explicit
    framing" (form defaults to distance).
    """
    v = (form.get('primary_metric') or '').strip()
    return v if v in ('distance', 'duration') else None


def _parse_goal_outcome(form) -> str | None:
    """Parse the §H.2 `goal_outcome` selector. Anything outside the closed set
    (incl. blank) coerces to None — the cached Layer 3B wrapper then falls
    back to the conservative "Finish" tier. Repo + DB CHECK validate again."""
    v = (form.get('goal_outcome') or '').strip()
    return v if v in VALID_GOAL_OUTCOMES else None


def _parse_first_time_at_distance(form) -> bool | None:
    """Parse the §H.2 `first_time_at_distance` tri-state selector:
    'yes' → True, 'no' → False, blank/anything else → None (not answered)."""
    v = (form.get('first_time_at_distance') or '').strip().lower()
    if v == 'yes':
        return True
    if v == 'no':
        return False
    return None


def _parse_pack_weight_kg(form):
    """Parse the §H.2 `race_pack_weight_kg` number input. Negative / non-numeric
    coerce to None (the DB CHECK is >= 0; the payload Field is ge=0). Blank =
    None (not captured)."""
    v = _parse_decimal(form, 'race_pack_weight_kg')
    if v is None or v < 0:
        return None
    return v


def _parse_previous_attempts(form) -> list[dict]:
    """Parse the repeating `previous_attempts[N][...]` form fields into a list
    of `{"outcome": str, "dnf_cause": str|None}` dicts (§H.2 Slice 2).

    Mirrors `_parse_race_terrain`'s indexed-field discovery + drop-on-empty
    semantics. A row with no (or out-of-vocab) `outcome` is dropped — an
    empty attempt row shouldn't fail the save. `dnf_cause` outside
    `VALID_DNF_CAUSES` (incl. blank) collapses to None; it only matters for
    DNF rows (it keys Layer 3B's recovery-window mapping, which defaults
    unknown/None to 8 weeks).
    """
    out: list[dict] = []
    indices: set[int] = set()
    for key in form.keys():
        m = re.match(
            r"^previous_attempts\[(\d+)\]\[(outcome|dnf_cause)\]$",
            key,
        )
        if m:
            indices.add(int(m.group(1)))
    for idx in sorted(indices):
        outcome = (form.get(f'previous_attempts[{idx}][outcome]') or '').strip()
        if outcome not in VALID_PREVIOUS_ATTEMPT_OUTCOMES:
            continue
        cause = (form.get(f'previous_attempts[{idx}][dnf_cause]') or '').strip()
        dnf_cause = cause if cause in VALID_DNF_CAUSES else None
        out.append({'outcome': outcome, 'dnf_cause': dnf_cause})
    return out


def _coerce_event_date(value):
    """Coerce a stored `event_date` to a `date`, or None.

    Postgres hands back a `date`; the SQLite dev fallback hands back an ISO
    `'YYYY-MM-DD'` string. The manager listing compares against today to
    bucket upcoming/past + compute weeks-out, so normalize both shapes here.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _tab_redirect():
    return redirect(url_for('race_events.index'))


@bp.route('/', methods=['GET'])
def index():
    """Standalone Races · event manager (redesign §10).

    Promotes the race calendar out of the `/profile?tab=race-events` tab into
    a first-class page under Plan. The target race drives Layer 3
    periodization + the pre-race-week brief, so it gets a spotlight; the
    remaining races split into upcoming / past by `event_date`. Per-race edit
    (route locales, equipment, Mapbox anchor) still lives on `edit_race`;
    create / set-target / delete reuse the existing POST handlers, which now
    land back here via `_tab_redirect`.
    """
    db = get_db()
    uid = current_user_id()
    races = list_athlete_race_events(db, uid)
    today = date.today()

    target = None
    upcoming: list[dict] = []
    past: list[dict] = []
    for r in races:
        ed = _coerce_event_date(r['event_date'])
        r['event_date_d'] = ed
        r['weeks_out'] = (ed - today).days // 7 if ed and ed >= today else None
        if r['is_target_event']:
            target = r
            continue
        if ed is not None and ed < today:
            past.append(r)
        else:
            upcoming.append(r)

    # The repo returns event_date ascending; show past races most-recent-first.
    past.reverse()

    target_upcoming = bool(
        target and (target['event_date_d'] is None or target['event_date_d'] >= today)
    )
    upcoming_count = len(upcoming) + (1 if target_upcoming else 0)

    return render_template(
        'profile/race_events.html',
        target=target,
        upcoming=upcoming,
        past=past,
        upcoming_count=upcoming_count,
    )


@bp.route('/new', methods=['GET', 'POST'])
def new_race():
    """Render + accept the create form for a new race_events row."""
    db = get_db()
    uid = current_user_id()

    if request.method == 'POST':
        name = _parse_str(request.form, 'name')
        event_date = _parse_date(request.form, 'event_date')
        race_format = (request.form.get('race_format') or '').strip()

        if not name:
            flash('Race name is required.', 'danger')
            return redirect(url_for('race_events.new_race'))
        if not event_date:
            flash('Race date is required (YYYY-MM-DD).', 'danger')
            return redirect(url_for('race_events.new_race'))
        if race_format not in VALID_RACE_FORMATS:
            flash('Pick a race format.', 'danger')
            return redirect(url_for('race_events.new_race'))

        # D-73 Phase 5.2 walkthrough #1 — Mapbox-anchored race location
        # fields ride through as hidden inputs (populated by the
        # search-result-click JS handler in the template).
        locale_fields = _extract_mapbox_locale_from_form(request.form)
        # D-73 Phase 5.2 Bucket C (i) — race location is required. Pydantic
        # backstops this at RaceEventPayload construction; the flash here is
        # the athlete-facing UX.
        if not locale_fields['event_locale_mapbox_id']:
            flash('Pick a race location before saving.', 'danger')
            return redirect(url_for('race_events.new_race'))

        new_race_terrain = _parse_race_terrain(request.form)
        new_discipline_filter = _parse_discipline_id_filter(request.form)
        # Issue #342 — block terrain rows scoped to a discipline the race
        # doesn't include. No prior selection to auto-clear on the create
        # path, so validate the parsed values directly.
        mismatches = _terrain_discipline_mismatches(
            new_race_terrain, new_discipline_filter
        )
        if mismatches:
            flash(_terrain_discipline_mismatch_flash(mismatches), 'danger')
            return redirect(url_for('race_events.new_race'))

        race_event_id = create_race_event(
            db, uid,
            name=name,
            event_date=event_date,
            race_format=race_format,
            distance_km=_parse_decimal(request.form, 'distance_km'),
            total_elevation_gain_m=_parse_decimal(
                request.form, 'total_elevation_gain_m'
            ),
            estimated_duration_hr=_parse_estimated_duration_hr(request.form),
            primary_metric=_parse_primary_metric(request.form),
            notes=_parse_str(request.form, 'notes'),
            race_terrain=new_race_terrain,
            previous_attempts=_parse_previous_attempts(request.form),
            race_url=_parse_race_url(request.form),
            framework_sport=_parse_str(request.form, 'framework_sport'),
            included_discipline_ids=new_discipline_filter,
            goal_outcome=_parse_goal_outcome(request.form),
            first_time_at_distance=_parse_first_time_at_distance(request.form),
            time_goal=_parse_str(request.form, 'time_goal'),
            race_pack_weight_kg=_parse_pack_weight_kg(request.form),
            **locale_fields,
        )
        flash(f'Race "{name}" added.', 'success')
        # Multi-day races immediately go to the edit page so the athlete
        # can fill in route locales; single-day races bounce back to the
        # tab listing.
        if race_format != 'single_day':
            return redirect(
                url_for('race_events.edit_race', race_event_id=race_event_id)
            )
        return _tab_redirect()

    terrain_choices = _terrain_choices(db)
    # D-73 Phase 5.2 Bucket E.(b)-B2 + E.(c)-C1 — discipline grid for the
    # B2 `<select multiple>` rendered as checkboxes + the per-row terrain
    # discipline_id `<select>`. Initial render uses the athlete's
    # primary_sport (no race exists yet for the new-race path); client-
    # side JS rebinds when athlete edits the framework_sport input via the
    # `/profile/race-events/disciplines/search` endpoint.
    initial_framework_sport = _resolve_effective_framework_sport(db, uid, None)
    # #892 — union the bridge set with the race's saved disciplines (none here
    # on the new-race path, so a plain bridge set) so the picker never collapses.
    discipline_choices = _discipline_choices_for_race(db, initial_framework_sport, None)
    framework_sport_choices = _framework_sport_choices(db)
    # D-73 Phase 5.2 walkthrough #1 — Mapbox-anchored race-location picker.
    # The search box + result list are rendered + driven by the inline
    # `<script nonce="..."` block in `templates/_race_locale_picker.html`
    # which fetches from the JSON `locale_search` endpoint and fills the
    # 5 hidden inputs on result-click. This sidesteps the form-state
    # preservation problem the GET round-trip would have introduced
    # (the merged race notes field can be multi-KB and the URL line
    # limit is 8KB).
    return render_template(
        'profile/race_event_edit.html',
        race=None,
        race_locales=[],
        equipment_by_locale={},
        terrain_choices=terrain_choices,
        discipline_choices=discipline_choices,
        initial_framework_sport=initial_framework_sport,
        framework_sport_choices=framework_sport_choices,
        race_formats=VALID_RACE_FORMATS,
        route_locale_roles=VALID_ROUTE_LOCALE_ROLES,
        is_new=True,
        mapbox_acked=_disclosure_acked(db, uid),
        mapbox_disclosure_version=MAPBOX_DISCLOSURE_VERSION,
    )


@bp.route('/<int:race_event_id>/edit', methods=['GET'])
def edit_race(race_event_id: int):
    """Render the per-race edit page — race details form + route-locale
    list with per-row inline forms + nested equipment add/delete.

    The race-location picker fires Mapbox via `?locale_q=...` (server-side
    `mapbox_client.search_places`) and renders results inline. Result-click
    POSTs to `race_events.set_locale` which updates the 5 Mapbox columns
    standalone (decoupled from the main race-details form so the edit page
    behaves like the existing inline route-locale + equipment forms).
    """
    db = get_db()
    uid = current_user_id()

    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    race_locales = list_route_locales(db, race_event_id)
    equipment_by_locale = {
        rl['id']: list_route_locale_equipment(db, rl['id'])
        for rl in race_locales
    }
    terrain_choices = _terrain_choices(db)
    initial_framework_sport = _resolve_effective_framework_sport(db, uid, race)
    # #892 — union the bridge set with the race's own saved disciplines so the
    # picker renders them even when the sport is blank / doesn't resolve in the
    # bridge, instead of collapsing to "Race-wide."
    discipline_choices = _discipline_choices_for_race(db, initial_framework_sport, race)
    framework_sport_choices = _framework_sport_choices(db)
    return render_template(
        'profile/race_event_edit.html',
        race=race,
        race_locales=race_locales,
        equipment_by_locale=equipment_by_locale,
        terrain_choices=terrain_choices,
        discipline_choices=discipline_choices,
        initial_framework_sport=initial_framework_sport,
        framework_sport_choices=framework_sport_choices,
        race_formats=VALID_RACE_FORMATS,
        route_locale_roles=VALID_ROUTE_LOCALE_ROLES,
        is_new=False,
        mapbox_acked=_disclosure_acked(db, uid),
        mapbox_disclosure_version=MAPBOX_DISCLOSURE_VERSION,
    )


@bp.route('/<int:race_event_id>/update', methods=['POST'])
def update_race(race_event_id: int):
    db = get_db()
    uid = current_user_id()

    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    name = _parse_str(request.form, 'name')
    event_date = _parse_date(request.form, 'event_date')
    race_format = (request.form.get('race_format') or '').strip()

    if not name:
        flash('Race name is required.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
    if not event_date:
        flash('Race date is required (YYYY-MM-DD).', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
    if race_format not in VALID_RACE_FORMATS:
        flash('Pick a race format.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
    # D-73 Phase 5.2 Bucket C (i) — block the update when the row isn't
    # Mapbox-anchored. The race-details form doesn't carry the Mapbox hidden
    # inputs (the standalone `set_locale` POST owns those); check the loaded
    # row directly so legacy un-anchored rows force the athlete through the
    # picker before any further edits land.
    if not race.get('event_locale_mapbox_id'):
        flash(
            'Pick a race location before saving other changes — use the '
            'Race location picker above.',
            'danger',
        )
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))

    new_distance_km = _parse_decimal(request.form, 'distance_km')
    new_total_elevation_gain_m = _parse_decimal(
        request.form, 'total_elevation_gain_m'
    )
    new_estimated_duration_hr = _parse_estimated_duration_hr(request.form)
    new_primary_metric = _parse_primary_metric(request.form)
    new_notes = _parse_str(request.form, 'notes')
    new_race_terrain = _parse_race_terrain(request.form)
    new_previous_attempts = _parse_previous_attempts(request.form)
    new_race_url = _parse_race_url(request.form)
    new_framework_sport = _parse_str(request.form, 'framework_sport')
    parsed_discipline_filter = _parse_discipline_id_filter(request.form)
    new_goal_outcome = _parse_goal_outcome(request.form)
    new_first_time_at_distance = _parse_first_time_at_distance(request.form)
    new_time_goal = _parse_str(request.form, 'time_goal')
    new_race_pack_weight_kg = _parse_pack_weight_kg(request.form)

    # #892 — re-map (don't wipe) the discipline narrowing when the race event
    # type (framework_sport) changes. Previously this cleared
    # `included_discipline_ids` to None, which read to the athlete as "the sport
    # edit dropped all my disciplines" (picker collapses to "Race-wide" / "not
    # included in disciplines"). Canonical discipline IDs are global, so most
    # prior picks stay valid for the new sport — keep the still-valid subset and
    # re-scope any terrain couplings the same way. Only fires when
    # framework_sport actually changed.
    prior_framework_sport = race.get('framework_sport')
    prior_discipline_filter = race.get('included_discipline_ids')
    framework_sport_will_change = prior_framework_sport != new_framework_sport
    if framework_sport_will_change:
        new_discipline_filter, dropped_disciplines = (
            _remap_discipline_filter_on_sport_change(
                db, new_framework_sport, parsed_discipline_filter,
                prior_discipline_filter,
            )
        )
        # Re-scope terrain couplings to the surviving set so a row pinned to a
        # now-dropped discipline falls back to race-wide rather than tripping
        # the #342 mismatch block on a simple sport edit.
        new_race_terrain = _rescope_terrain_to_included(
            new_race_terrain, new_discipline_filter
        )
        if dropped_disciplines:
            flash(
                'Race event type changed — disciplines that don’t apply to the '
                'new event type were dropped (' + ', '.join(dropped_disciplines) +
                '); your other picks were kept. Review the discipline list '
                'below.',
                'info',
            )
    else:
        new_discipline_filter = parsed_discipline_filter

    # Issue #342 — block terrain rows scoped to a discipline that isn't in
    # the race's included disciplines. Validate against the *effective*
    # filter (post re-map): a sport change re-scopes orphaned couplings to
    # race-wide above, so there's nothing left to block on that path.
    mismatches = _terrain_discipline_mismatches(
        new_race_terrain, new_discipline_filter
    )
    if mismatches:
        flash(_terrain_discipline_mismatch_flash(mismatches), 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))

    # D-73 Phase 5.2 walkthrough #1 — the race-details form no longer carries
    # `event_locale_id` (legacy dropdown removed); the 5 Mapbox columns are
    # owned by the standalone `/locales/update` flow on the edit page (POST
    # to `race_events.set_locale`). For the new_race path the hidden fields
    # ride through this same `update_race` POST handler when athlete picks
    # a result on first creation, but for subsequent edits the picker is
    # decoupled — there are no Mapbox hidden fields to read here.
    update_race_event(
        db, uid, race_event_id,
        name=name,
        event_date=event_date,
        race_format=race_format,
        distance_km=new_distance_km,
        total_elevation_gain_m=new_total_elevation_gain_m,
        estimated_duration_hr=new_estimated_duration_hr,
        primary_metric=new_primary_metric,
        event_locale_id=race['event_locale_id'],  # legacy FK preserved
        event_locale_name=race.get('event_locale_name'),
        event_locale_mapbox_id=race.get('event_locale_mapbox_id'),
        event_locale_place_name=race.get('event_locale_place_name'),
        event_locale_lat=race.get('event_locale_lat'),
        event_locale_lng=race.get('event_locale_lng'),
        race_url=new_race_url,
        framework_sport=new_framework_sport,
        included_discipline_ids=new_discipline_filter,
        goal_outcome=new_goal_outcome,
        first_time_at_distance=new_first_time_at_distance,
        time_goal=new_time_goal,
        race_pack_weight_kg=new_race_pack_weight_kg,
        notes=new_notes,
        race_terrain=new_race_terrain,
        previous_attempts=new_previous_attempts,
    )

    # Layer 4 cache invalidation per D-66 §9. Non-target edits leave the
    # cache untouched (race not in scope of any plan); target edits route
    # to the narrowest helper that covers the changed fields. race_terrain
    # routes to brief-only — it affects Layer 2B output, but Layer 2B is
    # recomputed on every orchestrator call (uncached at the orchestrator
    # level); the Layer 4 brief is the cache-load-bearing artifact
    # downstream.
    if race['is_target_event']:
        # estimated_duration_hr feeds Layer 2E's TargetEvent duration →
        # fueling tiers consumed by the brief + plan synthesis, so it rides
        # the periodization-grade (_NON_SINGLE_SESSION) eviction alongside
        # event_date / race_format.
        periodization_changed = (
            race['event_date'] != event_date
            or race['race_format'] != race_format
            or race['estimated_duration_hr'] != new_estimated_duration_hr
            # §H.2 goal fields feed Layer 3B's goal-viability + periodization-
            # shape selection (Compete/Podium warrant more Build/Peak; a DNF
            # history or first-time-at-distance shift viability). A change
            # flips the 3B cache key → 3B re-runs and the shape can move, so
            # evict periodization-grade alongside event_date / race_format.
            # previous_attempts (Slice 2) drives the 3B.dnf_recurrence_risk
            # HITL flag + confidence floor — same periodization grade. Hydrated
            # as a list of dicts (JSONB), compared as-is like race_terrain.
            or race.get('goal_outcome') != new_goal_outcome
            or race.get('first_time_at_distance') != new_first_time_at_distance
            or race.get('time_goal') != new_time_goal
            or race.get('race_pack_weight_kg') != new_race_pack_weight_kg
            or (race.get('previous_attempts') or []) != new_previous_attempts
        )
        # Existing race_terrain comes back from get_race_event as a list
        # of dicts (JSONB hydrated in the repo); compare as-is.
        prior_terrain = race.get('race_terrain') or []
        prior_race_url = race.get('race_url')
        # D-73 Phase 5.2 Bucket E.(b) — framework_sport override change
        # flips Layer 2A's discipline classification → wider eviction than
        # periodization (`layer2a` policy = all 4 entry points + Layer
        # 3A/3B vs periodization's `_NON_SINGLE_SESSION`). Fire it first;
        # the layer2a policy supersets both periodization + brief-only.
        framework_sport_changed = prior_framework_sport != new_framework_sport
        # D-73 Phase 5.2 Bucket E.(b)-B2 — included_discipline_ids override
        # change uses the same `layer2a` policy as framework_sport (both
        # reshape Layer 2A's discipline output). Subsumed by the
        # framework_sport branch when the override is what's driving the
        # auto-clear; only fires on its own when athlete edits the
        # discipline grid without touching framework_sport.
        discipline_filter_changed = (
            prior_discipline_filter != new_discipline_filter
        )
        brief_only_changed = (
            race['distance_km'] != new_distance_km
            or race['total_elevation_gain_m'] != new_total_elevation_gain_m
            or race['notes'] != new_notes
            or prior_terrain != new_race_terrain
            or prior_race_url != new_race_url
            or race['primary_metric'] != new_primary_metric
        )
        if framework_sport_changed:
            evict_on_target_event_framework_sport_change(db, uid)
        elif discipline_filter_changed:
            evict_on_target_event_included_discipline_ids_change(db, uid)
        elif periodization_changed:
            evict_on_target_event_periodization_change(db, uid)
        elif brief_only_changed:
            # Periodization + framework_sport / discipline-filter evictions
            # are broader than brief-only; firing brief-only on top would
            # only re-evict already-evicted race_week_brief rows.
            evict_on_target_event_brief_field_change(db, uid)

    flash('Race updated.', 'success')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


@bp.route('/<int:race_event_id>/locale/update', methods=['POST'])
def set_locale(race_event_id: int):
    """Standalone POST endpoint for picking a Mapbox-anchored race location.

    Decoupled from the main `update_race` POST so the athlete can pick a
    location on the edit page without re-submitting (and re-validating) the
    rest of the race-details form. Mirrors the inline route-locale + nested
    equipment forms already on the same page.
    """
    db = get_db()
    uid = current_user_id()
    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    locale_fields = _extract_mapbox_locale_from_form(request.form)
    # D-73 Phase 5.2 Bucket C (i) — strict Mapbox requirement. The picker JS
    # always sets mapbox_id alongside name on result-click, so empty mapbox_id
    # means either a malformed POST OR the athlete cleared the picker without
    # picking a new location. Both are rejected.
    if not locale_fields['event_locale_mapbox_id']:
        flash('Pick a race location.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))

    update_race_event_locale(db, uid, race_event_id, **locale_fields)

    # Target-row Mapbox edit → race-week brief invalidates. The legacy
    # `event_locale_id` Layer 2C eviction does NOT fire because the race
    # finish anchor doesn't dictate which athlete locale's equipment is
    # used for race-week prep (the athlete's primary training locale
    # drives Layer 2C; race finish drives brief logistics text only).
    if race['is_target_event']:
        evict_on_target_event_brief_field_change(db, uid)
    flash('Race location updated.', 'success')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


@bp.route('/locale/search', methods=['GET'])
def locale_search():
    """JSON Mapbox forward-search endpoint for the inline race-location
    picker (D-73 Phase 5.2 walkthrough #1).

    Used by both the race-edit page + the onboarding step 3c form. Both
    surfaces issue a same-origin `fetch()` from the inline picker script;
    on result-click the JS fills the 5 Mapbox hidden inputs (event_locale_*)
    in the parent form. Response shape:

        {"results": [{"text", "place_name", "mapbox_id", "lat", "lng"}, ...]}
        OR
        {"error": "..."}    (human-readable; 200 OK)
        OR
        {"error": "disclosure_required"}    (400; UI must ack first)
    """
    db = get_db()
    uid = current_user_id()
    if not _disclosure_acked(db, uid):
        return jsonify({'error': 'disclosure_required'}), 400
    q = (request.args.get('q') or '').strip()
    results, error = _run_mapbox_search(q)
    if error:
        return jsonify({'error': error})
    return jsonify({
        'results': [
            {
                'text': r.get('text', ''),
                'place_name': r.get('place_name', ''),
                'mapbox_id': r.get('mapbox_id', ''),
                'lat': r.get('lat'),
                'lng': r.get('lng'),
            }
            for r in results
        ],
    })


@bp.route('/disciplines/search', methods=['GET'])
def disciplines_search():
    """JSON endpoint that returns the discipline list for a framework_sport.

    D-73 Phase 5.2 Bucket E.(b)-B2 — backs the inline picker that rebinds
    the discipline checkbox grid + the per-row terrain discipline `<select>`
    when athlete edits the framework_sport input. Mirrors `locale_search`
    shape (auth scoped via `current_user_id`; result list keyed by
    `framework_sport` query param).

    Response: `{"framework_sport": "...", "results": [{"id", "label"}, ...]}`
    Empty results when the sport doesn't resolve in the bridge — the JS
    swaps to a "Discipline filtering not available for this sport" hint.
    """
    db = get_db()
    # Force auth — the bridge data is non-sensitive but keeping the route
    # behind the session preserves the "authed surfaces only" invariant.
    uid = current_user_id()
    framework_sport = (request.args.get('framework_sport') or '').strip()
    # #885 — a blank value is the structured select's "Same as my profile
    # sport" (inherit) option. Resolve it to the athlete's primary_sport the
    # same way the initial server render does (`_resolve_effective_framework_
    # sport`), so toggling the select back to inherit repopulates the grid
    # instead of emptying it.
    if not framework_sport:
        framework_sport = _resolve_effective_framework_sport(db, uid, None) or ''
    choices = _disciplines_for_framework_sport(db, framework_sport)
    return jsonify({
        'framework_sport': framework_sport,
        'results': choices,
    })


@bp.route('/parse-url', methods=['GET'])
def parse_url():
    """#256 — parse a pasted race URL into a best-effort form pre-fill.

    GET, mirroring locale_search/disciplines_search (no server-state mutation,
    so CSRF-free; auth-gated). The form JS pre-fills only the non-null fields,
    renders the distance/event chooser, and routes location_text into the
    Mapbox picker. Always returns 200; `{ok: False, hint}` on a failed fetch so
    manual entry is never blocked. Response:

        {"ok": true, "fields": {...}, "distance_options": [...],
         "terrain": {"entries": [...], "pct_basis": "..."}|null,
         "confidence": "...", "summary": "..."}
        OR {"ok": false, "hint": "..."}
    """
    db = get_db()
    _ = current_user_id()
    url = (request.args.get('url') or '').strip()
    if not url:
        return jsonify({'ok': False, 'hint': 'Paste a race URL first.'})
    return jsonify(run_url_parse(db, url))


@bp.route('/infer-terrain', methods=['GET'])
def infer_terrain_suggestion():
    """#592 — the subordinate location->terrain fallback + climate-normals
    nudge, fired client-side once the athlete confirms a location and the
    terrain editor is still empty. GET, auth-gated, best-effort. Response:

        {"ok": true, "terrain": {"entries":[...],"confidence":"...",
         "summary":"..."}|null, "conditions": "..."|null}
    """
    db = get_db()
    _ = current_user_id()

    def _s(name):
        return (request.args.get(name) or '').strip() or None

    def _num(name):
        v = _s(name)
        if v is None:
            return None
        try:
            return float(v)
        except ValueError:
            return None

    return jsonify(run_terrain_inference(
        db,
        lat=_num('lat'), lng=_num('lng'), place_name=_s('place_name'),
        event_date=_coerce_event_date(_s('event_date')),
        race_name=_s('name'), distance_km=_num('distance_km'),
        elevation_gain_m=_num('elevation_gain_m'), race_format=_s('race_format'),
        framework_sport=_s('framework_sport'), notes=_s('notes'), race_url=_s('race_url'),
    ))


@bp.route('/locale/acknowledge', methods=['POST'])
def acknowledge_mapbox_disclosure():
    """Records the Mapbox geocoding consent + redirects back to the
    referrer race page. Shares `disclosure_acknowledgments` rows with
    `/locales/new`; an ack from either surface unblocks both.
    """
    db = get_db()
    uid = current_user_id()
    _record_disclosure_ack(db, uid)
    return_to = (request.form.get('return_to') or '').strip()
    if return_to and return_to.startswith('/profile/race-events/'):
        return redirect(return_to)
    if return_to.startswith('/onboarding/'):
        return redirect(return_to)
    return _tab_redirect()


@bp.route('/<int:race_event_id>/delete', methods=['POST'])
def delete_race(race_event_id: int):
    db = get_db()
    uid = current_user_id()

    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    was_target = bool(race['is_target_event'])
    delete_race_event(db, uid, race_event_id)
    if was_target:
        evict_on_target_event_periodization_change(db, uid)
    flash(f'Race "{race["name"]}" deleted.', 'info')
    return _tab_redirect()


@bp.route('/<int:race_event_id>/set-target', methods=['POST'])
def set_target(race_event_id: int):
    """Atomic flip — clears any other target row for the user, then
    marks this one. The partial UNIQUE index `race_events_user_target_uidx`
    guarantees only one TRUE row per athlete.
    """
    db = get_db()
    uid = current_user_id()

    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    set_target_event(db, uid, race_event_id)
    # Target flag flipped (UNSET old target + SET this row); fires
    # periodization-grade eviction per D-66 §9.
    evict_on_target_event_periodization_change(db, uid)
    flash(
        f'"{race["name"]}" is now your target race. '
        'A plan refresh will trigger on the next morning sync.',
        'success',
    )
    return _tab_redirect()


# ─── Route-locale CRUD ──────────────────────────────────────────────────────


@bp.route('/<int:race_event_id>/locales/add', methods=['POST'])
def add_locale(race_event_id: int):
    db = get_db()
    uid = current_user_id()
    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    role = (request.form.get('role') or '').strip()
    sequence_idx = _parse_int(request.form, 'sequence_idx')
    name = _parse_str(request.form, 'name')

    if not name:
        flash('Locale name is required.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
    if role not in VALID_ROUTE_LOCALE_ROLES:
        flash('Pick a route-locale role.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
    if sequence_idx is None or sequence_idx < 1:
        flash('Sequence number must be 1 or greater.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))

    try:
        add_route_locale(
            db, race_event_id,
            role=role,
            sequence_idx=sequence_idx,
            name=name,
            mile_marker=_parse_decimal(request.form, 'mile_marker'),
            lat=_parse_decimal(request.form, 'lat'),
            lng=_parse_decimal(request.form, 'lng'),
            mapbox_id=_parse_str(request.form, 'mapbox_id'),
            notes=_parse_str(request.form, 'notes'),
        )
        if race['is_target_event']:
            evict_on_target_event_brief_field_change(db, uid)
        flash(f'Route locale "{name}" added.', 'success')
    except Exception as e:
        # Most likely: UNIQUE (race_event_id, sequence_idx) violation on
        # collision with an existing row. Surface to the athlete so they
        # can pick a different sequence number rather than 500.
        flash(f'Could not add route locale: {e}', 'danger')

    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


@bp.route('/<int:race_event_id>/locales/<int:route_locale_id>/update', methods=['POST'])
def update_locale(race_event_id: int, route_locale_id: int):
    db = get_db()
    uid = current_user_id()
    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    role = (request.form.get('role') or '').strip()
    sequence_idx = _parse_int(request.form, 'sequence_idx')
    name = _parse_str(request.form, 'name')

    if not name:
        flash('Locale name is required.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
    if role not in VALID_ROUTE_LOCALE_ROLES:
        flash('Pick a route-locale role.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
    if sequence_idx is None or sequence_idx < 1:
        flash('Sequence number must be 1 or greater.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))

    try:
        update_route_locale(
            db, race_event_id, route_locale_id,
            role=role,
            sequence_idx=sequence_idx,
            name=name,
            mile_marker=_parse_decimal(request.form, 'mile_marker'),
            lat=_parse_decimal(request.form, 'lat'),
            lng=_parse_decimal(request.form, 'lng'),
            mapbox_id=_parse_str(request.form, 'mapbox_id'),
            notes=_parse_str(request.form, 'notes'),
        )
        if race['is_target_event']:
            evict_on_target_event_brief_field_change(db, uid)
        flash('Route locale updated.', 'success')
    except Exception as e:
        flash(f'Could not update route locale: {e}', 'danger')

    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


@bp.route('/<int:race_event_id>/locales/<int:route_locale_id>/delete', methods=['POST'])
def delete_locale(race_event_id: int, route_locale_id: int):
    db = get_db()
    uid = current_user_id()
    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    delete_route_locale(db, race_event_id, route_locale_id)
    if race['is_target_event']:
        evict_on_target_event_brief_field_change(db, uid)
    flash('Route locale deleted.', 'info')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


# ─── Route-locale equipment CRUD ────────────────────────────────────────────


@bp.route('/<int:race_event_id>/locales/<int:route_locale_id>/equipment/add', methods=['POST'])
def add_equipment(race_event_id: int, route_locale_id: int):
    db = get_db()
    uid = current_user_id()
    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    equipment_name = _parse_str(request.form, 'equipment_name')
    if not equipment_name:
        flash('Equipment name is required.', 'danger')
        return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))

    add_route_locale_equipment(
        db, route_locale_id,
        equipment_name=equipment_name,
        quantity_text=_parse_str(request.form, 'quantity_text'),
        notes=_parse_str(request.form, 'notes'),
    )
    if race['is_target_event']:
        evict_on_target_event_brief_field_change(db, uid)
    flash(f'Equipment "{equipment_name}" added.', 'success')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


@bp.route(
    '/<int:race_event_id>/locales/<int:route_locale_id>/equipment/<int:equipment_id>/delete',
    methods=['POST'],
)
def delete_equipment(race_event_id: int, route_locale_id: int, equipment_id: int):
    db = get_db()
    uid = current_user_id()
    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    delete_route_locale_equipment(db, route_locale_id, equipment_id)
    if race['is_target_event']:
        evict_on_target_event_brief_field_change(db, uid)
    flash('Equipment removed.', 'info')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
