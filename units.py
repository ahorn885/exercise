"""Unit conversion + display formatting for athlete-facing measurements.

Internal storage is canonical metric (kg for weight, cm for height) across
the board (issue #469). Athletes pick `imperial` or `metric` on their
profile; the UI/entry boundary and the rx display layer convert via these
helpers so the canonical value never leaks the wrong unit into a prompt
or form.

`format_weight()` returns the display string used in templates and the
Layer 4 `load_prescription` text. Whole-number imperial is the common case
and prints cleanly ("185 lb" not "185.0 lb"); fractional kg rounds to 1 dp
for readability. Height (`display_height` / `entered_height_to_cm`) is a
single-field number — inches for imperial, cm for metric.
"""

from __future__ import annotations

from typing import Optional


# International avoirdupois pound, exact to 7 decimal places.
LB_PER_KG = 2.2046226218
KG_PER_LB = 0.45359237

# International inch (exact).
CM_PER_INCH = 2.54
INCH_PER_CM = 1.0 / CM_PER_INCH

IMPERIAL = 'imperial'
METRIC = 'metric'
UNIT_PREFERENCE_CHOICES = (IMPERIAL, METRIC)
DEFAULT_UNIT_PREFERENCE = IMPERIAL


def kg_to_lb(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) * LB_PER_KG


def lb_to_kg(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) * KG_PER_LB


def normalize_unit_preference(value: Optional[str]) -> str:
    """Coerce arbitrary input to a known choice; fall back to the default."""
    if value in UNIT_PREFERENCE_CHOICES:
        return value
    return DEFAULT_UNIT_PREFERENCE


def display_weight(value_kg: Optional[float], unit_pref: Optional[str]) -> Optional[float]:
    """Return `value_kg` converted to the athlete's display unit (raw number).

    Use this when populating a form input or chart series. For a labeled
    string ("185 lb"), call `format_weight()` instead.
    """
    if value_kg is None:
        return None
    pref = normalize_unit_preference(unit_pref)
    if pref == IMPERIAL:
        return kg_to_lb(value_kg)
    return float(value_kg)


def entered_weight_to_kg(value: Optional[float], unit_pref: Optional[str]) -> Optional[float]:
    """Convert a value entered in the athlete's preferred unit back to kg
    for canonical storage. Inverse of `display_weight`."""
    if value is None:
        return None
    pref = normalize_unit_preference(unit_pref)
    if pref == IMPERIAL:
        return lb_to_kg(value)
    return float(value)


def weight_unit_label(unit_pref: Optional[str]) -> str:
    """Short label for templates: 'lb' or 'kg'."""
    return 'lb' if normalize_unit_preference(unit_pref) == IMPERIAL else 'kg'


def format_weight(value_kg: Optional[float], unit_pref: Optional[str],
                  fallback: str = '') -> str:
    """Render a kg value as a display string in the athlete's unit.

    Imperial whole-number is the dominant case (plate weights, set targets):
    "185 lb". Kg fractional rounds to 1 dp ("84.0 kg") for readability.
    Returns `fallback` for None.
    """
    if value_kg is None:
        return fallback
    pref = normalize_unit_preference(unit_pref)
    if pref == IMPERIAL:
        lbs = kg_to_lb(value_kg)
        return f"{int(round(lbs))} lb"
    return f"{float(value_kg):.1f} kg"


# ─── Height (canonical cm) ────────────────────────────────────────────────


def cm_to_in(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) * INCH_PER_CM


def in_to_cm(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) * CM_PER_INCH


def display_height(value_cm: Optional[float], unit_pref: Optional[str]) -> Optional[float]:
    """Return `value_cm` converted to the athlete's display unit (in or cm)."""
    if value_cm is None:
        return None
    pref = normalize_unit_preference(unit_pref)
    if pref == IMPERIAL:
        return cm_to_in(value_cm)
    return float(value_cm)


def entered_height_to_cm(value: Optional[float], unit_pref: Optional[str]) -> Optional[float]:
    """Inverse of `display_height` — convert from athlete's unit to canonical cm."""
    if value is None:
        return None
    pref = normalize_unit_preference(unit_pref)
    if pref == IMPERIAL:
        return in_to_cm(value)
    return float(value)


def height_unit_label(unit_pref: Optional[str]) -> str:
    """Short label for templates: 'in' or 'cm'."""
    return 'in' if normalize_unit_preference(unit_pref) == IMPERIAL else 'cm'


# ─── Temperature (canonical °C) ───────────────────────────────────────────────
#
# Weather/climate values originate in metric (Open-Meteo returns °C). Imperial
# athletes see Fahrenheit so the weather display honors the same unit toggle as
# weight + height (issue #946).


def c_to_f(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) * 9.0 / 5.0 + 32.0


def f_to_c(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return (float(value) - 32.0) * 5.0 / 9.0


def display_temperature(value_c: Optional[float], unit_pref: Optional[str]) -> Optional[float]:
    """Return `value_c` converted to the athlete's display unit (°F or °C)."""
    if value_c is None:
        return None
    pref = normalize_unit_preference(unit_pref)
    if pref == IMPERIAL:
        return c_to_f(value_c)
    return float(value_c)


def temp_unit_label(unit_pref: Optional[str]) -> str:
    """Short label for templates: '°F' or '°C'."""
    return '°F' if normalize_unit_preference(unit_pref) == IMPERIAL else '°C'
