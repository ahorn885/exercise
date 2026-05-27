# Backlog migration — doc-tracked backlog → GitHub issues — Closing Handoff

**Session:** Migrated the entire doc-tracked backlog into GitHub issues (epics + sub-issues), froze the `Project_Backlog_vN.md` chain under `archive/backlog/`, and repointed the housekeeping docs + verify script at issues. Process/tooling session — no app code changed.
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_BlockMaxTokens_SchemaViolationFix_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/backlog-stub-discovery-RdtlW` (PR #292)
**Status:** 5 bookkeeping files + 63 file moves + ~90 GitHub issues created. No substantive app-code files (ceiling N/A). PR #292 merged.

---

## 1. Session-start verification (Rule #9)

This session's task was a backlog-tracking migration, not an implementation pass, so the predecessor §8 anchor sweep was not the gate. The predecessor's live state (D-77 block-`max_tokens` fix shipped via PR #195, **re-run verification still owed**) is carried forward intact into issue **#201/#202** — see §6.

**Reconciliation note:** clean. No app code or specs were touched; the predecessor's owed prod re-run remains owed and is now tracked on #201.

---

## 2. Session narrative

The backlog had grown to **62 versioned `Project_Backlog_vN.md` snapshots** plus a churning Notes column — hard to query, easy to drift from code/handoffs. At an `AskUserQuestion` gate Andy chose to **migrate all themes now** (every open `D-NN` → its own issue) and to **archive the backlog doc** (freeze + point canonical docs at issues), rather than a thin index or a single tracking issue.

Execution: four parallel `general-purpose` agents each owned a set of themes and created the epics + sub-issues (the verbose `sub_issue_write` responses were kept out of the main context by delegating). Meanwhile the doc archiving + housekeeping edits ran in the main thread. One label-spelling split (`priority:medium` vs `priority:med`) was normalized to `priority:med` afterward.

**Gotcha discovered:** the GitHub MCP `issue_write` **ignores `state` on create** — every issue opens. "Create-as-closed" (e.g. already-shipped items like #207) needs a follow-up `method=update, state=closed, state_reason=completed`.

---

## 3. File-by-file edits

### 3.1 `archive/backlog/` (new) + 63 file moves
`git mv` of `Project_Backlog.md` + `Project_Backlog_v1.md … v62.md` into `aidstation-sources/archive/backlog/`. New `archive/backlog/README.md` explains the freeze (2026-05-27), the D-NN→issue mapping, and the label scheme; names `Project_Backlog_v62.md` as the last live version.

### 3.2 `CLAUDE.md` (modified)
Working-principles bullet rewritten: **GitHub issues are the single source of truth** for backlog/features/bugs (label taxonomy + preserve `[D-NN]` in titles). Rule #12 "Backlog exception" → "Backlog (historical)": the versioning convention is recorded only to read the frozen archive.

### 3.3 `CURRENT_STATE.md` / `CARRY_FORWARD.md` (modified)
Banners that issues are canonical as of 2026-05-27. `CARRY_FORWARD` now scoped to **live operational carry-state only** (owed deploys, §5.0 walkthrough ledger), not deferred work items.

### 3.4 `scripts/verify-handoff.sh` (modified)
Section [2] rewritten: checks the frozen `archive/backlog/` and warns if a `Project_Backlog*.md` reappears in the source root, instead of reporting a live backlog version.

---

## 4. Code / tests

None — no app code or tests changed this session.

---

## 5. Manual §5.0 verification steps

None. (Doc/tracking change; the live D-77 re-run owed to Andy is tracked on #201/#202 — see §6.)

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move — **START ON #201**

**Epic [#201](https://github.com/ahorn885/exercise/issues/201) — [D-77] Plan-generation reliability & convergence** is the live fire and the agreed next move.

The concrete first step is **[#202](https://github.com/ahorn885/exercise/issues/202) — cone cache-key non-determinism audit** (`priority:high`, `status:in-progress`). Two more non-deterministic cache-key inputs are still un-audited:
- `layer2d/builder.py:567` — `datetime.utcnow().date()` for injury age (confirm it can't reach a sub-day-precision hash input).
- `layer3a/builder.py:403` + `layer3a/integration.py:471` — `datetime.now()` / `as_of or datetime.now()` fallback (confirm `as_of` is always day-anchored, and the fallback can't churn `layer3a_hash`).
- Grep all builders/payloads for `utcnow` / `datetime.now` / `time.time()` / `uuid` / `random` / `NOW()` and trace each to whether it reaches a cache key. Add a determinism regression test per fixed layer.

**Still owed (Andy's hands), gating verification of everything else on #201:** redeploy + re-run the PGE 2026 plan with the new per-layer-hash + per-block HIT/MISS diagnostics (shipped `39a6c55`). The re-run proof is `synthesize_phase: <phase>:w<n> done — … accepted=True` firing and the cone NOT re-running 3A/3B every pass. If a per-layer hash drifts between passes, the `llm_layer4_plan_create_cached` log names the guilty layer — that's the 4th instance for #202.

Sibling sub-issues under #201, in rough order: **#205** per-block budget + block-`max_tokens` (shipped, verifying), **#206** real-LLM smoke parity ("Step 7" — the missing safety net), **#203** week-seam stitcher (Slice 3 — only meaningful once convergence holds; design §14 coherence judgment), **#207** schema_violation hardening (closed/shipped).

### 6.2 Alternative pivots
- High-priority `status:designed` builds ready to start: **#213** Layer 3C/3D/3.5 HITL gate and **#214** `Layer4ShapeInfeasibleError` (epic **#211**). Filter: `label:priority:high label:status:designed`.
- **#251** OAuth-first onboarding (epic **#246**); **#235** catalog `public.*`→`layer0.*` migration (epic **#228**).

### 6.3 Operating notes for next session
1. Rule #13 — first re-read is `CLAUDE.md` (note: backlog is now GitHub issues, not `Project_Backlog`).
2. Read `CURRENT_STATE.md` + `CARRY_FORWARD.md`.
3. **Browse open issues** in `ahorn885/exercise` — filter by `epic`, then by `layer:*` / `priority:*` / `status:*`. The 12 epics are #201, #210, #211, #212, #225, #228, #241, #246, #259, #261, #262, #286.
4. Read this handoff, then `./scripts/verify-handoff.sh` for the anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Migrate all themes now (every open D-NN → its own issue) | Andy | Full visibility over a thin index; ~90 issues acceptable |
| 2 | Archive the backlog doc (freeze + repoint canonical docs) | Andy | Issues are the SSOT; the 62-version chain is frozen history |
| 3 | Explode v1 maintenance/security icebox into individual children (#262) | Andy (per "every item its own child") | Labeled `v1`+`icebox`+`low` so easy to filter out despite the retired track |
| 4 | Normalize `priority:medium` → `priority:med` on 5 issues | Claude | Parallel agents split on spelling; consistent filtering |
| 5 | Start next session on #201 (cone determinism #202 first) | Andy | The live plan-gen non-convergence fire |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| 63 `Project_Backlog*.md` moved to `archive/backlog/`; none left in source root | ✅ `ls` |
| `archive/backlog/README.md` exists | ✅ |
| CLAUDE.md / CURRENT_STATE / CARRY_FORWARD / verify-handoff.sh repointed at issues | ✅ grep |
| ~90 issues created across 12 epics; all sub-issue-linked | ✅ agent maps + `list_issues` |
| PR #292 CI green (Vercel deploy `success`), no review comments | ✅ `get_status` |
| Working tree clean after commit | ✅ git status |

---

## 9. Files shipped this session

**Substantive (0 files):** none (no app code/specs).

**Bookkeeping (5 files + 63 moves):**
1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. `scripts/verify-handoff.sh`
5. `archive/backlog/README.md` (new)
6. 63 × `Project_Backlog*.md` → `archive/backlog/` (moves)
7. this handoff

**GitHub (not files):** ~90 issues across 12 epics in `ahorn885/exercise`; PR #292.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` gained the "tracking moved to GitHub issues" banner and is now scoped to live operational carry-state only. Deferred work items that previously lived there are now issues. The owed D-77 prod re-run is tracked on #201/#202.

---

**End of handoff.**
