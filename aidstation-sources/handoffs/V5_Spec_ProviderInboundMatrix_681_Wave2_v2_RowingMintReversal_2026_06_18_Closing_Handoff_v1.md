# V5 Spec — Provider Inbound Matrix (#681 Wave 2) — v2: Rowing-mint reversed + discipline-vs-modality framing — Closing Handoff v1

**Date:** 2026-06-18
**Type:** Spec/reference revision (no code). PR [#723](https://github.com/ahorn885/exercise/pull/723) — **MERGED** (squash) this session at Andy's instruction. Reverses one previously-ratified decision (§6 Rowing mint) and adds a framing section (§12).
**Branch:** `claude/optimistic-pasteur-1g10vg` (scope matches; kept).
**Predecessor handoff:** `handoffs/V5_Spec_ProviderInboundMatrix_681_Wave2_2026_06_18_Closing_Handoff_v1.md` (the Batches 1–3 authoring session — superseded by this revision on the §6 point only).

---

## §1 — Session-start verification (Rule #9)

Continued the in-flight matrix PR #723. Andy questioned the §6 Rowing-mint and the proposed `discipline_type` column by repeatedly pointing at "how cycling trainer works." Verified that pointer against on-disk reality before answering (did **not** answer from memory):
- `layer4/session_feasibility.py:96-120` — `_DISCIPLINE_INDOOR_MACHINES` maps disciplines → canonical `layer0.equipment_items` machine tags (`Treadmill`/`Stair climber`/`Ski erg`/`Cycling trainer`/`Rowing ergometer`/`Paddle ergometer`), fired by the `EXACT → PROXY → INDOOR → STRENGTH → REALLOCATE` cascade. A "cycling trainer" is **equipment**, not a discipline.
- `handoffs/V5_Implementation_IndoorBikeFold_692_…` + `etl/migrations/layer0/0012_retire_spin_stationary_bike.sql` — #692 precedent: duplicate indoor bikes were **folded into the `Cycling trainer` machine**, not minted as disciplines.
- `etl/layer0/discipline_canon.py` — `CANONICAL_NAMES` D-001…D-032 (no D-033 anywhere); `DISCIPLINE_ENDURANCE_PROFILE` assert-guarded; `classify_non_discipline` → `CATEGORY_STRENGTH`/`CATEGORY_MOBILITY`. Confirmed no D-033 in `etl/` at all.

## §2 — What changed this session (the decision)

**Andy reversed the §6 Rowing-mint (2026-06-18):** on-water rowing (the traditional sport) is **not frequent in our market and will never appear as a race leg** — the bar for a canon discipline (D-ids drive Layer-2A race composition / race classification). So:
- **No `D-033`.** `discipline_canon.py` untouched; no layer0 migration. Provider Rowing → **bucket-3** (record-don't-drop); erg-rowing as a training substitute already routes through the existing `Rowing ergometer` machine.
- **The proposed `discipline_type` column was rejected** — a training-only modality never receives a D-id, so it cannot leak in as a race leg; the schema already expresses the race/train split by *where the row lives*. No new column.
- **New §12 (discipline vs. training-modality/equipment)** generalizes the call: stair/erg/treadmill/rollerski = machines (`_DISCIPLINE_INDOOR_MACHINES`); walking = coarse `_plan_sport_type`; yoga/HIIT/CrossFit = `CATEGORY_MOBILITY`/`CATEGORY_STRENGTH`. §12.4 records the reusable decision bar; mint a discipline only as a last resort and only if it can be a race leg.
- **Multi-source precedence RATIFIED: freshest-timestamp-wins**, de-dup hub-of-hubs (TrainingPeaks) re-emits by source-of-origin.

The one real build-wave gap §12 surfaced: **carry an inbound indoor/machine flag** (Strava `VirtualRide`/`StairStepper`, RWGPS `is_stationary`, Wahoo `workout_type_location_id`) in `raw_payload` — no vocab change.

## §3 — Files (substantive vs bookkeeping)

**Substantive (1 — under ceiling):**
- `aidstation-sources/specs/Provider_Inbound_Matrix_v2.md` — NEW (v1 → `archive/superseded-specs/` per Rule #12). Edits: status line (§6 reversed); §1 option-C parenthetical; §2.2 Rowing + Crossfit/HIIT + Stair/Elliptical rows; §6 Rowing bullet + "Rowing across providers" bullet + precedence (freshest-timestamp); §10.2 Wahoo ROWING row; §11 TP `rowing` row + §11.3 takeaway (3); **new §12** framing section.

**Bookkeeping (ceiling-exempt):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, PR #723 (body updated + merged), #681 comment.

## §4 — Code / tests

None — reference doc only. The merge pulled in `main`'s concurrent #698 recovery work (PRs #722/#725/#727/#728/#730) onto the branch (one `CURRENT_STATE.md` rolling-pointer conflict, resolved by taking main + re-inserting the matrix entry). Required checks green at merge: `Python unit suite (stubbed)` ✓, `JS harness (jsdom)` ✓, `Layer 0 integrity gate` ✓, Vercel ✓ (Real-LLM smoke skipped).

## §5 — Manual verification owed (Andy)

- **None for this PR** — merged. (No D-033 mint to apply; that task is cancelled.)
- Carried, unchanged: post-#572 live **T3 refresh** re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify on a real Garmin log (Andy-action — Neon egress blocked from the container). Plus the #698 carried live-verifies (Slice 3b + race-week-brief recovery) from the concurrent sessions.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **§4 build wave (Trigger #3 — schema; the high-value move, fresh session).** Stand up `provider_value_map` / `provider_raw_record` / `provider_outbound_ref` (parent §4) + backfill the scattered dicts (this matrix IS the seed data + #679 aliases + `garmin_fit_parser`'s `GARMIN_TYPE_TO_PLAN_SPORT` / FIT maps). Carries: **freshest-timestamp-wins precedence**, one-FIT-decoder-many-providers, `cardio_log` carrying the fine D-id + a deterministic D-id→coarse collapse table, and **recording the inbound indoor/machine flag** (§12). **NB: the Rowing-mint task is CANCELLED — do not author a D-033.**
2. **Deferred batches (doc §7):** Batch 4 MyFitnessPal — blocked on a Layer-2E nutrition model; Batch 5 Apple/Samsung/Google Health — native-client-gated.
3. **Later waves (parent §6.2):** 3a/3b outbound serializers (TP `Structure`, Zwift `.zwo`, Wahoo `plan.json`); Wave 4 bucket-3 UI; Wave 5 API security; Wave 6 MCP.

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| W2-5 | §6 Rowing discipline mint (was W2-2 "MINT → D-033") | **REVERSED — do NOT mint.** Not frequent, never a race leg → bucket-3 + existing `Rowing ergometer` machine |
| W2-6 | A `discipline_type` flag column on `layer0.disciplines` | **Rejected** — training-only modalities never get a D-id; the schema already expresses the split by where the row lives |
| W2-7 | Training modalities/equipment vs disciplines | **§12 framing** — stair/erg/treadmill/rollerski = machines; walking = coarse; yoga/HIIT/CrossFit = mobility/strength categories; mint a discipline only if it can be a race leg |
| W2-8 | Multi-source precedence | **Freshest-timestamp-wins**; de-dup TP hub re-emits by source-of-origin |
| W2-9 | This PR | **MERGE now** (Andy instruction) |

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Matrix doc (current) | `aidstation-sources/specs/Provider_Inbound_Matrix_v2.md` | Status line "§6 Rowing mint — REVERSED by Andy 2026-06-18"; §6 bullet "mint REVERSED … Do NOT mint"; **§12** "Discipline vs. training-modality / equipment"; precedence "freshest-timestamp-wins" |
| Superseded | `aidstation-sources/archive/superseded-specs/Provider_Inbound_Matrix_v1.md` | exists (the mint-ratified version, preserved) |
| Canon (unchanged) | `etl/layer0/discipline_canon.py` | `CANONICAL_NAMES` highest = **D-032** (no D-033); no `etl/` reference to D-033 |
| Rolling state | `aidstation-sources/CURRENT_STATE.md` | "Last shipped" = matrix v2 / Rowing-mint-reversed / MERGED, names this handoff |
| Carry | `aidstation-sources/CARRY_FORWARD.md` | "#681 Wave 2 … §6 mint REVERSED"; "freshest-timestamp-wins"; Rowing-mint follow-up "cancelled" |
| PR / issue | PR #723 (MERGED), GitHub #681 (open) | #723 merged; #681 has the v2/reversal comment; epic kept open |

## §9 — Carry-forward

- **The §6 candidate-loop is closed by rejection, not by a mint** — there is no outstanding Rowing work. If a future market shift makes on-water rowing a race leg, §12.4 step 5 is the path to revisit (Trigger #2).
- §12.4 is the **reusable bar** for the next provider batch's unmapped activities — apply it before flagging any candidate discipline.
- Findings unchanged from the Wave-2 authoring handoff: provider source URLs + unit traps (Wahoo joules, RWGPS/Wahoo kcal-vs-cal, TP `TotalTime`=hours) are empirical-check items for the §4 build (Rule #14, not guesses).
</content>
</invoke>
