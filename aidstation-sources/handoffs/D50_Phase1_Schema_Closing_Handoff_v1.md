# D-50 Phase 1 Schema Closing Handoff — `init_db.py` provider-integration tables shipped

**Session:** First production-code session after the L3-Spec-Trio + 3B-Spec design wave. First catchup pass under Andy's "push to production as we go" rule (CLAUDE.md §Operating context, captured 2026-05-14).
**Date:** 2026-05-14
**Predecessor handoff:** `3B_Spec_Closing_Handoff_v1.md`
**Status:** ✅ Schema-only PR shipped (D-50 schema half). Per-provider route wiring deferred to a follow-up D-50 PR.
**Time-on-task:** Single chat. Substantive files touched: 3 (`init_db.py`, `DATABASE.md`, `Project_Backlog_v14.md`). Close-out file (this handoff) is book-keeping. Well under the 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

Verified `3B_Spec_Closing_Handoff_v1.md`'s claimed file updates against on-disk state before any new work.

| File | Anchor checked | Result |
|---|---|---|
| `Layer3_3B_Spec.md` | 14 H2 sections; `llm_layer3b_goal_timeline_viability` signature; §6 decisions A/B/C/D present; §13 8 test scenarios | ✅ |
| `CLAUDE.md` | Rule #13 present at ~line 101; §Operating context with selective-rebuild + strangler-fig + push-to-prod rule; §Stack rewritten for Flask + Vercel + TrueNAS + Neon | ✅ |
| `Project_Backlog_v13.md` | v13 header; Rule #13 noted; Session 3B-Spec block at line 282 | ✅ |
| `Control_Spec_v7.md` | v7 header; §9 doc map; per-node Layer 3 split | ✅ |

No drift. CLAUDE.md read fully per Rule #13.

---

## 2. Andy's directive

Per chat 2026-05-14: D-50 and onboarding catchup. After surfacing that `Athlete_Onboarding_Data_Spec_v4.md` §"What changed in v4 vs v3" itself flags §A flow / §B locales / §G schedule / §J equipment as out of scope pending the D-58–D-61 design wave (lines 19–25 of v4), Andy chose:

- **Onboarding path:** D-50 only this session; D-58–D-61 design wave next.
- **D-50 scope:** split — schema-only PR first; per-provider wiring next.

Onboarding rationale: v4-vs-v3 deltas were spec-only corrections (pregnancy never captured; shooting/fencing technical readiness removed). A grep of `init_db.py`, `routes/profile.py`, and `templates/profile/*.html` found **no references to those fields in v1 code**, so there's nothing to surgically patch from v4 deltas. The bigger v1→v2 onboarding gap is a much larger UX rebuild, but v4 itself says §A / §B / §G / §J restructure when D-58–D-61 land — building any of that against v4 now means rebuilding it again. Defer.

---

## 3. Files shipped this session

| # | File | Change | Notes |
|---|---|---|---|
| 1 | `init_db.py` | +~170 lines | New tables appended to both `_SQLITE_MIGRATIONS` and `_PG_MIGRATIONS` lists. Each list's block is labeled `# D-50 Phase 1 — provider integration tables.` The SQLite block uses `INTEGER PRIMARY KEY AUTOINCREMENT` / `TEXT DEFAULT (datetime('now'))` / `INTEGER` for BIGINT and BOOLEAN; the PG block uses `SERIAL` / `TIMESTAMP DEFAULT NOW()` / `BIGINT` / `BOOLEAN`. Partial indexes (`WHERE status IN (...)` for `provider_auth_status_idx`; `WHERE processed_at IS NULL` for `idx_webhook_events_pending`) work in both backends. |
| 2 | `DATABASE.md` | +~85 lines | New `### Provider integrations` section between Garmin and Shared catalogs. Documents `provider_auth`, `webhook_events`, the four `polar_*`, `wahoo_plans`, the three `coros_*`, and the foreign-id ALTER columns on `cardio_log` / `training_log`. Garmin-paused context noted (D-55). |
| 3 | `Project_Backlog_v14.md` | new file | v13 carried forward; v14 header; D-50 row updated to 🟡 Partial — schema ✅ / wiring pending; session block. |
| 4 | `handoffs/D50_Phase1_Schema_Closing_Handoff_v1.md` | new file | This file. |

**Files explicitly NOT touched:**
- `PROVIDERS_SCHEMA.md` — v12 reconciliation already documented `session_blob` (lines 187–188 of the live file). No edit needed.
- `Athlete_Data_Integration_Spec_v3.md` — input contract for this session's implementation. Specs don't get edited from implementation rounds.
- `CLAUDE.md` — operating context unchanged.
- `Control_Spec_v7.md` — doc-map sync is bundled with the Layer 3C/3D ship per 3B handoff §6.2; not a single-table-batch concern.
- The provider route files (`routes/coros.py`, `routes/ride_with_gps.py`, `routes/polar.py`, …) — Andy explicitly chose schema-only first; wiring is the next PR.

---

## 4. What landed in `init_db.py`

### 4.1 Generic tables (per Integration v3 §4)

- **`provider_auth`** — 14 columns including `session_blob TEXT` (for Garmin's `garth` session JSON post-rebuild). UNIQUE `(user_id, provider)`. Partial index `provider_auth_status_idx ON (status) WHERE status IN ('error', 'pending_backfill')` for error/backfill scans.
- **`webhook_events`** — 11 columns. Lookup index on `(provider, provider_user_id, entity_id, event_type)`. Partial pending index `ON (received_at) WHERE processed_at IS NULL`. `payload` is TEXT not JSONB per spec §4.2 portability note. `user_id` nullable for pending dispatch resolution.

### 4.2 Per-provider tables (per Integration v3 §5)

- **Polar (4 tables):** `polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, `polar_continuous_hr_samples`. UNIQUE constraints per spec. `polar_continuous_hr_samples` also gets `idx_polar_hr_user_time ON (user_id, timestamp_ms)`.
- **Wahoo (1 table):** `wahoo_plans` (outbound push log). Index on `plan_item_id`. Inbound Wahoo activities flow into `cardio_log.wahoo_workout_id` (no separate inbound table per spec §5.2).
- **COROS (3 tables):** `coros_daily_summary`, `coros_hrv_samples`, `coros_plans`. UNIQUEs per spec. `coros_plans` indexed on `plan_item_id`.

### 4.3 Foreign-id columns on existing tables (per Integration v3 §6)

- `cardio_log` — `polar_exercise_id`, `wahoo_workout_id`, `coros_label_id`, `rwgps_trip_id`.
- `training_log` — `polar_exercise_id`, `wahoo_workout_id`, `coros_label_id`.
- `strava_activity_id` on `cardio_log` — deferred per spec §6 until Strava integration design lands (D-48).

### 4.4 Garmin (per Integration v3 §5.4)

No new per-provider table. Existing `garmin_workouts` + `wellness_log` schemas remain as deployment targets. `garmin_auth` legacy table untouched (D-55 paused; the `garmin_auth → provider_auth` cleanup waits for Garmin API reopening).

---

## 5. Session-end verification (Rule #10)

Ran `init_sqlite()` from a fresh `rm -f /tmp/test_d50.db`:

```
D-50 tables (10): ['coros_daily_summary', 'coros_hrv_samples', 'coros_plans',
                   'polar_cardio_load', 'polar_continuous_hr_samples',
                   'polar_nightly_recharge', 'polar_sleep', 'provider_auth',
                   'wahoo_plans', 'webhook_events']
cardio_log new cols:   ['coros_label_id', 'polar_exercise_id', 'rwgps_trip_id', 'wahoo_workout_id']
training_log new cols: ['coros_label_id', 'polar_exercise_id', 'wahoo_workout_id']
provider_auth cols (14): id, user_id, provider, access_token, refresh_token,
                          token_expires_at, session_blob, provider_user_id,
                          scopes, webhook_token, status, registered_at,
                          created_at, updated_at
webhook_events cols (11): id, provider, event_type, provider_user_id, entity_id,
                           user_id, payload, signature_ok, received_at,
                           processed_at, error
D-50 indexes (6): idx_coros_plans_plan_item, idx_polar_hr_user_time,
                  idx_wahoo_plans_plan_item, idx_webhook_events_lookup,
                  idx_webhook_events_pending, provider_auth_status_idx
```

Re-run with the file present completed without errors — migration loop's try/except + `IF NOT EXISTS` make every statement idempotent.

**PG path not exercised locally** (would require a Neon connection). The PG migration list mirrors the SQLite block's structure with standard type swaps. The existing PG-migration precedent (`wellness_self_report` deployed under exactly this pattern) is the strongest evidence the new block will apply on `init_postgres()` cold-start. **Recommend:** confirm in the deploy-monitoring step that no `_PG_MIGRATIONS` exceptions show up after merge.

---

## 6. Mechanically-applicable instructions for next session (Rule #11)

### 6.1 Forward move: D-58–D-61 onboarding design wave

**Per 3B handoff §7:** "[The D-58–D-61 wave is] worth scoping as a single design wave rather than four isolated sessions, since the items interact heavily — account-first flow feeds Google Maps location flow feeds gear-from-proximity feeds session-unbinding." That recommendation stands.

**Pre-step reads (Rule #13 ordering):**
1. **`aidstation-sources/CLAUDE.md` fully** (Rule #13 — first re-read, always)
2. `aidstation-sources/Project_Backlog_v14.md` (this file's predecessor file)
3. `aidstation-sources/handoffs/D50_Phase1_Schema_Closing_Handoff_v1.md` (this file)
4. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` — for the §A / §B / §G / §J / §K + Account Config 1 sections that the design wave restructures
5. `aidstation-sources/Athlete_Data_Integration_Spec_v3.md` §7 (field mapping) + §8 (two-regime consumer model) — D-58 prefill logic builds on §7
6. Backlog rows D-58, D-59, D-60, D-61 — the four design tracks

**Open questions the design wave must resolve:**
- **D-58:** per-field prefill priority across providers (when Polar + COROS both offer RHR, which wins?); UI flow ordering (provider-connection step before §A self-report — what happens if athlete skips?); confirm-or-edit affordance for prefilled values.
- **D-59:** Google Maps Places API auth + quota + billing model; chain detection logic; nearby-instance discovery radius; opt-in UX for adding multiple chain instances; stale Places data / rebrand handling.
- **D-60:** locale-category default equipment manifests (chain gym / hotel gym / home gym / climbing gym / pool / etc.); confidence model for plan-gen on inferred equipment; override UI design.
- **D-61:** schedule field migration §J.5 → §G; session→locale assignment logic for plan-gen; hard-constraint semantics (max session duration as equipment/safety rather than scheduling).

**Output target:** `Onboarding_Design_Wave_v1.md` (name TBD) capturing decisions across all four D-rows + `Athlete_Onboarding_Data_Spec_v5.md` rewriting §A / §B / §G / §J / §K + Account Config 1.

### 6.2 Parallel / follow-on: D-50 route wiring

Independent of the onboarding design wave. Strangler-fig roll-in:

1. **Helper module.** Build `provider_auth.py` (or a function set inside an existing module) for UPSERT by `(user_id, provider)`, status transitions (active / revoked / error / pending_backfill / migrating), token refresh helpers, and webhook_token rotation (Pattern A per Integration v3 §4.1 — UPSERT every event).
2. **Migrate shipped providers first.** COROS (`routes/coros.py`) and RWGPS (`routes/ride_with_gps.py`) — the two that already work — switch from whatever they do today to writing through `provider_auth` / `webhook_events`. Behavior unchanged; storage path changes.
3. **Wire stubbed providers.** As Polar, Wahoo, Strava, Whoop, Zwift, TrainingPeaks ship real OAuth flows (HANDOFF-2026-05-13-stub-batch.md tracks the stubs), each one lands directly on `provider_auth` — no detour through provider-specific auth tables.
4. **Webhook handlers.** Each `/<slug>/webhook` route writes a row into `webhook_events` (signature_ok set; user_id resolved by `provider_user_id` → `provider_auth.user_id` join; processed_at = NOW() on success). Failed signatures get a row with `signature_ok = FALSE` for audit but no dispatch (per spec §4.2).
5. **Garmin (D-55, paused).** When Garmin reopens, rebuild `routes/garmin.py` + `garmin_connect.py` against `provider_auth.session_blob`. Drop the legacy `garmin_auth` table afterward (no production data per FC-2026-05-14 confirmation).

**Recommend** the wiring be split across 2–3 PRs to stay under the 5-file ceiling: PR1 = helper + COROS migration; PR2 = RWGPS migration + webhook_events dispatch scaffold; PR3 = stub-provider wiring as each one's OAuth code ships.

### 6.3 After Layer 3 spec writing is fully complete (3C + 3D)

3B handoff §6.3's "first piece of code" recommendation — a Layer 3A endpoint consuming v1 athlete data — still stands. This session's D-50 schema work doesn't fulfill that; it's the integration plumbing, not the LLM-pipeline implementation. Once 3C + 3D specs ship and the design wave settles onboarding, building a 3A endpoint is the smallest meaningful pipeline cut.

---

## 7. Forward pointers

- **Next session:** D-58–D-61 onboarding design wave per §6.1 above.
- **In parallel / shortly after:** D-50 route wiring per §6.2 (when ready — independent of the design wave).
- **After both:** Layer 3C+3D spec session per 3B handoff §6.1.
- **After Layer 3 specs complete:** Layer 3A endpoint code per 3B handoff §6.3.
- **D-54 SQLite collapse:** still queued; Catalog Migration Phase 5. The dual-backend pattern stays intact for now.
- **D-55 Garmin rebuild:** paused until Garmin API access reopens.

**Rules in force, unchanged:**
- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits
- #12 numeric version suffixes
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §6.1 lists CLAUDE.md as step 1**

---

## 8. Gut check

**What this session got right.**

- **Caught the onboarding-spec-itself-flagging trap before any onboarding code.** v4 spec lines 19–25 explicitly mark §A / §B / §G / §J as out of scope pending D-58–D-61. Building against v4 now means rebuilding after the design wave. Surfacing this to Andy as the stop-and-ask point — rather than just executing "do D-50 and onboarding" literally — meant the catchup pass actually delivered work that won't get redone.
- **Schema-only first.** Splitting D-50 into schema + wiring keeps the blast radius minimal. Three substantive files this session (init_db, DATABASE.md, backlog) is well under the ceiling. Wiring lands as a separate review-able PR with its own scope.
- **Mirrored Integration v3 spec verbatim where possible.** Column lists, UNIQUE constraints, partial indexes — all match the spec block exactly. The two intentional translations (SQLite ↔ PG type swaps; following the migration-list pattern rather than touching the frozen SCHEMA strings) are documented in this handoff §4 and in the inline `init_db.py` comment.
- **Verified locally before declaring done.** Idempotent re-run confirms the migration loop doesn't trip on the new statements. Caught a few potential gotchas (SQLite partial index syntax; BIGINT → INTEGER for SQLite; BOOLEAN → INTEGER for SQLite) before they hit deploy.

**Risks.**

- **PG path not exercised locally.** The PG migrations should apply cleanly based on syntax-level mirroring with successful precedents (`wellness_self_report` deployed under the same pattern), but no `init_postgres()` run was performed. Monitor the deploy logs after merge — `_PG_MIGRATIONS` exceptions get rolled back silently per the loop's try/except, so a malformed statement would fail without any other symptom until something queried a missing table.
- **`session_blob` column will sit empty until Garmin reopens.** Architecturally clean; operationally just dead weight on every row of `provider_auth` for non-Garmin providers. Cost is negligible (one NULL TEXT column); design decision per Integration v3 §2.3.
- **Schema is deployed but no consumers yet.** The 10 tables + 7 ALTER columns are reachable from `init_db.py`'s migration loop only. No route writes into them, no query reads from them. If the next implementation session drifts off-plan (e.g., wires a provider into an ad-hoc table instead of `provider_auth`), the work here becomes dead weight. The mechanically-applicable steps in §6.2 are the protection.
- **Strava and Whoop deferred at spec level (Integration v3 §5.5 "TBD"; backlog D-48).** Schema here covers Polar/Wahoo/COROS only. When Strava/Whoop ship, the spec needs to firm up their per-provider table shapes (or confirm `cardio_log.strava_activity_id` is enough for Strava). Not a today-problem; flagged so it doesn't get forgotten.
- **Test coverage is zero.** No unit tests added for the new tables. The v1 codebase doesn't have a test suite to extend, so this matches the existing pattern, but it means correctness depends on the spec mirror being faithful. If a column is wrong, we'll find out when a webhook hits it in production.

**What might be missing.**

- **No `provider_auth` row for Andy yet on deploy.** The migration creates the table empty. The first real user data lands when a provider OAuth flow writes through it. Andy's existing COROS / RWGPS connections (pre-D-50, via whatever code path they currently use) won't be visible in `provider_auth` until the wiring PR migrates them. Worth noting at deploy time so we don't expect to see his rows appear without the wiring.
- **No webhook_events retention strategy implemented.** Spec §4.2 recommends a daily cron pruning `processed_at IS NOT NULL AND received_at < NOW() - INTERVAL '90 days'`. Not in scope for schema-only; needs to be tracked. Adding as an in-line note to the wiring PR or as a follow-on backlog row would catch it.
- **No `garmin_auth → provider_auth` migration path documented in `init_db.py`.** Per Integration v3 §2.3 + D-55, when Garmin reopens we drop `garmin_auth` entirely and rebuild on `provider_auth.session_blob`. The mechanics of that drop (`DROP TABLE garmin_auth` in `_PG_MIGRATIONS` + remove all `garmin_auth` references from the SQLite schema string) aren't pre-staged. Probably fine — staging the drop now would create dead code in the file. But worth flagging so the eventual D-55 PR remembers the cleanup half.

**Best argument against this session's scope.**

You could argue catchup work was a distraction from the agreed forward sequence — 3B handoff §7's forward move was "combined Layer3_3C + 3D session", not D-50 schema. Counter: Andy explicitly chose D-50 (and reframed onboarding) when asked, and the "push to production as we go" rule he added 2026-05-14 says preferring shipping working v2 code into v1 over accumulating more design. Schema-only is the smallest possible D-50 increment — it doesn't violate the rule; it executes it.

Alternatively, you could argue the schema should be PG-only (per Integration v3 §2.5) — adding SQLite migrations is investment in a backend D-54 will collapse. Counter: D-54 collapse is Catalog-Migration-Plan Phase 5, which is several sessions away. Until then the dual-backend pattern is alive; local dev uses SQLite; new tables that don't work locally would break the dev experience for the next several sessions. The marginal cost of SQLite-mirroring is ~50 lines that get deleted in Phase 5 anyway.

---

*End of D-50 Phase 1 Schema closing handoff.*
