# Layer 4 Synthesizer 500 Fix (extended thinking × forced tool_choice) — Closing Handoff

**Session:** Diagnosed + fixed a production 500 on every Layer 4 plan-gen entry point (extended thinking is incompatible with a forced `tool_choice` and with `temperature != 1`); also reconciled the owed Neon deploys (bookkeeping half, opened as PR #170).
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_DisciplineCanon_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/amazing-carson-pZDqQ`
**Status:** 6 substantive files (one logical change — an identical 9-line edit across 5 callers — plus its guard test); over the ~5 ceiling but a single mechanical fix, not 6 independent changes. Bookkeeping: this handoff + `CURRENT_STATE.md` + `CARRY_FORWARD.md`. Shipped on PR #170.

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` against the predecessor (DisciplineCanon) — exit 0, all anchors ✅ (discipline_canon module + Swimrun override + share_fields + row_category + display-names re-export + validator wiring + migration file + 32 etl tests + both PRs merged). The session's first half was itself an owed-deploy reconciliation:

| Claim | Anchor | Result |
|---|---|---|
| Predecessor handoff anchors land on disk | `verify-handoff.sh` exit 0 | ✅ |
| Owed FormRefresh A1/A2/Slice-C public-schema deploy applied to Neon | Andy ran `python init_db.py`; `\d` spot-checks (no stale `expedition_ar`/`multi_day_ultra`; `aid_stations` dropped; §G columns dropped; `daily_availability_windows` bound 30..720) | ✅ |
| Owed layer0 batch deploy applied | Andy ran `run_owed_layer0_migrations.sql`; K3 equipment = 10; `primary_movement` 25/25 within `ENUM_MOVEMENTS` | ✅ |
| `primary_movement` HARD-prereq (PR #156) | already satisfied by the discipline-canon loader re-run (`etl/layer0/run.py` inserts it from the extractor) — the standalone migration was an idempotent re-set | ✅ |

**Reconciliation note:** clean. The owed-deploy bullets in `CURRENT_STATE.md` + the §5.0 scenarios in `CARRY_FORWARD.md` were flipped owed → done (both deploy channels), with the UI-walk steps left owed (need the deployed app).

---

## 2. Session narrative

Two halves.

**(A) Bookkeeping — owed-deploy reconciliation.** Recorded that Andy applied both owed Neon deploy channels (public schema via `init_db.py`; layer0 via `run_owed_layer0_migrations.sql`) and verified each clean. Flipped the `CURRENT_STATE.md` "Owed Neon deploys" bullets and the `CARRY_FORWARD.md` §5.0 deploy steps owed → done. Opened PR #170.

**(B) Production 500 on plan-create.** Andy reported a 500 from the live plan-gen path. Root cause: the five Layer 4 production callers build a request with extended **thinking** enabled **and** a **forced `tool_choice`** (`{"type":"tool", ...}`) **and** a **`temperature` of 0.2/0.15**. The Anthropic API rejects both combos with a 400 (extended thinking requires `tool_choice: auto` and `temperature == 1`), which the routes surfaced as an unhandled 500. The bug shipped because every Layer 4 suite injects a **stub** LLM caller — the real `_default_*_caller` request shape was never exercised by a test.

Andy picked **Option A** (keep extended thinking on; relax the two incompatible knobs) **+ an error wrap** (translate SDK errors to the existing graceful `Layer4OutputError` flash). Decided to **fold the fix into PR #170** rather than a dedicated branch (the harness pins this branch).

---

## 3. File-by-file edits

### 3.1 `layer4/per_phase.py`, `layer4/seam_review.py`, `layer4/single_session.py`, `layer4/plan_refresh.py`, `layer4/race_week_brief.py` (modified)

Identical 9-line edit in each `_default_*_caller`. In the `if extended_thinking_budget > 0:` block, after enabling `thinking`, add:

```python
request_kwargs["tool_choice"] = {"type": "auto"}
request_kwargs["temperature"] = 1.0
```

and wrap the SDK call:

```python
try:
    msg = client.messages.create(**request_kwargs)
except anthropic.APIError as exc:
    raise Layer4OutputError(
        "anthropic_api_error",
        detail=f"{type(exc).__name__}: {exc}",
    ) from exc
```

When `extended_thinking_budget == 0` the path is unchanged (forced tool + passed temperature — a valid request). `anthropic.APIError` is the SDK base for status/connection/timeout errors. Anchor: `grep -c 'anthropic_api_error' layer4/*.py` → 1 per file.

---

## 4. Code / tests

New `tests/test_layer4_thinking_request.py` (3 parametrized tests × 5 callers = **15 cases**). Mocks `anthropic.Anthropic` to capture the kwargs passed to `messages.create` and asserts the request-shape invariant the bug violated:

- thinking-on → `tool_choice == {"type":"auto"}`, `temperature == 1.0`, `thinking.type == "enabled"`;
- thinking-off → `tool_choice == {"type":"tool","name":...}`, `temperature == passed`, no `thinking`;
- a raised `anthropic.APIError` → `Layer4OutputError`.

Full suite **1674 passed / 16 skipped** in a fresh `/tmp/venv` (`pip install -r requirements.txt pytest`; system python lacks pytest/pydantic). The 16 skipped are the NL-parser + Layer 3 SDK smoke tests (no `ANTHROPIC_API_KEY`). Absolute count differs from prior handoffs' 1786/1796 — environment/version difference (consistent with the FormRefresh-era 1641 note), not lost coverage; the new suite contributes +15.

---

## 5. Manual §5.0 verification steps

Appended one scenario to `CARRY_FORWARD.md`: a **live plan-create against the real Anthropic API**. This is the decisive proof — the plan-gen path had never run against the real API, so the fix unblocks it but may surface further downstream issues. ~$0.30–0.50 real-LLM cost, Andy's hands.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

Run the **live plan-create** (`/plans/v2/new` for Andy's PGE 2026 context, `ANTHROPIC_API_KEY` set). Confirm: no 500; the per-phase synthesizer returns a tool_use block under `tool_choice: auto`; thinking blocks are emitted and skipped by the parser. If it fails, capture the new error — it will now be a graceful `Layer4OutputError` flash, not a 500, and the detail string names the SDK error type.

### 6.2 Alternative pivots

- **Dedupe the 5 callers.** The request construction + the new guard are identical across `per_phase`/`seam_review`/`single_session`/`plan_refresh`/`race_week_brief`. Extracting a shared `_build_messages_request(...)` + a single error-wrap helper would collapse the fix to one site and make it directly unit-testable without mocking. Good `simplify`-skill candidate; deferred to avoid refactoring during an urgent fix.
- **Retry on transient overload.** API 429/529 now become a `Layer4OutputError` (user retries manually). A bounded backoff retry on transient errors only is a nice-to-have; not in scope for this fix (Andy chose A + wrap, not + retry).

### 6.3 Operating notes for next session

1. `CLAUDE.md` — stable rules (Rule #13).
2. `CURRENT_STATE.md` — what just shipped + focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Keep extended thinking; when on, relax `tool_choice` → `auto` + force `temperature` → `1.0` | Andy (Option A) | Preserves the thinking budget the prompts were tuned for; the tool is still required by the prompt body + offered in `tools`. |
| 2 | Wrap `client.messages.create` → `Layer4OutputError` on `anthropic.APIError` | Andy (error wrap) | Any future SDK error degrades to the existing graceful "synthesis failed" flash instead of a 500. |
| 3 | Fold the fix into PR #170 (no dedicated branch) | Andy | Harness pins `claude/amazing-carson-pZDqQ`; #170 re-titled to lead with the fix. |

---

## 8. Session-end verification (Rule #10)

Re-grep from repo root:

| Check | Result |
|---|---|
| `grep -c 'request_kwargs\["tool_choice"\] = {"type": "auto"}' layer4/per_phase.py layer4/seam_review.py layer4/single_session.py layer4/plan_refresh.py layer4/race_week_brief.py` → 1 each | ✅ |
| `grep -c 'anthropic_api_error' layer4/*.py` → 1 per caller (5) | ✅ |
| `tests/test_layer4_thinking_request.py` exists; `pytest` → 15 passed | ✅ |
| `python -m py_compile` on all 5 callers | ✅ |
| Full suite `pytest tests/` → 1674 passed / 16 skipped | ✅ |
| Working tree clean (post-commit `b53f028`) | ✅ git status |

---

## 9. Files shipped this session

**Substantive (6 files — one logical change + its test):**
1. `layer4/per_phase.py`
2. `layer4/seam_review.py`
3. `layer4/single_session.py`
4. `layer4/plan_refresh.py`
5. `layer4/race_week_brief.py`
6. `tests/test_layer4_thinking_request.py` (new)

Files 1–5 are an identical 9-line edit; file 6 guards it. Over the ~5 substantive ceiling, but a single mechanical fix replicated across near-identical callers, not 6 independent changes. The dedupe follow-on (§6.2) would prevent the replication next time.

**Bookkeeping:**
7. `CURRENT_STATE.md` — last-shipped pointer bumped to this handoff; DisciplineCanon demoted to predecessor; owed-deploy bullets (flipped earlier this session) retained; Tests section + Layer 4 status note updated.
8. `CARRY_FORWARD.md` — owed-deploy §5.0 steps flipped done (earlier); +1 live plan-create §5.0 walk for the 500 fix.
9. This handoff.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md`: flipped the FormRefresh A2 + Slice-C deploy steps owed → done (deploy half only; UI walks still owed); appended a new §5.0 scenario — live plan-create against the real Anthropic API to prove the synthesizer 500 fix end-to-end.

---

**End of handoff.**
