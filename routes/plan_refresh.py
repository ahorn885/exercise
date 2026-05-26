"""D-64 plan-refresh caller-side route (Phase 5.2 caller-side).

Composes `orchestrate_plan_refresh` end-to-end:
1. GET `/plans/v2/refresh` renders the tier-picker form. If the athlete
   has no prior `plan_versions` row, renders an empty-state CTA pointing
   at `/plans/v2/new` instead — the T1/T2/T3 buttons are hidden until a
   plan exists, since plan-refresh requires a `plan_version_id_parent`.
2. POST `/plans/v2/refresh` allocates a new `plan_versions` row,
   resolves the prior-window via `load_prior_plan_session_window`, runs
   the NL parser (catching `NLParserError` → degraded
   `_default_parsed_intent()` per D-64 §5.4), invokes
   `orchestrate_plan_refresh`, persists the returned sessions, writes
   one `plan_refresh_log` row, and commits atomically per D-64 §6.2.
3. GET `/plans/v2/refresh/<plan_version_id>` renders the post-refresh
   diff view: scope dates + per-session list grouped by date with
   "updated" / "unchanged" / "new" badges computed by comparing each
   session's `payload_json` against the parent version's session in the
   same `(date, session_index_in_day)` slot. Honors D-64 §9 in v1.

Atomicity per D-64 §6.2: commit fires only after parser + orchestrator +
persistence + `plan_refresh_log` INSERT all succeed. On parser error the
route degrades to `_default_parsed_intent()` and continues — a parser
failure does NOT abort the refresh. On orchestrator/`Layer4*Error`,
nothing commits + the auto-rollback keeps the half-allocated row off the
table; a failure-row plan_refresh_log INSERT is written in a fresh
sub-transaction so the failure telemetry still lands.

Frequency caps per D-64 §8 enforced server-side via
`_check_frequency_cap` — counts `success=TRUE` rows in the per-tier
window against `plan_refresh_log`. Over-cap POSTs re-render the form
with an auto-opening Bootstrap modal asking the athlete to confirm;
[Refresh anyway] resubmits with hidden `cap_override=1` and the route
stamps `cap_overridden=TRUE` on the resulting log row. Override is
single-use — each subsequent refresh re-checks the cap independently.

D-63 §5.4 attribution: when the T1 hook anchor lands the athlete here,
the originating `ad_hoc_workout_suggestions.id` rides through as a
URL/form param and is stamped on `plan_refresh_log.triggered_by_ad_hoc_id`.
The ID is validated against the current user at both GET (prefill) and
POST (pre-log) — mismatches silently collapse to NULL since attribution
is best-effort telemetry. Override + failure-path log rows carry the FK
through too: a successful override of the cap and a failed cascade are
both still attributable to the ad-hoc workout that triggered them.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import nl_parser
from database import get_db
from layer4 import (
    Layer4Cache,
    OrchestrationError,
    PostgresCacheBackend,
    orchestrate_plan_refresh,
)
from layer3a.builder import Layer3AOutputError
from layer3b.builder import Layer3BOutputError
from layer4.errors import Layer4InputError, Layer4OutputError
from layer4.plan_refresh import _default_parsed_intent
from nl_parser import IntentParserInput, NLParserError
from plan_sessions_repo import (
    allocate_plan_version_row,
    load_plan_sessions_by_version,
    load_prior_plan_session_window,
    persist_layer4_sessions,
)
from routes.auth import current_user_id


bp = Blueprint("plan_refresh", __name__, url_prefix="/plans/v2/refresh")


VALID_TIERS = ("T1", "T2", "T3")

_TIER_HORIZON_DAYS: dict[str, int] = {"T1": 2, "T2": 7, "T3": 28}
_TIER_CREATED_VIA: dict[str, str] = {
    "T1": "plan_refresh_t1",
    "T2": "plan_refresh_t2",
    "T3": "plan_refresh_t3",
}
_TIER_DEFAULT_LAYERS_RUN: dict[str, tuple[str, ...]] = {
    "T1": ("3A", "3B", "Layer4"),
    "T2": ("3A", "3B", "Layer4"),
    "T3": ("2A", "2B", "2C", "2D", "2E", "3A", "3B", "Layer4"),
}

_NL_TEXT_SOFT_CAP_CHARS = 500

# D-64 §8 — frequency caps. `(count_limit, window_hours)` per tier.
# Soft caps; override allowed via the modal-confirm flow per §4.5.
_TIER_CAP_LIMITS: dict[str, tuple[int, int]] = {
    "T1": (3, 24),
    "T2": (1, 48),
    "T3": (1, 24 * 7),
}


# ─── Helpers ────────────────────────────────────────────────────────────────


def _build_layer4_cache() -> Layer4Cache:
    return Layer4Cache(PostgresCacheBackend(lambda: get_db()))


def _latest_plan_version(db, user_id: int) -> dict | None:
    """Return the athlete's most-recently-created plan_versions row, or
    None when the athlete has never created a plan. Scoped to user_id."""
    row = db.execute(
        "SELECT id, created_at, created_via, scope_start_date, "
        "scope_end_date, pattern "
        "FROM plan_versions WHERE user_id = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "created_at": row["created_at"],
        "created_via": row["created_via"],
        "scope_start_date": row["scope_start_date"],
        "scope_end_date": row["scope_end_date"],
        "pattern": row["pattern"],
    }


def _load_plan_version(db, user_id: int, plan_version_id: int) -> dict | None:
    """Fetch a plan_versions row scoped to user_id."""
    row = db.execute(
        "SELECT id, user_id, created_at, created_via, scope_start_date, "
        "scope_end_date, pattern "
        "FROM plan_versions WHERE id = ? AND user_id = ?",
        (plan_version_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "created_at": row["created_at"],
        "created_via": row["created_via"],
        "scope_start_date": row["scope_start_date"],
        "scope_end_date": row["scope_end_date"],
        "pattern": row["pattern"],
    }


def _athlete_locale_slugs(db, user_id: int) -> tuple[str, ...]:
    rows = db.execute(
        "SELECT locale FROM locale_profiles WHERE user_id = ? ORDER BY locale",
        (user_id,),
    ).fetchall()
    return tuple(r["locale"] for r in rows if r["locale"])


def _athlete_active_injury_summary(db, user_id: int) -> tuple[str, ...]:
    """Render active injuries as human-readable strings for the NL parser
    user prompt: '<body_part> — <description or status>'. Filters on
    status = 'Active' per `injury_log.status` convention."""
    rows = db.execute(
        "SELECT body_part, description, status FROM injury_log "
        "WHERE user_id = ? AND status = 'Active' "
        "ORDER BY id",
        (user_id,),
    ).fetchall()
    summaries: list[str] = []
    for r in rows:
        body_part = (r["body_part"] or "").strip()
        if not body_part:
            continue
        descr = (r["description"] or "").strip()
        if descr:
            summaries.append(f"{body_part} — {descr}")
        else:
            summaries.append(body_part)
    return tuple(summaries)


def _resolve_prefill(args) -> tuple[str, str | None, int | None]:
    """Resolve D-63 §3.5 T1-hook query/form prefill into
    `(nl_context, tier-or-None, triggered_by_ad_hoc_id-or-None)`.
    nl_context is truncated at the soft cap (defensive — textarea
    maxlength bounds visible input identically). Unknown / blank tier
    strings collapse to None. `triggered_by_ad_hoc_id` is int-coerced;
    non-numeric / blank values collapse to None. Ownership validation
    happens separately via `_validate_ad_hoc_id_for_user` (this helper
    stays pure for test isolation)."""
    raw_nl = args.get("nl_context", "") or ""
    nl_context = raw_nl[:_NL_TEXT_SOFT_CAP_CHARS]
    raw_tier = (args.get("tier") or "").strip().upper()
    tier = raw_tier if raw_tier in VALID_TIERS else None
    raw_id = args.get("triggered_by_ad_hoc_id")
    try:
        triggered_by_ad_hoc_id = int(raw_id) if raw_id else None
    except (TypeError, ValueError):
        triggered_by_ad_hoc_id = None
    return nl_context, tier, triggered_by_ad_hoc_id


def _validate_ad_hoc_id_for_user(
    db, user_id: int, ad_hoc_id: int | None
) -> int | None:
    """Per D-63 §5.4 attribution: confirm the ad-hoc suggestion exists
    and belongs to `user_id`. Returns the ID on match, None on miss or
    None input. Mismatches silently collapse — telemetry is best-effort
    and the refresh itself is still legitimate."""
    if ad_hoc_id is None:
        return None
    row = db.execute(
        "SELECT 1 AS ok FROM ad_hoc_workout_suggestions "
        "WHERE id = ? AND user_id = ?",
        (ad_hoc_id, user_id),
    ).fetchone()
    return ad_hoc_id if row is not None else None


def _parse_tier(form) -> tuple[str | None, str | None]:
    """Tier may arrive as `tier=T2` or as one of three named submit
    buttons (`submit_t1`/`submit_t2`/`submit_t3`)."""
    raw = (form.get("tier") or "").strip().upper()
    if raw in VALID_TIERS:
        return raw, None
    for tier in VALID_TIERS:
        if form.get(f"submit_{tier.lower()}") is not None:
            return tier, None
    return None, "Pick a tier (T1 / T2 / T3)."


def _resolve_scope_dates(tier: str, today: date) -> tuple[date, date]:
    """Per D-64 §3: T1 = today + tomorrow; T2 = today + 6; T3 = today + 27."""
    horizon = _TIER_HORIZON_DAYS[tier]
    return today, today + timedelta(days=horizon - 1)


_ORCH_ERROR_MESSAGES = {
    "etl_version_set_undiscoverable": "Platform data is unavailable. Try again shortly.",
    "primary_locale_missing": "Set up your home locale before refreshing your plan.",
    "framework_sport_missing": "Set your primary sport in your profile before refreshing your plan.",
}


def _orchestration_error_message(err: OrchestrationError) -> str:
    return _ORCH_ERROR_MESSAGES.get(
        err.code,
        f"Plan refresh failed ({err.code}). Try again or contact support.",
    )


def _count_recent_refreshes(
    db,
    user_id: int,
    tier: str,
    *,
    window_hours: int,
    now: datetime | None = None,
) -> int:
    """Count `plan_refresh_log` rows for this user+tier with
    `success=TRUE` and `triggered_at >= now - window_hours`. Only
    completed refreshes count toward the cap per D2; failed cascades let
    athletes retry without burning their budget."""
    if now is None:
        now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=window_hours)
    row = db.execute(
        "SELECT COUNT(*) AS n FROM plan_refresh_log "
        "WHERE user_id = ? AND tier = ? AND success = TRUE "
        "AND triggered_at >= ?",
        (user_id, tier, threshold),
    ).fetchone()
    if row is None:
        return 0
    return int(row["n"])


def _check_frequency_cap(
    db, user_id: int, tier: str, *, now: datetime | None = None
) -> tuple[bool, int]:
    """Return `(exceeded, current_count)` for the tier's window. The
    next refresh would land as the `(current_count + 1)`th in-window
    row; exceeded := `current_count >= limit`."""
    limit, window_hours = _TIER_CAP_LIMITS[tier]
    count = _count_recent_refreshes(
        db, user_id, tier, window_hours=window_hours, now=now
    )
    return count >= limit, count


def _run_parser(
    db,
    user_id: int,
    *,
    nl_text: str,
    tier: str,
) -> tuple[Any, bool]:
    """Invoke the parser; on `NLParserError`, substitute the degraded
    default per D-64 §5.4. Returns `(parsed_intent, used_degraded)`."""
    parser_input = IntentParserInput(
        nl_text=nl_text,
        tier=tier,
        athlete_locales=_athlete_locale_slugs(db, user_id),
        athlete_active_injuries=_athlete_active_injury_summary(db, user_id),
    )
    try:
        return nl_parser.parse_intent(parser_input, user_id=user_id), False
    except NLParserError:
        return _default_parsed_intent(), True


def _write_refresh_log(
    db,
    *,
    user_id: int,
    tier: str,
    nl_text: str,
    parsed_intent_json: str | None,
    layers_run: tuple[str, ...],
    scope_start_date: date,
    scope_end_date: date,
    plan_version_id_before: int | None,
    plan_version_id_after: int | None,
    duration_ms: int | None,
    sessions_changed: int | None,
    success: bool,
    failure_reason: str | None,
    cap_overridden: bool = False,
    triggered_by_ad_hoc_id: int | None = None,
) -> None:
    """INSERT one plan_refresh_log row. Caller owns the transaction."""
    db.execute(
        """INSERT INTO plan_refresh_log
               (user_id, tier, nl_text, parsed_intent, layers_run,
                scope_start_date, scope_end_date, plan_version_id_before,
                plan_version_id_after, duration_ms, sessions_changed,
                success, failure_reason, cap_overridden,
                triggered_by_ad_hoc_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            tier,
            nl_text or None,
            parsed_intent_json,
            list(layers_run),
            scope_start_date,
            scope_end_date,
            plan_version_id_before,
            plan_version_id_after,
            duration_ms,
            sessions_changed,
            success,
            failure_reason,
            cap_overridden,
            triggered_by_ad_hoc_id,
        ),
    )


_DIFF_EXCLUDE_FIELDS = {"plan_version_id", "session_id"}
"""Fields excluded from the structural diff because the orchestrator
rebinds them on every refresh — they're identity, not content. A
refreshed session that re-emits the same training content will compare
equal to its parent slot."""


def _diff_signature(session) -> str:
    """Structural-content signature for diffing. Excludes the rebound
    identity fields per `_DIFF_EXCLUDE_FIELDS`."""
    import json

    payload = session.model_dump(mode="json", exclude=_DIFF_EXCLUDE_FIELDS)
    return json.dumps(payload, sort_keys=True)


def _diff_sessions_against_parent(
    new_sessions: list,
    parent_sessions: list,
) -> tuple[dict[tuple, str], int]:
    """Per-slot diff resolver for D-64 §9 diff visibility. Returns a
    `(date, session_index_in_day) -> 'updated' | 'unchanged' | 'new'`
    map + the count of slots that changed (updated + new).

    Compare keys: structural signature excluding `plan_version_id` +
    `session_id` (rebound on every refresh). Any other payload-field
    difference (intensity, blocks, notes, etc.) flips the slot to
    'updated'. Slots present in `new_sessions` but absent from
    `parent_sessions` are 'new' (the refresh extended the window).
    """
    parent_by_slot = {
        (s.date, s.session_index_in_day): _diff_signature(s)
        for s in parent_sessions
    }
    badges: dict[tuple, str] = {}
    changed = 0
    for s in new_sessions:
        slot = (s.date, s.session_index_in_day)
        parent_sig = parent_by_slot.get(slot)
        new_sig = _diff_signature(s)
        if parent_sig is None:
            badges[slot] = "new"
            changed += 1
        elif parent_sig != new_sig:
            badges[slot] = "updated"
            changed += 1
        else:
            badges[slot] = "unchanged"
    return badges, changed


# ─── Routes ─────────────────────────────────────────────────────────────────


@bp.route("", methods=["GET", "POST"])
def refresh():
    """GET: render tier-picker form (empty state when no prior plan).
    POST: parse tier + nl_text → allocate plan_versions row → run parser
    (degraded fallback on error) → orchestrate → persist → log → commit."""
    db = get_db()
    uid = current_user_id()

    parent_plan = _latest_plan_version(db, uid)

    if request.method == "GET":
        # D-63 §3.5 post-log T1 hook auto-fills nl_context + selects
        # tier=T1 via query params on the redirect from the suggestion
        # modal's [Yes — refresh] anchor. The T1 hook also carries
        # `triggered_by_ad_hoc_id` per D-63 §5.4 attribution; ownership
        # is checked here so a cross-user / stale URL collapses to None
        # before reaching the hidden form field.
        prefill_nl_context, prefill_tier, raw_prefill_ad_hoc_id = (
            _resolve_prefill(request.args)
        )
        prefill_triggered_by_ad_hoc_id = _validate_ad_hoc_id_for_user(
            db, uid, raw_prefill_ad_hoc_id
        )
        return render_template(
            "plans/v2/refresh.html",
            parent_plan=parent_plan,
            nl_text_cap=_NL_TEXT_SOFT_CAP_CHARS,
            prefill_nl_context=prefill_nl_context,
            prefill_tier=prefill_tier,
            prefill_triggered_by_ad_hoc_id=prefill_triggered_by_ad_hoc_id,
        )

    if parent_plan is None:
        flash(
            "Create a plan before refreshing — refresh requires a parent plan version.",
            "danger",
        )
        return redirect(url_for("plan_create.new_plan"))

    tier, err = _parse_tier(request.form)
    if err is not None or tier is None:
        flash(err or "Invalid input.", "danger")
        return redirect(url_for("plan_refresh.refresh"))

    nl_text = (request.form.get("nl_context") or "").strip()
    cap_override = request.form.get("cap_override") == "1"

    # D-63 §5.4 attribution — the ad-hoc-suggestion FK rides through
    # as a hidden form field on both the main form + the cap-exceeded
    # mini-form. Int-coerced + validated against the current user;
    # tampering / staleness silently collapses to None.
    raw_form_ad_hoc_id = request.form.get("triggered_by_ad_hoc_id")
    try:
        parsed_form_ad_hoc_id: int | None = (
            int(raw_form_ad_hoc_id) if raw_form_ad_hoc_id else None
        )
    except (TypeError, ValueError):
        parsed_form_ad_hoc_id = None
    triggered_by_ad_hoc_id = _validate_ad_hoc_id_for_user(
        db, uid, parsed_form_ad_hoc_id
    )

    # D-64 §8 — frequency cap. Soft cap; over-cap submissions without
    # an explicit override re-render the form with an auto-opening
    # modal-confirm. Override is single-use per D3.
    cap_exceeded_now, current_count = _check_frequency_cap(db, uid, tier)
    if cap_exceeded_now and not cap_override:
        _, window_hours = _TIER_CAP_LIMITS[tier]
        return render_template(
            "plans/v2/refresh.html",
            parent_plan=parent_plan,
            nl_text_cap=_NL_TEXT_SOFT_CAP_CHARS,
            prefill_nl_context=nl_text,
            prefill_tier=tier,
            prefill_triggered_by_ad_hoc_id=triggered_by_ad_hoc_id,
            cap_exceeded={
                "tier": tier,
                "count": current_count,
                "window_hours": window_hours,
            },
        )
    cap_overridden = cap_exceeded_now and cap_override

    today = date.today()
    scope_start_date, scope_end_date = _resolve_scope_dates(tier, today)

    parsed_intent, used_degraded = _run_parser(
        db, uid, nl_text=nl_text, tier=tier
    )

    parent_id: int = parent_plan["id"]
    layers_run = _TIER_DEFAULT_LAYERS_RUN[tier]

    new_plan_version_id = allocate_plan_version_row(
        db,
        uid,
        created_via=_TIER_CREATED_VIA[tier],
        scope_start_date=scope_start_date,
        scope_end_date=scope_end_date,
        pattern="B",
        notes=None,
    )

    started = time.monotonic()
    try:
        prior_window = load_prior_plan_session_window(
            db, uid, today=today, tier=tier
        )
        result = orchestrate_plan_refresh(
            db,
            uid,
            tier=tier,  # type: ignore[arg-type]
            refresh_scope_start=scope_start_date,
            refresh_scope_end=scope_end_date,
            plan_version_id=new_plan_version_id,
            plan_version_id_parent=parent_id,
            prior_plan_session_window=prior_window,
            cache=_build_layer4_cache(),
            parsed_intent=parsed_intent,
            today=today,
        )
    except OrchestrationError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        db.rollback()
        _write_refresh_log(
            db,
            user_id=uid,
            tier=tier,
            nl_text=nl_text,
            parsed_intent_json=parsed_intent.model_dump_json(),
            layers_run=layers_run,
            scope_start_date=scope_start_date,
            scope_end_date=scope_end_date,
            plan_version_id_before=parent_id,
            plan_version_id_after=None,
            duration_ms=duration_ms,
            sessions_changed=None,
            success=False,
            failure_reason=f"orchestration:{exc.code}",
            triggered_by_ad_hoc_id=triggered_by_ad_hoc_id,
        )
        db.commit()
        flash(_orchestration_error_message(exc), "danger")
        return redirect(url_for("plan_refresh.refresh"))
    except (
        Layer3AOutputError,
        Layer3BOutputError,
        Layer4InputError,
        Layer4OutputError,
    ) as exc:
        # 3A/3B run upstream of Layer 4 in the same cone, so a Layer3*OutputError
        # (e.g. a `schema_violation` from the synthesizer) reaches here too;
        # without this catch it bubbles as an unhandled 500.
        duration_ms = int((time.monotonic() - started) * 1000)
        db.rollback()
        layer_tag = (
            "layer3"
            if isinstance(exc, (Layer3AOutputError, Layer3BOutputError))
            else "layer4"
        )
        _write_refresh_log(
            db,
            user_id=uid,
            tier=tier,
            nl_text=nl_text,
            parsed_intent_json=parsed_intent.model_dump_json(),
            layers_run=layers_run,
            scope_start_date=scope_start_date,
            scope_end_date=scope_end_date,
            plan_version_id_before=parent_id,
            plan_version_id_after=None,
            duration_ms=duration_ms,
            sessions_changed=None,
            success=False,
            failure_reason=f"{layer_tag}:{exc.code}",
            triggered_by_ad_hoc_id=triggered_by_ad_hoc_id,
        )
        db.commit()
        flash(
            f"Plan refresh failed ({exc.code}). Adjust your inputs and try again.",
            "danger",
        )
        return redirect(url_for("plan_refresh.refresh"))

    duration_ms = int((time.monotonic() - started) * 1000)
    persist_layer4_sessions(db, result)

    parent_sessions = load_plan_sessions_by_version(db, parent_id)
    _, sessions_changed = _diff_sessions_against_parent(
        result.sessions, parent_sessions
    )

    _write_refresh_log(
        db,
        user_id=uid,
        tier=tier,
        nl_text=nl_text,
        parsed_intent_json=parsed_intent.model_dump_json(),
        layers_run=layers_run,
        scope_start_date=scope_start_date,
        scope_end_date=scope_end_date,
        plan_version_id_before=parent_id,
        plan_version_id_after=new_plan_version_id,
        duration_ms=duration_ms,
        sessions_changed=sessions_changed,
        success=True,
        failure_reason="parser_degraded" if used_degraded else None,
        cap_overridden=cap_overridden,
        triggered_by_ad_hoc_id=triggered_by_ad_hoc_id,
    )
    db.commit()

    if used_degraded:
        flash(
            "NL parser unavailable — refresh ran on the default cascade only.",
            "warning",
        )
    return redirect(
        url_for(
            "plan_refresh.view_refresh", plan_version_id=new_plan_version_id
        )
    )


@bp.route("/<int:plan_version_id>", methods=["GET"])
def view_refresh(plan_version_id: int):
    """Render the post-refresh diff view: scope dates + sessions grouped
    by date with 'updated' / 'unchanged' / 'new' badges. 404 + cross-user-
    defense via the user_id filter on `_load_plan_version`."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)

    new_sessions = load_plan_sessions_by_version(db, plan_version_id)

    parent_id = _latest_parent_for_refresh(db, uid, plan_version_id)
    parent_sessions = (
        load_plan_sessions_by_version(db, parent_id) if parent_id is not None else []
    )

    badges, sessions_changed = _diff_sessions_against_parent(
        new_sessions, parent_sessions
    )

    sessions_by_date: dict = {}
    for s in new_sessions:
        sessions_by_date.setdefault(s.date, []).append(
            {
                "session": s,
                "badge": badges.get((s.date, s.session_index_in_day), "unchanged"),
            }
        )

    return render_template(
        "plans/v2/refresh_view.html",
        plan_version=plan_version,
        sessions_by_date=sorted(sessions_by_date.items()),
        session_count=len(new_sessions),
        sessions_changed=sessions_changed,
        parent_plan_version_id=parent_id,
    )


def _latest_parent_for_refresh(
    db, user_id: int, plan_version_id: int
) -> int | None:
    """Resolve the parent plan_version_id from the most recent
    `plan_refresh_log` row pointing AT this plan_version_id. Falls back
    to the immediately-prior plan_versions row for this user when the
    log row is absent (defensive: pre-telemetry refreshes or test
    fixtures that bypass the log INSERT)."""
    row = db.execute(
        "SELECT plan_version_id_before FROM plan_refresh_log "
        "WHERE user_id = ? AND plan_version_id_after = ? "
        "ORDER BY id DESC LIMIT 1",
        (user_id, plan_version_id),
    ).fetchone()
    if row is not None and row["plan_version_id_before"] is not None:
        return int(row["plan_version_id_before"])

    fallback = db.execute(
        "SELECT id FROM plan_versions "
        "WHERE user_id = ? AND id < ? "
        "ORDER BY id DESC LIMIT 1",
        (user_id, plan_version_id),
    ).fetchone()
    if fallback is None:
        return None
    return int(fallback["id"])
