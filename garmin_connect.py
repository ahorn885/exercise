"""
Garmin Connect API wrapper — Vercel-compatible stateless design.

Garth session tokens are stored as JSON in the garmin_auth DB table so they
persist across serverless invocations. On each API call we write the session
to /tmp/garth, use it, then serialize any refreshed tokens back to the DB.

Browser-cookie auth: if garth SSO is rate-limited, store session cookies
directly from Chrome. Stored as {"type": "browser_cookie", "cookie": "..."}.
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

# Garmin typeKey → human-readable activity name (matches cardio_log.activity values)
_GARMIN_TYPE_TO_ACTIVITY = {
    'running': 'Running',
    'trail_running': 'Trail Running',
    'treadmill_running': 'Treadmill Running',
    'track_running': 'Track Running',
    'cycling': 'Road Cycling',
    'road_biking': 'Road Cycling',
    'mountain_biking': 'Mountain Biking',
    'gravel_cycling': 'Gravel Cycling',
    'indoor_cycling': 'Indoor Cycling',
    'virtual_ride': 'Indoor Cycling',
    'strength_training': 'Strength Training',
    'swimming': 'Pool Swimming',
    'open_water_swimming': 'Open Water Swimming',
    'hiking': 'Hiking',
    'walking': 'Walking',
}

# Garmin typeKey → plan sport_type category (for plan item matching)
GARMIN_TYPE_TO_PLAN_SPORT = {
    'running': 'running',
    'trail_running': 'running',
    'treadmill_running': 'running',
    'track_running': 'running',
    'cycling': 'cycling',
    'road_biking': 'cycling',
    'mountain_biking': 'cycling',
    'gravel_cycling': 'cycling',
    'indoor_cycling': 'cycling',
    'virtual_ride': 'cycling',
    'strength_training': 'strength_training',
    'swimming': 'swimming',
    'open_water_swimming': 'swimming',
    'hiking': 'hiking',
    'walking': 'walking',
}


# ── Browser-cookie auth helpers ──────────────────────────────────────────────

def _is_browser_auth(session_json: str) -> bool:
    try:
        return json.loads(session_json).get('type') == 'browser_cookie'
    except Exception:
        return False


def _browser_requests_session(session_json: str):
    import requests as _requests
    cookie_string = json.loads(session_json).get('cookie', '')
    s = _requests.Session()
    s.headers.update({
        'NK': 'NT',
        'X-App-Ver': '4.64.2.0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
        'Referer': 'https://connect.garmin.com/',
        'Cookie': cookie_string,
    })
    return s


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
        row = db.execute('SELECT garth_session, garmin_username FROM garmin_auth LIMIT 1').fetchone()
        if not row or not row['garth_session']:
            return {'authenticated': False, 'username': None}
        if _is_browser_auth(row['garth_session']):
            s = _browser_requests_session(row['garth_session'])
            resp = s.get('https://connect.garmin.com/modern/currentuser-service/user/info', timeout=10)
            if resp.status_code == 200:
                username = row['garmin_username'] or resp.json().get('username', '')
                return {'authenticated': True, 'username': username, 'auth_type': 'browser_cookie'}
            return {'authenticated': False, 'username': None}
        import garth
        _write_session_to_tmp(row['garth_session'])
        garth.resume(GARTH_TMP)
        username = row['garmin_username'] or ''
        return {'authenticated': True, 'username': username, 'auth_type': 'garth'}
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


def fetch_activities(db, start_date: str, end_date: str) -> list:
    """Fetch activities from Garmin Connect for a date range.

    Returns raw Garmin API activity dicts. Call normalize_activity() on each.
    start_date / end_date: ISO strings YYYY-MM-DD.
    """
    row = db.execute('SELECT garth_session FROM garmin_auth LIMIT 1').fetchone()
    if row and _is_browser_auth(row['garth_session']):
        s = _browser_requests_session(row['garth_session'])
        resp = s.get(
            'https://connect.garmin.com/activitylist-service/activities/search/activities',
            params={'startDate': start_date, 'endDate': end_date, 'start': 0, 'limit': 100},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get('activityList', data.get('activities', []))

    client = _load_client(db)
    try:
        activities = client.get_activities_by_date(start_date, end_date)
    except Exception:
        activities = client.get_activities(0, 100) or []
        activities = [a for a in activities
                      if start_date <= (a.get('startTimeLocal') or '')[:10] <= end_date]
    _save_session_to_db(db)
    return activities or []


def download_activity_fit(db, activity_id) -> bytes:
    """Download the original FIT file for a Garmin activity. Returns raw bytes."""
    client = _load_client(db)
    data = client.download_activity(
        activity_id,
        dl_fmt=client.ActivityDownloadFormat.ORIGINAL
    )
    _save_session_to_db(db)
    return bytes(data) if not isinstance(data, bytes) else data


def normalize_activity(a: dict) -> dict:
    """Convert a raw Garmin API activity dict to cardio_log-compatible fields."""
    garmin_type = (a.get('activityType') or {}).get('typeKey', 'other')
    activity = _GARMIN_TYPE_TO_ACTIVITY.get(
        garmin_type, garmin_type.replace('_', ' ').title()
    )

    duration_sec = a.get('duration') or a.get('elapsedDuration') or 0
    duration_min = round(duration_sec / 60, 2) if duration_sec else None
    moving_sec = a.get('movingDuration') or duration_sec or 0
    moving_min = round(moving_sec / 60, 2) if moving_sec else None

    distance_m = a.get('distance') or 0
    distance_mi = round(distance_m * 0.000621371, 3) if distance_m else None

    avg_speed_ms = a.get('averageSpeed') or 0
    avg_speed_mph = round(avg_speed_ms * 2.23694, 2) if avg_speed_ms else None

    avg_pace = None
    if avg_speed_mph and avg_speed_mph > 0 and 'run' in garmin_type.lower():
        pace_min = 60 / avg_speed_mph
        avg_pace = f"{int(pace_min)}:{int((pace_min % 1) * 60):02d}"

    elev_gain_m = a.get('elevationGain') or 0
    elev_loss_m = a.get('elevationLoss') or 0

    # Running cadence: Garmin stores one-leg steps; double it
    cadence = (a.get('averageRunningCadenceInStepsPerMinute')
               or a.get('averageCadence') or None)
    if cadence is not None:
        cadence = int(cadence * 2) if ('run' in garmin_type.lower() and cadence < 120) else int(cadence)

    return {
        'date': (a.get('startTimeLocal') or '')[:10],
        'activity': activity,
        'activity_name': a.get('activityName'),
        'duration_min': duration_min,
        'moving_time_min': moving_min,
        'distance_mi': distance_mi,
        'avg_pace': avg_pace,
        'avg_speed': avg_speed_mph,
        'avg_hr': a.get('averageHR'),
        'max_hr': a.get('maxHR'),
        'calories': a.get('calories'),
        'elev_gain_ft': round(elev_gain_m * 3.28084, 1) if elev_gain_m else None,
        'elev_loss_ft': round(elev_loss_m * 3.28084, 1) if elev_loss_m else None,
        'avg_cadence': cadence,
        'avg_power': a.get('avgPower'),
        'max_power': a.get('maxPower'),
        'norm_power': a.get('normPower'),
        'aerobic_te': a.get('aerobicTrainingEffect'),
        'anaerobic_te': a.get('anaerobicTrainingEffect'),
        'garmin_activity_id': str(a.get('activityId', '')),
        '_plan_sport_type': GARMIN_TYPE_TO_PLAN_SPORT.get(garmin_type, ''),
    }
