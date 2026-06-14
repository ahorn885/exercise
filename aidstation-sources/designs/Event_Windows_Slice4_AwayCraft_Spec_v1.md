# Event Windows — Slice 4: away craft (brought-craft on the away window) — Build Spec v1

**Workstream:** WS-H (issue [#581](https://github.com/ahorn885/exercise/issues/581) Phase H (b)+(c)) — the literal close condition of #581.
**Arc:** `designs/Event_Windows_Design_v1.md` §6 Slice 4 + F4. **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H.
**Predecessors (live):** Slice 1 (#596/#599 subtractive home windows), Slice 2a (#600 away windows + counts-follow-away), Slice 2b (#601 inline-create), Slice 3 (#603 category equipment baselines).
**Status:** DESIGN-FIRST — Trigger #3 (new DDL) + Trigger #5 (a scope re-split: I recommend shipping **craft↔window (c) only** and re-slicing **craft↔locale (b)** to a fast-follow). **No build until §10 sign-off.**
**Date:** 2026-06-14

---

## 1. Purpose + scope

Today an `away` event-window segment resolves the destination's cluster with **`owned_crafts=[]` hard-coded** (`orchestrator.py:738`, F4) — home crafts don't travel, so every away bike/paddle day degrades through the cascade (terrain → indoor → strength → reallocate). That's correct *cold*, but it means an athlete who **brings a craft** to a destination (Andy's packraft in the bag for an away window) still gets no credit for it: D-009 Packrafting away resolves to strength even though they have the boat with them.

**Slice 4 closes #581's stated end state: away `owned_crafts` becomes non-empty when the athlete declares craft availability away.** #581 Phase H names two surfaces:
- **(b) craft↔locale** — a standing association: an owned craft kept at a specific away location (a bike at the parents' place).
- **(c) craft↔window** — brought-craft attached to a specific event window, available at that window's destination for its dates.

**This spec ships (c) — brought-craft on the away window — and recommends deferring (b)** (§5, §10 Fork 1). (c) is the dominant travel case, it's the design's own worked example (§8 test 6: "Packraft ticked onto an away window → D-009 `exact` for those days only"), and it plugs straight into the existing away branch with no new table or per-locale read — keeping the slice within the 5-file ceiling. (b) is a separable, lower-value fast-follow (Slice 4b).

**In scope (c):** a brought-craft set per `away` window → fed as `owned_crafts` to the existing away cascade for that window's date-segment → folded into the plan cache key → captured on the existing `/profile/event-windows` away form.
**Out of scope:** (b) craft↔locale standing associations (Slice 4b, §5); any cascade rewrite (the unified WS-I cascade is reused verbatim); any new craft vocabulary (brought-craft draws from the existing closed `BIKE_TYPES ∪ PADDLE_CRAFT_TYPES` enum).

---

## 2. Boundaries

- **Reuses, does not rewrite, the cascade.** `resolve_craft_terrain_feasibility` already takes `owned_crafts: list[str]` and walks tiers 1–4 (own/proxy craft) before INDOOR→STRENGTH→REALLOCATE. Slice 4 only changes the *value* passed for an away segment — `[]` → the window's brought-craft set. Tiers fire for free.
- **Away-only.** Brought-craft is meaningful only on `away` windows (the destination's env replaces home). `indoor_only` / `locale_unavailable` keep the home env, where the athlete's full owned-craft set already applies (WS-G); a brought-craft value on a non-away window is cleared (mirrors how the repo clears the non-applicable locale field, repo §1).
- **No owned-set gate.** Brought-craft is validated against the **closed craft enum** (`BIKE_TYPES ∪ PADDLE_CRAFT_TYPES`), NOT against the athlete's home craft store — a rented/borrowed craft at the destination is legitimately available away even if not in the home store. The closed-enum check still blocks garbage. (§10 Fork 3 — minor; flag for sign-off.)
- **Counts unchanged.** Slice 2a's counts-follow-away already drives a fully-away week off `away_feasibility`; brought-craft changes *which tier* a discipline lands on inside that same map, not the count machinery. No `session_grid` change.

---

## 3. Data model (DDL — owed Andy's hands, Neon egress blocked)

**One idempotent ALTER**, via the `init_db._PG_MIGRATIONS` pattern (mirrors Slice 2a's `away_locale` add):

```sql
ALTER TABLE athlete_event_windows
  ADD COLUMN IF NOT EXISTS brought_craft TEXT;   -- comma-separated craft slugs; NULL/'' = none brought
```

**Shape decision (Fork 2):** a **comma-separated `TEXT` column**, matching the craft-store convention (`discipline_baseline_cycling.bike_types_available`, `discipline_baseline_paddling.paddle_craft_types`) and the `_split_csv` read shape — *not* a `TEXT[]` and *not* a join table. One window = one row; brought-craft is a per-window attribute, so a join table (`athlete_event_window_crafts`) adds a table + cascade-delete handling + more code for no normalization win at this cardinality (≤ a handful of crafts per window). The closed enum is re-asserted in app code (the project's no-DB-CHECK convention), so the stored string can't leak an unknown slug.

No other schema change. (b)'s `athlete_craft_locale(user_id, craft_slug, locale)` is **not** created here (deferred — §5).

---

## 4. Resolution model — fill the away `owned_crafts` (extends Slice 2a §4)

The away branch in `_build_event_window_overlay` (`orchestrator.py:719-754`) is unchanged except the craft set it passes:

1. `EventWindowOverride` gains `brought_craft: tuple[str, ...] = ()` (frozen dataclass → tuple). The orchestrator builds the raw override from each window with `w.brought_craft` (today: `EventWindowOverride(w.override_type, w.unavailable_locale, w.away_locale)` at `orchestrator.py:709`).
2. In the away segment, the selected `away_ov` (the same override whose `away_locale` anchors `away_cluster`) carries the brought-craft. Replace `owned_crafts=[]` (`orchestrator.py:738`) with **`owned_crafts=list(away_ov.brought_craft)`**. Craft and locale stay consistent — both come from the one chosen away override, so a multi-away-overlap (contradictory: two destinations same day) can't cross a craft from window X onto window Y's cluster.
3. Everything downstream is unchanged: the same `_resolve_included_feasibility` → `resolve_craft_terrain_feasibility` walk runs, now with a non-empty craft set, so a brought packraft makes D-009 resolve via tiers 1–4 (terrain permitting at the destination) instead of falling to strength. `away_feasibility` (the full map Slice 2a feeds the grid for counts-follow-away) reflects it automatically.

**Empty brought-craft (the default) is byte-identical to today** — `list(()) == []`, the existing `owned_crafts=[]` path. This is the no-regression guard (§9 test 1).

---

## 5. Change surface

**Slice 4 (this spec, ≤5 substantive files):**

| # | File | Change |
|---|---|---|
| 1 | `init_db.py` | `_PG_MIGRATIONS` idempotent `ALTER … ADD COLUMN IF NOT EXISTS brought_craft TEXT` (DDL owed Andy's hands on Neon, apply-before-merge like Slice 2a/3). |
| 2 | `athlete_event_windows_repo.py` | `EventWindow.brought_craft: tuple[str, ...]`; `load_event_windows` splits the CSV; `add_event_window(..., brought_craft=None)` validates each slug against `BIKE_TYPES ∪ PADDLE_CRAFT_TYPES` (raise `EventWindowError` on unknown), stores **only when `override_type == 'away'`** else clears (mirrors the locale-clear logic). Reuse the `athlete_crafts_repo._validate` enum-order/dedupe shape for a stable stored string. |
| 3 | `layer4/session_feasibility.py` | `EventWindowOverride.brought_craft: tuple[str, ...] = ()`. |
| 4 | `layer4/orchestrator.py` | build the override with `w.brought_craft`; away branch `owned_crafts=list(away_ov.brought_craft)`; update the existing Rule #15 `_away_dbg` line to print the real set (`owned_crafts={sorted(...)}`) instead of the literal `[]`. |
| 5 | `routes/profile.py` + `templates/profile/event_windows.html` | brought-craft multi-select (checkboxes from `load_craft_catalog()`, shown for the away override), threaded through `add_event_window_route` via `request.form.getlist('brought_craft')`; `event_windows()` passes the catalog. (UI counted as one, per the WS-H slice precedent.) |

**Thin mechanical (mirror of an existing one-field pattern, not counted — Slice 2a precedent):**
- `layer4/hashing.py` — `compute_event_windows_hash` adds `brought_craft` to the per-window flattened dict + sort key, so a brought-craft edit busts `plan_create_key` / `plan_refresh_key`. One-field add to the existing `away_locale` pattern.

**+ tests** (`tests/test_layer4_event_windows.py` + repo tests — not counted).

**Slice 4b (DEFERRED — its own PR, pending Fork 1):** craft↔locale (b) — new `athlete_craft_locale(user_id, craft_slug, locale)` table + a small repo + a per-locale read that **unions** standing-craft for any locale in `away_cluster` into the away `owned_crafts` (alongside the brought set) + capture UI. Separable: it's additive to the same `owned_crafts=list(...)` line. Filed as a sub-issue of #581 if Andy keeps (b).

---

## 6. Caching

`brought_craft` is a **declared window input**, not a derived resolution, so it belongs in `compute_event_windows_hash` exactly like `override_type` / `away_locale` (the away destination's *equipment/terrain* edits already evict via the locale-edit path + `compute_terrain_feasibility_hash`; this hash covers the window's own declared fields). Folding it in means: tick a packraft onto an away window → hash changes → the plan re-synthesizes the overlapping window only (Slice 1's overlap-scoped eviction). No-brought-craft windows leave the digest unchanged → no spurious cold re-synth. The repo's `evict_plan_caches_on_event_windows_change` (already called on add/delete) covers the write path unchanged.

---

## 7. Rule #15 logging + Trigger-#1 wording

- **Rule #15:** the away branch already prints `event_window_overlay: … owned_crafts=[] …`. Slice 4 makes that line carry the real decided input — `owned_crafts={sorted(list(away_ov.brought_craft))}` — so a surprising away bike/paddle day ("why did D-009 still land on strength?") is diagnosable from logs alone (brought nothing? brought it but the destination cluster has no compatible terrain?). No new log site; the existing one becomes honest.
- **Trigger #1 (synthesis wording) — OPTIONAL, flagged, NOT in this slice's required surface.** The brought-craft already shows up implicitly: the changed-discipline resolution (D-009 strength→exact) renders in the existing overlay. A *explicit* "you brought your packraft for these days" line in `per_phase._format_event_window_overlay` would be a nicety but is new synthesis copy → Trigger #1 sign-off. Recommend **deferring the explicit line**; the resolution diff already communicates the effect. If Andy wants the explicit mention, it's a one-line wording add at build time with sign-off.

---

## 8. Edge cases

1. **Empty brought-craft (default)** → `owned_crafts=[]`, byte-identical to today. *Regression guard.*
2. **Brought a craft the destination can't use** (packraft but the away cluster has no water terrain) → cascade tiers 1–4 miss on terrain, walk degrades to INDOOR/STRENGTH — same as cold, correctly (you brought it but can't ride it here). The Rule #15 line shows the craft was present, so the strength landing reads as terrain-gated, not craft-absent.
3. **Brought-craft on a non-away window** (form misuse / stale field) → repo clears it (away-only), so it can't imply availability on a home-env window where the full owned set already applies.
4. **Unknown slug** (crafted POST) → `EventWindowError`, nothing written (closed-enum validation).
5. **Two overlapping away windows** (contradictory) → the away branch already picks one `away_ov`; brought-craft comes from that same override, so locale and craft never cross. (Repo-level prevention of overlapping away windows is out of scope.)
6. **Brought craft = a proxy** (gravel_bike brought, destination has trail → D-008 MTB) → tiers 3/4 proxy logic fires unchanged; the swap/proxy overlay renders as it does at home.

---

## 9. Test scenarios (`tests/test_layer4_event_windows.py` + repo)

1. **No brought-craft away window** → away segment resolves identical to the current `owned_crafts=[]` path. *Byte-identical regression guard.*
2. **Packraft brought onto an away window** whose destination cluster has water terrain → D-009 resolves `exact`/own-craft tier for those dates only; non-away dates unchanged. *(The design's worked example.)*
3. **Brought craft, destination has no compatible terrain** → still degrades to indoor/strength; Rule #15 line shows the craft was in the set (terrain-gated, not craft-absent).
4. **`compute_event_windows_hash` changes** when a window's `brought_craft` changes; **unchanged** when it doesn't — and a no-brought-craft window set hashes byte-identical to pre-Slice-4.
5. **Repo:** brought-craft stored only on `away`; cleared on `indoor_only`/`locale_unavailable`; unknown slug → `EventWindowError`, no write; CSV round-trips through `load_event_windows` in enum order.
6. **Proxy brought-craft** (gravel_bike → trail D-008) → proxy tier fires; swap overlay renders.

Run the full `tests/` (the circular-import quirk on isolated collection — CLAUDE.md env note).

---

## 10. Open items / sign-off

**Triggers tripped:** #3 (new DDL — the `brought_craft` ALTER) + #5 (the (c)-only scope re-split below). DDL is owed Andy's hands (apply-before-merge like Slice 2a/3).

**Fork 1 — scope (the load-bearing decision).** #581's stated close condition is craft↔locale **∪** craft↔window. Both in one slice is ~7 files (new table + repo + per-locale read + window carrier + cascade wire + 2 capture UIs) — over the ceiling.
- **Recommendation: ship (c) brought-craft now (Slice 4); re-slice (b) craft↔locale to Slice 4b** (a small, additive fast-follow — it unions standing per-locale craft into the same `owned_crafts` line). Delivers the headline travel case (the packraft example) within the ceiling and de-risks (b) behind a proven (c).
- **Alternative:** do both now and accept a 2-over-ceiling slice (WS-B/C precedent exists). I don't recommend it — (b) carries a new table + its own capture, which is a clean independent vertical, and the ceiling exists precisely to avoid this.
- **Or:** if (b) standing-craft isn't worth a surface at all (brought-craft per window can cover "I keep a bike there" by re-declaring each visit), **drop (b)** and close #581 on (c) alone. Your call on whether the standing association earns its table.

**Fork 2 — window craft carrier shape.** Recommend a **comma-separated `TEXT brought_craft` column** on `athlete_event_windows` (matches the craft-store CSV convention, one ALTER, no join). Alternative: a `athlete_event_window_crafts` join table (normalized, more code, no win at this cardinality). Recommend the column.

**Fork 3 — validation target (minor).** Recommend validating brought-craft against the **closed craft enum only**, not the athlete's owned home set (allows a rental/borrowed craft away; closed-enum still blocks garbage). Flag if you'd rather gate to owned-only.

**Deferred to build (no sign-off needed now):** the Trigger-#1 explicit "you brought X" overlay line (§7) — recommend skipping; the resolution diff already conveys it.

---

## 11. Gut check

- **This is the smallest honest close of #581.** The away branch was *built* to take a craft set (Slice 2a left `owned_crafts=[]` as the explicit F4 placeholder with a comment naming Slice 4); Slice 4 (c) is almost entirely "stop passing `[]`." The risk surface is the capture/validation + the cache fold, both of which mirror patterns already in the repo (the craft store's enum validation, Slice 2a's `away_locale` hash fold). Low risk.
- **Biggest judgement call is Fork 1.** If you want #581 closed on the literal union, say so and I'll spec (b) into 4a/4b sequencing; otherwise (c)-now is the lean path and (b) earns its own issue.
- **Best argument against (c)-only:** an athlete who *always* keeps a craft at a second home will re-tick it on every window — mildly annoying. That's exactly what (b) standing-craft fixes, which is why it's a fast-follow, not a drop, unless you judge the case too rare to model.
- **No vocabulary risk:** brought-craft draws from the existing closed `BIKE_TYPES ∪ PADDLE_CRAFT_TYPES` — no padding, no new craft entries (Trigger #2 not tripped).
- **No-regression is cheap and provable:** empty brought-craft is `list(()) == []`, so the whole away path is byte-identical until a craft is actually declared — test 1 pins it.
