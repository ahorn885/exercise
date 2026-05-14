"""Provider-data extractors for v5 §A.2 prefill UX (PR7 / D2a).

One function per (prefill-eligible field × connected provider). Each
returns a 3-tuple `(value, synced_at, note)` where:

  - `value`: numeric value extracted, or `None` if the provider has no
    data for this athlete / field today.
  - `synced_at`: ISO date or timestamp string describing the freshness
    of the underlying data — for derived values, the latest contributing
    row's date; for direct readings, the row's `fetched_at`. `None` when
    `value` is `None`.
  - `note`: short human-readable derivation hint shown beneath the value
    on the prefill comparison card ("Max across last 90 days of activity
    data"), or `None` when no clarification is helpful.

Functions are pure reads. They never write to the DB and never raise on
empty inputs — a provider with no data for the field returns
`(None, None, None)` so the caller's render loop can skip the candidate
without branching on exception classes.

The dispatch table lives in `routes/profile_fields.py:KNOWN_PROFILE_FIELDS`.
"""

from datetime import date, timedelta
from typing import Optional, Tuple

ExtractorResult = Tuple[Optional[float], Optional[str], Optional[str]]

_EMPTY: ExtractorResult = (None, None, None)

# Window for derived aggregates over cardio_log. v5 §A.2 doesn't pin a
# specific window; 90 days mirrors the reasonable horizon a coach would
# trust for HRmax (long enough to catch a hard race, short enough that
# detraining doesn't drag the value).
_DERIVED_WINDOW_DAYS = 90


def _window_start_iso() -> str:
    return (date.today() - timedelta(days=_DERIVED_WINDOW_DAYS)).isoformat()


def _hrmax_from_cardio_log(db, user_id: int, provider_id_col: str) -> ExtractorResult:
    """Common shape for `extract_hrmax_<provider>`. Scans `cardio_log` for
    rows tagged with the provider's foreign-id column (e.g.
    `coros_label_id`, `polar_exercise_id`), takes MAX(max_hr) over the
    last 90 days, and returns the latest contributing row's date as
    `synced_at`.

    `provider_id_col` is a column name interpolated into the SQL — it
    comes from this module's call sites only (never from user input), so
    f-string interpolation is safe.
    """
    row = db.execute(
        f'SELECT MAX(max_hr) AS hrmax, MAX(date) AS latest '
        f'FROM cardio_log '
        f'WHERE user_id = ? '
        f'  AND {provider_id_col} IS NOT NULL '
        f'  AND max_hr IS NOT NULL '
        f'  AND date >= ?',
        (user_id, _window_start_iso()),
    ).fetchone()
    if not row or row['hrmax'] is None:
        return _EMPTY
    return (
        int(row['hrmax']),
        row['latest'],
        'Max heart-rate observed across the last 90 days of activity data.',
    )


# ----- body_weight_kg -------------------------------------------------------
#
# Neither COROS nor Polar's current ingest captures body weight. Both
# providers can deliver it via wellness APIs that aren't wired yet
# (Polar UserBodyComposition, COROS account profile). When that ingest
# lands, these stubs flip to real reads against the new tables.

def extract_body_weight_coros(db, user_id: int) -> ExtractorResult:
    return _EMPTY


def extract_body_weight_polar(db, user_id: int) -> ExtractorResult:
    return _EMPTY


# ----- hrmax_bpm ------------------------------------------------------------

def extract_hrmax_coros(db, user_id: int) -> ExtractorResult:
    return _hrmax_from_cardio_log(db, user_id, 'coros_label_id')


def extract_hrmax_polar(db, user_id: int) -> ExtractorResult:
    return _hrmax_from_cardio_log(db, user_id, 'polar_exercise_id')


# ----- lactate_threshold_hr_bpm --------------------------------------------
#
# No provider currently delivers this through our ingest. Polar reports
# a HR-based "training-zone limit" but that's not the same as a lab
# lactate-threshold value, and we don't ingest it anyway. Stubs.

def extract_lactate_threshold_hr_bpm_coros(db, user_id: int) -> ExtractorResult:
    return _EMPTY


def extract_lactate_threshold_hr_bpm_polar(db, user_id: int) -> ExtractorResult:
    return _EMPTY


# ----- vo2max ---------------------------------------------------------------
#
# COROS Health reports a VO2max estimate; Polar's Fitness Test produces
# one. Neither is in our current ingest. Stubs.

def extract_vo2max_coros(db, user_id: int) -> ExtractorResult:
    return _EMPTY


def extract_vo2max_polar(db, user_id: int) -> ExtractorResult:
    return _EMPTY


# ----- cycling_ftp_w --------------------------------------------------------
#
# Wahoo has an FTP API (paused — Wahoo integration not yet shipped per
# CLAUDE.md). COROS / Polar don't supply FTP. Stubs.

def extract_cycling_ftp_w_coros(db, user_id: int) -> ExtractorResult:
    return _EMPTY


def extract_cycling_ftp_w_polar(db, user_id: int) -> ExtractorResult:
    return _EMPTY
