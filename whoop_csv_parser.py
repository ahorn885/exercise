"""WHOOP CSV wellness parser (#767 manual-upload slice 4).

Parses the `physiological_cycles.csv` from a WHOOP "export your data" bundle
into per-day wellness records shaped for `provider_raw_record`
(`provider='whoop'`, `data_type='daily_summary'`), so the Layer-3A
`q_layer3A_recent_wellness` coalesce reads Whoop sleep / HRV / resting-HR the
same way it reads Polar and COROS — no reader rewrite beyond the new whoop
branch + the `WellnessSource` extension.

`physiological_cycles.csv` is one row per physiological cycle (≈ one per day):
HRV (RMSSD, ms), resting HR (bpm), recovery score, day strain, and a sleep
summary (asleep / in-bed durations in minutes). WHOOP's exact header strings
drift across export versions and locales, so columns are resolved by a
normalized-token *contains* match (lowercase, alphanumeric-only) rather than
exact equality — tolerant of casing / unit-suffix / version drift, the same
philosophy as the namespace-agnostic local-name match in `tcx_gpx_parser`.

Built against WHOOP's documented export schema (Andy-ratified 2026-06-19);
LIVE-VERIFY the column resolution against a real export is owed (Rule #14) — the
Rule #15 `[whoop-wellness]` log line below prints the resolved column map so a
silent header drift (a metric dropping out of `cols=`) is diagnosable in prod.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Callable


# Each target payload key → predicate over a *normalized* header cell. First
# matching (unclaimed) column wins. Order matters only for disambiguation; the
# predicates are written to be mutually exclusive on a real WHOOP header.
_COLUMN_MATCHERS: dict[str, Callable[[str], bool]] = {
    # "Cycle start time" → the day the cycle belongs to.
    "date": lambda h: "cycle start" in h,
    # "Heart rate variability (ms)" — WHOOP HRV is RMSSD, our canonical unit.
    "hrv_rmssd_ms": lambda h: "heart rate variability" in h or h == "hrv"
    or h.startswith("hrv "),
    # "Resting heart rate (bpm)".
    "resting_hr": lambda h: "resting heart rate" in h or "resting hr" in h,
    # "Asleep duration (min)" — actual sleep, NOT "In bed duration".
    "total_sleep_min": lambda h: "asleep duration" in h
    or ("asleep" in h and "duration" in h),
    # Corroboration-only (record-don't-drop); not read by the coalesce.
    "recovery_score": lambda h: "recovery score" in h,
    "day_strain": lambda h: "day strain" in h,
    "sleep_performance_pct": lambda h: "sleep performance" in h,
}

# Metrics the Layer-3A coalesce actually reads — at least one must be present
# on a row for it to be worth recording.
_COALESCE_KEYS = ("total_sleep_min", "hrv_rmssd_ms", "resting_hr")

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _norm(header: str) -> str:
    """Lowercase + collapse every non-alphanumeric run to a single space."""
    return re.sub(r"[^a-z0-9]+", " ", header.lower()).strip()


def _resolve_columns(header: list[str]) -> dict[str, int]:
    """Map each target key to a column index via the first unclaimed header
    cell whose normalized form satisfies the key's predicate."""
    idx: dict[str, int] = {}
    for col_i, raw in enumerate(header):
        h = _norm(raw)
        for key, pred in _COLUMN_MATCHERS.items():
            if key not in idx and pred(h):
                idx[key] = col_i
                break
    return idx


def _date_of(value: str) -> str | None:
    """Extract the ISO date (YYYY-MM-DD) from a WHOOP timestamp cell
    ("2024-01-15 06:30:00", "2024-01-15T06:30:00+00:00", …)."""
    m = _DATE_RE.search(value or "")
    return m.group(1) if m else None


def _pos(value: str) -> float | None:
    """Positive-float coercion (sleep minutes / HRV / RHR are all > 0).
    Blank / non-numeric / non-positive → None rather than raising."""
    try:
        v = float((value or "").strip())
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _num(value: str) -> float | None:
    """Non-negative-float coercion for corroboration fields (recovery 0-100,
    strain 0-21) where 0 is meaningful."""
    try:
        v = float((value or "").strip())
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def parse_whoop_physiological_cycles(raw: bytes) -> list[dict]:
    """Parse a WHOOP `physiological_cycles.csv` (bytes) → one record per day,
    newest-first ordering not guaranteed (the writer keys on the date). Each
    record:

        {'date': 'YYYY-MM-DD',
         'total_sleep_min': float | None,
         'hrv_rmssd_ms':    float | None,
         'resting_hr':      int   | None,
         'recovery_score':  float | None,   # corroboration only
         'day_strain':      float | None,
         'sleep_performance_pct': float | None}

    Raises ValueError if the file has no header or no resolvable date column /
    no coalesce-relevant metric column — i.e. it is not a recognizable
    physiological_cycles export.
    """
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("WHOOP CSV is empty (no header row).")

    idx = _resolve_columns(header)
    if "date" not in idx:
        raise ValueError(
            "WHOOP CSV has no 'Cycle start time' column — not a "
            "physiological_cycles export."
        )
    if not any(k in idx for k in _COALESCE_KEYS):
        raise ValueError(
            "WHOOP CSV carries no sleep / HRV / resting-HR column — nothing to "
            "ingest from this export."
        )

    out: list[dict] = []
    n_rows = skipped_no_date = skipped_empty = 0

    def _cell(row: list[str], key: str) -> str:
        col = idx.get(key)
        return row[col] if col is not None and col < len(row) else ""

    for row in reader:
        if not any(c.strip() for c in row):  # blank line
            continue
        n_rows += 1
        date = _date_of(_cell(row, "date"))
        if not date:
            skipped_no_date += 1
            continue

        rec = {
            "date": date,
            "total_sleep_min": _pos(_cell(row, "total_sleep_min")),
            "hrv_rmssd_ms": _pos(_cell(row, "hrv_rmssd_ms")),
            "resting_hr": _pos(_cell(row, "resting_hr")),
            "recovery_score": _num(_cell(row, "recovery_score")),
            "day_strain": _num(_cell(row, "day_strain")),
            "sleep_performance_pct": _num(_cell(row, "sleep_performance_pct")),
        }
        if rec["resting_hr"] is not None:
            rec["resting_hr"] = int(round(rec["resting_hr"]))
        if all(rec[k] is None for k in _COALESCE_KEYS):
            skipped_empty += 1
            continue
        out.append(rec)

    print(  # Rule #15 — resolved column map makes a silent header drift visible
        f"[whoop-wellness] physiological_cycles rows={n_rows} kept={len(out)} "
        f"skipped_no_date={skipped_no_date} skipped_empty={skipped_empty} "
        f"cols={ {k: header[i] for k, i in idx.items()} }"
    )

    if not out:
        raise ValueError(
            "WHOOP CSV parsed but yielded no usable day rows "
            "(no date + metric on any row)."
        )
    return out
