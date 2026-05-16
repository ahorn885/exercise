# Plan Refresh Tiers — D-64 Design

**Version:** 1.0
**Date:** 2026-05-15
**Status:** Design decisions locked; spec rewrite into authoritative location TBD (likely a new section in `Control_Spec` and/or a Layer 4 spec when Layer 4 lands).
**Backlog row:** D-64 (new this session)
**Track:** Plan-execution design wave — first of two new D-rows surfaced by Andy 2026-05-15 (sibling: D-63 on-demand workout).
**Affects:** Layer 4 plan-gen (consumer); Layer 3A/3B/2A-2E (cascade re-runs); Layer 1 athlete profile (read-only); new athlete UX (button + modal); new telemetry rows (`plan_refresh_log`); plan-version history surface.
**Cross-references:**
- `Control_Spec_v7.md` §4 (partial-update model — D-64 is the athlete-initiated counterpart to data-change-triggered cascades).
- `Layer3_3A_Spec.md` + `Layer3_3B_Spec.md` (cascade nodes consumed by all three tiers).
- `OnDemand_Workout_D63_Design_v1.md` — sibling design doc; D-63's post-completion CTA fires a D-64 T1 with the on-demand workout's NL context.
- `Athlete_Onboarding_Data_Spec_v5.md` (Layer 1 source-of-truth read by the cascade).

---

## 1. Purpose

Plans are generated once at onboarding and then evolve. Two existing mechanisms move them forward: (a) **data-change-triggered cascades** (the `Control_Spec_v7` §4 partial-update model — athlete edits a field, downstream layers re-run); (b) **scheduled re-evaluation cadence** (D-57, deferred). Both are reactive — the system updates when something it can detect changes.

Missing: an **athlete-initiated** refresh. Reasons the athlete wants to refresh that the system can't detect by itself:
- Soft state ("I'm tired this week, ease the next few days")
- Unrecorded equipment/location changes ("I'm at my in-laws for the weekend")
- Subjective fitness shifts ("I feel stronger than the plan assumes")
- Context the athlete hasn't bothered to type into a structured field ("I just got a new MTB")
- A periodic check-in habit ("Sunday evening, regenerate the next 4 weeks")

D-64 defines **three tiers** of athlete-initiated plan refresh, scoped by horizon:

| Tier | Horizon | Use case |
|---|---|---|
| T1 | Next 2 days (rolling) | Quick fix — energy, equipment-of-the-moment, "make tomorrow easier" |
| T2 | Next 7 days (rolling) | Weekly check-in — "regenerate the rest of the week" |
| T3 | Next 28 days (rolling) | Big update — new fitness signal, race-block re-eval, OR initial plan generation when none exists |

Each tier is athlete-triggered via a button (no auto-fire), accepts an optional natural-language context note, and runs a tier-appropriate subset of the layer cascade. NL context is parsed by an LLM intent classifier that may **add** upstream layer re-runs to the cascade (e.g., NL mentions an injury → 2D re-runs).

This is a **core differentiator surface** (Differentiator #1 — Plan iteration as situations change) made athlete-explicit instead of system-reactive.

---

## 2. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Tier horizon shape | **T1 = next 2 days rolling; T2 = next 7 days rolling; T3 = next 28 days rolling (or initial plan generation when none exists).** | Andy 2026-05-15. Rolling windows from `today` avoid edge-of-week awkwardness (athlete refreshes Tuesday → T2 covers Tue-next-Mon, not "the rest of this calendar week"). T3 doubling as initial-plan-gen path means there's one "create or update the long-horizon plan" surface, not two. |
| 2 | Trigger mechanism | **Athlete-initiated button + optional free-text context textarea.** No auto-fire. Athlete owns the decision to refresh. | Athlete-explicit by design. The `Control_Spec_v7` §4 partial-update model handles data-change-triggered cascades; D-64 is the complementary athlete-driven surface. Auto-firing T2/T3 would conflict with athlete-as-decision-maker framing. |
| 3 | NL context handling | **Free-text textarea + LLM intent parser → upstream layer triggers.** Parser classifies NL intent, may add layer re-runs to the tier's default cascade. | Andy 2026-05-15. Captures soft signals (fatigue, life events, subjective fitness) that structured fields miss. LLM parsing routes to specific upstream layers (2D injury, 2C equipment, 2E nutrition, etc.) so the cascade is precise. |
| 4 | Default cascade per tier | **T1: Layer 3A (athlete state) + Layer 4 (next 2 days).** **T2: Layer 3A + Layer 3B + Layer 4 (next 7 days).** **T3: Layer 2A/B/C/D/E + Layer 3A/B/C/D + Layer 4 (next 28 days).** NL intent can ADD upstream re-runs to any tier (e.g., T1 + "I just hurt my ankle" triggers 2D + 3A + Layer 4). | Tier scope drives cascade depth. Short-horizon refreshes don't need the full upstream re-eval; long-horizon refreshes do. NL intent is additive — it never reduces the cascade, only expands. |
| 5 | Button placement | **Both `/dashboard` AND training plan view.** | Andy 2026-05-15. Discoverability (every login sees it) + contextual access (next to the plan it modifies). |
| 6 | Frequency caps | **Soft cap with override:** warning if athlete triggers T3 more than once per 7 days; T2 more than once per 2 days; T1 more than 3× per day. Allow override; log to telemetry. | Andy 2026-05-15. Cost protection without nagging. Athlete owns the override decision; system surfaces the cost signal. |
| 7 | Concurrency | **Block re-trigger while a refresh is in flight.** UI shows "Refresh in progress…"; second click is a no-op. | Avoids race conditions in plan-version writes. Refreshes are short-lived (seconds-to-tens-of-seconds expected); blocking is simpler than queueing. |
| 8 | Failure handling | **Atomic.** New plan version commits only if the cascade completes successfully end-to-end. Any layer failure → rollback (previous plan version stays active); athlete sees "Refresh failed: <reason>" + retry button. | Row-invalidation versioning model already supports atomic version writes. Mid-flight failure must NOT leave the athlete with a partially-updated plan. |
| 9 | Diff visibility | **New plan rendered with subtle "updated" badge on changed sessions.** "View what changed" expandable per session shows old-vs-new fields. Plan-summary view shows "N sessions changed" header. | Honest about what the refresh did; doesn't force diff review on every athlete. |
| 10 | Versioning + history | **Each refresh writes a new plan version.** Prior versions retained per `Control_Spec_v7` row-invalidation model. Athlete can revert to any prior version via a plan-management UI (UI itself is out of scope this spec; storage shape is in scope). | Reuses existing versioning. Revert is the safety valve when athlete decides the refresh was a mistake. |
| 11 | Telemetry | **`plan_refresh_log` table** captures: tier, athlete_id, NL text, parsed-intent JSON, layers re-run, cascade duration, output-diff size (sessions changed), athlete-keep vs revert decision, token cost, success/failure. | Operational observability + cost tracking + future product analytics ("which tier do athletes use most? which NL signals predict reverts?"). |
| 12 | NL intent parser | **Runtime LLM call** (Claude Sonnet/Opus per Layer 4 conventions when Layer 4 lands; v1 stopgap can use the existing `coaching.py` Claude surface). Cached deterministically per `(athlete_id, NL_text_normalized)` since identical input from the same athlete should produce identical intent classification. **Prompt body design deferred to its own spec session** (stop-and-ask trigger #2). This doc defines the input/output CONTRACT; the prompt text itself lands separately. | NL parsing is athlete-specific and runtime, not Layer 0 reference. The prompt body needs its own design pass; doing it inline here would conflate D-64's framework decisions with prompt-engineering work. |

---

## 3. Tier definitions

### 3.1 T1 — Next 2 days

**Horizon:** today + tomorrow (rolling from "now"). If today's session is already completed, T1 covers tomorrow + day-after instead.

**Default cascade:** Layer 3A re-eval + Layer 4 (with `scope_days=2, start_date=today_or_next_uncompleted`).

**Use cases:**
- "I'm wiped from yesterday — make tomorrow easier"
- "I'm at my in-laws today and tomorrow — adjust to bodyweight"
- "I just did an unscheduled long ride; absorb that into the next two days"

**NL context examples + parsed intent:**
- "I'm tired" → 3A re-eval picks up athlete state shift; no upstream changes.
- "I'm at my in-laws — only have a yoga mat" → adds 2C re-run (location-bound equipment view); 3A re-eval; Layer 4.
- "I tweaked my knee" → adds 2D re-run (injury risk); 3A re-eval; Layer 4. **May trigger HITL gate at Layer 3D** if 2D produces a blocker-severity item.

**Layer 4 input contract additions (when Layer 4 specs land):**
- `refresh_tier: 'T1'`
- `scope_start_date: <date>` + `scope_end_date: <date+2>`
- `nl_context_text: <athlete's text>` (passed through for the synthesizer to weight)
- `parsed_intent: { triggers_2d: bool, triggers_2c_locales: [<locale>], fatigue_signal: <enum>, ... }`

### 3.2 T2 — Next 7 days

**Horizon:** today through today+6 days (rolling).

**Default cascade:** Layer 3A + Layer 3B (viability + periodization re-eval) + Layer 4 (with `scope_days=7`).

**Use cases:**
- "Regenerate the rest of the week"
- "I'm sick — back off the week"
- "I have an unexpected travel day Wednesday"

**3B inclusion rationale:** 7-day horizon is long enough that periodization shape may shift (e.g., athlete reports significant fatigue → 3B re-evaluates the week's intensity distribution; phase may pull back). T1's 2-day horizon doesn't justify 3B since periodization operates on weekly granularity.

### 3.3 T3 — Next 28 days

**Horizon:** today through today+27 days (rolling). Approximately 4 weeks.

**Default cascade:** Layer 2A + 2B + 2C + 2D + 2E + Layer 3A + 3B + 3C + 3D + Layer 4 (with `scope_days=28`). Effectively: full upstream re-eval through Layer 3, then plan synthesis for the next 28 days.

**Use cases:**
- "Sunday-evening monthly check-in: regenerate the next 4 weeks"
- "Major fitness update — I just PR'd; reassess everything"
- "Race date moved — re-eval against the new event date"
- **Initial plan generation** when no plan exists yet (athlete completes onboarding → T3 button is the path to first plan)

**Layer 4 internal handling:** the spec defines T3 SCOPE as 28 days; Layer 4 may snap to whole-week boundaries internally (e.g., generate the current calendar week + 3 following weeks) for periodization coherence. Spec defines the athlete-facing horizon; Layer 4 owns the generation strategy within it.

**HITL gate at Layer 3D:** T3 always runs the full 3D gate (since it runs all 2x and 3x layers). If 3D surfaces blockers, T3 cannot complete until athlete resolves them. T1 and T2 only hit 3D if NL intent triggered an upstream layer that produced HITL items.

---

## 4. Athlete UX

### 4.1 Button placement (both surfaces)

**Dashboard surface (`/dashboard`):**
- Top-level card titled "Refresh your plan" with three radio options (T1 / T2 / T3) and a textarea for NL context.
- Dashboard surface targets the every-login discovery path.

**Training plan view surface (`/training` or equivalent — exact route TBD with Layer 4 UI spec):**
- Inline "Refresh from here" button on each day's session card → defaults to T1 with the picked day as scope-start.
- "Refresh the week" button at the week header → T2 with the week's start as scope-start.
- "Refresh the full plan" button at the plan header → T3.
- Contextual surface targets athletes who are already looking at the plan.

### 4.2 NL context modal

After tier selection, a single modal:
- "What changed? (optional)" — free-text textarea, ~500 char soft limit.
- Examples shown as placeholders: "I'm tired", "I tweaked my ankle", "Travel Wed-Fri", "I just got a new MTB".
- "Refresh" submit button + "Cancel".
- No structured prompts — the athlete writes whatever's relevant (Andy 2026-05-15 picked free-text + parsing over structured prompts).

### 4.3 In-flight feedback

After submit:
- Modal closes; persistent toast/banner: "Refreshing your plan… (T1 — next 2 days)" with spinner.
- Concurrency: if athlete navigates away or clicks the button again, second invocation is a no-op with toast "Refresh already in progress".
- Cascade typically completes in seconds; long-running cascades (T3 with full 2x re-runs) may take tens of seconds.

### 4.4 Completion feedback

On success:
- Banner flips to "Plan refreshed — N sessions updated" with [View changes] link → expanded diff view.
- Updated sessions in the plan view show a subtle "updated" badge (e.g., dot indicator) for ~24 hours after the refresh.

On failure:
- Banner flips to "Refresh failed: <reason>" with [Retry] button.
- Plan unchanged (atomicity per Decision #8).
- Failure logged to `plan_refresh_log`.

### 4.5 Frequency-cap UX

When athlete triggers a refresh that exceeds the soft cap (Decision #6):
- Modal-confirm: "You've refreshed 3 times today. Each refresh costs ~$X in compute. Continue?" + [Refresh anyway] + [Cancel].
- Override logged to `plan_refresh_log.cap_overridden=TRUE`.

---

## 5. NL intent parser — input/output contract

**Prompt body deferred to its own spec session** (stop-and-ask trigger #2). This section defines the contract Layer 4 will consume.

### 5.1 Input

```python
@dataclass
class IntentParserInput:
    nl_text: str                    # athlete's free-text input
    tier: Literal['T1', 'T2', 'T3']
    athlete_locales: list[str]      # athlete's locale slugs (for "at my in-laws" → matching)
    athlete_active_injuries: list[str]  # active injury site/type for "tweaked my knee" → existing-injury-vs-new disambiguation
```

### 5.2 Output

```python
@dataclass
class ParsedIntent:
    # Upstream layer re-run flags (added to tier's default cascade; never subtracted)
    triggers_2a_discipline: bool        # "I'm starting kayaking" → 2A
    triggers_2b_terrain: bool           # "I'll be in the mountains" → 2B
    triggers_2c_equipment: list[str]    # locale slugs needing 2C re-run; empty list = none
    triggers_2d_injury: bool            # any injury mention → 2D
    triggers_2e_nutrition: bool         # "GI issues last race" → 2E

    # Soft signals (passed to Layer 4 as context, not full re-runs)
    fatigue_signal: Literal['fresh', 'normal', 'tired', 'wiped']  # default 'normal'
    sickness_signal: Literal['none', 'recovering', 'active']      # default 'none'
    motivation_signal: Literal['low', 'normal', 'high']           # default 'normal'

    # Free-text passthrough (always included for Layer 4 context)
    raw_text: str

    # Confidence + ambiguity
    parser_confidence: Literal['high', 'medium', 'low']
    ambiguity_notes: str | None     # if parser couldn't classify cleanly, what was ambiguous
```

### 5.3 Caching

Cache key: `(athlete_id, sha256(nl_text_normalized), parser_prompt_version)`.

`nl_text_normalized` = lowercase + whitespace-collapsed. Same athlete pasting "I'm tired" twice gets the same parse.

`parser_prompt_version` invalidates the cache when the prompt body is revised.

### 5.4 Failure mode

Parser API failure → return `ParsedIntent` with all flags FALSE, all signals at default, `parser_confidence='low'`, `ambiguity_notes='Parser unavailable; running default cascade only.'`.

The refresh proceeds with the tier's default cascade. Athlete gets a degraded refresh, not a failed one.

---

## 6. Cascade execution

### 6.1 Layer execution order

Per `Control_Spec_v7` §4: 2x layers run first (in parallel where independent), then 3A → 3B → 3C → 3D, then Layer 4.

D-64 respects this ordering. Tier scope only narrows which 2x/3x nodes run; the order among the running nodes is unchanged.

### 6.2 Atomic version write

Every refresh produces:
1. New rows in 2x output tables (only the layers that re-ran)
2. New rows in 3A/3B/3C/3D output tables (only the layers that re-ran)
3. New rows in Layer 4 plan-session output tables (scoped to tier's date window)

All writes share a single `plan_version_id` set at refresh start. Commit-or-rollback boundary is the full set. Mid-cascade failure → none of the new rows commit; previous `plan_version_id` remains active.

### 6.3 Out-of-scope sessions (T1 / T2)

T1 covers next 2 days. Sessions on day 3+ are NOT regenerated; they keep their previous `plan_version_id` row.

When athlete views the plan, the resolver shows: days 1-2 from new version, days 3+ from prior version. Plan-version pointer is per-day, not per-plan.

(Implementation: `plan_session.plan_version_id` per session, not a single per-athlete pointer. Layer 4 spec will detail.)

---

## 7. Storage

### 7.1 New table: `plan_refresh_log`

```sql
CREATE TABLE plan_refresh_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tier TEXT NOT NULL CHECK (tier IN ('T1', 'T2', 'T3')),
    nl_text TEXT,
    parsed_intent JSONB,
    layers_run TEXT[] NOT NULL,           -- e.g. {'3A', 'Layer4'} for T1 default
    scope_start_date DATE NOT NULL,
    scope_end_date DATE NOT NULL,
    plan_version_id_before BIGINT,         -- FK to plan-versions table (TBD)
    plan_version_id_after BIGINT,          -- NULL on failure
    duration_ms INTEGER,
    sessions_changed INTEGER,
    token_cost_estimate INTEGER,           -- sum of LLM tokens across cascade
    success BOOLEAN NOT NULL,
    failure_reason TEXT,                   -- NULL on success
    cap_overridden BOOLEAN NOT NULL DEFAULT FALSE,
    reverted_at TIMESTAMPTZ,               -- if athlete later reverted this version
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX plan_refresh_log_user_triggered_idx ON plan_refresh_log (user_id, triggered_at DESC);
```

### 7.2 Plan-version table

D-64 assumes a per-session `plan_version_id` foreign key. The plan-versions table itself is **out of scope this spec** (lands with Layer 4). D-64 specifies that:
- Each refresh allocates a new `plan_version_id`.
- Sessions written by the refresh point to it.
- Out-of-scope sessions retain their prior `plan_version_id`.
- Revert UI flips per-day pointers back to the prior version.

---

## 8. Frequency caps

| Tier | Soft cap | Override |
|---|---|---|
| T1 | 3 per 24h | Allowed with confirmation |
| T2 | 1 per 48h | Allowed with confirmation |
| T3 | 1 per 7d | Allowed with confirmation |

Enforced server-side (count `plan_refresh_log` rows for `user_id` in the window). Cap thresholds tunable per athlete account in future (out of scope this spec — single global threshold for v1).

Override logged with `cap_overridden=TRUE`. No hard cap — Andy's "athlete owns the decision" framing.

---

## 9. Implementation gating

D-64 implementation **gates on Layer 4 spec landing** because:
- T1/T2/T3 cascade outputs are consumed by Layer 4 plan-gen, which doesn't yet have an input contract.
- The plan-version table shape lives in Layer 4 spec (D-64 references it but doesn't define it).
- The diff view (Decision #9) requires Layer 4's session output schema.

**Pre-Layer-4 stopgap (optional, v1 path):** a degraded T1-only surface against the existing `coaching.py` v1 surface — athlete clicks "Refresh next 2 days", system regenerates the next two days against the v1 single-Claude-call coaching prompt with the NL context appended. No real layer cascade; no version history; no diff. Acceptable as a placeholder; loses most of the framework's value. **Recommend: don't ship the stopgap; wait for Layer 4.**

---

## 10. Open items

- **Layer 4 spec doesn't exist.** D-64 implementation blocks on Layer 4 spec landing.
- **NL intent parser prompt body deferred** to its own spec session per stop-and-ask trigger #2. D-64 defines the input/output contract; the prompt text lands separately.
- **Plan-revert UI** is out of scope this spec. D-64 specifies storage shape (per-day version pointer); the UI to flip pointers back lands with the plan-management UI work.
- **Cost-estimate accuracy.** Token-count estimate per cascade (Decision #6 + Decision #11) requires Layer 4 + 3A/3B prompt-body sizes to be known. Until Layer 4 lands, frequency-cap warnings show generic "compute cost" copy without dollar amounts.
- **Per-athlete cap tunability** deferred. v1 ships single global thresholds.
- **Revert UX** — "athlete reverts a refresh, then immediately re-refreshes" — interaction with frequency caps. Should a revert reset the cap window? Probably yes (athlete is iterating on the same intent), but flagged for tuning post-deploy.
- **Multiple concurrent athletes** triggering refreshes against shared inputs (e.g., joint training overlays per `Athlete_Onboarding_Data_Spec_v5.md` §L) — out of scope; team-coordination is differentiator #5 territory and lands with team features.
- **HITL gate interaction.** Cascade failure due to a 3D blocker is a "soft failure" (athlete can't complete the refresh until they resolve the blocker, but the cascade itself ran correctly). UX should distinguish "system error" from "you have an open HITL item blocking this refresh." Spec'd at the Layer 4 / 3D level when Layer 4 lands.
- **Telemetry retention.** `plan_refresh_log` will grow indefinitely. Same retention question as `webhook_events` (D-62). Likely lands in the same retention-prune cron when D-62 ships.

---

## 11. Test scenarios (forward-pointers)

When D-64 implements:

1. T1 with empty NL context → cascade runs Layer 3A + Layer 4 only; sessions on days 1-2 update; sessions on days 3+ unchanged; `plan_refresh_log` row recorded.
2. T1 with "I'm tired" → parser returns `fatigue_signal='tired'`; cascade unchanged from #1; Layer 4 weights fatigue signal in synthesis; `plan_refresh_log.parsed_intent` records the signal.
3. T1 with "I tweaked my ankle" → parser returns `triggers_2d_injury=TRUE`; cascade runs 2D + 3A + Layer 4; if 2D produces a blocker, refresh fails with HITL-gate message.
4. T2 from Wednesday → covers Wed-Tue (7 rolling days); cascade runs 3A + 3B + Layer 4.
5. T3 with no prior plan → initial plan generation path; full cascade; plan_version_id allocated for the first time.
6. T3 within 7 days of prior T3 → soft-cap warning; athlete confirms; cascade runs; `cap_overridden=TRUE`.
7. Concurrent click → second click no-op'd; toast "Refresh in progress".
8. Cascade failure mid-flight (mock 2C error) → previous plan_version_id retained; athlete sees "Refresh failed: 2C unavailable"; retry succeeds.
9. Athlete reverts a T2 refresh → per-day plan_version_id pointers flip back; `plan_refresh_log.reverted_at` set.
10. NL parser API down → returns degraded `ParsedIntent`; refresh proceeds with default cascade; `plan_refresh_log.parsed_intent.parser_confidence='low'` recorded.

---

## 12. Gut check

**What's right:**
- **Athlete-explicit** is the missing surface. Data-change cascades + scheduled re-eval cover system-detected reasons to refresh; NL context covers the human reasons.
- **Three tiers map to real athlete intent.** "Make tomorrow easier" (T1), "regenerate the week" (T2), "monthly big update" (T3). Each tier's horizon matches the question athletes actually ask.
- **NL parsing is the smart middle ground.** Free-text alone (no parsing) loses cascade routing; structured prompts alone are friction. LLM intent classification gets both — athlete writes naturally; system routes precisely.
- **Atomic versioning + revert is the safety valve.** Athletes will hit refresh and regret it; the revert path means they can.
- **Soft caps + override respects athlete agency.** Hard caps are paternalistic and would push athletes to game them.

**Risks:**
- **NL parser accuracy is unproven.** Parser routes the cascade — wrong routing means wrong cascade. Mitigation: parser_confidence flag + ambiguity_notes surfaced in athlete-facing diff so they can spot mis-routing; revert path lets them undo.
- **T3 cost is real.** Full cascade is expensive (5 Layer-2 nodes + 4 Layer-3 nodes + Layer 4 synthesis). Soft cap protects the worst case but doesn't prevent it. Telemetry will reveal whether athletes regularly override.
- **Revert UX could be confusing.** "I refreshed and reverted; now my plan looks like before — but did anything actually change in the database?" needs to be made clear (yes — revert wrote a new pointer; the old version is preserved in history).
- **Frequency-cap thresholds are guesses.** No production traffic to tune against. Plan to revisit after first cohort using D-64.
- **Parser prompt body undefined.** Spec defines the I/O contract but the prompt itself is the thing that determines accuracy. Building a prompt that reliably classifies "I tweaked my ankle" → `triggers_2d_injury=TRUE` while NOT mis-classifying "my old ankle injury feels better" → `triggers_2d_injury=TRUE` is real prompt-engineering work.

**What might be missing:**
- **Multi-athlete coordination.** Athlete A and athlete B share a joint training overlay (§L). Athlete A triggers T2; should B's plan re-run too? Probably yes but out of scope this spec.
- **Notification/coaching layer.** When cascade surfaces a real signal (athlete keeps reporting fatigue across multiple T1s), there should be a coaching observation: "you've reported tired 4 times this week — consider a recovery week." Not in D-64; lives in a future Layer 5 advisory or a separate "coaching observations" surface.
- **Refresh-while-doing-a-session.** Athlete is mid-workout, opens app, hits refresh. Should the in-progress session be regenerated? Recommend: no — in-progress sessions are immutable; refresh starts from the next session. Spec'd at session-state level when Layer 4 lands.
- **Cross-tier interaction.** Athlete fires T1, then T2 within minutes. Does T2 supersede T1's writes? Yes (T2 covers days 1-7, T1 covered 1-2 — T2's day-1-2 writes overwrite T1's). Plan-version pointers handle this correctly via per-day update; flagged for verification when implemented.

**Best argument against this scope:**
The framework is real but the *immediate need* is small. At N=1 athlete (Andy), a single button "regenerate my plan" would cover 90% of the use cases. The three-tier framework optimizes for cohort-scale where athletes have varied patterns (some never refresh; some refresh every Sunday; some refresh constantly when traveling). Building the framework now adds spec surface that doesn't pay off until cohort > 10.

Counter: the alternative is to ship a single-button refresh now, then re-spec when the framework is needed — and the re-spec means migrating the single-button storage shape, the UI, the cascade choices, and the telemetry. The cost of building the framework once is lower than the cost of building it twice. Andy's "build the right abstraction now" framing (carried from D-60) applies. Same logic.

Counter to the counter: only the bits where migration cost is real matter. The `plan_refresh_log` schema, the per-day plan_version_id pointer, the atomic-version-write boundary — those are storage decisions that ARE expensive to migrate later. The button-placement, the modal copy, the diff-visibility UX — those are cheap to evolve. PR-by-PR shipping should prioritize the storage + cascade decisions; UX can iterate.

Net: ship the framework's storage + cascade design as spec'd; iterate the UI as athletes come online.

---

*End of Plan_Refresh_D64_Design_v1.md.*
