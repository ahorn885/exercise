# Equipment-Token Mismatch Fix (V4c) — v1

Follows V4b (PR #501). Fixes a silent matching bug surfaced by V4b's
token-coverage check.

## The bug
Layer 2C matching is exact-string set membership against the athlete's pool
(`layer2c/builder.py:360`), and the pool is built from layer0 **canonical**
equipment names — sentence-case (`locations.locale_effective_tags`: gym profile
JSON + overrides, both canonical). The audit (`Vocabulary_Audit_v2.md`)
documents col-7 → canonical renames with a `✓`, but most were **never wired
into `vocabulary_transforms._RENAME`**. So Title-case exercise tokens (`Ab
Wheel`, `Foam Roller`, `Gymnastic Rings`, `Pull-Up Bar`, …) leaked through the
transform unchanged and could never match the sentence-case canonical — **29
exercise tokens silently failed Tier-1 equipment matching**, with no error.

## Fix
- **27 `_RENAME` entries** for the orphaned exercise tokens: 22 pure case-only
  (`Ab Wheel`→`Ab wheel`, …) + 5 target renames (`Bike trainer`→`Cycling
  trainer`, `TRX`/`suspension trainer`→`TRX / suspension trainer`, `Sea
  Kayak`→`Kayak`, `Rowing Shell`→`Rowing ergometer`).
- **Fixed 7 latent wrong-case rename *values*** already in `_RENAME` (the same
  bug, just not yet exercised): `rings`→`Gymnastic rings`, `band`→`Resistance
  band`, `mtb`→`Mountain bike`, `cable`→`Cable machine`, `box`/`vault box`→`Plyo
  box`, `vest`/`weight vest`→`Weighted vest`, `shoes`→`Running shoes`. (The
  stale tests that asserted the old Title-case output were corrected.)
- **Dropped 2 tokens** (`_DROP_TOKENS`): `Chairs` (improvised furniture) and
  `Canoe Seat` (assumed with the vessel — Andy).
- **Removed 4 unreferenced paddle accessories** from the vocab (Andy: don't
  track a seat/paddle/oar if they have the vessel): `Paddle (double-blade)`,
  `Single-blade paddle`, `Rowing oar`, `Kayak / canoe seat`. On-water rowing is
  not prescribed, so `Rowing Shell` normalizes to `Rowing ergometer`.

Active `equipment_items`: 131 → **127**.

## Recurrence guard (the real root-cause fix)
`etl/tests/test_equipment_token_coverage.py` — asserts (1) every Tier-1 exercise
token and (2) every non-improvised Tier-2 substitute token resolves to an active
canonical or a toggle, and (3) every `_RENAME`/`_ROLLUP` target is itself a valid
pool token. This is the check that was missing; it would have caught the
original drift and will catch any future col-7/canonical divergence.

## Neon apply
Single step: apply `etl/output/layer0_etl_v1.6.5.sql`. The 4 removed accessories
are 0C rows, retired by the normal `0C-v%` supersede sweep on apply (no legacy
pre-migration, no CI-name collision).

## Out of scope / flagged
- `_RENAME["race belt)"] → "Race belt"`: dormant, unreferenced typo-fix mapping
  to a non-canonical (race belts aren't tracked equipment). Left as-is; excluded
  from the guard test. Decide separately whether to drop it.
