# Housekeeping — Docs→GitHub-Issues Repoint + 4-Tier Next-Steps Framework — Closing Handoff

**Session:** Bookkeeping / process only. Repointed every housekeeping doc at GitHub-issues tracking (removing the old `Project_Backlog_vN.md` workflow references), pruned the deferred-work sections that migrated to issues, consolidated the owed Andy's-hands deploys into one ledger, and recast "next moves" as a 4-tier priority framework. A follow-on pass then professionally reorganized the GitHub issue tracker (label hygiene, backfill, native sub-issue hierarchy, milestones) — applied via `scripts/issue-cleanup.sh`; see §11. **No app code or specs touched.**
**Date:** 2026-05-28
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_CacheKeyDeterminismAudit_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/friendly-darwin-tEKUp`
**Status:** 0 substantive / 7 bookkeeping files (incl. `scripts/issue-cleanup.sh`) + the GitHub issue-tracker reorganization (§11). Docs + tracker only; the live code state is unchanged from PR #294 (D-77 convergence re-run still owed — Andy's hands).

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor §8 claims (PR #294 — the `last_sync` day-anchor + cone cache-key determinism audit) against on-disk state. This session touches no app code, so the code anchors should still hold — confirmed:

| Claim | Anchor | Result |
|---|---|---|
| `layer3a/integration.py` `as_of` fallback day-anchored (no bare `datetime.now()`) | `grep -n "as_of or datetime" layer3a/integration.py` → line 477 `…utcnow().replace(midnight)` | ✅ |
| `last_sync` field present in the Layer 3A integration cone | `grep -n "last_sync" layer4/context.py` → line 952 | ✅ |
| Guard test `test_last_sync_is_day_anchored` present | `grep -rln test_last_sync_is_day_anchored tests/` → `tests/test_layer3a_integration.py` | ✅ |
| Suite baseline 1802 / 16 (PR #294) | inherited — **not re-run** this session (no app code touched) | ✅ inherited |
| Backlog frozen under `archive/backlog/` | `ls archive/backlog/Project_Backlog_v*.md` | ✅ |

**Reconciliation note:** Clean — all predecessor code anchors present. One *prior* Rule #10 drift was reconciled into the predecessor index while editing `CURRENT_STATE.md` this session: the volume-band pct→hours session (PR #293) shipped its handoff + code but never bumped the `Last shipped session` pointer. It's now recorded in the `CURRENT_STATE.md` predecessor chain. No new drift introduced.

---

## 2. Session narrative

Andy handed three handoffs and four asks. The three handoffs:

1. **`…D77_CacheKeyDeterminismAudit…`** — the main working handoff: the D-77 plan-gen convergence fire. The cache-key non-determinism class (full-precision wall-clock timestamps fold into Layer 4 cache keys → re-mint every resumable pass → 504 money-loop past the immovable 300s Vercel cap). Three drifts fixed before this (`layer1.as_of` + `layer2a.generated_at` = `c4f9160`/#199; `layer2e.computed_at` = #199; **`ProviderStatus.last_sync` = PR #294**, the 3rd that the #202 audit missed). The redeploy + fresh PGE re-run that *confirms* convergence is still owed.
2. **`…BacklogMigration_DocToGitHubIssues…`** — the new tracking method: backlog / icebox / carry-forward *work items* now live as GitHub issues in `ahorn885/exercise` (epics + sub-issues, labelled `layer:*`/`area:*`/`type:*`/`status:*`/`priority:*` + `v1`/`v2`/`icebox`; `[D-NN]` ids preserved in titles). The `Project_Backlog_vN.md` chain (v1–v62) is frozen under `archive/backlog/`.
3. **`…OrphanedCode…`** — the built-but-never-wired sweep (epic #295): a six-cluster audit (one per layer) that found code shipped ahead of its consumers. Four flavors (A starved input / B captured-not-threaded / C emitted-not-consumed / D dead). Children #296–#302 / #306 / #307. The §H.2 goal-fields and several 2E classifications were the prompt; this epic catalogs the rest.

**The four asks (Andy, verbatim intent):**
1. Understand the full context logged across those three handoffs.
2. Update/deprecate **all** housekeeping & carry-forward docs to refer to the GitHub-issues method; remove references to the previous doc-based ways of tracking.
3. Recast "next steps" as a **4-tier priority order**: (1) finish an unresolved in-flight task; (2) resolve go-live / live-functionality blockers; (3) "finish" open-but-not-fully-shipped functions; (4) pursue new functionality.
4. Clean up anything that has to be **re-queried or re-investigated every session** — plug it into this handoff so it isn't re-derived each time.

No /plan-mode gate (bookkeeping). The one judgment call: the planned blind cut of the migrated deferred-work sections was unsafe — two **live** owed deploys were embedded in that narrative — so I harvested them into a new consolidated ledger first (see §3.1).

---

## 3. File-by-file edits

### 3.1 `CARRY_FORWARD.md` (modified, 374 → 222 lines)

- **New `## Owed Andy's-hands deploys (consolidated)` section** (top, after the banner) — the single place a new session finds owed deploys instead of hunting the file. **3 deploys** (full text in §6.3 below): (1) D-77 PGE convergence re-run (#201/#202); (2) L3B-P-2 Slice 2 `previous_attempts` JSONB `init_db.py` (#211/#228); (3) K3 equipment ETL (#228). Deploys (2) and (3) were **harvested out of the deferred narrative before pruning** — they were live, not history.
- **Pruned** the migrated deferred-work sections (old lines 187–374: Phase 3.1/4/5.1/5.2 follow-ons, best-fit re-model leftover slices, D-64 NL-1..8, D-66 rewire, parallel tracks, tabled items) — those are now GitHub issues.
- **Appended `## Deferred work → GitHub issues`** with the 13-epic table.
- Banner (lines 3–8) was already GitHub-issues-canonical; left as-is. The operational ledger (owed deploys + the §5.0 walkthrough) is retained — that's live carry-state, not migrated work items.

### 3.2 `CURRENT_STATE.md` (modified, 236 → 219 lines)

- **Replaced `## Current focus`** with the D-77 code-state paragraph (chain through PR #294) + **`Next moves — 4-tier priority order`** (the issue map, §6.2 here) + a closing pointer to issues/`CARRY_FORWARD.md`.
- **Repointed `## Last shipped session`** (line 11) to this handoff (bookkeeping/process — no app code), then **demoted CacheKeyDeterminismAudit to `### Predecessor`** (full narrative kept).
- Fixed a stale path: `Project_Backlog_v62.md` → `archive/backlog/Project_Backlog_v62.md`.

### 3.3 `README.md` (modified, full rewrite)

- `Control_Spec_v{1..6}` → `v{1..8}`; **removed `Project_Backlog_v{1..11}` from the root tree** (→ frozen under `archive/backlog/`, tracking → issues); `app/ (to be created)` → note that the **live v1 Flask app is at the actual repo root**; `Layer3_3B_Spec` listed as existing (not "to be created"); added `CURRENT_STATE.md` / `CARRY_FORWARD.md` / `archive/` / `prompts/` / `scripts/` tree entries; rewrote "Current state pointers" to be **drift-proof** (resolve `Control_Spec` to highest `_vN`; backlog = GitHub issues; current state = `CURRENT_STATE.md` + `CARRY_FORWARD.md`; latest handoff = named at the top of `CURRENT_STATE.md`).

### 3.4 `scripts/verify-handoff.sh` (modified, header comment only)

- Updated the §[2] header comment from the old "reports latest Project_Backlog version vs. references" to "confirms the backlog is frozen under `archive/backlog/` (tracking in GitHub issues) and warns if a `Project_Backlog*.md` reappears in the source root." The section [2] **code** was already GitHub-issues-aware — only the comment was stale.
- **Note for next session:** this script auto-discovers the latest handoff by grepping `CURRENT_STATE.md` for `handoffs/…\.md` (line 41). The new handoff name must match `CURRENT_STATE.md` line 11 exactly — it does.

### 3.5 `CLAUDE.md` (modified, +1 working principle)

- Added the **`Next-step prioritization (the 4-tier order)`** bullet in "Working principles" (after the GitHub-issues bullet, before "Branch naming"): finish in-flight → resolve go-live/live-functionality blockers (incl. safety gaps) → finish open-but-not-fully-live functions → pursue new functionality. Points at this handoff §6 + `CURRENT_STATE.md` "Next moves" for the live mapping.

### 3.6 `handoffs/V5_Housekeeping_DocsToGitHubIssues_NextStepsFramework_2026_05_28_Closing_Handoff_v1.md` (new)

This file.

---

## 4. Code / tests

None — bookkeeping only. **Suite baseline unchanged: 1802 passed / 16 skipped** (PR #294). The 16 skips = 12 NL-parser smoke + 4 Layer 3 SDK smoke, gated on `ANTHROPIC_API_KEY`. **Venv gotcha (re-investigation eliminated):** the container has no project venv; run `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then `/tmp/venv/bin/pytest tests/`.

---

## 5. Manual §5.0 verification steps

None new this session. The ledger (115 scenarios + the D-77 plan-gen entry) is untouched in `CARRY_FORWARD.md`.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Housekeeping is done — get back on the path to live.** The 2026-05-28 housekeeping arc — the docs→issues repoint AND the full issue-tracker reorganization (§11) — is complete; no bookkeeping is owed. The next session returns to the work that actually ships AIDSTATION: the D-77 go-live blocker, then the two other owed deploys.

**Tier 1 — the D-77 PGE convergence re-run (#201 / #202).** It's owed (Andy's hands) and is the #1 go-live blocker (plan-gen 504-loops without it). Redeploy `main`, create one fresh PGE 2026 plan, and confirm in the Vercel log: `llm_layer3a_athlete_state: … HIT … ibundle=<X>` **identical across passes**, per-block `HIT` on later passes, blocks `cap_hit`-cache, plan reaches `ready`. Then the §14 coherence read — do the independently-generated weeks blend within a phase? If `ibundle` still drifts, the diagnostic names the remaining volatile field. **The concrete path to live = the three owed Andy's-hands deploys in §6.3:** (1) this D-77 re-run, (2) the #211/#228 `previous_attempts` `init_db.py`, (3) the K3 equipment ETL — run, confirm, then the §5.0 walkthrough.

### 6.2 The 4-tier next-steps framework (ask #3) — live issue map

This is the canonical mapping; it's mirrored in `CURRENT_STATE.md` "Next moves."

**Tier 1 — Finish the in-flight task.** **D-77 convergence (#201 / #202)** — the re-run above. The whole convergence chain shipped through PR #294; only the confirming re-run remains.

**Tier 2 — Resolve go-live / live-functionality blockers.**
- **#303 — `food_allergies` (incl. anaphylaxis severity) never reaches the nutrition layer (SAFETY, priority:high).** Thread allergy capture into Layer 2E before any nutrition output ships. *This is the highest-priority non-convergence item.*
- D-77 quality flags still firing in prod but **NOT** convergence-blocking (all under #201): **(B)** `volume_band_below` (#293 incomplete — likely D-015 Navigation getting a spurious hours-band + primary under-prescribed; needs a *modeling decision* before touching band logic); **(C)** ~150s/block latency (`out`≈10k tokens; lever = block thinking-budget/size); **(D)** `unknown discipline_category` D-015/D-008 + `sport_locale_incompatible_D-008_home` data hygiene.

**Tier 3 — Finish open-but-not-fully-live functions.**
- **#205** per-block `max_tokens` budget (in-progress — verify in the re-run).
- **#206** real-LLM smoke parity (Layer 4 "Step 7" — the missing safety net).
- **#203** week-seam stitcher (Slice 3 — only meaningful once convergence holds; needs its own Trigger #1 prompt pass).
- **#210** Layer 2E de-stubs (in-progress) + the **orphaned-output wiring under #295** (children #296–#302 / #306 / #307 — builders emit, nothing consumes; `coaching_flags` is a systemically dead channel — one generic render block un-orphans ~6 surfaces).
- The **plan-comparison feature** (completes D-64 Decision #9 — badges built, per-session old-vs-new discarded).
- **#259** plan-ready / plan-failed notifications (poller built; notify + dashboard badge not wired).
- **#208** sibling-route async/resumable treatment.
- The **parked plan-refresh surface redesign** (sequences after D-77 — shares the T3 engine; per-concept decisions pinned in the 2026-05-27 handoff §7.2 and `CARRY_FORWARD.md`).

**Tier 4 — Pursue new functionality.**
- **#211** Layer 3 HITL gate (3C / 3D / 3.5; children #213 + #214 `Layer4ShapeInfeasibleError`).
- **#246 / #251** OAuth-first onboarding.
- **#228 / #235** catalog `public.*` → `layer0.*` migration + the upstream build-out arc.
- **#241** provider integrations & OAuth.
- **#225** testing & tooling.
- **#261 / #262 / #286** icebox (priority:low).

### 6.3 Operating notes for next session (the re-investigation killers — ask #4)

**Session-start read order (Rule #13):** (1) `CLAUDE.md` first; (2) `CURRENT_STATE.md` + `CARRY_FORWARD.md`; (3) this handoff; (4) `./scripts/verify-handoff.sh` for the anchor sweep.

Everything below is here so a new session does **not** re-derive it.

**Tracking model.** Backlog / features / bugs / deferred work = **GitHub issues** in `ahorn885/exercise` (browse `label:epic`). The `Project_Backlog_vN.md` chain (v1–v62) is **frozen under `archive/backlog/`** — read for history, don't reopen. `CARRY_FORWARD.md` keeps only live operational carry-state (owed deploys + the §5.0 walkthrough ledger). GitHub MCP tools are restricted to `ahorn885/exercise`; `issue_write` ignores `state` on create.

**The 13 open epics (browse `label:epic`):**

| # | Title | priority / status |
|---|---|---|
| **#201** | [D-77] Plan-generation reliability & convergence | high — **live fire** |
| **#210** | Layer 2E nutrition / supplements / heat completeness | high — in-progress |
| **#211** | Layer 3 evaluation & HITL gating | high — designed |
| **#228** | Upstream pipeline build-out (Layer 1–3) | high |
| **#212** | Layer 2D injury accommodation | med |
| **#225** | Testing & tooling | med |
| **#241** | Provider integrations & OAuth | med |
| **#246** | Onboarding & athlete data capture (Layer 1) | med |
| **#259** | Notifications (§6.3) | med |
| **#295** | Orphaned code: built-but-not-wired sweep (Layers 1–4) | med — type:bug |
| **#261** | Layer 0 spec & data reconciliation | low |
| **#262** | v1 app maintenance & security icebox | low — icebox |
| **#286** | Post-launch / vision / icebox | low — icebox |

(Note: **#303** food_allergies SAFETY is a *sub-issue*, not an epic — Tier 2. Orphaned-code children #296–#302/#306/#307 sit under #295; HITL children #213/#214 under #211.)

**Owed Andy's-hands deploys (consolidated — DB egress to Neon is blocked from the container, so these are Andy's-hands; tick each off + note on the linked issue once run):**
1. **D-77 PGE convergence re-run — THE gating proof (#201 / #202).** Redeploy `main`; create one fresh PGE 2026 plan. Expect `llm_layer3a_athlete_state: … HIT … ibundle=<X>` with `ibundle` **identical across passes**, per-block `HIT` on later passes, blocks `cap_hit`-cache, plan reaches `ready`. Confirms PR #294 (`last_sync` day-anchor). If `ibundle` still drifts, the diagnostic names the remaining field.
2. **L3B-P-2 Slice 2 — `previous_attempts` JSONB column (#211 / #228).** `python init_db.py` on Neon (idempotent, nullable-default, no backfill) + redeploy. Unlocks the `3B.dnf_recurrence_risk` HITL flag (Slice 1 scalars already live). Closes the last piece of the Phase 4 §H.2 deployed-shape gap.
3. **K3 equipment ETL (#228), independent of everything above.** `psql $DATABASE_URL -f etl/sources/populate_equipment_items_K3_additions.sql` on Neon (idempotent — 10 canonical 0B equipment names). Also confirm `etl/sources/populate_skill_capability_toggles.sql` is applied.

**Test baseline + venv.** 1802 passed / 16 skipped (PR #294). The 16 skips need `ANTHROPIC_API_KEY`. Container has no venv: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest` then `/tmp/venv/bin/pytest tests/`.

**Layer status (unchanged from PR #294).** L0 deployed; L1 shipped; L2 all 5 runtimes shipped (best-fit re-model complete); L3 3A+3B complete + cached wrappers wired (3C/3D/3.5 designed, not built); L4 spec complete §§1–14, all 4 entry points wired; L5 not specced. **Forcing function: Andy's PGE 2026 (2026-07-17); `race_week_brief` auto-fires 2026-07-03.**

**Read-tool gotcha.** `CARRY_FORWARD.md` and some GitHub sub-issue payloads have giant single lines that overflow the 25000-token read window — read in small offset windows, or splice with `head`/`tail`/`cat`, or `jq` the saved JSON.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Backlog / features / bugs / deferred work tracked in **GitHub issues**; the `Project_Backlog_vN.md` doc chain is frozen under `archive/backlog/` and not reopened. | Andy (2026-05-27) | One queryable, labelled, cross-linkable source; the doc chain had grown to v62. |
| 2 | "Next steps" everywhere expressed as the **4-tier priority order** (finish in-flight → go-live/live blockers → finish partial → new). | Andy (this session) | A stable, repeatable triage rule independent of which issues are open. |
| 3 | **Consolidate** the owed deploys + the re-investigated anchors (epic map, test baseline, venv, read order) **into this handoff** so no session re-hunts them. | Andy (this session, ask #4) | Kills the per-session re-investigation tax. |
| 4 | Harvest the two live owed deploys (init_db Slice 2, K3 ETL) out of the deferred narrative **before** pruning it. | Architect call | A blind cut would have dropped live operational state. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| This handoff exists; named exactly as `CURRENT_STATE.md` line 11 references | ✅ `ls handoffs/V5_Housekeeping_DocsToGitHubIssues_NextStepsFramework_2026_05_28_Closing_Handoff_v1.md` |
| `CURRENT_STATE.md` `Last shipped session` points here; CacheKeyDeterminismAudit demoted to Predecessor | ✅ grep line 11 + `### Predecessor` |
| `CURRENT_STATE.md` "Next moves" carries the 4-tier order | ✅ grep `4-tier priority order` |
| `CARRY_FORWARD.md` has the consolidated `Owed Andy's-hands deploys` section (3 deploys) | ✅ grep `Owed Andy's-hands deploys` |
| `CLAUDE.md` carries the `Next-step prioritization (the 4-tier order)` principle | ✅ grep |
| `README.md` root tree has no `Project_Backlog_v{1..11}`; Control_Spec → v8 | ✅ grep |
| `verify-handoff.sh` §[2] comment references `archive/backlog/` (no stale "latest version vs references") | ✅ grep |
| No app code / spec / migration touched | ✅ `git status` — only the 6 bookkeeping files |
| Suite baseline inherited 1802 / 16 (not re-run — no code change) | ✅ inherited |
| `./scripts/verify-handoff.sh` anchor sweep clean | ✅ run pre-commit |
| `scripts/issue-cleanup.sh` committed (the applied cleanup) | ✅ ls |
| Issue-tracker reorg live (labels recolored, #296–#308 backfilled, sub-issues linked under epics, 2 milestones) | ✅ connector reads + milestones page |

---

## 9. Files shipped this session

**Substantive (0 files):** none — no app code, specs, or migrations.

**Bookkeeping (6 files):**
1. `CARRY_FORWARD.md` — consolidated owed-deploys section; pruned migrated deferred work; appended 13-epic table.
2. `CURRENT_STATE.md` — repointed `Last shipped session`; new 4-tier "Next moves"; path fix.
3. `README.md` — full rewrite (version bumps, backlog→issues, drift-proof pointers).
4. `scripts/verify-handoff.sh` — §[2] header comment refresh.
5. `CLAUDE.md` — 4-tier prioritization working principle.
6. `handoffs/V5_Housekeeping_DocsToGitHubIssues_NextStepsFramework_2026_05_28_Closing_Handoff_v1.md` — this handoff.
7. `scripts/issue-cleanup.sh` — the idempotent `gh` cleanup applied to the tracker (§11); kept as the record.

The 5-file ceiling applies to substantive files only; bookkeeping is outside the count.

---

## 10. Carry-forward updates

In `CARRY_FORWARD.md`: added the `Owed Andy's-hands deploys (consolidated)` section (3 deploys, two harvested from the about-to-be-pruned narrative); pruned the migrated deferred-work sections; appended the `Deferred work → GitHub issues` 13-epic table. The §5.0 walkthrough ledger and the live D-77 plan-gen entry were left untouched.

---

## 11. GitHub issue-tracker reorganization (2026-05-28 follow-on)

After the doc repoint, the 104 open issues got a professional pass. The approved cleanup was applied to `ahorn885/exercise` via `scripts/issue-cleanup.sh` (committed this session — idempotent `gh` script, kept as the record). Verified live this session via connector reads + the public milestones page:

- **Label hygiene.** Deleted the 8 unused stock labels (`bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`) + the duplicate `priority:medium`. Created `layer:2b` / `layer:2c` (were missing). Recolored + described every custom label — one hue per dimension (priority = red, layer = blue, area = green, type = purple, status = amber, meta = grey).
- **Backfill.** `priority:` + `status:` on the orphaned-code cluster (#296–#308); `layer:2b` / `layer:2c` onto #297 / #298; full label set on the previously-bare #196; `status:in-progress` on epic #201; `status:deferred` on epic #295.
- **Title fix.** #256 renamed (no longer opens with a link-breaking `#2b`).
- **Sub-issue hierarchy.** Non-epic issues linked as native GitHub sub-issues under their epics (progress bars + real trees). #234 ("[D-73] Layer 1–3 arc") nested under epic #228 rather than closed — keeps the `[D-NN]` traceability.
- **Milestones.** `Go-live: PGE 2026` (due 2026-07-17; 5 issues — #201 / #202 / #205 / #206 / #303) + `Post-launch` (7 issues) — the tracker now mirrors the 4-tier framework directly.

**Net:** backlog discipline lives entirely in GitHub now (labelled, hierarchical, milestoned); no doc re-derivation needed.

---

**End of handoff.**
