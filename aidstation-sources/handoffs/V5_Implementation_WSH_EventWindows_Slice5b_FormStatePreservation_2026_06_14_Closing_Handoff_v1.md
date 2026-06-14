# V5 Implementation — WS-H: Event Windows — Slice 5b: 2b round-trip form-state preservation (#608 item 2) — Closing Handoff

**Session:** Picked up the Slice-5b/F1 closing handoff; Andy: *"let's keep going."* Of the two remaining #608 items I surfaced both with a recommendation; **Andy chose item 2 — the 2b round-trip form-state preservation — built via a server-side session stash** (over a CSP carve-out). The away-window capture's "create a not-yet-saved destination" round-trip (Slice 2b) used to **reset the half-filled window form** when the athlete bounced out to `/locales/new` and back — strict CSP (`app.py` forbids inline JS) blocks the obvious client-side fix. Now the in-progress form is stashed in the session (consumed once on return) and replayed into the form. **No DDL / no prompt / no vocab / no cache-key change** — reuses the existing windows routes + repo; only the capture surface moved.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice5b_PlanGenReviewPanel_2026_06_14_Closing_Handoff_v1.md` (Slice 5b item 1 / the F1 plan-gen review panel, PR #609 merged + live).
**Branch:** `claude/plan-gen-review-panel-mqah8e`.
**Spec/arc:** `designs/Event_Windows_Design_v1.md` §6 (Slice 5 "capture UX polish") + §F1/§F5. No separate spec (UX wiring, no DDL / no resolution change / no vocab / no trigger — the design line + issue [#608](https://github.com/ahorn885/exercise/issues/608) are the spec). **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. **#608 tracks the Slice-5b remainder** — this PR is **item 2 of the two that were left**; #608 stays open for item 3 (onboarding F5).

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the Slice-5b/F1 handoff — green except the one known ❌: `etl/output/layer0_etl_v1.7.0.sql` MISSING (the **owed #604 `pg_dump`**, Neon egress blocked — a referenced *future* file, not a claimed-landed edit, so **not drift**). Branch correct, tree clean. No reconciliation needed.

## 2. Scope decision (the #608 remainder → did item 2)

Issue #608 had two items left after the F1 panel (#609): **(2)** the 2b round-trip form-state preservation; **(3)** the onboarding event-window panel (F5). I surfaced both with a recommendation (item 2 — it polishes an already-live flow with a clear CSP-safe approach; onboarding-surface for windows a brand-new athlete usually doesn't have yet is lower-value). **Andy chose item 2.** Item 3 deferred, #608 stays open.

## 3. The approach fork (the issue flagged it — Andy chose)

The issue itself flagged item 2 as *"blocked under strict CSP without inline JS → needs either a server-side stash of the in-progress window form or a CSP carve-out (worth a design call before building)."* Two options:
- **Option A (chosen) — server-side session stash.** When the athlete clicks "Add a new location," POST the in-progress form to a stash route that saves it in the session (consumed once on return) and hands off to `/locales/new`; the editor GET pops the draft and repopulates. **No CSP change.** Mirrors the locale flow's own session-stashed `return_to` (`locales._stash_return_to`).
- **Option B — a CSP carve-out for one inline script** to serialize the form into the round-trip client-side. Rejected — widens the strict-CSP surface for a single form.

Andy: **item 2, server-side stash.**

## 4. Implementation

- **`routes/profile.py`** — `_EVENT_WINDOW_DRAFT` session key + two helpers: `_stash_event_window_draft(form)` (persists `start_date / end_date / override_type / unavailable_locale / away_locale / brought_craft[] / notes`, stripped) and `_pop_event_window_draft()` (returns + clears — **consumed once**, so a stale draft can't leak onto a later unrelated visit). New `POST /event-windows/new-locale → event_window_new_locale_route`: stashes `request.form`, computes a safe `return_to` (`_safe_local_path`), and redirects to `locales.new_locale` with `return_to=` the event-windows page (itself carrying any plan-gen `return_to`). **Rule #15** `print('event_window_draft_stash: …')` on the hand-off. `event_windows()` GET now passes `draft=_pop_event_window_draft()`.
- **`templates/profile/event_windows.html`** — `{% set d = draft or {} %}` at the top of the add-window form (empty dict on a normal visit → every field renders blank as before). The "Add a new location" control changed from a plain `<a href>` into a **`<button type="submit" formnovalidate formaction="…event_window_new_locale_route">`** (POSTs the in-progress form to the stash route — no JS; `formnovalidate` lets it fire before the required date fields are filled). Every field repopulates: `value="{{ d.get(...) }}"` on the date/notes inputs, `selected` on the `override_type` / `unavailable_locale` / `away_locale` options, `checked` on the brought-craft checkboxes. **Implicit-submission guard:** because the new-location submit now precedes the visible "Add window" submit in tree order, a first **visually-hidden duplicate** of the primary submit (`<button type="submit" class="visually-hidden" tabindex="-1" aria-hidden="true">`) claims the Enter-key default so pressing Enter still adds the window instead of bouncing to `/locales/new`.

**The round-trip chain:** add-window form → (click "Add a new location") POST `/profile/event-windows/new-locale` (stash draft) → `/locales/new?return_to=/profile/event-windows?return_to=<plan-gen>` → save bounces back to `/profile/event-windows` → GET pops the draft → **form repopulated**, the new destination now selectable in the away dropdown.

**No DDL, no resolution change, no cache-key change, no vocab, no prompt-wording change.** The `athlete_event_windows_repo` + orchestrator overlay are **byte-identical** — only the capture surface moved. The `return_to` stays open-redirect-guarded.

## 5. Tests

- **`tests/test_redesign_locales_form_render.py`** — +3: `test_event_windows_form_repopulates_from_draft` (dates + notes `value=`, away constraint + destination `selected`, brought-craft `checked`); `test_event_window_draft_stash_is_consumed_once` (the stash preserves the multi-valued brought-craft list + strips notes; second pop returns None); extended `test_event_windows_capture_renders_away_create_link` for the link→`formaction` button change + the no-draft blank-field regression + the implicit-submission ordering (the visually-hidden primary submit precedes the new-location submit, anchored on the add form's action so the shell can't interfere).
- **Full suite: 2474 passed / 30 skipped** (+2 net from 2472; +3 new test fns, the link→button assertion folded into an existing test). The two `Layer3BEvidenceBasisWarning`s are pre-existing/unrelated. Touched route module imports clean.

## 6. CI / PR

- **PR [#610](https://github.com/ahorn885/exercise/pull/610) OPEN** (**Part of #608** item 2; #608 stays open for item 3). Created ready-for-review. Vercel preview deploy = **Ready**. GitHub Actions CI status to confirm on the feature commit (subscribed to PR activity).
- The feature commit is the code+tests; a second commit carries the bookkeeping (CURRENT_STATE + this handoff).

## 7. Owed Andy's hands

- **This PR owes nothing** — no DDL; reuses live routes/repo.
- (carried, #604) the live **`pg_dump`** → `etl/output/layer0_etl_v1.7.0.sql` (parts 1–2) + the Rule #12 sign-off / K3 decision for part 3 (see the Slice-5a handoff §2 + CARRY_FORWARD).
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

## 8. Next session

- **#608 item 3** (the last Slice-5b piece): the **onboarding event-window panel (F5)** — surface the capture during onboarding. **Design call:** the onboarding stepper is already 6 steps (Connect → Profile → Locations → Skills → Schedule → Target race) and a brand-new athlete usually has no travel/constraint windows yet, so a full gated 7th step is likely wrong — lean toward a lightweight optional link/card on an existing step. Surface the option before building.
- **#604 — vocab single-source-of-truth** (parked; still owed the live `pg_dump`; part 3 scaffolding retirement needs a Rule #12 sign-off + the K3 decision).
- (split out) #592 race-location terrain/weather; #593 reduced-volume travel days.

### 8.1 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — WS-H block + the #604 entry. 4. This handoff. 5. `designs/Event_Windows_Design_v1.md` §6/§F1/§F5 + issue #608. 6. `./scripts/verify-handoff.sh`.

---

## 9. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Draft stash helpers | `routes/profile.py` | `_EVENT_WINDOW_DRAFT`; `def _stash_event_window_draft(form)`; `def _pop_event_window_draft()` |
| Stash hand-off route | `routes/profile.py` | `@bp.route('/event-windows/new-locale', methods=['POST'])`; `def event_window_new_locale_route()`; `redirect(url_for('locales.new_locale', return_to=back))`; Rule #15 `event_window_draft_stash:` print |
| Draft into render ctx | `routes/profile.py` | `event_windows()` passes `draft=_pop_event_window_draft()` |
| Form repopulation | `templates/profile/event_windows.html` | `{% set d = draft or {} %}`; `value="{{ d.get('start_date', '') }}"`; `selected if … else ''`; `checked if c.slug in bc`; the `formaction`/`formnovalidate` "Add a new location" submit; the `visually-hidden` primary-submit duplicate |
| Tests | `tests/test_redesign_locales_form_render.py` | `test_event_windows_form_repopulates_from_draft`; `test_event_window_draft_stash_is_consumed_once`; updated `test_event_windows_capture_renders_away_create_link` |
| Suite | — | 2474 passed / 30 skipped |
| CI / PR | — | PR #610 OPEN (Part of #608 item 2; #608 open for item 3); Vercel preview deploy Ready; GH Actions CI to confirm |
| Owed | — | This PR owes nothing (no DDL); #604 `pg_dump` + the T3-refresh re-verify carried |
