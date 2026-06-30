# V5 Implementation — Data-Pipeline Campaign, Phase 3: #340 Off-Trail / Trackless Terrain — Reuse Existing TRN-018 (No New Vocab) — Closing Handoff (2026-06-30)

**Branch:** `claude/data-pipeline-phase-3-6-uxcpv3`
**Commits:** `afca826` (discipline attach + tests), `9c7de1d` (migration `0035`)
**PR:** [#1077](https://github.com/ahorn885/exercise/pull/1077) — **bundled #269 + #340 (Andy's call), auto-merge armed (merge commit).** Self-merges once the required checks pass.
**Campaign kickoff:** `handoffs/DataPipeline_Phase1-2_Done_Phase3-6_Kickoff_Handoff.md`
**Issue:** [#340](https://github.com/ahorn885/exercise/issues/340) (closes on merge)

---

## 1. The pivot — no new terrain (no-padding trigger #2)

The kickoff planned a NEW `TRN-021` "Off-Trail / Trackless" terrain, attached to D-001/D-003/D-024/D-018 — **conditioned on "after confirming no existing terrain covers the trackless stimulus."** That confirmation **failed**:

- **TRN-018 "Off Trail / Bushwhack"** already exists in the live vocab (genesis `0C-v1.6.7`, active, `race_eligible=true`, `simulatable='none'`). Its notes: *"Trackless off-trail ground — scrub brush, tall grass, bushwhacking through vegetated or untracked terrain. No path at all. … Expedition-AR stimulus."* That is exactly TRN-021's intended stimulus.
- **Tell that the plan missed it:** the kickoff listed **D-003 Trekking** among disciplines to attach the new terrain to — but TRN-018 was **already** in D-003's required-terrain set. (Also corroborated: `designs/Layer4_DeterminismFirst_Synthesis_Design_v2.md:350` shows Andy planned this terrain on 2026-06-06 as "Off-Trail / Bush"; it landed as TRN-018 on 2026-06-10.)

Adding TRN-021 would have been textbook padding. I stopped (Stop-and-ask trigger #2) and surfaced it. **Andy chose (AskUserQuestion 2026-06-30): reuse TRN-018 + add the gap rule.**

---

## 2. What shipped

**(a) Attach existing TRN-018 — `layer4/session_feasibility.py` (commit `afca826`).** Added `TRN-018` to `_DISCIPLINE_REQUIRED_TERRAINS` for **D-001** Trail Running, **D-024** Mountain Running, **D-018** Mountaineering (D-003 Trekking already carried it). The map is an any-of frozenset (a session is feasible at a locale carrying ANY required terrain), so this broadens feasibility + recognizes the trackless demand for those disciplines. Code only — that map is not DB-backed. Map comment notes the #340 reuse. Tests updated: `test_d018_mountaineering_matches_any_of_four` (was three), and `required_terrains` exact-set asserts for D-018 + D-001.

**(b) Gap rules — migration `etl/migrations/layer0/0035_trn018_off_trail_gap_rules.sql` (commit `9c7de1d`).** TRN-018 had **no** `terrain_gap_rules` row, so once it became required, an athlete whose locale lacked trackless terrain got no proxy/adaptation guidance. Added 3 bridgeable proxies (best→worst):

| proxy | severity | fidelity | rationale |
|---|---|---|---|
| TRN-003 Technical Trail | medium | 0.50 | closest footing analog (rocky/root, uneven) |
| TRN-007 Technical Rock / Scree | high | 0.45 | strong unstable-footing transfer; rock, no vegetation |
| TRN-002 Groomed Trail | high | 0.40 | aerobic base / unpaved gait only |

Andy's call: **groomed + scree are low-fidelity proxies** (both land in the high-severity band; Technical Trail is the moderate one). Inserted at bumped `etl_version 0C-v2.5` (serving-relevant → the terrain-gap digest advances → plan-gen caches invalidate). Idempotent: `(target_terrain_id, proxy_terrain_id, etl_version)` UNIQUE + `ON CONFLICT DO NOTHING`.

**Citations reuse repo-vetted bases — no fabricated research.** Off-trail = footing (Myer et al. 2006, J Athl Train — already cited on the TRN-003 rule) + route-finding (Dyer et al. 2016 — already cited on the TRN-006 Fell/Moorland rule).

---

## 3. Verification

- **Real-Postgres gate (the gold standard for a migration):** stood up a throwaway PG16, loaded the `v1.10.1` baseline (CI strip of `\restrict`/`\unrestrict`/`SET transaction_timeout`), applied both `0034`s + `0035` in order — all clean (`0035` → `INSERT 0 3`). `python -m etl.layer0.validate_layer0` → **PASS, all 13 checks clean** (incl. `phase_load_allocation_aggregators: 0`, which re-confirms #269). The 3 TRN-018 rows verified present/correct; re-apply → `INSERT 0 0` (idempotent).
- Full pytest suite: **4104 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B warnings).
- No `terrain_gap_rules` gate check exists, so the new rows conform to the spec contract by construction (severity enum, UNIQUE, fidelity bands).

---

## 4. Owed after merge

- **`layer0-apply` of `0035` on prod Neon** (Andy one-tap on the `production` environment). The container has no Neon egress.
- After apply, `0035` will be folded into the next baseline re-dump (per the README redump-fold rule) — not owed now.

---

## 5. PR — bundled (decided)

Andy chose to **bundle**: PR [#1077](https://github.com/ahorn885/exercise/pull/1077) carries both the #269 close-out (Phase 2 tail) and #340 (Phase 3). Auto-merge armed with a **merge commit**, so the per-commit `#269` / `#340` trail stays visible in `main`'s history (revertible individually). After merge: `layer0-apply` `0035`, close #269 + #340, close epic #261.

---

## 6. NEXT — Phase 4: #229 + #233 (THIS IS THE NEXT STEP — CONTINUE HERE)

**The campaign continues with Phase 4 next.** Per the kickoff (`layer2e/builder.py`): promote `_FUELING_BANDS`, `_SPORT_PROFILE_CHO_MOD`, `_MULTIPLIER_BANDS`, and the `_dietary_pattern_adjustments` rules into Layer 0 tables; add `layer0.sport_met_values` + a MET path in `_compute_activity_multiplier()`. Seed with current constants verbatim (behavior-preserving), add loaders, register tables in family `0A`, add gate checks, add a test that table-driven output == old hardcoded output. **Next migration number = `0036`.** Its own PR, off `main` once #1077 merges.

---

## 7. Bookkeeping (Rule #10)

### §7 anchor table (next session's Rule #9 input)

| Claim | File | Anchor / check |
|---|---|---|
| TRN-018 attached to D-001/D-024/D-018 | `layer4/session_feasibility.py` | `grep -c "TRN-018" layer4/session_feasibility.py` → ≥4 (3 map rows + comment) |
| migration present | `etl/migrations/layer0/0035_trn018_off_trail_gap_rules.sql` | exists; 3 `VALUES` rows; `ON CONFLICT … DO NOTHING` |
| gate passes with it | gate | local: baseline + 0034s + 0035 → `validate_layer0` PASS (CI `layer0-gate` re-runs on PR) |
| tests updated | `tests/test_layer4_session_feasibility.py` | `test_d018_mountaineering_matches_any_of_four`; `required_terrains("D-001")` asserts TRN-018 |
| suite green | `tests/` + `etl/tests/` | `PYTHONPATH=. python -m pytest tests/ etl/tests/ -q` → 4104 passed / 30 skipped |
| TRN-021 NOT created | `etl/migrations/layer0/` | `grep -rc "TRN-021" etl/` → 0 |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (data-pipeline campaign entry)
4. This handoff + the campaign kickoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

**PR state:** not yet opened (PR-gated rule). On Andy's go: decide bundle-vs-split (§5), open ready + auto-merge (merge commit). After merge: `layer0-apply` `0035`; close #340; comment with the commit refs.
