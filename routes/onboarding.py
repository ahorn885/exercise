"""Onboarding flow blueprint (v5 Steps 2 + 3a + 3b + 3c + 3d).

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

Step 3b — D-61 Schedule & availability — the v5 §G per-day-windows form.
Saves the athlete's training windows + capacity toggles (long-session,
doubles, preferred rest days).

Step 3c — D-66 §H.2 target-race — captures race name, event_date,
race_format (closed 4-enum), and the multi-day-only extension fields
(distance_km, total_elevation_gain_m, race_rules_summary,
mandatory_gear_text). Writes a `race_events` row with `is_target_event=TRUE`
(or UPDATEs the existing target row). All picks redirect to the §H.4
route-locale step (optional on every event type). Skip writes an
`'target_race_skipped'` account_nudge + redirects to the profile form.

Step 3d — D-66 §H.4 route-locales (offered on every event type, optional)
— captures the athlete's route-locale graph (start + transition_areas +
aid_stations +
drop_bag_points + bivvies + finish) for the target race_event. Per
design §6.3 the step is skippable; on skip OR continue-with-<2-locales
an `'route_locales_incomplete'` account_nudge fires so the athlete sees
a soft reminder later. Equipment-per-locale CRUD is intentionally
deferred to the profile UI (`/profile/race-events/<id>/edit`) per the
"profile UI handles later additions" framing in design §6.3.

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

import json
import re
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)

from database import get_db
from athlete import (
    DAY_TOKENS, DAY_LABELS, DOUBLES_FEASIBLE_CHOICES, TWO_A_DAY_CHOICES,
    get_athlete_profile, upsert_athlete_profile,
    get_daily_availability_windows, upsert_daily_availability_windows,
)
from race_events_invalidation import (
    evict_on_target_event_brief_field_change,
    evict_on_target_event_framework_sport_change,
    evict_on_target_event_included_discipline_ids_change,
    evict_on_target_event_periodization_change,
)
from race_events_repo import (
    VALID_RACE_FORMATS,
    VALID_ROUTE_LOCALE_ROLES,
    add_route_locale,
    create_race_event,
    delete_route_locale,
    list_route_locales,
    update_race_event,
)
from routes.auth import current_user_id
from routes.locales import LOCALES as LEGACY_LOCALES
from routes.profile import CONNECTION_PROVIDERS, load_connections
from routes.profile_fields import KNOWN_PROFILE_FIELDS, provider_label

from athlete_skill_toggles_repo import (
    evict_layer1_on_skill_toggle_change,
    get_athlete_skill_toggles,
    load_active_skill_capability_toggle_vocab,
    parse_skill_form,
    upsert_athlete_skill_toggles,
)
from athlete_crafts_repo import (
    CraftSelectionError,
    get_athlete_crafts,
    load_craft_catalog,
    replace_athlete_crafts,
)


bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')


# Where to drop the athlete after Continue / Skip on Step 2. PR7 flips
# Continue to the new prefill comparison page; Skip still jumps straight
# to the profile form since an athlete who skipped connecting providers
# has nothing to compare against. PR12 (D-61) slots `/onboarding/schedule`
# between Step 3a (prefill) and the §A profile entry — Step 3b owns the
# per-day-windows §G surface. D-66 onboarding slots
# `/onboarding/target-race` after schedule (Step 3c) so athletes write a
# `race_events` row with `is_target_event=TRUE` before landing on the
# profile form. Multi-day picks then flow through `/onboarding/route-locales`
# (Step 3d) before profile.
_POST_STEP2_CONTINUE_TARGET = '/onboarding/prefill'
_POST_STEP2_SKIP_TARGET = '/profile?tab=athlete'
# Bucket C (l) capture-surface follow-on (2026-05-24): inserts the
# Locations review + Skills capture steps between prefill and schedule.
# Old: prefill → schedule. New: prefill → locales → skills → schedule.
_POST_STEP3_TARGET = '/onboarding/locales'
_POST_STEP_LOCALES_TARGET = '/onboarding/skills'
_POST_STEP_SKILLS_TARGET = '/onboarding/schedule'
_POST_STEP3B_TARGET = '/onboarding/target-race'
_POST_STEP3C_TARGET = '/profile?tab=athlete'
_POST_STEP3D_TARGET = '/profile?tab=athlete'

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
# Step 4 — Locations review (Bucket C (l) capture-surface follow-on)
# ---------------------------------------------------------------------------


def _athlete_locales_for_review(db, uid: int) -> list:
    """Return the per-athlete locale rows for the onboarding-Step-4
    review template. Shape:
      {slug, label, is_custom, configured, category}

    Includes every legacy slot (home / hotel / partner / airport) with
    `is_custom=False` so athletes always see the four default slots
    even when zero rows exist. Custom rows (locale_profiles where slug
    is not in LEGACY_LOCALES) carry `is_custom=True`. `configured`
    reflects whether locale_profiles has a row for the slug — drives
    the "(not configured)" small print in the legacy-slot list.
    """
    rows = db.execute(
        'SELECT locale, locale_name, category FROM locale_profiles '
        'WHERE user_id = ?',
        (uid,),
    ).fetchall()
    by_slug = {r['locale']: r for r in rows}
    out = []
    for slug in LEGACY_LOCALES:
        row = by_slug.get(slug)
        out.append({
            'slug': slug,
            'label': (row['locale_name'] if row and row['locale_name'] else slug),
            'is_custom': False,
            'configured': row is not None,
            'category': (row['category'] if row else None),
        })
    for slug in sorted(s for s in by_slug if s not in LEGACY_LOCALES):
        row = by_slug[slug]
        out.append({
            'slug': slug,
            'label': row['locale_name'] or slug,
            'is_custom': True,
            'configured': True,
            'category': row['category'],
        })
    return out


@bp.route('/locales', methods=['GET'])
def locales():
    """Render the Step 4 locations review screen.

    Read-only summary of the athlete's locale_profiles rows + the four
    legacy slots, with edit links pointing at the existing /locales
    blueprint (which owns the Mapbox picker, terrain grid, equipment
    editor). Continue advances to /onboarding/skills regardless of
    locale count — the step educates and provides a CTA, not a gate.
    """
    db = get_db()
    uid = current_user_id()
    return render_template(
        'onboarding/locales.html',
        athlete_locales=_athlete_locales_for_review(db, uid),
        post_step_locales_target=_POST_STEP_LOCALES_TARGET,
    )


@bp.route('/locales/continue', methods=['POST'])
def locales_continue():
    """Advance from Step 4 (locations review) to Step 5 (skills).

    No DB write — the review step doesn't mutate locale_profiles; that
    happens through the /locales blueprint's own POST handlers.
    """
    return redirect(_POST_STEP_LOCALES_TARGET)


# ---------------------------------------------------------------------------
# Step 5 — Skills capture (Bucket C (l) capture-surface follow-on)
# ---------------------------------------------------------------------------


@bp.route('/skills', methods=['GET'])
def skills():
    """Render the Step 5 skill-capability toggle grid.

    Loads the active vocab from layer0.skill_capability_toggles + the
    athlete's current per-toggle state from athlete_skill_toggles, and
    renders the shared `_skills_form.html` partial.
    """
    db = get_db()
    uid = current_user_id()
    return render_template(
        'onboarding/skills.html',
        toggle_defs=load_active_skill_capability_toggle_vocab(db),
        current_states=get_athlete_skill_toggles(db, uid),
        # 2c.2b (#540) — owned-craft picker shares this step.
        craft_catalog=load_craft_catalog(),
        athlete_crafts=get_athlete_crafts(db, uid),
        post_step_skills_target=_POST_STEP_SKILLS_TARGET,
    )


@bp.route('/skills', methods=['POST'])
def skills_save():
    """Persist the Step 5 skill-capability state + advance to Step 6.

    UPSERTs one athlete_skill_toggles row per canonical toggle (every
    vocab entry produces either an explicit-True or explicit-False
    row). Fires the Layer 1 cache eviction so the next plan / brief /
    ad-hoc workout / Layer 3 evaluation recomputes against the new
    skill_toggle_states. Empty vocab (populate script not yet applied)
    no-ops the upsert + still advances.
    """
    db = get_db()
    uid = current_user_id()
    vocab = load_active_skill_capability_toggle_vocab(db)
    states = parse_skill_form(request.form, vocab)
    # 2c.2b (#540) — the same step captures owned crafts (replace-all per
    # family; the form always submits the current checkbox state). Validated
    # against the closed enums before any write.
    try:
        replace_athlete_crafts(
            db,
            uid,
            bike_types=request.form.getlist('bike_types'),
            paddle_crafts=request.form.getlist('paddle_crafts'),
        )
    except CraftSelectionError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('onboarding.skills'))
    if states:
        upsert_athlete_skill_toggles(db, uid, states)
    db.commit()
    # Skills + crafts both live in Layer 1 — one eviction covers both.
    evict_layer1_on_skill_toggle_change(db, uid)
    flash('Skills & gear saved.', 'success')
    return redirect(_POST_STEP_SKILLS_TARGET)


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

    doubles = form.get('doubles_feasible', '').strip().lower()
    if doubles not in DOUBLES_FEASIBLE_CHOICES:
        doubles = 'no'
    doubles_allows_second = doubles in ('regularly', 'occasionally')

    for dow, token in enumerate(DAY_TOKENS):
        primary_enabled = bool(form.get(f'enabled_{token}'))
        primary_start = _parse_time(form.get(f'start_{token}'))
        primary_dur = _parse_int(
            form.get(f'duration_{token}'), min_=30, max_=720,
        )
        if primary_enabled and (primary_start is None or primary_dur is None):
            errors.append(
                f'{DAY_LABELS[dow]}: start time and duration (30–720 min) '
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

    # FormRefresh Slice C (2026-05-25) — the long-session day + rest days are
    # no longer asked: the longest enabled window is the weekly long session
    # and disabled days are the rest days, both derived downstream from the
    # per-day windows.
    #
    # Slice 2b.2b §5.1.1 — two session-count-ceiling scalars join doubles:
    #   * two_a_day_preference: the friendly density control (radio; defaults
    #     to 'occasionally' on miss, mirroring the doubles fallback).
    #   * peak_sessions_max: the optional advanced override. Blank → NULL (the
    #     grid derives the ceiling from the preference). Rejected (with a flash)
    #     when out of 1..2×available_days — the grid's hard feasibility clamp.
    two_a_day = form.get('two_a_day_preference', '').strip().lower()
    if two_a_day not in TWO_A_DAY_CHOICES:
        two_a_day = 'occasionally'

    available_days = sum(1 for w in windows if w['primary']['enabled'])
    raw_peak = (form.get('peak_sessions_max') or '').strip()
    if raw_peak:
        peak_sessions_max = _parse_int(raw_peak, min_=1, max_=max(1, 2 * available_days))
        if peak_sessions_max is None:
            errors.append(
                f'Most sessions per week at Peak must be a whole number from 1 '
                f'to {2 * available_days} (2× your {available_days} available '
                'training day(s)). Left unset — the ceiling follows your '
                'two-a-day preference instead.'
            )
    else:
        peak_sessions_max = None

    profile_updates = {
        'doubles_feasible': doubles,
        'two_a_day_preference': two_a_day,
        'peak_sessions_max': peak_sessions_max,
    }
    return windows, profile_updates, errors


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

    doubles = (profile.get('doubles_feasible') or 'no').lower()
    if doubles not in DOUBLES_FEASIBLE_CHOICES:
        doubles = 'no'

    two_a_day = (profile.get('two_a_day_preference') or 'occasionally').lower()
    if two_a_day not in TWO_A_DAY_CHOICES:
        two_a_day = 'occasionally'

    return render_template(
        'onboarding/schedule.html',
        days=days,
        doubles_feasible=doubles,
        doubles_choices=DOUBLES_FEASIBLE_CHOICES,
        two_a_day_preference=two_a_day,
        two_a_day_choices=TWO_A_DAY_CHOICES,
        peak_sessions_max=profile.get('peak_sessions_max'),
        post_step3b_target=_POST_STEP3B_TARGET,
    )


@bp.route('/schedule', methods=['POST'])
def schedule_save():
    """Persist the §G form. Per-day windows replace existing rows for
    this user; athlete_profile carries the `doubles_feasible` toggle.
    Errors flash and re-render; partial saves are allowed — any field
    that parsed cleanly persists.
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


# ---------------------------------------------------------------------------
# Step 3c — Target race (D-66 §H.2)
# ---------------------------------------------------------------------------

# Inline form parsers — mirror the patterns from `routes/race_events.py`
# so the onboarding + profile-tab surfaces coerce form input identically.


def _parse_str_field(form, key):
    v = (form.get(key) or '').strip()
    return v or None


def _parse_decimal_field(form, key):
    v = (form.get(key) or '').strip()
    if not v:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_date_field(form, key):
    v = (form.get(key) or '').strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_int_field(form, key):
    v = (form.get(key) or '').strip()
    if not v:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


# Terrain-row form parser + vocabulary lookup — mirrors `_TRN_PATTERN` +
# `_parse_race_terrain` + `_terrain_choices` in `routes/race_events.py`.
# Duplicated route-local (rather than shared in `race_events_repo.py`) to
# keep the repo layer free of form-parsing concerns; the helpers are tiny
# and the duplication is explicitly cross-referenced. Drift is exercised
# by tests on both sides.
_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")


def _parse_race_terrain(form):
    """Parse the repeating `race_terrain[N][...]` form fields into a list
    of `{"terrain_id": str, "pct_of_race": float, "discipline_id": str|None}`
    dicts.

    Empty rows (no terrain_id selected OR no percent entered) are silently
    dropped — athletes adding a row then leaving it blank shouldn't fail
    the save. Invalid terrain_id (not matching TRN-\\d{3}) or invalid
    percent (non-numeric / out of [0, 100]) drops the row and skips it.
    Mirrors `routes/race_events.py:_parse_race_terrain` (D-73 Phase 5.2
    Bucket E.(c)-C1 — per-row discipline_id added on both sides).
    """
    out = []
    indices = set()
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


def _parse_discipline_id_filter(form):
    """Parse `included_discipline_ids` checkbox values into a canonical-id
    list, or None when no boxes are checked. Mirrors
    `routes/race_events.py:_parse_discipline_id_filter` exactly.
    """
    if hasattr(form, 'getlist'):
        raw = form.getlist('included_discipline_ids')
    else:
        raw = []
    values = [v.strip() for v in raw if isinstance(v, str) and v and v.strip()]
    return values or None


def _terrain_choices(db):
    """Return `{id, label, description}` dicts for race-eligible
    `layer0.terrain_types` rows.

    `id` is the canonical TRN-xxx slug; `label` is the `canonical_name`;
    `description` is the row `notes` (rendered as a hover tooltip — issue
    #444). Training-only terrains are dropped (issue #445). ORDER BY
    terrain_id for stable rendering; ~16 rows so no caching. Mirrors
    `routes/race_events.py:_terrain_choices` (this form renders the same
    `_race_terrain_editor.html` partial, so the two must agree).
    """
    # Function-local import to match this module's other race_events imports
    # and keep blueprint load order circular-import-safe.
    from routes.race_events import RACE_INELIGIBLE_TERRAIN_IDS
    # D-73 Phase 5.2 Bucket E.(a) — defensive `terrain_id IS NOT NULL`
    # filter. See `routes/race_events.py:_terrain_choices` for rationale.
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


def _get_target_race_row(db, uid):
    """Return the athlete's current target race_events row as a dict, or
    None when no target row exists. Used by Step 3c GET to pre-populate
    the form when the athlete returns to onboarding mid-stream.

    `race_terrain` is hydrated to a list of dicts (list-or-string-tolerant
    JSONB adapter, matching `race_events_repo.get_race_event`); `None`
    falls back to `[]` so downstream comparison + template iteration
    never hit a NoneType.
    """
    cur = db.execute(
        'SELECT id, name, event_date, race_format, distance_km, '
        '       total_elevation_gain_m, race_rules_summary, mandatory_gear_text, '
        '       event_locale_id, notes, race_terrain, previous_attempts, '
        '       goal_outcome, first_time_at_distance, time_goal, race_pack_weight_kg, '
        '       event_locale_name, event_locale_mapbox_id, event_locale_place_name, '
        '       event_locale_lat, event_locale_lng, race_url, framework_sport, '
        '       included_discipline_ids '
        '  FROM race_events '
        ' WHERE user_id = ? AND is_target_event = TRUE '
        ' LIMIT 1',
        (uid,),
    )
    row = cur.fetchone()
    if not row:
        return None
    result = dict(row)
    raw_terrain = result.get('race_terrain')
    if isinstance(raw_terrain, str):
        result['race_terrain'] = json.loads(raw_terrain) if raw_terrain else []
    elif raw_terrain is None:
        result['race_terrain'] = []
    # previous_attempts JSONB hydration mirrors race_terrain (§H.2 Slice 2).
    raw_attempts = result.get('previous_attempts')
    if isinstance(raw_attempts, str):
        result['previous_attempts'] = json.loads(raw_attempts) if raw_attempts else []
    elif raw_attempts is None:
        result['previous_attempts'] = []
    # D-73 Phase 5.2 walkthrough #1 (2026-05-21) — NUMERIC(9,6) lat/lng
    # round-trips as Decimal; coerce to float so template arithmetic stays
    # simple. Mirrors `race_events_repo.get_race_event` precedent.
    for k in ('event_locale_lat', 'event_locale_lng'):
        v = result.get(k)
        if v is not None and not isinstance(v, float):
            result[k] = float(v)
    # D-73 Phase 5.2 Bucket E.(b)-B2 — TEXT[] adapter surfaces as list[str]
    # under psycopg2; coerce any non-list iterable to list for clean equals
    # comparisons in the eviction-diff path below.
    raw_disc_filter = result.get('included_discipline_ids')
    if raw_disc_filter is not None and not isinstance(raw_disc_filter, list):
        result['included_discipline_ids'] = list(raw_disc_filter)
    return result


def _write_account_nudge(db, uid, nudge_type):
    """UPSERT an account_nudges row keyed on (user_id, nudge_type).

    The `account_nudges` table carries `UNIQUE (user_id, nudge_type)`;
    a repeat write (e.g., athlete re-skips after re-visiting the step)
    silently no-ops via `ON CONFLICT DO NOTHING` rather than raising.
    """
    db.execute(
        'INSERT INTO account_nudges (user_id, nudge_type) VALUES (?, ?) '
        'ON CONFLICT (user_id, nudge_type) DO NOTHING',
        (uid, nudge_type),
    )


@bp.route('/target-race', methods=['GET'])
def target_race():
    """Render the v5 §H.2 target-race form (Step 3c).

    If the athlete already has a target race_events row (e.g., migrated
    from legacy athlete_profile.target_event_*, or returning to onboarding
    after a prior save), the form pre-populates from it and POST updates
    the existing row. Otherwise POST creates a new row with
    `is_target_event=TRUE`.
    """
    db = get_db()
    uid = current_user_id()

    target = _get_target_race_row(db, uid)
    terrain_choices = _terrain_choices(db)

    # D-73 Phase 5.2 Bucket E.(b)-B2 + E.(c)-C1 — discipline grid for the
    # B2 `<select multiple>` rendered as checkboxes + the per-row terrain
    # discipline_id `<select>`. Initial render resolves
    # `target.framework_sport ?? athlete_profile.primary_sport` so the
    # checkbox grid populates from page load; the inline JS picker rebinds
    # when the athlete edits the framework_sport input. Mirrors the
    # `_resolve_effective_framework_sport` + `_disciplines_for_framework_sport`
    # helpers from `routes/race_events.py`.
    from routes.race_events import (
        _resolve_effective_framework_sport,
        _disciplines_for_framework_sport,
    )
    initial_framework_sport = _resolve_effective_framework_sport(db, uid, target)
    discipline_choices = _disciplines_for_framework_sport(db, initial_framework_sport)

    # D-73 Phase 5.2 walkthrough #1 (2026-05-21) — race-location picker
    # imports the Mapbox disclosure ack helpers from `routes/locales`;
    # disclosure version is shared across `/locales/new` and the race-event
    # picker so a prior ack from either surface unblocks both.
    from routes.locales import _disclosure_acked, MAPBOX_DISCLOSURE_VERSION
    return render_template(
        'onboarding/target_race.html',
        target=target,
        terrain_choices=terrain_choices,
        discipline_choices=discipline_choices,
        initial_framework_sport=initial_framework_sport,
        race_formats=VALID_RACE_FORMATS,
        post_step3c_target=_POST_STEP3C_TARGET,
        mapbox_acked=_disclosure_acked(db, uid),
        mapbox_disclosure_version=MAPBOX_DISCLOSURE_VERSION,
    )


@bp.route('/target-race', methods=['POST'])
def target_race_save():
    """Persist the §H.2 target-race form. Writes a `race_events` row with
    `is_target_event=TRUE` (or UPDATEs the existing target row).

    All race_format picks redirect to `/onboarding/route-locales` so the
    athlete can fill in the route graph if they want; the step is optional
    on every event type. Errors flash and re-render.
    """
    db = get_db()
    uid = current_user_id()

    name = _parse_str_field(request.form, 'name')
    event_date = _parse_date_field(request.form, 'event_date')
    race_format = (request.form.get('race_format') or '').strip()

    errors = []
    if not name:
        errors.append('Race name is required.')
    if not event_date:
        errors.append('Race date is required (YYYY-MM-DD).')
    if race_format not in VALID_RACE_FORMATS:
        errors.append('Pick a race format.')

    if errors:
        for msg in errors:
            flash(msg, 'danger')
        return redirect(url_for('onboarding.target_race'))

    new_distance_km = _parse_decimal_field(request.form, 'distance_km')
    new_total_elevation_gain_m = _parse_decimal_field(
        request.form, 'total_elevation_gain_m'
    )
    new_race_rules_summary = _parse_str_field(request.form, 'race_rules_summary')
    new_mandatory_gear_text = _parse_str_field(request.form, 'mandatory_gear_text')
    new_notes = _parse_str_field(request.form, 'notes')
    new_race_terrain = _parse_race_terrain(request.form)
    # D-73 Phase 5.2 walkthrough #1 + #2a (2026-05-21) — Mapbox-anchored race
    # location hidden inputs ride alongside the rest of the form (populated
    # client-side by the picker JS); race_url is a new athlete-typed input.
    from routes.race_events import (
        _extract_mapbox_locale_from_form,
        _parse_estimated_duration_hr,
        _parse_first_time_at_distance,
        _parse_goal_outcome,
        _parse_pack_weight_kg,
        _parse_previous_attempts,
        _parse_primary_metric,
        _parse_race_url,
    )
    new_locale_fields = _extract_mapbox_locale_from_form(request.form)
    new_race_url = _parse_race_url(request.form)
    new_estimated_duration_hr = _parse_estimated_duration_hr(request.form)
    new_primary_metric = _parse_primary_metric(request.form)
    new_framework_sport = _parse_str_field(request.form, 'framework_sport')
    parsed_discipline_filter = _parse_discipline_id_filter(request.form)
    # §H.2 goal context
    new_goal_outcome = _parse_goal_outcome(request.form)
    new_first_time_at_distance = _parse_first_time_at_distance(request.form)
    new_time_goal = _parse_str_field(request.form, 'time_goal')
    new_race_pack_weight_kg = _parse_pack_weight_kg(request.form)
    new_previous_attempts = _parse_previous_attempts(request.form)

    # D-73 Phase 5.2 Bucket C (i) — Mapbox-anchored race location is required
    # on save. The `[Skip]` button (target_race_skip) remains as the escape
    # valve for athletes who can't find their race in Mapbox.
    if not new_locale_fields['event_locale_mapbox_id']:
        flash('Pick a race location before saving.', 'danger')
        return redirect(url_for('onboarding.target_race'))

    target = _get_target_race_row(db, uid)
    # D-73 Phase 5.2 Bucket E.(b)-B2 — auto-clear discipline picks when
    # framework_sport changes (orphan cleanup; same semantic as
    # `routes/race_events.py:update_race`). Only fires on the UPDATE branch
    # (the new-target branch has no prior selection to invalidate).
    if target:
        prior_framework_sport = target.get('framework_sport')
        prior_discipline_filter = target.get('included_discipline_ids')
        if prior_framework_sport != new_framework_sport and prior_discipline_filter:
            new_discipline_filter = None
            flash(
                'Sport override changed — your discipline picks were cleared. '
                'Re-select them for the new sport.',
                'info',
            )
        else:
            new_discipline_filter = parsed_discipline_filter
    else:
        prior_framework_sport = None
        prior_discipline_filter = None
        new_discipline_filter = parsed_discipline_filter

    if target:
        update_race_event(
            db, uid, int(target['id']),
            name=name,
            event_date=event_date,
            race_format=race_format,
            distance_km=new_distance_km,
            total_elevation_gain_m=new_total_elevation_gain_m,
            estimated_duration_hr=new_estimated_duration_hr,
            primary_metric=new_primary_metric,
            race_rules_summary=new_race_rules_summary,
            mandatory_gear_text=new_mandatory_gear_text,
            event_locale_id=None,
            notes=new_notes,
            race_terrain=new_race_terrain,
            previous_attempts=new_previous_attempts,
            race_url=new_race_url,
            framework_sport=new_framework_sport,
            included_discipline_ids=new_discipline_filter,
            goal_outcome=new_goal_outcome,
            first_time_at_distance=new_first_time_at_distance,
            time_goal=new_time_goal,
            race_pack_weight_kg=new_race_pack_weight_kg,
            **new_locale_fields,
        )
        # D-66 §9 invalidation — same diff logic as routes/race_events.py
        # update_race; target row is already known. race_terrain routes to
        # brief-only (Layer 2B reads it but is uncached at the orchestrator
        # level; the Layer 4 brief is the cache-load-bearing artifact
        # downstream).
        # estimated_duration_hr feeds Layer 2E → fueling tiers consumed by
        # the brief + plan synthesis; rides the periodization-grade eviction
        # alongside event_date / race_format. Mirrors routes/race_events.py.
        periodization_changed = (
            target['event_date'] != event_date
            or target['race_format'] != race_format
            or target['estimated_duration_hr'] != new_estimated_duration_hr
            # §H.2 goal fields feed Layer 3B goal-viability + periodization-
            # shape selection; a change re-runs 3B and can shift the shape.
            # previous_attempts (Slice 2) drives 3B.dnf_recurrence_risk — same
            # grade, compared as-is (hydrated JSONB list of dicts). Mirrors
            # routes/race_events.py:update_race.
            or target.get('goal_outcome') != new_goal_outcome
            or target.get('first_time_at_distance') != new_first_time_at_distance
            or target.get('time_goal') != new_time_goal
            or target.get('race_pack_weight_kg') != new_race_pack_weight_kg
            or (target.get('previous_attempts') or []) != new_previous_attempts
        )
        prior_terrain = target.get('race_terrain') or []
        prior_race_url = target.get('race_url')
        prior_mapbox_id = target.get('event_locale_mapbox_id')
        # D-73 Phase 5.2 Bucket E.(b) — framework_sport override change on
        # the target row → wider Layer 2A eviction (supersets periodization
        # + brief-only). Mirrors `routes/race_events.py:update_race`.
        framework_sport_changed = prior_framework_sport != new_framework_sport
        # D-73 Phase 5.2 Bucket E.(b)-B2 — included_discipline_ids change
        # uses same `layer2a` policy as framework_sport (both reshape Layer
        # 2A's discipline output). Subsumed when framework_sport drives
        # the auto-clear; fires standalone when athlete edits picks alone.
        discipline_filter_changed = (
            prior_discipline_filter != new_discipline_filter
        )
        brief_only_changed = (
            target['distance_km'] != new_distance_km
            or target['total_elevation_gain_m'] != new_total_elevation_gain_m
            or target['race_rules_summary'] != new_race_rules_summary
            or target['mandatory_gear_text'] != new_mandatory_gear_text
            or target['notes'] != new_notes
            or prior_terrain != new_race_terrain
            or prior_race_url != new_race_url
            or prior_mapbox_id != new_locale_fields['event_locale_mapbox_id']
            or target['primary_metric'] != new_primary_metric
        )
        if framework_sport_changed:
            evict_on_target_event_framework_sport_change(db, uid)
        elif discipline_filter_changed:
            evict_on_target_event_included_discipline_ids_change(db, uid)
        elif periodization_changed:
            evict_on_target_event_periodization_change(db, uid)
        elif brief_only_changed:
            evict_on_target_event_brief_field_change(db, uid)
        flash('Target race updated.', 'success')
    else:
        create_race_event(
            db, uid,
            name=name,
            event_date=event_date,
            race_format=race_format,
            distance_km=new_distance_km,
            total_elevation_gain_m=new_total_elevation_gain_m,
            estimated_duration_hr=new_estimated_duration_hr,
            primary_metric=new_primary_metric,
            race_rules_summary=new_race_rules_summary,
            mandatory_gear_text=new_mandatory_gear_text,
            is_target_event=True,
            notes=new_notes,
            race_terrain=new_race_terrain,
            previous_attempts=new_previous_attempts,
            race_url=new_race_url,
            framework_sport=new_framework_sport,
            included_discipline_ids=new_discipline_filter,
            goal_outcome=new_goal_outcome,
            first_time_at_distance=new_first_time_at_distance,
            time_goal=new_time_goal,
            race_pack_weight_kg=new_race_pack_weight_kg,
            **new_locale_fields,
        )
        # A fresh target row was created. Layer 3B's mode flips from
        # open_ended → event; periodization-grade eviction covers the
        # plan_create + plan_refresh + race_week_brief entry points.
        evict_on_target_event_periodization_change(db, uid)
        flash(f'Target race "{name}" saved.', 'success')

    # Route locales are offered on every event type (optional). The step
    # has its own skip/continue, so single-day athletes can pass through
    # without entering any — but the option is no longer hidden from them.
    return redirect(url_for('onboarding.route_locales'))


@bp.route('/target-race/skip', methods=['POST'])
def target_race_skip():
    """Skip Step 3c with no target race set.

    Writes an `'target_race_skipped'` account_nudge so the athlete sees
    a soft reminder to come back and pick a target race later. Mirrors
    the D-58 `/onboarding/skip` pattern, except a nudge IS recorded
    here — race-week brief synthesis is gated on a target race existing,
    so the absence is load-bearing for downstream coaching.
    """
    db = get_db()
    uid = current_user_id()
    _write_account_nudge(db, uid, 'target_race_skipped')
    db.commit()
    flash(
        "You can add a target race any time from Profile → Race events.",
        'info',
    )
    return redirect(_POST_STEP3C_TARGET)


# ---------------------------------------------------------------------------
# Step 3d — Route locales (D-66 §H.4) — offered on every event type, optional
# ---------------------------------------------------------------------------


@bp.route('/route-locales', methods=['GET'])
def route_locales():
    """Render the v5 §H.4 route-locale list (Step 3d).

    Offered for any target race_events row regardless of `race_format`;
    always optional (the Skip/Continue controls let the athlete pass
    through without entering any). Empty state explains the value of
    filling in route locales; populated state lists current rows with
    per-row Delete buttons and a default sequence_idx pre-populated as
    `len(existing)+1`. Equipment per locale is intentionally deferred to
    the profile UI per design §6.3 — onboarding captures the route graph
    only; equipment entry happens on the relaxed timeline.
    """
    db = get_db()
    uid = current_user_id()

    target = _get_target_race_row(db, uid)
    if not target:
        # Athlete reached Step 3d without a target race row — bounce back
        # to Step 3c rather than render an empty form against no parent.
        flash(
            'Pick a target race first before adding route locales.',
            'info',
        )
        return redirect(url_for('onboarding.target_race'))

    race_event_id = int(target['id'])
    race_locales = list_route_locales(db, race_event_id)

    return render_template(
        'onboarding/route_locales.html',
        target=target,
        race_locales=race_locales,
        next_sequence_idx=len(race_locales) + 1,
        route_locale_roles=VALID_ROUTE_LOCALE_ROLES,
        post_step3d_target=_POST_STEP3D_TARGET,
    )


@bp.route('/route-locales/add', methods=['POST'])
def route_locales_add():
    """Add a single race_route_locales row + re-render the §H.4 list."""
    db = get_db()
    uid = current_user_id()

    target = _get_target_race_row(db, uid)
    if not target:
        abort(404)
    race_event_id = int(target['id'])

    role = (request.form.get('role') or '').strip()
    sequence_idx = _parse_int_field(request.form, 'sequence_idx')
    name = _parse_str_field(request.form, 'name')

    errors = []
    if not name:
        errors.append('Locale name is required.')
    if role not in VALID_ROUTE_LOCALE_ROLES:
        errors.append('Pick a route-locale role.')
    if sequence_idx is None or sequence_idx < 1:
        errors.append('Sequence number must be 1 or greater.')

    if errors:
        for msg in errors:
            flash(msg, 'danger')
        return redirect(url_for('onboarding.route_locales'))

    try:
        add_route_locale(
            db, race_event_id,
            role=role,
            sequence_idx=sequence_idx,
            name=name,
            mile_marker=_parse_decimal_field(request.form, 'mile_marker'),
            notes=_parse_str_field(request.form, 'notes'),
        )
        # Parent race is the target by construction (`_get_target_race_row`
        # filters on `is_target_event=TRUE`); brief-only eviction per §9.
        evict_on_target_event_brief_field_change(db, uid)
        flash(f'Route locale "{name}" added.', 'success')
    except Exception as e:
        # Most likely UNIQUE (race_event_id, sequence_idx) collision.
        flash(f'Could not add route locale: {e}', 'danger')

    return redirect(url_for('onboarding.route_locales'))


@bp.route('/route-locales/<int:route_locale_id>/delete', methods=['POST'])
def route_locales_delete(route_locale_id):
    """Delete a single race_route_locales row + re-render the §H.4 list."""
    db = get_db()
    uid = current_user_id()

    target = _get_target_race_row(db, uid)
    if not target:
        abort(404)
    race_event_id = int(target['id'])

    delete_route_locale(db, race_event_id, route_locale_id)
    # Parent is the target by construction; brief-only eviction per §9.
    evict_on_target_event_brief_field_change(db, uid)
    flash('Route locale removed.', 'info')
    return redirect(url_for('onboarding.route_locales'))


@bp.route('/route-locales/continue', methods=['POST'])
def route_locales_continue():
    """Advance from Step 3d to the profile form.

    Writes an `'route_locales_incomplete'` account_nudge when the athlete
    continues with fewer than 2 route locales (recommended minimum is
    start + finish per design §4.2 first/last-role-anchors invariant).
    The nudge is the same shape as `target_race_skipped`; downstream
    surfaces can show a soft reminder to flesh out the route later.
    """
    db = get_db()
    uid = current_user_id()

    target = _get_target_race_row(db, uid)
    if not target:
        abort(404)
    race_event_id = int(target['id'])

    race_locales = list_route_locales(db, race_event_id)
    if len(race_locales) < 2:
        _write_account_nudge(db, uid, 'route_locales_incomplete')
        db.commit()
        flash(
            "Add more route locales any time from Profile → Race events.",
            'info',
        )
    else:
        flash('Route locales saved.', 'success')

    return redirect(_POST_STEP3D_TARGET)


@bp.route('/route-locales/skip', methods=['POST'])
def route_locales_skip():
    """Skip Step 3d entirely. Writes the `'route_locales_incomplete'`
    nudge unconditionally so a return visit can surface the reminder.
    """
    db = get_db()
    uid = current_user_id()
    _write_account_nudge(db, uid, 'route_locales_incomplete')
    db.commit()
    flash(
        "You can add route locales any time from Profile → Race events.",
        'info',
    )
    return redirect(_POST_STEP3D_TARGET)
