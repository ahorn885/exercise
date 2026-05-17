"""Canonical-JSON + SHA-256 cache-key helpers per `Layer4_Spec.md` §9.1.

Pure-function module — no I/O, no state. All hashes are SHA-256 hex digests
of canonical-JSON (sorted keys, stable serialization for dates/Decimals/sets);
all cache keys are SHA-256 of the listed components concatenated with `||`
per the spec formulas.

Per-call rebinding (§9.4): `plan_version_id` and `suggestion_id` are allocated
per call by the orchestrator and intentionally NOT in any cache key — a cache
hit returns the cached payload with those fields overwritten to the new
allocated values. None of the helpers below accept them.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from layer4.payload import PlanSession


_LAYER2_BUNDLE_ATTRS = frozenset({"a", "b", "c", "d", "e"})


def _to_jsonable(obj: Any) -> Any:
    """Recursive conversion to JSON-safe types with stable serialization.

    - pydantic BaseModel  → model_dump(mode='json') (recurse)
    - dict                → recurse values; json.dumps sorts keys
    - list / tuple        → list of converted items
    - set / frozenset     → sorted list (elements must be comparable)
    - datetime / date     → ISO 8601 string
    - Decimal             → str(value)
    - other scalars       → passthrough
    """
    if isinstance(obj, BaseModel):
        return _to_jsonable(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_to_jsonable(x) for x in obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    return obj


def canonical_json(obj: Any) -> str:
    """SHA-256-stable JSON encoding: sorted keys, no whitespace, ISO dates."""
    return json.dumps(
        _to_jsonable(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compute_payload_hash(payload: Any) -> str:
    """SHA-256 hex of canonical-JSON of a typed payload (typically a pydantic model).

    Building block for the per-layer hashes (`layer1_hash`, `layer2a_hash`,
    etc.) that the orchestrator pre-computes and passes into the cache-key
    helpers below.
    """
    return _sha256_hex(canonical_json(payload))


def compute_layer2c_bundle_hash(locale_to_hash: dict[str, str]) -> str:
    """Per §9.1 — SHA-256 of canonical-JSON of {locale_id: layer2c_hash}, sorted by locale_id.

    Used by both `plan_create_key` and `race_week_brief_key` to fold a
    user's per-locale Layer 2C hashes into a single bundle hash component.
    """
    return _sha256_hex(canonical_json(locale_to_hash))


def compute_layer2_bundle_canonical_hash(layer2_hashes: dict[str, str | None]) -> str:
    """Per §9.1 `plan_refresh` — SHA-256 of canonical-JSON of {attr: layer2x_hash or None}.

    Keys MUST be exactly {'a', 'b', 'c', 'd', 'e'}; null entries preserved
    so the cache differentiates 'T1 cascade with 2A re-run' from 'T1 cascade
    with no Layer 2 re-run'.
    """
    if set(layer2_hashes.keys()) != _LAYER2_BUNDLE_ATTRS:
        raise ValueError(
            f"layer2_hashes must have keys exactly {sorted(_LAYER2_BUNDLE_ATTRS)}; "
            f"got {sorted(layer2_hashes.keys())}"
        )
    return _sha256_hex(canonical_json(layer2_hashes))


def compute_prior_plan_session_window_hash(sessions: list[PlanSession]) -> str:
    """Per §9.1 — SHA-256 of canonical-JSON of PlanSession list sorted by (date, session_index_in_day).

    The ±7-day context window per §3.2 IS included in the hashed set; the
    orchestrator should pass the full window (not the refresh scope only).
    """
    sorted_sessions = sorted(
        sessions, key=lambda s: (s.date, s.session_index_in_day, s.plan_version_id)
    )
    return _sha256_hex(canonical_json(sorted_sessions))


def plan_create_key(
    *,
    user_id: int,
    layer1_hash: str,
    layer2a_hash: str,
    layer2b_hash: str,
    layer2c_bundle_hash: str,
    layer2d_hash: str,
    layer2e_hash: str,
    layer3a_hash: str,
    layer3b_hash: str,
    plan_start_date: date,
    etl_version_set: dict[str, str],
    model_synthesizer: str,
    model_seam_reviewer: str,
    temperature: float,
    max_tokens_per_phase: int,
    capped_retries_per_phase: int,
) -> str:
    """Per §9.1 — cache key for `llm_layer4_plan_create`.

    `plan_version_id` is intentionally absent (allocated per call; rebinding
    on hit per §9.4). `layer2c_bundle_hash` is the bundle hash from
    `compute_layer2c_bundle_hash`.
    """
    components = [
        str(user_id),
        layer1_hash,
        layer2a_hash,
        layer2b_hash,
        layer2c_bundle_hash,
        layer2d_hash,
        layer2e_hash,
        layer3a_hash,
        layer3b_hash,
        plan_start_date.isoformat(),
        canonical_json(etl_version_set),
        model_synthesizer,
        model_seam_reviewer,
        str(temperature),
        str(max_tokens_per_phase),
        str(capped_retries_per_phase),
    ]
    return _sha256_hex("||".join(components))


def plan_refresh_key(
    *,
    user_id: int,
    tier: str,
    refresh_scope_start: date,
    refresh_scope_end: date,
    layer1_hash: str,
    layer2_bundle_canonical_hash: str,
    layer3a_hash: str,
    layer3b_hash: str,
    prior_plan_session_window_hash: str,
    parsed_intent_hash: str | None,
    etl_version_set: dict[str, str],
    model_synthesizer: str,
    model_seam_reviewer: str | None,
    temperature: float,
    max_tokens: int,
    capped_retries: int,
) -> str:
    """Per §9.1 — cache key for `llm_layer4_plan_refresh`.

    `model_seam_reviewer` MUST be None for Pattern B refreshes (T1, T2, T3
    intra-phase); only T3 cross-phase routes to Pattern A and contributes
    the seam-reviewer model to the key. None → '' in the key to prevent
    gratuitous cache misses on the model field for Pattern B refreshes.
    """
    components = [
        str(user_id),
        tier,
        refresh_scope_start.isoformat(),
        refresh_scope_end.isoformat(),
        layer1_hash,
        layer2_bundle_canonical_hash,
        layer3a_hash,
        layer3b_hash,
        prior_plan_session_window_hash,
        parsed_intent_hash or "",
        canonical_json(etl_version_set),
        model_synthesizer,
        model_seam_reviewer or "",
        str(temperature),
        str(max_tokens),
        str(capped_retries),
    ]
    return _sha256_hex("||".join(components))


def single_session_synthesize_key(
    *,
    user_id: int,
    request: Any,
    layer1_hash: str,
    layer2c_locale_hash: str | None,
    layer2d_hash: str,
    layer3a_hash: str,
    etl_version_set: dict[str, str],
    model: str,
    temperature: float,
    max_tokens: int,
    capped_retries: int,
) -> str:
    """Per §9.1 — cache key for `llm_layer4_single_session_synthesize`.

    `request` is the `SingleSessionRequest` shape per D-63 §4.3; passed
    through `canonical_json` so dicts / pydantic models / dataclasses all
    encode stably. `suggestion_id` is intentionally absent — rebinding
    on hit per §9.4.
    """
    components = [
        str(user_id),
        canonical_json(request),
        layer1_hash,
        layer2c_locale_hash or "",
        layer2d_hash,
        layer3a_hash,
        canonical_json(etl_version_set),
        model,
        str(temperature),
        str(max_tokens),
        str(capped_retries),
    ]
    return _sha256_hex("||".join(components))


def race_week_brief_key(
    *,
    user_id: int,
    layer1_hash: str,
    layer2a_hash: str,
    layer2b_hash: str,
    layer2c_bundle_hash: str,
    layer2d_hash: str,
    layer2e_hash: str,
    layer3a_hash: str,
    layer3b_hash: str,
    prior_plan_session_window_hash: str,
    etl_version_set: dict[str, str],
    model: str,
    temperature: float,
    max_tokens: int,
    capped_retries: int,
) -> str:
    """Per §9.1 — cache key for `llm_layer4_race_week_brief`.

    `today()` is intentionally absent — `days_to_event` shifts daily so the
    orchestrator invalidates `race_week_brief` caches at midnight UTC (per
    §9.3) rather than baking today's date into the key.
    """
    components = [
        str(user_id),
        layer1_hash,
        layer2a_hash,
        layer2b_hash,
        layer2c_bundle_hash,
        layer2d_hash,
        layer2e_hash,
        layer3a_hash,
        layer3b_hash,
        prior_plan_session_window_hash,
        canonical_json(etl_version_set),
        model,
        str(temperature),
        str(max_tokens),
        str(capped_retries),
    ]
    return _sha256_hex("||".join(components))
