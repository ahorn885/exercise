import hashlib
import json
import os
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session as flask_session
from werkzeug.utils import secure_filename
from database import get_db
from canonical_wellness import materialize_canonical_wellness
from calculations import calculate_1rm
from rx_engine import apply_session_outcome
from provider_cardio_resolve import DISCIPLINE_TO_PLAN_SPORT
from routes.auth import current_user_id
from plan_match import (
    find_best_match,
    candidate_plan_items,
    record_disposition,
    compute_compliance,
)

bp = Blueprint('garmin', __name__, url_prefix='/garmin')


# Redesign §17 — the `garmin.dashboard` (GET /garmin/) and `garmin.debug_fit`
# (/garmin/debug-fit) surfaces were folded into the unified Connections hub
# (`connections.hub`): the dashboard's recent-activity view is the Files tab.
# The FIT field-dump inspector now lives on the admin surface
# (`admin.fit_inspect`, issue #473) — it's operator diagnostic tooling, not
# athlete-facing. Old URLs were hard-cut
# (single-user app, no redirect shims — CONVENTIONS §A). The .FIT import +
# sync + wellness + auth pipeline below stays; the hub's drop zone posts to
# `garmin.import_fit`.


@bp.route('/import', methods=['GET', 'POST'])
def import_fit():
    if request.method == 'POST':
        if 'fit_file' not in request.files or request.files['fit_file'].filename == '':
            flash('No file selected.', 'warning')
            return redirect(url_for('garmin.import_fit'))
        fit_file = request.files['fit_file']
        fname = secure_filename(fit_file.filename or '').lower()
        if not (fname.endswith('.fit') or fname.endswith('.zip')):
            flash('File must be a .fit or .zip file.', 'danger')
            return redirect(url_for('garmin.import_fit'))
        try:
            raw = fit_file.read()
            if fname.endswith('.zip'):
                import zipfile, io
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    fit_names = [n for n in zf.namelist() if n.lower().endswith('.fit')]
                    if not fit_names:
                        flash('No .fit file found inside the zip.', 'danger')
                        return redirect(url_for('garmin.import_fit'))
                    raw = zf.read(fit_names[0])
            from garmin_fit_parser import parse_fit
            result = parse_fit(raw)
            # Stable dedup key so the cardio provider_raw_record write (Slice 2c,
            # in import_confirm) keys on the same id the bulk path uses.
            result['fit_dedup_id'] = _fit_dedup_id(raw)
            flask_session['fit_import'] = result
            flask_session['fit_name_override'] = request.form.get('activity_name', '')
            flask_session['fit_notes'] = request.form.get('notes', '')
            return redirect(url_for('garmin.import_preview'))
        except Exception as e:
            flash(f'Error parsing FIT file: {e}', 'danger')
            return redirect(url_for('garmin.import_fit'))
    return render_template('garmin/import.html')


@bp.route('/import/preview')
def import_preview():
    result = flask_session.get('fit_import')
    if not result:
        flash('No FIT data in session. Please upload a file.', 'warning')
        return redirect(url_for('garmin.import_fit'))
    db = get_db()

    # Auto-match: derive a representative activity dict (date + duration + sport)
    # for the matcher. For strength sessions the rows share a date and we use
    # the first as the representative.
    match_activity = _activity_match_repr(result)
    auto_match = find_best_match(db, match_activity) if match_activity else None

    # Nearby candidates for the resolve dropdown (or to swap from auto-match).
    nearby = candidate_plan_items(db, match_activity.get('date') if match_activity else None)
    nearby_dicts = [dict(r) for r in nearby]

    # Wider list as fallback. Dedupe against `nearby` so a near-future item
    # doesn't appear in both optgroups.
    nearby_ids = {r['id'] for r in nearby_dicts}
    all_scheduled = db.execute(
        '''SELECT pi.id, pi.item_date, pi.workout_name, pi.sport_type,
                  pi.target_duration_min, pi.target_distance_mi,
                  tp.name as plan_name
           FROM plan_items pi
           JOIN training_plans tp ON tp.id = pi.plan_id
           WHERE tp.user_id = ?
             AND pi.status = 'scheduled' AND tp.status != 'archived'
           ORDER BY pi.item_date ASC
           LIMIT 60''',
        (current_user_id(),)
    ).fetchall()
    plan_items = [r for r in all_scheduled if r['id'] not in nearby_ids]

    from units import normalize_unit_preference, display_weight, weight_unit_label
    from athlete import get_athlete_profile
    profile = get_athlete_profile(db, current_user_id()) or {}
    unit_pref = normalize_unit_preference(profile.get('unit_preference'))
    # #469 — FIT sets carry weight_kg; surface a `weight_display` chip value
    # so the preview reads in the athlete's chosen unit.
    if result and result.get('log_type') == 'strength':
        for row in result.get('data', []):
            for s in row.get('sets', []):
                d = display_weight(s.get('weight_kg'), unit_pref)
                s['weight_display'] = round(d, 1) if d is not None else None
    return render_template('garmin/import_preview.html', result=result,
                           name_override=flask_session.get('fit_name_override', ''),
                           notes=flask_session.get('fit_notes', ''),
                           plan_items=plan_items,
                           nearby=nearby_dicts,
                           weight_unit_label=weight_unit_label(unit_pref),
                           auto_match=(
                               {'plan_item': dict(auto_match['plan_item']),
                                'score': auto_match['score'],
                                'day_offset': auto_match['day_offset']}
                               if auto_match else None
                           ))


def _record_disposition_for_import(db, disposition, plan_item_id, raw_plan_item_id,
                                   log_type, log_id, reason=None, user_id=None):
    """Translate a form-submitted disposition into a disposition row.

    `plan_item_id` is what was actually written to the log row (None for
    'in_addition_to'). `raw_plan_item_id` is what the user picked in the
    dropdown — used to mark the plan item swapped/completed even when the
    log itself isn't linked.
    """
    if disposition == 'completed' and plan_item_id:
        record_disposition(db, plan_item_id, log_type, log_id, 'completed', reason, user_id=user_id)
    elif disposition == 'swapped_for' and raw_plan_item_id:
        # The log row links to the plan item; the disposition row marks the swap.
        record_disposition(db, raw_plan_item_id, log_type, log_id, 'swapped_for', reason, user_id=user_id)
    elif disposition == 'none' and plan_item_id:
        # Legacy dropdown-only flow: a plan item was picked without a radio.
        # Treat as completion so the plan item gets marked done.
        record_disposition(db, plan_item_id, log_type, log_id, 'completed', reason, user_id=user_id)
    # 'in_addition_to' — intentional no-op


def _disposition_flash(log_type_label, disposition, raw_plan_item_id):
    """Build the post-import flash message for the user."""
    base = 'Activity imported into ' + (
        'Cardio Log' if log_type_label == 'cardio' else 'Training Log'
    )
    if disposition == 'completed' and raw_plan_item_id:
        return f'{base}. Planned workout marked complete.'
    if disposition == 'swapped_for' and raw_plan_item_id:
        return f'{base}. Planned workout marked swapped.'
    if disposition == 'in_addition_to':
        return f'{base} as a standalone log (planned workout left scheduled).'
    return base + '.'


def _activity_match_repr(parsed):
    """Build the activity dict the matcher expects from a parse_fit() result.

    Cardio FIT carries date/duration/distance/activity directly. Strength FIT
    is a list of per-exercise rows; we build a session-level dict from the
    first row's date, sum sets to estimate duration if available, and tag the
    sport so the matcher knows it's a strength session.
    """
    if not parsed:
        return None
    log_type = parsed.get('log_type')
    if log_type == 'cardio':
        d = parsed['data']
        return {
            'date': d.get('date'),
            'duration_min': d.get('duration_min'),
            'distance_mi': d.get('distance_mi'),
            'activity': d.get('activity'),
        }
    if log_type == 'strength':
        rows = parsed.get('data') or []
        if not rows:
            return None
        # Sum all set durations as a rough session duration (in minutes).
        total_sec = 0
        for row in rows:
            for s in row.get('sets', []):
                if s.get('duration_sec'):
                    total_sec += s['duration_sec']
        return {
            'date': rows[0].get('date'),
            'duration_min': (total_sec / 60.0) if total_sec else None,
            'activity': 'strength_training',
            '_plan_sport_type': 'strength_training',
        }
    return None


@bp.route('/import/confirm', methods=['POST'])
def import_confirm():
    result = flask_session.get('fit_import')
    if not result:
        flash('Session expired. Please re-upload the file.', 'warning')
        return redirect(url_for('garmin.import_fit'))

    db = get_db()
    log_type = result.get('log_type')

    def _num_int(v):
        try:
            return int(v) if v else None
        except (ValueError, TypeError):
            return None

    # disposition: one of 'completed' | 'swapped_for' | 'in_addition_to' | 'none'
    # 'in_addition_to' is captured here for messaging only — it does NOT link
    # to the plan_item in the DB (per Andy's note: "user-friendly framing,
    # not a link"). plan_item_id is forced to NULL in that case.
    disposition = request.form.get('disposition', 'none')
    raw_plan_item_id = _num_int(request.form.get('plan_item_id'))
    swap_reason = (request.form.get('swap_reason') or '').strip() or None

    if disposition == 'in_addition_to':
        plan_item_id = None
    elif disposition in ('completed', 'swapped_for'):
        plan_item_id = raw_plan_item_id
    else:  # 'none'
        plan_item_id = raw_plan_item_id  # legacy: dropdown alone = completed

    uid = current_user_id()
    if log_type == 'cardio':
        data = result['data']
        data['activity_name'] = request.form.get('activity_name') or data.get('activity_name')
        data['notes'] = request.form.get('notes') or data.get('notes')
        data['activity'] = request.form.get('activity') or data.get('activity', 'Running')
        cur = db.execute(
            '''INSERT INTO cardio_log
               (date, activity, activity_name, duration_min, moving_time_min,
                distance_mi, avg_pace, avg_speed, avg_hr, max_hr, calories,
                elev_gain_ft, elev_loss_ft, avg_cadence, max_cadence,
                avg_power, max_power, norm_power, aerobic_te, anaerobic_te,
                swolf, active_lengths,
                stride_length_m, vert_oscillation_cm, vert_ratio_pct,
                gct_ms, gct_balance, discipline_id, plan_item_id, notes, user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
            (data.get('date'), data.get('activity'), data.get('activity_name'),
             data.get('duration_min'), data.get('moving_time_min'),
             data.get('distance_mi'), data.get('avg_pace'), data.get('avg_speed'),
             data.get('avg_hr'), data.get('max_hr'), data.get('calories'),
             data.get('elev_gain_ft'), data.get('elev_loss_ft'),
             data.get('avg_cadence'), data.get('max_cadence'),
             data.get('avg_power'), data.get('max_power'), data.get('norm_power'),
             data.get('aerobic_te'), data.get('anaerobic_te'),
             data.get('swolf'), data.get('active_lengths'),
             data.get('stride_length_m'), data.get('vert_oscillation_cm'),
             data.get('vert_ratio_pct'), data.get('gct_ms'), data.get('gct_balance'),
             data.get('discipline_id'), plan_item_id, data.get('notes'), uid)
        )
        log_id = cur.lastrowid
        _record_provider_raw_cardio(
            db, data.get('_provider_raw'), uid, result.get('fit_dedup_id'))
        _record_disposition_for_import(
            db, disposition, plan_item_id, raw_plan_item_id,
            log_type='cardio', log_id=log_id, reason=swap_reason, user_id=uid,
        )
        db.commit()
        flask_session.pop('fit_import', None)
        flash(_disposition_flash('cardio', disposition, raw_plan_item_id), 'success')
        return redirect(url_for('cardio.list_entries'))

    elif log_type == 'strength':
        rows = result['data']
        global_notes = request.form.get('notes') or ''

        session_date = rows[0]['date'] if rows else date.today().isoformat()
        sess_cur = db.execute(
            'INSERT INTO training_sessions (date, notes, plan_item_id, user_id) VALUES (?,?,?,?) RETURNING id',
            (session_date, global_notes or None, plan_item_id, uid)
        )
        session_id = sess_cur.lastrowid

        body_wt_row = db.execute(
            'SELECT weight_kg FROM body_metrics WHERE user_id = ? '
            'ORDER BY date DESC LIMIT 1',
            (uid,)
        ).fetchone()
        body_weight = body_wt_row['weight_kg'] if body_wt_row else None

        inserted = 0
        first_log_id = None
        for row in rows:
            exercise = row.get('exercise', '')
            sets = row.get('sets', [])

            actual_sets = len(sets)
            last_reps = sets[-1].get('reps') if sets else None
            all_weights = [s.get('weight_kg') or 0 for s in sets]
            max_weight = max(all_weights) if all_weights else None
            if max_weight == 0:
                max_weight = None
            last_duration = sets[-1].get('duration_sec') if sets else None
            volume = sum((s.get('reps') or 0) * (s.get('weight_kg') or 0) for s in sets) or None
            if volume == 0:
                volume = None
            all_1rms = [calculate_1rm(s.get('weight_kg'), s.get('reps')) or 0 for s in sets]
            est_1rm = max(all_1rms) if all_1rms else None
            if est_1rm == 0:
                est_1rm = None

            # FIT manual import: no plan-item targets available → bootstrap mode.
            # rx_engine seeds current_* and next_* from the actuals and creates
            # a current_rx row if this exercise is new.
            rx = apply_session_outcome(
                db, exercise, row.get('date'), sets,
                rx_source='From FIT Import', user_id=uid,
            )

            log_cur = db.execute(
                '''INSERT INTO training_log
                   (date, exercise, sub_group, session_id,
                    actual_sets, actual_reps, actual_weight, actual_duration,
                    outcome, est_1rm, volume, body_weight,
                    next_weight, next_sets, next_reps, next_duration, plan_item_id, notes, user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
                (row.get('date'), exercise, rx['movement_pattern'], session_id,
                 actual_sets, last_reps, max_weight, last_duration,
                 rx['outcome'], est_1rm, volume, body_weight,
                 rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
                 plan_item_id, global_notes or None, uid)
            )
            log_id = log_cur.lastrowid
            if first_log_id is None:
                first_log_id = log_id

            for i, s in enumerate(sets, 1):
                db.execute(
                    'INSERT INTO training_log_sets (training_log_id, set_number, reps, weight_kg, duration_sec, user_id) VALUES (?,?,?,?,?,?)',
                    (log_id, i, s.get('reps'), s.get('weight_kg'), s.get('duration_sec'), uid)
                )
            inserted += 1

        # Disposition is recorded against the session-level row (first log id
        # is the canonical anchor) so a plan item only gets one disposition
        # row even though a strength session spans many training_log rows.
        if first_log_id is not None:
            _record_disposition_for_import(
                db, disposition, plan_item_id, raw_plan_item_id,
                log_type='strength', log_id=first_log_id, reason=swap_reason, user_id=uid,
            )
        db.commit()
        flask_session.pop('fit_import', None)
        flash(_disposition_flash('strength', disposition, raw_plan_item_id) +
              f' ({inserted} exercise entries added.)', 'success')
        return redirect(url_for('training.list_entries'))

    flash('Unknown activity type.', 'danger')
    return redirect(url_for('garmin.import_fit'))


# ── Bulk import (multi-file drag-and-drop) ──────────────────────────────────
# The single-file flow above runs an interactive preview + plan-match step.
# Bulk import skips all of that: every file is parsed and logged as-is (no
# plan-item link, no disposition), which is what a historical backfill of many
# files wants. The browser uploads files in size-bounded batches to the JSON
# endpoints below (see static/app.js `data-bulk-upload`).

# #767 slice 1 — manual-upload source generalization. The same drop zone now
# ingests FIT activities exported from non-Garmin services (a service down or
# never-wired connection can't sync, but the athlete can still export). A
# manually uploaded FIT carries no provider activity-id, so we hash the bytes
# for an idempotent dedup key (see _fit_dedup_id) and store it in the id column
# matching the source, with a source-specific prefix so keys never collide
# across providers. Garmin stays the default (the existing single-file + Connect-
# sync paths). training_log has every column except strava_activity_id — but
# Strava exports no strength-set FITs, so a Strava strength upload can't occur.
_SOURCE_MAP = {
    'garmin': ('garmin_activity_id', 'fit:'),
    'coros':  ('coros_label_id',     'coros-file:'),
    'wahoo':  ('wahoo_workout_id',   'wahoo-file:'),
    'polar':  ('polar_exercise_id',  'polar-file:'),
    'strava': ('strava_activity_id', 'strava-file:'),
}


def _source_column(source: str) -> str:
    """The cardio_log / training_log provider-id column an upload source writes to."""
    return _SOURCE_MAP.get(source, _SOURCE_MAP['garmin'])[0]


def _source_prefix(source: str) -> str:
    """The dedup-key prefix that namespaces an upload source's content hashes."""
    return _SOURCE_MAP.get(source, _SOURCE_MAP['garmin'])[1]


def _fit_dedup_id(raw: bytes, prefix: str = 'fit:') -> str:
    """Stable per-file dedup key for manually uploaded activity FITs.

    Provider activity IDs only exist for API-synced activities; a raw uploaded
    .fit has none. Hashing the bytes gives an idempotent key so re-dropping the
    same folder skips files already imported. Stored in the source's id column
    (see _SOURCE_MAP) with a source-specific `prefix` so it never collides with
    a numeric service ID or a hash from another provider."""
    return prefix + hashlib.sha256(raw).hexdigest()


# Activity upload formats and their parser dispatch key. .fit is Garmin's path;
# .tcx/.gpx (#767 slice 2) are the non-Garmin per-session exports (Polar/COROS/
# Strava) — each parser emits the same normalized cardio dict, so the writer is
# shared. The key is the lowercased extension sans dot.
_ACTIVITY_EXTS = ('fit', 'tcx', 'gpx')

# #767 slice 5 — the unified uploader also auto-detects a WHOOP wellness export
# (`physiological_cycles.csv`) and routes it to provider_raw_record (the
# wellness path) instead of cardio_log. CSV is the only non-activity upload
# format, so a `.csv` blob == a WHOOP wellness export (the parser validates).
_WELLNESS_CSV_EXT = 'csv'
_UPLOAD_EXTS = _ACTIVITY_EXTS + (_WELLNESS_CSV_EXT,)


def _blob_ext(name: str) -> str | None:
    """The upload-format key for a filename, or None if it isn't ingestible.
    Activity formats ('fit'|'tcx'|'gpx') route to cardio_log; 'csv' is a WHOOP
    wellness export routed to provider_raw_record (#767 slice 5)."""
    low = name.lower()
    for ext in _UPLOAD_EXTS:
        if low.endswith('.' + ext):
            return ext
    return None


def _iter_activity_blobs(files):
    """Expand an uploaded file list into (name, bytes, ext, error) tuples.

    Each upload is an ingestible file (.fit/.tcx/.gpx activity or a .csv WHOOP
    wellness export) or a .zip (every ingestible entry inside, so a whole
    exported folder zipped up imports in one shot). `ext` is the dispatch key
    ('fit'|'tcx'|'gpx'|'csv'); exactly one of (bytes+ext) / error is set per
    yielded tuple."""
    import zipfile
    import io
    for f in files:
        if not f or not f.filename:
            continue
        name = secure_filename(f.filename or '') or '(unnamed)'
        if name.lower().endswith('.zip'):
            try:
                raw = f.read()
            except Exception as e:
                yield (name, None, None, f'could not read upload: {e}')
                continue
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    entries = [(n, _blob_ext(n)) for n in zf.namelist()]
                    entries = [(n, ext) for n, ext in entries if ext]
                    if not entries:
                        yield (name, None, None, 'no .fit/.tcx/.gpx/.csv files inside zip')
                        continue
                    for n, ext in entries:
                        yield (f'{name}:{n}', zf.read(n), ext, None)
            except zipfile.BadZipFile:
                yield (name, None, None, 'not a valid zip file')
            continue
        ext = _blob_ext(name)
        if not ext:
            yield (name, None, None, 'not a .fit/.tcx/.gpx/.csv or .zip file')
            continue
        try:
            yield (name, f.read(), ext, None)
        except Exception as e:
            yield (name, None, None, f'could not read upload: {e}')


def _record_provider_raw_cardio(db, raw: dict, uid: int, external_id,
                                provider: str | None = None) -> None:
    """#681 §4 Slice 2c — record the raw provider cardio signal into
    provider_raw_record (record-don't-drop), carrying the indoor-machine flag
    when the completed activity used one.

    This is the table's first writer. Idempotent per
    (user_id, provider, data_type, external_id) so re-importing the same
    activity refreshes rather than duplicates; a NULL external_id (the rare
    single-file path with no dedup key) cannot conflict, so it inserts.
    `raw` is the `_provider_raw` dict that parse_fit / normalize_activity attach;
    a falsy raw (e.g. a session payload parsed before this slice) is a no-op.
    `provider` (#767 slice 1) tags the corroboration row with the upload source
    (coros/wahoo/polar/strava) instead of the parser default — None keeps the
    raw dict's own provider (garmin).

    BEST-EFFORT: this raw passthrough is corroboration data, not the athlete's
    log, so the write is wrapped in a SAVEPOINT — a failure is logged and
    swallowed, never aborting the cardio_log import it rides alongside (the
    write shares the import's transaction)."""
    if not raw:
        return
    payload = raw.get('payload') or {}
    machine = payload.get('indoor_machine')
    # '' (a FIT whose session timestamp didn't parse) is not a valid TIMESTAMP
    # literal — store NULL rather than letting it error the import.
    observed_at = raw.get('observed_at') or None
    try:
        db.execute('SAVEPOINT provider_raw_cardio')
        db.execute(
            '''INSERT INTO provider_raw_record
                   (user_id, provider, data_type, external_id, observed_at,
                    raw_payload, bucket, canonical_ref)
               VALUES (?,?,?,?,?,?::jsonb,?,?)
               ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE SET
                   observed_at = EXCLUDED.observed_at,
                   raw_payload = EXCLUDED.raw_payload,
                   bucket = EXCLUDED.bucket,
                   canonical_ref = EXCLUDED.canonical_ref,
                   fetched_at = NOW()''',
            (uid, provider or raw.get('provider', 'garmin'), 'cardio', external_id,
             observed_at, json.dumps(payload),
             raw.get('bucket'), raw.get('canonical_ref'))
        )
        db.execute('RELEASE SAVEPOINT provider_raw_cardio')
    except Exception as e:  # Rule #15 — never break the import on a corroboration write
        try:
            db.execute('ROLLBACK TO SAVEPOINT provider_raw_cardio')
        except Exception:
            pass
        print(
            f"[provider-raw] {provider or raw.get('provider', 'garmin')} cardio "
            f"external_id={external_id!r} SKIPPED ({type(e).__name__}: {e})"
        )
        return
    print(  # Rule #15
        f"[provider-raw] {provider or raw.get('provider', 'garmin')} cardio "
        f"external_id={external_id!r} "
        f"bucket={raw.get('bucket')} canonical_ref={raw.get('canonical_ref')!r} "
        f"machine={machine!r}"
    )


def _normalize_started_at(data: dict):
    """Resolve one comparable UTC start instant for a cardio activity — the #196
    Phase 3 cross-source clustering fingerprint input (Slice 1).

    Reads an explicit ``data['started_at']`` when a provider set one (Strava
    passes its true-UTC ``start_date`` there, since its
    ``_provider_raw.observed_at`` is local wall-clock), else falls back to
    ``_provider_raw.observed_at`` (the activity start for Wahoo/RWGPS; date-only
    for manual FIT/TCX/GPX, so those land at 00:00 UTC). Accepts a ``datetime``
    or an ISO-8601 string (``Z``, numeric offset, or date-only) and returns a
    naive UTC ``datetime``, or ``None`` if absent/unparseable. Never raises — a
    bad start must not break the import (Rule #15 logs the miss)."""
    raw = (data.get('started_at')
           or (data.get('_provider_raw') or {}).get('observed_at'))
    if raw is None or raw == '':
        return None
    dt = raw
    if isinstance(dt, str):
        s = dt.strip().replace('Z', '+00:00')
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            try:  # date-only fallback (manual FIT/TCX/GPX observed_at)
                dt = datetime.fromisoformat(s[:10])
            except ValueError:
                print(f"[cardio-started_at] unparseable start {raw!r} — storing NULL")
                return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ── #196 Phase 3 Slice 2 — cross-source activity clustering ───────────────────
# One real-world activity reaching us via N connected providers lands as N
# cardio_log rows (a Wahoo ride auto-forwarded to Strava → the repro rows 73+74).
# Slice 1 laid the substrate (started_at + activity_clusters + cardio_log.
# cluster_id); this slice is the matcher: right after each insert, fingerprint
# the row and either attach it to an existing same-activity cluster or open a new
# one. It sits ABOVE the per-source *_uidx idempotency (which already collapses a
# provider's own re-deliveries) — it never weakens it.
#
# Tolerances (Andy 2026-06-23): start ±5 min, duration ±10%, distance ±10%.
_CLUSTER_START_TOL = timedelta(minutes=5)
_CLUSTER_DURATION_TOL = 0.10
_CLUSTER_DISTANCE_TOL = 0.10
# Advisory-lock namespace so two near-simultaneous webhooks for the same ride
# (Wahoo + its Strava auto-forward) serialize through find-or-create and can't
# both miss and open a cluster — the handoff's "must not fork" requirement. The
# lock is txn-scoped (writes run in a transaction, autocommit off — database.py),
# so it auto-releases at the caller's commit.
_CLUSTER_LOCK_NS = 196

# Coarse sport family for the fingerprint. The match is deliberately loose on
# event type (Andy 2026-06-23: "some apps may not have categories which match
# perfectly"): providers label the same ride differently — Strava 'cycling'/
# 'ride', Polar/COROS 'cycle', Garmin a fine D-id. Resolve the canonical coarse
# family from the layer0 discipline when the provider set one
# (DISCIPLINE_TO_PLAN_SPORT — provider-independent: every resolver-backed source
# collapses the same ride to the same family), else fold the resolver-less
# provider vocab (Polar _SPORT_MAP / COROS _SPORT_MODE singulars) onto that same
# namespace. Anything else stays as-is; '', 'other' and 'unknown' are wildcards.
_SPORT_FAMILY_ALIASES = {
    'cycle': 'cycling', 'bike': 'cycling', 'biking': 'cycling',
    'run': 'running', 'jog': 'running', 'trail_run': 'running',
    'swim': 'swimming',
    'hike': 'hiking', 'trek': 'hiking',
    'walk': 'walking',
}
_SPORT_WILDCARD = {'', 'other', 'unknown'}


def _coarse_sport(data: dict) -> str:
    """Resolve a cardio activity's coarse sport family for cross-source matching.

    Canonical layer0 discipline → coarse family first (DISCIPLINE_TO_PLAN_SPORT;
    Strava/Wahoo/RWGPS/Garmin all collapse the same ride to the same family
    regardless of label), else the freetext `activity` folded through
    _SPORT_FAMILY_ALIASES (Polar/COROS set no discipline_id). 'other' when
    nothing classifies it — which then matches loosely (see _sport_matches)."""
    fam = DISCIPLINE_TO_PLAN_SPORT.get(data.get('discipline_id') or '')
    if fam:
        return fam
    activity = (data.get('activity') or '').strip().lower().replace(' ', '_')
    return _SPORT_FAMILY_ALIASES.get(activity, activity) or 'other'


def _sport_matches(a: str, b: str) -> bool:
    """Loose coarse-sport equality: same family, or either side unclassified."""
    return a == b or a in _SPORT_WILDCARD or b in _SPORT_WILDCARD


def _metric_within(a, b, tol):
    """Tri-state tolerance check for a fingerprint metric (duration / distance):
    True = both present, non-zero, within ±tol (corroborates); False = both
    present and outside ±tol (disqualifies); None = can't tell (missing on a
    side, or both ~zero — e.g. an indoor ride's 0 distance)."""
    if a is None or b is None:
        return None
    hi = max(abs(a), abs(b))
    if hi == 0:
        return None
    return abs(a - b) <= tol * hi


def _fingerprint_match(data: dict, started_at, family: str, cand) -> bool:
    """Does the new row belong to candidate cluster `cand`? Requires the start
    within tolerance, a loose sport match, no metric clearly disagreeing, and at
    least one of duration/distance positively corroborating — so a bare start
    coincidence (no distance, unknown duration) never merges on its own."""
    c_start = cand['started_at']
    if c_start is None or abs(started_at - c_start) > _CLUSTER_START_TOL:
        return False
    if not _sport_matches(family, cand['sport_class'] or 'other'):
        return False
    dur = _metric_within(data.get('duration_min'), cand['duration_min'], _CLUSTER_DURATION_TOL)
    dist = _metric_within(data.get('distance_mi'), cand['distance_mi'], _CLUSTER_DISTANCE_TOL)
    if dur is False or dist is False:
        return False
    return dur is True or dist is True


def cluster_activity(db, uid: int, cardio_id: int, data: dict, started_at):
    """Attach a freshly-inserted cardio_log row to its cross-source activity
    cluster, opening a new one if nothing matches; returns the cluster id (or
    None when the row can't be clustered). Called by _bulk_insert_cardio right
    after insert, so every provider webhook and the manual uploader run through
    one matcher.

    Idempotent + re-entrant: late arrivals (RWGPS cron-deferred up to 24h; Strava
    lags minutes) attach to the existing cluster, and a per-user advisory lock
    keeps two near-simultaneous inserts of the same ride from forking it. A row
    with no resolvable start can't be time-fingerprinted, so it's left
    unclustered rather than risk a false merge (kickoff §6 NULL tolerance).
    Rule #15: logs the fingerprint inputs + the match/no-match decision + id."""
    family = _coarse_sport(data)
    if started_at is None:
        print(f"[cardio-cluster] id={cardio_id} user={uid} sport={family} "
              f"started_at=None -> unclustered (no start instant)")
        return None

    # Serialize find-or-create per user (txn-scoped; released at commit) so
    # concurrent same-ride webhooks can't both miss and open duplicate clusters.
    db.execute('SELECT pg_advisory_xact_lock(?, ?)', (_CLUSTER_LOCK_NS, uid))

    lo, hi = started_at - _CLUSTER_START_TOL, started_at + _CLUSTER_START_TOL
    candidates = db.execute(
        '''SELECT id, sport_class, started_at, duration_min, distance_mi
           FROM activity_clusters
           WHERE user_id = ? AND started_at BETWEEN ? AND ?
           ORDER BY started_at''',
        (uid, lo, hi),
    ).fetchall()
    match = next(
        (c for c in candidates if _fingerprint_match(data, started_at, family, c)),
        None,
    )

    if match is not None:
        cluster_id = match['id']
        db.execute('UPDATE cardio_log SET cluster_id = ? WHERE id = ?', (cluster_id, cardio_id))
        db.execute('UPDATE activity_clusters SET updated_at = NOW() WHERE id = ?', (cluster_id,))
        print(f"[cardio-cluster] id={cardio_id} user={uid} sport={family} "
              f"started_at={started_at} dur={data.get('duration_min')} "
              f"dist={data.get('distance_mi')} -> MATCH cluster={cluster_id} "
              f"(of {len(candidates)} candidate(s))")
        materialize_canonical_activity(db, uid, cluster_id)  # #196 P3 Slice 3 — re-merge
        return cluster_id

    cluster_id = db.execute(
        '''INSERT INTO activity_clusters
           (user_id, sport_class, started_at, duration_min, distance_mi)
           VALUES (?,?,?,?,?) RETURNING id''',
        (uid, family, started_at, data.get('duration_min'), data.get('distance_mi')),
    ).lastrowid
    db.execute('UPDATE cardio_log SET cluster_id = ? WHERE id = ?', (cluster_id, cardio_id))
    print(f"[cardio-cluster] id={cardio_id} user={uid} sport={family} "
          f"started_at={started_at} dur={data.get('duration_min')} "
          f"dist={data.get('distance_mi')} -> NEW cluster={cluster_id} "
          f"({len(candidates)} candidate(s), none matched)")
    materialize_canonical_activity(db, uid, cluster_id)  # #196 P3 Slice 3 — first merge
    return cluster_id


# ── #196 Phase 3 Slice 3 — completeness scoring + canonical materialization ───
# Slice 2 groups the N cardio_log rows of one real-world activity into an
# activity_clusters row; this slice merges each cluster into ONE best-of
# canonical_activity record + per-field provenance. materialize_canonical_activity
# runs at the tail of cluster_activity on every member add, so a late Strava/RWGPS
# arrival (cron-deferred up to 24h) re-merges. Storage shape B + weighted "richest
# data wins" (Andy 2026-06-23, Trigger-#3 ratified).
#
# Per-field weights: sensor/device-grade metrics (power, HR, running dynamics,
# training effect, swim) outweigh GPS/derived, which outweigh the baseline fields
# present on nearly every copy. The richest copy becomes the primary; each merged
# field is gap-filled from the highest-scoring copy that actually carries it.
_METRIC_WEIGHTS = {
    # tier 3 — sensor/device-grade (the "better device" signal)
    'avg_power': 3, 'max_power': 3, 'norm_power': 3,
    'avg_hr': 3, 'max_hr': 3,
    'aerobic_te': 3, 'anaerobic_te': 3,
    'stride_length_m': 3, 'vert_oscillation_cm': 3, 'vert_ratio_pct': 3,
    'gct_ms': 3, 'gct_balance': 3,
    'swolf': 3, 'active_lengths': 3,
    # tier 2 — GPS / derived
    'elev_gain_ft': 2, 'elev_loss_ft': 2,
    'avg_cadence': 2, 'max_cadence': 2,
    'avg_speed': 2, 'avg_pace': 2, 'calories': 2, 'moving_time_min': 2,
    # tier 1 — baseline, on nearly every copy
    'duration_min': 1, 'distance_mi': 1, 'activity_name': 1,
}
# Identity fields: primary-wins, non-null gap-fill, NOT scored (every copy of the
# same activity carries the same date/sport/start, so they don't differentiate).
_IDENTITY_FIELDS = ('date', 'activity', 'discipline_id', 'started_at')
# Every column the merged canonical row carries (identity first, then the metrics).
_CANONICAL_FIELDS = _IDENTITY_FIELDS + tuple(_METRIC_WEIGHTS)

# A cardio_log row's origin provider = whichever per-source dedup id column is set
# (manual file uploads land in their file-type's column too — _SOURCE_MAP — so
# this names the data's origin). Drives provenance display ("power from wahoo")
# and the score-TIE tiebreaker: prefer the recording device over a downstream
# re-import. Order here = the tiebreaker order; it rarely fires (score decides).
_PROVIDER_ID_COLUMNS = (
    ('garmin_activity_id', 'garmin'),
    ('wahoo_workout_id', 'wahoo'),
    ('polar_exercise_id', 'polar'),
    ('coros_label_id', 'coros'),
    ('rwgps_trip_id', 'rwgps'),
    ('strava_activity_id', 'strava'),
)
_SOURCE_ORDER = {name: i for i, (_col, name) in enumerate(_PROVIDER_ID_COLUMNS)}


def _has_value(v) -> bool:
    """Does a field carry a meaningful value for scoring / gap-fill? Non-null, and
    non-zero for numerics (a 0 avg_power / 0 distance is 'sensor absent', not real
    data — the same reason the Slice-2 clusterer treats 0 distance as 'can't
    tell'), and non-empty for text."""
    if v is None:
        return False
    if isinstance(v, (int, float)):  # bool is an int subclass; False reads as absent
        return v != 0
    if isinstance(v, str):
        return v.strip() != ''
    return True


def _completeness_score(row) -> int:
    """Weighted count of the meaningful metric fields a cardio_log row carries.
    Higher = richer copy = preferred primary (Andy 2026-06-23 'richest data wins')."""
    return sum(w for f, w in _METRIC_WEIGHTS.items() if _has_value(row.get(f)))


def _row_provider(row) -> str:
    """Origin provider of a cardio_log row, from whichever per-source id column is
    set. 'unknown' if none is (e.g. a pre-provider manual entry)."""
    for col, name in _PROVIDER_ID_COLUMNS:
        if _has_value(row.get(col)):
            return name
    return 'unknown'


def _primary_rank(row):
    """Primary-selection sort key: richest completeness first, then the static
    source order as the tiebreaker (lower index = preferred)."""
    return (-_completeness_score(row), _SOURCE_ORDER.get(_row_provider(row), len(_SOURCE_ORDER)))


def materialize_canonical_activity(db, uid: int, cluster_id: int):
    """(Re)build the single best-of canonical_activity record for a cluster + its
    per-field provenance. Idempotent: called at the tail of cluster_activity on
    every member add, so a late cross-source arrival re-merges. Picks the richest
    copy as primary (weighted completeness; static source order breaks ties),
    gap-fills each field from the highest-scoring copy that carries it, upserts the
    canonical row (ON CONFLICT cluster_id) and replaces the cluster's provenance.
    Rule #15: logs the members, the chosen primary, and the per-field source map."""
    id_cols = tuple(col for col, _name in _PROVIDER_ID_COLUMNS)
    select_cols = ', '.join(('id',) + _CANONICAL_FIELDS + id_cols)
    members = db.execute(
        f'SELECT {select_cols} FROM cardio_log WHERE cluster_id = ? ORDER BY id',
        (cluster_id,),
    ).fetchall()
    if not members:
        # Defensive: a cluster with no members keeps no canonical record. (Slice 3
        # never empties a cluster, but re-materialization must be self-consistent.)
        db.execute('DELETE FROM canonical_activity_field_provenance WHERE cluster_id = ?', (cluster_id,))
        db.execute('DELETE FROM canonical_activity WHERE cluster_id = ?', (cluster_id,))
        print(f"[cardio-canon] cluster={cluster_id} user={uid} no members -> cleared")
        return

    ranked = sorted(members, key=_primary_rank)
    primary = ranked[0]

    # Best-of merge: each field takes the value of the highest-scoring copy that
    # actually carries one (primary first since it leads `ranked`); provenance
    # records which copy + provider that was.
    merged, provenance = {}, {}
    for f in _CANONICAL_FIELDS:
        src = next((m for m in ranked if _has_value(m.get(f))), None)
        merged[f] = src.get(f) if src is not None else None
        if src is not None:
            provenance[f] = (src['id'], _row_provider(src))

    insert_cols = ['user_id', 'cluster_id', *_CANONICAL_FIELDS,
                   'primary_cardio_log_id', 'completeness_score']
    values = [uid, cluster_id, *[merged[f] for f in _CANONICAL_FIELDS],
              primary['id'], _completeness_score(primary)]
    placeholders = ', '.join(['?'] * len(insert_cols))
    update_assign = ', '.join(
        f'{c} = EXCLUDED.{c}'
        for c in (*_CANONICAL_FIELDS, 'primary_cardio_log_id', 'completeness_score'))
    db.execute(
        f'''INSERT INTO canonical_activity ({', '.join(insert_cols)}, updated_at)
            VALUES ({placeholders}, NOW())
            ON CONFLICT (cluster_id) DO UPDATE SET {update_assign}, updated_at = NOW()''',
        tuple(values),
    )

    # Replace provenance wholesale — re-materialization is the only writer, and a
    # field that lost its source on a re-merge must not leave a stale row behind.
    db.execute('DELETE FROM canonical_activity_field_provenance WHERE cluster_id = ?', (cluster_id,))
    for f, (src_id, prov) in provenance.items():
        db.execute(
            '''INSERT INTO canonical_activity_field_provenance
               (cluster_id, field_name, source_cardio_log_id, source_provider)
               VALUES (?,?,?,?)''',
            (cluster_id, f, src_id, prov),
        )

    field_map = ', '.join(f'{f}<-{prov}' for f, (_id, prov) in sorted(provenance.items()))
    print(f"[cardio-canon] cluster={cluster_id} user={uid} members={len(members)} "
          f"primary=id{primary['id']}/{_row_provider(primary)} "
          f"score={_completeness_score(primary)} fields={{{field_map}}}")


def _bulk_insert_cardio(db, data: dict, uid: int, gid: str,
                        plan_item_id=None, notes=None, source: str = 'garmin') -> int:
    """Insert one parsed cardio activity. Returns the new cardio_log id.

    `source` (#767 slice 1) selects which provider-id column `gid` lands in:
    garmin_activity_id for the default Garmin path, or the matching column for a
    COROS / Wahoo / Polar / Strava manual upload. The column comes from the
    fixed _SOURCE_MAP allowlist (no user-supplied identifier reaches the SQL)."""
    col = _source_column(source)
    started_at = _normalize_started_at(data)  # #196 P3 Slice 1 — UTC fingerprint input
    cur = db.execute(
        f'''INSERT INTO cardio_log
           (date, activity, activity_name, duration_min, moving_time_min,
            distance_mi, avg_pace, avg_speed, avg_hr, max_hr, calories,
            elev_gain_ft, elev_loss_ft, avg_cadence, max_cadence,
            avg_power, max_power, norm_power, aerobic_te, anaerobic_te,
            swolf, active_lengths,
            stride_length_m, vert_oscillation_cm, vert_ratio_pct,
            gct_ms, gct_balance, started_at, discipline_id, {col}, plan_item_id, notes, user_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
        (data.get('date'), data.get('activity'), data.get('activity_name'),
         data.get('duration_min'), data.get('moving_time_min'),
         data.get('distance_mi'), data.get('avg_pace'), data.get('avg_speed'),
         data.get('avg_hr'), data.get('max_hr'), data.get('calories'),
         data.get('elev_gain_ft'), data.get('elev_loss_ft'),
         data.get('avg_cadence'), data.get('max_cadence'),
         data.get('avg_power'), data.get('max_power'), data.get('norm_power'),
         data.get('aerobic_te'), data.get('anaerobic_te'),
         data.get('swolf'), data.get('active_lengths'),
         data.get('stride_length_m'), data.get('vert_oscillation_cm'),
         data.get('vert_ratio_pct'), data.get('gct_ms'), data.get('gct_balance'),
         started_at, data.get('discipline_id'), gid, plan_item_id,
         (notes if notes is not None else (data.get('notes') or None)), uid)
    )
    rec_id = cur.lastrowid
    print(  # Rule #15 — the resolved UTC start fingerprint input (#196 P3 Slice 1)
        f"[cardio-insert] id={rec_id} source={source} gid={gid!r} "
        f"date={data.get('date')!r} sport={data.get('activity')!r} "
        f"started_at={started_at}"
    )
    cluster_activity(db, uid, rec_id, data, started_at)  # #196 P3 Slice 2 — cross-source dedup
    _record_provider_raw_cardio(db, data.get('_provider_raw'), uid, gid, provider=source)
    return rec_id


def _bulk_insert_strength(db, rows: list, uid: int, gid: str,
                          plan_item_id=None, notes=None, source: str = 'garmin') -> tuple:
    """Insert a parsed strength FIT session (one training_log row per
    exercise, plus per-set rows). Returns (n_exercises, first_log_id); the
    first log id is the canonical anchor for a plan-item disposition.

    Mirrors the single-file confirm path: rx_engine seeds/advances progression
    in bootstrap mode since manual FITs carry no plan targets.

    `source` (#767 slice 1) picks the provider-id column, same as the cardio
    path. Strava is excluded (no training_log strava column) but exports no
    strength FITs, so that pairing never reaches here."""
    if not rows:
        return 0, None
    col = _source_column(source)
    session_date = rows[0].get('date') or date.today().isoformat()
    sess_cur = db.execute(
        'INSERT INTO training_sessions (date, notes, plan_item_id, user_id) VALUES (?,?,?,?) RETURNING id',
        (session_date, notes, plan_item_id, uid)
    )
    session_id = sess_cur.lastrowid
    first_log_id = None

    body_wt_row = db.execute(
        'SELECT weight_kg FROM body_metrics WHERE user_id = ? ORDER BY date DESC LIMIT 1',
        (uid,)
    ).fetchone()
    body_weight = body_wt_row['weight_kg'] if body_wt_row else None

    inserted = 0
    for row in rows:
        exercise = row.get('exercise', '')
        sets = row.get('sets', [])
        actual_sets = len(sets)
        last_reps = sets[-1].get('reps') if sets else None
        all_weights = [s.get('weight_kg') or 0 for s in sets]
        max_weight = max(all_weights) if all_weights else None
        if max_weight == 0:
            max_weight = None
        last_duration = sets[-1].get('duration_sec') if sets else None
        volume = sum((s.get('reps') or 0) * (s.get('weight_kg') or 0) for s in sets) or None
        if volume == 0:
            volume = None
        all_1rms = [calculate_1rm(s.get('weight_kg'), s.get('reps')) or 0 for s in sets]
        est_1rm = max(all_1rms) if all_1rms else None
        if est_1rm == 0:
            est_1rm = None

        rx = apply_session_outcome(
            db, exercise, row.get('date'), sets,
            rx_source='From FIT Import', user_id=uid,
        )

        log_cur = db.execute(
            f'''INSERT INTO training_log
               (date, exercise, sub_group, session_id,
                actual_sets, actual_reps, actual_weight, actual_duration,
                outcome, est_1rm, volume, body_weight,
                next_weight, next_sets, next_reps, next_duration,
                {col}, plan_item_id, notes, user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
            (row.get('date'), exercise, rx['movement_pattern'], session_id,
             actual_sets, last_reps, max_weight, last_duration,
             rx['outcome'], est_1rm, volume, body_weight,
             rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
             gid, plan_item_id, notes, uid)
        )
        log_id = log_cur.lastrowid
        if first_log_id is None:
            first_log_id = log_id
        for i, s in enumerate(sets, 1):
            db.execute(
                'INSERT INTO training_log_sets (training_log_id, set_number, reps, weight_kg, duration_sec, user_id) VALUES (?,?,?,?,?,?)',
                (log_id, i, s.get('reps'), s.get('weight_kg'), s.get('duration_sec'), uid)
            )
        inserted += 1
    return inserted, first_log_id


def _cardio_detail(data: dict) -> str:
    """Short one-line description of an imported cardio activity for the UI."""
    bits = [data.get('activity') or 'Activity']
    if data.get('date'):
        bits.append(data['date'])
    if data.get('distance_mi'):
        bits.append(f"{data['distance_mi']} mi")
    elif data.get('duration_min'):
        bits.append(f"{round(data['duration_min'])} min")
    return ' · '.join(bits)


def _activity_repr_date(result) -> str:
    """Best-effort activity date, used to order inserts chronologically so the
    rx_engine progression sees strength sessions oldest-first."""
    if not result:
        return ''
    if result.get('log_type') == 'cardio':
        return (result.get('data') or {}).get('date') or ''
    rows = result.get('data') or []
    return (rows[0].get('date') or '') if rows else ''


def _match_notes(plan_item, compliance: dict) -> str:
    """Build the auto-match note string (parity with the Garmin sync path)."""
    parts = [f'Auto-matched: "{plan_item["workout_name"]}"']
    if compliance.get('duration_pct') is not None:
        parts.append(f"Duration {compliance['duration_pct']}% of target")
    if compliance.get('distance_pct') is not None:
        parts.append(f"Distance {compliance['distance_pct']}% of target")
    return '. '.join(parts)


def _bulk_log_one(db, uid: int, gid: str, result: dict, match_plan: bool,
                  source: str = 'garmin') -> dict:
    """Insert one parsed activity, optionally auto-matching it to a scheduled
    plan item (and marking that item complete). Caller owns commit/rollback.

    Returns a per-file result dict, or None for an unknown activity type.
    Matching mirrors the Garmin sync: best same-day-first match at/above the
    auto-match threshold links the log, records a 'completed' disposition, and
    annotates the log with compliance vs the plan target."""
    log_type = result.get('log_type')
    match_repr = _activity_match_repr(result) if match_plan else None
    m = find_best_match(db, match_repr, user_id=uid) if match_repr else None
    plan_item = m['plan_item'] if m else None
    plan_item_id = plan_item['id'] if plan_item else None

    notes = None
    match_detail = ''
    if plan_item:
        compliance = compute_compliance(match_repr, plan_item)
        notes = _match_notes(plan_item, compliance)
        match_detail = f' → "{plan_item["workout_name"]}" ({compliance["label"]})'

    if log_type == 'cardio':
        log_id = _bulk_insert_cardio(db, result['data'], uid, gid, plan_item_id, notes, source)
        if plan_item_id:
            record_disposition(db, plan_item_id, 'cardio', log_id, 'completed', user_id=uid)
        return {'status': 'imported', 'log_type': 'cardio', 'matched': bool(plan_item_id),
                'detail': _cardio_detail(result['data']) + match_detail}
    if log_type == 'strength':
        n, first_log_id = _bulk_insert_strength(db, result['data'], uid, gid, plan_item_id, notes, source)
        if plan_item_id and first_log_id:
            record_disposition(db, plan_item_id, 'strength', first_log_id, 'completed', user_id=uid)
        return {'status': 'imported', 'log_type': 'strength', 'matched': bool(plan_item_id),
                'detail': (f'{n} exercise' + ('' if n == 1 else 's')) + match_detail}
    return None


@bp.route('/import/bulk', methods=['POST'])
def import_bulk():
    """Parse many uploaded files and auto-route each to the right place — one
    drop zone for a whole export folder, activities AND wellness. .tcx/.gpx
    (#767 slice 2) are the non-Garmin per-session activity exports; each parser
    emits the same normalized cardio dict, so the writer is shared. Activity
    files (cardio / strength) are logged and optionally auto-matched to a
    scheduled plan workout (pass match_plan=0 to log raw); FIT wellness /
    daily-metric files (`_WELLNESS`, `_METRICS`, `_SLEEP_DATA`, `_HRV_STATUS`)
    merge into wellness_log / daily_wellness_metrics; and a WHOOP
    `physiological_cycles.csv` (#767 slice 5) is auto-detected by extension and
    ingested into provider_raw_record (provider='whoop'). Idempotent
    (content-hash dedup for activities, per-row dedup for wellness). Returns JSON
    for the drag-and-drop UI."""
    db = get_db()
    uid = current_user_id()
    files = request.files.getlist('files')
    if not files:
        return jsonify({'ok': False, 'error': 'No files in request.'}), 400

    from garmin_fit_parser import parse_fit, fit_file_meta
    from tcx_gpx_parser import parse_tcx, parse_gpx
    _ACTIVITY_PARSERS = {'fit': parse_fit, 'tcx': parse_tcx, 'gpx': parse_gpx}

    match_plan = request.form.get('match_plan', '1') not in ('0', 'false', 'no', 'off', '')

    # #767 slice 1 — which service these files came from. Selects the provider-id
    # column + dedup prefix; an unknown value falls back to Garmin (the default).
    source = request.form.get('source', 'garmin').strip().lower()
    if source not in _SOURCE_MAP:
        source = 'garmin'
    prefix = _source_prefix(source)
    print(  # Rule #15 — chosen source + id-column for this import batch
        f"[bulk-import] source={source} id_column={_source_column(source)} "
        f"files={len(files)}"
    )

    results = []
    summary = {'imported': 0, 'matched': 0, 'duplicates': 0, 'skipped': 0,
               'errors': 0, 'files': 0, 'metrics_days': 0}

    # Phase 0 — classify each file by its FileIdMessage kind. Wellness / daily-
    # metric files go to the wellness tables; activities (and FileId-less
    # 'unknown' files) go to the activity path below, which itself falls back to
    # wellness ingestion if parse_fit finds no session. Each file's result row
    # records where it landed (Rule #15: the decision is legible per file).
    # Only FIT files carry wellness/daily-metric payloads; TCX/GPX are always
    # activities (no wellness variant), so they skip the FileId classification.
    _WELLNESS_KINDS = {'wellness', 'metrics', 'sleep_data', 'hrv_status'}
    wellness_pending = []      # (time_ms, name, raw, kind)
    wellness_csv_pending = []  # (name, raw) — WHOOP physiological_cycles.csv
    activity_blobs = []        # (name, raw, ext)
    for name, raw, ext, err in _iter_activity_blobs(files):
        if err:
            results.append({'name': name, 'status': 'skipped', 'detail': err})
            summary['skipped'] += 1
            continue
        if ext == 'csv':
            wellness_csv_pending.append((name, raw))
            continue
        if ext == 'fit':
            try:
                kind, time_ms = fit_file_meta(raw)
            except Exception:
                kind, time_ms = 'unknown', 0
            if kind in _WELLNESS_KINDS:
                wellness_pending.append((time_ms, name, raw, kind))
                continue
        activity_blobs.append((name, raw, ext))

    # Wellness / daily-metric ingestion — chronological so same-day _METRICS
    # files UPSERT newest-last (the acute-load / RMR race, see _ingest_wellness_fit).
    wellness_pending.sort(key=lambda p: p[0])
    for _time_ms, name, raw, kind in wellness_pending:
        _ingest_wellness_fit(db, uid, name, raw, kind, results, summary)

    # WHOOP wellness CSVs (#767 slice 5) — auto-detected; ingested into
    # provider_raw_record via the whoop writer (the same daily_summary path the
    # standalone /whoop/import used before it was folded into this one uploader).
    for name, raw in wellness_csv_pending:
        _ingest_wellness_csv(db, uid, name, raw, results, summary)

    # Phase 1 (activities) — hash, dedup, parse. Inserts are deferred so strength
    # sessions can be applied oldest-first (rx_engine is order-aware).
    to_insert = []   # (name, gid, result)
    seen = set()
    for name, raw, ext in activity_blobs:
        gid = _fit_dedup_id(raw, prefix)
        if gid in seen or _already_imported(db, gid, source):
            results.append({'name': name, 'status': 'duplicate', 'detail': 'already imported'})
            summary['duplicates'] += 1
            continue
        try:
            result = _ACTIVITY_PARSERS[ext](raw)
        except ValueError as e:
            msg = str(e)
            if ext == 'fit' and 'session' in msg.lower():
                # Not an activity after all (e.g. an older wellness file with no
                # FileIdMessage) — route to wellness ingestion rather than drop it.
                _ingest_wellness_fit(db, uid, name, raw, 'wellness', results, summary)
            else:
                results.append({'name': name, 'status': 'error', 'detail': msg})
                summary['errors'] += 1
            continue
        except Exception as e:
            results.append({'name': name, 'status': 'error', 'detail': str(e)})
            summary['errors'] += 1
            continue
        seen.add(gid)
        to_insert.append((name, gid, result))

    to_insert.sort(key=lambda it: _activity_repr_date(it[2]))

    # Phase 2 — insert + match. Each file is its own transaction so one bad
    # file can't roll back the rest of the batch. Matching runs here (not in
    # phase 1) so each completed plan item is claimed once, in date order.
    for name, gid, result in to_insert:
        try:
            r = _bulk_log_one(db, uid, gid, result, match_plan, source)
            if r is None:
                db.rollback()
                results.append({'name': name, 'status': 'skipped', 'detail': 'unknown activity type'})
                summary['skipped'] += 1
                continue
            db.commit()
            if r.pop('matched', False):
                summary['matched'] += 1
            r['name'] = name
            results.append(r)
            summary['imported'] += 1
        except Exception as e:
            db.rollback()
            results.append({'name': name, 'status': 'error', 'detail': str(e)})
            summary['errors'] += 1

    return jsonify({'ok': True, 'summary': summary, 'results': results})


def _already_imported(db, gid: str, source: str = 'garmin') -> bool:
    """Return True if this dedup id is already in cardio_log or training_log for
    the current user, in the provider-id column matching the upload `source`
    (#767 slice 1). Two users sharing an account import independently."""
    uid = current_user_id()
    col = _source_column(source)
    if db.execute(
        f'SELECT id FROM cardio_log WHERE {col}=? AND user_id=?', (gid, uid)
    ).fetchone() is not None:
        return True
    # training_log carries every provider-id column except strava_activity_id;
    # Strava exports no strength FITs, so a Strava strength dup can't occur.
    if source == 'strava':
        return False
    return db.execute(
        f'SELECT id FROM training_log WHERE {col}=? AND user_id=?', (gid, uid)
    ).fetchone() is not None


def _import_activity(db, act: dict, plan_item, compliance: dict,
                     disposition: str = 'completed',
                     raw_plan_item_id=None,
                     reason: str | None = None) -> dict:
    """Insert one activity into the correct log table. Does NOT commit.

    `disposition` + `raw_plan_item_id` control the plan-item link and the
    disposition row (if any):
      - 'completed'      → log links to plan; disposition row 'completed'
      - 'swapped_for'    → log links to plan; disposition row 'swapped_for'
      - 'in_addition_to' → log standalone; no disposition row
      - 'none'           → log standalone; no disposition row

    Default args preserve the prior auto-match-only behavior: pass `plan_item`
    alone and the activity is recorded as completing it.

    Returns {'ok': bool, 'log_type': str, 'rows': int, 'error': str|None}
    """
    gid = act.get('garmin_activity_id', '')
    is_strength = act.get('_plan_sport_type') == 'strength_training'

    if raw_plan_item_id is None and plan_item:
        raw_plan_item_id = plan_item['id']
    plan_item_id = raw_plan_item_id if disposition in ('completed', 'swapped_for') else None

    # If the user picked a different plan item than the auto-match, refresh
    # plan_item + compliance so notes reflect what they actually chose.
    if raw_plan_item_id and (not plan_item or plan_item['id'] != raw_plan_item_id):
        chosen = db.execute(
            '''SELECT pi.*, tp.name as plan_name
               FROM plan_items pi
               JOIN training_plans tp ON tp.id = pi.plan_id
               WHERE pi.id = ? AND tp.user_id = ?''',
            (raw_plan_item_id, current_user_id())
        ).fetchone()
        if chosen:
            plan_item = dict(chosen)
            compliance = compute_compliance(act, plan_item)

    notes_parts = []
    if plan_item:
        verb = {
            'completed': 'Auto-matched',
            'swapped_for': 'Swapped for',
            'in_addition_to': 'In addition to',
            'none': 'Unmatched from',
        }.get(disposition, 'Auto-matched')
        notes_parts.append(f'{verb}: "{plan_item["workout_name"]}"')
        if compliance.get('duration_pct') is not None:
            notes_parts.append(f"Duration {compliance['duration_pct']}% of target")
        if compliance.get('distance_pct') is not None:
            notes_parts.append(f"Distance {compliance['distance_pct']}% of target")
    if reason and disposition in ('swapped_for', 'in_addition_to'):
        notes_parts.append(f'Reason: {reason}')
    notes = '. '.join(notes_parts) or None

    uid = current_user_id()
    if is_strength:
        try:
            from garmin_connect import download_activity_fit
            from garmin_fit_parser import parse_fit
            fit_bytes = download_activity_fit(db, gid)
            parsed = parse_fit(fit_bytes)
        except Exception as e:
            return {'ok': False, 'log_type': 'strength', 'rows': 0, 'error': str(e)}

        rows = parsed.get('data', []) if parsed.get('log_type') == 'strength' else []
        if rows:
            session_date = rows[0]['date'] if rows else date.today().isoformat()
            sess_cur = db.execute(
                'INSERT INTO training_sessions (date, notes, plan_item_id, user_id) VALUES (?,?,?,?) RETURNING id',
                (session_date, notes, plan_item_id, uid)
            )
            session_id = sess_cur.lastrowid

            body_wt_row = db.execute(
            'SELECT weight_kg FROM body_metrics WHERE user_id = ? '
            'ORDER BY date DESC LIMIT 1',
            (uid,)
        ).fetchone()
            body_weight = body_wt_row['weight_kg'] if body_wt_row else None

            for row in rows:
                exercise = row.get('exercise', '')
                sets = row.get('sets', [])

                actual_sets = len(sets)
                last_reps = sets[-1].get('reps') if sets else None
                all_weights = [s.get('weight_kg') or 0 for s in sets]
                max_weight = max(all_weights) if all_weights else None
                if max_weight == 0:
                    max_weight = None
                last_duration = sets[-1].get('duration_sec') if sets else None
                volume = sum((s.get('reps') or 0) * (s.get('weight_kg') or 0) for s in sets) or None
                if volume == 0:
                    volume = None
                all_1rms = [calculate_1rm(s.get('weight_kg'), s.get('reps')) or 0 for s in sets]
                est_1rm = max(all_1rms) if all_1rms else None
                if est_1rm == 0:
                    est_1rm = None

                # Auto-imported strength: FIT files don't carry plan targets,
                # so this runs in bootstrap mode (seeds baseline + projects next).
                rx = apply_session_outcome(
                    db, exercise, row.get('date'), sets,
                    rx_source='From FIT Import', user_id=uid,
                )

                log_cur = db.execute(
                    '''INSERT INTO training_log
                       (date, exercise, sub_group, session_id,
                        actual_sets, actual_reps, actual_weight, actual_duration,
                        outcome, est_1rm, volume, body_weight,
                        next_weight, next_sets, next_reps, next_duration,
                        garmin_activity_id, plan_item_id, notes, user_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
                    (row.get('date'), exercise, rx['movement_pattern'], session_id,
                     actual_sets, last_reps, max_weight, last_duration,
                     rx['outcome'], est_1rm, volume, body_weight,
                     rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
                     gid, plan_item_id, notes, uid)
                )
                log_id = log_cur.lastrowid

                for i, s in enumerate(sets, 1):
                    db.execute(
                        'INSERT INTO training_log_sets (training_log_id, set_number, reps, weight_kg, duration_sec, user_id) VALUES (?,?,?,?,?,?)',
                        (log_id, i, s.get('reps'), s.get('weight_kg'), s.get('duration_sec'), uid)
                    )

            if raw_plan_item_id:
                first_log = db.execute(
                    'SELECT id FROM training_log WHERE session_id=? AND user_id=? '
                    'ORDER BY id LIMIT 1',
                    (session_id, uid)
                ).fetchone()
                if first_log:
                    _record_disposition_for_import(
                        db, disposition, plan_item_id, raw_plan_item_id,
                        'strength', first_log['id'], reason, user_id=uid,
                    )
            return {'ok': True, 'log_type': 'strength', 'rows': len(rows), 'error': None}
        # FIT didn't yield strength data — fall through to cardio insert

    cur = db.execute(
        '''INSERT INTO cardio_log
           (date, activity, activity_name, duration_min, moving_time_min,
            distance_mi, avg_pace, avg_speed, avg_hr, max_hr, calories,
            elev_gain_ft, elev_loss_ft, avg_cadence,
            avg_power, max_power, norm_power, aerobic_te, anaerobic_te,
            discipline_id, garmin_activity_id, plan_item_id, notes, user_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
        (act.get('date'), act.get('activity'), act.get('activity_name'),
         act.get('duration_min'), act.get('moving_time_min'),
         act.get('distance_mi'), act.get('avg_pace'), act.get('avg_speed'),
         act.get('avg_hr'), act.get('max_hr'), act.get('calories'),
         act.get('elev_gain_ft'), act.get('elev_loss_ft'), act.get('avg_cadence'),
         act.get('avg_power'), act.get('max_power'), act.get('norm_power'),
         act.get('aerobic_te'), act.get('anaerobic_te'),
         act.get('discipline_id'), gid, plan_item_id, notes, uid)
    )
    _record_provider_raw_cardio(db, act.get('_provider_raw'), uid, gid)
    if raw_plan_item_id:
        _record_disposition_for_import(
            db, disposition, plan_item_id, raw_plan_item_id,
            'cardio', cur.lastrowid, reason, user_id=uid,
        )
    return {'ok': True, 'log_type': 'cardio', 'rows': 1, 'error': None}


def _build_preview(db, raw_activities: list) -> list:
    """Turn raw Garmin API activity list into a preview list for the template or API."""
    from garmin_connect import normalize_activity
    preview = []
    for a in raw_activities:
        norm = normalize_activity(a)
        gid = norm.get('garmin_activity_id', '')
        already = _already_imported(db, gid)
        match = find_best_match(db, norm)
        plan_item = match['plan_item'] if match else None
        compliance = compute_compliance(norm, plan_item)
        nearby = candidate_plan_items(db, norm.get('date'))
        preview.append({
            'activity': norm,
            'already_imported': already,
            'plan_item': dict(plan_item) if plan_item else None,
            'compliance': compliance,
            'match_score': match['score'] if match else None,
            'match_day_offset': match['day_offset'] if match else None,
            'nearby': [dict(r) for r in nearby],
        })
    return preview


@bp.route('/sync', methods=['GET', 'POST'])
def sync():
    db = get_db()
    try:
        from garmin_connect import get_auth_status
        auth_status = get_auth_status(db)
    except Exception:
        auth_status = {'authenticated': False, 'username': None}

    if not auth_status['authenticated']:
        flash('Please authenticate with Garmin Connect first.', 'warning')
        return redirect(url_for('garmin.auth'))

    default_start = (date.today() - timedelta(days=7)).isoformat()
    default_end = date.today().isoformat()

    if request.method == 'POST':
        start_date = request.form.get('start_date') or default_start
        end_date = request.form.get('end_date') or default_end
        try:
            from garmin_connect import fetch_activities
            raw = fetch_activities(db, start_date, end_date)
        except Exception as e:
            flash(f'Failed to fetch from Garmin Connect: {e}', 'danger')
            return redirect(url_for('garmin.sync'))

        preview = _build_preview(db, raw)

        # `nearby` is only used for template rendering (per-row dropdown
        # candidates); confirm just reads form fields. Drop it from the session
        # copy to keep the cookie under 4 KB.
        flask_session['garmin_sync_preview'] = [
            {k: v for k, v in item.items() if k != 'nearby'} for item in preview
        ]

        # All-scheduled fallback list shared across rows. Per-row `nearby` is
        # already on each preview item.
        all_scheduled = db.execute(
            '''SELECT pi.id, pi.item_date, pi.workout_name, pi.sport_type,
                      pi.target_duration_min, pi.target_distance_mi,
                      tp.name as plan_name
               FROM plan_items pi
               JOIN training_plans tp ON tp.id = pi.plan_id
               WHERE tp.user_id = ?
                 AND pi.status = 'scheduled' AND tp.status != 'archived'
               ORDER BY pi.item_date ASC
               LIMIT 60''',
            (current_user_id(),)
        ).fetchall()
        return render_template('garmin/sync_preview.html', preview=preview,
                               all_scheduled=[dict(r) for r in all_scheduled],
                               start_date=start_date, end_date=end_date)

    return render_template('garmin/sync.html', auth_status=auth_status,
                           default_start=default_start, default_end=default_end)


@bp.route('/sync/confirm', methods=['POST'])
def sync_confirm():
    preview = flask_session.get('garmin_sync_preview', [])
    if not preview:
        flash('Session expired — please fetch again.', 'warning')
        return redirect(url_for('garmin.sync'))

    selected = set(request.form.getlist('selected_ids'))
    db = get_db()
    imported = matched = swapped = added = errors = 0

    def _num(v):
        try:
            return int(v) if v not in (None, '', '0') else None
        except (TypeError, ValueError):
            return None

    for item in preview:
        gid = item['activity'].get('garmin_activity_id', '')
        if gid not in selected or item['already_imported']:
            continue

        # Per-row resolve. Defaults preserve auto-match-as-completed when the
        # user didn't touch the row.
        default_disp = 'completed' if item.get('plan_item') else 'none'
        disposition = request.form.get(f'disposition_{gid}', default_disp)
        raw_pid = _num(request.form.get(f'plan_item_id_{gid}'))
        if raw_pid is None and item.get('plan_item'):
            raw_pid = item['plan_item']['id']
        reason = (request.form.get(f'swap_reason_{gid}') or '').strip() or None

        result = _import_activity(
            db, item['activity'], item.get('plan_item'),
            item.get('compliance', {}),
            disposition=disposition,
            raw_plan_item_id=raw_pid,
            reason=reason,
        )
        if result['ok']:
            imported += result['rows']
            if disposition == 'completed' and raw_pid:
                matched += 1
            elif disposition == 'swapped_for' and raw_pid:
                swapped += 1
            elif disposition == 'in_addition_to':
                added += 1
        else:
            errors += 1
            flash(f"Error importing {item['activity'].get('activity_name')}: {result['error']}", 'warning')

    db.commit()
    flask_session.pop('garmin_sync_preview', None)
    msg = f'{imported} activit{"y" if imported == 1 else "ies"} imported'
    bits = []
    if matched:
        bits.append(f'{matched} matched')
    if swapped:
        bits.append(f'{swapped} swapped')
    if added:
        bits.append(f'{added} added alongside plan')
    if bits:
        msg += ' (' + ', '.join(bits) + ')'
    if errors:
        msg += f', {errors} error(s)'
    flash(msg + '.', 'success')
    return redirect(url_for('connections.hub', tab='files'))


@bp.route('/api/sync', methods=['POST'])
def api_sync():
    """Headless sync endpoint for Claude Desktop remote triggering.

    POST JSON: {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
    Returns import summary with per-activity results.
    """
    data = request.get_json(silent=True) or {}
    start_date = data.get('start_date', (date.today() - timedelta(days=7)).isoformat())
    end_date = data.get('end_date', date.today().isoformat())

    db = get_db()
    try:
        from garmin_connect import get_auth_status, fetch_activities
        if not get_auth_status(db)['authenticated']:
            return jsonify({'ok': False, 'error': 'Not authenticated with Garmin Connect'}), 401
        raw = fetch_activities(db, start_date, end_date)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    preview = _build_preview(db, raw)
    imported = matched = skipped = 0
    activity_log = []

    for item in preview:
        act = item['activity']
        name = act.get('activity_name') or act.get('activity')
        if item['already_imported']:
            skipped += 1
            activity_log.append({'name': name, 'date': act['date'], 'status': 'already_imported'})
            continue
        result = _import_activity(db, act, item.get('plan_item'), item.get('compliance', {}))
        if result['ok']:
            imported += result['rows']
            if item.get('plan_item'):
                matched += 1
            activity_log.append({
                'name': name,
                'date': act['date'],
                'log_type': result['log_type'],
                'plan_match': item['plan_item']['workout_name'] if item.get('plan_item') else None,
                'compliance': item['compliance'].get('label'),
                'status': 'imported',
            })
        else:
            activity_log.append({'name': name, 'date': act['date'], 'status': 'error', 'error': result['error']})

    db.commit()
    return jsonify({
        'ok': True,
        'date_range': {'start': start_date, 'end': end_date},
        'imported': imported,
        'matched': matched,
        'skipped': skipped,
        'activities': activity_log,
    })


@bp.route('/auth')
def auth():
    try:
        from garmin_connect import get_auth_status
        status = get_auth_status(get_db())
    except Exception:
        status = {'authenticated': False, 'username': None}
    return render_template('garmin/auth.html', status=status)


@bp.route('/auth/login', methods=['POST'])
def auth_login():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    mfa_code = request.form.get('mfa_code', '').strip() or None
    if not email or not password:
        flash('Email and password are required.', 'danger')
        return redirect(url_for('garmin.auth'))
    try:
        from garmin_connect import login
        login(get_db(), email, password, mfa_code)
        flash('Successfully authenticated with Garmin Connect.', 'success')
    except Exception as e:
        flash(f'Authentication failed: {e}', 'danger')
    return redirect(url_for('garmin.auth'))


@bp.route('/auth/import-cookies', methods=['POST'])
def auth_import_cookies():
    import json
    cookie_string = request.form.get('cookie_string', '').strip()
    if not cookie_string:
        flash('No cookie string provided.', 'danger')
        return redirect(url_for('garmin.auth'))
    session_data = json.dumps({'type': 'browser_cookie', 'cookie': cookie_string})
    db = get_db()
    uid = current_user_id()
    existing = db.execute('SELECT id FROM garmin_auth WHERE user_id=? LIMIT 1', (uid,)).fetchone()
    if existing:
        db.execute(
            "UPDATE garmin_auth SET garth_session=?, garmin_username=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (session_data, '', existing[0])
        )
    else:
        db.execute(
            'INSERT INTO garmin_auth (garth_session, garmin_username, user_id) VALUES (?,?,?)',
            (session_data, '', uid)
        )
    db.commit()
    flash('Browser session cookies saved. Testing connection on the sync page.', 'success')
    return redirect(url_for('garmin.auth'))


@bp.route('/import-wellness', methods=['GET', 'POST'])
def import_wellness():
    if request.method == 'GET':
        return render_template('garmin/import_wellness.html', preview=None)

    f = request.files.get('fit_file')
    if not f or not f.filename:
        flash('No file selected.', 'warning')
        return redirect(url_for('garmin.import_wellness'))

    fname = secure_filename(f.filename or '').lower()
    if not (fname.endswith('.fit') or fname.endswith('.zip')):
        flash('File must be a .fit or .zip file.', 'danger')
        return redirect(url_for('garmin.import_wellness'))

    try:
        raw = f.read()
        if fname.endswith('.zip'):
            import zipfile, io
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                fit_names = [n for n in zf.namelist() if n.lower().endswith('.fit')]
                if not fit_names:
                    flash('No .fit file found inside the zip.', 'danger')
                    return redirect(url_for('garmin.import_wellness'))
                raw = zf.read(fit_names[0])

        from garmin_fit_parser import parse_wellness_fit
        rows = parse_wellness_fit(raw)

        if not rows:
            flash('No wellness data found in this FIT file. Make sure it\'s a wellness/monitoring file, not an activity file.', 'warning')
            return redirect(url_for('garmin.import_wellness'))

        # Write parsed rows to a temp file — avoids cookie session size limits
        tmp_path = os.path.join(tempfile.gettempdir(), f'wellness_{uuid.uuid4().hex}.json')
        with open(tmp_path, 'w') as fh:
            json.dump(rows, fh)
        flask_session['wellness_tmp'] = tmp_path

        # Build preview summary
        dates = sorted({r['date'] for r in rows if r['date']})
        counts = {
            'total': len(rows),
            'heart_rate': sum(1 for r in rows if r.get('heart_rate')),
            'stress_level': sum(1 for r in rows if r.get('stress_level')),
            'body_battery': sum(1 for r in rows if r.get('body_battery')),
            'respiration_rate': sum(1 for r in rows if r.get('respiration_rate')),
            'steps': sum(1 for r in rows if r.get('steps')),
        }
        preview = {
            'date_min': dates[0] if dates else '?',
            'date_max': dates[-1] if dates else '?',
            'date_count': len(dates),
            'counts': counts,
            'sample': rows[:8],
        }
        return render_template('garmin/import_wellness.html', preview=preview)

    except Exception as e:
        flash(f'Error parsing wellness FIT file: {e}', 'danger')
        return redirect(url_for('garmin.import_wellness'))


@bp.route('/import-wellness/confirm', methods=['POST'])
def import_wellness_confirm():
    tmp_path = flask_session.get('wellness_tmp')
    if not tmp_path or not os.path.exists(tmp_path):
        flash('Session expired or data missing. Please re-upload the file.', 'warning')
        return redirect(url_for('garmin.import_wellness'))

    try:
        with open(tmp_path) as fh:
            rows = json.load(fh)
    except Exception:
        flash('Could not read parsed data. Please re-upload.', 'danger')
        return redirect(url_for('garmin.import_wellness'))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        flask_session.pop('wellness_tmp', None)

    db = get_db()
    uid = current_user_id()
    inserted = skipped = 0

    for row in rows:
        try:
            cur = db.execute(
                '''INSERT INTO wellness_log
                   (date, timestamp_ms, heart_rate, stress_level, body_battery,
                    respiration_rate, steps, active_calories, active_time_s,
                    distance_m, activity_type, user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(user_id, timestamp_ms) DO NOTHING RETURNING id''',
                (row.get('date'), row.get('timestamp_ms'), row.get('heart_rate'),
                 row.get('stress_level'), row.get('body_battery'),
                 row.get('respiration_rate'), row.get('steps'),
                 row.get('active_calories'), row.get('active_time_s'),
                 row.get('distance_m'), row.get('activity_type'), uid)
            )
            # _CompatCursor exposes no .rowcount; RETURNING yields a row only
            # when a row was actually inserted (none on ON CONFLICT DO NOTHING).
            if cur.fetchone():
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1

    db.commit()

    msg = f'{inserted} wellness records imported'
    if skipped:
        msg += f', {skipped} already existed (skipped)'
    flash(msg + '.', 'success')
    return redirect(url_for('garmin.wellness_log'))


def _bulk_insert_wellness(db, rows: list, uid: int, chunk: int = 500) -> tuple:
    """Insert wellness rows in chunked multi-row INSERTs.

    Returns (inserted, duplicates). ON CONFLICT (user_id, timestamp_ms) DO
    NOTHING + RETURNING makes re-imports skip seconds already stored, and the
    count reflects only genuinely new rows. Chunking keeps each statement small
    enough for thousands of per-second readings without a round-trip per row."""
    cols_sql = ('date, timestamp_ms, heart_rate, stress_level, body_battery, '
                'respiration_rate, steps, active_calories, active_time_s, '
                'distance_m, activity_type, user_id')
    ncol = 12  # the columns above, including user_id
    inserted = 0
    total = 0
    for start in range(0, len(rows), chunk):
        batch = rows[start:start + chunk]
        if not batch:
            continue
        total += len(batch)
        one = '(' + ','.join(['?'] * ncol) + ')'
        placeholders = ','.join([one] * len(batch))
        params = []
        for r in batch:
            params.extend([
                r.get('date'), r.get('timestamp_ms'), r.get('heart_rate'),
                r.get('stress_level'), r.get('body_battery'),
                r.get('respiration_rate'), r.get('steps'),
                r.get('active_calories'), r.get('active_time_s'),
                r.get('distance_m'), r.get('activity_type'), uid,
            ])
        sql = (f'INSERT INTO wellness_log ({cols_sql}) VALUES {placeholders} '
               'ON CONFLICT (user_id, timestamp_ms) DO NOTHING RETURNING id')
        cur = db.execute(sql, params)
        inserted += len(cur.fetchall())
    return inserted, total - inserted


def _wellness_skip_detail(name: str) -> str:
    """Accurate skip reason for a file that yielded no wellness readings.

    `parse_wellness_fit` only extracts the five per-second streams (heart
    rate, stress, body battery, respiration, steps). _METRICS / _SLEEP_DATA
    / _HRV_STATUS files are routed away from this parser by the bulk
    importer (#283 Phase B), so a file landing here is genuinely empty or
    of an unrecognized type. Use the Garmin filename convention as a hint
    so the message isn't misleading."""
    upper = (name or '').upper()
    if 'ACTIVITY' in upper:
        return 'activity file — import it on the Garmin → Import FIT page instead'
    return ('no supported wellness readings found '
            '(heart rate, stress, body battery, respiration, steps)')


_DAILY_METRICS_COLUMNS = (
    'sleep_score', 'sleep_start_ms', 'sleep_end_ms', 'sleep_awake_min',
    # sleep_avg_respiration retired in the field-mapping audit (Jun 7):
    # [384] field_18 was a coincidence on May 28 (=13 matched 13 brpm) but
    # diverged on May 30 / Jun 2. Column kept nullable so old rows don't
    # need a DROP; new uploads stop writing it.
    'sleep_avg_respiration', 'sleep_contributors_json',
    'sleep_light_sub_score', 'sleep_rem_sub_score',
    'sleep_stress_sub_score', 'sleep_awake_sub_score',
    'sleep_stress_above_resting_pct', 'sleep_onset_latency_sec',
    'sleep_stage_raw_min_json',
    'sleep_deep_min', 'sleep_light_min', 'sleep_rem_min',
    'sleep_stress_avg', 'sleep_wake_count',
    'sleep_duration_sub_score', 'restless_moments',
    'hrv_overnight_avg_ms', 'hrv_7d_avg_ms', 'hrv_highest_5min_ms',
    'hrv_samples_json',
    'training_readiness', 'vo2max_running', 'vo2max_cycling',
    'spo2_avg', 'spo2_low',
    'resting_metabolic_rate', 'resting_hr', 'resting_hr_7day_avg',
    'heat_acclimation_pct', 'acute_training_load',
    'floors_climbed', 'floors_descended', 'intensity_minutes',
)


def _upsert_garmin_daily_metrics(db, uid: int, date: str, fields: dict) -> bool:
    """UPSERT one day's derived metrics. Only the keys present in `fields`
    are touched — a `_HRV_STATUS.fit` upload won't clobber a sleep_score
    that a `_METRICS.fit` upload already wrote for the same date. Returns
    True if any column actually changed."""
    cols = [c for c in _DAILY_METRICS_COLUMNS if c in fields]
    if not cols:
        return False
    set_clause = ', '.join(f'{c} = COALESCE(EXCLUDED.{c}, daily_wellness_metrics.{c})'
                           for c in cols)
    col_sql = ', '.join(cols)
    placeholder_sql = ', '.join(['?'] * len(cols))
    values = [fields[c] for c in cols]
    db.execute(
        f'INSERT INTO daily_wellness_metrics (user_id, date, {col_sql}, updated_at) '
        f'VALUES (?, ?, {placeholder_sql}, NOW()) '
        f'ON CONFLICT (user_id, date) DO UPDATE SET '
        f'{set_clause}, updated_at = NOW()',
        [uid, date, *values],
    )
    return True


def _metrics_to_db_fields(parsed: dict) -> dict:
    """Translate the parser's dict shape into `daily_wellness_metrics` column
    values. Lists land as JSON strings; ms timestamps pass through."""
    out: dict = {}
    # sleep_avg_respiration intentionally NOT in this list — retired Jun 7
    # after the May 28 field_18 match was disproved by Jun 2 data.
    for key in ('sleep_score', 'sleep_start_ms', 'sleep_end_ms',
                'sleep_awake_min',
                'sleep_duration_sub_score', 'restless_moments',
                'sleep_light_sub_score', 'sleep_rem_sub_score',
                'sleep_stress_sub_score', 'sleep_awake_sub_score',
                'sleep_stress_above_resting_pct', 'sleep_onset_latency_sec',
                'hrv_overnight_avg_ms', 'hrv_7d_avg_ms',
                'hrv_highest_5min_ms',
                'training_readiness', 'vo2max_running', 'vo2max_cycling',
                'spo2_avg', 'spo2_low',
                'sleep_deep_min', 'sleep_light_min', 'sleep_rem_min',
                'sleep_stress_avg', 'sleep_wake_count',
                'resting_metabolic_rate', 'resting_hr',
                'resting_hr_7day_avg',
                'heat_acclimation_pct', 'acute_training_load',
                'floors_climbed', 'floors_descended', 'intensity_minutes'):
        if key in parsed:
            out[key] = parsed[key]
    if 'sleep_contributors' in parsed:
        out['sleep_contributors_json'] = json.dumps(parsed['sleep_contributors'])
    # Raw [275] stage tally (#524) — `{code: minutes}` from _SLEEP_DATA.fit.
    # JSON-encoded so the route can recover it for the smoothing-delta chart.
    if 'sleep_stage_minutes_by_code_partial' in parsed:
        out['sleep_stage_raw_min_json'] = json.dumps(
            parsed['sleep_stage_minutes_by_code_partial']
        )
    if 'hrv_samples' in parsed:
        # Compact list of [ts_ms, ms_value] pairs for the overnight chart.
        out['hrv_samples_json'] = json.dumps(parsed['hrv_samples'])
    return out


def _ingest_wellness_fit(db, uid, name, raw, kind, results, summary):
    """Ingest one non-activity .FIT — daily metrics (`_METRICS`/`_SLEEP_DATA`/
    `_HRV_STATUS`) into daily_wellness_metrics, or per-second `_WELLNESS` data into
    wellness_log (+ daily extras). Appends one row to `results` and updates
    `summary` in place. Shared by the wellness bulk endpoint and the unified
    activity+wellness bulk endpoint so both route files identically.
    """
    from garmin_fit_parser import (
        parse_wellness_fit, parse_wellness_daily_extras,
        parse_metrics_fit, parse_sleep_data_fit, parse_hrv_status_fit,
    )
    if kind in ('metrics', 'sleep_data', 'hrv_status'):
        parser = {
            'metrics':    parse_metrics_fit,
            'sleep_data': parse_sleep_data_fit,
            'hrv_status': parse_hrv_status_fit,
        }[kind]
        try:
            parsed = parser(raw)
        except Exception as e:
            db.rollback()
            results.append({'name': name, 'status': 'error', 'detail': str(e)})
            summary['errors'] += 1
            return
        if not parsed or 'date' not in parsed:
            results.append({'name': name, 'status': 'skipped',
                            'detail': f'no {kind} fields recognized'})
            summary['skipped'] += 1
            return
        try:
            fields = _metrics_to_db_fields(parsed)
            wrote = _upsert_garmin_daily_metrics(db, uid, parsed['date'], fields)
            # #196 Phase 2 Slice 2.2 — rebuild the canonical daily-wellness row
            # for the day we just wrote, atomically with the upsert.
            materialize_canonical_wellness(db, uid, parsed['date'])
            db.commit()
            detail_keys = ', '.join(sorted(fields.keys())) or '(no columns)'
            results.append({'name': name, 'status': 'imported',
                            'detail': f"{kind} · {parsed['date']} · {detail_keys}"})
            if wrote:
                summary['metrics_days'] += 1
            summary['files'] += 1
        except Exception as e:
            db.rollback()
            results.append({'name': name, 'status': 'error', 'detail': str(e)})
            summary['errors'] += 1
        return

    # Wellness path (kind == 'wellness' or 'unknown' — older files w/o
    # FileIdMessage fall here too, and parse_wellness_fit will return [] if
    # there's truly nothing recognizable).
    try:
        rows = parse_wellness_fit(raw)
    except Exception as e:
        db.rollback()
        results.append({'name': name, 'status': 'error', 'detail': str(e)})
        summary['errors'] += 1
        return
    if not rows:
        results.append({'name': name, 'status': 'skipped',
                        'detail': _wellness_skip_detail(name)})
        summary['skipped'] += 1
        return
    try:
        ins, dup = _bulk_insert_wellness(db, rows, uid)
        # Also harvest the daily-aggregate values that live in WELLNESS files
        # (resting metabolic rate, resting HR, 7d-avg resting HR). Best-effort:
        # a parse failure here shouldn't fail the per-second insert above.
        extras_date = None
        try:
            extras = parse_wellness_daily_extras(raw)
            if extras.get('date'):
                extras_fields = {
                    k: v for k, v in extras.items()
                    if k in ('resting_metabolic_rate', 'resting_hr',
                             'resting_hr_7day_avg',
                             'floors_climbed', 'floors_descended',
                             'intensity_minutes',
                             'spo2_avg', 'spo2_low')
                }
                if extras_fields:
                    _upsert_garmin_daily_metrics(
                        db, uid, extras['date'], extras_fields,
                    )
                    extras_date = extras['date']
        except Exception:
            pass
        # #196 Phase 2 Slice 2.2 — rebuild the canonical row for the day whose
        # daily aggregates (incl. resting_hr) we just wrote. OUTSIDE the
        # best-effort harvest above on purpose: a materialize failure must
        # surface (the outer except rolls back the whole file) rather than be
        # swallowed by `pass` and then poison the wellness_log commit below.
        if extras_date:
            materialize_canonical_wellness(db, uid, extras_date)
        db.commit()
        dates = sorted({r['date'] for r in rows if r.get('date')})
        drange = dates[0] if dates else '?'
        if len(dates) > 1:
            drange += f' → {dates[-1]}'
        results.append({'name': name, 'status': 'imported',
                        'detail': f'{ins} new, {dup} dup · {drange}'})
        summary['imported'] += ins
        summary['duplicates'] += dup
        summary['files'] += 1
    except Exception as e:
        db.rollback()
        results.append({'name': name, 'status': 'error', 'detail': str(e)})
        summary['errors'] += 1


def _ingest_wellness_csv(db, uid, name, raw, results, summary):
    """Ingest one auto-detected WHOOP `physiological_cycles.csv` (#767 slice 5)
    into provider_raw_record via the whoop writer. Appends one row to `results`
    and updates `summary` in place — same contract as `_ingest_wellness_fit`, so
    the unified uploader routes a wellness CSV exactly like a wellness FIT. A CSV
    that isn't a usable WHOOP export is reported as an error, not dropped."""
    from routes.whoop import ingest_whoop_csv
    try:
        days = ingest_whoop_csv(db, uid, raw)
        db.commit()
    except ValueError as e:
        db.rollback()
        results.append({'name': name, 'status': 'error',
                        'detail': f'not a usable WHOOP CSV: {e}'})
        summary['errors'] += 1
        return
    except Exception as e:
        db.rollback()
        results.append({'name': name, 'status': 'error', 'detail': str(e)})
        summary['errors'] += 1
        return
    results.append({'name': name, 'status': 'imported',
                    'detail': f'WHOOP wellness · {days} day(s)'})
    summary['files'] += 1
    summary['metrics_days'] += days
    print(  # Rule #15 — where this CSV landed
        f"[bulk-import] wellness-csv name={name} provider=whoop "
        f"ingested {days} day(s)"
    )


@bp.route('/import-wellness/bulk', methods=['POST'])
def import_wellness_bulk():
    """Parse many Garmin daily FITs and merge them into the right table:

      - `_WELLNESS.fit` (per-second monitoring) → `wellness_log`
      - `_METRICS.fit` / `_SLEEP_DATA.fit` / `_HRV_STATUS.fit` (daily-derived
        metrics) → `daily_wellness_metrics`, UPSERTed by (user, date) so the
        three file types can land in any order and each contributes the
        columns it owns

    Duplicate per-second readings are skipped at the wellness_log layer.
    Returns JSON for the drag-and-drop UI.
    """
    db = get_db()
    uid = current_user_id()
    files = request.files.getlist('files')
    if not files:
        return jsonify({'ok': False, 'error': 'No files in request.'}), 400

    from garmin_fit_parser import fit_file_meta

    results = []
    summary = {'imported': 0, 'duplicates': 0, 'skipped': 0, 'errors': 0,
               'files': 0, 'metrics_days': 0}

    # Pre-pass: pull (kind, time_created_ms) once per file so we can sort
    # chronologically. Without this, three _METRICS.fit files for the same
    # day in arbitrary zip order can have the earliest UPSERT clobber the
    # latest value of acute_training_load / RMR / etc. — Andy's Jun 2 upload
    # had ATL = 95 → 107 → 126 across the morning/midday/evening syncs.
    pending = []
    # _iter_activity_blobs expands .zip → its entries and yields a 4-tuple
    # (name, bytes, ext, err). This endpoint is Garmin wellness-FIT only, so we
    # gate on ext == 'fit' and skip any stray .tcx/.gpx/.csv. (It was renamed
    # from _iter_fit_blobs in #767 Slice 2; the wellness call site was missed,
    # so every upload here 500'd on a NameError from 2026-06-19 until this fix.)
    for name, raw, ext, err in _iter_activity_blobs(files):
        if err:
            results.append({'name': name, 'status': 'skipped', 'detail': err})
            summary['skipped'] += 1
            continue
        if ext != 'fit':
            results.append({'name': name, 'status': 'skipped',
                            'detail': 'not a Garmin wellness .fit file'})
            summary['skipped'] += 1
            continue
        try:
            kind, time_ms = fit_file_meta(raw)
        except Exception as e:
            db.rollback()
            results.append({'name': name, 'status': 'error', 'detail': str(e)})
            summary['errors'] += 1
            continue
        # Tuples sort lexically; time_ms == 0 (no FileIdMessage) sorts to
        # the front, which is fine — those files write only wellness_log
        # per-second rows and don't compete with the metrics UPSERT race.
        pending.append((time_ms, name, raw, kind))

    # Stable chronological order. files keep their relative within-second
    # ordering, which is also stable in `pending.sort`.
    pending.sort(key=lambda p: p[0])

    for _time_ms, name, raw, kind in pending:
        _ingest_wellness_fit(db, uid, name, raw, kind, results, summary)

    # Rule #15 — this path was print-silent, which is exactly why a dead call
    # site (the NameError above) couldn't be spotted from /admin/logs. Log the
    # per-file disposition for skips/errors + a summary so it's diagnosable.
    for r in results:
        if r['status'] in ('skipped', 'error'):
            print(f"[wellness-import] user={uid} {r['status']}: "
                  f"{r['name']} — {r.get('detail', '')}")
    print(f"[wellness-import] user={uid} files={summary['files']} "
          f"metrics_days={summary['metrics_days']} imported={summary['imported']} "
          f"dup={summary['duplicates']} skipped={summary['skipped']} "
          f"errors={summary['errors']}")
    return jsonify({'ok': True, 'summary': summary, 'results': results})


@bp.route('/wellness')
def wellness_log():
    db = get_db()
    uid = current_user_id()
    date_filter = request.args.get('date', '')

    # Default to most recent date if none selected, so the chart has something to draw
    if not date_filter:
        latest = db.execute(
            'SELECT date FROM wellness_log WHERE user_id = ? '
            'ORDER BY date DESC LIMIT 1',
            (uid,)
        ).fetchone()
        if latest:
            date_filter = latest['date']

    query = 'SELECT * FROM wellness_log WHERE user_id = ?'
    params = [uid]
    if date_filter:
        query += ' AND date = ?'
        params.append(date_filter)
    query += ' ORDER BY timestamp_ms DESC LIMIT 2000'
    rows = db.execute(query, params).fetchall()

    # Chart data: ASC by time, only for the single selected day. Each series
    # carries its own x to skip nulls cleanly in Chart.js.
    chart_data = None
    if date_filter and rows:
        asc = sorted([dict(r) for r in rows], key=lambda r: r['timestamp_ms'])
        def series(field):
            return [{'x': r['timestamp_ms'], 'y': r[field]}
                    for r in asc if r.get(field) is not None]
        chart_data = {
            'date': date_filter,
            'heart_rate':       series('heart_rate'),
            'stress_level':     series('stress_level'),
            'body_battery':     series('body_battery'),
            'respiration_rate': series('respiration_rate'),
        }

    # Distinct dates for the date picker
    dates = db.execute(
        'SELECT DISTINCT date FROM wellness_log WHERE user_id = ? '
        'ORDER BY date DESC LIMIT 60',
        (uid,)
    ).fetchall()

    return render_template('garmin/wellness_log.html', rows=rows,
                           dates=dates, date_filter=date_filter,
                           chart_data=chart_data)


@bp.route('/auth/import-tokens', methods=['POST'])
def auth_import_tokens():
    import json
    raw = request.form.get('token_json', '').strip()
    if not raw:
        flash('No token JSON provided.', 'danger')
        return redirect(url_for('garmin.auth'))
    try:
        token_data = json.loads(raw)
    except json.JSONDecodeError as e:
        flash(f'Invalid JSON: {e}', 'danger')
        return redirect(url_for('garmin.auth'))
    try:
        from garmin_connect import _save_session_to_db, _write_session_to_tmp, GARTH_TMP
        import garth, os
        _write_session_to_tmp(json.dumps(token_data))
        garth.resume(GARTH_TMP)
        username = getattr(garth.client, 'username', '')
        db = get_db()
        uid = current_user_id()
        existing = db.execute('SELECT id FROM garmin_auth WHERE user_id=? LIMIT 1', (uid,)).fetchone()
        session_json = json.dumps(token_data)
        if existing:
            db.execute(
                "UPDATE garmin_auth SET garth_session=?, garmin_username=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (session_json, username, existing[0])
            )
        else:
            db.execute(
                'INSERT INTO garmin_auth (garth_session, garmin_username, user_id) VALUES (?,?,?)',
                (session_json, username, uid)
            )
        db.commit()
        flash(f'Tokens imported successfully{" for " + username if username else ""}.', 'success')
    except Exception as e:
        flash(f'Token import failed: {e}', 'danger')
    return redirect(url_for('garmin.auth'))
