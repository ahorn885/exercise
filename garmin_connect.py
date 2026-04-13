"""
Garmin Connect API wrapper — Vercel-compatible stateless design.

Garth session tokens are stored as JSON in the garmin_auth DB table so they
persist across serverless invocations. On each API call we write the session
to /tmp/garth, use it, then serialize any refreshed tokens back to the DB.
"""
import json
import os
import shutil
import tempfile

GARTH_TMP = os.path.join(tempfile.gettempdir(), 'garth_session')

SPORT_TYPES = {
    'running': {'sportTypeId': 1, 'sportTypeKey': 'running'},
    'cycling': {'sportTypeId': 2, 'sportTypeKey': 'cycling'},
    'strength_training': {'sportTypeId': 4, 'sportTypeKey': 'strength_training'},
    'pool_swimming': {'sportTypeId': 5, 'sportTypeKey': 'pool_swimming'},
    'walking': {'sportTypeId': 11, 'sportTypeKey': 'walking'},
    'hiking': {'sportTypeId': 17, 'sportTypeKey': 'hiking'},
}


# ── Session persistence helpers ───────────────────────────────────────────────

def _write_session_to_tmp(session_json: str):
    """Write stored session JSON to /tmp/garth so garth can resume from it."""
    os.makedirs(GARTH_TMP, exist_ok=True)
    data = json.loads(session_json)
    for filename, content in data.items():
        path = os.path.join(GARTH_TMP, filename)
        if isinstance(content, str):
            with open(path, 'w') as f:
                f.write(content)
        else:
            with open(path, 'w') as f:
                json.dump(content, f)


def _read_session_from_tmp() -> str:
    """Serialize /tmp/garth directory back to a JSON string for DB storage."""
    files = {}
    if os.path.isdir(GARTH_TMP):
        for fname in os.listdir(GARTH_TMP):
            fpath = os.path.join(GARTH_TMP, fname)
            with open(fpath, 'r') as f:
                try:
                    files[fname] = json.load(f)
                except json.JSONDecodeError:
                    files[fname] = f.read()
    return json.dumps(files)


def _save_session_to_db(db, username: str = ''):
    """Read /tmp/garth and upsert into garmin_auth table."""
    session_json = _read_session_from_tmp()
    existing = db.execute('SELECT id FROM garmin_auth LIMIT 1').fetchone()
    if existing:
        db.execute(
            "UPDATE garmin_auth SET garth_session = ?, garmin_username = ?, updated_at = datetime('now') WHERE id = ?",
            (session_json, username, existing['id'] if hasattr(existing, '__getitem__') else existing[0])
        )
    else:
        db.execute(
            'INSERT INTO garmin_auth (garth_session, garmin_username) VALUES (?, ?)',
            (session_json, username)
        )
    db.commit()


def _load_client(db):
    """Load garth session from DB, write to /tmp, resume, return Garmin client."""
    import garth
    from garminconnect import Garmin

    row = db.execute('SELECT garth_session, garmin_username FROM garmin_auth LIMIT 1').fetchone()
    if not row or not row['garth_session']:
        raise RuntimeError('No saved Garmin session. Please log in via Garmin Auth Settings.')

    _write_session_to_tmp(row['garth_session'])
    garth.resume(GARTH_TMP)

    client = Garmin()
    client.garth = garth.client
    return client


# ── Public API ────────────────────────────────────────────────────────────────

def get_auth_status(db) -> dict:
    """Return {'authenticated': bool, 'username': str|None}."""
    try:
        import garth
        row = db.execute('SELECT garth_session, garmin_username FROM garmin_auth LIMIT 1').fetchone()
        if not row or not row['garth_session']:
            return {'authenticated': False, 'username': None}
        _write_session_to_tmp(row['garth_session'])
        garth.resume(GARTH_TMP)
        username = row['garmin_username'] or ''
        return {'authenticated': True, 'username': username}
    except Exception:
        return {'authenticated': False, 'username': None}


def login(db, email: str, password: str, mfa_code: str = None):
    """Perform a fresh Garmin login and persist the session to DB."""
    import garth

    os.makedirs(GARTH_TMP, exist_ok=True)

    if mfa_code:
        garth.login(email, password, prompt_mfa=lambda: mfa_code)
    else:
        garth.login(email, password)

    garth.save(GARTH_TMP)
    username = getattr(garth.client, 'username', email)
    _save_session_to_db(db, username=username)


def upload_workout(db, workout_json: dict) -> str:
    """Upload a workout JSON to Garmin Connect. Returns the workoutId string."""
    client = _load_client(db)
    result = client.add_workout(workout_json)
    _save_session_to_db(db)
    try:
        return str(result.get('workoutId') or result['workoutId'])
    except (KeyError, TypeError, AttributeError):
        return str(result)


def schedule_workout(db, workout_id: str, date: str):
    """Schedule a workout on a given ISO date (YYYY-MM-DD)."""
    client = _load_client(db)
    client.schedule_workout(workout_id, date)
    _save_session_to_db(db)


def delete_workout(db, workout_id: str):
    """Delete a workout from Garmin Connect."""
    client = _load_client(db)
    client.delete_workout(workout_id)
    _save_session_to_db(db)
