"""Health-check endpoint.

Liveness + database-readiness probe. Returns 200 when Flask is up and the
configured database responds to SELECT 1 within ~1 second; returns 503
otherwise.

Originally added so the COROS partner-application form has a real URL
to point at (the form asks for a "Service Status Check URL"). Reusable
for any future partner application or external uptime monitor.
"""
import sqlite3

from flask import Blueprint, jsonify

import database

bp = Blueprint('status', __name__)


def _db_ok() -> bool:
    # Open a short-lived connection independent of the request-scoped one
    # in flask.g — a hung pooled connection mustn't be able to poison the
    # probe. For Postgres we cap connect at ~1s; SELECT 1 is effectively
    # instant once connected.
    try:
        if database._is_postgres():
            import psycopg2
            conn = psycopg2.connect(database.DATABASE_URL, connect_timeout=1)
            try:
                cur = conn.cursor()
                cur.execute('SELECT 1')
                cur.fetchone()
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(database.sqlite_path(), timeout=1)
            try:
                conn.execute('SELECT 1').fetchone()
            finally:
                conn.close()
        return True
    except Exception:
        return False


@bp.route('/status', methods=['GET'])
def status():
    if _db_ok():
        return jsonify(status='ok'), 200
    return jsonify(status='error', detail='database unreachable'), 503
