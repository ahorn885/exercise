"""Profile blueprint (Session 4).

Single page at `/profile` with three sections:
  - Athlete profile — DOB, sex, height, target event, weekly hours, etc.
  - Coach memory — list of `coaching_preferences` rows for the current
    user, each with provenance (which feedback_log row produced it),
    delete buttons, and a manual-add form.
  - Account — username display + change-password form.

All writes are scoped to the current user. Coach memory rows from the
auto-capture pipeline (Session 0) are surfaced verbatim with their
`source` and `captured_at` from the originating `feedback_log` row.
"""

from datetime import datetime

import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from database import get_db
from routes.auth import (
    current_user_id, _hash_password, _check_password, _password_strength_errors,
    generate_api_token,
)
from athlete import (
    PROFILE_FIELDS, PREFILL_ELIGIBLE_FIELDS,
    DOUBLES_FEASIBLE_CHOICES,
    get_athlete_profile, upsert_athlete_profile,
    get_daily_availability_windows, upsert_daily_availability_windows,
)
from units import (
    UNIT_PREFERENCE_CHOICES, DEFAULT_UNIT_PREFERENCE,
    normalize_unit_preference, entered_weight_to_kg, display_weight,
    weight_unit_label,
)
from athlete_skill_toggles_repo import (
    evict_layer1_on_skill_toggle_change,
    get_athlete_skill_toggles,
    load_active_skill_capability_toggle_vocab,
    parse_skill_form,
    upsert_athlete_skill_toggles,
)
from race_events_repo import list_athlete_race_events
from routes import provider_auth as pa


bp = Blueprint('profile', __name__, url_prefix='/profile')


# Categories shown in the manual-add coaching_preferences dropdown. Mirrors
# the categories the auto-extractor (coaching.py:_FEEDBACK_EXTRACT_PROMPT)
# emits, so manually-added prefs slot in alongside auto-captured ones.
PREFERENCE_CATEGORIES = (
    'avoid_exercise', 'prefer_exercise',
    'nutrition', 'training', 'scheduling', 'equipment', 'general',
)

# Providers surfaced on the Account Config 1 Connections tab. Order is the
# rendering order; entries here must have a `<slug>.oauth_start` Flask
# endpoint (the connect button links to it via url_for) and ideally a
# matching disconnect path through `provider_auth.disconnect`. New
# providers slot in as their OAuth blueprints land (Wahoo / Strava / Whoop
# / TrainingPeaks / Zwift / RWGPS — RWGPS already wired but the OAuth
# start endpoint name may differ; verify before adding).
CONNECTION_PROVIDERS = (
    ('coros', 'COROS', 'coros.oauth_start'),
    ('polar', 'Polar', 'polar.oauth_start'),
)

# pa.status → (badge label, Bootstrap badge class). Mirrors v5 §Account
# Config 1 "Connection Status" enum (Connected / Disconnected / Auth
# Error / Sync Paused) plus the pending_backfill mid-state PR3 introduced
# for Polar's two-phase OAuth+registration flow.
_STATUS_DISPLAY = {
    pa.STATUS_ACTIVE: ('Connected', 'bg-success'),
    pa.STATUS_REVOKED: ('Disconnected', 'bg-secondary'),
    pa.STATUS_ERROR: ('Auth error', 'bg-danger'),
    pa.STATUS_PENDING_BACKFILL: ('Setup in progress', 'bg-warning text-dark'),
    pa.STATUS_MIGRATING: ('Migrating', 'bg-info text-dark'),
}


def load_connections(db, uid, return_to=None):
    """Build provider-connection display data. Returns a list of dicts in
    `CONNECTION_PROVIDERS` order, one per known provider. Each entry
    carries the on-disk `provider_auth` row (or None) plus pre-computed
    display fields (status label, badge class, is_connected flag,
    connect_url) the templates render.

    `return_to` is the relative path the provider's OAuth callback
    redirects to with `?<provider>_connected=1` / `?<provider>_oauth_error=…`
    appended. Defaults to `/profile?tab=connections` so the existing
    Connections-tab callers (PR4) keep working unchanged; the onboarding
    Step-2 connect screen (PR5) passes `/onboarding/connect` so the
    post-OAuth bounce lands the athlete back in the onboarding flow.
    """
    rows = db.execute(
        'SELECT provider, status, registered_at, scopes, '
        'updated_at, created_at, provider_user_id '
        'FROM provider_auth WHERE user_id = ?',
        (uid,),
    ).fetchall()
    by_provider = {r['provider']: dict(r) for r in rows}
    if return_to is None:
        return_to = url_for('profile.edit') + '?tab=connections'
    out = []
    for slug, label, endpoint in CONNECTION_PROVIDERS:
        row = by_provider.get(slug)
        status = (row or {}).get('status')
        display_label, badge_class = _STATUS_DISPLAY.get(
            status, ('Not connected', 'bg-light text-dark border')
        )
        out.append({
            'slug': slug,
            'label': label,
            'row': row,
            'status': status,
            'status_label': display_label,
            'badge_class': badge_class,
            'is_connected': status == pa.STATUS_ACTIVE,
            'connect_url': url_for(endpoint, return_to=return_to),
        })
    return out


def _record_self_report_provenance(db, uid, field_values):
    """Write `athlete_profile_field_provenance` rows for prefill-eligible
    fields the athlete just saved via the profile form.

    Source-flip rules per v5 §A.2.3:

      - Prior `source` starts with `'provider_'` → flip to `'manual_override'`
        (the athlete is overriding a provider-prefilled value by typing
        their own).
      - Prior `source = 'manual_override'` → stays `'manual_override'`
        (subsequent edits of an already-overridden value).
      - Prior row missing OR `source = 'self_report'` → write `'self_report'`
        (never-prefilled field, athlete is filling in or correcting).

    PG-only per `Athlete_Data_Integration_Spec_v4` §2.5 (SQLite frozen).
    Local-dev SQLite saves skip the provenance write.

    `field_values` is a dict keyed by `athlete_profile.field_name`. None
    values are skipped — clearing a field doesn't write a provenance row
    here (see `routes/onboarding.py:keep_current` for the explicit
    "athlete reviewed and rejected the provider candidate" path).

    Field-name validation is registry-driven: only names in
    `PREFILL_ELIGIBLE_FIELDS` produce writes. Unknown keys are silently
    dropped (the table's `field_name` column is free-text TEXT today;
    this filter is the enforcement layer until a CHECK constraint ships).
    """
    prior_rows = db.execute(
        'SELECT field_name, source '
        'FROM athlete_profile_field_provenance WHERE user_id = ?',
        (uid,),
    ).fetchall()
    prior_by_field = {r['field_name']: r['source'] for r in prior_rows}
    for field_name, value in field_values.items():
        if value is None:
            continue
        if field_name not in PREFILL_ELIGIBLE_FIELDS:
            continue
        prior_source = prior_by_field.get(field_name)
        if prior_source and prior_source.startswith('provider_'):
            new_source = 'manual_override'
        elif prior_source == 'manual_override':
            new_source = 'manual_override'
        else:
            new_source = 'self_report'
        db.execute(
            'INSERT INTO athlete_profile_field_provenance '
            '(user_id, field_name, source) '
            'VALUES (?, ?, ?) '
            'ON CONFLICT (user_id, field_name) DO UPDATE SET '
            '    source = EXCLUDED.source, '
            '    last_updated_at = NOW()',
            (uid, field_name, new_source),
        )


def _load_memory(db, user_id):
    """Return the coach-memory rows for the current user with provenance.

    Each preference row joins LEFT to feedback_log via source_feedback_id
    so manually-added prefs (no source) render with empty provenance.
    """
    rows = db.execute(
        '''SELECT cp.id, cp.category, cp.content, cp.permanent, cp.created_at,
                  cp.source_feedback_id,
                  fl.source as fb_source, fl.captured_at as fb_captured_at,
                  fl.raw_content as fb_raw_content
           FROM coaching_preferences cp
           LEFT JOIN feedback_log fl ON fl.id = cp.source_feedback_id
           WHERE cp.user_id = ?
           ORDER BY cp.created_at DESC''',
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


@bp.route('/', methods=['GET', 'POST'])
def edit():
    db = get_db()
    uid = current_user_id()

    if request.method == 'POST':
        # Profile section — POST body carries the profile fields. Empty
        # strings are coerced to None so we don't store '' for unset.
        f = request.form

        def _str(key):
            v = (f.get(key) or '').strip()
            return v or None

        def _num(key, cast=float):
            v = (f.get(key) or '').strip()
            if not v:
                return None
            try:
                return cast(v)
            except (ValueError, TypeError):
                return None

        # #469 — body weight is entered in the athlete's chosen display unit
        # but stored canonically in kg. The form posts BOTH the in-effect
        # preference at render time (hidden `body_weight_input_unit`) AND
        # the newly-chosen preference (the dropdown). We convert the entered
        # body weight from the RENDER-time unit — if the user toggled the
        # dropdown without retyping the weight, the displayed number is still
        # in the render-time unit, so reading it as the new unit would store
        # the wrong value (the classic "161.8 lb saved as 161.8 kg" bug).
        submitted_unit_pref = normalize_unit_preference(_str('unit_preference'))
        input_unit_pref = normalize_unit_preference(
            _str('body_weight_input_unit')
        ) or submitted_unit_pref
        entered_body_weight = _num('body_weight')
        body_weight_kg = entered_weight_to_kg(entered_body_weight, input_unit_pref)

        prefill_values = {
            'body_weight_kg': body_weight_kg,
            'hrmax_bpm': _num('hrmax_bpm', cast=int),
            'lactate_threshold_hr_bpm': _num('lactate_threshold_hr_bpm', cast=int),
            'vo2max': _num('vo2max'),
            'cycling_ftp_w': _num('cycling_ftp_w', cast=int),
        }
        upsert_athlete_profile(
            db, uid,
            date_of_birth=_str('date_of_birth'),
            sex=_str('sex'),
            height_cm=_num('height_cm'),
            primary_sport=_str('primary_sport'),
            weekly_hours_target=_num('weekly_hours_target'),
            notes=_str('notes'),
            unit_preference=submitted_unit_pref,
            **prefill_values,
        )
        _record_self_report_provenance(db, uid, prefill_values)
        db.commit()
        flash('Profile saved.', 'success')
        return redirect(url_for('profile.edit'))

    profile = get_athlete_profile(db, uid) or {}
    memory = _load_memory(db, uid)

    days = get_daily_availability_windows(db, uid)
    doubles = (profile.get('doubles_feasible') or 'no').lower()
    if doubles not in DOUBLES_FEASIBLE_CHOICES:
        doubles = 'no'

    user_row = db.execute(
        'SELECT username, display_name, email, last_login FROM users WHERE id=?', (uid,)
    ).fetchone()
    api_tokens = db.execute(
        'SELECT id, name, created_at, last_used_at, revoked_at, expires_at '
        'FROM api_tokens WHERE user_id=? ORDER BY created_at DESC',
        (uid,)
    ).fetchall()
    # New-token plaintext is shown exactly once after creation, then cleared
    # from the session. Storing in flask session means a successful create
    # redirects to GET, then the GET handler reads-and-clears.
    from flask import session as flask_session
    new_token_plaintext = flask_session.pop('new_api_token_plaintext', None)
    connections = load_connections(db, uid)
    race_events = list_athlete_race_events(db, uid)
    # Post-OAuth-callback flags. `<provider>.oauth_callback` redirects to
    # `return_to?<slug>_connected=1` on success (or `?<slug>_oauth_error=...`
    # / `?<slug>_register_error=1` on failure). Surface the connected
    # label so the template can render the passive prompt without
    # re-implementing the slug → label mapping. Per v5 spec §A.2.5 this
    # is the post-connect re-onboarding prompt surface; the full
    # per-field prefill UX lands in D2.
    just_connected_label = None
    just_connected_slug = None
    for slug, label, _endpoint in CONNECTION_PROVIDERS:
        if request.args.get(f'{slug}_connected') == '1':
            just_connected_label = label
            just_connected_slug = slug
            break
    # Best-effort surface for OAuth failures. Same shape — the callback
    # writes `?<slug>_oauth_error=<reason>` or `?<slug>_register_error=1`.
    oauth_error_label = None
    for slug, label, _endpoint in CONNECTION_PROVIDERS:
        if request.args.get(f'{slug}_oauth_error') or request.args.get(f'{slug}_register_error'):
            oauth_error_label = label
            break
    # Bucket C (l) capture-surface follow-on (2026-05-24) — Skills tab.
    # Loads the canonical vocab + athlete state for the same shared
    # `_skills_form.html` partial used by /onboarding/skills.
    skill_toggle_defs = load_active_skill_capability_toggle_vocab(db)
    skill_toggle_states = get_athlete_skill_toggles(db, uid)

    # #469 — body weight is stored canonical kg; render it in the athlete's
    # chosen display unit so the form field round-trips cleanly. `profile` is
    # mutated in place because it's the dict the template reads.
    unit_pref = normalize_unit_preference(profile.get('unit_preference'))
    profile['unit_preference'] = unit_pref
    profile['body_weight_display'] = display_weight(profile.get('body_weight_kg'), unit_pref)
    profile['weight_unit_label'] = weight_unit_label(unit_pref)

    from datetime import datetime as _dt
    return render_template(
        'profile/edit.html',
        profile=profile,
        unit_preference_choices=UNIT_PREFERENCE_CHOICES,
        memory=memory,
        preference_categories=PREFERENCE_CATEGORIES,
        user_row=dict(user_row) if user_row else {},
        api_tokens=[dict(t) for t in api_tokens],
        new_api_token=new_token_plaintext,
        connections=connections,
        race_events=race_events,
        just_connected_label=just_connected_label,
        just_connected_slug=just_connected_slug,
        oauth_error_label=oauth_error_label,
        active_tab=request.args.get('tab'),
        days=days,
        doubles_feasible=doubles,
        doubles_choices=DOUBLES_FEASIBLE_CHOICES,
        skill_toggle_defs=skill_toggle_defs,
        skill_toggle_states=skill_toggle_states,
        # Used by the template to render an "Expired" badge without
        # round-tripping the timestamp through a Jinja-only comparison.
        now_iso=_dt.utcnow().isoformat(timespec='seconds'),
    )


@bp.route('/schedule', methods=['POST'])
def save_schedule():
    """Persist the v5 §G schedule form when submitted from the
    `/profile?tab=schedule` surface. Identical write semantics to
    `onboarding.schedule_save` — per-day windows replace existing rows,
    athlete_profile carries the `doubles_feasible` toggle — differing
    only in the redirect target (stays on the profile tab instead of
    forwarding to the §A profile entry).

    `_parse_schedule_form` is lazy-imported from `routes.onboarding`
    because `onboarding` already imports from this module (load_connections
    + CONNECTION_PROVIDERS); the cycle is broken at function-call time.
    """
    from routes.onboarding import _parse_schedule_form

    db = get_db()
    uid = current_user_id()

    windows, profile_updates, errors = _parse_schedule_form(request.form)

    upsert_daily_availability_windows(db, uid, windows)
    upsert_athlete_profile(db, uid, **profile_updates)
    db.commit()

    for msg in errors:
        flash(msg, 'warning')
    if not errors:
        flash('Schedule saved.', 'success')

    return redirect(url_for('profile.edit', tab='schedule'))


@bp.route('/skills', methods=['POST'])
def save_skills():
    """Persist the Skills-tab form submitted from `/profile?tab=skills`.

    Mirrors the onboarding-step write path: parse the form against the
    canonical vocab, UPSERT one row per toggle, evict Layer 1 caches.
    Lands the athlete back on the Skills tab.
    """
    db = get_db()
    uid = current_user_id()
    vocab = load_active_skill_capability_toggle_vocab(db)
    states = parse_skill_form(request.form, vocab)
    if states:
        upsert_athlete_skill_toggles(db, uid, states)
        db.commit()
        evict_layer1_on_skill_toggle_change(db, uid)
        flash('Skills saved.', 'success')
    return redirect(url_for('profile.edit', tab='skills'))


@bp.route('/connections/<provider>/disconnect', methods=['POST'])
def disconnect_provider(provider):
    """Athlete-initiated disconnect from the Account Config 1 tab.
    Scoped on `current_user_id()`; unknown provider slugs 404.
    `pa.disconnect` nulls credentials + flips status to `revoked` (no
    row delete — audit + scope-ack history is preserved).
    """
    if provider not in {slug for slug, _label, _endpoint in CONNECTION_PROVIDERS}:
        abort(404)
    db = get_db()
    changed = pa.disconnect(db, current_user_id(), provider)
    label = next(
        (lbl for slug, lbl, _endpoint in CONNECTION_PROVIDERS if slug == provider),
        provider,
    )
    if changed:
        flash(f'{label} disconnected.', 'info')
    else:
        flash(f'{label} was already disconnected.', 'info')
    return redirect(url_for('profile.edit', tab='connections'))


@bp.route('/preference/add', methods=['POST'])
def add_preference():
    """Manually add a coaching preference. Provenance is left NULL —
    the UI label distinguishes manual entries from auto-captured ones."""
    db = get_db()
    uid = current_user_id()
    category = (request.form.get('category') or '').strip()
    content = (request.form.get('content') or '').strip()
    permanent = 1 if request.form.get('permanent') else 0

    if category not in PREFERENCE_CATEGORIES:
        flash('Unknown preference category.', 'danger')
        return redirect(url_for('profile.coach_memory'))
    if not content:
        flash('Preference content required.', 'danger')
        return redirect(url_for('profile.coach_memory'))

    db.execute(
        'INSERT INTO coaching_preferences (category, content, permanent, user_id) '
        'VALUES (?, ?, ?, ?)',
        (category, content, permanent, uid)
    )
    db.commit()
    flash('Preference added.', 'success')
    return redirect(url_for('profile.coach_memory'))


@bp.route('/preference/<int:pref_id>/delete', methods=['POST'])
def delete_preference(pref_id):
    """Delete a coaching preference. Scoped on user_id — a crafted
    POST can't reach another user's row."""
    db = get_db()
    db.execute(
        'DELETE FROM coaching_preferences WHERE id=? AND user_id=?',
        (pref_id, current_user_id())
    )
    db.commit()
    flash('Preference removed.', 'info')
    return redirect(url_for('profile.coach_memory'))


@bp.route('/feedback/<int:fb_id>')
def view_feedback(fb_id):
    """Show the original feedback_log row that produced a preference.
    Scoped on user_id; 404s for other users' rows."""
    db = get_db()
    row = db.execute(
        'SELECT id, source, raw_content, captured_at FROM feedback_log '
        'WHERE id=? AND user_id=?',
        (fb_id, current_user_id())
    ).fetchone()
    if not row:
        abort(404)
    return render_template('profile/feedback.html', feedback=dict(row))


@bp.route('/account')
def account_settings():
    """Redesign §19 — Account settings. Identity (read-only, from `users`) +
    change password (posts to `profile.change_password`) + sign out (posts to
    `auth.logout`). No billing / 2FA / export / delete — cut for lack of
    backend (CONVENTIONS §E.1)."""
    db = get_db()
    uid = current_user_id()
    user_row = db.execute(
        'SELECT username, display_name, email, last_login FROM users WHERE id=?',
        (uid,)
    ).fetchone()
    return render_template('profile/account.html',
                           user_row=dict(user_row) if user_row else {})


@bp.route('/memory')
def coach_memory():
    """Redesign §20 — Coach memory. Durable AI-coach preferences with
    `fb_source` provenance (chat / plan_review / natural_log / workout_note /
    manual). List + manual add (`add_preference`) + delete
    (`delete_preference`)."""
    db = get_db()
    uid = current_user_id()
    return render_template('profile/coach_memory.html',
                           memory=_load_memory(db, uid),
                           preference_categories=PREFERENCE_CATEGORIES)


@bp.route('/password', methods=['POST'])
def change_password():
    db = get_db()
    uid = current_user_id()
    current = request.form.get('current_password') or ''
    new = request.form.get('new_password') or ''
    confirm = request.form.get('confirm_password') or ''

    if not current or not new:
        flash('Current and new password are both required.', 'danger')
        return redirect(url_for('profile.account_settings'))
    user_row = db.execute(
        'SELECT password_hash, username, display_name, email FROM users WHERE id=?',
        (uid,)
    ).fetchone()
    if not user_row or not _check_password(current, user_row['password_hash']):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('profile.account_settings'))
    strength_errors = _password_strength_errors(
        new, user_inputs=[user_row['username'], user_row['display_name'] or '',
                          user_row['email'] or '']
    )
    if strength_errors:
        for e in strength_errors:
            flash(e, 'danger')
        return redirect(url_for('profile.account_settings'))
    if new != confirm:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('profile.account_settings'))

    db.execute(
        'UPDATE users SET password_hash=? WHERE id=?',
        (_hash_password(new), uid)
    )
    db.commit()
    flash('Password changed.', 'success')
    return redirect(url_for('profile.account_settings'))


_TOKEN_TTL_DAYS_CHOICES = {'', '30', '90', '365'}


@bp.route('/api-tokens', methods=['POST'])
def create_api_token():
    """Issue a new bearer token for the current user.

    The plaintext is shown exactly once after creation (stashed in the
    Flask session and read-and-cleared on the next GET /profile/).
    Only the SHA-256 hash is persisted, so a leaked DB doesn't expose
    usable tokens.

    `ttl_days` is optional — empty / unset means the token never expires.
    Accepted values are restricted to the dropdown choices (30/90/365)
    to keep the UI simple; widen the allowlist when there's a real
    request for arbitrary TTLs.
    """
    name = (request.form.get('name') or '').strip()
    if not name or len(name) > 80:
        flash('Token name is required (1–80 characters).', 'danger')
        return redirect(url_for('profile.edit'))

    ttl_raw = (request.form.get('ttl_days') or '').strip()
    if ttl_raw not in _TOKEN_TTL_DAYS_CHOICES:
        flash('Invalid expiry choice.', 'danger')
        return redirect(url_for('profile.edit'))
    expires_at = None
    if ttl_raw:
        from datetime import datetime, timedelta
        expires_at = (
            datetime.utcnow() + timedelta(days=int(ttl_raw))
        ).isoformat(timespec='seconds')

    plaintext, hashed = generate_api_token()
    db = get_db()
    db.execute(
        'INSERT INTO api_tokens (user_id, name, token_hash, expires_at) '
        'VALUES (?,?,?,?)',
        (current_user_id(), name, hashed, expires_at)
    )
    db.commit()
    from flask import session as flask_session
    flask_session['new_api_token_plaintext'] = plaintext
    flash(f'Token "{name}" created. Copy it now — you won\'t see it again.', 'success')
    return redirect(url_for('profile.edit'))


@bp.route('/api-tokens/<int:token_id>/revoke', methods=['POST'])
def revoke_api_token(token_id):
    """Revoke a token. Scoped on user_id so a crafted POST can't reach
    another user's row. Soft-revoke (sets revoked_at) so the audit
    trail of past usage is preserved."""
    db = get_db()
    db.execute(
        'UPDATE api_tokens SET revoked_at = ? WHERE id = ? AND user_id = ? '
        'AND revoked_at IS NULL',
        (datetime.utcnow().isoformat(timespec='seconds'),
         token_id, current_user_id())
    )
    db.commit()
    flash('Token revoked.', 'info')
    return redirect(url_for('profile.edit'))
