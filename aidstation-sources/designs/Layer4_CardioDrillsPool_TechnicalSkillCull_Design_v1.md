# Layer 4 — Cardio drills "consider these" pool + Technical/Skill catalog cull — Design

**Status:** v1 — sequencing + binding ratified (Andy 2026-06-18); per-row cull list + discipline-weight map OPEN (ratify before the Part B migration / Part A pool land).
**Issue:** #698 Track 2 (follow-on to the closed Track 1 recovery-session arc, PR #730).
**Evidence base:** `research/RecoveryMobility_RestDay_CardioDrills_EnduranceEvidence_v1.md` §3 (cardio drills vs volume) + §"Design implication".
**Differentiator:** #6 science-backed, and #4 multi-sport-first — the orphaned catalog is overwhelmingly underserved-discipline skill content (paddle, ski, swim, scramble).

---

## 1. Purpose & boundaries

Wire the **orphaned cardio/skill `0B` catalog** into cardio prescription, and **audit/cull** the Technical/Skill rows that feed it.

Today `cardio_blocks` are **free-composed** by the synthesizer from prompt zone/interval guidance; there is **no cardio analog of `_format_strength_exercise_pool`**, so the structured cardio catalog is never fed to the model (#698 comments 2026-06-17). Active rows with no prescription home:

| `exercise_type` | active | character |
|---|---|---|
| Technical / Skill | 65 | discipline skill drills — paddle strokes, ski/climb/descent technique, navigation, swim drills |
| Interval / Tempo | 8 | structured intervals — Threshold/VO2/Sweet-Spot (bike), Hill Repeats, Tempo/Marathon-pace run, Rowing/erg |
| Aerobic / Endurance | 4 | Paddling/Rowing erg, Sustained LISS, Freestyle Pull, Kicking drill |

**This design's scope:** a **`cardio_drills[]` session block** (the `recovery_exercises[]` analog) — enum-bound, discipline-weighted, Base-emphasized — plus the Part B catalog audit that cleans its source rows.

**Out of scope (named, not solved here):**
- **Cardio volume/zone composition stays LLM-composed.** This adds a drills *vocabulary*, not a volume model. We are *not* moving `cardio_blocks` onto the catalog.
- **Structured-interval prescription** (turning `EX074 VO2 Max Intervals (Bike)` into "Z5 4×4min" deterministically) overlaps **#337** and is a *larger* separate design. The Interval/Tempo rows may seed the drill pool, but catalog-driven interval *structure* is deferred (§13 open).
- The **equipment-vocab conflation** (13 rows carrying skill/discipline tokens in `equipment_required`, #698 comment 2026-06-17) is folded into Part B's hygiene pass only because it touches the same rows — see §3.

---

## 2. The two coupled parts + sequencing

Part B (cull) and Part A (pool) are **two sides of one audit**: Part A's pool draws from the surviving Technical/Skill (+ cardio) rows, so the catalog must be clean and discipline-tagged before the pool is defined over it.

**Sequencing — RATIFIED (Andy 2026-06-18): Part B first, then Part A.**

**Reframe (load-bearing):** the snapshot (`etl/output/layer0_etl_v1.8.0.sql`, active rows) shows the 65 Technical/Skill rows are **overwhelmingly legitimate, high-value, well-cued discipline drills** (e.g. `EX093 Eskimo Roll Practice`, `EX140 Open Water Sighting Drill`, `EX166 Ferry & Eddy Turn`, `EX212 Scrambling Technique`). **Part B is therefore an asset inventory + narrow hygiene cull, NOT a mass deletion.** The survivors are the product asset; the cull removes only genuinely non-prescribable/duplicate rows and fixes vocabulary conflation.

---

## 3. Part B — Technical/Skill audit & cull (Trigger #2)

A read-only audit of all 65 active `Technical / Skill` rows (+ the 8 Interval/Tempo + 4 Aerobic/Endurance), producing a per-row disposition. Output is a **layer0 migration**; every removal/edit is Andy-ratified before it lands (no-padding rule applies in reverse — no cull without review).

**Disposition buckets:**
1. **KEEP + discipline-tag (expected majority).** The row is a prescribable, discipline-relevant drill. Confirm its `sport_exercise_map` membership + `terrain_required` so the pool can discipline-weight it (§5). No content change.
2. **HYGIENE-FIX (the 13 conflation rows).** Skill/discipline tokens mis-filed in `equipment_required` (`Climbing — roped` ×8 → skill-capability gate #336; `Touring/AT ski setup` ×4, `Mountaineering` ×1 → `terrain_required`/discipline). Move the token to the correct gate; correct `equipment_required`. These rows otherwise KEEP.
3. **CULL (expected few).** Genuinely non-prescribable (no real training stimulus / pure logistics, e.g. candidate `EX094 Packraft Inflation/Deflation Drill`, `EX123 Pack Fit Optimization Drill` — gear-handling, not a session) or exact-duplicate of another row. Each cull cites the reason + any inbound `physical_proxies`/substitute references to repoint.

**Deliverable:** an audit table (`exercise_id | name | discipline | terrain | disposition | reason`) appended to this design as §3a before the migration, ratified by Andy. The migration supersedes culled rows (`superseded_at`, not hard-delete — Rule #12 history) and applies hygiene edits.

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

**Why a session block, not a `cardio_blocks` sub-item:** a drill ("Open Water Sighting") is a discrete catalog movement with its own id/cues, like a `recovery_exercises` entry — not a zone sub-block of a volume workout. Mirroring `recovery_exercises` reuses the entire shipped pattern (pool fn → enum-bind → validator membership → render).

---

## 5. Drill pool computation (deterministic) — `per_phase.py`

`compute_cardio_drill_pool_ids(layer2c_payloads, layer2d_payload, *, disciplines, phase)` — mirrors `compute_recovery_pool_ids` (per_phase.py:520) but with the drill type allowlist + **discipline weighting** + **phase periodization**:

- **Type allowlist:** `Technical / Skill`, `Interval / Tempo`, `Aerobic / Endurance` (a `_CARDIO_DRILL_POOL_EXERCISE_TYPES` frozenset, the `_RECOVERY_POOL_EXERCISE_TYPES` analog).
- **2D exclusion:** drop `layer2d.excluded_exercises` ids (wrist/injury contraindications honored — same as recovery).
- **Discipline weighting (evidence §3 — the load-bearing knob):**
  - **HEAVY** (drills transfer): swimming, paddle sports (kayak/canoe/packraft/SUP/raft), swimrun, technical MTB, ski/skimo, climbing/scrambling. Surface the full discipline-matched pool.
  - **LIGHT** (drills don't move economy — MA null): steady road running, road cycling. Surface a *minimal* set (the few rows like `EX051/052 Up/Downhill Running Technique`, `EX186 High Cadence Spin`, `EX070 Single-Leg Cycling`) and the prompt de-emphasizes them.
  - The exact discipline→tier map is §13 OPEN (ratify with the §3a audit, since both key on the same discipline tags).
- **Phase periodization (evidence §3 "front-loaded in Base, displaced toward Build/Peak/taper"):** Base → full weighted pool; Build → reduced; Peak/Taper → race-specific technical only (or empty). Implemented as a phase gate on the rendered pool, not the schema enum.

Sorted+deduped for deterministic enum ordering (cache-key stability), Rule #15 log on type/discipline-dropped rows — same contract as `compute_recovery_pool_ids`.

---

## 6. Prompt changes (Trigger #1) — `per_phase.py`

- `_format_cardio_drill_pool(...)` — the `_format_recovery_exercise_pool` analog (per_phase.py:967). Renders `=== Cardio drill pool (consider these) ===` with each drill's id/name/cue, grouped/annotated by discipline-weight tier and the current phase emphasis.
- `# Cardio drills` SYSTEM_PROMPT section: *when* to prescribe — Base-heavy, technical-discipline-heavy; **explicitly caution against over-prescribing running/cycling form drills** (coaching-voice rendering of the null-economy finding: "form drills don't move running economy — prioritize volume + strength; use cadence cues only for injury/biomechanics"). Drills attach to existing cardio sessions; they do not add sessions or volume.

This is a Trigger #1 prompt-body change → ratify the prompt wording before it ships (per the project's stop-and-ask).

---

## 7. Enforcement (RATIFIED: enforced enum-bound) + the free-compose reconciliation

Andy ratified **enforced enum-bound** (over the advisory option I recommended). Reconciled with "cardio stays LLM-composed" as follows, and flagged because the tension is real:

- **Enforcement binds the drill *vocabulary*, not the *presence* of drills.** The `cardio_drills[*].exercise_id` is enum-bound to `compute_cardio_drill_pool_ids(...)` at the tool boundary (mirrors `strength_exercises`/`recovery_exercises`: per_phase.py:682-686), so an out-of-catalog or wrong-discipline drill is structurally impossible. A validator membership rule (§8) backstops the injected/`model_construct` path.
- **Volume/zone composition stays free.** The LLM still decides *whether* a cardio session carries drills and how much volume — guided by the Base-emphasized prompt — and `cardio_blocks` are untouched. So "enforced" means *if you name a drill it must be a real, discipline-appropriate, phase-appropriate catalog drill*, not *every cardio session must contain drills*.
- **Empty-pool fallback (mirrors recovery):** when the pool resolves empty (no discipline match / Peak-Taper gate / all 2D-excluded), the caller passes no enum (schema falls back to free string) **and** the prompt block is suppressed — the LLM is never handed an unfillable `cardio_drills[]`. The §8 validator rule skips on empty pool (no re-freeze).

**Open tension to watch (§14):** enum-binding a *marginal-evidence* lever is stronger than the evidence strictly supports for the LIGHT tier. The phase/discipline gating keeps the LIGHT-tier pool tiny, so the binding mostly bites where evidence is strong (swim/paddle/ski).

---

## 8. Validator (`validator.py`)

- **`_rule_cardio_drill_pool_membership`** — the `_rule_recovery_pool_membership` analog (validator.py:722): every `cardio_drills[*].exercise_id` ∈ `compute_cardio_drill_pool_ids(...)`. Blocker; lazy-imports `per_phase` to dodge the cycle; **skips on no-2C / empty-pool** (empty-pool owned by suppress, blocking would re-freeze).
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

- **Empty pool** → suppress + free-string fallback (§7).
- **No discipline match** (athlete's disciplines all LIGHT-tier, e.g. road marathoner) → minimal/empty pool; prompt de-emphasizes; acceptable (evidence says drills don't help here).
- **Peak/Taper** → race-specific technical only or empty.
- **2D wrist contraindication** (Andy's live case) → wrist-loaded drills (some climbing rows) dropped via the 2D exclusion, same as recovery.
- **Refresh / single-session paths** → no `phase`/discipline cone in some contexts → pool may no-op; validator guards on context (mirrors recovery placement-match guard).

---

## 12. Test plan

- `compute_cardio_drill_pool_ids`: type allowlist; 2D exclusion; discipline weighting (HEAVY surfaces full, LIGHT minimal); phase periodization (Base full, Peak empty); deterministic ordering; empty-pool.
- Schema: `cardio_drills` only on cardio; enum-bind present when pool non-empty, free-string when empty; invariants.
- `_rule_cardio_drill_pool_membership`: in-pool passes, out-of-pool blocks, empty-pool skips, no-2C skips.
- Render branch; cache-key includes drill-pool hash.
- Part B: the audit migration validates against the CI layer0 gate (postgres + snapshot + `validate_layer0`); culled-row inbound proxy/substitute references repointed.

---

## 13. Decisions

**Ratified (Andy 2026-06-18):**
- Sequencing: **Part B (cull) → Part A (pool)**.
- Binding: **enforced enum-bound** (reconciled per §7 — binds vocabulary, not presence).

**Open (ratify before the respective slice lands):**
- **§3a per-row cull/keep/hygiene list** — the actual dispositions for the 65+12 rows (Trigger #2; no cull without review).
- **Discipline→weight-tier map** — which disciplines are HEAVY vs LIGHT (decided with §3a, same tags).
- **Prompt-body wording** (§6) — Trigger #1 ratification.
- **Interval/Tempo scope** — are the 8 Interval/Tempo rows in the *drill* pool, or reserved for a future catalog-driven interval-structure design (#337)? Recommend: include `Aerobic/Endurance` + technical drills now; **defer** structured intervals to #337 to avoid conflating "skill drill" with "interval prescription."

---

## 13a. Build slices (>5 files → split per the 5-file ceiling)

- **B1 — audit + cull migration:** §3a audit table (ratified) → one layer0 migration (supersede culls + hygiene edits) + repoint inbound proxies. Bookkeeping + `etl/` only.
- **A1 — schema:** `payload.py` `CardioDrill` + field + invariants + tests. No prompt/cache.
- **A2 — pool + prompt + cache:** `per_phase.py` `compute_cardio_drill_pool_ids` + `_format_cardio_drill_pool` + `# Cardio drills` section + schema enum-bind thread; `hashing.py` revision bump. (Prompt ratified first.)
- **A3 — validator + render:** `validator.py` `_rule_cardio_drill_pool_membership`; `templates/plan_create/view.html` + CSS.

---

## 14. Gut check

**Risks / what might be missing / best argument against:**
- **The evidence is genuinely mixed and the binding is strong.** Enum-enforcing a marginal lever (LIGHT tier) over-commits relative to the science; §7's phase/discipline gating is what keeps that honest — if the gating is weak, we hard-gate something that doesn't matter. Watch the LIGHT-tier pool stays near-empty.
- **Soft-nudge risk inverted.** With enforced binding the failure mode flips from "LLM ignores the pool" (advisory) to "LLM is blocked/retries when it names a sensible drill we didn't tag to that discipline" — i.e. a too-narrow pool causes correction-loop churn. The discipline tagging in §3a is therefore load-bearing for *not freezing*, same lesson as the recovery placement rule. Suppress-on-empty + skip-on-empty mitigate the empty case; the *partial* case (pool has rows but not the one the LLM wanted) is the new risk.
- **Best argument against the whole track:** cardio volume stays free-composed regardless, so the *performance* delta is concentrated in technical disciplines (swim/paddle/ski) — but that is precisely AIDSTATION's underserved-discipline market and Andy's own PGE race (packraft/technical-MTB/scramble/climb), so the asset is on-target rather than incidental. The bigger near-term value is arguably **Part B's catalog hygiene** (real correctness — conflation fix + dead-row removal), which lands first regardless.
- **Open dependency:** the structured-interval question (#337) is deliberately walled off; if Andy wants catalog-driven interval *structure*, that's a separate, larger design and this drill pool should not try to absorb it.
