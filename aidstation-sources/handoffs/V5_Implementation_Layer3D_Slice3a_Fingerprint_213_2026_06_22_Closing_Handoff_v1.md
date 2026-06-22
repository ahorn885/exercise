# V5 — Layer 3D HITL Gate Slice 3a: the `evaluated_against` input fingerprint (#213)

**Date:** 2026-06-22. **Branch:** `claude/magical-carson-snzvvh`. **Outcome:** Slice 3a shipped — the Trigger-#3 `evaluated_against` fingerprint contract, spec-first then coded. PR opened (ready, auto-merge). The divergent **#874** was closed as superseded first. **Net to `main` (via PR):** spec `Layer3D_Spec.md` (§6.1.1 new + §11.2 rewrite) + `layer3d/gate.py` + `layer4/orchestrator.py` + `tests/test_layer3d_gate.py` + the bookkeeping.

> **⚠️ SUPERSEDED IN PART (post-merge) — see §9.** After #881 merged, a parallel session's **#880** (`5959ed7`) was found to have shipped the *same* #213 staleness re-fire a different way ("Reading-B"). Andy chose to consolidate on #880; #881's "Reading-A" code (this handoff's §2–§3) was **reverted** and the spec rewritten to Reading-B in a follow-up cleanup PR. §1–§8 describe the as-built #881 Reading-A (now reverted); **§9 is the authoritative final state.**

---

## 1. What this session did

1. **Closed #874 as superseded.** This branch had earlier built Slice 3 a simpler way — a `stale: bool` flag + a *synchronous* advance-loop re-gate, all-in-one. The parallel **#873** session design-gated Slice 3 with **different** ratified decisions (real fingerprint, async recompute, 3a/3b split). Andy chose "hold #874, build per #873." Disabled auto-merge on #874, closed it (commit `5b4de06` preserved via the closed PR for cherry-picking the `[Fix this]` bits), reset this branch to `main`.
2. **Spec-first §6.1.1/§11.2, signed off before code** (Trigger #3). Presented the fingerprint contract; Andy approved (incl. the two confirmations — per-layer fingerprint, `h2.*`→`race_events`). Commit `dca4121`.
3. **Built Slice 3a** to the contract. Commit `8c17f95`. Gate suite **42 passed**.

---

## 2. The contract (as built — `Layer3D_Spec` §6.1.1)

`evaluated_against: dict[str,str]` widened from the Layer-0 etl digest (blind to athlete edits) to a per-athlete **input fingerprint**, computable **without an LLM call** so the staleness check (§11.2) is cheap:

```
{
  "layer1":    compute_payload_hash(layer1_payload),     # athlete profile (DB rebuild)
  "2A":        compute_payload_hash(layer2a_payload),    # deterministic query node
  "2C":        compute_layer2c_bundle_hash(locale→hash), # deterministic query node
  "2D":        compute_payload_hash(layer2d_payload),    # deterministic query node
  "3B_inputs": sha256(race_event_id | canonical_json(section_h2_kwargs)),
  "etl":       canonical_json(etl_version_set),
}
```

- **2E/3A/3B carry no key** — covered transitively (pure functions of the fingerprinted inputs). **2E was the spec correction:** it runs *after* 3B in `_upstream_full_cone` (consumes `start_phase`), so it can't be hashed standalone — my first spec draft wrongly listed it as a cheap query hash.
- **`3B_inputs`** captures the target-race/goal inputs 3B consumes that aren't yet folded into `layer1` (the §H.2 D11 kwargs — `goal_outcome`, `event_date`, `race_distance_km`, …). This is what makes an `h2.*` race edit register as staleness. Verified against `layer3b/cached_wrapper.py:layer3b_goal_timeline_viability_key` (which folds `layer1_hash`, `layer3a_hash`, `layer2a_hash`, `race_event_id`, `current_date`, `non_event_goal_type`, `etl`, `section_h2_kwargs`, model params).
- **Deliberately omitted (both backstopped by the generate-click real re-run):** `current_date` (else every parked plan goes stale on the next calendar day → a 3B LLM re-fire on page-views — the synchronous-on-GET cost the async model rejects) + the 3A/3B model/prompt params (change only on a deploy). **Andy reviewed + accepted this call.**
- **Comparison** = dict equality; an absent/empty stored fingerprint compares unequal → stale → recomputed once (self-healing, no migration).

---

## 3. Code as built

- **`layer3d/gate.py`** — `compute_gate_fingerprint(*, layer1_payload, layer2a_payload, layer2c_payloads, layer2d_payload, etl_version_set, race_event_id, section_h2_kwargs)` (pure; lazy-imports `layer4.hashing`). `evaluate_layer3d_gate` gained `evaluated_against: dict[str,str] | None = None` → used if given, else falls back to the coherent `etl_version_set` (Slice-1 aggregation-only callers + unit tests stay green). The `_coherent_etl_version_set` check is unchanged (still validates + raises §4 `etl_version_set_mismatch`).
- **`layer4/orchestrator.py`** — `_UpstreamFullCone` gained `gate_fingerprint: dict[str,str]`, composed at the end of `_upstream_full_cone` (all cheap inputs in scope: `layer1_payload`, `layer2a_payload`, `layer2c_payloads`, `layer2d_payload`, `etl_version_set`, `target_race_event.race_event_id`/`None`, `section_h2_kwargs`). The gate hook in `orchestrate_plan_create` passes `evaluated_against=cone.gate_fingerprint` + a Rule #15 `print("layer3d gate: pv=… status=… items=… fp=…")` (hashes truncated). No generate-guard change — generation already can't run stale (the advance loop re-runs the cone + re-gates via `Layer3DGateBlocked`).
- **`tests/test_layer3d_gate.py`** — `+8` (`_fingerprint()` helper + key-set/LLM-omission, determinism, per-input isolation for layer1/etl/2D/3B_inputs, `evaluate` stores the passed fingerprint, `evaluate` falls back to etl).

---

## 4. Slice 3b — the deferred remainder (mechanically-applicable, Rule #11)

3b is the **staleness-re-fire mechanism's consumer** + the revise links. Why it's one slice: the cheap **on-view** check and the **async recompute** both need the *same* new capability — building the upstream cone **off the request path, stopping before the 3A/3B LLM**. Re-verify all line refs (Rule #9) — they drift.

### 4.1 The partial-cone fingerprint helper (the keystone)
- In `layer4/orchestrator.py`, add `recompute_current_gate_fingerprint(db, user_id, today, target_race_event) -> dict[str,str]` that builds **layer1 → 2A → 2B → 2D → 2C** (the prefix of `_upstream_full_cone`, lines ~995–1113, all `q_*` deterministic — **no 3A/3B**) and returns `compute_gate_fingerprint(...)`. Cleanest implementation: **extract the pre-3A prefix of `_upstream_full_cone` into a shared `_cheap_upstream_prefix(...)` helper** that both `_upstream_full_cone` (which then continues 3A→3B→2E) and this new fn call — avoids a drift-prone duplicate of the framework_sport/discipline-filter/locale setup. (Verify 2B is a `q_*` query, not LLM, before relying on the prefix being cheap.)

### 4.2 On-view cheap check — `plan_review` GET (`routes/plan_create.py` ~1509)
- After `load_hitl_gate`, compute `current_fp = recompute_current_gate_fingerprint(...)` and compare to `gate.evaluated_against`. On mismatch: trigger the async recompute (4.3) + render the "re-evaluating" state. Pass a `stale: bool` to the template.

### 4.3 Async recompute (Andy decision #1)
- Mirror plan-gen's off-thread model: a detected-stale gate (or a revise edit-save) flips the row to a recomputing state, a background pass runs the full cone + `evaluate_layer3d_gate` + `save_hitl_gate`, and the review screen **polls** (like `plan_progress`) until the gate + `generation_status` settle. The gate-level staleness logic (resolution carry by `item_key`, re-block on a new pending blocker) is **already built + unit-tested** — 3b is the route/async trigger around it. Extract a `recompute_layer3d_gate(db, user_id, plan_version_id, *, cone=None)` helper from the create-path hook (cone build + evaluate + save; optional pre-built `cone=` so the create path pays no extra cost), per the #873 handoff §3.4.

### 4.4 `[Fix this]` revise links (`templates/plan_create/review.html` + `routes/plan_create.py`)
- Today the revise affordance is a plain-text stub (`Fix via: {{ it.revise_target }}`). Make it a link. Build a `revise_target → url` map in `plan_review` and pass it to the template. **Confirmed routes:**
  - `profile.injuries` → `routes/injuries.py` (`/injuries`, the list/edit surface).
  - `profile.disciplines` / `profile.nutrition` / `profile.availability` → `routes/locales.py:edit_profile(locale)` — **needs the athlete's primary locale** (read it; the cone exposes `primary_locale`).
  - `h2.goal_outcome` / `h2.event_date` / other `h2.*` (these come from the 3B payload at runtime, not literals in `gate.py`) → `routes/race_events.py` `/<race_event_id>/edit` (`race_event_edit`, line ~804) — **needs the plan's target `race_event_id`**.
- The parked **#874** commit `5b4de06` already has a working `[Fix this]` form + `resolve_review_item` revise branch + a `_REVISE_TARGET_ENDPOINTS` map — cherry-pick/adapt rather than rewrite (`git show 5b4de06 -- templates/plan_create/review.html routes/plan_create.py`).

---

## 5. Next session

### 5.1 Start here
Build **Slice 3b** per §4. Re-verify the §4 line refs against `main` first (Rule #9), and confirm 2B is a deterministic query (so the partial-cone prefix is genuinely LLM-free). Test locally with the **container gotcha** in mind (§6): the wiring test can't run here (Neon hang at app import); run the pure `tests/test_layer3d_gate.py` with `dangerouslyDisableSandbox` + `timeout`, and add new wiring tests for the on-view check that **patch** `recompute_current_gate_fingerprint` (don't build a real cone).

### 5.2 Operating notes — session-start read order (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — top entry is this session
3. `CARRY_FORWARD.md` — the Layer-3 Slice-3 bullet + the new test-run gotcha
4. **This handoff**
5. `./scripts/verify-handoff.sh` — anchor sweep
Then `git fetch origin main` + check #213 for any new in-flight 3b work (the parallel-build collision lesson).

---

## 6. Container gotcha (also in CARRY_FORWARD)
- `tests/test_layer3d_wiring.py` imports `routes.plan_create` → the Flask app → a Neon connect at import → **hangs** in the container (Neon egress blocked). It runs only in CI ("Python unit suite (stubbed)"). It is **unaffected** by 3a (it monkeypatches `orchestrate_plan_create`, so the cone/hook changes are never exercised).
- The harness **sandbox terminates** any pytest run that touches the network mid-collection (silent: 0-byte output, exit 1, the `>file` redirect never lands). Run pure unit files with `dangerouslyDisableSandbox: true` + a `timeout`; front-load a `tests/test_layer4_*.py` to dodge the isolated-single-file circular-import quirk.

---

## 7. Rule #9 verification table (input to next session's anchor sweep)

| File | Anchor / check | Expect |
|---|---|---|
| `aidstation-sources/specs/Layer3D_Spec.md` | grep `6.1.1` + `3B_inputs` | ✅ new fingerprint contract; 2E NOT in the §6.1.1 table |
| `layer3d/gate.py` | grep `def compute_gate_fingerprint` + `evaluated_against: dict` | ✅ helper + param |
| `layer4/orchestrator.py` | grep `gate_fingerprint` | ✅ cone field + compose + `evaluated_against=cone.gate_fingerprint` at the hook |
| `tests/test_layer3d_gate.py` | grep `def _fingerprint` | ✅ +8 tests; 42 pass (`dangerouslyDisableSandbox` + `timeout`) |
| `aidstation-sources/CURRENT_STATE.md` | top entry grep `SLICE 3a BUILT` | ✅ new top; #256/#592 demoted to predecessor |
| PR #874 | state | closed (not merged); superseded by #873 design |

---

## 8. Issue reconcile
- **#213** — Slice 3a built (fingerprint contract); commented with the PR + the 3b scope (on-view check + async + `[Fix this]`). Stays **open** as the 3b tracker.
- **#874** — closed (not merged); superseded by the #873-ratified design; reusable `[Fix this]` bits preserved at `5b4de06`.
- **#211** epic, **#844** (3C) — untouched.

---

## 9. POST-MERGE CONSOLIDATION — #880 collision → consolidate on Reading-B (authoritative)

After #881 merged, `git log origin/main` showed a parallel #213 merge immediately prior — **#880** (`claude/serene-newton-igye62`, `5959ed7`, "Reading-B staleness fingerprint for parked plans"), merged ~minutes before #881. It solved the **same** #213 staleness re-fire a different (and better) way. The two auto-merged with no textual conflict but were **never CI'd together**.

**The two readings.**
- **#881 "Reading-A" (this handoff §2–§3, now REVERTED):** `evaluated_against` = hashes of the *computed* 2A/2C/2D payloads (`compute_gate_fingerprint`). Detecting staleness this way needs the query layers rebuilt (a partial cone); 2E/3B can't be hashed cheaply.
- **#880 "Reading-B" (KEPT):** `Layer3DGate.input_fingerprint` = one SHA-256 over the **raw leaf inputs** (`layer4.orchestrator.compute_gate_input_fingerprint`: profile / race / equipment+terrain / training-bundle / event-windows / etl / prompt-rev / start-date — all cheap indexed reads, **no LLM, no cone**). Stamped on the gate when the orchestrator parks it non-green. **Plus the on-view consumer** in `routes/plan_create.py`: `_gate_inputs_changed` (recompute + compare, fail-safe) gates `plan_review` (re-entry → re-kick), `resolve_review_item` (acknowledge → bounce), `generate_from_review` (generate → re-kick regardless of stored verdict); `_rekick_stale_gate` flips the row to `generating` (idempotent) so the resumable poller re-evaluates — the async recompute (the progress screen polls). Tests: `tests/test_gate_input_fingerprint.py` + `tests/test_layer3d_wiring.py` (+111).

**Andy's call: consolidate on #880's Reading-B** — cheaper (no cone rebuild) and it already ships the consumer #881 had deferred. The cleanup PR:
1. **Reverts #881's Reading-A code** — removed `compute_gate_fingerprint` (gate.py); the `evaluated_against` param + the cone `gate_fingerprint` field + the hook `evaluated_against=` arg + the fp log (orchestrator); the 8 fingerprint tests (test_layer3d_gate.py). `evaluate_layer3d_gate` returns `evaluated_against=etl_version_set` again — the etl-provenance stamp #880's design relies on (#880 keeps `evaluated_against` = etl, staleness in the separate `input_fingerprint`).
2. **Rewrites `Layer3D_Spec` §6.1 table + §6.1.1 + §11.2 + §8 + TS-3D-16** to document the shipped Reading-B (#880 shipped no spec; #881's spec had described Reading-A).
3. Leaves all of #880 untouched.

**Verification:** combined main was green pre-cleanup (CI #783/#784 success); post-cleanup the gate + #880 suites pass locally (**128**, via `dangerouslyDisableSandbox` + `timeout`). #880's consumer reviewed end-to-end — covers re-entry / acknowledge / generate, fail-safe (probe error → treat as fresh, never 500s), idempotent re-kick.

**Still owed for #213 staleness:**
- **`[Fix this]` revise links** — `templates/plan_create/review.html` is still the plain-text `Fix via: {{ it.revise_target }}` stub. Turn it into a link per `revise_target`: `profile.injuries`→`routes/injuries.py` (`/injuries`); `profile.disciplines`/`profile.nutrition`/`profile.availability`→`routes/locales.py:edit_profile(locale)` (needs the athlete's primary locale — the cone exposes `primary_locale`); `h2.*` (3B items, e.g. `h2.goal_outcome`/`h2.event_date`)→`routes/race_events.py` `/<race_event_id>/edit` (needs the plan's target `race_event_id`). The parked **#874** commit `5b4de06` has a reusable `[Fix this]` form + `resolve_review_item` revise branch + `_REVISE_TARGET_ENDPOINTS` — `git show 5b4de06 -- templates/plan_create/review.html routes/plan_create.py`.
- **Live-verify (Andy-action — container can't run plan-gen):** park a plan at `needs_review`, edit a profile/race field, re-enter the review screen → it re-kicks (progress screen) and re-evaluates against the edit; `/admin/logs` shows the re-kick.

**Lesson (reinforced):** the collision was invisible until `git log origin/main` *after* the merge. Check the epic for in-flight parallel work both at session start **and immediately before opening a PR** — webhooks/CI don't surface a sibling branch racing the same issue.
