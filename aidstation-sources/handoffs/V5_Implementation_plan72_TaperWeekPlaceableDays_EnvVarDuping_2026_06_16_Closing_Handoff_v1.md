# V5 Implementation — plan-72 taper-week placeable days + Vercel/Neon env-var duping

**Date:** 2026-06-16
**Branch:** `claude/gifted-fermi-7dy0dn`
**PR:** [#661](https://github.com/ahorn885/exercise/pull/661) (merged this session)
**Predecessor handoff:** latest in `aidstation-sources/handoffs/` (2026-06-14 WSH/WSI Event-Windows / Craft-cascade slices)
**CI on merge commit:** Python unit suite ✅ · Layer 0 integrity gate ✅ · JS harness ✅ · Real-LLM smoke skipped · Vercel ✅

---

## ⚡ Diagnostic token

```
DIAG_TOKEN = sk_6U4jchTy5oAhwXszu4hsCsS5AUVa30qJ_c_yDy4fvNc
```

Rotated by Andy 2026-06-16 (supersedes the prior `0dKHoR2…` token).
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` via the
Vercel MCP `web_fetch_vercel_url` tool.

---

## 1. What this session was

Two things:

1. **plan-72 root fix — taper-week session ceiling.** Andy reported a plan
   failed with `generation_error: Plan generation stalled and was stopped — a
   step couldn't complete within the time budget`. The deterministic taper
   week emitted more sessions than there were placeable days before the race,
   so the synthesizer could not lay them out at ≤2/day, every payload
   validation pass failed, and the block exhausted its retry budget and
   stalled. Shipped a deterministic per-week truncation so the session ceiling
   is fed the real placeable-day count.
2. **Vercel/Neon env-var duping.** `DATABASE_URL` and `DATABASE_URL_UNPOOLED`
   had accumulated 20+ times in the Vercel project's env-var list. Root-caused
   to the Neon ↔ Vercel integration provisioning a branch-scoped Preview var
   set per preview deployment, never pruned. Fixed via integration/automation
   settings (Andy) + a documentation guard (repo).

---

## 2. Shipped (PR #661)

### 2.1 — Taper-week placeable-days truncation

- **New helper** `placeable_days_in_week()` (`layer4/session_grid.py`).
  Race-week-aware truncation of the resolved weekly `available_days` to the
  days of a given calendar week that can still hold a session:
  on/before a cutoff date and, when per-day windows are on file, an enabled
  weekday. Returns `min(available_days, <placeable count>)`. Fast-path: when
  `cutoff_date is None` (open-ended / no race) or the whole week is on/before
  the cutoff, returns `available_days` unchanged — so every non-race-adjacent
  week is byte-identical to prior behavior.
- **Cutoff** = `event_date − 2` (`layer4/per_phase.py:_format_session_grid`).
  Per Andy's "reserve as rest" choice: the **race day** and the **immediate
  pre-race day** (rest) are both excluded; the last trainable day is
  `event_date − 2`.
- **Wire:** `_format_session_grid` computes the per-week placeable count and
  passes it as `available_days` into `build_session_grid`, so the deterministic
  `2 × days` clamp in `apply_session_ceiling` becomes a real ≤2/day feasibility
  guarantee instead of leaning on the post-hoc payload validator (which only
  rejects — there was no deterministic shedding path; that was the stall).
  A Rule #15 `placeable_days:` log line is emitted only when truncation fires.
- **Exports:** added to `layer4/session_grid.py` `__all__` and re-exported from
  `layer4/__init__.py`.
- **Tests:** `tests/test_layer4_session_grid.py::TestPlaceableDaysInWeek` —
  open-ended pass-through, full-week-before-cutoff pass-through, enabled-day
  truncation, the excluded pre-race rest day, the windowless
  `available_days_per_week` cap, and the `available_days` ceiling.

**Back-compat:** non-race weeks and open-ended plans are unchanged. Only the
race-adjacent taper week(s) shrink. Full suite: **2503 passed, 30 skipped**.

### 2.2 — DB env-var duping documentation (`DATABASE.md`)

New "Duplicate `DATABASE_URL` / `DATABASE_URL_UNPOOLED` in the Vercel env list"
section under *Where the DB lives*: explains that nothing in the repo adds them
(no `vercel env add` in any script/workflow/hook), that they are branch-scoped
Preview vars from the Neon integration, that the app reads only the unscoped
`DATABASE_URL` (`database.py:5`), and records the resolved configuration.

---

## 3. Ops actions taken by Andy (not in repo)

The env-var fix is platform configuration, not code:

- **Neon Console → Integrations → Vercel → Automation workflows** — enabled
  "Automatically delete Neon preview branches after the corresponding git
  branch is merged or deleted." (Stops the accrual.)
- **GitHub → repo Settings → "Automatically delete head branches"** — enabled,
  so merged PR branches are deleted, which triggers the Neon automation.
- **Neon → Branches** — manually deleted all existing orphaned preview branches
  (one-time backlog cleanup; the automation is not retroactive). Deleting the
  Neon branch removes its linked Vercel env vars via the integration.

**Optional, not yet done:** the integration's "Vercel environment variables"
checklist still pushes `PGHOST`/`PGUSER`/`PGDATABASE`/`PGPASSWORD`/`…UNPOOLED`
per branch; the app only needs `DATABASE_URL`, so those can be unchecked to
shrink the per-branch footprint further.

**Verify:** Vercel → Project `exercise` → Settings → Environment Variables →
filter **Preview** — confirm the stale branch-scoped rows are gone (deleting
the Neon branches should have removed them; any leftovers via ⋯ → Remove, or
`vercel env ls preview` / `vercel env rm <NAME> preview <branch> -y`).

---

## 4. Owed / next focus

- **(optional)** Trim the Neon integration's pushed-variable checklist to just
  `DATABASE_URL` (see §3).
- **(optional)** The `DEV_SETUP.md` `vercel env pull` section could gain a
  one-line pointer to the new `DATABASE.md` env-var note.
- **Watch the next race-targeted plan generation** to confirm the taper week
  now lays out at ≤2/day end-to-end in prod (the unit + integration tests pass;
  this is the live confirmation).
