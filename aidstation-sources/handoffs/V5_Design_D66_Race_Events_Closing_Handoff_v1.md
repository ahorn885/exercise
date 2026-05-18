# V5 Design — D-66 Race-Event Data Model Closing Handoff

**Session:** Single chat. Scope: D-66 race-event data model design wave (the unblocker for Layer 4 implementation Step 4e race-week-brief, which was queued behind D-66 per `Layer4_Spec.md` §14.3.4). Paired spec amendments: `Layer4_Spec.md` §3.4 + §4.5 + §5.4; `Athlete_Onboarding_Data_Spec_v5.md` §A.1 + §H.2 extension + new §H.4.
**Date:** 2026-05-18
**Predecessor handoff:** `V5_Implementation_Layer4_Step4d_T3_PlanRefresh_Closing_Handoff_v1.md` (Step 4d shipped 2026-05-17; combined `tests/` 445 green; D-64 plan refresh implementation arc through tier 4d complete).
**Branch:** `claude/plan-refresh-closing-handoff-yEd2O` (harness-pinned for this session — name carried over from Step 4d's branch even though this session is D-66 design wave; precedent: harness names mismatched with scope across PR-A → Step 4a → Step 4b/c → Step 4d).
**Status:** 🟢 1 new design doc + 2 paired spec amendments + 3 bookkeeping = 6 files. D-66 status flipped 🟡 Deferred → 🟢 Design wave shipped. **Layer 4 implementation Step 4e race-week-brief is now unblocked** as the architect-recommended next forward move.

---

## 1. Session-start verification (Rule #9)

Predecessor (Step 4d) handoff §7 claimed: `layer4/phase_structure.py` + `plan_refresh_t3.py` + `Layer4_RefreshT3_v1.md` + `Layer4_RefreshT1_v2.md` + `Plan_Refresh_D64_Design_v1.md` §2/§3 carry-forward + `Layer4_Spec.md` §3.2 + §4.3 amendments all on disk; combined `tests/` 445 green; `Project_Backlog_v47.md` exists; PR #76 merge commit `d587a01` on origin/main; working tree clean on fresh-cut `claude/plan-refresh-closing-handoff-yEd2O`.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `layer4/phase_structure.py` exists | `ls -la` | ✅ 11095 bytes |
| `layer4/plan_refresh_t3.py` exists | `ls -la` | ✅ 17213 bytes |
| `aidstation-sources/prompts/Layer4_RefreshT3_v1.md` exists | `ls -la` | ✅ 48222 bytes |
| `aidstation-sources/prompts/Layer4_RefreshT1_v2.md` exists | `ls -la` | ✅ 62191 bytes |
| `Project_Backlog_v47.md` exists | `ls -la` | ✅ 253996 bytes |
| `Layer4_Spec.md` §3.2 contains `plan_start_date` parameter | grep | ✅ line 150 |
| `Layer4_Spec.md` §4.3 contains `plan_start_date_missing` + `tier_t3_cross_phase_requires_pattern_a` | grep | ✅ lines 780-781 |
| `layer4/__init__.py` exports 3 new symbols (`phase_for_date`, `phase_structure_from_3b`, `scope_spans_phase_boundary`) | grep | ✅ lines 105-107 + 287-289 |
| Combined `tests/` 445 green | `python -m pytest tests/ -q` | ✅ 445 passed in 0.53s (after `pip install pydantic pytest` in fresh container) |
| Working tree clean on fresh-cut branch `claude/plan-refresh-closing-handoff-yEd2O` | `git status` | ✅ |
| PR #76 merge commit `d587a01` on origin/main | `git log --oneline -5` | ✅ visible |

**No drift found.** Step 4d state on disk matches the handoff narrative exactly.

---

## 2. Session narrative — D-66 design wave (Andy 2026-05-18 picks 1+2+3 then 4+5+6 then route-locale-equip clarification)

Andy opened with a URL pointer to the Step 4d closing handoff and "let's go." I followed §5 operating notes — re-read CLAUDE.md (Rule #13), ran Rule #9 verification, surfaced state + next focus + drift (none), and offered four scope options via `AskUserQuestion`:

### 2.1 Picks surfaced via AskUserQuestion

**Round 1 (2026-05-18, 1-question batch):** session scope. Andy picked **Step 4e race-week-brief**, which is blocked behind D-66. Per the option description, picking this pivots the session to designing D-66 first.

**Round 2 (2026-05-18, 3-question batch):**
1. **D-66 scope = Full design wave** (single substantial session producing the design doc + spec amendments + Layer 4 §3.4 input contract amendment + onboarding/profile UI design described). Step 4e implementation deferred to subsequent session.
2. **Entry posture = Onboarding + Profile** (onboarding §H.2 extends; new §H.4 route-locale step for multi-day; profile retains full CRUD via new `/profile?tab=race-events` tab).
3. **Gear + rules = Free-text** (mandatory_gear_text + race_rules_summary as TEXT columns; LLM consumes verbatim).

**Round 3 (2026-05-18, 3-question batch):**
4. **Layer 4 input wiring = New `race_event_payload: RaceEventPayload` arg** on §3.4 signature (over extend-Layer-3B or read-from-DB-inside-synthesizer).
5. **Race-event count = Multiple races with `is_target_event` partial-UNIQUE flag** (over single-race-per-athlete or no-target-flag).
6. **Per-route-locale equipment = "explain more"** — Andy asked for clarification before picking.

**Plain-language explanation of route-locale equipment options** (rendered in chat; not in AskUserQuestion):
- Option A: Reuse `locale_profiles` + FK from route locale.
- Option B: Dedicated `route_locale_equipment` table parallel to locale_profiles.
- Option C: Free-text `kit_notes` per route locale.

**Round 4 (2026-05-18, 1-question batch):**
6. **Per-route-locale equipment = Dedicated `race_route_locale_equipment` table** per Andy: "these are ephemeral and won't have any use outside of the race for which they were generated." Closes the locale-list-pollution concern.

### 2.2 Architect-pick sub-decisions

Resolved inline against the picks without re-routing through AskUserQuestion (low-stakes, mechanically derived from the load-bearing picks above):

- **Layer 3B source** = reads from `race_events WHERE is_target_event=true` (orchestrator-side join); existing `athlete.target_event_*` columns deprecated + migrated per design doc §10. Single source of truth.
- **Locale role enum** = closed 7-element set `start / transition_area / aid_station / drop_bag_point / bivvy / finish / other` per backlog D-66 sketch.
- **Distance + elevation** = nullable per `NUMERIC NULL` — athletes booking races 6+ months out often don't know exact route specs yet. Race-week-brief degrades gracefully.
- **Sequence_idx** = 1-indexed INT NOT NULL; UNIQUE per race_event_id; gaps allowed (1, 2, 5, 8 valid) — lets athletes insert forgotten locales without cascading rewrites.
- **First/last role anchors** = pydantic `model_validator(mode='after')` on RaceEventPayload enforces: when route_locales non-empty, lowest-sequence_idx entry has role 'start' and highest has role 'finish'.
- **Migration** = legacy `athlete.target_event_name` + `target_event_date` columns kept on table for migration grace period; new onboarding writes `race_events`; existing v1 athlete rows migrated with `race_format='single_day'` safe default (Andy updates his Pocket Gopher Extreme row manually post-migration).

### 2.3 Single-pass design doc draft

After the 6 picks settled, I read existing design-doc structures (`Plan_Refresh_D64_Design_v1.md` + `Onboarding_D58_Design_v1.md`) to match conventions + the Layer 4 §3.4 + §4.5 + §5.4 sections to know what spec surfaces D-66 needs to amend.

Discovered on re-read that the onboarding spec uses **§H (Target Events)** for race scoping, not §A as I'd initially framed in the design doc. §K already exists as "Locale Schedule" — different scope. Surgically renamed the design doc references from §A/§K to §H.2/§H.4 (extending §H rather than reusing existing letters) via `sed` + Edit replace_all.

### 2.4 Files shipped

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Race_Events_D66_Design_v1.md` | New | ~640 lines, 15 H2 sections (Purpose + Decisions table + Schema additions + RaceEventPayload contract + Layer 4 amendment + Onboarding extension + Profile UI + Layer 3B integration + Invalidation rules + Migration + Spec amendments paired + Test scenarios + Open items + Gut check + Forward pointers). |
| 2 | `aidstation-sources/Layer4_Spec.md` | Modified | §3.4 signature gains `race_event_payload: RaceEventPayload` positional arg; parameter table gains corresponding row; §4.5 gains 2 new precondition rows (`race_event_payload_missing` + `race_event_date_mismatch_3b`); §4.5 row 9 `kit_manifest_inputs_incomplete` annotation updated for post-D-66 active branch; §5.4 rule body for `kit_manifest_inputs_incomplete` updated (3 outcomes: skip on single_day/None, emit `kit_manifest_inputs_incomplete_no_route_locales`, emit `kit_manifest_inputs_incomplete_no_route_locale_equipment`); §5.4 D-66 forward-pointer block flipped 🟡 Deferred → ✅ Design wave shipped. |
| 3 | `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` | Modified | §A.1 disclosure list gains race-rules-paste-acknowledgment row; §H.2 target-event step extended with race_format closed-enum radio + race_rules_summary free-text + is_target_event boolean (notes the existing v4 fields stay; replaces "Number of Transition Areas" + "Number of Aid Stations" with structured route-locale graph in new §H.4); §H.3 unchanged; **NEW §H.4 Route locales (when H.2 Race Format != 'single_day')** — full multi-day route-locale entry surface (6 per-route-locale fields + nested 0..N per-equipment items + skip semantics + account_nudge 14 days post-skip). |
| 4 | `aidstation-sources/Project_Backlog_v47.md` → `_v48.md` | New (per Rule #12) | D-66 status flipped 🟡 Deferred → 🟢 **Design wave shipped 2026-05-18**; row narrative updated with the picks + architect sub-decisions + stop-and-ask trigger retrospective; v48 file-revision-header gains this session's full narrative with v47 demoted as predecessor. |
| 5 | `aidstation-sources/CLAUDE.md` | Modified | Last-shipped-session narrative bumped to D-66 design wave (~3500-word block); Step 4d narrative compressed to predecessor entry; Backlog ref v47 → v48; Authoritative current files gains `Race_Events_D66_Design_v1.md` row; Next-forward-move recommends Step 4e race-week-brief (now unblocked); Step 4e candidate row updated from "depends on D-66" → "NOW UNBLOCKED 2026-05-18". |
| 6 | `aidstation-sources/handoffs/V5_Design_D66_Race_Events_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**6 files total. Over the 5-file ceiling intentionally** — precedent from Step 4d 13 + Step 4b/c 10 + PR-A 8 + Step 4a 8 + PR-C-followon 6 + PR-D 6 + PR-E 6.

### 2.5 Architectural choices on the record

- **Multiple races per athlete with partial UNIQUE `is_target_event=true` flag** (Andy Pick 5) over single-race-per-athlete or no-target-flag alternatives. Endurance athletes typically have 2–3 races on their calendar.
- **Free-text gear + rules** (Andy Pick 3) over structured taxonomy — race directors publish PDFs, athletes paste; v2 may add structured forward-pointer if LLM extraction proves unreliable.
- **Dedicated `race_route_locale_equipment` table** (Andy Pick 6) over reuse-locale_profiles or free-text — race-route locales are ephemeral; no locales-list pollution; structured for validator reconciliation.
- **Layer 4 §3.4 new arg** (Andy Pick 4) over extend-Layer-3B or read-from-DB-inside-synthesizer — preserves pure-function-over-typed-payloads pattern + clean separation (3B = periodization-relevant; race_event_payload = brief-rendering-relevant).
- **Onboarding + Profile entry posture** (Andy Pick 2) — captures load-bearing race_format pick early (drives 3B periodization) while allowing post-onboarding completion of route locales for athletes booking 6+ months out.
- **Layer 3B reads from race_events.target_row** (architect-pick) — single source of truth; legacy `athlete.target_event_*` columns deprecated + migrated.
- **Route-locale sequence_idx UNIQUE with gaps allowed** (architect-pick) — avoids cascading rewrites when athletes insert forgotten aid stations.
- **First/last role anchors enforced by pydantic model_validator** on RaceEventPayload — when route_locales non-empty, lowest-sequence_idx entry has role='start' and highest has role='finish'. Caught at construction time.
- **`race_event_payload.event_date == layer3b_payload.event_date` defensive consistency check** as §4.5 precondition — orchestrator passes both payloads; race-day shifts must propagate to both consistently.
- **Onboarding §H.4 is skippable** with 14-day account_nudge — athletes who book races early without finalized routes can complete later via profile.

### 2.6 Stop-and-ask triggers — #5 + #7 + #8 + #11 fired and routed

- **Trigger #5 (schema/inter-layer-contract amendments):** fired on Layer 4 §3.4 + §4.5 + §5.4 amendments (new `race_event_payload` arg + 2 new preconditions + rule body rebinding) AND on Athlete_Onboarding_Data_Spec_v5 §A.1 + §H.2 + §H.4 amendments. Routed via this session's 3-round AskUserQuestion gate per the Step 4a/4b/c/4d precedent (formal `/plan` mode equivalent for amendment-authoring per the Andy 2026-05-17 directive).
- **Trigger #7 (new partial-update invalidation rules):** fired on the rules in design doc §9 (target-flag flips → Layer 3B + 4 invalidation; race_event field edits → tier-specific invalidation; route-locale CRUD → race_week_brief cache only). Routed via same AskUserQuestion gate.
- **Trigger #8 (architectural alternatives with real tradeoffs):** fired on the per-route-locale equipment storage pick (reuse-locale_profiles vs dedicated table vs free-text); Andy picked dedicated table after a plain-language explanation of the three options. Same AskUserQuestion gate.
- **Trigger #11 (cross-layer D-row design wave):** fired on D-66 itself — extending the v1 sketch in the backlog into a full design wave is the trigger #11 archetype. Routed via the design-doc + spec-amendment + bookkeeping bundle approach precedented by D-58/59/60/61 and the PR-C-followon injury-accommodation design wave.
- Other triggers — none applicable.

### 2.7 Scope NOT changed this session

- **Step 4e race-week-brief implementation** — deferred to next session per Andy Pick 1.
- **v5 onboarding implementation PR** — independent of this design wave; consumes §H.2 + §H.4 + §A.1 amendments when it lands.
- **D-67 / D-68 / D-70 / D-71** — not touched.
- **Layer 4.5 Joint Session Coordinator** — out of scope; mentioned in §13 deferred items.
- **D-66 sub-decisions deferred to implementation PR** per design doc §2.1: profile UI "set as target" affordance shape; onboarding §H.4 skip semantics; Mapbox anchoring on race_route_locales (data carried; not consumed by Layer 4 v1); free-text route_locale notes content.

---

## 3. Spec amendments paired this session — surgical edit summary

### 3.1 `Layer4_Spec.md`

- **§3.4 signature** gains `race_event_payload: RaceEventPayload` positional arg (inserted between `layer3b_payload` and `prior_plan_session_window`).
- **§3.4 parameter table** gains new row for `race_event_payload` describing the source + the brief-rendering surfaces it drives.
- **§4.5 precondition table** gains two new rows: `race_event_payload_missing` (blocker; required non-None when mode='race_week_brief') + `race_event_date_mismatch_3b` (blocker; defensive consistency check).
- **§4.5 row 9 `kit_manifest_inputs_incomplete`** annotation updated for D-66-active branch (pre-D-66 always-warn → D-66-active warning fires only when athlete legitimately hasn't filled in route-locale equipment).
- **§5.4 rule body for `kit_manifest_inputs_incomplete`** updated to read `ctx.race_event.route_locales[].equipment` with 3 outcomes (skip / emit no-route-locales / emit no-equipment).
- **§5.4 D-66 forward-pointer block** flipped from 🟡 Deferred → ✅ Design wave shipped 2026-05-18.

### 3.2 `Athlete_Onboarding_Data_Spec_v5.md`

- **§A.1 disclosure list** gains race-rules-paste-acknowledgment row (D-66 amendment).
- **§H.2** target-event step extended with: race_format closed-enum radio (4 values); race_rules_summary multi-line TEXT free-text (up to 8000 chars); is_target_event boolean (DB partial UNIQUE enforced). Notes that existing v4 fields (Race Distance + Estimated Duration, Race Elevation Gain / Loss, Race Pack Weight + Mandatory Kit, etc.) carry forward; "Number of Transition Areas" + "Number of Aid Stations" counts are replaced by structured §H.4 route-locale graph.
- **§H.3** unchanged.
- **New §H.4 Route locales (when H.2 Race Format != 'single_day')** — full multi-day route-locale entry surface. 6 per-route-locale fields (role 7-element enum + name + sequence_idx + mile_marker NULL + Mapbox anchor optional + notes NULL) + nested 0..N per-equipment items (equipment_name + quantity_text NULL + notes NULL) + skip semantics + 14-day account_nudge.

### 3.3 `Project_Backlog_v47.md` → `_v48.md`

- D-66 row status flipped 🟡 Deferred → 🟢 Design wave shipped 2026-05-18.
- D-66 row narrative replaced with: design doc reference + the 6 settled picks + 4 architect sub-decisions + stop-and-ask trigger retrospective.
- File-revision-header bumped to v48 with the full session narrative; v47 demoted to predecessor entry.

### 3.4 `CLAUDE.md`

- Current state date bumped 2026-05-17 → 2026-05-18.
- Last-shipped-session narrative replaced with the D-66 design wave block; Step 4d narrative compressed to predecessor.
- Backlog ref updated v47 → v48.
- Authoritative current files gains `Race_Events_D66_Design_v1.md` (🟢 Design wave shipped 2026-05-18).
- Next-forward-move now recommends Step 4e race-week-brief (NOW UNBLOCKED) as architect-recommended next; Step 4e candidate row in "Other candidates" updated from "depends on D-66" to "NOW UNBLOCKED 2026-05-18" + ~3-4 file scope sketch.

---

## 4. Next session pointers — Step 4e race-week-brief implementation

**Architect-recommended next forward move:**

### 4.1 Step 4e scope: `llm_layer4_race_week_brief` D-66 caller integration

Consumes the now-defined `RaceEventPayload` contract (per `Race_Events_D66_Design_v1.md` §4) + the already-shipped `Layer4_RaceWeekBrief_v1.md` prompt body. ~3-4 files projected:

1. **New `layer4/race_week_brief.py`** (~700 lines) — driver per Step 4a/4b/c/4d precedent: input validation per `Layer4_Spec.md` §4.5 (now including 2 new D-66 preconditions); `build_record_race_week_brief_tool()` returning a strict JSON schema mirroring `RaceWeekBrief` + `RacePlan` schemas per §7.13 + §7.14; `_default_llm_caller` Anthropic SDK adapter; `_render_user_prompt()` rendering `Layer4_RaceWeekBrief_v1.md` §6 template against the typed payloads (5 Layer 2 + 3A + 3B + prior_plan_session_window + race_event_payload); capped-retry loop with §5.5 best-effort semantics on cap-hit; `Observation` emissions per §8.7 (`opportunity` LLM-emitted; `data_gap` orchestrator-emitted on §4.5 soft-fail).

2. **`layer4/context.py` modifications** — replace v1 `RaceEventStub` placeholder with 3 new typed models (`RouteLocaleEquipment` + `RouteLocale` + `RaceEventPayload`) + 2 new Literal aliases (`RaceFormat` + `RouteLocaleRole`). Pydantic v2 `BaseModel` per PR-D precedent; `extra='forbid'`; bounds on text fields per §4.1 of the design doc; `model_validator(mode='after')` enforces sequence_idx-unique-sorted + first/last role anchors when route_locales non-empty.

3. **`layer4/validator.py` modifications** — rebind `kit_manifest_inputs_incomplete` rule body from always-warn to D-66-active logic per §5.4 amendment. ValidatorContext's existing `RaceEventStub | None` field changes to `RaceEventPayload | None` (same field name — backwards-compatible).

4. **`layer4/__init__.py`** — re-exports for 3 new types + 2 Literal aliases + `build_record_race_week_brief_tool` + `llm_layer4_race_week_brief`.

5. **`tests/test_layer4_race_week_brief.py`** (~40 tests projected) — covering: RaceEventPayload pydantic validation (~10 tests covering structural invariants + JSON round-trip); §4.5 precondition activation (~6 tests including the 2 new D-66 preconditions); entry-point happy path single-day + multi-day (~6 tests); observation emission (~3 tests); capped retry (~4 tests); schema violation (~3 tests); Layer4Payload composition invariants (~5 tests); prompt rendering (~3 tests).

**Combined `tests/` count projected:** 445 → ~485.

### 4.2 Stop-and-ask risk for Step 4e

- **Trigger #2** (modifying a prompt body) — the existing `Layer4_RaceWeekBrief_v1.md` references `event_locale` as a single locale name + `kit_manifest` items as a flat list. Post-D-66 the synthesizer has route_locales as an ordered list with per-locale equipment. The prompt body may need a v2 amendment surgical to §3 (Inputs) + §4 (Tool schema) to reflect the new typed payload — similar to Step 4a's `SingleSession_v1.md → v2.md` precedent for tool-schema fidelity. Pre-flag for the implementation session.
- **Trigger #5** (contract amendments) — likely fires on the v1 `RaceEventStub` → typed `RaceEventPayload` swap in `layer4/context.py` if any structural-invariant surprises surface during implementation. Route via implementation-session AskUserQuestion gate.
- **Trigger #8** (architectural alternatives) — none expected; the D-66 design wave settled the architectural picks.
- **Trigger #11** (cross-layer D-rows) — not expected.

### 4.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff (D-66 design wave).
3. **Third re-read**: `Race_Events_D66_Design_v1.md` fully (~640 lines).
4. **Fourth re-read**: `Layer4_Spec.md` §3.4 + §4.5 + §5.4 + §7.13 + §7.14 (race-week-brief contract surfaces).
5. **Fifth re-read**: `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` (~955 lines; consumer prompt body).
6. **Sixth re-read**: `layer4/single_session.py` + `layer4/plan_refresh.py` (closest implementation analogs — Pattern B driver shape; tool schema builder; capped retry; observation emission).
7. **Branch**: cut a fresh branch off post-merge main; or stay on a harness pin per precedent.
8. **Test convention**: top-level `tests/test_layer4_race_week_brief.py` for Step 4e.

### 4.4 Subsequent forward moves

- **v5 onboarding implementation PR** consumes §H.2 extension + §H.4 + §A.1 disclosure per design doc §6 + §7. Independent of Layer 4 implementation track; can run in parallel.
- **Migration script per design doc §10** lands in implementation PR — migrates Andy's Pocket Gopher Extreme row from athlete.target_event_* columns to race_events; Andy manually updates his row to race_format='expedition_ar' post-migration.
- **Step 4f `plan_create` Pattern A orchestration** — heaviest remaining; per-phase synthesizer + seam reviewer wiring; ~6-8 files projected. T3 cross-phase Pattern A lands here as a natural consumer of the same per-phase machinery; closes the `tier_t3_cross_phase_requires_pattern_a` raise path.

---

## 5. Open items / decisions pinned this session

### 5.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Full design wave; Step 4e implementation deferred | Andy 2026-05-18 | Single substantial session producing stable contract for Step 4e against; matches Onboarding D-58/59/60/61 pattern. |
| 2 | Entry posture = Onboarding + Profile | Andy 2026-05-18 | Captures load-bearing race_format pick early (drives 3B periodization); allows post-onboarding completion for races booked 6+ months out. |
| 3 | Gear + rules = Free-text TEXT columns | Andy 2026-05-18 | Race directors publish PDFs; athletes paste. No structured taxonomy forced in v1; v2 may add structured forward-pointer. |
| 4 | Layer 4 input wiring = New `race_event_payload: RaceEventPayload` arg on §3.4 | Andy 2026-05-18 | Preserves pure-function pattern + clean separation (3B = periodization; race_event = brief-rendering). |
| 5 | Race-event count = Multiple races with `is_target_event` partial-UNIQUE flag | Andy 2026-05-18 | Endurance athletes typically have 2-3 races on calendar at once; single-race forces in-place editing on switch. |
| 6 | Per-route-locale equipment = Dedicated `race_route_locale_equipment` table | Andy 2026-05-18 | Ephemeral; no locales-list pollution; structured for validator reconciliation. Andy: "these are ephemeral and won't have any use outside of the race for which they were generated." |
| 7 | Layer 3B reads from race_events.target_row | Architect-pick | Single source of truth; existing athlete.target_event_* columns deprecated + migrated. |
| 8 | Locale role closed 7-element enum | Architect-pick | Matches backlog D-66 sketch + Layer 4 spec §7.13/§7.14 consumer surface. |
| 9 | Distance + elevation nullable | Architect-pick | Athletes book races 6+ months out without final route specs. |
| 10 | Route-locale sequence_idx UNIQUE per race with gaps allowed | Architect-pick | Avoids cascading rewrites on insertions. |

### 5.2 Stop-and-ask trigger retrospective

- **Triggers #5, #7, #8, #11** fired and routed properly via the 4 AskUserQuestion rounds + the architect-pick sub-decisions block. Per the Step 4a/4b/c/4d precedent, AskUserQuestion-based gating substitutes for formal `/plan` mode.
- No other triggers fired.

### 5.3 No carry-forward expected for Step 4e session

Step 4e implementation is self-contained against this design doc + the existing `Layer4_RaceWeekBrief_v1.md` prompt body. Trigger #5 may fire on the v1 RaceEventStub → RaceEventPayload type swap in `layer4/context.py` if structural-invariant surprises surface during implementation; routed via implementation-session AskUserQuestion gate per the precedent. Trigger #2 may fire if the `Layer4_RaceWeekBrief_v1.md` prompt body needs a v2 amendment surgical to §3 (Inputs) + §4 (Tool schema) to reflect the new typed payload — pre-flagged in §4.2 above.

### 5.4 Carried forward — Layer 1 typed payload

Still deferred. `Layer1Payload` is `dict[str, Any]` opaque pass-through across all entry points including the queued Step 4e. Lands as typed pydantic model when Layer 1 implementation arc begins.

### 5.5 Carried forward — Step 4f Pattern A orchestration

Step 4f remains heaviest queued sub-step. T3 cross-phase Pattern A naturally lands here.

---

## 6. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `aidstation-sources/Race_Events_D66_Design_v1.md` exists | ✅ inspection |
| Design doc has 15 H2 sections (Purpose + Decisions + Schema additions + RaceEventPayload contract + Layer 4 amendment + Onboarding extension + Profile UI + Layer 3B integration + Invalidation rules + Migration + Spec amendments paired + Test scenarios + Open items + Gut check + Forward pointers) | ✅ inspection |
| Design doc references §H.2 + §H.4 (not §A + §K) | ✅ grep — no remaining stale §A target-race / §K route-locale refs |
| `Layer4_Spec.md` §3.4 signature has `race_event_payload: RaceEventPayload` arg | ✅ grep line 234 |
| `Layer4_Spec.md` §3.4 parameter table has new row for race_event_payload | ✅ grep line 262 |
| `Layer4_Spec.md` §4.5 has `race_event_payload_missing` precondition row | ✅ grep line 810 |
| `Layer4_Spec.md` §4.5 has `race_event_date_mismatch_3b` precondition row | ✅ grep line 811 |
| `Layer4_Spec.md` §4.5 `kit_manifest_inputs_incomplete` annotation updated for D-66 active | ✅ grep line 812 |
| `Layer4_Spec.md` §5.4 rule body for `kit_manifest_inputs_incomplete` D-66-active rebinding | ✅ grep line 912 |
| `Layer4_Spec.md` §5.4 D-66 forward-pointer block flipped to ✅ Design wave shipped | ✅ grep |
| `Athlete_Onboarding_Data_Spec_v5.md` §A.1 has race-rules-paste-acknowledgment row | ✅ grep |
| `Athlete_Onboarding_Data_Spec_v5.md` §H.2 has race_format + race_rules_summary + is_target_event extension | ✅ grep |
| `Athlete_Onboarding_Data_Spec_v5.md` new §H.4 Route locales section exists | ✅ grep |
| `Project_Backlog_v48.md` exists | ✅ inspection |
| `Project_Backlog_v48.md` D-66 row flipped 🟡 → 🟢 | ✅ grep |
| `Project_Backlog_v48.md` file-revision-header bumped to v48 with this session narrative | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v48.md` | ✅ grep line 82 |
| `CLAUDE.md` Last-shipped-session is D-66 design wave; Step 4d demoted to Predecessor | ✅ inspection |
| `CLAUDE.md` Authoritative files has `Race_Events_D66_Design_v1.md` | ✅ grep |
| `CLAUDE.md` Next-forward-move recommends Step 4e (NOW UNBLOCKED) | ✅ inspection |
| Working tree shows 6 files modified / created | ✅ `git status` |
| Branch is `claude/plan-refresh-closing-handoff-yEd2O` (harness-pinned) | ✅ |

---

## 7. Files shipped this session

One commit on `claude/plan-refresh-closing-handoff-yEd2O` — 1 new design doc + 2 spec amendments + 3 bookkeeping bundled (precedented by Step 4d 13 + Step 4b/c 10 + PR-A 8 + Step 4a 8 + PR-C-followon 6 + PR-D 6 + PR-E 6):

1. New `aidstation-sources/Race_Events_D66_Design_v1.md` (~640 lines)
2. Modified `aidstation-sources/Layer4_Spec.md` (§3.4 + §4.5 + §5.4 + D-66 forward-pointer block amendments)
3. Modified `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` (§A.1 + §H.2 + new §H.4)
4. New `aidstation-sources/Project_Backlog_v48.md` (per Rule #12; v47 retained as predecessor)
5. Modified `aidstation-sources/CLAUDE.md` (current state bump + Layer 4 row + Backlog ref + Authoritative files + Next forward move)
6. New `aidstation-sources/handoffs/V5_Design_D66_Race_Events_Closing_Handoff_v1.md` (this file)

**6 files total. Over the 5-file ceiling intentionally** — Andy confirmed at session start via the AskUserQuestion gate scope pick (Full design wave); precedented across the Layer 4 implementation arc.

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; D-66 is design-layer (no UI surface yet; implementation PR will add §5.0 row for the new `/profile?tab=race-events` tab + onboarding §H.2 + §H.4 walks).
- Step 4e race-week-brief implementation — NOW UNBLOCKED 2026-05-18; queued as architect-recommended next forward move.
- Step 4f `plan_create` Pattern A orchestration — queued as the heaviest remaining; T3 cross-phase Pattern A lands here.
- v5 onboarding implementation PR — consumes §H.2 + §H.4 + §A.1 extensions; independent of Layer 4 implementation track.
- Migration of athlete.target_event_* columns to race_events — per design doc §10; lands in Step 4e implementation PR or v5 onboarding implementation PR (whichever ships first).
- D-50 wiring resumption — unblocked by D-58; can run in parallel.

---

**End of handoff.**
