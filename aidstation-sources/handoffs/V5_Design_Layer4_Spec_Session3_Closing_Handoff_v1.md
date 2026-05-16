# V5 Design — Layer 4 Spec Session 3 Closing Handoff

**Session:** Single-stage. No Andy decisions teed up — §§8–9 are mechanical fleshing-out of session-1/2 contracts per the session-2 handoff §5 recommendation. One spec-file commit (`fe6cafe`); this handoff is the second commit on the branch.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Design_Layer4_Spec_Session2_Closing_Handoff_v1.md` (session 2's §5 named "§8 (coaching flag rules) + §9 (caching & determinism)" as session 3 scope, both flagged as mechanical and fittable in a single session unless Andy wanted to redesign the flag taxonomy — Andy went "go for it" with no redesign).
**Branch:** `claude/v5-design-layer-implementation-7gSTX` (cut from `main` at `96def4a` — the merge commit for session-2 PR #56).
**Status:** 🟢 §§8–9 drafted + `seam_unresolved` added to §7.10 Observation enum (gap session-2 left). 🟡 Spec mid-stream: §§10–14 still stubbed; sessions 4–5 land them. 🟡 No CLAUDE.md / backlog bump this session — held per the v1-commit deferral rule carried forward from sessions 1 and 2 ("lands at end-of-PR once §§10–14 are also drafted"). PR will be created after this handoff lands; same end-of-arc cadence.
**Time-on-task:** Single chat. 5 surgical Edits to one file. Files this session: **1 substantive** (Layer4_Spec.md, 1013 → 1247 lines; +249 / -15) + **1 bookkeeping** (this handoff). Well under 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

Session-2 closing handoff §7 claimed Layer4_Spec.md was 1013 lines + 48 H2 headings + all §§4–6 content + Decision 8 references + §§8–14 stub-label updates on disk. Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| Layer4_Spec.md 1013 lines pre-session-3 | `wc -l` | ✅ |
| 48 H2+ headings (`grep -c "^##"`) | `grep` | ✅ |
| §§4.1–4.5 + §§5.1–5.5 + §§6.1–6.5 all present | `grep -nE "^### [456]\."` | ✅ — 15 sub-sections found |
| Decision 8 references (header source-decisions, §6.2, §12 strikethrough, footer) | `grep -n "propose-patch\|Decision 8"` | ✅ — 6 hits across the four expected anchors |
| §§8–14 stub labels read "to be drafted in a later session" | `grep -n "to be drafted"` | ✅ — 7 hits |
| Branch `claude/v5-design-layer-implementation-7gSTX` cut clean from `main` at `96def4a` | `git log` | ✅ — session-2 merge present at HEAD of main |
| Working tree clean | `git status` | ✅ |

No drift. Session-2 narrative reconciled cleanly against on-disk state.

Note on the Rule #9 finding fed into §2 below: while reading §6.2 + §5.2 narrative for the seam-reviewer semantics context, noticed `seam_unresolved` is committed-to as an `Observation.category` value in five narrative spots but was NOT in the §7.10 enum. Treated as a session-2 cleanup gap to fold into this session's drafting rather than as a "drift" requiring a separate fix — the spec contracts are consistent in narrative, just missing the enum entry.

---

## 2. Session narrative — §§8–9 mechanical drafting

The chat opened with Andy asking me to look at the session-2 handoff and "let's work." Per the session-2 handoff §5, the scope was §8 (coaching flag rules) + §9 (caching & determinism), both flagged as mechanical with no Andy decisions teed up. I confirmed scope with Andy ("Want me to proceed with §§8–9 drafting, or different scope?") and got "go for it."

No new Andy decisions surfaced during drafting. Five policy defaults I picked without explicit Andy confirmation (warrant flagging in §6 below):

1. **§8.1 LLM-emitted vs spec-auto-emitted convention.** Two-kinds split; orchestrator owns post-synthesis merge; closed-set rule on synthesizer flag vocabulary (unknown flags → schema-violation per §5.5). Could have been three-kinds (LLM-emitted / spec-auto / validator-emitted) but validator-emitted observations don't appear in the current rule set; collapsed to two.
2. **§8.2 Base-phase flags.** Four entries (`first_introduction_to_<discipline>`, `aerobic_base_focus`, `technique_emphasis`, `volume_ramp_conservative`). Conservative pick; might be missing flags for "long-slow-distance" emphasis or "aerobic threshold" markers — revisit if production cases surface them.
3. **§8.3 Build-phase flags.** Four entries (`weak_link_targeted`, `overreach_test`, `discipline_specific_intensity`, `volume_ramp_aggressive`). The `volume_ramp_aggressive` threshold (ACWR ≥ 1.15 while still inside the 1.4 blocker band) is a v1 default that warrants tuning post-launch.
4. **§8.6 Cross-phase flags.** Only two entries (`race_day`, `intensity_modulated`). Originally drafted a third (`awaiting_joint_coordinator`) for §L joint sessions, then dropped — Layer 4.5 owns that surface per §2 + §12; v1 Layer 4 should not pre-emit joint-session placeholders.
5. **§9.5 cache lifetime.** No time-based TTL in v1 except the `race_week_brief` midnight-UTC rollover. The spec recommends (if orchestrator adds TTL) aligning to ~7 days per typical 3A re-eval cadence; not enforced.

Also folded in the session-2 cleanup gap noted in §1 above: added `'seam_unresolved'` to the §7.10 `Observation.category` enum so the §6.2 / §5.2 narrative commitments have a typed home.

No other Andy decisions this session — the rest was mechanical drafting against the session-1/2 contracts.

---

## 3. Files shipped this session

All on branch `claude/v5-design-layer-implementation-7gSTX`. Spec commit `fe6cafe` pushed at end of chat per the standard mechanic; this handoff commit follows.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Layer4_Spec.md` | Edit (1013 → 1247 lines; +249 / -15) | Full breakdown in §4 below. |
| 2 | `aidstation-sources/handoffs/V5_Design_Layer4_Spec_Session3_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Not touched this session** (deferred per the v1-commit rule):

- `CLAUDE.md` — no last-shipped-narrative bump; stays pointed at PR17.
- `Project_Backlog_v30.md` — no version bump.
- `PR_Verification_Status.md` — no PR shipped this session.
- `Control_Spec_v8.md` — §9 doc-map stale-flag from PR16 still standing; Layer 4 entry lands at end-of-arc.

---

## 4. What the spec now commits to (post-session-3)

### 4.1 Newly-drafted sections (§§8–9)

| Section | Status | Content |
|---|---|---|
| §8 Coaching flag rules | ✅ | §8.1 LLM-emitted vs spec-auto-emitted convention + closed-set rule + orchestrator post-synthesis pass + defensive validator check (`coaching_flag_missing_<flag>`). §§8.2–8.6 per-phase + cross-phase flag tables (Base 4 entries; Build 4; Peak 3; Taper 5 preserved verbatim from session-1 draft; cross-phase 2). Each flag tagged LLM-emitted or Spec-auto. §8.7 call-level observation auto-emit triggers covering every `Observation.category` enum value + the `opportunity`-only LLM-emitted exception. §8.8 v1 scope caveats. |
| §9 Caching & determinism | ✅ | §9.1 per-entry cache key formulae for all four entry points (full SHA-256 component lists; canonical-JSON encoding rules). §9.2 per-phase cache for Pattern A (derived key chain; cache hit semantics; seam-reviews-not-cached rationale; T3 cross-phase refresh behavior). §9.3 invalidation triggers table (per Control_Spec §4 partial-update model); race_week_brief midnight-UTC date-rollover rule. §9.4 determinism guarantees (cache-hit byte-identicality; per-call `plan_version_id` + `suggestion_id` rebinding semantics; seed-parameter forward-pointer). §9.5 cache scope + lifetime. §9.6 observability (orchestrator-owned; Layer 4 doesn't see hits). |

### 4.2 §7.10 Observation enum cleanup

Added `'seam_unresolved'` between `'best_effort_plan'` and `'intensity_modulated'` with inline `# §6.2 — per-seam iteration cap exhausted or seam patch blocked by retry budget` comment. The category is referenced in 5 narrative spots (§5.2 step 4.4; §6.2 verdict table; §6.2 per-seam cap paragraph; §6.2 seam/validator-retry interaction paragraph; new §8.7 trigger table) — all now have a typed home.

### 4.3 Header updates

- Status line: bumped from "Session 2" framing to "Session 3 (this update) covers §8 Coaching flag rules and §9 Caching & determinism." Source-decisions narrative carried forward; added explicit "No new source decisions this session" note to make the mechanical-fleshing-out nature loud.
- Source-decisions block: unchanged (no new Andy decision).

### 4.4 Stub headings re-labeled

Sections §§10–14 still bear the "to be drafted in a later session" suffix. The session-2 §§8–14 set narrows to session-3 §§10–14.

### 4.5 v1-commit deferral rule still standing

Per session-1's commit-message convention (carried through sessions 2 and 3): mid-stream work; no CLAUDE.md / backlog bump yet. They land at end-of-PR once §§10–14 are also drafted. This handoff respects that rule — no CLAUDE.md or `Project_Backlog_v30.md` bump.

---

## 5. Session 4+ scope

Session-2 handoff §5's recommended order still stands. Concretely:

### Session 4 (recommended): §10 (edge cases) + §11 (performance budget) + §13 (test scenarios)

- **§10** — existing stub already enumerates ~8 edge cases. Tighten + add a few (joint-session day on a refresh boundary; race_week_brief triggered with no Taper-phase sessions; D-63 single-session when locale's effective equipment changes between request and synthesis; ETL-version-set drift mid-synthesis). Now that §9 caches are spec'd, also add: cache-hit-then-rebind-collision (two concurrent plan_create calls allocate different `plan_version_id` values but hit the same cached body); per-phase cache hit on phase 0 + miss on phase 1 (downstream chain re-synthesis verification).
- **§11** — Pattern A / B latency numbers already in stub + repeated in §5.2 and §5.3 narrative. Per-phase + per-seam cost-cap interaction with D-64 §6 frequency caps. Now also: cache-hit-rate assumptions (orchestrator-side; affects amortized cost). Tighten.
- **§13** — full TS-1..TS-N table. Stub names ~7 scenarios; expand to coverage matrix across (entry_point × periodization_shape × tier × validator_pass/fail). Add coaching-flag emit scenarios (every spec-auto trigger from §§8.2–8.6 + every LLM-emit-then-orchestrator-merge scenario) + cache-hit/miss scenarios (per-entry + per-phase + invalidation event).

### Session 5 (recommended): §12 (open items maintenance) + §14 (gut check) + end-of-arc CLAUDE.md + backlog bump

- **§12** — prune resolved items (none additional this session); tighten the still-open items; pin forward to Layer 4.5 + Layer 5 specs. The §9 cache spec resolved the session-2 §12 item "Validator's `intended_intensity_distribution` per-phase defaults" partially (§5.4 already had them; §9.3 invalidation table now references the tunable change rule). The §8 spec generated three new tuning-candidate items (§8.3 `volume_ramp_aggressive` threshold; §8.2 `volume_ramp_conservative` data_density trigger; §8.4 `peak_volume_marker` definition); these should fold into the §12 "v1 defaults; tune post-launch" basket.
- **§14** — end-of-spec retrospective per 14-section template.
- **CLAUDE.md** + **Project_Backlog_v30.md → v31.md** — end-of-PR bookkeeping bump per the deferral rule.
- **PR**.

This keeps the original 3–5-session estimate intact (session 1 + 2 + 3 + 4 + 5 = 5 total).

### Alternative chunking

If Andy wants to front-load a prompt-body session (per-phase synthesizer prompt for Pattern A, or the seam-reviewer prompt), that's an explicit `stop-and-ask trigger #2` carve-out and can slot anywhere; it would slip the v1 spec arc by one session.

---

## 6. Open items / decisions pinned this session

### 6.1 v1-default policy items (flagged for Andy review post-session-3)

Per §2 narrative — five policy items I picked without explicit Andy confirmation, all with conservative defaults and inline "v1 / tune post-launch" framing:

1. §8.1 two-kinds split (LLM-emitted vs spec-auto-emitted) — could have been three-kinds with a validator-emitted category, but no current observations need it.
2. §8.2 Base-phase flag set — 4 entries; potentially incomplete (no LSD / aerobic-threshold flags).
3. §8.3 `volume_ramp_aggressive` ACWR threshold ≥ 1.15.
4. §8.6 cross-phase flag set — only 2 entries (joint-session flag dropped pending Layer 4.5 spec).
5. §9.5 cache lifetime defaults — no time-based TTL except midnight-UTC `race_week_brief` rollover; recommends ~7-day TTL if orchestrator adds one (per typical 3A re-eval cadence).

None are load-bearing schema decisions; all are tuning parameters or narrow rule-set additions Andy can adjust without restructuring the spec. Flagged here so they don't slip past review.

Carry-forward from session-2 §6.1 (still pending Andy sanity-check): §5.4 validator tolerance thresholds; §5.4 intensity-distribution defaults per phase; §6.1 open-ended mode total horizon (16 weeks); §6.1 Taper bounds (1–4 wk); §6.4 `shape_override` trigger set (3 narrow rules).

### 6.2 §12 open-items state (post-session-3)

Same set as session-2 §6.2 with one minor tightening: "Validator's `intended_intensity_distribution` per-phase defaults" is now substantially addressed by §5.4 v1 defaults + §9.3 invalidation rule (tunable change invalidates affected caches). Item stays open as a tuning candidate but the load-bearing schema work is done.

Three new tuning-candidate items generated this session (all v1-default flags noted inline; should fold into §12 in session 5):

- §8.3 `volume_ramp_aggressive` ACWR threshold (currently ≥ 1.15).
- §8.2 `volume_ramp_conservative` data_density trigger (currently `data_density ∈ {'sparse', 'very_sparse'}`).
- §8.4 `peak_volume_marker` "highest-volume week" definition (currently the single highest-volume week; could be tightened to "weeks within 5% of the highest").

13 items still open in §12 (unchanged count from session 2 — three additions above are tuning items that fold into existing "v1 defaults; tune post-launch" basket rather than separate items).

---

## 7. Session-end verification (Rule #10)

Final pass over the file before composing this handoff:

| Check | Result |
|---|---|
| Layer4_Spec.md 1247 lines | ✅ `wc -l` |
| 62 H2+ headings (was 48 pre-session; +14 new sub-sections: 8 in §8 + 6 in §9) | ✅ `grep -c "^##"` |
| §8 sub-sections §§8.1–8.8 all present | ✅ `grep -nE "^### 8\."` |
| §9 sub-sections §§9.1–9.6 all present | ✅ `grep -nE "^### 9\."` |
| `seam_unresolved` in §7.10 enum (line 507) + still in 5 narrative spots | ✅ `grep -n "seam_unresolved"` — 7 hits total (1 enum + 5 narrative + 1 footer) |
| Header status line bumped to "Session 3" | ✅ Read line 3 |
| End-of-spec footer mentions session 3 + drafted §§8–9 + seam_unresolved enum addition | ✅ Read line 1247 |
| §§10–14 stub labels still read "to be drafted in a later session" (5 entries; was 7) | ✅ `grep -n "to be drafted"` |
| No CLAUDE.md / Backlog bump (per v1-commit deferral rule) | ✅ `git diff --stat HEAD~1..HEAD` shows only Layer4_Spec.md |
| Branch ahead of `main` by 1 commit (`fe6cafe`) pre-handoff; will be 2 commits after this handoff | ✅ `git log main..HEAD` |
| Working tree clean before handoff write | ✅ `git status` |

---

## 8. Operating notes for session 4

1. **First re-read** (per CLAUDE.md Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load.
2. **Second re-read**: this handoff in full.
3. **Third re-read**: `Layer4_Spec.md` in full, with extra attention to §8 (closed-set flag taxonomy — §10 edge cases will reference flag-driven retry paths; §11 cost numbers depend on per-flag re-synthesis frequency) and §9 (cache invalidation triggers — §10 edge cases include cache-related races; §11 cost numbers depend on cache hit rates).
4. **Do not bump CLAUDE.md or backlog** until §§10–14 are also drafted. The bump lands at end-of-arc per the sessions-1/2/3 deferral rule.
5. **No new gating Andy-decisions teed up for session 4** as currently scoped. §10 edge cases is mechanical enumeration; §11 performance budget is tightening existing stub numbers; §13 test scenarios is matrix expansion. If Andy wants to change the latency budget envelope (e.g., "p95 60s is too slow; redesign Pattern A for parallelism") or add new validator rules that change cost shape, those are stop-and-ask trigger #5 (schema change affecting inter-layer contract) — surface them then.
6. **Policy defaults from session 3** (§8.1 two-kinds split, §8.2/§8.3/§8.4 per-phase flag sets, §8.3 ACWR threshold, §8.6 cross-phase flag set, §9.5 cache lifetime) — none lock anything; Andy can adjust at any time. Surface them in session 4 if drafting §10 or §13 makes them feel wrong.
7. **Stop-and-ask trigger #2 still applies**: per-phase / per-tier / single-session / seam-reviewer / race-week-brief prompt bodies are explicitly OUT of session 4 (and §§10–14 in general). Session 4 expands the contract sections (§10 edge cases, §11 perf budget, §13 test scenarios); prompt bodies are downstream.
8. **Cost/latency numbers** in §11 should stay informal until Andy has measured production retry rates + cache-hit rates. Same posture as sessions 2 and 3 ("design well, cut later if too costly"). §9 cache spec is now in hand to inform §11's amortized-cost discussion.
9. **§8 + §9 interactions to keep consistent in §10/§11/§13:** Pattern A's per-phase cache (§9.2) means downstream phases hit cache when prior phases are byte-identical to a prior call — §10 should cover the cache-hit + concurrent-call-rebinding edge cases; §11 amortized cost should factor cache hit rates; §13 should include cache-hit vs cache-miss scenarios. The §8.1 closed-set rule means synthesizer-emitted unknown flag is a schema-violation — §10 should cover that as an edge case; §13 should cover it as a TS scenario.

---

## 9. Carry-forward from PR17 (informational)

Same state as sessions 1 and 2:

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — Andy mentioned in session-1 chat that it passed; not actioned this session (no CLAUDE.md / backlog touch).
- PR15 `/profile?tab=schedule` round-trip from PR15 §5.0 — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate as of `96def4a` (main): same totals as session-2's reading (43 done / 21 blocked / 23 owed / 4 N/A). No movement this session (no PR shipped; this session is design-track).

---

---

## 10. Post-handoff calibration pass (Andy 2026-05-16, same chat)

After this handoff was committed (`9055bca`), Andy walked through the policy items flagged in §6.1 + the carry-forward set. Decisions captured below; the spec was amended in a follow-on commit on the same branch (no new structural Andy decisions — these are tuning parameter calls within already-decided contracts, so no Decision 9+ in the header source-decisions block).

### 10.1 Resolved this pass

| Item | Resolution | Spec edit site |
|---|---|---|
| §5.4 validator tolerance thresholds (carry-forward from session 2 §6.1) | Keep as-is: ±15% volume blocker / ±5% warning; ACWR safe-band 0.8–1.3 (blocker 0.7–1.4); ±10pp intensity per zone. | No edit. |
| §5.4 intensity-distribution per-phase defaults (carry-forward from session 2 §6.1) | Peak lowered from 60/25/15 to **70/20/10** (matches Build's zone distribution). Build / Peak differentiate via volume shape + race-specific intensity placement (LLM-emitted `race_pace_specific` flag per §8.4), not zone distribution. Pyramidal-polarized stays flat through Peak for endurance / ultra / AR / multi-sport disciplines. Base 80/15/5 + Taper 75/15/10 unchanged. | §5.4 intensity-distribution rule row. |
| §6.1 open-ended-mode total horizon (carry-forward from session 2 §6.1) | Changed from 16 weeks to **12 weeks (one mesocycle)** rolling forward. Extension is via T3 refresh as the 12-week horizon approaches end (D-57 scheduled re-eval still deferred; athlete-initiated T3 supported on existing refresh path). Broader D7 tiered tight/loose question unchanged — still HELD. | §6.1 "Total horizon resolution" paragraph. |
| §6.1 Taper bounds (carry-forward from session 2 §6.1) | **Hard 1–4 wk bounds removed.** Taper length is duration-based coaching judgment (race format + §H.2 `estimated_duration_hr` primary drivers; not discipline alone). Synthesizer picks within mode proportion budget. v1 prompt guidance (informational, not enforced): ~1–2 wk sub-marathon; ~2–3 wk marathon / half-IM; 3+ wk expedition AR + multi-day ultras + full-IM. | §6.1 — Taper paragraph rewritten; prior 1/4-wk floor/ceiling deleted. |
| §8.3 `volume_ramp_aggressive` ACWR threshold (this session §6.1 item 3) | Threshold raised from **≥ 1.15 to ≥ 1.25** so the flag fires only on genuinely aggressive ramps, not on every mid-band Build week. | §8.3 ACWR row. |

### 10.2 Deferred / pending

| Item | Status |
|---|---|
| §6.4 `shape_override` trigger set completeness (carry-forward from session 2 §6.1) | Deferred to §10 edge-case drafting (session 4). Andy: "defer to science here. what does research and coaching [say]" — surface relevant research framing in session 4 §10 draft + bring options to him before locking. |
| §8.1 two-kinds split (this session §6.1 item 1) | Pending. Andy hasn't pushed back; if §10/§11 surfaces a need for a validator-emitted third category, that's a small spec amendment. |
| §8.2 Base-phase flag set completeness (this session §6.1 item 2) | Pending. Easy to add later — taxonomy is closed-set but extensible via spec amendment. |
| §8.6 cross-phase flag set completeness (this session §6.1 item 4) | Pending. Layer-4.5 joint-coordinator flag intentionally absent in v1; revisit when 4.5 spec is drafted. |
| §9.5 cache lifetime (this session §6.1 item 5) | Pending. Orchestrator concern; no spec enforcement. |

### 10.3 Handoff §6.1 status (post-calibration)

The five "items flagged for Andy review post-session-3" in §6.1 above resolve as: item 1 (two-kinds split) pending; item 2 (Base flag set) pending; item 3 (ACWR threshold) ✅ resolved → ≥ 1.25; item 4 (cross-phase flag set) pending; item 5 (cache lifetime) pending.

The carry-forward set from session 2 §6.1 resolves as: validator tolerances ✅ kept; intensity-distribution ✅ Peak lowered to 70/20/10; open-ended horizon ✅ 12 weeks; Taper bounds ✅ removed (LLM-picked); `shape_override` triggers deferred to §10 with research framing.

### 10.4 Bookkeeping

- Spec commit covering all five edits: pushed alongside this handoff amendment.
- No new Decision 9+ in the source-decisions block — these are calibration tweaks within already-decided contracts (Decision 4 race-prep + the §5.4/§6.1/§8.3 v1-defaults framework). The "Andy 2026-05-16 session-3 calibration" attributions live inline at each change site.
- No CLAUDE.md / backlog bump (v1-commit deferral rule still standing).
- File count this calibration micro-pass: 2 (spec + this handoff edit). Session total: 1 substantive spec + 1 handoff + 1 calibration amendment = 3 files. Still under 5-file ceiling.

---

**End of handoff.**
