# CLAUDE.md — AIDSTATION

This file is loaded at the start of every Claude Code session. It encodes project context, current state, working rules, and the decisions that require Andy's input before you proceed.

---

## What this project is

AIDSTATION is a commercial direct-to-athlete SaaS application providing AI-driven coaching for endurance and multi-sport athletes. The market focus is on disciplines underserved by existing training software: ultramarathons, skimo, modern pentathlon, Ironman triathlon, swimrun, marathon paddle sports, multi-sport, and adventure racing.

**Andy** is the product architect and sole decision-maker. He is also the test athlete (training for Pocket Gopher Extreme 2026, July 17–19, MN; 48–56 hour expedition AR; 15-week plan started 2026-04-01).

## Coaching voice

Direct, focused, evidence-grounded. No platitudes. No cheerleading. No hype. Tone matches a real endurance coach talking to a serious athlete. This applies to all user-facing copy you draft (prompt templates, UI text, error messages, marketing copy).

## Core differentiators (treat as launch commitments)

1. Plan iteration as situations change — only invalidated layers re-run (partial-update model)
2. Performance-driven auto-updates from incoming athlete data
3. Travel and on-the-go flexibility — plans adapt to athlete location and equipment
4. Multi-sport flexibility — first-class, not bolted-on
5. Team-based training — coordinated plans for teams training toward a shared race
6. Science-backed decisions — cited research, not practitioner heuristics
7. Real-life accommodation — injuries, moves, equipment changes, life disruptions as first-class inputs
8. Crowd-sourced data (eventual) — performance norms, injury patterns, gym equipment profiles

---

## Architecture

Spec-first, multi-layer LLM pipeline. Storage: PostgreSQL with JSONB. Versioning via row invalidation (not overwrite), keyed by user, layer, version. The partial-update model — surgical re-runs of only invalidated layers — is a core product differentiator and shapes every schema decision.

**Layer pipeline:**

| Layer | Purpose | Status |
|---|---|---|
| **0** | Platform-level reference data (LLM-generated, human-reviewed, locked). 0A sport rule sets, 0B exercise library. | DEPLOYED |
| **1** | Athlete profile (form inputs + performance stats). Sourced from Onboarding spec + integration data. | In progress (D-51 field inventory pending) |
| **2** | Race + sport classification. 5 parallel sub-prompts: 2A discipline mix, 2B terrain, 2C equipment/modality, 2D injury risk, 2E nutrition baseline. | SPECS DONE |
| **3** | Athlete evaluation. 4 nodes: 3A athlete state, 3B viability + periodization, 3C cross-node conflict, 3D HITL gate. | 3A SPEC DONE; 3B NEXT |
| **3.5** | Hard HITL resolution gate before plan generation. | Designed; not yet implemented |
| **4** | Plan generation + periodization validator (capped correction loop). | SPEC v1 DONE (§§1–13 + §3.5/§4.4/§10.4/§13.4 D-63-sport-unavailable amendments 2026-05-16; §14 retro deferred to fresh-eyes session); PROMPT BODIES 3/5 (seam-reviewer + per-phase synth + single-session synth) |
| **5** | Parallel supplemental outputs: nutrition, supplements, 7-day clothing/conditions advisor. | Not yet specced |

Architecture overview lives in `Control_Spec` (resolve to highest `_vN.md`).

---

## Current state (as of 2026-05-16)

Last shipped session: **PR18 — locale-CRUD bundle (PR11 follow-on; items A address-display + B 🔴 refresh-broken-on-rename fix + C duplicate-mapbox_id detection + D delete with privacy split rule + outdoor_park reclassification + `home_gym`/`other_residence` label tweaks)** — see `handoffs/V5_Implementation_PR18_Locale_CRUD_Bundle_Closing_Handoff_v1.md`. Ships the four bundle items captured during the PR11 verification walk plus the outdoor_park reclassification (residence-vs-public privacy boundary) + the `Home (primary residence)` / `Other residence (in-laws / friend / AirBnB)` label tweaks. 4 substantive code files + 4 bookkeeping. **`mapbox_client.py`** gains `retrieve(mapbox_id, session_token=None)` + `_request_retrieve` helper hitting `GET /search/searchbox/v1/retrieve/{mapbox_id}` (one-shot UUID session token generated per refresh — Mapbox bills as a fresh session; same `MapboxNoResults` / `MapboxAPIError` / `MapboxTokenMissing` hierarchy as the forward endpoint; `_normalize_feature` reused). **`routes/locales.py`** gets `_display_address(profile_row)` extractor (JSON-parses `place_payload` → `properties.full_address` / `properties.place_formatted` / empty; tolerates absent + malformed + non-dict payloads); `_existing_locale_by_mapbox_id(db, uid, mapbox_id, exclude_slug=None)` dup helper; new `delete_locale` route at `POST /locales/<locale>/delete` (FK CASCADE clears `locale_equipment` + `locale_equipment_overrides` + `locale_toggle_overrides`; residential split rule additionally drops the linked `gym_profiles` row when `category IN ('home_gym','other_residence')` AND `gym_profile_id IS NOT NULL` AND `created_by_user_id = uid`; legacy enum slugs `home/hotel/partner/airport` guarded with a warning flash); `_save_mapbox_anchored` dup-check on both INSERT + upgrade paths (warning flash + redirect to `edit_profile` on the existing dup; upgrade path uses `exclude_slug=upgrade_slug` so it doesn't self-trigger); `nearby_instances` POST filters selections against existing-`mapbox_id` rows for this user and flashes a `Skipped N already-saved location` info message; `refresh_from_mapbox` Phase 1 rewritten to call `mapbox_client.retrieve(stored_mapbox_id, session_token=uuid.uuid4().hex)` instead of `search_nearby(locale_name, lng, lat)`+match-by-id — eliminates the renamed-locale failure mode entirely (Item B 🔴 fix); the now-unused `stored_lng` / `stored_lat` reads dropped; `MapboxNoResults` from `/retrieve` keeps the existing "Mapbox no longer returns this exact place. Edit the locale to relink." warning + edit-screen redirect; `SHARED_PROFILE_CATEGORIES` gains `'outdoor_park'` (8 total — privacy boundary becomes residence-vs-public, cleanly); `MANUAL_CATEGORIES` label swaps for `home_gym` → `Home (primary residence)` and `other_residence` → `Other residence (in-laws / friend / AirBnB)` (enum values unchanged); `_is_shared_profile_locale` docstring updated. **`templates/locales/list.html`** renders the address as a muted small-text caption under each non-legacy card title (gated on non-empty `display_addresses[locale]`). **`templates/locales/form.html`** renders the address as a muted small-text caption under the header (gated on non-empty `display_address`) + adds a bottom Delete button (browser `confirm()` per Andy 2026-05-16 pick) gated on `is_deletable` (legacy enums hidden). Session-token approach: Python `uuid.uuid4().hex` per refresh call — fresh UUID per invocation, no tracked-token table at N=1; can fold in `mapbox_session_tokens` table later if billing visibility becomes needed. **Known follow-up tracked in §6** of the closing handoff: park-specific tag taxonomy — `EQUIPMENT_CATEGORIES` is gym-centric, so outdoor_park shared profiles render irrelevant gym checkboxes (athletes leave most unchecked; shared profile is effectively just "this park exists, anchored here"). Item E (retire legacy `LOCALES = ['home','hotel','partner','airport']`) is its own PR — hard-coupled to `routes/coaching.py` literal at line 22 + `routes/references.py` import at line 5 + cosmetic badge logic in `templates/references/exercises.html:56`; scope-bounded but separate. PR_Verification_Status gains a new PR18 section with 12 testable §5.0 steps for the post-merge walk. Predecessor: **Layer 4 prompt-body arc — 3 of 5 prompts shipped (seam-reviewer + per-phase synth + single-session synth); coupled §10.4 spec amendment retiring rest-shape repurposing for sport-unavailable** — see `handoffs/V5_Design_Layer4_Prompts_SingleSession_Closing_Handoff_v1.md`. Andy picked single-session synth (D-63; Pattern B) as third prompt of the arc per the handoff §5.1 smallest-to-largest recommended ordering. `aidstation-sources/prompts/Layer4_SingleSession_v1.md` (589 lines, 14 H2 + 13 H3+ file-structure subsections) is the Pattern-B single-call synthesizer prompt called by D-63 on-demand workout — one LLM call, no phase context, no seam reviewer, `is_ad_hoc=True` + `len(sessions)==1` output. Source decisions D1–D12 in the file header: D1 tool-use (`record_single_session`); D2 extended thinking ON ~3500 tokens (mid-defensive between seam-reviewer's 2000 + per-phase's 5000); D3 full payloads verbatim (~3500 input budget fits without trimming); D4 hybrid prior-session-window (summary stats + last 7d verbatim); D5 closed-set 3-flag D-63-only enum (`intensity_modulated`, `technique_emphasis`, `discipline_specific_intensity` — phase-tied flags excluded since D-63 is phase-agnostic); D6 judgment + anchor signals + must-explain when modulating; **D7 pre-LLM precondition (γ) — sport-unavailable becomes a §4.4 input validation raise + D-63 §6.3 caller-side handling; rest-shape repurposing retired** (paired spec amendment this session — see below); D8 hybrid `RuleFailure` retry context; D9 tight schema length caps (240 / 200 / 120 / 240 chars `session_notes` / `coaching_intent` / `load_prescription` / `instructions` — matched to the 1500 `max_tokens` budget); D10 verbatim-respect-on-`notes_for_synthesizer` unless safety blocker, + overreach warning + three-tier interaction with D6 (full honor → honor-with-warning → modulate-with-explanation); D11 unified prompt with conditional equipment block (one file, Mustache branch at the equipment-injection slot — same coaching logic for both locale + quick_equipment paths); D12 file at `aidstation-sources/prompts/Layer4_SingleSession_v1.md` per `prompts/` subdir convention. Token + cost per invocation: ~3500 input + ~3500 extended thinking + ~800 output = ~$0.075/invocation worst-case (matches `Layer4_Spec.md` §11.3 ~$0.02 typical headline assuming reasoning depth is below worst-case). 15 PSS-prefix v1 test scenarios in §12 mapping to `Layer4_Spec.md` §13.4 single-session scenarios + §13.6 coaching-flag emit + §13.7 cache hit/miss. **Paired spec amendments this session (broke the prompt-body-doesn't-touch-spec convention per Andy's option-2 pick to fold §10.4 fix into this session):** `Layer4_Spec.md` §3.5 (new `request_sport_unavailable_at_locale` error code), §4.4 (new sport-availability precondition row), §10.4 (sport-unavailable row rewritten — rest-shape repurposing retired; pre-LLM raise path); §13.4 TS-33 (updated expected output); `OnDemand_Workout_D63_Design_v1.md` §6.3 (caller-side pre-check wording) + §9 scenario 5 (matching update). Spec contract relevant: pre-LLM raise keeps Layer 4 producing workouts only; D-63 caller handles the unavailable response shape + frontend affordances; LLM is never invoked on impossible requests. **Two prompt bodies still queued** (Andy's pick on order): per-tier T1/T2 synthesizer (D-64; Pattern B refresh), race-week-brief (Pattern B; pre-race only). Predecessor: **Layer 4 prompt-body arc — 2 of 5 prompts shipped (seam-reviewer + per-phase synth); cadence switched to per-prompt** — see `handoffs/V5_Design_Layer4_Prompts_PerPhase_Closing_Handoff_v1.md`. Andy picked per-phase synthesizer as second prompt of the arc (seam-reviewer was first; both build against the v1 spec contracts). Per-prompt cadence (rather than end-of-arc batch) means CLAUDE.md + backlog bump + PR after each prompt body — switched this session per Andy 2026-05-16. `aidstation-sources/prompts/Layer4_PerPhase_v1.md` (764 lines, 14 H2 + 23 H3+ subsections) is the load-bearing per-phase synthesizer prompt called by Pattern A (`plan_create` + Pattern-A `plan_refresh` T3 cross-phase) — one call per phase, sequential, prior phase's accepted output passed as context. Source decisions D1–D10 in the file header: D1 tool-use (`record_phase_sessions`); D2 extended thinking ON ~5000 budget tokens (max-defensive); D3 hybrid input format (small payloads full, large payloads trimmed per-locale per-format); D4 hybrid prior-phase rendering (weekly rollup + last-week sessions full); D5 closed-set coaching-flag schema enum union per §§8.2–8.6 (6 LLM-emitted flags only — `technique_emphasis`, `long_slow_distance`, `weak_link_targeted`, `overreach_test`, `discipline_specific_intensity`, `race_pace_specific`); D6 deload cadence anchor table per mode (every 4th/3rd/5th wk standard/compressed/extended; custom = judgment); D7 Taper-length anchor table per race format (1–2wk sub-marathon / 2–3wk marathon-IM-class / 3wk full-IM & expedition AR 48–72h & multi-day ultra & stage race / 3–4wk expedition AR >72h / 1wk open-ended); D8 hybrid RuleFailure retry context; D9 schema-enforced length caps (600/240/600 chars for `session_notes`/`coaching_intent`/`phase_synthesis_notes`); D10 file at `aidstation-sources/prompts/Layer4_PerPhase_v1.md` per the `prompts/` subdir convention. Token + cost per phase: ~8000 input + ~5000 extended thinking + ~3000 output = ~$0.144/phase; 4-phase `plan_create` ~$0.76 total (matches §11.3 headline $0.50–1.10). 15 PPS-prefix v1 test scenarios in §12. **Companion v1 contracts honored:** §5.2 step 3 (call site), §5.4 (deterministic validator), §5.5 (capped retry), §6.1 (phase boundary helper), §6.2 (seam re-prompt path), §6.5 (start_phase != 'Base'), §7.2/§7.3/§7.4 (PlanSession discriminated union + sub-blocks), §7.6 (PhaseSpec + SynthesisMetadata), §8 (closed-set flag taxonomy), §11.2 (token budget — confirmed). `Layer4_Spec.md` untouched this session — prompt bodies are downstream consumers; §12.2 forward-pointer remains accurate at 2 of 5 shipped. **Three prompt bodies still queued** (Andy's pick on order): per-tier T1/T2 synthesizer (D-64; Pattern B refresh), single-session synthesizer (D-63; Pattern B), race-week-brief (Pattern B; pre-race only). Predecessor: **Layer 4 seam-reviewer prompt body** — see `handoffs/V5_Design_Layer4_Prompts_SeamReviewer_Closing_Handoff_v1.md`. `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md` (436 lines) shipped 2026-05-16 via PR #59 — first of 5 in the prompt-body arc. Source decisions D1–D7 in the file header: tool-use, extended thinking ON ~2000 tokens, hybrid input (rollup + last/first week verbatim), coaching-judgment-with-anchors verdict calibration (10%/8pp/25% wk-over-wk drift thresholds), constraint-level-only `seam_issues` writing (≤30 words / ≤4 entries), CLAUDE.md voice, new `prompts/` subdir per Andy's D7 override. Established the prompt-body-arc conventions inherited by all four subsequent prompts (file structure, tool-use mechanism, closed-set flag enforcement pattern). CLAUDE.md/backlog bump was deferred per the v1-commit-deferral rule carried from the spec arc; retroactively folded into v32 this session per the cadence switch. Predecessor: **Layer 4 spec v1 — 4-session design arc + 2 calibration commits + close-out** — see `handoffs/V5_Design_Layer4_Spec_Session4_Closing_Handoff_v1.md` (with §10 close-out addendum). Layer 4 (plan generation) is the next layer in the v2 LLM pipeline after Layers 0–3 — owns the discriminated-union `PlanSession` shape, the four entry points (`plan_create` / `plan_refresh` / `single_session_synthesize` / `race_week_brief`), Pattern A (per-phase synthesis + LLM seam review with β propose-patch authority per Decision 8) and Pattern B (single-call + deterministic validator), the periodization decomposition + shape-override path (4 triggers + 4 `Layer4ShapeInfeasibleError` classes with concrete detection algorithms), the coaching-flag taxonomy (closed-set per-phase + cross-phase tables + LLM-emitted vs spec-auto-emitted split + call-level observation triggers), the cache + determinism contract (per-entry cache keys + per-phase cache for Pattern A + invalidation triggers + per-call rebinding semantics), and the performance budget (latency + token + cost + cache hit-rate + cumulative ceilings + alert thresholds). Contract sections §§1–13 are complete (1746 lines, 96 H2+ headings, 84 numbered test scenarios + 5 CI smoke tests). §14 retrospective intentionally deferred to a follow-on fresh-eyes session per §12.6 — the retro will land before Layer 4 implementation begins. D-63 (on-demand workout) + D-64 (plan refresh tiers) implementation gates removed (both were "🟡 implementation pending — gates on Layer 4 spec landing"; now "🟡 implementation pending — Layer 4 spec landed v1; ready for implementation"). Layer 4.5 — Joint Session Coordinator — its own spec, deferred per the post-pass approach Andy picked 2026-05-16. Predecessor: **PR17 — DATABASE.md deep rewrite + 3 code residuals** — see `handoffs/V5_Implementation_PR17_DATABASE_md_Deep_Rewrite_Closing_Handoff_v1.md`. Closes out the last remaining SQLite-cleanup carry-forward. Root `DATABASE.md` deep-section rewrite: drops the 4 `[STALE — SQLite path retired PR13]` blockquotes PR14 added (Migration philosophy, Init and seed flow, Backend-portable upserts, Postgres datetime vs SQLite TEXT); rewrites each section PG-only; surgical inline cleanup on 5 other spots (top-of-file marker, Multi-user scoping NULL framing, `users.created_at` template-slicing note, `athlete_profile` UPSERT description, `body_metrics` UPSERT branching note). Code residuals PR13 missed: `routes/body.py:73` had a live `if _IS_PG: ... else: INSERT OR REPLACE ...` branch — dead code since `_IS_PG` is always True post-PR13 — stripped; `routes/conditions.py:170` stale comment about `ON CONFLICT vs INSERT OR IGNORE` removed; `routes/locales.py:341` stale comment about `CURRENT_TIMESTAMP vs datetime('now')` removed. Final SQLite reference inventory across the codebase: 0 Python references (`grep -r "_IS_PG\|_is_postgres\|INSERT OR IGNORE\|INSERT OR REPLACE\|datetime('now')"` returns empty); DATABASE.md only references SQLite in the top-of-file historical-marker block + 3 incidental historical mentions (PR13 retirement note, `SQLite→Neon cutover` defense-in-depth context, "no SQLite fallback path" architecture statement) — all appropriate. 5-file ceiling broken intentionally (7 files: 1 doc rewrite + 3 code residuals + 3 doc bookkeeping). D-54 SQLite + D-65 TrueNAS Docker stack-cleanup story closed for real. Predecessor: **PR16 — Control_Spec v7 → v8 SQLite cleanup** — see `handoffs/V5_Implementation_PR16_Control_Spec_v8_Closing_Handoff_v1.md`. Doc-only spec bump executing the PR14 §5.3 / PR15 §5.1 Option B deferred cleanup carry-forward. `Control_Spec_v7.md` → `_v8.md` adds a new "What changed in v8 vs v7" section that retroactively flags v6's "removed during Phase 5 of the catalog migration" SQLite-coupling narrative (item #7) as superseded by PR13's standalone D-54 closure; notes the TrueNAS Docker retirement (D-65 ✅ Resolved); flags §9 doc-map snapshot as stale with explicit Rule #12 resolve-to-highest-N reminder (Onboarding v4 → v5, Integration v2 → v5, Catalog plan v2 → v3, Backlog v11 → v29, Layer3_3B_Spec ⏳ → ✅, design-wave specs uncovered). §§1–8 + §§10–11 body byte-identical to v7 per Rule #12. No code; no D-row status flips (the SQLite cleanup carry-forward isn't a D-row of its own; tracked in handoff §5.3). Single file change (Control_Spec_v8) + 3 doc-bookkeeping files (this CLAUDE.md edit, backlog v29, closing handoff) = 4 substantive files, under the 5-file ceiling. Predecessor: **PR15 — D-61 profile-tab schedule edit follow-on** — see `handoffs/V5_Implementation_PR15_D61_Profile_Tab_Edit_Closing_Handoff_v1.md`. Surfaces the v5 §G per-day-windows form on `/profile?tab=schedule` so athletes can edit their schedule without re-visiting `/onboarding/schedule`. Extracts the §G form fields into a shared partial `templates/onboarding/_schedule_form.html` (218 lines); `templates/onboarding/schedule.html` slims 293 → 53 lines and includes the partial inside its existing `<form action="/onboarding/schedule">` wrapper (onboarding flow regression-clean). `templates/profile/edit.html` gains a Schedule tab + tab-pane wrapping `<form action="/profile/schedule">` + the same partial + Save-schedule button. `routes/profile.py` `edit()` GET pre-populates schedule context identically to `routes/onboarding.py:schedule` GET; new `save_schedule()` POST handler at `/profile/schedule` lazy-imports `_parse_schedule_form` from `routes.onboarding` (cycle would otherwise close — onboarding already imports from profile) and round-trips identically to `onboarding.schedule_save` differing only in success redirect (`/profile/?tab=schedule` vs `/profile?tab=athlete`). D-61 status flipped 🟢 §G + onboarding integration shipped (PR12) → 🟢 §G + onboarding + profile-tab editing shipped (PR12 + PR15); 🟡 JIT swap session-card UI still pending Layer 4 spec. Predecessor: **PR14 — Doc sweep** — `handoffs/V5_Implementation_PR14_Doc_Sweep_Closing_Handoff_v1.md`. Closes out the PR13-deferred doc-sweep follow-on. `Catalog_Migration_Plan` v2 → v3 (SQLite retirement decoupled from §1 out-of-scope + §5 decision #5 marked Resolved). `Athlete_Data_Integration_Spec` v4 → v5 (§2.5 SQLite freeze flagged Retired). `aidstation-sources/DATABASE.md` (a stale duplicate of root) collapsed to a thin redirect at the root file. Root `DATABASE.md` PR13 marker strengthened + inline `[STALE — SQLite path retired PR13]` flags added on the three biggest SQLite-historical subsections (Migration philosophy, Init and seed flow, Backend-portable upserts, Postgres datetime vs SQLite TEXT in templates). No code changes. (PR13 + PR12 fall off this last-shipped chain per the 4-deep convention — both reachable via PR14's narrative line, via their own handoff files, and via PR17's narrative which explicitly references PR13's SQLite retirement.)

**Authoritative current files** (always resolve by listing directory and viewing the highest `_vN`):
- Architecture: `Control_Spec_v8.md`
- Backlog: `Project_Backlog_v34.md`
- PR verification status: `PR_Verification_Status.md` (per-PR §5.0 step state — read at session start so prior PRs' "still owed" carry-forward is reconciled against actual on-disk truth instead of treated as monolithically pending)
- Onboarding data: `Athlete_Onboarding_Data_Spec_v5.md` (consolidates D-58 + D-59 + D-60 + D-61; v4 retained as in-project history per Rule #12)
- Onboarding design wave inputs: `Onboarding_D58_Design_v1.md`, `Onboarding_D59_Design_v1.md`, `Onboarding_D60_Design_v1.md`, `Onboarding_D61_Design_v1.md`
- Plan-execution design wave inputs: `OnDemand_Workout_D63_Design_v1.md`, `Plan_Refresh_D64_Design_v1.md` (both 🟡 implementation gates on Layer 4 spec landing)
- Integration: `Athlete_Data_Integration_Spec_v5.md`
- Catalog migration: `Catalog_Migration_Plan_v3.md`
- Layer 0 ETL: `Layer0_ETL_Spec_v7.md`
- Layer 3 done: `Layer3_3A_Spec.md`, `Layer3_3B_Spec.md`
- Layer 4 done (v1; §14 retro pending): `Layer4_Spec.md`
- Layer 4 prompt bodies (3 of 5 shipped; 2 queued — per-tier T1/T2, race-week-brief): `aidstation-sources/prompts/Layer4_SeamReviewer_v1.md`, `aidstation-sources/prompts/Layer4_PerPhase_v1.md`, `aidstation-sources/prompts/Layer4_SingleSession_v1.md`
- Vocabulary audit: `Vocabulary_Audit_v3.md`
- Exercise DB: `data/AR_Exercise_Database_v19.xlsx` (245 exercises, 36 sports, 1,068 sport-exercise pairings)
- Sports framework: `data/Sports_Framework_v10.xlsx`

**Next forward move:** Andy's choice. Candidates with Layer 4 spec v1 + 3/5 prompt bodies landed (per-prompt cadence in effect; each remaining prompt is its own session under stop-and-ask trigger #2):
- **Layer 4 §14 retrospective** — fresh-eyes critical-evaluation pass over §§1–13 (including the §3.5/§4.4/§10.4/§13.4 amendments from the D-63 prompt session); lands before Layer 4 implementation per §12.6 deferral.
- **Layer 4 prompt-body design sessions (2 remaining)** — per-tier T1/T2 synthesizer (D-64; Pattern B refresh; may split T1+T2 across 2 sessions), race-week-brief (Pattern B; pre-race only). Andy picks order. Conventions inherited from `Layer4_SeamReviewer_v1.md` + `Layer4_PerPhase_v1.md` + `Layer4_SingleSession_v1.md`: tool-use output mechanism, extended thinking, hybrid input format, closed-set coaching-flag schema-enum enforcement, 14-section file structure, schema-enforced length caps, coaching voice, anchor-table-based judgment for prompt-internal heuristics.
- **Layer 4 implementation track** — D-63 (on-demand workout) + D-64 (plan refresh tiers) implementation gates removed by spec landing; both ready for implementation against the §§1–13 contracts. D-63 LLM-call layer can now be implemented against `Layer4_SingleSession_v1.md`; D-64 prompt body (per-tier T1/T2) still queued. Deterministic-validator harness + payload schema scaffolding can start independently of remaining prompt bodies.
- **v5 onboarding implementation PR** — substantial code work: `_PG_MIGRATIONS` for `daily_availability_windows`, `gym_profiles`, `locale_equipment_overrides`, `locale_toggle_overrides`, `athlete_profile_field_provenance`, `account_nudges`; `locale_profiles` column additions; `chain_registry.py` module; OAuth-first onboarding flow frontend; provider prefill UX; shared-gym-profile inherit/override/dispute UI; per-day windows UI; session-card JIT swap.
- **D-50 wiring resumption** — now unblocked by D-58. PR1 scope: `provider_auth.py` helper + first real OAuth flow (COROS recommended) + COROS webhook recording + D-58 connect-step frontend integration.
- **PR18 follow-on — Item E retire legacy `LOCALES`** — separate PR per PR18 closing handoff §3.5. Audit found hard consumers: `routes/coaching.py:22` `LOCALES = ['home','hotel','partner','airport']` literal (v1 coaching form dropdown + fallback default); `routes/references.py:5` imports `LOCALES`; `templates/references/exercises.html:56` cosmetic badge logic. The refactor switches coaching + references to query the athlete's actual locales (legacy + athlete-created) instead of the hardcoded list; coaching default-fallback decision pending (D-61 `preferred=TRUE` locale vs. most-recently-updated vs. form-level guard). Scope ~4 files, well under ceiling. Independent of v1-coaching-v2-LLM-pipeline replacement track.
- **PR18 follow-on — park-specific tag taxonomy** — `EQUIPMENT_CATEGORIES` is gym-centric; outdoor_park shared profiles now render irrelevant gym checkboxes. Real fix: category-aware tag taxonomy or new `OUTDOOR_TAGS` literal (water fountain, restroom, shelter, parking, trailhead signage). Defer until park-locale usage actually exercises the seam.
- **Layer 4.5 — Joint Session Coordinator spec** — separate file; post-pass over linked athletes' Layer 4 payloads. Lands when team-features track activates.
- **Layer 5 spec** — parallel supplemental outputs (nutrition, supplements, 7-day clothing/conditions). Consumes `PlanSession.session_notes` + `cardio_blocks` per §12.3 forward-pointer.

**Independent parallel tracks:**
- D-50 wiring (now unblocked by D-58) — see "Next forward move" above for PR1 scope
- D-52 Catalog Migration Phase 1 — fuzzy-match HITL alias audit
- D-54 SQLite collapse — ✅ Resolved 2026-05-16 (PR13 — stripped `SQLITE_SCHEMA`, `_SQLITE_MIGRATIONS`, `init_sqlite`, `sqlite_path`, `_is_postgres()` guards across `database.py`/`init_db.py`/`app.py`/route files; PG-only via `DATABASE_URL`)
- D-55 Garmin onto `provider_auth` — **paused** until Garmin reopens API access
- D-57 Research re-evaluation cadence design
- D-58–D-61 Onboarding Design Wave — ✅ **complete** (design + v5 spec consolidation shipped 2026-05-14)
- D-62 webhook_events retention prune — tracked; lands alongside first real webhook handler implementation

---

## Rules of operation (NON-NEGOTIABLE)

These exist because handoff narrative has drifted from on-disk state before. Quality is enforced by mechanical verification, not by trust.

### Rule #9 — Session-start verification

Before continuing prior work, verify the previous handoff's claimed file updates actually landed in the files. Spot-check the specific edits the handoff claims using `grep` or anchor reads. Reconcile any gap as the **first action of the session**, before any new work. Do not proceed assuming the handoff narrative is accurate.

### Rule #10 — Session-end verification

Do not write a handoff claiming a file edit landed unless the edit is actually in the file. Verify each claimed update against the on-disk file before composing the handoff.

### Rule #11 — Mechanically-applicable deferred edits

When a handoff defers edits, include mechanically-applicable instructions:
- For surgical edits: `str_replace`-style old_string / new_string blocks
- For section rewrites: "replace section X with verbatim content: [...]"

**No narrative summaries** like "update §2/§3 of Control_Spec" without the new text. The next session executes spec'd edits; it does not re-derive them. Failure mode is loud (str_replace mismatch) not silent (interpretive drift).

### Rule #12 — Numeric version suffixes

Revised files save with a numeric version suffix (`_v1.md`, `_v2.md`, …). Each revision bumps N from the highest existing. Old versions accumulate as in-project history — do not delete. Cross-references cite the logical name without version; resolve via directory listing to the highest N at use time.

### Rule #13 — Every closing handoff names CLAUDE.md as the first re-read

Every closing handoff's forward-pointer / next-session reading list begins with **"Read `aidstation-sources/CLAUDE.md` fully"** as the first explicit step, before any domain-specific reads (backlog, prior handoff, target spec files). The First-session checklist already names CLAUDE.md as item 1; Rule #13 makes it the handoff author's responsibility to reinforce it in the handoff itself, so the next session's Rule #9 reconciliation runs against the latest operating context (rules, framing, stop-and-ask triggers) rather than only the latest spec narrative. Especially important when operating rules or framing have changed mid-stream — a session that reads only the latest handoff and skips CLAUDE.md will operate on stale context.

---

## Stop-and-ask trigger list

Your default is execution. **Exception:** the items below. For these, stop, enter `/plan` mode, and wait for Andy's explicit confirmation before implementing.

1. **Scoping a new prompt vs a query** — is this Layer 0 reference data (LLM-generated once, human-reviewed, locked) or a runtime athlete-specific query?
2. **Designing or significantly modifying an LLM prompt body**
3. **Adding a new vocabulary entry** — strict no-padding rule applies; only when no existing entry covers the same physical stimulus / technique / injury profile
4. **Adding a new exercise database entry** — same no-padding rule
5. **Schema changes** affecting an inter-layer contract or `etl_version_set` pinning
6. **Designing or modifying a HITL trigger** (Layer 3.5 gate logic)
7. **Creating or changing a partial-update invalidation rule** (which layers re-run when X changes)
8. **Architectural alternatives with real tradeoffs** — don't pick silently
9. **Promoting a Project_Backlog item from Deferred to Blocker**
10. **Any change to `Control_Spec` architecture**
11. **Any new D-row in the backlog with cross-layer scope**

For each, the expected output before stopping is: options considered, tradeoffs, your recommendation, your gut check (risks / what might be missing / best argument against). Then wait.

**Do not implement first and ask forgiveness.**

---

## Working principles

- **Spec-first sequencing.** Architecture → prompts → implementation. Resist shortcuts. Resist producing testable output before the spec is correct and complete.
- **Layer specs follow a depth standard.** 14 sections matching `Layer2C_Spec.md`: purpose, boundaries, function signature, validation, algorithm, payload schema, coaching flags, caching, edge cases, performance budget, open items, test scenarios, gut check. Do not skip per-node specs; do not let design decisions live only in handoff docs.
- **5-file quality ceiling per session.** Do not push more than ~5 files of substantive edits/creations in a single chat. Quality degrades past that. If a request exceeds the ceiling, propose splitting before starting.
- **Project_Backlog is the single source of truth for deferred work.** Update between sessions when items are deferred. Categories: Blocker / Deferred / Cleanup. Items can promote to Blocker but never demote silently.
- **Never invent file contents.** If a file is referenced and not yet viewed, view it first. If a function or table is referenced and not visible, search for it before assuming.
- **Andy makes all final architectural decisions.** You are a technical thought partner.

---

## Chat tone with Andy

- Direct. No filler. No hype. No "great question."
- Match confidence to reality. If uncertain or tradeoffs exist, say so briefly.
- If an idea is weak or flawed, say it plainly and explain why.
- End substantive recommendations with a gut check: risks / what might be missing / best argument against.
- If the session gets long or messy, remind Andy to create a handoff note and start fresh.

---

## Stack

- **AI backend:** Claude API (Sonnet/Opus latest)
- **Database:** PostgreSQL (Neon) — both production and dev. SQLite path retired 2026-05-16 (PR13)
- **ETL / data work:** Python (openpyxl, rapidfuzz, pandas)
- **Web app:** Flask + Jinja templates, deployed to Vercel (`aidstation-pro.vercel.app`). Code at the repo root (`app.py`, `routes/`, `init_db.py`, etc.). This is the **v1 app**, which is the current production target for the v2 LLM-pipeline build being designed in `aidstation-sources/`. TrueNAS / Docker deployment path retired 2026-05-16 (PR13) — was never used in practice.
- **Athlete integrations:** COROS + Ride With GPS shipped (Phase-0 webhook stubs); Strava/Whoop/TrainingPeaks/Zwift stubs prepped on a separate branch (uncommitted at time of writing per `HANDOFF-2026-05-13-stub-batch.md`); Polar + Wahoo next; Garmin paused (API closed); Apple Health + Samsung Health out of scope (need native iOS/Android clients).

---

## Operating context (v1 + v2, selective rebuild)

This repo holds **two parallel work tracks**:

1. **v1 Flask app at the repo root.** Live production AIDSTATION. Strength-training + cardio-logging + Garmin FIT ingestion + Claude-API-based coaching. The current code path. Has no users in production — Andy is the only test athlete (one test account).
2. **v2 LLM-pipeline design in `aidstation-sources/`.** Layers 0–5 spec-first build. Layer 0 reference data is deployed; Layers 2A–2E specced; Layer 3 in progress (3A done, 3B next).

**Selective rebuild (the v1→v2 path):**
- **Keep:** provider integration layer (`routes/`, `*_connect.py`, OAuth callback plumbing), auth + accounts, DB scaffolding pattern (`init_db.py`, `_PG_MIGRATIONS` / `_SQLITE_MIGRATIONS`, the `database.py` compatibility layer), and `rx_engine_spec.md` as the strength-progression algorithm spec.
- **Replace:** coaching + plan-generation. The current `coaching.py` is one big Claude call; v2 is the structured 0–5 layer pipeline.
- **Revisit later:** v1 strength UI, the broader v1 schema rot.

**Strangler-fig sequencing.** v2 modules ship into the running v1 app one at a time, replacing pieces. No parallel staging environment. v1 having no users (only Andy as test athlete) makes this safe — schema migrations and route swaps don't need backward-compatibility shims.

**"Push to production as we go" rule (Andy 2026-05-14):** prefer shipping working v2 code into v1 over accumulating more design ahead of any implementation. The 5-file ceiling and spec-first sequencing still apply, but specs should be scoped to what we're about to build, not everything ahead.

---

## Andy's active athlete context (May 2026)

Training for **Pocket Gopher Extreme 2026** (July 17–19, Nerstrand MN; 48–56 hour expedition AR). Disciplines: trail running, hiking, MTB, packrafting, outdoor rock climbing, abseiling.

**Active injury — left wrist:** painful and weak with wrist extension under load. Avoid all wrist-extension-loaded exercises. Pushups in fist position only. Climbing grip-dominant moves OK; wrist-loaded moves not.

This context matters because Andy dogfoods his own product — coaching guidance you draft may be tested against his actual training. If you draft a session for him, respect the wrist constraint.

---

## First-session checklist

When you start a fresh session, do this before anything else:

1. Read this CLAUDE.md fully.
2. Read `Project_Backlog_v11.md` (or highest `_vN`).
3. Read the most recent handoff in `handoffs/`.
4. Apply Rule #9 — verify the previous handoff's claimed edits actually landed.
   - Also read `PR_Verification_Status.md` so you know which §5.0 steps Andy has already walked / what's blocked vs. genuinely owed. Don't re-list completed items as "still owed."
5. Tell Andy: (a) what you understand current state to be, (b) what you understand the next focus to be, (c) any drift you found between handoff narrative and on-disk state.
6. **Do not start work** until Andy confirms scope.

---

*End of CLAUDE.md.*
