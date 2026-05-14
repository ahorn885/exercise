# D-50 Review + Onboarding Design Wave (D-59 + D-60) Closing Handoff

**Session:** Review-and-design pass following the D-50 Phase 1 schema ship. Three pieces: (1) Rule #9 / Rule #10 audit of `D50_Phase1_Schema_Closing_Handoff_v1.md`; (2) Option-A ratification of the SQLite-freeze override surfaced by the review; (3) first two of four Onboarding Design Wave tracks (D-59 place lookup + D-60 shared gym profiles).
**Date:** 2026-05-14
**Predecessor handoff:** `D50_Phase1_Schema_Closing_Handoff_v1.md`
**Branch:** `claude/review-aidstation-handoff-4aRtE`
**Status:** ✅ Review-and-cleanup complete; ✅ first two of four design-wave tracks shipped; 🟡 D-61 + D-58 design tracks pending.
**Time-on-task:** Single chat across multiple turns. Substantive files shipped: **5** (review, integration v4, backlog v15, D-59 design, D-60 design) — at the 5-file ceiling. This handoff itself is book-keeping.

---

## 1. Session-start verification (Rule #9)

Verified the D-50 Phase 1 closing handoff's claimed file updates against on-disk state before composing the review. Method: anchor checks on each claimed table column, every UNIQUE / index, each ALTER, plus the migration-list block markers; spec-mirror cross-read against `Athlete_Data_Integration_Spec_v3.md` §4–§6.

| Claim | Result |
|---|---|
| `init_db.py` — 10 new tables, 7 ALTER columns, 6 D-50 indexes in both `_SQLITE_MIGRATIONS` and `_PG_MIGRATIONS` | ✅ Verified (PG block + SQLite block both present; column lists match spec verbatim) |
| `DATABASE.md` — new `### Provider integrations` section between Garmin and Shared catalogs | ✅ Verified at repo-root `/DATABASE.md` (handoff did not prefix path; ambiguous between root and `aidstation-sources/DATABASE.md` — flagged as Finding #3 in the review) |
| `Project_Backlog_v14.md` — v13 carried forward; D-50 row updated to 🟡 Partial — schema ✅ / wiring pending | ✅ Verified |
| Idempotent re-run of `init_sqlite()` | ✅ Verified — re-runs without error per the handoff's §5 |

**Findings logged in `D50_Phase1_Schema_Review_v1.md`:**

1. **SQLite migrations shipped despite a locked freeze** (most important). Spec v3 §2.5 + Backlog D-54 explicitly say `_SQLITE_MIGRATIONS` is frozen, no new entries. The ship added 147 lines + 7 ALTERs. Handoff §8 acknowledged the override as "best argument against this session's scope" and overrode unilaterally. Per CLAUDE.md stop-and-ask triggers #5 and #8, this should have been Andy's call.
2. `init_db.py` line count under-stated — handoff said "+~170 lines"; actual was +293.
3. `DATABASE.md` path ambiguous (root vs. `aidstation-sources/`).
4. PG path not exercised locally; failure mode is silent (migration loop's `try/except` swallows malformed statements).

Spec mirror itself was **faithful** — every column, UNIQUE, index, and ALTER matched Integration v3 §4–§6 verbatim. The shipped schema is correct; the review concerns process discipline, not data.

---

## 2. Andy's directives

Three decisions reshaped the session:

1. **Option A on the SQLite-freeze override** (after review): "we should be developing on the Neon PG database. I don't want to waste effort on something we won't use, but I also don't know what needs to be kept in sync so the eventual final swap works properly." Runtime audit clarified the answer: **nothing on the schema side needs to stay in sync.** `init_sqlite()` only fires when `DATABASE_URL` is unset; Andy's dev path against Neon makes the SQLite block inert. The 147 sunk-cost lines age out at the D-54 PG-only collapse. Ratified retroactively; freeze remains in force going forward.

2. **"Do both" wiring + design wave** (after I proposed wiring first). When I read `routes/coros.py` to scope wiring, I surfaced that COROS is a **19-line Phase-0 webhook stub** — not the "shipped working integration" the D-50 handoff §6.2 framed it as. The same applies to RWGPS, Strava, Whoop, TrainingPeaks, Zwift. None of the "shipped providers" have OAuth or token storage to migrate; they're stubs that ack 200. The wiring track is **blocked by D-58's UX decisions** (OAuth-first vs. self-report-first dictates where the connect button lives, which dictates route shape). Andy pivoted to design-wave-only this session.

3. **Design-wave sequencing** (Andy chose all three recommendations): D-59 first (most foundational); per-row design doc + single spec v5 (smaller per-turn commits); one track per turn.

---

## 3. Files shipped this session

All on branch `claude/review-aidstation-handoff-4aRtE`. Each commit pushed individually.

| # | File | Type | Commit | Notes |
|---|---|---|---|---|
| 1 | `aidstation-sources/handoffs/D50_Phase1_Schema_Review_v1.md` | New | `f52f0e5` | Rule #9 audit of the D-50 Phase 1 ship; four findings; Option A/B/C presented for resolution. |
| 2 | `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` | New (bump from v3) | `43740e9` | v4 = v3 + §2.5 carve-out paragraph ratifying the D-50 SQLite block as a one-time documented exception. v4 is byte-identical to v3 outside §2.5 + the v4-vs-v3 changelog block. |
| 3 | `aidstation-sources/Project_Backlog_v15.md` | New (bump from v14) | `43740e9` | D-54 row updated to cite the v4 §2.5 carve-out. New row D-62 added for the `webhook_events` 90d retention prune (flagged in D-50 handoff §8 but never tracked as a real backlog row). |
| 4 | `aidstation-sources/Onboarding_D59_Design_v1.md` | New | `87668a1` | First of four design-wave docs. Locks: Mapbox Geocoding (Andy chose over Google), hybrid registry chain detection, 42.2 km nearby-instance radius (matches §J proximity), on-demand refresh, manual fallback as first-class path, inline Mapbox privacy disclosure → Account Config 3 acknowledgment, new `chain_registry.py` application module, 8 columns documented for `locale_profiles` (not yet migrated — that's the v5 implementation PR's job). |
| 5 | `aidstation-sources/Onboarding_D60_Design_v1.md` | New | `eeee9ef` | Second of four design-wave docs. **Reframed entirely per Andy's "no inferences" reply.** Originally backlog D-60 asked for category-default equipment manifests; Andy rejected the premise. Rebuilt around per-physical-address **shared gym profiles, crowd-sourced** across enterprise users. First athlete at a `mapbox_id` builds; subsequent athletes inherit + per-athlete override. New tables: `gym_profiles`, `locale_equipment_overrides`, `locale_toggle_overrides` (all PG-only per the §2.5 freeze). 10-category flat taxonomy with `partner_home` → `other_residence` rename. Last-Writer-Wins on shared updates, with `disputed` flag. §J.3 toggles same shared model. |
| — | `aidstation-sources/handoffs/D50_Review_and_Onboarding_Wave_D59_D60_Closing_Handoff_v1.md` | New (this file) | (this commit) | Book-keeping. |

**Files explicitly NOT touched:**

- `aidstation-sources/CLAUDE.md` — pointers in "Authoritative current files" section are stale (says Control_Spec_v6, Backlog v11, Integration v2; current are v7, v15, v4). Pointer refresh is admin work that fits inside the ceiling; chose to defer to next session's housekeeping pass rather than push past 5 substantive files this session.
- `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` — the v5 spec rewrite consolidates all four design wave decisions; v5 lands after D-61 + D-58 design docs settle. Don't bump in pieces.
- `init_db.py` — D-60 schema additions are documented in the design doc; the actual migration lands as part of the v5 onboarding implementation PR, not now. Per the per-row-design-doc + single-spec-v5 model.
- `Athlete_Data_Integration_Spec_v4.md` further updates — §2.5 was the only v4 change; v5 will integrate the design wave outputs.
- `routes/locales.py`, `routes/profile.py` — v1 code untouched. Design wave is pure v2-spec work; no v1 implementation in scope.

---

## 4. What landed — by piece

### 4.1 D-50 review (Finding #1 resolution = Option A)

The review found four issues but the only one requiring an Andy decision was the SQLite-freeze override. Andy's grounded question — "what needs to be kept in sync so the eventual final swap works properly?" — got a clean answer from a runtime audit of `init_db.py:2289` + `database.py:88` + `app.py:52`:

- `init_sqlite()` only fires when `DATABASE_URL` is unset.
- Andy's dev path runs against Neon (`DATABASE_URL` set), so the SQLite block never executes against any database he touches.
- The eventual D-54 PG-only collapse deletes `_SQLITE_MIGRATIONS` + `init_sqlite()` + the SQLite branches in `database.py` + the dual-type docs in DATABASE.md as one unit. No schema state needs to be "kept in sync" because the SQLite path is not actively used.

The 147 SQLite-block lines are sunk cost with zero operational impact; ripping them out now is a separate PR with no benefit. **Ratified retroactively; freeze remains in force.** Captured in `Athlete_Data_Integration_Spec_v4` §2.5 + `Project_Backlog_v15` D-54.

The other three findings (line-count under-statement, DATABASE.md path ambiguity, PG-path-not-exercised) are factual and noted for next-session attention; none require code changes.

### 4.2 Webhook-events retention prune as a real backlog row (D-62)

D-50 handoff §8 "What might be missing" flagged the retention prune as a future concern. Spec v3/v4 §4.2 calls for daily prune of `processed_at IS NOT NULL AND received_at < NOW() - INTERVAL '90 days'`. That's now tracked as D-62 in Backlog v15 — cron host TBD (Vercel cron vs. TrueNAS scheduled task vs. in-app scheduler); recommended hard-delete (the dispatched-side row's data lives in per-provider tables already); the `processed_at IS NULL` dead-letter case is out of scope for the prune and needs separate dead-letter design.

### 4.3 D-59 design (Onboarding_D59_Design_v1.md)

Locks **eight decisions** for the locale place-lookup + chain-detection feature:

1. **Mapbox Geocoding** (Andy's call, not the recommendation) — generous free tier, weaker brand metadata compensated by heavier registry.
2. **Hybrid chain detection** — registry primary, API backup.
3. **42.2 km nearby-instance radius** (same as §J proximity).
4. **On-demand refresh only** — athlete-triggered.
5. **Manual address fallback** always available; first-class path with same schema shape.
6. **Inline Mapbox privacy disclosure** at first place lookup; acknowledgment stored in Account Config 3.
7. **`chain_registry.py` Python module** for the chain list (not a Layer 0 table; rebrand-cadence updates ship in code).
8. **~30-entry initial seed list** drafted as a follow-on PR; this doc commits to the shape, not the specific entries.

Schema additions documented for `locale_profiles`: `mapbox_id`, `lat`, `lng`, `chain_id`, `chain_name`, `category`, `manual_entry`, `place_payload`, `place_fetched_at`. Migration is part of the v5 implementation PR, not this design doc.

Hands off `chain_id` + `category` to D-60; `lat` / `lng` to D-61. No interaction with D-58.

### 4.4 D-60 design (Onboarding_D60_Design_v1.md)

**Major reframe.** The original backlog row asked for category-default and chain-default equipment manifests. Andy rejected the premise: "no inferences" + "user has to build a profile for the gym or accept an existing profile" + "gym profiles (per address, not per chain) should be a shared entity across all enterprise users."

The doc rebuilds D-60 around **per-physical-address shared gym profiles, crowd-sourced**:

- First athlete at a given `mapbox_id` (or `address_fingerprint` for manual-entry rows) builds the profile.
- Subsequent athletes at the same address inherit it on confirmation; their personal view is `shared_profile + locale_equipment_overrides`.
- Last-Writer-Wins on shared updates (athlete clicks "submit my equipment list as a correction"); provenance display ("last confirmed on YYYY-MM-DD by another athlete") + `disputed` flag for conflicts.
- §J.3 sport-specific gear toggles live in the same shared model.
- Default-on contribution model; account-level opt-out for private contributions; home gyms, outdoor parks, and other-residence locales are inherently private (no shared profile, no `gym_profile_id` FK).

10-category flat taxonomy locked: `commercial_chain_gym` / `independent_gym` / `hotel_gym` / `home_gym` / `climbing_gym_chain` / `climbing_gym_indie` / `pool_indoor` / `pool_outdoor` / `outdoor_park` / `other_residence` (renamed from `partner_home` per Andy 2026-05-14).

Schema additions documented:
- New table `gym_profiles` (id, mapbox_id UNIQUE, address_fingerprint, display_name, category, equipment JSON, toggles JSON, disputed_items JSON, private BOOLEAN, created_by_user_id, last_confirmed_by, last_confirmed_at, contribution_count).
- New table `locale_equipment_overrides` ((user_id, locale_id, equipment_tag, action) UNIQUE).
- New table `locale_toggle_overrides` ((user_id, locale_id, toggle_name) UNIQUE).
- Columns on `locale_profiles`: `gym_profile_id`, `sharing_opt_out`.

All PG-only per the freeze. Migration is athlete-driven (existing `locale_equipment` rows coexist; opt-in re-anchor per locale).

Hands off effective-equipment-view contract to D-61 (for "qualifying locale by equipment" assignment). No interaction with D-58.

---

## 5. Session-end verification (Rule #10)

| Claim | Anchor | Result |
|---|---|---|
| Integration v4 §2.5 has the D-50 carve-out paragraph | `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` §2.5 starts with the v3 freeze text, then adds the "Documented exception (v4, 2026-05-14)" block with three bullets | ✅ Verified |
| Backlog v15 has updated D-54 + new D-62 | `aidstation-sources/Project_Backlog_v15.md` D-54 row carries the "2026-05-14 update" with carve-out reference; D-62 row exists after D-61 | ✅ Verified |
| D-59 design has 8 decisions in §2 | `aidstation-sources/Onboarding_D59_Design_v1.md` §2 table has 8 rows | ✅ Verified |
| D-60 design has 9 decisions in §2 | `aidstation-sources/Onboarding_D60_Design_v1.md` §2 table has 9 rows | ✅ Verified |
| All commits pushed to `claude/review-aidstation-handoff-4aRtE` | `git log origin/...` matches HEAD | ✅ Verified pre-handoff-commit |

No spec content was edited outside the bounded §2.5 carve-out (v4 vs. v3); no design-doc text drift from the in-chat decisions table.

---

## 6. Mechanically-applicable instructions for next session (Rule #11)

### 6.1 Forward move — D-61 design (Onboarding Design Wave 3/4)

**Pre-step reads (Rule #13 ordering):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read. **Note: stale pointers** in "Authoritative current files" — actual currents are `Control_Spec_v7.md`, `Project_Backlog_v15.md`, `Athlete_Data_Integration_Spec_v4.md`, `Athlete_Onboarding_Data_Spec_v4.md`. A pointer refresh is the right opening admin pass for the next session.
2. `aidstation-sources/Project_Backlog_v15.md` — D-61 row + cross-cutting context.
3. `aidstation-sources/handoffs/D50_Review_and_Onboarding_Wave_D59_D60_Closing_Handoff_v1.md` (this file).
4. `aidstation-sources/handoffs/D50_Phase1_Schema_Review_v1.md` — context on the four findings + Option A ratification.
5. `aidstation-sources/Onboarding_D59_Design_v1.md` + `Onboarding_D60_Design_v1.md` — input contracts. D-61 reads `locale_profiles.lat` / `.lng` (from D-59) + the per-athlete effective-equipment-view (from D-60).
6. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` §G (Schedule & Availability, lines 554–574) — the existing weekly fields D-61 either consolidates or restructures.
7. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` §J.5 (Locale Capacity Metrics, lines 749–755) — the locale-level time fields D-61 moves to plan level.
8. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` §K (Locale Schedule, lines 758–814) — the overlay model that interacts with per-session locale assignment.

**Open questions to resolve with Andy in the next session (high-leverage four):**

1. **Per-day vs. weekly schedule granularity in §G.** Today §G has "Available Training Hours per Week" + "Typical Session Duration" + "Long Session Available" (Y/N + day + max duration). D-61 wants per-day windows ("Mon 7am 60min, Tue 6am 90min, Thu evening 75min, weekend longer"). Options:
   - (a) Replace §G entirely with a 7-day per-day schedule (~7 fields with optional times).
   - (b) Keep §G high-level + add a new §G.x for per-day plan windows.
   - (c) Hybrid — weekly summary fields + per-day override array.
2. **Session→locale assignment algorithm.** D-61 says "default to closest qualifying locale by equipment; allow athlete to swap per-session." Open: what's the tiebreaker order? Distance → equipment match → §J.5 max-session-duration → athlete preference?
3. **Max session duration semantics.** D-61 says max-session-duration stays at the locale "as equipment/safety constraint rather than scheduling constraint." Where does that field live in v5 — still on `locale_profiles` (per-athlete locale) or on `gym_profiles` (shared)? Argument for shared: pool-locale max-duration is a property of the pool (lap reservations, capacity). Argument for per-athlete: hotel-gym max-duration is athlete-context (the athlete's own scheduling, not the gym's).
4. **UX for per-session locale picking.** Plan-gen picks a locale per session. Does the athlete confirm the pick at plan-generation time (single bulk review), at session-start time (just-in-time), or both?

**Output target:** `aidstation-sources/Onboarding_D61_Design_v1.md`.

### 6.2 Following move — D-58 design (Onboarding Design Wave 4/4)

**Pre-step reads (in addition to §6.1 list):**

1. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` §A (Athlete Identity, lines 127–164) — fields D-58 wants to prefill.
2. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` Account Config 1 (Connected Services, lines 851–865) — existing structure.
3. `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` §7 (Field mapping — onboarding fields to data sources, lines 508–630). The authoritative per-field source list.
4. `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` §8 (Two-regime consumer model). D-58 OAuth-first reshapes both regimes.

**Open questions to resolve with Andy:**

1. **Provider-connection step placement.** Before §A (truly OAuth-first)? After §A.1 disclosures (consent first, then connect)? At a Step 0 "Welcome — connect your accounts" screen?
2. **Per-field prefill priority across providers.** When Polar + COROS both have RHR, which wins? (a) Explicit per-provider preference per field (Andy ranks once); (b) Most-recent-wins; (c) Weighted blend; (d) Athlete-picks per field at prefill.
3. **Prefilled field affordance.** Edit-in-place ("Body Weight: 78.2 kg [from Polar, 2 days ago]") or locked-with-explicit-override?
4. **"No providers connected" path.** Graceful degradation to v1-style self-report, or harder nudge to connect first?
5. **Re-onboarding after later provider connect.** If athlete onboards self-report-first, then connects providers later, does the system retroactively prefill (potentially overwriting their entries)? With what consent prompt?

**Output target:** `aidstation-sources/Onboarding_D58_Design_v1.md`.

### 6.3 After all four design tracks settle — v5 spec rewrite

**Output target:** `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md`. Consolidates all four design doc decisions into a single spec rewrite of §A / §B / §G / §J / §K + Account Config 1. Spec follows the same 14-section depth standard as Layer 2 specs where applicable; for §J and §G specifically, the design doc content is the authoritative reference and v5 quotes it verbatim where useful.

Plus pointer refresh of `aidstation-sources/CLAUDE.md`'s "Authoritative current files" section (admin).

### 6.4 D-50 wiring — paused

The original D-50 handoff §6.2 wiring plan assumed COROS and RWGPS were "shipped working providers" with auth state to migrate. They are not — they are 19/21-line Phase-0 webhook stubs. There is no migration; there is only **net-new OAuth-flow implementation** per provider.

The OAuth-flow UX is owned by D-58. Building any provider's real OAuth flow before D-58 decisions land risks rebuilding it. **D-50 wiring is functionally paused until D-58 ships.** Once D-58 lands:

1. Build `provider_auth.py` helper module (UPSERT by (user_id, provider), status transitions per Integration v4 §4.1, token-refresh skeleton, webhook_token rotation Pattern A). Provider-agnostic; can be built any time.
2. Pick one provider to ship a real OAuth flow against (probably COROS since CLAUDE.md flags it as next-to-ship). Implement OAuth callback exchange, token storage via `provider_auth.py`, token refresh.
3. Webhook handler change: each `/{slug}/webhook` route writes a row into `webhook_events` (signature_ok, payload, processed_at NULL → NOW() on dispatch).
4. Per-provider data ingestion (one provider at a time): wire webhook dispatch → per-provider table writes.

PR1 of wiring is no longer `provider_auth.py` helper + COROS migration — it's `provider_auth.py` helper + real COROS OAuth flow + COROS webhook recording. **Substantially bigger scope than the D-50 handoff originally framed.** Expect 2–4 sessions of implementation per provider, not a single session.

---

## 7. Forward pointers

- **Next session:** D-61 design (Onboarding Design Wave 3/4) per §6.1.
- **Following:** D-58 design (Onboarding Design Wave 4/4) per §6.2.
- **After both:** v5 onboarding spec rewrite consolidating all four design tracks; CLAUDE.md pointer refresh as the admin pass.
- **Paused / blocked:** D-50 wiring per §6.4. Unblocks when D-58 lands.
- **D-54 SQLite collapse:** still queued; Catalog Migration Phase 5. SQLite freeze remains in force per `Athlete_Data_Integration_Spec_v4` §2.5.
- **D-55 Garmin rebuild:** still paused until Garmin reopens API access.
- **D-62 webhook_events retention prune:** tracked; lands either alongside the first real webhook handler implementation or as its own ops PR.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits
- #12 numeric version suffixes
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §6.1 step 1 is CLAUDE.md.**

---

## 8. Gut check

**What this session got right.**

- **Caught a meaningful process gap before propagating it.** The D-50 Phase 1 schema correctness was real, but the SQLite-freeze override was a stop-and-ask trigger that got bypassed. Surfacing it through a review pass, getting Andy's grounded ratification, and reaffirming the freeze going forward turned a one-time process failure into reinforced discipline rather than silent drift. The carve-out paragraph in `Athlete_Data_Integration_Spec_v4` §2.5 is the durable artifact; future sessions that read v4 see the override + the rule, not just the rule.
- **Discovered wiring was blocked before sinking time into it.** Reading `routes/coros.py` and finding a 19-line stub instead of "shipped working integration" prevented hours of misdirected implementation work. The D-50 handoff's wiring framing was based on optimistic interpretation; the actual codebase state required a different plan.
- **Andy's "no inferences" reply on D-60 was a real fork; the design rebuilt around it.** Instead of compromising — "ok we'll have light category defaults with overrides" — the doc fully absorbed the reframe. The shared-gym-profile architecture is a more honest design for a multi-tenant SaaS product than the original category-default-manifest framing in the backlog row would have produced. Worth the design-time cost.
- **Sequential per-row design docs respect the spec-first discipline.** Each design doc is a single-decision-cluster artifact; spec v5 consolidates from settled inputs rather than reshaping under-decided ideas. Avoids the v3 → v4 surgical-amendment thrash and avoids the "design lives in handoff narrative" anti-pattern Rules #11 and #12 exist to prevent.
- **Stayed at the 5-file ceiling cleanly.** Five substantive files + this book-keeping handoff = matches CLAUDE.md's quality cap. No file count gymnastics; no "well it's only half a file" rationalization.

**Risks.**

- **Two design tracks remain.** D-61 + D-58 aren't designed yet; the v5 spec rewrite is blocked on both. Mid-stream pauses tend to drift — design decisions made later may conflict subtly with D-59/D-60 decisions captured here. Mitigation: the design docs commit to specific schema shapes (column names, table layouts); D-61/D-58 are constrained to fit those shapes or to explicitly amend them.
- **D-50 wiring is paused for an unknown duration.** Implementation budget that might have gone to wiring is now going to design. If Andy needs working integrations sooner than D-58 → D-50 wiring → first-real-OAuth sequence allows, the priority needs to flip. No pressure flagged yet.
- **CLAUDE.md pointer drift was not fixed this session.** Future sessions will read stale references (Control_Spec_v6 instead of v7; Backlog v11 instead of v15) until the next admin pass. Rule #9 verification against stale pointers wastes effort. The next-session opening admin pass is the protection but it's an opt-in protection, not a forced one.
- **No code was shipped.** All five substantive files are spec / review / design docs. Andy's "push to production as we go" rule favors implementation; this session was 100% design. Defensible because (a) the implementation that would have happened was blocked by the wiring-state discovery, and (b) the design wave needs to happen before implementable specs exist. But if multiple sessions in a row stay in design without code, the rule is being violated in practice even if defensibly per-session.
- **D-60 shared-profile model is overkill for a single user.** The shared-gym-profile schema delivers value at N≥2 athletes per address; Andy alone gets identical functional behavior from v4's per-athlete `locale_equipment`. The design's value is in the migration story (build the abstraction now while data is migratable; building it post-launch requires migrating production data). Real but unproven at this point — if cohort growth stalls at 1, the design is overhead with no payoff. Counter-argument captured in the D-60 gut-check §8 "best argument against."

**What might be missing.**

- **`Account Config 2` (Gym Memberships) and the D-59/D-60 design.** Account Config 2 in v4 says athlete declares which gym chains they're members of. D-59 chain detection runs against the same registry; D-60 shared profiles are address-scoped, not chain-scoped. The Account Config 2 fields (`Gym Chain`, `Membership Active`) interact with D-59 (cross-reference at nearby-instance surfacing — "you can also access these PFs in your travel city, and yes you're a member") but neither design doc explicitly cites it. Worth a sanity-check during v5 spec rewrite.
- **`other_residence` category implications for §K joint-training overlays.** §K K.2 joint-training overlays read the active locale per overlay date. If an athlete sets an `other_residence` as the active locale for a joint-training window, equipment is empty by default — does plan-gen surface a warning, or just generate bodyweight-only sessions? Not explicitly handled in D-60. Backlog item or v5 spec-rewrite catch.
- **D-59 manual `address_fingerprint` and D-60 shared-profile dedup.** D-60 says `gym_profiles` is keyed by `mapbox_id UNIQUE` with `address_fingerprint` as fallback. The normalization rules for `address_fingerprint` aren't specified (lowercase + whitespace-collapse + abbreviation-expansion → can two athletes typing "123 Main St" and "123 Main Street" dedup correctly?). Implementation detail; flag for v5 implementation PR.
- **No design-doc-quality review pass.** Just like the D-50 ship benefited from a Rule #9 review pass, the D-59/D-60 design docs could benefit from a separate Rule-#9-style sanity check before v5 quotes them as authoritative. Possibly bundled into the v5 spec-rewrite session as a self-review step.

**Best argument against this session's scope.**

A simpler session would have done just the review (Option A ratification + backlog row D-62) and stopped. Two design docs is genuinely more design than implementation under Andy's "push to production as we go" rule. Counter: the wiring-was-blocked discovery meant implementation was unavailable this session; substituting design (which is what the next session was going to do anyway, per the D-50 handoff §6.1 forward pointer) was the highest-leverage use of the chat budget. Plus the sequential per-row design model means each track shipped is a permanent piece of locked decision-making, not a sunk-cost interim artifact. The session converted blocked-implementation time into permanent design progress.

---

*End of D-50 Review + Onboarding Wave (D-59 + D-60) closing handoff.*
