#!/usr/bin/env python3
"""
Generate migrate_disciplines_add_body_parts_at_risk_v1.sql from
D23_Curation_Reference_v1.md.

Source of truth: the row tables in `D23_Curation_Reference_v1.md`. If a
value needs to change, edit the curation reference and re-run this script.

Output: etl/sources/migrate_disciplines_add_body_parts_at_risk_v1.sql

House style follows migrate_exercises_add_movement_components_v1.sql:
  - BEGIN/COMMIT atomic transaction
  - ALTER TABLE ADD COLUMN IF NOT EXISTS
  - 31 idempotent UPDATE statements grouped by sport family
  - CREATE INDEX IF NOT EXISTS (GIN on body_parts_at_risk)
  - DO $$ verification block with RAISE EXCEPTION on violation
"""

import re
from pathlib import Path

CURATION_REF = Path("/mnt/project/D23_Curation_Reference_v1.md")
# Fallback to outputs dir if project copy not present
if not CURATION_REF.exists():
    CURATION_REF = Path("/mnt/user-data/outputs/D23_Curation_Reference_v1.md")

OUTPUT_SQL = Path("/mnt/user-data/outputs/migrate_disciplines_add_body_parts_at_risk_v1.sql")

# Canonical 51 body parts (Vocabulary_Audit_v2 Section 1 + Collarbone amendment 2026-05-12)
CANONICAL_BODY_PARTS = [
    # Head / Neck
    "Neck", "Jaw", "Trapezius",
    # Shoulder
    "Shoulder", "Rotator cuff", "AC joint", "Shoulder blade", "Collarbone",
    # Arm
    "Elbow", "Forearm", "Wrist", "Hand", "Bicep", "Tricep",
    "Fingers", "Thumb", "Finger pulley", "DIP joint", "CMC joint",
    # Back
    "Upper back", "Lower back", "Spine (general)", "SI joint", "Sciatica",
    # Hip
    "Hip", "Groin", "Hip flexor", "Glute", "Hip crest (iliac crest)", "TFL",
    # Upper leg
    "Quad", "Hamstring", "IT band",
    # Knee
    "Knee", "Kneecap", "Meniscus", "ACL", "PCL", "MCL", "LCL",
    # Lower leg
    "Calf", "Soleus", "Shin", "Achilles", "Peroneal",
    # Foot / Ankle
    "Ankle", "Plantar fascia", "Foot", "Toes",
    # Trunk
    "Rib", "Chest",
]
CANONICAL_SET = set(CANONICAL_BODY_PARTS)

# Row regex inside the "Locked mappings" tables:
# | D-XXX | Discipline Name | {Part1, Part2, ...} |
ROW_RE = re.compile(r"^\|\s*(D-\d+\w?)\s*\|\s*([^|]+?)\s*\|\s*\{([^}]*)\}\s*\|\s*$")
SECTION_RE = re.compile(r"^###\s+(.+?)\s*$")
LOCKED_MAPPINGS_RE = re.compile(r"^## Locked mappings")


def parse_curation_reference(path: Path):
    """Walk the markdown's Locked Mappings section and yield row dicts in source
    order. Tracks the current section header for SQL grouping comments."""
    rows = []
    in_locked = False
    current_section = None

    with path.open() as f:
        for line in f:
            line = line.rstrip("\n")

            if LOCKED_MAPPINGS_RE.match(line):
                in_locked = True
                continue
            if not in_locked:
                continue

            # Stop when we hit a top-level section after Locked Mappings
            if line.startswith("## ") and not LOCKED_MAPPINGS_RE.match(line):
                in_locked = False
                continue

            m_sec = SECTION_RE.match(line)
            if m_sec:
                current_section = m_sec.group(1).strip()
                continue

            m_row = ROW_RE.match(line)
            if m_row and current_section:
                disc_id = m_row.group(1)
                disc_name = m_row.group(2).strip()
                parts_raw = m_row.group(3).strip()
                if parts_raw == "":
                    parts = []
                else:
                    parts = [p.strip() for p in parts_raw.split(",") if p.strip()]

                unknown = [p for p in parts if p not in CANONICAL_SET]
                if unknown:
                    raise ValueError(
                        f"Non-canonical body part(s) in {disc_id}: {unknown}"
                    )

                rows.append({
                    "disc_id": disc_id,
                    "disc_name": disc_name,
                    "parts": parts,
                    "section": current_section,
                })

    return rows


def sql_array_literal(parts):
    """ARRAY[...]::TEXT[] with proper quoting. Empty -> ARRAY[]::TEXT[]."""
    if not parts:
        return "ARRAY[]::TEXT[]"
    quoted = [f"'{p.replace(chr(39), chr(39)*2)}'" for p in parts]
    return "ARRAY[" + ", ".join(quoted) + "]::TEXT[]"


def emit_sql(rows):
    n = len(rows)
    out = []
    out.append("-- migrate_disciplines_add_body_parts_at_risk_v1.sql")
    out.append("--")
    out.append("-- Promote `layer0.disciplines.common_injury_patterns` (free text) to a")
    out.append("-- structured `body_parts_at_risk TEXT[]` column. Enables direct set-")
    out.append("-- intersect against athlete `Injury Record.body_part` (canonical 51-token")
    out.append("-- vocabulary from Vocabulary_Audit_v2 + Collarbone amendment), replacing")
    out.append("-- the heuristic BODY_PART_KEYWORDS map currently in Layer 2D §5.5.")
    out.append("--")
    out.append(f"-- Population: {n} active discipline rows.")
    out.append("-- Source of truth: D23_Curation_Reference_v1.md row tables.")
    out.append("-- Generator: etl/sources/generate_body_parts_at_risk_migration.py")
    out.append("--")
    out.append("-- Vocabulary: 51 canonical body parts (Vocabulary_Audit_v2 Section 1's 50")
    out.append("-- + Collarbone added 2026-05-12 per D-23 curation review).")
    out.append("--")
    out.append("-- Idempotent: ALTER TABLE / CREATE INDEX use IF NOT EXISTS; UPDATEs are")
    out.append("-- naturally idempotent (hardcoded values keyed on discipline_id).")
    out.append("--")
    out.append("-- Atomic: the DO $$ verification block at the end RAISEs EXCEPTION on")
    out.append("-- any violation, which rolls back the entire transaction.")
    out.append("--")
    out.append("-- Resolves: Project_Backlog D-23 (FC-1b).")
    out.append("")
    out.append("BEGIN;")
    out.append("")

    # --- 1. Schema migration ---
    out.append("-- ── 1. Schema migration ────────────────────────────────────────────────────")
    out.append("")
    out.append("ALTER TABLE layer0.disciplines")
    out.append("  ADD COLUMN IF NOT EXISTS body_parts_at_risk TEXT[];")
    out.append("")
    out.append("COMMENT ON COLUMN layer0.disciplines.body_parts_at_risk IS")
    out.append("  'Canonical body parts at risk per discipline (subset of Vocabulary_Audit "
               "Section 1 + Collarbone). Populated by "
               "migrate_disciplines_add_body_parts_at_risk_v1.sql from "
               "D23_Curation_Reference_v1.md. Curated 2026-05-12.';")
    out.append("")

    # --- 2. Populate ---
    out.append(f"-- ── 2. Populate — {n} UPDATE statements grouped by sport family ──────────")
    out.append("")

    current_section = None
    for r in rows:
        if r["section"] != current_section:
            if current_section is not None:
                out.append("")
            out.append(f"-- {r['section']}")
            current_section = r["section"]

        sql_arr = sql_array_literal(r["parts"])
        line = (
            f"UPDATE layer0.disciplines SET body_parts_at_risk = {sql_arr} "
            f"WHERE discipline_id = '{r['disc_id']}';"
        )
        if len(line) <= 110:
            out.append(line)
        else:
            out.append(f"UPDATE layer0.disciplines")
            out.append(f"   SET body_parts_at_risk = {sql_arr}")
            out.append(f" WHERE discipline_id = '{r['disc_id']}';")
    out.append("")

    # --- 3. Index ---
    out.append("-- ── 3. Index — GIN on body_parts_at_risk for set-intersect performance ────")
    out.append("")
    out.append("CREATE INDEX IF NOT EXISTS idx_disciplines_body_parts_at_risk")
    out.append("  ON layer0.disciplines USING GIN (body_parts_at_risk);")
    out.append("")

    # --- 4. Verify ---
    out.append("-- ── 4. Verify — RAISE EXCEPTION aborts the transaction on any violation ───")
    out.append("")
    out.append("DO $$")
    out.append("DECLARE")
    out.append("  v_total_rows    INTEGER;")
    out.append("  v_null_rows     INTEGER;")
    out.append("  v_dup_rows      INTEGER;")
    out.append("  v_bad_parts     TEXT;")
    out.append("  v_missing_base  INTEGER;")
    out.append("  v_off_baseline  INTEGER;")
    out.append("  v_canonical     TEXT[] := ARRAY[")
    out.append(",\n".join([f"    '{p}'" for p in CANONICAL_BODY_PARTS]))
    out.append("  ]::TEXT[];")
    out.append("  v_baseline      TEXT[] := ARRAY[")
    out.append(",\n".join([f"    '{r['disc_id']}'" for r in rows]))
    out.append("  ]::TEXT[];")
    out.append("BEGIN")
    out.append("  -- 4a: total discipline row count should equal baseline size")
    out.append("  SELECT COUNT(*) INTO v_total_rows FROM layer0.disciplines;")
    out.append(f"  IF v_total_rows <> {n} THEN")
    out.append("    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: expected % rows, found %',")
    out.append(f"      {n}, v_total_rows;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4b: every baseline discipline_id must exist as a row")
    out.append("  SELECT COUNT(*) INTO v_missing_base")
    out.append("    FROM unnest(v_baseline) AS b(discipline_id)")
    out.append("    WHERE NOT EXISTS (")
    out.append("      SELECT 1 FROM layer0.disciplines d")
    out.append("      WHERE d.discipline_id = b.discipline_id")
    out.append("    );")
    out.append("  IF v_missing_base > 0 THEN")
    out.append("    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: % baseline discipline_id(s) not present',")
    out.append("      v_missing_base;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4c: no row may have NULL body_parts_at_risk")
    out.append("  SELECT COUNT(*) INTO v_null_rows")
    out.append("    FROM layer0.disciplines")
    out.append("    WHERE body_parts_at_risk IS NULL;")
    out.append("  IF v_null_rows > 0 THEN")
    out.append("    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: % row(s) with NULL body_parts_at_risk',")
    out.append("      v_null_rows;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4d: every token must be in the canonical 51-token set")
    out.append("  SELECT string_agg(DISTINCT t.part, ', ') INTO v_bad_parts")
    out.append("    FROM layer0.disciplines d,")
    out.append("         unnest(d.body_parts_at_risk) AS t(part)")
    out.append("    WHERE NOT (t.part = ANY (v_canonical));")
    out.append("  IF v_bad_parts IS NOT NULL THEN")
    out.append("    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: non-canonical token(s): %',")
    out.append("      v_bad_parts;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4e: no duplicate tokens within a single row's array")
    out.append("  -- (COALESCE on array_length: empty array → 0, not NULL)")
    out.append("  SELECT COUNT(*) INTO v_dup_rows")
    out.append("    FROM layer0.disciplines")
    out.append("    WHERE body_parts_at_risk IS NOT NULL")
    out.append("      AND COALESCE(array_length(body_parts_at_risk, 1), 0) IS DISTINCT FROM")
    out.append("          (SELECT COUNT(DISTINCT t)::INT FROM unnest(body_parts_at_risk) AS t);")
    out.append("  IF v_dup_rows > 0 THEN")
    out.append("    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: % row(s) with duplicate tokens',")
    out.append("      v_dup_rows;")
    out.append("  END IF;")
    out.append("")
    out.append("  -- 4f: no row outside the curated baseline")
    out.append("  SELECT COUNT(*) INTO v_off_baseline")
    out.append("    FROM layer0.disciplines d")
    out.append("    WHERE NOT (d.discipline_id = ANY (v_baseline));")
    out.append("  IF v_off_baseline > 0 THEN")
    out.append("    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: % discipline(s) outside the baseline',")
    out.append("      v_off_baseline;")
    out.append("  END IF;")
    out.append("")
    out.append(f"  RAISE NOTICE 'migrate_disciplines_add_body_parts_at_risk: OK — {n} rows populated, % canonical body parts, GIN index in place',")
    out.append("    array_length(v_canonical, 1);")
    out.append("END $$;")
    out.append("")
    out.append("COMMIT;")
    out.append("")
    out.append("-- End of migrate_disciplines_add_body_parts_at_risk_v1.sql")

    return "\n".join(out)


def main():
    rows = parse_curation_reference(CURATION_REF)

    assert len(rows) == 31, f"Expected 31 rows, got {len(rows)}"

    ids = [r["disc_id"] for r in rows]
    assert len(set(ids)) == len(ids), "Duplicate discipline_id detected"

    # Every token canonical (parser already validates, redundant check)
    for r in rows:
        for p in r["parts"]:
            assert p in CANONICAL_SET, f"{r['disc_id']}: non-canonical {p}"

    # Spot-checks for Andy's edits
    d016 = next(r for r in rows if r["disc_id"] == "D-018")
    assert "Finger pulley" in d016["parts"], "D-018 should have Finger pulley (climbing inherit)"
    assert "Trapezius" in d016["parts"], "D-018 should have Trapezius (hiking inherit)"

    d022 = next(r for r in rows if r["disc_id"] == "D-024")
    assert "Foot" in d022["parts"] and "Ankle" in d022["parts"], \
        "D-024 should have Foot + Ankle (tarsal/metatarsal stress reactions)"

    d021 = next(r for r in rows if r["disc_id"] == "D-023")
    assert all(p in d021["parts"] for p in ["Calf", "Shin", "Foot"]), \
        "D-023 should have Calf + Shin + Foot (lower leg + foot)"

    d006 = next(r for r in rows if r["disc_id"] == "D-008")
    assert "Collarbone" in d006["parts"], "D-008 should have Collarbone (canonical amendment)"

    d005a = next(r for r in rows if r["disc_id"] == "D-007")
    d005 = next(r for r in rows if r["disc_id"] == "D-006")
    assert set(d005a["parts"]) == set(d005["parts"]), \
        "D-007 should equal D-006 baseline (per Andy expansion)"

    # All 51 canonical tokens present? Probably not — check coverage
    all_used = set()
    for r in rows:
        all_used.update(r["parts"])
    print(f"Canonical tokens used: {len(all_used)} of {len(CANONICAL_BODY_PARTS)}")

    sql = emit_sql(rows)
    OUTPUT_SQL.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SQL.write_text(sql)

    print(f"Wrote: {OUTPUT_SQL}")
    print(f"  Disciplines: {len(rows)}")
    print(f"  Total token references: {sum(len(r['parts']) for r in rows)}")
    print(f"  D-018 spot-check: {sorted(d016['parts'])}")
    print(f"  D-024 spot-check: {sorted(d022['parts'])}")
    print(f"  D-008 spot-check: {sorted(d006['parts'])}")
    print(f"  D-006 = D-007: {set(d005['parts']) == set(d005a['parts'])}")
    print(f"  SQL size: {len(sql):,} chars, {sql.count(chr(10))+1} lines")


if __name__ == "__main__":
    main()
