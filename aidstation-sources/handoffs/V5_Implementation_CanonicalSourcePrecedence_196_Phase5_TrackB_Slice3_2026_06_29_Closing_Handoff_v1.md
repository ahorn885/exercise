# V5 Implementation — #196 Phase 5 Track B Slice B3: Cardio Merge + Pin — Closing Handoff (2026-06-29)

**Branch:** `claude/issue-196-canonical-source-wyhs08` · **Suite:** 3645 passed / 30 skipped · **PR:** not yet opened (push + bookkeep + wait for Andy's go — project rule) · **Design:** `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md` · **Predecessor:** B2 (`…Slice2…`, PR #984 / `086fe26`, MERGED) · **Epic:** #196 (stays OPEN — Track B continues at B4).

> **⚠️ #196 IS NOT DONE — WE CONTINUE ON IT NEXT SESSION.** This slice (B3) wires the cardio consumer of B1's substrate. The epic **stays OPEN**: **B4** (picker UI) is the last Track-B slice, and Phase 5 is the last open phase of #196. The next session picks up at **B4** — do not treat a B3 merge as closing #196.

> **▶ IMMEDIATE NEXT:** **Slice B4 — picker UI.** A two-dropdown source-precedence picker (wellness provider / cardio provider) on the connections/settings surface → `source_preferences_repo.set_source_preference` / `clear_source_preference`, then call the apply helpers (`source_preference_apply.apply_wellness_pin_change` / `apply_cardio_pin_change`) to re-materialize + evict. Coaching-voice copy. Read §6 below.

---

## 1. What this slice did (one line)

Wired the **cardio consumer** of B1's substrate: threaded the **hard cardio pin** into the `canonical_activity` most-complete merge (`routes/garmin.materialize_canonical_activity`) and shipped the **re-materialize-clusters + 3A-evict** apply helper for a cardio pin change (`apply_cardio_pin_change`) — the faithful analog of B2's wellness slice.

## 2. The merge change (decision 1 — the hard pin)

**Before (through B2):** the cardio merge picked the **most-complete copy** as primary (`_primary_rank` = `(-_completeness_score, _SOURCE_ORDER)`), per-field gap-fill from the highest-scoring copy that carries each field, `_SOURCE_ORDER` (garmin>wahoo>polar>coros>rwgps>strava) only as a completeness-tie tiebreak.

**Now (B3):** the merge is **already most-complete** — B3 only adds the **hard pin override** (decision 1):
- `_primary_rank(row, pin=None)` gained a **leading hard-pin term**: `(0 if pin and _row_provider(row) == pin else 1, -_completeness_score(row), _SOURCE_ORDER.get(...))`. A copy from the pinned provider sorts ahead of everything → becomes **primary**. Among non-pinned copies (and among multiple pinned copies — defensive, clustering keeps ≤1/provider/cluster) completeness then source-order still decide.
- The **per-field gap-fill is unchanged** — it still iterates `ranked` and fills each field from the highest-scoring copy that carries it. Because the pinned primary leads `ranked`, its values win where present; a **richer non-pinned copy still gap-fills the fields the pinned primary lacks** (e.g. pin Strava for the activity but still take power from the Wahoo copy in the cluster).
- `materialize_canonical_activity` reads the pin once via `source_preferences_repo.get_source_preferences(db, uid).get(CARDIO)` — **lazy import** inside the function (keeps the route module's import graph cheap; mirrors B2's cycle-safety pattern). Read placed **after** the empty-cluster early-return, so an empty cluster does no pin query. Rule #15 `[cardio-canon]` log gained a `pin=…` note.

Absent pin, or a pin whose provider has no copy in the cluster → the automatic most-complete merge, **byte-identical to before** (the leading term is `1` for every member → the sort collapses to the old key).

Determinism is preserved (the merged row → `canonical_activity` → the `canonical_cardio_feed` view → `integration_bundle_hash` → the 3A cache key), so resumable passes stay stable.

## 3. The apply helper (cross-layer / 3A-cache — Trigger #3)

Added **`apply_cardio_pin_change(db, cache, uid)`** to `source_preference_apply.py` (the analog of `apply_wellness_pin_change`):
- Discover the user's clusters: `SELECT id FROM activity_clusters WHERE user_id = ?` (no pre-existing per-user cardio re-materialize existed — checked `routes/garmin`), re-materialize each via `materialize_canonical_activity` (lazy import of `routes.garmin` — keeps the Flask blueprint graph off the module import path; the cache backend stays lazy too, mirroring B2). Then `evict_on_layer_change(cache, uid, "layer3a")`. Returns the evicted-row count. **Caller commits `db`.**
- **Why `layer3a` eviction (confirmed, per §6.2 of the B2 handoff's ask):** the cardio merge feeds the 3A integration bundle — `layer3a/integration.q_layer3A_recent_workouts` (line 110+) and the ACWR read (line 324+) both read **`canonical_cardio_feed`**, which `init_db.py:2940` defines as a **VIEW over `canonical_activity`** (JOIN to the primary `cardio_log` ∪ unclustered rows). So a re-materialized cluster is reflected in the feed immediately, the 3A bundle hash moves, and the 3A row **natural-misses** on `integration_bundle_hash` (Layer3A spec §9.2) — no explicit 3A-row eviction needed. The DOWNSTREAM L4 + 3B rows key on `layer3a_hash` and are evicted here as hygiene (`evict_on_layer_change('layer3a')` = `_ALL_ENTRY_POINTS + 3B`).
- **B4's picker route calls this** right after `set_source_preference` / `clear_source_preference`. B3 ships the helper ready; B4 wires the route.

## 4. Cache-key safety (this slice)

- **No one-time shift this slice.** Unlike B2 (which flipped the wellness rule freshest→most-complete and re-coalesced every multi-source day), B3's merge is *already* most-complete — adding the hard-pin term changes the output **only for a user who has actually set a cardio pin** (none today). With no pins set, every `materialize_canonical_activity` is byte-identical → no 3A bundle-hash shift, no re-synth.
- **No schema/DDL → no Neon apply owed** (code-only; B1's `user_source_preferences` table is live since #981).

## 5. What shipped (2 substantive code files + tests/bookkeeping)

- **`routes/garmin.py`** — `_primary_rank(row, pin=None)` (hard-pin leading term), pin read in `materialize_canonical_activity` (`get_source_preferences(...).get(CARDIO)`, lazy import), `sorted(..., key=lambda m: _primary_rank(m, cardio_pin))`, Rule #15 `pin=` log + docstring update.
- **`source_preference_apply.py`** — new `apply_cardio_pin_change(db, cache, uid)`; module docstring updated (cardio paragraph + B4 caller note).
- `tests/test_garmin_bulk_source.py` — `_CanonConn` gained an optional `cardio_pin` (serves the new `user_source_preferences` read; existing constructions pass an absent pin → unchanged) + new `TestCardioHardPin` (×2: pin makes the pinned copy primary over a richer copy with gap-fill from the richer copy; pinned-but-absent-from-cluster falls through to most-complete).
- `tests/test_source_preference_apply.py` — `_FakeCardioDb` + `TestApplyCardio` (×2: re-materialize-the-user's-clusters-then-evict-`layer3a`; user-scoped).

(2 substantive code files + 2 touched test files = 4, within ceiling; bookkeeping — CURRENT_STATE / CARRY_FORWARD / this handoff / issue reconcile — is exempt.)

## 6. NEXT — Slice B4 (picker UI)

**6.1 Surface.** A two-dropdown source-precedence picker (wellness provider / cardio provider) on the **connections/settings surface** (`routes/connections.py` + its template — confirm where the existing provider-connection cards render). Each dropdown's options = the valid providers for that domain (`source_preferences_repo.VALID_PROVIDERS[WELLNESS]` / `[CARDIO]`) **filtered to the providers the athlete has actually connected** (don't offer a pin for a source they don't feed) + an explicit "Automatic (most complete)" = no pin.

**6.2 Route.** `POST` handler: on a chosen provider → `set_source_preference(db, uid, domain, provider)`; on "Automatic" → `clear_source_preference(db, uid, domain)`; **commit**; then call the matching apply helper (`apply_wellness_pin_change` / `apply_cardio_pin_change`) so the canonical layer re-materializes and the 3A-dependent caches evict. Both helpers take `(db, cache, uid)` and the **caller commits `db`** (they run in the caller's txn; the cache eviction is the backend's own commit). Rule #15 log already exists in both the repo (`set`/`clear`) and the apply helpers — the route just needs its own `[source-pref-ui]`-style line if you want the form decision logged.

**6.3 Copy (coaching-voice, Stop-and-ask Trigger #1 if it's prompt-shaped — but this is UI microcopy, not an LLM prompt, so just write it direct).** Explain the pin plainly: "We merge your devices automatically, picking the most complete record. Pin a preferred source to override that when it has data." No hype.

**6.4 Tests:** the route's set/clear/automatic branches each call the right repo fn + apply helper (mock the apply helper); the dropdown options are filtered to connected providers.

**6.5 Read order for the next session (Rule #13):** 1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this B3). 3. `CARRY_FORWARD.md` (#196 Phase 5 Track B entry). 4. This handoff + `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md`. 5. `source_preferences_repo.py` (`set`/`clear`/`VALID_PROVIDERS`) + `source_preference_apply.py` (both apply helpers) + `routes/connections.py` (the connection-card surface). 6. `./scripts/verify-handoff.sh`.

## 7. Open items / decisions made this slice

- **Pin scope vs gap-fill — RESOLVED to "pin the PRIMARY only, gap-fill stays completeness-ordered"** (decision 1 / design §4): the pinned provider's copy is primary, but a richer non-pinned copy still fills the fields the pinned copy lacks. This matches the wellness B2 behavior (hard-pin-first per metric, then gap-fill) and the design's "pinned copy is primary; else most complete." The alternative (pin every field to the pinned provider, no gap-fill from richer copies) was **not** taken — it would discard real sensor data the athlete's pinned device didn't record.
- **Re-materialize scope on a cardio pin change — RESOLVED to all-of-the-user's-clusters** (`SELECT id FROM activity_clusters WHERE user_id = ?`): mirrors B2's whole-history wellness choice — reuses the idempotent `materialize_canonical_activity`, and the 3A eviction is user-scoped regardless of date, so a recent-window optimization buys nothing on correctness. Narrow to a recent window only if re-materialize latency becomes a problem on a large activity history.
- **Whether the Track is worth it** — unchanged from B1/B2 §7: real power-user value, thin for a single-primary-device athlete; Andy chose to build it. The Phase-4 LIVE-VERIFY is still owed (gated on his wellness re-upload).

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Hard-pin sort key | `routes/garmin.py` | `def _primary_rank(row, pin=None)`; body has `0 if pin and _row_provider(row) == pin else 1` |
| Pin read | `routes/garmin.py` | `from source_preferences_repo import CARDIO, get_source_preferences` inside `materialize_canonical_activity`; `sorted(members, key=lambda m: _primary_rank(m, cardio_pin))` |
| Rule #15 log | `routes/garmin.py` | `pin_note = f" pin={cardio_pin}"` appended to the `[cardio-canon]` print |
| Apply helper | `source_preference_apply.py` | `def apply_cardio_pin_change`; `SELECT id FROM activity_clusters WHERE user_id = ?` + `materialize_canonical_activity` + `evict_on_layer_change(cache, uid, "layer3a")` |
| Cardio merge tests | `tests/test_garmin_bulk_source.py` | `class TestCardioHardPin`; `test_pin_makes_pinned_copy_primary_over_richer_copy` (asserts `primary_cardio_log_id == 74`, `avg_power` gap-filled from id73/wahoo) |
| Apply test | `tests/test_source_preference_apply.py` | `test_apply_cardio_rematerializes_user_clusters_and_evicts_layer3a` (asserts `layer == "layer3a"`) |
| Cardio→3A feed | `init_db.py:2940` + `layer3a/integration.py` | `CREATE OR REPLACE VIEW canonical_cardio_feed AS … FROM canonical_activity`; `q_layer3A_recent_workouts` reads `canonical_cardio_feed` |
| Cache key | — | unchanged inputs; **no** one-time shift (merge already most-complete; pin output changes only for a user who set a pin — none today) |
| Neon | — | **No apply owed** — code-only; B1's table is live |
| Suite | — | `… pytest tests/ -q` → 3645 passed / 30 skipped (3 pre-existing #217 Layer3B warnings) |
| Epic | #196 | OPEN — B3 done; B4 (picker UI) remains |
