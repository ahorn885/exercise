# Plan-Gen D-77 — Cone Cache-Key Determinism Audit (#202) — Closing Handoff

**Session:** Live-fire move #202 off epic #201 — audit the two un-checked wall-clock reads for the cache-key non-determinism class that caused the D-77 convergence money-loop (c4f9160 + PR #199). The audit concluded "no third money-loop" — **but the prod re-run (Andy, same session) DISPROVED that conclusion: a third drift exists in `ProviderStatus.last_sync`. See §9 — fixed in this same PR.** The audit's per-instance verdicts (§1) still stand for the two reads it examined; the miss was scope — it never scrutinized `last_sync`, an output field, and its guard test used fixed DB rows.
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_VolumeBandPctToHours_UnitFix_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/zealous-pasteur-LYRuG`
**Status:** 1 code file + 1 test file. Suite **1801 passed / 16 skipped** (+2). **No migration** (code-only; the change is defensive and inert in production — the touched fallback is unreachable in the cone).

---

## 1. The finding — audit, not a bug

The #202 mandate (from the backlog-migration handoff / epic #201) was to audit the **2 un-audited timestamp reads** named there — `layer2d/builder.py:567` and the `layer3a` `as_of` fallback — for the same non-determinism class as c4f9160 (`layer1.as_of` + `layer2a.generated_at`) and PR #199 (`layer2e.computed_at`). Those prior bugs stamped **full-precision** timestamps into payloads that fold into every Layer 4 cache key, so the cone re-minted keys every resumable pass → nothing ever cached → the 504 money-loop.

Full sweep of wall-clock / non-deterministic reads across the cone (`layer1` `layer2a-e` `layer3a/b` `layer4`):

| Read | Verdict |
| :--- | :--- |
| `layer1/builder.py:161` `as_of=datetime.utcnow().replace(midnight)` | ✅ already day-anchored (c4f9160) |
| `layer2a/builder.py:727` `generated_at=…replace(midnight).isoformat()` | ✅ already day-anchored (c4f9160) |
| `layer2e/builder.py:1081` `today or date.today()` | ✅ day-granular; `computed_at` fixed in #199 |
| `layer3a/builder.py:403` `now = datetime.now(...)` | ✅ transient future-date validation guard; never stored/hashed |
| `layer4/orchestrator.py` `today = date.today()` fallbacks | ✅ day-granular; `as_of = datetime.combine(today, time.min)` is midnight-anchored |
| `uuid.uuid4()` session IDs (`per_phase`/`plan_create`/`plan_refresh`/`single_session`/`race_week_brief`) | ✅ not a key input; frozen by the per-block synthesis cache (see §1.1) |
| **`layer3a/integration.py:471` `as_of or datetime.now()`** (#202 target 1) | ⚠ unreachable + day-granular — **hardened** (§2) |
| **`layer2d/builder.py:567` `datetime.utcnow().date()`** (#202 target 2) | ⚠ day-granular, self-healing — **documented, left as-is** (§5 D3) |

### 1.1 Why the two flagged instances are NOT the money-loop class

**Target 1 — `layer3a/integration.py:471` (`q_layer3A_connected_providers`).** The `connected_providers` block rides in the `Layer3AIntegrationBundle`, whose hash (`compute_payload_hash(integration_bundle)`) folds into the **3A call cache key** (`layer3a_athlete_state_key`, `layer3a/cached_wrapper.py:135`). So determinism here IS load-bearing. But: (a) the `or datetime.now()` fallback is **unreachable in the cone** — the sole non-test caller, `assemble_layer3a_integration_bundle` (`integration.py:601`), takes `as_of: datetime` (required, non-Optional) and the orchestrator passes `as_of = datetime.combine(today, time.min)` (midnight) at both call sites (`orchestrator.py:320, 631`); and (b) even if it fired, `anchor` is consumed **only** through `_window_cutoff(...)`, which `.date()`-truncates — it is never stored raw in `ProviderStatus` (the output is day-granular coverage booleans + DB-sourced `last_sync`). So no sub-day drift is possible.

**Target 2 — `layer2d/builder.py:567` (`_is_recent_post_surgical`).** `datetime.utcnow().date()` is read fresh each cone build (the Layer 2D entry `q_layer2d_injury_risk_profile_payload` takes no logical `today`). It reaches `layer2d_hash` **only** when the athlete's primary injury is `Post-surgical` and within the 6-week window (it swaps the accommodation modality to `loading_type_change`). It is `.date()`-granular → at most one re-key per **UTC midnight** → one re-synthesis, then stable (self-healing). Same accepted granularity as `layer1.as_of`. Not the per-pass full-precision class.

**Net: the genuine money-loop bugs were all already fixed.** This audit closes the question "is a third instance hiding?" with: no.

## 2. What shipped

`layer3a/integration.py:471` — day-anchored the `q_layer3A_connected_providers` `as_of` fallback (`datetime.now()` → `datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)`) with a comment tying it to the 3A-cache-key determinism rationale. Defensive: the path is unreachable today, but a full-precision fallback on a key-feeding path is a footgun if a future caller omits `as_of` or uses `anchor` raw.

Two guard tests in `tests/test_layer3a_integration.py`:
- `test_none_as_of_fallback_uses_day_anchored_cutoffs` — exercises the fallback (`as_of` omitted); asserts the SQL date cutoffs are pure ISO dates and stable across calls.
- `test_bundle_hash_is_deterministic_across_passes` — the load-bearing invariant: `compute_payload_hash(assemble_layer3a_integration_bundle(...))` is identical across two assembles with the same day-anchored `as_of`. Catches the c4f9160 class (a fresh timestamp anywhere in the bundle/accessors) at the integration-bundle-hash level.

## 3. Code / tests

| File | Change |
| :--- | :----- |
| `layer3a/integration.py` | Day-anchored the `q_layer3A_connected_providers` `as_of` fallback (defensive determinism hardening). |
| `tests/test_layer3a_integration.py` | `+compute_payload_hash` import; `+test_none_as_of_fallback_uses_day_anchored_cutoffs`; `+test_bundle_hash_is_deterministic_across_passes`. |

Suite: **1801 passed, 16 skipped** (+2).

## 4. Owed actions + manual verification

- **No new owed deploy.** Code-only, no migration; the touched fallback is unreachable in the cone, so production behavior is unchanged. The change is a regression-guard for a future footgun.
- **The PGE prod re-run is still owed (Andy's hands)** — carried from the #293 volume-band handoff §4 (DB egress to Neon is blocked in the dev container). This audit *predicts* convergence should now hold: no remaining per-pass key drift. The re-run remains the live proof (`call_cache_key=<X>` identical across passes; per-block `HIT`; `<phase>:w<n> done — … accepted=True`; reaches `ready`).

## 5. Decisions pinned

| | Decision | Who | Rationale |
| :--- | :----- | :--- | :----- |
| **D1** | Treat #202 as closed: no third money-loop | Claude | Full cone sweep; both flagged instances are day-granular, not per-pass full-precision. The 3 real bugs (layer1/2a/2e) were already fixed. |
| **D2** | Day-anchor the `layer3a/integration.py:471` fallback (defensive) | Claude | Unreachable today, but a full-precision `datetime.now()` on a path whose output folds into the 3A cache key is a footgun; matches the c4f9160 day-anchor pattern. 1 line, inert in prod. |
| **D3** | Leave `layer2d/builder.py:567` as-is (documented) | Claude | Day-granular + self-healing (≤1 re-key per UTC midnight, post-surgical athletes only). Threading the cone's `as_of` into the Layer 2D entry to source one logical clock would be a Layer-2 contract change (Trigger #3) disproportionate to a self-healing once-a-day re-key. **Offered to Andy as an optional consistency follow-on; not done silently.** |
| **D4** | Reconcile the CURRENT_STATE drift (#293 was never recorded) | Claude | Rule #10 gap from the volume-band session; recorded it in the predecessor chain this session. |

## 6. Next session — deferred follow-ons

- **(Owed, Andy's hands) PGE 2026 prod re-run** — the live convergence proof for the whole D-77 arc (volume-band #293 + the determinism fixes). The single highest-value next action; everything below is gated on what it shows.
- **(Optional, Trigger #3) Source Layer 2D's date from the cone `as_of`** — thread a `today`/`as_of` into `q_layer2d_injury_risk_profile_payload` so the post-surgical-window check uses the cone's one logical clock instead of `datetime.utcnow()` (D3). Eliminates the lone cross-midnight re-key + the only spot where the cone reads the clock independently. Small, but it's a Layer-2 entry-signature change → ratify first.
- **From the #293 handoff §6 (unchanged):** discipline taxonomy → trail running vs trekking (Catalog/ETL, Trigger #3); rest-day / load-variation synthesis-shape (Trigger #1 prompt); feasibility gate + block-mode latency levers (largely subsumed — revisit only if the re-run still rides the 300s cap).

## 6.3 Operating notes for next session (read order — Rule #13)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

The cone cache-key determinism model: every wall-clock read on a key-feeding path must be day-anchored (date-granular). The invariant is now guarded at the integration-bundle level by `tests/test_layer3a_integration.py::test_bundle_hash_is_deterministic_across_passes`; the analogous upstream guards live in `tests/test_layer2*`/`test_layer1*` per c4f9160 / #199. Don't reintroduce a full-precision `datetime.now()`/`utcnow()` into any hashed payload.

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer3a/integration.py` fallback day-anchored (no bare `datetime.now()`) | ✅ `grep -n "as_of or datetime" layer3a/integration.py` → utcnow().replace(midnight) |
| `test_none_as_of_fallback_uses_day_anchored_cutoffs` present + green | ✅ `pytest -k fallback_uses_day_anchored` |
| `test_bundle_hash_is_deterministic_across_passes` present + green | ✅ `pytest -k bundle_hash_is_deterministic` |
| Full suite 1801 / 16 | ✅ `pytest tests/` |
| No migration / no schema change | ✅ code-only |
| Working tree clean after commit | ✅ git status |

---

## 9. ⚠ CORRECTION — the prod re-run found a third drift (`last_sync`); fixed

The audit's headline ("no third money-loop") was **wrong**. Andy ran the PGE plan (`pv=35`) on prod (main, with #293). It did NOT money-loop in the old way, but it 504-looped ~6 min then failed `synthesis_budget_exhausted`. The runtime logs (`synthesize_phase:` diagnostics) showed the real state:

- **Two passes had different `call_cache_key`, differing ONLY in `l3a` + `l3b`** (`l1`/`l2a`–`l2e` byte-identical). So 3A + 3B re-ran every pass → every Layer 4 block orphaned (`Build:w1 MISS` in both passes, re-burning a ~150s synthesis call each time). Still a non-convergence money-loop, just one the audit missed.
- **Root cause:** `ProviderStatus.last_sync` (`layer4/context.py:952`) is a raw `MAX(webhook_events.received_at)` timestamp. It rides in the `Layer3AIntegrationBundle`, whose hash (`compute_payload_hash`) folds into the 3A cache key (`layer3a_athlete_state_key`). When a connected provider (Andy's COROS/RWGPS) checks in mid-generation, `last_sync` advances sub-day → bundle hash drifts → 3A misses → re-runs at temp=1 → new `l3a` → 3B keys on `layer3a_hash` so `l3b` drifts too → `call_cache_key` drifts → blocks never reuse. The exact c4f9160/#199 pattern, in the one bundle field the audit didn't scrutinize (its guard test used fixed DB rows, so it never exercised a volatile field).

**Fix (this PR):** day-anchor `last_sync` in `q_layer3A_connected_providers` (`layer3a/integration.py`) — `MAX(received_at).replace(hour=0,…)`. Day-granular is sufficient for the LLM's "is data flowing" view; genuine new training data still invalidates via the day-keyed `recent_workouts/sleep/hrv` records. Plus HIT/MISS + `integration_bundle_hash` diagnostics in the 3A + 3B cached wrappers so the next re-run *proves* the bundle hash is stable (a drifting `ibundle=` would name a remaining field; a later-pass `HIT` means 3A finally caches). New guard test `test_last_sync_is_day_anchored` (same-day, different times → one anchored value). Suite **1802/16**. No migration.

**Owed (Andy's hands): redeploy + re-run.** Expected logs: `llm_layer3a_athlete_state: … HIT … ibundle=<X>` with `ibundle` IDENTICAL across passes, `call_cache_key` stable, per-block `HIT` on later passes, plan grinds to `ready` over the cron passes (each block best-effort-accepts, so it caches + progresses even while `volume_band` is still flagged — see below). **If `ibundle` STILL drifts**, the diagnostic names it: most likely genuinely-new workout data arriving mid-generation (a harder, separate problem) rather than `last_sync`.

**Still open (NOT convergence blockers, separate follow-ups):**
- **B — `volume_band_below` still fires** after #293 (D-001, D-015 in the logs). Does NOT block convergence (the per-block budget guard best-effort-accepts, 12-13 sessions cache), but the accepted weeks are flagged under-volume. Likely the hours-band is being applied to **D-015 Navigation** (a skill/conditional discipline, not a standalone-hours discipline — note the `unknown discipline_category 'Navigation'` warning) and/or the primary is under-prescribed. Needs a modeling decision before changing the band logic.
- **C — per-block latency ~150s** (`out`≈10k tokens). ~1.5 blocks per 300s invocation, so convergence takes several cron passes (tolerable now that blocks cache). Watch; the lever is block thinking-budget / size if it regresses.
- **D — data hygiene:** `unknown discipline_category` for D-015 (Navigation) + D-008 (Cycling), and `sport_locale_incompatible_D-008_home`. Layer 0/2 discipline-category + locale-compat data.
