# V5 — #196 Phase 4: Recovery-Aware Planning (LLM-soft) — Kickoff Handoff (2026-06-28)

**Status:** NOT STARTED — **STOP-AND-ASK** before any code (Trigger #1 prompt design + #3 cross-layer). This kickoff scopes the work and lists the decisions to put to Andy in `/plan`; it does **not** pre-decide them. · **Epic:** #196 (OPEN) · **Design:** `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md`.

> **▶ START HERE NEXT SESSION:** enter `/plan`, present the options in §4 (channel + surfaces + soft-guidance language + freshness gating + cache-key handling), AskUserQuestion, **wait for Andy's confirmation**, then build the smallest first slice he picks. Do **not** implement first.

---

## 1. Goal (one line)

Make the Layer-4 plan generator **condition on the athlete's recovery state** — suppressed HRV, sleep debt, poor readiness — so a plan/refresh eases load when the body says so, via **LLM-soft guidance** (pre-ratified mechanism, design §; Andy 2026-06-23). Not a deterministic load-cut: the prompt is *informed*, the LLM decides.

## 2. Where Phase 4 sits (what's already done)

Phase 2 is now **consumer-ready**:
- **Slice 2.1** built `canonical_daily_wellness` + the writer; **2.2** hooked it into every ingest path + backfill; **2.3** (just shipped, this branch) repointed the first reader (`layer3a.integration.q_layer3A_recent_wellness`) at the table and made the merge byte-identical to the old inline path.
- **`recent_wellness` already reaches the Layer-3A LLM** (`assemble_layer3a_integration_bundle` → `llm_layer3a_athlete_state`), which digests it into the **`Layer3APayload`** (`current_state` / `recent_trajectory` / `data_density` / `notable_observations`). `connected_providers.has_recent_sleep / has_recent_hrv / has_recent_workouts` are computed too.

What's **missing** is the **Layer-4 consumption** — the plan-gen prompts don't yet act on recovery state. (Note: the `recovery` references already in `layer4/per_phase.py` are about *recovery-session programming* — a structural plan element — **not** wellness-driven recovery awareness. Don't conflate them.)

## 3. The consumption surfaces (anchors)

The Layer-4 plan-gen prompt bodies that would carry the recovery-aware guidance:
- **`layer4/per_phase.py`** — PerPhase synthesis (the main plan-build prompt).
- **`layer4/plan_refresh_t2.py`** + **`layer4/plan_refresh_t3.py`** — the Refresh tiers (most *reactive* to incoming data — the natural first slice).
- **`layer4/race_week_brief.py`** — RaceWeekBrief.
- **`layer4/single_session.py`** — single-session synthesis (if in scope).

Inputs available to thread: the **`Layer3APayload`** digest (already recovery-aware in substance) and/or the raw **`Layer3AIntegrationBundle.recent_wellness`** + `connected_providers` (`layer4/context.py:1029`).

## 4. Decisions for Andy (the `/plan` agenda)

1. **Channel — digest vs raw vs hybrid.** (a) Rely on the **3A digest** (`current_state`/`recent_trajectory`/`notable_observations`) that already folds wellness, and just add prompt language telling Layer-4 to act on it; (b) thread **raw** `recent_wellness` + `has_recent_*` into the Layer-4 prompts; (c) **hybrid** — have 3A emit an explicit `recovery_state` field that Layer-4 reads. (a) is the least new surface (no new cross-layer input → smallest cache-key blast radius); (b)/(c) are more direct but add inputs to the Layer-4 payload hash. **Recommend leaning (a)** unless the digest proves too lossy — confirm with Andy.
2. **Which prompts first.** All four at once, or **start with `plan_refresh` T2/T3** (most reactive, smallest blast radius) and fold PerPhase/RaceWeekBrief after? Recommend a single first slice.
3. **The soft-guidance language (Trigger #1).** The actual prompt-body wording — coaching-voice, evidence-grounded, no hype (CLAUDE.md). Must be drafted and **signed off** before it ships.
4. **Freshness gating.** Only inject recovery guidance when `has_recent_hrv`/`has_recent_sleep` is true; how to phrase "no recent recovery data" so the LLM doesn't hallucinate a state. (Andy's wellness data is empty until he re-uploads post-#934 — so the no-data path is the *default* path today.)
5. **Cache-key / invalidation (Trigger #3).** Any new input folded into a Layer-4 prompt changes that layer's payload hash → re-runs. It MUST be **day-anchored / deterministic** (the D-77 / `last_sync` lesson — a sub-day timestamp drifts the key every pass). If we go channel (a), the 3A digest already carries this discipline; channels (b)/(c) need the same care on the new field.

## 5. Read order (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = Slice 2.3). 3. `CARRY_FORWARD.md` → "#196 … Phase 2 — canonical daily-wellness layer" (the "Then Phase 4" bullet). 4. This kickoff + the Slice 2.3 closing handoff + `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md`. 5. The §3 anchor files + `layer4/context.py:Layer3APayload` (the digest) / `Layer3AIntegrationBundle` (the raw bundle). 6. `./scripts/verify-handoff.sh`.

## 6. Prereq (live verify only — not the design/unit work)
For a *live* spot-check that recovery guidance actually fires, wellness must flow: Andy re-uploads Garmin wellness zips after the #934 deploy → `daily_wellness_metrics` fills → the Slice-2.2 hook materializes `canonical_daily_wellness` → 3A digests it. The design + prompt-body work does **not** need live data.

## 7. Out of scope / parked
- `/wellness` chart repoint (optional Phase-2 cleanup) + `coaching.get_wellness_summary` (v1-only) — both deferred at Slice 2.3.
- #884 gear/craft is PAUSED mid-arc at slice 3b (slices 4→6 remain) — resume when Andy redirects.
