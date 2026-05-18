# V5 Implementation — Layer 4 Step 6 Pattern A Orchestration Polish Closing Handoff

**Session:** Single chat. Scope: Layer 4 Step 6 — Pattern A orchestration polish per `Layer4_Spec.md` §14.3.4 sequencing. Three sub-pieces in one PR: 6a per-phase cache wiring per §9.2 + 6b ThreadPoolExecutor concurrency for non-overlapping iter-1 seam reviews per §5.2 closing note + 6c per-call telemetry module per §9.6 + §14.3.5. No spec amendments (Trigger #5/#11 did not fire). No paired prompt body amendments (Trigger #2 did not fire — orchestrator-side polish has no LLM coupling).

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_Layer4_Step5_Cache_Closing_Handoff_v1.md` (Step 5 shipped 2026-05-18 earlier same day; commit `c5d8e25` on origin/main via PR #80).

**Branch:** `claude/implement-cache-closing-Ng3Bl` (harness-pinned for this session — name carried over from the harness even though this session is Step 6 Pattern A polish; precedent: harness names mismatched with scope across every prior Layer 4 implementation session).

**Status:** 🟢 1 new code module + 3 modified code modules + 1 modified `__init__` + 2 modified tests + 1 new test = 8 substantive + 3 bookkeeping = 11 files. Combined `tests/` 621 → 662 net new in 0.86s. **Layer 4 implementation Step 6 of 8 COMPLETE.**

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| Step 5 shipped on `main` per Step 5 handoff | `git log --oneline -10` | ✅ commits `ba6c018` (merge PR #80) + `c5d8e25` |
| `layer4/cache.py` (~360 lines) + `cache_postgres.py` + `cache_invalidation.py` + `cached_wrappers.py` exist | `ls layer4/` + `wc -l` | ✅ all four modules present (506/224/150/500 lines) |
| `compute_accepted_output_hash` + `compute_phase_cache_key` in `layer4/hashing.py` | grep | ✅ both helpers in place |
| Combined `tests/` 621 green | `python -m pytest tests/ -q` | ✅ 621 passed in 0.80s |
| Working tree clean on `claude/implement-cache-closing-Ng3Bl` | `git status` | ✅ |
| `Project_Backlog_v51.md` exists; CLAUDE.md backlog ref reads `Project_Backlog_v51.md` | `ls` + grep | ✅ |

**No drift found.** Step 5 narrative matches on-disk state exactly.

---

## 2. Session narrative — Step 6 Pattern A orchestration polish (Andy 2026-05-18)

Andy opened with the URL to the Step 5 closing handoff + "lets work." I followed the operating model — read CLAUDE.md fully (Rule #13), ran Rule #9 verification, surfaced state, and offered the architect-recommended next-forward-move set from the Step 5 handoff §4.1.

### 2.1 Scope pick

**Round 1 (2026-05-18, 1-question):** session scope. Andy picked **Step 6 full polish (6a + 6b + 6c)** — closes Step 6 of 8 in one PR; precedented ceiling break.

### 2.2 Architectural choices — 4-question AskUserQuestion gate

During the load-bearing re-read (Rule #13: CLAUDE.md fully via system context + Step 5 handoff + `Layer4_Spec.md` §5.2 + §9.2 + §9.6 + §10.6 + §14.3.4/§14.3.5 + the already-shipped `layer4/cache.py` + `cached_wrappers.py` + `plan_create.py` + `hashing.py` per-phase helpers), surfaced 4 architectural decisions:

1. **Concurrency mechanism for non-overlapping seam reviews** (per §5.2 closing note): ThreadPoolExecutor (~80 LOC; ~10s p95 latency win on 4-phase plans) vs asyncio + AsyncAnthropic refactor (~500+ LOC ripple) vs skip 6b (defer the optimization). **Andy picked ThreadPoolExecutor** after a plain-English explanation of the tradeoffs.
2. **Telemetry shape / module layout** (per §9.6 + §14.3.5): new `layer4/telemetry.py` + `CallMetrics` dataclass vs extending `CacheMetrics` with retry/verdict counters vs inline-only Layer4Payload fields. **Andy picked new `layer4/telemetry.py` + CallMetrics dataclass** — distinct concern from cache observability per spec §9.6 framing.
3. **T3 cross-phase per-phase cache wiring scope**: thread cache through both `llm_layer4_plan_create_cached` AND `llm_layer4_plan_refresh_cached` vs plan_create-only. **Andy picked both entry points** — same `_run_pattern_a_engine` benefits both; clean symmetry.
4. **File ceiling break**: 8 substantive + 3 bookkeeping = 11 files projected. **Andy picked break** — precedented across Step 5 11 + Step 4f 13 + Step 4d 13 + Step 4b/c 10 + Step 4e 10.

### 2.3 Implementation order

1. NEW `layer4/telemetry.py` (~280 lines) — `CallMetrics` frozen dataclass + `MODEL_PRICING_USD_PER_M` table + `TelemetryAggregator` running aggregator.
2. Modified `layer4/plan_create.py`:
   - Imports: `concurrent.futures.{Executor, ThreadPoolExecutor}`, `layer4.cache.Layer4Cache`, `layer4.hashing.{compute_accepted_output_hash, compute_phase_cache_key}`, `layer4.payload.SynthesisMetadata`, `layer4.seam_review.SeamReviewCallResult`.
   - New helpers `_serialize_phase_result_with_meta` + `_hydrate_phase_result_with_meta` per §9.2 storage shape.
   - `_build_phase_structure_with_metadata` refactored to consume `synthesis_metadata_by_index: dict[int, SynthesisMetadata]`.
   - `_run_pattern_a_engine` gains `cache: Layer4Cache | None = None`, `call_cache_key: str | None = None`, `executor: Executor | None = None` kwargs. Per-phase loop wraps `synthesize_phase()` in a synthesizer closure + uses `cache.get_phase_or_synthesize()` when cache + key both provided. Tracks `synthesis_metadata_by_index` + `prev_accepted_output_hash` running variable for the §9.2 chain. Seam-review loop refactored: pairs-to-review identified first, iter-1 LLM calls fire in parallel via `ThreadPoolExecutor` (or caller-injected `Executor`), iter-2 + re-synth processed sequentially per seam_idx. Re-synth updates `synthesis_metadata_by_index[target_idx]` so the final PhaseStructure reflects the re-synth metadata.
   - `llm_layer4_plan_create` + `synthesize_pattern_a_for_refresh` entry points gain matching `cache` + `call_cache_key` + `executor` kwargs; thread through to `_run_pattern_a_engine`.
3. Modified `layer4/cached_wrappers.py` — `llm_layer4_plan_create_cached` + `llm_layer4_plan_refresh_cached` synthesizer closures pass `cache=cache, call_cache_key=key, executor=executor` into the underlying entry points. Both wrappers gain an `executor: Executor | None = None` top-level kwarg.
4. Modified `layer4/plan_refresh.py` — `llm_layer4_plan_refresh` entry point gains `cache` + `call_cache_key` + `executor` kwargs; `_route_t3_cross_phase_to_pattern_a` delegate forwards them through to `synthesize_pattern_a_for_refresh`.
5. Modified `layer4/__init__.py` — 3 new telemetry re-exports (`CallMetrics`, `MODEL_PRICING_USD_PER_M`, `TelemetryAggregator`).
6. NEW `tests/test_layer4_telemetry.py` (~520 lines, 26 tests).
7. Modified `tests/test_layer4_plan_create.py` — 14 new tests across 3 classes.
8. Modified `tests/test_layer4_plan_refresh.py` — 1 new T3 cross-phase cache threading test.
9. Bookkeeping: `Project_Backlog_v51.md` → `v52.md` + CLAUDE.md update + this handoff.

### 2.4 Architectural choices on the record

- **Per-phase cached shape** stores `(sessions, synthesis_metadata, phase_synthesis_notes, opportunities, validator_results, cap_hit, retries_used)`. Token / latency / llm_call_count are NOT cached because cache hits should stamp ZERO on `Layer4Payload.latency_ms_total` per §9.6 ("synthesis-only" framing). The cached `synthesis_metadata` retains the ORIGINAL token counts for §9.2 chain-hashing fidelity (downstream phase keys depend on the canonical accepted-output hash which mixes sessions + synthesis_metadata).
- **`synthesis_metadata_by_index: dict[int, SynthesisMetadata]`** tracked separately from `results_by_index` because cache hits return zeroed `PhaseSynthesisResult` but the final PhaseStructure must carry the canonical metadata (original token counts when from cache; live counts when from miss). Refresh on seam-driven re-synth: `synthesis_metadata_by_index[target_idx] = build_synthesis_metadata_from_result(re_result, …)` so the re-synth's metadata wins.
- **Seam-review iter-1 parallelization semantics** — per §5.2 closing note: "Seam reviews COULD parallelize across non-overlapping pairs (with N synthesized phases, seams 0..N-2 are independent in their LLM-call inputs)." Iter-1 runs all in parallel against the INITIAL synthesized phase outputs. Iter-2 + phase re-synth stay sequential per seam_idx order — per-phase retry budget consumption + chained context dependencies are load-bearing. **Tradeoff documented inline**: when seam i iter-1 triggers re-synth of phase i+1, seam (i+1)'s iter-1 — already fired in parallel against the ORIGINAL phase i+1 — does not re-fire; the §5.2 step-5 final cross-phase validator pass + seam (i+1)'s iter-2 (if its iter-1 ALSO flagged) catch downstream issues.
- **ThreadPoolExecutor only kicks in for ≥2 seams** — single-seam plans (Peak→Taper edge case) skip the pool overhead and run the one iter-1 task directly. Caller-injected `Executor` is used unconditionally when provided (tests inject a sequential `_RecordingExecutor` for deterministic call ordering).
- **Seam-driven re-synthesis intentionally NOT cache-wired in v1** — matches `Layer4_Spec.md` §10.6 row 3 expected behavior ("seam review re-prompts phase 0 → new `phase_key[0]` computed with seam-issue-merged context; cache miss"). The §9.2 formula doesn't expose how to chain seam_issues into a new phase_key; the spec gap is acknowledged as a §6.3 carry-forward. v1 runs re-synth uncached and accepts the chain break — downstream phases miss on the new chain hash. Cache helps only first pass per spec's own framing.
- **`Layer4Cache` is the new positional/keyword type threaded** through `_run_pattern_a_engine` even though plan_create.py is downstream of cache.py in the import graph. No circular import since `cache.py` doesn't import `plan_create.py` (the cached wrapper handles all bidirectional plumbing).
- **`CallMetrics` retries inference for Pattern B** uses a heuristic: when `best_effort_emitted` (any `best_effort_plan` observation) AND the last validator result is accepted with NON-EMPTY rule_failures all at severity 'warning', back out the synthesized-on-top accepted pass per §5.5 best-effort semantics. This handles the canonical Pattern B cap-hit shape (real failing passes + synthesized accepted pass with demoted blockers).
- **Cost estimate uses `model_synthesizer` pricing for ALL tokens** — Layer4Payload doesn't expose a synth-vs-seam token breakdown. Seam-reviewer tokens are a small fraction in practice (per spec §11.2/§11.3); per-call split is v2 once measured costs justify the breakdown. Unknown models graceful-zero rather than raise — telemetry should degrade quietly when a new model lands before the pricing table updates.
- **Latency percentile** uses nearest-rank (no linear interpolation in v1) — small N makes the distinction irrelevant for orchestrator dashboards. Out-of-[0, 100] ranges raise loudly.
- **Cached wrapper does NOT change the entry-point cache semantics** — the per-entry cache (top-level `get_or_synthesize`) wraps the FULL synthesis call including all per-phase work. On a per-entry hit, the synthesizer closure is never invoked, so `_run_pattern_a_engine` doesn't fire and per-phase caches aren't consulted. On a per-entry miss, the closure invokes the entry point with `cache=cache, call_cache_key=key` so the per-phase chain rolls.

### 2.5 Stop-and-ask triggers — #8 fired × 4; #5, #11 + #2 did NOT fire

- **Trigger #8 (architectural alternatives):** fired and routed × 4 — concurrency mechanism + telemetry layout + T3 wiring scope + file ceiling.
- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire. No `Layer4_Spec.md` amendments needed — §5.2 closing-note framing remains authoritative; §9.2 contract for the per-entry-cache-driven chain is clear; §9.6 observability framing is followed; seam-driven re-synth caching gap is acknowledged as a v2 amendment candidate, not a v1 change.
- **Trigger #2 (prompt body amendments):** did NOT fire — Step 6 is purely orchestrator-side polish with no LLM-coupling change.
- **Trigger #11 (new D-rows):** did NOT fire — no new cross-layer dependencies.

---

## 3. No paired amendments this session

Step 6 consumes the existing v1 §9.2 + §5.2 + §9.6 + §14.3.5 spec contracts without surfacing any contract gap that demands a v1 amendment. **No `Layer4_Spec.md` amendments. No prompt body v2 bumps.** The §9.2 seam-driven-resynth-chain spec gap is acknowledged in §5.2 below as a §6.3 carry-forward.

---

## 4. Next session pointers

### 4.1 Architect-recommended next forward moves

**Layer 4 Step 6 Pattern A orchestration polish COMPLETE.** §14.3.4 Steps 1-6 of 8 closed. Architect-recommended next:

1. **Step 7 live LLM integration** — first end-to-end against real Anthropic API for `single_session_synthesize` (~$0.075/call worst-case per `Layer4_Spec.md` §11.3). The cache layer (Step 5) + telemetry (Step 6c) now make this safe to iterate on:
   - Per-entry cache prevents repeat-billing on identical inputs (~$0.05-0.75/call savings per invalidation cycle)
   - `CallMetrics.cost_usd_estimate` + `TelemetryAggregator.total_cost_usd` give running cost visibility
   - `verdict_histogram` + `cap_hit_rate` + `seam_unresolved_count` surface verdict quality without manual log-reading
   - `single_session_synthesize` is the cheapest entry point to validate (no per-phase + no seam reviewer); good first integration
   - Successful Step 7 unblocks Step 8 telemetry tuning + production rollout track
2. **Step 8 telemetry tuning** — once Step 7 lands real measured retry rates + verdict distributions + cost data, calibrate the §5.4 validator tolerance thresholds (±20%/±10% volume bands; ±10pp intensity distribution; 28-day ACWR window) + `capped_retries_per_phase` (currently 2) + the v1 baseline sentinels in `_rule_injury_accommodation_violation` (currently hardcoded 40 reps / 60 min / 80%1RM / 3 sessions/week). All v1 defaults flagged as "tune post-launch" in spec §5.4 closing paragraph.
3. **v5 onboarding implementation PR** — substantial UI + DB work per `Athlete_Onboarding_Data_Spec_v5.md` (D-58/59/60/61 onboarding flow + `/profile?tab=race-events` tab per D-66). Independent of Layer 4; can run in parallel with Step 7.
4. **D-50 wiring resumption** — independent track; unblocked by D-58; can run in parallel with all of the above.

### 4.2 Carry-forward — Seam-driven re-synthesis cache-key formula (§9.2 gap)

Per `Layer4_Spec.md` §10.6 row 3, when a seam review triggers re-synthesis of an adjacent phase, the spec describes the behavior as "New `phase_key[0]` computed with seam-issue-merged context; cache miss; fresh phase 0 synthesis; phase 0's new `accepted_output_hash` differs". But the §9.2 formula

```
phase_key[i] = sha256(
    call_cache_key ||
    phases[i].phase_name ||
    str(i) ||
    (phases[i-1].accepted_output_hash if i > 0 else '')
)
```

does NOT include seam_issues in the chain key. The v1 implementation accepts this gap: seam-driven re-synth runs uncached (the engine doesn't wrap `synthesize_phase` in the cache for the iter-2 re-synth path), and downstream phases — which now have a different `prev_accepted_output_hash` because the re-synth's output differs from the cached initial-synthesis output — would naturally miss on the new chain hash if re-checked. But the v1 engine doesn't re-check downstream phases after seam-driven re-synth (the per-phase loop completes before the seam loop fires). So the cache simply doesn't help on the seam-resynth path.

**Two possible v2 paths:**

1. **Spec amendment to §9.2** — extend the formula to include a `seam_issues_hash` component (sha256 of canonical-JSON of the seam_issues list merged into the phase's context), and recompute phase_key when seam_issues is non-empty. Implementation would re-wrap the seam-driven `synthesize_phase` call in cache.get_phase_or_synthesize using the seam-issue-aware key. Tradeoff: more cache rows; rare collisions across calls (seam_issues lists tend to be call-specific).

2. **Accept v1 behavior + document loudly** — Keep the chain break on seam-driven re-synth as the documented behavior. Update §10.6 row 3 to read "phase_key chain is intentionally cache-bypassing on seam-driven re-synth in v1; cache helps only the initial per-phase loop." Match implementation to spec.

Path 2 is the simpler v1 framing. Path 1 is a v2 candidate once measured seam-driven re-synth rates justify the additional cache complexity.

### 4.3 Carry-forward — Anthropic SDK `seed` parameter

Per `Layer4_Spec.md` §9.4 forward-pointer: "When the Anthropic API exposes a `seed` parameter for hard determinism, add it to every entry-point cache key (next to `temperature`) and forward to the API call. v1 does not use `seed`." When this lands (Anthropic v2026.x?), `seed` gets threaded into every `*_key()` helper in `hashing.py` and every entry-point call site. Trivial mechanical update.

### 4.4 Carry-forward — Per-call synth-vs-seam token breakdown

Layer4Payload currently exposes `input_tokens_total` + `output_tokens_total` + `llm_call_count` at the call level. For sharper cost estimates (especially on Pattern A where the seam reviewer is a different model than the synthesizer with different pricing), expose `input_tokens_synthesizer` / `output_tokens_synthesizer` / `input_tokens_seam_reviewer` / `output_tokens_seam_reviewer`. Then `CallMetrics.from_layer4_payload` can blend by model pricing accurately. v2 candidate.

### 4.5 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff.
3. **Third re-read**: depends on scope. If Step 7 → `Layer4_Spec.md` §13 test scenarios + each prompt body's §12 PSS-prefix scenarios + the `single_session_synthesize` driver + Anthropic SDK docs for `messages.create(thinking=…)`. If Step 8 → §5.4 validator + §5.5 retry semantics + the v1 default callouts in §5.4 closing paragraph.
4. **Branch**: cut fresh off post-merge `main` OR stay on the harness pin (precedent).
5. **Live LLM testing**: needs `ANTHROPIC_API_KEY` env var; use `single_session_synthesize` first per §11.3 cost ordering. Use the cache layer + telemetry from the start (set up `Layer4Cache(PostgresCacheBackend(…))` + `TelemetryAggregator` in the test harness).

---

## 5. Open items / decisions pinned this session

### 5.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Step 6 full polish (6a + 6b + 6c) | Andy 2026-05-18 | Closes Step 6 of 8 in one PR; precedented ceiling break |
| 2 | Concurrency = ThreadPoolExecutor on iter-1 | Andy 2026-05-18 | ~10s p95 latency win on 4-phase plans; ~80 LOC; easy to test (inject sequential Executor); iter-2 stays sequential for budget + chain integrity |
| 3 | Telemetry = new `layer4/telemetry.py` + CallMetrics dataclass | Andy 2026-05-18 | Distinct concern from CacheMetrics per §9.6 framing; future-proofs Step 8 tuning |
| 4 | T3 wiring = thread cache through both entry points | Andy 2026-05-18 | Same `_run_pattern_a_engine` benefits both; clean symmetry; marginal extra LOC |
| 5 | File ceiling break (11 files) | Andy 2026-05-18 | Precedented across every prior Layer 4 implementation session |
| 6 | Per-phase cached shape preserves original metadata token counts | Architect-pick | §9.2 chain-hashing requires canonical synthesis_metadata; hits stamp zero on PhaseSynthesisResult but cached metadata wins for chain fidelity |
| 7 | Seam-driven re-synth NOT cache-wired in v1 | Architect-pick | Matches §10.6 row 3 expected behavior; §9.2 formula gap acknowledged; v2 candidate |
| 8 | ThreadPoolExecutor kicks in only for ≥2 seams | Architect-pick | Single seam = no pool overhead; caller-injected Executor unconditional |
| 9 | Cost estimate uses synthesizer pricing for ALL tokens | Architect-pick | Layer4Payload lacks synth-vs-seam token split; per-call breakdown is v2 |
| 10 | Unknown model = cost_usd_estimate of 0.0 (graceful-zero) | Architect-pick | Telemetry degrades quietly when new models land before pricing table updates |
| 11 | Pattern B retries heuristic backs out cap-hit synthesized pass | Architect-pick | Heuristic: best_effort_emitted + last-pass-accepted-with-non-empty-all-warning failures → subtract 1 from retries_used_total |

### 5.2 Carry-forward — Seam-driven re-synth cache-key (§9.2 gap)

See §4.2 above. v1 accepts the chain break per §10.6 row 3; v2 candidate spec amendment.

### 5.3 Carried forward — Layer 1 typed payload

Still deferred. `Layer1Payload` is `dict[str, Any]` opaque pass-through across all entry points.

### 5.4 Carried forward — Anthropic SDK `seed` per §9.4

See §4.3 above. Awaits Anthropic API support.

---

## 6. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `layer4/telemetry.py` exists (~280 lines) | ✅ inspection |
| `layer4/plan_create.py` modified — new imports (Executor, ThreadPoolExecutor, Layer4Cache, hashing helpers, SynthesisMetadata, SeamReviewCallResult); new serialize/hydrate helpers; `_run_pattern_a_engine` gains cache+key+executor kwargs; entry points gain matching kwargs | ✅ inspection |
| `layer4/cached_wrappers.py` modified — `Executor` import; plan_create_cached + plan_refresh_cached thread cache+key+executor into synthesizer closures | ✅ inspection |
| `layer4/plan_refresh.py` modified — entry point + `_route_t3_cross_phase_to_pattern_a` forward cache+key+executor | ✅ inspection |
| `layer4/__init__.py` re-exports CallMetrics + MODEL_PRICING_USD_PER_M + TelemetryAggregator | ✅ grep |
| `tests/test_layer4_telemetry.py` exists with 26 tests | ✅ `pytest tests/test_layer4_telemetry.py -q` → 26 passed in 0.20s |
| `tests/test_layer4_plan_create.py` gains 14 tests (TestPerPhaseCacheWiring × 7 + TestSeamReviewConcurrency × 5 + TestCachedWrapperThreadsCacheAndExecutor × 2) | ✅ inspection |
| `tests/test_layer4_plan_refresh.py` gains 1 T3 cross-phase cache threading test | ✅ inspection |
| Combined `tests/` 662 green | ✅ `pytest tests/ -q` → 662 passed in 0.86s |
| `Project_Backlog_v52.md` exists; file-revision-header bumped to v52 | ✅ ls + grep |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v52.md` | ✅ grep |
| `CLAUDE.md` Last-shipped-session is Step 6; Step 5 demoted to predecessor | ✅ inspection |
| Branch is `claude/implement-cache-closing-Ng3Bl` (harness-pinned) | ✅ |

---

## 7. Files shipped this session

One commit (or multiple bundled) on `claude/implement-cache-closing-Ng3Bl`:

**Substantive code + tests (8 files):**
1. New `layer4/telemetry.py` (~280 lines — `CallMetrics` + `TelemetryAggregator` + `MODEL_PRICING_USD_PER_M`)
2. Modified `layer4/plan_create.py` (per-phase cache wiring + ThreadPoolExecutor iter-1 + serialize/hydrate helpers + signature updates)
3. Modified `layer4/cached_wrappers.py` (thread cache+key+executor through plan_create + plan_refresh wrappers)
4. Modified `layer4/plan_refresh.py` (entry point + T3 cross-phase delegate thread cache+key+executor)
5. Modified `layer4/__init__.py` (3 new telemetry re-exports)
6. Modified `tests/test_layer4_plan_create.py` (14 new tests across 3 classes)
7. Modified `tests/test_layer4_plan_refresh.py` (1 new T3 cross-phase cache test)
8. New `tests/test_layer4_telemetry.py` (~520 lines, 26 tests)

**Bookkeeping (3 files):**
9. New `aidstation-sources/Project_Backlog_v52.md` (per Rule #12; v51 retained as predecessor)
10. Modified `aidstation-sources/CLAUDE.md`
11. New `aidstation-sources/handoffs/V5_Implementation_Layer4_Step6_PatternAPolish_Closing_Handoff_v1.md` (this file)

**11 files total. Over the 5-file ceiling intentionally** — Andy confirmed at session start via AskUserQuestion question #4; precedented across Step 5 11 + Step 4f 13 + Step 4d 13 + Step 4b/c 10 + Step 4e 10.

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- v5 onboarding implementation PR — consumes §H.2 + §H.4 + §A.1 extensions per D-66 design wave; independent of Layer 4 implementation track.
- Migration script per `Race_Events_D66_Design_v1.md` §10 — deferred to v5 onboarding implementation PR.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **Step 7 live LLM integration** — architect-recommended next forward move per §14.3.4 sequencing.
- **Seam-driven re-synth cache-key formula per §9.2** — concrete carry-forward per §4.2 above.
- **Anthropic SDK `seed` parameter per §9.4** — v2 forward-pointer; awaits API support.

---

**End of handoff.**
