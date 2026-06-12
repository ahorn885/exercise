# §B.4.2 Rule 3 sex-adjustment addendum

**Supersedes:** the Rule 3 trigger table and the "Out of scope" entry on sex-specific RHR bands in `v2_spec_SECTION_B_PATCH_v2.md`.

Two surgical changes within §B.4.2 Rule 3. Everything else in the prior patch (Rules 1, 2, suppression behaviour, dismissal memory, confidence note) stays.

---

## Change 1 — Replace Rule 3 trigger table

**Find** (in the Rule 3 — RHR outlier sub-section):

```
**Trigger conditions** (any one fires the suggestion):

| Condition | Threshold | Notes |
|---|---|---|
| **Sustained tachycardia at rest** | 7-day rolling average RHR > 100 bpm | Suppressed if any of the following is logged within the same 7-day window: illness, fever, recent caffeine spike, ACWR > 1.5 (training overload), severe sleep deprivation. AHA standard tachycardia threshold |
| **Symptomatic bradycardia** | RHR < 40 bpm AND athlete has logged within the past 14 days any of: dizziness, syncope, unexplained fatigue, exercise intolerance, chest discomfort, palpitations | RHR < 40 bpm alone is normal in trained endurance athletes (up to 80% of endurance athletes develop sinus bradycardia). The trigger is the symptom pairing, not the rate |
| **Sustained baseline shift upward** | 30-day rolling average RHR > 10 bpm above the prior 90-day baseline | Only fires after a 90-day baseline is established (≥60 days of data in the last 90). Suppressed if illness, ACWR > 1.5, or recent significant detraining is logged |
| **First-entry extreme outlier** | Initial RHR > 100 bpm or < 35 bpm AND no training history sufficient to explain the value (Years of Structured Training < 1 in primary endurance discipline, OR primary discipline is non-endurance) | One-time check at first RHR entry. Above 100 bpm: suggests evaluation regardless of training. Below 35 bpm: suggests evaluation when not explained by endurance training history |
```

**Replace with:**

```
**Sex-based threshold adjustment:**

Women have an average resting heart rate approximately 5 bpm higher than men in large population cohorts (Health eHeart Study, n=66,800: ~4 bpm difference; Fasa PERSIAN cohort: ~5 bpm difference). Bradycardia thresholds are adjusted upward by 5 bpm for athletes with §A Sex = Female to maintain symmetric outlier sensitivity. Tachycardia thresholds (clinical definition 100 bpm per AHA) are sex-agnostic. Baseline shift triggers are inherently self-correcting for sex (the athlete's own baseline is the reference).

Athletes whose §A Sex is unspecified or marked Other use the male thresholds as a conservative default (lower bradycardia trigger threshold = fewer false positives for athletes with naturally lower baselines).

**Trigger conditions** (any one fires the suggestion):

| Condition | Threshold (Male / Other / Unspecified) | Threshold (Female) | Notes |
|---|---|---|---|
| **Sustained tachycardia at rest** | 7-day rolling average RHR > 100 bpm | Same — 100 bpm | Sex-agnostic per AHA clinical tachycardia definition. Suppressed if any of the following is logged within the same 7-day window: illness, fever, recent caffeine spike, ACWR > 1.5 (training overload), severe sleep deprivation |
| **Symptomatic bradycardia** | RHR < 40 bpm AND athlete has logged within the past 14 days any of: dizziness, syncope, unexplained fatigue, exercise intolerance, chest discomfort, palpitations | RHR < **45 bpm** AND same symptom set | RHR below the threshold alone is normal in trained endurance athletes (up to 80% of endurance athletes develop sinus bradycardia). The trigger is the symptom pairing, not the rate. The 5-bpm sex offset reflects the higher female baseline |
| **Sustained baseline shift upward** | 30-day rolling average RHR > 10 bpm above the prior 90-day baseline | Same — 10 bpm above own baseline | Inherently self-correcting for sex (uses the athlete's own baseline). Only fires after a 90-day baseline is established (≥60 days of data in the last 90). Suppressed if illness, ACWR > 1.5, or recent significant detraining is logged |
| **First-entry extreme outlier** | Initial RHR > 100 bpm OR < 35 bpm AND no training history sufficient to explain the value (Years of Structured Training < 1 in primary endurance discipline, OR primary discipline is non-endurance) | Initial RHR > 100 bpm OR < **40 bpm** AND same training-history condition | One-time check at first RHR entry. Upper threshold sex-agnostic (clinical tachycardia). Lower threshold sex-adjusted to maintain equivalent outlier sensitivity |
```

---

## Change 2 — Update the "Out of scope for launch" entry

**Find** (in the Rule 3 — RHR outlier sub-section):

```
- Sex-specific or age-specific RHR band refinements (e.g., adjusting upper threshold downward for athletes >50). Defer until enough launch data confirms the symmetric thresholds above are not generating excess false positives in any demographic.
```

**Replace with:**

```
- **Age-specific** RHR band refinements (e.g., adjusting upper threshold downward for athletes >50). Defer until enough launch data confirms whether age adjustment is warranted on top of sex adjustment. Resting heart rate rises only ~1–2 bpm per decade in adults (Health eHeart Study), so the absolute thresholds may remain valid across age bands without explicit adjustment, but launch data should confirm.
- Pregnancy-state RHR adjustments. Pregnancy elevates resting heart rate by 10–20 bpm during the second and third trimesters; the system does not currently track pregnancy state on the athlete profile, so the trigger may produce false positives for pregnant athletes. Athletes can dismiss the suggestion with no system-side memory penalty in this case, but a future profile field for pregnancy state could suppress the trigger automatically. Tracked as a post-launch design item.
```

---

## After applying

- Bump version. Save. Upload.
- The rest of the prior §B patches still apply.

## Confidence note for this addendum

The +5 bpm female adjustment is well-supported by large-cohort data (Health eHeart Study n=66,800; Fasa PERSIAN cohort) clustering around 4–6 bpm. Smaller and demographically narrower cohorts report wider ranges (8–11 bpm), but the conservative middle-of-the-credible-range value (5 bpm) is the right pick for a launch heuristic. Tune from launch data if needed.

The pregnancy carve-out is a known gap in the trigger logic. The system can't suppress the trigger automatically without pregnancy state on the profile, but acknowledging the gap (and giving athletes a clean dismiss path with no memory penalty) is better than silently false-positive-ing them. Adding pregnancy state to the profile is a separate design discussion.
