# Conditions advisory — live upcoming-conditions producer (#289) + advisory notification (#964) — design

**Issues:** [#289](https://github.com/ahorn885/exercise/issues/289) (Layer-5 conditions advisor — *the producer*) · [#964](https://github.com/ahorn885/exercise/issues/964) (notifications: new trigger types — *the consumer*) · **Epics:** #286 (#289), #259 (#964) · **Decision:** Andy 2026-06-29 — **build the live-forecast producer + advisory**, with the producer **designed as a #289 Layer-5 surface first** (over reusing the climate-normals `plan_conditions` blob, and over holding the whole thing blocked).

This design closes the **conditions advisory** trigger on #964 ("rain / freezing / over 100°"). It is the one remaining #964 trigger that needs *new data*, not a new fire mechanism — so the bulk of the work is a small **#289 producer** (a live-forecast signal persisted in a shape a notification can query), and the consumer is one more `_STALENESS_RECONCILE` entry on the existing daily cron.

---

## 1. Why the existing conditions data can't drive this notification (Rule #9 correction)

The prior #964 handoff scoped this as "coordinate with #289 — is a conditions signal persisted/queryable, or does #289 need to land a producer first?" The on-disk answer corrects a stale assumption: **Layer 5B *is* built** — `weather_client.py` + `layer5/conditions_builder.py` + `layer5/conditions_orchestrator.py` produce a per-day clothing/conditions advisory persisted in `plan_conditions` and rendered in the plan view. That *is* #289's "7-day clothing/conditions advisor," already shipping.

But that data is the **wrong source for a notification**, for three concrete reasons:

1. **It's climate *normals*, not a live forecast.** `weather_client.get_expected_conditions` averages 5 years of archive data ±3 days around the date; the artifact's own standing note is *"dress for these, but check the live forecast nearer the day."* Normals don't change day-to-day — a normals-driven nudge would either fire on every warm-season plan day or just echo what the plan view already shows. A notification must fire on something **new and actionable**; "rain / freezing / over 100° **coming up**" is inherently a near-term *forecast* signal.
2. **It's keyed per `plan_version_id` as one opaque JSONB blob** (`plan_conditions.payload_json`, `UNIQUE (plan_version_id)`), not by `(user, date)`. The reconcile-nudge pattern is pure SQL (`_STALENESS_RECONCILE` insert/delete); it cannot read a JSONB array of `DayConditions`. A cron would have to deserialize every active plan's blob and filter in memory — brittle and off-pattern.
3. **Thresholds differ.** The builder flags heat at 28 °C / 82 °F (a *clothing* band boundary); the #964 advisory is about genuinely extreme, alert-worthy conditions ("over 100°").

So the clean path is a **small live-forecast producer** that persists a queryable per-`(user, date)` signal, designed as a #289 Layer-5 surface, which the #964 advisory then reads via the existing reconcile pattern. The producer reuses the same external source (Open-Meteo), the same coordinate plumbing (`locale_profiles.lat/lng`, post-#941), and the same deterministic/zero-LLM posture as Layer 5B.

---

## 2. Architecture — producer (#289) → signal table → consumer (#964)

```
DAILY producer cron  (/cron/conditions/refresh, before the reconcile cron)
   for each user with an active READY plan:
     load that plan's sessions in [today, today + HORIZON]   (plan_sessions_repo)
     per training-day locale -> lat/lng                       (locale_profiles, post-#941)
     one Open-Meteo FORECAST call per distinct locale         (weather_client.get_upcoming_forecast)
     upsert one row per (user, forecast_date) into upcoming_conditions
     prune that user's rows with forecast_date < today
                                   │
                                   ▼
        upcoming_conditions  (user_id, forecast_date) — PLAIN, QUERYABLE
          temp_max_c · temp_min_c · precip_prob_pct · locale_id · refreshed_at
                                   │
                                   ▼
DAILY reconcile cron  (/cron/nudges/reconcile, existing)
   new _STALENESS_RECONCILE entry 'conditions_advisory':
     INSERT a nudge while ANY row in the user's [today, today+HORIZON] window
            crosses a threshold (heat | freeze | rain)
     DELETE it once no crossing row remains (forecast updated / days passed)
                                   │
                                   ▼
        account_nudges row  ->  banner + feed  (existing surface, unchanged)
```

The producer is the **only** new infrastructure. The consumer is one reconcile spec + one notification type + one registry entry — no new cron, no new feed table, no `account_nudges` schema change (same as `plan_needs_review` / `race_week_plan_due`).

---

## 3. The producer signal — `upcoming_conditions` (#289, Layer 5C)

A new public-schema table holding, per user, the **live forecast** for each upcoming **training day** at that day's session locale. One row per `(user, date)` — exactly the shape a reconcile spec can `WHERE` against.

```sql
-- Live near-term forecast for each upcoming training day, per user. Refreshed
-- daily by the producer cron; pruned as days pass. Distinct from plan_conditions
-- (climate normals, baked per plan_version) — this is the live, queryable signal
-- the conditions-advisory notification fires on. Public-schema _PG_MIGRATIONS
-- (auto-applies on deploy; NO layer0-apply).
CREATE TABLE IF NOT EXISTS upcoming_conditions (
    user_id         INTEGER  NOT NULL REFERENCES users(id),
    forecast_date   DATE     NOT NULL,          -- the training day (local calendar date)
    locale_id       TEXT,                       -- the session locale this forecast is for
    temp_max_c      DOUBLE PRECISION,           -- forecast daily high (°C, Open-Meteo native)
    temp_min_c      DOUBLE PRECISION,           -- forecast daily low (°C)
    precip_prob_pct SMALLINT,                   -- forecast max precip probability (0–100)
    refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, forecast_date)
);
```

- **Canonical storage is °C** (Open-Meteo native; the same convention `weather_client`/Layer 5B already use). Thresholds are expressed in °C; athlete-facing rendering (if/when a surface shows it) uses the existing `units.c_to_f` toggle.
- **`DOUBLE PRECISION`** not `REAL` — matches the precision decision from #196 Slice 2.3 (avoids single-precision round-trip drift); cheap, table is tiny.
- **One row per `(user, date)`**, not per-locale-per-date: a training day has one representative locale (the day's first session carrying a locale — same `_representative_session` rule Layer 5B uses). `locale_id` is carried for transparency/debugging, not keyed on. Multi-locale days are a non-goal for v1 (the plan rarely splits a single day across locales).
- **Volume:** ≤ `HORIZON` rows per user with an active plan. One test athlete today; trivially small at launch scale.

### 3.1 The forecast fetch — extend `weather_client`

`weather_client` already has `get_forecast_high` (single day, temp-max only, Open-Meteo `/v1/forecast`). Add a sibling that returns the **per-day triple** over a date range in one call:

```python
@dataclass(frozen=True)
class DayForecast:
    temp_max_c: float
    temp_min_c: float
    precip_prob_pct: int

def get_upcoming_forecast(
    latitude: float | None, longitude: float | None,
    start_date: date, end_date: date, *, fetcher: Fetcher | None = None,
) -> dict[date, DayForecast]:
    """Per-day forecast for [start_date, end_date] at (lat, lng). Empty dict on
    missing coords / network error / malformed response (best-effort, same
    degrade-to-empty contract as get_expected_conditions). Open-Meteo daily =
    temperature_2m_max,temperature_2m_min,precipitation_probability_max;
    timezone=auto so the daily buckets align to the locale's local calendar day."""
```

- **Best-effort by design** (mirrors the rest of the module): a network/parse failure yields an empty dict → that user's refresh writes nothing this run → the *previous* run's rows linger until they age out (acceptable; the advisory is not a guaranteed-delivery channel). No exception escapes the cron.
- **Horizon:** `ADVISORY_HORIZON_DAYS = 7`. Open-Meteo serves up to 16 forecast days, but `precipitation_probability_max` is only meaningfully reliable ~7 days out; beyond that we *deliberately* emit nothing rather than fall back to normals (a normals-based "alert" is exactly the low-value nudge §1 rejects).

### 3.2 The producer — `layer5/upcoming_conditions.py` + `upcoming_conditions_repo.py`

Mirror the existing Layer 5B split (`conditions_orchestrator.py` builds/persists; `plan_conditions_repo.py` is pure data-access):

- **`upcoming_conditions_repo.py`** (new, pure DB, no HTTP/Flask, caller owns the txn):
  - `upsert_upcoming_conditions(db, user_id, rows)` — `INSERT … ON CONFLICT (user_id, forecast_date) DO UPDATE` (re-stamps `refreshed_at`).
  - `prune_past(db, user_id, today)` — `DELETE … WHERE user_id=? AND forecast_date < ?`.
  - (No read helper needed by the consumer — the reconcile spec reads the table directly in SQL.)
- **`layer5/upcoming_conditions.py`** (new, the orchestration — the producer-cron's body):
  - `refresh_upcoming_conditions_for_user(db, user_id, *, today=None, fetcher=None)`:
    1. resolve the user's active **ready** plan version (the same selection `_ACTIVE_PLAN_NO_BRIEF` uses: `generation_status='ready' AND archived_at IS NULL AND completed_at IS NULL`, most-recent wins);
    2. `load_plan_sessions_by_version`; keep sessions with a locale whose `date ∈ [today, today + HORIZON]`; reduce to one representative locale per date (`_representative_session` rule);
    3. resolve each distinct locale → `lat/lng` (`locale_profiles`, same `_coords_for_locales` lookup Layer 5B uses; **away-window destination coords are a noted refinement** — v1 keys off the session's own `locale_id`, see §7);
    4. **one** `get_upcoming_forecast` call per distinct locale over the whole window (not per-day — bounds external calls to ~1–2/user);
    5. build `(forecast_date, locale_id, temp_max_c, temp_min_c, precip_prob_pct)` rows; `upsert` + `prune_past`;
    6. **Rule #15** log: `print(f"[conditions-refresh] user={uid} pv={pv} days={n} locales={k} crossed={c}")` (inputs + the decision: how many days, how many crossed a threshold).
  - `refresh_all_upcoming_conditions(db, *, today=None, fetcher=None)` — iterate users with an active ready plan; per-user try/except so one bad user/locale can't sink the batch.

### 3.3 The producer cron — `GET /cron/conditions/refresh`

- Daily, **before** the reconcile cron so the signal is fresh when the advisory reconciles. `vercel.json`: `{ "path": "/cron/conditions/refresh", "schedule": "0 13 * * *" }` (reconcile is `0 15 * * *`). Token-gated (`cron_authorized()`); `app.py` `_AUTH_EXEMPT_ENDPOINTS` entry (cron carries the `Authorization: Bearer $CRON_SECRET` header, no session cookie). Hosted in `routes/conditions.py` (the existing conditions route module) or a small dedicated module — TBD at build, leaning `routes/conditions.py` for cohesion. Returns `{refreshed: {users: N, rows: M}}`.

---

## 4. The consumer — `conditions_advisory` notification (#964)

One new reconcile spec, riding the **existing** daily `/cron/nudges/reconcile` (no new cron — same as `plan_needs_review`). `forecast_date` is a real `DATE`, so plain date arithmetic applies (no `TO_CHAR` ISO-text cutoff like the log/body/injury TEXT-date specs).

```python
# Thresholds — alert-worthy extremes (NOT the Layer-5B clothing-band boundaries).
# RATIFIED Andy 2026-06-29 (the "90°F recommendation set" — a heat-management
# heads-up bar, not record-heat; see Open item 11.1, resolved).
ADVISORY_HORIZON_DAYS = 7
HEAT_TMAX_C  = 32.2   # 90°F   forecast daily high at/above which heat matters
FREEZE_TMIN_C = 0.0   # 32°F   freezing overnight/low
RAIN_PROB_PCT = 60    # forecast precip probability — a real "likely to rain"

_CONDITIONS_CROSSES = f'''
    uc.forecast_date >= CURRENT_DATE
    AND uc.forecast_date <= CURRENT_DATE + {ADVISORY_HORIZON_DAYS}
    AND (uc.temp_max_c >= {HEAT_TMAX_C}
         OR uc.temp_min_c <= {FREEZE_TMIN_C}
         OR uc.precip_prob_pct >= {RAIN_PROB_PCT})'''

{
    'nudge_type': 'conditions_advisory',
    # Fires while the user has ANY upcoming training day inside the horizon whose
    # LIVE forecast crosses a heat/freeze/rain threshold.
    'insert': f'''
        INSERT INTO account_nudges (user_id, nudge_type)
        SELECT DISTINCT uc.user_id, 'conditions_advisory'
        FROM upcoming_conditions uc
        WHERE {_CONDITIONS_CROSSES}
          AND NOT EXISTS (
              SELECT 1 FROM account_nudges an
              WHERE an.user_id = uc.user_id AND an.nudge_type = 'conditions_advisory'
          )
        ON CONFLICT (user_id, nudge_type) DO NOTHING
        RETURNING id
    ''',
    # Clears once no crossing day remains in the window — the forecast updated
    # (rain dropped out), or the extreme day passed. Re-fires on a later spell.
    'delete': f'''
        DELETE FROM account_nudges an
        WHERE an.nudge_type = 'conditions_advisory'
          AND NOT EXISTS (
              SELECT 1 FROM upcoming_conditions uc
              WHERE uc.user_id = an.user_id AND {_CONDITIONS_CROSSES}
          )
        RETURNING id
    ''',
}
```

**Type registration — `notification_prefs.NOTIFICATION_TYPES` (1 new §22 row):**
```python
{
    'key': 'conditions_advisory',
    'label': 'Weather conditions advisory',
    'description': 'A heads-up when extreme weather — heat, freezing, or rain — '
                   'is forecast for an upcoming training day.',
    'category': 'warning',                 # safety-relevant, unlike the passive info nudges
    'channels': ['in_app', 'push'],
    'defaults': {'in_app': True, 'push': True},
}
```

**`routes/nudges.NUDGE_REGISTRY` (1 new entry):**
```python
'conditions_advisory': {
    'message': (
        'Extreme weather is in the forecast for an upcoming training day — '
        'check conditions and adjust your kit or timing.'
    ),
    'cta_label': 'View your plan',
    'cta_endpoint': 'plans.list_plans',    # see Open item 11.2 (a live-conditions surface)
    'category': 'warning',
    'notification_type': 'conditions_advisory',
}
```

**Static copy** (account_nudges has no per-row content column — same constraint as every other nudge): the message is generic ("extreme weather … upcoming training day"), not "100 °F on Saturday." The CTA deep-links to the plan. The honest gap: the plan view renders **normals**, not this live forecast — surfacing the live `upcoming_conditions` on a view is an Open item (§11.2), not a v1 blocker.

---

## 5. Slice plan (≈8 substantive files → two within-ceiling slices)

**Slice 1 — #289 producer (the new infrastructure). ✅ SHIPPED 2026-06-29** (commit on branch `claude/notification-triggers-recurring-schedule-6e50c0`; full suite 3928 passed / 30 skipped; ruff clean on changed files; no Neon/layer0 apply owed). ~5 substantive:
1. `weather_client.py` — `DayForecast` + `get_upcoming_forecast`.
2. `init_db.py` — `upcoming_conditions` CREATE (`_PG_MIGRATIONS`, auto-applies; **no layer0-apply**).
3. `upcoming_conditions_repo.py` (new) — `upsert_upcoming_conditions`, `prune_past`.
4. `layer5/upcoming_conditions.py` (new) — `refresh_upcoming_conditions_for_user` / `refresh_all_upcoming_conditions` (+ Rule #15 log).
5. `routes/conditions.py` — `GET /cron/conditions/refresh` (token-gated); plus the one-liners `vercel.json` (`0 13 * * *`) + `app.py` (auth-exempt) (bookkeeping-class one-liners).
6. `tests/test_upcoming_conditions.py` (new) — forecast parse (stub fetcher), repo upsert/prune, producer day-window + representative-locale + best-effort-empty, cron token gate.

After Slice 1 the live signal populates daily; **nothing fires yet** (no consumer).

**Slice 2 — #964 consumer (the advisory). ✅ SHIPPED 2026-06-30** (branch `claude/notification-triggers-conditions-advisory-4ho2av`; full suite 3935 passed / 30 skipped; ruff clean on changed files; no Neon/layer0 apply owed — pure consumer, no schema). ~2 substantive:
1. `routes/nudges.py` — the `conditions_advisory` `_STALENESS_RECONCILE` entry (insert-while-crossing / delete-when-clear) + `NUDGE_REGISTRY` entry (CTA `plans.list_plans`, `warning`) + threshold constants (`HEAT_TMAX_C 32.2` / `FREEZE_TMIN_C 0.0` / `RAIN_PROB_PCT 60` / `CONDITIONS_HORIZON_DAYS 7`) + shared `_CONDITIONS_CROSSES` fragment.
2. `notification_prefs.py` — the new §22 type (`warning`, `['in_app','push']`, email non-applicable).
3. `tests/test_nudges_staleness.py` — registry/pref wiring (`TestConditionsAdvisoryWiring`) + reconcile-spec crossing matrix (heat/freeze/rain OR'd, in-horizon, self-clear NOT EXISTS); the parametrized insert/delete + cron-route tests pick the new spec up automatically.

Both landed → the full build Andy chose.

---

## 6. Producer↔consumer ordering & freshness

- **Cron ordering:** producer `0 13` → reconcile `0 15` (2 h gap). The reconcile reads whatever the producer last wrote; a producer miss (deploy gap / API outage) leaves yesterday's rows, so the advisory degrades to slightly-stale, never to wrong-shape. Acceptable.
- **Self-healing:** because the consumer is a *reconcile* (insert-while-true / delete-when-false), a forecast that updates away from a threshold **clears** the nudge next reconcile; a new spell **re-fires** it. No manual dismissal needed for correctness.
- **Once-per-spell, not daily spam:** `UNIQUE (user_id, nudge_type)` + insert's `NOT EXISTS` guard means one standing advisory per user while *any* crossing day sits in the window — it doesn't re-stamp daily. (An escalation/re-surface ladder like `plan_needs_review` is a deliberate non-goal; a weather heads-up shouldn't nag.)

---

## 7. Edge cases

- **No active plan / no located sessions in the window** → producer writes nothing for that user → no advisory. Correct (nothing to advise about).
- **Locale with no coordinates** (legacy manual row pre-#941) → skipped (no coords → no forecast), same best-effort degrade as Layer 5B.
- **Open-Meteo down / malformed** → empty dict → that user's rows untouched this run; advisory rides the last good rows. No exception escapes (`refresh_all` per-user try/except).
- **Away/travel windows** → v1 keys the forecast off the **session's own `locale_id`**. If plan sessions already carry the travel locale for away days, this is already correct; if away-day sessions still carry the home locale, the forecast is for home. The post-#941 `resolve_weather_location` (away-destination coords win) is the **refinement** to fold in if §11.1 shows the gap matters — noted, not built v1.
- **Forecast horizon vs. plan length** → only the next 7 days are advised; a hot day 3 weeks out is silent until it enters the window. Intended (live forecast only).
- **Athlete mutes the type** (`disabled_in_app_types`) → display suppressed at read time (`get_active_nudges`), reconciliation-agnostic — same as every other type.
- **DST / half-hour tz** → not applicable; the producer keys on calendar `forecast_date` with Open-Meteo `timezone=auto`, no clock-hour matching.

---

## 8. Test scenarios

- `get_upcoming_forecast`: stub fetcher → per-day triple parsed; missing coords / empty / malformed → `{}`.
- Repo: upsert round-trip (insert then conflict-update re-stamps `refreshed_at`); `prune_past` drops only `< today`.
- Producer: only in-window located sessions written; one representative locale per date; one forecast call per distinct locale (memoized); best-effort empty writes nothing; Rule #15 line emitted.
- Consumer reconcile: insert fires on heat-only / freeze-only / rain-only crossings; ignores days outside the horizon; **delete** clears when the crossing drops out; re-insert on a later spell; `ON CONFLICT` keeps it idempotent across same-day cron double-fires.
- Registry/pref: `conditions_advisory` present, `warning`, `['in_app','push']`, email-non-applicable.

---

## 9. Verification & ops

- Full `tests/` green (`python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`), per-file `tests/test_upcoming_conditions.py` + the consumer tests.
- Ruff: zero new findings on changed files.
- **No Neon/layer0-apply owed** — `upcoming_conditions` is public-schema (`_PG_MIGRATIONS`, auto-applies on deploy), same as `notification_schedules`/`user_source_preferences`.
- Live-verify (gated on Andy + real upcoming weather): after deploy, hit `/cron/conditions/refresh`, confirm `[conditions-refresh]` rows in `/admin/logs` and `upcoming_conditions` populated (via `neon-query.yml`); when a real spell lands inside the horizon, the advisory appears in the feed and clears after it passes.

---

## 10. Why this over the alternatives (decision record)

- **vs. reuse `plan_conditions` (climate normals):** rejected — normals are typical-not-live, already shown in the plan view, and only reachable by JSONB-scanning every active plan. A normals "alert" is a low-value nudge (§1). *Andy 2026-06-29.*
- **vs. hold blocked / spec-only:** rejected — the producer is small (forecast API we already call + a thin queryable table), so there's no reason to park a now-buildable feature. *Andy 2026-06-29.*
- **vs. a Python-side cron that fetches live weather and inserts nudges directly (no table):** rejected — couples the notification to the network in the hot path, can't reconcile/clear cleanly, and re-fetches on every read. The persisted-signal split keeps the consumer pure SQL (reconcile-pattern) and the producer best-effort/offline-tolerant.
- **Producer owned by #289, designed first:** *Andy 2026-06-29* — it's a Layer-5 surface (deterministic, zero-LLM, weather-derived), sibling to the 5B normals advisor; #964 is purely its consumer.

---

## 11. Open items (decide before/at build)

1. **Threshold calibration — RESOLVED (Andy 2026-06-29).** Heat lands at **32.2 °C / 90 °F** (the "90°F recommendation set" — a heat-*management* heads-up, not record-heat), freeze at `temp_min ≤ 0 °C / 32 °F`, rain at `precip_prob ≥ 60%`. Constants in §4; baked into Slice 2. *(User impact: too-high a bar = the advisory rarely fires; too-low = it nags. No infra impact.)*
2. **Live-conditions surface for the CTA.** The advisory deep-links to the plan, which renders **normals**, not this live forecast. A small surface that renders `upcoming_conditions` (or folding it into the dashboard/plan-view conditions block beside the normals) would make the CTA land on the actual forecast that triggered the nudge. Deferred enhancement — not a v1 blocker, but the most natural follow-up.
3. **Away-window locale resolution** (§7) — fold `resolve_weather_location` (away-destination coords win) into the producer if travel-day sessions don't already carry the travel locale. Confirm against real plan-session data before building (Rule #14 — don't infer).

---

## 12. Gut check

- **Strongest risk:** Slice 1 ships a producer + daily external-API cron that does nothing user-visible until Slice 2 — and if Slice 2 slips, we're paying Open-Meteo calls for an unread table. Mitigated by both slices landing in one arc; the cost is trivial (≤7 calls/user/day, one test athlete).
- **External dependency in a cron** is new for this subsystem (the other nudge crons are pure DB). The best-effort/degrade-to-empty contract and per-user try/except contain it, and `weather_client` already models exactly this for plan-gen — so it's a known-good pattern, not a new failure mode.
- **The CTA/normals mismatch** (§11.2) is the weakest UX seam — the nudge says "extreme weather coming" but the link shows typical conditions. Honest for v1 (the message itself is accurate and the plan is the right place to act), but worth closing soon.
- **What might be missing:** per-day content in the nudge ("100 °F Saturday") would be far more useful than the generic copy, but needs an `account_nudges` content column — the same deferred item the recurring-send design flagged. If/when that column lands, this advisory is a prime first consumer.
- **Scope honesty:** the producer genuinely expands #289 from "iceboxed idea" to "shipping Layer-5 surface #2." That's intended (Andy chose build + #289-owned), but it means #289 should be re-labelled off `icebox` and its body updated to point at this design.
