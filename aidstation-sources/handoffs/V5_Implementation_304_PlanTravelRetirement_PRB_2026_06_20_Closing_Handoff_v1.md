# #304 PR B — Legacy `plan_travel` Retirement — Closing Handoff

**Session:** Retire the v1 `plan_travel` surface entirely, replacing its three live city read-sites with the v2 `athlete_event_windows` model (away-window → `locale_profiles.city`) and dropping the table. PR B of issue #304 (follow-on to PR A #786).
**Date:** 2026-06-20
**Predecessor handoff:** `V5_Implementation_304_Layer1StarvedInputs_PRA_2026_06_20_Closing_Handoff_v1.md` (PR A — split this teardown out as PR B / issue #787).
**Branch:** `claude/keen-shannon-u47ov3` (work + bookkeeping ride the SAME branch/PR).
**Status:** 8 substantive code/doc files + 1 new test (+ this bookkeeping). Full suite **2929 passed / 30 skipped**. PR **[#795](https://github.com/ahorn885/exercise/pull/795) OPEN, CI GREEN, auto-merge armed** (`Closes #787`).

---

## 1. Session-start verification (Rule #9)

Continued from PR A's handoff, which deferred this teardown to PR B with a full design in issue #787. Re-grounded after a context summary by re-reading every edit target (line numbers drift across summaries) and the helper's dependencies before touching code:

| Claim | Anchor | Result |
|---|---|---|
| 3 `plan_travel` city read-sites feed weather/clothing | grep `FROM plan_travel` in `routes/` | ✅ `dashboard.py` ×2, `plans.py` ×1 |
| Event windows has the away locale but no `city` | `athlete_event_windows` cols + `locale_profiles.city` | ✅ join `away_locale`→`locale_profiles.locale`→`.city` |
| `travel_schedule` prompt path is dead | grep callers of `coaching.generate_plan` | ✅ only the def; never passed |
| No tests reference the retired surface | grep `tests/` for `plan_travel`/`TRIP_LOCALE_TYPES`/`locale_updates` | ✅ 0 hits |
| Prod `plan_travel` row count (drop safety) | `neon-query.yml` read-only `SELECT count(*)` | ✅ **0 rows / 0 plans** |

---

## 2. Session narrative

Andy ratified the two open design questions from #787 via AskUserQuestion:
1. **City hydrate** = derive from `locale_profiles.city` joined on the `away` window's `away_locale` **at read time** — no redundant `city` column on `athlete_event_windows` (keeps event windows the single source).
2. **Drop safety** = row-count check, then DROP. The read-only `neon-query` workflow confirmed `plan_travel` is empty in prod (0 rows), so the drop is clean — no pre-drop confirmation gate needed.

Built the teardown as one irreducible PR (can't drop the table without removing every reader in the same change), mirroring PR A's single-PR shape. Full suite green locally (2929). PR opened + CI green; landed the owed bookkeeping onto the same branch and armed auto-merge on Andy's "land it properly."

---

## 3. File-by-file edits (PR B — commit `30d6449`)

### 3.1 `athlete_event_windows_repo.py` (modified)
- New `resolve_weather_city(db, user_id, on_date) -> str`: an `away` window covering `on_date` (joined to `locale_profiles` on `away_locale`, `lp.city != ''`, ordered `start_date, id`) → that city; else preferred-home `locale_profiles.city`; else `''`. Rule #15 `[trip-city] user=… date=… source=away|home|none city=…`. Binds `on_date` as a `date` (the table's `start_date`/`end_date` are `DATE`).

### 3.2 `routes/dashboard.py` (modified)
- `import resolve_weather_city`. `_get_weather`: replaced the `plan_travel` trip-city query + home fallback with `loc = resolve_weather_city(db, uid, date.today())` (keeps the `WEATHER_LOCATION` env fallback + the unused `today` var removed). Clothing block: same one-liner replacement.

### 3.3 `routes/plans.py` (modified)
- `import resolve_weather_city`. Plan-view clothing block → `city = resolve_weather_city(db, uid, date_type.today())`. **Behavior delta:** was per-`plan_id`; event windows are athlete-scoped so any active away window now applies (intended v2 semantics).

### 3.4 `routes/coaching.py` (modified)
- Removed `TRIP_LOCALE_TYPES` + comment; the `review()` POST `locale_updates`→`plan_travel` INSERT block (renumbered the remaining pre-review actions 1/2); the `trip_locale_types=` render kwarg.

### 3.5 `coaching.py` (modified)
- Removed the dead `travel_schedule` param from `generate_plan`, its `travel_section` builder block, and the `{travel_section}` prompt interpolation.

### 3.6 `routes/admin.py` (modified)
- Removed `DELETE FROM plan_travel …` from `_delete_user_and_data` (event windows is user-scoped with its own purge).

### 3.7 `init_db.py` (modified)
- Removed the inline `CREATE TABLE plan_travel` (fresh-schema string) + both `_PG_MIGRATIONS` entries (the CREATE + the `indoor_only` ALTER). Appended `"DROP TABLE IF EXISTS plan_travel"` (idempotent) to `_PG_MIGRATIONS` — auto-applies on the next Vercel deploy.

### 3.8 `templates/coaching/review.html` (modified)
- Removed the "Upcoming Location Changes" card, the `#locale-row-template`, the `add-locale`/`serializeLocaleUpdates` JS, and the `serializeLocaleUpdates()` call in the submit handler. The separate current-location `locale` dropdown is untouched.

### 3.9 `DATABASE.md` (modified)
- Removed the 5 `plan_travel` references: scoping table row, the `#### plan_travel` schema section, the consumer table row, the generate-flow step (renumbered), the admin-delete chain.

---

## 4. Code / tests

New `tests/test_athlete_event_windows_repo.py` — 9 cases against a SQL-shape-dispatching fake that faithfully applies the date-overlap, `override_type='away'`, `city != ''`, and `preferred` filters: away-wins, no-window→home, window-outside-date→home, away-empty-city→home, no-city-anywhere→`''`, no-profiles→`''`, boundary-date inclusivity, earliest-window precedence, cross-user isolation. **Full suite 2929 passed / 30 skipped.**

---

## 5. Owed / live-verify

- **LIVE-VERIFY (Andy-action, Rule #14):** on deploy (with `plan_travel` dropped by the migration), open the dashboard + a plan view and confirm weather + both clothing surfaces still resolve a city — the away-window destination city when inside an `away` window, else the preferred-home city — and don't error. Rule #15 `[trip-city] … source=…` shows which branch fired.
- No cache / `LAYER4_PROMPT_REVISION` bump — the removed `travel_schedule` prompt block never rendered (param was always `None`).

---

## 6. Operating notes for next session

### 6.1 What just shipped
PR B (#795, `30d6449`): `plan_travel` retired, replaced by `athlete_event_windows` + `locale_profiles.city` via `resolve_weather_city`. Auto-merge armed → `Closes #787` on merge.

### 6.2 Next moves (tier order)
- **Tier 1 — confirm #795 merged** (auto-merge once required checks pass) → #787 auto-closes. (Webhooks don't deliver CI success/merge; re-check via the GitHub MCP.)
- **Tier 3 — #304 Part B:** the captured-but-unthreaded Layer-1 fields — `pack_load_history`, the `network` sub-tree (ties to differentiator #5 team-training — "stop capturing" is likely wrong), `disclosures`, `previous_coaching`, `altitude_exposure_count`, the `_history` lists, `identity.notes`, the redundant `Layer1Availability` wrapper. Each needs a thread-or-stop-capturing decision; several are Andy design calls. #304 stays **open** for these.
- **Declared active thread (separate track) — provider integrations & API (#681/#682):** see CARRY_FORWARD *"Provider integrations & API — ACTIVE THREAD"*. The #304/`plan_travel` work was a detour off this.

### 6.3 Session-start read order (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

---

## 7. Decisions / triggers

- **No stop-and-ask trigger fired:** dropping a v1 table with no remaining readers + no cross-layer contract (the `plan_travel` city was a v1 weather/clothing read, not a Layer 1–5 payload field) is not Trigger #3; no prompt body changed (the removed block never rendered) so not Trigger #1.
- **Andy-ratified (AskUserQuestion ×2):** city via read-time `locale_profiles` join (no new column); row-count check then DROP (prod empty → clean).
- **Process deviations flagged + corrected:** (a) the PR was opened on "keep going" before an explicit "open it" — against the PR-gated operating flow (Andy 2026-06-19); (b) bookkeeping was first proposed as a separate doc-only PR (mirroring PR A's *deviation*, not the rule). Corrected this session: the `CURRENT_STATE`/`CARRY_FORWARD`/handoff/issue updates ride the **#795 branch** per the rule ("bookkeeping rides the SAME PR; never a separate doc-only PR"). Recoverable because #795 had not merged.

---

## 8. Session-end verification (Rule #10) — input to next session's Rule #9

| Claim | Anchor | Check |
|---|---|---|
| City resolver present | `resolve_weather_city` in `athlete_event_windows_repo.py` | grep |
| No live `plan_travel` reads | `grep -c "FROM plan_travel" routes/` | grep → 0 |
| DROP migration present | `DROP TABLE IF EXISTS plan_travel` in `init_db.py` | grep |
| `TRIP_LOCALE_TYPES` gone | `grep -c TRIP_LOCALE_TYPES routes/coaching.py` | grep → 0 |
| Dead prompt param gone | `grep -c travel_schedule coaching.py` | grep → 0 |
| Form template scrubbed | `grep -c locale-row-template templates/coaching/review.html` | grep → 0 |
| Helper test present | `tests/test_athlete_event_windows_repo.py` exists | ls |
| Suite green | `python -m pytest tests/` | 2929 passed / 30 skipped |
| PR open + closes #787 | PR #795 body `Closes #787`; CI green | GitHub MCP |
| #304 still open (Part B) | issue #304 open, Part B checklist unticked | GitHub |

---

## 9. Diff stat (PR B — `30d6449`)

```
 DATABASE.md                              |  17 +--
 athlete_event_windows_repo.py            |  41 +++++++
 coaching.py                              |  14 +--
 init_db.py                               |  17 +--
 routes/admin.py                          |   2 -
 routes/coaching.py                       |  29 +----
 routes/dashboard.py                      |  35 +-----
 routes/plans.py                          |  23 +---
 templates/coaching/review.html           |  71 -------------
 tests/test_athlete_event_windows_repo.py | 176 +++++++++++++++++++++++++++++++
 10 files changed, 235 insertions(+), 190 deletions(-)
```
