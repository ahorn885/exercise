# V5 Implementation — WS-B/WS-C: retire legacy `LOCALES` enum + onboarding forced-home gate (Closing Handoff)

**Session:** Shipped the next slice off the locale-retirement north star — WS-B (retire the legacy `home/hotel/partner/airport` enum so locales are purely athlete-created) + WS-C (make the onboarding locations step a gate requiring ≥1 built locale and one tagged home). Both land together per Andy's call.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSI_SliceB_UnifiedCraftTerrainCascade_2026_06_14_Closing_Handoff_v1.md` (WS-I complete).
**Branch / PR:** [#589](https://github.com/ahorn885/exercise/pull/589) (`claude/ws-bc-locale-retirement-onboarding-home`). **Squash-merged to `main`, CI-green.** Closes WS-B (#582) + WS-C (#583).
**North-star plan:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§4 WS-B, §5 WS-C).
**Status:** 7 substantive files (4 code/template + 3 mechanical test edits) — **2 over the 5-file ceiling, flagged.** Andy chose to land B+C together after the ceiling risk was surfaced; the test edits are mechanical follow-ons to the code change. No DDL.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the WS-I Slice B §8 table — **all ✅, working tree clean, no drift.** Branch was based on the post-#588 merge (Slice A #587 + Slice B #588 both in `git log`; WS-I #586 closed). The harness-pinned branch name (`claude/slice-b-terrain-cascade-cmtw5i`) named the *just-finished* WS-I Slice B, so per the branch-naming rule it was renamed to `claude/ws-bc-locale-retirement-onboarding-home` to match this scope.

Scope was a genuine decision (WS-I done; B/C/E2/H all technically open) — asked Andy via `AskUserQuestion`; he picked **WS-B + WS-C together**.

---

## 2. Session narrative

- **Why these next.** The plan's §2 sequence after WS-I is **B → C → V**. The only Tier-1 carried item (T3 *refresh* re-verify) is Andy's-hands (diag token + log paste, Rule #14) — not solo-buildable in the container. WS-B is Andy-DECIDED with verbatim mechanical edit sites (plan §4); WS-C is coupled and meant to land close behind. Neither trips a stop-and-ask trigger (no LLM-prompt change, no DDL, no HITL gate — all decided).
- **WS-B is also a candidate *cause*, not just cleanup.** The plan (§1, §5) flags that a stale legacy locale read as home could feed the empty-cluster → strength-saturation failure. Retiring the force-rendered slots removes that whole class.
- **Grounded every edit against the live files.** The plan's line numbers are from 2026-06-13; they held up well, but I re-read each site (Rule: never invent file contents) and found `_ensure_home` already auto-tags the first built locale as home on every create path — so "≥1 locale built" implies "home tagged" in practice. The WS-C gate still checks both defensively.
- **Surgical.** Removed only the `LOCALES` constant and the special cases keyed off it; left the `_ensure_home` / `make_home` / `preferred` machinery (already the canonical home model) untouched.
- **Validated with the full pytest suite** (2380 passed, 30 skipped) — no Postgres run needed (no SQL).

---

## 3. File-by-file edits

### 3.1 `routes/locales.py` (modified — core, WS-B)
- **Removed the `LOCALES = ['home','hotel','partner','airport']` constant** (+ its back-compat comment).
- **`athlete_locale_choices`** — dropped the `for slug in LOCALES` prepend; the `/references` where-available choices now come purely from `locale_profiles` rows (bucket via `CATEGORY_TO_WHERE_AVAILABLE_BUCKET`). Docstring updated.
- **`list_profiles`** — `displayed_locales = sorted(profiles.keys())` (was `list(LOCALES) + custom`); dropped the `legacy_locales=LOCALES` template kwarg.
- **`edit_profile`** — removed the `if locale not in LOCALES` auto-create bypass; **all** locales must already exist (built via `new_locale`).
- **`form.html` render** — `is_deletable=True` (was `locale not in LOCALES`).
- **`delete_locale`** — removed the `if locale in LOCALES: refuse` short-circuit guard + its docstring note.
- Lightly de-staled two comments that referenced the retired legacy-auto-create behavior (the `_edit_locale` upsert + the first-locale-auto-home note).

### 3.2 `routes/onboarding.py` (modified — WS-B + WS-C)
- **WS-B:** dropped `from routes.locales import LOCALES as LEGACY_LOCALES`; `_athlete_locales_for_review` now returns athlete-created rows only with shape `{slug, label, category, is_home}` (was the 4 legacy slots + custom, with `is_custom`/`configured`). Empty when no rows → drives the template empty state.
- **WS-C:** `locales_continue` is now a **GATE** — selects `preferred` over the athlete's `locale_profiles`; if no rows → flash "add a location" + redirect back to `/onboarding/locales`; if rows but none `preferred` → flash "tag one home" + redirect back; else advance to `/onboarding/skills`. Building any locale auto-tags the first as home (`_ensure_home`), so one locale satisfies both — both checked defensively. No DB write.

### 3.3 `templates/locales/list.html` (modified — WS-B)
Removed the `is_legacy` set + all its branches (capitalized-slug title, the `not is_legacy` refresh/delete gates). The empty "Where do you train?" hero no longer loops legacy slots — it leads with the search/add CTA to `new_locale`. Top comment de-staled.

### 3.4 `templates/onboarding/locales.html` (modified — WS-B + WS-C)
Reworked from the custom/legacy split (`selectattr('is_custom')` / `rejectattr`) to a single athlete-created list with a ★ Home flag (`is_home`), an empty state, and WS-C requirement copy ("Add at least one location and tag one as home — you can't continue without a home location"). The Continue button gets a hint title when the gate isn't satisfied (server-side gate is authoritative).

### 3.5 `tests/test_onboarding_skills.py` (modified)
`TestAthleteLocalesForReview` rewritten to the new shape (empty list when no rows; row mapping; home-flagged + slug-sorted). `TestLocalesRoute`: the empty-template assertion is now `== []`; replaced the single "continue → skills" test with the three WS-C gate paths (home present → skills; no locale → back; no home → back).

### 3.6 `tests/test_locales.py` (modified)
`test_legacy_locale_short_circuits_without_delete` → `test_former_legacy_slug_is_now_deletable` (a `home`-slug locale now deletes like any athlete-created row).

### 3.7 `tests/test_redesign_locales_list_render.py` (modified)
Empty-hero test repointed off the retired `/locales/home/edit` + `/locales/hotel/edit` shortcuts onto the real `/locales/new` path; one comment de-staled.

---

## 4. Code / tests

**Full suite green: 2380 passed, 30 skipped, 2 pre-existing unrelated warnings** (`test_layer3b_builder` evidence-basis). Affected suites all green: `test_locales`, `test_onboarding_skills`, `test_redesign_locales_list_render`, `test_redesign_onboarding_render`, `test_onboarding_race_events`, `test_layer4_orchestrator`.

---

## 5. Manual verification

No SQL — the schema already supports athlete-created locales + the `preferred` home flag. Behavioral correctness pinned by tests. Vercel preview deployed green; the live onboarding-gate walkthrough (new user → blocked until a home is built) is a good **next-session Andy's-hands check** on the preview/prod URL but not owed for merge.

---

## 6. Next session pointers

### 6.1 This slice
WS-B + WS-C **shipped + squash-merged to `main`** on #589 (CI-green). Plan §2 table flipped to SHIPPED for both; issues #582 (WS-B) + #583 (WS-C) closed. No owed deploy (no DDL). **#583 note:** closed for the home-gate (the load-bearing go-live correctness piece); the issue's secondary "make craft capture required" bullet was **not** implemented as a hard gate — a universal craft requirement would wrongly block craftless foot/swim/climb athletes, and empty craft now degrades gracefully through the WS-I cascade (INDOOR/strength) rather than crashing. The craft *capture* surface already shipped (slice 2c.2b). A conditional bike/paddle-only craft prompt is a possible small follow-up if Andy wants it.

### 6.2 Next forward moves (4-tier order)
- **STILL OWED (carried, Tier 1):** the post-#572 live **T3 *refresh*** re-verify (paired: diag token + Andy pasting logs, Rule #14). pv=71 was a *create*; a *refresh* has never been live-verified post-#572.
- **Tier-4 remaining on this plan:** **WS-V** the full Vocabulary arc (`Vocabulary_TargetState_and_Plan_v1`) — the durable one-source-of-truth cleanup; **WS-E2** saturation policy (dose+2 cap + reallocate-with-variety, queued lower since E1 + the craft model cover the crash); **WS-H** away-craft availability (needs DDL → design-first, Trigger #3, + a Neon write Andy must apply).
- Off-plan: the #541/#542/#543 plan-quality batch + the compliance build-out (epics #353/#355/#356/#359).

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules (incl. Rules #14/#15).
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — top entry.
4. This handoff.
5. The plan `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md`.
6. `aidstation-sources/scripts/verify-handoff.sh` (run from `aidstation-sources/`).

**Test env:** `pytest` isn't in `requirements.txt` — `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then run the full `tests/`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Land WS-B + WS-C in one PR | Andy (2026-06-14, AskUserQuestion) | Coupled by design — without C a new user reaches plan-gen with no home → empty cluster → the strength saturation B/C close. |
| 2 | WS-C gate checks both "≥1 locale" AND "a `preferred` home", defensively | Claude | `_ensure_home` auto-tags the first build so they usually coincide, but the partial unique index allows zero homes; both checks keep the message precise. |
| 3 | Gate lives in `locales_continue` (server-side), template only hints | Claude | Authoritative enforcement can't be bypassed by a hand-rolled POST; the template title is UX only. |
| 4 | Removed `LOCALES` outright (not deprecated) | Plan §4 (Andy-decided) | The force-render was the bug; only `routes/onboarding.py` imported it (tests don't). |
| 5 | Shipped at 7 files (2 over ceiling) | Claude (flagged) | The 4 code/template files are one cohesive B+C change; the 3 test edits are mechanical. Splitting would fragment it. |

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Enum removed | `routes/locales.py` | no `\bLOCALES\b` anywhere in file (grep clean) |
| Display off rows | `routes/locales.py` | `displayed_locales = sorted(profiles.keys())`; no `legacy_locales=` kwarg |
| Edit gate | `routes/locales.py` | `edit_profile` has no `if locale not in LOCALES`; unconditional existing-row check |
| Delete ungated | `routes/locales.py` | `delete_locale` has no `if locale in LOCALES` block; `is_deletable=True` |
| Import dropped | `routes/onboarding.py` | no `LEGACY_LOCALES`; `_athlete_locales_for_review` returns `{slug,label,category,is_home}` |
| WS-C gate | `routes/onboarding.py` | `locales_continue` selects `preferred`, redirects `_POST_STEP3_TARGET` when missing |
| Template | `templates/locales/list.html` | no `is_legacy`/`legacy_locales` |
| Onboarding template | `templates/onboarding/locales.html` | `is_home`; no `is_custom`/legacy split |
| Gate tests | `tests/test_onboarding_skills.py` | `test_continue_blocked_when_no_locale` / `_no_home` / `_with_home_redirects_to_skills` |
| Suite | — | `pytest tests/` → 2380 passed, 30 skipped |
| Working tree | — | clean after the bookkeeping commit |

---

## 9. Files shipped this session

**Substantive (7 files):**
1. `routes/locales.py`
2. `routes/onboarding.py`
3. `templates/locales/list.html`
4. `templates/onboarding/locales.html`
5. `tests/test_onboarding_skills.py`
6. `tests/test_locales.py`
7. `tests/test_redesign_locales_list_render.py`

**Bookkeeping (this commit):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§2 table), this handoff.

---

## 10. Owed Andy's hands (Neon — container has no egress)

**None.** This slice added no DDL and made no Neon write. PR #589 squash-merged to `main` (CI-green); nothing remaining. (Carried, unrelated: the post-#572 live T3 *refresh* re-verify.)
