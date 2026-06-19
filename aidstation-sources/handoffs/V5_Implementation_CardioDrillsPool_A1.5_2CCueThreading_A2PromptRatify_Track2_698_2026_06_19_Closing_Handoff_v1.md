# #698 Track 2 Part A — A1.5 (2C coaching-cue threading) + A2 prompt-body ratified — Closing Handoff

**Issue:** #698 Track 2 Part A (the `cardio_drills` "consider these" session block).
**PR:** _this branch_ `claude/cardio-drills-pool-impl-0zki9l` (A1.5 — 2C cue threading; auto-merge enabled).
**Predecessor:** `handoffs/V5_Implementation_CardioDrillsPool_DesignV2_A1Schema_Track2_698_2026_06_19_Closing_Handoff_v1.md` (design v2 + A1 schema, on main via #755).

---

## 1. What happened (in order)

1. **Resumed the A1 handoff** ("check it out and keep going"). **Rule #9 sweep clean** — `verify-handoff.sh` green; spot-checked A1 on disk: `CardioDrill` model + invariants + 7 tests present in `layer4/payload.py` / `tests/test_layer4_payload.py`; merged on main via #755.
2. **Drafted the A2 prompt body** (the Trigger-#1 gate the predecessor flagged) and brought it to Andy.
3. **Andy ratified the prompt body AS-IS** (AskUserQuestion) → Trigger #1 cleared. The verbatim wording is preserved in §7 below.
4. **Surfaced a design-vs-code gap:** design §6 wants each rendered pool row to carry the catalog `coaching_cue` (interval dose), but `coaching_cues` lives on `layer0.exercises` and was **not threaded through Layer 2C's `ResolvedExercise`** — the render couldn't reach it.
5. **Andy chose "thread the cue through 2C first"** (the Trigger-#3 cross-layer add) over shipping the render without it.
6. **Built A1.5** — the 2C cue threading. Full suite green.

## 2. What shipped (A1.5 — this session)

Threads `layer0.exercises.coaching_cues` → `ResolvedExercise.coaching_cue` so A2's `_format_cardio_drill_pool` can render the dose. **Additive, defaulted None** — pre-change cached 2C payloads hydrate cleanly; no behavior change for existing consumers.

- **`layer2c/builder.py`:** `_load_exercises` SQL adds `e.coaching_cues` to the SELECT; `_dedupe_by_exercise` adds `"coaching_cue": r.get("coaching_cues")` to the per-exercise entry (per-exercise, not per-discipline → on the entry, not a dict); the `ResolvedExercise(...)` construction passes `coaching_cue=ex.get("coaching_cue")`.
- **`layer4/context.py`:** `ResolvedExercise.coaching_cue: str | None = None` (defaulted).
- **`aidstation-sources/specs/Layer2C_Spec.md`:** §7 `ResolvedExercise` schema gains `coaching_cue`.
- **`tests/test_layer2c.py`:** `_ex_row` gains a `coaching_cues=` param; +2 tests (`test_coaching_cue_passes_through`, `test_coaching_cue_defaults_none_when_absent`).
- **`aidstation-sources/designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v2.md`:** §13 records the ratifications (prompt body ✅, cue-through-2C ✅) + adds the constituent-sport-gate-taxonomy open item; §13a marks A1.5 DONE.

## 3. Ratified decisions (Andy, this session)

1. **A2 prompt body — ratified verbatim** (Trigger #1 cleared). Build the §7 wording as-is.
2. **Coaching-cue handling — thread through 2C** (over render-without-cue). Done as A1.5.

## 4. Validation

- **Full suite 2692 passed / 30 skipped** (`/tmp/venv`, `python -m pytest tests/ -q`); +2 in `test_layer2c.py`.
- Isolated single-file collection still hits the documented circular-import quirk → run the full `tests/`.
- No DDL / no migration: `coaching_cues` is an existing `layer0.exercises` column (read-only add to the 2C SELECT) → Layer-0 gate untouched.

## 5. Manual verification owed (Andy)

- **None new for A1.5** — schema-only pass-through, no prod surface until A2 renders the pool. (`coaching_cue` is populated on every 2C build going forward but read by nothing until A2.)

## 6. Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next move = A2 (pool + prompt + cache).** Prompt body is ratified (§7). **A2 is gated on ONE remaining decision:**

- **CONSTITUENT-SPORT GATE TAXONOMY (design §13 open) — bring to Andy before building the pool fn.** `compute_cardio_drill_pool_ids` must include EX175 (Brick Run) / EX176 (Tri Transition) **only if** the athlete's discipline set holds **both** a cycling discipline AND a running discipline (§5). This needs the concrete `discipline_id` sets for "cycling" and "running." The live `layer0.disciplines` id space is **not cleanly hardcodeable from the container** (ids reused across sports + heavy version drift; see the failed parse in this session). Two options to put to Andy:
  - **(a) Hardcoded frozensets** of cycling / running `discipline_id`s in `per_phase.py` (`_CONSTITUENT_SPORT_GATE`). Simple, but brittle to canon changes and needs a live `neon-query` to enumerate the right ids first.
  - **(b) Derive from `disciplines.primary_movement`** (or a modality-group families read) — robust to id drift, but needs that column threaded/queried. Likely the cleaner classifier; confirm its live values via `neon-query` first.
  - Without the gate, EX175 Brick Run leaks to the AR-paddle-climb athlete (incl. **Andy's own PGE set** — packraft/MTB/climb, no run+bike pairing in the brick sense) → A2's pool is **not shippable** until resolved.

**A2 build checklist (once the gate decision lands):**
1. `per_phase.py` `compute_cardio_drill_pool_ids(layer2c_payloads, layer2d_payload, *, disciplines, phase)` — type allowlist (`Technical / Skill`, `Interval / Tempo`, `Aerobic / Endurance` frozenset) + 2D exclusion + discipline-match (intersect `ResolvedExercise.discipline_ids`) + the constituent-sport gate + character-keyed phase periodization (skill/transition Base-heavy→drop Peak/Taper; interval/endurance no suppression). Sorted+deduped. Rule #15 log on rows dropped by type/discipline/gate/phase.
2. `per_phase.py` `_format_cardio_drill_pool(...)` — the §7 render; grouped by discipline, **reads `rx.coaching_cue` for the per-row dose**, character annotation, ≤12 cap (highest SEM-priority per discipline on overflow).
3. `per_phase.py` `# Cardio drills` SYSTEM_PROMPT section — §7 verbatim.
4. `per_phase.py` enum-bind thread — `_session_schema` + `build_record_phase_sessions_tool` gain `cardio_drill_pool_ids` (mirror `recovery_pool_ids` exactly: `{"type":"string","enum":cardio_drill_pool_ids} if cardio_drill_pool_ids else {"type":"string"}` on `cardio_drills[*].exercise_id`, `maxItems:1` already in the payload invariant); production caller computes the pool + passes it; suppress the render block when the pool is empty.
5. `hashing.py` `LAYER4_PROMPT_REVISION "10"→"11"`.
6. Tests: type allowlist; 2D exclusion (EX288 drops for wrist); discipline-match; constituent-sport gate (EX175/176 present iff cycling+running both present); phase-by-character; deterministic order; empty-pool; enum-bind present when non-empty / free-string when empty; cue renders in the menu.

**A3 (after A2):** `validator._rule_cardio_drill_pool_membership` (only blocker; skip on empty/no-2C) + `templates/plan_create/view.html` cardio_drills branch + CSS (reuse `.sess-recovery`).

**5-file ceiling:** A2 is ~`per_phase.py` + `hashing.py` + tests (3–4) — fits. A3 is its own slice (§13a).

## 7. The ratified A2 prompt body (Rule #11 — build verbatim)

### 7.1 New `# Cardio drills` section in `per_phase.py` `SYSTEM_PROMPT` (place after `# Recovery programming`)

> # Cardio drills
>
> A cardio session may optionally carry **one** drill from the `=== Cardio drill pool (consider these) ===` menu — a discrete, catalog-defined skill, transition, or interval drill that sharpens a discipline (a brick run, a single-leg cycling drill, a swim CSS set). Drills are optional and additive to the session's free-composed `cardio_blocks`: they refine *how* a session trains a discipline; they do not add sessions or volume. Most cardio sessions carry none.
>
> - **At most one drill per session.** A session targets one technical focus, not a drill circuit. Never emit more than one `cardio_drills` entry.
> - **Pick only from the rendered pool, by id.** Choose `exercise_id`s from the menu only — never invent one, and never name a drill or drill-type that isn't in the menu. If no menu is rendered, prescribe no drills.
> - **Attach a drill only to a session of its own discipline.** The menu is grouped under each discipline header; a drill belongs on a session training that discipline (a bike over-under on a bike session, a swim set on a swim session), never on an unrelated one.
> - **Emphasis follows the drill's character, noted inline per row.** Skill/transition/form drills are a Base-phase tool — build technique early and let them fade toward the race. Interval and endurance drills follow the session's normal phase intent (threshold/VO2 work belongs in Build/Peak).
> - **Two cautions:** (a) a form/cadence drill does **not** move steady road economy — for a pure road run or ride, prioritize volume and strength, and reach for a cadence/single-leg cue only for a specific biomechanics or injury reason, not as default seasoning; (b) a brick or transition drill belongs **only** on a day that actually pairs the two sports — a brick run goes on a day with a bike session immediately before it, not on a standalone run.
> - Give each drill a free-text `prescription` (e.g. "4×50m, focus on catch", "15 min off the bike at goal pace") and brief `instructions`. `cardio_drills` rides `kind='cardio'` sessions only; leave it null on strength / recovery / rest.

### 7.2 Rendered pool header + per-row format (`_format_cardio_drill_pool`)

```
=== Cardio drill pool (consider these) ===
Optionally attach one drill appropriate to today's discipline, from the pool below (pick by id only):
- <Discipline name>:
  - EX073 (Threshold Intervals (Bike)) — <coaching_cue> [interval — follow phase intent]
  - EX292 (Bike Over-Under Intervals) — <coaching_cue> [interval — follow phase intent]
- <Discipline name>:
  - EX175 (Brick Run Drill (Bike-to-Run)) — <coaching_cue> [transition — Base tool, fades to race]
```

- `<coaching_cue>` = `rx.coaching_cue` (now available via A1.5); omit the ` — <cue>` segment when None.
- Bracket annotation = the phase-emphasis-by-character tag the pool fn computes (skill/transition vs interval/endurance).
- Grouped by discipline; ≤12 rows; highest SEM-priority (`[C]`>`[H]`>`[M]`) per discipline on overflow (§6/§6a-G4).

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| 2C cue (SQL) | `layer2c/builder.py` | `e.coaching_cues` in `_load_exercises` SELECT; `"coaching_cue": r.get("coaching_cues")` in `_dedupe_by_exercise`; `coaching_cue=ex.get("coaching_cue")` in `ResolvedExercise(...)` |
| 2C cue (model) | `layer4/context.py` | `coaching_cue: str \| None = None` on `class ResolvedExercise(_Base)` |
| 2C cue (spec) | `aidstation-sources/specs/Layer2C_Spec.md` | `coaching_cue` in the `ResolvedExercise` dataclass (§7) |
| 2C cue (tests) | `tests/test_layer2c.py` | `test_coaching_cue_passes_through`, `test_coaching_cue_defaults_none_when_absent`; `_ex_row(..., coaching_cues=...)` |
| Design ratify | `aidstation-sources/designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v2.md` | §13 "RATIFIED verbatim" prompt body + "thread the cue through 2C"; §13 open "Constituent-sport gate taxonomy"; §13a A1.5 DONE |
| Suite | `tests/` | `/tmp/venv/bin/python -m pytest tests/ -q` → 2692 passed / 30 skipped |
| PR / issues | this branch PR; #698 (open, commented) | — |

## 9. Carry-forward

- **A1 (schema) + A1.5 (2C cue threading) DONE.** Part A remaining: **A2 (gated on the constituent-sport gate taxonomy decision) + A3.**
- **Active Part-A pool source = 24 rows** (8 T/S + 12 I/T + 4 A/E) — design v2 §3a.
- **STILL OWED (carried, unchanged):** post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.
