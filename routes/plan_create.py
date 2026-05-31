"""Plan-create caller-side route (Phase 5.2 caller-side).

Generation is asynchronous + resumable so it survives the serverless
function timeout — the full Layer 3A → 3B → per-phase Layer 4 cone is many
sequential extended-thinking LLM calls (minutes of wall-clock), far past
any single request budget. The flow:

1. GET `/plans/v2/new` renders the create form (plan_start_date + a
   read-only summary of the athlete's existing target race, if any).
2. POST `/plans/v2/new` allocates a `plan_versions` row via
   `allocate_plan_version_row(created_via='plan_create', pattern='A')`,
   marks it `generation_status='generating'`, commits, and redirects to
   the progress screen. No LLM work runs in this request.
3. GET `/plans/v2/<id>/progress` renders a progress screen whose JS polls
   POST `/plans/v2/<id>/generate`.
4. POST `/plans/v2/<id>/generate` runs one `orchestrate_plan_create` pass.
   Each upstream layer + per-phase synthesis is individually cached +
   committed in `layer4_cache`, so a pass cut short by the function
   timeout resumes from the cache on the next poll. On completion the
   sessions persist atomically + the row flips to `ready`; a typed
   upstream error flips it to `failed`.
5. GET `/plans/v2/<id>` renders the plan once `ready` (scope dates +
   pattern + per-session list grouped by date); `generating` redirects to
   the progress screen, `failed` flashes the error.

Caller owns the transaction per substrate D-64 §6.2 — `generate_plan`'s
final `commit()` fires only after orchestrate + persist succeed. On any
raised exception no commit fires; the connection's auto-rollback on close
keeps partial sessions off the table (re-persist is also DELETE-guarded).

`notes=None` for v1; phase-synthesis-notes population from
`payload.phase_structure.phases[*].phase_synthesis_notes` requires an
`update_plan_version_notes` repo helper that doesn't exist yet —
deferred.

The form does NOT include a target-race picker — the orchestrator reads
the athlete's `is_target_event=TRUE` race from `race_events` via
`load_target_race_event_payload`. Athletes manage that on
`/profile/race-events`. Open-ended plans (no target race) are first-
class per slice 3 D4 — `race_event_payload=None` flows cleanly.
"""

from __future__ import annotations

import os
import time
import traceback
from datetime import date, timedelta

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
)

from database import get_db
from layer4 import (
    Layer4Cache,
    OrchestrationError,
    PostgresCacheBackend,
    orchestrate_plan_create,
)
from layer4.plan_create import _SEAM_CACHE_PHASE_IDX_BASE
from layer4.errors import Layer4InputError, Layer4OutputError
from layer3a.builder import Layer3AInputError, Layer3AOutputError
from layer3b.builder import Layer3BInputError, Layer3BOutputError
from layer2_modality import Layer2ModalityInputError
from layer2a.builder import Layer2AInputError
from layer2b.builder import Layer2BInputError
from layer2c.builder import Layer2CInputError
from layer2d.builder import Layer2DInputError
from layer2e.builder import Layer2EInputError
from plan_sessions_repo import (
    allocate_plan_version_row,
    load_plan_sessions_by_version,
    persist_layer4_sessions,
    snapshot_progress_blocks,
)
from race_events_repo import load_target_race_event_payload
from routes.auth import cron_authorized, current_user_id


bp = Blueprint('plan_create', __name__, url_prefix='/plans/v2')

# Hard cap on `generating` rows the cron scans per fire. The real guard is
# `_CRON_WALL_CLOCK_BUDGET_S` below — this just bounds the SELECT.
_CRON_ADVANCE_BATCH = 5

# Wall-clock budget for one cron fire. Each `_advance_plan_generation` pass is
# a full resumable cone pass that can run up to the function-duration cap
# (300s on Pro), so advancing several cold rows back-to-back in one request
# would blow that cap and 504 — wasting every row after the one that hit the
# wall. The cron stops starting NEW passes once this budget is spent; the
# in-flight pass it already started still commits its per-phase progress, and
# the unstarted rows resume on the next minute's fire. Set below the function
# cap so a final pass started just under the budget still has headroom to
# finish + commit.
_CRON_WALL_CLOCK_BUDGET_S = 240

# D-77 §6 progress-based backstop. The per-week-block decomposition makes each
# unit fit the 300s function ceiling, so a healthy generation caches ≥1 new block
# within each pass; a generation that caches ZERO new blocks for longer than a
# couple of function budgets has a unit that genuinely can't fit, and the row
# fails loudly rather than 504-looping forever.
#
# The signal is WALL-CLOCK, not a per-call counter. Both the every-minute cron
# AND the progress-screen poller call `_advance_plan_generation` on the same
# `generating` row, and a single pass may legitimately spend its whole ~300s
# budget synthesizing the first block before caching anything. The original
# per-call counter (`_STALL_PASS_LIMIT` consecutive no-progress *calls*) raced
# that window: poller-start incremented to 1, the cron one minute later
# incremented to 2, and the plan was failed in ~1 min — before the first block
# could ever cache. `_generation_stalled` instead measures elapsed time since the
# most-recent block cached (or generation start if none yet) on the DB clock, so
# it is robust to a 504-killed pass and to concurrent cron/poller calls.
_STALL_WALLCLOCK_S = 900


# D-77 concurrency guard. Vercel's every-minute cron re-fires while a prior
# pass is still running (each can run up to the function-duration cap) and the
# progress poller hits the same row -- so without a guard up to ~5 invocations
# advance ONE plan at once. They all replay the cached blocks, all MISS the
# same frontier week, and all synthesize it concurrently: N duplicate
# extended-thinking calls, one wins the cache put, the rest are burned. (This,
# not single-pass cost, is the dominant money-loop once cache keys are
# deterministic.) A Postgres session advisory lock keyed on the plan lets
# exactly one invocation advance it; the rest no-op. Session locks auto-release
# when the connection closes (request teardown OR a 504 dropping the conn), so
# a killed pass never strands the lock -- the next fire re-acquires and resumes
# from the cache.
_ADVANCE_LOCK_NS = 0x504C414E  # ascii 'PLAN' -- advisory-lock namespace

# D-77 per-invocation budget. Sized off the Vercel function Max Duration
# (PLAN_GEN_FUNCTION_CAP_S, a dashboard setting: 300s default, up to 800s on
# Pro). Once a pass has spent (cap - reserve) seconds it stops STARTING a new
# week-block synthesis and returns 'generating', so it never 504s mid-synthesis
# and burns that block's in-flight Anthropic call. Bump PLAN_GEN_FUNCTION_CAP_S
# the moment you raise the dashboard Max Duration.
#
# RESERVE must exceed the worst-case single-block wall time + cleanup, because a
# block STARTED just before the deadline runs to completion AFTER it. Prod pv=39
# (#324) showed blocks up to ~250s (one a 249s Peak week), and the old 255s
# reserve left only ~6s of headroom over a 249s block on the 800s cap — so a
# block started near the deadline ran into the 800s wall and 504'd, losing its
# work. Raised to 330s (≈250s worst block + ~80s for persist/seam/overhead) so a
# started block always finishes and caches before the cap. Env-overridable.
_FUNCTION_CAP_S = float(os.environ.get("PLAN_GEN_FUNCTION_CAP_S", "300"))
_INVOCATION_RESERVE_S = float(os.environ.get("PLAN_GEN_INVOCATION_RESERVE_S", "330"))
_INVOCATION_BUDGET_S = max(_FUNCTION_CAP_S - _INVOCATION_RESERVE_S, 30.0)

# #324 resilience — Layer4OutputError codes that mean "the synthesizer fumbled
# ONE block's output" (unparseable sessions), as opposed to a genuine
# input/contract fault. These are usually transient (temp=0.2 stochastic), so a
# single one should NOT discard a near-complete plan — it's retried on the next
# resumable pass instead (see the handler in `_advance_plan_generation`).
_RETRYABLE_BLOCK_CODES = frozenset({"schema_violation", "synthesis_budget_exhausted"})

from layer4.generation_budget import (  # noqa: E402 (grouped with its config)
    Layer4GenerationIncomplete,
    generation_deadline,
)


def _try_acquire_advance_lock(db, plan_version_id: int) -> bool:
    """Non-blocking `pg_try_advisory_lock(ns, plan_version_id)`. True => this
    invocation holds the advance lock for the plan; False => another already
    does (skip, don't duplicate-synthesize). A null/absent result (the
    non-Postgres FakeDb in unit tests) reads as acquired, so the guard is inert
    there unless contention is explicitly simulated."""
    row = db.execute(
        "SELECT pg_try_advisory_lock(?, ?) AS locked",
        (_ADVANCE_LOCK_NS, plan_version_id),
    ).fetchone()
    if row is None:
        return True  # non-Postgres FakeDb (no canned row) → fail-open, guard inert
    try:
        locked = row["locked"]
    except (KeyError, TypeError, IndexError):
        return True  # row that isn't a lock result → fail-open
    return bool(locked)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _parse_plan_start_date(form) -> tuple[date | None, str | None]:
    raw = (form.get('plan_start_date') or '').strip()
    if not raw:
        return None, "Plan start date is required."
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, "Plan start date must be in YYYY-MM-DD format."


def _load_plan_version(db, user_id: int, plan_version_id: int) -> dict | None:
    """Fetch a plan_versions row scoped to user_id. Returns dict or None."""
    row = db.execute(
        "SELECT id, user_id, created_at, created_via, scope_start_date, "
        "scope_end_date, pattern, generation_status, generation_error, "
        "generation_units_cached, generation_stall_passes "
        "FROM plan_versions WHERE id = ? AND user_id = ?",
        (plan_version_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return {
        'id': int(row['id']),
        'user_id': int(row['user_id']),
        'created_at': row['created_at'],
        'created_via': row['created_via'],
        'scope_start_date': row['scope_start_date'],
        'scope_end_date': row['scope_end_date'],
        'pattern': row['pattern'],
        'generation_status': row['generation_status'],
        'generation_error': row['generation_error'],
        'generation_units_cached': int(row['generation_units_cached'] or 0),
        'generation_stall_passes': int(row['generation_stall_passes'] or 0),
    }


def _build_layer4_cache() -> Layer4Cache:
    return Layer4Cache(PostgresCacheBackend(lambda: get_db()))


def _count_cached_blocks(db, user_id: int, plan_version_id: int) -> int:
    """D-77 §6 — count the per-week-block cache rows for THIS plan's generation
    (the progress signal for the stall backstop). Block rows carry `phase_idx`
    in `[0, _SEAM_CACHE_PHASE_IDX_BASE)`; the per-entry row (`phase_idx = -1`),
    the upstream-layer rows (other `entry_point`s), and the seam-review rows
    (`phase_idx >= _SEAM_CACHE_PHASE_IDX_BASE`) are excluded.

    The route doesn't hold this plan's exact `call_cache_key` (the orchestrator
    derives it), so the query is user-scoped — but orphaned block rows from a
    PRIOR failed plan would otherwise inflate the count. Bounding to rows created
    at/after the plan_versions row's own `created_at` keeps it to this
    generation's progress."""
    row = db.execute(
        "SELECT COUNT(*) AS n FROM layer4_cache c, plan_versions pv "
        "WHERE pv.id = ? AND pv.user_id = ? "
        "AND c.user_id = ? AND c.entry_point = 'plan_create' "
        "AND c.phase_idx >= 0 AND c.phase_idx < ? "
        "AND c.created_at >= pv.created_at",
        (plan_version_id, user_id, user_id, _SEAM_CACHE_PHASE_IDX_BASE),
    ).fetchone()
    return int(row['n']) if row else 0


def _generation_stalled(db, user_id: int, plan_version_id: int) -> bool:
    """D-77 §6 — True iff no plan_create week-block has cached within
    `_STALL_WALLCLOCK_S` seconds, measured on the DB clock against the
    most-recent block's cache time (or the plan_versions row's start time if no
    block has cached yet).

    This replaces the original per-call no-progress counter, which raced the
    every-minute cron + the progress poller and tripped before the first ~300s
    block could cache. A wall-clock gate never false-trips a block that is
    legitimately in flight, and concurrent cron/poller calls can't double-count
    it — yet a unit that genuinely can't fit the budget still trips once the
    elapsed window is exceeded.

    The block subquery is bounded to `created_at >= pv.created_at` so orphaned
    block rows from a PRIOR failed plan (this query is user-scoped, not keyed to
    this plan's call_cache_key) can't anchor the elapsed-time window in the
    past and false-trip every NEW plan on its first pass."""
    row = db.execute(
        "SELECT (NOW() - COALESCE("
        "  (SELECT MAX(created_at) FROM layer4_cache "
        "     WHERE user_id = ? AND entry_point = 'plan_create' "
        "       AND phase_idx >= 0 AND phase_idx < ? "
        "       AND created_at >= pv.created_at), "
        "  pv.created_at)) > (? * INTERVAL '1 second') AS stalled "
        "FROM plan_versions pv WHERE pv.id = ? AND pv.user_id = ?",
        (user_id, _SEAM_CACHE_PHASE_IDX_BASE, _STALL_WALLCLOCK_S,
         plan_version_id, user_id),
    ).fetchone()
    return bool(row['stalled']) if row else False


_ORCH_ERROR_MESSAGES = {
    'etl_version_set_undiscoverable': "Platform data is unavailable. Try again shortly.",
    'primary_locale_missing': "Set up your home locale before creating a plan.",
    'framework_sport_missing': "Set your primary sport in your profile before creating a plan.",
}


def _orchestration_error_message(err: OrchestrationError) -> str:
    return _ORCH_ERROR_MESSAGES.get(
        err.code,
        f"Plan creation failed ({err.code}). Try again or contact support.",
    )


def _resolve_plan_scope_end_date(start_date: date, race_event_payload) -> date:
    """Pick a `scope_end_date` for the new plan_versions row.

    The orchestrator does not return scope bounds; for v1 we pick:
    - Race event present + event_date >= start_date → event_date.
    - Otherwise → start_date + 168 days (24-week default no-event
      ceiling per Layer 3B §6.6).
    """
    if race_event_payload is not None and getattr(race_event_payload, 'event_date', None):
        event_date = race_event_payload.event_date
        if event_date >= start_date:
            return event_date
    return start_date + timedelta(days=168)


def _view_plan_url(plan_version_id: int) -> str:
    return url_for('plan_create.view_plan', plan_version_id=plan_version_id)


def _mark_plan_failed(
    db, plan_version_id: int, user_id: int, message: str,
    traceback_text: str | None = None,
) -> dict:
    """Persist a terminal failure on the plan_versions row + return the
    poller JSON. Rolls back first so the write lands on a clean transaction
    even if an upstream layer left the connection mid-statement — and the
    rollback is reconnect-safe (`database._PgConn.rollback`), so a fault raised
    *because the connection itself dropped* (Neon closing an idle SSL link
    during a multi-minute synthesis) can't turn this failure path into a 500
    with the row stuck 'generating'.

    `traceback_text` (optional) persists the full Python traceback to
    `plan_versions.generation_traceback` for the token-gated
    `/admin/plan/<id>/diag` endpoint (CLAUDE.md Rule #14 — read the real fault
    without the login wall / the truncating runtime-log MCP). It's written in
    its OWN isolated, best-effort statement so a missing column (pre-migration)
    or any write fault can NEVER turn the failure path back into a 500 — the
    user-facing failure is already committed above."""
    db.rollback()
    db.execute(
        "UPDATE plan_versions SET generation_status = 'failed', "
        "generation_error = ? WHERE id = ? AND user_id = ?",
        (message, plan_version_id, user_id),
    )
    db.commit()
    if traceback_text:
        try:
            db.execute(
                "UPDATE plan_versions SET generation_traceback = ? "
                "WHERE id = ? AND user_id = ?",
                (traceback_text[:20000], plan_version_id, user_id),
            )
            db.commit()
        except Exception as _tb_exc:  # noqa: BLE001 — diag write must not break the failure path
            db.rollback()
            print(
                f"_mark_plan_failed: generation_traceback persist failed for "
                f"plan_version_id={plan_version_id} (non-fatal; column may be "
                f"pre-migration): {_tb_exc}"
            )
    return {"status": "failed", "error": message}


def _advance_plan_generation(db, uid: int, plan_version_id: int) -> dict:
    """Run one resumable generation pass for plan_versions row
    `plan_version_id`, scoped to `uid`. Shared by the progress-screen
    poller (`generate_plan`) and the background cron
    (`cron_generate_pending`) so generation advances whether the create
    tab is open or closed.

    Returns a view-agnostic outcome dict — no URLs, the caller owns view
    concerns:
      {"status": "not_found"}                   — no such row for this user
      {"status": "ready"}                        — generation complete
      {"status": "failed", "error": <message>}   — typed upstream failure

    Already-terminal rows short-circuit without re-running the cone, so a
    poll (or cron pass) that races a just-finished row is a cheap no-op.
    On a fresh pass each upstream layer + per-phase synthesis is
    individually cached + committed in `layer4_cache`; a pass cut short by
    the function timeout resumes from the cache on the next call rather
    than restarting. On completion the sessions persist atomically
    (DELETE-guarded) and the row flips to `ready`; a typed upstream error
    flips it to `failed`.
    """
    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        return {"status": "not_found"}

    status = plan_version['generation_status']
    if status == 'ready':
        return {"status": "ready"}
    if status == 'failed':
        return {
            "status": "failed",
            "error": plan_version['generation_error']
            or "Plan generation failed. Please try again.",
        }

    # D-77 concurrency guard -- see `_ADVANCE_LOCK_NS`. Acquire the per-plan
    # advance lock; if another invocation (a concurrent cron fire or the
    # poller) already holds it, no-op now rather than duplicate-synthesizing the
    # same frontier week. The session lock auto-releases when this request's
    # connection closes, so the next pass resumes from the cache.
    if not _try_acquire_advance_lock(db, plan_version_id):
        return {"status": "generating", "note": "advance_in_progress_elsewhere"}

    # D-77 §6 progress-based backstop (runs BEFORE the cone so it survives the
    # prior pass being 504-killed mid-flight). Trip only when no week-block has
    # cached for `_STALL_WALLCLOCK_S` (wall-clock on the DB clock), NOT on a
    # per-call counter — see the `_STALL_WALLCLOCK_S` rationale: the cron + the
    # poller both call this, and the first block legitimately takes a full pass
    # to cache, so a call-count trip killed plans before they could start.
    now_cached = _count_cached_blocks(db, uid, plan_version_id)
    if _generation_stalled(db, uid, plan_version_id):
        # Convert the silent infinite 504 loop into a loud terminal failure.
        print(
            f"_advance_plan_generation: D-77 stall backstop tripped for "
            f"plan_version_id={plan_version_id} — no new week-block cached in "
            f"{_STALL_WALLCLOCK_S}s at {now_cached} cached block(s); a synthesis "
            f"unit (next block index {now_cached}) exceeds the function budget."
        )
        return _mark_plan_failed(
            db, plan_version_id, uid,
            "Plan generation stalled and was stopped — a step couldn't complete "
            "within the time budget. This is unexpected; please contact support.",
        )
    # Not stalled — persist the latest progress count (telemetry: the progress
    # screen and a later pass can see how far generation has gotten) before
    # running one more resumable pass.
    db.execute(
        "UPDATE plan_versions SET generation_units_cached = ? "
        "WHERE id = ? AND user_id = ?",
        (now_cached, plan_version_id, uid),
    )
    # #321 observability — snapshot the accepted blocks cached so far into the
    # durable `plan_progress_blocks` table so an in-flight/failed plan's partial
    # progress survives cache eviction and is inspectable (admin view). Best-
    # effort: a snapshot fault must NEVER break generation, so it's isolated in
    # its own try and never propagates. WRITE-ONLY — never feeds a cache key.
    try:
        snapshot_progress_blocks(
            db, uid, plan_version_id,
            seam_phase_idx_base=_SEAM_CACHE_PHASE_IDX_BASE,
        )
    except Exception as _snap_exc:  # noqa: BLE001 — observability must not break gen
        print(
            f"_advance_plan_generation: progress-block snapshot failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {_snap_exc}"
        )
    db.commit()

    try:
        with generation_deadline(_INVOCATION_BUDGET_S):
            # D-77 per-invocation budget -- stop synthesizing new blocks before
            # the function-duration cap so the pass returns cleanly (cached
            # blocks persist; next pass resumes) instead of 504-ing
            # mid-synthesis and wasting that block's Anthropic call.
            result = orchestrate_plan_create(
                db, uid,
                plan_start_date=plan_version['scope_start_date'],
                plan_version_id=plan_version_id,
                cache=_build_layer4_cache(),
            )
        # Success path runs INSIDE the try so a persist/commit failure (e.g. a
        # plan_sessions schema or natural-key surprise) is caught below and
        # marks the row terminal — not a raw 500 that leaves it 'generating'
        # for the every-minute cron to re-pick. DELETE-before-insert keeps the
        # persist idempotent: if a prior pass committed sessions then died
        # before flipping the status, the cache-hit replay would otherwise
        # collide on the natural-key UNIQUE.
        db.execute(
            "DELETE FROM plan_sessions WHERE plan_version_id = ?",
            (plan_version_id,),
        )
        persist_layer4_sessions(db, result)
        db.execute(
            "UPDATE plan_versions SET generation_status = 'ready', "
            "generation_error = NULL WHERE id = ? AND user_id = ?",
            (plan_version_id, uid),
        )
        db.commit()
        return {"status": "ready"}
    except Layer4GenerationIncomplete as exc:
        # D-77 budget spent mid-pass -- NOT a failure. Blocks synthesized this
        # pass are already cached (per-block cache commits independently), so
        # keep the row 'generating'; the next pass resumes from the cache.
        # (Layer4GenerationIncomplete is a BaseException, so the broad handlers
        # below never catch it.)
        print(
            f"_advance_plan_generation: budget partial progress for "
            f"plan_version_id={plan_version_id} -- {exc.blocks_cached} "
            f"block(s) cached this pass; resuming next pass"
        )
        return {"status": "generating", "note": "budget_partial_progress"}
    except OrchestrationError as exc:
        return _mark_plan_failed(
            db, plan_version_id, uid, _orchestration_error_message(exc)
        )
    except (Layer4InputError, Layer4OutputError) as exc:
        # exc.detail carries the failing field/invariant (e.g. the pydantic
        # ValidationError for a session the synthesizer mis-emitted); the
        # user-facing message only carries exc.code. Log the detail — same as
        # the Layer3 catch below — else a Layer 4 schema_violation is
        # undiagnosable from the runtime log.
        print(
            f"_advance_plan_generation: Layer4 {type(exc).__name__} "
            f"({exc.code}) for plan_version_id={plan_version_id}: "
            f"{getattr(exc, 'detail', None)}"
        )
        # #324 resilience — a single block the synthesizer fumbles (unparseable
        # output) used to call _mark_plan_failed and DISCARD the entire
        # near-complete plan (prod pv=39 lost 7 good weeks to one bad 8th block).
        # These fumbles are usually transient, so instead keep the row
        # 'generating' and let the next resumable pass re-attempt that block with
        # a fresh call — the already-cached blocks replay as HITs, so it picks up
        # right where it left off. We NEVER ship a best-effort broken block: the
        # block either parses + caches, or is retried. A block that fails
        # PERSISTENTLY is bounded by the existing 15-min stall backstop
        # (`_generation_stalled`, checked at the top of this function): with no
        # new block caching, the next pass flips the plan to a clean `failed`.
        # Only the block-fumble codes resume; a genuine input/contract fault
        # (any other code, or Layer4InputError) still fails fast.
        if isinstance(exc, Layer4OutputError) and exc.code in _RETRYABLE_BLOCK_CODES:
            db.rollback()  # clear the aborted synthesis txn before resuming
            fumble_detail = f"{exc.code}: {getattr(exc, 'detail', None)}"
            # Bound the deterministic retry. A *transient* fumble (temp=1.0 thinking
            # coin-flip) varies pass-to-pass and is worth re-attempting. A
            # *deterministic* one repeats the identical detail every pass and used
            # to burn the full 15-min stall backstop before failing — a silent
            # mystery (the #325 flaw). So: stash this pass's detail on the row; if
            # the prior pass already stored the IDENTICAL detail and no new block
            # cached since (now_cached unchanged), it's deterministic — fail fast
            # with the real code+detail surfaced, instead of looping to the wall.
            prior_err = plan_version['generation_error']
            if prior_err == fumble_detail and now_cached == 0:
                print(
                    f"_advance_plan_generation: block-fumble ({exc.code}) for "
                    f"plan_version_id={plan_version_id} REPEATED identically with "
                    f"0 cached blocks — deterministic; failing fast: {fumble_detail}"
                )
                return _mark_plan_failed(
                    db, plan_version_id, uid,
                    f"Plan synthesis failed ({exc.code}): {getattr(exc, 'detail', None)}",
                )
            # First sighting (or progress was made) — keep 'generating', stash the
            # detail so the next pass can detect a deterministic repeat AND so the
            # admin inspect view shows the real cause live (not just the generic
            # stall message the backstop would later write).
            db.execute(
                "UPDATE plan_versions SET generation_error = ? "
                "WHERE id = ? AND user_id = ?",
                (fumble_detail, plan_version_id, uid),
            )
            db.commit()
            print(
                f"_advance_plan_generation: block-fumble ({exc.code}) for "
                f"plan_version_id={plan_version_id} — keeping 'generating' to "
                f"retry the block next pass (bounded by the stall backstop): "
                f"{fumble_detail}"
            )
            return {"status": "generating", "note": "block_retry_resume"}
        return _mark_plan_failed(
            db, plan_version_id, uid,
            f"Plan synthesis failed ({exc.code}). Adjust your inputs and try again.",
        )
    except (
        Layer3AInputError,
        Layer3BInputError,
        Layer3AOutputError,
        Layer3BOutputError,
    ) as exc:
        # Input-validation failures (Layer3*InputError) escaped here as a raw
        # "unexpected" 500 before — they are ValueError subclasses, not in the
        # *OutputError contract. Catch them alongside the output errors so an
        # upstream-contract gap degrades to a coded message instead of an
        # opaque one. Log the detail so the cause is visible in the runtime log.
        print(
            f"_advance_plan_generation: Layer3 {type(exc).__name__} "
            f"({exc.code}) for plan_version_id={plan_version_id}: "
            f"{getattr(exc, 'detail', None)}"
        )
        return _mark_plan_failed(
            db, plan_version_id, uid,
            f"Athlete evaluation failed ({exc.code}). Try again or contact support.",
        )
    except (
        Layer2AInputError,
        Layer2BInputError,
        Layer2CInputError,
        Layer2DInputError,
        Layer2EInputError,
        Layer2ModalityInputError,
    ) as exc:
        # Layer 1/2 upstream-input failures (e.g. a profile missing
        # body_weight_kg / height_cm for Layer 2E) are bare ValueError
        # subclasses outside the Layer3/Layer4 typed contract. Without this
        # they fall to the catch-all below and surface as the opaque "failed
        # unexpectedly" — same diagnostic dead-end the Layer3 catch closed.
        # Log the message + flip the row to a named, diagnosable failure.
        print(
            f"_advance_plan_generation: {type(exc).__name__} for "
            f"plan_version_id={plan_version_id}: {exc}"
        )
        return _mark_plan_failed(
            db, plan_version_id, uid,
            f"Plan setup failed ({type(exc).__name__}). "
            "Check your profile data and try again.",
        )
    except Exception as exc:
        # Anything not in the typed-error contract (e.g. a DB error mid-cone)
        # must still flip the row to a terminal state — otherwise it escapes as
        # a raw 500 AND the row stays 'generating', so the every-minute cron
        # re-picks it and 500-loops forever, burning a real cone each fire.
        # Log a full traceback (not just the repr) so an unexpected fault is
        # diagnosable from the runtime log without another instrumentation pass.
        traceback.print_exc()
        print(
            f"_advance_plan_generation: unexpected {type(exc).__name__} for "
            f"plan_version_id={plan_version_id}: {exc}"
        )
        # Persist the full traceback (best-effort) so the token-gated diag
        # endpoint surfaces the real fault without the login wall / the
        # truncating runtime-log MCP (CLAUDE.md Rule #14).
        return _mark_plan_failed(
            db, plan_version_id, uid,
            "Plan generation failed unexpectedly. Please try again or contact support.",
            traceback_text=traceback.format_exc(),
        )


# ─── Routes ─────────────────────────────────────────────────────────────────


@bp.route('/new', methods=['GET', 'POST'])
def new_plan():
    """Render the create form on GET. On POST: parse + allocate the
    plan_versions row, mark it 'generating', commit, and redirect to the
    progress screen. The cone runs asynchronously via `generate_plan` —
    the POST itself does no LLM work so it can't blow the function timeout."""
    db = get_db()
    uid = current_user_id()

    if request.method == 'POST':
        plan_start_date, err = _parse_plan_start_date(request.form)
        if err is not None or plan_start_date is None:
            flash(err or "Invalid input.", 'danger')
            return redirect(url_for('plan_create.new_plan'))

        if plan_start_date < date.today():
            flash("Plan start date must be today or in the future.", 'danger')
            return redirect(url_for('plan_create.new_plan'))

        race_event = load_target_race_event_payload(db, uid)
        scope_end_date = _resolve_plan_scope_end_date(plan_start_date, race_event)

        plan_version_id = allocate_plan_version_row(
            db, uid,
            created_via='plan_create',
            scope_start_date=plan_start_date,
            scope_end_date=scope_end_date,
            pattern='A',
            notes=None,
        )

        # Don't run the cone here. The full Layer 3A → 3B → per-phase Layer 4
        # cascade is many sequential extended-thinking LLM calls — minutes of
        # wall-clock that blows the serverless function timeout. Mark the row
        # 'generating', commit, and hand off to the progress screen, which
        # drives generation step-by-step via POST /<id>/generate (each pass
        # resumes from the layer4_cache).
        db.execute(
            "UPDATE plan_versions SET generation_status = 'generating' "
            "WHERE id = ? AND user_id = ?",
            (plan_version_id, uid),
        )
        db.commit()
        return redirect(
            url_for('plan_create.plan_progress', plan_version_id=plan_version_id)
        )

    race_event = load_target_race_event_payload(db, uid)
    return render_template(
        'plan_create/new_form.html',
        race_event=race_event,
        today_iso=date.today().isoformat(),
    )


@bp.route('/<int:plan_version_id>', methods=['GET'])
def view_plan(plan_version_id: int):
    """Render the plan: scope dates + pattern + per-session list grouped
    by date. 404 + cross-user-defense via the user_id filter in
    `_load_plan_version`."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)

    status = plan_version['generation_status']
    if status == 'generating':
        return redirect(
            url_for('plan_create.plan_progress', plan_version_id=plan_version_id)
        )
    if status == 'failed':
        flash(
            plan_version['generation_error']
            or "Plan generation failed. Please try again.",
            'danger',
        )
        return redirect(url_for('plan_create.new_plan'))

    sessions = load_plan_sessions_by_version(db, plan_version_id)
    sessions_by_date: dict = {}
    for session in sessions:
        sessions_by_date.setdefault(session.date, []).append(session)

    return render_template(
        'plan_create/view.html',
        plan_version=plan_version,
        sessions_by_date=sorted(sessions_by_date.items()),
        session_count=len(sessions),
    )


@bp.route('/<int:plan_version_id>/progress', methods=['GET'])
def plan_progress(plan_version_id: int):
    """Render the generation progress screen. Its JS polls
    `generate_plan` until the plan is ready (then redirects to the view)
    or fails (then surfaces the error). A ready plan skips straight to the
    view; a missing/cross-user id 404s via `_load_plan_version`."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)

    if plan_version['generation_status'] == 'ready':
        return redirect(_view_plan_url(plan_version_id))

    return render_template(
        'plan_create/progress.html',
        plan_version=plan_version,
        generate_url=url_for(
            'plan_create.generate_plan', plan_version_id=plan_version_id
        ),
        view_url=_view_plan_url(plan_version_id),
        new_url=url_for('plan_create.new_plan'),
    )


@bp.route('/<int:plan_version_id>/generate', methods=['POST'])
def generate_plan(plan_version_id: int):
    """Resumable generation step for the progress poller. Returns JSON.

    Thin wrapper over `_advance_plan_generation` (shared with the
    background cron). Maps the view-agnostic outcome to the poller's JSON:
    a missing/cross-user row 404s; `ready` carries the view redirect;
    `failed` carries the stored error message.
    """
    db = get_db()
    uid = current_user_id()

    outcome = _advance_plan_generation(db, uid, plan_version_id)
    status = outcome['status']
    if status == 'not_found':
        abort(404)
    if status == 'ready':
        return jsonify(
            {"status": "ready", "redirect": _view_plan_url(plan_version_id)}
        )
    if status == 'failed':
        return jsonify({"status": "failed", "error": outcome['error']})
    # 'generating' — this pass made partial progress and the row is still
    # generating: either the D-77 per-invocation budget stopped before the
    # function cap (`budget_partial_progress`) or the D-77 concurrency guard
    # found another invocation already advancing this plan
    # (`advance_in_progress_elsewhere`). Both are the NORMAL multi-block path —
    # tell the poller to keep polling (it resumes from the cache on the next
    # pass). The old code fell through to the `failed` branch and KeyError'd on
    # the missing 'error' key, 500-ing every intermediate poll; the poller
    # counted each 500 as a transport failure and, after its retry cap, showed
    # "This is taking longer than expected. Please try again." — the reported
    # symptom for any plan needing more than one pass.
    return jsonify({"status": "generating"})


@bp.route('/cron/generate-pending', methods=['GET'])
def cron_generate_pending():
    """Background generation backstop. Vercel Cron hits this with
    `Authorization: Bearer $CRON_SECRET`; it advances up to
    `_CRON_ADVANCE_BATCH` plan_versions rows still in `generating` by one
    resumable pass each, so a plan finishes even with the create tab
    closed (the progress screen still polls for faster feedback when open).

    Each row is advanced under its own owner's user id + committed
    independently inside `_advance_plan_generation`, so a pass cut short by
    the function timeout keeps the rows it already finished. Returns JSON
    `{advanced: N, ready: R, failed: F}`. Idempotent — already-terminal
    rows are excluded by the WHERE filter, and a row mid-flight resumes
    from `layer4_cache` on the next fire.
    """
    if not cron_authorized():
        abort(401)

    db = get_db()
    rows = db.execute(
        "SELECT id, user_id FROM plan_versions "
        "WHERE generation_status = 'generating' "
        "ORDER BY created_at ASC LIMIT ?",
        (_CRON_ADVANCE_BATCH,),
    ).fetchall()

    advanced = ready = failed = 0
    deadline = time.monotonic() + _CRON_WALL_CLOCK_BUDGET_S
    for row in rows:
        # Don't start a pass we can't finish before the function-duration cap.
        # Whatever we've already advanced is committed per row; the rest resume
        # on the next fire.
        if time.monotonic() >= deadline:
            break
        outcome = _advance_plan_generation(db, int(row['user_id']), int(row['id']))
        advanced += 1
        if outcome['status'] == 'ready':
            ready += 1
        elif outcome['status'] == 'failed':
            failed += 1

    return jsonify(advanced=advanced, ready=ready, failed=failed), 200
