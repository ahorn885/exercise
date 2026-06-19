# #698 Track 2 — cardio drills pool + Technical/Skill cull: DESIGN v1 + §6a reliability guardrails — Closing Handoff

**Session:** Design-only. Opened **#698 Track 2** (the follow-on to the now-closed Track 1 recovery-session arc, PR #730). Wrote the ratified design doc, then — at Andy's prompt ("how do we de-risk so the LLM is unlikely to stumble/fail?") — added a **§6a LLM-reliability guardrails** section + a **one-drill-per-session hard cap**. No code; this is a spec for the next build session (Part B first).
**Date:** 2026-06-19 (Track 2 design ratified 2026-06-18; guardrails + cap ratified 2026-06-19)
**Predecessor handoff:** `V5_Implementation_RecoverySessionKind_RaceWeekBriefRecovery_698_2026_06_18_Closing_Handoff_v1.md` (Track 1 close)
**Branches/PRs (all MERGED, squash, auto-merge):**
- **#734** — design v1 (the doc + CURRENT_STATE pointer). Branch `claude/recovery-session-deterministic-placement-8m9mzn`. (Had a `dirty` merge-conflict against main — concurrent #681 provider sessions #723/#733 moved main + both touched the `CURRENT_STATE.md` "Last shipped" pointer; resolved by keeping the Track 2 entry on top + threading the provider entries below as predecessors, no content lost.)
- **#736** — §6a guardrails + `maxItems:1` cap (design amendment, in place on v1). Same branch. (Add/add conflict on the design doc vs main's squashed v1 — resolved `--ours`, my branch is the strict superset.)
- **This bookkeeping PR** — CURRENT_STATE "Last shipped" refresh + this handoff + #698 comment.

---

## 1. What shipped — design only

New design doc `designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v1.md` (14-section standard, mirrors the recovery design v2). Two coupled parts:

- **Part A — cardio drills "consider these" pool.** Today `cardio_blocks` are free-composed; there's no cardio analog of `_format_strength_exercise_pool`, so the structured cardio `0B` catalog (65 Technical/Skill + 8 Interval/Tempo + 4 Aerobic/Endurance active rows) is **dead catalog**. Part A adds a `cardio_drills[]` session block — the `recovery_exercises[]` structural analog (pool fn → enum-bind → validator membership → render) — discipline-weighted + Base-emphasized.
- **Part B — Technical/Skill cull.** A row-by-row audit (Trigger #2 → layer0 migration). **Reframe (load-bearing):** the 65 Technical/Skill rows are overwhelmingly **legitimate, high-value underserved-discipline drills** (paddle strokes, ski/climb/descent technique, swim drills). So Part B is an **asset inventory + narrow hygiene cull, NOT a mass deletion**; the survivors are Part A's pool source.

## 2. Ratified decisions (Andy)

- **Sequencing (06-18):** **Part B (cull) → Part A (pool)** — the pool draws from the surviving rows, so the catalog is cleaned + discipline-tagged first.
- **Binding (06-18):** **enforced enum-bound** (Andy chose this over my advisory rec). Reconciled in §7: enforcement binds the drill **vocabulary** (any named drill ∈ a discipline/phase-appropriate pool), **not** the **presence** of drills — `cardio_blocks` volume/zones stay LLM-composed.
- **One drill per session (06-19):** **hard cap `maxItems:1`** — tool-schema cap + pydantic `len ≤ 1`. One technical focus per session, not a drill circuit. Also the smallest possible failure surface.
- **§6a guardrails G1–G8 (06-19):** see §3.

## 3. §6a — LLM-reliability guardrails (the de-risk plan)

The enforced enum-bound mechanism is inherited verbatim from the shipped `strength_exercises`/`recovery_exercises` pattern, so the model **cannot emit an out-of-pool id** and drills carry **only one** validator blocker (membership) with **no placement rule** — *hard*-failure is already unlikely. The guardrails target the residual *unfillable ask* (hard-fail) and *wrong pick* (soft-stumble):

- **Tier 1 — kill hard-fail/churn.** G1 optional + pool-derived prompt (an optional field can't be unfillable; prompt never names a specific drill the enum might lack). G2 exactly one membership blocker — no discipline-match/count validator rule. G3 validate the `only-on-cardio` + `≤1` invariants **inside the per-session try/except** → `schema_violation` retry, not a 500 (carries the race-week-brief `_check_two_per_day`-outside-try/except lesson).
- **Tier 2 — kill soft-stumble.** G4 legible capped render (group by the athlete's discipline, carry each row's `coaching_cue`, ≤12 rendered, ≤1 per session). G5 discipline-scope via prompt, not a rule (a swim drill on a run session is a quality nit, not a failure; tighten to a soft `severity=warning` check only if it bites live). G6 Part B clean-enum-first (garbage-in → garbage-pick).
- **Tier 3 — bound the blast radius.** G7 Rule #15 logging at the pool boundary (computed pool ids+discipline+phase + any reject detail). G8 keep drills out of the volume/ACWR/band math.

## 4. NEXT — Part B Slice §3a (build first), per design §3 / §13a

**B1 — audit + cull migration.** Read-only audit of all 65 active `Technical/Skill` rows (+ 8 Interval/Tempo + 4 Aerobic/Endurance) → a per-row disposition table appended to the design as **§3a**, **ratified by Andy before the migration** (no cull without review). Buckets: (1) KEEP + discipline-tag (expected majority); (2) HYGIENE-FIX the 13 conflation rows (skill/discipline tokens mis-filed in `equipment_required` — `Climbing — roped` ×8 → skill-capability #336; `Touring/AT ski setup` ×4 + `Mountaineering` ×1 → terrain/discipline); (3) CULL the few genuinely non-prescribable rows (e.g. candidates `EX094 Packraft Inflation/Deflation`, `EX123 Pack Fit Optimization` — gear-handling, not a session). Migration supersedes culls (`superseded_at`, not hard-delete) + repoints inbound `physical_proxies`/substitutes. Validates against the CI layer0 gate. Bookkeeping + `etl/` only.

**Then Part A:** A1 schema (`payload.py` `CardioDrill` + field + `maxItems:1` invariants) → A2 pool+prompt+cache (`per_phase.py` `compute_cardio_drill_pool_ids` + `_format_cardio_drill_pool` + `# Cardio drills` section; `hashing.py` `LAYER4_PROMPT_REVISION "10"→"11"`) → A3 validator+render (`validator.py` `_rule_cardio_drill_pool_membership`; `templates/plan_create/view.html` + CSS).

## 5. Still-OPEN decisions (ratify before the respective slice)

- **§3a per-row cull/keep/hygiene list** (Trigger #2) — produce + ratify before B1's migration.
- **Discipline→weight-tier map** (HEAVY swim/paddle/ski/technical-MTB/climb vs LIGHT steady run/cycle) — decide with §3a (same discipline tags).
- **Prompt-body wording** (§6 / §6a-G1) — Trigger #1 ratification before A2.
- **Interval/Tempo scope** — are the 8 Interval/Tempo rows in the *drill* pool, or reserved for a catalog-driven interval-structure design (#337)? Design recommends: include Aerobic/Endurance + technical drills now; **defer** structured intervals to #337.
- **Tighten-later (§6a-G5):** a soft discipline-match warning, only if wrong-discipline picks show up live.

## 6. Also this session — #732 filed + PARKED

Filed **#732**: the **race-week brief is built-not-wired** — `race_week_brief.py` is reachable but the orchestrator is a partial stub (hardcoded `prior_plan_session_window=[]` + placeholder `plan_version_id`), with no persistence and no display surface. Andy ratified the eventual shape (plan-view-button trigger + mutate `plan_sessions`) and a 3-slice plan, then **chose Track 2 over building it** → #732 is PARKED with its plan recorded on the issue. Not on Track 2's critical path.

## 7. Verification

- No code/tests this session (design + bookkeeping only). The design's code anchors were grounded against on-disk reality before writing: the `cardio_blocks`/`strength_exercises` schema (`per_phase.py:619`/`665`, enum-bind at `:682-686`), `compute_recovery_pool_ids` (`per_phase.py:520`), `_format_recovery_exercise_pool` (`per_phase.py:967`), `_rule_recovery_pool_membership` (`validator.py:722`), and the active catalog breakdown from `etl/output/layer0_etl_v1.8.0.sql` (65 Technical/Skill, 8 Interval/Tempo, 4 Aerobic/Endurance active).
- #734 + #736 merged with required checks green (Python unit suite, JS harness, Layer 0 gate; Real-LLM smoke skipped). Design v1 (with §6a) present on main.

## 8. Anchor checks for the next Rule #9 sweep

| Claim | File | Anchor / check |
|---|---|---|
| Design doc on main | `designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v1.md` | exists; `grep -c "## 6a. LLM-reliability guardrails" <file>` → 1 |
| One-drill cap ratified | same | `grep "maxItems: 1" <file>` hits §4 |
| Guardrails G1–G8 | same | `grep -c "^- \*\*G[1-8]" <file>` → 8 |
| §3a not yet produced | same | `grep "appended to this design as §3a" <file>` (deliverable still owed) |
| No code yet | repo | `grep -rn "cardio_drills" layer4/` returns **nothing** until A1 ships |
| CURRENT_STATE pointer | `CURRENT_STATE.md` | top "Last shipped" anchor `TRACK 2 — CARDIO DRILLS POOL` names #734/#736 + this handoff |

## 9. Read order for next session (Rule #13)

`CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh` → then the ratified design `designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v1.md` §3/§6a/§13a and produce **Part B §3a** (the per-row audit table for Andy's ratification) before the cull migration.

**STILL OWED (carried):** post-#572 live T3 *refresh* re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify (Andy-action); #732 parked (race-week-brief wiring).

---

**End of handoff.**
