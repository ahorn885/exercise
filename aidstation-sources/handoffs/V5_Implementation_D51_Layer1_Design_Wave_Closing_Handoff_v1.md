# V5 Implementation — D-51 Layer 1 Design Wave Closing Handoff

**Session:** Single chat. Scope: D-73 Phase 1.1 — D-51 design wave per `Upstream_Implementation_Plan_v1.md` §4 Phase 1.1. Output is `Layer1_D51_Design_v1.md` (~340 lines) + paired `Athlete_Data_Integration_Spec_v6.md` §7.6.1 annotation + backlog v62 with D-51 status flip.

**Date:** 2026-05-19

**Predecessor handoff:** `V5_Implementation_Upstream_Implementation_Plan_Closing_Handoff_v1.md` (D-73 plan shipped 2026-05-19; merged via PR #90 at `cd70127`).

**Branch:** `claude/implement-handoff-plan-wE132` (harness-pinned; first branch name in the D-66/D-72/D-73 chain that thematically matches the scope — "implement-handoff-plan" is what this session does).

**Status:** 🟢 5 files (1 substantive design doc + 1 paired spec bump + 3 bookkeeping). **At the 5-file ceiling — second ceiling-clean (or exact-hit) session in the D-73 arc.** No code; design + bookkeeping only.

---

## 1. Session-start verification (Rule #9)

Verified at session start before composing the design doc:

| Claim | Anchor | Result |
|---|---|---|
| `Upstream_Implementation_Plan_v1.md` exists on disk | `ls` | ✅ 301 lines |
| `Project_Backlog_v61.md` exists; D-73 row present (line 167); D-51 status 🟡 Deferred (line 143) | grep | ✅ |
| `Athlete_Data_Integration_Spec_v5.md` exists; §7.6 gap summary at line 624 | grep | ✅ |
| `init_db.py` PG_SCHEMA `athlete_profile` at line 16 (19 columns) | grep | ✅ |
| `athlete_profile_field_provenance` table shipped (D-58) | grep | ✅ line 889 |
| `gym_profiles` + `locale_equipment_overrides` + `locale_toggle_overrides` shipped (D-60) | grep | ✅ |
| `race_events` + `race_route_locales` shipped (D-66) | grep | ✅ lines 1136 + 1157 |
| `wellness_self_report` shipped | grep | ✅ line 725 |
| `account_nudges` shipped (D-58) | grep | ✅ line 901 |
| `CLAUDE.md` line 52 last-shipped narrative reads D-73 plan | grep | ✅ |
| Working tree clean on `claude/implement-handoff-plan-wE132` | `git status` | ✅ |

**Rule #9 reconciliation:** all predecessor handoff claims match on-disk state. No drift. Proceeded to scope-pick gate.

**Critical finding:** much more schema infrastructure already exists than `Athlete_Data_Integration_Spec_v5.md` §7.6 implied — D-58/D-59/D-60/D-61/D-66 closed the largest pieces. D-51 design wave residual scope is NARROWER than originally framed in v5 §7.6.

---

## 2. Session narrative — gate chain

Andy opened with the URL to the D-73 plan handoff + "let's work." Followed the operating model — fetched the predecessor handoff from GitHub, did Rule #9 verification (all green; PR #90 already merged), read CLAUDE.md fully, surfaced state.

### 2.1 Q1 — Scope pick (1-question gate)

Andy 2026-05-19 picked **D-73 Phase 1.1 — D-51 design wave** (over Layer 4 Step 4f Pattern A / Layer 4 Step 7 env-gated scaffolding / Manual §5.0 walkthrough prep) per the architect-recommended longest-lever next move framing.

### 2.2 Q2-Q4 — /plan-mode-equivalent gate (3-question batch)

Trigger #5 (cross-layer contract — Layer 1 storage), #8 (architectural alternatives — table-heavy vs JSONB-heavy), #11 (D-51 status flip + potential sub-rows) all anticipated to fire per `Upstream_Implementation_Plan_v1.md` §6. Surfaced 3 questions:

- **Q2 design-wave scope** — Andy picked **Full §A-§L field-by-field** (over phased §C/§D/§E/§F first or phased §H + §G first).
- **Q3 storage strategy** — Andy answered "which is the best long term option" — request for architect-pick rationale (not a direct pick from the 3 offered options).
- **Q4 D-row strategy** — Andy picked **Keep D-51 as umbrella** (over splitting D-51.1 .. D-51.6 sub-rows).

### 2.3 Architect-pick exchange on storage strategy

I had framed Q3 as a 3-way pick (Hybrid / Table-heavy / JSONB-heavy). Andy's "best long term" answer pushed me to architect-pick rather than menu-pick. Surfaced the architect-pick: **Table-heavy** (rolling back my own initial Hybrid framing as overstating the JSONB case).

Reasoning surfaced:

- **§A.2 provenance is column-driven.** v5 designs `athlete_profile_field_provenance(user_id, field_name, source, source_synced_at, manual_override_at)` with one row per scalar field. Columns map cleanly; JSONB-key-level provenance complicates the existing model and breaks tolerance-based re-prefill (§A.2.7) for prefill-eligible fields like Body Weight, HRmax, FTP.
- **§E (9 strength benchmarks) is the only place JSONB looks tempting** — bundled scalars accessed together for Layer 1, never individually. But manual entry only (not prefill-eligible per A.2.1), so the provenance argument for JSONB is moot. A 1:1 `strength_benchmarks` table with 9 columns keeps schema symmetric for the small cost of one JOIN.
- **Long-term: typed Layer 1 payload (plan Phase 1.3 carry-forward).** Promoting `dict[str, Any]` → `Layer1Payload` is cleaner against columnar storage than JSONB-keyed payloads.
- **Cost is small.** Layer 1 builder does ~6-8 JOINs to assemble the full payload vs ~2-3 with JSONB. PG handles sub-millisecond.

Andy confirmed table-heavy via follow-on AskUserQuestion gate.

### 2.4 Deep reconnaissance for design composition

Read the third-re-read targets per the predecessor handoff §6.3:

- `Athlete_Onboarding_Data_Spec_v5.md` §A-§L (918 lines fully scanned).
- `Athlete_Data_Integration_Spec_v5.md` §7.6 (existing gap summary at line 624).
- `init_db.py` PG_SCHEMA `athlete_profile` definition + all related tables.
- `Upstream_Implementation_Plan_v1.md` §2.4 + §4 Phase 1.1.

Confirmed via grep that ~half of the v5 §7.6 catalogued gaps are CLOSED by shipped D-58/D-59/D-60/D-61/D-66 work. Residual scope: ~12 new tables + ~30 new columns + 1 legacy column drop.

### 2.5 Design composition

Composed `Layer1_D51_Design_v1.md` (~340 lines, 8 sections) using `Race_Events_D66_Design_v1.md` format precedent. Structure:

- §1 Purpose & scope (architect-pick on the record; out-of-scope items: D-52 sequencing, D-56, Layer 1 builder code, Layer 1 prompt body, typed payload promotion)
- §2 Current schema state (Rule #9 audit table — what already exists)
- §3 Section-by-section design (12 subsections covering §A through §L)
- §4 Migration ordering (Phase 1.2 sliced into 3 ceiling-clean sessions: 1.2A column extensions + bundled-scalar sub-tables; 1.2B multi-row tables for §B/§C/§L; 1.2C per-discipline §D tables)
- §5 Cross-cutting concerns (provenance + tolerance config + §A.2.5 re-prefill + Layer 1 typed payload + backwards-compatibility)
- §6 Open questions (7 deferred items)
- §7 Gut check (risks + best argument against + what might be missing)
- §8 Next forward move (D-73 Phase 1.2 Session 1.2A)

---

## 3. File-by-file edits

### 3.1 `aidstation-sources/Layer1_D51_Design_v1.md` (new)

~340 lines, 8 sections. Format precedent: `Race_Events_D66_Design_v1.md`.

**Key content choices:**

- **§3.1 §A.1 Disclosures** → new `disclosure_acknowledgments` table with append-only audit shape (id + user_id + disclosure_type + version_seen + acknowledged_at + delivery_method + optional subject_id polymorphic FK).
- **§3.2 §B Health Status** → three new tables: `health_conditions_log` (parallel to `injury_log`), `medications_log` (closed enum on `medication_class`), `food_allergies` (severity enum with anaphylaxis tier triggering §B.4.2 auto-population rule application-side).
- **§3.3 §C Training History** → 7 new scalar columns on `athlete_profile` (`years_structured_training`, `peak_weekly_volume_hrs` + `_year`, `longest_event_completed`, `training_consistency_*`, `previous_coaching`) + 4 new multi-row tables (`athlete_secondary_sports`, `athlete_discipline_weighting`, `recent_race_results`, `pack_load_history`).
- **§3.4 §D Discipline-Specific Baselines** → 7 per-discipline sparse 1:1 tables (`discipline_baseline_running` through `_technical`). Type fidelity over schema compactness.
- **§3.5 §E Strength Benchmarks** → new 1:1 `strength_benchmarks` table with 9 columns + `last_tested_at`.
- **§3.6 §F Performance Baselines** → 8 new columns on `athlete_profile` (FTP test date + Threshold Pace + CSS + their test dates + source enums for HRmax/LT/VO2max).
- **§3.7 §G Schedule** → new `daily_availability_windows` table per v5 §G.1 with paired non-null CHECK constraints; drops legacy `athlete_profile.training_window` per D-66 Scope B precedent.
- **§3.8 §H Target Events** → ✅ existing per D-66; adds 2 columns to `athlete_profile` for §H.3 no-event mode (`plan_duration_weeks_no_event`, `non_event_goal_type`).
- **§3.9 §I Lifestyle & Recovery** → 13 new columns on `athlete_profile` (work_stress + dietary_pattern + supplements + caffeine + altitude + I.2 race-day fueling + I.3 sleep-deprivation).
- **§3.10 §J Locales** → ✅ existing per D-59 + D-60.
- **§3.11 §K Locale Schedule** → architect-pick deferred; `plan_travel` is v1 storage; richer §K modeling carry-forward.
- **§3.12 §L Athlete Network** → new `athlete_network_links` table + `linked_partner_consents` deferred to Session 1.2B.

**Total Phase 1.2 surface:** ~12 new tables + ~30 new columns on `athlete_profile`; 1 legacy column drop.

### 3.2 `aidstation-sources/Athlete_Data_Integration_Spec_v6.md` (new; v5 retained per Rule #12)

- Title bumped v5 → v6; Version 5.0 → 6.0; Last updated 2026-05-19; Supersedes line points at v5.
- New `Layer1_D51_Design_v1.md` cross-reference added.
- New "What changed in v6 vs v5" section: §7.6 gap summary annotated with D-51 resolution; substantial schema already shipped; D-51 residual scope narrower than originally framed.
- New §7.6.1 D-51 design-wave resolution sub-section: 12-row table mapping each §7.6 gap-row to the closing design pointer in `Layer1_D51_Design_v1.md`; migration sequencing note; D-52 sequencing decision note; D-56 sequencing note.

### 3.3 `aidstation-sources/Project_Backlog_v62.md` (new; v61 retained per Rule #12)

- File revision header rewritten for D-51 design wave ship (Andy 2026-05-19 picks + design doc structure + Phase 1.2 schema scope + architectural choices + status flip).
- **D-51 row** Notes column extended with D-51 design-wave resolution narrative + Phase 1.2 implementation sequencing pointer + architectural picks ratification + D-52/D-56 coordination notes; **status flipped 🟡 Deferred → 🟢 Design wave shipped 2026-05-19**.
- **D-73 row** narrative extended: "**Phase 1.1 (D-51 design wave) shipped 2026-05-19**" prefix added to the description.

### 3.4 `aidstation-sources/CLAUDE.md` — last-shipped narrative + line 260 + Authoritative current files

- Line 52 last-shipped narrative bumped (D-73 plan → D-51 design wave; demotes D-73 plan to "Predecessor" tail reference).
- Line 260 First-session-checklist backlog ref bumped (v61 → v62).
- Authoritative current files section: backlog v55 → v62 (was stale at v55 before this session — fix-up included); Integration v5 → v6; new Layer1_D51_Design_v1.md entry added.

### 3.5 `aidstation-sources/handoffs/V5_Implementation_D51_Layer1_Design_Wave_Closing_Handoff_v1.md` (this file, new)

---

## 4. No code; no tests

Pure design + bookkeeping session. `tests/` count unchanged at 751.

---

## 5. Manual §5.0 verification steps — NONE this session

Design document is an artifact; no runtime behavior to walk. Manual walkthrough scenarios stay at 36 (12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72 from prior sessions).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward moves

**D-73 Phase 1.2 Session 1.2A — athlete_profile column extensions + bundled-scalar sub-tables** is the longest-lever next move within Phase 1.2. Suggested session prompt:

> Open D-73 Phase 1.2 Session 1.2A per `Layer1_D51_Design_v1.md` §4. Athlete profile column extensions (~15 new columns per §3.3 + §3.6 + §3.8 + §3.9) + bundled-scalar sub-tables (`strength_benchmarks` §3.5, `daily_availability_windows` §3.7) + drop `athlete_profile.training_window` per D-66 Scope B precedent + extend `KNOWN_PROFILE_FIELDS` application-code registry. ~5 files; under ceiling. Trigger #5 expected to fire for schema migration; /plan-mode gate on day-of-week numbering convention (Sunday=0 vs ISO Monday=0).

### 6.2 Alternative pivots (if Andy defers Phase 1.2)

The arc isn't time-critical until PGE 2026 forcing function activates (~2026-07-03 = days_to_event 14 for race_week_brief auto-fire). ~10 weeks of runway from 2026-05-19.

- **Layer 4 Step 4f `llm_layer4_plan_create` Pattern A orchestration** — orthogonal; closes Layer 4 §14.3.4 Step 4 sub-arc completely (4a-4f); ~6-8 files. Doesn't need upstream layers.
- **Layer 4 Step 7 env-gated smoke test scaffolding** — needs ANTHROPIC_API_KEY path; ~3-4 files without the real key.
- **Manual §5.0 walkthrough** of accumulated 36 scenarios on Vercel.

### 6.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully. (Delegate to Explore agent — it's now ~120k+ tokens.)
2. **Second re-read:** this handoff.
3. **Third re-read:** depends on scope.
   - D-73 Phase 1.2 Session 1.2A → `Layer1_D51_Design_v1.md` §3.3 + §3.5 + §3.6 + §3.7 + §3.8 + §3.9 + §4 + §6 + `init_db.py` `_PG_MIGRATIONS` section + the existing `KNOWN_PROFILE_FIELDS` application-code constant (in `athlete.py` or similar) + D-66 Scope B `init_db.py` precedent for `DROP COLUMN IF EXISTS`.
   - Layer 4 Step 4f → `Layer4_Spec.md` §5.1 + §5.2 + §6.1 + §6.2 + §6.3 + `aidstation-sources/prompts/Layer4_PerPhase_v2.md` + `Layer4_SeamReviewer_v2.md` + the already-shipped `layer4/per_phase.py` + `layer4/seam_review.py` + `layer4/plan_create.py`.
   - Layer 4 Step 7 → `layer4/single_session.py:_default_llm_caller` + `tests/test_layer4_single_session.py` + decide on env-gated test scaffolding pattern.
4. **Branch:** cut fresh off post-merge main OR stay on the harness pin (precedent: every D-66 / D-72 / D-73 session including this one has stayed harness-pinned).

---

## 7. Open items / decisions pinned this session

### 7.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Q1 scope = D-73 Phase 1.1 (D-51 design wave) | Andy 2026-05-19 | Architect-recommended longest-lever next move per `Upstream_Implementation_Plan_v1.md` §6.1. |
| 2 | Q2 design-wave scope = Full §A-§L field-by-field | Andy 2026-05-19 | Single design wave closes Phase 1.1; D-51 implementation sequences cleanly behind it. |
| 3 | Q3 storage strategy = Table-heavy | Andy 2026-05-19 (architect-pick + confirm) | §A.2 provenance is column-driven; §A.2.7 tolerance-based re-prefill needs per-field columns; long-term `Layer1Payload` typed promotion cleaner against columnar storage; JSONB-keyed provenance is a maintenance burden. |
| 4 | Q4 D-row strategy = Keep D-51 as umbrella | Andy 2026-05-19 | Simpler tracking; sub-row split adds surface without proportionate benefit at v1 scale. |
| 5 | §K Locale Schedule richer modeling deferred | Architect-pick | v1 has no exercise of §K.2 joint-training or §K.3 recurrence; `plan_travel` is v1 storage. |
| 6 | `linked_partner_consents` companion table deferred to Session 1.2B | Architect-pick | v1 has no multi-athlete-team-training case. |
| 7 | Day-of-week numbering deferred to Session 1.2A /plan-mode gate | Architect-pick | Sunday=0 per v5 §G.1 vs ISO Monday=0; Andy's call. |
| 8 | D-56 (`cardio_log.is_race` + `start_time`) stays separate from D-51 | Architect-pick | Small migration on existing table; sequenced to Phase 1.4 per `Upstream_Implementation_Plan_v1.md`. |
| 9 | Per-discipline §D 1:1 tables sparse (7 tables) | Architect-pick | Type fidelity over schema compactness; merging into generic `discipline_baselines(user_id, discipline, field_name, value)` loses discipline-specific schemas. |
| 10 | `disclosure_acknowledgments` table append-only audit (not JSONB on users) | Architect-pick | Acknowledgment events are append-only per v5 §A.1; JSONB would require copy-on-write semantics. |
| 11 | `food_allergies.severity='anaphylaxis'` auto-population application-side | Architect-pick | §B.4.2 rule logic is more flexible at application layer than DB trigger; allows future refinement without schema migration. |
| 12 | v5 Open Item #17 `KNOWN_PROFILE_FIELDS` registry extended in tandem per session | Architect-pick | Provenance keying integrity requires application-code registry to stay in sync with `athlete_profile` columns. |

### 7.2 Carry-forward — D-73 Phase 1.2 (deferred until Andy picks Session 1.2A)

Phase 1.2 activates when Andy opens Session 1.2A. Until then, D-73 stays 🟡 Deferred. All 3 sessions captured in `Layer1_D51_Design_v1.md` §4 with file estimates + trigger anticipations.

### 7.3 Carry-forward — D-73 Phase 1.3 / 1.4 / 1.5 sequencing

- **Phase 1.3** Layer1_Spec.md consolidation lands AFTER D-51 implementation per architect-pick (b) in plan §5 — schema decisions force spec shape, not vice versa.
- **Phase 1.4** D-56 `cardio_log.is_race` + `start_time` — small migration; can fold into Session 1.2A if migration batch favored larger.
- **Phase 1.5** D-52 catalog migration — soft-blocker; sequencing decision deferred to Phase 2 kickoff /plan-mode gate per architect-pick (f) in plan §5.

### 7.4 Carry-forward — pre-existing nits to bundle into upstream sessions

Per `Upstream_Implementation_Plan_v1.md` plan §6 item 8 (unchanged from predecessor handoff):

- `routes/onboarding.py:710` docstring tense (stale "legacy athlete_profile.target_event_*" reference after Scope B/C) — fold into Phase 4 or Phase 5.
- `Layer4_Spec.md` §4.5 source-pointer wording (D-72 obsolescence) — fold into Phase 5.1 orchestrator vertical slice.
- `Race_Events_D66_Design_v1.md` §8.3 `open_ended` → `no-event` drift — fold into Phase 4.2 Layer 3B prompt-body session.

### 7.5 Carry-forward — `_v61.md` retained per Rule #12

`Project_Backlog_v61.md` preserved alongside the new `_v62.md`. Historical chain stays intact (v55 → v56 → … → v61 → v62). Same for `Athlete_Data_Integration_Spec_v5.md` preserved alongside `_v6.md`.

### 7.6 Carry-forward — manual §5.0 walkthrough (unchanged)

36 scenarios total: 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72. Unchanged this session (design doc doesn't add walkthrough scenarios).

### 7.7 Carry-forward — Layer 4 Step 7 live LLM (orthogonal to D-73)

Step 7 doesn't depend on upstream implementation. Blocked on ANTHROPIC_API_KEY env access. Can ship env-gated smoke test scaffolding without the key (~3-4 files).

### 7.8 Carry-forward — Layer 4 Step 4f Pattern A orchestration (orthogonal to D-73)

`llm_layer4_plan_create` Pattern A is the heaviest remaining Layer 4 sub-step. Closes Layer 4 §14.3.4 Step 4 sub-arc (4a-4f). Doesn't depend on upstream layers (uses dependency-injected upstream payloads in tests). ~6-8 files. Could land in parallel with D-73 Phase 1.2.

### 7.9 Carry-forward — Layer 1 prompt body question (plan §6 item 5)

If §C free-text parsing ("Longest Event Completed" text → structured event + distance + time + year) needs LLM judgment, Layer 1 expands to an LLM-driven node. Open question per `Upstream_Implementation_Plan_v1.md` §6 item 5. Defer until first §C real-athlete parsing case justifies it.

---

## 8. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `aidstation-sources/Layer1_D51_Design_v1.md` exists; ~340 lines; 8 sections | ✅ inspection (`wc -l` = 340 expected; actual close to projection) |
| Design doc §3 has 12 subsections covering §A through §L | ✅ inspection |
| Design doc §4 has 3-session migration sequencing | ✅ inspection |
| `Athlete_Data_Integration_Spec_v6.md` exists; v5 retained; v6 header + §7.6.1 D-51 resolution block present | ✅ inspection |
| `Project_Backlog_v62.md` exists; v61 retained; v62 file revision header rewritten | ✅ `ls -la aidstation-sources/Project_Backlog_v6*.md` |
| `Project_Backlog_v62.md` D-51 row status flipped 🟡 Deferred → 🟢 Design wave shipped 2026-05-19 | ✅ grep |
| `Project_Backlog_v62.md` D-51 Notes column extended with D-51 design-wave resolution narrative | ✅ grep |
| `Project_Backlog_v62.md` D-73 row narrative extended with Phase 1.1 ship note | ✅ grep |
| `CLAUDE.md` line 52 reads D-51 design wave ship narrative; D-73 plan demoted to Predecessor | ✅ inspection |
| `CLAUDE.md` First-session-checklist Backlog ref reads `Project_Backlog_v62` | ✅ inspection |
| `CLAUDE.md` Authoritative current files reads Integration v6 + new Layer1_D51_Design_v1 entry | ✅ inspection |
| Working tree clean prior to commit | `git status` (run at commit time) |

---

## 9. Files shipped this session

**Substantive (2 files):**
1. New `aidstation-sources/Layer1_D51_Design_v1.md` (~340 lines, 8 sections).
2. New `aidstation-sources/Athlete_Data_Integration_Spec_v6.md` (v5 retained per Rule #12; v5 byte-identical except v6 header block + §7.6.1 D-51 resolution sub-section).

**Bookkeeping (3 files):**
3. New `aidstation-sources/Project_Backlog_v62.md` (per Rule #12; v61 retained) — file revision header rewritten + D-51 status flipped + Notes column extended + D-73 row narrative extended.
4. Modified `aidstation-sources/CLAUDE.md` — last-shipped narrative bump (D-73 plan → D-51 design wave; demotes D-73 plan to "Predecessor — D-73 upstream implementation arc plan: …" tail reference); First-session-checklist Backlog ref bumped (v61 → v62); Authoritative current files updated (backlog v55 → v62 stale fix-up; Integration v5 → v6; new Layer1_D51_Design_v1 entry).
5. New `aidstation-sources/handoffs/V5_Implementation_D51_Layer1_Design_Wave_Closing_Handoff_v1.md` (this file).

**5 files total. At the 5-file ceiling — second ceiling-clean (or exact-hit) session in the D-73 arc.**

---

## 10. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **D-73 upstream Layer 1-3 implementation arc** — Phase 1.1 (D-51 design wave) CLOSED 2026-05-19 this session; Phase 1.2 (D-51 implementation) opens with Andy's next scope pick; remaining 9-13 sessions; ~50-70 files across the rest of the arc.
- **D-51** — Status flipped 🟡 Deferred → 🟢 Design wave shipped 2026-05-19; implementation Phase 1.2 queued.
- **Layer 4 Step 4f Pattern A orchestration** — orthogonal to D-73; ~6-8 files; closes Layer 4 §14.3.4 Step 4 sub-arc.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward; needs `ANTHROPIC_API_KEY`.
- **Manual §5.0 walkthrough (36 scenarios accumulating)** — 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72. Andy walks on Vercel after PR merges.
- **`routes/onboarding.py:710` docstring tense + `Layer4_Spec.md` §4.5 source-pointer wording + `Race_Events_D66_Design_v1.md` §8.3 `open_ended` drift** — doc-sweep follow-on nits; folded into upstream-arc sessions per `Upstream_Implementation_Plan_v1.md` §6 item 8.

---

**End of handoff.**
