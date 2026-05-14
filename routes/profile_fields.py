"""Canonical registry of prefill-eligible athlete-profile fields (PR7 / D2a).

Closes Open Item #17 from the D-58 onboarding design wave: the
`KNOWN_PROFILE_FIELDS` registry that pins per-field metadata for the
v5 §A.2 prefill UX. Seeded from `athlete.PREFILL_ELIGIBLE_FIELDS` (the
5 columns PR6 / D-51 added to `athlete_profile`) with the extra metadata
the comparison page needs: display label, unit, numeric cast, and the
per-provider extractor dispatch.

The extractor refs live in `routes.profile_extractors`. Each takes
`(db, user_id)` and returns `(value, synced_at, note)` — see that
module's docstring for the contract.

Validation:
- Insert-time validation against this registry is the obvious next step
  for `athlete_profile_field_provenance.field_name` (currently free-text
  TEXT per init_db.py line 1820). D2b adds a CHECK constraint or
  application-level validator once the write paths exist.
"""

from typing import Tuple

from athlete import PREFILL_ELIGIBLE_FIELDS
from routes.profile import CONNECTION_PROVIDERS
from routes import profile_extractors as _ex


# Each entry: `name` matches the `athlete_profile` column name (and the
# `athlete_profile_field_provenance.field_name` value). `label` /
# `unit` drive the comparison-card UI. `cast` mirrors the form-handler
# numeric cast in `routes/profile.py:edit()` so D2b's write path can
# re-use the same coercion. `extractors` is keyed by provider slug from
# `CONNECTION_PROVIDERS`; an absent key means "no extractor for this
# (field × provider)" and the route skips it without calling.
KNOWN_PROFILE_FIELDS = (
    {
        'name': 'body_weight_kg',
        'label': 'Body weight',
        'unit': 'kg',
        'cast': float,
        'extractors': {
            'coros': _ex.extract_body_weight_coros,
            'polar': _ex.extract_body_weight_polar,
        },
    },
    {
        'name': 'hrmax_bpm',
        'label': 'Maximum heart rate (HRmax)',
        'unit': 'bpm',
        'cast': int,
        'extractors': {
            'coros': _ex.extract_hrmax_coros,
            'polar': _ex.extract_hrmax_polar,
        },
    },
    {
        'name': 'lactate_threshold_hr_bpm',
        'label': 'Lactate threshold heart rate',
        'unit': 'bpm',
        'cast': int,
        'extractors': {
            'coros': _ex.extract_lactate_threshold_hr_bpm_coros,
            'polar': _ex.extract_lactate_threshold_hr_bpm_polar,
        },
    },
    {
        'name': 'vo2max',
        'label': 'VO2max',
        'unit': 'ml/kg/min',
        'cast': float,
        'extractors': {
            'coros': _ex.extract_vo2max_coros,
            'polar': _ex.extract_vo2max_polar,
        },
    },
    {
        'name': 'cycling_ftp_w',
        'label': 'Cycling FTP',
        'unit': 'watts',
        'cast': int,
        'extractors': {
            'coros': _ex.extract_cycling_ftp_w_coros,
            'polar': _ex.extract_cycling_ftp_w_polar,
        },
    },
)


# Defensive sanity check (loud failure if `PREFILL_ELIGIBLE_FIELDS` and
# this registry drift apart). Both tuples are authoritative for different
# concerns — `PREFILL_ELIGIBLE_FIELDS` gates provenance writes in
# `routes/profile.py`, `KNOWN_PROFILE_FIELDS` drives the prefill UI. They
# must stay in lockstep.
_REGISTRY_NAMES = tuple(f['name'] for f in KNOWN_PROFILE_FIELDS)
assert set(_REGISTRY_NAMES) == set(PREFILL_ELIGIBLE_FIELDS), (
    f'KNOWN_PROFILE_FIELDS ({_REGISTRY_NAMES}) drifted from '
    f'PREFILL_ELIGIBLE_FIELDS ({PREFILL_ELIGIBLE_FIELDS}). Update both.'
)


def provider_label(slug: str) -> str:
    """Slug → display label, using the `CONNECTION_PROVIDERS` source of
    truth so the prefill UI doesn't introduce a parallel mapping."""
    for s, label, _endpoint in CONNECTION_PROVIDERS:
        if s == slug:
            return label
    return slug
