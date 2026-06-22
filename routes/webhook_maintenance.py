"""Webhook-event housekeeping (#250) — retention prune + dead-letter sweep.

The `webhook_events` table is the durable audit log every provider webhook
writes to (COROS / Strava / Whoop / Polar / Wahoo / RWGPS / Oura). Two jobs keep
it healthy, run together by one daily Vercel cron:

  1. **Dead-letter sweep.** A delivery that was attempted and errored
     (`processed_at IS NULL AND error IS NOT NULL`) but has aged past the
     per-provider retry window is never going to succeed. We stamp
     `dead_lettered_at` so it stops being mistaken for in-flight work and
     surfaces on the dead-letter path — `WHERE dead_lettered_at IS NOT NULL`
     (indexed) — for operator inspection instead of being silently dropped.
     The synchronous providers retry in-window inside their own cron
     (e.g. RWGPS drains the last 24h); past that window the failure is terminal.

  2. **Retention prune.** Rows older than 90 days are deleted. By the time a
     row reaches 90 days the dead-letter sweep has already terminal-stamped any
     stuck failure, so the prune only ever removes processed or dead-lettered
     rows — never an un-acknowledged in-flight delivery.

Bearer-`CRON_SECRET` gated, exactly like the provider cron drains; auth is
verified inside the route, so the endpoint is exempt from the global session
wall in `app.py`.
"""
from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify

from database import get_db
from routes.auth import cron_authorized

bp = Blueprint('webhook_maintenance', __name__, url_prefix='/integrations/webhooks')

# A failed delivery still unprocessed this long after receipt is terminal: the
# synchronous providers retry within a 24h window, so 1 day clears it.
DEAD_LETTER_AFTER_DAYS = 1
# Audit-log retention. Drop deliveries older than this.
RETAIN_DAYS = 90


def run_maintenance(
    db,
    *,
    dead_letter_after_days: int = DEAD_LETTER_AFTER_DAYS,
    retain_days: int = RETAIN_DAYS,
) -> tuple[int, int]:
    """Dead-letter aged failures, then prune aged rows. Returns
    `(dead_lettered, pruned)` counts. Intervals are interpolated as ints (not
    bound params) because Postgres can't parameterize an INTERVAL literal."""
    dead = db.execute(
        "UPDATE webhook_events SET dead_lettered_at = NOW() "
        "WHERE dead_lettered_at IS NULL AND processed_at IS NULL "
        "  AND error IS NOT NULL "
        f"  AND received_at < NOW() - INTERVAL '{int(dead_letter_after_days)} days' "
        "RETURNING id"
    ).fetchall()
    pruned = db.execute(
        "DELETE FROM webhook_events "
        f"WHERE received_at < NOW() - INTERVAL '{int(retain_days)} days' "
        "RETURNING id"
    ).fetchall()
    db.commit()
    return len(dead), len(pruned)


@bp.route('/cron/maintenance', methods=['GET', 'POST'])
def cron_maintenance():
    """Daily housekeeping: dead-letter aged webhook failures + prune rows older
    than 90 days. Bearer-`CRON_SECRET` gated."""
    if not cron_authorized():
        abort(401)
    db = get_db()
    try:
        dead_lettered, pruned = run_maintenance(db)
    except Exception:  # noqa: BLE001 — don't let a sweep error wedge the cron
        current_app.logger.exception('webhook_events maintenance failed')
        db.rollback()
        abort(500)
    print(f'[webhook-maint] dead_lettered={dead_lettered} pruned={pruned}')  # noqa: T201
    return jsonify(dead_lettered=dead_lettered, pruned=pruned), 200
