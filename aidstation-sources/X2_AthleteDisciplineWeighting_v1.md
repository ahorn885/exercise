# X2 — Athlete Discipline Weighting (end-to-end) — v1

Wires the half-built `athlete_discipline_weighting` feature so an athlete's
self-declared discipline load split actually reaches Layer 2A.

## Pre-existing (read path)
- `athlete_discipline_weighting` table (init_db `_PG_MIGRATIONS`): `user_id,
  discipline_slug, weight_pct, UNIQUE(user_id, discipline_slug)`. Sum-to-100 is
  app-enforced (no DB CHECK — multi-row edits have valid intermediate states).
- `layer1.builder._load_discipline_weighting` →
  `Layer1TrainingHistory.discipline_weighting` (with the model's sum-to-100
  validator). Layer 2A already accepts `athlete_discipline_overrides`
  (`{discipline_id: {"weight": pct}}`, X1b.2); `_compute_load_weight` (spec
  §5.4) lets an athlete weight win over the race-time-midpoint system default.

## The two gaps X2 closes
1. **Write side (UI):** athletes had no way to set the weighting.
2. **Orchestrator unpack:** the two 2A call sites passed no overrides.

## Decision (Andy)
The picker offers **all potential disciplines** (the distinct discipline set
across every sport's bridge), and the athlete selects + weights any subset.
All-or-nothing: non-zero weights must sum to 100, or the whole set is cleared
(revert to system defaults).

## Convention
`discipline_slug` stores the canonical `discipline_id` (`D-006`) — there is no
human discipline slug in `layer0.disciplines`, so storing the id makes the
orchestrator unpack a direct remap with no slug→id mapping layer.

## Changes
- **`athlete_discipline_weighting_repo.py`** (new): `load_discipline_catalog`
  (distinct bridge disciplines, `discipline_display_name` labels),
  `get_discipline_weighting`, `replace_discipline_weighting` (all-or-nothing +
  sum-to-100 / 1..100 validation; raises `DisciplineWeightingError`),
  `evict_layer1_on_discipline_weighting_change` (mirrors the skill-toggle
  eviction — weighting lives in the Layer 1 payload).
- **`routes/profile.py`**: GET loads catalog + current weights; new
  `POST /profile/disciplines` (`save_disciplines`) mirrors `save_skills`
  (parse `dw_<id>` → validate → replace → commit → evict Layer 1 → flash).
- **`templates/profile/edit.html`**: a separate weighting form in the Athlete
  tab (own form so its sum rule can't block the profile save), with a
  client-side running-total readout. No inline `style=` (redesign §18).
- **`layer4/orchestrator.py`**: `_athlete_discipline_overrides(layer1_payload)`
  unpack threaded into both 2A call sites (shared cone + single_session).

## Safety
Threading is inert until the table has rows (empty → `{}` → 2A system
defaults), so no behavior change for existing athletes until they set weights.

## Coverage
`tests/test_athlete_discipline_weighting_repo.py` — catalog dedupe, get
round-trip, sum-to-100 / over-100 / empty-clear / zero-filter write paths, and
the orchestrator unpack shape. Full suite green (2382+).

## Not owed
No ETL / Neon migration — the table already exists on prod.
