# Provider Translation — Garmin FIT strength name → layer0 EX-id (#679, Slice D of #430) — Design v1

**Status:** RATIFIED v1 (Andy, 2026-06-17). Design ratified; **build deferred to a dedicated next session** (Andy's call). New Garmin-derived EX-id candidates are ratified in **one consolidated batch at the end** of the build (not per-entry — Andy, 2026-06-17). The first concrete **inbound** slice of the provider data translation layer (`Provider_Data_Translation_Layer_Spec` §6.1). Spec/design only — no code ships from this doc.
**Type:** Build design (data-mapping). Sits on the EX-id single-source-of-truth (#335, CLOSED) and the rx write-path FK cutover (#430 Slice C, MERGED — PR #676/#677/#678).
**Date:** 2026-06-17
**Predecessor:** #430 Slice C made the rx write path key off the layer0 EX-id; this slice is how an arbitrary Garmin FIT exercise name *reaches* an EX-id (or gets recorded when it can't).
**Cross-refs:** `Provider_Data_Translation_Layer_Spec` (§4.2 value-map table, §6.1 strength seed, §6.4 bucket-3, §7 authoring), `rx_engine_spec.md`, `Catalog_Migration_Plan_v3.md` (fuzzy + HITL pattern).

---

## 1. Problem (measured, from #679)

After #430 Slice C the rx write path keys off the layer0 EX-id, but **resolving a Garmin FIT upload's exercise name to an EX-id is still limited**, so most Garmin-logged strength lifts land as `first_exposure` and never surface as capacity-derived loads in plan-gen — defeating the original #335 goal for the athlete who dogfoods via Garmin.

The gap, measured:
- `garmin_fit_parser._exercise_name` can emit **~1,261** distinct names (`_EXERCISE_CATEGORY_MAP` 33 categories + the dynamically-built `_EXERCISE_SUBTYPE_MAP`), and **prefers the specific subtype** — a watch-logged squat arrives as `"Barbell Back Squat"` (1 of 92 squat subtypes), not `"Squat"`.
- `layer0_progression.NAME_TO_EX_ID` has **20** entries; only **14** exactly match a FIT name, and those are the **coarse category** names (`Squat`, `Bench Press`, `Curl`, `Row`, `Deadlift`, `Pull Up`, `Push Up`, `Plank`, `Sit Up`, `Lateral Raise`, `Triceps Extension`, `Goblet Squat`, `Dead Bug`, `Side Plank`).
- So a FIT upload resolves only when the file emits a coarse category name or the athlete already has a backfilled `current_rx` row for that exact name. The common specific-subtype case → no EX-id → **`first_exposure`** (a NULL-EX-id `current_rx` row).
- `layer0.exercises` has ~249 (`EX001`–`EX249`) equipment-**qualified** names (`Back Squat (Barbell)`) that align well with Garmin's specifics — so the mapping is tractable.

---

## 2. Decisions (proposed — Andy to ratify)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | **Resolution point** | **`rx_engine.apply_session_outcome` EX-id step** (`rx_engine.py:~205`), not resolve-at-parse. | It's the **single chokepoint** all 3 log routes pass through (`routes/training.py` manual + synthesized; `routes/garmin.py` FIT manual/auto/circuit). Resolving here self-heals on the UPSERT and covers manual logs too, not just FIT. The FIT parser still produces the *name*; this step maps name→EX-id. |
| 2 | **Mapping mechanism** | **Fuzzy + HITL alias map**, high-frequency-first, preserving specificity. | The `Catalog_Migration_Plan_v3.md` Phase-1 pattern (`rapidfuzz` offline + Andy sign-off). `Barbell Back Squat` → the barbell-back-squat EX-id, **not** collapsed to generic Squat. |
| 3 | **Storage of the map** | Author as the **strength rows of `provider_value_map`** (translation spec §4.2: `provider='garmin', data_type='strength', direction='in'`); generalizes today's curated `NAME_TO_EX_ID`. | Aligns the first slice with the layer's schema instead of growing another bespoke dict. (If the table isn't built when #679 ships, an expanded in-code seed is the interim, migrated into the table — call this out at build.) |
| 4 | **Fallback** | **Category-collapse, through the name, as a backstop only** (cat 28 → `"Squat"` → `EX001`). | There is no direct category→EX-id map; the coarse name already routes via the map. Used only when no specific alias exists — never the default (preserves specificity). |
| 5 | **No match → bucket-3** | Record + **surface inline** in completed as "logged, not prescribed" (NULL EX-id), an **explicit** state. | Replaces the ambiguous `first_exposure` rendering with an intentional record-don't-drop signal (translation spec §6.4). |
| 6 | **New EX-ids** | **Identify candidates, do not pad**; ratify in **one consolidated batch at the end** of the build (Andy, 2026-06-17 — not per-entry). | Precedent: EX246–EX249 (migration `0011`, ratified 2026-06-16). A common Garmin specific with no layer0 home is a candidate add, not an auto-insert; author the whole alias map, then bring Andy one list. |

---

## 3. Approach

### 3.1 The resolution chain (at `apply_session_outcome`)

Today (line ~205):
```python
layer0_exercise_id = (rx['layer0_exercise_id'] if rx else None) or NAME_TO_EX_ID.get(exercise)
```
Proposed (additive, no regression to the #430 path):
```
layer0_exercise_id =
    rx['layer0_exercise_id']                       # 1. already-backfilled EX-id on the row (unchanged)
    or strength_alias_lookup(exercise)             # 2. NEW: fuzzy-authored alias map (provider_value_map strength rows)
    or category_collapse_to_ex_id(exercise)        # 3. backstop: coarse category name → EX-id (cat 28 → "Squat" → EX001)
    or None                                         # 4. record-don't-drop → bucket-3 (explicit), surfaced in completed
```
Step 2 supersedes the bare `NAME_TO_EX_ID.get`; the curated 20 entries fold into the authored alias set. Step 4's `None` is the same value the code writes today (so the legacy `exercise_inventory.movement_pattern` fallback path is preserved), but the **completed-history record is tagged `prescribed=false` + provider** so it surfaces intentionally rather than as an ambiguous `first_exposure`.

### 3.2 Map authoring (offline, HITL)

1. Enumerate the Garmin name space the parser can emit (`_EXERCISE_CATEGORY_MAP` × `_EXERCISE_SUBTYPE_MAP`).
2. Enumerate the ~249 layer0 qualified names (`layer0.exercises`).
3. **`rapidfuzz`** candidate match (new dependency — only `difflib` exists today, in ETL validation; add `rapidfuzz` to `requirements.txt` at build). **High-frequency-first:** prioritize the names that actually appear in Andy's Garmin history.
4. **Andy HITL** confirms/edits; record `match_kind` (`exact`/`fuzzy`/`manual`) + `confidence`.
5. Commit as seed (the strength rows of `provider_value_map`).

### 3.3 Specificity vs collapse

`Barbell Back Squat` must map to the barbell-back-squat EX-id when one exists; only if no specific alias is authored does the category-collapse backstop route it via the coarse `"Squat"` → `EX001`. The backstop guarantees *something* resolves for common categories without silently flattening specificity for mapped names.

---

## 4. Record-don't-drop signal (bucket-3)

Define the explicit state to replace the ambiguous `first_exposure`:
- A completed strength record with no resolved EX-id is stored with `prescribed=false`, `provider='garmin'`, the raw FIT name retained (`provider_raw_record`), `canonical_ref=NULL`.
- It surfaces **inline** in completed history, flagged "logged, not prescribed" (UI build = `Bucket3_InlineCompleted_Surfacing_Design`, later wave; this slice fixes the data contract + the resolution outcome).
- It remains eligible to *become* mapped later (author an alias → next ingest resolves it), with no data loss in the meantime.

---

## 5. New-EX-id policy (Trigger #2)

During authoring, Garmin specifics that are common and legitimate but have **no** layer0 home are collected as **candidate** new EX-ids and flagged for Andy — never auto-added (strict no-padding rule). The bar: no existing EX-id covers the same physical stimulus/technique/injury profile. Precedent: EX246–EX249. Until ratified, the value resolves to bucket-3 (record-don't-drop), not a forced near-match.

---

## 6. Tests

- **Extend `tests/test_rx_engine_apply_outcome_layer0.py`:** a specific-subtype FIT name (`"Barbell Back Squat"`) resolves to the specific EX-id via the alias step (not collapsed); a coarse name still resolves via category-collapse; an unmapped legitimate name resolves to `None` **and** yields the explicit bucket-3 tag (not a silent `first_exposure`); the #430 COALESCE preserve-existing-EX-id path is unchanged.
- **Extend `tests/test_garmin_fit_parser_strength.py`:** the parser still emits the subtype-preferred name the resolver expects (guards the name contract the alias map is authored against).
- **Instrumentation (Rule #15):** the resolution `print()` carries `exercise`, the step that resolved it (alias/collapse/none), resolved EX-id or bucket, `match_kind`, `confidence` — so a prod miss says which name, which step, which bucket.

---

## 7. Open questions for Andy (carried into the build session)
1. **Authoring scope for v1:** map only the high-frequency names in your Garmin history first (recommended), or attempt the full ~1,261 up front? (Recommend incremental, frequency-first.)
2. **Interim vs table:** if `provider_value_map` (translation spec §4.2) isn't built when #679 ships, OK to ship the alias set as an expanded in-code seed and migrate it into the table later? (Recommend yes — keeps #679 shippable independently.)
3. **Candidate new EX-ids — RESOLVED (Andy, 2026-06-17):** ratify in **one consolidated batch at the end** of the build, not per-entry.

---

## 8. Gut check
- **Biggest risk:** fuzzy authoring mismaps a specific lift to the wrong EX-id, corrupting capacity → bad loads. Mitigation: HITL sign-off on every fuzzy row; `confidence` recorded; category-collapse only as an explicit backstop; bucket-3 (record-don't-drop) is the safe default over a forced near-match.
- **Best argument against resolving at `apply_session_outcome`:** the parser "knows" the Garmin category/subtype that the name was derived from, so resolving at parse could use the enum directly instead of re-matching a string. Counter: the chokepoint covers manual logs too and self-heals on write; we can still pass through category/subtype as a hint if needed without moving the resolution point.
- **Did I preserve the #430 contract?** Yes — step 1 (existing backfilled EX-id) and the `None` fallback are unchanged; the new steps only fill the gap between them.
