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

from datetime import date
from types import SimpleNamespace

import pytest

from athlete_event_windows_repo import (
    EventWindow,
    EventWindowError,
    add_event_window,
    delete_event_window,
    load_event_windows,
)
from layer4.hashing import (
    compute_event_windows_hash,
    plan_create_key,
    plan_refresh_key,
)
from layer4.orchestrator import (
    _FeasibilityInputs,
    _build_event_window_overlay,
    _reduced_env,
    _resolve_included_feasibility,
)
from layer4.per_phase import _format_event_window_overlay
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
        group_kind_by_group={},
        pool_by_discipline=pool_by_discipline or {},
        gated={},
        included=[SimpleNamespace(discipline_id=d) for d in disciplines],
        name_by_discipline={d: d for d in disciplines},
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
            EventWindow(1, 7, date(2026, 6, 10), date(2026, 6, 12), "indoor_only", None, ""),
            # locale_unavailable on a non-cluster locale → no-op → dropped
            EventWindow(2, 7, date(2026, 6, 20), date(2026, 6, 22),
                        "locale_unavailable", "ghost", ""),
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
            EventWindow(1, 7, date(2026, 9, 1), date(2026, 9, 5), "indoor_only", None, ""),
        ]
        self._patch(monkeypatch, fi, windows)
        segments, overlapping = _build_event_window_overlay(
            None, 7, None,
            plan_start=date(2026, 6, 1), plan_end=date(2026, 6, 30),
            home_feasibility={},
        )
        assert segments == [] and overlapping == []


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


# ─── hashing + cache-key regression ──────────────────────────────────────────

class TestHashAndKey:
    def _win(self, ot="indoor_only", loc=None):
        return EventWindow(1, 7, date(2026, 6, 10), date(2026, 6, 12), ot, loc, "")

    def test_hash_order_independent_and_nonempty(self):
        a = self._win("indoor_only")
        b = self._win("locale_unavailable", "park")
        assert compute_event_windows_hash([a, b]) == compute_event_windows_hash([b, a])
        assert compute_event_windows_hash([]) != compute_event_windows_hash([a])

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


# ─── repo: app-layer validation ──────────────────────────────────────────────

class TestRepo:
    def test_load_coerces_dates_and_orders(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {"id": 1, "user_id": 7, "start_date": "2026-06-10",
             "end_date": "2026-06-12", "override_type": "indoor_only",
             "unavailable_locale": None, "notes": ""},
        ])
        windows = load_event_windows(conn, 7)
        assert windows[0].start_date == date(2026, 6, 10)
        assert isinstance(windows[0].start_date, date)
        assert "ORDER BY start_date" in conn.calls[0][0]

    def test_add_rejects_unknown_override_type(self):
        conn = _FakeConn()
        with pytest.raises(EventWindowError):
            add_event_window(
                conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
                override_type="away",
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
        add_event_window(
            conn, 7, start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
            override_type="locale_unavailable", unavailable_locale="park", notes="x",
        )
        insert = conn.calls[-1]
        assert "INSERT INTO athlete_event_windows" in insert[0]
        assert insert[1] == (7, date(2026, 6, 1), date(2026, 6, 2),
                             "locale_unavailable", "park", "x")

    def test_indoor_only_clears_stray_locale(self):
        conn = _FakeConn()
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
