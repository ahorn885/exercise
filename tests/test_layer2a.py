"""Tests for `layer2a.builder.q_layer2a_discipline_classifier_payload`.

Coverage matches `Layer2A_Spec.md` §13 test scenarios + §10 edge cases:
- §4 input validation
- §13.1 AR baseline — disciplines + conditional D-015 → prompt_required
- §13.2 AR with override — `weight_override_divergence` flag fires
- §13.4 Triathlon — §5.1 D-17 strip logic (top_level=Triathlon, framework=sub-format)
- §10 unknown sport → empty disciplines + HITL + unresolved flag
- §10 override targeting non-sport-set discipline → silently ignored
- §5.3 conditional discipline (no override) → prompt_required + HITL

All tests use the `_FakeConn` / `_FakeCursor` pattern matching
`tests/test_race_events_repo.py` + `tests/test_layer1_builder.py`. The
spec §5.2 SQL is a single SELECT, so each test queues exactly one
response.
"""

from __future__ import annotations

from datetime import datetime

import pytest

# Pre-load layer4 to break the layer4.orchestrator → layer2a.builder → layer4.context
# circular import that otherwise blocks this module from collection. Mirrors
# `tests/test_layer3_cached_wrappers.py:30` precedent.
from layer4 import InMemoryCacheBackend  # noqa: F401

from layer2a import Layer2AInputError, q_layer2a_discipline_classifier_payload
from layer4.context import Layer2APayload


# ─── Fakes (mirror tests/test_race_events_repo.py) ───────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.commits: int = 0
        self.responses: list[tuple] = []

    def queue_response(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)

    def commit(self):
        self.commits += 1


# ─── Row fixture helper ──────────────────────────────────────────────────────


def _row(
    discipline_id: str,
    discipline_name: str,
    role: str,
    *,
    race_time_pct_low: float | None = None,
    race_time_pct_high: float | None = None,
    sport_specific_context: str | None = None,
    base_pct_low: float | None = None,
    base_pct_high: float | None = None,
    build_pct_low: float | None = None,
    build_pct_high: float | None = None,
    peak_pct_low: float | None = None,
    peak_pct_high: float | None = None,
    taper_pct_low: float | None = None,
    taper_pct_high: float | None = None,
    pla_role: str | None = None,
    notes_conditions: str | None = None,
    gap_type: str | None = None,
    gap_notes: str | None = None,
    multi_substitute_candidate: bool | None = None,
    discipline_category: str | None = None,
    primary_movement: str | None = None,
) -> dict:
    """Build a query-result row dict mirroring `_load_disciplines`'s
    SELECT list. PLA + DTG + disciplines columns default to None (LEFT
    JOIN miss)."""
    return {
        "discipline_id": discipline_id,
        "discipline_name": discipline_name,
        "applicability": "INCLUDED",
        "role": role,
        "discipline_category": discipline_category,
        "primary_movement": primary_movement,
        "race_time_pct_low": race_time_pct_low,
        "race_time_pct_high": race_time_pct_high,
        "sport_specific_context": sport_specific_context,
        "phase_load_text": None,
        "base_pct_low": base_pct_low,
        "base_pct_high": base_pct_high,
        "build_pct_low": build_pct_low,
        "build_pct_high": build_pct_high,
        "peak_pct_low": peak_pct_low,
        "peak_pct_high": peak_pct_high,
        "taper_pct_low": taper_pct_low,
        "taper_pct_high": taper_pct_high,
        "pla_role": pla_role,
        "notes_conditions": notes_conditions,
        "gap_type": gap_type,
        "gap_notes": gap_notes,
        "multi_substitute_candidate": multi_substitute_candidate,
    }


_DEFAULT_ETL = {"0A": "v19", "0B": "v15", "0C": "v7"}


# ─── §4 input validation ─────────────────────────────────────────────────────


class TestInputValidation:
    def test_empty_framework_sport_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2AInputError, match="non-empty"):
            q_layer2a_discipline_classifier_payload(
                conn, "", etl_version_set=_DEFAULT_ETL
            )

    def test_missing_etl_key_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2AInputError, match="etl_version_set"):
            q_layer2a_discipline_classifier_payload(
                conn, "Adventure Racing", etl_version_set={"0A": "v19", "0B": "v15"}
            )

    def test_non_dict_etl_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2AInputError, match="etl_version_set"):
            q_layer2a_discipline_classifier_payload(
                conn,
                "Adventure Racing",
                etl_version_set="v19",  # type: ignore[arg-type]
            )

    def test_negative_duration_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2AInputError, match="positive"):
            q_layer2a_discipline_classifier_payload(
                conn,
                "Adventure Racing",
                estimated_race_duration_hours=-1.0,
                etl_version_set=_DEFAULT_ETL,
            )

    def test_invalid_team_format_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2AInputError, match="team_format"):
            q_layer2a_discipline_classifier_payload(
                conn,
                "Adventure Racing",
                team_format="Mixed",
                etl_version_set=_DEFAULT_ETL,
            )


# ─── §13.1 AR baseline ───────────────────────────────────────────────────────


def _ar_rows() -> list[dict]:
    """Minimal AR fixture: a Primary, a Secondary, a Minor, the two
    conditional disciplines (D-010 whitewater + D-015 nav), and a
    Technical with a training gap. Six rows is sufficient for the
    behavioral surface — spec §13 doesn't require all 15."""
    return [
        _row(
            "D-001", "Trail Running", "Primary",
            race_time_pct_low=25, race_time_pct_high=40,
            sport_specific_context="Foundational endurance base.",
            base_pct_low=30, base_pct_high=40,
            build_pct_low=35, build_pct_high=45,
            peak_pct_low=30, peak_pct_high=40,
            taper_pct_low=20, taper_pct_high=30,
        ),
        _row(
            "D-006", "Mountain Biking", "Primary",
            race_time_pct_low=20, race_time_pct_high=30,
        ),
        _row(
            "D-008", "Packrafting", "Secondary",
            race_time_pct_low=10, race_time_pct_high=20,
        ),
        _row(
            "D-009", "Trekking with Pack", "Minor",
            race_time_pct_low=5, race_time_pct_high=10,
        ),
        _row(
            "D-010", "Kayaking", "Secondary",
            race_time_pct_low=5, race_time_pct_high=10,
        ),
        _row(
            "D-015", "Orienteering / Navigation", "Technical (*Conditional)",
            notes_conditions="*CONDITIONAL: included when navigation required",
        ),
        _row(
            "D-018", "Mountaineering", "Minor",
            race_time_pct_low=1, race_time_pct_high=3,
            gap_type="terrain_unavailable",
            gap_notes="Glacier terrain not accessible in MN.",
            multi_substitute_candidate=False,
        ),
    ]


class _FixedClock(datetime):
    """datetime subclass with a controllable utcnow() (only utcnow overridden)."""
    _now = datetime(2026, 5, 27, 6, 11, 31, 123456)

    @classmethod
    def utcnow(cls):
        return cls._now


class TestCacheKeyDeterminism:
    def test_generated_at_day_anchored_so_layer2a_hash_is_stable(self, monkeypatch):
        """Regression (D-77): `rationale_metadata.generated_at` is hashed into
        `layer2a_hash` (plan_create / per-block / race_week_brief keys). It must
        be day-granular so re-builds within a calendar day hash identically —
        a microsecond `utcnow()` made the cone re-run cold every pass."""
        from layer4.hashing import compute_payload_hash

        monkeypatch.setattr("layer2a.builder.datetime", _FixedClock)

        _FixedClock._now = datetime(2026, 5, 27, 6, 11, 31, 123456)
        conn1 = _FakeConn()
        conn1.queue_response(rows=_ar_rows())
        p1 = q_layer2a_discipline_classifier_payload(
            conn1,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            etl_version_set=_DEFAULT_ETL,
        )
        assert p1.rationale_metadata.generated_at == "2026-05-27T00:00:00"
        h1 = compute_payload_hash(p1)

        # Same calendar day, different wall-clock time → identical hash.
        _FixedClock._now = datetime(2026, 5, 27, 18, 45, 9, 987654)
        conn2 = _FakeConn()
        conn2.queue_response(rows=_ar_rows())
        p2 = q_layer2a_discipline_classifier_payload(
            conn2,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            etl_version_set=_DEFAULT_ETL,
        )
        assert compute_payload_hash(p2) == h1


class TestARBaseline:
    def test_56h_ar_baseline_disciplines(self):
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            etl_version_set=_DEFAULT_ETL,
        )

        assert isinstance(payload, Layer2APayload)
        assert payload.framework_sport == "Adventure Racing"
        assert len(payload.disciplines) == 7

        by_id = {d.discipline_id: d for d in payload.disciplines}

        # D-010 Kayaking: ordinary discipline post-R6 collapse (no longer a
        # whitewater duration-gated conditional).
        kayak = by_id["D-010"]
        assert kayak.inclusion == "included"
        assert kayak.is_conditional is False
        assert kayak.conditional_resolution is None

        # D-015 nav: conditional → prompt_required (race-rule auto-resolution retired)
        nav = by_id["D-015"]
        assert nav.inclusion == "prompt_required"
        assert nav.conditional_resolution == "athlete_opt_in"
        assert nav.is_conditional is True
        assert nav.sleep_deprivation_relevant is True

        # Primaries unconditional + included
        trail = by_id["D-001"]
        assert trail.inclusion == "included"
        assert trail.is_conditional is False
        assert trail.conditional_resolution is None
        # load_weight is normalized to a 0–1 distribution over the included
        # set (Layer4_Spec §4.2). Trail's raw 25–40 midpoint (32.5) is the
        # largest included band, so it carries the largest normalized share.
        included = [d for d in payload.disciplines if d.inclusion == "included"]
        assert sum(d.load_weight.value for d in included) == pytest.approx(1.0)
        assert trail.load_weight.value == max(d.load_weight.value for d in included)
        assert trail.load_weight.source == "system_default"
        assert "core discipline" in trail.rationale
        assert "25–40%" in trail.rationale
        assert "Foundational endurance" in trail.rationale  # sport_specific_context appended

        # Phase load surfaced where PLA row joined
        assert trail.phase_load is not None
        assert trail.phase_load.base_low == 30
        assert trail.phase_load.default_inclusion == "included"

        # D-008 secondary
        packraft = by_id["D-008"]
        assert "supporting discipline" in packraft.rationale

        # D-009 minor
        trek = by_id["D-009"]
        assert "minor discipline" in trek.rationale

        # HITL gate: D-015 nav is conditional → prompt_required → True
        assert payload.hitl_required is True
        assert payload.unresolved_flags == []

        # Coaching flags: 1 training_gap (D-018). Race-rule auto-resolution
        # retired, so no conditional_auto_resolved flag fires.
        flag_types = [f.flag_type for f in payload.coaching_flags]
        assert flag_types.count("training_gap") == 1
        assert "conditional_auto_resolved" not in flag_types

        # Training gaps summary
        assert payload.training_gaps_summary.flagged_count == 1
        assert payload.training_gaps_summary.any_no_substitute is False

        # ETL version set echoed
        assert payload.etl_version_set == _DEFAULT_ETL

        # Rationale metadata
        assert payload.rationale_metadata.template_version == "v1"
        assert payload.rationale_metadata.generated_at  # non-empty ISO string

        # Two queries: the per-discipline join + the per-phase weekly-total
        # hours fetch (`phase_load_weekly_totals`, used to convert the
        # per-discipline phase_load percentages into hours downstream).
        assert len(conn.calls) == 2
        sql, params = conn.calls[0]
        assert "layer0.sport_discipline_map" in sql
        assert "layer0.phase_load_allocation" in sql
        assert "layer0.discipline_training_gaps" in sql
        # disciplines join carries discipline_category + primary_movement
        assert "layer0.disciplines" in sql
        # D-05 standing filter present (psycopg2 `%%` escape — see Bucket
        # B #1, 2026-05-21 walkthrough)
        assert "NOT LIKE '%%WEEKLY TOTAL%%'" in sql
        assert "layer0.phase_load_weekly_totals" in conn.calls[1][0]
        # Params: top_level=AR, version_0a, framework_sport=AR (same — no
        # parens), then version_0a × 3 for the PLA / DTG / disciplines joins.
        assert params == ("Adventure Racing", "v19", "Adventure Racing", "v19", "v19", "v19")

    def test_discipline_category_and_primary_movement_plumb_through(self):
        # The layer0.disciplines join surfaces the terrain + movement axes
        # onto Layer2ADiscipline for downstream consumers (Layer 2E fueling).
        conn = _FakeConn()
        conn.queue_response(rows=[
            _row(
                "D-001", "Trail Running", "Primary",
                discipline_category="Foot / Running", primary_movement="running",
            ),
            _row("D-099", "Legacy Row", "Primary"),  # LEFT JOIN miss → NULLs
        ])
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            etl_version_set=_DEFAULT_ETL,
        )
        by_id = {d.discipline_id: d for d in payload.disciplines}
        assert by_id["D-001"].discipline_category == "Foot / Running"
        assert by_id["D-001"].primary_movement == "running"
        # Missing join row tolerated as NULL (legacy / unpopulated).
        assert by_id["D-099"].discipline_category is None
        assert by_id["D-099"].primary_movement is None


# ─── §13.2 AR override divergence ────────────────────────────────────────────


class TestAROverride:
    def test_override_above_50pct_relative_emits_flag(self):
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            athlete_discipline_overrides={"D-008": {"weight": 25.0}},
            etl_version_set=_DEFAULT_ETL,
        )

        by_id = {d.discipline_id: d for d in payload.disciplines}
        packraft = by_id["D-008"]
        assert packraft.load_weight.source == "athlete_override"
        # value + system_default are normalized (÷ included total) but their
        # ratio is preserved: raw override 25 vs raw default 15 (midpoint 10-20).
        assert (
            packraft.load_weight.value / packraft.load_weight.system_default
            == pytest.approx(25.0 / 15.0)
        )

        # Divergence: |25-15|/15 = 0.67 > 0.5 → flag fires
        divergence_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "weight_override_divergence"
        ]
        assert len(divergence_flags) == 1
        assert divergence_flags[0].discipline_id == "D-008"
        assert divergence_flags[0].metadata["override_pct"] == 25.0
        assert divergence_flags[0].metadata["default_pct"] == 15.0
        assert divergence_flags[0].metadata["divergence_relative"] > 0.5


# ─── §13.4 Triathlon D-17 strip logic ────────────────────────────────────────


class TestTriathlonD17:
    def test_sub_format_strip_for_sdm_full_name_for_pla(self):
        conn = _FakeConn()
        # Layer 0 returns 3 Triathlon disciplines (swim/bike/run); fixture
        # doesn't need real PLA bands — just verifies the param splitting.
        conn.queue_response(rows=[
            _row("D-002", "Open Water Swimming", "Primary",
                 race_time_pct_low=15, race_time_pct_high=20),
            _row("D-004", "Road Cycling", "Primary",
                 race_time_pct_low=50, race_time_pct_high=55),
            _row("D-001", "Road Running", "Primary",
                 race_time_pct_low=25, race_time_pct_high=30),
        ])
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Triathlon (Standard / Olympic)",
            etl_version_set=_DEFAULT_ETL,
        )

        assert len(payload.disciplines) == 3
        assert payload.framework_sport == "Triathlon (Standard / Olympic)"

        # Params: SDM gets stripped top-level "Triathlon"; PLA gets full
        # sub-format name "Triathlon (Standard / Olympic)".
        sql, params = conn.calls[0]
        assert params[0] == "Triathlon"  # top_level_sport
        assert params[1] == "v19"
        assert params[2] == "Triathlon (Standard / Olympic)"  # framework_sport for PLA
        assert params[3] == "v19"
        assert params[4] == "v19"

    def test_sport_without_parens_not_stripped(self):
        """AR has no parens — both SDM + PLA lookups use the full name."""
        conn = _FakeConn()
        conn.queue_response(rows=[])
        q_layer2a_discipline_classifier_payload(
            conn, "Adventure Racing", etl_version_set=_DEFAULT_ETL,
        )
        sql, params = conn.calls[0]
        assert params[0] == "Adventure Racing"
        assert params[2] == "Adventure Racing"

    def test_non_whitelisted_parens_not_stripped(self):
        """Defensive: only sports in `_SUB_FORMAT_SPORTS` get stripped.
        A hypothetical sport with parens not in the whitelist keeps the
        full name for both lookups."""
        conn = _FakeConn()
        conn.queue_response(rows=[])
        q_layer2a_discipline_classifier_payload(
            conn,
            "Some New Sport (Variant)",
            etl_version_set=_DEFAULT_ETL,
        )
        sql, params = conn.calls[0]
        # Both lookups carry the full name — no false-positive strip
        assert params[0] == "Some New Sport (Variant)"
        assert params[2] == "Some New Sport (Variant)"


# ─── §10 edge cases ──────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_unknown_sport_yields_hitl_and_unresolved_flag(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])  # SDM has no rows for this sport
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Underwater Basket Weaving",
            etl_version_set=_DEFAULT_ETL,
        )

        assert payload.disciplines == []
        assert payload.hitl_required is True
        assert len(payload.unresolved_flags) == 1
        assert payload.unresolved_flags[0].raw_input == "Underwater Basket Weaving"
        assert payload.unresolved_flags[0].severity == "error"
        assert payload.training_gaps_summary.flagged_count == 0
        assert payload.coaching_flags == []

    def test_override_targeting_unmapped_discipline_is_ignored(self):
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            athlete_discipline_overrides={"D-999": {"weight": 99.0}},  # not in AR
            etl_version_set=_DEFAULT_ETL,
        )

        # Sport's canonical list wins per §10. Override silently ignored;
        # no D-999 discipline appears, no failure raised.
        by_id = {d.discipline_id: d for d in payload.disciplines}
        assert "D-999" not in by_id
        # No spurious divergence flag from the unmapped override
        assert not any(
            f.flag_type == "weight_override_divergence" and f.discipline_id == "D-999"
            for f in payload.coaching_flags
        )

    def test_conditional_discipline_is_prompt_required(self):
        """§10: a conditional discipline with no athlete override resolves to
        `prompt_required` and sets `hitl_required=True`."""
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=None,
            etl_version_set=_DEFAULT_ETL,
        )

        by_id = {d.discipline_id: d for d in payload.disciplines}
        # D-010 Kayaking: ordinary discipline → included regardless of signals.
        assert by_id["D-010"].inclusion == "included"
        # D-015: conditional with no override → prompt_required, athlete_opt_in
        assert by_id["D-015"].inclusion == "prompt_required"
        assert by_id["D-015"].conditional_resolution == "athlete_opt_in"
        # HITL fires
        assert payload.hitl_required is True
        # Rationale prompts the athlete to confirm
        assert "Confirm whether" in by_id["D-015"].rationale


# ─── _load_disciplines psycopg2 %% escape (Bucket B #1 2026-05-21) ──────────


class TestLoadDisciplinesPercentEscape:
    """The PLA `discipline_name NOT LIKE '%WEEKLY TOTAL%'` clause must
    use `%%` to survive psycopg2's parameter substitution. A bare `%`
    inside the SQL collides with `%s` placeholder parsing and raises
    `IndexError: tuple index out of range` on every plan-gen POST.
    Production-only failure (test substrate mocks `db.execute` and never
    hits the parser).
    """

    def test_sql_escapes_like_pattern_with_double_percent(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])  # empty SDM → exits via §10 unknown-sport path

        q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            etl_version_set=_DEFAULT_ETL,
        )

        assert conn.calls, "expected _load_disciplines to issue exactly one SELECT"
        sql, _params = conn.calls[0]
        assert "%%WEEKLY TOTAL%%" in sql, (
            "LIKE pattern must use %% to survive psycopg2 substitution"
        )
        assert "'%WEEKLY TOTAL%'" not in sql, (
            "bare '%' in the LIKE pattern triggers IndexError under psycopg2"
        )


class TestDisciplineIdFilter:
    """D-73 Phase 5.2 Bucket E.(b)-B2 — race-level `discipline_id_filter`
    narrows the bridge-derived discipline list to an explicit subset
    while preserving rationale + phase_load + training_gap on the
    surviving rows. None = full bridge defaults (pre-B2 behavior).
    """

    def test_none_filter_returns_full_bridge_list(self):
        """`discipline_id_filter=None` (default) reproduces pre-B2 output:
        all bridge rows survive."""
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            etl_version_set=_DEFAULT_ETL,
        )
        ids = {d.discipline_id for d in payload.disciplines}
        # _ar_rows seeds 7 disciplines; full set surfaces.
        assert len(payload.disciplines) == 7
        assert "D-001" in ids and "D-010" in ids and "D-015" in ids

    def test_subset_filter_narrows_disciplines(self):
        """`discipline_id_filter=["D-001","D-015"]` keeps only those two
        from the bridge-derived 7. Surviving rows retain their rationale,
        phase_load, conditional_resolution."""
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            discipline_id_filter=["D-001", "D-015"],
            etl_version_set=_DEFAULT_ETL,
        )
        ids = [d.discipline_id for d in payload.disciplines]
        assert ids == ["D-001", "D-015"]
        # Phase load preserved on surviving rows
        by_id = {d.discipline_id: d for d in payload.disciplines}
        assert by_id["D-001"].phase_load is not None
        assert by_id["D-001"].phase_load.base_low == 30
        # Conditional resolution preserved
        assert by_id["D-015"].conditional_resolution == "athlete_opt_in"

    def test_empty_filter_returns_no_disciplines(self):
        """`discipline_id_filter=[]` is the explicit "no disciplines"
        case (callers that supply an empty list — distinct from None).
        Hits the same unresolved-sport edge case as an unknown sport."""
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            discipline_id_filter=[],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.disciplines == []
        # Layer 2A's existing unresolved-sport behavior surfaces:
        assert payload.hitl_required is True
        assert len(payload.unresolved_flags) == 1
        assert payload.unresolved_flags[0].raw_input == "Adventure Racing"

    def test_filter_with_nonexistent_ids_silently_drops(self):
        """`discipline_id_filter=["D-999"]` — IDs not in the bridge are
        silently dropped (no crash). Defensive against stale UI state."""
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            discipline_id_filter=["D-999"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.disciplines == []

    def test_filter_preserves_phase_load_and_training_gap(self):
        """Surviving rows keep their PLA + DTG columns intact. The filter
        is a post-prune over the existing SELECT result — it doesn't
        re-query or strip metadata."""
        conn = _FakeConn()
        conn.queue_response(rows=_ar_rows())
        payload = q_layer2a_discipline_classifier_payload(
            conn,
            "Adventure Racing",
            estimated_race_duration_hours=56.0,
            discipline_id_filter=["D-018"],  # the row with a training_gap
            etl_version_set=_DEFAULT_ETL,
        )
        assert len(payload.disciplines) == 1
        d = payload.disciplines[0]
        assert d.discipline_id == "D-018"
        assert d.training_gap is not None
