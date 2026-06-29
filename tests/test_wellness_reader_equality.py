"""Slice 2.3 reader-equality test (#196 Phase 2), retuned for the B2 merge.

Proves the writer → reader round-trip is deterministic and matches an independent
reimplementation of the merge: for the same underlying multi-source device data,
the **NEW** path (`canonical_wellness.materialize_canonical_wellness` writes the
merged row → `layer3a.integration.q_layer3A_recent_wellness` reads it back) yields
a `recent_wellness` list **byte-identical** to a standalone **reference** coalesce
below.

Why byte-identical matters: the list folds into `integration_bundle_hash`
(exact-float `canonical_json`) and thus the 3A cache key — any drift silently
invalidates 3A caches. The canonical numeric columns are DOUBLE PRECISION
(Slice 2.3 widened them from REAL) so the merged doubles round-trip losslessly.

The reference coalesce below mirrors the production rule. Through Slice 2.3 that
rule was freshest-non-null; **#196 Phase 5 Track B (B2) changed it to
most-complete-record-primary + per-metric gap-fill** (decision 2), and this
reference was retuned to match. The two paths remain independent implementations
(the writer's lives in `canonical_wellness.py`); driving both from one fixture set
cross-checks them.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

import canonical_wellness as cw
from layer3a.integration import _as_date, _window_cutoff, q_layer3A_recent_wellness
from layer4.context import DailyWellnessRecord

_AS_OF = datetime(2026, 5, 20, 12, 0, 0)
_SINCE = 14  # _DEFAULT_SLEEP_WINDOW_DAYS


# ─── Reference reader (independent reimplementation of the B2 merge) ──────────

_WELLNESS_SOURCE_PRIORITY = {"garmin": 5, "whoop": 4, "oura": 3, "polar": 2, "coros": 1}


def _rank_sources_ref(*metric_cands):
    """Richest-first source order: completeness (metrics carried) desc, priority
    desc as the tiebreak — the reference twin of `cw._rank_sources`."""
    score: dict[str, int] = {}
    for cands in metric_cands:
        for src in {c[2] for c in cands}:
            score[src] = score.get(src, 0) + 1
    return sorted(score, key=lambda s: (-score[s], -_WELLNESS_SOURCE_PRIORITY[s]))


def _coalesce_ref(candidates, ranked):
    """Most-complete pick for one metric: the first source in `ranked` that has a
    value (freshest within a source). No pin here — the equality fixtures set none."""
    if not candidates:
        return None, None
    by_source: dict[str, tuple] = {}
    for ts, val, src in candidates:
        cur = by_source.get(src)
        if cur is None or (ts or datetime.min) >= (cur[0] or datetime.min):
            by_source[src] = (ts, val)
    for src in ranked:
        if src in by_source:
            return by_source[src][1], src
    return None, None


def _reference_recent_wellness(db, user_id, as_of, *, since_days=_SINCE):
    """Standalone six-source coalesce mirroring the B2 production merge, so the
    equality assertion compares the new path against an independent implementation."""
    cutoff_iso = _window_cutoff(as_of, since_days).isoformat()
    sleep_cand: dict[date, list] = defaultdict(list)
    hrv_cand: dict[date, list] = defaultdict(list)
    rhr_cand: dict[date, list] = defaultdict(list)

    cur = db.execute("daily_wellness_metrics window", (user_id, cutoff_iso))
    for row in cur.fetchall():
        d = _as_date(row["date"])
        ts = row["updated_at"]
        start_ms, end_ms = row["sleep_start_ms"], row["sleep_end_ms"]
        if start_ms is not None and end_ms is not None and end_ms > start_ms:
            sleep_cand[d].append((ts, (end_ms - start_ms) / 3600_000.0, "garmin"))
        if row["hrv_overnight_avg_ms"] is not None:
            hrv_cand[d].append((ts, float(row["hrv_overnight_avg_ms"]), "garmin"))
        if row["resting_hr"] is not None:
            rhr_cand[d].append((ts, float(row["resting_hr"]), "garmin"))

    cur = db.execute("polar sleep window", (user_id, cutoff_iso))
    for row in cur.fetchall():
        if row["total_sleep_min"] is not None:
            sleep_cand[_as_date(row["date"])].append(
                (row["fetched_at"], row["total_sleep_min"] / 60.0, "polar"))

    cur = db.execute("polar hrv window", (user_id, cutoff_iso))
    for row in cur.fetchall():
        if row["hrv_rmssd_ms"] is not None:
            hrv_cand[_as_date(row["date"])].append(
                (row["fetched_at"], float(row["hrv_rmssd_ms"]), "polar"))

    cur = db.execute("coros daily window", (user_id, cutoff_iso))
    for row in cur.fetchall():
        d = _as_date(row["date"])
        ts = row["fetched_at"]
        start_ms, end_ms = row["sleep_start_ms"], row["sleep_end_ms"]
        if start_ms is not None and end_ms is not None and end_ms > start_ms:
            sleep_cand[d].append((ts, (end_ms - start_ms) / 3600_000.0, "coros"))
        if row["ppg_hrv"] is not None:
            hrv_cand[d].append((ts, float(row["ppg_hrv"]), "coros"))

    for provider in ("whoop", "oura"):
        cur = db.execute(f"{provider} daily window", (user_id, cutoff_iso))
        for row in cur.fetchall():
            d = _as_date(row["date"])
            ts = row["fetched_at"]
            if row["total_sleep_min"] is not None:
                sleep_cand[d].append((ts, row["total_sleep_min"] / 60.0, provider))
            if row["hrv_rmssd_ms"] is not None:
                hrv_cand[d].append((ts, float(row["hrv_rmssd_ms"]), provider))
            if row["resting_hr"] is not None:
                rhr_cand[d].append((ts, float(row["resting_hr"]), provider))

    out: list[DailyWellnessRecord] = []
    for d in sorted(set(sleep_cand) | set(hrv_cand) | set(rhr_cand), reverse=True):
        s_c, h_c, r_c = sleep_cand.get(d, []), hrv_cand.get(d, []), rhr_cand.get(d, [])
        ranked = _rank_sources_ref(s_c, h_c, r_c)
        sleep_h, sleep_src = _coalesce_ref(s_c, ranked)
        hrv_v, hrv_src = _coalesce_ref(h_c, ranked)
        rhr_v, rhr_src = _coalesce_ref(r_c, ranked)
        out.append(DailyWellnessRecord(
            date=d,
            total_sleep_hours=round(sleep_h, 3) if sleep_h is not None else None,
            total_sleep_hours_source=sleep_src,
            hrv_rmssd_ms=hrv_v,
            hrv_rmssd_ms_source=hrv_src,
            resting_hr=int(round(rhr_v)) if rhr_v is not None else None,
            resting_hr_source=rhr_src,
        ))
    return out


# ─── One fixture set, two projections ────────────────────────────────────────
# Values are deliberately not single-precision-exact (7.8333h, 58.3/71.4 ms) so a
# REAL round-trip WOULD drift them — the DOUBLE PRECISION canonical columns are
# exactly what keeps OLD == NEW.

_UID = 1

# garmin daily_wellness_metrics rows: date -> full column dict (writer reads the
# context fields too; the reader ignores them).
_GARMIN: dict[str, dict[str, Any]] = {
    # 2026-05-19 — garmin carries all three (the most-complete record); a fresher
    # but less-complete Whoop (hrv+rhr only) no longer flips anything under B2.
    "2026-05-19": dict(
        sleep_start_ms=0, sleep_end_ms=7 * 3_600_000 + 3_000_000,  # 7.8333h
        hrv_overnight_avg_ms=58.3, resting_hr=50,
        updated_at=datetime(2026, 5, 19, 6, 0),
        hrv_7d_avg_ms=57.0, resting_hr_7day_avg=49, sleep_score=80,
        training_readiness=70, vo2max_running=54.0, vo2max_cycling=49.0,
        acute_training_load=310,
    ),
    # 2026-05-18 — CONTEXT-ONLY: readiness present, no sleep/hrv/rhr. The writer
    # keeps a canonical row (readiness is a Phase-4 input); the reader must skip
    # it, exactly as the old coalesce never emitted a record for such a day.
    "2026-05-18": dict(
        sleep_start_ms=None, sleep_end_ms=None, hrv_overnight_avg_ms=None,
        resting_hr=None, updated_at=datetime(2026, 5, 18, 6, 0),
        hrv_7d_avg_ms=None, resting_hr_7day_avg=None, sleep_score=None,
        training_readiness=65, vo2max_running=None, vo2max_cycling=None,
        acute_training_load=None,
    ),
}

# provider_raw_record rows: (provider, data_type, date) -> [(payload, fetched_at)]
_PRR: dict[tuple[str, str, str], list[tuple[dict, datetime]]] = {
    # 2026-05-19 — Whoop, fresher than garmin, carries only hrv + rhr (no sleep).
    # Under B2 garmin's record is more complete, so it stays primary for all three;
    # Whoop contributes nothing (every metric it has, garmin also has).
    ("whoop", "daily_summary", "2026-05-19"): [
        ({"hrv_rmssd_ms": 71.4, "resting_hr": 45.0}, datetime(2026, 5, 19, 9, 0)),
    ],
    # 2026-05-17 — COROS sleep+hrv (fresher, 2 metrics) and Oura sleep+hrv+rhr
    # (older, 3 metrics). Under B2 Oura is the most-complete record → primary for
    # sleep+hrv+rhr; COROS contributes nothing despite being fresher.
    ("coros", "daily_summary", "2026-05-17"): [
        ({"sleep_start_ms": 0, "sleep_end_ms": 8 * 3_600_000 + 1_800_000,  # 8.5h
          "ppg_hrv": 47.9}, datetime(2026, 5, 17, 8, 0)),
    ],
    ("oura", "daily_summary", "2026-05-17"): [
        ({"total_sleep_min": 500.0, "hrv_rmssd_ms": 46.0, "resting_hr": 48.0},
         datetime(2026, 5, 17, 7, 30)),
    ],
}

_ALL_DATES = sorted(set(_GARMIN) | {d for _, _, d in _PRR})


class _Cursor:
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


class _RefConn:
    """Serves the reference reader's six windowed reads, projecting each fixture
    into the computed-column shape the reader's SQL produced. Provider/data_type
    are fixed per call label."""

    def execute(self, label, params=()):
        if label.startswith("daily_wellness_metrics"):
            return _Cursor(rows=[{"date": d, **g} for d, g in _GARMIN.items()])
        if label.startswith("polar sleep"):
            return _Cursor(rows=self._prr_sleep_min("polar", "sleep"))
        if label.startswith("polar hrv"):
            return _Cursor(rows=self._prr_hrv("polar", "hrv"))
        if label.startswith("coros daily"):
            return _Cursor(rows=self._prr_coros())
        if label.startswith("whoop daily"):
            return _Cursor(rows=self._prr_daily("whoop"))
        if label.startswith("oura daily"):
            return _Cursor(rows=self._prr_daily("oura"))
        return _Cursor()

    @staticmethod
    def _prr_sleep_min(provider, dtype):
        out = []
        for (p, t, d), recs in _PRR.items():
            if (p, t) == (provider, dtype):
                for payload, fetched in recs:
                    out.append({"date": d, "total_sleep_min": payload.get("total_sleep_min"),
                                "fetched_at": fetched})
        return out

    @staticmethod
    def _prr_hrv(provider, dtype):
        out = []
        for (p, t, d), recs in _PRR.items():
            if (p, t) == (provider, dtype):
                for payload, fetched in recs:
                    if payload.get("hrv_rmssd_ms") is not None:
                        out.append({"date": d, "hrv_rmssd_ms": payload["hrv_rmssd_ms"],
                                    "fetched_at": fetched})
        return out

    @staticmethod
    def _prr_coros():
        out = []
        for (p, t, d), recs in _PRR.items():
            if (p, t) == ("coros", "daily_summary"):
                for payload, fetched in recs:
                    out.append({"date": d, "sleep_start_ms": payload.get("sleep_start_ms"),
                                "sleep_end_ms": payload.get("sleep_end_ms"),
                                "ppg_hrv": payload.get("ppg_hrv"), "fetched_at": fetched})
        return out

    @staticmethod
    def _prr_daily(provider):
        out = []
        for (p, t, d), recs in _PRR.items():
            if (p, t) == (provider, "daily_summary"):
                for payload, fetched in recs:
                    out.append({"date": d, "total_sleep_min": payload.get("total_sleep_min"),
                                "hrv_rmssd_ms": payload.get("hrv_rmssd_ms"),
                                "resting_hr": payload.get("resting_hr"), "fetched_at": fetched})
        return out


class _CanonConn:
    """Backs the NEW path: serves materialize's per-(uid, date) reads from the
    same fixtures, captures its canonical upserts/deletes in-memory, then serves
    the reader's windowed canonical SELECT."""

    def __init__(self):
        self.canon: dict[str, dict] = {}

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("INSERT INTO canonical_daily_wellness"):
            cols = ("user_id", "date", *cw._COALESCED_COLS, *cw._GARMIN_CTX_COLS)
            row = dict(zip(cols, params))
            self.canon[row["date"]] = row
            return _Cursor()
        if s.startswith("DELETE FROM canonical_daily_wellness"):
            self.canon.pop(params[1], None)
            return _Cursor()
        if "FROM canonical_daily_wellness" in s:           # reader windowed read
            cutoff = params[1]
            rows = [r for d, r in self.canon.items() if d >= cutoff]
            rows.sort(key=lambda r: r["date"], reverse=True)
            return _Cursor(rows=rows)
        if "FROM daily_wellness_metrics" in s:             # materialize exact-date
            return _Cursor(one=_GARMIN.get(params[1]))
        if "FROM provider_raw_record" in s:                # materialize exact prr
            _uid, provider, dtype, d = params
            recs = _PRR.get((provider, dtype, d), [])
            return _Cursor(rows=[{"raw_payload": p, "fetched_at": f} for p, f in recs])
        return _Cursor()


def _new_path_recent_wellness():
    """Materialize every fixture (uid, date) into the in-memory canonical store,
    then read it back through the production reader."""
    conn = _CanonConn()
    for d in _ALL_DATES:
        cw.materialize_canonical_wellness(conn, _UID, d)
    return q_layer3A_recent_wellness(conn, _UID, _AS_OF)


class TestReaderEquality:
    def test_new_path_equals_reference(self):
        ref = _reference_recent_wellness(_RefConn(), _UID, _AS_OF)
        new = _new_path_recent_wellness()
        assert new == ref

    def test_expected_shape(self):
        # Guards the fixtures themselves: if both paths silently collapsed to []
        # the equality above would pass vacuously. Pin the merged result.
        new = _new_path_recent_wellness()
        assert [r.date for r in new] == [date(2026, 5, 19), date(2026, 5, 17)]  # desc

        r19 = new[0]
        # garmin is the most-complete record → primary for all three (B2).
        assert r19.total_sleep_hours == round(7 + 3_000_000 / 3_600_000, 3)  # garmin
        assert r19.total_sleep_hours_source == "garmin"
        assert r19.hrv_rmssd_ms == 58.3 and r19.hrv_rmssd_ms_source == "garmin"
        assert r19.resting_hr == 50 and r19.resting_hr_source == "garmin"

        r17 = new[1]
        # oura's record (3 metrics) out-completes coros (2) → primary for all three.
        assert r17.total_sleep_hours == round(500.0 / 60.0, 3) and r17.total_sleep_hours_source == "oura"
        assert r17.hrv_rmssd_ms == 46.0 and r17.hrv_rmssd_ms_source == "oura"
        assert r17.resting_hr == 48 and r17.resting_hr_source == "oura"

    def test_context_only_day_skipped_both_paths(self):
        # 2026-05-18 has only Garmin context (readiness, no device sleep/hrv/rhr):
        # absent from both the old coalesce output and the new reader output.
        new = _new_path_recent_wellness()
        ref = _reference_recent_wellness(_RefConn(), _UID, _AS_OF)
        assert all(r.date != date(2026, 5, 18) for r in new)
        assert all(r.date != date(2026, 5, 18) for r in ref)
