# #884 Unified Gear/Craft Model — Slice 6c-3 (legacy `athlete_craft_locale` retirement) — Closing Handoff v1

**Written:** 2026-06-30 (branch `claude/6c3-2c-resolve-mfuvo2`, fresh off `main`, NOT stacked; commit `6ff79d5`). **Kickoff:** `…Slice6c3_LegacyCraftLocaleRetire_2026_06_30_Kickoff_Handoff_v1.md`. **Predecessors:** the 6c column-cleanup closing (`…Slice6cColumnCleanup_BroughtCraftDrop…`), slice 5 (`…Slice5_AwayOverlay…`, which made the repo app-dead). **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 6c. **Issue:** [#884](https://github.com/ahorn885/exercise/issues/884).

---

## 1. What shipped

Retired the **app-dead** `athlete_craft_locale` surface — the standing "this craft is kept at this locale" (b) store from Event Windows Slice 4. Slice 5 (away overlay) cut the live write/read path onto the gear analogue `athlete_gear_locale` (`replace_gear_locale` / `load_gear_locales`), leaving `athlete_craft_locale_repo.py` + the `athlete_craft_locale` table with **no live app reader** — only the deploy-time backfill that seeded `athlete_gear_locale`. This slice deletes the dead module, its tests, and the table. Behavior-neutral.

This **completes slice 6c** (6c-1 brought-gear cutover + 6c-2 onboarding parity + column-cleanup `brought_craft` drop + 6c-3 craft_locale retirement all shipped).

## 2. Precondition (verified)

- **Live write/read path is on gear_locale:** `routes/locales.py` imports + calls `replace_gear_locale` / `load_gear_locales` (lines 21/23/1051/1206/1276/1357). No live caller of the deleted craft-locale repo remained — only `tests/test_layer4_event_windows.py` imported it.
- **Slice-5 gear_locale write live in prod:** 6c-1 deployed to prod READY (`dpl_BdNXRecgy3gQsVnv9Tg7UzGzgHMS`, sha `2230185`, per the column-cleanup closing + CURRENT_STATE), so every deploy since slice 5 ran the `athlete_craft_locale → athlete_gear_locale` backfill a final time → `athlete_gear_locale` is authoritative and the table can go.

## 3. Changes (Rule #11 edits, as applied)

1. **`git rm athlete_craft_locale_repo.py`** — app-dead module, no live importer.
2. **`init_db.py`** (public-schema `_PG_MIGRATIONS`):
   - Removed the `athlete_craft_locale` table create + `idx_acl_user` index + the `(b)` comment (was ~2641–2649).
   - Removed the `craft_locale → gear_locale` backfill `INSERT` + comment (was ~3123–3127) **and** its now-orphaned `_GEAR_BACKFILL_CRAFT_IN` constant (clean up own orphan — the backfill was its only consumer).
   - Appended `"DROP TABLE IF EXISTS athlete_craft_locale CASCADE"` at the `_PG_MIGRATIONS` tail (after the column-cleanup's `brought_craft` DROP) with a 6c-3 comment. `CASCADE` drops the orphaned index; `IF EXISTS` → re-run safe + clean no-op on a fresh DB (the create is gone, the table is never made).
3. **`tests/test_layer4_event_windows.py`** — dropped the dead-repo import block (was ~30–35) and the whole `TestCraftLocaleRepo` section (was ~1043–1088). The unrelated integration section after it stays. (Gear-locale equivalents are covered by the `athlete_gear_repo` tests; nothing lost.)
4. **`athlete_gear_repo.py`** — scrubbed the 4 now-dangling `Mirrors athlete_craft_locale_repo.*` doc-pointers (on `load_gear_locales` / `replace_gear_locale` / the gear-locale eviction / `_validate_gear_ids`). These pointed a reader at a deleted file; the gear repo IS the authority now, mirrors nothing.

**Kept intentionally** (historical context, not dangling code-pointers): `routes/locales.py:1041` ("prior `athlete_craft_locale` write" — explains why the gear write is byte-identical), `athlete_gear_repo.py:8` (lineage docstring — `athlete_crafts_repo` still exists, so "the two craft repos" framing reads as design history), `init_db.py` comment on `athlete_gear_locale` ("the gear analogue of athlete_craft_locale" — accurate lineage for the surviving table).

## 4. Cache / behavior

Behavior-neutral. No live reader of `athlete_craft_locale` remained; away-segment standing-gear resolution is already on `athlete_gear_locale` (slice 5). **No plan-cache invalidation owed.** The dead repo's `evict_plan_caches_on_craft_locale_change` (layer `"craft_locale"`) had no live caller; the live path uses `evict_plan_caches_on_gear_locale_change` (layer `"gear_locale"`).

## 5. Verification (Rule #10)

- `grep -rn athlete_craft_locale` over `*.py` → only the intentional comments in §3 + the new `DROP` line. Zero live code references.
- `init_db.py` parses; `DROP TABLE IF EXISTS athlete_craft_locale CASCADE` is in `_PG_MIGRATIONS`; the create + index + backfill + `_GEAR_BACKFILL_CRAFT_IN` are gone.
- `tests/test_layer4_event_windows.py` imports cleanly; targeted subset (`test_layer4_event_windows test_athlete_gear_repo test_layer1_builder test_init_db_schema test_redesign_locales_form_render`) **172 passed**.
- **Full suite 3965 passed / 30 skipped** (only the 3 pre-existing #217 `evidence_basis` warnings).
- **3 substantive files** (`athlete_craft_locale_repo.py` deleted, `init_db.py`, `athlete_gear_repo.py`) + 1 test — under the 5-file ceiling.
- **Owes a deploy, NOT a `layer0-apply`** (public-schema `_PG_MIGRATIONS` auto-applies on each Vercel deploy).

## 6. Next + operating notes

### 6.1 Next — the deferred per-segment 2C re-resolve (slice-5 §2)

The only remaining slice-6 item. **Architectural — Stop-and-ask triggers #3 (cross-layer surface change) + #5 (architectural alternatives); present + confirm before building.** Goal: thread an away-cluster 2C payload (the destination's equipment pool + gear-toggle states) through `EventWindowSegment` → `per_phase` → `synthesize_phase`, so an away week's strength-substitute exercise pool (`pool_by_discipline`) + `toggle_off_for_discipline` flag reflect the destination's equipment, not the home gym's. Today Layer 2C is built once against the home cluster; the away env is captured only in `EventWindowSegment.away_feasibility` (terrain/craft), and the away cascade still uses the home `fi.pool_by_discipline`.

**Plumbing mapped this session (read-only, ~3 core + 2 test files):**
- `layer4/session_feasibility.py` — `EventWindowSegment` (~line 860): the dataclass that would carry the away 2C pool/payload.
- `layer4/orchestrator.py` — `_build_event_window_overlay` away branch (~line 933) already unions standing `athlete_gear_locale` + `brought_gear`; it calls `_resolve_included_feasibility` (~line 630) which currently passes the **home** `fi.pool_by_discipline`. The away 2C payload is already in `cone.layer2c_payloads[away_locale]` (a dict of ALL cluster locales) — no new DB read. Insertion: extract `away_pool_by_discipline` from that payload (reuse the `_gather_feasibility_inputs` lines ~587–601 logic, worth a `_extract_pool_by_discipline` helper) and thread it as an optional `pool_override` into the cascade.
- `layer4/per_phase.py` — `synthesize_phase` (~line 3581) already receives `layer2c_payloads` + `event_window_segments`; `_format_event_window_overlay` (~line 1661) renders the per-segment substitutes. If the away pool is correct at cascade time, the renderer needs no change (substitutes already come from the away `TerrainResolution`). Optional enhancement: render away 2C `toggle_off_for_discipline` coaching flags.

The away strength-substitute pool currently still uses the **home** gym's equipment — an existing limitation predating slice 5 (slices 2/3/4 carried it), now the last #884 item. It depends on slice-6 brought-gear capture (shipped) to be observable.

### 6.2 Operating notes (Rule #13 read order)

1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — what just shipped + current focus. 3. `CARRY_FORWARD.md` — #884 rolling item. 4. This closing + the 6c-3 kickoff + the slice-5 closing + the slice-6 plan. 5. `./scripts/verify-handoff.sh` — automated anchor sweep.

**PR state:** pushed; PR not yet opened — wait for Andy's go, then open (ready, not draft) + `enable_pr_auto_merge` with the **merge** method. Bookkeeping rides this same branch.

---

## 7. Issue reconciliation

[#884](https://github.com/ahorn885/exercise/issues/884) — commented: slice 6c-3 shipped (commit `6ff79d5`), slice 6c complete; the deferred per-segment 2C re-resolve is the sole remaining slice-6 item. Issue stays **open** for the 2C re-resolve.

---

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Dead repo deleted | `athlete_craft_locale_repo.py` | file absent (`git rm`) |
| Table create + index removed | `init_db.py` | no `CREATE TABLE IF NOT EXISTS athlete_craft_locale` / `idx_acl_user` in `_PG_MIGRATIONS` |
| craft_locale→gear_locale backfill + orphan constant removed | `init_db.py` | no `FROM athlete_craft_locale` INSERT; no `_GEAR_BACKFILL_CRAFT_IN` |
| DROP appended at the list tail | `init_db.py` | `"DROP TABLE IF EXISTS athlete_craft_locale CASCADE"` after the `brought_craft` DROP |
| Test import + class removed | `tests/test_layer4_event_windows.py` | no `from athlete_craft_locale_repo import`; no `class TestCraftLocaleRepo` |
| Dangling doc-pointers scrubbed | `athlete_gear_repo.py` | no `Mirrors \`athlete_craft_locale_repo.` strings |
| No live craft_locale code reader left | (repo grep) | `grep -rn athlete_craft_locale` over `*.py` → only the kept comments (§3) + the DROP |
| Parses + tests green | (local) | `init_db.py` parses; subset **172 passed**; full suite **3965 passed / 30 skipped** |
| Owes a deploy, not a `layer0-apply` | — | public-schema `_PG_MIGRATIONS` |

---

**End of closing handoff.**
