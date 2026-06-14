# Event Windows — Slice 4: away craft (brought-craft + craft↔locale) — Build Spec v1

**Workstream:** WS-H (issue [#581](https://github.com/ahorn885/exercise/issues/581) Phase H (b)+(c)) — the literal close condition of #581.
**Arc:** `designs/Event_Windows_Design_v1.md` §6 Slice 4 + F4. **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H.
**Predecessors (live):** Slice 1 (#596/#599 subtractive home windows), Slice 2a (#600 away windows + counts-follow-away), Slice 2b (#601 inline-create), Slice 3 (#603 category equipment baselines).
**Status:** BUILD-READY — forks ratified (Andy 2026-06-14): **both (b)+(c) in one slice**; CSV `TEXT` carrier; validate against the closed craft enum. Trigger #3 (new DDL) — DDL owed Andy's hands on Neon, apply-before-merge (like Slices 2a/3). **Over the 5-file ceiling, accepted by Andy** (WS-B/C precedent).
**Date:** 2026-06-14

---

## 1. Purpose + scope

Today an `away` event-window segment resolves the destination's cluster with **`owned_crafts=[]` hard-coded** (`orchestrator.py:738`, the F4 placeholder Slice 2a left with a comment naming Slice 4) — home crafts don't travel, so every away bike/paddle day degrades through the cascade (terrain → indoor → strength → reallocate). Correct *cold*, but an athlete who has a craft available away (brought it, or keeps one there) gets no credit: D-009 Packrafting away resolves to strength even with the boat on hand.

**Slice 4 closes #581's stated end state — away `owned_crafts` becomes non-empty via the two declared surfaces:**
- **(c) craft↔window** — brought-craft attached to a specific `away` event window; available at that window's destination for its dates (the dominant travel case — the design's worked example, §9 test 2).
- **(b) craft↔locale** — a standing association: an owned craft kept at a specific locale (a bike at the parents' place); available whenever that locale is in the active away cluster, no per-trip re-declaration.

The away cluster's `owned_crafts` = **`brought_craft(window) ∪ standing_craft(locale ∈ away_cluster)`**.

**In scope:** both surfaces; the union fed to the existing away cascade; cache correctness; capture on `/profile/event-windows`.
**Out of scope:** any cascade rewrite (the unified WS-I cascade is reused verbatim — Slice 4 only changes the craft *set* passed for an away segment); any new craft vocabulary (both surfaces draw from the closed `BIKE_TYPES ∪ PADDLE_CRAFT_TYPES` enum — no padding, Trigger #2 untripped); the plan-gen review-panel hook + onboarding capture (Slice 5 polish).

---

## 2. Boundaries

- **Reuses, does not rewrite, the cascade.** `resolve_craft_terrain_feasibility` already takes `owned_crafts: list[str]` and walks tiers 1–4 (own/proxy craft) before INDOOR→STRENGTH→REALLOCATE. Slice 4 only changes the *value* for an away segment — `[]` → the brought ∪ standing union. Tiers fire for free.
- **Away-only.** Craft availability away is meaningful only on `away` windows (the destination's env replaces home). `indoor_only` / `locale_unavailable` keep the home env, where the athlete's full owned-craft set already applies (WS-G). Brought-craft on a non-away window is cleared (mirrors the repo's locale-clear).
- **No owned-set gate.** Both surfaces validate against the **closed craft enum** (`BIKE_TYPES ∪ PADDLE_CRAFT_TYPES`), NOT the athlete's home store — a rented/borrowed/kept-there craft is legitimately available away even if not in the home store. The closed-enum check still blocks garbage.
- **Counts unchanged.** Slice 2a's counts-follow-away drives a fully-away week off `away_feasibility`; the craft union changes *which tier* a discipline lands on inside that same map, not the count machinery. No `session_grid` change.

---

## 3. Data model (DDL — owed Andy's hands, Neon egress blocked)

Two idempotent statements via the `init_db._PG_MIGRATIONS` pattern:

```sql
-- (c) craft↔window: brought-craft on the away window. Comma-separated craft slugs;
--     NULL/'' = none brought. Mirrors discipline_baseline_*.{bike_types_available,
--     paddle_craft_types} CSV convention + the _split_csv read shape.
ALTER TABLE athlete_event_windows
  ADD COLUMN IF NOT EXISTS brought_craft TEXT;

-- (b) craft↔locale: a standing "this craft is kept at this locale" association.
--     One row per (craft, locale); athlete-scoped. locale references the athlete's
--     own locale_profiles.locale (app-validated, no FK — the no-DB-CHECK convention).
CREATE TABLE IF NOT EXISTS athlete_craft_locale (
  user_id     INTEGER NOT NULL,
  craft_slug  TEXT    NOT NULL,
  locale      TEXT    NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, craft_slug, locale)
);
```

**Shape (ratified Fork 2):** brought-craft is a **comma-separated `TEXT` column** (one window = one row; the closed enum is re-asserted in app code, so no unknown slug leaks). craft↔locale is a thin **join table** because it's a many-to-many (a craft at several locales, a locale holding several crafts) with no per-row attributes — the natural normalized shape; replace-all-per-locale on write keeps it simple.

---

## 4. Resolution model — fill the away `owned_crafts` (extends Slice 2a §4)

`_build_event_window_overlay` (`orchestrator.py:668`) loads the athlete's craft↔locale map **once** before the segment loop (covers both the create and refresh call sites — they share this builder). The away branch (`orchestrator.py:719-754`) changes only the craft set it passes:

1. `EventWindowOverride` gains `brought_craft: tuple[str, ...] = ()` (frozen dataclass → tuple). The orchestrator builds the raw override with `w.brought_craft` (today: `EventWindowOverride(w.override_type, w.unavailable_locale, w.away_locale)` at `orchestrator.py:709`).
2. In the away segment, compute the union and replace `owned_crafts=[]` (`orchestrator.py:738`):
   ```python
   brought = set(away_ov.brought_craft)                       # (c)
   standing = {c for loc in away_cluster for c in craft_locale_map.get(loc, ())}  # (b)
   owned_crafts = sorted(brought | standing)
   ```
   `away_cluster` is the destination's radius cluster already resolved on the line above; `craft_locale_map` is `{locale: [craft_slug, ...]}` loaded once. Craft and locale stay consistent — both brought and standing are scoped to the one chosen away override's destination cluster.
3. Downstream is unchanged: the same `_resolve_included_feasibility` → `resolve_craft_terrain_feasibility` walk runs with a non-empty craft set, so an available packraft makes D-009 resolve via tiers 1–4 (terrain permitting at the destination) instead of strength. `away_feasibility` (the full map Slice 2a feeds the grid for counts-follow-away) reflects it automatically.

**Empty union (the default) is byte-identical to today** — no brought-craft, no standing craft at the cluster's locales → `sorted(set()) == []`, the existing `owned_crafts=[]` path. No-regression guard (§9 test 1).

---

## 5. Change surface (over the 5-file ceiling — accepted by Andy 2026-06-14)

| # | File | Change |
|---|---|---|
| 1 | `init_db.py` | `_PG_MIGRATIONS`: idempotent `ALTER … ADD COLUMN IF NOT EXISTS brought_craft TEXT` + `CREATE TABLE IF NOT EXISTS athlete_craft_locale`. DDL owed Andy's hands on Neon, apply-before-merge. |
| 2 | `athlete_event_windows_repo.py` | `EventWindow.brought_craft: tuple[str, ...]`; `load_event_windows` splits the CSV; `add_event_window(..., brought_craft=None)` validates each slug against the closed enum, stores **only when `override_type == 'away'`** else clears. |
| 3 | `athlete_craft_locale_repo.py` (NEW) | `load_craft_locales(db, user_id) -> dict[str, list[str]]` ({locale: [slug]}); `replace_craft_locale(db, user_id, locale, crafts)` (replace-all per locale, validate enum + `_locale_exists`); `delete_craft_locale(db, user_id, locale)`; `evict_plan_caches_on_craft_locale_change` (plan_create + plan_refresh, mirrors the windows repo's eviction). |
| 4 | `layer4/session_feasibility.py` | `EventWindowOverride.brought_craft: tuple[str, ...] = ()`. |
| 5 | `layer4/orchestrator.py` | load `craft_locale_map` once in `_build_event_window_overlay`; build the override with `w.brought_craft`; away branch `owned_crafts = sorted(brought ∪ standing)`; update the Rule #15 `_away_dbg` line to print the real set + its `(brought=…, standing=…)` provenance. |
| 6 | `routes/profile.py` + `templates/profile/event_windows.html` | (c) brought-craft multi-select on the away window (checkboxes from `load_craft_catalog()`, threaded via `request.form.getlist('brought_craft')`); (b) a "Crafts you keep at a location" section (pick locale + check crafts → `replace_craft_locale`; list + delete). `event_windows()` passes the catalog + the current craft↔locale map. (Capture lives here, not on the locale page, to avoid touching `routes/locales.py`; the plan-gen review-panel + locale-page home are Slice-5 polish.) |

**Thin mechanical (mirror of the existing one-field pattern, not counted — Slice 2a precedent):**
- `layer4/hashing.py` — `compute_event_windows_hash` adds `brought_craft` to the per-window flattened dict + sort key (the (c) window field, consistent with `away_locale`).

**+ tests** (`tests/test_layer4_event_windows.py` + repo tests — not counted).

---

## 6. Caching

- **(c) brought_craft** is a **declared window field**, so it folds into `compute_event_windows_hash` exactly like `override_type`/`away_locale` — tick a packraft onto an away window → hash changes → the overlapping window re-synthesizes (Slice 1's overlap-scoped eviction). No-brought-craft windows leave the digest unchanged. The window add/delete path already calls `evict_plan_caches_on_event_windows_change`.
- **(b) craft↔locale** is **athlete-level standing data, not a window field** — so it is covered by **eviction-on-write** (`evict_plan_caches_on_craft_locale_change`, scoped to plan_create/plan_refresh), **NOT** a content hash. This mirrors how home `owned_crafts` works: the craft store is a Layer-1 field covered by `evict_layer1_on_crafts_change`, not folded into a plan content hash. Since every (b) write is user-scoped and evicts, two different (b) states can never collide on a stale key. (Folding (b)'s away-cluster subset into the hash would require resolving clusters at hash time for no correctness gain — explicitly avoided.)

---

## 7. Rule #15 logging + Trigger-#1 wording

- **Rule #15:** the away branch already prints `event_window_overlay: … owned_crafts=[] …`. Slice 4 makes it carry the decided input with provenance — `owned_crafts={sorted(union)} (brought={…} standing={…} away_cluster=[…])` — so a surprising away bike/paddle day is diagnosable from logs alone (brought nothing? kept it elsewhere? brought it but the cluster has no compatible terrain?). No new log site; the existing one becomes honest.
- **Trigger #1 (synthesis wording) — OPTIONAL, deferred.** The available craft already shows implicitly via the changed-discipline resolution (D-009 strength→exact) the existing overlay renders. An explicit "you have your packraft for these days" line would be new synthesis copy → Trigger-#1 sign-off; recommend skipping (the resolution diff conveys it). One-line add at build time if Andy wants it.

---

## 8. Edge cases

1. **Empty union (default)** → `owned_crafts=[]`, byte-identical to today. *Regression guard.*
2. **Craft available but the destination can't use it** (packraft, no water terrain in the away cluster) → tiers 1–4 miss on terrain, degrade to INDOOR/STRENGTH — correct (have it, can't ride it here). Rule #15 shows the craft was present → reads as terrain-gated, not craft-absent.
3. **Brought-craft on a non-away window** → repo clears it (away-only).
4. **Unknown slug** (crafted POST, either surface) → repo raises, nothing written (closed-enum validation).
5. **Standing craft at a locale not in the away cluster** → excluded (the union filters by `loc ∈ away_cluster`); a craft kept at home locale L is irrelevant to an away destination whose cluster doesn't include L.
6. **Same craft brought AND kept at the destination** → `set` union dedupes.
7. **Two overlapping away windows** (contradictory) → the away branch picks one `away_ov`; brought comes from that override, standing from that override's cluster — locale/craft never cross.
8. **craft↔locale row for a deleted locale** → `replace_craft_locale` validates `_locale_exists` on write; a locale deleted later leaves an orphan row that simply never matches an away cluster (harmless). Optional: locale-delete cascades — out of scope (Slice 5).

---

## 9. Test scenarios (`tests/test_layer4_event_windows.py` + repo)

1. **No craft available away** → away segment resolves identical to the current `owned_crafts=[]` path. *Byte-identical regression guard.*
2. **(c) Packraft brought onto an away window** whose destination cluster has water terrain → D-009 `exact`/own-craft tier for those dates only; non-away dates unchanged. *(The design's worked example.)*
3. **(b) Mountain bike kept at the away destination's locale** (craft↔locale) → D-008 resolves via craft for an away window there, no per-window declaration.
4. **(b ∪ c) union** → brought packraft + standing MTB at the cluster → both disciplines resolve via craft; `set` dedupes a craft that's both.
5. **Available craft, no compatible terrain** → degrades to indoor/strength; Rule #15 shows the craft in the set.
6. **`compute_event_windows_hash`** changes when a window's `brought_craft` changes; unchanged otherwise; a no-brought-craft window set hashes byte-identical to pre-Slice-4 *(for the no-overlapping-windows → '' case)*.
7. **Repo (c):** brought-craft stored only on `away`; cleared on `indoor_only`/`locale_unavailable`; unknown slug → `EventWindowError`, no write; CSV round-trips in enum order.
8. **Repo (b):** `replace_craft_locale` rejects unknown slug + non-existent locale (nothing written); replace-all semantics per locale; `load_craft_locales` shape; delete.
9. **Proxy craft available** (gravel_bike → trail D-008) → proxy tier fires; swap overlay renders.

Run the full `tests/` (the isolated-collection circular-import quirk — CLAUDE.md env note).

---

## 10. Open items / sign-off

**Ratified (Andy 2026-06-14):** Fork 1 — **both (b)+(c) in one slice** (over the ceiling, accepted); Fork 2 — CSV `TEXT brought_craft` for (c) + a join table for (b); Fork 3 — validate against the closed craft enum (not owned-only).
**Owed Andy's hands:** the two DDL statements (§3) on Neon, apply-before-merge.
**Deferred (no sign-off needed):** the Trigger-#1 explicit-craft overlay line (§7); locale-delete cascade for orphan craft↔locale rows (§8.8); moving (b)'s capture to the locale page / plan-gen review panel (Slice 5).

---

## 11. Gut check

- **This is the honest close of #581** — the away branch was built to take a craft set; (c) is "stop passing `[]`," (b) adds a standing union into the same line. Low resolution risk: the cascade is untouched.
- **Cost of "both" is the file count + (b)'s capture/eviction surface**, not resolution complexity. The over-ceiling is real but each file's change is small and mirrors an existing pattern (the craft store's enum validation; Slice 2a's `away_locale` hash fold; the windows repo's eviction). Accepted by Andy; flagged here so the next `simplify` pass can eyeball it.
- **Best argument against (b) the way it's scoped:** capturing a standing per-locale craft on the *event-windows* page is a slight UX stretch (it's a locale property, not a window). I chose it to avoid touching `routes/locales.py`; if it reads wrong in use, Slice 5 moves it to the locale page cheaply (the repo + resolution don't change).
- **No vocabulary risk / no-regression is provable:** both surfaces draw from the closed enum; empty union is `sorted(set()) == []`, so the whole away path is byte-identical until a craft is actually declared — test 1 pins it.
