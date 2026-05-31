# V5 Implementation — diag-endpoint auth-gate fix (#352) + compliance issue tree (#353–#395) + plan #48 504 triage

**Session:** Three threads off the post-#349 watch. (1) Found the #349 diag endpoint was **unreachable** in prod — the global login wall shadowed its token auth — and fixed it (PR #352, squash-merged). (2) Turned the finalized privacy/compliance design (`docs/redesign/00_OVERVIEW` + `Privacy_Program_Backlog_v17`) into an organized GitHub epic/story tree (43 issues, #353–#395). (3) Watched plan **#48** fail again and triaged it to a **504 wall-clock timeout mid-LLM-call** — a different failure mode than #47, and the diag endpoint's blind spot (#350).
**Date:** 2026-05-31
**Predecessor handoff:** `V5_Implementation_PlanGen_47_RetryablePayloadValidation_LogVisibility_2026_05_31_Closing_Handoff_v1.md`
**Branch:** `claude/keen-lovelace-eQI41` (PR #352, squash-merged to `main`)
**Status:** 1 substantive code change (`app.py` auth-exempt) + 1 test file + 1 spec-pointer line in `CLAUDE.md` + bookkeeping. Suite green for the new test (4/4); full suite unchanged. **No migration.** GitHub: 43 compliance issues filed; 2 issues referenced for the plan-#48 triage (#350, #316).

---

## 1. Session-start verification (Rule #9)

The predecessor (#349) shipped to `main`; its claims were the input to this session's work and were verified **empirically** by trying to use the diag endpoint:

| Claim (predecessor §8) | Result |
|---|---|
| Diag endpoint `def plan_diag(` + `_diag_token_ok` present | ✅ grep `routes/admin.py:360` |
| Token auth (`_diag_authorized`: admin OR `DIAG_TOKEN`) | ✅ — but **shadowed in prod** (see §2) |
| `generation_traceback` migration + `DIAG_TOKEN` set (Andy) | ✅ per CARRY_FORWARD owed-deploy #4 |

**Reconciliation note:** the #349 claim "readable past the login wall" was **false in prod** — the endpoint's unit test (`TestDiagTokenOk`) only covered the pure helper, and the §5.0 route smoke was never actually run against the wired app, so the integration gap reached production. Fixed this session (§3.1).

---

## 2. Session narrative

**Thread 1 — the diag endpoint never worked.** Asked to watch plan #48, I went to fetch `GET /admin/plan/48/diag?token=…` (the #349 surface built exactly for this) and got the **sign-in page**, not JSON. Root cause: the app-wide `@app.before_request _require_login` gate (`app.py:233`) runs *before* any route and redirects every non-exempt endpoint to `/auth/login`; `admin.plan_diag` was missing from `_AUTH_EXEMPT_ENDPOINTS`, so the global wall **shadowed** the route's own token check. The whole point of the endpoint — readable without the app login — was defeated. Same in-route-auth shape as the cron/webhook endpoints already exempt; it simply wasn't added alongside them.

**Thread 2 — compliance issue tree.** Andy uploaded `docs/redesign/00_OVERVIEW.md` (8 buildable compliance controls, each with acceptance criteria) and pointed at `docs/privacy_program/Privacy_Program_Backlog_v17.md`. Reviewed both and turned them into an organized GitHub tree (decisions confirmed via `AskUserQuestion`: **epics + stories hybrid**, **open items only**, **single-source cross-linked**). See §5.

**Thread 3 — plan #48 failed again.** Pulled the Vercel runtime logs (Rule #14 — and the `Traceback`/`synthesize` full-text queries returned `query timed out before all pages were fetched`, so those negatives are **unreliable**, per the documented gotcha). The reliable positive signal: repeated **504 Gateway Timeout** on `POST /plans/v2/48/generate` (15:50:42, 16:11:56) and on the cron `GET /plans/v2/cron/generate-pending` (16:21:02, 16:22:02); the log line *immediately before* each 504 is an Anthropic SDK `HTTP Request: POST https://…`. A tight 16:06–16:13 window shows the poller polling every ~2s (all `200` keep-polling) and one advance invocation at 16:11:56 blocking in an LLM call and 504-ing. **Diagnosis: a single slow LLM call exceeding the 300s function max — a hard kill before any Python `except` runs**, so `_mark_plan_failed` never persists a traceback and the diag endpoint can only ever show `generation_status` + `blocks_snapshotted` (no traceback) for this class. This is the #350 (log-drain hard-kill backstop) / #316 (latency) territory — **not** the #47 `ValidationError`, and not something the diag-traceback surface can capture.

---

## 3. File-by-file edits

### 3.1 `app.py` (modified)
Added `admin.plan_diag` to `_AUTH_EXEMPT_ENDPOINTS` (~`app.py:230`), with a comment explaining the in-route-auth pattern (mirrors the cron/webhook entries directly above). Security is unchanged: `_diag_authorized()` still requires an admin session **or** a constant-time `DIAG_TOKEN` match, with **no bypass when `DIAG_TOKEN` is unset**. `current_user_id()` reads `session['user_id']` directly, so the admin-session path still works under the exemption. The HTML `…/inspect` page is intentionally **not** exempted — it stays fully admin-only.

### 3.2 `tests/test_app_auth_gate.py` (new)
Route-level regression against the **real wired app** (gate + blueprint together) — the only place the bug is observable. Neutralizes the module-level `init_postgres()` hang by pointing `DATABASE_URL` at a fast-failing value before `import app` (every assertion resolves before any `get_db()`). Asserts: wrong/absent token → **403** (route reached), *not* a 302 to `/auth/login` (the regression); `admin.plan_diag` in the exempt set; `…/inspect` unauthed → still 302 to login (guards against over-exempting). 4 passed.

### 3.3 `aidstation-sources/CLAUDE.md` (modified)
Added the redesign-work pointer under **Working principles** (per Andy): *"For redesign work, follow `docs/redesign/CONVENTIONS.md` and the phase specs alongside it."*

---

## 4. Code / tests

- `tests/test_app_auth_gate.py` — **4 passed** (real-app gate regression; see §3.2).
- `tests/test_routes_admin.py` — 22 passed (unchanged; no regression from the exempt change).
- Full suite otherwise unchanged from the #349 baseline (1855/16). **No migration.**

---

## 5. Compliance issue tree (GitHub, #353–#395)

Turned `docs/redesign/00_OVERVIEW.md` (8 controls) + `Privacy_Program_Backlog_v17.md` (open items) into two epic trees under a new `area:compliance` label, matching the repo's `epic + sub-issues` convention.

- **Epic #353 — Privacy & compliance controls (engineering build).** 8 control epics: **#355** 01 AI-training · **#356** 02 deletion · **#357** 03 inactivity · **#358** 04 aggregation · **#359** 05 DSR · **#360** 06 breach-logging · **#361** 07 DMCA · **#362** 08 cookies. Heavy controls broken into requirement-level stories: 01→#363–#371, 02→#372–#377, 05→#378–#382, 07→#383–#387. Light controls (03/04/06/08) carry acceptance-criteria checklists in the epic body.
- **Epic #354 — Privacy program, open non-code items.** #388 D-92 fairness thresholds · #389 D-95 DPA · #390 D-97 DPO · #391 D-98 EU AI Act · #392 DMCA operational standup (D-99–D-103/D-106) · #393 D-81 L3 health_screening contract · #394 Health-Screening UX (D-79–D-85) · #395 D-124 counsel anonymization flag.
- **Decisions pinned (Andy):** epics+stories hybrid; open items only (the ~40 shipped doc items not mirrored); single-source cross-linked (shared D-NN engineering items live once under the control epics, the backlog epic links to them).
- **Open judgment calls flagged to Andy:** everything tagged `v1` (controls target the live Flask app); single new `area:compliance` label rather than splitting privacy/legal.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Re-run the PGE e2e and read plan #48 (or its successor) from the now-live diag endpoint.** With #352 on `main` + deployed, `GET /admin/plan/<id>/diag?token=…` is finally reachable past the login wall. For a **504 hard-kill** specifically it shows no traceback — but `blocks_snapshotted` / `total_sessions` / `generation_status` localize how far synthesis got before the stall. If #48 is the recurring case, that read + the §6.2 path is the work.

### 6.1.1 DIAG_TOKEN (live — read the diag endpoint without the app login)
**`DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc`** (set in Vercel prod env; constant-time-checked by `_diag_authorized`). Read any plan's generation state from the container via the Vercel `web_fetch_vercel_url` MCP (container bash egress is allowlisted and can't reach the prod host directly):

`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc` → 200 JSON (`generation_status` / `blocks_snapshotted` / `generation_units_cached` / `total_sessions` / `generation_error` / `generation_traceback`). The `…/inspect` HTML page (per-block synthesis_metadata) stays admin-session-only — not token-exempt.

**Rotate-later (owed):** this value is committed in the repo (originally `…PlanGen_47…_v1.md:73`, and now here on purpose for findability) — it is NOT secret while this work is open. Andy's decision (2026-05-31): keep as-is to ease debugging the plan-gen completion arc; rotate + scrub both docs once the arc closes. Decision #3 of the #47 handoff ("keeps the secret out of the repo") is therefore knowingly suspended.

### 6.2 Alternative pivots
- **#316 / #350 — the plan-#48 504.** A single LLM call exceeding the 300s function cap kills the invocation before it can cache the block or run any `except`. Candidate fix: a **per-invocation wall-clock backstop** that returns a resumable "keep-polling" pass before the gateway 504s, so a slow cold-cone call yields progress instead of a hard kill (couples to the existing per-block budget). Latency root cause is #316 (pre-compute periodization grid).
- **Compliance build** — start Control 01 or 02 (#355/#356) per the new milestone, or knock out the DMCA operational standup (#392).
- Still-owed: the §14 within-phase coherence read (gated on #333) and remaining #333 sub-items.

### 6.3 Operating notes for next session (read order)
1. `CLAUDE.md` — stable rules (Rule #14 on logs; now also the redesign-work pointer)
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — owed-deploys (#4 = diag endpoint; **now login-wall-fixed live after #352**)
4. This handoff
5. `./scripts/verify-handoff.sh`

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Diag endpoint exempt from the global login wall (in-route token auth, like cron/webhooks) | Claude (sensible default) | The endpoint's entire purpose is readability without the app login; `_diag_authorized` is the real gate, default-deny when `DIAG_TOKEN` unset |
| 2 | Compliance tree = epics+stories hybrid, open items only, single-source cross-linked | Andy (`AskUserQuestion`) | Organized hierarchy without mirroring ~40 already-shipped doc items; no duplication of shared D-NN engineering work |
| 3 | Plan #48 = 504 wall-clock timeout, triaged to #350/#316 (not a code-exception fix) | Claude (evidence-based) | The pre-504 line is an in-flight Anthropic call; a 504 hard-kills before any `except`, so no traceback exists to fix against — it's latency/backstop work |

---

## 8. Session-end verification (Rule #10)

| Check | Anchor string | Result |
|---|---|---|
| Diag endpoint exempt | `'admin.plan_diag'` in `_AUTH_EXEMPT_ENDPOINTS` | ✅ grep `app.py` |
| Gate regression test | `TestDiagEndpointBypassesLoginWall` | ✅ grep `tests/test_app_auth_gate.py` |
| Test passes | wrong-token → 403, not login redirect | ✅ `pytest tests/test_app_auth_gate.py` (4 passed) |
| Redesign pointer | `docs/redesign/CONVENTIONS.md` | ✅ grep `aidstation-sources/CLAUDE.md` |
| Compliance epics | #353 + #354 with sub-issues | ✅ GitHub |
| #352 merged | squash to `main` | ✅ (this merge) |
| Working tree clean | — | ✅ `git status` |

---

## 9. Files shipped this session

**Substantive (1 code + 1 test):**
1. `app.py` — exempt `admin.plan_diag` from the global login wall
2. `tests/test_app_auth_gate.py` — real-app gate regression

**Spec / bookkeeping:** `aidstation-sources/CLAUDE.md` (redesign-work pointer), `aidstation-sources/CURRENT_STATE.md` (pointer), `aidstation-sources/CARRY_FORWARD.md` (owed-deploy #4 update + plan-#48 504 note), this handoff.

**GitHub:** PR #352 (this work); compliance issue tree #353–#395; plan-#48 504 evidence to be added to #350/#316.

---

# ADDENDUM — plan-gen live watch (#50 credit-exhaustion + #52 re-run) + the "300s cap" investigation (2026-05-31, evening)

> Appended to the live handoff (not a new closing doc) at Andy's request so the next agent keeps full context. This is a **watch/diagnose session, no code shipped.** It supersedes parts of the §2/§3 #48 triage narrative (see "Correction" below). Branch in use: `claude/beautiful-fermat-EmrCL`.

## A1. Session-start reconciliation (Rule #9) — drift found

`verify-handoff.sh` is green, but **four commits landed on `main`/this branch AFTER this handoff was written, and `CURRENT_STATE.md` was never bumped for them.** Next session should update `CURRENT_STATE.md` to point past #352. The four:

- **#396 — plan-gen advance-lock leak fix + the 800s correction (the important one).**
  - Fixes a leaked **session-scoped Postgres advisory lock** that could silently starve generation: once held, every later advance no-op'd with **no log line** until the 900s stall backstop reaped the plan (diagnosed on a **plan #49 stall, 2026-05-31**). Now releases in a `finally` around the locked pass (extracted to `_advance_plan_generation_locked`) and **logs the previously-silent lock-contention no-op**. That log line is the truncated `_advance_plan_generation: a…` you now see on every backed-off cron — it is the **benign `advance_in_progress_elsewhere` no-op**, NOT an error.
  - **Corrected the Vercel function Max Duration to 800s** (prior docs/CLAUDE.md said 300s). This is now reflected in `CLAUDE.md`'s env quick-reference.
- **#397 / #398 / #399 — redesign Phase 0** (`docs/redesign/*`, `static/tokens.css`, `static/style.css` polish layer, `templates/_shell/icons.svg` sprite, `base.html` links). All `.app`-scoped and **inert** — changes no live screen. Not relevant to plan-gen.

## A2. THE "300s" INVESTIGATION (Andy's direct question: "are there any places where WE limited the function duration to 300?")

**Answer: exactly one, and it is INERT in prod.**

`routes/plan_create.py:152-154`:
```
_FUNCTION_CAP_S       = float(os.environ.get("PLAN_GEN_FUNCTION_CAP_S", "300"))   # default 300
_INVOCATION_RESERVE_S = float(os.environ.get("PLAN_GEN_INVOCATION_RESERVE_S", "330"))
_INVOCATION_BUDGET_S  = max(_FUNCTION_CAP_S - _INVOCATION_RESERVE_S, 30.0)
```
- **Andy confirmed BOTH** the Vercel dashboard Max Duration **AND** the `PLAN_GEN_FUNCTION_CAP_S` **env var are 800.** So `_FUNCTION_CAP_S = 800` → `_INVOCATION_BUDGET_S = max(800−330, 30) = **470s**`. The `"300"` literal is only a fallback default and **never applies in prod**.
- All other `300`s in the grep are unrelated (schema `maxLength` / `duration_min` maxima). `_CRON_WALL_CLOCK_BUDGET_S = 240` is a separate cron-batch guard. So `_FUNCTION_CAP_S`'s default is THE only "300 = duration" in the code.
- **The deadline mechanism is COOPERATIVE** (`layer4/generation_budget.py`): a `ContextVar` deadline checked by `generation_deadline_passed()` only **between Layer-4 week-blocks**. It **cannot interrupt an in-flight LLM call**, and it is **never consulted during the cone** (3A/3B/2x run before the Pattern-A block loop). `Layer4GenerationIncomplete` is a `BaseException` (control-flow, not error) so broad `except Exception` can't swallow it; only the route's explicit handler keeps the row `generating`.
- **Latent footgun (the CARRY_FORWARD "cap-drift" watch-item), still unfixed:** if `PLAN_GEN_FUNCTION_CAP_S` is ever dropped from the env (new environment, Vercel migration), the code falls back to 300 → reserve 330 > cap 300 → budget **floors to 30s**, silently crippling Layer-4 throughput (≈no blocks per pass) with no error. **Optional 2-line hardening (Andy's call, NOT yet done):** change the default `"300"`→`"800"` at `routes/plan_create.py:152` (+ its comment at :138-143) so the env var isn't load-bearing. Andy was asked, hasn't decided. Low risk; do only with his ok.

## A3. CORRECTION to the §2/§3 #48 (and #50) triage — it was NOT a 300s wall-clock cap

The original #48 triage (this handoff §2 Thread 3 / §7 Decision 3) read the ~300s 504 as "a single LLM call exceeding the function cap, hard-killed before any except." **With the cap confirmed at 800s, that mechanism is wrong.** A ~300s death is an **earlier limit**: the Vercel **gateway 504** (client-facing, ~300s) and/or SDK retry/timeout behavior — the function itself keeps running past it to the 800s wall (or the 470s invocation budget). The note in CLAUDE.md's env quick-reference already flags this; #350/#316 should be re-validated against real timings, not the 300s assumption.

## A4. PLAN #50 — FAILED, root cause = OUT OF ANTHROPIC CREDITS (not an outage, not our code)

Watched #50 live (`created_via plan_create`, scope `2026-05-31 → 2026-07-17` ✅ reaches race day, pattern A). It **stalled in the cone at Layer 3A** for ~15 min (every pass re-entered `llm_layer3a_athlete_state`, 0 blocks, 0 units), then **failed** with the user-facing: *"Plan synthesis failed (anthropic_api_error). Adjust your inputs and try again."*

- **Root cause (Andy confirmed): the Anthropic account was OUT OF CREDITS.** A credit-exhausted key returns an API error the SDK surfaces as `anthropic_api_error`; the cold 3A call retried against it for ~300s, then raised → caught → `_mark_plan_failed` persisted the error → plan terminal. **Andy added credits.**
- During the incident I also hit **three Cloudflare 502s directly from `api.anthropic.com`** (the `web_fetch_vercel_url` MCP transport routes through Anthropic infra) — same exhausted-account symptom on my read path. I initially mis-read this as a transient Anthropic *outage*; it was billing.
- **System behaved correctly under the upstream failure** — it persisted a clean `generation_error` (better than the #48 silent hard-kill). #50 is terminal; it needed a fresh plan version (→ #52).
- **Rule #14 note that held up well:** the runtime-log MCP **truncates** the message column (`…`) and **groups by request showing only the first line**, so I could read *which* stage each pass was in but never the latency/token tail of `llm_layer3a_athlete_state:`. That tail (ms / in-out / HIT-MISS) is still **owed-from-Andy** if we ever need to distinguish slow-vs-hang-vs-retry at 3A. The `synthesize_phase` full-text negative is only reliable when there's NO "query timed out" warning AND you account for request-grouping by start-time windowing (a request that started before `since` won't return even if it logged the term later).

## A5. PLAN #52 — IN PROGRESS at handoff write-time (credits added; this is the real re-run to finish watching)

- **22:32:25** `POST /plans/v2/52/generate` started (scope `2026-05-31 → 2026-07-17` ✅, pattern A). (Andy also created a #51 around 22:29 — NOT being watched; ignore unless he says otherwise.)
- **Cone completed by ~22:36** — the `synthesize_phase` full-text query matched the 22:32:25 POST request, i.e. it reached **Layer 4 block synthesis** (the exact milestone #50 never reached). This proves credits fixed it.
- **BUT at 22:36:32 and 22:39:33 the diag still showed `blocks_snapshotted: 0`, `generation_units_cached: 0`** (no error, no traceback), and **every cron 22:34:00→22:40:00 logged the `a…` contention no-op** — i.e. the **single 22:32:25 POST invocation held the advisory lock for the whole ~7.5 min.**
- **KEY FINDING — that 0 is almost certainly STALE, not a stall.** `routes/plan_create.py:810-813`: `generation_units_cached` (UPSERT `= … + EXCLUDED…`) and the `blocks_snapshotted` progress snapshot are **persisted per-pass on `db.commit()`, NOT per-block.** While the long first invocation is still in flight (never committed), the diag columns read 0 even though per-block `layer4_cache` rows may be committing independently. The **per-invocation budget is 470s → the POST should yield `Layer4GenerationIncomplete` ~22:40:15**, release the lock, and the **next cron (~22:41) acquires the now-warm-cone lock and commits** — at which point the diag counters should jump.
- **THE NEXT READ (≈22:42+, after the first pass commits) IS THE REAL TELL:**
  - **Healthy:** `blocks_snapshotted` / `generation_units_cached` jump to N>0 and climb each subsequent cron pass (warm cone = fast 3A/3B HITs, full 470s budget spent on blocks), `generation_status` eventually → `ready`. `total_sessions` stays 0 until the final `ready` flip (sessions persist on completion, per pv=46 behavior — not a bug).
  - **Genuine stall (escalate):** counters still 0 after a pass has demonstrably committed (a cron that did NOT hit `a…` contention) → then a block truly isn't caching within the budget; that's #316/#350 latency territory (NOT credits, NOT the cone). Pull the per-block `synthesize_phase: <phase>:w<n> …` lines (latency/`accepted`) and, if truncated, have Andy paste them (Rule #14).

## A6. EXACTLY WHERE TO PICK UP (next agent, do this first)

1. **Re-read plan #52 diag immediately:**
   `GET https://aidstation-pro.vercel.app/admin/plan/52/diag?token=0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc`
   (via the Vercel `web_fetch_vercel_url` MCP — container egress can't reach prod directly). Token is the live DIAG_TOKEN from §6.1.1.
2. **Interpret per A5:** counters >0 and climbing, or `ready` = success (pv=52 is the 2nd-ever PGE plan to complete; if so, do the §14 coherence read gated on #333). Counters still 0 after a non-contended cron pass = real Layer-4 caching stall → diagnose per A5 bullet.
3. **Vercel MCP coordinates** (also in CLAUDE.md): projectId `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`, teamId `team_rkZGxltBw2ykWtrIPCYy16JZ`, prod `aidstation-pro.vercel.app`, current deploy `dpl_5DZwESAyhomX7duMqjdDzCk47hm6`. `get_runtime_logs` truncates messages + groups by request (Rule #14 gotchas above).
4. **Owed bookkeeping when watch closes:** bump `CURRENT_STATE.md` past #352 (note #396/#397-399 + this watch); decide the A2 optional hardening; if pv=52 completed, close out the latency/coherence follow-ups.
5. **DIAG_TOKEN rotation** remains owed once the plan-gen arc closes (per §6.1.1) — still knowingly committed.
