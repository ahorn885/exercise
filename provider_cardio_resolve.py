"""Resolve a logged cardio activity TYPE to its canonical layer0 discipline (#681 §4 Slice 2).

The cardio-fidelity sibling of `provider_strength_resolve` (strength NAME → EX-id).
A completed cardio activity arrives carrying a provider-specific activity type
(Strava `TrailRun`, RWGPS `cycling:gravel`, Wahoo `workout_type_id=4`,
TrainingPeaks `mtb`, …). Matrix-v2 §1 ratified **option C**: store the fine
layer0 discipline id where one exists, derive the coarse `_plan_sport_type` via a
deterministic collapse. This module is that resolution:

    1. DISCIPLINE — the provider type maps to a fine layer0 D-id
                    (`provider_value_map_seed.CARDIO_DISCIPLINE_MAP`). The coarse
                    `_plan_sport_type` is DERIVED via `DISCIPLINE_TO_PLAN_SPORT`
                    below — bucket 1.
    2. MODALITY   — a real activity with no race-discipline D-id but a coarse home
                    (walking, strength_training) → coarse-only, no D-id — bucket 1.
    3. BUCKET-3   — explicitly-recorded known-unmapped (e.g. Rowing, mint reversed
                    2026-06-18) OR any type not in the seed at all → no canonical
                    discipline, record raw (record-don't-drop) — bucket 3.

It mirrors `provider_strength_resolve`'s as-built shape (#681 §4 Slice 1): a pure
function reading the consolidated `provider_value_map_seed` module (the same data
`init_db` materializes into the `provider_value_map` table, so the in-process path
and the table cannot drift). No DB read on the resolution path; the Rule #15
decision log lands at the cardio-ingest call site that wires this in (Slice 2b),
not in this pure function.

Per `designs/ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` §6 +
`specs/Provider_Inbound_Matrix_v2.md` §1 (option C, Andy-ratified).
"""

from __future__ import annotations

from typing import NamedTuple

from provider_value_map_seed import CARDIO_DISCIPLINE_MAP


# Fine layer0 discipline id → coarse `_plan_sport_type` (matrix-v2 §1 option C;
# ratified Q3 as a canon-internal dict next to the resolver, NOT value-map rows).
# The collapse is deterministic and lossless (fine→coarse only; the reverse isn't,
# which is why we store the fine id). Disciplines with NO coarse home — the
# paddle / climb / ski / OCR multisport set (D-009/010/011/012/013/014/019/021/
# 022/027/028/032) — are intentionally ABSENT: they collapse to None (fine-only),
# preserving the skimo/paddle/climb signal the coarse 6-value set would discard.
DISCIPLINE_TO_PLAN_SPORT: dict[str, str] = {
    # running family
    'D-001': 'running',   # Trail Running
    'D-002': 'running',   # Road Running
    'D-024': 'running',   # Mountain Running
    # cycling family
    'D-006': 'cycling',   # Road Cycling
    'D-007': 'cycling',   # Time-Trial Cycling
    'D-008': 'cycling',   # Mountain Biking
    'D-030': 'cycling',   # Gravel Cycling
    'D-031': 'cycling',   # Cross Country Cycling
    # swimming
    'D-004': 'swimming',  # Swimming
    # hiking / trek family
    'D-003': 'hiking',    # Trekking
    'D-017': 'hiking',    # Snowshoeing
    'D-018': 'hiking',    # Mountaineering
}


class CardioResolution(NamedTuple):
    """The outcome of resolving a (provider, activity-type) pair.

    discipline_id    — fine layer0 D-id, or None (coarse-only / bucket-3).
    plan_sport_type  — coarse `_plan_sport_type` for plan-item matching, or None.
    bucket           — 1 (mapped) | 3 (record raw, no canonical discipline).
    match_kind       — 'manual' for an authored row, None for an unseeded type.
    """
    discipline_id: str | None
    plan_sport_type: str | None
    bucket: int
    match_kind: str | None


def resolve_cardio_discipline(provider: str, source_value: str | None) -> CardioResolution:
    """Resolve a provider cardio activity type to (discipline_id, coarse, bucket).

    `provider` is the lowercase provider key ('strava'|'rwgps'|'wahoo'|
    'trainingpeaks'|...); `source_value` is the provider's activity-type token
    (enum string, namespaced family:variant, or a `workout_type_id` as a string).
    An unmapped or empty type resolves to bucket-3 (record-don't-drop) — never
    raises, never force-maps.
    """
    entry = CARDIO_DISCIPLINE_MAP.get((provider or '').lower(), {}).get(source_value or '')
    if entry is None:
        return CardioResolution(None, None, 3, None)

    kind, value = entry
    if kind == 'discipline':
        return CardioResolution(value, DISCIPLINE_TO_PLAN_SPORT.get(value), 1, 'manual')
    if kind == 'modality':
        return CardioResolution(None, value, 1, 'manual')
    # 'bucket3' — explicitly-recorded known-unmapped (e.g. Rowing, §6/§12)
    return CardioResolution(None, None, 3, 'manual')
