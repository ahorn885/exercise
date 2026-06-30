# V5 — Conditions Advisory follow-ups: live-conditions CTA surface (#1035) + away-window locale resolution (#1036) — Kickoff Handoff (2026-06-30)

**Branch:** none yet (each follow-up is its own slice → its own branch + PR) · **Issues:** [#1035](https://github.com/ahorn885/exercise/issues/1035) (live-conditions surface, §11.2) / [#1036](https://github.com/ahorn885/exercise/issues/1036) (away-window locale, §11.3), both children of epic #286, follow-ups to #289 (producer) / #964 (consumer) · **Design:** `designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md` §11.2 / §11.3 / §7 / §12.

**Context:** The conditions-advisory arc shipped end-to-end on 2026-06-30 — Slice 1 (#289 producer, the live `upcoming_conditions` signal) + Slice 2 (#964 consumer, the `conditions_advisory` notification). Two **non-blocking** enhancements were deferred at design time (§11) and are now filed as issues. This kickoff scopes both so either can be picked up cold. **Neither blocks anything; pick by priority against the live threads (#884 slice 6c, #971 slice 2).** Do them as **separate slices / separate PRs** — they touch different layers and share no code.

---

## Follow-up A — Live upcoming-conditions surface for the CTA (#1035, design §11.2)

**The gap (design §12 — the weakest UX seam):** the `conditions_advisory` nudge fires "extreme weather coming," but its CTA (`NUDGE_REGISTRY['conditions_advisory'].cta_endpoint = 'plans.list_plans'`) lands on the plan view, which renders **climate normals** (Layer-5B `plan_conditions`), **not** the live forecast that triggered the nudge. Message and surface disagree.

**The fix:** render the live `upcoming_conditions (user_id, forecast_date)` rows — temp_max_c / temp_min_c / precip_prob_pct — somewhere the CTA can land, then re-point `cta_endpoint` at it.

**Mechanical pointers (next session does its own Rule #9 first):**
- **Signal to read:** `upcoming_conditions` table (populated daily by Slice 1). A new repo read (`upcoming_conditions_repo.load_upcoming_for_user(db, user_id)` → in-window rows ordered by date) mirrors the existing `load_*` patterns; pure DB.
- **Where to render — two options (Andy's call, surface in `/plan` before building since it's a UX choice):**
  1. **Fold into the existing plan-view conditions block** beside the normals — `templates/plans/view.html` (the conditions block is around the `similar_past_conditions` / `rec.forecast` render, ~L92–L111). Lowest new-surface cost; keeps everything on the plan view the CTA already targets, so `cta_endpoint` may not even need to change.
  2. **A small standalone "Upcoming conditions" view** (`routes/conditions.py` already exists for the producer cron — add a GET view route there or on the dashboard) + re-point `cta_endpoint` to it.
- **Re-point the CTA:** `routes/nudges.py` `NUDGE_REGISTRY['conditions_advisory']['cta_endpoint']` → the chosen endpoint. Update the design §4 note (which flags this as Open item §11.2) + the `route_locales`-style copy if the label changes.
- **Read-only, no schema, no Neon/layer0 apply** — `upcoming_conditions` is already on disk.

**Test shape:** render test (the surface shows a heat/freeze/rain day from a stubbed `upcoming_conditions` read; empty → graceful "no upcoming extremes" state) + the CTA-endpoint assertion in `tests/test_nudges_staleness.py` updates if `cta_endpoint` changes.

**Recommendation:** option 1 (fold into the plan view) is the leaner first cut — it closes the mismatch with the least new surface and likely needs **no** `cta_endpoint` change. Surface both to Andy in `/plan` (it's a UX-placement decision, not a mechanical one) before building.

## Follow-up B — Away-window locale resolution in the producer (#1036, design §11.3 / §7)

**The gap:** the producer (`layer5/upcoming_conditions.refresh_upcoming_conditions_for_user`) keys each forecast day off the **session's own `locale_id`** (`locale_by_date` = the day's first session carrying a locale, the Layer-5B rule). For an away/travel day, if the plan session carries the **home** locale, the producer fetches the **home** forecast — so the advisory could warn about the wrong place.

**⚠️ Rule #14 — confirm before building (do NOT infer).** First establish whether away-day sessions actually carry the home locale or the travel locale:
- Pull real data: a `neon-query` SELECT of `plan_sessions.locale_id` for an athlete who has an `away` `athlete_event_windows` row covering session dates, compared against `away_locale`.
- **If sessions already carry the travel locale → this is a no-op; close #1036 `not_planned`.** Don't build on the assumption.

**The fix (only if the data shows the gap is real):** fold `athlete_event_windows_repo.resolve_weather_location(db, user_id, on_date)` (away-destination coords win; the #941 fix for exactly this home-vs-away class) into the producer's per-date locale resolution. `resolve_weather_location` returns a bare `"lat,lng"` token (away window → home preferred → `""`), which the producer can feed to `get_upcoming_forecast` directly per away-date, falling back to the session-locale path otherwise.

**Mechanical pointers:**
- `athlete_event_windows_repo.py:132` `resolve_weather_location` (away/home/none cascade + Rule #15 `[trip-weather]` log).
- `layer5/upcoming_conditions.py` `refresh_upcoming_conditions_for_user` — the `locale_by_date` loop (~L76–L99) is where the per-date resolution lives; the producer currently does one forecast call per distinct *locale slug*, so an away path keyed on coords needs care to keep the one-call-per-distinct-location memoization (key by the resolved token, not the slug).
- Producer-side only; no schema, no consumer change (the reconcile reads whatever rows the producer writes).

**Test shape:** producer test — an away-window day resolves to the destination forecast (stub `resolve_weather_location` → destination token), a non-away day keeps the session-locale path, memoization still collapses repeated locations to one fetch.

**Recommendation:** **gate on the data pull.** This is the lower-value of the two (it only matters for athletes with away windows during the 7-day horizon — and only if the locale doesn't already travel). Confirm first; it may close `not_planned`.

---

## Ordering & priority

Both are `priority:low`, non-blocking. **#1035 (the CTA surface) is the higher-value** — it closes a real message/surface mismatch every advisory currently has, and it's pure read/render. **#1036 is gated on a data check** that may zero it out. Neither should preempt the live threads (#884 slice 6c, #971 slice 2) unless Andy reprioritizes.

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. The conditions-advisory Slice 2 closing handoff (`handoffs/V5_Implementation_NotificationTriggers_ConditionsAdvisorySlice2_289_964_2026_06_30_Closing_Handoff_v1.md`) + this kickoff + the design doc
5. `./scripts/verify-handoff.sh` — automated anchor sweep
