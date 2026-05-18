# V5 Implementation — Layer 4 Step 5 Cache Layer Closing Handoff

**Session:** Single chat. Scope: Layer 4 Step 5 — orchestrator-side cache layer per `Layer4_Spec.md` §9 (per-entry caches §9.1 + per-phase chain helpers §9.2 + invalidation matrix §9.3 + per-call rebinding §9.4 + observability §9.6). No paired prompt body amendments (no Trigger #2 substantive). No paired spec amendments (no Trigger #5 substantive — §9 contract was already clear).

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_Layer4_Step4f_PlanCreate_Closing_Handoff_v1.md` (Step 4f shipped 2026-05-18 earlier same day; commit `c5e0ea9` on origin/main via PR #79).

**Branch:** `claude/implement-layer4-step4f-vkltG` (harness-pinned for this session — name carried over from the harness even though this session is Step 5 cache layer; precedent: harness names mismatched with scope across every prior Layer 4 implementation session).

**Status:** 🟢 4 new code modules + 1 modified DDL + 1 modified hashing helpers + 1 modified `__init__` + 1 new test + 3 bookkeeping = 11 files. Combined `tests/` 547 → 621 net new in 0.71s. **Layer 4 implementation Step 5 of 8 COMPLETE.**

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| Step 4f shipped on `main` per Step 4f handoff | `git log --oneline -10` | ✅ commits `e7086e5` (merge PR #79) + `c5e0ea9` |
| `layer4/plan_create.py` exists (~800 lines) | `ls` | ✅ |
| `layer4/per_phase.py` + `layer4/seam_review.py` exist | `ls` | ✅ |
| `tests/test_layer4_plan_create.py` exists with 46 tests | `pytest --collect-only` | ✅ |
| Combined `tests/` 547 green | `python -m pytest tests/ -q` | ✅ 547 passed in 0.92s |
| `tier_t3_cross_phase_requires_pattern_a` raise replaced with delegate | grep | ✅ — Step 4f closed it |
| Working tree clean on `claude/implement-layer4-step4f-vkltG` | `git status` | ✅ |
| `Project_Backlog_v50.md` exists | `ls` | ✅ |

**No drift found.** Step 4f narrative matches on-disk state exactly.

---

## 2. Session narrative — Step 5 cache layer (Andy 2026-05-18)

Andy opened with the URL to the Step 4f closing handoff + "let's work." I followed the operating model — read CLAUDE.md fully (Rule #13), ran Rule #9 verification, surfaced state, and offered the architect-recommended next-forward-move set from the Step 4f handoff §4.1.

### 2.1 Scope pick

**Round 1 (2026-05-18, 1-question):** session scope. Andy picked **Step 5 cache layer** (architect-recommended next forward move per the Step 4f handoff §4.1 — Layer 4 Step 4 sub-arc was complete and Step 5 is the natural next step in §14.3.4 sequencing).

### 2.2 Architectural choices — 4-question AskUserQuestion gate

During the load-bearing re-read (Rule #13: CLAUDE.md fully via system context + Step 4f handoff + `Layer4_Spec.md` §9 + §7.11 plan_versions DDL + §14.3.4 sequencing + the already-shipped `layer4/hashing.py` cache-key helpers + `database.py` PG conn shape), surfaced 4 architectural decisions:

1. **Step 5 scope**: full Step 5 in one PR (per-entry + rebinding + invalidation + observability + all 4 entry-point wrappers + per-phase helpers; ~8-10 files) vs split per-entry-first (defer per-phase + invalidation to follow-on; ~5-6 files) vs minimum-viable (cache + single_session only; ~4-5 files). **Andy picked full Step 5** — clean closure of §9 contract.
2. **Cache backend**: Postgres JSONB cache table vs in-memory LRU vs hybrid. **Andy picked Postgres JSONB** — Vercel serverless = in-memory LRU is useless across cold-start invocations; only PG delivers actual cache hits in deployment; ~10-50ms read overhead is acceptable vs ~$0.05-0.75/call LLM cost saved.
3. **Module layout**: split `cache.py` + `cache_invalidation.py` + cached wrappers vs monolithic single file vs **abstract `CacheBackend` interface + `PostgresCacheBackend` impl + split**. **Andy picked abstract + PG impl + split** — future-proofs for Redis later; YAGNI cost acceptable.
4. **File ceiling break**: trim to fit vs **Yes break (11 files projected)**. **Andy picked break** — precedented across Step 4f 13 + Step 4d 13 + Step 4b/c 10 + Step 4e 10.

### 2.3 Implementation order

1. NEW `layer4/cache.py` (~360 lines) — `CacheBackend` abstract base + `CacheEntry` + `CacheMetrics` + `InMemoryCacheBackend` + `Layer4Cache.get_or_synthesize()` + `Layer4Cache.get_phase_or_synthesize()` + `_rebind_payload_dict()`.
2. NEW `layer4/cache_postgres.py` (~190 lines) — `PostgresCacheBackend(CacheBackend)` concrete impl.
3. NEW `layer4/cache_invalidation.py` (~130 lines) — §9.3 invalidation matrix verbatim + `evict_on_layer_change` + `evict_on_midnight_rollover` + `policy_for_layer`.
4. NEW `layer4/cached_wrappers.py` (~470 lines) — `llm_layer4_*_cached()` for all 4 entry points.
5. Modified `init_db.py` `_PG_MIGRATIONS` — `layer4_cache` table DDL.
6. Modified `layer4/hashing.py` — `compute_accepted_output_hash` + `compute_phase_cache_key` per §9.2.
7. Modified `layer4/__init__.py` — 17 new re-exports.
8. NEW `tests/test_layer4_cache.py` — 74 tests.
9. Bookkeeping: CLAUDE.md + Project_Backlog_v50 → v51 + this handoff.

### 2.4 Architectural choices on the record

- **`CacheBackend` abstract base + `InMemoryCacheBackend` (tests + ephemeral) + `PostgresCacheBackend` (production)** — clean substitutability; tests run without a live DB by injecting a fake `_PgConn` factory matching `database._PgConn`'s execute/commit shape.
- **`phase_idx = -1` sentinel for per-entry rows** lets per-entry + per-phase cache rows share one table with a composite primary key `(cache_key, phase_idx)`. CHECK constraint enforces the invariant: per-entry rows have `phase_idx = -1 AND phase_name IS NULL`; per-phase rows have `phase_idx >= 0 AND phase_name IS NOT NULL`.
- **Rebinding via dict-level mutation + pydantic re-validate** — faster than full pydantic round-trip; rebound fields (`plan_version_id` top-level + per-session, `suggestion_id`) don't change validator outcomes. `_rebind_payload_dict()` returns a NEW dict; the cached row is not modified.
- **Per-phase cache helpers shipped + `Layer4Cache.get_phase_or_synthesize()` API exposed BUT wiring into `_run_pattern_a_engine` deferred** per §9.2 own note ("primarily a within-call optimization... across-call per-phase reuse is rare in practice — plan_create typically only re-fires after an upstream invalidation, which changes the call cache key and invalidates the whole chain"). The follow-on PR carry-forward in §4.2 specs the wiring concretely.
- **Cache wrappers as siblings to entry-point functions, not modifications** — entry points stay cache-unaware per spec's "cache wraps at orchestrator boundary" framing. Each `_cached()` wrapper composes the cache + the underlying entry point via a synthesizer closure.
- **Layer hash columns NOT stored per-row** — the cache key already incorporates them via the §9.1 formulas; eviction routing by `entry_point` alone (per the §9.3 matrix) suffices. Storing them separately would be redundant + a sync hazard.
- **Postgres backend uses CTE-wrapped `DELETE ... RETURNING`** to count evictions in a single round-trip: `WITH d AS (DELETE FROM layer4_cache WHERE ... RETURNING 1) SELECT COUNT(*) FROM d`. Avoids the two-statement count-then-delete race.
- **`CacheMetrics` is per-`Layer4Cache` instance** — orchestrator dashboards read `cache.metrics` directly. Per-entry-point breakdowns kept in dicts; per-phase rolls into the same `phase_*` counter set.
- **Cache key TEXT type matches `hashing.py` sha256 hex output** — no driver-side type coercion.

### 2.5 Stop-and-ask triggers — #8 fired × 4; #5 + #11 did NOT fire

- **Trigger #8 (architectural alternatives):** fired and routed × 4 — scope, backend, module layout, file ceiling.
- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire. No `Layer4_Spec.md` amendments needed — §9 contract was clear; the new `layer4_cache` table is implementation-of-spec following PR-B's `plan_versions` migration precedent (DDL is internal storage, not an inter-layer contract).
- **Trigger #2 (prompt body amendments):** did NOT fire — cache layer is orchestrator-side, has no LLM coupling.
- **Trigger #11 (new D-rows):** did NOT fire — no new cross-layer dependencies.

---

## 3. No paired amendments this session

The cache layer consumes the existing v1 §9 spec contract without surfacing any contract gap. **No `Layer4_Spec.md` amendments.** The new `layer4_cache` table is implementation-of-spec following the PR-B precedent.

---

## 4. Next session pointers

### 4.1 Architect-recommended next forward moves

**Layer 4 Step 5 cache layer COMPLETE.** §14.3.4 Steps 1-5 of 8 closed. Architect-recommended next:

1. **Step 6 Pattern A orchestration polish** per `Layer4_Spec.md` §14.3.4. Three sub-pieces:
   - **Per-phase cache wiring carry-forward** (deferred from this session per §4.2 below). ~80-150 LOC + ~6-8 tests; <1 file ceiling.
   - **Concurrency for non-overlapping seam reviews** per §5.2 closing note. Currently sequential; some seams could run in parallel since they depend only on the two adjacent phase outputs, not on prior seams. Worth investigating once the per-phase cache lands so concurrent runs don't double-fetch.
   - **Telemetry on verdict distribution + retry rates + cost/call** per §9.6 + §14.3.5. `CacheMetrics` is the foundation; orchestrator dashboards consume.

2. **Step 7 live LLM integration** — first end-to-end test against real Anthropic API for a single entry point. `single_session_synthesize` is the cheapest to validate (~$0.075/call); the cache layer makes this safe to iterate on without burning budget.

3. **v5 onboarding implementation PR** — substantial UI + DB work per `Athlete_Onboarding_Data_Spec_v5.md` (D-58/59/60/61 onboarding flow + `/profile?tab=race-events` tab per D-66). Independent of Layer 4; can run in parallel.

4. **D-50 wiring resumption** — independent track; unblocked by D-58.

### 4.2 Carry-forward — per-phase cache wiring into `_run_pattern_a_engine`

Per §9.2's own note the across-call utility is rare, but within-call (across retries) it's load-bearing. Mechanically-applicable spec:

**File:** `layer4/plan_create.py:_run_pattern_a_engine`

**Add kwargs to the signature:**
```python
def _run_pattern_a_engine(
    ...,
    cache: Layer4Cache | None = None,
    call_cache_key: str | None = None,
) -> _PatternAEngineResult:
```

**Inside the per-phase loop, before each `synthesize_phase()` call:**
```python
from layer4.hashing import compute_accepted_output_hash, compute_phase_cache_key

prev_accepted_output_hash: str | None = None  # initialize before the loop

# Inside the loop, for each phase_idx in phase_indices_to_synthesize:
if cache is not None and call_cache_key is not None:
    phase_key = compute_phase_cache_key(
        call_cache_key=call_cache_key,
        phase_name=phase_spec.phase_name,
        phase_index=phase_idx,
        prev_accepted_output_hash=prev_accepted_output_hash,
    )

    def _synth_phase() -> dict[str, Any]:
        result = synthesize_phase(...)  # existing call
        return {
            "sessions": [s.model_dump(mode="json") for s in result.sessions],
            "synthesis_metadata": build_synthesis_metadata_from_result(result).model_dump(mode="json"),
            # plus any other fields the engine needs to reconstruct PhaseSynthesisResult
        }

    cached = cache.get_phase_or_synthesize(
        phase_key=phase_key,
        phase_idx=phase_idx,
        phase_name=phase_spec.phase_name,
        user_id=user_id,
        entry_point="plan_create",  # or "plan_refresh" for T3 cross-phase
        synthesizer=_synth_phase,
    )
    # Re-construct PhaseSynthesisResult from cached['sessions'] + cached['synthesis_metadata']
    ...
else:
    # Existing non-cached path.
    result = synthesize_phase(...)
```

**After each phase's accepted output, before moving to the next phase:**
```python
prev_accepted_output_hash = compute_accepted_output_hash(
    result.sessions, build_synthesis_metadata_from_result(result)
)
```

**Threading the cache through the wrappers:**

`llm_layer4_plan_create_cached` already has the `cache` kwarg; pass `call_cache_key=key` (the computed per-entry cache key) into the synthesizer closure so the engine sees both.

**Tests:** add 6-8 tests in `tests/test_layer4_plan_create.py`: per-phase miss-then-store + per-phase chain (phase[i+1] miss when phase[i] output changes; hit when same) + per-phase hit-skips-synthesizer + per-phase metric counter + cache=None retains today's behavior + cross-call utility (rare but should work).

### 4.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff.
3. **Third re-read**: depends on scope. If Step 6 → §5.2 + §9.2 + this §4.2 carry-forward. If Step 7 → §13 test scenarios + each prompt body's §12 PSS-prefix scenarios.
4. **Branch**: cut fresh off post-merge `main` OR stay on the harness pin (precedent).
5. **Test convention**: top-level `tests/test_layer4_<feature>.py`.
6. **Database setup for tests**: tests in this session use `InMemoryCacheBackend` + `_FakeConn` for `PostgresCacheBackend`. Live PG isn't required to run the suite. A future smoke test against Neon would be the first live validation.

---

## 5. Open items / decisions pinned this session

### 5.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Full Step 5 in one PR | Andy 2026-05-18 | Clean §9 contract closure; 11 files precedented |
| 2 | Backend = Postgres JSONB cache table | Andy 2026-05-18 | Vercel serverless requires shared backend; in-memory LRU is empty per cold start |
| 3 | Module layout = Abstract `CacheBackend` + Postgres impl + split cache/invalidation/wrappers | Andy 2026-05-18 | Future-proofs for Redis; YAGNI cost acceptable |
| 4 | File ceiling break (11 files) | Andy 2026-05-18 | Precedented across every Layer 4 implementation session |
| 5 | Per-phase cache wiring deferred to follow-on | Architect-pick (per §9.2 own note) | Spec explicitly flags across-call per-phase reuse as rare; helpers + API shipped; engine integration is a clean follow-on |
| 6 | Layer hash columns NOT stored per-row | Architect-pick | Cache key already incorporates them; eviction routes by entry_point per §9.3 matrix |
| 7 | Postgres backend uses CTE `DELETE ... RETURNING` for eviction counts | Architect-pick | Single round-trip; avoids count-then-delete race |
| 8 | `phase_idx = -1` sentinel for per-entry rows | Architect-pick | Composite PK shared between per-entry + per-phase; CHECK constraint enforces invariant |

### 5.2 Carry-forward — per-phase cache wiring

See §4.2 above for the mechanically-applicable spec. ~80-150 LOC + ~6-8 tests; <1 file ceiling. Lands cleanly in Step 6 polish.

### 5.3 Carried forward — Layer 1 typed payload

Still deferred. `Layer1Payload` is `dict[str, Any]` opaque pass-through across all entry points. The cache layer hashes it via `compute_payload_hash` which handles dicts identically to pydantic models via the canonical_json encoder.

### 5.4 Carried forward — telemetry dashboards

Per §9.6 + §14.3.5 + finding C-1 of §14.3.3. `CacheMetrics` exposes the in-memory counters; the orchestrator-side aggregation (per-athlete cost monitor, hit-rate dashboards) lands when the orchestrator track activates.

---

## 6. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `layer4/cache.py` exists (~360 lines) | ✅ inspection |
| `layer4/cache_postgres.py` exists (~190 lines) | ✅ inspection |
| `layer4/cache_invalidation.py` exists (~130 lines) | ✅ inspection |
| `layer4/cached_wrappers.py` exists (~470 lines) | ✅ inspection |
| `layer4_cache` table in `_PG_MIGRATIONS` | ✅ grep |
| `compute_accepted_output_hash` + `compute_phase_cache_key` in `layer4/hashing.py` | ✅ grep |
| `layer4/__init__.py` re-exports 17 new symbols | ✅ inspection |
| `tests/test_layer4_cache.py` exists with 74 tests | ✅ `pytest tests/test_layer4_cache.py -q` → 74 passed in 0.30s |
| Combined `tests/` 621 green | ✅ `pytest tests/ -q` → 621 passed in 0.71s |
| `Project_Backlog_v51.md` exists | ✅ ls |
| `Project_Backlog_v51.md` file-revision-header bumped to v51 | ✅ grep |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v51.md` | ✅ grep |
| `CLAUDE.md` Last-shipped-session is Step 5; Step 4f demoted | ✅ inspection |
| Branch is `claude/implement-layer4-step4f-vkltG` (harness-pinned) | ✅ |

---

## 7. Files shipped this session

One commit (or multiple bundled) on `claude/implement-layer4-step4f-vkltG`:

**Substantive code + tests + DDL (8 files):**
1. New `layer4/cache.py` (~360 lines)
2. New `layer4/cache_postgres.py` (~190 lines)
3. New `layer4/cache_invalidation.py` (~130 lines)
4. New `layer4/cached_wrappers.py` (~470 lines)
5. Modified `init_db.py` (`layer4_cache` table + 3 indexes appended to `_PG_MIGRATIONS`)
6. Modified `layer4/hashing.py` (2 new helpers per §9.2)
7. Modified `layer4/__init__.py` (17 new re-exports)
8. New `tests/test_layer4_cache.py` (74 tests)

**Bookkeeping (3 files):**
9. New `aidstation-sources/Project_Backlog_v51.md` (per Rule #12; v50 retained as predecessor)
10. Modified `aidstation-sources/CLAUDE.md`
11. New `aidstation-sources/handoffs/V5_Implementation_Layer4_Step5_Cache_Closing_Handoff_v1.md` (this file)

**11 files total. Over the 5-file ceiling intentionally** — Andy confirmed at session start via AskUserQuestion question #4; precedented across Step 4f 13 + Step 4d 13 + Step 4b/c 10 + Step 4e 10 + PR-A 8 + Step 4a 8.

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- v5 onboarding implementation PR — consumes §H.2 + §H.4 + §A.1 extensions per D-66 design wave; independent of Layer 4 implementation track.
- Migration script per `Race_Events_D66_Design_v1.md` §10 — deferred to v5 onboarding implementation PR.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **Step 6 Pattern A orchestration polish** — architect-recommended next forward move per §14.3.4 sequencing.
- **Per-phase cache wiring into `_run_pattern_a_engine`** — concrete carry-forward per §4.2 above.

---

**End of handoff.**
