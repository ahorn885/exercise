# V5 Implementation — Provider Translation Layer Cardio Fidelity (#681 §4 Slice 2 = 2a + 2b) — Closing Handoff v1

**Date:** 2026-06-19
**Type:** Build. Two back-to-back PRs shipped this session: **Slice 2a** (cardio resolver + provider crosswalk seed) — **MERGED** PR [#738](https://github.com/ahorn885/exercise/pull/738); **Slice 2b** (live Garmin ingest repoint) — PR [#739](https://github.com/ahorn885/exercise/pull/739), auto-merge enabled, CI green.
**Branches:** `claude/hopeful-newton-yq0bab` (2a, merged) + `claude/hopeful-newton-yq0bab-slice2b` (2b).
**Predecessor handoff:** `handoffs/V5_Design_ProviderTranslation_StorageSchema_681_2026_06_18_Closing_Handoff_v1.md` (Slice 1 built; its §6 NEXT = Slice 2, this wave).

---

## §1 — Session-start verification (Rule #9)

Continued the storage-schema thread ("keep at it", pointing at the Slice-1 closing handoff). Ran the full anchor sweep before any new work — **clean, no drift:**
- `aidstation-sources/scripts/verify-handoff.sh` — all ✅; working tree clean; branch `claude/hopeful-newton-yq0bab`.
- Slice-1 anchors spot-checked on-disk: `provider_value_map_seed.py` holds `STRENGTH_NAME_TO_EX_ID` (147) + `GARMIN_TYPE_TO_PLAN_SPORT` (15) + `provider_value_map_rows()`; the old dict symbols (`NAME_TO_EX_ID`/`GARMIN_STRENGTH_ALIASES`/`LOGGED_NAME_ALIASES`/`GARMIN_TYPE_TO_PLAN_SPORT`) live **only** in the seed (consumers import it); `init_db` creates `provider_value_map` + `provider_raw_record` and materializes the seed via `ON CONFLICT DO UPDATE`.
- Canon unchanged: `discipline_canon.py` highest **D-032**; no `D-033`.
- PR #733 (Slice 1) confirmed MERGED on `main` (commit `30e7aa8`); a later #698 Track 2 design (PR #734) merged after it — so `CURRENT_STATE`'s "Last shipped" was that Track-2 design, with Slice 1 as a predecessor, and **Slice 2 unstarted** (= the "keep at it" target).

## §2 — What changed this session (the decisions)

Slice 2 (matrix-v2 §1 **option C**: store the fine layer0 discipline id for a completed cardio activity, derive coarse `_plan_sport_type` via a deterministic collapse) was **designed + ratified** in the Slice-1 design (§0 Q1–Q5; Q3 = collapse-as-a-dict). It is **Trigger #3 (cross-layer schema)**, already cleared at design level.

**Surfaced one scope fork to Andy (`AskUserQuestion`)** — Slice 2 exceeds the 5-file ceiling, and the live-Garmin repoint needs a Garmin→D-id crosswalk the matrix never authored (it authored Strava/RWGPS/Wahoo/TP). **Andy chose "Full Slice 2 (incl. live Garmin), run as two back-to-back PRs."** So:
- **Slice 2a** = schema + transcription + resolver (infra, no behavior change).
- **Slice 2b** = the live Garmin ingest repoint (the Garmin crosswalk + the writes).
- **Slice 2c** (deferred, flagged) = the §12 indoor-machine flag into `provider_raw_record.raw_payload` — the genuinely-new writer surface; split out to keep both PRs within the ceiling.

## §3 — Files (substantive vs bookkeeping)

**Slice 2a (PR #738, MERGED) — 4 substantive:**
- `init_db.py` — `ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS discipline_id TEXT` (public `_PG_MIGRATIONS`, auto-deploy).
- `provider_value_map_seed.py` — NEW `CARDIO_DISCIPLINE_MAP` (Strava §2.2 / RWGPS §10.1 / Wahoo §10.2 / TP §11.1); `provider_value_map_rows()` extended.
- `provider_cardio_resolve.py` — NEW: `DISCIPLINE_TO_PLAN_SPORT` collapse dict (Q3) + `resolve_cardio_discipline()` (pure, reads the seed; bucket-3 on unmapped).
- `tests/test_provider_cardio_resolve.py` — NEW (+16); plus a surgical edit to `tests/test_provider_strength_resolve.py` (Slice-1 parity test scoped to strength).

**Slice 2b (PR #739) — 5 substantive (incl. tests):**
- `provider_value_map_seed.py` — `garmin` added to `CARDIO_DISCIPLINE_MAP`; Garmin cardio rows are now fine `discipline` rows (were Slice-1 coarse `modality`); `provider_value_map_rows()` drops the old `GARMIN_TYPE_TO_PLAN_SPORT` modality loop.
- `garmin_connect.py` — `normalize_activity` sets `discipline_id` + Rule #15 log.
- `garmin_fit_parser.py` — `_garmin_disc_token` (sub_sport refinement) + `parse_fit_file` sets `discipline_id` + Rule #15 log.
- `routes/garmin.py` — `discipline_id` written at all 3 `cardio_log` INSERT sites.
- tests — `test_provider_cardio_resolve.py` (+3) + `test_provider_strength_resolve.py` parity update.

**Bookkeeping (ceiling-exempt):** `CURRENT_STATE.md`, this handoff, PRs #738/#739, #681 comment.

## §4 — Code / tests

**2a:** additive + transcription, **no behavior change** (nothing writes `discipline_id` yet). Seed materializes **259** rows (162 Slice-1 + 97 cardio: 81 fine-discipline bucket-1, 11 coarse-only, 5 explicit bucket-3 = the §6/§12 Rowing cluster). Transcription guarded by a test asserting every authored discipline value ∈ `discipline_canon.CANONICAL_NAMES`.

**2b:** the live Garmin paths (Connect API `normalize_activity` + FIT `parse_fit_file` — the FIT path is Andy's real ingest, API is closed) now write the fine `discipline_id`. The FIT `sport_key` is **coarse** (sub_sport carries trail/MTB/gravel/open-water), so `_garmin_disc_token` refines it before resolving — a trail run lands as **D-001**, not coarse road-running. The coarse `_plan_sport_type` path (the only LIVE consumer — plan-item matching) is **unchanged** (still `GARMIN_TYPE_TO_PLAN_SPORT`); a test guards that the fine D-id collapses back to the **same** coarse value for every Garmin typeKey. Garmin cardio rows flipped modality→discipline (seed now 263 rows). **Verification:** full suite **2669 passed / 30 skipped**; all 3 INSERT sites column/placeholder-balanced; imports clean. Rule #15: each ingest path prints `(provider, token) → discipline_id / coarse / bucket`.

## §5 — Manual verification owed (Andy)

- **NEW (Slice 2b):** live-verify that a real FIT import writes `cardio_log.discipline_id` — import a trail run + an MTB ride, then read `/admin/logs` for the `[cardio-ingest] garmin-fit …` line (expect `discipline_id=D-001` / `D-008`) and/or a read-only `neon-query` of the new `cardio_log.discipline_id` column. Container can't reach Neon, so this is Andy-action.
- Carried, unchanged: post-#572 live **T3 refresh** re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **Confirm #739 merged** (auto-merge enabled, CI green). If CI flaked, re-kick.
2. **Slice 2c — the §12 indoor-machine flag** (the last Slice-2 piece). Record which machine a completed indoor activity used (Strava `VirtualRide`→`Cycling trainer`, `StairStepper`→`Stair climber`; RWGPS `is_stationary`; Wahoo `workout_type_location_id`; Garmin indoor sub_sports `spin`/`indoor_cycling`) into **`provider_raw_record.raw_payload`** — this table's **first writer** (created empty in Slice 1). No new vocab. Design §6 step 4 + matrix §12.3 gap 1.
3. **Slice 3** — Polar/COROS ingest consolidation into core + `provider_raw_record`; then the **zero-row-guarded** bespoke-table drops (irreversible; gated on a live `neon-query` check first). `provider_outbound_ref` waits for the outbound wave (3a/3b).
4. **Deferred batches (matrix §7):** Batch 4 MyFitnessPal (Layer-2E-blocked); Batch 5 Apple/Samsung/Google Health (native-client-gated).

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| S2-1 | Slice 2 scope this session | **Full Slice 2 incl. live Garmin repoint**, run as two back-to-back PRs (2a then 2b) |

Derived (mine, flagged): the §12 indoor-machine flag → **Slice 2c** (split out for the 5-file ceiling; it's the first `provider_raw_record` writer). The coarse `_plan_sport_type` path is **kept on `GARMIN_TYPE_TO_PLAN_SPORT`** (unchanged live behavior) rather than re-derived from the collapse — surgical, zero plan-matching risk; the new fine `discipline_id` is the added fidelity, guarded consistent with the coarse dict.

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Migration | `init_db.py` | `_PG_MIGRATIONS` tail has `ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS discipline_id TEXT` |
| Seed crosswalk | `provider_value_map_seed.py` | `CARDIO_DISCIPLINE_MAP` has 5 providers incl. `garmin` (discipline rows); `provider_value_map_rows()` yields 263 rows, no garmin coarse-modality loop |
| Cardio resolver | `provider_cardio_resolve.py` | `DISCIPLINE_TO_PLAN_SPORT` (running/cycling/swimming/hiking families) + `resolve_cardio_discipline()` → `CardioResolution`; unmapped → bucket 3 |
| Garmin API repoint | `garmin_connect.py` | `normalize_activity` returns `'discipline_id'` via `resolve_cardio_discipline('garmin', garmin_type)` + Rule #15 print |
| Garmin FIT repoint | `garmin_fit_parser.py` | `_garmin_disc_token(sport, sub_sport)` + `parse_fit_file` sets `result['data']['discipline_id']` + Rule #15 print |
| INSERT sites | `routes/garmin.py` | `discipline_id` in all 3 `INSERT INTO cardio_log` column lists (balanced) |
| Tests | `tests/test_provider_cardio_resolve.py` | option-C resolution + transcription fidelity + Garmin consistency; full suite 2669/30 |
| Rolling state | `aidstation-sources/CURRENT_STATE.md` | "Last shipped" = Slice 2 cardio fidelity / names this handoff |
| PRs / issue | PR #738 (MERGED), #739 (auto-merge); GitHub #681 (open) | #681 wave comment posted; epic kept open |

## §9 — Carry-forward

- **Slice 2c (indoor-machine flag) is the remaining Slice-2 deliverable** — first `provider_raw_record` writer; matrix §12.3 + design §6 step 4. No new vocab.
- **`cardio_log.discipline_id` has no downstream consumer yet** — it's populated by the Garmin paths now; the consumers (Layer-1 fidelity, completed-history surfacing, multi-source precedence) land in later waves. The write is additive and safe.
- **Slice 3's zero-row guard is a live check, not an assumption** — confirm the bespoke Polar/COROS tables hold no athlete rows (read-only `neon-query`) before any drop.
- Matrix-v2 empirical-check items still standing (Rule #14, not guesses): provider unit traps (Wahoo joules, RWGPS/Wahoo kcal-vs-cal, TP `TotalTime`=hours).
