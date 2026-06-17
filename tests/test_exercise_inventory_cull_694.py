"""#694 — the five mis-classified v1 `exercise_inventory` novelty entries are
culled from the seeds and removed from existing DBs by a public migration.

These are cardio sessions / coaching cues, not trackable strength exercises;
they surfaced on the /rx Exercises page (the v1 catalog), not in layer0 / the
plan-gen pool, so this is v1-catalog hygiene with no Layer-4 impact.
"""

from __future__ import annotations

import os

os.environ.setdefault('DATABASE_URL', '')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-cull-test')

import init_db  # noqa: E402

CULLED = [
    '1,000 Step-Up Challenge',
    'Hanging Leg Raise in Boots',
    'Weighted Treadmill Incline Walk',
    'High-Rep Strength Endurance Sets',
    'Nasal-Breathing-Only Climbing',
]


def test_culled_names_absent_from_seeds():
    seed_names = {row[0] for row in init_db.EXERCISES}
    for name in CULLED:
        assert name not in seed_names, f"{name!r} still in EXERCISES seed"
        assert name not in init_db.EXERCISE_EQUIPMENT, \
            f"{name!r} still in EXERCISE_EQUIPMENT seed"


def test_cull_migration_present_and_fk_ordered():
    mig = init_db._PG_MIGRATIONS
    joined = "\n".join(m for m in mig if isinstance(m, str))
    # Every culled name is deleted from the catalog.
    inv_delete = next(
        (m for m in mig if isinstance(m, str)
         and m.startswith('DELETE FROM exercise_inventory')
         and 'Nasal-Breathing-Only Climbing' in m),
        None,
    )
    assert inv_delete is not None, "exercise_inventory cull migration missing"
    for name in CULLED:
        assert name in inv_delete

    # FK children are deleted before the catalog row they reference.
    def idx(prefix):
        return next(i for i, m in enumerate(mig)
                    if isinstance(m, str) and m.startswith(prefix)
                    and 'Nasal-Breathing-Only Climbing' in m)

    eq_i = idx('DELETE FROM exercise_equipment')
    inj_i = idx('DELETE FROM injury_exercise_modifications')
    inv_i = idx('DELETE FROM exercise_inventory')
    assert eq_i < inv_i, "exercise_equipment must be deleted before exercise_inventory"
    assert inj_i < inv_i, "injury_exercise_modifications must be deleted before exercise_inventory"
    # The per-user rx rows (name-keyed) are cleaned too.
    assert 'DELETE FROM current_rx WHERE exercise IN' in joined
