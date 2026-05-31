# V5 Implementation — Plan-gen #47: retryable Layer 4 payload validation + log-visibility diag endpoint

**Session:** Watched the post-#334 PGE e2e (plan #47). The plan reached race day (3B fix confirmed live) but generation crashed; root-caused a latent Layer 4 error-handling gap, fixed it, then built the log-visibility surface that the triage proved we needed, and added a standing rule for log access.
**Date:** 2026-05-31
**Predecessor handoff:** `V5_Implementation_Layer4_ReachRaceDay_TerminalTaper_334_2026_05_31_Closing_Handoff_v1.md`
**Branch:** `claude/e2e-test-run-alnUX` (PR #349, squash-merged to `main`)
**Status:** 5 substantive files (1 Layer 4 code, 2 v1-app code, 1 migration, 2 tests counted as the test pair) + 1 spec amendment + bookkeeping. Suite **1855 / 16**. Migration owed (applied by Andy this session). 2 follow-ups filed (#350, #351).

---

## 1. Session-start verification (Rule #9)

The predecessor (#334) shipped to `main` and its claims were verified **empirically** by this session's e2e rather than by an anchor sweep:

| Claim (predecessor §8) | Result |
|---|---|
| `c3f14b3` (#334) + `e29053c` (#345) on `main` | ✅ `git log` |
| Prod running the post-#334 build | ✅ newest `target:production` deployment = `e072b45` (bookkeeping atop #334), READY |
| 3B race-day-inclusive ceil reaches race day | ✅ **plan #47 scope = 2026-05-31 → 2026-07-17** (47-day gap → `ceil(48/7)=7` weeks, ends exactly on race day) |

**Reconciliation note:** clean. The #334 horizon fix is confirmed live; the Taper allocation was not separately re-verified because gen crashed before producing sessions (see §2).

---

## 2. Session narrative

Watched the fresh PGE e2e (plan #47). The scope confirmed #334 works (spans through race day). But generation went `failed` with **0 blocks / 0 sessions** and the opaque "Plan generation failed unexpectedly."

**Diagnosis — and the log-access wall.** The Vercel runtime-log MCP truncates the message column, groups by request, and has an unreliable-negative full-text search (the documented CLAUDE.md gotcha). I narrowed it to the generic `except Exception` in `_advance_plan_generation` (the `unexpected …` + `Traceback` + `_advance_plan_generation` matches in the 11:40:20 cron pass) and ruled out the usual suspects by probing — but the probe negatives were *unreliable* and the admin inspect page sat behind the app login (I hit the sign-in wall via `web_fetch_vercel_url`). I could not read the actual exception. **Andy pasted the raw traceback**, which named it instantly: a pydantic `ValidationError` — `Layer4Payload: "max 2 sessions per day (got 3)"`.

**Root cause (latent, exposed by #334).** `synthesize_phase` wraps the per-**row** `PlanSession` parse in `try/except → Layer4OutputError("schema_violation")` (retryable), but the `_build_payload_for_validation` construction — where the **top-level cross-session** `@model_validator`s (`_check_two_per_day` et al.) fire — sat *outside* that wrapper. A raw `ValidationError` escaped the typed-error contract → the route catch-all marked the whole plan terminally failed over one bad block. Latent until #334 ran the first **cold cone** synthesizing fresh blocks; the warm-cache pv=46 replayed cached blocks and never re-built a payload from a live fumble.

**Three workstreams shipped** (Andy chose: log option 1 build + #47 fix scope "wrap now, clamp later"):
1. **#47 fix** — wrap the payload construction so *every* top-level invariant violation becomes a retryable `schema_violation`.
2. **Log-visibility (Rule #14, option 1)** — persist the full traceback + a token-gated `/admin/plan/<id>/diag` JSON endpoint readable without the app login.
3. **CLAUDE.md Rule #14** — ask, don't infer, on logs.

---

## 3. File-by-file edits

### 3.1 `layer4/per_phase.py` (modified)
Wrapped the `_build_payload_for_validation(...)` call in `synthesize_phase` (~line 1725) in `try/except ValidationError`, mirroring the parse-step handling directly above: record a `schema_violation` `RuleFailure` and `continue` to retry in-loop; after `capped_retries`, raise `Layer4OutputError("schema_violation", …)`. `schema_violation ∈ _RETRYABLE_BLOCK_CODES` (`routes/plan_create.py:161`), so the block re-synthesizes on the next resumable pass instead of discarding the plan.

### 3.2 `routes/plan_create.py` (modified)
`_mark_plan_failed` gained an optional `traceback_text`, persisted to `plan_versions.generation_traceback` in its **own isolated, best-effort** statement (a missing column pre-migration or any write fault can NEVER turn the failure path into a 500 — the user-facing failure is already committed). The generic `except Exception` in `_advance_plan_generation` now passes `traceback.format_exc()`.

### 3.3 `routes/admin.py` (modified)
`GET /admin/plan/<id>/diag` → JSON (control row + full `generation_traceback` + block-snapshot summary). Auth via `_diag_authorized()`: admin session **or** constant-time `_diag_token_ok(supplied, os.environ['DIAG_TOKEN'])` (header `X-Diag-Token` or `?token=`). No token bypass when `DIAG_TOKEN` is unset. `generation_traceback` is read in a separate best-effort query so the endpoint works pre-migration.

### 3.4 `init_db.py` (modified)
`_PG_MIGRATIONS`: `ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_traceback TEXT` (idempotent, nullable).

### 3.5 `aidstation-sources/Layer4_Spec.md` (amended in place)
§5.5 schema-violation special case: **#47 amendment** — "malformed structured output" now explicitly covers BOTH the per-row parse AND the top-level `Layer4Payload` `@model_validator` invariants; both raise a retryable `schema_violation`. Names the per-day clamp as a follow-up.

### 3.6 `aidstation-sources/CLAUDE.md` (Rule #14 added)
NON-NEGOTIABLE Rule #14 — log access: ask, don't infer. (1) signal not logged → propose the exact instrumentation, ask to add it; (2) log exists but unreachable → ask for the specific line/panel. A negative from a tool with a known reliability gotcha is not evidence of absence.

---

## 4. Code / tests

Suite **1855 passed / 16 skipped** (+4 from the predecessor's 1851).
- `tests/test_layer4_plan_create.py::TestTopLevelPayloadValidationRetryable` — 3 cardio sessions on one day (indices ∈{0,1} so each row parses; the cross-session count rule trips at payload build) → retried the full cap (3 attempts) → raises `Layer4OutputError("schema_violation")`, **not** a raw `ValidationError`. Asserts `code == "schema_violation"` and `"2 sessions per day" in detail`.
- `tests/test_routes_admin.py::TestDiagTokenOk` — pure token-gate helper (no token configured → deny; mismatch/empty → deny; exact match → allow). Route smoke deferred to manual §5.0 per the module precedent.

---

## 5. Manual §5.0 verification steps

1. **Owed migration — DONE this session (Andy):** `generation_traceback` column applied on Neon.
2. **`DIAG_TOKEN` — DONE this session (Andy):** set in Vercel (value `0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc`, shared with Claude). Redeploy lands on the PR #349 merge.
3. **Re-run the PGE e2e (fresh `pv`)** once #349 is deployed. Expect: the >2/day fumble (if it recurs) is now *retried*, not fatal; the plan progresses past it. If anything else throws, fetch `GET /admin/plan/<pv>/diag?token=…` (via `web_fetch_vercel_url`) and read `generation_traceback` directly — no more hand-pasting.
4. **Diag endpoint smoke:** `/admin/plan/<id>/diag` with no auth → 403; with `?token=<DIAG_TOKEN>` → 200 JSON; an admin-session browser hit → 200.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Re-run the PGE e2e and read the result from the diag endpoint.** The #334 reach-race-day fix + the #47 resilience fix are both live after #349; this is the run that should finally produce a usable event-mode plan spanning to 2026-07-17 with a 2-week Taper. Then the **§14 within-phase coherence read** (still owed since pv=46) and the remaining **#333** sub-items.

### 6.2 Alternative pivots
- **#351** (per-day clamp) — if the re-run shows the >2/day fumble recurring and burning retry passes, build the clamp so it self-heals without a retry.
- **#350** (log-drain backstop) — only if a hard-kill (504/OOM before the except runs) failure shows up that the diag endpoint can't capture.
- **#347** (event-mode overshoot clamp), **#316** (latency / pre-compute grid).

### 6.3 Operating notes for next session (read order)
1. `CLAUDE.md` — stable rules (now includes **Rule #14**)
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (owed-deploys #4 = the diag endpoint's two activation steps, both done this session)
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Log-visibility = **option 1** (in-app durable diag endpoint) now; log-drain (option 2) deferred to #350 | Andy | Smallest build, durable across log eviction, full fidelity, token-readable; drain is the completeness backstop only if a hard-kill case appears |
| 2 | #47 fix = **wrap now, per-day clamp later** (#351) | Andy | The wrap is the structural safety net covering all invariants; the clamp silently drops an LLM-emitted session, so it wants its own deliberate change |
| 3 | Token via `DIAG_TOKEN` env secret, shared in chat; no token bypass when unset | Claude (sensible default) | Keeps the secret out of the repo; default-deny so the endpoint is safe before the token is set |

---

## 8. Session-end verification (Rule #10)

| Check | Anchor string | Result |
|---|---|---|
| #47 wrap present | `except ValidationError as e:` around `_build_payload_for_validation` | ✅ grep `layer4/per_phase.py` |
| Retryable, not fatal | `Layer4Payload invariant violated` | ✅ grep `layer4/per_phase.py` |
| #47 regression test | `TestTopLevelPayloadValidationRetryable` | ✅ grep `tests/test_layer4_plan_create.py` |
| Traceback persist | `traceback_text=traceback.format_exc()` | ✅ grep `routes/plan_create.py` |
| Diag endpoint | `def plan_diag(` + `_diag_token_ok` | ✅ grep `routes/admin.py` |
| Migration | `generation_traceback TEXT` | ✅ grep `init_db.py` |
| Spec amendment | `#47 amendment 2026-05-31` | ✅ grep `aidstation-sources/Layer4_Spec.md` |
| Rule #14 | `Rule #14 — Log access: ask, don't infer` | ✅ grep `aidstation-sources/CLAUDE.md` |
| Diag-token test | `TestDiagTokenOk` | ✅ grep `tests/test_routes_admin.py` |
| Suite | 1855 passed / 16 skipped | ✅ `pytest tests/` |
| Working tree clean | — | ✅ `git status` |
| #349 merged | squash to `main` | ✅ (this merge) |

---

## 9. Files shipped this session

**Substantive (5):**
1. `layer4/per_phase.py` — wrap the payload construction → retryable `schema_violation`
2. `routes/plan_create.py` — best-effort traceback persist on failure
3. `routes/admin.py` — token-gated `/admin/plan/<id>/diag` JSON endpoint
4. `init_db.py` — `generation_traceback` column migration
5. `tests/test_layer4_plan_create.py` + `tests/test_routes_admin.py` — regression + token-gate tests

**Spec / bookkeeping:** `aidstation-sources/Layer4_Spec.md` (§5.5 #47 amendment), `aidstation-sources/CLAUDE.md` (Rule #14), `aidstation-sources/CARRY_FORWARD.md` (owed-deploys #4), `aidstation-sources/CURRENT_STATE.md` (pointer), this handoff.

**GitHub:** PR #349 (this work); issues #350 (log-drain backstop), #351 (per-day clamp) filed.
