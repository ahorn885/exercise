# #698 Track 2 Part A — A1.5 + A2 + A3: cardio_drills pool COMPLETE — Closing Handoff

**Issue:** #698 Track 2 Part A (the `cardio_drills` "consider these" session block).
**PRs:** [#760](https://github.com/ahorn885/exercise/pull/760) MERGED (A1.5 + A2) + a follow-on PR on `claude/cardio-drills-pool-impl-0zki9l` (A3 — validator + render).
**Predecessor:** `handoffs/V5_Implementation_CardioDrillsPool_DesignV2_A1Schema_Track2_698_2026_06_19_Closing_Handoff_v1.md` (design v2 + A1 schema, on main via #755).

> **Part A is code-COMPLETE this session:** A1 (#755) + A1.5 + A2 (#760, merged) + A3 (this PR). The `cardio_drills` block is wired end-to-end on the plan-create path — schema, 2C cue threading, pool fn, prompt, enum-bind, cache bump, validator blocker, render. Only **live-verify** (a real plan generating a drill) remains owed.

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
- **`aidstation-sources/designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v2.md`:** §13 records the ratifications (prompt body ✅, cue-through-2C ✅, constituent-sport gate taxonomy resolved ✅); §13a marks A1.5 + A2 DONE.

## 2b. What shipped (A2 — pool + prompt + cache, this session)

The `cardio_drills` block wired end-to-end on the plan-create per-phase path. The ratified prompt body (§7) + the A1.5 `coaching_cue` make the pool a read-not-guess menu.

- **`layer4/per_phase.py`:**
  - `compute_cardio_drill_pool_ids(layer2c_payloads, layer2d_payload, *, disciplines, phase)` — type allowlist (`_CARDIO_DRILL_POOL_EXERCISE_TYPES` = T/S, I/T, A/E) + 2D exclusion + discipline-match (`discipline_ids` ∩ included) + **constituent-sport gate** (`_constituent_sport_gate_ok` — EX175/EX176 require both a cycling AND a running discipline) + **character periodization** (`_cardio_drill_phase_allows` — Technical/Skill drops in Peak/Taper; Interval/Tempo + Aerobic/Endurance always kept). Sorted+deduped. Rule #15 log: `compute_cardio_drill_pool_ids: phase=… athlete_disciplines=… pool=… dropped(…)`.
  - `_format_cardio_drill_pool(...)` — grouped under discipline headers (load-weight order), reads `rx.coaching_cue` for the per-row dose, character tag, highest-SEM-priority first, capped at `_CARDIO_DRILL_POOL_CAP=12`.
  - `# Cardio drills` SYSTEM_PROMPT section (§7.1 verbatim) + the `=== Cardio drill pool (consider these) ===` render block in `render_user_prompt` (suppress-on-empty).
  - enum-bind: `_session_schema` / `build_record_phase_sessions_tool` / `synthesize_phase` thread `cardio_drill_pool_ids` onto `cardio_drills[*].exercise_id` (enum when non-empty, free string when empty), `maxItems:1`.
- **`layer4/hashing.py`:** `LAYER4_PROMPT_REVISION "10" → "11"`.
- **`tests/test_layer4_cardio_drill_pool.py` (NEW):** +13 (compute filters/gate/phase/empty, render grouping/cue/cap/empty, schema enum-bind + cap, prompt section).
- **Constituent-sport gate taxonomy (the §13 open item) — RESOLVED.** Read the live `layer0.disciplines.primary_movement` (read-only neon-query run 27828748291): clean — `cycling` = {D-006, D-007, D-008, D-030, D-031}, `running` = {D-001, D-002, D-024, D-027}. Hardcoded as `_CYCLING_DISCIPLINE_IDS` / `_RUNNING_DISCIPLINE_IDS` frozensets in `per_phase.py` (grounded in that read, commented for re-derivation). Chose hardcode over threading `primary_movement` through the L4 context (simplicity-first; D-id is stable locked-canon) — **flagged for Andy's review in the PR.**

## 2c. Scope note (A2/A3 = plan-create path only)

A2/A3 wire `cardio_drills` into the **plan-create per-phase synthesizer + validator + view** only. The refresh / single-session / race-week-brief paths are untouched (the field defaults `None`, so they're unaffected). Extending drills to those paths is a separate, later slice if wanted.

## 2d. What shipped (A3 — validator + render, this session)

- **`layer4/validator.py`:** `_rule_cardio_drill_pool_membership` — the `_rule_recovery_pool_membership` analog. Every `cardio_drills[*].exercise_id` ∈ `compute_cardio_drill_pool_ids(...)`. **Blocker; the ONLY drill rule** (§6a-G2). Lazy-imports `per_phase` (cycle dodge). Pool is phase-scoped → computed per distinct phase (memoized → one Rule #15 log line per phase). Skips on no-2C / no-2A / empty-pool (suppress-on-empty owns empty). Registered in `_ALL_RULES` after `_rule_recovery_placement_match`.
- **`templates/plan_create/view.html`:** a `cardio_drills` render branch on the cardio session card (after `cardio_blocks`) — drill name + a `drill` chip + prescription + instructions. **Reuses `.sess-exercises`/`.sess-exercise`/`.chip` — no new CSS** (drills ride the cardio card; no card-level class needed, unlike recovery's `.sess-recovery`). No route change — `cardio_drills` rides `PlanSession` like `recovery_exercises`, already passed to the template.
- **`tests/test_layer4_validator.py`:** `_cardio_session` gains a `cardio_drills=` param; +4 tests (in-pool no-fire, out-of-pool blocks, skip-without-2C, skip-when-empty).
- Full suite **2716 passed / 30 skipped** (+4).

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

**Part A (A1 + A1.5 + A2 + A3) is code-COMPLETE.** Everything is wired on the plan-create path; the suite is green at 2716.

**Next moves (priority order):**
1. **LIVE-VERIFY (Andy-action) — the only thing owed for Part A.** Generate a real plan for a multi-discipline athlete (Andy's PGE set works — it has cycling D-008 + running D-001 so EX175 surfaces) and confirm: (a) `/admin/logs` shows the `compute_cardio_drill_pool_ids: phase=… pool=…` line with a sensible pool; (b) the plan view renders a `cardio_drills` drill (name + `drill` chip + prescription) on at least one cardio session; (c) no `cardio_drill_pool_membership` blocker churn. Note: A2 bumped `LAYER4_PROMPT_REVISION 10→11`, so cached plans regenerate on next plan-gen — a fresh plan will exercise the new path.
2. **Optional follow-ups (file as issues if wanted):** extend `cardio_drills` to the refresh / single-session / race-week-brief synthesizers (currently plan-create only, §2c); the §6a-G5 soft `severity=warning` discipline-match check **only if** wrong-discipline picks show up live; the #337 catalog-driven interval *structure* (deliberately walled off, design §13).

**5-file ceiling:** A3 was `validator.py` + `view.html` + tests (3) — fit.

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
| A2 pool fn | `layer4/per_phase.py` | `def compute_cardio_drill_pool_ids`; `_CARDIO_DRILL_POOL_EXERCISE_TYPES`; `_CYCLING_DISCIPLINE_IDS`/`_RUNNING_DISCIPLINE_IDS`; `_constituent_sport_gate_ok`; `_cardio_drill_phase_allows` |
| A2 render + prompt | `layer4/per_phase.py` | `def _format_cardio_drill_pool` (reads `rx.coaching_cue`); `# Cardio drills` in `SYSTEM_PROMPT`; `=== Cardio drill pool (consider these) ===` in `render_user_prompt`; `cardio_drill_pool_ids` threaded through `_session_schema`/`build_record_phase_sessions_tool`/`synthesize_phase` (`maxItems:1`) |
| A2 cache | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "11"` |
| A2 tests | `tests/test_layer4_cardio_drill_pool.py` | 13 tests (compute/render/schema/prompt) |
| A3 validator | `layer4/validator.py` | `def _rule_cardio_drill_pool_membership`; in `_ALL_RULES` after `_rule_recovery_placement_match` |
| A3 render | `templates/plan_create/view.html` | `{% if sess.kind == 'cardio' and sess.cardio_drills %}` branch + `drill` chip |
| A3 tests | `tests/test_layer4_validator.py` | `test_cardio_drill_pool_membership_*` (4); `_cardio_session(..., cardio_drills=...)` |
| Design | `aidstation-sources/designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v2.md` | §13 ratifications + constituent-sport gate RESOLVED; §13a A1.5/A2/A3 DONE |
| Suite | `tests/` | `/tmp/venv/bin/python -m pytest tests/ -q` → 2716 passed / 30 skipped |
| PRs / issues | #760 MERGED (A1.5+A2); A3 PR (this branch); #698 (open, commented) | — |

## 9. Carry-forward

- **Part A COMPLETE: A1 (#755) + A1.5 + A2 (#760, merged) + A3 (this PR).** The only thing owed is **live-verify** (§6 move 1).
- **Active Part-A pool source = 24 rows** (8 T/S + 12 I/T + 4 A/E) — design v2 §3a. Cache bumped to revision "11" → next plan-gen regenerates with drills.
- **STILL OWED (carried, unchanged):** post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.
