"""Shared Layer 4 strength-session composition guidance.

Single source of truth for the strength-programming prompt body, imported by
every path that authors strength sessions — `per_phase.py` (new-plan +
plan_refresh T3 cross-phase) and the rolling-window refreshers
`plan_refresh_t1.py` / `plan_refresh_t2.py`. Keeping it here prevents the three
prompts from drifting apart (#335 Phase 2 §B — two-template restructure).

The text is deliberately self-contained: it does not reference caller-specific
prompt blocks (e.g. a rendered exercise pool), so it reads correctly spliced
into any of the three system prompts. Caller-specific tails (exercise-pool
selection, session placement, discipline attribution) stay in each caller.

Evidence basis: see `designs/Layer4_StrengthProgramming_Phase2_Design_v2.md` §A.
The two-template split (programmed vs failover) is the core change — programmed
strength is the heavy/durability economy+resilience work bounded to 2–3×/week;
failover strength is the terrain/craft substitution composed as muscular
endurance to REPLACE an infeasible aerobic session without adding a heavy day.
"""

from __future__ import annotations

# Spliced under each caller's own "# Strength programming" header. No leading
# markdown header here — the header stays caller-side.
STRENGTH_PROGRAMMING_GUIDANCE = """\
Strength sessions come in two kinds. Read the session-grid annotations to tell which you are composing, then follow the matching template. When a session carries no feasibility annotation, it is a PROGRAMMED session.

PROGRAMMED STRENGTH (the default — an elective strength allocation from the grid):
Build it in layers; scale the depth to the phase and the race demands — deeper for long / multi-day / load-carriage races, leaner for short-course:
- Heavy core: 2–3 multi-joint compound lifts (a knee-dominant squat pattern, a hip-hinge / deadlift pattern, optionally one more). 3 sets, 4–6 reps, heavy, explosive concentric intent, NOT to failure, prescribed as RM/RPE targets (e.g. 3×5 @ ~8RM) — never invent absolute weights. This is the strength/economy anchor; keep it tight — extra heavy lifts do not add economy.
- Durability layer (for long / ultra / expedition / load-carriage races): 2–3 eccentric-emphasis movements at moderate load — eccentric or unilateral knee work (split squat, step-down; for descent braking), an eccentric hamstring movement (Nordic, RDL), eccentric calf and tibialis-anterior work. These target the tissues that fail late in multi-day events. Trim or skip for short-course athletes.
- One plyometric / explosive movement (jumps, bounds) for rate-of-force-development and low-speed economy.
- One trunk anti-rotation or loaded carry (suitcase carry, Pallof press) — efficient trunk and grip work; honor any wrist / joint accommodations.
Dose: 2 programmed sessions/week in Base/Build, 1/week in Peak/Taper, never more than 3. In Peak/Taper, trim toward the heavy core plus one plyometric and one carry and cut sets — but keep the load heavy; never maintain by lowering the weight.
Variety: keep the 2–3 heavy compound lifts stable across the phase so they progress, but treat the accessory work — the durability, plyometric, carry, and trunk movements — as a ROTATION, not a fixed template: swap in different accessory exercises week to week and span the movement patterns (knee-dominant, hip-hinge, single-leg, carry, anti-rotation, plyometric) rather than repeating the same handful. Across a phase, draw broadly from the accessory options the athlete has access to; do not let two strength sessions read as the same workout.

FAILOVER STRENGTH (a cardio session the grid flags [TERRAIN-INFEASIBLE] or [NO CRAFT] — compose as a strength substitution, NOT a cardio session):
This session stands in for an infeasible endurance session, so it must REPLACE aerobic work, not add a heavy CNS day:
- Compose as muscular endurance / aerobic-strength: circuits, higher reps (12–20+), short rests, loaded carries, and the durability movements above. Keep the missing session's target hours — a 2-hour infeasible session becomes a long circuit, never two hours of maximal lifting.
- Target the muscles the infeasible discipline demands, drawn from the rendered substitution pool.
- These do NOT count toward the programmed 2–3/week dose, but they ARE capped: the grid hands you at most a bounded number of strength sessions per week (the programmed dose plus a small failover headroom) and deterministically reallocates any excess infeasible volume to feasible disciplines before you compose. Compose only the strength sessions the grid gives you, and compose them light."""

__all__ = ["STRENGTH_PROGRAMMING_GUIDANCE"]
