# 3B-Spec Closing Handoff — Reconciliation + Layer3_3B_Spec.md + Rule #13

**Session:** First Claude Code session continuing from Claude.ai chat. Single chat, end-to-end: handoff intake → drift verification → reconciliation pass → Layer 3 3B spec writing → close-out.
**Date:** 2026-05-14
**Predecessor handoff:** `L3_Spec_Trio_R2_Closing_Handoff_v1.md`
**Status:** ✅ All approved work shipped. Rule #9 verification clean against the predecessor handoff. Rule #10 verification clean against this session's outputs.
**Time-on-task:** Single chat. Ceiling: substantive work touched ~6 files (Control_Spec_v7 + 4-file reconciliation + Layer3_3B_Spec.md). Close-out files (Backlog v13, this handoff) are book-keeping; counted lightly.

---

## 1. Session-start verification (Rule #9)

Verified `L3_Spec_Trio_R2_Closing_Handoff_v1.md`'s claimed file updates against on-disk state before any new work. All anchors landed:

| File | Anchors checked | Result |
|---|---|---|
| `Athlete_Onboarding_Data_Spec_v4.md` (1077 lines) | "What changed in v4 vs v3" header; "Pregnancy intentionally never captured" (lines 13, 379); §D.7 Rock Climbing + Abseiling only (lines 502–503); §J.3 Fencing/Shooting setup rows removed; Snowshoeing setup at line 736 | ✅ |
| `Athlete_Data_Integration_Spec_v2.md` (780 lines) | v2 changelog; §2.3 build-from-scratch (line 69); §2.7 retention rule; §3 Garmin "Scaffold only" (line 163); §5.4 "Garmin (build-from-scratch)" (line 449) | ✅ |
| `Catalog_Migration_Plan_v2.md` (334 lines) | v2 changelog; fuzzy-match + HITL workflow (line 17); wipe pattern (line 230) | ✅ |
| `Project_Backlog_v11.md` (302 lines, 58 D-rows) | v11 header; D-55 reframed (line 92); D-57–D-61 present; Session L3-Spec-Trio Round 2 close block (line 241) | ✅ |
| `Layer3_3A_Spec.md` (649 lines) | 14 H2 sections; `llm_layer3a_athlete_state` signature; `Layer3APayload` schema; §6 self-report-vs-integration + confidence floors; `confidence_clamped_by_data_density` observation | ✅ |
| `Control_Spec_v6.md` (438 lines) | Architecture trunk unchanged from prior round | ✅ |

**No drift in the Rule #9 sense.** Two minor housekeeping items surfaced and were addressed in-session (not deferred):
- CLAUDE.md First-session checklist item 2 referenced `backlog/Project_Backlog_v11.md` but the file lives at the repo root — fixed in `Control_Spec_v7` housekeeping commit.
- `Control_Spec_v6.md` §9 doc map showed Layer 3 as "not yet started" while `Layer3_3A_Spec.md` had shipped — fixed via `Control_Spec_v7` (handoff §5 Option B path).

---

## 2. Repo-reality reconciliation (mid-session, not in the predecessor handoff's scope)

The Claude.ai chat track had been operating under the belief that the Vercel-app codebase was a **separate repository**. It is not — the v1 Flask AIDSTATION app lives at the root of this repo, alongside `aidstation-sources/`. Surveyed the parallel `HANDOFF-2026-05-*.md` track + `PROVIDERS_SCHEMA.md` + `DATABASE.md` + `DEV_SETUP.md` + `routes/` + `init_db.py` to ground the reconciliation.

**Operating framing locked (per Andy 2026-05-14 — three answered questions):**

- **Q1 = selective rebuild (option c).** Keep providers + auth + DB scaffolding from v1. Replace coaching + plan-gen with the Layer 0–5 LLM pipeline. Revisit v1 strength UI later.
- **Q2 = v2 integration path (Integration v2/v3 plan).** Drop `garmin_auth`, build Garmin onto `provider_auth` with `session_blob` once Garmin API access reopens. Resolved a direct contradiction between `PROVIDERS_SCHEMA.md` ("garmin_auth stays as-is") and `Athlete_Data_Integration_Spec_v2` ("drop garmin_auth as cleanup").
- **Q3 = strangler-fig (option i).** v1 is "live" but has no users — Andy is the sole test athlete. Ship v2 modules directly into v1 one at a time. No parallel staging environment needed.

**Also confirmed in-session:** new operating rule — **"push to production as we go"**. Prefer shipping working v2 code into v1 over accumulating more design ahead of any implementation. Captured in `CLAUDE.md` §Operating context.

**Garmin operational fact (per Andy 2026-05-14):** Garmin has temporarily closed new API access. D-55 status flipped Deferred → ⏸ Paused. The architectural decision in v2/v3 §2.3 stands; implementation waits for API reopen. D-50 (the rest of `provider_auth` for Polar / Wahoo / COROS / etc.) is **not** paused.

---

## 3. Files shipped this session

| # | File | Lines | Status | Notes |
|---|---|---|---|---|
| 1 | `Control_Spec_v7.md` | 454 | ✅ Shipped | Housekeeping bump from v6: §9 doc map sync after L3-Spec-Trio Round 2; per-node split of Layer 3 entry (3A ✅ canonical, 3B/3C/3D ⏳); Onboarding v4 / Integration v2 / Catalog Migration v2 / Backlog v11 all promoted to canonical. Body §§1–8, §10, §11 unchanged from v6. |
| 2 | `CLAUDE.md` (edit in place) | +~50 lines net | ✅ Edited | First-session checklist path fix; §Stack rewritten to reflect v1 Flask reality (Vercel + TrueNAS, Neon prod / SQLite dev); new §Operating context section covering selective-rebuild + strangler-fig + push-to-prod rule; D-50 line corrected; new **Rule #13** (every closing handoff names CLAUDE.md as the first re-read). |
| 3 | `Project_Backlog_v12.md` | 324 | ✅ Shipped | D-50 + D-55 reframed to drop separate-repo framing; D-55 status ⏸ Paused; v12 session block added. |
| 4 | `Athlete_Data_Integration_Spec_v3.md` | ~800 | ✅ Shipped | Cross-refs corrected (single repo); §2.3 Garmin pause noted; §1 producer-vs-consumer framing kept but stripped of "different codebase" implication. Field mappings, query signatures, retention rule (§2.7) unchanged from v2. |
| 5 | `PROVIDERS_SCHEMA.md` (edit in place, repo root) | ~330 | ✅ Edited | §5.1 + §7 garmin_auth statements reconciled with Integration v3 — drop on Garmin reopen, build onto `provider_auth` with `session_blob`. |
| 6 | `Layer3_3B_Spec.md` | 508 | ✅ Shipped | Second of four Layer 3 node specs (see §4 below). |
| 7 | `Project_Backlog_v13.md` | ~360 | ✅ Shipped | 3B-Spec session-close block added. Rule #13 noted in changelog. |
| 8 | `handoffs/3B_Spec_Closing_Handoff_v1.md` | this file | ✅ Shipped | Session-close mechanic. |

Counting against the 5-file substantive ceiling: files 1–6 are substantive (Control_Spec_v7 is light); files 7–8 are book-keeping. Ceiling held loosely.

---

## 4. Layer3_3B_Spec.md — what it commits to

Per Andy's approved scope (decisions A/B/C/D confirmed before writing):

**A. HITL trigger thresholds (§6.1).** Four-row table over typed conditions:
- `viability == 'unrealistic-as-stated'` → `blocker` (cannot be acknowledged, must be revised)
- `'achievable-with-adjustment'` AND first-time-at-distance AND `goal_outcome ∈ {Compete mid-pack, Podium}` → `warning`
- prior DNF + `time_to_event_weeks < dnf_recovery_window_weeks` (mapping in spec) → `warning`
- `compressed` periodization + 3A short-term `∈ {overreached, fatigued}` → `warning`

`viability == 'achievable'` with no qualifiers → no HITL.

**B. Periodization-shape vocabulary (§6.2).** `mode` enum:
- `standard` — use 2A's `phase_load_allocation` bands as-is
- `compressed` — shorter or skipped Base
- `extended` — lengthened, possibly double-Base
- `custom` — explicit `phase_weeks` override

Plus `start_phase: enum {Base, Build, Peak, Taper}` for skip-ahead logic when 3A shows athlete is already mid-Build-equivalent.

**C. No-event mode (§6.6).** Viability reduces to "is Plan Duration + Non-Event Goal Type internally consistent given current state?" Heuristics for the LLM (in system prompt, not hard rules) + §C Primary Sport cross-check (auto-observation when Goal Type mismatches sport family).

**D. Race date in past (§4 rule 1).** Fatal `Layer3BInputError('event_date_in_past')`. No soft pivot to results-mode. Athlete edits §H; partial-update invalidation cascades.

**Confidence floors (§6.5).** Mirror of 3A §6.2 pattern. Four validator-enforced floor rules; `'confidence_clamped_by_data_signal'` observation auto-emits when a floor fires.

**Test scenarios (§13).** 8 cases including Andy's actual PGX 2026 case as TS-1, AR podium 4 weeks unrealistic case, first-time half-marathon, no-event endurance + strength variants, ultra prior-DNF, 1-week-out compressed taper, race-date-in-past validation.

---

## 5. Session-end verification (Rule #10)

Final pass over the 8 files before composing this handoff:

**Control_Spec_v7.md:** v7 header; "What changed in v7 vs v6" block; §9 Layer 1 v4 canonical; Layer 3 per-node split; Cross-cutting v7 + v2/v2/v11 canonical. v6 untouched.

**CLAUDE.md:** §Stack rewritten (Flask + Vercel + TrueNAS + Neon); §Operating context section present (v1+v2 selective-rebuild + strangler-fig + push-to-prod rule); Rule #13 present at line ~101 above stop-and-ask triggers; First-session checklist path corrected.

**Project_Backlog_v12.md:** v12 header (line 5); D-50 reframed (line 88); D-55 status ⏸ Paused (line 93); Session Reconciliation v12 block (line 260).

**Athlete_Data_Integration_Spec_v3.md:** v3 header (line 1); "What changed in v3 vs v2" block (line 19); §1 producer-vs-consumer kept; §2.3 Garmin pause subsection (line ~82); §7 "App-track (repo root)" framing (line ~780).

**PROVIDERS_SCHEMA.md:** §5.1 "Plan: when Garmin API access reopens..." present; §7 garmin_auth "Currently still in use" + "Planned for removal" + D-55 cross-ref to v12.

**Layer3_3B_Spec.md:** 14 H2 sections present in order; 508 lines; function signature `llm_layer3b_goal_timeline_viability`; `Layer3BPayload` + `GoalViability` + `PeriodizationShape` + `HITLItem` + `Observation` dataclasses; §6 contains all four decision resolutions A/B/C/D; §13 contains 8 test scenarios.

**Project_Backlog_v13.md:** v13 header; v12 → predecessor; Session 3B-Spec block.

**3B_Spec_Closing_Handoff_v1.md:** this file.

No drift between handoff narrative and on-disk state.

---

## 6. Mechanically-applicable instructions for next session (Rule #11)

### 6.1 Combined `Layer3_3C_Spec.md` + `Layer3_3D_Spec.md` session

**Type:** Query/rules nodes (3C is rules-based conflict detection; 3D is HITL aggregation gate orchestration). No LLM calls in either.

**Estimated length:** 3C ~350–450 lines; 3D ~250–350 lines. Combined fits in one session.

**3C scope** (per L3-Discovery §5.3):
- Reads all five 2A–2E typed payloads
- Detects cross-node inconsistencies that don't surface within any single node
- Initial rule set (enumerate + expand): 7 rules listed in L3-Discovery §5.3
- Output: list of structured conflict items consumed by 3D
- 14-section depth standard; mirror Layer2A pattern (query node) — `q_layer3c_cross_node_conflicts(...)` signature

**3D scope** (per L3-Discovery §5.4):
- Collects HITL items from 2A `prompt_required`, 2D HITL items, 2E HITL items, 3B `hitl_surface`, 3C conflict items
- Unified resolution flow (acknowledge / revise / blocker-cannot-acknowledge)
- Gate semantics: `gate_status: enum (pending / green)`. Layer 4 runs only on green.
- Output schema in L3-Discovery §5.4

**Pre-step reads for next session (Rule #13 ordering):**
1. **`aidstation-sources/CLAUDE.md` fully** (Rule #13 — first re-read, always)
2. `aidstation-sources/Project_Backlog_v13.md` (or highest `_vN`)
3. `aidstation-sources/handoffs/3B_Spec_Closing_Handoff_v1.md` (this file)
4. `aidstation-sources/Layer3_3A_Spec.md` and `aidstation-sources/Layer3_3B_Spec.md` — input contracts for 3C (3A/2A-2E payloads) and 3D (3B's `hitl_surface`)
5. `aidstation-sources/Layer2A_Spec.md` through `Layer2E_Spec.md` — 3C consumes all five
6. `aidstation-sources/handoffs/L3_Discovery_Closing_Handoff_v1.md` §5.3 + §5.4 — scope statements

**Open question 3C must resolve** (per L3-Discovery §5.3): if conflict patterns prove harder to enumerate than expected, revisit as LLM finishing step (D-49 in backlog).

**Open question 3D must resolve:** blocker-severity escalation semantics — what happens if an athlete tries to acknowledge a blocker? UX behavior + system-side response.

### 6.2 After 3C + 3D: `Control_Spec_v8.md` doc-map sync

Round 2 handoff §5 Option A is now reachable. Bump Control_Spec_v7 → v8 with §9 doc map updates for `Layer3_3B_Spec`, `Layer3_3C_Spec`, `Layer3_3D_Spec` all promoted to ✅ canonical. Should also update §3 data flow contract if 3C/3D specs surface anything that changes the cross-node typed-payload picture.

### 6.3 After Layer 3 specs complete: code

Per Andy's "push to production as we go" rule (Rule #13 anchors this in CLAUDE.md §Operating context), the post-Layer-3 forward move is implementation, not more spec writing ahead. Options surveyed during this session:

- **Option B (recommended, agreed during this session):** scaffold runtime + build L0–L3 nodes against shipped specs, while L4 spec drafts in parallel. Strangler-fig into the v1 Flask app at repo root.
- Option A: spec L4 + L5 first, then build whole pipeline. Risk: spec rot, slower to ship.
- Option C: build L0–L3 first, defer L4 entirely. Risk: L4 design after the rest is committed forces upstream rework.

**First piece of code to build (proposed):** a Layer 3 3A endpoint that consumes existing v1 athlete data and produces a state evaluation. Tiny surface, real production hit, validates the integration pattern. Confirm with Andy at session start.

### 6.4 Independent parallel tracks (unchanged from Round 2)

- D-50 Phase 1 integration deployment — this repo (root `init_db.py`, `routes/`, `app.py`)
- D-52 Catalog Migration Phase 1 — fuzzy-match HITL alias audit
- D-55 Garmin onto `provider_auth` — **paused** (Garmin API closed)
- D-57 Research re-evaluation cadence design
- D-58 / D-59 / D-60 / D-61 onboarding architectural design wave

None block Layer 3C/3D spec writing or the start of code implementation.

---

## 7. Forward pointers

- **Next session:** combined `Layer3_3C_Spec.md` + `Layer3_3D_Spec.md` per §6.1.
- **After 3D:** `Control_Spec_v8` doc-map sync per §6.2.
- **After Layer 3 specs:** code begins per §6.3.
- **Layer 4 design:** drafts in parallel with code implementation (Option B).
- **D-58–D-61 onboarding wave:** worth scoping as a single design "wave" rather than four isolated sessions, since the items interact heavily (account-first flow feeds Google Maps location flow feeds gear-from-proximity feeds session-unbinding).
- **D-57 research re-eval cadence:** out-of-cycle, any time before AIDSTATION pipeline goes to wider testing.

**Rules in force, unchanged:**
- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits
- #12 numeric version suffixes

**Rule new this session:**
- #13 every closing handoff names CLAUDE.md as the first re-read. Backstop against operating-context drift between sessions. Especially important when operating rules or framing have changed mid-stream (which they did this session — Q1/Q2/Q3 resolutions, push-to-prod rule, repo-reality reconciliation).

---

## 8. Gut check

**What this session got right.**

- **Repo-reality reconciliation caught before any code work.** The "separate repo" misconception in the planning track would have caused real misalignment if 3B's spec or any subsequent implementation had been written under it (e.g., assuming `provider_auth` could be designed without reference to `init_db.py`'s actual migration pattern). Surfacing it as Q1/Q2/Q3 stop-and-ask before doc edits avoided that.
- **Rule #13 captures a real failure mode.** Without it, a future session reading only `3B_Spec_Closing_Handoff_v1.md` would miss the v1+v2 selective-rebuild framing in CLAUDE.md §Operating context, the push-to-prod rule, and the Q1/Q2/Q3 resolutions — all of which shape every decision downstream. The First-session checklist already named CLAUDE.md as item 1, but handoff authors were inconsistent about reinforcing it. Rule #13 makes the responsibility explicit.
- **3B's decisions A/B/C/D resolved before writing.** Following the 3A pattern of putting the open-question resolution in §6 (as authoritative rules the LLM sees verbatim) means downstream consumers (3C, 3D, Layer 4) can rely on 3B's outputs meaning what they say. The LLM proposes, the floor enforces. Same shape that made 3A's confidence tags trustworthy.
- **Race-date-in-past as fatal, not soft pivot.** Aligns with spec-first principle. If state is wrong, fix the input. Saves Layer 4 from having to detect "is this plan still relevant?" — 3B blocks the pipeline before it gets there.

**Risks.**

- **Periodization-shape vocabulary committed before Layer 4 exists.** §6.2's `standard`/`compressed`/`extended`/`custom` + `start_phase` may need adjustment when Layer 4's input contract solidifies. Mitigation: §12 forward-reference. The vocabulary is small enough that renaming or adding values is a §6.2 patch.
- **HITL trigger thresholds (§6.1) and confidence floors (§6.5) are policy, not data-validated.** Same risk shape as 3A's floors. Post-launch iteration expected once real athlete data accumulates. The `dnf_recovery_window_weeks` mapping (quad_failure → 12, nutrition_blowup → 4, etc.) is the most exposed — reasoned defaults that may need quick adjustment.
- **3A → 3B coherence is partly implicit.** 3B reads 3A's `Layer3APayload` but the validator hooks for "if 3A short-term overreached AND compressed periodization → force HITL" rely on 3A having tagged trajectory correctly. Cross-spec coupling. Mitigation: 3C will likely surface inconsistencies during cross-node conflict detection.
- **D-55 pause means `provider_auth.session_blob` design is unvalidated.** The Integration v3 architecture decision is sound, but until Garmin API reopens we can't actually wire `garth` session capture against `provider_auth`. Other providers (Polar, Wahoo, COROS, etc.) don't use `session_blob` — they're OAuth-token-based. The `session_blob` column will sit unused on `provider_auth` until Garmin reopens.
- **Closing handoff is light on "what didn't get done."** Most of D-57 / D-58 / D-59 / D-60 / D-61 onboarding wave is still queued. None blocks Layer 3 spec writing or code start, but they'll surface as soon as serious onboarding UX work begins.

**What might be missing.**

- **3B + 3C interaction is implicit.** 3C reads 2A-2E payloads but may also want to reason about 3B's `goal_viability.viability` and `periodization_shape.mode` (e.g., `compressed` periodization + 2D HIGH-risk discipline → escalate). Decide explicitly in 3C spec whether 3C reads 3B's payload too.
- **Plan Management spec (D-27) still unstarted.** Becoming a thicker dependency: 3A's `data_density`, 3B's `hitl_surface`, 3D's gate state all touch Plan Management surfaces. Worth scoping soon.
- **No `Layer1_Spec_v3` standalone doc.** The §H.3 amendment landed in Onboarding v3 → v4. Layer 1 sourcing lives in Control_Spec §3 + Onboarding v4 + Integration v3 §7. `q_layer1_payload` function spec is unwritten — likely lands as part of D-51 (Layer 1 field inventory) when implementation starts.
- **Test scenarios in 3B §13 assume LLM behavior; no concrete success criteria.** Each TS asserts shape (which enum values appear, which HITL items emit, which observations auto-emit) but not specific reasoning text. Implementation should snapshot first-run reasoning text and freeze as regression baselines once real testing begins.

**Best argument against this session's scope.**

You could argue the reconciliation pass should have been its own session (4 files) and 3B should have been a clean fresh-start session (1 file + close-out). Counter: combining was the right call given context — the repo-reality reconciliation surfaced operating rules (v1+v2 selective-rebuild, push-to-prod, strangler-fig) that 3B was about to need anyway. Splitting would have meant reading CLAUDE.md's new §Operating context cold at next session start without the in-session context of why it changed. Ceiling held loosely; quality didn't visibly degrade.

Alternatively, you could argue Rule #13 should have been added earlier, retroactively, by every prior handoff author — and the fact that it took until session 8+ to land is a process failure. Counter: the rule earns its existence from the specific failure mode this session surfaced (the "separate repo" drift that survived multiple handoffs because no session re-read CLAUDE.md). Adding it earlier would have been speculative; adding it now is grounded in observed failure.

---

*End of 3B-Spec closing handoff.*
