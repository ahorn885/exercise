# V5 Implementation — Notification Triggers: Recurring-Send Mechanism, Slice 1 (storage + capture) (#964) — Closing Handoff (2026-06-29)

**Branch:** `claude/notification-triggers-race-week-tcsny1` · **PR:** not yet opened (push + bookkeep + wait for Andy's go) · **Issue:** [#964](https://github.com/ahorn885/exercise/issues/964) (type:feature, priority:med, area:notifications) · **Epic:** #259 · **Design:** `designs/Notifications_RecurringSchedule_964_Design_v1.md` · **Suite:** full `tests/` **3835 passed / 30 skipped** (+38; the 3 Layer3B `evidence_basis` warnings pre-exist, #217).
**Context:** Continuation of the #964 thread. Predecessor slice (race-week-14d `race_week_plan_due`, PR #1020, merged) closed the last clean reconcile-spec trigger. This session starts the **recurring time-of-day reminder mechanism** — the biggest remaining #964 chunk and the one the predecessor handoff §6 flagged as a **design slice (Stop-and-ask Trigger #5)** needing options-to-Andy before code. **Andy chose the full build** (schedule store + hourly cron + in-app delivery now) over capture-now/deliver-later. Build is ~8 files → **split into 2 within-ceiling slices, both landing this arc**; this session shipped **Slice 1 (storage + capture)**.

---

## 1. The decision (Stop-and-ask Trigger #5)

The recurring-send family — **supplement AM/PM**, **next-day's-workouts preview**, **opt-in daily-log ping** — fires on a **clock**, unlike every #964 trigger so far (one-shot *condition* nudges reconciled in/out of `account_nudges`). I surfaced the load-bearing problem before building: **the only deliverable channel is the in-app feed, which is pull-based** (seen on app-open), and **push is undeliverable** (no native app; `channel_available('push')` is False). So a "7am supplement" item in the feed has no timeliness — time-of-day delivery is semantically weak without push.

Options put to Andy: **A** capture+store now, deliver when push ships (#963 posture); **B** full build now (schedule store + hourly cron + in-app delivery); **B-lite** daily-log-ping delivery only. I recommended **A**. **Andy chose B.** This session builds B as two slices.

## 2. The design (full doc: `designs/Notifications_RecurringSchedule_964_Design_v1.md`)

Two architectural problems, both resolved by **reuse, not new infrastructure**:

1. **Recurring daily sends vs. `account_nudges`'s `UNIQUE (user_id, nudge_type)` one-shot constraint.** Reuse the **resurface pattern already proven for `plan_needs_review`** (`routes/nudges.py:679`): keep one row per `(user, type)` and on each daily fire **re-stamp `created_at = NOW()`, clear `read_at`/`dismissed_at`** so it floats up fresh. **No new feed table, no `account_nudges` schema change.** The banner / feed / read / dismiss / per-type in-app pref gate all work unchanged.
2. **Time-of-day needs per-user timezone (none existed; `athlete_supplements.timing` is categorical, not clock times).** New **`users.timezone`** (IANA name) — the normalized home (a user's many schedule rows share one tz). Send granularity is the **hour** (`send_hour` 0–23), not the minute — sidesteps minute precision and the half-hour-offset-tz cracks an on-the-hour cron would miss. NULL tz ⇒ a schedule never fires (fail-safe).

`schedule_type` == the `account_nudges.nudge_type` it fires (identity mapping → trivial cron).

## 3. What shipped — Slice 1 (storage + capture; NO delivery yet)

| File | Change |
|---|---|
| `init_db.py` | `_PG_MIGRATIONS`: `CREATE TABLE notification_schedules (user_id, schedule_type, send_hour SMALLINT, enabled, last_sent_on DATE, updated_at; PK (user_id, schedule_type))` + `ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT`. Both auto-apply on deploy — **no layer0-apply owed** (public schema). |
| `notification_schedules_repo.py` *(new)* | `SCHEDULE_TYPES` registry (4 types; AM+PM roll up to the `supplement_reminder` pref), `HOUR_CHOICES`, curated `TIMEZONES`. `get_schedules` / `build_schedule_view` (off-at-default-hour when no row; fail-open) / `set_schedule` (rejects unknown type + out-of-range hour) / `get_user_timezone` (fail-open None) / `set_user_timezone` (rejects unlisted tz) / `save_schedules_from_form` (off-state captured by registry iteration, bad hour → default, one commit). |
| `notification_prefs.py` | 3 new §22 types: `supplement_reminder`, `next_day_workouts`, `daily_log_ping` — `info`, channels `['in_app','push']`, email non-applicable (no nudge→email path), defaults in_app/push True. |
| `routes/nudges.py` | `import notification_schedules_repo`; `nudges.schedules` route (GET renders view; POST `save_schedules_from_form`, fail-soft flash). |
| `templates/nudges/schedules.html` *(new)* | Enable-toggle + hour-picker per type + timezone selector; no-JS, CSP-clean; reuses `ns-*` classes; nudges "set your timezone or nothing fires." |
| `templates/nudges/settings.html` | One-line cross-link to the schedule page. |
| `tests/test_notification_schedules.py` *(new)* | Pref-type registration, schedule registry (AM+PM→one toggle, hour/tz lists), repo round-trip + defaults + fail-open, form-save (off-state, bad-hour→default, tz accept/reject), crafted-input guards. |

**File count:** 6 substantive code files + the design doc — slightly over the 5-file nominal. The smallest cohesive unit here is "storage + capture" (capture without storage is nothing); flagged rather than split further into an awkward storage-only/capture-only pair.

## 4. Verification

- Full suite **3835 passed / 30 skipped** (`python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest Flask-WTF`). Only the 3 pre-existing #217 `evidence_basis` warnings.
- Ruff clean on all changed files. The one reported `init_db.py:3406` E402 is **pre-existing** (confirmed: present with my changes `git stash`ed) and unrelated to the migration-list append.
- **No Neon/layer0 apply owed** — public-schema migrations auto-apply on deploy.

## 5. NEXT — STILL ON #964: Slice 2 (delivery)

Wire the fire path onto Slice 1's storage. ~5 files, within ceiling:
- **`routes/nudges.py`** — `scan_scheduled_sends` route (`GET /cron/notifications/scheduled`), token-gated. Per-fire logic (Rule #15 — log each fire): select due schedules where `EXTRACT(HOUR FROM (NOW() AT TIME ZONE u.timezone)) = s.send_hour AND u.timezone IS NOT NULL AND (s.last_sent_on IS NULL OR s.last_sent_on < (NOW() AT TIME ZONE u.timezone)::date)`; per row **resurface-upsert** into `account_nudges` (`ON CONFLICT (user_id, nudge_type) DO UPDATE SET created_at = NOW(), read_at = NULL, dismissed_at = NULL`) + advance `last_sent_on` to the local date. Returns `{sent: {...}}`. (Design doc §4.)
- **`routes/nudges.NUDGE_REGISTRY`** — 4 entries: `supplement_am`/`supplement_pm` (CTA → supplement list in `routes/profile.py`, `notification_type: 'supplement_reminder'`), `next_day_workouts` (CTA → plan/calendar view, `notification_type: 'next_day_workouts'`), `daily_log_ping` (CTA → `log.index`, `notification_type: 'daily_log_ping'`). All `info`. **Static copy** (account_nudges has no per-row content column — `next_day_workouts` says "look at tomorrow's training," CTA deep-links to the live plan; dynamic enumeration is a deliberate non-goal).
- **`vercel.json`** — add `{ "path": "/cron/notifications/scheduled", "schedule": "0 * * * *" }`.
- **`app.py`** — add `'nudges.scan_scheduled_sends'` to `_AUTH_EXEMPT_ENDPOINTS`.
- **`tests/test_notification_schedules.py`** — cron due-selection matrix (local-hour match, NULL-tz skip, `last_sent_on` same-day dedup + advance, resurface-upsert shape), 4 registry-entry shapes (AM+PM both → `supplement_reminder`).

**Then (still #964):** conditions advisory (coordinate with **#289**). **Blocked on #939:** race-day-7d + share-with-crew (no race-day-plan artifact/generator; no crew-sharing). **After #964:** the standing **#884** arc (slice 5 — away overlay).

### §6 anchor table (Rule #10 — next session's Rule #9 input)

| File | Anchor string | Check |
|---|---|---|
| `init_db.py` | `CREATE TABLE IF NOT EXISTS notification_schedules (` | grep |
| `init_db.py` | `ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT` | grep |
| `notification_schedules_repo.py` | `SCHEDULE_TYPES = [` | grep |
| `notification_schedules_repo.py` | `def save_schedules_from_form(` | grep |
| `notification_prefs.py` | `'key': 'supplement_reminder',` | grep |
| `routes/nudges.py` | `def schedules():` | grep |
| `templates/nudges/schedules.html` | `name="timezone"` | grep |
| `tests/test_notification_schedules.py` | `class TestSaveSchedulesFromForm:` | grep |
| `designs/Notifications_RecurringSchedule_964_Design_v1.md` | `# Recurring time-of-day notifications` | grep |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff + the design doc (`designs/Notifications_RecurringSchedule_964_Design_v1.md`)
5. `./scripts/verify-handoff.sh` — automated anchor sweep
