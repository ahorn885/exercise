# V5 Design — Provider Translation Layer Storage-Schema Build (#681 §4 wave) — Closing Handoff v1

**Date:** 2026-06-18
**Type:** Build design (no code). Design-only this session at Andy's instruction; ratify §9 then build Slice 1.
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

**Substantive (1 — under ceiling):**
- `aidstation-sources/designs/ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` — NEW.

**Bookkeeping (ceiling-exempt):** `CURRENT_STATE.md`, this handoff, PR (to be opened), #681 comment.

## §4 — Code / tests

None — design doc only. No code, no DDL, no test changes. (Full suite was 2647 passed / 30 skipped at the predecessor session; untouched.)

## §5 — Manual verification owed (Andy)

- **None for this design doc.**
- Carried, unchanged: post-#572 live **T3 refresh** re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify on a real Garmin log (Neon egress blocked from the container); the #698 carried live-verifies (Slice 3b + race-week-brief recovery).

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **Ratify the design's §9 open questions** (Q1–Q5; my rec on each is in the doc) — then **build Slice 1** (Trigger #3 already satisfied by *this* ratified design; the build is execution). Slice 1 = create the 3 tables (public `_PG_MIGRATIONS`) + seed `provider_value_map` (strength `ex_id` rows + the 15 coarse-cardio rows, verbatim) + repoint the 4 consumers (§5 of the design) + delete the dicts. Additive, no behavior change; golden parity test gates the dict→table move.
2. **Slice 2** — cardio fidelity: `cardio_log.discipline_id` + fine-D-id cardio rows (matrix option C) + the D-id→coarse collapse + the §12 indoor-machine flag in `raw_payload`.
3. **Slice 3** — Polar/COROS ingest consolidation + the **zero-row-guarded** bespoke-table drops (irreversible; gated on a live `neon-query` check). `provider_outbound_ref` consumers wait for the outbound wave (3a/3b).
4. **Deferred batches (matrix §7):** Batch 4 MyFitnessPal (Layer-2E-blocked); Batch 5 Apple/Samsung/Google Health (native-client-gated).

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| S4-1 | Source of truth for `provider_value_map` | **Table is canonical now** — retire the scattered dicts into it (no parallel authoring home) |
| S4-2 | Scope this session | **Design only, no build** — ratify §9 first |

**Proposed in the design, awaiting ratification (design §9):** Q1 consolidated seed module (rec yes) · Q2 public-schema `_PG_MIGRATIONS` not `layer0-apply` (rec yes) · Q3 D-id→coarse collapse as a Python dict (rec yes) · Q4 defer `provider_outbound_ref` to the outbound wave (rec defer) · Q5 Slice-1 auto-merge (rec yes).

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Design doc (new) | `aidstation-sources/designs/ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` | exists; §2.1 "table becomes canonical source of truth, now"; §3 the 3 `CREATE TABLE` blocks; §5 "Consumer repoint graph" 4-row table + "ordering constraint C1"; §7 the 4-slice table; §9 Q1–Q5 |
| Rolling state | `aidstation-sources/CURRENT_STATE.md` | "Last shipped" = storage-schema build design / design-only / names this handoff; matrix v2 demoted to first Predecessor |
| Canon (still unchanged) | `etl/layer0/discipline_canon.py` | highest D-032; no `etl/` `D-033` (this wave adds no discipline) |
| Parent spec (unchanged) | `aidstation-sources/specs/Provider_Data_Translation_Layer_Spec_v1.md` | §4.2–4.4 are the DDL source this design refines |
| PR / issue | PR pending; GitHub #681 (open) | open the PR ready-for-review; comment #681 with the design link; epic kept open |

## §9 — Carry-forward

- The build is **gated on ratifying the design's §9 (Q1–Q5)** — all have a recommendation; a one-line "Q1–Q5: yes/yes/dict/defer/yes" greenlight unblocks Slice 1.
- **The sharp edge for the build session is the consumer repoint (design §5):** `NAME_TO_EX_ID` has 4 consumers + the seed-before-backfill ordering constraint; a miss degrades silently to bucket-3 (no crash). The golden parity test + a seed-count-before-backfill assertion make a miss loud — do not skip them.
- **Slice 3's zero-row guard is a live check, not an assumption** — confirm the bespoke Polar/COROS tables hold no athlete rows (read-only `neon-query`) before any drop.
- Matrix-v2 findings still standing for the build: provider source URLs + unit traps (Wahoo joules, RWGPS/Wahoo kcal-vs-cal, TP `TotalTime`=hours) are empirical-check items (Rule #14, not guesses).
