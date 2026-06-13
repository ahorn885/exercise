# Layer 4 — Strength Programming (Phase 2) Design v2

**Status:** signed off (Andy, 2026-06-13) + **PR 1 implemented**. Supersedes v1 (Slices 1 & 2, 2026-06-04→05). v2 is a **deepening pass** driven by a refreshed, durability-weighted evidence sweep (§A): it replaces the single shallow strength template with a **two-template model** (programmed vs failover), makes the strength guidance a **shared source of truth** fanned into the refresh paths, and bumps the prompt cache revision.
**Changes from v1:** §3 (frequency = advisory, **failover-exempt**), §4 (two-template structure replaces "3–5 exercises, 2–3 sets"), new §4b (failover strength) + §7b (refresh fan-out) + §11 (cache bump), §A (durability/interference re-weighting). **Carried unchanged from v1:** §2 deterministic/LLM split, §5 selection bias, §6 attribution, §8 exercise-surface rendering (shipped), §10 advisory-validator shape.
**Fixes:** #335 (Phase 2 deepening). **Date:** 2026-06-13. **Source:** pv-level review + a second cited deep-research pass (5 angles: session depth, interference, durability/load-carriage, core, periodization — see §A).

---

## 0. What v2 changes and why (the deepening)

v1 set strength at **3–5 multi-joint lower-body exercises, 2–3 sets, not to failure** — a number drawn almost entirely from the **running/cycling running-economy** literature (Rønnestad/Mujika; road runners optimizing 5k–marathon economy). For AIDSTATION's actual market — **multi-day expedition / ultra / load-carriage** athletes (Andy: 48–56h AR with pack carriage across four disciplines) — that objective is wrong. The refreshed evidence (§A) splits cleanly:

- **Economy** is maximized by a *few heavy* compounds; extra volume adds nothing (plateau past ~2–3 sets/exercise).
- **Durability / injury-prevention** is partly **volume-dependent** (Lauersen 2018) and benefits from *tissue-specific* eccentric/unilateral/posterior-chain/trunk work that heavy bilateral squats alone don't cover — and multiday-ultra MSK failures cluster on days 3–4 (Krabak 2011), i.e. exactly the durability window.
- **Interference** does **not** penalize strength *volume* — it's driven by endurance volume/intensity/modality and same-session *timing*, and it lands on explosive/RFD, not endurance (Schumann 2022). So "more strength volume hurts endurance" is unsupported; the real constraints are *frequency* (recovery budget) and *same-day placement* (already handled, §7).

Net: a deeper, layered session is justified **for durability**, not economy. v2 encodes that as the **programmed** template, and adds a distinct **failover** template for the terrain/craft substitution path (§4b).

---

## 1. Purpose & scope

The strength-authoring prompts produce strength sessions for new plans (`per_phase.py`, Pattern A) **and** refreshes (`plan_refresh_t1/t2`, plus T3 → per_phase). v2 makes all of them share one evidence-based composition policy with two templates, and ensures a prompt-only change actually re-synthesizes cached plans.

**In scope (PR 1):** the two-template shared guidance (`layer4/strength_guidance.py`); splice into `per_phase` + `plan_refresh_t1` + `plan_refresh_t2`; cache-key prompt-revision bump (`hashing.py`).
**Deferred to PR 2 (the refresh-feasibility track):** wiring the deterministic terrain/craft feasibility resolver into the refresh orchestrator so the **failover template's trigger** (`[TERRAIN-INFEASIBLE]`/`[NO CRAFT]`) actually fires on refresh — today refresh runs **no** feasibility resolution (a pre-existing gap: refresh can prescribe/clobber infeasible cardio); the `strength_substitution` schema marker + validator source-scoping (§10) ride with it.
**Out of scope (unchanged from v1):** rx_engine absolute loads (Phase 2b, #335); single_session (renders its own pool; prompt unchanged in PR 1).

---

## 2. Deterministic vs LLM split

Unchanged from v1. Frequency target + candidate pool + feasibility tier = deterministic; which exercises + session shape + placement = LLM; guardrails = deterministic `warning`-only.

---

## 3. Strength-dose policy (frequency = advisory, failover-exempt)

Default per-phase **programmed** strength frequency (sessions/week):

| Phase | Programmed sessions/wk | Emphasis |
|---|---|---|
| **Base** | **2** | Heavy core + durability build |
| **Build** | **2** | Strength→power + durability |
| **Peak** | **1** (maintenance) | Trim to heavy core + 1 plyo + 1 carry; **keep load heavy** |
| **Taper** | **1** early, then **0** in the final ~7–10 days | Maintain then shed fatigue |

These match the existing `_STRENGTH_SESSIONS_PER_WEEK` validator targets (Base/Build 2, Peak/Taper 1, ±1) — v2 does **not** change the numbers; it changes what fills the session (§4).

**The cap is advisory, never a hard gate (load-bearing).** `_rule_strength_frequency_band` is `warning`-only and stays that way. This is what lets the terminal **failover** path (endurance → strength when no terrain/craft/substitute is feasible; `session_feasibility.py` cascade) stack strength sessions **above** the programmed dose without ever being blocked. A hard cap here would starve the fallback (forcing an empty/hole day or a validation error) — explicitly rejected.

**Two strength flows sum.** Programmed strength (from the 2A grid allocation) **+** failover strength (terrain/craft substitution of a cardio slot) can total >3 in a constrained week. That is acceptable: failover sessions are forced by feasibility, not a programming choice, and are composed *light* (§4b) so the extra volume doesn't wreck recovery. **PR 2** adds the `strength_substitution` marker so the advisory warning counts only *programmed* sessions; until then the warning counts all strength (a noisier-but-harmless advisory, never a block).

---

## 4. Programmed strength — the layered session (replaces v1 §4)

The default template (an elective strength allocation). Build it in **layers**, scaling depth to phase + race demands (deeper for long/multi-day/load-carriage; leaner for short-course):

1. **Heavy core** — 2–3 multi-joint compound lifts (knee-dominant squat pattern, hip-hinge/deadlift pattern, optional third). **3 sets × 4–6 reps**, heavy, explosive concentric intent, **not to failure**, as **RM/RPE targets** (`3×5 @ ~8RM`), never absolute weights. The economy/strength anchor — kept tight (extra heavy lifts don't add economy).
2. **Durability layer** (long/ultra/expedition/load-carriage) — **2–3 eccentric-emphasis** movements at moderate load: eccentric/unilateral knee (split squat, step-down — descent braking), eccentric hamstring (Nordic, RDL), eccentric calf + tibialis-anterior. Targets the day-3–4 failure tissues; trimmed/skipped for short-course.
3. **One plyometric/explosive** (jumps, bounds) — RFD + low-speed economy.
4. **One trunk anti-rotation / loaded carry** (suitcase carry, Pallof) — efficient trunk + grip; **honor wrist/joint accommodations** (Andy's left-wrist constraint → neutral-grip carries, no loaded wrist extension).

**Maintenance (Peak/Taper):** trim toward heavy core + 1 plyo + 1 carry and **cut sets** — but **keep the load heavy; never maintain by lowering the weight** (Spiering 2021; the v1 maintenance principle, retained).
**No-history exercise:** prescribe the reps, tell the athlete to use a load they can complete for that many reps with ~2 RIR, and log it — they set their own baseline (retained from v1; seeds Phase 2b rx_engine).

This lands a Build session at ~6–8 movements — deeper than v1's 3–5, but only ~3 are *heavy/maximal*; the rest is lower-CNS durability/plyo/carry work. The heavy-load surface stays bounded (fatigue + economy plateau), which is the real constraint — **not** interference (§0).

## 4b. Failover strength — the terrain/craft substitution (new)

When the deterministic resolver tags a cardio slot `[TERRAIN-INFEASIBLE]` / `[NO CRAFT]`, the session is **standing in for an infeasible aerobic session** — so it must **replace aerobic work, not add a heavy CNS day**:

- Compose as **muscular endurance / aerobic-strength**: circuits, higher reps (12–20+), short rests, loaded carries, the durability movements above. **Keep the missing session's target hours** — a 2-hour infeasible session becomes a long circuit, *never* two hours of maximal lifting (which is both wrong and impossible).
- Target the muscles the infeasible discipline demands, from the rendered substitution pool.
- **Exempt from the programmed 2–3/week dose** — forced by feasibility; compose light.

This resolves the cap-vs-fallback tension: the cap is advisory (§3), failover is a different, lighter stimulus, and the true terminal (`reallocate`) is unchanged.

---

## 5. Exercise selection & integrated-stability bias

Unchanged from v1 (compound > heavy+plyo > unilateral/offset/anti-rotation > eccentric injury-resilience; 2D-filtered; hybrid stable-core + rotating-accessory). v2's layered template makes the eccentric/unilateral/carry bias explicit per-layer rather than as a single "prefer" sentence.

## 6. Session attribution (`discipline_id`)

Unchanged from v1 — attribute each strength session to the discipline it most supports.

## 7. Scheduling (paired + interference)

Unchanged from v1 — strength rides as the 2nd session on an easy/moderate day, not same-day as a key intensity/long session; ≥3h separation is athlete guidance (`session_notes` cue), not an engine constraint. v2 §0 reaffirms the evidence: same-session timing is the interference lever, not strength volume.

## 7b. Refresh fan-out (new — the shared-source requirement)

Strength is authored in **three** prompts, which previously could drift: `per_phase` (new-plan + T3 cross-phase) and the rolling-window refreshers `plan_refresh_t1` (2-day) / `plan_refresh_t2` (7-day "regenerate the week"). v1's guidance lived only in `per_phase`; the refreshers carried their own thinner strength instructions. v2 extracts the composition policy into **`layer4/strength_guidance.py` (`STRENGTH_PROGRAMMING_GUIDANCE`)**, imported and spliced into all three system prompts, so a refresh can't revert a plan to the old shallow style.

**Trigger caveat (→ PR 2):** the **programmed** template fires everywhere immediately. The **failover** template needs the `[TERRAIN-INFEASIBLE]`/`[NO CRAFT]` annotation, which only `per_phase`/plan-create compute today. The refresh paths run **no** feasibility resolution, so the failover half is dormant on refresh until PR 2 wires `_build_terrain_feasibility()` into `orchestrate_plan_refresh()` (and threads it through T1/T2 + the T3 `synthesize_pattern_a_for_refresh()` pass-through). That PR 2 also fixes the standalone pre-existing bug (refresh prescribing/clobbering infeasible cardio) and adds the `strength_substitution` marker.

---

## 8. Exercise-surface rendering

Unchanged — shipped in v1 Slice 1 (`render_user_prompt` `=== Strength exercise pool ===`). The shared guidance references it caller-agnostically ("the rendered substitution pool" / "rendered Strength exercise pool").

## 9. System-prompt additions

The `# Strength programming` section in `per_phase.py:SYSTEM_PROMPT` now = the shared `STRENGTH_PROGRAMMING_GUIDANCE` body + a per_phase tail (pool selection, no-history, attribution, placement). `plan_refresh_t1/t2` add a `# Strength programming` section = the shared body. `SYSTEM_PROMPT` literals were converted to parenthesized string concatenation to splice the constant.

## 10. Validator guardrails (advisory — all `warning`)

Unchanged in PR 1: `_rule_strength_frequency_band` stays `warning`-only with Base/Build 2, Peak/Taper 1, ±1. **PR 2:** scope the count to **programmed** sessions only (exclude `strength_substitution=true`) so legitimate failover stacking doesn't trip the advisory. No new `blocker` rules (Phase 1 lesson).

## 11. Cache / cost / latency (new for v2)

- **Prompt revision bump:** the synthesis/refresh prompt text is **not** part of the content-addressed cache key (key = payload + model + sampling + `etl_version_set`, which is DB-sourced, not prompt-derived). So a prompt-only change does **not** invalidate cached plans on its own. v2 adds `hashing.LAYER4_PROMPT_REVISION = "2"`, mixed into `plan_create_key` + `plan_refresh_key` → first post-deploy plan/refresh re-synthesizes cold (one-time, expected). Bump on future prompt-body changes. (`single_session_synthesize_key` not bumped — its prompt is unchanged.)
- **Tokens:** the layered guidance adds ~2.5KB of system-prompt text per block (static, cacheable by the provider). Net session content is similar; watch block latency on first re-run (#316), as v1.

## 12. Test plan

PR 1 (`tests/test_layer4_strength_templates.py`): both templates + trigger seam present in shared guidance; programmed dose/cap + layered structure; failover = muscular-endurance + uncapped; **fan-out** — shared guidance embedded in all three system prompts; superseded "3–5 … 2–3 sets" line gone from per_phase; cache-key prompt-revision bump changes both create + refresh keys. Existing `test_layer4_strength_frequency.py` + full layer4/refresh/hashing suite green (no regression).

## 13. Open items / deferred

- **PR 2 — refresh-feasibility track:** `_build_terrain_feasibility()` into `orchestrate_plan_refresh()`; thread to T1/T2 prompts + fix T3 `terrain_feasibility` pass-through; add it to the refresh cache key; **`strength_substitution` marker** on `PlanSession` + tool schemas + validator source-scoping (§10). Closes the pre-existing "refresh ignores feasibility" bug and lights the failover template on refresh.
- **Phase 2b (#335):** rx_engine absolute loads.
- **Phase 3 (#298/#341):** multi-locale cluster.

## 14. Gut check

- **Risk — the deeper session is durability-justified, not economy-justified, and that evidence is medium-confidence** (Lauersen's dose-response rests on 6 studies; expedition-AR durability is extrapolated from runners + military). It is **not** a performance/economy win (economy plateaus). If we wanted to stay strictly on high-confidence economy evidence, v1's leaner 3–5 holds. Justification for going deeper: AIDSTATION's market *is* underserved extreme endurance, so designing strength for multi-day durability is on-brand and defensible. **Decision (Andy 2026-06-13): go deeper.**
- **Risk — contested sub-claims** (Nordic ~51%: Impellizzeri 2021 reappraisal; unilateral-asymmetry→injury chain disputed; core→economy small/mixed). Mitigation: these ride in the template on **specificity/efficiency** grounds, not as hard injury claims.
- **Risk — refresh fan-out is only half-live in PR 1** (failover dormant until PR 2). Mitigation: programmed template improves refresh immediately; refresh is **no worse** than today on failover (the latent bug is untouched, not worsened); PR 2 is scoped and queued.
- **Best argument against:** do PR 1 + PR 2 together so both templates are fully live everywhere at once. Rejected: that bundles a prompt change with a refresh-orchestration + caching change (10+ files, over the ceiling) into one hard-to-review PR; the split ships the durability deepening now and isolates the feasibility-wiring/bugfix.

---

## §A. Evidence basis (second cited deep-research pass, 2026-06-13)

Five angles; full per-angle findings with PMIDs/DOIs + dissent in the session record. Headlines:

- **Session depth / economy:** effective economy protocols use **3–5 heavy lower-body compounds + plyometrics** (≥80% 1RM, low-rep, not to failure); no review supports a 10+ movement circuit; submaximal/isometric work does **not** improve economy — Balsalobre-Fernández 2016 *JSCR* (PMID 26694507); Llanos-Lagos 2024 *Sports Med* (PMID 38165636); Blagrove 2018 *Sports Med* (PMID 29249083); Rønnestad & Mujika 2014.
- **Durability / load-carriage (the case for going deeper):** strength training cuts overall injury to <⅓, overuse ~½, **dose-dependent on volume** — Lauersen 2014 (PMID 24100287) / 2018 *BJSM* (PMID 30131332); eccentric hamstring ~½ (van Dyk 2019, PMID 30808663 — magnitude contested, Impellizzeri 2021); multiday-ultra MSK encounters peak **days 3–4** (Krabak 2011, PMID 21552155); top overuse sites PFP/ITB/Achilles/tib-ant (Scheer 2021); load-carriage S&C = posterior-chain + eccentric-quad/calf + trunk (NSCA TSAC).
- **Interference (why volume isn't the constraint):** interference is endurance-driven + same-session-timing-driven, lands on explosive strength, abolished by ≥3h separation; max-strength/hypertrophy/endurance essentially unimpaired — Schumann 2022 *Sports Med* (PMID 34757594); Methenitis 2018 (PMC6315763); Fyfe 2014 (PMID 24728927).
- **Core/trunk:** carries (esp. suitcase) + anti-rotation isometrics are validated multi-planar trunk stimuli (Holcomb 2024, PMID 38665162); core→economy effect small/mixed (Hung 2019, PMID 30849105; Sato & Mokha 2009) — 1 carry/anti-rotation movement is a defensible *adjunct*, not a displacer of heavy compounds + plyo (Llanos-Lagos 2024).
- **Periodization/frequency:** 2×/wk build → 1×/wk in-season maintenance; **cut volume, hold load**; ceiling **2–3/wk** (no source recommends 4+); taper cut volume 41–60%, hold intensity — Rønnestad 2010 (PMID 20799042); Spiering 2021 (PMID 33629972); Bosquet 2007 (PMID 17762369); Mujika & Padilla 2003.

**Caveats:** most data are runners/cyclists, not multi-day expedition AR — load-carriage/durability specifics extrapolated (military/NSCA). Direction robust; exact magnitudes medium-confidence. The deeper session is a **durability** bet, not an economy claim.
