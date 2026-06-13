# Plan — pv=69 feasibility saturation + legacy-locale retirement

**Date:** 2026-06-13
**Status:** ACTIVE (multi-PR arc; this doc is the north star — update it as each workstream lands)
**Origin:** the pv=69 live plan-create failure (a 5-week PGE plan that cron-looped on a repeated `2026-06-28: no strength+strength on same day` payload reject in the Peak week, then hit the D-77 stall backstop → `failed` with a "contact support" error).
**Related:** [#576](https://github.com/ahorn885/exercise/pull/576) (observability — MERGED to `main`). Adjacent: [#572](https://github.com/ahorn885/exercise/issues/572)/[#575](https://github.com/ahorn885/exercise/issues/575) (refresh truncation + per-pass give-up), [#540](https://github.com/ahorn885/exercise/issues/540)/[#557](https://github.com/ahorn885/exercise/issues/557) (feasibility cascade), [#571](https://github.com/ahorn885/exercise/issues/571) (strength two-template + dose-cap-exempt failover), [#336](https://github.com/ahorn885/exercise/issues/336) (skill-capability gate).

This plan exists to prevent drift across a multi-PR effort where the **root cause is still partly pending live-log data**. It separates **DECIDED / ready-to-build** work from **PENDING-DATA / candidate** work, and records Andy's design decisions verbatim so a later session does not re-derive or contradict them.

---

## 1. Root-cause summary (what we know)

pv=69 is `created_via=plan_create`. The Peak week resolved **5 strength sessions** (Peak dose target = 1) because terrain/craft-constrained disciplines each fell to the cascade's **STRENGTH tier** (the dose-cap-exempt failover from #571 — "may push total strength higher… acceptable"). With the week strength-saturated and a fixed structural opportunity, two strength sessions collided on one day → the hard `Layer4Payload._check_two_per_day` invariant (`payload.py:611`) rejected the block. The per-block correction loop only re-asks the model (no deterministic repair), the seam reviewer kept re-synthesizing the boundary week, and the per-block **time** budget often couldn't fit a corrective retry → block-fumble → cron re-drive → D-77 stall backstop → `failed`.

**Two layers, and the crash is the louder one:**
- **(crash)** strength+strength on one day → hard reject → loop → stall-fail.
- **(quality)** even when it validates, a 5-strength Peak week is periodization-backwards.

**Open question (the real lever):** *why did so many disciplines fall to STRENGTH?* Andy's prior: "substitute equipments and terrains **should** have been present within the cluster" — i.e., the disciplines may have been **wrongly** marked infeasible. Possible causes: empty/under-populated cluster terrain/equipment maps, a `locale_terrain_ids` coercion drop, an empty/mis-resolved cluster (no home, or a stale **legacy locale** read as home). This is why the legacy-locale retirement (below) is in scope: it is a candidate *cause*, not just a UX cleanup.

---

## 2. Workstreams + sequencing

| WS | Title | Status | PR |
|----|-------|--------|----|
| A | Observability — feasibility/collision/source logging | **MERGED #576 + extended #577** | #576, #577 |
| B | Retire the legacy `LOCALES` enum | **DECIDED — build now** | this branch (`claude/locale-retirement`) |
| C | Onboarding: force build + tag a home locale | **DECIDED — next** | follow-up PR |
| D | Feasibility-correctness investigation | **PENDING** the logged re-run | — |
| E | Failover saturation fix (cap + reallocate + repair) | **PENDING DATA** | — |

**Sequence:** A (done) → B → C → (logged re-run reads WS-A output) → D diagnosis → E fix. B unblocks Andy immediately; C must follow B closely (B removes the implicit "home always exists"); D/E wait on real logs before any code.

---

## 3. Workstream A — Observability (MERGED, #576)

Shipped on `main`:
- `layer4/orchestrator.py` `_build_terrain_feasibility`: per-discipline **why** — required vs. available terrain (EXACT), proxies + fidelity + in-cluster (PROXY), indoor machines + in-pool (INDOOR), strength-pool size (STRENGTH), skill-gate toggle, craft status; plus the empty-cluster short-circuit and per-locale terrain/equipment maps.
- `locations.py` `cluster_terrain_by_locale`: raw `locale_terrain_ids` cell alongside the coerced set (catches "saved but didn't surface").
- `layer4/per_phase.py`: on a `_check_two_per_day` reject, dump each multi-session day's `kind/discipline_id/session_index_in_day`.
- `CLAUDE.md` **Rule #15 — Instrument as you build**.

**Extended on #577 (source-level "why" for all three failure types):**
- `locations.cluster_equipment_by_locale`: per-locale `gym_profile_id` link + tag count — equipment thinness attributable to "no gym profile linked" vs. a genuinely empty pool.
- `locations.cluster_locale_ids`: the two degenerate paths (no preferred/home → empty cluster; home without coords → single-locale cluster, radius sweep skipped) — catches a tiny/wrong cluster that looks normal downstream (incl. a stale legacy locale read as home).
- `layer2c/builder.py` skill block: loaded `skill_toggle_defs` + the athlete's `skill_toggle_states` + which off-toggles gate which disciplines — an **empty** defs set means `layer0.skill_capability_toggles` is unapplied (the gate silently no-ops), itself a finding.
- `layer4/per_phase.py` `_format_session_grid`: the deterministic `build_session_grid` per-(phase,week) allocation (`sessions_this_week × min` per discipline) — the **upstream half** of saturation (how many sessions the week wants, *before* feasibility turns infeasible ones to strength).
- `layer4/orchestrator.py` `_build_terrain_feasibility`: each discipline's **2A inclusion** status — feasibility is built on the included set, so a wrong include/exclude is root-upstream.

Together these give the full causal chain: **2A include → grid allocate → feasibility resolve → failover/collision**. Feed WS-D. Read on the next prod create via `/admin/logs` with `q=_build_terrain_feasibility` (incl. `2A_inclusion`), `q=cluster_terrain_by_locale`, `q=cluster_equipment_by_locale`, `q=cluster_locale_ids`, `q=layer2c skill-capability`, `q=build_session_grid`.

**Diag-token reachability (verified):** all of the above are `print()` → Vercel log drain → `vercel_logs` → readable via `GET /admin/logs?token=<DIAG_TOKEN>` (same gate as `/admin/plan/<id>/diag`), stored **verbatim** (no truncation). Caveats: (1) must be deployed to `main` (prod runs on `main`); (2) a log fires only when its path executes — the feasibility/grid/terrain/equipment/cluster + per-block-collision logs fire on any **cold plan-create**, but the `layer2c skill-capability` line fires only on a **cold cone/2C build** (silent if the cone is a cache hit).

**Known-but-unlogged suspects (add on demand if WS-D points there):** block cache-**key components** (only the hash is logged → the "re-synthesizes every drive" determinism / #202 question); 3B phase-structure derivation + per-phase volume/intensity band targets; 2D injury exclusions applied (wrist); LLM transient API errors (usually surface via the failure traceback).

---

## 4. Workstream B — Retire the legacy `LOCALES` enum (DECIDED)

**Decision (Andy 2026-06-13):** *"yes I want them gone. we should be only using the new locale type."* The 4 legacy slots (`LOCALES = ['home','hotel','partner','airport']`) are force-rendered and undeletable by design (Track 1 back-compat) — that is why deletion never stuck. Retire the enum entirely; locales become purely athlete-created (`locale_profiles` + `gym_profiles` + overrides), home = the `preferred` flag.

**Edit sites (`routes/locales.py`), mechanically:**
1. `:48` — remove the `LOCALES` constant (and its comment).
2. `~:282` choices builder — drive the `/references` where-available choices off `locale_profiles` rows only (drop the `for slug in LOCALES` prepend).
3. `:589–591` `list_profiles` — `displayed_locales = sorted(profiles.keys())`; drop `list(LOCALES) +`.
4. `:608` — stop passing `legacy_locales` to the template.
5. `~:621` `edit_profile` — remove the `locale not in LOCALES` special-case.
6. `:785` — `is_deletable=True` (drop the `locale not in LOCALES` gate).
7. `:1248` `delete_locale` — remove the `if locale in LOCALES: refuse` block.
8. `routes/onboarding.py:84` — remove `from routes.locales import LOCALES as LEGACY_LOCALES` and any use.
9. `templates/locales/list.html` (+ `edit` if it branches on `legacy_locales`) — remove legacy-slot rendering.

**Tests:** update/remove any asserting the 4 slots render or are non-deletable; add a test that a created locale is deletable and that no slots appear with zero rows. Run the locale + onboarding route suites.

**Out of scope for B:** the data side — if Andy has stale auto-created rows for those slugs, they're now deletable via the normal UI; no Neon write is needed from B (container can't reach Neon anyway).

**Success criteria:** `/locales` shows only athlete-created locales; each is deletable and stays deleted; `/references` where-available filter still works off real locales; onboarding still imports cleanly; full suite green.

---

## 5. Workstream C — Onboarding forced-home (DECIDED, follow-up PR)

**Decision (Andy 2026-06-13):** *"the user should just be forced to build and tag one as home during onboarding."*

The flow already has a `/onboarding/locales` step (`prefill → locales → skills → schedule`). Make that step **require** ≥1 locale built **and** one tagged home (`preferred`) before "continue" — replacing the current skippable behavior. Add the validation + a clear UI prompt; tests for the gate.

**Coupling with B:** B removes the enum's implicit "home always exists." Without C, a new user could reach plan-gen with **no home → empty cluster → the exact strength saturation we're chasing**. So land C close behind B; do not rely on retirement for the new-user home guarantee until C ships.

**Success criteria:** onboarding cannot complete without a home-tagged locale; existing users unaffected; suite green.

---

## 6. Workstream D — Feasibility-correctness investigation (PENDING the logged re-run)

After B/C and a prod re-run with WS-A logging, read per-discipline resolution + cluster maps. Decide which is true:
- **Maps populated, genuine gap** → the saturation is real infeasibility → WS-E (saturation policy) is the fix.
- **Maps thin/empty despite data present** → a read/coercion/cluster bug (e.g., legacy locale read as home, `_coerce_terrain_ids` dropping a shape, radius excluding the locale with terrain) → fix *that* (the bigger lever); WS-E becomes belt-and-suspenders.

**Verify:** we can name exactly why each discipline resolved to its tier.

---

## 7. Workstream E — Failover saturation fix (PENDING DATA — candidate only)

Do **not** implement until WS-D data is in. Recorded Andy decisions (held as design input, not yet ratified against data):
- **Cap = dose + 2** total strength/week (programmed + failover).
- **Over-cap failovers → `reallocate`** — note: in the cascade, `reallocate` is the *last* tier (only reached with no strength pool); STRENGTH is preferred over it. So "trim over-cap strength-subs to reallocate" is a **new weekly-saturation rule that overrides** the per-discipline strength>reallocate preference — not the existing tier firing.
- **Reallocation must respect VARIETY, not just feasibility.** Andy's failure mode: *"3 running + 3 attempted cycling, cycling infeasible → reallocated to running = 6 running"* is too little variety. The rule must distribute reallocated volume across feasible disciplines and cap how much any one discipline can absorb — not dump it all on the nearest one.
- **Deterministic repair is the Layer-3 crash guard** (Andy's pick over a prompt-only rule): on a `_check_two_per_day` strength+strength, relocate/drop the lower-priority strength before validation so a stray collision self-heals instead of re-rolling to the stall backstop.
- **Prefer deterministic defensive routes (Andy 2026-06-13):** *"I want as many of the defensive routes to be deterministic as makes sense. I don't want to create new likely failure modes."* The cap, the over-cap→reallocate trim, the variety distribution, and the collision repair should be **deterministic code**, not new LLM prompt-directives. The root failure was precisely an LLM-driven defensive route (the failover-as-prompt-directive intermittently emitting the collision); the fix must not swap one probabilistic failure mode for another. Reserve the LLM for composing session *content*; let code decide *which/where/how-many*. (Cross-cutting principle for this arc, not just WS-E.)

**Triggers:** the saturation policy + any prompt wording are **Trigger #1 (prompt) / #5 (cascade architecture)** — bring exact wording + the cap value + the variety rule for Andy's sign-off before editing.

**Success criteria:** an over-constrained athlete still reaches `ready` (no strength+strength; ≤ dose+2 strength/week; reallocated volume spread, not concentrated); a forced collision self-heals or fails fast rather than stalling.

---

## 8. Stop-and-ask gates

- WS-E wording / cap value / variety rule → **Trigger #1/#5**, explicit sign-off required.
- Any Neon migration (none currently owed) → owed-Andy's-hands (container can't reach Neon).
- WS-D conclusion may redirect WS-E scope — re-confirm the lever with Andy after the logs.

---

## 9. Read order for the next session (Rule #13)

`CLAUDE.md` (now incl. Rule #15) → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this plan → the latest handoff. This plan is the live tracker for the arc until all workstreams close.
