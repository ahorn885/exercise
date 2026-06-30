# #884 Unified Gear/Craft Model — Slice 6c column cleanup (`brought_craft` column DROP) — Closing Handoff v1

**Session:** 2026-06-30 · branch `claude/gear-craft-column-cleanup-zwdlcx` (fresh off `main`; NOT stacked) · PR not yet opened (push + bookkeep + wait for Andy's go).
**Kickoff:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6c_OnboardingParityLegacyRetire_2026_06_29_Kickoff_Handoff_v1.md` §2 (the deferred DROP). **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 6c. **Predecessor:** 6c-1 (`…Slice6c1_BroughtGearCutover_2026_06_30…`, the brought-gear read+write cutover that deferred this DROP).

---

## 1. Session narrative — the 1-file tail of 6c-1

6c-1 renamed `EventWindow.brought_craft` → `brought_gear` and cut the repo's **read + write** onto the new `brought_gear` column. It deliberately **kept** the legacy `brought_craft` column plus the deploy-time `brought_craft`→`brought_gear` backfill, deferring the column DROP to this follow-up. The reason (6c-1 §3 deviation 2, the slice-4.3 redump-fold lesson): the old write path only ever wrote `brought_craft`, so `brought_gear` was populated lazily by the backfill — dropping the source column in the *same* deploy as the cutover would risk losing data from any row written by the old path just before deploy. The DROP is safe only **after** 6c-1's read+write cutover has deployed (so `brought_gear` is authoritative and the backfill has run a final time).

**Precondition verified live this session.** 6c-1 merged as PR #1038 (merge commit `2230185`) and deployed to **production READY** (`dpl_BdNXRecgy3gQsVnv9Tg7UzGzgHMS`, `githubCommitSha 2230185…`, `target: production`, `state: READY`). Two later prod deploys (#1039 6c-2, #1040) also landed READY. So the brought-gear write path is live and the final backfill has run — the legacy column can be retired.

## 2. File-by-file edits

### 2.1 `init_db.py` (substantive — the only code file)
All three edits are in the public-schema `_PG_MIGRATIONS` list (auto-applies on each Vercel deploy):
- **Removed** the `brought_craft` column create (`ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS brought_craft TEXT`) and its 4-line Slice-4 comment.
- **Removed** the deploy-time backfill (`UPDATE athlete_event_windows SET brought_gear = brought_craft WHERE brought_gear IS NULL AND brought_craft IS NOT NULL AND btrim(brought_craft) <> ''`) and its 2-line comment — its source column is going away and 6c-1's deploy already ran it a final time.
- **Appended** at the `_PG_MIGRATIONS` tail: `"ALTER TABLE athlete_event_windows DROP COLUMN IF EXISTS brought_craft"`, with a comment explaining the 6c-1-tail provenance + the `IF EXISTS` re-run/fresh-DB safety.

### 2.2 `athlete_event_windows_repo.py` (comment-only touch)
The `brought_gear` field comment said "the `brought_craft` column drop is the 6c-1 redump-fold follow-up" (forward-looking). Updated to past-tense ("the legacy `brought_craft` column was dropped in the 6c column-cleanup follow-up") so the next reader doesn't re-discover it as still-owed work. No behavior change.

## 3. Notes

- **Migration ordering is safe both ways.** *Existing prod DB:* `brought_craft` exists + `brought_gear` exists & backfilled → the tail DROP removes `brought_craft`. *Fresh DB init:* `brought_craft` is never created (create removed), `brought_gear` is created directly (its own `ALTER … ADD` is untouched, ~`init_db.py:3110`) and written by the new path → the tail `DROP … IF EXISTS` is a clean no-op.
- **No runtime reader of the dropped column.** The repo reads `row["brought_gear"]` (since 6c-1). The only surviving `brought_craft` string in live code is the **deliberate digest-stability tombstone** in `layer4/hashing.py` — the fold dict KEY is kept as the legacy string `"brought_craft"` (it reads the renamed `brought_gear` *attribute* for its value) so `compute_event_windows_hash` stays byte-stable. This is in-memory only; **the column drop does not touch it** and owes no plan-cache invalidation.
- **Owes a deploy, NOT a `layer0-apply`.** Public-schema → rides `_PG_MIGRATIONS` on the next Vercel deploy. No Neon apply, no layer0 work.

## 4. Manual §5.0 verification step (owed to Andy)
After this deploys: an **away** event window with brought gear still saves + displays its brought set (read/write already on `brought_gear` since 6c-1; this slice only removes the now-unused legacy column behind it). Nothing user-visible changes — the check is that event-window save/display is unaffected by the column drop. (Optional DB spot-check: `\d athlete_event_windows` no longer lists `brought_craft`.)

## 5. Next session pointers

### 5.1 Remaining slice 6c
- **6c-3 — legacy retirement** (kickoff §4, riskiest): retire app-dead `athlete_craft_locale_repo.py` + its tests + the `athlete_craft_locale` table. **Do NOT** drop the `discipline_baseline_*` craft CSVs (live Layer-1 substitution source) without re-homing Layer 1 onto `athlete_gear` first — a larger cross-layer move, likely out of #884 scope. Coordinate any layer0 drops with a redump-fold; likely its own scoped Layer-0 housekeeping slice.
- The deferred per-segment **2C re-resolve** (slice-5 §2) also lives in slice 6 — architectural, its own slice.

### 5.2 Operating notes (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this column cleanup). 3. `CARRY_FORWARD.md` (#884 rolling item). 4. This handoff + the 6c kickoff + the 6c-1 closing + the slice-6 plan. 5. `./scripts/verify-handoff.sh`.

## 6. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| `brought_craft` create removed | `init_db.py` | no `ADD COLUMN … brought_craft` in `_PG_MIGRATIONS` |
| `brought_craft`→`brought_gear` backfill removed | `init_db.py` | no `UPDATE athlete_event_windows SET brought_gear = brought_craft` |
| DROP appended at the list tail | `init_db.py` | `"ALTER TABLE athlete_event_windows DROP COLUMN IF EXISTS brought_craft"` is the last entry before the `_PG_MIGRATIONS` close `]` |
| Repo comment de-staled | `athlete_event_windows_repo.py` | `brought_gear` field comment reads "was dropped in the 6c column-cleanup follow-up" |
| No live `brought_craft` reader left | (repo grep) | `grep -rn brought_craft` over `*.py` → only the `hashing.py` tombstone (key + comments) + `init_db.py` DROP/comments + historical comments |
| Parses + tests green | (local) | `init_db.py` parses; `tests/test_layer4_event_windows.py test_routes_event_windows.py test_layer4_hashing.py test_onboarding_skills.py test_redesign_locales_form_render.py test_layer1_builder.py test_init_db_schema.py` → **271 passed** |
| 6c-1 prod deploy precondition met | (Vercel) | `dpl_BdNXRecgy3gQsVnv9Tg7UzGzgHMS` sha `2230185` target production state READY |
| Owes a deploy, not a `layer0-apply` | — | public-schema `_PG_MIGRATIONS` |

## 7. Files shipped this session

**Substantive (1, well under ceiling):** `init_db.py`.
**Comment touch (not really substantive):** `athlete_event_windows_repo.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue #884 comment.

---

**End of handoff.**
