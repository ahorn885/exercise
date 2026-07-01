"""Shared pytest fixtures for the AIDSTATION test suite.

Exposes two opt-in skipif markers, both off by default so `pytest tests/`
stays $0 and side-effect-free:

- `requires_anthropic_api_key` — gates the real-LLM smoke tests in
  `tests/test_layer3a_smoke.py` / `tests/test_layer3b_smoke.py` on the
  `ANTHROPIC_API_KEY` env var.
- `requires_real_postgres` (#754/T-5.7) — gates real-database ingest tests
  (`tests/test_cardio_ingest.py`) on the `TEST_DATABASE_URL` env var. Point
  it at a scratch Postgres database; the test bootstraps that database's
  schema itself via `init_db.init_postgres()`, so nothing needs pre-seeding.
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

TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"

requires_real_postgres = pytest.mark.skipif(
    not os.environ.get(TEST_DATABASE_URL_ENV),
    reason=(
        f"{TEST_DATABASE_URL_ENV} not set; real-Postgres ingest tests skipped. "
        "Point it at a scratch Postgres database (e.g. "
        "postgresql://postgres:postgres@localhost:5432/aidstation_test) to "
        "exercise the real cardio-ingest SQL path."
    ),
)
