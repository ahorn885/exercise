# V5 Implementation — T-1.4 (taper tolerance) + WS-2 (all 7 render/trim tasks + T-2.9 bump) + T-3.2 (#831 verify) + T-3.3 (team-only gate) — Closing Handoff (2026-07-01)

**Session:** Continuation of `PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` §4 Global order, after T-5.7 (real-DB cardio-ingest test, WS-5 closed out — no PR yet at that point).
**Date:** 2026-07-01
**Plan doc:** [`plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md) — T-1.4, all of WS-2, T-3.2, T-3.3
**Predecessor handoff:** [`V5_Implementation_T57_RealDBCardioIngestTest_WS5Closed_2026_07_01_Closing_Handoff_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/handoffs/V5_Implementation_T57_RealDBCardioIngestTest_WS5Closed_2026_07_01_Closing_Handoff_v1.md)
**Branch:** `claude/project-handoff-execution-cijxz8` — merged to `main` this session (Andy's go: "merge the work").
**Status:** Every task this session touched is DONE, verified, or explicitly deferred by Andy's own choice (T-2.9's real-LLM walk). Suite: **4176 passed / 49 skipped, 0 failed** (+7 over the T-5.7 baseline of 4169/49).

---

## 1. Session-start context

Prior to this session, WS-5 (Integrations) had just closed out (T-5.7). Every other plan task was Andy-gated. This session's work happened in direct chat with Andy (not `/plan` mode) — he was asked plain-language questions for each gate, and this handoff records exactly what he ratified.

## 2. What shipped

### T-1.4/#930 — One-sided taper tolerance in the week-seam reviewer — **DONE**

Andy approved the exact proposed wording verbatim: *"a volume drop steeper than the planned descent is acceptable for long/ultra events... A taper that drops LESS than planned (under-taper) → flagged_major."* Added as a new CALIBRATION ANCHORS bullet in `layer4/week_seam_review.py::SYSTEM_PROMPT` (there was **no** existing Taper anchor in the runtime prompt — the design doc's own Taper bullet had drifted out of sync with runtime; both are now in sync). New `TestTaperAnchor` class in `tests/test_layer4_week_seam_review.py` (2 tests) — since the reviewer's actual verdict is real-LLM-judged (not mechanically testable), these pin the two things that are: the anchor states both directions in one bullet, and `render_week_seam_prompt` surfaces "Taper phase" + the planned descent ratio.

### WS-2 — Upstream-signal wiring — **ALL 7 TASKS DONE**

Andy ratified the render/trim table via plain-language chat questions (not the plan's original recommended-defaults table verbatim — two corrections surfaced during verification, both brought back to Andy before building):

- **T-2.1/#297 — TRIM.** The plan's own field name was wrong: `Layer2BPayload.terrain_by_discipline` is NOT dead (a real reader: `layer2_modality/substitution.py`). The actually-dead surface was `Layer2BPayload.summary`, the flat top-level `.race_terrain`/`.terrain_gaps` (Layer2BDisciplineBlock's per-block `.terrain_gaps` and `terrain_by_discipline` itself were kept alive), and the `Layer2BSummaryBlock` class entirely. Also found `Layer2BPayload.coaching_flags` is actually rendered already (`format_upstream_coaching_flags`, #307) — contradicting issue #297's own "0 reads" claim — so it was explicitly NOT trimmed. `discipline_relevance_assessed` (the issue's 3rd trim target) doesn't exist in code, only in planning docs — left alone per "don't guess a replacement."
- **T-2.2/#299 — resolved as a no-op.** Andy said "trim" in chat, but verification found a real reader outside Layer 4 (`layer3d/gate.py` reads `discipline_risk_profiles` for the HITL gate) — deleting it would break Layer 3D. Brought back to Andy: he confirmed leaving it alone (it was never rendered in a Layer 4 prompt to begin with, so there's nothing to trim without breaking something that already works).
- **T-2.3/#301 — RENDER, from a corrected location.** The plan named `TrainingSubstitution.uncoverable_stimulus`/`proxy_methods` — those fields don't exist on that class. The real fields live on `TerrainGap` (`layer4/context.py`), reachable via `Layer2BPayload.terrain_by_discipline[].terrain_gaps[]`. Andy approved building from the real location. New `format_terrain_gap_detail()` helper in `layer4/per_phase.py`, wired into all 5 render sites (per_phase, single_session, race_week_brief, the shared `plan_refresh.py` refresh-append point). Confirmed `ParsedIntent.triggers_2b_terrain` (R2) needs no new wiring: Layer 2B is unconditionally recomputed on every refresh regardless of any trigger flag (traced the call chain: `routes/plan_refresh.py` → `orchestrator.orchestrate_plan_refresh` → `_upstream_full_cone` → `layer2b/builder.py`) — no cache-skip path exists to go stale. (Flagged as a separate, pre-existing observation: `triggers_2b_terrain` and its siblings look like dead/render-only code outside this task's scope — not fixed, just noted.)
- **T-2.4/#302 — RENDER, per_phase only.** `goal_viability.reasoning_text` was already rendered in `race_week_brief.py`; the gap was per_phase.py specifically. Added there, confirmed the other 4 sites genuinely didn't need it.
- **T-2.5/#302 — TRIM.** `Layer3BPayload.notable_observations` (a different class from Layer4's own `Observation`/T-1.1 surface — do not confuse the two) confirmed zero real readers; removed the field, its producer code in `layer3b/builder.py`, and the `_NOTABLE_OBSERVATIONS_MAX` budget-cap machinery that existed only to serve it.
- **T-2.6/#302 — sleep_quality scale, data fix.** A real live bug, not just cleanup: the wellness check-in form captures `sleep_quality` on a 1–5 scale, but the value flowed unconverted into `SleepRecord`, and everything downstream (the payload's own `ge=1,le=10` validation, `layer3a/builder.py`'s `.../10` prompt rendering) already assumed 1–10. A "4/5" (great sleep) was reading to the coaching AI as "4/10" (below average) — backwards. Fixed by doubling the raw value at the read site (`q_layer3A_recent_self_report_sleep`).
- **T-2.7/#306 — RENDER, race_week_brief only.** `race_url` added alongside the existing `notes`/`distance`/`duration` block; confirmed absent from all other sites (ground truth: "notes + locale already render; only race_url is missing" held).
- **T-2.9/R1 — bump DONE, walk STILL OWED (Andy's deliberate call).** `LAYER4_PROMPT_REVISION` "20" → "21" once, comment names #301/#302/#306. Andy: wants to land more changes before running the one real-LLM walk, rather than walk after every session. Walk checklist written into the plan doc §3 T-2.9 as-built note for whenever he's ready.

### T-3.2/#831 — Prevent double-strength-same-day crash — **VERIFIED ALREADY FIXED, no build; issue closed**

Andy: "verify, but spend time making sure the fix doesn't lead to new failure routes" rather than build fresh (he was already confident it was fixed). Investigation confirmed: #831's own issue body already documents its fix as done (`_normalize_day_composition`, `layer4/per_phase.py:3385`, called pre-validation at `:4024`). Traced it line-by-line against `Layer4Payload._check_two_per_day` (`payload.py:681-718`) to confirm the two independently-maintained implementations currently agree on every clause — not just trusting the docstring. Existing regression coverage (`tests/test_layer4_day_composition_normalizer.py`, 14 tests incl. the exact plan-78 scenario) already locks this in. No new failure mode found in the interaction with #590's saturation cap (different pipeline stages: weekly capacity vs. per-day placement; the normalizer's shape-agnostic derivation catches any violation regardless of how session counts arose upstream). One non-code risk flagged for the record: the normalizer and the validator are separately-maintained — a future edit to one without the other could reopen this bug class.

**Closed 2026-07-01:** the issue's own text called for a formal live-verify (regenerate plan #78 in prod, check `/admin/logs`) — not formally done, but Andy is now on plan #84 and hasn't hit this failure class since. Closed `completed` on that basis.

### T-3.3/#559 — Team-only sport gate for solo athletes — **DONE, migration applied to prod**

Andy's design call (asked in chat before building, since there was no existing solo/team concept anywhere): "solo" derives from existing data — an athlete counts as on a team if they have an `athlete_network_links` row with `relationship_types` containing `"race_teammate"`; no such link means solo. No new onboarding question.

**Built:**
- `Layer1Payload.is_solo_athlete: bool` (default `True`), computed in `layer1/builder.py` from the already-loaded `network_links` (no new query), following the exact `doubles_feasible`/`owned_gear` top-level-convenience-field pattern.
- Migration `etl/migrations/layer0/0038_disciplines_requires_team.sql` — `layer0.disciplines.requires_team boolean NOT NULL DEFAULT false` (cache-neutral, no `etl_version` bump). **Every row ships `false`** — investigated `layer0.sports.team_vs_solo` + `layer0.team_formats` for a discipline backed only by a team-mandatory sport with no solo variant; found none (every discipline the two team-mandatory sports — Adventure Racing, Swimrun — use is also practiced solo elsewhere in the canon). Per the task's own "don't hardcode a guess" rule, left all-`false` and flagged which discipline_id(s), if any, should flip to `true` as an open follow-up decision (full evidence trail in the migration's own comment).
- `layer2a/builder.py::_resolve_inclusion` gets a new tier-0 hard gate, outranking the existing race/athlete/curator precedence chain: `requires_team` + `is_solo_athlete` → excluded. Threaded as its own new `is_solo_athlete` parameter (not overloaded onto the existing-but-inert `team_format` parameter — race format vs. athlete's own team membership are different signals).

**Migration applied to prod this session:** triggered `layer0-apply.yml` against this branch (ref `claude/project-handoff-execution-cijxz8`, so it picked up migration 0038 pre-merge); Andy one-tap approved the `production` environment gate; workflow run [28533587192](https://github.com/ahorn885/exercise/actions/runs/28533587192) succeeded. `requires_team` is now live on prod Neon, all rows `false` — the gate is live but currently inert pending the discipline-flagging follow-up decision above.

## 3. Tests

Full suite: **4176 passed / 49 skipped, 0 failed** (baseline 4169/49 at session start → +7 net: T-1.4 +2, T-2.1 −2/+0 net (2 tests deleted, described above), T-2.6 (extended existing test, no net count change reported separately), T-2.3/T-2.4/T-2.7 +24 in new `tests/test_layer4_structured_cardio_337.py` plus T-2.5's trim removing some — net reconciles to +9 across the WS-2 commit, T-3.3 +3). Each task's commit ran the full suite before/after independently; every commit message and the plan doc's as-built notes carry the exact per-task deltas. `ruff check` on every touched file across all commits — 0 new findings (several pre-existing findings confirmed unchanged via `git stash` diff at each step).

## 4. Docs updated (this session)

- `plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` — T-1.4, all WS-2 tasks (table + per-task as-built notes), T-2.9, T-3.2, T-3.3 all updated in place with as-built notes; §4 Global order updated throughout.
- `CURRENT_STATE.md` — new "Last shipped session" entry (this one); prior top entry (T-5.7) demoted to a named predecessor entry.

## 5. GitHub bookkeeping (this session)

- **#754** — already closed in the predecessor session (T-5.7); no change this session.
- **#831 — commented + closed** (`completed`): re-verification findings + Andy's plan-#84 confirmation.
- No new issues filed this session (the #1125 CI-wiring fast-follow was filed in the predecessor T-5.7 session).
- Plan doc updated in-place per above (exempt from the 5-file ceiling as bookkeeping).

## 6. Merge

Andy's instruction this session: **"merge the work."** This branch (`claude/project-handoff-execution-cijxz8`) was opened as a PR and merged to `main` — see the PR link in this session's chat reply for the exact number. All 8 commits from T-1.4 through T-3.3 (plus the earlier T-5.7 work already on this branch) landed together.

## 7. Next session pointers

Every task in the plan that had a clear go/no-go from Andy this session is now resolved. What's left:

- **T-2.9's real-LLM walk** — Andy is deliberately deferring this until more changes land first (his call, not a blocker on anything else). The walk checklist is in the plan doc §3 T-2.9 as-built note, ready whenever he wants to run it.
- **T-3.3's discipline-flagging follow-up** — which `discipline_id`(s), if any, should get `requires_team=true`. Open, not decided this session (see the migration's own comment for the evidence already gathered).
- **T-1.5 (#847, week-seam auto-resynth)** — now unblocked by T-1.4 (R3 precondition met). Not started this session — it's the plan's own "most complex task," flagged as needing full step-by-step care.
- **T-3.1 (#1060, delete impossible sleep-dep advisory)** — small, `GATE: none` (its prompt-content effect rides T-2.9's walk, doesn't need its own). Not started this session.
- **#1125** (CI-wiring fast-follow from the T-5.7 session) — still open, ungated.
- Everything else (WS-2 render/trim table is now fully ratified and built, so nothing there is still gated) is closed out.

### Operating notes (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`
6. `bash aidstation-sources/scripts/verify-handoff.sh`

---

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Taper anchor | `layer4/week_seam_review.py` | `- TAPER week: a volume drop steeper than the planned descent` in `SYSTEM_PROMPT` |
| Taper anchor doc | `aidstation-sources/prompts/Layer4_WeekSeamReviewer_v1.md` | "2026-07-01 addendum (#930/T-1.4)" |
| Layer2B trim | `layer4/context.py` | `Layer2BSummaryBlock` absent; `Layer2BPayload.coaching_flags` present; `terrain_by_discipline` present |
| Terrain-gap render | `layer4/per_phase.py` | `def format_terrain_gap_detail(` |
| Goal-viability render | `layer4/per_phase.py` | `Goal viability reasoning:` |
| 3B trim | `layer4/context.py` | `Layer3BPayload` has no `notable_observations` field |
| Sleep-scale fix | `layer3a/integration.py` | `sleep_quality=raw_quality * 2 if raw_quality is not None else None` |
| race_url render | `layer4/race_week_brief.py` | `**Race URL:**` |
| Prompt revision | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "21"` |
| #831 normalizer | `layer4/per_phase.py` | `def _normalize_day_composition(` |
| Solo-athlete flag | `layer4/context.py` | `is_solo_athlete: bool = True` on `Layer1Payload` |
| Team migration | `etl/migrations/layer0/0038_disciplines_requires_team.sql` | applied to prod, run 28533587192 |
| Layer 2A gate | `layer2a/builder.py` | `# 0. Hard team-requirement gate` in `_resolve_inclusion` |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 4176 passed / 49 skipped |
| GitHub | — | #831 closed `completed` |
| Plan doc | `plans/PlanGenReliability_..._v1.md` | T-1.4/WS-2(all)/T-2.9/T-3.2/T-3.3 all show as-built notes |
| Branch | — | `claude/project-handoff-execution-cijxz8`, merged to `main` this session |

**End of handoff.**
