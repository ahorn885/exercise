# V5 Implementation — Upstream Layer 1-3 Implementation Plan Closing Handoff

**Session:** Single chat. Scope: upstream Layer 1-3 implementation arc plan composition per the D-72 closing handoff §6.1 forward-pointer ("Layer 3B caller-side rewire — the actual orchestrator build … longest forward-pointer"). Output is `Upstream_Implementation_Plan_v1.md` (~340 lines); no code shipped.

**Date:** 2026-05-19

**Predecessor handoff:** `V5_Implementation_D72_Locale_FK_Type_Alignment_Closing_Handoff_v1.md` (D-72 shipped 2026-05-19; merged via PR #89 at `4da19ab`).

**Branch:** `claude/locale-fk-type-alignment-jgscK` (harness-pinned for this session; name mismatches scope — precedent across the D-66/D-72/Layer 4 implementation arc).

**Status:** 🟢 4 files (1 substantive plan doc + 3 bookkeeping). **Under the 5-file ceiling — first ceiling-clean session since D-72.** No code; planning + bookkeeping only.

---

## 1. Session-start verification (Rule #9)

Verified at session start before composing the plan:

| Claim | Anchor | Result |
|---|---|---|
| D-72 shipped on main | `git log --oneline -15` | ✅ `333880f` D-72 commit + `4da19ab` merge PR #89 |
| `layer4/context.py:942` reads `event_locale_id: str \| None = None` | grep | ✅ |
| `race_events_repo.py:85-88` LEFT JOIN locale_profiles + `lp.locale AS event_locale_slug` | grep | ✅ |
| `CLAUDE.md` line 52 last-shipped narrative reads D-72 | grep | ✅ |
| `Project_Backlog_v60.md` exists; v59 retained | `ls` | ✅ |
| Working tree clean on `claude/locale-fk-type-alignment-jgscK` | `git status` | ✅ |

**Rule #9 reconciliation:** all D-72 handoff claims match on-disk state. No drift. Proceeded to scope pick.

---

## 2. Session narrative — 4-question gate chain

Andy opened with the URL to the D-72 closing handoff + "let's work." Followed the operating model — Rule #9 verification (all green), surfaced state + the carry-forward set from the predecessor handoff §6.

### 2.1 Q1 — Scope pick (1-question gate)

Andy 2026-05-19 picked **Layer 4 Step 7 live LLM integration** (over Layer 3B caller-side rewire / doc-sweep nits routes/onboarding.py:710 + Layer4_Spec.md §4.5 / manual §5.0 walkthrough prep).

### 2.2 Blocker discovered — ANTHROPIC_API_KEY not in env

Reconnaissance via `env | grep -iE "anthropic|api_key"` surfaced `ANTHROPIC_BASE_URL=https://api.anthropic.com` but no `ANTHROPIC_API_KEY`. The container has `CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR` for the Claude Code session's own auth but no general Anthropic API key. Existing tests in `tests/test_layer4_single_session.py` all stub the LLM caller (`_stub_caller`, `_sequence_caller`); no live integration scaffolding exists.

### 2.3 Q2 — How to handle Step 7

Three options surfaced:
1. Land an env-gated smoke test + standalone smoke script (~3-4 files; CI stays green; Andy runs the real call locally).
2. Andy pastes the key into this session (ephemeral container; key transit through chat).
3. Pivot scope.

Andy picked **Pivot scope** — key handling deferred + Step 7 stays a carry-forward until Andy has a safe key path.

### 2.4 Q3 — Pivot pick

Three pivot options surfaced:
1. **Layer 3B caller-side rewire (orchestrator build)** — longest forward-pointer per D-72 §6.1; Trigger #5/#8 likely fire; needs /plan-mode gate.
2. **Doc-sweep nits** (routes/onboarding.py:710 + Layer4_Spec.md §4.5) — small surface.
3. **Manual §5.0 walkthrough prep** — consolidate the 36 accumulated scenarios into a single checklist.

Andy picked **Layer 3B caller-side rewire (orchestrator build)**.

### 2.5 Reconnaissance — no upstream builders exist

Spawned `Explore` subagent for thorough reconnaissance of the Layer 3B → Layer 4 orchestrator wiring surface. Findings:

- **`Layer3BPayload` typed contract exists** in `layer4/context.py:771-827` (with D-66 event-metadata fields + D-72 slug-typed `event_locale_id`)
- **`llm_layer4_race_week_brief_cached()` already exists** in `layer4/cached_wrappers.py:416-510` (Step 5 shipped)
- **`load_target_race_event_payload(db, user_id)` already exists** in `race_events_repo.py:168-185` (D-66 DB foundation)
- **Invalidation hooks wired** in `race_events_invalidation.py` (Scope C shipped)
- **NO call sites exist** for `llm_layer4_race_week_brief()` outside tests
- **NO Layer 4 orchestrator code** exists at all

**Critical finding via parallel recon:** no `layer1/`, `layer2*/`, `layer3*/` modules exist anywhere in the repo. Only `layer4/` has runtime code. The "actual orchestrator build" framed by the D-72 handoff §6.1 can't realistically mean a single-session vertical slice — it requires the entire upstream stack (Layer 1 builder + Layer 2A-E query nodes + Layer 3A LLM driver + Layer 3B LLM driver) which doesn't exist yet.

### 2.6 Q4 — Upstream slice

Surfaced this finding to Andy as a /plan-mode gate. Three options:
1. **Survey + multi-session implementation plan (no code)** — audit the gap end-to-end + produce a sequenced multi-session arc (similar to Layer 4 §14.3.4 8-step plan). 3-4 files.
2. **Typed-payload skeletons for 1/2A-E/3A/3B** — mirror what layer4/context.py did but invert; build the upstream-side typed payloads in their own modules. 8-12 files.
3. **Implement Layer 3A first** — smallest LLM-callable next-up. ~5-8 files.

Andy picked **Survey + multi-session implementation plan (no code)** — most honest scope given the size of the gap.

### 2.7 Deep reconnaissance for plan composition

Spawned a second `Explore` subagent (background, ~287s) to map upstream spec + implementation state in 8 dimensions: spec completeness, existing skeletons, dependency ordering, Layer 4 §14.3.4 structure precedent, existing design-wave handoffs, data source readiness, token/cost projections, test conventions. Report (synthesized inline in the plan doc) confirmed:

- Layer 1 has NO canonical spec file (consolidation pending D-51); source-of-truth split across `Athlete_Onboarding_Data_Spec_v5.md` + `Athlete_Data_Integration_Spec_v5.md` §7.6.
- Layers 2A/2B/2C/2D/2E specs COMPLETE (443/403/515/1169/1324 lines).
- Layers 3A/3B specs COMPLETE (649/524 lines).
- All upstream typed payloads ALREADY EXIST in `layer4/context.py` (~55 types) — critical reuse opportunity.
- Hard blockers: D-51 (Layer 1 schema), D-56 (cardio_log additions).
- Soft blocker: D-52 (catalog migration; can run in parallel or sequence).

### 2.8 Plan composition

Composed `Upstream_Implementation_Plan_v1.md` (~340 lines, 9 sections) using `Layer4_Spec.md` §14.3 format precedent. Structure:

- §1 Purpose & scope
- §2 Current state inventory (5 subsections including the critical typed-payload-mirrors reuse opportunity)
- §3 Dependency graph & build order (ASCII tree)
- §4 Sequenced multi-session arc — 5 phases with per-step file estimates
- §5 Cross-cutting concerns (test fixtures, prompt-body arc, cache integration, ceiling, production-data forcing function)
- §6 Open questions / triggers expected to fire per session
- §7 Backlog additions (new D-73 row)
- §8 Gut check (risks + best argument against + what might be missing)
- §9 Next forward move (Andy's choice when Phase 1 opens)

---

## 3. File-by-file edits

### 3.1 `aidstation-sources/Upstream_Implementation_Plan_v1.md` (new)

~340 lines, 9 sections per the structure above. Format precedent: `Layer4_Spec.md` §14.3.

**Key content choices:**

- **Phase 1 (3-5 sessions, ~15-20 files):** D-51 design wave → D-51 implementation → Layer1_Spec.md consolidation → D-56 cardio_log additions → D-52 catalog migration (deferrable).
- **Phase 2 (5 sessions, ~25 files):** Layer 2A first (foundation), then 2D + 2B + 2C (with /plan-mode gate for §5 Decision Points) + 2E in serial. Query nodes — NOT LLM-driven.
- **Phase 3 (1-2 sessions, ~6-10 files):** Layer 3A LLM driver per Layer 4 Step 4a precedent + paired `Layer3A_v1.md` prompt body.
- **Phase 4 (1-2 sessions, ~8-11 files):** Layer 3B LLM driver + event-metadata helper `load_layer3b_event_metadata(db, user_id)` (the original D-72 forward-pointer) + paired `Layer3B_v1.md` prompt body + §8.3 `open_ended` → `no-event` doc-sweep fix.
- **Phase 5 (1-2 sessions, ~10-15 files):** Layer 4 orchestrator `orchestrate_race_week_brief(db, user_id)` vertical slice + remaining 3 entry points + Layer4_Spec.md §4.5 source-pointer wording fix (D-72 nit).

**Arc total: ~10-14 sessions, ~70-90 files.**

### 3.2 `aidstation-sources/Project_Backlog_v61.md` (new; v60 retained per Rule #12)

- File revision header rewritten for the upstream-plan ship.
- **D-73 row added** (umbrella row for the upstream arc) at the bottom of the open-items table after D-72.
- D-51 Notes column extended: "2026-05-19: blocks Phase 1.1 of D-73 upstream implementation arc per `Upstream_Implementation_Plan_v1.md` — the longest-lever next move; D-51 design wave is the gate to opening Layer 1 builder work."
- D-52 Notes column extended: "2026-05-19: soft-blocks Phase 2 of D-73 upstream implementation arc — Layer 2A-E builders can ship reading `public.*` initially with a paired refactor when D-52 finishes, OR D-52 lands first. Sequencing pick deferred to D-73 Phase 2 kickoff /plan-mode gate."
- D-56 Notes column extended: "2026-05-19: blocks Phase 3 of D-73 upstream implementation arc — Layer 3A driver needs `is_race` for "Recent Race Results" §C filter + `start_time` for Night Running detection §D.1. Small migration; can fold into D-73 Phase 1.4 (~1-2 files)."

### 3.3 `aidstation-sources/CLAUDE.md` — line 52 + line 260

- Line 52 last-shipped narrative bumped (D-72 → upstream plan; demotes D-72 to "Predecessor — D-72 locale-FK type alignment: …" tail reference).
- Line 260 First-session-checklist backlog ref bumped (v60 → v61).

### 3.4 `aidstation-sources/handoffs/V5_Implementation_Upstream_Implementation_Plan_Closing_Handoff_v1.md` (this file, new)

---

## 4. No code; no tests

Pure planning + bookkeeping session. `tests/` count unchanged at 751.

---

## 5. Manual §5.0 verification steps — NONE this session

Plan document is a design artifact; no runtime behavior to walk. Manual walkthrough scenarios stay at 36 (12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72 from prior sessions).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward moves

**D-73 Phase 1.1 — D-51 design wave** is the longest-lever next move. Everything else is downstream. Suggested session prompt:

> Open D-51 design wave per `Upstream_Implementation_Plan_v1.md` §4 Phase 1.1. Field-by-field inventory of Layer 1 §A-§L against `public.*` existing tables. Output: `Layer1_D51_Design_v1.md` + paired `Athlete_Data_Integration_Spec_v5.md` §7.6 update + backlog row updates. ~5 files; under ceiling. Trigger #5/#8/#11 expected to fire.

### 6.2 Alternative pivots (if Andy defers Phase 1)

The arc isn't time-critical until PGE 2026 forcing function activates (~2026-07-03 = days_to_event 14 for race_week_brief auto-fire). ~10 weeks of runway from 2026-05-19.

- **Layer 4 Step 4f `llm_layer4_plan_create` Pattern A orchestration** — orthogonal; closes Layer 4 §14.3.4 Step 4 sub-arc completely (4a-4f); ~6-8 files. Doesn't need upstream layers.
- **Layer 4 Step 7 live LLM integration** — needs ANTHROPIC_API_KEY; env-gated smoke test scaffolding can ship without the key (real call lands when Andy has a key path).
- **Manual §5.0 walkthrough** of accumulated 36 scenarios on Vercel.

### 6.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully. (Delegate to Explore agent — it's now ~120k+ tokens.)
2. **Second re-read:** this handoff.
3. **Third re-read:** depends on scope.
   - D-73 Phase 1.1 (D-51 design wave) → `Athlete_Onboarding_Data_Spec_v5.md` §A-§L + `Athlete_Data_Integration_Spec_v5.md` §7.6 (the existing gap summary) + `init_db.py` PG_SCHEMA `athlete_profile` definition + `Upstream_Implementation_Plan_v1.md` §2.4 + §4 Phase 1.1.
   - Layer 4 Step 4f → `Layer4_Spec.md` §5.1 + §5.2 + §6.1 + §6.2 + §6.3 + `aidstation-sources/prompts/Layer4_PerPhase_v2.md` + `Layer4_SeamReviewer_v2.md` + the already-shipped `layer4/per_phase.py` + `layer4/seam_review.py` + `layer4/plan_create.py`.
   - Layer 4 Step 7 → `layer4/single_session.py:_default_llm_caller` + `tests/test_layer4_single_session.py` + decide on env-gated test scaffolding pattern.
4. **Branch:** cut fresh off post-merge main OR stay on the harness pin (precedent: every D-66 / D-72 session including this one has stayed harness-pinned).

---

## 7. Open items / decisions pinned this session

### 7.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Q1 scope = Layer 4 Step 7 live LLM | Andy 2026-05-19 | First end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call; cache + telemetry + invalidation make it safer. |
| 2 | Q2 path = Pivot scope | Andy 2026-05-19 | ANTHROPIC_API_KEY blocker; ephemeral container can't safely host the key from chat transit. |
| 3 | Q3 pivot pick = Layer 3B caller-side rewire (orchestrator build) | Andy 2026-05-19 | Longest forward-pointer per D-72 §6.1; cleanest D-66 follow-on. |
| 4 | Q4 upstream slice = Survey + multi-session implementation plan (no code) | Andy 2026-05-19 | Most honest scope given the gap; "we should go back and fix the upstream gaps." |
| 5 | Plan ITSELF is the deliverable | Architect-pick | Ratification gate before any Phase implementation session opens. |
| 6 | Layer 1 spec consolidation lands AFTER D-51 design + implementation | Architect-pick | Schema decisions force spec shape, not vice versa. |
| 7 | Layer 2 query nodes serial-not-parallel | Architect-pick | Design-drift catch across 5 nodes outweighs parallelization benefit. |
| 8 | Layer 4 entry-point signatures keep `dict[str, Any]` for Layer 1 in v1 | Architect-pick | Typed-payload promotion deferred to v2 (~10-15 test files of churn otherwise). |
| 9 | Cache integration architect-pick: cache-agnostic upstream builders | Architect-pick | Per-upstream-layer caching deferred until telemetry justifies. |
| 10 | D-52 sequencing decision deferred to Phase 2 kickoff /plan-mode gate | Architect-pick | Not pre-committed in this plan; depends on Phase 1 progression. |
| 11 | Prompt-body cadence per-session paired with driver | Architect-pick | Per Layer 4 Step 4a precedent (`Layer4_SingleSession_v2.md` shipped with `llm_layer4_single_session_synthesize`). |
| 12 | Forcing function = Andy's PGE 2026 (10 weeks runway) | Architect-pick | race_week_brief auto-fires 2026-07-03; arc has comfortable margin. |

### 7.2 Carry-forward — D-73 phases (deferred until Andy picks Phase 1.1)

The arc activates when Andy opens Phase 1.1 (D-51 design wave). Until then, D-73 stays 🟡 Deferred. All 5 phases captured in plan §4 with file estimates + trigger anticipations.

### 7.3 Carry-forward — pre-existing nits to bundle into upstream sessions

Per plan §6 item 8:
- `routes/onboarding.py:710` docstring tense (stale "legacy athlete_profile.target_event_*" reference after Scope B/C) — fold into Phase 4 or Phase 5.
- `Layer4_Spec.md` §4.5 source-pointer wording (D-72 obsolescence) — fold into Phase 5.1 orchestrator vertical slice.
- `Race_Events_D66_Design_v1.md` §8.3 `open_ended` → `no-event` drift — fold into Phase 4.2 Layer 3B prompt-body session.

### 7.4 Carry-forward — `_v60.md` retained per Rule #12

`Project_Backlog_v60.md` preserved alongside the new `_v61.md`. Historical chain stays intact (v55 → v56 → v57 → v58 → v59 → v60 → v61).

### 7.5 Carry-forward — manual §5.0 walkthrough (accumulating)

36 scenarios total: 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72. Unchanged this session (planning doesn't add walkthrough scenarios).

### 7.6 Carry-forward — Layer 4 Step 7 live LLM (orthogonal to D-73)

Step 7 doesn't depend on upstream implementation; it's a Layer 4 in-vivo test against Anthropic API. Blocked on ANTHROPIC_API_KEY env access. Can ship env-gated smoke test scaffolding without the key (separate session; ~3-4 files).

### 7.7 Carry-forward — Layer 4 Step 4f Pattern A orchestration (orthogonal to D-73)

`llm_layer4_plan_create` Pattern A is the heaviest remaining Layer 4 sub-step. Closes Layer 4 §14.3.4 Step 4 sub-arc (4a-4f). Doesn't depend on upstream layers (uses dependency-injected upstream payloads in tests). ~6-8 files. Could land in parallel with D-73 Phase 1.

---

## 8. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `aidstation-sources/Upstream_Implementation_Plan_v1.md` exists; ~340 lines; 9 sections | ✅ inspection |
| Plan §4 has 5 phases with per-step file estimates | ✅ inspection |
| Plan §7 specifies the D-73 row to add | ✅ inspection |
| `Project_Backlog_v61.md` exists; v60 retained | ✅ `ls -la aidstation-sources/Project_Backlog_v6*.md` |
| `Project_Backlog_v61.md` file revision header reads `v61 — 2026-05-19` with upstream-plan narrative | ✅ inspection |
| `Project_Backlog_v61.md` D-73 row present after D-72 | ✅ grep |
| `Project_Backlog_v61.md` D-51/D-52/D-56 Notes columns extended with D-73 phase references | ✅ grep |
| `CLAUDE.md` line 52 reads upstream-plan ship narrative | ✅ inspection |
| `CLAUDE.md` line 260 First-session-checklist Backlog ref reads `Project_Backlog_v61` | ✅ inspection |
| Working tree clean prior to commit | `git status` (run at commit time) |

---

## 9. Files shipped this session

**Substantive plan (1 file):**
1. New `aidstation-sources/Upstream_Implementation_Plan_v1.md` (~340 lines, 9 sections).

**Bookkeeping (3 files):**
2. New `aidstation-sources/Project_Backlog_v61.md` (per Rule #12; v60 retained) — file revision header rewritten + D-73 row added + D-51/D-52/D-56 Notes columns extended.
3. Modified `aidstation-sources/CLAUDE.md` — last-shipped narrative bump (D-72 → upstream plan; demotes D-72 to "Predecessor — D-72 locale-FK type alignment: …" tail reference); First-session-checklist Backlog ref bumped (line 260: v60 → v61).
4. New `aidstation-sources/handoffs/V5_Implementation_Upstream_Implementation_Plan_Closing_Handoff_v1.md` (this file).

**4 files total. Under the 5-file ceiling** — first ceiling-clean session since D-72.

---

## 10. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **D-73 upstream Layer 1-3 implementation arc** — NEW this session; ~10-14 sessions; 5 phases; arc total ~70-90 files. Andy ratifies plan before any Phase session opens.
- **Layer 4 Step 4f Pattern A orchestration** — orthogonal to D-73; ~6-8 files; closes Layer 4 §14.3.4 Step 4 sub-arc.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward; needs `ANTHROPIC_API_KEY`.
- **Manual §5.0 walkthrough (36 scenarios accumulating)** — 12 onboarding + 6 nudge UI + 6 Scope A + 6 Scope B + 5 Scope C + 1 D-72. Andy walks on Vercel after PR merges.
- **`routes/onboarding.py:710` docstring tense + `Layer4_Spec.md` §4.5 source-pointer wording + `Race_Events_D66_Design_v1.md` §8.3 `open_ended` drift** — doc-sweep follow-on nits; folded into upstream-arc sessions per plan §6 item 8.

---

**End of handoff.**
