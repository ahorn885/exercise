# Onboarding D-59 Design — Locale Place Lookup + Chain Detection

**Version:** 1.0
**Date:** 2026-05-14
**Status:** Design decisions locked; spec rewrite pending (`Athlete_Onboarding_Data_Spec_v5.md` lands after all four design tracks settle).
**Backlog row:** D-59
**Track:** First of the four-track Onboarding Design Wave (D-58–D-61). Sequence: D-59 → D-60 → D-61 → D-58 (D-59 is foundational; the others build on the chain identity + locale coords this doc establishes).
**Affects:** `Athlete_Onboarding_Data_Spec` §J.1, Account Config 1, new Account Config 2 (Gym Memberships) interaction; `locale_profiles` table schema; `routes/locales.py` (eventual rewrite); new `chain_registry.py` module.
**Cross-references:**
- `Athlete_Onboarding_Data_Spec_v4.md` §J.1, §J.4, §J.5 (existing locale fields the design rewrites)
- `Project_Backlog_v15.md` D-59 (problem statement), D-60 (consumes chain_id for category default), D-61 (consumes coords for session→locale assignment)
- `D50_Phase1_Schema_Closing_Handoff_v1.md` (predecessor work; established the v4 spec context)
- `D50_Phase1_Schema_Review_v1.md` (predecessor work; confirmed CLAUDE.md stop-and-ask discipline)

---

## 1. Purpose

Replace v4 §J.1's vague "Place lookup → lat/long" with a concrete design covering: which third-party API, how chain identity is determined, what gets stored, how nearby chain instances surface, what happens when the API is unavailable, and how stale data gets refreshed.

The goal is to remove ambiguity and provide enough specificity that the spec rewrite (v5) can quote this doc verbatim and the eventual implementation PR can be scoped without re-litigating these choices.

---

## 2. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Geocoding provider | **Mapbox Geocoding API** | Generous free tier (100K requests/month free) covers expected v1 query volume by orders of magnitude. ~50% cheaper than Google at paid tier. Andy's call (2026-05-14) — accepts weaker chain metadata in exchange for cost predictability. Compensated by heavier manual chain registry (decision #2). |
| 2 | Chain detection mechanism | **Hybrid — registry primary, API backup** | Maintain a curated chain registry of ~30–50 entries (canonical name + name-pattern array). Mapbox Geocoding response's `text` and `properties` get pattern-matched against the registry. API hints (Mapbox returns `category: gym` and sometimes brand info) fill gaps. Most reliable; required because Mapbox's brand metadata is weaker than Google's. |
| 3 | Nearby-chain-instance discovery radius | **42.2 km / 26.2 mi** (same as §J proximity) | Reuses the marathon-distance threshold already specced for `proximity_cluster` in §J. Single radius keeps semantics simple — "if it's in your locale-cluster, it's also in your chain-instance pool." |
| 4 | Refresh cadence | **On-demand only — athlete-triggered** | Place data captured at locale creation is stored verbatim and never auto-refreshed. Athlete clicks a "Refresh from Mapbox" button per locale if they suspect staleness (rebrand, gym closed, chain takeover). Lowest cost; tolerates stale data as the most likely failure mode. |
| 5 | Manual address fallback | **Always available; degrades gracefully** | Athlete can choose "Enter address manually" instead of place lookup at any locale-creation step. Stored as: free-text address, no coords, no chain_id, manual_entry=TRUE. Athlete can later click "Look up on map" to upgrade to a Mapbox-anchored row. Required for: API down, athlete privacy preference, addresses Mapbox doesn't recognize (rural, new construction). |
| 6 | Privacy disclosure | **Inline at locale-creation, single acknowledgment per athlete** | First time the athlete uses place lookup, show: "We send your address to Mapbox (third-party geocoding) to look up coordinates and nearby gyms. See [privacy policy]." One acknowledgment is recorded in Account Config 3 (Disclosure Acknowledgment Records); subsequent locale creations don't re-prompt. Athletes who decline use the manual fallback path. |
| 7 | Chain registry storage | **Application-code Python module: `chain_registry.py`** | Not a Layer 0 table (curation cadence is "rare; rebrand-driven", not "ETL-pipeline"). Not a runtime DB row (no per-athlete data). Single module with a frozen tuple of dicts. Updates ship in code. Any future migration to a DB-backed registry can be a one-line swap of the lookup function. |
| 8 | Initial chain registry coverage | **~30 entries: large US fitness chains + climbing-gym chains relevant to Andy's training** | First-pass registry includes: Planet Fitness, LA Fitness, Anytime Fitness, YMCA, Equinox, Crunch Fitness, 24 Hour Fitness, Gold's Gym, Lifetime Fitness, Orangetheory, Snap Fitness, Blink Fitness, Retro Fitness, Movement (climbing), Planet Granite (climbing), Sender One, Brooklyn Boulders, Touchstone Climbing, Vertical World, Mesa Rim, plus regional chains in MN/WI as Andy identifies them. Full list draftable as a follow-on PR; not blocking. |

---

## 3. Mapbox Geocoding integration

### 3.1 Endpoints

Two Mapbox Geocoding API endpoints are used:

| Use case | Endpoint | Notes |
|---|---|---|
| Address autocomplete (athlete typing into Locale-creation form) | `GET /geocoding/v5/mapbox.places/{search_text}.json` | `autocomplete=true`, `types=poi,address`, `limit=5`. Single POI/address returned per result. |
| Nearby chain-instance discovery (after a locale is anchored) | `GET /geocoding/v5/mapbox.places/{chain_canonical_name}.json` | `proximity={lng},{lat}`, `bbox={derived from 42.2km radius}`, `types=poi`, `limit=10`. Bbox is the authoritative filter (Mapbox doesn't accept a true radius parameter; bbox approximates it). |

Reverse geocoding (coords → address) is not used in v1 — the athlete always starts from a search string.

### 3.2 Authentication

`MAPBOX_TOKEN` env var (a public-scope token, since the API is called from server-side Python where rotating secret-scope tokens isn't required). Add to `.env.example` as a non-required entry; locale features degrade to manual-entry fallback when unset.

### 3.3 Request/response shape

Standard Mapbox Geocoding response — `features[]` array, each carrying `place_name`, `text`, `center: [lng, lat]`, `properties.category`, `id` (the stable Mapbox `place_id` analog), and `context[]` (city/state/country breadcrumb). Server stores the relevant subset on `locale_profiles`; raw response goes to `place_payload TEXT` for audit.

### 3.4 Failure modes

| Failure | Behavior |
|---|---|
| `MAPBOX_TOKEN` unset | Place lookup UI hidden; manual-entry path is the only option. App boots normally. |
| Mapbox API 4xx (bad request, auth) | Show inline "Place lookup unavailable — enter address manually." Log to app error stream. |
| Mapbox API 5xx (their outage) | Same as 4xx. Retry once with 1s backoff before falling back. |
| Mapbox API rate-limit (HTTP 429) | Same as 5xx. Backlog item D-NN (TBD) tracks "if we hit 429s in production, switch to a per-user request token bucket." Not a v1 concern. |
| Mapbox returns 0 results | Show inline "No matches — enter address manually or try a different search." |
| Mapbox returns wrong address (athlete sees the picker, none match) | Athlete can reject and use manual entry. |

---

## 4. Chain detection — hybrid algorithm

### 4.1 Registry shape

`chain_registry.py`:

```python
GYM_CHAINS: tuple[dict, ...] = (
    {
        'chain_id': 'planet_fitness',
        'canonical_name': 'Planet Fitness',
        'name_patterns': (
            'planet fitness',
            'planet fit',
            'pf #',     # store-numbered locations
        ),
        'category': 'commercial_chain_gym',  # consumed by D-60
    },
    # … ~30 entries …
)
```

Patterns are lowercased substrings; matching is case-insensitive `in`-comparison. Patterns are intentionally lax (e.g., `'planet fit'` matches both "Planet Fitness" and "Planet Fitness Express").

### 4.2 Detection algorithm

When a Mapbox feature is selected as a locale anchor:

1. Lowercase the Mapbox `text` field (the place's primary name, e.g., `"planet fitness north loop"`).
2. Walk `GYM_CHAINS`. First entry whose any `name_patterns` substring is in the lowercased `text` wins.
3. If no registry match:
   - Inspect Mapbox `properties.category`. If it includes `gym`, `fitness`, or `climbing`, mark the locale as `chain_id=NULL, category='independent_gym'` (D-60 will later read this as a no-defaults case).
   - Otherwise mark `chain_id=NULL, category=NULL` (the locale isn't a gym at all — could be home, hotel, park, etc.).

### 4.3 Override path

If the registry mis-matches (e.g., a Planet Fitness location that's actually been bought by a different operator and renamed but the sign hasn't changed), athlete can manually set `chain_id` from a dropdown of all registry entries plus "None — independent" plus "None — not a gym."

---

## 5. Nearby chain-instance discovery

After a locale is anchored to a chain, the system runs one Mapbox Geocoding search per nearby-instance check:

1. Compute a bounding box around the anchor coords with the 42.2 km radius.
2. Mapbox query: `{chain_canonical_name}` with `proximity={anchor lng/lat}`, `bbox=…`, `types=poi`, `limit=10`.
3. Filter results by re-running the chain-detection algorithm — only Mapbox features whose chain_id matches the anchor's chain_id are surfaced.
4. Exclude the anchor itself (compare by Mapbox `id`).
5. Surface the remaining N instances in the locale-creation UI with: "We found N other [chain_canonical_name] locations within 42 km. Add any to your locale list?" + per-instance opt-in checkboxes.

When the athlete opts in to a nearby instance, a new `locale_profiles` row is created with `chain_id=anchor.chain_id`, equipment defaults inherited per D-60 design (when D-60 lands).

**Cost ceiling:** at locale-creation, this adds 1 Mapbox API call per chain-anchored locale. With Mapbox's 100K free monthly tier and Andy as the sole athlete, even pathological re-creation patterns stay well inside the free tier.

---

## 6. Manual fallback flow

| Step | Behavior |
|---|---|
| Athlete clicks "Enter address manually" link below the place-lookup search box | Place-lookup search box hides; free-text "Address" textarea + "Locale name" text input + "Type of location" dropdown (commercial gym / home / hotel / partner home / outdoor / other) appear. |
| Athlete fills in fields and saves | `locale_profiles` row inserted with `mapbox_id=NULL, lat=NULL, lng=NULL, chain_id=NULL, manual_entry=TRUE, category=<athlete's pick>`. |
| Later, athlete edits the locale and clicks "Look up on map" | Place-lookup search box reappears; if athlete picks a Mapbox feature, the row updates with coords + Mapbox id + chain detection runs. `manual_entry` flips to FALSE. |

Plan-gen reads `manual_entry=TRUE` rows as "no proximity-cluster membership" (since no coords) and "no chain default equipment" (D-60 design will treat these as `category='unknown'` requiring fully manual J.2 equipment entry).

---

## 7. Refresh & rebrand handling

Per decision #4: on-demand only. UX:

- Each locale row in `/locales` list view gets a "⟳ Refresh place data" link.
- Click triggers a fresh Mapbox lookup using the stored `mapbox_id`.
- If the lookup returns a feature whose name has changed, system shows: "This location was 'Planet Fitness — Main St' when you saved it; Mapbox now reports it as 'LA Fitness — Main St'. Update?" with Yes/No.
- On Yes: name + chain detection re-runs; `place_payload` overwritten; new chain_id stored.
- On No: athlete keeps the stale data; next refresh shows the same prompt.

If `mapbox_id` lookup returns 404 (location no longer in Mapbox's data), system flags the locale as "stale — Mapbox no longer recognizes this place" with options: re-search by name, manual fallback, or delete.

**No background refresh.** No cron. No login-time refresh. Athlete owns the cadence.

---

## 8. Privacy disclosure

First time an athlete uses place lookup (across any locale, any session), an inline disclosure appears above the search box:

> *"We send your address to Mapbox (third-party geocoding service) to convert it into coordinates and find nearby gyms. Mapbox's privacy policy is [linked]. AIDSTATION stores Mapbox's response (place name, coordinates, category) on your account; we don't share your locale list with Mapbox or anyone else. You can use manual address entry instead — see the link below the search box."*

Acknowledgment is captured as a row in `account_config_disclosure_acknowledgments` (Account Config 3) with `disclosure_id='mapbox_geocoding_consent'`, `version_id`, `acknowledged_at`. Athletes who haven't acknowledged see the disclosure each time until they click Acknowledge or pick manual fallback.

If athlete revokes (no UI for v1; they'd contact support), all `locale_profiles` rows lose their Mapbox-derived columns (`mapbox_id`, `lat`, `lng`, `place_payload`); chain associations are kept (athlete can re-set manually); proximity-cluster features go offline for that athlete.

**A.1 disclosure slot:** add to the v5 onboarding spec's §A.1 disclosures table: `Mapbox geocoding consent | At first place-lookup use | Per copy above. Stored in Account Config 3.`

---

## 9. Storage — `locale_profiles` schema additions

The current v1 `locale_profiles` table (per `routes/locales.py:70` + `init_db.py`) has columns `user_id, locale, notes, city, updated_at`. The v2 schema needs the following additions to support D-59:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `locale_name` | TEXT | (existing `locale` repurposed) | Display label per §J.1. v1 uses a hardcoded enum; v2 replaces with athlete-supplied text. |
| `mapbox_id` | TEXT | NULL | Stable Mapbox feature identifier; primary key for re-lookups. NULL for manual-entry rows. |
| `lat` | REAL | NULL | Latitude (decimal degrees). NULL for manual-entry rows. |
| `lng` | REAL | NULL | Longitude (decimal degrees). NULL for manual-entry rows. |
| `chain_id` | TEXT | NULL | FK-style reference to `GYM_CHAINS[i].chain_id` in `chain_registry.py`. NULL for non-gym, independent gym, or manual-entry rows. |
| `chain_name` | TEXT | NULL | Denormalized canonical name from the registry (so display doesn't need a registry lookup on every query). NULL when `chain_id` is NULL. |
| `category` | TEXT | NULL | Locale type — set by D-59 (chain detection: `commercial_chain_gym` / `independent_gym` / NULL); refined by D-60 design (`home_gym` / `hotel_gym` / `climbing_gym` / `outdoor` / etc.). |
| `manual_entry` | BOOLEAN | FALSE | TRUE when athlete bypassed Mapbox; gates plan-gen behavior. |
| `place_payload` | TEXT | NULL | Raw Mapbox response JSON for audit; not consumed at runtime. |
| `place_fetched_at` | TIMESTAMP | NULL | Timestamp of the Mapbox call that populated `place_payload`. NULL for manual-entry. |

**Migration approach:** since v1 has 1–2 test accounts and no real production data, the migration is a single `ALTER TABLE locale_profiles ADD COLUMN …` per new column on `_PG_MIGRATIONS` only (per the `_SQLITE_MIGRATIONS` freeze ratified in `Athlete_Data_Integration_Spec_v4` §2.5). The hardcoded `locale` enum (`['home', 'hotel', 'partner', 'airport']`) is replaced with athlete-supplied text; existing rows retain their enum value as their initial `locale_name`.

The schema migration itself is **out of scope for this design doc** — it lands as part of the Onboarding v5 implementation PR, not now.

---

## 10. Cross-track interactions

| Track | What D-59 hands off |
|---|---|
| **D-60** Gear from proximity | `chain_id` (registry pointer, has `category` field) and `category` (locale-level) provide the keys D-60 uses to look up default equipment manifests. D-60 design defines the manifests per category; D-59 just establishes how the category is determined. |
| **D-61** Session time → plan | `lat` / `lng` provide the geographic coords D-61 uses for "closest qualifying locale by equipment" assignment. D-59 establishes that coords exist (for non-manual-entry rows); D-61 design defines the assignment algorithm. |
| **D-58** OAuth-first flow | No direct interaction. D-58 prefills §A/B/C/F from integration data; D-59 is locale data athletes type/lookup themselves. |

D-60 and D-61 design docs land next; both can quote the storage shape from §9 above as the integration point.

---

## 11. What this design doc explicitly does NOT cover

- Chain registry initial 30-entry seed values (drafted as a follow-on PR; this doc commits to the shape, not the specific entries).
- The v5 spec rewrite of §J.1 incorporating these decisions (lands after D-60 + D-61 design docs settle).
- The implementation PR (`chain_registry.py` module + `routes/locales.py` rewrite + `locale_profiles` migration).
- Privacy policy text (legal/product owns; this doc only commits to the disclosure slot existing).
- Any non-gym place-lookup use case (events, races, partner homes get the same lookup but no chain semantics).

---

## 12. Gut check

**What this design got right.**

- **Mapbox over Google was Andy's call, not the recommendation.** The recommendation was Google for chain-metadata coverage; Andy chose Mapbox for cost predictability. The design absorbs the choice cleanly — heavier registry compensates for weaker brand metadata. No silent override of the user.
- **Hybrid registry + API is the robust choice.** Either alone is fragile (registry-only misses long-tail chains; API-only misses small chains and cross-chain rebrands). Hybrid catches both, at the cost of a small upkeep burden — patch the registry when a new chain becomes relevant.
- **On-demand refresh respects the cost-conscious provider choice.** Background refresh would multiply Mapbox API calls per athlete-month; on-demand keeps the call count tied to actual locale changes.
- **Manual fallback is a first-class path, not a hack.** Athletes who don't want their addresses going to Mapbox have a real, supported alternative. The fallback row is just a different shape, not a degraded shape.
- **42.2 km consistency is genuinely simpler.** One radius for proximity + chain surfacing means one number to explain in the UX and one threshold to debate when athletes ask why a particular locale was/wasn't surfaced.

**Risks.**

- **Mapbox's chain coverage is going to disappoint.** The free-tier-cost win is real, but expect to discover that Mapbox returns "Planet Fitness #234" while Google would return "Planet Fitness" with `business_status: OPERATIONAL` and a clean brand field. The hybrid registry helps, but the registry will need patches as Andy and future athletes onboard at chains the initial 30-entry list missed.
- **The 42.2 km radius is generous for chain surfacing.** Athletes near city centers may see 8+ Planet Fitness locations within 42 km; the per-instance opt-in UX needs to scroll cleanly. If this becomes UX clutter in production, the multi-tier fallback (8 km auto-surface, 42.2 km opt-in) is the next iteration.
- **No background refresh = stale data.** When Planet Fitness #234 closes or rebrands, the athlete's locale row keeps the old data until they manually refresh. They might never refresh. Acceptable for v1 (stale data degrades gracefully — the equipment defaults are still mostly right, the chain category is unchanged) but a real risk if a chain mass-rebrands.
- **Mapbox token in env-var means single-tenant rate limit.** All athletes share the 100K/month free tier. Per-tenant scaling would need a different cost model. v1 has one athlete; not a v1 concern.
- **Privacy disclosure may itself be a friction point.** Athletes who've never thought about geocoding privacy now have to make a decision. Some will pick manual entry just to avoid the prompt — and lose chain detection + nearby surfacing. Tradeoff is unavoidable; honest disclosure beats silent data exfiltration.

**What might be missing.**

- **`category` semantics for non-gym locales.** This doc commits `category='commercial_chain_gym'` / `'independent_gym'` / NULL. D-60 design will need: home, hotel, climbing-gym (chain vs. independent), pool, outdoor (trail/park). D-60 owns the full taxonomy; D-59 just establishes the column. If the D-60 taxonomy turns out to need richer detection signals, this doc will need a small amendment.
- **Chain detection for non-fitness locales.** If athlete adds a hotel locale, hotel chain detection (Marriott, Hilton, IHG) might also be useful — hotel chains often have predictable on-property gym profiles. Out of scope for v1; backlog candidate after launch.
- **Mapbox's coord precision policy.** Mapbox returns coords to ~6 decimal places (sub-meter precision). For locale clustering, even 2 decimal places (~1 km) is plenty. We store full precision and don't truncate. If at some point Andy wants to reduce on-disk precision for privacy, that's a one-line change.
- **No deletion cascade for `chain_registry.py` removals.** If a chain entry is removed from the registry (rare — only for misclassified entries), `locale_profiles` rows pointing at it via `chain_id` become orphaned. v1 cost is negligible; flag for v2 cleanup.

**Best argument against this design.**

You could argue the entire chain-detection layer is overengineered for v1. Andy is one athlete; he knows which gyms are Planet Fitness; he can just type the chain into a dropdown. The registry + Mapbox API + hybrid algorithm + nearby-surfacing UX is a lot of code for what could be a single dropdown.

Counter: chain detection is the foundation D-60 needs. D-60's whole value proposition is "you don't have to enumerate equipment per locale; we infer it from the chain." If the chain identification is manual-dropdown-only, D-60 collapses to "athlete picks chain from dropdown, system applies pre-curated defaults" — which is fine for v1, but loses the whole D-59 → D-60 → D-61 chain (chain identity → category default → equipment-qualified locale assignment). Building D-59 properly preserves the design wave's leverage.

Alternative: ship the dropdown-only variant for the v1 implementation and add the Mapbox layer in a v1.1 patch. Reasonable phasing if implementation budget is tight; the design doc as written supports that staging by treating manual entry as a first-class path.

---

*End of D-59 design doc. Next: D-60 design — gear-from-proximity, category default equipment manifests, per-instance override semantics.*
