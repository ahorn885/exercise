# #884 Unified Gear/Craft Model — Slice 6c-3 (legacy `athlete_craft_locale` retirement) — Kickoff Handoff v1

**Written:** 2026-06-30 (from the 6c column-cleanup session, branch `claude/gear-craft-column-cleanup-zwdlcx`). **Predecessors:** the 6c kickoff §4 (`…Slice6c_OnboardingParityLegacyRetire_2026_06_29_Kickoff…`), the column-cleanup closing (`…Slice6cColumnCleanup_BroughtCraftDrop_2026_06_30…`), slice 5 (`…Slice5_AwayOverlay…`, which made the repo app-dead). **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 6c. **Issue:** [#884](https://github.com/ahorn885/exercise/issues/884).

---

## 1. What 6c-3 is (and is NOT)

**Retire the app-dead `athlete_craft_locale` surface** — the standing "this craft is kept at this locale" (b) store from Event Windows Slice 4. Slice 5 (away overlay) cut the live write/read path onto the gear analogue `athlete_gear_locale` (`replace_gear_locale` / `load_gear_locales`), leaving `athlete_craft_locale_repo.py` and the `athlete_craft_locale` table with **no live app reader** — only a deploy-time backfill still reads the table to seed `athlete_gear_locale`. 6c-3 deletes the dead module, its tests, and the table.

**Explicitly NOT in scope (the trap the 6c kickoff §4 + every predecessor flagged):** do **NOT** drop the `discipline_baseline_*` craft CSVs. Those are a **live Layer-1 substitution source** (`layer1.builder` reads them) and are a *layer0* surface — re-homing Layer 1 onto `athlete_gear` is a larger cross-layer move, likely its own slice outside #884. 6c-3 touches only the **public-schema** `athlete_craft_locale` table + the dead repo; no layer0 work, no redump-fold.

## 2. Precondition (verify first, like the column-cleanup session did for 6c-1)

The `athlete_craft_locale` table is still read by the init_db backfill that seeds `athlete_gear_locale` (`INSERT INTO athlete_gear_locale … SELECT … FROM athlete_craft_locale`). Dropping the table means removing that backfill — safe only once slice 5's `athlete_gear_locale` **write** path is live in prod (so gear_locale is authoritative and the backfill has run a final time). Slice 5 merged + deployed long ago, so this is almost certainly already met, but confirm the same way the column-cleanup session confirmed 6c-1:
- `git show origin/main:routes/locales.py | grep replace_gear_locale` → the live write path is on gear_locale.
- Vercel `list_deployments` → the slice-5 (or any later) merge is `target: production`, `state: READY`. (Every deploy since has run the table→gear_locale backfill, so `athlete_gear_locale` is fully populated.)

## 3. Mechanically-applicable edits (Rule #11)

### 3.1 Delete `athlete_craft_locale_repo.py` entirely
App-dead module (no live importer — only the test file below imports it). `git rm athlete_craft_locale_repo.py`.

### 3.2 `tests/test_layer4_event_windows.py` — drop the dead-repo import + its test class
- **Remove the import block** (currently lines ~30–35):
  ```python
  from athlete_craft_locale_repo import (
      CraftLocaleError,
      delete_craft_locale,
      load_craft_locales,
      replace_craft_locale,
  )
  ```
- **Remove the whole `TestCraftLocaleRepo` section** — the section comment `# ─── craft↔locale repo (Slice 4, the (b) surface) ───…` through the end of `class TestCraftLocaleRepo` (its last method `test_delete_scoped_to_user_and_locale`), currently lines ~1043–1088. The next section (`# ─── integration: the overlay reaches a full synthesis prompt ───`) is unrelated and stays. (The gear-locale equivalents are covered by the `athlete_gear_repo` tests; nothing is lost.)

### 3.3 `init_db.py` — drop the table (public-schema `_PG_MIGRATIONS`)
Same shape as the just-shipped `brought_craft` column drop. Current line numbers (post-column-cleanup):
- **Remove the table create + index + (b) comment** (currently ~2645–2649):
  ```python
  # (b) craft<->locale: a standing "this craft is kept at this locale"
  # association (a bike at the parents' place). Many-to-many, no per-row
  # attribute → a thin join table; athlete-scoped; locale app-validated against
  # the athlete's locale_profiles (no FK, the no-CHECK convention).
  "CREATE TABLE IF NOT EXISTS athlete_craft_locale ("
  "user_id INTEGER NOT NULL REFERENCES users(id), craft_slug TEXT NOT NULL, "
  "locale TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW(), "
  "PRIMARY KEY (user_id, craft_slug, locale))",
  "CREATE INDEX IF NOT EXISTS idx_acl_user ON athlete_craft_locale(user_id)",
  ```
- **Remove the craft_locale→gear_locale backfill + its comment** (currently ~3122–3126):
  ```python
  # craft↔locale rows migrate 1:1 (craft_slug IS a gear_id), filtered to known slugs.
  f"INSERT INTO athlete_gear_locale (user_id, gear_id, locale) "
  f"SELECT user_id, craft_slug, locale FROM athlete_craft_locale "
  f"WHERE craft_slug IN ({_GEAR_BACKFILL_CRAFT_IN}) "
  f"ON CONFLICT (user_id, gear_id, locale) DO NOTHING",
  ```
  After removing it, check whether `_GEAR_BACKFILL_CRAFT_IN` (defined near the other `_GEAR_BACKFILL_*_IN` constants) still has a user — if this was its only consumer, remove that constant too (clean up your own orphan, surgical rule).
- **Append at the `_PG_MIGRATIONS` tail** (after the `brought_craft` DROP added by the column-cleanup slice):
  ```python
  "DROP TABLE IF EXISTS athlete_craft_locale CASCADE",
  ```
  `IF EXISTS` → re-run safe + a clean no-op on a fresh DB (after the create is removed, the table is never made). Public-schema → auto-applies on each Vercel deploy. **No `layer0-apply` owed.**

### 3.4 Dead doc/comment references (optional scrub — flag, don't pad the diff)
After the module is gone, these name it by string in comments/docstrings only (no runtime effect): `athlete_gear_repo.py` (docstring + the `Mirrors …`/`per …` comments ~lines 8/378/397/429/454), `routes/locales.py:~1041` (a "prior `athlete_craft_locale` write" comment), `layer4/hashing.py:~216`. Scrubbing them makes the retirement clean, but each is a one-line comment touch — keep the diff surgical and decide per the simplicity-first rule. (At minimum, the `athlete_gear_repo.py` docstring "Replaces the two craft repos" framing is worth a pass since one of the two is now deleted.)

## 4. Cache / behavior

- **Behavior-neutral.** No live reader of `athlete_craft_locale` remains; away-segment standing-gear resolution is already on `athlete_gear_locale` (slice 5). Dropping the table changes nothing a plan sees → **no plan-cache invalidation owed.**
- The dead repo carried an `evict_plan_caches_on_craft_locale_change` (layer `"craft_locale"`); it has no live caller, so deleting it evicts nothing that matters. The live path uses `evict_plan_caches_on_gear_locale_change` (layer `"gear_locale"`).

## 5. Verify (Rule #10 targets for the closing handoff)
- `grep -rn athlete_craft_locale` over `*.py` → zero hits (or only any intentionally-kept comment from §3.4).
- `init_db.py` parses; `DROP TABLE IF EXISTS athlete_craft_locale CASCADE` is in `_PG_MIGRATIONS`; the create + backfill are gone.
- `tests/test_layer4_event_windows.py` imports cleanly and the rest of the file's tests pass; run the event-window + gear-locale + builder subset, then the full suite.
- File count: ~2 substantive (`athlete_craft_locale_repo.py` deleted, `init_db.py`) + 1 test + the optional comment scrubs — well under ceiling.
- Owes a **deploy**, not a `layer0-apply` (public-schema).

## 6. Operating notes (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md`. 3. `CARRY_FORWARD.md` (#884 rolling item). 4. This kickoff + the 6c kickoff + the column-cleanup closing + the slice-5 closing + the slice-6 plan. 5. `./scripts/verify-handoff.sh`.

After 6c-3, the only remaining slice-6 item is the deferred per-segment **2C re-resolve** (slice-5 §2) — architectural, its own larger slice.

---

**End of kickoff.**
