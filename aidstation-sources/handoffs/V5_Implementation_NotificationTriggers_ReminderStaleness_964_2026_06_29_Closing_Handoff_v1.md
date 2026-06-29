# V5 Implementation — Notification Triggers: Reminder/Staleness Slice (#964) — Closing Handoff (2026-06-29)

**Branch:** `claude/issue-964-5az3es` · **PR:** [#1006](https://github.com/ahorn885/exercise/pull/1006) (merged) · **Issue:** [#964](https://github.com/ahorn885/exercise/issues/964) (type:feature, priority:med, area:notifications) · **Epic:** #259 (notifications subsystem) · **Suite:** full `tests/` **3728 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217); CI + Vercel green on the PR head.
**Context:** Andy's notifications-expansion feedback checklist (2026-06-28). #964 lists **9** requested notification triggers on top of the now-functional notifications page + §22 preference matrix (sibling infra #963/#259/#260, already shipped). This is the **first slice** — the three triggers that fit the existing one-shot `account_nudges` model cleanly and depend on no other epic.

> **▶ IMMEDIATE NEXT: STAY ON THE #964 THREAD — build the next slice (see §6).** The standing **#884** arc (slice 4.3) remains the main thread to return to once #964's buildable triggers are exhausted or Andy redirects. No schema/DDL in this slice → **no Neon/layer0 apply owed** (the cron is public-schema; `account_nudges` is live).

---

## 1. What shipped (3 reminder/staleness triggers)

| nudge_type | Fires when | CTA |
|---|---|---|
| `log_reminder` | No workout (training_log **or** cardio_log) logged in ~5 days, account past onboarding (~7d) | `log.index` |
| `body_metric_stale` | Athlete has logged a body metric before but none in ~30 days | `body.list_entries` |
| `injury_review` | An `injury_log` row still `status='Active'` with `start_date` older than ~30 days | `injuries.list_entries` |

Thresholds are module constants in `routes/nudges.py` (`LOG_STALE_DAYS`, `LOG_MIN_ACCOUNT_DAYS`, `BODY_STALE_DAYS`, `BODY_MIN_ACCOUNT_DAYS`, `INJURY_REVIEW_DAYS`) — tune there.

## 2. The key design decision — a RECONCILING cron (insert-while-true, delete-on-clear)

`account_nudges` has `UNIQUE (user_id, nudge_type)` → a plain insert is **one-shot-forever** (correct for `connect_provider_14d`, wrong for a *recurring* condition: once dismissed it could never fire again). New endpoint **`GET /cron/nudges/reconcile`** (`scan_reconcile_staleness`, daily) reconciles each type:

1. **DELETE** rows whose condition has lifted (athlete logged / refreshed / resolved). Removing the row — dismissed or not — lets the same nudge re-fire on a later recurrence.
2. **INSERT** one row per newly-eligible athlete (condition holds, no existing row), `ON CONFLICT DO NOTHING` for overlap-idempotency.

Each type's DELETE is the logical complement of its INSERT's activity-condition, so insert/delete are mutually exclusive for a given user at a given time. The spec lives in `_STALENESS_RECONCILE` (a list of `{nudge_type, insert, delete}` SQL). PG-only (`TO_CHAR`/`INTERVAL`/`ON CONFLICT`); ISO-text `date`/`start_date` columns compare lexicographically against a `TO_CHAR(NOW() - INTERVAL 'N days', 'YYYY-MM-DD')` cutoff.

## 3. Files touched

- **`notification_prefs.py`** — registered `log_reminder` / `body_metric_stale` / `injury_review` in `NOTIFICATION_TYPES`. Channels **`['in_app', 'push']`**; defaults in_app/push True. **Email deliberately NOT applicable** — there is no nudge→email delivery path, and `email` is `available: True`, so listing it would render an enabled toggle that silently never delivers. Push follows the project "store now, deliver when the app ships" posture.
- **`routes/nudges.py`** — (a) three `NUDGE_REGISTRY` entries, each with a **`notification_type`** link; (b) a new `notification_type` key on the existing connect/onboarding entries (→ `account_reminders`); (c) `_INTERNAL_REGISTRY_KEYS = ('display_delay_days', 'notification_type')` stripped from the per-row overlay; (d) **`get_active_nudges` now gates in-app display** on `disabled_in_app_types(db, uid)` (fail-open on a store fault) — this also **wires the previously-inert `account_reminders` toggle** for the existing nudges; (e) the `_STALENESS_RECONCILE` spec + `scan_reconcile_staleness` route.
- **`vercel.json`** — `{ "path": "/cron/nudges/reconcile", "schedule": "0 15 * * *" }` (an hour after the connect-provider scan).
- **`app.py`** — added `'nudges.scan_reconcile_staleness'` to `_AUTH_EXEMPT_ENDPOINTS` (token-gated cron, like `scan_connect_provider_14d`; without this the global session wall 302-redirects the cron). **Watch-out for the next slice:** any new cron endpoint must be added here too.
- **`tests/test_nudges_staleness.py`** (new) — registry wiring, preference gating (incl. fail-open + no `notification_type` leak), reconcile-spec shape, and the cron route (401 without token; delete-then-insert per type with per-type counts).

## 4. Notes / decisions

1. **"Daily reminder to log exercises" → implemented as logging *staleness*** (no log in N days), not a literal time-of-day daily ping. The in-app feed/banner is a passive surface; a true daily ping needs the recurring time-of-day mechanism (deferred, §6). This is the deliverable form for the in-app channel we actually ship today. *(Confirm with Andy if he wants the literal daily cadence — that's the recurring-mechanism slice.)*
2. **Preference gating happens at READ time** (`get_active_nudges`), not insert time — mirrors the plan-notification badge gate (`get_unseen_plan_notifications` → `disabled_in_app_types`). The cron stays preference-agnostic; toggling a type off mutes it without disturbing reconciled rows.
3. **`body_metric_stale` requires a prior body-metric row** (`EXISTS … body_metrics`) — it's a "refresh", not a "start tracking", nudge. `log_reminder` deliberately has **no** prior-log requirement (it drives the habit broadly; a connected provider's auto-imported `cardio_log` rows keep synced athletes out of eligibility naturally).
4. **`injury_review`** keys on `start_date` (no `updated_at` on `injury_log`); clears when status flips off `'Active'` or the row is removed.

## 5. Deferred (still OPEN on #964 — the other 6 triggers)

- **Recurring time-of-day reminders** — **supplement** AM/PM, **next-day's-workouts** (and the literal daily log ping, see §4.1). These are recurring scheduled *sends*, not one-shot condition nudges; they need a **recurring-schedule mechanism the current model doesn't have**. Bigger slice (new infra).
- **Conditions advisory** (rain / freezing / >100°) — overlaps **#289** (Layer-5 conditions advisor); `weather_client.py` exists but the advisory logic is that epic's.
- **Race-week-plan reminder (14d out)** / **race-day-plan reminder (7d out)** / **share-with-crew (2–3d before)** — depend on the **#939** race-planning expansion epic's features existing. Race dates ARE available now (`race_events.event_date`, `is_target_event`; `race_week_brief_repo.py` exists), so the 14d/7d reminders are arguably buildable; **share-with-crew** needs the crew-sharing feature from #939. **Open scope question for Andy** (§6).

## 6. NEXT — keep working the #964 thread

Open the scope question with Andy, then build the next buildable slice:

1. **Race reminders (recommended next):** `race_week_plan_due` (target race `event_date` 14d out, no race-week brief yet) + `race_day_plan_due` (7d out). Reuse the **exact reconcile pattern** here — add `_STALENESS_RECONCILE`-style specs keyed on `race_events` + the brief/plan existence checks, register two notification types, two `NUDGE_REGISTRY` entries. Clears when the brief/plan is generated or the race passes. **Decision needed:** build now vs. hold for the #939 epic (the underlying race-week brief generation already exists; race-day plan may not).
2. **Recurring time-of-day mechanism** (supplements AM/PM, next-day workouts, literal daily log ping): design a recurring-send scheduler. Larger; introduces new infra and a bigger review surface. Probably its own design doc.
3. **Conditions advisory** → coordinate with / fold into **#289**.

The reconcile framework (`_STALENESS_RECONCILE` + `scan_reconcile_staleness`) is **reusable** — adding a condition nudge is: a notification type, a NUDGE_REGISTRY entry (with `notification_type`), and an `{insert, delete}` spec. Remember the **`app.py` auth-exempt** entry only if you add a *new* cron endpoint (the race reminders can ride the existing `/cron/nudges/reconcile` by appending to `_STALENESS_RECONCILE`).

## 7. Verification

- Full suite **3728 passed / 30 skipped** locally (deps installed ad-hoc in-container: `Flask Flask-WTF -r requirements.txt pytest`, blinker pinned `--ignore-installed`). CI green on PR head: Python unit suite ✅, JS harness ✅, Layer 0 gate ✅, Vercel ✅, Real-LLM smoke skipped (no key — expected).
- **No Neon/layer0 apply owed** (cron is public-schema code; `account_nudges` table is live since the #259/#260 work).
- PR-activity subscription armed on #1006 + an hourly self-check (CronCreate `8814cff9`, session-only, 7-day auto-expire) to confirm post-merge state; stop on merge/close.
