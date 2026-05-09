"""
populate_substitutes_structured.py

Populates layer0.exercises.equipment_substitutes_structured from parsed
substitute data. Companion to migrate_exercises_substitutes_structured.sql.

Inputs:
  - parsed_substitutes.json (alongside this script in etl/sources/)
    Schema: [{ex_id, name, substitutes: [{substitute_text, equipment_required[], is_improvised}]}]
  - DATABASE_URL env var (Postgres connection string)

Behavior:
  - For each exercise in the JSON, find the active row in layer0.exercises by
    exercise_id and UPDATE equipment_substitutes_structured with the JSONB array.
  - Active row = superseded_at IS NULL.
  - Idempotent: running twice produces the same result. Running with revised
    JSON overwrites prior structured values on the same active rows.
  - Does NOT bump etl_version. The structured field is enrichment, not a
    semantic change to the existing exercise data. The historical context for
    "when this enrichment was added" lives in this script's commit history.
  - **Validates** that every equipment token emitted by the parser exists in
    layer0.equipment_items (canonical_name). Unknown tokens emit a WARNING but
    do not block the populate. This catches drift between the parser's regex
    output and the canonical vocabulary. Run populate_equipment_items_K_additions.sql
    BEFORE this script to ensure new vocab entries are in place.

Verification:
  - After run, all 154 exercises with non-empty substitute data should have a
    populated equipment_substitutes_structured field.
  - Total entries written should equal entries in JSON (currently 510).

Safe to re-run.
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json


def main():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL env var not set", file=sys.stderr)
        sys.exit(1)

    # JSON is in same directory as this script
    json_path = Path(__file__).parent / 'parsed_substitutes.json'
    if not json_path.exists():
        print(f"ERROR: {json_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(json_path) as f:
        parsed = json.load(f)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            # Verify column exists
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'layer0'
                  AND table_name = 'exercises'
                  AND column_name = 'equipment_substitutes_structured'
            """)
            if cur.fetchone() is None:
                raise RuntimeError(
                    "Column equipment_substitutes_structured not found. "
                    "Run migrate_exercises_substitutes_structured.sql first."
                )

            # ── Canonical vocab validation ──────────────────────────────────
            # Collect every equipment token the parser emitted. Compare against
            # layer0.equipment_items.canonical_name. Unknown tokens warn but
            # do not block. This catches parser/vocab drift early.
            cur.execute("SELECT canonical_name FROM layer0.equipment_items")
            canonical_set = {row[0] for row in cur.fetchall()}

            emitted_tokens = set()
            token_locations = {}  # token → list of (ex_id, substitute_text) for diagnostics
            for entry in parsed:
                for sub in entry['substitutes']:
                    for group in sub.get('equipment_required', []):
                        for token in group:
                            emitted_tokens.add(token)
                            token_locations.setdefault(token, []).append(
                                (entry['ex_id'], sub['substitute_text'][:60])
                            )

            unknown_tokens = emitted_tokens - canonical_set
            if unknown_tokens:
                print(
                    f"WARNING: {len(unknown_tokens)} equipment token(s) emitted by parser "
                    f"are not present in layer0.equipment_items:",
                    file=sys.stderr
                )
                for token in sorted(unknown_tokens):
                    examples = token_locations[token][:3]
                    example_str = '; '.join(f"{ex} '{t}'" for ex, t in examples)
                    print(f"  ✗ {token!r} — first occurrences: {example_str}", file=sys.stderr)
                print(
                    "  These tokens will be persisted but will not match athlete "
                    "equipment in Layer 1 Node 2C.\n"
                    "  Fix by either: (a) running populate_equipment_items_*.sql for the "
                    "missing vocab, or (b) updating parse_substitutes.py to emit known tokens.",
                    file=sys.stderr
                )
            else:
                print(
                    f"Canonical vocab check: OK — all {len(emitted_tokens)} emitted "
                    f"tokens present in layer0.equipment_items"
                )

            # ── Populate ────────────────────────────────────────────────────
            updated = 0
            not_found = []
            total_entries = 0

            for entry in parsed:
                ex_id = entry['ex_id']
                substitutes = entry['substitutes']
                total_entries += len(substitutes)

                # Update active row only
                cur.execute("""
                    UPDATE layer0.exercises
                    SET equipment_substitutes_structured = %s
                    WHERE exercise_id = %s
                      AND superseded_at IS NULL
                """, (Json(substitutes), ex_id))

                if cur.rowcount == 1:
                    updated += 1
                elif cur.rowcount == 0:
                    not_found.append(ex_id)
                else:
                    # Multiple active rows for same exercise_id is a data integrity issue
                    raise RuntimeError(
                        f"{ex_id}: {cur.rowcount} active rows found — "
                        "expected exactly 1. Fix versioning before re-running."
                    )

            # Verify counts
            cur.execute("""
                SELECT COUNT(*) FROM layer0.exercises
                WHERE equipment_substitutes_structured IS NOT NULL
                  AND superseded_at IS NULL
            """)
            populated_count = cur.fetchone()[0]

            print(f"populate_substitutes_structured:")
            print(f"  Exercises in JSON:        {len(parsed)}")
            print(f"  Updated:                  {updated}")
            print(f"  Not found (missing rows): {len(not_found)}")
            if not_found:
                print(f"    {not_found}")
            print(f"  Total substitute entries: {total_entries}")
            print(f"  Active rows with structured field populated: {populated_count}")

            if not_found:
                print(
                    "\nWARNING: Some exercises in JSON have no matching active row. "
                    "Check exercise_id consistency between exercises table and JSON.",
                    file=sys.stderr
                )
                conn.rollback()
                sys.exit(2)

            conn.commit()
            print("\nOK — committed.")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
