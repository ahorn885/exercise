"""Unit coverage for the workout display filters added in issue #952.

`_duration_mmss` and `_distance_hundredths` (registered as the Jinja filters
`duration_mmss` / `distance_hundredths` in `app.py`) clean up how logged
workout duration and distance render in the cardio log, training list, and
dashboard recent-cardio table:

  * Duration — minutes:seconds, no decimal minutes, nothing finer than seconds.
  * Distance — rounded to the hundredth, trailing zeros trimmed.

These exercise the plain helper functions directly; no app context or DB is
needed, so the module imports them without booting the Flask app.
"""

from __future__ import annotations

import os

# `app.py` reads these at import time; a fast-failing DB URL keeps the
# module-level init_postgres() from blocking on a real host (the helpers we
# test never touch the DB).
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-workout-format-tests')
# Force-blank so app.py's module-level init_postgres() fast-fails instead of
# blocking on a real (egress-gated) Neon host. Must override any inherited URL.
os.environ['DATABASE_URL'] = ''

from app import _distance_hundredths, _duration_mmss  # noqa: E402


class TestDurationMmss:
    def test_fractional_minutes_become_seconds(self):
        assert _duration_mmss(45.5) == '45:30'

    def test_whole_minutes_pad_seconds(self):
        assert _duration_mmss(45) == '45:00'

    def test_total_minutes_can_exceed_an_hour(self):
        # The field is total minutes, not a clock — a 125-min ride stays 125:30.
        assert _duration_mmss(125.5) == '125:30'

    def test_quarter_minute_rounds_to_whole_second(self):
        assert _duration_mmss(90.25) == '90:15'

    def test_sub_second_rounds_to_nearest_second(self):
        # 0.008 min = 0.48 s -> rounds to 0 s, not a fractional-second tail.
        assert _duration_mmss(0.008) == '0:00'

    def test_none_and_blank_render_empty(self):
        assert _duration_mmss(None) == ''
        assert _duration_mmss('') == ''

    def test_garbage_is_swallowed(self):
        assert _duration_mmss('not-a-number') == ''


class TestDistanceHundredths:
    def test_long_decimal_tail_rounds(self):
        assert _distance_hundredths(13.123456) == '13.12'

    def test_trailing_zeros_trimmed(self):
        assert _distance_hundredths(13.50) == '13.5'

    def test_whole_number_has_no_decimal(self):
        assert _distance_hundredths(5.0) == '5'

    def test_rounds_to_two_places(self):
        # 13.126 -> 13.13 (third place rounds the hundredth up).
        assert _distance_hundredths(13.126) == '13.13'

    def test_none_and_blank_render_empty(self):
        assert _distance_hundredths(None) == ''
        assert _distance_hundredths('') == ''

    def test_garbage_is_swallowed(self):
        assert _distance_hundredths('not-a-number') == ''
