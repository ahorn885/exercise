"""Provider outbound — structured-workout serializers (#681 Wave 3b).

Turns a Layer-4 `PlanSession` (kind=='cardio') into a structured workout for a
destination platform. Two formats, one shared step model:

  - `to_zwo`            — Zwift `.zwo` XML (file download; no push API).
  - `to_tp_structure`   — TrainingPeaks `Structure` JSON (`POST /v2/workouts/plan`;
                          dispatched by the gated TP connector, Slice 2).

Design: `designs/ProviderOutbound_StructuredWorkout_681_Wave3b_BuildDesign_v1.md`.
Mappings transcribed from `specs/Provider_Inbound_Matrix_v2.md` §11.

**Anchor (load-bearing):** both targets take *percent-of-threshold*, never absolute
watts/bpm, and the athlete's FTP/LTHR are not reliably ingested
(`profile_extractors.extract_cycling_ftp_w_*` are `_EMPTY` stubs). So the
`intensity_zone` (Z1–Z5) is the serialization anchor — mapped to a %-band via the
fixed tables below (documented 5-zone defaults; env-overridable; verify-owed). The
absolute `intensity_target` is intentionally not used for the %.

Pure functions (no Flask, no DB) — the Zwift download route lives in
`routes/zwift.py`, the TP dispatch in `routes/trainingpeaks.py` (Slice 2).
"""
from __future__ import annotations

from typing import Any, NamedTuple
from xml.sax.saxutils import escape

from provider_cardio_resolve import DISCIPLINE_TO_PLAN_SPORT

# Zone → %-of-threshold bands (low, high). Single targets use the midpoint;
# ramps (warmup/cooldown) use the band. Documented standard 5-zone models
# (power: British-Cycling/Coggan %FTP; HR: Friel %LTHR) — env-overridable.
_ZONE_TO_PCT_FTP: dict[str, tuple[float, float]] = {
    'Z1': (0.50, 0.55),
    'Z2': (0.56, 0.75),
    'Z3': (0.76, 0.90),
    'Z4': (0.91, 1.05),
    'Z5': (1.06, 1.20),
}
_ZONE_TO_PCT_LTHR: dict[str, tuple[float, float]] = {
    'Z1': (0.70, 0.85),
    'Z2': (0.85, 0.89),
    'Z3': (0.90, 0.94),
    'Z4': (0.95, 0.99),
    'Z5': (1.00, 1.06),
}
# 'mixed' zone → steady aerobic (Z2) fallback (never crash).
_MIXED_FALLBACK = 'Z2'

# coarse `_plan_sport_type` → Zwift `sportType` (Zwift only does bike/run).
_COARSE_TO_ZWIFT_SPORT: dict[str, str] = {'cycling': 'bike', 'running': 'run'}


def is_zwift_exportable(discipline_id: str | None) -> bool:
    """True if a cardio session of this discipline can render a Zwift `.zwo`
    (bike/run disciplines only). Used to gate the download link in the plan view."""
    return DISCIPLINE_TO_PLAN_SPORT.get(discipline_id or '') in _COARSE_TO_ZWIFT_SPORT


class Step(NamedTuple):
    """One provider-agnostic workout step. Intervals carry rep/rest fields."""
    kind: str                 # warmup|main_set|cooldown|interval_set|transition
    duration_s: int           # work seconds (per rep for interval_set)
    zone: str                 # Z1..Z5 (mixed already collapsed)
    label: str
    reps: int | None = None
    rest_duration_s: int | None = None
    rest_zone: str | None = None


def _zone(z: str) -> str:
    return z if z in _ZONE_TO_PCT_FTP else _MIXED_FALLBACK


def _band(table: dict[str, tuple[float, float]], zone: str) -> tuple[float, float]:
    return table[_zone(zone)]


def _mid(table: dict[str, tuple[float, float]], zone: str) -> float:
    lo, hi = _band(table, zone)
    return round((lo + hi) / 2, 3)


def session_to_steps(session: dict[str, Any]) -> list[Step]:
    """Flatten a cardio `PlanSession` dict's `cardio_blocks` into `Step`s.

    Raises ValueError if the session is not an exportable cardio session.
    """
    kind = session.get('kind')
    if kind != 'cardio':
        raise ValueError(f"session kind={kind!r} is not exportable (cardio only)")
    blocks = session.get('cardio_blocks') or []
    if not blocks:
        raise ValueError("cardio session has no cardio_blocks")

    steps: list[Step] = []
    for b in blocks:
        bkind = b.get('block_kind')
        dur_s = int(b.get('duration_min', 0)) * 60
        zone = _zone(b.get('intensity_zone', _MIXED_FALLBACK))
        label = (b.get('instructions') or bkind or '').strip()[:120]
        if bkind == 'interval_set':
            steps.append(Step(
                kind=bkind, duration_s=dur_s, zone=zone, label=label,
                reps=int(b.get('repetitions') or 1),
                rest_duration_s=int(b.get('rest_between_min') or 0) * 60,
                rest_zone=_zone(b.get('rest_intensity_zone', 'Z1')),
            ))
        else:
            steps.append(Step(kind=bkind, duration_s=dur_s, zone=zone, label=label))
    return steps


def _coarse_sport(session: dict[str, Any]) -> str | None:
    return DISCIPLINE_TO_PLAN_SPORT.get(session.get('discipline_id') or '')


def _workout_title(session: dict[str, Any]) -> str:
    name = session.get('discipline_name') or session.get('kind') or 'Workout'
    date = session.get('date') or ''
    return f"AIDSTATION {name} {date}".strip()


# ─── Zwift .zwo ────────────────────────────────────────────────────────────


def to_zwo(session: dict[str, Any]) -> str:
    """Serialize a cardio session to a Zwift `.zwo` workout file (XML string).

    `sportType` from the coarse discipline (cycling→bike, running→run); any other
    discipline raises ValueError (Zwift has no other sport). `Power` is a fraction
    of FTP from the zone→%FTP band.
    """
    steps = session_to_steps(session)
    coarse = _coarse_sport(session)
    sport = _COARSE_TO_ZWIFT_SPORT.get(coarse or '')
    if sport is None:
        raise ValueError(
            f"discipline {session.get('discipline_id')!r} (coarse={coarse!r}) "
            "is not Zwift-exportable (bike/run only)"
        )

    title = _workout_title(session)
    out: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>', '<workout_file>']
    out.append(f'  <author>AIDSTATION</author>')
    out.append(f'  <name>{escape(title)}</name>')
    out.append(
        '  <description>Exported from AIDSTATION. Power targets are %FTP derived '
        'from prescribed intensity zones (Z1-Z5) — tune to your FTP.</description>'
    )
    out.append(f'  <sportType>{sport}</sportType>')
    out.append('  <workout>')
    for s in steps:
        out.append('    ' + _zwo_block(s))
    out.append('  </workout>')
    out.append('</workout_file>')
    xml = '\n'.join(out)
    print(
        f"[outbound-zwo] session={session.get('session_id')} sport={sport} "
        f"blocks={len(steps)} -> .zwo bytes={len(xml)}"
    )
    return xml


def _pf(v: float) -> str:
    return f"{v:.3f}"


def _zwo_block(s: Step) -> str:
    lo, hi = _band(_ZONE_TO_PCT_FTP, s.zone)
    mid = _mid(_ZONE_TO_PCT_FTP, s.zone)
    if s.kind == 'warmup':
        return (f'<Warmup Duration="{s.duration_s}" PowerLow="{_pf(lo)}" '
                f'PowerHigh="{_pf(hi)}"/>')
    if s.kind == 'cooldown':
        return (f'<Cooldown Duration="{s.duration_s}" PowerLow="{_pf(hi)}" '
                f'PowerHigh="{_pf(lo)}"/>')
    if s.kind == 'interval_set':
        off_mid = _mid(_ZONE_TO_PCT_FTP, s.rest_zone or 'Z1')
        return (f'<IntervalsT Repeat="{s.reps}" OnDuration="{s.duration_s}" '
                f'OffDuration="{s.rest_duration_s}" OnPower="{_pf(mid)}" '
                f'OffPower="{_pf(off_mid)}"/>')
    # main_set, transition → steady
    return f'<SteadyState Duration="{s.duration_s}" Power="{_pf(mid)}"/>'


# ─── TrainingPeaks Structure (Slice 2 consumer) ────────────────────────────


_TP_INTENSITY_CLASS = {
    'warmup': 'WarmUp',
    'cooldown': 'CoolDown',
    'main_set': 'Active',
    'interval_set': 'Active',
    'transition': 'Active',
}


def to_tp_structure(session: dict[str, Any]) -> dict[str, Any]:
    """Serialize a cardio session to a TrainingPeaks `Structure` object
    (`POST /v2/workouts/plan`). %FTP for cycling, %ThresholdHr otherwise.

    Pure function; dispatched by the gated TP connector (Slice 2).
    """
    steps = session_to_steps(session)
    coarse = _coarse_sport(session)
    if coarse == 'cycling':
        table, unit = _ZONE_TO_PCT_FTP, 'PercentOfFtp'
    else:
        table, unit = _ZONE_TO_PCT_LTHR, 'PercentOfThresholdHr'

    structure: list[dict[str, Any]] = []
    for s in steps:
        if s.kind == 'interval_set':
            work = _tp_step(s.kind, s.duration_s, s.zone, table, unit, s.label)
            rest = _tp_step('transition', s.rest_duration_s or 0,
                            s.rest_zone or 'Z1', table, unit, 'recovery')
            structure.append({
                'Type': 'Repetition',
                'Length': {'Value': int(s.reps or 1), 'Unit': 'Repetition'},
                'Steps': [work, rest],
            })
        else:
            structure.append(_wrap_single_step(
                _tp_step(s.kind, s.duration_s, s.zone, table, unit, s.label)))
    print(
        f"[outbound-tp] session={session.get('session_id')} coarse={coarse} "
        f"unit={unit} steps={len(structure)}"
    )
    return {
        'Structure': structure,
        'IntensityTargetType': unit,
    }


def _wrap_single_step(step: dict[str, Any]) -> dict[str, Any]:
    """A single (non-repeated) step is a Repetition of one (TP's Structure shape)."""
    return {'Type': 'Repetition', 'Length': {'Value': 1, 'Unit': 'Repetition'},
            'Steps': [step]}


def _tp_step(kind: str, duration_s: int, zone: str,
             table: dict[str, tuple[float, float]], unit: str, label: str) -> dict[str, Any]:
    lo, hi = _band(table, zone)
    return {
        'Name': (label or kind)[:64],
        'Length': {'Value': int(duration_s), 'Unit': 'Second'},
        'IntensityClass': _TP_INTENSITY_CLASS.get(kind, 'Active'),
        'IntensityTarget': {
            'Unit': unit,
            'MinValue': round(lo * 100, 1),
            'MaxValue': round(hi * 100, 1),
        },
    }
