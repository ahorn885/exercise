# V5 Spec — Provider Inbound Mapping Matrix (#681 Wave 2) — Batches 1–3 — Closing Handoff v1

**Date:** 2026-06-17 → 2026-06-18
**Type:** Spec/reference session (no code). PR [#723](https://github.com/ahorn885/exercise/pull/723) — **open, CI green, ready for review (not auto-merge — reference doc; Andy merges).** §1 + §6 decisions **RATIFIED by Andy 2026-06-17/18**.
**Branch:** `claude/optimistic-pasteur-1g10vg` (harness-pinned; kept — scope matches).

---

## §1 — Session-start verification (Rule #9)

`CURRENT_STATE.md` "Last shipped" (#679 complete) named the **provider matrix Wave 2** as the next data-mapping move. Picked that up. The parent `specs/Provider_Data_Translation_Layer_Spec_v1.md` (RATIFIED v1) owns the canonical model this matrix populates — confirmed on-disk: §2.3 SI metric registry, §2.4 5-zone HR, §4.2 `provider_value_map` schema, §6 seed matrix (Garmin + Polar/COROS). Discipline canon confirmed at `etl/layer0/discipline_canon.py` (`CANONICAL_NAMES` D-001…D-032 + `DISCIPLINE_ENDURANCE_PROFILE`, assert-guarded; highest id = D-032). No drift.

## §2 — What this session produced

Authored the **full-roster inbound mapping matrix** — the Wave-2 deliverable from the parent spec's §6.2 roadmap — as a new reference doc, in three depth-first batches. Each provider was researched from **official developer docs** (parallel research agents, source URLs cited per provider) and mapped to the **real** layer0 discipline canon + §2.3 registry, in the exact column vocabulary of the future `provider_value_map` table. Two gating decisions were ratified with Andy mid-session and folded in.

**7 providers = every realistically-ingestable platform.** The two un-authored providers (MyFitnessPal, Apple/Samsung/Google Health) are *blocked*, not skipped (§6) — so inbound authoring is effectively complete.

## §3 — Files (substantive vs bookkeeping)

**Substantive (1 — far under the 5-file ceiling):**
- `aidstation-sources/specs/Provider_Inbound_Matrix_v1.md` — NEW. The matrix. §0 how-to · §1 discipline-target decision (RATIFIED C) · §2 Strava · §3 WHOOP · §4 Oura · §5 Batch-1 coverage · §6 candidate new entries (Rowing RATIFIED → D-033) · §7 batch plan · §8 instrumentation · §9 gut check · §10 Batch 2 (Wahoo/RWGPS) · §11 Batch 3 (TrainingPeaks/Zwift).

**Bookkeeping (ceiling-exempt):** `CURRENT_STATE.md` (new top pointer), `CARRY_FORWARD.md` (#681 Wave-2 entry + the Rowing-mint follow-up), this handoff, PR #723 (title/body updated to full scope), #681 comment.

## §4 — Code / tests

None — reference doc only. PR #723: docs-only (1 substantive doc + 2 bookkeeping md), no DDL, no prompt revision, no vocab/canon change *in this PR*. CI green (`Python unit suite (stubbed)`, `JS harness (jsdom)`, `Layer 0 integrity gate`, Vercel preview; Real-LLM smoke skipped).

## §5 — Manual verification owed (Andy)

- **Review + merge PR #723.** Decisions are ratified and folded in; nothing else gates it. (Auto-merge intentionally OFF — reference doc.)
- Carried, unchanged: post-#572 live **T3 refresh** re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify on a real Garmin log (Andy-action — Neon egress blocked from the container).

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order — both are CODE tasks, Andy-gated):**

1. **Mint Rowing D-033 (ratified follow-up — small, self-contained layer0 change).** Mechanically (Rule #11):
   - `etl/layer0/discipline_canon.py` — add `"D-033": "Rowing"` to `CANONICAL_NAMES` **and** `"D-033": "Pure endurance"` to `DISCIPLINE_ENDURANCE_PROFILE` (the module-load `assert set(DISCIPLINE_ENDURANCE_PROFILE) == set(CANONICAL_NAMES)` + `etl/layer0/validation/discipline_canon_check.py` both require both edits).
   - A new layer0 migration `etl/migrations/layer0/00NN_add_rowing_discipline.sql` inserting the `D-033` row into `layer0.disciplines` (+ `discipline_modality_membership`, `primary_movement`, endurance_profile columns) — model on the **D-030/031/032 "Vocabulary V1"** additions + `0006_populate_disciplines_primary_movement`. Read the live `disciplines` DDL from `etl/output/layer0_etl_v1.8.0.sql` for the exact NOT-NULL column set first.
   - Validate against the CI `Layer 0 integrity gate` locally (postgres + snapshot + all migrations + `validate_layer0`), then apply via the **`layer0-apply`** Action (Andy one-tap-approves `production`).
   - Decide the coarse collapse: `rowing` has no `_plan_sport_type` today → either add a `rowing` coarse bucket or keep Rowing fine-only. Then the matrix's provider Rowing rows (§2.2, §10.2, §11.1) flip bucket-3 → D-033.
2. **§4 build wave (Trigger #3 — schema; the high-value move, deserves a fresh session).** Stand up `provider_value_map` / `provider_raw_record` / `provider_outbound_ref` (parent §4) + **backfill the existing scattered dicts** into seed rows: the matrix doc IS the seed data (transcription, not re-derivation), plus #679's aliases, `garmin_fit_parser`'s `GARMIN_TYPE_TO_PLAN_SPORT` / FIT category maps. Carries: the **multi-source precedence rule** (§6 finding — `ftp_w` from 3 providers; `sleep_score`/`resting_hr_bpm`/`body_mass_kg` from 2–3), the **one-FIT-decoder-many-providers** consolidation, and `cardio_log` carrying the fine D-id + a deterministic D-id→coarse collapse table (the option-C build consequence).
3. **Deferred batches (doc §7):** Batch 4 MyFitnessPal — *blocked* on a Layer-2E nutrition model; Batch 5 Apple/Samsung/Google Health — native-client-gated. Don't author until those unblock.
4. **Later waves (parent spec §6.2):** Wave 3a/3b outbound serializers (the matrix flagged the native formats: TP `Structure` push %-of-threshold-only/≤7-day-ahead; Zwift `.zwo` power-target XML file-import-only; Wahoo `plan.json`); Wave 4 bucket-3 UI; Wave 5 API security/developer platform; Wave 6 MCP server.

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| W2-1 | §1 cardio-activity discipline target | **Option C** — fine layer0 D-id + deterministic coarse `_plan_sport_type` collapse (preserve specificity; collapse is the backstop) |
| W2-2 | §6 candidate new discipline "Rowing" | **MINT → D-033** (follow-up layer0 migration; validated by Strava/Wahoo/TP all carrying a rowing type) |
| W2-3 | Authoring scope | Batches 1–3 (7 providers) = all ingestable; stop authoring (Batches 4/5 blocked/SDK) |
| W2-4 | This session's end-state | **Wrap + handoff**; §4 build + Rowing mint go to fresh sessions (Andy's call) |

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Matrix doc | `aidstation-sources/specs/Provider_Inbound_Matrix_v1.md` | Status line "§1 + §6 **RATIFIED by Andy 2026-06-17**"; §1 "Recommendation: (C). → RATIFIED"; §6 "Rowing … RATIFIED … MINT it → provisional `D-033`"; §10 "Batch 2 — RWGPS + Wahoo"; §11 "Batch 3 — TrainingPeaks + Zwift"; §7 batch-plan rows 1/2/3 all "✅" |
| Rolling state | `aidstation-sources/CARRY_FORWARD.md` | "#681 Wave 2 … (Batches 1–3) — DRAFTED, §1/§6 RATIFIED"; the "FOLLOW-UP TASK … mint Rowing D-033" bullet |
| Pointer | `aidstation-sources/CURRENT_STATE.md` | Top entry "SPEC — PROVIDER INBOUND MATRIX (#681 WAVE 2) — BATCHES 1–3" |
| Canon (for the mint) | `etl/layer0/discipline_canon.py` | `CANONICAL_NAMES` highest = D-032 (D-033 is next); `DISCIPLINE_ENDURANCE_PROFILE` assert at module load |
| PR / issue | PR #723, GitHub #681 | #723 title "Batches 1–3", body reflects ratifications + ready-for-review; #681 has the Wave-2 comment (issue kept OPEN) |

## §9 — Files shipped

Substantive: the 1 doc in §3. Bookkeeping: `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, PR #723 (title/body), #681 comment.

## §10 — Carry-forward

- **Provider research source URLs are in the doc per provider** (Strava/Oura/WHOOP §2–4; Wahoo/RWGPS §10; TP/Zwift §11), with confidence/unverified flags (the energy-unit traps — Wahoo `work_accum`=joules-not-kJ, RWGPS/Wahoo `calories` cal-vs-kcal-unstamped — and the TP `TotalTime`=hours gotcha are the empirical-check items for the build, per Rule #14, not guesses).
- **Rowing D-033 mint is the one ratified-but-unbuilt item** (§6 above) — closes the §6 candidate loop.
- The plaintext-token security gap (parent Wave 5) and the no-canonical-HR-zone-anchor open item (parent) are unchanged from the Wave-1 handoff.
