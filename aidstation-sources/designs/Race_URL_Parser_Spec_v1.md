# Race-URL Site-Parse Pre-Fill — onboarding race-entry auto-fill — Build Spec v1

**Parent epic:** #246 (onboarding & athlete data capture, Layer 1). **This is the build spec for GitHub [#256](https://github.com/ahorn885/exercise/issues/256)** — *"auto-fill race details from a pasted race URL."* The `race_events.race_url` column was added (D-73 Phase 5.2 walkthrough #2a) with a forward reference to exactly this slice: *"future Trigger #2 LLM site-parse slice will pre-fill rules/equipment/terrain from the URL"* (`init_db.py:1499-1501`).
**Status:** **DESIGN-FIRST — NOT BUILT.** Scoped per Andy 2026-06-21 (design-specs-first). The site-parse is a **new LLM call → Stop-and-ask Trigger #1 (LLM prompt design)**: the prompt **structure + I/O contract** are spec'd here; the **prompt body wording is owed Andy's sign-off at build** (matches #592's Trigger-#1 treatment — `designs/Race_Location_Terrain_Inference_Spec_v1.md`). No build until §12 sign-off.
**Date:** 2026-06-21
**Sibling:** #592 (race-location terrain inference). #256 and #592 are two LLM calls hanging off the same race-entry surface but with **disjoint outputs** — see §10 for the boundary.

---

## 1. Purpose + scope

When the athlete pastes a **race-director site URL** into the (already-present) `race_url` field, fetch that page and use a single LLM tool-call to **pre-fill the race-entry form** with whatever the page yields, as a reviewable suggestion the athlete confirms before saving.

**The guiding rule (Andy 2026-06-21): "as much as is possible, but don't *force* it and don't *block* if some info isn't available."** This shapes the whole contract:
- **Best-effort, field-by-field.** Every output field is independently optional. The parser fills the fields it confidently finds and leaves the rest for manual entry.
- **Never fabricate.** A field the model can't ground in the page text comes back `null` → the form field is left untouched. The model must not guess a date/distance/format that isn't on the page.
- **Never block.** A fetch failure, a JS-only page, a bot-wall, a malformed response — all degrade to today's behavior: the athlete fills the form by hand. Pasting a URL that can't be read is a no-op, not an error that stops onboarding.

**The carve (why this is small):** the race form, its payload (`RaceEventPayload`, `layer4/context.py:1245-1361`), the repo create/update path (`race_events_repo.py`), the LLM tool-call harness (`llm_invocation.invoke_tool_call`), the best-effort outbound-HTTP pattern (`weather_client._default_fetch`), and the Mapbox forward-geocoder (`mapbox_client.search_places`, via `routes/race_events.py:294`) **all exist**. The only new pieces are: one page-fetch+reduce helper, one LLM parse call (§4), and a pre-fill on the existing form (§5). **No new DB column, no migration** — the suggestion is transient (it lives in the form until the athlete saves through the existing path), which is the main thing that makes #256 *lighter* than #592 (which needed a persisted `race_terrain_suggested` column).

**In scope:** a `race_url_parser.py` exposing one parse entry point (`parse_race_url`); a fetch+reduce step (`requests.get` with timeout/size/content-type guards → HTML-to-text); the LLM tool-call (`record_race_url_parse`) returning a per-field-nullable partial; validation of each field against the same closed sets the repo already enforces (`VALID_RACE_FORMATS`, date/numeric coercion, terrain/discipline vocab); resolving an extracted location **string** through the existing Mapbox picker (athlete-confirmed, never auto-committed); a trigger button on the onboarding + profile race forms; Rule #15 logging.

**Out of scope:** terrain inference (#592 owns `race_terrain` — §10); any change to how the saved race feeds Layer 2A/2B/3B/4 (unchanged — #256 ends at pre-filling form inputs the athlete then saves normally); a live forecast / weather (the race-week brief already has it); athlete-specific fields that aren't on a race page (`goal_outcome`, `first_time_at_distance`, `time_goal`, `race_pack_weight_kg`, `previous_attempts`, `estimated_duration_hr` — §4 field table); persisting a suggestion across sessions (transient by design); auto-saving the race without athlete review.

**Success criteria:**
- (a) Pasting a readable race URL and triggering a parse pre-fills the form fields the page supports (name, date, format, distance, elevation, location, rules→notes, sport) with values the athlete can edit/clear before saving.
- (b) A field not present on the page is left **untouched** (never fabricated, never blanks an existing manual value the athlete already typed).
- (c) Fetch failure (non-200, timeout, non-HTML, oversized, JS-only/bot-walled) degrades gracefully → the athlete just fills the form manually; race entry is never blocked. A human-readable "couldn't read that page" hint is shown.
- (d) Extracted location is **resolved through the existing Mapbox picker** as a confirmable candidate — never written to the anchored columns without the athlete picking it.
- (e) Off-vocabulary / out-of-range extractions (bad `race_format`, unparseable date, negative distance) are dropped field-by-field; the rest of the parse still applies.
- (f) Re-triggering a parse on the same unchanged URL within the session does not silently double-charge the LLM (light dedup, §6).

---

## 2. Boundaries

- **Suggestion, not authority — and not auto-applied.** The parse *pre-fills* form inputs; the athlete reviews every field and saves through the **existing** create/update handlers (`routes/onboarding.py` target-race save, `routes/race_events.py` `new_race`/`update_race`). There is no new write path and no new persistence — exactly the same POST the manual flow uses.
- **Best-effort, never blocking** (criterion c). Mirrors `get_expected_conditions` / `_default_fetch`: any failure returns an empty/partial result, never raises into the request.
- **No downstream contract change.** #256 only changes what's pre-filled in the form. Everything after Save (Layer 2A discipline mix, 2B terrain, 3B viability, 4 synthesis) reads the saved row exactly as it does for a hand-typed race.
- **Don't clobber athlete input.** If the athlete already typed a field, a parse does not overwrite it unless they explicitly re-run parse on an empty form (UI decision, §5) — the never-fabricate rule extends to never-silently-replace.
- **Trigger #1 (prompt body).** The parse prompt is a new LLM prompt → its body wording is owed Andy's sign-off (§12); this spec fixes the I/O contract, inputs, validation, and intent only.

---

## 3. Data model

**No new table, no new column, no migration.** The parse result is transient — it pre-fills the form and is gone once the athlete saves (or navigates away). Everything it writes lands in the **existing** `race_events` columns via the existing save path:

- scalar/text fields → `name`, `event_date`, `race_format`, `distance_km`, `total_elevation_gain_m`, `notes`, `framework_sport`, `included_discipline_ids` (`init_db.py:1455-1517`)
- location → the 5 Mapbox-anchored columns (`event_locale_name/_mapbox_id/_place_name/_lat/_lng`) **only after the athlete confirms a picker candidate** (§5)
- the URL itself → `race_url` (already captured today)

This is the deliberate contrast with #592, which *did* add a persisted `race_terrain_suggested` column because its suggestion had to survive to a later review and feed the crowd path. #256's suggestion has no afterlife — so it gets no storage. (A short-lived cache to avoid re-billing repeated button clicks is §6; it is **not** a `race_events` column.)

---

## 4. The parse call (Trigger #1 — structure spec'd, body owed sign-off)

Two steps: a deterministic **fetch+reduce**, then a single **LLM tool-call**.

### 4.1 Fetch + reduce (deterministic, best-effort)
Mirror `weather_client._default_fetch` exactly in spirit:
- `requests.get(url, timeout=_TIMEOUT_S, headers={...})` with a short timeout (~8s) and a descriptive User-Agent.
- **Guards** (each → graceful "couldn't read the page", logged): non-200; `Content-Type` not HTML/text (PDF, image); body over a size cap (~2 MB) — read capped; connection/timeout exception.
- **Reduce HTML → text** before the LLM: strip `<script>/<style>/<nav>/<footer>`, collapse to visible text, truncate to a token-bounded length (~12–16k chars). This bounds cost and strips boilerplate. *(Implementation note, not a contract: a minimal regex/stdlib reduction avoids a new heavy dependency; if a parser lib is wanted it's a build-time call — flag at §12.)*
- **JS-only pages** (SPA shells with no server-rendered content) are an expected miss: the reduced text is near-empty → the parse returns nothing → manual entry. Documented limitation, not a bug (§8, §13).

### 4.2 LLM tool-call — `record_race_url_parse`
A single tool-call inference on the reduced page text, using the established harness (`llm_invocation.invoke_tool_call` + capped forced-tool retry + `ThinkingToolCallError`, `llm_invocation.py:50`; caller/exception-mapping per the `layer3b/builder` pattern).

**Inputs:** the reduced page text; the source URL; the **closed vocabularies** so the model can only emit valid tokens — `race_format ∈ {single_day, continuous_multi_day, stage_race}` (`VALID_RACE_FORMATS`), and (if discipline extraction is kept, §4.3) the candidate discipline ids/names for the resolved `framework_sport` from `layer0.sport_discipline_bridge`.

**Output tool schema — every field nullable; `null` ≡ "not found on the page" (never fabricate):**

| Output field | Maps to | Notes / validation |
|---|---|---|
| `name` | `name` | trimmed; non-empty else null |
| `event_date` | `event_date` | ISO `YYYY-MM-DD`; multi-day → start date; unparseable → null |
| `race_format` | `race_format` | must be one of `VALID_RACE_FORMATS`; else null |
| `distance_km` | `distance_km` | ≥ 0; if the page lists several distances, the model picks the one the page presents as primary, else null (don't guess) |
| `total_elevation_gain_m` | `total_elevation_gain_m` | ≥ 0; else null |
| `location_text` | → Mapbox (§5) | free string ("Nerstrand, MN"); **not** written directly — fed to the picker |
| `framework_sport` | `framework_sport` | free string (e.g. "Adventure Racing"); Layer 2A re-validates against the bridge at save |
| `included_discipline_ids` | `included_discipline_ids` | optional (§4.3); only canonical ids that resolve for the sport; else omit |
| `rules_notes` | `notes` | the high-value extraction: mandatory kit, cutoffs/time cuts, checkpoint/support rules, gear inspection — the race-week brief reads `notes` in full (#439). Capped to the 10 000-char `notes` Field max |
| `confidence` | UI framing | `high\|medium\|low` — low frames the pre-fill as "verify this" |
| `summary` | UI banner | one-line, coaching voice: what was found + what to fill in by hand |

**Excluded fields (deliberately not parsed):** `estimated_duration_hr`, `primary_metric` (derived from which of distance/duration got filled, not parsed), `goal_outcome`, `first_time_at_distance`, `time_goal`, `race_pack_weight_kg`, `previous_attempts` — these are athlete-specific, not race-page facts. `race_terrain` is **#592's** (§10).

**Validation (per field, reuse the repo's own coercers):** `race_format` against `VALID_RACE_FORMATS`; date via the existing `%Y-%m-%d` parse; numerics ≥ 0 (drop negatives, as `_parse_pack_weight_kg`/`_parse_estimated_duration_hr` do); `included_discipline_ids` against the sport's bridge set. A field that fails validation is **dropped individually** — the rest of the parse still pre-fills (criterion e). Capped retry (cap=2, house default) only on a schema-violation tool call, same as #592.

### 4.3 Open: discipline extraction
`included_discipline_ids` is the least reliable field (requires the page to enumerate disciplines *and* them to map cleanly to canonical ids). **Recommendation:** include it but treat a miss as the default (empty → "use bridge defaults", the existing semantic) — never narrow the discipline set on a shaky extraction. Final keep/drop is a §12 sign-off item.

---

## 5. Trigger point + UI

- **Trigger:** an explicit **"Fetch details from URL"** button next to the `race_url` input on both race forms (`templates/onboarding/target_race.html:58`, `templates/profile/race_event_edit.html:185`). **Explicit, not auto-on-blur** — fetching an external page is a deliberate, user-initiated action (cost + latency + privacy of hitting a third-party site), and it keeps the never-block promise obvious: the athlete can always just type.
- **Endpoint:** a new POST (e.g. `routes/race_events.py` `parse_race_url_endpoint`) that takes the URL, runs §4, and returns the per-field partial as JSON. The page's JS pre-fills only the fields that came back non-null (and only empty fields, unless the athlete confirms an overwrite — §2 don't-clobber), shows the `summary` banner with the `confidence` framing, and routes `location_text` into the existing locale picker as a pre-filled search the athlete confirms (reusing `_run_mapbox_search` → `mapbox_client.search_places`). Best-effort: a failed fetch returns a `{ ok: false, hint }` the banner surfaces; the form is untouched.
- **Latency:** fetch (~timeout 8s) + one thinking LLM call. The button shows a spinner; the call is async and non-blocking. No synchronous-at-save coupling (unlike one of #592's open options) — the parse only ever runs on the explicit button.

---

## 6. Caching / invalidation

- **Light dedup only.** Because the trigger is an explicit button, re-calls are user-initiated and rare; the main waste is a double-click or a re-parse of an unchanged URL. Key a short-lived cache on `sha256(normalized_url + reduced_page_hash)` so an identical re-fetch returns the prior parse without a second LLM call (criterion f).
- **Recommended placement:** a **transient / in-process** cache (or skip caching entirely for v1 — the button is explicit). **Do not** add a new `entry_point` to `layer4_cache` for this — that table's `entry_point` CHECK is an inter-layer surface (touching it is Stop-and-ask Trigger #3) and #256 has no business in the plan-gen cache. If a persistent cache is ever wanted, that's a separate, flagged decision.
- **No downstream invalidation.** Nothing is persisted by the parse itself; the athlete's Save goes through the normal race-event write, which already carries its own Layer-2B/plan invalidation. The parse never participates in any plan cache key.

---

## 7. Rule #15 logging

At parse: `race_url_parse: url=<normalized> fetch=<200|status|timeout|non_html|oversize> bytes=<n> reduced_chars=<n> fields=[name,event_date,race_format,distance_km,...] dropped=[<field>:<reason>,...] conf=<high|med|low> retries=<n>` — the URL it fetched, the fetch outcome, which fields it filled vs dropped (with the validation reason), and the confidence. On the degrade path: `race_url_parse fallback: <fetch_failed:STATUS|non_html:CT|oversize|empty_text|llm_error:CODE>`. So a wrong/empty pre-fill is diagnosable from logs alone (the page may simply not have carried the field — the log distinguishes "page didn't have it" from "we couldn't read the page").

---

## 8. Edge cases
- **JS-only / SPA race site** → reduced text near-empty → parse returns nothing → manual entry. Logged `empty_text`. (The dominant real-world miss — see §13.)
- **Bot-wall / Cloudflare / 403** → graceful fail, hint shown, manual entry. Logged with the status.
- **PDF / image flyer at the URL** → non-HTML guard trips → graceful fail. (A future slice could OCR/parse PDFs; not v1.)
- **Multiple distances on the page** (5k/25k/50k/100k) → model fills the page's primary distance or leaves it null; the athlete picks. Never guess across options.
- **Multi-day stage race** → `race_format=stage_race`, `event_date` = start date; durations/per-stage detail go to `rules_notes`.
- **Athlete already typed fields** → parse pre-fills only empty fields (don't-clobber, §2); an explicit "re-fill from URL" can offer to overwrite, athlete-confirmed.
- **Location resolves to the wrong place** (ambiguous "Springfield") → the picker shows candidates; the athlete confirms; nothing is written until they do (criterion d).
- **Wrong/garbage URL or a non-race page** → low confidence, little/nothing extracted; the athlete sees "couldn't find race details here" and fills manually.
- **Off-vocab `race_format` / unparseable date** → that field dropped, rest applied (criterion e).

---

## 9. Test scenarios
1. Readable static race page with coords-able location → parse fills name/date/format/distance/elevation + rules→notes; location surfaces as a confirmable picker candidate; athlete saves; row matches a hand-typed equivalent. *(a, d)*
2. Page missing distance + elevation → those fields left untouched (null), the present fields still fill. *(b)*
3. Fetch 404 / timeout / non-HTML → `{ok:false}` + hint; form untouched; race still saves manually. *(c)*
4. JS-only SPA → empty reduced text → nothing pre-filled; `empty_text` logged. *(c)*
5. Page lists `race_format`-like text that's off-vocab + an unparseable date → both dropped, name/location still fill. *(e)*
6. Athlete typed a name already → parse doesn't overwrite it (unless confirmed). *(b)*
7. Same URL parsed twice in a session → second call served from dedup, no second LLM charge. *(f)*
8. Rule #15 `race_url_parse` line present + correct (fetch outcome, filled vs dropped fields, confidence); degrade path logs the fallback reason.

---

## 10. Relationship to #592 (terrain) — the boundary
#256 and #592 are siblings on the race-entry surface with **disjoint outputs**, so they don't collide:
- **#256 (this)** fills the **factual race fields** from a pasted **URL**: name, date, format, distance, elevation, location, rules→notes, sport.
- **#592** infers the **terrain breakdown** (`race_terrain`, per-discipline `TRN-xxx` + pct) from the **location** — and lists `race_url` only as *free-text context* to its terrain prompt (`Race_Location_Terrain_Inference_Spec_v1.md` §4).

**Single writer per field:** #256 never writes `race_terrain`; #592 owns it. The schema comment that seeded this work said the site-parse would pre-fill *"rules/equipment/terrain"* (`init_db.py:1500`) — but since #592 was carved out to own terrain inference, **#256 drops terrain** and stops at rules→notes. If a race page happens to describe terrain explicitly, the clean integration (future, not v1) is for #256 to hand the extracted page text to #592's inference as additional context — **not** to write `race_terrain` directly. Flagged in §12.

---

## 11. Why this is small
The race form + payload, the repo write path, the LLM tool-call harness, the best-effort HTTP pattern (`weather_client`), the Mapbox forward-geocoder + picker, and the entire downstream consumption **all exist**. The only new code is: `race_url_parser.py` (fetch+reduce + one tool-call, §4), a parse endpoint + a button + JS pre-fill (§5), and Rule #15 logging. **No DB migration, no new column, no downstream contract touched** — strictly lighter than #592.

## 12. Open items / sign-off
- **Trigger #1 — PROMPT BODY OWED (Andy).** §4 fixes inputs / output schema / validation / intent; the **prompt wording** needs sign-off before build (mandatory Stop-and-ask Trigger #1).
- **Scope — SETTLED (Andy 2026-06-21):** best-effort **whole-form** pre-fill — "as much as possible, don't force it, don't block." Field set fixed in §4. **Spec'd.**
- **No persistence — SETTLED (this spec):** transient suggestion, no `race_events` column, no migration. (§3)
- **Discipline extraction (§4.3)** — keep `included_discipline_ids` (miss → bridge defaults) vs drop it — DECISION OWED.
- **HTML-reduce dependency (§4.1)** — stdlib/regex reduction (no new dep, recommended) vs a parser lib — DECISION OWED at build.
- **Re-fill overwrite UX (§5/§8)** — pre-fill empty-only (recommended) vs offer an athlete-confirmed overwrite of typed fields — DECISION OWED.
- **#592 terrain hand-off (§10)** — leave the "page text → #592 context" tie-in for a later slice (recommended) vs in v1 — DECISION OWED.

## 13. Gut check
- **Best argument against:** the value is bounded by what's *machine-readable* on race sites, and the best targets are exactly the worst pages — small adventure-race sites are often hand-built, JS-heavy, PDF flyers, or bot-walled, so the real-world hit rate may be mediocre. For a clean, static page the athlete could type the handful of fields about as fast as reviewing a pre-fill. It earns its keep most for **dense rules text** (mandatory kit, cutoffs, support rules → `notes`), where retyping is genuinely tedious and the brief reads it in full (#439) — that's the field to optimize the prompt around, more than name/date.
- **Biggest risk:** a **confidently-wrong** extraction the athlete rubber-stamps — wrong date or distance silently mis-periodizing the plan. Mitigations: the never-fabricate contract (null over guess), per-field validation, the explicit review-before-save gate, the confidence framing, and Rule #15 logging of filled-vs-dropped. Location is double-gated (Mapbox candidate the athlete must pick). The fetch layer is the other risk surface (SSRF/oversized/slow third-party) — bounded by timeout, size cap, content-type guard, and (build-time) a check that the URL is a public http(s) host.
- **What's genuinely clean:** scoping it as *transient form pre-fill with no persistence and no downstream change* means near-zero blast radius — worst case the athlete edits a few fields, exactly as today. Disjoint from #592 (no shared writable field) means the two LLM calls compose without coordination.
- **What might be missing:** PDF flyers are a common race-info format and are out of scope here (non-HTML guard skips them) — worth noting as the obvious follow-up if the hit rate on HTML alone disappoints.
