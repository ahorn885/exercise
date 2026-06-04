# Layer 4 — Strength Programming (Phase 2) Design v1

**Status:** signed off + **Slice 1 implemented** (2026-06-04, pv=57 stall investigation — strength surface was the upstream cause of the `equipment_unavailable` blockers + synthesis thrash). Slice 1 = §8 exercise-surface rendering + §9 system-prompt section in `layer4/per_phase.py` (the synthesizer now picks real resolved `exercise_id`s instead of inventing them). **Slice 2 (still owed):** §3 deterministic per-phase frequency target plumbing + the §10 `strength_frequency_band` advisory validator. **Slice-1 deviations** (both compensated by the §9 prompt): movement-pattern ranking omitted (`ResolvedExercise` has no `movement_patterns`); core-vs-accessory marking left to the prompt; pool rendered unfiltered by `exercise_type` (fail-open — `exercises_resolved` is already the 0B exercise set, and over-filtering risks the empty-surface bug this fixes).
**Fixes:** #335 (strength = bare labels). **Related:** #298, #341, #316. **Predecessor work:** PR #413 (Phase 1 — `sport_locale_incompatible` gate fix).
**Date:** 2026-06-03. **Source:** pv=54 cold-plan investigation + a cited sport-science deep-research pass (see §A).

---

## 1. Purpose & scope

The per-phase synthesizer (`layer4/per_phase.py`, Pattern A: `plan_create` + `plan_refresh` T3) currently produces **zero or bare-label strength sessions** because (a) the user prompt never renders the resolved exercise list, and (b) nothing instructs it to program strength or how much. This design wires the **resolved exercise surface** + an **evidence-based strength-dose policy** into per-phase synthesis.

**In scope (Phase 2):** exercise-surface rendering; strength-dose policy (frequency + structure); selection bias; session attribution; paired scheduling; advisory guardrails. **Loads prescribed as RM/RPE targets** (e.g. `3×5 @ ~8RM`), not absolute weight.

**Out of scope (Phase 2b, deferred — documented on #335):** wiring `rx_engine` for deterministic, performance-driven absolute loads from logged capacity records (with `strength_benchmarks` bootstrap). **Out of scope:** `single_session` (already renders exercises, `single_session.py:561`); multi-locale cluster (Phase 3, #298/#341).

---

## 2. Deterministic vs LLM split (the architecture)

Mirrors the cardio side (2A volume bands = deterministic soft targets; LLM synthesizes; validator checks as warnings).

| Element | Mechanism | Where |
|---|---|---|
| Strength **frequency** target (per phase) | **Deterministic** | orchestrator/phase-structure → prompt input + advisory validator |
| Candidate exercise **pool** | **Deterministic** — 2C-resolved × 2D-injury-filtered × ranked, capped | `render_user_prompt` |
| **Which** exercises + session shape | **LLM judgment** | synthesizer |
| Session→day **placement** + interference | **LLM judgment** + advisory validator | synthesizer |
| Week-to-week **variety/rotation** | **LLM judgment** (within hybrid policy) | synthesizer |
| **Load / sets / reps** | **LLM** as RM/RPE targets (Phase 2); **rx_engine deterministic** in Phase 2b | synthesizer → rx_engine later |
| **Guardrails** | **Deterministic, `warning` severity** (never `blocker` — Phase 1 lesson) | validator |

---

## 3. Strength-dose policy (deterministic frequency)

Default per-phase strength frequency (sessions/week), from the season-periodization evidence (§A):

| Phase | Sessions/wk | Emphasis |
|---|---|---|
| **Base** | **2** | Max-strength + plyometric build |
| **Build** | **2** | Strength→power conversion |
| **Peak** | **1** (maintenance) | Cut volume ~half, **keep load heavy** |
| **Taper** | **1 in the early part, then 0 in the final ~7–10 days** | Maintain then shed fatigue |

**Modulation** (deterministic inputs, applied to the default):
- **3A strength state:** `low` → keep 2× and bias hypertrophy-adjacent/general-strength longer; `high` → maintenance-lean sooner. (Soft ±, never below 1× in Base/Build.)
- **2D injury:** excluded movements removed from the pool (hard); accommodated → reduced volume/intensity per modality (`Layer2D_Spec §5.3.6`).
- **§K availability:** if days don't fit, frequency yields to the schedule (advisory, not a hard fail).

**Plumbing = option B:** computed in the orchestrator/phase layer and passed to `synthesize_phase` as a per-phase target (e.g. `strength_sessions_per_week`), **not** as a weighted 2A discipline (option A noted, not chosen). The existing `Layer4_Spec` `discipline_frequency_infeasible` math (`ceil(weight×7)`) is **not** used for strength (strength has no 2A weight).

---

## 4. Session structure (RM/RPE loads)

- **3–5 multi-joint, lower-body-biased exercises per session**, whole-body (not split).
- Build phases: **2–3 sets × 4–10RM (~80–90% 1RM-equivalent)**, ~2–3 min rest, **not to failure**.
- Maintenance (Peak/Taper): **reduce volume by cutting sets (3→2) and/or frequency (2→1×/wk) — keep ≥2 sets for realism — while HOLDING the load and rep range.** The maintenance literature is explicit: strength is preserved by cutting *volume*, **not** by reducing *intensity* — dropping the weight is precisely what detrains (Spiering 2021; Rønnestad 2010 held a ~23% strength gain on 1×/wk × 2 sets @ 80–85% 1RM). **Do not taper by lowering load.** (Note: this corrects the intuition to "drop reps or weight" — trimming a rep is fine, dropping kg is counterproductive.)
- **Load = RM/RPE target string** (`"3×5 @ ~8RM"` / `"@RPE 8"`), not absolute weight. (Phase 2b swaps this for rx_engine absolute loads.)
- **Novel / unlogged exercise (no history → unknown working weight):** prescribe the reps and instruct *"use a load you can complete for N reps with ~2 reps in reserve, and log it"* — the athlete self-establishes the baseline on first encounter, which seeds Phase 2b's rx_engine progression. **No exercise is withheld for lack of history.**
- De-prioritize hypertrophy-range (6–12 to failure) — added mass can hurt economy; some hypertrophy tolerable for load-carriage/durability.

---

## 5. Exercise selection & the integrated-stability bias

Priority order for what the LLM should pick from the pool (evidence §A):
1. **Compound multi-joint** — hinge/deadlift, squat, lunge/step-up (+ eccentric for descent), loaded carry, anti-rotation/anti-extension trunk; push/pull secondary (pack posture).
2. **Heavy + plyometric/explosive** over hypertrophy.
3. **Integrated stability-strength (Andy):** prefer **unilateral / offset / anti-rotation** variants (single-arm DB, suitcase/offset carries, single-leg) — builds one-side strength + trunk stability together, matches the asymmetric demands of cycling/running/paddling. Taggable from `movement_patterns` (`Single-Leg`, etc.) and `movement_components` where present; the offset/anti-rotation nuance the vocab doesn't yet encode is carried by **prompt instruction** (optional future: a Layer 0 tagging pass — §15).
4. **Injury resilience:** unilateral + eccentric (e.g. single-leg, step-down) — strength training ≈ halves overuse injury risk (Lauersen 2018).
5. **2D-filtered:** excluded exercises removed from the pool before rendering.

**Hybrid (variety vs progression):** a stable **core** of 2–3 progressed compound lifts (consistency → overload tracking; Phase 2b rx_engine) + a **rotating accessory** pool (variety/adherence). The LLM keeps the core consistent across a phase and rotates accessories week-to-week.

---

## 6. Session attribution (`discipline_id`)

A `strength` PlanSession must carry a non-None `discipline_id` (schema invariant). **Decision (option 2):** attribute each strength session to **the discipline it most supports** — the dominant discipline among its exercises by bridge `priority_per_discipline` / `sport_relevance_notes`. So the engine builds *discipline-targeted* strength (running-strength vs paddling-strength), and the rendered pool is organized per-discipline so the LLM can compose a session around one discipline's high-relevance exercises. General lower-body work that serves several disciplines attributes to the **primary** (highest 2A load weight) discipline.

---

## 7. Scheduling (paired + interference)

Scheduling is **day-level only** — the app prescribes sessions per day, not times of day; the athlete chooses when within the day. So:
- Place strength on an **easy/moderate cardio day**, **not** the same day as a key intensity/long session (same-day concurrent work is where interference concentrates; Schumann 2022). It rides as the day's 2nd session (within §K windows, 2-per-day cap, `session_index_in_day ∈ {0,1}`).
- The engine does **not** prescribe a time gap. If strength must share a day with a hard session, surface an athlete-facing cue in `session_notes` (e.g. *"separate this from today's hard session by a few hours if you can; don't lift heavy legs right before the quality session"*). The ≥3 h interference window is **athlete guidance, not an engine constraint**.
- Endurance is **not** impaired by adding strength (asymmetric) — placement protects strength/power, not the cardio.

---

## 8. Implementation — exercise-surface rendering

**File:** `layer4/per_phase.py`, `render_user_prompt`. **Insertion:** a new `=== Strength exercise pool ===` section **after** the `Locales + equipment views` block (~`:1048`), before `=== Best-fit training substitution ===`.

Per locale, per included discipline (ordered by 2A load weight), render the resolved strength exercises:
- **Source:** `l2c.exercises_resolved` filtered to `discipline_id ∈ rx.discipline_ids`.
- **Filter:** drop 2D-excluded (`exercise_id ∈ layer2d.excluded_exercises`).
- **Rank:** `priority_per_discipline` (Critical → High → Medium), then bias `movement_patterns` toward {Single-Leg, Hinge, Squat, Carry, Lunge, anti-rotation}; tier-1 preferred.
- **Dedup:** an exercise serving multiple disciplines is listed once under its highest-priority discipline.
- **Cap:** top **N≈8–12 per discipline** (tunable; balances grounding vs tokens/#316).
- **Line format:** `- EX### (Name) [pattern; Tier n{; substitute: …|proxy: …}]`, mirroring `single_session.py:561`.
- Mark a small **core** subset vs the **rotating accessory** remainder.

Empty pool for a discipline (e.g. D-008/D-012, zero 0B exercises) → render nothing for it (no blocker; sport sessions handle those — Phase 1).

---

## 9. Implementation — system-prompt additions

Add a `# Strength programming` section to `SYSTEM_PROMPT` (`per_phase.py:170`). Proposed text (for sign-off — Trigger #1):

> **# Strength programming**
> Program resistance training every week per the phase dose: **Base/Build 2 sessions/week, Peak 1 (maintenance), Taper 1 early then none in the final ~7–10 days.** Each session: **3–5 multi-joint, lower-body-biased exercises, 2–3 sets, 4–10 rep range, not to failure**, prescribed as **RM/RPE targets** (e.g. `3×5 @ ~8RM`) — never invent absolute weights. In maintenance phases (Peak/Taper) **reduce volume — drop to ~2 sets and/or 1 session/week — but keep the load and rep range heavy; never maintain by lowering the weight.** If the athlete has no logged history for an exercise, prescribe the reps and tell them to *use a load they can complete for that many reps with ~2 reps in reserve, and log it* — they set their own baseline; do not withhold an exercise for lack of history.
> Pick exercises from the rendered **Strength exercise pool** for the session's locale (never invent `exercise_id`s). Keep a **stable core** of 2–3 compound lifts across the phase for progression; **rotate accessory exercises** week-to-week for variety. Prefer **unilateral / offset / anti-rotation** variants (single-arm, single-leg, carries) — they build one-sided strength and trunk stability together, which transfers to multi-sport. Prefer heavy + explosive over hypertrophy; de-emphasize added muscle mass.
> Attribute each strength session's `discipline_id` to the discipline it most supports. Place strength as the **second session on an easy/moderate cardio day**, not on the same day as a key intensity/long session. Do not prescribe a time of day; if strength shares a day with a hard session, add a `session_notes` cue to separate them by a few hours and avoid heavy legs right before the quality session. Honor 2D injury exclusions/accommodations.

Also update the `# Output discipline` line on `load_prescription` to say **RM/RPE target, not absolute load**.

---

## 10. Validator guardrails (advisory — all `warning`)

- **`strength_frequency_band_*`** (new, `warning`): per-(phase, week) strength-session count within target ±1; surfaces under/over-dosing without blocking.
- Existing **`injury_violation_*`** (excluded exercise) stays `blocker` (hard safety); **`injury_accommodation_violation_*`** stays `warning`.
- No new `blocker` rules (Phase 1 lesson: blockers stall cold synthesis).

---

## 11. Cache / cost / latency

- System-prompt + render changes shift the per-phase content-addressed cache key → **first post-deploy plan re-synthesizes cold** (one-time, expected).
- Rendering the pool adds input tokens on every block → **interacts with #316**; the **N cap** (§8) is the control. Mandating strength adds sessions/block → measure block latency on the first re-run; tune N down if it pushes block time toward the budget.

---

## 12. Test plan

- **Rendering:** pool section present per (locale, discipline); 2D-excluded absent; capped at N; ranked Critical-first; unilateral patterns surfaced; empty for zero-exercise disciplines.
- **Dose:** per-phase frequency target computed (2/2/1/taper) + 3A/2D modulation; `strength_frequency_band` warns when out of band, never blocks.
- **Prompt:** `# Strength programming` present; phase-appropriate dose; `load_prescription` guidance = RM/RPE.
- **Attribution:** strength session `discipline_id` = highest-priority supported discipline.
- **No regression:** validator suite green; cardio-only paths unchanged.

---

## 13. Open items / deferred

- **Phase 2b (#335):** rx_engine deterministic absolute loads from logged capacity records + `strength_benchmarks` bootstrap; confirm capacity records reach `layer4/context.py`.
- **Optional Layer 0 enhancement:** a dedicated `offset/anti-rotation/contralateral` tag so the stability bias is data-driven, not prompt-only (today partial via `movement_patterns`/`movement_components`).
- **Phase 3 (#298/#341):** multi-locale cluster. Locale selection is **per-session and exclusive** (single-locale-per-session — never a workout requiring two places; the schema's single-locale invariant already enforces this). When a nearby strength gym is in the cluster, choose the session's locale by **anchoring on the highest-priority exercises**: if a Critical exercise (e.g. squat) needs equipment the home locale lacks but the gym has (a rack), select the gym; then any lower-priority exercise the chosen locale can't equip (e.g. battle ropes) is **substituted to fit that locale**, not split off to another place. The most-important exercise's equipment wins the locale; everything else conforms or is swapped.

---

## 14. Gut check

- **Risk — latency (#316):** more rendered tokens + more sessions/block could worsen block synthesis time. Mitigation: cap N, measure on re-run, tune. This is the main thing to watch.
- **Risk — RM/RPE vs absolute:** RM/RPE is less precise than rx_engine and asks the athlete to autoregulate; honest interim until Phase 2b, and correct for a no-history fresh plan.
- **Best argument against:** do Phase 2 + 2b together (render + rx_engine) so loads are absolute from day one. Rejected: that blocks the bare-labels go-live fix on a larger cross-layer integration with a fresh-plan bootstrap problem; RM/RPE ships the fix now and rx_engine upgrades it later.
- **What might be missing:** strength-session `discipline_id` attribution (option 2) may make per-discipline strength feel siloed for a 6-discipline athlete where most lower-body work is shared; watch the first real plan and reconsider a "general strength" sentinel (option 3) if it reads oddly.

---

## §A. Evidence basis (cited deep-research, 2026-06-03)

- **Frequency/periodization:** 2×/wk build → 1×/wk in-season maintenance, validated over a 40-week season — Beattie 2017 *JSCR* (PMID 27135468); Rønnestad, Hansen & Raastad 2010 *EJAP* (PMID 20799042). Benefit is on economy/strength/durability, not VO₂max.
- **Session structure:** 3–5 multi-joint, 2–3 sets, 4–10RM; maintenance = cut volume, keep intensity — Rønnestad & Mujika 2014 *Scand J Med Sci Sports*; Spiering 2021 *JSCR* (PMID 33629972); Schoenfeld 2017 *J Sports Sci* (volume dose-response, hypertrophy).
- **Concurrent interference:** narrow (explosive/power), abolished by ≥3 h separation; endurance unaffected — Schumann 2022 *Sports Med* (PMC8891239); Wilson 2012 *JSCR*; Doma (economy degraded ≤8 h post-leg-RT).
- **Selection:** heavy+plyometric, compound, unilateral/eccentric + carries/anti-rotation for load-carriage — Rønnestad & Mujika 2014; Lauersen 2018 *BJSM* (PMID 30131332, ~⅓ overall / ~½ overuse injury); van Dyk 2019 (Nordic ~51%, magnitude contested); Knapik/Williams 2011 (PMID 22130400); NSCA TSAC 2019.
- **Variety vs progression:** variation aids motivation, strength-neutral once volume-matched → hybrid core+accessory — Baz-Valle 2019 *PLoS One*; Kassiano 2022 *JSCR* (PMID 35438660).
- **Taper:** maintain strength (cut volume 40–60%, keep intensity), drop in final ~1–2 wks (strength detrains slowly) — Bosquet 2007 *MSSE* (PMID 17762369); Mujika & Padilla 2003.

**Caveats:** most data are runners/cyclists, not multi-day expedition AR — load-carriage/durability specifics extrapolated (military/NSCA); variation RCTs small/short/young-men. Direction robust; exact magnitudes medium-confidence.
