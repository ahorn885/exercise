# layer4_cache entry_point CHECK drift fix — Closing Handoff

**Session:** Diagnosed + fixed a live plan-generation 500. The progress screen showed "Plan generation didn't finish / Athlete evaluation failed (schema_violation)"; a Vercel runtime traceback revealed the real fault: a `psycopg2.errors.CheckViolation` on `layer4_cache_entry_point_check`. The 2026-05-21 Layer 3 caching slice (and the NL-parser cache) extended `cache.VALID_ENTRY_POINTS` to **7** labels but never updated the `layer4_cache.entry_point` CHECK constraint (still the original **4** Layer-4 labels) — in the live Neon table *and* in the `init_db.py` `CREATE TABLE` DDL. So every 3A/3B/NL cache write raised an uncaught 500, which 500-looped the every-minute `generate-pending` cron and re-rolled the 3A LLM call each pass.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_Layer4_CronBackgroundGeneration_2026_05_26_Closing_Handoff_v1.md` (§6.2 — cron-driven background generation, PR #176 `2594f12`)
**Branch:** `claude/ecstatic-allen-A6GC8`
**PR:** #177
**Status:** 2 substantive files (`init_db.py`, `routes/plan_create.py`) + 1 test file + bookkeeping. Full suite **1710 passed / 16 skipped** (+1 = the new regression test).

---

## 1. Session-start verification (Rule #9)

| Claim (predecessor) | Anchor | Result |
|---|---|---|
| Branch even with `origin/main` at PR #176 `2594f12` | `git log` | ✅ clean, working tree clean |
| §6.2 cron + `_advance_plan_generation` + `cron_authorized` present | grep | ✅ present |

No drift. State was clean; this session was driven by a live bug report rather than the roadmap's next forward move (§6.3 notifications).

---

## 2. Session narrative

Andy linked the §6.2 handoff and reported a live plan-gen failure: "Plan generation didn't finish / Athlete evaluation failed (schema_violation)." That user-facing message (`routes/plan_create.py:229`) drops the exception `detail`, so the cause wasn't visible from the message alone. Two `schema_violation` paths exist (no tool block in `llm_invocation.invoke_tool_call`; or tool args failing `Layer3APayload` validation in `layer3a/builder.py`) — neither logs the detail on the pydantic path.

Pulled the Vercel runtime log for the failing request. It was the **cron** (`GET /plans/v2/cron/generate-pending`) returning a **500 after ~141s**, not the schema_violation panel. 3A actually *succeeded* (the only log lines were warn-only `Layer3AEvidenceBasisWarning`s). The traceback pinned it:

```
File "layer3a/cached_wrapper.py", line 166, in llm_layer3a_athlete_state_cached
    cache_backend.put(...)
File "layer4/cache_postgres.py", line 129, in put
    db.execute(...)
psycopg2.errors.CheckViolation: new row for relation "layer4_cache"
violates check constraint "layer4_cache_entry_point_check"
DETAIL: Failing row contains (..., -1, 1, llm_layer3a_athlete_state, null, ...)
```

`cache.VALID_ENTRY_POINTS` (`layer4/cache.py:61`) = 7 labels (the 4 Layer-4 + `llm_layer3a_athlete_state`, `llm_layer3b_goal_timeline_viability`, `nl_parser_parse_intent`), but `init_db.py`'s `layer4_cache` CHECK only allowed the 4 Layer-4 labels. `CheckViolation` is not a typed `Layer*` error, so it escaped `_advance_plan_generation`'s catches as a raw 500. The suite never caught it because tests use the in-memory cache backend (no constraint). Knock-on: 3A never cached → every pass re-rolled the 3A LLM call → re-exposed the intermittent `schema_violation` Andy first saw.

Andy approved scope (AskUserQuestion): constraint fix + regression test + defensive catch-all (declined the detail-capture logging option).

---

## 3. File-by-file edits

### 3.1 `init_db.py` (modified)
- **`CREATE TABLE layer4_cache` DDL (`:1263`)** — extended the inline `entry_point` CHECK from the 4 Layer-4 labels to all 7 (matches `cache.VALID_ENTRY_POINTS`). Fixes fresh DBs.
- **`_PG_MIGRATIONS` tail** — appended an idempotent repair migration (a `DO $$ … END $$;` block: `ALTER TABLE layer4_cache DROP CONSTRAINT IF EXISTS layer4_cache_entry_point_check;` then `ADD CONSTRAINT … CHECK (entry_point IN (…7…))`). Drop-then-add is idempotent; the new set is a superset, so existing rows still satisfy it. `CREATE TABLE IF NOT EXISTS` is a no-op on the deployed table, so the migration is required to repair live Neon.

### 3.2 `routes/plan_create.py` (modified)
- **`_advance_plan_generation`** — added a trailing `except Exception as exc:` after the typed-error catches. Logs the unexpected exception + marks the row `failed` via `_mark_plan_failed` (which rolls back first). Prevents any non-`Layer*` error (e.g. a DB error mid-cone) from escaping as a 500 and 500-looping the every-minute cron, which re-picks `generating` rows.

### 3.3 `tests/test_layer4_cache.py` (modified)
- **`TestLayer4CacheEntryPointConstraint`** (1 test) — parses the `entry_point IN (…)` sets out of `init_db._PG_MIGRATIONS` (both the `CREATE TABLE` DDL and the repair migration) and asserts each equals `set(VALID_ENTRY_POINTS)`. Catches this drift class statically, since the in-memory backend can't.

---

## 4. Code / tests

Full suite **1710 passed / 16 skipped** in a fresh `/tmp/venv` (1709 pre-session → **+1**: the new constraint test). No tests removed.

---

## 5. Owed action (Andy's hands) — REQUIRED for the fix to take effect

The PR preview deploy runs against the **existing** Neon DB, whose constraint is still the broken 4-value set — so plan-gen keeps 500-ing until the migration is applied. Steps in §6.3 below / the chat. After the migration + redeploy, the clean test is a real `/plans/v2/new` run: 3A/3B cache (no `CheckViolation`), the cron returns `{advanced, ready, failed}` 200, and a subsequent pass hits the 3A cache (no LLM re-roll).

---

## 6. Next session pointers

### 6.1 Residual — the intermittent `schema_violation` itself
Fixing the constraint stops 3A re-rolling every pass, which should sharply reduce exposure to the athlete-evaluation `schema_violation`. But the underlying path (3A/3B tool args occasionally failing `Layer3APayload`/`Layer3BPayload` validation, or the model declining the tool twice) is not *proven* fixed — we never captured its `detail`. If it recurs after the migration, the first move is the **detail-capture logging** Andy declined this round: log `exc.detail` (the pydantic `ValidationError` / `stop_reason`) on the `Layer3*OutputError`/`Layer4*Error` catches in `_advance_plan_generation` so the cause is visible.

### 6.2 Residual — cron structural fragility (carried, not addressed)
`cron_generate_pending` runs the **full** `orchestrate_plan_create` cone for up to `_CRON_ADVANCE_BATCH=5` rows sequentially in one invocation, relying on platform-kill + `layer4_cache` resume. With the constraint fixed each phase now actually commits, so repeated fires make progress — but the seam-review/final-validator tail is still uncached and re-runs whole each resume, and the poller + cron can run the same row concurrently (double LLM cost). If this bites, consider: bound the cron to one row + a wall-clock budget, and/or cache the seam tail. Not triggered yet.

### 6.3 Architect-recommended next forward move — §6.3 email + in-app notifications
Unchanged from the §6.2 handoff: on terminal status in `_advance_plan_generation` (the single terminal hook for poller + cron), send a "plan ready"/"plan failed" email + a dashboard status badge; guard double-send (transition-into-terminal only, or a `notified_at` column).

### 6.4 Operating notes for next session (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items.
4. This handoff.
5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Repair the constraint via DDL edit + idempotent `DO`-block DROP/ADD migration | Claude | `CREATE TABLE IF NOT EXISTS` won't alter the live table; the DDL must also be fixed for fresh DBs. Drop-then-add is idempotent + the superset validates against existing rows. |
| 2 | Add a defensive `except Exception` in `_advance_plan_generation` | Andy | A non-`Layer*` error shouldn't 500-loop the every-minute cron; mark the row terminal instead. |
| 3 | Add a static constraint↔`VALID_ENTRY_POINTS` regression test | Andy | The whole bug class is invisible to the in-memory-backed suite; a source-level assertion is the only guard. |
| 4 | Defer detail-capture logging | Andy | Not needed if the constraint fix resolves the symptom; revisit only if `schema_violation` recurs (§6.1). |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `init_db.py` `layer4_cache` CHECK lists all 7 entry points (DDL + repair migration) | ✅ |
| `except Exception` catch-all in `_advance_plan_generation` | ✅ |
| `TestLayer4CacheEntryPointConstraint` present + passing | ✅ |
| `py_compile` the 3 files | ✅ |
| Full suite `pytest tests/` → 1710 passed / 16 skipped | ✅ (fresh `/tmp/venv`) |
| Working tree clean after commit | ✅ |

---

## 9. Files shipped this session

**Substantive (2 files):**
1. `init_db.py`
2. `routes/plan_create.py`

**Tests:**
3. `tests/test_layer4_cache.py`

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, this handoff.

---

**End of handoff.**
