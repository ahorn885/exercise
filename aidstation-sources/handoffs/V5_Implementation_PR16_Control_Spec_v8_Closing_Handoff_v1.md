# V5 Implementation PR16 — Control_Spec v7 → v8 SQLite Cleanup — Closing Handoff

**Session:** PR15 §5.1 Option B / PR14 §5.3 deferred cleanup. Andy 2026-05-16: from a candidate menu after PR15 closed (PR15 already merged at session start as PR #51), Andy picked "Control_Spec_v7 → v8 cleanup." Small doc-only spec bump: copy v7 → v8, retroactively flag v6's "removed during Phase 5" SQLite-coupling narrative as superseded by PR13's standalone D-54 closure, bump CLAUDE.md pointer, bump backlog v28 → v29.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Implementation_PR15_D61_Profile_Tab_Edit_Closing_Handoff_v1.md` (PR15 D-61 profile-tab schedule edit, merged: `9a08c58` / PR #51).
**Branch:** `claude/profile-tab-edit-closing-FHeNB` (per-session branch off post-PR15 `main`; the branch name predates this session's pivot from PR15 verification to the Option B cleanup — Andy chose the option after the session started so the branch name reflects the original session intent, not this work's content).
**Status:** 🟢 Spec + doc bookkeeping committed to feature branch; 🟡 push + PR pending Andy's request. No §5.0 pre-deploy verification owed — PR16 ships no code.
**Time-on-task:** Single chat (after Rule #9 reconciliation of PR15). Files this turn: **4 substantive** (1 spec + 3 doc bookkeeping). Under the 5-file ceiling. Rule #9 + Rule #10 verifications both clean.

---

## 1. Session-start verification (Rule #9)

Verified PR15 state before doing any new work. PR15 had already merged (PR #51, commits `b09890f` code + `8bdf7be` bookkeeping). **No drift between PR15 handoff narrative and on-disk state.**

| Claim | Anchor | Result |
|---|---|---|
| PR15 merged: 4 code files + 3 doc bookkeeping all on main | `git log --oneline` shows `9a08c58 Merge pull request #51` + `8bdf7be PR15: doc bookkeeping` + `b09890f PR15: D-61 profile-tab schedule edit` | ✅ Verified |
| `templates/onboarding/_schedule_form.html` exists (253 lines, ~10KB) | `wc -l` + `ls -la` | ✅ Verified |
| `templates/onboarding/schedule.html` slimmed to ~51 lines (handoff claimed ~53, 2-line difference) | `wc -l` → 51 | ✅ Verified (close enough) |
| `routes/profile.py` has `save_schedule()` route + the 6 new athlete imports | `grep` | ✅ Verified (handoff narrative accurate against on-disk) |
| `Project_Backlog_v28.md` exists; PR15 narrative on line 5 | `head -5` | ✅ Verified |
| `aidstation-sources/CLAUDE.md` backlog pointer reads v28; Architecture pointer reads `Control_Spec_v7.md`; last-shipped narrative leads with PR15 | `grep` | ✅ Verified |
| Current branch `claude/profile-tab-edit-closing-FHeNB` clean; working tree clean; tracks origin | `git status` + `git branch --show-current` | ✅ Verified |
| Control_Spec_v7.md SQLite ref count | `grep -c -i sqlite Control_Spec_v7.md` → 1 ref on line 25 (in `### What changed in v6 vs v5` block, item #7) | ✅ Verified (PR15 handoff §5.1 Option B estimated "~5 deployment paragraphs"; actual is 1) |

No drift. PR15 closed cleanly; PR16 executes the Option B deferred cleanup.

**Scope estimate correction:** PR15 §5.1 Option B narrative said "edit ~5 deployment paragraphs to drop the dual-backend framing." On-disk there is exactly 1 SQLite reference in Control_Spec_v7.md (line 25). The "~5" estimate was high; the actual cleanup is narrower than the handoff anticipated.

---

## 2. Files shipped this turn

All on branch `claude/profile-tab-edit-closing-FHeNB`. Push + PR pending after commit.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Control_Spec_v8.md` | New (copy of v7 + 2 surgical edits — version header + new "What changed in v8 vs v7" section) | (a) Header line 3 v7 → v8 with new closure narrative ("post-PR13 SQLite + TrueNAS retirement; retroactive cleanup of v6's 'removed during Phase 5' SQLite-coupling narrative; §9 doc map staleness explicitly flagged with Rule #12 resolve-to-highest-N reminder; no body changes to §§1–8 or §§10–11"). Full closure-date chain preserved (v7 closed 2026-05-14; v6 closed 2026-05-13; etc.). (b) New `## What changed in v8 vs v7` section inserted before `## What changed in v7 vs v6` with 4 items: (1) SQLite path retired in PR13 (D-54 ✅ Resolved) — supersedes v6 §7's "removed during Phase 5" framing; full cross-reference list (Catalog_Migration_Plan_v3 §5 decision #5 ✅ Resolved; Athlete_Data_Integration_Spec_v5 §2.5 [RETIRED 2026-05-16, PR13]; PR13 + PR14 closing handoffs); explicit "forward-looking force is zero" disclaimer; historical narrative preserved verbatim per Rule #12. (2) TrueNAS Docker retired in PR13 (D-65 ✅ Resolved) — flagged for audit-trail completeness; lists the 4 deleted deploy artifacts. (3) §9 doc-map staleness flagged with explicit Rule #12 resolve-to-highest-N reminder + enumerated list of cross-references that advanced between v7 (2026-05-14) and v8 (2026-05-16): Onboarding v4→v5, Integration v2→v5, Catalog plan v2→v3, Backlog v11→v29, Layer3_3B_Spec ⏳→✅, design-wave specs uncovered (Onboarding_D58/D59/D60/D61, OnDemand_Workout_D63, Plan_Refresh_D64); full §9 sync deferred to next architectural revision per same opportunistic-cleanup framing. (4) No body changes — §§1–8 + §§10–11 byte-identical to v7. |
| 2 | `aidstation-sources/CLAUDE.md` | Edit (3 surgical) | (a) "Architecture: `Control_Spec_v7.md`" → "Architecture: `Control_Spec_v8.md`". (b) "Backlog: `Project_Backlog_v28.md`" → "Backlog: `Project_Backlog_v29.md`". (c) "Current state (as of 2026-05-16)" last-shipped narrative re-headed: PR16 leads (Control_Spec v7 → v8 SQLite cleanup); PR15 demoted to predecessor; PR14 demoted to predecessor's predecessor; PR13 stays in the chain; PR12 falls off (still reachable via PR13's narrative line, mentioned tersely). Header date stays 2026-05-16. |
| 3 | `aidstation-sources/Project_Backlog_v29.md` | New (copy of v28 + 3 surgical edits per PR15 §5.4 mechanical spec) | (a) File-revision header v28 → v29 with PR16 narrative (1 spec + 3 doc bookkeeping; 4 substantive; under-ceiling framing; Catalog plan v3 + Integration v5 + DATABASE.md + Onboarding v5 + Backlog v29 + design-wave §9 staleness enumerated). (b) Prepend v28 entry to predecessor revisions block (trimmed to one line per PR15 handoff §5.4 step 3 verbatim text). (c) No D-row status flips — PR16 is doc-only and the deferred SQLite cleanup wasn't a D-row of its own (tracked as deferred cleanup in PR14 handoff §5.3 + PR15 handoff §5.3). Same pattern as PR14's v26 → v27 bump. D-50 row untouched this revision (no new code, no merge SHA fill-in owed). |
| 4 | `aidstation-sources/handoffs/V5_Implementation_PR16_Control_Spec_v8_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `aidstation-sources/Control_Spec_v7.md` — Rule #12 preserves predecessor verbatim.
- `aidstation-sources/Catalog_Migration_Plan_v3.md` — already up to date (PR14 shipped v3 with SQLite decoupling).
- `aidstation-sources/Athlete_Data_Integration_Spec_v5.md` — already up to date (PR14 shipped v5 with §2.5 retirement marker).
- `aidstation-sources/DATABASE.md` (the thin redirect) + root `DATABASE.md` — already handled in PR14.
- `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` — referenced in §9 staleness narrative but not edited this PR (full §9 sync deferred).
- `aidstation-sources/Layer3_3B_Spec.md` — referenced in §9 staleness narrative but not edited.
- Design-wave specs (`Onboarding_D58/D59/D60/D61_Design_v1.md`, `OnDemand_Workout_D63_Design_v1.md`, `Plan_Refresh_D64_Design_v1.md`) — referenced in §9 staleness narrative but not edited.
- `PR_Verification_Status.md` — PR16 ships no code; the 39 carry-forward §5.0 steps from PR12 + PR13 + PR15 are unchanged. PR15's 1 manual step (profile-tab schedule round-trip) carries forward.
- Code files — none touched. Doc-only PR.
- Tests directory — none exists; same framing as PR1–PR15.

---

## 3. What landed

### 3.1 Control_Spec v7 → v8 SQLite cleanup

Single change: a new `## What changed in v8 vs v7` section inserted at the top of the historical-changes block (before `## What changed in v7 vs v6`), per Rule #12's "predecessor sections preserved verbatim" convention. The new section has 4 items:

1. **SQLite path retired in PR13 — supersedes v6 §7's "removed during Phase 5" framing.** The v6→v5 change-narrative item #7 (line 25) characterised the dual-backend collapse as "removed during Phase 5 of the catalog migration." That coupling was broken by PR13, which retired the SQLite path as a standalone stack-cleanup PR independent of Phase 5. PR14 cleaned up the doc-side consequences (Catalog_Migration_Plan v3 §1 + §5; Athlete_Data_Integration_Spec v5 §2.5 [RETIRED] marker). Control_Spec was deferred to "next architectural revision" — PR16 executes that deferred cleanup opportunistically.

2. **TrueNAS Docker deployment retired in PR13 (D-65 ✅ Resolved).** Not referenced in v7's body. Flagged here for audit-trail completeness — a future reader scanning Control_Spec for deployment-context references should know that the TrueNAS / Docker path (`Dockerfile`, `docker-compose.yml`, `deploy/truenas_setup.sh`, `deploy/update.sh`) was retired in PR13 alongside SQLite. Vercel is the production deployment target.

3. **§9 doc-map snapshot is stale; cross-references resolve to highest-N at use time (Rule #12).** Per the top-of-§9 framing in v7, "Cross-references in this map use logical names without file-revision suffix; resolve to the highest-N version present in project knowledge." So the snapshot version pins are not load-bearing — readers should resolve via directory listing. For the record, the cross-references that advanced between v7 (2026-05-14) and v8 (2026-05-16):
   - `Athlete_Onboarding_Data_Spec` v4 → v5 (consolidates D-58 + D-59 + D-60 + D-61)
   - `Athlete_Data_Integration_Spec` v2 → v5 (§2.5 SQLite freeze flagged Retired)
   - `Catalog_Migration_Plan` v2 → v3 (SQLite retirement decoupled from §1/§5)
   - `Project_Backlog` v11 → v29 (rolling tracker advanced through PR1–PR16)
   - `Layer3_3B_Spec` ⏳ → ✅ shipped 2026-05-14 (goal-timeline viability + periodization shape; v7 listed it as ⏳ "next forward move")
   - New design-wave specs landed under Cross-cutting category but not currently listed in §9: `Onboarding_D58_Design_v1`, `Onboarding_D59_Design_v1`, `Onboarding_D60_Design_v1`, `Onboarding_D61_Design_v1`, `OnDemand_Workout_D63_Design_v1`, `Plan_Refresh_D64_Design_v1`

   Full §9 sync deferred to next architectural revision — same opportunistic-cleanup framing as the SQLite cleanup itself. Doing both in one PR would over-scope this revision.

4. **No body changes.** §§1–8 + §§10–11 unchanged from v7. The architecture itself (PG-only, single Neon Postgres database with `layer0.*` + `public.*` schemas, Vercel deployment) is unchanged. PR13 stripped the dual-backend implementation; the architecture was always PG-target.

### 3.2 Version-header bump

Header line 3 updated: `**Status:** File-revision v7 — 2026-05-14 (...)` → `**Status:** File-revision v8 — 2026-05-16 (...)`. New closure narrative summarises the v8 delta. Full v7-and-earlier closure-date chain preserved verbatim (v7 closed 2026-05-14; v6 closed 2026-05-13; ... v1 closed 2026-05-11).

### 3.3 CLAUDE.md pointers bumped

`Architecture: Control_Spec_v7.md` → `Control_Spec_v8.md`. `Backlog: Project_Backlog_v28.md` → `Project_Backlog_v29.md`. Last-shipped narrative re-headed with PR16 (Control_Spec cleanup) leading; PR15 demoted to predecessor; PR14 / PR13 retained in the chain; PR12 falls off (still reachable via PR13's mention).

### 3.4 Project_Backlog v28 → v29 bump

Per PR15 handoff §5.4 mechanical instructions:
- (Step 1) Copy v28 → v29.
- (Step 2) File-revision header narrative on line 5 rewritten with PR16 state-flip summary (4-file scope, SQLite cleanup, §9 deferred, no D-row flips).
- (Step 3) v28 entry prepended to predecessor revisions block, verbatim per the PR15 §5.4 spec text.
- (Step 4) No D-row status flips this revision. PR16 is doc-only and the SQLite cleanup deferred-item wasn't a D-row of its own. Mirrors PR14's "no D-row status flips" precedent.
- (Step 5) CLAUDE.md backlog pointer bumped (handled in §3.3 above).

### 3.5 Verification (Rule #10)

```
$ wc -l aidstation-sources/Control_Spec_v7.md aidstation-sources/Control_Spec_v8.md
  454 aidstation-sources/Control_Spec_v7.md
  463 aidstation-sources/Control_Spec_v8.md

$ diff aidstation-sources/Control_Spec_v7.md aidstation-sources/Control_Spec_v8.md | head
3c3
< **Status:** File-revision v7 — 2026-05-14 (...)
---
> **Status:** File-revision v8 — 2026-05-16 (...)
5a6,14
> 
> ---
> 
> ## What changed in v8 vs v7
> 
> 1. **SQLite path retired in PR13 (2026-05-16, D-54 ✅ Resolved) — supersedes v6's "removed during Phase 5" framing.** ...
> 2. **TrueNAS Docker deployment retired in PR13 (D-65 ✅ Resolved).** ...
> 3. **§9 doc map snapshot is stale; cross-references resolve to highest-N at use time (Rule #12).** ...
> 4. **No body changes.** ...
```

2 hunks. Header line bumped + new section inserted before `## What changed in v7 vs v6`. §§1–8 + §§10–11 byte-identical (the diff stops after the inserted section; the body diff is empty).

---

## 4. Session-end verification (Rule #10)

| Claim | Anchor | Result |
|---|---|---|
| `aidstation-sources/Control_Spec_v8.md` exists; 463 lines (v7 + 9); header line 3 reads "v8 — 2026-05-16"; `## What changed in v8 vs v7` section present with 4 items; SQLite item retroactively flags v6 §7; TrueNAS item flags D-65 ✅ Resolved; §9 staleness flagged + enumerated cross-references; no-body-changes item closes the section | `wc -l` + `grep` + `head -30` | ✅ Verified |
| `aidstation-sources/Control_Spec_v8.md` §§1–8 + §§10–11 byte-identical to v7 (the change is purely the new header section + revised version line) | `diff` shows 2 hunks, both in the header region; everything after the inserted section diffs clean | ✅ Verified |
| `aidstation-sources/CLAUDE.md` Architecture pointer reads `Control_Spec_v8.md`; Backlog pointer reads `Project_Backlog_v29.md`; last-shipped narrative leads with PR16 + names this handoff | `grep` | ✅ Verified |
| `aidstation-sources/Project_Backlog_v29.md` exists; file-revision header reads "v29 — 2026-05-16 (**PR16 — Control_Spec v7 → v8 SQLite cleanup**…)"; v28 entry prepended to predecessor revisions; no D-row status flips | `grep` + `head -10` | ✅ Verified |
| `aidstation-sources/handoffs/V5_Implementation_PR16_Control_Spec_v8_Closing_Handoff_v1.md` exists (this file) | `ls` | ✅ Verified |
| 4 substantive files (Control_Spec v8 new, CLAUDE.md edited, backlog v29 new, this handoff new). Doc-only; no Python edits | `git status` shows 4 files; `git diff --name-only` confirms no .py files | ✅ Verified |

No drift between this handoff's narrative and on-disk state.

**Live verification gap:** None — PR16 ships no code, so there's no app-boot or §5.0 step to walk. The PR12 + PR13 + PR15 §5.0 walk-throughs from their respective handoffs remain owed at deploy time; PR16 doesn't add or resolve any.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification owed (this PR)

**None.** PR16 ships no code. The doc edits affect spec-reference material only; nothing in the running app reads from `aidstation-sources/*.md` at runtime.

Carry-forward from PR15 + PR13 + PR12: the 39 owed §5.0 steps in `PR_Verification_Status.md` are unchanged. PR15's 1 manual step (profile-tab schedule round-trip on `/profile?tab=schedule`) also carries forward.

### 5.1 Next-session candidate menu

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read. Note v29 backlog pointer, v8 Control_Spec pointer, PR16-led last-shipped narrative.
2. `aidstation-sources/PR_Verification_Status.md` — 39 §5.0 steps still queued + 1 PR15 step (profile-tab schedule round-trip).
3. `aidstation-sources/handoffs/V5_Implementation_PR16_Control_Spec_v8_Closing_Handoff_v1.md` (this file).
4. `aidstation-sources/handoffs/V5_Implementation_PR15_D61_Profile_Tab_Edit_Closing_Handoff_v1.md` + `V5_Implementation_PR14_Doc_Sweep_Closing_Handoff_v1.md`.
5. `aidstation-sources/Project_Backlog_v29.md`.
6. Domain spec for the picked candidate.

#### Option A — Layer 4 plan-gen spec draft (Recommended next)

Unchanged from PR15 §5.1 Option A + PR14 §5.1 Option A + PR13 handoff. The next big unblock. Gates D-61 JIT swap session-card UI, D-63 on-demand workout, D-64 plan refresh tiers, and the rest of the plan-execution surface. Substantial multi-session work; spec-first.

**Start with:** §1 purpose + §2 boundaries + §3 function signature + §6 payload schema. Resist the temptation to draft the full 14-section template in one session; expect 3–5 sessions to land a draft for Andy's review.

**Domain spec re-read:** `Layer3_3A_Spec.md` + `Layer3_3B_Spec.md` (upstream contract) + `OnDemand_Workout_D63_Design_v1.md` + `Plan_Refresh_D64_Design_v1.md` (downstream consumers gating on Layer 4).

#### Option B — Control_Spec v8 §9 full doc-map sync

The §9 doc-map staleness PR16 surfaced but didn't fix. Single-session doc PR: bump §9 cross-cutting + Layer 1 + Layer 3+ entries to current versions (Onboarding v5, Integration v5, Catalog plan v3, Backlog v29, Layer3_3B_Spec ✅, add design-wave specs). Would produce `Control_Spec_v9.md`. Opportunistic; not blocking. Worth doing alongside the next architectural change to Control_Spec (per the original "opportunistic" framing).

#### Option C — Deeper root `DATABASE.md` rewrite

Carry-forward from PR14 §5.1 Option C2 / PR15 §5.1 Option C. ~50 historical SQLite refs in column-type tables + `CREATE TABLE` snippets + composite-UNIQUE table-rebuild notes (lines 280+). PR14's inline `[STALE]` markers + strengthened top-of-file note carry the load for now. Single-session doc PR.

#### Other PR15 §5.1 carry-forwards (unchanged)

- D-60 closeout (dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure) — premature at N=1.
- §J.3 sport-specific gear toggle UI — needs design re-read.
- F (Polar refresh-on-401), H (provider expansion), D2c (bulk apply), E-telemetry (nudge tracking), D-62 (webhook retention prune).

### 5.2 Recommended sequence (revised post-PR16)

1. **Layer 4 spec draft (Option A).** Substantial; 3–5 sessions. Gates D-61 JIT swap, D-63, D-64.
2. **Control_Spec v8 § 9 doc-map sync (Option B).** Opportunistic; small. Could fold into the next Control_Spec architectural change instead of as a standalone PR.
3. **Deeper DATABASE.md rewrite (Option C).** Opportunistic.
4. **D-63 + D-64 implementation** — once Layer 4 spec stabilizes.
5. **D-61 JIT swap session-card UI** — once Layer 4 lands in code.
6. **D-60 closeout + §J.3 toggles UI** — when cohort > 1.
7. **F / H / D2c / E-telemetry / D-62** — opportunistic.

### 5.3 Standing items not on the critical path (carried from PR15 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged (references v3 plan).
- **D-54 SQLite backend deprecation** — ✅ Resolved (PR13).
- **D-55 Garmin onto `provider_auth`** — paused.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — unchanged.
- **§J.3 sport-specific gear toggle UI** — unchanged.
- **D-60 dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure** — unchanged.
- **D-61 JIT swap session-card UI** — Layer-4-gated.
- **D-61 profile-tab edit surface** — ✅ Resolved (PR15).
- **D-63 on-demand workout** — Layer-4-gated.
- **D-64 plan refresh tiers** — Layer-4-gated.
- **D-65 TrueNAS Docker decommission** — ✅ Resolved (PR13).
- **NL intent parser prompt body design** (D-64) — deferred.
- **Layer 4 single-session synthesis prompt body design** (D-63) — folds into Layer 4 work.
- **Root DATABASE.md deep-section rewrite** — still owed; carry-forward.
- **Control_Spec_v7 deployment-context paragraphs** — ✅ Resolved (PR16, this revision — though scope was narrower than estimated: 1 SQLite reference, not ~5 deployment paragraphs).
- **Control_Spec v8 §9 full doc-map sync** — newly tracked this revision; opportunistic.
- **Open Item #18 — Telemetry on the 14-day connect-provider nudge** — unchanged.

### 5.4 Backlog row update (next PR's first action — conditional)

For the next code PR (e.g., Layer 4 spec draft session 1, or any other work), owed v29 → v30 bump:

1. Copy `aidstation-sources/Project_Backlog_v29.md` → `Project_Backlog_v30.md`.
2. **Replace** the file-revision header narrative on line 5 with the next PR's state-flip summary.
3. **Prepend** to predecessor revisions block (verbatim from current v29 line 5 narrative trimmed to one line):
    ```
    - v29 — 2026-05-16 (PR16 — Control_Spec v7 → v8 SQLite cleanup. New `Control_Spec_v8.md` with a "What changed in v8 vs v7" section retroactively flagging v6's "removed during Phase 5" SQLite-coupling narrative as superseded by PR13's standalone D-54 closure; TrueNAS D-65 ✅ Resolved noted; §9 doc-map staleness flagged with Rule #12 resolve-to-highest-N reminder + enumerated stale cross-refs (Onboarding v4→v5, Integration v2→v5, Catalog plan v2→v3, Backlog v11→v29, Layer3_3B_Spec ⏳→✅, design-wave specs uncovered); full §9 sync deferred to next architectural revision. §§1–8 + §§10–11 body byte-identical to v7. No code; no D-row status flips. Per `V5_Implementation_PR16_Control_Spec_v8_Closing_Handoff_v1.md`)
    ```
4. **Update** D-rows whose status changed by the next PR.
5. **Bump** `CLAUDE.md` backlog pointer v29 → v30 + state date + last-shipped narrative.

**If the next session is Layer 4 spec drafting** (design-only, no code): same shape; D-row statuses don't flip (Layer 4 has no backlog row of its own; D-63/D-64/D-61 JIT swap stay 🟡 until Layer 4 lands in code).

**If the next session is Control_Spec §9 full doc-map sync** (Option B above): would produce `Control_Spec_v9.md`. Mechanical edits: bump §9 Layer 1 (Onboarding v3→v5; demote v4 to historical), Layer 3+ (`Layer3_3B_Spec` ⏳ → ✅, add the spec line with shipping date), Cross-cutting (Control_Spec v8 → v9, Integration v2 → v5 + demote v2/v3/v4 to historical, Catalog plan v2 → v3 + demote v2 to historical, Backlog v11 → v30 + demote ~17 intermediate revisions to a single "v12–v29 — see git history" line to avoid noise; add Onboarding/OnDemand/Plan_Refresh design specs). Add a new "What changed in v9 vs v8" section noting the full §9 sync.

---

## 6. Open items / honest flags

- **Scope estimate was high.** PR15 §5.1 Option B said "edit ~5 deployment paragraphs to drop the dual-backend framing." On-disk there was exactly 1 SQLite reference in Control_Spec_v7.md (line 25 in the §"What changed in v6 vs v5" historical block). The PR16 edit is narrower than the handoff anticipated — the "deployment-context paragraphs" framing in the PR15 handoff was imprecise. Real impact: the cleanup is a single retroactive narrative flag, not 5 paragraphs of rewrites. Honest about this.
- **Rule #12 preserves the historical narrative verbatim.** Per Rule #12, the §"What changed in v6 vs v5" section in v7 (and now v8) is preserved exactly as written. So PR16 doesn't edit the v6→v5 historical narrative directly — instead, the new v8→v7 section retroactively flags it as superseded. This is the right pattern for in-project history; the alternative (editing the historical narrative inline) would violate the "predecessor sections preserved verbatim" convention.
- **§9 doc-map staleness flagged but not fixed.** §9 has multiple stale cross-references (Onboarding v4 → v5, Integration v2 → v5, Catalog plan v2 → v3, Backlog v11 → v29, Layer3_3B_Spec ⏳ → ✅, design-wave specs missing). PR16 surfaces these explicitly in the v8→v7 narrative item #3 but doesn't edit §9 — the rationale is scope discipline (PR16 is "SQLite cleanup," not "§9 sync") and the Rule #12 resolve-to-highest-N convention makes the staleness not load-bearing. A future Option B PR (or the next architectural Control_Spec revision) should sync §9.
- **No code changes; no §5.0 manual verification owed.** Pure doc PR.
- **No tests added.** Same framing as PR1–PR15 — no test suite exists.
- **`PR_Verification_Status.md` not updated.** PR16 adds zero §5.0 steps. The 39 carry-forward steps + PR15's 1 manual step are unchanged.
- **Stop-and-ask trigger #10 ("Any change to `Control_Spec` architecture") not invoked.** This PR doesn't change architecture — it retroactively flags a historical narrative item as superseded by an external event (PR13) that already happened. Architecture itself (PG-only, single Neon Postgres, Vercel deployment, layer pipeline) is unchanged. The new section is doc-cleanup of stale references, not an architectural decision. The trigger would have applied if PR16 (a) altered the layer pipeline, (b) introduced a new HITL gate or standing rule, (c) changed cross-layer contracts, or (d) added a new layer. None apply.
- **Branch name predates session pivot.** The branch `claude/profile-tab-edit-closing-FHeNB` was created for the original session intent (continue PR15 work), then Andy chose Option B post-Rule-#9-reconciliation when PR15 turned out to be already merged. So the branch name doesn't match the PR's content — minor honest flag for the eventual PR description.
- **5-file ceiling not broken.** 4 files (1 spec + 3 doc bookkeeping). Comfortable under-ceiling. PR14 + PR15 both broke the ceiling at 7 files; PR16 is back inside.
- **Project_Backlog_v29 has 426+ lines** (v28 was 425; net +1 from the prepended v28 entry — the header narrative replaces v28's so no net change there). Same observation as PR14/PR15 §6: the backlog is approaching a readability limit. Not actionable in PR16; flag for future-Andy attention.
- **PR12 + PR13 + PR15 §5.0 walk-throughs still owed.** PR16 doesn't move that needle (39 carry-forward + 1 PR15 step).

---

## 7. Gut check

**What this session got right.**

- **Rule #9 reconciliation ran clean.** Verified PR15 state before any new work. PR15 had already merged (PR #51); confirmed all 7 files described in the handoff are on disk; no drift. Clear handoff narrative against clean on-disk state.
- **Scope honest about being narrower than the handoff estimate.** PR15 §5.1 Option B said "~5 deployment paragraphs." On-disk: 1 reference. PR16 calls this out in §1 + §6 instead of inflating the work to match the estimate.
- **Rule #12 preserved correctly.** The historical "What changed in v6 vs v5" section is left verbatim; the v8→v7 section adds the retroactive flag without rewriting v6's content. Right pattern for in-project history.
- **§9 staleness surfaced honestly but not fixed.** Could have over-scoped this PR into a full §9 sync (Onboarding, Layer 3, Cross-cutting all need bumps). Instead, flagged the staleness explicitly in the v8→v7 narrative item #3 + queued it as Option B for the next session. The Rule #12 resolve-to-highest-N convention carries the load. Honest about deferred work.
- **Under the 5-file ceiling.** 4 files; comfortable. PR14 + PR15 both broke ceiling; PR16 is back inside.
- **D-row tracking conservatively honest.** No D-row status flips this revision (mirrors PR14's precedent for deferred-cleanup PRs that don't have a D-row of their own).
- **Mechanically-applicable §5.4 followed.** The v28 → v29 bump followed PR15's spec verbatim, including the trimmed v28 predecessor line text.

**Risks.**

- **Future readers might miss the v8→v7 retroactive flag.** The v6→v5 narrative item #7 is still present (verbatim per Rule #12) and reads as authoritative. The v8 section adds context but a reader skimming v7's historical-change section linearly might see item #7 first and accept it. Mitigation: the new v8 section is at the *top* of the historical-changes block (before v7→v6, v6→v5, etc.), so anyone reading linearly hits the retroactive flag first. The v8 section explicitly says "any forward-looking reading of v7 §"What changed in v6 vs v5" item #7 should defer to the v8→v7 narrative here."
- **§9 doc-map full sync deferred indefinitely.** Same opportunistic-cleanup framing as the SQLite cleanup itself — owed when Control_Spec gets its next architectural revision. If no architectural revision happens for a while, §9 staleness accumulates. The Rule #12 resolve-to-highest-N convention handles cross-reference correctness but readers using §9 as a quick "what specs exist" overview will see stale information. Mitigation: the v8→v7 section explicitly enumerates the stale cross-references so a future reader has the delta in one place.
- **Single SQLite reference vs handoff's "~5 paragraphs" estimate.** Honest flag in §6 — but a reviewer reading PR15's handoff first then this one might be briefly confused. The narrative correction in PR16 §1 + §6 + this gut-check is the right move; nothing to fix.
- **Doc-only PR = doc-only verification.** No app-boot smoke test possible (nothing in the running app reads `aidstation-sources/*.md`). Verification is `grep` + `wc -l` + `diff` only. Same risk as PR14.

**What might be missing.**

- **§9 full sync.** Owed; deferred to next opportunity. Option B for next session.
- **`Onboarding_*_Design_v1.md` cleanup.** Each design spec might have stale references to Integration v2 or v4. The §2.5 retirement marker in v5 makes those self-resolving, but a cleanup pass per design doc could be done. Not chased per PR15 §6.
- **`Onboarding_D58/D59/D60/D61_Design_v1` not added to §9.** Flagged in v8→v7 item #3 but not fixed. Same scope-discipline rationale.

**Best argument against this PR's scope.**

A reviewer could fairly argue that this PR is over-scoped for what it actually changes (1 retroactive flag on a historical narrative item). Two argument shapes:

1. **"This is one paragraph of meta-commentary on a historical narrative item. Why does it need a new file version + a new backlog version + a closing handoff?"** Counter: Rule #12 mandates version bumps for material content changes. Whether 1 line or 10, a content edit to a spec doc triggers the version bump. The backlog + handoff are required overhead for tracking the change. Alternative: roll this into the next substantive Control_Spec revision and don't bump separately — but that strategy was tried (PR14 explicitly skipped Control_Spec for that reason) and the deferred-cleanup carry-forward accumulated; Andy chose to clear it now.

2. **"You should have done the full §9 doc-map sync since you're bumping the spec anyway."** Counter: the SQLite cleanup and the §9 sync are independent concerns with different cognitive loads. The SQLite cleanup is a 1-line retroactive flag; the §9 sync touches ~20 lines across 4 sections (Layer 1, Layer 3+, Cross-cutting, Architecture predecessors) with demote-to-historical work for ~5 spec families. Bundling them would mean a v8 PR that's structurally about "§9 sync" with "SQLite flag" as a sidecar — which loses the focused-narrative discipline that PR14, PR15, and PR16 have all maintained. The Rule #12 resolve-to-highest-N convention means §9 staleness doesn't bleed into correctness; deferring is the right call.

Counter to the counter: if §9 staleness accumulates forever (no architectural revision happens), the deferred-§9-sync becomes a different kind of liability. PR16 explicitly flags this in §6 so future-Andy can decide when to spend the session.

Net: PR16 is a narrow, focused cleanup of a deferred carry-forward. The diff is small but structurally large (Rule #12 file-copy inflation), and the honest framing in §1 + §6 + §7 prevents the "this is bigger than it looks" misreading. Acceptable tradeoff.

---

## 8. Forward pointers

- **Next session:** Layer 4 plan-gen spec draft (Option A in §5.1) — the next big unblock; gates D-61 JIT swap, D-63, D-64. Substantial multi-session work; spec-first. Start with §1 purpose + §2 boundaries + §3 function signature + §6 payload schema.
- **Following next session:** continue Layer 4 spec drafting (sessions 2–5).
- **Before next code lands:** PR12 + PR13 + PR15 §5.0 walk-throughs at deploy time. PR16 adds 0 manual steps.
- **First action of next session:** Read `aidstation-sources/CLAUDE.md` fully (Rule #13 — note v29 backlog pointer + v8 Control_Spec pointer + PR16-led last-shipped narrative). Then Rule #9 reconciliation: confirm `aidstation-sources/Control_Spec_v8.md` exists with the new `## What changed in v8 vs v7` section; confirm `aidstation-sources/Project_Backlog_v29.md` exists with PR16 header narrative + v28 prepended to predecessors; confirm `CLAUDE.md` pointers read v8 + v29. Then read `Layer3_3A_Spec.md` + `Layer3_3B_Spec.md` for the Layer 4 upstream contract + `OnDemand_Workout_D63_Design_v1.md` + `Plan_Refresh_D64_Design_v1.md` for the downstream consumers.

**Rules in force, unchanged:**

- #9 session-start verification — fired at the start of this session; clean.
- #10 session-end verification — see §4; clean.
- #11 mechanically-applicable deferred edits — §5.4 spec'd for the v29 → v30 bump on the next code PR.
- #12 numeric version suffixes — Control_Spec now at v8 (was v7 → v8 in PR16); backlog now at v29 (was v28 → v29 in PR16); historical "What changed in v6 vs v5" preserved verbatim per Rule #12 (the new "What changed in v8 vs v7" section retroactively flags it without rewriting it).
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §5.1 forward-pointer reads CLAUDE.md as item 1; §8 first-action explicitly names CLAUDE.md.
- **The 5-file ceiling** — respected this PR (4 files: 1 spec + 3 doc bookkeeping). PR14 + PR15 both broke ceiling at 7; PR16 is back inside.

---

*End of V5 Implementation PR16 closing handoff. Control_Spec v7 → v8 SQLite cleanup (Option B from PR15 §5.1 / deferred cleanup from PR14 §5.3) per Andy's "Option B" pick. Single spec change: new `aidstation-sources/Control_Spec_v8.md` with a "What changed in v8 vs v7" header section (4 items) retroactively flagging v6's "removed during Phase 5" SQLite-coupling narrative as superseded by PR13's standalone D-54 closure; TrueNAS Docker D-65 ✅ Resolved noted; §9 doc-map staleness explicitly flagged with Rule #12 resolve-to-highest-N reminder + enumerated stale cross-refs (Onboarding v4→v5, Integration v2→v5, Catalog plan v2→v3, Backlog v11→v29, Layer3_3B_Spec ⏳→✅ shipped 2026-05-14, design-wave specs uncovered); full §9 sync deferred to next opportunity per same opportunistic-cleanup framing. §§1–8 + §§10–11 body byte-identical to v7. Version header bumped v7 → v8 with full closure-date chain preserved. Scope honest: actual on-disk SQLite reference count was 1 (in §"What changed in v6 vs v5" item #7, line 25), not the "~5 deployment paragraphs" PR15 §5.1 Option B estimated. CLAUDE.md pointers bumped (Architecture v7→v8; Backlog v28→v29; last-shipped narrative re-headed). Backlog v28→v29 bump executed per PR15 §5.4 mechanical spec verbatim. No code; no D-row status flips (deferred cleanup carry-forward isn't a D-row of its own). 4 substantive files; under the 5-file ceiling. Next: Layer 4 plan-gen spec draft (Option A in §5.1) — the next big unblock.*
