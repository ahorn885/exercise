# #698 Track 2 — Part B §3a per-row audit (PROPOSED, awaiting ratification) — Closing Handoff

**Session:** Design-only. "Lets keep working" on Track 2. Rule #9-verified the Track 2 design was intact, then produced the **one owed deliverable** — the Part B **§3a per-row audit table** — and appended it to the ratified design as a **PROPOSED** section. No `etl/` change: the cull/hygiene migration (B1) is gated on Andy's ratification of §3a (Trigger #2 — no cull without review). Stopped before B1.
**Date:** 2026-06-19
**Predecessor handoff:** `V5_Design_CardioDrillsPool_TechnicalSkillCull_Track2_698_2026_06_19_Closing_Handoff_v1.md` (Track 2 design + §6a close)
**Branch/PR:** branch `claude/kind-ptolemy-lv9b10` — design §3a + bookkeeping. (Docs-only; auto-merge once required checks pass.)

---

## 1. Rule #9 — session-start verification (Track 2)

Verified the Track 2 design anchors against on-disk before working — all clean:
- `designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v1.md` exists; §6a present; `grep -c "^- \*\*G[1-8]"` → 8; `maxItems: 1` in §4; §3a was the single owed item ("appended to this design as §3a"); `grep -rn cardio_drills layer4/` → nothing (no code yet); CURRENT_STATE top pointer named Track 2.
- (The repo's `verify-handoff.sh` keys on the newest-modified handoff, which is the parallel #681 Slice-2 app track — not Track 2. Track 2's anchors were spot-checked directly per Rule #9.)

No drift in the design itself. One **data drift** surfaced by the audit (see §3 below).

## 2. What shipped — §3a audit (design amendment only)

Appended **§3a "Per-row audit & dispositions — PROPOSED"** to the Track 2 design. Method: read-only parse of `etl/output/layer0_etl_v1.8.0.sql` (active rows, `superseded_at IS NULL`), cross-referenced against active `sport_exercise_map`, the 127-name `equipment_items` canon, and `skill_capability_toggles` (#336).

**Disposition tally — 77 active target rows (65 Technical/Skill + 8 Interval/Tempo + 4 Aerobic/Endurance):**

| Disposition | Count | Rows |
|---|---|---|
| KEEP + discipline-tag | 61 | all not listed below |
| HYGIENE-FIX | 14 | H1 EX112/113/114/130/131 · H2 EX148/149/150 · H3 EX168/169/170/171/172 · H4 EX194 |
| CULL? (ratify) | 2 | EX094, EX123 |

The full per-row table (`exercise_id | name | type | discipline | terrain | disposition`) is in §3a.

## 3. Findings worth carrying

- **Reframe confirmed.** 61 of 65 Technical/Skill rows are clean KEEP; the cull set is **2** (both gear-handling, not movement sessions). Asset inventory + narrow hygiene cull, exactly as §2 framed. **No exact-duplicate rows** — the near-pairs (EX118/EX183, EX175/EX197, EX070/EX186, EX051/EX215, EX052/EX213/EX214) are each explicitly differentiated in their `coaching_cues`.
- **Drift caught (Rule #9 / data).** §3 v1 estimated the conflation split as `Climbing — roped ×8 / Touring-AT ski ×4 / Mountaineering ×1`. On-disk audited reality: **`Climbing — roped ×5 / Mountaineering ×3 / Touring-AT ski ×5`** (total holds at 13). Fixed §3's parenthetical; §3a is authoritative.
- **`Touring/AT ski setup` is NOT a skill-cap conflation.** No ski/skimo toggle exists in `skill_capability_toggles` — it's genuine gear **missing from the `equipment_items` canon** (H3). Different fix from H1/H2 (which move a capability token to its #336 gate).
- **EX194 Laser-Run lost its discipline membership (real bug).** Active exercise, but **all** its `sport_exercise_map` rows are superseded (last active `0B-v19.0-r1`, superseded 2026-05-25) → no active discipline tag → it cannot be surfaced/weighted in the drill pool. The `Modern Pentathlon` sport is still active. H4 = restore the SEM row (priority `Critical`).

## 4. Still-OPEN — what Andy ratifies before B1 (§3a tail)

1. **CULL list** — EX123 (firm) + EX094 (contestable; keep-arg = AR transition value + parity with EX170/176 kept transition drills; cull-arg = static gear handling, no locomotion). Ratify both, or a subset.
2. **Hygiene H1–H4** — climbing-roped/mountaineering → skill-cap; ski-vocab option; EX194 SEM restore.
3. **Ski-vocab call (H3):** add `Touring/AT ski setup` to the `equipment_items` canon (no-padding call — it's real, uncatalogued gear) **or** leave as a known wart. Recommend **add**.
4. **Discipline→weight-tier map** — HEAVY/LIGHT proposed in §3a; **Hiking and Trail/Ultra flagged contestable** (recommend HEAVY — pole/pack/pacing drills are efficiency skills, not run-economy form).
5. **Interval/Tempo deferral** — recommend the 8 I/T rows stay catalog-KEEP but **out** of the v1 `cardio_drills` pool (structured-interval prescription = #337). Include A/E ×4 + T/S survivors now.

## 5. NEXT (after ratification) — B1, then Part A

**B1 — cull + hygiene migration** (Bookkeeping + `etl/` only, ratified §3a is the spec): one layer0 migration that (a) supersedes the ratified culls + repoints inbound `physical_proxies` (note EX176 lists EX094 as a proxy — drop/repoint if EX094 culled); (b) applies H1–H4 (remove mis-filed tokens; add `Touring/AT ski setup` to `equipment_items` if ratified; restore EX194's SEM row); (c) validates against the CI layer0 gate; apply via the gated `layer0-apply` Action.
**Then Part A:** A1 `payload.py` `CardioDrill` + `maxItems:1` → A2 `per_phase.py` pool+prompt + `hashing.py` `LAYER4_PROMPT_REVISION "10"→"11"` (prompt ratified first, Trigger #1) → A3 `validator.py` membership rule + `view.html` render.

## 6. Verification

- No code/tests this session (design amendment + bookkeeping). §3a row counts internally consistent: `grep -c '| KEEP+tag |'` → 61, HYGIENE → 14, CULL? → 2 (= 77). H1–H4 anchors present. Parser cross-checked the catalog: 65 T/S + 8 I/T + 4 A/E active = 77 (matches design §1).
- The audit's source-of-truth facts (active-row counts, conflation token usage, EX194 superseded-SEM, equipment_items canon membership) were computed from `etl/output/layer0_etl_v1.8.0.sql`, not from narrative.

### 6.3 — Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — top entry = this §3a session
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep
6. Then: the ratified design `designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v1.md` **§3a** — and **whatever Andy ratified in chat** — before writing the B1 migration.

## 7. §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| §3a section present | `designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v1.md` | `grep -c "## 3a. Per-row audit"` → 1 |
| Disposition counts | same | `grep -c "\| KEEP+tag \|"` → 61; `grep -cE "\| HYGIENE \(H[1-4]\) \|"` → 14; `grep -c "\| \*\*CULL?\*\* \|"` → 2 |
| Hygiene buckets | same | `grep -cE "^- \*\*H[1-4] —"` → 4 |
| §3 drift corrected | same | §3 bucket 2 reads `×5 … ×3 … ×5` (not `×8/×4/×1`) |
| Still PROPOSED (no migration) | repo | `ls etl/migrations/layer0/*cardio*drill* 2>/dev/null` → nothing; `grep -rn cardio_drills layer4/` → nothing |
| CURRENT_STATE pointer | `CURRENT_STATE.md` | top "Last shipped" = `#698 TRACK 2 — PART B §3a … PRODUCED`; names this handoff |

---

**End of handoff.**
