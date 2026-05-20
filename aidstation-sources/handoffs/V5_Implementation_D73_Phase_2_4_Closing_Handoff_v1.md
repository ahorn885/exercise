# D-73 Phase 2.4 — Layer 2C Equipment Mapper Builder — Closing Handoff

**Session:** D-73 Phase 2.4 per `Upstream_Implementation_Plan_v1.md` §4 row 2.4 + the Phase 2.4-Prep substrate (PR #102, 2026-05-19). Builder session ships `q_layer2c_equipment_mapper_payload` against the Decision Points pre-resolved in Prep (DP1 = (A) Runtime; DP2 = (b) Structured column).
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_2_4_Prep_Closing_Handoff_v1.md`
**Branch:** `claude/phase-2-4-implementation-RHRDh` (harness-pinned; scope-aligned for the first time across the Phase 2 chain — no H1 rename needed).
**Status:** 🟢 5 substantive files (3 new layer2c code + 2 spec touchpoint edits) at the 5-file ceiling. 901 tests green (866 baseline + 35 new Layer 2C builder tests). D-73 status note extended; Phase 2.4 closed. **Phase 2 of 5 now COMPLETE — all 5 Layer 2 runtimes shipped.**

---

## 1. Session-start verification (Rule #9)

Anchor-check of `V5_Implementation_D73_Phase_2_4_Prep_Closing_Handoff_v1.md` §8 via `./aidstation-sources/scripts/verify-handoff.sh` + 866-test baseline.

| Claim | Anchor | Result |
|---|---|---|
| `etl/layer0/schema.sql` declares the 4 new columns on `layer0.exercises` + `layer0.sport_specific_gear_toggles` | grep | ✅ |
| `aidstation-sources/migrations/migrate_toggles_v3_columns.sql` exists with 3 known-case populations + DO-block verification | grep | ✅ |
| `etl/layer0/extractors/vocabulary.py` defines `_TOGGLE_ALSO_SATISFIES` + `_TOGGLE_GATED_DISCIPLINES` + emits the 2 new fields per row | grep | ✅ |
| `etl/layer0/extractors/exercise_db.py` defines `load_parsed_substitutes_structured` + `extract_exercises` attaches the field per row | grep | ✅ |
| `etl/layer0/run.py` both INSERTs include the 4 new columns | grep | ✅ |
| `tests/test_layer2c_prep.py` has 16 tests | `grep -c "def test_"` = 16 | ✅ |
| `python -m pytest tests/` → 866 passed | 866 passed in 2.16s after env bootstrap | ✅ |
| `CURRENT_STATE.md` `Last shipped session` points at Phase 2.4-Prep handoff | inspection | ✅ |
| Backlog D-73 status note names Phase 2.4-Prep as shipped + Phase 2.4 builder queued | grep | ✅ |
| `verify-handoff.sh` reports all paths ✅ + working-tree clean | full report green | ✅ |
| Branch `claude/phase-2-4-implementation-RHRDh` is scope-aligned (matches "Phase 2.4 implementation") | `git branch --show-current` | ✅ no H1 rename needed |

**Reconciliation note:** clean wrt predecessor. The runtime-env quirk repeated — cloud container's default `pytest` is `uv tool install` isolated Python; documented working path `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` then `python -m pytest tests/` per Phase 2.2 §1 / Phase 2.3 §1 / Phase 2.4-Prep §1.

---

## 2. Session narrative

Andy opened with the Phase 2.4-Prep closing-handoff URL + "lets work." After reading CLAUDE → CURRENT_STATE → CARRY_FORWARD → predecessor handoff → `verify-handoff.sh` + 866-test baseline confirmation, architect-recommended next move was **D-73 Phase 2.4 — Layer 2C equipment mapper builder** per the predecessor §6.1 forward-pointer.

**No /plan-mode gate at session start** — the Decision Points were already resolved in Phase 2.4-Prep (DP1 = (A) Runtime lookup; DP2 = (b) Structured column). Andy confirmed the 3-substantive-file scope on a single AskUserQuestion gate ("Yes — build Layer 2C as scoped" vs "Different scope — let me describe").

**Drift check during recon found one spec-vs-data inconsistency that needed resolving in code:**

The Layer2C_Spec.md §5.1 effective-pool pseudo-code adds `toggle_def.also_satisfies` items directly to the equipment pool. But the deployed data shape (per `migrate_toggles_v3_columns.sql` + `Vocabulary_Audit_v2.md §4.2`) treats `also_satisfies` as a list of TOGGLE NAMES, not canonical equipment names. §6 prose is the canonical reading — when toggle X has `also_satisfies = [Y]`, then turning X on adds toggle Y's `paired_equipment_categories` to the pool (one hop, no cascade). The §5.1 pseudo-code is misleading; the builder implements §6 semantics. Documented inline + folded a §5.1 reconciliation note into `Layer2C_Spec.md` as a spec touchpoint edit.

**Implementation landed clean. 35 new tests green. Full suite 866 → 901.**

The two spec touchpoint edits queued in CARRY_FORWARD (`Layer2C_Spec.md` §5.1 + §8.3 DP annotations + §10 edge case + §12 Open Items; `Upstream_Implementation_Plan_v1.md` §4 row 2.4 + §5.4 + §6) folded into the same session per the "natural touchpoint" rule.

---

## 3. File-by-file edits

### 3.1 `layer2c/__init__.py` (new)

Re-exports per the established Layer 2x pattern:

```python
from layer2c.builder import (
    Layer2CInputError,
    q_layer2c_equipment_mapper_payload,
)

__all__ = [
    "Layer2CInputError",
    "q_layer2c_equipment_mapper_payload",
]
```

### 3.2 `layer2c/builder.py` (new, ~650 LOC)

Top-of-file module docstring spells out the spec contract + DP resolutions + the §5.1-vs-§6 reconciliation rationale. Three SQL loaders + helpers + the public entry point:

**Constants:**
- `_REQUIRED_ETL_KEYS = frozenset({"0A", "0B", "0C"})`
- `_LOW_COVERAGE_THRESHOLD = 0.50` (§8.1)
- `_CRITICAL_PRIORITY = "Critical"` (§8.2)
- `_DISCIPLINE_ID_PATTERN = re.compile(r"^D-\d{3}[a-z]?$")` (validates D-008b conditional sub-disciplines)

**`Layer2CInputError`** — ValueError subclass; plan-gen catches + surfaces user-facing error (not a HITL gate per spec §4).

**`_validate_inputs`** — all §4 preconditions: locale_id non-empty, locale_equipment_pool list-of-str (may be empty), cluster_locale_ids non-empty containing locale_id, toggle states dict[str, bool], included_discipline_ids non-empty matching D-### pattern, etl_version_set has 0A/0B/0C keys.

**Three DB loaders:**

1. `_load_toggle_defs(db, version_0c) -> dict[str, dict]` — single SELECT against `layer0.sport_specific_gear_toggles` for the active 0C version (DP1 = (A) Runtime lookup per spec §5.1). Returns map keyed by toggle_name with the four fields 2C reads: `paired_equipment_categories`, `also_satisfies`, `gated_discipline_ids`, `display_label`. 11 rows total in v1; UNIQUE-indexed.
2. `_load_discipline_info(db, discipline_ids, version_0a)` — pulls `discipline_name` + `exercise_db_sport` from `sport_discipline_bridge`. Separate from the main exercise query so zero-exercise disciplines still get a `DisciplineCoverage` row per §10. First-row deterministic when a discipline appears under multiple framework_sports.
3. `_load_exercises(db, included_discipline_ids, version_0a, versions_0b)` — the §5.2 sdb⨝sxm⨝e query; uses `versions_0b = [version_0b]` single-element list wrapped per the Phase 2.2 (2D) precedent so the ANY placeholder works on the single 0B string.

**`_build_effective_pool`** — implements §6 prose semantics (one-hop expansion of `also_satisfies` toggle names through the referenced toggle's `paired_equipment_categories`; no cascade). Docstring explains the §5.1-vs-§6 reconciliation. Unknown toggle names in `cluster_gear_toggle_states` skipped silently (UI may carry stale keys).

**Tier resolution helpers:**

- `_tier_1(equipment_required, effective_pool)` — flat-TEXT[] AND semantics; empty list = bodyweight always available.
- `_tier_2(substitutes_structured, effective_pool)` — iterates `equipment_substitutes_structured` in array order (Batch C 3-bucket sort preserved per spec); improvised always resolves (no pool check; flatten-and-dedupe across all CNF groups for the `substitute_equipment` field); empty `equipment_required` on a non-improvised sub auto-resolves with `substitute_equipment=[]`; otherwise first matching AND-group wins (returned flat per the `ResolutionDetail.substitute_equipment: list[str]` typed shape).
- `_tier_3(physical_proxies, effective_pool, exercise_index)` — iterates `physical_proxies`; checks Tier 1 only on the proxy (no cascade per §5.5 bullet 1); proxies pointing to exercises absent from the per-discipline query result skipped silently (performance per §5.5 bullet 3).

**`_dedupe_by_exercise`** — collapses the JOIN result by `exercise_id`; tracks `discipline_ids[]` + `sport_relevance_notes` + `priority_per_discipline` dicts.

**`_resolve_exercise`** — runs the §5.3 → §5.4 → §5.5 cascade; returns `(tier, ResolutionDetail | None)`.

**`_build_coverage`** — per-discipline rollup; iterates `included_discipline_ids` for stable order; skips disciplines absent from `discipline_info` per §10; coverage_pct = 0.0 on zero-exercise disciplines (divide-by-zero handled).

**`_attach_accommodations`** — §5.6 amendment pass-through. Only annotates Tier-1/2/3 entries (Tier-0 aren't prescribable). When `layer2d_payload=None`, leaves the empty default in place.

**`_emit_coaching_flags`** — §8 3-flag surface:
- `toggle_off_for_discipline` emitted FIRST (matches spec §8.3 "fires BEFORE 5.2 query" semantics; deterministic regardless of resolution outcome); reads `gated_discipline_ids` per DP2 = (b); only fires for disciplines actually in `included_discipline_ids`.
- `low_coverage` per discipline with `coverage_pct < 0.50`; `affected_exercise_ids` lists unavailable IDs.
- `critical_dropped` one flag per Tier-0 exercise where any of its discipline priorities is "Critical"; uses primary discipline (first in `discipline_ids`) for the `discipline_name` field.

**Public entry point `q_layer2c_equipment_mapper_payload`** — signature `(db, locale_id, locale_equipment_pool, cluster_locale_ids, cluster_gear_toggle_states, included_discipline_ids, *, layer2d_payload=None, etl_version_set)`. Matches `Layer2C_Spec.md` §3 verbatim with the established conventions: `db` first positional (per Phase 2.1/2.2/2.3 precedent); `layer2d_payload` + `etl_version_set` keyword-only.

### 3.3 `tests/test_layer2c.py` (new)

35 tests across 7 classes + 1 free-standing smoke test, using the `_FakeConn`/`_FakeCursor` pattern from `tests/test_layer2b.py`. Each call to the public entry point issues exactly three SELECTs in fixed order, so the `_FakeConn` queues batches via `queue(*rows)` matching that order.

- **`TestInputValidation`** (9) — empty locale_id, locale_pool not list, locale_pool token not string, empty cluster_locale_ids, locale not in cluster, toggle state non-bool, empty included_discipline_ids, bad D-### pattern, etl_version_set missing key.
- **`TestEffectivePool`** (4) — toggle OFF doesn't expand pool; toggle ON adds paired equipment; `also_satisfies` expands referenced toggle's paired (one-hop); unknown toggle key in state silently skipped.
- **`TestTierResolution`** (7) — Tier 1 with equipment present; bodyweight Tier 1 with empty pool; Tier 2 CNF first-matching-group; Tier 2 improvised always resolves; Tier 2 skips non-matching group then matches; Tier 3 proxy resolution; Tier 3 proxy not in index skipped; Tier 0 when nothing resolves.
- **`TestCoverageAndDedup`** (2) — multi-discipline exercise dedupes (single ResolvedExercise, two coverage rows); mixed-tier coverage_pct math.
- **`TestCoachingFlags`** (5) — low_coverage below 50%; critical_dropped one per exercise; toggle_off_for_discipline fires from gated column; toggle_off skipped when discipline not included; no low_coverage at 100%.
- **`TestAccommodationPassThrough`** (2) — `TempoModificationModality` attaches to Tier-1 resolved exercise; no layer2d_payload leaves accommodations empty.
- **`TestEdgeCases`** (4) — empty pool only bodyweight + improvised resolve; zero-exercise discipline gets low_coverage; discipline missing from sdb skipped; effective_pool sorted + deduped.
- Free-standing — `test_payload_round_trip_typed` (pydantic dump → validate smoke test).

### 3.4 `aidstation-sources/Layer2C_Spec.md` (modified — spec touchpoint edits)

Four edits folding in the doc-sweep nits queued by Phase 2.4-Prep CARRY_FORWARD:

1. **§5.1 Decision Point** — annotated "✅ Resolved 2026-05-19 — DP1 = (A) Runtime lookup." Resolution paragraph explains the cheap-query rationale + the "no Layer 1 disturbance" tradeoff vs alternative (B). Added §5.1-vs-§6 reconciliation note clarifying that `also_satisfies` carries TOGGLE NAMES, not equipment names, and §6 is the canonical reading.
2. **§8.3 Decision Point** — annotated "✅ Resolved 2026-05-19 — DP2 = (b) Structured column." Resolution paragraph notes Andy's divergence from the spec's "(a) for v1, defer (b) to FC-1" recommendation + cites the migration filename + the 3 populated cases.
3. **§10 Edge cases** — new row: "Exercise present in `layer0.exercises` but absent from `etl/sources/parsed_substitutes.json` (Tier 2 source for `equipment_substitutes_structured`)" → ETL extractor's `load_parsed_substitutes_structured` loud-fallback returns `[]`; Tier 2 returns None; cascade falls to Tier 3; no error.
4. **§12 Open Items** — rows 2C-1 + 2C-2 flipped to ✅ Resolved with date + resolution shorthand.

### 3.5 `aidstation-sources/Upstream_Implementation_Plan_v1.md` (modified — spec touchpoint edits)

Three surgical edits:

1. **§4 row 2.4** — rewritten to reflect the Split (Prep 6 + Builder 3) + DP pre-resolution + no /plan-mode gate.
2. **§5.4 ceiling-break list** — strikes 2.4 with explanation of the split outcome; remaining ceiling breaks expected on 3.1 / 4.2 / 5.1.
3. **§6 plan-mode-gate list item 4** — marked "✅ Resolved 2026-05-19 (D-73 Phase 2.4-Prep). DP1 (A); DP2 (b)."

---

## 4. Code / tests

`tests/` count: 866 → 901 (+35). All in the new `tests/test_layer2c.py`.

Module-import sanity: `python -c "from layer2c import Layer2CInputError, q_layer2c_equipment_mapper_payload; print('OK')"` succeeds.

`python -m pytest tests/` → **901 passed in 1.24s**.

---

## 5. Operational sequence for Andy on Neon

The Phase 2.4 builder runs against `_FakeConn` in tests; no Neon dependency in CI. For the §5.0 manual walkthrough scenarios against Andy's PGE 2026 context, the Phase 2.4-Prep operational sequence (3 SQL migrations + ETL re-run) is the hard prerequisite. Documented verbatim in `V5_Implementation_D73_Phase_2_4_Prep_Closing_Handoff_v1.md` §5:

```bash
# 1-3. Apply the three pre-shipped + new migrations
psql $DATABASE_URL -f aidstation-sources/migrations/migrate_exercises_substitutes_structured.sql
psql $DATABASE_URL -f aidstation-sources/migrations/migrate_exercises_terrain_required.sql
psql $DATABASE_URL -f aidstation-sources/migrations/migrate_toggles_v3_columns.sql

# 4. Re-run ETL on a NEW etl_version
python -m etl.layer0.run
```

Once those land, the two new §5.0 scenarios for Phase 2.4 (added to CARRY_FORWARD's manual-walkthrough list) become runnable:

1. **AR baseline 2C call against Andy's PGE 2026 context** — `q_layer2c_equipment_mapper_payload(db, locale_id='home', locale_equipment_pool=<Andy's Nerstrand home gym inventory>, cluster_locale_ids=['home'], cluster_gear_toggle_states={'Climbing — roped': True, 'Rappelling / abseiling': True, 'Snowshoeing setup': False, ...}, included_discipline_ids=<PGE 2026 AR set>, etl_version_set=<plan-gen pin>)`. Confirm: (a) `effective_pool` includes both Climbing — roped paired-equipment AND Rappelling/abseiling paired-equipment via §6 one-hop expansion; (b) coverage_pct >70% on running / hiking / MTB / strength; (c) Bench Press resolves Tier 1 at home; (d) hypothetical hotel pool shifts barbell exercises to Tier 2 DB; (e) `Snowshoeing setup: False` × included D-015 fires the `toggle_off_for_discipline` flag; (f) no `critical_dropped` flags at home.
2. **Empty-pool degenerate** — `locale_equipment_pool=[]`, all toggles OFF, 1 discipline included. Confirm only bodyweight + improvised resolve, most exercises hit Tier 0, `low_coverage` flag fires with discipline name + `affected_exercise_ids`, no call failure.

CARRY_FORWARD.md walkthrough count rises 67 → 69.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**With Phase 2 complete, the upstream arc opens onto Phase 3.** Per `Upstream_Implementation_Plan_v1.md` §4 row 3.1:

**Phase 3.1 — Layer 3A LLM driver.** First upstream LLM driver: `llm_layer3a_athlete_state_evaluation(...)` + paired `Layer3A_v1.md` prompt body in `aidstation-sources/prompts/`. Pattern: Layer 4 Step 4a single-session precedent.

- Pydantic schema already shipped (`Layer3APayload` + sub-models in `layer4/context.py`).
- Capped retry + validator (lightweight; 3A has §4 validation rules).
- Anthropic SDK extended-thinking + tool-use; dependency-injectable `LLMCaller` per Layer 4 precedent.
- Prompt body source decisions D1-D10 (tool-use; extended thinking budget; payload rendering; retry context; schema length caps; voice).

**Triggers #2 (prompt body authoring) + #8 (architectural alternatives) expected** — opens with a /plan-mode gate.

Estimated 6-8 substantive files (over ceiling — driver + prompt body + Anthropic SDK adapter + tests + bookkeeping; precedented by Layer 4 Step 4a).

### 6.2 Alternative pivots

- **Layer 4 Step 7** — env-gated `ANTHROPIC_API_KEY` scaffolding. Lands the Anthropic SDK plumbing without a real call (~3-4 files). Strategic value: unblocks Phase 5 vertical slice in parallel with Phase 3 work; the live LLM call can come later when the key is provisioned.
- **§H.2 / §J / §I.1 form-refresh PR** — paired alignment to wire Layer 2B + Layer 2E input-source surfaces simultaneously. Closes Open Items 2B-2 + 2B-3 + Layer 2E open items 2E-1 (FFM promotion) + 2E-6 (supplement_vocabulary integration via §I.1 structured supplements) + 2E-12 (pregnancy status capture). ~6-8 files (multi-section form refresh; over ceiling). De-stubs Layer 2E §5.5 supplements when shipped.
- **Plan Management spec authorship** — de-stubs Layer 2E §5.8 heat acclim. Per Layer 2E open items 2E-2/3/4, the `PlanManagementState` + `HeatAcclimState` contracts are unwritten. Spec session, no implementation. ~3-4 spec files.
- **D-73 Phase 1.4 — D-52 catalog migration sequencing** — /plan-mode gate per `Upstream_Implementation_Plan_v1.md` §6 item 2. Less urgent now that all 5 Layer 2 runtimes confirmed catalog reads are unaffected by D-52.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration (~6-8 files). Orthogonal to D-73 arc.
- **Manual §5.0 walkthrough of accumulated 69 scenarios** — Andy's call when to batch-walk. Notably the just-added 2 Phase 2.4 scenarios need Neon migrations + ETL re-run first.

### 6.3 Operating notes for next session

Read order per Rule #13:

1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff
3. `aidstation-sources/CARRY_FORWARD.md` — 69 walkthrough scenarios + remaining doc nits + orthogonal tracks
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward from 1.3 / 2.1 / 2.2 / 2.3 / 2.5 / 2.4-Prep):** the cloud container's default `pytest` binary is `uv tool install pytest` with isolated Python; working test command is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

**Branch-naming H1 precedent:** this session was the first across the Phase 2 chain where the harness-pinned name was scope-aligned (`claude/phase-2-4-implementation-RHRDh`). No rename happened. The H1 rename rule (per CLAUDE.md branch-naming guidance) still applies when the harness pins a mismatched name — surface to Andy at session start.

**If picking Phase 3.1 (Layer 3A LLM driver):** the /plan-mode gate at session start should walk the D1-D10 source decisions (tool-use; extended thinking budget; payload rendering; retry context shape; schema length caps; coaching-flag enum closed-set scope; voice; file location for the prompt body). Reuse Layer 4 Step 4a as the precedent — single-session shipped the driver + prompt body + Anthropic SDK extension + tests + bookkeeping; expect ~6-8 files over ceiling. The `LLMCaller` dependency-injection pattern from `tests/test_layer4_single_session.py` (`_stub_caller` + `_sequence_caller`) is the test-harness precedent.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Phase 2.4 Layer 2C builder as architect-recommended | Andy 2026-05-20 | Predecessor closing-handoff §6.1 named this as the architect-recommended next move; DPs already resolved in Prep; no /plan-mode gate needed; 3 substantive files comfortably under ceiling. |
| 2 | `_build_effective_pool` implements §6 prose semantics, not §5.1 pseudo-code | Architect-pick + spec touchpoint edit | Recon during implementation found that §5.1's pseudo-code adds `toggle_def.also_satisfies` items directly to the equipment pool. The deployed data shape per `migrate_toggles_v3_columns.sql` + `Vocabulary_Audit_v2.md §4.2` treats `also_satisfies` as TOGGLE NAMES (single case: `Climbing — roped` → `['Rappelling / abseiling']`). §6 prose is the canonical reading — when toggle X has `also_satisfies = [Y]`, then turning X on adds Y's `paired_equipment_categories` to the pool (one hop, no cascade per §6 paragraph 3). Builder implements §6 semantics + the spec gets a `§5.1-vs-§6 reconciliation` note as part of this session's spec touchpoint edits. |
| 3 | Tier 2 `substitute_equipment` is flat `list[str]` (not nested CNF) | Architect-pick | The typed contract is `ResolutionDetail.substitute_equipment: list[str] \| None`, not `list[list[str]]`. The spec pseudo-code in §5.4 has `substitute_equipment=[group]` (which would be `list[list[str]]`) but the typed shape forces a flat list. For non-improvised match: return the matching AND-group flat (`list(group)`). For improvised: flatten + dedupe across all CNF groups since all are "household-assumed" (preserves token semantics; flat is the shipped contract). |
| 4 | 0B etl_version wrapped to single-element list `versions_0b = [version_0b]` | Phase 2.2 precedent | Layer2C_Spec.md §5.2 query uses `ANY` for 0B versions (multi-version active), but `etl_version_set: dict[str, str]` carries a single 0B string. Wrap to single-element list at the SQL boundary; when the contract evolves to carry a real set, only the wrapping changes. Same pattern as Layer 2D. |
| 5 | `_load_discipline_info` separate from main exercise query | Architect-pick | §10 requires that zero-exercise disciplines still surface a `DisciplineCoverage` row + a `low_coverage` flag. A pure sdb-only query upfront guarantees the (discipline_name, exercise_db_sport) map for every `included_discipline_id` regardless of whether the main exercise query returns rows. First-row deterministic when a discipline appears under multiple framework_sports (exercise_db_sport should be stable across them). |
| 6 | `_emit_coaching_flags` emits `toggle_off_for_discipline` first | Spec §8.3 fidelity | Spec §8.3 says the flag "fires BEFORE 5.2 query" — meaning it's deterministic regardless of resolution outcome. Builder iterates `toggle_defs` for flags FIRST, then iterates coverage for low_coverage + resolved for critical_dropped. Order matters because Layer 4 may rank by flag_type; emitting the toggle flag first keeps the spec semantic visible in payload ordering. |
| 7 | `Layer2DPayload` optional input via `layer2d_payload` keyword-only | Spec §5.6 amendment | The §5.6 amendment (2026-05-17) requires accommodation pass-through from 2D. Builder accepts `layer2d_payload: Layer2DPayload \| None = None`; when None, accommodations stay empty default. Orchestrator (Phase 5) will thread the real 2D payload through. Optional shape lets v1 callers (and tests) omit when 2D output isn't relevant. |
| 8 | Spec touchpoint edits folded into this session | "Natural touchpoint" rule | The Phase 2.4-Prep CARRY_FORWARD §10 explicitly queued 5 doc nits for "the Phase 2.4 builder session — natural touchpoint." Folding them in this session closes the loop + avoids a tiny standalone PR. 2 of the 5 substantive files are spec edits (Layer2C_Spec.md + Upstream_Implementation_Plan_v1.md); 3 are code. Total 5 = at the ceiling. |
| 9 | `_attach_accommodations` only annotates Tier-1/2/3 (not Tier-0) | Spec §5.6 intent | Tier-0 exercises aren't prescribable — no modality applies. Matches the spec amendment language "for every exercise resolved at Tier 1, 2, or 3 (i.e., prescribable; not unavailable)." Tier-0 entries keep their empty default accommodations list. |
| 10 | Validation uses `D-\d{3}[a-z]?` regex for discipline IDs | Discipline-id convention | Matches the v1 deployed convention: D-001..D-016 for the AR set + D-008b (whitewater conditional sub-discipline). The `[a-z]?` suffix allows future sub-discipline IDs without re-tightening. Shape-only validation; canonical lookups happen UI-side per spec §4 bullet 1. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `layer2c/__init__.py` exists with re-exports of `Layer2CInputError` + `q_layer2c_equipment_mapper_payload` | ✅ grep |
| `layer2c/builder.py` defines `Layer2CInputError` (ValueError subclass) | ✅ grep |
| `layer2c/builder.py` defines `q_layer2c_equipment_mapper_payload` with the spec §3 signature | ✅ grep |
| `layer2c/builder.py` `_load_toggle_defs` queries `layer0.sport_specific_gear_toggles` (DP1=A runtime) | ✅ grep |
| `layer2c/builder.py` `_build_effective_pool` expands `also_satisfies` via one-hop toggle lookup (§6 semantics) | ✅ grep + inline docstring |
| `layer2c/builder.py` `_tier_2` handles improvised + non-improvised + empty equipment_required branches | ✅ grep |
| `layer2c/builder.py` `_tier_3` skips proxies not in exercise_index | ✅ grep |
| `layer2c/builder.py` `_attach_accommodations` reads `Layer2DPayload.accommodated_exercises` | ✅ grep |
| `layer2c/builder.py` `_emit_coaching_flags` reads `gated_discipline_ids` from toggle row (DP2=b) | ✅ grep |
| `tests/test_layer2c.py` exists with 35 tests across 7 classes + 1 free-standing | ✅ `grep -c "def test_" tests/test_layer2c.py` = 35 |
| `python -m pytest tests/test_layer2c.py` → 35 passed | ✅ `35 passed in 0.27s` |
| `python -m pytest tests/` → 901 passed | ✅ `901 passed in 1.24s` |
| `Layer2C_Spec.md` §5.1 Decision Point annotated "✅ Resolved 2026-05-19 — DP1 = (A) Runtime" | ✅ grep |
| `Layer2C_Spec.md` §5.1 carries the §5.1-vs-§6 reconciliation note | ✅ grep |
| `Layer2C_Spec.md` §8.3 Decision Point annotated "✅ Resolved 2026-05-19 — DP2 = (b) Structured column" | ✅ grep |
| `Layer2C_Spec.md` §10 carries new edge case row for missing parsed_substitutes.json entries | ✅ grep |
| `Layer2C_Spec.md` §12 Open Items 2C-1 + 2C-2 flipped to ✅ Resolved | ✅ grep |
| `Upstream_Implementation_Plan_v1.md` §4 row 2.4 reflects Split (Prep 6 + Builder 3) | ✅ grep |
| `Upstream_Implementation_Plan_v1.md` §5.4 ceiling-break list strikes 2.4 | ✅ grep |
| `Upstream_Implementation_Plan_v1.md` §6 plan-mode-gate item 4 marked ✅ Resolved | ✅ grep |
| Branch is `claude/phase-2-4-implementation-RHRDh` (harness-pinned, scope-aligned) | ✅ `git branch --show-current` |
| `CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `CURRENT_STATE.md` Layer status row 2 reads "🟢 All 5 of 5 runtimes shipped … 2C (Phase 2.4-Prep substrate 2026-05-19 + Phase 2.4 builder 2026-05-20)" | ✅ inspection |
| `CURRENT_STATE.md` Tests note bumped 866 → 901 | ✅ inspection |
| Backlog D-73 status note extended to name Phase 2.4 as shipped + Phase 2 complete | ✅ grep |
| Backlog `## Changelog` H2 has a new 2026-05-20 Phase 2.4 entry above the 2.4-Prep entry | ✅ grep |
| `CARRY_FORWARD.md` Manual §5.0 walkthrough count rose 67 → 69 (+2 Phase 2.4 scenarios) | ✅ inspection |
| `CARRY_FORWARD.md` Phase 2.4-Prep doc-sweep nits (§5.1 + §8.3 DP closure, §10 edge case, §12 Open Items, §4 row 2.4) struck-through as resolved | ✅ inspection |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (5 files; AT the 5-file ceiling):**

1. New `layer2c/__init__.py` — re-exports per the established Layer 2x pattern.
2. New `layer2c/builder.py` — full `Layer2C_Spec.md` §3-§10 implementation: validation + 3 SQL loaders + §5.1+§6 effective-pool construction + §5.3/5.4/5.5 tier cascade + §5.6 accommodation pass-through + §5.7 coverage rollup + §8 coaching flags.
3. New `tests/test_layer2c.py` — 35 tests across 7 classes.
4. Modified `aidstation-sources/Layer2C_Spec.md` — §5.1 + §8.3 Decision Points annotated ✅ Resolved with rationale; §5.1-vs-§6 reconciliation note; §10 new edge-case row; §12 Open Items 2C-1 + 2C-2 flipped to ✅ Resolved.
5. Modified `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 2.4 rewritten (Split outcome); §5.4 ceiling-break list strikes 2.4; §6 plan-mode-gate item 4 marked ✅ Resolved.

**Bookkeeping (4 files; outside ceiling per B3):**

6. Modified `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer 2 status row reads "🟢 All 5 of 5 runtimes shipped"; Tests note bumped to 901; D-73 arc note extended ("Phase 2 complete").
7. Modified `aidstation-sources/Project_Backlog_v62.md` — in-place: D-73 status note extended to name Phase 2.4 as shipped + Phase 2 of 5 COMPLETE; new 2026-05-20 Phase 2.4 entry in `## Changelog` (above the 2.4-Prep entry).
8. Modified `aidstation-sources/CARRY_FORWARD.md` — Manual §5.0 walkthrough gains 2 Phase 2.4 scenarios (count 67 → 69); doc-sweep nits §5.1+§8.3 DP closure + §10 edge case + §12 Open Items + Upstream Plan §4 row 2.4 marked as resolved this session.
9. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_2_4_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` gains 2 new §5.0 walkthrough scenarios under a "D-73 Phase 2.4" sub-bullet. Scenario count rises 67 → 69.

`CARRY_FORWARD.md` Phase 2.4-Prep doc-sweep nits closed (struck through with resolution date):

- ~~`Layer2C_Spec.md` §5.1 + §8.3 Decision Points annotation~~ ✅ Landed 2026-05-20.
- ~~`Layer2C_Spec.md` §10 edge case for missing parsed_substitutes entry~~ ✅ Landed 2026-05-20.
- ~~`Upstream_Implementation_Plan_v1.md` §4 row 2.4 + §5.4 + §6 updates~~ ✅ Landed 2026-05-20.

Remaining carry-forward (untouched this session): `etl/sources/parsed_substitutes.json` curation cadence + K-parser source location doc task; routes/onboarding.py:710 docstring tense; Layer4_Spec.md §4.5 source-pointer wording; Race_Events_D66_Design_v1.md §8.3 `open_ended` → `no-event`; Layer2A_Spec.md §5.2 pla.default_inclusion correction + Open Item 2A-1; Layer2D_Spec.md §3 "9-value enum" → 11-value; Upstream_Implementation_Plan_v1.md §4 row 2.2 read-tables rewrite; HealthConditionRecord.system_category 8 → 11 alignment; routes/injuries.py:BODY_PARTS 24 → 41 canonical alignment; Layer2B_Spec.md §13.1 TRN-008/009 swap + §7/§13 pct unit alignment note; §H.2 + §J + §I.1 form-refresh PRs; Plan Management spec authorship; Layer2E_Spec.md §6.1/§14 D-26 staleness + §3 shape vs deployed.

No new orthogonal carry-forwards this session.

Layer 4 Step 4f + Step 7 + Step 8 still queued per the existing list.

---

**End of handoff.**
