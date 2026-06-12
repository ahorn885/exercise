# V5 Housekeeping — `aidstation-sources/` reorganization + cleanup

**Date:** 2026-06-11
**Branch:** `claude/aidstation-sources-reorg`

## 1. What this session was

Two things, in order. First: closed the Layer 0 migration epic's gate-clearing work — migrations `0002` (`supplement_vocabulary`) + `0003` (`terrain_gap_rules`) de-orphaned the two spec-sourced tables, clearing the §6.4 freeze gate (**PR [#546](https://github.com/ahorn885/exercise/pull/546)**, squash-merged to `main`). Then Andy asked to expand scope into a **doc/repo reorganization**: the flat `aidstation-sources/` root (87 loose `.md` files, heavy superseded-version chains, placeholder cruft, dead ETL scratch) → a foldered structure that reads clearly for a non-technical user and keeps the auto-loaded `CLAUDE.md` + `verify-handoff.sh` machinery working.

**Decision (Andy):** archive superseded versions (don't delete — reconciles the ask with Rule #12); structure approved as proposed.

## 2. What shipped

**New `aidstation-sources/` layout** (was: flat dump of 87 root `.md`s):

```
CLAUDE.md  CURRENT_STATE.md  CARRY_FORWARD.md  PR_Verification_Status.md  README.md   ← machinery, stay at root
specs/      ← 14 canonical layer + architecture specs (Control_Spec_v8, Layer0_ETL_Spec_v8, Layer1–4, athlete data/onboarding)
designs/    ← 19 per-feature design docs (D-NN designs, X-series, Modality_Group, AuthoringModel, …)
research/   ← 8 audits/evidence (Bridge_Bands, Vocabulary_Audit_v3, Craft/Equipment recon, DATABASE, …)
plans/      ← 5 implementation/migration plans
prompts/    handoffs/    scripts/    .claude/   ← unchanged (prompts/ is imported by live code — left in place)
archive/
  backlog/           ← unchanged (frozen Project_Backlog chain)
  superseded-specs/  ← 35 superseded _vN versions (Control_Spec v1–v7 + unsuffixed, Layer0_ETL_Spec v2–v7, etc.)
  etl-scratch/       ← retired one-off ETL: etl/ migrations/ patches/ data/ vocab_reconciliation/
```

- **Categorized moves** were done by script with a completeness assert (every one of the 87 root `.md`s assigned exactly once; 0 orphans, 0 duplicates). Highest `_vN` of each chain kept in its live folder; the rest archived.
- **`README.md` rewritten** as a plain-English index: a "read these three first" intro, a "Where do I find…?" table, and a one-line description of every folder — the non-technical entry point Andy asked for. (Renaming the spec files was *rejected* — it would break ~63 `prompts/` + ~49 root-`HANDOFF.md` + ~12 cross-references and CLAUDE.md's resolve-by-logical-name mechanic; the folder names + README index deliver the readability without the breakage.)
- **`CLAUDE.md` synced:** architecture-doc pointer → `specs/Control_Spec`; depth-standard → `specs/Layer2C_Spec.md`; Rule #12 updated to "current stays in live folder, superseded → `archive/superseded-specs/`" + a reorg note.
- **Deletes (cruft only):** 8 `ph` git-keep stubs (3-byte "ph") + `placeholder.md` ("blah"). **No content deleted** — everything else is a `git mv` (121 renames). Empty `reference/`/`vocab_reconciliation/` dissolved.
- **Repo-root tidy:** 4 stray dated `HANDOFF-2026-05-*.md` → `aidstation-sources/handoffs/`. Left the two brand `.zip`s at root (possibly-wanted assets — flagged below) and the live root app docs (`HANDOFF.md` 49 refs, `DATABASE.md`, `DEV_SETUP.md`, `PROVIDERS_SCHEMA.md`).

**Change set:** 121 renames · 9 deletes (cruft) · 2 edits (`README.md`, `CLAUDE.md`).

## 3. Verification

- **Completeness assert** in the move script: 87/87 root docs assigned, 0 orphans/duplicates.
- **All references into the archived ETL-scratch dirs confirmed doc-only** (no `.py`/`.yml`/CI dependency; the one live-looking hit was a *negative* comment in `run_owed_layer0_migrations.sql`). **`prompts/` confirmed imported by live code** (`layer4/cache.py`, `layer3b/builder.py`) → left in place.
- **`verify-handoff.sh` green** against this handoff (its machinery — `CURRENT_STATE.md` pointer, `handoffs/`, `archive/backlog/` — all stayed at root).
- No app code or CI touched; the reorg is docs-only.

## 4. Owed / next move

1. **The freeze (Option 3) — the next slice**, now unblocked (gate cleared by #546, and this reorg gives a clean base). Retire the xlsx authoring path: relocate the live-referenced constants out of `etl/layer0/extractors/` (`RACE_INELIGIBLE_TERRAIN_IDS`, `_TERRAIN_STRUCTURED_ROWS`, toggle/substitute helpers) into a staying module, then archive `extractors/` + `run.py` + `emit_sql.py` + the v14/v19 workbooks + their ETL-only tests. Fires Trigger #6 — lead with a keep-vs-retire classification of each external reference before moving. (Full analysis in the `…Migrations0002_0003…` handoff §4 + this session's chat.)
2. **Brand `.zip`s at repo root** (`AIDSTATION PRO Brand Handoff[ V2].zip`) — 0 code refs, binaries. Left in place pending Andy's call (delete, or relocate to a `brand/` or out of git).
3. **Carried (unchanged):** `0003` Neon re-apply is optional (terrain_gap_rules already live); cold-plan post-deploy verify (slice 3b/#521); go-live blockers #539/#540.

## 5. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| New foldered structure | `aidstation-sources/` | `specs/` `designs/` `research/` `plans/` dirs exist; root has only the 5 machinery `.md`s |
| Superseded versions archived, not deleted | `aidstation-sources/archive/superseded-specs/` | contains `Control_Spec_v7.md`, `Layer0_ETL_Spec_v2.md`, … (35 files) |
| Plain-English index | `aidstation-sources/README.md` | "Where do I find…?" table + per-folder descriptions |
| CLAUDE.md path refs synced | `aidstation-sources/CLAUDE.md` | "`specs/Control_Spec`" + Rule #12 "`archive/superseded-specs/`" |
| Current specs resolvable | `aidstation-sources/specs/` | `Control_Spec_v8.md`, `Layer2C_Spec.md` present (CLAUDE.md depth standard) |
| Cruft removed, content preserved | git | 9 deletes are all `ph`/`placeholder.md`; 121 renames (no content loss) |

### 5.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. **Note the new doc layout** — specs in `specs/`, designs in `designs/`, etc.; superseded versions under `archive/superseded-specs/`; see `README.md`. The next substantive slice is the **freeze (Option 3)**, gated on a Trigger-#6 surface.

## 6. Stop-and-ask status

The reorg structure + the Rule #12 reconciliation (archive vs delete) were surfaced and approved before executing. No code/CI/contract surface touched. The freeze (next) is Trigger #6 and will be surfaced with a keep/retire classification before any file moves.

## 7. Summary

Closed the migration epic's gate-clearing work (#546 merged: `0002`+`0003` de-orphan the spec-sourced tables, freeze gate cleared), then reorganized `aidstation-sources/` from a flat 87-file dump into `specs/` · `designs/` · `research/` · `plans/` with superseded `_vN` versions moved to `archive/superseded-specs/` (Rule #12 reconciled to archive-not-delete, Andy's call) and dead ETL scratch to `archive/etl-scratch/`. `README.md` is now a plain-English index ("read these three first" + a where-do-I-find table); `CLAUDE.md` paths + Rule #12 synced; only 3-byte `ph` cruft deleted (121 renames, no content lost). `verify-handoff.sh` green; no app/CI touched. Next: the xlsx-authoring **freeze** (Option 3), now unblocked.
