# V5 — Notification Triggers: Conditions Advisory — DESIGN (live upcoming-conditions producer #289 + advisory notification #964) — Closing Handoff (2026-06-29)

**Branch:** `claude/notification-triggers-recurring-schedule-6e50c0` · **PR:** not yet opened (push + bookkeep + wait for Andy's go) · **Issues:** [#289](https://github.com/ahorn885/exercise/issues/289) (producer, epic #286) / [#964](https://github.com/ahorn885/exercise/issues/964) (consumer, epic #259) · **Design:** `designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md` · **Suite:** not run — **no code shipped this session** (design only).

**Context:** Continuation of the #964 arc. The recurring-send arc (Slices 1+2) is complete; the prior handoff's decided NEXT was "#964 conditions advisory, coordinating with #289." This session did that coordination, found the handoff's premise was stale (Rule #9), surfaced the architectural decision to Andy (Stop-and-ask Triggers #3 + #5), and — per Andy's choice — wrote the design.

---

## 1. Session-start verification (Rule #9)

The prior Slice-2 handoff's §6 anchor table swept clean (the recurring-send build is on disk):
- `routes/nudges.py` — `scan_scheduled_sends`, `_SCHEDULED_DUE_SELECT`, `supplement_am`, `daily_log_ping` all present.
- `vercel.json` — `/cron/notifications/scheduled` present (`0 * * * *`).
- `app.py` — `'nudges.scan_scheduled_sends',` auth-exempt present.
- `tests/test_notification_schedules.py` — `TestScheduledSendsRoute` present.

**Material Rule #9 finding (drove the whole session):** the prior handoff §5 (and #289's May comment) framed #289's conditions advisor as **unbuilt** / "no conditions signal." **On disk it IS built** — `weather_client.py` + `layer5/conditions_builder.py` + `layer5/conditions_orchestrator.py` + `plan_conditions_repo.py` produce a per-day climate-normals clothing advisory persisted in the `plan_conditions` table (`UNIQUE (plan_version_id)`, payload as JSONB), rendered in the plan view. The #941 weather/location fix (PR #980) further repointed weather off Mapbox `lat/lng`. So #289 is a **partially-shipped Layer-5 surface**, not an empty icebox — the assumption was reconciled before any work.

## 2. What shipped — the design (no code)

| File | Change |
|---|---|
| `designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md` | **New design doc** — the live upcoming-conditions producer (#289) + the conditions-advisory notification (#964), with implementation-ready SQL/signatures (Rule #11). |
| `CURRENT_STATE.md` | New last-shipped block; prior Slice-2 demoted to predecessor. |
| `CARRY_FORWARD.md` | (unchanged this session) |

Bookkeeping-class only — **zero substantive code files** (design + pointer + issue comments). Spec-first per Andy's "design first" choice.

## 3. The decision (Stop-and-ask — Triggers #3 cross-layer + #5 architectural alternatives)

Surfaced to Andy with options/tradeoffs/recommendation/gut-check; **Andy 2026-06-29 (AskUserQuestion ×2):**
1. **Approach = build a live-forecast producer + advisory** (over: reusing the climate-normals `plan_conditions` blob — rejected as a low-value, non-queryable signal; or holding blocked — rejected, the producer is small).
2. **Producer owner = make it a #289 design first** — the live-conditions signal is a Layer-5 surface #289 owns; #964 is purely its consumer. Design before build.

**Why the existing data can't drive the notification** (design §1): `plan_conditions` is climate *normals* (not live), keyed per `plan_version_id` as opaque JSONB (not queryable by `(user,date)` — the reconcile pattern is pure SQL), and its 28 °C clothing-band threshold isn't an alert-worthy extreme.

## 4. The designed architecture (design §2–§4 — for the builder)

**Producer (#289, "Layer 5C"):**
- New `weather_client.get_upcoming_forecast(lat,lng,start,end)` → `dict[date, DayForecast]` (temp_max_c/temp_min_c/precip_prob_pct; Open-Meteo `/v1/forecast` daily `temperature_2m_max,temperature_2m_min,precipitation_probability_max`, `timezone=auto`; best-effort empty-dict degrade).
- New **`upcoming_conditions (user_id, forecast_date)`** table — PK `(user_id, forecast_date)`, `temp_max_c`/`temp_min_c` `DOUBLE PRECISION`, `precip_prob_pct SMALLINT`, `locale_id`, `refreshed_at`. Public-schema `_PG_MIGRATIONS` (auto-applies; **no layer0-apply**).
- New `upcoming_conditions_repo.py` (`upsert_upcoming_conditions`, `prune_past`) + `layer5/upcoming_conditions.py` (`refresh_upcoming_conditions_for_user` / `refresh_all_upcoming_conditions`) — mirrors the existing `conditions_orchestrator`/`plan_conditions_repo` split. Resolves each user's active **ready** plan → in-window located sessions → one representative locale/date → one forecast call per locale → upsert + prune. Rule #15 `[conditions-refresh]` log.
- New cron `GET /cron/conditions/refresh` (token-gated, `app.py` auth-exempt, `vercel.json` `0 13 * * *` — **before** the `0 15` reconcile).

**Consumer (#964):** one `_STALENESS_RECONCILE` entry `conditions_advisory` on the **existing** `/cron/nudges/reconcile` (no new cron) — insert while any in-window day crosses `temp_max_c ≥ 37.8 OR temp_min_c ≤ 0.0 OR precip_prob_pct ≥ 60`, delete when none remain (self-clears/re-fires). New `notification_prefs` §22 type `conditions_advisory` (`warning`, `['in_app','push']`) + `NUDGE_REGISTRY` entry (CTA `plans.list_plans`, static copy). Full reconcile SQL is in design §4 (copy-paste ready).

## 5. Verification

- **No suite run / no ruff** — no code changed. (The design's §9 names the verification the build owes.)
- **No Neon/layer0 apply owed** — design only; the future `upcoming_conditions` table is public-schema.

## 6. NEXT — Slice 1 (#289 producer), on Andy's go

The build is pre-split (design §5) into two within-ceiling slices:
- **Slice 1 — #289 producer** (~5–6 files): `weather_client` forecast fn; `init_db` `upcoming_conditions`; `upcoming_conditions_repo.py`; `layer5/upcoming_conditions.py`; `routes/conditions.py` cron + `vercel.json`/`app.py` one-liners; `tests/test_upcoming_conditions.py`. After Slice 1 the signal populates daily; nothing fires yet.
- **Slice 2 — #964 consumer** (~2–3 files): `routes/nudges.py` reconcile spec + registry entry + thresholds; `notification_prefs.py` type; tests.

**Decide at/ before Slice 2 (design §11 open items):**
1. **Threshold calibration (real open question):** §4 pins heat at 37.8 °C / 100 °F per the #964 wording; for MN / a heat-*management* heads-up, 32 °C / 90 °F may be the better trigger. Ratify the heat/freeze/rain numbers — one-line constants.
2. **Live-conditions surface for the CTA** — the advisory deep-links to the plan, which shows *normals*, not this live forecast. A surface rendering `upcoming_conditions` is the natural follow-up (not a v1 blocker).
3. **Away-window locale resolution** — v1 keys off the session's own `locale_id`; fold in `resolve_weather_location` (away-destination coords win) only if real plan-session data shows away-days carry the home locale (Rule #14 — confirm, don't infer).

**Also:** #289 should be re-labelled off `icebox` and its body pointed at this design (it's now a shipping Layer-5 surface, not a parked idea).

**Other live threads (unchanged):** #939-blocked race-day-7d + share-with-crew; the standing #884 (slice 5/6) and #971 slice 2.

### §6 anchor table (Rule #10 — next session's Rule #9 input)

| File | Anchor string | Check |
|---|---|---|
| `designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md` | `# Conditions advisory — live upcoming-conditions producer` | grep (file exists) |
| `CURRENT_STATE.md` | `#289/#964 CONDITIONS ADVISORY — DESIGN` | grep (last-shipped block) |
| `designs/...289_964_Design_v1.md` | `CREATE TABLE IF NOT EXISTS upcoming_conditions` | grep (producer DDL spec'd) |
| `designs/...289_964_Design_v1.md` | `'nudge_type': 'conditions_advisory',` | grep (consumer reconcile spec'd) |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff + the design doc (`designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md`)
5. `./scripts/verify-handoff.sh` — automated anchor sweep (lives at `aidstation-sources/scripts/`)
