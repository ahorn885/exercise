# V2 Build Prep — Session Handoff

**Date:** 2026-05-06
**Predecessor:** `Phase_Load_Allocation_Handoff_v9.md` (Phase Load Allocation closed)
**Outgoing state:** Layer 0 ETL build kicked off in a separate coding session. Awaiting results.
**Next chat starts with:** ETL build report pasted in. Review warnings, decide what (if anything) needs spec follow-up, then resume v2 onboarding spec drafting (§I–§L plus Groups 2–3).

---

## TL;DR for the new chat

The Phase Load Allocation work is fully closed. The existing AIDSTATION app is going to be replaced by a v2 rebuild — wipe-and-rebuild rather than incremental migration. The user has approved Postgres-only (dropping SQLite parity), same Neon instance, same `aidstation` repo with a new `etl/` directory.

Two prep tasks were sent over to a separate coding session:
1. **`rx_engine_spec.md`** — already returned, saved into the project. Captures the strength progression algorithm from the existing app's `calculations.py` + `rx_engine.py` so it can be re-implemented during v2 build.
2. **Layer 0 ETL build** — currently in flight in another session. Builds the platform-level reference data into a new `layer0` schema in the existing Neon Postgres. Implements the spec in `Layer0_ETL_Spec_v2.md`.

When the ETL results come back, paste them into the new chat. Most likely artifact: a report file (`etl/reports/run-1.0-*.md`) plus possibly schema confirmation queries. Review warnings, surface anything that needs spec follow-up, then move on.

---

## What shipped this session

1. **`Sports_Framework_v6.xlsx`** — AR taper feasibility patch closed (audit notes added to R2, R3, R5, R6, R18, plus full audit block on R19). Group A audit (A.4–A.7) formal entries written. Phase Load Allocation work fully complete; zero open items remaining in that workstream.
2. **`Phase_Load_Allocation_Audit_Log.md`** — A.4–A.7 entries replaced the `[Pending verification]` stubs. AR Taper Feasibility Patch audit section appended.
3. **`Phase_Load_Allocation_Handoff_v9.md`** — closes the Phase Load Allocation workstream.
4. **`rx_engine_spec.md`** — earned domain logic from the existing app captured as a 903-line implementation-ready spec. Returned from a separate coding session, saved into the project.
5. **`Layer0_ETL_Spec_v2.md`** — refreshed from v1 (which was written against `Sports_Framework_v3.xlsx`) to align with v6 data and add three new things:
   - Vocabulary tables (5 new tables from `Vocabulary_Audit_v2.md`: body parts, health condition categories, equipment items, terrain types, sport-specific gear toggles)
   - Sheet 8 (Cross-Sport Properties) coverage
   - Phase Load Allocation schema corrected from single-percentage columns to low/high band columns plus notes
6. **Over-there prompt** — paste-ready instructions for the Layer 0 ETL build, sent to a separate coding session.

---

## Decisions locked this session

These should not be revisited in the new chat unless something concrete forces a change.

1. **The existing AIDSTATION app gets wiped and rebuilt as v2**, not incrementally migrated. Andy's existing user data is acceptable to lose (he keeps the source-of-truth elsewhere — `plan_wk1-4.md`, `workout_log.md`, `AR_Merged_Database.xlsx`).
2. **Postgres-only.** SQLite/TrueNAS dual-backend is dropped at v2 cutover. New code (the Layer 0 ETL) is Postgres-only from day one.
3. **Layer 0 lives in the existing Neon Postgres instance, in a separate `layer0` schema.** Not a new database. Existing app's `public` schema stays untouched until cutover.
4. **The Layer 0 ETL code lives in the existing `aidstation` repo** under a new `etl/` directory. Not a new repo.
5. **Layered plan generation is the v2 architecture.** The existing app's single-shot `/coaching/generate` flow is throwaway. The layered prompt architecture (Layer 0 reference → Layer 1 athlete → Layer 2+ plans) with surgical cache invalidation is the go-forward.
6. **Security work is closed.** The 7-PR security stack from `HANDOFF_v2.md` (PRs #11–#17) covers SECRET_KEY, CSRF, rate limiting, cookie hardening, security headers, CSP nonces, zxcvbn passwords, API tokens. v2 will inherit these patterns from day one.

---

## Existing app state (for context)

The user runs an app called AIDSTATION at `aidstation-pro.vercel.app` (Neon Postgres) and a TrueNAS Docker mirror (SQLite). It's their personal training app. See `DATABASE.md` and `HANDOFF.md` (uploaded to project) for full architecture.

What the v2 rebuild keeps from the existing app:
- The earned domain logic from `calculations.py` + `rx_engine.py` (captured in `rx_engine_spec.md`)
- Auth/admin/security patterns from the seven-PR security stack
- The `api_tokens` design (SHA-256 hashing, last_used_at, soft-revoke)
- The `admin_audit` design (append-only, FK-less target_user_id)
- Flask + Jinja templates **TBD** — frontend decision deferred

What v2 throws away:
- The flat relational schema (the existing schema doesn't support layered/JSONB/versioned storage)
- The single-shot plan generation pipeline
- Locale model with 4 enum slots (replaced with city-tagged locales)
- Garmin OAuth as a single-purpose table (replaced with generalized Connected Services)
- All existing user data

---

## What's pending — over there

**Layer 0 ETL build** — in flight in a separate coding session. The over-there prompt covered:
- Schema creation (16 tables in `layer0` namespace)
- Vocabulary transforms module (Vocab Audit §5 cleanup rules)
- Three extractors (Sports Framework, Exercise DB, Vocabulary doc)
- Run orchestrator (`python -m etl.layer0.run --version-tag VERSION`)
- Validation passes (sum-to-100, vocab alignment)
- Tests for parsers and transforms

Expected deliverable: a working ETL CLI plus a report file at `etl/reports/run-1.0-*.md` showing row counts and validation warnings.

**When the new chat opens with the ETL results pasted in, do this:**

1. **Read the report file first.** Confirm row counts roughly match expectations:
   - 50 body parts, 21 health condition categories, ~143 equipment items, 15 terrain types, 12 gear toggles
   - 39 sports, 33 disciplines, 72 sport-discipline map rows
   - Phase Load Allocation: ~193 rows
   - Discipline Pairing Matrix: should produce some rows from Sheet 4 (D-001 through D-017 pairs) plus fallback rows from Sheet 3 col 7
   - Cross-Sport Properties: 1 row (LIT_RATIO_001)
   - 247 exercises, ~1068 sport-exercise mappings
2. **Triage validation warnings.** Two validators will have run:
   - **sum_to_100**: should be 33 PASS, 0 WARN. Phase Load Allocation was thoroughly audited; warnings here would be a real concern.
   - **vocab_alignment**: warnings expected on first run. Each warning indicates an exercise with a `contraindicated_part` that doesn't match the canonical body part vocabulary, OR a sport name in the Sport-Exercise Map that doesn't bridge to the Sports Framework. Decide per-warning: fix the source data, fix the canonical vocab, or accept as edge case.
3. **Surface anything that needs spec follow-up.** The over-there prompt explicitly told them to document ambiguities in the report rather than guessing. Anything documented there is a candidate for a spec patch.
4. **Once the ETL is clean (or warnings are triaged), the over-there work is done.** Move to spec drafting.

---

## What's pending — here

The v2 onboarding spec is drafted §A through §H. Pending sections, with scope already defined:

- **§I — Lifestyle & Recovery** (sleep, stress, life context fields)
- **§J — Locales** (city-tagged geographic locales — replaces the existing app's 4-enum-slot locale model)
- **§K — Locale Schedule** (when athlete is at which locale)
- **§L — Athlete Network** (Solo Training Partners + Race Teammates, optional linked accounts)
- **Group 2 — Account Configuration** (Connected Services, Gym Memberships, Disclosure Records)
- **Group 3 — Plan Management** (Profile Update Triggers, Adherence Drop Spec, Plan Duration, Joint Training)

Source materials in project: `Athlete_Onboarding_Data_Spec_v2.md` (draft), `V2_Handoff_post_open_items.md`, `V2_spec_decisions_handoff`, plus the various batched section files (`Section_B_v2_Batch.md`, `Sections_C_J_v2_Batch.md`, `Sections_GHMN_v2_Batch.md`).

The Adherence Drop spec has its own dedicated handoff: `Adherence_Drop_Spec_v2.md`.

Layer 0 ETL doesn't depend on §I–§L. Spec drafting can resume independently of ETL completion.

---

## Files to reference in project

**Phase Load Allocation workstream (closed):**
- `Sports_Framework_v6.xlsx` — current canonical sports framework
- `Phase_Load_Allocation_Audit_Log.md` — full audit log, all groups documented
- `Phase_Load_Allocation_Handoff_v9.md` — workstream-closing handoff

**Layer 0 ETL workstream (in flight):**
- `Layer0_ETL_Spec_v2.md` — the spec the ETL is built against
- `Sports_Framework_v6.xlsx`, `AR_Exercise_Database_v17.xlsx`, `Vocabulary_Audit_v2.md` — source data

**Existing app context:**
- `DATABASE.md` — full schema reference
- `HANDOFF.md` — operator state pre-security stack
- `HANDOFF_v2.md` — operator state post-security stack (current)
- `rx_engine_spec.md` — preserved domain logic

**v2 onboarding spec drafts:**
- `Athlete_Onboarding_Data_Spec_v2.md` — primary draft, §A–§H complete
- `V2_Handoff_post_open_items.md` — most recent open-items resolution
- Various `Section_*_v2_Batch.md` files

---

## Versioning rule (carry-forward)

- **Sports Framework working file:** `Sports_Framework_v6.xlsx`. Next save → `v7`.
- **Phase Load Allocation handoff:** `Phase_Load_Allocation_Handoff_v9.md` is current. Next save → `v10` (but this workstream is closed; unlikely to update).
- **Layer 0 ETL spec:** `Layer0_ETL_Spec_v2.md` is current. Next save → `v3`.
- **Athlete Onboarding spec:** `Athlete_Onboarding_Data_Spec_v2.md` is current.

Always increment version numbers; never overwrite.

---

## Risks / things to watch

- **The Layer 0 ETL is being built against a spec the ETL session reads top-to-bottom.** If the source xlsx has edge cases the spec didn't anticipate, the over-there session was instructed to document them in the report rather than guess. Expect at least a few of these.
- **Vocabulary alignment is the most likely warning source.** The exercise DB was created before the canonical vocabulary was locked. Some `contraindicated_parts` entries probably don't match the canonical body parts list. Triaging these may produce small changes to either the vocabulary doc or the source xlsx.
- **The Sheet 4 / Sheet 3 col 7 pairing fallback is the most complex parsing in the ETL.** If the over-there session struggled here, expect questions or partial output for D-018+.
- **Don't accept ETL results without reading the report.** The validators are non-blocking by design. The ETL completes regardless of warnings. Real correctness comes from triaging the report.
- **Don't restart any of the closed workstreams** (Phase Load Allocation, security PRs, rx_engine spec, Layer 0 ETL spec) without a concrete reason. They're closed. The temptation to re-audit is real but unproductive.

---

## What good looks like for the next chat

- ETL report reviewed. Warnings triaged. Anything that needs a spec patch is captured as a discrete TODO.
- If the ETL needs a re-run (e.g., spec patch applied, vocab fix in source), that's a small over-there task — write a minimal follow-up prompt for the same session.
- Spec drafting resumes on §I or whichever pending section the user prioritizes.
- No new structural decisions — the architecture is locked.
