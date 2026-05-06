"""Build the markdown ETL report and write it to etl/reports/."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"


def build_report(
    version_tag: str,
    run_at: datetime,
    summaries: list[str],
    sum_to_100: dict[str, Any],
    vocab: dict[str, Any],
    extras: dict[str, Any] | None = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = run_at.strftime("%Y%m%d-%H%M%S")
    path = REPORTS_DIR / f"run-{version_tag}-{stamp}.md"

    lines: list[str] = []
    lines.append(f"# Layer 0 ETL run report — version {version_tag}")
    lines.append("")
    lines.append(f"**Run at:** {run_at.isoformat()}")
    lines.append("")
    lines.append("## Insert summary")
    lines.append("")
    for s in summaries:
        lines.append(f"- {s}")
    lines.append("")

    # ----- sum_to_100 -----
    lines.append("## Validation — sum_to_100")
    lines.append("")
    lines.append(
        f"**Sports checked:** {sum_to_100['sports_checked']}  ·  "
        f"**PASS:** {sum_to_100['pass_count']}  ·  "
        f"**WARN:** {sum_to_100['warn_count']}"
    )
    lines.append("")
    lines.append(
        "Adjusted stack: rows whose `role` contains `(*Conditional)` (or"
        " equals `Conditional`) are zeroed; among paddle disciplines"
        " (Packrafting, Kayaking, Canoeing, SUP, Rowing, Sea Kayak) only"
        " the maximum per-phase contribution is counted (athlete picks one"
        " for race day). HIGH band must reach ≥ 100% on every phase."
    )
    lines.append("")
    if sum_to_100["warn_count"]:
        lines.append("### Sports with WARN")
        lines.append("")
        lines.append("| Sport | BASE high | BUILD high | PEAK high | TAPER high |")
        lines.append("|---|---:|---:|---:|---:|")
        for sr in sum_to_100["sport_results"]:
            if any(s == "WARN" for s in sr["phase_status"].values()):
                adj = sr["adjusted"]
                lines.append(
                    f"| {sr['sport']} | "
                    f"{_fmt(adj['base']['high'], sr['phase_status']['base'])} | "
                    f"{_fmt(adj['build']['high'], sr['phase_status']['build'])} | "
                    f"{_fmt(adj['peak']['high'], sr['phase_status']['peak'])} | "
                    f"{_fmt(adj['taper']['high'], sr['phase_status']['taper'])} |"
                )
        lines.append("")

    # ----- vocab -----
    lines.append("## Validation — vocab_alignment")
    lines.append("")
    lines.append(
        f"**(a) Exercises × body_parts:** "
        f"{vocab['exercises_checked']} checked  ·  "
        f"PASS {vocab['pass_count']}  ·  "
        f"WARN {vocab['warn_count']}"
    )
    if vocab["exercise_warnings"]:
        lines.append("")
        lines.append("Exercises with unknown contraindicated body parts:")
        lines.append("")
        for w in vocab["exercise_warnings"]:
            unknown = ", ".join(repr(p) for p in w["unknown_parts"])
            lines.append(f"- `{w['exercise_id']}` {w['exercise_name']} → unknown: {unknown}")
        lines.append("")
    lines.append("")
    lines.append(
        f"**(b) Sport_exercise_map sport_name × bridge:** "
        f"{vocab['sport_names_checked']} unique sport names checked  ·  "
        f"PASS {vocab['sport_pass']}  ·  "
        f"WARN {vocab['sport_warn']}"
    )
    if vocab["sport_warnings"]:
        lines.append("")
        lines.append(
            "Sport names in `sport_exercise_map` not present in "
            "`sport_discipline_bridge.exercise_db_sport`. The bridge "
            "currently uses the framework's `sport_name` for both columns "
            "of its mapping (a placeholder); resolving these warnings is "
            "the manual reconciliation pass spec Open Item #5 calls for. "
            "Suggested candidates are the closest bridge sports by string "
            "similarity (≥ 0.55 ratio); the rightmost column shows which "
            "framework sports each candidate is currently mapped to."
        )
        lines.append("")
        lines.append("| Exercise-DB sport | # exercises | Closest bridge candidate(s) | Maps to framework |")
        lines.append("|---|---:|---|---|")
        for w in vocab["sport_warnings"]:
            if w["candidates"]:
                cands = " · ".join(
                    f"{c['candidate']} ({c['ratio']:.2f})"
                    for c in w["candidates"]
                )
                framework = " · ".join(
                    sorted({fs for c in w["candidates"] for fs in c["framework_sports"]})
                )
            else:
                cands = "(no close match)"
                framework = ""
            # collapse internal newlines from xlsx wrapping
            sport = w["sport_name"].replace("\n", " ")
            cands = cands.replace("\n", " ")
            framework = framework.replace("\n", " ")
            lines.append(
                f"| {sport} | {w['exercise_count']} | {cands} | {framework} |"
            )
        lines.append("")

    # ----- extras (dropped dupes, etc.) -----
    extras = extras or {}
    dropped = extras.get("dropped_sd_dupes") or []
    dropped_sxm = extras.get("dropped_sxm_dupes") or []
    if dropped or dropped_sxm:
        lines.append("## Source-data drops")
        lines.append("")
    if dropped:
        lines.append("### `sport_discipline_map`")
        lines.append("")
        lines.append(
            "Rows in `Sport × Discipline Map` (Sheet 3) with a duplicate "
            "`(sport_name, discipline_id)` key were dropped (first-seen "
            "wins) to satisfy the spec's UNIQUE constraint. The Triathlon "
            "D-002 case is a true duplicate; the Long Distance / Endurance "
            "Cycling D-005/D-006 cases are sub-format splits the spec's "
            "schema doesn't model."
        )
        lines.append("")
        lines.append("| Source row | Sport | Discipline ID | Discipline name | Role |")
        lines.append("|---:|---|---|---|---|")
        for d in dropped:
            lines.append(
                f"| {d['row_number']} | {d['sport_name']} | {d['discipline_id']} | "
                f"{d['discipline_name']} | {d['role']} |"
            )
        lines.append("")

    if dropped_sxm:
        lines.append("### `sport_exercise_map`")
        lines.append("")
        lines.append(
            "Rows in `Sport-Exercise Map` (0B) with a duplicate "
            "`(exercise_id, sport_name)` key were dropped. These appear to "
            "be accidental rephrasings during DB curation — the same "
            "exercise relevance was logged twice with slightly different "
            "wording."
        )
        lines.append("")
        lines.append("| Source row | Exercise ID | Sport | Exercise name | Priority |")
        lines.append("|---:|---|---|---|---|")
        for d in dropped_sxm:
            lines.append(
                f"| {d['row_number']} | {d['exercise_id']} | {d['sport_name']} | "
                f"{d['exercise_name']} | {d['priority']} |"
            )
        lines.append("")

    path.write_text("\n".join(lines))
    return path


def _fmt(value: float, status: str) -> str:
    badge = "✅" if status == "PASS" else "⚠️"
    return f"{value:.1f} {badge}"
