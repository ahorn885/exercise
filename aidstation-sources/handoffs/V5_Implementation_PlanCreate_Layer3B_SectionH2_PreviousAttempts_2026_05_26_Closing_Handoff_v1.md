# Layer 3B §H.2 deployed-shape gap — structured `previous_attempts` (Slice 2 of 2) — Closing Handoff

**Session:** Andy: "The new goal fields DID populate in the race event details screen. Let's keep working." That confirmed Slice 1's owed deploy-verify (the scalar §H.2 goal fields render + persist in prod). Session-start verification clean. Offered the designated next moves; Andy picked **Slice 2 — `previous_attempts`** (the pre-agreed second half of "Full §H.2" chosen last session). This session shipped it: the structured prior-attempt records end-to-end, closing the §H.2 capture gap entirely.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_PlanCreate_Layer3B_SectionH2_GoalContextScalars_2026_05_26_Closing_Handoff_v1.md`
**Branch:** `claude/friendly-bell-OsRrS` (harness-pinned; Slice 1 shipped on `claude/v5-implementation-blockers-PV5LH` → merged to `main` as #184, present in this branch's history)
**Status:** 9 substantive code files (same coupled capture surface as Slice 1) + 1 spec amend + 3 test files + bookkeeping. Full suite **1760 passed / 16 skipped** (+14 over the 1746 Slice-1 baseline). **No code blocker; one owed Neon migration (`python init_db.py`) + redeploy.**

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` clean — no ❌; working tree clean on the branch; the predecessor (Slice 1) §8 table extracted with all ✅. Spot-checked the Slice-1 claims on disk: `goal_outcome`/`first_time_at_distance`/`time_goal`/`race_pack_weight_kg` ALTERs in `init_db.py`; the 4 scalar fields on `RaceEventPayload`; `VALID_GOAL_OUTCOMES` + the columns in `race_events_repo`; `section_h2_kwargs` built + splatted in `layer4/orchestrator.py`. All present. #184 is in this branch's log. No drift.

## 2. The problem (plain language) + diagnosis

Slice 1 captured the **scalar** §H.2 goal fields. The remaining half is **`previous_attempts`** — a structured list of prior tries at this event/distance. Layer 3B was **already fully built to consume it**: `layer3b/builder.py` reads `previous_attempts` in the event-mode goal block (`:572-580`), the cache key (`:728`), the `3B.dnf_recurrence_risk` HITL trigger (`_has_dnf_attempt` `:1020` + `_dnf_recovery_window` `:1028` + the emit at `:1125`), and the confidence floor (`:1252`); `layer3b/cached_wrapper.py` already accepts + threads + cache-keys it (`:158`, `:208`, `:246`). But the deployed `race_events` row never stored it, `RaceEventPayload` didn't carry it, and the orchestrator passed nothing — so **`3B.dnf_recurrence_risk` could never fire** (the last starved HITL flag) and the LLM never saw an athlete's DNF history.

**Impact:** an athlete with a quad-failure DNF 8 weeks out (recovery window 12wk > time_to_event) got no `dnf_recurrence_risk` warning; the goal-viability reasoning had no prior-attempt evidence. **This slice is pure capture** — zero changes to the consume side (builder + cached_wrapper untouched).

## 3. File-by-file edits (Slice 2 = structured `previous_attempts`)

### 3.1 `init_db.py` — schema (migration)
1 idempotent `ALTER TABLE race_events ADD COLUMN IF NOT EXISTS previous_attempts JSONB NOT NULL DEFAULT '[]'::jsonb` after the §H.2 scalar block (shape mirrors `race_terrain`). No CHECK (free-form JSONB, like `race_terrain`); the route parser + `PreviousAttempt` payload model are the gates. Default `'[]'` → no backfill; fresh DB converges via the same ALTER. Also dropped the now-stale "`previous_attempts` is the follow-on slice" line from the Slice-1 comment.

### 3.2 `layer4/context.py` — `PreviousAttempt` model + `RaceEventPayload` field
New `PreviousAttempt(_Base)`: `outcome: Literal["Finished","DNF","DNS"]` + `dnf_cause: str | None (max_length=50)`. `dnf_cause` is a **loose bounded str** (not an enum) so an out-of-vocab value resolves to the builder's 8wk default rather than failing the row at load; the form offers the closed vocab. `RaceEventPayload.previous_attempts: list[PreviousAttempt] = Field(default_factory=list)` after `race_pack_weight_kg`; updated the §H.2 comment (dropped "follow-on slice / not yet carried here").

### 3.3 `race_events_repo.py`
- New `VALID_PREVIOUS_ATTEMPT_OUTCOMES = ("Finished","DNF","DNS")` + `VALID_DNF_CAUSES = ("quad_failure","nutrition_blowup","injury_during_event","weather","timeout","other")` — **`VALID_DNF_CAUSES` is lock-step with the keys of `layer3b.builder._DNF_RECOVERY_WINDOW_WEEKS`**.
- Imported `PreviousAttempt`.
- `load_race_event_payload`: column added to SELECT + list-or-str JSONB hydration (mirrors `race_terrain`) → `[PreviousAttempt(...)]` → onto the payload.
- `get_race_event` (form pre-fill): column added to SELECT + the same JSONB hydration.
- `create_race_event` + `update_race_event`: a `previous_attempts: list[dict] | None = None` kwarg + INSERT/UPDATE column + `?::jsonb` placeholder + `json.dumps(previous_attempts or [])`. **`etl_version_set` stays the last INSERT param** (previous_attempts inserted before it), so the "last param" test holds. No repo-side validation raise (matches `race_terrain`, not `goal_outcome` — the JSONB column has no CHECK).

### 3.4 `layer4/orchestrator.py` — thread into 3B
Added `previous_attempts` to `section_h2_kwargs`: `[{"outcome": a.outcome, "dnf_cause": a.dnf_cause or ""} for a in target_race_event.previous_attempts] or None` — plain dicts the builder consumes via `.get("outcome")` / `.get("dnf_cause")`. None/empty in no-event mode (unchanged wrapper resolution). Updated the comment block.

### 3.5 Templates — capture UI
New shared partial **`templates/_previous_attempts_editor.html`** modeled on `_race_terrain_editor.html` (repeating row: `outcome` `<select>` + `dnf_cause` `<select>`, both hardcoded closed sets; distinct JS hook IDs — `#previous-attempts-rows` / `#add-previous-attempt-row` / `#previous-attempts-template` / `.previous-attempt-row` / `data-action="remove-previous-attempt-row"` — so it co-renders with the terrain editor; nonce'd clone/remove JS). Included in the **Goal** section (after `time_goal`) of BOTH `templates/profile/race_event_edit.html` (`existing_previous_attempts` from `race.previous_attempts`) and `templates/onboarding/target_race.html` (from `target.previous_attempts`).

### 3.6 Routes — parse + evict
- `routes/race_events.py`: imported `VALID_PREVIOUS_ATTEMPT_OUTCOMES` + `VALID_DNF_CAUSES`; new `_parse_previous_attempts` (indexed `previous_attempts[N][outcome|dnf_cause]`, drop-on-invalid-outcome, dnf_cause→None when out-of-vocab; mirrors `_parse_race_terrain`); wired into `new_race` (create) + `update_race` (update); folded into `periodization_changed` (a `previous_attempts` change flips the 3B cache key → 3B re-runs → `dnf_recurrence_risk` + shape can move).
- `routes/onboarding.py` `target_race_save`: imported `_parse_previous_attempts`; parsed + passed to BOTH update + create branches; mirrored the periodization-evict fold. **Folded-in fix:** `_get_target_race_row`'s SELECT was missing **all** §H.2 goal columns (Slice 1 only added them to `get_race_event`, not this onboarding helper) — so the onboarding form's goal-field pre-fill rendered blank and the periodization-diff always read `None` (over-evicting on re-save). Added `previous_attempts` + the 4 Slice-1 goal columns to the SELECT + the JSONB hydration; this corrects both the pre-fill and the diff in the onboarding path.

### 3.7 `Athlete_Onboarding_Data_Spec_v6.md §H.2` (in place)
Flipped the goal-context amendment note from "`Previous Attempts` … is a follow-on slice / not yet captured" → "Slice 2 shipped 2026-05-26 … the full §H.2 goal set is now captured." Added a `Previous Attempts` row to the field table (JSONB `{outcome, dnf_cause}` shape; vocab; the `dnf_recovery_window` mapping; periodization-grade eviction). In-place amend (matches the Slice-1 in-place precedent — no `_v7`).

### 3.8 Tests (+14)
- `tests/test_race_events_repo.py`: `previous_attempts: []` added to `_race_row`; new `TestSectionH2PreviousAttempts` (7: create serialize / create empty-default / update serialize / load hydrate / load-from-str (sqlite path) / load empty-default / get hydrate). Fixed `test_update_serializes_race_terrain`'s positional tail assertion (`params[-3]`→`params[-4]`) — the new `previous_attempts = ?::jsonb` SET clause shifted the tuple tail.
- `tests/test_routes_race_events.py`: imported `_parse_previous_attempts`; new `TestParsePreviousAttempts` (7: DNF+cause / Finished→cause-None / invalid-outcome drop / blank-outcome drop / invalid-cause→None / multi-row order / empty form).
- `tests/test_layer4_orchestrator.py`: `previous_attempts` kwarg added to `_queue_target_race_event` + the fake row; extended `test_section_h2_goal_fields_thread_to_3b` to pass + assert `previous_attempts` threads as dicts.

## 4. Code / tests

Full suite **1760 passed / 16 skipped** in `/tmp/venv` (+14 over 1746: +7 repo, +7 route helpers; orchestrator test extended in place, not added). `py_compile` clean on all 6 changed Python files; the 3 templates parse clean via `jinja2.Environment().parse`. (Container: Neon egress blocked, PyPI works, `pytest` not in `requirements.txt` — `CLAUDE.md` Environment quick-reference.)

## 5. Owed action (Andy's hands)

**⚠ Neon migration (`python init_db.py`) + redeploy.** The 1 new column (`previous_attempts JSONB NOT NULL DEFAULT '[]'`) is idempotent + nullable-by-default (no backfill). After: redeploy (triggered by merging the PR) + smoke-check the race-event form's new "Previous attempts" sub-form (onboarding + profile edit) — add a `DNF` + `quad_failure` row, save, confirm persistence + that a fresh plan-gen for a race inside the 12-week recovery window surfaces `3B.dnf_recurrence_risk`. (Container can't reach Neon, so this stays an Andy's-hands action, same as every prior migration.)

## 6. Next session pointers

### 6.1 §H.2 is now fully captured — `dnf_recurrence_risk` unblocked
Both §H.2 slices are shipped. **L3B-P-3 is now safe to do:** tighten the evidence_basis mode-discriminator from `Layer3BEvidenceBasisWarning` (warn, per D9) → `Layer3BOutputError("evidence_basis_mode_mismatch")` (hard) — it was gated on L3B-P-2 closing, which it now has. Small, self-contained, in `layer3b/builder.py` (the D9 warn site) + a spec note. See `CARRY_FORWARD.md` L3B-P-3.

### 6.2 The two designed-but-unbuilt blockers (untouched this session)
- **#1 `Layer4ShapeInfeasibleError`** — fully designed (`Layer4_Spec §10.2`: 4 pure-function detection classes, tolerance defaults, TS-10..TS-13), **zero code**. Evaluates after `phase_structure_from_3b()` / before per-phase synthesis. One OPEN routing decision (§10.2/C3): inline athlete error now vs the unbuilt 3D gate — the §14-retro recommends inline now. Self-contained, one PR.
- **#4 3C/3D/3.5 HITL gate** — spec-first (no per-node specs exist); **stop-and-ask trigger #4**.

### 6.3 Operating notes for next session (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items (L3B-P-2 now fully closed; L3B-P-3 unblocked).
4. This handoff.
5. `./scripts/verify-handoff.sh`.
**Before a live plan-gen walk:** confirm Andy's profile has `body_weight_kg` + `height_cm` (the 2E gate) and run the owed `init_db.py`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Build Slice 2 (`previous_attempts`) this session | Andy (confirmed at the scope question) | The pre-agreed second half of "Full §H.2" from last session; unblocks the last starved HITL flag. |
| 2 | `outcome` as a strict `Literal`; `dnf_cause` as a loose bounded `str` | Claude | `outcome` drives DNF detection (small stable set, form-gated → Literal backstop). `dnf_cause` keys a builder mapping that already defaults unknown→8wk, so a loose str avoids a payload-validation failure on a future vocab expansion + a layering import of builder internals into `context.py`. |
| 3 | JSONB column, no DB CHECK (mirror `race_terrain`, not `goal_outcome`) | Claude | Structured free-form list, same storage shape as `race_terrain`; the route parser + payload model are the gates. A CHECK on JSONB array contents is heavy + brittle. |
| 4 | `previous_attempts` edits → periodization-grade eviction | Claude | A change flips the 3B cache key → 3B re-runs, `dnf_recurrence_risk` + confidence floor + shape can move; same grade as the Slice-1 goal fields. |
| 5 | Fold in the `_get_target_race_row` SELECT fix (add the missing §H.2 goal columns) | Claude | Slice 1 added the goal columns to `get_race_event` but not this onboarding helper, leaving the onboarding form's goal pre-fill blank + the periodization-diff over-evicting. It's the same §H.2 surface this slice touches; fixing it here is correct + low-risk. |

## 8. Session-end verification (Rule #10)

| Check | File:anchor | Method | Result |
|---|---|---|---|
| `previous_attempts JSONB` ADD COLUMN | `init_db.py` (after the §H.2 scalar ALTER block) | read | ✅ |
| `PreviousAttempt` model + `previous_attempts` field on `RaceEventPayload` | `layer4/context.py` (after `RaceTerrainEntry` / after `race_pack_weight_kg`) | read | ✅ |
| `VALID_PREVIOUS_ATTEMPT_OUTCOMES` + `VALID_DNF_CAUSES` + column in create/update/load/get + hydration | `race_events_repo.py` | read | ✅ |
| `previous_attempts` in `section_h2_kwargs` (dict-mapped, `or None`) | `layer4/orchestrator.py` | read | ✅ |
| new partial + included (after `time_goal`) in both forms | `templates/_previous_attempts_editor.html`, `templates/profile/race_event_edit.html`, `templates/onboarding/target_race.html` | read + jinja parse | ✅ |
| `_parse_previous_attempts` + wired into create/update/onboarding + periodization-evict fold | `routes/race_events.py`, `routes/onboarding.py` | read | ✅ |
| `_get_target_race_row` SELECT now carries §H.2 goal cols + previous_attempts + hydration | `routes/onboarding.py` | read | ✅ |
| §H.2 amendment flipped + `Previous Attempts` row added | `Athlete_Onboarding_Data_Spec_v6.md` | read | ✅ |
| +14 tests green; full suite 1760/16 | `tests/test_race_events_repo.py`, `tests/test_routes_race_events.py`, `tests/test_layer4_orchestrator.py` | pytest (`/tmp/venv`) | ✅ |
| `CURRENT_STATE.md` last-shipped = this handoff; D-73 §H.2 note = fully closed | `CURRENT_STATE.md` | read | ✅ |
| `CARRY_FORWARD.md` L3B-P-2 = closed; L3B-P-3 = unblocked | `CARRY_FORWARD.md` | read | ✅ |

## 9. Files shipped this session

**Substantive (code, 9):** `init_db.py`, `layer4/context.py`, `race_events_repo.py`, `layer4/orchestrator.py`, `templates/_previous_attempts_editor.html` (new), `templates/profile/race_event_edit.html`, `templates/onboarding/target_race.html`, `routes/race_events.py`, `routes/onboarding.py` (over the 5-file ceiling — same coupled capture surface as Slice 1, pre-approved when Andy picked "Full §H.2" + confirmed Slice 2).
**Spec:** `Athlete_Onboarding_Data_Spec_v6.md` (§H.2 in-place amend).
**Tests:** `tests/test_race_events_repo.py`, `tests/test_routes_race_events.py`, `tests/test_layer4_orchestrator.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
