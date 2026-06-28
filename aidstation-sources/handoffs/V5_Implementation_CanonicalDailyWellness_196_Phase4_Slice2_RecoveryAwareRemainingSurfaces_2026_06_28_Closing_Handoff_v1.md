# V5 Implementation — #196 Phase 4 Slice 2: Fold Recovery-Aware Guidance into the Remaining Layer-4 Surfaces — Closing Handoff (2026-06-28)

**Branch:** `claude/recovery-aware-planning-hypeol` · **Suite:** 3590 passed / 30 skipped · **PR:** not yet opened (awaiting Andy's go) · **Predecessor (Slice 1):** `handoffs/V5_Implementation_CanonicalDailyWellness_196_Phase4_Slice1_RecoveryAwarePlanning_2026_06_28_Closing_Handoff_v1.md` · **Kickoff/agenda:** `handoffs/V5_CanonicalDailyWellness_196_Phase4_RecoveryAwarePlanning_Kickoff_2026_06_28_v1.md` · **Design (Phase 2 substrate):** `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md` · **Epic:** #196 (stays OPEN — Phase 5 + Phase-2 leftovers remain).

> **▶ IMMEDIATE NEXT:** Phase 4 is complete (all five Layer-4 surfaces now condition on recovery state). Next #196 work is **Phase 5** + the parked Phase-2 leftovers (`/wellness` chart repoint in `routes/wellness.py`; `coaching.get_wellness_summary` — v1-only, out of scope). Channel (b)/(c) escalation (raw-threading / a dedicated `recovery_state` field) remains parked — pursue only if the 3A digest proves lossy once real data flows.

---

## 1. What this slice did (one line)

The Slice-1 `format_recovery_guidance` helper is now folded into the three remaining Layer-4 prompt surfaces — **PerPhase** (main plan build), **RaceWeekBrief**, and **single_session** — so all five Layer-4 surfaces (T2/T3 from Slice 1 + these three) condition on the athlete's recovery state via the same freshness-gated, strong-lean LLM-soft guidance, surfaced from the *already-hashed* `Layer3APayload` digest with **zero new input to any L4 cache key**.

## 2. Context + the one decision this session

Slice 1 (PR #936, merged `d86aa44`) shipped the `recovery_guidance.py` helper and wired it into the two refresh tiers. The Slice-1 handoff pre-cleared this slice's **mechanism** (channel (a), verbatim wording reuse) — STOP-AND-ASK is cleared unless the wording is *materially adapted per surface*.

**Decision (Andy 2026-06-28, AskUserQuestion):** the shipped helper's directive said "PRIORITIZE recovery **in this refresh**", which is correct for T2/T3 but reads wrong on the three Slice-2 surfaces (PerPhase is the *initial plan build*, single_session is one session, RaceWeekBrief is a brief — none is "a refresh"). Andy chose **genericize the one phrase**: "in this refresh" → "**here**". This is a non-material edit (the coaching directive is unchanged; the refresh tiers stay correct with "here"), keeping the wording single-sourced and verbatim-shared across all five surfaces. The **per-surface adaptation** path (e.g. RaceWeekBrief taper-aware phrasing, a surface param) was explicitly **not** taken — that would have re-triggered Trigger #1 and added a surface param for no benefit (the helper already says "unless a race-proximity constraint overrides").

## 3. What shipped (3 substantive files + 1 test edit + 1 helper one-phrase edit)

- **`layer4/recovery_guidance.py`:** one-phrase genericization — `"PRIORITIZE recovery in this refresh:"` → `"PRIORITIZE recovery here:"`. Nothing else changed; the gate, Block A/B structure, surfaced fields, and Rule #15 print are untouched from Slice 1.
- **`layer4/per_phase.py`:** `from layer4.recovery_guidance import format_recovery_guidance`; `parts.append("")` + `parts.extend(format_recovery_guidance(layer3a_payload))` immediately after the 3A `Data density:` line in the `=== Athlete context ===` block (before the `#337` measured-physiology block). `layer3a_payload` was already a parameter — no signature change.
- **`layer4/race_week_brief.py`:** same import + `parts.extend(format_recovery_guidance(layer3a_payload)); parts.append("")` after the `- Data density:` line in the `# Current athlete state (3A)` block (before `# Periodization phase (3B Taper context)`).
- **`layer4/single_session.py`:** same import + `parts.extend(format_recovery_guidance(layer3a_payload)); parts.append("")` after the `- Data density:` line in the `## Layer 3A summary` block (before `# Retry context`).
- **`tests/test_layer4_plan_refresh_recovery.py` (+2 → 8):** `TestSurfaceNeutralWording.test_directive_is_surface_neutral` (asserts `PRIORITIZE recovery here:` present, `in this refresh` absent — guards the genericization) + `TestSingleSourced.test_slice2_surfaces_share_one_helper` (per_phase / race_week_brief / single_session all reference the same `format_recovery_guidance` object — single-source pin, the Slice-2 analog of the Slice-1 both-tiers pin).

The helper is still a leaf module (`Layer3APayload` under `TYPE_CHECKING` only) → the three new importers introduce no import cycle (full suite imports clean).

## 4. Cache-key safety (Trigger #3)

Identical property to Slice 1: **no new function argument, no new payload field, no DDL.** All three render functions already received `layer3a_payload`; the new block renders existing-but-hidden fields of the already-hashed digest. Rendered prompt *text* is not part of any cache key. Therefore **no cache invalidation, no forced plan re-runs, no Neon apply owed.** The one-phrase wording edit changes the rendered text of all five surfaces but — again — rendered text is not hashed.

## 5. Tests + verification

- `SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:5999/none?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3590 passed / 30 skipped** (= 3588 Slice-1 baseline + 2 new; the 3 Layer3B `evidence_basis` warnings pre-exist, #217). Run the **full** `tests/` (isolated single-file collection hits the circular-import quirk).
- **LIVE-VERIFY (OWED — Andy, gated on data; shared with Slice 1):** after the Garmin wellness re-upload (post-#934) fills `daily_wellness_metrics` → materialize hook → `canonical_daily_wellness` → 3A digests it → trigger an **initial plan build** (PerPhase), a **race-week brief**, and/or a **single-session** synth and confirm `/admin/logs` shows `[recovery-guidance] fresh=True …` and the synthesized output eases load on a fatigued/overreach day. The wording/threading do not need live data; this is live proof only.

## 6. NEXT

Phase 4 is complete. Remaining #196 work:
- **Phase 5** (per the epic).
- **Parked Phase-2 leftovers:** `/wellness` chart repoint (`routes/wellness.py`); `coaching.get_wellness_summary` (v1-only, out of scope).
- **Parked escalation:** channel (b) raw-threading / (c) a dedicated `recovery_state` field — only if the 3A digest disappoints on real data (both widen the L4 hash + carry the day-anchored-cache-discipline burden; (a) carries none).
- **Orthogonal:** #884 gear/craft PAUSED mid-arc at slice 3b — slices 4→6 remain.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this slice). 3. `CARRY_FORWARD.md`. 4. This handoff + the Slice-1 closing handoff + the Phase-4 kickoff. 5. `layer4/recovery_guidance.py` + the three insertion sites (`per_phase.py` `=== Athlete context ===`, `race_week_brief.py` `# Current athlete state (3A)`, `single_session.py` `## Layer 3A summary`). 6. `aidstation-sources/scripts/verify-handoff.sh`.

## 7. Open questions
- **RaceWeekBrief taper-aware phrasing.** Deferred (Andy chose verbatim+genericized, not per-surface). The helper's "unless a race-proximity constraint overrides" already covers the taper case; revisit only if it reads under-specified for race week once live.
- **Combined-vs-per-discipline ACWR redundancy.** Unchanged from Slice 1 — Block A surfaces per-discipline ACWR; the existing 3A blocks already print combined ACWR. Slight redundancy (different grains) accepted; revisit if noisy live.

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Helper wording | `layer4/recovery_guidance.py` | `PRIORITIZE recovery here:` present; `in this refresh` absent (genericized) |
| PerPhase wiring | `layer4/per_phase.py` | `from layer4.recovery_guidance import format_recovery_guidance` + `parts.extend(format_recovery_guidance(layer3a_payload))` after the `Data density:` line in `=== Athlete context ===` |
| RaceWeekBrief wiring | `layer4/race_week_brief.py` | same import + `parts.extend(format_recovery_guidance(layer3a_payload))` after the `- Data density:` line in `# Current athlete state (3A)` |
| single_session wiring | `layer4/single_session.py` | same import + `parts.extend(format_recovery_guidance(layer3a_payload))` after the `- Data density:` line in `## Layer 3A summary` |
| Tests | `tests/test_layer4_plan_refresh_recovery.py` | 8 tests: 6 Slice-1 + `test_directive_is_surface_neutral` + `test_slice2_surfaces_share_one_helper` |
| Cache key | `layer4/hashing.py` | unchanged — no new payload field / no new arg; rendered prompt text is not hashed → no invalidation |
| Suite | — | `… pytest tests/ -q` → 3590 passed / 30 skipped |
| Neon | — | **No apply owed** — no DDL, no schema change |
| Epic | #196 | OPEN — comment Slice 2 shipped (Phase 4 done); Phase 5 + Phase-2 leftovers remain |
