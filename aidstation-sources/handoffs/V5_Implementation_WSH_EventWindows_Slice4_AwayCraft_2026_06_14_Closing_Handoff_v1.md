# V5 Implementation — WS-H: Event Windows — Slice 4: away craft (brought-craft + craft↔locale) — Closing Handoff

**Session:** Built + merged **Slice 4** of the Event-Windows arc — **away craft** (design §F4; #581 Phase H (b)+(c), the epic's literal close condition). The away segment's `owned_crafts`, hard-coded `[]` since Slice 2a (the F4 placeholder), now fills from two declared surfaces — **(c)** brought-craft on the away window ∪ **(b)** standing craft kept at a locale in the destination cluster — fed to the existing unified cascade. A brought/kept packraft now resolves D-009 via the craft tiers instead of degrading to strength. **#581 closed.**
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice3_CategoryBaselines_2026_06_14_Closing_Handoff_v1.md` (Slice 3 category baselines, PR #603 merged + live).
**Branch:** `claude/604-migration-xsqcb3` (PR [#605](https://github.com/ahorn885/exercise/pull/605) — **squash-merged to `main` 2026-06-14, CI green**). *(Harness-pinned branch named for the 604 migration; that migration's `pg_dump` is owed-Andy's-hands (Neon egress blocked), so the session pivoted to Slice 4 per Andy's `AskUserQuestion` choice. Branch kept per the "never push to a different branch" instruction.)*
**Spec/arc:** `designs/Event_Windows_Slice4_AwayCraft_Spec_v1.md` (build-ready, ratified) + `designs/Event_Windows_Design_v1.md` §F4/§6. **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. **Epic:** [#581](https://github.com/ahorn885/exercise/issues/581) (**closed completed**).

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the Slice-3 handoff — all green, tree clean, branch correct, §8 anchors on disk. No drift; Slice 3 genuinely merged + live.

## 2. The 604 blocker + the pivot

#604 (vocab single-source-of-truth) needs a `pg_dump` of live `layer0` from Neon — blocked from the container (egress). Confirmed the *unblocked* remainder (retiring the stale `etl/sources/populate_equipment_items_*.sql` scaffolding) is real but gated by Rule #12 sign-off + a destination collision (older differing K/K2 copies already in `aidstation-sources/archive/etl-scratch/migrations/`) + `run_owed_layer0_migrations.sql`'s live `\ir`. Surfaced via `AskUserQuestion`; **Andy chose "pivot to Slice 4."**

## 3. Decisions (Andy-ratified in-session, 2026-06-14)

Slice 4 trips **Trigger #3** (new DDL) + **Trigger #5** (a scope re-split I proposed). Wrote the spec, surfaced three forks, got sign-off, then built:
1. **Scope** — I recommended (c)-only-now + (b)-fast-follow to stay within the ceiling. **Andy: "both in one slice"** (over the 5-file ceiling, accepted — WS-B/C precedent).
2. **Carrier shape** — CSV `TEXT brought_craft` column for (c) + a `athlete_craft_locale` join table for (b). *(agreed)*
3. **Validation** — against the closed `BIKE_TYPES ∪ PADDLE_CRAFT_TYPES` enum, not the owned-home set (a rented/borrowed/kept-there craft is legitimately available away). *(agreed)*

## 4. Implementation (all merged in #605)

- **`init_db.py`** — `_PG_MIGRATIONS`: `ALTER athlete_event_windows ADD COLUMN IF NOT EXISTS brought_craft TEXT` + `CREATE TABLE IF NOT EXISTS athlete_craft_locale(user_id, craft_slug, locale, created_at, PK(user_id,craft_slug,locale))` + `idx_acl_user`. **APPLIED on Neon (Andy 2026-06-14)** → merged.
- **`athlete_event_windows_repo.py`** — `EventWindow.brought_craft: tuple[str,...]`; load splits the CSV; `add_event_window(..., brought_craft=None)` validates each slug against `_CRAFT_SLUGS` (= `BIKE_TYPES + PADDLE_CRAFT_TYPES`) + stores **only when `override_type=='away'`** (cleared otherwise); `_split_craft`/`_validate_crafts` mirror `athlete_crafts_repo`.
- **`athlete_craft_locale_repo.py` (NEW)** — `load_craft_locales → {locale:[slug]}`; `replace_craft_locale` (replace-all per locale, validate enum + `_locale_exists`); `delete_craft_locale`; `evict_plan_caches_on_craft_locale_change` (plan_create+plan_refresh).
- **`layer4/session_feasibility.py`** — `EventWindowOverride.brought_craft: tuple[str,...] = ()`.
- **`layer4/orchestrator.py`** — `_build_event_window_overlay` loads `craft_locale_map = load_craft_locales(...)` once (covers create + refresh call sites); builds the override with `w.brought_craft`; away branch `away_crafts = sorted(set(away_ov.brought_craft) | {c for loc in away_cluster for c in craft_locale_map.get(loc, ())})` → passed as `owned_crafts`; Rule #15 `_away_dbg` now prints `owned_crafts={…} (brought={…} standing={…})`.
- **`layer4/hashing.py`** — `compute_event_windows_hash` folds `brought_craft` into the per-window dict + sort key (the (c) window field).
- **`layer4/per_phase.py`** — `_event_window_label` dropped the now-false hard-coded `; no brought craft` clause → `"…that location's terrain/equipment + any craft you have there"` (the per-discipline resolution diff conveys the actual craft effect). **Correctness fix to previously-approved Trigger-#1 wording — flagged.**
- **`routes/profile.py` + `templates/profile/event_windows.html`** — (c) brought-craft multi-select on the away window (`request.form.getlist('brought_craft')`); (b) "Craft you keep at a location" section (`save_craft_locale_route`/`delete_craft_locale_route`); `event_windows()` passes `load_craft_catalog()` + `load_craft_locales()`.

**Cache model:** (c) brought_craft → in `compute_event_windows_hash` (declared window field, like `away_locale`); (b) craft↔locale → **eviction-on-write only** (`evict_plan_caches_on_craft_locale_change`), NOT a content hash — mirrors how home `owned_crafts` (a Layer-1 field) is covered by Layer-1 eviction, not a plan hash. **Empty union is byte-identical to the Slice-2a `owned_crafts=[]` path.**

## 5. Tests

- **`tests/test_layer4_event_windows.py`** +15: `TestAwayCraft` (brought passed as owned_crafts; standing-at-cluster-locale unioned; brought∪standing dedup+sorted; standing-outside-cluster excluded; empty-union byte-identical — via a spy on `_resolve_included_feasibility`); brought-craft hash change; repo (c) (away stores enum-ordered CSV, rejects unknown slug, non-away clears); `TestCraftLocaleRepo` (b) (load grouping, foreign-locale + unknown-slug rejection, delete-then-insert enum order, empty clears, scoped delete). Updated the two `_patch` helpers to stub `load_craft_locales`, the away-label render assertion, and the Slice-2b render-smoke to pass `craft_catalog`/`craft_locales`.
- **Full suite: 2467 passed / 30 skipped.** All touched modules byte-compile. Layer-0 gate untouched (the new table is an app migration, not a layer0 one).

## 6. Owed Andy's hands

- ✅ **DDL APPLIED on Neon (Andy 2026-06-14)** — the `brought_craft` ALTER + `athlete_craft_locale` table. Was the only pre-merge blocker; cleared → #605 merged.
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

## 7. Next session

- **Slice 5 — capture UX polish** (the arc's last slice): nav-link to `/profile/event-windows`; the plan-gen review/edit/append panel (F1); moving the (b) craft↔locale capture from the event-windows page to the **locale page** (it's a locale property — I parked it on event-windows this slice to avoid touching `routes/locales.py`; repo + resolution don't change); the 2b round-trip form-state preservation.
- **#604 — vocab single-source-of-truth** (still owed the `pg_dump` from live; the unblocked scaffolding-retirement needs a Rule #12 sign-off on the archive move + resolving the K/K2 archive-name collision + `run_owed_layer0_migrations.sql`'s `\ir`).
- (split out) #592 race-location terrain/weather; #593 reduced-volume travel days.

### 7.1 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — WS-H block. 4. This handoff. 5. `designs/Event_Windows_Design_v1.md` §F4/§6 + `designs/Event_Windows_Slice4_AwayCraft_Spec_v1.md`. 6. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| DDL | `init_db.py` | `ADD COLUMN IF NOT EXISTS brought_craft TEXT`; `CREATE TABLE IF NOT EXISTS athlete_craft_locale` + `idx_acl_user` |
| Brought-craft repo (c) | `athlete_event_windows_repo.py` | `EventWindow.brought_craft`; `_validate_crafts`; `brought_craft` stored only when `override_type=='away'` |
| Craft↔locale repo (b) | `athlete_craft_locale_repo.py` | `load_craft_locales`; `replace_craft_locale`; `evict_plan_caches_on_craft_locale_change` |
| Override field | `layer4/session_feasibility.py` | `EventWindowOverride.brought_craft: tuple[str, ...] = ()` |
| Union resolution | `layer4/orchestrator.py` | `load_craft_locales` in `_build_event_window_overlay`; away `owned_crafts = sorted(brought \| standing)`; `_away_dbg` prints `(brought=… standing=…)` |
| Cache | `layer4/hashing.py` | `"brought_craft"` in `compute_event_windows_hash` |
| Overlay wording | `layer4/per_phase.py` | `_event_window_label` away clause = "any craft you have there" (no "no brought craft") |
| Capture UI | `routes/profile.py`, `templates/profile/event_windows.html` | `brought_craft` getlist; `save_craft_locale_route`; `name="craft_slug"` + `crafts-at-locale` |
| Tests | `tests/test_layer4_event_windows.py` | `TestAwayCraft` (5) + `TestCraftLocaleRepo` (6) + brought-craft repo/hash (4) |
| Suite | — | 2467 passed / 30 skipped |
| Merge | — | PR #605 squash-merged to `main`, CI green; DDL applied on Neon before merge; #581 closed completed |
