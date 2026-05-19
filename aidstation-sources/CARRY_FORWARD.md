# AIDSTATION — Carry Forward

Rolling-state for items spanning multiple sessions. **Edit in place** — don't duplicate this content in handoff narratives. The handoff references this file; doesn't restate it.

---

## Manual §5.0 walkthrough (Vercel)

53 scenarios accumulated. Andy walks after PR merges.

- 12 onboarding (D-66 §H.2 / §H.4)
- 6 nudge UI
- 6 Layer 3B Scope A
- 6 Layer 3B Scope B
- 5 Layer 3B Scope C
- 1 D-72 (locale-FK alignment)
- 7 D-73 Phase 1.2A (Neon schema spot-checks + profile-tab form regression + provenance regression)
- 6 D-73 Phase 1.2B (Neon schema spot-checks for 8 new tables + idempotency + index existence + FK behavior + regression)
- 4 D-73 Phase 1.2C (Neon schema spot-checks for 7 per-discipline §D tables + PK = user_id 1:1 shape + idempotency + regression)

See `PR_Verification_Status.md` for the per-PR §5.0 step-by-step state (✅ done / ⏸ blocked / 🟡 owed / ⚪ N/A / 🔴 bug). D-73 Phase 1.2A + 1.2B + 1.2C steps are spelled out in §5 of their closing handoffs.

## Doc-sweep nits

Small drift items to fold into upcoming sessions rather than ship as their own PR.

- `routes/onboarding.py:710` — docstring tense (stale "legacy `athlete_profile.target_event_*`" reference after D-66 Scope B/C). Fold into upstream arc Phase 4 or 5.
- `Layer4_Spec.md` §4.5 — source-pointer wording reflects D-72 obsolescence. Fold into Phase 5.1 orchestrator vertical slice.
- `Race_Events_D66_Design_v1.md` §8.3 — `mode='open_ended'` drift vs canonical `mode='no-event'` (per `Layer3BPayload.mode: Literal["event","no-event"]`). Fold into Phase 4.2 Layer 3B prompt-body session.

## Orthogonal carry-forwards (Layer 4 implementation track)

Layer 4 Steps 2 + 3 + 4a-4e of 8 COMPLETE. Remaining:

- **Step 4f** `llm_layer4_plan_create` Pattern A orchestration. Closes Layer 4 §14.3.4 Step 4 sub-arc. ~6-8 files. T3 cross-phase Pattern A lands here as a same-shape consumer.
- **Step 5** Cache layer — ✅ Shipped 2026-05-18.
- **Step 6** Pattern A orchestration polish — ✅ Shipped 2026-05-18.
- **Step 7** Live LLM integration — needs `ANTHROPIC_API_KEY`. Env-gated smoke test scaffolding can ship without the key; real call lands later.
- **Step 8** Telemetry tuning — calibrate validator thresholds against measured retry rates once Step 7 lands real data.

## D-66 Layer 3B caller-side rewire (queued)

Orchestrator currently reads `athlete_profile.target_event_*` for Layer 3B's event-mode input. Once the Layer 4 orchestrator is built (none exists yet — `layer4/` is the only runtime code), swap to `load_target_race_event_payload(db, user_id)`. ~3-4 files. Lands as Phase 5.1 of the upstream arc.

## Parallel tracks (independent of upstream arc)

- **D-50** wiring resumption — unblocked by D-58. PR1 scope: `provider_auth.py` helper + first real OAuth flow (COROS recommended) + COROS webhook recording + D-58 connect-step frontend integration.
- **D-52** Catalog Migration Phase 1 — fuzzy-match HITL alias audit.
- **D-54** SQLite collapse — ✅ Resolved 2026-05-16 (PR13).
- **D-55** Garmin onto `provider_auth` — **paused** until Garmin reopens API access.
- **D-57** Research re-evaluation cadence design.
- **D-58–D-61** Onboarding Design Wave — ✅ complete 2026-05-14.
- **D-62** `webhook_events` retention prune — tracked; lands alongside first real webhook handler.

## Tabled (not active)

- **Park-specific tag taxonomy** (PR18 follow-on) — `EQUIPMENT_CATEGORIES` is gym-centric; outdoor_park shared profiles render irrelevant gym checkboxes. Defer until park-locale usage exercises the seam.
- **Layer 4.5 — Joint Session Coordinator spec** — separate file; lands when team-features track activates.
- **Layer 5 spec** — parallel supplemental outputs (nutrition, supplements, 7-day clothing/conditions). Consumes `PlanSession.session_notes` + `cardio_blocks`.

---
