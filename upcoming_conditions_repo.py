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
