# #698 Track 2 Part A — cardio_drills design v2 (post-cull reshape) + A1 schema — Closing Handoff

**Issue:** #698 Track 2 Part A (the original goal: a `cardio_drills` "consider these" session block).
**PR:** [#755](https://github.com/ahorn885/exercise/pull/755) MERGED (squash) — design v2 + A1 schema.
**Branch:** `claude/beautiful-maxwell-9rxsck`.
**Predecessor:** `handoffs/V5_Implementation_CardioCatalog_TechnicalSkillCull_CardioDrillAdds_Track2_698_2026_06_19_Closing_Handoff_v1.md` (Part B — the cull/adds, `0017`/`0018`, prod-live).

---

## 1. What happened (in order)

1. **Resumed after Andy confirmed the cull/adds prod-apply validated.** Rule #9 sweep clean; **independently re-verified prod live** via read-only `neon-query` (run 27808520792): **Technical/Skill = 8, Interval/Tempo = 12, EX290/291/292 active at `0B-v1.6.16`**. Reconciled the doc drift (CURRENT_STATE/CARRY_FORWARD had said "prod-apply owed").
2. **Refreshed the Part-A design to v2** because the aggressive cull **inverted the pool** from skill-drill-heavy (56 rows) to **interval-heavy (24: 8 T/S + 12 I/T + 4 A/E)** — breaking v1's §3a/§5 assumptions.
3. **Got Andy's ratification on the reshape** (AskUserQuestion ×3 — see §3).
4. **Built A1 (schema)** against the refreshed design; full suite green.
5. Shipped as PR #755, auto-merge (squash) → merged green.

## 2. What shipped

- **`designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v2.md`** (v1 → `archive/superseded-specs/` per Rule #12). Reshaped §1 (24-row pool source), §3 (Part B marked HISTORICAL — done via `0017`/`0018`), **§3a (the 24-row catalog + coverage + transition-drill analysis)**, §5 (knobs), §6 (prompt design), §11/§12/§13/§13a/§14 (consistency). Top carries a v2 changelog.
- **A1 — `layer4/payload.py`:** `CardioDrill` model (mirrors `RecoveryExercise`) + `PlanSession.cardio_drills: list[CardioDrill] | None = None` + invariants in `_check_kind_invariants` (only on `kind=='cardio'`; **≤1/session = the `maxItems:1` cap as a pydantic invariant**; non-empty `exercise_id`; `None` on strength/recovery/rest). Additive (default `None`).
- **Tests — `tests/test_layer4_payload.py`:** +7 (accept-one, allow-none, cap-at-one, non-empty-id, + strength/recovery/rest forbid).

## 3. Ratified decisions (Andy, this session — AskUserQuestion ×3)

1. **Weighting — drop pool-level HEAVY/LIGHT.** SEM-match every drill; the lone residual (don't push EX070 single-leg cycling on a pure road cyclist) is a **§6 prompt de-emphasis note**, not pool suppression. Intervals transfer to all SEM-tagged disciplines.
2. **Periodization — by drill character.** Skill/transition/form (the 8 T/S): Base-heavy → dropped Peak/Taper. Interval + endurance (12 I/T + 4 A/E): **no phase suppression** — follow normal phase emphasis (VO2/threshold peak in Build/Peak).
3. **Adjacency — prompt-steered placement + a deterministic constituent-sport pool gate on EX175/EX176** (Brick Run, Tri Transition): include only if the athlete's discipline set holds **both a cycling and a running discipline** (filters the AR-paddle-climb athlete who matches only via the broad "Multi-Sport Race" tag). The other 3 transition keeps (EX144 hike-a-bike, EX163 portage, EX170 skimo) are intra-discipline → plain SEM-match gates them. *Which* session a drill attaches to stays prompt-steered (daily schedule is LLM-composed → not deterministically gateable).

## 4. Validation

- **Full suite 2690 passed / 30 skipped** (`/tmp/venv`, `python -m pytest tests/`); +7 new in `test_layer4_payload.py`.
- PR #755 CI green (Python unit suite + JS harness + Layer-0 gate) → squash-merged. A1 is purely additive (default `None`); no `etl/` change so the Layer-0 gate is untouched.

## 5. Manual verification owed (Andy)

- **None new for A1** — it's a schema-only, additive change with no prod surface yet (`cardio_drills` is never populated until A2 wires the pool + prompt). The Part-B cull is already prod-verified live (predecessor handoff §5 closed).

## 6. Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **A2 (pool + prompt + cache) — GATED on a Trigger-#1 prompt-wording ratification.** Build `per_phase.compute_cardio_drill_pool_ids` (type allowlist + 2D exclusion + SEM-match + the **constituent-sport gate** on EX175/176 + **character-keyed phase periodization**; read `ResolvedExercise.discipline_ids` / `priority_per_discipline` from `l2c.exercises_resolved` — no separate SEM read) + `_format_cardio_drill_pool` (grouped-by-discipline, `coaching_cue`-carrying, ≤12 cap, highest-SEM-priority per discipline) + the `# Cardio drills` SYSTEM_PROMPT section + the schema enum-bind thread + `hashing.LAYER4_PROMPT_REVISION "10"→"11"`. **Bring Andy the verbatim prompt body for sign-off BEFORE shipping A2** (design §13 open).
2. **A3 (validator + render):** `validator._rule_cardio_drill_pool_membership` (the only blocker; skip on empty/no-2C) + `templates/plan_create/view.html` cardio_drills branch + CSS (reuse `.sess-recovery`).
3. Split A2/A3 across sessions for the 5-file ceiling.

## 7. Notes carried forward

- **The A2 prompt is the live gate.** Hardest part: steering "attach a brick/transition drill only on a bike→run day" via prompt + the constituent-sport pool gate, without a hard discipline-match validator (we deliberately keep one blocker = membership, §6a-G2/G5). Draft it for Andy's eyes.
- **Evidence caveat (EX290–292 copy):** prescription numbers are WebSearch-extracted (WebFetch 403-blocked), flagged per-claim in `designs/CardioDrill_EvidenceBased_Additions_EX290-292_2026_06_19.md`. Re-verify against primaries before any reach user-facing coaching copy.
- **Modern Pentathlon now has 0 pool drills** (EX194 Laser-Run was culled by `0017`) — acceptable per the eyes-open cull; revisit only if needed.

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Design v2 | `aidstation-sources/designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v2.md` | "24-row pool catalog"; "constituent-sport gate"; v2 changelog at top; v1 in `archive/superseded-specs/` |
| A1 model | `layer4/payload.py` | `class CardioDrill(_Base)`; `cardio_drills: list[CardioDrill] \| None = None` on `PlanSession` |
| A1 invariants | `layer4/payload.py` | in `_check_kind_invariants`: "at most one cardio_drills entry (maxItems:1)"; "non-empty exercise_id"; `cardio_drills is None` on strength/recovery/rest |
| A1 tests | `tests/test_layer4_payload.py` | `test_cardio_accepts_one_drill`, `test_cardio_drills_capped_at_one`, `test_{strength,recovery,rest}_forbids_cardio_drills` (7 total); `_cardio_drill()` builder |
| Suite | `tests/` | `/tmp/venv/bin/python -m pytest tests/ -q` → 2690 passed / 30 skipped |
| PR / issues | #755 (merged); #698 (open, commented) | — |

## 9. Carry-forward

- **Part B (cull `0017` + adds `0018`) is prod-live**; **A1 (schema) is on main via #755.** Part A remaining: A2 (gated) + A3.
- **Active Layer-0 pool source for Part A = 24 rows** (8 T/S + 12 I/T + 4 A/E) — see design v2 §3a for the per-row catalog with SEM priorities.
- **STILL OWED (carried, unchanged):** post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.
