"""#196 Phase 2 — the canonical daily-wellness writer.

`materialize_canonical_wellness(db, uid, target_date)` (re)builds the single
best-of `canonical_daily_wellness` row for one (user, date): it merges the three
genuinely-multi-source fields (sleep hours / HRV / resting HR) field-by-field
across the five device sources — freshest-non-null, garmin>whoop>oura>polar>coros
tiebreak — and copies the Garmin-origin context fields (HRV/RHR baselines,
sleep score, training readiness, VO2max, acute training load) straight from
`daily_wellness_metrics`. Idempotent: called on every wellness ingest for the
affected date (Slice 2.2 wires the call sites), upserts ON CONFLICT (user_id,date).

The coalesce rule is a copy of layer3a.integration's (`_WELLNESS_SOURCE_PRIORITY`
+ `_coalesce_wellness_field`) so this slice touches only new code; Slice 2.3
repoints the 3A reader at this table and folds the two copies into one.

Design: designs/CanonicalDailyWellness_196_Phase2_Design_v1.md
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

# Device priority for the freshest-non-null tiebreak — identical to
# layer3a.integration._WELLNESS_SOURCE_PRIORITY (deduped in Slice 2.3).
_WELLNESS_SOURCE_PRIORITY: dict[str, int] = {
    "garmin": 5,
    "whoop": 4,
    "oura": 3,
    "polar": 2,
    "coros": 1,
}

# A candidate value for one field on the target day: (ingest_ts, value, source).
_Candidate = tuple["datetime | None", float, str]


def _coalesce(candidates: list[_Candidate]) -> tuple[float | None, str | None]:
    """Freshest-non-null pick: newest ingest timestamp wins; ties (equal/missing
    timestamps) break on `_WELLNESS_SOURCE_PRIORITY`. Mirrors the 3A reader so a
    later repoint is behaviour-preserving."""
    if not candidates:
        return None, None
    best = max(
        candidates,
        key=lambda c: (c[0] or datetime.min, _WELLNESS_SOURCE_PRIORITY[c[2]]),
    )
    return best[1], best[2]


# Columns written to canonical_daily_wellness (order shared by INSERT + upsert).
_COALESCED_COLS = (
    "total_sleep_hours", "total_sleep_hours_source",
    "hrv_rmssd_ms", "hrv_rmssd_ms_source",
    "resting_hr", "resting_hr_source",
)
_GARMIN_CTX_COLS = (
    "hrv_7d_avg_ms", "resting_hr_7day_avg", "sleep_score",
    "training_readiness", "vo2max_running", "vo2max_cycling",
    "acute_training_load",
)


def materialize_canonical_wellness(db: Any, uid: int, target_date: str) -> None:
    """(Re)build the canonical_daily_wellness row for (uid, target_date)."""
    sleep_c: list[_Candidate] = []
    hrv_c: list[_Candidate] = []
    rhr_c: list[_Candidate] = []

    # Garmin — daily_wellness_metrics carries both the 3 coalesced fields and the
    # widened context fields (one row per user+date), so read them together.
    g = db.execute(
        """
        SELECT sleep_start_ms, sleep_end_ms, hrv_overnight_avg_ms, resting_hr,
               hrv_7d_avg_ms, resting_hr_7day_avg, sleep_score, training_readiness,
               vo2max_running, vo2max_cycling, acute_training_load, updated_at
          FROM daily_wellness_metrics
         WHERE user_id = %s AND date = %s
        """,
        (uid, target_date),
    ).fetchone()
    ctx = {c: None for c in _GARMIN_CTX_COLS}
    if g is not None:
        ts = g["updated_at"]
        start_ms, end_ms = g["sleep_start_ms"], g["sleep_end_ms"]
        if start_ms is not None and end_ms is not None and end_ms > start_ms:
            sleep_c.append((ts, (end_ms - start_ms) / 3600_000.0, "garmin"))
        if g["hrv_overnight_avg_ms"] is not None:
            hrv_c.append((ts, float(g["hrv_overnight_avg_ms"]), "garmin"))
        if g["resting_hr"] is not None:
            rhr_c.append((ts, float(g["resting_hr"]), "garmin"))
        for c in _GARMIN_CTX_COLS:
            ctx[c] = g[c]

    # Non-Garmin device sources live in provider_raw_record (JSONB raw_payload),
    # keyed by external_id = the calendar date. Each (provider, data_type) row is
    # at most one per day, but iterate defensively.
    def _prr(provider: str, data_type: str) -> list[Any]:
        return db.execute(
            """
            SELECT raw_payload, fetched_at
              FROM provider_raw_record
             WHERE user_id = %s AND provider = %s AND data_type = %s
               AND external_id = %s
            """,
            (uid, provider, data_type, target_date),
        ).fetchall()

    def _num(payload: dict, key: str):
        v = payload.get(key)
        return float(v) if v is not None else None

    for r in _prr("polar", "sleep"):
        mins = _num(r["raw_payload"], "total_sleep_min")
        if mins is not None:
            sleep_c.append((r["fetched_at"], mins / 60.0, "polar"))
    for r in _prr("polar", "hrv"):
        v = _num(r["raw_payload"], "hrv_rmssd_ms")
        if v is not None:
            hrv_c.append((r["fetched_at"], v, "polar"))
    for r in _prr("coros", "daily_summary"):
        p = r["raw_payload"]
        start_ms, end_ms = p.get("sleep_start_ms"), p.get("sleep_end_ms")
        if start_ms is not None and end_ms is not None and end_ms > start_ms:
            sleep_c.append((r["fetched_at"], (end_ms - start_ms) / 3600_000.0, "coros"))
        ppg = _num(p, "ppg_hrv")
        if ppg is not None:
            hrv_c.append((r["fetched_at"], ppg, "coros"))
    for provider in ("whoop", "oura"):
        for r in _prr(provider, "daily_summary"):
            p = r["raw_payload"]
            mins = _num(p, "total_sleep_min")
            if mins is not None:
                sleep_c.append((r["fetched_at"], mins / 60.0, provider))
            hrv = _num(p, "hrv_rmssd_ms")
            if hrv is not None:
                hrv_c.append((r["fetched_at"], hrv, provider))
            rhr = _num(p, "resting_hr")
            if rhr is not None:
                rhr_c.append((r["fetched_at"], rhr, provider))

    sleep_h, sleep_src = _coalesce(sleep_c)
    hrv_v, hrv_src = _coalesce(hrv_c)
    rhr_v, rhr_src = _coalesce(rhr_c)

    coalesced = {
        "total_sleep_hours": round(sleep_h, 3) if sleep_h is not None else None,
        "total_sleep_hours_source": sleep_src,
        "hrv_rmssd_ms": hrv_v,
        "hrv_rmssd_ms_source": hrv_src,
        "resting_hr": int(round(rhr_v)) if rhr_v is not None else None,
        "resting_hr_source": rhr_src,
    }

    # No signal for the day → keep no canonical row (and clear a stale one). A
    # re-materialization is the only writer, so a day that lost all its data must
    # not leave a row behind.
    has_value = any(coalesced[c] is not None for c in _COALESCED_COLS) \
        or any(ctx[c] is not None for c in _GARMIN_CTX_COLS)
    if not has_value:
        db.execute(
            "DELETE FROM canonical_daily_wellness WHERE user_id = %s AND date = %s",
            (uid, target_date),
        )
        print(f"[wellness-canon] user={uid} date={target_date} no data -> cleared")
        return

    cols = ("user_id", "date", *_COALESCED_COLS, *_GARMIN_CTX_COLS)
    values = [uid, target_date,
              *[coalesced[c] for c in _COALESCED_COLS],
              *[ctx[c] for c in _GARMIN_CTX_COLS]]
    placeholders = ", ".join(["%s"] * len(cols))
    update_assign = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in (*_COALESCED_COLS, *_GARMIN_CTX_COLS))
    db.execute(
        f"""INSERT INTO canonical_daily_wellness ({', '.join(cols)}, updated_at)
            VALUES ({placeholders}, NOW())
            ON CONFLICT (user_id, date) DO UPDATE SET {update_assign}, updated_at = NOW()""",
        tuple(values),
    )

    # Rule #15 — log the per-field source picks + which context fields landed, so
    # a surprising merge is diagnosable from /admin/logs.
    merged = ", ".join(
        f"{f}<-{s}" for f, s in (("sleep", sleep_src), ("hrv", hrv_src), ("rhr", rhr_src))
        if s is not None)
    ctx_present = ", ".join(c for c in _GARMIN_CTX_COLS if ctx[c] is not None)
    print(f"[wellness-canon] user={uid} date={target_date} "
          f"merged={{{merged}}} garmin_ctx={{{ctx_present}}}")
