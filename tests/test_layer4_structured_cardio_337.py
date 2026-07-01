"""#337 — Layer 4 structured cardio prescription.

Covers the shared, path-neutral pieces: the `format_measured_physiology`
render helper (the Layer-1 physiological anchors the synthesizer grounds
`intensity_target` numbers in) and the presence of the ratified
`# Cardio programming` section in the plan-create (per_phase) system prompt.
The single_session + plan_refresh path wiring is covered in
`tests/test_layer4_single_session.py` / `tests/test_layer4_plan_refresh.py`.
"""

from types import SimpleNamespace

from layer4.per_phase import (
    CARDIO_PROGRAMMING_PROMPT_SECTION,
    SYSTEM_PROMPT,
    _fmt_pace_mmss,
    format_measured_physiology,
    format_terrain_gap_detail,
    format_upstream_coaching_flags,
)


def _flag(flag_type, message, **scope):
    """Duck-typed stand-in for the Layer 2 coaching-flag models — the render
    helper only reads `.flag_type` / `.message` and probes scope fields via
    getattr, so a SimpleNamespace exercises it without the pydantic payloads."""
    return SimpleNamespace(flag_type=flag_type, message=message, **scope)


def _payload(*flags):
    return SimpleNamespace(coaching_flags=list(flags))


class TestFmtPaceMmss:
    def test_round_minute(self):
        assert _fmt_pace_mmss(240) == "4:00"

    def test_zero_pads_seconds(self):
        assert _fmt_pace_mmss(245) == "4:05"

    def test_sub_minute(self):
        assert _fmt_pace_mmss(58) == "0:58"


class TestFormatMeasuredPhysiology:
    def test_empty_when_no_performance_key(self):
        assert format_measured_physiology({}) == []
        assert format_measured_physiology({"experience_level": "advanced"}) == []

    def test_empty_when_all_anchors_null(self):
        assert (
            format_measured_physiology(
                {"performance": {"hrmax_bpm": None, "cycling_ftp_w": None}}
            )
            == []
        )

    def test_hr_only(self):
        lines = format_measured_physiology(
            {"performance": {"hrmax_bpm": 188, "lactate_threshold_hr_bpm": 168}}
        )
        assert lines[0].startswith("Measured physiology")
        assert lines[1] == "- HR max 188 bpm · LT-HR 168 bpm"
        # no second (power/pace) line when none of those anchors are set
        assert len(lines) == 2

    def test_full_set_renders_both_lines(self):
        lines = format_measured_physiology(
            {
                "performance": {
                    "hrmax_bpm": 188,
                    "lactate_threshold_hr_bpm": 168,
                    "cycling_ftp_w": 245,
                    "running_threshold_pace_sec_per_km": 245,
                    "css_swim_sec_per_100m": 98,
                }
            }
        )
        assert lines[1] == "- HR max 188 bpm · LT-HR 168 bpm"
        assert lines[2] == (
            "- cycling FTP 245 W · run threshold pace 4:05 /km · swim CSS 1:38 /100m"
        )

    def test_partial_power_pace_only(self):
        lines = format_measured_physiology(
            {"performance": {"cycling_ftp_w": 300}}
        )
        # no HR line, just the power/pace line under the header
        assert lines == [
            "Measured physiology (ground intensity targets in these where present):",
            "- cycling FTP 300 W",
        ]


class TestFormatUpstreamCoachingFlags:
    """#307 — the generic upstream coaching_flags render block (Layers
    2A/2B/2C/2D). Suppress-on-empty, per-layer label, scope rendering, and
    de-dup of per-locale 2C flags."""

    def test_empty_when_no_payloads(self):
        assert format_upstream_coaching_flags() == []

    def test_empty_when_all_flag_lists_empty(self):
        assert (
            format_upstream_coaching_flags(
                layer2a=_payload(), layer2d=_payload()
            )
            == []
        )

    def test_injury_flag_renders_with_label_and_header(self):
        lines = format_upstream_coaching_flags(
            layer2d=_payload(
                _flag(
                    "multi_body_part_load_concern",
                    "You have 3 active injuries.",
                )
            )
        )
        assert lines[0].startswith("Upstream coaching flags")
        assert lines[1] == "- [injury] multi_body_part_load_concern: You have 3 active injuries."

    def test_discipline_name_preferred_over_id_in_scope(self):
        lines = format_upstream_coaching_flags(
            layer2d=_payload(
                _flag(
                    "elevated_discipline_risk",
                    "Elevated risk.",
                    discipline_id="D-001",
                    discipline_name="Trail Running",
                )
            )
        )
        assert lines[1] == "- [injury] elevated_discipline_risk (Trail Running): Elevated risk."

    def test_discipline_id_used_when_no_name(self):
        lines = format_upstream_coaching_flags(
            layer2a=_payload(_flag("foo", "bar", discipline_id="D-009"))
        )
        assert lines[1] == "- [discipline] foo (D-009): bar"

    def test_terrain_scope_rendered(self):
        lines = format_upstream_coaching_flags(
            layer2b=_payload(
                _flag("race_terrain_unset", "Terrain missing.", target_terrain_id="TRN-3")
            )
        )
        assert lines[1] == "- [terrain] race_terrain_unset (TRN-3): Terrain missing."

    def test_per_locale_2c_flags_deduped(self):
        # Same flag emitted across two locale payloads collapses to one line.
        dup = _flag("equipment_gap", "No pool nearby.")
        lines = format_upstream_coaching_flags(
            layer2c_payloads=[_payload(dup), _payload(_flag("equipment_gap", "No pool nearby."))]
        )
        flag_lines = [ln for ln in lines if ln.startswith("- ")]
        assert flag_lines == ["- [equipment] equipment_gap: No pool nearby."]

    def test_multiple_layers_ordered_by_source(self):
        lines = format_upstream_coaching_flags(
            layer2a=_payload(_flag("a_flag", "a")),
            layer2b=_payload(_flag("b_flag", "b")),
            layer2c_payloads=[_payload(_flag("c_flag", "c"))],
            layer2d=_payload(_flag("d_flag", "d")),
        )
        labels = [ln.split("]")[0] for ln in lines if ln.startswith("- ")]
        assert labels == ["- [discipline", "- [terrain", "- [equipment", "- [injury"]


def _gap(target_terrain_name, uncoverable_stimulus=None, proxy_methods=None):
    """Duck-typed stand-in for `TerrainGap` — the render helper only reads
    `.target_terrain_name` / `.uncoverable_stimulus` / `.proxy_methods`."""
    return SimpleNamespace(
        target_terrain_name=target_terrain_name,
        uncoverable_stimulus=uncoverable_stimulus or [],
        proxy_methods=proxy_methods or [],
    )


def _discipline_block(*gaps):
    return SimpleNamespace(terrain_gaps=list(gaps))


def _layer2b(*blocks):
    return SimpleNamespace(terrain_by_discipline=list(blocks))


class TestFormatTerrainGapDetail:
    """T-2.3 — surfaces `TerrainGap.uncoverable_stimulus` / `.proxy_methods`
    (Layer 2B `terrain_by_discipline[i].terrain_gaps`). Suppress-on-empty."""

    def test_none_payload_returns_empty(self):
        assert format_terrain_gap_detail(None) == []

    def test_no_discipline_blocks_returns_empty(self):
        assert format_terrain_gap_detail(_layer2b()) == []

    def test_gap_with_no_stimulus_or_proxy_suppressed(self):
        payload = _layer2b(_discipline_block(_gap("Singletrack climb")))
        assert format_terrain_gap_detail(payload) == []

    def test_gap_with_data_renders_header_and_detail_line(self):
        payload = _layer2b(
            _discipline_block(
                _gap(
                    "Singletrack climb",
                    uncoverable_stimulus=["technical descent handling"],
                    proxy_methods=["hill repeats", "balance drills"],
                )
            )
        )
        lines = format_terrain_gap_detail(payload)
        assert lines[0].startswith("Terrain-gap detail")
        assert lines[1] == (
            "- Singletrack climb — can't replicate locally: technical descent "
            "handling — compensate via: hill repeats, balance drills"
        )

    def test_stimulus_only_no_proxy_methods(self):
        payload = _layer2b(
            _discipline_block(
                _gap("Altitude", uncoverable_stimulus=["hypoxic stress"])
            )
        )
        lines = format_terrain_gap_detail(payload)
        assert lines[1] == "- Altitude — can't replicate locally: hypoxic stress"

    def test_multiple_discipline_blocks_and_gaps(self):
        payload = _layer2b(
            _discipline_block(
                _gap("Sand", uncoverable_stimulus=["sand traction loss"]),
                _gap("Flat", uncoverable_stimulus=[], proxy_methods=[]),
            ),
            _discipline_block(
                _gap("Cobbles", proxy_methods=["gravel rides"]),
            ),
        )
        lines = format_terrain_gap_detail(payload)
        detail_lines = [ln for ln in lines if ln.startswith("- ")]
        assert detail_lines == [
            "- Sand — can't replicate locally: sand traction loss",
            "- Cobbles — compensate via: gravel rides",
        ]


class TestCardioProgrammingSection:
    def test_section_in_per_phase_system_prompt(self):
        assert CARDIO_PROGRAMMING_PROMPT_SECTION in SYSTEM_PROMPT

    def test_section_covers_structure_and_grounding(self):
        body = CARDIO_PROGRAMMING_PROMPT_SECTION.lower()
        # item 1 — warm-up / work / cool-down structure
        assert "warm-up" in body and "cool-down" in body
        # item 3 — ground targets in measured physiology with a fallback
        assert "measured physiology" in body
        assert "rpetarget" in body  # the explicit fallback when an anchor is absent
