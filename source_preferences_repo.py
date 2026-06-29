"""Per-athlete source-precedence pins (#196 Phase 5, Track B — slice B1).

The canonical merge layers pick a "best" value automatically — wellness coalesces
per metric (`canonical_wellness._coalesce`), cardio merges to the most-complete copy
(`routes/garmin.materialize_canonical_activity`). This module stores an optional
per-athlete HARD PIN that overrides that automatic pick: **one preferred provider
per domain** (Andy 2026-06-29 — single-provider pin per domain; per-metric / per-field
pins deferred). When a pin is set and the pinned provider HAS a value/copy it wins;
otherwise the canonical "most complete" merge applies.

This slice (B1) is **substrate only**: the table + these helpers. Nothing reads them
yet — the consumers wire in later slices: B2 (wellness coalesce reads the wellness
pin), B3 (cardio merge reads the cardio pin), B4 (the picker UI). Design:
`aidstation-sources/designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md`.

Storage: `user_source_preferences (user_id, domain, preferred_provider)`, PK
`(user_id, domain)` → at most one pin per domain. `set_*` upserts; `clear_*` deletes
the row (absence = "no pin → automatic merge"). Caller commits.

The valid provider set per domain mirrors the merge layers' own source lists:
wellness is imported from `canonical_wellness._WELLNESS_SOURCE_PRIORITY` (a leaf
module); cardio is restated here (importing the `routes.garmin` route module at
import time is unwanted) and pinned in lockstep with `_PROVIDER_ID_COLUMNS` by
`tests/test_source_preferences_repo.py::test_cardio_providers_match_source`.
"""
from __future__ import annotations

from canonical_wellness import _WELLNESS_SOURCE_PRIORITY

# The two domains a pin can target. 'wellness' = the daily-wellness coalesce
# (canonical_daily_wellness); 'cardio' = the cross-source activity merge
# (canonical_activity).
WELLNESS = "wellness"
CARDIO = "cardio"
DOMAINS = (WELLNESS, CARDIO)

# Valid provider per domain — single source of truth is each merge layer's own
# list. Cardio mirrors routes/garmin._PROVIDER_ID_COLUMNS (test-pinned).
_CARDIO_PROVIDERS = frozenset({"garmin", "wahoo", "polar", "coros", "rwgps", "strava"})
VALID_PROVIDERS: dict[str, frozenset[str]] = {
    WELLNESS: frozenset(_WELLNESS_SOURCE_PRIORITY),
    CARDIO: _CARDIO_PROVIDERS,
}


class SourcePreferenceError(ValueError):
    """Raised on an unknown domain or a provider not valid for that domain;
    nothing is written when raised."""


def get_source_preferences(db, user_id: int) -> dict[str, str]:
    """The athlete's pins as `{domain: preferred_provider}` — only domains with a
    pin appear (absence = no pin → automatic merge). Empty dict when none."""
    rows = db.execute(
        "SELECT domain, preferred_provider FROM user_source_preferences "
        "WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {r["domain"]: r["preferred_provider"] for r in rows}


def set_source_preference(db, user_id: int, domain: str, provider: str) -> None:
    """Pin `provider` as the preferred source for `domain` (upsert — one pin per
    domain). Validates the domain + that the provider is valid for it, writing
    nothing on a violation. Caller commits."""
    if domain not in VALID_PROVIDERS:
        raise SourcePreferenceError(f"unknown domain {domain!r}")
    if provider not in VALID_PROVIDERS[domain]:
        raise SourcePreferenceError(
            f"{provider!r} is not a valid {domain} source "
            f"(valid: {', '.join(sorted(VALID_PROVIDERS[domain]))})"
        )
    db.execute(
        "INSERT INTO user_source_preferences (user_id, domain, preferred_provider) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT (user_id, domain) DO UPDATE SET "
        "preferred_provider = EXCLUDED.preferred_provider, updated_at = NOW()",
        (user_id, domain, provider),
    )
    print(f"[source-pref] user={user_id} set {domain}={provider}")  # noqa: T201


def clear_source_preference(db, user_id: int, domain: str) -> None:
    """Remove the athlete's pin for `domain` (no-op when none set). Validates the
    domain. Caller commits."""
    if domain not in VALID_PROVIDERS:
        raise SourcePreferenceError(f"unknown domain {domain!r}")
    db.execute(
        "DELETE FROM user_source_preferences WHERE user_id = ? AND domain = ?",
        (user_id, domain),
    )
    print(f"[source-pref] user={user_id} cleared {domain}")  # noqa: T201
