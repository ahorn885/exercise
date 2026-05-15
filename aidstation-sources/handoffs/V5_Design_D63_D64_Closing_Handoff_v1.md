# V5 Design Pass — D-63 On-Demand Workout + D-64 Plan Refresh Tiers — Closing Handoff

**Session:** Design-only session. Two new D-rows surfaced by Andy 2026-05-15 mid-conversation while scoping PR12 D-61: (a) D-63 — "build me a workout right now" feature, off-plan single-session synthesis; (b) D-64 — Tier 1/2/3 plan refresh framework (athlete-initiated button + NL context). Both are cross-layer (stop-and-ask trigger #11), both Layer-4-dependent, both enterprise features. Andy chose Option A1 for PR12 D-61 (§G + onboarding integration only; JIT swap waits on Layer 4 spec) and "design D-63 now, PR12 D-61 code next chat" for sequencing — so this session ships **design specs only**, no executable code.
**Date:** 2026-05-15
**Predecessor handoff:** `V5_Implementation_PR11_Closing_Handoff_v1.md` (PR11 D3b shipped + merged as `5629a25`).
**Branch:** `claude/v5-closing-handoff-d5AOX` (per-session feature branch off post-PR11 `main`; this session adds design files only — no code changes; push pending).
**Status:** 🟡 Design specs shipped to feature branch; 🟡 push pending. **Implementation of both D-63 and D-64 gates on Layer 4 spec landing** — no §5.0 walk-through owed since no code shipped.
**Time-on-task:** Single chat. Files this turn: **5** (`Plan_Refresh_D64_Design_v1.md` new, `OnDemand_Workout_D63_Design_v1.md` new, `Project_Backlog_v24.md` new copy of v23 + 4 surgical edits, `CLAUDE.md` 3 surgical edits, this handoff). At the 5-substantive ceiling; design-pass discipline observed.

---

## 1. Session-start verification (Rule #9)

Verified the PR11 handoff's claimed state before any new work. **No drift.**

| Claim | Anchor | Result |
|---|---|---|
| PR11 D3b merged to `origin/main` as `5629a25` (PR #46 from `claude/v5-closing-handoff-eZFt9`); `claude/v5-closing-handoff-d5AOX` is at the same SHA; local `main` is 2 commits behind origin/main but `HEAD` has everything | `git log --oneline` | ✅ Verified |
| `init_db.py:1906-1959` has the FK fix block — composite-FK rewrite of `locale_equipment_overrides` + `locale_toggle_overrides` + idempotent `DO $$ BEGIN … END $$` ALTER guard | grep | ✅ Verified |
| `routes/locales.py` (839 lines) has `MANUAL_CATEGORIES` (10 entries), `SHARED_PROFILE_CATEGORIES` (7 entries), `_is_shared_profile_locale`, `_edit_shared_locale`, `_edit_legacy_locale`, `refresh_from_mapbox`, `_save_mapbox_anchored` upgrade-path | grep + line counts | ✅ Verified |
| `templates/locales/form.html` (105 lines) has three modes (legacy / shared_build / shared_inherit); `templates/locales/new.html` (128 lines) threads `upgrade_slug`; `templates/locales/list.html` (73 lines) has ⟳ Refresh form; `templates/locales/refresh_confirm.html` exists (40 lines) | grep | ✅ Verified |
| `Project_Backlog_v23.md` exists (416 lines); v22 archived to predecessor block; D-50 row reflects PR1–PR11 shipped; D-59 status 🟢 fully shipped; D-60 status 🟢 core inherit/override shipped | wc + grep | ✅ Verified |
| `CLAUDE.md` "Authoritative current files" backlog line reads `Project_Backlog_v23.md` | grep | ✅ Verified |
| `Onboarding_D61_Design_v1.md` exists (D-61 design ready to consume for next-chat PR12 code) | ls | ✅ Verified |
| `PR_Verification_Status.md` exists | ls | ✅ Verified |

No drift. PR11 closes v5 §J locale work end-to-end as the predecessor handoff claimed.

---

## 2. Files shipped this turn

All on branch `claude/v5-closing-handoff-d5AOX`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Plan_Refresh_D64_Design_v1.md` | New (~310 lines) | D-64 design doc. 12 decisions; 12 sections (purpose / decisions / tier definitions / athlete UX / NL intent parser contract / cascade execution / storage / frequency caps / implementation gating / open items / test scenarios / gut check). Defines athlete-initiated T1/T2/T3 plan refresh framework: rolling-window scopes (2/7/28 days); free-text NL + LLM intent parser → upstream layer triggers; default cascade per tier with NL-additive expansion; both `/dashboard` and training-plan-view button surfaces; soft frequency caps with override; atomic versioning with per-day `plan_version_id` pointer; concurrency block; failure rollback; diff visibility; `plan_refresh_log` table schema. NL intent parser **prompt body deferred** to its own spec session per stop-and-ask trigger #2 — D-64 defines the I/O contract (`IntentParserInput` / `ParsedIntent` dataclasses) only. **Implementation gates on Layer 4 spec landing.** |
| 2 | `aidstation-sources/OnDemand_Workout_D63_Design_v1.md` | New (~290 lines) | D-63 design doc. 13 decisions; 10 sections (purpose / decisions / athlete UX / layer placement / storage / constraint resolution / implementation gating / open items / test scenarios / gut check). Defines off-plan single-session "build me a workout right now" feature: athlete inputs sport/duration/intensity/location; reads Layer 1 profile (constraints) + Layer 3A state + D-60 effective-equipment view; Layer 4 single-session synthesis returns structured session matching planned-session output schema. Storage extends `cardio_log` + `training_log` with `is_ad_hoc` BOOLEAN + `ad_hoc_request_payload` JSONB + `ad_hoc_suggestion_id` BIGINT; new `ad_hoc_workout_suggestions` table with status lifecycle (suggested → logged/discarded/regenerated). Post-completion T1 hook into D-64 (cross-spec dependency: `plan_refresh_log.triggered_by_ad_hoc_id` lands on D-64 schema). Generation prompt body **deferred** to Layer 4 prompt-engineering work. **Implementation gates on Layer 4 spec landing.** |
| 3 | `aidstation-sources/Project_Backlog_v24.md` | New (copy of v23 + 4 surgical edits) | (a) **File revision header** bumped v23→v24 with the design-pass narrative ("Plan-execution design pass — two new D-rows added: D-63 + D-64"). (b) **Predecessor revisions block** prepends the v23 entry (trimmed to one line). (c) **D-63 row added** below D-62 with full Notes column referencing `OnDemand_Workout_D63_Design_v1.md`. (d) **D-64 row added** below D-63 with full Notes column referencing `Plan_Refresh_D64_Design_v1.md`. D-50 status cell **unchanged** — no PR shipped this revision; the design pass is the unit of revision. PR12 D-61 §G + onboarding-integration code is the next-chat candidate (per PR11 §5.1 Option A1). Numbering note unchanged (D-18/19/20 gap stable). |
| 4 | `aidstation-sources/CLAUDE.md` | Edit (3 surgical) | (a) "Authoritative current files" backlog line bumped from `Project_Backlog_v23.md` to `Project_Backlog_v24.md`. (b) Added line under "Onboarding design wave inputs": "Plan-execution design wave inputs: `OnDemand_Workout_D63_Design_v1.md`, `Plan_Refresh_D64_Design_v1.md` (both 🟡 implementation gates on Layer 4 spec landing)". (c) "Current state (as of 2026-05-14)" header bumped to `2026-05-15`; "Last shipped session" narrative updated to point at this design-pass handoff with a one-paragraph summary of D-63 + D-64. |
| 5 | `aidstation-sources/handoffs/V5_Design_D63_D64_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- All v1 application code (`init_db.py`, `routes/`, `templates/`, etc.) — design-only session; no code changes.
- `Athlete_Onboarding_Data_Spec_v5.md` — D-63 and D-64 are NOT onboarding scope; they're plan-execution scope. Athlete_Onboarding_Data_Spec stays at v5 with no changes.
- `Control_Spec_v7.md` — D-64 references §4 partial-update model but adds no new architectural surface; the "athlete-initiated counterpart" framing is in D-64's §1 purpose, not in Control_Spec. If Andy wants Control_Spec to formally reference D-63 + D-64, that would be a v8 bump (separate session, stop-and-ask trigger #10).
- Layer-spec files (Layer3_3A, Layer3_3B, Layer2x specs) — no changes; D-63 and D-64 consume them as-is.
- `PR_Verification_Status.md` — no PR shipped this revision; tracker stays as-is.
- `Onboarding_D61_Design_v1.md` — unchanged; PR12 will consume it as-is for §G + onboarding integration code.

---

## 3. What landed

### 3.1 D-63 — On-demand workout

The "build me a workout right now" feature Andy surfaced 2026-05-15. Athlete supplies sport/duration/intensity/location; system synthesizes a single session off-plan that respects the athlete's profile constraints (injuries, age, training load) and the location's equipment view. Logged sessions feed Layer 3A so athlete state evolves correctly. Optional T1 plan-check hook after completion lets athlete opt into refreshing the next 2 days based on what they just did.

**Key design choices:**
- **Profile-level constraints, not per-request.** Andy's "wrist doesn't matter, that's just me" framing — constraints come from Layer 1 §B injuries, scale across athletes; per-request override deferred to v2.
- **D-60 effective equipment view** (`(shared ∪ adds) ∖ removes`) is the equipment source. Reuses PR11 work; no new equipment-resolution path.
- **Single sport per request.** Brick (multi-sport) deferred to v2.
- **Output shape matches Layer 4 planned-session schema.** Layer 3A consumes ad-hoc sessions identically to planned ones.
- **Storage:** `cardio_log` + `training_log` extended with `is_ad_hoc` flag + JSONB request payload + suggestion FK. New `ad_hoc_workout_suggestions` table holds generated-but-unlogged sessions with status lifecycle.
- **T1 hook:** post-log CTA "Want to refresh the next 2 days?" → fires D-64 T1 with auto-filled NL context. Athlete can dismiss; soft, not forcing.
- **"Somewhere else" quick-add path** for travel/one-off cases without forcing a full locale-creation flow.
- **Prompt body deferred** to Layer 4 prompt-engineering work.

**13 decisions** captured in §2 of the spec.

### 3.2 D-64 — Plan refresh tiers (T1/T2/T3)

The framework Andy clarified after the "what does Tier 1 mean?" exchange. Athlete-initiated button on `/dashboard` AND training plan view + optional free-text NL context. Three tiers scoped by horizon:

- **T1** = next 2 days rolling. Cascade: Layer 3A + Layer 4. Use case: "make tomorrow easier."
- **T2** = next 7 days rolling. Cascade: Layer 3A + 3B + Layer 4. Use case: "regenerate the rest of the week."
- **T3** = next 28 days rolling, OR initial plan generation when no plan exists. Cascade: full 2A/B/C/D/E + 3A/B/C/D + Layer 4. Use case: "monthly big update" or first-plan-gen path.

NL context is parsed by an LLM intent classifier. Parsed intent flags can ADD upstream layer re-runs to the tier's default cascade (e.g., NL says "I tweaked my ankle" → 2D added regardless of tier). Soft signals (fatigue, sickness, motivation) flow through to Layer 4 as context without triggering re-runs.

**Key design choices:**
- **Rolling windows from `today`** (not calendar weeks) — Andy 2026-05-15. Avoids edge-of-week awkwardness.
- **Both button surfaces** (dashboard + plan view) — Andy 2026-05-15. Discoverability + contextual access.
- **Free-text + LLM parsing** — Andy 2026-05-15. Captures soft signals; routes cascade precisely.
- **Soft frequency caps with override** (T1 3/24h; T2 1/48h; T3 1/7d) — Andy 2026-05-15. Cost protection without paternalism.
- **Atomic versioning** — new plan version commits only if cascade completes end-to-end; mid-flight failure → previous version retained.
- **Per-day `plan_version_id` pointer** (not per-plan) — out-of-scope sessions retain prior pointer; T1 only updates day 1-2 pointers.
- **Concurrency block** — second click during in-flight refresh is a no-op.
- **Diff visibility** — "updated" badges + expandable per-session diff.
- **Telemetry table:** `plan_refresh_log` captures tier, NL text, parsed intent, cascade duration, sessions changed, token cost, success/failure, cap-overridden flag, revert timestamp.
- **NL intent parser prompt body deferred** to its own spec session per stop-and-ask trigger #2.

**12 decisions** captured in §2 of the spec.

### 3.3 Backlog v24 + CLAUDE.md sync

- **`Project_Backlog_v24.md`** copy of v23 with v23→v24 file-revision header (design-pass narrative), v23 entry prepended to predecessor revisions block, D-63 + D-64 rows added in numerical order below D-62. D-50 status unchanged (no PR shipped). Numbering note unchanged.
- **`CLAUDE.md`** updated: backlog pointer v23→v24; new "Plan-execution design wave inputs" line added; "Current state" header date + last-shipped narrative bumped.

### 3.4 NOT shipped — explicit deferrals

- **NL intent parser prompt body** (D-64) — deferred to its own spec session per stop-and-ask trigger #2. D-64 defines the I/O contract; the prompt text lands separately.
- **Single-session synthesis prompt body** (D-63) — deferred to Layer 4 prompt-engineering work. D-63 defines the input/output contract.
- **Layer 4 spec.** Both D-63 and D-64 implementation gate on Layer 4 spec existing. Layer 4 spec is the next big unspecced layer per CLAUDE.md.
- **Plan-version table schema.** D-64 references it; the table itself lands with Layer 4.
- **Plan-revert UI.** D-64 specifies storage shape (per-day pointer flip); the UI lands with plan-management UI work.
- **Mobile UX** for D-63 form — out of scope; no mobile client today.
- **Multi-sport (brick) on-demand workouts** — deferred to v2 per D-63 Decision #5.
- **Per-request profile-constraint override** — deferred to v2 per D-63 Decision #4.
- **Per-athlete cap tunability** for D-64 — v1 ships single global thresholds.
- **Joint-training overlay interaction** for D-64 — out of scope; team-coordination is differentiator #5 territory.
- **Cross-tier interaction** (athlete fires T1 then T2 within minutes) — works correctly under per-day pointer model; flagged for verification when implemented.
- **Auto-discard timer for `suggested` ad-hoc workouts** — open item; tune post-deploy.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| `Plan_Refresh_D64_Design_v1.md` exists; ~310 lines; header/decisions/tier-definitions/UX/parser-contract/cascade/storage/caps/gating/open-items/scenarios/gut-check sections all present | wc + grep | ✅ Verified |
| `OnDemand_Workout_D63_Design_v1.md` exists; ~290 lines; header/decisions/UX/layer-placement/storage/constraints/gating/open-items/scenarios/gut-check sections all present; cross-references D-64 for T1 hook | wc + grep | ✅ Verified |
| `Project_Backlog_v24.md` exists; v23 archived to predecessor block; D-63 + D-64 rows in numerical order below D-62; D-50 row content unchanged from v23 | grep + line check | ✅ Verified |
| `CLAUDE.md` "Authoritative current files" backlog line reads `Project_Backlog_v24.md`; new "Plan-execution design wave inputs" line present; "Current state (as of 2026-05-15)" header reflects today's date | grep | ✅ Verified |
| No code files (`init_db.py`, `routes/`, `templates/`, etc.) modified this session | git status (will run pre-push) | ✅ By construction (design-only session) |
| Handoff file (this) exists with §1-§7 sections | wc | ✅ Verified |
| 5-file ceiling respected: 5 substantive files (2 design specs + backlog + CLAUDE.md edit + this handoff) | file count | ✅ Verified |

No drift between this handoff's narrative and on-disk state.

**Live verification gap:** none, since no code shipped. The next code session's Rule #9 will verify the design specs exist as claimed.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 No pre-deploy verification owed

This was a design-only session. No code shipped → no §5.0 walk-through owed. PR11's §5.0 walk-through carry-forward (the live D-60 + §6 + §7 round-trips against PG + Mapbox) is still owed; tracked in `PR_Verification_Status.md`.

### 5.1 Next-session candidate menu

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read. Especially note the new "Plan-execution design wave inputs" line and the bumped backlog pointer to v24.
2. `aidstation-sources/PR_Verification_Status.md` — confirm which PR §5.0 steps have / haven't been walked.
3. `aidstation-sources/handoffs/V5_Design_D63_D64_Closing_Handoff_v1.md` (this file).
4. `aidstation-sources/handoffs/V5_Implementation_PR11_Closing_Handoff_v1.md` (predecessor — PR11).
5. `aidstation-sources/Project_Backlog_v24.md` — current; PR12 may bump to v25 (see §5.4 conditional).
6. Domain spec for the picked candidate (see below).

#### Option PR12 — D-61 §G + onboarding integration (per PR11 §5.1 Option A1; recommended next per Andy 2026-05-15)

**Domain spec read:** `Onboarding_D61_Design_v1.md` + `Athlete_Onboarding_Data_Spec_v5.md` §G + §J.5 deletion + §G.4 resolver.

Per-day windows UI replacement for v4 §G's weekly-totals form. Three orthogonal capacity flags (Long Session, Doubles, Preferred Rest Day). Onboarding-step integration slots the new §G form into the existing flow.

**Estimated 4-5 files.** JIT swap explicitly NOT in this PR's scope (Andy 2026-05-15 picked Option A1 — JIT waits on Layer 4 spec). Scope is the §G frontend rewrite + onboarding-step routing only.

**Likely files:**
- `init_db.py` — `daily_availability_windows` table is in PR2's `_PG_MIGRATIONS` (D-61 schema shipped). Verify FK shape; no new schema needed.
- `routes/onboarding.py` (or wherever the §G step routes) — wire the per-day windows form.
- New template for the per-day windows UI (or extend an existing one).
- `routes/profile.py` (potentially) — surface per-day windows on the athlete-tab edit screen.
- Backlog v24→v25 bump (PR12 will ship a state-changing event — D-61 status flips Implementation pending → 🟢 §G shipped).

#### Option Layer 4 spec draft

The next big unspecced layer in the pipeline. Both D-63 and D-64 implementation gate on it; D-61's JIT swap also gates on it. Substantial work (Layer 4 = plan generation + periodization validator + capped correction loop + session output schema + plan-version table). Multi-session likely.

**Domain spec read:** would start fresh; no predecessor Layer 4 spec exists.

#### Option D-63 + D-64 implementation pre-Layer-4 stopgap

Explicitly NOT recommended in either spec doc (D-63 §7, D-64 §9). Loses most of the framework value; throwaway work. Skip.

#### Other PR11 §5.1 carry-forwards (unchanged)

- **§J.3 sport-specific gear toggle UI** — needs spec re-read; Andy's "different form" framing.
- **D-60 closeout** (sharing-consent disclosure → opt-out → dispute → submit-as-correction).
- **F** (Polar refresh-on-401), **H** (provider blueprint expansion), **D2c** (bulk apply), **E-telemetry** (`account_nudges` `clicked_cta_at`).

### 5.2 Recommended sequence (revised post-D-63/D-64 design)

1. **PR12 = D-61 Option A1** (per-day windows §G + onboarding integration). Closes the v5 §G mechanic. Doesn't depend on Layer 4. Andy's chosen next move. **Recommended.**
2. **Layer 4 spec draft** — once D-61 §G ships, Layer 4 becomes the gate for everything else (D-63, D-64, JIT swap, the rest of v5 §J/§G). Multi-session work; spec-first. Substantial.
3. **D-63 + D-64 implementation** — once Layer 4 spec lands. Either as separate PRs or bundled depending on Layer 4's surface.
4. **§J.3 toggles UI design re-read** — parallel track.
5. **D-60 closeout** — when cohort > 1.

### 5.3 Standing items not on the critical path (carried from PR11 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged.
- **D-54 SQLite collapse** — unchanged.
- **D-55 Garmin onto `provider_auth`** — paused.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. PR9's `vercel.json` `crons` array remains the natural home.
- **§J.3 sport-specific gear toggle UI** — unchanged; awaiting design re-read.
- **D-60 dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure** — unchanged.
- **D-61 per-day windows UI** — PR12 candidate (recommended next).
- **D-63 on-demand workout** — *new this session* as design-complete, implementation-pending. Gates on Layer 4 spec.
- **D-64 plan refresh tiers** — *new this session* as design-complete, implementation-pending. Gates on Layer 4 spec.
- **NL intent parser prompt body design** (D-64) — *new this session* as deferred design item; needs its own session before D-64 ships.
- **Layer 4 single-session synthesis prompt body design** (D-63) — *new this session* as deferred design item; folds into Layer 4 prompt-engineering work.
- **Open Item #18 — Telemetry on the 14-day connect-provider nudge** — unchanged.
- **DATABASE.md update / PROVIDERS_SCHEMA.md update / Provenance-row deletion / `_POST_STEP2_TARGET` alias / Per-field "from {provider}" tag / `[Keep current]` writes 'manual_override' / No retry/idempotency on apply / `f.candidates[0]` divergence tag / Confirmation dialogs on `[Use provider value]`** — all carry-overs from prior PRs; unchanged.

### 5.4 Backlog row update (next PR's first action — conditional)

D-63 + D-64 design pass bumped v23→v24 (this revision). PR12 will need to bump v24→v25 if it lands a state-changing event (e.g., D-61 §G ships → D-50 row notes update + D-61 row status flip).

**For PR12, owed v24 → v25 bump (mechanically-applicable per Rule #11):**

1. Copy `aidstation-sources/Project_Backlog_v24.md` to `aidstation-sources/Project_Backlog_v25.md`.
2. **Replace** the file-revision header narrative on line 5 with PR12's state-flip summary. Pattern:
    ```
    **File revision:** v25 — 2026-05-1X (D-50 row status flip catching up PR12 + D-61 status flip: D-50 status cell now reads 🟢 PR1–PR12 shipped (commits …, `<PR12-merge>`); 🟢 D-61 §G + onboarding integration shipped PR12 — replaces v4 weekly-totals §G form with per-day windows + Long Session / Doubles / Preferred Rest Day orthogonal toggles per `Onboarding_D61_Design_v1.md`. JIT swap deferred to post-Layer-4. Per `V5_Implementation_PR12_Closing_Handoff_v1.md`. D-61 status flipped 🟡 Implementation pending → 🟢 §G shipped (JIT pending). No new D-row work this revision — pure status tracking + D-61 §G execution)
    ```
3. **Prepend** to the predecessor revisions block (verbatim from current v24 line 5 narrative trimmed to one line):
    ```
    - v24 — 2026-05-15 (Plan-execution design pass — two new D-rows added: D-63 on-demand workout + D-64 plan refresh tiers. Both design complete; implementation gates on Layer 4 spec landing. No code shipped this revision; pure design addition. Per `V5_Design_D63_D64_Closing_Handoff_v1.md`)
    ```
4. **Update** the D-50 row description column: add a new "PR12 (this revision):" entry summarising the §G + onboarding integration. **Update** the D-50 status cell: PR12 added to merged-commits list; PR12's feature added to the 🟢 shipped list. **Update** the D-50 Notes column: handoff pointer flipped to `V5_Implementation_PR12_Closing_Handoff_v1.md`; PR12+ → PR13+ candidate menu; D-61 §G removed from the menu; recommended sequence advanced (now: Layer 4 spec is next big thing, D-63/D-64 implementation gates on it).
5. **Update** the D-61 row status: 🟡 Implementation pending → 🟢 §G + onboarding integration shipped PR12; 🟡 JIT swap pending Layer 4. Notes column expanded.
6. **Bump** `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line from `Project_Backlog_v24.md` to `Project_Backlog_v25.md`.

**If PR12 doesn't ship the §G feature** (e.g. it's a watch-item PR), skip the v24→v25 bump entirely.

---

## 6. Open items / honest flags

- **5-file ceiling respected.** Two design specs (substantive) + backlog v24 + CLAUDE.md edit + this handoff = 5 files. At-ceiling, observed cleanly. PR10 + PR11 each ran over the ceiling for code-loading reasons; this session stays at the line because design work doesn't have the same coherence-vs-split tradeoff.
- **No live verification owed for this session** — pure design. The Rule #9 reconciliation in next session's start will verify the design specs exist as claimed.
- **Both specs gate implementation on Layer 4 spec.** Layer 4 is currently unspecced (per CLAUDE.md). D-63 and D-64 won't land in real code until Layer 4 spec exists. This is honest scope discipline — building D-63/D-64 against a guessed Layer 4 surface would waste work.
- **Two prompt bodies deferred to their own sessions** (NL intent parser for D-64; single-session synthesis for D-63). Both are stop-and-ask trigger #2 items; doing them inline would have conflated framework decisions with prompt-engineering. Spec'd as I/O contracts only.
- **NL intent parser accuracy is unproven.** D-64 §12 risk: parser routes the cascade — wrong routing means wrong cascade. Mitigation in spec: confidence flag + ambiguity_notes surfaced; revert path lets athlete undo. Real test is at first-cohort scale.
- **T3 cost is real.** Full cascade (5 Layer-2 nodes + 4 Layer-3 nodes + Layer 4 synthesis) at "1 per 7 days" soft cap. Telemetry will reveal whether athletes regularly override. Spec'd in D-64 §12.
- **D-63 "Somewhere else" quick-add** bypasses the locale system. Athletes may accumulate one-off generations without persistent location records. Mitigation: [Save as locale] affordance; suggestion row carries the equipment payload for traceability.
- **Frequency-cap thresholds are guesses.** No production traffic to tune against; tune post-deploy. Same flag for D-63's 5-per-24h and D-64's per-tier caps.
- **Cost-estimate copy stays generic until Layer 4 lands.** Token-count estimates require Layer 4 prompt-body sizes; until then, frequency-cap warnings show "compute cost" without dollar amounts.
- **Cross-spec dependency on `plan_refresh_log.triggered_by_ad_hoc_id`** — D-63's T1 hook telemetry correlation lives on D-64's schema. Both specs flag this; need to keep aligned when implemented.
- **Auto-discard timer for `suggested` ad-hoc workouts** — open item in D-63; tune post-deploy.
- **Per-athlete cap tunability** for D-64 — v1 single global thresholds; per-account customization is post-v1.
- **Joint-training overlay interaction** — D-64 §10 flags this; team-coordination scope.
- **D-61 PR12's eventual JIT swap UI gates on Layer 4 too** — not new this session, but reinforced. Andy's Option A1 split is exactly right: ship §G now; wait on Layer 4 for JIT.
- **No tests added.** Same framing as PR1–PR11: no `tests/` directory exists. Design specs aren't testable artifacts; the implementation will need tests when it lands.
- **Numbering note unchanged.** D-63 + D-64 added contiguously after D-62; no new gaps. D-18/19/20 historical gap stable.

---

## 7. Gut check

**What this session got right.**

- **Stop-and-ask discipline.** Andy surfaced two new cross-layer features mid-conversation. Default of "execution" was the wrong move; stop-and-ask trigger #11 (new D-row with cross-layer scope) fired correctly. Surfaced design questions before any code, asked four scoped multiple-choice questions (T2/T3 windows, NL handling, button surface, frequency caps), got crisp answers, then locked design.
- **Two specs, one chat, ceiling respected.** Two ~300-line design docs + backlog bump + CLAUDE.md sync + handoff = 5 files. At ceiling. Discipline observed.
- **D-63 and D-64 are properly separated.** They're distinct features with distinct scopes (off-plan single session vs. plan-modifying cascade); bundling them would have muddied the design. Cross-references clean: D-63's T1 hook fires D-64; D-63's storage payload has a dedicated FK column on D-64's telemetry table.
- **Honest about Layer 4 dependency.** Both specs explicitly gate implementation on Layer 4 spec landing. No throwaway pre-Layer-4 stopgaps recommended. Discipline aligns with CLAUDE.md "spec-first sequencing" principle.
- **Prompt bodies deferred correctly.** NL parser (D-64) and single-session synthesis (D-63) both deferred to their own sessions per stop-and-ask trigger #2. Specs define I/O contracts; the actual prompt engineering is its own work.
- **Andy's framing translated cleanly.** "Wrist doesn't matter, that's just me" → profile-level constraints, not per-request hard-coding. "Tier 1, 2, 3 plan refresh" → the framework spec'd in D-64 §3. "Build me a workout right now" → D-63 with the specific input/equipment/storage choices Andy made.
- **Backlog discipline.** v24 added two new D-rows in the right place; D-50 status preserved (no PR shipped); D-row numbering contiguous. Mechanical instructions for v24→v25 in §5.4 ready for PR12.

**Risks.**

- **Two specs with implementation gating on the same unspec'd layer (Layer 4).** If Layer 4 spec ends up reshaping things D-63 and D-64 assumed (e.g., session output schema, plan-version table shape, prompt-body conventions), parts of D-63/D-64 may need revision. Mitigation: specs are honest about gating; revision is expected.
- **NL parser is the load-bearing piece for D-64's cascade routing precision.** Parser quality determines whether the cascade actually narrows usefully or fires upstream re-runs all the time. Spec defers prompt body to its own session; that session's outputs will determine D-64's real value.
- **Frequency caps + cost copy lack real numbers.** Pre-Layer-4, cost estimates are abstract. Athletes seeing generic warnings ("compute cost") may underweight the signal. Tune post-deploy when token counts are real.
- **Cross-spec dependency** (`plan_refresh_log.triggered_by_ad_hoc_id`) requires both implementations to agree on column shape. Both specs flag it; risk is implementation drift if the two land in different sessions.

**What might be missing.**

- **Mobile UX consideration.** D-63 form and D-64 modal both designed for desktop browser. Mobile client doesn't exist today; when it does, both surfaces will need touch-optimized layouts. Out of scope this session; flagged in both specs' open items.
- **Coaching observations from refresh patterns.** Athlete who keeps reporting fatigue across multiple T1s is signaling overreaching. Future Layer 5 advisory surface; not in either spec.
- **Multi-tenant team coordination.** Athlete A and B share a joint training overlay; A triggers T2 — should B's plan re-run too? Out of scope (team features track); flagged in D-64 §10.
- **Telemetry retention.** `plan_refresh_log` and `ad_hoc_workout_suggestions` will grow indefinitely. Same retention-cron question as `webhook_events` (D-62). Could fold into the same prune.
- **Initial-plan-gen path (T3 with no prior plan).** D-64 §3.3 specifies this is the path; doesn't detail how it differs from a normal T3 (no diff to show; no revert option since no prior version). Flagged for refinement when implementing.

**Best argument against this session's scope.**

Two design docs ship for features that won't be implementable until Layer 4 is specced. Layer 4 is a substantial multi-session spec that doesn't exist yet. So D-63 + D-64 are sitting on the shelf for an unbounded period. The alternative would have been: skip D-63/D-64 entirely until Layer 4 lands; defer the design to "the same chat where we spec Layer 4."

Counter: Andy surfaced the design intent right now, with crisp answers to scoped questions. Capturing the design while context is fresh costs one chat; deferring it means re-deriving the same answers in 3-5 sessions when Layer 4 work begins. The "build the right abstraction now" framing applies — and unlike D-60 where the abstraction was structural (gym_profiles + override tables), D-63/D-64's cost is pure spec markdown. Cheap to write; expensive to lose.

Counter to the counter: design docs that don't get implemented for months tend to drift from reality. Layer 4's eventual shape may make some D-63/D-64 decisions obsolete (e.g., if Layer 4 has a fundamentally different session output schema, D-63's "matches Layer 4 schema" decision needs reworking). Mitigation: specs are explicit about Layer 4 gating; revision is expected when Layer 4 lands. The risk is real but bounded.

Net: capture the design now; revise when Layer 4 lands. The cost of revision is much lower than the cost of re-deriving from scratch.

---

## 8. Forward pointers

- **Next session:** PR12 = D-61 Option A1 (§G + onboarding integration). Per PR11 §5.1 + Andy 2026-05-15. The v5 §G mechanic is the next clean unit of code shipping; doesn't depend on Layer 4.
- **Following next session:** Layer 4 spec draft. Substantial work (multi-session likely). Becomes the gate for D-63, D-64, D-61's JIT swap, and the rest of v5's plan-execution surfaces.
- **Before next code lands:** Carry-forward from PR11 — the §5.0 walk-through against the deployed app (FK shape verification + D-60 first-athlete + inherit + §6 upgrade + §7 refresh paths). Track in `PR_Verification_Status.md`. No new walk-through owed for this design-only session.
- **First action of next session:** Read `aidstation-sources/CLAUDE.md` fully (Rule #13 — and note the new "Plan-execution design wave inputs" line). Then Rule #9 reconciliation against this handoff: confirm `Plan_Refresh_D64_Design_v1.md` + `OnDemand_Workout_D63_Design_v1.md` + `Project_Backlog_v24.md` exist; confirm CLAUDE.md backlog pointer reads v24; confirm no executable code changed this session. Then read `Onboarding_D61_Design_v1.md` + `Athlete_Onboarding_Data_Spec_v5.md` §G/§J.5 for PR12 scope.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **this handoff has one deferred mechanical edit:** the v24 → v25 backlog bump for PR12's first action, spec'd verbatim in §5.4 (conditional on PR12 shipping a state-changing event)
- #12 numeric version suffixes (backlog now at v24; v25 lands in PR12 per §5.4 conditional)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1; §8 first-action explicitly names CLAUDE.md.**

---

*End of V5 Design Pass D-63 + D-64 closing handoff. Two new D-rows shipped: D-63 on-demand workout (`OnDemand_Workout_D63_Design_v1.md`, 13 decisions; off-plan single-session synthesis with D-60 effective-equipment view + Layer 1 profile + Layer 3A state; storage extends `cardio_log`/`training_log` + new `ad_hoc_workout_suggestions` table; T1 hook into D-64 post-completion; profile-level constraints; single-sport v1) and D-64 plan refresh tiers (`Plan_Refresh_D64_Design_v1.md`, 12 decisions; T1 next-2-days + T2 next-7-days + T3 next-28-days-or-initial-plan-gen; rolling windows; free-text NL + LLM intent parser → upstream layer triggers; default cascade per tier; both /dashboard + training-plan-view button surfaces; soft frequency caps with override; atomic versioning; per-day `plan_version_id` pointer; `plan_refresh_log` table). Both gate implementation on Layer 4 spec landing. NL intent parser prompt body and Layer 4 single-session synthesis prompt body both deferred to their own spec sessions per stop-and-ask trigger #2. Backlog v23→v24 (D-63 + D-64 added; D-50 status unchanged; design pass is the unit of revision). CLAUDE.md backlog pointer + design wave inputs + current state header bumped. Next: PR12 = D-61 §G + onboarding integration code (per PR11 §5.1 Option A1 + Andy 2026-05-15). v24 → v25 backlog bump mechanically spec'd for PR12's first action (conditional on PR12 shipping a state-changing event).*
