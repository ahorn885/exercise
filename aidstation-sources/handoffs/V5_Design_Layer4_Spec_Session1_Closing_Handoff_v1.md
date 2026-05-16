# V5 Design — Layer 4 Spec Session 1 Closing Handoff

**Session:** Two-stage on the same branch. **Stage A** (prior turn / subagent): Layer 4 spec v1 draft from scratch — §1, §2, §3 (3 entry points), §7 (full payload schema), with §§4–6 + §§8–14 stubbed at the bottom (commit `08b4f20`). **Stage B** (this chat): seven-decision design conversation with Andy, folded back into the v1 draft in place — added the 4th `race_week_brief` entry point, two-sessions-per-day fields on `PlanSession`, `RaceWeekBrief` + `RacePlan` schemas, Taper auto-emit rules in §8 stub, Layer 4.5 + tiered-horizon forward-pointers in §12 stub (commit `effbb48`). This handoff = third commit on the branch.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Implementation_PR17_DATABASE_md_Deep_Rewrite_Closing_Handoff_v1.md` (PR17 §8 forward-pointer named "Layer 4 spec draft — Option A" as the next forward direction after the SQLite-cleanup story closed).
**Branch:** `claude/review-handoff-docs-cOzqJ` (branch name predates the Layer-4-spec scope; cut from `main` after PR17 merged at `6fd539d`).
**Status:** 🟢 Spec draft v1 + 7-decisions fold-in committed and pushed. 🟡 Spec is mid-stream: sessions 2–5 still required to land §§4–6 + §§8–14. 🟡 No CLAUDE.md / backlog bump this session — held per the v1-commit rule ("lands at end-of-PR per PR16 §5.4 mechanical spec once §§4–6 + §§8–14 are also drafted"). PR will be created after this handoff commits.
**Time-on-task:** Stage A was a single prior turn (single commit, 551 lines net new, no other files touched). Stage B was this chat: ~10 surgical Edits to one file (197 insertions / 12 deletions → 736 lines total). Files this session: **1 substantive** (Layer4_Spec.md) + **1 bookkeeping** (this handoff). Well under 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

PR17 closing handoff (`V5_Implementation_PR17_DATABASE_md_Deep_Rewrite_Closing_Handoff_v1.md`) §8 named the next forward-pointer as "Layer 4 spec draft (Option A) — start §1, §2, §3 of `Layer4_Spec.md` over an expected 3–5 sessions". Branch `claude/review-handoff-docs-cOzqJ` was cut from `main` post-PR17-merge (`6fd539d`) to execute it.

Verified at this session's start (Stage B):

| Claim | Anchor | Result |
|---|---|---|
| Branch ahead of `main` by 1 (Stage A's `08b4f20`) | `git log main..HEAD` | ✅ |
| `aidstation-sources/Layer4_Spec.md` exists; 551 lines | `wc -l` | ✅ |
| Spec covers §1, §2, §3 (three entry points), §7 with §§4–6 + §§8–14 stubbed | `grep "^##"` | ✅ — 33 H2 headings (§1–§14 + §3.1/§3.2/§3.3/§3.4 + §7.1–§7.12 sub-headings) |
| Stage A commit message names Decisions 1, 2, 3 + the v1-commit deferral rule for CLAUDE.md / backlog | `git log -1 --format=%B 08b4f20` | ✅ |
| Working tree clean | `git status` | ✅ |

No drift in the Rule #9 sense.

---

## 2. Stage B narrative — seven decisions folded in

The chat opened with Andy reviewing the Stage A v1 draft and responding to seven design questions I had teed up. All seven were answered explicitly; the spec was edited in place to fold each pick in. The full decision rationale + attribution lives in the spec header's "Source decisions (this session, 2026-05-16)" block — short summary here:

| # | Question | Andy's pick | Spec impact |
|---|---|---|---|
| **D1** | Topology (per-phase + LLM seam reviewer vs. one big call) | Per-phase + LLM seam reviewer for "big" calls (Pattern A); single-call + deterministic validator for short-horizon (Pattern B) | Already in Stage A v1; no Stage B change |
| **D2** | Entry points (one polymorphic vs. multiple) | Multiple distinct entry points; Stage A landed three (`plan_create`, `plan_refresh`, `single_session_synthesize`); D4 added a fourth (`race_week_brief`) | Stage A: 3; Stage B: +1 → 4 |
| **D3** | Session shape (separate `CardioSession` / `StrengthSession` types vs. discriminated union `PlanSession`) | Discriminated union with `kind: 'cardio' \| 'strength' \| 'rest'` + conditional sub-blocks. **Stage B refinement**: added `session_index_in_day: int` + `time_of_day: Literal[...]` to support two-sessions-per-day (e.g., morning strength + evening cardio) | Stage A landed the union; Stage B added the two new fields + schema-level rules ("max 2 per day; no strength+strength; no two hard cardios same day; at least one of the two must be cardio") |
| **D4** | Race-prep handling (Taper-flag metadata vs. separate brief entry point vs. both) | **Both.** (a) Taper-phase `coaching_flags` auto-emitted per a 5-row trigger table in §8 stub (`race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) AND (b) new `llm_layer4_race_week_brief` entry point producing a structured `RaceWeekBrief` | New §3.4 with full param table; new §7.13 `RaceWeekBrief` + `KitItem` schemas; new §8 stub auto-emit table; `Layer4Payload.mode` enum gets `'race_week_brief'`; new `race_week_brief` + `race_plan` optional payload fields |
| **D5** | Race-day handling for multi-day events (single-PlanSession vs. RacePlan entity) | **`RacePlan` entity for multi-day events** (expedition AR, stage races, multi-day ultras); single-day events stay as a regular `PlanSession` with `coaching_flags=['race_day']` | New §7.14 `RacePlan` + `RaceSegment` + `TransitionSpec` + `PacingStrategy` + `FuelingStrategy` + `Contingency` schemas. `RacePlan` populated only when `race_format != 'single_day'`. v1 schema intentionally lean (no per-segment athlete-checkin / actuals shape — deferred to a future race-execution surface) |
| **D6** | Multi-athlete coordination (in-Layer-4 pre-pass vs. cross-athlete entry point vs. post-pass coordinator) | **(B) Post-pass coordinator: Layer 4.5 — Joint Session Coordinator.** Each athlete gets a solo Layer 4 run; 4.5 reads two-or-more linked athletes' Layer 4 payloads + §L joint-session definitions and harmonizes joint-session days | §2 multi-athlete bullet rewritten to point at Layer 4.5 (no longer "out of v1 scope"); §1 explicit mention; §12 stub forward-pointer with the post-pass approach detail + the schema-readiness note (joint coordinator can supersede solo PlanSessions via a future `joint_session_id` FK addition on `plan_session` rows — schema addition deferred to Layer 4.5's spec) |
| **D7** | Tiered tight/loose plan horizon (uniform-quality long-horizon vs. tight-12wk + loose-remainder + scheduled re-run) | **HOLD.** Substantive direction change; revisit after Layer 4 v1 lands and we have measured cost/quality data on the uniform-quality long-horizon plan. Would un-defer D-57 (scheduled re-evaluation cadence) | §12 stub captures Andy's proposal in full — tight ~12 weeks at Pattern A quality + loose weeks 13+ at degraded quality (smaller model? weekly-summary granularity? fewer inputs?) + scheduled refresh ~1–2 weeks before tight horizon expires + variable T3 horizon. No spec body changes |

Two questions came up in chat that did NOT change the spec because they were already designed elsewhere:

- **Clothing/conditions recommendations.** Andy asked "where do these live?" Layer 5 owns per `Control_Spec_v8.md` §2. Layer 4 produces session metadata (sport + duration + intensity zone + locale FK + race-week kit_manifest) that Layer 5 reads.
- **Coach notes mentioning injury → cascade to 2D first.** Already specced in `D-64 §3 / §5` (NL parser triggers cascade). Orchestrator handles; Layer 4 just consumes the result of the upstream re-evals.

---

## 3. Files shipped this session

All on branch `claude/review-handoff-docs-cOzqJ`. Stage A's commit (`08b4f20`) was already pushed; Stage B's commit (`effbb48`) was pushed at end of chat per the standard mechanic.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Layer4_Spec.md` | Stage A: new (551 lines). Stage B: 10 surgical Edits (+197 / -12 → 736 lines total) | Full breakdown in §4 below. |
| 2 | `aidstation-sources/handoffs/V5_Design_Layer4_Spec_Session1_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Not touched this session** (deferred per the v1-commit rule):
- `CLAUDE.md` — no last-shipped-narrative bump; stays pointed at PR17.
- `Project_Backlog_v30.md` — no version bump; no D-row added for Layer 4 (Layer 3A/3B/3C/3D were also tracked at the spec-file level, not D-row level).
- `Control_Spec_v8.md` — §9 doc-map already-stale-flagged in PR16; full sync deferred per its existing Rule #12 reminder; Layer 4 entry will land then.

---

## 4. What the spec now commits to (post Stage A + Stage B)

### 4.1 Drafted sections

| Section | Status | Content |
|---|---|---|
| Header | ✅ | Status note, 7-decision attribution block (covers D1–D7 with rationale + Andy attribution), session/file/line counts. Mid-session refinements call-out for the Stage B fold-in. |
| §1 Purpose | ✅ | Four entry points enumerated with one-paragraph each; explicit Layer 4.5 carve-out for multi-athlete; "all four return `Layer4Payload`" framing with downstream-consumer list. |
| §2 What Layer 4 does NOT do | ✅ | Boundaries with v1-scope carve-outs. Multi-athlete bullet now points at Layer 4.5 (post-pass coordinator) rather than "out of scope, see §12". |
| §3.1 `llm_layer4_plan_create` | ✅ | Full param table (10+ inputs incl. all `layer2*` / `layer3*` payloads, `plan_version_id`, `etl_version_set`, model/temp/tokens). Returns: Pattern A Layer4Payload. |
| §3.2 `llm_layer4_plan_refresh` | ✅ | Same param table + `tier: T1\|T2\|T3` + `prior_plan_session_window`. Pattern A iff T3 spans phase boundary; Pattern B otherwise. |
| §3.3 `llm_layer4_single_session_synthesize` | ✅ | D-63 entry point. Athlete picks sport + duration + intensity + locale; Layer 4 produces one ad-hoc PlanSession. Pattern B. `suggestion_id` populated. |
| §3.4 `llm_layer4_race_week_brief` | ✅ | New (Stage B). Full param table. Fires when `days_to_event ≤ 14`. Event-mode only (raises `Layer4InputError('race_week_brief_requires_event_mode')` otherwise). `max_tokens=6000` higher than other Pattern B paths. Returns: Pattern B Layer4Payload with `race_week_brief` non-None + `race_plan` non-None for multi-day events. |
| §3.5 Errors raised | ✅ | `Layer4InputError` (with `race_week_brief_requires_event_mode` listed); `Layer4OutputError`; `Layer4ShapeInfeasibleError` (surfaces to 3D, not handled inline). |
| §7.1 `Layer4Payload` | ✅ | `mode` enum has all 4 values; new optional `race_week_brief` + `race_plan` fields. |
| §7.2 `PlanSession` | ✅ | Discriminated union with `kind: 'cardio' \| 'strength' \| 'rest'`. New fields (Stage B): `session_index_in_day: int` + `time_of_day: Literal['morning', 'afternoon', 'evening', 'unspecified']`. Sub-blocks: `CardioBlock` (zone + measure + duration + sport-specific fields), `StrengthExercise` (exercise FK + sets + reps + load). `is_ad_hoc` flag for D-63 path. `coaching_flags: list[str]` for §8-spec auto-emit + LLM-emit flags. |
| §7.3 `CardioBlock` | ✅ | Sport, duration_min, intensity_target (zone or measure-specific), terrain/environment context for Layer 5 advisors. |
| §7.4 `StrengthExercise` | ✅ | exercise_id FK to `layer0.exercises`, sets, reps, load, RPE target, accessory flag. |
| §7.5 `PhaseStructure` | ✅ | Phase boundaries + per-phase intensity distribution + per-phase weekly load profile. Populated only on Pattern A. |
| §7.6 `SeamReview` | ✅ | Pattern A only. Reads two adjacent phase outputs + boundary athlete state, emits verdict (`accepted` / `flagged` / `propose_patch`). |
| §7.7–7.10 | ✅ | `ValidatorResult`, `RuleFailure`, `NotableObservation`, `PlanVersion` (lifted from D-64 §7.2 stub — Layer 4 is the right owner). |
| §7.11 `plan_versions` table | ✅ | Storage shape supporting per-day pointer flip for plan-revert UX (UX itself deferred to Layer 4 §12). |
| §7.12 Schema-level rules | ✅ | Mode → required-fields invariants (incl. `race_week_brief` mode rules). Stage B added: `PlanSession` natural key is `(plan_version_id, date, session_index_in_day)`; `0 ≤ session_index_in_day ≤ 1` (max two per day); no strength+strength same day; no two hard cardios same day; at least one of the two must be cardio. |
| §7.13 `RaceWeekBrief` | ✅ | New (Stage B). Pre-race logistics, drop-bag strategy, course familiarization, kit_manifest (list[KitItem]), kit_check_dates, race-day fueling plan (from 2E), pre-race meal strategy, pacing summary, contingencies, mental-prep cues. Athlete-facing; surface UI TBD. Layer 5's clothing/conditions advisor consumes for race-day kit overlays. |
| §7.14 `RacePlan` | ✅ | New (Stage B). Multi-day events only. RaceSegment list (chronologically ordered), TransitionSpec list (between adjacent segments), PacingStrategy, FuelingStrategy, Contingency list. v1 lean — no per-segment athlete-checkin shape. |

### 4.2 Stubbed sections (session 2+)

| Section | Stub status | What's there | What's owed |
|---|---|---|---|
| §4 Input validation | Brief | One-paragraph target | Full rule list; precondition checks per entry point |
| §5 Algorithm — Pattern A | Brief | Names per-phase + seam-reviewer + validator | Full periodization decomposition; per-phase prompt structure (defers to its own session per stop-and-ask trigger #2); seam-reviewer authority semantics (decision point — flag-only vs. propose-patch vs. force-re-prompt) |
| §6 Algorithm — Pattern B | Brief | Names single-call + deterministic validator | Validator rule set; retry mechanic; best-effort fallback shape |
| §8 Coaching flag rules | Expanded (Stage B) | 5-row Taper auto-emit table + general flag-trigger framing | Full per-mode flag rule set; LLM-emitted flag conventions |
| §9 Cost mechanics | Brief | Pattern A vs. Pattern B token budgets named at high level | Per-entry-point token + cost budget tables; soft-cap interaction with D-64 §6 frequency caps |
| §10 Latency mechanics | Brief | 30–60s ceiling for Pattern A accepted by Andy | Per-stage latency budget; UI affordance contract for "plan generating" indicator |
| §11 Storage handoff | Brief | Atomic-write to `plan_sessions` per `plan_version_id` | Full transaction shape; rollback semantics; per-session vs. per-plan write granularity |
| §12 Open items / forward references | Expanded (Stage B) | LLM seam-reviewer authority; per-phase / per-tier / single-session / seam-reviewer / race-week-brief prompt-body designs (all defer); Plan-revert UX; **Layer 4.5 Joint Session Coordinator** (post-pass approach picked, separate spec); **Tiered tight/loose plan horizon (HELD)** with full Andy-proposal restatement; multi-day race-plan post-race analytics; Layer 5 consumption contract; per-phase intensity-distribution defaults; cost-cap interaction; Layer4ShapeInfeasibleError routing; seam-reviewer model downgrade; race-week-brief trigger policy | Tighten as later sessions land |
| §13 Test scenarios | Brief | Mirrors 3A/3B test-scenario discipline | Full TS-1..TS-N table covering all 4 entry points × phase configs × event/no-event |
| §14 Misc / appendix | Brief | Reserve | TBD |

### 4.3 v1-commit deferral rule

Per Stage A's commit message: "Mid-stream work; no CLAUDE.md / backlog bump yet (lands at end-of-PR per PR16 §5.4 mechanical spec once §§4–6 + §§8–14 are also drafted)." This handoff respects that rule — no `CLAUDE.md` or `Project_Backlog_v30.md` bump. They land at the end of the multi-session arc, when the spec is structurally complete.

---

## 5. Session 2 scope (next-session pickup)

The next chat picks up §§4–6 (preconditions, algorithm Pattern A, algorithm Pattern B). This is a chunky session — the load-bearing decision inside §6 is **seam-reviewer authority semantics**:

- **Option α — Flag-only.** Seam reviewer emits verdicts; orchestrator decides whether to retry. Cheap, simple, but pushes coordination burden upstream.
- **Option β — Propose-patch.** Seam reviewer emits a structured patch (e.g., "shorten Build phase by 1 week; bump first 2 weeks of Peak intensity by 5%"); orchestrator applies + re-validates. Middle ground.
- **Option γ — Force-re-prompt.** Seam reviewer can mandate that one or both adjacent phases be re-synthesized with explicit constraints. Most powerful, most expensive.

Recommend teeing this up as a single AskUserQuestion early in session 2 before drafting §6 body. My weak prior is **β (propose-patch)** — flag-only loses the seam reviewer's value, force-re-prompt risks unbounded retry chains. But Andy should pick.

Other session 2 items (mostly mechanical once §§4–6 are decided):

- §4 — full precondition rule set (one rule per entry point + cross-entry rules like "etl_version_set must match what the upstream payloads were generated under").
- §5 Pattern A — periodization decomposition (how 3B's `phase_weeks` maps to per-phase synthesis calls); seam set (which phase boundaries get reviewed); convergence mechanic (how many seam-review-then-revise rounds before bailing to best-effort).
- §6 Pattern B — validator rule set (intensity distribution check, equipment-availability check, injury-exclusion check, etc.); retry mechanic (capped retries; on-cap behavior); best-effort fallback shape.

After session 2 lands, sessions 3–5 cover §§8–14 (coaching flag rule set fleshed out; cost / latency / storage; test scenarios; misc) + the end-of-PR `CLAUDE.md` + backlog bump.

---

## 6. Open items pinned this session (in §12 stub)

The §12 stub now carries 14 forward-pointers. The four notable Stage B additions:

1. **Layer 4.5 — Joint Session Coordinator.** Its own spec, separate file. Post-pass approach picked (D6). Lands when team-features track activates.
2. **Tiered tight/loose plan horizon — HELD (D7).** Substantive future direction; revisit post-v1-launch with cost/quality data.
3. **Multi-day race plan post-race analytics.** `RacePlan.segments[*]` doesn't include athlete-checkin shape. Add when race-execution surface is designed.
4. **Race-week-brief trigger policy.** Currently flagged "single fire at 14 + athlete-triggerable re-runs"; tune post-launch (daily? once at 14, again at 7, again at 1?).

The other 10 forward-pointers carry over from Stage A unchanged (LLM seam-reviewer authority, prompt-body designs ×5, plan-revert UX, Layer 5 consumption, per-phase intensity defaults, cost-cap × D-64-frequency interaction, Layer4ShapeInfeasibleError routing, seam-reviewer model downgrade).

---

## 7. Session-end verification (Rule #10)

Final pass over the file before composing this handoff:

| Check | Result |
|---|---|
| `Layer4_Spec.md` 736 lines | ✅ `wc -l` |
| 33 H2 headings (§1–§14 with §3.1–§3.5 + §7.1–§7.14 sub-headings) | ✅ `grep -c "^##"` |
| Header decisions block lists D1–D7 with Andy 2026-05-16 attribution | ✅ Read |
| §3.4 `llm_layer4_race_week_brief` present with full param table + `race_week_brief_requires_event_mode` error | ✅ Read |
| `Layer4Payload.mode` enum has all 4 values; `race_week_brief` + `race_plan` payload fields present | ✅ Read |
| `PlanSession` has `session_index_in_day` + `time_of_day` fields | ✅ Read |
| §7.12 schema rules: max-2-per-day, no-strength+strength, no-two-hards, at-least-one-cardio invariants present | ✅ Read |
| §7.13 `RaceWeekBrief` + `KitItem` present | ✅ Read |
| §7.14 `RacePlan` + `RaceSegment` + `TransitionSpec` + `PacingStrategy` + `FuelingStrategy` + `Contingency` present | ✅ Read |
| §8 stub Taper auto-emit table (5 rows) present | ✅ Read |
| §12 stub Layer 4.5 + Tiered-horizon + Multi-day-analytics + Race-week-brief-trigger pointers present | ✅ Read |
| §2 multi-athlete bullet rewritten to point at Layer 4.5 (no "out of v1 scope" framing) | ✅ Read |
| Branch ahead of `main` by 2 commits (Stage A `08b4f20` + Stage B `effbb48`); push successful | ✅ `git log` + push response |
| No CLAUDE.md / Backlog bump (per Stage-A-commit deferral rule) | ✅ `git diff --stat` shows only Layer4_Spec.md touched in Stage B |

---

## 8. Operating notes for session 2

1. **First re-read** (per `CLAUDE.md` Rule #13): re-read CLAUDE.md before any other context-load.
2. **Second re-read**: this handoff in full, then `Layer4_Spec.md` in full (header decisions block + §1 + §2 + §3.4 + §7.13 + §7.14 + §12 stub specifically).
3. **Do not bump CLAUDE.md or backlog** until the spec is structurally complete (all of §§4–14 drafted). The bump lands at end-of-arc per the Stage-A-commit rule.
4. **Tee up the seam-reviewer-authority decision** (α/β/γ per §5 above) early in the session as a single AskUserQuestion before drafting §6 body. Don't draft §6 without Andy's pick.
5. **Stop-and-ask trigger #2 still applies**: per-phase / per-tier / single-session / seam-reviewer / race-week-brief prompt-body designs are explicitly OUT of session 2. Each defers to its own focused session. Session 2 defines the contracts; the prompts are downstream work items.
6. **Cost/latency mentions** in §§9–10 stay numerically informal until session 3+ (post-§§4–6 lock-in). Andy explicitly accepted "design well, cut later if too costly" as the Stage A topology guidance; same posture stands until measurement data exists.
7. **Schema-readiness for Layer 4.5**: `PlanSession` natural key is `(plan_version_id, date, session_index_in_day)`. Layer 4.5 will eventually add a `joint_session_id` FK on `plan_session` rows that supersedes the solo `session_id` per §7.11 versioning semantics. Do NOT pre-add the `joint_session_id` field in session 2 — it lands with the Layer 4.5 spec, not here.

---

## 9. Carry-forward from PR17 (informational)

PR17 §5.0 named one open verification owed to a future session: `routes/body.py` `/body` POST round-trip on Vercel after the dead-branch strip. Andy mentioned in this chat that PR17 §5.0 passed; if confirmed, the carry-forward chain can drop it when the next end-of-arc CLAUDE.md bump happens. Not actioned this session (no CLAUDE.md / backlog touch this session per §3 deferral rule).

PR15's `/profile?tab=schedule` round-trip from PR15 §5.0 is the other open carry-forward; status not confirmed in this chat.

---

**End of handoff.**
