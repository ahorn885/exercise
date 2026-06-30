"""Data-access helpers for the `upcoming_conditions` signal (#289 producer).

Pure read/write against `upcoming_conditions` — one row per `(user, upcoming
training date)` holding that day's **live** forecast (daily high/low °C, max
precip probability %). The #289 producer cron writes here; the #964
conditions-advisory reconcile reads the table directly in SQL, so no read helper
lives here.

`db.execute(sql, params)` with `?` placeholders; the caller owns the transaction
boundary (these helpers do NOT commit). PG-only — the producer cron only fires
on the deployed Postgres.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def upsert_upcoming_conditions(
    db: Any, user_id: int, rows: list[dict[str, Any]]
) -> int:
    """Upsert the user's forecast rows; return the count written.

    Each row dict carries `forecast_date`, `locale_id`, `temp_max_c`,
    `temp_min_c`, `precip_prob_pct`. Idempotent on `(user_id, forecast_date)` — a
    re-run re-stamps the forecast values and `refreshed_at`.
    """
    for r in rows:
        db.execute(
            """INSERT INTO upcoming_conditions
                   (user_id, forecast_date, locale_id,
                    temp_max_c, temp_min_c, precip_prob_pct, refreshed_at)
                VALUES (?, ?, ?, ?, ?, ?, NOW())
                ON CONFLICT (user_id, forecast_date) DO UPDATE SET
                    locale_id = EXCLUDED.locale_id,
                    temp_max_c = EXCLUDED.temp_max_c,
                    temp_min_c = EXCLUDED.temp_min_c,
                    precip_prob_pct = EXCLUDED.precip_prob_pct,
                    refreshed_at = NOW()""",
            (
                user_id,
                r["forecast_date"],
                r.get("locale_id"),
                r["temp_max_c"],
                r["temp_min_c"],
                r["precip_prob_pct"],
            ),
        )
    return len(rows)


def prune_past(db: Any, user_id: int, today: date) -> None:
    """Delete the user's rows for dates before `today` (elapsed / stale days)."""
    db.execute(
        "DELETE FROM upcoming_conditions WHERE user_id = ? AND forecast_date < ?",
        (user_id, today),
    )


def load_upcoming_for_user(db: Any, user_id: int) -> list[dict[str, Any]]:
    """The user's upcoming-forecast rows from today forward, ordered by date.

    Backs the #1035 plan-view "upcoming conditions" surface — the live forecast
    the conditions-advisory nudge fires on, rendered beside the Layer-5B climate
    normals so the advisory's CTA lands on the forecast that triggered it. The
    producer prunes elapsed rows and writes only in-horizon days, so a plain
    `forecast_date >= CURRENT_DATE` filter returns exactly the live window. Rows
    are normalised to plain dicts (`forecast_date`, `locale_id`, `temp_max_c`,
    `temp_min_c`, `precip_prob_pct`) so callers can `.get(...)` uniformly.
    """
    rows = db.execute(
        """SELECT forecast_date, locale_id,
                  temp_max_c, temp_min_c, precip_prob_pct
             FROM upcoming_conditions
            WHERE user_id = ? AND forecast_date >= CURRENT_DATE
            ORDER BY forecast_date""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]
