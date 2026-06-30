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
    make_response,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
)
from werkzeug.routing import BuildError

from database import get_db
from layer4 import (
    Layer4Cache,
    OrchestrationError,
    PostgresCacheBackend,
    compute_gate_input_fingerprint,
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
from layer3d.gate import (
    GateResolution,
    Layer3DGateBlocked,
    compute_gate_status,
    resolved_status,
)
from plan_sessions_repo import (
    allocate_plan_version_row,
    fill_rest_gaps,
    load_hitl_gate,
    load_plan_sessions_by_version,
    persist_layer4_sessions,
    save_hitl_gate,
    snapshot_progress_blocks,
)
from race_events_repo import load_target_race_event_payload
from plan_naming import target_race_name, generated_plan_name
from plan_notifications import notify_plan_terminal
from athlete_event_windows_repo import load_event_windows
from plan_nutrition_repo import load_plan_nutrition_by_version
from plan_conditions_repo import load_plan_conditions_by_version
from evidence_repo import (
    attach_baseline_plan_evidence,
    load_plan_evidence,
    record_plan_evidence_citations,
)
from race_week_brief_repo import load_race_week_brief
from layer5 import (
    generate_and_persist_plan_nutrition,
    generate_and_persist_plan_conditions,
)
from routes.auth import cron_authorized, current_user_id
from routes.outbound_workout import is_zwift_exportable


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


# D-77 concurrency guard. Vercel's every-minute cron re-fires while a prior pass
# is still running (each can run up to the function-duration cap) and the
# progress poller hits the same row -- so without a guard up to ~5 invocations
# advance ONE plan at once. They all replay the cached blocks, all MISS the same
# frontier week, and all synthesize it concurrently: N duplicate extended-thinking
# calls, one wins the cache put, the rest are burned. (This, not single-pass cost,
# is the dominant money-loop once cache keys are deterministic.) Exactly one
# invocation may hold the per-plan advance claim; the rest no-op.
#
# The claim is a TTL stamp on `plan_versions.advance_lock_until`, NOT a session
# `pg_advisory_lock`. The advisory lock leaked on a hard SIGKILL: a pass
# 504-killed mid-synthesis never ran its `finally` release, and on Neon's
# transaction pooler the session lock survived on the parked backend, so EVERY
# later advance no-op'd on it until the backend recycled -- starving the plan
# until the stall backstop failed it (pv=56, 2026-06-04). A TTL stamp can't
# outlive its pass: a killed claim simply lapses after `_ADVANCE_LOCK_TTL_S` and
# the next cron reclaims (`_ADVANCE_LOCK_TTL_S` is derived below, off the budget).

# D-77 per-invocation budget. Sized off the Vercel function Max Duration
# (PLAN_GEN_FUNCTION_CAP_S, mirroring the deployed cap: 800s on Pro + Fluid
# Compute, confirmed 2026-06-23). Once a pass has spent (cap - reserve) seconds it
# stops STARTING a new week-block synthesis and returns 'generating', so it never
# 504s mid-synthesis and burns that block's in-flight Anthropic call.
#
# The default is 800 to MATCH the deployed function, not the old 300 placeholder:
# the reserve below (330s) was already sized for an 800s cap, so a 300 default
# made `cap - reserve` negative and floored the budget to 30s — too short to
# cache a single ~250s dense week-block, so every resumable pass 504s and the plan
# stalls at the backstop with zero progress (the pv=80 "3 blocks then stalled at
# index 3" failure). vercel.json can't pin maxDuration here (its `functions` key
# is mutually exclusive with the legacy `builds` config this project uses), so the
# dashboard remains the source of truth and this default tracks it; keep the env
# override in sync if the dashboard cap ever changes.
#
# RESERVE must exceed the worst-case single-block wall time + cleanup, because a
# block STARTED just before the deadline runs to completion AFTER it. Prod pv=39
# (#324) showed blocks up to ~250s (one a 249s Peak week), and the old 255s
# reserve left only ~6s of headroom over a 249s block on the 800s cap — so a
# block started near the deadline ran into the 800s wall and 504'd, losing its
# work. Raised to 330s (≈250s worst block + ~80s for persist/seam/overhead) so a
# started block always finishes and caches before the cap. Env-overridable.
_FUNCTION_CAP_S = float(os.environ.get("PLAN_GEN_FUNCTION_CAP_S", "800"))
_INVOCATION_RESERVE_S = float(os.environ.get("PLAN_GEN_INVOCATION_RESERVE_S", "330"))
_INVOCATION_BUDGET_S = max(_FUNCTION_CAP_S - _INVOCATION_RESERVE_S, 30.0)

# D-77 misconfiguration guard (#213). The reserve (330s ≈ worst ~250s block +
# persist) is sized for the 800s cap; if the deployed cap is overridden lower
# (PLAN_GEN_FUNCTION_CAP_S set below the reserve), `cap - reserve` goes negative
# and the budget SILENTLY floors to 30s. 30s can't cache a single dense week-block
# (a Build/Peak week runs ~250s), so every resumable pass 504s mid-synthesis,
# caches nothing, and the plan stalls at the wall-clock backstop with ZERO
# progress — exactly the pv=80 "3 blocks then stalled at index 3" failure. This is
# purely a config error (reserve must sit below the real Vercel Max Duration), so
# surface it LOUDLY at import instead of letting it present as a mysterious
# generation hang. Log-only: the budget value is unchanged (raising it blindly
# would 504 a block started near a too-low real cap — the cap itself must match).
if _FUNCTION_CAP_S - _INVOCATION_RESERVE_S < 30.0:
    import logging as _logging

    _logging.getLogger(__name__).error(
        "PLAN_GEN per-pass budget floored to %.0fs: reserve (%.0fs) >= function "
        "cap (%.0fs). Dense week-blocks (~250s) cannot cache within the budget — "
        "plan generation will STALL at the backstop with no progress. Set "
        "PLAN_GEN_FUNCTION_CAP_S to the deployed Vercel maxDuration (with "
        "PLAN_GEN_INVOCATION_RESERVE_S kept below it).",
        _INVOCATION_BUDGET_S,
        _INVOCATION_RESERVE_S,
        _FUNCTION_CAP_S,
    )

# D-77 advance-claim TTL (see the concurrency-guard note above). Must EXCEED the
# longest a LIVE pass can hold the claim -- the per-invocation budget plus the
# worst single block that started just under the deadline and ran to completion
# after it (+persist) -- so a working pass is never robbed of its claim mid-block;
# and stay UNDER `_STALL_WALLCLOCK_S` so a LEAKED stamp (a pass SIGKILLed before
# it cleared the column) self-heals before the stall backstop fires. Derived from
# the budget so it tracks any cap retune; capped a minute under the stall window.
_ADVANCE_LOCK_TTL_MARGIN_S = 280.0  # worst-block overrun (~250s) + persist/seam
_ADVANCE_LOCK_TTL_S = min(
    _INVOCATION_BUDGET_S + _ADVANCE_LOCK_TTL_MARGIN_S,
    _STALL_WALLCLOCK_S - 60.0,
)

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
    """Atomically claim the per-plan advance lock by stamping
    `plan_versions.advance_lock_until = now() + TTL`, but ONLY if no live claim
    exists (the column is NULL or already lapsed). Returns True iff THIS
    invocation won the claim.

    Replaces the prior session-scoped `pg_advisory_lock`, which leaked on a hard
    SIGKILL: a 504-killed pass never ran its `finally` release, so on Neon's
    transaction pooler the lock survived on the parked backend and starved every
    later advance until recycle (the pv=56 stall). The TTL stamp lapses on its
    own, so a killed claim self-heals in <= `_ADVANCE_LOCK_TTL_S`. The conditional
    UPDATE is atomic — Postgres row-locks the plan row, so of N racing cron/poller
    fires exactly one sees `advance_lock_until` still NULL/lapsed and wins; the
    rest match 0 rows. A non-Postgres FakeDb returns no row → reads as NOT
    acquired; unit tests queue an explicit claimed row to simulate a win."""
    row = db.execute(
        "UPDATE plan_versions "
        "SET advance_lock_until = now() + (? * interval '1 second') "
        "WHERE id = ? "
        "AND (advance_lock_until IS NULL OR advance_lock_until < now()) "
        "RETURNING id",
        (_ADVANCE_LOCK_TTL_S, plan_version_id),
    ).fetchone()
    return row is not None


def _release_advance_lock(db, plan_version_id: int) -> None:
    """Clear this plan's advance claim (`advance_lock_until = NULL`) in a
    `finally` around the locked pass, so the next pass reclaims immediately
    instead of waiting out the TTL. Best-effort: a release fault must not mask
    the pass's real outcome, and the TTL lapse is the backstop if this never
    runs — which is exactly the hard-SIGKILL window the TTL stamp exists to
    bound (the prior session advisory lock had no such backstop, so a skipped
    release leaked until backend recycle — pv=56)."""
    try:
        db.execute(
            "UPDATE plan_versions SET advance_lock_until = NULL WHERE id = ?",
            (plan_version_id,),
        )
    except Exception as exc:  # noqa: BLE001 — release must not mask the outcome
        print(
            f"_advance_plan_generation: advance-lock release failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {exc}"
        )


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
        "generation_units_cached, generation_stall_passes, "
        "completed_at, archived_at, "
        "refresh_nl_text, refresh_parent_version_id, "
        "refresh_triggered_by_ad_hoc_id, refresh_cap_overridden, "
        "refresh_parsed_intent_json, refresh_used_degraded "
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
        'completed_at': row['completed_at'],
        'archived_at': row['archived_at'],
        'generation_units_cached': int(row['generation_units_cached'] or 0),
        'generation_stall_passes': int(row['generation_stall_passes'] or 0),
        # #208 async-refresh inputs (NULL on plan-create rows).
        'refresh_nl_text': row['refresh_nl_text'],
        'refresh_parent_version_id': (
            int(row['refresh_parent_version_id'])
            if row['refresh_parent_version_id'] is not None else None
        ),
        'refresh_triggered_by_ad_hoc_id': (
            int(row['refresh_triggered_by_ad_hoc_id'])
            if row['refresh_triggered_by_ad_hoc_id'] is not None else None
        ),
        'refresh_cap_overridden': bool(row['refresh_cap_overridden']),
        'refresh_parsed_intent_json': row['refresh_parsed_intent_json'],
        'refresh_used_degraded': bool(row['refresh_used_degraded']),
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


def _stall_diagnostic_text(db, user_id: int, plan_version_id: int,
                           cached_blocks: int) -> str:
    """Build the stall diagnostic persisted to `generation_traceback` when the
    D-77 backstop fires. The reaper used to leave `generation_traceback` NULL (a
    stall is a wall-clock gate, not a raised exception), so a stalled plan's diag
    couldn't say WHY it stalled — only that it did. This records exactly what the
    gate measured: the anchor it timed from (the most-recent plan_create block's
    cache time, else generation start — the SAME expression as
    `_generation_stalled`), the age past which it tripped, the window, and how
    far generation got. So the token-gated diag self-explains a stall per Rule
    #14. Best-effort: any read fault degrades to the static message — it must
    never break the already-committed failure path."""
    anchor_at = age_s = gen_started_at = None
    try:
        row = db.execute(
            "SELECT "
            "  COALESCE((SELECT MAX(created_at) FROM layer4_cache "
            "             WHERE user_id = ? AND entry_point = 'plan_create' "
            "               AND phase_idx >= 0 AND phase_idx < ? "
            "               AND created_at >= pv.created_at), pv.created_at) "
            "    AS anchor_at, "
            "  EXTRACT(EPOCH FROM (NOW() - COALESCE((SELECT MAX(created_at) "
            "             FROM layer4_cache WHERE user_id = ? "
            "               AND entry_point = 'plan_create' AND phase_idx >= 0 "
            "               AND phase_idx < ? AND created_at >= pv.created_at), "
            "             pv.created_at)))::int AS age_s, "
            "  pv.created_at AS gen_started_at "
            "FROM plan_versions pv WHERE pv.id = ? AND pv.user_id = ?",
            (user_id, _SEAM_CACHE_PHASE_IDX_BASE, user_id,
             _SEAM_CACHE_PHASE_IDX_BASE, plan_version_id, user_id),
        ).fetchone()
        if row is not None:
            anchor_at = row["anchor_at"]
            age_s = row["age_s"]
            gen_started_at = row["gen_started_at"]
    except Exception:  # noqa: BLE001 — observability read must not break the failure path
        db.rollback()
    return (
        "STALL DIAGNOSTIC (not a Python traceback): the D-77 wall-clock stall "
        "backstop fired.\n"
        f"window_s={_STALL_WALLCLOCK_S} cached_blocks={cached_blocks} "
        f"next_block_index={cached_blocks}\n"
        f"last_progress_at={anchor_at} age_since_last_progress_s={age_s} "
        f"generation_started_at={gen_started_at}\n"
        "Meaning: no new plan_create week-block cached within the window — the "
        "synthesis unit (cone + the next block) did not complete within the "
        "function budget across passes. See `block_timing` / `blocks` in this "
        "diag for per-block latency and `advance_lock_until` for the lock cycle."
    )


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


def _completed_view_url(plan_version_id: int, created_via: str | None) -> str:
    """Where a finished plan-version lands. #208 — a refreshed plan opens its
    diff view (`plan_refresh.view_refresh`); a created plan opens the plan view.
    `created_via` distinguishes them (`plan_refresh_t*` vs `plan_create`)."""
    if (created_via or '').startswith('plan_refresh'):
        return url_for(
            'plan_refresh.view_refresh', plan_version_id=plan_version_id
        )
    return _view_plan_url(plan_version_id)


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
    # #208 — for an async-refresh row, record a best-effort failure entry in the
    # refresh log (the success path logs from the finalize step). A no-op for
    # plan-create rows. Isolated + best-effort so a log fault can never turn the
    # already-committed failure path back into a 500.
    try:
        from routes.plan_refresh import write_refresh_failure_log
        write_refresh_failure_log(
            db, plan_version_id, user_id, failure_reason=message
        )
    except Exception as _rl_exc:  # noqa: BLE001 — refresh-log must not break the failure path
        db.rollback()
        print(
            f"_mark_plan_failed: refresh failure-log write skipped for "
            f"plan_version_id={plan_version_id} (non-fatal): {_rl_exc}"
        )
    # #259/#260 — plan-failed email + in-app dashboard badge, ONCE across the
    # poller/cron race (atomic claim on `notified_at` inside the helper). The
    # failure is already committed above; the helper swallows every fault so a
    # notification problem can't turn this failure path back into a 500.
    notify_plan_terminal(
        db, user_id, plan_version_id,
        {'generation_status': 'failed', 'generation_error': message},
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
    # #213 — a plan parked at the Layer 3D HITL gate does NOT advance via the
    # poller/cron. It resumes only when the athlete resolves on the review screen
    # and clicks [Generate plan], which flips the row back to 'generating'. The
    # poller maps this to a redirect onto the review screen (generate_plan).
    if status == 'needs_review':
        return {"status": "needs_review"}

    # D-77 concurrency guard -- see the `_ADVANCE_LOCK_TTL_S` note. Claim the
    # per-plan advance lock; if another invocation (a concurrent cron fire or the
    # poller) holds a live claim, no-op now rather than duplicate-synthesizing the
    # same frontier week. A killed pass's claim lapses after the TTL, so the next
    # pass reclaims and resumes from the cache even if `finally` never ran.
    if not _try_acquire_advance_lock(db, plan_version_id):
        # #350 observability — this no-op was SILENT: a pass blocked on the
        # per-plan advance lock logged nothing, so a leaked/long-held lock that
        # starves every advance was invisible (had to be inferred on the
        # 2026-05-31 plan-49 stall). Log it so repeated contention is readable.
        print(
            f"_advance_plan_generation: advance lock held elsewhere for "
            f"plan_version_id={plan_version_id} — another pass in progress; "
            f"skipping (keep-polling)"
        )
        return {"status": "generating", "note": "advance_in_progress_elsewhere"}
    # Claim won. Run the locked body under try/finally so the claim is cleared on
    # EVERY exit (return or raise), letting the next pass reclaim immediately
    # rather than waiting out the TTL. A hard SIGKILL still skips this `finally`
    # — that's the leak window the TTL stamp bounds (it lapses on its own).
    try:
        return _advance_plan_generation_locked(db, uid, plan_version_id, plan_version)
    finally:
        _release_advance_lock(db, plan_version_id)


def _advance_plan_generation_locked(db, uid: int, plan_version_id: int,
                                    plan_version: dict) -> dict:
    """The body of one advance pass, run while holding the per-plan advance
    lock. Extracted from `_advance_plan_generation` so the caller can release
    the lock in a `finally` regardless of which exit path (return or raise)
    this body takes. All commits/short-circuits are unchanged."""

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
            traceback_text=_stall_diagnostic_text(
                db, uid, plan_version_id, now_cached
            ),
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

    # #208 — a refresh row reuses this whole resumable pass (stall backstop,
    # per-invocation budget, retryable-block resume, terminal-fail handling);
    # only the orchestration call + the post-`ready` side-effect differ. The
    # dispatch is purely additive — plan-create rows take the identical path.
    is_refresh = (plan_version.get('created_via') or '').startswith('plan_refresh')
    refresh_ctx = None
    try:
        with generation_deadline(_INVOCATION_BUDGET_S):
            # D-77 per-invocation budget -- stop synthesizing new blocks before
            # the function-duration cap so the pass returns cleanly (cached
            # blocks persist; next pass resumes) instead of 504-ing
            # mid-synthesis and wasting that block's Anthropic call.
            if is_refresh:
                from routes.plan_refresh import (
                    build_refresh_advance_ctx,
                    run_refresh_orchestration,
                )
                refresh_ctx = build_refresh_advance_ctx(db, uid, plan_version)
                result = run_refresh_orchestration(
                    db, uid, plan_version_id, refresh_ctx,
                    cache=_build_layer4_cache(),
                )
            else:
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
        # #259/#260 — fire the plan-ready email + arm the in-app dashboard badge
        # ONCE across the poller/cron race (atomic claim on `notified_at` inside
        # the helper). Runs AFTER the row is durable + `ready`; the helper
        # swallows every fault so a notification problem can't break generation.
        notify_plan_terminal(
            db, uid, plan_version_id,
            {**plan_version, 'generation_status': 'ready'},
        )
        # #826 — best-effort science-provenance capture. Two channels, per the
        # issue's "mixed" attribution: (1) deterministic — link the baseline
        # methodology sources every plan rests on; (2) LLM-cited — persist the
        # Layer 3A/3B source-slug citations, validating each against the store
        # (hits link the plan, misses become curation-gap flags). Runs AFTER the
        # row is durable + `ready`; isolated in its own try + commit so a
        # provenance fault can NEVER affect the already-durable plan (mirrors the
        # Layer 5A pattern). All writes are idempotent, so cron/poller replay is
        # safe.
        try:
            wrote = attach_baseline_plan_evidence(db, plan_version_id) > 0
            citations_by_layer = getattr(result, 'evidence_source_citations', None) or {}
            _layer_context = {
                'layer3a': 'Layer 3A — athlete-state assessment',
                'layer3b': 'Layer 3B — goal viability & periodization',
            }
            for layer_key, slugs in citations_by_layer.items():
                cites = [
                    {'slug': slug,
                     'context_text': _layer_context.get(layer_key, layer_key)}
                    for slug in (slugs or [])
                ]
                if cites:
                    record_plan_evidence_citations(
                        db, plan_version_id, layer_key, cites)
                    wrote = True
            if wrote:
                db.commit()
        except Exception as _ev_exc:  # noqa: BLE001 — provenance must not break gen
            db.rollback()
            print(
                f"_advance_plan_generation: evidence provenance capture failed "
                f"for plan_version_id={plan_version_id} (non-fatal): {_ev_exc}"
            )
        if is_refresh:
            # #208 — record the successful refresh (diff vs parent + attribution)
            # in the refresh log, mirroring the synchronous route's success path.
            # Best-effort: the plan is already durable + `ready`, so a log fault
            # must never propagate.
            try:
                from routes.plan_refresh import finalize_refresh_success_log
                finalize_refresh_success_log(
                    db, uid, plan_version_id, result, refresh_ctx
                )
            except Exception as _rl_exc:  # noqa: BLE001 — log must not break gen
                db.rollback()
                print(
                    f"_advance_plan_generation: refresh success-log write failed "
                    f"for plan_version_id={plan_version_id} (non-fatal): {_rl_exc}"
                )
        else:
            # Layer 5A — best-effort post-`ready` deterministic nutrition
            # synthesis. The plan is already durable + `ready` above; a nutrition
            # fault must NEVER affect it, so it's isolated in its own try and
            # never propagates (mirrors the progress-block snapshot pattern).
            # Zero-LLM + fast, so it's safe to run inline on the completing pass.
            # Commit only when something was actually persisted, so the common
            # no-inputs case adds no extra commit (and no DB work).
            try:
                if generate_and_persist_plan_nutrition(db, uid, plan_version_id) is not None:
                    db.commit()
            except Exception as _nutr_exc:  # noqa: BLE001 — advisory must not break gen
                db.rollback()
                print(
                    f"_advance_plan_generation: post-ready nutrition synthesis failed "
                    f"for plan_version_id={plan_version_id} (non-fatal): {_nutr_exc}"
                )

            # Layer 5B — best-effort post-`ready` conditions/clothing advisory.
            # Isolated in its own try (a separate stage from 5A so a fault in one
            # never skips the other). Unlike 5A this makes bounded climate-normal
            # lookups (memoized per locale-month, ≤6 s each, degrade to None), so
            # worst case it just doesn't persist this pass — the plan is already
            # durable + `ready`, and the user can regenerate from the view.
            try:
                if generate_and_persist_plan_conditions(db, uid, plan_version_id) is not None:
                    db.commit()
            except Exception as _cond_exc:  # noqa: BLE001 — advisory must not break gen
                db.rollback()
                print(
                    f"_advance_plan_generation: post-ready conditions synthesis failed "
                    f"for plan_version_id={plan_version_id} (non-fatal): {_cond_exc}"
                )
        return {"status": "ready"}
    except Layer3DGateBlocked as exc:
        # #213 — the Layer 3D HITL gate is non-green: the plan needs athlete
        # review before synthesis. NOT a failure. The orchestrator already
        # persisted the gate JSONB inside this transaction (no DB error preceded
        # the raise, so the txn is healthy — do NOT roll back, or we'd discard the
        # gate write). Flip the row to `needs_review` and commit both. The athlete
        # resolves on the review screen and clicks [Generate plan], which flips
        # back to 'generating' and resumes this loop (the gate re-evaluates with
        # the stored resolutions).
        db.execute(
            "UPDATE plan_versions SET generation_status = 'needs_review', "
            "generation_error = NULL WHERE id = ? AND user_id = ?",
            (plan_version_id, uid),
        )
        db.commit()
        print(
            f"_advance_plan_generation: Layer 3D gate {exc.gate.gate_status} for "
            f"plan_version_id={plan_version_id} — parked at needs_review with "
            f"{len(exc.gate.items)} review item(s)"
        )
        return {"status": "needs_review"}
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
        # Non-retryable Layer4OutputError (a genuine contract/output fault, e.g.
        # an unparseable seam verdict). Mirror the Layer3 branch below: log the
        # code+detail AND persist the traceback to `generation_traceback` so the
        # cause is readable via the token-gated diag endpoint next time, instead
        # of dying with only the generic code (the pv=55 blind spot — Rule #14).
        print(
            f"_advance_plan_generation: Layer4 {type(exc).__name__} "
            f"({exc.code}) for plan_version_id={plan_version_id}: "
            f"{getattr(exc, 'detail', None)}"
        )
        return _mark_plan_failed(
            db, plan_version_id, uid,
            f"Plan synthesis failed ({exc.code}). Adjust your inputs and try again.",
            traceback_text=traceback.format_exc(),
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

        # #213 — one plan in flight at a time (Layer3D_Spec §11.1). An athlete may
        # have at most one plan in `generating`/`needs_review`; starting a new
        # create while one is parked or building is refused with a pointer back to
        # it (resume or cancel). Keeps the model simple at handful-of-athletes
        # scale.
        in_flight = db.execute(
            "SELECT id, generation_status FROM plan_versions "
            "WHERE user_id = ? AND generation_status IN ('generating', 'needs_review') "
            "AND superseded_at IS NULL "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (uid,),
        ).fetchone()
        if in_flight is not None:
            if in_flight['generation_status'] == 'needs_review':
                flash(
                    "You have a plan waiting for review. Resolve or cancel it "
                    "before starting a new one.", 'warning',
                )
                return redirect(url_for(
                    'plan_create.plan_review', plan_version_id=in_flight['id']
                ))
            flash(
                "A plan is already generating. Let it finish or cancel it before "
                "starting a new one.", 'warning',
            )
            return redirect(url_for(
                'plan_create.plan_progress', plan_version_id=in_flight['id']
            ))

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
    # Slice 5b (#581 WS-H) — surface the athlete's standing event windows for
    # REVIEW at plan generation (F1). Editing/appending round-trips to the
    # dedicated /profile/event-windows page (return_to back here); only upcoming
    # windows (end_date today-or-later) are worth reviewing for a new plan.
    today = date.today()
    event_windows = [w for w in load_event_windows(db, uid) if w.end_date >= today]
    return render_template(
        'plan_create/new_form.html',
        race_event=race_event,
        today_iso=today.isoformat(),
        event_windows=event_windows,
    )


def _coerce_view_date(value) -> date | None:
    """Best-effort coerce a plan_versions date column to a `date` for the
    lifecycle label. psycopg returns DATE as `date` already; the render
    harness's fake cursor hands back ISO strings. Returns None for anything
    unparseable so a bad value just degrades the label rather than 500-ing."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _plan_lifecycle_label(plan_version: dict, today: date) -> str:
    """State-appropriate label for a READY plan (#618 — never surface the raw
    internal `created_via`, e.g. 'plan create', to the athlete). Mirrors the
    plans-list bucketing in `routes/plans.py` so the vocabulary matches."""
    if plan_version.get('archived_at') is not None:
        return 'Archived'
    if plan_version.get('completed_at') is not None:
        return 'Completed'
    end = _coerce_view_date(plan_version.get('scope_end_date'))
    start = _coerce_view_date(plan_version.get('scope_start_date'))
    if end is not None and end < today:
        return 'Completed'
    if start is not None and start > today:
        return 'Upcoming'
    return 'Active'


def _plan_days_with_rest_gaps(sessions_by_date: dict) -> list:
    """Ordered `(date, day_of_week, sessions)` covering every calendar day from
    the first to the last session date, with off days as explicit rest (#618).

    Thin wrapper over the shared `plan_sessions_repo.fill_rest_gaps` rule so the
    plan's daily view and the home Today/Tomorrow cards stay in lockstep — the
    rest-day-as-absence convention lives in exactly one place (#888)."""
    return fill_rest_gaps(sessions_by_date)


@bp.route('/<int:plan_version_id>', methods=['GET'])
def view_plan(plan_version_id: int):
    """Render the plan: scope dates + per-session list grouped by date, with
    off days shown as explicit rest. 404 + cross-user-defense via the user_id
    filter in `_load_plan_version`."""
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

    # Layer 5A — the per-day + plan-level nutrition artifact (None until the
    # post-`ready` stage has run); keyed by date for the per-day cards. Advisory:
    # a nutrition load fault must NEVER 500 the plan view, so degrade to "no
    # nutrition" rather than propagate.
    try:
        nutrition = load_plan_nutrition_by_version(db, plan_version_id)
    except Exception as _nutr_exc:  # noqa: BLE001 — advisory must not break the view
        print(
            f"view_plan: nutrition load failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {_nutr_exc}"
        )
        nutrition = None
    nutrition_by_date = (
        {day.date: day for day in nutrition.days} if nutrition else {}
    )

    # Layer 5B — the per-day conditions/clothing advisory (None until the
    # post-`ready` stage has run, or absent when no session locale carried
    # coordinates); keyed by date for the per-day cards. Advisory: a load fault
    # must NEVER 500 the plan view, so degrade to "no conditions".
    try:
        conditions = load_plan_conditions_by_version(db, plan_version_id)
    except Exception as _cond_exc:  # noqa: BLE001 — advisory must not break the view
        print(
            f"view_plan: conditions load failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {_cond_exc}"
        )
        conditions = None
    conditions_by_date = (
        {day.date: day for day in conditions.days} if conditions else {}
    )

    # #1035 — the live upcoming-conditions extremes the conditions-advisory nudge
    # fires on. The advisory deep-links to this plan view, which otherwise shows
    # only the Layer-5B climate *normals*; surface the live forecast days that
    # crossed a heat/freeze/rain threshold beside them so the CTA lands on the
    # forecast that triggered it. Shares the nudge's thresholds (no drift).
    # Advisory: a load fault must NEVER 500 the plan view, so degrade to none.
    try:
        from routes.nudges import select_upcoming_extremes
        from upcoming_conditions_repo import load_upcoming_for_user
        upcoming_extremes = select_upcoming_extremes(
            load_upcoming_for_user(db, uid)
        )
        if upcoming_extremes:  # Rule #15 — which days the surface flagged + why.
            print(
                f"[conditions-surface] user={uid} pv={plan_version_id} "
                f"extreme_days={len(upcoming_extremes)} "
                f"dates={[e['date'].isoformat() for e in upcoming_extremes]}"
            )
    except Exception as _uc_exc:  # noqa: BLE001 — advisory must not break the view
        print(
            f"view_plan: upcoming-conditions load failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {_uc_exc}"
        )
        upcoming_extremes = []

    plan_name = generated_plan_name(
        target_race_name(db, uid),
        plan_version['scope_start_date'],
        plan_version['scope_end_date'],
    )

    # #826 — the always-visible "science behind your plan" panel. Read-only; a
    # load fault must NEVER 500 the plan view, so degrade to no panel. Empty
    # until the completing pass has linked the baseline sources.
    try:
        evidence_sources = load_plan_evidence(db, plan_version_id)
    except Exception as _ev_exc:  # noqa: BLE001 — advisory must not break the view
        print(
            f"view_plan: evidence load failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {_ev_exc}"
        )
        evidence_sources = []

    # #732 slice 3 — race-week-brief trigger gate. The brief unlocks within 14
    # days of a target event (the orchestrator's auto-fire window); surface the
    # [Generate race-week brief] button only inside that window and a link to the
    # stored brief once it exists. Advisory: any fault here must NEVER 500 the
    # plan view, so degrade to "button hidden".
    race_week_brief_available = False
    race_week_brief_exists = False
    days_to_event = None
    try:
        target_race = load_target_race_event_payload(db, uid)
        if target_race is not None and getattr(target_race, 'event_date', None):
            days_to_event = (target_race.event_date - date.today()).days
            race_week_brief_available = 1 <= days_to_event <= 14
        race_week_brief_exists = load_race_week_brief(db, plan_version_id) is not None
    except Exception as _rwb_exc:  # noqa: BLE001 — advisory must not break the view
        print(
            f"view_plan: race-week-brief gate check failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {_rwb_exc}"
        )

    # Item B (§5.4 Slice 2) — list the plan's informational gate items (the
    # advisory coaching_flags 3C surfaces + any 3B informational note) as
    # plan-page coaching notes. They never parked this plan, so the review screen
    # never showed them on a clean run; surface them here so a green plan still
    # carries the cross-node context. Fail-safe inside the helper.
    coaching_notes = _plan_coaching_notes(db, uid, plan_version_id)

    return render_template(
        'plan_create/view.html',
        plan_version=plan_version,
        plan_version_id=plan_version_id,
        plan_name=plan_name,
        coaching_notes=coaching_notes,
        evidence_sources=evidence_sources,
        lifecycle_state=_plan_lifecycle_label(plan_version, date.today()),
        days=_plan_days_with_rest_gaps(sessions_by_date),
        session_count=len(sessions),
        nutrition=nutrition,
        nutrition_by_date=nutrition_by_date,
        conditions=conditions,
        conditions_by_date=conditions_by_date,
        upcoming_extremes=upcoming_extremes,
        zwift_exportable=is_zwift_exportable,
        race_week_brief_available=race_week_brief_available,
        race_week_brief_exists=race_week_brief_exists,
        days_to_event=days_to_event,
    )


@bp.route('/<int:plan_version_id>/complete', methods=['POST'])
def mark_plan_complete(plan_version_id: int):
    """Manually file a ready plan under Completed on the Plan list, regardless
    of its scope dates — for when the athlete cancels a plan or it was
    superseded and they want it out of Upcoming/Active. Idempotent: only stamps
    a row that's `ready` and not already completed; the user_id filter is the
    cross-user guard. Redirects back to the list either way."""
    db = get_db()
    uid = current_user_id()
    db.execute(
        "UPDATE plan_versions SET completed_at = NOW() "
        "WHERE id = ? AND user_id = ? AND generation_status = 'ready' "
        "AND completed_at IS NULL",
        (plan_version_id, uid),
    )
    db.commit()
    flash("Plan marked complete.", 'success')
    return redirect(url_for('plans.list_plans'))


@bp.route('/<int:plan_version_id>/reopen', methods=['POST'])
def reopen_plan(plan_version_id: int):
    """Clear a manual completion stamp, returning the plan to its date-derived
    bucket (Upcoming/Active/Completed) on the Plan list. Inverse of
    `mark_plan_complete`; same cross-user guard + redirect."""
    db = get_db()
    uid = current_user_id()
    db.execute(
        "UPDATE plan_versions SET completed_at = NULL "
        "WHERE id = ? AND user_id = ?",
        (plan_version_id, uid),
    )
    db.commit()
    flash("Plan reopened.", 'success')
    return redirect(url_for('plans.list_plans'))


@bp.route('/<int:plan_version_id>/archive', methods=['POST'])
def archive_plan(plan_version_id: int):
    """Shelve a plan the athlete quit or that a refresh superseded, without
    implying completion. Archived plans drop off the active Plan list into its
    Archived section (still openable + restorable). Distinct from
    `mark_plan_complete` (which implies the plan was finished). Same cross-user
    guard + redirect."""
    db = get_db()
    uid = current_user_id()
    db.execute(
        "UPDATE plan_versions SET archived_at = NOW() "
        "WHERE id = ? AND user_id = ? AND archived_at IS NULL",
        (plan_version_id, uid),
    )
    db.commit()
    flash("Plan archived.", 'secondary')
    return redirect(url_for('plans.list_plans'))


@bp.route('/<int:plan_version_id>/unarchive', methods=['POST'])
def unarchive_plan(plan_version_id: int):
    """Clear an archive stamp, returning the plan to its date-derived bucket on
    the Plan list. Inverse of `archive_plan`; same cross-user guard + redirect."""
    db = get_db()
    uid = current_user_id()
    db.execute(
        "UPDATE plan_versions SET archived_at = NULL "
        "WHERE id = ? AND user_id = ?",
        (plan_version_id, uid),
    )
    db.commit()
    flash("Plan restored.", 'success')
    return redirect(url_for('plans.list_plans'))


@bp.route('/<int:plan_version_id>/notification/dismiss', methods=['POST'])
def dismiss_notification(plan_version_id: int):
    """Dismiss the in-app plan-ready/plan-failed dashboard badge (#259/#260) by
    stamping `notification_seen_at`. Scoped to `(id, user_id)` so a crafted POST
    for another athlete's plan is a no-op. Redirects back to the referrer (the
    badge renders on the dashboard) with a dashboard fallback."""
    from plan_notifications import mark_plan_notification_seen
    db = get_db()
    uid = current_user_id()
    mark_plan_notification_seen(db, uid, plan_version_id)
    return redirect(request.referrer or url_for('dashboard.index'))


@bp.route('/<int:plan_version_id>/delete', methods=['POST'])
def delete_plan(plan_version_id: int):
    """Hard-delete a generated plan version + its sessions/nutrition (ON DELETE
    CASCADE handles plan_sessions / plan_progress_blocks / plan_nutrition /
    plan_nutrition_inputs). The non-cascading back-references — a superseded
    predecessor's `superseded_by_version_id` pointer, a refresh child's
    `refresh_parent_version_id` pointer, and the plan_refresh_log audit rows —
    are nulled first so the DELETE doesn't trip an FK violation. (A plan that was
    later refreshed is the `refresh_parent_version_id` of its child version; that
    pointer 500'd the delete before it was nulled here — #688.) Cross-user guard
    via the ownership check + the user_id filter on every write."""
    db = get_db()
    uid = current_user_id()
    if not db.execute(
        'SELECT 1 FROM plan_versions WHERE id = ? AND user_id = ?',
        (plan_version_id, uid),
    ).fetchone():
        flash("Plan not found.", 'danger')
        return redirect(url_for('plans.list_plans'))
    db.execute(
        "UPDATE plan_versions SET superseded_by_version_id = NULL "
        "WHERE superseded_by_version_id = ? AND user_id = ?",
        (plan_version_id, uid),
    )
    db.execute(
        "UPDATE plan_versions SET refresh_parent_version_id = NULL "
        "WHERE refresh_parent_version_id = ? AND user_id = ?",
        (plan_version_id, uid),
    )
    db.execute(
        "UPDATE plan_refresh_log SET plan_version_id_before = NULL "
        "WHERE plan_version_id_before = ? AND user_id = ?",
        (plan_version_id, uid),
    )
    db.execute(
        "UPDATE plan_refresh_log SET plan_version_id_after = NULL "
        "WHERE plan_version_id_after = ? AND user_id = ?",
        (plan_version_id, uid),
    )
    db.execute(
        "DELETE FROM plan_versions WHERE id = ? AND user_id = ?",
        (plan_version_id, uid),
    )
    db.commit()
    print(
        f"delete_plan: pv={plan_version_id} user={uid} deleted "
        "(nulled superseded_by/refresh_parent back-refs + refresh-log audit)"
    )
    flash("Plan deleted.", 'warning')
    return redirect(url_for('plans.list_plans'))


@bp.route('/<int:plan_version_id>/nutrition/regenerate', methods=['POST'])
def regenerate_nutrition(plan_version_id: int):
    """Manually (re)generate the Layer 5A nutrition for a ready plan.

    The auto-trigger runs once when a plan flips `ready`; this lets the athlete
    re-run it on demand (e.g. after the energy model improves, or if the
    best-effort auto-run was skipped). Same cross-user guard as the other
    per-plan actions; redirects back to the plan view either way.
    """
    db = get_db()
    uid = current_user_id()
    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)
    if plan_version['generation_status'] != 'ready':
        flash("Nutrition is only available once the plan is ready.", 'error')
        return redirect(_view_plan_url(plan_version_id))
    try:
        result = generate_and_persist_plan_nutrition(db, uid, plan_version_id)
        db.commit()
        if result is None:
            flash(
                "Nutrition inputs aren't available for this plan — regenerate "
                "the plan to enable nutrition.",
                'error',
            )
        else:
            flash("Nutrition regenerated.", 'success')
    except Exception as exc:  # noqa: BLE001 — surface a friendly message, don't 500
        db.rollback()
        print(
            f"regenerate_nutrition: failed for plan_version_id={plan_version_id}: {exc}"
        )
        flash("Couldn't regenerate nutrition. Please try again.", 'error')
    return redirect(_view_plan_url(plan_version_id))


@bp.route('/<int:plan_version_id>/conditions/regenerate', methods=['POST'])
def regenerate_conditions(plan_version_id: int):
    """Manually (re)generate the Layer 5B conditions advisory for a ready plan.

    The auto-trigger runs once when a plan flips `ready`; this lets the athlete
    re-run it on demand (e.g. after adding coordinates to a locale, or if the
    best-effort auto-run was skipped or the weather source was unreachable).
    Same cross-user guard as the other per-plan actions; redirects back to the
    plan view either way.
    """
    db = get_db()
    uid = current_user_id()
    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)
    if plan_version['generation_status'] != 'ready':
        flash("Conditions are only available once the plan is ready.", 'error')
        return redirect(_view_plan_url(plan_version_id))
    try:
        result = generate_and_persist_plan_conditions(db, uid, plan_version_id)
        db.commit()
        if result is None:
            flash(
                "Conditions couldn't be derived — add coordinates to this plan's "
                "locales (via Locations) and try again.",
                'error',
            )
        else:
            flash("Conditions regenerated.", 'success')
    except Exception as exc:  # noqa: BLE001 — surface a friendly message, don't 500
        db.rollback()
        print(
            f"regenerate_conditions: failed for plan_version_id={plan_version_id}: {exc}"
        )
        flash("Couldn't regenerate conditions. Please try again.", 'error')
    return redirect(_view_plan_url(plan_version_id))


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
        return redirect(
            _completed_view_url(plan_version_id, plan_version.get('created_via'))
        )
    # #213 — a plan parked at the HITL gate sends the athlete to the review
    # screen rather than the (idle) progress poller.
    if plan_version['generation_status'] == 'needs_review':
        return redirect(
            url_for('plan_create.plan_review', plan_version_id=plan_version_id)
        )

    return render_template(
        'plan_create/progress.html',
        plan_version=plan_version,
        generate_url=url_for(
            'plan_create.generate_plan', plan_version_id=plan_version_id
        ),
        view_url=_completed_view_url(
            plan_version_id, plan_version.get('created_via')
        ),
        new_url=url_for('plan_create.new_plan'),
    )


# ─── Layer 3D HITL review screen (#213, Layer3D_Spec §11) ────────────────────


def _grouped_gate_items(gate) -> dict:
    """Group a gate's items by severity for the review template (blockers first).
    Recomputes each item's display status from its stored resolution (§6.3) so
    the screen always reflects the latest resolved/pending state."""
    buckets = {"blocker": [], "warning": [], "informational": []}
    for it in gate.items:
        it.status = resolved_status(it)
        buckets.setdefault(it.severity, []).append(it)
    return buckets


# `revise_target` values that resolve to an athlete-profile edit surface. After
# the #894 IA reorg these no longer all share one URL: disciplines stay on the
# Athlete tab (`profile.edit`), nutrition moved to the Fuel & health tab
# (`profile.edit?tab=health`), and availability/schedule moved to its own page
# under "Train" (`profile.schedule`). `profile.injuries` and the 3B `h2.*` race
# inputs resolve elsewhere. Each entry is `(endpoint, url_for kwargs)`.
_PROFILE_REVISE_SURFACES = {
    "profile.disciplines": ("profile.edit", {}),
    "profile.nutrition": ("profile.edit", {"tab": "health"}),
    "profile.availability": ("profile.schedule", {}),
    # 3C (§5.4) CN-1/CN-2 fixes live across the locale equipment editors; the
    # finding spans every locale, so we link to the locations list (the entry to
    # each per-locale editor) rather than one deep `locales.edit_profile` link.
    "profile.locales": ("locales.list_profiles", {}),
}


def _safe_url(endpoint: str, **values) -> str | None:
    """`url_for` that yields None instead of raising for an unregistered/renamed
    endpoint — a missing revise surface degrades to the plain-text target rather
    than 500-ing the review screen (same fail-safe posture as the staleness
    probe)."""
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return None


def _build_revise_urls(db, uid: int, gate) -> dict[str, str]:
    """`{revise_target -> edit-surface URL}` for the gate's items, so the review
    screen can render a [Fix this] link that takes the athlete straight to the
    input behind each finding (#213). Maps:

      * `profile.injuries`             -> the injuries list/editor
      * `profile.disciplines`          -> the Athlete tab
      * `profile.nutrition`            -> the Fuel & health tab
      * `profile.availability`         -> the standalone Schedule page
      * `profile.locales`              -> the locations list (3C §5.4 CN-1/CN-2)
      * 3B `h2.*` (target-race inputs) -> the target race editor

    A target with no edit surface (e.g. 3B `h3.plan_duration_weeks` on an
    open-ended plan), or one whose surface can't be resolved (no target race, or
    an unregistered endpoint), is omitted — the template falls back to naming the
    target. Never raises: revise-link resolution must not break the review
    render."""
    targets = {it.revise_target for it in gate.items if it.revise_target}
    urls: dict[str, str] = {}
    if not targets:
        return urls

    if "profile.injuries" in targets:
        url = _safe_url("injuries.list_entries")
        if url:
            urls["profile.injuries"] = url

    for t in targets & set(_PROFILE_REVISE_SURFACES):
        endpoint, kwargs = _PROFILE_REVISE_SURFACES[t]
        url = _safe_url(endpoint, **kwargs)
        if url:
            urls[t] = url

    if any(t.startswith("h2.") for t in targets):
        try:
            race = load_target_race_event_payload(db, uid)
        except Exception:  # noqa: BLE001 — never break review over a revise link
            race = None
        url = (
            _safe_url("race_events.edit_race", race_event_id=race.race_event_id)
            if race is not None
            else None
        )
        if url:
            for t in targets:
                if t.startswith("h2."):
                    urls[t] = url

    return urls


def _plan_coaching_notes(db, uid: int, plan_version_id: int) -> list:
    """The plan's display-only (`informational`) gate items — the advisory
    `coaching_flags` 3C surfaces (§5.4 Slice 2) plus any 3B `informational`
    surface — for listing as plan-page coaching notes on a generated plan.

    These never park a plan (`compute_gate_status` treats `informational` as
    non-gating), so the review screen only shows them when *something else* parks
    the plan; a fully-green plan never displays them. Surface them on the plan
    home so the athlete still sees the cross-node context (e.g. an included
    discipline that's gear-gated at every locale) on a clean plan.

    Advisory — a gate load/parse fault must NEVER 500 the plan view, so degrade to
    no notes (mirrors the nutrition/conditions/evidence loads in `view_plan`)."""
    try:
        gate = load_hitl_gate(db, uid, plan_version_id)
    except Exception as exc:  # noqa: BLE001 — advisory must not break the view
        print(
            f"_plan_coaching_notes: gate load failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {exc}"
        )
        return []
    if gate is None:
        return []
    return [it for it in gate.items if it.severity == "informational"]


def _gate_inputs_changed(db, uid: int, plan_version: dict, gate) -> bool:
    """True when the athlete's gate-relevant inputs changed since the parked gate
    was evaluated (Reading-B staleness check, #213). Recomputes the
    `input_fingerprint` from current inputs (cheap — no LLM) and compares it to
    the one stamped at park time.

    A gate with no stored fingerprint (a green gate, or one parked before this
    shipped) can't be checked → treated as fresh. Fail-safe: any error recomputing
    the fingerprint (e.g. the athlete deleted their home locale while parked) is
    swallowed and treated as fresh, so the staleness probe can never 500 the
    review screen — the next [Generate] re-evaluates against current inputs and
    surfaces any such gap there."""
    if gate is None or getattr(gate, "input_fingerprint", None) is None:
        return False
    try:
        current = compute_gate_input_fingerprint(
            db,
            uid,
            target_race_event=load_target_race_event_payload(db, uid),
            plan_start_date=plan_version["scope_start_date"],
            today=date.today(),
        )
    except Exception as exc:  # noqa: BLE001 — staleness probe must not break review
        print(
            f"plan_review: gate staleness probe failed for "
            f"plan_version_id={plan_version.get('id')} (treating as fresh): {exc}"
        )
        return False
    return current != gate.input_fingerprint


def _rekick_stale_gate(db, uid: int, plan_version_id: int):
    """Flip a parked plan back to `generating` so the resumable poller re-runs the
    pipeline and re-evaluates the Layer 3D gate against current inputs — re-parking
    with fresh findings, or proceeding if the athlete's edit cleared the gate. The
    UPDATE is guarded on `needs_review` so concurrent re-kicks are idempotent.
    Returns a redirect to the progress screen."""
    # Rule #15 — make the staleness re-fire observable so its firing frequency
    # is visible in `/admin/logs` (#213 Reading-B). The fingerprint is a single
    # opaque digest, so the changed leaf input isn't recoverable here; the event
    # + plan is the signal.
    print(
        f"_rekick_stale_gate: plan_version_id={plan_version_id} uid={uid} — "
        f"Layer 3D gate inputs changed since park; needs_review -> generating "
        f"to re-evaluate (#213 Reading-B staleness)"
    )
    db.execute(
        "UPDATE plan_versions SET generation_status = 'generating', "
        "generation_error = NULL WHERE id = ? AND user_id = ? "
        "AND generation_status = 'needs_review'",
        (plan_version_id, uid),
    )
    db.commit()
    flash(
        "Your details changed since this review — refreshing your plan against "
        "the latest.", 'secondary',
    )
    return redirect(
        url_for('plan_create.plan_progress', plan_version_id=plan_version_id)
    )


@bp.route('/<int:plan_version_id>/review', methods=['GET'])
def plan_review(plan_version_id: int):
    """The HITL review screen for a plan parked at `needs_review`. Lists the
    aggregated gate items grouped by severity (blockers first), each with its
    affordance: warnings/informational get [Acknowledge]; blockers are
    revise-only (Slice 1 surfaces the revise_target; the revise cascade is a
    later slice). A ready/generating plan redirects to its own screen."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)
    status = plan_version['generation_status']
    if status == 'ready':
        return redirect(
            _completed_view_url(plan_version_id, plan_version.get('created_via'))
        )
    if status == 'generating':
        return redirect(
            url_for('plan_create.plan_progress', plan_version_id=plan_version_id)
        )

    gate = load_hitl_gate(db, uid, plan_version_id)
    if gate is None:
        # No gate persisted (e.g. a row stuck at needs_review with no blob) —
        # nothing to review; send the athlete back to the list rather than a
        # blank screen.
        flash("No review items found for this plan.", 'secondary')
        return redirect(url_for('plans.list_plans'))

    if _gate_inputs_changed(db, uid, plan_version, gate):
        # The athlete edited something (or new training data synced) since this
        # gate was evaluated — the items below are stale. Re-run the pipeline so
        # the review reflects current reality (#213 Reading-B staleness).
        return _rekick_stale_gate(db, uid, plan_version_id)

    resp = make_response(render_template(
        'plan_create/review.html',
        plan_version=plan_version,
        gate=gate,
        grouped=_grouped_gate_items(gate),
        revise_urls=_build_revise_urls(db, uid, gate),
        resolve_url=url_for(
            'plan_create.resolve_review_item', plan_version_id=plan_version_id
        ),
        recheck_url=url_for(
            'plan_create.recheck_review', plan_version_id=plan_version_id
        ),
        generate_url=url_for(
            'plan_create.generate_from_review', plan_version_id=plan_version_id
        ),
        cancel_url=url_for(
            'plan_create.delete_plan', plan_version_id=plan_version_id
        ),
        plans_url=url_for('plans.list_plans'),
    ))
    # The review screen must re-fetch on browser back/forward rather than restore
    # from the bfcache — otherwise an athlete who clicks [Fix this], edits the
    # blocker, and hits Back lands on a stale page where "nothing happened" and the
    # only recourse is a manual reload. `no-store` forces a real GET on return, so
    # the staleness re-check (`_gate_inputs_changed`) fires and re-evaluates the
    # gate against the edit (#960). The template's `pageshow` handler is the
    # belt-and-suspenders for browsers that restore from bfcache anyway.
    resp.headers['Cache-Control'] = 'no-store, must-revalidate'
    return resp


@bp.route('/<int:plan_version_id>/review/resolve', methods=['POST'])
def resolve_review_item(plan_version_id: int):
    """Record an athlete acknowledgment of a single warning/informational gate
    item (Slice 1 = acknowledge path only; the revise cascade is a later slice).
    Recomputes the gate status and persists. A blocker can't be acknowledged
    (§5.1) — the route rejects it."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None or plan_version['generation_status'] != 'needs_review':
        abort(404)

    gate = load_hitl_gate(db, uid, plan_version_id)
    if gate is None:
        abort(404)

    if _gate_inputs_changed(db, uid, plan_version, gate):
        # Inputs changed under the athlete — the item they're acknowledging may no
        # longer exist (or now reads differently). Don't record a resolution
        # against a stale finding; bounce to the review screen, which re-kicks a
        # fresh gate evaluation (#213 Reading-B staleness).
        return redirect(
            url_for('plan_create.plan_review', plan_version_id=plan_version_id)
        )

    item_key = (request.form.get('item_key') or '').strip()
    reasoning = (request.form.get('reasoning') or '').strip() or None
    target = next((it for it in gate.items if it.item_key == item_key), None)
    if target is None:
        flash("That review item is no longer present.", 'warning')
        return redirect(
            url_for('plan_create.plan_review', plan_version_id=plan_version_id)
        )
    if not target.can_acknowledge:
        # A blocker is revise-only — no acknowledge escape hatch (§5.1/§6.3).
        flash(
            "This item is a blocker and can't be acknowledged — it must be fixed "
            "before the plan can be generated.", 'danger',
        )
        return redirect(
            url_for('plan_create.plan_review', plan_version_id=plan_version_id)
        )

    from datetime import datetime, timezone
    target.resolution = GateResolution(
        kind='acknowledged', reasoning=reasoning,
        resolved_at=datetime.now(timezone.utc),
    )
    for it in gate.items:
        it.status = resolved_status(it)
    gate.gate_status = compute_gate_status(gate.items)
    save_hitl_gate(db, uid, plan_version_id, gate)
    db.commit()

    flash("Noted.", 'success')
    return redirect(
        url_for('plan_create.plan_review', plan_version_id=plan_version_id)
    )


@bp.route('/<int:plan_version_id>/review/generate', methods=['POST'])
def generate_from_review(plan_version_id: int):
    """[Generate plan] from the review screen: only proceeds when the persisted
    gate is green (every item resolved). Flips the row back to `generating` and
    hands off to the progress poller, which resumes the advance loop — the gate
    re-evaluates against the stored resolutions and lets synthesis run."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None or plan_version['generation_status'] != 'needs_review':
        abort(404)

    gate = load_hitl_gate(db, uid, plan_version_id)
    if gate is not None:
        for it in gate.items:
            it.status = resolved_status(it)
        gate.gate_status = compute_gate_status(gate.items)
    # When the athlete's inputs changed since parking, the stored verdict is stale
    # — don't trust its green/non-green. Flip to generating regardless and let the
    # resumed orchestrator re-evaluate against current reality: it re-parks if a
    # new blocker appeared, or proceeds if the edit cleared the gate. Only when the
    # inputs are unchanged do we hold the "every item resolved" guard, which closes
    # the bug where a stale stored-non-green blocked an athlete who'd already fixed
    # the issue (#213 Reading-B staleness).
    if not _gate_inputs_changed(db, uid, plan_version, gate) and (
        gate is None or gate.gate_status != 'green'
    ):
        flash(
            "Resolve every item before generating the plan.", 'warning',
        )
        return redirect(
            url_for('plan_create.plan_review', plan_version_id=plan_version_id)
        )

    db.execute(
        "UPDATE plan_versions SET generation_status = 'generating', "
        "generation_error = NULL WHERE id = ? AND user_id = ? "
        "AND generation_status = 'needs_review'",
        (plan_version_id, uid),
    )
    db.commit()
    return redirect(
        url_for('plan_create.plan_progress', plan_version_id=plan_version_id)
    )


@bp.route('/<int:plan_version_id>/review/recheck', methods=['POST'])
def recheck_review(plan_version_id: int):
    """Athlete-initiated "I've fixed it — re-check" from the review screen (#960).

    The deliberate counterpart to the automatic Reading-B staleness re-kick: a
    blocker can't be acknowledged (§5.1), so fix-the-input → re-check is the only
    path forward, and the athlete shouldn't have to discover that by reloading the
    page. Flips the parked row back to `generating` and hands off to the progress
    poller, which re-runs the pipeline and re-evaluates the Layer 3D gate against
    current inputs — re-parking with fresh findings, or proceeding to synthesis if
    the edit cleared the gate. The UPDATE is guarded on `needs_review` so repeat
    clicks are idempotent."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None or plan_version['generation_status'] != 'needs_review':
        abort(404)

    db.execute(
        "UPDATE plan_versions SET generation_status = 'generating', "
        "generation_error = NULL WHERE id = ? AND user_id = ? "
        "AND generation_status = 'needs_review'",
        (plan_version_id, uid),
    )
    db.commit()
    # Rule #15 — make athlete-initiated re-checks observable in /admin/logs so
    # their frequency is visible alongside the automatic staleness re-fires.
    print(
        f"recheck_review: plan_version_id={plan_version_id} uid={uid} — "
        f"athlete-initiated re-check; needs_review -> generating to re-evaluate "
        f"the Layer 3D gate against current inputs (#960)"
    )
    flash("Re-checking your plan against your latest changes…", 'secondary')
    return redirect(
        url_for('plan_create.plan_progress', plan_version_id=plan_version_id)
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
        # Refreshed plans open their diff view; created plans the plan view.
        plan_version = _load_plan_version(db, uid, plan_version_id)
        created_via = plan_version.get('created_via') if plan_version else None
        return jsonify({
            "status": "ready",
            "redirect": _completed_view_url(plan_version_id, created_via),
        })
    if status == 'failed':
        return jsonify({"status": "failed", "error": outcome['error']})
    # #213 — the pass parked the plan at the Layer 3D HITL gate; send the poller
    # to the review screen.
    if status == 'needs_review':
        return jsonify({
            "status": "needs_review",
            "redirect": url_for(
                'plan_create.plan_review', plan_version_id=plan_version_id
            ),
        })
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
