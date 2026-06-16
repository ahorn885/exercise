# V5 Implementation — #644 Cull non-trainable "Technical / Skill" exercises — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/focused-faraday-yelunt`
**Migration:** `etl/migrations/layer0/0009_cull_nontrainable_technical_skill.sql` (merged via PR [#647](https://github.com/ahorn885/exercise/pull/647); applied to prod + verified)
**PRs this session:** [#646](https://github.com/ahorn885/exercise/pull/646) (#623 close bookkeeping, merged), [#647](https://github.com/ahorn885/exercise/pull/647) (0009 migration, merged), [#649](https://github.com/ahorn885/exercise/pull/649) (#644 bookkeeping, merged), [#650](https://github.com/ahorn885/exercise/pull/650) (#644 applied+verified bookkeeping + this handoff).
**Predecessor handoff:** `handoffs/V5_Implementation_Locations_RetireAssumedGear_623_2026_06_16_Closing_Handoff_v1.md` (#623, PR #643).

Session opened on the #623 closing handoff (Andy: *"0008 has been approved. update and close 623"*), then *"lets do 644"*. **Two issues closed this session — #623 (assumed-gear retirement) and #644 (Technical/Skill cull), both applied to prod + verified.** One new issue filed: #648.

---

## 0. #623 closed (carried in from the predecessor handoff)
`0008` applied to prod via `layer0-apply` ([run 27596296178](https://github.com/ahorn885/exercise/actions/runs/27596296178)) + verified via read-only `neon-query` ([run 27596476996](https://github.com/ahorn885/exercise/actions/runs/27596476996)): **101 active equipment_items, 0 retire-set items active, 0 exercises gating, 17 de-drifted at `0B-v1.6.9`.** #623 **CLOSED completed**; bookkeeping PR #646 merged.

---

## 1. What shipped — #644

### The gap
65 of 211 active exercises are `exercise_type = 'Technical / Skill'`. Because they live in `sport_exercise_map`, Layer 4 can prescribe them into a plan ("do Snowshoe Gait Technique this week"). Most are legitimate skill *sessions* a coach programs; ~10 are non-trainable familiarization / gear-setup / coaching cues.

### Audit (read-only `neon-query`)
Pulled all 65 active `Technical / Skill` entries' `coaching_cues` + the full progression/regression/physical-proxy reference graph from live prod (run id 27597531846 — the classify + reverse-FK query). Reference graph finding: the **only external reference into the cull set is EX176 (kept) → EX094 in `physical_proxies`**. The snowshoe trio (EX153/EX154/EX155) prog/regr links are all internal to the trio. The other culls have zero inbound references.

### Decisions (Andy via `AskUserQuestion` — Trigger #2, exercise-DB curation)
1. **Cull all 6 confident non-sessions:** EX123 (pack fit), EX148 (crampon walking), EX150 (rest step), EX152 (post-hole gait), EX153 (snowshoe gait), EX155 (snowshoe sidehill).
2. **Cull all 4 borderline:** EX094 (packraft inflation), EX121 (pole descent braking), EX122 (hip hinge under pack), EX154 (plunge step / snowshoe).
3. **Keep EX118** (trekking pole push — real propulsion-economy technique + it is EX183's regression link).
4. **Keep `Technical / Skill` a prescribable `exercise_type`** (cull-only; no separate skill-lane).

### The build (1 substantive file)
- **`etl/migrations/layer0/0009_cull_nontrainable_technical_skill.sql`** —
  - **(0B-i)** repoint EX176: supersede + reinsert at `0B-v1.6.9`→`0B-v1.6.10` with EX094 stripped from `physical_proxies` (the surviving EX180 proxy preserved, order kept). This reinsert is the migration's cache-bump carrier.
  - **(0B-ii)** supersede the 10 culled exercises (supersede-only; 2C/2D readers filter `superseded_at IS NULL` → they leave the library).
  - **(0B-iii)** supersede the culled exercises' `sport_exercise_map` rows (hygiene — already inert via the `exercises` join, but kept consistent).
  - **Atomic DO-block:** no culled exercise active; no active exercise references a culled id via progression/regression/`physical_proxies` (the exercises-FK check `validate_layer0` lacks); no active `sport_exercise_map` row maps one; EX176 repointed (active at `0B-v1.6.10`, EX094 gone, EX180 kept); exactly 55 `Technical / Skill` remain (65−10; typo guard).
  - Idempotent (EX176 reinsert guarded to the pre-bump row with a culled proxy; supersede UPDATEs match only still-active rows; re-run = clean no-op).
- **NO DDL. No `LAYER4_PROMPT_REVISION` bump** (data-only; cache invalidation rides the `0B-v1.6.10` digest, same as `0007`/`0008`).

### Why no app/template change
2C/2D consume `sport_exercise_map` only through a JOIN to `exercises` with `e.superseded_at IS NULL` (`layer2c/builder.py` ~line 298, `layer2d/builder.py` ~line 872), so superseding the exercise rows is sufficient to drop them from prescription. Nothing else references these exercise_ids.

### Verification
- **CI Layer-0 gate GREEN** on PR #647 (postgres:17, v1.8.0 baseline + migrations `0006`–`0009`, `validate_layer0`). The container has the psql **client only** (no local PG server) → CI is the authoritative gate this session.
- **Applied to prod** via `layer0-apply` ([run 27598426170](https://github.com/ahorn885/exercise/actions/runs/27598426170), success).
- **Verified** via read-only `neon-query` ([run 27615278864](https://github.com/ahorn885/exercise/actions/runs/27615278864)): **55 active `Technical / Skill`, 0 culled active, 0 dangling prog/regr/proxy refs, 0 stale `sport_exercise_map` rows, EX176 at `0B-v1.6.10` (EX094 gone, EX180 kept).** #644 **CLOSED completed**.

---

## 2. STILL OWED
- **Nothing on #623 or #644** — both applied to prod, verified, and closed completed.
- PR #650 (this final applied+verified bookkeeping + this handoff) is auto-merging on green.

## 3. Side-findings this session
- **`validate_layer0` has NO exercises-FK validator.** It FK-checks only the disciplines family (`etl/layer0/validation/fk_checks.py` — `discipline_substitutes`, `discipline_training_gaps`). A dangling `progression_exercise_id` / `regression_exercise_id` / `physical_proxies[].exercise_id` / `sport_exercise_map.exercise_id` would **not** be caught by the gate; per-migration DO-blocks are the only guard today (0009's DO-block did this check itself). Filed as **#648**.

## 4. NEW issue filed this session
- **[#648](https://github.com/ahorn885/exercise/issues/648)** — add a standing exercises-FK validator to `validate_layer0` (assert every active exercise's progression/regression/proxy targets + every active `sport_exercise_map.exercise_id` resolve to an active exercise; fix-not-waive). Hardening — makes future culls regression-proof rather than relying on each migration's DO-block.

## 5. NEXT STEPS — "Locations & Gear" arc
- **[#619](https://github.com/ahorn885/exercise/issues/619)** — profile Locations tab + nav IA. Pure UI/IA.
- **[#648](https://github.com/ahorn885/exercise/issues/648)** — exercises-FK validator (Layer 0 hardening).
- **Carried (unrelated):** post-#572 live **T3 *refresh*** re-verify (Rule #14 — needs Andy's live hands + diag token).

## 6. Bookkeeping done this session
- **`CURRENT_STATE.md`:** #644 "Last shipped session" entry (applied+verified+CLOSED, names this handoff); #623 demoted to predecessor (done in #649); #648 recorded.
- **GitHub:** #623 + #644 closed completed (each commented with the apply+verify result); #648 filed. PRs #646/#647/#649 merged; #650 open (auto-merge).
- **`CARRY_FORWARD.md`:** no edit.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Migration | `etl/migrations/layer0/0009_cull_nontrainable_technical_skill.sql` | `CREATE TEMP TABLE _cull_exercises`; 10 ids (EX094/121/122/123/148/150/152/153/154/155); `(0B-i)` EX176 reinsert at `'0B-v1.6.10'` with EX094 stripped; `(0B-ii)` supersede culled; `(0B-iii)` supersede `sport_exercise_map`; verify DO-block RAISEs on dirty state |
| Repoint logic | same | `jsonb_array_elements(e.physical_proxies) ... WHERE elem->>'exercise_id' NOT IN (SELECT exercise_id FROM _cull_exercises)`; EX176 survivor check asserts EX094 absent + EX180 present |
| Map inert | `layer2c/builder.py`, `layer2d/builder.py` | `JOIN layer0.exercises e ... WHERE e.superseded_at IS NULL` (~`layer2c` L298 / `layer2d` L872) — superseding the exercise drops the mapping |
| FK gap | `etl/layer0/validation/fk_checks.py` | only disciplines-family FK checks; no exercises-FK validator → tracked in #648 |
| CI gate | `.github/workflows/ci.yml` (`layer0-gate`) | postgres:17, v1.8.0 baseline + `0006`–`0009`, `validate_layer0`; GREEN on PR #647 |
| Prod apply | — | `layer0-apply` run 27598426170 success; `neon-query` run 27615278864 → 55 / 0 / 0 / 0 / 0 / 1 |
| Issue #623 | — | CLOSED completed (0008 applied run 27596296178 + verified run 27596476996) |
| Issue #644 | — | CLOSED completed (0009 applied + verified) |
| Issue #648 | — | NEW — exercises-FK validator hardening |
| Owed | — | none on #623/#644; carried: post-#572 live T3-refresh re-verify (Rule #14) |
