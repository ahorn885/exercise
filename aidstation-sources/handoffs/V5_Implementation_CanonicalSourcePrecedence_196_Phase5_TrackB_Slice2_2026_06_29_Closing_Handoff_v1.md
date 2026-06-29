# V5 Implementation — #196 Phase 5 Track B Slice B2: Wellness Coalesce → Most-Complete + Read the Wellness Pin — Closing Handoff (2026-06-29)

**Branch:** `claude/issue-196-implementation-aaju2n` · **Suite:** 3622 passed / 30 skipped · **PR:** [#984](https://github.com/ahorn885/exercise/pull/984) — auto-merge SQUASH armed · **Design:** `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md` · **Predecessor:** B1 (`…Slice1…`, PR #981 / `605f7e8`, MERGED) · **Epic:** #196 (stays OPEN — Track B continues at B3).

> **⚠️ #196 IS NOT DONE — WE CONTINUE ON IT NEXT SESSION.** This slice (B2) is one step of Phase 5 Track B. The epic **stays OPEN**: **B3** (cardio merge + pin) and **B4** (picker UI) remain before Track B closes, and Phase 5 is the last open phase of the #196 epic. The next session picks up at **B3** — do not treat the B2 merge as closing #196.

> **▶ IMMEDIATE NEXT:** **Slice B3 — cardio merge + pin** (`routes/garmin.materialize_canonical_activity`, `:812`): thread the cardio pin into the most-complete merge (the merge already IS most-complete — B3 only adds the hard-pin override), and re-materialize affected clusters on a pin change (a `apply_cardio_pin_change` analog of B2's `source_preference_apply.apply_wellness_pin_change`). Then **B4** (picker UI). Read §6 below.

---

## 1. What this slice did (one line)

Wired the **wellness consumer** of B1's substrate: rewrote the `canonical_wellness` coalesce from freshest-timestamp to the unified **most-complete merge** + an optional **hard pin**, and shipped the **re-materialize + 3A-evict** apply helper for a pin change (the cross-layer / 3A-cache part, Trigger #3).

## 2. The merge change (decision 2 — what flipped)

**Before (through Slice 2.3):** `canonical_wellness._coalesce` picked, per metric, the **freshest-non-null** value (newest ingest ts; `_WELLNESS_SOURCE_PRIORITY` only as a ts-tie tiebreak).

**Now (B2):** the **most-complete daily record** is primary (a faithful port of the cardio merge `materialize_canonical_activity`):
- `_rank_sources(*metric_cands)` orders the day's sources richest-first — completeness = how many of {sleep, hrv, rhr} a source carries that day; `_WELLNESS_SOURCE_PRIORITY` (garmin>whoop>oura>polar>coros) is now **only the tiebreak** between equally-complete records.
- `_coalesce(candidates, ranked, pinned)` per metric: **hard pin first** (decision 1 — if `pinned` carries a value here it wins) → else the first source in `ranked` that has the metric (primary-first **per-metric gap-fill**). Within a source the freshest row wins (defensive; ≤1 row/source/day).
- `materialize_canonical_wellness` reads the pin once via `source_preferences_repo.get_source_preferences(db, uid).get("wellness")` — **lazy import** inside the function (source_preferences_repo imports `_WELLNESS_SOURCE_PRIORITY` from this module, so a module-scope import would cycle). Rule #15 log gained a `pin=…` note.

Determinism is preserved (the merged row folds into `integration_bundle_hash` → the 3A cache key — Slice 2.3), so resumable passes stay stable.

## 3. The apply helper (cross-layer / 3A-cache — Trigger #3)

New **`source_preference_apply.py`** — kept OUT of B1's deliberately-inert repo:
- `apply_wellness_pin_change(db, cache, uid)` → `backfill_canonical_wellness(db, uid)` (re-materialize the user's whole wellness history under the new pin) **then** `evict_on_layer_change(cache, uid, "layer3a")`. Returns the evicted-row count. **Caller commits `db`.**
- **Why only `layer3a` eviction:** the 3A cache entry (`llm_layer3a_athlete_state`) keys on `integration_bundle_hash`, which is derived from `canonical_daily_wellness` — so a re-materialized day **natural-misses** the 3A row (Layer3A spec §9.2); no explicit 3A-row eviction is needed. The DOWNSTREAM L4 + 3B rows key on `layer3a_hash` and are evicted here as hygiene (`evict_on_layer_change('layer3a')` covers exactly those: `_ALL_ENTRY_POINTS + 3B`).
- **B4's picker route calls this** right after `set_source_preference` / `clear_source_preference`. B2 ships the helper ready; B4 wires the route.

## 4. Cache-key safety (this slice)

- **One-time benign 3A shift:** switching freshest→most-complete re-coalesces every multi-source day, so the **first** `materialize_canonical_wellness` after this deploys moves the 3A bundle hash once → a re-synth on the next plan run. Benign but real — flagged.
- **No schema/DDL → no Neon apply owed** (B1's `user_source_preferences` table is live since #981; this slice is code-only).

## 5. What shipped (3 substantive files + tests/bookkeeping)

- **`canonical_wellness.py`** — `_rank_sources` (new), `_coalesce` (rewritten signature `(candidates, ranked, pinned)`), pin read in `materialize_canonical_wellness`, log + docstring updates.
- **`source_preference_apply.py` (NEW)** — `apply_wellness_pin_change(db, cache, uid)`.
- **`tests/test_source_preference_apply.py` (NEW, +2)** — re-materialize-then-evict-`layer3a`; user-scoped.
- `tests/test_canonical_wellness.py` — `TestCoalesce` retuned to most-complete (completeness-beats-priority, gap-fill from a lesser source, completeness-tie→priority) + new `TestHardPin` (pin wins over a more-complete source; pinned-but-absent falls through).
- `tests/test_wellness_reader_equality.py` — the reference reader (`_coalesce_ref`/`_rank_sources_ref`/`_reference_recent_wellness`/`_RefConn`) + fixtures + `test_expected_shape` retuned to the most-complete rule; still cross-checks writer↔reader determinism that feeds the bundle hash.

(5 substantive files incl. the 3 touched test files; bookkeeping — CURRENT_STATE / CARRY_FORWARD / this handoff — is exempt.)

## 6. NEXT — Slice B3 (cardio merge + pin), mechanically-applicable (Rule #11)

**6.1 `routes/garmin.py::materialize_canonical_activity` (`:812`):** the cardio merge is ALREADY most-complete (`_primary_rank` = `-_completeness_score`, `_SOURCE_ORDER` tiebreak). B3 only adds the **hard pin**:
- Read the cardio pin: `cardio_pin = source_preferences_repo.get_source_preferences(db, uid).get("cardio")` (lazy import, same cycle-safety rationale as B2 — though `routes/garmin` already imports it freely; just keep it cheap).
- In the primary pick: if `cardio_pin` is set and a cluster member's `_row_provider(m) == cardio_pin`, that member is primary (decision 1 — a copy from the pinned provider exists in the cluster → it wins), **before** falling through to `_primary_rank`. The per-field gap-fill stays as-is (still fills from the highest-scoring copy that carries each field). Keep the `_SOURCE_ORDER` tiebreak.
- Rule #15: extend the existing `[cardio-canon]` log with a `pin=…` note.

**6.2 Apply helper:** add `apply_cardio_pin_change(db, cache, uid)` to `source_preference_apply.py` — re-materialize the user's affected clusters (find them: `SELECT id FROM activity_clusters WHERE user_id = ?` then `materialize_canonical_activity` each; or reuse whatever cluster-discovery the cardio backfill uses — check `routes/garmin` for an existing per-user re-materialize) **then** evict. **Cardio's eviction target:** `canonical_activity` feeds the 3A integration bundle too (recent workouts / ACWR), so the same `evict_on_layer_change(cache, uid, "layer3a")` applies — confirm the cardio feed actually lands in the 3A bundle (`layer3a/integration.py` recent-workouts read) before settling the layer.

**6.3 Tests:** pin the cardio hard-pin primary pick + the apply helper (mirror `test_source_preference_apply.py`).

**6.4 Read order for the next session (Rule #13):** 1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this B2). 3. `CARRY_FORWARD.md` (#196 Phase 5 Track B entry). 4. This handoff + `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md`. 5. `routes/garmin.py` (`materialize_canonical_activity` `:812`, `_primary_rank`/`_completeness_score`/`_row_provider` `:780-812`) + `source_preference_apply.py` + `source_preferences_repo.py`. 6. `./scripts/verify-handoff.sh`.

Then **B4** (two-dropdown picker UI on the connections/settings surface → `set`/`clear` + the B2/B3 apply helpers; coaching-voice copy).

## 7. Open items / decisions made this slice

- **"Most complete" for wellness scalars — RESOLVED to the cardio-port** (most-complete daily record primary + per-metric gap-fill), per decision 2 / design §4. The simpler per-metric "whoever has it, priority tiebreak" was the alternative; the port was chosen for cross-metric internal consistency (sleep+hrv+rhr from one device when it's the richest record). If Andy prefers the simpler rule, it's a localized change to `_coalesce` (drop the `ranked` order, pick per-metric by priority).
- **Re-materialize scope on a pin change — RESOLVED to whole-history** (`backfill_canonical_wellness(db, uid)`): reuses tested, idempotent code, and the 3A eviction is user-scoped regardless of date, so a recent-window optimization buys nothing on correctness. Narrow to a recent window only if backfill latency becomes a problem on a large history.
- **Whether the Track is worth it** — unchanged from B1 §7: real power-user value, thin for a single-primary-device athlete; Andy chose to build it. The Phase-4 LIVE-VERIFY is still owed (gated on his wellness re-upload).

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Most-complete merge | `canonical_wellness.py` | `def _rank_sources` + `def _coalesce(candidates, ranked, pinned)`; `_coalesce` body has `if pinned is not None and pinned in by_source` |
| Pin read | `canonical_wellness.py` | `from source_preferences_repo import WELLNESS, get_source_preferences` inside `materialize_canonical_wellness` |
| Apply helper | `source_preference_apply.py` | `def apply_wellness_pin_change`; `backfill_canonical_wellness(db, uid)` + `evict_on_layer_change(cache, uid, "layer3a")` |
| Wellness merge tests | `tests/test_canonical_wellness.py` | `class TestHardPin`; `TestCoalesce::test_completeness_beats_priority_for_primary` |
| Apply test | `tests/test_source_preference_apply.py` | `test_apply_rematerializes_user_and_evicts_layer3a` (asserts `layer == "layer3a"`) |
| Reader-equality | `tests/test_wellness_reader_equality.py` | `_reference_recent_wellness` + `test_new_path_equals_reference`; `test_expected_shape` r19 hrv source == `garmin` |
| Cache key | — | unchanged inputs; one-time benign 3A bundle-hash shift on first post-deploy materialize (freshest→most-complete) |
| Neon | — | **No apply owed** — code-only; B1's table is live |
| Suite | — | `… pytest tests/ -q` → 3622 passed / 30 skipped (3 pre-existing #217 Layer3B warnings) |
| Epic | #196 | OPEN — B2 done; B3/B4 remain |
