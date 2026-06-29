# #884 Unified Gear/Craft Model — Slice 6c (onboarding parity + legacy retirement + deferred `brought_gear` cutover) — Kickoff Handoff v1

**Purpose:** the build recipe for slice 6c, the **last** sub-arc of #884 design-v3 §15. Start on a fresh branch off `main` once the 6b PR (6b-1 + 6b-2) merges.
**Predecessors:** `handoffs/…Slice6b1_StandingPickerGeneralized…` + `handoffs/…Slice6b2_BroughtPickerGeneralized…` (the two picker generalizations; one PR on `claude/slice-6b-cutover-kickoff-od105s`). **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 6c. **Design:** `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §10 (UX/IA), §11 (migration).

---

## 1. Goal & state going in

After 6a/6b the unified gear model is **fully observable**: one "Your gear" surface (6a), and both the standing (6b-1) and brought (6b-2) pickers offer all kinds, so stationed/brought ski/climb gear resolves feasible away (slice-5 plumbing lit). 6c is **cleanup + parity + the one deferred cutover** — no new product capability, three independent pieces. **6c is bigger than the 5-file ceiling → ship as separate sub-PRs (6c-1/6c-2/6c-3), do NOT stack.**

## 2. Piece A — the deferred `brought_craft` → `brought_gear` cutover (6b-2 deferral)

6b-2 generalized the brought picker but **kept storage on `brought_craft`** (the rename ripples ~7 files for a behavior-neutral change; the column drop is 6c's anyway). 6c completes it. **Byte-identical today** (the `brought_gear` column was created + backfilled verbatim from `brought_craft` at `init_db.py:3088/3113`), so no cache churn on the cutover itself.

**Mechanical recipe (Rule #11 — rename the `EventWindow.brought_craft` *attribute* → `brought_gear` and propagate; cut the repo onto the `brought_gear` column):**
- **`athlete_event_windows_repo.py`** — `EventWindow.brought_craft` field decl → `brought_gear`; `_WINDOW_COLUMNS` `"… away_locale, brought_craft, volume_pct …"` → `brought_gear`; `_row_to_window` `brought_craft=tuple(_split_craft(row["brought_craft"]))` → reads `row["brought_gear"]` into `brought_gear=…`; `add_event_window` INSERT column list + the `(",".join(crafts) or None)` slot → write the `brought_gear` column. Keep the `add_event_window` **parameter** named `brought_craft` (it's the form payload; the route passes `brought_craft=request.form.getlist('brought_craft')`) OR rename the form field too — decide once (the form field is `name="brought_craft"` in `event_windows.html`, the draft stash key is `brought_craft` in `routes/profile.py:916`).
- **`layer4/orchestrator.py`** — `:902` `brought_craft=tuple(w.brought_craft)` → `brought_gear=tuple(w.brought_gear)` (constructing `EventWindowOverride`); `:947` `set(away_ov.brought_craft)` → `.brought_gear`.
- **`layer4/session_feasibility.py`** — `:850` `EventWindowOverride.brought_craft` field → `brought_gear`.
- **`layer4/hashing.py`** — `:230` dict key `"brought_craft": sorted(getattr(w, "brought_craft", ()) …)` → `"brought_gear"` + `getattr(w, "brought_gear", …)`; `:255` `tuple(d["brought_craft"])` → `d["brought_gear"]`; update the `:210/:214` doc comments. **Fold key change is byte-identical today** (same data) → no one-time invalidation owed.
- **`layer1/builder.py`** — `:910` `if w.brought_craft:` / `:911` `… {', '.join(w.brought_craft)}` → `w.brought_gear`.
- **Display templates** — `templates/profile/event_windows.html:54` `{% if w.brought_craft %}…{{ w.brought_craft | join(', ') … }}` → `w.brought_gear`; `templates/plan_create/new_form.html:66` same.
- **Tests** — the many `brought_craft=` EventWindow/Override constructor args + the `{"brought_craft": …}` row-dict fixtures + the `_ew(brought_craft=…)` helper rename to `brought_gear` (grep `brought_craft` across `tests/`). The `add_event_window(brought_craft=…)` *call* args stay iff the param name is kept.
- **Column drop (redump-fold, slice-4.3 pattern)** — once nothing reads `brought_craft`, drop the column. It's a **public-schema** column (`athlete_event_windows`, `init_db.py:2611`), not layer0 — so the DROP rides `_PG_MIGRATIONS` (auto-applies on deploy), not `layer0-apply`. Re-backfill `brought_gear` from `brought_craft` is already done (idempotent at `:3113`); add the `ALTER TABLE athlete_event_windows DROP COLUMN IF EXISTS brought_craft` migration **after** the read-cutover deploys. ~7 files → **this is its own sub-PR (6c-1).**

## 3. Piece B — onboarding gear-toggle parity (6c-2)
- `routes/onboarding.py` step 2c.2b captures owned **crafts** via `load_craft_catalog()` → `replace_athlete_crafts` (`templates/onboarding/_crafts_form.html`). It has **no** gear-toggle (ski/snow/climb/alpine) capture — the gap the profile surface closed in 4b/6a. Add toggle parity via the unified registry (mirror the 6a `save_gear` split: `replace_athlete_crafts` + `replace_owned_gear_for_kinds(…, _GEAR_TOGGLE_KINDS)`), so onboarding and profile capture the same kinds. `load_craft_catalog` is still imported by onboarding — generalize or supplement it here. ~3 files.

## 4. Piece C — legacy retirement (6c-3, needs redump coordination)
- **`athlete_craft_locale_repo.py`** is **app-dead** since slice 5 (no non-test importer — slice-5 finding). Retire it + its tests.
- **Legacy craft columns** — `discipline_baseline_*` craft CSVs are still the Layer-1 substitution source (NOT dead — `layer1.builder` reads them); do **not** drop those without re-homing Layer 1 onto `athlete_gear` first (a larger cross-layer move, likely out of #884 scope). The `athlete_craft_locale` table is app-dead (gear-locale replaced it). Coordinate any layer0 drops with a **redump-fold** (don't drop a backfill source before the new baseline stops needing it — the slice-4.3 lesson). Scope this piece carefully; it may warrant its own Layer-0 housekeeping slice.

## 5. Also still in slice 6 (separate, larger)
- **Per-segment 2C re-resolve** (slice-5 §2 / §6.1) — the away equipment pool → strength-substitute pool, deferred from slice 5 ("feasibility now, 2C later"). Needs new synthesis plumbing through `EventWindowSegment`→`per_phase`→`synthesize_phase`. Architectural + over-ceiling → its own slice, not folded into 6c cleanup.

## 6. Gut check
- **Biggest risk:** Piece C — don't drop `discipline_baseline_*` craft CSVs (live Layer-1 source) or any layer0 backfill source ahead of a redump-fold. Piece A's column drop is safe (public schema, re-backfilled, read-cut first).
- **Sequencing:** A (cutover) and B (onboarding) are independent; C is the riskiest and naturally last. Each is its own sub-PR (ceiling).
- **Cache:** Piece A is byte-identical (no invalidation owed). Piece B writes `athlete_gear` → `evict_layer1_on_gear_change` (exists). No new Layer-0 surface in A/B → no 0A/0C digest bump.

## 7. Operating notes (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (6b-2 last-shipped). 3. `CARRY_FORWARD.md` (#884 rolling item). 4. The two 6b closing handoffs + this 6c kickoff + the slice-6 plan + design §10/§11. 5. `./scripts/verify-handoff.sh`.

---

**End of kickoff handoff.**
