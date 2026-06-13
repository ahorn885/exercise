# V5 Implementation — pv=69/70 feasibility-saturation arc: observability, strength+strength crash-guard, craft-model correction (Closing Handoff)

**Date:** 2026-06-13
**Branches/PRs (all squash-merged to `main` unless noted):**
- [#576](https://github.com/ahorn885/exercise/pull/576) — Layer 4 observability (feasibility cascade + per-day collision logging) + CLAUDE.md **Rule #15**.
- [#577](https://github.com/ahorn885/exercise/pull/577) — complete source-level observability (3B/2A/grid/cluster/terrain/equipment/skill/cache-key/API-error) + the anti-drift plan doc.
- [#579](https://github.com/ahorn885/exercise/pull/579) — deterministic **strength+strength repair** (crash-guard).
- [#578](https://github.com/ahorn885/exercise/pull/578) — craft-from-equipment (Slice V5 surgical) — **MERGED then REVERTED**.
- [#580](https://github.com/ahorn885/exercise/pull/580) — **revert of #578** + corrected craft model in the plan + this closeout.

**North-star plan:** `aidstation-sources/plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (WS-A…V — keep it current as each workstream lands).
**New issues filed:** [#581](https://github.com/ahorn885/exercise/issues/581) (craft athlete-owned model — the **immediate next**), [#582](https://github.com/ahorn885/exercise/issues/582) (retire `LOCALES`), [#583](https://github.com/ahorn885/exercise/issues/583) (onboarding forced-home + craft capture, under epic #246), [#584](https://github.com/ahorn885/exercise/issues/584) (saturation policy).

---

## 1. What this session was

Andy ran live plan-creates (**pv=69**, then **pv=70**) and asked me to watch them. The watch (via the token-gated `/admin/plan/<id>/diag` + the `/admin/logs?token=` reader — Rule #14) caught a real, deterministic failure: the plan **stall-failed** (D-77 backstop) cron-looping on `<date>: no strength+strength on same day`. We instrumented the entire plan-gen decision surface, diagnosed the root cause from the logs, fixed the crash deterministically, and **corrected a craft-model design error** mid-flight (Andy's call).

## 2. Root cause (proven live on pv=70)

The Peak/Build weeks were **strength-saturated**: bike/paddle disciplines (D-008 Mountain Biking, grid-allocated **5×**; D-009 Packrafting) **craft-failed to STRENGTH** even though terrain + indoor trainers were present and the athlete owns the bikes. The craft axis reads the **athlete-level capture columns** (`bike_types_available`/`paddle_craft_types`, "set B") which were **empty**, while the bikes/boats were entered as **location equipment** ("set C"). 5 MTB-strength + packraft-strength + climbing (skill-gate) = 7 strength/week → two strength on one day → the hard `Layer4Payload._check_two_per_day` reject → per-block budget exhausted → block-fumble → cron re-drive → stall-fail. The multi-session-day log proved it verbatim: `strength/D-008/idx0, strength/D-008/idx1`.

## 3. What shipped

- **Observability (#576/#577) — MERGED.** Full causal chain now logged + readable via `/admin/logs?token=`: `q=plan_create 3B phase_structure`, `2A_inclusion`, `build_session_grid`, `cluster_locale_ids`, `cluster_terrain_by_locale`, `cluster_equipment_by_locale`, `layer2c skill-capability`, `_build_terrain_feasibility` (per-discipline tier + why), `compute_block_cache_key`, `synthesize_phase` (incl. `multi-session days` collision detail), `anthropic.APIError`. **Rule #15 (Instrument as you build)** added to CLAUDE.md.
- **Strength+strength crash-guard (#579) — MERGED.** `per_phase._repair_strength_collisions`: before validation, relocate a colliding 2nd strength onto a single non-hard cardio day (else drop). Deterministic; a collision now self-heals instead of looping to the stall backstop. Scoped to strength+strength.

## 4. The craft-model correction (the key decision)

#578 fixed the saturation surgically by deriving craft ownership from the **per-locale equipment inventory** (∪ set B). Andy then identified the conceptual error: **craft is athlete-owned portable gear, scoped to the athlete — not a location.** #578 was **reverted (#580)**. The decided model:
- **Canonical store = the athlete-level capture (set B)**, available across the whole **home-cluster** by default.
- **Away availability is explicit:** **(b)** a craft↔location association + **(c)** a craft attached to a travel event.
- (Corrects a misread: `Vocabulary_TargetState_and_Plan_v1` Slice V5 = source the craft *picker's option vocab* from the `equipment_items` catalog — **not** source ownership from location equipment.)

## 5. OWED / next steps (priority order)

1. **[#581] WS-G — athlete-owned craft store + home-cluster-wide (HIGH, the immediate next; this handoff's headline).** Make set B the canonical craft source, confirm/lock home-cluster-wide availability in the cascade, and ensure it's populated (the `/profile` → "Gear" form already writes it). **For Andy specifically:** after #580 deploys, his set B is empty → MTB/packraft will craft-fail again (no crash, #579 guards it) until he ticks his bikes/packraft in **Gear** (profile Athlete tab) — then a re-run resolves them to rides. Then **WS-H** (away (b)+(c) — new schema/UI, design first).
2. **[#583] WS-C — onboarding forced-home + craft capture** (under epic #246); **[#582] WS-B — retire the legacy `LOCALES` enum** (coupled).
3. **[#584] WS-E2 — saturation policy (dose+2 cap + reallocate-with-variety)** — lower priority now G + #579 cover the live issue.
4. **OWED (carried, NOT done this session): the post-#572 live T3-refresh re-verify.** This session watched *create* plans (pv=69/70), not a T3 *refresh* — so the CARRY_FORWARD T3 re-verify is still owed. Re-run a **T3 refresh** on prod and confirm `ready` + phase-correct `total_sessions`.
5. **No Neon migration owed** by this session's merged work (logging + crash-guard + revert are code-only). WS-H *will* need DDL (craft↔location, craft↔event) — owed-Andy's-hands.

## 6. Verification
- #576/#577/#579/#580 all CI-green (Python unit suite + Layer 0 gate + JS harness) at merge; local targeted suites green (craft 18, wiring+orchestrator 95/108, plan_create+payload 183, repair 5).
- pv=70 logs confirmed the full causal chain end-to-end (the diagnosis is evidence-based, not inferred).

## 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules (now incl. **Rule #15**).
2. `CURRENT_STATE.md` — top entry is this arc; focus = **#581 athlete-owned craft (WS-G)**.
3. `CARRY_FORWARD.md` — the craft section is **superseded** by this arc (see the new "#540 craft axis — REOPENED" note); T3 re-verify still owed.
4. This handoff.
5. The plan doc `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (the live arc tracker).
6. `./scripts/verify-handoff.sh`.

**Diag/log recipe (used all session):** `web_fetch_vercel_url("https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=<DIAG_TOKEN>")` for generation state; `…/admin/logs?token=<DIAG_TOKEN>&q=<substr>&minutes=N` for the verbatim drained `print()` logs (full-fidelity, unlike the runtime-log MCP). `DIAG_TOKEN` in the 2026-05-31 DiagAuthGate handoff §6.1.1.

## 7. Stop-and-asks this session
- **Fix-vs-design on craft (Trigger #5).** Surfaced the craft set-B/C drift + the candidate fix; Andy reconsidered and corrected the *model* (athlete-owned, not location). #578 reverted rather than kept-as-bridge (his call).
- **Logging scope.** Andy directed "add them all" — full decision-surface instrumentation shipped (#577).
- **Saturation-fix scope.** Deterministic-only (his principle: don't trade one LLM failure mode for another).

## 8. §8 anchor table (Rule #10)

| Area | Path | Anchor / check |
| --- | --- | --- |
| Rule #15 | `aidstation-sources/CLAUDE.md` | `### Rule #15 — Instrument as you build` |
| Feasibility cascade log | `layer4/orchestrator.py` | `_build_terrain_feasibility` per-discipline `feasibility[...]` + `2A_inclusion` prints |
| Terrain map raw cells | `locations.py` | `cluster_terrain_by_locale` `raw=… coerced=…` print; `cluster_equipment_by_locale` gym_profile_id; `cluster_locale_ids` degenerate-path prints |
| Skill source log | `layer2c/builder.py` | `layer2c skill-capability: toggle_defs=… toggle_states=…` |
| Grid log | `layer4/per_phase.py` | `build_session_grid: <phase>:w<n> … allocations=[…]` |
| Cache-key chain | `layer4/plan_create.py` | `compute_block_cache_key: … prev_accepted_output_hash=…` |
| LLM API error | `llm_invocation.py` | `except anthropic.APIError` → `invoke_tool_call: … anthropic.APIError` print |
| Crash-guard | `layer4/per_phase.py` | `def _repair_strength_collisions(`; called before `latest_sessions = sessions` |
| Craft source (reverted to) | `layer4/orchestrator.py` | `owned_crafts = _collect_athlete_crafts(cone.layer1_payload)` (the equipment-derivation is GONE) |
| Plan/north-star | `aidstation-sources/plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` | WS-A…V table; WS-G/H = #581 |
