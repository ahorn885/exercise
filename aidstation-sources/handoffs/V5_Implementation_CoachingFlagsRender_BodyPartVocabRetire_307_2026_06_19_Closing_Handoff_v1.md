# #307 — upstream coaching_flags render (Layer 4) + body_part_vocab_miss retirement + injury-form vocab expansion — Closing Handoff

**Issues:** [#307](https://github.com/ahorn885/exercise/issues/307) (coaching_flags systemically dead channel across Layers 2–3) + the `body_part_vocab_miss` cleanup that surfaced alongside it. Under #295 / #201 (orphaned-code sweep).
**Branch:** `claude/race-day-fueling-detail-pqzf7h`. **PR [#774](https://github.com/ahorn885/exercise/pull/774) — open, CI green, pending merge** (opened under the remote/web harness rule that auto-opens a PR after push; Andy has been interacting with it).
**Predecessor:** `handoffs/V5_Implementation_RaceDayFuelingDetailRender_333_300_2026_06_19_Closing_Handoff_v1.md` (named #300 item 3 / #307 as the primary next move).

> Every Layer 2 builder emits a `coaching_flags` advisory list but no Layer 4 prompt rendered them — a dead channel. Added a shared suppress-on-empty `format_upstream_coaching_flags` helper and wired the 2A/2B/2C/2D flags into all four prompt builders. 2E excluded by design (Layer 5A owns nutrition). Alongside it, the `body_part_vocab_miss` flag was found **reachable on valid structured dropdown picks** (not dead) and was **retired fully** at Andy's direction, with the injury-form body-part vocab expanded to a closed canonical set. Suite green at 2790.

---

## 1. What happened (in order)

1. **Resumed the predecessor's primary NEXT — #300 item 3 / #307** (the coaching_flags dead channel). Read #307 + #300: #300 is closed (Layer 2E nutrition; item 3 handed to #307); #307 is the governing issue.
2. **Mapped the channel** (Explore): every Layer 2 builder (2A/2B/2C/2D/2E) emits `coaching_flags`; 3A/3B carry **none**. Only `TrainingSubstitutionPayload.coaching_flags` was ever rendered (`per_phase` + `race_week_brief`). Confirmed per-builder payload availability: `single_session` has only 2C+2D in scope; the other three builders have all of 2A/2B/2C/2D.
3. **Andy ratified the scope (Trigger #1):** render 2A/2B/2C/2D into all prompts via one shared helper; **exclude 2E** (Layer 5A consumes nutrition downstream, training→nutrition).
4. **Sub-decision — `body_part_vocab_miss`.** Surfaced that this flag is **reachable**, not dead: the injury `body_part` is a structured dropdown, but the flag audits against `BODY_PART_KEYWORDS` (a subset of the dropdown), so valid picks `Abdomen`/`Other` tripped it. Andy: **"map abdomen, delete other"** → then, when the full retirement scope (cross-layer field + ~13 test files) was laid out, **"retire it fully"** and **"expand structured list"** for the body-part vocab.
5. **Built #307 + the body_part changes.** Suite green at 2790.
6. **Caught a missed cache bump during the doc pass:** the new render block changes the per_phase + plan_refresh prompt → `LAYER4_PROMPT_REVISION "13"→"14"` (was missing from the first commit; added).
7. **Doc scope call (Andy):** the per-layer **design** specs are frozen records — not version-bumped per code change. Living updates → CURRENT_STATE / CARRY_FORWARD / issues.

## 2. What shipped

**#307 — `layer4/per_phase.py` `format_upstream_coaching_flags(*, layer2a, layer2b, layer2c_payloads, layer2d)`** (mirrors `format_measured_physiology`):
- Suppress-on-empty (returns `[]`); self-contained block with a one-line advisory header.
- Each flag → `- [discipline|terrain|equipment|injury] flag_type (scope): message`; scope = `discipline_name` (else `discipline_id`) + `target_terrain_id`, via `getattr` (handles the per-layer flag-shape differences).
- Per-locale 2C flags de-duplicated on `(label, flag_type, message)`.
- Wired into **all four** builders: `per_phase.render_user_prompt` (2A/2B/2C/2D), `single_session._render_user_prompt` (2C+2D only — 2A/2B not in scope), `plan_refresh.llm_layer4_plan_refresh` (2A/2B/2C/2D via `layer2_bundle`, centralized after the physiology block), `race_week_brief._render_user_prompt` (2A/2B/2C/2D, after the substitution section).
- **2E excluded by design; 3A/3B have no flags;** pre-existing `TrainingSubstitutionPayload` render untouched/not duplicated.
- **`hashing.py` `LAYER4_PROMPT_REVISION "13"→"14"`** (per_phase + plan_refresh prompt content changed → cached plans + refreshes regenerate; single_session ad-hoc, no bump).

**body_part_vocab_miss — fully retired (Trigger #3):**
- `layer2d/builder.py`: removed the §8.6 emit loop, the `body_part_vocab_misses` param of `_emit_coaching_flags`, the computation block, and the two call/construction references.
- `layer4/context.py`: removed `Layer2DPayload.body_part_vocab_misses` (cross-layer contract field).
- Tests: removed the `body_part_vocab_misses=[]` construction kwarg from ~11 Layer4/2C test files; replaced `TestBodyPartVocabMiss` (Brain+Abdomen) with `TestBodyPartVocabMissRetired` (asserts no such flag/field).

**Injury-form vocab expansion (closed structured field):**
- `routes/injuries.py` `BODY_PARTS`: added `Left/Right Glute`, `Left/Right Calf`, `Left/Right Shin`, `Left/Right Achilles`, `Chest`, `Left/Right Rib`; **removed `Other`**.
- `athlete.py` `BODY_PART_CONSTRAINTS`: added the six new canonical parts with movement-constraint mappings; removed the `Other` catch-all entry.
- `layer2d/builder.py` `BODY_PART_KEYWORDS`: mapped `Abdomen` (`abdomen`/`abdominal`/`oblique`/`rectus abdominis`).

## 3. Ratified decisions (Andy, this session)

1. **#307 scope:** render 2A/2B/2C/2D via one shared helper into all four prompts; **2E excluded** (Layer 5A owns nutrition, training→nutrition); 3A/3B have no flags.
2. **`body_part_vocab_miss`:** **retire it fully** (flag + computation + the `Layer2DPayload` field + tests), having been shown reachable-not-dead.
3. **Injury-form coverage:** **expand the structured list** (Glute/Calf/Shin/Achilles/Chest/Rib) rather than restore an `Other` catch-all; keep the field closed over canonical parts.
4. **Docs:** per-layer design specs are frozen — no `_v2` version bumps for this change; update the living docs + issues only.

## 4. Validation

- **Full suite 2790 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/ -q`). (Was 2791 pre-retirement; the two vocab-miss tests collapsed to one retirement-lock test, net −1; +8 new `format_upstream_coaching_flags` tests; +6 new body-part-constraint canonical entries covered.)
- New `TestFormatUpstreamCoachingFlags` (`tests/test_layer4_structured_cardio_337.py`): suppress-on-empty, per-layer label, scope rendering, per-locale 2C dedup, source ordering.
- `test_layer2d.py` `TestBodyPartVocabMissRetired`: no `body_part_vocab_miss` flag + no `body_part_vocab_misses` attr.
- `test_injury_form_constraints.py`: `CANONICAL_PARTS` updated (+6), `test_other_catch_all_retired` locks `Other` removal.
- The `LAYER4_PROMPT_REVISION` bump is exercised by the existing monkeypatch test (`test_prompt_revision_changes_*_key`, value-agnostic) — no literal pin broke.

## 5. Manual verification owed + next pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Owed (Andy-action, live-verify):**
1. Generate/refresh a real plan for an athlete whose injury or discipline-risk emits a 2A/2B/2C/2D `coaching_flag` → confirm the `Upstream coaching flags` block renders in the synthesizer prompt (prompt dump / `/admin/logs`) and the cache bump (`14`) regenerated the cached plan. The green suite covers the helper + wiring, not the live prompt render.

**Next moves:**
1. **#304 — Layer-1 captured-but-not-threaded sweep** (per-field thread-or-stop decisions).
2. **Continue #295** — orphaned built-but-not-wired sweep.
3. On PR #774 merge, **close #307** (`completed`, ref PR #774) — both checklist items done (2E excluded by design; 3A/3B no flags). #307 was commented this session; left open until merge.

## 6. Deferred edits (Rule #11)

None — the slice is fully built and tested.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Render helper | `layer4/per_phase.py` | `def format_upstream_coaching_flags(` — suppress-on-empty; `- [{label}] {fl.flag_type}{scope}: {fl.message}`; 2C dedup on `(label, flag_type, message)` |
| Wiring | `layer4/{per_phase,single_session,plan_refresh,race_week_brief}.py` | each calls `format_upstream_coaching_flags(...)`; single_session passes only `layer2c_payloads=[...]` + `layer2d` |
| Cache bump | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "14"` + the `"14" = #307 …` comment |
| Vocab-miss retired | `layer2d/builder.py`, `layer4/context.py` | no `body_part_vocab_miss` / `body_part_vocab_misses` symbols remain (grep clean) |
| Injury vocab | `routes/injuries.py`, `athlete.py`, `layer2d/builder.py` | `BODY_PARTS` has Glute/Calf/Shin/Achilles/Chest/Rib, no `'Other'`; `BODY_PART_CONSTRAINTS` +6 parts, no `'Other'`; `BODY_PART_KEYWORDS` has `"Abdomen"` |
| Tests | `tests/test_layer4_structured_cardio_337.py`, `tests/test_layer2d.py`, `tests/test_injury_form_constraints.py` | `TestFormatUpstreamCoachingFlags`, `TestBodyPartVocabMissRetired`, `test_other_catch_all_retired` |
| Suite | `tests/` | `/tmp/venv/bin/python -m pytest tests/ -q` → 2790 passed / 30 skipped |
| Issues | #307 (commented; closes-on-merge of PR #774), #300 (already closed) | — |

## 8. Carry-forward

- **#307 coaching_flags render BUILT** (2A/2B/2C/2D into all four Layer-4 prompts via `format_upstream_coaching_flags`; 2E excluded by design; cache bump `14`). PR #774 open, CI green. Live-verify owed (see §5).
- **`body_part_vocab_miss` fully retired + injury-form vocab expanded** (Glute/Calf/Shin/Achilles/Chest/Rib; Abdomen mapped; `Other` removed → closed structured field).
- **Doc convention recorded (Andy 2026-06-19):** per-layer design specs are frozen design-phase records — not version-bumped per code change; living state is CURRENT_STATE / CARRY_FORWARD / issues.
- **STILL OWED (carried, unchanged):** #337 measured-physiology live-verify; #698 C1/C2 live-verify + Part-A item (b); post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.
