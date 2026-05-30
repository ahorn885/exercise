# V5 Implementation — Discipline/Sport Canon Cleanup + Plan-Gen Observability + Resilience + PGE Verification — Closing Handoff (2026-05-30)

**Session:** One long arc that (1) shipped the Layer-0 discipline/sport canon cleanup, (2) built plan-gen observability, (3) merged the staged Neon/quality fixes, (4) ran the **first end-to-end PGE 2026 plan-gen verification** in prod, diagnosed its failure with the observability just shipped, and (5) shipped the resilience fix for that failure. Six PRs merged (#314, #315, #319, #322, #323, #325); three issues filed (#320, #321→closed, #324); one branch of bookkeeping (this).

**All app code is on `main` and deployed.** Andy ran the one owed DB migration + ETL this session — Layer 0 is live on the new canon. No owed deploys remain.

---

## 1. What shipped (merged + deployed)

| PR | What | Notes |
|----|------|------|
| #314 | Neon idle-connection resilience (reconnect-retry + keepalives) | staged pre-session; merged. Fixes the SSL-drop 500/lost-block. |
| #315 | Plan-gen quality: anti-truncation token headroom + taper-aware volume_band | staged pre-session; merged. |
| **#319** | **Layer 0 discipline/sport canon cleanup** | the session's big one — see below. **DB migrated + ETL re-run (`--version-tag 1.3.1`) by Andy; live.** |
| #322 | Remove the `--version-tag 1.3` ETL footgun (uniform tag→version mapping) | the `1.3` special-case mapped to the retired `0A-v11.0` lineage; removed. |
| #323 | Plan-gen observability (#321) — durable `plan_progress_blocks` + admin inspect + block-content logging | auto-creates the table on cold start; no migration. |
| #325 | Plan-gen resilience (#324) — retry a fumbled block + return-before-cap | merged this turn; deploys on cold start, no migration. |

### #319 canon cleanup — the durable change set
- **Disciplines 25 → 21.** Removed D-025 Fencing, D-026 Laser Run, D-029 Rifle Shooting (`REMOVED_IDS`). Folded D-015 Orienteering → D-003, **renamed "Trekking"** (`ID_REMAP`). `etl/layer0/discipline_canon.py`.
- **New curated `endurance_profile`** per discipline (`DISCIPLINE_ENDURANCE_PROFILE` in the canon, stamped at ETL) replacing the junk free-text `discipline_category` (dropped). Layer 2E `_endurance_profile` reads the column directly; `_CATEGORY_ENDURANCE` deleted. Migration `etl/sources/migrate_disciplines_endurance_profile_v1.sql` (run by Andy).
- **New `etl/layer0/sport_canon.py`** — `REMOVED_SPORTS = {Modern Pentathlon, Biathlon}` cascaded across all sport-keyed tables in `run.py`. Sports finally have a code-side canon like disciplines.
- **Navigation conditional retired** (`_NAV_DISCIPLINE_ID` gone; sleep-dep flag now always False — the real overlay is event-duration-driven in 2E). OCR exercise alias re-homed to Off-Road / Adventure Multisport.
- Full suite green; `Layer2E_Spec.md` §5.3.3/§5.4.3 amended.

---

## 2. The PGE 2026 verification run (pv=39) — the headline outcome

First real end-to-end plan generation in prod, on the post-cleanup deploy. **It generated 7 clean week-blocks then failed on the 8th** — and the failure was diagnosed entirely from the #323 observability (admin `/plans/v2/39/inspect` + per-block `plan_progress_blocks` metadata + Vercel logs).

**Validated by the 7 weeks:** the canon cleanup (clean disciplines, no Fencing/pentathlon/biathlon), observability (per-block snapshot rendering live), and Layer 2D injury accommodation (wrist constraint in the sessions).

**The failure = the go-live blocker, now precisely characterized (issue #324):**
- **Too fragile:** the 8th block came back unparseable (`schema_violation`) → `_mark_plan_failed` **discarded all 7 good weeks**. Separately, two passes ran the **800s Vercel cap and 504'd**, losing the in-flight block (the reserve was 255s, barely over a 249s block).
- **Too slow:** every block was a single 156–249s call emitting 10–16k output tokens (`cap_hit=True, retries_used=0`). A 7-week plan is a 20–30 min grind, and the slowness is what pushes functions into the 800s wall.
- **Ruled out — cache-key drift (the suspected #3):** an Explore agent + direct verification confirmed every hashed cone input is day-anchored (`as_of` = midnight `orchestrator.py:237`; `Layer2EPayload.computed_at` = date-only `layer2e/builder.py:1156`; `last_sync` anchored #294). The repeated `llm_layer3a_athlete_state` logs were **benign cache HITs, not re-runs**. The cone is deterministic. (One latent hardening left: defensively day-anchor `as_of` *inside* `assemble_layer3a_integration_bundle` so a future caller can't reintroduce drift — low priority, not active.)

### #325 — the resilience fix (this turn)
- **1a:** a block-fumble (`Layer4OutputError` code ∈ `{schema_violation, synthesis_budget_exhausted}`) no longer fails the plan — `_advance_plan_generation` keeps it `generating` and the next resumable pass re-attempts the block with a fresh call (cached blocks replay as HITs). **Bounded by the existing 15-min stall backstop** (persistent failure → clean `failed`). Never ships a broken block. Only block-fumble codes resume; other codes / `Layer4InputError` still fail fast.
- **1b:** `_INVOCATION_RESERVE_S` 255 → 330 so a block started near the deadline finishes before the 800s cap (no more 504/lost work).
- `routes/plan_create.py` + `tests/test_routes_plan_create.py` (+4 net). Full suite **1993 passed / 16 skipped**. No migration.

---

## 3. Issues

- **#320** (open) — Retire the `Sports_Framework` xlsx as Layer 0 source-of-record → version-controlled code/SQL seeds. Future, low priority.
- **#321** (CLOSED, completed by #323) — plan-gen observability.
- **#324** (open) — the plan-gen completion blocker. Its **resilience half is shipped (#325)**; its **latency half is #316**.
- **#316** (open, `status:designed`) — the per-week pre-compute periodization grid (the latency cure). **Andy's call: pre-compute, not shrink blocks.**
- **#317** — its `discipline_category` root cause (A) was fixed by #319; the independent `sport_locale_incompatible` half (B) remains open. (Not narrowed this session.)

---

## 4. Key decisions captured (Andy, 2026-05-30)

- Canon: remove D-025/026/029, keep D-027 OCR + D-028 XC Skiing; fold Hiking+Orienteering → Trekking; **drop** the nav conditional; remove Modern Pentathlon + Biathlon **as sports** via a code-side canon; all 21 `endurance_profile` values confirmed.
- Observability: T1 **+ T2**, **admin** surface only (no athlete-facing partial view).
- Plan-gen completion fixes: **#1** retry a fumbled block, **never** ship a "needs review" broken block; **#2** pre-compute (the grid), not block-size reduction; **#3** pin the data (investigated → already pinned; cone deterministic).
- **#303 (food_allergies) is parked** — explicitly de-prioritized.

---

## 5. Open / owed / next

**Owed (Andy's hands):** nothing new. The #319 migration + ETL are done. #323/#325 deploy on cold start (no migration).

**The single most important next action: verify #325.** Generate a fresh PGE 2026 plan and confirm it **reaches `ready`**. #325 should let the pv=39 scenario complete (fumbled block retries instead of killing the plan; no 504 loses work). That run is the proof the go-live blocker is cleared.
- If it completes (even slowly ~20–30 min) → plan-gen is **functional**; #316 becomes a UX/speed optimization, schedulable.
- If it doesn't → the observability (admin inspect + the block metadata) will show where; reassess.

**Then #316** (the pre-compute grid) for speed — the next real build, only if 20–30 min generation is too slow for the timeline.

**Do NOT pre-build #316** — verify #325 first; the result decides #316's urgency.

---

## 6.3 Operating notes — session-start reads (Rule #13)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling carry-state (owed deploys = none new).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

**First move next session:** the #325 verification run (above), unless Andy redirects. Plan-gen completion (#324/#316) is the live go-live blocker; the canon/observability/data work is done and validated.

---

## 8. Verification table (Rule #10 — file:line anchors for the next Rule #9 sweep)

| Claim | File | Anchor / check |
|------|------|------|
| Disciplines 25→21, Trekking fold, removals | `etl/layer0/discipline_canon.py` | `CANONICAL_NAMES` has 21; `"D-003": "Trekking"`; `REMOVED_IDS` ⊇ {D-025,D-026,D-029}; `ID_REMAP["D-015"]=="D-003"` |
| Curated endurance map | `etl/layer0/discipline_canon.py` | `DISCIPLINE_ENDURANCE_PROFILE` (21 entries); `assert set(...)==set(CANONICAL_NAMES)` |
| Sport canon | `etl/layer0/sport_canon.py` | `REMOVED_SPORTS = frozenset({"Modern Pentathlon","Biathlon"})`; `filter_sport_rows` |
| endurance_profile column swap | `etl/layer0/schema.sql` | `endurance_profile TEXT` on `layer0.disciplines`; no `discipline_category` |
| 2E reads the column | `layer2e/builder.py` | `_endurance_profile` reads `d.endurance_profile`; no `_CATEGORY_ENDURANCE` |
| Nav conditional retired | `layer2a/builder.py` | no `_NAV_DISCIPLINE_ID`; `sleep_dep_relevant = False` |
| Observability table | `init_db.py` | `_PG_MIGRATIONS` has `CREATE TABLE IF NOT EXISTS plan_progress_blocks` |
| Snapshot + admin view | `plan_sessions_repo.py` / `routes/admin.py` | `snapshot_progress_blocks` / `load_progress_blocks`; `/admin/plan/<id>/inspect` |
| Resilience: block-fumble resumes | `routes/plan_create.py` | `_RETRYABLE_BLOCK_CODES`; the `isinstance(exc, Layer4OutputError) and exc.code in _RETRYABLE_BLOCK_CODES` branch returns `'generating'` |
| Reserve 255→330 | `routes/plan_create.py` | `_INVOCATION_RESERVE_S` default `"330"` |
| Version-tag de-footgun | `etl/layer0/run.py` | no `tag == "1.3"` branch; `_version_strings()` uniform |

Full suite at session end: **1993 passed / 16 skipped**.
