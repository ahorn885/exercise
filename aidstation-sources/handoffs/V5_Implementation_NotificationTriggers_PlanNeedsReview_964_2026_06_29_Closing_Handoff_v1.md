# V5 Implementation — Notification Triggers: Plan-Attention Nudge (#964) — Closing Handoff (2026-06-29)

**Branch:** `claude/notification-triggers-staleness-76ptlf` · **PR:** not yet opened (push + bookkeep + wait for Andy's go) · **Issue:** [#964](https://github.com/ahorn885/exercise/issues/964) (type:feature, priority:med, area:notifications) · **Epic:** #259 (notifications subsystem) · **Suite:** full `tests/` **3783 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).
**Context:** Continuation of the #964 thread. The first slice (PR #1006, merged) shipped 3 reminder/staleness triggers + the reconciling cron framework. **Andy chose (AskUserQuestion 2026-06-29) the plan-attention nudge** as the next slice (over race-week-14d / hold-for-#939 / a recurring-mechanism design). This builds the "incomplete plan / plan requiring attention" checklist item.

> **▶ IMMEDIATE NEXT: build the race-week-14d reminder (`race_week_plan_due`).** Andy greenlit building it ahead of #939 (2026-06-29) — see §6 for the full build recipe. It's another reconcile-spec addition riding the existing cron. No schema/DDL in *this* slice → **no Neon/layer0 apply owed** (rides the existing public-schema cron; `account_nudges` + `plan_versions` are live).

---

## 1. What shipped (1 plan-attention trigger)

| nudge_type | Fires when | CTA |
|---|---|---|
| `plan_needs_review` | A **live** plan version (`superseded_at IS NULL AND archived_at IS NULL`) has sat at `generation_status='needs_review'` past an escalation rung | `plans.list_plans` |

**Escalation ladder (Andy 2026-06-29).** The nudge first appears at rung 1, then **re-surfaces** (floats to top + marked unread) at each later rung if the athlete read/dismissed it, then stays until the plan is resolved. Rungs are a module constant in `routes/nudges.py`: `PLAN_REVIEW_RUNGS = ('1 day', '2 days', '7 days')`, measured from when the plan parked (`plan_versions.created_at`). **Andy pivoted to a day-granular ladder so the existing DAILY cron is kept** (an earlier 6h/24h/3d ladder would have forced an hourly cron / `vercel.json` change — not worth it). Tune the cadence by editing `PLAN_REVIEW_RUNGS`; adding a rung is a one-line change (the re-surface OR-clause is built off the tuple).

## 2. Grounding correction (done BEFORE building)

The earlier handoff flagged the plan-attention nudge as "depends on the #215 PlanManagementState derivation (only a spec today)." **That was wrong** and was the first thing checked:

- The live, queryable "plan requiring attention" signal is **`plan_versions.generation_status = 'needs_review'`** — a plan parked at the **Layer 3D HITL review gate** (#213). It already surfaces in its own "Needs review" bucket in the plan list UI (`routes/plans.py:284`), but **nothing prompts the athlete to return to it** — exactly the gap #964 wants filled. No #215 derivation needed.
- **`failed` is deliberately NOT actionable** (`routes/plans.py:244-246`: "Failed generations are intentionally NOT listed — they're a dead end the athlete re-runs, not a plan to act on"). So the nudge fires **only on `needs_review`**, never `failed`. (`plan_failed` already exists as a separate *event* notification type for the error case.)
- **Archived plans excluded** — an athlete who archived a needs_review plan deliberately shelved it; nudging them to review it would be wrong. (The UI's needs_review bucket shows archived ones too, but a proactive nudge should respect the archive action.)

## 3. The mechanism — reuses the #1006 reconcile framework verbatim

No new infrastructure. Added one `{nudge_type, insert, delete, resurface}` entry to `_STALENESS_RECONCILE`, so it **rides the existing `GET /cron/nudges/reconcile`** (`scan_reconcile_staleness`, daily). Because it's the existing cron endpoint, **no `app.py` auth-exempt entry and no `vercel.json` schedule change were needed** (contrast the first slice, which added a new endpoint). The cron loop runs **delete → insert → resurface** per spec, where `resurface` is optional (only `plan_needs_review` defines it); the JSON response gains a `resurfaced` map.

- **INSERT** (first fire) arms the nudge for any user with a live plan parked at the gate past rung 1 (`pv.created_at <= NOW() - INTERVAL '1 day'`; generation parks at the gate shortly after start, so `created_at` is a close proxy for "parked at"), `ON CONFLICT DO NOTHING`.
- **RE-SURFACE** (escalation) re-arms an existing row once a *later* rung (2 days, 7 days) has elapsed since the plan parked AND the row was last surfaced before that rung: `SET dismissed_at = NULL, read_at = NULL, created_at = NOW()`. Re-stamping `created_at` to now is what **bounds it to once per rung** — after firing, `created_at` sits at/after the rung threshold, so the `created_at < park + rung` guard is false on the next run. Anchored to ANY of the user's parked plans via `EXISTS` (avoids the multi-parked-plan `UPDATE...FROM` join ambiguity). The OR-clause over the later rungs is built off `PLAN_REVIEW_RUNGS[1:]`.
- **DELETE** clears once no live (`needs_review` + non-superseded + non-archived) plan remains for the user — resolved, superseded, archived, or deleted — letting the nudge re-fire on a *later* parked plan. The rung clauses are intentionally omitted from the DELETE (age only ever becomes *more* true, so it plays no part in clearing). DELETE runs before RE-SURFACE, so a row whose plan just cleared is removed, not re-armed.

**Cron-gap degradation:** if the daily cron misses runs and a plan is already past several rungs when first seen, the INSERT stamps `created_at = NOW()` (past all elapsed rungs) so the athlete gets one nudge rather than a backlog of re-surfaces — acceptable.

## 4. Files touched

- **`notification_prefs.py`** — registered `plan_needs_review` in `NOTIFICATION_TYPES`. Channels **`['in_app', 'push']`**, defaults in_app/push True, **`category: 'warning'`** (it blocks a plan from completing, unlike the passive `info` staleness types). **Email non-applicable** (same posture as the staleness slice — no nudge→email path).
- **`routes/nudges.py`** — (a) `PLAN_REVIEW_RUNGS = ('1 day', '2 days', '7 days')` + the derived `_PLAN_REVIEW_RESURFACE_OR` clause; (b) a `NUDGE_REGISTRY['plan_needs_review']` entry → CTA `plans.list_plans`, `notification_type` self-link, `category='warning'`; (c) the `_STALENESS_RECONCILE` spec entry (insert/delete/**resurface**); (d) the cron loop runs the optional `resurface` per spec and returns a `resurfaced` map.
- **`tests/test_nudges_staleness.py`** — added `RECONCILE_TYPES` (the 4 cron types), `TestPlanNeedsReviewWiring` (registry entry shape + the `warning` category + in_app/push/email-non-applicable pref registration), `test_plan_needs_review_spec_targets_live_parked_plans` (all three statements share the live-parked predicate; rung-1 arms the insert, delete is age-agnostic), and `test_plan_needs_review_resurface_escalates_on_later_rungs` (re-surface clears dismissal/unread + re-stamps `created_at`; driven by the later rungs, not rung 1). Updated `test_spec_covers_all_staleness_types` (full `RECONCILE_TYPES` set) and the cron-route test (delete→insert→resurface order + the `resurfaced` count).

**No template change** — `warning` is already a handled category in both `templates/_account_nudges.html` (`alert-warning`) and `templates/nudges/feed.html` (the `warn` chip branch).

## 5. Deferred (still OPEN on #964 — 5 triggers)

- **Recurring time-of-day reminders** — supplement AM/PM, next-day's workouts, the literal daily log ping. Recurring scheduled *sends*, not one-shot condition nudges; need a **recurring-schedule mechanism the current model doesn't have**. Bigger slice (new infra; probably its own design doc).
- **Conditions advisory** (rain / freezing / >100°) — overlaps **#289** (Layer-5 conditions advisor).
- **Race-week-plan reminder (14d out)** / **race-day-plan reminder (7d out)** / **share-with-crew (2–3d before)** — depend on **#939**. **Buildability re-checked this session:** only the **14d race-week** reminder is buildable today — `race_events` (DATE `event_date`, `is_target_event`) + `race_week_briefs` both exist, so the trigger is "target race 14d out, no brief yet," cleared on brief-gen or race-pass, a pure reconcile-spec addition. **`race_day_plan_due` (7d) is NOT buildable** — there is no race-day-plan artifact or generator yet (only "future race-day plan" placeholder references in `layer5/`); nudging to generate something that doesn't exist is a dead CTA. **`share_with_crew` is NOT buildable** — needs #939's crew-sharing feature.

## 6. NEXT — race-week-14d reminder (DECIDED — build it next)

**The next session continues the #964 thread by building the race-week-14d reminder.** Andy greenlit building it ahead of the #939 epic (2026-06-29). This is the immediate next step, not an open question.

1. **Race-week-14d reminder (`race_week_plan_due`) — NEXT:** another clean reconcile-pattern addition reusing this slice's framework. Build:
   - a `notification_prefs` type `race_week_plan_due` (channels `['in_app', 'push']`, email non-applicable — same posture);
   - a `NUDGE_REGISTRY['race_week_plan_due']` entry → CTA the race-week brief surface (`routes/race_week_brief.py` — confirm the endpoint name at build time);
   - a `_STALENESS_RECONCILE` `{insert, delete}` spec keyed on `race_events` (the athlete's `is_target_event` race, `event_date` within 14 days of `NOW()` and still future) **AND** no `race_week_briefs` row yet for that athlete's current plan version. **DELETE** clears once the brief is generated or the race passes.
   - It **rides the existing `/cron/nudges/reconcile`** — no new cron endpoint, so no `app.py`/`vercel.json` change. A simple one-shot fire (no escalation ladder) is the right starting shape; revisit if Andy wants re-surfacing.
   - **Skip `race_day_plan_due` + `share_with_crew`** — genuinely blocked on #939 (no race-day-plan artifact exists; no crew-sharing), see §5.
   - Grounding to confirm first: the exact `race_week_briefs` ↔ plan-version key (`race_week_brief_repo.py` upserts on `plan_version_id`), how to resolve the athlete's "current" plan version, and the race-week-brief CTA endpoint name.
2. *(Later)* **Recurring time-of-day mechanism** — design a recurring-send scheduler (supplements AM/PM, next-day workouts, literal daily log ping). Larger; new infra; its own design doc.
3. *(Later)* **Conditions advisory** → coordinate with / fold into **#289**.

The reconcile framework stays reusable — a new condition nudge is: a notification type, a `NUDGE_REGISTRY` entry (with `notification_type`), and an `{insert, delete}` spec appended to `_STALENESS_RECONCILE`. Only add an `app.py` auth-exempt entry if you introduce a *new* cron endpoint (the race-week reminder can ride the existing `/cron/nudges/reconcile`).

## 7. Verification

- Full suite **3783 passed / 30 skipped** locally (deps installed ad-hoc in-container: `pip install -r requirements.txt pytest Flask-WTF`). Only the 3 pre-existing Layer3B `evidence_basis` warnings (#217).
- **No Neon/layer0 apply owed** (rides the existing public-schema cron; `account_nudges` + `plan_versions` tables are live).
- **3 substantive files** (`notification_prefs.py`, `routes/nudges.py`, `tests/test_nudges_staleness.py`) — under the 5-file ceiling.

### §8 anchor table (Rule #10 — next session's Rule #9 input)

| File | Anchor string | Check |
|---|---|---|
| `routes/nudges.py` | `PLAN_REVIEW_RUNGS = ('1 day', '2 days', '7 days')` | grep |
| `routes/nudges.py` | `'resurface':` in the `plan_needs_review` spec | grep |
| `routes/nudges.py` | `'plan_needs_review': {` in `NUDGE_REGISTRY` | grep |
| `notification_prefs.py` | `'key': 'plan_needs_review'` | grep |
| `tests/test_nudges_staleness.py` | `test_plan_needs_review_resurface_escalates_on_later_rungs` | grep |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep
