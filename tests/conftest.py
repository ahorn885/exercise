"""Shared pytest fixtures for the AIDSTATION test suite.

Currently exposes the `requires_anthropic_api_key` skipif marker used by
the real-LLM smoke tests in `tests/test_layer3a_smoke.py` and
`tests/test_layer3b_smoke.py`. The marker gates module-level test
collection on the `ANTHROPIC_API_KEY` env var so the default `pytest
tests/` run remains $0 and side-effect-free; tests execute only when the
key is intentionally set (local dev / CI smoke job).
"""

from __future__ import annotations

import os

import pytest

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"

requires_anthropic_api_key = pytest.mark.skipif(
    not os.environ.get(ANTHROPIC_API_KEY_ENV),
    reason=(
        f"{ANTHROPIC_API_KEY_ENV} not set; real-LLM smoke tests skipped. "
        "Set the env var to exercise the production Anthropic SDK adapter."
    ),
)
