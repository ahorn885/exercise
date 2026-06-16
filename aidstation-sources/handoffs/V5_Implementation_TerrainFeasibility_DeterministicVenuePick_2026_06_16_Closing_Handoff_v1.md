# V5 Implementation — Terrain feasibility: deterministic venue pick (#624 + #618-7) — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/planview-polish-handoff-0yiak5` (main fix, merged via PR #635) → `claude/terrain-names-superseded-filter` (the `superseded_at` follow-up + this bookkeeping/handoff).
**PRs this session:** [#635](https://github.com/ahorn885/exercise/pull/635) (deterministic venue pick) — CI-green, auto-merged. [#636](https://github.com/ahorn885/exercise/pull/636) (follow-up: filter `_q_terrain_names` to active layer0 rows).
**Predecessor handoff:** `handoffs/V5_Implementation_PlanView_pv71_Polish_2026_06_15_Closing_Handoff_v1.md` (the pv=71 plan-view polish; this session is the **lead slice of the "Locations & Gear" arc** it teed up).

This session worked **#624** (the "no nearby groomed trail" plan-gen report) **investigation-first** (Rule #14) via the read-only `neon-query` workflow, and the data overturned the issue's premise — leading to a synthesis-grounding fix rather than a data fix.

---

## 1. What shipped

### Investigation (read-only `neon-query` vs prod) — premise overturned

pv=71 = user_id 1. Their saved locales + terrain tags (distances from the home locale, **509 Williams Avenue**, computed with the same haversine the cluster uses):

| Locale (slug) | Display name | Dist | In 42.2 km cluster | Groomed Trail (TRN-002)? |
|---|---|---|---|---|
| `509_williams_avenue` | 509 Williams Avenue *(home/preferred)* | 0 | ✅ anchor | ❌ (TRN-004 Hill/Rolling) |
| `lake_pat_cleburne` | Lake Pat Cleburne | ~6 km | ✅ | ❌ (water TRN-009) |
| `cleburne_state_park` | **Cleburne State Park** | **~18 km** | ✅ | ✅ **yes** |
| `chisenhall_mtb_trailhead` | Chisenhall Mtb Trailhead | ~19 km | ✅ | ✅ |
| `dinosaur_valley_state_park` | Dinosaur Valley State Park | ~40 km | ✅ | ✅ |
| `home_2` | The Horn's | ~42.3 km | ⚠️ borderline-out | ❌ |
| `river_legacy_parks` | River Legacy Parks | ~55 km | ❌ out | ✅ (out of cluster) |
| `home` / `hotel` | — | no coords | excluded | — |

**All three #624 hypotheses are negative.** Cleburne is **saved, in-cluster, and correctly tagged TRN-002** — no terrain-tagging gap, no radius/ranking miss. There is also **no public-venue discovery**: `locations.cluster_locale_ids` builds the candidate set purely from saved `locale_profiles`; the "Dinosaur Valley SP" recommendation was **LLM-invented from world knowledge**.

**Root cause = synthesis grounding.** The feasibility cascade handed the synthesizer **one locale slug** per discipline, and Trail Running (D-001 = any of TRN-002/003/004) resolved EXACT at *home* via TRN-004 (Hill/Rolling). With home offering only hills, the LLM editorialized "no nearby groomed trail" and named a park it knew. The same single-slug feed caused **#618-7** ("Williams" vs "509 Williams Avenue" — the LLM humanized the slug inconsistently).

### Fix — deterministic venue pick (Andy chose via `AskUserQuestion`; Trigger #1 prompt + Trigger #3 contract)

**PR #635** (`locations.py`, `layer4/session_feasibility.py`, `layer4/orchestrator.py`, `layer4/hashing.py` + 3 test files):
- **`locations.cluster_locale_ids`** now **haversine-sorts the cluster nearest-first** (home at 0 km, then ascending, slug tie-break) — wires the sort the resolver docstring long flagged as a stand-in, so "first satisfying locale" == nearest. New **`cluster_locale_meta`** → `{slug: {name, distance_km}}` (display name from `locale_profiles.locale_name`, distance via the existing `_haversine_km`).
- **`session_feasibility`**: `TerrainResolution` carries display fields (`locale_name`, `locale_distance_km`, `terrain_venues`); **`enrich_resolution_display`** (pure, orchestrator-applied via `dataclasses.replace`) attaches the scheduling locale's name+distance (every tier) and, for the **EXACT non-craft tier**, a **per-terrain nearest-venue menu** — each required terrain present in the cluster mapped to its NEAREST carrying locale, nearest-first. **`feasibility_line`** renders the menu by canonical terrain name + locale display name + distance and **bars naming any location not in the list**.
- **`orchestrator`**: `_gather_feasibility_inputs` gathers `cluster_locale_meta` + **`_q_terrain_names`** (reads `layer0.terrain_types` — the **DB**, never the frozen xlsx authoring); `_resolve_included_feasibility` enriches each resolution; away segments re-anchor the meta at the destination.
- **`hashing.LAYER4_PROMPT_REVISION` 3→4** so cached plans cold re-synthesize with the corrected line.

The synthesizer now sees, deterministically: *"real terrain in your saved locales — Groomed Trail at "Cleburne State Park" (18 km away); Technical Trail at "Cleburne State Park" (18 km away); Hill / Rolling at "509 Williams Avenue" (home). Train at these named locales only; never name a location not in this list."*

**PR #636** (`layer4/orchestrator.py`): the post-merge `neon-query` verification of `layer0.terrain_types` returned **70 rows for 5 ids** — the table keeps every superseded etl-version row, and `_q_terrain_names` read them unfiltered (resolving correctly only because `canonical_name` is stable across versions). Added the standard **`WHERE superseded_at IS NULL`** filter every other layer0 reader uses (`layer2b/builder._terrain_names`) so a future rename can't pick a stale name.

**Tests:** `tests/test_layer4_session_feasibility.py` (new `TestDeterministicVenueDisplay` — menu names the nearest venue per terrain, never the farther park; display name not slug; no TRN-id/slug leak), `tests/test_layer4_terrain_feasibility_wiring.py` + `tests/test_layer4_event_windows.py` (stub the two new readers in the cluster/away patches). **Full suite green: 2483 passed / 30 skipped. NO DDL.**

## 2. Deferred — the remaining #624 nuance (why it stays open)

The cascade still **collapses surface varieties**: TRN-002/003/004 are interchangeable for Trail Running, so a *home-hills* EXACT satisfies the discipline before groomed trail is ever weighed as the **scheduling** locale. The menu now *exposes* every real surface to the synthesizer (so it can't claim "none nearby" or invent a park), but the deterministic scheduler doesn't yet **prefer the matching specialized surface** (groomed trail at Cleburne) when a session's intent calls for it. **#624 is narrowed to that** — surface-specific within-discipline routing, a Layer-2C / feasibility-contract change (**Trigger #3**), not a data fix. Commented on the issue with the full data table + this scoping.

## 3. Bookkeeping done this session

- **GitHub issues** (the standard session-end step): **#618 CLOSED (completed)** — all 7 items shipped (items 1–6 via #632/#633, item 7 via #635); ticked the checklist with PR refs. **#624 narrowed** with the investigation data + the within-discipline surface-routing follow-up (stays open). PRs #635/#636 carry the cross-refs.
- **`CURRENT_STATE.md`** — new top "Last shipped session" entry (this work); demoted the pv=71 polish entry to a predecessor.
- **`CARRY_FORWARD.md`** — no edit: the next-step arc lives in GitHub issues (#622/#623/#619) and the #624 follow-up is narrowed on the issue.
- **Lesson (Andy, this session):** source vocab/reference names from the **`layer0` DB** (e.g. `layer0.terrain_types` via a versioned-row-filtered read), **never the frozen `etl/_frozen_xlsx_authoring/`** — that tree is history. The shipped code does this; the only frozen reference was a read during investigation (corrected).

## 4. NEXT STEPS — the "Locations & Gear" arc continues

The pv=71 walkthrough surfaced a cluster of location/gear issues; #624 + #618-7 (lead slice) shipped this session. Remaining:

- **Gear surface slice:** [#622](https://github.com/ahorn885/exercise/issues/622) (movable crafts — bikes/boats — still listed under Equipment on Locations → Gear; #586 split them into the craft store — verify the migration applied in prod via `neon-query`, then a render/route fix on the Gear picker) + [#623](https://github.com/ahorn885/exercise/issues/623) (retire "assumed" basic gear: backpack / headlamp / hiking boots / running shoes / trekking poles / wetsuit / swim cap & goggles / avalanche gear — **Trigger #2** vocab sign-off; **audit the 2C feasibility cascade first** so removing a gating item doesn't silently drop sessions).
- **UI/IA slice:** [#619](https://github.com/ahorn885/exercise/issues/619) (profile **Locations** tab + supplements/meds tab + sidebar rearrange + Sources 3-per-row + Schedule white bg).
- **#624 follow-up** (this session's deferral): within-discipline surface-specific routing (Trigger #3).

## 5. Owed / carried (unchanged)

- ⬜ **STILL OWED (carried):** the post-#572 live **T3 *refresh*** re-verify (Rule #14) — needs a live refresh on a real plan + the diag token. Unrelated to this session.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Cluster nearest-first sort | `locations.py` | `cluster_locale_ids` builds `within: list[tuple[float, str]]`, `within.sort(...)`, `ids.extend(...)` |
| Locale display meta | `locations.py` | `def cluster_locale_meta(` → `{name, distance_km}`; `_humanize_locale_slug` |
| Resolution display fields | `layer4/session_feasibility.py` | `TerrainResolution` has `locale_name` / `locale_distance_km` / `terrain_venues`; `def enrich_resolution_display(`; `def _venue_label(` |
| EXACT venue menu | `layer4/session_feasibility.py` | `feasibility_line` EXACT branch: `if resolution.terrain_venues:` → "Train at these named locales only; never name … a location not in this list" |
| Terrain names — DB, active rows | `layer4/orchestrator.py` | `def _q_terrain_names(` → `FROM layer0.terrain_types WHERE superseded_at IS NULL` |
| Orchestrator enrichment | `layer4/orchestrator.py` | `_FeasibilityInputs` has `locale_meta` / `terrain_names`; `_resolve_included_feasibility` calls `enrich_resolution_display(`; away site passes `locale_meta=locations.cluster_locale_meta(... anchor_locale=away_ov.away_locale)` |
| Cache bust | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "4"` |
| Tests | `tests/test_layer4_session_feasibility.py` | `class TestDeterministicVenueDisplay` — "Cleburne State Park", "18 km away", no `TRN-` / slug |
| Suite | — | 2483 passed / 30 skipped |
| Issues | #618 / #624 | #618 closed completed; #624 open, narrowed to within-discipline surface routing |
| Owed | — | T3-refresh re-verify carried |
