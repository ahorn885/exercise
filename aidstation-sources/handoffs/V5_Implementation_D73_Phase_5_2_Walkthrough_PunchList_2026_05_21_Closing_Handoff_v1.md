# D-73 Phase 5.2 Manual Walkthrough Punch-List Fixes — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side polish — Andy's 2026-05-21 manual walkthrough surfaced a 10-item punch list; this slice closes 5 of them plus 2 silent-fail bugs discovered during diagnosis. Template-only slice.
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Layer3_Caching_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/layer3-caching-implementation-GgIwX` (harness-pinned; the handoff Andy linked at session start was the Layer 3 caching handoff but that work was already shipped via PR #125, so this session pivoted to fixing the issues he surfaced during his Neon walkthrough of the just-shipped surface)
**PR:** #126 — `Walkthrough punch-list fixes — #3, #5, #9, #10 + silent-fail nonces`
**Status:** 8 template files (2 commits). No Python changes. Container-runnable test subset 752 passed + 12 skipped — unchanged from predecessor baseline.

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` ran clean against the Layer 3 Caching predecessor handoff. All §8 anchor claims verified on-disk. No drift.

Predecessor merged to main via PR #125 (`a380118`); the branch this session opens on was equal to `origin/main`. The Layer 3 caching slice is fully landed.

**Reconciliation note:** Clean. The user-linked entry-point (Layer 3 caching handoff) was the *closing* handoff for an already-merged slice — so this session pivoted to addressing Andy's manual walkthrough findings against that just-shipped surface.

---

## 2. Session narrative

Andy ran a manual walkthrough of the freshly-shipped Phase 5.2 caller-side surface and surfaced a 10-item punch list. Categorized at intake:

- **CRITICAL** (blocks testing): #10 `/coaching/generate` 500 on plan creation
- **HIGH**: #5 `/injuries` 500 on save; #9 plan-list page defaults to "Import Plan" not "Create with AI"
- **MEDIUM** (UX): #1 race-event "locale" should be a Mapbox-backed anchor (city/state/address), not a saved-locale dropdown; #3 `[+ Add terrain]` button does nothing; #4 injury body_part vocab has Left/Right doubled despite separate side field; #6 movement-constraints not dynamic per body-part; #7 can't delete locations
- **LOW**: #2 no race-URL field on race events (Andy wants LLM site-parse pre-fill of rules/equipment/terrain, but the URL column itself is the prerequisite); #8 user-facing "locales" should read "locations"

Triage approach:

1. **#10 + #5 needed Vercel tracebacks** — server errors that can't be diagnosed from code alone. Asked Andy for the traceback portion via the Vercel dashboard Runtime Logs.
2. **#9 was mechanical** — could be fixed without server-side info; started in parallel.
3. **#3 + #1 + #2 + #4 + #6 + #7 + #8 each have a code-side surface I could investigate** — recon completed during the wait for tracebacks.

Pre-design surface survey:

- **#3 root cause = CSP** (this turned out to be the highest-leverage find). `templates/_race_terrain_editor.html:82` has an inline `<script>` block with no `nonce="{{ csp_nonce() }}"` attribute. The app's CSP enforces `script-src 'self' 'nonce-...'` with no `'unsafe-inline'` (see `app.py:340-369`), so the browser silently blocks the IIFE and the event listeners never bind. The `[+ Add terrain]` button does nothing because no click handler ever attaches.
- **Bonus find — same root cause bites 2 other inline scripts** in recently-shipped templates: `templates/plans/v2/refresh.html:125` (cap-exceeded modal auto-open, shipped FreqCaps) + `templates/workouts/suggestion_view.html:134` (T1 hook modal auto-open, shipped LogThis+T1Hook). Both modals never auto-opened in production — the modal markup was present but the trigger script was inert. Andy may have noticed the T1 modal not firing post `[Log this workout]` and the cap-exceeded modal not firing on the 4th refresh attempt, but neither was on the punch list because they weren't visibly broken (the page rendered fine; the modal just didn't auto-show).
- **#9 mechanical**: `templates/plans/list.html` had only `[Import Plan]` as the CTA in both header and empty-state. The Phase 5.2 plan-create route at `/plans/v2/new` was not surfaced from the list page.
- **#7 surface**: `routes/locales.py:1127` has a `delete_locale` route, and `templates/locales/form.html:139-147` already renders a delete form gated on `is_deletable` — but the inline `onsubmit="return confirm(...)"` handler was also blocked by CSP (same script-src nonce policy), so the confirm dialog never fired. `templates/locales/list.html` has no delete button at all — only Edit — so the delete UI is buried at the bottom of an edit-form page and easy to miss.

Andy provided Vercel tracebacks for #10 + #5:

- **#10 traceback**: `templates/coaching/generate.html:354` `Object of type Undefined is not JSON serializable`. Root cause: `MULTISPORT_TYPES` was defined via `{% set %}` inside `{% block content %}` at line 30, but referenced at line 354 inside `{% block scripts %}` — Jinja block-scoping makes the variable `Undefined` in the second block, and `| tojson` raises `TypeError` on `Undefined`. (This was the legacy v1 `/coaching/generate` route, not the new `/plans/v2/new` — Layer 3 caching wiring was not the cause.)
- **#5 traceback**: `templates/injuries/list.html:36` `'>=' not supported between instances of 'str' and 'int'`. Root cause: `injury_log.severity` migrated INTEGER → 6-value TEXT enum in D-73 Phase 2.2 (per `init_db.py:1505-1525` + `athlete.KNOWN_INJURY_SEVERITIES`), but the list template still did integer comparison (`>= 4`, `== 3`, `/5` scale).

Implementation: 8 template edits across 2 commits.

**Commit 1 (`4b2a019`) — 6 templates, addresses #3 / #5 / #9 / #10 + 2 silent-fail nonces:**

1. `templates/_race_terrain_editor.html:82` — added `nonce="{{ csp_nonce() }}"` to inline `<script>`. Inline comment explains the load-bearing nature of the nonce per CSP.
2. `templates/plans/v2/refresh.html:125` — same nonce fix (capExceededModal auto-open).
3. `templates/workouts/suggestion_view.html:134` — same nonce fix (t1HookModal auto-open).
4. `templates/plans/list.html` — added primary `[+ Create with AI]` CTA linking to `plan_create.new_plan` (`/plans/v2/new`) in both header and empty-state; Import demoted to `outline-secondary`.
5. `templates/injuries/list.html:35-43` — replaced integer-threshold severity badge logic with enum-aware mapping (`Acute` / `Post-surgical` → `bg-danger`; `Recovering` / `Chronic-Managed` / `Structural-Permanent` → `bg-warning text-dark`; `Resolved` → `bg-secondary`). Removed `/5` suffix (no longer a numeric scale).
6. `templates/coaching/generate.html` — lifted `{% set MULTISPORT_TYPES = [...] %}` to template scope (above `{% block content %}`) with a Jinja comment explaining the block-scoping fix. `ALL_DISCIPLINES` + `DAYS` left inside `{% block content %}` since they're only referenced there.

**Commit 2 (`1365b0e`) — 2 templates, addresses #7:**

7. `templates/locales/list.html` — each non-legacy locale card now has a `[Delete]` button next to `[Edit]` in the card header, gated `if not is_legacy and p` (only athlete-created custom locales; legacy slots `home`/`hotel`/`partner`/`airport` remain non-deletable per the existing route guard at `routes/locales.py:1147`). Uses the canonical `data-confirm="..."` pattern from `static/app.js`.
8. `templates/locales/form.html:139-146` — converted the bottom-of-form delete from `onsubmit="return confirm(...)"` to `data-confirm="..."` so the confirm dialog actually fires through CSP. Also relabeled button text + dialog copy from "locale" to "location" to start aligning with Andy's user-facing terminology preference (full `/locales` → "Locations" rename queued as a separate slice per #8).

`/plan` Triggers fired: **none**. Triggers #1 / #2 / #3 / #4 / #5 / #6 did not fire — pure bug-fix slice with no LLM-prompt design, vocab additions, cross-layer schema, HITL gate, architectural alternatives, or architecture promotion.

`/plan` Triggers DEFERRED (for the remaining punch-list items):

- **#1 race locale → Mapbox** will need a Trigger #5 (architectural alternatives: mirror existing locale Mapbox flow vs. inline lat/lng-only vs. text-anchor-no-geocoding).
- **#2 race URL + LLM site-parse** will fire **Trigger #2** (LLM prompt design) and likely **Trigger #1** (form copy on the URL field). Prompt body needs its own design session before the runtime + caller-side ship.
- **#4 body_part vocab cleanup** will be folded into the §B onboarding form refresh (already tracked in `CARRY_FORWARD.md:54`).
- **#6 dynamic movement-constraints** will need a Trigger #5 (mapping design: which constraints apply to which body parts).
- **#8 "locales" → "locations"** is mechanical — no Triggers.

---

## 3. File-by-file edits

### 3.1 `templates/_race_terrain_editor.html` — CSP nonce fix (#3)

Added `nonce="{{ csp_nonce() }}"` to the inline `<script>` at line 82. Added a 3-line inline comment documenting the load-bearing nature of the nonce per CSP — without it, the IIFE registering the `[+ Add terrain]` click handler is silently blocked. No other changes; the JS logic itself was already correct.

### 3.2 `templates/plans/v2/refresh.html` — CSP nonce fix (silent T2/T3 cap-exceeded modal)

Added `nonce="{{ csp_nonce() }}"` to the inline `<script>` at line 125 that auto-opens `#capExceededModal` on the re-render after over-cap submission. Pre-fix, the modal markup rendered but never auto-opened — the athlete saw the form re-render with the in-textarea NL context preserved but no overlay explaining why submission didn't complete.

### 3.3 `templates/workouts/suggestion_view.html` — CSP nonce fix (silent T1 hook modal)

Added `nonce="{{ csp_nonce() }}"` to the inline `<script>` at line 134 that auto-opens `#t1HookModal` on `?just_logged=1` redirects. Pre-fix, the post-log T1 plan-check hook never auto-fired — athletes saw `Logged ✓` text under the workout card but no modal offering the T1 refresh.

### 3.4 `templates/plans/list.html` — primary [Create with AI] CTA (#9)

Header CTA pair (line 5-10): `[+ Create with AI]` (btn-primary, → `plan_create.new_plan`) + `[Import Plan]` (btn-outline-secondary, → `plans.import_plan`).

Empty-state CTA pair (line ~63-69): same two buttons, both larger size, centered. Andy's intent — defaults to creating a plan with AI when there's no plan yet — is satisfied via primary-vs-outline visual hierarchy.

### 3.5 `templates/injuries/list.html` — severity enum-aware badges (#5)

Replaced integer-threshold logic at line 36 with enum-aware mapping:

```jinja
{% if e.severity in ['Acute', 'Post-surgical'] %}
  <span class="badge bg-danger">{{ e.severity }}</span>
{% elif e.severity in ['Recovering', 'Chronic-Managed', 'Structural-Permanent'] %}
  <span class="badge bg-warning text-dark">{{ e.severity }}</span>
{% else %}
  <span class="badge bg-secondary">{{ e.severity }}</span>
{% endif %}
```

Severity → badge color follows the Layer 2D §5.3.4 verdict mapping (EXCLUDE → danger; ACCOMMODATE → warning; CLEAN/Resolved → secondary). Removed `/5` suffix since the column is no longer a 1-5 numeric scale.

### 3.6 `templates/coaching/generate.html` — Jinja block-scope fix (#10)

Moved `{% set MULTISPORT_TYPES = [...] %}` from inside `{% block content %}` (line 30) to template scope (line 7, between `{% block title %}` and `{% block content %}`). Added a 3-line Jinja comment explaining why the move was necessary (the variable is referenced inside `{% block scripts %}` at line 354 via `{{ MULTISPORT_TYPES | tojson }}`, and Jinja block-scoping made it `Undefined` across block boundaries).

`ALL_DISCIPLINES` and `DAYS` left inside `{% block content %}` since they're only referenced there (verified via `awk` + `grep` of the scripts block).

### 3.7 `templates/locales/list.html` — Delete button on list card (#7)

Added a delete form to the card header (line ~46-55) next to the existing Edit button, gated `if not is_legacy and p` (only renders for athlete-created custom locales that have a `locale_profiles` row). Uses the canonical `data-confirm="..."` pattern from `static/app.js` (CSP-compatible). Dialog copy: `Delete "<locale_name>"? Equipment overrides for this location will be removed too. This cannot be undone.`

### 3.8 `templates/locales/form.html` — CSP-compatible confirm (#7)

Converted the bottom-of-form delete form (line 141-146) from `onsubmit="return confirm(...)"` to `data-confirm="..."`. Pre-fix, the inline event handler was silently blocked by CSP `script-src 'self' 'nonce-...'` so the confirm dialog never fired — clicking `[Delete this locale]` would submit the form immediately. Now routes through the global handler at `static/app.js:43-55` which already covers `<form data-confirm="...">` for the canonical pattern. Also relabeled button text + dialog copy from "locale" to "location" (small step toward #8).

---

## 4. Code / tests

**Tests:** 1419 baseline preserved. No Python changes. Container-runnable subset 752 passed + 12 skipped — identical to predecessor handoff §4.

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
                    tests/test_layer3_cached_wrappers.py
# 752 passed, 12 skipped in ~1.5s
```

**Template parse-check:** Jinja2 `Environment(loader=FileSystemLoader('templates')).get_template(...)` exercised against all 8 touched templates. All parsed cleanly.

**No-regression confirmation:** All 738 pre-existing container-subset tests + 14 from the Layer 3 caching slice still pass. `tests/test_locales.py` 23/23 still passing post the locales template touches.

**Coverage gap acknowledged:** No tests added for the CSP nonce presence on inline `<script>` tags. Adding such a test would require either a Flask test-client + rendering of each affected route, OR a static-analysis sweep of all `<script>` tags in `templates/`. Skipped this session per the bug-fix slice scope; tracked as a forward-pointer below.

---

## 5. Manual §5.0 verification steps

For Andy's next manual walkthrough pass against the preview deployment (PR #126 Vercel preview at `exercise-git-claude-layer3-caching-i-d7f00f-andy-horns-projects.vercel.app`) or post-merge against main:

**Step 1 — Plan-list CTAs (#9).** Navigate to `/plans/` while logged in. Confirm: (a) header shows `[+ Create with AI]` (btn-primary, links to `/plans/v2/new`) + `[Import Plan]` (btn-outline-secondary, links to `/plans/import`); (b) if no plans exist, empty-state shows the same two buttons centered, with "Create a plan with AI" as the primary; (c) clicking `[+ Create with AI]` lands on the Phase 5.2 plan-create form with the read-only PGE 2026 target-race summary.

**Step 2 — Race terrain Add button (#3).** Navigate to `/profile/race-events/<pge_id>/edit`. Confirm: (a) `[+ Add terrain]` button renders below the existing terrain rows (or below the empty state); (b) clicking it appends a new row with a TRN-xxx select + percent input + Remove button; (c) clicking Remove on any row removes it; (d) browser dev-tools Network tab shows no CSP violation for the inline script (or check console — should be empty).

**Step 3 — Injury list page (#5).** Navigate to `/injuries`. Confirm: (a) page renders without 500; (b) each injury card shows a severity badge in the correct color (Acute/Post-surgical → red; Recovering/Chronic-Managed/Structural-Permanent → yellow; Resolved → gray); (c) no `/5` suffix anywhere; (d) submitting a new injury via `/injuries/new` redirects back to the list cleanly.

**Step 4 — Coaching generate page (#10).** Navigate to `/coaching/generate`. Confirm: (a) page renders without 500; (b) sport dropdown + framework_sport conditional behavior works (selecting one of `Triathlon` / `Duathlon` / `Adventure Race` / `Multisport` / `Pentathlon / Decathlon` / `Other multi-sport` reveals the multi-sport discipline checkboxes).

**Step 5 — Location delete UI (#7).** Navigate to `/locales/`. Confirm: (a) athlete-created custom locale cards (non-legacy slugs) now show a `[Delete]` button next to `[Edit]` in the card header; (b) clicking it pops a browser confirm dialog; (c) confirming actually deletes the locale and redirects to `/locales/`; (d) legacy slots (`home`/`hotel`/`partner`/`airport`) do NOT show a Delete button on either the list or edit pages; (e) on the edit form `/locales/<custom_slug>/edit`, the bottom-of-form `[Delete this location]` button also pops the confirm dialog correctly (pre-fix it submitted immediately without confirmation due to CSP block).

**Step 6 — Silent-fail modal flows now visible.** Bonus verification of the 2 nonce fixes:
- Log a workout via `/workouts/build` → `[Log this workout]` → confirm the T1 hook modal now auto-opens on the `?just_logged=1` redirect (pre-fix the page just rendered "Logged ✓" with no modal).
- Trigger a T1 refresh cap-exceeded (4th refresh in 24h) → confirm the cap-exceeded modal auto-opens on the form re-render (pre-fix the form re-rendered with no overlay).

Captured as a new scenario in `CARRY_FORWARD.md` "Manual §5.0 walkthrough" section.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**One of the 5 remaining punch-list items**, in priority order:

1. **#8 "locales" → "locations" rename** (~9 templates, mechanical, no Triggers). Lowest risk, highest user-facing visibility. URLs stay `/locales/...` to avoid breakage; only labels/headings/dialog copy change. Estimate ~9 substantive template files in one slice.
2. **#1 race locale → Mapbox** + **#2-schema-only race URL column** as a combined slice (~5-6 files). Mirror the existing locale Mapbox autocomplete flow (already shipped in `routes/locales.py` for athlete locales — same pattern applies to race events). Schema add for `race_events.race_url TEXT`. **Trigger #5** fires on the Mapbox vs. text-anchor architectural decision. Defer the LLM site-parse pre-fill (#2-LLM) to its own slice — that needs Trigger #2 prompt design.
3. **#6 dynamic movement-constraints** (~3-4 files; 1 design + 2-3 code). Trigger #5 fires on the mapping design (which constraints apply to which body parts). Likely a static `BODY_PART_CONSTRAINTS` dict at module scope + a small JS swap-on-change at the form template. Pairs naturally with **#4** body_part vocab cleanup if Andy is OK with combining (both touch `routes/injuries.py` + `templates/injuries/form.html`).

### 6.2 Alternative pivots (carried from Layer 3 caching §6.2)

- **Manual §5.0 walkthrough on Neon** — still the architect-recommended forward move pre-this-slice; now half-complete since 5 of the surfaced issues are fixed. Andy can finish the walkthrough against the post-merge state.
- **NL parser smoke-eval harness + Haiku 4.5 migration per NL-1** (~5-6 files; Trigger #2 fires).
- **Over-eviction cleanup for layer2c/layer2d** (~2 files; remove the None-optimization at `cache_invalidation.py:105-111`).
- **Telemetry surface extensions** (row-level drill-down / cache hit-rate panels on `/admin/telemetry/refresh`).
- **Real-LLM Layer 4 regression** parity to plan_refresh.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (5 remaining walkthrough punch-list items live here as doc-sweep nits).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_PunchList_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

**Forward-pointer (test coverage):** Adding a static-analysis or test-client-rendered sweep for missing `nonce="{{ csp_nonce() }}"` on inline `<script>` tags would catch the failure mode that bit #3 + the 2 silent-fail modals in advance. Small follow-on (~1 test file added to the lint-style test set). Tracked here for future consideration.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Bundle CSP nonce fixes for the 2 silent-fail modals (refresh cap + T1 hook) into the #3 fix commit | Claude (self-deciding small ratio-good move) | Same root cause as #3; same one-line fix per template. Surfacing them in their own commit would create artificial commit noise. Documented as "bonus finds" in the commit message + PR body. |
| **D2** | Slice scope = 5 of 10 punch-list items (#3 / #5 / #7 / #9 / #10) + 2 bonus nonces | Claude / Andy | Remaining 5 items each require either a larger code surface (#1 / #8) OR a design decision (#2 / #4 / #6) that exceeds a single bug-fix slice. Trigger #2 fires on #2-LLM; Trigger #5 fires on #1 / #6. Andy ratified by saying "do a few more if there's room" + "stop here, merge, and hyperlink the handoff." |
| **D3** | `templates/locales/form.html` button + dialog copy = "location" not "locale" | Claude | Small step toward #8 (rename) without committing the full slice. Andy's intent is unambiguous on the term preference. |
| **D4** | List-page Delete button gated `if not is_legacy and p` | Claude | Mirrors the existing route guard at `routes/locales.py:1147` (legacy slots non-deletable). No new design needed. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `templates/_race_terrain_editor.html` inline `<script>` has `nonce="{{ csp_nonce() }}"` | ✅ `grep -n 'nonce="{{ csp_nonce' templates/_race_terrain_editor.html` returns 1 hit |
| `templates/plans/v2/refresh.html` inline `<script>` has `nonce` | ✅ grep |
| `templates/workouts/suggestion_view.html` inline `<script>` has `nonce` | ✅ grep |
| No other inline `<script>` blocks missing nonce in `templates/` | ✅ `grep -rn "<script" templates/ \| grep -v nonce` returns empty |
| `templates/plans/list.html` references `plan_create.new_plan` for Create-with-AI CTA | ✅ grep returns 2 hits (header + empty-state) |
| `templates/injuries/list.html` no longer compares severity as integer | ✅ `grep -nE "severity.*>=|severity.*== [0-9]|severity.*/5" templates/injuries/list.html` returns empty |
| `templates/injuries/list.html` uses enum-aware badge mapping | ✅ grep for `'Acute', 'Post-surgical'` returns 1 hit |
| `templates/coaching/generate.html` defines `MULTISPORT_TYPES` at template scope (before `{% block content %}`) | ✅ `grep -nE "MULTISPORT_TYPES\|^\{% block" templates/coaching/generate.html` shows set at line 7, content block at line 9 |
| `templates/locales/list.html` has list-page Delete form gated `if not is_legacy and p` | ✅ grep returns the delete form within the conditional |
| `templates/locales/form.html` no longer has `onsubmit="return confirm` | ✅ `grep -n 'onsubmit="return confirm' templates/locales/form.html` returns empty |
| `templates/locales/form.html` uses `data-confirm` for the delete form | ✅ grep returns 1 hit |
| Container-runnable subset 752 passed + 12 skipped (matches predecessor baseline) | ✅ pytest run |
| Tests 1419 net (no delta — template-only slice) | ✅ no Python changes |
| `CURRENT_STATE.md` last-shipped pointer flipped to Walkthrough_PunchList handoff | ✅ |
| `CARRY_FORWARD.md` 5 remaining walkthrough items added under Doc-sweep nits; 5 fixed items annotated ✅ Shipped | ✅ |
| PR #126 has draft status + CI green (Vercel deploy success) | ✅ at time of handoff write |

---

## 9. Files shipped this session

**Substantive (8 template files; over the 5-file ceiling per Andy's explicit "do a few more" override):**

1. `templates/_race_terrain_editor.html` — added CSP nonce to inline `<script>` (#3).
2. `templates/plans/v2/refresh.html` — added CSP nonce to capExceededModal auto-open script (bonus, silent T2/T3 cap modal).
3. `templates/workouts/suggestion_view.html` — added CSP nonce to t1HookModal auto-open script (bonus, silent T1 hook modal).
4. `templates/plans/list.html` — primary `[+ Create with AI]` CTA in header + empty-state; Import demoted to outline-secondary (#9).
5. `templates/injuries/list.html` — severity badge logic rewritten as enum-aware mapping; `/5` suffix removed (#5).
6. `templates/coaching/generate.html` — `MULTISPORT_TYPES` set lifted from `{% block content %}` to template scope (#10).
7. `templates/locales/list.html` — list-page `[Delete]` button next to `[Edit]` for non-legacy custom locales (#7 surfacing fix).
8. `templates/locales/form.html` — converted `onsubmit="return confirm(...)"` to `data-confirm="..."` (#7 CSP fix); relabeled "locale" → "location" in button text + dialog copy (small step toward #8).

**Bookkeeping (3 files):**

9. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; session narrative appended.
10. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — 5 fixed items annotated ✅ Shipped; 5 remaining items added as doc-sweep nits with concrete next-slice guidance.
11. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_PunchList_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **5 walkthrough items shipped 2026-05-21** ✅ — #3 add terrain button, #5 injury list 500, #7 location delete UI, #9 plan-list AI CTA, #10 coaching/generate 500.
- **2 bonus silent-fail nonce fixes shipped 2026-05-21** ✅ — capExceededModal auto-open, t1HookModal auto-open.
- **5 walkthrough items deferred** as doc-sweep nits with concrete next-slice estimates: #1 race locale → Mapbox, #2 race URL + LLM site-parse, #4 body_part vocab cleanup, #6 dynamic movement-constraints, #8 "locales" → "locations" rename.
- 1 new manual §5.0 walkthrough scenario added (6 steps verifying the punch-list fixes against preview deployment or post-merge main).
- Architect-recommended §6.1 forward move = **#8 "locales" → "locations" rename** as the lowest-risk highest-visibility next slice; alternatives include #1 + #2-schema combined slice, or #6 + #4 paired slice.

**End of handoff.**
