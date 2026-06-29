"""#196 Phase 2 — the canonical daily-wellness writer.

`materialize_canonical_wellness(db, uid, target_date)` (re)builds the single
best-of `canonical_daily_wellness` row for one (user, date): it merges the three
genuinely-multi-source fields (sleep hours / HRV / resting HR) field-by-field
across the five device sources — most-complete-record-wins with a per-metric
gap-fill (decision 2 / #196 Phase 5 Track B, a port of the cardio merge), plus an
optional per-athlete HARD PIN (`source_preferences_repo`, B2) that overrides the
primary pick; garmin>whoop>oura>polar>coros breaks completeness ties — and copies
the Garmin-origin context fields (HRV/RHR baselines,
sleep score, training readiness, VO2max, acute training load) straight from
`daily_wellness_metrics`. Idempotent: called on every wellness ingest for the
affected date (Slice 2.2 wires the call sites), upserts ON CONFLICT (user_id,date).

This module is the single home of the wellness coalesce rule
(`_WELLNESS_SOURCE_PRIORITY` + `_coalesce`). Slice 2.3 repointed the 3A reader
(`layer3a.integration.q_layer3A_recent_wellness`) at this materialized table and
retired its inline copy, so the merge logic lives here only.

Design: designs/CanonicalDailyWellness_196_Phase2_Design_v1.md
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

# Device priority for the completeness tiebreak. Garmin first (richest daily
# source), then Whoop + Oura (dedicated recovery devices) above the watches
# Polar/COROS. The sole owner since Slice 2.3 deduped the layer3a copy. As of B2
# this is only a tiebreaker (between equally-complete records / a hard pin
# overrides it); the primary pick is the most-complete daily record.
_WELLNESS_SOURCE_PRIORITY: dict[str, int] = {
    "garmin": 5,
    "whoop": 4,
    "oura": 3,
    "polar": 2,
    "coros": 1,
}

# A candidate value for one field on the target day: (ingest_ts, value, source).
_Candidate = tuple["datetime | None", float, str]


def _rank_sources(*metric_candidates: list[_Candidate]) -> list[str]:
    """Order a day's sources richest-first for the most-complete merge: a source's
    completeness = how many of the tracked metrics (sleep / hrv / rhr) it carries
    that day; ties break on `_WELLNESS_SOURCE_PRIORITY` (garmin>whoop>oura>polar>
    coros). This single order drives both the primary pick and the per-metric
    gap-fill — a faithful port of the cardio merge (decision 2 / #196 Phase 5
    Track B). Deterministic so the merged row — and the 3A integration_bundle_hash
    that reads it (Slice 2.3) — is stable across resumable passes."""
    score: dict[str, int] = {}
    for cands in metric_candidates:
        for src in {c[2] for c in cands}:
            score[src] = score.get(src, 0) + 1
    return sorted(score, key=lambda s: (-score[s], -_WELLNESS_SOURCE_PRIORITY[s]))


def _coalesce(
    candidates: list[_Candidate],
    ranked: list[str],
    pinned: "str | None",
) -> tuple[float | None, str | None]:
    """Pick one value+source for a single metric. HARD PIN first: if `pinned` is
    set and carries a value for this metric, it wins (decision 1). Else most-
    complete: the first source in `ranked` (richest daily record first) that has a
    value here — i.e. primary-first per-metric gap-fill. Within a source the
    freshest row wins (defensive — at most one row/source/day). Deterministic so
    the 3A bundle hash that reads this (Slice 2.3) is stable across passes."""
    if not candidates:
        return None, None
    by_source: dict[str, tuple["datetime | None", float]] = {}
    for ts, val, src in candidates:
        cur = by_source.get(src)
        if cur is None or (ts or datetime.min) >= (cur[0] or datetime.min):
            by_source[src] = (ts, val)
    if pinned is not None and pinned in by_source:
        return by_source[pinned][1], pinned
    for src in ranked:
        if src in by_source:
            return by_source[src][1], src
    return None, None


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
    # Read the athlete's wellness source pin once (B2). A hard pin wins per metric
    # when the pinned provider has a value; absent/empty → most-complete merge.
    # Lazy import: source_preferences_repo imports this module (it reuses
    # `_WELLNESS_SOURCE_PRIORITY`), so importing it at module scope would cycle.
    from source_preferences_repo import WELLNESS, get_source_preferences
    wellness_pin = get_source_preferences(db, uid).get(WELLNESS)

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

    ranked = _rank_sources(sleep_c, hrv_c, rhr_c)
    sleep_h, sleep_src = _coalesce(sleep_c, ranked, wellness_pin)
    hrv_v, hrv_src = _coalesce(hrv_c, ranked, wellness_pin)
    rhr_v, rhr_src = _coalesce(rhr_c, ranked, wellness_pin)

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
    pin_note = f" pin={wellness_pin}" if wellness_pin else ""
    print(f"[wellness-canon] user={uid} date={target_date} "
          f"merged={{{merged}}} garmin_ctx={{{ctx_present}}}{pin_note}")


# ── Slice 2.2: ingest-hook + backfill entry points ────────────────────────

# The (provider, data_type) pairs in provider_raw_record that actually feed a
# canonical row — i.e. the sources materialize_canonical_wellness reads. An
# ingest write OUTSIDE this set (polar 'cardio_load', whoop 'workout', …)
# changes nothing the canonical layer reads, so it must NOT trigger a
# re-materialization. Garmin is absent here on purpose: its daily_wellness_metrics
# write always feeds canonical, so its hook calls materialize_* directly.
_WELLNESS_FEED_DATA_TYPES: dict[str, frozenset[str]] = {
    "polar": frozenset({"sleep", "hrv"}),
    "coros": frozenset({"daily_summary"}),
    "whoop": frozenset({"daily_summary"}),
    "oura": frozenset({"daily_summary"}),
}


def materialize_wellness_for_provider(
    db: Any, uid: int, provider: str, data_type: str, target_date: str,
) -> None:
    """Ingest-hook wrapper for the provider_raw_record writers: re-materialize
    (uid, target_date) only when the row just written is one the canonical layer
    reads. Gating keeps non-wellness writes (cardio load, workouts) from doing
    useless re-materialization work. Runs in the caller's transaction, so the
    canonical row lands atomically with the raw write (and a failure rolls both
    back — consistent with the existing webhook re-dispatch contract)."""
    if data_type in _WELLNESS_FEED_DATA_TYPES.get(provider, frozenset()):
        materialize_canonical_wellness(db, uid, target_date)


def _wellness_backfill_targets(db: Any, uid: int | None = None) -> list[tuple[int, str]]:
    """Every (user_id, date) carrying any wellness source — the backfill
    work-list. Unions the Garmin daily-metrics days with the non-Garmin
    provider_raw_record wellness days (exactly the sources materialize reads),
    casting both date keys to text so the union types line up."""
    where_g = "WHERE date IS NOT NULL" + (" AND user_id = %s" if uid is not None else "")
    where_p = (
        "WHERE (provider, data_type) IN "
        "(('polar','sleep'),('polar','hrv'),('coros','daily_summary'),"
        "('whoop','daily_summary'),('oura','daily_summary'))"
        + (" AND user_id = %s" if uid is not None else "")
    )
    params = (uid, uid) if uid is not None else ()
    rows = db.execute(
        f"""
        SELECT DISTINCT user_id, date::text AS date
          FROM daily_wellness_metrics {where_g}
        UNION
        SELECT DISTINCT user_id, external_id AS date
          FROM provider_raw_record {where_p}
        """,
        params,
    ).fetchall()
    return [(r["user_id"], r["date"]) for r in rows]


def backfill_canonical_wellness(db: Any, uid: int | None = None) -> int:
    """One-time (re)materialization of the canonical row for every historical
    (user, date) that has wellness data. Idempotent — safe to re-run, and a
    day that lost all its data clears its row (materialize's no-data path). The
    caller owns the commit. Returns the number of (user, date) pairs processed."""
    targets = _wellness_backfill_targets(db, uid)
    for user_id, target_date in targets:
        materialize_canonical_wellness(db, user_id, target_date)
    scope = f" user={uid}" if uid is not None else ""
    print(f"[wellness-canon] backfill{scope} materialized {len(targets)} (user,date) pairs")
    return len(targets)


def _main(argv: "list[str] | None" = None) -> int:
    """`python canonical_wellness.py --backfill [--user N]` — run the one-time
    backfill against the DATABASE_URL Postgres. The gated backfill GitHub Action
    sets DATABASE_URL=NEON_DATABASE_URL. `database` is imported lazily here so
    the library stays Flask-free for the unit tests (which import this module)."""
    import argparse

    parser = argparse.ArgumentParser(description="Canonical daily-wellness ops")
    parser.add_argument(
        "--backfill", action="store_true",
        help="(re)materialize every historical (user, date) wellness row")
    parser.add_argument(
        "--user", type=int, default=None,
        help="limit the backfill to one user_id (default: all users)")
    args = parser.parse_args(argv)
    if not args.backfill:
        parser.error("nothing to do — pass --backfill")

    from database import _PgConn, _connect  # lazy: keeps the unit tests Flask-free

    db = _PgConn(_connect())
    try:
        n = backfill_canonical_wellness(db, uid=args.user)
        db.commit()
    finally:
        db.close()
    print(f"[wellness-canon] backfill committed: {n} (user,date) rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
