# V5 Implementation — Notification Triggers: Race-Week-14d Reminder (#964) — Closing Handoff (2026-06-29)

**Branch:** `claude/notification-triggers-impl-sutrmp` · **PR:** not yet opened (push + bookkeep + wait for Andy's go) · **Issue:** [#964](https://github.com/ahorn885/exercise/issues/964) (type:feature, priority:med, area:notifications) · **Epic:** #259 (notifications subsystem) · **Suite:** full `tests/` **3797 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).
**Context:** Continuation of the #964 thread. Predecessor slice (PR #1018, merged) shipped `plan_needs_review` + the escalating re-surface ladder. **This session built the decided next slice — the race-week-14d reminder (`race_week_plan_due`)** — Andy greenlit it ahead of the #939 epic (2026-06-29; predecessor handoff §6). Another reconcile-spec addition riding the existing cron. **No schema/DDL → no Neon/layer0 apply owed** (`race_events` + `race_week_briefs` + `plan_versions` all live).

---

## 1. What shipped (1 race-week reminder trigger)

| nudge_type | Fires when | CTA |
|---|---|---|
| `race_week_plan_due` | The athlete's **target** race (`is_target_event = TRUE`) has `event_date` **inside the 14-day window** (`>= CURRENT_DATE` and `<= CURRENT_DATE + 14`) AND they have an **active plan version** (`load_active_plan_version_id` semantics) with **no `race_week_briefs` row yet** | `plans.list_plans` |

**One-shot fire — no escalation ladder** (predecessor handoff §6 starting shape). Revisit re-surfacing if Andy wants it.

## 2. Grounding confirmed before building

- **`race_events` schema** (`init_db.py:1523`): `event_date DATE NOT NULL`, `is_target_event BOOLEAN`, partial UNIQUE index `race_events_user_target_uidx` enforces **at most one target race per athlete** → the insert's `SELECT … FROM race_events` yields ≤1 row/user, no `DISTINCT` needed. `event_date` is a **real DATE column**, so the spec uses plain date arithmetic (`CURRENT_DATE + 14`) — NOT the `TO_CHAR(NOW() - INTERVAL 'Nd', 'YYYY-MM-DD')` ISO-text cutoff the log/body/injury specs use (those columns are TEXT).
- **`race_week_briefs` ↔ plan-version key** (`race_week_brief_repo.py`): one row per `plan_version_id` (UNIQUE upsert). So "no brief yet" must be checked against a **specific** plan version.
- **The "current" plan version** = `load_active_plan_version_id` (`plan_sessions_repo.py:571`): `generation_status = 'ready' AND archived_at IS NULL AND completed_at IS NULL`, **most-recent wins** (`ORDER BY created_at DESC, id DESC LIMIT 1`). This is the exact version `orchestrate_race_week_brief` attaches its Taper overrides to, so the brief-absent check keys off it — captured in the reused `_ACTIVE_PLAN_NO_BRIEF` SQL fragment.
- **CTA correction (deviation from predecessor §6's suggestion).** The handoff suggested pointing the CTA at a `routes/race_week_brief.py` endpoint. **Neither works as a zero-arg GET CTA** (`url_for(n.cta_endpoint)` with no args, `templates/_account_nudges.html:19`): `race_week_brief.view_brief` **404s until a brief exists** — exactly the nudge condition — and `race_week_brief.generate_brief` is **POST-only**. There is no zero-arg route to the v2 active plan view either (`plan_create.view_plan` needs a `plan_version_id`). So the CTA is **`plans.list_plans`** (same as `plan_needs_review`): the plan list surfaces the active plan (`routes/plans.py:247`), one click from the **[Generate race-week brief]** button on the plan view (`templates/plan_create/view.html:23`, shown when `days_to_event <= 14`).

## 3. The mechanism — reuses the reconcile framework verbatim

No new infrastructure. Added one `{nudge_type, insert, delete}` entry to `_STALENESS_RECONCILE`, so it **rides the existing `GET /cron/nudges/reconcile`** (`scan_reconcile_staleness`, daily). No `app.py` auth-exempt entry and no `vercel.json` schedule change (the existing cron endpoint). No `resurface` key (one-shot), so the cron loop's optional re-surface step skips it.

- **INSERT** arms the nudge for the target-race-in-window + active-plan-no-brief population, `ON CONFLICT DO NOTHING`.
- **DELETE** clears once the athlete is **no longer eligible** — brief generated, race passed (`event_date < CURRENT_DATE`), target race removed/changed, or the active plan went away — by mirroring the insert eligibility in a `NOT EXISTS` (same shape as `plan_needs_review`'s delete).

**`_ACTIVE_PLAN_NO_BRIEF`** (module-level SQL fragment, reused verbatim by insert + delete): `EXISTS` is true iff the user (`re.user_id`) has an active plan version (scalar subquery `ORDER BY created_at DESC, id DESC LIMIT 1`) with **no** `race_week_briefs` row. No active plan → the scalar subquery is NULL → `pv.id = NULL` → outer `EXISTS` false → **no fire** (keeps the CTA actionable).

## 4. Files touched

- **`notification_prefs.py`** — registered `race_week_plan_due` in `NOTIFICATION_TYPES`. Channels **`['in_app', 'push']`**, defaults in_app/push True, **`category: 'info'`** (a reminder to act, not a blocker — unlike the `warning` `plan_needs_review`). **Email non-applicable** (same posture — no nudge→email path).
- **`routes/nudges.py`** — (a) `RACE_WEEK_DUE_DAYS = 14` constant; (b) the `_ACTIVE_PLAN_NO_BRIEF` SQL fragment; (c) a `NUDGE_REGISTRY['race_week_plan_due']` entry → CTA `plans.list_plans`, `notification_type` self-link, `category='info'`; (d) the `_STALENESS_RECONCILE` `{insert, delete}` spec entry.
- **`tests/test_nudges_staleness.py`** — added `TestRaceWeekPlanDueWiring` (registry entry shape + `info` category + in_app/push/email-non-applicable pref registration) and `test_race_week_plan_due_spec_targets_target_race_and_active_plan` (both statements share the target-race + 14-day-window + active-plan-no-brief eligibility; no `resurface` key). Extended `RECONCILE_TYPES` (now the 5 cron types) — which auto-extends `test_spec_covers_all_staleness_types`, `test_each_spec_has_insert_and_delete` (parametrized), and the cron-route order test (the new type has no resurface → DELETE+INSERT only).

**No template change** — `info` is already a handled category. **No logging added** — the change is a new spec entry in the shared data-driven reconcile loop, whose decision record is the cron's `{inserted, cleared}` JSON response (consistent with the predecessor staleness slice; adding per-type `print()` would be a non-surgical change to shared infra).

## 5. Deferred (still OPEN on #964 — 4 triggers)

- **Recurring time-of-day reminders** — supplement AM/PM, next-day's workouts, the literal daily log ping. Recurring scheduled *sends*, not one-shot condition nudges; need a **recurring-schedule mechanism the current model doesn't have**. Bigger slice (new infra; probably its own design doc).
- **Conditions advisory** (rain / freezing / >100°) — overlaps **#289** (Layer-5 conditions advisor).
- **Race-day-plan reminder (7d out)** / **share-with-crew (2–3d before)** — depend on **#939** and **remain not-buildable** (re-confirmed predecessor §5): `race_day_plan_due` has **no race-day-plan artifact or generator** yet (only "future race-day plan" placeholders in `layer5/`) → a dead CTA; `share_with_crew` needs #939's crew-sharing feature.

## 6. NEXT

The reconcile framework remains the reusable spine — a new **condition** nudge is still: a notification type, a `NUDGE_REGISTRY` entry (with `notification_type`), and an `{insert, delete}` spec appended to `_STALENESS_RECONCILE` (add `app.py` auth-exempt + `vercel.json` only for a *new* cron endpoint). With `race_week_plan_due` shipped, the **remaining buildable #964 work is blocked on new mechanisms / other epics** (§5). Options for the next slice, in rough order:

1. **Recurring time-of-day mechanism** — design a recurring-send scheduler (supplements AM/PM, next-day workouts, literal daily log ping). Larger; new infra; its own design doc. The biggest remaining #964 chunk.
2. **Conditions advisory** → coordinate with / fold into **#289**.
3. *(Blocked on #939)* race-day-plan (7d) + share-with-crew — do **not** start until #939 lands the race-day-plan artifact + crew-sharing.

Alternatively **return to the standing #884 arc** (slice 5 — away overlay), the main thread before the #964 detour. **Open question for Andy:** design the recurring-send mechanism next, or step off #964 back to #884? (The remaining #964 triggers are all either new-infra or #939/#289-blocked — there's no more "clean reconcile-spec addition" low-hanging fruit.)

## 7. Verification

- Full suite **3797 passed / 30 skipped** locally (deps installed ad-hoc in-container: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest Flask-WTF`). Only the 3 pre-existing Layer3B `evidence_basis` warnings (#217).
- Ruff clean on the 3 changed files.
- Rendered the new insert/delete SQL — valid PostgreSQL; the `re` alias correlates correctly in both (insert `FROM race_events re`; delete's inner `FROM race_events re WHERE re.user_id = an.user_id`); `date + integer → date`.
- **No Neon/layer0 apply owed** (public-schema cron; `race_events` + `race_week_briefs` + `plan_versions` tables are live).
- **3 substantive files** (`notification_prefs.py`, `routes/nudges.py`, `tests/test_nudges_staleness.py`) — under the 5-file ceiling.

### §8 anchor table (Rule #10 — next session's Rule #9 input)

| File | Anchor string | Check |
|---|---|---|
| `routes/nudges.py` | `RACE_WEEK_DUE_DAYS = 14` | grep |
| `routes/nudges.py` | `_ACTIVE_PLAN_NO_BRIEF` | grep |
| `routes/nudges.py` | `'race_week_plan_due': {` in `NUDGE_REGISTRY` | grep |
| `routes/nudges.py` | `'nudge_type': 'race_week_plan_due'` in `_STALENESS_RECONCILE` | grep |
| `notification_prefs.py` | `'key': 'race_week_plan_due'` | grep |
| `tests/test_nudges_staleness.py` | `test_race_week_plan_due_spec_targets_target_race_and_active_plan` | grep |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep
