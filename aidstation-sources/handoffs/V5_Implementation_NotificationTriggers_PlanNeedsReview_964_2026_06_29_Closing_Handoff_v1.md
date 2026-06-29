# V5 Implementation — Notification Triggers: Plan-Attention Nudge (#964) — Closing Handoff (2026-06-29)

**Branch:** `claude/notification-triggers-staleness-76ptlf` · **PR:** not yet opened (push + bookkeep + wait for Andy's go) · **Issue:** [#964](https://github.com/ahorn885/exercise/issues/964) (type:feature, priority:med, area:notifications) · **Epic:** #259 (notifications subsystem) · **Suite:** full `tests/` **3782 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).
**Context:** Continuation of the #964 thread. The first slice (PR #1006, merged) shipped 3 reminder/staleness triggers + the reconciling cron framework. **Andy chose (AskUserQuestion 2026-06-29) the plan-attention nudge** as the next slice (over race-week-14d / hold-for-#939 / a recurring-mechanism design). This builds the "incomplete plan / plan requiring attention" checklist item.

> **▶ IMMEDIATE NEXT: STAY ON THE #964 THREAD.** The race-week-14d reminder is the next clean reconcile-pattern addition *if Andy greenlights building ahead of #939* (see §5). No schema/DDL in this slice → **no Neon/layer0 apply owed** (rides the existing public-schema cron; `account_nudges` + `plan_versions` are live).

---

## 1. What shipped (1 plan-attention trigger)

| nudge_type | Fires when | CTA |
|---|---|---|
| `plan_needs_review` | A **live** plan version (`superseded_at IS NULL AND archived_at IS NULL`) has sat at `generation_status='needs_review'` for ≥3 days | `plans.list_plans` |

Threshold is a module constant in `routes/nudges.py` (`PLAN_REVIEW_STALE_DAYS = 3`) — tune there.

## 2. Grounding correction (done BEFORE building)

The earlier handoff flagged the plan-attention nudge as "depends on the #215 PlanManagementState derivation (only a spec today)." **That was wrong** and was the first thing checked:

- The live, queryable "plan requiring attention" signal is **`plan_versions.generation_status = 'needs_review'`** — a plan parked at the **Layer 3D HITL review gate** (#213). It already surfaces in its own "Needs review" bucket in the plan list UI (`routes/plans.py:284`), but **nothing prompts the athlete to return to it** — exactly the gap #964 wants filled. No #215 derivation needed.
- **`failed` is deliberately NOT actionable** (`routes/plans.py:244-246`: "Failed generations are intentionally NOT listed — they're a dead end the athlete re-runs, not a plan to act on"). So the nudge fires **only on `needs_review`**, never `failed`. (`plan_failed` already exists as a separate *event* notification type for the error case.)
- **Archived plans excluded** — an athlete who archived a needs_review plan deliberately shelved it; nudging them to review it would be wrong. (The UI's needs_review bucket shows archived ones too, but a proactive nudge should respect the archive action.)

## 3. The mechanism — reuses the #1006 reconcile framework verbatim

No new infrastructure. Added one `{nudge_type, insert, delete}` entry to `_STALENESS_RECONCILE`, so it **rides the existing `GET /cron/nudges/reconcile`** (`scan_reconcile_staleness`, daily). Because it's the existing cron endpoint, **no `app.py` auth-exempt entry and no `vercel.json` schedule were needed** (contrast the first slice, which added a new endpoint).

- **INSERT** arms the nudge for any user with a live plan parked at the gate ≥`PLAN_REVIEW_STALE_DAYS` days (grace window keyed off `pv.created_at` — generation parks at the gate shortly after start, so `created_at` is a close proxy for "parked at"), `ON CONFLICT DO NOTHING`.
- **DELETE** clears once no live (`needs_review` + non-superseded + non-archived) plan remains for the user — resolved, superseded, archived, or deleted — letting the nudge re-fire on a *later* parked plan. The grace-window clause is intentionally omitted from the DELETE (it only ever becomes *more* true with age, so it plays no part in clearing).

## 4. Files touched

- **`notification_prefs.py`** — registered `plan_needs_review` in `NOTIFICATION_TYPES`. Channels **`['in_app', 'push']`**, defaults in_app/push True, **`category: 'warning'`** (it blocks a plan from completing, unlike the passive `info` staleness types). **Email non-applicable** (same posture as the staleness slice — no nudge→email path).
- **`routes/nudges.py`** — (a) `PLAN_REVIEW_STALE_DAYS = 3` constant; (b) a `NUDGE_REGISTRY['plan_needs_review']` entry → CTA `plans.list_plans`, `notification_type` self-link, `category='warning'`; (c) the `_STALENESS_RECONCILE` spec entry (insert/delete above).
- **`tests/test_nudges_staleness.py`** — added `RECONCILE_TYPES` (the 4 cron types), `TestPlanNeedsReviewWiring` (registry entry shape + the `warning` category + in_app/push/email-non-applicable pref registration), and `test_plan_needs_review_spec_targets_live_parked_plans` (both statements share the live-parked predicate; grace window arms insert but never clears delete). Updated `test_spec_covers_all_staleness_types` to assert the full `RECONCILE_TYPES` set.

**No template change** — `warning` is already a handled category in both `templates/_account_nudges.html` (`alert-warning`) and `templates/nudges/feed.html` (the `warn` chip branch).

## 5. Deferred (still OPEN on #964 — 5 triggers)

- **Recurring time-of-day reminders** — supplement AM/PM, next-day's workouts, the literal daily log ping. Recurring scheduled *sends*, not one-shot condition nudges; need a **recurring-schedule mechanism the current model doesn't have**. Bigger slice (new infra; probably its own design doc).
- **Conditions advisory** (rain / freezing / >100°) — overlaps **#289** (Layer-5 conditions advisor).
- **Race-week-plan reminder (14d out)** / **race-day-plan reminder (7d out)** / **share-with-crew (2–3d before)** — depend on **#939**. **Buildability re-checked this session:** only the **14d race-week** reminder is buildable today — `race_events` (DATE `event_date`, `is_target_event`) + `race_week_briefs` both exist, so the trigger is "target race 14d out, no brief yet," cleared on brief-gen or race-pass, a pure reconcile-spec addition. **`race_day_plan_due` (7d) is NOT buildable** — there is no race-day-plan artifact or generator yet (only "future race-day plan" placeholder references in `layer5/`); nudging to generate something that doesn't exist is a dead CTA. **`share_with_crew` is NOT buildable** — needs #939's crew-sharing feature.

## 6. NEXT — keep working the #964 thread

1. **Race-week-14d reminder (`race_week_plan_due`):** the next clean reconcile-pattern addition — register a notification type + a `NUDGE_REGISTRY` entry + a `_STALENESS_RECONCILE` `{insert, delete}` spec keyed on `race_events` (target race, `event_date` within 14d) + a `race_week_briefs` non-existence check. **Decision needed:** build now vs. hold for the #939 race-planning epic. (Skip `race_day_plan_due` + `share_with_crew` — genuinely blocked, see §5.)
2. **Recurring time-of-day mechanism** — design a recurring-send scheduler (supplements AM/PM, next-day workouts, literal daily log ping). Larger; new infra; its own design doc.
3. **Conditions advisory** → coordinate with / fold into **#289**.

The reconcile framework stays reusable — a new condition nudge is: a notification type, a `NUDGE_REGISTRY` entry (with `notification_type`), and an `{insert, delete}` spec appended to `_STALENESS_RECONCILE`. Only add an `app.py` auth-exempt entry if you introduce a *new* cron endpoint (the race-week reminder can ride the existing `/cron/nudges/reconcile`).

## 7. Verification

- Full suite **3782 passed / 30 skipped** locally (deps installed ad-hoc in-container: `pip install -r requirements.txt pytest Flask-WTF`). Only the 3 pre-existing Layer3B `evidence_basis` warnings (#217).
- **No Neon/layer0 apply owed** (rides the existing public-schema cron; `account_nudges` + `plan_versions` tables are live).
- **3 substantive files** (`notification_prefs.py`, `routes/nudges.py`, `tests/test_nudges_staleness.py`) — under the 5-file ceiling.

### §8 anchor table (Rule #10 — next session's Rule #9 input)

| File | Anchor string | Check |
|---|---|---|
| `routes/nudges.py` | `PLAN_REVIEW_STALE_DAYS = 3` | grep |
| `routes/nudges.py` | `'plan_needs_review': {` in `NUDGE_REGISTRY` | grep |
| `routes/nudges.py` | `'nudge_type': 'plan_needs_review'` in `_STALENESS_RECONCILE` | grep |
| `notification_prefs.py` | `'key': 'plan_needs_review'` | grep |
| `tests/test_nudges_staleness.py` | `class TestPlanNeedsReviewWiring` | grep |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep
