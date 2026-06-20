# #304 Layer-1 Starved Inputs (PR A) — Closing Handoff

**Session:** Wire the three Layer-4-read-but-`None`-hardcoded Layer-1 convenience fields (`experience_level`, `coaching_voice_preferences`, `travel_constraint`) and remove the dead `event_goal.target_race_event_id`. PR A of issue #304; the legacy `plan_travel` retirement split out as PR B (#787).
**Date:** 2026-06-20
**Predecessor handoff:** N/A — direct-task session off issue #304 (not a "continue prior work" session).
**Branch:** `claude/coaching-flags-render-next-0c00d4` (work, merged as #786 `817ae03`); `claude/304-pra-bookkeeping-0c00d4` (this doc-only bookkeeping PR).
**Status:** 7 substantive files (over the soft ceiling by 2 — accepted: one cohesive starved-input wave + the dead-field removal, Andy approved "all in one PR"). Full suite 2807 passed / 30 skipped. PR A **MERGED**.

---

## 1. Session-start verification (Rule #9)

Direct-task session — no predecessor handoff §8 table to anchor-check. Grounding instead came from reading the actual capture state before scoping (this corrected two wrong initial assumptions, see §2):

| Claim | Anchor | Result |
|---|---|---|
| `years_structured_training` has no capture form (orphan column) | grep templates/ + routes/ for the name | ✅ no writer — confirmed orphan |
| Travel IS captured (so `travel_constraint` has a real source) | `plan_travel` table + v2 `athlete_event_windows` | ✅ two surfaces; chose event-windows |
| `target_race_event_id` is a dead duplicate | grep repo-wide (excl. archive) | ✅ only builder/context/tests; the L3B test uses the `race_event_id` param, not this field |

**Reconciliation note:** Mid-session `git checkout main` + a silently-failing `git pull` left the local tree on a stale pre-PR-A `main` (`c58d143`); caught it before writing docs (builder.py showed `target_race_event_id` present) and rebased the bookkeeping branch onto the real `origin/main` (`817ae03`, PR A present). No bad commit made.

---

## 2. Session narrative

Picked up #304 (Layer-1 captured-but-unthreaded fields). Initial read of `layer1/builder.py:163-166` confirmed Part A: `experience_level` / `coaching_voice_preferences` / `travel_constraint` are read by the Layer-4 prompt builders but hardcoded `None`.

**Two assumption corrections from Andy (load-bearing):**
1. I first treated `years_structured_training` (a column in the SELECT list) as "captured" → wrong: no onboarding form or route writes it. So deriving `experience_level` from years was a non-starter without new capture. Andy: **self-select the band directly.**
2. I first thought travel had no source → wrong: travel IS captured. Andy: source `travel_constraint` from **event windows**, and **fully retire the legacy `plan_travel`** surface.

**Scope re-shaped twice via AskUserQuestion:** (a) experience capture = self-select; travel source = event-windows + remove plan_travel; (b) when an Explore sweep showed the `plan_travel` removal is a 10-file *live-path* teardown (3 city read-sites feed the weather/clothing path; event windows has no `city` field), recommended splitting → Andy chose **PR A (this) + PR B (#787)**.

PR A built, full suite green, Andy: commit/push/open + auto-merge. CI passed, squash-merged. Filed #787 for PR B with the full teardown design (durable handoff for next session's fresh container). Doc bookkeeping deferred (PR merged before it could ride the branch) → this doc-only PR on Andy's say-so.

---

## 3. File-by-file edits (PR A — `817ae03`)

### 3.1 `layer1/builder.py` (modified)
- Removed `_load_target_race_event_id` + its call + the `Layer1EventGoal(target_race_event_id=…)` kwarg.
- `_PROFILE_COLS` += `experience_level`, `coaching_voice_preferences`; `_load_athlete_profile` returns a 7th `convenience` dict (both row-present and empty branches); threaded into `Layer1Payload(...)` (replacing the `None`s).
- New `_summarize_travel_constraint(db, user_id)` — `load_event_windows` → one phrase per window (`indoor only` / `<locale> unavailable` / `training at <away_locale>` + brought-craft + notes), `None` when no windows. Rule #15 `[layer1-travel] …` log.
- Import `from athlete_event_windows_repo import load_event_windows`.

### 3.2 `layer4/context.py` (modified)
- `Layer1EventGoal.target_race_event_id` field removed (comment points at `RaceEventPayload` / L3B `race_event_id`).
- Updated the `Layer1Payload` convenience-fields comment (no longer "carry no v1 storage").

### 3.3 `athlete.py` (modified)
- `PROFILE_FIELDS` += `experience_level`, `coaching_voice_preferences`. New `EXPERIENCE_LEVEL_CHOICES = ('novice','developing','intermediate','advanced','elite')` (mirrors the payload `Literal`).

### 3.4 `init_db.py` (modified)
- Two additive nullable public-schema migrations: `athlete_profile.experience_level TEXT`, `athlete_profile.coaching_voice_preferences TEXT` (auto-apply on deploy).

### 3.5 `routes/profile.py` (modified)
- Import `EXPERIENCE_LEVEL_CHOICES`; pass it to the edit template; validate `experience_level` against the closed set on write (tampered → `None`); pass `coaching_voice_preferences=_str(...)` to `upsert_athlete_profile`.

### 3.6 `templates/profile/edit.html` (modified)
- `<select name="experience_level">` after Weekly-hours; `<textarea name="coaching_voice_preferences">` in the "Notes for the coach" card.

---

## 4. Code / tests

`tests/test_layer1_builder.py`: builder SELECT order swap is net-zero (retired target-race ↔ new event-windows → still 25, `test_25_selects_issued` holds); `_queue_andy` fixture +2 profile cols, dropped the race-events response, appended an event-windows response (renumbered the interior queue comments); `_PROFILE_COL_NAMES` helper +2; `test_explicit_off_rows_preserved` offset 23→22; removed the two `target_race_event_id` assertions; new `test_convenience_fields_threaded`. **2807 passed / 30 skipped.**

---

## 5. Owed / live-verify

- **LIVE-VERIFY (Andy-action, Rule #14):** on deploy, self-select an experience level + add an event window on `/profile` → confirm both surface in the synthesizer `=== Athlete context ===` block (experience band + travel constraint). Migrations auto-apply on deploy (public-schema).
- No cache-revision constant bumped — `layer1_hash` is content-derived, so it regenerates only for athletes who actually set these fields.

---

## 6. Operating notes for next session

### 6.1 What just shipped
PR A (#786, `817ae03`): the three starved Layer-1 inputs wired + dead `target_race_event_id` removed.

### 6.2 Next moves (tier order)
- **Tier 3/4 — PR B (#787):** retire `plan_travel`, fully replace with event windows. Full teardown design is in **issue #787** (blast radius, the `city`-field gap + the `locale_profiles`/`away_locale` hydrate, the v1 form/taxonomy/dead-param removals, the table drop, 2 open design questions). **Design next session** (Andy).
- **#304 Part B:** thread-or-stop decisions for `pack_load_history`, the `network`/`disclosures` sub-trees, `previous_coaching`, `altitude_exposure_count`, the `_history` lists, `identity.notes`, the redundant `Layer1Availability` wrapper. #304 stays **open** for these.

### 6.3 Session-start read order (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

---

## 7. Decisions / triggers

- **No stop-and-ask trigger fired in code:** the L4 prompt bodies already render these fields (`if voice:` etc.) — PR A supplies captured data to existing reads, not a prompt-body change (not Trigger #1). New nullable self-report columns are not an inter-layer contract change (not Trigger #3). `coaching_voice_preferences` is athlete free-text into the system prompt, consistent with the existing `notes` field.
- **Architectural choices (Andy-ratified via AskUserQuestion):** experience = self-select band; travel = event-windows source; `plan_travel` full retirement split into PR B.
- **Process deviation flagged:** bookkeeping did not ride the work PR (fast merge); recovered via an approved doc-only PR. The convention (`CLAUDE.md` Ops-automation operating flow) is bookkeeping-before-PR-open — do the docs first next time even when the task says "open it."

---

## 8. Session-end verification (Rule #10) — input to next session's Rule #9

| Claim | Anchor | Check |
|---|---|---|
| `target_race_event_id` gone from builder | `grep -c target_race_event_id layer1/builder.py` → 0 | grep |
| Travel summarizer present | `_summarize_travel_constraint` in `layer1/builder.py` | grep |
| Convenience fields threaded (not None) | `experience_level=convenience[` in `layer1/builder.py` | grep |
| Field removed from contract | `target_race_event_id` absent in `layer4/context.py` `Layer1EventGoal` | grep |
| New columns allow-listed | `experience_level` + `coaching_voice_preferences` in `athlete.py` `PROFILE_FIELDS` | grep |
| Migrations present | both `ADD COLUMN IF NOT EXISTS … experience_level / coaching_voice_preferences` in `init_db.py` | grep |
| Form fields present | `name="experience_level"` + `name="coaching_voice_preferences"` in `templates/profile/edit.html` | grep |
| Suite green | `python -m pytest tests/` | 2807 passed / 30 skipped |
| PR A merged | `git log origin/main` top = `817ae03` (#786) | git |
| PR B tracked | issue #787 open with teardown design | GitHub |

---

## 9. Diff stat (PR A)

```
 athlete.py                   | 11 +
 init_db.py                   |  6 +
 layer1/builder.py            | 80 +/-
 layer4/context.py            |  8 +/-
 routes/profile.py            |  9 +
 templates/profile/edit.html  | 12 +
 tests/test_layer1_builder.py | 56 +/-
 7 files changed, 141 insertions(+), 41 deletions(-)
```
