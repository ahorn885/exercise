# V5 Implementation PR14 — Doc Sweep — Closing Handoff

**Session:** Doc-cleanup PR. Andy 2026-05-16: "can we do c then b" after the candidate menu was surfaced. Option C is the PR13-deferred doc-sweep follow-on identified in `V5_Implementation_PR13_Closing_Handoff_v1.md` §5.3 — three design specs needed bumps for SQLite-path references that PR13 made obsolete, the deeper sections of root `DATABASE.md` still had ~50 stale SQLite refs, and `aidstation-sources/DATABASE.md` was a stale duplicate. Andy explicitly authorised running into B (D-61 profile-tab edit follow-on) after C; this handoff covers C only, with B teed up as the next session.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Implementation_PR13_Closing_Handoff_v1.md` (PR13 SQLite + TrueNAS retirement + workflow cleanup, all merged: `3232c68`, `35958e1`).
**Branch:** `claude/pr13-handoff-implementation-Kbr81` (per-session branch off post-PR13 `main`; push pending after commit).
**Status:** 🟡 Doc edits committed to feature branch; 🟡 push + PR + merge pending. No §5.0 pre-deploy verification owed — PR14 ships no code.
**Time-on-task:** Single chat (after Rule #9 reconciliation of PR12 + PR13 + workflow cleanup). Files this turn: **7 substantive** (slightly over the 5-file ceiling; honest break, doc-only scope so per-file cognitive load is bounded). Rule #9 + Rule #10 verifications both clean.

---

## 1. Session-start verification (Rule #9)

Verified PR13 + PR12 + workflow-cleanup state before doing any new work. **No drift between handoff narratives and on-disk state.**

| Claim | Anchor | Result |
|---|---|---|
| PR13 merged: `database.py` PG-only, 82 lines; `init_db.py` 1581 lines (was 2621); 0 `_is_postgres` refs in codebase; 4 TrueNAS artifacts deleted | grep + `wc -l` + `ls` | ✅ Verified |
| `.github/workflows/docker-publish.yml` deleted by PR13 follow-up commit `a87a64b` (merged in PR #49 `35958e1`) | `ls .github/workflows/` (directory itself gone since it had no other workflows) | ✅ Verified |
| CLAUDE.md Stack line PG-only + TrueNAS retirement note; D-54 ✅ Resolved line; backlog pointer v26; 2026-05-16 state header | grep | ✅ Verified |
| `Project_Backlog_v26.md` exists; D-54 status ✅ Resolved 2026-05-16 (PR13); D-65 row present ✅ Resolved | grep | ✅ Verified |
| `PR_Verification_Status.md` shows 24 doable-now §5.0 steps + 21 blocked-on-COROS/Polar-creds + 42 done + 4 N/A | wc + grep | ✅ Verified |
| Current branch `claude/pr13-handoff-implementation-Kbr81` even with origin; no in-progress work | `git status` + `git log` | ✅ Verified |

No drift. PR13 closed cleanly; PR14 is a focused doc-only follow-on.

---

## 2. Files shipped this turn

All on branch `claude/pr13-handoff-implementation-Kbr81`. Push pending after commit.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Catalog_Migration_Plan_v3.md` | New (copy of v2 + 4 surgical edits) | (a) Header v2→v3 with v3 narrative. (b) Prepend v2 entry to predecessor revisions (implicit — added new "What changed in v3 vs v2" section, kept "What changed in v2 vs v1" verbatim). (c) Cross-reference bumps: `Control_Spec_v6.md` → `Control_Spec_v7.md`, `Athlete_Data_Integration_Spec_v2.md` → `Athlete_Data_Integration_Spec_v5.md`. (d) §1 out-of-scope line "SQLite backend support — explicitly deprecated as part of this migration (D-54)" rewritten to "retired independently in PR13 (2026-05-16); see D-54 ✅ Resolved. No longer coupled to this plan." (e) §5 decision #5 flipped to ✅ Resolved (PR13). Plan body Phases 1–5 byte-identical to v2 otherwise. Phase 5 retains original scope "drop `public.*` catalogs" — never had a SQLite-removal deliverable embedded in it; the PR13 handoff §3.6 framing that conflated D-54's "during Phase 5" temporal coordination with Phase 5's deliverable is acknowledged inline in the v3 narrative. |
| 2 | `aidstation-sources/Athlete_Data_Integration_Spec_v5.md` | New (copy of v4 + §2.5 retirement marker + new "What changed in v5 vs v4" header section) | (a) Header v4→v5 with v5 narrative. (b) "What changed in v5 vs v4" section added (3 bullets) — keeps the "What changed in v4 vs v3" section + all earlier "What changed" sections verbatim per Rule #12. (c) Source-decisions block adds `V5_Implementation_PR13_Closing_Handoff_v1.md`. (d) Cross-reference for `DATABASE.md` description simplified ("app schema source of truth for `public.*`" → "app schema source of truth"; the `public.*` distinction was a v2-era artefact of the dual-namespace framing). (e) §2.5 section header flagged `[RETIRED 2026-05-16, PR13]`; the body restructured — top paragraph is the retirement marker pointing at PR13 + D-54 ✅ Resolved; underneath, the v3/v4 historical body retained verbatim with "Historical (v3 — v4):" / "Historical implication:" / "Historical documented exception (v4, 2026-05-14):" prefixes preserving the D-50 Phase 1 carve-out narrative for archaeology. All other sections (§1, §2.1–§2.4, §2.6–§2.7, §3, §4, §5, §6, §7, §8, §9, §10, §11, §12) byte-identical to v4. |
| 3 | `aidstation-sources/DATABASE.md` | Full rewrite (1047 lines → 23 lines; -1024) | Collapsed the stale duplicate to a thin redirect. The duplicate had drifted from root by ~200 lines over the v2 design wave (was 1047 vs root 1249) — root had v1-maintenance updates the duplicate never received (e.g. `admin_audit` table + `/admin/audit` page). Re-syncing line-by-line was not worth the effort vs. the ongoing-drift cost. New body points readers to: (a) live source of truth — root `DATABASE.md` + `init_db.py`'s `PG_SCHEMA` + `_PG_MIGRATIONS`; (b) `layer0.*` truth — `Layer0_ETL_Spec_v7.md`; (c) integration truth — `Athlete_Data_Integration_Spec_v5.md` + root `PROVIDERS_SCHEMA.md`. Original v2-design-wave content available in git history pre-PR14 if archaeology needed. |
| 4 | `DATABASE.md` (root) | Edit (3 surgical) | (a) Top-of-file PR13 marker note rewritten + strengthened — explicit pointer to `init_db.py`'s `PG_SCHEMA` + `_PG_MIGRATIONS` as live source of truth; "What does the schema actually look like right now?" → read `init_db.py`; "Why does this column exist?" → search this file + feature handoffs. Calls out that the inline `[STALE — SQLite path retired PR13]` flags below mark which subsections are historical. (b) `### Migration philosophy` subsection prepended with `[STALE — SQLite path retired PR13]` blockquote — drops the "new columns go in both lists" rule, the "don't write SQLite-only syntax" rule, and the dual-syntax framing. Body retained as historical reference. (c) `### Init and seed flow` subsection prepended with `[STALE — SQLite path retired PR13]` blockquote — notes `init_sqlite()` no longer exists, the five-phase shape still describes the PG path. (d) `### Backend-portable upserts` subsection prepended with `[STALE — SQLite path retired PR13]` blockquote — notes the dual-syntax table is historical; use PG forms only. (e) `### Postgres datetime vs SQLite TEXT in templates` subsection prepended with `[STALE — SQLite path retired PR13]` blockquote — notes the `\|string` wrap is now just a routine `datetime → ISO string` conversion (the three template sites still need it). (f) `?` placeholders subsection prose tightened — drops "they'll break the SQLite path"; rephrases as "stay inside the compatibility layer's contract." Full rewrite of the deeper schema-reference table (lines 280+; ~50 historical SQLite refs in column-type tables + `CREATE TABLE` snippets + composite-UNIQUE table-rebuild notes) explicitly deferred to a future doc PR — the inline section markers + strengthened top-of-file note make the staleness loud, and the schema-reference text is read-only documentation that doesn't bleed into code. |
| 5 | `aidstation-sources/CLAUDE.md` | Edit (3 surgical) | (a) "Authoritative current files" — Integration v4 → v5, Catalog plan v2 → v3, backlog v26 → v27. (b) "Current state (as of 2026-05-16)" last-shipped narrative rewritten to lead with PR14 (Catalog plan v3 + Integration spec v5 + DATABASE.md dedupe + root DATABASE.md marker strengthening) with PR13 as predecessor, then PR12. (c) Header date stays 2026-05-16 (same day as PR13). |
| 6 | `aidstation-sources/Project_Backlog_v27.md` | New (copy of v26 + 4 surgical edits per v26 mechanical spec) | (a) File-revision header v26→v27 with PR14 doc-sweep narrative (the 7-file scope, the per-spec deltas, the "no D-row status flips" honesty, the ceiling break framing). (b) Prepend v26 entry (trimmed to one line) to predecessor revisions block. (c) D-50 row description: PR14 entry appended; status cell PR12 + PR13 merge SHA placeholders filled in (`3232c68` for PR #48 combined PR12+PR13 merge; `35958e1` for PR #49 workflow-cleanup follow-on). (d) No D-row status flips — PR14 is doc-only; the doc-sweep items were tracked as deferred cleanup in PR13 handoff §5.3 rather than as their own D-row, so PR14 just executes them without re-tracking. |
| 7 | `aidstation-sources/handoffs/V5_Implementation_PR14_Doc_Sweep_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `Control_Spec_v7.md` — has scattered SQLite references in deployment-context paragraphs. Tracked in PR13 §5.3 as "cleanup when Control_Spec gets its next revision." Bundling here would push PR14 over the ceiling for marginal gain; deferred again.
- Root `DEV_SETUP.md` — already PG-only after PR13.
- Root `HANDOFF.md` — already has the PR13 top-of-file stale-context marker; no further updates owed.
- Layer specs (`Layer0_ETL_Spec_v7.md`, `Layer3_3A_Spec.md`, `Layer3_3B_Spec.md`, `Layer2C_Spec.md`, etc.) — none reference the SQLite path in a way that's now wrong. The "PG-only" framing in the Integration spec was the load-bearing piece; layer specs always assumed PG semantics.
- `Onboarding_D58_Design_v1.md` through `Onboarding_D61_Design_v1.md` + `OnDemand_Workout_D63_Design_v1.md` + `Plan_Refresh_D64_Design_v1.md` — design specs reference the dual-backend framing only in passing references to "PG-only" or "Integration v4 §2.5"; the §2.5 retirement marker in v5 makes those references self-resolving. No content-load-bearing references.
- `Vocabulary_Audit_v3.md`, `rx_engine_spec.md` — domain-specific, no SQLite refs.
- `Layer0_*` handoff files, `D50_Phase1_*` review docs, etc. — historical artifacts; not touched.
- Vercel-specific deploy config (`vercel.json`) — unchanged.
- Tests directory (`tests/`) — none exists; same framing as PR1–PR13.
- Root `DATABASE.md` deep schema-reference sections (lines 280+) — the bulk of the historical SQLite refs live here in column-type tables + dual-`CREATE TABLE` examples. Full rewrite owed but not blocking — inline `[STALE]` markers + strengthened top-of-file note carry the load. Tracked in §5.3.

---

## 3. What landed

### 3.1 Three design specs decoupled from the SQLite path

`Catalog_Migration_Plan_v2.md` → `_v3.md`: §1 out-of-scope dropped the "SQLite backend support — explicitly deprecated as part of this migration (D-54)" coupling and replaced it with "retired independently in PR13 (2026-05-16); see D-54 ✅ Resolved." §5 decision #5 (SQLite backend drop) flipped to ✅ Resolved. The plan's body is otherwise byte-identical to v2 — Phase 5 always was about `public.*` catalog drops, not SQLite removal; D-54's "scheduled during Phase 5" framing was temporal coordination, not a Phase 5 deliverable. v3 honest about that ambiguity.

`Athlete_Data_Integration_Spec_v4.md` → `_v5.md`: §2.5 SQLite freeze flagged `[RETIRED 2026-05-16, PR13]` at the section header; body restructured so the retirement marker leads and the v3/v4 historical body is preserved verbatim underneath with "Historical (v3 — v4):" / "Historical implication:" / "Historical documented exception (v4, 2026-05-14):" prefixes. The D-50 Phase 1 SQLite block carve-out narrative — which mattered for understanding why those 147 lines + 7 ALTERs existed during 2026-05-14 → 2026-05-16 — survives as archaeology. Forward-looking force is zero (the path it froze no longer exists).

### 3.2 `aidstation-sources/DATABASE.md` dedupe

The duplicate had drifted from root by ~200 lines over the v2 design wave. Root had received v1-maintenance updates (e.g. `admin_audit` table) the duplicate never absorbed. Re-syncing line-by-line was a cost without payoff — keeping two copies guarantees future drift, and the duplicate has no v2-design-wave-specific content that isn't either (a) stale (the dual-backend strategy notes) or (b) already migrated to layer specs that consumed it (the multi-user scoping doctrine fed into Integration v4 §2.4 + Layer 3A spec).

Replaced with a thin (23-line) redirect: live source of truth pointers (root `DATABASE.md` + `init_db.py` + `Layer0_ETL_Spec_v7.md` + `Athlete_Data_Integration_Spec_v5.md`), explicit "stale" framing for the v2-design-wave content (available in git history), and a note that any forward-looking equivalent should be re-derived from root rather than rebuilt from this stale text. One source of truth.

### 3.3 Root `DATABASE.md` marker strengthening

The PR13 marker note already flagged "deeper sections still reference the SQLite path." PR14 keeps that framing but strengthens it on two axes:

1. **Top-of-file** — explicit pointer to `init_db.py`'s `PG_SCHEMA` + `_PG_MIGRATIONS` as live source of truth for "what does the schema look like right now." Frames the file's deeper sections as the "why does this exist" reference, not "is this current" reference. Calls out the inline `[STALE]` flags that follow.

2. **Inline subsection markers** — four `[STALE — SQLite path retired PR13]` blockquotes added at the head of:
   - `### Migration philosophy` (the dual-`_SQLITE_MIGRATIONS` / `_PG_MIGRATIONS` framing)
   - `### Init and seed flow` (the `init_sqlite()` vs `init_postgres()` branch description)
   - `### Backend-portable upserts` (the dual-syntax `INSERT OR IGNORE` / `ON CONFLICT` table)
   - `### Postgres datetime vs SQLite TEXT in templates` (the `|string` wrap was a dual-backend hack)

Plus one prose tightening on `### ? placeholders only` (drops "break the SQLite path" → reframes as "stay inside the compatibility layer's contract").

Full rewrite of the deeper schema-reference sections (lines 280+; ~50 historical SQLite refs in column-type tables + `CREATE TABLE` snippets + composite-UNIQUE table-rebuild notes) deferred. Honest tradeoff: those are read-only documentation pages organised by table; they don't bleed into code paths, the column-type SQLite columns are visibly inert when read against the live PG schema, and the inline markers + top-of-file note make the staleness loud enough for human readers. Cleanup owed; not blocking.

### 3.4 Backlog discipline (v26 → v27)

- File-revision header narrative explicit about the ceiling-break (7 substantive files, doc-only scope, per-file cognitive load is low).
- v26 entry prepended to predecessor revisions block (one-line summary of PR13's scope).
- D-50 row description appended with PR14 entry; status cell PR12 + PR13 merge SHA placeholders filled in (`3232c68` PR #48 combined PR12+PR13 merge; `35958e1` PR #49 workflow-cleanup follow-on).
- No D-row status flips — PR14 is doc-only and the doc-sweep items were tracked as deferred cleanup in PR13 handoff §5.3 rather than as their own D-row, so PR14 just executes them without re-tracking. If a future PR wants to elevate "DATABASE.md deep-section rewrite" to its own D-row, that's a discretionary call when the work actually starts.

### 3.5 Verification

`ls aidstation-sources/Catalog_Migration_Plan_v3.md aidstation-sources/Athlete_Data_Integration_Spec_v5.md aidstation-sources/Project_Backlog_v27.md aidstation-sources/handoffs/V5_Implementation_PR14_Doc_Sweep_Closing_Handoff_v1.md` → all present.

`grep "v27\|v5\|v3" aidstation-sources/CLAUDE.md` → all three pointers bumped (Integration v5, Catalog plan v3, backlog v27).

`grep "STALE — SQLite path retired PR13" DATABASE.md | wc -l` → 4 inline subsection markers landed.

`wc -l aidstation-sources/DATABASE.md` → 23 lines (down from 1047; redirect-only).

`diff` of v5 vs v4 (Integration) — single section change (§2.5) + 3-bullet "What changed in v5 vs v4" header section + source-decisions block adds one line. Everything else byte-identical. ✅

`diff` of v3 vs v2 (Catalog plan) — three localised edits (§1 out-of-scope, §5 decision #5, header + new "What changed in v3 vs v2" section + cross-reference version bumps for `Control_Spec` and `Athlete_Data_Integration_Spec`). Phases 1–5 prose byte-identical. ✅

---

## 4. Session-end verification (Rule #10)

| Claim | Anchor | Result |
|---|---|---|
| `Catalog_Migration_Plan_v3.md` exists; header reads "v3" + "Supersedes v2 + v1"; §1 out-of-scope SQLite line rewritten; §5 decision #5 marked ✅ Resolved; "What changed in v3 vs v2" section present; cross-refs bumped to `Control_Spec_v7.md` + `Athlete_Data_Integration_Spec_v5.md` | grep + diff | ✅ Verified |
| `Athlete_Data_Integration_Spec_v5.md` exists; header reads "v5" + "Supersedes v4"; §2.5 header flagged `[RETIRED 2026-05-16, PR13]`; "What changed in v5 vs v4" section present; "Historical (v3 — v4)" prefixes preserved on the §2.5 carve-out paragraphs | grep + diff | ✅ Verified |
| `aidstation-sources/DATABASE.md` is now a thin redirect (23 lines); points at root `DATABASE.md` + `init_db.py` + `Layer0_ETL_Spec_v7.md` + `Athlete_Data_Integration_Spec_v5.md` | wc + grep | ✅ Verified |
| Root `DATABASE.md` top-of-file marker strengthened with "PR13 + PR14" framing; 4 inline `[STALE — SQLite path retired PR13]` blockquotes on Migration philosophy / Init and seed flow / Backend-portable upserts / Postgres datetime vs SQLite TEXT in templates subsections; `?` placeholders prose tightened | grep + read | ✅ Verified |
| `aidstation-sources/CLAUDE.md` backlog pointer reads `Project_Backlog_v27.md`; Integration line reads v5; Catalog plan line reads v3; last-shipped narrative leads with PR14 doc sweep | grep | ✅ Verified |
| `Project_Backlog_v27.md` exists; file-revision header reads "v27 — 2026-05-16 (PR14 — Doc sweep…)"; predecessor v26 entry prepended; D-50 row description has PR14 entry; D-50 status cell has `3232c68` + `35958e1` merge SHAs in place of the `<PR12-merge-pending>` / `<PR13-merge-pending>` placeholders | grep | ✅ Verified |
| 7 substantive files (Catalog plan v3, Integration spec v5, aidstation-sources/DATABASE.md replaced, root DATABASE.md edited, CLAUDE.md edited, backlog v27, this handoff). Doc-only — no code changes; `git status` clean of Python edits | `git diff --stat` | ✅ Verified |
| No code changes (Python files untouched): `git diff --name-only HEAD` shows only the 7 doc files | `git diff --name-only` | ✅ Verified |

No drift between this handoff's narrative and on-disk state.

**Live verification gap:** None — PR14 ships no code, so there's no app-boot or §5.0 step to walk. The PR12 + PR13 §5.0 walk-throughs from their respective handoffs remain owed at merge time; PR14 doesn't change that.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification owed (this PR)

**None.** PR14 ships no code. The doc edits affect human-facing reference material only; nothing in the running app reads from `aidstation-sources/*.md` or root `DATABASE.md` at runtime.

Carry-forward from PR13 + PR12 + PR11 + PR10: the 39 owed §5.0 steps queued in `PR_Verification_Status.md` are unchanged. PR14 doesn't help or hurt that backlog.

### 5.1 Next-session candidate menu

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read. Note v27 backlog pointer, v5 Integration spec line, v3 Catalog plan line, the bumped last-shipped narrative.
2. `aidstation-sources/PR_Verification_Status.md` — 39 §5.0 steps still queued.
3. `aidstation-sources/handoffs/V5_Implementation_PR14_Doc_Sweep_Closing_Handoff_v1.md` (this file).
4. `aidstation-sources/handoffs/V5_Implementation_PR13_Closing_Handoff_v1.md` + `V5_Implementation_PR12_Closing_Handoff_v1.md`.
5. `aidstation-sources/Project_Backlog_v27.md`.
6. Domain spec for the picked candidate.

#### Option B — D-61 profile-tab edit follow-on (Recommended, next-up per Andy's "c then b")

**Domain spec read:** `Onboarding_D61_Design_v1.md` §3.4 + PR12 handoff §3.6 + PR13 handoff §5.1 Option B.

Andy explicitly queued this after C. Scope: surface the v5 §G form (or a slimmer partial-template variant of it) on `/profile?tab=athlete` so athletes can edit per-day windows + the 5 orthogonal-capacity columns without re-visiting `/onboarding/schedule`. Small PR (~3-4 files):

1. **`routes/profile.py`** — extend the `/profile?tab=athlete` POST handler to accept the §G form fields (the 5 orthogonal-capacity columns + the per-day windows submission). Reuse the existing `athlete._parse_schedule_form` parser shape (or extract from `routes/onboarding.py:schedule_save` into a shared helper). The simplest path is to import + call the existing `_parse_schedule_form` from `routes/onboarding.py` directly — no new helper needed.
2. **New partial template `templates/onboarding/_schedule_form.html`** (or `templates/profile/_schedule_partial.html`) — extract the §G form fragment from `templates/onboarding/schedule.html` so both the onboarding step and the profile tab can include it without duplicating markup. The existing `schedule.html` becomes a thin wrapper around the partial; the profile tab `include`s the same partial. CSP-nonce script + form-no-JS-submittable invariants preserved.
3. **`templates/profile/edit.html`** (or whichever template renders the `tab=athlete` view) — `{% include 'onboarding/_schedule_form.html' with context %}` inside the athlete tab; pre-populated from the same `get_athlete_profile` + `get_daily_availability_windows` pair the onboarding GET uses.
4. **`templates/onboarding/schedule.html`** — slimmed down to include the new partial. Step-3b wrapper (step indicator + Save+Continue + Skip-for-now buttons + form `action="/onboarding/schedule"`) wraps the partial.

**Surfaces to check:** the existing `/onboarding/schedule` flow must remain fully functional after the partial extraction (this is the regression risk); the profile-tab form should pre-populate from `daily_availability_windows` + `athlete_profile` capacity columns identically to the onboarding flow; the POST handler on `/profile?tab=athlete` should validate identically (long-session day cross-validation, doubles-feasible second-window gating, etc.).

**Defers:** JIT session-card swap (still Layer-4-gated); per-day cross-validation UX refinement (still owed); travel-day window TZ handling (still owed).

**Estimated effort:** 3-4 files, single session, comfortably at ceiling. Local Flask test_client smoke test before commit (round-trip GET/POST on both routes, regression of the onboarding flow).

#### Option A — Layer 4 plan-gen spec draft

Unchanged from PR13 handoff §5.1 + PR12 handoff §5.1. The next big unblock. Gates D-61 JIT swap, D-63, D-64, plan-execution surface. Substantial multi-session work; spec-first. Start with §1 purpose + §2 boundaries + §3 function signature + §6 payload schema.

**Andy's call whether B-then-A or A-only.** B is the small parallel; A is the big unblock.

#### Option C2 — Deeper DATABASE.md rewrite

If PR14's marker-only approach to the deeper sections is unsatisfying, a follow-on doc PR can rewrite lines 280+ for PG-only. Scope: ~30 table reference blocks, ~20 `CREATE TABLE` examples, the composite-UNIQUE table-rebuild section in Multi-user scoping. Owed as deferred cleanup; not blocking.

#### Other PR13 §5.1 carry-forwards (unchanged)

- D-60 closeout (dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure) — premature at N=1.
- §J.3 sport-specific gear toggle UI — needs design re-read.
- F (Polar refresh-on-401), H (provider expansion), D2c (bulk apply), E-telemetry (nudge tracking), D-62 (webhook retention prune).

### 5.2 Recommended sequence (revised post-PR14)

1. **D-61 profile-tab edit follow-on (Option B).** Per Andy's "c then b" explicit. Small; parallel-safe.
2. **Layer 4 spec draft (Option A).** Substantial; 3-5 sessions.
3. **Deeper DATABASE.md rewrite (Option C2).** Opportunistic.
4. **D-63 + D-64 implementation** — once Layer 4 spec stabilizes.
5. **D-60 closeout + §J.3 toggles UI** — when cohort > 1.
6. **F / H / D2c / E-telemetry / D-62** — opportunistic.

### 5.3 Standing items not on the critical path (carried from PR13 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged (now references v3 plan).
- **D-54 SQLite backend deprecation** — ✅ Resolved (PR13).
- **D-55 Garmin onto `provider_auth`** — paused.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — unchanged.
- **§J.3 sport-specific gear toggle UI** — unchanged.
- **D-60 dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure** — unchanged.
- **D-61 JIT swap session-card UI** — Layer-4-gated.
- **D-61 profile-tab edit surface** — small follow-on, **next session per Andy**.
- **D-63 on-demand workout** — Layer-4-gated.
- **D-64 plan refresh tiers** — Layer-4-gated.
- **D-65 TrueNAS Docker decommission** — ✅ Resolved (PR13).
- **NL intent parser prompt body design** (D-64) — deferred.
- **Layer 4 single-session synthesis prompt body design** (D-63) — folds into Layer 4 work.
- **Root DATABASE.md deep-section rewrite** — still owed; PR14 strengthened markers but didn't rewrite. Tracked as deferred cleanup.
- **Catalog_Migration_Plan §5 Phase 5 scope adjustment** — ✅ Resolved by PR14 (v3 plan honesty about SQLite-coupling decoupling).
- **Integration v4 §2.5 retirement (v5 spec bump)** — ✅ Resolved by PR14 (v5 spec).
- **Control_Spec_v7 deployment-context paragraphs** — still owed; PR14 explicitly skipped it to stay roughly on-ceiling.
- **`aidstation-sources/DATABASE.md` dedupe** — ✅ Resolved by PR14.
- **Open Item #18 — Telemetry on the 14-day connect-provider nudge** — unchanged.

### 5.4 Backlog row update (next PR's first action — conditional)

For the next code PR (e.g., D-61 profile-tab edit follow-on), owed v27 → v28 bump:

1. Copy `aidstation-sources/Project_Backlog_v27.md` → `Project_Backlog_v28.md`.
2. **Replace** the file-revision header narrative on line 5 with the next PR's state-flip summary.
3. **Prepend** to predecessor revisions block (verbatim from current v27 line 5 narrative trimmed to one line):
    ```
    - v27 — 2026-05-16 (PR14 — Doc sweep. Catalog_Migration_Plan v2→v3 (SQLite retirement decoupled from §1/§5); Athlete_Data_Integration_Spec v4→v5 (§2.5 flagged Retired); aidstation-sources/DATABASE.md collapsed to thin redirect; root DATABASE.md PR13 marker strengthened with 4 inline [STALE] flags. No code; no D-row status flips. Per `V5_Implementation_PR14_Doc_Sweep_Closing_Handoff_v1.md`)
    ```
4. **Update** the D-50 row: PR14-merge SHA filled in from git log; next-PR entry appended.
5. **Update** D-rows whose status changed (D-61 likely flips to 🟢 fully shipped if profile-tab editing closes out PR14's Option B).
6. **Bump** `CLAUDE.md` backlog pointer v27 → v28 + state date + last-shipped narrative.

**If the next session is Layer 4 spec drafting** (design-only, no code): same shape; D-row statuses don't flip (Layer 4 has no backlog row of its own; D-63/D-64/D-61 JIT swap stay 🟡 until Layer 4 lands in code).

---

## 6. Open items / honest flags

- **5-file ceiling broken intentionally (7 files).** Doc-only scope so per-file cognitive load is bounded — copy-with-edits + version bumps are mostly mechanical. The substantive cognitive load is on the root `DATABASE.md` marker edits (file #4); everything else is mechanical. Honest tradeoff vs. splitting into two doc PRs: the v3 catalog plan + v5 integration spec + DATABASE.md dedupe are deeply linked (all stem from the same SQLite-path retirement framing), so splitting them would mean two PRs with overlapping rationale text and the same backlog-bump-handoff overhead.
- **Root `DATABASE.md` deep schema-reference sections (lines 280+) not fully rewritten.** ~50 historical SQLite refs survive in the table reference, column-type tables, `CREATE TABLE` examples, and composite-UNIQUE table-rebuild notes. Inline `[STALE]` markers + strengthened top-of-file note make the staleness loud, but a full rewrite is owed. Tracked in §5.3 as deferred cleanup; not blocking.
- **No D-row status flips this revision.** PR14 executes deferred-cleanup items from PR13 handoff §5.3 (which weren't tracked as their own D-row). Honest; not a regression.
- **`Control_Spec_v7.md` still references the dual-backend framing.** PR14 explicitly skipped Control_Spec to stay roughly on-ceiling. The references are in scattered deployment-context paragraphs, not load-bearing; can be cleaned up when Control_Spec gets its next architectural revision.
- **Push + PR + merge pending.** Branch `claude/pr13-handoff-implementation-Kbr81`; PR creation at Andy's request.
- **`aidstation-sources/DATABASE.md`'s history is preserved in git** — anyone needing the original v2-design-wave content (multi-user scoping doctrine, dual-backend strategy notes) can `git show HEAD~1:aidstation-sources/DATABASE.md`. The redirect notes this.
- **`Project_Backlog_v27.md` has 423 lines** (same as v26). The D-50 row description got longer (PR14 entry appended); status cell got shorter (SHAs replace placeholders). Net wash.
- **No tests added.** Doc-only PR; nothing to test inline.
- **PR12 + PR13's §5.0 walk-throughs still owed.** 39 steps queued in `PR_Verification_Status.md` carry forward unchanged; PR14 doesn't add or resolve any.
- **D-50 status cell PR12+PR13 merge SHA fill-in is the v25→v26 mechanical instruction (PR13 handoff §5.4 step 4) executing late.** PR13 handoff said "v26 → v27 bump fills the SHAs"; PR14 is that v26 → v27 bump and the SHAs are filled in. Discipline preserved (the deferred mechanical edit landed in the next revision as specified).

---

## 7. Gut check

**What this session got right.**

- **Rule #9 reconciliation ran clean.** Verified PR12 + PR13 + workflow-cleanup state before touching anything new. No drift surfaced — the handoffs are accurate.
- **Scoped C tight.** Resisted the temptation to bundle Option B (D-61 profile-tab edit, which Andy queued next) into the same PR. C was already 7 files; B is another 3-4. Splitting honours Andy's "c then b" sequencing literally — one focused doc PR + one focused code PR — rather than smuggling them together. Better diff to review, better commit history.
- **DATABASE.md duplicate handled honestly.** Could have spent two hours re-syncing the duplicate's 1047 lines against root's 1249 lines. Instead, called the duplicate stale-by-drift and collapsed it to a redirect. The v2-design-wave content lives in git history if anyone needs archaeology; the present-day content has one source of truth.
- **Inline `[STALE]` markers vs full rewrite.** Honest tradeoff for the deeper DATABASE.md sections — full rewrite would be ~200-400 lines of effort for a read-only documentation page that doesn't bleed into code. The inline markers make the staleness loud at the section level without burning a session on a doc rewrite.
- **Backlog discipline preserved.** D-50 status cell PR12+PR13 merge SHA placeholders filled in (this was the v26→v27 mechanical instruction from PR13 handoff §5.4 step 4 — executed on schedule). No D-row status flips because PR14 doesn't unblock or close anything that has its own row.
- **§2.5 historical context preserved.** The D-50 Phase 1 SQLite-block carve-out narrative (147 lines + 7 ALTERs ratified retroactively, Andy's stop-and-ask call) is preserved under "Historical" prefixes in v5 §2.5. Future sessions reading the spec can still trace why that block existed during the 2026-05-14 → 2026-05-16 window. Forward-looking force zero; historical context preserved.

**Risks.**

- **Inline-marker approach to DATABASE.md deep sections** leaves ~50 stale SQLite refs in human-readable docs. A reader skimming for "how does this table work" will still see SQLite columns + `INSERT OR IGNORE` examples. The 4 subsection-head markers + strengthened top-of-file note do flag this, but a determined-or-rushed reader could skip them. Mitigation: the schema-reference sections are read-only; nothing in the codebase consumes them at runtime.
- **Catalog plan v3's "Phase 5 always was about `public.*` drops" framing** is honest about ambiguity. The v2 plan's §1 out-of-scope coupled SQLite to "this migration"; the v3 narrative breaks that coupling and explains that PR13 handoff §3.6's "Phase 5's 'drop SQLite path' deliverable" was a conflation of D-54's temporal coordination with Phase 5's actual scope. If a future reader takes PR13 handoff §3.6 at face value they might be briefly confused; the v3 plan's "What changed in v3 vs v2" section addresses this directly.
- **`Athlete_Data_Integration_Spec_v5` §2.5 historical body is long.** ~15 lines of preserved historical context for a section flagged Retired. A reader might miss the [RETIRED] marker and read the historical body as current guidance. The "Historical (v3 — v4):" / "Historical implication:" / "Historical documented exception (v4, 2026-05-14):" prefixes are honest about the framing but require the reader to actually parse them.
- **Doc-only PR = doc-only verification.** No app-boot smoke test, no inline `flask.test_client` round-trip. The only "verification" is `grep` + `wc -l` + `diff` against the new files. If a future code session reads the v5 Integration spec and acts on an old "PG-only — SQLite freeze in force" framing that's now stale, they'd notice from the `[RETIRED]` flag and skip the directive — but the framing-drift risk is real.

**What might be missing.**

- **`Control_Spec_v7.md` cleanup.** Skipped this revision; the references are in passing deployment paragraphs, not load-bearing. Owed when Control_Spec gets its next revision.
- **`Onboarding_*_Design_v1.md` cleanup.** Each design spec has at most a one-line reference to "PG-only — Integration v4 §2.5" or similar. After v5 retirement, those references self-resolve (they point at a section that's flagged Retired with forward-pointing context). Not worth chasing per-design-doc.
- **`PROVIDERS_SCHEMA.md` (root)** — referenced from v5 Integration spec; doesn't reference SQLite directly. Skipped.
- **Layer specs cleanup.** Layer 0 + Layer 2 + Layer 3A/3B specs reference the dual-backend framing only in passing if at all. The §2.5 retirement marker in Integration v5 makes those references self-resolving.

**Best argument against this PR's scope.**

A 7-file doc PR is hard to review at scale — the `git diff` for `Project_Backlog_v27.md` alone is ~400 lines (a full file copy + a narrative cell append). The v3 Catalog plan diff is ~334 lines (full copy). The v5 Integration spec diff is ~808 lines (full copy). Total: ~1500 lines of diff for what's structurally a small set of changes. A reviewer skimming the diff stat will see "big PR" and may not engage closely with the actually-substantive edits (4 surgical Catalog plan edits + 1 Integration spec §2.5 marker + 4 DATABASE.md `[STALE]` flags + 3 CLAUDE.md pointer bumps + 1 backlog narrative append).

Counter: Rule #12 requires version bumps via new files (not in-place edits) so the diff inflation is structural, not avoidable. The PR description should clearly list "the substantive edits": 4 surgical points in Catalog plan v3 + 1 section in Integration spec v5 + 4 inline flags in root DATABASE.md + 1 dedupe + 3 CLAUDE.md pointer bumps + 1 backlog narrative append. Reviewers can focus on those 14 substantive edits rather than the file-copy noise.

Counter to the counter: maintaining version-bump discipline does have a cost — both in diff readability and in repo growth (Project_Backlog now has 27 versions; aidstation-sources/ has 15+ "What changed" history blocks across specs). At some point the cost is real. Not actionable in PR14; flag for future-Andy-attention.

Net: PR14 ships a small set of high-leverage doc edits behind a structurally-large diff. The PR description should call out the 14 substantive edits explicitly so reviewers can ignore the version-bump noise. Acceptable tradeoff.

---

## 8. Forward pointers

- **Next session:** D-61 profile-tab edit follow-on (Option B in §5.1) — Andy's explicit "c then b" sequence. Small (3-4 files): extract `templates/onboarding/schedule.html` form fragment into a partial, include it on both `/onboarding/schedule` and `/profile?tab=athlete`, wire `routes/profile.py` to handle the §G POST shape (reuse `_parse_schedule_form` from `routes/onboarding.py`).
- **Following next session:** Layer 4 spec draft (Option A) — substantial multi-session unblock.
- **Before next code lands:** PR12 + PR13 §5.0 walk-throughs (24 steps doable now, ~21 blocked on COROS/Polar credentials). PR14 adds 0 steps. Track at merge time.
- **First action of next session:** Read `aidstation-sources/CLAUDE.md` fully (Rule #13 — note v27 backlog pointer + v5 Integration spec + v3 Catalog plan + PR14-led last-shipped narrative). Then Rule #9 reconciliation: confirm `Catalog_Migration_Plan_v3.md` exists; confirm `Athlete_Data_Integration_Spec_v5.md` exists; confirm `aidstation-sources/DATABASE.md` is the 23-line redirect; confirm root `DATABASE.md` has 4 inline `[STALE]` markers; confirm `Project_Backlog_v27.md` D-50 status cell has the merge SHAs. Then read `Onboarding_D61_Design_v1.md` §3.4 + this handoff §5.1 Option B for the next-session domain spec.

**Rules in force, unchanged:**

- #9 session-start verification — fired at the start of this session; clean.
- #10 session-end verification — see §4; clean.
- #11 mechanically-applicable deferred edits — §5.4 spec'd for the v27 → v28 bump on the next code PR.
- #12 numeric version suffixes — Catalog plan now at v3 (was v2 → v3 in PR14), Integration spec now at v5 (was v4 → v5 in PR14), backlog now at v27 (was v26 → v27 in PR14).
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §5.1 forward-pointer reads CLAUDE.md as item 1; §8 first-action explicitly names CLAUDE.md.
- **The 5-file ceiling** — broken intentionally this PR (7 files, doc-only scope, per-file cognitive load is low). Back in force for the next PR. Recording the break in the backlog + handoff so future sessions don't take it as license to over-ship.

---

*End of V5 Implementation PR14 closing handoff. Doc-only PR closing the PR13-deferred cleanup follow-on: `Catalog_Migration_Plan` v2→v3 (SQLite retirement decoupled from §1 + §5 decision #5 ✅ Resolved); `Athlete_Data_Integration_Spec` v4→v5 (§2.5 SQLite freeze flagged Retired with historical context preserved); `aidstation-sources/DATABASE.md` (stale duplicate, ~200 lines drifted from root) collapsed to thin redirect; root `DATABASE.md` PR13 marker strengthened + 4 inline `[STALE — SQLite path retired PR13]` blockquotes added on Migration philosophy / Init and seed flow / Backend-portable upserts / Postgres datetime vs SQLite TEXT in templates subsections; CLAUDE.md pointers bumped (Integration v5, Catalog plan v3, backlog v27, last-shipped narrative). No code changes; no D-row status flips. PR12 + PR13 merge SHAs (`3232c68`, `35958e1`) filled into D-50 status cell, completing the v26→v27 mechanical instruction from PR13 handoff §5.4. 5-file ceiling broken intentionally (7 files, doc-only, per-file cognitive load is bounded); back in force for next PR. Next: D-61 profile-tab edit follow-on (Option B in §5.1) per Andy's explicit "c then b" sequence.*
