# V5 Implementation — WS-H: Event Windows — Slice 5b: onboarding event-window panel (F5, #608 item 3) — Closing Handoff

**Session:** Same session as #608 item 2; Andy: *"merge and keep going."* Merged item 2 (PR #610), then shipped the **last item of the Event-Windows arc** — the **onboarding event-window panel (F5)**. **Andy chose (via `AskUserQuestion`) a lightweight optional card** on an existing onboarding step (over a gated 7th step, or closing the item as low-value). **No DDL / no prompt / no vocab / no cache-key change** — reuses the live `/profile/event-windows` editor + routes; only adds an onboarding entry point + generalizes the editor's back-link label.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice5b_FormStatePreservation_2026_06_14_Closing_Handoff_v1.md` (#608 item 2 / the 2b round-trip form-state stash, PR #610 merged + live).
**Branch:** `claude/plan-gen-review-panel-mqah8e`.
**Spec/arc:** `designs/Event_Windows_Design_v1.md` §6 (Slice 5 "capture UX polish") + §F5 ("full panel on profile + onboarding"). No separate spec (UX wiring, no DDL / no resolution change / no vocab / no trigger — the design line + issue [#608](https://github.com/ahorn885/exercise/issues/608) are the spec). **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. **This is #608 item 3 of 3 — once merged, #608 is fully done → CLOSE.**

---

## 1. Session-start verification (Rule #9)

This item ran inside the same session as item 2 (no fresh session-start). The session began with a green Rule #9 sweep against the Slice-5b/F1 handoff (the one ❌ is the known-owed #604 `pg_dump`, not drift). Branch correct, tree clean after each merge.

## 2. Scope decision (the #608 remainder → did item 3, the last)

After item 2 merged, item 3 (onboarding F5) was the only remaining #608 item. I surfaced the placement fork (Trigger #5) rather than pick silently.

## 3. The placement fork (Andy chose)

F5 ratified *that* event-window capture surfaces in onboarding; *how* had a real fork:
- **Option A (chosen) — lightweight optional card/link** on an existing step. Leanest; keeps onboarding short; a brand-new athlete usually has no travel/indoor windows yet, so it stays out of any gate. Reuses the live editor.
- **Option B — a dedicated gated 7th onboarding step** (Connect → Profile → Locations → Skills → Schedule → **Event windows** → Target race). More prominent but lengthens setup for windows most new athletes don't have.
- **Option C — close #608 item 3 as low-value** (the profile page + the F1 plan-gen review panel already cover capture/review).

Andy: **Option A.** Host step = **Locations** (chosen over Schedule, which the option text named as an example): Locations is structurally a card-`stack` with a separate Continue (Schedule is one big `<form>`, awkward to splice a card into), and conceptually an away window reuses the locales built on that step.

## 4. Implementation

- **`templates/onboarding/locales.html`** — a new **"● Optional · event windows"** `<section class="card card-pad">` between the locations list and the `onb-nav`: copy explaining date-bounded travel/indoor/closed-locale windows + a **"Set up event windows"** link (`btn btn-ghost btn-sm`) → `url_for('profile.event_windows', return_to=url_for('onboarding.locales'))`. Explicitly **not** part of the WS-C home-location gate — it never blocks Continue.
- **`routes/profile.py`** — new `_event_windows_return_label(return_to)`: returns **`'setup'`** when `return_to` starts with `/onboarding`, else **`'plan generation'`** (default). `event_windows()` GET hoists `return_to = _safe_local_path(request.args.get('return_to'))` to a local and passes `return_to_label=_event_windows_return_label(return_to)`. Deriving the label from `return_to` (rather than threading a separate query/form param) keeps it **consistent across the add/delete redirects**, which preserve `return_to` but would drop a standalone label.
- **`templates/profile/event_windows.html`** — the round-trip banner now reads `← Back to {{ return_to_label or 'plan generation' }}` (default preserves the plan-gen wording + back-compat for direct template renders).

**The onboarding round-trip:** Locations step → "Set up event windows" → `/profile/event-windows?return_to=/onboarding/locales` (banner "← Back to setup") → add/delete preserve `return_to` (banner stays "setup") → "Back to setup" → Locations step → Continue.

**No DDL, no resolution change, no cache-key change, no vocab, no prompt-wording change.** Reuses the live editor + repo untouched.

## 5. Tests

- **`tests/test_redesign_onboarding_render.py`** — extended `test_locales_render` (real GET route, fake DB) to assert the optional card + the "Set up event windows" link + the `/profile/event-windows?return_to=` round-trip.
- **`tests/test_redesign_locales_form_render.py`** — +1: `test_event_windows_back_link_label_reflects_origin` (the `_event_windows_return_label` helper: `/onboarding/…`→'setup', `/plans/…`→'plan generation', None→default; + a template render with `return_to_label='setup'` asserting "Back to setup").
- **Full suite: 2475 passed / 30 skipped** (+1 from 2474). The two `Layer3BEvidenceBasisWarning`s are pre-existing/unrelated.

## 6. CI / PR

- **PR OPEN** on `claude/plan-gen-review-panel-mqah8e` (created this session for item 3; **Part of #608** item 3/3). Created ready-for-review.
- This handoff + the CURRENT_STATE roll are the bookkeeping commit on top of the item-3 code commit.

## 7. Owed Andy's hands

- **This PR owes nothing** — no DDL; reuses live routes/editor.
- (carried, #604) the live **`pg_dump`** → `etl/output/layer0_etl_v1.7.0.sql` (parts 1–2) + the Rule #12 sign-off / K3 decision for part 3.
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

## 8. Next session

- **CLOSE #608 (completed)** once this PR merges — all three Slice-5b items (F1 panel #609 / form-state #610 / onboarding F5) are done. The Event-Windows arc is complete.
- **#604 — vocab single-source-of-truth** (parked; still owed the live `pg_dump`; part 3 scaffolding retirement needs a Rule #12 sign-off + the K3 decision).
- New functionality (off-plan): #592 race-location terrain/weather; #593 reduced-volume travel days.

### 8.1 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — WS-H block + the #604 entry. 4. This handoff. 5. `designs/Event_Windows_Design_v1.md` §6/§F5 + issue #608. 6. `./scripts/verify-handoff.sh`.

---

## 9. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Onboarding card | `templates/onboarding/locales.html` | `● Optional · event windows`; `Set up event windows`; `url_for('profile.event_windows', return_to=url_for('onboarding.locales'))` |
| Back-link label helper | `routes/profile.py` | `def _event_windows_return_label(return_to)` → `'setup'` for `/onboarding`, else `'plan generation'`; `event_windows()` passes `return_to_label=` |
| Editor banner | `templates/profile/event_windows.html` | `← Back to {{ return_to_label or 'plan generation' }}` |
| Tests | `tests/test_redesign_onboarding_render.py`, `tests/test_redesign_locales_form_render.py` | extended `test_locales_render` (card + link); `test_event_windows_back_link_label_reflects_origin` |
| Suite | — | 2475 passed / 30 skipped |
| CI / PR | — | PR OPEN (Part of #608 item 3/3); on merge → close #608 completed |
| Owed | — | This PR owes nothing (no DDL); #604 `pg_dump` + the T3-refresh re-verify carried |
