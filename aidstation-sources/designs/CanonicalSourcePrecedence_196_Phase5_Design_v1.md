# Canonical Source-Precedence (User Pins) — #196 Phase 5, Track B — Design v1 (2026-06-29)

**Epic:** #196 (Unified athlete health-data layer). **Phase:** 5 (multi-service expansion). **Track:** B (user-configurable source precedence). **Predecessor canonical work:** Phase 2 (`canonical_daily_wellness`) + Phase 3 (`canonical_activity` / `canonical_cardio_feed`).

---

## 1. Why this exists + the Phase-5 reframe

The epic's Phase-5 line lists six provider stubs to wire (Wahoo/Whoop/Strava/TrainingPeaks/Zwift/RideWithGPS) **plus** a user-configurable source-precedence UI. A 2026-06-29 file-grounded sweep found the provider half is essentially done or blocked, so Phase 5 reduces to **Track B (source precedence)**:

- **9 of 10 providers already feed the canonical layer.** Garmin/Whoop/Oura/Polar/COROS coalesce into `canonical_daily_wellness`; Garmin/Polar/COROS/Strava/Wahoo/**RideWithGPS** merge into `canonical_activity` (RWGPS via `routes/ride_with_gps.py` → `_bulk_insert_cardio(source='rwgps')` → clusterer → materialize).
- **TrainingPeaks inbound is partner-approval-gated** ("no personal use," paused to new partners; `routes/trainingpeaks.py` is outbound-only) — an external-credential blocker, not a coding task.
- **Zwift inbound is deliberately not-built** (arrives via Strava/FIT; only outbound `.zwo` export exists).

So Track A had no buildable work; Track B is the substance of Phase 5.

## 2. Today's automatic merge (what a pin overrides)

- **Wellness** (`canonical_wellness._coalesce`, `canonical_wellness.py:39`): per-metric **freshest-timestamp-wins**, tie-break on `_WELLNESS_SOURCE_PRIORITY` (garmin>whoop>oura>polar>coros).
- **Cardio** (`routes/garmin.materialize_canonical_activity`, `:812`): **most-complete copy wins** (weighted completeness score), tie-break on `_SOURCE_ORDER` (garmin>wahoo>polar>coros>rwgps>strava); per-field gap-fill + provenance.

In both, the static source order is only a **tiebreaker** today — so a useful user precedence must override the *primary* pick, not just the tiebreaker.

## 3. Ratified decisions (Andy 2026-06-29)

1. **Hard pin.** A user-pinned source **wins when it has a value/copy**; otherwise fall through to the automatic merge.
2. **Fallback unified on "most complete" for BOTH domains.** When no pin applies, both wellness and cardio use the most-complete merge. **This changes wellness's default** from freshest-timestamp-wins to a cardio-style completeness-primary + per-metric gap-fill.
3. **Single provider pin per domain.** One preferred provider for `wellness`, one for `cardio` — *not* per-metric or per-field. (Per-metric / per-field pins explicitly deferred — "consider later.")

## 4. Model

`user_source_preferences(user_id, domain, preferred_provider)`, PK `(user_id, domain)` → at most one pin per domain. Absence of a row = "no pin → automatic merge." Valid providers per domain mirror the merge layers' own source lists (wellness = `_WELLNESS_SOURCE_PRIORITY`; cardio = `_PROVIDER_ID_COLUMNS`).

**Resolution per domain:**
- **Wellness** (per metric, at the `(user,date)` grain): if a wellness pin is set and the pinned provider has a non-null value for that metric → use it; else most-complete (the source whose daily record carries the most tracked metrics is primary, then per-metric gap-fill).
- **Cardio** (per cluster): if a cardio pin is set and a copy from the pinned provider is in the cluster → that copy is primary; else most-complete as today.

## 5. Cross-layer cache implication (Trigger #3)

The wellness coalesce output feeds `integration_bundle_hash` → the 3A cache key (Phase 2 Slice 2.3). Two consequences:
- **Switching wellness from freshest → most-complete (decision 2) re-coalesces values** for every multi-source day → a one-time 3A cache shift on first run after B2 ships.
- **A pin set/change/clear re-coalesces that user's wellness** → must **re-materialize `canonical_daily_wellness` for the user and evict their 3A caches** (and re-materialize affected `canonical_activity` clusters for a cardio pin). The merge must stay deterministic so the cache key is stable across resumable passes.

## 6. Slice plan (each ≤ 5 substantive files; cross-layer change isolated)

- **B1 — substrate + repo (THIS slice; behavior-inert).** `user_source_preferences` table (`init_db._PG_MIGRATIONS`, public-schema → auto-applies, no Neon apply owed) + `source_preferences_repo.py` (`get`/`set`/`clear`, domain+provider validation, Rule #15 logging) + test. **Nothing reads it yet** → no behavior or cache change. Mirrors Phase 2 Slice 2.1's substrate-first pattern.
- **B2 — wellness coalesce + pin (cross-layer / cache).** Rewrite `canonical_wellness` coalesce to most-complete + read the wellness pin; re-materialize + evict 3A on pin change; tests pin the new merge + the cache eviction.
- **B3 — cardio merge + pin.** Thread the cardio pin into `materialize_canonical_activity`; re-materialize affected clusters on pin change; tests.
- **B4 — picker UI.** A two-dropdown source-precedence picker (wellness provider / cardio provider) on the connections/settings surface → `set`/`clear` + trigger the B2/B3 re-materialize+evict. Coaching-voice copy.

## 7. Open items
- **B2 "most complete" for wellness scalars** = pick the source whose *daily record* is most complete as primary, then per-metric gap-fill (the faithful cardio-port). Confirm at B2 build if a simpler per-metric "whoever has it, priority tiebreak" is preferred.
- **Re-materialize scope on pin change** — whole-history vs recent-window for wellness; all clusters vs recent for cardio. Decide at B2/B3 (bounded by what the 3A/feed consumers actually read).

## 8. Gut check
Real power-user value, but thin for a single-primary-device athlete today — the automatic merge already does the sensible thing. Worth building as the remaining Phase-5 substance, but B2's cross-layer cache touch is the only risky part; B1 (this slice) is inert foundation. Argument against the whole track: defer until there are users with genuinely competing sources, and spend sessions on the Phase-4 LIVE-VERIFY or another epic instead.
