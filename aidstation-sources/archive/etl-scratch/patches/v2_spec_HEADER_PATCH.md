# Header patch — Athlete_Onboarding_Data_Spec_v2.md

Two surgical replacements at the top of the doc. Apply both before the §I-onwards integration.

---

## Patch 1 — Status line

**Find** (near the top, under the `# Athlete Onboarding Data Spec — v2` heading):

```
**Version:** 2.0
**Status:** Partial draft. Batches 1–3 complete (structural reorg + §A through §H). §I–§L pending in batch 4; §L (Athlete Network) + Account Config + Plan Management pending in batch 5. Open Items review completed May 2026 — see Resolved decisions log.
```

**Replace with:**

```
**Version:** 2.1
**Status:** Batches 1–5 complete. Spec body complete pending Open Items.
**Last updated:** 2026-05-06 (batch 4+5 integration)
```

> If the older draft variant is present (the one without the "Open Items review completed" sentence), match the shorter Status line and replace the same way.

---

## Patch 2 — Drafting status table

**Find** (in the `# Drafting status` section near the top of the doc):

```
| Section / Group | Status | Source |
|---|---|---|
| Front matter, structural reorg, Connected Services convention | ✅ Drafted (batch 1) | This pass |
| §A Athlete Identity + A.1 Disclosures | ✅ Drafted (batch 1) | This pass |
| §B Health Status (B, B.1, B.1.1, B.2, B.3, B.4, B.4.1, B.4.2) | ✅ Drafted (batch 1) | This pass |
| §C Training History & Fitness Baseline | ✅ Drafted (batch 2) | This pass |
| §D Discipline-Specific Baselines | ✅ Drafted (batch 2) | This pass |
| §E Strength, Core & Balance Benchmarks | ✅ Drafted (batch 2) | This pass |
| §F Performance Testing | ✅ Drafted (batch 3) | This pass |
| §G Schedule & Availability | ✅ Drafted (batch 3) | This pass |
| §H Target Events | ✅ Drafted (batch 3) | This pass |
| §I Lifestyle & Recovery | ⏳ Pending | Batch 4 |
| §J Locales | ⏳ Pending | Batch 4 |
| §K Locale Schedule | ⏳ Pending | Batch 4 |
| §L Athlete Network | ⏳ Pending | Batch 5 |
| Group 2 — Account Configuration | ⏳ Pending | Batch 5 (or its own pass) |
| Group 3 — Plan Management | ⏳ Pending | Batch 5+ |
```

**Replace with:**

```
| Section / Group | Status | Source |
|---|---|---|
| Front matter, structural reorg, Connected Services convention | ✅ Drafted (batch 1) | v2 drafting |
| §A Athlete Identity + A.1 Disclosures | ✅ Drafted (batch 1) | v2 drafting |
| §B Health Status (B, B.1, B.1.1, B.2, B.3, B.4, B.4.1, B.4.2) | ✅ Drafted (batch 1) | v2 drafting |
| §C Training History & Fitness Baseline | ✅ Drafted (batch 2) | v2 drafting |
| §D Discipline-Specific Baselines | ✅ Drafted (batch 2) | v2 drafting |
| §E Strength, Core & Balance Benchmarks | ✅ Drafted (batch 2) | v2 drafting |
| §F Performance Testing | ✅ Drafted (batch 3) | v2 drafting |
| §G Schedule & Availability | ✅ Drafted (batch 3) | v2 drafting |
| §H Target Events | ✅ Drafted (batch 3) | v2 drafting |
| §I Lifestyle & Recovery | ✅ Drafted (batch 4) | v2 drafting |
| §J Locales | ✅ Drafted (batch 4) | v2 drafting |
| §K Locale Schedule | ✅ Drafted (batch 4) | v2 drafting |
| §L Athlete Network | ✅ Drafted (batch 5) | v2 drafting |
| Group 2 — Account Configuration | ✅ Drafted (batch 5) | v2 drafting |
| Group 3 — Plan Management | ✅ Drafted (batch 5) | v2 drafting |
```

Optionally remove the "Reassess pace after each batch..." line that follows the table — it's no longer relevant. Or leave it as historical context.

---

## After both patches + the §I-onwards integration

- Save the file as `Athlete_Onboarding_Data_Spec_v2.md` (overwrite — the version inside is now 2.1).
- Upload the updated file to the project.
- Old version stays in chat history if you need to diff.
