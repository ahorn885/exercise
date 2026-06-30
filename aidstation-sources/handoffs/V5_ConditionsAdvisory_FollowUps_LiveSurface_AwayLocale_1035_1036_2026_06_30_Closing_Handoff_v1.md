# V5 — Conditions Advisory follow-ups: live-conditions CTA surface (#1035) + away-window locale resolution (#1036) — Closing Handoff (2026-06-30)

**Branch:** `claude/notification-triggers-conditions-pbcz11` (both follow-ups; PR not yet opened — push + bookkeep + wait for Andy's go) · **Issues:** [#1035](https://github.com/ahorn885/exercise/issues/1035) (live-conditions surface, §11.2) / [#1036](https://github.com/ahorn885/exercise/issues/1036) (away-window locale, §11.3), children of epic #286 · **Design:** `designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md` §11.2 / §11.3 / §7 / §5 (Slice 3) · **Kickoff:** `handoffs/V5_ConditionsAdvisory_FollowUps_LiveSurface_AwayLocale_1035_1036_2026_06_30_Kickoff_Handoff_v1.md`.

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` clean (no ❌); working tree clean at start; the Slice 2 §8 anchors (`_CONDITIONS_CROSSES`, the `conditions_advisory` registry/pref/reconcile entries, the `TestConditionsAdvisoryWiring` block) all present. Proceeded from the kickoff scope.

## 2. What shipped — both follow-ups (one cohesive arc; separable into two PRs, they share no code)

### #1035 — live upcoming-conditions surface for the CTA (design §11.2)

The `conditions_advisory` nudge fires "extreme weather coming," but its CTA (`plans.list_plans`) lands on the plan view, which rendered only the Layer-5B climate **normals** — not the live forecast that triggered it. **Andy's placement call (AskUserQuestion 2026-06-30): fold into the plan view** (option 1, not a standalone page). So the live forecast extremes now render in the plan-view Conditions card beside the normals; **the CTA is unchanged** (`plans.list_plans` — the surface lives where the CTA already lands, so no re-point and no `tests/test_nudges_staleness.py` CTA-assertion change).

- `upcoming_conditions_repo.load_upcoming_for_user(db, user_id)` — pure read, today-forward rows ordered by date, normalised to plain dicts.
- `routes/nudges.select_upcoming_extremes(rows)` — the Python twin of `_CONDITIONS_CROSSES`, **sharing the same `HEAT_TMAX_C` / `FREEZE_TMIN_C` / `RAIN_PROB_PCT` constants** so the surface and the nudge's arm/clear can never disagree. Returns `{date, temp_max_c, temp_min_c, precip_prob_pct, flags}` per crossing day; non-crossing days dropped.
- `routes/plan_create.view_plan` — loads + classifies, passes `upcoming_extremes` to the template inside an advisory try/except (a load fault must never 500 the view, matching the existing nutrition/conditions/evidence blocks) + a Rule #15 `[conditions-surface]` log when extremes are surfaced.
- `templates/plan_create/view.html` — the `cond-card` renders an "⚠ Extreme weather in the next 7 days" block (heat/freeze/rain chips, temps, precip %) **only when** a crossing day sits in the window; absent (graceful) otherwise.

### #1036 — away-window locale resolution in the producer (design §11.3 / §7)

**Rule #14 gate CLEARED — the gap is REAL.** A read-only `neon-query` data pull (2026-06-30) showed the one away window on record (user 1, Scottsdale Marriott, 2026-06-22→26) had **every** covered `plan_sessions` row carrying a *home* locale (`home` / `509_williams_avenue`), never the destination `scottsdale_marriott_at_mcdowell_mountains` (every `matches = f`). So the producer, keying off the session's `locale_id`, would fetch the **home** forecast for a travel day — exactly the §7 home-vs-away class #941 fixed for plan-view weather. Not a no-op; built.

- `athlete_event_windows_repo.resolve_away_location(db, user_id, on_date) → (slug, lat, lng) | None` — the **away-only** branch of `resolve_weather_location` (returns the destination slug + coords, or `None`). Deliberately **no** home/none fallthrough: on a non-away day the session's own locale is the right forecast point, so `None` tells the caller to keep its per-session resolution. `resolve_weather_location` is **untouched** (its other callers are unaffected). Rule #15 `[conditions-away]` log.
- `layer5/upcoming_conditions.refresh_upcoming_conditions_for_user` — per-date resolution now does: away window covering the date wins (destination coords + slug), else the session locale's coords; a date whose point has no coordinates is dropped (best-effort). Forecast fetch memoized **one call per distinct coordinate** (keyed on the rounded `"lat,lng"` token, not the slug — repeated away days / a shared home point collapse to one fetch). The persisted `upcoming_conditions.locale_id` now correctly reflects the forecast location (away slug on travel days). Summary log counts distinct `locations`.

## 3. Verification

- Full suite **3963 passed / 30 skipped** (+28 over Slice 2's 3935; only the 3 pre-existing #217 Layer3B warnings).
- New tests: `tests/test_upcoming_conditions.py` (repo read; `select_upcoming_extremes` heat/freeze/rain + boundary + multiflag + calm-empty; producer away→destination / non-away→session-locale / memoization-one-fetch); `tests/test_plan_view_conditions_render.py` (extremes block renders with chips; absent when empty); `tests/test_athlete_event_windows_repo.py` (`resolve_away_location` slug+coords / no-window→None / unanchored→None).
- `ruff check` clean on all changed files.
- **No Neon/layer0 apply owed** — read/render + producer-only; no schema change.
- **Live-verify owed (Andy, gated on deploy + real upcoming weather):** open a plan view while a real heat/freeze/rain day sits inside the 7-day horizon → confirm the "⚠ Extreme weather" block renders the right day(s) and `[conditions-surface]` logs in `/admin/logs`; if an away window lands inside the horizon, confirm the `upcoming_conditions` row for that day carries the destination slug and `[conditions-away]` logs (via `neon-query`). Folds into the arc-level live-verify the design §9 already owns.

## 4. File count

#1035: 4 substantive (`upcoming_conditions_repo.py`, `routes/nudges.py`, `routes/plan_create.py`, `templates/plan_create/view.html`) + 2 test files. #1036: 2 substantive (`athlete_event_windows_repo.py`, `layer5/upcoming_conditions.py`) + tests (shares `tests/test_upcoming_conditions.py`, adds `tests/test_athlete_event_windows_repo.py`). Counted as two within-ceiling slices (the handoff framed them so); each is small and self-contained.

## 5. NEXT

Both §11 follow-ups done → **the conditions-advisory arc + both deferred enhancements are fully closed** (§11.1 thresholds, §11.2 surface, §11.3 away-locale). Nothing further owed on #1035/#1036 beyond the deploy-gated live-verify. Live threads, unchanged priority: the standing **#884** (slice 6c) and **#971** slice 2 (the Layer-2C disputed-item slice); **#939-blocked** race-day-7d + share-with-crew.

**PR note:** both follow-ups are on this one branch as cohesive work. They're cleanly separable into two PRs (#1035 = surface, #1036 = producer; no shared code) if Andy prefers — otherwise one PR closing both. Opens + auto-merges (MERGE commit) on Andy's go.

---

### §6 anchor table (Rule #10 — next session's Rule #9 input)

| File | Anchor string | Check |
|---|---|---|
| `upcoming_conditions_repo.py` | `def load_upcoming_for_user(` | grep |
| `routes/nudges.py` | `def select_upcoming_extremes(` | grep |
| `routes/plan_create.py` | `upcoming_extremes = select_upcoming_extremes(` | grep |
| `routes/plan_create.py` | `upcoming_extremes=upcoming_extremes,` (render_template) | grep |
| `templates/plan_create/view.html` | `Extreme weather in the next 7 days` | grep |
| `athlete_event_windows_repo.py` | `def resolve_away_location(` | grep |
| `layer5/upcoming_conditions.py` | `from athlete_event_windows_repo import resolve_away_location` | grep |
| `layer5/upcoming_conditions.py` | `point_by_date: dict[date, tuple[str, float, float]]` | grep |
| `designs/...289_964_Design_v1.md` | `**Live-conditions surface for the CTA — ✅ SHIPPED 2026-06-30 (#1035).**` | grep |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff + the design doc (`designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md` §11 / §7 / §5)
5. `./scripts/verify-handoff.sh` — automated anchor sweep (lives at `aidstation-sources/scripts/`)
