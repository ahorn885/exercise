"""Onboarding flow blueprint (v5 Steps 2 + 3a).

Step 2 — D-58 "connect step" — the post-signup screen that lists
supported fitness providers, shows the v5 §A.1 Connected Service consent
disclosure, and offers Connect / Skip-for-now / Continue actions.

Step 3a — D-58 prefill comparison page — the v5 §A.2 provider-prefill
UX. Renders per-field cards comparing the athlete's stored value
against each connected provider's extractor output. PR7 shipped the
read side (D2a); PR8 wires the writes (D2b): `[Use provider value]`
applies the winning candidate + writes a `'provider_<slug>'` provenance
row; `[Keep current]` writes `'manual_override'` to suppress future
re-prefill; an inline "Use {provider} value instead" link beneath a
`'manual_override'` badge restores the provider value (v5 §A.2.6 clear
path). The profile-form save handler in `routes/profile.py` now flips
`'provider_*'` → `'manual_override'` when an athlete types over a
provider-sourced value (v5 §A.2.3).

Step 1 (account-creation acknowledgment) fires at `auth.register`.
Step 3 proper (§A profile-form entry) is the existing v1 surface at
`/profile?tab=athlete`. Continue from `/onboarding/connect` lands on
`/onboarding/prefill` instead of jumping straight to the profile form.

Reuses PR4's `CONNECTION_PROVIDERS` registry and `load_connections`
helper from `routes/profile.py` so the provider roster, status badges,
and connect-URL plumbing stay single-source. The only divergence from
the Connections-tab rendering is the `return_to` path (the OAuth
callback bounces the athlete back to `/onboarding/connect` instead of
`/profile?tab=connections`).
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)

from database import get_db
from athlete import (
    DAY_TOKENS, DAY_LABELS, DOUBLES_FEASIBLE_CHOICES,
    LONG_SESSION_MAX_HR_CHOICES, get_athlete_profile, upsert_athlete_profile,
    get_daily_availability_windows, upsert_daily_availability_windows,
)
from routes.auth import current_user_id
from routes.profile import CONNECTION_PROVIDERS, load_connections
from routes.profile_fields import KNOWN_PROFILE_FIELDS, provider_label


bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')


# Where to drop the athlete after Continue / Skip on Step 2. PR7 flips
# Continue to the new prefill comparison page; Skip still jumps straight
# to the profile form since an athlete who skipped connecting providers
# has nothing to compare against. PR12 (D-61) slots `/onboarding/schedule`
# between Step 3a (prefill) and the §A profile entry — Step 3b owns the
# per-day-windows §G surface.
_POST_STEP2_CONTINUE_TARGET = '/onboarding/prefill'
_POST_STEP2_SKIP_TARGET = '/profile?tab=athlete'
_POST_STEP3_TARGET = '/onboarding/schedule'
_POST_STEP3B_TARGET = '/profile?tab=athlete'

# Back-compat alias for the connect template (passes the value through
# to the Skip/Continue button copy via Jinja). Pre-PR7 callers expected
# a single target; the template now reads it as the Continue label hint
# only, since Skip has its own redirect target.
_POST_STEP2_TARGET = _POST_STEP2_CONTINUE_TARGET


@bp.route('/connect', methods=['GET'])
def connect():
    """Render the Step 2 connect screen.

    Lists every provider in `CONNECTION_PROVIDERS` with current status,
    the v5 §A.1 Connected Service consent disclosure (collapsible), and
    Connect buttons that bounce through the provider's `oauth_start`
    with `return_to=/onboarding/connect` so the post-OAuth callback
    lands the athlete back here with `?<slug>_connected=1` (success) or
    `?<slug>_oauth_error=…` / `?<slug>_register_error=1` (failure).
    """
    db = get_db()
    uid = current_user_id()

    return_to = url_for('onboarding.connect')
    connections = load_connections(db, uid, return_to=return_to)

    # Post-OAuth-callback flag surfacing. Same pattern as profile.edit
    # (PR4) — the first hit wins; multi-provider races on the same
    # render are rare-enough-to-ignore. The label drives the success /
    # error alert copy; the slug drives nothing (kept for parity in
    # case the template wants to highlight the specific card later).
    just_connected_label = None
    oauth_error_label = None
    for slug, label, _endpoint in CONNECTION_PROVIDERS:
        if just_connected_label is None and request.args.get(f'{slug}_connected') == '1':
            just_connected_label = label
        if oauth_error_label is None and (
            request.args.get(f'{slug}_oauth_error')
            or request.args.get(f'{slug}_register_error')
        ):
            oauth_error_label = label

    connected_count = sum(1 for c in connections if c['is_connected'])

    return render_template(
        'onboarding/connect.html',
        connections=connections,
        connected_count=connected_count,
        just_connected_label=just_connected_label,
        oauth_error_label=oauth_error_label,
        post_step2_target=_POST_STEP2_TARGET,
    )


@bp.route('/skip', methods=['POST'])
def skip():
    """Skip Step 2 with no providers connected.

    No DB write — the v5 §A.2.4 14-day connect-provider nudge (Option E
    in the PR4 §5.1 menu, not yet implemented) keys off `provider_auth`
    rowcount + account age, not off a skip event. If a future PR wants
    to differentiate "skipped explicitly" from "never visited the page"
    it can add an `account_nudges` row with `nudge_type='step2_skipped'`
    here. For PR5 the skip is a pure redirect.
    """
    flash(
        "You can connect providers any time from Profile → Connections.",
        'info',
    )
    return redirect(_POST_STEP2_SKIP_TARGET)


@bp.route('/continue', methods=['POST'])
def continue_():
    """Proceed to Step 3a (prefill review). PR7 flips this target from
    the bare profile form to `/onboarding/prefill` so athletes who
    connected at least one provider see the comparison page first.
    Athletes who connected zero providers also land here — the prefill
    page renders an honest empty state and offers a one-click pass
    through to the profile form.
    """
    return redirect(_POST_STEP2_CONTINUE_TARGET)


def _lookup_field(name):
    """Resolve a field name → `KNOWN_PROFILE_FIELDS` entry, or None.
    Used by the prefill POST handlers to validate the URL-param field
    against the registry before any DB write — unknown names 404."""
    for fd in KNOWN_PROFILE_FIELDS:
        if fd['name'] == name:
            return fd
    return None


def _resolve_candidates(db, uid, field_def, connected_slugs):
    """Return per-connected-provider candidate values for one field,
    sorted most-recent-first (v5 §A.2.2 step 3 winner = candidates[0]).

    Each entry: dict with `provider_slug`, `provider_label`, `value`,
    `synced_at`, `note`. Providers without data return None from the
    extractor and are skipped. None `synced_at` sorts to the end so
    present-but-undated candidates still render below dated ones.
    """
    candidates = []
    for slug, extractor in field_def['extractors'].items():
        if slug not in connected_slugs:
            continue
        value, synced_at, note = extractor(db, uid)
        if value is None:
            continue
        candidates.append({
            'provider_slug': slug,
            'provider_label': provider_label(slug),
            'value': value,
            'synced_at': synced_at,
            'note': note,
        })
    candidates.sort(key=lambda c: c['synced_at'] or '', reverse=True)
    return candidates


def _write_provider_provenance(db, uid, field_name, provider_slug):
    """UPSERT a `'provider_<slug>'` provenance row."""
    db.execute(
        'INSERT INTO athlete_profile_field_provenance '
        '(user_id, field_name, source) VALUES (?, ?, ?) '
        'ON CONFLICT (user_id, field_name) DO UPDATE SET '
        '    source = EXCLUDED.source, last_updated_at = NOW()',
        (uid, field_name, f'provider_{provider_slug}'),
    )


def _write_manual_override_provenance(db, uid, field_name):
    """UPSERT a `'manual_override'` provenance row. Called by `keep_current`
    when the athlete explicitly chooses to suppress provider re-prefill."""
    db.execute(
        'INSERT INTO athlete_profile_field_provenance '
        '(user_id, field_name, source) VALUES (?, ?, ?) '
        'ON CONFLICT (user_id, field_name) DO UPDATE SET '
        '    source = EXCLUDED.source, last_updated_at = NOW()',
        (uid, field_name, 'manual_override'),
    )


@bp.route('/prefill', methods=['GET'])
def prefill():
    """Render the v5 §A.2 per-field prefill comparison page (Step 3a).

    For each `KNOWN_PROFILE_FIELDS` entry, resolves:
      - Currently stored value from `athlete_profile`.
      - Existing provenance row (if any) from
        `athlete_profile_field_provenance` — drives the per-field
        `source` tag in the UI.
      - Per-connected-provider candidate values via
        `_resolve_candidates`.
    """
    db = get_db()
    uid = current_user_id()

    profile = get_athlete_profile(db, uid) or {}

    connections = load_connections(db, uid)
    connected_slugs = {c['slug'] for c in connections if c['is_connected']}

    rows = db.execute(
        'SELECT field_name, source, last_updated_at '
        'FROM athlete_profile_field_provenance WHERE user_id = ?',
        (uid,),
    ).fetchall()
    provenance_by_field = {r['field_name']: dict(r) for r in rows}

    fields = []
    for field_def in KNOWN_PROFILE_FIELDS:
        name = field_def['name']
        fields.append({
            'name': name,
            'label': field_def['label'],
            'unit': field_def['unit'],
            'current_value': profile.get(name),
            'provenance': provenance_by_field.get(name),
            'candidates': _resolve_candidates(db, uid, field_def, connected_slugs),
        })

    fields_with_candidates = sum(1 for f in fields if f['candidates'])

    return render_template(
        'onboarding/prefill.html',
        fields=fields,
        fields_with_candidates=fields_with_candidates,
        connected_count=len(connected_slugs),
        post_step3_target=_POST_STEP3_TARGET,
        # Exposed so the badge for a `'provider_<slug>'` source renders
        # "From COROS" / "From Polar" using the CONNECTION_PROVIDERS
        # display labels instead of the raw lowercase slug.
        provider_label=provider_label,
    )


@bp.route('/prefill/<field>/use-provider', methods=['POST'])
def use_provider(field):
    """Apply the winning provider candidate for `field` (v5 §A.2.5
    per-field 'use this' + §A.2.6 clear-override 'use {provider} value
    instead'). Both UI entry points hit this same endpoint.

    Re-resolves candidates at write time — the form carries no value
    payload, so a stale browser tab can't push a value the provider no
    longer reports. Aborts with a flash if (a) the field name isn't in
    the registry, (b) no provider candidate is available right now.
    """
    field_def = _lookup_field(field)
    if field_def is None:
        abort(404)

    db = get_db()
    uid = current_user_id()

    connections = load_connections(db, uid)
    connected_slugs = {c['slug'] for c in connections if c['is_connected']}
    candidates = _resolve_candidates(db, uid, field_def, connected_slugs)

    if not candidates:
        flash(
            f'No provider value available for {field_def["label"]} right now.',
            'warning',
        )
        return redirect(url_for('onboarding.prefill'))

    winner = candidates[0]
    upsert_athlete_profile(db, uid, **{field_def['name']: winner['value']})
    _write_provider_provenance(db, uid, field_def['name'], winner['provider_slug'])
    db.commit()
    flash(
        f'{field_def["label"]} set from {winner["provider_label"]}.',
        'success',
    )
    return redirect(url_for('onboarding.prefill'))


@bp.route('/prefill/<field>/keep-current', methods=['POST'])
def keep_current(field):
    """Record an explicit "keep current, suppress re-prefill" for `field`
    (v5 §A.2.3 manual_override stickiness). Writes a `'manual_override'`
    provenance row without changing the stored value.

    Defensive guard: aborts with a flash if there's no current value to
    keep (the prefill template hides the button in that case, but a
    crafted POST could still hit this endpoint).
    """
    field_def = _lookup_field(field)
    if field_def is None:
        abort(404)

    db = get_db()
    uid = current_user_id()
    profile = get_athlete_profile(db, uid) or {}

    if profile.get(field_def['name']) is None:
        flash(
            f'{field_def["label"]} has no current value to keep. '
            'Enter one on the profile page if you want to suppress '
            'provider prefill for this field.',
            'warning',
        )
        return redirect(url_for('onboarding.prefill'))

    _write_manual_override_provenance(db, uid, field_def['name'])
    db.commit()
    flash(
        f'{field_def["label"]} marked as manually set. '
        'Provider prefill is suppressed for this field.',
        'info',
    )
    return redirect(url_for('onboarding.prefill'))


# ---------------------------------------------------------------------------
# Step 3b — Schedule & Availability (D-61 §G)
# ---------------------------------------------------------------------------

# v5 §G form field shape per `Onboarding_D61_Design_v1.md`. Per-day rows
# carry primary (and optional secondary) window inputs; three orthogonal
# capacity toggles capture long-session capacity, doubles feasibility,
# and preferred rest days. JIT session-card swap UI explicitly deferred
# to post-Layer-4 per PR11 §5.1 Option A1.


def _parse_int(value, *, min_=None, max_=None):
    """Coerce a form value to an int inside [min_, max_]; None on miss."""
    if value is None or value == '':
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if min_ is not None and n < min_:
        return None
    if max_ is not None and n > max_:
        return None
    return n


def _parse_time(value):
    """Accept 'HH:MM' (24h). Returns string or None. Strict parse — bad
    values are dropped rather than silently zeroed."""
    if not value or not isinstance(value, str):
        return None
    parts = value.split(':')
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return f'{h:02d}:{m:02d}'


def _filter_day_tokens(values):
    """Return the subset of `values` that are valid day tokens, ordered
    by DAY_TOKENS (Sunday..Saturday). Empty list when nothing valid."""
    if not values:
        return []
    s = set(values)
    return [t for t in DAY_TOKENS if t in s]


def _parse_schedule_form(form):
    """Parse the §G form payload into ({windows, profile_updates}, errors).

    `windows` matches `upsert_daily_availability_windows`'s input shape.
    `profile_updates` is a dict of athlete_profile column updates.
    `errors` is a list of human-readable strings (rendered as flashes).

    The form is permissive — disabled days drop start/duration silently;
    invalid times/durations drop their day to disabled with a flash so
    the athlete can correct on the re-render rather than seeing a 500.
    """
    errors = []
    windows = []
    enabled_day_tokens = []

    doubles = form.get('doubles_feasible', '').strip().lower()
    if doubles not in DOUBLES_FEASIBLE_CHOICES:
        doubles = 'no'
    doubles_allows_second = doubles in ('regularly', 'occasionally')

    for dow, token in enumerate(DAY_TOKENS):
        primary_enabled = bool(form.get(f'enabled_{token}'))
        primary_start = _parse_time(form.get(f'start_{token}'))
        primary_dur = _parse_int(
            form.get(f'duration_{token}'), min_=30, max_=360,
        )
        if primary_enabled and (primary_start is None or primary_dur is None):
            errors.append(
                f'{DAY_LABELS[dow]}: start time and duration (30–360 min) '
                'are required when the day is enabled. The day was left '
                'disabled.'
            )
            primary_enabled = False
            primary_start = None
            primary_dur = None

        secondary = None
        if doubles_allows_second:
            second_enabled = bool(form.get(f'enabled2_{token}'))
            if second_enabled and not primary_enabled:
                errors.append(
                    f'{DAY_LABELS[dow]}: a second window requires the '
                    "primary window enabled. Second window dropped."
                )
                second_enabled = False
            if second_enabled:
                second_start = _parse_time(form.get(f'start2_{token}'))
                second_dur = _parse_int(
                    form.get(f'duration2_{token}'), min_=30, max_=360,
                )
                if second_start is None or second_dur is None:
                    errors.append(
                        f'{DAY_LABELS[dow]}: second-window start and '
                        'duration (30–360 min) are required. Second '
                        'window dropped.'
                    )
                else:
                    secondary = {
                        'enabled': True,
                        'window_start': second_start,
                        'window_duration_min': second_dur,
                    }

        if primary_enabled:
            enabled_day_tokens.append(token)

        windows.append({
            'day_of_week': dow,
            'day_token': token,
            'day_label': DAY_LABELS[dow],
            'primary': {
                'enabled': primary_enabled,
                'window_start': primary_start,
                'window_duration_min': primary_dur,
            },
            'secondary': secondary,
        })

    # Long Session Available — Y/N + day-set (subset of enabled) + max hr.
    long_available = bool(form.get('long_session_available'))
    raw_long_days = _filter_day_tokens(form.getlist('long_session_days'))
    long_days = [t for t in raw_long_days if t in enabled_day_tokens]
    if long_available and raw_long_days and not long_days:
        errors.append(
            'Long-session days must be a subset of your enabled training '
            'days. Long-session selection cleared.'
        )
    long_max_hr = _parse_int(form.get('long_session_max_hr'))
    if long_max_hr is not None and long_max_hr not in LONG_SESSION_MAX_HR_CHOICES:
        long_max_hr = None
    if long_available and (not long_days or long_max_hr is None):
        errors.append(
            'Long Session Available was selected but day(s) and max '
            'duration are required — long-session capacity not saved.'
        )
        long_available = False
        long_days = []
        long_max_hr = None
    if not long_available:
        long_days = []
        long_max_hr = None

    # Preferred Rest Day(s) — soft signal; no strict-subset enforcement.
    rest_days = _filter_day_tokens(form.getlist('preferred_rest_days'))

    profile_updates = {
        'long_session_available': long_available,
        'long_session_days': ','.join(long_days) if long_days else None,
        'long_session_max_hr': long_max_hr,
        'doubles_feasible': doubles,
        'preferred_rest_days': ','.join(rest_days) if rest_days else None,
    }
    return windows, profile_updates, errors


def _split_csv_days(value):
    """Comma-separated day tokens -> list, defensively filtering invalid."""
    if not value:
        return []
    return _filter_day_tokens([t.strip().lower() for t in value.split(',')])


@bp.route('/schedule', methods=['GET'])
def schedule():
    """Render the v5 §G Schedule & Availability form (Step 3b).

    Reads existing per-day windows + athlete-profile capacity fields and
    renders the form pre-populated. Athletes returning to the page see
    their last save; new athletes see seven disabled-day rows.
    """
    db = get_db()
    uid = current_user_id()

    profile = get_athlete_profile(db, uid) or {}
    days = get_daily_availability_windows(db, uid)

    long_days = _split_csv_days(profile.get('long_session_days'))
    rest_days = _split_csv_days(profile.get('preferred_rest_days'))
    doubles = (profile.get('doubles_feasible') or 'no').lower()
    if doubles not in DOUBLES_FEASIBLE_CHOICES:
        doubles = 'no'

    return render_template(
        'onboarding/schedule.html',
        days=days,
        doubles_feasible=doubles,
        doubles_choices=DOUBLES_FEASIBLE_CHOICES,
        long_session_available=bool(profile.get('long_session_available')),
        long_session_days=long_days,
        long_session_max_hr=profile.get('long_session_max_hr'),
        long_session_max_hr_choices=LONG_SESSION_MAX_HR_CHOICES,
        preferred_rest_days=rest_days,
        day_tokens=DAY_TOKENS,
        day_labels=DAY_LABELS,
        post_step3b_target=_POST_STEP3B_TARGET,
    )


@bp.route('/schedule', methods=['POST'])
def schedule_save():
    """Persist the §G form. Per-day windows replace existing rows for
    this user; athlete_profile carries the three orthogonal capacity
    toggles. Errors flash and re-render; partial saves are allowed —
    any field that parsed cleanly persists.
    """
    db = get_db()
    uid = current_user_id()

    windows, profile_updates, errors = _parse_schedule_form(request.form)

    upsert_daily_availability_windows(db, uid, windows)
    upsert_athlete_profile(db, uid, **profile_updates)
    db.commit()

    for msg in errors:
        flash(msg, 'warning')

    if errors:
        # Re-render with the just-persisted state so the athlete can fix
        # the rows that didn't make it through validation.
        return redirect(url_for('onboarding.schedule'))

    flash('Schedule saved. You can edit per-day windows any time from your profile.', 'success')
    return redirect(_POST_STEP3B_TARGET)
