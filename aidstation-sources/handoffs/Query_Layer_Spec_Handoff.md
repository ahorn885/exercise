# Onboarding Spec Closeout + Query Layer Pickup — Session Handoff

**Date:** 2026-05-06
**Predecessor:** `Post_ETL_Onboarding_Handoff.md`
**Status:** Onboarding spec body integration complete pending Andy's file application. Three additional in-spec decisions integrated. Spec body genuinely complete after patches applied.
**Next chat starts with:** Query layer spec (`Layer0_ETL_Spec_v2.md` §5).

---

## TL;DR for the new chat

Onboarding spec body is complete. Four patch files were generated this session and need to be applied to `Athlete_Onboarding_Data_Spec_v2.md` to produce the final body-complete version (v2.3 or higher depending on what Andy already had locally). Once applied, the only remaining "(integrate) — pending" item is Open Item #11 (TA / aid station fallback), which was explicitly scoped out of this spec — it belongs in the Plan Management spec.

The next active workstream is the **query layer spec** — `Layer0_ETL_Spec_v2.md` §5. This defines how the app queries the `layer0` tables to serve sport-filtered exercise recommendations, phase load queries, and discipline pairing queries. It's now unblocked because:
- Clean exercise data (0 WARNs both validators per the Post-ETL handoff)
- Alias map in place (sport-filtered queries work correctly)
- `contraindicated_conditions` column populated (health condition filtering works correctly)

After query layer: Layer 1 prompt design, then implementation.

---

## What shipped this session

### Batch 4+5 integration into `Athlete_Onboarding_Data_Spec_v2.md`

Produced as `Athlete_Onboarding_Data_Spec_v2_INTEGRATION_BLOCK.md` plus a header patch. Contains §I (Lifestyle & Recovery), §J (Locales), §K (Locale Schedule), §L (Athlete Network), Group 2 (Account Configuration) with Account Config 1–4, and Group 3 (Plan Management) with Plan Management 1–5. Updated Open Items table (now 15 items, renumbered) and Resolved decisions log. Applied per the integration instructions in the prior `Post_ETL_Onboarding_Handoff.md`.

### Three additional in-spec decisions integrated

1. **Re-injury risk model (§B.1.2)** — drafted with literature grounding. The simple "12-month linear decay" first draft was replaced with a per-Injury-Type table:
   - Acute soft tissue: stepped exponential decay over 12 months (full → half → quarter → neutral)
   - Tendinopathy / overuse: **permanent** elevated priority (10-yr Achilles cohort data; 19% persisting symptoms; 41% develop bilateral involvement)
   - Joint mechanical surgical: **permanent** (ACL graft rupture data — 18% by 5 yr, front-loaded)
   - Joint mechanical non-surgical: stepped decay over 18 months (ankle sprain proxy)
   - Bone stress fracture: 18-month tail (bone remodeling)
   - Bone non-stress: through healing window + 6 months
   - Skin / surface: no decay
   - Nerve, Inflammatory, Post-surgical, Other / uncertain: rules per the patch
   - Override rule preserved: ever Chronic-Managed or Structural-Permanent → permanent priority regardless of Injury Type

2. **Health Condition auto-population (§B.4.2)** — promoted from "deferred" to launch behaviour with operational thresholds:
   - Rule 1 (Anaphylaxis flag → suggest GI / Immune record): unchanged
   - Rule 2 (Condition-specific medication → suggest matching system category): unchanged
   - Rule 3 (RHR outlier → suggest Cardiac record): expanded to four operational triggers (Sustained tachycardia >100 bpm 7-day avg; Symptomatic bradycardia <40/<45 bpm + symptoms in 14 days; Sustained baseline shift +10 bpm above 90-day baseline; First-entry extreme outlier >100 or <35/<40 bpm with no training history)

3. **Sex adjustment on RHR bradycardia triggers** — +5 bpm offset for §A Sex = Female on the bradycardia-side triggers only (literature: Health eHeart Study n=66,800 ~4 bpm difference; Fasa PERSIAN ~5 bpm). Tachycardia threshold (100 bpm) is sex-agnostic per AHA. Baseline shift trigger is inherently self-correcting. Pregnancy state is a known unhandled gap — flagged in the patch as a post-launch profile-field design item.

### §M.4 field-level operational lookup

The integration block originally shipped only the abstract Hard gate / Soft warning / Profile prompt definitions. Added §M.4.2 — the operational table mapping each Tier 2/3 field to a prompt class and trigger condition. Five sub-tables grouped by source domain (Performance Testing fields, Lifestyle & Recovery fields, Locale fields, Discipline-Specific Baselines / Strength benchmarks, Safety gates).

Net additions vs. the source `Sections_GHMN_v2_Batch.md` §M.4 table:
- Salt / Electrolyte Tolerance (new v2 field)
- Sleep Deprivation Experience (was in abstract examples, promoted to row)
- Altitude Acclimatization History (new row, symmetric with Heat which is system-tracked)
- Fueling Format Preference (added per Andy's call this session — Soft warning, race within 4 weeks)
- Known Race-day GI Triggers (added per Andy's call this session — Profile prompt, race within 4 weeks)

Climbing belay partner gate is binary per the source — no Athlete Link escape (Andy explicitly reverted that on review).

### Decisions Andy made this session

| Decision | Outcome |
|---|---|
| Drop the Athlete Link escape on Climbing belay partner gate | **Reverted to binary** — roped climbing in plan = hard gate |
| HRT override on RHR sex-band rule | **No** — §A Sex value is the only sex signal used; HRT-on-RHR is not modelled |
| Pregnancy carve-out on RHR triggers | **Acknowledged** as a post-launch profile-field design item; current behaviour is to allow dismissal without memory penalty |
| Fueling fields trigger window | **4 weeks pre-race** (versus the 6–8 weeks I'd suggested for gut-training rehearsal). Tunable from launch data |
| TA / aid station fallback in this spec | **Out of scope** — belongs in Plan Management spec |

---

## Files Andy needs to apply

Four files in `/mnt/user-data/outputs/`, applied in this order to the current `Athlete_Onboarding_Data_Spec_v2.md`:

1. **`Athlete_Onboarding_Data_Spec_v2_INTEGRATION_BLOCK.md`** — replace from `## Section I — Lifestyle & Recovery` through end of file
2. **`v2_spec_HEADER_PATCH.md`** — version status line + Drafting status table replacements (near the top of the doc)
3. **`v2_spec_SECTION_B_PATCH_v2.md`** — §B.1.2 (re-injury decay, literature-grounded) + §B.4.2 (RHR launch behaviour with operational thresholds). Note the prior `v2_spec_SECTION_B_PATCH.md` is superseded for those two sub-sections; the §B.1 Status History row tweak and Open Items / Resolved decisions log changes from the prior patch still apply
4. **`v2_spec_B42_RULE3_SEX_ADJUSTMENT.md`** — sex offset addendum on §B.4.2 Rule 3

After applying, bump version to v2.3 and update Last updated. Save and upload.

---

## Open Items snapshot post-session

| # | Item | Status |
|---|---|---|
| 1 | Disclosure copy (§A.1) | Pre-launch blocker — product/legal owns |
| 2 | Movement Components structured field | Layer 0 enhancement, deferred |
| 3 | Re-injury risk model | **Integrated** — §B.1.2 (per the patch) |
| 4 | Sheet 7 deprecation | Mechanical — once spec is signed off |
| 5 | Migration path from current app | Architecture hold — needs schema dump |
| 6 | Layer 1 ↔ Layer 0 query layer spec | **Next active workstream** |
| 7 | Health Condition auto-population | **Integrated** — §B.4.2 (per the patch) |
| 8 | Sports Framework gap audit | Pre-launch audit — AR verified; other 17 sports not |
| 9 | Plan gen strategy for weeks 13+ | Pre-launch decision — product/engineering |
| 10 | Recurring §K rolling-window length | Direction set (8 weeks) — close once engineering confirms |
| 11 | TA / aid station fallback | **Plan Management spec, not onboarding** — explicitly scoped out this session |
| 12 | Multi-partner consent rules (N>2) | Team-training spec |
| 13 | Stale-link cleanup | Team-training spec |
| 14 | Coach mode | Closed — out of scope |
| 15 | Linked-account consent flow | Direction set in Account Config 4; full flow in Plan Management spec |

---

## Files to reference in project

**Onboarding spec workstream (closing this session):**
- `Athlete_Onboarding_Data_Spec_v2.md` — primary spec, complete after patches applied
- `Sections_IJKL_Groups23_v2_Batch.md` — source material for batch 4+5 (now integrated)
- `Section_B_v2_Batch.md` — §B v2 batch (already integrated; the patch updates §B.1.2 and §B.4.2 within it)
- `Vocabulary_Audit_v2.md` — controlled vocab references

**Layer 0 ETL workstream (closed):**
- `Layer0_ETL_Spec_v2.md` — the spec the ETL was built against. **§5 is the next workstream — query layer.**
- `Sports_Framework_v6.xlsx`, `AR_Exercise_Database_v17.xlsx` — source data; ETL output is in `layer0` Postgres schema

**Existing app context (carry-forward):**
- `DATABASE.md` — full schema reference
- `Training_App_Architecture_Handoff.md` — full system architecture document
- `Build_Prep_Handoff.md` — predecessor to the post-ETL handoff

---

## Versioning rule (carry-forward)

- **Athlete Onboarding spec:** `Athlete_Onboarding_Data_Spec_v2.md` is current. After this session's patches applied → v2.3. Always increment version inside the doc when materially changed; never overwrite.
- **Sports Framework working file:** `Sports_Framework_v6.xlsx` is current. Workstream closed; unlikely to update.
- **Layer 0 ETL spec:** `Layer0_ETL_Spec_v2.md` is current. Next save → `v3` (likely needed once query layer spec lands).

---

## Risks / things to watch

- **Don't reopen the onboarding spec unless something concrete forces it.** It's complete. The temptation to re-audit §M.4 or revisit the Health Condition auto-population thresholds is real but unproductive. If launch data shows false-positive patterns, that's a tuning concern for that field's row in §M.4 specifically — not a structural revisit.
- **Confidence notes inside the §B patches matter.** Some decay curves (Inflammatory, Nerve, non-surgical Joint mechanical 18-month, stress fracture 18-month) are extrapolated or heuristic, not direct-evidence. The patch flags this. If query layer design surfaces a need for tighter curves, the spec accommodates a tune; engineering shouldn't treat the curves as immutable.
- **§M.4 has interpretive additions vs. the source batch doc.** Salt/Electrolyte Tolerance, Altitude Acclimatization History, Sleep Deprivation Experience, Fueling Format Preference, Known Race-day GI Triggers — all five were added during integration (not in the source field-level table). They're consistent with v2's structural changes but worth knowing they're integration-time additions if anyone tries to triangulate against the batch doc.
- **Fueling trigger at 4 weeks may produce less rehearsal time than ideal.** Andy's call. Sport science suggests 6–8 weeks for gut training adaptation. Worth revisiting from launch data if athletes report inadequate rehearsal time before races.
- **Pregnancy state is an unhandled gap on RHR triggers.** Pregnancy elevates RHR by 10–20 bpm in 2nd/3rd trimester. The current rule will produce false positives for pregnant athletes; they can dismiss without memory penalty, but a profile field for pregnancy state would suppress automatically. Flagged in the patch as post-launch.
- **HRT-class medications and RHR bands.** The §A.1 disclosure language says "Plan generation will use this medication record — not the biological sex you entered earlier — for any programming decisions that depend on hormonal context." Andy explicitly chose NOT to apply this to the RHR sex-band rule. The §A Sex value is the sole sex signal for RHR triggers. If future review reopens this, it would be a self-contained rule change, not a structural one.

---

## What good looks like for the next chat

1. **Confirm the four onboarding spec patches were applied.** Quick verification that v2.3 is in the project before pivoting. If anything was deferred, surface it and decide whether to apply or document.
2. **Open `Layer0_ETL_Spec_v2.md` and read §5.** That's the spec section being defined this session. The first task is to understand what §5 currently says (likely a stub or skeleton from the original spec write — needs full design).
3. **Define the query interface for each downstream consumer.** From the existing Layer 0 ETL spec §8 ("Downstream Prompt Consumption Reference"), the consumers are roughly: Layer 1 (athlete profile), Layer 2 (plan generation), Layer 3+ (per-week / per-session). Each layer has a different read pattern against `layer0`. Sport-filtered exercise queries, phase load queries, discipline pairing queries are the three named workstreams in the Post-ETL handoff.
4. **Decide query layer interface shape.** Stored procedures? Application-side query builder? Direct SQL with documented patterns? This is the structural call that gates everything downstream.
5. **Output: a concrete query layer spec.** Sufficient for Layer 1 prompt design to consume in the following session.

---

## What this session did NOT touch

- The Plan Management spec (separate doc, doesn't yet exist as its own deliverable). Open Item #11 (TA fallback) and the full multi-athlete plan sync logic live there.
- The team-training spec (separate doc, doesn't yet exist). Open Items #12 and #13.
- Layer 1 prompt design (downstream of query layer).
- Anything related to Andy's personal PGE 2026 training plan. Coaching workstream is parallel and separate.

---

## Carry-forward principles

- Andy's working style is architecture before prompts, prompts before implementation. Don't skip steps.
- Triathlon literature is the most relevant multi-sport analog when sourcing references.
- Real, cited research preferred over practitioner heuristics. Confidence notes flag what's well-supported vs. extrapolated.
- Andy's userPreferences are: direct, useful, no praise/hype/filler; match confidence to reality; flag tradeoffs and risks; end planning/evaluation responses with a quick gut check (risks, what we might be missing, best argument against).
- When chats get long or messy: remind Andy to create a handoff note and start a new thread.
