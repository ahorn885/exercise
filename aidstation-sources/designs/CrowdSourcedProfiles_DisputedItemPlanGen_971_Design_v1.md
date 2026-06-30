# Crowd-Sourced Gym/Hotel Profiles (#971) — Disputed Item ⇒ Not-Available for Plan-Gen — Design v1

**Date:** 2026-06-30
**Status:** DESIGN — BUILD-READY. Two design forks ratified by Andy (2026-06-30, AskUserQuestion): **(1) plan-gen-only subtraction**; **(2) lazy / next-regen invalidation**. The core treatment ("a disputed item is not-available for plan generation") was approved earlier (Andy 2026-06-29, D-60 §5).
**Origin:** the committed next step from the #971 Slice-3 closing handoff §6.1 — the last remaining #971 piece after Slices 1 (name+geo dedup), 2 (photos), 3 (admin review) shipped.
**Issue:** [#971](https://github.com/ahorn885/exercise/issues/971).
**Cross-layer:** touches Layer 2C's `locale_equipment_pool` input contract (stop-and-ask trigger #3). Layer2C_Spec §3/§12 carry a cross-ref to this doc.

---

## 1. Purpose

When a peer flags a shared gym/hotel profile as wrong (Slice 3), the correction is stashed as an open proposal on `gym_profiles.disputed_items` — a JSON list of `{by, adds, removes, at}` objects. Until an admin reviews it, the proposal is **provisional**: the shared profile still carries the disputed tag, so every *other* athlete inheriting that profile keeps getting plans built around a tag a peer says isn't really there.

D-60 §5 pins the intended treatment: **a disputed item is not-available for plan generation.** This slice derives the disputed-tag set from the open proposals and subtracts it from the equipment pool Layer 2C resolves against, for all inheritors, while the dispute is open.

## 2. What this does NOT do

- **Does not touch the athlete's locale UI or references view.** The athlete still sees the real shared equipment set on their locale form (fork 1 = plan-gen-only). Only plan generation treats the tag as gone.
- **Does not handle disputed *adds*.** A proposal's `adds` are tags a peer claims the gym *has* but the shared profile lacks. Those aren't in the shared set until an admin approves them, so they never drive plan-gen — no handling needed. Only `removes` matter here.
- **Does not proactively refresh live plans** (fork 2 = lazy). Filing or withdrawing a dispute does not evict anyone's caches. The content-addressed 2C cache key changes when the pool changes, so the disputed tag drops out at each inheritor's *next* natural plan create / refresh / single-session synthesis.
- **Does not change Layer 2C's internal algorithm.** 2C is unchanged; only the upstream pool construction in `locations.py` changes.
- **Does not special-case the proposer.** Slice 3 already writes the proposer's personal `locale_equipment_overrides` remove and evicts *their* 2C cache on save, so their plan already excludes the tag. This slice is about the *other* inheritors.

## 3. The seam

`locations.py` is the single authoritative chokepoint for "what equipment is effective at a locale." Every plan-gen path resolves through `locale_effective_tags()`:

| Caller | Path | Disputed-aware? |
|---|---|---|
| `orchestrator.py:1218` (2C payload per-locale pool) | plan-gen | **yes** |
| `orchestrator.py:2313` (`locale_equipment` cache-key bundle) | plan-gen | **yes** |
| `_q_locale_equipment_pool` (`orchestrator.py:2345`, single-session) | plan-gen | **yes** |
| `cluster_effective_tags` (locations.py) | plan-gen union (no live caller today; documented 2C pool) | **yes** |
| `cluster_equipment_by_locale` (locations.py) | plan-gen feasibility routing | **yes** |
| `routes/locales.py:977` / `:1196` | locale UI + override-diff save | no (UI) |
| `routes/references.py:45` | references view | no (UI) |
| `coaching.py:309` | legacy v1 coaching (one-shot Claude call) | no (not v2 plan-gen) |
| `locale_assumed_baseline_display` (locations.py) | UI overlay | no (UI) |

A new `exclude_disputed: bool = False` parameter on `locale_effective_tags` keeps every UI / save / legacy caller byte-identical (they take the default) and is passed `True` only from the five plan-gen callsites.

## 4. Algorithm

`locale_effective_tags` today resolves `(shared ∪ adds) − removes`. With `exclude_disputed=True`:

```
disputed = union of open-proposal `removes` on the linked gym_profiles.disputed_items
effective = ((shared − disputed) ∪ adds) − removes
```

**Subtract disputed from `shared` only — not from `adds`.** An athlete who *personally* added the tag via their own override has explicitly affirmed it; their personal override is authoritative for them and wins over a peer's provisional dispute. (`(shared − disputed) ∪ adds` lets a personal add re-introduce a tag a peer disputed.)

New helper `disputed_equipment_tags(db, gym_profile_id) -> set[str]`: SELECT `disputed_items`, parse the JSON tolerantly (mirrors the existing inline `equipment` parse — NULL/empty/malformed → `set()`), return the union of every open proposal's `removes` (string entries only). Lives in `locations.py` (a pure domain module, no route imports — avoids a circular import with `routes/locales`).

`locale_effective_tags` only issues the extra `disputed_items` query when `exclude_disputed=True` **and** the locale links a `gym_profile_id`, so the UI path adds zero queries.

**Rule #15 instrumentation:** when `exclude_disputed=True` and disputed tags actually subtract something, log `user_id`, `locale`, the disputed set, and the count removed, so a "why did the plan stop prescribing X" question is answerable from `/admin/logs` alone.

## 5. Invalidation / caching (fork 2 = lazy)

The 2C cache is content-addressed — `locale_equipment_pool` is hashed into the cache key (`cached_wrappers._layer2c_bundle_hash` / `compute_payload_hash`), and `orchestrator.py:2313` folds the per-locale effective tags into the plan-gen cache-key bundle. Because both of those now exclude disputed tags, the hash changes the moment a dispute is filed or withdrawn → the next plan op for any inheritor misses the stale entry and re-derives with the disputed-adjusted pool. **No explicit eviction code is added.**

What lazy gives up: a disputed tag keeps driving an inheritor's *already-generated* live plan until that plan's next natural refresh. Accepted deliberately — a dispute is a soft, unreviewed signal from a single peer; churning every inheritor's live plan on one flag is the wrong default (fork 2, Andy 2026-06-30).

Admin resolution is a separate, already-correct path: **approve** folds the `removes` into the shared `gym_profiles.equipment` (Slice 3 `_apply_profile_edit`), so the disputed entry disappears and the pool returns to the new shared truth; **reject** drops the proposal, so `disputed_equipment_tags` returns `∅` and the tag is back in the pool. Both flow through the same content-hash mechanism.

## 6. Edge cases

| Case | Behavior |
|---|---|
| Locale links no gym_profile | No `disputed_items` to read; `disputed_equipment_tags` short-circuits via the `gym_profile_id` guard → `∅`; pool unchanged. |
| `disputed_items` NULL / empty / malformed | Tolerant parse → `∅`; pool unchanged. |
| Disputed tag the athlete personally re-added (`adds`) | `(shared − disputed) ∪ adds` re-introduces it — personal affirmation wins. |
| Disputed tag the athlete personally already removed (`removes`) | Already gone; subtracting again is idempotent. |
| Two peers dispute different tags | Union of all open proposals' `removes` — every disputed tag is subtracted. |
| Proposal has only `adds`, empty `removes` | Contributes nothing to the disputed set; pool unchanged (see §2). |
| Private profile | No peer inherits it, so it carries no proposals (Slice 3 `_record_profile_edit` only records on `report` against a *shared* base); `disputed_items` stays NULL. |

## 7. Caching determinism

`disputed_equipment_tags` returns a `set`; the disputed subtraction happens before `locale_effective_tags`'s existing `sorted(...)` at the plan-gen callsites, so the pool remains deterministically ordered for the 2C cache-key hash. No new non-determinism.

## 8. Test scenarios (unit, `tests/test_locations.py`)

1. **Plan-gen excludes a disputed tag.** Shared profile has `{Barbell, Treadmill}`; an open proposal `removes=["Treadmill"]` by another peer. `locale_effective_tags(..., exclude_disputed=True)` → `{Barbell}`; `exclude_disputed=False` (default / UI) → `{Barbell, Treadmill}`.
2. **Personal add beats a peer dispute.** Same dispute, but this athlete has a personal `add` of `Treadmill`. `exclude_disputed=True` → `{Barbell, Treadmill}` (personal affirmation wins).
3. **Withdraw restores.** `disputed_items` cleared (proposal withdrawn) → `exclude_disputed=True` returns the full shared set again.
4. **No disputes / no profile.** `exclude_disputed=True` with `disputed_items` NULL or no linked profile == `exclude_disputed=False`. (Default path is unchanged.)
5. **`cluster_effective_tags` / `cluster_equipment_by_locale` exclude disputed** across a multi-locale cluster.
6. **`disputed_equipment_tags`** unit: union of open `removes`, tolerant of NULL/empty/malformed, `adds`-only proposals contribute nothing.

Plus: existing `test_locations.py` cases (no `disputed_items` seeded) stay green — the new param defaults to the old behavior.

## 9. Gut check

- **Risk: lazy invalidation surprises.** An inheritor whose plan was generated *before* a dispute keeps the disputed tag until their next refresh. Accepted per fork 2; if it bites, the upgrade path is a proactive cross-inheritor eviction (the rejected fork-2 option) — additive, no rework.
- **Risk: plan-gen vs UI divergence confuses support.** The athlete sees the tag in their locale UI but the plan doesn't use it. Mitigated by the Rule #15 log line (the subtraction is attributable) and by it being the *intended* D-60 semantics; an athlete-facing "under review" UI hint is a possible follow-up, out of scope here.
- **Best argument against:** disputed-tag subtraction at *plan-gen read time* (vs. materializing it) means the disputed set is recomputed each plan op. It's one indexed SELECT per locale on `gym_profiles.disputed_items` behind the `exclude_disputed` + `gym_profile_id` guards — negligible against the multi-minute plan-gen cone, and it keeps a single source of truth (no derived column to invalidate). Worth it.
- **What might be missing:** no admin-facing signal of how many inheritors a given open dispute is currently affecting. Not load-bearing for the treatment; notable as a possible moderation-UX follow-up.
