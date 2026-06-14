# V5 Implementation — WS-H: Event Windows — Slice 5b: plan-gen review/edit/append panel (F1) — Closing Handoff

**Session:** Picked up the Slice-5a handoff; Andy: *"check it out and continue working. I think 5b is next."* Shipped **Slice 5b** of the Event-Windows capture-UX arc: the **plan-gen review/edit/append panel (F1)** — the arc's last real UX piece. The athlete's standing event windows now surface **for review at plan generation** on the create form (`/plans/v2/new`), with an **"Add / edit event windows"** button that round-trips to the dedicated `/profile/event-windows` editor and returns to the create form. **Andy chose the shape in-chat: Option 1 — lean review on the create form + round-trip edit on the dedicated page** (over a fully-inline panel, which strict-CSP would saddle with a start-date-reset-on-every-edit wrinkle, since no inline JS can preserve the field across reloads). **No DDL / no prompt change / no vocab / no cache-key change** — reuses the existing windows repo + routes; only the capture/review surface moved.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice5a_CaptureUX_NavCraftLocale_2026_06_14_Closing_Handoff_v1.md` (Slice 5a nav reachability + craft↔locale relocation, PR #607 merged + live).
**Branch:** `claude/eventwindows-5a-capture-ux-2kzr5d` (harness-pinned name says "5a"; scope is **5b** — kept per the explicit "never push to a different branch" instruction; name mismatch is cosmetic).
**Spec/arc:** `designs/Event_Windows_Design_v1.md` §6 (Slice 5 = "capture UX polish") + §F1/§F5. No separate Slice-5b spec (UX wiring, no DDL / no resolution change / no vocab / no trigger — the design §F1 line + issue [#608](https://github.com/ahorn885/exercise/issues/608) are the spec). **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. **Epic #581 closed** (Slice 4); **#608 tracks the Slice-5b remainder** — this PR is **item 1 of 3**.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the Slice-5a handoff — green except one ❌: `etl/output/layer0_etl_v1.7.0.sql` MISSING. That is the **known-owed #604 `pg_dump`** (owed-Andy's-hands, Neon egress blocked) — a referenced *future* file, **not** a claimed-landed edit, so **not drift**. Branch correct, tree clean. Spot-checked the Slice-5a anchors on disk (`save_locale_crafts` @ `routes/locales.py:634`, the sidebar `event_windows` nav entry) — present. No reconciliation needed.

## 2. Scope decision (the #608 grab-bag → did the F1 panel, item 1 of 3)

Issue #608 (Slice-5b remainder) enumerates three items: **(1) plan-gen review/edit/append panel (F1)** — the largest, touches the plan-create flow; **(2) 2b round-trip start-date form-state preservation**; **(3) onboarding event-window panel (F5)**. Shipped **(1)** as this PR; **(2)+(3) deferred, #608 stays open** for them. None trip a stop-and-ask trigger (no DDL / no prompt / no vocab / no cross-layer change).

## 3. The design fork (Trigger #5 — surfaced to Andy, he chose)

F1 ratified *what* (a review/edit/append panel at plan generation, w/ inline new-location create); the *how* on the create flow had a real fork I surfaced in chat rather than pick silently:
- **Option 1 (chosen) — lean review on the create form + round-trip edit on the dedicated page.** The create form lists windows for review; editing/appending round-trips to `/profile/event-windows` (return_to back to create). Leanest create form; single source of truth for the editor; **no date-reset wrinkle**.
- **Option 2 — full inline panel on the create form** (closest to v1 `/coaching/review`). More faithful, but strict-CSP (`app.py` forbids inline JS) means each window add/remove reloads and **resets the chosen start date to today** — and bloats the create form. Rejected.

Andy: **"option 1."**

## 4. Implementation (Slice 5b)

- **`routes/plan_create.py`** — added `from athlete_event_windows_repo import load_event_windows`; `new_plan` GET now loads the athlete's **upcoming** windows (`[w for w in load_event_windows(db, uid) if w.end_date >= today]`) and passes `event_windows=` to `new_form.html`. (POST path unchanged — generation flow untouched.)
- **`routes/profile.py`** — two new module-level helpers next to the event-windows routes: `_safe_local_path(value)` (honors a `return_to` only when it's a local same-site path — `startswith('/') and not startswith('//')` — open-redirect guard, mirrors `routes/locales._stash_return_to`) and `_event_windows_redirect(return_to)` (redirects to `profile.event_windows` **preserving** a safe `return_to`; `url_for` drops a None query arg → a standalone visit lands on the bare page unchanged). `event_windows()` GET now passes `return_to=_safe_local_path(request.args.get('return_to'))`. `add_event_window_route` + `delete_event_window_route` read `request.form.get('return_to')` and return `_event_windows_redirect(...)` on every exit (incl. the two error redirects in add).
- **`templates/plan_create/new_form.html`** — new "● Event windows" review section (between the start-date/race grid and "What you'll get"): a table of `event_windows` (dates + constraint label reusing the `event_windows.html` conditional + brought-craft) when present, else a "No upcoming event windows — declare any travel/indoor ranges" prompt; both render an **"Add / edit event windows"** link → `url_for('profile.event_windows', return_to=url_for('plan_create.new_plan'))`.
- **`templates/profile/event_windows.html`** — a `{% if return_to %}` "← Back to plan generation" hint banner at the top of the stack; a hidden `return_to` field on the add-window form **and** each per-row delete form (`value="{{ return_to or '' }}"`); and the inline new-location create link now nests `return_to` (`url_for('locales.new_locale', return_to=url_for('profile.event_windows', return_to=return_to))`) so creating a destination mid-round-trip still lands back in the chain → create.

**The round-trip chain:** create form → `/profile/event-windows?return_to=/plans/v2/new` → (add/delete preserve return_to → page keeps the back-link) and/or (inline `/locales/new?return_to=/profile/event-windows?return_to=/plans/v2/new` → save bounces back to the editor, still in-chain) → "Back to plan generation" → create form.

**No DDL, no resolution change, no cache-key change, no vocab, no prompt-wording change.** The `athlete_event_windows_repo` (load/add/delete/evict) + the orchestrator overlay are **byte-identical** — only the capture/review surface moved.

## 5. Tests

- **`tests/test_redesign_locales_form_render.py`** — +5: `test_event_windows_renders_plan_gen_round_trip_when_return_to_set` (back-link + return_to threaded through forms + nested locale link); extended `test_event_windows_capture_renders_away_create_link` with a no-`return_to` assertion (banner hidden standalone); `test_plan_create_form_lists_event_windows_for_review` + `test_plan_create_form_empty_event_windows_prompts_declaration` (the create-form panel populated + empty, CSP-clean, the edit link with return_to); `test_event_windows_return_to_rejects_non_local_paths` (the `_safe_local_path` open-redirect guard — accepts `/path`, rejects `//host`, `https://host`, `''`, `None`).
- **Full suite: 2472 passed / 30 skipped** (+4 net from 2468; the +5 minus the byte-shared craft-catalog ctx). The two `Layer3BEvidenceBasisWarning`s are pre-existing/unrelated. Touched route modules import clean (no circular import from the new top-of-module `load_event_windows` import in `plan_create.py`).

## 6. CI / PR

- **PR [#609](https://github.com/ahorn885/exercise/pull/609) squash-merged to `main`** (**Part of #608** item 1 of 3; #608 stays open for items 2–3). **GitHub Actions CI green** (run #279 on the feature commit, #280 on the bookkeeping commit); **Vercel deploy = success**. No review threads.
- Andy directed the merge in-session ("do the bookkeeping. update github. merge.").

## 7. Owed Andy's hands

- **Slice 5b (PR #609) owes nothing** — no DDL; reuses live routes/repo. PR #609 merged this session.
- (carried, #604) the live **`pg_dump`** → `etl/output/layer0_etl_v1.7.0.sql` (parts 1–2) + the Rule #12 sign-off / K3 decision for part 3 (see the Slice-5a handoff §2 + CARRY_FORWARD).
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

## 8. Next session

- **#608 items 2–3** (the Slice-5b remainder): (2) the **2b round-trip start-date form-state preservation** — when the athlete bounces to `/locales/new` mid-window-capture and returns, preserve the partially-filled window form (strict-CSP-blocked without inline JS — needs a server-side stash of the in-progress form, or a CSP carve-out; flag the tradeoff); (3) the **onboarding event-window panel (F5)**.
- **#604 — vocab single-source-of-truth** (parked; still owed the live `pg_dump`; part 3 scaffolding retirement needs a Rule #12 sign-off + the K3 decision).
- (split out) #592 race-location terrain/weather; #593 reduced-volume travel days.

### 8.1 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — WS-H block + the #604 entry. 4. This handoff. 5. `designs/Event_Windows_Design_v1.md` §6/§F1/§F5 + issue #608. 6. `./scripts/verify-handoff.sh`.

---

## 9. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Create-form windows load | `routes/plan_create.py` | `from athlete_event_windows_repo import load_event_windows`; `event_windows = [w for w in load_event_windows(db, uid) if w.end_date >= today]`; `event_windows=event_windows` render kwarg |
| return_to helpers | `routes/profile.py` | `def _safe_local_path(value)` (local-path guard); `def _event_windows_redirect(return_to)` |
| Edit-route round-trip | `routes/profile.py` | `event_windows()` passes `return_to=_safe_local_path(request.args.get('return_to'))`; add/delete return `_event_windows_redirect(...)` |
| Create-form review panel | `templates/plan_create/new_form.html` | `● Event windows`; `url_for('profile.event_windows', return_to=url_for('plan_create.new_plan'))`; `Add / edit event windows` |
| Editor round-trip UI | `templates/profile/event_windows.html` | `Back to plan generation`; `name="return_to"` on add + delete forms; nested `return_to` on the `new_locale` link |
| Tests | `tests/test_redesign_locales_form_render.py` | `test_plan_create_form_lists_event_windows_for_review`; `test_event_windows_renders_plan_gen_round_trip_when_return_to_set`; `test_event_windows_return_to_rejects_non_local_paths` |
| Suite | — | 2472 passed / 30 skipped |
| CI / PR | — | PR #609 squash-merged to `main` (Part of #608 item 1/3; #608 open for items 2–3); GH Actions CI green (runs #279/#280); Vercel deploy green; no review threads |
| Owed | — | Slice 5b owes nothing (no DDL); #604 `pg_dump` + the T3-refresh re-verify carried |
