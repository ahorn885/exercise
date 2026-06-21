"""Tests for the #826 Layer 3 LLM-cited evidence-source channel.

Covers the contract surface added to Layer 3A / 3B: the `source_citations`
top-level field in the tool schemas + Pydantic payloads, the shared prompt
catalog block, and the optional `Layer4Payload` carrier. The persistence side
(validate-link-or-flag) lives in `test_evidence_repo.py`; the orchestrator
threading in `test_layer4_orchestrator.py`.
"""

from __future__ import annotations

# Import the layer4 package first: layer3a/layer3b builders and layer4.context
# form a pre-existing circular import that only resolves cleanly when layer4 is
# fully loaded first (see the same ordering in the full-suite run). Without this
# the builders' top-level import would fail when this module is collected early.
import layer4  # noqa: F401  (import-order guard)

import evidence_catalog
from layer3a.builder import build_record_athlete_state_tool
from layer3b.builder import build_emit_layer3b_payload_tool


def test_layer3b_tool_schema_exposes_source_citations():
    schema = build_emit_layer3b_payload_tool()
    props = schema["input_schema"]["properties"]
    assert "source_citations" in props
    assert props["source_citations"]["items"]["type"] == "string"
    # Optional — not forced, so the model may omit when nothing applies.
    assert "source_citations" not in schema["input_schema"]["required"]


def test_layer3a_tool_schema_exposes_source_citations():
    schema = build_record_athlete_state_tool()
    props = schema["input_schema"]["properties"]
    assert "source_citations" in props
    assert props["source_citations"]["items"]["type"] == "string"
    assert "source_citations" not in schema["input_schema"]["required"]


def test_catalog_block_lists_every_slug_and_instructs():
    block = evidence_catalog.render_catalog_block()
    for slug in evidence_catalog.all_slugs():
        assert slug in block, f"catalog block missing slug {slug!r}"
    # The model must be told to cite ONLY catalog slugs (constrained-citation).
    assert "source_citations" in block
    assert "never invent" in block.lower()


def test_layer3a_payload_defaults_source_citations_empty():
    # The driver merges tool_args (which may omit source_citations) — the
    # default must be an empty list so omission hydrates cleanly.
    from tests.test_layer4_orchestrator import _fake_layer3a_payload

    p = _fake_layer3a_payload()
    assert p.source_citations == []
    p2 = p.model_copy(update={"source_citations": ["zone2-aerobic-base"]})
    # Survives the cache round-trip (model_dump_json → model_validate_json).
    from layer4.context import Layer3APayload

    assert Layer3APayload.model_validate_json(
        p2.model_dump_json()
    ).source_citations == ["zone2-aerobic-base"]


def test_layer3b_payload_defaults_source_citations_empty():
    from tests.test_layer4_orchestrator import _fake_layer3b_payload

    p = _fake_layer3b_payload()
    assert p.source_citations == []


def test_layer4_payload_evidence_citations_optional():
    from tests.test_layer4_orchestrator import _fake_plan_create_layer4_payload

    p = _fake_plan_create_layer4_payload()
    assert p.evidence_source_citations is None  # absent by default
