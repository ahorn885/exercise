"""Sum-to-100 validation per spec §6.4.

For each sport in `layer0.phase_load_allocation`, compute the adjusted stack
(conditionals zeroed, paddle disciplines treated as interchangeable — only
the maximum contribution counted) and report whether the HIGH band reaches
100% on each phase. The check is a WARN (informational) — the ETL never
fails on this.

Reference: `Phase_Load_Allocation_Audit_Log.md` (the AR pre-audit finding
"Adjusted (paddle interchange + race-specific minors zeroed): 77–109 / 88–
120 / 89–122 / 64–90" articulates the exact adjustment this validator
re-applies in code).
"""
from __future__ import annotations

from typing import Any

PHASES = ("base", "build", "peak", "taper")

# Discipline names treated as interchangeable for "paddle interchange".
# Source: AR audit log line 33 + Vocab Audit §3 (kayak / packraft / canoe
# decompose-to-atomic). The athlete picks one for race day; for the sum-to-
# 100 check we count only the largest contributor per phase.
PADDLE_DISCIPLINES = {
    "Packrafting",
    "Kayaking",
    "Canoeing",
    "Sea Kayak",
    "Rowing",
    "SUP",
}

# Special "totals" rows that aren't disciplines and must be skipped from
# the per-phase sum.
SKIP_DISCIPLINE_NAMES = {"Weekly Total Target"}


def _is_conditional(role: str) -> bool:
    if not role:
        return False
    r = role.lower()
    return "(*conditional)" in r or r.strip() == "conditional"


def run_sum_to_100(conn) -> dict[str, Any]:
    """Run the sum-to-100 check across every sport and return a structured
    summary suitable for both stdout printing and the markdown report.
    """
    by_sport = _load_phase_loads(conn)
    sport_results: list[dict[str, Any]] = []
    pass_count = 0
    warn_count = 0
    for sport, rows in sorted(by_sport.items()):
        adjusted = _compute_adjusted_stack(rows)
        # Per phase, decide PASS / WARN. HIGH band must reach >= 100%.
        phase_status: dict[str, str] = {}
        for phase in PHASES:
            high = adjusted[phase]["high"]
            phase_status[phase] = "PASS" if high >= 100.0 else "WARN"
        any_warn = any(s == "WARN" for s in phase_status.values())
        if any_warn:
            warn_count += 1
        else:
            pass_count += 1
        sport_results.append({
            "sport": sport,
            "adjusted": adjusted,
            "phase_status": phase_status,
        })
    return {
        "sports_checked": len(by_sport),
        "pass_count": pass_count,
        "warn_count": warn_count,
        "sport_results": sport_results,
    }


def _load_phase_loads(conn) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sport_name, discipline_name, role,
                   base_pct_low, base_pct_high,
                   build_pct_low, build_pct_high,
                   peak_pct_low, peak_pct_high,
                   taper_pct_low, taper_pct_high
              FROM layer0.phase_load_allocation
             WHERE superseded_at IS NULL
            """
        )
        for row in cur.fetchall():
            sport, disc, role, *pcts = row
            if disc in SKIP_DISCIPLINE_NAMES:
                continue
            entry = {
                "discipline_name": disc,
                "role": role or "",
                "is_conditional": _is_conditional(role or ""),
                "is_paddle": disc in PADDLE_DISCIPLINES,
                "base_low": _f(pcts[0]),  "base_high": _f(pcts[1]),
                "build_low": _f(pcts[2]), "build_high": _f(pcts[3]),
                "peak_low": _f(pcts[4]),  "peak_high": _f(pcts[5]),
                "taper_low": _f(pcts[6]), "taper_high": _f(pcts[7]),
            }
            out.setdefault(sport, []).append(entry)
    return out


def _f(x) -> float:
    return float(x) if x is not None else 0.0


def _compute_adjusted_stack(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Return:
        {
          'base':  {'low': X, 'high': Y},
          'build': {'low': X, 'high': Y},
          ...
        }
    Conditionals contribute 0; among paddle disciplines, only the max
    per-phase contribution is counted (interchangeable interpretation).
    """
    sums: dict[str, dict[str, float]] = {p: {"low": 0.0, "high": 0.0} for p in PHASES}
    paddle_max: dict[str, dict[str, float]] = {p: {"low": 0.0, "high": 0.0} for p in PHASES}

    for row in rows:
        if row["is_conditional"]:
            continue
        for phase in PHASES:
            low = row[f"{phase}_low"]
            high = row[f"{phase}_high"]
            if row["is_paddle"]:
                if low > paddle_max[phase]["low"]:
                    paddle_max[phase]["low"] = low
                if high > paddle_max[phase]["high"]:
                    paddle_max[phase]["high"] = high
            else:
                sums[phase]["low"] += low
                sums[phase]["high"] += high
    # Add the single representative paddle contribution back in
    for phase in PHASES:
        sums[phase]["low"] += paddle_max[phase]["low"]
        sums[phase]["high"] += paddle_max[phase]["high"]
    return sums
