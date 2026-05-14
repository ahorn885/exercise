# D-58 Onboarding Design Wave (4/4) Closing Handoff

**Session:** Onboarding Design Wave Track 4. Single piece: D-58 design — OAuth-first onboarding flow + provider-sourced prefill mechanics. Continuation of the same chat that shipped CLAUDE.md pointer refresh + D-61 design + D-61 handoff earlier (see `D61_Onboarding_Wave_Closing_Handoff_v1.md` — that handoff is the intermediate book-keeping; this one is the session-end closer).
**Date:** 2026-05-14
**Predecessor handoff:** `D61_Onboarding_Wave_Closing_Handoff_v1.md` (intermediate, same session)
**Branch:** `claude/review-onboarding-handoff-e90Ei`
**Status:** ✅ Fourth and final design-wave track shipped. **Onboarding Design Wave complete (D-59 + D-60 + D-61 + D-58 all settled).** 🟡 v5 onboarding spec rewrite is the next forward move; D-50 wiring is now unblocked.
**Time-on-task:** Single chat continuing from the D-61 close. Substantive files shipped *this turn*: **1** (D-58 design). Cumulative for the session: **3** substantive (CLAUDE.md refresh, D-61 design, D-58 design) + 2 handoffs. Within the 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

Verified the D-61 closing handoff's claimed file updates against on-disk state before continuing.

| Claim | Result |
|---|---|
| `aidstation-sources/CLAUDE.md` — Authoritative current files refreshed (v6→v7, v11→v15, v2→v4, Layer 3 done = 3A + 3B) | ✅ Verified at lines 55–61 |
| `aidstation-sources/Onboarding_D61_Design_v1.md` — 9 decisions in §2, ~296 lines, decisions on schedule shape / assignment algorithm / max-duration drop / JIT swap UX | ✅ Verified |
| Closing handoff present at `aidstation-sources/handoffs/D61_Onboarding_Wave_Closing_Handoff_v1.md` | ✅ Verified |
| All commits (`2ecd109`, `d350f45`, `503ec90`) pushed to `claude/review-onboarding-handoff-e90Ei` | ✅ Verified pre-D-58-work |

No drift between intermediate handoff narrative and on-disk state.

---

## 2. Files shipped this turn

All on branch `claude/review-onboarding-handoff-e90Ei`. Each commit pushed individually (push happens at the end of this handoff).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Onboarding_D58_Design_v1.md` | New | Fourth and final design-wave doc. 9 decisions locked covering OAuth-first flow placement, per-field prefill priority, edit-in-place affordance with manual_override stickiness, graceful-degradation + delayed-soft-nudge for athletes without providers, prompt + per-field opt-in for re-onboarding after later provider connect, override-clear path, per-provider scope acknowledgment storage, sidecar provenance table, and tolerance-based re-prefill cadence. New tables: `athlete_profile_field_provenance`, `account_nudges`. New `disclosure_id` values for Account Config 3 (per-provider OAuth scopes). PG-only per the freeze. |
| — | `aidstation-sources/handoffs/D58_Onboarding_Wave_Closing_Handoff_v1.md` | New (this file) | Session-end book-keeping. |

**Files explicitly NOT touched this turn (cumulative session list — same as the D-61 handoff plus D-58):**

- `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` — v5 consolidates all four design tracks; v5 lands as the next session's substantive work.
- `aidstation-sources/Project_Backlog_v15.md` — D-58 row still reads as High / Deferred; design landing does not flip its status (implementation does). Update during v5 spec rewrite when the row resolves.
- `aidstation-sources/CLAUDE.md` — pointer refresh from earlier in the session stands. The residual narrative staleness (Current state date, Last shipped session, Next forward move, Independent parallel tracks) is still pending; recommend handling at the close of the v5 spec session per the predecessor §5.2.
- `init_db.py`, `routes/profile.py`, `routes/connect_*.py`, OAuth callback handlers — all v1 code untouched. D-58 schema migrations + connect-step UI + provenance handling land in the v5 implementation PR, not now.
- `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` — no changes; D-58 reads §3, §4, §7, §8 as inputs but does not modify the integration spec.

---

## 3. What landed — Andy's decisions on the five open questions

The predecessor (D-61) handoff §5.1 carried forward five open questions from the original D-50 review handoff §6.2. Andy's locks this turn:

| Q | Andy's choice | Notable |
|---|---|---|
| 1. Provider-connection step placement | **After account-creation ack, before §A** | Matches the recommendation. Account-creation ack stays first as the legal/risk gate; provider-connect becomes Step 1 of actual data work. No separate "Welcome" screen. |
| 2. Per-field prefill priority across providers | **Most-recent-wins + provenance display** | Matches the recommendation. Honest, simple, athlete-correctable. Per-provider preference per field rejected as config burden athletes won't tune. |
| 3. Prefilled field affordance | **Edit-in-place + manual_override stickiness** | Matches the recommendation. Edit-in-place is lower friction than click-to-unlock; the stickiness flag closes the round-trip on "what happens to my edit when the next sync arrives" with the answer "nothing." |
| 4. "No providers connected" path | **Graceful degradation + delayed soft nudge after 14 days** | Matches the recommendation. Hard requirement was rejected as hostile UX for athletes without providers (Apple Health / Samsung Health out of scope per CLAUDE.md). 14-day delay surfaces value once without becoming nag. |
| 5. Re-onboarding after later provider connect | **Prompt + per-field opt-in, manual_override fields excluded** | Matches the recommendation. Silent rewrite was the "surprise the athlete" failure mode; per-field diff review is friction for the no-conflict case. The bulk-apply / per-field-review / skip prompt is honest and respects override stickiness. |

All five recommendations adopted. D-58 design doc (364 lines) captures decisions in §2 (9 rows including 4 inferred design choices beyond the 5 user-facing locks), the new flow ordering in §3, prefill mechanics in §4, no-providers path in §5, re-onboarding in §6, schema additions in §7, cross-track interactions in §8, what's explicitly not covered in §9, and gut check in §10.

### 3.1 Inferred design choices (beyond the five user-facing locks)

These were committed in the design doc without a separate Andy ask, on the principle that they're mechanical follow-throughs of the locked five:

- **Decision #6 — manual override clear path.** "Athlete can revert a manual_override on a field-by-field basis from the field's edit affordance." Without this, the `manual_override` stickiness from decision #3 traps athletes who fat-finger an edit. The clear path is the round-trip closer.
- **Decision #7 — per-provider scope acknowledgment storage.** "Each OAuth flow records a row in Account Config 3 with `disclosure_id='oauth_scope_<provider>'`, `version_id`, `acknowledged_at`, `scopes_granted` snapshot." The §A.1 disclosure already exists (v4 line 156); decision #7 just pins down storage shape against the existing Account Config 3 table.
- **Decision #8 — sidecar provenance table.** New table `athlete_profile_field_provenance` keyed by `(user_id, field_name)`. Alternatives (per-field columns on every value table; JSONB on athlete_profile) were rejected as schema-churn-prone; sidecar is the cleanest default.
- **Decision #9 — tolerance-based re-prefill cadence.** When a provider sync delivers a field the system already has prefill-stored from that same provider: silent update if within tolerance, surface as passive notification if beyond. Tolerance values themselves are v5 implementation config, not this design doc.

If Andy disagrees with any of these inferred choices, they're cheap to amend (each is a localized change to its respective section).

---

## 4. Session-end verification (Rule #10)

| Claim | Anchor | Result |
|---|---|---|
| D-58 design has 9 decisions in §2 | `awk '/^## 2\. Decisions/,/^## 3\./' Onboarding_D58_Design_v1.md \| grep -cE "^\| [0-9] "` returns 9 | ✅ Verified |
| D-58 design line count reasonable | 364 lines (compared to D-59's 252, D-60's 312, D-61's 296) | ✅ Verified — slightly larger than peers because of the cross-track interactions matrix in §8 (12 rows covering D-50 / D-59 / D-60 / D-61 / §A.1 / Account Config 1 / Account Config 3 / Integration v4 §7 / §8 / Layer 3A) |
| New tables documented for v5 implementation | `athlete_profile_field_provenance`, `account_nudges`; both PG-only per the freeze; both with full DDL in §7 | ✅ Verified |
| `manual_override` semantics specified end-to-end | Decisions #3 + #6 + §4.3 edit-semantics table + §6 re-onboarding exclusion | ✅ Verified |
| Onboarding Design Wave is now complete | D-59 + D-60 + D-61 + D-58 all on disk with `_v1.md` suffix | ✅ Verified |

No spec content touched outside the new design doc; no design-doc drift from the in-chat decision tables.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.1 Forward move — `Athlete_Onboarding_Data_Spec_v5.md`

The Onboarding Design Wave is complete. The next session consolidates all four design tracks into a single spec rewrite.

**Pre-step reads (Rule #13 ordering):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read. Pointer refresh done; **state-narrative refresh deferred to this session's closing admin pass** (see §5.2 below for what to refresh and why now is the right time).
2. `aidstation-sources/Project_Backlog_v15.md` — D-58 / D-59 / D-60 / D-61 rows + cross-cutting context. All four now have shipped design docs; backlog status updates as part of the spec rewrite session.
3. `aidstation-sources/handoffs/D58_Onboarding_Wave_Closing_Handoff_v1.md` (this file) and `D61_Onboarding_Wave_Closing_Handoff_v1.md` (intermediate). Both are needed because they together describe the full session-end state.
4. `aidstation-sources/Onboarding_D59_Design_v1.md`, `Onboarding_D60_Design_v1.md`, `Onboarding_D61_Design_v1.md`, `Onboarding_D58_Design_v1.md` — input contracts. The v5 spec quotes these verbatim where useful and consolidates schema additions.
5. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` fully — v5 is a rewrite, not a surgical edit; the whole v4 needs to be in working memory.
6. `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` §7 — authoritative per-field source mapping; D-58's prefill-eligibility list (D-58 §4.1) must stay in sync with §7.

**Output target:** `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md`.

**Scope of v5:**

- **§A (Athlete Identity)** — D-58 prefill behavior + connected-provider banner above the field set.
- **§A.1 (Disclosures)** — adds Mapbox geocoding consent (D-59 §8), shared-gym-profile contribution consent (D-60 §4.7), per-provider OAuth scope acknowledgments (D-58 §7.3); existing disclosures unchanged. The Connected Service consent disclosure's *firing point* moves to the new D-58 connect step (Step 2 of onboarding) per D-58 §3.3.
- **New §A flow framing** — replaces v4's implicit "athlete just enters fields in order" with the explicit step sequence per D-58 §3.1 (account creation → ack → connect step → §A → §B → ...).
- **§B–§F (Health, Training History, Disciplines, Strength, Performance Testing)** — annotate prefill-eligible fields per D-58 §4.1; behavior of provider-prefill / edit-in-place / manual_override per D-58 §4.3.
- **§G (Schedule & Availability)** — full rewrite per D-61 decisions #1–#7: per-day windows + orthogonal Long Session / Doubles toggles + Preferred Rest Day (demoted Tier 1→2). Drop "Available Training Hours per Week" / "Training Days Available" / "Typical Session Duration" as explicit fields; show as derived display.
- **§J.1 (Locale-level fields)** — D-59 lookup + chain detection storage shape; new columns `mapbox_id`, `lat`, `lng`, `chain_id`, `chain_name`, `category`, `manual_entry`, `place_payload`, `place_fetched_at`. Preserve §J's proximity model.
- **§J.2 (Equipment Inventory)** — D-60 shared-gym-profile + override model; introduces `gym_profiles` table reference and the inherit/override flow.
- **§J.3 (Sport-Specific Gear Toggles)** — D-60 same model as §J.2.
- **§J.4 (Terrain Access)** — unchanged.
- **§J.5 (Locale Capacity Metrics)** — **deleted entirely.** Both fields removed per D-61 decisions #4–#5.
- **§K (Locale Schedule)** — unchanged. D-61 reads §K as input but does not modify.
- **§L (Athlete Network)** — unchanged.
- **Account Config 1 (Connected Services)** — reframed from "connect here" to "manage your connections here" per D-58 §3.3. Connect possible from this screen as the post-onboarding path; primary connect happens at Step 2 of onboarding.
- **Account Config 2 (Gym Memberships)** — sanity-check interaction with D-59 chain detection + D-60 shared profiles; the v5 spec confirms the relationship rather than redesigning it. Per the predecessor D-50-Review handoff §8, this relationship is plausibly worth a standalone clarification subsection.
- **Account Config 3 (Disclosure Acknowledgment Records)** — new disclosure_id values per D-58 §7.3 and D-59 §8; existing record shape preserved.
- **Account Config 4 (Privacy and Linked-Partner Sharing)** — unchanged.
- **Plan Management 1–5** — unchanged.

**Cross-design-doc consistency check (recommended at v5 session opening):** the predecessor D-61 handoff §7 flagged this; D-58 reaffirms it. The four design docs together add ~7 new tables and ~12 new columns across `locale_profiles`, `athlete_profile`, and elsewhere. A 30-minute integration pass before v5 quotes them as authoritative would catch any subtle inconsistencies (column name mismatches, table-create ordering dependencies, missing FK targets).

**Plus a closing CLAUDE.md state-narrative refresh** (residual from the D-61 session's pointer-only edit) per §5.2.

### 5.2 Closing admin pass — CLAUDE.md state-narrative refresh

After v5 spec lands, refresh:

- **"Current state (as of 2026-05-13)"** header — bump to the v5 spec's date.
- **"Last shipped session: L3-Spec-Trio Round 2"** pointer — update to the most recent session at that point (likely "Onboarding v5 spec rewrite" if v5 ships in the next session).
- **"Next forward move: Layer3_3B_Spec.md"** pointer — 3B already shipped before D-50; update to whatever the post-v5 forward move is. Candidates:
  - Layer 4 plan-gen spec (Layer 4 has been deferred since the original spec hierarchy was laid out).
  - The v5 onboarding implementation PR (D-58 schema migrations + connect step UI + provenance + per-day windows + shared gym profiles + place lookup, all at once — substantial implementation work).
  - D-50 wiring resumption (now unblocked per D-58; first PR is `provider_auth.py` helper + first real OAuth flow + first provider's webhook recording).
  - Andy chooses among these.
- **"Independent parallel tracks" block** — reflect current state: D-50 Phase 1 schema shipped, wiring unblocked; D-52 Catalog Migration unchanged; D-55 Garmin paused; D-57 unchanged; D-58–D-61 design wave complete (replace this row entirely).

### 5.3 D-50 wiring — now unblocked

Predecessor handoff §6.4 paused D-50 wiring on D-58's UX decisions. **D-58 is now settled.** Wiring can resume per the original D-50 handoff §6.1 plan, updated for D-58's contracts:

1. **Build `provider_auth.py` helper module** (UPSERT by `(user_id, provider)`, status transitions per Integration v4 §4.1, token-refresh skeleton, webhook_token rotation Pattern A). Provider-agnostic; can be built any time.
2. **Pick one provider** to ship a real OAuth flow against. CLAUDE.md flags COROS as next-to-ship; Andy may revise.
3. **Implement OAuth callback** that: exchanges the code for tokens, stores via `provider_auth.py`, stores per-provider scope acknowledgment via Account Config 3 per D-58 decision #7, redirects per D-58 §3 (back to onboarding step 3 if mid-onboarding; back to Account Config 1 management screen if post-onboarding; triggers the §6 re-onboarding prompt if any prefill-eligible field has data available).
4. **Webhook handler** writes a row into `webhook_events` per Integration v4 §4.2.
5. **Per-provider data ingestion** — wire webhook dispatch → per-provider table writes.
6. **Frontend connect step** at the new Step 2 of onboarding; manage-connections framing in Account Config 1.

PR1 of wiring is no longer "provider_auth.py + COROS migration" — it's now "provider_auth.py + real COROS OAuth flow + COROS webhook recording + D-58 connect-step frontend integration." Substantially bigger scope than the original D-50 handoff framed; matches the D-50 review handoff §6.4's adjusted scope estimate (2–4 sessions of implementation per provider).

Andy can choose to sequence v5 spec rewrite first (recommended, since the implementation PR depends on the spec) or interleave wiring with spec.

### 5.4 D-62 webhook_events retention prune — still queued

Tracked in Backlog v15. Lands alongside the first real webhook handler implementation or as its own ops PR. Unchanged.

---

## 6. Forward pointers

- **Next session:** `Athlete_Onboarding_Data_Spec_v5.md` consolidating all four design tracks per §5.1, plus the CLAUDE.md state-narrative refresh per §5.2 as the closing admin pass.
- **Following:** Andy's call. Candidates: v5 onboarding implementation PR, D-50 wiring resumption, Layer 4 plan-gen spec.
- **Unblocked this session:** D-50 wiring (was paused on D-58 per predecessor handoff §6.4). See §5.3 for the updated PR1 scope.
- **D-54 SQLite collapse:** still queued; Catalog Migration Phase 5. SQLite freeze remains in force per `Athlete_Data_Integration_Spec_v4` §2.5.
- **D-55 Garmin rebuild:** still paused until Garmin reopens API access.
- **D-62 webhook_events retention prune:** tracked; lands either alongside first real webhook handler implementation or as its own ops PR.

**Onboarding Design Wave status:**

| Track | Status | Output |
|---|---|---|
| D-59 (place lookup + chain detection) | ✅ Complete | `Onboarding_D59_Design_v1.md` |
| D-60 (shared gym profiles + locale taxonomy) | ✅ Complete | `Onboarding_D60_Design_v1.md` |
| D-61 (plan-level schedule + session→locale assignment) | ✅ Complete | `Onboarding_D61_Design_v1.md` |
| D-58 (OAuth-first flow + provider-sourced prefill) | ✅ Complete | `Onboarding_D58_Design_v1.md` |
| **Wave consolidation** | 🟡 Pending | `Athlete_Onboarding_Data_Spec_v5.md` |

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits
- #12 numeric version suffixes
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 step 1 is CLAUDE.md.**

---

## 7. Gut check

**What this turn got right.**

- **Andy's "keep going" turned a single-track session into a wave-completing session without quality compromise.** D-58 was the natural next track per the predecessor §5.1; the chat budget was available; the open questions had been pre-staged for two sessions. Closing the wave in this session means the next session can be a cohesive v5 spec rewrite rather than another design-doc track.
- **All five recommendations adopted.** D-58's open questions had relatively clear-cut answers (most of them genuinely had a "best" option once tradeoffs were laid out), and Andy went with the recommendations across the board. Different from D-61's Q3, where Andy chose a third option (drop the field) that wasn't on the menu — both patterns are valid; D-58 happened to be the convergent case.
- **Inferred design choices were called out separately.** Decisions #6–#9 in the design doc are not in the original five-question menu. The handoff §3.1 explicitly lists them as inferred so Andy can push back on any without re-litigating the locked five. Reduces silent-decision risk.
- **D-50 wiring is genuinely unblocked.** D-58 §3 (connect step UX), §4 (prefill mechanics), §7 (provenance + scope acknowledgment storage) give the wiring PR concrete contracts to build against. The §5.3 forward pointer captures the updated PR1 scope.
- **The wave is complete in clean shape.** Four design docs at consistent depth (252–364 lines each, similar section structure, similar gut-check format), each committing to specific schema shapes. The v5 spec rewrite has clean inputs.
- **5-file ceiling honored across the session.** Cumulative substantive files: CLAUDE.md edit + D-61 design + D-58 design = 3. Two handoffs (D-61 + D-58) = book-keeping per the predecessor pattern. Well under the cap.

**Risks.**

- **Two handoffs in one session is unusual.** The D-61 handoff was written, committed, and pushed before the D-58 work began; this D-58 handoff is the session-end closer. Future sessions reading both may find the redundancy confusing — the D-61 handoff says "next move: D-58" while the D-58 handoff (this file) says "D-61 was the predecessor." Mitigation: this handoff §1 explicitly labels the D-61 handoff as "intermediate" and §2 makes the cumulative file list explicit. If the convention bothers Andy, future sessions can write a single closing handoff per session even when multiple tracks ship.
- **D-58 shipped as paper design against stub providers.** Per the design doc §10 best-argument-against, all "shipped" providers are 19-line webhook stubs. Nothing to actually OAuth against. The connect step at Step 2 of onboarding has nothing real behind it until D-50 wiring builds the per-provider OAuth flows. Mitigation: the v5 implementation PR can build the connect step + one real OAuth flow (COROS) together; subsequent providers ship per-PR against the now-real connect step.
- **Inferred design choices (decisions #6–#9) carry assumption risk.** Andy didn't see these as menu options. If any is wrong, the design doc has to amend. Lowest risk: #6 (override clear path) and #7 (Account Config 3 storage) are mechanical follow-throughs. Higher risk: #8 (sidecar provenance table — alternatives exist) and #9 (tolerance-based re-prefill — knob design is genuinely contestable).
- **CLAUDE.md state-narrative staleness has now persisted across two sessions.** Pointers refreshed at the start of this session; narrative still stale. The forward pointer in this handoff §5.2 names v5 spec session as the right time, but if v5 spec slips multiple sessions, the staleness compounds. Mitigation: any session can do the narrative refresh as its opening admin pass; the §5.2 framing is recommendation, not mandate.
- **Cross-design-doc consistency check still pending.** D-61 handoff §7 flagged it; this handoff §5.1 reaffirms it. The combined migrations are not yet sanity-checked. v5 spec session's opening 30-minute pass is the protection; not yet executed.
- **Three sessions in a row of design-only work.** Predecessor session shipped D-50 review + D-59 + D-60 (5 design files). D-61 session shipped CLAUDE.md + D-61 (2 substantive). This session adds D-58 (1 substantive). Andy's "push to production as we go" rule is being violated in the spirit (no code shipped) even if defensible per-session (design wave was the gating prerequisite). Mitigation: v5 spec → v5 implementation is the next implementation arc, and the v5 implementation PR will be substantial code work.

**What might be missing.**

- **Per-provider data shape sanity check.** D-58 §4 trusts Integration v4 §7 for "Polar can supply RHR." The Integration v4 spec is the authoritative reference; if it's wrong about a particular provider/field combo, D-58's prefill mechanics propagate the wrongness. Worth a sanity pass during the v5 implementation PR — first real OAuth flow (COROS) will surface any §7 inaccuracies for that provider.
- **`field_name` registry concrete list.** D-58 §7.1 names the column but defers the canonical list to v5 implementation. The v5 spec rewrite is the right place to commit the list (it touches every field in §A–§F that has a prefill-eligible mapping); v5 should produce a `KNOWN_PROFILE_FIELDS` constant referenced from this design doc.
- **Provider disconnect behavior on prefilled fields.** D-58 §10 raises this but doesn't spec it. v5 spec should add the answer (recommend: value persists with `source` flipped to `'self_report'` + a note tag; re-resolve to next-best provider on next display if any).
- **Audit trail for field-source changes.** D-58 §10 raises this; not specced. Backlog candidate; v5 implementation can land application logging as a v1 mitigation.
- **Connect step copy.** D-58 §5.1 illustrates the connect screen but doesn't commit copy. Like other §A.1 disclosures (per v4 line 159), copy is product/legal-owned; D-58 commits the *slot*, not the text.
- **Connect step provider list source.** D-58 assumes a `provider_registry.py` file analogous to D-59's `chain_registry.py`. Not specified. v5 spec or v5 implementation can land it.
- **Telemetry on the 14-day nudge.** D-58 §10 risks list flags this. Not specced. v5 implementation can add basic event logging (nudge displayed, dismissed, acted-on); reading it is a separate dashboard / query effort.

**Best argument against this turn's scope.**

A more conservative session would have stopped after the D-61 handoff and started fresh on D-58. Per the predecessor sessions' "one track per turn" discipline, D-58 deserves its own chat budget. Counter: the chat budget had room (3 substantive files at session end is well under the 5-file ceiling); Andy explicitly asked to keep going; the open questions were already pre-staged from the prior handoff so there was no fresh-research overhead. Plus the convergence on all five recommendations meant no decision-cluster-juggling — D-58 was a near-pure execution session, not an exploration session.

A less conservative session would have rolled into the v5 spec rewrite this same chat. Counter: v5 is substantively different work (consolidation across four design docs + reading the full v4 spec + cross-design-doc consistency pass) and benefits from a fresh chat budget. Plus v5 is a new logical artifact (`Athlete_Onboarding_Data_Spec_v5.md`) that crosses the spec-vs-design-doc line — the per-row design doc model was specifically about keeping these separated. Closing the design wave at D-58 and starting fresh for v5 respects the discipline.

---

*End of D-58 Onboarding Design Wave (4/4) closing handoff. Onboarding Design Wave complete.*
