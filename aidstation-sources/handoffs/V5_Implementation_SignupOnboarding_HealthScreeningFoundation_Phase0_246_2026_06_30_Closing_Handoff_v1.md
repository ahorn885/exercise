# V5 Implementation — Sign-up / Onboarding Consolidation, Phase 0: Health-Screening Foundation (#246) — Closing Handoff (2026-06-30)

**Branch:** `claude/signup-onboarding-plan-46m57q` · **PR:** [#1070](https://github.com/ahorn885/exercise/pull/1070) (opened + **merged**, merge commit, Andy's go 2026-06-30) · **Epic:** [#246](https://github.com/ahorn885/exercise/issues/246) (signup flow & athlete-info screens) · **Spec:** `docs/privacy_program/AIDSTATION_Health_Screening_Spec_v2.md` (binding) · **Plan:** the sign-up/onboarding consolidation plan (8 open issues, phased) · **Suite:** full `tests/` **3989 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).

**Context:** Andy asked for a single coordinated push to close out **all eight** open sign-up/onboarding issues "once and for all" (#246, #257, #394, #1067, #272, #223, #304, #267) rather than picking them off one at a time. A plan was built, the open *decisions* surfaced and resolved (see §4), and **Phase 0 — the missing health-screening foundation — shipped this session.** Phase 0 is the prerequisite for #394 (screening-question polish) and #223 (pregnancy field): both assumed a screening screen that **did not exist** (no `/onboarding/health-screening` route, no `health_screening` table).

---

## 1. Session-start verification (Rule #9)

Fresh arc (no predecessor handoff to sweep). Confirmed the starting gap against on-disk state before building:
- `grep` over `routes/` → **no** `health-screening` / `health_screening` route (confirmed absent).
- `init_db.py` → no `health_screening` table.
- `routes/onboarding.py` step chain ended at `target_race` → `route_locales` → `/profile?tab=athlete` (the §A hard-profile form); the screening had no slot.
- `docs/privacy_program/AIDSTATION_Health_Screening_Spec_v2.md` present and binding (the build target).
- Re-audited #304 Part B against current code (see §4 D2) — the issue text is materially stale.

## 2. What shipped — Phase 0 (health-screening foundation)

| File | Change |
|---|---|
| `init_db.py` | **New `health_screening` table** appended to `_PG_MIGRATIONS` (public-schema → auto-applies on deploy). One current-state row per user: `screening_version`, `flags JSONB`, `details JSONB`, `details_optin BOOLEAN`, `acknowledged`, `acknowledged_at`, `last_assessed_at`, `reassessment_due_at`, `created_at`, `updated_at`. Idempotent `CREATE TABLE IF NOT EXISTS`. |
| `health_screening_repo.py` *(new)* | The 10-question set (Spec §4), flag taxonomy → plain-language labels (§5), `parse_answers` (the sensitive free-text opt-in gate, §7.2 — no `details` stored without explicit opt-in), `flag_descriptions`, `get_screening` (current acknowledged row + live `reassessment_overdue`), `save_screening` (acknowledged-now upsert; `last_assessed_at = NOW()`, `reassessment_due_at = NOW() + INTERVAL '365 days'`, §9.1). Mirrors the `pack_load_repo` repo pattern (`?` placeholders, user-scoped, caller commits). |
| `routes/onboarding.py` | `import` from `health_screening_repo`; new constant `_POST_HEALTH_SCREENING_TARGET = '/profile?tab=athlete'`; **rerouted** the three profile-bound onboarding exits (`_POST_STEP2_SKIP_TARGET`, `_POST_STEP3C_TARGET`, `_POST_STEP3D_TARGET`) to `/onboarding/health-screening`; **new routes** `health_screening` (GET — intro + questions, Spec §3.2 Screens 1-2) and `health_screening_save` (POST — flag-aware acknowledgment screen → persist on `acknowledge=1`, Screen 3). Two-phase POST so the row is written **only on explicit acknowledgment** (§6.2). Acknowledgment-only / non-blocking (§2.3). |
| `templates/onboarding/health_screening.html` *(new)* | Questions phase (10 yes/no + per-item optional free-text + the sensitive-storage opt-in checkbox) and acknowledgment phase (flag-aware copy + the pregnancy paragraph when `PREGNANCY` is set). CSP-clean; reuses the existing `.onb-wrap`/`.onb-nav`/`.btn` shell classes. Carries answers forward as hidden fields between phases; the save handler re-parses them server-side. |
| `templates/onboarding/_onb_steps.html` | Added `health` (label **Health**) as the 7th/final stepper pill. |
| `templates/onboarding/{connect,prefill,locales,skills,schedule,target_race}.html` | "Step N of 6" → "Step N of 7" copy bump to match the new step count. |

**Placement rationale:** the screening is the **final onboarding gate before the §A hard-profile form**. Every prior exit that jumped straight to `/profile?tab=athlete` (connect-skip, target-race-skip, route-locales continue/skip) now routes through it, so the service-necessary screening (Spec §11) is always reached before plan-capable profile entry — regardless of which steps the athlete skipped.

## 3. Verification

- Full `tests/` suite **3989 passed / 30 skipped** (no new failures; the 3 warnings pre-exist, #217).
- New tests: `tests/test_health_screening_repo.py` (opt-in gate enforced at parse + write boundaries, flag taxonomy/ordering, JSONB upsert shape); `tests/test_health_screening_render.py` (questions render — shell + stepper + 10×yes/no + opt-in + CSP-clean; no-flags acknowledgment; pregnancy paragraph; final acknowledge → persist + 302 to profile); a migration-shape guard in `tests/test_init_db_schema.py`.
- CI on PR #1070: **all green** (Python unit suite ✅, Layer 0 gate ✅, JS harness ✅, Vercel deploy ✅; Real-LLM smoke skipped as expected).
- **No `layer0-apply` owed** — `health_screening` is a public-schema `_PG_MIGRATIONS` entry, auto-applies on the Vercel deploy. **Migrations were NOT run against live Neon from the container** (egress blocked, per CLAUDE.md); the statement is idempotent and deploy-applied.

## 4. Decisions (RESOLVED — Andy 2026-06-30, AskUserQuestion)

These are the project-level decisions surfaced by the plan; they govern Phases 1-3 and are also recorded in `CARRY_FORWARD.md`.

- **Scope:** all **8** issues in scope (Andy chose "everything"), incl. the heavier v1 infra (#272 SMS/WhatsApp, #267 passkeys).
- **D1 — #1067 pack-load weighting → PRIOR RACE EXPERIENCE.** Weight having carried the pack before on a long race above recent pack training (proven durability first). Lands in `layer3b/builder.py` near the `pack_load_history` read (`:615`).
- **D2 — #304 Part B (re-audited; issue text materially stale):**
  - `pack_load_history` — **KEEP** (already threaded: read `layer3b/builder.py:615`, modeled `layer4/context.py:1698`). Folds into D1.
  - `altitude_exposure_count` — **KEEP** (already threaded: read `layer3a/builder.py:597`). Minor follow-up: one path hardcodes `None` at `layer1/builder.py:357`.
  - `network` sub-tree — **ICEBOX** (leave loaded-but-unused, no action).
  - `previous_coaching` — **RETIRE** (stop capturing).
  - `disclosures` — **REMOVE FROM PAYLOAD** (drop `_load_disclosures` from the Layer-1 build + `disclosures` from `layer4/context.py`); **keep the `disclosure_acknowledgments` table** (legal consent record).
  - `identity.notes` — **NO-OP / CLOSE** (already retired; `Layer1Identity` has no `notes` field; migrated to `coaching_preferences` per #954).
- **D3 — #257 scope (confirm at Phase 1 start).** Add the 7 V3 fields; coordinate V3-I-4 (sweat-rate/salt-loss split) with Layer 2E heat work and V3-I-7 (supplement-protocol restructure) with `athlete_supplements_repo.py`.
- **D4 — #394 sequencing → PROCEED IN PARALLEL** with the Layer 3 data contract (#393/D-81); reconcile when it lands.
- **D5 — #272 + #267 → BOTH, VIA TWILIO**, built in Phase 3.

**Interim opt-in note:** the global Privacy-Policy §2.3 "Medical conditions that affect training" toggle does **not** exist in code yet, so Phase 0 gates the free-text on a **screening-local opt-in checkbox** (defaults off — explicit opt-in per §7.2). When the global §2.3 panel lands (D-80 territory, Phase 2), it should drive this instead.

## 5. NEXT — DECIDED: Phase 1 (onboarding data fields)

Phase 1 bundles four issues; **each lands as its own PR** on a fresh branch off `main`. Per the 4-tier order this is tier-3 (finish open-but-not-fully-live functions). Mechanically-applicable scope (Rule #11):

- **#223 — pregnancy field.** Add an explicit `pregnancy_status` onboarding field and make the screening **Q8 / `PREGNANCY` flag** the source of truth; read it in `layer2e/builder.py` HITL gates instead of the current free-text/HRT proxy. (Cross-layer + HITL-adjacent → Stop-and-ask triggers #3/#4 may apply; the *gate* change is the trigger, the field capture is not.)
- **#257 — 7 V3 fields.** Add columns/enums to `athlete.py` `PROFILE_FIELDS` (sleep variability, macro preference, caffeine sensitivity, hydration baseline, body-weight trend, sweat-rate/salt-loss split, supplement-protocol restructure) + `init_db.py` migrations + form fields in `routes/profile.py` / `templates/profile/edit.html`. Confirm D3 (V3-I-4 ownership vs Layer 2E; V3-I-7 vs `athlete_supplements_repo.py`) before starting.
- **#304 Part B (per D2).** Retire `previous_coaching` (stop capturing); remove `disclosures` from the Layer-1 payload + `layer4/context.py` model (keep the table); leave `network` as icebox; fix the `altitude_exposure_count` `None` hardcode at `layer1/builder.py:357`; close `identity.notes` as already-done. Add/extend tests near `tests/test_layer1_builder.py` asserting kept fields render and dropped fields no longer load.
- **#1067 (per D1).** Weight prior race experience above recent pack training in `layer3b/builder.py` (around `:615`); add the "summary view once filled, edit/delete to change" UX to the pack-load entry form (`routes/profile.py` + template; data via `pack_load_repo.py`).

**Then Phase 2** — #394 health-screening polish (D-79,80,82,83,84,85) on top of the Phase 0 screen. **Then Phase 3** — #272 SMS/WhatsApp invites + #267 passkeys/WebAuthn via Twilio (`routes/auth.py`, `mfa.py`). **Closeout** — roll up #246; close it when #257 (its only open child) is done.

### §6 anchor table (Rule #10 — next session's Rule #9 input)

| Claim | File | Anchor / check |
|---|---|---|
| health_screening table exists | `init_db.py` | `grep "CREATE TABLE IF NOT EXISTS health_screening" init_db.py` (in `_PG_MIGRATIONS`) |
| repo module present | `health_screening_repo.py` | `QUESTIONS`, `FLAG_LABELS`, `parse_answers`, `save_screening`, `get_screening` |
| routes present | `routes/onboarding.py` | `def health_screening`, `def health_screening_save`; `_POST_HEALTH_SCREENING_TARGET` |
| step rerouting | `routes/onboarding.py` | `_POST_STEP3C_TARGET = '/onboarding/health-screening'`, `_POST_STEP3D_TARGET = '/onboarding/health-screening'`, `_POST_STEP2_SKIP_TARGET = '/onboarding/health-screening'` |
| template present | `templates/onboarding/health_screening.html` | `phase == 'questions'` / `phase == 'acknowledge'` |
| stepper has Health | `templates/onboarding/_onb_steps.html` | `'health'` in `order`; `'health': 'Health'` |
| tests | `tests/test_health_screening_repo.py`, `tests/test_health_screening_render.py`, `tests/test_init_db_schema.py` | `python -m pytest` those files |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (the sign-up/onboarding arc entry has the resolved D1-D5)
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

**Decisions/notes:** acknowledgment-only / non-blocking model is deliberate (Spec §2.3 / §15 — legal posture); append-only acknowledgment *history* (Spec §8.3 liability defense, edge cases T10/T12) is a documented **follow-up**, not built — the Phase 0 row is current state only. The Layer-3 data contract (Spec §6) is provisional and reconciles with #393/D-81 (D4 = parallel).
