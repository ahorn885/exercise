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
from database import get_db
from race_events_invalidation import (
    evict_on_target_event_brief_field_change,
    evict_on_target_event_framework_sport_change,
    evict_on_target_event_periodization_change,
)
from race_events_repo import (
    VALID_RACE_FORMATS,
    VALID_ROUTE_LOCALE_ROLES,
    add_route_locale,
    add_route_locale_equipment,
    create_race_event,
    delete_race_event,
    delete_route_locale,
    delete_route_locale_equipment,
    get_race_event,
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


bp = Blueprint('race_events', __name__, url_prefix='/profile/race-events')


_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")


def _terrain_choices(db) -> list[dict]:
    """Return `{id, label}` dicts for every active `layer0.terrain_types` row.

    Used by the race-event edit template to populate the per-row terrain
    dropdown. `id` is the canonical TRN-xxx slug; `label` is the
    `canonical_name`. ORDER BY terrain_id for stable rendering; ~16 rows so
    no caching. Matches the `_athlete_locale_choices` precedent for
    request-time vocabulary lookups.
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
        'SELECT terrain_id, canonical_name FROM layer0.terrain_types '
        'WHERE superseded_at IS NULL AND terrain_id IS NOT NULL '
        'ORDER BY terrain_id'
    )
    return [
        {'id': r['terrain_id'], 'label': r['canonical_name']}
        for r in cur.fetchall()
    ]


def _parse_race_terrain(form) -> list[dict]:
    """Parse the repeating `race_terrain[N][...]` form fields into a list
    of `{"terrain_id": str, "pct_of_race": float}` dicts.

    Empty rows (no terrain_id selected OR no percent entered) are silently
    dropped — athletes adding a row then leaving it blank shouldn't fail
    the save. Invalid terrain_id (not matching TRN-\\d{3}) or invalid
    percent (non-numeric / out of [0, 100]) drops the row and skips it.
    """
    out: list[dict] = []
    # Discover the row indices used by the template (form names like
    # `race_terrain[0][terrain_id]`, `race_terrain[1][pct_of_race]`).
    indices: set[int] = set()
    for key in form.keys():
        m = re.match(r"^race_terrain\[(\d+)\]\[(terrain_id|pct_of_race)\]$", key)
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
        out.append({'terrain_id': terrain_id, 'pct_of_race': pct})
    return out


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


def _tab_redirect():
    return redirect(url_for('profile.edit', tab='race-events'))


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
        race_event_id = create_race_event(
            db, uid,
            name=name,
            event_date=event_date,
            race_format=race_format,
            distance_km=_parse_decimal(request.form, 'distance_km'),
            total_elevation_gain_m=_parse_decimal(
                request.form, 'total_elevation_gain_m'
            ),
            race_rules_summary=_parse_str(request.form, 'race_rules_summary'),
            mandatory_gear_text=_parse_str(request.form, 'mandatory_gear_text'),
            notes=_parse_str(request.form, 'notes'),
            race_terrain=_parse_race_terrain(request.form),
            aid_stations=_parse_int(request.form, 'aid_stations'),
            race_url=_parse_race_url(request.form),
            framework_sport=_parse_str(request.form, 'framework_sport'),
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
    # D-73 Phase 5.2 walkthrough #1 — Mapbox-anchored race-location picker.
    # The search box + result list are rendered + driven by the inline
    # `<script nonce="..."` block in `templates/_race_locale_picker.html`
    # which fetches from the JSON `locale_search` endpoint and fills the
    # 5 hidden inputs on result-click. This sidesteps the form-state
    # preservation problem the GET round-trip would have introduced
    # (mandatory_gear_text + race_rules_summary can be multi-KB and the
    # URL line limit is 8KB).
    return render_template(
        'profile/race_event_edit.html',
        race=None,
        race_locales=[],
        equipment_by_locale={},
        terrain_choices=terrain_choices,
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
    return render_template(
        'profile/race_event_edit.html',
        race=race,
        race_locales=race_locales,
        equipment_by_locale=equipment_by_locale,
        terrain_choices=terrain_choices,
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

    new_distance_km = _parse_decimal(request.form, 'distance_km')
    new_total_elevation_gain_m = _parse_decimal(
        request.form, 'total_elevation_gain_m'
    )
    new_race_rules_summary = _parse_str(request.form, 'race_rules_summary')
    new_mandatory_gear_text = _parse_str(request.form, 'mandatory_gear_text')
    new_notes = _parse_str(request.form, 'notes')
    new_race_terrain = _parse_race_terrain(request.form)
    new_aid_stations = _parse_int(request.form, 'aid_stations')
    new_race_url = _parse_race_url(request.form)
    new_framework_sport = _parse_str(request.form, 'framework_sport')

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
        race_rules_summary=new_race_rules_summary,
        mandatory_gear_text=new_mandatory_gear_text,
        event_locale_id=race['event_locale_id'],  # legacy FK preserved
        event_locale_name=race.get('event_locale_name'),
        event_locale_mapbox_id=race.get('event_locale_mapbox_id'),
        event_locale_place_name=race.get('event_locale_place_name'),
        event_locale_lat=race.get('event_locale_lat'),
        event_locale_lng=race.get('event_locale_lng'),
        race_url=new_race_url,
        framework_sport=new_framework_sport,
        notes=new_notes,
        race_terrain=new_race_terrain,
        aid_stations=new_aid_stations,
    )

    # Layer 4 cache invalidation per D-66 §9. Non-target edits leave the
    # cache untouched (race not in scope of any plan); target edits route
    # to the narrowest helper that covers the changed fields. race_terrain
    # + aid_stations route to brief-only — they affect Layer 2B + Layer 2E
    # outputs, but both layers are recomputed on every orchestrator call
    # (uncached at the orchestrator level); the Layer 4 brief is the
    # cache-load-bearing artifact downstream of both.
    if race['is_target_event']:
        periodization_changed = (
            race['event_date'] != event_date
            or race['race_format'] != race_format
        )
        # Existing race_terrain comes back from get_race_event as a list
        # of dicts (JSONB hydrated in the repo); compare as-is.
        prior_terrain = race.get('race_terrain') or []
        prior_aid = race.get('aid_stations')
        prior_race_url = race.get('race_url')
        prior_framework_sport = race.get('framework_sport')
        # D-73 Phase 5.2 Bucket E.(b) — framework_sport override change
        # flips Layer 2A's discipline classification → wider eviction than
        # periodization (`layer2a` policy = all 4 entry points + Layer
        # 3A/3B vs periodization's `_NON_SINGLE_SESSION`). Fire it first;
        # the layer2a policy supersets both periodization + brief-only.
        framework_sport_changed = prior_framework_sport != new_framework_sport
        brief_only_changed = (
            race['distance_km'] != new_distance_km
            or race['total_elevation_gain_m'] != new_total_elevation_gain_m
            or race['race_rules_summary'] != new_race_rules_summary
            or race['mandatory_gear_text'] != new_mandatory_gear_text
            or race['notes'] != new_notes
            or prior_terrain != new_race_terrain
            or prior_aid != new_aid_stations
            or prior_race_url != new_race_url
        )
        if framework_sport_changed:
            evict_on_target_event_framework_sport_change(db, uid)
        elif periodization_changed:
            evict_on_target_event_periodization_change(db, uid)
        elif brief_only_changed:
            # Periodization + framework_sport evictions are broader than
            # brief-only; firing brief-only on top would only re-evict
            # already-evicted race_week_brief rows.
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
    if not locale_fields['event_locale_name'] and not locale_fields['event_locale_mapbox_id']:
        flash('Place lookup result was malformed; try again.', 'danger')
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
