"""Admin dashboard.

Gated to user_id == 1 (the bootstrap user, conventionally the operator).
Adding more admin views: build them inside this blueprint and keep the
same `_require_admin()` gate at the top of every handler.
"""
import hmac
import os
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, render_template, redirect, url_for, flash, abort, request, jsonify,
)
from werkzeug.utils import secure_filename

from database import get_db
from plan_sessions_repo import load_plan_sessions_as_blocks, load_progress_blocks
from routes.auth import current_user_id

bp = Blueprint('admin', __name__, url_prefix='/admin')

ADMIN_USER_ID = 1

# D-73 Phase 5.2 — refresh-flow telemetry surface. Fixed 30-day rolling
# window per D4; aggregates only per D3; admin-only per D1; covers the
# full D-63 → D-64 funnel per D2 (ad_hoc_workout_suggestions +
# t1_hook_telemetry + plan_refresh_log).
TELEMETRY_WINDOW_DAYS = 30


def _require_admin():
    if current_user_id() != ADMIN_USER_ID:
        abort(403)


# Order matters: child rows must be deleted before their parents so the
# FK constraints don't reject the delete. Mirrors the SQL block we ran
# manually for the first test-user cleanup. Each tuple is (sql, params)
# so we can keep one with a sub-SELECT for the parent-JOIN scoped tables.
def _delete_user_and_data(db, user_id):
    db.execute('DELETE FROM training_log_sets             WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM plan_item_disposition         WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM plan_items                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM plan_reviews WHERE plan_id IN '
               '(SELECT id FROM training_plans WHERE user_id = ?)', (user_id,))
    db.execute('DELETE FROM coaching_chat                 WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM training_plans                WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM training_log                  WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM training_sessions             WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM cardio_log                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM body_metrics                  WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM conditions_log                WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM injury_exercise_modifications WHERE injury_id IN '
               '(SELECT id FROM injury_log WHERE user_id = ?)', (user_id,))
    db.execute('DELETE FROM injury_log                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM coaching_preferences          WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM feedback_log                  WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM wellness_log                  WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM wellness_self_report          WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM garmin_auth                   WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM garmin_workouts               WHERE user_id = ?', (user_id,))
    # Track 1 — locale_equipment is dropped; locale_equipment_overrides +
    # locale_toggle_overrides cascade on the locale_profiles delete below.
    db.execute('DELETE FROM locale_profiles               WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM clothing_options              WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM current_rx                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM athlete_profile               WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM user_purchase_recommendations WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM api_tokens                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM users                         WHERE id = ?',      (user_id,))


@bp.route('/')
def dashboard():
    _require_admin()
    db = get_db()
    users = db.execute(
        '''SELECT u.id, u.username, u.email, u.display_name,
                  u.created_at, u.last_login,
                  (SELECT COUNT(*) FROM training_log    WHERE user_id = u.id) AS strength_logs,
                  (SELECT COUNT(*) FROM cardio_log      WHERE user_id = u.id) AS cardio_logs,
                  (SELECT COUNT(*) FROM training_plans  WHERE user_id = u.id) AS plans
             FROM users u
            ORDER BY u.id'''
    ).fetchall()
    return render_template('admin/dashboard.html', users=users,
                           admin_user_id=ADMIN_USER_ID)


@bp.route('/fit-inspect', methods=['GET', 'POST'])
def fit_inspect():
    """Operator-only .FIT field-dump inspector.

    Relocated from the user-facing Connections/Data hub Files tab (issue
    #473) — the raw FIT field dump is developer diagnostic tooling for
    parsing issues (#458, #456), not something an athlete manages their data
    with. Parses an uploaded .FIT (or every .fit inside a .zip) and renders
    the dump. Reuses `garmin_fit_parser._dump_fit` — no parsing-logic change,
    just a relocation behind the admin gate.
    """
    _require_admin()
    dumps = None
    scan_matches = None
    value_match_results = None
    # `target` defaults to 48 (Andy's stable VO2max running — #283 follow-up).
    # `?target=X` overrides for other constant-value lookups. `_METRICS.fit`
    # GenericMessages 281/330/378/384 are the standard scan targets for
    # daily-rolled metrics, but `?scope=all` widens the search.
    try:
        scan_target = float(request.args.get('target') or 48)
    except (TypeError, ValueError):
        scan_target = 48.0
    scan_scope = (request.args.get('scope') or '').strip().lower()
    scan_message_ids = None if scan_scope == 'all' else (281, 330, 378, 384)
    # `?values=70,180,47,8` runs the per-file value-match scanner —
    # finds fields whose value matches any of the targets. Defaults to
    # Andy's May 30 Connect-smoothed stage minutes (#283 motivating
    # case): Deep=70 (already locked to [346] field_9), Light=180,
    # REM=47, Awake=8. `?values=off` disables.
    raw_values = (request.args.get('values') or '70,180,47,8').strip()
    if raw_values.lower() == 'off':
        value_targets: list = []
    else:
        value_targets = []
        for part in raw_values.split(','):
            try:
                value_targets.append(float(part.strip()))
            except (TypeError, ValueError):
                continue
    if request.method == 'POST':
        f = request.files.get('fit_file')
        if not f or not f.filename:
            flash('No file selected.', 'warning')
            return redirect(url_for('admin.fit_inspect'))
        dumps = []
        try:
            import io
            import zipfile

            from garmin_fit_parser import (
                _dump_fit, find_constant_value_fields, find_value_match_fields,
            )
            raw = f.read()
            fname = secure_filename(f.filename or '').lower()
            if fname.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    fit_names = [n for n in zf.namelist()
                                 if n.lower().endswith('.fit')]
                    if not fit_names:
                        flash('No .fit file found inside the zip.', 'danger')
                        return redirect(url_for('admin.fit_inspect'))
                    for n in fit_names[:60]:
                        try:
                            dumps.append({'name': n, 'dump': _dump_fit(zf.read(n))})
                        except Exception as e:  # noqa: BLE001 — per-entry isolation
                            dumps.append({'name': n, 'error': str(e)})
            else:
                dumps.append({'name': f.filename, 'dump': _dump_fit(raw)})
            # Cross-file constant-value scan only kicks in with ≥2 successful
            # dumps (one file admits trivially many false matches). Helps lock
            # constants like VO2max running across multiple `_METRICS.fit`
            # uploads.
            nights = [d['dump'].get('generic_samples', {})
                      for d in dumps if 'dump' in d]
            if len(nights) >= 2:
                scan_matches = find_constant_value_fields(
                    nights, scan_target, message_ids=scan_message_ids,
                )
            # Per-file value-match scan runs on every successful dump.
            # Empty `value_targets` (operator passed `?values=off`) skips.
            if value_targets:
                value_match_results = []
                for d in dumps:
                    if 'dump' not in d:
                        continue
                    value_match_results.append({
                        'name': d['name'],
                        'matches': find_value_match_fields(
                            d['dump'], value_targets,
                        ),
                    })
        except Exception as e:  # noqa: BLE001 — surface parse errors to the operator
            flash(f'Error: {e}', 'danger')
            return redirect(url_for('admin.fit_inspect'))
    return render_template(
        'admin/fit_inspect.html',
        inspect_dumps=dumps,
        inspect_scan_matches=scan_matches,
        inspect_scan_target=scan_target,
        inspect_scan_scope=('all' if scan_scope == 'all'
                            else '_METRICS.fit GenericMessages'),
        inspect_value_matches=value_match_results,
        inspect_value_targets=value_targets,
    )


@bp.route('/users/<int:user_id>')
def user_detail(user_id):
    """Per-user drill-in (§25). Identity + a data-footprint across the
    user-scoped tables + the admin-audit trail targeting this user, and
    the type-to-confirm delete dialog. Counts mirror the tables
    `_delete_user_and_data` cascades, so the operator sees exactly what a
    delete would remove. Admin-only; reads any user (operator surface)."""
    _require_admin()
    db = get_db()
    u = db.execute(
        '''SELECT u.id, u.username, u.email, u.display_name,
                  u.created_at, u.last_login,
                  (SELECT COUNT(*) FROM training_log     WHERE user_id = u.id) AS strength_logs,
                  (SELECT COUNT(*) FROM cardio_log       WHERE user_id = u.id) AS cardio_logs,
                  (SELECT COUNT(*) FROM training_plans   WHERE user_id = u.id) AS plans,
                  (SELECT COUNT(*) FROM coaching_chat    WHERE user_id = u.id) AS chat_msgs,
                  (SELECT COUNT(*) FROM locale_profiles  WHERE user_id = u.id) AS locations,
                  (SELECT COUNT(*) FROM current_rx       WHERE user_id = u.id) AS rx_entries,
                  (SELECT COUNT(*) FROM feedback_log     WHERE user_id = u.id) AS feedback_rows,
                  (SELECT COUNT(*) FROM wellness_log     WHERE user_id = u.id) AS wellness_rows
             FROM users u
            WHERE u.id = ?''',
        (user_id,),
    ).fetchone()
    if u is None:
        abort(404)
    audit_rows = db.execute(
        '''SELECT a.id, a.action, a.actor_user_id, au.username AS actor_username,
                  a.details, a.created_at
             FROM admin_audit a
             LEFT JOIN users au ON au.id = a.actor_user_id
            WHERE a.target_user_id = ?
            ORDER BY a.id DESC
            LIMIT 10''',
        (user_id,),
    ).fetchall()
    return render_template('admin/user_detail.html', u=u,
                           audit_rows=audit_rows, admin_user_id=ADMIN_USER_ID)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    _require_admin()
    if user_id == ADMIN_USER_ID:
        flash("Refusing to delete the admin user.", 'danger')
        return redirect(url_for('admin.dashboard'))

    db = get_db()
    row = db.execute(
        'SELECT id, username FROM users WHERE id = ?', (user_id,)
    ).fetchone()
    if not row:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    username = row['username']
    try:
        _delete_user_and_data(db, user_id)
        # Audit the action in the same transaction as the delete — either
        # both succeed or both roll back. actor_user_id captured before the
        # commit so the FK reference is still valid.
        db.execute(
            'INSERT INTO admin_audit '
            '(actor_user_id, action, target_user_id, target_username) '
            'VALUES (?,?,?,?)',
            (current_user_id(), 'delete_user', user_id, username)
        )
        db.commit()
    except Exception as e:
        flash(f'Delete failed: {e}', 'danger')
        return redirect(url_for('admin.dashboard'))

    flash(f'Deleted user "{username}" and all associated data.', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/audit')
def audit():
    """Read view over the admin_audit log.

    Filterable by action and actor via query string. Cap rows returned —
    the table only grows on admin mutations, so the cap is generous, but
    we'd rather page than render unbounded.
    """
    _require_admin()
    db = get_db()

    action = (request.args.get('action') or '').strip()
    actor = (request.args.get('actor') or '').strip()
    limit = 500

    where = []
    params: list = []
    if action:
        where.append('a.action = ?')
        params.append(action)
    if actor:
        # Accept either a numeric id or a username substring.
        if actor.isdigit():
            where.append('a.actor_user_id = ?')
            params.append(int(actor))
        else:
            where.append('u.username LIKE ?')
            params.append(f'%{actor}%')
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    rows = db.execute(
        f'''SELECT a.id, a.actor_user_id, u.username AS actor_username,
                   a.action, a.target_user_id, a.target_username,
                   a.details, a.created_at
              FROM admin_audit a
              LEFT JOIN users u ON u.id = a.actor_user_id
              {where_sql}
             ORDER BY a.id DESC
             LIMIT {limit}''',
        params,
    ).fetchall()

    # Distinct action values for the filter dropdown.
    actions = [
        r['action'] for r in db.execute(
            'SELECT DISTINCT action FROM admin_audit ORDER BY action'
        ).fetchall()
    ]

    return render_template(
        'admin/audit.html',
        rows=rows, actions=actions,
        selected_action=action, selected_actor=actor,
        limit=limit,
    )


# ─── Refresh-flow telemetry ────────────────────────────────────────────────


def _telemetry_window_threshold(now: datetime | None = None) -> datetime:
    """Return `now - TELEMETRY_WINDOW_DAYS` as a UTC datetime. `now`
    parameterized for test isolation."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now - timedelta(days=TELEMETRY_WINDOW_DAYS)


def _percentile(sorted_values: list[int], pct: float) -> int | None:
    """Nearest-rank percentile on a pre-sorted ascending list. Returns
    None on empty input. pct is in [0, 100]."""
    if not sorted_values:
        return None
    if pct <= 0:
        return sorted_values[0]
    if pct >= 100:
        return sorted_values[-1]
    # Nearest-rank: ceil(pct/100 * N) - 1, clamped to [0, N-1].
    idx = max(0, min(len(sorted_values) - 1, int((pct / 100.0) * len(sorted_values))))
    return sorted_values[idx]


def _aggregate_ad_hoc_suggestions(db, threshold: datetime) -> dict:
    """D-63 ad-hoc workout generation aggregate. Returns total + per-status
    counts + logged-conversion rate over the window."""
    rows = db.execute(
        'SELECT status, COUNT(*) AS n FROM ad_hoc_workout_suggestions '
        'WHERE requested_at >= ? '
        'GROUP BY status',
        (threshold,),
    ).fetchall()
    by_status = {r['status']: int(r['n']) for r in rows}
    total = sum(by_status.values())
    logged = by_status.get('logged', 0)
    return {
        'total': total,
        'suggested': by_status.get('suggested', 0),
        'logged': logged,
        'discarded': by_status.get('discarded', 0),
        'regenerated': by_status.get('regenerated', 0),
        'logged_rate': (logged / total) if total else 0.0,
    }


def _aggregate_t1_hook_dismissals(db, threshold: datetime) -> dict:
    """D-63 §3.5 [No, thanks] dismissals on the post-log T1 plan-check
    hook. One row per click; per-event semantics."""
    row = db.execute(
        'SELECT COUNT(*) AS n FROM t1_hook_telemetry WHERE dismissed_at >= ?',
        (threshold,),
    ).fetchone()
    return {'total': int(row['n']) if row else 0}


def _aggregate_plan_refresh_log(db, threshold: datetime) -> dict:
    """D-64 per-tier refresh metrics. Returns a `{tier: {...}}` dict
    keyed on T1/T2/T3. Per-tier signals: total, success_count + rate,
    cap_override_count + rate, parser_degraded_count + rate, T1-hook
    attribution count + rate, p50/p95 success duration_ms.

    p50/p95 computed on success=TRUE rows only — failures don't carry
    meaningful duration semantics (rollback short-circuits the timer).
    """
    rows = db.execute(
        'SELECT tier, success, cap_overridden, triggered_by_ad_hoc_id, '
        '       failure_reason, duration_ms '
        'FROM plan_refresh_log '
        'WHERE triggered_at >= ?',
        (threshold,),
    ).fetchall()
    per_tier: dict[str, dict] = {}
    for tier_label in ('T1', 'T2', 'T3'):
        tier_rows = [r for r in rows if r['tier'] == tier_label]
        total = len(tier_rows)
        success_count = sum(1 for r in tier_rows if r['success'])
        cap_count = sum(1 for r in tier_rows if r['cap_overridden'])
        parser_degraded_count = sum(
            1 for r in tier_rows if r['failure_reason'] == 'parser_degraded'
        )
        attributed_count = sum(
            1 for r in tier_rows if r['triggered_by_ad_hoc_id'] is not None
        )
        success_durations = sorted(
            int(r['duration_ms']) for r in tier_rows
            if r['success'] and r['duration_ms'] is not None
        )
        per_tier[tier_label] = {
            'total': total,
            'success_count': success_count,
            'success_rate': (success_count / total) if total else 0.0,
            'cap_override_count': cap_count,
            'cap_override_rate': (cap_count / total) if total else 0.0,
            'parser_degraded_count': parser_degraded_count,
            'parser_degraded_rate': (parser_degraded_count / total) if total else 0.0,
            't1_hook_attributed_count': attributed_count,
            't1_hook_attribution_rate': (attributed_count / total) if total else 0.0,
            'p50_duration_ms': _percentile(success_durations, 50),
            'p95_duration_ms': _percentile(success_durations, 95),
        }
    return per_tier


@bp.route('/telemetry/refresh')
def telemetry_refresh():
    """D-73 Phase 5.2 refresh-flow telemetry dashboard.

    Aggregates the D-63 → D-64 funnel across the last
    `TELEMETRY_WINDOW_DAYS` (30d): generation via ad_hoc_workout_suggestions,
    post-log T1 hook dismissals via t1_hook_telemetry, and per-tier
    refresh metrics via plan_refresh_log. Admin-only behind
    `_require_admin()`. Aggregates only — no row-level drill-down.
    """
    _require_admin()
    db = get_db()
    threshold = _telemetry_window_threshold()
    return render_template(
        'admin/telemetry_refresh.html',
        window_days=TELEMETRY_WINDOW_DAYS,
        threshold=threshold,
        ad_hoc=_aggregate_ad_hoc_suggestions(db, threshold),
        t1_hook=_aggregate_t1_hook_dismissals(db, threshold),
        refresh_by_tier=_aggregate_plan_refresh_log(db, threshold),
    )


@bp.route('/plan/<int:plan_version_id>/inspect')
def plan_inspect(plan_version_id):
    """#321 plan-gen observability — per-block inspect view for an in-flight,
    failed, or completed plan generation. Renders the `plan_versions` control
    row (status / error / blocks-cached) plus the durable per-block progress
    snapshot (`plan_progress_blocks`): each accepted week-block's sessions +
    validator flags, so a stalled/failed generation is diagnosable block-by-
    block instead of from sparse runtime logs. Admin-only; reads any user's
    plan (operator debug surface), so NOT user-scoped like the athlete routes.
    """
    _require_admin()
    db = get_db()
    pv = db.execute(
        "SELECT id, user_id, created_at, created_via, scope_start_date, "
        "scope_end_date, pattern, generation_status, generation_error, "
        "generation_units_cached FROM plan_versions WHERE id = ?",
        (plan_version_id,),
    ).fetchone()
    if pv is None:
        abort(404)
    blocks = load_progress_blocks(db, plan_version_id)
    # #333 — the per-block snapshot is in-flight progress; a finished plan's
    # sessions live in `plan_sessions`, so a terminal plan (and one generated
    # before the #321 snapshot feature shipped) goes blank on this page exactly
    # when you want to audit the result. Fall back to reconstructing per-block
    # shape from `plan_sessions` so a `ready`/`failed` plan stays inspectable.
    fallback_from_plan_sessions = False
    if not blocks and pv['generation_status'] in ('ready', 'failed'):
        blocks = load_plan_sessions_as_blocks(db, plan_version_id)
        fallback_from_plan_sessions = bool(blocks)
    total_sessions = sum(len(b['sessions'] or []) for b in blocks)
    return render_template(
        'admin/plan_inspect.html',
        pv=pv,
        blocks=blocks,
        total_sessions=total_sessions,
        fallback_from_plan_sessions=fallback_from_plan_sessions,
    )


def _diag_token_ok(supplied: str | None, configured: str | None) -> bool:
    """Constant-time check for the diag service token. When no token is
    configured (DIAG_TOKEN unset) there is NO token bypass — returns False so
    only the admin session can authorize. Pure (no Flask/env) so it's unit-
    testable per the §5.0 admin-route-smoke deferral precedent."""
    if not configured:
        return False
    return hmac.compare_digest(supplied or "", configured)


def _diag_authorized() -> bool:
    """Authorize the diag endpoint via EITHER the admin session OR the
    DIAG_TOKEN service secret (header `X-Diag-Token` or `?token=`)."""
    if current_user_id() == ADMIN_USER_ID:
        return True
    supplied = request.headers.get('X-Diag-Token') or request.args.get('token')
    return _diag_token_ok(supplied, os.environ.get('DIAG_TOKEN'))


def _summarize_progress_blocks(blocks: list[dict]) -> dict:
    """Pure aggregation of `load_progress_blocks()` output into the diag JSON
    block view + a timing rollup. Factored out (like `_diag_token_ok`) so it's
    unit-testable without a live DB or Flask request context.

    Rule #14 — the per-block `synthesis_metadata` (latency_ms / retries_used /
    cap_hit) is the signal that localizes a stall to slow synthesis. It's
    persisted (`plan_progress_blocks`) and shown on the HTML inspect page, but
    the token-readable diag JSON used to drop it, so an agent debugging past the
    login wall couldn't see it. The per-block view carries counts + metadata
    only (NOT the session bodies) to keep the payload lean."""
    block_diags: list[dict] = []
    total_latency_ms = 0
    max_block_latency_ms = 0
    total_retries = 0
    any_cap_hit = False
    last_snapshot_at = None
    for b in blocks:
        meta = b.get('synthesis_metadata') or {}
        latency_ms = int(meta.get('latency_ms') or 0)
        total_latency_ms += latency_ms
        max_block_latency_ms = max(max_block_latency_ms, latency_ms)
        total_retries += int(meta.get('retries_used') or 0)
        any_cap_hit = any_cap_hit or bool(meta.get('cap_hit'))
        snap = b.get('snapshot_at')
        if isinstance(snap, datetime) and (
            last_snapshot_at is None or snap > last_snapshot_at
        ):
            last_snapshot_at = snap
        block_diags.append({
            'phase_idx': b.get('phase_idx'),
            'phase_name': b.get('phase_name'),
            'session_count': len(b.get('sessions') or []),
            'synthesis_metadata': meta or None,
            'snapshot_at': str(snap) if snap is not None else None,
        })
    return {
        'blocks': block_diags,
        'block_timing': {
            'total_latency_ms': total_latency_ms,
            'max_block_latency_ms': max_block_latency_ms,
            'total_retries': total_retries,
            'any_cap_hit': any_cap_hit,
            'last_snapshot_at': (
                str(last_snapshot_at) if last_snapshot_at is not None else None
            ),
        },
    }


@bp.route('/plan/<int:plan_version_id>/diag')
def plan_diag(plan_version_id):
    """Rule #14 log-visibility — JSON diagnostics for a plan generation,
    readable WITHOUT the app login so an operator/agent debugging from outside
    the session can fetch the real fault (the FULL stored traceback that the
    Vercel runtime-log MCP truncates). Returns the `plan_versions` control row
    + the durable `generation_traceback` + a block-snapshot summary.

    Auth: admin session OR a constant-time match against the `DIAG_TOKEN` env
    secret (`X-Diag-Token` header or `?token=`). When `DIAG_TOKEN` is unset,
    only the admin session is accepted — no token bypass exists by default."""
    if not _diag_authorized():
        abort(403)
    db = get_db()
    pv = db.execute(
        "SELECT id, user_id, created_at, created_via, scope_start_date, "
        "scope_end_date, pattern, generation_status, generation_error, "
        "generation_units_cached FROM plan_versions WHERE id = ?",
        (plan_version_id,),
    ).fetchone()
    if pv is None:
        abort(404)
    # generation_traceback + advance_lock_until are read separately + best-
    # effort so the endpoint still works before those columns' migrations land
    # (Neon egress is blocked from the web container, so a migration is an
    # Andy's-hands action). advance_lock_until exposes the #419 TTL advance-lock
    # state — paired with `server_now` below, a reader can tell whether a pass
    # currently holds the per-plan claim and for how long (the self-heal cycle).
    traceback_text = None
    advance_lock_until = None
    try:
        diag_row = db.execute(
            "SELECT generation_traceback, advance_lock_until "
            "FROM plan_versions WHERE id = ?",
            (plan_version_id,),
        ).fetchone()
        if diag_row is not None:
            traceback_text = diag_row['generation_traceback']
            advance_lock_until = diag_row['advance_lock_until']
    except Exception:  # noqa: BLE001 — columns may be pre-migration
        db.rollback()
    blocks = load_progress_blocks(db, plan_version_id)
    return jsonify({
        'plan_version_id': pv['id'],
        'user_id': pv['user_id'],
        'created_via': pv['created_via'],
        'scope': [str(pv['scope_start_date']), str(pv['scope_end_date'])],
        'pattern': pv['pattern'],
        'generation_status': pv['generation_status'],
        'generation_error': pv['generation_error'],
        'generation_units_cached': pv['generation_units_cached'],
        'generation_traceback': traceback_text,
        'advance_lock_until': (
            str(advance_lock_until) if advance_lock_until is not None else None
        ),
        'server_now': str(datetime.now(timezone.utc)),
        'blocks_snapshotted': len(blocks),
        'total_sessions': sum(len(b['sessions'] or []) for b in blocks),
        **_summarize_progress_blocks(blocks),
    })
