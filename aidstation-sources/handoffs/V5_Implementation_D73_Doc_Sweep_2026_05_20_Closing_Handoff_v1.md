# D-73 Doc-Sweep — Spec-Touchpoint Cleanup Batch — Closing Handoff

**Session:** Doc-only cleanup session following the Phase 2.4 closing handoff. Andy opened with a question about the §5.1-vs-§6 reconciliation flag from the predecessor → "do the cleanup first and then we can get into 3.1 if we have space" → after the §5.1 cleanup, "do other doc sweep nits." Spec-only batch closing 1 follow-up clarity item + 4 "anytime OK" doc-sweep nits from `CARRY_FORWARD.md`. No code change; tests green at the inherited baseline. Phase 3.1 deferred to a fresh session per the 5-file ceiling + the `/plan-mode` gate required by Triggers #2 + #5.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_2_4_Closing_Handoff_v1.md`
**Branch:** `claude/review-handoff-clarification-IJKtJ` (harness-pinned; scope-aligned for the clarification-then-cleanup arc that actually ran).
**Status:** 🟢 5 substantive spec files (at ceiling) shipped across 2 commits (`226d0dd` §5.1 cleanup; `81946b6` doc-sweep batch). 901 tests green (unchanged — no code touched).

---

## 1. Session-start verification (Rule #9)

Anchor-check of `V5_Implementation_D73_Phase_2_4_Closing_Handoff_v1.md` §8 via `./aidstation-sources/scripts/verify-handoff.sh` + 901-test baseline.

| Claim | Anchor | Result |
|---|---|---|
| All §8 anchor paths from predecessor exist on disk | `verify-handoff.sh` [1] | ✅ all 18 paths ✅ |
| Predecessor §8 table reads green for the Phase 2.4 builder + spec-touchpoint claims | `verify-handoff.sh` [3] | ✅ table extracted clean |
| `python -m pytest tests/` → 901 passed | bootstrap + rerun | ✅ `901 passed in 2.20s` after one-time `pip install --break-system-packages` |
| Working tree clean at session start | `git status` | ✅ |
| Branch is harness-pinned; scope of work (clarification + cleanup) aligns | `git branch --show-current` | ✅ no H1 rename needed |

**No drift between predecessor narrative and on-disk state.** Runtime-env quirk repeated (cloud container's default `pytest` is `uv tool install` isolated Python; documented working path used per Phase 2.4-Prep §1).

---

## 2. Session narrative

Andy opened with the Phase 2.4 closing-handoff URL + "check this out and lets work" + a specific question about the §5.1-vs-§6 reconciliation flag from §2 of that handoff. Plain-English explanation given (the spec contained two readings of `also_satisfies`; the deployed data fits only §6's one-hop-via-toggle-names reading; the builder implements §6; a reconciliation note was added in the prior session). Andy followed with "do we need to clean up the item above?" → exploratory question, recommended rewriting the §5.1 pseudo-code in place rather than carrying the compensating note. Confirmed scope = cleanup first, then assess Phase 3.1 space.

After the §5.1 cleanup committed (`226d0dd`), Andy said "do other doc sweep nits." Surveyed `CARRY_FORWARD.md` Doc-sweep nits for "anytime OK" small spec-touchpoint edits (excluding ones explicitly scoped to a future phase). Six candidates surfaced; the 5-file ceiling left room for only 4 more after the §5.1 cleanup. Picked the 4 highest-audit-trail-value items (Layer 2A SQL + Open Item; Layer 2D §3 enum count; Upstream Plan §4 row 2.2 read-tables; Layer 2B §13.1 TRN swap) and explicitly deferred the 5th (`Layer2E_Spec.md` §6.1 + §14 D-26 wording) to the next Layer 2E touchpoint where it naturally pairs with the larger §3 sub-shape rewrite.

Phase 3.1 (Layer 3A LLM driver) discussed but explicitly deferred — Triggers #2 + #5 require a `/plan-mode` gate at session start, and the ~6-8 substantive files would compound the ceiling break started here. Cleaner as a fresh session.

---

## 3. File-by-file edits

### 3.1 `aidstation-sources/Layer2C_Spec.md` — §5.1 pseudo-code rewrite + reconciliation note shrink (commit `226d0dd`)

§5.1's pseudo-code block (lines 75-87 post-edit) now does the one-hop expansion of `also_satisfies` via the referenced toggle's `paired_equipment_categories` (matching §6 + matching the deployed data shape + matching `layer2c/builder.py:_build_effective_pool`). The prior `effective_pool.update(toggle_def.also_satisfies)` line — which would have dumped toggle names into the equipment pool, a silent no-op — replaced by a `for other_name in toggle_def.also_satisfies` loop with an explicit no-cascade comment pointing to §6.

The trailing reconciliation paragraph shrunk from a "compensating note" framing to an "audit trail" framing — pseudo-code is now self-correct so the note's job is just to preserve the change's provenance.

### 3.2 `aidstation-sources/Layer2A_Spec.md` — §5.2 `pla.default_inclusion` drop + §12 Open Item 2A-1 partial-close (commit `81946b6`)

(a) §5.2 SELECT no longer references `pla.default_inclusion` (the column doesn't exist on `layer0.phase_load_allocation`). Added a Key-points bullet noting that `default_inclusion` is code-derived from `notes_conditions` per §5.3 — matches `layer2a/builder.py`.

(b) §12 Open Item 2A-1 row flipped to 🟡 Partial-close with the Phase 5.1 forward-pointer (v1 templates shipped Andy-quality 2026-05-19; full athlete-facing review surfaces with the orchestrator vertical slice when `race_week_brief` renders to Andy in production).

### 3.3 `aidstation-sources/Layer2D_Spec.md` — §3 + §4 "9-value" → "11-value" enum (commit `81946b6`)

Two 1-character edits flip `InjuryRecord.injury_type` enum count from "9-value" to "11-value" in the §3 dataclass comment + the §4 validation rule. Matches `Athlete_Onboarding_Data_Spec_v5.md` §B.1.1 + deployed `injury_log.injury_type` + `athlete.KNOWN_INJURY_TYPES` + `layer4/context.py:InjuryRecord`.

### 3.4 `aidstation-sources/Layer2B_Spec.md` — §13.1 TRN-008/TRN-009 swap (commit `81946b6`)

Three-line edit to §13.1 AR PGE 2026 test scenario:
- "Flat Water (TRN-008): 15%" → TRN-009
- "Gap: TRN-008 Flat Water" → TRN-009
- "TRN-008 gap → look up rule → proxy=Pool (TRN-009)?" → TRN-009 gap → proxy=Pool (TRN-008)

Canonical deployed vocab per `etl/sources/migrate_terrain_types.sql` is TRN-008 = Pool, TRN-009 = Flat Water (the IDs were swapped vs the spec example). Phase 2.3 Layer 2B tests already use deployed IDs; this was the lone spec holdout.

### 3.5 `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 2.2 read-tables rewrite (commit `81946b6`)

Row 2.2 read-tables list rewritten to name the actual Layer 2D read tables per `Layer2D_Spec.md` §5.2 + §5.4 + §5.6 (`sport_discipline_bridge` + `sport_exercise_map` + `exercises` + `disciplines` + `discipline_substitutes` + `discipline_training_gaps`). Prior `injury_profiles` + `exercise_risk_assessments` references removed — neither table exists in `etl/layer0/schema.sql`.

### 3.6 `aidstation-sources/CARRY_FORWARD.md` (bookkeeping — outside ceiling per B3)

Doc-sweep nits ledger updated to strike the 5 items closed this session (§5.1 cleanup + 4 doc-sweep nits). Deferred item (`Layer2E_Spec.md` §6.1 + §14 D-26 wording) remains in the active list.

---

## 4. Code / tests

Zero code touched. `tests/` count unchanged at 901.

Sanity rerun after each commit: `python -m pytest tests/ -q` → `901 passed`.

---

## 5. Operational sequence for Andy on Neon

N/A — spec-only session. The Phase 2.4-Prep operational sequence (3 SQL migrations + ETL re-run) is still the live prerequisite for the Phase 2.4 §5.0 manual walkthrough scenarios, unchanged.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Phase 3.1 — Layer 3A LLM driver** (deferred from this session; the architect-recommended forward move per the predecessor §6.1). Same scope, same triggers, same precedent (Layer 4 Step 4a):

- Pydantic schema already shipped (`Layer3APayload` + sub-models in `layer4/context.py`).
- Capped retry + validator (lightweight; 3A has §4 validation rules).
- Anthropic SDK extended-thinking + tool-use; dependency-injectable `LLMCaller` per Layer 4 precedent.
- Prompt body source decisions D1–D10 (tool-use; extended thinking budget; payload rendering; retry context; schema length caps; voice).

**Opens with a `/plan-mode` gate** — Triggers #2 (prompt body design) + #5 (architectural alternatives). Estimated 6-8 substantive files (over ceiling — precedented).

### 6.2 Alternative pivots

Unchanged from predecessor §6.2:

- **Layer 4 Step 7** — env-gated `ANTHROPIC_API_KEY` scaffolding (~3-4 files). Unblocks Phase 5 vertical slice in parallel.
- **§H.2 / §J / §I.1 form-refresh PR** — paired alignment to wire Layer 2B + Layer 2E input-source surfaces (~6-8 files, over ceiling).
- **Plan Management spec authorship** — de-stubs Layer 2E §5.8 heat acclim.
- **D-73 Phase 1.4** — D-52 catalog migration sequencing.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration.
- **Manual §5.0 walkthrough** of the accumulated 69 scenarios (Phase 2.4 ones need Neon migrations + ETL re-run first).

### 6.3 Operating notes for next session

Read order per Rule #13:

1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff
3. `aidstation-sources/CARRY_FORWARD.md` — doc-sweep ledger now lists 5 closed items + 1 remaining Layer 2E nit
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward):** the cloud container's default `pytest` is `uv tool install` isolated Python; working path is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

**If picking Phase 3.1:** open with the `/plan-mode` gate walking D1–D10 source decisions per the predecessor §6.3 guidance. Reuse Layer 4 Step 4a as the precedent.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | §5.1 cleanup: rewrite pseudo-code in place + shrink the reconciliation note to an audit-trail paragraph | Andy 2026-05-20 (after recommendation) | The prior Phase 2.4 session added a reconciliation note below misleading pseudo-code. The note compensated rather than fixed; a reader copying the literal pseudo-code into their head would build the wrong mental model. Rewriting the pseudo-code to match §6 + shrinking the note to an audit trail removes the compensating-text pattern. |
| 2 | Doc-sweep batch scope: 4 nits this session, defer the 5th (Layer 2E §6.1 + §14 D-26 wording) | Architect-pick + ceiling | 5 spec files in the candidate set + the §5.1 cleanup = 6 substantive files, over ceiling. Per CLAUDE.md "propose splitting before starting," pick the 4 highest-audit-trail-value items and defer the Layer 2E one to its natural future touchpoint (the larger §3 sub-shape rewrite once Layer 1 §I.1 / §B form refresh lands). |
| 3 | Phase 3.1 deferred to a fresh session | Architect-pick | Phase 3.1 needs a `/plan-mode` gate at session start (Triggers #2 + #5) + lands ~6-8 substantive files. Bundling into this session would compound the ceiling break already started and bury the LLM-driver design decisions under a doc-cleanup commit history. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `Layer2C_Spec.md` §5.1 pseudo-code does one-hop expansion via `lookup_toggle(other_name, ...).paired_equipment_categories` | ✅ grep |
| `Layer2C_Spec.md` §5.1 reconciliation block reads "Audit trail (§5.1 vs §6 reconciliation)" — no longer "compensating note" framing | ✅ grep |
| `Layer2A_Spec.md` §5.2 SELECT does NOT contain `pla.default_inclusion` | ✅ grep |
| `Layer2A_Spec.md` §5.2 Key-points bullet documents code-side derivation of `default_inclusion` from `notes_conditions` | ✅ grep |
| `Layer2A_Spec.md` §12 Open Item 2A-1 reads "🟡 Partial-close 2026-05-20" with Phase 5.1 forward-pointer | ✅ grep |
| `Layer2D_Spec.md` §3 `InjuryRecord.injury_type` comment reads "11-value enum from B.1.1" | ✅ grep |
| `Layer2D_Spec.md` §4 validation rule 4 reads "11-value enum (B.1.1)" | ✅ grep |
| `Layer2B_Spec.md` §13.1 reads "Flat Water (TRN-009)" + "Gap: TRN-009 Flat Water" + "proxy=Pool (TRN-008)" | ✅ grep |
| `Upstream_Implementation_Plan_v1.md` §4 row 2.2 read-tables list names the 6 actual Layer 2D tables | ✅ grep |
| `Upstream_Implementation_Plan_v1.md` §4 row 2.2 does NOT contain `injury_profiles` or `exercise_risk_assessments` | ✅ grep |
| `CARRY_FORWARD.md` doc-sweep ledger strikes the 5 closed nits | ✅ inspection |
| `python -m pytest tests/` → 901 passed | ✅ `901 passed in 1.23s` post final commit |
| Working tree clean after both commits + push | ✅ `git status` clean; `81946b6` pushed to remote |
| `CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection (updated in this session) |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (5 files; AT the 5-file ceiling):**

1. Modified `aidstation-sources/Layer2C_Spec.md` — §5.1 pseudo-code rewritten to match §6 one-hop semantics; reconciliation note shrunk to audit-trail paragraph (commit `226d0dd`).
2. Modified `aidstation-sources/Layer2A_Spec.md` — §5.2 drops `pla.default_inclusion` + adds Key-points note on code-side derivation; §12 Open Item 2A-1 flipped to 🟡 partial-close (commit `81946b6`).
3. Modified `aidstation-sources/Layer2D_Spec.md` — §3 + §4 enum count "9-value" → "11-value" (commit `81946b6`).
4. Modified `aidstation-sources/Layer2B_Spec.md` — §13.1 TRN-008/TRN-009 swap (commit `81946b6`).
5. Modified `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 2.2 read-tables list rewritten (commit `81946b6`).

**Bookkeeping (3 files; outside ceiling per B3):**

6. Modified `aidstation-sources/CARRY_FORWARD.md` — doc-sweep ledger updated across both commits to strike the 5 closed nits.
7. Modified `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Tests note unchanged at 901.
8. New `aidstation-sources/handoffs/V5_Implementation_D73_Doc_Sweep_2026_05_20_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` Doc-sweep nits ledger:

- ~~`Layer2C_Spec.md` §5.1 pseudo-code literal-vs-§6 drift~~ ✅ Resolved 2026-05-20 (this session).
- ~~`Layer2A_Spec.md` §5.2 SQL `pla.default_inclusion` reference~~ ✅ Resolved 2026-05-20 (this session).
- ~~`Layer2A_Spec.md` Open Item 2A-1~~ 🟡 Partial-close 2026-05-20 (this session) + Phase 5.1 forward-pointer.
- ~~`Layer2D_Spec.md` §3 "9-value enum" wording~~ ✅ Resolved 2026-05-20 (this session).
- ~~`Layer2B_Spec.md` §13.1 TRN-008/TRN-009 swap~~ ✅ Resolved 2026-05-20 (this session).
- ~~`Upstream_Implementation_Plan_v1.md` §4 row 2.2 read-tables list~~ ✅ Resolved 2026-05-20 (this session).

Remaining (untouched this session, in active list):

- `routes/onboarding.py:710` docstring tense — fold into Phase 4/5.
- `Layer4_Spec.md` §4.5 source-pointer wording — fold into Phase 5.1.
- `Race_Events_D66_Design_v1.md` §8.3 `open_ended` → `no-event` — fold into Phase 4.2.
- `HealthConditionRecord.system_category` enum drift — its own §B onboarding form refresh PR.
- `routes/injuries.py:BODY_PARTS` 24 → 41 canonical alignment — same §B form refresh PR.
- `Layer2B_Spec.md` §7 + §13 pct unit alignment — no spec edit needed (already aligned).
- §H.2 + §J + §I.1 form-refresh PRs — bigger work; tracked separately.
- Plan Management spec authorship — bigger work; tracked separately.
- `Layer2E_Spec.md` §6.1 + §14 D-26 wording — **deferred this session**; folds into the next Layer 2E touchpoint (naturally pairs with the larger §3 sub-shape rewrite once Layer 1 §I.1 / §B form refresh lands).
- `Layer2E_Spec.md` §3 input shape vs deployed Layer1* types — folds into next Layer 2E touch.
- `Layer2E_Spec.md` §3 TargetEvent shape vs deployed `RaceEventPayload` — closer alignment with §H.2 form refresh.
- `Layer1Performance.ffm_kg` field promotion — onboarding §A/§F addition.
- `etl/sources/parsed_substitutes.json` curation cadence + K-parser source location doc task.

No new orthogonal carry-forwards this session.

Manual §5.0 walkthrough count unchanged at 69. Phase 2.4 scenarios still need Andy's Neon migrations + ETL re-run before they're runnable.

---

**End of handoff.**
