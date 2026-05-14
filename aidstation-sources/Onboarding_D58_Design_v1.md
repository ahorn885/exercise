# Onboarding D-58 Design — OAuth-First Flow + Provider-Sourced Prefill

**Version:** 1.0
**Date:** 2026-05-14
**Status:** Design decisions locked; spec rewrite pending (`Athlete_Onboarding_Data_Spec_v5.md` consolidates all four design tracks).
**Backlog row:** D-58
**Track:** Fourth and final of the Onboarding Design Wave (D-58–D-61). Sequence: D-59 ✅ → D-60 ✅ → D-61 ✅ → **D-58 (this doc)**. Order chosen because D-58 was the most blocked on UX-shape decisions for the v1→v2 wiring track (predecessor handoff §6.4).
**Affects:** `Athlete_Onboarding_Data_Spec` §A flow, §A.1 disclosures (Connected Service consent moves earlier in the flow but the disclosure itself was already specced), Account Config 1 (Connected Services), Account Config 3 (Disclosure Acknowledgment Records — new entries for OAuth scopes and prefill consent); new `athlete_profile_field_provenance` table; `routes/profile.py`, `routes/connect_*.py`, OAuth callback handlers (eventual rewrite); D-50 wiring track unblocks once this lands.
**Cross-references:**
- `Athlete_Onboarding_Data_Spec_v4.md` §A (lines 127–164 — fields D-58 prefills), §A.1 (lines 146–162 — disclosure slots, Connected Service consent already listed), Account Config 1 (lines 851–865), Account Config 3 (lines 876–887).
- `Athlete_Data_Integration_Spec_v4.md` §3 (provider list + stub status), §4 (`provider_auth` + `webhook_events` schema), §7 (per-field source mapping — the authoritative list of prefill-eligible fields), §8 (two-regime consumer model — pre-integration / post-integration / mixed).
- `Project_Backlog_v15.md` D-58 (problem statement), D-50 (wiring track that unblocks once D-58 settles per predecessor handoff §6.4).
- `D50_Phase1_Schema_Closing_Handoff_v1.md` and `D50_Phase1_Schema_Review_v1.md` — context on the provider stubs and the schema landed for `provider_auth`.

---

## 1. Purpose

The v4 spec places provider connection in Account Config 1, *after* the entire §A–§L onboarding flow completes. The athlete enters every field by hand, then optionally connects providers. This is the wrong ordering for two reasons:

1. **Prefill leverage is lost.** Integration v4 §7 maps dozens of onboarding fields to provider-derivable sources (HRmax, RHR, sleep baseline, body weight, recent race results, weekly volume). Putting connect last means the athlete enters all of them by hand even when a provider could have populated them.
2. **The connection state is itself onboarding signal.** Whether the athlete is connected determines which §A–§L fields are even meaningful as self-report (e.g., "weekly training volume" is more honest derived from `cardio_log` aggregates than guessed in a survey). A coaching product that claims integration as a launch commitment (CLAUDE.md core differentiators #2 and #6) cannot bury the connection step at the end of onboarding.

D-58 fixes both by **moving provider-connect to Step 1 of data entry** (after the one-time account-creation acknowledgment but before §A), defining how prefilled values are sourced and displayed, and specifying what happens when an athlete connects providers later (mid-onboarding, post-onboarding, or mid-plan).

The four other Onboarding Design Wave tracks (D-59 / D-60 / D-61) reshape what the athlete enters; D-58 reshapes when and from what source.

---

## 2. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Provider-connection step placement | **After the account-creation acknowledgment, before §A.** New flow: account creation → account-creation ack (already a one-time gate per §A.1) → "Connect your fitness providers" step → §A → §B → … | Andy 2026-05-14. The legal/risk gate stays first (athletes acknowledge training-carries-risk before being asked to share data with the app). Provider-connect becomes Step 1 of actual data work, framed as enabling everything that follows. No separate "Welcome" screen — the connect step IS the welcome step. |
| 2 | Per-field prefill priority across providers | **Most-recent-wins + provenance display.** When two or more connected providers offer the same field (e.g., Polar + COROS both have RHR), the value with the most recent provider-side update timestamp is shown. Provenance tag below the field shows source + age ("from Polar, 2 days ago"). When values diverge by more than the field-specific tolerance, the tag also surfaces the alternate ("Polar: 78.2 kg; Garmin: 79.1 kg — using Polar (more recent)"). | Andy 2026-05-14. Most-recent is honest about data freshness, simple to implement, and athlete-correctable. Per-provider preference per field is config burden athletes won't tune; weighted blends are arbitrary for non-numeric fields; per-field picking is friction. The provenance display + manual override path (decision #3) covers athletes who disagree with most-recent. |
| 3 | Prefilled field affordance | **Edit-in-place with provenance tag + `manual_override` stickiness.** Prefilled value sits in the input; athlete can type to overwrite without unlocking; provenance tag fades on first edit; field flips to `source='manual_override'` and is excluded from future prefill overwrites without explicit re-prompt. | Andy 2026-05-14. Edit-in-place is lower friction than a click-to-unlock pattern. The stickiness flag closes the loop on "what happens to my edit when Polar syncs again tomorrow" — the answer is "nothing; it stays." Athletes who want to revert can clear the override (decision #6). |
| 4 | "No providers connected" path | **Graceful degradation + delayed soft nudge after 14 days.** Athlete can skip the connect step entirely; v1-style self-report onboarding is a first-class equivalent path with no functional gating. After 14 days of self-report-only use (measured from account creation, regardless of connect-step path), one soft in-app nudge: "AIDSTATION works best with at least one fitness provider connected. Want to set one up?" Dismissable; no further nudges. | Andy 2026-05-14. Hard requirement blocks athletes who don't use a fitness provider (Apple Health and Samsung Health are out of scope per CLAUDE.md stack notes; some athletes legitimately have nothing to connect). No-nudge-ever loses the design intent (athletes who put off connecting forever lose the v2 value proposition). 14-day delay is long enough to not nag and short enough to surface before plan-gen routine sets in. |
| 5 | Re-onboarding after later provider connect | **Prompt + per-field opt-in, manual_override fields excluded.** When athlete connects a provider any time post-onboarding, system identifies fields where (a) the provider can supply data, (b) the current `source` is NOT `manual_override`. Surfaces a summary screen: "Polar can fill in HRmax, RHR, body weight, sleep baseline. Apply Polar values?" Three actions: bulk-apply-all, per-field review, skip. Manual_override fields never show up in the prompt — athlete edits stick. | Andy 2026-05-14. Silent rewrite is the surprise-the-athlete failure mode; no-retroactive-prefill leaves stale self-report data sitting forever; per-field diff review is friction for the (common) case where there's no conflict. The prompt + opt-in is honest, respects manual_override stickiness, and bulk-applies for the no-conflict case. |
| 6 | Manual override clear path | **Athlete can revert a manual_override on a field-by-field basis from the field's edit affordance.** The provenance tag for an overridden field reads "manually set on YYYY-MM-DD"; clicking opens a popover with "Use Polar value (78.2 kg, last synced 2 days ago) instead." Restores prefill behavior and removes the stickiness flag. | Closes the round-trip on decision #3. Without a clear path, an athlete who fat-fingers a manual edit can't easily undo back to provider-sourced. |
| 7 | Per-provider scope acknowledgment storage | **Each OAuth flow records a row in Account Config 3 with `disclosure_id='oauth_scope_<provider>'`, `version_id`, `acknowledged_at`, `scopes_granted` snapshot.** Re-acknowledgment required when scope set changes (provider adds new scope, or app requests new scope post-launch). | Reuses the §A.1 + Account Config 3 infrastructure. The Connected Service consent disclosure is already listed in v4 §A.1 (line 156); D-58 just moves it earlier in the flow and pins down storage shape. |
| 8 | Field-source provenance storage | **New table `athlete_profile_field_provenance` keyed by `(user_id, field_name)`. Stores `source` enum (`'self_report'` / `'provider_<X>'` / `'manual_override'`), `source_provider_id` (nullable FK to provider_auth), `source_synced_at`, `last_updated_at`.** Athlete-profile field values continue to live on `athlete_profile` and the discipline / benchmark tables (per Integration v4 §7.6 — D-51 inventory); provenance is sidecar metadata. | Sidecar table avoids fattening every field-bearing table with 3 metadata columns each. Per-field provenance is queryable for "what fields are stale" / "what fields are athlete-overridden" without joining wide rows. The shape is forward-compatible with adding new provenance fields (confidence, conflict-resolution log) without schema churn on the value tables. |
| 9 | Re-prefill cadence (already-prefilled fields) | **Provider syncs update field values on a per-field tolerance check.** For each provider sync that delivers a field the system has prefill-stored from that same provider: if the new value differs from stored by more than a field-specific tolerance (e.g., body weight ±0.5 kg, RHR ±2 bpm), update silently and bump `source_synced_at`. If divergence exceeds tolerance OR the provider source has changed (most-recent-wins switched to a different provider), surface a passive notification ("Polar updated your HRmax: 188 → 192 bpm. [Use new value] [Keep old]"). Manual_override fields never auto-update regardless. | Honest about data freshness without notification fatigue. The tolerance is the line between "this is the same value" (no need to bother athlete) and "this is a meaningful change" (athlete should know). Field-specific tolerances live in a v5 implementation config, not this design doc. |

---

## 3. Onboarding flow ordering (replaces v4 §A flow framing)

### 3.1 The new step sequence

| Step | Owner | What happens |
|---|---|---|
| 0 | Auth system | Sign-up / sign-in. Email + password (or OAuth-via-Google etc. — out of scope for D-58). |
| 1 | §A.1 account-creation ack | One-time disclaimer acknowledgment per v4 §A.1 (training carries risk, app provides recommendations not medical advice, etc.). Existing flow; unchanged. |
| 2 | **D-58 connect step (NEW)** | "Connect your fitness providers" screen. Lists supported providers (Polar, COROS, Wahoo, Strava, Whoop, RWGPS, TrainingPeaks, Zwift, Garmin-when-restored — per Integration v4 §3). Athlete connects 0 or more via per-provider OAuth. Connected Service consent disclosure (§A.1 line 156) shown inline at each connect; per-provider scope ack stored per decision #7. Athlete clicks "Continue" when done — at any time, including with zero providers connected. |
| 3 | §A entry | §A fields (Name, DoB, Sex, Height, Body Weight, Primary Training Location). Provider-prefillable fields (Body Weight at minimum; Height if any provider exposes it) display with provenance tag per decision #2/#3. Sex and Name and DoB are self-report only (no provider supplies them reliably). |
| 4 | §B–§L | Remaining onboarding sections in v4 order. Each section's prefill-eligible fields (per Integration v4 §7 mapping) display with provenance for connected providers. |
| 5 | Account Config screens | Configuration sections (Gym Memberships, Privacy, etc.). Account Config 1 (Connected Services) becomes a *management* screen (disconnect / re-auth / scope-update) rather than a connect screen — connect happened at step 2. |

### 3.2 Skip semantics

The connect step has a "Skip for now" affordance. Skipping moves directly to step 3. Athletes who skip see no provider-prefilled values; every §A–§L field renders as v1-style self-report. The 14-day soft nudge per decision #4 fires for athletes who skip (or who connect zero providers).

The skip path is functionally identical to the v1 Account Config 1 path — connect remains available at any time from the management screen, and the post-connect prompt (decision #5) handles retroactive prefill.

### 3.3 What this changes about the v4 spec

- **§A.1's "Connected Service consent" disclosure moves from "shown at Connected Service connect flow (Account Config)" to "shown at the new D-58 connect step (Step 2 of onboarding) + at any subsequent connect from the management screen."** Disclosure copy unchanged; only the timing shifts.
- **Account Config 1's framing changes from "connect here" to "manage your connections here."** Connect itself happens earlier; Account Config 1 becomes status display + disconnect / re-auth UI.
- **No fields are removed from §A or any other section.** D-58 only changes how field values arrive; the field set itself is preserved.

---

## 4. Per-field prefill mechanics

### 4.1 Eligibility

A field is **prefill-eligible** if Integration v4 §7 maps it to at least one provider source. Drawing from §7.1–§7.5:

| Section | Prefill-eligible fields (current Integration v4 §7) |
|---|---|
| §A | Body Weight (Polar, Garmin, Wahoo via wellness sync) |
| §C | Current Weekly Training Volume; Most Recent Race Results; (partially) Training Consistency 12 mo |
| §D.1 (Run) | Easy Run Pace; Recent Race Paces; Vertical Gain Tolerance |
| §D.2 (Cycle) | Longest Ride 12 mo |
| §D.3–D.7 | Volume / longest-session fields per discipline |
| §F | HRmax; (potentially) VO2max Estimate; Cycling FTP (when Wahoo FTP API ships) |
| §I | Average Nightly Sleep |

Self-report-only fields (Sex, DoB, Years of Structured Training, all §B health conditions, all §E strength benchmarks, Pack Load Training History, Trail Running Experience, etc.) are NOT prefill-eligible and behave exactly as in v1.

### 4.2 Prefill resolution (per field, at display time)

For each prefill-eligible field on a screen the athlete is viewing:

1. **Check `manual_override`.** If `athlete_profile_field_provenance.source = 'manual_override'`, render the stored value with the "manually set on YYYY-MM-DD" tag + "use provider value instead" affordance per decision #6. Skip the rest of the resolution.
2. **Check connected-provider candidates.** Query `provider_auth` for the user's currently connected providers. For each, check whether that provider has supplied a value for this field (per the per-provider data tables — `polar_*`, `coros_*`, etc.).
3. **Pick most-recent.** Among the candidates, pick the one whose latest sync delivering this field is most recent. Render its value with the "from {provider}, {age}" tag.
4. **Surface divergence (when present).** If a non-winning candidate's value differs from the winning value by more than the field-specific tolerance, append "; {alt-provider}: {alt-value}" to the tag.
5. **No candidates.** Render the field as v1-style self-report (empty, athlete fills in). `source` remains `'self_report'` until athlete edits or a provider sync delivers a value.

### 4.3 Edit semantics

| Athlete action | System action |
|---|---|
| Athlete types into a prefilled field (any character) | Field value updates to athlete's input; `source` flips to `'manual_override'`; provenance tag fades; `last_updated_at` bumps. |
| Athlete clears a prefilled field (deletes all characters) | Same: `source` flips to `'manual_override'`; value becomes empty (subject to validation — required fields enforce). |
| Athlete clicks "use provider value instead" on an overridden field | `source` reverts to the relevant provider; value reverts to the provider's most-recent value; tag refreshes. |
| Athlete enters a value into a never-prefilled field (no provider sources, or all providers disconnected) | `source` set to `'self_report'`. Behaves like v1. |
| Provider sync delivers a value for a field | If `source = 'manual_override'`: do nothing (silently store the new provider value as a "candidate" available via the override-clear path; do not surface). If `source = 'provider_<X>'` from the same provider: apply per-decision-#9 tolerance check. If `source = 'provider_<Y>'` (different provider) and the new sync is more recent than the stored: re-resolve per §4.2; if winning provider changes, surface as a passive notification. If `source = 'self_report'`: prefill silently (athlete had no value; no edit to overwrite). |

### 4.4 What happens at validation

Tier 1 required fields without a value (no provider, no athlete entry) block onboarding completion as in v1. Provider prefill counts as "has a value" — the athlete doesn't have to confirm a prefilled value to proceed; presence of prefill is presence of value. This preserves the prefill-as-leverage intent.

---

## 5. "No providers connected" path

### 5.1 Skip flow

At the connect step (Step 2), the screen shows:

```
Connect your fitness providers

[Polar]  [COROS]  [Wahoo]  [Strava]  [Whoop]  [RWGPS]  [TrainingPeaks]  [Zwift]
 (Garmin restoration pending; not currently available)

Connecting one or more providers lets AIDSTATION pre-fill onboarding
fields, generate plans against your actual training data, and adjust
plans as your data updates. You can always connect later.

[Continue without connecting]      [Continue with connected providers (N)]
```

Both buttons are always live; "Continue without connecting" is not greyed out or visually demoted. Athletes are not nudged at this step.

### 5.2 The 14-day soft nudge

Computed as: `account_created_at + INTERVAL '14 days'` AND `(SELECT COUNT(*) FROM provider_auth WHERE user_id = X AND status = 'connected') = 0`.

When both conditions are true and the nudge has not been previously dismissed:

- Display a passive in-app banner above the dashboard: "AIDSTATION works best with a fitness provider connected. Want to set one up? [Connect] [Not now]"
- "Connect" navigates to the management screen (Account Config 1 with the new connect-management framing).
- "Not now" sets a `nudge_dismissed_at` timestamp; banner does not re-display.

Stored as a single row in a new `account_nudges` table (or as a column on `users` — choose at v5 implementation). One row covers the lifecycle (created_at, dismissed_at).

If athlete connects a provider any time before or after the 14-day mark, the nudge is moot and never displays.

### 5.3 No further escalation

The design intentionally does not escalate beyond the one nudge. Athletes who dismiss are committing to self-report; the v1-equivalent path is fully supported and not stigmatized in copy or UX.

---

## 6. Re-onboarding after later provider connect

### 6.1 The trigger

When `provider_auth.status` transitions to `'connected'` for a provider that was previously not connected (or never connected) — typically the OAuth callback's success path — the system runs the prefill-prompt evaluation.

### 6.2 The evaluation

For the just-connected provider P:

1. **Identify P's prefill-eligible fields.** Per Integration v4 §7 — the union of fields that P specifically can supply (not the full prefill-eligible set across all providers).
2. **For each such field, check current state.**
   - If the field's `source = 'manual_override'`: skip. Manual edits stick per decision #5.
   - If the field is empty (no value yet): include as "P can fill this in."
   - If the field has a value with `source = 'self_report'`: include as "P has a different value; replace?"
   - If the field has a value with `source = 'provider_<other>'`: re-resolve per §4.2 — if P's data is more recent than the existing source, include as "P has more recent data."
3. **Surface the prompt.** Modal or full-screen card:

```
Polar is now connected. We can use Polar to update these fields:

  HRmax           188 → 192 bpm    (currently from Garmin, 12 days ago)
  RHR             52 → 49 bpm      (currently self-report, 6 weeks ago)
  Body Weight     78.5 → 78.2 kg   (currently from Polar, just synced — no change shown)
  Sleep baseline  7h 12m → 7h 28m  (currently self-report, 6 weeks ago)

  [Apply all]    [Review per field]    [Skip for now]
```

4. **Three actions.**
   - **Apply all:** every listed field updates to P's value; `source` flips to `'provider_polar'`; `source_synced_at` updates; provenance tags update.
   - **Review per field:** each row gets its own apply/skip checkbox; athlete picks; submit applies the checked subset.
   - **Skip for now:** no field changes. The prompt re-surfaces once on the next session start ("Polar still has data we could pull in — want to review?") and then never again unless athlete manually triggers from Account Config 1.

### 6.3 Section-new fields after onboarding rewrite

If the v5 spec rewrite adds new fields (e.g., per the predecessor handoff's open items + the design wave), those fields are subject to the same prefill mechanics as existing fields. The §6.2 prompt only fires for fields that exist at the time of the provider connect; new fields added by a subsequent v5+ release prompt independently when the schema lands.

---

## 7. Schema additions

All new tables and columns land on `_PG_MIGRATIONS` only — `_SQLITE_MIGRATIONS` remains frozen per `Athlete_Data_Integration_Spec_v4` §2.5.

### 7.1 New table — `athlete_profile_field_provenance`

```sql
CREATE TABLE IF NOT EXISTS athlete_profile_field_provenance (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    field_name          TEXT NOT NULL,
        -- Logical field identifier (e.g., 'body_weight_kg', 'hrmax_bpm',
        -- 'easy_run_pace_min_per_km'). Naming convention defined at v5
        -- implementation; per-section prefix recommended for query
        -- patterns ('a_body_weight_kg', 'f_hrmax_bpm', 'd1_easy_run_pace').
    source              TEXT NOT NULL,
        -- 'self_report' | 'manual_override' | 'provider_polar' |
        -- 'provider_coros' | 'provider_wahoo' | 'provider_garmin' |
        -- 'provider_strava' | etc. Enum values match provider slugs from
        -- Integration v4 §3.
    source_provider_id  INTEGER REFERENCES provider_auth(id),
        -- FK to the specific provider_auth row that sourced this value.
        -- NULL for source IN ('self_report', 'manual_override').
    source_synced_at    TIMESTAMP,
        -- The provider-side update timestamp for the value (when the
        -- provider says the value was measured / observed). Drives
        -- most-recent-wins comparisons. NULL for source IN
        -- ('self_report', 'manual_override').
    last_updated_at     TIMESTAMP NOT NULL DEFAULT NOW(),
        -- Last write to this provenance row (any source change).
    UNIQUE (user_id, field_name)
);

CREATE INDEX IF NOT EXISTS apfp_user_idx
    ON athlete_profile_field_provenance (user_id);

CREATE INDEX IF NOT EXISTS apfp_user_source_idx
    ON athlete_profile_field_provenance (user_id, source)
    WHERE source = 'manual_override';
    -- Partial index supports the "show me my overridden fields" query
    -- without scanning the full per-user provenance set.
```

The actual field values continue to live on whatever table currently houses them (`athlete_profile`, `body_metrics`, etc., per Integration v4 §7.6's gap inventory). Provenance is sidecar.

### 7.2 New table — `account_nudges`

```sql
CREATE TABLE IF NOT EXISTS account_nudges (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    nudge_type          TEXT NOT NULL,
        -- 'connect_provider_14d' (decision #4). Future nudge types
        -- (re-test stale fields, missed scheduled overlay, etc.) extend
        -- the enum. Per nudge type, one row per user.
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    displayed_at        TIMESTAMP,
        -- First time the nudge was rendered to the athlete.
    dismissed_at        TIMESTAMP,
        -- Athlete dismissed; nudge will not re-display.
    UNIQUE (user_id, nudge_type)
);
```

### 7.3 Account Config 3 acknowledgment entries

No schema change to Account Config 3 itself (already specced in v4 lines 876–887). New `disclosure_id` values land in the v5 implementation:

- `oauth_scope_polar`
- `oauth_scope_coros`
- `oauth_scope_wahoo`
- `oauth_scope_strava`
- `oauth_scope_whoop`
- `oauth_scope_rwgps`
- `oauth_scope_trainingpeaks`
- `oauth_scope_zwift`
- `oauth_scope_garmin` (when restored)

Each carries a `version_id` matching the scope set requested at the time of acknowledgment.

### 7.4 Migration of existing v1 data

Andy is the sole v1 user with one test account. Migration approach:

1. After the v5 implementation lands, create one `athlete_profile_field_provenance` row per existing field on Andy's account with `source = 'self_report'`, `source_synced_at = NULL`, `last_updated_at = athlete_profile.updated_at` (or NOW() if no per-field timestamp exists in v1).
2. When Andy connects providers post-v5-launch, the §6 re-onboarding prompt fires per field; Andy picks per-field whether to accept provider data.
3. No bulk auto-rewrite. Self-report values land as `source = 'self_report'`, eligible for the prompt path but not silently overwritten.

This is consistent with the D-60 / D-61 athlete-driven migration pattern — no automatic data transformation; athlete confirms each change.

---

## 8. Cross-track interactions

| Track | What D-58 hands off | What D-58 consumes |
|---|---|---|
| **D-59** Place lookup + chain detection | No direct interaction. D-59 fields (locale name, mapbox_id, lat/lng, chain_id, category) are not provider-derivable; they remain self-report at locale-creation. Mapbox geocoding consent disclosure (D-59) and OAuth scope acknowledgments (D-58) coexist in Account Config 3. | No direct interaction. |
| **D-60** Shared gym profiles + overrides | No direct interaction. Gym equipment is not provider-derivable. Crowd-sourcing-contribution consent (D-60) and OAuth scope acknowledgments (D-58) coexist in Account Config 3. | No direct interaction. |
| **D-61** Plan-level schedule + session→locale assignment | The `daily_availability_windows` table (D-61) is not provider-derivable in v5. (Calendar-provider sync is a v2 candidate per the D-61 §9 explicit-not-covered list.) | No direct interaction. |
| **§A.1 disclosures** | The Connected Service consent disclosure (already specced at v4 line 156) gets a new firing point — the D-58 connect step at Step 2 of onboarding, plus at every subsequent connect from the management screen. Disclosure copy unchanged. | The account-creation acknowledgment (already at Step 1) is unchanged. |
| **Account Config 1** | Reframed from "connect here" to "manage your connections here." Connect still possible from this screen (covers post-onboarding connect path); the screen is no longer the *only* connect path. | The existing field set (Service Name, Connection Status, Last Sync, Scopes Granted, Sync Direction per v4 lines 855–861) is preserved. |
| **Account Config 3** | New `disclosure_id` values for per-provider OAuth scopes per §7.3. | The existing record shape (Disclosure Type, Acknowledged At, Version Seen, Delivery Method per v4 lines 880–885) is preserved. |
| **Integration v4 §7** | The prefill-eligibility list per §4.1 is the operative subset of §7's mapping; D-58 commits to honoring §7's per-field source designations. If §7 grows in a future Integration spec version (Integration v5), prefill-eligible field set grows correspondingly. | §7's per-field source mapping is the authoritative reference. D-58 doesn't redefine what counts as "Polar can supply RHR" — it reads §7. |
| **Integration v4 §8 (two-regime consumer model)** | No reshape. §8 is about Layer 3A's runtime data access; D-58 is about onboarding-time prefill. The two regimes (pre-integration / post-integration / mixed) continue to apply at runtime regardless of D-58. The connect-during-onboarding path means more athletes will land in the post-integration regime sooner. | §8's regime model is unchanged. |
| **D-50 wiring** | **Unblocks once D-58 lands.** Predecessor handoff §6.4 paused D-50 wiring on D-58's UX decisions. With D-58's connect step + per-field prefill mechanics specced, the wiring track can resume. The first wiring PR (per predecessor handoff §6.4) is now: `provider_auth.py` helper + first real OAuth flow for COROS + COROS webhook recording — all aligned with the D-58 connect step's expected callback shape. | The shipped D-50 schema (`provider_auth`, `webhook_events`, per-provider tables per Integration v4 §4–§5) is the storage layer D-58 reads from. |
| **Layer 3A** | The `manual_override` source flag is a runtime input — Layer 3A reads provenance to know whether an HRmax value is provider-derived or athlete-claimed. The 3A spec may already account for this implicitly (Integration v4 §8.2 mentions confidence-weighing); D-58 makes the provenance explicit at the field level. | Layer 3A's existing data model (per `Layer3_3A_Spec.md`) — D-58 does not modify 3A inputs, only enriches the metadata. |

---

## 9. What this design doc explicitly does NOT cover

- **OAuth flow implementation per provider.** Each provider's OAuth callback exchange, token storage shape, refresh skeleton, and webhook signature verification is `routes/{provider}.py` work owned by the D-50 wiring PRs (now unblocked). D-58 commits to the connect-step UX and the post-callback prefill behavior; it does not spec the OAuth handshake itself.
- **Provider-specific data shape.** What each provider returns for "RHR" and how AIDSTATION normalizes across providers (units, timestamp granularity, missing-data conventions) is Integration v4 §5 + §7 territory. D-58 reads §7's mapping but does not extend it.
- **Calendar-provider sync.** Importing weekly schedule windows from Google Calendar / iCal is a v2 candidate per the D-61 design doc. D-58 is fitness-provider OAuth only.
- **Sign-in via OAuth (e.g., "Sign in with Google").** Auth-system OAuth and integration-OAuth are different concerns. D-58 covers integration-OAuth only.
- **Apple Health / Samsung Health.** Out of scope per CLAUDE.md (need native iOS/Android clients). D-58 doesn't include them in the connect step's provider list.
- **Tolerance values per field for decision #9.** "Body weight ±0.5 kg, RHR ±2 bpm" are illustrative; the actual tolerance table lives in v5 implementation config and benefits from athlete-feedback iteration. The design commits to tolerance-based-suppression, not to specific values.
- **Per-provider prefill confidence scoring.** Layer 3A has its own confidence model (Integration v4 §8.2); D-58 uses most-recent-wins as the prefill choice rule, not a confidence-weighted choice. If a confidence model is needed at prefill time (e.g., "Garmin's HRmax is more reliable than Polar's"), it's a v5+ refinement.
- **Bulk re-onboarding trigger.** "Athlete clicks 'rebuild my profile from current providers' to re-run §6 across all providers at once" is plausible; not specced in v5. Backlog candidate.
- **The v5 implementation PR.** Schema migrations, OAuth flows, frontend changes (connect step, provenance tags, edit-in-place affordance, post-connect prompt), and Account Config 1 reframing are substantial; owned by the v5 onboarding implementation PR.

---

## 10. Gut check

**What this design got right.**

- **OAuth-first respects the v2 product premise.** AIDSTATION's claim to be data-driven, integration-grounded coaching is honest only if integration is the first thing the athlete touches. D-58 makes that real without making it required (graceful degradation per decision #4 covers athletes without providers).
- **Most-recent-wins is the right default.** Honest, simple, and athlete-correctable. The two harder defaults (per-provider preference, weighted blend) buy expressive power athletes won't tune.
- **Edit-in-place + manual_override stickiness closes the round-trip.** Every other approach leaves the "what happens to my edit when the next sync arrives" question unanswered. The stickiness flag + clear-override path makes the contract explicit at the field level.
- **The 14-day nudge is deliberately mild.** A coaching product that gates value on integration but bullies athletes who can't integrate is hostile UX. One soft nudge surfaces the value proposition without becoming notification spam.
- **Per-field opt-in on later connect respects athlete autonomy.** The post-connect prompt is the moment of "do you want me to update your profile?" — silent rewrite would have been a betrayal of trust on data the athlete entered intentionally.
- **Sidecar provenance table avoids fattening every value table.** Provenance grows additively without schema churn; the value tables stay clean and readable.
- **D-50 wiring unblocks cleanly.** The connect step's expected callback shape, the per-provider scope acknowledgment storage, and the post-callback prefill prompt all give the D-50 wiring PRs concrete contracts to build against. Wiring no longer waits on UX-shape questions.

**Risks.**

- **Most-recent-wins can be wrong in real cases.** A provider that aggressively over-syncs (e.g., a watch that uploads body weight every time it's worn, including with stale data) can win against a more carefully measured provider. Tolerance-based suppression (decision #9) helps but isn't a complete answer. Mitigation: athlete-correctable via manual override; long-term might need per-provider per-field staleness tolerances.
- **Provenance display may be visual clutter.** Every prefill-eligible field gets a tag underneath; on a dense form, this is a lot of metadata text. UX risk: athletes ignore tags, miss source attribution, and are surprised when a value seems wrong. Mitigation: tag styling should be subtle (smaller, lighter); the tag's job is "ambient honesty," not "demand attention."
- **manual_override stickiness can trap athletes.** An athlete who fat-fingers a body weight edit (78.2 → 782 kg) flips the field to manual_override; future syncs don't fix it. The clear-override path (decision #6) fixes this if the athlete notices. If they don't, the bad value persists. Mitigation: validation on numeric fields catches the worst cases (782 kg is implausible); subtler errors (78.5 vs. 78.2) fall through. Acceptable.
- **The 14-day nudge timing is arbitrary.** Could be 7 days, could be 30 days. 14 was Andy's recommendation pickup; there's no data to support 14 specifically. If first-cohort athletes report the nudge as too early or too late, tune. Backlog candidate for explicit telemetry.
- **Per-field provenance table grows linearly with athletes × prefill-eligible fields.** For Andy alone, ~30 prefill-eligible fields × 1 athlete = 30 rows. For 1000 athletes, 30K rows. Index-supported queries scale fine; storage is negligible. Not a near-term concern.
- **D-58 has no D-59/D-60/D-61 cross-track schema interaction.** All four design docs land independent migrations. Risk: in the v5 implementation PR, the combined migration order may have subtle dependencies (e.g., `account_nudges` references `users`; verifying users.id exists is trivial). Worth a sanity-check during the v5 implementation planning per the predecessor D-61 handoff §7's flagged "cross-design-doc consistency check."
- **Re-prefill cadence (decision #9) is the most under-specified piece of this design.** "Field-specific tolerance" is a knob the design names but doesn't set. Implementation will need to either pick reasonable defaults (and be wrong sometimes) or require per-field config (and be cumbersome). Defer; expect iteration.

**What might be missing.**

- **Conflict-resolution UX when two providers diverge significantly.** If Polar says HRmax 188 and Garmin says HRmax 198, most-recent-wins picks one and the divergence note shows the other. But neither is necessarily *right* — the athlete may have done a max-effort test that produced 198, and Polar's 188 is a stale resting max. The provenance tag surfaces the divergence; the athlete has to choose. Not specced beyond the surfacing — no "ask the athlete to pick" modal at first-prefill. Backlog candidate if real-world divergence is frequent.
- **Provider-disconnect behavior on prefilled fields.** When an athlete disconnects Polar, what happens to fields with `source = 'provider_polar'`? Options: (a) value persists with source flipped to `'self_report'` + a note ("last sourced from Polar before disconnect"); (b) field re-resolves to the next-best provider per §4.2; (c) field is cleared. Not specced. Recommend (a) with re-resolve on next display — implementation can land it; design doc commits to behavior in a v1.1 amendment if needed.
- **Audit trail for field-source changes.** `athlete_profile_field_provenance` stores current state; doesn't keep history. If an athlete asks "when did this change?", the table can't answer. Backlog candidate; v1 mitigation is application logging.
- **Field-name registry.** Decision #8's `field_name` column is free-text TEXT, not enforced against a known list. Risk: typos in implementation produce orphan provenance rows. Mitigation: a `KNOWN_PROFILE_FIELDS` constant in app code + validation on insert. Implementation detail; flag for v5 implementation PR.
- **Connected-provider list maintenance.** As Garmin restores, as new providers ship, the connect step's provider list grows. The list is presumably driven from a config / `provider_registry.py` file analogous to D-59's `chain_registry.py`; not specified here. Implementation detail; the design assumes a registry-driven UI exists.
- **The §6.2 prompt's screen real estate.** Listing 30 fields in a single modal is cramped. UX may benefit from grouping by section (§A fields, §F fields, etc.) or paginating. Implementation detail; the design commits to "surface a prompt with bulk-apply / per-field-review / skip" without prescribing the layout.

**Best argument against this design.**

The whole D-58 reshape is forward-looking design for a multi-provider integration story that doesn't exist yet. Per `D50_Phase1_Schema_Closing_Handoff_v1.md` and the D-50 review, all current "shipped" provider integrations are 19-line webhook stubs. None of Polar / COROS / Wahoo / Strava / Whoop / RWGPS / TrainingPeaks / Zwift have a real OAuth flow. So the connect step at Step 2 of onboarding has nothing to actually connect to. D-58's OAuth-first design is paper-only until D-50 wiring builds the per-provider flows.

A simpler v1: keep v4's flow (connect at Account Config 1, after onboarding); ship one real OAuth flow (COROS first per CLAUDE.md); add D-58's reshape as a v5.1 patch once at least 2–3 providers are real. The reshape is paid once at the right time, not now when there's nothing to reshape against.

Counter: the D-50 wiring track has been paused on D-58's UX decisions (predecessor handoff §6.4). Without D-58 settled, the wiring track can't define the OAuth callback's expected post-success behavior (does it redirect to onboarding step 3? to Account Config 1? back to the connect step for additional connects?). The wiring needs the UX shape *before* it builds any OAuth flow, otherwise the first OAuth flow gets built against an assumed UX that may be wrong. D-58 unblocks D-50 by making the post-callback contract concrete. Plus Andy's "push to production as we go" rule favors shipping the right shape now (one cohesive v5 spec rewrite) over patching post-launch.

Alternative phasing: ship the v5 spec rewrite consolidating all four design tracks; the v5 implementation PR builds the connect step + prefill mechanics around a single working OAuth provider (COROS); subsequent provider OAuth flows ship per-provider against the now-real connect step. This is the recommended path; the design doc as written supports it (the connect step's UI degrades gracefully with N=1 connected provider).

---

*End of D-58 design doc. Final track of the Onboarding Design Wave. Next: `Athlete_Onboarding_Data_Spec_v5.md` consolidating D-59 + D-60 + D-61 + D-58 into a single spec rewrite.*
