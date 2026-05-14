# D-61 Onboarding Design Wave (3/4) Closing Handoff

**Session:** Onboarding Design Wave Track 3. Two pieces: (1) admin pass — CLAUDE.md pointer refresh; (2) D-61 design — plan-level schedule + session→locale assignment.
**Date:** 2026-05-14
**Predecessor handoff:** `D50_Review_and_Onboarding_Wave_D59_D60_Closing_Handoff_v1.md`
**Branch:** `claude/review-onboarding-handoff-e90Ei`
**Status:** ✅ Admin pass done; ✅ third of four design-wave tracks shipped; 🟡 D-58 design pending.
**Time-on-task:** Single chat. Substantive files shipped: **2** (CLAUDE.md pointer refresh, D-61 design). Well under the 5-file ceiling.

---

## 1. Session-start verification (Rule #9)

Verified the D-50 Review + D-59/D-60 closing handoff's claimed file updates against on-disk state before starting new work.

| Claim | Result |
|---|---|
| `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` — §2.5 carve-out paragraph for the D-50 SQLite-freeze override | ✅ Verified at line 129 ("Documented exception (v4, 2026-05-14):" anchor) |
| `aidstation-sources/Project_Backlog_v15.md` — D-54 row updated with 2026-05-14 carve-out citation; new D-62 webhook_events retention row | ✅ Verified both rows present (D-54 at line 95, D-62 at line 103) |
| `aidstation-sources/Onboarding_D59_Design_v1.md` — 8 decisions in §2 | ✅ Verified (252 lines, 8-row decisions table) |
| `aidstation-sources/Onboarding_D60_Design_v1.md` — 9 decisions in §2 | ✅ Verified (312 lines, 9-row decisions table) |
| All commits merged to main via PR #31 | ✅ Verified (PR #31 merged; `claude/review-aidstation-handoff-4aRtE` closed) |

**Drift confirmed (handoff-flagged, this session partially fixed):**
- `aidstation-sources/CLAUDE.md` "Authoritative current files" section pointed at Control_Spec_v6, Backlog_v11, Integration_v2, and Layer3_3A_Spec only. The predecessor handoff §6.1 step 1 explicitly named this as the next session's opening admin pass. Refreshed this session (see §2 below).

**Drift residual (not fixed this session):**
- CLAUDE.md "Current state (as of 2026-05-13)" header date.
- CLAUDE.md "Last shipped session: L3-Spec-Trio Round 2" pointer — actually L3-Trio R2 → D-50 Phase 1 → D-50 Review + D-59/D-60 → D-61 (this session).
- CLAUDE.md "Next forward move: Layer3_3B_Spec.md" — 3B shipped; current next is D-58 design.
- CLAUDE.md "Independent parallel tracks" block — D-50 listed as pending (actually Phase 1 shipped, wiring paused on D-58); D-58–D-61 listed as a design wave (3 of 4 now shipped).

These are state-narrative updates, not pointer references. Left untouched this session because the predecessor handoff's explicit ask was the "Authoritative current files" pointer refresh. They warrant a separate broader CLAUDE.md update pass — recommend doing it at the end of the D-58 design session (which is also when the v5 spec rewrite will be the only remaining forward move, justifying a full state refresh).

---

## 2. Files shipped this session

All on branch `claude/review-onboarding-handoff-e90Ei`. Each commit pushed individually.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/CLAUDE.md` | Surgical edit | "Authoritative current files" section refreshed: Control_Spec_v6 → v7; Project_Backlog_v11 → v15; Athlete_Data_Integration_Spec_v2 → v4; Layer 3 done now lists 3A + 3B; added a parenthetical to Onboarding pointing at the D-59 / D-60 design wave artifacts. No other CLAUDE.md changes. |
| 2 | `aidstation-sources/Onboarding_D61_Design_v1.md` | New | Third of four design-wave docs. 9 decisions locked: per-day windows replace weekly §G aggregates; Long Session + Doubles preserved as orthogonal capacity flags; session→locale assignment by equipment-qualifying filter → distance → athlete-set `preferred` flag inside qualifying set; anchor locale resolved through §K overlays; **§J.5 `Max session duration` field dropped entirely** (Andy 2026-05-14, third option not on the original Q3 framing); §J.5 `Typical session time available` also dropped (superseded by per-day windows); JIT swap UX at session start + non-required "Session locations" review surface; no-qualifying-locale path is explicit `assignment_status='unassigned'` with three athlete options. New table `daily_availability_windows`; new column `locale_profiles.preferred`. PG-only per the freeze. |
| — | `aidstation-sources/handoffs/D61_Onboarding_Wave_Closing_Handoff_v1.md` | New (this file) | Book-keeping. |

**Files explicitly NOT touched:**

- `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` — v5 consolidates all four design tracks; v5 lands after D-58 settles.
- `aidstation-sources/Project_Backlog_v15.md` — D-61 row still reads as Med / Deferred; design landing does not flip its status (implementation does). Update during v5 spec rewrite when the row resolves.
- `init_db.py` — schema migrations for D-61 (`daily_availability_windows`, `locale_profiles.preferred`, `locale_profiles.max_session_duration` / `typical_session_time` drops) land as part of the v5 implementation PR, not now.
- `routes/profile.py`, `routes/locales.py` — v1 code untouched. D-61 is pure v2-spec design work.
- `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` — no changes; D-61 has no provider-integration interaction.

---

## 3. What landed — by piece

### 3.1 CLAUDE.md pointer refresh (admin)

Surgical edit to the "Authoritative current files" subsection, lines 55–64. Four version bumps and one Layer 3 addition:

| Pointer | Was | Now |
|---|---|---|
| Architecture | `Control_Spec_v6.md` | `Control_Spec_v7.md` |
| Backlog | `Project_Backlog_v11.md` | `Project_Backlog_v15.md` |
| Integration | `Athlete_Data_Integration_Spec_v2.md` | `Athlete_Data_Integration_Spec_v4.md` |
| Layer 3 done | `Layer3_3A_Spec.md` | `Layer3_3A_Spec.md`, `Layer3_3B_Spec.md` |
| Onboarding data | `Athlete_Onboarding_Data_Spec_v4.md` | `Athlete_Onboarding_Data_Spec_v4.md` (added parenthetical naming the D-59 / D-60 design-wave artifacts and the v5 consolidation target) |

No other CLAUDE.md content touched. Residual staleness in §1 (state-narrative, not pointers) flagged for the D-58 session.

### 3.2 D-61 design — Andy's decisions on the four open questions

The predecessor handoff §6.1 listed four high-leverage open questions. Andy's locks:

| Q | Andy's choice | Notable |
|---|---|---|
| 1. §G schedule granularity | **Per-day windows + Long Session / Doubles as orthogonal toggles** | Matches the recommendation. Per-day replaces weekly aggregates; long-session capacity and doubles feasibility stay as separate fields. |
| 2. Session→locale assignment algorithm | **Equipment-qualifying filter → distance → athlete `preferred` flag inside qualifying set** | Matches the recommendation. Simpler than the original 4-tier tiebreaker chain in the predecessor handoff's framing. |
| 3. Max session duration field | **Dropped entirely from v5** | **Did not match the recommendation** (which proposed a two-field split between shared gym profile and per-athlete locale). Andy chose a third option not on the original question — the field is removed from v5 rather than relocated. Plus `Typical session time available` also dropped (decision #5 in the design doc) — superseded by per-day windows. |
| 4. Per-session locale-picking UX | **JIT at session start + optional review surface** | Matches the recommendation. Plan-gen picks the default; tap-to-swap is the primary touch point; "Session locations" review view is non-required. |

D-61 design doc (296 lines) captures all 9 decisions, the per-day window schema, the session→locale resolver algorithm in §4.1, the §J.5 cleanup, the schema additions, cross-track interactions with D-59 / D-60 / §K / Layer 4 plan-gen, and what the doc explicitly does not cover. Gut check + best-argument-against in §10.

### 3.3 §J.5 field removal — explicit override of the backlog framing

The predecessor handoff §6.1 Q3 framed max-session-duration as "stays at the locale as equipment/safety constraint rather than scheduling constraint" — i.e., it stays, the question was just where. Andy's drop is an explicit override of that framing. Captured in the D-61 design doc decision #4 with rationale: a Tier-3 field with no observed plan-gen consumption is survey burden for no signal; real per-locale caps are enforced JIT at session start through the new swap surface, not through a stored cap field.

This means v5 §J (Locales) loses §J.5 entirely. §J.1 (locale-level fields), §J.2 (equipment inventory — D-60-reframed), §J.3 (sport-specific gear toggles — D-60-reframed), §J.4 (terrain access — unchanged) remain.

---

## 4. Session-end verification (Rule #10)

| Claim | Anchor | Result |
|---|---|---|
| CLAUDE.md pointer refresh landed | `grep -nE "^- (Architecture\|Backlog\|Integration\|Layer 3 done):" aidstation-sources/CLAUDE.md` returns `v7`, `v15`, `v4`, `3A + 3B` | ✅ Verified |
| D-61 design has 9 decisions in §2 | `grep -cE "^\| [0-9] " aidstation-sources/Onboarding_D61_Design_v1.md` returns 9 | ✅ Verified |
| D-61 design line count reasonable | 296 lines (compared to D-59's 252 and D-60's 312) | ✅ Verified |
| All commits pushed to `claude/review-onboarding-handoff-e90Ei` | Verified pre-handoff-commit | ✅ Verified |

No spec content touched outside the bounded CLAUDE.md pointer-refresh edit; no design-doc drift from the in-chat decision table.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.1 Forward move — D-58 design (Onboarding Design Wave 4/4)

**Pre-step reads (Rule #13 ordering):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read. Pointer-refresh done this session; the "Current state" narrative block (last-shipped-session, next-forward-move, independent-parallel-tracks) is still stale. Recommend doing the broader state-narrative refresh as the **closing** admin pass of the D-58 session (when D-58 lands, the only remaining forward move is the v5 spec rewrite — justifying a full state refresh at that point).
2. `aidstation-sources/Project_Backlog_v15.md` — D-58 row + cross-cutting context.
3. `aidstation-sources/handoffs/D61_Onboarding_Wave_Closing_Handoff_v1.md` (this file).
4. `aidstation-sources/handoffs/D50_Review_and_Onboarding_Wave_D59_D60_Closing_Handoff_v1.md` — context on Andy's three sequencing directives (per-row design docs; single spec v5; one track per turn).
5. `aidstation-sources/Onboarding_D59_Design_v1.md`, `Onboarding_D60_Design_v1.md`, `Onboarding_D61_Design_v1.md` — input contracts. D-58 has no direct interaction with any of these per their cross-track tables, but the design wave's shared discipline (no inferences, athlete-owned data, JIT vs. bulk-confirm patterns) shapes D-58's flow design.
6. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` §A (Athlete Identity, lines 127–164) — fields D-58 wants to prefill.
7. `aidstation-sources/Athlete_Onboarding_Data_Spec_v4.md` Account Config 1 (Connected Services, lines 851–865) — existing connection-state structure.
8. `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` §7 (Field mapping — onboarding fields to data sources) — authoritative per-field source list.
9. `aidstation-sources/Athlete_Data_Integration_Spec_v4.md` §8 (Two-regime consumer model) — D-58's OAuth-first reshapes both regimes.

**Open questions to resolve with Andy in the next session (carried forward from predecessor handoff §6.2):**

1. **Provider-connection step placement.** Before §A (truly OAuth-first)? After §A.1 disclosures (consent first, then connect)? At a Step 0 "Welcome — connect your accounts" screen?
2. **Per-field prefill priority across providers.** When Polar + COROS both have RHR, which wins?
   - (a) Explicit per-provider preference per field (Andy ranks once);
   - (b) Most-recent-wins;
   - (c) Weighted blend;
   - (d) Athlete-picks per field at prefill.
3. **Prefilled field affordance.** Edit-in-place ("Body Weight: 78.2 kg [from Polar, 2 days ago]") or locked-with-explicit-override?
4. **"No providers connected" path.** Graceful degradation to v1-style self-report, or harder nudge to connect first?
5. **Re-onboarding after later provider connect.** If athlete onboards self-report-first, then connects providers later, does the system retroactively prefill (potentially overwriting their entries)? With what consent prompt?

**Output target:** `aidstation-sources/Onboarding_D58_Design_v1.md`.

### 5.2 Following move — v5 spec rewrite

After D-58 lands, the four-track Onboarding Design Wave is complete. Consolidate into a single spec rewrite:

**Output target:** `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md`.

**Scope:**
- §A (Athlete Identity) — D-58 prefill behavior + connected-provider banner.
- §G (Schedule & Availability) — full rewrite per D-61 decisions #1–7: per-day windows + orthogonal Long Session / Doubles toggles + Preferred Rest Day (demoted Tier 1→2).
- §J.1 — D-59 lookup + chain detection storage shape.
- §J.2 — D-60 shared-gym-profile + override model.
- §J.3 — D-60 same model for sport-specific gear toggles.
- §J.5 — **deleted section.** Both fields removed per D-61.
- §K — unchanged; D-61 reads §K as input but doesn't modify.
- Account Config 1 — D-58 connection-state shape.
- Account Config 2 (Gym Memberships) — interaction with D-59 chain detection + D-60 shared profiles (sanity check during rewrite per predecessor handoff §8 "What might be missing").
- Account Config 3 — new acknowledgments for Mapbox geocoding consent (D-59), shared gym profile contribution consent (D-60), provider OAuth consent batches (D-58).

**Plus CLAUDE.md state-narrative refresh** (residual staleness from this session's pointer-only edit): the "Current state" header date, "Last shipped session" pointer, "Next forward move" pointer, and "Independent parallel tracks" block. Do this as the closing admin pass of the v5 spec session — at that point the project's state has changed enough to warrant a full narrative refresh rather than another pointer-only patch.

### 5.3 D-50 wiring — still paused

D-50 wiring blocked on D-58 per predecessor handoff §6.4. Unchanged. Unblocks when D-58 design lands.

### 5.4 D-62 webhook_events retention prune — still queued

Tracked in Backlog v15. Lands alongside the first real webhook handler implementation or as its own ops PR. Unchanged.

---

## 6. Forward pointers

- **Next session:** D-58 design (Onboarding Design Wave 4/4) per §5.1.
- **Following:** v5 onboarding spec rewrite consolidating all four design tracks + CLAUDE.md state-narrative refresh per §5.2.
- **Paused / blocked:** D-50 wiring per predecessor handoff §6.4. Unblocks when D-58 lands.
- **D-54 SQLite collapse:** still queued; Catalog Migration Phase 5. SQLite freeze remains in force per `Athlete_Data_Integration_Spec_v4` §2.5.
- **D-55 Garmin rebuild:** still paused until Garmin reopens API access.
- **D-62 webhook_events retention prune:** tracked; lands either alongside first real webhook handler implementation or as its own ops PR.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits
- #12 numeric version suffixes
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 step 1 is CLAUDE.md.**

---

## 7. Gut check

**What this session got right.**

- **Andy's drop on max-session-duration was preserved cleanly.** The original Q3 framing assumed the field stays and asked where; Andy chose a third option that wasn't on the menu. The design doc absorbed the reframe (drop + Typical session time also drops) without rationalizing the original framing back in. This is the same pattern as the D-60 "no inferences" reframe — when the user surfaces a better third option, take it.
- **Stop-and-ask discipline.** Four open questions surfaced as a single structured AskUserQuestion before drafting any design content. Recommendations attached but Andy's call was the gating event; the design doc came after the locks, not before.
- **Per-row design doc model continues to work.** Three sessions in (D-59, D-60, D-61), each design doc has been a single-decision-cluster artifact at ~250–310 lines. Each commits to specific schema shapes that the next track has to fit or amend. No "design lives in handoff narrative" anti-pattern.
- **CLAUDE.md pointer refresh was kept tight.** The explicit ask was the "Authoritative current files" section. The session refreshed exactly that and explicitly flagged the residual state-narrative staleness for the D-58 session, where it's a more natural fit. No scope creep into a broader CLAUDE.md rewrite that would have eaten the design-doc time.
- **Two-file session = well under the ceiling.** 5-file quality ceiling honored with margin. The admin pass + the design doc are the natural scope; nothing forced.

**Risks.**

- **CLAUDE.md state narrative is now half-stale.** Pointer block is current; the "Current state (as of 2026-05-13)" header, "Last shipped session" pointer, "Next forward move", and "Independent parallel tracks" block all lag. Future Rule #9 verification against the narrative block will still operate on stale framing. Mitigation: the §5.2 instructions name the narrative refresh as the v5 spec session's closing admin pass, which is the right gate. But if a session between now and v5 doesn't read this handoff carefully, they may not realize the narrative is stale even though pointers are not.
- **D-61 design touches a section Layer 4 plan-gen will own.** §4.1's resolver algorithm and the `assignment_status` state machine are Layer 4's territory; D-61 documents the contract. Risk: when Layer 4 spec lands, the contract may need amendment. Mitigation: the design doc explicitly names the consumer contract (§8 cross-track table); changes go through a v2 of this design doc, not silent re-interpretation in Layer 4.
- **Per-day windows are a survey design risk.** Athletes with variable schedules may find per-day rigidity worse than v4's weekly aggregates. The design absorbs this as a "use §K overlays for variability" answer, which is true but not seamless. Real-world athlete feedback may surface that the model is too rigid. v2 candidate.
- **The `preferred` flag is a minimum-viable expression.** Per-discipline preference ("YMCA for swim, home for strength") is a recognized v2 gap. Workaround through the qualifying filter works in the common case (swim only qualifies at YMCA) but not always.
- **No code was shipped (third session in a row).** Andy's "push to production as we go" rule still favors implementation. D-58 + v5 spec rewrite would make it four. Mitigation: the design wave was the precondition for shipping; the v5 implementation PR can absorb all four tracks at once.

**What might be missing.**

- **Cross-design-doc consistency check.** D-59 / D-60 / D-61 have been written sequentially; the schema additions across all three (`mapbox_id`, `chain_id`, `category`, `manual_entry`, `place_payload`, `place_fetched_at`, `gym_profile_id`, `sharing_opt_out`, `preferred`, plus `gym_profiles`, `locale_equipment_overrides`, `locale_toggle_overrides`, `daily_availability_windows` tables) haven't had a single integration pass. Worth a sanity-check section in the v5 implementation PR planning — does the combined migration land cleanly? Are there ordering dependencies between table creates? Are any column types inconsistent (e.g., `mapbox_id TEXT` vs. `mapbox_id VARCHAR(...)`)? The v5 spec rewrite is the natural place to surface this.
- **Calendar-provider sync as a future track.** D-58 is fitness-provider OAuth (COROS, Polar, etc.); calendar-provider sync (Google Cal, iCal) is a plausible v2 add for the D-61 schedule-windows feature — importing windows rather than re-entering. Not a v5 concern; backlog candidate after launch.
- **`Long Session Available` day-picker × `daily_availability_windows.enabled` cross-validation.** Athletes who unselect Saturday from per-day windows but kept Saturday as their long-session day end up with an inconsistent state. The design doc flags this in §10 risks; the v5 implementation handles the cross-validation. Worth an explicit sentence in the v5 §G text.
- **Stale-assignment surfacing volume.** §4.2's "re-run for 14 days on locale edit" may produce more flag noise than expected. Mitigation flagged in §10 (only re-run on qualifying-status-changing edits, not all edits) but not part of the contract. v5 implementation refinement.
- **Pre-flight pass on D-59/D-60/D-61 docs before v5 quotes them.** Predecessor handoff §8 "What might be missing" raised this for D-59/D-60; it's true for all three now. A Rule-#9-style sanity pass before the v5 spec rewrite quotes them as authoritative would catch any inconsistencies. Could be bundled into the v5 session opening.

**Best argument against this session's scope.**

A maximally minimal session would have done only the admin pass (CLAUDE.md pointer refresh) and stopped, deferring D-61 to its own dedicated session. The argument: design-doc quality benefits from a fresh chat where the chat budget is fully available, not divided between admin work and design work. Counter: the admin pass was 5 minutes of editing; the remaining session budget went to D-61. Bundling avoided a session that would have been ~95% idle.

A maximally larger session would have done D-61 *and* D-58 to ship the design wave's last two tracks in one chat. Counter: the per-row design doc + one-track-per-turn model exists because design-doc quality degrades when the chat juggles two undecided decision clusters; the predecessor handoff §4.4 D-60 reframe is the worst-case argument for keeping the tracks separate (Andy's "no inferences" reframe of D-60 would have been harder to absorb if the chat were also juggling D-58 open questions). Sticking to one track per session preserves the discipline.

---

*End of D-61 Onboarding Design Wave (3/4) closing handoff.*
