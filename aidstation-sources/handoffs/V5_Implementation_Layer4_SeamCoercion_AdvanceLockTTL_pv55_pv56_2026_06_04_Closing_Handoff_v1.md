# V5 Implementation — Layer 4 seam-verdict coercion + TTL advance-lock (pv=55 / pv=56 cold-plan triage)

**Date:** 2026-06-04
**Branch:** `claude/layer4-strength-phase2-U2btL`
**PRs:** #416 (seam coercion + logging hardening — **merged** `3ce7ed3`), #419 (TTL advance-lock — **merged**)
**Issues:** #417 filed+closed (seam-fatal bug, by #416); #418 filed (Layer 4 observations have no reader, deferred, under #295).

---

## 1. What this session was

Andy ran two fresh cold PGE plans on prod to validate the Phase 1 `sport_locale_incompatible` fix (PR #413). Both failed; each failure was root-caused from the diag endpoint + Vercel runtime log + the `/admin/plan/<id>/inspect` block view, fixed, and shipped. **The Phase 1 fix is validated** — both plans sailed far past pv=54's stall-at-0. Two *new*, distinct go-live blockers were found and fixed:

1. **pv=55** synthesized **70 sessions / 6 blocks**, then died at the **seam reviewer** on `seam_reviewer_invalid_verdict_combination` — a single advisory LLM mislabel (`patched` + `accept_with_observation`) that was **not** in the route's `_RETRYABLE_BLOCK_CODES`, so it killed a near-complete plan on the FIRST occurrence. → **PR #416**.
2. **pv=56** cached only **1 block / 10 sessions**, then was failed by the 900s stall backstop. Root cause (confirmed, not latency — block 0 was a clean 169s, 0 retries): the per-plan **advance-lock leaked**. It was a session-scoped `pg_advisory_lock`; the pass that cached block 0 was 504/SIGKILLed before its `finally` release, and on Neon's transaction pooler the lock survived on the parked backend → every later cron fire no-op'd on "advance lock held elsewhere" → zero progress → stall. → **PR #419**.

Neither blocker touches the other; the seam fix (#416) was **never reached** on pv=56 (died upstream on the lock), so it remains valid and unexercised in prod.

---

## 2. PR #416 — seam-verdict coercion + non-retryable logging (merged)

- **`layer4/seam_review.py`:** replaced the raise-based `_validate_verdict_combination` with **`_coerce_verdict_combination`**, which normalizes every invalid `(verdict, direction)` combo to the nearest valid one and logs the coercion. A seam review is *advisory* (it judges a transition between two already-validated phases), so an LLM mislabel must never discard valid synthesis. Coercion table:
  - `patched` + `accept_with_observation` → `flagged_major` + `accept_with_observation`
  - `flagged_major`/`patched` + null → `flagged_major` + `accept_with_observation`
  - `approved` + issues → `flagged_minor`
  - `approved`/`flagged_minor` + direction → drop direction
  Only a genuinely unparseable `reviewer_verdict` enum still raises (`schema_violation`, which the route already retries).
- **`routes/plan_create.py`:** the **non-retryable `Layer4OutputError` branch** now logs `exc.code`+`exc.detail` AND persists `traceback.format_exc()` to `generation_traceback` (mirrors the Layer3 branch). This was the Rule #14 blind spot that made pv=55 hard to read — the diag endpoint returned `generation_traceback: null` because that branch dropped the detail.
- **`aidstation-sources/Layer4_Spec.md` §6.2:** verdict table updated from "raises" to "coerced," with the coercion table + pv=55 history.
- **Tests:** `tests/test_layer4_plan_create.py::TestSeamReviewInvalidCombinations` rewritten (assert coercion + full table).

## 3. PR #419 — TTL advance-lock (merged)

Replaced the leak-prone session `pg_advisory_lock` with a **TTL/heartbeat claim** on a new `plan_versions.advance_lock_until TIMESTAMPTZ` column:

- **Acquire** (`_try_acquire_advance_lock`): atomic conditional `UPDATE plan_versions SET advance_lock_until = now() + (? * interval '1 second') WHERE id = ? AND (advance_lock_until IS NULL OR advance_lock_until < now()) RETURNING id`. A row ⇒ won (Postgres row-locks the row so exactly one of N racing cron/poller fires wins).
- **Release** (`_release_advance_lock`): `UPDATE … SET advance_lock_until = NULL WHERE id = ?` in the existing `finally`.
- A SIGKILLed pass can't clear the stamp, but it **lapses after `_ADVANCE_LOCK_TTL_S`** and the next cron reclaims — a leak self-heals in ≤ TTL instead of starving until the stall backstop.
- **`_ADVANCE_LOCK_TTL_S = min(_INVOCATION_BUDGET_S + 280, _STALL_WALLCLOCK_S − 60)`** — derived from the budget so it always exceeds the longest a live pass can hold the claim (never robs a working pass) yet stays under the 900s stall window (a leak always recovers before the stall). Env-tracking via the budget.
- **Tests:** `tests/test_plan_create_concurrency.py` + `tests/test_routes_plan_create.py` updated to the new claim contract (UPDATE…RETURNING id; release clears the column). **65 passed** in those two files.

---

## 4. The pv=56 latency finding (carry-forward, NOT fixed this session)

The block-0 inspect (`latency_ms=168657`, 0 retries, `cap_hit=False`) plus the cron log proves the budget is **mis-sized vs the real ceiling**: `_INVOCATION_BUDGET_S = _FUNCTION_CAP_S − _INVOCATION_RESERVE_S`. With `PLAN_GEN_FUNCTION_CAP_S` set to **800** in prod env, budget = **470s**, but the real kill is the **~300s Vercel gateway** (the lambda's response is 504'd there; block 0 cached ~9 min after the 23:37 gateway 504 only because the cron resumed it). So a pass *starts* block N+1 after block N (169s × 2 ≈ 338s) and gets gateway-killed mid-flight — which is exactly what triggered the lock leak.

**The TTL lock makes completion correct regardless** (each pass banks its frontier block before the kill; the lock self-heals). But **setting `PLAN_GEN_FUNCTION_CAP_S=300` in Vercel** (so a pass returns after ~1 block, before the gateway) would make passes bank cleanly and the leak *rare* rather than load-bearing — faster + less wasted Anthropic spend. This validates the CLAUDE.md "re-validate the 800s-cap triage against real timings" note: the effective ceiling is the ~300s gateway, not 800s. Tracked as an env-tuning item in CARRY_FORWARD; reversible; Andy's call.

---

## 5. Issues

- **#417** (`layer:4 type:bug priority:high`) — seam-reviewer invalid verdict combo was fatal. **Closed `completed`** by #416.
- **#418** (`layer:4 type:bug priority:med v2 status:deferred`, part of #295) — **Layer 4 `notable_observations` have no reader.** Traced every consumer: only `layer4/telemetry.py` (metric counts) + an internal dedup check read them. No template/route surfaces them; nothing interprets `elevates_to_hitl` on a Layer 4 observation; the Layer 3.5 HITL gate runs *before* Layer 4 so it can't see them; the spec's "escalate to next-run HITL gate" is unwired. So the seam reviewer's `accept_with_observation`/`seam_unresolved` escalate **into the void**. This *simplified* the #416 fix (graceful degrade is correct because nothing downstream listens). Real fix = give Layer 4 observations a reader.

---

## 6. Owed (Andy's hands) + next moves

### 6.1 Owed deploys
1. **Apply the #419 migration on Neon** (see CARRY_FORWARD item) — `ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS advance_lock_until TIMESTAMPTZ`. **Must land before/with the #419 deploy** — the claim/release SQL needs the column. (Container can't reach Neon.)
2. **Optional env tune:** set `PLAN_GEN_FUNCTION_CAP_S=300` in Vercel (§4).

### 6.2 Next moves (4-tier)
- **Tier 2 (go-live):** re-run a fresh cold PGE plan after the #419 deploy + migration. Expect it to bank a block per pass and grind to `ready` — finally exercising the seam fix. Read via `GET /admin/plan/<id>/diag?token=…`; if the coercion fires, the runtime log shows `review_seam: coerced invalid seam verdict combination …`.
- **Tier 2/3:** the latency itself (#316) and #418 (observations have no reader) remain.
- **Tier 4:** **Phase 2 strength programming** (`Layer4_StrengthProgramming_Phase2_Design_v1.md`, #335) — spec signed off, ready to implement *once a cold plan completes* so it's built on a plan that finishes. Strength is still bare/empty until then (expected, not a regression).

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (note the new #419 migration + env-tune)
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

---

## 7. Test / verification state

- `tests/test_plan_create_concurrency.py` + `tests/test_routes_plan_create.py`: **65 passed** (full lock + route surface).
- `tests/test_layer4_telemetry.py` + the seam coercion table test: green.
- `tests/test_layer4_plan_create.py` has **pre-existing date-stale failures** (`plan_start_date_in_past` — the container sim clock is 2026-06-04; fixtures hardcode an earlier `_PLAN_START`). These fail identically with/without this session's changes (verified by stash). **Not introduced here**; flagged as a separate fixture-staleness nit.
- No live-DB / LLM run from the container (Neon egress blocked).

---

## 8. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Seam coercion replaces the raise | `layer4/seam_review.py` | `grep -n "_coerce_verdict_combination" layer4/seam_review.py` → def + call site (~`:590`) |
| Coercion wired into `review_seam` | `layer4/seam_review.py` | `verdict, direction = _coerce_verdict_combination(` present; no `_validate_verdict_combination` remains |
| Non-retryable L4 branch logs + persists traceback | `routes/plan_create.py` | `grep -n "Layer4 {type(exc).__name__}" routes/plan_create.py` in the non-retryable branch + `traceback_text=traceback.format_exc()` |
| Spec §6.2 updated to coercion | `aidstation-sources/Layer4_Spec.md` | `grep -n "coerced.*not raised\|_coerce_verdict_combination" Layer4_Spec.md` (line ~1023) |
| TTL advance-lock claim | `routes/plan_create.py` | `grep -n "advance_lock_until = now()" routes/plan_create.py` (UPDATE…RETURNING id) |
| TTL constant derivation | `routes/plan_create.py` | `grep -n "_ADVANCE_LOCK_TTL_S = min(" routes/plan_create.py` |
| No advisory-lock left | `routes/plan_create.py` | `grep -n "pg_advisory\|_ADVANCE_LOCK_NS" routes/plan_create.py` → no matches |
| Migration present | `init_db.py` | `grep -n "advance_lock_until TIMESTAMPTZ" init_db.py` |
| Lock tests on new contract | `tests/test_plan_create_concurrency.py` | `grep -n "advance_lock_until = NULL\|RETURNING id" tests/test_plan_create_concurrency.py` |

---

*End of handoff.*
