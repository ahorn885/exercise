# V5 Implementation — Notification Triggers: Recurring-Send Mechanism, Slice 2 (delivery) (#964) — Closing Handoff (2026-06-29)

**Branch:** `claude/notification-triggers-recurring-schedule-ne8qjt` · **PR:** not yet opened (push + bookkeep + wait for Andy's go) · **Issue:** [#964](https://github.com/ahorn885/exercise/issues/964) (type:feature, priority:med, area:notifications) · **Epic:** #259 · **Design:** `designs/Notifications_RecurringSchedule_964_Design_v1.md` (§4 = this slice) · **Suite:** full `tests/` **3890 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).
**Context:** Continuation of the #964 recurring-send arc. Predecessor (Slice 1 — storage + capture, PR merged as `b030e56`) landed the `notification_schedules` table + `users.timezone` + the capture UI + the 3 new `notification_prefs` types. **Andy chose the full build** (schedule store + hourly cron + in-app delivery) back in Slice 1's Stop-and-ask Trigger #5 decision; this session shipped **Slice 2 (delivery)** — the fire path — completing that choice across the two-slice arc.

---

## 1. Session-start verification (Rule #9)

Slice 1's handoff §6 anchor table swept clean against on-disk state:
- `init_db.py` — `notification_schedules` CREATE + `users.timezone` ALTER both present.
- `notification_schedules_repo.py` — `SCHEDULE_TYPES`, `save_schedules_from_form`, `set_user_timezone`, `get_user_timezone` all present.
- `notification_prefs.py` — `supplement_reminder` / `next_day_workouts` / `daily_log_ping` registered.
- `routes/nudges.py` — `schedules()` route + `import notification_schedules_repo` present; `scan_scheduled_sends` correctly **absent** (this slice's work).
- `templates/nudges/schedules.html`, `tests/test_notification_schedules.py` present.

(`./scripts/verify-handoff.sh` is referenced in Slice 1's §6 read order but lives at `aidstation-sources/scripts/verify-handoff.sh`, not repo-root `scripts/` — noted, not a gap in Slice 1's work.)

## 2. What shipped — Slice 2 (delivery)

| File | Change |
|---|---|
| `routes/nudges.py` | **4 new `NUDGE_REGISTRY` entries** (`supplement_am`/`supplement_pm` → CTA `profile.edit`, both `notification_type: 'supplement_reminder'`; `next_day_workouts` → CTA `plans.list_plans`; `daily_log_ping` → CTA `log.index`; all `info`, static copy). **3 module-level SQL constants** (`_SCHEDULED_DUE_SELECT`, `_SCHEDULED_RESURFACE_UPSERT`, `_SCHEDULED_ADVANCE_LAST_SENT`). **New route `scan_scheduled_sends`** (`GET /cron/notifications/scheduled`, `cron_authorized()`-gated): one due-select, then per row a resurface-upsert + `last_sent_on` advance + a Rule-#15 per-fire log line; returns `{sent: {...}}`. |
| `vercel.json` | New cron entry `{ "path": "/cron/notifications/scheduled", "schedule": "0 * * * *" }` (hourly on the hour). |
| `app.py` | `'nudges.scan_scheduled_sends'` added to `_AUTH_EXEMPT_ENDPOINTS` (cron hits it with no session cookie; auth is the `Authorization: Bearer $CRON_SECRET` header verified inside the route). |
| `tests/test_notification_schedules.py` | **+11 tests** across `TestScheduledSendRegistry` (4 feed entries shaped; AM+PM share the `supplement_reminder` toggle; registry covers every `SCHEDULE_TYPES` key), `TestDueSelectSql` (due-select guards: NULL-tz fail-safe, local-hour match, last_sent_on dedup; resurface upsert re-stamps `created_at` + clears `read_at`/`dismissed_at`; advance writes the local-date watermark), `TestScheduledSendsRoute` (token-gated 401 touches no DB; due rows → `SELECT, INSERT, UPDATE, INSERT, UPDATE` with the right params + one commit; no-due-rows is a clean SELECT-only no-op that still commits once). |

**Delivery logic (design §4).** A schedule is due when `enabled AND u.timezone IS NOT NULL AND EXTRACT(HOUR FROM (NOW() AT TIME ZONE u.timezone)) = s.send_hour AND (s.last_sent_on IS NULL OR s.last_sent_on < (NOW() AT TIME ZONE u.timezone)::date)`. Localization happens in Postgres — no Python tz library in the hot path. NULL timezone ⇒ never due (fail-safe). The resurface-upsert reuses the `plan_needs_review` pattern verbatim: one row per `(user, nudge_type)`, re-stamped fresh each daily fire. `last_sent_on` advancing to the local date bounds delivery to once per local day (a second cron fire in the same hour is a no-op).

**File count:** 2 substantive code files (`routes/nudges.py`, the test file) + the `vercel.json`/`app.py` one-liners — under the 5-file ceiling.

## 3. Verification

- Full suite **3890 passed / 30 skipped** (`python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest Flask-WTF`). The new schedule file alone: **31 passed**. Only the 3 pre-existing #217 `evidence_basis` warnings.
- Ruff: **zero new findings** on the changed files. The 42 `app.py` E402s are the pre-existing deferred-blueprint-import structure — confirmed identical count with the working diff `git stash`ed. The test file is clean.
- **No Neon/layer0 apply owed** — this slice adds no schema; it fires onto Slice 1's `notification_schedules` + `users.timezone`, both already auto-applied via `_PG_MIGRATIONS` on deploy.

## 4. Decisions / notes

- **CTA endpoints** resolved against the live route map: supplements live on the profile edit page (`profile.edit`, `/profile/` — `add_supplement`/`delete_supplement` are POST-only, the list renders under `_health_tab.html`); `next_day_workouts` lands on `plans.list_plans` (same generic, always-actionable landing the `plan_needs_review`/`race_week_plan_due` nudges use — there's no zero-arg per-plan calendar route); `daily_log_ping` lands on `log.index` (same as `log_reminder`).
- **Static copy** is a deliberate non-goal-to-fix this slice — `account_nudges` has no per-row content column, so `next_day_workouts` reads "Here's a look at tomorrow's training — open your plan" and deep-links the live plan rather than enumerating tomorrow's sessions. Dynamic per-send content would need a content column; deferred (design §3).
- **Per-row loop, not one set-based UPSERT** — the design (§4) and Rule #15 want each fire individually logged, so the route iterates the due-select result and logs per row.

## 5. NEXT (DECIDED — Andy 2026-06-29): #964 conditions advisory, coordinating with #289

The recurring-send arc is **COMPLETE** (Slice 1 storage+capture + Slice 2 delivery both shipped). Of the two #964 triggers left, **Andy chose the conditions advisory next** — the race-day-7d + share-with-crew pair stays **blocked on #939** (no race-day-plan artifact/generator, no crew-sharing) and isn't buildable until #939 ships those.

**The work — conditions advisory (#964 × #289):**
- **Coordinate with #289 first** — read where #289 stands before scoping. The advisory is a notification *surface* over the conditions/weather data #289 owns; the two need to agree on the producer→consumer contract (what conditions signal exists, on what cadence, keyed how) before this becomes a clean slice. Don't assume the shape — open #289, see what's built vs. specced, and surface the contract decision to Andy if it's a Trigger #3 cross-layer surface (likely).
- **Likely shape (to validate against #289, not to build blind):** a reconcile-spec or schedule-driven nudge that fires when a relevant conditions signal crosses a threshold for the athlete's upcoming training/race — reusing the same `account_nudges` surface + `notification_prefs` type pattern the rest of #964 uses. Whether it's a one-shot *condition* nudge (reconcile-spec, like `race_week_plan_due`) or a recurring *send* (schedule, like this slice) depends on what #289 exposes.
- **Open question for Andy / #289:** is there a conditions/weather signal already persisted and queryable (Rule #14 — don't infer it), or does this advisory need #289 to land a producer first? If the latter, this is blocked-on-#289, not buildable-now — flag it rather than building a nudge with no data behind it.

**After #964:** the standing **#884** arc (slice 5/6 — away overlay / capture UX) and **#971** slice 2 (photos / Vercel Blob) remain live threads.

### §6 anchor table (Rule #10 — next session's Rule #9 input)

| File | Anchor string | Check |
|---|---|---|
| `routes/nudges.py` | `def scan_scheduled_sends():` | grep |
| `routes/nudges.py` | `_SCHEDULED_DUE_SELECT = '''` | grep |
| `routes/nudges.py` | `    'supplement_am': {` | grep |
| `routes/nudges.py` | `    'daily_log_ping': {` | grep |
| `vercel.json` | `/cron/notifications/scheduled` | grep |
| `app.py` | `'nudges.scan_scheduled_sends',` | grep |
| `tests/test_notification_schedules.py` | `class TestScheduledSendsRoute:` | grep |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff + the design doc (`designs/Notifications_RecurringSchedule_964_Design_v1.md`)
5. `./scripts/verify-handoff.sh` — automated anchor sweep (lives at `aidstation-sources/scripts/`)
