"""Event Windows Slice 1 (#581 WS-H) — subtractive home windows.

Covers spec §9 scenarios at the unit level: no-windows byte-identical cache key
(regression), `indoor_only` + `locale_unavailable` routing against the reduced
environment, the cascade fallback "not always a downgrade", the changed-only /
no-op-dropped segment filter, the date-scoped synthesis overlay render, the
declared-window hash, and the repo's app-layer validation.

The resolution model is the EXISTING cascade run against a reduced environment
(Andy 2026-06-14), so these tests construct a `_FeasibilityInputs` by hand and
exercise `_reduced_env` + `_resolve_included_feasibility` directly — no DB / LLM.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from athlete_event_windows_repo import (
    EventWindow,
    EventWindowError,
    add_event_window,
    delete_event_window,
    load_event_window,
    load_event_windows,
    update_event_window_restrictions_by_date,
    update_event_window_volume_by_date,
)
from layer4.context import (
    Layer2ADiscipline,
    Layer2APayload,
    PhaseLoadBands,
    RationaleMetadata,
    TrainingGapsSummary,
    WeightResult,
)
from layer4.hashing import (
    compute_event_windows_hash,
    plan_create_key,
    plan_refresh_key,
)
from layer4.orchestrator import (
    _FeasibilityInputs,
    _build_event_window_overlay,
    _extract_pool_by_discipline,
    _reduced_env,
    _resolve_included_feasibility,
)
from layer4.payload import PhaseSpec, PhaseStructure, SynthesisMetadata
from layer4.per_phase import (
    _format_event_window_overlay,
    _format_session_grid,
    _week_volume_capacity,
)
from layer4.session_feasibility import (
    EventWindowOverride,
    EventWindowSegment,
    TerrainResolution,
    segment_window_boundaries,
)


# ─── test doubles ────────────────────────────────────────────────────────────

class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[list] = []

    def queue_response(self, rows=None):
        self.responses.append(rows or [])

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        rows = self.responses.pop(0) if self.responses else []
        return _FakeCursor(rows)


def _mk_inputs(
    *,
    cluster,
    terrain_by_locale,
    equip_by_locale,
    disciplines,
    pool_by_discipline=None,
):
    """Build a `_FeasibilityInputs` with empty craft maps (so every discipline
    walks the terrain-only cascade — no DB needed)."""
    return _FeasibilityInputs(
        cluster=list(cluster),
        terrain_by_locale={k: set(v) for k, v in terrain_by_locale.items()},
        equip_by_locale={k: set(v) for k, v in equip_by_locale.items()},
        gap_rules={},
        owned_crafts=[],
        craft_disciplines={},
        craft_kind={},
        craft_terrain={},
        discipline_groups={},
        discipline_gear_kind={},
        craft_fidelity_rank={},
        pool_by_discipline=pool_by_discipline or {},
        gated={},
        included=[SimpleNamespace(discipline_id=d) for d in disciplines],
        name_by_discipline={d: d for d in disciplines},
        locale_meta={loc: {"name": loc, "distance_km": None} for loc in cluster},
        terrain_names={},
        terrain_attrs={},
    )


def _fake_l2c(pool_by_discipline=None, toggle_flags=None):
    """A minimal stand-in for a `Layer2CPayload` for the away-overlay tests. The
    away 2C re-resolve reads `.exercises_resolved[*].{tier,discipline_ids,
    exercise_id,priority_per_discipline}` (the strength pool, #884 slice 6 PR-1)
    and `.coaching_flags[*].{flag_type,discipline_name,discipline_id,metadata}`
    (the away toggle-off flags, PR-2). `pool_by_discipline` → one tier-1 High
    exercise per (discipline, exercise_id); `toggle_flags` → a list of
    (discipline_name, gear_label) rendered as `toggle_off_for_discipline` flags."""
    exs = [
        SimpleNamespace(
            tier=1, discipline_ids=[d_id], exercise_id=ex_id,
            priority_per_discipline={d_id: "High"},
        )
        for d_id, ex_ids in (pool_by_discipline or {}).items()
        for ex_id in ex_ids
    ]
    flags = [
        SimpleNamespace(
            flag_type="toggle_off_for_discipline", discipline_name=disc,
            discipline_id=disc, metadata={"toggle_name": gear},
        )
        for disc, gear in (toggle_flags or [])
    ]
    return SimpleNamespace(exercises_resolved=exs, coaching_flags=flags)


def _fake_cone():
    """A `_UpstreamFullCone` stand-in carrying only the fields the away-branch 2C
    re-resolve reads (the build itself is stubbed via `_fake_l2c`, so the values
    are placeholders that just need to exist)."""
    return SimpleNamespace(
        layer2d_payload=None,
        etl_version_set={},
        layer1_payload=SimpleNamespace(
            lifestyle=SimpleNamespace(skill_toggle_states={})
        ),
    )


# ─── segment_window_boundaries (pure date logic) ─────────────────────────────

class TestSegmentBoundaries:
    def test_single_window_one_segment(self):
        ov = EventWindowOverride("indoor_only")
        segs = segment_window_boundaries(
            date(2026, 6, 1), date(2026, 6, 30),
            [(date(2026, 6, 10), date(2026, 6, 12), ov)],
        )
        assert segs == [(date(2026, 6, 10), date(2026, 6, 12), (ov,))]

    def test_window_clamped_to_plan_span(self):
        ov = EventWindowOverride("indoor_only")
        segs = segment_window_boundaries(
            date(2026, 6, 5), date(2026, 6, 20),
            [(date(2026, 6, 1), date(2026, 6, 8), ov)],
        )
        assert segs == [(date(2026, 6, 5), date(2026, 6, 8), (ov,))]

    def test_window_outside_span_dropped(self):
        ov = EventWindowOverride("indoor_only")
        segs = segment_window_boundaries(
            date(2026, 6, 1), date(2026, 6, 10),
            [(date(2026, 7, 1), date(2026, 7, 5), ov)],
        )
        assert segs == []

    def test_overlapping_windows_union_in_overlap_segment(self):
        a = EventWindowOverride("indoor_only")
        b = EventWindowOverride("locale_unavailable", "park")
        segs = segment_window_boundaries(
            date(2026, 6, 1), date(2026, 6, 30),
            [(date(2026, 6, 5), date(2026, 6, 15), a),
             (date(2026, 6, 10), date(2026, 6, 20), b)],
        )
        # three atomic ranges: a-only, a+b, b-only
        assert [(s, e) for s, e, _ in segs] == [
            (date(2026, 6, 5), date(2026, 6, 9)),
            (date(2026, 6, 10), date(2026, 6, 15)),
            (date(2026, 6, 16), date(2026, 6, 20)),
        ]
        assert segs[1][2] == (a, b)  # overlap segment carries both (sorted)

    def test_no_windows_empty(self):
        assert segment_window_boundaries(date(2026, 6, 1), date(2026, 6, 10), []) == []


# ─── reduced environment + cascade routing (spec §9 scenarios 2–5) ───────────

class TestReducedEnvRouting:
    def test_indoor_only_reroutes_outdoor_to_indoor_machine(self):
        # D-001 Trail Running: trail at home + a treadmill → exact normally.
        fi = _mk_inputs(
            cluster=["home"],
            terrain_by_locale={"home": {"TRN-002"}},
            equip_by_locale={"home": {"Treadmill"}},
            disciplines=["D-001"],
        )
        home = _resolve_included_feasibility(
            fi, locale_order=fi.cluster,
            terrain_by_locale=fi.terrain_by_locale, equip_by_locale=fi.equip_by_locale,
        )
        assert home["D-001"].tier == "exact"

        order, terr, equip = _reduced_env(fi, (EventWindowOverride("indoor_only"),))
        assert terr == {"home": set()}        # all outdoor terrain removed
        assert equip == {"home": {"Treadmill"}}  # equipment untouched
        reduced = _resolve_included_feasibility(
            fi, locale_order=order, terrain_by_locale=terr, equip_by_locale=equip,
        )
        assert reduced["D-001"].tier == "indoor"
        assert reduced["D-001"].machine == "Treadmill"

    def test_indoor_only_no_machine_falls_to_strength(self):
        fi = _mk_inputs(
            cluster=["home"],
            terrain_by_locale={"home": {"TRN-002"}},
            equip_by_locale={"home": set()},
            disciplines=["D-001"],
            pool_by_discipline={"D-001": ["EX-1", "EX-2"]},
        )
        order, terr, equip = _reduced_env(fi, (EventWindowOverride("indoor_only"),))
        reduced = _resolve_included_feasibility(
            fi, locale_order=order, terrain_by_locale=terr, equip_by_locale=equip,
        )
        assert reduced["D-001"].tier == "strength"

    def test_locale_unavailable_fallback_stays_exact(self):
        # Two locales both carry trail; closing one keeps D-001 exact at the other
        # ("not always a downgrade" — the cascade finds the fallback).
        fi = _mk_inputs(
            cluster=["home", "park"],
            terrain_by_locale={"home": {"TRN-002"}, "park": {"TRN-002"}},
            equip_by_locale={"home": set(), "park": set()},
            disciplines=["D-001"],
        )
        order, terr, equip = _reduced_env(
            fi, (EventWindowOverride("locale_unavailable", "park"),)
        )
        assert "park" not in terr and order == ["home"]
        reduced = _resolve_included_feasibility(
            fi, locale_order=order, terrain_by_locale=terr, equip_by_locale=equip,
        )
        assert reduced["D-001"].tier == "exact"
        assert reduced["D-001"].locale_id == "home"

    def test_locale_unavailable_only_terrain_source_degrades(self):
        # Only "park" carries the trail; closing it forces indoor/strength.
        fi = _mk_inputs(
            cluster=["home", "park"],
            terrain_by_locale={"home": set(), "park": {"TRN-002"}},
            equip_by_locale={"home": {"Treadmill"}, "park": set()},
            disciplines=["D-001"],
        )
        order, terr, equip = _reduced_env(
            fi, (EventWindowOverride("locale_unavailable", "park"),)
        )
        reduced = _resolve_included_feasibility(
            fi, locale_order=order, terrain_by_locale=terr, equip_by_locale=equip,
        )
        assert reduced["D-001"].tier == "indoor"

    def test_locale_not_in_cluster_is_noop(self):
        fi = _mk_inputs(
            cluster=["home"],
            terrain_by_locale={"home": {"TRN-002"}},
            equip_by_locale={"home": set()},
            disciplines=["D-001"],
        )
        order, terr, equip = _reduced_env(
            fi, (EventWindowOverride("locale_unavailable", "ghost"),)
        )
        assert order == ["home"] and terr == {"home": {"TRN-002"}}


# ─── _build_event_window_overlay glue (changed-only + no-op dropped) ─────────

class TestOverlayBuilder:
    def _patch(self, monkeypatch, fi, windows):
        import layer4.orchestrator as orch
        monkeypatch.setattr(orch, "load_event_windows", lambda db, uid: windows)
        monkeypatch.setattr(orch, "load_gear_locales", lambda db, uid: {})
        monkeypatch.setattr(orch, "_gather_feasibility_inputs", lambda db, uid, cone: fi)

    def test_changed_segment_emitted_noop_dropped(self, monkeypatch):
        fi = _mk_inputs(
            cluster=["home"],
            terrain_by_locale={"home": {"TRN-002"}},
            equip_by_locale={"home": {"Treadmill"}},
            disciplines=["D-001"],
        )
        home = _resolve_included_feasibility(
            fi, locale_order=fi.cluster,
            terrain_by_locale=fi.terrain_by_locale, equip_by_locale=fi.equip_by_locale,
        )
        windows = [
            # indoor_only → D-001 exact→indoor → CHANGED → emitted
            EventWindow(1, 7, date(2026, 6, 10), date(2026, 6, 12), "indoor_only", None, None, ""),
            # locale_unavailable on a non-cluster locale → no-op → dropped
            EventWindow(2, 7, date(2026, 6, 20), date(2026, 6, 22),
                        "locale_unavailable", "ghost", None, ""),
        ]
        self._patch(monkeypatch, fi, windows)
        segments, overlapping = _build_event_window_overlay(
            None, 7, None,
            plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility=home,
        )
        assert len(overlapping) == 2          # both feed the hash
        assert len(segments) == 1             # only the changed one renders
        assert segments[0].start_date == date(2026, 6, 10)
        assert segments[0].resolutions["D-001"].tier == "indoor"

    def test_no_overlapping_windows_returns_empty(self, monkeypatch):
        fi = _mk_inputs(
            cluster=["home"], terrain_by_locale={"home": {"TRN-002"}},
            equip_by_locale={"home": set()}, disciplines=["D-001"],
        )
        windows = [
            EventWindow(1, 7, date(2026, 9, 1), date(2026, 9, 5), "indoor_only", None, None, ""),
        ]
        self._patch(monkeypatch, fi, windows)
        segments, overlapping = _build_event_window_overlay(
            None, 7, None,
            plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility={},
        )
        assert segments == [] and overlapping == []


# ─── per-date volume schedule (#889): one-day override expansion ─────────────

class TestPerDateVolumeExpansion:
    """A reduced_volume window carrying a per-DATE schedule expands into one-day
    volume segments — each covered day at its OWN retained fraction, full (1.0)
    days emitting nothing. A window WITHOUT a schedule stays one segment."""

    def _patch(self, monkeypatch, fi, windows):
        import layer4.orchestrator as orch
        monkeypatch.setattr(orch, "load_event_windows", lambda db, uid: windows)
        monkeypatch.setattr(orch, "load_gear_locales", lambda db, uid: {})
        monkeypatch.setattr(orch, "_gather_feasibility_inputs", lambda db, uid, cone: fi)

    def _fi_home(self):
        # D-001 fully feasible at home (trail terrain) → reduced_volume changes no
        # feasibility, so a segment is emitted purely for its volume effect.
        return _mk_inputs(
            cluster=["home"],
            terrain_by_locale={"home": {"TRN-002"}},
            equip_by_locale={"home": set()},
            disciplines=["D-001"],
        )

    def test_per_day_schedule_expands_to_one_day_segments(self, monkeypatch):
        fi = self._fi_home()
        home = _resolve_included_feasibility(
            fi, locale_order=fi.cluster,
            terrain_by_locale=fi.terrain_by_locale, equip_by_locale=fi.equip_by_locale,
        )
        # 6/10..6/12 window; 6/10 dialed to 0.25, 6/11 full (no reduction),
        # 6/12 unmapped → falls back to the window-wide 0.5.
        win = EventWindow(
            id=1, user_id=7, start_date=date(2026, 6, 10), end_date=date(2026, 6, 12),
            override_type="reduced_volume", unavailable_locale=None, away_locale=None,
            notes="", volume_pct=0.5,
            volume_by_date={date(2026, 6, 10): 0.25, date(2026, 6, 11): 1.0},
        )
        self._patch(monkeypatch, fi, [win])
        segments, overlapping = _build_event_window_overlay(
            None, 7, None,
            plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility=home,
        )
        assert len(overlapping) == 1  # the single declared window feeds the hash
        by_pct = {s.start_date: s.volume_pct for s in segments}
        # 6/10 at its dialed 0.25; 6/12 at the window default 0.5; 6/11 (full)
        # emits no volume segment.
        assert by_pct == {date(2026, 6, 10): 0.25, date(2026, 6, 12): 0.5}
        assert all(s.start_date == s.end_date for s in segments)  # one-day each
        assert all(s.start_date != date(2026, 6, 11) for s in segments)

    def test_no_schedule_stays_single_segment(self, monkeypatch):
        # Regression: a reduced_volume window with no per-date map is one segment
        # spanning the whole window (byte-identical to pre-#889).
        fi = self._fi_home()
        home = _resolve_included_feasibility(
            fi, locale_order=fi.cluster,
            terrain_by_locale=fi.terrain_by_locale, equip_by_locale=fi.equip_by_locale,
        )
        win = EventWindow(
            id=1, user_id=7, start_date=date(2026, 6, 10), end_date=date(2026, 6, 12),
            override_type="reduced_volume", unavailable_locale=None, away_locale=None,
            notes="", volume_pct=0.5,
        )
        self._patch(monkeypatch, fi, [win])
        segments, _ = _build_event_window_overlay(
            None, 7, None,
            plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility=home,
        )
        assert len(segments) == 1
        assert segments[0].start_date == date(2026, 6, 10)
        assert segments[0].end_date == date(2026, 6, 12)
        assert segments[0].volume_pct == 0.5

    def test_non_reduced_window_with_per_day_schedule_yields_volume_segments(
        self, monkeypatch
    ):
        # Consolidated per-day editor — per-day % now layers onto ANY window type.
        # An indoor_only window carrying a per-DATE schedule expands into one-day
        # volume segments (mirrors the reduced_volume expansion), the volume
        # carried on the non-reduced override now being picked up by vol_overrides.
        fi = self._fi_home()
        home = _resolve_included_feasibility(
            fi, locale_order=fi.cluster,
            terrain_by_locale=fi.terrain_by_locale, equip_by_locale=fi.equip_by_locale,
        )
        win = EventWindow(
            id=1, user_id=7, start_date=date(2026, 6, 10), end_date=date(2026, 6, 12),
            override_type="indoor_only", unavailable_locale=None, away_locale=None,
            notes="", volume_pct=None,
            volume_by_date={date(2026, 6, 10): 0.25, date(2026, 6, 11): 1.0,
                            date(2026, 6, 12): 0.5},
        )
        self._patch(monkeypatch, fi, [win])
        segments, overlapping = _build_event_window_overlay(
            None, 7, None,
            plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility=home,
        )
        assert len(overlapping) == 1
        by_pct = {s.start_date: s.volume_pct for s in segments}
        # 6/10 at 0.25, 6/12 at 0.5; 6/11 (full) emits no volume segment.
        assert by_pct == {date(2026, 6, 10): 0.25, date(2026, 6, 12): 0.5}
        assert all(s.start_date == s.end_date for s in segments)


# ─── away windows (Slice 2): replacement env + counts-follow-away ────────────

class TestAwayWindows:
    """`away` REPLACES the home cluster with the destination's own radius cluster
    (re-anchored `cluster_locale_ids`), with `owned_crafts=[]` (F4). The SAME
    cascade runs against the away env (spec §4). The away segment carries the FULL
    away feasibility for the grid (counts-follow-away, §4.1)."""

    def _patch(self, monkeypatch, fi, windows, *, cluster, terrain, equip,
               gear_locales=None, away_pool=None, away_flags=None):
        import layer4.orchestrator as orch
        monkeypatch.setattr(orch, "load_event_windows", lambda db, uid: windows)
        monkeypatch.setattr(
            orch, "load_gear_locales", lambda db, uid: dict(gear_locales or {})
        )
        monkeypatch.setattr(orch, "_gather_feasibility_inputs", lambda db, uid, cone: fi)
        # #884 slice 6 — the away branch builds a destination 2C payload; stub it
        # (and the locale-equipment read it needs) so the cascade gets `away_pool`
        # and the overlay gets `away_flags` (PR-2 toggle-off flags).
        # Defaults to the home pool (a real destination 2C is never empty —
        # bodyweight strength always resolves), so away strength substitution keeps
        # working unless a test overrides to assert home-vs-destination divergence.
        pool = fi.pool_by_discipline if away_pool is None else away_pool
        monkeypatch.setattr(
            orch, "q_layer2c_equipment_mapper_payload",
            lambda *a, **k: _fake_l2c(pool, away_flags),
        )
        monkeypatch.setattr(
            orch.locations, "locale_effective_tags",
            lambda db, uid, loc, exclude_disputed=False: set(),
        )
        monkeypatch.setattr(
            orch.locations, "cluster_locale_ids",
            lambda db, uid, anchor_locale=None: cluster,
        )
        monkeypatch.setattr(
            orch.locations, "cluster_terrain_by_locale",
            lambda db, uid, c: terrain,
        )
        monkeypatch.setattr(
            orch.locations, "cluster_equipment_by_locale",
            lambda db, uid, c: equip,
        )
        monkeypatch.setattr(
            orch.locations, "cluster_locale_meta",
            lambda db, uid, c, anchor_locale=None: {
                loc: {"name": loc, "distance_km": None} for loc in c
            },
        )

    def _away_win(self, dest):
        return EventWindow(
            1, 7, date(2026, 6, 10), date(2026, 6, 12), "away", None, dest, "",
        )

    def test_away_degrades_when_destination_lacks_terrain(self, monkeypatch):
        # Home: trail + treadmill → D-001 exact. Away "hotel": nothing → strength.
        fi = _mk_inputs(
            cluster=["home"], terrain_by_locale={"home": {"TRN-002"}},
            equip_by_locale={"home": {"Treadmill"}}, disciplines=["D-001"],
            pool_by_discipline={"D-001": ["EX-1"]},
        )
        home = _resolve_included_feasibility(
            fi, locale_order=fi.cluster,
            terrain_by_locale=fi.terrain_by_locale, equip_by_locale=fi.equip_by_locale,
        )
        assert home["D-001"].tier == "exact"
        self._patch(
            monkeypatch, fi, [self._away_win("hotel")],
            cluster=["hotel"], terrain={"hotel": set()}, equip={"hotel": set()},
        )
        segments, overlapping = _build_event_window_overlay(
            None, 7, _fake_cone(), plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility=home,
        )
        assert len(overlapping) == 1 and len(segments) == 1
        seg = segments[0]
        assert seg.resolutions["D-001"].tier == "strength"
        # counts-follow-away needs the FULL away map on the segment (§4.1).
        assert seg.away_feasibility is not None
        assert seg.away_feasibility["D-001"].tier == "strength"

    def test_away_stays_exact_when_destination_has_terrain(self, monkeypatch):
        # Home: no trail (indoor only). Away "trailtown": trail → exact (CHANGED).
        fi = _mk_inputs(
            cluster=["home"], terrain_by_locale={"home": set()},
            equip_by_locale={"home": {"Treadmill"}}, disciplines=["D-001"],
        )
        home = _resolve_included_feasibility(
            fi, locale_order=fi.cluster,
            terrain_by_locale=fi.terrain_by_locale, equip_by_locale=fi.equip_by_locale,
        )
        assert home["D-001"].tier == "indoor"
        self._patch(
            monkeypatch, fi, [self._away_win("trailtown")],
            cluster=["trailtown"], terrain={"trailtown": {"TRN-002"}},
            equip={"trailtown": set()},
        )
        segments, _ = _build_event_window_overlay(
            None, 7, _fake_cone(), plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility=home,
        )
        assert segments[0].away_feasibility["D-001"].tier == "exact"

    def test_away_wins_over_subtractive_on_same_dates(self, monkeypatch):
        # An away + indoor_only declared on the same dates → away replaces; the
        # subtractive override is ignored (precedence, §4).
        fi = _mk_inputs(
            cluster=["home"], terrain_by_locale={"home": set()},
            equip_by_locale={"home": set()}, disciplines=["D-001"],
        )
        home = _resolve_included_feasibility(
            fi, locale_order=fi.cluster,
            terrain_by_locale=fi.terrain_by_locale, equip_by_locale=fi.equip_by_locale,
        )
        windows = [
            self._away_win("trailtown"),
            EventWindow(2, 7, date(2026, 6, 10), date(2026, 6, 12),
                        "indoor_only", None, None, ""),
        ]
        self._patch(
            monkeypatch, fi, windows,
            cluster=["trailtown"], terrain={"trailtown": {"TRN-002"}},
            equip={"trailtown": set()},
        )
        segments, _ = _build_event_window_overlay(
            None, 7, _fake_cone(), plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility=home,
        )
        # away env resolved (D-001 exact at trailtown), not the home-indoor result.
        assert segments[0].away_feasibility["D-001"].tier == "exact"

    def test_away_strength_pool_comes_from_destination_2c(self, monkeypatch):
        # #884 slice 6 per-segment 2C re-resolve — an away week's strength
        # substitute draws from the DESTINATION's 2C pool (EX-AWAY), not the home
        # gym's (EX-HOME). The away cascade receives the destination pool as
        # `pool_override` (reverses the #780 "substitute at home" default for away
        # segments only).
        import layer4.orchestrator as orch
        fi = _mk_inputs(
            cluster=["home"], terrain_by_locale={"home": set()},
            equip_by_locale={"home": set()}, disciplines=["D-001"],
            pool_by_discipline={"D-001": ["EX-HOME"]},
        )
        self._patch(
            monkeypatch, fi, [self._away_win("hotel")],
            cluster=["hotel"], terrain={"hotel": set()}, equip={"hotel": set()},
            away_pool={"D-001": ["EX-AWAY"]},
        )
        recorded: dict = {}

        def _spy(_fi, *, pool_override=None, **kw):
            if pool_override is not None:
                recorded["pool"] = pool_override
            return {}

        monkeypatch.setattr(orch, "_resolve_included_feasibility", _spy)
        _build_event_window_overlay(
            None, 7, _fake_cone(),
            plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility={},
        )
        assert recorded["pool"] == {"D-001": ["EX-AWAY"]}

    def test_away_toggle_flags_populated_from_destination_2c(self, monkeypatch):
        # #884 slice 6 PR-2 — the destination's toggle_off_for_discipline 2C flags
        # land on the away segment as (discipline_name, gear_label) pairs.
        fi = _mk_inputs(
            cluster=["home"], terrain_by_locale={"home": set()},
            equip_by_locale={"home": set()}, disciplines=["D-001"],
            pool_by_discipline={"D-001": ["EX-1"]},
        )
        self._patch(
            monkeypatch, fi, [self._away_win("hotel")],
            cluster=["hotel"], terrain={"hotel": set()}, equip={"hotel": set()},
            away_flags=[("Sport Climbing", "Climbing gear")],
        )
        segments, _ = _build_event_window_overlay(
            None, 7, _fake_cone(),
            plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility={},
        )
        assert segments[0].away_toggle_flags == (("Sport Climbing", "Climbing gear"),)


class TestExtractPoolByDiscipline:
    """`_extract_pool_by_discipline` (#884 slice 6) groups a 2C payload's tier-1/2/3
    exercises by discipline, dropping tier-0 (unavailable) and sorting each pool by
    per-discipline priority. Shared by the home cone build + the away re-resolve."""

    def test_filters_tier_zero_and_sorts_by_priority(self):
        l2c = SimpleNamespace(exercises_resolved=[
            SimpleNamespace(tier=2, discipline_ids=["D-1"], exercise_id="LOW",
                            priority_per_discipline={"D-1": "Low"}),
            SimpleNamespace(tier=1, discipline_ids=["D-1"], exercise_id="CRIT",
                            priority_per_discipline={"D-1": "Critical"}),
            SimpleNamespace(tier=0, discipline_ids=["D-1"], exercise_id="DROP",
                            priority_per_discipline={"D-1": "Critical"}),
        ])
        # tier-0 dropped; Critical sorts before Low within the discipline.
        assert _extract_pool_by_discipline(l2c) == {"D-1": ["CRIT", "LOW"]}


# ─── away craft: brought-craft (c) ∪ standing gear↔locale (b) ────────────────

class TestAwayCraft:
    """The away segment's `owned_crafts` is the union of the window's brought-craft
    (c) and the standing gear kept at any locale in the destination cluster (b),
    filtered to the craft cascade kinds. Verified by spying the craft set passed to
    `_resolve_included_feasibility` — only that value changes (the cascade is
    reused). #884 slice 5 cut the standing (b) read over from the legacy
    craft-locale store to the unified `athlete_gear_locale` store + added the
    craft-kind filter; bike/paddle is byte-identical (backfilled 1:1)."""

    def _captured_owned_crafts(self, monkeypatch, windows, *, cluster,
                               gear_locales=None):
        import layer4.orchestrator as orch
        fi = _mk_inputs(
            cluster=["home"], terrain_by_locale={"home": set()},
            equip_by_locale={"home": set()}, disciplines=["D-008"],
        )
        recorded: dict = {}

        def _spy(_fi, *, locale_order, terrain_by_locale, equip_by_locale,
                 owned_crafts=None, locale_meta=None, pool_override=None):
            recorded["owned_crafts"] = owned_crafts
            return {}

        monkeypatch.setattr(orch, "load_event_windows", lambda db, uid: windows)
        monkeypatch.setattr(
            orch, "load_gear_locales", lambda db, uid: dict(gear_locales or {})
        )
        monkeypatch.setattr(orch, "_gather_feasibility_inputs", lambda db, uid, cone: fi)
        # #884 slice 6 — stub the away-branch destination 2C build (and its
        # locale-equipment read) so the spy below only observes owned_crafts.
        monkeypatch.setattr(
            orch, "q_layer2c_equipment_mapper_payload", lambda *a, **k: _fake_l2c()
        )
        monkeypatch.setattr(
            orch.locations, "locale_effective_tags",
            lambda db, uid, loc, exclude_disputed=False: set(),
        )
        monkeypatch.setattr(orch, "_resolve_included_feasibility", _spy)
        monkeypatch.setattr(
            orch.locations, "cluster_locale_ids",
            lambda db, uid, anchor_locale=None: list(cluster),
        )
        monkeypatch.setattr(
            orch.locations, "cluster_terrain_by_locale", lambda db, uid, c: {}
        )
        monkeypatch.setattr(
            orch.locations, "cluster_equipment_by_locale", lambda db, uid, c: {}
        )
        monkeypatch.setattr(
            orch.locations, "cluster_locale_meta",
            lambda db, uid, c, anchor_locale=None: {},
        )
        _build_event_window_overlay(
            None, 7, _fake_cone(), plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility={},
        )
        return recorded["owned_crafts"]

    def _away_win(self, dest, brought=()):
        return EventWindow(
            1, 7, date(2026, 6, 10), date(2026, 6, 12), "away", None, dest, "",
            brought_gear=tuple(brought),
        )

    def test_brought_gear_passed_as_owned_crafts(self, monkeypatch):
        got = self._captured_owned_crafts(
            monkeypatch, [self._away_win("belfast", ("packraft",))],
            cluster=["belfast"],
        )
        assert got == ["packraft"]

    def test_standing_craft_at_cluster_locale_unioned(self, monkeypatch):
        got = self._captured_owned_crafts(
            monkeypatch, [self._away_win("cabin")], cluster=["cabin"],
            gear_locales={"cabin": ["mountain_bike"]},
        )
        assert got == ["mountain_bike"]

    def test_brought_toggle_gear_passed_as_owned_crafts(self, monkeypatch):
        # #884 slice 6b / design §17 — climbing gear brought to an away window
        # flows into the away segment's owned_crafts (group_kind 'climb' is in
        # _CRAFT_ALIAS_GROUP_KINDS), so the climbing discipline resolves feasible
        # at the destination for that segment only. The brought-picker
        # generalization is what makes this capturable.
        got = self._captured_owned_crafts(
            monkeypatch, [self._away_win("belfast", ("climbing_gear",))],
            cluster=["belfast"],
        )
        assert got == ["climbing_gear"]

    def test_brought_and_standing_union_deduped_and_sorted(self, monkeypatch):
        got = self._captured_owned_crafts(
            monkeypatch, [self._away_win("cabin", ("packraft",))], cluster=["cabin"],
            gear_locales={"cabin": ["packraft", "mountain_bike"]},
        )
        assert got == ["mountain_bike", "packraft"]

    def test_standing_craft_outside_away_cluster_excluded(self, monkeypatch):
        got = self._captured_owned_crafts(
            monkeypatch, [self._away_win("belfast")], cluster=["belfast"],
            gear_locales={"home": ["road_bike"]},
        )
        assert got == []

    def test_empty_union_is_byte_identical_to_slice2a(self, monkeypatch):
        got = self._captured_owned_crafts(
            monkeypatch, [self._away_win("belfast")], cluster=["belfast"],
        )
        assert got == []

    # ── #884 slice 5: the unified gear store feeds non-bike/paddle kinds ──────
    def test_standing_gear_toggle_kind_unioned(self, monkeypatch):
        # Climbing gear stationed at the away locale (a discipline-unlocking gear
        # toggle, group_kind 'climb') now flows into the away cascade's owned_crafts
        # — the win the unified store buys over the bike/paddle-only craft-locale.
        got = self._captured_owned_crafts(
            monkeypatch, [self._away_win("crag")], cluster=["crag"],
            gear_locales={"crag": ["climbing_gear"]},
        )
        assert got == ["climbing_gear"]

    def test_non_craft_gear_filtered_out(self, monkeypatch):
        # Swim gear (group_kind 'swim') is drill-gating only, never a craft cascade
        # input — the craft-kind filter drops it so it can't leak into owned_crafts.
        got = self._captured_owned_crafts(
            monkeypatch, [self._away_win("pool_town")], cluster=["pool_town"],
            gear_locales={"pool_town": ["paddles", "pull_buoy", "mountain_bike"]},
        )
        assert got == ["mountain_bike"]


class TestCountsFollowAway:
    """Spec §4.1 — a plan week FULLY inside an away window is counted against the
    destination (the grid is fed the away tiers); a partial week keeps home."""

    def _l2a(self):
        def _disc(did, name, lw):
            return Layer2ADiscipline(
                discipline_id=did, discipline_name=name,
                inclusion="included", role="Primary", is_conditional=False,
                load_weight=WeightResult(
                    value=lw, source="system_default", system_default=lw,
                ),
                sleep_deprivation_relevant=False, rationale="t",
                phase_load=PhaseLoadBands(
                    base_low=20.0, base_high=30.0, build_low=20.0, build_high=30.0,
                    peak_low=40.0, peak_high=50.0, taper_low=20.0, taper_high=30.0,
                    default_inclusion="included",
                ),
            )
        return Layer2APayload(
            framework_sport="adventure_racing", etl_version_set={"layer0": "v7"},
            disciplines=[_disc("D-001", "Trail Running", 3.0),
                         _disc("D-008", "Mountain Biking", 2.0)],
            training_gaps_summary=TrainingGapsSummary(
                flagged_count=0, any_no_substitute=False,
                any_multi_substitute_candidate=False),
            hitl_required=False, unresolved_flags=[], coaching_flags=[],
            rationale_metadata=RationaleMetadata(
                template_version="v1", generated_at="2026-06-06T00:00:00Z"),
            weekly_total_hours_by_phase={
                "Base": (8.0, 10.0), "Build": (10.0, 14.0),
                "Peak": (12.0, 16.0), "Taper": (5.0, 7.0)},
        )

    def _phase(self, start):
        # A 2-week Peak phase: week 1 = start..+6, week 2 = start+7..+13.
        return PhaseStructure(
            phases=[PhaseSpec(
                phase_name="Peak", start_date=start, end_date=start + timedelta(days=13),
                weeks=2, intended_volume_band=(12.0, 16.0),
                intended_intensity_distribution={"easy": 0.7, "hard": 0.3},
                synthesis_metadata=SynthesisMetadata(
                    model="m", temperature=0.2, input_tokens=0, output_tokens=0,
                    latency_ms=0, retries_used=0, cap_hit=False),
            )],
            total_weeks=2, derived_from="3b_standard",
        )

    def _away_seg(self, start, end):
        # Away env: D-008 (bike) infeasible (strength), D-001 exact.
        res = {
            "D-001": TerrainResolution(discipline_id="D-001", tier="exact",
                                       locale_id="away", note="trail away"),
            "D-008": TerrainResolution(discipline_id="D-008", tier="strength",
                                       locale_id=None, note="no craft away"),
        }
        return EventWindowSegment(
            start, end, (EventWindowOverride("away", away_locale="away"),),
            {"D-008": res["D-008"]}, away_feasibility=res,
        )

    def test_fully_away_week_logged_partial_not(self, capsys):
        start = date(2026, 6, 1)
        l2a, ps = self._l2a(), self._phase(start)
        # Away window covers ALL of week 1 (06-01..06-07) but only part of week 2.
        seg = self._away_seg(start, start + timedelta(days=9))  # 06-01..06-10
        _format_session_grid(
            {"availability": {}}, l2a, ps, "Peak", None,
            terrain_feasibility=None, event_window_segments=[seg],
        )
        logged = capsys.readouterr().out
        assert "counts_follow_away: Peak:w1" in logged   # week 1 fully away
        assert "counts_follow_away: Peak:w2" not in logged  # week 2 only partial

    def test_no_away_segment_never_logs(self, capsys):
        start = date(2026, 6, 1)
        _format_session_grid(
            {"availability": {}}, self._l2a(), self._phase(start), "Peak", None,
            terrain_feasibility=None, event_window_segments=None,
        )
        assert "counts_follow_away" not in capsys.readouterr().out

    def test_skill_gated_annotation_carries_no_slug(self):
        # #618 — the skill-gate grid annotation flags the gated discipline for a
        # strength substitution, but must not leak the raw toggle slug into the
        # synthesis prompt (the LLM was echoing it into athlete-facing text).
        start = date(2026, 6, 1)
        lines = _format_session_grid(
            {"identity": {"weekly_hours_target": 15.0}},
            self._l2a(), self._phase(start), "Peak", None,
            skill_gated={"D-008": "climbing_roped"},
        )
        out = "\n".join(lines)
        assert "SKILL-GATED" in out
        assert "climbing_roped" not in out


# ─── synthesis overlay render (Trigger #1 wording) ───────────────────────────

class TestOverlayRender:
    def _segment(self):
        res = TerrainResolution(
            discipline_id="D-001", tier="indoor", locale_id="home", machine="Treadmill",
            note="indoor Treadmill at home",
        )
        return EventWindowSegment(
            date(2026, 6, 10), date(2026, 6, 12),
            (EventWindowOverride("indoor_only"),),
            {"D-001": res},
        )

    def test_renders_block_for_overlapping_unit(self):
        out = _format_event_window_overlay(
            [self._segment()], date(2026, 6, 1), date(2026, 6, 14), None, {},
        )
        text = "\n".join(out)
        assert "Event-window overlay" in text
        assert "indoor-only (no outdoor terrain available)" in text
        assert "2026-06-10–2026-06-12" in text
        assert "D-001" in text
        assert "Placement preference (soft)" in text

    def test_clips_displayed_dates_to_unit_window(self):
        out = _format_event_window_overlay(
            [self._segment()], date(2026, 6, 11), date(2026, 6, 30), None, {},
        )
        # segment 06-10..06-12 clipped to the unit start 06-11
        assert any("2026-06-11–2026-06-12" in line for line in out)

    def test_empty_when_no_overlap(self):
        assert _format_event_window_overlay(
            [self._segment()], date(2026, 7, 1), date(2026, 7, 30), None, {},
        ) == []

    def test_empty_when_no_segments(self):
        assert _format_event_window_overlay(
            None, date(2026, 6, 1), date(2026, 6, 14), None, {},
        ) == []

    def test_away_segment_renders_away_label(self):
        res = TerrainResolution(
            discipline_id="D-008", tier="strength", locale_id=None,
            note="no craft away",
        )
        seg = EventWindowSegment(
            date(2026, 6, 10), date(2026, 6, 12),
            (EventWindowOverride("away", away_locale="hotel"),),
            {"D-008": res}, away_feasibility={"D-008": res},
        )
        text = "\n".join(_format_event_window_overlay(
            [seg], date(2026, 6, 1), date(2026, 6, 14), None, {},
        ))
        assert 'away at "hotel"' in text
        assert "any craft you have there" in text  # Slice 4 dropped "no brought craft"
        assert "replaced (training away" in text  # away-aware intro

    def test_assumed_baseline_note_renders_on_cold_away_segment(self):
        # Slice 3 (F8): a cold destination resolved on the category baseline →
        # the overlay tells the athlete to log actuals on arrival.
        res = TerrainResolution(
            discipline_id="D-008", tier="indoor", locale_id="belfast_hotel",
            note="assumed",
        )
        seg = EventWindowSegment(
            date(2026, 6, 10), date(2026, 6, 12),
            (EventWindowOverride("away", away_locale="belfast_hotel"),),
            {"D-008": res}, away_feasibility={"D-008": res},
            assumed_baseline_category="hotel gym",
        )
        text = "\n".join(_format_event_window_overlay(
            [seg], date(2026, 6, 1), date(2026, 6, 14), None, {},
        ))
        assert "assumed from the standard hotel gym baseline" in text
        assert "log the gym's actual equipment on arrival" in text

    def test_no_baseline_note_when_destination_logged(self):
        # assumed_baseline_category None (logged destination) → no note.
        res = TerrainResolution(
            discipline_id="D-008", tier="strength", locale_id=None, note="x",
        )
        seg = EventWindowSegment(
            date(2026, 6, 10), date(2026, 6, 12),
            (EventWindowOverride("away", away_locale="hotel"),),
            {"D-008": res}, away_feasibility={"D-008": res},
        )
        text = "\n".join(_format_event_window_overlay(
            [seg], date(2026, 6, 1), date(2026, 6, 14), None, {},
        ))
        assert "baseline" not in text

    def test_away_toggle_off_flags_render_in_overlay(self):
        # #884 slice 6 PR-2 — the away toggle-off flags render the approved copy so
        # the synthesizer doesn't program a destination-unavailable discipline.
        res = TerrainResolution(
            discipline_id="D-008", tier="strength", locale_id=None, note="x",
        )
        seg = EventWindowSegment(
            date(2026, 6, 10), date(2026, 6, 12),
            (EventWindowOverride("away", away_locale="hotel"),),
            {"D-008": res}, away_feasibility={"D-008": res},
            away_toggle_flags=(("Sport Climbing", "Climbing gear"),),
        )
        text = "\n".join(_format_event_window_overlay(
            [seg], date(2026, 6, 1), date(2026, 6, 14), None, {},
        ))
        assert "At this destination you won't have: Sport Climbing (no Climbing gear on hand)" in text
        assert "don't program these disciplines for these dates" in text


# ─── hashing + cache-key regression ──────────────────────────────────────────

class TestHashAndKey:
    def _win(self, ot="indoor_only", loc=None, away=None):
        return EventWindow(1, 7, date(2026, 6, 10), date(2026, 6, 12), ot, loc, away, "")

    def test_hash_order_independent_and_nonempty(self):
        a = self._win("indoor_only")
        b = self._win("locale_unavailable", "park")
        assert compute_event_windows_hash([a, b]) == compute_event_windows_hash([b, a])
        assert compute_event_windows_hash([]) != compute_event_windows_hash([a])

    def test_hash_changes_with_away_locale(self):
        belfast = self._win("away", away="belfast")
        chamonix = self._win("away", away="chamonix")
        assert compute_event_windows_hash([belfast]) != compute_event_windows_hash([chamonix])

    def test_hash_changes_with_brought_gear(self):
        # Slice 4 (c): brought-gear is a declared window field → in the digest.
        bare = self._win("away", away="belfast")
        packraft = EventWindow(
            1, 7, date(2026, 6, 10), date(2026, 6, 12), "away", None, "belfast", "",
            brought_gear=("packraft",),
        )
        assert compute_event_windows_hash([bare]) != compute_event_windows_hash([packraft])

    def _key_kwargs(self):
        return dict(
            user_id=7, layer1_hash="l1", layer2a_hash="2a", layer2b_hash="2b",
            layer2c_bundle_hash="2c", layer2d_hash="2d", layer2e_hash="2e",
            layer3a_hash="3a", layer3b_hash="3b", plan_start_date=date(2026, 6, 1),
            etl_version_set={"x": "1"}, model_synthesizer="m", model_seam_reviewer="m",
            temperature=0.2, max_tokens_per_phase=0, capped_retries_per_phase=2,
        )

    def test_plan_create_key_byte_identical_when_no_windows(self):
        base = plan_create_key(**self._key_kwargs())
        with_none = plan_create_key(**self._key_kwargs(), event_windows_hash=None)
        assert base == with_none

    def test_plan_create_key_changes_with_windows(self):
        base = plan_create_key(**self._key_kwargs())
        ewh = compute_event_windows_hash([self._win()])
        assert plan_create_key(**self._key_kwargs(), event_windows_hash=ewh) != base

    def test_plan_refresh_key_byte_identical_when_no_windows(self):
        kw = dict(
            user_id=7, tier="T1", refresh_scope_start=date(2026, 6, 1),
            refresh_scope_end=date(2026, 6, 30), layer1_hash="l1",
            layer2_bundle_canonical_hash="b", layer3a_hash="3a", layer3b_hash="3b",
            prior_plan_session_window_hash="w", parsed_intent_hash=None,
            etl_version_set={"x": "1"}, model_synthesizer="m", model_seam_reviewer=None,
            temperature=0.2, max_tokens=10, capped_retries=2,
        )
        assert plan_refresh_key(**kw) == plan_refresh_key(**kw, event_windows_hash=None)

    def test_plan_refresh_key_changes_with_windows(self):
        kw = dict(
            user_id=7, tier="T1", refresh_scope_start=date(2026, 6, 1),
            refresh_scope_end=date(2026, 6, 30), layer1_hash="l1",
            layer2_bundle_canonical_hash="b", layer3a_hash="3a", layer3b_hash="3b",
            prior_plan_session_window_hash="w", parsed_intent_hash=None,
            etl_version_set={"x": "1"}, model_synthesizer="m", model_seam_reviewer=None,
            temperature=0.2, max_tokens=10, capped_retries=2,
        )
        ewh = compute_event_windows_hash([self._win()])
        assert plan_refresh_key(**kw, event_windows_hash=ewh) != plan_refresh_key(**kw)


# ─── repo: app-layer validation ──────────────────────────────────────────────

class TestRepo:
    def test_load_coerces_dates_and_orders(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {"id": 1, "user_id": 7, "start_date": "2026-06-10",
             "end_date": "2026-06-12", "override_type": "indoor_only",
             "unavailable_locale": None, "away_locale": None,
             "brought_gear": None, "volume_pct": None, "volume_by_date": None,
             "notes": ""},
        ])
        windows = load_event_windows(conn, 7)
        assert windows[0].start_date == date(2026, 6, 10)
        assert isinstance(windows[0].start_date, date)
        assert windows[0].volume_pct is None
        assert "ORDER BY start_date" in conn.calls[0][0]

    def test_add_rejects_unknown_override_type(self):
        conn = _FakeConn()
        with pytest.raises(EventWindowError):
            add_event_window(
                conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
                override_type="teleport",
            )
        assert conn.calls == []  # validation precedes any write

    def test_add_rejects_end_before_start(self):
        conn = _FakeConn()
        with pytest.raises(EventWindowError):
            add_event_window(
                conn, 7, start_date=date(2026, 6, 10), end_date=date(2026, 6, 1),
                override_type="indoor_only",
            )

    def test_locale_unavailable_requires_resolvable_locale(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])  # _locale_exists → not found
        with pytest.raises(EventWindowError):
            add_event_window(
                conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
                override_type="locale_unavailable", unavailable_locale="ghost",
            )

    def test_locale_unavailable_inserts_when_resolvable(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"1": 1}])  # _locale_exists → found
        conn.queue_response(rows=[{"id": 11}])  # INSERT ... RETURNING id
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="locale_unavailable", unavailable_locale="park", notes="x",
        )
        insert = conn.calls[-1]
        assert "INSERT INTO athlete_event_windows" in insert[0]
        assert insert[1] == (7, date(2026, 6, 1), date(2026, 6, 2),
                             "locale_unavailable", "park", None, None, None, "x")

    def test_away_requires_resolvable_destination(self):
        conn = _FakeConn()
        with pytest.raises(EventWindowError):  # missing away_locale
            add_event_window(
                conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
                override_type="away",
            )
        conn2 = _FakeConn()
        conn2.queue_response(rows=[])  # _locale_exists → not found
        with pytest.raises(EventWindowError):
            add_event_window(
                conn2, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
                override_type="away", away_locale="ghost",
            )

    def test_away_inserts_and_clears_unavailable_locale(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"1": 1}])  # _locale_exists → found
        conn.queue_response(rows=[{"id": 12}])  # INSERT ... RETURNING id
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="away", away_locale="hotel",
            unavailable_locale="park",  # stray — must be nulled for away
        )
        params = conn.calls[-1][1]
        assert params[4] is None        # unavailable_locale nulled
        assert params[5] == "hotel"     # away_locale persisted

    def test_indoor_only_clears_stray_locale(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"id": 13}])  # INSERT ... RETURNING id
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="indoor_only", unavailable_locale="park",
        )
        # the stored unavailable_locale is nulled for indoor_only
        assert conn.calls[-1][1][4] is None

    def test_delete_scoped_to_user(self):
        conn = _FakeConn()
        delete_event_window(conn, 7, 3)
        assert conn.calls[0][1] == (3, 7)
        assert "user_id = ?" in conn.calls[0][0]

    def test_away_stores_brought_gear_in_enum_order(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"1": 1}])  # _locale_exists → found
        conn.queue_response(rows=[{"id": 14}])  # INSERT ... RETURNING id
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="away", away_locale="belfast",
            brought_gear=["packraft", "road_bike"],
        )
        # index 6 = brought_gear CSV, emitted in BIKE+PADDLE enum order.
        assert conn.calls[-1][1][6] == "road_bike,packraft"

    def test_away_stores_brought_toggle_gear_in_registry_order(self):
        # #884 slice 6b — brought gear generalized from craft-only to all kinds;
        # a mixed bike + climbing brought set is accepted and emitted in registry
        # (_GEAR_IDS) order — bikes precede the toggle kinds.
        conn = _FakeConn()
        conn.queue_response(rows=[{"1": 1}])  # _locale_exists → found
        conn.queue_response(rows=[{"id": 15}])  # INSERT ... RETURNING id
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="away", away_locale="belfast",
            brought_gear=["climbing_gear", "mountain_bike"],
        )
        assert conn.calls[-1][1][6] == "mountain_bike,climbing_gear"

    def test_away_rejects_unknown_brought_gear(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"1": 1}])  # _locale_exists → found
        with pytest.raises(EventWindowError):
            add_event_window(
                conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
                override_type="away", away_locale="belfast", brought_gear=["jetpack"],
            )

    def test_non_away_window_clears_brought_gear(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"id": 16}])  # INSERT ... RETURNING id
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="indoor_only", brought_gear=["packraft"],
        )
        assert conn.calls[-1][1][6] is None  # brought-gear only on 'away'


# ─── integration: the overlay reaches a full synthesis prompt ────────────────
# Reuses the per-phase prompt fixtures to confirm render_user_prompt actually
# emits the date-scoped overlay for a segment overlapping the block's date
# window (the date-intersection wiring, not just the formatter in isolation).

class TestRenderUserPromptIntegration:
    def test_overlay_appears_for_overlapping_block(self):
        from datetime import timedelta

        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b
        import tests.test_layer4_plan_create as f

        l3b = f._layer3b()
        ps = phase_structure_from_3b(l3b, f._PLAN_START)
        phase0 = ps.phases[0]
        seg = EventWindowSegment(
            phase0.start_date, phase0.start_date + timedelta(days=2),
            (EventWindowOverride("indoor_only"),),
            {"D-run": TerrainResolution(
                discipline_id="D-run", tier="indoor", locale_id="home",
                machine="Treadmill", note="indoor Treadmill at home",
            )},
        )
        l1 = {**f._layer1(), "identity": {"weekly_hours_target": 12.0}}
        text = render_user_prompt(
            phase_spec=phase0,
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=l1,
            layer2a_payload=f._layer2a(),
            layer2b_payload=f._layer2b(),
            layer2c_payloads=f._layer2c(),
            layer2d_payload=f._layer2d(),
            layer2e_payload=f._layer2e(),
            layer3a_payload=f._layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
            event_window_segments=[seg],
            week_range=(1, 1),
        )
        assert "Event-window overlay" in text
        assert "indoor-only (no outdoor terrain available)" in text
        assert "Placement preference (soft)" in text

    def test_no_overlay_when_block_outside_window(self):
        from datetime import timedelta

        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b
        import tests.test_layer4_plan_create as f

        l3b = f._layer3b()
        ps = phase_structure_from_3b(l3b, f._PLAN_START)
        phase0 = ps.phases[0]
        # A segment far in the future — week 1 of phase 0 doesn't overlap it.
        far = phase0.end_date + timedelta(days=400)
        seg = EventWindowSegment(
            far, far + timedelta(days=2), (EventWindowOverride("indoor_only"),),
            {"D-run": TerrainResolution(
                discipline_id="D-run", tier="indoor", locale_id="home",
                machine="Treadmill",
            )},
        )
        l1 = {**f._layer1(), "identity": {"weekly_hours_target": 12.0}}
        text = render_user_prompt(
            phase_spec=phase0, phase_structure=ps, phase_index_in_plan=0,
            is_first_phase_in_plan=True, layer1_payload=l1,
            layer2a_payload=f._layer2a(), layer2b_payload=f._layer2b(),
            layer2c_payloads=f._layer2c(), layer2d_payload=f._layer2d(),
            layer2e_payload=f._layer2e(), layer3a_payload=f._layer3a(),
            layer3b_payload=l3b, race_event_payload=None, prior_block_sessions=[],
            retries_used=0, rule_failures=[], seam_issues=[], seam_direction=None,
            event_window_segments=[seg], week_range=(1, 1),
        )
        assert "Event-window overlay" not in text


# ─── Slice 6 (#593) — volume / in-transit windows ────────────────────────────


class TestVolumeRepo:
    """reduced_volume / no_training validation + persistence (the data layer)."""

    def test_reduced_volume_requires_pct_in_unit_interval(self):
        conn = _FakeConn()
        for bad in (None, 0.0, 1.0, 1.5, -0.2):
            with pytest.raises(EventWindowError):
                add_event_window(
                    conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
                    override_type="reduced_volume", volume_pct=bad,
                )
        assert conn.calls == []  # validation precedes any write

    def test_reduced_volume_inserts_pct_and_clears_locale(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"id": 21}])  # INSERT ... RETURNING id
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="reduced_volume", volume_pct=0.5,
            unavailable_locale="park",  # must be cleared (volume carries no locale)
        )
        params = conn.calls[-1][1]
        # (..., unavail, away, brought_gear, volume_pct, notes)
        assert params[4] is None and params[5] is None  # locale fields cleared
        assert params[7] == 0.5

    def test_no_training_inserts_with_null_pct(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"id": 22}])  # INSERT ... RETURNING id
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 3),
            override_type="no_training",
        )
        params = conn.calls[-1][1]
        assert params[3] == "no_training"
        assert params[7] is None  # no_training stores no pct

    def test_load_round_trips_volume_pct(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {"id": 1, "user_id": 7, "start_date": "2026-06-10",
             "end_date": "2026-06-12", "override_type": "reduced_volume",
             "unavailable_locale": None, "away_locale": None,
             "brought_gear": None, "volume_pct": 0.5, "volume_by_date": None,
             "notes": ""},
        ])
        w = load_event_windows(conn, 7)[0]
        assert w.override_type == "reduced_volume"
        assert w.volume_pct == 0.5
        assert w.volume_by_date == {}  # #889 — no schedule → window-wide pct


class TestPerDateVolumeRepo:
    """#889 — the per-DATE volume schedule: load round-trip + the writer's
    validation/persistence."""

    def _row(self, **kw):
        base = {
            "id": 1, "user_id": 7, "start_date": "2026-06-10",
            "end_date": "2026-06-12", "override_type": "reduced_volume",
            "unavailable_locale": None, "away_locale": None,
            "brought_gear": None, "volume_pct": 0.5, "volume_by_date": None,
            "notes": "",
        }
        base.update(kw)
        return base

    def test_load_parses_volume_by_date_json(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row(
            volume_by_date=json.dumps({"2026-06-10": 0.25, "2026-06-12": 1.0})
        )])
        w = load_event_window(conn, 7, 1)
        assert w.volume_by_date == {date(2026, 6, 10): 0.25, date(2026, 6, 12): 1.0}

    def test_writer_serializes_sorted_map(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row()])  # load_event_window SELECT
        update_event_window_volume_by_date(
            conn, 7, 1, {date(2026, 6, 12): 0.5, date(2026, 6, 10): 0.25}
        )
        sql, params = conn.calls[-1]
        assert "UPDATE athlete_event_windows" in sql
        # Stored sorted → deterministic digest.
        assert params[0] == '{"2026-06-10": 0.25, "2026-06-12": 0.5}'

    def test_writer_clears_on_empty_map(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row()])
        update_event_window_volume_by_date(conn, 7, 1, {})
        sql, params = conn.calls[-1]
        assert "UPDATE athlete_event_windows" in sql
        assert params[0] is None  # cleared → window-wide pct again applies

    def test_writer_rejects_date_outside_window(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row()])
        with pytest.raises(EventWindowError):
            update_event_window_volume_by_date(
                conn, 7, 1, {date(2026, 6, 20): 0.5}
            )

    def test_writer_rejects_level_out_of_range(self):
        conn = _FakeConn()
        for bad in (0.0, -0.1, 1.5):
            conn.queue_response(rows=[self._row()])
            with pytest.raises(EventWindowError):
                update_event_window_volume_by_date(
                    conn, 7, 1, {date(2026, 6, 11): bad}
                )

    def test_writer_accepts_non_reduced_window(self):
        # Consolidated per-day editor — per-day % now layers onto ANY window type
        # (the reduced_volume-only gate was removed). A no_training (or any) window
        # accepts a per-day schedule, which the plan-gen overlay expands per day.
        conn = _FakeConn()
        conn.queue_response(rows=[self._row(override_type="no_training",
                                            volume_pct=None)])
        update_event_window_volume_by_date(
            conn, 7, 1, {date(2026, 6, 11): 0.5}
        )
        sql, params = conn.calls[-1]
        assert "UPDATE athlete_event_windows" in sql
        assert params[0] == '{"2026-06-11": 0.5}'

    def test_writer_rejects_unknown_window(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])  # load_event_window → None
        with pytest.raises(EventWindowError):
            update_event_window_volume_by_date(
                conn, 7, 99, {date(2026, 6, 11): 0.5}
            )


class TestPerDateRestrictionsRepo:
    """#237 — per-DATE restrictions: load round-trip + the writer's validation,
    normalization, and persistence."""

    def _row(self, **kw):
        base = {
            "id": 1, "user_id": 7, "start_date": "2026-06-10",
            "end_date": "2026-06-12", "override_type": "indoor_only",
            "unavailable_locale": None, "away_locale": None,
            "brought_gear": None, "volume_pct": None, "volume_by_date": None,
            "restrictions_by_date": None, "notes": "",
        }
        base.update(kw)
        return base

    def test_load_parses_restrictions_by_date_json(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row(restrictions_by_date=json.dumps({
            "2026-06-10": {"locale_lock": "home", "indoor_only": True},
        }))])
        w = load_event_window(conn, 7, 1)
        assert w.restrictions_by_date == {
            date(2026, 6, 10): {"locale_lock": "home", "indoor_only": True}
        }

    def test_load_ignores_legacy_discipline_exclusions_and_minutes(self):
        # A pre-2026-06-30 stored row may still carry the dropped keys; they're
        # silently ignored at parse time (no migration needed).
        conn = _FakeConn()
        conn.queue_response(rows=[self._row(restrictions_by_date=json.dumps({
            "2026-06-10": {"locale_lock": "home", "discipline_exclusions": ["D-012"],
                           "indoor_only": True, "max_total_minutes": 60},
        }))])
        w = load_event_window(conn, 7, 1)
        assert w.restrictions_by_date == {
            date(2026, 6, 10): {"locale_lock": "home", "indoor_only": True}
        }

    def test_load_absent_column_is_empty(self):
        # A driver row without the column (pre-migration / fake) → {} not a crash.
        conn = _FakeConn()
        row = self._row()
        del row["restrictions_by_date"]
        conn.queue_response(rows=[row])
        assert load_event_window(conn, 7, 1).restrictions_by_date == {}

    def test_writer_serializes_sorted_and_normalized(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row()])  # load_event_window SELECT
        conn.queue_response(rows=[{"1": 1}])  # _locale_exists → found
        update_event_window_restrictions_by_date(conn, 7, 1, {
            date(2026, 6, 12): {"indoor_only": True},
            date(2026, 6, 10): {"locale_lock": "home"},
        })
        sql, params = conn.calls[-1]
        assert "UPDATE athlete_event_windows" in sql
        stored = json.loads(params[0])
        assert list(stored.keys()) == ["2026-06-10", "2026-06-12"]  # sorted
        assert stored["2026-06-10"]["locale_lock"] == "home"
        assert stored["2026-06-12"]["indoor_only"] is True

    def test_writer_ignores_legacy_discipline_exclusions_and_minutes(self):
        # A caller still passing the dropped keys (e.g. stale client) doesn't
        # error; they're just not part of the stored shape.
        conn = _FakeConn()
        conn.queue_response(rows=[self._row()])
        update_event_window_restrictions_by_date(conn, 7, 1, {
            date(2026, 6, 10): {"max_total_minutes": 45,
                                "discipline_exclusions": ["D-012", "D-012"]},
        })
        _sql, params = conn.calls[-1]
        assert params[0] is None  # neither key is a real restriction → cleared

    def test_writer_drops_empty_day_and_clears_when_all_empty(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row()])
        update_event_window_restrictions_by_date(conn, 7, 1, {
            date(2026, 6, 11): {"indoor_only": False},
        })
        _sql, params = conn.calls[-1]
        assert params[0] is None  # no real restriction → cleared

    def test_writer_validates_locale_lock_exists(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row()])     # load_event_window
        conn.queue_response(rows=[])                # _locale_exists → not found
        with pytest.raises(EventWindowError):
            update_event_window_restrictions_by_date(
                conn, 7, 1, {date(2026, 6, 11): {"locale_lock": "ghost"}})

    def test_writer_rejects_date_outside_window(self):
        conn = _FakeConn()
        conn.queue_response(rows=[self._row()])
        with pytest.raises(EventWindowError):
            update_event_window_restrictions_by_date(
                conn, 7, 1, {date(2026, 6, 20): {"indoor_only": True}})


class TestVolumeHash:
    """A volume_pct (slider) change must invalidate the overlapping synthesis."""

    def _win(self, override_type, volume_pct=None):
        return EventWindow(
            id=1, user_id=7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type=override_type, unavailable_locale=None, away_locale=None,
            notes="", volume_pct=volume_pct,
        )

    def test_pct_change_changes_digest(self):
        a = compute_event_windows_hash([self._win("reduced_volume", 0.5)])
        b = compute_event_windows_hash([self._win("reduced_volume", 0.25)])
        assert a != b

    def test_no_training_vs_reduced_differ(self):
        a = compute_event_windows_hash([self._win("no_training")])
        b = compute_event_windows_hash([self._win("reduced_volume", 0.5)])
        assert a != b

    def test_volume_by_date_change_changes_digest(self):
        # #889 — a per-day level edit must invalidate the overlapping synthesis,
        # and an absent schedule stays byte-identical to the pre-#889 key.
        plain = self._win("reduced_volume", 0.5)
        sched_a = EventWindow(
            id=1, user_id=7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="reduced_volume", unavailable_locale=None, away_locale=None,
            notes="", volume_pct=0.5, volume_by_date={date(2026, 6, 1): 0.25},
        )
        sched_b = EventWindow(
            id=1, user_id=7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="reduced_volume", unavailable_locale=None, away_locale=None,
            notes="", volume_pct=0.5, volume_by_date={date(2026, 6, 1): 0.75},
        )
        h_plain = compute_event_windows_hash([plain])
        h_a = compute_event_windows_hash([sched_a])
        h_b = compute_event_windows_hash([sched_b])
        assert h_plain != h_a != h_b and h_plain != h_b
        # Empty schedule == no schedule (byte-identical key — regression guard).
        empty = EventWindow(
            id=1, user_id=7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="reduced_volume", unavailable_locale=None, away_locale=None,
            notes="", volume_pct=0.5, volume_by_date={},
        )
        assert compute_event_windows_hash([empty]) == h_plain


class TestWeekVolumeCapacity:
    """The per-week deterministic capacity factor (`_week_volume_capacity`)."""

    def _seg(self, start, end, volume_pct):
        return EventWindowSegment(
            start, end, (), {}, volume_pct=volume_pct,
        )

    def test_no_segment_is_identity(self):
        # Mon 2026-06-01 .. Sun 2026-06-07
        factor, no_train = _week_volume_capacity(
            date(2026, 6, 1), date(2026, 6, 7), set(), []
        )
        assert factor == 1.0 and no_train == 0

    def test_single_no_training_day_all_week_enabled(self):
        seg = self._seg(date(2026, 6, 3), date(2026, 6, 3), 0.0)  # one Wed
        factor, no_train = _week_volume_capacity(
            date(2026, 6, 1), date(2026, 6, 7), set(), [seg]
        )
        assert no_train == 1
        assert factor == pytest.approx(6 / 7)

    def test_single_reduced_day(self):
        seg = self._seg(date(2026, 6, 3), date(2026, 6, 3), 0.5)
        factor, no_train = _week_volume_capacity(
            date(2026, 6, 1), date(2026, 6, 7), set(), [seg]
        )
        assert no_train == 0
        assert factor == pytest.approx((6 + 0.5) / 7)

    def test_whole_week_no_training_is_zero(self):
        seg = self._seg(date(2026, 6, 1), date(2026, 6, 7), 0.0)
        factor, no_train = _week_volume_capacity(
            date(2026, 6, 1), date(2026, 6, 7), set(), [seg]
        )
        assert factor == 0.0 and no_train == 7

    def test_enabled_dows_restrict_the_denominator(self):
        # Only Mon/Wed/Fri enabled; a no_training Wed → 1 of 3 enabled days zeroed.
        seg = self._seg(date(2026, 6, 3), date(2026, 6, 3), 0.0)  # Wed
        factor, no_train = _week_volume_capacity(
            date(2026, 6, 1), date(2026, 6, 7), {"Mon", "Wed", "Fri"}, [seg]
        )
        assert no_train == 1
        assert factor == pytest.approx(2 / 3)

    def test_no_training_wins_over_reduced_on_same_day(self):
        # Two segments cover the same Wed; the most-reducing (0.0) wins.
        segs = [
            self._seg(date(2026, 6, 3), date(2026, 6, 3), 0.0),
            self._seg(date(2026, 6, 3), date(2026, 6, 3), 0.5),
        ]
        factor, no_train = _week_volume_capacity(
            date(2026, 6, 1), date(2026, 6, 7), set(), segs
        )
        assert no_train == 1
        assert factor == pytest.approx(6 / 7)


class TestVolumeOverlayRender:
    """The date-scoped overlay renders the in-transit directive for a volume
    segment (Trigger-#1 wording — owed Andy's sign-off at build)."""

    def test_no_training_segment_renders_directive(self):
        seg = EventWindowSegment(
            date(2026, 6, 10), date(2026, 6, 11),
            (EventWindowOverride("no_training"),), {}, volume_pct=0.0,
        )
        text = "\n".join(_format_event_window_overlay(
            [seg], date(2026, 6, 1), date(2026, 6, 14), None, {},
        ))
        assert "no training" in text
        assert "In-transit dates" in text  # the placement directive

    def test_reduced_volume_segment_shows_percent(self):
        seg = EventWindowSegment(
            date(2026, 6, 10), date(2026, 6, 11),
            (EventWindowOverride("reduced_volume", volume_pct=0.5),), {},
            volume_pct=0.5,
        )
        text = "\n".join(_format_event_window_overlay(
            [seg], date(2026, 6, 1), date(2026, 6, 14), None, {},
        ))
        assert "reduced volume" in text
        assert "50%" in text
