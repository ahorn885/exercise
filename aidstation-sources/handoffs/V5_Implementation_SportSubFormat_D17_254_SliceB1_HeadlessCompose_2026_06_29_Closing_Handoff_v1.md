# V5 Implementation — #254 / D-17 Sport Sub-Format Capture — Slice B1 (headless backend compose) — Closing Handoff

**Date:** 2026-06-29
**Branch:** `claude/issue-254-slice-b-46tprr`
**Issue:** [#254](https://github.com/ahorn885/exercise/issues/254) — Onboarding: map a race goal to the correct sport sub-format (D-17 Sheet 3 / Sheet 5 naming mismatch). Parent #246.
**Design:** `aidstation-sources/designs/Onboarding_SportSubFormat_D17_254_Design_v1.md` (ratified; §8 slice B).
**Predecessor handoff:** `handoffs/V5_Implementation_SportSubFormat_D17_254_Slice2_Guard_SliceA_Layer0Map_2026_06_29_Closing_Handoff_v1.md` (slice 2 guard + slice A Layer-0 map).

## 0. Thread continuity — #254 → SLICE B2 NEXT

Slice A's Layer-0 map (`0033`) **is applied to prod Neon** (Andy, 2026-06-29). This session shipped **slice B1 — the headless backend compose** (the serving-side bug fix, no UI). **Slice B2 (capture UI + override) is the next session's work** (§6). Andy chose the **B1-first cut** (AskUserQuestion 2026-06-29): B1 closes the live bug via the Layer-0 default; B2 adds the athlete override.

## 1. What B1 fixes (and what it doesn't)

The five sub-format parents (Triathlon, Skimo, Long Distance / Endurance Cycling, Canoe / Kayak Marathon, Open Water Marathon Swimming) are top-level-named in `sport_discipline_bridge`/SDM but sub-format-named in `phase_load_allocation` (PLA). A bare parent reaching Layer 2A joins **zero** PLA bands → silent no-volume plan (slice 2 turned that silent failure into a loud HITL).

**B1 makes the no-action path resolve.** The Layer-4 orchestrator now composes the Layer 2A sport input as **`sport_sub_format or <parent default> or framework_sport`** (D1′ two-column model). With zero UI, every one of the five parents resolves to its Layer-0 curated `is_default` sub-format (a real PLA `sport_name`) → real phase-load bands, and the slice-2 guard stops firing on the normal path. **B1 does NOT add the athlete override** (the second select that lets an athlete pick Sprint vs. Ironman) — that's B2.

## 2. Files shipped (5 substantive code + 3 test — at ceiling)

### 2.1 `init_db.py` (modified) — column + D5 backfill
Appended at the `_PG_MIGRATIONS` tail:
- `ALTER TABLE race_events ADD COLUMN IF NOT EXISTS sport_sub_format TEXT NULL` (public schema → auto-applies on every Vercel deploy).
- D5 backfill — a guarded `DO $$ … IF to_regclass('layer0.sport_sub_format_map') IS NOT NULL … UPDATE race_events re SET sport_sub_format = m.sub_format_sport FROM layer0.sport_sub_format_map m WHERE re.sport_sub_format IS NULL AND m.parent_sport = re.framework_sport AND m.is_default = TRUE AND m.superseded_at IS NULL`. Guard makes it a clean no-op on a DB without the Layer-0 table; the `IS NULL` predicate is idempotent and never overwrites a stored pick (athlete intent wins).

### 2.2 `sport_sub_format_repo.py` (new) — Layer-0 reader
`default_sub_format(db, parent_sport) -> str | None` — the `is_default` / `superseded_at IS NULL` lookup against `layer0.sport_sub_format_map`. Short-circuits on a falsy parent; returns None when the parent has no rows (single-format sport).

### 2.3 `layer4/orchestrator.py` (modified) — the compose
In `_upstream_full_cone`, immediately before the `q_layer2a_discipline_classifier_payload` call (~line 1100): compute `framework_sport_for_2a`. The athlete's `sport_sub_format` wins; else, **only when `framework_sport in _SUB_FORMAT_SPORTS`** (imported from `layer2a.builder` — the authoritative 5-parent set, not a second hardcoded list), `default_sub_format(db, framework_sport) or framework_sport`; else the bare name. Passed **only** to the `q_layer2a` call — lines ~1301/1322/1348 (2D/2C/3A/3B/2E) keep the plain top-level `framework_sport` (D1′). Rule-#15 `print` logs the inputs + the chosen 2A sport. The `_SUB_FORMAT_SPORTS` gate is also what keeps the new DB read from firing in the queue-fake cone tests (non-parent sports → no read → no queue misalignment).

### 2.4 `race_events_repo.py` (modified) — threading
`sport_sub_format` added to `create_race_event` (new kw, default None; column + placeholder + value), `update_race_event` (kw + `SET sport_sub_format = ?`), `get_race_event` SELECT, and `load_race_event_payload` (SELECT `re.sport_sub_format` + pass to `RaceEventPayload`). New keyword defaults None → all existing route call sites untouched (that's B2's wiring).

### 2.5 `layer4/context.py` (modified) — payload field
`RaceEventPayload.sport_sub_format: str | None = Field(default=None, max_length=120)`, placed next to `framework_sport`.

### 2.6 Tests
- `tests/test_sport_sub_format_repo.py` (new) — `default_sub_format`: returns the row value (SQL shape + params asserted), None on miss, short-circuits on falsy parent.
- `tests/test_layer4_orchestrator.py` — `TestSportSubFormatCompose` (parent→Layer-0 default; athlete pick wins + skips the read; no-default→bare name; non-parent inert). `_queue_target_race_event` + the fake main row gained a `sport_sub_format` field/param.
- `tests/test_race_events_repo.py` — `TestSportSubFormatColumn` (load populates / defaults None; get surfaces; create + update pass the kwarg). `_race_row` gained the `sport_sub_format` key.

## 3. Validation

- Full suite (`--ignore=etl/_frozen_xlsx_authoring`, a pre-existing collection-error dir): **3897 passed / 30 skipped**, only the 3 pre-existing #217 `evidence_basis` warnings.
- `ruff check` on all new/changed code: clean. (4 residual ruff findings in the touched files — 1 E402 in `init_db.py`, 3 F841 `mocks` in `test_layer4_orchestrator.py` — are **pre-existing**, identical counts at HEAD; left alone per surgical-changes.)
- Migration `0033` (slice A) already applied to prod; the new public column + backfill apply on the merge's Vercel deploy.

## 4. Decisions pinned this slice

- **B1-first cut** (Andy, AskUserQuestion 2026-06-29) — slice B split into B1 (headless backend, this slice) + B2 (capture UI), because the full slice B is ~9 substantive files (2× ceiling). B1 alone closes the live bug.
- **Compose gated on `_SUB_FORMAT_SPORTS`** — the default DB read fires only for the five parents (non-parents have no map rows anyway), which also keeps the ordered-queue cone tests green without touching every test.
- **Default lookup applies regardless of sport source** — if `framework_sport` comes from the profile `primary_sport` (no race) and is a parent, the default still resolves (strictly better; the `sport_sub_format` override only exists on race events).

## 5. Owed / not owed

- **No layer0-apply owed** — `sport_sub_format` is public schema (auto-applies on deploy); `0033` already applied.
- **Redump-fold of `0033`** (§6.1 step 2 of the predecessor handoff: `layer0-redump` v1.10.1 + archive) is still owed at the Layer-0-baseline level but does **not** block B1 or B2 — prod Neon already has the table. Flag for a Layer-0 housekeeping pass.

## 6. Next session — BUILD SLICE B2 (capture UI + override)

Per design §8 / §6 of the predecessor handoff (the UI half):
1. **Templates** — `templates/onboarding/target_race.html` + `templates/profile/race_event_edit.html`: a second "Sub-format" `<select>`, populated client-side from a `parent → [{sub_format_sport, display_label, is_default}]` JSON blob, shown only when the chosen parent has rows; `is_default` pre-selected; coaching-voice helper text. On profile edit, repopulate directly from the two stored columns (no name-parsing — that's the whole point of D1′).
2. **Reader** — extend `sport_sub_format_repo.py` with `sub_format_options(db, parent)` + a `parent_options_map(db)` for the JSON blob.
3. **Routes** — `routes/onboarding.py` (~1126 update / ~1204 create) + `routes/race_events.py` (~918 create / ~1075 update): parse the new field, pass `sport_sub_format=` to the repo; add an options helper alongside `_framework_sport_choices`; clear/re-default on parent change.
4. **Invalidation (D6)** — fire `evict_on_target_event_framework_sport_change` when `sport_sub_format` changes on its own (it shifts the composed 2A input — same cache axis). See `tests/test_race_events_invalidation.py` for the existing pattern.
5. **Spec** — `Athlete_Onboarding_Data_Spec_v6.md` §H.2: add the Sport Sub-Format row (design §7.4); explicitly distinguish from the `race_format` periodization enum.
6. Tests: helper-level (options helper + route submit + invalidation), per the route-test convention.

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md`. 3. `CARRY_FORWARD.md` (#254 rolling item). 4. This handoff + design §8. 5. `./scripts/verify-handoff.sh`.

## 7. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Compose at 2A boundary | `layer4/orchestrator.py` | grep `framework_sport_for_2a` — only used at the `q_layer2a` call; 2D/2C/3A/3B/2E keep `framework_sport=framework_sport` |
| `_SUB_FORMAT_SPORTS` gate | `layer4/orchestrator.py` | grep `from layer2a.builder import` includes `_SUB_FORMAT_SPORTS`; `elif framework_sport in _SUB_FORMAT_SPORTS` |
| Layer-0 reader | `sport_sub_format_repo.py` | `def default_sub_format`; queries `layer0.sport_sub_format_map`, `is_default = TRUE`, `superseded_at IS NULL` |
| Column + backfill | `init_db.py` | grep `ADD COLUMN IF NOT EXISTS sport_sub_format`; guarded `to_regclass('layer0.sport_sub_format_map')` DO block |
| Repo threading | `race_events_repo.py` | grep `sport_sub_format` in create/update/get/load (5 hits across the 4 helpers) |
| Payload field | `layer4/context.py` | grep `sport_sub_format: str \| None` on `RaceEventPayload` |
| Tests green | (local venv) | full suite 3897 passed / 30 skipped (3 #217 warnings only) |
| Layer-0 apply | — | not owed (public column); `0033` already applied; redump-fold owed at baseline level only (non-blocking) |
| Slice B2 OWED | — | capture UI + override not started (§6) |

## 8. Carry-forward update

`CARRY_FORWARD.md` #254: slice B1 (headless backend compose) **done** on `claude/issue-254-slice-b-46tprr`; the live no-volume bug is closed via the Layer-0 default. **NEXT: slice B2 (capture UI + override).** #254 stays open until B2 ships.
