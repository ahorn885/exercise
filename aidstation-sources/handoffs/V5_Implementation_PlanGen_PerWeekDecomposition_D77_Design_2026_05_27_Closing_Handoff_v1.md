# Plan-Gen Non-Convergence Incident + D-77 Design — Closing Handoff

**Session:** Live plan-gen incident triage (prod `plan_version_id=23` 504-loop) + a design detour comparing v1 Coaching Review ↔ v2 Plan Refresh, landing the **D-77 per-week decomposition** design as the prioritized fix. Design + bookkeeping only — **no application code shipped**.
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanCreate_Layer3B_SectionH2_PreviousAttempts_2026_05_26_Closing_Handoff_v1.md`
**Branch:** `claude/great-ride-SVQHu`
**PR:** #187 (merged — design doc + this handoff + CURRENT_STATE/CARRY_FORWARD bookkeeping).
**Status:** 1 substantive file (the D-77 design doc) + 3 bookkeeping files (this handoff, CURRENT_STATE, CARRY_FORWARD). No code, no schema, no tests changed.

---

## 1. Session-start verification (Rule #9 — adapted)

This was a mid-stream request, not a fresh session, so the formal first-session checklist / `verify-handoff.sh` was not run. State was verified by **directly reading live on-disk code + the Vercel runtime logs** (not handoff narrative): `routes/plan_refresh.py`, `templates/plans/v2/refresh*.html`, `routes/coaching.py`, `templates/coaching/review.html`, `nl_parser.py`, `layer4/{seam_review,hashing,cache,plan_create,per_phase}.py`, `routes/plan_create.py`, and the `V1CoachingRetire` handoff. No drift relevant to this work was found; the incident was diagnosed against the actual prod deployment (`dpl_Lepws…`, #186).

## 2. Session narrative

**(A) The detour Andy asked for.** Compare the two near-identical plan-iteration surfaces that drifted v1→v2:
- **v1 "Coaching Review"** (`/coaching/review`, `routes/coaching.py` + `templates/coaching/review.html`) — still live, operates on the v1 `training_plans`/`plan_items`/`plan_travel` schema; one big Claude call. Per the 2026-05-21 `V1CoachingRetire` handoff, `/coaching/generate` was hard-retired but `/coaching/review` was deliberately kept because its v2 successor wasn't feature-complete.
- **v2 "Plan Refresh"** (`/plans/v2/refresh`, `layer4/plan_refresh*.py`) — the layered cascade (partial re-run + caching + diff badges + frequency caps + telemetry) on the `plan_versions`/`plan_sessions` schema.

**Finding:** v2 is the better *engine*; v1 had the better *capture surface*. v2 collapsed v1's structured controls into one free-text "what changed?" box + the NL parser. The parser is good for ambient signals ("I'm tired") but structurally **cannot** (a) capture high-frequency explicit signals better served by a button (difficulty), or (b) add net-new entities outside its closed locale vocab (travel locations). Andy's per-concept decisions are pinned in §7.

**(B) The live incident (became priority #1).** While the detour ran, Andy flagged a plan generation stuck at 1600s+. Vercel logs showed `plan_version_id=23` 504-looping on **every** cron pass + direct poll from 00:53→01:31 UTC (~30 min) on the current prod deploy (#186). Diagnosis: a single per-phase synthesizer call (`synthesize_phase`, ≤56 sessions, extended thinking) exceeds the **immovable 300s Vercel function cap**, so it never caches, and the resumable cron redoes it every pass forever — the row never reaches a terminal state, so the progress screen spins indefinitely. Andy killed it via Neon SQL (`UPDATE plan_versions SET generation_status='failed' WHERE id=23`); logs confirmed the cron flipped 504 → 200 (fast no-op) at 01:31.

**(C) The reframe that set the fix.** Andy: the complex multi-discipline expedition plan **is the NORM, not the edge** — that's the product. This rules out a give-up circuit-breaker (it would abandon exactly the plans the app exists to serve) and special-casing big plans. With the 300s ceiling immovable, the only honest lever is **unit size**. Andy also surfaced the "stitcher" concept; verified on-disk it's the **phase-level seam reviewer** (`layer4/seam_review.py`) — no separate stitcher artifact exists — and approved generalizing it to the finer grain.

**(D) D-77 design landed.** `Layer4_PerWeekDecomposition_D77_Design_v1.md` (PR #187): per-week synthesis units (fits budget, monotonic convergence) + proactive prior-block threading + a NEW intra-phase week-seam reviewer + a progress-based backstop. Two decisions ratified at an AskUserQuestion gate (§7). `/plan` triggers fired: #5 (architecture) + #3 (cache contract) + #1 (the new week-seam prompt) — so implementation is **gated on ratification of the design**; this session stopped at the design per "do not implement first and ask forgiveness."

## 3. File-by-file

### 3.1 NEW `aidstation-sources/Layer4_PerWeekDecomposition_D77_Design_v1.md` (substantive)
The full design — problem, the three pillars (per-week unit / threading + week-seam stitcher / progress-based backstop), cache contract (extends the §9.2 per-phase chain to per-block; new `phase_idx` namespaces), schema (2 additive `plan_versions` columns), performance budget, edge cases, a 3-slice implementation plan, open items, test scenarios, gut check. Scope = Pattern A only (`plan_create` + `plan_refresh` T3 cross-phase). 14-section depth standard.

### 3.2 MODIFIED `aidstation-sources/CURRENT_STATE.md` (bookkeeping)
Pointer flipped to this handoff; PreviousAttempts demoted to Predecessor; "Current focus" rewritten to lead with the three prioritized next steps (§6).

### 3.3 MODIFIED `aidstation-sources/CARRY_FORWARD.md` (bookkeeping)
Added the incident + D-77 entry, the parked plan-refresh-redesign track (with Andy's captured per-concept decisions), and the plan-comparison to-do.

### 3.4 NEW this file (bookkeeping)

## 4. Code / tests

**None.** Design + bookkeeping only. No application code, schema, or tests changed. The full suite is unchanged from the predecessor baseline (1760 passed / 16 skipped).

## 5. Owed actions + manual verification

- **✅ Already done (Andy, this session):** killed the runaway `plan_version_id=23` via Neon SQL; cron confirmed back to 200 no-op.
- **Owed when the D-77 implementation slices land (NOT owed now — no code shipped):** Slice 2 adds two `plan_versions` columns (`generation_units_cached`, `generation_stall_passes`) → `python init_db.py` on Neon + redeploy (container egress to Neon is blocked). §5.0 walk scenarios get added with each slice.
- **No owed action from this doc-only session** beyond the PR #187 merge.

## 6. Next session pointers

### 6.1 Next moves — priority order (Andy-set this session)

1. **D-77 — ratify, then implement Slice 1** (per-week decomposition + proactive threading): the part that actually closes the convergence hole. Then **Slice 2** (progress-based backstop + the 2 columns) — Slices 1+2 together close the incident — then **Slice 3** (week-seam stitcher; its own Trigger #1 prompt-design pass for the intra-phase calibration). Spec: `Layer4_PerWeekDecomposition_D77_Design_v1.md`. **Pending:** ratify the D-77 design + add the D-77 backlog row (Trigger #3) + confirm the `_BLOCK_WEEKS=1` default.
2. **Plan-refresh surface redesign** — fold the v1 Coaching Review concepts into v2 plan_refresh. Andy's per-concept decisions are in §7.2. Spec-first (Triggers #1/#3/#5 fire). D-77 convergence is foundational to the T3 path here, so it sequences after #1.
3. **NEW — plan-comparison feature (completes D-64 Decision #9).** When a refresh runs, show the athlete what the plan **was** vs what it **is** for the affected dates. **Specced** (D-64 #9: "'View what changed' expandable per session shows old-vs-new fields") **but only partially built**: `templates/plans/v2/refresh_view.html` + `routes/plan_refresh.py:_diff_sessions_against_parent` render "updated/new/unchanged" badges + an "N changed" header, but the diff resolver discards the prior session content, so there is no per-session old-vs-new field comparison. Finalize the design (does it live on `refresh_view` expandables, the plan view, or both? per-day pointer per D-64 #10?) + implement.

### 6.2 Operating notes for next session

Read order (Rule #13):
1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + the 3 prioritized next moves.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling items (the parked plan-refresh-redesign track + the plan-comparison to-do live here).
4. `aidstation-sources/Layer4_PerWeekDecomposition_D77_Design_v1.md` — the design to ratify before any code.
5. This handoff.
6. `./aidstation-sources/scripts/verify-handoff.sh` — anchor sweep.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Kill the runaway plan via Neon SQL (over letting it loop / waiting) | Andy | The row never self-terminates (every pass 504s before flipping to terminal); each loop burns a function invocation + a partial Anthropic call. Manual fail is the only stop (no in-app cancel; container can't reach Neon). |
| **D2** | Fix = shrink the synthesis unit (per-week), NOT a give-up circuit-breaker or big-plan special-case | Andy ("complex is the NORM") | 300s is the immovable Vercel ceiling; any single-call-per-phase design is structurally guaranteed to wall for some athlete. Decomposition scales with complexity instead of fighting it. |
| **D3** | Stitch strategy = **threading + week-seam reviewer now** (over threading-only / fast-follow) | Andy (AskUserQuestion gate) | Strongest coherence; build the corrective stitcher at week boundaries in this arc. Requires a NEW intra-phase reviewer prompt (Trigger #1, different calibration than the phase-seam prompt). |
| **D4** | Block size = **1 week, tunable** (over adaptive / decide-in-spec) | Andy (AskUserQuestion gate) | Smallest safe unit, max convergence margin; `_BLOCK_WEEKS` is a config knob to raise to 2+ if per-block latency proves the call-count overhead high (revisit after the §5.0 walk). |
| **D5** | Progress-based backstop (zero-progress pass → fail loudly) over a time/attempt give-up timer | Andy ("complex is the NORM") | A complex plan may take many passes; only a pass that caches zero units signals a genuinely over-budget unit. Detection at next-pass start is robust to the 504-kill. |

### 7.2 Plan-refresh redesign — Andy's per-concept decisions (for next move #2)

- **Tier:** v2 (T1 2d / T2 7d / T3 28d). **Tier-3 semantic:** "regenerate the next 28 days, **or** generate them if they don't exist — without going past the plan end."
- **Free text:** v2 ("what changed?" → NL parser). **One box**, helper text defines what goes in it (also runs the v1 preference-miner + clarify).
- **Difficulty:** v1 structured control (too easy / just right / too hard) — but it **recalibrates the plan from that point forward AND updates the athlete's fitness baseline** (next plan, "too easy" ticks it back up → a self-correcting baseline). NOT a per-refresh-ephemeral signal.
- **Fatigue:** becomes a **flag/nudge** suggesting a refresh (not a competing refresh input) — resolves the difficulty↔fatigue double-count.
- **Travel:** v1 structured capture **+ the ability to add a genuinely new location that doesn't exist yet** (the hard part — equipment source for a new location; scope to a coarse template + optional Mapbox anchor, not a global equipment DB).
- **Current location:** v1 ("training from right now" picker).
- **Goals:** **hybrid** — pull from the race's §H.2 goals, show + allow free-text edits; if new text, **write it back to the race event** (triggers 3B periodization eviction).
- **Clarification:** v1 (`/coaching/clarify`-style 1-3 pre-flight questions on the free-text box; new prompt = Trigger #1).
- **Plan health:** v1 "review due" indicators **+ nudges** (the fatigue/staleness/travel-ahead nudges).
- **Notes:** v1 (durable preference mining) — folded into the one free-text box.
- **Partial:** v2 (surgical re-run + cache + diff + caps + telemetry — the engine stays).

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| D-77 design doc exists | ✅ `aidstation-sources/Layer4_PerWeekDecomposition_D77_Design_v1.md` created + committed (PR #187) |
| Design doc is design-only (no code) | ✅ markdown only; no `.py`/schema/test touched this session |
| `CURRENT_STATE.md` pointer flipped to this handoff | ✅ "Last shipped session" → this file; PreviousAttempts demoted to Predecessor |
| `CURRENT_STATE.md` "Current focus" leads with the 3 prioritized moves | ✅ |
| `CARRY_FORWARD.md` carries the incident + parked redesign + plan-comparison to-do | ✅ |
| Incident stopped | ✅ Vercel logs: cron 504 → 200 at 01:31 UTC after the Neon fail |
| PR #187 merged to `main` | ✅ (squash) |
| No owed deploy from this session | ✅ doc-only; the 2-column migration is owed only when Slice 2 ships |

## 9. Files shipped this session

**Substantive (1):**
1. NEW `aidstation-sources/Layer4_PerWeekDecomposition_D77_Design_v1.md` — D-77 design.

**Bookkeeping (3):**
2. MODIFIED `aidstation-sources/CURRENT_STATE.md` — pointer + focus.
3. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — incident + parked redesign + plan-comparison to-do.
4. NEW `aidstation-sources/handoffs/V5_Implementation_PlanGen_PerWeekDecomposition_D77_Design_2026_05_27_Closing_Handoff_v1.md` — this file.

## 10. Carry-forward updates

See `CARRY_FORWARD.md`. Net changes:
- **Plan-gen non-convergence incident + D-77 design (2026-05-27)** added — root cause (single per-phase unit > 300s cap), the manual Neon fail that stopped it, and the D-77 fix design (pending ratification + 3-slice implementation).
- **Plan-refresh surface redesign (parked track)** added — Andy's per-concept decisions (§7.2) for folding v1 Coaching Review concepts into v2 plan_refresh.
- **Plan-comparison feature to-do** added — completes D-64 Decision #9 (per-session old-vs-new field comparison; badges + header already built).

**End of handoff.**
