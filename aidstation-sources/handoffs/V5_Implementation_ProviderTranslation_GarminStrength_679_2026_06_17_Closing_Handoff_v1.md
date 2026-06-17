# V5 Implementation — #679 Garmin strength name → layer0 EX-id resolver — Closing Handoff v1

**Date:** 2026-06-17
**Type:** Build (data-mapping, inbound). Code shipped. PR pending on branch `claude/upbeat-euler-q4ucqa` (auto-merge enabled).
**Branch:** `claude/upbeat-euler-q4ucqa` (harness-pinned; scope matches).

---

## §1 — Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the predecessor handoff (`V5_Spec_ProviderDataTranslationLayer_681_682_679_..._v1.md`): all §1 file-existence anchors ✅, backlog tracked in GitHub issues, working tree clean. Spot-checked on-disk: `rx_engine.apply_session_outcome` keyed off `(rx['layer0_exercise_id'] if rx else None) or NAME_TO_EX_ID.get(exercise)` (line ~205); `layer0_progression.NAME_TO_EX_ID` = 20 entries (incl. EX246–249); `garmin_fit_parser._EXERCISE_SUBTYPE_MAP` builds from `fit_tool`. No drift. The #679 design was **RATIFIED** (Andy 2026-06-17), build deferred to this session.

## §2 — What this session produced

Built the ratified #679 design — the first concrete **inbound** slice of the #681 provider data translation layer. A logged strength exercise NAME now resolves to its canonical layer0 EX-id at the single write chokepoint, so Garmin-logged lifts stop landing as NULL-EX-id "first exposure" rows and start surfacing as capacity-derived loads in plan-gen.

The build splits cleanly into a **safe, HITL-free core** (shipped) and a **HITL batch** (worksheet, awaiting Andy — D-10).

## §3 — Files

**Substantive (4 — under the 5-file ceiling):**
- `provider_strength_resolve.py` — NEW. The resolver: `GARMIN_STRENGTH_ALIASES` (12 token-exact specifics) + `resolve_strength_ex_id(name) -> (ex_id, match_kind)` (alias → category-collapse → bucket-3). The subtype→category reverse map is built lazily from `garmin_fit_parser`'s maps (graceful-degrades to {} if fit_tool absent).
- `rx_engine.py` — wired the chain at `apply_session_outcome` (replacing the bare `NAME_TO_EX_ID.get`); added `match_kind`/`bucket3` to the return dict; extended the Rule #15 log line. Dropped the now-unused `NAME_TO_EX_ID` import (kept `progression_pattern`).
- `tests/test_provider_strength_resolve.py` — NEW. Alias / category / bucket-3 / specificity / seed-integrity + a real-`garmin_fit_parser`-map integration case.
- `tests/test_rx_engine_apply_outcome_layer0.py` — extended with the four #679 cases (design §6).

**Bookkeeping (ceiling-exempt):** `designs/ProviderTranslation_GarminStrength_679_CandidateBatch_v1.md` (the D-10 ratification worksheet), this handoff, `CURRENT_STATE.md`, GitHub #679 comment, the PR.

## §4 — Code / tests

Full suite **2580 passed / 30 skipped** (`/tmp/tvenv` = `requirements.txt` + pytest). No DDL, no prompt revision, no `LAYER4_PROMPT_REVISION` bump (post-resolution data path, outside the cache). Required CI checks unaffected by language: Python-only change (JS harness / Layer 0 integrity gate untouched).

**Resolution chain at `apply_session_outcome`:**
```
row_ex_id = rx['layer0_exercise_id'] if rx else None
if row_ex_id:  layer0_exercise_id, match_kind = row_ex_id, 'existing'
else:          layer0_exercise_id, match_kind = resolve_strength_ex_id(exercise)
# resolve_strength_ex_id: alias (NAME_TO_EX_ID ∪ GARMIN_STRENGTH_ALIASES)
#                         → category-collapse (subtype→FIT category → coarse NAME_TO_EX_ID)
#                         → (None,'bucket3')
```
Coverage measured: category-collapse rescues **582** subtypes across the 11 already-mapped categories; the 12 token-exact aliases add specificity beyond the coarse collapse. The #430 contract is preserved — step 1 (existing backfilled EX-id) and the `None`/bucket-3 fallback (legacy `exercise_inventory` pattern) are unchanged; the new steps only fill the gap between them.

## §5 — Deviation from the ratified design (flagged)

Design §3.2 / handoff §6 step 1 said "add `rapidfuzz` to `requirements.txt`." **I did not.** The shipped resolver is **exact-match only** (alias + category-collapse + bucket-3) and needs no fuzzy matching at runtime; adding an unused runtime dependency is exactly the speculative bloat CLAUDE.md's simplicity-first principle rejects ("first principle wins, flag the conflict"). The offline alias authoring used stdlib `difflib` — the existing ETL precedent (`etl/layer0/validation/vocab_alignment.py`). If Andy wants `rapidfuzz` for ongoing authoring tooling, it can be added when a committed tool consumes it.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (4-tier order):**
1. **Finish the in-flight task — apply Andy's D-10 batch.** Work `designs/ProviderTranslation_GarminStrength_679_CandidateBatch_v1.md` once Andy marks it up: Batch A (fuzzy aliases → add to `GARMIN_STRENGTH_ALIASES`), Batch B (coarse category-home extensions → a sibling coarse map / extend `NAME_TO_EX_ID`), Batch C (new EX-ids → a gated `layer0` migration like 0011, if greenlit). Follow-up PR.
2. **Live-verify (Andy-action):** a real Garmin strength upload now self-heals its EX-id and a subsequent plan-gen reads it (carried from #430 Slice C; Neon egress blocked from the container so it can't be done here). Watch `/admin/logs` for `match_kind=` / `bucket3=` lines.
3. **Wave 2+** of the translation arc (full inbound matrix; outbound serializers; bucket-3 inline UI; API security wave) per the Wave-1 spec.

## §7 — Decisions / notes pinned

- Resolver is **additive** to the #430 path; no regression (existing 5 layer0-EX-id tests still pass unchanged).
- **No new vocabulary shipped** — the category-collapse reuses already-ratified coarse `NAME_TO_EX_ID` entries; new vocab (fuzzy aliases, category homes, new EX-ids) is the explicit D-10 batch, none auto-applied.
- Bucket-3 in this slice = the **resolution outcome + return tag + log** (the `provider_raw_record` persistence + inline-completed UI are later waves, per design §4).
- The snapshot `etl/output/layer0_etl_v1.8.0.sql` shows 211 live exercises (max EX245) — it predates migration 0011 (EX246–249); the authoring catalog = snapshot-live ∪ 0011's 4.

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Resolver | `provider_strength_resolve.py` | `resolve_strength_ex_id` returns `(ex_id, match_kind)`; `GARMIN_STRENGTH_ALIASES` has 12 entries; `_subtype_to_category()` lazy-builds from `garmin_fit_parser` |
| Wiring | `rx_engine.py` | `from provider_strength_resolve import resolve_strength_ex_id`; `match_kind`/`bucket3` in the return dict; no `NAME_TO_EX_ID` import remains |
| Tests | `tests/test_provider_strength_resolve.py`, `tests/test_rx_engine_apply_outcome_layer0.py::TestStrength679Resolution` | full suite 2580 passed / 30 skipped |
| Worksheet | `aidstation-sources/designs/ProviderTranslation_GarminStrength_679_CandidateBatch_v1.md` | Batch A/B/C; "AWAITING ANDY (D-10)" |
| Pointer | `aidstation-sources/CURRENT_STATE.md` | Top entry "APP — #679 GARMIN STRENGTH NAME → layer0 EX-id RESOLVER — BUILT"; Wave-1 spec demoted to predecessor |
| Issue | GitHub #679 | session comment with PR link + what shipped + the D-10 batch |

## §9 — Carry-forward

- **rapidfuzz** intentionally not in `requirements.txt` (§5) — revisit if a committed authoring tool needs it.
- The D-10 candidate batch (Batch A/B/C) is the open HITL item; the shipped core is independent.
- Live-verify of EX-id self-heal on a real Garmin log remains owed (Andy-action; container can't reach Neon).
