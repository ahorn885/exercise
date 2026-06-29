# Recurring time-of-day notifications — design (#964)

**Issue:** [#964](https://github.com/ahorn885/exercise/issues/964) (notifications: new trigger types) · **Epic:** #259 · **Decision:** Andy chose the **full build** (schedule store + hourly cron + in-app delivery now), 2026-06-29 — over the "capture now, deliver later" alternative.

This design covers the **recurring scheduled-send** family of #964 triggers — structurally distinct from every #964 trigger shipped so far. The reminder/staleness/race-week nudges (`log_reminder`, `body_metric_stale`, `injury_review`, `plan_needs_review`, `race_week_plan_due`) are **one-shot _condition_ nudges**: a row exists in `account_nudges` while a DB condition holds and is reconciled away when it clears. The triggers here fire on a **clock**, regardless of any standing condition:

| schedule_type | What it sends | Cadence |
|---|---|---|
| `supplement_am` | "Take your morning supplements." | daily, AM |
| `supplement_pm` | "Take your evening supplements." | daily, PM |
| `next_day_workouts` | "Here's a look at tomorrow's training." (evening preview) | daily, PM |
| `daily_log_ping` | "Log today's training." (opt-in daily cadence — distinct from `log_reminder`, which only fires after ~5 stale days) | daily |

---

## 1. The two architectural problems and how this resolves them

### 1.1 Recurring sends vs. `account_nudges`'s one-shot `UNIQUE (user_id, nudge_type)`

`account_nudges` has `UNIQUE (user_id, nudge_type)` — one row per user per type, ever. A daily send needs to re-surface fresh each day. **We do not need a new feed table or a schema change to `account_nudges`.** The `plan_needs_review` escalation ladder already established the exact pattern: keep one row per `(user, type)` and on each recurrence **re-stamp `created_at = NOW()` and clear `read_at`/`dismissed_at`** so it floats to the top of the feed and reads unread (`routes/nudges.py:679` `resurface`). A recurring send is that same upsert, run once per local day instead of per escalation rung.

**Consequence:** the recurring-send delivery reuses the entire existing surface unchanged — the banner (`get_active_nudges`), the feed (`get_feed_nudges`), read/dismiss actions, and the per-type in-app preference gate (`disabled_in_app_types`). The only new write is the schedule-driven upsert.

### 1.2 Time-of-day requires per-user timezone (none stored today)

The `users` table has no timezone column, and `athlete_supplements.timing` is categorical (`morning`/`evening`/`anytime`), not a clock time. Time-of-day is **new capture**. We add **`users.timezone`** (IANA name, e.g. `America/Chicago`) — the normalized home for a user-level attribute, so a user's multiple schedule rows share one tz (no update anomaly). Captured on the schedule settings page. A schedule whose user has a NULL timezone **never fires** (fail-safe — no localizing the clock without it).

**Send granularity is the hour, not the minute.** Schedules store `send_hour` (0–23, local). The cron fires hourly on the hour; matching on the whole local hour sidesteps minute precision and the half-hour-offset-timezone cracks an on-the-hour cron would otherwise miss (e.g. IST +5:30). A reminder does not need 7:03 precision.

---

## 2. Schema (two migrations, both `_PG_MIGRATIONS`-appended — auto-apply on deploy, no `layer0-apply`)

```sql
-- Per-user, per-type recurring send schedule. The *when*, orthogonal to the
-- notification_preferences *whether* matrix. PG-only (mirrors notification_preferences).
CREATE TABLE IF NOT EXISTS notification_schedules (
    user_id       INTEGER  NOT NULL REFERENCES users(id),
    schedule_type TEXT     NOT NULL,   -- supplement_am | supplement_pm | next_day_workouts | daily_log_ping
    send_hour     SMALLINT NOT NULL,   -- 0–23, local to users.timezone
    enabled       BOOLEAN  NOT NULL DEFAULT TRUE,
    last_sent_on  DATE,                -- local date of the last fire; NULL = never. Drives once-per-day dedup.
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, schedule_type)
);

-- Per-user IANA timezone (e.g. 'America/Chicago'). NULL ⇒ schedules never fire.
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT;
```

**No `cadence` column.** All four v1 types are daily; a cadence knob is speculative (simplicity-first). Add it when a weekly variant is actually requested.

**`schedule_type` == `nudge_type`** (same string). The cron's fire action is `upsert account_nudges (user_id, nudge_type=schedule_type)`, so the mapping is the identity — no translation table.

---

## 3. Type registrations

**`notification_prefs.NOTIFICATION_TYPES` — 3 new §22 rows** (the matrix is per *preference type*; the two supplement times share one toggle):
- `supplement_reminder` — channels `['in_app','push']`, `info`. (Covers both AM + PM schedule rows.)
- `next_day_workouts` — channels `['in_app','push']`, `info`.
- `daily_log_ping` — channels `['in_app','push']`, `info`.

Email non-applicable (no nudge→email path — same posture as the other #964 types). Push follows wire-now/deliver-later.

**`routes/nudges.NUDGE_REGISTRY` — 4 new entries** (one per schedule_type/nudge_type; AM + PM are distinct feed rows with distinct copy, both mapping to `notification_type: 'supplement_reminder'`):
- `supplement_am` → CTA `profile` (supplement list), `notification_type: 'supplement_reminder'`, `info`.
- `supplement_pm` → CTA `profile`, `notification_type: 'supplement_reminder'`, `info`.
- `next_day_workouts` → CTA the plan/calendar view, `notification_type: 'next_day_workouts'`, `info`.
- `daily_log_ping` → CTA `log.index`, `notification_type: 'daily_log_ping'`, `info`.

**Static message copy.** `account_nudges` carries no per-row content column, so messages come from the static registry. `next_day_workouts` therefore reads "Here's a look at tomorrow's training — open your plan" rather than enumerating tomorrow's actual sessions. Dynamic per-send content is a deliberate **non-goal** for this slice (would need a content column on `account_nudges`); the CTA deep-links to the live plan where the real sessions render.

---

## 4. The hourly cron — `GET /cron/notifications/scheduled`

Hourly (`vercel.json` `0 * * * *`), token-gated (`cron_authorized()`), auth-exempt entry in `app.py`. Per fire it logs the decision (Rule #15).

Logic (one SELECT of due schedules, then a per-row upsert + `last_sent_on` advance, so each fire is individually logged):

```
due = SELECT s.user_id, s.schedule_type
      FROM notification_schedules s JOIN users u ON u.id = s.user_id
      WHERE s.enabled
        AND u.timezone IS NOT NULL
        AND EXTRACT(HOUR FROM (NOW() AT TIME ZONE u.timezone)) = s.send_hour
        AND (s.last_sent_on IS NULL
             OR s.last_sent_on < (NOW() AT TIME ZONE u.timezone)::date)
for each (user_id, schedule_type) in due:
    UPSERT account_nudges (user_id, nudge_type=schedule_type)
        ON CONFLICT (user_id, nudge_type)
        DO UPDATE SET created_at = NOW(), read_at = NULL, dismissed_at = NULL   -- resurface
    UPDATE notification_schedules
        SET last_sent_on = (NOW() AT TIME ZONE u.timezone)::date
        WHERE user_id = ? AND schedule_type = ?
    print(f"scheduled-send fired: user={uid} type={schedule_type} local_date={d}")
returns {sent: {schedule_type: N, ...}}
```

- **Dedup / once-per-day:** the `last_sent_on < local_date` guard. A second cron fire in the same hour is a no-op; advancing `last_sent_on` to the local date bounds it to once per local day.
- **`NOW() AT TIME ZONE u.timezone`** does the localization in Postgres — no Python tz library needed in the hot path.
- **Volume:** tiny (only schedules due *this hour*). One test athlete today.

---

## 5. Capture UI

A new section/page reachable from the existing notification settings page (`nudges.settings`, `templates/nudges/settings.html`). For each schedule_type: an **enable toggle + an hour picker** (a `<select>` of 0–23 rendered as "7:00 AM" etc.), plus a **timezone `<select>`** (IANA list) that writes `users.timezone`. No JS — one Save posts the form (mirrors the settings matrix idiom: `name="sched:<type>:hour"`, `name="sched:<type>:enabled"`, `name="timezone"`; unchecked enable boxes don't post, so off-state is captured by iterating the registry). Degrades to defaults if the read faults (SQLite dev), same fail-open posture as the matrix.

Timezone selector defaults to unset → a clear "set your timezone so reminders arrive at the right local time" prompt; nothing fires until it's set.

---

## 6. Slice plan (the build is ~8 substantive files — over the 5-file ceiling → split into two within-ceiling PRs, both landing this arc)

**Slice 1 — storage + capture (foundation; no delivery yet).** ~5 files:
1. `init_db.py` — `notification_schedules` CREATE + `users.timezone` ALTER (both `_PG_MIGRATIONS`).
2. `notification_schedules_repo.py` (new) — CRUD, `build_schedule_view`, `save_schedules_from_form`, `get_user_timezone`/`set_user_timezone`.
3. `notification_prefs.py` — 3 new §22 types.
4. `routes/nudges.py` + `templates/nudges/schedules.html` — the capture route + template (link from settings).
5. `tests/test_notification_schedules.py` (new) — repo + view + form-save + the 3 new pref registrations.

Athlete can configure their times + timezone; nothing fires yet. (Functionally the "capture now" half — but it's the required foundation for delivery, not the deliver-later end state.)

**Slice 2 — delivery (wires the fire path onto Slice 1's storage).** ~5 files:
1. `routes/nudges.py` — the hourly cron `scan_scheduled_sends` + the 4 `NUDGE_REGISTRY` entries.
2. `vercel.json` — `0 * * * *` schedule.
3. `app.py` — auth-exempt entry for the new cron endpoint.
4. `tests/test_notification_schedules.py` — cron due-selection (tz/hour/dedup matrix) + registry-entry shape.
5. (the cron's SQL is exercised against the rendered statements as the other `_STALENESS_RECONCILE` tests do.)

Both ship this arc → achieves the full build across two reviewable PRs.

---

## 7. Edge cases

- **NULL `users.timezone`** → schedule never selected (fail-safe). The capture UI nudges the athlete to set it.
- **Half-hour-offset tz** → handled by hour-granular matching (no minute precision to miss).
- **DST shift** → `NOW() AT TIME ZONE name` honors DST automatically (IANA name, not a fixed offset). The send-hour can land one wall-clock hour off across a transition for a single day — acceptable for a reminder.
- **Cron double-fire in an hour** → `last_sent_on` guard makes the second a no-op.
- **Cron missed an hour** (deploy gap) → the schedule still fires later that same local day if the cron runs during a later hour? No — it only fires when `local_hour == send_hour`. A missed send-hour means the day is skipped (acceptable; not a guaranteed-delivery channel — push lands later). Documented, not engineered around.
- **Athlete disables a type** → `enabled = FALSE`; existing feed row (if present) stays until dismissed/reconciled. (Recurring rows aren't reconcile-deleted; they age out naturally as they stop being re-stamped.)
- **Athlete toggles the §22 in-app pref off** → display suppressed at read time (`get_active_nudges`), reconciliation-agnostic — same as every other type.

---

## 8. Test scenarios

- Repo round-trips a schedule (`enabled`, `send_hour`), and `set/get_user_timezone`.
- Form save: hour + enabled + timezone parsed from a settings POST; off-state captured by registry iteration.
- 3 new pref types registered with `info` + `['in_app','push']` + email-non-applicable.
- (Slice 2) Cron due-selection matrix: fires only when local hour matches; respects NULL tz; `last_sent_on` dedup blocks same-day re-fire; advances `last_sent_on`; the upsert resurfaces (re-stamps `created_at`, clears `read_at`/`dismissed_at`).
- (Slice 2) 4 registry entries shaped correctly; AM+PM both map to `supplement_reminder`.

---

## 9. Gut check

- **Strongest risk:** Slice 1 ships a config UI for reminders that don't fire until Slice 2 lands. Mitigated by both slices landing in the same arc; if Slice 2 slips, the #963 wire-now/deliver-later precedent makes the interim honest.
- **In-app time-of-day is weak without push** (the athlete only sees the feed on open). This was raised with Andy; he chose the full build anyway. The design keeps the door open: when push ships, the same schedule rows drive push delivery by adding a push branch to the cron — no schema change.
- **`users.timezone` is a new user-level column** other features will likely want — not speculative here (delivery needs it now), and the normalized home beats per-schedule-row duplication.
- **What might be missing:** a tz auto-detect (JS `Intl.DateTimeFormat().resolvedOptions().timeZone`) would beat a manual dropdown for UX, but adds JS to a deliberately no-JS settings surface — deferred; manual dropdown for v1.
```
