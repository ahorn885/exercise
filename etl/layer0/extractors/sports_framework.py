"""Layer 0 ETL — extractor for Sports_Framework_v6.xlsx (source 0A).

One function per sheet. Each returns a list of dicts ready for INSERT.
Parsing rules per spec §4.2–§4.8.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# en-dash (–) and hyphen-minus (-) both observed in source data
_DASH = r"[–\-]"

_PACK_WEIGHT_RE = re.compile(rf"(\d+)(?:\s*{_DASH}\s*(\d+))?\s*lb", re.IGNORECASE)
_WEEKS_RE = re.compile(rf"(\d+)(?:\s*{_DASH}\s*(\d+))?\s*weeks?", re.IGNORECASE)
_PCT_RE = re.compile(rf"(\d+(?:\.\d+)?)(?:\s*{_DASH}\s*(\d+(?:\.\d+)?))?\s*%")

# Age band header markers — used to slice the age_adjusted_ramp text
# into per-band sections. The text format is consistently
#   "40–44: ...\n45–54: ...\n55+: ..."
# but some disciplines use just "40-44:" or "Standard ramp" globally.
_AGE_BANDS = (
    ("40_44", re.compile(rf"40\s*{_DASH}\s*44\s*:")),
    ("45_54", re.compile(rf"45\s*{_DASH}\s*54\s*:")),
    ("55_plus", re.compile(r"55\s*\+\s*:")),
)


def _parse_pack_weight(text: str | None) -> tuple[float | None, float | None]:
    """Extract (low, high) lb values from pack carry notes."""
    if not text:
        return None, None
    m = _PACK_WEIGHT_RE.search(text)
    if not m:
        return None, None
    low = float(m.group(1))
    high = float(m.group(2)) if m.group(2) else low
    return low, high


def _parse_weeks(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None
    m = _WEEKS_RE.search(text)
    if not m:
        return None, None
    low = int(m.group(1))
    high = int(m.group(2)) if m.group(2) else low
    return low, high


def _parse_race_time_pct(text: str | None) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    m = _PCT_RE.search(text)
    if not m:
        return None, None
    low = float(m.group(1))
    high = float(m.group(2)) if m.group(2) else low
    return low, high


def _parse_age_ramps(text: str | None) -> dict[str, float | None]:
    """Slice the age-adjusted ramp text into 3 bands; extract the first %
    value from each band's slice. Returns NULLs for bands that say
    "Standard ramp" or otherwise have no % token."""
    out = {"40_44": None, "45_54": None, "55_plus": None}
    if not text:
        return out

    # Find each band header start; use them as slice boundaries.
    positions: list[tuple[str, int]] = []
    for key, pat in _AGE_BANDS:
        m = pat.search(text)
        if m:
            positions.append((key, m.end()))

    if not positions:
        return out
    positions.sort(key=lambda x: x[1])
    for i, (key, start) in enumerate(positions):
        end = positions[i + 1][1] if i + 1 < len(positions) else len(text)
        slice_text = text[start:end]
        m = _PCT_RE.search(slice_text)
        if m:
            out[key] = float(m.group(1))
    return out


def _split_dot_list(text: str | None) -> list[str]:
    """Split a ` · `-delimited list, trim entries, drop empties."""
    if not text:
        return []
    return [p.strip() for p in str(text).split(" · ") if p.strip()]


def _parse_recovery_modalities(text: str | None) -> list[str]:
    """Col 11 is a numbered list:
        '1. Sleep (8+ hrs)\n2. CWI lower body (11–15°C, 10–15 min)\n3. ...'
    Extract each item after the digit-and-period prefix.
    """
    if not text:
        return []
    items: list[str] = []
    for line in str(text).splitlines():
        m = re.match(r"^\s*\d+[.)]\s*(.+?)\s*$", line)
        if m:
            items.append(m.group(1))
    return items


def _parse_yes_no(text: str | None) -> tuple[bool, str]:
    """Parse a 'YES/NO — explanation' cell.

    Returns (flag_bool, full_text).
    """
    if text is None:
        return False, ""
    s = str(text).strip()
    if not s:
        return False, ""
    # First whitespace-delimited token, stripping a trailing dash separator
    head = re.split(r"[\s—–\-]", s, maxsplit=1)[0].strip().upper()
    flag = head == "YES"
    return flag, s


def _i(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _t(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# ---------------------------------------------------------------------------
# Sheet extractors
# ---------------------------------------------------------------------------

def open_workbook(path: str | Path):
    return load_workbook(str(path), read_only=False, data_only=True)


def extract_sports(ws: Worksheet) -> list[dict[str, Any]]:
    """Sheet 1 — Sports Index. Header on R1, data R2+."""
    rows: list[dict[str, Any]] = []
    for r in range(2, ws.max_row + 1):
        sport = _t(ws.cell(row=r, column=1).value)
        if not sport:
            continue
        nav_text = ws.cell(row=r, column=6).value
        sleep_text = ws.cell(row=r, column=7).value
        pack_text = ws.cell(row=r, column=8).value
        trans_text = ws.cell(row=r, column=9).value

        flag_nav, nav_full = _parse_yes_no(nav_text)
        flag_sleep, sleep_full = _parse_yes_no(sleep_text)
        flag_pack, pack_full = _parse_yes_no(pack_text)
        flag_trans, trans_full = _parse_yes_no(trans_text)
        pack_low, pack_high = _parse_pack_weight(pack_full) if flag_pack else (None, None)

        rows.append({
            "sport_name": sport,
            "typical_duration_range": _t(ws.cell(row=r, column=4).value),
            "team_vs_solo": _t(ws.cell(row=r, column=5).value),
            "flag_navigation": flag_nav,
            "navigation_notes": nav_full or None,
            "flag_sleep_deprivation": flag_sleep,
            "sleep_deprivation_notes": sleep_full or None,
            "flag_pack_carry": flag_pack,
            "pack_carry_notes": pack_full or None,
            "pack_weight_lbs_low": pack_low,
            "pack_weight_lbs_high": pack_high,
            "flag_transition_training": flag_trans,
            "transition_training_notes": trans_full or None,
            "primary_discipline_count": _i(ws.cell(row=r, column=10).value),
            "secondary_discipline_count": _i(ws.cell(row=r, column=11).value),
            "status_label": _t(ws.cell(row=r, column=12).value),
        })
    return rows


def extract_disciplines(ws: Worksheet) -> list[dict[str, Any]]:
    """Sheet 2 — Discipline Library. Header R1, data R2+."""
    rows: list[dict[str, Any]] = []
    for r in range(2, ws.max_row + 1):
        did = _t(ws.cell(row=r, column=1).value)
        if not did or not did.startswith("D-"):
            continue
        min_base_text = _t(ws.cell(row=r, column=5).value)
        weeks_low, weeks_high = _parse_weeks(min_base_text)
        age_text = _t(ws.cell(row=r, column=8).value)
        age = _parse_age_ramps(age_text)

        recovery_text = _t(ws.cell(row=r, column=12).value)
        rows.append({
            "discipline_id": did,
            "discipline_name": _t(ws.cell(row=r, column=2).value) or did,
            "discipline_category": _t(ws.cell(row=r, column=3).value),
            "min_base_phase_text": min_base_text,
            "min_base_phase_weeks_low": weeks_low,
            "min_base_phase_weeks_high": weeks_high,
            "periodization_text": _t(ws.cell(row=r, column=6).value),
            "ramp_text": _t(ws.cell(row=r, column=7).value),
            "age_adjusted_ramp_text": age_text,
            "age_ramp_40_44_pct": age["40_44"],
            "age_ramp_45_54_pct": age["45_54"],
            "age_ramp_55_plus_pct": age["55_plus"],
            "taper_norms_text": _t(ws.cell(row=r, column=9).value),
            "common_injury_patterns": _split_dot_list(ws.cell(row=r, column=10).value),
            "injury_preceding_behaviors": _split_dot_list(ws.cell(row=r, column=11).value),
            "recovery_priority_text": recovery_text,
            "recovery_modalities": _parse_recovery_modalities(recovery_text),
            "evidence_quality_text": _t(ws.cell(row=r, column=13).value),
        })
    return rows


def extract_sport_discipline_map(
    ws: Worksheet,
    dropped_dupes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Sheet 3 — Sport × Discipline Map. Header R1, data R2+.

    Dedupes by `(sport_name, discipline_id)` to satisfy the spec's UNIQUE
    constraint. First-seen wins. The source has three known duplicate
    keys as of v6 — one true duplicate (Triathlon D-002 listed twice
    identically) and two genuine sub-format splits where multiple
    disciplines share a `discipline_id` (Long Distance / Endurance
    Cycling D-005 and D-006). Dropped rows are appended to
    `dropped_dupes` if provided, for surfacing in the report.
    """
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for r in range(2, ws.max_row + 1):
        sport = _t(ws.cell(row=r, column=1).value)
        did = _t(ws.cell(row=r, column=2).value)
        if not sport or not did:
            continue
        race_text = _t(ws.cell(row=r, column=6).value)
        race_low, race_high = _parse_race_time_pct(race_text)
        row = {
            "sport_name": sport,
            "discipline_id": did,
            "discipline_name": _t(ws.cell(row=r, column=3).value) or did,
            "applicability": _t(ws.cell(row=r, column=4).value) or "INCLUDED",
            "role": _t(ws.cell(row=r, column=5).value) or "",
            "race_time_pct_text": race_text,
            "race_time_pct_low": race_low,
            "race_time_pct_high": race_high,
            "sport_specific_context": _t(ws.cell(row=r, column=7).value),
            "b2b_pairing_rule_text": _t(ws.cell(row=r, column=8).value),
            "phase_load_text": _t(ws.cell(row=r, column=9).value),
        }
        key = (sport, did)
        if key in seen:
            if dropped_dupes is not None:
                dropped_dupes.append({
                    "row_number": r,
                    "sport_name": sport,
                    "discipline_id": did,
                    "discipline_name": row["discipline_name"],
                    "role": row["role"],
                })
            continue
        seen.add(key)
        rows.append(row)
    return rows


def extract_discipline_pairing_matrix(ws: Worksheet) -> list[dict[str, Any]]:
    """Sheet 4 — primary matrix. Header on R10; data R11–R27.

    R29–R37 are commentary rationales — not turned into pairing rows.
    """
    rows: list[dict[str, Any]] = []
    rating_map = {
        "PRE": "PREFERRED",
        "ACC": "ACCEPTABLE",
        "AVO": "AVOID",
        "IMP": "IMPRACTICAL",
        "N/A": "N/A",
        "PREFERRED": "PREFERRED",
        "ACCEPTABLE": "ACCEPTABLE",
        "AVOID": "AVOID",
        "IMPRACTICAL": "IMPRACTICAL",
    }

    # Read header row R10 to extract destination D-IDs
    header_ids: list[str | None] = [None]  # col 1 is "FROM" label
    for c in range(2, ws.max_column + 1):
        val = _t(ws.cell(row=10, column=c).value)
        # Header cell looks like "D-001\nTrail Run"
        m = re.search(r"(D-\d+)", val or "")
        header_ids.append(m.group(1) if m else None)

    for r in range(11, 28):
        first = _t(ws.cell(row=r, column=1).value)
        if not first:
            continue
        m = re.match(r"(D-\d+)", first)
        if not m:
            continue
        from_id = m.group(1)
        for c in range(2, ws.max_column + 1):
            to_id = header_ids[c - 1]
            if not to_id:
                continue
            cell = _t(ws.cell(row=r, column=c).value)
            if not cell:
                continue
            rating = rating_map.get(cell.upper(), cell.upper())
            rows.append({
                "discipline_id_a": from_id,
                "discipline_id_b": to_id,
                "pairing_rating": rating,
                "rationale": None,
                "source": "matrix",
            })
    return rows


def extract_pairing_b2b_fallback(
    sport_discipline_rows: list[dict[str, Any]],
    discipline_name_to_id: dict[str, str],
    matrix_pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Parse Sheet 3 col 7 `b2b_pairing_rule_text` per spec §4.6 (3).

    Each line is `→ {discipline_name}: {RATING}` or
    `→ {discipline_name}: {RATING} ({rationale})`.

    Skips pairs already present in the matrix (matrix wins).
    """
    rows: list[dict[str, Any]] = []
    pat = re.compile(
        r"→\s*(?P<dest>[^:]+?)\s*:\s*"
        r"(?P<rating>PREFERRED|ACCEPTABLE|AVOID|IMPRACTICAL|N/A)"
        r"(?:\s*\((?P<rat>[^)]+)\))?",
        re.IGNORECASE,
    )
    seen: set[tuple[str, str]] = set()

    # build name→id map case-insensitive
    name_lookup = {k.lower(): v for k, v in discipline_name_to_id.items()}

    for sdrow in sport_discipline_rows:
        from_id = sdrow["discipline_id"]
        text = sdrow.get("b2b_pairing_rule_text")
        if not text or not from_id:
            continue
        for line in str(text).splitlines():
            m = pat.search(line)
            if not m:
                continue
            dest_name = m.group("dest").strip()
            # Strip trailing parens or notes from the dest name
            dest_clean = re.sub(r"\s*\([^)]*\)\s*$", "", dest_name).strip()
            dest_id = name_lookup.get(dest_clean.lower())
            if not dest_id:
                continue
            key = (from_id, dest_id)
            if key in matrix_pairs or key in seen:
                continue
            seen.add(key)
            rating = m.group("rating").upper()
            rationale = m.group("rat")
            rows.append({
                "discipline_id_a": from_id,
                "discipline_id_b": dest_id,
                "pairing_rating": rating,
                "rationale": rationale.strip() if rationale else None,
                "source": "b2b_rule",
            })
    return rows


def extract_phase_load_allocation(ws: Worksheet) -> list[dict[str, Any]]:
    """Sheet 5 — Phase Load Allocation. Header R1, data R2+."""
    rows: list[dict[str, Any]] = []
    last_sport: str | None = None
    for r in range(2, ws.max_row + 1):
        sport = _t(ws.cell(row=r, column=1).value)
        # Some rows omit the sport column (block layout) — carry the last
        # seen sport value forward only when discipline col is non-empty.
        if sport:
            last_sport = sport
        disc = _t(ws.cell(row=r, column=3).value)
        role = _t(ws.cell(row=r, column=4).value)
        # Skip blank rows
        if not disc and not role:
            continue
        rows.append({
            "sport_name": last_sport or "",
            "discipline_id": _t(ws.cell(row=r, column=2).value),
            "discipline_name": disc or "",
            "role": role or "",
            "base_pct_low": _f(ws.cell(row=r, column=5).value),
            "base_pct_high": _f(ws.cell(row=r, column=6).value),
            "build_pct_low": _f(ws.cell(row=r, column=7).value),
            "build_pct_high": _f(ws.cell(row=r, column=8).value),
            "peak_pct_low": _f(ws.cell(row=r, column=9).value),
            "peak_pct_high": _f(ws.cell(row=r, column=10).value),
            "taper_pct_low": _f(ws.cell(row=r, column=11).value),
            "taper_pct_high": _f(ws.cell(row=r, column=12).value),
            "notes_conditions": _t(ws.cell(row=r, column=13).value),
        })
    return rows


_TEAM_FORMAT_SKIP_PREFIXES = ("PARADIGM", "FORMAT KEY", "TRAINING IMPLICATION")


def extract_team_formats(ws: Worksheet) -> list[dict[str, Any]]:
    """Sheet 6 — header on R3, data R4+. Skip paradigm separator rows."""
    rows: list[dict[str, Any]] = []
    for r in range(4, ws.max_row + 1):
        sport = _t(ws.cell(row=r, column=1).value)
        if not sport:
            continue
        # Skip section headers / paradigm separators
        upper = sport.upper()
        if any(upper.startswith(p) for p in _TEAM_FORMAT_SKIP_PREFIXES):
            continue
        rows.append({
            "sport_name": sport,
            "formats_available": _t(ws.cell(row=r, column=2).value),
            "team_format_types": _t(ws.cell(row=r, column=3).value),
            "unified_team_description": _t(ws.cell(row=r, column=4).value),
            "relay_specialist_description": _t(ws.cell(row=r, column=5).value),
            "training_implication_unified": _t(ws.cell(row=r, column=6).value),
            "training_implication_relay": _t(ws.cell(row=r, column=7).value),
            "key_distinctions_notes": _t(ws.cell(row=r, column=8).value),
        })
    return rows


def extract_cross_sport_properties(ws: Worksheet) -> list[dict[str, Any]]:
    """Sheet 8 — header R1, data R2+.

    Stops at the EXTENSION NOTES marker; everything below it is commentary.
    A blank row before the marker is also a stop signal (the substantive
    block ends at the first gap).
    """
    rows: list[dict[str, Any]] = []
    seen_any_data = False
    for r in range(2, ws.max_row + 1):
        prop = _t(ws.cell(row=r, column=1).value)
        if prop and prop.upper().startswith("EXTENSION NOTES"):
            break
        if not prop:
            if seen_any_data:
                break
            continue
        seen_any_data = True
        rows.append({
            "property_id": prop,
            "property_name": _t(ws.cell(row=r, column=2).value) or prop,
            "description": _t(ws.cell(row=r, column=3).value),
            "scope": _t(ws.cell(row=r, column=4).value),
            "ranking_text": _t(ws.cell(row=r, column=5).value),
            "estimated_values": _t(ws.cell(row=r, column=6).value),
            "source_evidence": _t(ws.cell(row=r, column=7).value),
            "notes": _t(ws.cell(row=r, column=9).value) or _t(ws.cell(row=r, column=8).value),
        })
    return rows


def build_sport_discipline_bridge(
    sport_discipline_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Spec §4.9 — derived bridge. One row per (sport, discipline_id) where
    applicability='INCLUDED'.

    `exercise_db_sport`: defaults to the framework `sport_name`. The vocab
    alignment validator (Open Item #5) surfaces mismatches between this
    field and `sport_exercise_map.sport_name` for manual reconciliation.
    """
    rows: list[dict[str, Any]] = []
    for r in sport_discipline_rows:
        if (r.get("applicability") or "").upper() != "INCLUDED":
            continue
        rows.append({
            "framework_sport": r["sport_name"],
            "discipline_id": r["discipline_id"],
            "discipline_name": r["discipline_name"],
            "exercise_db_sport": r["sport_name"],
            "role": r["role"],
            "default_race_time_pct_low": r.get("race_time_pct_low"),
            "default_race_time_pct_high": r.get("race_time_pct_high"),
        })
    return rows
