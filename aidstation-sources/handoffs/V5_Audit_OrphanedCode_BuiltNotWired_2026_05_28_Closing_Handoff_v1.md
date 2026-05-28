# Orphaned-code audit — built-but-not-wired sweep (Layers 1–4) — Closing Handoff

**Session:** Andy: "run comprehensive research against the application to see what data points and functions we built but somehow never wired in — things we inadvertently orphaned and that don't show up in our GitHub issues. During the plan-gen investigation we found numerous items in layers 2 and 3 already built but not actually USED. Find the rest. All of them." Ran a six-cluster parallel sweep of the whole pipeline; filed the findings as a GitHub epic + 13 sub-issues. Audit/tracking session — **no app code or specs changed.**
**Date:** 2026-05-28
**Predecessor handoff:** `V5_BacklogMigration_DocToGitHubIssues_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/admiring-thompson-Cp6wF`
**Status:** 0 substantive files (ceiling N/A). Deliverable = epic **#295** + sub-issues **#296–#308** + this handoff. ~30 distinct orphan clusters found, grep-verified.

---

## 1. Session-start verification (Rule #9)

Audit/research task, not an implementation pass, so the predecessor §8 anchor sweep was not the gate. The predecessor (backlog→issues migration) left the D-77 prod re-run owed on #201/#202; that remains owed and untouched here.

**Reconciliation note:** clean. No app code, specs, or housekeeping docs were modified this session. The orphan rubric below treats *the deployed wiring* (`layer4/orchestrator.py` + routes + Layer 4 prompt bodies) as the source of truth for "used," and the §H.2 / Layer-2E fixes are confirmed live (verified, see §2 non-findings).

---

## 2. Session narrative

**The bug class.** During D-77 we found Layer 3B's §H.2 goal fields and several Layer 2E classifications were *built but not USED* — the builder read them, but the orchestrator never supplied them (3B was hardcoded `goal_outcome="Finish"`, starving two HITL flags), or the output was computed and dropped. This session hunted the rest of that pattern across the whole pipeline.

**Method.** Six `general-purpose` agents in parallel, one per layer cluster (L1; 2A+2B; 2C+2D; 2E+modality; 3A+3B; Layer-4/RaceEvent glue), each with an identical rubric: for every payload field, builder input, and helper — read the builder, grep the whole repo (excluding `tests/`) for downstream reads, and trace inputs back through the orchestrator + routes. "Consumed" = read into a prompt body, the validator, a downstream builder, a route, or persistence. The verbose agent transcripts were kept out of the main context by delegating; the main thread independently re-grepped every HIGH finding (all confirmed).

**Key mechanical fact that makes the audit valid:** the Layer 4 prompt builders **cherry-pick** specific fields from the typed 2A/2B/2C/2D/2E/3A/3B/substitution payloads — they do *not* `model_dump` them wholesale (only `Layer1Payload` is dumped whole). So a payload field referenced nowhere in `layer4/`/`routes/` is a genuine orphan, not just "present in a JSON blob the LLM might read." Caveat recorded in the epic: the cached wrappers hash the *whole* payload (`compute_payload_hash`), so orphaned fields still perturb cache keys (the vector behind the `computed_at`/`as_of` non-determinism bugs, #202) — cache-surface area, not semantic consumption.

**Four flavors found:** **(A)** starved input / inert feature; **(B)** captured-but-not-threaded (athlete enters it, app ignores it — the §H.2 shape); **(C)** emitted-but-unconsumed builder output; **(D)** dead code.

**Three root causes:** (1) `coaching_flags` is a *systemically* dead channel — every Layer 2/3 builder emits flags, no Layer 4 prompt renders any (except the substitution payload's, which proves the pattern works); (2) builders shipped ahead of their consumers (the 3.5 gate + the richer prompt bodies that would read 2B/2D/2E detail were never built); (3) capture surfaces shipped ahead of threading (forms/columns landed; the orchestrator wiring didn't — the invalidation matrix even evicts caches on a field the brief never reads).

**Scope-pick gate (`AskUserQuestion`):** Andy chose **"File as GitHub issues"** over planning fixes / deleting dead code / report-only. No prompt or cross-layer code was touched (a fix to the cross-cutting flag channel is a Trigger #1 design pass).

---

## 3. File-by-file edits

**None.** No app code, specs, or housekeeping docs changed. The deliverable is the GitHub epic + sub-issues (§9) and this handoff. The full findings catalogue (with file:line evidence) lives in the issue bodies; reproduced compactly in §6 for a self-contained record.

---

## 4. Code / tests

None — no code or tests changed. The audit was read-only (`grep`/`Read`/agent reads).

---

## 5. Manual §5.0 verification steps

None to append. Each HIGH finding was verified by re-grep in-session (the issues cite the proof). No new walkthrough scenarios — these are code-wiring gaps, not UI behaviors, and the fixes (when scoped) will carry their own §5.0 steps.

---

## 6. Findings catalogue (the "all of this") + next pointers

Epic **[#295](https://github.com/ahorn885/exercise/issues/295)**. 13 grouped sub-issues, deduped against the 90 open issues. Grouped by layer/fix; each carries file:line + a checklist.

### Bucket A — starved inputs / inert features (logic that can never fire)
- **#296** Layer 2A `athlete_discipline_overrides` never threaded — builder docstring claims the orchestrator unpacks it from `discipline_weighting`; it never does (`orchestrator.py:267,:582`). Override-weight branch + `weight_override_divergence` flag + conditional include/exclude are inert.
- **#298** Layer 2C `cluster_gear_toggle_states={}` at both call sites (`orchestrator.py:312,:623`; `init_db.py:1925` documents the deferral) → toggle-driven pool expansion can never add equipment.
- **#305** Plan-gen: `ParsedIntent.triggers_2a..2e` cascade is inert — `triggers_2b_terrain`/`triggers_2e_nutrition` have zero readers; the other three render as prose only; **nothing gates a layer re-run** (`_upstream_full_cone` always runs all layers). The partial-update/selective-re-run differentiator depends on this.
- **#304** (partial) Layer 1 `experience_level`/`coaching_voice_preferences`/`travel_constraint` read by 5 prompt builders but hardcoded `None` (`layer1/builder.py:163-166`).

### Bucket B — captured-but-not-threaded (athlete enters it, app ignores it)
- **#303** `food_allergies` incl. `severity="anaphylaxis"` never reaches Layer 2E — only doc-comments downstream; `_emit_hitl_items` (`layer2e/builder.py:945`) returns `[]`. **SAFETY-relevant.** (`priority:high`)
- **#306** `RaceEventPayload.notes` (evicts the brief cache per `race_events_invalidation.py:17`, but the brief never reads it), `race_url`, `RouteLocale.lat/lng/mapbox_id` — stored, never threaded.
- **#302** (partial) `SleepRecord.sleep_quality` SELECTed in the integration substrate (`integration.py:178,217`) but never read by the 3A builder (+ 1–5 capture vs 1–10 model scale mismatch).
- **#304** Layer 1 `pack_load_history`, `network` + `disclosures` sub-trees, `event_goal.target_race_event_id` (dead duplicate of `RaceEventPayload`), `previous_coaching`, `altitude_exposure_count`, the `*_history` lists, `identity.notes`.

### Bucket C — emitted-but-unconsumed builder outputs (computed and dropped)
- **#297** Layer 2B — almost the whole payload; only `terrain_by_discipline` is read (`orchestrator.py:433` → substitution). `summary`/`race_terrain`/`terrain_gaps`/`coaching_flags` + per-block detail dropped.
- **#299** Layer 2D — the entire risk product: `discipline_risk_profiles`, `Evidence` (the "why-excluded" on every verdict), all 6 `coaching_flags`, `body_part_vocab_misses`. (Distinct from tracked #236/#238/#240/#242/#243/#244.)
- **#300** Layer 2E — `daily_nutrition_baseline` (full BMR/calorie/macro subtree), ~70% of `RaceDayFueling` (caffeine plan, formats, protein-after-hr, modifiers), all 6 `coaching_flags`, `sleep_dep_overlay`, `heat_acclim_adjustments`, `dietary_pattern_adjustments`, `supplement_integration`, `bmr_method/kcal`. (Missing-*consumer* gap is separate from the #218/#220 builder stubs.)
- **#301** Layer 2 modality — `TerrainEmphasis.{emphasis_score,gap_severity,proxy_methods,uncoverable_stimulus}` + flag `metadata` (adaptation-weeks); `race_craft` is a dup of `discipline_name`; `craft_substitution` enum value never emitted.
- **#298** Layer 2C — `coaching_flags`, `DisciplineCoverage` tier counts, several `ResolvedExercise`/`ResolutionDetail` sub-fields.
- **#296** Layer 2A — `rationale` (+ `rationale_metadata`, ~90-line template system), `coaching_flags`, `unresolved_flags`, `sleep_deprivation_relevant`.
- **#302** Layer 3 — 3A/3B `notable_observations` (write-only channel), `GoalViability.suggested_adjustments`/`confidence`/`evidence_basis`, `PeriodizationShape.reasoning_text`/`evidence_basis`.

### Bucket D — dead code (defined, never called)
- **#308** `layer4/telemetry.py` (entire module — `TelemetryAggregator`, `CallMetrics`; also orphans `SeamReview.reviewer_*` token/latency fields); `_section_completeness_estimate()` (`layer3a/builder.py:432`, ~75 lines); `evict_on_target_event_locale_change()` (`race_events_invalidation.py:93`); hardcoded-empty/unemitted `condition_vocab_misses` / `discipline_relevance_assessed` / `craft_substitution`.

### Cross-cutting
- **#307** `coaching_flags` is a systemically dead channel across Layers 2–3 — **high-leverage:** one generic render block in the Layer 4 prompts (modeled on the substitution-flag render that already works) un-orphans the flag surfaces in #296/#297/#298/#299/#300 at once. Trigger #1 (prompt design) before code.

### 6.1 Architect-recommended next forward move
Triage, not a blind fix-all. Order: **#303** first (the only safety-relevant one — allergens/anaphylaxis bypassing the nutrition layer). Then **#307** (cheap, high-leverage, but a Trigger #1 design pass — scope the flag-render block, get sign-off). Then **#305** (the inert selective-re-run cascade — closest to a *claimed differentiator that silently doesn't work*). Then **#308** (low-risk dead-code deletion — its own PR with tests). The richer Bucket-C surfaces (**#300** overlays, **#302** observations) need new prompt design and partly overlap deliberately-deferred consumers — make the "deferred vs accidental" call per item before building.

### 6.2 Alternative pivots
Unchanged from the predecessor: epic **#201** (D-77 convergence) is still the live fire, gated on Andy's owed PGE re-run; **#202** cone cache-key audit; high-priority `status:designed` builds **#213**/**#214**. This audit is orthogonal and can interleave.

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules (backlog = GitHub issues).
2. `CURRENT_STATE.md` + `CARRY_FORWARD.md`.
3. Browse epic **#295** and its sub-issues #296–#308 (filter `label:type:bug` / `label:layer:*`).
4. This handoff, then `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Hunt the full "built-but-not-used" pattern pipeline-wide (not just L2/L3) | Andy | "Find the rest. All of them." |
| 2 | Six parallel per-layer agents + main-thread re-grep of every HIGH | Claude | Keeps verbose transcripts out of context; independent verification |
| 3 | Group ~30 findings into 13 layer/fix sub-issues (not 1-per-field, not one mega-issue) | Claude | Each independently actionable; matches the issues-as-backlog workflow without noise |
| 4 | **File as GitHub issues** (over plan-fixes / delete-dead-code / report-only) | Andy (`AskUserQuestion`) | Issues are the SSOT; no prompt/cross-layer code touched (Trigger #1) |
| 5 | Treat `coaching_flags` orphaning as one cross-cutting issue (#307) | Claude | One render block fixes five layers' flag surfaces |
| 6 | Surface findings that sit under broad epics (#246/#210) but aren't filed individually | Claude | They're concrete unwired instances, not the epic's framing |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| Epic #295 created, labelled `epic`/`v2`/`type:bug`/`priority:med` | ✅ `issue_write` create |
| 13 sub-issues #296–#308 created | ✅ create responses |
| All 13 linked to #295 as sub-issues | ✅ 13× `sub_issue_write` returned parent #295 |
| `layer:2b`/`layer:2c` confirmed non-existent → layer carried in titles, not labels | ✅ `get_label` (404) |
| Deduped against 90 open issues; related-but-distinct (#202/#213/#218/#220/#237) noted | ✅ `list_issues` |
| HIGH findings re-grepped in-session (L2D risk product, L2C/L2D/L2E flags, 2B unread, 2A overrides, daily_nutrition_baseline, ParsedIntent triggers, telemetry, evict_locale, notes, sleep_quality) | ✅ Bash grep |
| Non-findings verified wired (§H.2 threaded; `Layer2Bundle.{a..e}`; `data_density`; `acwr.per_discipline`; weather lat/lng) | ✅ grep + agent traces |
| No app code/spec modified | ✅ git status (only this handoff new) |

---

## 9. Files shipped this session

**Substantive (0 files):** none — read-only audit; no app code or specs.

**Bookkeeping (1 file):**
1. this handoff (`V5_Audit_OrphanedCode_BuiltNotWired_2026_05_28_Closing_Handoff_v1.md`)

**GitHub (not files):** epic **#295** + sub-issues **#296–#308** in `ahorn885/exercise`.

---

## 10. Carry-forward updates

**Owed (not done unilaterally — large rolling-state files; defer to Andy):** bump `CURRENT_STATE.md` "Last shipped session" to this handoff, and (optionally) note epic #295 in `CARRY_FORWARD.md`. Not edited this session because the user asked for "a handoff," and the audit's tracked output already lives in issues. No §5.0 walkthrough or owed-deploy items added (no code shipped).

---

**End of handoff.**
