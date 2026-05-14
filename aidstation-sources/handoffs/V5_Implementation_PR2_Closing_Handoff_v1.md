# V5 Onboarding Implementation PR2 — Closing Handoff

**Session:** Second substantive code session of the v5 onboarding implementation arc. Executes PR1 handoff §5.4 (backlog v15 → v16 bump) **plus** Option A from PR1 §5.1 (D-59/60/61 schema PR). PG-only schema half of the rest of the onboarding design wave.
**Date:** 2026-05-14
**Predecessor handoff:** `V5_Implementation_PR1_Closing_Handoff_v1.md` (its §5.4 + §5.1 Option A are what this session executes).
**Branch:** `claude/review-v5-handoff-t7KBL`
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 frontend (locale lookup, chain-detection UX, shared gym profile inherit/override/dispute, per-day windows form) and `_SQLITE_MIGRATIONS` are out of scope per Integration v4 §2.5 freeze. PR3+ candidates unchanged from PR1 §5.1.
**Time-on-task:** Single chat. Substantive files: **4** (init_db.py, chain_registry.py [new], Project_Backlog_v16.md [new], aidstation-sources/CLAUDE.md). Plus this handoff (5 total — at the ceiling per CLAUDE.md "5-file quality ceiling per session," and one under the one-over-ceiling pattern PR1 hit).

---

## 1. Session-start verification (Rule #9)

Verified the PR1 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| PR1 commit `3628ca6` merged to main; working tree clean on `claude/review-v5-handoff-t7KBL` (branch off post-merge main) | `git log --oneline -5` + `git status` | ✅ Verified |
| `init_db.py` `_PG_MIGRATIONS` contains all 3 D-58 tables (`athlete_profile_field_provenance`, `account_nudges`, `disclosure_acknowledgments`) | `grep -c "CREATE TABLE IF NOT EXISTS … "` returns 3 | ✅ Verified |
| `routes/provider_auth.py` exists (160 lines) | `wc -l` | ✅ Verified (160 lines on disk vs. PR1 handoff §2's "~145 lines" — within `~` tolerance) |
| `routes/coros.py` rewrite present (342 lines) | `wc -l` | ✅ Verified (342 lines on disk vs. PR1 handoff §2's "341 lines" — off-by-one is the standard discrepancy band) |
| `routes/coros_ingest.py` exists (242 lines) | `wc -l` | ✅ Verified (242 lines on disk vs. PR1 handoff §2's "~205 lines" — within `~` tolerance) |
| `routes/oauth_callbacks.py` `_PROVIDERS` does NOT contain `'coros'` | `grep "'coros'" routes/oauth_callbacks.py` returns empty | ✅ Verified |
| All 5 PR1 files AST-parse clean | `ast.parse` over each | ✅ Verified |
| `Project_Backlog_v15.md` D-50 row is stale per PR1 §5.4 (still reads "🟡 Partial — schema ✅; wiring 🟡 Deferred") | `grep "D-50.*Phase 1 integration deployment" Project_Backlog_v15.md` | ✅ Confirmed stale — drove the v16 bump executed this session |

One drift confirmed (and resolved this session by the v16 bump): the backlog narrative didn't yet reflect PR1's ship. No other drift.

---

## 2. Files shipped this turn

All on branch `claude/review-v5-handoff-t7KBL`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Project_Backlog_v16.md` | New (copy of v15 + 2 surgical edits) | Top-of-file `**File revision:**` bumped to v16 with full provenance entry; v15 demoted to predecessor revisions. D-50 row updated: status cell flips `🟡 Partial — schema ✅; wiring 🟡 Deferred` → `🟢 PR1 shipped 2026-05-14 (commit \`3628ca6\`); 🟡 follow-on PRs pending`; description column appends the PR1 wiring narrative; notes column rewritten to point at `V5_Implementation_PR1_Closing_Handoff_v1.md` §5.1 with the PR2+ candidate menu (Options A/B/C/D/E + recommended sequence A→C→B→D) and the PR1 §5.0 pre-deploy verification checklist. |
| 2 | `aidstation-sources/CLAUDE.md` | Edit (1 line) | "Authoritative current files" → "Backlog: `Project_Backlog_v15.md`" replaced with `Project_Backlog_v16.md` per PR1 §5.4 step 3. |
| 3 | `init_db.py` | Edit (+89 lines on `_PG_MIGRATIONS`) | D-59/60/61 schema additions appended to `_PG_MIGRATIONS` after the PR1 D-58 block. **D-59:** 10 `ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS …` (`locale_name`, `mapbox_id`, `lat` DOUBLE PRECISION, `lng` DOUBLE PRECISION, `chain_id`, `chain_name`, `category`, `manual_entry` BOOLEAN DEFAULT FALSE, `place_payload`, `place_fetched_at` TIMESTAMP). **D-60:** new tables `gym_profiles` + 2 partial indexes (`gym_profiles_mapbox_idx WHERE mapbox_id IS NOT NULL`, `gym_profiles_address_idx WHERE address_fingerprint IS NOT NULL`), `locale_equipment_overrides` + `leo_user_locale_idx`, `locale_toggle_overrides`; 2 more `locale_profiles` ALTERs (`gym_profile_id INTEGER REFERENCES gym_profiles(id)`, `sharing_opt_out BOOLEAN DEFAULT FALSE`). **D-61:** new `daily_availability_windows` with 3 CHECK constraints (`window_index IN (0,1)`, enabled/start/duration paired, duration 30–360) + `daw_user_day_idx`; 1 more `locale_profiles` ALTER (`preferred BOOLEAN DEFAULT FALSE`). 13 `locale_profiles` ALTERs total (the design wave's "~11" was an undercount; verified against D-59 §9 + D-60 §5.4 + D-61 §7.2). SQLite block stays frozen per Integration v4 §2.5. |
| 4 | `chain_registry.py` | New (236 lines) | Python module per D-59 §4.1. Exports `GYM_CHAINS: tuple[dict, ...]` with **32 entries** (24 `commercial_chain_gym` + 8 `climbing_gym_chain`). US-focused (Planet Fitness, LA Fitness, 24 Hour Fitness, Anytime, Gold's, Crunch, Equinox, Life Time, YMCA, Orangetheory, F45, Snap, UFC, Retro, Blink, Chuze, EoS, VASA, Esporta, SoulCycle, Barry's, CycleBar) with international by exception (PureGym UK, Basic-Fit EU). Climbing chains per D-60 §3 examples (Movement, Sender One, Touchstone, Brooklyn Boulders, Bouldering Project, Earth Treks, MetroRock, Vertical World). Patterns are lowercased substrings; `detect_chain(mapbox_text)` helper walks GYM_CHAINS in declaration order and returns the first match (None when no entry matches). Decision-order discipline noted in module docstring (more specific patterns first to avoid lax-matching collisions). |
| — | `aidstation-sources/handoffs/V5_Implementation_PR2_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `routes/locales.py` — the v1 locale form. D-59 frontend / chain-detection UX is PR3+ scope. The PG schema additions are non-breaking (all `ADD COLUMN IF NOT EXISTS` with NULL/FALSE defaults), so the existing route continues to work unchanged.
- `_SQLITE_MIGRATIONS` block — frozen per `Athlete_Data_Integration_Spec_v4` §2.5. Verified: `awk '/^_SQLITE_MIGRATIONS = \[/,/^\]/' init_db.py | grep -c "daily_availability_windows\|gym_profiles\|locale_equipment_overrides\|locale_toggle_overrides"` returns 0.
- `Athlete_Onboarding_Data_Spec_v5.md` / `Onboarding_D5[89]_Design_v1.md` / `Onboarding_D60_Design_v1.md` / `Onboarding_D61_Design_v1.md` — input contracts; specs don't edit from implementation rounds.
- `DATABASE.md` — D-59/60/61 schema additions not yet documented. Same "deferred to consolidated PR" framing PR1 §2 used; this session keeps the consolidation candidate open since DATABASE.md update would push us a sixth substantive file.
- `PROVIDERS_SCHEMA.md` — out of scope; D-59/60/61 are locale-layer, not provider-layer.

---

## 3. What landed

### 3.1 D-59 — Mapbox-anchored place lookup (`locale_profiles` columns)

```sql
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS locale_name TEXT;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS mapbox_id TEXT;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS chain_id TEXT;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS chain_name TEXT;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS manual_entry BOOLEAN DEFAULT FALSE;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS place_payload TEXT;
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS place_fetched_at TIMESTAMP;
```

`lat` / `lng` use `DOUBLE PRECISION`; D-59 §9 says "REAL" but PG's REAL is single-precision (≈7 digits) which loses meaningful coordinate resolution past ~5 decimal places. Single-precision lat 45.123456 round-trips as 45.12346 (≈10 cm). DOUBLE PRECISION is the PG-idiomatic choice for coordinates and matches Mapbox's response precision. Flagged in §6.

`place_payload` stays TEXT (raw JSON string) rather than JSONB — D-59 §9 calls it audit-only, not consumed at runtime. JSONB pays an indexing cost we don't need; can lift later if a query pattern emerges.

### 3.2 D-60 — shared gym profiles + per-athlete overrides

```sql
CREATE TABLE IF NOT EXISTS gym_profiles (
    id SERIAL PRIMARY KEY,
    mapbox_id TEXT UNIQUE,
    address_fingerprint TEXT,
    display_name TEXT,
    category TEXT NOT NULL,
    equipment TEXT,           -- JSON array of equipment tags (whole-doc R/W)
    toggles TEXT,             -- JSON object: {toggle: bool}
    disputed_items TEXT,      -- JSON array of flagged equipment tags
    private BOOLEAN DEFAULT FALSE,
    created_by_user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    last_confirmed_by INTEGER REFERENCES users(id),
    last_confirmed_at TIMESTAMP DEFAULT NOW(),
    contribution_count INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS gym_profiles_mapbox_idx
    ON gym_profiles (mapbox_id) WHERE mapbox_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS gym_profiles_address_idx
    ON gym_profiles (address_fingerprint) WHERE address_fingerprint IS NOT NULL;

CREATE TABLE IF NOT EXISTS locale_equipment_overrides (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    locale_id INTEGER NOT NULL REFERENCES locale_profiles(id),
    equipment_tag TEXT NOT NULL,
    action TEXT NOT NULL,          -- 'add' | 'remove'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, locale_id, equipment_tag, action)
);
CREATE INDEX IF NOT EXISTS leo_user_locale_idx
    ON locale_equipment_overrides (user_id, locale_id);

CREATE TABLE IF NOT EXISTS locale_toggle_overrides (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    locale_id INTEGER NOT NULL REFERENCES locale_profiles(id),
    toggle_name TEXT NOT NULL,
    value BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, locale_id, toggle_name)
);

ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS gym_profile_id INTEGER REFERENCES gym_profiles(id);
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS sharing_opt_out BOOLEAN DEFAULT FALSE;
```

Two structural choices from D-60 §5.1 carried verbatim:
- **JSON for `equipment` / `toggles` / `disputed_items` rather than normalized tables.** Profile is read whole / written whole; normalization would churn cross-products on every save.
- **`action` enum stays free-text TEXT** (not a CHECK constraint). Same risk class as `field_name` in `athlete_profile_field_provenance` (PR1 Open Item #17); same mitigation deferred to insert-side validation in the routes layer.

Two D-60 §5.5 carve-outs honored:
- **No migration of existing `locale_equipment` rows.** v1's per-user equipment lists coexist; plan-gen reads `effective_equipment` as "shared profile when `gym_profile_id IS NOT NULL`, else legacy `locale_equipment` join." Athlete-driven migration.
- **No automatic `gym_profiles` seed.** First athlete at any `mapbox_id` is offered the "build profile" flow; no pre-population.

### 3.3 D-61 — per-day availability windows + `preferred` flag

```sql
CREATE TABLE IF NOT EXISTS daily_availability_windows (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    day_of_week SMALLINT NOT NULL,        -- 0=Sunday, 6=Saturday
    window_index SMALLINT NOT NULL DEFAULT 0,  -- 0=primary, 1=secondary
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    window_start TIME,
    window_duration_min INTEGER,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, day_of_week, window_index),
    CHECK (window_index IN (0, 1)),
    CHECK (
        (enabled = FALSE AND window_start IS NULL AND window_duration_min IS NULL)
        OR (enabled = TRUE AND window_start IS NOT NULL AND window_duration_min IS NOT NULL)
    ),
    CHECK (window_duration_min IS NULL OR window_duration_min BETWEEN 30 AND 360)
);
CREATE INDEX IF NOT EXISTS daw_user_day_idx
    ON daily_availability_windows (user_id, day_of_week);

ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS preferred BOOLEAN DEFAULT FALSE;
```

`day_of_week` uses Sunday=0 (D-61 §7.1 explicit) — note that Python's `datetime.weekday()` is Monday=0 / Sunday=6; the form-display order is what's authoritative. Conversion happens at the route boundary, not at the column.

`preferred` has no uniqueness constraint per D-61 §7.2. Semantics (§4.3 of D-61): one athlete can have multiple `preferred=TRUE` locales; the locale-assignment algorithm uses it as a tiebreaker, not a hard select.

### 3.4 `chain_registry.py` — 32-entry chain seed

Two functions live in this module:

- `GYM_CHAINS: tuple[dict, ...]` — the literal seed. Tuple (immutable) so callers can't accidentally mutate the registry at runtime.
- `detect_chain(mapbox_text: str) -> dict | None` — the D-59 §4.2 step 2 matcher. Lowercase + walk + first-match-wins. Returns the matched dict or None. Caller responsible for the §4.2 step 3 fallback (inspect Mapbox `properties.category`).

Distribution:

| Category | Count | Examples |
|---|---|---|
| `commercial_chain_gym` | 24 | Planet Fitness, LA Fitness, 24 Hour Fitness, Anytime Fitness, Gold's Gym, Crunch Fitness, Equinox, Life Time, YMCA, Orangetheory, F45 Training, Snap Fitness, UFC Gym, Retro Fitness, Blink Fitness, Chuze Fitness, EoS Fitness, VASA Fitness, Esporta Fitness, PureGym (UK), Basic-Fit (EU), SoulCycle, Barry's, CycleBar |
| `climbing_gym_chain` | 8 | Movement, Sender One, Touchstone Climbing, Brooklyn Boulders, Bouldering Project, Earth Treks, MetroRock, Vertical World |

D-59 §4.1 spec'd "~30 entries" — this is 32. Decision: include the climbing chains generously because Andy's Pocket Gopher Extreme prep includes outdoor rock climbing + abseiling, and climbing-gym category coverage matters more than commercial coverage for the test athlete's actual training. Andy can prune entries he doesn't care about at any time — registry is just a Python literal.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` + `chain_registry.py` AST-parse clean | `ast.parse` over each | ✅ Verified |
| `_PG_MIGRATIONS` totals 204 statements (was 183 after PR1; +21 = 10 D-59 ALTERs + 4 tables + 4 indexes + 2 D-60 ALTERs + 1 D-61 ALTER) | AST count via `ast.parse` walk for the `_PG_MIGRATIONS` assignment | ✅ Verified |
| `_SQLITE_MIGRATIONS` totals 140 statements (unchanged from PR1) | Same | ✅ Verified |
| 4 new `CREATE TABLE` statements landed (`daily_availability_windows`, `gym_profiles`, `locale_equipment_overrides`, `locale_toggle_overrides`) | `grep -c "CREATE TABLE IF NOT EXISTS …"` returns 4 | ✅ Verified |
| 13 new `locale_profiles` ALTER ADD COLUMN landed in `_PG_MIGRATIONS` (region grep yields 15 = 2 pre-existing `city` + `user_id` from older revisions + 13 new) | `awk '/_PG_MIGRATIONS/,/]/' init_db.py \| grep -c ALTER` | ✅ Verified |
| 4 new partial / regular indexes landed in PR2 region (`gym_profiles_mapbox_idx`, `gym_profiles_address_idx`, `leo_user_locale_idx`, `daw_user_day_idx`) | Region grep | ✅ Verified |
| `_SQLITE_MIGRATIONS` contains 0 mentions of the 4 new table names | Region grep returns 0 | ✅ Verified |
| `chain_registry.GYM_CHAINS` declares 32 entries; categories restricted to `commercial_chain_gym` (24) + `climbing_gym_chain` (8) | AST walk over `GYM_CHAINS` tuple | ✅ Verified |
| `detect_chain('Planet Fitness North Loop')` returns the planet_fitness dict; `detect_chain('Random Local Gym')` returns None | Local Python via spec_from_file_location (avoids the `flask` import barrier on init_db) | ✅ Verified |
| `aidstation-sources/CLAUDE.md` Authoritative current files names `Project_Backlog_v16.md` | `grep "Backlog: " aidstation-sources/CLAUDE.md` | ✅ Verified |
| `Project_Backlog_v16.md` D-50 row status flipped + PR1 commit `3628ca6` referenced in two places (status cell + notes column) | `grep -c "PR1 shipped 2026-05-14 (commit \`3628ca6\`)"` returns 2 | ✅ Verified |

No drift between this handoff's narrative and on-disk state.

A note about the "could not exec init_db.py" gap: `python3 init_db.py` (or `importlib` load) requires `flask` which isn't installed in this session's sandbox. AST parse confirms syntactic validity; behavior of the migrations themselves can only be exercised at deploy time against a live PG connection. Same exercise gap PR1 §6 flagged for the D-58 tables. Spot-check on Neon post-deploy.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR2 reaches production)

Symmetric to PR1 §5.0 but smaller — no third-party API to confirm, no env vars to set; only the migration run to monitor.

1. **Monitor first cold-start `_PG_MIGRATIONS` run on Neon.** The migration loop catches per-statement exceptions silently; if any of the 21 new statements fails to apply, no other symptom surfaces until a query hits a missing table or column. After the next Vercel deploy, spot-check in the Neon console with:
   ```
   \d locale_profiles                      -- expect 13 new columns visible
   \d gym_profiles
   \d locale_equipment_overrides
   \d locale_toggle_overrides
   \d daily_availability_windows
   ```
2. **`lat` / `lng` precision was promoted to `DOUBLE PRECISION`.** D-59 §9 specifies `REAL`; this implementation uses `DOUBLE PRECISION` (8 bytes, ~15 decimal digits) because PG's `REAL` is single-precision and loses meaningful resolution past ~5 decimal places of lat/lng. If Andy prefers exact spec compliance, the swap is a one-line edit + a fresh ALTER (PG will rewrite the column). Flagged in §6.
3. **`chain_registry.py` lives at the repo root** alongside `app.py` / `init_db.py` / `database.py`. Same import-as-module pattern the rest of the v1 app uses. No `__init__.py` required (Flask app at repo root).

### 5.1 PR3+ candidates — Andy's choice (carried forward from PR1 §5.1)

The recommended sequence A → C → B → D from PR1 §5.1 — **Option A has now landed in this PR2**. So the remaining ordering is **C → B → D**, with E (14-day nudge job) available as a small standalone whenever Andy wants the UX.

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR2_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR1_Closing_Handoff_v1.md` — the predecessor scope-lock and candidate menu.
4. `aidstation-sources/Project_Backlog_v16.md` — confirm the D-50 row reads "🟢 PR1 shipped" with the candidate menu inline.

#### ✅ Option A (D-59/60/61 schema PR) — SHIPPED in this PR2 session

No remaining work in the schema half. Frontend rendering of the new columns is PR3+ (Option B / D).

#### Option C — Next provider OAuth (Polar — Andy locked this in pre-PR2)

Andy picked Polar over Wahoo when authorizing this PR2 session. Provider-specific shape:
- **Tokens don't expire.** `provider_auth.token_expires_at = NULL`. The token-refresh skeleton in `provider_auth.py` won't be exercised by Polar; Wahoo (2h refresh) is still the first real test of that path when it lands later.
- **Registration call required.** After token exchange, POST `https://www.polaraccesslink.com/v3/users` with `{member-id: <athlete-id>}` to activate the partner relationship; the response includes `polar-user-id` which is the Polar identifier we store. Set `provider_auth.registered_at = NOW()` only after the registration call returns 200.
- **Webhook signature is HMAC-SHA256** of the raw request body, using a **separate** `POLAR_WEBHOOK_SECRET` env var (Polar issues this when the webhook is registered via their API; it's distinct from the OAuth client_secret). Header name: `Polar-Webhook-Signature`. Use `hmac.compare_digest` to compare.
- **No per-event webhook_token rotation.** That's Wahoo's pattern (Pattern A in PR1 §3.2); Polar uses a static webhook secret per partner.
- **Per-provider tables in PG already:** `polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, `polar_exercises` (or similar — verify against `init_db.py` `_PG_MIGRATIONS` at session start; D-50 shipped these in v14 of the backlog).

Expected files for Option C:
- `routes/polar.py` (new) — three routes (start, callback, webhook) using `pa.upsert_auth` + `pa.record_oauth_scope_ack`.
- `routes/polar_ingest.py` (new) — payload-shape dispatcher to the per-provider tables.
- `routes/oauth_callbacks.py` — drop `('polar', 'Polar')` from `_PROVIDERS` (same one-line pattern PR1 used for COROS).
- `init_db.py` — no schema additions expected (D-50 shipped the tables); add a partial `UNIQUE (user_id, polar_exercise_id) WHERE polar_exercise_id IS NOT NULL` index on `cardio_log` to fix the dedup race window flagged in PR1 §6 (and add the parallel `coros_label_id` / `wahoo_workout_id` partials while we're touching the file).
- Closing handoff.

5 files, comfortably at the ceiling.

**Polar env vars to set in Vercel (Production + Preview, Sensitive):**
- `POLAR_CLIENT_ID`
- `POLAR_CLIENT_SECRET`
- `POLAR_WEBHOOK_SECRET` (set after webhook registration via Polar partner portal)
- Optionally `POLAR_AUTH_URL` / `POLAR_TOKEN_URL` / `POLAR_USERS_URL` if defaults need overriding

**Polar developer-portal redirect_uri to register:** `https://aidstation-pro.vercel.app/polar/oauth/callback` (follows the COROS convention deviation from `/auth/<slug>/callback` flagged in PR1 §6; or pivot to `/auth/polar/callback` if Andy decides the slug-dispatch pattern is better).

#### Option B — COROS frontend + Account Config 1 management screen (smallest user-facing PR)

Unchanged from PR1 §5.1 description. Useful once Option C lands so two providers are visible.

#### Option D — v5 frontend onboarding flow

Unchanged from PR1 §5.1 — defer until at least A + C + B land. With Option A now done, the schema is fully in place; the gating concern is having two real providers connected before building the prefill UX against just COROS.

#### Option E — 14-day connect-provider nudge background job

Unchanged. Small standalone.

### 5.2 Recommended sequence (revised post-PR2)

**C → B → D**, with **E** available as an opportunistic small-PR drop-in whenever convenient.

Per PR1 §5.1: A first (✅ done in PR2), then C to validate `provider_auth` is genuinely provider-agnostic, then B to make connections visible, then D as the full reshape.

### 5.3 Standing items not on the critical path (unchanged from PR1 §5.3)

- **D-52 Catalog Migration Phase 1** — fuzzy-match HITL alias audit. Independent.
- **D-54 SQLite collapse** — Catalog Migration Phase 5. Queued.
- **D-55 Garmin onto `provider_auth`** — paused until Garmin reopens API access.
- **D-57 Research re-evaluation cadence design.**
- **D-62 webhook_events retention prune** — in scope for the next ops PR (still PR1's COROS webhook is the first real accumulator).
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — `athlete_profile_field_provenance.field_name` still free-text TEXT. Lands with PR3+ prefill UX work. PR2 leaves it untouched.
- **DATABASE.md update** — 7 new tables/column groups now undocumented (PR1's 3 + PR2's 4). Consolidates naturally with a docs-only PR after at least one frontend PR makes the columns visible — the right time to draft user-facing column descriptions is when there's a UX to anchor them to.
- **PROVIDERS_SCHEMA.md update** — same framing as PR1; lands with Option C (second real provider).
- **lat/lng precision** (new in PR2 §6) — `DOUBLE PRECISION` chosen over D-59 §9's `REAL`. If Andy wants strict spec adherence, swap is a single-statement ALTER on each column.

### 5.4 Backlog row update (executed in this PR2 — no work owed)

Unlike PR1 §5.4 which deferred a v15 → v16 bump, **PR2 executed the bump as its first action.** `Project_Backlog_v16.md` is the live backlog on disk; CLAUDE.md "Authoritative current files" cites v16. The next session's Rule #9 read should land on v16 with the D-50 row already saying "🟢 PR1 shipped 2026-05-14."

If Option C ships next, that session's closing handoff should bump backlog v16 → v17 with an updated D-50 row noting "🟢 PR1 + PR2 + PR3 shipped … "; same mechanical pattern.

---

## 6. Open items / honest flags

- **`lat` / `lng` are `DOUBLE PRECISION`, not `REAL` per D-59 §9.** Spec deviation, intentional. PG's `REAL` is single-precision (~7 decimal digits); coordinates with 4+ decimal places of meaningful precision (~10m resolution) need double-precision. Mapbox returns coordinates to 6+ decimal places. Captured here so Andy can revisit if strict spec match is preferred; otherwise carry forward.
- **`chain_registry.py` has 32 entries, not "~30."** D-59 §4.1's "~30" is a rough sizing; 32 is well within the `~` band. Distribution favors climbing-gym chains because Andy's training context (Pocket Gopher prep includes outdoor rock + abseiling) makes climbing coverage useful even at v1.
- **`action` column in `locale_equipment_overrides` is free-text TEXT, not a CHECK enum.** Mirrors `field_name` in `athlete_profile_field_provenance` (PR1 Open Item #17). Insert-side validation lives in the route handlers (PR3+). Risk: typo-orphan rows that don't tie to a valid override action. Mitigation: rare event class; not in PR2 critical path.
- **Migrations not exercised against PG locally.** Same constraint as PR1 §6: dev runs SQLite (per `database.py` fall-through), and PR2 is PG-only. First real exercise is the next Vercel deploy + Neon cold start. AST parse + grep anchors are the pre-deploy guard.
- **No `gym_profiles` seed.** D-60 §5.5 calls out the coexistence migration approach: `locale_equipment` rows stay; new locales opt into shared profiles. PR2 doesn't seed; first athlete at any given Mapbox-anchored locale creates the profile.
- **`day_of_week` is Sunday=0.** D-61 §7.1 explicit, but Python's `datetime.weekday()` is Monday=0. Mismatch is a known footgun at the route boundary. PR3 frontend work will need a one-line conversion (`weekday() == 6 ? 0 : weekday() + 1`) on the route side.
- **`equipment_tag` in `locale_equipment_overrides` is free-text TEXT.** Same risk class as `action` / `field_name`. The canonical 121-item equipment list lives in v1's `equipment_items` table; PR3 frontend should constrain the input to those tags. Until then, the column accepts anything.
- **5 files this session counting the handoff** (4 substantive + handoff). At the CLAUDE.md ceiling exactly, one under PR1's pattern. Quality across the substantive files: AST-parses clean, manual readthrough caught no logic gaps, the chain registry was sanity-tested with `detect_chain` calls against known inputs.
- **No tests added.** Matches PR1's decision to defer the `tests/` directory introduction until at least Option C's per-provider OAuth ships — `provider_auth.py` is the better first unit-test surface than a static registry literal. `chain_registry.detect_chain` would be a one-paragraph unit-test surface if/when we want one.

---

## 7. Gut check

**What this session got right.**

- **Two scope-locked PRs executed in one chat under ceiling.** §5.4 (2 files: backlog + CLAUDE.md) + Option A (2 files: init_db.py + chain_registry.py) is the natural pairing — the backlog bump is the bookkeeping that lets the next session's Rule #9 reconciliation land on accurate state, and PR2 is what makes the bump meaningful.
- **Schema-only PR keeps blast radius minimal.** No route handlers touched; no frontend touched; no API contracts in flight. The 21 new statements are all idempotent (`IF NOT EXISTS` everywhere); deploy failure is a no-op, not a regression.
- **`chain_registry.py` is honest about pattern collisions.** Module docstring explicitly tells future patch-authors to put more specific patterns first to avoid lax-matching (`'planet fit'` shouldn't shadow a future `'planet fitness express'` registry split). Decision-order discipline noted in the code, not buried in a handoff.
- **Spec deviation flagged loudly, not glossed.** D-59 §9 says `REAL`; PR2 uses `DOUBLE PRECISION`. Reason: REAL is wrong for coordinates. Captured in §3.1, §5.0 #2, §5.3, §6 — four places — so Andy can revisit without digging.
- **D-58 / D-59 / D-60 / D-61 are now schema-complete on disk.** The full v5 onboarding design wave (PR1's D-58 + PR2's D-59/60/61) has its PG schema in place. Frontend can build against a stable surface; no more "but D-60 isn't even a table yet" gotchas blocking Options B/D.

**Risks.**

- **First Neon migration run carries 21 statements that were never PG-validated locally.** Same risk class as PR1. The migration loop's per-statement `try/except` + `IF NOT EXISTS` keeps failures non-blocking, but a syntax error in (say) the `daily_availability_windows` CHECK clauses would silently roll the statement back, and the first query against a missing column would surface only later. Spot-check is mandatory per §5.0 #1.
- **`DOUBLE PRECISION` vs `REAL` deviation could surprise.** Anyone reading D-59 §9 then looking at the on-disk column will see a mismatch. The deviation is documented in this handoff but not on the schema itself (no SQL comment). If we ship enough deviations from D-59/60/61 specs over time, the specs become harder to trust. Mitigation: capture in `DATABASE.md` when that doc gets updated.
- **`locale_equipment` legacy table now coexists with `gym_profiles`.** Plan-gen needs the if-else logic per D-60 §5.5 step 4. If a frontend PR writes through one path but plan-gen reads the other, athletes see equipment mismatches. Mitigation: PR3 frontend should write to `gym_profiles` + `locale_equipment_overrides` exclusively; the legacy `locale_equipment` writes should be deprecated at the same time.
- **32 chain entries are a first-pass guess.** The registry is intentionally easy to patch (Python literal, no DB ceremony); the seed is a starting point, not a curated final state. Andy's actual locale list is the source of truth for which chains matter.
- **Backlog narrative drift remains a class hazard.** PR2 cleaned up the D-50 row; if PR3 (Option C) ships and doesn't bump v16 → v17 with a status update, we're back in the same drift state that prompted Rule #9 in the first place. Discipline-only mitigation.

**What might be missing.**

- **`address_fingerprint` normalization rule isn't anywhere on disk.** D-60 §5.1 calls it "normalized address string (lowercase, whitespace-collapsed, abbreviation-expanded)" but the abbreviation expansion table doesn't exist yet. PR3 frontend or a future ops PR needs to define it (e.g., "St." → "Street", "N" → "North", etc.) before manual-fallback dedup is meaningful. Until then, the column is informational.
- **`gym_profiles.disputed_items` mutation contract is implicit.** D-60 §4.6 describes the dispute flow but the JSON-array update semantics (atomic write? append-only? compaction?) aren't pinned down. PR3 frontend needs to decide; current default is "whole-doc R/W under app-level lock," which is the PG `UPDATE gym_profiles SET disputed_items = '[...]' WHERE id = …` pattern.
- **No coordinate-system note in the schema.** `lat` / `lng` are assumed WGS84 (Mapbox's coordinate system); no SRID column. If we ever need PostGIS spatial queries, the columns become non-trivial to retrofit. Acceptable now; not great if a `nearby_locales(user_id, radius_km)` query pattern emerges.
- **`window_index = 1` (doubles) has no first-class UX yet.** The schema supports it; D-61 §3.1 documents the form rendering; PR3 frontend will build the second-window UI. Until then, athletes can only enter primary windows.
- **DATABASE.md update is still deferred.** Now 7 undocumented additions (D-58's 3 + PR2's 4 tables + 13 column ALTERs). The longer this defers, the more reconciliation work the docs-only PR carries. Risk: someone reads DATABASE.md and concludes the schema state from there, missing 18+ items.

**Best argument against this session's scope.**

PR2's schema-only framing accepts that the new columns / tables sit empty until PR3+ frontend writes to them. There's a counter-argument that schema and the first frontend write should land together so the schema is exercised at merge time, not weeks later when memory has faded. Counter to the counter: this is the strangler-fig pattern — schema-first, write-paths-second is the safest sequencing when no users are at risk (v1 has Andy only) and the schema is small + idempotent. Bundling schema + frontend would push us to 8–10 files in one chat; the 5-file ceiling exists because that's where quality degrades. The deferred-frontend cost is two more PRs of context-switching, not architectural debt.

Alternatively, the D-59/60/61 schema could have shipped per-design-doc as three separate PRs. Counter: the three docs are tightly coupled (D-60 references `locale_profiles.mapbox_id` from D-59 and `chain_id` from D-59; D-61 references `locale_profiles.lat/lng` from D-59). One PR keeps the inter-dependent schema atomic at deploy time. Three PRs would have the same total file count and three migration runs to spot-check.

---

## 8. Forward pointers

- **Next session:** Option C (Polar OAuth, Andy locked-in pre-PR2). The §5.1 Option C breakdown above is the scope-lock for PR3.
- **Before next code lands:** PR2 §5.0 pre-deploy spot-check on Neon. PR1 §5.0 pre-deploy checklist (COROS env vars + redirect_uri registration + API surface confirmation) also still owed before PR1 is real for users.
- **First action of next session:** Rule #9 reconciliation; specifically the `Project_Backlog_v16.md` D-50 row (now reads "🟢 PR1 shipped"); confirm CLAUDE.md cites v16; spot-check PR2's 4 new tables exist in `_PG_MIGRATIONS` (they do — this handoff §4 verifies).

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits
- #12 numeric version suffixes (backlog v15 → v16 owed → ✅ executed this session)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR2 closing handoff. PG schema half of the rest of the v5 onboarding design wave shipped. Next: Andy's choice among PR3 candidates in §5.1 (Polar OAuth pre-locked).*
