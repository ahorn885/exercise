# Plan-Gen Observability (#321) — Plan & Blast-Radius (v1)

**Status:** IMPLEMENTED 2026-05-30 (Andy chose **T1 + T2, admin-only**). Scoping issue #321
(block-content logging + partial-plan view + incremental persist), deferred by #314/#315/#319.

## As-built (T1 + T2, admin surface)
- **Durable table `plan_progress_blocks`** (`init_db.py` `_PG_MIGRATIONS`) — keyed
  `(plan_version_id, phase_idx)`, holds each accepted week-block's `sessions_json` +
  `synthesis_metadata_json`. Auto-creates on the next deploy (`init_postgres()` runs on every
  cold start with `IF NOT EXISTS`) — **no manual Neon step**.
- **Snapshot** (`plan_sessions_repo.snapshot_progress_blocks`) — copies the cached blocks into
  the durable table once per generation pass, called from `_advance_plan_generation`
  **defensively** (its own try/except — a snapshot fault never breaks generation).
- **Admin inspect view** — `GET /admin/plan/<id>/inspect` (`routes/admin.py`,
  `templates/admin/plan_inspect.html`): plan status/error/progress + per-block sessions &
  validator flags. Admin-only (`_require_admin`), reads any user's plan.
- **Block-content logging** (`layer4/per_phase.py`) — accepted-path validator flags on the
  per-block summary line + an env-gated (`PLAN_GEN_LOG_BLOCK_CONTENT=1`) per-session dump.
- **Guardrail honored** — `plan_progress_blocks` is a write-only side effect; a test asserts
  it never appears in `layer4/hashing.py` (the cache-key module).
- Tests: `tests/test_plan_progress_blocks.py` (+5). Full suite green.

**Headline finding:** most of the substrate already exists. Accepted blocks are *already*
persisted per-pass (in `layer4_cache`), the loop *already* logs rich diagnostics, and the
cached value is the *full* block content. So this is mostly **surface the data we already
have**, not build new machinery — which lets us ship the high-value 80% with zero schema
change and zero cache-key risk.

---

## 1. Decisions captured / context

The three parts of #321, and why they were prioritized: the D-77 saga was repeatedly *blind*
to per-block state, and the **Tier-1 verification run** (generate a fresh PGE plan, confirm
`ready`) is far higher-EV if it's self-diagnosing. This work is the lens for that run.

**`#303 (food_allergies) is parked** — Andy, 2026-05-30. Not a priority.

---

## 2. How plan-gen works today (the substrate this builds on)

- **Multi-pass loop.** `_advance_plan_generation` (`routes/plan_create.py:322`) is re-invoked
  by the poller (`/plans/v2/<id>/generate`) and cron (`/plans/v2/cron/generate-pending`).
  Each pass synthesizes week-blocks until its wall-clock budget (`_INVOCATION_BUDGET_S`) is
  spent, then returns `generating`; the next pass resumes from cache.
- **Blocks are cached per-pass, individually committed.** Each accepted week-block is written
  to `layer4_cache` (`phase_idx >= 0`) at the end of its synthesis
  (`cache.py:506-514`), as `{"sessions":[…PlanSession…], "synthesis_metadata":{…}}`
  (`plan_create.py:261-284`). **This is the full block content, not a hash.** (PR #314 fixed
  the bug where a connection drop lost this write.)
- **`plan_sessions` is written all-at-once at the end.** On final success only:
  `DELETE … WHERE plan_version_id=? → persist_layer4_sessions → flip generation_status='ready'`,
  one commit (`plan_create.py:415-425`). The view reads `plan_sessions`, so **nothing is
  visible until `ready`.**
- **Control surface:** `plan_versions.generation_status` ∈ {generating, ready, failed},
  `generation_error`, `generation_units_cached` (count of cached blocks)
  (`init_db.py:1947-1977`).
- **The view** (`view_plan`, `plan_create.py:577`) reads `plan_sessions`; the **progress
  screen** (`templates/plan_create/progress.html`) is a pure spinner. No partial visibility,
  no admin plan-inspect surface (`routes/admin.py` has only user counts + refresh aggregates).
- **Logging today** is rich `print()` diagnostics: per-attempt latency/tokens
  (`per_phase.py:1605`), validator **rejections** (`:1758`), per-block summary
  `done — … accepted=T/F … sessions=K` (`:1782`), cache HIT/MISS (`cache.py:490/500`), and
  the `call_cache_key=… [l1=… l2a=… …]` drift line (`cached_wrappers.py:387`).

---

## 3. The hard constraint — cache-key determinism guardrail (#199/#202/#294)

The per-block key chains `prev_accepted_output_hash`; the call key folds `user_id + l1..l3b
hashes + plan_start_date + etl_version_set + model params` (`hashing.py:118-326`). Keys are
computed from **immutable upstream payloads before orchestration**. The non-negotiable rule
for everything below:

> **Any new logging or persistence is a WRITE-ONLY side effect. It must never be folded into,
> nor read back into, a cache key.** Specifically never key on `plan_version_id`,
> `generation_status`, `generation_units_cached`, timestamps, or any new progress row.

`print()` logging is inherently safe. New persistence is safe as long as it's never an input
to `compute_*_key`. This is the one thing a reviewer must check on every diff in this work.

---

## 4. Part-by-part design

### Part 1 — Block-content logging (smallest gap)

Today the loop logs everything *except* two things: the validator verdict on the **accepted**
path (only rejections print), and the block's actual session content. Two additions:

1. **Accepted-path verdict** — at the accept branch (`per_phase.py:1768`), emit a one-liner
   mirroring the rejection log: `synthesize_phase: {tag} accepted — {n} warning(s): [rule(sev)…]`
   (currently silent on accept, so a best-effort-accepted block's warnings vanish from logs).
2. **Gated block-content dump** — behind an env flag (`PLAN_GEN_LOG_BLOCK_CONTENT=1`, default
   off so prod logs aren't flooded), log a compact per-session line for the accepted block
   (date, discipline, kind, duration, intensity, key flags). Sourced from the in-memory
   `PhaseSynthesisResult.sessions` (`per_phase.py:1309`).

Pure `print()` → **zero cache-key risk, no schema, no migration.**

### Part 2 — Partial-plan view (mostly a read)

The blocks-so-far are already in `layer4_cache`. Build:

1. **A read helper** `load_partial_blocks(db, user_id, plan_version_id)` — generalize
   `_count_cached_blocks` (`plan_create.py:215`) from COUNT to SELECT: pull the
   `entry_point='plan_create', phase_idx ∈ [0, _SEAM_CACHE_PHASE_IDX_BASE)` rows for this
   plan's window (`created_at >= pv.created_at`, user-scoped), hydrate each
   `payload_json → sessions`, order by `phase_idx`.
2. **A route** — `GET /plans/v2/<id>/progress-detail` (user-scoped via the existing
   `_load_plan_version` 404 pattern) returning the partial blocks + `generation_status`,
   `generation_units_cached`, elapsed-since-last-block.
3. **Render** — extend `progress.html` (or a sibling template) to show the blocks generated
   so far, grouped by week, each tagged **"draft — not finalized."** Reuse the `view.html`
   session-row markup.

**No schema change, no cache-key risk** (read-only).

**Caveat (note, don't over-engineer):** the cache-block lookup keys on
`(user_id, entry_point, created_at-window)`, not the plan's `call_cache_key` (which isn't
stored on `plan_versions`). For one in-flight plan per user (today: the PGE athlete) this is
exact. With multiple concurrent generations per user it could mingle blocks. Two cheap fixes
if/when that matters: (a) persist the `call_cache_key` on the `plan_versions` row at
allocation and filter on it, or (b) accept the created-at window as good-enough for v1. **Open
decision — see §7.**

### Part 3 — Incremental persist (the only part with real design weight)

**Reframing:** the original goal — "don't discard earlier accepted work on a late-pass
failure" — is **already largely met.** Accepted blocks are committed to `layer4_cache`
per-block, and #314 stopped the connection-drop loss. A failed/stalled plan re-runs and
replays the cached prefix. So the *reliability* goal is mostly done.

What's genuinely *not* first-class:
- `layer4_cache` is **TTL/eviction-managed** — a long-delayed resume *could* lose blocks
  (unlikely within an active generation window, but possible).
- The accepted prefix isn't queryable as durable **plan data** (only as cache).

**Two options (Andy's call):**
- **(3a) Cache-read only (recommended for now).** Treat `layer4_cache` as the partial-block
  source (Part 2 already does). No new table. Accept the TTL caveat. Ships immediately.
- **(3b) Durable `plan_progress_blocks` table.** New table (`plan_version_id, phase_idx,
  week_in_phase, sessions_json, accepted_at`), written once per accepted block inside the
  loop. Eviction-proof, post-completion durable, and the foundation for a future
  "accept this block / regenerate that one" UX. Cost: a migration + a per-block write +
  Trigger #3 (schema). **Defer unless we want the accept/reject UX or hit real eviction.**

---

## 5. Tiering — what to actually build now

| Tier | Scope | Risk | Schema | Ships |
|------|------|------|------|------|
| **T1 (recommended now)** | Part 1 (logging) + Part 2 (partial view, cache-read) + Part 3a | low | none | self-diagnosing verification run |
| **T2 (defer)** | Part 3b durable `plan_progress_blocks` + accept/reject UX | med (Trigger #3) | +1 table, migration | reliability/UX, not needed for the verification |

**T1 delivers ~all the debuggability value** that made us prioritize this — block-by-block
visibility in logs *and* UI, with no schema change and no cache-key exposure. T2 is a
durability/UX enhancement that can follow once the verification run proves the pipeline.

---

## 6. Blast radius

- **Touched (T1):** `routes/plan_create.py` (new read helper + route), `layer4/per_phase.py`
  (+2 log lines), one template (+ maybe a sibling), and tests. No existing behavior changes
  — additive only.
- **Cache-key guardrail:** the single must-check invariant (§3). T1 is read/log-only, so it
  cannot drift a key by construction; the reviewer still verifies nothing new feeds
  `compute_*_key`.
- **Concurrency caveat:** the created-at-window block lookup (Part 2) — exact for one
  in-flight plan/user; §7 decision covers the multi-plan hardening.
- **Not affected:** the synthesis math, the cache contents, the `ready`-plan view, the
  resumption logic. `plan_sessions` end-only write is unchanged under T1.

---

## 7. Open decisions for Andy

1. **Tier:** ship **T1 only** now (recommended), or include the durable `plan_progress_blocks`
   table (T2) in the same PR?
2. **Partial view surface:** user-facing (extend the progress screen the athlete sees) vs.
   **admin/debug** (`/admin/plan/<id>/inspect`) vs. both? For the verification run, an
   admin/debug page is the higher-leverage first cut.
3. **Block-content dump:** env-gated `print()` (recommended) vs. always-on compact line?
4. **Concurrency hardening:** persist `call_cache_key` on `plan_versions` now (clean, tiny
   schema add), or accept the created-at window for v1 and defer?

---

## 8. Sequenced build (once T1 confirmed)

1. `per_phase.py` — accepted-path verdict log + env-gated content dump (+ unit assertions on the format).
2. `routes/plan_create.py` — `load_partial_blocks()` read helper + `/progress-detail` route (user-scoped).
3. Template — partial-block render with "draft" badge (admin or progress, per §7.2).
4. Tests — `load_partial_blocks` over a seeded `layer4_cache` (in-flight + failed), route auth/ownership, log-format guards.
5. Verify: full suite green; then drive the **Tier-1 PGE verification run** with the new visibility live.
