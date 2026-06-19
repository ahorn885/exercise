# #698 Track 2 — Part B §3a per-row audit (RATIFIED + CORRECTED) — Closing Handoff

**Session:** Design-only. "Lets keep working" on Track 2. Produced the owed Part B **§3a** per-row audit, Andy ratified four calls, **then a Rule #9 reconciliation caught a methodology error and corrected §3a.** Net outcome: **the Technical/Skill cull was already executed by migration 0009/#644; Part B reduces to a hygiene-only migration (12 edits).** No `etl/` change yet — B1 is the next slice, built against the corrected §3a.
**Date:** 2026-06-19
**Predecessor handoff:** `V5_Design_CardioDrillsPool_TechnicalSkillCull_Track2_698_2026_06_19_Closing_Handoff_v1.md` (Track 2 design + §6a close)
**Branch/PRs:** `claude/kind-ptolemy-lv9b10`. PR #741 MERGED (proposed §3a, on the stale snapshot). Corrected §3a + bookkeeping in the follow-on PR.

---

## 1. What happened (in order)

1. Rule #9 on Track 2 design anchors — clean (design exists, §6a present, G1–G8=8, `maxItems:1`, §3a owed, no `cardio_drills` code).
2. Produced §3a by parsing `etl/output/layer0_etl_v1.8.0.sql` (77 active target rows) → committed PROPOSED §3a (PR #741, merged).
3. Andy ratified four calls (AskUserQuestion): **cull both** EX094+EX123 · **gear-toggle hygiene** ("add to the gear toggles section") · **Hiking+Trail+Ultra HEAVY** · **Interval/Tempo include now**.
4. Updated §3a → RATIFIED + corrected the hygiene model (the conflation tokens are `sport_specific_gear_toggles`, not skill-cap/equipment_items).
5. **While prepping B1, read migration 0009 and caught the error:** §3a had audited the *raw snapshot*, not *snapshot + migrations*. Reproduced the gate's composite (`v1.8.0` + `0006–0016`) in a local Postgres → **true active set = 68, not 77.** Corrected §3a.

## 2. The methodology error + correction (the load-bearing part)

The authoritative Layer 0 state = **baseline snapshot + the numbered migrations applied on top** — exactly what the CI `layer0-gate` validates (`ls etl/output/layer0_etl_v*.sql | sort -V | tail -1`, then every `etl/migrations/layer0/[0-9]*.sql` in order). §3a's first cut audited the raw snapshot and so was stale by **−10 / +1**:

- **−10 already culled:** migration **0009 (`0009_cull_nontrainable_technical_skill.sql`, #644, Andy-ratified 2026-06-16)** already retired EX094, EX121, EX122, EX123, EX148, EX150, EX152, EX153, EX154, EX155 — *the same non-trainable Technical/Skill cull Part B set out to do.* Both rows I had Andy re-ratify (EX094, EX123) and the 8 I'd wrongly marked KEEP were already retired. Active T/S = **55**, not 65.
- **+1 missing:** EX288 *Treadwall Intervals* (I/T, added by 0016 at `0B-v1.6.14`) — active, absent from the raw snapshot's active set. Active I/T = **9**, not 8.

**Net: Part B's cull is already complete (0009/#644). What remains is HYGIENE ONLY.** Reproduced via a throwaway Postgres (postgres user; the gate's load+apply recipe); all migrations applied clean.

## 3. Corrected §3a (authoritative, 68 active rows)

| Disposition | Count |
|---|---|
| KEEP + discipline-tag | 56 |
| HYGIENE — gear-toggle token strip | 11 |
| HYGIENE — SEM restore | 1 |
| CULL | 0 (done by 0009/#644) |

- **H1** strip `Climbing — roped` (gear toggle #268) from `equipment_required`: EX112, EX113, EX114, EX130, EX131.
- **H2** strip `Mountaineering` (#272): EX149 (EX148/EX150 were 0009 culls).
- **H3** strip `Touring/AT ski setup` (#265 — already exists): EX168, EX169, EX170, EX171, EX172.
- **H4** restore EX194 Laser-Run's Modern Pentathlon SEM row (priority Critical) — it's the **only** target row with zero active SEM → currently un-poolable.
- *(Aside, out of scope: EX115 [Balance] + EX195 [Strength] also carry `Climbing — roped` but aren't drill-pool types.)*

## 4. Ratified for Part A (still valid after the correction)

- **Discipline→weight-tier:** HEAVY = paddle/swim/ski/climb/snow/MTB/nav/row **+ Hiking + Trail Running + Ultramarathon** (pole/pack/pacing drills are efficiency skills, not run-economy form); LIGHT = road run/cycle (Marathon, Triathlon, RBR Duathlon, Bikepacking, Road/Gravel Cycling).
- **Interval/Tempo:** included in the v1 `cardio_drills` pool (9 rows incl. EX288); cue carries the dose.
- (The "cull both" ratification is satisfied by the existing 0009 — no new cull action.)

## 5. NEXT — B1 hygiene migration, then Part A

**B1 — `etl/migrations/layer0/0017_*.sql`** (Bookkeeping + `etl/` only): apply §3a's 12 hygiene edits — strip the 11 mis-filed gear-toggle tokens from `equipment_required` + restore EX194's Modern Pentathlon SEM row. **Serving-relevant 0B edit**: supersede + re-insert at a bumped `0B-v…` version (the `0016_rename_exercises_and_equipment_edits.sql` pattern), atomic verify DO-block, idempotent. Validate via the local-Postgres gate recipe + CI `layer0-gate`; apply via the gated `layer0-apply` Action (Andy one-tap). Then **Part A:** A1 `payload.py` `CardioDrill` + `maxItems:1` → A2 `per_phase.py` pool+prompt + `hashing.py` `LAYER4_PROMPT_REVISION "10"→"11"` (prompt ratified first, Trigger #1) → A3 `validator.py` + render.

## 6. Verification

- §3a counts internally consistent: `grep -c '| KEEP+tag |'` → 56; `grep -c '| HYGIENE (token) |'` → 11; `grep -c '| HYGIENE (SEM) |'` → 1 (= 68). Table has 68 EX-rows.
- Authoritative active set computed from `v1.8.0` + migrations `0006–0016` in a local Postgres (gate recipe), not from narrative. Pre-migration 65/8/4 → post 55/9/4.
- 0009 culls confirmed inactive post-migration; EX288 confirmed active I/T; EX194 confirmed only zero-SEM target row; conflation tokens confirmed still present (hygiene genuinely owed).
- No `etl/` migration written yet (B1 is next): `ls etl/migrations/layer0/0017_*.sql` → nothing.

### 6.3 — Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` → 2. `CURRENT_STATE.md` (top = this §3a session) → 3. `CARRY_FORWARD.md` → 4. this handoff → 5. `./scripts/verify-handoff.sh` → then the ratified+corrected `designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v1.md` **§3a** and write B1.
- **Carry-forward lesson:** when auditing Layer 0, the truth is **snapshot + `etl/migrations/layer0/` applied**, never the raw `layer0_etl_v*.sql` snapshot alone. Reproduce with the gate recipe in a local Postgres (`runuser -u postgres`).

## 7. §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| §3a corrected | `designs/Layer4_CardioDrillsPool_TechnicalSkillCull_Design_v1.md` | `grep -c "RATIFIED + CORRECTED"` ≥1; tally row `**CULL** ... 0 ... already executed by 0009/#644` |
| §3a counts | same | `grep -c "\| KEEP+tag \|"` → 56; `grep -c "\| HYGIENE (token) \|"` → 11; `grep -c "\| HYGIENE (SEM) \|"` → 1 |
| Cull already done | same / repo | §3a/§3 note "0009 (#644) already retired"; `etl/migrations/layer0/0009_cull_nontrainable_technical_skill.sql` exists |
| B1 not yet written | repo | `ls etl/migrations/layer0/0017_*.sql 2>/dev/null` → nothing; `grep -rn cardio_drills layer4/` → nothing |
| CURRENT_STATE pointer | `CURRENT_STATE.md` | top "Last shipped" = `#698 TRACK 2 — PART B §3a … RATIFIED + CORRECTED`; names this handoff |

---

**End of handoff.**
