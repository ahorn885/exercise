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

from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from database import get_db
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
    update_route_locale,
)
from routes.auth import current_user_id


bp = Blueprint('race_events', __name__, url_prefix='/profile/race-events')


def _athlete_locale_choices(db, uid: int) -> list[dict]:
    """Return `{id, label}` dicts for every locale_profiles row the
    athlete owns. Used to populate the event_locale_id dropdown on the
    race edit form. `id` is the D-66 surrogate `BIGSERIAL` added to
    locale_profiles alongside the composite PK; `label` falls back to
    the slug when the athlete never set a `locale_name`.
    """
    cur = db.execute(
        'SELECT id, locale, locale_name FROM locale_profiles '
        'WHERE user_id = ? '
        'ORDER BY COALESCE(locale_name, locale)',
        (uid,),
    )
    return [
        {'id': int(r['id']), 'label': (r['locale_name'] or r['locale'])}
        for r in cur.fetchall()
    ]


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
            event_locale_id=_parse_int(request.form, 'event_locale_id'),
            notes=_parse_str(request.form, 'notes'),
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

    locale_choices = _athlete_locale_choices(db, uid)
    return render_template(
        'profile/race_event_edit.html',
        race=None,
        race_locales=[],
        equipment_by_locale={},
        locale_choices=locale_choices,
        race_formats=VALID_RACE_FORMATS,
        route_locale_roles=VALID_ROUTE_LOCALE_ROLES,
        is_new=True,
    )


@bp.route('/<int:race_event_id>/edit', methods=['GET'])
def edit_race(race_event_id: int):
    """Render the per-race edit page — race details form + route-locale
    list with per-row inline forms + nested equipment add/delete.
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
    locale_choices = _athlete_locale_choices(db, uid)
    return render_template(
        'profile/race_event_edit.html',
        race=race,
        race_locales=race_locales,
        equipment_by_locale=equipment_by_locale,
        locale_choices=locale_choices,
        race_formats=VALID_RACE_FORMATS,
        route_locale_roles=VALID_ROUTE_LOCALE_ROLES,
        is_new=False,
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

    update_race_event(
        db, uid, race_event_id,
        name=name,
        event_date=event_date,
        race_format=race_format,
        distance_km=_parse_decimal(request.form, 'distance_km'),
        total_elevation_gain_m=_parse_decimal(
            request.form, 'total_elevation_gain_m'
        ),
        race_rules_summary=_parse_str(request.form, 'race_rules_summary'),
        mandatory_gear_text=_parse_str(request.form, 'mandatory_gear_text'),
        event_locale_id=_parse_int(request.form, 'event_locale_id'),
        notes=_parse_str(request.form, 'notes'),
    )
    flash('Race updated.', 'success')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


@bp.route('/<int:race_event_id>/delete', methods=['POST'])
def delete_race(race_event_id: int):
    db = get_db()
    uid = current_user_id()

    race = get_race_event(db, uid, race_event_id)
    if not race:
        abort(404)

    delete_race_event(db, uid, race_event_id)
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
    if not get_race_event(db, uid, race_event_id):
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
    if not get_race_event(db, uid, race_event_id):
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
        flash('Route locale updated.', 'success')
    except Exception as e:
        flash(f'Could not update route locale: {e}', 'danger')

    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


@bp.route('/<int:race_event_id>/locales/<int:route_locale_id>/delete', methods=['POST'])
def delete_locale(race_event_id: int, route_locale_id: int):
    db = get_db()
    uid = current_user_id()
    if not get_race_event(db, uid, race_event_id):
        abort(404)

    delete_route_locale(db, race_event_id, route_locale_id)
    flash('Route locale deleted.', 'info')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


# ─── Route-locale equipment CRUD ────────────────────────────────────────────


@bp.route('/<int:race_event_id>/locales/<int:route_locale_id>/equipment/add', methods=['POST'])
def add_equipment(race_event_id: int, route_locale_id: int):
    db = get_db()
    uid = current_user_id()
    if not get_race_event(db, uid, race_event_id):
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
    flash(f'Equipment "{equipment_name}" added.', 'success')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))


@bp.route(
    '/<int:race_event_id>/locales/<int:route_locale_id>/equipment/<int:equipment_id>/delete',
    methods=['POST'],
)
def delete_equipment(race_event_id: int, route_locale_id: int, equipment_id: int):
    db = get_db()
    uid = current_user_id()
    if not get_race_event(db, uid, race_event_id):
        abort(404)

    delete_route_locale_equipment(db, route_locale_id, equipment_id)
    flash('Equipment removed.', 'info')
    return redirect(url_for('race_events.edit_race', race_event_id=race_event_id))
