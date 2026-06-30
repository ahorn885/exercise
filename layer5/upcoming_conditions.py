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

    # One representative locale per in-window training date (the day's first
    # session carrying a locale — the Layer 5B rule).
    locale_by_date: dict[date, str] = {}
    for s in load_plan_sessions_by_version(db, pv):
        if not s.locale_id:
            continue
        if not (today <= s.date <= horizon_end):
            continue
        locale_by_date.setdefault(s.date, s.locale_id)
    if not locale_by_date:
        return 0

    coords = _coords_for_locales(db, user_id, sorted(set(locale_by_date.values())))
    if not coords:
        return 0

    # One forecast call per distinct locale, spanning the whole window.
    forecasts: dict[str, dict[date, DayForecast]] = {
        slug: get_upcoming_forecast(lat, lng, today, horizon_end, fetcher=fetcher)
        for slug, (lat, lng) in coords.items()
    }

    rows: list[dict[str, Any]] = []
    for d in sorted(locale_by_date):
        slug = locale_by_date[d]
        fc = forecasts.get(slug, {}).get(d)
        if fc is None:
            continue
        rows.append(
            {
                "forecast_date": d,
                "locale_id": slug,
                "temp_max_c": fc.temp_max_c,
                "temp_min_c": fc.temp_min_c,
                "precip_prob_pct": fc.precip_prob_pct,
            }
        )

    upsert_upcoming_conditions(db, user_id, rows)
    print(
        f"[conditions-refresh] user={user_id} pv={pv} "
        f"days={len(rows)} locales={len(coords)}"
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
