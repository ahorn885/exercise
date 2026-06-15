# V5 Implementation — Plan-view pv=71 polish (#618, 6 of 7) — Closing Handoff

**Date:** 2026-06-15
**Branch:** `claude/practical-newton-lk98tt` (both code PRs merged to `main`; this handoff + bookkeeping land on the same branch).
**PRs this session:** [#632](https://github.com/ahorn885/exercise/pull/632) (render) + [#633](https://github.com/ahorn885/exercise/pull/633) (plan-gen + render) — both CI-green, auto-merged.
**Predecessor handoff:** `handoffs/V5_Implementation_Layer0_OpsAutomation_OperatingModelCodified_2026_06_15_Closing_Handoff_v1.md` (the prior session-close; Layer 0 `primary_movement` + ops automation).

This session got back to **the app itself** after several Layer 0 / ops-automation sessions — working Andy's live **plan-71 (pv=71)** walkthrough batch (#618).

---

## 1. What shipped (#618 — 6 of 7 checklist items)

All render/plan-gen polish from the pv=71 read. **No DDL.** Full suite green at close: **2481 passed / 30 skipped**.

**PR #632 — plan-view render (`templates/plan_create/view.html` + `routes/plan_create.py`):**
- **"Pattern A" jargon removed** — dropped the internal synthesis term from the plan eyebrow (now `● Plan`).
- **State label instead of "plan create"** — the chip now reads a lifecycle label (`Active` / `Upcoming` / `Completed` / `Archived`), computed by `_plan_lifecycle_label` the same way the plans-list buckets (`routes/plans.py`). `_load_plan_version` now also selects `completed_at` / `archived_at`.
- **Flags grouped with the coach notes** — the coaching/workout-type flags (e.g. "long slow distance", an LLM-emitted `coaching_flag`) moved up next to `coaching_intent` / `session_notes` instead of rendering below the per-block detail.
- **Explicit rest days** — `_plan_days_with_rest_gaps` gap-fills the plan span so off days render as a "Rest — off day" card and each week reads continuously. Production session dates are real `date`s (gap-filled); the string-dated render harness degrades to a no-fill passthrough rather than erroring.

**PR #633 — skill-gate slug leak + duplicate effort label:**
- **Discipline-slug leak fixed (#618 item 5; Trigger #1, Andy-confirmed).** "Prescribing strength until cleared on `climbing_roped`" leaked because the synthesis prompt handed the LLM the **raw toggle slug**, which it echoed into athlete-facing `coaching_intent`. Removed the slug from **both** feeds: the `per_phase.py` session-grid `SKILL-GATED` annotation, and the `validator.py` skill-capability correction feedback (now steers the note to the discipline's plain name). Added a coaching-**VOICE** rule barring internal ids/slugs in athlete-facing text across `per_phase` + `plan_refresh_t1/t2/t3`. Bumped `hashing.LAYER4_PROMPT_REVISION` **2→3** so cached plans re-synthesize cold with the corrected wording.
- **Duplicate effort label fixed (#618 item 4; Andy-confirmed "drop").** Dropped the trailing nutrition `load_tier` word from the day-fuel macros line — it duplicated the phase name ("Peak") and the per-session intensity chip; the kcal chip already accents on hard/peak.

**Tests:** `tests/test_redesign_view_plan_render.py` (jargon hidden, lifecycle label, flag ordering, rest-gap rendering), `tests/test_layer4_validator.py` + `tests/test_layer4_event_windows.py` (no slug in the validator detail or grid annotation), and the directly-rendered nutrition/wellness render tests updated to the new `days` context.

## 2. Deferred — the one remaining #618 item

- ⬜ **#618 item 7 — address inconsistency** ("Williams" vs "509 Williams"). This is **locale data**, not render (likely `gym_profiles` naming: Mapbox place name vs street address). Left **#618 open** for it; folded into the Locations & Gear next-steps below.

## 3. Bookkeeping done this session

- **GitHub issues** — commented on #618 with the 6 shipped items + PR refs, kept it open scoped to item 7. (Per the new standard step — see below.)
- **`CLAUDE.md`** — added a standing rule (under the GitHub-issues working principle): **reconciling GitHub issues is a STANDARD session-end step** — comment PR refs, close completed ones with a reason, tick partial checklists, file new issues for discovered work, every shipped session, before writing the handoff. (Andy asked for this explicitly.)
- **`CURRENT_STATE.md`** — new top "Last shipped session" entry (this work); demoted the prior Layer 0 / ops entry to a predecessor.
- **`CARRY_FORWARD.md`** — the WS-H Slice-5b / #608 staleness was already corrected in PR #632 (arc now marked complete).

## 4. NEXT STEPS — a "Locations & Gear" arc (the focus for next session)

The pv=71 walkthrough surfaced a **cluster of location/gear issues** that share surfaces — the locale / `gym_profiles` data, the profile **Gear** / equipment picker, and the feasibility cascade's location inputs. They're worth tackling as one themed arc rather than scattered. Suggested lead + wrap:

**Lead — the location issue:**
- **[#624](https://github.com/ahorn885/exercise/issues/624) — nearby groomed-trail location not detected (plan-gen bug, med).** Plan-71 said "no nearby groomed trail," but Cleburne State Park (which has one) is nearby; discovery DID surface a *farther* park (Dinosaur Valley SP). So it's the **input** side — either the discovery **radius/ranking** or the **terrain tagging** of nearby parks (`locale_terrain_ids` missing TRN-002 groomed trail). **Investigation-first (Rule #14):** use the read-only **`neon-query`** workflow to inspect pv=71's athlete locales, the resolved cluster, and each candidate's `locale_terrain_ids` + distance — decide the fix only once the data shows whether Cleburne is *absent* from the candidate set (radius/ranking) or *present-but-untagged* (terrain gap), or whether public venues must be added manually. Related shipped: #540 (route to matching-terrain locales only), #581 (home-cluster radius 42.2 km).
- **#618 item 7 — locale-label normalization** ("Williams" vs "509 Williams"). Small, locale-data; pairs naturally with the #624 data dig (same `gym_profiles` look).

**Wrap — the Gear surface:**
- **[#622](https://github.com/ahorn885/exercise/issues/622) — movable crafts still under Equipment (bug, med).** Bikes/boats still listed under Equipment on Locations → Gear, even though #586 split them into the athlete-owned craft store. Likely the Gear UI/picker isn't excluding craft entries (or #586's migration isn't applied in prod — **verify via `neon-query` first**). Render/route fix on the profile Gear surface.
- **[#623](https://github.com/ahorn885/exercise/issues/623) — retire "assumed" basic gear (cleanup, med — TRIGGER #2).** Stop tracking backpack / headlamp / hiking boots / running shoes / trekking poles / wetsuit / swim cap & goggles / avalanche gear. **Trips Trigger #2** (vocab retirement → Andy signs off the canonical set). **Before removing, audit the feasibility cascade** (2C effective-pool / craft↔terrain) to confirm none of these gate a discipline/exercise — removing a gating item must not silently drop sessions.

**Possible third slice (general UI/IA, parent #434):**
- **[#619](https://github.com/ahorn885/exercise/issues/619) — nav & profile IA cleanup.** Has a location-adjacent item ("Make **Locations** a tab on the profile") plus broader work (supplements/meds into their own tab, sidebar rearrange, Sources 3-per-row, Schedule-tab white background). The Locations-tab item could ride with the Gear slice; the rest is its own UI slice.

**Recommended scoping (≤5 substantive files each; flag triggers up front):**
1. **#624 + #618-7** — "locale data + terrain feasibility" (investigation-first via `neon-query`; the fix may be a layer0 / `gym_profiles` terrain-tagging update or a discovery radius/ranking tweak — **could trip Trigger #3** if it touches the cluster/feasibility contract).
2. **#622 + #623** — "Gear surface" (equipment picker + vocab; **#623 = Trigger #2** sign-off + the feasibility-gate audit).
3. **#619** — UI/IA slice on its own (or fold the Locations-tab item into slice 2).

## 5. Owed / carried (unchanged)

- ⬜ **STILL OWED (carried):** the post-#572 live **T3 *refresh*** re-verify (Rule #14) — needs a live refresh on a real plan + the diag token. Unrelated to this session.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules **+ the new GitHub-issues session-end step**. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model first; WS-H arc complete. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Render — jargon + state label | `templates/plan_create/view.html` | eyebrow `● Plan` (no "Pattern"); chip `{{ lifecycle_state }}`; macros line has no `load_tier` |
| Render — rest gaps + flag order | `templates/plan_create/view.html` | `{% for d, dow, sessions in days %}`; `sess-rest` "Rest" card; `sess-flags` block precedes `coaching_intent` |
| Route — lifecycle + gap-fill | `routes/plan_create.py` | `_plan_lifecycle_label`; `_plan_days_with_rest_gaps`; `_load_plan_version` selects `completed_at`, `archived_at` |
| Slug leak — grid annotation | `layer4/per_phase.py` | `[SKILL-GATED: athlete not cleared for this skill` (no `{skill_gated[...]}`); VOICE bullet "Never surface internal identifiers" |
| Slug leak — validator feedback | `layer4/validator.py` | detail says "requires a skill capability" + "plain name — never an id or internal slug" (no `'{toggle}'`) |
| Slug leak — refresh VOICE | `layer4/plan_refresh_t1.py` (+ `_t2`, `_t3`) | each VOICE line ends "...use the plain discipline name." |
| Cache bust | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "3"` |
| Tests | `tests/test_layer4_validator.py`, `tests/test_layer4_event_windows.py` | `"climbing_roped" not in` detail / grid annotation |
| Suite | — | 2481 passed / 30 skipped |
| Issues | #618 | open; commented 6/7 done + PR refs; item 7 (address) carried |
| Bookkeeping rule | `aidstation-sources/CLAUDE.md` | GitHub-issues principle has "STANDARD session-end step" sub-bullet |
| Owed | — | T3-refresh re-verify carried; nothing owed on #618 items 1–6 |
