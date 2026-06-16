# #620 — Generated plans named after the target race — COMPLETE — Closing Handoff

**Session:** Andy steered off the #430/#679 strength-rx arc to "high-priority issues for app launch and usability for new users." No clear in-flight target remained (#430 Slice C closed last session). Via `AskUserQuestion` he chose **Quick v1 UX wins**; I picked **#620** (highest-priority of that bucket, surfaced from his own plan-71 walkthrough) and shipped it as one PR.
**Date:** 2026-06-16
**Predecessor handoff:** `V5_Implementation_RxWire_430_SliceC_FK_Cutover_2026_06_16_Closing_Handoff_v1.md`
**Branch:** `claude/app-launch-usability-7imonw`
**Status:** PR **[#683](https://github.com/ahorn885/exercise/pull/683) MERGED** to `main` (squash, auto-merge on green CI). #620 closed via "Closes #620". This handoff + the `CURRENT_STATE.md` pointer land in a small bookkeeping follow-up PR (docs only).

---

## 1. Session-start verification (Rule #9)
`verify-handoff.sh` clean at start (all #430 Slice C anchors ✅, working tree clean). Predecessor §8 spot-checked. Direct continuation, no drift.

## 2. Session narrative
- Andy: "let's keep going… look at high-priority issues for app launch and usability for new users." Surveyed the tracker: of 35 `priority:high` open issues, **22 are compliance** (privacy/DSR/deletion — launch *blockers* but mostly legal/ops decisions + large builds), the rest are v2 plan-gen/pipeline. The new-user-usability surface = `area:onboarding` + `area:ux`. Only **#251 (OAuth-first onboarding, designed)** is both high-priority and code-actionable there.
- `AskUserQuestion` → Andy picked **Quick v1 UX wins**. Of that bucket (#620 plan-naming, #526/#527 wellness polish, #543 health-condition dropdown), **#620** is highest-priority (med vs low), broadest-reach, and came straight from his plan-71 walkthrough → chosen.

## 3. What shipped (#620)
Generated `plan_versions` plans had **no name**; three surfaces hardcoded "Generated plan" / "Training plan". Now a label is **derived** from the athlete's target race.
- **`plan_naming.py` (NEW)** — single source of truth:
  - `target_race_name(db, user_id)` → the `race_events.is_target_event=TRUE` row's `name` (lightweight single-column read; deliberately NOT `load_race_event_payload`, which fans out into route-locale/equipment/terrain queries). Uses `row.get("name")` so a generic render-test fake row degrades to "no race" rather than KeyError-ing the page.
  - `generated_plan_name(race_name, scope_start, scope_end)` → `"<race> — <N>-week build"` (N = `round(days/7)` from scope; suffix dropped when <1 or dates unusable), else plain `"Training plan"`.
- **`routes/plans.py`** `list_plans` — one race read for the page; attaches `display_name` to each generated row.
- **`routes/plan_create.py`** `view_plan` — passes `plan_name` to the header (`<title>`, crumb, `<h1>`).
- **`routes/dashboard.py`** — new `_v2_plan_names(db, uid, sessions)` resolves today/tomorrow v2 cards' names (one race read + one `plan_versions` scope read for the distinct ids); **returns {} with zero queries when there are no v2 sessions** (the common new-user case). `_v2_session_card` gained a `plan_name=None` param (fallback `"Training plan"`).
- **Templates:** `plans/list.html` (card title → `c.display_name`), `plan_create/view.html` (title/crumb/h1 → `plan_name`).
- **Derived at render time — NO schema migration, no edit UI** (the issue asked for a *default* name).

## 4. Code/tests
Full suite **2550 passed / 30 skipped** (was 2543; +7). New `tests/test_plan_naming.py` (suffix / ISO-string dates / no-race fallback / unusable-scope / whitespace). Updated render-fakes to model the target-race read: `test_redesign_plans_list_render.py` (`_RaceCursor`, `race_name` param, + a "named after target race" assertion and a no-race "Training plan"/no-"Generated plan" assertion); `test_redesign_log_wellness_render.py` (`monkeypatch pc.target_race_name → None`); `test_routes_dashboard.py` (assertion "Generated plan"→"Training plan" + a supplied-name case). venv: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`. NO DDL; Layer-0 gate + JS harness unaffected.

## 5. Decisions pinned (this session)
| # | Decision | Picked by |
|---|---|---|
| 1 | Next track: Quick v1 UX wins (not compliance, not #251) | Andy (`AskUserQuestion`) |
| 2 | Within bucket: #620 first (highest-prio, broadest reach) | Claude |
| 3 | **Derive** the name at render time (no stored column / edit UI) | Claude (issue says "default name") |
| 4 | Name = `"<race> — <N>-week build"`, fallback `"Training plan"` | Claude (matches Andy's issue example) |
| 5 | Include the dashboard (6 substantive files, 1 over the ~5 ceiling) rather than ship a list/dashboard inconsistency | Claude (flagged) |

## 6. Next session pointers

### 6.1 REMAINING in the "Quick v1 UX wins" bucket
- **#543** — profile health-condition capture as a curated, system-filtered dropdown (no free text). **Needs Andy to ratify which conditions qualify (Trigger #2 vocab add)** before building — stop-and-ask.
- **#526 / #527** — wellness page: group the 24+ charts into collapsible sections / "what changed" headline strip (both `priority:low`, v1, pure-ish UI).
- **#620 was the only `area:ux` item with `priority:med`+broad reach.**

### 6.2 Bigger new-user / launch items (if pivoting up a tier)
- **#251 — OAuth-first onboarding** (`priority:high`, designed D-58): the literal front door for a stranger. Reorders sign-up so a provider connects before the rest. Touches the OAuth flow — check it doesn't brush Trigger #1 (prompt) / #3 (cross-layer).
- **Compliance cluster** (22 `priority:high`): the real go-live gate, but mostly Andy-decisions (DPO #390, DPA #389, fairness thresholds #388) + large feature builds (account deletion #356, DSR self-service #359/#378). Pick the most code-actionable epic if going there.
- **#679 (Slice D)** — Garmin FIT-name→EX-id resolver: still the recommended *data-mapping* next from the #430 arc (highest dogfood impact for Andy's own Garmin strength data).

### 6.3 Operating notes for next session (read order)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. This handoff 5. `./scripts/verify-handoff.sh`.

## 7. Manual verification — OWED (Andy-action)
Can't drive the live app from the container. Worth an eyeball on the preview/prod: with a target race set, the plans list card + plan header + dashboard eyebrow read `"<race> — <N>-week build"`; with no target race they read `"Training plan"`. (Carried: post-#572 live **T3 refresh** re-verify, Rule #14; #430 Slice C EX-id self-heal live-verify.)

## 8. Session-end verification (Rule #10)
| Check | Result |
|---|---|
| `plan_naming.generated_plan_name` + `target_race_name` exist | ✅ plan_naming.py |
| plans-list attaches `display_name` from the target race | ✅ routes/plans.py |
| `view_plan` passes `plan_name`; view.html title/crumb/h1 use it | ✅ routes/plan_create.py + templates/plan_create/view.html |
| dashboard v2 cards derive the name (`_v2_plan_names`) | ✅ routes/dashboard.py |
| list.html card title → `c.display_name` | ✅ templates/plans/list.html |
| no remaining hardcoded "Generated plan" in templates/routes | ✅ (grep clean; only the `_v2_session_card` "Training plan" fallback) |
| Full suite green | ✅ 2550 passed / 30 skipped |
| PR #683 merged; #620 closed | ✅ |

## 9. Files shipped
**Substantive (6):** `plan_naming.py` (new), `routes/plans.py`, `routes/plan_create.py`, `routes/dashboard.py`, `templates/plans/list.html`, `templates/plan_create/view.html`. **Tests:** `tests/test_plan_naming.py` (new) + 3 updated. **Bookkeeping:** `CURRENT_STATE.md`, this handoff, #620 (closed via PR).

## 10. Carry-forward
- Standing: post-#572 live **T3 refresh** re-verify (Rule #14).
- #430 Slice C: live-verify the EX-id self-heal on a real log + downstream plan-gen (Andy-action).
- #679 Garmin FIT-name→EX-id resolver (the real "do Garmin uploads map correctly" fix).

---

**End of handoff.**
