#!/usr/bin/env python3
"""
populate_substitute_covers.py

Computes and writes substitute_covers for every row in layer0.discipline_substitutes
where superseded_at IS NULL.

Logic:
  substitute_covers = (target.stimulus_components ∩ substitute.stimulus_components)
                      minus manual overclaim overrides

Run AFTER populate_stimulus_components.sql has been applied.

Usage:
  DATABASE_URL=postgres://... python populate_substitute_covers.py [--dry-run]
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Manual overclaim overrides
# Paddle-sport grip patterns (sustained rotational pull) do not transfer to
# climbing grip patterns (crimping, pinching, static hold).
# Remove 'grip_strength' from substitute_covers when a paddle sport is used
# as substitute for a climbing/mountaineering discipline.
# ---------------------------------------------------------------------------
GRIP_OVERCLAIM_TARGETS = {'D-012', 'D-013', 'D-014', 'D-018'}
GRIP_OVERCLAIM_SOURCES = {'D-009', 'D-010', 'D-011', 'D-019'}


def apply_overrides(target_id: str, substitute_id: str, intersection: set) -> list:
    result = set(intersection)
    if target_id in GRIP_OVERCLAIM_TARGETS and substitute_id in GRIP_OVERCLAIM_SOURCES:
        result.discard('grip_strength')
    return sorted(result)


def main(dry_run: bool = False):
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        sys.exit('DATABASE_URL not set')

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Fetch canonical discipline stimulus maps
        cur.execute("""
            SELECT discipline_id, stimulus_components
            FROM layer0.disciplines
            WHERE superseded_at IS NULL
              AND stimulus_components IS NOT NULL
        """)
        rows = cur.fetchall()
        if not rows:
            sys.exit('No disciplines with stimulus_components found. '
                     'Run populate_stimulus_components.sql first.')

        stim_map = {r['discipline_id']: set(r['stimulus_components']) for r in rows}
        print(f'Loaded stimulus_components for {len(stim_map)} disciplines')

        # Fetch all canonical substitution rows
        cur.execute("""
            SELECT id, target_id, substitute_id, target_name, substitute_name
            FROM layer0.discipline_substitutes
            WHERE superseded_at IS NULL
            ORDER BY target_id, substitute_id
        """)
        subs = cur.fetchall()
        print(f'Found {len(subs)} substitution rows to process')

        updates = []
        warnings = []

        for row in subs:
            tid = row['target_id']
            sid = row['substitute_id']

            t_stim = stim_map.get(tid)
            s_stim = stim_map.get(sid)

            if t_stim is None:
                warnings.append(f'  WARN: target {tid} ({row["target_name"]}) '
                                 f'has no stimulus_components — skipping row {row["id"]}')
                continue
            if s_stim is None:
                warnings.append(f'  WARN: substitute {sid} ({row["substitute_name"]}) '
                                 f'has no stimulus_components — skipping row {row["id"]}')
                continue

            intersection = t_stim & s_stim
            covers = apply_overrides(tid, sid, intersection)

            override_applied = (
                'grip_strength' in intersection and
                tid in GRIP_OVERCLAIM_TARGETS and
                sid in GRIP_OVERCLAIM_SOURCES
            )

            updates.append({
                'id': row['id'],
                'target_id': tid,
                'substitute_id': sid,
                'covers': covers,
                'override': override_applied,
            })

        # Report
        for w in warnings:
            print(w)

        override_rows = [u for u in updates if u['override']]
        print(f'\nRows to update:   {len(updates)}')
        print(f'Warnings (skipped): {len(warnings)}')
        print(f'Override applied (grip removed): {len(override_rows)}')

        if override_rows:
            print('\nOverride details:')
            for r in override_rows:
                print(f'  {r["target_id"]} ← {r["substitute_id"]}: '
                      f'grip_strength removed from covers')

        zero_coverage = [u for u in updates if not u['covers']]
        if zero_coverage:
            print(f'\nZero-coverage rows ({len(zero_coverage)}) '
                  f'— no overlap between target and substitute stimuli:')
            for r in zero_coverage:
                print(f'  {r["target_id"]} ← {r["substitute_id"]}')

        if dry_run:
            print('\n[DRY RUN] No changes written.')
            conn.rollback()
            return

        # Apply updates
        updated = 0
        for u in updates:
            cur.execute("""
                UPDATE layer0.discipline_substitutes
                SET substitute_covers = %s
                WHERE id = %s AND superseded_at IS NULL
            """, (u['covers'], u['id']))
            updated += cur.rowcount

        # Verify
        cur.execute("""
            SELECT COUNT(*) AS remaining_null
            FROM layer0.discipline_substitutes
            WHERE superseded_at IS NULL AND substitute_covers IS NULL
        """)
        remaining = cur.fetchone()['remaining_null']

        if remaining > len(warnings):
            conn.rollback()
            sys.exit(f'Unexpected NULL rows remaining after update: {remaining}. '
                     f'Expected at most {len(warnings)} (skipped). Rolling back.')

        conn.commit()
        print(f'\nDone. {updated} rows updated. '
              f'{remaining} rows still NULL (expected — skipped due to missing stimulus data).')


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    main(dry_run=dry_run)
