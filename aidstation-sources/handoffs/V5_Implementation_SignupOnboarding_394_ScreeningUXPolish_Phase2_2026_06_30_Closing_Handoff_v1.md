# Closing Handoff — Sign-up/Onboarding Phase 2: #394 — Health-Screening UX Polish
**Date:** 2026-06-30
**Branch:** `claude/pack-load-weighting-phase1-uy2kfz`
**Commit:** `b0fd7e4`
**PR:** NOT opened — pushed + bookkept, awaiting Andy's go (project rule: no auto-open)
**Issue:** [#394](https://github.com/ahorn885/exercise/issues/394) — CLOSED `completed`
**New issue filed:** [#1083](https://github.com/ahorn885/exercise/issues/1083) (D-79 split-out, icebox)
**Epic:** [#246](https://github.com/ahorn885/exercise/issues/246)
**Predecessor handoff:** `V5_Implementation_SignupOnboarding_223_PregnancyCapture_Phase1_2026_06_30_Closing_Handoff_v1.md`

---

## §1 — What this session was

#394 bundled six disparate, independently-scoped UX items (D-79, D-80, D-82, D-83, D-84, D-85) against the Phase-0 health-screening flow, labelled `priority:low`/`icebox`/`when:someday`. Rather than build the bundle blind, scope was put to Andy per-item before any code: explanations of each (grounded in the actual on-disk code, not the issue text alone), then his calls. He iceboxed-and-expanded D-79, approved D-80/82/83/84 to build, and asked two clarifying questions on D-83/D-85 ("what kind of screening(s) are we talking about") — answered by confirming there's exactly one screening in this app (the 10-question PAR-Q+-derived `health_screening` flow) before building.

---

## §2 — Per-item disposition

### D-79 — locale-aware "physician" terminology → SPLIT OUT, not built
**Andy's call:** icebox this, but expand its scope to app-wide localization.

The original ask ("doctor"/"GP"/locale equivalents on one acknowledgment-screen string) was too narrow — the underlying gap is that this app's copy is US-English-only throughout, not specific to health screening. Filed as new issue **[#1083](https://github.com/ahorn885/exercise/issues/1083)** ("App-wide localization for international athletes"), icebox, no parent epic (none fit — this is genuinely new ground, confirmed via search). #394's D-79 line points to it.

### D-80 — sensitive-field trust indicator → BUILT
**Andy's call:** do it.

The free-text detail fields and the opt-in checkbox already explained the privacy posture in plain inline text; this makes it visually distinct. `templates/onboarding/health_screening.html`:
- Per-question detail label gets a `<span class="chip accent">🔒 private — opt-in only</span>` badge (replaces the plain-text parenthetical)
- The opt-in checkbox block is now wrapped `class="hs-optin card card-pad"` (bordered box) with a 🔒 prefix on its copy

CSS-only via **existing** utility classes (`.chip`, `.chip.accent`, `.card`, `.card-pad` — all already defined in `static/tokens.css`/`static/style.css`) — no stylesheet edit needed. No new icon sprite added (the sprite sheet has no lock/shield symbol; a Unicode 🔒 glyph was used instead, consistent with how `conditions_advisory`'s template already uses emoji for similar inline badges — adding sprite-sheet machinery for one use would have been the kind of single-use abstraction the project's simplicity-first principle rejects).

### D-82 — voluntary mid-cycle screening update → BUILT (zero backend change)
**Andy's call:** do it.

Confirmed by reading `routes/onboarding.py`'s `health_screening`/`health_screening_save` handlers first: the GET handler already pre-fills from any existing screening (`prior_flags`/`prior_details`/`prior_optin`), and the flash message on first acknowledgment already said "You can update it any time from Settings" — meaning Phase 0 already intended this entry point, it just never got wired into Settings/profile. The only gap was a discoverability link, added in `templates/profile/edit.html`'s new "Health screening" card (same card as D-85, see below) → `{{ url_for('onboarding.health_screening') }}`.

No new route, no new repo function. The existing flow's POST redirect target (`_POST_HEALTH_SCREENING_TARGET = '/profile?tab=athlete'`) is unchanged — re-running screening from Settings still lands you back on the profile athlete tab, which was left as-is (pre-existing, shared with fresh onboarding's "next step" use of the same redirect; not this session's call to change).

### D-83 — reassessment-due UX → BUILT (dashboard banner); plan-output note DEFERRED
**Andy's call:** do it. (Clarifying Q answered: one screening, confirmed above.)

The Health Screening Spec v2 §9.2 already fully specifies the intended behavior (not invented this session):
- 14 days before due: soft in-app notification
- On due date: dashboard banner, persists until completed
- After due date: banner persists + plan output gets a one-line "reassessment overdue" note

**Built — the dashboard banner (covers the first two states as one persistent condition):** `routes/nudges.py`:
- New constant `SCREENING_REASSESS_LEAD_DAYS = 14`
- New `NUDGE_REGISTRY['health_screening_due']` entry — `warning` category (same liability-relevant class as `conditions_advisory`, per spec §8.3's framing of screening data as liability-defense evidence), CTA → `onboarding.health_screening`. **Deliberately no `notification_type` key** — rolls up to the existing `account_reminders` catch-all rather than claiming a new independently-mutable settings toggle this session doesn't build out (every other `_STALENESS_RECONCILE`-era nudge has its own type; this one doesn't, and that's flagged as a deliberate scope trim, not an oversight)
- New `_STALENESS_RECONCILE` entry: insert when `health_screening.reassessment_due_at <= NOW() + INTERVAL '14 days'`, delete when it's pushed back out past that window by a voluntary reassessment. **Note:** `reassessment_due_at` is a real `TIMESTAMP` column (unlike the ISO-text `date` columns the other staleness types compare via `TO_CHAR(..., 'YYYY-MM-DD')`), so this compares directly against `NOW() + INTERVAL` — a different SQL shape from its neighbors, documented inline.

**Deferred — the plan-output one-line note (the spec's third sub-piece):** NOT built this session. Recipe, ready to pick up directly:
- In `routes/plan_create.py`'s `view_plan`, add a try/except advisory load (mirrors the existing `#1035` conditions-advisory load pattern at `:1210-1232` and the `_plan_coaching_notes` pattern at `:1644`): `screening = health_screening_repo.get_screening(db, uid)`, pass `screening_overdue = bool(screening and screening['reassessment_overdue'])` into the template context. Must never break the view on a load fault (same posture as nutrition/conditions/coaching-notes loads in that function) — wrap in try/except, log via `print(f"view_plan: screening load failed ... (non-fatal): {exc}")` on failure, default to `False`.
- In `templates/plan_create/view.html`, render a standalone line right after the `page-sub` paragraph (before the `coaching_notes` card, NOT inside it — `coaching_notes` is specifically the Layer-3.5 HITL gate's informational items per its docstring, a different concept from a compliance/profile-completeness reminder):
  ```html
  {% if screening_overdue %}
  <p class="rail-note">⚠ Your annual health screening is overdue. <a href="{{ url_for('profile.edit', tab='health') }}">Update it</a> — this doesn't block your plan.</p>
  {% endif %}
  ```
- This was cut to hold the file count at the 5-file ceiling (it would have added 2 more substantive files — `routes/plan_create.py` + `templates/plan_create/view.html` — on top of the 4 already touched). The dashboard banner already delivers the core "athlete is reminded" outcome; the plan-output note is a smaller belt-and-suspenders addition from the spec, not the primary deliverable.

### D-84 — anti-skim guard → BUILT
**Andy's call:** do it.

`templates/onboarding/health_screening.html`, `acknowledge` phase: when `flags` is non-empty, the submit button gets `id="hs-ack-btn"` and a CSP-nonce'd inline script holds it disabled for a 3-second countdown (button text suffixed `" (3)"` → `" (2)"` → `" (1)"` → restored + enabled).

**Correctness note (caught + fixed before shipping):** the button is **never server-rendered `disabled`**. The first draft did render `disabled` server-side, which would have permanently trapped any athlete with JS unavailable/blocked — this app is otherwise CSP-clean no-JS, so that's a real population to consider. Fixed: only the script itself sets `btn.disabled = true` once it runs, so a no-JS browser gets a working (just un-delayed) button instead of a dead end. This is the one deliberate JS exception in an otherwise no-JS app (uses the existing `nonce="{{ csp_nonce() }}"` CSP escape hatch — confirmed allowed via `app.py`'s documented per-request nonce pattern, already used in 33 other templates).

### D-85 — settings read-view → BUILT
**Andy's call:** do it. (Same clarifying Q as D-83 — one screening, confirmed.)

New "Health screening" card on the profile Health tab (`templates/profile/edit.html`, between the pregnancy card and the `_health_tab.html` include — same placement convention as the #223 pregnancy card, not inside `_health_tab.html` itself since that partial is scoped to injuries/supplements/conditions/medications, a different capture pattern). Shows:
- Flag list in plain language (via `health_screening_repo.flag_descriptions`) or "No items flagged for physician consultation"
- Last-assessed date + reassessment-due date
- An overdue warning chip when `reassessment_overdue` is true
- The D-82 update link, in the same card header

`routes/profile.py`'s `edit()` GET handler now also loads `screening = get_screening(db, uid)` and `screening_flag_descriptions`, passed to the template. Zero new repo functions — `get_screening()` already returned everything needed (including the live-computed `reassessment_overdue` boolean), built in Phase 0 but never read by anything until now.

---

## §3 — Files changed

**4 substantive code files:**
1. `templates/onboarding/health_screening.html` — D-80 (trust indicator) + D-84 (anti-skim script)
2. `routes/profile.py` — D-82/D-85 (screening + flag_descriptions import + GET context)
3. `templates/profile/edit.html` — D-82/D-85 ("Health screening" card)
4. `routes/nudges.py` — D-83 (constant + registry entry + `_STALENESS_RECONCILE` entry)

**3 test files:**
5. `tests/test_health_screening_render.py` — +3 (D-80 privacy-indicator markup; D-84 present/absent cases)
6. `tests/test_redesign_profile_render.py` — +3 (D-85 card: no-screening / flags+dates / overdue-chip cases); extended the fake `_Conn` to distinguish `get_screening()`'s query (has `reassessment_overdue` in the SQL) from `get_pregnancy_flag()`'s simpler query, both against the same `health_screening` table
7. `tests/test_nudges_staleness.py` — +4 (registry wiring `TestHealthScreeningDueWiring` ×2; spec-content test; the parametrized `_STALENESS_RECONCILE` expansion picked up the new entry automatically — `RECONCILE_TYPES` updated so the existing completeness assertion stays accurate)

---

## §4 — Verification

- Full suite: **4041 passed / 30 skipped** (baseline 4031 + 10 new; only the 3 pre-existing #217 `evidence_basis` warnings, unrelated to this session)
- Ruff on all 7 changed files: **0 new errors**. The 4 pre-existing `routes/profile.py` errors (`bcrypt` unused import, `PROFILE_FIELDS` unused import, `DEFAULT_UNIT_PREFERENCE` unused import, ambiguous variable `l` at line 991) are untouched, confirmed unrelated to this session's edits.
- No `layer0-apply` owed — no schema change; this session reads existing `health_screening` columns (`flags`, `reassessment_due_at`, `reassessment_overdue` — the last one a computed SQL expression, not a stored column) that have existed since Phase 0.

---

## §5 — Session-end checklist

### §5.1 — Bookkeeping
- [x] `CURRENT_STATE.md` updated (last-shipped entry = #394; #223 demoted to predecessor)
- [x] `CARRY_FORWARD.md` updated (#394 marked DONE with full per-item disposition; Phase 1 marked COMPLETE; next = Phase 3)
- [x] Closing handoff written (this file)
- [x] GitHub issue #394 reconciled (checklist updated in-body for the D-79 split, then closed `completed`)
- [x] New issue #1083 filed (D-79 split-out)
- [x] Branch pushed: `claude/pack-load-weighting-phase1-uy2kfz`
- [ ] PR: NOT opened — awaiting Andy's go (project rule: no auto-open)

### §5.2 — Operating notes for next session

**Read order:**
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

**Next work: Phase 3 → #272 + #267 via Twilio** (`routes/auth.py`, `mfa.py`) — SMS/WhatsApp notifications + passkeys. Heavier v1 infra than the Phase 1/2 capture-only slices; budget accordingly, likely its own fresh branch off `main` rather than continuing this one (this branch already carries three bundled issues — #1067, #223, #394 — which is already a deviation from "each issue its own PR," justified only because all three landed in one continued session).

**Branch state:** `claude/pack-load-weighting-phase1-uy2kfz` now carries #1067 (pack-load weighting) + #223 (pregnancy capture) + #394 (screening UX polish) — three issues, one branch, because this session continued directly from the #223 session rather than starting fresh. When Andy says open the PR, it'll bundle all three; flag this in the PR description so it's not mistaken for scope creep on a single-issue PR.

**Deferred work to track:**
- D-83's plan-output overdue note (recipe in §2 above, ready to apply directly — not re-derive)
- #1083 (app-wide localization) — icebox, not scoped further, no action needed until international rollout is on the roadmap
- #304's `_history`-lists call (medications/conditions/injury history) — still blocking epic #246 closeout per the existing carry-state

---

## §6 — Decisions made this session

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Per-item scope confirmation before building, not blind bundle-build | #394's 6 items were independently scoped (different urgency, different build cost); Andy's "give me an explanation of each" request confirmed this was the right call |
| D2 | D-79 split + scope-expanded rather than built narrowly | The narrow ask (one string) undersold the actual gap (app-wide US-only copy); Andy's framing ("expand its scope") is the more honest issue to track |
| D3 | D-83 covered via the existing nudge framework, not new machinery | `_STALENESS_RECONCILE` already exists for exactly this shape (condition-holds → insert, condition-clears → delete); reusing it is both less code and consistent with 5 sibling nudges |
| D4 | `health_screening_due` rolls up to `account_reminders`, no dedicated pref type | Holds file count at ceiling; a compliance reminder arguably shouldn't be as freely mutable as a generic staleness nudge anyway |
| D5 | D-84's button is JS-disabled only, never server-rendered `disabled` | Caught during build: server-rendering `disabled` would permanently trap a no-JS athlete on a real medical-consequence screen — fail-open is the only safe default here |
| D6 | D-83's plan-output note deferred, not built | Would have pushed file count to 6, past ceiling; the dashboard banner already delivers the core reminder, the plan note is a smaller belt-and-suspenders piece from spec §9.2 |
| D7 | New "Health screening" card lives in `edit.html` directly, not `_health_tab.html` | Matches the #223 pregnancy-card placement precedent; `_health_tab.html` is scoped to a different capture pattern (injuries/supplements/conditions/meds), not a fit for a read-view + update-link card |

---

## §7 — Rule #10 verification table

| File | Anchor string | Check method |
|------|--------------|-------------|
| `templates/onboarding/health_screening.html` | `chip accent` | `grep -n "chip accent" templates/onboarding/health_screening.html` |
| `templates/onboarding/health_screening.html` | `id="hs-ack-btn"` | `grep -n hs-ack-btn templates/onboarding/health_screening.html` |
| `routes/profile.py` | `screening = get_screening(db, uid)` | `grep -n "screening = get_screening" routes/profile.py` |
| `templates/profile/edit.html` | `id="health-screening"` | `grep -n "id=\"health-screening\"" templates/profile/edit.html` |
| `routes/nudges.py` | `SCREENING_REASSESS_LEAD_DAYS` | `grep -n SCREENING_REASSESS_LEAD_DAYS routes/nudges.py` |
| `routes/nudges.py` | `'health_screening_due'` (registry + reconcile) | `grep -n health_screening_due routes/nudges.py` |
| `tests/test_health_screening_render.py` | `test_acknowledge_flagged_has_anti_skim_script` | `grep -n test_acknowledge_flagged_has_anti_skim_script tests/test_health_screening_render.py` |
| `tests/test_redesign_profile_render.py` | `test_profile_health_screening_card_overdue_chip` | `grep -n test_profile_health_screening_card_overdue_chip tests/test_redesign_profile_render.py` |
| `tests/test_nudges_staleness.py` | `class TestHealthScreeningDueWiring` | `grep -n TestHealthScreeningDueWiring tests/test_nudges_staleness.py` |
| GitHub | Issue #394 state | `closed`, reason `completed` |
| GitHub | Issue #1083 exists | `open`, icebox label |
