"""Canonical catalog of curated evidence sources (#826).

Single source of truth for two consumers, so they can never drift:

* `init_db` seeds the `evidence_sources` table from `seed_rows()`.
* The Layer 3A / 3B builders render `citable_catalog()` into their prompts as
  the allowlist the LLM may cite from.

Because both read from here, every slug the model is told about is exactly a
slug that exists in the store — the constrained-citation rule. Persistence
still validates cited slugs against the live DB (see
`evidence_repo.record_plan_evidence_citations`), so an operator removing a
source, or the model inventing one, is caught and flagged for curation.

Each row: (slug, kind, title, summary, citation, url, is_baseline).
`kind` is one of study | guideline | expert_coach (the table CHECK enforces it).
`is_baseline=True` marks the house-methodology sources auto-linked to every
plan; the rest are specific sources the Layer 3 LLM cites selectively.
"""

from __future__ import annotations

_SOURCES: list[tuple[str, str, str, str, str, str | None, bool]] = [
    # ─── Baseline — the house methodology every periodized plan rests on. ────
    (
        "periodization-foundations", "expert_coach",
        "Periodized training structure",
        "Plans are organized into Base → Build → Peak → Taper phases that "
        "progressively develop fitness then sharpen it for the goal date, the "
        "foundational model behind every generated plan.",
        "Bompa, T.O. & Haff, G.G. Periodization: Theory and Methodology of "
        "Training (5th ed.). Human Kinetics.",
        None, True,
    ),
    (
        "polarized-intensity", "study",
        "Polarized training-intensity distribution",
        "Endurance work is weighted toward easy aerobic volume with a smaller "
        "share of high-intensity work, which outperforms threshold-heavy "
        "distributions for most endurance athletes.",
        "Seiler, S. (2010). What is best practice for training intensity and "
        "duration distribution in endurance athletes? Int J Sports Physiol "
        "Perform, 5(3), 276-291.",
        None, True,
    ),
    (
        "progressive-overload", "guideline",
        "Progressive overload in resistance training",
        "Strength and load are advanced gradually and systematically rather "
        "than all at once, the basis for how week-over-week load is stepped up.",
        "ACSM Position Stand: Progression Models in Resistance Training for "
        "Healthy Adults. Med Sci Sports Exerc, 41(3), 687-708 (2009).",
        None, True,
    ),
    (
        "tapering-peak", "study",
        "Tapering before the goal event",
        "A pre-event reduction in training volume while preserving intensity "
        "restores freshness and improves performance, the basis for the Taper "
        "phase shape.",
        "Bosquet, L. et al. (2007). Effects of tapering on performance: a "
        "meta-analysis. Med Sci Sports Exerc, 39(8), 1358-1365.",
        None, True,
    ),
    (
        "recovery-adaptation", "guideline",
        "Recovery and the overload-adaptation cycle",
        "Adaptation happens during recovery, so rest days and lighter weeks are "
        "scheduled deliberately to let the prescribed load translate into "
        "fitness and to manage injury risk.",
        "Kellmann, M. et al. (2018). Recovery and Performance in Sport: "
        "Consensus Statement. Int J Sports Physiol Perform, 13(2), 240-245.",
        None, True,
    ),
    # ─── Non-baseline — specific sources the Layer 3 LLM cites selectively ───
    # when a particular athlete's state or goal makes them relevant.
    (
        "acwr-injury-risk", "study",
        "Acute:chronic workload ratio and injury risk",
        "Spikes in training load relative to the recent chronic average raise "
        "injury risk — the basis for flagging an aggressive ramp in an "
        "athlete's recent trajectory.",
        "Gabbett, T.J. (2016). The training-injury prevention paradox. Br J "
        "Sports Med, 50(5), 273-280.",
        None, False,
    ),
    (
        "zone2-aerobic-base", "expert_coach",
        "Zone 2 aerobic base development",
        "A large base of low-intensity aerobic work builds mitochondrial and "
        "cardiovascular capacity that underpins later high-intensity work — "
        "relevant when aerobic capacity is the limiter.",
        "Seiler, S. & Tønnessen, E. (2009). Intervals, thresholds, and long "
        "slow distance: the role of intensity and duration in endurance "
        "training. Sportscience, 13, 32-53.",
        None, False,
    ),
    (
        "vo2max-intervals", "study",
        "High-intensity intervals for VO2max",
        "Appropriately dosed high-intensity intervals are the most potent "
        "stimulus for raising VO2max — relevant when peak aerobic power is the "
        "judgment's limiter.",
        "Bacon, A.P. et al. (2013). VO2max trainability and high intensity "
        "interval training in humans: a meta-analysis. PLoS One, 8(9), e73182.",
        None, False,
    ),
    (
        "lactate-threshold-training", "study",
        "Lactate / functional threshold development",
        "Threshold work raises the intensity an athlete can sustain — relevant "
        "when the goal is paced near threshold or threshold is the limiter.",
        "Faude, O., Kindermann, W. & Meyer, T. (2009). Lactate threshold "
        "concepts: how valid are they? Sports Med, 39(6), 469-490.",
        None, False,
    ),
    (
        "strength-for-endurance", "study",
        "Concurrent strength training for endurance performance",
        "Heavy or explosive strength work improves endurance economy and "
        "performance without harming aerobic gains — relevant when strength is "
        "a weak link for an endurance goal.",
        "Beattie, K. et al. (2014). The effect of strength training on "
        "performance in endurance athletes. Sports Med, 44(6), 845-865.",
        None, False,
    ),
    (
        "heat-acclimation", "guideline",
        "Heat acclimation for hot-weather events",
        "Progressive heat exposure over ~1-2 weeks improves thermoregulation "
        "and performance in the heat — relevant when the goal event is hot.",
        "Racinais, S. et al. (2015). Consensus recommendations on training and "
        "competing in the heat. Scand J Med Sci Sports, 25(S1), 6-19.",
        None, False,
    ),
    (
        "altitude-training", "study",
        "Altitude training and acclimatization",
        "Living and/or training at altitude alters oxygen carrying capacity and "
        "needs deliberate acclimatization — relevant when the event or the "
        "athlete's environment is at altitude.",
        "Millet, G.P. et al. (2010). Combining hypoxic methods for peak "
        "performance. Sports Med, 40(1), 1-25.",
        None, False,
    ),
    (
        "masters-athlete-recovery", "study",
        "Masters-athlete recovery and adaptation",
        "Older athletes generally need more recovery between hard sessions and "
        "respond well to maintained intensity — relevant when age shapes the "
        "recovery and load assumptions.",
        "Lepers, R. & Stapley, P.J. (2016). Master athletes are extending the "
        "limits of human endurance. Front Physiol, 7, 613.",
        None, False,
    ),
    (
        "female-athlete-health", "guideline",
        "Female-athlete energy availability and health",
        "Adequate energy availability protects bone, hormonal, and performance "
        "health (RED-S) — relevant when assessing load tolerance and recovery "
        "for female athletes.",
        "Mountjoy, M. et al. (2018). IOC consensus statement on Relative Energy "
        "Deficiency in Sport (RED-S): 2018 update. Br J Sports Med, 52, 687-697.",
        None, False,
    ),
    (
        "sleep-and-performance", "study",
        "Sleep, recovery, and athletic performance",
        "Sufficient sleep is a primary recovery lever; chronic restriction "
        "degrades performance and raises injury/illness risk — relevant when "
        "lifestyle constraints affect recovery capacity.",
        "Walsh, N.P. et al. (2021). Sleep and the athlete: narrative review and "
        "consensus recommendations. Br J Sports Med, 55(7), 356-368.",
        None, False,
    ),
    (
        "detraining-reversibility", "study",
        "Detraining and reversibility of fitness",
        "Fitness declines measurably after a training interruption, with "
        "aerobic and strength qualities fading at different rates — relevant "
        "when a layoff or low-density history shapes the starting point.",
        "Mujika, I. & Padilla, S. (2000). Detraining: loss of training-induced "
        "adaptations. Sports Med, 30(2), 79-87 & 145-154.",
        None, False,
    ),
]


def seed_rows() -> list[tuple[str, str, str, str, str, str | None, bool]]:
    """Rows for `init_db` executemany:
    (slug, kind, title, summary, citation, url, is_baseline)."""
    return list(_SOURCES)


def citable_catalog() -> list[dict[str, str]]:
    """slug / kind / title / summary for prompt injection — the allowlist the
    Layer 3 LLM may cite from. Returns every source (baseline + non-baseline);
    the model selects whichever back its judgments for this athlete."""
    return [
        {"slug": s[0], "kind": s[1], "title": s[2], "summary": s[3]}
        for s in _SOURCES
    ]


def all_slugs() -> set[str]:
    """Every catalog slug — used by tests + the prompt-citation guardrail."""
    return {s[0] for s in _SOURCES}


def render_catalog_block() -> str:
    """The research-source catalog as a prompt block — one line per source,
    `slug — title: summary`. Injected into the Layer 3A / 3B user prompts so
    the LLM cites slugs (in `source_citations`) only from this allowlist."""
    lines = [
        "Research-source catalog (cite slugs in `source_citations`; use ONLY "
        "these slugs, never invent one):",
    ]
    for s in _SOURCES:
        slug, _kind, title, summary = s[0], s[1], s[2], s[3]
        lines.append(f"- {slug} — {title}: {summary}")
    return "\n".join(lines)
