# Injury-Form Refresh — Side-Field Drop + Wrist-Extension Vocab Fold + Per-Body-Part Constraint Gating — Closing Handoff

**Session:** Picked up the form-feedback batch (unblocked; PR #156's `primary_movement` Neon migration is still parked). Shipped **slice B — the injury-form refresh** = feedback items **#4** (Side-field drop + `"Pain with wrist extension"→"extension"` vocab generalization) **+ #6** (movement-constraints dynamic per body part), bundled per Andy's call.
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_Layer2E_SpecSweep_UpstreamSourced_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/v5-layer2e-handoff-dBxzn` (harness-pinned; name predates this scope) → **PR #158** (merged).
**Status:** Shipped + merged. 5 substantive code/spec files + tests (over the 5-file ceiling, authorized at gate). **No deploy owed** beyond the standing PR #156 Neon migration; manual UI eyeball owed (no sandbox runtime).

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the predecessor (SpecSweep) handoff. Two ❌ paths flagged, both confirmed mechanically as **script artifacts, not drift**:
- `tests/test_layer2_modality.py` — intentionally deleted by best-fit Slice-6 (modality path retired). Expected absent.
- `tests/test_v10/v11_parsers.py` — the script mis-parsed the handoff's `v10/v11` shorthand as a path; the real file is `etl/tests/test_v11_parsers.py`, which exists.

PR #156 (`primary_movement` code + migration) and PR #157 (Layer 2E spec sweep) both merged into branch history; working tree clean on entry. Only genuinely owed item remains the parked PR #156 Neon migration (Andy's hands; out of scope). Reconciliation: clean.

---

## 2. Session narrative

Andy: "let's work." The architect-recommended forward move (run PR #156 migration on Neon, then deploy) is blocked on Andy. Presented the unblocked menu; Andy picked the **form-feedback UI batch**, then — when shown that the §6.2 pointer was too terse — asked me to find the original feedback. Located it in the Slice1 walkthrough handoff §6.3 (line 76): five deferred items, **all five touch a layer** (the §6.2 "Template/route work" framing undersold them). Clustered into slice A (race-event form: 1+2+3), B (injury form: #4), C (schedule: #5). Andy picked **B first**.

Grounding B against the code surfaced that the "injury-form refresh" is really **#4 + #6** paired (CARRY_FORWARD #4 line 105 + #6 line 106), and raised a genuine fork (Side direction) + a vocab call (trigger #2) + a mapping curation (trigger #5). Ratified four decisions at AskUserQuestion gates (§7), then implemented, tested, and shipped.

Key reconnaissance facts that shaped the design:
- `injury_log.side` is **output-only** for Layer 2D (athlete.py:177-180); never used to filter. `body_part` already carries Left/Right; `_strip_side()` (layer2d/builder.py) collapses it. So the separate Side select was redundant.
- `"Pain with wrist extension"` → keyword bundle `["wrist extension","palm-down"]` (layer2d/builder.py); it is also Andy's own active injury + the §13.1 Layer 2D test scenario.
- Exercise `movement_components` (where the dormant ETL generator writes the old string) is **not consumed by any runtime layer** — left untouched.

---

## 3. File-by-file edits

### Code
- **`athlete.py`** — `KNOWN_MOVEMENT_CONSTRAINTS` 11→10 (removed `"Pain with wrist extension"`). Added `BODY_PART_CONSTRAINTS` mapping (16 side-less canonical parts → relevant constraint subset; `Other`=catch-all). Built via a `_MC = {c: c for c in KNOWN_MOVEMENT_CONSTRAINTS}` self-map so any typo'd value fails loud (KeyError) at import. Updated the `KNOWN_INJURY_SIDES` comment to note side is now derived.
- **`layer2d/builder.py`** — removed the `"Pain with wrist extension"` key from `MOVEMENT_CONSTRAINT_KEYWORDS`; **folded** its `wrist extension` / `palm-down` keywords into the `"Pain above specific joint angle"` bundle so exercise `injury_flags_text` matching is preserved.
- **`layer4/context.py`** — removed `"Pain with wrist extension"` from the `InjuryRecord.movement_constraints` pydantic `Literal`.
- **`routes/injuries.py`** — import `BODY_PART_CONSTRAINTS` (dropped `KNOWN_INJURY_SIDES`); `_save` now **derives `side` from the `body_part` prefix** (`Left `→Left / `Right `→Right / else N/A) instead of reading a form field; both render contexts pass `body_part_constraints` and drop `sides`.
- **`templates/injuries/form.html`** — removed the Side `<select>` + rebalanced the top row to 4× col-md-3; added `id="body_part"`; replaced the internal-jargon help text (`Drives Layer 2D's…`) with athlete-facing copy; added `id="movement-constraints"` + per-cell `data-constraint`; added a CSP-nonced `<script>` that filters the constraint checkboxes to the selected body part (strips Left/Right prefix; **keeps already-checked constraints visible** → no silent data loss).

### Specs
- **`Layer2D_Spec.md`** — §3 `InjuryRecord` example + `side` comment; §5.3.3 `MOVEMENT_CONSTRAINT_KEYWORDS` reproduction (fold); §5.3.6 muscle-group prose; §13.1 Andy-baseline fixture — all reflect the fold.
- **`Athlete_Onboarding_Data_Spec_v5.md`** §B.3 — dated in-place amendment (no version bump, per the Layer2B/2C precedent) documenting the 11→10 fold + the body-part gating.

### Tests
- NEW **`tests/test_injury_form_constraints.py`** (7 tests) — locks the vocab fold (10 entries; wrist gone; fold target present) + `BODY_PART_CONSTRAINTS` invariants (16 parts covered; every value ⊆ vocab; no per-part dupes; `Other`=catch-all). Dependency-light (imports only `athlete`).
- **`tests/test_layer2d.py`** / **`test_layer1_builder.py`** / **`test_layer3a_builder.py`** — fixture + assertion strings flipped to `"Pain above specific joint angle"`.

---

## 4. Code / tests

- `python3 -m pytest tests/test_injury_form_constraints.py tests/test_layer2a.py tests/test_layer2d.py tests/test_layer1_builder.py tests/test_layer3a_builder.py` → **123 passed** (116 existing + 7 new). `test_layer2a.py` is collected first to satisfy the pre-existing layer4↔layer3a import-order shim.
- `py_compile` clean on all touched modules; Jinja parse OK on `injuries/form.html`.
- (pytest + pydantic pip-installed into the sandbox; flask/bcrypt skipped — a `blinker` RECORD conflict blocks them, so route-level tests weren't run. The affected suites don't need flask.)

---

## 5. Manual verification owed

No Neon/runtime in the sandbox, so the form's JS swap + side derivation were **not browser-tested**. On the Vercel preview (`exercise-git-claude-v5-layer2e-hando-b4ae86-andy-horns-projects.vercel.app`) → `/injuries/new`: confirm no Side field; constraints swap on Body Part change; editing an injury keeps already-checked constraints visible; saving derives the right `side`. **Re-log the existing "Pain with wrist extension" injury** (no data migration shipped, per decision) so it picks the folded constraint.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
Still **run the PR #156 `migrate_disciplines_add_primary_movement_v1.sql` on Neon, then deploy** — the parked hard prerequisite (Layer 2A `SELECT`s `dl.primary_movement`).

### 6.2 Remaining form-feedback slices (both unblocked, each needs its own plan-mode design)
- **Slice A — race-event form** (items 1+2+3): distance-or-duration metric + format/`framework_sport` reconciliation; drop the top aid-stations count + derive fueling cadence from route locales (Layer 2E); mandatory-gear → pack-weight/portage rework. Multiple new/changed `race_events` columns + Layer 2A/2C/2E plumbing; likely splits further.
- **Slice C — schedule inference** (item 5): infer long-session day + rest days instead of asking; removes schedule-form inputs, changes Layer 1 derivation.

### 6.3 Operating notes — read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `Project_Backlog_v62.md` 6. `./aidstation-sources/scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| track | Form-feedback batch → slice B (injury form) first | Andy at gate | Unblocked; smallest blast radius; touches Andy's own dogfooded wrist injury. |
| D1 | **Path A** — drop Side, derive from `body_part` prefix (keep sided vocab) | Andy at gate | Honors the literal "Side-field drop"; smallest change; laterality preserved; the 41-canonical body_part cleanup stays a separate future item (`_strip_side` bridges it). |
| D2 | **Fold** `"Pain with wrist extension"` into `"Pain above specific joint angle"` | Andy at gate | That entry already carries `full extension`; the wrist keywords ride on it. Vocab 11→10. |
| D3 | **Bundle** #4 + #6 in one slice | Andy at gate | Both touch the same form; ship together. Over the 5-file ceiling, authorized. |
| D4 | `BODY_PART_CONSTRAINTS` mapping (16×subset) | Andy at gate | Approved as drafted (trigger #5 curation). |
| D5 | **No data migration** for the existing wrist injury | Andy at gate | Andy re-logs manually; avoids a JSONB-rewrite migration for a single test-athlete row. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `"Pain with wrist extension"` gone from `KNOWN_MOVEMENT_CONSTRAINTS` (10 entries) | ✅ `athlete.py` |
| `BODY_PART_CONSTRAINTS` present; 16 parts; all values ⊆ vocab; `Other`=catch-all | ✅ `athlete.py` + `test_injury_form_constraints.py` |
| Wrist key removed from `MOVEMENT_CONSTRAINT_KEYWORDS`; keywords folded into "above joint angle" | ✅ `layer2d/builder.py:151` |
| Pydantic `InjuryRecord` enum no longer lists the wrist constraint | ✅ `layer4/context.py` |
| Side select removed; `side` derived from `body_part` prefix in `_save` | ✅ `routes/injuries.py` + `templates/injuries/form.html` |
| Form-text jargon leak replaced; CSP-nonced constraint-filter JS added | ✅ `templates/injuries/form.html` |
| Specs reflect the fold (Layer2D §3/§5.3.3/§5.3.6/§13.1; onboarding §B.3) | ✅ |
| Tests green | ✅ 123 passed |
| No orphaned `sides=` / `KNOWN_INJURY_SIDES` import / runtime `"Pain with wrist extension"` (only dormant ETL generator) | ✅ `grep` |
| CURRENT_STATE pointer bumped + CARRY_FORWARD #4/#6 marked shipped | ✅ |

---

## 9. Files shipped this session

**Substantive (5):** `athlete.py`, `layer2d/builder.py`, `layer4/context.py`, `routes/injuries.py`, `templates/injuries/form.html`. (Specs `Layer2D_Spec.md` + `Athlete_Onboarding_Data_Spec_v5.md` and the 4 test files round out the PR; ceiling break authorized at gate.)

**Bookkeeping:** `CURRENT_STATE.md` (pointer bump), `CARRY_FORWARD.md` (#4/#6 shipped), this handoff.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md`: the 2026-05-21 punch-list **#4** (injury body_part/Side redundancy) + **#6** (movement-constraints not dynamic per body part) struck through ✅ Shipped 2026-05-25. The 41-canonical side-less `body_part` vocab cleanup (the other half of #4's framing) remains open as a separate low-priority form-UX item — `_strip_side` keeps it functionally harmless. Slice A (race-event form) + slice C (schedule inference) remain as the open form-feedback work, each gated on its own plan-mode design.

**Out-of-scope boundary recorded:** `etl/sources/generate_movement_components_migration.py` + its generated SQL still reference `"Pain with wrist extension"` in exercise `movement_components`, which no runtime layer consumes — dormant; align only if `movement_components` ever gets a consumer.

---

**End of handoff.**
