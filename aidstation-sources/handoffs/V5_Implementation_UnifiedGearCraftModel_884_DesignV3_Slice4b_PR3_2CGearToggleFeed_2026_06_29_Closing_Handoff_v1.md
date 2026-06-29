# V5 Implementation — #884 Unified Gear/Craft Model — Slice 4b PR-3 (Layer 2C gear-toggle feed) — Closing Handoff

**Session:** Slice 4b PR-3 of #884 — the **2C consumer** un-starve. Fed Layer 2C's `cluster_gear_toggle_states` (both call sites passed `{}`) from the athlete's owned gear via a new `gear_id → toggle_name` bridge. **Closes the last #298 consumer.** Also triggered + confirmed the OWED Neon `layer0-apply` for PR-2's `0026`+`0027`+`0028`.
**Date:** 2026-06-29
**Predecessor handoff:** `V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice4b_PR2_CascadeExtension_2026_06_29_Closing_Handoff_v1.md` (PR-2, merged as `2cdd24b` / PR #983)
**Branch:** `claude/884-cascade-extension-m5weck` (harness-pinned; name reflects PR-2's scope, reused for PR-3 — see §6)
**Status:** code done, **suite 3737/30 green**, ruff clean. Committed `52d71ae`. **PR not yet opened — awaiting Andy's go** (ops model). No new migration → **no Neon apply owed** (PR-2's apply is DONE — §1).

---

## 0. Thread continuity — NEXT SESSION CONTINUES #884

**The next session stays on #884** (tier-1 finish-the-in-flight-task). Continuous build: Slice 4b = **PR-1 capture (merged #976)** → **PR-2 cascade extension + taxonomy normalization (merged #983)** → **PR-3 = 2C gear-toggle feed (this)**. **The next forward move is slice 4.3** — Layer-0 redump retiring `craft_discipline_aliases` + the equipment strip (`pull_buoy`/`kickboard`/`Swim fins` out of `equipment_items` + EX126/EX128 `equipment_required`). Then slices 5–6 (design-v3 §15: 4b→4.3→5→6). Design: `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §5.5/§6/§15. Plan: `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md`.

---

## 1. Session-start verification (Rule #9) + the OWED Neon apply

PR-2's §8 anchors re-checked against on-disk + merged state — all ✅ (`verify-handoff.sh` clean; PR-2 is in `origin/main` as `2cdd24b`/#983; tree clean). Branch was behind main (its only unique commit, PR-2, was already merged) → `git reset --hard origin/main` (no loss), so PR-3 builds on `0026`/`0027`/`0028` + the two intervening merges (#982, #985).

**OWED Neon apply — DONE this session.** PR-2 left `layer0-apply` for `0026`+`0027`+`0028` owed (most recent run was #17, slice-3b's `0025`). Triggered `layer0-apply` on `main`; Andy one-tapped the `production` gate (~8 min). Run #18 (`4f7ea2d`) applied all three (log-confirmed): `0026` INSERT 10 gear-toggle terrain rows; `0027` UPDATE 3 `climbing_gear` aliases `climbing`→`climb`; `0028` dropped `modality_groups.group_kind`; `0023`–`0025` correctly ledger-skipped. **Climbing no longer degrades to terrain-only.**

---

## 2. The change (ratified slice — Andy Decision 2, 2026-06-29)

PR-2 split the 2C feed to PR-3 (Decision 2: it needs a `gear_id → sport_specific_gear_toggles.toggle_name` bridge — different keyspaces — and would have blown PR-2's file ceiling). This session executes that ratified split. No new architectural decision; no stop-and-ask trigger (no schema change, no new payload field, no prompt change, no invalidation-rule change — fills a stubbed input).

**Why a bridge:** the unified store keys on stable snake_case `gear_id` (`GEAR_REGISTRY`); Layer 2C's `cluster_gear_toggle_states` / `toggle_defs` key on the catalog's free-text `toggle_name`. The two keyspaces differ (`classic_xc_ski` vs `'Classic XC ski setup'`; `mountaineering` vs `'Mountaineering'`), so 2C can't read `athlete_gear` without the map.

**Grounding finding (drives the behavioral scope):** all 6 active `sport_specific_gear_toggles` rows have **empty `paired_equipment_categories`** (the §5.4 gym-equipment boundary cleanup already stripped gear-covered items), so feeding states does **not** change `_build_effective_pool` (the equipment pool is byte-identical). The only effect is on the **§8.3 `toggle_off_for_discipline` coaching flag**, and only the two toggles carrying `gated_discipline_ids` matter: **`Climbing gear` → D-012/013/014** and **`Snowshoeing setup` → D-017**. Owning that gear now suppresses the spurious "you don't have the gear" flag — making 2C consistent with PR-2's cascade gating (own gear → discipline feasible AND no spurious flag; no gear → gated AND flag fires).

---

## 3. File-by-file edits

### 3.1 `athlete_gear_repo.py` (modified)
- **NEW `GEAR_TOGGLE_NAMES: dict[str,str]`** — the `gear_id → toggle_name` bridge (design v3 §5.5 source). 6 entries (classic_xc_ski, skate_xc_ski, snowshoes, climbing_gear, mountaineering, skimo_at). **`rollerskis` intentionally absent** (new gear, Decision 10 — no `sport_specific_gear_toggles` row; its D-028 feasibility is the cascade's job via `gear_discipline_aliases`, and it gates nothing in 2C). Pinned against the live catalog's toggle_name strings by the repo test.
- **NEW `owned_gear_toggle_states(owned_gear_ids) -> dict[str,bool]`** — pure derivation: `{toggle_name: True}` for each owned gear_id in the bridge. No DB query (consumes `Layer1Payload.owned_gear`, rides `layer1_hash`). Unbridged/unowned gear (rollerskis, bike/paddle crafts) contribute no key (the 2C consumer treats absent toggles as OFF). Owned gear is always ON (the store has no explicit-False rows).

### 3.2 `layer4/orchestrator.py` (modified)
- **Full-cone path (~1138):** `cluster_gear_states = owned_gear_toggle_states(layer1_payload.owned_gear)` (local import, mirroring the existing `GEAR_REGISTRY` local import — `athlete_gear_repo` pulls in `layer4.cache`); threaded into the per-locale 2C call (was `={}`). The state is the same for every cluster locale (gear is portable — §3). Rule #15 fan-out log gains `gear_toggle_states=`.
- **Single-session/locale path (~1583):** same wire (`cluster_gear_toggle_states=owned_gear_toggle_states(layer1_payload.owned_gear)`).

### 3.3 Tests
- `tests/test_athlete_gear_repo.py` (+4 — `TestGearToggleNameBridge`): bridge pins the §5.5 toggle_names; bridge keys == toggle-kind gear_ids minus rollerskis; `owned_gear_toggle_states` maps bridged→ON and omits unbridged/craft gear; empty cases.
- `tests/test_layer2c.py` (+1): `test_toggle_on_suppresses_gated_discipline_flag` — the ON complement of the existing `test_toggle_off_for_discipline_fires_from_gated_column` (owning `Climbing gear` suppresses the D-012 flag). PR-3's served-output behavior pin.

---

## 4. Behavior change (intended) + cache

**Intended served-output change.** For an athlete who **owns** climbing gear and/or snowshoes and includes those disciplines, the spurious 2C `toggle_off_for_discipline` coaching flag no longer fires. Athletes who don't own the gear are unchanged (absent key → OFF → flag fires, as before). The equipment pool is byte-identical for everyone (empty `paired_equipment_categories`).

**Cache:** feeding states changes the 2C coaching-flag set for owning athletes who include the gated disciplines → `compute_layer2c_bundle_hash` shifts → those cached blocks re-run. Correct, intended invalidation (same property as PR-2). Athletes who own no gated gear / don't include those disciplines stay byte-identical (no re-run).

---

## 5. Code / tests validation

- Suite `tests/ etl/tests/`: **3737 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings). Ruff clean on all 4 changed files.
- No migration this slice → **no Neon apply owed.** (PR-2's `0026`+`0027`+`0028` applied this session — §1.)
- **1 code + 1 repo (= 2 substantive code) + 2 test files** — under the 5-file ceiling.

---

## 6. Next session pointers

### 6.1 OWED this PR
- **Nothing DB-side.** PR not yet opened — awaiting Andy's go (ops model). When he says go: push (done), open PR (ready, not draft), `enable_pr_auto_merge` with **method=`merge`** (real merge commit, NOT squash — Andy 2026-06-29).
- **Branch note:** the harness pinned `claude/884-cascade-extension-m5weck` (PR-2's name). Kept it for PR-3 rather than rename (the strict "never push to a different branch without permission" harness rule). The PR title/handoff carry the real scope. Andy may want a cleaner branch name for the PR.

### 6.2 Next session — CONTINUE #884 (start here)
- **Slice 4.3 — Layer-0 redump + equipment strip.** Retire `craft_discipline_aliases` (forced redump — **heed the redump-MUST-pair-with-fold rule**, `etl/migrations/layer0/README.md`); strip `pull_buoy`/`kickboard`/`Swim fins` from `equipment_items` + EX126/EX128 `equipment_required` (0B supersede+re-insert → global cache invalidation). Then slices 5–6.

### 6.3 Open follow-on (not owed by this slice)
- **Onboarding parity for gear toggles** (carried from PR-1/PR-2): toggles captured on the profile gear-tab only; if onboarding should surface them too, small follow-on. Flag for Andy.

### 6.4 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped (this) + the #884 predecessors.
3. `CARRY_FORWARD.md` — the #884 rolling item.
4. This handoff + `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md`.
5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | 2C feed is its own PR-3 (split from PR-2) | Andy 2026-06-29 | Needs the gear→toggle_name bridge + would have exceeded PR-2's file ceiling |
| 2 | Bridge source = design v3 §5.5 keyspace; `rollerskis` excluded | Claude | rollerskis has no `sport_specific_gear_toggles` row (new gear, Decision 10); its feasibility is the cascade's, not a 2C toggle |
| 3 | Derive states off `Layer1Payload.owned_gear` (no new query) | Claude | Rides `layer1_hash`; mirrors PR-2's `discipline_gear_kind` derivation |

---

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Bridge defined | `athlete_gear_repo.py` | grep `GEAR_TOGGLE_NAMES` → 6 entries; `"climbing_gear": "Climbing gear"`; no `rollerskis` key |
| State helper | `athlete_gear_repo.py` | grep `def owned_gear_toggle_states` |
| Full-cone 2C fed | `layer4/orchestrator.py` | grep `cluster_gear_toggle_states=cluster_gear_states` |
| Single-session 2C fed | `layer4/orchestrator.py` | grep `cluster_gear_toggle_states=owned_gear_toggle_states(` |
| §8.3 ON-suppress pin | `tests/test_layer2c.py` | grep `test_toggle_on_suppresses_gated_discipline_flag` |
| Bridge pin | `tests/test_athlete_gear_repo.py` | grep `TestGearToggleNameBridge` |
| Suite green | (local) | `tests/ etl/tests/` 3737 passed / 30 skipped |
| Neon apply DONE | `layer0-apply` run #18 (`4f7ea2d`) | log: 0026 INSERT 10 / 0027 UPDATE 3 / 0028 ALTER |

---

## 9. Files shipped this session

**Substantive (2 code + 2 test):**
1. `athlete_gear_repo.py` — `GEAR_TOGGLE_NAMES` bridge + `owned_gear_toggle_states`
2. `layer4/orchestrator.py` — both 2C sites fed from owned gear + Rule #15 log
3. `tests/test_athlete_gear_repo.py` — bridge + state derivation pins
4. `tests/test_layer2c.py` — toggle-ON-suppresses-flag complement

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue #298 comment.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` #884: slice-4 PROGRESS — 4a/4.2 done; 4b-PR1 (capture) + 4b-PR2 (cascade + `0026`/`0027`/`0028`, **Neon-applied this session**) merged; **4b-PR3 (2C gear-toggle feed) done+pushed, PR awaiting Andy's go**; **slice 4.3 (redump + equipment strip) next.** #298 (gear-toggle starvation): **all three consumers now closed** — capture (PR-1), terrain-feasibility cascade (PR-2), 2C feed (this).

---

**End of handoff.**
