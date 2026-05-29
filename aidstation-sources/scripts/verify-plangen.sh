#!/usr/bin/env bash
# D-77 plan-gen convergence proof harness for AIDSTATION.
#
# Turns the manual "owed-deploy #1" convergence walk (CARRY_FORWARD.md) into a
# one-command pass/fail check. It DRIVES a plan to a terminal state and ASSERTS
# the three things the manual walk looks for:
#
#   1. CONVERGENCE  (DB)   — the plan reaches generation_status='ready', and the
#                            cached week-block count grows MONOTONICALLY (never
#                            resets). A reset = orphaned blocks = the cache-key
#                            non-determinism money-loop (#199/#200/#294 class).
#   2. DETERMINISM  (logs) — `ibundle=<X>` and `call_cache_key=<Y>` are IDENTICAL
#                            across every pass, and repeated week-blocks log a
#                            cache HIT on later passes. This is the actual
#                            root-cause proof; it lives only in the runtime logs.
#   3. NO REGRESSION (logs/route) — `POST /plans/v2/<id>/generate` returns
#                            200 {"status":"generating"} mid-flight, never a 500
#                            (the PR #312 poller-mapping fix).
#
# This script runs on ANDY'S machine, not in a Claude web container: it needs
# DB egress to Neon + the Vercel CLI/token + the deployed app, none of which the
# container can reach. See aidstation-sources/scripts/verify-plangen.md for the
# exact setup, or run with --help.
#
# Usage:
#   ./scripts/verify-plangen.sh --help
#   PLAN_VERSION_ID=42 ./scripts/verify-plangen.sh        # observe an existing plan
#   ./scripts/verify-plangen.sh                           # auto-discover newest 'generating'
#
# Exit code 0 = every ENABLED tier passed. Non-zero = a failure or timeout.
# Tiers self-disable (with a loud SKIP) when their inputs are absent, so the
# DB-only convergence proof still runs without a Vercel token.

set -uo pipefail

# ─── Config (all via env; see verify-plangen.md) ─────────────────────────────
APP_URL="${APP_URL:-https://aidstation-pro.vercel.app}"
DATABASE_URL="${DATABASE_URL:-}"          # Neon — required for the convergence tier
CRON_SECRET="${CRON_SECRET:-}"            # drives passes without a browser (cron endpoint)
SESSION_COOKIE="${SESSION_COOKIE:-}"      # e.g. "session=..."; enables the direct /generate poll
VERCEL_LOG_TARGET="${VERCEL_LOG_TARGET:-$APP_URL}"  # what `vercel logs <target>` follows
VERCEL_TOKEN="${VERCEL_TOKEN:-}"          # enables the determinism (log) tier
PLAN_VERSION_ID="${PLAN_VERSION_ID:-}"    # observe a specific plan; else auto-discover
TIMEOUT_S="${TIMEOUT_S:-1800}"            # give up after 30 min by default
POLL_S="${POLL_S:-10}"                    # seconds between drive+poll iterations

# Block-cache rows live in phase_idx [0, _SEAM_CACHE_PHASE_IDX_BASE). Keep this
# in lock-step with routes/plan_create.py:_SEAM_CACHE_PHASE_IDX_BASE (1000).
SEAM_BASE="${SEAM_BASE:-1000}"

LOGFILE="$(mktemp -t plangen-logs.XXXXXX)"
LOG_PID=""
PASS=0; FAIL=0; SKIP=0
declare -a RESULTS=()

# ─── Helpers ─────────────────────────────────────────────────────────────────
say()  { printf '%s\n' "$*"; }
hr()   { printf -- '────────────────────────────────────────────────────────────\n'; }
record() { # record <PASS|FAIL|SKIP> <message>
  case "$1" in
    PASS) PASS=$((PASS+1)); RESULTS+=("✅ $2");;
    FAIL) FAIL=$((FAIL+1)); RESULTS+=("❌ $2");;
    SKIP) SKIP=$((SKIP+1)); RESULTS+=("⚠  SKIP — $2");;
  esac
}
cleanup() { [[ -n "$LOG_PID" ]] && kill "$LOG_PID" 2>/dev/null; rm -f "$LOGFILE"; }
trap cleanup EXIT

# Fail fast instead of hanging when the DB is unreachable (blocked egress, bad
# URL). PGCONNECT_TIMEOUT covers connect; the outer `timeout` (if present) also
# bounds DNS/TLS stalls that the libpq timeout can miss.
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
_TMO="$(command -v timeout || true)"
psql_q() { ${_TMO:+$_TMO 30} psql "$DATABASE_URL" -tAqc "$1" 2>/dev/null; }

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

# ─── Preflight ───────────────────────────────────────────────────────────────
command -v curl >/dev/null || { say "curl is required"; exit 2; }

HAVE_DB=0
if [[ -n "$DATABASE_URL" ]] && command -v psql >/dev/null; then
  if [[ "$(psql_q 'SELECT 1')" == "1" ]]; then HAVE_DB=1
  else say "note: DATABASE_URL is set but the DB is unreachable (blocked egress / bad URL) — convergence tier OFF."; fi
fi
HAVE_LOGS=0; [[ -n "$VERCEL_TOKEN" ]] && command -v vercel >/dev/null && HAVE_LOGS=1
HAVE_CRON=0; [[ -n "$CRON_SECRET" ]] && HAVE_CRON=1
HAVE_POLL=0; [[ -n "$SESSION_COOKIE" ]] && HAVE_POLL=1

hr; say "D-77 plan-gen convergence proof"; hr
if   [[ $HAVE_POLL -eq 1 ]]; then DRIVER_DESC="direct /generate poll (SESSION_COOKIE)"
elif [[ $HAVE_CRON -eq 1 ]]; then DRIVER_DESC="cron-kick (CRON_SECRET)"
else DRIVER_DESC="live Vercel cron only (slow; set CRON_SECRET or SESSION_COOKIE to accelerate)"; fi
say "app:        $APP_URL"
say "convergence tier (DB):     $([[ $HAVE_DB -eq 1 ]] && echo on || echo 'OFF — set DATABASE_URL + install psql')"
say "determinism tier (logs):   $([[ $HAVE_LOGS -eq 1 ]] && echo on || echo 'OFF — set VERCEL_TOKEN + install vercel CLI')"
say "driver: $DRIVER_DESC"
hr

if [[ $HAVE_DB -eq 0 && $HAVE_LOGS -eq 0 ]]; then
  say "Neither the DB nor the log tier is configured — nothing to assert. See verify-plangen.md."
  exit 2
fi

# ─── Resolve the target plan_version_id ──────────────────────────────────────
if [[ -z "$PLAN_VERSION_ID" ]]; then
  if [[ $HAVE_DB -eq 1 ]]; then
    PLAN_VERSION_ID="$(psql_q "SELECT id FROM plan_versions WHERE generation_status='generating' ORDER BY created_at DESC LIMIT 1")"
  fi
  if [[ -z "$PLAN_VERSION_ID" ]]; then
    say "No PLAN_VERSION_ID given and no 'generating' plan found."
    say "Create one in the UI (/plans/v2/new) and re-run, or pass PLAN_VERSION_ID=<id>."
    exit 2
  fi
  say "Auto-discovered newest generating plan: plan_version_id=$PLAN_VERSION_ID"
fi
OWNER_UID=""
[[ $HAVE_DB -eq 1 ]] && OWNER_UID="$(psql_q "SELECT user_id FROM plan_versions WHERE id=$PLAN_VERSION_ID")"

# ─── Start live log capture (determinism tier) ───────────────────────────────
if [[ $HAVE_LOGS -eq 1 ]]; then
  say "Capturing runtime logs via the Vercel CLI → $LOGFILE"
  # `vercel logs` follows runtime logs for the target deployment. Captured live
  # so we never depend on the (retention-limited) log-fetch API.
  vercel logs "$VERCEL_LOG_TARGET" --token "$VERCEL_TOKEN" >>"$LOGFILE" 2>&1 &
  LOG_PID=$!
  sleep 2
fi

# ─── Driver: advance one pass ────────────────────────────────────────────────
csrf_token() { # scrape the csrf-token meta from the progress page (for the poll driver)
  curl -s -b "$SESSION_COOKIE" "$APP_URL/plans/v2/$PLAN_VERSION_ID/progress" \
    | grep -oE 'name="csrf-token"[^>]*content="[^"]+"' | grep -oE 'content="[^"]+"' \
    | head -1 | sed -E 's/content="([^"]+)"/\1/'
}

drive_once() {
  if [[ $HAVE_POLL -eq 1 ]]; then
    # The exact PR #312 path: POST /<id>/generate. Asserts 200 + a JSON status,
    # never the old KeyError 500.
    local tok; tok="$(csrf_token)"
    local body code
    body="$(curl -s -o /tmp/plangen_resp.$$ -w '%{http_code}' -X POST \
      -b "$SESSION_COOKIE" -H "Accept: application/json" -H "X-CSRFToken: $tok" \
      "$APP_URL/plans/v2/$PLAN_VERSION_ID/generate")"
    code="$body"
    local json; json="$(cat /tmp/plangen_resp.$$ 2>/dev/null)"; rm -f /tmp/plangen_resp.$$
    if [[ "$code" == "500" ]]; then
      record FAIL "POST /generate returned 500 (PR #312 regression!) — body: $json"
      return 1
    fi
    POLL_SEEN_OK=1
    say "  /generate → HTTP $code  $(echo "$json" | head -c 120)"
  elif [[ $HAVE_CRON -eq 1 ]]; then
    curl -s -H "Authorization: Bearer $CRON_SECRET" \
      "$APP_URL/plans/v2/cron/generate-pending" >/dev/null || true
  fi
  # else: rely on the live every-minute Vercel cron (no-op here)
}

# ─── Drive + poll to a terminal state ────────────────────────────────────────
POLL_SEEN_OK=0
prev_blocks=-1
monotonic_ok=1
status=""
deadline=$(( $(date +%s) + TIMEOUT_S ))

say "Driving plan_version_id=$PLAN_VERSION_ID (timeout ${TIMEOUT_S}s)…"
while :; do
  drive_once || break

  if [[ $HAVE_DB -eq 1 ]]; then
    status="$(psql_q "SELECT generation_status FROM plan_versions WHERE id=$PLAN_VERSION_ID")"
    blocks="$(psql_q "SELECT COUNT(*) FROM layer4_cache c JOIN plan_versions pv ON pv.id=$PLAN_VERSION_ID \
      WHERE c.user_id=pv.user_id AND c.entry_point='plan_create' \
        AND c.phase_idx>=0 AND c.phase_idx<$SEAM_BASE AND c.created_at>=pv.created_at")"
    blocks="${blocks:-0}"
    if [[ "$prev_blocks" -ge 0 && "$blocks" -lt "$prev_blocks" ]]; then
      monotonic_ok=0
      say "  ⚠ cached block count DROPPED $prev_blocks → $blocks (orphaning = cache-key drift)"
    fi
    [[ "$blocks" != "$prev_blocks" ]] && say "  status=$status  cached_blocks=$blocks"
    prev_blocks="$blocks"
    [[ "$status" == "ready" || "$status" == "failed" ]] && break
  fi

  [[ $(date +%s) -ge $deadline ]] && { say "  timeout after ${TIMEOUT_S}s"; break; }
  sleep "$POLL_S"
done

# ─── Tier 1: convergence (DB) ────────────────────────────────────────────────
if [[ $HAVE_DB -eq 1 ]]; then
  case "$status" in
    ready)
      record PASS "convergence — plan_version_id=$PLAN_VERSION_ID reached 'ready' ($prev_blocks blocks)";;
    failed)
      err="$(psql_q "SELECT generation_error FROM plan_versions WHERE id=$PLAN_VERSION_ID")"
      record FAIL "convergence — plan_version_id=$PLAN_VERSION_ID is 'failed': $err";;
    *)
      record FAIL "convergence — plan_version_id=$PLAN_VERSION_ID still '$status' at timeout ($prev_blocks blocks)";;
  esac
  if [[ $monotonic_ok -eq 1 ]]; then
    record PASS "monotonic blocks — cached week-block count never reset (no orphan storm)"
  else
    record FAIL "monotonic blocks — count RESET mid-run → blocks orphaned (cache-key non-determinism)"
  fi
else
  record SKIP "convergence tier (DATABASE_URL / psql not configured)"
fi

# ─── Tier 2: determinism (logs) ──────────────────────────────────────────────
if [[ $HAVE_LOGS -eq 1 ]]; then
  sleep 3; [[ -n "$LOG_PID" ]] && kill "$LOG_PID" 2>/dev/null; LOG_PID=""

  # `ibundle=<X>` identical across passes (the 3A integration-bundle hash).
  mapfile -t ibundles < <(grep -oE 'ibundle=[A-Za-z0-9]+' "$LOGFILE" | sort -u)
  if [[ "${#ibundles[@]}" -eq 0 ]]; then
    record SKIP "determinism (ibundle) — no 'ibundle=' lines captured (no 3A activity in window?)"
  elif [[ "${#ibundles[@]}" -eq 1 ]]; then
    record PASS "determinism (ibundle) — single value across passes: ${ibundles[0]}"
  else
    record FAIL "determinism (ibundle) — DRIFTED across passes: ${ibundles[*]}"
  fi

  # `call_cache_key=<Y>` identical across passes (the per-block key).
  mapfile -t keys < <(grep -oE 'call_cache_key=[A-Za-z0-9]+' "$LOGFILE" | sort -u)
  if [[ "${#keys[@]}" -le 1 ]]; then
    record PASS "determinism (call_cache_key) — ${#keys[@]} distinct value(s): ${keys[*]:-none captured}"
  else
    record FAIL "determinism (call_cache_key) — DRIFTED: ${keys[*]}"
  fi

  # Per-block cache HIT on later passes (replay, not re-synthesis).
  # Real phrasing: "layer4 cache: block idx=<n> <phase> HIT …" (layer4/cache.py).
  hits="$(grep -cE 'layer4 cache: block idx=[0-9]+.*HIT' "$LOGFILE" || true)"
  if [[ "${hits:-0}" -gt 0 ]]; then
    record PASS "determinism (block HIT) — $hits block cache-HIT log line(s) on replay"
  else
    record SKIP "determinism (block HIT) — no block HIT lines captured (single-pass run, or log phrasing changed)"
  fi

  # Regression guard from logs: any 500 on /generate (two-stage so request-line
  # field order doesn't matter).
  if grep -E '/plans/v2/[0-9]+/generate' "$LOGFILE" | grep -qE '\b500\b'; then
    record FAIL "regression — a 500 on POST /generate appears in the logs (PR #312)"
  else
    record PASS "regression — no 500 on POST /generate in the captured logs"
  fi
else
  record SKIP "determinism tier (VERCEL_TOKEN / vercel CLI not configured)"
fi

# ─── Regression guard from the direct poll driver ────────────────────────────
if [[ $HAVE_POLL -eq 1 && $POLL_SEEN_OK -eq 1 ]]; then
  record PASS "regression — direct POST /generate returned non-500 every pass (PR #312)"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
hr; say "RESULT"
for r in "${RESULTS[@]}"; do say "  $r"; done
hr
say "PASS=$PASS  FAIL=$FAIL  SKIP=$SKIP"
[[ $FAIL -eq 0 ]] && { say "✅ convergence proof GREEN"; exit 0; } || { say "❌ convergence proof RED"; exit 1; }
