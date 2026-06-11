# On-Demand Workout — D-63 Design

**Version:** 1.0
**Date:** 2026-05-15
**Status:** Design decisions locked; spec rewrite into authoritative location TBD (likely a new Layer 4 sub-section when Layer 4 lands).
**Backlog row:** D-63 (new this session)
**Track:** Plan-execution design wave — second of two new D-rows surfaced by Andy 2026-05-15 (sibling: D-64 plan-refresh tiers).
**Affects:** Layer 4 plan-gen (consumer — single-session synthesis path); Layer 1 athlete profile (read-only); D-60 effective-equipment view (read-only); `cardio_log` / `training_log` schema (extension — new columns); athlete UX (new "Build me a workout" form + result view); D-64 T1 hook (post-completion CTA).
**Cross-references:**
- `Plan_Refresh_D64_Design_v1.md` — sibling design doc; D-63's post-completion CTA fires a D-64 T1 with the on-demand workout's NL context.
- `Onboarding_D60_Design_v1.md` §4.4 — D-60 effective-equipment view read by D-63 location selection.
- `Onboarding_D61_Design_v1.md` — locale-as-source-of-equipment pattern carried forward.
- `Layer3_3A_Spec.md` — completed on-demand workouts feed athlete state per the same path as planned sessions.
- `Athlete_Onboarding_Data_Spec_v5.md` (Layer 1 source-of-truth — active injuries + athlete attributes consumed by D-63 generation).

---

## 1. Purpose

The current plan tells the athlete what to do today. Sometimes the athlete wants to do something **outside** the plan — right now, on demand:
- "I'm at the gym, plan says rest day, but I want to lift."
- "I have 90 minutes free this afternoon — give me a MTB ride."
- "I just got home; quick easy run before dinner."

Today there's no surface for this. Athletes either improvise (bypass the system entirely — performance feedback is lost) or skip the workout (lose the training opportunity).

D-63 adds a **"Build me a workout right now"** button that:
1. Takes athlete-supplied parameters (sport, duration, intensity, location).
2. Generates a single off-plan session **referring to current fitness + the current plan, but not part of it**.
3. Stores the completed workout so it feeds Layer 3A (athlete state evolves correctly).
4. Optionally triggers a D-64 T1 plan check after completion — "you did this; want to refresh the next 2 days?"

This is an **enterprise feature** per Andy 2026-05-15 — multi-athlete; not an Andy-specific affordance. Athletes' constraints (injuries, age, training load) come from their Layer 1 profile, not per-request.

Crucial framing: the on-demand workout **does not modify the plan**. It exists alongside it. Plan invalidation is a separate question routed through D-64 (the T1 hook is opt-in, not automatic).

---

## 2. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Athlete inputs | **Sport (Layer 0A enum), duration (30–360 min), intensity (Z1/Z2/Z3/Z4/Z5 OR named: easy/moderate/hard/race-pace), location (athlete's locale enum).** | Andy 2026-05-15. Minimum viable input set; everything else derives. Equipment derives from location. Athlete-level constraints derive from Layer 1 profile. |
| 2 | Layer placement | **Simplified Layer 4 invocation — single-session synthesis, no week pacing or block consideration.** Inputs: athlete profile (Layer 1) + current state (Layer 3A) + location-equipment view (D-60 effective view) + athlete's session params. Output: one structured session. | Andy 2026-05-15 — "Layer 4." Off-plan workout doesn't need periodization. Layer 4 owns session synthesis; D-63 invokes a narrower variant of that surface. |
| 3 | Equipment source | **D-60 effective view for the picked location:** (shared ∪ athlete-adds) ∖ athlete-removes. | Reuses the D-60 inherit/override view shipped in PR11. No new equipment-resolution path. |
| 4 | Athlete-level constraints | **Pulled from Layer 1 profile.** Active injuries (§B), age, recent training load, etc. NOT user-set per request. | Profile is single source of truth; per-workout constraint override would be a v2+ addition. (Andy 2026-05-15 explicitly: "wrist doesn't matter, that's just me" — meaning the wrist constraint should come from his profile, not be hard-coded.) |
| 5 | Multi-sport per request | **Single sport per request in v1.** Brick (multi-sport, e.g. ride + run) deferred to v2 expansion. | Scope discipline. Single-sport covers the dominant use case ("I want to MTB now"). |
| 6 | Output shape | **Structured session matching Layer 4's session output schema** (warmup / main / cooldown blocks for cardio; set/rep structure for strength). Layer 3A consumes on-demand sessions identically to planned ones. | Consistency. Avoids a parallel session-shape that Layer 3A would need to special-case. |
| 7 | Coaching voice | **Same direct-no-platitudes voice spec as planned sessions.** Inherits Layer 4's voice prompt body when Layer 4 lands; v1 stopgap uses the existing `coaching.py` voice. | Consistency across all coaching surfaces. CLAUDE.md "Coaching voice" applies. |
| 8 | Storage | **Extend `cardio_log` + `training_log`** with `is_ad_hoc BOOLEAN NOT NULL DEFAULT FALSE` + `ad_hoc_request_payload JSONB NULL` (athlete inputs). No new table. | Avoids schema sprawl in v1. Logged on-demand sessions feed Layer 3A through the same query path as planned sessions. |
| 9 | Lifecycle | **Generated-but-unlogged** sessions persist as "suggested" status (separate `ad_hoc_workout_suggestions` table, see §5.3). Logged sessions move to `cardio_log`/`training_log` with `is_ad_hoc=TRUE`. Unlogged suggestions can be regenerated or discarded by the athlete. | Simple lifecycle. No auto-discard timer in v1; review at first cohort scale. |
| 10 | T1 plan-check hook | **After athlete logs an on-demand workout**, surface non-modal CTA: "Want to refresh the next 2 days based on this session?" → triggers D-64 T1 with the workout pre-populated as NL context (e.g., "Did an unscheduled 60min MTB Z3 — absorb this into the next two days"). Athlete can dismiss; dismissal is logged. | Andy 2026-05-15 — "recommend a tier 1 plan check but the athlete can skip." Closes the loop between off-plan execution and plan invalidation. Soft, not forcing. |
| 11 | Cost protection | **Soft cap with override:** warning if athlete generates 5+ on-demand workouts in 24h. Allow override; log to telemetry. | Same shape as D-64's frequency caps. Cost protection without paternalism. |
| 12 | Location not in athlete's locales | **Inline "Quick add" path:** athlete selects "I'm somewhere else" → minimal form (sport-relevant equipment checkboxes, no full locale creation) → equipment view derives from those checkboxes only; no `gym_profiles` row created; not stored as a locale. | Andy's locales surface assumes pre-registered locations. Travel/one-off cases shouldn't force a full locale-creation flow. |
| 13 | Generation prompt body | **Deferred to its own spec session** (stop-and-ask trigger #2). D-63 defines the input/output CONTRACT; the prompt text lands separately, likely as part of Layer 4's prompt-body design. | Same framing as D-64's NL parser deferral. Spec the contract; prompt-engineer separately. |

---

## 3. Athlete UX

### 3.1 Entry surfaces

- **Dashboard** (`/dashboard`): "Build a workout" CTA card alongside D-64's "Refresh your plan" card.
- **Training plan view**: "Build a workout" button on rest days (where there's no planned session) and a less-prominent "Add an extra session" affordance on training days.
- **Mobile** (when mobile UI exists): same surfaces; form should be touch-friendly.

### 3.2 Input form

Single-page form (no multi-step wizard — Andy's "minimum friction" framing):

| Field | Control | Source |
|---|---|---|
| Sport | Dropdown | Layer 0A sport list (filtered to athlete's `framework_sport` set + cross-training options) |
| Duration | Slider or numeric, 30–360 min in 15-min increments | Athlete-set per request |
| Intensity | Radio: Easy (Z1–Z2) / Moderate (Z2–Z3) / Hard (Z3–Z4) / Race-pace (Z4–Z5) | Athlete-set per request |
| Location | Dropdown of athlete's locales + "Somewhere else" option | Athlete's `locale_profiles` rows + the §3.4 quick-add path |

"Generate workout" submit button.

### 3.3 Result view

After generation:
- Session displayed in the same card layout as planned sessions (consistency).
- Header: sport icon + duration + intensity badge + location name.
- Body: warmup / main / cooldown blocks (cardio) OR exercise list with sets/reps (strength).
- Footer: [Log this workout] (primary action) + [Regenerate] (re-runs with same inputs) + [Discard] (drops the suggestion).

[Regenerate] re-invokes the synthesis with the same inputs; expected to produce a different session (LLM stochasticity is acceptable for "give me another option").

### 3.4 "Somewhere else" quick-add path

Selecting "Somewhere else" reveals:
- Sport-relevant quick-equipment checkboxes (e.g., for MTB: bike + helmet + spare tube; for running: shoes + water; for strength: dumbbells / barbell / rack / bench)
- Free-text "Other equipment" line
- "Generate" button

Equipment view for synthesis = the checked items only. No locale created; no `gym_profiles` row written. Athlete can save this as a new locale via a small "Save as locale" link (which routes to the existing `/locales/new?manual=1` flow with prefilled equipment).

### 3.5 Post-completion T1 hook

When athlete clicks [Log this workout]:
1. Workout writes to `cardio_log`/`training_log` with `is_ad_hoc=TRUE`.
2. Banner appears: "Logged. Want to refresh the next 2 days based on this session? [Yes — refresh] [No, thanks]"
3. [Yes — refresh] → fires D-64 T1 with NL context auto-filled (e.g., "Did an unscheduled 60min MTB Z3-Z4 at Lebanon Hills") + tier=T1; athlete sees the D-64 modal with NL pre-filled (editable).
4. [No, thanks] → logs `t1_hook_dismissed=TRUE` to telemetry; banner fades.

### 3.6 Frequency-cap UX

When athlete exceeds the cap (Decision #11):
- Modal-confirm: "You've generated 5 on-demand workouts today. Each generation costs ~$X in compute. Continue?" + [Generate anyway] + [Cancel].
- Override logged to telemetry.

---

## 4. Layer placement + scope

### 4.1 What D-63 invokes

D-63 invokes a **single-session synthesis** path inside Layer 4. Layer 4's full plan-gen has additional context (week pacing, block phase, periodization shape); the single-session path strips those, keeps only:
- Layer 1 athlete profile (constraints — injuries, age, etc.)
- Layer 3A latest athlete state (fitness, fatigue)
- D-60 effective equipment view for the picked location
- D-63 athlete params (sport, duration, intensity)

Layer 4 owns the prompt body for both paths. D-63 just signals "single-session mode" via a flag.

### 4.2 What D-63 does NOT invoke

- **No 2x re-runs.** Equipment and discipline assignments are read from existing 2C/2A outputs.
- **No 3B/3C/3D.** No periodization re-eval; no cross-node conflict; no HITL gate. Athlete is asking for one workout; the plan-level reasoning is bypassed.
- **No plan-version write.** On-demand workouts aren't planned sessions; they don't bump `plan_version_id`.

### 4.3 Layer 4 input contract addition (when Layer 4 specs land)

```python
@dataclass
class SingleSessionRequest:
    athlete_id: int
    sport: str                         # Layer 0A canonical sport name
    duration_min: int                  # 30–360
    intensity: Literal['easy', 'moderate', 'hard', 'race_pace']
    locale_slug: str | None            # athlete's locale slug, OR None for "somewhere else"
    quick_equipment: list[str] | None  # equipment tags when locale_slug is None
    notes_for_synthesizer: str | None  # optional athlete note ("focus on hill climbs")
```

Layer 4 returns a session matching its planned-session output schema (TBD in Layer 4 spec).

---

## 5. Storage

### 5.1 Extension to `cardio_log`

```sql
ALTER TABLE cardio_log
  ADD COLUMN is_ad_hoc BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN ad_hoc_request_payload JSONB,        -- the SingleSessionRequest from §4.3
  ADD COLUMN ad_hoc_suggestion_id BIGINT;          -- FK to ad_hoc_workout_suggestions (§5.3)

CREATE INDEX cardio_log_ad_hoc_idx ON cardio_log (user_id, is_ad_hoc) WHERE is_ad_hoc = TRUE;
```

### 5.2 Extension to `training_log` (strength)

```sql
ALTER TABLE training_log
  ADD COLUMN is_ad_hoc BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN ad_hoc_request_payload JSONB,
  ADD COLUMN ad_hoc_suggestion_id BIGINT;

CREATE INDEX training_log_ad_hoc_idx ON training_log (user_id, is_ad_hoc) WHERE is_ad_hoc = TRUE;
```

### 5.3 New table: `ad_hoc_workout_suggestions`

Holds generated-but-not-yet-logged suggestions.

```sql
CREATE TABLE ad_hoc_workout_suggestions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_payload JSONB NOT NULL,         -- the SingleSessionRequest
    generated_session JSONB NOT NULL,       -- the session structure Layer 4 returned
    status TEXT NOT NULL DEFAULT 'suggested'
        CHECK (status IN ('suggested', 'logged', 'discarded', 'regenerated')),
    logged_into_table TEXT,                 -- 'cardio_log' | 'training_log' | NULL
    logged_into_id BIGINT,                  -- FK to the row in cardio_log or training_log when logged
    discarded_at TIMESTAMPTZ,
    regenerated_into_id BIGINT REFERENCES ad_hoc_workout_suggestions(id),  -- chain regenerations
    token_cost_estimate INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ad_hoc_workout_suggestions_user_status_idx
  ON ad_hoc_workout_suggestions (user_id, status, requested_at DESC);
```

### 5.4 Telemetry on `plan_refresh_log` (D-64 table)

When the §3.5 T1 hook fires, the resulting `plan_refresh_log` row carries:
- `nl_text` = the auto-generated context ("Did an unscheduled <duration>min <sport> <intensity> at <locale>")
- `parsed_intent.raw_text` = same
- A new optional column on `plan_refresh_log`: `triggered_by_ad_hoc_id BIGINT` (FK to `ad_hoc_workout_suggestions.id`). This lets analytics correlate ad-hoc sessions with subsequent plan refreshes.

(Add this column to the D-64 schema spec — flagged in §10.)

### 5.5 Lifecycle states

| Status | Meaning | Transitions |
|---|---|---|
| `suggested` | Generated, not yet acted on | → `logged` (athlete logs it) / → `discarded` (athlete dismisses) / → `regenerated` (athlete clicks Regenerate; new row created) |
| `logged` | Athlete completed and logged the session | Terminal (workout exists in `cardio_log`/`training_log`) |
| `discarded` | Athlete dismissed the suggestion without logging | Terminal |
| `regenerated` | Superseded by a re-generation | Terminal (this row stays for telemetry; `regenerated_into_id` points to the next suggestion) |

`suggested` rows older than N days (TBD: 30? 90?) prune by a future retention cron — same shape as D-62 / D-64 telemetry retention.

---

## 6. Constraint resolution

### 6.1 Active injuries

Read from Layer 1 §B (Current Injuries). Passed to Layer 4 synthesis as exclusion/downgrade context (same as planned-session synthesis). Athlete cannot override per-request — if their profile says "no wrist-loaded exercises," the on-demand workout will not include them.

(Andy 2026-05-15 was explicit: profile-level constraints, not per-request.)

### 6.2 Recent training load

Read from Layer 3A latest output. If athlete just did a hard session 6 hours ago, synthesis weights toward easier intensity even if athlete picks "hard" — coaching voice surfaces this in the session notes ("This is lower intensity than you asked for because you logged a hard session this morning. To override, log this and refresh your plan with T1.").

This is a soft override — synthesis modulates; it doesn't refuse. Athlete can [Regenerate] to push for the harder version; coaching voice gets more direct on the second pass.

### 6.3 Sport availability at location

If athlete picks "MTB" + "home gym," the location's effective equipment view can't support the sport. **D-63 caller pre-checks sport availability against the picked locale's equipment view (or against `quick_equipment` when in "Somewhere else" mode) before invoking Layer 4.** When the picked sport is not resolvable, D-63 returns its own structured "sport unavailable" response directly to the frontend — Layer 4 is never invoked — and the frontend renders: "MTB not possible at Home Gym (no bike). Pick a different location or sport." [Pick another location] / [Pick another sport] buttons. The rest-shape is reserved for genuine coaching-chosen rest days; the system-error path stays separate from the coaching domain. Layer 4 raises `Layer4InputError('request_sport_unavailable_at_locale')` defensively per Layer4_Spec §4.4 if the caller-side pre-check is missed.

### 6.4 Off-plan-day check

If today's planned session is uncompleted, synthesis surfaces a coaching note: "You have a planned <session> today. This on-demand workout is in addition to it. To replace, log this and refresh your plan with T1." (Same T1 hook surfaces post-log.)

---

## 7. Implementation gating

D-63 implementation **gates on Layer 4 spec landing** (same as D-64) because:
- Single-session synthesis is a Layer 4 path; Layer 4's prompt body and output schema must exist first.
- Coaching voice integration uses Layer 4's voice spec.
- Output session shape must match Layer 4's planned-session shape (Decision #6).

**Pre-Layer-4 stopgap (optional, v1 path):** ship a degraded form against `coaching.py`'s existing v1 surface. Athlete picks sport/duration/intensity/location → v1 coaching prompt augmented with the params → generated session shown. No `ad_hoc_workout_suggestions` table; just direct write to `cardio_log` on log. No T1 hook (D-64 isn't shipping pre-Layer-4 either). Acceptable as a placeholder; loses the structured session output, the suggestion lifecycle, and the T1 integration. **Recommend: don't ship the stopgap; wait for Layer 4.**

---

## 8. Open items

- **Layer 4 spec doesn't exist.** D-63 (and D-64) implementation blocks on Layer 4 spec.
- **Generation prompt body deferred** to Layer 4 prompt-engineering work. D-63 defines the input/output contract.
- **Mobile UX.** No mobile client today (Apple Health / Samsung Health out of scope per CLAUDE.md). When mobile lands, the form should be touch-optimized; out of scope this spec.
- **Brick (multi-sport) sessions** deferred to v2.
- **Per-request override of profile constraints** deferred to v2 (Decision #4).
- **Long-running synthesis.** Layer 4 single-session synthesis is expected to be fast (single LLM call). If it ever exceeds athlete patience (say, >10s), need a progress indicator. Out of scope this spec.
- **Sharing on-demand workouts.** "Athlete generates a great session and wants to share with their team" — not a v1 use case; flagged for team-features track.
- **Recurring on-demand workouts.** "Generate this same session every Tuesday" → that's a plan modification, belongs in D-64 T1/T2 territory, not D-63.
- **Auto-discard timer for `suggested` status.** Spec'd as "TBD: 30 or 90 days?" Decide with first-cohort data.
- **`plan_refresh_log.triggered_by_ad_hoc_id` column** (§5.4) needs to land on the D-64 schema. Cross-spec dependency; flagged in both specs.
- **Cost-estimate copy.** Pre-Layer-4 we can't show actual dollar amounts (token counts unknown). Generic "compute cost" copy until Layer 4 lands.
- **Strength-session output shape.** Layer 0B exercise library is the source; cardio uses warmup/main/cooldown blocks; strength uses set/rep structure. Both shapes defined by Layer 4 spec; D-63 just consumes.

---

## 9. Test scenarios (forward-pointers)

When D-63 implements:

1. Athlete picks MTB + 60min + Hard + (their MTB-equipped locale) → suggestion generated; structured session displayed; `ad_hoc_workout_suggestions` row written.
2. Athlete clicks [Log this workout] → `cardio_log` row written with `is_ad_hoc=TRUE`; suggestion row → `status='logged'`; T1 hook banner appears.
3. Athlete clicks [Yes — refresh] on T1 hook → D-64 T1 fires with NL pre-filled; `plan_refresh_log.triggered_by_ad_hoc_id` set.
4. Athlete clicks [Regenerate] → new suggestion row created; old row → `status='regenerated'`; `regenerated_into_id` chain populated.
5. Athlete picks MTB + 60min + Hard + Home Gym (no bike) → D-63 caller pre-check per §6.3 catches the unavailable sport; D-63 returns the unavailable response directly to the frontend ([Pick another location] / [Pick another sport]); Layer 4 not invoked; no suggestion row written.
6. Athlete picks Strength + 45min + Moderate + Commercial Gym → strength session synthesized using D-60 effective view of the gym's equipment; respects active injuries.
7. Athlete with active wrist injury picks Strength → no wrist-loaded exercises in the output (Decision #4 + §6.1).
8. Athlete picks "Somewhere else" + checks dumbbells + barbell → quick-add path; no locale created; synthesis uses checked equipment only.
9. Athlete generates 5 workouts in 1 hour → 6th attempt triggers soft-cap warning per §3.6.
10. Athlete logged a hard session this morning, picks Hard → synthesis modulates to moderate per §6.2; coaching note explains; regeneration request returns same modulation.
11. Athlete generates suggestion, leaves app, returns 30 days later → suggestion still exists with `status='suggested'` (no auto-discard in v1 — open item).

---

## 10. Gut check

**What's right:**
- **Closes a real gap.** Off-plan workouts happen all the time; today they're invisible to the system. D-63 makes them visible without making them part of the plan.
- **D-60 + D-63 fit cleanly.** The effective-equipment view shipped in PR11 is the equipment-resolution path D-63 uses. Reuses, doesn't reinvent.
- **D-64 hook closes the loop.** Off-plan execution → optional plan invalidation. Athlete owns the decision; system makes it easy.
- **Layer 1 profile = constraint source.** Andy's "wrist doesn't matter, that's just me" framing was the right correction — profile-level constraints scale across athletes; per-feature hard-coding doesn't.
- **Storage extension over new table.** `is_ad_hoc` flag on existing logs avoids parallel query paths in Layer 3A consumption.

**Risks:**
- **"Generate one more option" stochasticity could feel arbitrary.** [Regenerate] producing wildly different sessions for the same inputs may erode trust. Mitigation: synthesis prompt should commit to consistency within an athlete's profile (same sport + intensity + duration → similar session shape with reasonable variation). Prompt-engineering concern; flagged for the prompt-body design pass.
- **T1 hook could feel pushy.** "You logged a workout — want to refresh?" every time may train athletes to dismiss reflexively. Mitigation: dismissal logged; cohort data could inform whether to suppress the prompt for athletes who consistently dismiss.
- **"Somewhere else" quick-add bypasses the locale system.** Athletes may end up with a graveyard of one-off "wherever" generations whose equipment-context isn't captured anywhere persistent. Mitigation: the [Save as locale] affordance lets them promote it; otherwise, the suggestion row carries the equipment payload for traceability.
- **Cost at scale.** A motivated athlete who refreshes-then-regenerates-then-refreshes can rack up cost fast. Soft caps + telemetry + override-logging is the v1 protection; hard caps may be needed at cohort scale.
- **`suggested` rows piling up.** No auto-discard in v1 means athletes who generate-without-logging accumulate cruft. Open item; tune post-deploy.

**What might be missing:**
- **Cardio-vs-strength UX divergence.** Cardio sessions have warmup/main/cooldown timing structure; strength sessions have exercise lists with sets/reps. Single result-view layout may not serve both well. Likely need two layouts; flagged for Layer 4 spec.
- **In-progress session interaction.** Athlete is mid-workout (planned), opens app, generates an on-demand. What happens to the in-progress planned session? Recommend: planned session stays as "in progress"; on-demand is independent. No interaction. Flagged for verification when implemented.
- **Discovery.** "Build a workout" is a new surface; athletes have to know it exists. Onboarding tour or first-time-empty-state copy might be needed; out of scope this spec.
- **Goal-context awareness.** Generated session should be aware of the athlete's race goal (Pocket Gopher Extreme for Andy). Probably handled by Layer 1 → Layer 4 context flow already, but worth verifying when prompt-body lands.
- **Coaching observations from on-demand patterns.** Athlete who consistently does "easy MTB" on rest days is signaling something (overreaching? under-recovery?). Same future Layer-5 advisory surface that D-64 mentioned would consume this signal.

**Best argument against this scope:**
At N=1 athlete (Andy), this is a button he'd click maybe once a week. The infrastructure cost (new table, schema extensions, T1 hook, lifecycle logic, telemetry) is meaningful for a low-frequency use case. A simpler path: free-text "log a session" form that just writes to `cardio_log` without LLM synthesis at all. That covers "I did something off-plan, here's the data" without any generation cost.

Counter: the LLM-synthesis IS the value. Andy's framing is "build me a workout" — not "let me log what I did." The synthesis (referencing current fitness + plan + location-equipment) is what makes this a coaching feature instead of a logging feature. Stripping the synthesis turns this into journal-entry-with-extra-steps. The marquee value is the workout the system suggests; the lifecycle around it (suggested → logged → optional T1) is the plumbing that makes that suggestion safe to act on.

Counter to the counter: if synthesis quality is mediocre (athlete regenerates 3× before getting something usable, or always tweaks the suggestion before logging), the value evaporates and the cost stays. Mitigation is in the prompt body — which is deferred. So this design's payoff is contingent on Layer 4's synthesis quality being genuinely good. Carrying that contingency forward to the prompt-body spec session.

Net: ship the framework's storage + lifecycle + integration design; tie the outcome to Layer 4's prompt quality when that lands.

---

*End of OnDemand_Workout_D63_Design_v1.md.*
