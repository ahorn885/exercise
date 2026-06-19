# V5 Implementation — Provider Translation: Slice 3 (Polar/COROS Consolidation + Bespoke-Table Drops, #681 §4) — Closing Handoff v1

**Date:** 2026-06-19
**Type:** Build (v1 app, provider wellness ingest). Branch `claude/v5-slice3-provider-consolidation`. Closes the **#681 §4 storage build wave**. Also this session: closed out the **#698 Track 2** prod-apply (already applied; live-verified + bookkeeping).
**Predecessor handoff:** `handoffs/V5_Implementation_ProviderTranslation_IndoorMachineFlag_Slice2c_681_2026_06_19_Closing_Handoff_v1.md` (its §6 next-move #1 = this slice).

---

## §1 — Session-start verification (Rule #9)

Read order ran (CLAUDE.md → CURRENT_STATE → CARRY_FORWARD → the Slice 2c handoff) + `verify-handoff.sh` — **all ✅, tree clean**. Spot-checked on-disk anchors for both recent threads: Slice 2c (`resolve_indoor_machine` + `INDOOR_MACHINE_MAP`, `_record_provider_raw_cardio` + `SAVEPOINT provider_raw_cardio`, test file) **present**; #698 Track 2 migrations `0017`/`0018` **present** (highest on disk). **No drift.**

**One reconciliation:** the verify script keys off `CURRENT_STATE`'s "Last shipped session," which was **#698 Track 2** with a stale **"prod-apply owed."** Checked the live `layer0-apply` runs — run **27807932933** (2026-06-19 05:45) had **already applied 0017+0018** (`0017: OK — 55→8`; `0018: OK — Interval/Tempo 9→12`). Re-verified read-only (`neon-query`): **`Technical / Skill`=8, `Interval / Tempo`=12**. So the owed action was already done — flipped the stale docs + commented #698 (a redundant `layer0-apply` I'd queued was cancelled).

## §2 — What shipped (Slice 3)

Design `ProviderTranslation_StorageSchema_681_BuildDesign_v1.md` §7 **Slice 3**: consolidate Polar/COROS wellness into canonical core + drop the per-provider bespoke tables. **Live `neon-query` zero-row gate (2026-06-19): all 6 bespoke tables = 0 rows in prod** → clean drop, no data backfill.

The design under-scoped it (it listed only the two ingest files + a migration). The deeper read found the bespoke tables have **live readers** — `layer3a/integration.py` (5 accessors) — so the slice is a **writer + reader repoint**, and Andy ratified expanding scope to a **provider-neutral rename** of `garmin_daily_metrics`.

**Andy scope calls (AskUserQuestion, this session):**
- **U-1** Next move: apply #698 migrations, then Slice 3.
- **U-2** Target/naming: **reuse the canonical table + rename it provider-neutral**.
- **U-3 / U-4** Slicing: **one PR, accept the 5-file ceiling breach** (the rename drags in the whole Garmin read/write surface → ~9 files).
- **U-5** Build: **full consolidation, behavior-preserving** (Garmin daily metrics stay out of Layer-3A for now) + **file a follow-up issue** to wire Garmin into coaching later → **#757**.

## §2a — Engineering deviation (documented, within U-5's intent)

U-2's wording was "writers → canonical (source-tagged) + raw to `provider_raw_record`." The deeper read showed writing Polar/COROS into the Garmin-keyed `daily_wellness_metrics (user_id, date)` row would **collide with / corrupt Garmin's row** on any future multi-provider day (and break the wellness page's one-row-per-day assumption) — risky to the **live** Garmin path for **zero P/C data**. So the realized design routes **Polar/COROS daily wellness into `provider_raw_record`** (the purpose-built multi-provider, provider-tagged, record-don't-drop store) and continuous/sample **HR into `wellness_log`** — and `daily_wellness_metrics` gets a **pure rename, no key/schema surgery** (lowest risk to Andy's working wellness path). Layer-3A reads the P/C signals back from `provider_raw_record`. Net: same outcome (consolidated canonical core, provenance preserved, bespoke dropped), minimal blast radius on the live path.

## §3 — Files (substantive — ceiling breach pre-authorized, U-4)

- **`init_db.py`** — idempotent `DO $$ … ALTER TABLE garmin_daily_metrics RENAME TO daily_wellness_metrics` (+ `ALTER INDEX … RENAME`), guarded by `to_regclass` so a fresh DB builds it directly; CREATE/index/ALTERs renamed; **`DROP TABLE IF EXISTS`** ×6 for the retired wellness tables (`polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, `polar_continuous_hr_samples`, `coros_daily_summary`, `coros_hrv_samples`). `wahoo_plans`/`coros_plans` (plan-push) untouched.
- **`routes/polar_ingest.py`** — `_record_raw` (→ `provider_raw_record`, provider='polar') + `_record_hr_sample` (→ `wellness_log`, source='polar'). `_ingest_sleep`→data_type='sleep', `_ingest_nightly_recharge`→'hrv', `_ingest_cardio_load`→'cardio_load' (normalised snake_case payload + `_raw`); `_ingest_continuous_hr`→`wellness_log`.
- **`routes/coros_ingest.py`** — `_record_raw` (provider='coros') + `_record_hr_sample` (source='coros'). `_ingest_daily_summary`→data_type='daily_summary'; `_ingest_hrv_sample`→`wellness_log` (ts seconds→ms; per-second HRV value dropped — no consumer/home).
- **`layer3a/integration.py`** — the 4 wellness readers (`q_layer3A_recent_sleep`, `q_layer3A_recent_hrv`, `q_layer3A_combined_load` polar cross-ref, `q_layer3A_connected_providers` coverage counts) read back from `provider_raw_record` (provider/data_type filter, JSONB `->>` extraction), preserving source tags + return shapes.
- **`routes/garmin.py`, `routes/wellness.py`, `garmin_fit_parser.py`, `templates/wellness/index.html`, `layer4/context.py`** — table-name + docstring updates for the rename. `_upsert_garmin_daily_metrics` keeps its name (it's the Garmin writer; the table is now neutral).
- **`tests/test_provider_wellness_consolidation.py`** (NEW) — assert the writers emit well-formed SQL against the canonical tables (right columns, `::jsonb`, ON CONFLICT) and **never** a dropped table.

**Bookkeeping (ceiling-exempt):** `DATABASE.md`, `PROVIDERS_SCHEMA.md`, `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, #681/#698 comments, new issue #757.

## §4 — Code / tests / verification

- Full Python suite **2690 passed / 30 skipped** (2683 baseline + 7 new). Changed modules import clean (via the suite; the isolated-import circular quirk is pre-existing — run the full `tests/`).
- **Migration:** public-schema (`_PG_MIGRATIONS`, auto-applies on deploy) — `init_db.py`. NOT layer0. Idempotent (rename guarded; drops are `IF EXISTS`).
- **Behavior-preserving:** Garmin write path + wellness page unchanged (table renamed only). Layer-3A still reads only Polar/COROS/self-report (Garmin daily metrics still excluded → #757). For Andy (no P/C data) all four repointed readers return empty exactly as before.

## §5 — Live verification — OWED (Andy-action; container can't reach Neon)

1. **Confirm the rename + drops applied on the next deploy** (read-only `neon-query`): `daily_wellness_metrics` exists (Andy's Garmin rows intact), and `to_regclass` is NULL for all 6 bespoke tables (`polar_sleep` … `coros_hrv_samples`). The public-schema migrations auto-apply on Vercel deploy.
2. **Smoke the wellness page** (reads `daily_wellness_metrics`) renders Andy's Garmin sleep/HRV/RHR as before.
3. *(low value — no P/C athlete)* a Polar/COROS webhook records into `provider_raw_record` (`/admin/logs`).

- Carried, unchanged: post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (priority order):**
1. **Live-verify §5** on the next deploy (rename applied; bespoke gone; wellness page intact).
2. **#757** — wire Garmin daily metrics into Layer-3A sleep/HRV/RHR (the deliberate coaching-input improvement deferred out of this slice).
3. **#698 Track 2 Part A** — the `cardio_drills` session block (`maxItems:1`, discipline-weighted; Trigger #1 prompt) on the now-live culled catalog.
4. The **outbound wave** — `provider_outbound_ref` + serializers (deferred since Slice 1). `#747` residual hardening (low-pri).
5. **Deferred (matrix §7):** Batch 4 MyFitnessPal (Layer-2E-blocked); Batch 5 Apple/Samsung/Google Health (native-client-gated).

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| U-1 | Session focus | Apply #698 0017/0018 to prod (was already applied — verified), then Slice 3 |
| U-2 | Slice 3 canonical target | Reuse the canonical daily table **+ rename it provider-neutral** (`daily_wellness_metrics`) |
| U-3/U-4 | Slicing | **One PR**, accept the 5-file ceiling breach (~9 files; the rename pulls in the Garmin surface) |
| U-5 | Build | **Full consolidation, behavior-preserving** (Garmin stays out of Layer-3A) + file follow-up **#757** |

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Rename migration | `init_db.py` | `DO $$ … ALTER TABLE garmin_daily_metrics RENAME TO daily_wellness_metrics` guarded by `to_regclass`; `CREATE TABLE IF NOT EXISTS daily_wellness_metrics` |
| Bespoke drops | `init_db.py` | `DROP TABLE IF EXISTS polar_sleep` … `coros_hrv_samples` (×6); `wahoo_plans`/`coros_plans` retained |
| Polar writer | `routes/polar_ingest.py` | `_record_raw` → `INSERT INTO provider_raw_record … ?::jsonb … ON CONFLICT`; `_record_hr_sample` → `INSERT INTO wellness_log … source` ; ingesters use data_type sleep/hrv/cardio_load |
| COROS writer | `routes/coros_ingest.py` | `_record_raw` (provider='coros', data_type='daily_summary'); `_ingest_hrv_sample` → `_record_hr_sample(… ts*1000 …)` |
| Layer-3A reads | `layer3a/integration.py` | sleep/hrv/combined_load/connected_providers read `FROM provider_raw_record WHERE provider = 'polar'/'coros' AND data_type = …`, `raw_payload->>'…'` |
| Rename refs | `routes/garmin.py`, `routes/wellness.py`, `garmin_fit_parser.py`, `templates/wellness/index.html`, `layer4/context.py` | no remaining `garmin_daily_metrics` table refs (only the `_upsert_garmin_daily_metrics` function name) |
| Writer tests | `tests/test_provider_wellness_consolidation.py` | 7 tests; `_no_bespoke_writes` guard |
| Suite | full | 2690 passed / 30 skipped |
| Live state | prod `neon-query` | bespoke tables = 0 rows (gate passed); rename/drops apply on next deploy (§5 owed) |
| Issues | #681 (open, commented), #698 (prod-apply closed), **#757** (new follow-up) | — |

## §9 — Carry-forward

- **#681 §4 storage build wave is closed** (Slice 1 schema → 2 cardio fidelity → 2c indoor flag → **3 consolidation + drops**). Polar/COROS wellness is now canonical (`provider_raw_record` + `wellness_log`); the 6 bespoke tables are dropped. **`daily_wellness_metrics`** is the provider-neutral daily store (Garmin-populated today).
- **Still no downstream coaching consumer wires Garmin daily metrics into Layer-3A** — deliberate, tracked as **#757**. `provider_raw_record` / `cardio_log.discipline_id` consumers still land in later waves.
- **COVERAGE GAP (carried, low-pri):** the new writers have fake-DB unit tests (SQL/params well-formed), but the **live SQL — the rename/drop migration AND the Layer-3A `provider_raw_record` JSONB-extraction reads — is not exercised against a real Postgres in CI** (public-schema, not the `layer0-gate`). Same class as the Slice 2c `''`-timestamp gap (#752). A small public-schema Postgres integration test would close it.
- **Multi-source precedence (matrix-v2 freshest-timestamp-wins) is not yet implemented at the field level** — irrelevant until a 2nd provider has data for the same day; surfaces when #757 / the outbound wave lands.
