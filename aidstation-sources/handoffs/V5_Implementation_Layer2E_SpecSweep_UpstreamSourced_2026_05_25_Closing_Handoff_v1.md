# Layer 2E — Spec Sweep: Upstream-Sourced Classification Narrative + D-26 Hard-Blocker Correction — Closing Handoff

**Session:** Unblocked follow-through on PR #156. PR #156's `primary_movement` migration is parked awaiting a Neon run, so this session did the doc-only work that reconciles `Layer2E_Spec.md` with the already-shipped as-built code (the §6.2 item the PR #156 handoff explicitly left for Andy) plus the same-file D-26 "hard blocker" doc-sweep nit.
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_Layer2E_UpstreamSourced_PrimaryMovement_2026_05_25_Closing_Handoff_v1.md` (PR #156)
**Branch:** `claude/implementation-layer-unblocked-7RwuC`
**Status:** Shipped to branch. 1 substantive file (`Layer2E_Spec.md`, amended in place). Doc-only — no code/test change, **no deploy owed.**

---

## 1. Session-start verification (Rule #9)

The predecessor on `CURRENT_STATE.md`'s "Last shipped" pointer was the D-74/D-75 cleanup handoff, but the actual last shipped work is PR #156 (Layer 2E upstream-sourced classification) — its handoff §8 logged "CURRENT_STATE.md pointer bumped: ❌ owed (large-file edit deferred)." So PR #156's claimed code edits were anchor-checked against on-disk state:

| Claim (PR #156 §8) | Anchor | Result |
|---|---|---|
| `_ENDURANCE_PROFILE` / `_DISCIPLINE_PROFILE_VOTE` / `_STRENGTH_DOMINANT_IDS` removed | `grep` in `layer2e/` | ✅ no refs |
| `_endurance_profile` / `_movement_sport_profile` derive from upstream + warn | `layer2e/builder.py:208,223` | ✅ |
| `_CATEGORY_ENDURANCE` / `_MOVEMENT_SPORT_PROFILE` maps present | `layer2e/builder.py:175,190` | ✅ |
| Layer 2A query joins `layer0.disciplines` + selects both fields | `layer2a/builder.py:167-168,654-655` | ✅ |
| `Layer2ADiscipline` carries `discipline_category` + `primary_movement` | `layer4/context.py:227-228` | ✅ |
| Migration file present | `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` | ✅ exists |
| Migration run on Neon | (owed) | ❌ — **parked** (this is the blocker Andy flagged; out of scope this session) |
| `verify-handoff.sh` ❌ paths | `migrations/populate_terrain_gap_rules.sql`, `tests/test_layer2_modality.py`, `tests/test_v10/v11_parsers.py` | ✅ all explained by recent shipped work (D-76 deleted duplicate; Slice-6 deleted modality suite; R6 renamed v10→v11; script mis-parses the "v10/v11" string) — not real drift |

**Reconciliation note:** clean. PR #156 code is fully on-disk; the only owed item is the Neon migration (parked) + the CURRENT_STATE pointer bump (done this session, see §3.2). No code drift.

---

## 2. Session narrative

Andy: "let's work … I can't run the required ETL which came from this last PR for a bit. so we need to work on stuff which isn't blocked by that." Read `CLAUDE.md` + the PR #156 handoff + the rolling-state files; mapped blocked vs. unblocked. Blocked = deploying PR #156 (the Layer 2A query now `SELECT`s `dl.primary_movement`, a hard prerequisite) + the other owed-Neon items (K3 equipment ETL, `skill_capability_toggles`, D-74 idempotency redeploy). Presented an unblocked menu via `AskUserQuestion`; Andy picked **Layer 2E spec sweep**.

Convention call: the PR #156 handoff §6.2 framed the §5.3.3/§5.4.3 update as "a versioned-spec edit (Rule #12)." But the on-disk precedent for sibling layer specs (`Layer2B_Spec.md`, `Layer2C_Spec.md`) is **in-place amendment with dated audit-trail markers, no version bump** (e.g. "Amended 2026-05-20 (Phase 5.1 form-refresh C)", "(re-model Slice 4, 2026-05-25)"). `Layer2E_Spec.md` has no versioned copies. Followed the in-place precedent.

Scope discipline: the §3 input-shape drift nits are TWO different things. The `IncludedDiscipline` shape is directly coupled to the §5.3.3/§5.4.3 derivation change (it must now carry `discipline_category` + `primary_movement`) → done. The `TargetEvent` / `Layer1*` aspirational-shape rewrites are explicitly gated by CARRY_FORWARD on the §B / §I.1 onboarding form refresh landing → **left untouched** (doing them now would be premature and likely need redoing).

---

## 3. File-by-file edits

### 3.1 `aidstation-sources/Layer2E_Spec.md` (modified, in place)

- **Status line (§ header):** appended an "Amended in place 2026-05-25" note summarizing the sweep (traceability for the next Rule #9).
- **§3 Parameters table** (`included_disciplines` row): notes the upstream `discipline_category` + `primary_movement` classification now rides on the input + drives the §5.3.3 / §5.4.3 derivations.
- **§3 `IncludedDiscipline` dataclass:** added `discipline_category: str | None` and `primary_movement: str | None` with inline source/default comments.
- **§5.3.3:** new lead paragraph — endurance profile sourced from upstream `discipline_category` (category-prefix → `{Pure endurance | Mixed | Technical-dominant}`), no hand-maintained dict; protein band uses upstream `primary_movement` (`climbing` = strength-biased). Pseudo-code updated (`_endurance_profile(d)` reads `d.discipline_category`; protein checks `d.primary_movement in _STRENGTH_MOVEMENTS`). Replaced the stale "For v1: hard-coded by endurance_profile lookup" comment.
- **§5.4.3:** replaced the one-liner "Sport profile resolved from weighted discipline mix." with the upstream-sourced derivation narrative (movement → profile map matching the modifier table labels; >50% weighted vote else multi_sport; movement axis required because terrain `discipline_category` can't split swim vs paddle; missing → multi_sport, unknown logged). The modifier **table** itself was already correct (matches `_SPORT_PROFILE_CHO_MOD`) — only the resolution narrative changed.
- **§6.2** promotion-candidate row (`sport_endurance_modifier`): fixed the stale "classification that itself is hand-coded" clause → "now sourced from upstream `primary_movement`".
- **§6.1 / §12 (2E-6) / §14 (×2):** flipped the D-26 `supplement_vocabulary` "hard blocker" framing to ✅ Resolved (FC-1, 2026-05-11), with the audit-trail note that the residual §5.5 supplement-integration stub roots in an input-shape gap (free-text `supplement_protocol_notes` vs structured `AthleteSupplementRecord`), not vocab availability — closed by the §I.1 form refresh. Struck-through rather than deleted to keep the audit trail.

### 3.2 Bookkeeping

- `CURRENT_STATE.md` — "Last shipped session" pointer bumped to this handoff; folded in PR #156's owed pointer as the first predecessor block (so the chain is now complete: this → PR #156 → D-74/D-75).
- `CARRY_FORWARD.md` — Doc-sweep nit "`Layer2E_Spec.md` §6.1 + §14 D-26 hard blocker" struck through as ✅ Resolved 2026-05-25.

---

## 4. Code / tests

None. Doc-only session; no code touched, no test delta.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Run the PR #156 migration on Neon, then merge/deploy #156.** This is the parked HARD prerequisite — until `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` runs on Neon, every Layer 2A invocation errors (`column dl.primary_movement does not exist`) once #156 deploys. Order: migration first (or atomically), then merge. The spec now matches the code, so once the migration lands the loop is fully closed.

### 6.2 Alternative pivots (all unblocked, no Neon dependency)
- **Form-feedback UI batch** — the parked race-event/injury form simplifications (distance-or-duration, drop aid-station count, mandatory-gear → pack-weight/portage, injury copy, schedule). Template/route work, testable locally.
- **Structured-supplements (§I.1)** — de-stubs Layer 2E §5.5; needs a plan-mode gate on schema shape (`athlete_supplement_records` table vs JSONB column). This is what closes the remaining 2E-6 work the D-26 correction now points at.
- **§3 `TargetEvent` / `Layer1*` spec rewrites** — only ripe once the §B / §I.1 onboarding form refresh lands (CARRY_FORWARD-gated).

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `Project_Backlog_v62.md` 6. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| track | Layer 2E spec sweep over form-feedback / gated items | Andy at gate | Unblocked, contained, closes the loop on PR #156; zero Neon dependency. |
| mechanism | In-place amendment + dated markers (no version bump) | this agent | Matches the on-disk Layer2B/2C precedent; `Layer2E_Spec.md` has no versioned copies; keeps cross-references stable. |
| scope | Do `IncludedDiscipline` §3 edit; **defer** `TargetEvent`/`Layer1*` §3 rewrites | this agent | The first is coupled to the §5.3.3/§5.4.3 change; the latter are CARRY_FORWARD-gated on the form refresh landing — doing them now would be premature. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| §5.3.3 narrative + pseudo-code describe upstream `discipline_category` derivation | ✅ `Layer2E_Spec.md` §5.3.3 |
| §5.4.3 narrative describes upstream `primary_movement` derivation; modifier table unchanged | ✅ §5.4.3 |
| §3 `IncludedDiscipline` carries `discipline_category` + `primary_movement` + param note | ✅ §3 |
| D-26 "hard blocker" corrected in §6.1 / §12 (2E-6) / §14 risk bullet / §14 closing | ✅ `grep` — only struck-through audit-trail mention remains |
| §6.2 stale "hand-coded" clause fixed | ✅ §6.2 |
| No stale `weighted discipline mix` / `_lookup_sport_endurance_profile` / `_is_strength_dominant` refs | ✅ `grep` clean |
| `TargetEvent` / `Layer1*` §3 shapes left untouched (gated) | ✅ unchanged |
| Status-line amendment note added | ✅ §header |
| CURRENT_STATE pointer bumped + PR #156 pointer folded in | ✅ |
| CARRY_FORWARD D-26 nit struck through | ✅ |
| Working tree | (committed this session) |

---

## 9. Files shipped this session

**Substantive (1 file):**
1. `aidstation-sources/Layer2E_Spec.md` — in-place amendment (see §3.1).

**Bookkeeping (3 files):**
2. `aidstation-sources/CURRENT_STATE.md` — pointer bump + PR #156 fold-in.
3. `aidstation-sources/CARRY_FORWARD.md` — D-26 nit struck through.
4. `aidstation-sources/handoffs/V5_Implementation_Layer2E_SpecSweep_UpstreamSourced_2026_05_25_Closing_Handoff_v1.md` — this handoff.

The 5-file ceiling applies to substantive files only.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` Doc-sweep nits: the "`Layer2E_Spec.md` §6.1 + §14 — D-26 hard blocker" item flipped to ✅ Resolved 2026-05-25. The two §3 input-shape drift nits (`TargetEvent` vs `RaceEventPayload`; `Layer1*` type drift) remain open and explicitly gated on the §B / §I.1 onboarding form refresh.

---

**End of handoff.**
