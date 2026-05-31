# V5 Implementation — Layer 3B/4: reach race day + 2-week terminal Taper (#334)

**Date:** 2026-05-31
**Branch:** `claude/layer4-reach-race-day-334` (PR #346, merged squash `c3f14b3`)
**Also merged this session:** PR #345 (#333 volume-band sentinel guard, squash `e29053c`) — see §5.
**Suite:** 1851 passed / 16 skipped. **No migration.**

---

## 1. What shipped

Fixed **#334** — event-mode plans stopped ~1 week short of race day and dropped the Taper phase. Spec-first (two amendments), then implementation, then split to its own PR.

### Root cause (two compounding bugs)

1. **3B horizon floored.** `layer3b/builder.py::_time_to_event_weeks` did `days // 7`; a 48-day gap → 6 weeks not 7, dropping the final partial week.
2. **Taper rounded away.** `layer4/phase_structure.py::_allocate_weeks_standard` used `int()` truncation; a sub-1-week Taper share floored to 0 and was dropped (`if weeks <= 0: continue`), so `scope_end_date` landed on Peak's end. A dropped Taper *also* silently kills the Decision-4 race-week brief + Taper `coaching_flags` (they only attach to an existing Taper phase).

### The fix

- **3B horizon** (`_time_to_event_weeks`): `days // 7` → race-day-inclusive `ceil((days + 1) / 7)`. The `+1` counts race day, so an exact-multiple gap (race day = first day of next week) still pulls in the week containing race day; `ceil` gives the partial final week a full week so the plan spans *through* race day. Past events clamp to 0. PGE 48-day gap → 7 weeks, ends exactly on race day.
- **Layer 4 terminal floor** (`_allocate_weeks_standard`, new `terminal_phase_min_weeks` param): event mode floors the terminal phase (Taper) at **2 weeks** (taper wk + race wk). Race week stays the final Taper week — **no 5th phase**. Shortfall reclaimed one week at a time from a non-terminal phase (Base first when present, else largest remaining) without driving any preceding phase below 1 week; `sum == total_weeks` preserved. Open-ended/custom modes unchanged. Event mode detected via `layer3b_payload.time_to_event_weeks is not None`, threaded in by `phase_structure_from_3b`. `plan_create.py` fallback total-weeks calc mirrors the same ceil.
- **Safety insulation** (DNF-recurrence trigger, `layer3b/builder.py`): the recovery-window check (`weeks < window`) now computes a conservative **floor** of full weeks locally, NOT the new plan-horizon ceil. The ceil would inflate the count by up to a week and silently suppress the warning at the window boundary (a 77-day gap is genuinely inside the 12-week `quad_failure` window, but ceil reads 12). Trigger fires at exactly its pre-#334 boundary — no false-negative.

### Worked allocations (event mode)

| start | mode | weeks | allocation |
|---|---|---|---|
| Base | standard | 7 (PGE) | Base 2 / Build 2 / Peak 1 / **Taper 2** |
| Build | standard | 6 (was Build5/Peak1/Taper0) | Build 3 / Peak 1 / **Taper 2** |
| Peak | standard | 2 (degenerate) | Peak 1 / Taper 1 (floor is a target, won't starve a phase) |

---

## 2. Design decisions (Andy, this session)

1. **Terminal floor = ≥2 weeks** (taper week → race week), not ≥1. Rationale: long-duration target events (expedition AR / multi-day ultra) need the taper to actually taper (week 1) before the event week (week 2). Race week is the final Taper week, not a new phase.
2. **Race-day-inclusive ceil** (`+1`): chosen so an exact-multiple gap doesn't end a day short. Guarantees "never ends *before* race day."
3. **Split #334 to its own PR** (#346) off main, restoring #345 to #333-only — the two had stacked on one branch.

---

## 3. Known residual → issue #347

Whole-week phase structure + no `event_date` clamp ⇒ the plan can **overshoot** race day by up to 6 days when race day falls early in a week (e.g. 42-day gap → 7 weeks → ends 6 days after the race). **Exact / no-impact for PGE** (race day = last day of the final week). Trimming the final week to land precisely on race day needs a **session-level** clamp — filed as **#347** (`layer:4` / `area:plan-gen` / `type:bug` / `v2`), deferred (larger, session-grained change).

---

## 4. Files changed (all on `main`)

| File | Change |
|---|---|
| `layer3b/builder.py` | `_time_to_event_weeks` → race-day-inclusive ceil; DNF-recurrence check uses local floor |
| `layer4/phase_structure.py` | `_allocate_weeks_standard` `terminal_phase_min_weeks` param + reclaim; `phase_structure_from_3b` event-mode detection |
| `layer4/plan_create.py` | fallback total-weeks calc mirrors the ceil |
| `aidstation-sources/Layer3_3B_Spec.md` | §5.1 #334 amendment (ceil rationale) |
| `aidstation-sources/Layer4_Spec.md` | §6.1 #334 amendment (terminal floor + reclaim rule) |
| `tests/test_layer3b_builder.py` | helper + builder assertions updated for ceil; past-event clamp case |
| `tests/test_layer4_phase_structure.py` | new `TestPhaseStructureEventModeTerminalFloor` (5 cases + open-ended control) |

---

## 5. PR #345 (#333) also merged

#345 (volume-band `(0,0)` sentinel guard in `templates/plan_create/view.html`) had stacked on the same branch as #334. After splitting #334 out, #345's branch was rebuilt as one clean commit off `main` (the pre-squash #344 commit was causing a `dirty` mergeable state) and merged (`e29053c`). Net change: the single guard line. #333 stays **open** (multi-item epic; #345 was "Part of", not "Fixes").

---

## 6. Next moves

The go-live board still runs through the §14 coherence sign-off. #333 (phase-label visibility) is the gate; its render pieces (#344 labels, #345 sentinel guard) are now live. #334 (reach race day) is closed. **Recommended next: re-run the PGE e2e (a fresh `pv`) to verify (a) the plan now spans through 2026-07-17 with a 2-week Taper, and (b) the §14 within-phase coherence read Andy owes.** Then the remaining #333 sub-items / the orphaned-field family (#295/#316).

**Cache note:** #334 changes the `time_to_event_weeks` value, so the first post-deploy event-mode generation is a cold cone (the cone hashes that value into Layer 4 keys) — expected, not a regression.

### 6.3 Operating notes for next session (read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

---

## 8. Rule #10 verification table

| Claim | File | Anchor string | Check |
|---|---|---|---|
| 3B ceil horizon | `layer3b/builder.py` | `ceil((days + 1) / 7)` | `grep` |
| DNF check uses floor | `layer3b/builder.py` | `full_weeks_to_event` | `grep` |
| Terminal-phase floor + reclaim | `layer4/phase_structure.py` | `terminal_phase_min_weeks` | `grep` |
| Event-mode detection | `layer4/phase_structure.py` | `2 if layer3b_payload.time_to_event_weeks is not None else 0` | `grep` |
| plan_create fallback ceil | `layer4/plan_create.py` | `ceil((days + 1) / 7)` | `grep` |
| 3B spec amendment | `aidstation-sources/Layer3_3B_Spec.md` | `race-day-inclusive` | `grep` |
| L4 spec amendment | `aidstation-sources/Layer4_Spec.md` | `guaranteed **≥ 2 weeks**` | `grep` |
| Event-mode terminal test | `tests/test_layer4_phase_structure.py` | `TestPhaseStructureEventModeTerminalFloor` | `grep` |
| #334 merged | `main` | `c3f14b3` Layer 3B/4: reach race day | `git log` |
| #345 merged | `main` | `e29053c` volume-band sentinel | `git log` |
| #347 filed | GitHub | clamp final plan week to land on race day | issues |
