# Race-Location Terrain Inference — SUBORDINATE fallback under the race-URL parse — Build Spec v2

**Parent design:** the folded race-entry auto-fill spec, `designs/Race_URL_Parser_Spec_v1.md` (#256). **This is the build spec for GitHub [#592](https://github.com/ahorn885/exercise/issues/592).**
**Status:** **DESIGN-FIRST — NOT BUILT.** The terrain inference is a **new LLM call → Stop-and-ask Trigger #1**: its **prompt body wording is owed Andy's sign-off at build** (separate from the `RaceURLParser` prompt body, which covers the *site* parse). No build until §12 sign-off.
**Date:** 2026-06-21
**Supersedes:** `Race_Location_Terrain_Inference_Spec_v1.md` (archived). **What changed in v2 (Andy 2026-06-21):**
1. **Folded under #256 as the SUBORDINATE source.** The race-website parse (#256) is primary; this location inference runs **only as the fallback when the page didn't yield terrain**. It is no longer a standalone race-logging trigger.
2. **Persisted-suggestion column dropped.** v1 settled on a persisted `race_terrain_suggested` (+ `_at`) column; v2 makes the per-athlete suggestion **transient** (no column, no migration). Durable, cross-athlete repeated-race storage moved to **[#856](https://github.com/ahorn885/exercise/issues/856)**.
3. **Crowd tie-in moved to #856** (was §10 here).

---

## 1. Purpose + scope

When the athlete enters a **race location** *and the race-URL parse did not already supply terrain*, use an LLM call to infer the **general area's likely terrain**, then:
1. **Suggest in the UI** — pre-fill the (otherwise manual-only) race-terrain editor with an inferred breakdown the athlete reviews/edits, plus a plain-language *"this race likely has `<terrain>`; train for it"* nudge.
2. **Feed plan-gen** — once accepted/edited, it flows the **existing** `race_terrain → Layer 2B → orchestrator` path with **no plan-gen change**. This populates `race_terrain`, which is manual-only absent a suggestion.

**Subordinate by design (the v2 fold).** This is the **terrain backfill** for the race-entry auto-fill flow: the site parse (`RaceURLParser`) runs first and, when the page describes the course, fills `race_terrain` directly. This inference fires **only on the terrain gap** — page parse returned no terrain (or none in vocab) — and only when the location resolved to coordinates. If the page had terrain, this call **does not run** (precedence). See `Race_URL_Parser_Spec_v1.md` §4.4.

**Weather stays always-on + deterministic.** `weather_client.get_expected_conditions()` (`weather_client.py:36`, Open-Meteo climate normals from coords + date) already exists and is consumed by `race_week_brief.py`. The fold surfaces those existing normals at race-logging time as the "train for these conditions" half of the nudge — regardless of whether terrain came from the page or this fallback (a race page won't carry climate normals). **No new weather inference is built.**

**In scope:** the single-call LLM terrain inference (`record_race_terrain_inference`); the fallback hook in the race-entry auto-fill flow that runs it on the terrain gap; the pre-fill of `_race_terrain_editor.html` + the terrain+conditions nudge; reuse of `get_expected_conditions`; validation against the Layer-0 terrain vocabulary (reuse Layer 2B's TRN pattern + `layer0.terrain_types`); a cache key so re-inferring the same location is skipped.

**Out of scope:** any change to how plan-gen *consumes* `race_terrain` (unchanged); a live forecast (climate normals only); **durable cross-athlete storage / the crowd-sourced shared race-profile (→ #856)**; auto-committing inferred terrain without athlete review; the *site* parse itself (#256 / `RaceURLParser`).

**Success criteria:**
- (a) On the terrain gap, entering a race location surfaces an inferred breakdown (valid TRN-xxx ids, pct ~sums 100) the athlete can accept/edit/reject.
- (b) Accepted terrain persists to `race_events.race_terrain` and feeds Layer 2B unchanged (byte-identical downstream to a manual or page-parsed identical breakdown).
- (c) The conditions nudge shows the existing climate normals for the location+date at logging time.
- (d) Inference failure (LLM error, no coords, off-vocab) degrades gracefully → the athlete sees the empty manual editor (today's behavior). Never blocks race logging.
- (e) Re-saving an unchanged location does not re-invoke the LLM (keyed).
- (f) **Precedence:** when the page parse already supplied terrain, this inference does not run.

---

## 2. Boundaries

- **Subordinate to the site parse.** Runs only on the terrain gap (criterion f). Never overrides page-parsed terrain.
- **Suggestion, not authority.** The inference *pre-fills* the manual editor; the athlete confirms. Adventure-race terrain guesses are exactly where the model is least certain (AR venues change year-to-year), so the human review gate is load-bearing.
- **Best-effort, never blocking.** Like `get_expected_conditions`, any failure falls back to the empty manual editor. Race logging never depends on it (criterion d).
- **No plan-gen surface change.** Downstream (Layer 2B, orchestrator cone, race-week brief) is untouched — it already reads `race_terrain`. This ends at populating that field.
- **Trigger #1.** The inference prompt body is owed Andy's sign-off (§12); this spec fixes the I/O contract, inputs, validation, and intent.

---

## 3. Data model

**No new table, no new column, no migration.** The inference writes a **transient** suggestion — it pre-fills the terrain editor in the same session and is gone once the athlete saves (or leaves). Accepted terrain lands in the existing `race_events.race_terrain JSONB` (`init_db.py:1480`, typed `list[RaceTerrainEntry]` — `terrain_id` / `pct_of_race` / optional `discipline_id`, `layer4/context.py:290`) via the existing save path — exactly as a manual entry or a page-parsed accept.

**v2 change — the persisted `race_terrain_suggested` column is NOT built.** v1 added it so the suggestion survived to a later review and seeded the crowd path. Under the fold, the suggestion is reviewed in the session it's produced (transient), and the durable cross-athlete store is **#856**. The "don't re-invoke" guarantee (criterion e) is met by the §6 input-hash cache, not a persisted column. This drops the onboarding-critical-path schema change v1 carried.

---

## 4. The inference call (Trigger #1 — structure spec'd, body owed sign-off)

A single tool-call inference mirroring the established harness (`llm_invocation.invoke_tool_call` + capped retry + `ThinkingToolCallError`, `llm_invocation.py:50`; caller/exception-mapping per the `layer3b/builder` pattern).

**Inputs (all on the race record by the time this fires):** race `name`, location (`event_locale_name`, `event_locale_place_name`, `event_locale_lat/lng`), `distance_km`, `total_elevation_gain_m`, `race_format`, free-text `notes`/`race_url` context, `event_date` (season), the race's **discipline set** (from the Layer 2A discipline mix where available, else `race_format`/notes — and the athlete's just-picked event from the distance chooser scopes this), and the **Layer-0 terrain vocabulary** (valid `TRN-xxx` ids + names from `layer0.terrain_types`).

**Output tool schema — `record_race_terrain_inference` (per-discipline breakdown):**
- `terrain_breakdown: [{ discipline_id: str, terrain_id: "TRN-\d{3}", pct_of_race: 0–100, rationale: str }]` — each entry scoped to a discipline (populates the optional `RaceTerrainEntry.discipline_id`). Single-discipline race → every entry carries that one discipline.
- `confidence: "high" | "medium" | "low"` (low expected for AR/unstable venues — drives UI framing).
- `summary: str` — the one-line coaching nudge, project voice (direct, no hype).

**Validation (reuse Layer 2B's):** every `terrain_id` matches `TRN-\d{3}` and exists in `layer0.terrain_types`; every `discipline_id` is one of the race's disciplines; `pct_of_race ∈ [0,100]`; per-discipline pct sum ∈ [80,120]. Off-vocab/unknown-discipline/out-of-bounds → inference failure → empty editor (criterion d). Capped retry (cap=2) on a schema-violation tool call.

**Weather:** call the **existing** `get_expected_conditions(lat, lng, event_date)` alongside; render `summary_line()` as the conditions half of the nudge. Deterministic reuse, not part of the LLM call, always-on regardless of terrain source.

---

## 5. Trigger point + UI

- **Trigger:** the **terrain-gap fallback step of the race-entry auto-fill flow** (`Race_URL_Parser_Spec_v1.md` §4.4), reached after the site parse + the athlete's event pick when `race_terrain` is still empty and coordinates resolved. It is no longer a standalone race-logging trigger; the unified flow owns the trigger. Synchronous best-effort or deferred to editor render — TBD by latency (§12); either way non-blocking (criterion d).
- **Surface:** `_race_terrain_editor.html` renders **pre-filled** from the suggestion, each row tagged *"suggested — review"*, with confidence framing (low-confidence → stronger "verify this") and the terrain+conditions nudge banner above it. The athlete edits/accepts/clears exactly as today; accept writes `race_terrain` through the existing path. This is the same editor the page-parse pre-fills — a single surface, two possible upstream sources (page primary, this inference subordinate).

---

## 6. Caching / invalidation

- **Don't re-invoke:** key on the location inputs (`mapbox_id` or rounded `lat/lng` + `event_date` season + `distance`/`elevation`/`format`). A stored input-hash means a re-save with unchanged inputs skips the call (criterion e); changing the location re-infers. **The key is the dedup mechanism now that the persisted-suggestion column is gone (§3).**
- **Downstream invalidation unchanged:** once accepted into `race_terrain`, the existing race-event/Layer-2B cache invalidation applies. The transient suggestion never participates in plan keys.

---

## 7. Rule #15 logging
At inference: `race_terrain_inference: race=<id> loc=<place_name>@<lat,lng> conf=<high|med|low> terrain=[TRN-xxx:pct,...] sum=<pct> retries=<n> | weather=<summary_line|none>` — plus failure cause on the degrade path (`fallback: <no_coords|llm_error:CODE|off_vocab:TRN-xxx|pct_sum=NN>`) and the **skip reason when precedence applies** (`skipped: page_terrain_present`). So a wrong/absent/skipped suggestion is diagnosable from logs alone, including *why* terrain came from the page vs the inference.

---

## 8. Edge cases
- **Page parse already supplied terrain** → this inference **does not run** (precedence, criterion f). Logged `skipped: page_terrain_present`.
- **No coordinates** → skip inference + weather; empty editor. Logged `fallback: no_coords`.
- **Standardized race** (Boston) → high confidence; #856 is where these converge across athletes.
- **Adventure race** (changes yearly) → low confidence; UI frames "starting point, verify." Most valuable (no per-venue data) and least certain — the review gate matters most here.
- **Multi-discipline race** → terrain scoped per discipline via `discipline_id`; each discipline's entries sum ~100 independently. Single-discipline is the degenerate case.
- **LLM off-vocab / pct way off** → inference failure → empty editor (never persist garbage). Logged.
- **Athlete already entered terrain** (manually or via the page parse) → no suggestion overwrite; the inference only fires on empty/unconfirmed terrain.

---

## 9. Test scenarios
1. Terrain gap (page had none) + coords → inference returns a valid breakdown (TRN in vocab, pct ~100), high confidence; editor pre-fills; accept → `race_terrain` populated; Layer 2B output identical to the same manual entry. *(a, b)*
2. AR race, low confidence → editor pre-fills with "verify" framing; athlete edits → edited values persist. *(a)*
3. **Page parse supplied terrain** → inference skipped; `skipped: page_terrain_present` logged. *(f)*
4. No coords → no inference, empty editor, race still logs. *(d)*
5. LLM error / off-vocab → graceful fallback to empty editor; `fallback:` logged. *(d)*
6. Conditions nudge shows `get_expected_conditions` normals for location+date. *(c)*
7. Re-save unchanged location → no second LLM call (keyed). *(e)*
8. Rule #15 `race_terrain_inference` line present + correct (inputs, breakdown, weather, failure/skip cause).

---

## 10. Relationship to #256 and #856
- **#256 (primary).** The `RaceURLParser` site parse fills `race_terrain` directly when the page describes the course; this inference is its subordinate fallback. Single target field (`race_terrain`), page-wins precedence — no write conflict.
- **#856 (durable data).** The crowd-sourced shared race-profile convergence — the strategic frame v1 carried in its §10 — is now **#856**: parsed/inferred/athlete-confirmed terrain keyed on race identity, accumulating across athletes for standardized races (differentiator #8). v2 stays **per-athlete + transient**; #856 owns aggregation.

## 11. Why this is small
The race model, the manual terrain editor, the LLM harness, the terrain vocabulary + 2B validation, the weather client, and the entire downstream consumption **all exist**. The new pieces are one LLM inference call (§4), the terrain-gap fallback hook in the auto-fill flow (§5), and the §6 input-hash key. Plan-gen is untouched. **v2 is even smaller than v1 — the persisted column is gone.**

## 12. Open items / sign-off
- **Trigger #1 — PROMPT BODY OWED (Andy).** §4 fixes inputs / output schema / validation / intent; the prompt wording needs sign-off before build.
- **Fold / subordinate role — SETTLED (Andy 2026-06-21).** Spec'd.
- **Storage — SETTLED (Andy 2026-06-21):** transient; persisted column dropped; durable store → #856. Spec'd (§3).
- **Per-discipline terrain — SETTLED:** breakdown scoped per `discipline_id`, pct ~100 within each. Spec'd (§4/§8).
- **Trigger timing — DECISION OWED:** sync-at-save (short timeout) vs lazy-at-editor-render — both non-blocking (§5).

## 13. Gut check
- **Best argument against:** terrain is a small manual entry today, and the fold means this only fires on the gap the page didn't fill — so for standardized races (clean pages) it may rarely run, and for AR races (its best case) it's least certain. It earns its keep as the **terrain backfill** that keeps the auto-fill flow yielding terrain even when the page is thin, and as the **cold-start signal** for #856.
- **Biggest risk:** a confidently-wrong low-confidence suggestion the athlete rubber-stamps → the plan trains for the wrong terrain. Mitigations: the review gate, explicit low-confidence framing, precedence (page wins when available), and Rule #15 logging of suggested-vs-accepted. The conditions half is safe (deterministic normals).
- **What's genuinely clean:** scoping it as a *subordinate middle step that only populates `race_terrain`* means zero plan-gen risk; dropping the persisted column removes the only schema change v1 put on the onboarding path.
- **What might be missing:** the precedence handoff (page-terrain vs gap) must be unambiguous in the orchestration so this never double-writes or overrides — the `skipped: page_terrain_present` log line (§7) is the guard that it's working.

---

*End of Race_Location_Terrain_Inference_Spec_v2.md.*
