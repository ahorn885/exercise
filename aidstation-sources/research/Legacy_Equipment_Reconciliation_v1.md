# Legacy Equipment Reconciliation (pre-V5) — v2

Reconciles the 22 active legacy `layer0.equipment_items` rows (families
`0A-v17.K`, `0B-v19.K2`, `0B-v19.K3`) — seeded by retired one-shot scripts
(`populate_equipment_items_K*.sql`) to feed Layer 2C resolution — into the
0C-owned vocab, then supersedes the legacy rows. After this, `equipment_items`
is single-source (0C) and the version-scope orphan problem is gone.

## Architecture facts (verified)
- Matching (`layer2c/builder.py:360`) is **exact-string set membership**
  (`set(equipment_required).issubset(effective_pool)`); no case normalization.
- `effective_pool` = locale equipment tags **+ enabled readiness toggles**. The
  transform already rolls sport gear sub-components into the **12 toggles** via
  `vocabulary_transforms._ROLLUP` (e.g. `Climbing Rope`→`Climbing — roped`,
  `Touring Skis`→`Touring/AT ski setup`). **The toggle IS the "kit" bundle.**
- Exercise col-7 IS transformed (`exercise_db.py:172`). Substitutes
  (`parsed_substitutes.json`) are loaded **as-is** — tokens must match a pool
  member verbatim (an equipment name or a toggle name).

## Decision (Andy): Option 1 — route into existing toggles
"Bundle climbing into a kit" is *already* satisfied by the toggle rollup — an
athlete flips `Climbing — roped` and never sees harness/rope/quickdraws. So we
route the legacy aggregate tokens into the existing toggles rather than adding a
redundant `Climbing kit` equipment row (which would also have collided with the
roped-vs-boulder distinction the exercise DB already encodes). Chosen over a
flat single-kit collapse because it preserves matching fidelity and touches no
schema/builder/toggle-table code.

**Bouldering** is not a discipline in any of our sports → slated for full
removal (follow-up issue). No V4b token routes into the `Bouldering` toggle;
the legacy training-wall token (`Climbing holds`) routes to `Climbing — roped`.

## Mapping (22 legacy rows)
| Legacy row | Action |
|---|---|
| Climbing gear, Climbing Wall, Harness, Quickdraws, Climbing rope, Climbing holds, Climbing gym membership, Crash pad | `_ROLLUP` → existing climbing toggle (`Climbing — roped`); Crash pad keeps its existing `Bouldering` rollup (dies with the follow-up) |
| Mountaineering kit | `_ROLLUP` → `Mountaineering` |
| Touring ski kit | `_ROLLUP` → `Touring/AT ski setup` |
| XC ski kit | unreferenced by any exercise → dropped (no rollup needed) |
| TT Bike | `_RENAME` → existing `TT / triathlon bike` vessel |
| Rollerskis, Inline skates | re-add as equipment → Sport-Specific — Winter |
| Hyperextension bench | re-add → Machines - Strength |
| Ab straps, Mini hurdles, Stairs | re-add → Bodyweight & Portable |
| Mini trampoline, Wobble board | re-add → Plyo, Power & Stability |
| Stick roller | re-add → Recovery & Therapy |

New 0C equipment rows: **9** (Rollerskis, Inline skates + 7 gym/misc). Active
`equipment_items`: 122 → **131** (legacy 22 superseded).

## Changes
- `Vocabulary_Audit_v2.md` §3: Rollerskis/Inline skates + gym-misc rows; note
  that kits are toggle rollups.
- `vocabulary_transforms.py`: `_ROLLUP` += legacy climbing/ski aggregate tokens;
  `_RENAME` += `tt bike`→vessel.
- `parsed_substitutes.json`: EX101/EX133 climbing tokens → `Climbing — roped`.
- `retire_legacy_equipment_v4b.sql`: supersede the 22 legacy rows. **Run FIRST**,
  then apply `layer0_etl_v1.6.4.sql` (several re-homed names are case-insensitive
  duplicates of the legacy rows; retiring first clears the active-name index).

## Correctness gate (passed)
Re-emit + token-coverage check: every exercise (Tier-1) and non-improvised
substitute (Tier-2) token in V4b scope resolves to an active equipment row or an
existing toggle. No new `Bouldering` route introduced.

## Owed follow-ups (NOT built here)
1. **Remove Bouldering** toggle/discipline end-to-end (Andy: not a real
   discipline) — GitHub issue.
2. **Athlete data migration**: existing saved selections of retired tokens
   (`TT Bike`, and any old climbing/ski equipment picks) → the new vessel /
   toggles, so current athletes keep matching.
3. **Pre-existing finding** (separate from V4b): ~29 exercise col-7 equipment
   tokens are Title-case variants (`Ab Wheel`, `Foam Roller`, `Gymnastic Rings`,
   …) that don't match their sentence-case `equipment_items` canonical — the
   md's documented "✓ rename" intent was never wired into `_RENAME`. Those
   exercises silently fail Tier-1 equipment matching. Worth its own slice.
