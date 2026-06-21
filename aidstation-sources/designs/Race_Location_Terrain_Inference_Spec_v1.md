# Race-Location Terrain/Weather Inference — UI suggestion + plan-gen feed — Build Spec v1

**Parent design:** `designs/Event_Windows_Design_v1.md` (F-race split this out as its own track — a race location is a *target*, not a training environment). **This is the build spec for GitHub [#592](https://github.com/ahorn885/exercise/issues/592).**
**Status:** **DESIGN-FIRST — NOT BUILT.** Scoped per Andy 2026-06-21 (design-specs-first this session). The terrain inference is a **new LLM call → Stop-and-ask Trigger #1**: the prompt **structure + I/O contract** are spec'd here; the **prompt body wording is owed Andy's sign-off at build** (matches the Slice-1 Trigger-#1 treatment). No build until §12 sign-off.
**Date:** 2026-06-21

---

## 1. Purpose + scope

When the athlete enters a **race location**, use an LLM call to infer the **general area's likely terrain**, then:
1. **Suggest in the UI** — pre-fill the (today manual-only) race-terrain editor with an inferred terrain breakdown the athlete reviews/edits, plus a plain-language *"this race likely has `<terrain>`; you should train for it"* nudge.
2. **Feed plan-gen** — once the athlete accepts/edits the suggestion, it flows through the **existing** `race_terrain → Layer 2B → orchestrator` path with **no plan-gen change**. 592 simply *populates* `race_terrain`, which is manual-only today.

**The carve (why this is small):** terrain inference is a **new middle step between the race-logging UI and the existing Layer-2B consumption** — not a plan-gen change. And **weather is already solved**: `weather_client.get_expected_conditions()` (`weather_client.py:36`, Open-Meteo climate normals from coords + date) already exists and is already consumed by `race_week_brief.py`. 592's weather contribution is only to **surface those existing normals at race-logging time** (today they appear only at the race-week brief, ~14 days out), as the "train for these conditions" half of the nudge. **No new weather inference is built.**

**In scope:** a single-call LLM terrain inference (`record_race_terrain_inference`); a race-logging-time trigger that runs it and stores the result as a **suggestion** (not auto-committed); the UI surface that pre-fills `_race_terrain_editor.html` + shows the terrain+conditions nudge; reuse of `get_expected_conditions` at logging time; validation against the Layer-0 terrain vocabulary (reuse Layer 2B's TRN pattern + `layer0.terrain_types`); a cache key so re-logging the same location doesn't re-call.

**Out of scope:** any change to how plan-gen *consumes* `race_terrain` (unchanged); a live forecast (climate normals only — already the house approach); the crowd-sourced shared race-profile convergence (noted as the future tie-in, §10, differentiator #8 — **not built in v1**); auto-committing inferred terrain without athlete review.

**Success criteria:**
- (a) Entering a race location surfaces an inferred terrain breakdown (valid TRN-xxx ids, pct ~sums 100) the athlete can accept/edit/reject.
- (b) Accepted terrain persists to `race_events.race_terrain` and feeds Layer 2B unchanged (byte-identical downstream to a manually-entered identical breakdown).
- (c) The conditions nudge shows the existing climate normals for the location+date at logging time.
- (d) Inference failure (LLM error, no coords, off-vocabulary output) degrades gracefully → the athlete just sees the empty manual editor (today's behavior). Never blocks race logging.
- (e) Re-saving an unchanged location does not re-invoke the LLM (keyed).

---

## 2. Boundaries

- **Suggestion, not authority.** The inference *pre-fills* the manual editor; the athlete confirms. Adventure-race terrain guesses are exactly where the model is least certain (the issue's point: AR venues change year-to-year and have no stable per-venue data), so the human review gate is load-bearing, not optional.
- **Best-effort, never blocking.** Like `get_expected_conditions`, the inference is best-effort — any failure falls back to the empty manual editor. Race logging never depends on it (criterion (d)).
- **No plan-gen surface change.** Downstream (Layer 2B gap analysis, orchestrator cone, race-week brief) is untouched — it already reads `race_terrain`. 592 ends at populating that field.
- **Trigger #1.** The inference prompt is a new LLM prompt → its body wording is owed Andy's sign-off (§12); this spec fixes the I/O contract, inputs, validation, and intent only.

---

## 3. Data model

**No new table.** Reuse `race_events` (`init_db.py:1378–1430`): location is already Mapbox-anchored (`event_locale_name/_mapbox_id/_place_name/_lat/_lng`) and terrain already lives in `race_terrain JSONB` (`init_db.py:1403`, typed as `list[RaceTerrainEntry]` — `terrain_id` / `pct_of_race` / optional `discipline_id`, `layer4/context.py:290`).

The inference **writes a suggestion**, not the committed field. Two storage options (open item §12):
- **(A) Transient suggestion** — compute on demand at the editor render, never persisted; the athlete's accept writes `race_terrain` exactly as a manual entry would. Simplest; re-renders re-call unless cached (§6).
- **(B) Persisted suggestion column** — add `race_terrain_suggested JSONB NULL` + `race_terrain_suggested_at TIMESTAMP NULL` so the suggestion is stored once, shown until the athlete acts, and never re-called. Costs one idempotent ALTER.
- **Recommendation: (B)** — it makes the "don't re-invoke" guarantee (criterion (e)) trivial and persists the inference rationale for the crowd-sourcing tie-in later (§10). One small ALTER; no plan-gen contract touched (suggestion column is read only by the editor).

---

## 4. The inference call (Trigger #1 — structure spec'd, body owed sign-off)

A single tool-call inference, mirroring the established harness (`llm_invocation.invoke_tool_call` + capped retry + `ThinkingToolCallError`, `llm_invocation.py:50`; caller/exception-mapping pattern as `layer3b/builder.py:180`).

**Inputs (all already on the race record):** race `name`, location (`event_locale_name`, `event_locale_place_name`, `event_locale_lat/lng`), `distance_km`, `total_elevation_gain_m`, `race_format`, free-text `notes`/`race_url` context, `event_date` (season), and **the Layer-0 terrain vocabulary** (the valid `TRN-xxx` ids + display names from `layer0.terrain_types`) so the model can only choose real ids.

**Output tool schema — `record_race_terrain_inference`:**
- `terrain_breakdown: [{ terrain_id: "TRN-\d{3}", pct_of_race: 0–100, rationale: str }]`
- `confidence: "high" | "medium" | "low"` (low expected for AR/unstable venues — drives UI framing)
- `summary: str` — the one-line coaching nudge ("this race is mostly technical singletrack with sustained climbing; train for it"), in the project coaching voice (direct, no hype).

**Validation (reuse Layer 2B's, `layer2b/builder.py`):** every `terrain_id` matches `TRN-\d{3}` and exists in `layer0.terrain_types`; `pct_of_race ∈ [0,100]`; sum ∈ [80,120] (the 2B bound). Off-vocabulary or out-of-bounds → treat as inference failure → empty editor (criterion (d)). Capped retry (cap=2, the house default) on a schema-violation tool call.

**Weather:** call the **existing** `get_expected_conditions(lat, lng, event_date)` (`weather_client.py`) alongside; render its `summary_line()` as the conditions half of the nudge. Not part of the LLM call — deterministic reuse.

---

## 5. Trigger point + UI

- **Trigger:** at race-logging time — the `routes/race_events.py` race create/update POST handlers and the onboarding target-race step (`routes/onboarding.py`, `templates/onboarding/target_race.html`), fired when the location (coords) is set/changed and `race_terrain` is empty/unconfirmed. Synchronous best-effort with a short timeout, or deferred to the editor render — TBD by latency (§12); either way non-blocking (criterion (d)).
- **Surface:** `_race_terrain_editor.html` (the existing manual editor) renders **pre-filled** from the suggestion, each row tagged *"suggested — review"*, with the confidence framing (low-confidence races get a stronger "verify this" prompt) and the terrain+conditions nudge banner above it. The athlete edits/accepts/clears exactly as today; accept writes `race_terrain` through the existing path.

---

## 6. Caching / invalidation

- **Don't re-invoke:** key the inference on the location inputs (`mapbox_id` or rounded `lat/lng` + `event_date` season + `distance`/`elevation`/`format`). With storage option (B), the persisted `race_terrain_suggested` + a stored input-hash means a re-save with unchanged inputs skips the call (criterion (e)); changing the location re-infers.
- **Downstream invalidation is unchanged:** once accepted into `race_terrain`, the existing race-event/Layer-2B cache invalidation applies (the suggestion column is not read by plan-gen, so it never participates in plan keys).

---

## 7. Rule #15 logging
At inference: `race_terrain_inference: race=<id> loc=<place_name>@<lat,lng> conf=<high|med|low> terrain=[TRN-xxx:pct,...] sum=<pct> retries=<n> | weather=<summary_line|none>` — the inputs it decided on and the breakdown it produced, plus failure cause on the degrade path (`fallback: <no_coords|llm_error:CODE|off_vocab:TRN-xxx|pct_sum=NN>`). So a wrong/absent suggestion is diagnosable from logs alone.

---

## 8. Edge cases
- **No coordinates** (location not Mapbox-anchored) → skip inference + weather; empty editor. Logged `fallback: no_coords`.
- **Standardized race** (Boston) → high confidence; the future crowd path (§10) would converge these.
- **Adventure race** (changes yearly) → low confidence; UI frames it as "starting point, verify." This is where inference is most valuable (no per-venue data) **and** least certain — the review gate matters most here.
- **Multi-discipline race** → the model may scope terrain `pct` per discipline via the existing optional `RaceTerrainEntry.discipline_id`; v1 may keep it discipline-agnostic and let the athlete split (simplest) — open item §12.
- **LLM returns off-vocabulary / pct way off** → inference failure → empty editor (never persist garbage). Logged.
- **Athlete already entered terrain manually** → no suggestion overwrite; inference only fires on empty/unconfirmed terrain.

---

## 9. Test scenarios
1. Known standardized race with coords → inference returns valid breakdown (TRN ids in vocab, pct ~100), high confidence; editor pre-fills; accept → `race_terrain` populated; Layer 2B output identical to the same manual entry. *(criteria a, b)*
2. AR race, low confidence → editor pre-fills with "verify" framing; athlete edits → edited values persist. *(criterion a)*
3. No coords → no inference, empty editor, race still logs. *(criterion d)*
4. LLM error / off-vocabulary output → graceful fallback to empty editor; `fallback:` logged. *(criterion d)*
5. Conditions nudge shows `get_expected_conditions` normals for location+date. *(criterion c)*
6. Re-save unchanged location → no second LLM call (keyed). *(criterion e)*
7. Rule #15 `race_terrain_inference` line present + correct (inputs, breakdown, weather, failure cause).

---

## 10. Crowd-sourcing tie-in (future — NOT v1)
The issue's strategic frame: for **standardized** races the inferred → athlete-confirmed → result-confirmed terrain could converge into a **shared race-profile** (the race analog of the event-window crowd-sourced locations funnel, differentiator #8). v1 stays **per-athlete** (each athlete gets their own suggestion). The persisted-suggestion column (§3 option B) + the input-hash key are the hooks a later crowd slice would aggregate on (dedup by `mapbox_id`, like the locale crowd path). Flagged, not built.

---

## 11. Why this is small
The race model, the manual terrain editor, the LLM invocation harness, the terrain vocabulary + 2B validation, the weather client, and the entire downstream consumption **all exist**. The only new pieces are: one LLM inference call (§4), a race-logging-time trigger + a pre-fill on the existing editor (§5), and (optionally) one suggestion column (§3). Plan-gen is untouched.

## 12. Open items / sign-off
- **Trigger #1 — PROMPT BODY OWED (Andy).** §4 fixes inputs / output schema / validation / intent; the **prompt wording** needs sign-off before build (mandatory Stop-and-ask Trigger #1).
- **Storage — DECISION OWED.** Transient suggestion (A) vs persisted `race_terrain_suggested` column (B). **Recommendation: (B).** (§3)
- **Trigger timing — DECISION OWED.** Synchronous-at-save (short timeout) vs lazy-at-editor-render — driven by inference latency; both non-blocking. (§5)
- **Per-discipline terrain — CONFIRM.** v1 discipline-agnostic breakdown (athlete splits) vs model scoping `pct` per `discipline_id`. **Recommendation: discipline-agnostic v1.** (§8)
- **Confidence framing copy** — the low-confidence "verify this" wording (coaching voice) — at build with the prompt body.

## 13. Gut check
- **Best argument against:** weather is already covered and terrain is a *small* manual entry today — is auto-inferring 3–5 terrain rows worth an LLM call + a review gate the athlete still has to walk? It earns its keep mainly for **adventure races with no per-venue data** (the issue's own framing) and as the **cold-start for the crowd-sourced race profile** (§10). For standardized races the athlete could near-instantly enter terrain themselves. If the crowd path isn't on the near roadmap, this is a convenience feature, not a differentiator.
- **Biggest risk:** a **confidently-wrong** low-confidence suggestion that the athlete rubber-stamps → the plan trains for the wrong terrain. Mitigations: the review gate, explicit low-confidence framing, and Rule #15 logging of what was suggested vs accepted. The conditions half is safe (deterministic normals, already shipped).
- **What's genuinely clean:** scoping it as a *middle step that only populates `race_terrain`* means zero plan-gen risk — if the inference is bad, the worst case is the athlete edits a few rows, exactly as today. The blast radius is contained to the editor.
- **What might be missing:** whether the inference should also nudge the **race-week brief** (which already has weather) with terrain — but that brief reads `race_terrain` already, so accepted suggestions flow there for free; no extra work.
