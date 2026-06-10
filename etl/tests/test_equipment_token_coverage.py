"""Guard against equipment-token / canonical drift (V4c).

Layer 2C matching is exact-string set membership against the athlete's pool,
and the pool is built from layer0 *canonical* equipment names (sentence-case)
plus enabled readiness toggles. So every equipment token an exercise (Tier-1)
or a non-improvised substitute (Tier-2) requires MUST be either an active
equipment canonical or a toggle name — otherwise the exercise silently fails to
match for everyone, with no error.

This is the check that was missing when the audit's documented col-7 -> canonical
renames were never wired into `_RENAME`: ~29 Title-case tokens (`Ab Wheel` vs
`Ab wheel`, etc.) leaked through and orphaned. Keep this test green.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from etl.layer0.extractors import exercise_db
from etl.layer0.extractors.vocabulary import parse_vocabulary_md
from etl.layer0.run import EXERCISES_XLSX, VOCAB_MD
from etl.layer0.vocabulary_transforms import _RENAME, _ROLLUP


def _valid_pool_tokens() -> set[str]:
    vocab = parse_vocabulary_md(VOCAB_MD)
    canonicals = {e["canonical_name"] for e in vocab["equipment_items"]}
    toggles = set(_ROLLUP.values())  # toggle names enter the pool when enabled
    return canonicals | toggles


def _flatten(eq) -> list[str]:
    out: list[str] = []
    for grp in eq or []:
        out.extend(grp if isinstance(grp, list) else [grp])
    return out


@pytest.fixture(scope="module")
def emitted():
    wb = exercise_db.open_workbook(EXERCISES_XLSX)
    exercises = exercise_db.extract_exercises(wb["Exercise Master"])
    substitutes = exercise_db.load_parsed_substitutes_structured()
    return exercises, substitutes


def test_tier1_exercise_tokens_all_resolve(emitted):
    """Every exercise equipment_required token resolves to a pool member."""
    exercises, _ = emitted
    valid = _valid_pool_tokens()
    orphans: dict[str, int] = {}
    for ex in exercises:
        for tok in _flatten(ex.get("equipment_required")):
            if tok not in valid:
                orphans[tok] = orphans.get(tok, 0) + 1
    assert not orphans, (
        "Exercise equipment tokens with no matching canonical/toggle "
        f"(silently unmatchable): {dict(sorted(orphans.items()))}"
    )


def test_tier2_substitute_tokens_all_resolve(emitted):
    """Every non-improvised substitute CNF token resolves to a pool member.

    Improvised substitutes (🏠) bypass the Tier-2 pool check by design, so they
    are exempt."""
    _, substitutes = emitted
    valid = _valid_pool_tokens()
    orphans: dict[str, int] = {}
    for subs in substitutes.values():
        for sub in subs:
            if sub.get("is_improvised"):
                continue
            for tok in _flatten(sub.get("equipment_required")):
                if tok not in valid:
                    orphans[tok] = orphans.get(tok, 0) + 1
    assert not orphans, (
        "Substitute equipment tokens with no matching canonical/toggle: "
        f"{dict(sorted(orphans.items()))}"
    )


def test_rename_rollup_targets_are_canonical_or_toggle():
    """Each transform target must itself be a valid pool token, so a token that
    hits a rename/rollup lands on something matchable. (`race belt)` -> `Race
    belt` is a known dormant, unreferenced typo-fix entry — race belts are not
    tracked equipment — and is excluded.)"""
    valid = _valid_pool_tokens()
    known_dormant = {"race belt)"}
    bad_rename = {
        k: v for k, v in _RENAME.items() if k not in known_dormant and v not in valid
    }
    bad_rollup = {k: v for k, v in _ROLLUP.items() if v not in valid}
    assert not bad_rename, f"_RENAME values not a canonical/toggle: {bad_rename}"
    assert not bad_rollup, f"_ROLLUP values not a canonical/toggle: {bad_rollup}"
