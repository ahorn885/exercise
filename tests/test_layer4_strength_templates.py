"""#335 Phase 2 §B — strength two-template restructure.

Covers the shared strength-composition guidance (programmed vs failover) being
the single source of truth wired into every strength-authoring prompt
(`per_phase`, `plan_refresh_t1`, `plan_refresh_t2`), and the cache-key prompt
revision bump that forces cached plans to re-synthesize on a prompt-only change.
"""

from __future__ import annotations

from datetime import date

import layer4.hashing as hashing
from layer4.hashing import plan_create_key, plan_refresh_key
from layer4.strength_guidance import STRENGTH_PROGRAMMING_GUIDANCE
from layer4.per_phase import SYSTEM_PROMPT as PER_PHASE_SYSTEM_PROMPT
from layer4.plan_refresh_t1 import SYSTEM_PROMPT as T1_SYSTEM_PROMPT
from layer4.plan_refresh_t2 import SYSTEM_PROMPT as T2_SYSTEM_PROMPT
from layer4.plan_refresh_t3 import SYSTEM_PROMPT as T3_SYSTEM_PROMPT


# ─── Shared guidance content ────────────────────────────────────────────────


def test_guidance_carries_both_templates():
    g = STRENGTH_PROGRAMMING_GUIDANCE
    # Two distinct templates with a clear trigger seam.
    assert "PROGRAMMED STRENGTH" in g
    assert "FAILOVER STRENGTH" in g
    assert "[TERRAIN-INFEASIBLE]" in g and "[NO CRAFT]" in g


def test_guidance_programmed_dose_and_layers():
    g = STRENGTH_PROGRAMMING_GUIDANCE
    # Frequency cap (advisory) stated in-prompt; layered session structure present.
    assert "never more than 3" in g
    assert "2 programmed sessions/week in Base/Build, 1/week in Peak/Taper" in g
    assert "Heavy core" in g
    assert "Durability layer" in g
    assert "plyometric" in g
    assert "carry" in g.lower()


def test_guidance_failover_is_muscular_endurance_and_uncapped():
    g = STRENGTH_PROGRAMMING_GUIDANCE
    # Failover must REPLACE aerobic work (not add a heavy day) and is exempt
    # from the programmed dose so it can never be starved by the cap.
    assert "muscular endurance" in g.lower()
    assert "Keep the missing session's target hours" in g
    assert "do NOT count toward the programmed" in g


def test_guidance_instructs_strength_substitution_marker():
    # #573 — the failover template must tell the synthesizer to flag the
    # session so the validator can exclude it from the programmed-dose count.
    g = STRENGTH_PROGRAMMING_GUIDANCE
    assert "strength_substitution: true" in g
    assert "PROGRAMMED session" in g


# ─── Fan-out: every strength-authoring prompt embeds the shared guidance ─────


def test_per_phase_prompt_embeds_shared_guidance():
    assert STRENGTH_PROGRAMMING_GUIDANCE in PER_PHASE_SYSTEM_PROMPT


def test_all_three_refresh_prompts_embed_shared_guidance():
    # #573 — the fan-out requirement: all three refresh tiers must carry the
    # same strength logic as plan-gen, not drift to their own (older,
    # shallower, or in T3's case entirely absent) instructions.
    assert STRENGTH_PROGRAMMING_GUIDANCE in T1_SYSTEM_PROMPT
    assert STRENGTH_PROGRAMMING_GUIDANCE in T2_SYSTEM_PROMPT
    assert STRENGTH_PROGRAMMING_GUIDANCE in T3_SYSTEM_PROMPT


def test_old_shallow_structure_line_is_gone():
    # The superseded "3–5 ... 2–3 sets, 4–10 rep range" single-template line must
    # not linger in the per-phase prompt alongside the new layered guidance.
    assert "3–5 multi-joint, lower-body-biased exercises, 2–3 sets" not in (
        PER_PHASE_SYSTEM_PROMPT
    )


# ─── Cache-key prompt-revision bump ─────────────────────────────────────────


def _create_key_kwargs():
    return dict(
        user_id=1,
        layer1_hash="l1",
        layer2a_hash="l2a",
        layer2b_hash="l2b",
        layer2c_bundle_hash="l2c",
        layer2d_hash="l2d",
        layer2e_hash="l2e",
        layer3a_hash="l3a",
        layer3b_hash="l3b",
        plan_start_date=date(2026, 4, 1),
        etl_version_set={"layer4": "1"},
        model_synthesizer="claude-x",
        model_seam_reviewer="claude-y",
        temperature=0.2,
        max_tokens_per_phase=8000,
        capped_retries_per_phase=2,
    )


def _refresh_key_kwargs():
    return dict(
        user_id=1,
        tier="T1",
        refresh_scope_start=date(2026, 4, 1),
        refresh_scope_end=date(2026, 4, 2),
        layer1_hash="l1",
        layer2_bundle_canonical_hash="l2",
        layer3a_hash="l3a",
        layer3b_hash="l3b",
        prior_plan_session_window_hash="w",
        parsed_intent_hash="pi",
        etl_version_set={"layer4": "1"},
        model_synthesizer="claude-x",
        model_seam_reviewer=None,
        temperature=0.2,
        max_tokens=2000,
        capped_retries=1,
    )


def test_prompt_revision_changes_create_key(monkeypatch):
    before = plan_create_key(**_create_key_kwargs())
    monkeypatch.setattr(hashing, "LAYER4_PROMPT_REVISION", "999")
    after = plan_create_key(**_create_key_kwargs())
    assert before != after


def test_prompt_revision_changes_refresh_key(monkeypatch):
    before = plan_refresh_key(**_refresh_key_kwargs())
    monkeypatch.setattr(hashing, "LAYER4_PROMPT_REVISION", "999")
    after = plan_refresh_key(**_refresh_key_kwargs())
    assert before != after
