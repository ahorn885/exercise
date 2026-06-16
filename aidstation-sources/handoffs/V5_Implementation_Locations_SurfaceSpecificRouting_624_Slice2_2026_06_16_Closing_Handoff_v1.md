# V5 Implementation — #624 Slice 2: grid session-typing (surface-routing per-slot binding) — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/aidstation-surface-routing-ddhuyv`
**PR:** #640 — opened ready-for-review, auto-merge enabled, awaiting CI (Layer 0 integrity gate + Python unit suite + JS harness).
**Design:** `designs/Layer4_SurfaceSpecificRouting_624_Design_v2.md` (bumped from v1 — Slice 2 as-built; v1 archived under `archive/superseded-specs/`).
**Predecessor handoff:** `handoffs/V5_Implementation_Locations_SurfaceSpecificRouting_624_2026_06_16_Closing_Handoff_v1.md` (#624 Slice 1, PR #639 merged).

Picked up from the Slice-1 closing handoff ("check it out and let's keep going"). Rule #9 sweep clean (all Slice-1 §8 anchors on disk; tree even with `origin/main`). Andy chose **Slice 2** (grid session-typing) for the next arc slice and directed me to **verify #622's `0007` migration is applied + update docs**.

---

## 1. First — #622 `0007` verified live (the carried owed item, now closed)

Andy: "622 migration is done. verify and update docs appropriately." Triggered the read-only `neon-query` workflow against prod Neon. **Confirmed `0007` is fully applied:**

| check | result |
|---|---|
| active vessels left in `equipment_items` | **0** (0C retired all 9) |
| new craft aliases | **raft→D-019, sup→D-032, tt_bike→D-007** (0A, all 3) |
| new craft-terrain rows | **7** (tt_bike 2 + raft 3 + sup 2) |
| max active `0A` alias version | **0A-v1.6.8** (digest bumped → craft caches invalidated) |
| active exercises still naming a vessel | **0** (0B de-drifted) |

→ Dropped the "`layer0-apply` for `0007` owed" line from both the `CURRENT_STATE.md` Slice-1 entry and the #622 predecessor entry. (Query gotcha for next time: `equipment_required` is a `text[]`, not `text` — use `array_to_string(...) ILIKE ANY (...)`, not `ILIKE` directly.)

## 2. What shipped — Slice 2

### The gap
Slice 1 made *surface-per-purpose* deterministic (`surface_routes`: aerobic→groomed, vert→hills, technical→technical). But the grid still handed the synthesizer only per-discipline session **counts** + a **week-level** easy/hard `IntensityMix`, with the prompt explicitly saying "distribute the easy/hard count as you see fit." So *how many* sessions of each purpose a discipline gets — and therefore which surface routes actually get used — stayed the LLM's call. Slice 2 types each discipline's sessions into deterministic purpose slots so the Slice-1 routing binds to real per-slot counts.

### Binding depth (Andy ratified via `AskUserQuestion`)
**Count-deterministic** — fix the per-discipline long/easy/quality **counts** deterministically; let the LLM pick which surface (vert vs technical) each **quality** session uses, from `surface_routes`. Rejected: (a) a fully-deterministic vert-vs-technical split — fabricates a coaching rule with no basis when both surfaces are present; (b) a prompt-only no-op — leaves the per-purpose counts non-deterministic, the exact gap Slice 2 exists to close.

### The build (3 substantive code files + design + tests)
- **`layer4/session_grid.py`** — new `SessionTypeSplit` frozen model (`long`/`easy`/`quality` + `total`); `DisciplineAllocation.session_types: SessionTypeSplit | None = None` (set only on cardio allocations with ≥1 session; strength + zero-session rows stay `None`). New `_type_sessions(allocations, phase_name, intensity)` run inside `build_session_grid` right after `_intensity_mix`: distributes the week `intensity.hard_count` across cardio disciplines proportional to their session counts (largest-remainder, capped per discipline) so **`sum(quality) == hard_count` exactly**; remaining aerobic sessions are `easy`, except the **primary** (highest-load-weight, i.e. first in the load-sorted allocations) discipline carves one `long` LSD cornerstone in every phase but **Taper** (`aerobic >= 1` guard) → **`sum(long + easy) == easy_count`**. The per-discipline typing and the week-level polarized mix are consistent by construction. `SessionTypeSplit` added to `__all__`.
- **`layer4/per_phase.py`** — `_format_session_grid` renders a per-discipline typing line (`Session types (deterministic): 1× long (LSD, aerobic) + 5× easy (aerobic) + 1× quality (vert/technical).`); the week mix line reworded to "aggregate cross-check." Rule #15 `build_session_grid` log line gains the per-discipline `(L#/E#/Q#)` typing. **Prompt body (Trigger #1):** the `=== Session grid ===` guidance lists per-discipline typing as authoritative and directs **long + easy → the aerobic surface; quality → the vert/technical surface** (from the feasibility surface routing), race-sim long day = one quality session.
- **`layer4/hashing.py`** — `LAYER4_PROMPT_REVISION` `"5"`→`"6"` (synthesis directive changed → cached plans cold re-synth).
- **`tests/test_layer4_session_grid.py`** — new `TestSessionTypes` (5 tests): quality-sums-to-hard_count + total==sessions; primary carves one long, secondary none; Taper drops long; strength not typed; no-negative-easy / quality≤sessions across all phases.

### Worked example (Build, trail_running lw=3 / mtb lw=2, 14h)
`trail_running` 7 sessions → 1 long + 5 easy + 1 quality; `mtb_outdoor` 4 → 0 long + 3 easy + 1 quality. `sum(quality)=2 == hard_count`; `sum(long+easy)=9 == easy_count`. Primary gets the long anchor; secondary doesn't. Deterministic.

### Scope containment
`build_session_grid` / `_format_session_grid` are used only in `per_phase.py` (create path). The T2/T3 refresh prompts carry the LSD-anchor rule as **prose** and do **not** call the grid → untouched. The validator's `intensity_dist` rule is zone-hours-based → orthogonal, untouched.

**Verification:** `tests/` **2492 passed / 30 skipped** (was 2487; +5 new); `etl/tests/` **89 passed**. **NO DDL** (Python-only) → Layer-0 gate + JS harness unaffected.

## 3. Deferred — Slice 3 (craft disciplines)
Bike/paddle keep the existing `resolve_craft_terrain_feasibility` cascade; surface-purpose routing + session-typing there is the open follow-up (the craft tier composes craft ownership with terrain — more involved). **#624 stays OPEN, narrowed to Slice 3.**

## 4. STILL OWED
- ⬜ **post-#572 live T3 *refresh* re-verify** (Rule #14) — needs a live refresh on a real plan + the diag token. Unrelated to this session. (#622's `0007` apply is **no longer owed** — verified live this session, see §1.)

## 5. NEXT STEPS — the "Locations & Gear" arc continues
- **#624 Slice 3** (craft-discipline surface routing) — the last #624 slice.
- **[#623](https://github.com/ahorn885/exercise/issues/623)** — retire assumed basic gear (Trigger #2; `0007` is the template; audit the 2C cascade first).
- **[#619](https://github.com/ahorn885/exercise/issues/619)** — profile Locations tab + nav IA. Pure UI/IA.

## 6. Bookkeeping done this session
- **`CURRENT_STATE.md`:** new top "Last shipped session" entry (Slice 2); Slice 1 demoted to predecessor; #622 `0007`-owed line dropped (verified live); Slice-1 entry's design ref repointed to v2.
- **Design:** `Layer4_SurfaceSpecificRouting_624_Design_v2.md` (Slice 2 as-built; §3 intro, §4, §6, §7 updated); v1 archived under `archive/superseded-specs/`.
- **GitHub:** PR #640 opened (ready for review) + auto-merge; #624 to be commented with Slice-2 detail, kept OPEN narrowed to Slice 3.
- **`CARRY_FORWARD.md`:** no edit — next-step arc lives in GitHub issues.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Typing model | `layer4/session_grid.py` | `class SessionTypeSplit`; `DisciplineAllocation.session_types`; `"SessionTypeSplit"` in `__all__` |
| Typing algorithm | `layer4/session_grid.py` | `def _type_sessions(`; called in `build_session_grid` after `_intensity_mix`; `sum(quality)==hard_count`, primary carves `long` except Taper |
| Render + prompt | `layer4/per_phase.py` | `Session types (deterministic):` line; `(L{...}/E{...}/Q{...})` in the `build_session_grid` log; prompt body "long + easy → … aerobic surface; quality … vert or technical surface" |
| Prompt revision | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "6"` |
| Unit tests | `tests/test_layer4_session_grid.py` | `class TestSessionTypes`; `test_quality_counts_sum_to_week_hard_count`; `test_primary_discipline_gets_one_long_anchor`; `test_taper_drops_the_long_anchor`; `test_strength_is_not_typed` |
| Design | `designs/Layer4_SurfaceSpecificRouting_624_Design_v2.md` | Slice 1+2 BUILT; Slice 3 deferred; v1 archived |
| Suite | — | tests/ 2492 passed / 30 skipped; etl/tests 89 |
| Gate | — | NO DDL (Python-only); Layer-0 gate + JS harness unaffected |
| #622 verify | — | `0007` live in prod (neon-query: 0 active vessels, 3 aliases @ 0A-v1.6.8, 7 terrain rows, 0 vessel-naming exercises) |
| Issue | #624 | OPEN, narrowed to Slice 3 |
| Owed | — | post-#572 live T3-refresh re-verify carried (Rule #14) |
