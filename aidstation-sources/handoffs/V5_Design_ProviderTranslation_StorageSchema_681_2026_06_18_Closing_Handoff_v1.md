# V5 Design — Provider Translation Layer Storage-Schema Build (#681 §4 wave) — Closing Handoff v1

**Date:** 2026-06-18
**Type:** Build design + **Slice 1 build**. Andy ratified §9 Q1–Q5 + table-canonical this session; Slice 1 shipped (full suite 2650 passed / 30 skipped).
**Branch:** `claude/admiring-euler-rj3gqh` (scope matches; kept). PR pending.
**Predecessor handoff:** `handoffs/V5_Spec_ProviderInboundMatrix_681_Wave2_v2_RowingMintReversal_2026_06_18_Closing_Handoff_v1.md` (the merged matrix-v2 spec; its §6 NEXT = this build wave).

---

## §1 — Session-start verification (Rule #9)

Continued the merged matrix-v2 thread ("check it out and keep working"). Ran the full anchor sweep before any new work — **clean, no drift:**
- `aidstation-sources/scripts/verify-handoff.sh` — all ✅ (files exist; backlog frozen; §8 table extracted); working tree clean.
- Matrix-v2 §8 anchors spot-checked: `specs/Provider_Inbound_Matrix_v2.md` carries the status line "§6 Rowing mint — REVERSED", the §6 "Do NOT mint" bullet, **§12** "Discipline vs. training-modality / equipment", and "freshest-timestamp-wins"; v1 preserved under `archive/superseded-specs/`.
- Canon unchanged: **no `D-033` anywhere in `etl/`**; `discipline_canon.py` `CANONICAL_NAMES` highest = D-032.
- Rolling state + carry: `CURRENT_STATE.md` "Last shipped" = matrix v2; `CARRY_FORWARD.md` line 16+ carries "#681 Wave 2 … §6 mint REVERSED", "freshest-timestamp-wins", follow-up "cancelled".
- PR #723 confirmed **MERGED** (by Andy, 2026-06-18) via GitHub MCP.

## §2 — What changed this session (the decisions)

The matrix-v2 handoff names the **§4 storage build wave** as the next high-value move. It is **Trigger #3 (cross-layer schema)** — three new tables forming the provider→canonical contract — so per CLAUDE.md it is **designed, not built**. Surfaced the design + the gating decisions to Andy (`AskUserQuestion`); he ratified:

- **`provider_value_map` is the canonical source of truth NOW.** The scattered Python dicts (`NAME_TO_EX_ID`, `GARMIN_STRENGTH_ALIASES`, `LOGGED_NAME_ALIASES`, `GARMIN_TYPE_TO_PLAN_SPORT`, Polar/COROS field maps) are **retired into the table**, not kept as a parallel authoring home. (This is the spec end-state — avoids a dual-source limbo.)
- **Design only this session; nothing ships until §9 is ratified.**

Wrote `designs/ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` — concrete DDL for the 3 tables, the table-canonical realization (one consolidated committed seed module materialized via `ON CONFLICT DO UPDATE`), the 4-consumer repoint graph + the `init_db` seed-before-backfill ordering constraint, a 3-slice build plan (additive Slice 1 → cardio fidelity → gated bespoke-table drops), tests, and 5 open questions.

## §3 — Files (substantive vs bookkeeping)

**Substantive (design + Slice 1 = 7; one coherent dicts→table refactor):**
- `aidstation-sources/designs/ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` — NEW (build design; §0 records the as-built realization).
- `provider_value_map_seed.py` — NEW (the consolidated seed = git authoring surface + table source; 147 strength + 15 cardio = 162 rows).
- `provider_strength_resolve.py` — `_alias_map` + category backstop read the seed; deleted the 2 alias dicts + the `layer0_progression` import.
- `garmin_connect.py` — `_plan_sport_type` reads the seed; deleted `GARMIN_TYPE_TO_PLAN_SPORT`.
- `layer0_progression.py` — deleted `NAME_TO_EX_ID` (moved to the seed).
- `init_db.py` — `CREATE provider_value_map` + `provider_raw_record` (PG_SCHEMA); materialize the seed (`ON CONFLICT DO UPDATE`); repointed the `current_rx` backfill to the seed map.
- `tests/test_provider_strength_resolve.py` — repointed imports + 3 new seed-rows tests.

**Bookkeeping (ceiling-exempt):** `CURRENT_STATE.md`, this handoff, PR #733, #681 comment.

## §4 — Code / tests

**Slice 1 shipped.** New tables `provider_value_map` (seeded, 162 rows) + `provider_raw_record` (created for Slice 2's writers) via public `PG_SCHEMA` (auto-applies on Vercel deploy — NOT `layer0-apply`). The 4 scattered provider dicts were consolidated into `provider_value_map_seed.py` — **generated verbatim from the live dicts** (a one-off script; fidelity asserted equal before deleting the originals) — and deleted from their old homes. Consumers import the seed module; `init_db` materializes the same seed into the table (so they cannot drift). **Verification:** resolver parity **152/152 identical** vs a captured pre-refactor baseline; full suite **2650 passed / 30 skipped** (+3 seed tests); DDL parens balanced; `init_db` imports clean. Rule #15: `init_db` prints the seeded row count. **No behavior change** (deterministic refactor; no LLM cache bump).

## §5 — Manual verification owed (Andy)

- **None for this design doc.**
- Carried, unchanged: post-#572 live **T3 refresh** re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify on a real Garmin log (Neon egress blocked from the container); the #698 carried live-verifies (Slice 3b + race-week-brief recovery).

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **Slice 1 — DONE** (Q1–Q5 ratified; PR #733; suite 2650). 
2. **NEXT = Slice 2 (cardio fidelity, design §6).** `ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS discipline_id TEXT`; author the **fine-D-id cardio rows** into `provider_value_map_seed` (`canonical_kind='discipline'`) transcribed from the matrix-v2 per-provider cardio tables (`Provider_Inbound_Matrix_v2.md` §2 Strava / §10 Wahoo·RWGPS / §11 TP — each row gives the fine D-id); add the **D-id→coarse collapse** as a Python `dict` next to the resolver (ratified Q3; matrix §1 option-C mapping); write the **§12 indoor-machine flag** into `provider_raw_record.raw_payload` (the table's first writer) + repoint the cardio ingest to carry the D-id. Rule #15 log the `(provider,typeKey)→D-id→coarse` decision. Deterministic — no LLM cache bump.
3. **Slice 3** — Polar/COROS ingest consolidation into core + `provider_raw_record`; then the **zero-row-guarded** bespoke-table drops (irreversible; gated on a live `neon-query` check first). `provider_outbound_ref` waits for the outbound wave (3a/3b).
4. **Deferred batches (matrix §7):** Batch 4 MyFitnessPal (Layer-2E-blocked); Batch 5 Apple/Samsung/Google Health (native-client-gated).

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| S4-1 | Source of truth for `provider_value_map` | **Table is canonical now** — retire the scattered dicts into it (no parallel authoring home) |
| S4-2 | Scope this session | **Design only, no build** — ratify §9 first |

**§9 RATIFIED (Andy 2026-06-18): Q1 yes (consolidated seed module) · Q2 yes (public `PG_SCHEMA`, not `layer0-apply`) · Q3 dict (D-id→coarse collapse) · Q4 defer `provider_outbound_ref` · Q5 yes (Slice-1 auto-merge).** As-built deviation from design §5 (recorded in doc §0): consumers **import the consolidated seed module**, not the table-with-cache, because `resolve_strength_ex_id` is a pure function asserted ~20× with no DB and runs off the `apply_session_outcome` hot path — a table read would break the suite for zero gain. The table stays the canonical store, materialized from the seed (can't drift). Resolver parity 152/152.

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Design doc | `aidstation-sources/designs/ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` | exists; **§0 "Ratification & as-built status"** (Q1–Q5 ratified + realization adjustment); §3 the 3 `CREATE TABLE` blocks; §6 the cardio Slice 2 plan |
| Seed module (new) | `provider_value_map_seed.py` | `STRENGTH_NAME_TO_EX_ID` (147) + `GARMIN_TYPE_TO_PLAN_SPORT` (15) + `provider_value_map_rows()` yields 162 ten-col tuples; the old dict symbols (`NAME_TO_EX_ID` etc.) exist ONLY here now |
| Table CREATE + seed | `init_db.py` | `PG_SCHEMA` has `CREATE TABLE IF NOT EXISTS provider_value_map` + `provider_raw_record`; `INSERT … ON CONFLICT … DO UPDATE` from `provider_value_map_rows()`; backfill loops `STRENGTH_NAME_TO_EX_ID` |
| Resolver repoint | `provider_strength_resolve.py` | `_alias_map()` returns `STRENGTH_NAME_TO_EX_ID`; backstop uses `STRENGTH_COARSE_NAME_TO_EX_ID`; no local dicts. `pytest tests/test_provider_strength_resolve.py` = 19 passed |
| Rolling state | `aidstation-sources/CURRENT_STATE.md` | "Last shipped" = storage-schema design **+ Slice 1 built** / names this handoff; matrix v2 demoted to first Predecessor |
| Canon (still unchanged) | `etl/layer0/discipline_canon.py` | highest D-032; no `etl/` `D-033` (this wave adds no discipline) |
| PR / issue | PR [#733](https://github.com/ahorn885/exercise/pull/733); GitHub #681 (open) | #733 = design + Slice 1; #681 has the wave comment; epic kept open |

## §9 — Carry-forward

- The build is **gated on ratifying the design's §9 (Q1–Q5)** — all have a recommendation; a one-line "Q1–Q5: yes/yes/dict/defer/yes" greenlight unblocks Slice 1.
- **The sharp edge for the build session is the consumer repoint (design §5):** `NAME_TO_EX_ID` has 4 consumers + the seed-before-backfill ordering constraint; a miss degrades silently to bucket-3 (no crash). The golden parity test + a seed-count-before-backfill assertion make a miss loud — do not skip them.
- **Slice 3's zero-row guard is a live check, not an assumption** — confirm the bespoke Polar/COROS tables hold no athlete rows (read-only `neon-query`) before any drop.
- Matrix-v2 findings still standing for the build: provider source URLs + unit traps (Wahoo joules, RWGPS/Wahoo kcal-vs-cal, TP `TotalTime`=hours) are empirical-check items (Rule #14, not guesses).
