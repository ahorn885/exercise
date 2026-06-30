"""Unit tests for the Layer 3D gate staleness fingerprint (#213, Reading B).

`compute_gate_input_fingerprint` hashes the deterministic LEAF inputs that feed
the gate — athlete profile, target race, equipment/terrain, the incoming
training-data bundle, the platform-data version, and the 3A/3B prompt revision —
so a plan parked at the HITL review screen can be re-checked WITHOUT re-running
the LLM stages 3A/3B. These tests stub the leaf loaders to prove the digest is
stable for unchanged inputs and moves for any single changed leaf.

Pure-function test against stubbed loaders — no DB, no LLM (same $0 / side-effect
-free contract as the other layer4 unit suites).
"""

from __future__ import annotations

from datetime import date

import layer4.orchestrator as orch


_PSD = date(2026, 6, 1)
_TODAY = date(2026, 6, 1)


def _patch_leaves(monkeypatch, *, profile, training, etl=None, terrain=None,
                  equipment=None, windows=None):
    monkeypatch.setattr(orch, "build_layer1_payload", lambda db, uid: profile)
    monkeypatch.setattr(
        orch, "assemble_layer3a_integration_bundle", lambda db, uid, as_of: training
    )
    monkeypatch.setattr(orch, "load_event_windows", lambda db, uid: windows or [])
    monkeypatch.setattr(
        orch, "_q_current_etl_version_set", lambda db: etl or {"0A": "v1"}
    )
    monkeypatch.setattr(orch, "_q_primary_locale", lambda db, uid: "home")
    monkeypatch.setattr(
        orch, "_q_locale_terrain_ids", lambda db, uid, loc: terrain or ["t1"]
    )
    monkeypatch.setattr(orch.locations, "cluster_locale_ids", lambda db, uid: ["home"])
    monkeypatch.setattr(
        orch.locations, "locale_effective_tags",
        lambda db, uid, loc, **kw: equipment or {"e1"}
    )


def _fp(target_race_event=None):
    return orch.compute_gate_input_fingerprint(
        None, 3, target_race_event=target_race_event,
        plan_start_date=_PSD, today=_TODAY,
    )


class TestGateInputFingerprint:
    def test_stable_for_identical_inputs(self, monkeypatch):
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 1})
        digest = _fp()
        assert _fp() == digest
        assert isinstance(digest, str) and len(digest) == 64  # sha256 hex

    def test_changes_when_profile_changes(self, monkeypatch):
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 1})
        before = _fp()
        _patch_leaves(monkeypatch, profile={"a": 2}, training={"w": 1})
        assert _fp() != before

    def test_changes_when_training_data_changes(self, monkeypatch):
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 1})
        before = _fp()
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 2})
        assert _fp() != before

    def test_changes_when_equipment_changes(self, monkeypatch):
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 1}, equipment={"e1"})
        before = _fp()
        _patch_leaves(
            monkeypatch, profile={"a": 1}, training={"w": 1}, equipment={"e1", "e2"}
        )
        assert _fp() != before

    def test_changes_when_etl_version_changes(self, monkeypatch):
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 1}, etl={"0A": "v1"})
        before = _fp()
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 1}, etl={"0A": "v2"})
        assert _fp() != before

    def test_changes_when_target_race_changes(self, monkeypatch):
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 1})
        no_race = _fp(target_race_event=None)
        with_race = _fp(target_race_event={"race_event_id": 9})
        assert no_race != with_race

    def test_changes_when_prompt_revision_bumps(self, monkeypatch):
        _patch_leaves(monkeypatch, profile={"a": 1}, training={"w": 1})
        before = _fp()
        monkeypatch.setattr(orch, "LAYER3_GATE_PROMPT_REVISION", "999")
        assert _fp() != before
