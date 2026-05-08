"""Athlete profile helpers (Session 4).

The profile is a tiny per-user table seeded by the user themselves on
`/profile`. It feeds into the coaching context so plan generation /
review have the athlete's age, target event, weekly hours, and training
window without the user typing them into the generate form each time.

Allowed fields are pinned here so route POSTs can't write arbitrary
columns. New fields added in future sessions go in this list and the
`athlete_profile` schema in init_db.py simultaneously.
"""

from typing import Optional

import database


PROFILE_FIELDS = (
    'date_of_birth',
    'sex',
    'height_cm',
    'primary_sport',
    'target_event_name',
    'target_event_date',
    'weekly_hours_target',
    'training_window',
    'notes',
)

TRAINING_WINDOWS = ('morning', 'midday', 'evening', 'flexible')


def get_athlete_profile(db, user_id) -> Optional[dict]:
    """Return the profile row for `user_id` as a dict, or None if missing."""
    if user_id is None:
        return None
    row = db.execute(
        f"SELECT user_id, {', '.join(PROFILE_FIELDS)}, updated_at "
        "FROM athlete_profile WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_athlete_profile(db, user_id, **fields) -> dict:
    """Insert-or-update the profile for `user_id`. Unknown keys are
    silently dropped — caller can pass a request.form-shaped dict
    without sanitising. Returns the resulting row as a dict.

    Caller is responsible for db.commit().
    """
    if user_id is None:
        raise ValueError('user_id required')

    clean = {k: fields[k] for k in PROFILE_FIELDS if k in fields}
    now_sql = 'NOW()' if database._is_postgres() else "datetime('now')"

    if db.execute(
        'SELECT 1 FROM athlete_profile WHERE user_id = ?', (user_id,)
    ).fetchone():
        if clean:
            assigns = ', '.join(f'{k}=?' for k in clean)
            db.execute(
                f'UPDATE athlete_profile SET {assigns}, updated_at = {now_sql} '
                f'WHERE user_id = ?',
                list(clean.values()) + [user_id]
            )
    else:
        cols = ['user_id'] + list(clean.keys())
        vals = [user_id] + list(clean.values())
        placeholders = ', '.join(['?'] * len(cols))
        db.execute(
            f'INSERT INTO athlete_profile ({", ".join(cols)}) '
            f'VALUES ({placeholders})',
            vals
        )

    return get_athlete_profile(db, user_id) or {}
