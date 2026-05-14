# Onboarding D-60 Design — Shared Gym Profiles + Locale Category Taxonomy

**Version:** 1.0
**Date:** 2026-05-14
**Status:** Design decisions locked; spec rewrite pending (`Athlete_Onboarding_Data_Spec_v5.md` lands after all four design tracks settle).
**Backlog row:** D-60
**Track:** Second of the four-track Onboarding Design Wave (D-58–D-61). Sequence: D-59 ✅ → **D-60 (this doc)** → D-61 → D-58.
**Affects:** `Athlete_Onboarding_Data_Spec` §J.2, §J.3, Account Config 1; new `gym_profiles` table (shared across users); `locale_profiles.gym_profile_id` FK column; `locale_equipment` provenance columns; eventual `routes/locales.py` rewrite.
**Cross-references:**
- `Onboarding_D59_Design_v1.md` — establishes `mapbox_id`, `chain_id`, `category` on `locale_profiles`; D-60 reads `mapbox_id` as the gym-profile join key.
- `Athlete_Onboarding_Data_Spec_v4.md` §J.2 (Equipment Inventory — 121-item canonical list), §J.3 (12 sport-specific gear toggles).
- `Project_Backlog_v15.md` D-60 (problem statement; reframed by this doc).

---

## 1. Purpose

The v4 spec has §J.2 (manual equipment checklist against 121 canonical items × 17 categories) and §J.3 (12 sport-specific gear toggles), both filled in by the athlete per locale. The D-60 backlog row asked: should equipment be inferred from a locale's category / chain identity rather than enumerated by the athlete?

**Andy's answer (2026-05-14): no inferences.** Chain identity is a discovery aid (D-59 surfacing of nearby same-chain locations); it does NOT imply equipment. Category is informational (filtering, display); it does NOT imply equipment either.

The alternative Andy chose: **per-physical-address shared gym profiles, crowd-sourced across all AIDSTATION users**. First athlete at a given address builds the equipment profile; subsequent athletes at the same address inherit it (with per-athlete override). The system never invents what equipment a gym has — it either knows (a real athlete built the profile) or it doesn't (athlete in front of an unprofiled gym has to build it).

This reframes D-60 from "design category-default manifests" to "design a shared, crowd-sourced gym-equipment database keyed by physical location."

---

## 2. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Equipment inference | **None. No inference from chain or category.** | Andy 2026-05-14. Inference at the chain level is wrong on a per-store basis (Planet Fitness #234 vs. #235 can differ materially); at the category level it's even worse (every "commercial_chain_gym" being the same is a fiction). |
| 2 | Equipment source-of-truth | **Per-address shared gym profile.** Keyed by `mapbox_id` (or address-equivalent fallback for manual-entry locales). Equipment list + §J.3 toggles live in `gym_profiles`. | Real-world equipment is physical-address-specific. Crowd-sourcing across enterprise users means the second athlete to onboard at a given gym inherits the first athlete's curation. |
| 3 | Contribution model | **Default-on crowd-sourcing.** When an athlete creates or modifies a gym profile, the change is shared by default. Athlete can opt out at the account level (Account Config setting). | Andy 2026-05-14 — "crowd sourced equipment data" implies opt-out, not opt-in. Aligns with "AIDSTATION is multi-tenant; the second athlete shouldn't have to re-enumerate what the first already captured." |
| 4 | Per-athlete override | **Two-layer model.** Shared `gym_profiles.equipment` is the base. Per-athlete deltas (`locale_equipment_overrides`) capture corrections specific to one athlete's view. Plan-gen for athlete X reads: shared profile + athlete X's overrides (overrides win). | Athletes can disagree without polluting each other's view. Overrides can later be promoted to shared (athlete explicitly "submit as correction"). |
| 5 | Conflict resolution between athletes | **Last-Writer-Wins on the shared profile, with provenance display.** Most recent shared confirmation defines the active shared row. Athletes see "Last confirmed by another athlete on YYYY-MM-DD" + a "disputed?" affordance that flips equipment items to "disputed" status if they disagree. Active disputes show both signals; plan-gen treats "disputed" items as not-available. | Simple. Honest about uncertainty. Avoids voting/curator-review overhead at v1. Disputes are operational signal, not algorithmic resolution. |
| 6 | Confidence model for plan-gen | **Binary: available / not available.** Inferred-vs-confirmed distinction collapses to "is the equipment in this athlete's effective view of this gym profile, yes or no." Disputed items are not-available. | Andy 2026-05-14 — "available or not available." Simplifies plan-gen reads. Provenance information is preserved at the storage layer for future surfacing but doesn't affect plan-gen's go/no-go on a given exercise. |
| 7 | §J.3 sport-specific gear toggles | **Live on the shared gym profile alongside §J.2 equipment.** Same model: first athlete at the gym sets them; subsequent athletes inherit + can override per-athlete; default-shared. | Consistent with §J.2 treatment. "No inferences" applies equally — the system doesn't guess that a climbing-gym category has roped climbing; the first climber at the address establishes that. |
| 8 | Locale category taxonomy | **Medium flat — ~10 categories.** Final list: `commercial_chain_gym`, `independent_gym`, `hotel_gym`, `home_gym`, `climbing_gym_chain`, `climbing_gym_indie`, `pool_indoor`, `pool_outdoor`, `outdoor_park`, `other_residence`. Renamed `partner_home` → `other_residence` per Andy 2026-05-14 (covers in-laws, friends, AirBnB, etc. — not strictly partner). | Single-level enum; small enough to populate as a dropdown; large enough to drive useful display filtering and to distinguish "expect a shared profile" categories (the four gym-flavors + two pool-flavors) from "no shared profile" categories (home_gym, other_residence, outdoor_park). |
| 9 | Categories that imply a shared profile | **The six gym-flavor + pool-flavor categories.** Categories where shared profiles are expected: `commercial_chain_gym`, `independent_gym`, `hotel_gym`, `climbing_gym_chain`, `climbing_gym_indie`, `pool_indoor`, `pool_outdoor`. Categories where they are NOT: `home_gym`, `outdoor_park`, `other_residence` (no `gym_profile_id` FK set; athlete builds their own equipment list per the v4 §J.2 pattern). | Home gyms are athlete-specific (no public address; sharing other people's home equipment is a privacy violation). Outdoor parks aren't equipment-fixed (a park's "equipment" is its terrain, not its kit). Other-residence locales are private. |

---

## 3. Locale category taxonomy

Final v5 taxonomy (replaces v4 §J.2's implicit "athletes always type their own equipment" model):

| `category` value | Display label | Has shared gym profile? | Notes |
|---|---|---|---|
| `commercial_chain_gym` | Commercial gym (chain) | Yes | Set by D-59 chain detection. |
| `independent_gym` | Commercial gym (independent) | Yes | Set by D-59 when chain not detected and Mapbox `category` matches gym/fitness. |
| `hotel_gym` | Hotel gym | Yes | Athlete-picked. Often basic equipment; profile typically small. |
| `climbing_gym_chain` | Climbing gym (chain) | Yes | D-59 chain detection covers chains like Movement, Sender One, Touchstone, Brooklyn Boulders. |
| `climbing_gym_indie` | Climbing gym (independent) | Yes | The unbranded local climbing gym. |
| `pool_indoor` | Indoor pool | Yes | Lap pools, YMCAs, athletic clubs. |
| `pool_outdoor` | Outdoor pool | Yes | Public pools, neighborhood pools. |
| `home_gym` | Home gym | No | Per-athlete; no shared profile. |
| `outdoor_park` | Outdoor / trail / park | No | Equipment-irrelevant; locale's value is its terrain (terrain access lives on `locale_profiles` per §J.4). |
| `other_residence` | Other residence | No | In-laws, friend's house, AirBnB. Per-athlete; equipment list is per-athlete or empty. |

**Category is set by:** (a) D-59 detection where possible (`commercial_chain_gym` / `independent_gym` / climbing variants from chain detection + Mapbox category hints); (b) athlete picker for everything else.

**Category is mutable.** Athlete can change a locale's category any time (e.g., a place they thought was a chain gym turns out to be independent). Changing from a "has shared profile" category to a "no shared profile" category orphans the FK; changing the other way prompts the athlete to either link to an existing profile or start a new one.

---

## 4. Shared gym profile model

### 4.1 The fundamental claim

Every physical-address gym has exactly one shared `gym_profiles` row in the AIDSTATION database. Multiple `locale_profiles` rows (across multiple users) point at it via `gym_profile_id` FK. The profile carries equipment availability + §J.3 toggles + provenance metadata.

### 4.2 First-athlete-creates flow

When athlete A creates a locale that resolves to a `mapbox_id` not yet in `gym_profiles`:
1. System asks A: "We don't have an equipment profile for this gym yet — want to build one? (You can also skip and add equipment later)."
2. If A builds: the athlete completes a §J.2 equipment checklist (canonical 121-item list) + §J.3 toggles. On save, a `gym_profiles` row is created with A's data and `created_by_user_id = A`. A's `locale_profiles` row gets `gym_profile_id = <new row id>`.
3. If A skips: `locale_profiles.gym_profile_id = NULL` for now. A can later either create the profile or link to one (if a peer creates it in the meantime).

### 4.3 Subsequent-athlete-inherits flow

When athlete B creates a locale at the same `mapbox_id`:
1. System detects an existing `gym_profiles` row for that `mapbox_id`.
2. UI shows: "Another athlete built an equipment profile for this gym, last confirmed on YYYY-MM-DD. Want to inherit it?" + preview of equipment list and toggles.
3. If B inherits: `locale_profiles.gym_profile_id = <existing row id>`. B's effective view of equipment is the shared profile. No `locale_equipment_overrides` yet.
4. If B declines and builds their own: B is creating an override-only profile from the start. The shared row is unchanged; B's locale operates purely from overrides.

### 4.4 Per-athlete override

Plan-gen for athlete X at locale L reads equipment as:

```
effective_equipment(X, L) =
  (shared_profile.equipment ∪ X's overrides where action='add')
  ∖ (X's overrides where action='remove')
  ∖ (any equipment with disputed=TRUE on the shared profile, unless X explicitly added it back)
```

Same shape for §J.3 toggles.

Overrides are stored as rows in a new `locale_equipment_overrides` table, keyed by `(user_id, locale_id, equipment_id, action)` where `action ∈ ('add', 'remove')`. §J.3 toggle overrides live in a parallel `locale_toggle_overrides` table.

### 4.5 Submit-as-correction (override → shared)

When athlete X has been operating with overrides for a while and confirms their version is correct (button: "submit my equipment list as a correction to the shared profile"):
1. System computes the "submitted profile" = current shared profile + X's overrides applied.
2. UI confirmation: "You're about to update the shared profile for [gym name]. Other athletes' overrides remain in place. Continue?"
3. On confirm: shared profile updates; X's overrides are zeroed out (they're now reflected in the shared view); `last_confirmed_by` and `last_confirmed_at` update.
4. Other athletes' next session at this locale: their inherit/override view recomputes from the new shared base.

### 4.6 Dispute flow

When athlete X's override on a specific equipment item conflicts with the shared profile (e.g., shared says "cable machine YES"; X removes it), X can mark the item as "disputed":
1. UI: "I think the shared profile is wrong about cable machine. Mark as disputed?"
2. On confirm: `gym_profiles.disputed_items` JSON array gains the equipment_id. X's override remains in place for X.
3. Other athletes at this locale see "[Cable machine] — disputed by 1 athlete. Confirm what you see?" with their own override option.
4. Once the dispute is resolved (an athlete submits a correction; or the item gets enough "I confirm" clicks from other athletes — TBD, see §10), the disputed flag clears.

For plan-gen: any item with `disputed=TRUE` is treated as not-available for any athlete who has not explicitly overridden it (in either direction).

### 4.7 Crowd-sourcing consent + opt-out

Default behavior: athlete's gym-profile contributions are shared. Single account-level toggle: "Contribute my gym-equipment edits to the shared AIDSTATION gym database (default on)." When off:
- Athlete's new gym profile creations stay private (`gym_profiles.private=TRUE` + `created_by_user_id=X`).
- Athlete's overrides on shared profiles stay athlete-local (no submit-as-correction button; if athlete tries, prompt to enable sharing).
- Other athletes at the same `mapbox_id` see the locale as "no shared profile yet" until a sharing athlete creates one.

Privacy disclosure when sharing is enabled (one-time inline at first gym-profile creation, stored as Account Config 3 acknowledgment):

> *"Your equipment edits at commercial gyms, climbing gyms, and pools will be shared with other AIDSTATION athletes who train at the same locations. Your name and identity are never shared — only the equipment list and the date it was last confirmed. Home gyms and private residences are never shared. You can opt out at any time in account settings; existing contributions remain unless you delete them."*

---

## 5. Schema additions

All new tables and columns land on `_PG_MIGRATIONS` only — `_SQLITE_MIGRATIONS` remains frozen per `Athlete_Data_Integration_Spec_v4` §2.5.

### 5.1 New table — `gym_profiles`

```sql
CREATE TABLE IF NOT EXISTS gym_profiles (
    id                    SERIAL PRIMARY KEY,
    mapbox_id             TEXT UNIQUE,
        -- Stable place identifier from D-59 Mapbox lookup. UNIQUE enforces
        -- one shared profile per physical address. NULL only for manual-
        -- address fallback profiles (rare; private by default).
    address_fingerprint   TEXT,
        -- Fallback dedup key for manual-entry profiles: normalized address
        -- string (lowercase, whitespace-collapsed, abbreviation-expanded).
        -- NULL when mapbox_id is set.
    display_name          TEXT,
        -- Human-readable gym name. Sourced from Mapbox `text` field at
        -- creation. Editable by any contributing athlete.
    category              TEXT NOT NULL,
        -- One of the seven 'has shared profile' categories in §3.
    equipment             TEXT,
        -- JSON array of canonical equipment_item tag strings.
    toggles               TEXT,
        -- JSON object: {toggle_canonical_name: bool} for the 12 §J.3 toggles.
    disputed_items        TEXT,
        -- JSON array of equipment_item tags currently flagged disputed.
        -- See §4.6.
    private               BOOLEAN DEFAULT FALSE,
        -- TRUE when created by an athlete with sharing disabled.
        -- private=TRUE rows are visible only to created_by_user_id.
    created_by_user_id    INTEGER REFERENCES users(id),
    created_at            TIMESTAMP DEFAULT NOW(),
    last_confirmed_by     INTEGER REFERENCES users(id),
    last_confirmed_at     TIMESTAMP DEFAULT NOW(),
    contribution_count    INTEGER DEFAULT 1
        -- Total number of athletes who have inherited or contributed to
        -- this profile (informational; surfaced to subsequent athletes as
        -- "N athletes have used this profile").
);

CREATE INDEX IF NOT EXISTS gym_profiles_mapbox_idx
    ON gym_profiles (mapbox_id) WHERE mapbox_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS gym_profiles_address_idx
    ON gym_profiles (address_fingerprint) WHERE address_fingerprint IS NOT NULL;
```

**Why JSON for equipment + toggles, not normalized tables?** v1's `locale_equipment` is a normalized join table because each row is athlete-scoped (per `(user_id, locale, equipment_id)`). The shared profile is global; it's read whole and written whole. JSON is simpler, indexable on substring-search if needed, and avoids the (gym_profile_id, equipment_id) cross-product churn on every update.

### 5.2 New table — `locale_equipment_overrides`

```sql
CREATE TABLE IF NOT EXISTS locale_equipment_overrides (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    locale_id         INTEGER NOT NULL REFERENCES locale_profiles(id),
    equipment_tag     TEXT NOT NULL,
        -- Canonical tag from the 121-item equipment list.
    action            TEXT NOT NULL,
        -- 'add' (athlete has this; shared profile doesn't list it)
        -- 'remove' (athlete confirms this isn't here; shared profile lists it)
    created_at        TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, locale_id, equipment_tag, action)
);

CREATE INDEX IF NOT EXISTS leo_user_locale_idx
    ON locale_equipment_overrides (user_id, locale_id);
```

### 5.3 New table — `locale_toggle_overrides`

```sql
CREATE TABLE IF NOT EXISTS locale_toggle_overrides (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    locale_id         INTEGER NOT NULL REFERENCES locale_profiles(id),
    toggle_name       TEXT NOT NULL,
        -- Canonical §J.3 toggle name (12-value enum).
    value             BOOLEAN NOT NULL,
        -- Athlete's belief about this toggle for this locale.
    created_at        TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, locale_id, toggle_name)
);
```

### 5.4 Additions to `locale_profiles`

```sql
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS gym_profile_id INTEGER REFERENCES gym_profiles(id);
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS sharing_opt_out BOOLEAN DEFAULT FALSE;
    -- Mirror of account-level setting at locale-creation time; lets athlete
    -- override per-locale (e.g., "share my gym contributions but not for
    -- my home base, which I want kept private even though it's at a
    -- commercial address").
```

### 5.5 Migration of existing `locale_equipment`

Per backlog D-60: "1–2 test accounts so trivial." The existing `locale_equipment` rows reflect Andy's current locale equipment lists; the migration approach is:

1. For each existing `locale_profiles` row, check whether a `gym_profiles` row exists for its `mapbox_id` (will be NULL for all rows pre-D-59; this is genuinely a new schema).
2. If not: rows stay as-is in `locale_equipment` (Andy's current equipment lists remain his private view) until he opts in by either (a) re-anchoring the locale via Mapbox lookup, or (b) explicitly migrating it to the shared model.
3. No automatic conversion at the data layer — the migration is athlete-driven through the new UI.

This is a coexistence migration. `locale_equipment` (old, per-user) and `gym_profiles` + `locale_equipment_overrides` (new, shared) live side-by-side. Plan-gen reads athlete's effective equipment as:

```
if locale.gym_profile_id IS NOT NULL:
    effective = compute_from_shared_profile(locale.gym_profile_id, user_id)
else:
    effective = legacy_locale_equipment_for(user_id, locale.id)
```

When all of Andy's locales have been migrated (athlete-driven), `locale_equipment` can be deprecated. Not a v1-launch concern.

---

## 6. Cross-track interactions

| Track | What D-60 hands off | What D-60 consumes |
|---|---|---|
| **D-59** Place lookup + chain detection | — | `locale_profiles.mapbox_id` (gym profile join key) and `locale_profiles.category` (gates whether to expect a shared profile). |
| **D-61** Session time → plan | Per-athlete effective equipment view (shared profile + overrides) for the locale-assignment step. D-61 reads "qualifying locale by equipment" against this effective view, not the bare shared profile. | — |
| **D-58** OAuth-first flow | No direct interaction. Provider integrations don't surface gym equipment. | — |

---

## 7. What this design doc explicitly does NOT cover

- **Curator / admin moderation UI.** When a dispute can't be resolved peer-to-peer, who arbitrates? Out of scope for v1; backlog candidate D-NN after sufficient dispute volume surfaces (initially Andy is the only user; disputes won't exist).
- **Voting-based dispute resolution.** "N confirmations override a single dispute" is plausible but adds state machine complexity. Defer until cohort behavior justifies it.
- **Equipment-list versioning.** v1 treats the canonical 121-item list as the source of truth for equipment tags. If a new item is added later (e.g., "trap bar" wasn't on the v4 list but should have been), the shared profiles need to be checked against new entries. Not a v1 concern.
- **Crowd-sourced equipment quality ratings.** "This gym has dumbbells but they're rusty / mismatched / topping out at 50 lb" is real signal but a different schema. Backlog candidate post-launch.
- **The implementation PR.** `gym_profiles` migration + `routes/locales.py` rewrite + UI for inherit / override / dispute / submit-as-correction is a substantial implementation effort. Lands as part of the v5 onboarding implementation, not this design doc.
- **Geographic edge cases.** Gym at a multi-tenant building where Mapbox returns the building, not the gym suite — manual `address_fingerprint` path catches this but ugly. Backlog item.

---

## 8. Gut check

**What this design got right.**

- **Honored Andy's "no inferences" reframe completely.** The original D-60 backlog row asked for category-default manifests; Andy rejected the premise. This doc absorbs the rejection and rebuilds D-60 around the per-address shared-profile alternative. No silent re-introduction of inference; the system genuinely refuses to guess.
- **Crowd-sourcing as default-on with a privacy-respecting opt-out.** Matches the "AIDSTATION is multi-tenant SaaS" reality. Athletes contribute by default because the network effect is the value proposition; opt-out exists for athletes who don't want their private gym profile contributing to the shared knowledge base.
- **Home gyms and other-residence stay private by category.** No shared profile FK; equipment is per-athlete only. Privacy-by-design for the locales where it matters most.
- **Override-first design.** Plan-gen reads athlete's effective view, not the raw shared profile. Disagreement with the crowd doesn't break plan-gen for the disagreeing athlete.
- **Last-Writer-Wins + provenance display is honest.** No pretense of algorithmic dispute resolution at v1. Athletes see who last confirmed; athletes can dispute; disputes show up as "verify in person." Matches the "evidence-grounded, no platitudes" coaching voice — the system says "we're not sure" instead of inventing a confidence number.
- **Category taxonomy is small enough to commit to and large enough to filter on.** Andy's `other_residence` rename caught a real conceptual gap (`partner_home` was too narrow); the 10-category enum covers what athletes actually distinguish.

**Risks.**

- **Crowd-sourcing requires a crowd.** Andy is the only test athlete. The shared-profile model only delivers value at N≥2 athletes per address. For v1 launch, the system effectively behaves like "Andy builds profiles for everywhere he trains; nobody else inherits." That's the same outcome as v4 §J.2 (per-athlete equipment list) — the gym-profile abstraction is overhead until the second athlete shows up. Justification: building it later means migrating Andy's data; building it now is cheap.
- **Conflict-resolution UX is underspecified.** "Last-writer-wins + disputed flag" works for two-athlete disagreements; doesn't scale to 50-athlete divergent views. v1 doesn't need to scale that far, but the design doesn't pre-stage the path to richer conflict resolution. If cohort hits 100+ athletes at a popular chain (a single Planet Fitness location), the design needs a v2 iteration.
- **Dispute decay isn't designed.** A disputed item stays disputed until someone resolves it. If the original disputer leaves the cohort, the dispute lingers indefinitely. Mitigation: "auto-resolve dispute after 6 months of no new activity" — not specced here; backlog item.
- **The override tables grow with the cohort.** `locale_equipment_overrides` has up to (athletes × locales × equipment-items) rows in the worst case. For Andy alone, negligible. For 1000 athletes × 5 locales × 20 equipment overrides each = 100K rows. Plan-gen reads need an index on `(user_id, locale_id)` — provided. Not a near-term scaling concern.
- **Shared profile vandalism risk.** A bad-actor athlete could submit garbage equipment lists to corrupt the shared view. v1 mitigation: provenance display lets athletes see "last confirmed by user_id N" and override locally. v2 would need rate-limiting on shared submissions + admin moderation tools. Out of scope.
- **Mapbox-id uniqueness is the bedrock.** If two athletes anchor to the same physical address but Mapbox returns different `mapbox_id` values for the same place (e.g., one athlete searches by name, another by street address; Mapbox may return distinct POI vs. address-point ids), they end up with two separate shared profiles. v1 mitigation: rely on Mapbox stability + treat `address_fingerprint` as a secondary dedup key. Real-world failures may surface; flag for v2.

**What might be missing.**

- **Per-athlete "show me what I should verify" surfacing.** Athletes who inherit a shared profile should periodically be prompted: "It's been 90 days since you confirmed your equipment at [gym]; want to re-verify?" Not specced — could ship as part of the v5 implementation as a soft suggestion. Captured implicitly in the `last_confirmed_at` column.
- **Bulk override pattern.** If Andy moves from one chain gym to another within the same chain, his overrides from gym A don't auto-apply to gym B (they're locale-scoped, not gym-pattern-scoped). Probably correct (physical addresses really do differ), but a "copy my override pattern from another locale" affordance would save time. Backlog item.
- **Equipment count / quantity not captured.** "Dumbbells 5–50 lb" vs. "Dumbbells 5–120 lb" matters for plan-gen. The canonical 121-item list captures it where it's discriminating (different tags for different dumbbell ranges); not all gyms differentiate. If a gym has the "Dumbbells (full set)" tag but tops out at 50 lb, plan-gen could prescribe a 70-lb lift that fails. v1 mitigation: rely on the canonical list's discrimination + athlete override. Per-quantity refinement is a v2 backlog item.
- **Cross-gym chain consistency hint.** Even though "no inferences," it would be useful to surface "this Planet Fitness has different equipment than the Planet Fitness you visited last month" as a sanity check at gym-profile creation. Not specced; backlog item if athletes complain about re-entering equipment for each PF.
- **Account Config 1 (Connected Services) interaction.** None obvious — gym equipment is athlete-curated, not provider-derived. Worth confirming during v5 spec rewrite.

**Best argument against this design.**

The whole shared-profile abstraction is premature for a single-user product. Andy alone derives zero value from crowd-sourcing his own data; the shared-profile schema, override tables, dispute machinery, and consent UX are all overhead that only pays off at multi-user scale. A simpler v1: keep `locale_equipment` per-user, ship the v5 spec around per-user enumeration, add the shared-profile layer in a v2 when cohort growth justifies it.

Counter: the migration cost from "per-user equipment lists" to "shared profile + per-user overrides" is non-trivial (existing rows need to be classified as shared-eligible or private, mapbox_ids retroactively assigned to old locales, etc.). Building it now while Andy is the sole user means the migration is one user's data; building it later means migrating every athlete onboarded between launch and v2. Andy's "push to production as we go" rule biases toward "ship the right abstraction now," which this design is. The cost is the implementation effort, paid once.

Alternative phasing: ship the per-user enumeration in the v5 implementation PR (matches v4 §J.2's pattern); add the shared-profile layer as a v5.1 patch once the second test athlete onboards. Reasonable defer if implementation budget is tight. The design doc as written supports this staging — the schema additions are forward-compatible (existing `locale_equipment` rows coexist with the new model; migration is athlete-driven).

---

*End of D-60 design doc. Next: D-61 design — session time tied to plan, not locale; locale assignment per session; max-session-duration semantics as locale equipment/safety constraint.*
