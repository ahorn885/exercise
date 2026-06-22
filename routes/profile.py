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

import os
from datetime import datetime

import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session

from datetime import date

import mfa
from database import get_db
from plan_nutrition_repo import load_plan_nutrition_by_version
from routes.auth import (
    current_user_id, _hash_password, _check_password, _password_strength_errors,
    generate_api_token, send_verification_email, send_password_changed_email,
)
from email_helper import send_email
from email_templates import render_email, account_security_url, format_timestamp
from athlete import (
    PROFILE_FIELDS, PREFILL_ELIGIBLE_FIELDS,
    DOUBLES_FEASIBLE_CHOICES, TWO_A_DAY_CHOICES,
    DIETARY_PATTERN_CHOICES, FUELING_FORMAT_CHOICES,
    CAFFEINE_TOLERANCE_CHOICES, CAFFEINE_RACE_DAY_STRATEGY_CHOICES,
    SALT_ELECTROLYTE_TOLERANCE_CHOICES, EXPERIENCE_LEVEL_CHOICES,
    get_athlete_profile, upsert_athlete_profile,
    get_daily_availability_windows, upsert_daily_availability_windows,
)
from units import (
    UNIT_PREFERENCE_CHOICES, DEFAULT_UNIT_PREFERENCE,
    normalize_unit_preference, entered_weight_to_kg, display_weight,
    weight_unit_label, entered_height_to_cm, display_height, height_unit_label,
)
from athlete_discipline_weighting_repo import (
    DisciplineWeightingError,
    evict_layer1_on_discipline_weighting_change,
    get_discipline_weighting,
    load_discipline_catalog,
    replace_discipline_weighting,
)
from athlete_crafts_repo import (
    CraftSelectionError,
    evict_layer1_on_crafts_change,
    get_athlete_crafts,
    load_craft_catalog,
    replace_athlete_crafts,
)
from athlete_event_windows_repo import (
    EventWindowError,
    OVERRIDE_TYPES,
    add_event_window,
    delete_event_window,
    evict_plan_caches_on_event_windows_change,
    load_event_windows,
)
from athlete_skill_toggles_repo import (
    evict_layer1_on_skill_toggle_change,
    get_athlete_skill_toggles,
    load_active_skill_capability_toggle_vocab,
    parse_skill_form,
    upsert_athlete_skill_toggles,
)
from race_events_repo import list_athlete_race_events
from athlete_supplements_repo import (
    load_supplement_vocab, vocab_index, list_athlete_supplements,
    add_athlete_supplement, delete_athlete_supplement,
    clean_frequency, clean_timing,
    SUPPLEMENT_FREQUENCIES, SUPPLEMENT_TIMINGS,
    FREQUENCY_LABELS, TIMING_LABELS,
)
from health_inputs_repo import (
    list_health_conditions, add_health_condition, delete_health_condition,
    list_medications, add_medication, delete_medication, clean_severity,
    SYSTEM_CATEGORY_CHOICES, MEDICATION_CLASS_CHOICES,
    SYSTEM_CATEGORY_LABELS, MEDICATION_CLASS_LABELS,
    CONDITIONS_BY_CATEGORY,
)
from pack_load_repo import (
    list_pack_loads, add_pack_load, delete_pack_load,
)
from routes import account_merge
from routes import provider_auth as pa
from routes import provider_identity as pi


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
    ('strava', 'Strava', 'strava.oauth_start'),
    ('whoop', 'Whoop', 'whoop.oauth_start'),
    ('wahoo', 'Wahoo', 'wahoo.oauth_start'),
    ('oura', 'Oura', 'oura.oauth_start'),
    ('rwgps', 'Ride With GPS', 'ride_with_gps.oauth_start'),
    ('trainingpeaks', 'TrainingPeaks', 'trainingpeaks.oauth_start'),
)

# Client-id env var per provider. Its presence in the environment gates
# whether the connect surfaces offer a live "Connect" button: when unset the
# provider renders "Not available yet" instead of a Connect that dead-ends in
# the provider's `oauth_start` abort(503) (the credentials aren't registered
# yet). Names match each routes/<provider>.py oauth_start lookup
# (rwgps/trainingpeaks are irregular). Self-healing — setting STRAVA_CLIENT_ID
# flips Strava back to a live Connect with no code change.
_PROVIDER_CLIENT_ID_ENV = {
    'coros': 'COROS_CLIENT_ID',
    'polar': 'POLAR_CLIENT_ID',
    'strava': 'STRAVA_CLIENT_ID',
    'whoop': 'WHOOP_CLIENT_ID',
    'wahoo': 'WAHOO_CLIENT_ID',
    'oura': 'OURA_CLIENT_ID',
    'rwgps': 'RWGPS_CLIENT_ID',
    'trainingpeaks': 'TP_CLIENT_ID',
}


def _coerce_date(value):
    """Best-effort scope-date coercion; tolerates date objects, ISO strings,
    or None (mirrors routes/plans.py bucketing for the fake-cursor tests)."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _load_active_plan_nutrition(db, uid):
    """The athlete's currently-live AI plan + its nutrition artifact, if any.

    Active mirrors routes/plans.list_plans: `ready`, not superseded, not
    completed, not archived, and scope spans today. Returns
    `(plan_version_id, PlanNutrition)` or `(None, None)`. Advisory — wholly
    best-effort, so a fault here never breaks the profile page (the standing
    protocol still renders)."""
    try:
        rows = db.execute(
            "SELECT id, scope_start_date, scope_end_date, completed_at, archived_at "
            "FROM plan_versions WHERE user_id = ? "
            "AND generation_status = 'ready' AND superseded_at IS NULL "
            "ORDER BY created_at DESC",
            (uid,),
        ).fetchall()
        today = date.today()
        for r in rows:
            if r['completed_at'] is not None or r['archived_at'] is not None:
                continue
            start = _coerce_date(r['scope_start_date'])
            end = _coerce_date(r['scope_end_date'])
            if start is not None and start > today:
                continue
            if end is not None and end < today:
                continue
            return r['id'], load_plan_nutrition_by_version(db, r['id'])
    except Exception as exc:  # noqa: BLE001 — advisory must not break the page
        print(f"_load_active_plan_nutrition failed for uid={uid} (non-fatal): {exc}")
    return None, None

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
    # Which providers are an active sign-in method (provider_identity), so the
    # management screen can offer "Remove sign-in" distinctly from "Disconnect"
    # (#251 §6.3). Defensive: provider_identity is PG-only; on local SQLite the
    # table is absent — treat as no sign-in links rather than crash the tab.
    try:
        signin_slugs = {
            r['provider'] for r in db.execute(
                'SELECT provider FROM provider_identity WHERE user_id = ?', (uid,)
            ).fetchall()
        }
    except Exception:
        signin_slugs = set()
    if return_to is None:
        return_to = url_for('profile.edit') + '?tab=connections'
    out = []
    for slug, label, endpoint in CONNECTION_PROVIDERS:
        row = by_provider.get(slug)
        status = (row or {}).get('status')
        display_label, badge_class = _STATUS_DISPLAY.get(
            status, ('Not connected', 'bg-light text-dark border')
        )
        env_var = _PROVIDER_CLIENT_ID_ENV.get(slug)
        is_configured = bool(env_var and os.environ.get(env_var))
        out.append({
            'slug': slug,
            'label': label,
            'row': row,
            'status': status,
            'status_label': display_label,
            'badge_class': badge_class,
            'is_connected': status == pa.STATUS_ACTIVE,
            'is_configured': is_configured,
            'is_signin': slug in signin_slugs,
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

    # #887 — Locations is consolidated under the Log nav group and no longer
    # has a profile tab. Redirect any lingering ?tab=locations links/bookmarks
    # to the canonical standalone surface.
    if request.method == 'GET' and request.args.get('tab') == 'locations':
        return redirect(url_for('locales.list_profiles'))

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

        # Same render-time-unit pattern for height — entered in `in` for
        # imperial, `cm` for metric, stored canonical cm.
        height_input_unit_pref = normalize_unit_preference(
            _str('height_input_unit')
        ) or submitted_unit_pref
        entered_height = _num('height')
        height_cm = entered_height_to_cm(entered_height, height_input_unit_pref)

        prefill_values = {
            'body_weight_kg': body_weight_kg,
            'hrmax_bpm': _num('hrmax_bpm', cast=int),
            'lactate_threshold_hr_bpm': _num('lactate_threshold_hr_bpm', cast=int),
            'vo2max': _num('vo2max'),
            'cycling_ftp_w': _num('cycling_ftp_w', cast=int),
        }
        # #304 — self-select band; reject a tampered value to the closed set.
        experience_level = _str('experience_level')
        if experience_level not in EXPERIENCE_LEVEL_CHOICES:
            experience_level = None
        upsert_athlete_profile(
            db, uid,
            date_of_birth=_str('date_of_birth'),
            sex=_str('sex'),
            height_cm=height_cm,
            primary_sport=_str('primary_sport'),
            weekly_hours_target=_num('weekly_hours_target'),
            coach_notes=_str('coach_notes'),
            experience_level=experience_level,
            unit_preference=submitted_unit_pref,
            # #894 — the nutrition / fueling / altitude protocol moved to its own
            # Fuel & health tab (profile.save_nutrition); supplements moved to
            # structured records (athlete_supplements). None of those columns are
            # passed here, so a basics-only save leaves them untouched (not wiped).
            **prefill_values,
        )
        _record_self_report_provenance(db, uid, prefill_values)
        db.commit()
        flash('Profile saved.', 'success')
        return redirect(url_for('profile.edit'))

    profile = get_athlete_profile(db, uid) or {}
    memory = _load_memory(db, uid)

    # #894 — the Schedule surface left the profile tab strip for its own page
    # under "Train" (profile.schedule); per-day windows + doubles / two-a-day
    # context now load there, not here.

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

    # X2 — discipline-weighting picker (Athlete tab). Catalog = all potential
    # disciplines; weighting = the athlete's current split (empty → unset).
    discipline_catalog = load_discipline_catalog(db)
    discipline_weighting = get_discipline_weighting(db, uid)

    # 2c.2b (#540) — owned-craft picker (Athlete tab). Catalog = the closed
    # bike/paddle craft enums; current = the athlete's saved crafts.
    craft_catalog = load_craft_catalog()
    athlete_crafts = get_athlete_crafts(db, uid)

    # #469 — body weight is stored canonical kg; render it in the athlete's
    # chosen display unit so the form field round-trips cleanly. `profile` is
    # mutated in place because it's the dict the template reads.
    unit_pref = normalize_unit_preference(profile.get('unit_preference'))
    profile['unit_preference'] = unit_pref
    profile['body_weight_display'] = display_weight(profile.get('body_weight_kg'), unit_pref)
    profile['weight_unit_label'] = weight_unit_label(unit_pref)
    profile['height_display'] = display_height(profile.get('height_cm'), unit_pref)
    profile['height_unit_label'] = height_unit_label(unit_pref)

    # Plan-specific nutrition is surfaced only when a plan is live (hidden
    # otherwise). The standing protocol below always renders from `profile`.
    active_plan_id, plan_nutrition = _load_active_plan_nutrition(db, uid)

    # 2E-6 — structured supplement capture: the athlete's records + the Layer 0
    # vocab that powers the add-supplement picker.
    supplements = list_athlete_supplements(db, uid)
    supplement_vocab = load_supplement_vocab(db)
    # §B health inputs — feed the Layer 2E contraindication screening.
    health_conditions = list_health_conditions(db, uid)
    medications = list_medications(db, uid)
    # §C pack-load history — load-carriage base, summarized into Layer 3B.
    pack_loads = list_pack_loads(db, uid)

    from datetime import datetime as _dt
    return render_template(
        'profile/edit.html',
        profile=profile,
        active_plan_id=active_plan_id,
        plan_nutrition=plan_nutrition,
        supplements=supplements,
        supplement_vocab=supplement_vocab,
        health_conditions=health_conditions,
        medications=medications,
        pack_loads=pack_loads,
        system_category_choices=SYSTEM_CATEGORY_CHOICES,
        conditions_by_category=CONDITIONS_BY_CATEGORY,
        medication_class_choices=MEDICATION_CLASS_CHOICES,
        system_category_labels=SYSTEM_CATEGORY_LABELS,
        medication_class_labels=MEDICATION_CLASS_LABELS,
        supplement_frequencies=SUPPLEMENT_FREQUENCIES,
        supplement_timings=SUPPLEMENT_TIMINGS,
        frequency_labels=FREQUENCY_LABELS,
        timing_labels=TIMING_LABELS,
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
        dietary_pattern_choices=DIETARY_PATTERN_CHOICES,
        fueling_format_choices=FUELING_FORMAT_CHOICES,
        caffeine_tolerance_choices=CAFFEINE_TOLERANCE_CHOICES,
        caffeine_race_day_strategy_choices=CAFFEINE_RACE_DAY_STRATEGY_CHOICES,
        salt_electrolyte_tolerance_choices=SALT_ELECTROLYTE_TOLERANCE_CHOICES,
        experience_level_choices=EXPERIENCE_LEVEL_CHOICES,
        skill_toggle_defs=skill_toggle_defs,
        skill_toggle_states=skill_toggle_states,
        discipline_catalog=discipline_catalog,
        discipline_weighting=discipline_weighting,
        craft_catalog=craft_catalog,
        athlete_crafts=athlete_crafts,
        # Used by the template to render an "Expired" badge without
        # round-tripping the timestamp through a Jinja-only comparison.
        now_iso=_dt.utcnow().isoformat(timespec='seconds'),
    )


@bp.route('/schedule', methods=['GET'])
def schedule():
    """Render the standing Schedule & Availability surface (#894).

    Lifted out of the athlete-profile tab strip onto its own page under
    "Train" in the sidebar. Reuses the shared `_schedule_form.html` partial
    (also used by onboarding Step 3b) so the two capture surfaces stay in
    lockstep; the matching POST handler is `save_schedule` on the same URL.
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
        'profile/schedule.html',
        days=days,
        doubles_feasible=doubles,
        doubles_choices=DOUBLES_FEASIBLE_CHOICES,
        two_a_day_preference=two_a_day,
        two_a_day_choices=TWO_A_DAY_CHOICES,
        peak_sessions_max=profile.get('peak_sessions_max'),
    )


@bp.route('/schedule', methods=['POST'])
def save_schedule():
    """Persist the v5 §G schedule form submitted from `/profile/schedule`.

    Identical write semantics to `onboarding.schedule_save` — per-day windows
    replace existing rows, athlete_profile carries the `doubles_feasible`
    toggle — differing only in the redirect target (stays on the standalone
    Schedule page instead of forwarding to the §A profile entry).

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

    return redirect(url_for('profile.schedule'))


@bp.route('/skills', methods=['POST'])
def save_skills():
    """Persist the Skills form submitted from the Gear & skills tab
    (`/profile?tab=gear`).

    Mirrors the onboarding-step write path: parse the form against the
    canonical vocab, UPSERT one row per toggle, evict Layer 1 caches.
    Lands the athlete back on the Gear & skills tab.
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
    return redirect(url_for('profile.edit', tab='gear'))


@bp.route('/disciplines', methods=['POST'])
def save_disciplines():
    """Persist the discipline-weighting form (Athlete tab).

    All-or-nothing: the athlete selects + weights any subset of the
    discipline catalog; non-zero weights must sum to 100, or the whole set is
    cleared (revert to Layer 2A system defaults). Form fields are `dw_<id>`
    carrying the percent. Mirrors `save_skills`' parse → write → evict-Layer-1
    path. Stored `discipline_slug` holds the canonical `discipline_id`.
    """
    db = get_db()
    uid = current_user_id()
    catalog_ids = {d['id'] for d in load_discipline_catalog(db)}
    weights: dict[str, int] = {}
    for did in catalog_ids:
        raw = (request.form.get(f'dw_{did}') or '').strip()
        if not raw:
            continue
        try:
            weights[did] = int(float(raw))
        except (ValueError, TypeError):
            flash(f'Invalid weight for {did}.', 'error')
            return redirect(url_for('profile.edit', tab='athlete'))
    try:
        replace_discipline_weighting(db, uid, weights)
    except DisciplineWeightingError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('profile.edit', tab='athlete'))
    db.commit()
    evict_layer1_on_discipline_weighting_change(db, uid)
    flash('Discipline weighting saved.', 'success')
    return redirect(url_for('profile.edit', tab='athlete'))


@bp.route('/crafts', methods=['POST'])
def save_crafts():
    """Persist the owned-craft form (Gear & skills tab) — 2c.2b (#540).

    The athlete checks the bike types + paddle crafts they own; each family is
    replace-all (unchecked = not owned). Slugs are validated against the closed
    enums, then the discipline-baseline craft columns are upserted. Mirrors
    `save_disciplines`' parse → write → evict-Layer-1 path. These crafts feed
    the X1b.3b craft-substitution narrowing in plan generation.
    """
    db = get_db()
    uid = current_user_id()
    try:
        replace_athlete_crafts(
            db,
            uid,
            bike_types=request.form.getlist('bike_types'),
            paddle_crafts=request.form.getlist('paddle_crafts'),
        )
    except CraftSelectionError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('profile.edit', tab='gear'))
    db.commit()
    evict_layer1_on_crafts_change(db, uid)
    flash('Gear saved.', 'success')
    return redirect(url_for('profile.edit', tab='gear'))


@bp.route('/nutrition', methods=['POST'])
def save_nutrition():
    """Persist the standing nutrition / fueling / altitude protocol — the
    Fuel & health tab (#894).

    Carved out of the main profile save so these fields can live on their own
    tab alongside supplements without a partial POST wiping the athlete-tab
    baselines (`upsert_athlete_profile` only touches the columns it's handed).
    Coercion mirrors `profile.edit`; lands back on the Fuel & health tab.
    """
    db = get_db()
    uid = current_user_id()
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

    def _csv(key, allowed):
        # Multi-select checkbox group -> comma-separated storage. Filter to the
        # known vocab so a tampered POST can't store junk tokens.
        picked = [v for v in f.getlist(key) if v in allowed]
        return ','.join(picked) or None

    # Altitude acclimatization is a tri-state select: yes / no / unset.
    # Map to BOOLEAN | None; anything outside the pair stays None.
    _alt_raw = _str('altitude_acclimatization_history')
    altitude_acclimatization_history = (
        True if _alt_raw == 'yes' else False if _alt_raw == 'no' else None
    )
    upsert_athlete_profile(
        db, uid,
        # §I.2 nutrition & fueling protocol.
        dietary_pattern=_csv('dietary_pattern', DIETARY_PATTERN_CHOICES),
        fueling_format_preference=_csv(
            'fueling_format_preference', FUELING_FORMAT_CHOICES),
        caffeine_tolerance=_str('caffeine_tolerance'),
        caffeine_daily_mg_estimate=_num('caffeine_daily_mg_estimate', cast=int),
        caffeine_race_day_strategy=_str('caffeine_race_day_strategy'),
        salt_electrolyte_tolerance=_str('salt_electrolyte_tolerance'),
        gi_triggers_known=_str('gi_triggers_known'),
        # §I altitude exposure — acclimatization history (tri-state), highest
        # sustained exposure, and how many distinct exposures.
        altitude_acclimatization_history=altitude_acclimatization_history,
        altitude_max_exposure_m=_num('altitude_max_exposure_m', cast=int),
        altitude_exposure_count=_num('altitude_exposure_count', cast=int),
    )
    db.commit()
    flash('Nutrition & fueling saved.', 'success')
    return redirect(url_for('profile.edit', tab='health'))


# ─── Event windows — Slice 1 (#581 WS-H) ─────────────────────────────────────
# Minimal capture: list + add + delete of date-bounded SUBTRACTIVE home windows
# (`indoor_only` / `locale_unavailable`). Plan generation date-segments the plan
# span against these and resolves the existing feasibility cascade per reduced
# environment. (Nav-linking shipped in Slice 5a; the plan-gen review-panel
# round-trip — `?return_to` below — is Slice 5b.)


def _safe_local_path(value):
    """A `?return_to` / form return path is honored only when it's a local,
    same-site path — mirrors `routes/locales._stash_return_to`'s safety check so
    the plan-gen round-trip can't be turned into an open redirect."""
    if value and value.startswith('/') and not value.startswith('//'):
        return value
    return None


def _event_windows_return_label(return_to):
    """Label for the editor's 'back to …' banner, derived from the round-trip
    origin so it reads right whether the athlete arrived from plan generation
    (#608 item 1) or from onboarding setup (#608 item 3). Consistent across the
    add/delete redirects, which preserve return_to but not a separate label."""
    if return_to and return_to.startswith('/onboarding'):
        return 'setup'
    return 'plan generation'


def _event_windows_redirect(return_to):
    """Redirect back to the event-windows page, PRESERVING a safe `return_to` so
    the Slice-5b 'back to plan generation' link survives across an add/delete
    write (each of which redirects here). `url_for` drops a None query arg, so a
    standalone visit (no round-trip) lands on the bare page unchanged."""
    return redirect(
        url_for('profile.event_windows', return_to=_safe_local_path(return_to))
    )


# Form-state preservation (#608 item 2, WS-H) — creating a not-yet-saved away
# destination mid-capture round-trips out to /locales/new and back; without this
# the half-filled window form would reset (strict CSP forbids the inline-JS
# client-side fix). Stash the in-progress form in the session, consumed once on
# the next render, so the round-trip returns to a repopulated form. Mirrors the
# locale flow's own session-stashed return_to (routes/locales._stash_return_to).
_EVENT_WINDOW_DRAFT = 'event_window_draft'


def _stash_event_window_draft(form):
    """Persist the in-progress add-window form across a /locales/new round-trip."""
    from flask import session as flask_session
    flask_session[_EVENT_WINDOW_DRAFT] = {
        'start_date': (form.get('start_date') or '').strip(),
        'end_date': (form.get('end_date') or '').strip(),
        'override_type': (form.get('override_type') or '').strip(),
        'unavailable_locale': (form.get('unavailable_locale') or '').strip(),
        'away_locale': (form.get('away_locale') or '').strip(),
        'brought_craft': form.getlist('brought_craft'),
        'volume_pct': (form.get('volume_pct') or '').strip(),
        'notes': (form.get('notes') or '').strip(),
    }


def _pop_event_window_draft():
    """Return + clear any stashed add-window draft (consumed once on render)."""
    from flask import session as flask_session
    return flask_session.pop(_EVENT_WINDOW_DRAFT, None)


@bp.route('/event-windows')
def event_windows():
    """List + capture the athlete's event windows."""
    db = get_db()
    uid = current_user_id()
    windows = load_event_windows(db, uid)
    locales = [
        r['locale']
        for r in db.execute(
            "SELECT locale FROM locale_profiles WHERE user_id = ? ORDER BY locale",
            (uid,),
        ).fetchall()
    ]
    return_to = _safe_local_path(request.args.get('return_to'))
    return render_template(
        'profile/event_windows.html',
        windows=windows,
        locales=locales,
        override_types=OVERRIDE_TYPES,
        # Slice 4 (#581 WS-H) — away-craft capture: the brought-craft (c) picker
        # catalog. (The standing craft↔locale (b) capture moved to the per-locale
        # edit page in Slice 5.)
        craft_catalog=load_craft_catalog(),
        # Slice 5b (#581 WS-H) — when the athlete reached this page from the
        # plan-gen review panel (#608 item 1) or onboarding setup (#608 item 3),
        # thread the origin path through so the add/delete forms preserve it and
        # the "back to <origin>" link can round-trip them back where they started.
        return_to=return_to,
        return_to_label=_event_windows_return_label(return_to),
        # #608 item 2 — repopulate the add-window form after an inline
        # new-location round-trip (consumed once); None on a normal visit.
        draft=_pop_event_window_draft(),
    )


@bp.route('/event-windows/add', methods=['POST'])
def add_event_window_route():
    """Validate + persist one event window (the repo enforces date order +
    override/locale rules), then evict the plan-gen caches it feeds."""
    db = get_db()
    uid = current_user_id()
    return_to = request.form.get('return_to')
    try:
        start = date.fromisoformat((request.form.get('start_date') or '').strip())
        end = date.fromisoformat((request.form.get('end_date') or '').strip())
    except ValueError:
        flash('Enter valid start and end dates.', 'error')
        return _event_windows_redirect(return_to)
    # Slice 6 (#593) — the reduced-volume control captures a PERCENT of a normal
    # training day; the repo stores the fraction (0,1). Only meaningful for the
    # reduced_volume type (the repo ignores it for every other type).
    vol_raw = (request.form.get('volume_pct') or '').strip()
    volume_pct = None
    if vol_raw:
        try:
            volume_pct = float(vol_raw) / 100.0
        except ValueError:
            flash('Enter a valid reduced-volume percentage.', 'error')
            return _event_windows_redirect(return_to)
    try:
        add_event_window(
            db,
            uid,
            start_date=start,
            end_date=end,
            override_type=(request.form.get('override_type') or '').strip(),
            unavailable_locale=(request.form.get('unavailable_locale') or None),
            away_locale=(request.form.get('away_locale') or None),
            brought_craft=request.form.getlist('brought_craft'),
            volume_pct=volume_pct,
            notes=(request.form.get('notes') or '').strip(),
        )
    except EventWindowError as exc:
        flash(str(exc), 'error')
        return _event_windows_redirect(return_to)
    db.commit()
    evict_plan_caches_on_event_windows_change(db, uid)
    flash('Event window saved.', 'success')
    return _event_windows_redirect(return_to)


@bp.route('/event-windows/<int:window_id>/delete', methods=['POST'])
def delete_event_window_route(window_id):
    """Delete one of the athlete's windows (user-scoped) + evict plan caches."""
    db = get_db()
    uid = current_user_id()
    delete_event_window(db, uid, window_id)
    db.commit()
    evict_plan_caches_on_event_windows_change(db, uid)
    flash('Event window removed.', 'success')
    return _event_windows_redirect(request.form.get('return_to'))


@bp.route('/event-windows/new-locale', methods=['POST'])
def event_window_new_locale_route():
    """Hand off to the locale builder to create a not-yet-saved away destination
    mid-window-capture, preserving the in-progress form (#608 item 2). Stashes
    the add-window draft (repopulated on return), then redirects to /locales/new
    with a return_to back here that itself carries any plan-gen return_to."""
    uid = current_user_id()
    _stash_event_window_draft(request.form)
    return_to = _safe_local_path(request.form.get('return_to'))
    back = url_for('profile.event_windows', return_to=return_to)
    print(
        f"event_window_draft_stash: user={uid} "
        f"override={(request.form.get('override_type') or '').strip()!r} "
        f"return_to={return_to!r} -> locales.new_locale"
    )
    return redirect(url_for('locales.new_locale', return_to=back))


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


@bp.route('/connections/<provider>/unlink', methods=['POST'])
def unlink_provider_signin(provider):
    """Remove a provider as a SIGN-IN method (#251 §6.3) — distinct from
    `disconnect_provider`, which stops data sync. Removing the athlete's last
    login method is refused (self-lockout guard, design decision #9): sync can
    keep running on a provider you can no longer log in with, but you must
    always retain at least one way in. Scoped on `current_user_id()`; unknown
    slugs 404.
    """
    if provider not in {slug for slug, _label, _endpoint in CONNECTION_PROVIDERS}:
        abort(404)
    db = get_db()
    label = next(
        (lbl for slug, lbl, _endpoint in CONNECTION_PROVIDERS if slug == provider),
        provider,
    )
    ok, reason = pi.unlink_identity(db, current_user_id(), provider)
    if not ok and reason == 'last_method':
        flash(f"Can't remove {label} sign-in — it's your only way to log in. "
              f'Set a password first, then try again.', 'warning')
    elif ok:
        flash(f'{label} sign-in removed. Data sync is unaffected.', 'info')
    else:
        flash(f'{label} was not a sign-in method.', 'info')
    return redirect(url_for('connections.hub', tab='sources'))


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


@bp.route('/supplement/add', methods=['POST'])
def add_supplement():
    """Add one structured supplement record. The selection is validated against
    the Layer 0 vocab and the display fields (name/category) are taken from
    there — a crafted POST can't store an unknown id or a spoofed name."""
    db = get_db()
    uid = current_user_id()
    supplement_id = (request.form.get('supplement_id') or '').strip()
    index = vocab_index(db)
    vocab_row = index.get(supplement_id)
    if vocab_row is None:
        flash('Unknown supplement.', 'danger')
        return redirect(url_for('profile.edit', tab='health'))

    def _opt(key):
        return (request.form.get(key) or '').strip() or None

    add_athlete_supplement(
        db, uid,
        supplement_id=supplement_id,
        canonical_name=vocab_row['canonical_name'],
        category=vocab_row.get('category'),
        dose=_opt('dose'),
        # frequency/timing are closed vocabs — drop anything not in the set so a
        # tampered POST stores NULL rather than a junk token.
        frequency=clean_frequency(request.form.get('frequency')),
        timing=clean_timing(request.form.get('timing')),
        notes=_opt('notes'),
    )
    db.commit()
    flash('Supplement added.', 'success')
    return redirect(url_for('profile.edit', tab='health'))


@bp.route('/supplement/<int:supp_id>/delete', methods=['POST'])
def delete_supplement(supp_id):
    """Remove one supplement record. Scoped on user_id — a crafted POST can't
    reach another athlete's row."""
    db = get_db()
    delete_athlete_supplement(db, current_user_id(), supp_id)
    db.commit()
    flash('Supplement removed.', 'info')
    return redirect(url_for('profile.edit', tab='health'))


@bp.route('/condition/add', methods=['POST'])
def add_condition():
    """Add one active health condition. system_category is validated against the
    §B vocab; a tampered category or blank name is rejected (no insert)."""
    db = get_db()
    system = (request.form.get('system_category') or '').strip()
    # The Condition field is a system-filtered select (#543); the free-text
    # `condition_name_other` is the escape for the `other` system or a listed
    # category's "Other (not listed)" sentinel — it keeps the system_category.
    name = (request.form.get('condition_name') or '').strip()
    if system == 'other' or name in ('', '__other__'):
        name = (request.form.get('condition_name_other') or '').strip()
    ok = add_health_condition(
        db, current_user_id(),
        system_category=system,
        condition_name=name,
        severity=clean_severity(request.form.get('severity')),
        notes=(request.form.get('notes') or '').strip() or None,
    )
    if ok:
        db.commit()
        flash('Health condition added.', 'success')
    else:
        flash('Pick a category and enter a condition name.', 'danger')
    return redirect(url_for('profile.edit', tab='health'))


@bp.route('/condition/<int:condition_id>/delete', methods=['POST'])
def delete_condition(condition_id):
    """Remove one health condition. Scoped on user_id."""
    db = get_db()
    delete_health_condition(db, current_user_id(), condition_id)
    db.commit()
    flash('Health condition removed.', 'info')
    return redirect(url_for('profile.edit', tab='health'))


@bp.route('/medication/add', methods=['POST'])
def add_medication_route():
    """Add one active medication. medication_class is validated against the §B
    vocab; a tampered class is rejected (no insert)."""
    db = get_db()
    ok = add_medication(
        db, current_user_id(),
        medication_class=(request.form.get('medication_class') or '').strip(),
        medication_name=None,  # class only — we don't capture exact names (Andy 2026-06-11)
        notes=(request.form.get('notes') or '').strip() or None,
    )
    if ok:
        db.commit()
        flash('Medication added.', 'success')
    else:
        flash('Pick a medication class.', 'danger')
    return redirect(url_for('profile.edit', tab='health'))


@bp.route('/medication/<int:medication_id>/delete', methods=['POST'])
def delete_medication_route(medication_id):
    """Remove one medication. Scoped on user_id."""
    db = get_db()
    delete_medication(db, current_user_id(), medication_id)
    db.commit()
    flash('Medication removed.', 'info')
    return redirect(url_for('profile.edit', tab='health'))


@bp.route('/pack-load/add', methods=['POST'])
def add_pack_load_route():
    """Add one pack-load record. `pack_weight_kg` is the only required field;
    a blank/negative weight is rejected (no insert)."""
    db = get_db()
    ok = add_pack_load(
        db, current_user_id(),
        pack_weight_kg=request.form.get('pack_weight_kg'),
        session_count_4wk=request.form.get('session_count_4wk'),
        longest_session_hrs=request.form.get('longest_session_hrs'),
        terrain_type=request.form.get('terrain_type'),
        notes=request.form.get('notes'),
    )
    if ok:
        db.commit()
        flash('Pack-load record added.', 'success')
    else:
        flash('Enter a pack weight (kg).', 'danger')
    return redirect(url_for('profile.edit', tab='gear'))


@bp.route('/pack-load/<int:pack_load_id>/delete', methods=['POST'])
def delete_pack_load_route(pack_load_id):
    """Remove one pack-load record. Scoped on user_id."""
    db = get_db()
    delete_pack_load(db, current_user_id(), pack_load_id)
    db.commit()
    flash('Pack-load record removed.', 'info')
    return redirect(url_for('profile.edit', tab='gear'))


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
        'SELECT username, display_name, email, email_verified, last_login '
        'FROM users WHERE id=?',
        (uid,)
    ).fetchone()
    # 2FA status (#265): 'on' (active), 'pending' (secret issued, not yet
    # verified) or 'off'. Drives the card the account template renders.
    totp_row = mfa.get_totp(db, uid)
    if totp_row and totp_row['confirmed_at']:
        totp_status = 'on'
    elif totp_row:
        totp_status = 'pending'
    else:
        totp_status = 'off'
    # Account-merge entry (#274 follow-up, design §6). Only surfaced when the
    # feature flag is on; buttons are the identity providers whose client id is
    # configured (the OAuth-into-the-other-account proof runs through them).
    merge_enabled = account_merge.merge_enabled()
    merge_providers = []
    if merge_enabled:
        merge_providers = [
            {'slug': slug, 'label': label, 'endpoint': endpoint}
            for slug, label, endpoint in CONNECTION_PROVIDERS
            if slug in pi.SIGNIN_PROVIDERS
            and os.environ.get(_PROVIDER_CLIENT_ID_ENV.get(slug, ''))
        ]
    return render_template('profile/account.html',
                           user_row=dict(user_row) if user_row else {},
                           totp_status=totp_status,
                           merge_enabled=merge_enabled,
                           merge_providers=merge_providers)


@bp.route('/merge/confirm')
def merge_confirm():
    """Confirm screen for an account merge staged by a provider OAuth (design
    §6). 404 when the feature is off; bounces to settings if nothing's staged."""
    if not account_merge.merge_enabled():
        abort(404)
    db = get_db()
    keep_id = current_user_id()
    drop_id = account_merge.staged_drop_id(session)
    if not drop_id or drop_id == keep_id:
        flash('No account is staged to merge. Start from "Merge a duplicate '
              'account" in settings.', 'info')
        return redirect(url_for('profile.account_settings'))
    drop = account_merge.account_label(db, drop_id)
    if not drop:
        account_merge.clear_staged_merge(session)
        flash('That account no longer exists.', 'warning')
        return redirect(url_for('profile.account_settings'))
    keep = account_merge.account_label(db, keep_id)
    return render_template('profile/merge_confirm.html', keep=keep, drop=drop)


@bp.route('/merge/execute', methods=['POST'])
def merge_execute():
    """Run the staged merge (DESTRUCTIVE). Re-auths the survivor's password when
    it has one (walk-up-attacker guard, §6) and requires a typed confirmation.
    All-or-nothing: on any engine error nothing is changed."""
    if not account_merge.merge_enabled():
        abort(404)
    db = get_db()
    keep_id = current_user_id()
    drop_id = account_merge.staged_drop_id(session)
    if not drop_id or drop_id == keep_id:
        flash('No account is staged to merge.', 'info')
        return redirect(url_for('profile.account_settings'))

    keep = account_merge.account_label(db, keep_id)
    if keep and keep['has_password']:
        row = db.execute('SELECT password_hash FROM users WHERE id=?', (keep_id,)).fetchone()
        if not row or not _check_password(request.form.get('current_password') or '',
                                          row['password_hash']):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('profile.merge_confirm'))
    if (request.form.get('confirm') or '').strip() != 'MERGE':
        flash('Type MERGE to confirm the merge.', 'danger')
        return redirect(url_for('profile.merge_confirm'))

    try:
        summary = account_merge.merge_accounts(db, keep_id, drop_id)
    except Exception as exc:  # noqa: BLE001 — surface failure, change nothing
        print(f'[account-merge] failed keep={keep_id} drop={drop_id}: {exc}')  # Rule #15
        flash('Merge failed — nothing was changed.', 'danger')
        return redirect(url_for('profile.account_settings'))

    account_merge.clear_staged_merge(session)
    moved = sum(summary.get('repointed', {}).values())
    flash(f'Account merged — {moved} records moved in, and the duplicate '
          f'account was removed.', 'success')
    return redirect(url_for('profile.account_settings'))


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
    # Security receipt. Best-effort — the change is committed; a notification
    # fault must never surface as an error on a successful password change.
    try:
        send_password_changed_email(
            user_row['email'], user_row['display_name'] or user_row['username'])
    except Exception as exc:  # noqa: BLE001 — receipt must not break the change
        print(f'[email] password-changed receipt failed (change): {exc}')
    flash('Password changed.', 'success')
    return redirect(url_for('profile.account_settings'))


def _send_email_changed_email(to_old_address: str, display_name: str,
                              old_email: str, new_email: str | None) -> None:
    """Anti-takeover security receipt sent to the PREVIOUS address when the
    account email is changed or cleared, so the original owner always gets the
    last word. Best-effort; the caller swallows faults."""
    subject = 'AIDSTATION — your email address was changed'
    html, text = render_email(
        'email-changed',
        display_name=display_name or 'there',
        old_email=old_email,
        new_email=new_email or '(removed)',
        timestamp=format_timestamp(),
        security_url=account_security_url(),
    )
    send_email(to_old_address, subject, text, html)


@bp.route('/email', methods=['POST'])
def change_email():
    """Add / change / clear the account email (#251). A new address lands
    UNCONFIRMED and triggers a verification link; an athlete can also clear it
    (sets NULL). Rejected if another account already uses the address — we
    never attach the same email to two accounts (no-silent-merge, design #5).
    """
    db = get_db()
    uid = current_user_id()
    new_email = (request.form.get('email') or '').strip() or None
    current = db.execute(
        'SELECT email, display_name, username FROM users WHERE id=?', (uid,)
    ).fetchone()
    current_email = current['email'] if current else None
    current_name = (current['display_name'] or current['username']) if current else ''

    if (new_email or '').lower() == (current_email or '').lower():
        flash('That\'s already your email.', 'info')
        return redirect(url_for('profile.account_settings'))

    if new_email:
        if '@' not in new_email or '.' not in new_email.split('@')[-1]:
            flash('Enter a valid email address.', 'danger')
            return redirect(url_for('profile.account_settings'))
        taken = db.execute(
            'SELECT 1 FROM users WHERE LOWER(email) = LOWER(?) AND id <> ?',
            (new_email, uid),
        ).fetchone()
        if taken:
            flash('That email is already registered to another account.', 'danger')
            return redirect(url_for('profile.account_settings'))

    # A changed address is unverified until confirmed; clearing it resets the
    # flag too (no email = nothing to be verified).
    db.execute('UPDATE users SET email=?, email_verified=FALSE WHERE id=?',
               (new_email, uid))
    db.commit()

    if new_email:
        try:
            send_verification_email(db, uid, new_email)
        except Exception:
            pass
        flash(f'Email updated to {new_email}. Check your inbox to confirm it.', 'success')
    else:
        flash('Email removed.', 'info')
    # Notify the PREVIOUS address (anti-takeover) whenever there was one to warn.
    # Best-effort — a receipt fault must never fail the (committed) change.
    if current_email:
        try:
            _send_email_changed_email(current_email, current_name,
                                      current_email, new_email)
        except Exception as exc:  # noqa: BLE001 — receipt must not break change
            print(f'[email] email-changed receipt failed: {exc}')
    return redirect(url_for('profile.account_settings'))


# ─── Two-factor auth (TOTP) — #265 ───────────────────────────────────────────
# Enroll / confirm / disable app-based 2FA from the Account page. The login
# challenge itself lives in routes/auth.totp_challenge; the secret state machine
# and crypto live in mfa.py.


@bp.route('/totp/setup', methods=['GET', 'POST'])
def totp_setup():
    """Begin (or resume) TOTP enrollment: issue a pending secret and render the
    QR + manual key + verify form.

    POST (the "Enable" button) always rotates to a fresh secret. GET resumes an
    existing pending enrollment without rotating — so a page refresh doesn't
    invalidate the secret the athlete just scanned — and 404-equivalents to the
    account page if there's nothing pending to resume."""
    db = get_db()
    uid = current_user_id()
    if mfa.is_enabled(db, uid):
        flash('Two-factor authentication is already on.', 'info')
        return redirect(url_for('profile.account_settings'))

    existing = mfa.get_totp(db, uid)
    if request.method == 'POST' or existing is None:
        secret = mfa.start_enrollment(db, uid)
        db.commit()
    else:
        secret = existing['secret']

    user_row = db.execute(
        'SELECT username, email FROM users WHERE id=?', (uid,)
    ).fetchone()
    account_name = (user_row['email'] or user_row['username']) if user_row else 'athlete'
    uri = mfa.provisioning_uri(secret, account_name)
    return render_template('profile/totp_setup.html',
                           secret=secret, otpauth_uri=uri, qr_svg=mfa.qr_svg(uri))


@bp.route('/totp/confirm', methods=['POST'])
def totp_confirm():
    """Finish enrollment: verify the first code against the pending secret and,
    on success, flip the row to active so logins start challenging."""
    db = get_db()
    uid = current_user_id()
    row = mfa.get_totp(db, uid)
    if not row or row['confirmed_at']:
        # Nothing pending (or already active) — no-op back to account.
        return redirect(url_for('profile.account_settings'))
    if not mfa.verify_code(row['secret'], request.form.get('code') or ''):
        flash('That code didn\'t match. Scan the QR again and enter a fresh code.',
              'danger')
        return redirect(url_for('profile.totp_setup'))
    mfa.confirm_enrollment(db, uid)
    db.commit()
    flash('Two-factor authentication is on. You\'ll enter a code from your '
          'authenticator app each time you sign in.', 'success')
    return redirect(url_for('profile.account_settings'))


@bp.route('/totp/disable', methods=['POST'])
def totp_disable():
    """Turn off 2FA, or cancel a not-yet-confirmed enrollment.

    Disabling *active* 2FA requires the current password — re-auth so a walk-up
    attacker on an unlocked session can't strip the second factor (mirrors the
    change_password credential check). Cancelling a *pending* enrollment needs
    no password: nothing's protecting logins yet, so there's no factor to
    weaken."""
    db = get_db()
    uid = current_user_id()
    if mfa.is_enabled(db, uid):
        current = request.form.get('current_password') or ''
        user_row = db.execute(
            'SELECT password_hash FROM users WHERE id=?', (uid,)
        ).fetchone()
        if not user_row or not _check_password(current, user_row['password_hash']):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('profile.account_settings'))
        msg = 'Two-factor authentication turned off.'
    else:
        msg = 'Two-factor setup cancelled.'
    mfa.disable(db, uid)
    db.commit()
    flash(msg, 'info')
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
