# V5 Implementation — #681 §4 Provider Translation: wellness/sleep/body/zone metric-key crosswalk transcribed — Closing Handoff (2026-06-20)

**Branch:** `claude/provider-integrations-api-kickoff-3poeuw` · **PR:** pending Andy's go (PR-gated) · **Suite:** 2839 passed / 30 skipped.

## 1. What this session did

"go on 681" off the provider-integrations kickoff handoff. **Rule #9 surfaced a major drift before any code:** the kickoff handoff (`...ProviderIntegrations_API_ThreadKickoff_681_682...`, PR #788) frames the **#681 §4 build wave** as the next thing to build, but **the §4 storage spine was already shipped to `origin/main`**:

| Handoff "to build" (§4) | Reality on `origin/main` |
|---|---|
| `provider_value_map` table | ✅ `init_db.py:136` (Slice 1, #733), seeded from `provider_value_map_seed.py` |
| `provider_raw_record` table | ✅ `init_db.py:152` (existed) |
| Backfill scattered dicts | ✅ strength `ex_id` + cardio `discipline`/`modality` (Slices 1, 2a #738) |
| `cardio_log` fine D-id + coarse collapse | ✅ `provider_cardio_resolve.py`, live Garmin repoint (Slice 2b #739) |
| Inbound indoor/machine flag | ✅ into `provider_raw_record` (Slice 2c #751, hotfix #752, live-verified #753) |
| `provider_outbound_ref` table | ❌ **not built** — but it's Wave-3b outbound (spec §4.4), deferred, not part of inbound |

(Local `main` was a stale ref — no merge base with HEAD; `origin/main` has all of it and this branch sits at its tip, `8a29846`. Slice 3 #759 explicitly "closes the storage build wave.")

**Andy's call (AskUserQuestion): transcribe the one genuinely-remaining §4 piece.** `provider_value_map_seed.py` covered only `strength` + `cardio` rows; the matrix's **wellness/sleep/body/zone metric-key mappings** (matrix-v2 §2.3 Strava body · §3 WHOOP · §4 Oura) were never authored into the seed.

**Shipped (1 substantive file + 1 test):**
- `provider_value_map_seed.py` — new `WELLNESS_VALUE_MAP` (**49 rows**: 30 bucket-1 mapped → real §2.3 metric keys / Z1–Z5; 19 bucket-2 proprietary → `no_canonical_match=True`, record-raw) + generator extension (`provider_value_map_rows()` now also yields the wellness rows; `direction='in'`, `match_kind='manual'`, `no_canonical_match = canonical_value is None`). `init_db` materializes them unchanged → `provider_value_map` now **312 seed rows** (strength 147 / cardio 116 / sleep 20 / wellness 17 / body 6 / zone 6).
- `tests/test_provider_wellness_value_map.py` — +10 tests.

**Pure transcription. No schema change** (table + row-generator already existed). **No stop-and-ask trigger fired:** the §2.3 metric keys are already-ratified vocab (not Trigger #2 padding); the table contract is unchanged (not Trigger #3). Rows are **dormant** until a provider is live-wired (workstream B) — nothing reads `metric_key`/`zone` rows yet.

## 2. The three matrix-flagged build decisions (resolved per the matrix's own recommendation; encoded + tested)

1. **WHOOP `sleep_total_min`** — DERIVED as asleep = Σstages (`deep+rem+light`), matching Polar/COROS. `total_in_bed_time_milli` is kept **raw (bucket-2)**, NOT mapped to `sleep_total_min`. (No WHOOP row maps to `sleep_total_min`.)
2. **`sleep_score`** — ← Oura `daily_sleep.score` (the genuine device composite). WHOOP `sleep_performance_percentage` is a proprietary % → **bucket-2, NOT** `sleep_score`.
3. **WHOOP `zone_one..five_milli` → Z1..Z5** — a high-confidence inference (WHOOP's published 5-zone %maxHR framework, not a verbatim API statement) → **confidence 0.9** (every other row is 1.0). `zone_zero_milli` (sub-Z1) → no canonical zone (bucket-2).

## 3. Registry gaps surfaced (matrix §6 — flagged, NOT padded)

- **`steps`** is consumed as a canonical target (parent §6.3, COROS) but is **missing from the §2.3 registry table**. Mapped here (Oura `daily_activity.steps` → `steps`); the §2.3 table-add is owed (doc edit, parent spec).
- **Daily energy** (WHOOP `kilojoule`, Oura `daily_activity.total_calories`) has **no §2.3 energy key** → recorded **bucket-2 candidate**, not minted (Trigger #2).
- **Oura `vo2_max`** is one undifferentiated value → fills `vo2max_running` only; `vo2max_cycling` stays unmapped from Oura (no row maps to `vo2max_cycling`).
- **Strava HR/power zones** are positional `{min,max}` arrays with no labels → normalized by index in the (future) ingest, **not** value-map rows (so no Strava `zone` rows).

## 4. Next moves (Andy's call — the §4 build wave is done)

- **(B) Live-provider OAuth/webhook wiring** — Strava + Whoop first (highest-value; mapping authored; stubs + the upload path exist). Token-exchange + connect flow (mirror `coros.py`/`polar.py`) + ingest (mirror `coros_ingest.py`/`polar_ingest.py`, writing canonical via the seed + raw via `provider_raw_record`). **Code can be made ready in the container; the OAuth app registration is the only Andy-gated (external dev-portal) step.** This is also what lights up the dormant wellness rows + forces the freshest-timestamp-wins precedence into real code. Touches #251.
- **(C) #682 AIDSTATION API scoping** — Trigger #5 (architectural design pass; ratify surface + auth model first). Peer epic to #681.
- **Deferred:** `provider_outbound_ref` table + outbound serializers (Wave 3b).

## 5. Owed / carried (unchanged by this session)

All prior live-verify items still owed (Andy-action; container can't reach Neon): slice-1/2 activity-upload; WHOOP CSV wellness; #757 `connected_providers` Garmin coverage; #337 measured-physiology; #698 C1/C2 + Part-A item (b); post-#572 T3 refresh; #430 Slice C / #679 EX-id self-heal; `0019` plan-75 regen + `layer0-redump`; #732 parked. Plan-75 follow-ups #778/#779/#780 open (#780 scheduled for a new session).

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last shipped (this session) + the §4-done correction.
3. `CARRY_FORWARD.md` — *"Provider integrations & API — ACTIVE THREAD"* — (A) now marked ✅ SHIPPED; sequencing → (B)/(C).
4. This handoff.
5. `specs/Provider_Inbound_Matrix_v2.md` §2.3/§3/§4 (what was transcribed) + `provider_value_map_seed.py` (`WELLNESS_VALUE_MAP`).
6. `./scripts/verify-handoff.sh` — anchor sweep.

Then pick up **(B) Strava/Whoop live wiring** or **(C) #682 API scoping** (Andy's call).

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Wellness seed map | `provider_value_map_seed.py` | `WELLNESS_VALUE_MAP: list[...]` = 49 entries; 30 with non-None `canonical_value`, 19 None |
| Generator yields wellness | `provider_value_map_seed.py` | `provider_value_map_rows()` 3rd loop: `for provider, data_type, source_value, kind, value, conf, notes in WELLNESS_VALUE_MAP` → `direction='in'`, `no_canonical_match = value is None` |
| Seed row totals | `provider_value_map_seed.py` | `list(provider_value_map_rows())` → 312 rows; by data_type strength 147 / cardio 116 / sleep 20 / wellness 17 / body 6 / zone 6 |
| Decision 1 (sleep_total) | `provider_value_map_seed.py` | `total_in_bed_time_milli` → `(…, None, …)` bucket-2; no row maps `sleep_total_min` for whoop; stages map deep/rem/light |
| Decision 2 (sleep_score) | `provider_value_map_seed.py` | `oura … 'daily_sleep.score' … 'sleep_score'`; `whoop … 'sleep_performance_percentage' … None` |
| Decision 3 (zone inference) | `provider_value_map_seed.py` | `zone_one_milli`..`zone_five_milli` → `'Z1'..'Z5'`, `conf=0.9`; `zone_zero_milli` → None |
| Tests | `tests/test_provider_wellness_value_map.py` | `TestWellnessRowShape` / `TestFlaggedBuildDecisions` / `TestTranscriptionFidelity`; `METRIC_KEY_REGISTRY` incl. `steps` |
| Table unchanged | `init_db.py` | `CREATE TABLE IF NOT EXISTS provider_value_map` (no DDL change this session); `provider_value_map_rows()` materialized at line ~2823 |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 2839 passed / 30 skipped |
| §4 storage already shipped | `origin/main` | Slices 1/2a/2b/2c/3 = PRs #733/#738/#739/#751/#752/#753/#759; `provider_value_map`/`provider_raw_record` in `init_db.py` |
| Issue | #681 | comment: wellness rows transcribed; §4 storage spine already shipped; epic stays open for (B)/(C) |
