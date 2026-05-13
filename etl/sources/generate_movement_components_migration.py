#!/usr/bin/env python3
"""
Generate migrate_exercises_add_movement_components_v1.sql from
D22_Curation_Reference_v2.md.

Source of truth: the row tables in Pass 1 + Pass 2 baseline sections
of D22_Curation_Reference_v2.md. If a value needs to change, edit the
curation reference and re-run this script.

Output: etl/sources/migrate_exercises_add_movement_components_v1.sql

House style follows update_retype_keeper_exercises.sql v2:
  - Pre-flight introspection block (column absence, row count, baseline ID match)
  - ALTER TABLE ADD COLUMN IF NOT EXISTS
  - 159 idempotent UPDATE statements grouped by curation section
  - CREATE INDEX IF NOT EXISTS (GIN on movement_components)
  - Validation block (non-blocking; reports violations)
"""

import re
import sys
from pathlib import Path

CURATION_REF = Path("/mnt/project/D22_Curation_Reference_v2.md")
OUTPUT_SQL = Path("/mnt/user-data/outputs/migrate_exercises_add_movement_components_v1.sql")

# Abbreviation -> canonical token (per handoff §4)
TOKEN_MAP = {
    "Load":     "Pain with loading",
    "Impact":   "Pain with impact",
    "Angle":    "Pain above specific joint angle",
    "Ecc":      "Pain on descent / eccentric",
    "Rot":      "Pain on rotation",
    "Grip":     "Pain with grip / sustained hold",
    "WristExt": "Pain with wrist extension",
    "Overhead": "Pain with overhead movement",
    "Instab":   "Instability",
    "ROM":      "Reduced ROM",
    "Vol":      "Pain at high volume only",
}

# Row regex: | sample_idx | EXnnn | name | {tokens} |
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*(EX\d+)\s*\|\s*(.+?)\s*\|\s*\{([^}]*)\}\s*\|\s*$")
# Section header regex: ### Strength (17)
SECTION_RE = re.compile(r"^###\s+(.+?)\s+\(\d+\)\s*$")
# Pass header: ## Pass 1 baseline / ## Pass 2 baseline
PASS_RE = re.compile(r"^##\s+(Pass\s+[12])\s+baseline")


def parse_curation_reference(path: Path):
    """Walk the markdown and yield (sample_idx, exercise_id, exercise_name,
    components_list, pass_label, section_label) tuples in source order."""
    rows = []
    current_pass = None
    current_section = None

    with path.open() as f:
        for line in f:
            line = line.rstrip("\n")

            m_pass = PASS_RE.match(line)
            if m_pass:
                current_pass = m_pass.group(1)
                current_section = None
                continue

            m_sec = SECTION_RE.match(line)
            # Only treat as section header if we're inside a Pass baseline block
            if m_sec and current_pass is not None:
                current_section = m_sec.group(1)
                continue

            m_row = ROW_RE.match(line)
            if m_row and current_pass is not None:
                sample_idx = int(m_row.group(1))
                exercise_id = m_row.group(2)
                exercise_name = m_row.group(3)
                tokens_raw = m_row.group(4).strip()
                if tokens_raw == "":
                    abbrevs = []
                else:
                    abbrevs = [t.strip() for t in tokens_raw.split(",") if t.strip()]

                # Validate every abbreviation maps to a canonical token
                unknown = [a for a in abbrevs if a not in TOKEN_MAP]
                if unknown:
                    raise ValueError(
                        f"Unknown abbreviation(s) in {exercise_id}: {unknown} "
                        f"(line: {line!r})"
                    )

                canonical = [TOKEN_MAP[a] for a in abbrevs]
                rows.append({
                    "sample_idx": sample_idx,
                    "exercise_id": exercise_id,
                    "exercise_name": exercise_name,
                    "abbrevs": abbrevs,
                    "canonical": canonical,
                    "pass": current_pass,
                    "section": current_section,
                })

    return rows


def sql_array_literal(canonical_tokens):
    """Emit ARRAY[...]::TEXT[] with proper quoting. Empty -> ARRAY[]::TEXT[]."""
    if not canonical_tokens:
        return "ARRAY[]::TEXT[]"
    quoted = [f"'{t.replace(chr(39), chr(39)*2)}'" for t in canonical_tokens]
    return "ARRAY[" + ", ".join(quoted) + "]::TEXT[]"


def emit_sql(rows):
    """Produce the full migration SQL as a string. Follows house style from
    migrate_exercises_substitutes_structured.sql: BEGIN / schema / DO $$ verify
    / COMMIT, atomic rollback on validation failure via RAISE EXCEPTION."""
    n = len(rows)
    pass1 = [r for r in rows if r["pass"] == "Pass 1"]
    pass2 = [r for r in rows if r["pass"] == "Pass 2"]
    ids_sorted = sorted(rows, key=lambda r: r["sample_idx"])
    canonical_tokens_ordered = list(TOKEN_MAP.values())

    out = []
    out.append("-- migrate_exercises_add_movement_components_v1.sql")
    out.append("--")
    out.append("-- Promote `layer0.exercises.injury_flags_text` (free text) to a structured")
    out.append("-- `movement_components TEXT[]` column. Enables mathematically exact set-")
    out.append("-- intersect against the Athlete_Onboarding_Data_Spec §B.3 11-token enum,")
    out.append("-- replacing the heuristic keyword-match path in Layer 2D.")
    out.append("--")
    out.append("-- Population: 159 active exercise rows (superseded_at IS NULL).")
    out.append(f"-- Baseline: {len(pass1)} Pass 1 + {len(pass2)} Pass 2 = {n} rows.")
    out.append("-- Source of truth: D22_Curation_Reference_v2.md row tables.")
    out.append("-- Generator: etl/sources/generate_movement_components_migration.py")
    out.append("--")
    out.append("-- Idempotent: ALTER TABLE / CREATE INDEX use IF NOT EXISTS; UPDATEs are")
    out.append("-- naturally idempotent (hardcoded values keyed on exercise_id with")
    out.append("-- superseded_at IS NULL filter).")
    out.append("--")
    out.append("-- Atomic: the DO $$ verification block at the end RAISEs EXCEPTION on")
    out.append("-- any violation, which rolls back the entire transaction (ALTER, UPDATEs,")
    out.append("-- INDEX). Safe to re-run.")
    out.append("--")
    out.append("-- Resolves: Project_Backlog D-22 (FC-1b).")
    out.append("")
    out.append("BEGIN;")
    out.append("")

    # --- 1. Schema migration ---
    out.append("-- ── 1. Schema migration ────────────────────────────────────────────────────")
    out.append("")
    out.append("ALTER TABLE layer0.exercises")
    out.append("  ADD COLUMN IF NOT EXISTS movement_components TEXT[];")
    out.append("")
    out.append("COMMENT ON COLUMN layer0.exercises.movement_components IS")
    out.append("  'Canonical movement-constraint tokens (subset of Onboarding §B.3 "
               "11-token enum). Populated by "
               "migrate_exercises_add_movement_components_v1.sql from "
               "D22_Curation_Reference_v2.md. Curated 2026-05-11 (Pass 1) / "
               "2026-05-12 (Pass 2).';")
    out.append("")

    # --- 2. Populate (159 UPDATE statements grouped by pass + section) ---
    out.append("-- ── 2. Populate — 159 UPDATE statements grouped by curation section ───────")
    out.append("")

    current_key = None
    for r in ids_sorted:
        key = (r["pass"], r["section"])
        if key != current_key:
            if current_key is not None:
                out.append("")
            out.append(f"-- {r['pass']} — {r['section']}")
            current_key = key

        sql_arr = sql_array_literal(r["canonical"])
        if len(sql_arr) <= 90:
            out.append(
                f"UPDATE layer0.exercises SET movement_components = {sql_arr} "
                f"WHERE exercise_id = '{r['exercise_id']}' AND superseded_at IS NULL;"
            )
        else:
            out.append(f"UPDATE layer0.exercises")
            out.append(f"   SET movement_components = {sql_arr}")
            out.append(f" WHERE exercise_id = '{r['exercise_id']}' AND superseded_at IS NULL;")
    out.append("")

    # --- 3. Index ---
    out.append("-- ── 3. Index — GIN on movement_components for set-intersect performance ───")
    out.append("")
    out.append("CREATE INDEX IF NOT EXISTS idx_exercises_movement_components")
    out.append("  ON layer0.exercises USING GIN (movement_components);")
    out.append("")

    # --- 4. Verify (atomic; aborts transaction on any failure) ---
    out.append("-- ── 4. Verify — RAISE EXCEPTION aborts the transaction on any violation ───")
    out.append("")
    out.append("DO $$")
    out.append("DECLARE")
    out.append("  v_active_rows   INTEGER;")
    out.append("  v_null_rows     INTEGER;")
    out.append("  v_dup_rows      INTEGER;")
    out.append("  v_bad_tokens    TEXT;")
    out.append("  v_missing_base  INTEGER;")
    out.append("  v_off_baseline  INTEGER;")
    out.append("  v_canonical     TEXT[] := ARRAY[")
    can_lines = [f"    '{t}'" for t in canonical_tokens_ordered]
    out.append(",\n".join(can_lines))
    out.append("  ]::TEXT[];")
    out.append("  v_baseline      TEXT[] := ARRAY[")
    base_lines = [f"    '{r['exercise_id']}'" for r in ids_sorted]
    out.append(",\n".join(base_lines))
    out.append("  ]::TEXT[];")
    out.append("BEGIN")
    out.append("  -- 4a: active row count should be exactly 159")
    out.append("  SELECT COUNT(*) INTO v_active_rows")
    out.append("    FROM layer0.exercises WHERE superseded_at IS NULL;")
    out.append(f"  IF v_active_rows <> {n} THEN")
    out.append("    RAISE EXCEPTION 'migrate_exercises_add_movement_components: expected % active rows, found %',")
    out.append(f"      {n}, v_active_rows;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4b: every baseline exercise_id must exist as an active row")
    out.append("  SELECT COUNT(*) INTO v_missing_base")
    out.append("    FROM unnest(v_baseline) AS b(exercise_id)")
    out.append("    WHERE NOT EXISTS (")
    out.append("      SELECT 1 FROM layer0.exercises e")
    out.append("      WHERE e.exercise_id = b.exercise_id AND e.superseded_at IS NULL");
    out.append("    );")
    out.append("  IF v_missing_base > 0 THEN")
    out.append("    RAISE EXCEPTION 'migrate_exercises_add_movement_components: % baseline exercise_id(s) not present as active rows',")
    out.append("      v_missing_base;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4c: no active row may have NULL movement_components")
    out.append("  SELECT COUNT(*) INTO v_null_rows")
    out.append("    FROM layer0.exercises")
    out.append("    WHERE superseded_at IS NULL AND movement_components IS NULL;")
    out.append("  IF v_null_rows > 0 THEN")
    out.append("    RAISE EXCEPTION 'migrate_exercises_add_movement_components: % active row(s) with NULL movement_components',")
    out.append("      v_null_rows;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4d: every token must be in the canonical 11-token set")
    out.append("  SELECT string_agg(DISTINCT t.token, ', ') INTO v_bad_tokens")
    out.append("    FROM layer0.exercises e,")
    out.append("         unnest(e.movement_components) AS t(token)")
    out.append("    WHERE e.superseded_at IS NULL")
    out.append("      AND NOT (t.token = ANY (v_canonical));")
    out.append("  IF v_bad_tokens IS NOT NULL THEN")
    out.append("    RAISE EXCEPTION 'migrate_exercises_add_movement_components: non-canonical token(s) found: %',")
    out.append("      v_bad_tokens;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4e: no duplicate tokens within a single row's array")
    out.append("  -- (COALESCE on array_length: empty array → 0, not NULL, so check passes for EX018)")
    out.append("  SELECT COUNT(*) INTO v_dup_rows")
    out.append("    FROM layer0.exercises")
    out.append("    WHERE superseded_at IS NULL")
    out.append("      AND movement_components IS NOT NULL")
    out.append("      AND COALESCE(array_length(movement_components, 1), 0) IS DISTINCT FROM")
    out.append("          (SELECT COUNT(DISTINCT t)::INT FROM unnest(movement_components) AS t);")
    out.append("  IF v_dup_rows > 0 THEN")
    out.append("    RAISE EXCEPTION 'migrate_exercises_add_movement_components: % row(s) with duplicate tokens',")
    out.append("      v_dup_rows;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4f: no active row outside the curated baseline")
    out.append("  -- (catches: active row added since curation that we missed)")
    out.append("  SELECT COUNT(*) INTO v_off_baseline")
    out.append("    FROM layer0.exercises e")
    out.append("    WHERE e.superseded_at IS NULL")
    out.append("      AND NOT (e.exercise_id = ANY (v_baseline));")
    out.append("  IF v_off_baseline > 0 THEN")
    out.append("    RAISE EXCEPTION 'migrate_exercises_add_movement_components: % active exercise(s) outside the 159-row baseline',")
    out.append("      v_off_baseline;")
    out.append("  END IF;")
    out.append("")
    out.append(f"  RAISE NOTICE 'migrate_exercises_add_movement_components: OK — {n} rows populated, % canonical tokens, GIN index in place',")
    out.append("    array_length(v_canonical, 1);")
    out.append("END $$;")
    out.append("")

    out.append("COMMIT;")
    out.append("")
    out.append("-- End of migrate_exercises_add_movement_components_v1.sql")

    return "\n".join(out)


def main():
    rows = parse_curation_reference(CURATION_REF)

    # Sanity checks
    assert len(rows) == 159, f"Expected 159 rows, got {len(rows)}"

    sample_indices = [r["sample_idx"] for r in rows]
    assert sorted(sample_indices) == list(range(1, 160)), \
        "sample_idx should cover 1..159 with no gaps"

    pass1_count = sum(1 for r in rows if r["pass"] == "Pass 1")
    pass2_count = sum(1 for r in rows if r["pass"] == "Pass 2")
    assert pass1_count == 57, f"Expected 57 Pass 1 rows, got {pass1_count}"
    assert pass2_count == 102, f"Expected 102 Pass 2 rows, got {pass2_count}"

    # EX024 spot-check (the retroactive correction)
    ex024 = next(r for r in rows if r["exercise_id"] == "EX024")
    assert ex024["abbrevs"] == ["Angle", "Load", "Impact"], \
        f"EX024 should be {{Angle, Load, Impact}}, got {ex024['abbrevs']}"

    # Every exercise_id unique
    ids = [r["exercise_id"] for r in rows]
    assert len(set(ids)) == len(ids), "Duplicate exercise_id detected"

    # Empty-array row check
    empty_rows = [r for r in rows if not r["canonical"]]
    assert len(empty_rows) == 1 and empty_rows[0]["exercise_id"] == "EX018", \
        f"Expected exactly one empty row (EX018), got {[r['exercise_id'] for r in empty_rows]}"

    # Token coverage: all 11 canonical tokens must appear
    all_tokens_used = set()
    for r in rows:
        all_tokens_used.update(r["abbrevs"])
    missing = set(TOKEN_MAP.keys()) - all_tokens_used
    assert not missing, f"Canonical tokens never used in baseline: {missing}"

    sql = emit_sql(rows)
    OUTPUT_SQL.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SQL.write_text(sql)

    print(f"Wrote: {OUTPUT_SQL}")
    print(f"  Rows parsed: {len(rows)} ({pass1_count} Pass 1 + {pass2_count} Pass 2)")
    print(f"  sample_idx coverage: 1..{max(sample_indices)} (no gaps)")
    print(f"  EX024 confirmed: {ex024['abbrevs']}")
    print(f"  Empty-array rows: 1 (EX018)")
    print(f"  All 11 canonical tokens used in baseline: True")
    print(f"  SQL size: {len(sql):,} chars, {sql.count(chr(10))+1} lines")


if __name__ == "__main__":
    main()
