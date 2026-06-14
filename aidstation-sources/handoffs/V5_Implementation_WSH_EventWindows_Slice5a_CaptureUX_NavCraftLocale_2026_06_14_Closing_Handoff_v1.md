# V5 Implementation — WS-H: Event Windows — Slice 5a: capture UX (nav reachability + craft↔locale relocation) — Closing Handoff

**Session:** Picked up the harness-pinned #604 branch; #604's pivotal piece (the live `pg_dump`) is still owed-Andy's-hands and its "unblocked remainder" (scaffolding retirement) turned out to be genuinely gated — so per Andy's `AskUserQuestion` choice ("move on the other slices in the larger project") the session pivoted to the in-flight WS-H arc's last slice. Shipped **Slice 5a** of the Event-Windows capture-UX polish: (1) **nav reachability** — `/profile/event-windows` was built but had **no nav entry anywhere** (built-but-unnavigable); added it to the sidebar dropdown + mobile drawer. (2) **Relocated the (b) standing craft↔locale capture** off the event-windows page onto the **per-locale edit page** (`/locales/<locale>/edit`) — craft kept at a place is a property of the place, where the predecessor explicitly parked it. **Resolution + repo unchanged**; only the capture point moved.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice4_AwayCraft_2026_06_14_Closing_Handoff_v1.md` (Slice 4 away craft, PR #605 merged + live; #581 closed).
**Branch:** `claude/big-data-migration-604-yx7j6l` (harness-pinned for #604; kept per the explicit "never push to a different branch" instruction + last session's precedent — scope is Slice 5a, not the 604 migration).
**Spec/arc:** `designs/Event_Windows_Design_v1.md` §6 (Slice 5 = "capture UX polish") + §F5. No separate Slice-5 spec written (UX-relocation polish, no DDL / no resolution change / no vocab / no trigger — the design §6 line is the spec). **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. **Epic #581 already closed** (Slice 4); this is the arc's UX tail.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the Slice-4 handoff — all green, tree clean, branch correct (`claude/big-data-migration-604-yx7j6l`), §8 anchors on disk. No drift; Slice 4 genuinely merged + live.

## 2. The 604 re-look + the pivot (Andy-directed)

Andy: *"keep working. the 604 big data migration isn't done yet just fyi."* Re-investigated #604's actual state:
- **Part 1–2 (genesis refresh from live `pg_dump` → reconcile → `validate_layer0`)** — **still blocked, owed Andy's hands.** Newest snapshot in `etl/output/` is `v1.6.7`; no `v1.7.0` has landed (Neon egress blocked from the container).
- **Part 3 (retire the stale `etl/sources/populate_equipment_items_*.sql` scaffolding)** — the "unblocked remainder," but **not a clean drop**: `batch_a` is dead-and-wrong (its verify block `RAISE EXCEPTION`s on the *retired* `Bench press rack`); `K`/`K2` **collide** with older differing copies already in `aidstation-sources/archive/etl-scratch/migrations/` (archive copies use `ON CONFLICT (canonical_name)`, the `etl/sources` ones the current `(canonical_name, etl_version)` shape); and **`K3` is NOT dead** — `etl/sources/run_owed_layer0_migrations.sql:39` still `\ir`s it, its Neon deploy was last logged **owed** (CARRY_FORWARD), and it lands the paddling vocab (Kayak/Canoe) **but also contains the now-retired `Crash pad`**. The archive move needs a Rule #12 sign-off + a K3 decision.
- Surfaced both via `AskUserQuestion`. **Andy chose "move on the other slices in the larger project"** (and "see prior message" for the scaffolding fork → same answer). So #604 stays parked, fully captured below + in CARRY_FORWARD; the session moved to WS-H Slice 5.

## 3. Scope decision (Slice 5 is a grab-bag → did the clean, no-trigger subset)

Design §6 Slice 5 = "capture UX polish (F5): full panel on profile + onboarding, beyond the minimal Slices 1–2 capture." The Slice-4 handoff §7 enumerated four items: **(a) nav-link**, **(b) plan-gen review/edit/append panel (F1)**, **(c) move the (b) craft↔locale capture to the locale page**, **(d) 2b round-trip form-state preservation**. None trip a stop-and-ask trigger (no DDL / no prompt / no vocab / no cross-layer change). Shipped the two smallest, highest-certainty, fully-contained items — **(a) + (c)** — as **Slice 5a**. **(b)** (the plan-gen review panel) is the largest, touches the plan-create flow, and is deferred to its own slice (flagged §7). **(d)** deferred with it.

## 4. Implementation (Slice 5a)

- **`routes/locales.py`** — imports `load_craft_catalog` (from `athlete_crafts_repo`) + the craft↔locale repo fns; **new route `POST /locales/<locale>/crafts` → `save_locale_crafts(locale)`**: existence-checks the locale (user-scoped), `replace_craft_locale(db, uid, locale, request.form.getlist('craft_slug'))` (replace-all; none-checked clears), `CraftLocaleError`→flash, commit, `evict_plan_caches_on_craft_locale_change`, redirect back to the edit page. `_edit_locale` GET render now passes `craft_catalog=load_craft_catalog()` + `crafts_here=load_craft_locales(db, uid).get(locale, [])`.
- **`templates/locales/form.html`** — new "● Craft you keep here" card (its own `<form>`, separate from the equipment-save POST so the equipment/terrain/privacy path is untouched), checkboxes from `craft_catalog` with `crafts_here` driving the checked state, posting to `save_locale_crafts`. **Guarded `{% if craft_catalog %}`** so pre-Slice-5 callers / bare renders skip it.
- **`routes/profile.py`** — removed the two now-moved route handlers (`save_craft_locale_route`, `delete_craft_locale_route`) + the whole `athlete_craft_locale_repo` import + the `craft_locales=` render kwarg on `event_windows()`. Kept `load_craft_catalog` (still feeds the brought-craft (c) picker + the crafts tab).
- **`templates/profile/event_windows.html`** — removed the "Craft you keep at a location" card; replaced with a one-line hint linking to the locations page. Header comment updated to note the (b) capture moved.
- **`templates/_shell/sidebar.html` + `templates/_shell/mobile_drawer.html`** — "Event windows" nav entry in the account dropdown / drawer (next to Coach memory), pointing at `profile.event_windows`. (Mechanical, 1 + 3 lines.)

**No DDL, no resolution change, no cache-key change, no vocab.** The craft↔locale repo (`load_craft_locales`/`replace_craft_locale`/`delete_craft_locale`/`evict_plan_caches_on_craft_locale_change`) and the orchestrator union resolution are **byte-identical** — only the capture surface moved. `delete_craft_locale` is now unused by any route (replace-all-with-none clears instead); left in the repo (no orphan in my diff; flag-don't-delete).

## 5. Tests

- **`tests/test_redesign_locales_form_render.py`** — `_form_ctx` gains `craft_catalog` + `crafts_here`; new `test_form_renders_craft_kept_here` (the relocated card renders, posts to `/locales/home/crafts`, `crafts_here` drives checked state, and the `craft_catalog=None` bare render hides it). Updated `test_event_windows_capture_renders_away_create_link`: dropped the moved `name="craft_slug"`/`crafts-at-locale` asserts + the `craft_locales` kwarg, added asserts that the in-page craft form is **gone** and the locations-page link renders (kept brought-craft (c)).
- **Full suite: 2468 passed / 30 skipped** (+1 from the new test; was 2467). The two `Layer3BEvidenceBasisWarning`s are pre-existing/unrelated. All touched modules byte-compile. The render tests exercise `url_for('locales.save_locale_crafts')`, confirming the route registers (no circular import from the new top-of-module repo imports in `locales.py`).

## 6. Owed Andy's hands

- (carried, #604) the live **`pg_dump`** → `etl/output/layer0_etl_v1.7.0.sql` (parts 1–2) + the Rule #12 sign-off / K3 decision for part 3 (see §2 + CARRY_FORWARD).
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).
- **Slice 5a itself owes nothing** — no DDL, reuses live routes/repo.

## 7. Next session

- **Slice 5b — the plan-gen review/edit/append panel (F1)** (the arc's last real piece): surface the event-window calendar for review/edit/**append** at plan generation (restores the v1 `/coaching/review` UX), with inline new-location create. Larger — touches the plan-create flow/routes; worth its own slice. Plus **the 2b round-trip form-state preservation** (item (d)) + the onboarding panel (F5).
- **#604 — vocab single-source-of-truth** (parked; still owed the live `pg_dump`; part 3 scaffolding retirement needs a Rule #12 sign-off + the K3 decision — §2).
- (split out) #592 race-location terrain/weather; #593 reduced-volume travel days.

### 7.1 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — WS-H block + the #604 entry. 4. This handoff. 5. `designs/Event_Windows_Design_v1.md` §6/§F5. 6. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| New craft-locale route | `routes/locales.py` | `def save_locale_crafts(locale)` @ `POST /locales/<locale>/crafts`; `replace_craft_locale` + `evict_plan_caches_on_craft_locale_change` |
| Edit render ctx | `routes/locales.py` | `craft_catalog=load_craft_catalog()` + `crafts_here=load_craft_locales(db, uid).get(locale, [])` in `_edit_locale` |
| Relocated capture UI | `templates/locales/form.html` | `● Craft you keep here`; `url_for('locales.save_locale_crafts', locale=locale)`; `name="craft_slug"`; guarded `{% if craft_catalog %}` |
| Event-windows cleanup | `templates/profile/event_windows.html` | no `craft_slug` form; one-line hint linking to `locales.list_profiles` (`own page</a>`) |
| Profile route cleanup | `routes/profile.py` | no `save_craft_locale_route`/`delete_craft_locale_route`; no `athlete_craft_locale_repo` import; no `craft_locales=` kwarg |
| Nav reachability | `templates/_shell/sidebar.html`, `templates/_shell/mobile_drawer.html` | `url_for('profile.event_windows')` "Event windows" entry |
| Tests | `tests/test_redesign_locales_form_render.py` | `test_form_renders_craft_kept_here`; updated event-windows render asserts |
| Suite | — | 2468 passed / 30 skipped |
| Owed | — | Slice 5a owes nothing (no DDL); #604 `pg_dump` + the T3-refresh re-verify carried |
