# Layer 4 — Cardio drills "consider these" pool + Technical/Skill catalog cull — Design

**Status:** v2 — Part B (catalog cull) DONE + PROD-LIVE; Part A (pool) reshaped for the post-cull catalog and RATIFIED (Andy 2026-06-19), pending build. Supersedes v1 (`archive/superseded-specs/`).

**⚠ v2 changelog — why this supersedes v1 (read first).** v1 specced Part B as a *hygiene-only* pass over **68 active rows (56 keep)** because it (correctly, at the time) found migration `0009/#644` had already done a narrow cull. **After v1, Andy ratified an AGGRESSIVE Technical/Skill cull** (full-catalog audit → keep 8, retire 47) **plus three evidence-based cardio adds (EX290–292)** — shipped as migrations `0017`+`0018` (PR #750) and **prod-verified live** (T/S 55→8, I/T 9→12; read-only `neon-query` 2026-06-19, run 27808520792). So **Part B is complete and live, not pending**; the v1 §2/§3/§3a hygiene-audit narrative is now **historical** (its 11 gear-toggle-token rows were almost all culled by `0017` — only EX170 survives among them; EX194, the SEM-restore target, was itself culled). **Part A's pool source is now the 24 active rows** (8 T/S + 12 I/T + 4 A/E), which inverts v1's §5 assumptions — see the reshaped §3a (catalog) + §5 (knobs) below.

**Ratified Part-A reshape (Andy 2026-06-19), driven by the cull inverting the pool from skill-drill-heavy to interval-heavy:**
1. **Weighting — drop pool-level HEAVY/LIGHT.** SEM-match every drill; handle the lone residual ("don't push EX070 cycling-form on pure road cyclists") as a prompt de-emphasis note, not a pool suppression. Intervals transfer to all SEM-tagged disciplines.
2. **Periodization — by drill character.** Skill/transition/form drills (the 8 T/S) Base-heavy, minimized toward Peak/Taper; interval + endurance drills (16 I/T + A/E) follow normal phase emphasis (incl. Build/Peak). Not one blanket Base-full→Peak-empty gate.
3. **Adjacency — prompt-steered placement + a deterministic constituent-sport gate on EX175/176.** Discipline-match already gates the 5 transition drills to the right athletes; additionally include the cross-discipline brick/transition drills (EX175 Brick Run, EX176 Tri Transition) only when the athlete's discipline set holds **both a cycling and a running discipline** (filters the AR-paddle-climb athlete who matches only via the broad "Multi-Sport Race" tag). Which session they attach to stays prompt-steered (the daily schedule is LLM-composed → not deterministically gateable, same limit as recovery placement).
**Issue:** #698 Track 2 (follow-on to the closed Track 1 recovery-session arc, PR #730).
**Evidence base:** `research/RecoveryMobility_RestDay_CardioDrills_EnduranceEvidence_v1.md` §3 (cardio drills vs volume) + §"Design implication".
**Differentiator:** #6 science-backed, and #4 multi-sport-first — the orphaned catalog is overwhelmingly underserved-discipline skill content (paddle, ski, swim, scramble).

---

## 1. Purpose & boundaries

Wire the **orphaned cardio/skill `0B` catalog** into cardio prescription, and **audit/cull** the Technical/Skill rows that feed it.

Today `cardio_blocks` are **free-composed** by the synthesizer from prompt zone/interval guidance; there is **no cardio analog of `_format_strength_exercise_pool`**, so the structured cardio catalog is never fed to the model (#698 comments 2026-06-17). The **post-cull (0017/0018) active pool source** — the 24 rows the pool draws from (full per-row list in §3a):

| `exercise_type` | active | character |
|---|---|---|
| Technical / Skill | 8 | transition/carry + standalone drills (brick, tri/skimo transition, hike-a-bike, portage, poles, single-leg cycling, obstacle vault) — the aggressive-cull keeps |
| Interval / Tempo | 12 | structured intervals — bike Threshold/VO2/Sweet-Spot/Over-Under, Hill Repeats, Strides, Tempo/Marathon-pace/Flat-VO2 run, Swim CSS, Rowing erg, Treadwall |
| Aerobic / Endurance | 4 | Paddling erg, Sustained LISS, Freestyle Pull, Kicking drill |

**The cull inverted the pool's character:** v1 designed for a 56-row pool dominated by *skill/technique* drills (paddle strokes, ski edging, descent technique — all culled by `0017`). The surviving 24 are **mostly structured interval/endurance work (16) + 8 transition/form drills** — which is why the §5 knobs are reshaped (see the v2 changelog).

**This design's scope:** a **`cardio_drills[]` session block** (the `recovery_exercises[]` analog) — enum-bound, SEM-matched, periodized by drill character. Part B (the catalog cull that cleans its source rows) is **done + prod-live** via `0017`/`0018`.

**Out of scope (named, not solved here):**
- **Cardio volume/zone composition stays LLM-composed.** This adds a drills *vocabulary*, not a volume model. We are *not* moving `cardio_blocks` onto the catalog.
- **Structured-interval prescription** (turning `EX074 VO2 Max Intervals (Bike)` into "Z5 4×4min" deterministically) overlaps **#337** and is a *larger* separate design. The Interval/Tempo rows seed the drill pool carrying their `coaching_cue` dose, but catalog-driven interval *structure* is deferred (§13 open).

---

## 2. The two coupled parts + sequencing

Part B (cull) and Part A (pool) are **two sides of one audit**: Part A's pool draws from the surviving Technical/Skill (+ cardio) rows, so the catalog must be clean and discipline-tagged before the pool is defined over it.

**Sequencing — RATIFIED (Andy 2026-06-18): Part B first, then Part A.**

**Reframe (load-bearing):** the snapshot (`etl/output/layer0_etl_v1.8.0.sql`, active rows) shows the 65 Technical/Skill rows are **overwhelmingly legitimate, high-value, well-cued discipline drills** (e.g. `EX093 Eskimo Roll Practice`, `EX140 Open Water Sighting Drill`, `EX166 Ferry & Eddy Turn`, `EX212 Scrambling Technique`). **Part B is therefore an asset inventory + narrow hygiene cull, NOT a mass deletion.** The survivors are the product asset; the cull removes only genuinely non-prescribable/duplicate rows and fixes vocabulary conflation.

---

## 3. Part B — Technical/Skill audit & cull (Trigger #2) — HISTORICAL (DONE via 0017/0018)

> **Historical (v2):** this section's hygiene-cull framing was superseded by Andy's aggressive cull. Part B shipped as the full-catalog audit (`research/`/audit doc, PR #745) → migrations `0017` (cull 55→8) + `0018` (adds EX290–292), **prod-live**. §3a below is the operative artifact: the resulting 24-row pool source. The buckets/figures in the rest of §3 describe the pre-cull plan.

A read-only audit of all 65 active `Technical / Skill` rows (+ the 8 Interval/Tempo + 4 Aerobic/Endurance), producing a per-row disposition. Output is a **layer0 migration**; every removal/edit is Andy-ratified before it lands (no-padding rule applies in reverse — no cull without review).

**Disposition buckets:**
1. **KEEP + discipline-tag (expected majority).** The row is a prescribable, discipline-relevant drill. Confirm its `sport_exercise_map` membership + `terrain_required` so the pool can discipline-weight it (§5). No content change.
2. **HYGIENE-FIX (the conflation rows).** Gear-bundle tokens mis-filed in `equipment_required` — each is an active `sport_specific_gear_toggles` entry (268/272/265), not an `equipment_items` piece. Fix = remove the toggle name from `equipment_required` (no new vocab). In the **live (post-0009) catalog** this is **11 in-scope rows**: `Climbing — roped` ×5, `Mountaineering` ×1 (EX149 — EX148/EX150 were among 0009's culls), `Touring/AT ski setup` ×5. (The earlier "13 / ×5-×3-×5" figure counted EX148/EX150 before recognising 0009 had retired them; see §3a H1–H3.)
3. **CULL.** ⚠ **Already done (see §3a).** The non-trainable Technical/Skill cull — incl. `EX094 Packraft Inflation/Deflation` and `EX123 Pack Fit Optimization` — was executed by migration **0009 (#644, Andy-ratified 2026-06-16)**, which retired 10 rows. Part B carries **no new culls**; this bucket is empty against the live (post-0009) catalog.

**Deliverable:** an audit table (`exercise_id | name | discipline | terrain | disposition | reason`) appended to this design as §3a before the migration, ratified by Andy. The migration supersedes culled rows (`superseded_at`, not hard-delete — Rule #12 history) and applies hygiene edits.

---

## 3a. The post-cull pool catalog — 24 active rows (the Part-A pool source)

**Status:** authoritative as of 2026-06-19 (read-only `neon-query` run 27808520792 vs prod Neon, post `0017`/`0018`). This replaces v1's 68-row hygiene-audit table: the aggressive cull retired 47 of the 55 Technical/Skill rows, so the pool now draws from **24 active rows — 8 T/S + 12 I/T + 4 A/E**. Discipline priorities are the active `sport_exercise_map` tier: `[C]`ritical / `[H]`igh / `[M]`edium (here Critical shown in full; the [H]/[M] tail summarised for the broad interval rows).

**Drill-character split (drives §5 periodization + the §6 prompt):**
- **Skill / transition / form — the 8 T/S** (EX070, EX144, EX163, EX170, EX175, EX176, EX183, EX196): Base-heavy, minimized toward Peak/Taper.
- **Interval + endurance — the 12 I/T + 4 A/E**: follow normal phase emphasis — intervals are *not* Base-only (VO2/threshold work peaks in Build/Peak).

### The 24-row pool catalog (`T/S` Technical/Skill · `I/T` Interval/Tempo · `A/E` Aerobic/Endurance)

| id | name | type | disciplines (active SEM — `[C]`/`[H]`/`[M]`) | terrain |
|---|---|---|---|---|
| EX070 | Single-Leg Cycling Drill (Trainer) | T/S | MTB [C]; XC/AR Cycling [C]; Gravel/Road/Duathlon/Triathlon [H] | — |
| EX144 | Hike-a-Bike Carry Drill | T/S | Bikepacking [C]; XC/AR Cycling [C] | — |
| EX163 | Canoe Portage Yoke Carry | T/S | Canoeing [C]; Long Distance Paddle Racing [C] | — |
| EX170 | SkiMo Race Transition Drill | T/S | SkiMo [C] | — |
| EX175 | Brick Run Drill (Bike-to-Run) | T/S | Multi-Sport Race [C]; Run-Bike-Run Duathlon [C]; Triathlon [C] | — |
| EX176 | Triathlon Transition Practice (T1 & T2) | T/S | Multi-Sport Race [C]; Triathlon [C]; Run-Bike-Run Duathlon [H] | — |
| EX183 | Running with Poles (Trail / Ultra) | T/S | Ultramarathon [C]; LD Orienteering [H]; Mtn/Sky Running [H] | Trail |
| EX196 | Obstacle Vault & Wall Traversal | T/S | Obstacle Course Racing [C] | — |
| EX048 | Hill Repeats | I/T | Fell Running [C]; LD Orienteering [C]; Mtn/Sky Running [C]; SkiMo [C]; Trail Running [C]; Ultramarathon [C]; XC Skiing [C]; +9 [H/M] | Outdoor Hill |
| EX049 | Strides (Flying Sprints) | I/T | Marathon/Multi-Sport/OCR/Duathlon/SwimRun/Trail/Triathlon [H]; Orienteering/Ultra [M] | — |
| EX073 | Threshold Intervals (Bike) | I/T | Gravel [C]; MTB [C]; Road [C]; Duathlon [C]; Triathlon [C]; XC/AR Cycling [C]; +4 [H] | — |
| EX074 | VO2 Max Intervals (Bike) | I/T | Mountain Biking [C]; Gravel/Road/Duathlon/Triathlon/XC-AR [H] | — |
| EX075 | Sweet Spot Training (Bike) | I/T | Bikepacking/Gravel/MTB/Road/Duathlon/Triathlon/XC-AR Cycling [C]; +3 [H] | — |
| EX178 | Tempo Run (Flat / Road) | I/T | Marathon [C]; Run-Bike-Run Duathlon [C]; Multi-Sport/OCR/SwimRun/Ultra [H] | Road; Flat Trail |
| EX179 | Marathon Pace Run | I/T | Marathon [C]; Duathlon/Ultramarathon [H] | Road; Flat Trail |
| EX203 | Rowing Erg Interval Session | I/T | Rowing [C] | — |
| EX288 | Treadwall Intervals | I/T | Rock Climbing [H]; General Conditioning [M] | — |
| EX290 | Flat VO2max Run Intervals | I/T | Marathon [C]; Fell/Mtn-Sky/Multi-Sport/OCR/Orienteering/Duathlon/Trail/Triathlon [H]; +3 [M] | Road; Flat Trail |
| EX291 | Swim CSS / Threshold Intervals | I/T | SwimRun [C]; Swimming [C]; Triathlon [C] | Pool |
| EX292 | Bike Over-Under Intervals | I/T | Gravel [C]; Road [C]; MTB/Duathlon/Triathlon/XC-AR [H]; Bikepacking/Multi-Sport [M] | — |
| EX090 | Paddling Ergometer Session | A/E | Canoeing [C]; Kayaking [C]; LD Paddle Racing [C]; Packrafting [C]; Multi-Sport/SUP [H] | — |
| EX120 | Sustained LISS (Hiking Pace) | A/E | Bikepacking [C]; Hiking [C]; LD Orienteering [C]; Mountaineering [C]; Snowshoeing [C]; Ultramarathon [C]; SkiMo/XC Skiing [H]; Rowing [M] | — |
| EX126 | Freestyle Pull (With Buoy) | A/E | SwimRun [C]; Triathlon [C]; Swimming [H] | Pool |
| EX128 | Kicking Drill (Flutter / Frog) | A/E | Swimming [H]; Triathlon [H] | Pool |

### Coverage after the cull

- **Disciplines that lose their *skill* drills but keep interval/endurance + transition coverage.** The paddle (stroke/roll/line-reading), ski-technique, climbing-movement, navigation, and pure-run-technique drills were all culled by `0017`. Those disciplines still match the surviving **interval/endurance** rows (e.g. paddle → EX090 erg; swim → EX291/EX126/EX128; ski → EX048/EX073/EX075 + EX120 LISS) and the relevant **transition keeps**.
- **Modern Pentathlon now has 0 pool drills** — EX194 Laser-Run (its only drill, and the v1 SEM-restore target) was itself culled by `0017`. Acceptable per the eyes-open cull (U-2); revisit only if Modern Pentathlon coaching needs it.
- **2D / wrist (Andy's live case):** EX288 Treadwall Intervals is wrist-loaded climbing — dropped via the standard 2D `excluded_exercises` filter (§5), same path as recovery.

### Transition-drill handling (the §5 constituent-sport gate)

The 5 transition/carry keeps split two ways:
- **Cross-discipline (need two separately-scheduled sports): EX175 Brick Run, EX176 Tri Transition.** Their SEM disciplines (Multi-Sport Race, Triathlon, Duathlon) are composites — but "Multi-Sport Race" is broad enough to match an AR athlete whose race is paddle+climb (no bike/run). **§5 gate (ratified):** include EX175/EX176 only if the athlete's discipline set contains **both** a cycling discipline **and** a running discipline. *Which session* they attach to is prompt-steered (§6) — the daily pairing isn't deterministically known at pool-compute time (same limit as recovery placement).
- **Intra-discipline (the transition/carry *is* part of one discipline): EX144 hike-a-bike (Bikepacking/XC-AR Cycling), EX163 portage (Canoeing/LD Paddle Racing), EX170 skimo transition (SkiMo).** Plain SEM discipline-match already gates these correctly — no constituent-sport check needed.

### Ratified reshape

The three ratified decisions (weighting / periodization / adjacency) this catalog drives are in the v2 changelog (top). Part B (the cull) is done + prod-live; **NEXT = the Part A build, A1→A2→A3** (§13a).

---

## 4. Part A — schema changes (Trigger #3) — `payload.py`

A new **session-level `cardio_drills[]` block**, the structural analog of `recovery_exercises[]` (§ Track-1 design v2 §3). It rides `kind=="cardio"` sessions alongside the free-composed `cardio_blocks`; it is **not** a new session `kind`.

```
class CardioDrill(BaseModel):
    exercise_id: str          # enum-bound to the drill pool at the tool boundary
    exercise_name: str
    prescription: str         # free text — "4×50m focus on catch", "6×30s sighting every 3rd"
    instructions: str | None
```

`PlanSession`: add `cardio_drills: list[CardioDrill] | None = None`. Invariants: `cardio_drills` only on `kind=="cardio"`; null/empty elsewhere; each `exercise_id` non-empty. `cardio_blocks` unchanged.

**One drill per session — HARD CAP (Andy 2026-06-19).** The tool-schema sets `cardio_drills` `maxItems: 1` and the pydantic invariant enforces `len ≤ 1`. We don't prescribe more than one skill/drill in a session — a session targets one technical focus, not a drill circuit. The cap is also a reliability lever (§6a-G4): a single-element bounded array is the smallest possible failure surface and removes any "how many drills?" ambiguity from the model. (Field stays a `list` not a scalar to reuse the `recovery_exercises` render/parse/validate path verbatim; the cap is the only difference.)

**Why a session block, not a `cardio_blocks` sub-item:** a drill ("Open Water Sighting") is a discrete catalog movement with its own id/cues, like a `recovery_exercises` entry — not a zone sub-block of a volume workout. Mirroring `recovery_exercises` reuses the entire shipped pattern (pool fn → enum-bind → validator membership → render).

---

## 5. Drill pool computation (deterministic) — `per_phase.py`

`compute_cardio_drill_pool_ids(layer2c_payloads, layer2d_payload, *, disciplines, phase)` — mirrors `compute_recovery_pool_ids` (per_phase.py:520) but with the drill type allowlist + **discipline match** + the **constituent-sport gate** + **phase periodization by drill character**. It reads the same `l2c.exercises_resolved` surface, which already carries per-exercise `discipline_ids` + `priority_per_discipline` (`ResolvedExercise`, context.py:419) — so no separate `sport_exercise_map` read is needed.

- **Type allowlist:** `Technical / Skill`, `Interval / Tempo`, `Aerobic / Endurance` (a `_CARDIO_DRILL_POOL_EXERCISE_TYPES` frozenset, the `_RECOVERY_POOL_EXERCISE_TYPES` analog).
- **2D exclusion:** drop `layer2d.excluded_exercises` ids (wrist/injury contraindications honored — same as recovery; this is what drops EX288 Treadwall for Andy's wrist).
- **Discipline match (no HEAVY/LIGHT — ratified):** keep a drill iff its `discipline_ids` intersect the athlete's included disciplines. The post-cull pool is interval-heavy, and intervals transfer to every discipline they're SEM-tagged to, so there is **no per-discipline pool-suppression tier**. The single residual ("don't push EX070 single-leg cycling on a pure road cyclist") is handled by a §6 prompt de-emphasis note, not by dropping rows.
- **Constituent-sport gate (the cross-discipline transition drills — ratified):** `EX175` Brick Run and `EX176` Tri Transition are included **only if** the athlete's discipline set contains **both** a cycling discipline **and** a running discipline. (Their SEM disciplines — Multi-Sport Race / Triathlon / Duathlon — are composites; "Multi-Sport Race" alone would match an AR-paddle-climb athlete with no bike/run leg.) The other three transition keeps (EX144 hike-a-bike, EX163 portage, EX170 skimo) are intrinsic to a single discipline → the plain discipline-match gates them, no extra check. Implemented as a small `_CONSTITUENT_SPORT_GATE = {"EX175": (cycling_set, running_set), "EX176": (...)}` keyed on the discipline-id families.
- **Phase periodization — by drill character (ratified), not a blanket gate:**
  - **Skill / transition / form** (the 8 T/S): Base → full; Build → reduced; Peak/Taper → drop (race-specific only). The evidence-§3 "front-load drills in Base" finding applies *here*.
  - **Interval + endurance** (12 I/T + 4 A/E): **no phase suppression** — they follow the athlete's normal phase emphasis (VO2/threshold work peaks in Build/Peak). Gating them out of Build/Peak would hide the pool's most useful rows.
  - Implemented as a character-keyed phase gate on the pool, not the schema enum.

Sorted+deduped for deterministic enum ordering (cache-key stability), Rule #15 log on the rows dropped by type / discipline-miss / constituent-gate / phase — same contract as `compute_recovery_pool_ids`, and the §6a-G7 pool-boundary instrumentation.

---

## 6. Prompt changes (Trigger #1) — `per_phase.py`

- `_format_cardio_drill_pool(...)` — the `_format_recovery_exercise_pool` analog (per_phase.py:967). Renders `=== Cardio drill pool (consider these) ===` **grouped under the athlete's discipline headers** (so the model matches `Bike Over-Under → bike session` by reading, not guessing), each row carrying its catalog **`coaching_cue`** (which for the interval rows carries the dose, e.g. EX290 "3–5 min reps at ~95–100% vVO2max; 4–6 reps") and an inline emphasis annotation. **Size-capped** like the recovery pool (≤12 rendered rows; if a multisport union exceeds it, keep the **highest SEM-priority** (`[C]`>`[H]`>`[M]`) per discipline).
- `# Cardio drills` SYSTEM_PROMPT section: *when* to prescribe — **at most one drill per cardio session** (§4 cap); attach a drill **only to a session of its own discipline**; emphasis follows **drill character** (skill/transition drills are a Base-phase tool and fade toward race; interval/endurance drills follow the session's normal phase intent — the menu carries the emphasis annotation). Two specific cautions, in coaching voice: (a) **the form drills don't move steady road economy** — for a pure road run/cycle session, prioritize volume + strength, use a cadence/single-leg cue only for a biomechanics/injury reason (the null-economy finding; mainly EX070); (b) **a transition/brick drill (EX175/EX176) belongs only on a session that pairs the two sports** — a brick run goes on a day with a bike session immediately prior, not on a standalone run. Drills attach to existing cardio sessions; they do not add sessions or volume.
- **Pool-derived, never name-specific (§6a-G1).** The instruction body must stay generic — "*optionally* attach one drill appropriate to today's discipline, **from the pool below**" — and must **never name a specific drill or drill-type** the enum might not contain (no "prescribe a sighting drill"). All specifics come only from the rendered enum, so the prompt can never ask for something the pool lacks.

This is a Trigger #1 prompt-body change → ratify the prompt wording before it ships (per the project's stop-and-ask).

---

## 6a. LLM-reliability guardrails (de-risking the drill assignment) — RATIFIED (Andy 2026-06-19)

The enforced enum-bound mechanism is inherited verbatim from the shipped `strength_exercises`/`recovery_exercises` pattern, so the model **cannot emit an out-of-pool id** and drills carry **only one** validator blocker (membership) with **no placement rule** — i.e. *hard*-failure/correction-loop-churn is already unlikely. These guardrails target the residual risks: the *unfillable ask* (hard-fail) and the *wrong pick* (soft-stumble). Tiered by leverage.

**Tier 1 — eliminate hard-fail / churn paths.**
- **G1. Optional + pool-derived prompt (keystone).** `cardio_drills` is nullable / "consider these," **never mandatory** — an optional field cannot produce an unfillable payload. Combined with the §6 pool-derived/never-name-specific rule, the model can never be asked for a drill the enum lacks. (Contrast recovery's *assigned* placement, which could conflict with `daily_window_fit` and churn.)
- **G2. Exactly one hard constraint.** Membership (enum-backstopped) is the **only** drill blocker. Discipline-fit, phase emphasis, and dosage are steered by render+prompt, **not** added as validator rules — one hard rule = minimal deadlock surface. Explicitly **resist** a discipline-match or drill-count validator (§8).
- **G3. Validate the `cardio_drills` invariants INSIDE the per-session try/except.** The `only-on-cardio` + `≤1` checks must run where a violation becomes a `schema_violation` **retry**, not a hard 500. (Carried watch-out: the race-week-brief handoff flagged `_check_two_per_day` running *outside* the per-override try/except → a non-contiguous override 500s instead of retrying. The new invariants must not repeat that — wire them into the retryable path.)

**Tier 2 — eliminate the soft-stumble (wrong pick).**
- **G4. Legible, capped rendering (§6).** Group by the athlete's discipline, carry each row's `coaching_cue`, annotate phase-emphasis, cap the rendered pool (≤12) **and** cap per-session drills at **1** (§4). A grouped+cued+bounded menu turns selection into matching, not guessing — the dominant lever for pick-quality on a multisport athlete's large union pool.
- **G5. Discipline-scoping via prompt, not a rule.** The residual soft-risk (a swim drill on a run session, both in-pool for a multisport athlete) is handled by the grouped render + the explicit "own-discipline-only" instruction — **not** a hard discipline-match validator (which would reintroduce churn). A rare mis-attach is a quality nit, not a failure. **Open call (§13):** tighten to a soft `severity=warning` discipline-match check later *only if* it bites live.
- **G6. Part B first = a clean enum (upstream guarantee).** The worst stumble is the model dutifully picking an *in-pool* row that's junk or mis-tagged. The §3a audit guarantees every pool row is genuinely prescribable and correctly discipline-tagged **before the pool exists** — garbage-in → garbage-pick. This is an independent reason the ratified B→A sequencing is itself a de-risk.

**Tier 3 — bound the blast radius if it does churn.**
- **G7. Rule #15 instrumentation at the pool boundary.** Log the computed drill pool (`ids + discipline + phase`) per session and any membership-reject `detail`, so a live stumble is a one-read `/admin/logs` diagnosis — not a pv=69-style reverse-engineering. (Inherits `compute_recovery_pool_ids`' Rule #15 log pattern, §5.)
- **G8. Keep drills out of the volume/ACWR/band math (§8)** so a drill can't interact with the existing correction-loop pressure — they carry no `discipline_id` and add no prescribed volume.

---

## 7. Enforcement (RATIFIED: enforced enum-bound) + the free-compose reconciliation

Andy ratified **enforced enum-bound** (over the advisory option I recommended). Reconciled with "cardio stays LLM-composed" as follows, and flagged because the tension is real:

- **Enforcement binds the drill *vocabulary*, not the *presence* of drills.** The `cardio_drills[*].exercise_id` is enum-bound to `compute_cardio_drill_pool_ids(...)` at the tool boundary (mirrors `strength_exercises`/`recovery_exercises`: per_phase.py:682-686), so an out-of-catalog or wrong-discipline drill is structurally impossible. A validator membership rule (§8) backstops the injected/`model_construct` path.
- **Volume/zone composition stays free.** The LLM still decides *whether* a cardio session carries drills and how much volume — guided by the Base-emphasized prompt — and `cardio_blocks` are untouched. So "enforced" means *if you name a drill it must be a real, discipline-appropriate, phase-appropriate catalog drill*, not *every cardio session must contain drills*.
- **Empty-pool fallback (mirrors recovery):** when the pool resolves empty (no discipline match / Peak-Taper gate / all 2D-excluded), the caller passes no enum (schema falls back to free string) **and** the prompt block is suppressed — the LLM is never handed an unfillable `cardio_drills[]`. The §8 validator rule skips on empty pool (no re-freeze).

**Open tension to watch (§14):** the binding now mostly bites on well-evidenced interval/endurance work (the cull removed the marginal form-drill bulk). The one weak-evidence row left in the LIGHT-economy zone is EX070 single-leg cycling, handled by a §6 prompt de-emphasis rather than enum-suppression.

---

## 8. Validator (`validator.py`)

- **`_rule_cardio_drill_pool_membership`** — the `_rule_recovery_pool_membership` analog (validator.py:722): every `cardio_drills[*].exercise_id` ∈ `compute_cardio_drill_pool_ids(...)`. Blocker; lazy-imports `per_phase` to dodge the cycle; **skips on no-2C / empty-pool** (empty-pool owned by suppress, blocking would re-freeze).
- **This is the ONLY drill blocker (§6a-G2).** No discipline-match rule, no drill-count rule. The `≤1`-per-session and `only-on-cardio` caps live as **pydantic invariants on the retryable path (§6a-G3)**, not as validator rules — a slip self-corrects via `schema_violation` retry rather than churning a blocker.
- **No placement rule.** Drills ride cardio sessions; they are not date-placed, so there is no `compute_recovery_placement` analog. (Phase periodization is a render gate, not a per-date constraint.)
- Drills are excluded from volume-band/ACWR/strength-count/discipline-gate by construction (they carry no `discipline_id` and add no prescribed volume) — confirm during build, same as recovery's §8 sweep.

---

## 9. Render (`templates/plan_create/view.html`)

Cardio session card gains a subordinate `cardio_drills` list (the `recovery_exercises` render branch analog, Track-1 Slice 3a §9) — drill name + prescription. CSS reuse from `.sess-recovery`.

---

## 10. Caching

`hashing.py` `LAYER4_PROMPT_REVISION` bump (current "10" → "11"): the prompt body + tool schema change, so cached plans regenerate with drills on next plan-gen. The drill-pool ids fold into the existing cache key the same way the recovery pool did.

---

## 11. Edge cases

- **Empty pool** → suppress + free-string fallback (§7). Rare post-cull — even a pure road marathoner matches the run interval rows (EX178/EX179/EX290/EX048/EX049).
- **No discipline match** (none of the athlete's disciplines tag any surviving drill) → empty pool → suppress; acceptable.
- **Peak/Taper** → skill/transition drills dropped; **interval/endurance drills retained**, following the session's normal phase intent (not force-emptied — that was the v1 blanket gate, now reshaped).
- **2D wrist contraindication** (Andy's live case) → wrist-loaded drills (EX288 Treadwall) dropped via the 2D exclusion, same as recovery.
- **Refresh / single-session paths** → no `phase`/discipline cone in some contexts → pool may no-op; validator guards on context (mirrors recovery placement-match guard).

---

## 12. Test plan

- `compute_cardio_drill_pool_ids`: type allowlist; 2D exclusion (EX288 drops for a wrist case); discipline match (SEM intersect); **constituent-sport gate** (EX175/EX176 present only when the athlete has both a cycling and a running discipline; absent otherwise); **phase-by-character** (skill/transition dropped in Peak/Taper, interval/endurance retained); deterministic ordering; empty-pool.
- Schema: `cardio_drills` only on cardio; **`maxItems:1` — a 2-drill payload rejects (§4 / §6a-G4)**; enum-bind present when pool non-empty, free-string when empty; invariants.
- **Guardrails (§6a):** the `only-on-cardio` + `≤1` invariants raise a **retryable `schema_violation`, not a 500** (G3); membership is the only blocker — no discipline-match/count rule (G2); a wrong-discipline-but-in-pool drill is accepted by the validator (G5, render/prompt-steered).
- `_rule_cardio_drill_pool_membership`: in-pool passes, out-of-pool blocks, empty-pool skips, no-2C skips.
- Render branch; cache-key includes drill-pool hash.
- (Part B catalog is already prod-live via `0017`/`0018` — not part of the Part-A build.)

---

## 13. Decisions

**Ratified (Andy 2026-06-18 / -06-19):**
- Sequencing: **Part B (cull) → Part A (pool)**.
- Binding: **enforced enum-bound** (reconciled per §7 — binds vocabulary, not presence).
- **One drill per session — hard cap `maxItems:1`** (2026-06-19, §4).
- **§6a LLM-reliability guardrails G1–G8** (2026-06-19) — optional+pool-derived prompt; one membership blocker only; retryable invariants; legible capped render; discipline-scope via prompt not rule; clean-enum-first; Rule #15 logging.
- **Interval/Tempo scope** (2026-06-19) — **include** the Interval/Tempo rows in the drill pool now (not deferred to #337); they carry their `coaching_cue` dose. See §3a.

**Ratified v2 (Andy 2026-06-19) — the post-cull reshape (see the v2 changelog + §5):**
- **Part B = the aggressive cull** (keep 8 / retire 47) + EX290–292 adds, shipped `0017`/`0018`, **prod-live**. (Supersedes v1's hygiene-only Part B.)
- **Weighting** — drop pool-level HEAVY/LIGHT; SEM-match + a §6 prompt de-emphasis note for the lone form drill (EX070).
- **Periodization** — by drill character (skill/transition Base-heavy → dropped Peak/Taper; interval/endurance follow normal phase emphasis).
- **Adjacency** — prompt-steered placement + a deterministic constituent-sport pool gate on EX175/EX176 (athlete needs both a cycling and a running discipline).

**Ratified (Andy 2026-06-19, A2 prep session):**
- **Prompt-body wording** (§6 / §6a-G1) — **RATIFIED verbatim** (Trigger #1 cleared). The `# Cardio drills` SYSTEM_PROMPT section + the `=== Cardio drill pool (consider these) ===` render header/row format are signed off as drafted in the A2-prep handoff §"Drafted prompt body"; build them as-is.
- **Coaching-cue handling — thread the cue through 2C** (over render-without-cue). The catalog `coaching_cues` (dose) was NOT reachable from `l2c.exercises_resolved`; Andy chose the Trigger-#3 cross-layer add over shipping the render without it. **DONE this session (A1.5):** `coaching_cues` now threads 0B → `_load_exercises` SELECT → `_dedupe_by_exercise` → `ResolvedExercise.coaching_cue` (`layer2c/builder.py` + `layer4/context.py` + `Layer2C_Spec.md` §7). A2's `_format_cardio_drill_pool` reads `rx.coaching_cue` for the per-row dose.

**Open (ratify before the respective slice lands):**
- **Constituent-sport gate taxonomy (§5) — OPEN, blocks A2.** `_CONSTITUENT_SPORT_GATE` needs the concrete `discipline_id` sets that count as "a cycling discipline" and "a running discipline" (the EX175/EX176 include test). The live `layer0.disciplines` id space is **not** cleanly hardcodeable from the container (ids reused across sports + heavy version drift; the `primary_movement` column is the likeliest clean classifier but must be read live). Decide the source before building the gate: (a) explicit hardcoded cycling/running `discipline_id` frozensets, or (b) derive from `disciplines.primary_movement` / a modality-group families read. Without the gate, EX175 Brick Run leaks to AR-paddle-climb athletes (incl. Andy's PGE set) — so A2's pool is not shippable until this is resolved.
- **Tighten-later (§6a-G5):** add a soft `severity=warning` discipline-match check **only if** wrong-discipline picks show up live — kept out of v1 to avoid churn.

---

## 13a. Build slices (>5 files → split per the 5-file ceiling)

- **~~B (catalog)~~ — DONE + PROD-LIVE** via `0017` (cull 55→8) + `0018` (EX290–292). No further catalog work for Part A.
- **A1 — schema:** `payload.py` `CardioDrill` + field + invariants + tests. No prompt/cache. **DONE (#755).**
- **A1.5 — 2C coaching-cue threading:** `layer2c/builder.py` (SELECT `e.coaching_cues` + dedupe + construction) + `layer4/context.py` (`ResolvedExercise.coaching_cue`) + `Layer2C_Spec.md` §7 + tests. Additive, defaulted None. **DONE (this session)** — unblocks A2's cue-carrying render.
- **A2 — pool + prompt + cache:** `per_phase.py` `compute_cardio_drill_pool_ids` + `_format_cardio_drill_pool` (reads `rx.coaching_cue`) + `# Cardio drills` section + schema enum-bind thread; `hashing.py` revision bump. Prompt ratified ✅; **still gated on the §13 constituent-sport gate taxonomy decision.**
- **A3 — validator + render:** `validator.py` `_rule_cardio_drill_pool_membership`; `templates/plan_create/view.html` + CSS.

---

## 14. Gut check

**Risks / what might be missing / best argument against:**
- **The cull made the pool interval-heavy — which is actually *stronger*-evidence ground than v1.** The marginal-evidence worry in v1 was the form-drill (LIGHT) tier; post-cull the only surviving form drill is EX070, handled by a prompt de-emphasis (not enum-suppression), and the bulk of the pool is well-evidenced interval/endurance work. The residual soft-risk is a drill surfacing on a phase/session where it adds little — bounded by the optional field (G1) + character periodization (§5).
- **Soft-nudge risk inverted — largely closed by §6a.** With enforced binding the failure mode flips from "LLM ignores the pool" (advisory) to "LLM is blocked/retries when it names a sensible drill we didn't tag to that discipline." **§6a-G1 defuses the *freeze* form of this**: drills are *optional*, so a too-narrow/partial pool makes the model **omit** a drill, not churn a blocker — the residual is under-use (a missed nudge), not a stall. Suppress-on-empty + skip-on-empty cover the empty case; the discipline tagging in §3a (G6) still matters, but now for *coverage quality*, not for *not-freezing*.
- **Best argument against the whole track:** cardio volume stays free-composed regardless, so the *performance* delta is concentrated in technical disciplines (swim/paddle/ski) — but that is precisely AIDSTATION's underserved-discipline market and Andy's own PGE race (packraft/technical-MTB/scramble/climb), so the asset is on-target rather than incidental. The bigger near-term value is arguably **Part B's catalog hygiene** (real correctness — conflation fix + dead-row removal), which lands first regardless.
- **Open dependency:** the structured-interval question (#337) is deliberately walled off; if Andy wants catalog-driven interval *structure*, that's a separate, larger design and this drill pool should not try to absorb it.
