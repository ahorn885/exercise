# #884 Unified Gear/Craft Model — Slice 6c-1 (brought-gear read+write cutover, `brought_craft`→`brought_gear`) — Closing Handoff v1

**Session:** 2026-06-30 · branch `claude/onboarding-parity-legacy-retire-vyprwg` · commit `be0f327` · PR not yet opened (push + bookkeep + wait for Andy's go).
**Kickoff:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6c_OnboardingParityLegacyRetire_2026_06_29_Kickoff_Handoff_v1.md` §2. **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 6c. **Design:** §10 (UX/IA), §11 (migration). **Predecessor:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6b2_BroughtPickerGeneralized_2026_06_29_Closing_Handoff_v1.md` (6b-2 — brought picker generalized; deferred this rename here).

---

## 1. Session narrative — Piece A of slice 6c (the deferred cutover)

Slice 6c is **cleanup + parity + the one deferred cutover** — three independent pieces, each its own sub-PR, **do NOT stack** (kickoff §1). This session shipped **Piece A = 6c-1**: the `brought_craft`→`brought_gear` cutover that 6b-2 deferred.

6b-2 generalized the brought (event-window) picker to all gear kinds but **kept storage on the legacy `brought_craft` field/column** (the rename ripples ~7 files for a behavior-neutral change; the column drop was 6c's anyway). 6c-1 completes it: the `EventWindow.brought_craft` **attribute is renamed → `brought_gear`** and the repo's **read + write** are cut onto the `brought_gear` column (created + backfilled 1:1 verbatim from `brought_craft` at `init_db.py:3088/3113`). Per Andy's call (2026-06-30) the rename is **full** — model attr, repo, layer4 reads, the event-windows **form field** (`name="brought_gear"`) + route getlist + draft-stash key, and both display templates — leaving zero `brought_craft` in live code except one deliberate, documented digest-stability tombstone (see §3 deviation 1).

**This PR is the read+write cutover only.** The `brought_craft` **column DROP is a follow-up** (see §3 deviation 2) that must land *after* 6c-1 deploys.

## 2. File-by-file edits

### 2.1 `athlete_event_windows_repo.py` (substantive)
- `EventWindow.brought_craft` field → **`brought_gear`** (+ comment); `_WINDOW_COLUMNS` `… away_locale, brought_gear, volume_pct …`; `_row_to_window` reads `row["brought_gear"]`; `add_event_window` **parameter** `brought_gear` + INSERT column list `… away_locale, brought_gear, volume_pct, notes …` (the `(",".join(crafts) or None)` value slot is positionally unchanged → index-6 assertions still hold).

### 2.2 `routes/profile.py` (substantive)
- `_stash_event_window_draft` stash key `'brought_gear': form.getlist('brought_gear')`; `add_event_window_route` `brought_gear=request.form.getlist('brought_gear')`.

### 2.3 `templates/profile/event_windows.html` (substantive)
- Display read `w.brought_gear`; form field `name="brought_gear"`, draft read `d.get('brought_gear', [])`; comment updated.

### 2.4 `templates/plan_create/new_form.html` (substantive)
- Review-panel display read `w.brought_gear`.

### 2.5 `layer4/orchestrator.py` (substantive)
- `_build_event_window_overlay`: `EventWindowOverride(..., brought_gear=tuple(w.brought_gear), ...)`; away branch `brought = set(away_ov.brought_gear)`; comment updated.

### 2.6 `layer4/session_feasibility.py` (substantive)
- `EventWindowOverride.brought_craft` field → **`brought_gear`** (+ comment).

### 2.7 `layer1/builder.py` (substantive)
- Travel-summary phrase reads `w.brought_gear` (`if w.brought_gear: … {', '.join(w.brought_gear)}`).

### 2.8 `layer4/hashing.py` (substantive) — digest-stable rename (deviation 1)
- `compute_event_windows_hash` value source moves to the renamed attr: `"brought_craft": sorted(getattr(w, "brought_gear", ()) or ())`. **The dict KEY string stays `"brought_craft"`** and the sort-key read `tuple(d["brought_craft"])` is unchanged — deliberate, to keep the digest byte-stable (see §3). Docstring + inline comment explain why.

## 3. Two deliberate deviations from the kickoff (flagged for Andy)

**(1) `hashing.py` — the kickoff's instruction is self-contradicting; I kept the digest stable.** The kickoff §2 says rename the `hashing.py` dict key `"brought_craft"`→`"brought_gear"` AND claims "Fold key change is byte-identical today (same data) → no one-time invalidation owed." But `canonical_json` uses `json.dumps(..., sort_keys=True)`, which serializes dict **keys** into the digest — so renaming the key would change `compute_event_windows_hash` for **every athlete with any overlapping event window** (the key string `…brought_craft…`→`…brought_gear…` differs even when the value is `[]`). That is a real one-time plan-cache invalidation, exactly what the kickoff said was NOT owed. **Resolution:** keep the JSON key string `"brought_craft"` (read the renamed `brought_gear` attribute for its value) → digest byte-identical, honoring the kickoff's stated invariant. The lone residual `brought_craft` string in live code, documented in place.

**(2) Column DROP deferred to a 1-file follow-up (redump-fold sequencing).** The write path (`add_event_window`) only ever wrote `brought_craft`; `brought_gear` is populated **lazily by the deploy-time backfill** (`init_db.py:3113`). Per the slice-4.3 redump-fold lesson ("don't drop a backfill source before the new baseline stops needing it") and the kickoff's own "add the DROP migration **after** the read-cutover deploys," dropping `brought_craft` in the **same** deploy as the cutover risks losing data from any row written by the old path just before deploy. So 6c-1 = read+write cutover only (no `init_db.py` change). **The DROP follow-up** (after 6c-1 deploys): remove the create at `init_db.py:2611` + the backfill at `:3111–3114`, add `"ALTER TABLE athlete_event_windows DROP COLUMN IF EXISTS brought_craft"` at the `_PG_MIGRATIONS` tail. Public-schema → rides `_PG_MIGRATIONS` (auto-applies on deploy), **not** `layer0-apply`. By then `brought_gear` is authoritative (new write path + backfill caught all stragglers in the 6c-1 deploy).

## 4. Manual §5.0 verification steps (owed to Andy)

**Profile → Event windows**, add an **away** window with gear brought:
1. Check e.g. **Packraft** + **Climbing gear**, set destination + dates, Save → the window persists and shows "· with packraft, climbing gear" in the list (read path now off `brought_gear`).
2. Inline "Add a new location" round-trip mid-add → the brought selections survive (draft stash now keyed `brought_gear`).
3. End-to-end: with that away window overlapping a plan, generate/refresh → the away segment still resolves the brought disciplines feasible for those dates (parity with pre-6c-1; the cutover is behavior-neutral). The plan-cache digest is unchanged (deviation 1) → no spurious regeneration.

## 5. Next session pointers

### 5.1 The DROP follow-up (do FIRST, after 6c-1 deploys)
- 1-file `init_db.py` change as in §3 deviation 2. Safe once 6c-1 is live (write path on `brought_gear`; backfill complete). Owes a deploy (auto-applied `_PG_MIGRATIONS`), not a `layer0-apply`.

### 5.2 Remaining slice 6c (separate branches off `main`, do NOT stack)
- **6c-2 — onboarding gear-toggle parity** (kickoff §3, ~3 files): `routes/onboarding.py` step 2c.2b captures owned crafts via `load_craft_catalog()` → `replace_athlete_crafts` but has **no** gear-toggle (ski/snow/climb/alpine) capture. Mirror the 6a `save_gear` split (`replace_athlete_crafts` + `replace_owned_gear_for_kinds(…, _GEAR_TOGGLE_KINDS)`) so onboarding + profile capture the same kinds. Cache: writes `athlete_gear` → `evict_layer1_on_gear_change` (exists).
- **6c-3 — legacy retirement** (kickoff §4, riskiest, last): retire app-dead `athlete_craft_locale_repo.py` + its tests + the `athlete_craft_locale` table. **Do NOT drop the `discipline_baseline_*` craft CSVs** — they are still the live Layer-1 substitution source (`layer1.builder` reads them); re-homing Layer 1 onto `athlete_gear` first is a larger cross-layer move (likely out of #884 scope). Coordinate any layer0 drops with a redump-fold. May warrant its own Layer-0 housekeeping slice.
- The deferred per-segment **2C re-resolve** (slice-5 §2) also lives in slice 6 — its own larger slice (architectural, over-ceiling).

### 5.3 Branch-name note
The pinned branch reads `claude/onboarding-parity-legacy-retire-vyprwg` (named from the slice-6c handoff title), but this PR carries **6c-1** (the cutover). Kept the pinned name (the harness pin + the "never push to a different branch" instruction). 6c-2/6c-3 take fresh branches off `main` after 6c-1 merges.

### 5.4 Operating notes (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped 6c-1). 3. `CARRY_FORWARD.md` (#884 rolling item). 4. This handoff + the 6c kickoff + the 6b-2 closing + the slice-6 plan + design §10/§11. 5. `./scripts/verify-handoff.sh`.

## 6. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | **Full** rename to `brought_gear` (attr + repo + layer4 reads + form field/param/route/stash + display templates) | Andy (AskUserQuestion 2026-06-30) | Legacy-retirement slice → cleanest end state; a mixed template (display `brought_gear` + form `name="brought_craft"`) reads worse than a full rename; churn is mechanical + confined to files already in the diff |
| 2 | Keep the `hashing.py` fold dict KEY as the legacy string `"brought_craft"`; move only the value source to the renamed attr | Claude (flagged) | `canonical_json` serializes dict keys (`sort_keys=True`) → renaming the key would change `compute_event_windows_hash` for every athlete with an overlapping window (a one-time plan-cache invalidation the kickoff said was NOT owed). Keeping the string keeps the digest byte-stable, honoring the kickoff's invariant |
| 3 | Column DROP is a follow-up after 6c-1 deploys (not in this PR) | Claude (flagged) | Write path only wrote `brought_craft` until now; `brought_gear` is backfill-populated → redump-fold: drop the source only after the read+write cutover deploys (the kickoff's own "after the read-cutover deploys") |

## 7. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Attribute + storage cut to `brought_gear` | `athlete_event_windows_repo.py` | `EventWindow.brought_gear` field; `_WINDOW_COLUMNS` + INSERT use `brought_gear`; `_row_to_window` reads `row["brought_gear"]`; `add_event_window(brought_gear=…)` |
| Layer4 reads renamed | `layer4/orchestrator.py`, `layer4/session_feasibility.py`, `layer1/builder.py` | `EventWindowOverride.brought_gear`; `set(away_ov.brought_gear)`; `w.brought_gear` in builder |
| Digest byte-stable (deviation 1) | `layer4/hashing.py` | dict key string still `"brought_craft"`; value `getattr(w, "brought_gear", ())`; `tuple(d["brought_craft"])` unchanged; docstring explains |
| Form field + stash renamed | `routes/profile.py`, `templates/profile/event_windows.html` | `getlist('brought_gear')` (stash + route); `name="brought_gear"`; `d.get('brought_gear')` |
| No `brought_craft` left in live code except the documented tombstone + the (to-be-dropped) `init_db.py` create/backfill | (repo grep) | `grep -rn brought_craft` (excl. handoffs/docs/archive) → only `init_db.py` create `:2611` / backfill `:3113` + `hashing.py` key + comment references |
| Suite green | (local) | `tests/ etl/tests/` **4009 passed / 30 skipped** (3 pre-existing #217 warnings) |
| No Neon/layer0 apply owed in 6c-1 | — | public-schema cutover, no migration this PR; the DROP follow-up owes a deploy (auto-`_PG_MIGRATIONS`), not a `layer0-apply` |

## 8. Files shipped this session (6c-1)

**Substantive (8 — over the 5-file ceiling; mechanical behavior-neutral rename, accepted by the kickoff as its own sub-PR):** `athlete_event_windows_repo.py`, `routes/profile.py`, `templates/profile/event_windows.html`, `templates/plan_create/new_form.html`, `layer4/orchestrator.py`, `layer4/session_feasibility.py`, `layer1/builder.py`, `layer4/hashing.py`.
**Tests (not counted):** `tests/test_layer4_event_windows.py`, `tests/test_redesign_locales_form_render.py`, `tests/test_routes_event_windows.py`, `tests/test_layer1_builder.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue #884 comment.

---

**End of handoff.**
