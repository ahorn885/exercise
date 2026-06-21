# Race-Entry Auto-Fill — race-URL site-parse (primary) + location inference (subordinate) — Build Spec v1

**Parent epic:** #246 (onboarding & athlete data capture, Layer 1). **Build spec for GitHub [#256](https://github.com/ahorn885/exercise/issues/256)** — *"auto-fill race details from a pasted race URL"* — now **folded with [#592](https://github.com/ahorn885/exercise/issues/592)** (race-location terrain/weather inference) per Andy 2026-06-21. The `race_events.race_url` column was added (D-73 Phase 5.2 walkthrough #2a) with a forward reference to exactly this slice: *"future Trigger #2 LLM site-parse slice will pre-fill rules/equipment/terrain from the URL"* (`init_db.py:1499-1501`).
**Status:** **DESIGN-FIRST — NOT BUILT.** The site-parse is a **new LLM call → Stop-and-ask Trigger #1 (LLM prompt design)**: the prompt **structure + I/O contract** are spec'd here; the **prompt body wording is owed Andy's sign-off at build** (matches #592's Trigger-#1 treatment). No build until §12 sign-off.
**Date:** 2026-06-21

**The fold (Andy 2026-06-21):** #256 (parse the race *website*) and #592 (infer from the race *location*) become **one coordinated pre-fill**, not two disjoint calls. **The website parse takes precedence; the location inference is subordinate — it only fills what the site doesn't have.** Concretely: terrain becomes dual-source (page → location, page wins); weather normals always come from the location (a race page won't carry climate data). #592's terrain call becomes a subordinate step *inside* this flow rather than a standalone trigger — its spec needs a corresponding "now subordinate" update (§10, owed).
**Persistence split-out:** the durable, cross-athlete repeated-race profile store (Boston-type races, differentiator #8) is **[#856](https://github.com/ahorn885/exercise/issues/856)** — out of scope here. This slice is **per-athlete and transient** (§3).

---

## 1. Purpose + scope

When the athlete pastes a **race-director site URL**, fetch that page and use a single LLM tool-call to **pre-fill the race-entry form** with whatever the page yields — as a reviewable suggestion the athlete confirms before saving. For anything the **page** doesn't carry, fall back to the **location** inference (#592): terrain inferred from the resolved coordinates, plus the existing climate-normals nudge.

**The guiding rule (Andy 2026-06-21): "as much as possible, but don't *force* it and don't *block* if some info isn't available."**
- **Best-effort, field-by-field.** Every output field is independently optional. Fill what's confidently found; leave the rest for manual entry.
- **Never fabricate.** A field the model can't ground in the page text comes back `null` → the form field is left untouched. No guessed dates/distances/formats.
- **Never block.** A fetch failure, a JS-only page, a bot-wall — all degrade to manual entry (then, for terrain, the location fallback). Pasting an unreadable URL is a no-op, not a blocking error.
- **Site wins, location backfills.** Where both could supply a field (terrain), the page's value is used; the location inference runs only for the gap.

**The carve (why this is small):** the race form + payload (`RaceEventPayload`, `layer4/context.py:1245-1361`), the repo write path (`race_events_repo.py`), the LLM tool-call harness (`llm_invocation.invoke_tool_call`), the best-effort HTTP pattern (`weather_client._default_fetch`), the Mapbox forward-geocoder (`mapbox_client.search_places`), the terrain editor + Layer-2B terrain validation, the weather client, and #592's terrain inference **all exist or are spec'd**. New pieces: one `race_url_parser.py` (fetch+reduce + one tool-call), the precedence orchestration that invokes #592's terrain call as a fallback, the distance/event chooser, and a pre-fill on the existing form. **No new DB column, no migration** — the suggestion is transient (§3).

**In scope:** `race_url_parser.py` (`parse_race_url`); fetch+reduce (`requests.get` guarded → HTML-to-text); the LLM tool-call (`record_race_url_parse`) returning a per-field-nullable partial **including terrain**; per-field validation against the repo's closed sets + Layer-2B terrain vocab; resolving an extracted location **string** through the existing Mapbox picker (athlete-confirmed); the **distance/event chooser** (§5); the **location-inference fallback** for terrain when the page lacks it (#592, subordinate) + the climate-normals nudge; a trigger button on both race forms; Rule #15 logging.

**Out of scope:** durable cross-athlete storage (→ #856); distance *inference* (athlete-selected only, §5); athlete-specific fields not on a race page (`goal_outcome`, `first_time_at_distance`, `time_goal`, `race_pack_weight_kg`, `previous_attempts`, `estimated_duration_hr`); a live forecast; auto-saving without review.

**Success criteria:**
- (a) Pasting a readable race URL + triggering a parse pre-fills the supported fields (name, format, elevation, location, rules→notes, sport, **terrain**) as editable suggestions.
- (b) A field not on the page is left **untouched** (never fabricated; never blanks a value the athlete already typed).
- (c) Fetch failure degrades gracefully → manual entry; race entry is never blocked. For terrain, the location fallback still runs.
- (d) Extracted location is **resolved through the Mapbox picker** as a confirmable candidate — never written to the anchored columns without the athlete picking it.
- (e) **Distance is never auto-set.** The parse surfaces the page's distance/event options; the athlete picks one (or types one); the pick re-scopes date/elevation/terrain to that event (§5).
- (f) **Terrain precedence:** when the page describes terrain, it pre-fills the terrain editor and the location inference is skipped; when it doesn't, #592's location inference fills it (subject to its own review gate). Both round-trip identically downstream to a manual entry.
- (g) Off-vocab / out-of-range extractions are dropped field-by-field; the rest still applies.

---

## 2. Boundaries

- **Suggestion, not authority — not auto-applied.** The parse + fallback *pre-fill* form inputs; the athlete reviews every field and saves through the **existing** create/update handlers. No new write path, no new persistence.
- **Best-effort, never blocking** (criterion c). Mirrors `get_expected_conditions` / `_default_fetch`: any failure returns empty/partial, never raises into the request.
- **Site precedence is load-bearing.** The location inference (#592) is strictly subordinate — it runs only for a field the page didn't supply (terrain), never overriding a parsed value.
- **No downstream contract change.** #256+#592-folded only changes what's pre-filled. Everything after Save (Layer 2A/2B/3B/4) reads the saved row exactly as for a hand-typed race.
- **Don't clobber athlete input.** Parse pre-fills only empty fields; an explicit re-fill can offer an athlete-confirmed overwrite.
- **Trigger #1 (prompt body).** New LLM prompt → its body wording is owed Andy's sign-off (§12).

---

## 3. Data model

**No new table, no new column, no migration.** The parse + fallback result is transient — it pre-fills the form and is gone once the athlete saves (or leaves). Everything written lands in **existing** `race_events` columns via the existing save path: scalars/text → `name`/`event_date`/`race_format`/`distance_km`/`total_elevation_gain_m`/`notes`/`framework_sport`/`included_discipline_ids`; terrain → `race_terrain` (athlete-confirmed, exactly as a manual entry or #592 accept); location → the 5 Mapbox columns (after picker confirm); the URL → `race_url`.

**This revises #592's persisted-suggestion decision.** #592's standalone spec settled on a persisted `race_terrain_suggested` (+ `_at`) column so the suggestion survived to a later review and seeded the crowd path. Under the fold + the #856 split, the per-athlete flow is **transient** (the suggestion is reviewed in the same session it's produced), and **durable cross-athlete storage moves to #856**. So the `race_terrain_suggested` column is **not built here** — pending Andy's confirm that the fold supersedes that earlier decision (§12). This is the main simplification the fold buys: no schema change on the onboarding critical path.

---

## 4. The parse call (Trigger #1 — structure spec'd, body owed sign-off)

Three steps: deterministic **fetch+reduce**, one **LLM tool-call**, then the **subordinate location fallback**.

### 4.1 Fetch + reduce (deterministic, best-effort)
Mirror `weather_client._default_fetch` in spirit:
- `requests.get(url, timeout≈8s, headers={descriptive UA})`.
- **Guards** (each → graceful "couldn't read the page", logged): non-200; `Content-Type` not HTML/text (PDF/image); body over a size cap (~2 MB, read capped); connection/timeout exception; **non-public host** (block private/loopback/link-local targets — SSRF guard, build-time).
- **Reduce HTML → text**: strip `<script>/<style>/<nav>/<footer>`, collapse to visible text, truncate to ~12–16k chars. Bounds cost, strips boilerplate. *(Stdlib/regex reduction avoids a new dependency — §12.)*
- **JS-only pages** → near-empty reduced text → parse returns nothing → manual entry (+ terrain fallback). Documented limitation (§8, §13).

### 4.2 LLM tool-call — `record_race_url_parse`
Single tool-call on the reduced page text via the established harness (`invoke_tool_call` + capped forced-tool retry + `ThinkingToolCallError`, `llm_invocation.py:50`; caller/exception-mapping per the `layer3b/builder` pattern).

**Inputs:** the reduced page text; the source URL; the **closed vocabularies** so the model can only emit valid tokens — `race_format ∈ {single_day, continuous_multi_day, stage_race}` (`VALID_RACE_FORMATS`); the Layer-0 terrain vocabulary (valid `TRN-\d{3}` ids + names from `layer0.terrain_types`); and the candidate discipline ids/names for the page's apparent sport (`layer0.sport_discipline_bridge`).

**Output tool schema — every field nullable; `null` ≡ "not found" (never fabricate):**

| Output field | Maps to | Notes / validation |
|---|---|---|
| `name` | `name` | trimmed; non-empty else null |
| `event_date` | `event_date` | ISO `YYYY-MM-DD`; per-event when the page ties dates to distances (§4.3); unparseable → null |
| `race_format` | `race_format` | one of `VALID_RACE_FORMATS`; else null |
| `distance_options` | → chooser (§5) | **list**, not a single value: `[{label, distance_km, event_date?, elevation_m?, terrain?}]` — the events/distances the page offers. **Never sets `distance_km` directly** (criterion e) |
| `total_elevation_gain_m` | `total_elevation_gain_m` | ≥ 0 (race-wide; per-event rides in `distance_options`); else null |
| `location_text` | → Mapbox (§5) | free string; **not** written directly — fed to the picker |
| `framework_sport` | `framework_sport` | free string; Layer 2A re-validates at save |
| `included_discipline_ids` | `included_discipline_ids` | optional; only canonical ids that resolve for the sport; miss → omit (= bridge defaults) |
| `race_terrain` | `race_terrain` | **the fold's primary terrain source.** Per-discipline `[{discipline_id, terrain_id: "TRN-\d{3}", pct_of_race}]`, reusing `RaceTerrainEntry`. Validated like Layer 2B (TRN in vocab; per-discipline pct sum ∈ [80,120]); off-vocab → drop terrain, let the location fallback fill it (§4.4) |
| `rules_notes` | `notes` | the high-value extraction: mandatory kit, cutoffs, checkpoint/support rules, gear inspection — the brief reads `notes` in full (#439). Capped to 10 000 chars |
| `confidence` | UI framing | `high\|medium\|low` — low frames "verify this" |
| `summary` | UI banner | one line, coaching voice: what was found + what to fill by hand |

**Excluded (not parsed):** `distance_km` as a scalar (chooser-driven, §5), `estimated_duration_hr`, `primary_metric` (derived), `goal_outcome`, `first_time_at_distance`, `time_goal`, `race_pack_weight_kg`, `previous_attempts`.

**Validation (per field, reuse the repo's coercers + Layer 2B):** `race_format` vs `VALID_RACE_FORMATS`; date via the existing `%Y-%m-%d` parse; numerics ≥ 0 (drop negatives); terrain vs the Layer-2B TRN pattern/vocab/pct-sum; disciplines vs the sport's bridge set. A failing field is **dropped individually** (criterion g). Capped retry (cap=2) on a schema-violation tool call.

### 4.3 Distance/event detection (feeds the chooser, never auto-sets)
The page commonly offers several distances, often as distinct sub-events with their own date/elevation/terrain (the 100-miler Saturday, the 50k Sunday). The model returns these as `distance_options` — the *menu*, not a pick. The athlete selects which event they're racing (§5); the selection sets `distance_km` and re-scopes `event_date`/`total_elevation_gain_m`/`race_terrain` to that event's values where the page tied them. Single-distance pages yield a one-entry list (still athlete-confirmed). No options detected → the athlete types distance manually; nothing is auto-set.

### 4.4 Subordinate location fallback (#592, terrain + weather)
After the parse + the athlete's event pick, **if `race_terrain` is still empty** *and* the location resolved to coordinates, invoke **#592's** terrain inference (`record_race_terrain_inference`) as the fallback and pre-fill the terrain editor from it (with #592's own review framing/confidence). If the page supplied terrain, **skip** the inference (precedence). Independently, always call the existing `get_expected_conditions(lat, lng, event_date)` (`weather_client.py`) and surface its `summary_line()` as the conditions nudge — the page won't carry climate normals, so this half is always location-sourced. Both are best-effort; failure → the empty terrain editor (today's behavior).

---

## 5. Trigger point + UI

- **Trigger:** an explicit **"Fetch details from URL"** button next to `race_url` on both forms (`templates/onboarding/target_race.html:58`, `templates/profile/race_event_edit.html:185`). Explicit, not auto-on-blur — fetching a third-party page is a deliberate, user-initiated action, and it keeps the never-block promise obvious.
- **Endpoint:** a new POST (`routes/race_events.py` `parse_race_url_endpoint`) that runs §4 and returns the partial as JSON. The page JS pre-fills only non-null, empty fields; shows the `summary` banner with `confidence` framing; routes `location_text` into the existing picker (`_run_mapbox_search` → `mapbox_client.search_places`) as a confirmable candidate; and renders the **distance/event chooser** from `distance_options`.
- **Distance/event chooser (Andy 2026-06-21 — "editable field + chooser"):** `distance_km` stays a **normal athlete-owned form field** (never auto-filled). When `distance_options` has ≥1 entry, a post-parse *"Which distance are you racing?"* chooser lists them; picking one fills the distance field **and** re-scopes the event-tied fields (`event_date`, `total_elevation_gain_m`, `race_terrain`) to that option. The athlete can always ignore the chooser and type a distance. No options → just the manual field.
- **Terrain editor:** pre-filled from the page parse (primary) or the #592 fallback (subordinate), each row tagged *"suggested — review"*; the athlete edits/accepts/clears exactly as today; accept writes `race_terrain` through the existing path. The conditions nudge (from `get_expected_conditions`) renders above it.
- **Latency:** fetch (~8s) + one thinking LLM call (+ the #592 call only on the terrain-gap path). Async with a spinner; non-blocking; runs only on the explicit button.

---

## 6. Caching / invalidation

- **Light dedup only.** The trigger is an explicit button, so re-calls are user-initiated and rare. Key a short-lived cache on `sha256(normalized_url + reduced_page_hash)` so an identical re-fetch returns the prior parse without a second LLM call (criterion ~f).
- **Recommended placement:** transient / in-process (or skip for v1). **Do not** add an `entry_point` to `layer4_cache` — that CHECK is an inter-layer surface (Stop-and-ask Trigger #3) and this has no business in the plan-gen cache. (#592's own keyed-inference caching applies to the fallback call per its spec.)
- **No downstream invalidation.** Nothing is persisted by the parse; the athlete's Save goes through the normal race-event write, which carries its own Layer-2B/plan invalidation. Durable cross-athlete persistence is #856.

---

## 7. Rule #15 logging

At parse: `race_url_parse: url=<normalized> fetch=<200|status|timeout|non_html|oversize|blocked_host> bytes=<n> reduced_chars=<n> fields=[name,event_date,race_format,...] distance_options=<n> terrain=<page|fallback|none> dropped=[<field>:<reason>,...] conf=<high|med|low> retries=<n>`. On the degrade path: `race_url_parse fallback: <fetch_failed:STATUS|non_html:CT|oversize|empty_text|llm_error:CODE>`. On the terrain-fallback path, #592's own `race_terrain_inference` line fires. So a wrong/empty pre-fill is diagnosable — the log distinguishes "page didn't have it", "we couldn't read the page", and "filled from the location fallback".

---

## 8. Edge cases
- **JS-only / SPA / bot-wall / 403** → graceful fail + hint → manual entry; terrain still gets the location fallback. Logged.
- **PDF / image flyer** → non-HTML guard trips → graceful fail. (PDF/OCR is a future slice.)
- **Multiple distances/events** → chooser; the pick re-scopes date/elevation/terrain (criterion e, §4.3).
- **Page describes terrain** → use it (primary); **skip** the location inference (criterion f). **Page lacks terrain** → #592 fallback fills it.
- **Per-event terrain differs** (100-miler vs 50k) → the selected event's terrain (from `distance_options[i].terrain`) pre-fills; race-wide terrain applies when the page doesn't differentiate.
- **Ambiguous location** ("Springfield") → picker shows candidates; athlete confirms; nothing written until they do (criterion d). No coords → no terrain fallback, no weather nudge; empty terrain editor.
- **Athlete already typed fields** → pre-fill empty-only (don't-clobber); explicit re-fill can offer a confirmed overwrite.
- **Off-vocab `race_format`/terrain or unparseable date** → that field dropped; terrain off-vocab → location fallback; rest applies (criterion g).

---

## 9. Test scenarios
1. Readable static page, single event, page has terrain → fills name/format/elevation + rules→notes + per-discipline terrain; location surfaces as a picker candidate; chooser shows the one distance; athlete saves; row matches a hand-typed equivalent and the location inference was **not** called. *(a, d, f)*
2. Page missing terrain, location resolves → #592 fallback fills the terrain editor with its review framing; weather nudge shows. *(c, f)*
3. Multi-distance page → chooser lists all; picking the 50k sets distance + that event's date/elevation/terrain; the 100-miler's values are not used. *(e)*
4. Fetch 404 / timeout / non-HTML / blocked host → `{ok:false}` + hint; form untouched; race saves manually; terrain fallback still runs if coords exist. *(c)*
5. JS-only SPA → empty reduced text → nothing pre-filled; `empty_text` logged; terrain fallback on coords. *(c)*
6. Off-vocab `race_format` + unparseable date + off-vocab terrain → those dropped; terrain → location fallback; name/location still fill. *(f, g)*
7. Athlete typed a name already → parse doesn't overwrite it. *(b)*
8. Same URL parsed twice in a session → second served from dedup, no second LLM charge.
9. Rule #15 `race_url_parse` line correct (fetch outcome, `terrain=page|fallback|none`, filled vs dropped); degrade path logs the fallback reason; #592's line fires on the fallback path.

---

## 10. The fold with #592, and the #856 crowd track
- **#592 becomes subordinate.** Its terrain inference is invoked by §4.4 *only* on the terrain-gap path; its weather-surfacing half is always-on (location-sourced). **#592's standalone spec (`Race_Location_Terrain_Inference_Spec_v1.md`) needs a "now subordinate" update** — its race-logging-time trigger is subsumed by this flow, and its §10 crowd tie-in + its persisted-suggestion column move to #856 / §3 here. Owed (§12); not silently rewritten.
- **#856 owns durable data.** Parsed/inferred/athlete-confirmed race profiles, keyed on race identity (Mapbox id / normalized URL / name+location), accumulating across athletes for repeated/standardized races (differentiator #8). This slice leaves the hooks (the identity key + the payloads it currently discards) but persists nothing itself.

## 11. Why this is small
The race form + payload, the repo write path, the LLM harness, the best-effort HTTP pattern, the Mapbox geocoder + picker, the terrain editor + Layer-2B validation, the weather client, and #592's inference **all exist or are spec'd**. New code: `race_url_parser.py` (§4), the precedence orchestration (§4.4), the parse endpoint + button + JS pre-fill + the distance chooser (§5), Rule #15 logging. **No DB migration, no new column, no downstream contract touched.**

## 12. Open items / sign-off
- **Trigger #1 — PROMPT BODY OWED (Andy).** §4 fixes inputs / output schema / validation / intent; the **prompt wording** needs sign-off before build.
- **Fold precedence — SETTLED (Andy 2026-06-21):** site primary, location subordinate (terrain backfill only). **Spec'd.**
- **Distance — SETTLED (Andy 2026-06-21):** athlete-selected; editable field + post-parse chooser that re-scopes event-tied fields; never inferred. **Spec'd (§4.3/§5).**
- **Persistence — SETTLED (Andy 2026-06-21):** split to **#856**; this slice is transient. **Confirm** this supersedes #592's persisted `race_terrain_suggested` column (§3) — recommended.
- **#592 spec update (§10)** — revise it to "subordinate" + move its crowd tie-in to #856 — OWED (do alongside build, or now).
- **Discipline extraction** — keep `included_discipline_ids` (miss → defaults) vs drop — DECISION OWED.
- **HTML-reduce dependency (§4.1)** — stdlib/regex (recommended) vs a parser lib — DECISION OWED.
- **Re-fill overwrite UX (§5/§8)** — pre-fill empty-only (recommended) vs confirmed overwrite — DECISION OWED.

## 13. Gut check
- **Best argument against:** value is bounded by what's machine-readable, and the best targets are often the worst pages — small AR sites are frequently JS-only, PDF flyers, or bot-walled, so HTML-only hit rate may be mediocre. The fold mitigates this for *terrain* (the location fallback covers the gap), which is the most plan-relevant field — so even a thin parse still yields terrain + conditions. The parse earns its keep most on **dense rules text** → `notes` (the brief reads it in full, #439), where retyping is genuinely tedious.
- **Biggest risk:** a **confidently-wrong** extraction the athlete rubber-stamps — a wrong date/distance silently mis-periodizing the plan. Mitigations: never-fabricate (null over guess), per-field validation, **distance is never auto-set** (the field the athlete most owns), the review-before-save gate, the Mapbox double-gate on location, confidence framing, and Rule #15 logging of filled-vs-dropped + terrain source. The fetch layer is the other surface (SSRF/oversize/slow third-party) — bounded by timeout, size cap, content-type + public-host guards.
- **What's genuinely clean:** transient form pre-fill, no persistence, no downstream change → near-zero blast radius. The precedence model gives one target field per datum (page wins, location backfills), so the two LLM calls compose without a write conflict.
- **What might be missing:** PDF flyers are a common race-info format and are out of scope (non-HTML guard skips them) — the obvious follow-up if HTML-only hit rate disappoints. And per-event field scoping (§4.3/§8) adds parse complexity for stage/multi-event pages — worth confirming the model reliably ties date/elevation/terrain to the right distance, or keeping v1 to race-wide values + an athlete-edited distance.
