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


def _resolve_effective_framework_sport(db, user_id: int, race: dict | None) -> str | None:
    """Resolve the framework_sport to use for initial discipline-grid render.

    Mirrors the orchestrator's resolution order (`layer4/orchestrator.py`
    `_upstream_full_cone`): race-row override wins; otherwise fall back to
    athlete-profile `primary_sport`. Returns None when neither is set —
    the template then renders an empty discipline grid with helper copy
    pointing the athlete at the framework_sport field.
    """
    race_override = (race or {}).get('framework_sport') if race else None
    if race_override:
        return race_override
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
        # D-73 Phase 5.2 Bucket C (i) — race location is required. Pydantic
        # backstops this at RaceEventPayload construction; the flash here is
        # the athlete-facing UX.
        if not locale_fields['event_locale_mapbox_id']:
            flash('Pick a race location before saving.', 'danger')
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
            race_rules_summary=_parse_str(request.form, 'race_rules_summary'),
            mandatory_gear_text=_parse_str(request.form, 'mandatory_gear_text'),
            notes=_parse_str(request.form, 'notes'),
            race_terrain=_parse_race_terrain(request.form),
            previous_attempts=_parse_previous_attempts(request.form),
            race_url=_parse_race_url(request.form),
            framework_sport=_parse_str(request.form, 'framework_sport'),
            included_discipline_ids=_parse_discipline_id_filter(request.form),
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
    discipline_choices = _disciplines_for_framework_sport(db, initial_framework_sport)
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
        discipline_choices=discipline_choices,
        initial_framework_sport=initial_framework_sport,
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
    discipline_choices = _disciplines_for_framework_sport(db, initial_framework_sport)
    return render_template(
        'profile/race_event_edit.html',
        race=race,
        race_locales=race_locales,
        equipment_by_locale=equipment_by_locale,
        terrain_choices=terrain_choices,
        discipline_choices=discipline_choices,
        initial_framework_sport=initial_framework_sport,
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
    new_race_rules_summary = _parse_str(request.form, 'race_rules_summary')
    new_mandatory_gear_text = _parse_str(request.form, 'mandatory_gear_text')
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

    # D-73 Phase 5.2 Bucket E.(b)-B2 — auto-clear on framework_sport
    # change. Previously-selected discipline IDs reference the old sport's
    # bridge set and are invalid for the new sport; silently dropping them
    # at Layer 2A would create a UI/runtime mismatch (form shows old
    # selection; classifier ignores). Clear to None + flash a hint so the
    # athlete knows to re-pick. Only fires when framework_sport actually
    # changed AND there was a prior non-NULL selection (no flash on
    # already-empty rows).
    prior_framework_sport = race.get('framework_sport')
    prior_discipline_filter = race.get('included_discipline_ids')
    framework_sport_will_change = prior_framework_sport != new_framework_sport
    if framework_sport_will_change and prior_discipline_filter:
        new_discipline_filter = None
        flash(
            'Sport override changed — your discipline picks were cleared. '
            'Re-select them for the new sport.',
            'info',
        )
    else:
        new_discipline_filter = parsed_discipline_filter

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
            or race['race_rules_summary'] != new_race_rules_summary
            or race['mandatory_gear_text'] != new_mandatory_gear_text
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
    _ = current_user_id()
    framework_sport = (request.args.get('framework_sport') or '').strip()
    choices = _disciplines_for_framework_sport(db, framework_sport)
    return jsonify({
        'framework_sport': framework_sport,
        'results': choices,
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
