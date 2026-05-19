# D-73 Phase 2.1 — Layer 2A Discipline Classifier — Closing Handoff

**Session:** D-73 Phase 2.1 per `Upstream_Implementation_Plan_v1.md` §4 Phase 2. First Layer 2 runtime — `q_layer2a_discipline_classifier_payload` per `Layer2A_Spec.md` §3 verbatim. Phase 2 of 5 kicked off (1 of 5 nodes shipped).
**Date:** 2026-05-19
**Predecessor handoff:** `V5_Implementation_D73_Phase_1_3_Closing_Handoff_v1.md`
**Branch:** `claude/d73-phase-2-1` (renamed from harness-pinned `claude/v5-phase-1-3-closing-3G5yx` at session start per H1).
**Status:** 🟢 3 substantive files (well under ceiling). 784 tests green (770 baseline + 14 new Layer 2A tests). D-73 status note extended; Phase 2.1 closed.

---

## 1. Session-start verification (Rule #9)

Anchor-check of `V5_Implementation_D73_Phase_1_3_Closing_Handoff_v1.md` §8 via `./aidstation-sources/scripts/verify-handoff.sh` + targeted greps + 770-test baseline.

| Claim | Anchor | Result |
|---|---|---|
| `aidstation-sources/Layer1_Spec.md` exists | `ls` | ✅ |
| `Layer1_Spec.md` has 14 section H2s | `grep -c "^## "` ≥ 14 | ✅ |
| `layer4/context.py` contains `class Layer1Payload(_Base):` + 11 section sub-models | grep | ✅ |
| `layer1/__init__.py` exports `build_layer1_payload` | grep | ✅ |
| `layer1/builder.py` has 24 `db.execute` call sites | `grep -c "db.execute"` = 24 | ✅ |
| `tests/test_layer1_builder.py` has 19 tests | `grep -c "def test_"` = 19 | ✅ |
| `python -m pytest tests/` → 770 passed | `pip install --break-system-packages pytest` first per runtime-env quirk; then `770 passed in 2.12s` | ✅ |
| `CURRENT_STATE.md` `Last shipped session` points at 1.3 handoff | inspection | ✅ |
| Backlog D-73 status note names Phase 1.3 as shipped | grep | ✅ |
| `verify-handoff.sh` reports all paths ✅ except one false-positive | `tests/test_layer2a.py` flagged ❌ — regex captured the §6.1 forward-pointer (next-session target, not a missed claim) | ✅ (reconciled as expected false-positive) |

**Reconciliation note:** clean wrt predecessor. The runtime-env quirk surfaced again: the cloud container's default `pytest` binary is a `uv tool install pytest` with isolated Python; the working path is `pip install --break-system-packages pytest` (requirements.txt doesn't pin pytest separately) then `python -m pytest`. Already documented in 1.3 §6.3; surfaced again here for next-session continuity.

---

## 2. Session narrative

Andy opened with the predecessor handoff URL and "lets work." After reading CLAUDE → CURRENT_STATE → CARRY_FORWARD → predecessor handoff → `verify-handoff.sh` + 770-test baseline confirmation, the architect-recommended next move was **D-73 Phase 2.1 — Layer 2A discipline classifier** per `Upstream_Implementation_Plan_v1.md` §4 Phase 2.1. Predecessor §6.1 framed Layer 2A as foundation for 2B/C/D/E (all four consume 2A's `included_discipline_ids`); spec is 🟢 complete (443 lines); typed `Layer2APayload` + 9 sub-types already in `layer4/context.py` lines 162-241.

Andy 2026-05-19 picked **Phase 2.1, but /plan first**. Plan-mode equivalent flow (Andy controls the harness toggle, so plan presented as text + AskUserQuestion-style confirmation): 3 substantive files (`layer2a/__init__.py` + `layer2a/builder.py` + `tests/test_layer2a.py`), builder signature **spec-verbatim per §3** (caller-supplied params; Phase 5 orchestrator composes), package layout mirroring `layer1/`, D-17 sub-format strip via `_SUB_FORMAT_SPORTS` whitelist per spec §14 gut-check.

**D-52 sub-decision dissolved during planning.** Predecessor §6.1 framed a soft sub-decision (read `public.*` for v1 or `layer0.*` post-D-52); reconnaissance showed the three Layer 2A catalog tables (`sport_discipline_map`, `phase_load_allocation`, `discipline_training_gaps`) exist only under `layer0.*` — no `public.*` counterparts in `init_db.py` (`grep` returned zero hits); D-52 scope per `Catalog_Migration_Plan_v3.md` §1 is `exercise_inventory` / `equipment_items` / `exercise_equipment` / `training_modalities` only. Builder reads `layer0.*` directly per spec §5.2 SQL verbatim — no migration coupling.

Andy answered three plan decisions:
1. **Rationale templates** — "don't defer" → shipped Andy-quality inline strings this session (Open Item 2A-1 partial-close).
2. **Test count** — "don't care" → landed 14 tests (5 input-validation + 1 AR baseline + 1 AR override + 1 short AR + 3 Triathlon D-17 + 3 edge cases).
3. **Branch rename** — "rename" → `claude/v5-phase-1-3-closing-3G5yx` → `claude/d73-phase-2-1` (H1, matches 1.2A/B/C/1.3 precedent).

Implementation: 3 substantive files shipped — `layer2a/__init__.py` (10 lines, re-exports `q_layer2a_discipline_classifier_payload` + `Layer2AInputError`); `layer2a/builder.py` (~530 lines — constants block, `Layer2AInputError`, 14 helpers including `_strip_sub_format` + `_load_disciplines` + `_resolve_conditional` + `_compute_load_weight` + `_render_rationale` + coaching-flag emitters + `q_layer2a_discipline_classifier_payload` public entry); `tests/test_layer2a.py` (~330 lines, 14 tests).

Tests 770 → 784 (+14). Full suite green. Sole spec-vs-storage drift surfaced: `Layer2A_Spec.md` §5.2 SQL references `pla.default_inclusion` but `etl/layer0/schema.sql` doesn't carry that column on `layer0.phase_load_allocation`. Builder derives `default_inclusion` from `notes_conditions` text per spec §5.3 semantics (`*CONDITIONAL`-prefixed → `prompt_required`; else `included`). Spec doc-sweep nit queued in `CARRY_FORWARD.md`.

---

## 3. File-by-file edits

### 3.1 `layer2a/__init__.py` (new)

10 lines. Module docstring + re-exports `q_layer2a_discipline_classifier_payload` + `Layer2AInputError` from `layer2a.builder`. Mirrors `layer1/__init__.py` package precedent.

### 3.2 `layer2a/builder.py` (new)

~530 lines. Public entry: `q_layer2a_discipline_classifier_payload(db, framework_sport, *, athlete_discipline_overrides=None, estimated_race_duration_hours=None, navigation_required=None, team_format=None, etl_version_set) -> Layer2APayload` per spec §3 verbatim (with `db` added as first positional matching `layer1/builder.py` precedent).

**Constants block:**

- `_SUB_FORMAT_SPORTS: frozenset[str]` — whitelist of 5 sports that use top-level naming in SDM and sub-format naming in PLA per spec §5.1: Triathlon, Skimo, Long Distance / Endurance Cycling, Canoe / Kayak Marathon, Open Water Marathon Swimming.
- `_REQUIRED_ETL_KEYS = frozenset({"0A", "0B", "0C"})` — §4 validation.
- `_AR_DURATION_THRESHOLD_HOURS = 20.0` — D-008b spec §5.3 rule.
- `_WHITEWATER_DISCIPLINE_ID = "D-008b"` + `_NAV_DISCIPLINE_ID = "D-013"`.
- `_DIVERGENCE_RATIO_THRESHOLD = 0.5` — §8.3 flag fires when relative divergence > 50%.
- `_VALID_TEAM_FORMATS = frozenset({"Solo", "Unified", "Relay"})`.
- `_TEMPLATE_VERSION = "v1"`.
- `_SUB_FORMAT_PATTERN = re.compile(r"^(.+?)\s*\(.+\)\s*$")`.

**Helpers (14):**

| Helper | Purpose |
|---|---|
| `_strip_sub_format(framework_sport)` | Returns SDM-side top-level name; whitelisted strip only |
| `_load_disciplines(db, top_level_sport, framework_sport, version_0a)` | Single SQL per spec §5.2; D-05 filter applied |
| `_role_modifier(role)` | Maps SDM role (with `(*Conditional)` suffix preserved) to "core"/"supporting"/"minor"/"technical" |
| `_is_conditional(role, notes_conditions)` | Detects `*Conditional` in role OR `*CONDITIONAL`-prefixed notes |
| `_default_inclusion(notes_conditions)` | Derives `PhaseLoadBands.default_inclusion` from text |
| `_build_phase_load(row)` | Builds `PhaseLoadBands` or returns None |
| `_build_training_gap(row)` | Builds `TrainingGap` or returns None |
| `_resolve_conditional(row, duration, nav, team, overrides)` | Per spec §5.3 — race-rule-driven inclusion |
| `_compute_load_weight(row, overrides)` | Per spec §5.4 — midpoint + override |
| `_render_rationale(row, sport, inclusion, conditional, duration, nav)` | Athlete-quality templated rationale |
| `_append_sport_context(text, row)` | Appends `sport_specific_context` verbatim |
| `_fmt_pct(value)` + `_fmt_hours(value)` | Display formatters |
| `_emit_coaching_flags(disciplines, raw_rows, duration, nav)` | Three spec §8 triggers |
| `_build_training_gaps_summary(disciplines)` | Per spec §7 |

**Public entry** orchestrates: §4 validation → strip → `_load_disciplines` → for-row resolve+weight+rationale → unresolved-sport edge case → HITL gate → flags + summary → `Layer2APayload` assembly with `rationale_metadata.generated_at = datetime.utcnow().isoformat()`.

### 3.3 `tests/test_layer2a.py` (new)

~330 lines. 14 tests across 5 test classes:

- **`TestInputValidation`** (5) — empty `framework_sport` → raise; missing `0A`/`0B`/`0C` → raise; non-dict `etl_version_set` → raise; negative `estimated_race_duration_hours` → raise; invalid `team_format` → raise.
- **`TestARBaseline`** (1) — spec §13.1 — 7-row AR fixture (Primary D-001, Primary D-005, Secondary D-006, Minor D-007, conditional D-008b, conditional D-013, Minor D-016 with DTG). 56h + nav=True. Asserts: 7 disciplines, D-008b auto-in, D-013 auto-in (with `sleep_deprivation_relevant=True`), correct role modifiers in rationale, D-001 phase load surfaced + `default_inclusion="included"`, weight=32.5 midpoint, `sport_specific_context` appended verbatim, no HITL, no unresolved flags, 1 `training_gap` flag + 2 `conditional_auto_resolved` flags + `training_gaps_summary.flagged_count=1`, ETL version echoed, rationale_metadata populated, single query issued with 5 correct params + D-05 filter in SQL.
- **`TestAROverride`** (1) — spec §13.2 — D-006 override 25.0 vs default 15.0. Asserts: `value=25.0`, `source='athlete_override'`, `system_default=15.0`, `weight_override_divergence` flag fires (67% relative > 50%), metadata carries `override_pct`/`default_pct`/`divergence_relative`.
- **`TestShortAR`** (1) — spec §13.3 — 8h + nav=True. Asserts: D-008b `inclusion='excluded'`, `conditional_resolution='race_rule_auto_out'`, `sleep_deprivation_relevant=False`, rationale contains "below" + "20h", `conditional_auto_resolved` flag with auto-out wording + `metadata['value']=8.0`, HITL still False.
- **`TestTriathlonD17`** (3) — spec §13.4 + 2 defensive — `"Triathlon (Standard / Olympic)"` strips to `"Triathlon"` for SDM param + full name for PLA param; AR with no parens doesn't strip; non-whitelisted parens don't strip (false-positive guard).
- **`TestEdgeCases`** (3) — unknown sport → empty disciplines + HITL + error-severity unresolved flag; override targeting non-sport-set discipline silently ignored; both signals None → conditionals `prompt_required` + HITL + rationale prompts athlete to confirm.

All 14 green; full suite 770 → 784. Fixture pattern matches `tests/test_race_events_repo.py` + `tests/test_layer1_builder.py` `_FakeConn`/`_FakeCursor`.

---

## 4. Code / tests

`tests/` count: 770 → 784 (+14). All in the new `tests/test_layer2a.py`. No deletions or modifications to existing test files.

Modified-file import check: `python -c "from layer2a import q_layer2a_discipline_classifier_payload, Layer2AInputError; from layer4.context import Layer2APayload; print('OK')"` succeeds.

`python -m pytest tests/` → **784 passed in 1.85s**.

---

## 5. Manual §5.0 verification steps (Vercel, post-merge)

2 testable steps for the manual walkthrough after this PR deploys to Neon production.

1. **AR baseline call on Andy's PGE 2026 context:** open a Python REPL in the running Vercel environment (or a one-off Flask shell), execute `from layer2a import q_layer2a_discipline_classifier_payload; from database import get_db; payload = q_layer2a_discipline_classifier_payload(get_db(), "Adventure Racing", estimated_race_duration_hours=56.0, navigation_required=True, etl_version_set={"0A": <current 0A pin>, "0B": <pin>, "0C": <pin>}); print(payload.model_dump_json(indent=2)[:2000])`. Confirm: (a) no exception (single SELECT returns without DB error against `layer0.*`); (b) 15 AR disciplines present (D-001 through D-016 per spec §13.1); (c) D-008b auto-in (race_rule_auto_in); (d) D-013 auto-in; (e) rationale strings render with Andy-quality wording (no platitudes; pct band + sport context surfaced).
2. **Triathlon D-17 spot-check (if Triathlon data is loaded):** `q_layer2a_discipline_classifier_payload(get_db(), "Triathlon (Standard / Olympic)", etl_version_set=<pin>)`. Confirm: (a) 4 disciplines returned (swim/bike/run + transitions if PLA carries them); (b) SDM lookup found Triathlon rows (strip logic worked); (c) PLA bands match the sub-format. If Layer 0 doesn't carry Triathlon data yet (Andy's near-term focus is AR), record this scenario as ⏸ blocked-on-data rather than 🔴 bug.

Appended to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" under D-73 Phase 2.1 header (scenario count 55 → 57).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**D-73 Phase 2.2 — Layer 2D injury risk** per `Upstream_Implementation_Plan_v1.md` §4 Phase 2.2. Sequenced before 2B per plan §4 because 2D's typed `ExerciseRisk` + `AccommodationModality` discriminated union already shipped via PR-C-followon 2026-05-17 — **no new design** needed. Consumes Layer 1 §B (conditions_log + injury_log already shipped via D-51 / D-73 Phase 1.2B) + Layer 0 `injury_profiles` + `exercise_risk_assessments`. ~4-5 files (new `layer2d/builder.py` + `tests/test_layer2d.py` + bookkeeping). **Trigger #8 unlikely to fire** — spec is complete; accommodation modality framework locked.

**Soft sub-decision before opening:** Layer 0 storage gap — does `layer0.injury_profiles` + `layer0.exercise_risk_assessments` exist in `etl/layer0/schema.sql`? Phase 2.1 reconnaissance didn't sweep — recommend a 1-grep verification at 2.2 session start; if missing, the gap surfaces as another design-vs-storage drift like Phase 2.1's `pla.default_inclusion`. Architect-pick: read from `layer0.*` if present; surface a doc-sweep nit + derive from `conditions_log` text if not.

### 6.2 Alternative pivots

- **D-73 Phase 2.3 — Layer 2B terrain classifier** (~4-5 files). Reads target event terrain description + Layer 0 terrain taxonomy. Spec complete.
- **D-73 Phase 2.4 — Layer 2C equipment mapper** (~5-7 files, **ceiling break expected** per plan §5.4). **/plan-mode gate** for §5 Decision Points (runtime vs pre-resolved toggle lookup; discipline-to-toggle mapping). Triggers #5 + #8 expected.
- **D-73 Phase 2.5 — Layer 2E nutrition baseline** (~4-5 files). Reads §B + §H + §I + 2A `framework_sport` + `discipline_ids` + Layer 0 fueling-tier bands (read from `Layer2E_Spec.md` §3 constants until a DB table lands).
- **D-73 Phase 1.4 — D-52 catalog migration sequencing** — /plan-mode gate per plan §6 item 2. Less urgent now that Phase 2.1 confirmed Layer 2A catalog reads are unaffected by D-52 (no `public.*` counterparts).
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration (~6-8 files). Orthogonal to D-73 arc.
- **Layer 4 Step 7 env-gated scaffolding** — `ANTHROPIC_API_KEY` plumbing without a real call (~3-4 files). Strategic value: unblocks Phase 5 vertical slice.
- **Manual §5.0 walkthrough of accumulated 57 scenarios** — Andy's call when to batch-walk.
- **`Layer2A_Spec.md` §5.2 SQL doc-sweep** — strip `pla.default_inclusion` from the spec SQL (~5-line edit; queued in `CARRY_FORWARD.md`).

### 6.3 Operating notes for next session

Read order per Rule #13:
1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff
3. `aidstation-sources/CARRY_FORWARD.md` — 57 walkthrough scenarios + 5 doc nits (one new from this session) + orthogonal tracks
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward from 1.3 §6.3):** the cloud container's default `pytest` binary is a `uv tool install pytest` that uses its own isolated Python without project deps. The working test command is `pip install --break-system-packages pytest` (one-time) then `python -m pytest tests/`. Not a code issue; just a runtime quirk.

If picking Phase 2.2: re-read `Layer2D_Spec.md` (already 🟢 complete; 1169 lines; largest of Layer 2) + `layer4/context.py` `Layer2DPayload` + 8 sub-types + 6-variant `AccommodationModality` discriminated union + `Upstream_Implementation_Plan_v1.md` §4 Phase 2.2. Plan ahead for the Layer 0 storage gap soft-decision per §6.1 above.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Branch renamed `claude/v5-phase-1-3-closing-3G5yx` → `claude/d73-phase-2-1` | Andy 2026-05-19 ("rename") | H1 rule. Matches 1.2A/B/C/1.3 precedent across the D-73 arc. |
| 2 | Builder signature spec-verbatim 6 params + `db` first positional | Architect-pick during plan-first gate | Keeps query node pure per spec §2 boundary ("does not resolve sport name aliases"). Caller (Phase 5 orchestrator) sources params from Layer 1 §C overrides + `race_events` row + ETL plan-gen pin. Avoids coupling layer2a to Layer 1 + race_events schemas. |
| 3 | D-52 sub-decision dissolved | Architect-pick during plan-first reconnaissance | Three Layer 2A catalog tables exist only under `layer0.*` (no `public.*` counterparts in `init_db.py`); spec §5.2 SQL targets `layer0.*` directly. D-52 scope (`exercise_inventory` / `equipment_items` / `exercise_equipment` / `training_modalities`) doesn't include any Layer 2A tables. |
| 4 | Module layout package mirror of `layer1/` | Architect-pick | `layer1/__init__.py` + `layer1/builder.py` is the freshest precedent. Plan §4 text said "layer2a.py" (flat) but the package layout is cleaner for future Phase 2.x sub-modules. |
| 5 | Rationale templates shipped Andy-quality v1 inline | Andy 2026-05-19 ("don't defer") | Open Item 2A-1 (athlete-facing rationale content review) partial-close. Direct, evidence-grounded voice per CLAUDE.md; no platitudes; 4 role modifiers (core/supporting/minor/technical) × 3 inclusion states + conditional-resolution appendices + `sport_specific_context` verbatim append. Full content review naturally falls out of Phase 5.1 when race_week_brief surfaces them in production. |
| 6 | D-17 sub-format strip via whitelist (not blanket regex) | Architect-pick per spec §14 gut-check | `_SUB_FORMAT_SPORTS = {Triathlon, Skimo, LDC, OWMS, Canoe/Kayak Marathon}` — only sports known to use sub-format naming get stripped. Avoids false-positive strips on hypothetical sports that contain parens for unrelated reasons. AR (no parens) bypasses entirely. |
| 7 | `PhaseLoadBands.default_inclusion` derived from `notes_conditions` text | Architect-pick (spec-vs-storage drift mitigation) | `Layer2A_Spec.md` §5.2 SQL references `pla.default_inclusion` but `etl/layer0/schema.sql` doesn't carry that column. Builder reads `notes_conditions` text and applies the spec §5.3 semantics (`*CONDITIONAL`-prefixed → `prompt_required`; else `included`). Spec doc-sweep nit queued in `CARRY_FORWARD.md` for the next session that touches `Layer2A_Spec.md`. |
| 8 | Conditional rule encoding code-side | Per spec §5.3 | "Rules are tightly coupled to race-specific business logic and easier to maintain in versioned code than in a normalized table." Future `discipline_conditional_rules` table candidate if rule count grows past ~10 unique cases. |
| 9 | `team_format` plumbed but relay-leg filtering deferred | Architect-pick (v1 scope) | No current consumer sport — AR + Triathlon + Andy's near-term work are all non-relay. Spec §5.3 ("Relay-only legs — depend on `team_format`. Not applicable to AR") supports the deferral. Future Triathlon-team session lands the logic. |
| 10 | Sleep-deprivation relevance v1 surface narrow | Architect-pick | D-013 (nav) always; D-008b only when included via long-duration race rule. Spec §8 doesn't enumerate a closed list; downstream layers can extend the flag-emission surface. |
| 11 | Override-divergence threshold = 50% relative | Per spec §8.3 example | Spec example: 25 override vs 15 default → 67% relative divergence → flag fires. `abs(ov - default) / default > 0.5` matches; absolute-percentage-point reading would have given 10 (not 50% of anything) so relative is correct. Metadata carries both `divergence` (absolute) + `divergence_relative` for transparency. |
| 12 | 14 tests landed (over 8-test plan estimate) | Plan said "8 tests; Andy don't care" | Input validation grew to 5 sub-cases; Triathlon D-17 grew to 3 (canonical + 2 defensive false-positive guards). Test density right-sized to behavioral surface. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `layer2a/__init__.py` exists and exports `q_layer2a_discipline_classifier_payload` + `Layer2AInputError` | ✅ grep |
| `layer2a/builder.py` exists with `def q_layer2a_discipline_classifier_payload(db, framework_sport` | ✅ grep |
| `layer2a/builder.py` SQL references `layer0.sport_discipline_map` + `layer0.phase_load_allocation` + `layer0.discipline_training_gaps` | ✅ grep |
| `layer2a/builder.py` carries D-05 standing filter `NOT LIKE '%WEEKLY TOTAL%'` | ✅ grep |
| `layer2a/builder.py` `_SUB_FORMAT_SPORTS` whitelist has 5 entries (Triathlon, Skimo, LDC, OWMS, Canoe/Kayak Marathon) | ✅ inspection |
| `layer2a/builder.py` `_AR_DURATION_THRESHOLD_HOURS = 20.0` + `_WHITEWATER_DISCIPLINE_ID = "D-008b"` + `_NAV_DISCIPLINE_ID = "D-013"` | ✅ grep |
| `tests/test_layer2a.py` exists with 14 tests | ✅ `grep -c "def test_" tests/test_layer2a.py` = 14 |
| `python -m pytest tests/test_layer2a.py` → 14 passed | ✅ `14 passed in 0.40s` |
| `python -m pytest tests/` → 784 passed | ✅ `784 passed in 1.85s` |
| Branch is `claude/d73-phase-2-1` (renamed per H1) | ✅ `git branch --show-current` |
| `CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `CURRENT_STATE.md` Layer status row 2 flipped to "🟡 2A runtime shipped 2026-05-19" | ✅ inspection |
| `CURRENT_STATE.md` Tests note bumped 770 → 784 | ✅ inspection |
| Backlog `D-73` status note extended to name Phase 2.1 as shipped | ✅ grep |
| Backlog `## Changelog` H2 has a new 2026-05-19 Phase 2.1 entry above the 1.3 entry | ✅ grep |
| `CARRY_FORWARD.md` Manual §5.0 walkthrough count rose 55 → 57 (+2 Phase 2.1 scenarios) | ✅ inspection |
| `CARRY_FORWARD.md` doc-sweep nits gains the `Layer2A_Spec.md` §5.2 `pla.default_inclusion` drift entry + Open Item 2A-1 partial-close note | ✅ inspection |
| `Layer2APayload` constructable via builder against an empty `_FakeConn` (smoke) | ✅ test_unknown_sport_yields_hitl_and_unresolved_flag exercises the path |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (3 files; well under 5-file ceiling):**

1. New `layer2a/__init__.py` — module init exporting `q_layer2a_discipline_classifier_payload` + `Layer2AInputError`.
2. New `layer2a/builder.py` — runtime builder per `Layer2A_Spec.md` §3-§8.
3. New `tests/test_layer2a.py` — 14 tests across input validation / AR baseline / override / short AR / Triathlon D-17 / edge cases.

**Bookkeeping (4 files; outside ceiling per B3):**

4. Modified `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer 2 status note flipped to "🟡 2A runtime shipped 2026-05-19"; Tests note bumped to 784; D-73 arc note extended.
5. Modified `aidstation-sources/Project_Backlog_v62.md` — in-place: D-73 status note extended to name Phase 2.1 as shipped; new 2026-05-19 Phase 2.1 entry added to `## Changelog` (above the 1.3 entry, per most-recent-first rule).
6. Modified `aidstation-sources/CARRY_FORWARD.md` — Manual §5.0 walkthrough section gains a "2 D-73 Phase 2.1" sub-bullet (scenario count 55 → 57); doc-sweep nits gains the `Layer2A_Spec.md` §5.2 `pla.default_inclusion` drift entry + Open Item 2A-1 partial-close note.
7. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_2_1_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` gains 2 new §5.0 walkthrough scenarios under a "D-73 Phase 2.1" sub-bullet in the "Manual §5.0 walkthrough" section. Scenario count rises 55 → 57 (12 onboarding + 6 nudge UI + 6 Layer 3B Scope A + 6 Layer 3B Scope B + 5 Layer 3B Scope C + 1 D-72 + 7 D-73 Phase 1.2A + 6 D-73 Phase 1.2B + 4 D-73 Phase 1.2C + 2 D-73 Phase 1.3 + 2 D-73 Phase 2.1).

`CARRY_FORWARD.md` doc-sweep nits section gains 2 entries:
- `Layer2A_Spec.md` §5.2 SQL — `pla.default_inclusion` references non-existent column; builder derives from `notes_conditions` text. Fold into next session that touches the spec (~5-line edit).
- `Layer2A_Spec.md` Open Item 2A-1 — rationale template content review partial-close. v1 templates shipped Andy-quality; full review naturally folds into Phase 5.1 orchestrator vertical slice.

No new orthogonal carry-forwards this session.

Layer 4 Step 4f + Step 7 + Step 8 still queued per the existing list.

---

**End of handoff.**
