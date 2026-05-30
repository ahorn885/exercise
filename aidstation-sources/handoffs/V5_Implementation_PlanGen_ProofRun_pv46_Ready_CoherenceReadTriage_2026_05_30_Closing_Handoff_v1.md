# V5 Implementation — Plan-Gen Proof Run (pv=46 → `ready`) + Coherence Read & Triage (2026-05-30) — Closing Handoff

**Session:** The proof run landed. Confirmed the six-link chain's last link (#332) was **already merged + deployed** (the predecessor handoff's "OPEN/CI-green" was stale), watched Andy's fresh PGE plan **pv=46 generate end-to-end and reach `ready`** — the **first PGE 2026 plan to complete in ~15 sessions** — then turned the win into the next agenda by triaging Andy's coherence read of the finished plan into the GitHub tracker. **No app code changed this session** (bookkeeping + issue triage only); suite unchanged.

**Headline:** **Completion is solved.** pv=46 ran cone (cache HIT) → Layer 4 blocks (mostly cache HITs replayed from pv=45, rebound to pv=46 by #332) → **clean persist, zero errors**, `ready` in ~7 min. **#324 (the completion blocker) is closed.** But the read proved **`ready` ≠ usable**: the plan completes while a large amount of computed intelligence never reaches the page. The blocker has **moved from "can it complete?" to "is what it produces correct and complete?"** — and most of those gaps were already-known *static-audit* findings (epic #295), now **empirically confirmed** by a real plan.

---

## 1. The proof run (pv=46)

- **Prereq already done:** #332 merged 2026-05-30 19:21 UTC; prod deployment `dpl_95uU2…` (commit `50bd3c7`) READY/production carries all six fixes. My branch `claude/v5-implementation-plan-mcYEL` was even with `main` (0/0). The Rule #9 sweep was clean.
- **Run:** `POST /plans/v2/new` 19:32:14 → **pv=46**; generate 19:32:15; 3A a cache **HIT** (cone warm from pv=39→45). Cron drove it from there; `ready` by ~19:39. Vercel error-level sweep over the whole 20-min window: **zero errors / 5xx / traceback / UniqueViolation / stall.**
- **Why fast:** pv=45 had synthesized the *full* plan before crashing at persist, so pv=46's blocks replayed as cache HITs (rebound to pv=46 via #332's `_hydrate_phase_result_with_meta` fix) → mostly hydrate-and-persist, which is exactly the step that used to crash. The persist guard held.
- **Log-visibility note for next session:** from the container, the Vercel `get_runtime_logs` full-text search reliably matches only **request-level** access lines + **error-level** prints (the granular `synthesize_phase`/`accepted`/`done` app prints did NOT surface via query). The plan's terminal status is best read from the **UI** (`/plans/v2/<id>` or `/admin/plan/<id>/inspect`), not the log query. (Note this is itself partly #333 — inspect is blank for `ready` plans.)

---

## 2. The coherence read — completion proven, coherence NOT signed off

Andy read the finished pv=46 plan against the design §14 / §5.2 coherence criteria. **Verdict: indeterminate, because the plan exposes no phase structure** (no phase labels in the UI → can't read whether weeks blend *within* a phase). Positives that DID hold: no duplicate days; **wrist constraint threaded throughout**; training schedule respected (no long days as set; "doubles regularly" honored); a peak+taper volume shape exists (~26h baseline → 34h@−2wk → 30h@−1wk). The §14 sign-off remains **owed**, gated on phase-label visibility (**#333**).

The read produced 17 notes. All triaged into the tracker (§3). The throughline: the plan generates *some* good programming but drops most of the pipeline's computed detail (nutrition, strength prescription, structured zones, substitution, notes-driven weighting) and has real correctness gaps (doesn't reach race day; prescribes an unselected skill; not on the plans list).

---

## 3. What was filed (the deliverable this session)

**Research-first:** swept all 102 open issues; most "missing from the plan" notes map onto the existing **orphaned-code epic #295** (children #296–#308: "builder computes X, nothing renders X") + the **Layer 2E nutrition** epic #210/#300 + **#306** (RaceEvent `notes` captured but never read). pv=46 is the empirical proof of that static audit.

**10 new issues (#333–#342):**

| # | Issue | Tier / labels |
|---|---|---|
| **#333** | Plan UI render gaps — phase labels, plans-list visibility, inspect-for-`ready`, sparse daily view | go-live · high · **milestone 1** |
| **#334** | Plan doesn't reach race day (pv=46 ends 2026-07-10, race 2026-07-17; missing race-week + taper) | go-live · high · **milestone 1** |
| **#335** | Strength sessions are bare labels; rx_engine + capacity records not wired | go-live · high · **milestone 1** |
| **#336** | Skill-capability not gating discipline assignment (roped climb/abseil prescribed, skill unchecked) | go-live · high · **milestone 1** |
| #337 | Cardio lacks structured zone-interval prescription | med |
| #338 | Discipline volume not proportional to race share (climb/abseil every week) | med |
| #339 | Synthesizer never substitutes equivalent disciplines for variety (only MTB, only trail) | med |
| #340 | Add "off-trail" terrain type — **Trigger #2/#3, decision required** | low |
| #341 | Recommend venue/location for equipment-gated sessions (needs spec) | low |
| #342 | Race form: terrain-associated discipline ≠ included discipline (Andy's #16 — validation question) | low |

**6 comments** (pv=46 empirical evidence + new-issue cross-links) on: **#316** (volume/periodization), **#306** (notes never read — broadened beyond the race-week brief to plan-gen), **#300** (nutrition dropped), **#289** (weather/Layer 5), **#298** (strength + skill-capability root), **#301** (equivalent-sport substitution).

**Closed #324** (`completed`) with the six-link chain (#325/#327/#329/#330/#331/#332) + pv=46 documented; Part B (latency) carried as **#316**. The **Go-live: PGE 2026 milestone (number 1)** is now 9 issues (was 5).

**One correction from Andy:** note #16 is NOT #317 (a vocabulary mismatch). His point is a data-model/validation question — *should the race form let you associate a discipline with a race terrain when that discipline isn't an included race discipline?* — filed as **#342**, not commented on #317 (no pv=46 evidence of #317's symptom).

---

## 4. Open / owed / next

**Coherence sign-off (§14) is still owed** — gated on **#333** (phase labels). Recommended first *fix*: **#333** (UI, low-risk, unblocks the coherence read), then **#334** (plan must reach race day — the most clearly broken). Both are go-live (milestone 1).

**Go-live blocker board (Tier 2):** #333, #334, #335, #336 (this session) + pre-existing **#303** (food-allergy safety) all in milestone 1. **Latency (#316)** is the remaining Part-B of the old completion blocker (Andy's call: pre-compute grid, not shrink blocks). Several new issues are **Triggers** (#340 data/cross-layer; #337/#338/#339 touch prompt bodies = Trigger #1; #341/#342 need spec/UX decisions) — stop-and-ask before implementing.

**Do NOT** start coding any of these without Andy pointing at a target — several are prompt/cross-layer Triggers, and the set far exceeds the 5-file ceiling.

**Owed Andy's-hands deploys** (unchanged this session except #1 resolved — see CARRY_FORWARD): the six-link proof run is **done**; remaining are the L3B `previous_attempts` migration + the K3 equipment / skill-capability ETL (the latter now also relevant to **#336**).

---

## 6.3 Operating notes — session-start reads (Rule #13)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling carry-state (owed-deploy #1 now DONE; the new go-live board is #333–#336 + #303).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

**First move next session:** the focus has shifted **off the completion blocker for the first time in ~15 sessions** — onto **plan usability/fidelity**. Tackle the go-live board (recommend #333 → unblocks the §14 coherence sign-off → then #334). The pipeline-fidelity gaps (#335/#337/#338/#339 + the #295/#300/#301/#306 audit roots) are the substance of "make the `ready` plan actually usable."

---

## 8. Verification table (Rule #10 — anchors for the next Rule #9 sweep)

| Claim | Where | Anchor / check |
|------|------|------|
| #332 merged + deployed (chain complete) | GitHub / Vercel | PR #332 `merged_at` 2026-05-30T19:21Z; prod `dpl_95uU2…` commit `50bd3c7` |
| #324 closed (completion solved) | GitHub | issue #324 state `closed`, reason `completed`; close comment lists #325/#327/#329/#330/#331/#332 |
| 10 new issues filed | GitHub | #333–#342 exist; #333/#334/#335/#336 carry `priority:high` + milestone 1 |
| 6 evidence comments | GitHub | comments on #316, #306, #300, #289, #298, #301 referencing pv=46 |
| Go-live milestone | GitHub | milestone 1 "Go-live: PGE 2026" open_issues = 9 |
| Coherence §14 NOT signed off | this handoff §2 | gated on #333 (phase labels) |
| No app code changed | git | branch `claude/v5-implementation-plan-mcYEL`; suite unchanged; no migration |
| CURRENT_STATE pointer repointed | `CURRENT_STATE.md` | "Last shipped session" = this handoff; six-link handoff demoted to predecessor |
| CARRY_FORWARD owed-deploy #1 | `CARRY_FORWARD.md` | item 1 marked ✅ DONE (proof run complete, #324 closed) |

No PRs this session. No migration. Suite unchanged (no code touched).
