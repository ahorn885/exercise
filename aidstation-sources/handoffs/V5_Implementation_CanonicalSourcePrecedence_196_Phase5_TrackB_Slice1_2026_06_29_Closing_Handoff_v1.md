# V5 Implementation — #196 Phase 5 Track B Slice B1: Source-Precedence Pin Substrate — Closing Handoff (2026-06-29)

**Branch:** `claude/handoff-implementation-continue-aeqj8t` · **Suite:** 3604 passed / 30 skipped · **PR:** opening with auto-merge (SQUASH) on Andy's go · **Design:** `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md` · **Epic:** #196 (stays OPEN — Phase 5 Track B continues at B2).

> **▶ IMMEDIATE NEXT:** **Slice B2 — wellness coalesce → most-complete + read the wellness pin** (`canonical_wellness.py`), and **re-materialize `canonical_daily_wellness` + evict the user's 3A cache on a pin change**. This is the cross-layer / 3A-cache slice (Trigger #3): the wellness coalesce output feeds `integration_bundle_hash` → the 3A cache key (Phase 2 Slice 2.3). Read §6 below before building.

---

## 1. What this slice did (one line)

Shipped the **substrate** for user-configurable source precedence (#196 Phase 5, Track B): a `user_source_preferences` table + `source_preferences_repo.py` (`get`/`set`/`clear`, validated). **Behavior-inert — nothing reads it yet**; the consumers wire in B2 (wellness), B3 (cardio), B4 (UI).

## 2. The Phase-5 reframe (why Track A had no buildable work)

A file-grounded sweep found the epic's Phase-5 provider-stub list (Wahoo/Whoop/Strava/TrainingPeaks/Zwift/RideWithGPS) is **stale**:
- **9 of 10 providers already feed the canonical layer.** **RideWithGPS is fully wired** — `routes/ride_with_gps.py` does OAuth + record-and-defer webhook + cron drain → `_fetch_and_ingest_trip` → `_bulk_insert_cardio(..., source='rwgps')`, which runs `cluster_activity` + `materialize_canonical_activity`. (`rwgps` is in `_SOURCE_ORDER`.)
- **TrainingPeaks inbound is partner-approval-gated** — `routes/trainingpeaks.py` is **outbound-only by design** (it pushes plan sessions TO TP); inbound is "no personal use, paused to new partners," **untestable** (no API access, no fixture). An external-credential blocker, not a coding task.
- **Zwift inbound is deliberately not-built** (arrives via Strava/FIT; only outbound `.zwo` export).

So "Track A" (wire remaining providers) is done/blocked/not-built → Phase 5 = **Track B (source precedence)**.

## 3. Decisions ratified (Andy 2026-06-29)

1. **Hard pin** — a user-pinned source wins when it has a value/copy; otherwise fall through to the automatic merge.
2. **Fallback unified on "most complete" for BOTH wellness and cardio.** This **changes wellness's current default** (freshest-timestamp-wins, `canonical_wellness._coalesce`) to a cardio-style completeness merge.
3. **Single provider pin per domain** — one for `wellness`, one for `cardio`. Per-metric / per-field pins **deferred** ("consider later").

## 4. What shipped (3 substantive files + design)

- **`init_db.py`** (`_PG_MIGRATIONS` tail): `CREATE TABLE IF NOT EXISTS user_source_preferences (user_id, domain, preferred_provider, created_at, updated_at, PK(user_id, domain))`. Public-schema → **auto-applies on deploy, no Neon apply owed**.
- **`source_preferences_repo.py` (NEW):** `WELLNESS`/`CARDIO`/`DOMAINS`; `VALID_PROVIDERS` (wellness = `canonical_wellness._WELLNESS_SOURCE_PRIORITY` keys [imported]; cardio = `{garmin,wahoo,polar,coros,rwgps,strava}` [restated, test-pinned]); `SourcePreferenceError`; `get_source_preferences(db,uid) -> {domain: provider}`; `set_source_preference(db,uid,domain,provider)` (validate + upsert `ON CONFLICT (user_id,domain)`); `clear_source_preference(db,uid,domain)` (delete). Rule #15 `[source-pref]` logging on set/clear. Caller commits.
- **`tests/test_source_preferences_repo.py` (NEW, +10):** get empty / get map; set upsert SQL + params; unknown-domain and wrong-provider-for-domain raise + write nothing; clear delete + unknown-domain raise; source-of-truth lockstep (`test_wellness_providers_match_source`, `test_cardio_providers_match_source` import `_WELLNESS_SOURCE_PRIORITY` / `routes.garmin._PROVIDER_ID_COLUMNS` at test time).
- **`designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md` (NEW):** the full Track-B design (reframe, decisions, merge model, cache implication, B1–B4 slice plan).

## 5. Cache-key safety (this slice)

**None touched.** B1 is pure substrate — the new table is unread by any serving path, so no cache key, no invalidation, no Neon apply. (The cache work lands in B2/B3 when the pins are consumed.)

## 6. NEXT — Slice B2 (mechanically-applicable, Rule #11)

Wire the **wellness** pin + the unified most-complete fallback.

**6.1 `canonical_wellness.py`:**
- `materialize_canonical_wellness(db, uid, target_date)` already has `db` + `uid`. Read the pin once: `wellness_pin = source_preferences_repo.get_source_preferences(db, uid).get("wellness")`.
- Replace the per-metric **freshest-timestamp** pick (`_coalesce`, `:39`, `key=lambda c: (c[0] or datetime.min, _WELLNESS_SOURCE_PRIORITY[c[2]])`) with:
  1. **Hard pin:** if `wellness_pin` is set and that source has a non-null value for the metric → use it.
  2. **Else "most complete":** pick the source whose **daily record carries the most of the tracked metrics** as primary, then gap-fill each metric from the most-complete source that has it. (Faithful cardio-port — **confirm this reading with Andy at build** vs. a simpler per-metric "whoever has it, priority tiebreak". Open item §7.)
  - Keep `_WELLNESS_SOURCE_PRIORITY` as the final tiebreaker; keep determinism (the 3A bundle hash reads this — Slice 2.3).
- The candidate set already gathers all sources per metric (`:115-146`) — the change is the *selection rule*, not the gather.

**6.2 Cache invalidation (Trigger #3 — the load-bearing part):**
- **Switching freshest→most-complete is itself a one-time 3A shift:** the first materialize after B2 deploys re-coalesces every multi-source day → the 3A bundle hash moves once. Flag it; it's benign (re-synth on next plan run) but real.
- **On a pin set/change/clear:** re-materialize the user's `canonical_daily_wellness` (over the dates that have rows — `_wellness_backfill_targets`-style discovery, or a recent window; decide scope, §7) **and evict the user's 3A caches**. The 3A eviction path: find the layer3a/3A cache eviction helper (mirror how `canonical_wellness` callers / `layer3a` invalidate; the L1/L3/L4 eviction helpers live in `layer4/cache_invalidation.py` + the per-repo `evict_*` wrappers). Trigger this from the B4 picker route (and/or a repo-level helper) — NOT from B1's repo (kept inert).

**6.3 Read order for the next session (Rule #13):**
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this B1). 3. `CARRY_FORWARD.md` (#196 Phase 5 Track B entry). 4. This handoff + `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md`. 5. `canonical_wellness.py` (`_coalesce` `:39`, `materialize_canonical_wellness` `:66`) + `source_preferences_repo.py`. 6. `./scripts/verify-handoff.sh`.

Then **B3** (cardio merge + pin — thread the cardio pin into `routes/garmin.materialize_canonical_activity`, `:812`; re-materialize affected clusters on pin change) and **B4** (two-dropdown picker UI on the connections/settings surface → `set`/`clear` + the B2/B3 re-materialize+evict; coaching-voice copy).

## 7. Open questions (for B2 build)
- **"Most complete" for wellness scalars** — pick the source whose *daily record* is most complete as primary + per-metric gap-fill (the cardio-port, recommended), vs. a per-metric "whoever has it, priority tiebreak". Confirm with Andy.
- **Re-materialize scope on a pin change** — whole-history vs a recent window (bounded by what the 3A reader / `/wellness` actually consume).
- **Whether the whole Track is worth it now** — real power-user value but thin for a single-primary-device athlete; the automatic merge already does the sensible thing. Andy chose to build it; revisit if priorities shift (the Phase-4 LIVE-VERIFY is still owed and gated on his wellness re-upload).

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Substrate table | `init_db.py` | `CREATE TABLE IF NOT EXISTS user_source_preferences` + `PRIMARY KEY (user_id, domain)` in `_PG_MIGRATIONS` |
| Repo | `source_preferences_repo.py` | `def get_source_preferences` / `def set_source_preference` / `def clear_source_preference`; `VALID_PROVIDERS`; `class SourcePreferenceError` |
| Wellness provider source | `source_preferences_repo.py` | `from canonical_wellness import _WELLNESS_SOURCE_PRIORITY` (VALID_PROVIDERS[WELLNESS] built from it) |
| Tests | `tests/test_source_preferences_repo.py` | 10 tests incl. `test_cardio_providers_match_source` (pins to `routes.garmin._PROVIDER_ID_COLUMNS`) |
| Design | `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md` | exists; §3 decisions, §6 slice plan |
| Cache key | — | unchanged — table unread by any serving path → no invalidation |
| Suite | — | `… pytest tests/ -q` → 3604 passed / 30 skipped |
| Neon | — | **No apply owed** — public-schema table auto-applies on deploy |
| Epic | #196 | OPEN — commented (Phase-5 reframe + B1); B2/B3/B4 remain |
