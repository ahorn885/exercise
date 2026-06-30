# Kickoff Handoff — Sign-up/Onboarding: Phase 1+2 Merging, Phase 3 Next
**Date:** 2026-06-30
**Branch merged:** `claude/pack-load-weighting-phase1-uy2kfz`
**PR:** [#1084](https://github.com/ahorn885/exercise/pull/1084) — opened, auto-merge armed (merge commit method, Andy's go 2026-06-30)
**Epic:** [#246](https://github.com/ahorn885/exercise/issues/246)
**Predecessor handoffs:**
- `V5_Implementation_SignupOnboarding_1067_PackLoadWeighting_Phase1_2026_06_30_Closing_Handoff_v1.md`
- `V5_Implementation_SignupOnboarding_223_PregnancyCapture_Phase1_2026_06_30_Closing_Handoff_v1.md`
- `V5_Implementation_SignupOnboarding_394_ScreeningUXPolish_Phase2_2026_06_30_Closing_Handoff_v1.md`

---

## §1 — What this handoff is

Not a closing handoff for new work — **Andy gave the go to merge** the work shipped on `claude/pack-load-weighting-phase1-uy2kfz`, so this records that merge plus the clear next step: **Phase 3**. Read this alongside the closing handoffs above for the actual implementation detail — this file is the pointer, not a re-narration.

**Correction caught while writing this handoff:** #1067 was already merged separately — PR [#1078](https://github.com/ahorn885/exercise/pull/1078), merge commit `eb18124`, on its own branch `claude/dreamy-curie-r1di5z`, *before* `claude/pack-load-weighting-phase1-uy2kfz` continued with #223 and #394. It is **not** part of PR #1084. `CURRENT_STATE.md`'s #1067 entry had drifted (still said "PR NOT opened") — fixed in the same bookkeeping pass that produced this handoff. Listed above as a predecessor handoff because it's still part of this arc's narrative, not because it's in #1084's diff.

## §2 — What's merging (PR #1084)

One PR bundling two Sign-up/Onboarding Consolidation Phase 1–2 slices, because both landed on one continued session branch (#1067 is separate — see the correction above):

1. **#223 — pregnancy-status capture.** `health_screening.flags` / `PREGNANCY` flag wired into `Layer1HealthStatus.pregnancy_status` + a profile toggle. Capture-only — the Layer 2E HITL-gate half stays deferred (#518, stop-and-ask trigger #4).
2. **#394 — health-screening UX polish.** D-80 (sensitive-field trust indicator), D-82 (voluntary mid-cycle update link), D-83 (reassessment-due dashboard nudge — plan-output note deferred, recipe in that closing handoff), D-84 (anti-skim delay), D-85 (settings read-view card). D-79 split out + scope-expanded to [#1083](https://github.com/ahorn885/exercise/issues/1083) (app-wide localization), iceboxed.

**Already merged separately, not part of #1084:** **#1067 — pack-load weighting + summary/edit/delete UX** (PR [#1078](https://github.com/ahorn885/exercise/pull/1078), merge commit `eb18124`). Deterministic `pack_load_readiness` tier in `layer3b/builder.py` (prior longest-carry duration + weight coverage outranks recent frequency); profile pack-load form collapses behind `<details>` once a record exists. Listed here for arc continuity only.

**Status at write time:** PR #1084 open, Vercel preview building, auto-merge armed (`MERGE` method per Andy's 2026-06-29 standing instruction — never squash/rebase). Subscribed to PR activity; will land once the three required checks (`Python unit suite (stubbed)` / `JS harness (jsdom)` / `Layer 0 integrity gate`) pass. No `layer0-apply` owed by either slice — no schema changes.

## §3 — Next: Phase 3 — #272 (SMS/WhatsApp invites) + #267 (passkeys), both via Twilio

Per the original phased plan (`CARRY_FORWARD.md`, Andy's D5 decision 2026-06-30): build both, via Twilio. Re-grounding needed at the start of that session — neither issue has been scoped against current code yet this arc. What's known from the issue text alone (re-confirm, don't trust blind):

**#272 — SMS/WhatsApp sign-up invites** (parent #262, `icebox`/`priority:low`):
> Send invites via SMS and WhatsApp [in addition to email]. Refs: `HANDOFF.md`.

**#267 — Passkey / WebAuthn sign-in** (parent #262, `icebox`/`priority:low`, 1 existing comment — read it first):
> Support passkey / WebAuthn authentication. Refs: `HANDOFF.md`.

Both are thin one-line issue bodies pointing at `HANDOFF.md` (a file, not this `handoffs/` directory — confirm it still exists and what it says before assuming scope). Both are heavier v1 infra than the Phase 1/2 capture-only slices just merged — this is a different shape of work (third-party integration + auth flow changes), not a deterministic-tier-and-a-form-field session. Budget a full session for re-grounding alone before writing code.

**Known surfaces (from CARRY_FORWARD.md's existing notes, not yet re-verified):**
- `routes/auth.py`, `mfa.py` — current auth/MFA code, the likely passkey integration point
- Invite-sending currently goes through email only (`email_helper.py`/`email_templates.py` per the existing pattern elsewhere in this codebase) — the SMS/WhatsApp path is new, via Twilio
- No Twilio integration exists yet anywhere in this codebase (confirm via grep before assuming a starting point)

**Before writing any code:**
1. Read `HANDOFF.md` (root) for whatever context the issue refs point to
2. Grep for any existing Twilio/WebAuthn/passkey scaffolding (none expected, but confirm — don't assume a blank slate without checking)
3. Re-confirm scope with Andy the same way #394 was handled this session — these are NOT a single cohesive feature (SMS+WhatsApp invites and passkey auth are unrelated to each other beyond "both via Twilio" for the first, and passkeys don't use Twilio at all — WebAuthn is a browser API, not an SMS feature). **Likely two separate sessions/PRs, not one** — flag this to Andy rather than assuming D5's "build both" meant "build both in one PR."
4. Passkey/WebAuthn work touches the login/auth flow — consider whether this trips **stop-and-ask trigger #5** (architectural alternatives with real tradeoffs) given it's a new auth mechanism alongside password + existing MFA, not obviously a capture-only slice like the Phase 1/2 work just merged.

## §4 — After Phase 3

Per the standing plan: roll up + close epic #246 once its remaining open children land — Phase 3 (#272, #267) plus #304's still-open `_history`-lists call (medications/conditions/injury history capture — Part B's D2 didn't decide this; see `V5_Implementation_SignupOnboarding_304PartB_DisclosuresPayloadRemoval_Phase1_2026_06_30_Closing_Handoff_v1.md`).

---

## §5 — Operating notes for next session

**Read order (Rule #13):**
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` if present — automated anchor sweep (not found in this repo snapshot as of this session; if it exists by next session, run it)

**Branch:** start Phase 3 fresh off `main` (post-merge) — do not continue on `claude/pack-load-weighting-phase1-uy2kfz`, which is done once PR #1084 lands. Use a new branch name reflecting Phase 3 scope (rename at session start if the harness pins something else, per CLAUDE.md's branch-naming rule).

**PR #1084 status:** if this handoff is being read before #1084 has actually merged, check its state first (`pull_request_read get_status` / `mcp__github__pull_request_read`) — don't assume it landed just because this handoff says auto-merge was armed.
