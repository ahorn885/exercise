"""Layer 0 ETL — vocabulary cleanup transforms.

Implements the rename + slash-decompose + sport-specific-rollup rules
documented in `Vocabulary_Audit_v2.md` Section 5. Applied at ETL time per
spec §3.1 option (b) — source xlsx is never modified.

Public functions:
    transform_equipment_string(raw)         -> list[str]   (col 7)
    transform_body_part_string(raw)         -> list[str]   (col 13, body parts only)
    split_contraindicated_string(raw)       -> tuple[list[str], list[str]]
                                               (col 13, splits body parts ↔ conditions)
    validate_against_canonical(name, set)   -> str         ('match'/'unknown')
"""
from __future__ import annotations

import re
from typing import Iterable

# ---------------------------------------------------------------------------
# Rename rules — Vocab Audit §5 "Col 7 cleanup tasks — vocab-driven renames"
#
# Match is case-insensitive on the WHOLE token (after slash-decompose).
# Empty-string rename keys map "drop entirely".
# ---------------------------------------------------------------------------

_RENAME: dict[str, str] = {
    # Bands
    "band": "Resistance Band",
    "rubber band": "Resistance Band",
    # Cycling
    "mtb": "Mountain Bike",
    # Cable machine
    "cable": "Cable Machine",
    # Plyo box family
    "box": "Plyo Box",
    "vault box": "Plyo Box",
    # Vest family
    "vest": "Weighted Vest",
    "weight vest": "Weighted Vest",
    # Footwear
    "shoes": "Running Shoes",
    # Rings
    "rings": "Gymnastic Rings",
    # Bike trainer
    "trainer": "Bike Trainer",
    "or trainer": "Bike Trainer",  # comma-split artifact noted in audit
    # SUP
    "stand-up paddleboard": "SUP",
    # Fix typo
    "race belt)": "Race belt",
}

# Race-fueling items moved out of equipment per audit §5
_DROP_TOKENS: set[str] = {
    "gels",
    "chews",
    "cups",
    "soft flask",
}


# ---------------------------------------------------------------------------
# Sport-specific rollup — Vocab Audit §5 "sport-specific gear rollup (NEW in v2)"
#
# Maps each former col-7 sub-component token to its rolled-up toggle.
# Lower-case keys for case-insensitive matching.
# ---------------------------------------------------------------------------

_ROLLUP: dict[str, str] = {
    # Climbing — roped
    "climbing rope": "Climbing — roped",
    "belay device": "Climbing — roped",
    "carabiners": "Climbing — roped",
    "anchor hardware": "Climbing — roped",
    "quickdraws": "Climbing — roped",
    # Bouldering
    "bouldering shoes": "Bouldering",
    "crash pad": "Bouldering",
    # Rappelling
    "rappel device": "Rappelling",
    "backup prusik": "Rappelling",
    # Via ferrata
    "via ferrata y-lanyard": "Via ferrata",
    # Mountaineering
    "mountaineering boots": "Mountaineering",
    "mountaineering harness": "Mountaineering",
    "mechanical ascender": "Mountaineering",
    # Touring/AT ski setup
    "touring skis": "Touring/AT ski setup",
    "alpine skis": "Touring/AT ski setup",
    "ski boots (touring)": "Touring/AT ski setup",
    "ski poles (touring/alpine)": "Touring/AT ski setup",
    "climbing skins": "Touring/AT ski setup",
    "ski crampons": "Touring/AT ski setup",
    "boot buckles": "Touring/AT ski setup",
    # Classic XC
    "classic cross-country skis": "Classic XC ski setup",
    "classic xc boots": "Classic XC ski setup",
    "classic xc poles": "Classic XC ski setup",
    # Skate XC
    "skate cross-country skis": "Skate XC ski setup",
    "skate xc boots": "Skate XC ski setup",
    "skate xc poles": "Skate XC ski setup",
    # Whitewater
    "spray skirt": "Whitewater paddling setup",
    "whitewater helmet": "Whitewater paddling setup",
    "whitewater pfd": "Whitewater paddling setup",
    "throw bag": "Whitewater paddling setup",
    # Shooting
    "laser pistol": "Shooting setup",
    "air pistol": "Shooting setup",
}

# Ambiguous tokens — context-dependent rollup. Audit notes:
#   "Slings"  → Climbing — roped (default; or Rappelling by exercise context)
#   "Crampons" → Mountaineering (default; or Touring/AT ski setup if SkiMo)
#   "Ice axe" → Mountaineering (default; or Touring/AT ski setup if SkiMo)
#   "Harness (when context = roped climbing)" → Climbing — roped
#   "Chalk (when bouldering)" → Bouldering — but chalk is also a generic
#       weightlifting accessory; only roll up when paired with bouldering kit.
# We pick the documented default. If the equipment string contains a clearly
# stronger context signal (e.g. SkiMo / ski tokens already present), we route
# to the alternate. The full per-exercise context is the role of v2's
# rebuild — these defaults match the audit's stated convention.
_AMBIGUOUS_DEFAULT: dict[str, str] = {
    "slings": "Climbing — roped",
    "crampons": "Mountaineering",
    "ice axe": "Mountaineering",
    "harness": "Climbing — roped",
    "chalk": "Bouldering",
}

# Mountaineering harness is referenced in Touring/AT context too; we
# detect ski context by presence of "ski" tokens in the original string.
_SKI_CONTEXT_TOKENS = {
    "touring/at ski setup",
    "classic xc ski setup",
    "skate xc ski setup",
    "ski",
    "skis",
    "ski poles",
}

_BOULDERING_CONTEXT_TOKENS = {
    "bouldering shoes",
    "crash pad",
    "bouldering",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transform_equipment_string(raw: str | None) -> list[str]:
    """Apply the Vocab Audit §5 rules to a raw col-7 equipment string.

    Pipeline:
      1. Split the raw string on `,` into items.
      2. For each item, decompose on `/` (slash-strings → atomic items per §5).
      3. Strip whitespace, drop empties.
      4. Apply the rename map.
      5. Apply the sport-specific rollup map.
      6. Drop race-fueling tokens entirely.
      7. Deduplicate while preserving first-seen order.

    Returns a list of canonical equipment names. Empty input → [].
    """
    if not raw:
        return []
    s = str(raw).strip()
    if not s:
        return []

    raw_items: list[str] = []
    for chunk in s.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        for piece in _decompose_slash(chunk):
            piece = piece.strip()
            if piece:
                raw_items.append(piece)

    # Round 1 — apply rename + rollup + drop tokens
    intermediate: list[str] = []
    lower_set: set[str] = set(t.lower() for t in raw_items)
    for token in raw_items:
        canonical = _resolve_token(token, lower_set)
        if canonical is None:
            continue
        intermediate.append(canonical)

    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in intermediate:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# Col-13 (body parts) cleanup — Vocab Audit §5
# ---------------------------------------------------------------------------

_BODY_RENAME: dict[str, str] = {
    "cervical": "Neck",
    "cervical spine": "Neck",
    "lumbar": "Lower back",
    "thoracic": "Upper back",
    "anterior cruciate ligament": "ACL",
    "hip abductor": "Glute",
    "sacrum": "SI joint",
    "ribs": "Rib",
    "hip crest": "Hip crest (iliac crest)",
    "spine": "Spine (general)",
    "finger flexor pulley": "Finger pulley",
    "finger": "Fingers",
    "tricep": "Triceps",
    "bicep": "Biceps",
}

# Tokens in col 13 that are health/systemic conditions, not body parts.
# Routed to contraindicated_conditions by split_contraindicated_string().
SYSTEMIC_TOKENS: set[str] = {
    "cognitive",
    "cardiac",
    "lungs",
    "gi",
    "skin",
    "sciatica",
}

# Aliases applied to systemic tokens before they land in
# contraindicated_conditions. Maps a raw col-13 token (lower-cased) to the
# canonical health_condition_categories.category_name. Tokens not in this
# map pass through unchanged.
_CONTRA_RENAME: dict[str, str] = {
    "lungs": "Respiratory",
    "sciatica": "Neurological",
}

# Tokens to drop from col 13 entirely — functional capacity / gear-side
# adaptations / non-systemic flags that aren't athlete health data.
# Saddle / Goggle / Blister are gear-fit adaptations built up through
# training (Vocab Audit §2.2 "excluded — col 13 keeps as filter flags but
# no athlete-side field"); Core Temperature is captured by the
# Thermoregulation category but the raw token isn't a category itself.
_CONTRA_DROP: set[str] = {
    "grip",
    "saddle",
    "goggle",
    "blister",
    "core temperature",
}

# "Chest/Rib" splits into ["Chest", "Rib"] per audit §5.
# Compound slash entries like "Shoulder/Wrist" similarly split.
# We achieve the split via the slash-decompose pipeline, then run rename.


def transform_body_part_string(raw: str | None) -> list[str]:
    """Apply col-13 rename + split rules per Vocab Audit §5.

    Pipeline:
      1. Split on "," then on "/" (or " or ") — handles "Chest/Rib",
         "Shoulder/Wrist", "Shoulder/Neck" splits.
      2. Apply body-part rename map.
      3. Dedupe preserving order.

    Tokens that map to non-body-part filter flags (Cardiac, Cognitive,
    Lungs, GI, Skin) pass through unchanged — they're surfaced as warnings
    by the vocab alignment validator, which is the correct behavior since
    they're not body parts. The v2 query layer should route them to
    health_condition_categories. The contraindication splitter
    (`split_contraindicated_string`) handles the routing automatically.
    """
    if not raw:
        return []
    s = str(raw).strip()
    if not s:
        return []
    items: list[str] = []
    for chunk in s.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        for piece in _decompose_slash(chunk):
            piece = piece.strip()
            if not piece:
                continue
            lower = piece.lower()
            items.append(_BODY_RENAME.get(lower, piece))
    seen: set[str] = set()
    out: list[str] = []
    for t in items:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def split_contraindicated_string(
    raw: str | None,
) -> tuple[list[str], list[str]]:
    """Split a col-13 contraindicated string into body parts and conditions.

    Pipeline per token (after comma-split and slash-decompose):
      - Token in _CONTRA_DROP     → drop silently
      - Token in SYSTEMIC_TOKENS  → apply _CONTRA_RENAME (if present),
                                    append to conditions list
      - Otherwise                 → apply _BODY_RENAME, append to body_parts list

    Returns (body_parts, conditions). Each list is deduplicated, order preserved.
    """
    if not raw:
        return [], []
    s = str(raw).strip()
    if not s:
        return [], []

    body_parts: list[str] = []
    conditions: list[str] = []
    seen_bp: set[str] = set()
    seen_cond: set[str] = set()

    for chunk in s.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        for piece in _decompose_slash(chunk):
            piece = piece.strip()
            if not piece:
                continue
            lower = piece.lower()

            if lower in _CONTRA_DROP:
                continue
            elif lower in SYSTEMIC_TOKENS:
                canonical = _CONTRA_RENAME.get(lower, piece)
                ckey = canonical.lower()
                if ckey not in seen_cond:
                    seen_cond.add(ckey)
                    conditions.append(canonical)
            else:
                renamed = _BODY_RENAME.get(lower, piece)
                rkey = renamed.lower()
                if rkey not in seen_bp:
                    seen_bp.add(rkey)
                    body_parts.append(renamed)

    return body_parts, conditions


def validate_against_canonical(
    name: str,
    canonical_set: Iterable[str],
) -> str:
    """Compare `name` to a set of canonical names (case-insensitive).

    Returns 'match' | 'unknown'. Caller wraps with table-specific lookup
    against `layer0.equipment_items` / `body_parts` / etc.
    """
    target = name.strip().lower()
    for c in canonical_set:
        if c.strip().lower() == target:
            return "match"
    return "unknown"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _decompose_slash(item: str) -> list[str]:
    """Split a slash-string into atomic items per Vocab Audit §5.

    "Kayak / Packraft"            → ["Kayak", "Packraft"]
    "Foot/Ankle"                  → ["Foot", "Ankle"]    (also documented)
    "Floor or Bench"              → ["Floor", "Bench"]   (exercise-side OR-logic)
    "Bench or Box"                → ["Bench", "Box"]

    Notes:
      - Some equipment items legitimately contain "/" — e.g. "TT / triathlon
        bike", "TRX / suspension trainer", "Glute ham developer (GHD)". The
        spec asks us to decompose for matching purposes; the canonical list
        already has the alternates as separate entries (TRX is acceptable
        as-is per audit). We err on the side of decomposing, then the rename
        map normalizes the components.
    """
    # Split on " or " too — the audit treats "or" the same as "/"
    parts = re.split(r"\s*/\s*|\s+or\s+", item)
    return [p for p in parts if p]


def _resolve_token(token: str, all_lower: set[str]) -> str | None:
    """Apply rename → rollup → drop, returning the canonical name (or None
    if the token should be dropped entirely)."""
    lower = token.lower().strip()
    if not lower:
        return None

    # 1. Drop list (race fueling)
    if lower in _DROP_TOKENS:
        return None

    # 2. Direct rename
    if lower in _RENAME:
        return _RENAME[lower]

    # 3. Rollup — sport-specific gear sub-components
    if lower in _ROLLUP:
        return _ROLLUP[lower]

    # 4. Ambiguous — context-aware rollup
    if lower in _AMBIGUOUS_DEFAULT:
        if lower in {"crampons", "ice axe"} and _has_ski_context(all_lower):
            return "Touring/AT ski setup"
        if lower == "chalk":
            # Only rollup chalk if we're clearly in a bouldering context;
            # otherwise leave as a generic gym accessory (drop for now —
            # chalk isn't in the canonical equipment list).
            if _has_bouldering_context(all_lower):
                return "Bouldering"
            return None
        return _AMBIGUOUS_DEFAULT[lower]

    # 5. No transform — return as-is, with a basic title-case normalization
    #    only when the source was clearly upper/lower-cased inconsistently.
    return token.strip()


def _has_ski_context(tokens: set[str]) -> bool:
    return any(any(t.startswith(p) or p in t for p in _SKI_CONTEXT_TOKENS) for t in tokens)


def _has_bouldering_context(tokens: set[str]) -> bool:
    return any(t in _BOULDERING_CONTEXT_TOKENS for t in tokens)
