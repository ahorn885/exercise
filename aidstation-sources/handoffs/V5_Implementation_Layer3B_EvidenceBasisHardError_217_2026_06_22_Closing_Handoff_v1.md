# V5 — #217: 3B evidence-basis mode-discriminator flipped warning → hard error (closing)

**Date:** 2026-06-22. **Branch:** `claude/layer3-gate-epic-handoff-eb1ino`. **PR:** pending Andy's "open it" (PR-gated operating model). **Issue:** #217 (parent #211). **Predecessor / next-work map:** `handoffs/V5_Layer3_GateEpic_NextWork_211_213_2026_06_22_Kickoff_Handoff_v1.md` §4/§7.

---

## 1. What shipped

`layer3b/builder.py` `_check_evidence_basis(...)` bundled **two** distinct checks under the single `Layer3BEvidenceBasisWarning`:

1. **Name-existence** — a cited `evidence_basis` path absent from the input set. This is the *same* check 3A runs, and 3A keeps it **warn-only**. Not tied to §H.2.
2. **§7 mode-discriminator** — event-mode `goal_viability.evidence_basis` must reference ≥1 `h2.*` field; no-event must reference none. D9/L3B-P-2/L3B-P-3 explicitly gate *this* on the §H.2 form-refresh.

#217 = "now that §H.2 goal capture shipped, flip the 3B evidence-basis warning to a hard error." **Scope ratified with Andy in chat: flip only the mode-discriminator (sites 2 & 3) → hard `Layer3BOutputError('evidence_basis_mode_violation')`; keep name-existence warn-only** (parity with 3A; it's not what §H.2 gated).

**Why the flip is safe (Andy's question, confirmed against code):** the missing-goal *entry gap* never reaches the LLM — `_validate_inputs` §4 (`layer3b/builder.py:445`) already hard-raises `Layer3BInputError('event_mode_missing_goal_outcome')` **before** any LLM call when an event-mode plan lacks `goal_outcome`. So by the time the model runs, the goal data is guaranteed present, and a missing/illegal `h2.*` citation can only be an **LLM grounding defect** — exactly what should fail, not an athlete-entry gap (which is caught upstream).

**Rule #15 (Andy's explicit ask — "see how often plans fail because of this"):** a `print("_check_evidence_basis: FAIL evidence_basis_mode_violation mode=… reason=… …")` precedes each raise, carrying the mode + the offending `evidence_basis` paths, so `/admin/logs` (Rule #14) can count the prod failure rate. **No retry was added** — a non-clean output fails the plan; if the FAIL line fires more than expected, the documented next step is a single re-prompt before raising (flagged in the prompt gut-check).

**No contract / schema / migration / cache change.** It's a post-LLM output check; prompt *wording* is unchanged, so no `LAYER3_GATE_PROMPT_REVISION` / `LAYER4_PROMPT_REVISION` bump.

---

## 2. Files touched (4 substantive)

| File | Change | Verify |
|---|---|---|
| `layer3b/builder.py` | `_check_evidence_basis`: name-existence stays `warnings.warn`; the two mode-discriminator branches now `print()` (Rule #15) + `raise Layer3BOutputError("evidence_basis_mode_violation", detail=…)`. Module-docstring item 6, the call-site comment (~step 5), and the `llm_…` algorithm-docstring item 6 synced. | `grep -n "evidence_basis_mode_violation" layer3b/builder.py` → 2 hits (both raises) |
| `tests/test_layer3b_builder.py` | `TestEvidenceBasisCheck`: `test_event_mode_missing_h2_reference_warns`→`…_raises` and `test_no_event_mode_with_h2_reference_warns`→`…_raises` (both `pytest.raises(Layer3BOutputError)`, assert `.code == "evidence_basis_mode_violation"`). `test_unknown_path_warns` unchanged (still warns). | `grep -n "_raises" tests/test_layer3b_builder.py` in `TestEvidenceBasisCheck` |
| `specs/Layer3_3B_Spec.md` | §7 schema-level rules: the two mode-discriminator bullets annotated **"Hard-enforced (#217) → `Layer3BOutputError('evidence_basis_mode_violation')`"**. | `grep -n "Hard-enforced" specs/Layer3_3B_Spec.md` → 2 hits |
| `prompts/Layer3B_v1.md` | D9 cell, §8.3 mode-discriminator bullet, the algorithm Step-5 line, and the gut-check (L3B-P-3 row CLOSED + the prose paragraph) all flipped from "warn-only/telemetry" to the hard-error description. | `grep -n "#217" prompts/Layer3B_v1.md` → 4 hits |

Bookkeeping (not counted): `CURRENT_STATE.md` top entry, this handoff, issue #217 reconcile.

---

## 3. Tests

Container recipe (handoff §6.2 — dead-localhost `DATABASE_URL` + front-loaded `test_layer4_*` to dodge the single-file circular-import collection quirk):

```
DATABASE_URL="postgresql://u:p@127.0.0.1:5999/none?connect_timeout=2" /tmp/venv/bin/python -m pytest \
  tests/test_layer4_orchestrator.py tests/test_layer3b_builder.py \
  tests/test_layer3_cached_wrappers.py tests/test_layer3b_smoke.py \
  tests/test_layer3d_gate.py tests/test_layer3d_wiring.py -q
```

- `test_layer4_orchestrator` + `test_layer3b_builder` → **169 passed**.
- Broader layer3/4 batch above → **245 passed / 7 skipped**. The 3 residual warnings are the *name-existence* check correctly still warning (incl. one in the no-event raise test, which warns on `h2.goal_outcome` not being a no-event input key, then raises — both fire; the test asserts the raise).

**No LIVE-VERIFY owed by Claude** — deterministic post-LLM check, fully covered by the stubbed suite. The prod signal to watch is the new `/admin/logs` `_check_evidence_basis: FAIL evidence_basis_mode_violation` line frequency.

---

## 4. Open / next

- **#217 → close on merge** (commented + ready; see issue reconcile).
- **3C (the headline remaining 3D node):** **#216 is a STOP-AND-ASK** — rules-only vs LLM + enumerate the cross-node conflict rules with Andy *before* building **#844** (`map_3c_items()` drop-in, no contract change). Do not start #844 before #216 is ratified. Full shape in the #211 kickoff handoff §3.
- **#302** orphaned-analysis tie-in (now attractive — the 3D gate can consume 3A/3B `notable_observations`).
- **#213 live-verify** (Andy-action, still owed): park a plan at `needs_review` → working `[Fix this]` links + edit-a-field → re-kick + re-evaluate + `_rekick_stale_gate:` log line.

---

## 5. Operating notes (§6.3 — next-session read order, Rule #13)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry (this #217 session).
3. `CARRY_FORWARD.md` — Layer-3 rolling items.
4. **This handoff** + the #211 next-work kickoff handoff (for the 3C / #302 map).
5. `aidstation-sources/scripts/verify-handoff.sh` — anchor sweep. Then `git fetch origin main` + check #216/#844/#302 for in-flight parallel work (the collision lesson).

**PR-gated:** committed + pushed on the session branch; bookkeeping rides this branch; **wait for Andy's "open it"** before opening the PR, then `enable_pr_auto_merge`. Required checks: `Python unit suite (stubbed)` / `JS harness (jsdom)` / `Layer 0 integrity gate`.
