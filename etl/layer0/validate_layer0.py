"""validate_layer0 — standalone DB-side integrity gate for Layer 0.

Ports the ETL's validation pass (`etl/layer0/validation/*`) into a standalone
gate that runs against the live `layer0.*` tables and exits non-zero on any
integrity violation not covered by an explicit waiver. Pre-migration these
checks ran only as a side effect of re-running the full ETL; once the DB is the
authoring source of truth (`Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md`)
this is the integrity backstop that gates every DB-native edit.

Disposition — decision C (design spec §5.2, Andy 2026-06-10): **every check is
FAIL.** The only escape hatch is the waiver registry (`layer0_validation_waivers
.json`), reserved by policy for `sum_to_100` (intentionally sub-100 sports).
`vocab_alignment` and `contraindicated_conditions` are FAIL-and-fix-the-data,
not waive — that policy is enforced by PR review of the registry, not in code.

Usage:
    python -m etl.layer0.validate_layer0           # reads DATABASE_URL
    python -m etl.layer0.validate_layer0 --json     # machine-readable summary

Exit code: 0 = clean (or fully waived); 1 = unwaived violations.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from etl.layer0.validation.contraindicated_conditions import (
    run_contraindicated_conditions,
)
from etl.layer0.validation.default_inclusion import run_default_inclusion
from etl.layer0.validation.discipline_canon_check import (
    run_discipline_canon_conformance,
)
from etl.layer0.validation.fk_checks import (
    run_substitution_fks,
    run_training_gap_fks,
)
from etl.layer0.validation.modality_group_orphan import run_modality_group_orphan
from etl.layer0.validation.primary_movement_check import run_primary_movement
from etl.layer0.validation.terrain_types_check import run_terrain_types
from etl.layer0.validation.sum_to_100 import run_sum_to_100
from etl.layer0.validation.vocab_alignment import run_vocab_alignment

WAIVERS_PATH = Path(__file__).parent / "layer0_validation_waivers.json"


@dataclass(frozen=True)
class Violation:
    """One failing item from a check. `id` is the stable key a waiver matches
    on; `detail` is human-readable context for the report."""

    id: str
    detail: str


# --- Per-check violation extractors. Each maps a validator's result dict to a
# --- flat list of Violations. Result-dict shapes are the validators' own
# --- contracts (etl/layer0/validation/*).

def _v_substitution_fks(r: dict) -> list[Violation]:
    return [
        Violation(f"{e['target_id']}->{e['substitute_id']}",
                  f"dangling FK on {', '.join(e['broken'])}")
        for e in r["errors"]
    ]


def _v_training_gap_fks(r: dict) -> list[Violation]:
    return [
        Violation(e["discipline_id"],
                  f"{e['discipline_name']} (gap_type={e['gap_type']}) has no discipline row")
        for e in r["errors"]
    ]


def _v_discipline_canon(r: dict) -> list[Violation]:
    return [
        Violation(f"{e['table']}.{e['column']}:{e['discipline_id']}", e["problem"])
        for e in r["errors"]
    ]


def _v_modality_group_orphan(r: dict) -> list[Violation]:
    return [Violation(d, "no modality-group membership") for d in r["orphans"]]


def _v_primary_movement(r: dict) -> list[Violation]:
    return [
        Violation(e["discipline_id"],
                  f"{e['discipline_name']}: {e['problem']} ({e['primary_movement']!r})")
        for e in r["errors"]
    ]


def _v_terrain_types(r: dict) -> list[Violation]:
    out: list[Violation] = []
    out += [Violation(f"terrain_id:{t}", "malformed terrain_id (expected TRN-NNN)")
            for t in r["malformed_ids"]]
    out += [Violation(f"dup_terrain_id:{t}", "duplicate terrain_id in active set")
            for t in r["duplicate_ids"]]
    out += [Violation(f"dup_name:{n}", "duplicate canonical_name in active set")
            for n in r["duplicate_names"]]
    return out


def _v_sum_to_100(r: dict) -> list[Violation]:
    out: list[Violation] = []
    for sr in r["sport_results"]:
        bad = [p for p, s in sr["phase_status"].items() if s == "WARN"]
        if bad:
            out.append(Violation(sr["sport"], f"below threshold in phase(s): {', '.join(bad)}"))
    return out


def _v_vocab_alignment(r: dict) -> list[Violation]:
    out = [
        Violation(f"exercise:{w['exercise_id']}",
                  f"unknown contraindicated body part(s): {w['unknown_parts']}")
        for w in r["exercise_warnings"]
    ]
    out += [
        Violation(f"sport:{w['sport_name']}",
                  f"sport name absent from sport_discipline_bridge ({w['exercise_count']} exercises)")
        for w in r["sport_warnings"]
    ]
    return out


def _v_contraindicated(r: dict) -> list[Violation]:
    return [
        Violation(f"exercise:{w['exercise_id']}",
                  f"unknown condition(s): {w['unknown_conditions']}")
        for w in r["warnings"]
    ]


def _v_default_inclusion(r: dict) -> list[Violation]:
    return [
        Violation(f"{e['sport_name']}/{e['discipline_id']}",
                  f"invalid value {e['default_inclusion']!r}")
        for e in r["errors"]
    ]


@dataclass(frozen=True)
class Check:
    name: str
    runner: Callable[[Any], dict]
    extract: Callable[[dict], list[Violation]]


# Registry order = report order. fk_checks splits into two runners; the rest
# are 1:1 with their logical checks (the spec §5.2 seven, plus terrain_types and
# primary_movement added with the DB-source-of-truth model).
CHECKS: tuple[Check, ...] = (
    Check("substitution_fks", run_substitution_fks, _v_substitution_fks),
    Check("training_gap_fks", run_training_gap_fks, _v_training_gap_fks),
    Check("discipline_canon", run_discipline_canon_conformance, _v_discipline_canon),
    Check("primary_movement", run_primary_movement, _v_primary_movement),
    Check("modality_group_orphan", run_modality_group_orphan, _v_modality_group_orphan),
    Check("terrain_types", run_terrain_types, _v_terrain_types),
    Check("sum_to_100", run_sum_to_100, _v_sum_to_100),
    Check("vocab_alignment", run_vocab_alignment, _v_vocab_alignment),
    Check("contraindicated_conditions", run_contraindicated_conditions, _v_contraindicated),
    Check("default_inclusion", run_default_inclusion, _v_default_inclusion),
)


@dataclass
class CheckOutcome:
    name: str
    violations: list[Violation]
    waived: list[str]  # ids that matched an active waiver

    @property
    def unwaived(self) -> list[Violation]:
        waived = set(self.waived)
        return [v for v in self.violations if v.id not in waived]

    @property
    def failed(self) -> bool:
        return bool(self.unwaived)


def load_waivers(path: Path = WAIVERS_PATH) -> dict[str, set[str]]:
    """Read the waiver registry → {check_name: {waived_id, ...}}. Missing file
    means no waivers (the gate fails on every violation)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for entry in data.get("waivers", []):
        out.setdefault(entry["check"], set()).add(entry["id"])
    return out


def collect(conn) -> dict[str, dict]:
    """Run every check's validator against the DB. The only DB-touching step."""
    return {check.name: check.runner(conn) for check in CHECKS}


def evaluate(results: dict[str, dict], waivers: dict[str, set[str]]) -> list[CheckOutcome]:
    """Pure: turn raw validator results + waivers into per-check outcomes."""
    outcomes: list[CheckOutcome] = []
    for check in CHECKS:
        violations = check.extract(results[check.name])
        waived_ids = waivers.get(check.name, set())
        matched = [v.id for v in violations if v.id in waived_ids]
        outcomes.append(CheckOutcome(check.name, violations, matched))
    return outcomes


def gate_failed(outcomes: list[CheckOutcome]) -> bool:
    return any(o.failed for o in outcomes)


def format_report(outcomes: list[CheckOutcome], *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(
            {
                "gate": "fail" if gate_failed(outcomes) else "pass",
                "checks": [
                    {
                        "name": o.name,
                        "violations": len(o.violations),
                        "waived": len(o.waived),
                        "unwaived": len(o.unwaived),
                        "failing_ids": [v.id for v in o.unwaived],
                    }
                    for o in outcomes
                ],
            },
            indent=2,
        )
    lines = ["Layer 0 integrity gate (validate_layer0)", ""]
    for o in outcomes:
        mark = "FAIL" if o.failed else ("PASS (waived)" if o.waived else "PASS")
        lines.append(
            f"[{mark}] {o.name}: {len(o.violations)} violation(s), "
            f"{len(o.waived)} waived, {len(o.unwaived)} unwaived"
        )
        for v in o.unwaived:
            lines.append(f"    - {v.id}: {v.detail}")
    lines.append("")
    lines.append(
        "RESULT: " + (
            "FAIL — unwaived integrity violations above"
            if gate_failed(outcomes)
            else "PASS — all checks clean (or waived)"
        )
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Layer 0 DB integrity gate.")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    # Imported lazily so the pure logic above (and its unit tests) don't pull in
    # psycopg2 / a live connection.
    from etl.layer0 import db

    waivers = load_waivers()
    with db.connect() as conn:
        results = collect(conn)
    outcomes = evaluate(results, waivers)
    print(format_report(outcomes, as_json=args.json), flush=True)
    return 1 if gate_failed(outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
