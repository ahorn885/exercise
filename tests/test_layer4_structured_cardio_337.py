"""#337 — Layer 4 structured cardio prescription.

Covers the shared, path-neutral pieces: the `format_measured_physiology`
render helper (the Layer-1 physiological anchors the synthesizer grounds
`intensity_target` numbers in) and the presence of the ratified
`# Cardio programming` section in the plan-create (per_phase) system prompt.
The single_session + plan_refresh path wiring is covered in
`tests/test_layer4_single_session.py` / `tests/test_layer4_plan_refresh.py`.
"""

from layer4.per_phase import (
    CARDIO_PROGRAMMING_PROMPT_SECTION,
    SYSTEM_PROMPT,
    _fmt_pace_mmss,
    format_measured_physiology,
)


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
