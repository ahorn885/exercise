# D-73 Phase 5.2 Walkthrough V1 Coaching Retire + Delete Double-Confirm — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — closes Bucket A from Andy's 2026-05-21 second-pass manual walkthrough (post-RaceLocaleMapbox). Retires the v1 `/coaching/generate` surface that was polluting Andy's plan-gen UX via a stale nav link, and fixes the `data-confirm` double-prompt root cause in `static/app.js`.
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_RaceLocaleMapbox_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/serene-clarke-rsiWw` (harness-pinned; system-prompt rule forbids renaming so the abstract name stays. CLAUDE.md's scope-matching guidance loses to the stricter rule here).
**PR:** TBD — open as draft once pushed.
**Status:** 5 substantive files (3 deletions, 2 surgical edits). Tests 1441 unchanged; container-runnable subset 774 passed + 12 skipped — identical to predecessor baseline. No regressions. Net -655 lines.

---

## 1. Session-start verification (Rule #9)

`./aidstation-sources/scripts/verify-handoff.sh` ran clean against the RaceLocaleMapbox predecessor handoff. All §8 anchor claims verified on-disk. No drift. Predecessor merged to main via PR #127 (`94bebac`).

---

## 2. Session narrative

Andy ran a fresh manual walkthrough against the Vercel deployment and produced a ~20-item punch list spanning 5 themes: plan-gen UX confusion, location vocab issues, race-event creation gaps, a delete double-confirm, and a few 500s. Investigation:

- 4 of 6 plan-gen complaints (no race picker / `Goal finish time` + `Race Day Philosophy` repetitive / hardcoded location dropdown / `Remote control (headless API)` block) lived on the **v1 `/coaching/generate`** page reachable from `templates/base.html:74`'s "Generate with AI" nav link — NOT the v2 `/plans/v2/new` surface shipped 2026-05-21. CLAUDE.md strangler-fig sequencing flags v1 coaching as the replace-bucket; the nav link was the active leak.
- The double-confirm reproduced from `static/app.js`'s click+submit handler overlap: a click on `<button type="submit">` inside `<form data-confirm="...">` walks up the DOM, finds the form's `data-confirm`, fires `confirm()`, returns; then the form's submit event handler sees the SAME `data-confirm` and fires `confirm()` again.
- The 500s (plan-gen orchestration, `/locales/horn_s_house/edit` delete), terrain-checkbox persistence, race-event "None" prepending, terrain×discipline coupling, locale-vocab cleanup, and legacy hardcoded-locale wipe were grouped into Buckets B-E and deferred pending: Andy's Vercel logs (B) and Trigger #5 design conversations (C/D/E).

Andy ratified 2 D-decisions at `AskUserQuestion` gate:

- **D1** = Hard retire (over Soft-retire-with-302 + Just-nav-repoint). Killing the route + template eliminates the surface entirely; no risk of athletes finding it again via direct URL or bookmark. Keeps `/coaching/review`, `/coaching/clarify`, `/coaching/api/review`, `/coaching/chat`, `/coaching/preferences`, `/coaching/context` alive (still wired into `plans/view.html` AI-Review buttons + shared by /review's template).
- **D2** = Yes, fix double-confirm in this slice. Diagnosis matches Andy's report.

Implementation: 5 substantive files (3 deletions, 2 surgical edits). Net -655 LOC.

`/plan` Triggers fired: none. Bucket A is a mechanical cleanup; D1 was the only architectural call and it was sized small enough to handle at the AskUserQuestion gate without entering `/plan` mode.

`/plan` Triggers DEFERRED (Bucket B-E from the new punch list):

- **Bucket B** — 500s: plan-gen orchestration + `/locales/<slug>/delete` + locale terrain-checkbox persistence. Needs Andy's Vercel function logs or local repro to root-cause.
- **Bucket C** — terrain vocab cleanup (Time-of-Day / Social / Partner-presence / Generic / Climbing gym-vs-outdoor split / water-type expansion / locale-terrain vs Outdoor-Terrain merge / Cycling Trainer dedup). Trigger #5 (architecture) + Trigger #2 (vocab adds) + Trigger #3 (Layer 0 schema). Design pass owed.
- **Bucket D** — legacy hardcoded locales (home/hotel/partner/airport) wipe + free-text location field removal. Depends on C.
- **Bucket E** — race event creation: "None"-prepending on terrain dropdown + disciplines surfaced on creation + terrain↔discipline coupling. Trigger #5.

---

## 3. File-by-file edits

### 3.1 `templates/base.html` — re-point nav

Line 74: `url_for('coaching.generate')` → `url_for('plan_create.new_plan')`. "Generate with AI" nav link now lands athletes on the v2 surface that already (a) reads the target race from `race_events` instead of asking again, (b) has no hardcoded `TRIP_LOCALE_TYPES`, (c) has no headless-API disclosure block, (d) has no `Goal Finish Time` / `Race Day Philosophy` repeat.

### 3.2 `routes/coaching.py` — delete /generate + /api/generate

Removed:
- `@bp.route('/generate', methods=['GET', 'POST'])` + `def generate():` (lines 30-164 of pre-edit). 135 lines.
- `@bp.route('/api/generate', methods=['POST'])` + `@_csrf_exempt` + `def api_generate():` (lines 357-404 of pre-edit). 48 lines.

Net -187 lines. Module shrinks from 660 to 473.

Kept (still in active use):
- `TRIP_LOCALE_TYPES = ('home', 'hotel', 'partner', 'airport')` — `/review` POST still reads this (line 196 post-edit).
- `from routes.locales import athlete_locale_choices` — used by `/review` POST.
- `_csrf_exempt` decorator — applied to `/api/review`.
- `_check_api_key` helper — used by `/api/review` + `/clarify`.
- `/context`, `/review/<plan_id>`, `/api/review`, `/clarify`, `/chat/<plan_id>`, `/preferences`, `/preferences/<pref_id>/delete` routes.

Pre-edit comment on `TRIP_LOCALE_TYPES` mentioned "plan_travel.locale + Claude prompt construction" — still accurate; `/review`'s POST writes `plan_travel` rows. Left as-is.

### 3.3 `templates/coaching/generate.html` — delete file

471 lines deleted. Contained: `MULTISPORT_TYPES` lookup, target-event form with race_name/race_date/race_type/race_location/race_disciplines text inputs, Event-Day-Goals card (`goal_finish_time` + `goal_splits` + `goal_checkpoints`), Plan-Block card with hardcoded locale dropdown, Training-Parameters card, the `<summary>Remote control (headless API)</summary>` disclosure block + the `<pre><code>POST /coaching/api/generate ...</code></pre>` example, the `/coaching/clarify` `fetch()` pre-flight invocation.

`/coaching/clarify` itself stays alive because `templates/coaching/review.html:332` still calls it.

### 3.4 `templates/profile/edit.html` — bearer-token wording

Lines 347-348: `<code>/coaching/api/generate</code> and <code>/coaching/api/review</code>` → `<code>/coaching/api/review</code>` (sole surviving endpoint). One sentence collapsed.

### 3.5 `static/app.js` — bail at `<form>` boundary in click walker

Added `if (el.tagName === 'FORM') return;` at the top of the click-handler walker loop. Eliminates the double-prompt on `<form data-confirm="..."><button type="submit">` patterns by ceding form-level `data-confirm` ownership to the submit handler exclusively.

Behavior table after fix:
- `<form data-confirm="X"><button type="submit">` → click handler hits form, bails; submit handler reads `X`, prompts once. ✅
- `<button data-confirm="Y">` (no form OR `type="button"`) → click handler finds Y BEFORE hitting form, prompts once. ✅
- `<a data-confirm="Z" href="...">` → click handler finds Z, prompts once. ✅
- `<form>` (no data-confirm) `<button data-confirm="W">` → click handler finds W on button (before form), prompts once; submit handler sees form has no data-confirm, no prompt. ✅

Affected delete buttons (~20 sites): `plans/list.html`, `plans/view.html` (×2), `locales/list.html`, `locales/form.html`, `cardio/list.html`, `training/list.html`, `body/form.html`, `conditions/list.html`, `injuries/list.html`, `dashboard.html` (×4 complete/skip buttons), `profile/edit.html` (×3 — disconnect/delete-pref/revoke-token), `profile/_race_events_tab.html` (×2), `profile/race_event_edit.html` (×3), `rx/list.html`, `onboarding/route_locales.html`, `admin/dashboard.html`.

---

## 4. Code / tests

**Tests:** 1441 unchanged (no test files directly covered `/coaching/generate` or `/api/generate`; deletion didn't strand any tests).

Container-runnable subset: 774 passed + 12 skipped in ~1.7s (identical to predecessor baseline).

Run reproducer (same set as predecessor):

```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                    tests/test_race_events_repo.py \
                    tests/test_race_events_invalidation.py \
                    tests/test_onboarding_race_events.py \
                    tests/test_layer4_context.py tests/test_layer4_payload.py \
                    tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                    tests/test_layer4_race_week_brief.py \
                    tests/test_plan_sessions_repo.py \
                    tests/test_routes_ad_hoc_workouts.py \
                    tests/test_routes_plan_create.py \
                    tests/test_nl_parser.py \
                    tests/test_routes_plan_refresh.py \
                    tests/test_nl_parser_smoke.py \
                    tests/test_routes_dashboard.py \
                    tests/test_routes_admin.py \
                    tests/test_layer3_cached_wrappers.py \
                    tests/test_routes_race_events.py
# 774 passed, 12 skipped
```

**Python syntax check:** `python3 -m py_compile routes/coaching.py` passes.

**Template parse-check:** `Environment(loader=FileSystemLoader('templates')).get_template(t) for t in ['base.html', 'profile/edit.html']` parses cleanly.

**Inline-script nonce sweep** (PR #126 anchor): `grep -rnE '<script\b' templates/ | grep -v 'nonce="{{ csp_nonce' | grep -v 'src='` returns empty. Deleting `templates/coaching/generate.html` removed 3 inline scripts (all already nonce-protected); no template-side regression.

**No-regression confirmation:** All 774 pre-existing container-subset tests pass. Pre-existing tests in `tests/test_layer3a_builder.py::TestCacheWrapper` (7) + `tests/test_layer3b_builder.py::TestCacheWrapper` (7) remain pre-existing-circular-import-blocked from collection (same as predecessor).

**Coverage gap acknowledged:** JS behavior in `static/app.js` not unit-tested (no jsdom/playwright harness in this repo). Manual §5.0 verification is the path; jsdom harness flagged in CARRY_FORWARD as a future slice.

---

## 5. Manual §5.0 verification steps

For Andy's next manual walkthrough pass against the preview deployment or post-merge against main:

**Step 1 — Nav re-point.** Navigate to any page. Click the `Plans` dropdown in the top nav. Click `Generate with AI`. Confirm the URL is `/plans/v2/new` (not `/coaching/generate`); the page renders the v2 `plan_create.new_plan` form (single plan-start-date input + read-only target-race summary card + optional alert when no target race is set).

**Step 2 — v1 routes deleted.** Navigate directly to `/coaching/generate` and `/coaching/api/generate` (POST via browser dev tools or curl). Both should return 404. `/coaching/review/<plan_id>`, `/coaching/clarify`, `/coaching/api/review`, `/coaching/chat/<plan_id>`, `/coaching/preferences` should still respond (200 / 401 depending on auth).

**Step 3 — AI Review still wired.** Navigate to `/plans/<plan_id>` for any v1 plan. Confirm the `AI Review` button (in the header + footer) still appears and links to `/coaching/review/<plan_id>`. Click it; confirm the review form renders normally. The `/coaching/clarify` pre-flight fetch on the notes field still fires (open browser network tab and watch when typing).

**Step 4 — Bearer-token docs.** Navigate to `/profile/edit?tab=api`. Confirm the description now reads "Bearer tokens for headless access to `/coaching/api/review`. Send as `Authorization: Bearer <token>`…" (no mention of `/coaching/api/generate`).

**Step 5 — Delete double-confirm fixed.** On `/plans/`, click `[Delete]` on any non-archived plan card. Confirm: exactly ONE browser confirm() dialog appears ("Delete <name>? This cannot be undone."). Click OK. Confirm: the plan is deleted, page reloads, no second dialog. Repeat on `/locales/` (`[Delete]` on a non-legacy location), `/injuries/` (delete an injury), `/training/` (delete a strength entry), `/cardio/` (delete a cardio entry). All should single-prompt.

**Step 6 — Plain-button data-confirm.** On `/dashboard` Today's Workouts section, click `[Complete]` or `[Skip]` on a today-due workout. Single prompt ("Mark as complete?" / "Skip this workout?"). Confirm OK, workout marks. (This pattern uses `<form data-confirm><button type="submit">` — same as deletes.)

Captured as 6 new steps in `CARRY_FORWARD.md` "Manual §5.0 walkthrough" section.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Remaining Buckets B-E from Andy's 2026-05-21 second-pass walkthrough**, in priority order:

1. **Bucket B — 500s + persistence bugs.** Three discrete issues, each needs Andy's repro/logs first:
   - Plan-gen 500 on POST to `/plans/v2/new`: `plan_create.new_plan` catches `OrchestrationError` + `Layer4InputError/OutputError` but anything else bubbles to 500. Likely Vercel 60s timeout (Pattern A is 30-60s); could also be DB error, generic exception, etc. **Action**: pull Vercel function logs for the failing request; if timeout, consider chunking the orchestration or moving to a job-queue pattern; if exception, add a catch-all handler with telemetry.
   - `/locales/horn_s_house/edit` delete 500: probably FK constraint or missing row (the slug has apostrophe→underscore transform). **Action**: repro locally with a similar slug; check `delete_locale` handler at `routes/locales.py:1127`.
   - Locale terrain checkboxes don't persist: the POST is parsed by `_parse_locale_terrain` at `routes/locales.py:50` and stored via the `_edit_legacy_locale` / `_edit_shared_locale` flow. **Action**: trace one round-trip end-to-end; suspect either the SQL UPDATE isn't writing or `_hydrate_locale_terrain_ids` isn't reading back.

2. **Bucket E — race event creation surface fixes.** ~3 sub-items:
   - "None" prepending on terrain dropdown: check `layer0.terrain_types` seed data for a literal "None" row OR the `_race_terrain_editor.html` partial's `— Pick terrain —` placeholder rendering.
   - Disciplines on race event creation page: currently absent. Trigger #5 — design where they go (multi-select alongside terrain? separate card?).
   - Terrain-↔-discipline coupling: currently race_terrain is a flat `[{terrain_id, pct}]` list per race. Coupling to discipline (e.g., "Singletrack — for the Running leg / Flat Water — for the Packraft leg") is a schema change.

3. **Bucket C — terrain vocab cleanup.** Big design slice. ~10 sub-items in Andy's list, each requires:
   - Trigger #3 (Layer 0 schema): add/remove `layer0.terrain_types` rows.
   - Trigger #2 (vocab adds): adding new water-type rows (still / moving / whitewater / ocean) hits the no-padding rule.
   - Trigger #5 (architecture): merging "Terrain accessible from this location" with the "Outdoor & Terrain" equipment category fieldset crosses the schema boundary between `layer0.terrain_types` (terrain vocab) and `layer0.equipment_items` (equipment vocab).

4. **Bucket D — legacy locale cleanup.** ~2 sub-items:
   - Wipe hardcoded `LOCALES = ('home','hotel','partner','airport')` slots from `routes/locales.py`. Cross-layer impact: `TRIP_LOCALE_TYPES` (`/coaching/review`), `coaching/review.html`, `routes/coaching.py:locales/refresh_from_mapbox` route conventions, prior `disclosure_acknowledgments` rows, athlete_locale_choices callers.
   - Remove free-text city/notes manual-entry path now that Mapbox is the canonical anchor.

### 6.2 Alternative pivots

If Bucket B blocked on Andy's logs and C-E need design conversations not yet ready:

- **#8 "locales" → "locations" rename** (~9 templates, mechanical, no Triggers) — predecessor's §6.1 carry-forward. Lowest-risk highest-visibility candidate.
- **#6 + #4 paired injury form refresh** (~6-8 files; Trigger #5 fires on `BODY_PART_CONSTRAINTS` mapping design).
- **#2b LLM site-parse runtime** (~4-6 files; Trigger #2 fires on prompt design first).
- **Flask test_client integration tests for the 4 RaceLocaleMapbox endpoints** (~150 LOC follow-on from predecessor §6.3 forward-pointer).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Buckets B-E live here as the active punch list).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_V1CoachingRetire_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Forward-pointer (JS test coverage):** No jsdom/playwright harness in this repo, so the `static/app.js` double-confirm fix is verified only via manual §5.0 step 5+6. If JS regressions accumulate, a small jsdom harness (~150 LOC) would close the gap.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Hard-retire `/coaching/generate` + `/api/generate` (over Soft-retire-with-302 + Just-nav-repoint) | Andy at AskUserQuestion gate | Killing the route + template eliminates the surface entirely; no risk of bookmarks/direct-URL re-discovery. CLAUDE.md strangler-fig sequencing flags v1 coaching as the replace-bucket, and the v2 plan_create already covers the same job better. Keeps the rest of `/coaching/*` intact (`/review` still wired to `plans/view.html:32, 76` AI-Review buttons; `/clarify` still used by `review.html`; `/api/review` still bearer-token-accessible; `/chat`, `/preferences`, `/context` untouched). |
| **D2** | JS click walker bails at `<form>` boundary (over removing the click handler entirely) | Claude (implementation), Andy confirmed diagnosis | Single-line fix preserves the existing `<a data-confirm>` / `<button data-confirm>` patterns while ceding form-level `data-confirm` ownership to the submit handler. Removing the click handler entirely would have broken anchor + non-submit button patterns. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| Nav `Generate with AI` re-pointed | ✅ `grep -n "coaching.generate" templates/base.html` returns 0 |
| `templates/base.html` references `plan_create.new_plan` | ✅ `grep -n "plan_create.new_plan" templates/base.html` returns 1 hit at line 74 |
| `routes/coaching.py` no longer defines `generate()` | ✅ `grep -n "^def generate" routes/coaching.py` returns 0 |
| `routes/coaching.py` no longer defines `api_generate()` | ✅ `grep -n "^def api_generate" routes/coaching.py` returns 0 |
| `routes/coaching.py` retains `TRIP_LOCALE_TYPES` (used by /review) | ✅ `grep -n "TRIP_LOCALE_TYPES" routes/coaching.py` returns 3 hits (def + /review use + comment) |
| `routes/coaching.py` retains `/review`, `/clarify`, `/api/review`, `/chat`, `/preferences`, `/context` | ✅ `grep -n "@bp.route" routes/coaching.py` returns 8 routes (all surviving) |
| `templates/coaching/generate.html` deleted | ✅ `ls templates/coaching/` shows only `review.html` |
| `templates/profile/edit.html` bearer-token text references only `/coaching/api/review` | ✅ `grep -n "/coaching/api/" templates/profile/edit.html` returns 1 hit |
| `static/app.js` click walker bails at `<form>` | ✅ `grep -n "tagName === 'FORM'" static/app.js` returns 1 hit |
| No `coaching.generate` references anywhere in templates/routes/static/tests | ✅ `grep -rn "coaching\\.generate\\|coaching/generate\\|coaching\\.api_generate\\|coaching/api/generate" templates/ routes/ static/ tests/` returns 0 |
| No inline `<script>` blocks missing nonce in `templates/` | ✅ `grep -rnE '<script\\b' templates/ \\| grep -v 'nonce="{{ csp_nonce' \\| grep -v 'src='` returns empty |
| `routes/coaching.py` Python syntax valid | ✅ `python3 -m py_compile routes/coaching.py` passes |
| Edited templates parse cleanly via Jinja2 | ✅ `python3 -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); [env.get_template(t) for t in ['base.html', 'profile/edit.html']]"` |
| Tests 1441 unchanged | ✅ pytest count |
| Container-runnable subset 774 passed + 12 skipped | ✅ pytest run |
| `CURRENT_STATE.md` last-shipped pointer flipped to V1CoachingRetire handoff | ✅ |
| `CARRY_FORWARD.md` Bucket A annotated ✅ Shipped; Buckets B-E carried as the next punch-list cohort | ✅ |
| PR opened as draft + CI green (Vercel deploy success) | ⏸ pending push |

---

## 9. Files shipped this session

**Substantive (5 files; at ceiling):**

1. `templates/base.html` — nav line 74 re-pointed from `coaching.generate` to `plan_create.new_plan`. +1 / -1.
2. `routes/coaching.py` — `generate()` (135 lines) + `api_generate()` (48 lines) deleted. Net -187 lines.
3. `templates/coaching/generate.html` — DELETED (471 lines).
4. `templates/profile/edit.html` — bearer-token wording collapsed. +1 / -2.
5. `static/app.js` — `if (el.tagName === 'FORM') return;` added to click walker + 3-line comment. +4 / -0.

**Bookkeeping (3 files):**

6. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; session narrative appended.
7. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket A annotated ✅ Shipped; Buckets B-E carried as the next punch-list cohort; 6-step §5.0 walkthrough scenario added.
8. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_V1CoachingRetire_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket A v1 `/coaching/generate` retirement + delete double-confirm shipped 2026-05-21** ✅ — nav re-pointed, route + template deleted, double-prompt fixed via single-line `<form>`-boundary bail in `static/app.js`.
- **Bucket B 500s + persistence bugs carried forward** — needs Andy's Vercel logs for plan-gen 500; local repro for `/locales/<slug>/edit` delete 500 + terrain-checkbox persistence bug.
- **Bucket C terrain vocab cleanup carried forward** — Trigger #5 design pass first; ~10 sub-items.
- **Bucket D legacy locale cleanup carried forward** — depends on C.
- **Bucket E race event creation surface fixes carried forward** — Trigger #5 design pass on disciplines + terrain↔discipline coupling first; "None"-prepending is a smaller standalone fix.
- 1 new manual §5.0 walkthrough scenario added (6 steps: nav re-point + v1 routes deleted + AI Review still wired + bearer-token text + delete single-prompt + complete/skip single-prompt).
- 1 forward-pointer added: jsdom/playwright harness for `static/app.js` regression coverage (~150 LOC).
- Architect-recommended §6.1 forward move = **Bucket B (500s)** pending Andy's logs; alternatives include Bucket E (race-event surface fixes) or the predecessor's §6.1 candidates (#8 rename, #6+#4 injury form, #2b LLM site-parse runtime).

**End of handoff.**
