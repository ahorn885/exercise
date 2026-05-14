# Onboarding D-61 Design — Plan-Level Schedule + Session-to-Locale Assignment

**Version:** 1.0
**Date:** 2026-05-14
**Status:** Design decisions locked; spec rewrite pending (`Athlete_Onboarding_Data_Spec_v5.md` lands after all four design tracks settle).
**Backlog row:** D-61
**Track:** Third of the four-track Onboarding Design Wave (D-58–D-61). Sequence: D-59 ✅ → D-60 ✅ → **D-61 (this doc)** → D-58.
**Affects:** `Athlete_Onboarding_Data_Spec` §G (Schedule & Availability), §J.5 (Locale Capacity Metrics — field removed); new `daily_availability_windows` table; `locale_profiles.preferred` column; Layer 4 plan-gen consumer contract for session→locale assignment; session-card UX in the eventual plan-execution UI.
**Cross-references:**
- `Onboarding_D59_Design_v1.md` — establishes `locale_profiles.lat` / `.lng`; D-61 reads these for distance ranking.
- `Onboarding_D60_Design_v1.md` — establishes the shared-profile + per-athlete-override effective-equipment view; D-61 reads this as the qualifying filter.
- `Athlete_Onboarding_Data_Spec_v4.md` §G (lines 554–574 — six weekly availability fields D-61 restructures), §J.5 (lines 749–755 — two fields D-61 removes/relocates), §K (lines 758–814 — overlay model that anchors per-date locale).
- `Project_Backlog_v15.md` D-61 (problem statement; framed "session time at plan, not at locale"; Q3 max-session-duration framing overridden by Andy 2026-05-14 — see decision #5 below).

---

## 1. Purpose

The v4 spec splits training-time information across two sections in a way that doesn't match how plans get generated:

- **§G (Schedule & Availability)** holds *weekly aggregates* — total hours, days available, typical session duration. These are coarse-grained; they don't say *when* on each day the athlete can train.
- **§J.5 (Locale Capacity Metrics)** holds *per-locale* "Typical session time available" and "Max session duration." These bind time to location, which is backwards: an athlete's Tuesday-morning 60-minute window doesn't change because they're at the hotel gym instead of the home gym.

D-61 fixes both halves:

1. **Time lives at the plan level, not the locale level.** Athletes answer "when can you train" once, per-day, as part of §G.
2. **Locale is computed per session** by plan-gen, filtered by equipment fit (D-60's effective-equipment view) and ranked by distance from the active anchor locale (resolved through §K overlays).
3. **The §J.5 `Max session duration` field is removed entirely from v5**, not relocated. Andy 2026-05-14: a Tier-3 field with no observed plan-gen consumption is noise; real per-locale caps are enforced at session-start through the same JIT swap surface D-61 introduces, not through a stored field.

This reframes the v4 separation: §G owns *when*; D-60 owns *with what equipment* per location; D-59 owns *where each locale is*; D-61 owns the *runtime composition* (per-session pick).

---

## 2. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Schedule granularity in §G | **Per-day windows replace weekly aggregates; Long Session Available and Doubles Feasible stay as orthogonal capacity flags.** Each of 7 days carries: enabled? + window start time + window duration (minutes), with an optional second window for doubles-feasible days. Total weekly hours derives. Athlete enters per-day; weekly aggregate is displayed, not entered. | Andy 2026-05-14. Per-day is honest about how plans actually run — "Mon 7am 60min, Thu 6am 75min, Sat long" is the real schedule, not "10 hrs/week + days." Long-session capacity and doubles feasibility are orthogonal to per-day windowing (a long-session day is a different *kind* of capacity, not a longer window); both stay as their own fields. |
| 2 | Session→locale assignment algorithm | **Equipment-qualifying filter → distance ranking → athlete-set `preferred` flag wins inside the qualifying set.** Per-session manual swap always available. | Andy 2026-05-14. D-60's binary available/not-available makes the qualifying filter clean (no fuzzy match-quality score). Distance is the only meaningful sort among qualified locales. A `preferred` flag handles the "this commercial gym is closer than my home gym but I want home as the default when both qualify" case without inventing a multi-tier tiebreaker chain. |
| 3 | Anchor locale (the point distance is measured from) | **The plan-active locale at the session's date, resolved through §K overlays.** Default: the athlete's `is_primary_locale=TRUE` locale. §K self-overlays with `Active Locale` set override the default for their date window. Joint-training overlays override identically. | Reuses the v4 §K machinery (already specced) for the "where is the athlete on date D" question. D-61 doesn't add a new anchor concept; it asks the same question per session and computes distance from the answer. |
| 4 | Max session duration field | **Removed from v5 entirely.** v4 §J.5's `Max session duration (hard constraint)` is dropped from the spec, not relocated. | Andy 2026-05-14. Original handoff §6.1 Q3 framed the question as locale vs. shared-gym-profile; Andy chose a third option not on the original list. Tier-3 fields with no observed plan-gen consumption add survey burden for no signal. Real per-locale caps (pool reservation, gym closing time) are enforced at session start through the JIT swap surface in decision #6 — the athlete swaps locales or shortens the session in the moment, rather than maintaining a stored cap. |
| 5 | Typical session time available field | **Removed from v5 entirely.** v4 §J.5's `Typical session time available` is dropped — superseded by the per-day window duration in decision #1. | The per-day window is a richer signal than a per-locale enum. Once §G captures per-day duration, §J.5's locale-bound enum is redundant. Drop, don't relocate. |
| 6 | Per-session locale-picking UX | **JIT at session start with a tap-to-swap affordance, plus a non-required "Session locations" review surface in the plan summary.** Plan-gen picks the default; athlete sees the assignment on the session card; swap is one tap; the plan-summary review view exists for athletes who want a bulk sanity pass but is never a forcing function. | Andy 2026-05-14. Bulk plan-gen-time confirmation is friction athletes will skip; JIT respects current state (the athlete is at the locale; they know what's actually there). The optional review view costs little and serves athletes who want to scan the upcoming week. |
| 7 | Athlete-set `preferred` flag scope | **One boolean per `locale_profiles` row.** No per-discipline or per-day variants in v5. Multiple locales can be marked preferred; ties inside the preferred subset resolve by distance. | Smallest expressive primitive that handles Andy's stated case. Per-discipline preference (e.g., "for swim sessions, prefer the YMCA; for strength, prefer home gym") is a v2 expressivity refinement; the qualifying filter already does most of that work because swim sessions don't qualify against a home gym without a pool. |
| 8 | No-qualifying-locale fallback | **Session is flagged `assignment_status='unassigned'` with three athlete options: (a) swap a substitutable exercise that does qualify against the current locale set, (b) add or temporarily activate a locale that qualifies, (c) defer the session.** Plan-gen does not silently degrade to "bodyweight only" or invent equipment. | Honors the D-60 "no inferences" stance — plan-gen doesn't pretend a barbell session can happen without a barbell. The flag is the honest signal; the three options match the actual moves an athlete makes when stuck. |
| 9 | Tap-to-swap re-validation | **System re-runs the qualifying filter against the swap target; if the target doesn't qualify, show a warning ("This locale is missing [equipment]; the session won't run as planned") with options to accept-and-modify, accept-and-defer, or cancel the swap.** Athlete can always override the warning. | Honest about consequences without being paternalistic. Athletes who know better than the equipment data (D-60 is crowd-sourced and imperfect) can override; athletes who didn't realize get a flag. |

---

## 3. Per-day schedule shape (replaces v4 §G)

### 3.1 Fields

The §G replacement is centered on a 7-row per-day table plus three orthogonal capacity fields:

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Daily Windows | Repeating per day of week (Sun–Sat): `enabled` (Boolean) + `window_start` (time-of-day) + `window_duration` (minutes, integer 30–360) + optional `second_window_start` + `second_window_duration` (gated on Doubles Feasible) | 1 | Hard scheduling envelope per day; plan-gen places sessions inside windows; days with `enabled=FALSE` are unavailable for any non-rest session | Self-report |
| Long Session Available | Y/N + day (one or multiple days from enabled set) + max duration (2 / 3 / 4 / 5 / 6 / 8+ hr) | 1 | Long run/ride/hike ceiling per week; overrides daily window cap on the picked day(s) | Self-report |
| Doubles Feasible | Enum (Regularly / Occasionally / No) | 1 | Whether second windows can be entered for any day; gates the second-window fields' visibility in the form | Self-report |
| Preferred Rest Day(s) | Day-of-week single or multi-select (must be a subset of days with `enabled=FALSE`, or treated as a soft preference if enabled days are picked) | 2 | Soft rest-day preference signal for plan-gen; "I'd rather rest Sunday than Saturday" | Self-report |

### 3.2 Derived/displayed values (not entered)

- **Available Training Hours per Week** — sum of `window_duration` across all enabled days + second windows. Displayed in the §G UI as athletes enter per-day data; provides immediate feedback ("you've allocated 6.5 hrs/week") without requiring a separate entry that can drift from the per-day truth.
- **Training Days Available** — derived from `enabled=TRUE` rows. v4 had this as an explicit multi-select; v5 removes the explicit field.
- **Typical Session Duration** — modal value of `window_duration` across enabled days. Optional display only; not stored.

### 3.3 Window semantics

- `window_start` is an *earliest start*, not a fixed start time. Plan-gen can schedule the session to start any time between `window_start` and `window_start + (window_duration - session_duration)`. Sessions cannot extend past `window_start + window_duration`.
- Daily windows do not enforce sport mix — that lives at plan-gen against the discipline plan from Layer 2 + the athlete's phase.
- The second window is only consulted on days the athlete picked Doubles Feasible = Regularly *or* Occasionally; for "Regularly" it's used freely, for "Occasionally" it's used at plan-gen's discretion within a per-week double-day cap (default: 2 doubles per week; final tuning is Layer 4 plan-gen's call).
- Long Session day windows are *replaced* by the long-session capacity on the selected day: if the athlete picks Saturday with max 6 hr, Saturday's `window_duration` is treated as 6 hr × 60 = 360 min when scheduling the long session, regardless of the entered window. Other Saturday sessions (e.g., a recovery walk) still respect the entered window.

### 3.4 What gets dropped from v4 §G

| v4 field | Status | Replacement |
|---|---|---|
| Available Training Hours per Week | Dropped | Derived/displayed from per-day windows |
| Training Days Available | Dropped | Derived from `enabled` flags |
| Typical Session Duration | Dropped | Modal of per-day durations; not stored |
| Long Session Available | Kept | Same shape; orthogonal to per-day windows |
| Doubles Feasible | Kept | Same shape; gates second-window fields |
| Preferred Rest Day(s) | Kept | Same shape; tier demoted 1 → 2 |

---

## 4. Session→locale assignment

### 4.1 The algorithm

For each session in the generated plan:

1. **Required equipment set.** Plan-gen (Layer 4) determines the equipment needed for the session — the union of equipment tags consumed by all prescribed exercises plus any sport-specific gear from §J.3.
2. **Anchor locale.** Read the athlete's active locale for the session's date through §K: default to the athlete's primary; if a §K overlay (self or joint-training) covers the date and sets `Active Locale`, that wins.
3. **Candidate locale set.** All `locale_profiles` rows for the athlete in the active locale's proximity cluster — the 42.2 km / 26.2 mi neighborhood per §J's proximity model (preserved from v4; D-59 storage shape) plus the active locale itself.
4. **Qualifying filter.** For each candidate, compute the athlete's effective equipment view per D-60 (shared profile + per-athlete overrides, minus disputed items the athlete hasn't explicitly re-added). A candidate qualifies if its effective view is a superset of the required equipment set.
5. **Preferred-flag check.** If any qualifying candidate has `locale_profiles.preferred=TRUE`, restrict the candidate set to preferred-flagged ones.
6. **Distance ranking.** Sort the remaining set by haversine distance from the anchor locale's `(lat, lng)`. Closest wins.
7. **Manual-entry locale handling.** Manual-entry locales (D-59 `manual_entry=TRUE`, no coords) are excluded from distance ranking but remain eligible if explicitly flagged `preferred=TRUE` and they qualify; tie-breaks against distance-ranked alternatives by preferring the distance-ranked option.
8. **No-qualifying-candidate path.** If the qualifying set is empty: mark the session `assignment_status='unassigned'`; surface to the athlete with the three options in decision #8 (swap exercise, swap/activate locale, defer).

### 4.2 When assignment runs

Assignment runs at three points:

- **Plan generation** — first pass for every session. The default assignment lands on the session.
- **§K overlay change** — when an athlete adds, edits, or deletes a §K overlay that affects future sessions, re-run assignment for affected dates only.
- **Locale change** — when an athlete edits a locale (equipment override, `preferred` flag toggle, deletion), re-run assignment for any session in the next 14 days whose assignment used that locale. Older sessions stay logged with the original assignment (audit-preserving).

Re-runs do not silently change athlete-confirmed assignments. If an athlete has tap-confirmed or tap-swapped a session's locale, the assignment is locked (`assigned_by='athlete_swap'`); the re-run flags the assignment as "stale" and surfaces in the session card but doesn't auto-overwrite.

### 4.3 The `preferred` flag

`locale_profiles.preferred` is a single BOOLEAN with these semantics:

- Default FALSE.
- Athlete can set TRUE on any number of locales.
- Setting `preferred=TRUE` on `is_primary_locale=TRUE` is the no-op-but-explicit case (primary is already the anchor default; preferred-among-qualifying is the additional behavior).
- No uniqueness constraint — multiple preferred locales coexist; if more than one qualifies for a session, distance breaks the tie inside the preferred subset.

The flag is set/unset from the locale-edit screen. No bulk-set; per-locale only.

---

## 5. UX for per-session locale picking

### 5.1 Session card

Each generated session displays:

```
[Date]  [Discipline]
Time:   [window_start] — [duration]
Locale: [resolved locale name]   ↺ Swap
```

The session card is the primary touch point. `↺ Swap` opens a modal listing all locales in the active proximity cluster with their qualifying status (✓ / ✗ + missing-equipment hint for ✗) and distance. Athlete picks; system re-runs the assignment validation and applies (with the warning per decision #9 if the pick is non-qualifying).

### 5.2 Plan summary review surface

A non-required "Session locations" view shows the next 4 weeks of session→locale assignments in a single table. Athletes who want a bulk sanity pass can scan; athletes who don't, don't. Bulk-edit affordance: clicking a row opens the same swap modal as the session card.

### 5.3 Stale-assignment surfacing

When §4.2's "re-run for affected dates" or "re-run for next 14 days" produces a different default than the locked athlete-confirmed assignment, the session card shows:

> *"Locale assignment is stale. Original plan-gen pick: [A]. After your recent change, the better pick may be [B]. [Apply suggestion] [Keep [A]]"*

Not auto-overwriting respects athlete intent; flagging keeps the system honest about the divergence.

---

## 6. §J.5 cleanup

v4 §J.5 (Locale Capacity Metrics) is removed entirely in v5. Both fields are dropped:

- `Typical session time available` — superseded by per-day window duration (decision #5).
- `Max session duration (hard constraint)` — dropped without replacement (decision #4); real per-locale caps are enforced JIT at session start, not stored.

Migration of existing v1 `locale_profiles` rows that may have populated either field: no automatic transformation; the columns are simply ignored by v5 read paths. The v5 implementation PR drops the columns on `_PG_MIGRATIONS` (per the `_SQLITE_MIGRATIONS` freeze ratified in `Athlete_Data_Integration_Spec_v4` §2.5):

```sql
ALTER TABLE locale_profiles DROP COLUMN IF EXISTS typical_session_time;
ALTER TABLE locale_profiles DROP COLUMN IF EXISTS max_session_duration;
```

If those columns don't exist in the v1 schema (they may be design-only fields that never landed in DDL), the migration is a no-op.

---

## 7. Schema additions

All new tables and columns land on `_PG_MIGRATIONS` only.

### 7.1 New table — `daily_availability_windows`

```sql
CREATE TABLE IF NOT EXISTS daily_availability_windows (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    day_of_week         SMALLINT NOT NULL,
        -- 0=Sunday, 6=Saturday. Mirrors Python's datetime.weekday() shifted
        -- by one (Sunday=0 keeps the form display order natural).
    window_index        SMALLINT NOT NULL DEFAULT 0,
        -- 0 = primary window; 1 = secondary window (doubles). Hard cap at 1.
    enabled             BOOLEAN NOT NULL DEFAULT FALSE,
    window_start        TIME,
        -- Earliest start time of day. NULL when enabled=FALSE.
    window_duration_min INTEGER,
        -- Window length in minutes (30–360). NULL when enabled=FALSE.
    updated_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, day_of_week, window_index),
    CHECK (window_index IN (0, 1)),
    CHECK (
        (enabled = FALSE AND window_start IS NULL AND window_duration_min IS NULL)
        OR (enabled = TRUE AND window_start IS NOT NULL AND window_duration_min IS NOT NULL)
    ),
    CHECK (window_duration_min IS NULL OR window_duration_min BETWEEN 30 AND 360)
);

CREATE INDEX IF NOT EXISTS daw_user_day_idx
    ON daily_availability_windows (user_id, day_of_week);
```

Primary-window rows always exist (one per athlete × 7 days at onboarding completion, with `enabled=FALSE` for unselected days). Secondary-window rows exist only when athlete picked Doubles Feasible ≠ No and entered a second window for that day.

### 7.2 New columns on `locale_profiles`

```sql
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS preferred BOOLEAN DEFAULT FALSE;
```

No uniqueness constraint; semantics per §4.3.

### 7.3 Other §G fields

`Long Session Available`, `Doubles Feasible`, `Preferred Rest Day(s)` continue to live on the athlete-profile row (wherever v1 stores §G — verify during v5 implementation; do not assume a specific table without reading). The v5 implementation PR aligns the storage to whatever shape lands for the per-day windows.

### 7.4 Session-assignment storage

The session's locale assignment lives on whatever table Layer 4 plan-gen uses to store generated sessions (out of scope for this design doc — Layer 4 owns it). Required columns on that table:

| Column | Purpose |
|---|---|
| `locale_id` | FK to `locale_profiles`; the resolved locale for this session. NULL when `assignment_status='unassigned'`. |
| `assignment_status` | Enum: `'plan_gen'` / `'athlete_swap'` / `'unassigned'` / `'stale'`. |
| `assigned_at` | Timestamp of the last assignment write. |

D-61's contract with Layer 4: plan-gen invokes a `resolve_locale(user_id, session_date, required_equipment)` helper that returns `(locale_id, status)`. The helper implementation is owned by the v5 implementation PR; the algorithm is §4.1 above.

---

## 8. Cross-track interactions

| Track | What D-61 hands off | What D-61 consumes |
|---|---|---|
| **D-59** Place lookup + chain detection | — | `locale_profiles.lat` / `.lng` (haversine distance), `manual_entry` flag (§4.1 step 7). |
| **D-60** Shared gym profiles + overrides | — | The per-athlete effective-equipment view (§4.1 step 4); D-60 owns the computation, D-61 consumes the result. |
| **D-58** OAuth-first flow | No direct interaction. Provider integrations don't surface scheduling data D-61 cares about. (Calendar-provider sync — Google Cal, etc. — is a separate future track; D-58 is auth, not calendar.) | No direct interaction. |
| **§K Locale Schedule** (existing v4 spec) | — | The active-locale resolution per session date (§4.1 step 2). §K is not modified by D-61; D-61 reads its existing output. |
| **Layer 4 plan-gen** (future spec) | The `resolve_locale(...)` algorithm + the per-day-window envelope for session-time placement + the `assignment_status` state machine + the JIT swap re-validation contract. | Layer 4 invokes the resolver; D-61 doesn't constrain plan-gen's discipline mix, periodization, or exercise selection. |

---

## 9. What this design doc explicitly does NOT cover

- **Layer 4 plan-gen spec.** D-61 defines the consumer contract for locale resolution and the §G envelope; it does not spec how Layer 4 picks exercises, structures phases, or weights load. That's `Layer4_*_Spec.md`, not yet written.
- **Per-discipline scheduling.** "Swim only Tue/Thu" is not a v5 primitive; the qualifying filter already gates discipline-fit through equipment. v2 expressivity refinement.
- **Session UI implementation.** Card layout, swap modal styling, and the review surface's table shape are frontend-implementation concerns. The design fixes the touch points (card with swap, review surface, stale flag) but not the rendering.
- **Multi-timezone athletes.** An athlete who flies LAX → JFK with §K overlay sees `window_start` as a local time-of-day value at their current locale; v5 stores `TIME` without a TZ. Travel across TZs may misalign windows; not handled in v5. Backlog if it bites in production.
- **Calendar-provider sync.** Importing windows from Google Calendar / iCal is plausible v2 product surface; not v5. D-58 is OAuth for *fitness* providers, not calendar providers.
- **Per-week variance.** "Usually Mon 7am, but every third Mon I have a 6am flight" is real; v5 stores typical-week only. §K self-overlays can flag specific dates as constrained; finer variance is out of scope.
- **Seasonal schedule changes.** "Winter I train indoors, summer I train outdoors at 5am" is real; v5 doesn't model seasonal §G variants. Re-onboarding `daily_availability_windows` is the v5 mechanism (athlete edits per-day on schedule change). Stored seasonal variants are a v2 candidate.
- **The v5 implementation PR.** `daily_availability_windows` migration, `locale_profiles.preferred` migration, §G UI rewrite, the resolver helper, session-card and review-surface frontends — substantial work. Owned by the v5 onboarding implementation PR after all four design tracks settle.

---

## 10. Gut check

**What this design got right.**

- **Per-day windows are honest about how athletes train.** v4 §G's weekly aggregates were the survey-design path of least resistance, not the real signal. Athletes don't have a "weekly training-hours budget" in their heads; they have "I can do Mon morning, Wed evening, Sat long." The design matches that mental model.
- **Andy's drop on max-session-duration was a real simplification.** The original handoff §6.1 Q3 framed the question as "where does the field live"; Andy chose neither location. Tier-3 fields that nobody fills in or reads add survey burden for no signal. The JIT swap surface in decision #6 enforces real per-locale caps in the moment they matter, not through a stored field maintenance burden.
- **Equipment-filter-then-distance is the minimum viable algorithm.** D-60's binary available/not-available makes the qualifying filter clean; distance is the only meaningful sort among qualifying. A four-tier tiebreaker chain would have looked more sophisticated and worked worse — every tier added is a decision athletes can't predict.
- **JIT + optional review respects both kinds of athletes.** Athletes who want to scan ahead get the review view; athletes who run on-the-fly skip it. Forcing review at plan-gen time would have lost the on-the-fly users; never offering review would have lost the planners.
- **No-qualifying-locale fallback is the D-60 "no inferences" stance applied to scheduling.** The system flags the gap and asks the athlete to resolve it, rather than silently substituting bodyweight or inventing equipment. Consistent with the design wave's discipline.

**Risks.**

- **Per-day windows may be too rigid for genuinely variable schedules.** Athletes with shift work, kids with shifting school schedules, or unpredictable travel will set "typical" windows that misrepresent their reality. v5's §K overlays handle date-specific deviation, but the typical-week model degrades for "every week is different." Mitigation: athlete can leave a day at `enabled=TRUE` with a generous window and let §K overlays trim; not ideal, but a workable degradation.
- **`preferred` flag is a single boolean — may not be expressive enough.** The case "I prefer the YMCA for swim, the home gym for everything else" isn't directly expressible (one flag, one locale, applies globally). Workaround: rely on the qualifying filter (swim sessions only qualify against the YMCA, so it wins for swim regardless of flag). Cleaner expression is a v2 refinement.
- **Stale-assignment surfacing may produce noise.** Every locale edit re-runs assignment for 14 days of sessions; if Andy edits a locale frequently, the session cards may show "stale" flags often, training the athlete to ignore them. Mitigation: only re-run when the edit *changes the qualifying status* (equipment override that adds/removes an item the session needs), not on every edit. Implementation refinement; the design doc commits to the contract, not the optimization.
- **Review surface usage may be near-zero.** Optional surfaces in software often go unused. If athletes never look at "Session locations," the design overhead is non-zero (a frontend view to build) for no value. Counterargument: it's cheap to build and serves the audit-needing minority; not building it would push those athletes toward the plan-gen-time bulk-confirm flow, which is the higher-friction option.
- **Long-session day vs. typical-day window interaction is subtle.** Decision #1's window-replacement rule for long-session days ("Saturday's window_duration becomes the long-session max for the long session") is correct but easy to get wrong in implementation. The recovery walk on Saturday still uses the original entered window. Testing this edge case at v5 implementation time is essential.

**What might be missing.**

- **Travel-day default behavior.** When a §K overlay puts the athlete at a hotel locale, do their windows shift to local-time-at-hotel automatically, or do they stay at home-time-of-day and just place sessions there? v5 stores `TIME` without TZ, so the system can't know — it treats the time as local-to-current-locale. Honest but underspecified; a backlog candidate for a "travel scheduling" pattern.
- **Plan-gen feedback on impossible schedules.** If athlete enters 30-min windows every day and the plan needs a 60-min session, plan-gen produces no qualifying time slot. Where does that fail? Layer 4 owns the failure mode, but D-61 should at least surface "your §G envelope is tighter than your goal demands" at plan-gen time. Not specced here; consider when Layer 4 spec lands.
- **Recurring-template `preferred` overrides.** §K K.3 recurrence templates carry `Active Locale`; a recurring Wednesday-evening joint-training overlay can pin a locale that isn't preferred globally. Does the template's Active Locale override the resolver, or does the resolver re-run against the qualifying set with the template's locale as the anchor? The design implies the latter (the template fixes the anchor; the resolver still picks among qualifying within proximity). Worth explicit confirmation in the v5 spec.
- **`assignment_status='unassigned'` rate-limiting.** If an athlete's locale set genuinely doesn't qualify for the plan, every session shows the unassigned-warning UI. Honest but tiresome. UX may benefit from a one-time "your locale set doesn't currently cover this plan; here are the gaps" summary at plan-gen time. Backlog candidate.
- **Interaction with §G Long Session day picker and `daily_availability_windows.enabled`.** Long Session Available's "day" picker must come from the enabled set; if athlete unchecks Saturday from `enabled`, the Long-Session-day-on-Saturday becomes invalid. v5 implementation handles the cross-validation; the design doc doesn't spec the precise UX. Worth a sentence in the spec rewrite.

**Best argument against this design.**

The whole D-61 reshape is over-engineering for a single-user product. Andy could keep v4 §G's weekly aggregates, keep §J.5 fields, and just add a "swap locale" button on the session card — a one-feature add, not a schedule redesign + locale resolution algorithm + UX surface trio. The per-day windows + preferred-flag + JIT-swap + review-surface stack is a lot of moving parts for what could be a single button.

Counter: the v4 §G/§J.5 split misrepresents the data model — time isn't a locale property; equipment isn't an athlete property; locale-per-session isn't a fixed assignment. Carrying the v4 misalignment into v5 means every downstream layer (Layer 4 plan-gen, the session UI, future scheduling features) inherits the misrepresentation. The reshape is paid once now; the misrepresentation would compound. Plus Andy's "push to production as we go" rule favors shipping the right abstraction over an additive button on the wrong one.

Alternative phasing: ship per-day windows in v5 (the highest-leverage piece) but keep `preferred` flag + tap-to-swap as v5.1, leaving plan-gen to use a simple "closest qualifying" without the preferred-set restriction in v5. Reasonable defer if implementation budget is tight; the design as written supports this staging — the resolver algorithm in §4.1 degrades cleanly without step 5.

---

*End of D-61 design doc. Next: D-58 design — OAuth-first onboarding flow, per-field prefill priority across providers, re-onboarding semantics after late provider connect.*
