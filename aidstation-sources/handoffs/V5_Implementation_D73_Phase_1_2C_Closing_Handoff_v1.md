# D-73 Phase 1.2C — D-51 Implementation Session 3 of 3 — Closing Handoff

**Session:** D-73 Phase 1.2C per `Layer1_D51_Design_v1.md` §4. Per-discipline §D 1:1 baseline sub-tables: §3.4 (`discipline_baseline_running` + `_cycling` + `_swimming` + `_paddling` + `_skiing` + `_navigation` + `_technical`). 7 new tables. 6 paired closed-enum constants in `athlete.py`. Closes the Phase 1.2 schema arc.
**Date:** 2026-05-19
**Predecessor handoff:** `V5_Implementation_D73_Phase_1_2B_Closing_Handoff_v1.md`
**Branch:** `claude/d73-phase-1-2c` (renamed from harness-pinned `claude/v5-phase-1-implementation-yAUJg` at session start per H1).
**Status:** 🟢 2 substantive code = under the 5-substantive-file ceiling. 751 tests green (baseline preserved). D-73 status note extended; Phase 1.2 schema arc closed.

---

## 1. Session-start verification (Rule #9)

Anchor-check of `V5_Implementation_D73_Phase_1_2B_Closing_Handoff_v1.md` §8 claims via `./aidstation-sources/scripts/verify-handoff.sh` + targeted greps. `verify-handoff.sh` reported all paths ✅, working tree clean.

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS health_conditions_log` | grep | ✅ |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS medications_log` | grep | ✅ |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS food_allergies` | grep | ✅ |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS athlete_secondary_sports` | grep | ✅ |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS athlete_discipline_weighting` | grep | ✅ |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS recent_race_results` | grep | ✅ |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS pack_load_history` | grep | ✅ |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS athlete_network_links` | grep | ✅ |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS linked_partner_consents` | grep | ✅ |
| `init_db.py` `_PG_MIGRATIONS` length = 288 (entry to this session) | `python -c "import init_db; print(len(init_db._PG_MIGRATIONS))"` = 288 | ✅ |
| `init_db.py` did NOT touch `disclosure_acknowledgments` (shipped shape preserved) | grep | ✅ |
| `athlete.py` `KNOWN_SYSTEM_CATEGORIES` len 8 / `KNOWN_MEDICATION_CLASSES` len 9 / `KNOWN_ALLERGEN_CATEGORIES` len 12 / `KNOWN_RELATIONSHIP_TYPES` len 6 / `LINKED_PARTNER_CONSENT_SCOPES` len 3 | python -c | ✅ |
| `athlete.py` `PROFILE_FIELDS` len 47 (unchanged) | python -c | ✅ |
| `KNOWN_PROFILE_FIELDS` ⇄ `PREFILL_ELIGIBLE_FIELDS` runtime assert holds | import succeeds; both = 5 | ✅ |
| `pytest tests/` → 751 passed | `751 passed in 0.99s` | ✅ |
| Branch `claude/d73-phase-1-2b` ✅ on `verify-handoff.sh`; harness pinned this session `claude/v5-phase-1-implementation-yAUJg` → renamed `claude/d73-phase-1-2c` at session start | harness rename | ✅ |
| `CURRENT_STATE.md` `Last shipped session` points at 1.2B handoff | inspection | ✅ |
| Backlog D-73 status note names Phase 1.2B as shipped | grep | ✅ |
| Backlog `## Changelog` H2 section has 2026-05-19 Phase 1.2B entry above 1.2A | grep | ✅ |

**Reconciliation note:** clean wrt predecessor. No mid-session drift surfaced — design wave §3.4 specifies every per-discipline column verbatim and on-disk state confirms none of these 7 tables exist yet (greenfield ship).

---

## 2. Session narrative

Andy opened with the predecessor handoff URL and "lets work." After reading CLAUDE → CURRENT_STATE → CARRY_FORWARD → predecessor → `verify-handoff.sh` + spot-grep + 751-test baseline confirmation, the architect-recommended next move was D-73 Phase 1.2C per `Layer1_D51_Design_v1.md` §3.4. Andy picked **Phase 1.2C (recommended)** via the 1-question AskUserQuestion gate.

Branch renamed at session start per H1: `claude/v5-phase-1-implementation-yAUJg` (harness-pinned, scope-mismatched) → `claude/d73-phase-1-2c`. Matches the predecessor 1.2B precedent.

Pre-implementation drift sweep against design wave §3.4 confirmed no on-disk drift: none of the 7 per-discipline tables exist on the running schema (greenfield). Trigger #3 (cross-layer surface change — schema migration) was anticipated by the predecessor §6.1 forward-pointer; no architectural reopening since the design wave specifies every column verbatim. Two minor architect-picks (carried as decisions §7 below):

1. **`updated_at` audit column.** Design wave §3.4 column lists do NOT enumerate `updated_at`; design wave §3.5 (`strength_benchmarks`) DOES. Picked include `updated_at TIMESTAMP DEFAULT NOW()` on all 7 tables for parity with the 1.2A `strength_benchmarks` 1:1 sub-table precedent — same shape, same need for last-edit audit.
2. **`bike_types_available` closed-enum scope.** Design wave §3.4 calls out "comma-separated closed enum subset" but does not enumerate the subset. Picked: no new constant in `athlete.py`; application-side validation against the existing `EQUIPMENT_CATEGORIES['Cycling Equipment']` slugs in `init_db.py` (road_bike / mountain_bike / gravel_bike / cycling_trainer). Reused not invented; same shape as `athlete_secondary_sports.sport_slug` (1.2B) which references Layer 0 framework slugs.

Implementation: `_PG_MIGRATIONS` appends after the existing 1.2B `linked_partner_consents_active_idx` index. One inline anchor comment block pointing back to §3.4 + naming the 6 paired closed-enum constants + the two architect-picks above. Closed-enum constants in `athlete.py` follow the established precedent (tuple of lowercase tokens, paired comment naming the design-wave subsection + the consumer column).

751 tests still green (baseline preserved; schema migrations aren't exercised by pytest by precedent — manual §5.0 walkthrough on Neon is the verification path).

---

## 3. File-by-file edits

### 3.1 `init_db.py` (modified)

One region edited:

- **Lines after the existing 1.2B `linked_partner_consents_active_idx` index, before the closing `]` of `_PG_MIGRATIONS`**: 7 `CREATE TABLE IF NOT EXISTS` blocks (7 new entries; `_PG_MIGRATIONS` grew from 288 → 295). Single anchor-comment block at the head of the region points back to §3.4 + names the paired `athlete.py` constants.

Table-by-table:

| Table | Design wave § | Columns | Pattern |
|---|---|---|---|
| `discipline_baseline_running` | §3.4 §D.1 | 9 (easy_run_pace_sec_per_km, vertical_gain_weekly_m, vertical_gain_peak_session_m, trail_experience_terrain, downhill_adaptation, downhill_sessions_3mo, night_running, gut_training_g_per_hr_cho, gut_training_issues) + updated_at | 1:1 sparse; PK = user_id |
| `discipline_baseline_cycling` | §3.4 §D.2 | 6 (bike_types_available, mtb_skill, longest_ride_distance_km, longest_ride_hrs, saddle_endurance_hrs, aero_endurance_min) + updated_at | 1:1 sparse; PK = user_id |
| `discipline_baseline_swimming` | §3.4 §D.3 | 6 (pool_100m_pace_sec, ow_experience, wetsuit_experience, cold_water_experience, ow_feeding_experience, weekly_swim_volume_km) + updated_at | 1:1 sparse; PK = user_id |
| `discipline_baseline_paddling` | §3.4 §D.4 | 3 (longest_paddle_km, longest_paddle_hrs, paddle_craft_types) + updated_at | 1:1 sparse; PK = user_id |
| `discipline_baseline_skiing` | §3.4 §D.5 | 2 (ski_disciplines, weekly_ski_volume_hrs) + updated_at | 1:1 sparse; PK = user_id |
| `discipline_baseline_navigation` | §3.4 §D.6 | 2 (experience_level, night_nav_experience) + updated_at | 1:1 sparse; PK = user_id |
| `discipline_baseline_technical` | §3.4 §D.7 | 3 (rock_climbing_outdoor_grade, rock_climbing_indoor_grade, abseiling_experience) + updated_at | 1:1 sparse; PK = user_id |

All migrations idempotent (`CREATE TABLE IF NOT EXISTS`). Every column except `user_id` is nullable per v5 §D "every field is nullable; null means 'not asked.'" PK = `user_id INTEGER REFERENCES users(id)` matches the 1.2A `strength_benchmarks` 1:1 precedent and provides the only index needed (PG creates a unique-btree on PK automatically; sparse 1:1 row count makes additional indexes unwarranted).

No new indexes shipped — design wave §3.4 doesn't call for any, and the PK-on-user_id auto-index serves the only read pattern (per-user lookup).

### 3.2 `athlete.py` (modified)

Appended 6 closed-enum constants after `LINKED_PARTNER_CONSENT_SCOPES` (line 200), before `get_daily_availability_windows`. One anchor-comment block at the head of the region explains the pairing + the two architect-picks (no constant for `bike_types_available` — application-validated against `EQUIPMENT_CATEGORIES`; no constant for `rock_climbing_*_grade` — free-text multi-system per Layer 4 Step 4a).

| Constant | Values | Design wave § | Used by |
|---|---|---|---|
| `TRAIL_EXPERIENCE_TERRAINS` | 4 (moderate/technical/mountain/moorland) | §3.4 §D.1 | `discipline_baseline_running.trail_experience_terrain` (multi-select, comma-separated subset) |
| `MTB_SKILL_LEVELS` | 3 (beginner/intermediate/advanced) | §3.4 §D.2 | `discipline_baseline_cycling.mtb_skill` write-path validation |
| `OW_EXPERIENCE_LEVELS` | 3 (none/limited/experienced) | §3.4 §D.3 | `discipline_baseline_swimming.ow_experience` write-path validation |
| `PADDLE_CRAFT_TYPES` | 4 (kayak/canoe/packraft/surfski) | §3.4 §D.4 | `discipline_baseline_paddling.paddle_craft_types` (multi-select, comma-separated subset) |
| `SKI_DISCIPLINES` | 3 (classic_xc/skate_xc/skimo) | §3.4 §D.5 | `discipline_baseline_skiing.ski_disciplines` (multi-select, comma-separated subset) |
| `NAVIGATION_EXPERIENCE_LEVELS` | 4 (none/map_only/map_compass/expert) | §3.4 §D.6 | `discipline_baseline_navigation.experience_level` write-path validation |

No changes to existing constants. `PROFILE_FIELDS` length stays 47.

---

## 4. Code / tests

`tests/` count: 751 → 751. No new test files (matches 1.2A + 1.2B precedent — schema migrations are verified through downstream code that consumes them + the §5.0 manual walkthrough on Neon).

Modified-file import check: `python -c "import init_db, athlete; from routes.profile_fields import KNOWN_PROFILE_FIELDS, PREFILL_ELIGIBLE_FIELDS"` succeeds. `KNOWN_PROFILE_FIELDS` (5) ⇄ `PREFILL_ELIGIBLE_FIELDS` (5) runtime assert holds. `_PG_MIGRATIONS` length 288 → 295 (+7 entries).

`pytest tests/` → **751 passed in 0.88s**.

---

## 5. Manual §5.0 verification steps (Vercel, post-merge)

4 testable steps for the manual walkthrough after this PR deploys to Neon production.

1. **Schema migration — 7 new tables present:** `\d discipline_baseline_running` + `\d discipline_baseline_cycling` + `\d discipline_baseline_swimming` + `\d discipline_baseline_paddling` + `\d discipline_baseline_skiing` + `\d discipline_baseline_navigation` + `\d discipline_baseline_technical` on Neon — confirm each table exists with the column shape matching `init_db.py` (running 9 + updated_at + PK; cycling 6 + updated_at + PK; etc.).
2. **PK shape — 1:1 user_id constraint:** `\d <table>` should show `user_id` as PRIMARY KEY (auto-creating the unique-btree index `<table>_pkey`). Insert a row + attempt second insert with same `user_id` — confirm UNIQUE-violation error.
3. **Idempotency:** trigger a second cold-start (or manually re-run `init_postgres()`) — confirm zero errors (`CREATE TABLE IF NOT EXISTS` is a no-op on the second run).
4. **Regression sweep:** `/profile?tab=athlete` + `/profile?tab=connections` + `/onboarding/prefill` + `/locales` + `/dashboard` all render unchanged (this session adds storage only; no UI surface touched).

Appended to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" under a new D-73 Phase 1.2C header (scenario count rises 49 → 53).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**D-73 Phase 1.3** per `Upstream_Implementation_Plan_v1.md` §4 — Layer 1 builder + `Layer1Payload` typed pydantic mirror in `layer4/context.py`. The Phase 1.2 schema arc is now closed (all of §A-§L storage shipped except the intentionally-skipped §3.1 `disclosure_acknowledgments` polymorphic-FK addition); Phase 1.3 is the consumer-side closer: a Python builder that reads the `athlete_profile` columns + 1:1 sub-tables + multi-row companions and assembles a `Layer1Payload` for downstream consumption. Per `Layer1_D51_Design_v1.md` §5.4, this is the long-deferred typed-payload promotion. ~6-8 files (`layer4/context.py` extension + new `layer1/builder.py` or `layer1/__init__.py` + paired test scaffolding + Layer1_Spec.md consolidation per `Upstream_Implementation_Plan_v1.md` §4 Phase 1.3). **Ceiling break expected** — propose splitting if it grows past 5 substantive files (the typed-payload promotion alone could be its own session).

### 6.2 Alternative pivots

- **D-73 Phase 1.4 — D-52 catalog migration sequencing kickoff** — /plan-mode gate per `Upstream_Implementation_Plan_v1.md` §4 (sequencing decision deferred to Phase 2 kickoff but D-52 Phase 1 verification + alias-tables scoping can land independently). ~3-4 files.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration (~6-8 files). Closes Layer 4 §14.3.4 Step 4 sub-arc. Orthogonal to D-73 arc.
- **Layer 4 Step 7 env-gated scaffolding** — `ANTHROPIC_API_KEY` plumbing without a real call (~3-4 files). Strategic value: unblocks Phase 5 vertical slice.
- **Manual §5.0 walkthrough of accumulated scenarios** — 53 §5.0 scenarios in `CARRY_FORWARD.md` (37 doable now per `PR_Verification_Status.md` + 6 from 1.2A re-walks + 6 from 1.2B + 4 from 1.2C). Andy's call when to batch-walk.
- **§3.1 disclosure_acknowledgments polymorphic-FK addition** — additive `ALTER TABLE disclosure_acknowledgments ADD COLUMN IF NOT EXISTS subject_id BIGINT`. ~1 file delta. Not currently demanded by any open spec; remains queued from 1.2B §6.2.

### 6.3 Operating notes for next session

Read order per Rule #13:
1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff
3. `aidstation-sources/CARRY_FORWARD.md` — 53 walkthrough scenarios + 3 doc nits + orthogonal tracks
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

If picking Phase 1.3: re-read `Layer1_D51_Design_v1.md` §5.4 (Layer 1 typed payload carry-forward) + `layer4/context.py` (existing pydantic v2 contracts as the shape reference) + `Upstream_Implementation_Plan_v1.md` §4 Phase 1.3 (file estimate + ratification gate). Trigger #5 (cross-layer contract — Layer 1 typed-payload promotion) expected to fire; route via /plan-mode gate. Expect ceiling break — propose splitting at session start.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Branch renamed `claude/v5-phase-1-implementation-yAUJg` → `claude/d73-phase-1-2c` | Architect at session start | H1 rule (rename harness-pinned branches if they mismatch session scope). Predecessor 1.2B set the exact precedent. |
| 2 | Include `updated_at TIMESTAMP DEFAULT NOW()` on all 7 per-discipline tables | Architect-pick | 1.2A `strength_benchmarks` 1:1 precedent includes it; same shape (sparse 1:1 sub-table) → same audit need. Design wave §3.4 doesn't enumerate it but doesn't exclude it either. No functional cost (default NOW()), nominal audit benefit. |
| 3 | No closed-enum constant in `athlete.py` for `bike_types_available` | Architect-pick | Design wave §3.4 calls out "comma-separated closed enum subset" but doesn't enumerate. Reuse existing `EQUIPMENT_CATEGORIES['Cycling Equipment']` slugs (road_bike / mountain_bike / gravel_bike / cycling_trainer) at the application layer — mirrors the `athlete_secondary_sports.sport_slug` precedent (1.2B) where Layer 0 framework slugs are the validation source. Avoids inventing a new closed enum that would have to be reconciled with Layer 0 later. |
| 4 | No closed-enum constant for `rock_climbing_outdoor_grade` / `_indoor_grade` | Architect-pick | Design wave §3.4 explicitly says "Yosemite Decimal / French Sport / UIAA per Layer 4 Step 4a precedent" — free-text multi-system grading. Layer 4 Step 4a established the validation path. Adding a closed-enum here would force the consumer to over-constrain. |
| 5 | No indexes beyond PK = user_id | Architect-pick | 1:1 sparse sub-tables. PG auto-creates a unique-btree on PRIMARY KEY (user_id), which is the only access pattern (`SELECT … WHERE user_id = ?`). Additional indexes would be dead weight. Design wave §3.4 doesn't call for any. |
| 6 | Phase 1.2 schema arc closed with this session | Architect-call | §3.4 was the last storage subsection in the design wave (§3.1 intentionally skipped per 1.2B §7 #2). Phase 1.3 (Layer 1 builder + typed payload) is the next phase per `Upstream_Implementation_Plan_v1.md` §4. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS discipline_baseline_running` | ✅ `grep -c "CREATE TABLE IF NOT EXISTS discipline_baseline_running"` = 1 |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS discipline_baseline_cycling` | ✅ grep |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS discipline_baseline_swimming` | ✅ grep |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS discipline_baseline_paddling` | ✅ grep |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS discipline_baseline_skiing` | ✅ grep |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS discipline_baseline_navigation` | ✅ grep |
| `init_db.py` contains `CREATE TABLE IF NOT EXISTS discipline_baseline_technical` | ✅ grep |
| `init_db.py` `_PG_MIGRATIONS` length = 295 | ✅ `python -c "import init_db; print(len(init_db._PG_MIGRATIONS))"` = 295 |
| `init_db.py` `discipline_baseline_running` has `user_id INTEGER PRIMARY KEY REFERENCES users(id)` | ✅ grep |
| `init_db.py` `discipline_baseline_running` has 9 §D.1 columns (easy_run_pace_sec_per_km / vertical_gain_weekly_m / vertical_gain_peak_session_m / trail_experience_terrain / downhill_adaptation / downhill_sessions_3mo / night_running / gut_training_g_per_hr_cho / gut_training_issues) + updated_at | ✅ inspection |
| `athlete.py` `TRAIL_EXPERIENCE_TERRAINS` length 4 | ✅ `python -c "import athlete; print(len(athlete.TRAIL_EXPERIENCE_TERRAINS))"` = 4 |
| `athlete.py` `MTB_SKILL_LEVELS` length 3 | ✅ = 3 |
| `athlete.py` `OW_EXPERIENCE_LEVELS` length 3 | ✅ = 3 |
| `athlete.py` `PADDLE_CRAFT_TYPES` length 4 | ✅ = 4 |
| `athlete.py` `SKI_DISCIPLINES` length 3 | ✅ = 3 |
| `athlete.py` `NAVIGATION_EXPERIENCE_LEVELS` length 4 | ✅ = 4 |
| `athlete.py` `PROFILE_FIELDS` length 47 (unchanged) | ✅ = 47 |
| `KNOWN_PROFILE_FIELDS` ⇄ `PREFILL_ELIGIBLE_FIELDS` runtime assert holds | ✅ `from routes.profile_fields import KNOWN_PROFILE_FIELDS, PREFILL_ELIGIBLE_FIELDS` succeeds |
| `pytest tests/` → 751 passed | ✅ `751 passed in 0.88s` |
| Branch is `claude/d73-phase-1-2c` (renamed per H1) | ✅ `git branch --show-current` |
| `CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| Backlog `D-73` status note extended to name Phase 1.2C as shipped + Phase 1.2 arc closed | ✅ grep |
| Backlog `## Changelog` H2 section has a new 2026-05-19 Phase 1.2C entry above the 1.2B entry | ✅ grep |
| `CARRY_FORWARD.md` Manual §5.0 walkthrough count rose 49 → 53 (+4 Phase 1.2C scenarios) | ✅ inspection |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (2 files; well under the 5-file ceiling):**

1. Modified `init_db.py` — `_PG_MIGRATIONS` appends (7 new CREATE TABLE blocks; `_PG_MIGRATIONS` length 288 → 295).
2. Modified `athlete.py` — 6 new closed-enum constants appended after `LINKED_PARTNER_CONSENT_SCOPES` (`TRAIL_EXPERIENCE_TERRAINS` + `MTB_SKILL_LEVELS` + `OW_EXPERIENCE_LEVELS` + `PADDLE_CRAFT_TYPES` + `SKI_DISCIPLINES` + `NAVIGATION_EXPERIENCE_LEVELS`).

**Bookkeeping (4 files; outside ceiling per B3):**

3. Modified `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer 1 status note extended (Phase 1.2 schema arc closed; Phase 1.3 queued); Tests note bumped to 2026-05-19 + Phase 1.2C.
4. Modified `aidstation-sources/Project_Backlog_v62.md` — in-place: D-73 status note extended to name Phase 1.2C as shipped + Phase 1.2 arc closed; new 2026-05-19 Phase 1.2C entry added to `## Changelog` (above the 1.2B entry, per most-recent-first rule).
5. Modified `aidstation-sources/CARRY_FORWARD.md` — Manual §5.0 walkthrough section gains a "4 D-73 Phase 1.2C" sub-bullet; total scenario count 49 → 53.
6. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_1_2C_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` gains 4 new §5.0 walkthrough scenarios under a "D-73 Phase 1.2C (post-merge Neon walks)" sub-header in the "Manual §5.0 walkthrough" section. Scenario count rises from 49 to 53 (12 onboarding + 6 nudge UI + 6 Layer 3B Scope A + 6 Layer 3B Scope B + 5 Layer 3B Scope C + 1 D-72 + 7 D-73 Phase 1.2A + 6 D-73 Phase 1.2B + 4 D-73 Phase 1.2C).

No new orthogonal carry-forwards this session. The §3.1 `disclosure_acknowledgments` polymorphic-FK addition queued in 1.2B §6.2 remains the only D-73 storage-side carry-forward not yet shipped.

No new doc-sweep nits surfaced this session.

Layer 4 Step 4f + Step 7 + Step 8 still queued per the existing list.

---

**End of handoff.**
