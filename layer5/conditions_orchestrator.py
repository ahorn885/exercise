"""Layer 5B conditions stage — resolve locale coords, build, persist.

Deterministic glue (zero-LLM) between the durable substrate and the pure
`layer5.conditions_builder`. Runs AFTER a plan reaches `ready`: it reads the
plan's persisted sessions, resolves each session locale's coordinates from
`locale_profiles`, derives expected conditions from climate normals
(`weather_client.get_expected_conditions`) and persists the `PlanConditions`
artifact. Also the entry point for the manual regenerate action.

Network cost is bounded by memoizing the climate-normals lookup per
``(locale, year, month)`` — normals are stable within a calendar month, so a
months-long plan at a couple of locales makes only a handful of lookups. Each
lookup is itself best-effort (≤6 s timeout, degrades to ``None``), so a slow or
offline weather source never blocks the already-`ready` plan.

Best-effort by contract: callers wrap this so a fault can never affect the plan.
Returns None (rather than raising) when conditions can't be produced — no
sessions, or no session locale resolved to coordinates with a usable sample — so
a caller's `if result is None` branch can message the user without treating it
as an error.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from layer5.conditions_builder import build_plan_conditions
from layer5.conditions_payload import PlanConditions
from plan_conditions_repo import persist_plan_conditions
from plan_sessions_repo import load_plan_sessions_by_version
from weather_client import ExpectedConditions, get_expected_conditions


def _coords_for_locales(
    db: Any, user_id: int, locale_ids: list[str]
) -> dict[str, tuple[float, float]]:
    """Map locale slug -> (lat, lng) for the user's locales that carry coords.

    One lookup per distinct slug (a plan touches very few locales); slugs with
    no coordinates (manual-entry locales) are simply absent from the result.
    """
    out: dict[str, tuple[float, float]] = {}
    for slug in locale_ids:
        cur = db.execute(
            "SELECT lat, lng FROM locale_profiles WHERE user_id = ? AND locale = ?",
            (user_id, slug),
        )
        row = cur.fetchone()
        if row is None:
            continue
        lat, lng = row["lat"], row["lng"]
        if lat is not None and lng is not None:
            out[slug] = (float(lat), float(lng))
    return out


def generate_and_persist_plan_conditions(
    db: Any,
    user_id: int,
    plan_version_id: int,
    *,
    today: date | None = None,
    fetcher: Any | None = None,
) -> PlanConditions | None:
    """Build + persist the Layer 5B conditions artifact for `plan_version_id`.

    Returns the `PlanConditions` on success, or None when conditions cannot be
    produced (no sessions, or no day resolved to usable expected conditions).
    `today` / `fetcher` are forwarded to `weather_client` for deterministic
    tests. Caller owns the transaction boundary — this helper does NOT commit.
    """
    sessions = load_plan_sessions_by_version(db, plan_version_id)
    if not sessions:
        return None

    locale_ids = sorted({s.locale_id for s in sessions if s.locale_id})
    if not locale_ids:
        return None

    coords = _coords_for_locales(db, user_id, locale_ids)
    if not coords:
        return None

    # Memoize per (locale, year, month) — climate normals are stable within a
    # calendar month, so this bounds the (already best-effort) weather lookups.
    memo: dict[tuple[str, int, int], ExpectedConditions | None] = {}

    def conditions_for(locale_id: str, d: date) -> ExpectedConditions | None:
        latlng = coords.get(locale_id)
        if latlng is None:
            return None
        key = (locale_id, d.year, d.month)
        if key not in memo:
            memo[key] = get_expected_conditions(
                latlng[0], latlng[1], d, today=today, fetcher=fetcher
            )
        return memo[key]

    conditions = build_plan_conditions(
        plan_version_id=plan_version_id,
        sessions=sessions,
        conditions_for=conditions_for,
    )
    if not conditions.days:
        return None

    persist_plan_conditions(db, user_id, conditions)
    return conditions
