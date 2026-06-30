# V5 Implementation — Sign-up / Onboarding Consolidation, Phase 1: #304 Part B — Remove `disclosures` from the Layer-1 Payload — Closing Handoff (2026-06-30)

**Branch:** `claude/signup-onboarding-health-screening-b224t2` · **Commit:** `b3f1436` (code) + the bookkeeping commits riding the same branch · **PR:** [#1073](https://github.com/ahorn885/exercise/pull/1073) — opened + **auto-merge armed (merge commit, Andy's go 2026-06-30)** · **Issue:** [#304](https://github.com/ahorn885/exercise/issues/304) (use-or-stop-collecting orphaned Layer-1 fields), Part B · **Epic:** [#246](https://github.com/ahorn885/exercise/issues/246) · **Plan:** sign-up/onboarding consolidation, Phase 1 (`CARRY_FORWARD.md` arc entry) · **Suite:** full `tests/` **3989 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).

**Context:** Continuation of the sign-up/onboarding consolidation arc (Phase 0 health-screening foundation shipped + merged last session, PR #1070). Phase 1 bundles four issues, **each its own PR off `main`**. Andy picked the **#304 Part B** slice this session (AskUserQuestion 2026-06-30) — the lowest-risk one, no new UI, executing the already-resolved **D2** decisions.

---

## 1. Session-start verification (Rule #9)

- `./scripts/verify-handoff.sh` → **clean** (no ❌); Phase 0 anchors all present.
- Branch `claude/signup-onboarding-health-screening-b224t2` == `origin/main` (0/0 ahead/behind) — Phase 0 fully merged, clean tree.
- Re-grounded D2 against current code before editing (the issue text is, per D2, "materially stale"):
  - `disclosures` — `_load_disclosures` builds `Layer1Disclosures` into `Layer1Payload`; **grep → no downstream consumer** of `.disclosures` / `Layer1Disclosures` / `DisclosureAck` (only the builder + the model defs). Confirmed orphan.
  - `previous_coaching` — **already retired**: `init_db.py` `_PG_MIGRATIONS` `DROP COLUMN IF EXISTS previous_coaching` (coach_notes merge); no Python capture anywhere.
  - `altitude_exposure_count` — **already threaded**: real load in `layer1/builder.py` lifestyle dict (`row["altitude_exposure_count"]`) + consumer `layer3a/builder.py:597`. The handoff's "`:357` None hardcode" is `_empty_lifestyle()`'s correct empty-row default, NOT a live bug — NO-OP.
  - `network` — ICEBOX (no action). `identity.notes` — `Layer1Identity` has no `notes` field (already retired, #954); `Layer1Availability` — already promoted top-level. NO-OP.

## 2. What shipped — #304 Part B (disclosures payload removal)

| File | Change |
|---|---|
| `layer1/builder.py` | Removed the `disclosures = _load_disclosures(...)` call, the `disclosures_model = Layer1Disclosures(...)` build, the `disclosures=disclosures_model` payload kwarg, the `_load_disclosures` loader function, and the now-orphaned `DisclosureAck` / `Layer1Disclosures` imports. |
| `layer4/context.py` | Removed the `disclosures: Layer1Disclosures` field from `Layer1Payload`, the `DisclosureAck` + `Layer1Disclosures` model classes, and the `Layer1Disclosures` mention from the module docstring. |
| `layer1/__init__.py` | Dropped the now-stale `disclosure_acknowledgments` mention from the "reads these companion tables" docstring (the builder no longer reads it). |
| `tests/test_layer1_builder.py` | Removed the empty-payload `disclosures` assert; removed the `# 22) disclosure_acknowledgments` queued fixture; `_queue_empty_athlete` 27→26 + SELECT-count assert 27→26; **fixed `test_explicit_off_rows_preserved`** (the dropped disclosures SELECT shifted the toggle SELECT 23→22, so its 22-empty preamble became 21); replaced `test_disclosures` with `test_disclosures_dropped_from_payload` (asserts the field is gone from the model + `model_dump()`). |
| `tests/test_layer3a_builder.py`, `test_layer3a_smoke.py`, `test_layer3b_builder.py`, `test_layer3b_smoke.py`, `test_layer4_orchestrator.py` | Removed the orphaned `Layer1Disclosures` import + `disclosures=Layer1Disclosures()` constructor kwarg (`extra="forbid"` would otherwise reject it). |

**`disclosure_acknowledgments` TABLE retained** — it's the legal consent record, still written by the OAuth/locale route handlers (`routes/provider_auth.py`, `routes/locales.py`, etc.). Only the unused payload *load* was removed.

**Scope:** logic change is 2 files (`builder.py`, `context.py`); everything else is mechanical fallout from the single field removal (orphaned imports/kwargs/fixtures + one docstring). Within the spirit of the 5-file ceiling (one coherent, reviewable change).

## 3. Verification

- Full `tests/` suite **3989 passed / 30 skipped** — unchanged baseline, no new failures (the 3 warnings pre-exist, #217).
- `grep -rn "Layer1Disclosures|DisclosureAck|_load_disclosures|disclosures=|\.disclosures\b"` over `*.py` → only the two intentional explanatory comments in `test_layer1_builder.py`. `disclosure_acknowledgments` table refs all retained (init_db, routes, tests).
- **No `layer0-apply` owed** — no schema change (the table stays). Removing a payload field changes `layer1_hash` (it keys every Layer-4 cache entry), so plan-gen cold-recomputes once on the next deploy — expected under the partial-update model; safe (Andy is the only test athlete).

## 4. Decisions

No new decisions this session — executed the already-resolved **D2** (Andy, 2026-06-30, recorded in `CARRY_FORWARD.md`). The disclosures removal IS the decided action; the other D2 fields needed no code change (see §1).

## 5. NEXT — DECIDED: continue with Phase 1 slice **#257 (7 V3 profile fields)**

This handoff continues directly into **#257** next session — it's the explicit next step (Andy, 2026-06-30). It's epic #246's only open child, so it's the path to closing the epic.

- **#257 — 7 V3 profile fields (NEXT).** Columns/enums in `athlete.py` `PROFILE_FIELDS` + `init_db.py` migrations + form in `routes/profile.py` / `templates/profile/edit.html` (sleep variability, macro preference, caffeine sensitivity, hydration baseline, body-weight trend, sweat-rate/salt-loss split, supplement-protocol restructure). **Confirm D3 first** (V3-I-4 sweat-rate/salt-loss split ownership vs Layer 2E heat; V3-I-7 supplement restructure vs `athlete_supplements_repo.py`). Its own PR off `main`.

Then the rest of Phase 1, each its own PR off `main`:

- **#1067 — pack-load weighting (per D1).** Weight prior race experience above recent pack training in `layer3b/builder.py` (~`:615`) + a summary/edit/delete UX on the pack-load entry form (`routes/profile.py` + template; data via `pack_load_repo.py`).
- **#223 — pregnancy field (capture only).** Make screening Q8/`PREGNANCY` the source of truth; add an explicit capture field. **DEFER the `layer2e` HITL-gate half** — gates 1-4 are dead-stubbed (`_emit_hitl_items` returns `[]`, deferred to the post-§I.1 supplements refresh) so there's nothing live to wire into, AND the gate change is stop-and-ask trigger #4. #223 is also labelled `priority:low`/`icebox` on GitHub — confirm with Andy it's still wanted in Phase 1.
- **#304 remains OPEN** — Part B's `_history`-lists decision (medications/conditions/injury history; only the *active* lists are read) was **not** in D2 scope and still needs a thread-or-stop-capturing call.

**Then Phase 2** — #394 screening polish (D-79..D-85) on the Phase 0 screen. **Then Phase 3** — #272 SMS/WhatsApp + #267 passkeys via Twilio (`routes/auth.py`, `mfa.py`). **Closeout** — close epic #246 when #257 is done.

### §6 anchor table (Rule #10 — next session's Rule #9 input)

| Claim | File | Anchor / check |
|---|---|---|
| disclosures gone from payload build | `layer1/builder.py` | `grep -c "_load_disclosures\|Layer1Disclosures\|disclosures=" layer1/builder.py` → 0 |
| disclosures gone from the model | `layer4/context.py` | `grep -c "Layer1Disclosures\|DisclosureAck\|disclosures:" layer4/context.py` → 0 |
| table retained | `init_db.py` | `grep "CREATE TABLE IF NOT EXISTS disclosure_acknowledgments" init_db.py` (present) |
| route writers retained | `routes/locales.py`, `routes/provider_auth.py` | `INSERT INTO disclosure_acknowledgments` present |
| regression test | `tests/test_layer1_builder.py` | `def test_disclosures_dropped_from_payload`; SELECT-count assert `== 26` |
| suite green | `tests/` | `python -m pytest tests/ -q` → 3989 passed / 30 skipped |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (the sign-up/onboarding arc entry has D1-D5 + the Phase-1 progress)
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

**PR state:** PR [#1073](https://github.com/ahorn885/exercise/pull/1073) opened on Andy's go; **auto-merge armed (merge commit)** — self-merges once the required checks pass (`Python unit suite (stubbed)` / `JS harness (jsdom)` / `Layer 0 integrity gate`). The bookkeeping commits ride the same branch/PR as the code. Session subscribed to PR #1073 activity (CI / review comments).
