# V5 Implementation — #254 / D-17 Sport Sub-Format Capture — Slice B2 (capture UI + override) — Closing Handoff

**Date:** 2026-06-29
**Branch:** `claude/slice-254-b2-v7wsdo` — **committed + pushed; PR not yet opened** (per the settled no-auto-PR rule — awaiting Andy's go).
**Next session continues:** **#254 housekeeping only** — B2 closes the issue's functional scope; the redump-fold of `0033` to the Layer-0 baseline (§5) is the lone non-blocking carry. See §6.
**Issue:** [#254](https://github.com/ahorn885/exercise/issues/254) — Onboarding: map a race goal to the correct sport sub-format (D-17 Sheet 3 / Sheet 5 naming mismatch). Parent #246.
**Design:** `aidstation-sources/designs/Onboarding_SportSubFormat_D17_254_Design_v1.md` (ratified; §6 UX flow, §7.4 spec, §8 slice B).
**Predecessor handoff:** `handoffs/V5_Implementation_SportSubFormat_D17_254_SliceB1_HeadlessCompose_2026_06_29_Closing_Handoff_v1.md` (slice B1 — headless backend compose).

## 0. Thread continuity — #254 → FUNCTIONALLY COMPLETE

Slice B1 shipped the serving-side compose (the live no-volume bug closed via the Layer-0 default, no UI). **This session shipped slice B2 — the capture UI + override**: the second `<select>` that lets an athlete pick Sprint vs. Ironman (and the four other parents' variants), threaded end-to-end through both race-event surfaces. With B2, #254's functional scope is done: the five sub-format parents resolve to real PLA bands by default (B1) **and** the athlete can override the default in the form (B2).

## 1. What B2 adds

The five sub-format parents (Triathlon, Skimo, Long Distance / Endurance Cycling, Canoe / Kayak Marathon, Open Water Marathon Swimming) are top-level-named in `sport_discipline_bridge` but sub-format-named in `phase_load_allocation`. B1 made a bare parent resolve to the Layer-0 `is_default` sub-format at compose time. **B2 surfaces that choice in the UI**: when the chosen "Race event type" is one of the five parents, a **"Race sub-format"** select appears (pre-set to `is_default`), and the athlete's pick is stored in `race_events.sport_sub_format` (two-column model, D1′). On a non-parent sport the select stays hidden and the column stays NULL. Empty pick → NULL → B1's compose still applies the default.

## 2. Files shipped (5 substantive code + 1 spec + 3 test)

### 2.1 `sport_sub_format_repo.py` (modified) — two form readers
- `sub_format_options(db, parent_sport) -> list[dict]` — `[{sub_format_sport, display_label, is_default}, ...]` for one parent in seed (`id`) order; `[]` on a falsy/single-format parent (short-circuits on falsy). Backs the server-rendered select.
- `parent_options_map(db) -> dict[str, list[dict]]` — the full `parent -> options` map (`ORDER BY parent_sport, id`), grouped preserving order. Backs the client-side JSON blob.
- `_option_dict(row)` — shared row-shaping helper (`is_default` coerced to bool).
- All read the current canonical mapping (`superseded_at IS NULL`), same as `default_sub_format`.

### 2.2 `routes/race_events.py` (modified) — helper + threading + invalidation
- New `_sub_format_context(db, race)` (next to `_framework_sport_choices`) → `{sub_format_options, sub_format_options_map}`, keyed on `race.framework_sport` (the value the event-type select shows selected; `[]`/hidden for a single-format sport). Imported by `onboarding.py`.
- Both render helpers spread `**_sub_format_context(db, race)`.
- `_race_form_echo`: `'sport_sub_format': _parse_str(form, 'sport_sub_format')` (a failed save keeps the pick, #947).
- `new_race` create + `update_race` update pass `sport_sub_format=`.
- **D6 invalidation:** `sport_sub_format_changed = prior_sport_sub_format != new_sport_sub_format`; the eviction branch is now `if framework_sport_changed or sport_sub_format_changed:` → `evict_on_target_event_framework_sport_change` (same Layer-2A cache axis). `prior_framework_sport != new_framework_sport` still gates the terrain re-scope alone (a sub-format change does not re-scope terrain).

### 2.3 `routes/onboarding.py` (modified) — same threading on the target-race form
- `_get_target_race_row` SELECT adds `sport_sub_format` (edit-form repopulation).
- `_render_target_race_form` imports + spreads `_sub_format_context(db, target)`.
- `target_race_save`: parse `new_sport_sub_format`; pass to create + update; `prior_sport_sub_format` + the same `framework_sport_changed or sport_sub_format_changed` eviction branch.

### 2.4–2.5 `templates/onboarding/target_race.html` + `templates/profile/race_event_edit.html` (modified)
- A **"Race sub-format"** `<select id="sport_sub_format" name="sport_sub_format">` in a `#sport-sub-format-field` wrapper, server-rendered for the current parent, the stored `sport_sub_format` (else `is_default`) pre-selected. **Hidden via Bootstrap `d-none`** (not inline `style=` — the render tests enforce CSP-clean).
- A `<script type="application/json" id="sport-sub-format-options">` JSON blob (`sub_format_options_map|tojson`) + a nonced IIFE that, on a `framework_sport` `change`, repopulates the select from the blob (default pre-selected) and toggles `d-none`; hides + clears on a parent with no sub-formats. Mirrors the `_race_terrain_editor.html` discipline-rebind pattern. A prior pick is intentionally **not** carried across a parent change (sub-formats don't overlap between parents → re-default).

### 2.6 `aidstation-sources/specs/Athlete_Onboarding_Data_Spec_v6.md` (modified) — §H.2 row
In-place amendment block + a "Sport Sub-Format" field row (per the goal-context-amendment precedent — §H.2 additions edit v6 in place, not a version bump). Per design §7.4: closed enum per parent, default = `is_default`, shown only for the five parents, stored in `race_events.sport_sub_format`, composed for the Layer 2A joins; **explicitly distinguished from the `race_format` periodization enum.**

### 2.7 Tests
- `tests/test_sport_sub_format_repo.py` — `sub_format_options` (shaped dicts in `id` order; SQL shape + params; `[]` on single-format; short-circuit on falsy) + `parent_options_map` (grouped, order-preserving; SQL shape; `{}` on empty).
- `tests/test_routes_race_events.py` — `TestSubFormatContext` (parent drives server options; None/blank parent → `[]` options but full blob), `TestRaceFormEchoSubFormat` (echo carries / NULLs the pick), `TestUpdateRaceSubFormatInvalidation` (a sub-format-**only** change on the target fires `evict_on_target_event_framework_sport_change` and nothing else).
- `tests/test_onboarding_race_events.py` — `_get_target_race_row` now asserts `sport_sub_format` in the SELECT + surfaced on the row.

## 3. Validation

- Full suite (`--ignore=etl/_frozen_xlsx_authoring`): **3947 passed / 30 skipped**, only the 3 pre-existing #217 `evidence_basis` warnings.
- `ruff check` on all new/changed code: clean. (1 residual F841→ actually 1 pre-existing F401 `import pytest` in `tests/test_routes_race_events.py` — present at HEAD, not in my diff; left alone per surgical-changes.)
- No DB apply owed — `sport_sub_format` is a public-schema column (B1, auto-applied on deploy); `0033` already on prod Neon.

## 4. Decisions pinned this slice

- **Sub-format UI keyed strictly on the `framework_sport` select value** (not the profile-fallback resolved sport). Server render + client JS use the same key, so they never disagree. An athlete leaving "Same as my profile sport" doesn't see the picker; B1's compose still applies the default for their profile sport. Override is available the moment they explicitly pick a parent.
- **Came in at 6 substantive files** (2 templates + 2 routes + repo + spec) — one over the soft ceiling, but the templates are a mirror pair and the routes are a mirror pair (≈3 logical changes), and B2 was pre-scoped as exactly this set when Andy approved the B1/B2 split. No further split warranted.
- **`d-none` over inline `style`** — the redesign render tests assert `'style="' not in html`; class-toggle is the established CSP-clean pattern (`templates/plans/view.html`).
- **No flagged-out-of-set option for the sub-format select** (unlike the framework_sport "unrecognized" branch) — `sport_sub_format` values only ever come from the curated map, and the orchestrator falls back to the default if a stored value fails to join PLA. Adding the branch would be speculative.

## 5. Owed / not owed

- **No layer0-apply owed**, **no public migration owed.**
- **Redump-fold of `0033`** (fold the applied map into the `layer0` baseline via `layer0-redump` + archive) is still owed at the Layer-0-baseline level only — does **not** block anything; prod Neon already has the table. Flag for a Layer-0 housekeeping pass (carried since B1).

## 6. Next session

#254 is functionally complete. Remaining is housekeeping, in 4-tier order:
1. **Reconcile + close #254** once the B2 PR merges (comment the PR/commit ref; close `completed`). #246 epic stays open if other D-rows remain.
2. **Redump-fold of `0033`** (§5) — Layer-0 baseline housekeeping; non-blocking.
3. Otherwise pick up the next live-blocker / open-function tier from `CURRENT_STATE.md` "Next moves".

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md`. 3. `CARRY_FORWARD.md` (#254 rolling item). 4. This handoff + design §6/§7.4. 5. `./scripts/verify-handoff.sh`.

## 7. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Form readers | `sport_sub_format_repo.py` | grep `def sub_format_options`, `def parent_options_map`; both query `layer0.sport_sub_format_map`, `superseded_at IS NULL` |
| Render context helper | `routes/race_events.py` | grep `def _sub_format_context`; spread `**_sub_format_context(db, race)` in both render helpers; imported + spread in `routes/onboarding.py:_render_target_race_form` |
| Repo threading (routes) | `routes/race_events.py`, `routes/onboarding.py` | grep `sport_sub_format` in create + update calls + `_race_form_echo` + `_get_target_race_row` SELECT |
| D6 invalidation | `routes/race_events.py`, `routes/onboarding.py` | grep `sport_sub_format_changed`; branch `if framework_sport_changed or sport_sub_format_changed:` → `evict_on_target_event_framework_sport_change` |
| Sub-format select | `templates/onboarding/target_race.html`, `templates/profile/race_event_edit.html` | grep `name="sport_sub_format"`; `id="sport-sub-format-options"` JSON blob; `d-none` toggle (no inline `style=`) |
| Spec row | `specs/Athlete_Onboarding_Data_Spec_v6.md` | grep `Sport Sub-Format amendment`; §H.2 field row distinguishing from `race_format` |
| Tests green | (local venv) | full suite 3947 passed / 30 skipped (3 #217 warnings only) |
| #254 functional scope | — | DONE (B1 default + B2 override). Redump-fold owed at baseline level only (non-blocking). |

## 8. Carry-forward update

`CARRY_FORWARD.md` #254: slice B2 (capture UI + override) **done** on `claude/slice-254-b2-v7wsdo` (committed + pushed; PR awaiting Andy's go). #254 is **functionally complete** (B1 default + B2 override). Only the non-blocking `0033` redump-fold remains at the Layer-0-baseline level. Close #254 on the B2 PR merge.
