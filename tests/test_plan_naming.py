"""Unit tests for `plan_naming.generated_plan_name` (#620) — the derived
display name for generated (`plan_versions`) plans."""
from __future__ import annotations

from datetime import date

from plan_naming import generated_plan_name, plan_display_name


def test_names_after_target_race_with_week_suffix():
    assert generated_plan_name(
        'Pocket Gopher Extreme 2026',
        date(2026, 4, 1), date(2026, 7, 17),
    ) == 'Pocket Gopher Extreme 2026 — 15-week build'


def test_accepts_iso_string_dates():
    # The render harness's fake cursor hands back ISO strings, not `date`s.
    assert generated_plan_name(
        'Boston Marathon', '2026-06-01', '2026-06-29',
    ) == 'Boston Marathon — 4-week build'


def test_falls_back_to_plain_label_without_race():
    assert generated_plan_name(None, date(2026, 4, 1), date(2026, 7, 17)) == 'Training plan'
    assert generated_plan_name('', '2026-04-01', '2026-07-17') == 'Training plan'


def test_drops_week_suffix_when_scope_unusable():
    # Unparseable / missing scope → race name alone, no bogus "0-week build".
    assert generated_plan_name('PGE 2026', None, None) == 'PGE 2026'
    assert generated_plan_name('PGE 2026', '2026-07-17', '2026-07-18') == 'PGE 2026'


def test_strips_surrounding_whitespace_on_race_name():
    assert generated_plan_name('  PGE 2026  ', None, None) == 'PGE 2026'


def test_display_name_prefers_stored_snapshot():
    # #1056 — a stored snapshot wins even when the *current* target race differs,
    # so adding a new target race can't silently rename an existing plan.
    assert plan_display_name(
        'Pocket Gopher — 3-week build', 'Cowboy Tough',
        date(2026, 4, 1), date(2026, 4, 22),
    ) == 'Pocket Gopher — 3-week build'


def test_display_name_falls_back_when_no_snapshot():
    # No snapshot (older row / passthrough dict) → derive from the current race.
    expected = generated_plan_name('Cowboy Tough', date(2026, 4, 1), date(2026, 4, 22))
    assert plan_display_name(
        None, 'Cowboy Tough', date(2026, 4, 1), date(2026, 4, 22),
    ) == expected
    # A blank/whitespace snapshot also falls back rather than showing an empty label.
    assert plan_display_name(
        '   ', 'Cowboy Tough', date(2026, 4, 1), date(2026, 4, 22),
    ) == expected
