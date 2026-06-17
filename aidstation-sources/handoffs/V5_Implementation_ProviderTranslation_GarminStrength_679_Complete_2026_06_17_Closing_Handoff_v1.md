# V5 Implementation — #679 Garmin strength resolver + 40-exercise catalog build — COMPLETE — Closing Handoff v1

**Date:** 2026-06-17
**Type:** Build (data-mapping inbound + Layer-0 catalog expansion). Shipped end-to-end, applied to prod, **#679 CLOSED completed**.
**Branches:** a series of `claude/garmin-679-*` (+ the original `claude/upbeat-euler-q4ucqa` core). PRs #699/#700/#701/#709/#710/#713/#714/#715/#717/#720 all merged.

---

## §1 — Session-start verification (Rule #9)

Continuation of the ratified #679 design (`designs/ProviderTranslation_GarminStrength_679_Design_v1.md`, RATIFIED v1). `verify-handoff.sh` was green on the predecessor handoff; on-disk anchors (`rx_engine.apply_session_outcome` line ~205, `NAME_TO_EX_ID`, `garmin_fit_parser` maps) confirmed. No drift.

## §2 — What this session produced (the whole #679 arc)

A logged strength exercise NAME now resolves to a canonical layer0 EX-id at the single write chokepoint, so Garmin/manual lifts surface as capacity-derived loads instead of NULL-EX-id "first exposure" rows.

1. **Resolver** (`provider_strength_resolve.py`, PR #699) — `resolve_strength_ex_id(name) -> (ex_id, match_kind)`: **alias** (`NAME_TO_EX_ID ∪ GARMIN_STRENGTH_ALIASES ∪ LOGGED_NAME_ALIASES`) → **category-collapse** (subtype → coarse FIT category → coarse `NAME_TO_EX_ID`, reverse map lazily from `garmin_fit_parser`) → **bucket-3** `(None,'bucket3')`. Wired into `rx_engine` with `match_kind`/`bucket3` in the return + Rule #15 log.
2. **Aliases (87)** — PRs #700 (17 Garmin Batch-A), #701 (70 logged-vocab), #715 (re-point to new EX-ids). **Key pivot:** a read-only prod query (`neon-query`) of Andy's `current_rx` showed the real target is his own vocabulary, not the Garmin enum (his FIT imports come *coarse* and already resolved). Everything he's logged/weighted already resolved; the 97 "unmapped" were unperformed scaffolding.
3. **40 new exercises EX250–289** (Tier 3, fully prescribable) — layer0 migrations **0012** (5, calibration slice Andy approved), **0013** (13), **0014** (12), **0015** (10). Each = full 0B row + `sport_exercise_map` relevance at `0B-v1.6.13`. `injury_flags_text` is **general biomechanics, never athlete-specific** (Andy's rule). PRs #709/#710/#713/#714.
4. **0016** (PR #717) — 7 renames (drop equipment qualifier) + the per-row equipment Andy specified + 4 equipment fixes (Sandbag/Battle ropes/Treadwall are valid picker tokens) + 5 coach-note appends. Supersede-and-reinsert at `0B-v1.6.14` (the 0008 pattern).
5. **`current_rx` backfill + cull** (PR #720) — `init_db` backfill extended from `NAME_TO_EX_ID` to the full alias map; 3 aliases removed to respect the #694 cull.
6. **Applied to prod** via gated `layer0-apply` (run 27722039891, Andy-approved). **Verified live:** 245 live exercises, EX250–289 present, EX002→"Goblet Squat", EX287 `{Battle ropes}`.

## §3 — Files (substantive)

`provider_strength_resolve.py` (new), `rx_engine.py` (wire), `init_db.py` (backfill), `etl/migrations/layer0/0012–0016` (5 migrations), `tests/test_provider_strength_resolve.py` (new) + `tests/test_rx_engine_apply_outcome_layer0.py` (extended). Worklist docs under `designs/ProviderTranslation_GarminStrength_679_*` (Design / CandidateBatch / NewExercise_ReviewSheet).

## §4 — Code / tests / validation

Full suite **2600 passed / 30 skipped** at close. Every layer0 migration **validated locally against the exact CI gate** before push (local postgres-16 as user `pg`: load snapshot stripping `\restrict`/`\unrestrict` + `SET transaction_timeout`, apply all `[0-9]*.sql`, run `python -m etl.layer0.validate_layer0`). No `rapidfuzz` runtime dep (resolver is exact-match; offline authoring used stdlib `difflib`). Multi-row `VALUES` INSERTs need the first row's NULLs cast (`NULL::integer`, `NULL::text[]`) or PG infers text. `contraindicated_parts` IS vocab-gated (use real body-part tokens; `Finger` is invalid → `Forearm`); muscles/equipment are NOT gated but should use canonical tokens (`Pectoralis Major`, `Latissimus Dorsi`, `Biceps Brachii`/`Biceps`, single-word tokens unquoted in PG arrays).

## §5 — Decisions pinned (Andy, this session)

- **Map them all** — full `current_rx` vocabulary, not just performed lifts.
- **Tier 3** for all new exercises (fully prescribable, sport_map).
- **No hard-coded personal warnings** in layer0 — it's platform reference data, not Andy's plan. General injury flags only.
- Generic names for KB Snatch→**Snatch**, KB Clean & Press→**Clean & Press**, KB Sumo Deadlift→**Sumo Deadlift** (multi-equipment).
- **Respect the #694 cull** — don't alias the culled names.
- **Don't drift:** the catalog build is the cost of closing the *first inbound slice*; the arc is the **provider data-unification (#681)**.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (4-tier order):**
1. **(Owed, Andy-action)** live-verify a real Garmin/manual strength log → capacity-derived load (`/admin/logs` → `match_kind=alias ex_id=EX2xx`). Container can't log.
2. **Provider matrix Wave 2** — the north star. Full inbound matrix (Strava/Whoop/Wahoo/Oura/MyFitnessPal/RWGPS/TrainingPeaks/Zwift/health platforms) per `specs/Provider_Data_Translation_Layer_Spec`. Then Wave 3 (outbound serializers), Wave 4 (bucket-3 inline UI), Wave 5 (API security), Wave 6 (MCP).
3. The concurrent **#698 recovery-session arc** (Slice 3) is a separate track owned elsewhere — see its predecessor entry in `CURRENT_STATE`.

## §7 — Carry-forward

- **Two `0012_` migrations** coexist on main (mine + `0012_retire_spin_stationary_bike` from #698). Cosmetic numbering collision; both apply/validate. If renumbering ever matters, mine could become `0017` — but it's applied to prod, so leave it.
- **Local layer0 validation recipe** (above, §4) is reusable — it mirrors the CI `layer0-gate` exactly and caught every issue before push.
- Sandbag/Battle ropes/Treadwall are valid equipment-picker tokens (confirmed live); they just weren't in any `equipment_required` before 0016.

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Resolver | `provider_strength_resolve.py` | `resolve_strength_ex_id`; 3 alias maps; `_subtype_to_category()` lazy from `garmin_fit_parser`; the 3 #694-culled names ABSENT |
| Wiring | `rx_engine.py` | `from provider_strength_resolve import resolve_strength_ex_id`; `match_kind`/`bucket3` in return |
| New exercises | `etl/migrations/layer0/0012`–`0015` | EX250–289, `0B-v1.6.13`, verify DO blocks |
| Catalog edits | `etl/migrations/layer0/0016_rename_exercises_and_equipment_edits.sql` | 7 renames + equipment + coach-notes at `0B-v1.6.14` |
| Backfill | `init_db.py` | backfill loop over `{**NAME_TO_EX_ID, **GARMIN_STRENGTH_ALIASES, **LOGGED_NAME_ALIASES}` |
| Live prod | `neon-query` run | 245 live ex, EX250–289 present, EX002="Goblet Squat", EX287 `{Battle ropes}` |
| Issue | GitHub #679 | CLOSED completed with PR refs |
