# V5 — Notification Triggers: Conditions Advisory — Slice 2 (#964 consumer — the advisory notification) — Closing Handoff (2026-06-30)

**Branch:** `claude/notification-triggers-conditions-advisory-4ho2av` · **PR:** not yet opened (push + bookkeep + wait for Andy's go) · **Issues:** [#289](https://github.com/ahorn885/exercise/issues/289) (producer, epic #286) / [#964](https://github.com/ahorn885/exercise/issues/964) (consumer, epic #259) · **Design:** `designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md` (§4 consumer spec; Slice 2 marked shipped §5) · **Suite:** full `tests/` **3935 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).

**Context:** Direct continuation of the prior session (design + Slice 1 producer). Slice 1 shipped the live `upcoming_conditions` signal; this session shipped **Slice 2 — the #964 consumer** (the advisory notification that reads that signal), exactly per design §4 (copy-paste ready). The conditions-advisory arc is now complete end-to-end.

---

## 1. Session-start verification (Rule #9)

The prior handoff's §6 anchor table swept clean — Slice 1 is on disk on this branch (the branch is cut off the merge that carries commit `9cfcf25 #289 Slice 1`):
- `weather_client.py` — `def get_upcoming_forecast(` present.
- `init_db.py` — `CREATE TABLE IF NOT EXISTS upcoming_conditions (` present.
- `upcoming_conditions_repo.py` — `def upsert_upcoming_conditions(` present.
- `layer5/upcoming_conditions.py` — `def refresh_all_upcoming_conditions(` present.
- `routes/conditions.py` — `def cron_refresh_conditions():` present.
- `vercel.json` — `/cron/conditions/refresh` present (`0 13 * * *`).
- `app.py` — `'conditions.cron_refresh_conditions',` auth-exempt present.
- `tests/test_upcoming_conditions.py` — present.

No gap to reconcile — the producer signal exists, so the consumer had real columns to read.

## 2. What shipped — Slice 2 (#964 consumer)

| File | Change |
|---|---|
| `routes/nudges.py` | **Threshold constants** (`CONDITIONS_HORIZON_DAYS = 7`, `HEAT_TMAX_C = 32.2`, `FREEZE_TMIN_C = 0.0`, `RAIN_PROB_PCT = 60`) + shared **`_CONDITIONS_CROSSES`** WHERE fragment (aliased `uc`; reused verbatim by insert + delete so arm/clear can't drift). New **`conditions_advisory` `_STALENESS_RECONCILE`** entry (insert-while-crossing / delete-when-clear). New **`NUDGE_REGISTRY`** entry (`warning`, CTA `plans.list_plans`, static copy). |
| `notification_prefs.py` | New **§22 `conditions_advisory`** type (`warning`, `['in_app','push']`, email non-applicable). |
| `tests/test_nudges_staleness.py` | `TestConditionsAdvisoryWiring` (registry + pref shape) + `test_conditions_advisory_spec_crosses_heat_freeze_rain_in_window` (crossing matrix: heat/freeze/rain OR'd, in-horizon both sides, self-clear NOT EXISTS); `RECONCILE_TYPES` extended → the parametrized insert/delete + cron-route tests pick the new spec up automatically. |

**2 substantive code files** + the test — under ceiling. Design + bookkeeping exempt.

**The reconcile (design §4, as built):**
- **Insert:** `SELECT DISTINCT uc.user_id, 'conditions_advisory' FROM upcoming_conditions uc WHERE {_CONDITIONS_CROSSES} AND NOT EXISTS (existing row)` `ON CONFLICT (user_id, nudge_type) DO NOTHING RETURNING id`. Fires while the athlete has ANY upcoming training day in `[CURRENT_DATE, CURRENT_DATE+7]` whose live forecast crosses heat/freeze/rain. One standing advisory per athlete (`DISTINCT` + `UNIQUE` + the `NOT EXISTS` guard) — no daily re-stamp, no escalation ladder.
- **Delete:** `DELETE FROM account_nudges an WHERE an.nudge_type = 'conditions_advisory' AND NOT EXISTS (SELECT 1 FROM upcoming_conditions uc WHERE uc.user_id = an.user_id AND {_CONDITIONS_CROSSES}) RETURNING id`. Clears once no crossing day remains (forecast updated away / extreme day passed), so it self-clears and re-fires on a later spell.
- `forecast_date` is a real `DATE` → plain `CURRENT_DATE + N` arithmetic (no `TO_CHAR` ISO-text cutoff like the log/body/injury TEXT-date specs).

## 3. Ratified thresholds (Andy 2026-06-29, "90°F recommendation set")

Heat ≥ **32.2 °C / 90 °F** (`temp_max_c`), freeze ≤ **0 °C / 32 °F** (`temp_min_c`), rain ≥ **60 %** (`precip_prob_pct`), horizon **7 days**. These are alert-worthy extremes — NOT the Layer-5B clothing-band boundaries. No open question blocked this slice.

## 4. Verification

- Full suite **3935 passed / 30 skipped** (`python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest Flask-WTF`); `tests/test_nudges_staleness.py` 30 passed (7 new). Only the 3 pre-existing #217 `evidence_basis` warnings.
- Ruff: **zero findings** on `routes/nudges.py` / `notification_prefs.py` / `tests/test_nudges_staleness.py`.
- **No Neon/layer0 apply owed** — Slice 2 is a pure consumer: it reads Slice 1's public-schema `upcoming_conditions`, adds no schema. The reconcile is PG-only (the cron is token-gated; SQLite dev never reaches it).

## 5. NEXT

The conditions-advisory arc (Slice 1 producer + Slice 2 consumer) is **complete end-to-end**. Nothing blocks.

**Bookkeeping owed at session close (done this session):** `CURRENT_STATE.md` pointer, this handoff, design §5 Slice-2-shipped marker, issue reconcile on #289 / #964.

**#289 should come off `icebox`** and its body point at the design — it's now a shipping Layer-5 surface, not a parked idea (carried over from the Slice 1 handoff; do it when touching the issues).

**Remaining design open items (§11, non-blocking) — filed as issues + scoped in a kickoff** (`handoffs/V5_ConditionsAdvisory_FollowUps_LiveSurface_AwayLocale_1035_1036_2026_06_30_Kickoff_Handoff_v1.md`):
- §11.2 → [#1035](https://github.com/ahorn885/exercise/issues/1035) **Live-conditions surface for the CTA** — the advisory deep-links to the plan, which renders *normals*, not this live forecast. A surface rendering `upcoming_conditions` is the natural follow-up (higher value, pure read/render). Not a v1 blocker.
- §11.3 → [#1036](https://github.com/ahorn885/exercise/issues/1036) **Away-window locale resolution** — v1 keys the forecast off the session's own `locale_id`; fold in `resolve_weather_location` (away-destination coords win) only if real plan-session data shows away-days carry the home locale (Rule #14 — confirm, don't infer; may close `not_planned`).

**Other live threads (unchanged):** the standing **#884** (slice 6c — onboarding parity + legacy retire) and **#971** slice 2 (photos / Vercel Blob); **#939-blocked** race-day-7d + share-with-crew.

### §6 anchor table (Rule #10 — next session's Rule #9 input)

| File | Anchor string | Check |
|---|---|---|
| `routes/nudges.py` | `_CONDITIONS_CROSSES = f'''` | grep |
| `routes/nudges.py` | `'nudge_type': 'conditions_advisory',` | grep |
| `routes/nudges.py` | `'conditions_advisory': {` (NUDGE_REGISTRY) | grep |
| `notification_prefs.py` | `'key': 'conditions_advisory',` | grep |
| `tests/test_nudges_staleness.py` | `class TestConditionsAdvisoryWiring:` | grep |
| `tests/test_nudges_staleness.py` | `def test_conditions_advisory_spec_crosses_heat_freeze_rain_in_window(` | grep |
| `designs/...289_964_Design_v1.md` | `**Slice 2 — #964 consumer (the advisory). ✅ SHIPPED 2026-06-30**` | grep |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff + the design doc (`designs/Notifications_ConditionsAdvisory_289_964_Design_v1.md`)
5. `./scripts/verify-handoff.sh` — automated anchor sweep (lives at `aidstation-sources/scripts/`)
