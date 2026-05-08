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

    # ----- v10 validators -----
    extras = extras or {}
    sub_fk = extras.get("substitution_fks")
    gap_fk = extras.get("training_gap_fks")
    contra = extras.get("contraindicated_conditions")
    di = extras.get("default_inclusion")

    if sub_fk is not None:
        lines.append("## Validation — substitution_fks")
        lines.append("")
        lines.append(
            f"**Rows checked:** {sub_fk['rows_checked']}  ·  "
            f"**PASS:** {sub_fk['pass_count']}  ·  "
            f"**ERROR:** {sub_fk['error_count']}"
        )
        if sub_fk["errors"]:
            lines.append("")
            lines.append("| Target ID | Substitute ID | Broken |")
            lines.append("|---|---|---|")
            for e in sub_fk["errors"]:
                lines.append(
                    f"| {e['target_id']} | {e['substitute_id']} | "
                    f"{', '.join(e['broken'])} |"
                )
        lines.append("")

    if gap_fk is not None:
        lines.append("## Validation — training_gap_fks")
        lines.append("")
        lines.append(
            f"**Rows checked:** {gap_fk['rows_checked']}  ·  "
            f"**PASS:** {gap_fk['pass_count']}  ·  "
            f"**ERROR:** {gap_fk['error_count']}"
        )
        if gap_fk["errors"]:
            lines.append("")
            lines.append("| Discipline ID | Discipline name | Gap type |")
            lines.append("|---|---|---|")
            for e in gap_fk["errors"]:
                lines.append(
                    f"| {e['discipline_id']} | {e['discipline_name']} | "
                    f"{e['gap_type']} |"
                )
        lines.append("")

    if contra is not None:
        lines.append("## Validation — contraindicated_conditions")
        lines.append("")
        lines.append(
            f"**Exercises checked:** {contra['exercises_checked']}  ·  "
            f"**PASS:** {contra['pass_count']}  ·  "
            f"**WARN:** {contra['warn_count']}"
        )
        if contra["warnings"]:
            lines.append("")
            lines.append(
                "Conditions in `exercises.contraindicated_conditions[]` "
                "not present in `layer0.health_condition_categories.category_name`:"
            )
            lines.append("")
            for w in contra["warnings"]:
                unknown = ", ".join(repr(c) for c in w["unknown_conditions"])
                lines.append(
                    f"- `{w['exercise_id']}` {w['exercise_name']} → unknown: {unknown}"
                )
        lines.append("")

    if di is not None:
        lines.append("## Validation — default_inclusion")
        lines.append("")
        lines.append(
            f"**Rows checked:** {di['rows_checked']}  ·  "
            f"**PASS:** {di['pass_count']}  ·  "
            f"**ERROR:** {di['error_count']}"
        )
        if di["errors"]:
            lines.append("")
            lines.append("| Sport | Discipline ID | Default inclusion |")
            lines.append("|---|---|---|")
            for e in di["errors"]:
                lines.append(
                    f"| {e['sport_name']} | {e['discipline_id']} | "
                    f"{e['default_inclusion']!r} |"
                )
        lines.append("")

    # ----- v10 extractor diagnostics -----
    movement_warnings = extras.get("movement_warnings") or []
    matrix_meta = extras.get("matrix_meta") or {}
    pl_split = extras.get("pl_split_stats") or {}
    weekly_failures = extras.get("weekly_failures") or []
    substitute_warnings = extras.get("substitute_warnings") or []

    if matrix_meta or pl_split or movement_warnings or weekly_failures or substitute_warnings:
        lines.append("## v10 extractor diagnostics")
        lines.append("")

    if matrix_meta:
        lines.append(
            f"**Discipline pairing matrix:** scanned R11–R{matrix_meta.get('matrix_last_data_row')}"
            f", {len(matrix_meta.get('matrix_header_ids', []))} header discipline IDs."
        )
        ids = matrix_meta.get("matrix_header_ids", [])
        if ids:
            lines.append("")
            lines.append(f"Header IDs: {', '.join(ids)}")
        lines.append("")

    if pl_split:
        rows_n = pl_split.get("rows", 0)
        with_pres = pl_split.get("with_prescription", 0)
        pct = (with_pres / rows_n * 100) if rows_n else 0.0
        lines.append(
            f"**Phase Load Notes split:** {with_pres}/{rows_n} rows yielded a "
            f"non-NULL `prescription_note` ({pct:.1f}%)."
        )
        if pct < 70.0:
            lines.append("")
            lines.append(
                "⚠️ Coverage below 70% — the heuristic may need tuning. "
                "Inspect `_split_phase_load_notes` and the audit-prefix list."
            )
        lines.append("")

    if weekly_failures:
        lines.append("**Weekly Total Target parser failures:**")
        lines.append("")
        for f in weekly_failures:
            txt = (f.get("weekly_target_text") or "")[:120].replace("\n", " ")
            lines.append(f"- R{f['row_number']} {f['sport_name']} → {txt!r}…")
        lines.append("")

    if movement_warnings:
        lines.append("**Sports Index — unknown enum tokens:**")
        lines.append("")
        for w in movement_warnings:
            for warn in w["warnings"]:
                lines.append(f"- R{w['row_number']} {w['sport_name']}: {warn}")
        lines.append("")

    if substitute_warnings:
        lines.append("**Discipline Substitution Map — dropped rows:**")
        lines.append("")
        for w in substitute_warnings:
            lines.append(
                f"- R{w['row_number']} {w['target_id']} → "
                f"{w['substitute_id']}: {w['reason']}"
            )
        lines.append("")

    # ----- extras (dropped dupes, etc.) -----
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
