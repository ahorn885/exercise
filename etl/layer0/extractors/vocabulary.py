"""Layer 0 ETL — extractor for Vocabulary_Audit_v2.md (source 0C).

Parses Sections 1, 2.2, 3, 4 from the structured markdown. Sections 5–8
(commentary + cleanup tasks) are intentionally skipped — those drive
transforms, not data per spec §2 / §7.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# Body regions in §1 are H2 headers in this exact order. Each header
# delimits a region whose markdown table rows are body parts under that
# region. The "Trunk" region also contains a "derived" row for Chest.
_BODY_REGION_HEADERS = [
    "Head / Neck",
    "Shoulder",
    "Arm",
    "Back",
    "Hip",
    "Upper leg",
    "Knee",
    "Lower leg",
    "Foot / Ankle",
    "Trunk",
]

# Section 3 equipment categories — H2 headers in §3. Order matters for
# parsing (we use the next H2 / # / final marker as the section
# terminator). "Assumed Universal — system-level category" sets the
# is_universal flag. "Terrain (separate from equipment ...)" feeds the
# terrain table, not equipment.
_EQUIPMENT_CATEGORIES = [
    "Barbells & Bars",
    "Dumbbells",
    "Kettlebells",
    "Machines — Lower Body",
    "Machines — Upper Body",
    "Machines — Cardio",
    "Bodyweight & Portable Equipment",
    "Stability & Balance",
    "Plyo & Power",
    "Grip & Forearm Specific",
    "Sport-Specific — Cycling (top-level vessels — kept individual)",
    "Sport-Specific — Paddle (top-level vessels — kept individual)",
    "Sport-Specific — Running & Hiking (top-level — kept individual)",
    "Sport-Specific — Winter (top-level singletons — kept individual)",
    "Sport-Specific — Swimming (top-level — kept individual)",
    "Recovery & Therapy",
]

_UNIVERSAL_HEADER = "Assumed Universal — system-level category"
_TERRAIN_HEADER = "Terrain (separate from equipment — not athlete-side)"

# DROP markers — entries flagged "DROP from AR Schema 2.2" in the audit
# notes column. We honor these by skipping the row.
_DROP_RE = re.compile(r"\bDROP from AR Schema\b", re.IGNORECASE)


def _slugify_label(s: str) -> str:
    return s.strip().lower()


def parse_vocabulary_md(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Top-level entry. Returns:
        {
          "body_parts":               [...],
          "health_condition_categories": [...],
          "equipment_items":          [...],
          "terrain_types":            [...],
          "sport_specific_gear_toggles": [...],
        }
    """
    text = Path(path).read_text(encoding="utf-8")
    return {
        "body_parts": _parse_body_parts(text),
        "health_condition_categories": _parse_health_categories(text),
        "equipment_items": _parse_equipment(text),
        "terrain_types": _parse_terrain(text),
        "sport_specific_gear_toggles": _parse_gear_toggles(text),
    }


# ---------------------------------------------------------------------------
# Section 1 — Body parts
# ---------------------------------------------------------------------------

def _parse_body_parts(text: str) -> list[dict[str, Any]]:
    """Walk the §1 H2 headers and extract markdown table rows under each.

    Dedupes by canonical_name (first-seen wins) — the audit lists a few
    body parts under multiple regions for navigation (e.g. Trapezius
    appears under both Head/Neck and Back, TFL appears twice under Hip).
    The schema's UNIQUE (canonical_name, etl_version) only allows one row
    per canonical name, so we collapse here.
    """
    sec_text = _slice_section(text, "# Section 1 — Body Part Canonical List",
                              "# Section 2 — Health Conditions Canonical List")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for region in _BODY_REGION_HEADERS:
        block = _slice_block(sec_text, f"## {region}", _next_h2_marker(sec_text, f"## {region}"))
        if not block:
            continue
        for record in _parse_md_table(block):
            canonical = record.get("Canonical")
            if not canonical:
                continue
            key = canonical.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "canonical_name": canonical,
                "body_region": region,
                "source_origin": record.get("Source"),
                "notes": record.get("Notes"),
            })
    return rows


# ---------------------------------------------------------------------------
# Section 2.2 — Health condition categories
# ---------------------------------------------------------------------------

def _parse_health_categories(text: str) -> list[dict[str, Any]]:
    sec_text = _slice_section(
        text,
        "## 2.2 System category enum",
        "**Mapping from old col 13 systemic tokens:**",
    )
    rows: list[dict[str, Any]] = []
    for record in _parse_md_table(sec_text):
        cat = record.get("System category")
        if not cat:
            continue
        rows.append({
            "category_name": cat,
            "description": (
                # combine "Drives" and "Examples that map here" into description
                f"{record.get('Drives','').strip()} "
                f"— Examples: {record.get('Examples that map here','').strip()}"
            ).strip(" —"),
        })
    return rows


# ---------------------------------------------------------------------------
# Section 3 — Equipment + Terrain
# ---------------------------------------------------------------------------

def _parse_equipment(text: str) -> list[dict[str, Any]]:
    """Parse all standard equipment categories + Assumed Universal block.

    Dedupes by canonical_name (first-seen wins) — the audit lists a few
    items in multiple categories (e.g. Foam roller appears under both
    Bodyweight & Portable and Recovery & Therapy with a "Already in ..."
    note in the second slot).
    """
    sec_text = _slice_section(
        text,
        "# Section 3 — Equipment Canonical List",
        "# Section 4 — Sport-Specific Gear Readiness Toggles",
    )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(row: dict[str, Any]) -> None:
        key = row["canonical_name"].strip().lower()
        if key in seen:
            return
        seen.add(key)
        rows.append(row)

    # Standard categories
    for cat in _EQUIPMENT_CATEGORIES:
        block = _slice_block(sec_text, f"## {cat}", _next_h2_marker(sec_text, f"## {cat}"))
        if not block:
            continue
        for record in _parse_md_table(block):
            canonical = record.get("Canonical")
            if not canonical:
                continue
            notes = record.get("Notes") or ""
            if _DROP_RE.search(notes):
                continue
            _add({
                "canonical_name": canonical,
                "equipment_category": cat,
                "is_universal": False,
                "notes": notes or None,
            })

    # Assumed Universal block — different table column header is "Canonical"
    block = _slice_block(
        sec_text,
        f"## {_UNIVERSAL_HEADER}",
        _next_h2_marker(sec_text, f"## {_UNIVERSAL_HEADER}"),
    )
    if block:
        for record in _parse_md_table(block):
            canonical = record.get("Canonical")
            if not canonical:
                continue
            _add({
                "canonical_name": canonical,
                "equipment_category": "Assumed Universal",
                "is_universal": True,
                "notes": record.get("Use case") or None,
            })

    return rows


def _parse_terrain(text: str) -> list[dict[str, Any]]:
    """Audit's terrain table is a 'col-7 phrases → Section K canonical'
    mapping. Use the right-hand Section K label as canonical (one row per
    distinct label). The left-hand col-7 aliases go into `notes` for
    traceability."""
    sec_text = _slice_section(
        text,
        "# Section 3 — Equipment Canonical List",
        "# Section 4 — Sport-Specific Gear Readiness Toggles",
    )
    block = _slice_block(
        sec_text,
        f"## {_TERRAIN_HEADER}",
        _next_h2_marker(sec_text, f"## {_TERRAIN_HEADER}"),
    )
    if not block:
        return []
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for record in _parse_md_table(block):
        col7 = record.get("Terrain in col 7")
        locale = record.get("Belongs in Section K (Locale Terrain)")
        if not locale:
            continue
        canonical = locale.strip()
        if canonical not in grouped:
            grouped[canonical] = []
            order.append(canonical)
        if col7:
            grouped[canonical].append(col7.strip())
    rows: list[dict[str, Any]] = []
    for canonical in order:
        aliases = grouped[canonical]
        rows.append({
            "canonical_name": canonical,
            "notes": "; ".join(aliases) if aliases else None,
        })
    return rows


# ---------------------------------------------------------------------------
# Section 4.1 — Sport-specific gear toggles
# ---------------------------------------------------------------------------

# D-73 Phase 2.4-Prep: code-side constants for `also_satisfies` +
# `gated_discipline_ids` per Layer2C_Spec.md §5.1 + §6 + §8.3. The
# Vocabulary_Audit_v2.md §4 source markdown doesn't carry these signals
# as table columns (the relevant facts live in §4.2 notes + reverse
# inference against `layer0.disciplines`). v1 ships them code-side so
# next ETL re-run carries them forward; same pattern as Layer2D's
# `_HIGH_CARDIAC_LOAD_DISCIPLINES` (per Phase 2.2 precedent). Promotion
# to a Layer 0 reference table is a future option if non-AR sports add
# enough cases to make curation pressure real.
_TOGGLE_ALSO_SATISFIES: dict[str, list[str]] = {
    "Climbing — roped": ["Rappelling / abseiling"],
}

_TOGGLE_GATED_DISCIPLINES: dict[str, list[str]] = {
    "Climbing — roped": ["D-010"],
    "Rappelling / abseiling": ["D-011"],
    "Snowshoeing setup": ["D-015"],
}


def _parse_gear_toggles(text: str) -> list[dict[str, Any]]:
    sec_text = _slice_section(
        text,
        "## 4.1 The 12 toggles",
        "## 4.2 Notes on overlap and edge cases",
    )
    rows: list[dict[str, Any]] = []
    for record in _parse_md_table(sec_text):
        toggle = record.get("Toggle (canonical token)")
        if not toggle:
            continue
        # Strip trailing markdown emphasis like "*(retained as note only)*"
        toggle_clean = re.sub(r"\s*\*\([^)]+\)\*\s*$", "", toggle).strip()
        rows.append({
            "toggle_name": toggle_clean,
            "display_label": toggle_clean,
            "description": record.get("Replaces these former col 7 sub-tokens"),
            # paired_equipment_categories is left empty — no clean source
            # signal in the markdown. Future: cross-reference §3 categories.
            "paired_equipment_categories": [],
            "also_satisfies": list(_TOGGLE_ALSO_SATISFIES.get(toggle_clean, [])),
            "gated_discipline_ids": list(
                _TOGGLE_GATED_DISCIPLINES.get(toggle_clean, [])
            ),
        })
    return rows


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _slice_section(text: str, start_marker: str, end_marker: str) -> str:
    a = text.find(start_marker)
    if a < 0:
        return ""
    b = text.find(end_marker, a + len(start_marker))
    if b < 0:
        b = len(text)
    return text[a:b]


def _slice_block(text: str, start_marker: str, end_marker: str | None) -> str:
    a = text.find(start_marker)
    if a < 0:
        return ""
    if end_marker:
        b = text.find(end_marker, a + len(start_marker))
        if b < 0:
            b = len(text)
    else:
        b = len(text)
    return text[a:b]


def _next_h2_marker(sec_text: str, current_h2: str) -> str | None:
    """Return the next H2 (or H1) header after `current_h2` to scope a block."""
    a = sec_text.find(current_h2)
    if a < 0:
        return None
    a += len(current_h2)
    # Find the next "## " or "# " or end-of-section
    candidates: list[int] = []
    for marker in ("\n## ", "\n# "):
        pos = sec_text.find(marker, a)
        if pos >= 0:
            candidates.append(pos + 1)  # skip the leading newline
    if not candidates:
        return None
    next_start = min(candidates)
    line_end = sec_text.find("\n", next_start)
    if line_end < 0:
        line_end = len(sec_text)
    return sec_text[next_start:line_end]


def _parse_md_table(block: str) -> list[dict[str, str]]:
    """Parse all GFM-style tables in `block` into a list of dict rows.

    Multiple tables in a single block concatenate. Header row is the line
    immediately above the `|---|---|` separator. Cells are stripped.
    """
    out: list[dict[str, str]] = []
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        # Look for a separator row
        if _is_separator(line) and i > 0 and lines[i - 1].strip().startswith("|"):
            headers = _split_md_row(lines[i - 1])
            j = i + 1
            while j < len(lines):
                row_line = lines[j].rstrip()
                if not row_line.strip().startswith("|"):
                    break
                if _is_separator(row_line):
                    break
                cells = _split_md_row(row_line)
                # zip headers ↔ cells
                row: dict[str, str] = {}
                for k, h in enumerate(headers):
                    val = cells[k] if k < len(cells) else ""
                    row[h] = val.strip()
                if any(v for v in row.values()):
                    out.append(row)
                j += 1
            i = j
        else:
            i += 1
    return out


def _is_separator(line: str) -> bool:
    s = line.strip()
    if not s.startswith("|"):
        return False
    inner = s.strip("|")
    parts = [p.strip() for p in inner.split("|")]
    return all(re.fullmatch(r":?-{1,}:?", p) for p in parts) and len(parts) >= 1


def _split_md_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]
