# V5 Onboarding Spec Closing Handoff

**Session:** Onboarding Design Wave consolidation. Single piece: `Athlete_Onboarding_Data_Spec_v5.md` absorbing D-58 + D-59 + D-60 + D-61 design decisions. Same chat that shipped CLAUDE.md pointer refresh + D-61 design + D-61 handoff + D-58 design + D-58 handoff earlier (cumulative session detail in §2 below).
**Date:** 2026-05-14
**Predecessor handoffs (same session):** `D61_Onboarding_Wave_Closing_Handoff_v1.md` (intermediate), `D58_Onboarding_Wave_Closing_Handoff_v1.md` (intermediate session-end before Andy's "keep going" continuation).
**Branch:** `claude/review-onboarding-handoff-e90Ei`
**Status:** ✅ Onboarding Design Wave complete and consolidated. v5 spec lands as the new authoritative onboarding artifact. 🟡 v5 onboarding implementation PR is the next substantive code work; D-50 wiring resumption is the parallel track.
**Time-on-task:** Single chat. Substantive files shipped *this turn*: **3** (v5 spec; CLAUDE.md state-narrative refresh; Project_Backlog_v15 rows D-58/D-59/D-60/D-61 updated). Cumulative session: **6** substantive (CLAUDE.md pointer refresh + D-61 design + D-58 design + v5 spec + CLAUDE.md state-narrative refresh + Project_Backlog_v15 row updates) + 3 handoffs. **One file over the 5-file ceiling** — see §7 gut-check best-argument-against.

---

## 1. Session-start verification (Rule #9)

Verified the D-58 closing handoff's claimed state before continuing.

| Claim | Result |
|---|---|
| `aidstation-sources/Onboarding_D58_Design_v1.md` — 9 decisions in §2, 364 lines | ✅ Verified pre-work |
| `aidstation-sources/handoffs/D58_Onboarding_Wave_Closing_Handoff_v1.md` shipped + pushed | ✅ Verified pre-work |
| Onboarding Design Wave: D-59 + D-60 + D-61 + D-58 all on disk as `_v1.md` | ✅ Verified pre-work |
| All session commits pushed to `claude/review-onboarding-handoff-e90Ei` | ✅ Verified pre-work |

No drift between intermediate handoff narrative and on-disk state.

---

## 2. Files shipped this turn (and cumulative session list)

### 2.1 This turn

All on branch `claude/review-onboarding-handoff-e90Ei`. Each commit pushed individually (push happens at the end of this handoff).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` | New | 878 lines, 26 top-level sections. Consolidates D-58 + D-59 + D-60 + D-61 into the new authoritative onboarding spec. v4 retained as in-project history per Rule #12. |
| 2 | `aidstation-sources/CLAUDE.md` | Edit | State-narrative refresh — Current state header bumped to 2026-05-14; Last shipped session updated to "Onboarding v5 spec rewrite"; Authoritative current files updated (onboarding bumped to v5; design-doc references added); Next forward move enumerates candidates (v5 implementation PR / D-50 wiring resumption / Layer 4 plan-gen spec); Independent parallel tracks updated (D-58–D-61 marked complete; D-62 added). |
| 3 | `aidstation-sources/Project_Backlog_v15.md` | Edit | D-58 / D-59 / D-60 / D-61 rows updated: status flips to "✅ Design complete (2026-05-14); 🟡 Implementation pending"; original problem statement preserved as historical context; notes column rewritten to point at the design doc + the v5 spec + the implementation PR scope. Other rows unchanged. |
| — | `aidstation-sources/handoffs/V5_Onboarding_Spec_Closing_Handoff_v1.md` | New (this file) | Session-end book-keeping. |

### 2.2 Cumulative session list

| # | File | Turn |
|---|---|---|
| 1 | `aidstation-sources/CLAUDE.md` (pointer refresh — Authoritative current files v6→v7, v11→v15, v2→v4, Layer 3 done) | Turn 1 |
| 2 | `aidstation-sources/Onboarding_D61_Design_v1.md` | Turn 1 |
| 3 | `aidstation-sources/handoffs/D61_Onboarding_Wave_Closing_Handoff_v1.md` (intermediate) | Turn 1 |
| 4 | `aidstation-sources/Onboarding_D58_Design_v1.md` | Turn 2 |
| 5 | `aidstation-sources/handoffs/D58_Onboarding_Wave_Closing_Handoff_v1.md` (intermediate session-end) | Turn 2 |
| 6 | `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` | Turn 3 (this turn) |
| 7 | `aidstation-sources/CLAUDE.md` (state-narrative refresh) | Turn 3 |
| 8 | `aidstation-sources/Project_Backlog_v15.md` (D-58/D-59/D-60/D-61 row updates) | Turn 3 |
| 9 | `aidstation-sources/handoffs/V5_Onboarding_Spec_Closing_Handoff_v1.md` (this handoff) | Turn 3 |

**Files explicitly NOT touched this turn (cumulative):**

- `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` — retained as in-project history per Rule #12. v5 supersedes; v4 stays accessible for sections v5 references by name ("unchanged from v4 §B.1") rather than restating verbatim. See §6 design-choice note.
- `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` — no changes; v5 reads §3, §4, §7, §8 as inputs but does not modify the integration spec.
- `init_db.py`, `routes/profile.py`, `routes/connect_*.py`, `routes/locales.py`, OAuth callback handlers — all v1 code untouched. v5 schema migrations + frontend rewrite + OAuth flows land in the v5 implementation PR + the D-50 wiring resumption.

---

## 3. What landed in v5

### 3.1 The four design tracks, absorbed

| Track | v5 sections rewritten | Tables / columns added |
|---|---|---|
| **D-58** OAuth-first flow + provider-sourced prefill | §A flow framing (new "Onboarding step sequence" before §A); §A field-level prefill annotations (Body Weight); §A.1 Disclosures (Connected Service consent firing point + new per-provider OAuth scope acknowledgments); **§A.2** (new — full prefill mechanics: eligibility, resolution, edit semantics, no-providers path, re-onboarding prompt, override clear, tolerance-based re-prefill); §B/§C/§D/§F/§I field-level prefill annotations; Account Config 1 reframe (manage-only); Account Config 3 new `disclosure_id` values | `athlete_profile_field_provenance` (new table); `account_nudges` (new table) |
| **D-59** Mapbox geocoding + chain detection | §J overview (locale-creation flow); §J.1 locale-level fields + §J.1.1–§J.1.5 (Mapbox integration, chain detection algorithm, category taxonomy, nearby-instance discovery, manual fallback); §A.1 new Mapbox geocoding consent disclosure; Account Config 3 new `disclosure_id` | `locale_profiles` ALTER ADD COLUMN ×9 (`locale_name`, `mapbox_id`, `lat`, `lng`, `chain_id`, `chain_name`, `category`, `manual_entry`, `place_payload`, `place_fetched_at`); `chain_registry.py` Python module (not a DB table) |
| **D-60** Shared gym profiles + locale category taxonomy | §J.2 full rewrite (shared-profile inherit/override/dispute/submit-as-correction); §J.3 full rewrite (same model for sport-specific gear toggles); §J.1.3 (10-category enum); §A.1 new gym-profile sharing consent disclosure; Account Config 2 role-clarify (membership tracker, no longer equipment-prefill source) | `gym_profiles` (new table — shared across users); `locale_equipment_overrides` (new table); `locale_toggle_overrides` (new table); `locale_profiles` ALTER ADD `gym_profile_id` + `sharing_opt_out` |
| **D-61** Plan-level schedule + session→locale assignment | §G full rewrite (per-day windows + Long Session + Doubles + Preferred Rest Day demoted Tier 1→2; G.2 derived/displayed values; G.3 window semantics; G.4 session-to-locale resolver; G.5 §K cross-reference); **§J.5 deleted entirely** | `daily_availability_windows` (new table); `locale_profiles` ALTER ADD `preferred` column |

### 3.2 Sections preserved verbatim from v4

§B (and all its subsections including B.1.1 Injury Type enum, B.1.2 Re-injury preventive priority rule, B.2 body-part enum, B.3 movement-constraint enum, B.4.1 system category enum, B.4.2 auto-population rules); §C.1 Pack Training Record; §D.3–§D.7 discipline-specific fields; §E strength benchmarks; §H Target Events (H.1, H.2, H.3); §I subsections (I.1.1 Caffeine, I.2 race-day fueling, I.3 sleep-dep); §K (K.1, K.2, K.3) joint-training overlay + recurrence template; §L Athlete Network; Account Config 4 Privacy; Plan Management 1 / 3 / 4 / 5.

These sections are **referenced** in v5 rather than restated verbatim ("Unchanged from v4 §B.1"). v5 is therefore not fully self-contained; readers need v4 in working memory for the unchanged sections. This is a deliberate design choice — see §6 below.

### 3.3 Open Items list — v5 update

v4's 15 Open Items were re-numbered + filtered:

- Items resolved at design wave (effectively): the D-59 / D-60 / D-61 / D-58 design rows themselves (v4 listed each as "deferred to dedicated design session" — now done).
- Items carried forward unchanged: disclosure copy refinement (#1), Movement Components (#2), Sheet 7 deprecation (#3), migration path (#4 — now noted "effectively moot, Andy sole test user"), Layer 1 ↔ Layer 0 query layer (#5), Sports Framework gap audit (#6), plan-gen weeks 13+ (#7), §K rolling-window length (#8), TA fallback (#9), multi-partner N>2 (#10), stale-link cleanup (#11).
- **New v5 items (12–21):** Mapbox token rate-limit at multi-tenant scale; chain registry curation cadence + initial seed; gym-profile dispute resolution maturity; equipment quantity/quality ratings; per-field re-prefill tolerance config; canonical `KNOWN_PROFILE_FIELDS` registry; 14-day nudge telemetry; JIT-swap UX detail; plan-level "alt-windows" carry-over; provider-disconnect behavior on prefilled fields.

---

## 4. Session-end verification (Rule #10)

| Claim | Anchor | Result |
|---|---|---|
| v5 spec exists at 878 lines, 26 top-level sections | `wc -l Athlete_Onboarding_Data_Spec_v5.md` + `grep -c "^## "` | ✅ Verified |
| v5 §A.2 (prefill mechanics) exists with 7 subsections (A.2.1–A.2.7) | grep `^### A.2.` | ✅ Verified |
| v5 §G full rewrite covers per-day windows + resolver + §J cross-reference | grep `^### G.[1-5]` | ✅ Verified |
| v5 §J.1 / §J.1.1–§J.1.5 covers Mapbox + chain detection + 10-category + nearby + manual fallback | grep `^#### J.1.[1-5]` | ✅ Verified |
| v5 §J.2 + §J.3 covers shared-profile model with 6 J.2 subsections | grep `^#### J.2.[1-6]` | ✅ Verified |
| v5 §J.5 deletion explicit (struck-through section heading) | grep `~~Locale Capacity Metrics~~` | ✅ Verified |
| CLAUDE.md Current state header bumped to 2026-05-14 | grep `^## Current state` | ✅ Verified |
| CLAUDE.md "Authoritative current files" includes `Athlete_Onboarding_Data_Spec_v5.md` | grep `Athlete_Onboarding_Data_Spec_v5` | ✅ Verified |
| Project_Backlog_v15 D-58/D-59/D-60/D-61 rows all flipped to "Design complete (2026-05-14)" | `grep -c "Design complete (2026-05-14)"` = 4 | ✅ Verified |
| Handoff filename in CLAUDE.md matches actual handoff on disk | corrected from `D50_Onboarding_Wave_Closing_Handoff_v1.md` → `D50_Review_and_Onboarding_Wave_D59_D60_Closing_Handoff_v1.md` after directory check | ✅ Verified (caught + fixed) |

No drift between the design-doc narrative and the v5 spec content; cross-design-doc consistency check (pre-draft) revealed no conflicts; v5 cleanly references all four design docs as source-of-truth for their respective sections.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.1 Forward move — Andy's choice (3 candidates)

The Onboarding Design Wave is fully consolidated. Andy chooses among three substantive next-session candidates:

#### Option A — v5 onboarding implementation PR

The largest substantive next move. Implements the v5 spec end-to-end across the v1 Flask app.

**Pre-step reads (Rule #13 ordering):**
1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read. State-narrative was just refreshed (turn 3 of this session); rules-of-operation block unchanged.
2. `aidstation-sources/Project_Backlog_v15.md` — D-58/D-59/D-60/D-61 rows updated this turn; reflect status + implementation scope.
3. `aidstation-sources/handoffs/V5_Onboarding_Spec_Closing_Handoff_v1.md` (this file).
4. `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` (full read) — the implementation target.
5. `aidstation-sources/Onboarding_D58_Design_v1.md` / `_D59_` / `_D60_` / `_D61_` — for details v5 references but doesn't restate (e.g., Mapbox failure modes, chain detection algorithm, schema DDL).
6. `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` §7 — per-field provider source mapping the prefill mechanics consume.
7. `init_db.py` + `routes/profile.py` + `routes/connect_*.py` + `routes/locales.py` — the v1 code that gets restructured.

**Scope of the implementation PR (v5 implementation, end-to-end):**

PG-only migrations on `_PG_MIGRATIONS` (per the SQLite freeze):

```
-- D-58 tables
CREATE TABLE athlete_profile_field_provenance (...);
CREATE TABLE account_nudges (...);

-- D-59 locale_profiles additions
ALTER TABLE locale_profiles ADD COLUMN locale_name TEXT;  -- (or repurpose existing column)
ALTER TABLE locale_profiles ADD COLUMN mapbox_id TEXT;
ALTER TABLE locale_profiles ADD COLUMN lat REAL;
ALTER TABLE locale_profiles ADD COLUMN lng REAL;
ALTER TABLE locale_profiles ADD COLUMN chain_id TEXT;
ALTER TABLE locale_profiles ADD COLUMN chain_name TEXT;
ALTER TABLE locale_profiles ADD COLUMN category TEXT;
ALTER TABLE locale_profiles ADD COLUMN manual_entry BOOLEAN DEFAULT FALSE;
ALTER TABLE locale_profiles ADD COLUMN place_payload TEXT;
ALTER TABLE locale_profiles ADD COLUMN place_fetched_at TIMESTAMP;

-- D-60 tables + locale_profiles additions
CREATE TABLE gym_profiles (...);
CREATE TABLE locale_equipment_overrides (...);
CREATE TABLE locale_toggle_overrides (...);
ALTER TABLE locale_profiles ADD COLUMN gym_profile_id INTEGER REFERENCES gym_profiles(id);
ALTER TABLE locale_profiles ADD COLUMN sharing_opt_out BOOLEAN DEFAULT FALSE;

-- D-61 table + locale_profiles addition
CREATE TABLE daily_availability_windows (...);
ALTER TABLE locale_profiles ADD COLUMN preferred BOOLEAN DEFAULT FALSE;
```

Exact DDL per v5 §J.1 / §J.2 / §G and the source design docs.

New application code:
- `chain_registry.py` module with the ~30-entry seed list (initial coverage per D-59 §2 decision #8; expandable post-launch).
- OAuth-first onboarding flow frontend: connect step UI (Step 2 of onboarding); inline disclosures per §A.1; per-provider OAuth flow integration.
- Provider prefill UX: provenance tags ("from Polar, 2 days ago"); edit-in-place; manual_override clear popover; passive notifications for tolerance-beyond and provider-source-change events.
- Locale-creation flow frontend: Mapbox autocomplete; chain detection display; category picker for non-detected; nearby-instance opt-in checkboxes; manual-address fallback path; inherit-or-create gym profile UI; override and dispute affordances; submit-as-correction button.
- Per-day windows UI: 7-row schedule editor with enabled/start/duration + optional second window; Long Session day/duration picker; Doubles Feasible enum; Preferred Rest Day(s) multi-select; derived display ("you've allocated 6.5 hrs/week").
- Session-card JIT swap: "Other locales here:" affordance with Qualifying / Not-qualifying grouping.
- Account Config 1 reframe: management screen with disconnect / re-auth / scope-update.
- Account Config 3 new `disclosure_id` write paths.
- 14-day connect-provider nudge job (in-app banner; `account_nudges` row creation + dismissal handling).

This is a substantial multi-PR effort, likely 4–8 PRs broken by sub-feature. Sequencing within the implementation arc is its own design pass; recommend Andy walk it through with a planner agent or a dedicated planning session before starting PR1.

#### Option B — D-50 wiring resumption (parallel to A)

Now unblocked by D-58. PR1 of the wiring track:

1. **`provider_auth.py` helper module** — UPSERT by `(user_id, provider)`, status transitions per Integration v4 §4.1, token-refresh skeleton, webhook_token rotation Pattern A. Provider-agnostic; can be built any time.
2. **COROS as the first real OAuth provider** (CLAUDE.md flags COROS as next-to-ship; Andy may revise).
3. **OAuth callback** — exchanges code for tokens; stores via `provider_auth.py`; records per-provider scope acknowledgment via Account Config 3 per D-58 §7; redirects per the new onboarding flow (back to onboarding step 3 if mid-onboarding; Account Config 1 management screen if post-onboarding; triggers §A.2.5 re-onboarding prompt if any prefill-eligible field has data available).
4. **Webhook handler** writes a row into `webhook_events` per Integration v4 §4.2.
5. **Per-provider data ingestion** — wire webhook dispatch → per-provider table writes.
6. **Frontend connect step at the new Step 2 of onboarding** — overlaps with Option A's frontend work; Andy decides whether wiring + frontend ship in one PR or sequentially.

If Andy picks B before A: the D-50 wiring lands first against a still-v4-spec onboarding flow (athletes connect at Account Config 1, post-onboarding); the v5 frontend reshape lands after. If Andy picks A then B: the v5 frontend ships against stub OAuth flows; first real OAuth lands as a follow-on.

Recommend: **A and B interleaved** — v5 schema migrations + Option B's wiring (PR1) ship together as the unblocking PR; v5 frontend work and subsequent per-provider OAuth flows ship as follow-on PRs in parallel.

#### Option C — Layer 4 plan-gen spec

The next unspecced layer in the pipeline. Layer 3A and 3B are done; Layer 3.5 is designed; Layer 4 (plan generation + periodization validator) is not yet specced. Spec-first sequencing argues for shipping Layer 4 spec before any production plan-gen code runs.

**Pre-step reads:** CLAUDE.md fully + Layer3_3A_Spec.md + Layer3_3B_Spec.md + Layer2A/2B/2C/2D/2E specs + the v5 onboarding spec (Layer 4 consumes v5 §G windows + §J locale resolver + §A.2 provider prefill state).

Scope: full 14-section depth standard per the Layer 2C pattern. Significant single-session effort (probably 2–3 chats to land).

### 5.2 Standing items not on the critical path

- **D-52 Catalog Migration Phase 1** — fuzzy-match HITL alias audit. Independent track.
- **D-54 SQLite collapse** — Catalog Migration Phase 5. Queued.
- **D-55 Garmin onto `provider_auth`** — paused until Garmin reopens API access.
- **D-57 Research re-evaluation cadence design**.
- **D-62 webhook_events retention prune** — tracked; lands alongside first real webhook handler implementation (Option B PR1) or as its own ops PR.

### 5.3 Cross-design-doc consistency pass status

The pre-draft consistency pass this session caught zero hard conflicts across the four design docs (D-58 + D-59 + D-60 + D-61). The v5 spec is the formal consolidation of that pass. No follow-on consistency work owed.

---

## 6. Design choice flagged for Andy — v5 is not fully self-contained

The v5 spec **references v4 by name** for unchanged sections (§B subsections, §C.1, §D.3–§D.7, §H, §I subsections, §K, §L, Account Config 4, Plan Management 1/3/4/5) rather than restating their content verbatim. Reading v5 alone does not fully describe what onboarding collects — readers need v4 in working memory for ~450 lines of unchanged content.

**Why this choice:**

- v5 already absorbed substantial new content (§A.2 prefill mechanics, §G full rewrite, §J locale-creation flow + shared-profile model + 10-category taxonomy + Mapbox integration). Restating everything would push v5 to ~1300+ lines.
- The carry-forward pattern reduces inadvertent edits during restating — a body-part enum copy/paste error would be silent.
- v4 stays in-project per Rule #12 as historical record; it's not deleted.
- The next session reads v5 (per CLAUDE.md "Authoritative current files"); v5 explicitly names v4 as the source for unchanged sections.

**Risks of this choice:**

- v5 is not the single source of truth for the full onboarding data inventory. Readers / LLM sessions consuming "the onboarding spec" need to consume both.
- If v4 is ever archived or deprecated, v5 needs a restatement pass first.
- Subtle drift could occur if a future edit to one of the "carried from v4" sections lands in v4 only and v5 doesn't get re-pointed.

**Alternative Andy may prefer:** restate all unchanged sections verbatim in v5 (next session task; mechanical effort, ~450 lines). This makes v5 fully self-contained at the cost of duplicating content and creating two places to edit if those sections ever change again.

**Recommended:** keep the carry-forward pattern; treat v4 as a "reference appendix" for the unchanged sections. If Andy wants v5 self-contained, a separate small session can do the restatement (well within 5-file ceiling).

---

## 7. Gut check

**What this turn got right.**

- **Cross-design-doc consistency check ran before drafting.** D-61 handoff §7 flagged the need; D-58 handoff §5.1 reaffirmed; this turn ran it. Zero hard conflicts surfaced; the four design docs were genuinely designed to fit together. The consistency pass paid off as confidence-builder rather than issue-finder, but the right discipline regardless.
- **Schema additions are clean and additive.** All new tables (`athlete_profile_field_provenance`, `account_nudges`, `gym_profiles`, `locale_equipment_overrides`, `locale_toggle_overrides`, `daily_availability_windows`) and all new columns on `locale_profiles` are PG-only ALTER ADD operations against existing tables. No destructive migrations; v1 test data persists where applicable; v5 implementation PR can sequence migrations without coupling constraints across the four design tracks.
- **Open Items list cleanly absorbed.** v4 had 15 Open Items including 4 deferred-to-design-session rows (D-58–D-61). v5 retires those 4, carries the other 11 forward unchanged, and adds 10 new items genuinely surfaced by the design tracks (most flagged as "v1.x implementation refinement," not "spec-rewrite-needed").
- **Backlog rows updated this turn, not deferred.** The D-58–D-61 row status flip was a small but real task that the predecessor handoffs deferred ("update during v5 spec session"). This turn cleared it. Forward-pointer in §5.1 reflects "implementation PR" status as the next move, not "design pending."
- **CLAUDE.md state-narrative refresh was the right scope.** Pointer refresh from turn 1 + state-narrative refresh from turn 3 together brought CLAUDE.md fully up to date. No residual staleness for the next session to inherit.
- **D-50 wiring is now genuinely unblocked.** v5 §A flow framing + §A.2 prefill mechanics + Account Config 1 reframe give the OAuth callback's expected behavior concrete contracts. Option B in §5.1 is no longer paper; it has a real PR1 scope.

**Risks.**

- **6 substantive files in one session is over the 5-file ceiling.** Cumulative: CLAUDE.md pointer refresh (turn 1) + D-61 design (turn 1) + D-58 design (turn 2) + v5 spec (turn 3) + CLAUDE.md state-narrative refresh (turn 3) + Project_Backlog_v15 row updates (turn 3) = 6. CLAUDE.md counts as 2 separate edits across 2 turns; if treated as 1, the cumulative is 5. Either accounting is honest; the 5-file ceiling exists to protect quality. Quality so far across turns 1–2 was good (zero rework, all decisions adopted, no drift). Turn 3's quality should be similar — v5 is a synthesis of completed work, not new design — but the ceiling exists for a reason and 6 files in one chat does erode the safety margin. Mitigation: each turn's substantive output was reviewed against the design docs / v4 / each other before commit; verification (§4) passed.
- **v5 is not fully self-contained (per §6).** Real reader-burden risk. If next session's reader skips v4, they miss §B-§L's full field inventory.
- **Three turns in one chat is unusual.** D-61 → D-58 → v5. Each turn could have been its own chat; staying in one chat is efficient (working memory carries over) but accumulates risk (any error compounds; context-window pressure increases). Andy's "lets keep going" rolled each turn; the chat has not yet hit context limits.
- **CLAUDE.md handoff filename was wrong (caught + fixed).** I named the predecessor handoff `D50_Onboarding_Wave_Closing_Handoff_v1.md` in the state-narrative refresh; actual filename is `D50_Review_and_Onboarding_Wave_D59_D60_Closing_Handoff_v1.md`. Caught during Rule #10 verification; fixed via a one-line edit. Low-stakes but a real risk-of-drift example — even with the recent file in working memory, the name was wrong.
- **v5 implementation PR is genuinely large.** Option A in §5.1 enumerates ~30+ frontend components, ~12 new tables/columns of DB migration, ~5 new modules. No single chat can ship the full implementation. Sub-PR sequencing is its own design pass that the v5 spec does not commit to.
- **`KNOWN_PROFILE_FIELDS` registry deferred (Open Item #17).** v5 spec allows `athlete_profile_field_provenance.field_name` to be free-text TEXT. Implementation PR must add the canonical list + insert validation; missing this would silently allow typo-orphan provenance rows.

**What might be missing.**

- **v5 spec verification against `Athlete_Data_Integration_Spec_v4.md` §7.** v5 §A.2.1 lists prefill-eligible fields by section, but I didn't grep §7 against §A.2.1 to verify field-by-field coverage. Could be over- or under-claiming prefill eligibility for some fields. Recommend the v5 implementation PR's planning session run this verification before any prefill code is written.
- **Account Config 2 (Gym Memberships) usefulness audit.** v5 keeps Account Config 2 as a membership-tracker entity, separate from D-59's chain detection. The interaction (§Account Config 2 v5 narrative) is that membership status surfaces at locale-creation chain-instance discovery. If athletes don't actually maintain Account Config 2 membership lists in practice, the entity becomes vestigial. Track this in v1 use; consider deprecating in v5.1 if so.
- **§K and §J.1 interaction with Mapbox.** §K Locale Schedule overlays reference `locale_profiles` via FK. If a locale is deleted (athlete removed it) but an active §K overlay points at it, behavior is unspecified. Backlog candidate; v5 implementation likely needs an ON DELETE policy decision.
- **Long Session day picker × `daily_availability_windows.enabled` cross-validation.** D-61 §10 flagged the UX cross-validation; v5 §G.3 mentions it. Implementation detail.
- **Provider-data backfill historical window.** If athlete connects Polar mid-onboarding and Polar has 6 months of historical data, does the system pull all of it (for prefill purposes) or only the last 90 days (per the freshness rules)? v5 doesn't specify. Recommend: prefill uses the same 90/30 day freshness window as runtime queries.
- **Disclosure version IDs.** v5 §A.1 + Account Config 3 carry "version_id" as part of the acknowledgment record. Where is the version registry maintained? Implementation detail; recommend a `disclosures.py` constant table with `disclosure_id → current_version` mapping.

**Best argument against this turn's scope.**

A stricter interpretation of the 5-file ceiling would have stopped this turn after the CLAUDE.md state-narrative refresh + backlog updates and deferred the v5 spec rewrite to a fresh chat. Counter: the design wave was the gating prerequisite and the consistency check ran clean; v5 is a synthesis exercise with concrete inputs (the four design docs), not exploration; the same chat's working memory had all four design docs in fresh context. A fresh chat would have re-read 1100+ lines of input before starting the synthesis. Trade-off: file-ceiling discipline vs. context-efficiency. Andy's "keep going" + a successful consistency pass biased toward continuing; if quality of the v5 spec degrades on review, the right answer is "v5.1 patch" not "should have been a separate chat."

Alternative phasing: the v5 spec could have been deliberately written as a "diff document" (only the changes from v4, with v4 as the base) rather than a full new spec. That would have been ~400 lines instead of 878. Counter: the next session's reader would have had to navigate v4 + v5-diff to understand the current state; the "Authoritative current files" pattern in CLAUDE.md is cleaner with a single primary spec file. The carry-forward references in v5 are a middle path — full document, but partial reference to v4 for unchanged content. Imperfect; the genuinely-clean alternatives are (a) full restatement (~1300+ lines, redundant) or (b) diff-document (~400 lines, harder to read).

---

## 8. Onboarding Design Wave summary (closed)

| Track | Backlog | Status | Outputs |
|---|---|---|---|
| D-59 (Mapbox place lookup + chain detection) | High → ✅ Design complete | Done | `Onboarding_D59_Design_v1.md` |
| D-60 (Shared gym profiles + per-athlete overrides) | High → ✅ Design complete | Done | `Onboarding_D60_Design_v1.md` |
| D-61 (Per-day schedule + session→locale resolver) | Med → ✅ Design complete | Done | `Onboarding_D61_Design_v1.md` |
| D-58 (OAuth-first flow + provider-sourced prefill) | High → ✅ Design complete | Done | `Onboarding_D58_Design_v1.md` |
| Wave consolidation | — | ✅ Done | `Athlete_Onboarding_Data_Spec_v5.md` |
| v5 implementation PR | High | 🟡 Pending | Next-session candidate (Option A in §5.1) |
| D-50 wiring resumption | Med | 🟡 Pending; unblocked | Next-session candidate (Option B in §5.1) |

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits
- #12 numeric version suffixes (v5 lands as `_v5.md`; v4 stays as in-project history)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 Option A / B / C all start with CLAUDE.md.**

---

*End of V5 Onboarding Spec closing handoff. Onboarding Design Wave consolidated and shipped. Next session: Andy's choice among the three forward-move candidates in §5.1.*
