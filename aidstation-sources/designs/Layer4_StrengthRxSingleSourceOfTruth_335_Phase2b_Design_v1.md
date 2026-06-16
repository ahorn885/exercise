# Layer 4 — Strength Rx: single source of truth + load progression (#335 Phase 2b) — Design v1

**Status:** Decisions LOCKED (Andy, 2026-06-16): **D5 = phase-aware %1RM**, **D7 = identity + load model in one arc (split into PRs)**, **D2 = backfill history to EX-ids**, D3 crosswalk per §4. Implementation underway — PR 1 = the `movement_patterns[]→progression-key` crosswalk (`layer0_progression.py`). Stop-and-ask #3 gate cleared by sign-off.
**Fixes:** #335 (the reopened "strength loads not keyed off capacity records" gap). Phase 2b of `Layer4_StrengthProgramming_Phase2_Design_v2.md` (which deferred "rx_engine absolute loads").
**Date:** 2026-06-16
**Predecessor:** the #335 render slice (PR #662) fixed the double-render + made rx_wire `print()`-visible; this design is the substantive fix behind it.
**Cross-refs:** `rx_engine_spec.md`, `Catalog_Migration_Plan_v3.md` (#430), `Layer4_StrengthProgramming_Phase2_Design_v2.md`.

---

## 1. Problem (confirmed against live prod, pv=71)

Strength sessions never key off the athlete's logged capacity records. Root cause, verified by read-only `neon-query`:

- Capacity records exist and reach Layer 4 — user 1 has 117 `current_rx` rows, 18 weighted.
- `rx_engine.current_rx(db, user_id, exercise_name)` is an **exact string match** between two name-spaces that never align:
  - **Synthesizer (layer0 0B):** `Back Squat (Barbell)`, `Bulgarian Split Squat (DB)`, `Single-Leg Calf Raise (Loaded)` — equipment-qualified.
  - **`current_rx` (v1 seed + Garmin FIT):** `Back Squat`, `Bulgarian Split Squat` — bare.
- Result: pv=71's strength sessions are **100% `first_exposure` (32/32)**, including lifts with real logged weights.

Andy's direction (2026-06-16): **a single source of truth for these names/values — not an alias/normalization bridge** — and the prescription should "take the most-recent-successful baseline, consider it, and issue an appropriate progression."

So this is two coupled problems: **(A) identity** (one catalog the rx path and the synthesizer both key off) and **(B) load progression** (surface a capacity-derived, phase-appropriate load instead of a calibration placeholder).

---

## 2. Current state (grounded)

### 2.1 Two catalogs, two name-spaces
- **`public.exercise_inventory`** — the v1 catalog (`exercise` TEXT UNIQUE, `id` SERIAL, `movement_pattern` single TEXT, `weight_increment`, `discipline`, `type`, `suggested_volume`). Seeded from `EXERCISES` in `init_db.py`. Read in **14 places** (routes/rx, references, injuries, natural_log, training, plans, purchases; `rx_engine.py`; `coaching.py`; init_db backfills).
- **`layer0.exercises`** — the v2 canonical catalog: `exercise_id` (TEXT EX-id), `exercise_name`, `movement_patterns` (TEXT[]), `progression_exercise_id`/`regression_exercise_id` (its own swap graph), `equipment_required`, `physical_proxies`, `coaching_cues`. **No `weight_increment`, no single `movement_pattern`.** Layer 4 / 2C already read exclusively from here.

### 2.2 Per-user strength tables (all FK to `public.exercise_inventory(id)`)
- `current_rx` — `exercise` (TEXT name, the match key), `exercise_id` (int FK), denormalized `discipline`/`type`/`movement_pattern`/`inventory_sugg_volume`/`weight_increment`, `current_*` baseline, **`next_*` projection**, counters. `UNIQUE(user_id, exercise)`.
- `training_log` / `training_log_sets`, `injury_exercise_modifications` (`exercise_id` + `substitute_exercise_id`).

### 2.3 The rx engine (the "logic we designed before" — `rx_engine_spec.md`)
- `apply_session_outcome` computes PROGRESS/REPEAT/REDUCE, promotes the baseline (Family A/B), and writes **`next_*`** — the projected next prescription — on every logged session. Deload + auto-regression included.
- It pulls static fields (`movement_pattern`, `weight_increment`, `discipline`, `type`, `suggested_volume`) from `exercise_inventory` **by name**; no match → `Various` fallback.
- `movement_pattern` selects a `PROGRESSION_RULES` row (keys: Squat/Hinge/Lunge/Push/Pull/Core/Carry/Rotation/Plyo/Balance/Grip/Mobility/Various/…).

### 2.4 The synthesizer already emits the EX-id
`StrengthExercise.exercise_id` (`layer4/payload.py:183`) carries the **layer0 EX-id**, constrained to the 2C feasible pool (Track-2 slice 2a). So the plan side already speaks the canonical identity; only the rx side doesn't.

### 2.5 The two movement-pattern vocabularies differ
- **layer0 `movement_patterns[]` (20, multi-valued, biomechanical):** Squat, Hinge, Carry, Rotation, Push-H/Push-V, Pull-H/Pull-V, Single-Leg, Anti-Extension/Flexion/Rotation/Lateral-Flexion/Adduction, Hip-Ext, Abduction, Isometric, Locomotion, Balance / Proprioception, Stretch.
- **rx `PROGRESSION_RULES` (single-valued):** Squat, Hinge, Lunge, Push, Pull, Core, Carry, Rotation, Plyo, Balance, Grip, Mobility, Various.
- Overlap is partial (Squat/Hinge/Carry/Rotation); the rest needs a deterministic crosswalk.

---

## 3. Target state

**`layer0.exercises.exercise_id` (EX-id) is the single source of truth** for strength exercise identity. The rx path keys off the EX-id, not the name string. The synthesizer already emits it; `current_rx`/`training_log` learn to store it. The exact-name-match failure class disappears by construction — `Back Squat (Barbell)` and a logged `Back Squat` resolve to the **same EX-id** regardless of the display string.

On that foundation, the strength prescription becomes: **the athlete's most-recent-successful baseline (capacity), progressed to a load appropriate for the plan phase's prescribed reps**, with `first_exposure` as the genuine no-history fallback.

---

## 4. Design decisions

### D1 — Identity: match on the layer0 EX-id **[PROPOSED]**
Add `layer0_exercise_id TEXT` to `current_rx` and `training_log`. `rx_wire` looks up the athlete's record by `(user_id, layer0_exercise_id)` using the EX-id the synthesizer already emits (`StrengthExercise.exercise_id`) — no name matching. `rx_engine.current_rx` / `apply_session_outcome` gain an EX-id-keyed path.
- *Why not keep the name as key + normalize:* Andy rejected the bridge; names are unstable (qualifiers, FIT variants) and ambiguous; the EX-id is the catalog's stable key and is already on both sides.
- *Display:* still denormalize `exercise_name` from `layer0.exercises` for human-readable logs (matches the Catalog plan's "denormalize using layer0 canonical names" recommendation), but it is **not** the join key.

### D2 — Historical data: backfill vs wipe **[NEEDS ANDY]**
Andy's 18 weighted records (+99 others) are real dogfooding baselines — the whole point of #335 is to surface them. Two options:
- **(a) One-time name→EX-id backfill [PROPOSED].** Curate a map from Andy's ~117 distinct `current_rx.exercise` names to layer0 EX-ids (fuzzy + HITL, same pattern as Catalog plan Phase 1). Preserves his training history. Some FIT-generic names (`Squat`, `Row`, `Curl`) have no clean single EX-id → flag for his per-item call (Trigger #2-adjacent) or leave unmapped (they stay first-exposure until re-logged).
- **(b) Wipe + regenerate** (Catalog plan Phase-4 "wipe pattern", viable at 1–2 test accounts). Half a session, but throws away Andy's logged baselines — defeats the immediate goal.
- *Recommendation: (a)*, accepting a small unmapped tail.

### D3 — `movement_patterns[]` → progression key crosswalk **[PROPOSED]**
A deterministic, code-level mapping in the rx layer (NOT a new layer0 column — keep v1-rx concerns out of the canonical catalog):
`Squat→Squat`, `Hinge|Hip-Ext→Hinge`, `Single-Leg→Lunge`, `Push-H|Push-V→Push`, `Pull-H|Pull-V→Pull`, `Anti-*|Isometric→Core`, `Carry→Carry`, `Rotation→Rotation`, `Balance / Proprioception→Balance`, `Stretch→Mobility`, `Locomotion→Various`, `Abduction→Various`. When an exercise has multiple patterns, pick the highest-priority compound (Squat/Hinge/Lunge/Push/Pull) else first. Unknown → `Various`.
- *Open:* confirm the priority order with Andy; it determines which dimension the engine bumps.

### D4 — `weight_increment` source **[PROPOSED]**
layer0 has no increment. Drop the per-exercise catalog override; resolve from per-user `current_rx.weight_increment` (when set) → runtime rule (<15 lb → 2.5, else 5) → pattern default. *Pre-check:* count non-null `exercise_inventory.weight_increment` rows; if Andy relies on specific overrides, reconsider. (Likely negligible.)

### D5 — The load model: increment vs phase-aware %1RM **[NEEDS ANDY — the big fork]**
This is the heart of "consider the baseline, issue an appropriate progression."
- **(a) Increment model (exists today).** Surface `current_rx.next_*` — the engine's already-computed projection (last successful + one increment on the priority dimension). Coherent triple `(next_sets, next_reps, next_weight)`. **But** the reps are the athlete's last-logged scheme, which may not match the plan phase's prescribed reps (Base 8–12 vs the logged 5). Showing a 5RM-derived weight at 8 reps misleads.
- **(b) Phase-aware %1RM model (net-new).** Estimate 1RM from the athlete's logged best (`est_1rm`, Epley — already computed but unused in progression), then set the working weight from the **plan phase's prescribed reps** via an RPE/%1RM table (e.g. Build §4: `3×5 @ ~85% e1RM`). The phase owns sets/reps (periodization, `Layer4_StrengthProgramming` §4); the rx layer owns the load. This is what makes the prescription both capacity-grounded *and* phase-appropriate. Falls back to first-exposure / RPE when no history.
- *Recommendation: (b)*, as the honest realization of Andy's words — but it's more logic and a Trigger-#1-adjacent change to how loads are authored. (a) is shippable now and unblocks the visible bug; (b) is the real differentiator (#2 performance-driven auto-updates).

### D6 — Display reconciliation **[PROPOSED, coupled to D5]**
Phase owns `sets × reps` (volume/periodization); rx owns the load. Render `{phase sets} × {phase reps} @ {capacity-derived load}`. Honest only under D5(b) (weight valid for the phase's reps). Under D5(a), show the rx triple as a unit instead. `first_exposure` (calibration template) remains the no-history fallback; `_render_current_rx` already returns load-only (PR #662).

### D7 — Scope & sequencing **[NEEDS ANDY]**
Equipment-catalog unification (`equipment_items`, the other half of #430) is **out of scope** — #335 is exercises only. Proposed slices:
- **Slice A — identity (D1+D3+D4) + surface existing baselines via the increment model (D5a).** Add `layer0_exercise_id`, the crosswalk, EX-id-keyed `rx_wire`/`current_rx`, the D2 backfill. **Delivers the visible #335 fix** (Andy's logged loads finally appear). ~4–5 substantive files (init_db migration, rx_engine, rx_wire, calculations crosswalk, tests).
- **Slice B — phase-aware %1RM load model (D5b + D6).** The differentiator; builds on A.
- **Slice C — retire `public.exercise_inventory` reads route-by-route** (the rest of #430 Phase 3–5: references/injuries/training/plans/purchases/coaching). Separate track; not gating #335.
- *Recommendation:* ship **A** next (closes the user-visible gap, single source of truth for identity), then decide B vs deferring.

---

## 5. Open questions for Andy (lock before code)
1. **D5** — increment model now (a), or go straight to the phase-aware %1RM model (b)?
2. **D2** — backfill Andy's logged history to EX-ids (a), or wipe + regenerate (b)?
3. **D7** — is Slice A the right first cut, or bundle A+B?
4. **D3** — sign off the movement-pattern crosswalk + compound priority order.

---

## 6. Risks / gut check
- **Backfill ambiguity (D2a):** FIT-generic names (`Squat`, `Row`) map to no single EX-id; a wrong map injects a wrong baseline. Mitigation: HITL confirm; leave ambiguous ones unmapped (→ first-exposure, status quo) rather than guess.
- **%1RM model confidence (D5b):** Epley 1RM from sparse/old logs is noisy; %1RM tables are population averages. It's still strictly better than an exact-name miss → calibration text. Cap aggressive jumps; keep RPE as the honest fallback.
- **Crosswalk loss (D3):** collapsing 20 biomechanical patterns to ~12 progression classes loses nuance (a Pull-V and Pull-H both bump as "Pull"). Acceptable — the progression rules only need the dimension to bump, not the full biomechanics.
- **Scope creep:** the full single-source-of-truth (Slice C) is the #430 multi-month migration. This design deliberately scopes #335 to **identity for the strength-rx path** (Slice A) + the load model (Slice B), leaving the v1-route catalog retirement to #430. Best argument against: doing identity-by-EX-id only for `current_rx`/`training_log` leaves `exercise_inventory` alive for the other 12 readers — a partial source-of-truth. Rebuttal: those readers are display/coaching surfaces, not the strength-prescription correctness path; unifying them is #430's job and doesn't block #335.
- **What might be missing:** layer0's own `progression_exercise_id`/`regression_exercise_id` graph is a *different* progression axis (swap to a harder/easier movement) than the rx engine's load progression. Not used here; worth a future note on whether plan-gen should ever swap the exercise (vs just the load) as the athlete advances.

---

**End of design v1 (draft).**
