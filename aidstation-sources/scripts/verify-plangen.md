# `verify-plangen.sh` — D-77 convergence proof harness

Turns the manual **owed-deploy #1** convergence walk (`CARRY_FORWARD.md` →
"Owed Andy's-hands deploys") into a one-command pass/fail check. Instead of
eyeballing the progress screen + Vercel logs by hand, it drives a plan to a
terminal state and asserts the three things the walk looks for.

## Why it runs on your machine, not in a Claude web session

A Claude Code web container is sealed off from exactly the things this proof
needs: **DB egress to Neon is blocked**, there's **no `ANTHROPIC_API_KEY`** (so
the cone can't actually run), and there's no Vercel token/CLI. The harness
inherently tests the *live deploy*, so it has to run somewhere that can reach
Neon + Vercel + the deployed app — i.e. your laptop. I can write and maintain
the script; I can't execute it end-to-end from a web session. (From a web
session I *can* still pull Vercel runtime logs via the Vercel MCP tools and read
them for you — that covers the "evaluate/investigate" half of the loop, just not
the "drive a real plan" half.)

## What it proves

| # | Tier | Assertion | What a failure means |
|---|---|---|---|
| 1 | Convergence (DB) | Plan reaches `generation_status='ready'` | The cone never finished within the timeout |
| 1 | Convergence (DB) | Cached week-block count grows **monotonically**, never resets | A reset = blocks orphaned = cache-key non-determinism (the #199/#200/#294 money-loop) |
| 2 | Determinism (logs) | `ibundle=<X>` identical across every pass | The 3A integration-bundle hash drifts → 3A re-runs every pass (the #294 `last_sync` class) |
| 2 | Determinism (logs) | `call_cache_key=<Y>` identical across passes | A per-block key input is non-deterministic |
| 2 | Determinism (logs) | Repeated blocks log a cache **HIT** on later passes | Blocks are re-synthesized instead of replayed |
| 3 | Regression | `POST /generate` returns 200, never 500 | The PR #312 poller `'generating'`-mapping regression came back |

Tiers **self-disable with a loud SKIP** when their inputs are missing, so the
DB-only convergence proof still runs without a Vercel token, and vice-versa.
Exit code `0` = every enabled tier passed; non-zero = a failure or timeout.

## Exact setup

### Tools

- `bash`, `curl` — always required.
- `psql` (PostgreSQL client) — required for the **convergence tier**.
  `brew install libpq` (then add it to PATH) or `brew install postgresql`.
- `vercel` CLI — required for the **determinism (log) tier**.
  `npm i -g vercel`. The script captures live runtime logs with
  `vercel logs <target> --token …`, so you never depend on log retention.

### Environment variables

| Var | Required? | What it's for | Where to get it |
|---|---|---|---|
| `DATABASE_URL` | Convergence tier | `psql` connection to Neon | Neon dashboard → Connection string (the same one you use for `init_db.py`) |
| `VERCEL_TOKEN` | Determinism tier | Authenticates `vercel logs` | Vercel → Account Settings → Tokens → Create |
| `APP_URL` | Optional (default `https://aidstation-pro.vercel.app`) | The deployed app base URL | — |
| `VERCEL_LOG_TARGET` | Optional (default `$APP_URL`) | What `vercel logs <target>` follows; a concrete **deployment URL** is most reliable | `vercel ls` or the dashboard → the production deployment URL |
| `CRON_SECRET` | Optional (driver) | Drives passes via the auth'd cron endpoint, no browser needed | Vercel → Project → Settings → Environment Variables (already set, PR9) |
| `SESSION_COOKIE` | Optional (driver) | Enables the **direct `/generate` poll** — the exact PR #312 route, asserts 200-not-500 per pass | Log into the app in your browser → DevTools → Application → Cookies → copy the whole `session=…` value |
| `PLAN_VERSION_ID` | Optional | Observe a specific plan; else auto-discover the newest `generating` row (needs the DB tier) | The number in the progress-screen URL `/plans/v2/<id>/progress` |
| `TIMEOUT_S` | Optional (default `1800`) | Give-up deadline (30 min) | — |
| `POLL_S` | Optional (default `10`) | Seconds between drive+poll iterations | — |

### Drivers (how passes get advanced)

The script needs *something* to advance generation passes. In priority order:

1. **`SESSION_COOKIE` set** → it POSTs `/plans/v2/<id>/generate` itself each
   iteration. This is the only mode that exercises (and asserts on) the exact
   PR #312 route — it confirms 200-not-500 directly, per pass.
2. **`CRON_SECRET` set** → it pokes `GET /plans/v2/cron/generate-pending`
   (`Authorization: Bearer …`) each iteration. The per-plan advisory lock makes
   concurrent pokes safe (extras no-op).
3. **Neither** → it relies on the live every-minute Vercel cron. Works, just
   slow (≤1 min between passes) and it can't directly assert the `/generate`
   route's status code (the log tier still catches a 500 if one occurs).

## Running it

```bash
# 1. Redeploy main (so PR #294 + #311 + #312 are live) — done in the Vercel UI / `vercel --prod`.

# 2. Create one fresh PGE 2026 plan in the browser: /plans/v2/new → submit.
#    Note the id from the progress URL (/plans/v2/<id>/progress), or let the
#    script auto-discover the newest 'generating' row.

# 3. Full proof (all tiers + the direct-route driver):
export DATABASE_URL='postgres://…neon…'
export VERCEL_TOKEN='…'
export VERCEL_LOG_TARGET='https://exercise-<hash>-andy-horns-projects.vercel.app'  # a deployment URL
export SESSION_COOKIE='session=…'
PLAN_VERSION_ID=42 ./aidstation-sources/scripts/verify-plangen.sh

# Minimal (DB-only convergence, live cron drives it):
DATABASE_URL='postgres://…' ./aidstation-sources/scripts/verify-plangen.sh

# Self-documenting:
./aidstation-sources/scripts/verify-plangen.sh --help
```

## Reading the output

It prints a live trace (`status=… cached_blocks=…` as blocks accumulate) then a
summary block of ✅/❌/⚠ lines and `PASS=… FAIL=… SKIP=…`. `✅ convergence proof
GREEN` (exit 0) is the deliverable that closes owed-deploy #1.

If it goes ❌:
- **ibundle DRIFTED** → the diagnostic lists the distinct values; the remaining
  non-deterministic field is upstream of the 3A integration bundle (the #294
  follow-on — likely genuinely-new workout data mid-generation, the harder case).
- **monotonic blocks RESET** → blocks are being orphaned; a per-block cache-key
  input is still non-deterministic (re-open the #201 "4th instance" audit).
- **convergence still 'generating' at timeout** → raise `TIMEOUT_S`, or a single
  block genuinely can't fit the function budget (the latency item C under #201).
- **a 500 on /generate** → the PR #312 regression is back; check `generate_plan`
  in `routes/plan_create.py` still maps `'generating'`.

## Limitations

- The determinism assertions depend on the diagnostic `print()` phrasing:
  `ibundle=` in `layer3a/cached_wrapper.py`, `call_cache_key=` in
  `layer4/cached_wrappers.py`, and `layer4 cache: block idx=… HIT` in
  `layer4/cache.py`. If that wording changes, update the `grep` patterns in the
  determinism tier. (`l3a=`/`l3b=` in the L4 line and `l3a=` in
  `layer3b/cached_wrapper.py` are the prefixes that name which layer's hash
  drifted when `call_cache_key` is NOT stable — the pv=35 finding.)
- `SEAM_BASE` must stay in lock-step with
  `routes/plan_create.py:_SEAM_CACHE_PHASE_IDX_BASE` (1000) — it's how the block
  rows are distinguished from seam-review rows in the count query.
- It does not create the plan (that needs an authenticated browser session); it
  observes + drives an existing or auto-discovered one.
