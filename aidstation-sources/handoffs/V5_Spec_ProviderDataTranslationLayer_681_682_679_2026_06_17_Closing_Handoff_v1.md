# V5 Spec — Provider Data Translation Layer (#681) + AIDSTATION API (#682) co-design + #679 design — Wave 1 — Closing Handoff v1

**Date:** 2026-06-17
**Type:** Spec/design session (no code). PR [#695](https://github.com/ahorn885/exercise/pull/695), CI green. **D1/D2/D3 RATIFIED by Andy 2026-06-17; auto-merge enabled.** Build of #679 deferred to a fresh session (Andy's call).
**Branch:** `claude/trusting-cori-7adynl` (harness-pinned; kept).

---

## §1 — Session-start verification (Rule #9)

Prior pointer (`CURRENT_STATE.md`) named **#679** (Garmin FIT-name→EX-id resolver) as the recommended data-mapping next, following #335 (CLOSED) + #430 Slice C (MERGED, #676/#677/#678). Confirmed on-disk: `rx_engine.apply_session_outcome` keys off `layer0_exercise_id` (line ~205), `layer0_progression.NAME_TO_EX_ID` has 20 entries, `garmin_fit_parser` carries `_EXERCISE_CATEGORY_MAP`/`_EXERCISE_SUBTYPE_MAP`. No drift.

**One correction to record:** a repo-only Explore sweep concluded issues **#681/#682 "do not exist"** (they aren't referenced in committed docs). That is a **false negative** — backlog lives in GitHub issues, not the repo. Confirmed via the **GitHub MCP** that #679/#681/#682 are all real, open, OWNER-filed (2026-06-16). Lesson for next session: verify issue existence against GitHub, not the filesystem.

## §2 — What this session produced

Picked up #679; recognized it as the first concrete **inbound** slice of the #681⟷#682 co-designed arc and (with Andy, in a planning conversation) scoped the whole arc spec-first. Authored Wave 1: the canonical-model owner (#681), the API contract over it (#682), and the #679 build design. Decisions were taken interactively with Andy (see §7).

## §3 — Files (substantive vs bookkeeping)

**Substantive (3 — under the 5-file ceiling):**
- `aidstation-sources/specs/Provider_Data_Translation_Layer_Spec_v1.md` — NEW. #681 canonical-model owner.
- `aidstation-sources/specs/AIDSTATION_API_Spec_v1.md` — NEW. #682 API contract.
- `aidstation-sources/designs/ProviderTranslation_GarminStrength_679_Design_v1.md` — NEW. #679 first slice.

**Bookkeeping (ceiling-exempt):** `CURRENT_STATE.md` (new top pointer), this handoff, GitHub comments (#681 bidirectional amendment, #682/#679 cross-links), PR #695.

## §4 — Code / tests

None — spec only. PR #695 CI all green (`Python unit suite (stubbed)`, `JS harness (jsdom)`, `Layer 0 integrity gate`, Vercel preview; Real-LLM smoke skipped). Docs-only change, no DDL, no prompt revision.

## §5 — Manual verification owed (Andy)

- **DONE — D1/D2/D3 RATIFIED (Andy, 2026-06-17); PR #695 auto-merge enabled.** The **SI metric registry** (spec §2.3) and the **5-zone HR anchor** (spec §2.4) remain Trigger-#2 ratifications, but they're consumed by *later* waves — **not needed for #679** (strength name→EX-id only).
- Carried from prior sessions: post-#572 live **T3 refresh** re-verify (Rule #14); #430 Slice C live-verify of EX-id self-heal on a real log + downstream plan-gen.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves (D1/D2/D3 ratified):**
1. **Build #679 — THIS IS THE NEXT SESSION'S TASK (Andy).** The dogfood win (Garmin lifts → capacity-derived loads). Turnkey design in `ProviderTranslation_GarminStrength_679_Design` (now RATIFIED). Steps: add `rapidfuzz` to `requirements.txt`; offline alias authoring (frequency-first) over Garmin names × ~250 layer0 qualified names; resolution at `rx_engine.apply_session_outcome` (backfilled EX-id → alias → category-collapse backstop → `None` = bucket-3); explicit bucket-3 record-don't-drop replacing `first_exposure`; tests per design §6. **New Garmin-derived EX-id candidates: author the whole map, then bring Andy ONE consolidated batch to ratify at the end (Andy, not per-entry).** Open build questions carried in design §7 (authoring scope; interim in-code seed vs `provider_value_map` table).
2. **Wave 2** — full inbound matrix (Strava, Whoop, Wahoo, Oura, MyFitnessPal/nutrition, RWGPS, TrainingPeaks, Zwift, Apple/Samsung/Google Health) from provider docs.
3. **Wave 3a/3b** — outbound: calendar serializer; then native training-platform workout serializers (TrainingPeaks/Garmin/Zwift/Wahoo).
4. **Wave 4** — bucket-3 inline UI surfacing (`Bucket3_InlineCompleted_Surfacing_Design`).
5. **Wave 5** — `AIDSTATION_API_Security_and_Developer_Platform_Spec` (two credential planes, encryption, published OpenAPI + application/issuance flow, versioning). **Gate: no public API exposure before this.**
6. **Wave 6** — `AIDSTATION_MCP_Server_Spec`.

## §7 — Decisions pinned (Andy, this session)

| # | Decision | Pick |
|---|---|---|
| D-1 | #681 direction | **Bidirectional** (charter amended on the issue) |
| D-2 | Breadth | Full ~18-provider roster; full matrix from docs (across waves) |
| D-3 | API co-design | Canonical keys defined once (translation spec §2), shared |
| D-4 | Metric vocab | Mint own SI registry; raw value always preserved (Trigger #2) |
| D-5 | HR zones | Standard 5-zone canonical; normalize providers onto it (Trigger #2; none exists today) |
| D-6 | Outbound | Two tiers — calendars lightweight / training platforms native fidelity |
| D-7 | Bucket-3 | Surfaces **inline** in completed (data + API + UI) |
| D-8 | Storage | **Replace + consolidate** per-provider tables (decided WITH the evidence that Polar/COROS ingest is wired → real migration, gated on zero-row check) |
| D-9 | #679 resolution point | `rx_engine.apply_session_outcome` EX-id step |
| D-10 | #679 matching | Preserve subtype specificity; collapse only as backstop; identify-don't-pad new EX-ids — **ratify candidates in one batch at the end of the build** (Andy, 2026-06-17) |
| D-14 | Spec ratification + #679 timing | **D1/D2/D3 RATIFIED (Andy, 2026-06-17); #679 built in a fresh session** |
| D-11 | Sequencing | As many waves as needed; Wave 1 = architecture + #679 |
| D-12 | API security | Designed (not deferred) — provider-secret + consumer-credential planes, published API + issuance flow (Wave 5) |
| D-13 | MCP server | Spec'd (Wave 6) |

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Translation spec | `aidstation-sources/specs/Provider_Data_Translation_Layer_Spec_v1.md` | §2 canonical keys (SI metric registry, 5-zone); §3 two-tier outbound; §4 `provider_value_map`/`provider_raw_record`/`provider_outbound_ref` + replace+consolidate; §6.1 Garmin strength = #679 seed |
| API spec | `aidstation-sources/specs/AIDSTATION_API_Spec_v1.md` | §2 envelope `_source/_match_kind/_confidence/_raw`; §3 outbound push endpoints; §5 security in scope (refs security spec) |
| #679 design | `aidstation-sources/designs/ProviderTranslation_GarminStrength_679_Design_v1.md` | §2 decision table (resolution point = `apply_session_outcome`); §3.1 resolution chain; §6 test plan |
| Pointer | `aidstation-sources/CURRENT_STATE.md` | Top entry "SPEC — PROVIDER DATA TRANSLATION LAYER … WAVE 1"; #620 demoted to predecessor |
| Issues | GitHub #681/#682/#679 | #681 has the bidirectional scope-amendment comment; #682/#679 link PR #695 |

## §9 — Files shipped

Substantive: the 3 docs in §3. Bookkeeping: `CURRENT_STATE.md`, this handoff, PR #695, issue comments.

## §10 — Carry-forward

- Provider OAuth tokens stored **plaintext** in `provider_auth.access_token/refresh_token` — a current security gap; the driver for the Wave-5 provider-secret plane (encryption-at-rest + rotation; coordinates #268/#279).
- No canonical HR-zone model exists today (only `Z1–Z5` labels + regex inference in `fit_workout_generator.py`); Wave-1 mints one (open item: ratify the per-athlete anchor — %HRmax/%HRR/%LTHR/FTP — or keep it a Layer 4 concern with record-raw until then).
- `body_metrics.weight_lbs` is legacy-lb; the canonical store normalizes to kg (migration §8 of the translation spec).
- The repo-vs-GitHub false-negative on issue existence (§1) — verify issues against GitHub.
