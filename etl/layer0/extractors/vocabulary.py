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
    # Vocabulary V4 §6 — gym rows recategorized from the prior 10-category
    # scheme into these 6 buckets. Order matters: dedupe is first-seen-wins,
    # so Bodyweight & Portable must precede Recovery & Therapy (Foam roller
    # resolves to Bodyweight). Headers must match the ## sections in
    # Vocabulary_Audit_v2.md Section 3 exactly.
    "Freeweights",
    "Machines - Strength",
    "Machines - Cardio",
    "Plyo, Power & Stability",
    "Grip & Climbing",
    "Bodyweight & Portable Equipment",
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


# D-73 Phase 5.2 Walkthrough — ETL terrain-vocab drift fix (Bucket C sub-item k).
# The audit markdown carries terrain only as a 'col-7 phrases → Section K
# canonical' alias table (15 minimal-shape rows, no terrain_id / category /
# fidelity / environment / simulation_note). The structured 9-column shape
# shipped via etl/sources/migrate_terrain_types.sql 2026-05-09 as a one-shot
# corrective; subsequent `python -m etl.layer0.run` invocations then
# re-introduced the minimal-shape audit rows under a fresh 0C-vN and
# superseded the TRN-xxx rows (insert_versioned's supersede sweep matches
# LIKE '0C-v%' — see etl/layer0/db.py:122-130). To stop that drift the
# structured rows now live code-side here, mirroring the Phase 2.4-Prep
# precedent (`_TOGGLE_ALSO_SATISFIES` / `_TOGGLE_GATED_DISCIPLINES` below
# at vocabulary.py:270-278). The audit terrain block becomes a dead source
# for terrain_types population (still referenced by Section K narrative).
_TERRAIN_STRUCTURED_ROWS: list[dict[str, Any]] = [
    # Foot terrains
    {
        "terrain_id": "TRN-001",
        "canonical_name": "Road / Paved",
        "category": "Foot",
        "requires_elevation": False,
        "technical_surface": False,
        "environment": "Outdoor",
        "simulatable": "full",
        "simulation_note": "Treadmill is full-fidelity substitute for road running.",
        "notes": "Standard road and paved path running surface.",
    },
    {
        "terrain_id": "TRN-002",
        "canonical_name": "Groomed Trail",
        "category": "Foot",
        "requires_elevation": False,
        "technical_surface": False,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Treadmill covers aerobic load; loses surface variation and proprioceptive demand.",
        "notes": "Compacted, maintained singletrack or dirt trail. Low surface variability.",
    },
    {
        "terrain_id": "TRN-003",
        "canonical_name": "Technical Trail",
        "category": "Foot",
        "requires_elevation": False,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Agility and balance drills are partial proxy; proprioceptive adaptation to variable surface requires real terrain.",
        "notes": "Rocky, root-crossed, or otherwise unpredictable trail surface. High ankle demand.",
    },
    {
        "terrain_id": "TRN-004",
        "canonical_name": "Hill / Rolling",
        "category": "Foot",
        "requires_elevation": True,
        "technical_surface": False,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Max-incline treadmill simulates uphill aerobic load; descent EIMD adaptation requires actual downhill terrain.",
        "notes": "Moderate sustained elevation. Rolling hills with recoverable grades.",
    },
    {
        "terrain_id": "TRN-005",
        "canonical_name": "Mountain / Alpine",
        "category": "Foot",
        "requires_elevation": True,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Stair climber and weighted vest simulate vertical load; descent skill and alpine balance cannot be replicated indoors.",
        "notes": "High sustained elevation with exposed, technical, or multi-hour vertical gain. Includes above-treeline terrain.",
    },
    {
        "terrain_id": "TRN-006",
        "canonical_name": "Fell / Moorland",
        "category": "Foot",
        "requires_elevation": True,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "none",
        "simulation_note": "No meaningful indoor substitute. Navigation on unmarked terrain and variable footing on heather/bog cannot be simulated.",
        "notes": "Open, pathless, navigationally demanding terrain. Steep grass, heather, bog, moorland. Fell running specific.",
    },
    {
        "terrain_id": "TRN-007",
        "canonical_name": "Technical Rock / Scree",
        "category": "Foot",
        "requires_elevation": False,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "none",
        "simulation_note": "Balance drills develop general stability but rock-specific proprioceptive adaptation requires actual boulder/scree terrain.",
        "notes": "Loose boulder fields, scree slopes, rock gardens. Distinct from rock climbing — locomotive movement over unstable rock.",
    },
    # Vocabulary V3 (#340) — Off-trail / trackless ground. Distinct stimulus
    # confirmed against the existing vocab: TRN-002 is a maintained path,
    # TRN-003 is technical-but-tracked trail, and TRN-006 Fell/Moorland is OPEN
    # pathless upland (heather/bog). This row is the vegetated/wooded bushwhack
    # case — scrub, tall grass, deadfall — a real expedition-AR stimulus with no
    # path at all. race_eligible TRUE (expedition courses genuinely cross it).
    {
        "terrain_id": "TRN-018",
        "canonical_name": "Off Trail / Bushwhack",
        "category": "Foot",
        "requires_elevation": False,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "none",
        "simulation_note": "No indoor substitute. Trackless travel through scrub, tall grass, deadfall, and uneven vegetated ground demands constant footing micro-adjustment, vegetation resistance, and continuous route-finding that no treadmill or machine reproduces.",
        "notes": "Trackless off-trail ground — scrub brush, tall grass, bushwhacking through vegetated or untracked terrain. No path at all. Distinct from groomed trail (TRN-002), technical-but-tracked trail (TRN-003), and open pathless upland (TRN-006 Fell / Moorland). Expedition-AR stimulus.",
        "race_eligible": True,
    },
    # Bucket C sub-item (g) 2026-05-24 — Gravel added as the unambiguous surface
    # gap in the terrain vocab (TRN-001 is paved, TRN-002 is dirt singletrack,
    # TRN-004 is elevation-keyed not surface-keyed). Terrain rows describe
    # SURFACE only; modality (foot/bike/etc.) is captured discipline-side +
    # equipment-side. A "best-fit" cross-reference (future slice) lets a planner
    # reason {locale_terrain_ids + equipment + included_disciplines} → which
    # modality fits a given session (e.g., gravel_bike + TRN-020 + gravel
    # cycling discipline → recommend gravel ride). Same TRN-020 also serves
    # gravel-running stimulus.
    {
        "terrain_id": "TRN-020",
        "canonical_name": "Gravel",
        "category": "Foot",
        "requires_elevation": False,
        "technical_surface": False,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Treadmill covers aerobic load and gait pattern; loses gravel-specific surface inconsistency (slip, micro-instability, occasional embedded rocks). Indoor cycling trainer covers cadence/power but loses bike-handling on loose surface for cycling use.",
        "notes": "Compacted unpaved gravel road or path. Distinct from paved road (TRN-001) and dirt singletrack (TRN-002). Serves both gravel-running and gravel-cycling stimuli; modality captured by discipline + equipment.",
    },
    # Water terrains
    {
        "terrain_id": "TRN-008",
        "canonical_name": "Pool",
        "category": "Water",
        "requires_elevation": False,
        "technical_surface": False,
        "environment": "Indoor",
        "simulatable": "full",
        "simulation_note": "Full fidelity for stroke mechanics and aerobic base. Standard pool environment.",
        "notes": "Controlled lane swimming. Flip turns, lane lines, consistent conditions.",
    },
    {
        "terrain_id": "TRN-009",
        "canonical_name": "Flat Water",
        "category": "Water",
        "requires_elevation": False,
        "technical_surface": False,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Pool covers aerobic base and stroke mechanics; loses open-water pacing, sighting, and conditions handling (wind, chop).",
        "notes": "Still water — lake, reservoir, pond. No perceptible current. Standard flatwater paddling and open-water swim training environment.",
    },
    {
        "terrain_id": "TRN-017",
        "canonical_name": "Moving Water",
        "category": "Water",
        "requires_elevation": False,
        "technical_surface": False,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Flat water covers paddle aerobic and stroke mechanics; loses current reading, ferry angles, and eddy use. Whitewater experience over-covers these skills.",
        "notes": "Rivers, current-driven channels, or tidal flats below Class II. Ferry angles, eddy reads, and current navigation required. Standard river-paddling and packraft-touring environment.",
    },
    {
        "terrain_id": "TRN-010",
        "canonical_name": "Ocean / Tidal",
        "category": "Water",
        "requires_elevation": False,
        "technical_surface": False,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Pool maintains aerobic base; loses sighting, wave/swell navigation, salt and cold exposure, and mass-start dynamics.",
        "notes": "Saltwater or tidal water — ocean, sea, or tidal estuary. Cold-shock potential, salt exposure, swell, horizon sighting. OW swimming and ocean paddling territory.",
    },
    {
        "terrain_id": "TRN-011",
        "canonical_name": "Whitewater",
        "category": "Water",
        "requires_elevation": False,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "none",
        "simulation_note": "Flat water maintains paddling fitness only. Whitewater skill (eddy catches, reading water, bracing, rolling) requires moving water.",
        "notes": "Class II+ moving water with rapids, eddies, hydraulics. Technical paddling terrain.",
    },
    # Snow terrain
    {
        "terrain_id": "TRN-012",
        "canonical_name": "Snow / Winter Alpine",
        "category": "Snow",
        "requires_elevation": True,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Stair climber with poles approximates uphill skinning aerobic load. Descent skill on snow cannot be simulated off-snow.",
        "notes": "Snow-covered mountain terrain requiring skis, snowshoes, or crampons. Includes groomed tracks, off-piste, and alpine descent.",
    },
    # Climbing terrains
    {
        "terrain_id": "TRN-013",
        "canonical_name": "Rock Wall (Outdoor)",
        "category": "Climbing",
        "requires_elevation": False,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "partial",
        "simulation_note": "Climbing gym transfers movement patterns and strength well; loses natural rock reading, exposure confidence, and protection placement.",
        "notes": "Natural rock climbing terrain. Sport routes, trad, or scrambling on real rock.",
    },
    {
        "terrain_id": "TRN-014",
        "canonical_name": "Climbing Gym",
        "category": "Climbing",
        "requires_elevation": False,
        "technical_surface": True,
        "environment": "Indoor",
        "simulatable": "full",
        "simulation_note": "Full fidelity for movement pattern development, finger strength, and route reading on plastic holds.",
        "notes": "Indoor climbing wall. Bouldering or roped. Standard AR climbing prep environment.",
        "race_eligible": False,
    },
    # MTB terrain
    {
        "terrain_id": "TRN-015",
        "canonical_name": "Pump Track / Skills Course",
        "category": "MTB",
        "requires_elevation": False,
        "technical_surface": True,
        "environment": "Outdoor",
        "simulatable": "none",
        "simulation_note": "No indoor substitute for pump track or MTB skills course. Balance and cornering drills are poor proxies.",
        "notes": "MTB-specific terrain. Berms, jumps, pump sections, technical flow. Skills training focused.",
        "race_eligible": False,
    },
    # Gym / indoor
    {
        "terrain_id": "TRN-016",
        "canonical_name": "Indoor / Gym",
        "category": "Gym",
        "requires_elevation": False,
        "technical_surface": False,
        "environment": "Indoor",
        "simulatable": "full",
        "simulation_note": "By definition this is the simulation environment. Full fidelity for any exercise it hosts.",
        "notes": "Treadmill, stair climber, erg, gym equipment. The indoor training environment itself.",
        "race_eligible": False,
    },
]

# Issue #445 — training-only environments that should never appear on the
# race-event terrain selector (no real race takes place at a climbing gym,
# pump track, or indoor gym). The `race_eligible: False` rows above are the
# source of record. As of Vocabulary V3 the flag is also promoted to a real
# `layer0.terrain_types.race_eligible` column (schema + ETL emit — #445's
# documented clean follow-up), so the app can move to a `WHERE race_eligible`
# clause. This frozenset still mirrors the rows for the current code-side
# request-time filter (`routes/race_events.py` + `routes/onboarding.py`)
# until that query switch lands. Same entries stay visible on the
# locale/training pickers (they're real training venues).
RACE_INELIGIBLE_TERRAIN_IDS = frozenset(
    row["terrain_id"]
    for row in _TERRAIN_STRUCTURED_ROWS
    if row.get("race_eligible") is False
)


def _parse_terrain(text: str) -> list[dict[str, Any]]:
    """Returns the 19 TRN-xxx structured terrain rows.

    `text` is accepted for parser-signature parity with the other section
    parsers but is unused — terrain vocab is code-side per the module-level
    `_TERRAIN_STRUCTURED_ROWS` rationale comment.
    """
    return [dict(row) for row in _TERRAIN_STRUCTURED_ROWS]


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
    "Climbing — roped": ["D-012"],
    "Rappelling / abseiling": ["D-013"],
    "Snowshoeing setup": ["D-017"],
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
