# Spec narrative sweep — post-R6 discipline-id prose reconciliation — Closing Handoff

**Session:** Follow-on from the nav-retire / weather-contingency slice §6.2 open pivot ("Spec narrative sweep — per-layer specs still cite pre-R6 discipline ids in prose; Layer2A_Spec §13 fixture list still references the old auto-resolution world"). Andy picked this move at the gate, then chose **all 6 files in one careful pass** over a split (the ~6-file ceiling + the Layer2D collapse-merge mismap risk were surfaced and accepted).
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_Layer4_NavRetire_WeatherContingency_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/v5-layer4-nav-retire-weather-FECA1` (harness-pinned; name describes the predecessor slice, not this one — kept per the session's "never push to a different branch" instruction).
**Status:** Implementation complete on-branch. **Doc-only** — 5 spec files changed (the 6th, `Layer3_3B_Spec.md`, was checked and needed no edit: its lone `D-001` is a stable example path). **No code, no tests, no schema, no deploy owed.** Draft PR opened.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the predecessor (nav-retire / weather) handoff: all checks clean, working tree clean. Spot-checked every §8 anchor on-disk:
- `navigation_required` gone from non-test code (only the explanatory comment at `layer4/validator.py:166`) ✅
- `weather_client.get_expected_conditions` + `ExpectedConditions.summary_line` defined ✅
- `validator.py` — `"weather"` in all 3 `_CONTINGENCY_ANCHORS_PER_FORMAT` tuples ✅
- `layer4/context.py:230` — `conditional_resolution: Literal["athlete_opt_in"] | None` ✅

**State reconciled:** slice #164 (nav-retire / weather) is committed, pushed, and already on `origin/main` (`828fa99`); this branch == `origin/main` at session start (zero diff). Local `main` ref was stale (at #129) — a fetch lag, not real drift. No PR existed for the branch yet.

**Authoritative R6 map** read from `Discipline_ID_Renumber_R6_Design_v1.md` §2 (the single source of truth). Confirmed the post-R6 toggle-gating ids against the **already-renumbered SQL** (`etl/sources/populate_discipline_technique_foci.sql`): Climbing — roped → D-012, Rappelling/abseiling → D-013, Snowshoeing → D-017.

---

## 2. Problem statement

The R6 renumber (#154) mechanically renumbered all `.py` / `.sql` / workbook + the *normative* discipline references, but **did not touch the prose / test-scenario narrative** in several per-layer specs. Git blame confirms: Layer2A §13.1 was created pre-R6 (#115) with `D-001, D-003, D-005, D-006, D-007` Primary, and #164 only fixed the nav line (D-013→D-015) — the rest of the pre-R6 list survived. `Layer2D_Spec.md` was **entirely pre-R6** in its prose (e.g. "D-010 Rock Climbing", "D-018 Swimrun"), including both collapse pairs appearing as separate scenario rows.

Files were **mixed** (some refs already post-R6 from #164), so a blanket find/replace was unsafe — each occurrence was checked against the R6 map and edited with its name in the match string (collision-free).

---

## 3. File-by-file edits

### 3.1 `Layer2D_Spec.md` (the bulk — was entirely pre-R6)
All discipline-id prose + the §13 test scenarios remapped. Both **collapses** handled as data-unions, not just renumbers:
- **Kayak collapse (D-008a flat + D-008b whitewater → D-010 Kayaking):** §13.1's two separate kayak risk rows merged into one `D-010 Kayaking: ELEVATED (… whitewater bracing adds forearm/wrist load …)`; the included-discipline list dropped 14→13 ids; the "5 elevated disciplines" / `× 5` coaching-flag counts dropped to **4**; the substitutes example re-pointed (`D-012 might return D-009 / D-013`).
- **Mountain-running collapse (D-022 uphill + D-023 downhill → D-024 Mountain Running):** the §10 cardiac-load list and the §13.2 knee-elevation list each merged the two MtnRun entries into one D-024.
- Straight renumbers: D-005→D-006 (Road Cycling), D-006→D-008 (MTB), D-007→D-009 (Packrafting), D-010→D-012 (Rock Climbing), D-011→D-013 (Abseiling), D-013→D-015 (Orienteering), D-014→D-016 (Swimming), D-015→D-017 (Snowshoeing), D-016→D-018 (Mountaineering), D-018→D-020 (Swimrun, incl. §13.7 header + body), D-020→D-022 (Alpine Descent), D-024→D-025 (Épée).
- The generic "14 AR disciplines" count in §13.2–13.6 → "13 AR disciplines" (same base set, post-collapse).
- **Decision ids left untouched:** `D-21`/`D-22`/`D-23` (§14 + open-items table) and `2D-5`/`2D-6` are decision/open-item ids, not disciplines.

### 3.2 `Layer2A_Spec.md`
- §1 prose range: "D-001 Trail Running through **D-016** Mountaineering" → "**D-018** Mountaineering"; dropped the hard "15 disciplines" assertion (the kayak collapse changed the count — see §6).
- §7 (`training_gaps_summary`): "D-016 Mountaineering … D-020 Alpine Descent and D-024 Épée Fencing" → "D-018 … D-022 … D-025".
- §10 edge case: "e.g., D-008b for some sub-format sports" → "D-010".
- §13.1: Primary list "D-001, D-003, D-005, D-006, D-007" → "D-001, D-003, **D-006, D-008, D-009**"; the "15 disciplines returned" bullet rewritten to state the kayak-collapse count delta instead of a hard number.
- §13.2 override example: `{'D-006': …}` (the same MTB discipline as §13.1) → `{'D-008': …}` across all 3 mentions.
- **Left as-is:** the post-R6 nav notes at §5.3/§8.2/§13.1 (D-015, from #164) and the `D-17`/`D-05`/`D-08` **decision** ids in §12/§13.4/§14.

### 3.3 `Layer2C_Spec.md`
- §11 [DECISION POINT] hard-code example `{'D-010': 'Climbing — roped', 'D-015': 'Snowshoeing', …}` → `{'D-012': …, 'D-017': …}`.
- §11 resolution prose: the 3 populated gate cases → `Climbing — roped → D-012; Rappelling / abseiling → D-013; Snowshoeing setup → D-017` (verified against the renumbered populate SQL).
- §13 hotel scenario: bike-coverage flag "D-005 and D-006" → "**D-006 and D-008**". (`[D-001, D-003]` left — both stable.)

### 3.4 `Layer2B_Spec.md`
- §10 edge case: "athlete includes D-007 Packrafting" → "**D-009** Packrafting".

### 3.5 `Layer0_ETL_Spec_v7.md`
- §5.2 per-consumer signature mirror: removed the stale `navigation_required: bool | None,` line from `q_layer2a_discipline_classifier_payload` to re-sync with Layer2A §3 (the spec's own "spec-of-spec" rule mandates this when the per-layer spec is revised — #164 dropped the param).
- **Deliberately NOT changed:** the `D-008a`/`D-008b`/`D-005a` references elsewhere in this spec (§ workbook-version changelog, schema-comment examples, JSON payload examples). They document the **source-workbook v2→v10 evolution** — the D-008 split into flat/whitewater really happened in those versions before R6 (workbook v11) collapsed it. Rewriting that changelog would falsify the ETL history. (Out of the named "per-layer specs" scope; flagged in CARRY_FORWARD as an intentional boundary.)

---

## 4. Code / tests

**None touched.** Doc-only change (5 `.md` files). No test run owed — no Python/SQL changed. `git status` shows exactly the 5 spec files.

---

## 5. Manual verification (owed — Andy's hands)

Appended to `CARRY_FORWARD.md`:
1. **Post-R6 AR discipline count.** Two prose spots (Layer2A §1 + §13.1) previously asserted "15 AR disciplines"; the kayak collapse (D-008a/b → D-010) removes one member where both were present (Andy's PGE set carried both pre-R6). I replaced the hard "15" with a collapse-delta description rather than assert an unverified absolute. **Verify the real active AR count** against the deployed `0A-v11.0` bridge during the next data walk (`SELECT … FROM layer0.disciplines WHERE superseded_at IS NULL` + the AR pairing set) and pin the exact number back into Layer2A §13.1 if a concrete count is wanted in the test scenario.

No migration / deploy owed for this slice.

---

## 6. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | **Do the whole sweep in one pass** (all 6 candidate files) | Andy at gate | Ceiling + Layer2D collapse-mismap risk surfaced; accepted. |
| 2 | **Edit per-occurrence with the discipline name in the match string** (no blanket sed) | this agent | Files were mixed pre/post-R6; the R6 design itself flagged the silent-mismap risk (~24 of 29 ids changed meaning). Name-anchored edits are collision-free. |
| 3 | **Collapses are data-unions, not renumbers** | this agent (per R6 §3) | Two kayak rows → one D-010 (forearm load folded in); two MtnRun rows → one D-024. Counts dropped accordingly (14→13 set; 5→4 elevated). |
| 4 | **Drop the hard "15 AR disciplines" assertion** rather than guess the post-collapse number | this agent | Can't verify the absolute count without the deployed bridge; asserting a wrong number reintroduces drift. Stated the collapse delta + parked a §5.0 verify. |
| 5 | **Leave the Layer0 ETL spec's workbook-history D-008a/b refs** | this agent | They document the real v2→v10 workbook lineage; rewriting falsifies the changelog. Only the §5.2 signature mirror (coupled to Layer2A §3 by the spec's own rule) was synced. |
| 6 | **Decision ids (`D-21`, `D-17`, `D-05`, `2D-6`, …) are not disciplines** | this agent | 1–2-digit `D-NN` = decision/open-item ids; only 3-digit `D-0NN` are disciplines. Left all decision ids alone. |

---

## 7. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| All (id, name) pairs across the 5 edited specs match the R6 §2 map (`grep -hoE "D-0[0-9][0-9]…name"`) | ✅ |
| No retired suffix forms (`D-004b\|D-005a\|D-008a\|D-008b`) remain in any per-layer spec or in the Layer0 ETL §5.2 mirror | ✅ |
| `navigation_required` gone from `Layer0_ETL_Spec_v7.md` | ✅ |
| Layer2D §13.1 kayak rows merged to one D-010; elevated count 5→4; set 14→13 | ✅ |
| Layer2D §13.2 / §10 mountain-running merged to one D-024 | ✅ |
| Decision ids `D-21/D-22/D-23` + `D-17/D-05/D-08` + `2D-5/2D-6` untouched | ✅ |
| `git status` → only the 5 intended `.md` files; no code/test/schema | ✅ |
| `Layer3_3B_Spec.md` checked — lone `D-001` is a stable example path, no edit needed | ✅ |

---

## 8. Files shipped this session

**Specs (5):** `aidstation-sources/Layer2A_Spec.md`, `Layer2B_Spec.md`, `Layer2C_Spec.md`, `Layer2D_Spec.md`, `Layer0_ETL_Spec_v7.md`.
**Bookkeeping:** this handoff; `CURRENT_STATE.md` pointer; `CARRY_FORWARD.md` §5.0 entry.

---

## 9. Next session pointers

### 9.1 Architect-recommended next forward move
**Run the owed Neon deploys** (unchanged by this slice; still Andy's hands — no `DATABASE_URL` in the build container): public-schema `python init_db.py` (A1 race_events remap + A2 `aid_stations` drop + Slice-C §G drops + `daily_availability_windows` 720 bump) **plus** `etl/sources/run_owed_layer0_migrations.sql` (PR #156 `primary_movement` HARD Layer-2A prereq). Then the accumulated manual §5.0 walks.

### 9.2 Open pivots
- **Weather contingency follow-on (optional)** — surface the climate normals as a structured `RaceWeekBrief` field (UI + Layer 5 conditions advisor) and/or a closer-in forecast refresh as `days_to_event` shrinks. Gates on a `/plan`-mode design (Trigger #1/#3).
- **Residual spec narrative** — the Layer0 ETL spec still carries workbook-history D-008a/b refs (intentional, see §3.5); if a future call wants the ETL schema-comment/JSON *examples* (lines ~311/923/1314/1325/1390) modernized to v11 ids, that's a small follow-on. Doc-only; no gate.
- **Manual §5.0 real-LLM + data walks** — accumulated in `CARRY_FORWARD.md` (incl. this slice's AR-count verify + the prior weather-contingency live-Open-Meteo walk).

### 9.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules (read first).
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep; reconcile any ❌ first.
6. **Test env (if code work resumes):** deps not pre-installed in fresh web containers — `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

---

## 10. Carry-forward updates

- New Manual §5.0 entry (verify post-R6 AR discipline count against deployed `0A-v11.0`) appended to `CARRY_FORWARD.md`.
- The owed Neon deploys are **unchanged** by this slice — no new deploy debt.
- Per-layer spec prose is now R6-consistent; the Layer0 ETL spec's remaining pre-R6 ids are intentional workbook history (noted in CARRY_FORWARD).

---

**End of handoff.**
