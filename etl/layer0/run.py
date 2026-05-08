"""Layer 0 ETL — orchestrator.

Usage:
    python -m etl.layer0.run --version-tag 1.0

Reads `DATABASE_URL` from the environment. Spec: §6 (run order),
§4 (per-table parsing).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from etl.layer0 import db
from etl.layer0.db import insert_versioned, now_utc, to_jsonb
from etl.layer0.extractors import exercise_db, sports_framework, vocabulary
from etl.layer0.sport_name_aliases import SPORT_NAME_ALIASES, _ALL
from etl.layer0.validation.contraindicated_conditions import (
    run_contraindicated_conditions,
)
from etl.layer0.validation.default_inclusion import run_default_inclusion
from etl.layer0.validation.fk_checks import (
    run_substitution_fks,
    run_training_gap_fks,
)
from etl.layer0.validation.report import build_report
from etl.layer0.validation.sum_to_100 import run_sum_to_100
from etl.layer0.validation.vocab_alignment import run_vocab_alignment

SOURCES = Path(__file__).parent.parent / "sources"
SPORTS_XLSX = SOURCES / "Sports_Framework_v10.xlsx"
EXERCISES_XLSX = SOURCES / "AR_Exercise_Database_v17.xlsx"
VOCAB_MD = SOURCES / "Vocabulary_Audit_v2.md"

# v10 source-version strings (re-run #3). 0A bumps with the framework xlsx.
# 0B/0C content is unchanged — `-r3` marks the schema env this load runs in.
SOURCE_VERSION_0A = "0A-v10.0"
SOURCE_VERSION_0B = "0B-v17.0-r3"
SOURCE_VERSION_0C = "0C-v2.0-r1"


def _v(family: str, tag: str) -> str:
    return f"{family}-v{tag}"


def _print(line: str) -> None:
    print(line, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Layer 0 ETL.")
    parser.add_argument(
        "--version-tag",
        required=True,
        help="Version tag suffix (e.g. '1.0' → 0A-v1.0, 0B-v1.0, 0C-v1.0).",
    )
    args = parser.parse_args(argv)
    tag = args.version_tag.strip()
    # When the tag is "1.3" we use the explicit v10 / r3 / r1 strings;
    # otherwise fall back to family-vTAG so older version strings keep
    # working (regression guard for ad-hoc reruns).
    if tag == "1.3":
        v_0a, v_0b, v_0c = SOURCE_VERSION_0A, SOURCE_VERSION_0B, SOURCE_VERSION_0C
    else:
        v_0a = _v("0A", tag)
        v_0b = _v("0B", tag)
        v_0c = _v("0C", tag)
    run_at = now_utc()

    _print("[layer0 ETL] Connecting to Neon...")
    summaries: list[str] = []
    warnings_per_step: list[tuple[str, int]] = []

    with db.connect() as conn:
        db.apply_schema(conn)

        # ----- Phase 1 — Vocabularies (0C) -----
        _print("[layer0 ETL] Phase 1 — Vocabularies")
        vocab = vocabulary.parse_vocabulary_md(VOCAB_MD)

        n = insert_versioned(
            conn, "layer0.body_parts",
            ["canonical_name", "body_region", "source_origin", "notes"],
            [
                (r["canonical_name"], r["body_region"], r["source_origin"], r["notes"])
                for r in vocab["body_parts"]
            ],
            v_0c, run_at, source_family="0C",
        )
        _print(f"layer0.body_parts: inserted {n} rows")
        summaries.append(f"layer0.body_parts: {n}")

        n = insert_versioned(
            conn, "layer0.health_condition_categories",
            ["category_name", "description"],
            [(r["category_name"], r["description"]) for r in vocab["health_condition_categories"]],
            v_0c, run_at, source_family="0C",
        )
        _print(f"layer0.health_condition_categories: inserted {n} rows")
        summaries.append(f"layer0.health_condition_categories: {n}")

        n = insert_versioned(
            conn, "layer0.equipment_items",
            ["canonical_name", "equipment_category", "is_universal", "notes"],
            [
                (r["canonical_name"], r["equipment_category"], r["is_universal"], r["notes"])
                for r in vocab["equipment_items"]
            ],
            v_0c, run_at, source_family="0C",
        )
        _print(f"layer0.equipment_items: inserted {n} rows")
        summaries.append(f"layer0.equipment_items: {n}")

        n = insert_versioned(
            conn, "layer0.terrain_types",
            ["canonical_name", "notes"],
            [(r["canonical_name"], r["notes"]) for r in vocab["terrain_types"]],
            v_0c, run_at, source_family="0C",
        )
        _print(f"layer0.terrain_types: inserted {n} rows")
        summaries.append(f"layer0.terrain_types: {n}")

        n = insert_versioned(
            conn, "layer0.sport_specific_gear_toggles",
            ["toggle_name", "display_label", "description", "paired_equipment_categories"],
            [
                (
                    r["toggle_name"],
                    r["display_label"],
                    r["description"],
                    r["paired_equipment_categories"],
                )
                for r in vocab["sport_specific_gear_toggles"]
            ],
            v_0c, run_at, source_family="0C",
        )
        _print(f"layer0.sport_specific_gear_toggles: inserted {n} rows")
        summaries.append(f"layer0.sport_specific_gear_toggles: {n}")

        # Alias map — curated vocabulary artifact, versioned under 0C
        # Load framework sport names directly from xlsx (Sports Index sheet)
        # so this block does not depend on Phase 2 having run first.
        _wb_si = sports_framework.open_workbook(SPORTS_XLSX)["Sports Index"]
        _all_fw = [
            str(_wb_si.cell(row=r, column=1).value).strip().replace("\n", " ")
            for r in range(2, _wb_si.max_row + 1)
            if _wb_si.cell(row=r, column=1).value
        ]
        alias_rows = []
        for ex_sport, targets in SPORT_NAME_ALIASES.items():
            fw_list = _all_fw if targets == _ALL else targets
            for fw in fw_list:
                alias_rows.append((ex_sport, fw))
        n = insert_versioned(
            conn, "layer0.sport_name_aliases",
            ["exercise_db_sport", "framework_sport"],
            alias_rows,
            v_0c, run_at, source_family="0C",
        )
        _print(f"layer0.sport_name_aliases: inserted {n} rows")
        summaries.append(f"layer0.sport_name_aliases: {n}")

        # ----- Phase 2 — Sports framework (0A) -----
        _print("[layer0 ETL] Phase 2 — Sports Framework")
        wb = sports_framework.open_workbook(SPORTS_XLSX)

        movement_warnings: list = []
        sports_rows = sports_framework.extract_sports(
            wb["Sports Index"], movement_warnings=movement_warnings,
        )
        if movement_warnings:
            _print(
                f"  [warn] sports: {len(movement_warnings)} row(s) had unknown "
                f"movement / endurance / format tokens — see report"
            )
        sports_columns = [
            "sport_name", "typical_duration_range", "team_vs_solo",
            "flag_navigation", "navigation_notes",
            "flag_sleep_deprivation", "sleep_deprivation_notes",
            "flag_pack_carry", "pack_carry_notes",
            "pack_weight_lbs_low", "pack_weight_lbs_high",
            "flag_transition_training", "transition_training_notes",
            "primary_discipline_count", "secondary_discipline_count",
            "status_label",
            "constituent_movements", "endurance_profile",
            "participation_format", "multi_discipline",
        ]
        n = insert_versioned(
            conn, "layer0.sports",
            sports_columns,
            [tuple(r[k] for k in sports_columns) for r in sports_rows],
            v_0a, run_at, source_family="0A",
        )
        _print(f"layer0.sports: inserted {n} rows")
        summaries.append(f"layer0.sports: {n}")

        disc_rows = sports_framework.extract_disciplines(wb["Discipline Library"])
        disciplines_columns = [
            "discipline_id", "discipline_name", "discipline_category",
            "min_base_phase_text", "min_base_phase_weeks_low", "min_base_phase_weeks_high",
            "periodization_text", "ramp_text", "age_adjusted_ramp_text",
            "age_ramp_40_44_pct", "age_ramp_45_54_pct", "age_ramp_55_plus_pct",
            "taper_norms_text", "common_injury_patterns", "injury_preceding_behaviors",
            "recovery_priority_text", "recovery_modalities", "evidence_quality_text",
            "stimulus_components",
        ]
        n = insert_versioned(
            conn, "layer0.disciplines",
            disciplines_columns,
            [tuple(r[k] for k in disciplines_columns) for r in disc_rows],
            v_0a, run_at, source_family="0A",
        )
        _print(f"layer0.disciplines: inserted {n} rows")
        summaries.append(f"layer0.disciplines: {n}")

        dropped_sd_dupes: list = []
        sd_rows = sports_framework.extract_sport_discipline_map(
            wb["Sport × Discipline Map"], dropped_dupes=dropped_sd_dupes,
        )
        if dropped_sd_dupes:
            _print(
                f"  [warn] sport_discipline_map: dropped {len(dropped_sd_dupes)} duplicate "
                f"(sport, discipline_id) rows — see report"
            )
        n = insert_versioned(
            conn, "layer0.sport_discipline_map",
            [
                "sport_name", "discipline_id", "discipline_name", "applicability", "role",
                "race_time_pct_text", "race_time_pct_low", "race_time_pct_high",
                "sport_specific_context", "b2b_pairing_rule_text", "phase_load_text",
            ],
            [tuple(r[k] for k in [
                "sport_name", "discipline_id", "discipline_name", "applicability", "role",
                "race_time_pct_text", "race_time_pct_low", "race_time_pct_high",
                "sport_specific_context", "b2b_pairing_rule_text", "phase_load_text",
            ]) for r in sd_rows],
            v_0a, run_at, source_family="0A",
        )
        _print(f"layer0.sport_discipline_map: inserted {n} rows")
        summaries.append(f"layer0.sport_discipline_map: {n}")

        # discipline_pairing — matrix + b2b fallback
        matrix_meta: dict = {}
        matrix_rows = sports_framework.extract_discipline_pairing_matrix(
            wb["Discipline Pairing Matrix"], debug_meta=matrix_meta,
        )
        _print(
            f"  discipline_pairing matrix: scanned R11–R{matrix_meta.get('matrix_last_data_row')}, "
            f"{len(matrix_meta.get('matrix_header_ids', []))} header IDs"
        )
        name_to_id = {d["discipline_name"]: d["discipline_id"] for d in disc_rows}
        matrix_pairs = {(r["discipline_id_a"], r["discipline_id_b"]) for r in matrix_rows}
        fallback_rows = sports_framework.extract_pairing_b2b_fallback(
            sd_rows, name_to_id, matrix_pairs
        )
        all_pair_rows = matrix_rows + fallback_rows
        n = insert_versioned(
            conn, "layer0.discipline_pairing",
            ["discipline_id_a", "discipline_id_b", "pairing_rating", "rationale", "source"],
            [tuple(r[k] for k in [
                "discipline_id_a", "discipline_id_b", "pairing_rating", "rationale", "source"
            ]) for r in all_pair_rows],
            v_0a, run_at, source_family="0A",
        )
        _print(f"layer0.discipline_pairing: inserted {n} rows "
               f"({len(matrix_rows)} matrix + {len(fallback_rows)} fallback)")
        summaries.append(
            f"layer0.discipline_pairing: {n} ({len(matrix_rows)} matrix + {len(fallback_rows)} fallback)"
        )

        pl_split_stats: dict = {}
        pl_rows = sports_framework.extract_phase_load_allocation(
            wb["Phase Load Allocation"], split_stats=pl_split_stats,
        )
        pl_columns = [
            "sport_name", "discipline_id", "discipline_name", "role",
            "base_pct_low", "base_pct_high", "build_pct_low", "build_pct_high",
            "peak_pct_low", "peak_pct_high", "taper_pct_low", "taper_pct_high",
            "notes_conditions", "default_inclusion",
            "prescription_note", "audit_log", "raw_notes",
        ]
        n = insert_versioned(
            conn, "layer0.phase_load_allocation",
            pl_columns,
            [tuple(r[k] for k in pl_columns) for r in pl_rows],
            v_0a, run_at, source_family="0A",
        )
        if pl_split_stats.get("rows"):
            pct = (pl_split_stats["with_prescription"] / pl_split_stats["rows"]) * 100
            _print(
                f"layer0.phase_load_allocation: inserted {n} rows "
                f"(prescription_note coverage: {pl_split_stats['with_prescription']}/"
                f"{pl_split_stats['rows']} = {pct:.1f}%)"
            )
        else:
            _print(f"layer0.phase_load_allocation: inserted {n} rows")
        summaries.append(f"layer0.phase_load_allocation: {n}")

        weekly_failures: list = []
        wt_rows = sports_framework.extract_phase_load_weekly_totals(
            wb["Phase Load Allocation"], parse_failures=weekly_failures,
        )
        wt_columns = [
            "sport_name", "phase",
            "weekly_low_hours", "weekly_high_hours",
            "weekly_target_text",
        ]
        n = insert_versioned(
            conn, "layer0.phase_load_weekly_totals",
            wt_columns,
            [tuple(r[k] for k in wt_columns) for r in wt_rows],
            v_0a, run_at, source_family="0A",
        )
        if weekly_failures:
            _print(
                f"  [warn] phase_load_weekly_totals: {len(weekly_failures)} sport(s) "
                f"failed to parse 4 phases — see report"
            )
        _print(f"layer0.phase_load_weekly_totals: inserted {n} rows")
        summaries.append(f"layer0.phase_load_weekly_totals: {n}")

        tf_rows = sports_framework.extract_team_formats(wb["Team Format Cross-Reference"])
        n = insert_versioned(
            conn, "layer0.team_formats",
            [
                "sport_name", "formats_available", "team_format_types",
                "unified_team_description", "relay_specialist_description",
                "training_implication_unified", "training_implication_relay",
                "key_distinctions_notes",
            ],
            [tuple(r[k] for k in [
                "sport_name", "formats_available", "team_format_types",
                "unified_team_description", "relay_specialist_description",
                "training_implication_unified", "training_implication_relay",
                "key_distinctions_notes",
            ]) for r in tf_rows],
            v_0a, run_at, source_family="0A",
        )
        _print(f"layer0.team_formats: inserted {n} rows")
        summaries.append(f"layer0.team_formats: {n}")

        csp_rows = sports_framework.extract_cross_sport_properties(wb["Cross-Sport Properties"])
        csp_columns = [
            "property_id", "property_name", "description", "scope",
            "ranking_text", "estimated_values",
            "source_evidence", "source_text", "confidence", "notes",
        ]
        n = insert_versioned(
            conn, "layer0.cross_sport_properties",
            csp_columns,
            [tuple(r[k] for k in csp_columns) for r in csp_rows],
            v_0a, run_at, source_family="0A",
        )
        _print(f"layer0.cross_sport_properties: inserted {n} rows")
        summaries.append(f"layer0.cross_sport_properties: {n}")

        # v10 — Discipline Substitution Map
        substitute_warnings: list = []
        ds_rows = sports_framework.extract_discipline_substitutes(
            wb, parse_warnings=substitute_warnings,
        )
        ds_columns = [
            "target_id", "target_name", "substitute_id", "substitute_name",
            "fidelity", "constraints", "category", "substitute_covers",
        ]
        n = insert_versioned(
            conn, "layer0.discipline_substitutes",
            ds_columns,
            [tuple(r[k] for k in ds_columns) for r in ds_rows],
            v_0a, run_at, source_family="0A",
        )
        if substitute_warnings:
            _print(
                f"  [warn] discipline_substitutes: dropped {len(substitute_warnings)} "
                f"row(s) with bad fidelity — see report"
            )
        _print(f"layer0.discipline_substitutes: inserted {n} rows")
        summaries.append(f"layer0.discipline_substitutes: {n}")

        # v10 — Discipline Training Gaps
        dtg_rows = sports_framework.extract_discipline_training_gaps(wb)
        dtg_columns = [
            "discipline_id", "discipline_name", "gap_type",
            "notes", "multi_substitute_candidate",
        ]
        n = insert_versioned(
            conn, "layer0.discipline_training_gaps",
            dtg_columns,
            [tuple(r[k] for k in dtg_columns) for r in dtg_rows],
            v_0a, run_at, source_family="0A",
        )
        _print(f"layer0.discipline_training_gaps: inserted {n} rows")
        summaries.append(f"layer0.discipline_training_gaps: {n}")

        # ----- Phase 3 — Bridge + 0B -----
        _print("[layer0 ETL] Phase 3 — Bridge + Exercise DB")
        bridge_rows = sports_framework.build_sport_discipline_bridge(sd_rows)
        n = insert_versioned(
            conn, "layer0.sport_discipline_bridge",
            [
                "framework_sport", "discipline_id", "discipline_name", "exercise_db_sport",
                "role", "default_race_time_pct_low", "default_race_time_pct_high",
            ],
            [tuple(r[k] for k in [
                "framework_sport", "discipline_id", "discipline_name", "exercise_db_sport",
                "role", "default_race_time_pct_low", "default_race_time_pct_high",
            ]) for r in bridge_rows],
            v_0a, run_at, source_family="0A",
        )
        _print(f"layer0.sport_discipline_bridge: inserted {n} rows")
        summaries.append(f"layer0.sport_discipline_bridge: {n}")

        wb_ex = exercise_db.open_workbook(EXERCISES_XLSX)
        ex_rows = exercise_db.extract_exercises(wb_ex["Exercise Master"])
        n = insert_versioned(
            conn, "layer0.exercises",
            [
                "exercise_id", "exercise_name", "exercise_type",
                "movement_patterns", "primary_muscles", "secondary_muscles",
                "equipment_required", "injury_flags_text", "contraindicated_parts",
                "contraindicated_conditions",
                "equipment_substitutes", "physical_proxies",
                "progression_exercise_id", "progression_exercise_name",
                "regression_exercise_id", "regression_exercise_name",
                "sport_count", "coaching_cues",
            ],
            [(
                r["exercise_id"], r["exercise_name"], r["exercise_type"],
                r["movement_patterns"], r["primary_muscles"], r["secondary_muscles"],
                r["equipment_required"], r["injury_flags_text"], r["contraindicated_parts"],
                r["contraindicated_conditions"],
                to_jsonb(r["equipment_substitutes"]), to_jsonb(r["physical_proxies"]),
                r["progression_exercise_id"], r["progression_exercise_name"],
                r["regression_exercise_id"], r["regression_exercise_name"],
                r["sport_count"], r["coaching_cues"],
            ) for r in ex_rows],
            v_0b, run_at, source_family="0B",
        )
        _print(f"layer0.exercises: inserted {n} rows")
        summaries.append(f"layer0.exercises: {n}")

        dropped_sxm_dupes: list = []
        sxm_rows = exercise_db.extract_sport_exercise_map(
            wb_ex["Sport-Exercise Map"], dropped_dupes=dropped_sxm_dupes,
        )
        if dropped_sxm_dupes:
            _print(
                f"  [warn] sport_exercise_map: dropped {len(dropped_sxm_dupes)} duplicate "
                f"(exercise_id, sport_name) rows — see report"
            )
        n = insert_versioned(
            conn, "layer0.sport_exercise_map",
            [
                "exercise_id", "exercise_name", "exercise_type",
                "sport_name", "sport_relevance_note", "priority",
            ],
            [tuple(r[k] for k in [
                "exercise_id", "exercise_name", "exercise_type",
                "sport_name", "sport_relevance_note", "priority",
            ]) for r in sxm_rows],
            v_0b, run_at, source_family="0B",
        )
        _print(f"layer0.sport_exercise_map: inserted {n} rows")
        summaries.append(f"layer0.sport_exercise_map: {n}")

        # ----- Phase 5 — Validation -----
        _print("[layer0 ETL] Validation")
        sum_to_100_result = run_sum_to_100(conn)
        _print(
            f"sum_to_100: {sum_to_100_result['sports_checked']} sports checked, "
            f"{sum_to_100_result['pass_count']} PASS, {sum_to_100_result['warn_count']} WARN"
        )
        vocab_result = run_vocab_alignment(conn)
        _print(
            f"vocab_alignment: {vocab_result['exercises_checked']} exercises checked, "
            f"{vocab_result['pass_count']} PASS, {vocab_result['warn_count']} WARN; "
            f"{vocab_result['sport_names_checked']} sport names checked, "
            f"{vocab_result['sport_pass']} PASS, {vocab_result['sport_warn']} WARN"
        )

        # v10 — new validators
        sub_fk_result = run_substitution_fks(conn)
        _print(
            f"substitution_fks: {sub_fk_result['rows_checked']} substitute rows, "
            f"{sub_fk_result['pass_count']} PASS, {sub_fk_result['error_count']} ERROR"
        )
        gap_fk_result = run_training_gap_fks(conn)
        _print(
            f"training_gap_fks: {gap_fk_result['rows_checked']} gap rows, "
            f"{gap_fk_result['pass_count']} PASS, {gap_fk_result['error_count']} ERROR"
        )
        contra_result = run_contraindicated_conditions(conn)
        _print(
            f"contraindicated_conditions: {contra_result['exercises_checked']} exercises, "
            f"{contra_result['pass_count']} PASS, {contra_result['warn_count']} WARN"
        )
        di_result = run_default_inclusion(conn)
        _print(
            f"default_inclusion: {di_result['rows_checked']} rows, "
            f"{di_result['pass_count']} PASS, {di_result['error_count']} ERROR"
        )

        report_path = build_report(
            tag, run_at, summaries, sum_to_100_result, vocab_result,
            extras={
                "dropped_sd_dupes": dropped_sd_dupes,
                "dropped_sxm_dupes": dropped_sxm_dupes,
                "movement_warnings": movement_warnings,
                "matrix_meta": matrix_meta,
                "pl_split_stats": pl_split_stats,
                "weekly_failures": weekly_failures,
                "substitute_warnings": substitute_warnings,
                "substitution_fks": sub_fk_result,
                "training_gap_fks": gap_fk_result,
                "contraindicated_conditions": contra_result,
                "default_inclusion": di_result,
            },
        )
        _print(f"[layer0 ETL] Report written to {report_path}")

    _print("[layer0 ETL] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
