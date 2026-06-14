# V5 Implementation — WS-H: Event Windows arc design + Slice 1 build spec (Closing Handoff)

**Session:** Design-first slice for **WS-H** (issue [#581](https://github.com/ahorn885/exercise/issues/581) Phase H). Picked WS-H (away-craft) as the next slice after WS-E2 closed the last *code* workstream; chose design-first. Investigating away-craft surfaced that it can't exist without a missing **event-window** surface, which Andy then reframed and shaped across several rounds. Output: the **Event Windows arc design** + a **build-ready Slice 1 spec**, all forks ratified. No code/DDL/tests — design only.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSE2_StrengthSaturationCap_2026_06_14_Closing_Handoff_v1.md` (WS-E2 shipped, #590).
**PRs (both squash-merged to `main`):** [#591](https://github.com/ahorn885/exercise/pull/591) (arc design + Slice-1 spec, `b8bfe6e`) → [#594](https://github.com/ahorn885/exercise/pull/594) (seam simplification, `d6038b9`). Branch `claude/v5-strength-saturation-cap-pjscu2` (harness-pinned name; scope was WS-H).
**North-star plan:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§2 WS-H + §6a).
**Issues filed:** [#592](https://github.com/ahorn885/exercise/issues/592) (race-location terrain/weather inference), [#593](https://github.com/ahorn885/exercise/issues/593) (reduced-volume/in-transit travel days). #581 commented with the design outcome.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the WS-E2 §8 table — all ✅, working tree clean, no drift. Spot-checked: `apply_strength_saturation_cap` present + in `__all__`; `_FAILOVER_STRENGTH_HEADROOM = 2`; `SessionGrid.saturation_note`; the `strength_guidance.py` failover wording. WS-E2 confirmed shipped on #590, suite green (2391 passed). Scope was a genuine decision (last code workstream closed) → asked Andy via `AskUserQuestion`; he picked **WS-H, design-first**.

---

## 2. Session narrative (the reframes)

1. **The finding (Trigger #5).** WS-H wants craft↔location + craft↔travel-event. But v2 plan-gen resolves feasibility only over the **home cluster** for the whole plan (`orchestrator._build_terrain_feasibility`, `cluster = locations.cluster_locale_ids`, `orchestrator.py:371`); away locales (>42 km) are excluded by definition. So a craft↔away-location store alone would be **unconsumed** — the WS-F (#578, reverted) failure shape. Away-craft is the *last axis* of a missing **away/event-window** surface. v1 *had* travel-logging (`plan_travel` via `/coaching/review`, `routes/coaching.py:62-70`) using the now-retired `home/hotel/partner/airport` enum — **left behind** in v2.
2. **Andy reframe #1 — "event windows," not "away/travel."** v1's date feature also constrained training **at home** (`plan_travel.indoor_only` — weather, or kids needing supervision). So the model is **event windows**: date-bounded periods where the environment differs, covering home-constraint AND away.
3. **Andy reframe #2 — per-day, not per-week.** He may be in 3-4 locations in one week (work travel). Granularity is **per-day / sub-week**, not per-week.
4. **Andy reframe #3 — category baselines + a third override.** A not-yet-seen hotel gym gets an **assumed** equipment baseline (scoped to **commercial / hotel / climbing gyms** — the *current* `routes/locales.py:205 MANUAL_CATEGORIES`, **NOT** the retired enum; I had to correct that framing); athlete logs actuals on arrival → T1/T2 regen. Plus a new override **`locale_unavailable`** — "this cluster, but not this place in it" (gym remodel, park flooded). And `indoor_only`/`no_outdoor_cardio` collapse to **one flag** (same effect); `reduced_volume` deferred to #593.
5. **Andy reframe #4 — the seam is nothing new.** I over-built a per-week "good-days / overflow-retiering" arithmetic; Andy: *"why aren't we just using the same deterministic steps as proxies/substitutions? It's just resolving against different terrain/equipment."* Correct. **Removed the arithmetic.** The cascade already does substitutions; the only new element is the **time dimension** — emit one `dict[discipline → tier]` **per date-segment** instead of plan-wide. (#594.) A key sub-correction earlier: the retier tier is whatever the cascade resolves for the changed environment — may be **valid different outdoor terrain** (hotel run, Alps scree), another cluster locale, indoor, or strength — never an assumed downgrade.
6. **Race split.** Andy: race locations are real but **treated differently** (a target, not a training environment; Boston stable vs AR year-to-year). The DB already splits them (`race_events` Mapbox-anchored, `init_db.py:1414-1417`; `event_locale_id` FK legacy/nullable). Filed **#592** (LLM terrain/weather inference + UI suggestion). Out of this arc.

---

## 3. What shipped (design artifacts)

- **`designs/Event_Windows_Design_v1.md`** (new) — the arc design: the finding, the event-window model (3 override types), forks F1–F9 + F-race (all ratified), the cascade/synthesis change, the 5-slice plan, DDL, caching, tests, gut check.
- **`designs/Event_Windows_Slice1_HomeWindows_Spec_v1.md`** (new) — the **build-ready** Slice 1 spec. §4 = the settled resolution model (existing cascade per date-segment). §5 = the 5-file change surface. §3 = the `athlete_event_windows` DDL.
- **Bookkeeping:** plan §2 WS-H row + §6a; `CURRENT_STATE.md`; this handoff; `CARRY_FORWARD.md`.

---

## 4. Code / tests

**None this session — design only.** No code, no DDL, no tests, no cache changes. (CI green on both PRs — docs-only.) Full suite unchanged from WS-E2's 2391 passed / 30 skipped.

---

## 5. Decisions pinned (all Andy, 2026-06-14)

| # | Decision | Note |
|---|---|---|
| 1 | Build WS-H this slice, design-first | `AskUserQuestion`; last code workstream was WS-E2 |
| 2 | Reframe "away/travel" → **event windows** | covers home-constraint + away; v1 had it (left behind) |
| 3 | F1 windows **athlete-level + plan-gen review/edit/append panel + inline new-location create** | restores the v1 `/coaching/review` UX |
| 4 | F2 destination = **reused `locale_profiles` row** | *"travel is how we build our crowd-sourced locations database"* (differentiator #8) |
| 5 | F3 granularity = **per-day / sub-week** | 3-4 locations in a week possible |
| 6 | F4 away craft **none unless declared** | craft↔locale ∪ craft↔window |
| 7 | F8 category equipment baselines (Trigger #2) | **commercial / hotel / climbing gyms** (current `MANUAL_CATEGORIES`, not the retired enum); assumed→logged→regen |
| 8 | F9 home overrides = **`indoor_only` + `locale_unavailable`** | collapsed the indoor/no-outdoor flags to one; `reduced_volume`→#593 |
| 9 | Seam = **existing cascade resolved per date-segment** | no bespoke arithmetic (#594); retier tier = cascade result, not an assumed downgrade |
| 10 | Race locations → **separate issue #592** | target ≠ training environment; LLM terrain/weather inference |
| 11 | **Re-sliced into 5**, each ≤5 files, independently shippable | keeps scope within the ceiling |

---

## 6. Next session — BUILD Slice 1 (mechanically-applicable, Rule #11)

**The work:** build Slice 1 (subtractive home windows: `indoor_only` + `locale_unavailable`) per `designs/Event_Windows_Slice1_HomeWindows_Spec_v1.md`. **Spec is build-ready.** The 5 substantive files (spec §5):

1. **`athlete_event_windows_repo.py`** (new) — `load_event_windows(db, user_id)` + add/delete + Layer-1/plan-cache eviction (mirror `athlete_crafts_repo.evict_layer1_on_crafts_change`). Table per spec §3: `(id, user_id, start_date, end_date, override_type ∈ {indoor_only, locale_unavailable}, unavailable_locale|null, notes, created_at)`. **DDL owed Andy's hands** (Neon egress blocked — write the idempotent `_PG_MIGRATIONS` CREATE in `init_db.py`; Andy applies).
2. **`layer4/orchestrator.py`** — load windows overlapping `[plan_start, plan_end]`; **segment the span by date** into environments (home; `indoor_only` = home cluster minus outdoor terrain; `locale_unavailable(L)` = home cluster minus locale L's terrain+equipment); call the **existing** `_build_terrain_feasibility` once per environment → `feasibility_by_segment`. Grid + E2 stay on the home env. Rule #15 log (`event_window_overlay: …` per spec §7).
3. **`layer4/per_phase.py`** — render the date-scoped `=== Session feasibility ===` block (per-segment tiers + date ranges, via the `per_phase.py:1647-1654` week→date anchor) + the soft directive "prefer placing outdoor-dependent disciplines on the unconstrained days." **Trigger #1 — bring the exact wording to Andy before finalizing.**
4. **`layer4/hashing.py`** — `compute_event_windows_hash` (windows overlapping the plan span: type + dates + `unavailable_locale`) into `plan_create_key` + `plan_refresh_key` (mirror `compute_terrain_feasibility_hash`, #556). No-windows → empty digest → byte-identical key.
5. **Capture UI** — minimal: an event-window list + add/delete on the profile + the plan-gen review-panel hook; reuse the existing locale picker for `locale_unavailable`. (Route + thin template; may split a 6th file — flag if it pushes the ceiling.)

Plus `tests/test_layer4_event_windows.py` (spec §9 scenarios — regression no-windows, `indoor_only`, `locale_unavailable` with/without fallback, cache invalidation, Rule #15 line).

**The one accepted Slice-1 limitation (spec §4):** counts resolve against home, so E2 won't pre-cap a window-induced substitution (+1–2 strength on a constrained week at composition time). Acceptable for short home windows; the fix (feed the grid segment tiers for fully-covered weeks) waits for `away`/Slice 2.

### 6.1 Slice sequence after Slice 1
- **Slice 2** — away windows + destination locale (reuse + inline create) + per-environment cascade against its terrain/equipment + `mapbox_id` dedup. DDL: window→`away_locale` + away discriminator on `locale_profiles`.
- **Slice 3** — category equipment baselines (Trigger #2 — get the commercial/hotel/climbing-gym equipment lists ratified) + arrival→regen loop.
- **Slice 4** — away craft (the literal WS-H (b)+(c)): craft↔locale ∪ craft↔window → away `owned_crafts`. DDL: `athlete_craft_locale` + window craft carrier.
- **Slice 5** — capture UX polish.

### 6.2 Carried (unchanged)
- **STILL OWED (Tier 1):** the post-#572 live **T3 *refresh*** re-verify (paired: diag token + Andy pasting logs, Rule #14). Andy's-hands.
- Off-plan: #542 nutrition macros (clean solo fix), #543 health-condition dropdown (Trigger #2), compliance epics.

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — top entry (WS-H).
4. This handoff.
5. `designs/Event_Windows_Slice1_HomeWindows_Spec_v1.md` (the build spec) + `designs/Event_Windows_Design_v1.md` (the arc).
6. The plan `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§2/§6a).
7. `./scripts/verify-handoff.sh` (from `aidstation-sources/`).

**Test env:** `pytest` isn't in `requirements.txt` — `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then the full `tests/`.

---

## 7. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Arc design | `designs/Event_Windows_Design_v1.md` | present; §4 forks F1-F9 + F-race "RATIFIED"; 5-slice §6 |
| Slice 1 spec | `designs/Event_Windows_Slice1_HomeWindows_Spec_v1.md` | present; §4 "existing cascade … per date-segment"; no "good_days"/"overflow" left |
| Plan §2 WS-H | `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` | WS-H row = "**DESIGNED** … `Event_Windows_Design_v1.md`" |
| Plan §6a | same | "Seam settled … per date-segment" |
| CURRENT_STATE | `CURRENT_STATE.md` | top entry = WS-H Event Windows; "Seam SETTLED" |
| CARRY_FORWARD | `CARRY_FORWARD.md` | top entry = WS-H Event Windows |
| Race issue | GitHub | #592 open |
| Reduced-volume issue | GitHub | #593 open |
| #581 | GitHub | comment with design outcome + slice plan |
| PRs | GitHub | #591 + #594 merged to `main` |
| Suite | — | unchanged (no code); 2391 passed / 30 skipped |

---

## 8. Owed Andy's hands

- **Slice-1 build DDL:** the `athlete_event_windows` migration (Neon egress blocked from the container) — write it in `init_db.py`, Andy applies on Neon.
- **Trigger #1:** the Slice-1 synthesis date-scoped feasibility-block + soft placement-directive wording — bring exact text for sign-off at build.
- **Carried (unrelated):** the post-#572 live T3 *refresh* re-verify.
