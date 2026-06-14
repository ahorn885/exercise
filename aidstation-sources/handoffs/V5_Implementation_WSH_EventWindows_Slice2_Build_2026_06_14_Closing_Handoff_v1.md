# V5 Implementation — WS-H: Event Windows Slice 2 BUILD (away destinations) — Closing Handoff

**Session:** Built **Slice 2** of the Event-Windows arc (issue [#581](https://github.com/ahorn885/exercise/issues/581) Phase H) per the ratified arc design `designs/Event_Windows_Design_v1.md` §6 (Slice 2). The athlete declares a date-bounded **`away` window** with a destination `locale_profiles` row (picked, or built inline via the existing Mapbox wizard); plan-gen **replaces** the home cluster with that destination's terrain/equipment for the window dates and resolves the **existing cascade** against it (no brought craft — F4, that's Slice 4).
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice1_Build_2026_06_14_Closing_Handoff_v1.md` (Slice 1, #596).
**Branch:** `claude/eventwindows-slice-2-8nnn3h` (PR TBD).
**North-star plan:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H.

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` clean against the Slice-1 handoff (all anchors present; working tree clean; on the slice-2 branch). Andy confirmed he applied the Slice-1 `athlete_event_windows` DDL on Neon → Slice 1 live in prod. Spot-checked the Slice-1 code (repo, `_build_event_window_overlay`, `_reduced_env`, `per_phase` overlay, hash) to ground the Slice-2 extension. No drift.

**Scope decisions taken with Andy (this session):** (1) target = **Slice 2 away windows**; (2) **full inline Mapbox create now** — satisfied by wiring the panel to the EXISTING `new_locale` wizard via the `return_to` machinery (NOT a wizard rewrite); (3) **include the `is_away` discriminator now** — and it turned out load-bearing, not cosmetic (see §2). **Trigger-#1** away-overlay wording **signed off** (extends the Slice-1 block to cover "replaced by a travel destination").

---

## 2. What shipped (the resolution model)

`away` is a third `override_type`: instead of *subtracting* from the home cluster (Slice 1's `indoor_only` / `locale_unavailable`), it **replaces** the env with a destination locale. The cascade is unchanged — only the `(locale_order, terrain, equipment, owned_crafts)` inputs differ.

1. **`orchestrator._away_env(db, user_id, away_locale)`** — builds the replacement env by running the existing `locations.cluster_terrain_by_locale` / `cluster_equipment_by_locale` against a **single-locale "cluster"** `[away_locale]`. Home cluster discarded.
2. **`orchestrator._resolve_included_feasibility`** gains an `owned_crafts` kwarg (default `fi.owned_crafts`); the away path passes **`set()`** (F4 — no brought craft away until Slice 4, so away bike/paddle degrade through indoor/strength).
3. **`orchestrator._build_event_window_overlay`** dispatches per segment: a segment carrying an `away` override resolves via `_away_env` + empty crafts; else the Slice-1 `_reduced_env` path. **Away wins** over any co-active subtractive override on the same days (you can't be "indoor-only at home" while away); multiple away windows on one day → deterministic first by `away_locale` (declaration error). Rule #15 log gains `@<away_locale>`.
4. **`is_away` discriminator** (`locale_profiles.is_away`) — `locations.cluster_locale_ids` now excludes `is_away` rows from the home-cluster radius sweep. **This is the load-bearing reason for the column:** the sweep pulls in *every* saved locale within `_CLUSTER_RADIUS_KM` of home, so a nearby travel destination would otherwise pollute home feasibility (2B terrain / 2C equipment / the feasibility cascade). Excluded at the source so every cluster consumer agrees.
5. **Cache:** `hashing.compute_event_windows_hash` now folds `away_locale` per away window. **`away_locale` is OMITTED from the per-window dict when unset**, so a subtractive-only window hashes **byte-identically to the Slice-1 digest** (no needless cache bust on the Slice-2 deploy). The no-windows key stays byte-identical (caller passes None) — both regressions held.
6. **Synthesis:** `per_phase._event_window_label` away branch (`away — training at "<dest>"`) + the intro/soft-directive wording extended to "reduced **or** replaced by a travel destination" (**Trigger-#1, signed off**). An away segment is resolved against its destination alone, so the label leads with the away destination.
7. **Capture UI:** `routes/profile` `/profile/event-windows` gains the `away` option + a **travel-destination picker** (the athlete's `is_away` locales) + a **"+ Add a travel location"** link → `/locales/new?away=1&return_to=/profile/event-windows`. `routes/locales` honors `?away=1` (session-stashed, survives the multi-step wizard): the created locale is flagged `is_away` and is **NOT auto-homed** (`_ensure_home` skipped). Mapbox `mapbox_id` dedup falls out of the existing `new_locale` path for free.
8. **Repo:** `add_event_window` validates `away` (requires an `away_locale` resolving to a saved locale; clears `unavailable_locale`); `EventWindow.away_locale` field; select/insert the column. `OVERRIDE_TYPES = ("indoor_only", "locale_unavailable", "away")`.
9. **DDL** (`init_db._PG_MIGRATIONS`, idempotent): `athlete_event_windows.away_locale TEXT` + `locale_profiles.is_away BOOLEAN NOT NULL DEFAULT FALSE`.

---

## 3. Files

| File | Kind | Change |
|---|---|---|
| `athlete_event_windows_repo.py` | substantive | `away` override_type + `away_locale` field/validation/select/insert |
| `layer4/session_feasibility.py` | substantive | `EventWindowOverride.away_locale` + Literal; sort key includes away_locale |
| `layer4/orchestrator.py` | substantive | `_away_env` + away dispatch in the overlay loop + `owned_crafts` kwarg on `_resolve_included_feasibility` |
| `locations.py` | substantive | `cluster_locale_ids` excludes `is_away` locales from the sweep |
| `layer4/hashing.py` | substantive | `away_locale` folded into `compute_event_windows_hash` (omit-when-None → subtractive byte-identical) |
| `layer4/per_phase.py` | substantive | away label + Trigger-#1 wording (reduced **or** replaced) |
| `routes/locales.py` | substantive (UI) | `?away=1` flow → `is_away` flag + skip auto-home |
| `routes/profile.py` + `templates/profile/event_windows.html` | substantive (UI) | away option + travel-destination picker + inline-create link + table render |
| `init_db.py` | bookkeeping-adjacent | the two DDL migrations |
| `tests/test_layer4_event_windows.py` | tests (not counted) | +8 away cases; Slice-1 fixtures updated for the new field |

**File-count flag:** ~9 substantive (2 UI route files + template). Over the soft 5-ceiling — **Andy explicitly chose the full scope** (away + full inline create + the discriminator) over a pick-existing-only split; consistent with the WS-B/WS-C 7-file precedent.

---

## 4. Tests

`tests/test_layer4_event_windows.py` now **37** (29 Slice-1 + 8 new): away env resolution (destination replaces home → D-001 reroutes to the destination's machine); away segment override carries `away_locale`; away overlay label + "replaced by a travel destination" intro; hash distinguishes destinations; **subtractive digest byte-identical to the pre-away form** (legacy object lacking the attr); repo away validation (requires away_locale, requires resolvable, inserts + clears unavailable); cluster sweep excludes `is_away` (SQL guard). Slice-1 positional `EventWindow` fixtures updated for the new field; the old "rejects `away`" test repointed to `bogus` (away is now valid).

**Full suite: 2428 passed / 30 skipped.** Env: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

---

## 5. Decisions pinned (Andy, 2026-06-14)

| # | Decision |
|---|---|
| 1 | Target = Slice 2 away windows. |
| 2 | **Full inline Mapbox create now** — wired via the existing `new_locale` wizard + `return_to` (no wizard rewrite). |
| 3 | **Include `is_away` now** — turned out load-bearing (cluster-sweep pollution), not cosmetic. |
| 4 | Trigger-#1 away-overlay wording approved (reduced **or** replaced). |

---

## 6. Next session

### 6.1 Owed Andy's hands
- **Apply the Slice-2 DDL on Neon** (no container egress). **DEPLOY ORDERING — apply BEFORE the code goes live:** `cluster_locale_ids` reads `is_away` on a hot path (every plan-gen / 2B / 2C), so the column must exist before the Slice-2 code serves traffic, else that path errors for everyone.
  ```sql
  ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS away_locale TEXT;
  ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS is_away BOOLEAN NOT NULL DEFAULT FALSE;
  ```
- (carried) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

### 6.2 Deferred follow-ups (flagged)
- **Refresh-overlay render** — still create-first (mirrors #540→#557). `event_windows_hash` is a param on `plan_refresh_key`; wire `orchestrate_plan_refresh` to compute overlapping windows + feed the hash + thread `event_window_segments` into the tier prompts. A window edit already evicts both caches, so refresh won't serve stale — it just won't *render* the overlay until wired. (Now covers away too.)
- **Slice 3 — category equipment baselines (Trigger #2):** assumed-equipment for commercial/hotel/climbing gyms + the assumed→logged arrival-regen loop (F6/F8). Baseline *contents* need Andy's sign-off — don't author blind.
- **Slice 4 — away craft (F4):** craft↔locale ∪ craft↔window → away `owned_crafts` (currently hard-`set()`). DDL: `athlete_craft_locale` + window craft carrier.
- **Slice 5 — capture UX polish:** plan-gen review panel hook + nav-link `/profile/event-windows` from the Athlete tab; a toggle to mark an *existing* (non-away) locale as a travel destination (Slice 2 only flags on inline-create / pick-from-away-list).
- **Minor:** the away picker shows only `is_away` locales; an athlete who built a destination as a normal locale can't pick it as away without re-creating it (acceptable for Slice 2; Slice 5 toggle closes it).

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — top entry (WS-H Slice 2 BUILT).
4. This handoff.
5. `designs/Event_Windows_Design_v1.md` (arc) + the Slice-1 spec.
6. `./scripts/verify-handoff.sh` (from `aidstation-sources/`).

**Test env:** `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then full `tests/`.

---

## 7. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Repo | `athlete_event_windows_repo.py` | `OVERRIDE_TYPES = ("indoor_only", "locale_unavailable", "away")`; `away_locale` on `EventWindow`; away validation in `add_event_window` |
| Override model | `layer4/session_feasibility.py` | `EventWindowOverride.away_locale`; Literal includes `"away"` |
| Away env | `layer4/orchestrator.py` | `_away_env`; away dispatch in `_build_event_window_overlay`; `owned_crafts` kwarg on `_resolve_included_feasibility` |
| Cluster exclusion | `locations.py` | `cluster_locale_ids` others-sweep has `AND NOT COALESCE(is_away, FALSE)` |
| Hash | `layer4/hashing.py` | `compute_event_windows_hash` folds `away_locale` (omit-when-None) |
| Render | `layer4/per_phase.py` | `_event_window_label` away branch; "replaced by a travel destination" |
| DDL | `init_db.py` | `away_locale` + `is_away` ALTERs in `_PG_MIGRATIONS` |
| UI | `routes/profile.py` + `routes/locales.py` + `templates/profile/event_windows.html` | away picker + `?away=1` inline-create + table render |
| Tests | `tests/test_layer4_event_windows.py` | 37 pass |
| Suite | — | 2428 passed / 30 skipped |

---

## 8. Owed Andy's hands
- **Slice-2 DDL on Neon — BEFORE deploy** (deploy-ordering, §6.1).
- (carried, unrelated) the post-#572 live T3 *refresh* re-verify.
