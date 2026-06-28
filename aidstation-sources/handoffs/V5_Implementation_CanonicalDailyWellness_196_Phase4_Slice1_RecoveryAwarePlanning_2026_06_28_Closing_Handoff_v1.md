# V5 Implementation — #196 Phase 4 Slice 1: Recovery-Aware Planning (LLM-soft) on the Refresh Tiers — Closing Handoff (2026-06-28)

**Branch:** `claude/phase4-slice23-handoff-a0abm5` · **Suite:** 3588 passed / 30 skipped · **PR:** [#936](https://github.com/ahorn885/exercise/pull/936) (auto-merge SQUASH armed) · **Kickoff/agenda:** `handoffs/V5_CanonicalDailyWellness_196_Phase4_RecoveryAwarePlanning_Kickoff_2026_06_28_v1.md` · **Design (Phase 2 substrate):** `designs/CanonicalDailyWellness_196_Phase2_Design_v1.md` · **Epic:** #196 (stays OPEN — Slice 2 + Phase 5 remain).

> **▶ IMMEDIATE NEXT:** Phase 4 Slice 2 — fold the same `format_recovery_guidance` helper into the remaining Layer-4 prompt surfaces (`per_phase.py`, `race_week_brief.py`, `single_session.py`). Same channel (a), same wording, no new cache-key input. STOP-AND-ASK is **cleared for the mechanism** (ratified this session); a Slice-2 design gate is only needed if the wording is materially adapted per surface.

---

## 1. What this slice did (one line)

The Layer-4 **plan-refresh** prompts (T2 + T3) now condition on the athlete's recovery state via **LLM-soft guidance** surfaced from the *already-hashed* `Layer3APayload` digest — freshness-gated, strong-lean — adding **zero new input** to the Layer-4 cache key.

## 2. Context + the decisions ratified this session

Phase 2 made wellness consumer-ready (substrate + writer + ingest hooks + the 3A reader repoint, Slice 2.3 merged as PR #935). Phase 4 is the consumption side: make plan-gen ease load when recovery is suppressed. The kickoff framed a 5-decision `/plan` agenda; it was put to Andy (AskUserQuestion ×2 + a plain-language tradeoff round) and ratified:

1. **Channel = (a) the existing 3A digest.** The decisive finding (Explore map): the 3A digest already flows into all five L4 prompts **and already folds wholesale into every L4 cache key** (`layer3a_hash` in `hashing.py:plan_refresh_key` etc.). The recovery signals we want — `recent_trajectory.short_term/medium_term.{direction,reasoning_text}`, per-discipline + combined `acwr_status.zone`, `notable_observations` — already live in that payload; the prompt bodies just rendered a thin slice (direction enums + combined ACWR) and never surfaced the reasoning text, per-discipline ACWR, or observations. So this slice is **prompt-text only**: render existing-but-hidden fields + add the guidance wording. No payload field added → re-run fingerprint unchanged. **Escalate to (b) raw-threading or (c) a dedicated `recovery_state` field only if the digest proves lossy once real data flows** (both widen the L4 hash and carry the day-anchored-cache-discipline burden; (a) carries none).
2. **Surfaces = Refresh T2/T3 first** — the most reactive-to-incoming-data tiers, smallest blast radius. PerPhase / RaceWeekBrief / single_session are Slice 2.
3. **Freshness = gate** — inject the recovery block only when recent HRV/sleep exists; else an explicit "do not infer" line (Andy's wellness is empty until he re-uploads post-#934, so the no-data path is today's default).
4. **Posture = strong-lean** — push hard toward de-load on poor recovery, still short of a hard rule. (The freshness gate is what makes strong-lean safe today: with no data, Block B fires and nothing de-loads spuriously.)

(Trigger #1 prompt wording — the actual block text — is reproduced verbatim in §3 below and was approved at plan-exit.)

## 3. What shipped (3 substantive files + 1 test file)

- **`layer4/recovery_guidance.py` (NEW) — `format_recovery_guidance(layer3a_payload) -> list[str]`:** the single home for the wording (shared across tiers, reused by Slice 2). Gate: `fresh = data_density.recent_hrv_count > 0 or data_density.recent_sleep_count > 0`.
  - **Block A (fresh):** header `=== Recovery state (3A wellness — act on this) ===`; both trajectory lines as `{direction} — {reasoning_text}`; an `ACWR by discipline:` sub-list (sorted; omitted if `per_discipline` empty); a `Recovery flags (3A):` sub-list from `notable_observations` filtered to `warning`/`data_gap` (omitted if none); then the strong-lean `Guidance:` directive (PRIORITIZE recovery on `fatigued`/`overreached`/HRV-down/sleep-debt/`functional_overreach`/`non_functional_overreach` → pull volume to the band's lower edge + cut intensity bias Z1-Z2 unless race-proximity overrides; conflict → conservative load; solid recovery → don't under-load; *coaching judgment, not a hard rule, separate from the calendar deload cadence*).
  - **Block B (no data):** header `=== Recovery state (3A wellness) ===` + "No recent HRV or sleep data … Do not infer a recovery state or fatigue level from its absence — plan the normal progression for this phase."
  - **Rule #15:** `print(f"[recovery-guidance] fresh=… short=… acwr_combined_zone=… hrv_n=… sleep_n=… injected_block=A|B")`.
  - Leaf module — imports nothing from `layer4` at runtime (`Layer3APayload` under `TYPE_CHECKING` only) → no import cycle with `per_phase`/`plan_refresh*` (which will import it in Slice 2).
- **`layer4/plan_refresh_t2.py`:** `from layer4.recovery_guidance import format_recovery_guidance`; `parts.extend(format_recovery_guidance(layer3a_payload)); parts.append("")` immediately after the existing `=== Athlete state (3A — re-run as part of refresh cascade) ===` block.
- **`layer4/plan_refresh_t3.py`:** same import + same insertion after its `=== Athlete state (3A — re-run as part of T3 cascade) ===` block.
- **`tests/test_layer4_plan_refresh_recovery.py` (NEW, +6):** app-free unit tests against the helper — fresh→Block A (strong-lean directive present, trajectory reasoning + per-discipline ACWR + `warning`/`data_gap` flags surfaced); sleep-only counts as fresh; empty ACWR/observations omit their sub-lists; only `warning`/`data_gap` categories surface (`opportunity`/`data_hygiene` excluded); no-data→Block B with the directive **absent**; both tiers share the one helper object (single-source pin).

## 4. Cache-key safety (Trigger #3)

The repoint adds **no new function argument and no new payload field**. `plan_refresh_key` (`hashing.py`, `layer3a_hash` at ~L382) hashes the `Layer3APayload`, which already contained every field the new block renders. The rendered prompt *text* is not part of any cache key. Therefore: **no cache invalidation, no forced plan re-runs, no Neon apply owed** (no DDL). This is exactly why channel (a) was recommended and chosen.

## 5. Tests + verification

- `SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:5999/none?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3588 passed / 30 skipped** (= 3582 Slice-2.3 baseline + 6 new; the 3 Layer3B `evidence_basis` warnings pre-exist, #217). Run the **full** `tests/` (isolated single-file collection hits the circular-import quirk).
- **LIVE-VERIFY (OWED — Andy, gated on data):** after the Garmin wellness re-upload (post-#934 deploy) → `daily_wellness_metrics` fills → Slice-2.2 hook materializes `canonical_daily_wellness` → 3A digests it → trigger a T2/T3 refresh and confirm `/admin/logs` shows `[recovery-guidance] fresh=True …` and the synthesized refresh eases load on a fatigued/overreach day. The wording/threading do not need live data; this is live proof only.

## 6. NEXT — Phase 4 Slice 2 (fold in the remaining surfaces)

Reuse `format_recovery_guidance` in `layer4/per_phase.py` (PerPhase synthesis — the main plan build), `layer4/race_week_brief.py`, and `layer4/single_session.py`. Each already renders its own `=== Athlete context / Current athlete state (3A) ===` block (the 3A render is duplicated, not shared — a `simplify`-pass candidate later). Same channel (a) → same zero-cache-key-cost property. Decide at build whether RaceWeekBrief wants race-proximity-aware phrasing (its guidance already weighs taper).

Parked: channel (b)/(c) escalation (only if the digest disappoints on real data); `/wellness` chart repoint + `coaching.get_wellness_summary` (Phase-2 leftovers); #884 gear/craft (paused mid-arc at slice 3b).

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this slice). 3. `CARRY_FORWARD.md` → "#196 … Phase 4 … Slice 1 SHIPPED" bullet. 4. This handoff + the Phase-4 kickoff. 5. `layer4/recovery_guidance.py` + the two `plan_refresh_t2/t3.py` insertion sites + the §3 anchor render-blocks in `per_phase.py` / `race_week_brief.py` / `single_session.py`. 6. `aidstation-sources/scripts/verify-handoff.sh`.

## 7. Open questions
- **Per-surface wording.** Should PerPhase (fresh-plan build, no "this refresh" framing) and RaceWeekBrief (taper-aware) reuse the refresh wording verbatim or get light per-surface adaptation? Decide at Slice-2 build; a material reword re-triggers Trigger #1.
- **Combined-vs-per-discipline ACWR in the prompt.** Block A surfaces per-discipline ACWR; the existing 3A block already prints combined ACWR (RaceWeekBrief). Slight redundancy is acceptable (different grains); revisit if it reads noisy live.

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Helper | `layer4/recovery_guidance.py` | `def format_recovery_guidance(layer3a_payload)`; gate `recent_hrv_count > 0 or recent_sleep_count > 0`; Block A header `=== Recovery state (3A wellness — act on this) ===`; Block B "Do not infer"; `[recovery-guidance]` Rule #15 print |
| T2 wiring | `layer4/plan_refresh_t2.py` | `from layer4.recovery_guidance import format_recovery_guidance` + `parts.extend(format_recovery_guidance(layer3a_payload))` after the `=== Athlete state (3A — re-run as part of refresh cascade) ===` block |
| T3 wiring | `layer4/plan_refresh_t3.py` | same import + `parts.extend(...)` after the `=== Athlete state (3A — re-run as part of T3 cascade) ===` block |
| Tests | `tests/test_layer4_plan_refresh_recovery.py` | 6 tests: fresh Block A / sleep-only-fresh / empty-sublists-omitted / category-filter / no-data Block B (directive absent) / single-source pin |
| Cache key | `layer4/hashing.py` | `plan_refresh_key` unchanged — no new payload field; `layer3a_hash` already carries the surfaced fields → no invalidation |
| Suite | — | `… pytest tests/ -q` → 3588 passed / 30 skipped |
| Neon | — | **No apply owed** — no DDL, no schema change |
| Epic | #196 | OPEN — comment Slice 1 shipped; Slice 2 (PerPhase/RaceWeekBrief/single_session) + Phase 5 remain |
