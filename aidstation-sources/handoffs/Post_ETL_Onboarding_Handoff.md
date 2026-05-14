# Post-ETL + Onboarding Spec Completion — Session Handoff

**Date:** 2026-05-06
**Predecessor:** `Build_Prep_Handoff.md`
**Status:** Layer 0 ETL fully complete and clean. Onboarding spec §I–§L + Groups 2–3 drafted. Spec body complete pending integration of batch doc.
**Next chat starts with:** Integrating `Sections_IJKL_Groups23_v2_Batch.md` into the main spec, then query layer design.

---

## TL;DR for the new chat

Layer 0 ETL shipped, went through two rounds of follow-up fixes (sport name reconciliation + vocabulary split), and is now fully clean — 0 WARNs on both validators. The onboarding spec body is complete: §A–§H were already drafted, §I–§L + Groups 2–3 were drafted this session. The batch doc (`Sections_IJKL_Groups23_v2_Batch.md`) needs to be integrated into `Athlete_Onboarding_Data_Spec_v2.md`. Once that's done, the spec is complete pending the open items listed below (none of which are design work — they're product/legal/engineering holds).

Next major workstream: **query layer spec (Layer0_ETL_Spec_v2.md §5)**.

---

## What shipped this session

### ETL review and triage

1. **sum_to_100 WARNs resolved:** 9 WARNs, all Taper-phase only, all non-AR sports (Triathlon variants, Aquabike, Duathlon, Swimrun, Skimo, Off-Road Multisport). Adventure Racing is clean. Documented as low-priority data debt — taper allocations for those sports weren't tuned to sum to 100%. No action required.

2. **cross_sport_properties = 1 row confirmed correct.** Sheet 8 genuinely has one data entry (LIT_RATIO_001). Not a parser bug.

3. **Open Item #5 resolved — sport name reconciliation.** The exercise DB uses discipline-level sport names ("Trail Running", "Mountain Biking") while the framework uses sport-level names ("Adventure Racing"). Full reconciliation table produced; all 36 exercise DB sport names mapped. Decisions captured:
   - Rock Climbing, Mountaineering, Fixed Rope / Via Ferrata → AR + Multisport + Skimo
   - General Conditioning → all framework sports (wildcard)
   - Multi-Sport Race → Off-Road / Adventure Multisport (Non-Nav) directly (fuzzy match had failed due to embedded `\n` in xlsx cell)
   - Rappelling / Abseiling, SUP, Snowshoeing → AR + Multisport
   - Rowing → AR + Multisport + all paddle sports
   - Obstacle Course Racing → Modern Pentathlon
   - Fencing → Modern Pentathlon only

### ETL fixes (two Claude Code rounds, both merged and green)

**Round 1 — Open Item #5 + newline fix (v1.1):**
- `sport_name_aliases.py` uploaded to `etl/layer0/` (123 rows; hand-curated, authoritative)
- `sports_framework.py` `_t()` function: added `.replace("\n", " ")` — fixes 5 sport names with embedded newlines from xlsx cell wrapping
- `schema.sql`: added `layer0.sport_name_aliases` table
- `run.py`: loads alias map in Phase 1 under 0C source family
- `vocab_alignment.py`: check (b) now queries alias table instead of bridge placeholder
- Result: vocab_alignment (b) → 36 PASS, 0 WARN

**Round 2 — Vocabulary split (v1.2):**
- `Vocabulary_Audit_v2.md`: 7 body parts added to Section 1 (Trachea, Biceps, Triceps, Thumb, Trapezius, TFL, Diaphragm). Actual count landed at 54 (not 57) because Thumb, Trapezius, TFL were already present — dedup logic added to `_parse_body_parts` to handle gracefully.
- `vocabulary_transforms.py`: two new rename rules (Tricep→Triceps, Bicep→Biceps); `SYSTEMIC_TOKENS` set; `_CONTRA_DROP` set (Grip → drop); new `split_contraindicated_string()` function routing systemic flags to conditions list
- `schema.sql`: `contraindicated_conditions TEXT[]` column added to `layer0.exercises` + `ALTER TABLE IF NOT EXISTS` for existing databases
- `exercise_db.py`: switched from `transform_body_part_string` to `split_contraindicated_string`; populates both `contraindicated_parts` and `contraindicated_conditions`
- `run.py`: `contraindicated_conditions` added to exercises insert
- Claude Code also added `"spine": "Spine (general)"` rename — not in the handoff but caught EX167's lone remaining WARN. Correct call.
- Result: vocab_alignment (a) → 245 PASS, 0 WARN

**Final ETL state (v1.2, all merged to main):**
- sum_to_100: 33 sports checked, 24 PASS, 9 WARN (Taper-only, non-AR, documented)
- vocab_alignment (a): 245 PASS, 0 WARN
- vocab_alignment (b): 36 PASS, 0 WARN

### Onboarding spec — §I–§L + Groups 2–3

Drafted in `Sections_IJKL_Groups23_v2_Batch.md`. Key decisions baked in:

**§I — Lifestyle & Recovery:**
- v1 §J fields carried forward minus Heat Acclimatization History (system-tracked)
- Race-day Caffeine Strategy added as sub-question on Caffeine Tolerance & Strategy
- Fueling Format Preference, Known Race-day GI Triggers, Salt/Electrolyte Tolerance added (race-day fueling fields from Sections_C_J_v2_Batch.md)
- Sleep Deprivation Experience added, conditional on §H Estimated Duration > 20hr

**§J — Locales:**
- Proximity model: **26.2 mi / 42.2 km** default radius (marathon distance — inside joke)
- J.1: Locale Name, lat/long from place lookup, Gym Chain Memberships, Is Primary; dropped Linked Primary Locale FK
- J.2: Equipment Inventory against Vocabulary_Audit_v2 §3 canonical list; added Bench, Foam pad, Incline board; dropped Jacob's Ladder, Compression boots, Sauna, Stretch strap
- J.3: All 12 gear readiness toggles from Vocabulary_Audit_v2 §4.1 (canonical names, including Fencing setup which was initially missed in a draft and corrected before delivery)
- J.4: Terrain Access with hybrid seasonality (climate-derived defaults + per-month override)
- J.5: Locale Capacity Metrics (session time available, max session duration)

**§K — Locale Schedule:**
- K.1 Self-overlays: Date Range, Active Locale, Date-Specific Constraints (At home only / Indoor only / Short sessions only / Other), Notes
- K.2 Joint-training overlays: Joint Training Link FK, Status (Proposed/Accepted/Declined/Expired), Proposed By, Notes from Proposer, Source enum, Parent Recurrence FK. Storage model: two records (one per athlete) linked by shared joint-training-instance ID. Declined records preserved for audit trail.
- K.3 Recurrence templates: Pattern (Weekly/Biweekly + day-of-week), Start/End Date, Template Status (Active/Cancelled), inherited overlay fields

**§L — Athlete Network:**
- Athlete Link entity: Partner Name, Linked Account FK (optional), Relationship Types (Solo Training Partner / Race Teammate), Partner-specific Rules
- Race Teammate conditional: Race Event Association FK (1+), Discipline Focus on Team
- Role on Team enum removed (was in deleted Athlete_Link_Entity_v2.md — not re-incorporated)

**Group 2 — Account Configuration:**
- Connected Services (Service Name, Status, Last Sync, Scopes Granted, Sync Direction; launch tier Garmin/Strava/Apple Health)
- Gym Memberships (Chain, Membership Active)
- Disclosure Acknowledgment Records (Disclosure Type, Acknowledged At, Version Seen, Delivery Method)
- Privacy / Linked-partner sharing (per Athlete Link: Consent Scope — None / Activity summaries / Full plan)

**Group 3 — Plan Management:**
- Plan Duration / Event Prefix routing logic
- Profile Update Triggers §M.1–M.4 (slotted from Sections_GHMN_v2_Batch.md)
- Adherence-drop threshold: 4 consecutive flagged sessions (cross-ref to Adherence_Drop_Spec_v2.md)
- Soft Warning / Hard Gate / Profile Prompt classification table
- Joint Training Generation (rolling 8-week forward window; pending engineering confirmation per Open Item #10)
- System-Tracked Heat Acclimatization (workout date + location + weather API)
- Multi-athlete plan sync: out of scope for v2 launch, flagged for team-training spec

---

## Immediate next action for new chat

**Integrate the batch doc into the main spec.** Mechanically straightforward:

1. Open `Athlete_Onboarding_Data_Spec_v2.md`
2. Replace the §I, §J, §K, §L, Group 2, Group 3 pending stubs with the content from `Sections_IJKL_Groups23_v2_Batch.md`
3. Update the Drafting status table — all sections → ✅ Drafted
4. Update the spec version status line to: "Batches 1–5 complete. Spec body complete pending Open Items."
5. Upload updated spec to project

After integration, the spec is done as a design artifact. Remaining open items are holds, not design work.

---

## Open items status (post this session)

| # | Item | Status |
|---|---|---|
| 1 | Disclosure copy (§A.1) | Pre-launch blocker — product/legal owns |
| 2 | Movement Components structured field | Cross-layer; Layer 0 enhancement, deferred |
| 3 | Re-injury risk model | v2 design decision, deferred |
| 4 | Sheet 7 deprecation | Mechanical — once spec is signed off |
| 5 | Migration path from current app | Architecture hold — needs schema dump |
| 6 | Layer 1 ↔ Layer 0 query layer spec | **Next active workstream** |
| 7 | Health Condition auto-population | v2 design decision, deferred |
| 8 | Sports Framework gap audit | Pre-launch audit — AR verified; other 17 sports not |
| 9 | Plan gen strategy for weeks 13+ | Pre-launch decision — product/engineering |
| 10 | Recurring §K rolling-window length | Direction set (8 weeks) — close once engineering confirms |
| 11 | TA / aid station fallback | Plan-gen behaviour, deferred |
| 12 | Multi-partner consent rules (N>2) | Team-training spec |
| 13 | Stale-link cleanup | Team-training spec |
| 14 | Coach mode | Out of scope |
| 15 | Linked-account consent flow | Direction set in Account Config 4; full flow in Plan Management spec |

---

## What's next after spec integration

**Query layer spec (Layer0_ETL_Spec_v2.md §5).** This is the next build. Defines how the app queries layer0 tables to serve sport-filtered exercise recommendations, phase load queries, and discipline pairing queries. Now unblocked by:
- Clean exercise data (0 WARNs)
- Alias map in place (sport-filtered queries work correctly)
- contraindicated_conditions column populated (health condition filtering works correctly)

After query layer: Layer 1 prompt design, then implementation.

---

## Files in project — current state

| File | State |
|---|---|
| `Athlete_Onboarding_Data_Spec_v2.md` | §A–§H complete; §I–§L + Groups 2–3 pending integration of batch doc |
| `Sections_IJKL_Groups23_v2_Batch.md` | **New this session — needs to be uploaded to project and integrated into spec** |
| `Layer0_ETL_Spec_v2.md` | Current; §5 (query layer) is the next spec work |
| `Sports_Framework_v6.xlsx` | Current canonical |
| `AR_Exercise_Database_v17.xlsx` | Current canonical |
| `Vocabulary_Audit_v2.md` | Current; 54 canonical body parts (7 added this session, 3 were already present) |
| `sport_name_aliases.py` | In repo at `etl/layer0/sport_name_aliases.py` |
| `Phase_Load_Allocation_Audit_Log.md` | Closed workstream; no further updates expected |

---

## Versioning rule (carry-forward)

- **ETL version:** currently at 1.2. Next schema or data change → 1.3 (or 2.0 for major restructure).
- **Athlete Onboarding spec:** `Athlete_Onboarding_Data_Spec_v2.md` — no version suffix; update in place.
- **Sports Framework:** `Sports_Framework_v6.xlsx` — next save → v7.
- **Exercise DB:** `AR_Exercise_Database_v17.xlsx` — next save → v18.
- **Vocabulary Audit:** `Vocabulary_Audit_v2.md` — next save → v3 (reflects the 7 new body parts and any future changes).

Always increment; never overwrite.

---

## Risks / things to watch

- **`Sections_IJKL_Groups23_v2_Batch.md` is not yet in the project.** It was produced this session and is in outputs. Upload it before the new chat tries to reference it.
- **The spec is complete as a data inventory, not as a prompt spec.** The next reader needs to understand: this tells you *what* the app collects, not *how* prompts use it. Prompt design is downstream.
- **Open Item #8 (Sports Framework gap audit) is a pre-launch blocker** if Discipline Weighting defaults are going to read from Phase Load Allocation for all sports. AR is verified; the other 17 sports have unverified coverage. Don't ship Discipline Weighting without this.
- **The 26.2 mi proximity radius** is an inside joke and will need explanation in any external-facing documentation or engineering tickets. Note it as intentional if it comes up.
- **General Conditioning → all sports (wildcard mapping)** means those exercises will appear in every sport's exercise pool. Verify at query layer that this doesn't flood results for athletes targeting a single sport.
