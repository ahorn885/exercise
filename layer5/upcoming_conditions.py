"""Layer 5C — live upcoming-conditions producer (#289).

Refreshes the `upcoming_conditions` signal: for each athlete with an active
(ready) plan, fetch the **live** forecast for the next ``ADVISORY_HORIZON_DAYS``
of training-day locales and persist one row per `(user, date)`. That table is
the queryable signal the #964 conditions-advisory notification fires on —
distinct from the Layer 5B `plan_conditions` climate-normals artifact (typical,
not live; keyed per plan_version as opaque JSONB).

Deterministic + zero-LLM (Layer 5 posture), best-effort (a missing locale /
forecast just yields no row for that day), and offline-tolerant (a network fault
leaves the prior run's rows in place). No Flask here — the cron route calls in,
owns the transaction, and commits.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from athlete_event_windows_repo import resolve_away_location
from plan_sessions_repo import (
    load_active_plan_version_id,
    load_plan_sessions_by_version,
)
from upcoming_conditions_repo import prune_past, upsert_upcoming_conditions
from weather_client import DayForecast, get_upcoming_forecast

# How many days ahead we advise on. Open-Meteo's precipitation probability is
# only meaningfully reliable ~7 days out; beyond that we emit nothing rather than
# fall back to climate normals (a normals-based "alert" is the low-value nudge
# this whole design avoids).
ADVISORY_HORIZON_DAYS = 7


def _coords_for_locales(
    db: Any, user_id: int, locale_ids: list[str]
) -> dict[str, tuple[float, float]]:
    """{locale slug: (lat, lng)} for the user's geocoded locales.

    One lookup per distinct slug (a plan touches very few locales); slugs with no
    coordinates (legacy manual-entry locales) are simply absent from the result.
    Mirrors `layer5.conditions_orchestrator._coords_for_locales`.
    """
    out: dict[str, tuple[float, float]] = {}
    for slug in locale_ids:
        row = db.execute(
            "SELECT lat, lng FROM locale_profiles WHERE user_id = ? AND locale = ?",
            (user_id, slug),
        ).fetchone()
        if row is None:
            continue
        lat, lng = row["lat"], row["lng"]
        if lat is not None and lng is not None:
            out[slug] = (float(lat), float(lng))
    return out


def refresh_upcoming_conditions_for_user(
    db: Any, user_id: int, *, today: date | None = None, fetcher: Any | None = None
) -> int:
    """Rebuild one user's `upcoming_conditions`; return rows written.

    Caller owns the transaction boundary (does NOT commit). `today`/`fetcher` are
    injectable for deterministic tests. Prunes elapsed rows first, then writes a
    row per in-window training day whose locale resolves to a live forecast.
    """
    today = today or date.today()
    horizon_end = today + timedelta(days=ADVISORY_HORIZON_DAYS)

    prune_past(db, user_id, today)

    pv = load_active_plan_version_id(db, user_id)
    if pv is None:
        return 0

    # One representative session-locale per in-window training date (the day's
    # first session carrying a locale — the Layer 5B rule).
    locale_by_date: dict[date, str] = {}
    for s in load_plan_sessions_by_version(db, pv):
        if not s.locale_id:
            continue
        if not (today <= s.date <= horizon_end):
            continue
        locale_by_date.setdefault(s.date, s.locale_id)
    if not locale_by_date:
        return 0

    session_coords = _coords_for_locales(
        db, user_id, sorted(set(locale_by_date.values()))
    )

    # Resolve each date to its forecast point `(label, lat, lng)`. #1036: an
    # `away` event window covering the date wins (destination coords + slug),
    # because away-day sessions routinely still carry the *home* locale — keying
    # off the session locale alone advises on home weather for a trip. Otherwise
    # the session locale's own coords. A date whose point has no coordinates is
    # dropped (best-effort), same degrade as a localeless session.
    point_by_date: dict[date, tuple[str, float, float]] = {}
    for d, slug in locale_by_date.items():
        away = resolve_away_location(db, user_id, d)
        if away is not None:
            point_by_date[d] = away
        elif slug in session_coords:
            lat, lng = session_coords[slug]
            point_by_date[d] = (slug, lat, lng)
    if not point_by_date:
        return 0

    # One forecast call per distinct coordinate — keyed on the rounded token, not
    # the slug, so an away spell and a home week sharing a point (or repeated
    # away days) collapse to a single fetch.
    forecasts: dict[str, dict[date, DayForecast]] = {}
    for _label, lat, lng in point_by_date.values():
        key = f"{lat:.4f},{lng:.4f}"
        if key not in forecasts:
            forecasts[key] = get_upcoming_forecast(
                lat, lng, today, horizon_end, fetcher=fetcher
            )

    rows: list[dict[str, Any]] = []
    for d in sorted(point_by_date):
        label, lat, lng = point_by_date[d]
        fc = forecasts.get(f"{lat:.4f},{lng:.4f}", {}).get(d)
        if fc is None:
            continue
        rows.append(
            {
                "forecast_date": d,
                "locale_id": label,
                "temp_max_c": fc.temp_max_c,
                "temp_min_c": fc.temp_min_c,
                "precip_prob_pct": fc.precip_prob_pct,
            }
        )

    upsert_upcoming_conditions(db, user_id, rows)
    print(
        f"[conditions-refresh] user={user_id} pv={pv} "
        f"days={len(rows)} locations={len(forecasts)}"
    )
    return len(rows)


def refresh_all_upcoming_conditions(
    db: Any, *, today: date | None = None, fetcher: Any | None = None
) -> dict[str, int]:
    """Refresh every user with an active ready plan; return `{users, rows}`.

    Per-user try/except so one bad user/locale can't sink the batch. Caller
    commits.
    """
    user_rows = db.execute(
        "SELECT DISTINCT user_id FROM plan_versions "
        "WHERE generation_status = 'ready' "
        "AND archived_at IS NULL AND completed_at IS NULL"
    ).fetchall()
    users = 0
    total = 0
    for ur in user_rows:
        uid = int(ur["user_id"])
        try:
            total += refresh_upcoming_conditions_for_user(
                db, uid, today=today, fetcher=fetcher
            )
            users += 1
        except Exception as exc:  # best-effort — one user's fault can't sink the batch
            print(
                f"[conditions-refresh] user={uid} ERROR "
                f"{type(exc).__name__}: {exc}"
            )
    return {"users": users, "rows": total}
