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
