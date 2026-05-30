"""Guard: --version-tag maps uniformly to etl_version strings.

Pins the de-footgun (2026-05-30): the legacy `tag == "1.3"` special-case that
mapped to the retired `0A-v11.0` R6 lineage is gone, so an ad-hoc rerun with
any tag can no longer silently reintroduce a superseded version line.
"""
from __future__ import annotations

from etl.layer0.run import _version_strings


def test_version_strings_uniform():
    # The live line: tag 1.3.1 -> 0A-v1.3.1 across all three source families.
    assert _version_strings("1.3.1") == ("0A-v1.3.1", "0B-v1.3.1", "0C-v1.3.1")
    assert _version_strings("2.0") == ("0A-v2.0", "0B-v2.0", "0C-v2.0")


def test_no_legacy_1_3_special_case():
    # "1.3" now maps uniformly like any other tag — it must NOT resolve to the
    # superseded 0A-v11.0 / 0B-v19.0-r1 / 0C-v2.0-r1 strings the old branch used.
    assert _version_strings("1.3") == ("0A-v1.3", "0B-v1.3", "0C-v1.3")
    assert "0A-v11.0" not in _version_strings("1.3")
