# Athlete Onboarding Data Spec — v7

**Version:** 7.0
**Status:** Onboarding Design Wave consolidated. D-58 + D-59 + D-60 + D-61 absorbed into the spec body. Spec body complete pending Open Items. v7 promotes the built #257 Section-I v3 fields and resolves the Section_I_Audit Fix-now #4 sweat/salt conflation.
**Last updated:** 2026-06-30
**Supersedes:** `Athlete_Onboarding_Data_Spec_v6.md` (v6.0, 2026-05-25)
**Built:** May 2026

## What changed in v7 vs v6

**#257 — Section-I v3 onboarding fields promoted to built (2026-06-30).** Five fields from the Section_I_Audit v3-candidate set shipped this slice; the spec now carries them in their sections:

- **§A Body** — `Body-weight Trend (3 mo)` (V3-I-10).
- **§I.1 Core lifestyle** — `Sleep Consistency` (V3-I-1) and `Daily Hydration Baseline` (V3-I-9).
- **§I.2 Race-day fueling** — `Sweat Rate` split out from `Salt / Electrolyte Loss` (V3-I-4). This **resolves Section_I_Audit Fix-now #4**: the v2 single enum conflated sweat *rate* (volume → fluid) with salt *loss* (concentration → sodium). Layer 2E now scales the race-day **fluid** band on Sweat Rate and the **sodium** band on Salt / Electrolyte Loss independently.
- **§I.1 Dietary Pattern** — vocabulary gains `low_carb` and `fat_adapted` (V3-I-2; a macro axis distinct from `keto` / `paleo`).

Dropped from the v3 set: V3-I-3 (caffeine CYP1A2 genetic flag — not self-knowable; daily-dose proxy suffices). V3-I-7 (supplement restructure) was already built (the `athlete_supplements` structured capture). No other section changes.

## What changed in v6 vs v5

**FormRefresh Slice C — schedule simplification (infer long day + rest days).** §G no longer asks for the standalone "Long Session Available" (Y/N + day + max-duration) or "Preferred Rest Day(s)" inputs. The weekly long session is now the **longest enabled daily window** — the primary-window duration ceiling is raised 360→720 min (6→12 h) so an expedition-length long day fits — and the rest days are the **disabled days** (`enabled=FALSE`). Both are derived from the per-day windows rather than entered, removing the redundant triple-entry (window + long-day picker + rest-day picker). `daily_availability_windows.window_duration_min` CHECK bound raised to 720; the `athlete_profile.long_session_available` / `long_session_days` / `long_session_max_hr` / `preferred_rest_days` columns are dropped. `doubles_feasible` is the sole surviving §G `athlete_profile` scalar.

Sections touched: §G.1 (Long Session + Preferred Rest rows removed; Daily Windows duration range 360→720), §G.2 (long-session day + rest days added as derived values), §G.3 (the long-session window-override rule removed — the window *is* the long session), §M.1 (the "Athlete updates Long Session Available" lifecycle trigger removed). No other section changes.

## What changed in v5 vs v4

All four architectural items the v4 spec flagged for "dedicated design sessions" are now folded in. The change is large because the four sessions covered four different concerns; the consolidation is mechanical, not interpretive — each change is traceable to one of the four shipped design docs.

| Change | Driver | Sections touched |
|---|---|---|
| **OAuth-first onboarding flow.** Provider-connect moves to Step 2 of onboarding (after account-creation acknowledgment, before §A). Connected Service consent disclosure fires there. Provider data prefills eligible fields via most-recent-wins + edit-in-place + manual_override stickiness. Athletes who connect no providers see a single soft nudge after 14 days. Re-onboarding after later connect prompts per-field opt-in. | `Onboarding_D58_Design_v1.md` | §A flow framing, §A.1 (Connected Service consent firing point), §A–§F + §I (prefill-eligible field annotations), Account Config 1 (reframed manage-only), Account Config 3 (per-provider OAuth scope acknowledgments). New tables: `athlete_profile_field_provenance`, `account_nudges`. |
| **Locale place lookup + chain detection.** §J.1 Locale gets Mapbox-anchored coords, stable place identifier, chain detection via a curated `chain_registry.py` module + Mapbox category hints, manual-address fallback, on-demand refresh, single-acknowledgment privacy disclosure. | `Onboarding_D59_Design_v1.md` | §J.1 (locale-level fields), §J overview (locale-creation flow), §A.1 (Mapbox geocoding consent disclosure), Account Config 3 (Mapbox consent disclosure_id). New columns on `locale_profiles`: `locale_name`, `mapbox_id`, `lat`, `lng`, `chain_id`, `chain_name`, `category`, `manual_entry`, `place_payload`, `place_fetched_at`. |
| **Shared gym profiles + per-athlete overrides.** §J.2 (equipment) and §J.3 (sport-specific gear toggles) become two-layer: shared profile per physical address (crowd-sourced default-on, opt-out at account level) + per-athlete add/remove overrides. Plan-gen reads the athlete's effective view. Locale categories collapse to a 10-value enum; only seven of the ten expect a shared profile. | `Onboarding_D60_Design_v1.md` | §J.2, §J.3, §J overview (category taxonomy), §A.1 (gym-profile sharing consent disclosure), Account Config 3 (sharing consent disclosure_id). New tables: `gym_profiles`, `locale_equipment_overrides`, `locale_toggle_overrides`. New columns on `locale_profiles`: `gym_profile_id`, `sharing_opt_out`. |
| **Plan-level schedule + per-session locale assignment.** §G is rewritten with per-day windows (enabled/start/duration + optional second window when Doubles Feasible). "Available Training Hours per Week," "Training Days Available," and "Typical Session Duration" are dropped as explicit fields — derived/displayed from per-day data instead. "Preferred Rest Day(s)" is demoted Tier 1 → 2. Long Session Available and Doubles Feasible remain Tier 1 orthogonal toggles. §J.5 (Locale Capacity Metrics — "Typical session time available," "Max session duration") is **deleted entirely** — locale equipment + safety, not athlete-entered time fields, determine whether a session fits at a locale. Per-session locale assignment runs through a deterministic resolver (anchor-locale → proximity cluster → equipment-qualifying → preferred-flag → closest-by-distance) at plan-gen time; athletes can JIT-swap to another qualifying locale from the session card. | `Onboarding_D61_Design_v1.md` | §G (full rewrite), §J overview (preferred-locale flag), §J.5 (deleted), session-card UX (cross-references Layer 4 plan-gen). New table: `daily_availability_windows`. New column on `locale_profiles`: `preferred`. |

No vocabulary changes outside the four design tracks. No tier changes outside §G's Preferred Rest Day demotion. No changes to §B / §C / §D / §E / §F / §H / §I / §K / §L / Account Config 2 / Account Config 4 / Plan Management 1–5 field content (only annotation updates where D-58 prefill applies to existing fields).

**Predecessor history:**
- v4 (2026-05-13) — v3 + scope clarifications (pregnancy never captured; no shooting/fencing technical readiness — ever); deferred D-58/D-59/D-60/D-61 to dedicated design sessions
- v3 (2026-05-13) — §H.3 Non-Event Goal Type added
- v2.5 (2026-05-06) — §B.1.1 bone split; v2.4 — joint mechanical split; v2.3 — batch 4+5; v2.0–v2.2 — Batches 1–5

**Sources reconciled (carried forward from v4):**
- v1 spec
- `V2_spec_decisions_handoff.md` (authoritative for the three locked v2 decisions)
- `V2_Reconciliation_Findings.md`
- v2 batch docs
- `Vocabulary_Audit_v2.md` (controlled vocab)
- `Onboarding_Session_Handoff.md`
- `L3_Discovery_Closing_Handoff_v1.md`

**New for v5:**
- `Onboarding_D58_Design_v1.md` — OAuth-first flow + provider-sourced prefill
- `Onboarding_D59_Design_v1.md` — Mapbox geocoding + chain detection
- `Onboarding_D60_Design_v1.md` — Shared gym profiles + locale category taxonomy
- `Onboarding_D61_Design_v1.md` — Plan-level schedule + session-to-locale assignment
- `Athlete_Data_Integration_Spec_v4.md` §7 (per-field provider source mapping; consumed by D-58 prefill mechanics)

---

## Purpose

Defines the complete athlete-side data the training plan app collects from a user, organised into three top-level groups:

1. **Athlete Data** — what drives plan generation (§A–§L)
2. **Account Configuration** — how the user's account integrates with services and tracks consent (Connected Services, Gym Memberships, Disclosure Acknowledgments, Privacy)
3. **Plan Management** — how plans are generated, updated, and reconciled across linked athletes (Profile Update Triggers, Adherence Drop, Plan Duration logic, joint-training generation)

This split clarifies what's onboarding-blocking versus account-level versus deferred to runtime.

v5 is **agnostic to UX flow** for §B onwards. What screens exist, what's collected upfront vs. deferred, what's a wizard vs. a settings page — separate design pass. v5 does, however, commit to a specific **onboarding step ordering for §A and the surrounding pre-data-entry surfaces** (account creation → acknowledgment → provider-connect → §A onwards) per D-58. See "Onboarding step sequence" below.

---

## Onboarding step sequence

New in v5. Replaces v4's implicit "athlete just enters fields in order, providers connected post-onboarding" model.

| Step | Owner | What happens |
|---|---|---|
| 0 | Auth system | Sign-up / sign-in. Email + password (or sign-in-with-Google etc. — out of scope here). |
| 1 | §A.1 account-creation acknowledgment | One-time disclaimer acknowledgment (training carries risk, app provides recommendations not medical advice, athlete responsible for medical clearance). Existing v4 disclosure; firing point unchanged. |
| 2 | D-58 connect step | "Connect your fitness providers" screen. Lists supported providers (Polar, COROS, Wahoo, Strava, Whoop, RWGPS, TrainingPeaks, Zwift, Garmin-when-restored). Athlete connects 0 or more via per-provider OAuth. Connected Service consent disclosure (§A.1) shown inline at each connect; per-provider scope acknowledgment recorded in Account Config 3. Athlete clicks "Continue" when done — at any time, including with zero providers connected. |
| 3 | §A entry | §A fields. Provider-prefillable fields (Body Weight at minimum) display with provenance tag per §A.2 prefill mechanics. |
| 4 | §B–§L | Remaining onboarding sections in order. Each section's prefill-eligible fields (per Integration v4 §7 mapping) display with provenance for connected providers. |
| 5 | Account Config screens | Configuration sections (Gym Memberships, Privacy, etc.). Account Config 1 becomes a *management* screen (disconnect / re-auth / scope-update) rather than a connect screen — connect happened at Step 2. |
| 6 | Plan creation | Schedule (§G) and Target Events (§H) drive Layer 4 plan-gen; per-session locale assignment runs through the resolver per §G.3. |

The connect step (Step 2) is skippable. Athletes who skip see no provider-prefilled values; every §A–§L field renders as v1-style self-report. A single soft nudge fires after 14 days of self-report-only use (see §A.2.4).

---

## Tier definitions (unchanged from v1)

- **TIER 1** — Required. Plan generation cannot produce a meaningful output without it.
- **TIER 2** — Important. Significantly improves plan specificity. App should prompt for it but accept deferred entry.
- **TIER 3** — Optional. Refinement only.

---

## Connected Services data convention

v4 marked fields with "Manual entry from FIT export at launch; Connected Service post-launch." v5 makes this concrete: **prefill-eligible fields read from connected providers per the mapping in `Athlete_Data_Integration_Spec_v4.md` §7.** Field-level prefill behavior is governed by §A.2 (provenance, edit-in-place, manual_override stickiness, tolerance-based re-prefill, post-connect prompt). Fields the spec marks "self-report only" never prefill regardless of which providers are connected.

Freshness rules carry forward from v1: ≤90 days for activity-derived fields, ≤30 days for wellness-derived fields. Freshness is enforced against the provider's source-timestamp for prefilled fields and against athlete-edit timestamp for self-report fields.

---

# Group 1 — Athlete Data

The data that drives plan generation. Sections §A through §L. All sections are athlete-scoped (one record set per user) except §J Locales (1+ per athlete), §K Locale Schedule (0+ overlays), §L Athlete Network (0+ links).

---

## Section A — Athlete Identity

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Name | Text | 1 | Labeling only | Self-report |
| Date of Birth | Date (Month/Year) | 1 | Volume ceiling, ramp rate, masters injury stratification (40+), age-group categorization | Self-report |
| Sex | Enum (M/F) | 1 | Event categorization for mixed relays; physiological adaptation rates; HR zone calibration; iron metabolism flags | Self-report |
| Height | Number (cm or ft/in) | 2 | Body composition context, swim drag, bike fit, OCR obstacle scaling | Self-report (no reliable provider source at launch) |
| Body Weight | Number (kg or lb) | 1 | W/kg cycling, calorie targets, OW buoyancy, pack-weight % of bodyweight | Provider-prefill (Polar / Garmin / Wahoo wellness sync per Integration v4 §7.1) with edit-in-place override; monthly fallback if no provider connected |
| Body-weight Trend (3 mo) | Enum (Stable / Gaining / Losing / Significant gain / Significant loss; significant = >5% over ~3 mo) | 3 | Fueling-target accuracy; the significant bands are an energy-availability / RED-S signal | Self-report — #257 V3-I-10 |
| Primary Training Location | Text (Country/State/City) | 1 | Seeds required home locale; climate, altitude, terrain defaults | Self-report at locale setup |

**Notes on what's not collected:**

Gender identity is not collected. Sex (M/F) is collected because plan logic genuinely depends on it (HR zones, iron metabolism, event categorization for mixed-team races where rules apply). Gender identity drives no plan logic; collecting it without using it adds friction without value. Athletes whose physiology differs from their assigned sex due to HRT or other medical context capture that through §B Medications, which is read independently of §A Sex.

**HRT and programming:** Where an athlete is on hormone replacement therapy, programming should respond to the medication record in §B, not to a presumed mapping from §A Sex. v5 (like v2–v4) treats biological sex (§A) and hormonal milieu (§B) as separate inputs to plan generation.

### A.1 Disclosures

A.1 documents what the athlete is shown and asked to acknowledge during onboarding and at certain plan-generation moments. The athlete's acknowledgment state (timestamp, content version, what was shown) is stored in Account Configuration 3.

| Disclosure | When shown | What it covers |
|---|---|---|
| Account-creation acknowledgment | One-time, at account creation (Step 1) | Replaces v1's removed Physician Clearance field. User acknowledges training carries inherent risk; app provides plan recommendations, not medical advice; user is responsible for medical clearance with their own provider |
| **Connected Service consent** | At the D-58 connect step (Step 2) and at any subsequent connect from the management screen | Per-service scope acknowledgment — what data is read, frequency, revocation path. **Firing point updated in v5: was "at Connected Service connect flow (Account Config)" in v4; is now the new onboarding connect step + management-screen connects.** Disclosure copy unchanged from v4 |
| **Per-provider OAuth scope acknowledgment** | At each OAuth flow for a specific provider (new in v5) | Specific scopes granted to that provider in this OAuth flow. Captures `scopes_granted` snapshot. Re-acknowledgment required when scope set changes. One record per provider per acknowledgment event |
| Sex-collection inline disclosure | At the §A Sex field | Brief explainer (unchanged from v4) |
| Health-data inline disclosure | At §B section entry | Brief explainer on data sensitivity (unchanged from v4) |
| HRT inline disclosure | At §B Medications when an HRT-class drug is entered | Brief explainer that HRT presence overrides §A Sex assumptions (unchanged from v4) |
| **Mapbox geocoding consent** | First time the athlete uses §J place lookup (new in v5) | "We send your address to Mapbox to look up coordinates and find nearby gyms. AIDSTATION stores Mapbox's response (place name, coordinates, category). You can use manual address entry instead." Single acknowledgment per athlete; subsequent locale creations don't re-prompt |
| **Gym-profile sharing consent** | First time the athlete creates or edits a shared gym profile (new in v5) | "Your equipment edits at commercial gyms, climbing gyms, and pools will be shared with other AIDSTATION athletes who train at the same locations. Your identity is never shared. Home gyms and private residences are never shared. You can opt out at any time" |
| Linked-partner data-sharing disclosure | At §L Athlete Link creation when Linked Account FK is set | What the other party sees; what they don't; revocation flow (unchanged from v4) |
| **Race-rules paste acknowledgment** | At §H.2 Race Rules Summary field when athlete enters text (D-66 amendment 2026-05-18) | Athlete confirms text is from the official race director's published guide; AIDSTATION uses these to generate the race-week brief and accepts no responsibility for AI-misinterpretation of pasted text. Single acknowledgment per athlete per race_events row; subsequent edits to the same row don't re-prompt |

**Copy is product/legal-owned.** Specific wording for each disclosure is a separate design pass. A.1 specifies the **slots**; the actual text is filled in pre-launch.

**Storage of acknowledgment state:** see Account Config 3.

### A.2 Provider-sourced prefill mechanics

New in v5. Specifies how connected-provider data fills onboarding fields and what happens when the athlete edits a prefilled value.

#### A.2.1 Eligibility

A field is **prefill-eligible** if Integration v4 §7 maps it to at least one provider source. The prefill-eligible set across §A–§L:

| Section | Prefill-eligible fields |
|---|---|
| §A | Body Weight |
| §C | Current Weekly Training Volume; Most Recent Race Results; (partially) Training Consistency 12 mo |
| §D.1 (Run) | Easy Run Pace; Recent Race Paces; Vertical Gain Tolerance |
| §D.2 (Cycle) | Longest Ride 12 mo |
| §D.3–D.7 | Volume / longest-session fields per discipline |
| §F | HRmax; Lactate Threshold HR (where provider supplies); VO2max Estimate; Cycling FTP (when Wahoo FTP API ships) |
| §I | Average Nightly Sleep |

Self-report-only fields (Sex, DoB, Years of Structured Training, all §B health conditions, all §E strength benchmarks, Pack Load Training History, Trail Running Experience, all §G schedule fields, all §J locale fields, etc.) are NOT prefill-eligible and behave as in v4.

#### A.2.2 Per-field prefill resolution

For each prefill-eligible field on a screen the athlete is viewing:

1. **Check `manual_override`.** If `athlete_profile_field_provenance.source = 'manual_override'`, render the stored value with the "manually set on YYYY-MM-DD" tag + "use provider value instead" affordance. Skip the rest of the resolution.
2. **Check connected-provider candidates.** Query `provider_auth` for the user's currently connected providers. For each, check whether that provider has supplied a value for this field.
3. **Pick most-recent.** Among the candidates, pick the one whose latest sync delivering this field is most recent. Render its value with the "from {provider}, {age}" tag.
4. **Surface divergence (when present).** If a non-winning candidate's value differs from the winning value by more than the field-specific tolerance, append "; {alt-provider}: {alt-value}" to the tag.
5. **No candidates.** Render the field as v1-style self-report (empty, athlete fills in). `source` remains `'self_report'` until athlete edits or a provider sync delivers a value.

#### A.2.3 Edit semantics

| Athlete action | System action |
|---|---|
| Athlete types into a prefilled field | Field value updates to athlete's input; `source` flips to `'manual_override'`; provenance tag fades; `last_updated_at` bumps |
| Athlete clears a prefilled field | Same: `source` flips to `'manual_override'`; value becomes empty (subject to validation — required fields enforce) |
| Athlete clicks "use provider value instead" on an overridden field | `source` reverts to the relevant provider; value reverts to the provider's most-recent value; tag refreshes |
| Athlete enters a value into a never-prefilled field | `source` set to `'self_report'`. Behaves like v1 |
| Provider sync delivers a value for a field | If `source = 'manual_override'`: do nothing visible (silently store as "candidate" available via override-clear path). If `source = 'provider_<X>'` from the same provider: tolerance-based update (silent if within tolerance, passive notification if beyond). If `source = 'provider_<Y>'` (different provider) and the new sync is more recent: re-resolve per A.2.2; if winning provider changes, surface as passive notification. If `source = 'self_report'`: prefill silently (athlete had no value) |

Tier 1 required fields without a value (no provider, no athlete entry) block onboarding completion as in v4. Provider prefill counts as "has a value" — the athlete doesn't have to confirm a prefilled value to proceed.

#### A.2.4 No-providers-connected path

Athletes who skip Step 2 or connect zero providers proceed to §A entry with no prefilled values. Onboarding completes via the v1-equivalent self-report path. After **14 days** of self-report-only use (measured from account creation) AND zero connected providers, a single passive in-app banner appears: "AIDSTATION works best with a fitness provider connected. Want to set one up?" Dismissable. One nudge only — no further escalation. Stored as a row in `account_nudges` with `nudge_type='connect_provider_14d'`.

If athlete connects a provider any time before or after the 14-day mark, the nudge is moot and never displays.

#### A.2.5 Re-onboarding after later provider connect

When `provider_auth.status` transitions to `'connected'` for a provider that was previously not connected, the system runs a prefill-prompt evaluation for that provider:

1. Identify the provider's prefill-eligible fields per Integration v4 §7.
2. For each, check current state:
   - `source = 'manual_override'`: skip (manual edits stick)
   - Field is empty: include as "P can fill this in"
   - `source = 'self_report'` with a value: include as "P has a different value; replace?"
   - `source = 'provider_<other>'`: re-resolve; include if P's data is more recent
3. Surface a prompt with three actions: **Apply all** (bulk update), **Review per field** (per-row checkbox), **Skip for now** (re-prompts once on next session start, then never).

Manual_override fields never appear in this prompt.

#### A.2.6 Manual override clear path

The provenance tag for an overridden field reads "manually set on YYYY-MM-DD"; clicking opens a popover with "Use Polar value (78.2 kg, last synced 2 days ago) instead." Restores prefill behavior and removes the stickiness flag.

#### A.2.7 Tolerance-based re-prefill cadence

When a provider sync delivers a field already prefilled from that same provider:

- If the new value differs from stored by more than a field-specific tolerance (e.g., body weight ±0.5 kg, RHR ±2 bpm), update silently and bump `source_synced_at`.
- If divergence exceeds tolerance OR the provider source has changed (most-recent-wins switched to a different provider), surface a passive notification ("Polar updated your HRmax: 188 → 192 bpm. [Use new value] [Keep old]").
- Manual_override fields never auto-update regardless.

Tolerance values per field are owned by the v5 implementation config; v5 spec commits to tolerance-based suppression, not to specific values.

---

## Section B — Health Status

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Current Injuries | Injury Record (1+, see B.1) | 1 | Exercise filtering via col 9 + col 13 | Self-report |
| Injury History (last 3 years, resolved) | Injury Record (0+, status=Resolved) | 2 | Preventive exercise prioritisation | Self-report |
| Health Conditions | Health Condition Record (0+, see B.4) | 1 | Volume ceiling, HR ceiling, altitude flags, carb-timing for diabetic ultra athletes, system-specific filtering | Self-report |
| Current Medications (training-relevant types only) | Multi-select | 2 | Beta blockers → RPE not HR; diuretics → hydration; NSAIDs → injury masking flag; HRT → programming-independent of biological sex | Self-report |
| Food Allergies & Intolerances | Multi-select + free text | 2 | Race nutrition planning, aid station strategy, anaphylaxis kit flag | Self-report |
| Resting Heart Rate | Number (bpm) | 2 | HR zone calibration; >10 bpm above baseline = overtraining flag | Provider-prefill (5+ day average) per A.2 mechanics |

The Disclosure Acknowledgment for §B (see A.1) is shown at section entry.

### B.1 Injury Record substructure

Unchanged from v4. Each injury record contains Body Part / Side / Injury Type / Severity / Movement Constraints / Date of Onset / Status History / Notes. Full schema, including B.1.1 Injury Type enumeration and B.1.2 Re-injury preventive priority rule, carries forward verbatim from v4 §B.1.

### B.2 Body Part enumeration

Unchanged from v4. 41 canonical body parts per `Vocabulary_Audit_v2.md` §1.

### B.3 Movement Constraint enumeration

Multi-select per injury; maps to exercise DB col 9 keyword patterns. **Amended 2026-05-25:** `Pain with wrist extension` folded into `Pain above specific joint angle` (enumeration 11 → 10); the former entry's `wrist extension` / `palm-down` keyword bundle now rides on `Pain above specific joint angle` (see `Layer2D_Spec.md` §5.3.3). The injury form narrows the visible constraints to those relevant for the selected body part (`athlete.BODY_PART_CONSTRAINTS`). Otherwise unchanged from v4.

### B.4 Health Condition Record substructure

Unchanged from v4. Includes B.4.1 System category enum and B.4.2 Auto-population rules (anaphylaxis flag → Immune/GI suggestion; condition-specific medication → matching system category; RHR outlier with sex-adjusted thresholds → Cardiac suggestion).

---

## Section C — Training History & Fitness Baseline

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Years of Structured Training | Integer | 1 | Year 1: 6%/wk ramp + mandatory 3-on-1-off; veteran 5+ yr: 10% ramp | Self-report |
| Primary Sport | Single-select (from 18 framework sports in `Sports_Framework_v3.xlsx` Sheet 1) | 1 | Aerobic base transferability; seeds Discipline Weighting defaults | Self-report |
| Secondary Sports / Disciplines | Multi-select + experience tier per (Under 1yr / 1–3yr / 3+ yr) | 1 | Per-discipline base-build vs. accelerated vs. maintenance decision | Self-report |
| Discipline Weighting | Per-discipline % (slider/numeric, sum=100) | 2 | Volume allocation across disciplines (hours, not priority levels) | Default + self-edit |
| Current Weekly Training Volume | Number (hrs/wk) + per-discipline breakdown | 1 | Week 1 starting point; ACWR 0.8–1.3 from day 1 | Provider-prefill per A.2 mechanics |
| Peak Historical Weekly Volume | Number (hrs/wk) + year | 2 | Proven physiological ceiling; never target >20% above prior peak without extended base | Self-report |
| Longest Event Completed | Text (event, distance, time, year) — within 2 yrs preferred | 1 | Race endurance proof; gates ultra distance jumps | Self-report |
| Most Recent Race Results | Structured list (last 3–5 races) | 2 | Fitness calibration; pace/FTP/CSS estimation | Provider-prefill per A.2 mechanics |
| Training Consistency (last 12 mo) | Number (disrupted weeks) + cause | 2 | High disruption → conservative ramp + flexibility; chronic travel → auto-activate hotel substitution | Provider-prefill (partial) + self-report fallback |
| Pack Load Training History | Pack Training Record (see C.1) | 2 | Pack-load ramp rate; race-pack tolerance gate | Self-report |
| Previous Coaching/Plans | Single-select (Self / Online plan / Coach / None) | 3 | Calibrates plan complexity | Self-report |

**On Discipline Weighting:** unchanged from v4. Single athlete-level set of weights summing to 100; defaults from `Sports_Framework_v3.xlsx` Phase Load Allocation midpoints; user can edit; zeroed disciplines allowed.

**Pack Load Training History tier rationale:** unchanged from v4. Tier 2 by default; effectively Tier 1 for athletes with AR / expedition / mountain-marathon target events.

### C.1 Pack Training Record substructure

Unchanged from v4.

---

## Section D — Discipline-Specific Baselines

Sport-relevant fields collected only when the athlete's Primary Sport, Secondary Sports, or §H Constituent Disciplines include the relevant discipline. UX implication: dynamic — only relevant sub-sections are shown. For database design: every field is nullable; null means "not asked."

Structural changes from v4: none. v5 only annotates which fields are provider-prefill-eligible per A.2; the field inventory is unchanged.

### D.1 Running

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Easy Run Pace | Time (min:sec/km or /mile) | 1 | Zone 2 anchor; 80/20 polarised distribution | Provider-prefill per A.2 mechanics |
| Recent Race Paces (5K/10K/HM/Mar) | Per distance | 2 | McMillan/Riegel pace prediction | Provider-prefill per A.2 mechanics; or derived from §C |
| Trail Running Experience | Y/N + terrain category (mod/tech/mtn/moor) + Night Y/N | 1 | Road→trail: 8–12 wk terrain adaptation; moorland is non-transferable from road | Self-report |
| Downhill Running Adaptation | Y/N + sessions/3mo at >-10% grade | 1 | **CRITICAL** — only proven EIMD prevention is prior exposure; no adaptation = -5% start max | Self-report |
| Vertical Gain Tolerance | Number (m/wk current) + peak single-session (m) | 1 | Primary load metric for mountain sports; max 10%/wk increase | Provider-prefill per A.2 mechanics |
| Night Running Experience | Y/N | 2 | 100M ultra + multi-day AR: 2–3 night sessions mandatory in peak phase | Self-report |
| Gut Training History | Number (g/hr CHO sustained without GI distress) + issues | 1 | Ultra finisher avg 70 g/hr, non-finisher <45 g/hr | Training log |

### D.2 Cycling

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Bike Types Available | Multi-select (Road/Gravel/MTB-HT/MTB-FS/TT-Tri/CX/Trainer-only) | 1 | XTERRA/AR require MTB; TT events require TT/tri bike | Multi-select |
| MTB Technical Skill | Enum (Beginner/Intermediate/Advanced) | 1 | Cannot start at race-difficulty terrain without skill base | Self-report |
| Longest Ride (12 mo) | Distance + time, self-supported flag | 2 | Endurance baseline; peak training ride targets 70–80% of event distance | Provider-prefill per A.2 mechanics |
| Saddle Endurance | Longest comfortable consecutive hours + issues | 2 | Events >4 hr saddle-limited not aerobic-limited | Self-report |
| Aero Position Endurance (TT only) | Time (min) sustainable + issues | 2 | TT FTP 3–8% lower than road; start 20 min/session if new | Self-assessment during ride |

### D.3 Swimming

Unchanged from v4. Fields: Pool 100m Pace, Open Water Experience, Wetsuit Experience, Cold Water Experience, OW Marathon Feeding Experience, Weekly Swim Volume. Weekly Swim Volume is provider-prefill-eligible per A.2.

### D.4 Paddling (Kayak / Canoe / Packraft)

Unchanged from v4. Longest Paddle (12 mo) is provider-prefill-eligible per A.2.

### D.5 Skiing (XC / Nordic / Skimo)

Unchanged from v4.

### D.6 Navigation

Unchanged from v4.

### D.7 Technical Disciplines

Unchanged from v4. Rock Climbing Experience + Abseiling Experience only. Shooting and Fencing remain out of scope per v4 — AIDSTATION does not program shooting or fencing technique.

---

## Section E — Strength, Core & Balance Benchmarks

Unchanged from v4. Manual entry only — these don't prefill from connected providers. Front plank, dead bug, side plank, push-ups, bodyweight squat, single-leg squat, pull-up max, dead hang duration, grip strength.

---

## Section F — Performance Testing Baselines (Aerobic & Lab)

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Maximum Heart Rate (HRmax) | Number (bpm) + source (measured/estimated) | 1 | All HR zone calculations | Provider-prefill per A.2 mechanics; Tanaka (208 - 0.7×age) fallback |
| Lactate Threshold HR | Number (bpm) + method | 2 | Primary intensity anchor for threshold zones | Provider-prefill (where available) per A.2; or 30-min hard effort avg / lab test |
| VO2max Estimate | Number (ml/kg/min) + source | 3 | Aerobic capacity ceiling | Provider-prefill per A.2; or Cooper test |
| Cycling FTP | Number (W) + test date | 2 | All cycling zones; W/kg climbing performance. Soft warning at plan gen if cycling intervals scheduled | Provider-prefill per A.2 (when Wahoo FTP API ships); or 20-min TT / ramp test |
| Running Threshold Pace | Pace (min:sec/km or /mile) + test date | 2 | Run interval prescription | 30-min TT (final 20 min avg) or 5K race pace proxy |
| Critical Swim Speed (CSS) | Time (min:sec/100m) + test date | 2 | Pool interval prescription | 400m TT + 200m TT |

**Section banner (UX guidance):** unchanged from v4.

**Soft-warning linkage:** unchanged from v4. Each Tier 2/3 field's plan-generation behavior when missing is captured in the Plan Management profile-update spec's classification table (Plan Management 2 §M.4).

---

## Section G — Schedule & Availability

**Full rewrite in v5 per `Onboarding_D61_Design_v1.md`.** v4's six-field structure ("Available Training Hours per Week," "Training Days Available," "Preferred Rest Day(s)," "Typical Session Duration," "Long Session Available," "Doubles Feasible") is replaced with a per-day window shape plus two orthogonal capacity toggles. Three of the v4 fields are dropped as explicit inputs; their values are computed and displayed.

### G.1 Fields

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Daily Windows | Repeating per day of week (Sun–Sat): `enabled` (Boolean) + `window_start` (time-of-day) + `window_duration` (minutes, integer 30–720) + optional `second_window_start` + `second_window_duration` (minutes 30–360, gated on Doubles Feasible ≠ No) | 1 | Hard scheduling envelope per day; plan-gen places sessions inside windows; days with `enabled=FALSE` are unavailable for any non-rest session (they are the athlete's rest days). The **longest enabled primary window is the weekly long session** — its 12 h ceiling carries expedition-length long days | Self-report |
| Doubles Feasible | Enum (Regularly / Occasionally / No) | 1 | Whether second windows can be entered for any day; gates the second-window fields' visibility | Self-report |

**FormRefresh Slice C (2026-05-25) removed two v5 fields from this table:** *Long Session Available* (Y/N + day-picker + max-duration enum) and *Preferred Rest Day(s)*. The long session is now derived as the longest enabled window (§G.2), and rest days are the disabled days — neither is asked. This eliminated the redundant triple-entry where the athlete set a window, then separately re-picked which day was "long" and which were rest.

### G.2 Derived / displayed values (not entered)

The following fields are dropped as explicit inputs and surfaced as derived values in the §G UI:

- **Available Training Hours per Week** — sum of `window_duration` across all enabled days + second windows. Displayed as athletes enter per-day data ("you've allocated 6.5 hrs/week").
- **Training Days Available** — derived from `enabled=TRUE` rows.
- **Typical Session Duration** — modal value of `window_duration` across enabled days. Optional display only; not stored.
- **Weekly long session** *(Slice C)* — the enabled day with the greatest primary `window_duration`. Plan-gen places the long session there; no separate day-picker. The 720-min (12 h) primary-window ceiling lets an expedition athlete express an 8–12 h long day directly in the window (the dropped `long_session_max_hr` enum topped out at "8+").
- **Rest days** *(Slice C)* — the days with `enabled=FALSE`. Already a hard no-session constraint for plan-gen; the soft "I'd rather rest Sunday than Saturday" preference among *available* days is no longer captured (it was unused by any plan-gen rule).

### G.3 Window semantics

- `window_start` is an *earliest start*, not a fixed start time. Plan-gen can schedule the session to start any time between `window_start` and `window_start + (window_duration - session_duration)`. Sessions cannot extend past `window_start + window_duration`.
- The second window is only consulted on days the athlete picked Doubles Feasible ≠ No. For "Regularly" it's used freely; for "Occasionally" it's used at plan-gen's discretion within a per-week double-day cap (default: 2 doubles per week; final tuning is Layer 4 plan-gen's call).
- The weekly long session occupies the longest enabled primary window directly — there is no separate long-session capacity that overrides the window (the pre-Slice-C "Saturday treated as 360 min regardless of entered window" rule is gone; the window *is* the long session, so its entered duration is the truth).
- Daily windows do not enforce sport mix — that lives at plan-gen against the discipline plan from Layer 2 + the athlete's phase.

### G.4 Session-to-locale assignment

Each plan-gen-produced session is assigned to a locale at plan-gen time via a deterministic resolver. Athletes can swap to another qualifying locale per-session from the session card (JIT swap).

**Resolver algorithm (`resolve_locale(user_id, session_date, required_equipment) → (locale_id, status)`):**

1. **Required equipment set.** Plan-gen (Layer 4) determines the equipment needed for the session — the union of equipment tags consumed by all prescribed exercises plus any sport-specific gear from §J.3 toggles.
2. **Anchor locale.** Read the athlete's active locale for the session's date through §K: default to the athlete's primary; if a §K overlay (self or joint-training) covers the date and sets `Active Locale`, that wins.
3. **Candidate locale set.** All `locale_profiles` rows for the athlete in the active locale's proximity cluster — the 42.2 km / 26.2 mi neighborhood per §J's proximity model plus the active locale itself.
4. **Qualifying filter.** For each candidate, compute the athlete's effective equipment view per §J.2 (shared gym profile + per-athlete overrides, minus disputed items the athlete hasn't explicitly re-added). A candidate qualifies if its effective view is a superset of the required equipment set.
5. **Preferred-flag check.** If any qualifying candidate has `locale_profiles.preferred=TRUE`, restrict the candidate set to preferred-flagged ones.
6. **Distance ranking.** Sort the remaining set by haversine distance from the anchor locale's `(lat, lng)`. Closest wins.
7. **No-candidate fallback.** If no candidate qualifies, return `(NULL, 'unassigned')`. Plan-gen surfaces the session as needing manual locale picking; the athlete can JIT-swap to a non-qualifying locale (with a "missing equipment" warning) or substitute the session.

**JIT swap UX (session card):**

- Each session card shows the assigned locale and an "Other locales here:" affordance.
- Clicking surfaces all locales in the proximity cluster, grouped by Qualifying / Not-qualifying.
- Athlete picks; the session's `locale_id` updates; `assignment_status` flips to `'athlete_swap'`.
- Plan-gen does not re-resolve on athlete swap — the swap is explicit and persistent for that session.

### G.5 Cross-reference to §K

§G captures the athlete's *typical weekly* availability. §K (Locale Schedule) overlays specific date ranges for travel, blackout periods, alternate locales, and date-bound joint training. Plan generation reads §G first (default schedule), then applies §K overlays for any covered dates.

---

## Section H — Target Events

§H is conditional. The H.1 prefix gate determines whether the athlete is training for a specific event (H.2 fills) or following a time-based plan (H.3 fills). Multiple events supported in H.2.

### H.1 Event mode gate

Unchanged from v4.

### H.2 Event details (when H.1 = Yes)

Multiple event records supported; each contains Event Name, Event Date, Event URL, Target Sport / Format, Constituent Disciplines, Race Distance + Estimated Duration, Race Elevation Gain / Loss, Race Terrain Type, Race Pack Weight + Mandatory Kit, Navigation Requirement, Team Format, Goal Outcome, Previous Attempts, Known Event Complications, Race-Specific Nutrition Restrictions.

**D-66 amendment 2026-05-18 — race_format + race_rules_summary + is_target_event added; "Number of Transition Areas" + "Number of Aid Stations" replaced by structured route-locale graph (§H.4).** Per `Race_Events_D66_Design_v1.md`:

| Field | Type | Required | Drives | Notes |
|---|---|---|---|---|
| Race Format | Closed enum: `single_day` / `expedition_ar` / `stage_race` / `multi_day_ultra` | Yes | Layer 3B periodization mode; Layer 4 race-week brief Pattern B path (RacePlan emitted iff != 'single_day'); validator rule `kit_manifest_inputs_incomplete` D-66 active branch | Replaces the implicit format embedded in v4's "Target Sport / Format" free-text. Default radio in onboarding UI: `single_day`. When != 'single_day': §H.4 route-locale step presented; race-rules-summary + mandatory-gear-text encouraged. |
| Race Rules Summary | TEXT (multi-line free-text, up to 8000 chars) | No (optional; encouraged when race_format != 'single_day') | Layer 4 race-week brief contingencies + DQ-avoidance reasoning; reconciled via race-week-brief prompt body D9 hybrid | Athlete pastes / summarizes the race-director-published rules guide (mandatory checkpoints, time cuts, support rules, gear inspections). LLM consumes verbatim. **Disclosure required:** §A.1 race-rules-paste-acknowledgment (athlete confirms text is from official guide; AIDSTATION accepts no responsibility for AI-misinterpretation of pasted text). |
| Is Target Event | Boolean | Yes (exactly one of the athlete's events has TRUE at a time; enforced via DB partial UNIQUE index `race_events_user_target_uidx`) | Layer 3B reads the target row for `mode='event'` periodization decisions | Profile UI "set as target" affordance flips the flag. Switching target fires Layer 3B + Layer 4 invalidation per `Race_Events_D66_Design_v1.md` §9. |

**Goal-context amendment 2026-05-26 — closes the Layer 3B §H.2 deployed-shape gap.** 3B's event-mode goal block + HITL triggers were designed to read the athlete's goal fields, but the deployed `race_events` row never stored them — the cached wrapper hardcoded `goal_outcome='Finish'`, so every athlete was treated as a finisher regardless of ambition (skewing goal-viability optimistic + starving two HITL flags). These goal columns are now captured on the race-event form (onboarding + profile edit) and threaded into Layer 3B by the orchestrator. Shipped in two slices: **Slice 1** (scalars — `goal_outcome` / `first_time_at_distance` / `time_goal` / `race_pack_weight_kg`); **Slice 2** (structured `previous_attempts`, 2026-05-26) — unblocks the last starved HITL flag, `3B.dnf_recurrence_risk`. The full §H.2 goal set is now captured.

| Field | Type | Required | Drives | Notes |
|---|---|---|---|---|
| Goal Outcome | Closed enum: `Finish` / `Compete mid-pack` / `Podium` | No (NULL → cached Layer 3B wrapper falls back to the conservative `Finish` tier) | Layer 3B goal-viability + periodization-shape selection (competitive goals warrant more Build/Peak); the `3B.first_time_competitive_goal` HITL flag | Column `race_events.goal_outcome`. CHECK mirrors `layer3b.builder._VALID_GOAL_OUTCOMES`. A change re-runs Layer 3B (cache-key flip) → periodization-grade Layer 4 eviction. |
| First Time At Distance | Boolean (tri-state: Yes / No / not-answered) | No | The `3B.first_time_competitive_goal` HITL flag (fires when True AND goal_outcome ∈ {Compete mid-pack, Podium}) | Column `race_events.first_time_at_distance` (NULL = not answered). |
| Time Goal | TEXT (free-text, ≤ 200 chars, e.g. "sub-24h") | No | Layer 3B goal-context prompt block | Column `race_events.time_goal`. |
| Race Pack Weight | NUMERIC kg (≥ 0) | No | Layer 3B load-carriage goal context | Column `race_events.race_pack_weight_kg`. A **numeric** field distinct from the free-text mandatory-kit text below; supersedes the prior "pack weight folds into mandatory_gear_text" storage note for the magnitude. |
| Previous Attempts | JSONB list of `{outcome, dnf_cause}` records (Slice 2, 2026-05-26). `outcome` ∈ `Finished` / `DNF` / `DNS`; `dnf_cause` ∈ `quad_failure` / `nutrition_blowup` / `injury_during_event` / `weather` / `timeout` / `other` (DNF rows only). | No | The `3B.dnf_recurrence_risk` HITL flag — fires when a DNF entry's recovery window (`dnf_cause` → weeks, per `layer3b.builder._DNF_RECOVERY_WINDOW_WEEKS`: quad_failure→12, injury_during_event→16, nutrition_blowup/weather/timeout→4, other/unknown→8) exceeds `time_to_event_weeks` | Column `race_events.previous_attempts` (free-form JSONB, no DB CHECK — same storage shape as `race_terrain`; the route parser + the `PreviousAttempt` payload model are the gates). A repeating sub-form on both race-event surfaces. A change is periodization-grade Layer 4 eviction. |

**Sport Sub-Format amendment 2026-06-29 (#254 / D-17, design `designs/Onboarding_SportSubFormat_D17_254_Design_v1.md` §7.4) — closes the Sheet 3 / Sheet 5 naming mismatch.** Five sports (Triathlon, Skimo, Long Distance / Endurance Cycling, Canoe / Kayak Marathon, Open Water Marathon Swimming) name themselves **top-level** in `sport_discipline_bridge` (the "Race event type" / `framework_sport` select) but **sub-format** in `phase_load_allocation`, so a bare-parent pick joined **zero** phase-load bands → a silent no-volume plan. The race-event form now captures **which** sub-format, defaulting to a Layer-0-curated variant the athlete may override. **Two-column model (D1′):** `framework_sport` keeps storing the top-level parent (unchanged — §H.4 disciplines + the SDM strip read it); a new `sport_sub_format` column stores the chosen full PLA `sport_name`, which the Layer 4 orchestrator composes for the Layer 2A phase-load joins (`sport_sub_format or <parent default> or framework_sport`). Shipped in two slices: **B1** (headless backend compose + the Layer-0 default — closes the live bug, 2026-06-29) and **B2** (the capture UI + override, 2026-06-29).

| Field | Type | Required | Drives | Notes |
|---|---|---|---|---|
| Sport Sub-Format | Closed enum per parent sport, sourced from `layer0.sport_sub_format_map` (one row per PLA variant; exactly one `is_default` per parent). Shown only for the five sub-format parents; NULL for every other sport. | No (NULL → the orchestrator resolves the parent's `is_default` at compose time) | The Layer 2A phase-load joins — `framework_sport` composed with this picks the real PLA `sport_name` so phase-load bands are non-empty. **Distinct from Race Format** (the `single_day` / `expedition_ar` / … periodization enum): this is the sport's competitive distance/variant, not the event's day-structure. | Column `race_events.sport_sub_format` (TEXT, NULL; public `_PG_MIGRATIONS`, auto-applies). Default + option list read live from `layer0.sport_sub_format_map`; pre-selected to `is_default`, repopulated client-side on a parent change. A change shifts the composed Layer 2A input (same cache axis as `framework_sport`) → Layer 2A-wide Layer 4 eviction (D6). |

Storage: rows write to new `race_events` table (per D-66 §3.1) instead of the legacy `athlete.target_event_name` + `athlete.target_event_date` columns; legacy columns deprecated + migrated per D-66 §10. The Mandatory Kit list stays free-text in `race_events.mandatory_gear_text` (per D-66 Decision 3); the **pack-weight magnitude** is now the numeric `race_events.race_pack_weight_kg` column (goal-context amendment 2026-05-26) rather than embedded in the free-text.

### H.3 No-event mode (when H.1 = No)

Unchanged from v4. Plan Duration enum (8 / 12 / 16 / 20 / 24 weeks) + Non-Event Goal Type enum (Endurance / General fitness / Strength / Mixed, default = General fitness).

### H.4 Route locales (when H.2 Race Format != 'single_day')

**Added 2026-05-18 (D-66 amendment).** Replaces the v4 free-text "Number of Transition Areas" + "Number of Aid Stations" counts with a structured route-locale graph captured during onboarding (or deferred to profile per the skip affordance below).

Step presented after §H.2 completes and only when the athlete picked a multi-day race_format. Athletes book races 6+ months out; route details may not be published yet. The step is **skippable** ("I'll fill this in later") — race_events row is still created in §H.2; 0 race_route_locales rows are written until athlete completes §H.4 (either at onboarding time or via the profile UI per `Race_Events_D66_Design_v1.md` §7).

| Field (per route locale) | Type | Required | Drives | Notes |
|---|---|---|---|---|
| Role | Closed enum: `start` / `transition_area` / `aid_station` / `drop_bag_point` / `bivvy` / `finish` / `other` | Yes | Layer 4 `RacePlan.segments` adjacent-pair derivation; race-week brief contingency reasoning per anchor table | Closed 7-element enum per `Race_Events_D66_Design_v1.md` Decision 8. `other` is the relief valve for race-format-specific edges (e.g., crew checkpoints in stage races). |
| Name | Text (up to 160 chars) | Yes | Synthesizer prompt verbatim rendering | Athlete-friendly name ("Aid Station 3", "TA1 — Lake Mary Trailhead", "Drop bag at swim entry"). |
| Sequence Index | Integer (1-indexed; UNIQUE per race; gaps allowed) | Yes (auto-assigned by UI on save) | Synthesizer iteration order; RacePlan.segments derivation | UI provides drag-handle reorder. Gaps allowed (1, 2, 5, 8 is valid) so athletes can insert forgotten locales without cascading rewrites. |
| Mile Marker | Numeric (≥0; kilometers or miles per athlete preference) | No | Pacing strategy summary; segment ordering when distance_km on race_events is also known | NULL when athlete doesn't know yet OR race director hasn't published. |
| Mapbox Anchor | Lat + Lng + mapbox_id (optional triple) | No | Forward-pointer for v2 GPX export / map rendering | Same Mapbox-anchored flow as §J locale_profiles per PR18; v1 doesn't consume coordinates in Layer 4 synthesis. |
| Notes | Text (up to 800 chars) | No | Synthesizer prompt verbatim rendering | Free-text per-locale notes (terrain, crew-access rules, mandatory-gear-check-here flag, water-availability). |

**Per-route-locale equipment** (nested 0..N entries per route locale):

| Field (per equipment item) | Type | Required | Notes |
|---|---|---|---|
| Equipment Name | Text (1–160 chars) | Yes | Free-text per D-66 Decision 5; race-route equipment is ephemeral + doesn't reconcile against layer0 `exercise_inventory` (gym-oriented). Examples: "6L water cache", "spare batteries — 4× AAA", "dry socks + base layer", "first-aid kit". |
| Quantity Text | Text (up to 80 chars) | No | Free-text not numeric since units vary. Examples: "6 liters", "2 pair", "1 charged". |
| Notes | Text (up to 400 chars) | No | Free-text caveats. Examples: "for the 4pm leg only", "shared with team", "pre-position by crew Friday". |

**Skip semantics.** Athlete may either fill in 2+ route locales (start + finish minimum recommended) or skip with a "fill in later" affordance. Skipping writes 0 race_route_locales rows; profile UI handles later additions. Validator rule `kit_manifest_inputs_incomplete` (per `Layer4_Spec.md` §4.5 + §5.4) emits `data_gap` observation when route_locale count < 2 OR all route_locale equipment lists empty on race-week-brief invocation. Account-nudge fires 14 days post-skip: "You picked a multi-day race. Add your race route locales when you have them to enable race-week brief generation."

**Storage:** rows write to new `race_route_locales` table per D-66 §3.2 + per-equipment rows write to `race_route_locale_equipment` per D-66 §3.3. CASCADE delete on race_events removal.

**Profile UI:** Full CRUD on race_events + route_locales + equipment via new `/profile?tab=race-events` tab per `Race_Events_D66_Design_v1.md` §7.

---

## Section I — Lifestyle & Recovery

### I.1 Core lifestyle fields

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Average Nightly Sleep | Number (hours, 0.5 increments) + subjective quality (Poor / Fair / Good / Excellent) | 1 | Sleep deficit modelling; recovery day placement; consecutive hard-day limits | Provider-prefill per A.2 mechanics (where Whoop / Polar / Garmin wellness sync available) |
| Sleep Consistency | Enum (Consistent / Mostly consistent / Variable / Highly variable) | 3 | Recovery-day placement refinement (night-to-night variability beyond mean hours) | Self-report — #257 V3-I-1 |
| Work / Life Stress Level | Enum (Low / Moderate / High / Variable) | 1 | Weekly volume ceiling; rest day frequency; hard session placement | Self-report |
| Dietary Pattern | Multi-select (incl. `keto`, `paleo`, and the distinct macro axis `low_carb` / `fat_adapted` — #257 V3-I-2) | 2 | Nutrition recommendations | Self-report |
| Daily Hydration Baseline | Enum (Low / Moderate / High) | 3 | Hydration-habit refinement | Self-report — #257 V3-I-9 |
| Current Supplement Protocol | Free text | 2 | Cross-reference at plan generation | Self-report |
| Caffeine Tolerance & Strategy | Enum + daily mg estimate (optional) | 2 | Training-day caffeine windows; gates race-day sub-question | Self-report |
| Altitude Acclimatization History | Y/N + altitude range (m) + approximate exposure count | 3 | Pacing adjustments for altitude events | Self-report |

#### I.1.1 Race-day Caffeine Strategy

Unchanged from v4. Sub-question on Caffeine Tolerance & Strategy. Collected when Caffeine Tolerance ≠ None.

### I.2 Race-day fueling preferences

Fueling Format Preference and Known Race-day GI Triggers are unchanged from v4. **Salt / Electrolyte Tolerance is split into two independent enums as of v7 (#257 V3-I-4), resolving the Section_I_Audit Fix-now #4 conflation:**

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Salt / Electrolyte Loss | Enum (Low / Moderate / High) | 2 | Layer 2E race-day **sodium** band (concentration → Na replacement need) | Self-report |
| Sweat Rate | Enum (Low / Moderate / High) | 2 | Layer 2E race-day **fluid** band (volume → fluid replacement need) | Self-report — #257 V3-I-4 |

The v2 single "Salt / Electrolyte Tolerance" enum drove both bands; sweat *rate* (volume) and salt *loss* (concentration) vary independently, so they are now captured and consumed separately. The underlying `athlete_profile.salt_electrolyte_tolerance` column is retained (now sodium-only); `sweat_rate_level` is the new column.

### I.3 Sleep deprivation experience

Unchanged from v4. Conditional on §H Target Event Estimated Duration > 20 hr.

---

## Section J — Locales

A Locale is a geographic base from which the athlete trains. Most athletes have one primary locale (home) and may add travel locales. Coordinates, chain identity (where applicable), category, and an athlete's effective equipment view (per a shared gym profile + per-athlete overrides) are stored per locale.

**Proximity model (unchanged from v4):**

Each Locale has coordinates derived from a Mapbox place lookup at creation (or NULL for manual-address fallback). The system computes a proximity cluster using a default radius of **26.2 mi / 42.2 km** — locales within this radius of the active locale are treated as co-accessible (their effective equipment views union into the active set). The athlete can manually override: explicitly link two locales the system didn't catch, or unlink two it linked incorrectly. Manual overrides persist across proximity recalculations.

**Locale-creation flow (new in v5):**

1. Athlete clicks "Add locale" from §J management screen.
2. Athlete types a search string into the place-lookup search box (autocomplete via Mapbox Geocoding API — see §J.1.1). First-time use displays the Mapbox geocoding consent disclosure inline (§A.1); athlete acknowledges or picks the manual fallback path.
3. Athlete selects a Mapbox feature OR uses the "Enter address manually" affordance to bypass Mapbox.
4. System runs chain detection (§J.1.2) and category classification (§J.1.3) on the selected feature.
5. If the resolved category expects a shared gym profile (§J.1.3) and a `gym_profiles` row exists for the `mapbox_id`: system surfaces the existing profile for inheritance (§J.2.4). If no row exists: system offers to build one.
6. Athlete completes per-locale fields (Locale Name display label, primary-locale flag, sharing-opt-out per locale, equipment + toggle entry or inheritance per §J.2 / §J.3, terrain access per §J.4).
7. After save, system runs nearby-chain-instance discovery (§J.1.4) and surfaces opt-in checkboxes for other locations of the same chain within the proximity cluster.

**Equipment availability is NEVER inferred from chain or category.** Chain identity is a discovery aid (surfacing nearby same-chain locations) and a display tag; it does not imply equipment. Category is informational (filtering, display) and gates whether a shared profile is expected; it does not imply equipment. Equipment lives on shared gym profiles (per physical address) per §J.2.

### J.1 Locale-level fields

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Locale Name | Text (e.g., "Home — Austin", "Nashville hotel") | 1 | Display label only | Self-report |
| Mapbox feature | Stable Mapbox identifier + place name + coordinates | 1 | Proximity cluster; chain detection; gym-profile join key; weather-API lookup | Mapbox Geocoding API at locale creation |
| Chain ID | TEXT, FK-style reference to `chain_registry.py` entry; NULL for non-chain or independent | 2 | Discovery aid (nearby same-chain locations); membership status display in Account Config 2 | D-59 chain detection algorithm |
| Category | Enum (10 values; see §J.1.3) | 1 | Filtering / display; gates whether a shared gym profile is expected | D-59 + athlete picker |
| Manual entry flag | Boolean (TRUE when athlete bypassed Mapbox) | 1 | Gates plan-gen behavior — no proximity cluster membership; no shared profile expected; equipment fully manual | System-set |
| Is Primary Locale | Boolean | 1 | Designates the home base; first locale defaults to primary | System-set (athlete can override) |
| Is Preferred | Boolean (default FALSE) | 2 | Plan-gen prefers this locale over other qualifying locales in the proximity cluster (per §G.4 resolver). Multiple preferred-flagged locales allowed | Self-report |
| Sharing opt-out (per locale) | Boolean (default FALSE) | 3 | Per-locale override of the account-level gym-profile-sharing setting | Self-report |

**Dropped from v4:** Gym Chain Memberships moves from a per-locale field to Account Config 2's membership-tracker entity (still per-athlete; no longer duplicated at locale level). Locale-level chain identity is now stored as `chain_id` derived from D-59 detection, not as athlete-entered membership.

#### J.1.1 Mapbox Geocoding integration

Two endpoints:

| Use case | Endpoint | Parameters |
|---|---|---|
| Address autocomplete (athlete typing into locale-creation form) | `GET /geocoding/v5/mapbox.places/{search_text}.json` | `autocomplete=true`, `types=poi,address`, `limit=5` |
| Nearby chain-instance discovery (after a locale is anchored) | `GET /geocoding/v5/mapbox.places/{chain_canonical_name}.json` | `proximity={lng},{lat}`, `bbox={derived from 42.2km radius}`, `types=poi`, `limit=10` |

Reverse geocoding (coords → address) is not used.

**Authentication:** `MAPBOX_TOKEN` env var (public-scope token).

**Failure modes:**

| Failure | Behavior |
|---|---|
| `MAPBOX_TOKEN` unset | Place lookup UI hidden; manual-entry path is the only option. App boots normally |
| Mapbox API 4xx (bad request, auth) | Show inline "Place lookup unavailable — enter address manually." Log to app error stream |
| Mapbox API 5xx | Same as 4xx. Retry once with 1s backoff before falling back |
| Mapbox API rate-limit (HTTP 429) | Same as 5xx. v1 is single-athlete; ceiling is 100K/month free tier (orders of magnitude headroom) |
| Mapbox returns 0 results | Show inline "No matches — enter address manually or try a different search" |

**Refresh:** on-demand only. Each locale row gets a "⟳ Refresh place data" affordance. If the lookup returns a feature whose name has changed, the system prompts the athlete to accept the update; otherwise stored data is kept. If `mapbox_id` returns 404 (location no longer in Mapbox), the locale is flagged stale.

No background refresh. No cron. No login-time refresh.

#### J.1.2 Chain detection

A `chain_registry.py` Python module (curated, ~30–50 entries) drives detection:

```python
GYM_CHAINS: tuple[dict, ...] = (
    {
        'chain_id': 'planet_fitness',
        'canonical_name': 'Planet Fitness',
        'name_patterns': ('planet fitness', 'planet fit', 'pf #'),
        'category': 'commercial_chain_gym',
    },
    # … ~30 entries …
)
```

**Detection algorithm:**

1. Lowercase the Mapbox `text` field.
2. Walk `GYM_CHAINS`. First entry whose any `name_patterns` substring is in the lowercased `text` wins.
3. If no registry match: inspect Mapbox `properties.category`. If it includes `gym`, `fitness`, or `climbing`, mark the locale as `chain_id=NULL, category='independent_gym'` (or appropriate climbing variant). Otherwise mark `chain_id=NULL, category=NULL` and prompt the athlete to pick a category.

**Override path:** athlete can manually set `chain_id` from a dropdown of all registry entries plus "None — independent" plus "None — not a gym."

Initial registry coverage targets ~30 entries (large US fitness chains + climbing-gym chains relevant to Andy's training); full list is a follow-on PR, not blocking v5 spec landing.

#### J.1.3 Category taxonomy

10 canonical categories:

| `category` value | Display label | Has shared gym profile? | Notes |
|---|---|---|---|
| `commercial_chain_gym` | Commercial gym (chain) | Yes | Set by chain detection |
| `independent_gym` | Commercial gym (independent) | Yes | Set when chain not detected and Mapbox category matches gym/fitness |
| `hotel_gym` | Hotel gym | Yes | Athlete-picked. Often basic equipment |
| `climbing_gym_chain` | Climbing gym (chain) | Yes | Chain detection covers Movement, Sender One, Touchstone, Brooklyn Boulders, etc. |
| `climbing_gym_indie` | Climbing gym (independent) | Yes | The unbranded local climbing gym |
| `pool_indoor` | Indoor pool | Yes | Lap pools, YMCAs, athletic clubs |
| `pool_outdoor` | Outdoor pool | Yes | Public pools, neighborhood pools |
| `home_gym` | Home gym | No | Per-athlete; no shared profile |
| `outdoor_park` | Outdoor / trail / park | No | Equipment-irrelevant; locale's value is its terrain (terrain access lives on `locale_profiles` per §J.4) |
| `other_residence` | Other residence | No | In-laws, friend's house, AirBnB. Per-athlete; equipment list is per-athlete or empty |

**Category is mutable.** Athlete can change a locale's category any time. Changing from a "has shared profile" category to a "no shared profile" category orphans the `gym_profile_id` FK; changing the other way prompts the athlete to either link to an existing profile or start a new one.

#### J.1.4 Nearby chain-instance discovery

After a locale is anchored to a chain, the system runs one Mapbox Geocoding search:

1. Compute a bounding box around the anchor coords with the 42.2 km radius.
2. Mapbox query: `{chain_canonical_name}` with `proximity={anchor lng/lat}`, `bbox=…`, `types=poi`, `limit=10`.
3. Filter results by re-running the chain-detection algorithm — only Mapbox features whose chain_id matches the anchor's chain_id are surfaced.
4. Exclude the anchor itself (compare by Mapbox `id`).
5. Surface the remaining N instances in the locale-creation UI with per-instance opt-in checkboxes.

When the athlete opts in to a nearby instance, a new `locale_profiles` row is created with `chain_id = anchor.chain_id`; the athlete proceeds through the inherit/create flow for that instance's `gym_profile_id`.

#### J.1.5 Manual address fallback

Always available; first-class path. Athlete clicks "Enter address manually" instead of using place lookup at any point. `locale_profiles` row is inserted with `mapbox_id=NULL`, `lat=NULL`, `lng=NULL`, `chain_id=NULL`, `manual_entry=TRUE`, `category=<athlete's pick>`.

Plan-gen reads `manual_entry=TRUE` rows as "no proximity-cluster membership" (since no coords) and "no shared profile expected" (equipment list is fully athlete-entered per `locale_equipment` or per-athlete-only `gym_profile_id` if athlete chose to build a private profile).

Later, athlete can edit the locale and click "Look up on map" — if athlete picks a Mapbox feature, the row updates with coords + Mapbox id + chain detection runs. `manual_entry` flips to FALSE.

### J.2 Equipment Inventory — Shared Gym Profile model

**Replaces v4 §J.2's per-locale equipment checklist.** Equipment now lives on per-physical-address shared `gym_profiles` rows (one per `mapbox_id` — crowd-sourced across all AIDSTATION users) with per-athlete add/remove overrides. Plan-gen reads the athlete's effective equipment view.

**Categories where a shared profile is expected:** `commercial_chain_gym`, `independent_gym`, `hotel_gym`, `climbing_gym_chain`, `climbing_gym_indie`, `pool_indoor`, `pool_outdoor`. **Categories where it is not:** `home_gym`, `outdoor_park`, `other_residence` — equipment is per-athlete (or empty) for these.

The canonical 121-item equipment list from `Vocabulary_Audit_v2.md` §3 + 9 Assumed Universal items remains the authoritative equipment taxonomy. v5 does not change the equipment list itself.

#### J.2.1 First-athlete-creates flow

When athlete A creates a locale that resolves to a `mapbox_id` not yet in `gym_profiles`:

1. System asks A: "We don't have an equipment profile for this gym yet — want to build one? (You can also skip and add equipment later.)"
2. If A builds: A completes a §J.2 equipment checklist (121-item canonical list) + §J.3 toggles. On save, a `gym_profiles` row is created with A's data; A's `locale_profiles` row gets `gym_profile_id = <new row id>`. `created_by_user_id = A`. First-time creators acknowledge the gym-profile sharing consent disclosure (§A.1) inline.
3. If A skips: `locale_profiles.gym_profile_id = NULL` for now. A can later either create the profile or link to one a peer creates.

#### J.2.2 Subsequent-athlete-inherits flow

When athlete B creates a locale at the same `mapbox_id`:

1. System detects the existing `gym_profiles` row.
2. UI shows: "Another athlete built an equipment profile for this gym, last confirmed on YYYY-MM-DD. Want to inherit it?" + preview.
3. If B inherits: `locale_profiles.gym_profile_id = <existing row id>`. B's effective view = the shared profile. No `locale_equipment_overrides` yet.
4. If B declines and builds their own: B creates an override-only profile from the start (or, if sharing is opted-out for B, a private profile).

#### J.2.3 Per-athlete override model

Plan-gen for athlete X at locale L reads equipment as:

```
effective_equipment(X, L) =
  (shared_profile.equipment ∪ X's overrides where action='add')
  ∖ (X's overrides where action='remove')
  ∖ (any equipment with disputed=TRUE on the shared profile, unless X explicitly added it back)
```

Same shape for §J.3 toggles.

Overrides are stored as rows in `locale_equipment_overrides` keyed by `(user_id, locale_id, equipment_tag, action)` where `action ∈ ('add', 'remove')`. §J.3 toggle overrides live in `locale_toggle_overrides` (per-toggle value).

#### J.2.4 Submit-as-correction (override → shared)

When athlete X has been operating with overrides and wants to push them to the shared profile (button: "submit my equipment list as a correction to the shared profile"):

1. System computes the submitted profile = current shared + X's overrides applied.
2. UI confirms: "You're about to update the shared profile for [gym name]. Other athletes' overrides remain in place. Continue?"
3. On confirm: shared profile updates; X's overrides are zeroed out (reflected in shared now); `last_confirmed_by` and `last_confirmed_at` update.
4. Other athletes' next session at this locale: their effective view recomputes from the new shared base.

#### J.2.5 Dispute flow

When athlete X's override conflicts with the shared profile, X can mark the item as "disputed":

1. UI: "I think the shared profile is wrong about [cable machine]. Mark as disputed?"
2. On confirm: `gym_profiles.disputed_items` JSON array gains the equipment tag. X's override remains in place for X.
3. Other athletes at this locale see "[Cable machine] — disputed by 1 athlete. Confirm what you see?"
4. For plan-gen: any item with `disputed=TRUE` is treated as not-available for any athlete who has not explicitly overridden it.

Dispute decay is not specced in v5; backlog item.

#### J.2.6 Crowd-sourcing consent + opt-out

Default: athlete's gym-profile contributions are shared. Account-level toggle: "Contribute my gym-equipment edits to the shared AIDSTATION gym database (default on)." When off:

- New gym profile creations stay private (`gym_profiles.private=TRUE`, `created_by_user_id=X`).
- Athlete's overrides on shared profiles stay athlete-local.
- Other athletes at the same `mapbox_id` see the locale as "no shared profile yet" until a sharing athlete creates one.

Per-locale opt-out is available (`locale_profiles.sharing_opt_out`) for athletes who want to opt out at one specific address (e.g., a home gym they entered at a Mapbox-resolved address).

### J.3 Sport-Specific Gear Readiness Toggles

10 sport-specific gear readiness toggles per `Vocabulary_Audit_v2.md` §4.1. **Same shared-profile model as §J.2.** Toggles live on `gym_profiles.toggles` (JSON object); per-athlete `locale_toggle_overrides` capture deltas.

| Toggle | Tier | What it gates |
|---|---|---|
| Climbing — roped | 2 | Lead climbing, top-rope, multi-pitch; also satisfies Rappelling / abseiling check |
| Bouldering | 2 | Bouldering-specific exercise selection |
| Rappelling / abseiling | 2 | Rappel / abseil sessions; also satisfied by Climbing — roped |
| Via ferrata | 2 | Via ferrata sessions |
| Mountaineering | 2 | Alpine / glacier sessions; hard gate without avalanche safety endorsement on col-type terrain |
| Whitewater paddling setup | 2 | Whitewater kayak / packraft sessions above Class II |
| Touring / AT ski setup | 2 | Ski mountaineering, randonnée sessions |
| Classic XC ski setup | 2 | Classic cross-country ski sessions |
| Skate XC ski setup | 2 | Skate cross-country ski sessions |
| Snowshoeing setup | 2 | Snowshoe-specific conditioning sessions |

**Roped climbing passes rappelling check:** an athlete with Climbing — roped enabled is assumed to have gear sufficient for rappelling. The reverse is not true.

**The system does not infer toggles from category.** A `climbing_gym_chain` category locale does not auto-set Climbing — roped = TRUE. First climber at the address sets it; subsequent climbers inherit + can override per-athlete.

### J.4 Terrain Access

Unchanged from v4. Terrain types multi-select + per-month seasonality (climate-derived defaults + athlete override).

### J.5 ~~Locale Capacity Metrics~~

**Deleted in v5 per `Onboarding_D61_Design_v1.md`.** "Typical session time available" and "Max session duration" fields are removed. Whether a session fits at a locale is now determined by:

- The athlete's per-day `daily_availability_windows` (per §G.1) — sets the time envelope per day-of-week, not per-locale.
- The locale's effective equipment view (per §J.2) and §J.3 toggles — determines whether the session's prescribed exercises can be performed at the locale.
- Layer 4 plan-gen's safety / supervision rules — handled at plan-gen, not stored as locale fields.

Athletes who relied on the v4 §J.5 fields to express "I can't train more than 60 min at this gym before it gets too crowded" can instead capture the same intent via §G `daily_availability_windows` (shorter window on the day they train at that gym) or via §K overlays (date-specific Constraint = "Short sessions only").

---

## Section K — Locale Schedule

Unchanged from v4. Three sub-types:

- **K.1 Self-overlays** — travel, blackout, locale switch, constraints
- **K.2 Joint-training overlays** — same structure as K.1 plus joint-training-specific fields
- **K.3 Recurrence templates** — generates K.1 or K.2 instances on a rolling forward window

Field inventory carries forward verbatim from v4 §K.1 / §K.2 / §K.3. Plan-gen reads §K overlays as the per-date locale anchor input to §G.4's session-to-locale resolver.

---

## Section L — Athlete Network

Unchanged from v4. Athlete Link entity (Partner Name, Linked Account FK, Relationship Types multi-select, Partner-specific Rules) + Race Teammate conditional fields (Race Event Association FK, Discipline Focus on Team).

---

# Group 2 — Account Configuration

Account-level entities. Not plan-gen inputs directly — they determine what data the system can pull, what the athlete has consented to, and which gym memberships are tracked.

## Account Config 1 — Connected Services

**Reframed in v5 per `Onboarding_D58_Design_v1.md`.** Account Config 1 is now a *management* screen: status display, disconnect, re-auth, scope update. The primary connect path happens at the D-58 onboarding connect step (Step 2). Athletes can also initiate new connects from this screen post-onboarding; the new connect runs the same OAuth flow and triggers the §A.2.5 re-onboarding prompt.

One record per integrated third-party service.

| Field | Type | Notes |
|---|---|---|
| Service Name | Enum (COROS / RWGPS / Polar / Wahoo / Strava / Whoop / TrainingPeaks / Zwift / Garmin-when-restored — extendable) | Aligned with Integration v4 §3. Apple Health and Samsung Health out of scope (no native iOS / Android clients) |
| Connection Status | Enum (Connected / Disconnected / Auth Error / Sync Paused) | System-set |
| Last Sync | Timestamp | System-set |
| Scopes Granted | Multi-select (Activity data / Wellness / Sleep / HR / Power / GPS track) | System-set from OAuth flow |
| Sync Direction | Enum (Pull only / Push only / Bidirectional) | System-set per service integration |

**v5 changes from v4:**

- Removed "At launch: Connected Services are manual-upload equivalents (FIT file upload). OAuth integration is the post-launch upgrade path." OAuth integration ships in v5 per the D-50 wiring track (unblocked by D-58); FIT-upload becomes a per-provider fallback path, not the primary mode.
- Effect side still lives in Plan Management 2 §M.2 (account-config-event athlete-data effects).

## Account Config 2 — Gym Memberships

| Field | Type | Notes |
|---|---|---|
| Gym Chain | Text or FK to `chain_registry.py` entry | Athlete adds the chains they have active memberships at |
| Membership Active | Boolean | Inactive memberships retained for history but not surfaced in locale setup |

**v5 role clarification:** Account Config 2 tracks athlete-claimed memberships at gym chains. It is **separate from** §J.1 chain detection (which determines a locale's `chain_id` automatically from Mapbox). The two interact in one place: when athlete creates a new travel locale and §J.1 detects a chain the athlete is a member of (per Account Config 2), the UI surfaces this in the nearby-chain-instance discovery step ("You're a member of LA Fitness; here are 3 LA Fitness locations within 42 km").

**v5 removed:** the v4 "gym-equipment profile surfacing" function of Account Config 2. Equipment now lives on per-physical-address shared `gym_profiles` (D-60), not per-chain manifests. Membership tracking remains useful for chain-discovery surfacing.

## Account Config 3 — Disclosure Acknowledgment Records

Storage backing for §A.1 disclosures. One record per disclosure type per acknowledgment event.

| Field | Type | Notes |
|---|---|---|
| Disclosure Type | FK to disclosure category (from §A.1) | E.g., `account_creation_ack`, `connected_service_consent`, `oauth_scope_<provider>`, `sex_collection_inline`, `health_data_inline`, `hrt_inline`, `mapbox_geocoding_consent`, `gym_profile_sharing_consent`, `linked_partner_data_sharing` |
| Acknowledged At | Timestamp | System-set on athlete confirmation |
| Version Seen | Text (disclosure version string) | Enables re-prompt when disclosure copy changes |
| Delivery Method | Enum (In-app / Email) | Audit trail |

**New disclosure types in v5:**

- `oauth_scope_polar` / `oauth_scope_coros` / `oauth_scope_wahoo` / `oauth_scope_strava` / `oauth_scope_whoop` / `oauth_scope_rwgps` / `oauth_scope_trainingpeaks` / `oauth_scope_zwift` / `oauth_scope_garmin` (when restored) — one row per provider per OAuth flow, carrying `version_id` matching the scope set requested. Re-acknowledgment required when scope set changes.
- `mapbox_geocoding_consent` — one row per athlete (single acknowledgment).
- `gym_profile_sharing_consent` — one row per athlete (single acknowledgment, fires at first shared profile interaction).

**Pre-launch blocker (carried from v4):** disclosure copy is PLACEHOLDER for several entries — refine with product/legal before ship (Open Item #1).

## Account Config 4 — Privacy and Linked-Partner Sharing

Unchanged from v4. One record per Athlete Link (§L) where Linked Account is set. Consent Scope (None / Activity summaries / Full plan access), Consent Granted / Revoked timestamps.

---

# Group 3 — Plan Management

Lifecycle events and runtime logic. Not athlete-facing data points — these are how the system responds to data changes, plan signals, and account events.

## Plan Management 1 — Plan Duration and Event Prefix Logic

Unchanged from v4. When §H.1 = Yes, plan duration is derived from today → event date subject to minimum base phase per discipline. When §H.1 = No, athlete selects Plan Duration enum (8 / 12 / 16 / 20 / 24 weeks).

## Plan Management 2 — Profile Update Triggers (§M)

### M.1 Athlete data lifecycle triggers

Same triggers as v4 §M.1, with these v5 additions / clarifications:

| New / clarified trigger | What updates |
|---|---|
| **Athlete connects a new provider (post-onboarding)** | Trigger the §A.2.5 re-onboarding prompt for that provider's prefill-eligible fields |
| **Provider sync delivers a value beyond field-specific tolerance for a same-provider-sourced field** | Surface passive notification per §A.2.7 |
| **Provider sync delivers a value where the winning provider changes** | Surface passive notification per §A.2.2 |
| **Athlete updates `daily_availability_windows` for a day** | Re-validate any in-flight plan sessions for that day; flag sessions that no longer fit. Also re-derives the weekly long session (longest enabled window) + rest days (disabled days) per §G.2 |
| **Athlete creates a shared gym profile, inherits one, or submits a correction** | Re-evaluate exercise pool for that locale; flag any in-flight plan sessions affected |
| **Athlete adds or removes a per-locale equipment override** | Same — re-evaluate exercise pool for that locale |
| **Athlete marks a `locale_profiles.preferred=TRUE`** | Future session-to-locale assignments prefer this locale per §G.4 step 5 |
| **`account_nudges.dismissed_at` set on `nudge_type='connect_provider_14d'`** | One-time event; no further nudges |

### M.2 Account Config events that affect athlete data

| Account Config event | Athlete data effect |
|---|---|
| Provider connects (OAuth flow completes successfully) | Pull activity / wellness data; run §A.2.5 prefill prompt; record per-provider scope acknowledgment in Account Config 3 |
| Provider disconnects | Stop auto-fill; flag any `source = 'provider_<X>'` fields as stale at next plan generation; revert to manual-entry expectations for those fields |
| Provider scope reduced | Re-check which fields can still auto-fill; prompt athlete for any newly-uncovered fields |
| Provider auth fails / sync stops | Stale-data warning at plan generation; prompt athlete to reconnect |
| Gym membership added (Account Config 2) | Surface gym-chain-instance suggestions in nearby-chain discovery at any §J locale-creation in that chain |
| Gym membership removed | Re-evaluate whether chain-dependent display tags remain valid at affected locales |
| Athlete enables / disables account-level gym-profile sharing | New gym-profile creations honor the new setting; existing private profiles remain private; existing shared profiles remain shared (no retroactive flip) |

### M.3 Adherence-drop detection threshold

Unchanged from v4. 4 consecutive flagged sessions triggers the adherence-drop prompt.

### M.4 Soft Warning / Hard Gate / Profile Prompt classification

Unchanged from v4. Hard gate / Soft warning / Profile prompt categories with the same example mappings.

## Plan Management 3 — Joint Training Generation

Unchanged from v4. Rolling 8-week forward window for K.3 Recurring templates; either party can override individual instances; locale-mismatch reconciliation prompt.

## Plan Management 4 — System-Tracked Heat Acclimatization

Unchanged from v4. Inferred from workout date + active locale coordinates + weather API.

## Plan Management 5 — Multi-Athlete Plan Sync

**Out of scope for first v5 publish (unchanged from v4).** Data model in place; generation logic deferred to team-training spec session.

---

# Open Items

Genuinely deferred or in-progress.

| # | Item | Source | Status |
|---|---|---|---|
| 1 | Disclosure copy refinement (§A.1) — placeholder copy drafted for new v5 disclosures (Mapbox geocoding consent, gym-profile sharing consent, per-provider OAuth scopes); legal review pending across all §A.1 disclosures | Onboarding handoff #5; v5 additions per D-58, D-59, D-60 | Pre-launch blocker; product/legal owns |
| 2 | Movement Components structured field on exercise DB | Cross-layer (Layer 0 enhancement) | Deferred — post-v2 |
| 3 | Sheet 7 deprecation execution — mark superseded once v5 spec is signed off | v1 Open Item | Mechanical action; trigger on v5 signoff |
| 4 | Migration path from current app database — needs current schema dump | Onboarding handoff #10 | Architecture hold; effectively moot — Andy is sole test user, schema is forward-only |
| 5 | Layer 1 ↔ Layer 0 query layer concrete spec | v1 To-Do #6 | Active workstream |
| 6 | Sports Framework Phase Load Allocation gap audit — full pre-launch audit, all 17 unverified sports (AR verified) | `V2_spec_decisions_handoff.md` Deferred #7 | Pre-launch audit; multi-session effort |
| 7 | Plan gen strategy for weeks 13+ — split-model: stronger LLM weeks 1–12, cheaper LLM weeks 13+ | v4 Resolved #9; engineering implementation pending | Pre-launch decision; product/engineering |
| 8 | Recurring §K rolling-window length — direction set (8 weeks); confirm with engineering | Batch 4+5 | Direction set |
| 9 | TA / aid station fallback — conservative default | v4 Resolved #11 | Plan-gen behaviour; integrate during plan-gen spec |
| 10 | Multi-partner consent rules (N>2) — partial-link decided; detailed UX deferred | `V2_spec_decisions_handoff.md` Deferred #17 | Direction set; detailed UX in team-training spec |
| 11 | Stale-link cleanup — never auto-archive; manual user action only | V2_Spec_Prep #25 | Direction set; team-training spec to formalize |
| 12 | **NEW v5:** Mapbox token rate-limit handling at multi-tenant scale (HTTP 429 fallback to per-tenant token bucket) | D-59 §3.4 risks | Not a v1 concern (single athlete); flag for v2 |
| 13 | **NEW v5:** Chain registry curation cadence + initial 30-entry seed values (drafted as a follow-on PR; not blocking spec) | D-59 §2 decision #8 | Pre-launch / launch follow-on |
| 14 | **NEW v5:** Gym-profile dispute resolution maturity — voting / admin moderation / dispute decay | D-60 §7 + risks | Backlog candidate after cohort growth |
| 15 | **NEW v5:** Equipment quantity / quality ratings on shared gym profiles ("Dumbbells 5–50 lb" vs "Dumbbells 5–120 lb"; condition signals) | D-60 risks | Backlog candidate post-launch |
| 16 | **NEW v5:** Per-field tolerance values for §A.2.7 re-prefill cadence (body weight ±0.5 kg, RHR ±2 bpm, etc.) — config table, not spec | D-58 §10 | v5 implementation config |
| 17 | **NEW v5:** Canonical `KNOWN_PROFILE_FIELDS` registry for `athlete_profile_field_provenance.field_name` — application-code constant + validation on insert | D-58 §10 risks | v5 implementation |
| 18 | **NEW v5:** Telemetry on the 14-day connect-provider nudge (display / dismiss / act-on rates) | D-58 §10 risks | v5 implementation |
| 19 | **NEW v5:** JIT-swap UX detail at session card — clear visual differentiation Qualifying vs. Not-qualifying; missing-equipment warning copy | D-61 §5 | v5 implementation |
| 20 | **NEW v5:** Plan-level "alt-windows" carry-over from prior plan — should athlete's last plan's windows seed the next plan's windows by default? | D-61 §9 | Backlog candidate after first multi-plan cohort |
| 21 | **NEW v5:** Provider-disconnect behavior on prefilled fields — value persists with `source` flipped to `'self_report'` + a note, or re-resolves to next-best provider, or cleared | D-58 §10 | v1.1 amendment if needed; recommend "persist with note" default |

---

# What this spec is not

- **Not the full UX flow.** What screens exist and what their layout is, what's collected upfront vs. deferred, what's a wizard vs. a settings page — separate design pass. v5 does commit to the onboarding step sequence (account creation → ack → connect step → §A onwards) per D-58.
- **Not the database schema in implementation detail.** This spec specifies tables, columns, types, and constraints; the migration PR owns the SQL specifics, indexes-not-named-here, and trigger logic. All new tables and columns land on `_PG_MIGRATIONS` only per the `_SQLITE_MIGRATIONS` freeze ratified in `Athlete_Data_Integration_Spec_v4` §2.5.
- **Not the prompt design.** Prompts reference schema fields. Schema comes first.
- **Not the OAuth flow implementation per provider.** Each provider's OAuth callback, token exchange, refresh skeleton, and webhook signature verification is `routes/{provider}.py` work owned by the D-50 wiring PRs (now unblocked by D-58). v5 spec commits to the connect-step UX, the post-callback prefill prompt, and the storage shape; it does not spec the per-provider OAuth handshake.

---

# Drafting status

| Section / Group | Status | Source |
|---|---|---|
| Front matter, v5 changelog, onboarding step sequence | ✅ Drafted (v5 consolidation) | D-58 + D-59 + D-60 + D-61 design docs |
| §A Athlete Identity + A.1 Disclosures + A.2 Provider-sourced prefill mechanics | ✅ Drafted | v4 §A + D-58 |
| §B Health Status (B, B.1, B.1.1, B.1.2, B.2, B.3, B.4, B.4.1, B.4.2) | ✅ Carried from v4 (unchanged) | v4 §B |
| §C Training History & Fitness Baseline | ✅ Carried from v4 (annotated for provider prefill) | v4 §C + D-58 |
| §D Discipline-Specific Baselines | ✅ Carried from v4 (annotated for provider prefill) | v4 §D + D-58 |
| §E Strength, Core & Balance Benchmarks | ✅ Carried from v4 (unchanged) | v4 §E |
| §F Performance Testing | ✅ Carried from v4 (annotated for provider prefill) | v4 §F + D-58 |
| §G Schedule & Availability | ✅ Rewritten | D-61 |
| §H Target Events | ✅ Carried from v4 (unchanged) | v4 §H |
| §I Lifestyle & Recovery | ✅ Carried from v4 (annotated for sleep prefill) | v4 §I + D-58 |
| §J Locales + J.1 / J.1.1–J.1.5 / J.2 / J.2.1–J.2.6 / J.3 / J.4 / ~~J.5~~ | ✅ Rewritten | v4 §J + D-59 + D-60 + D-61 (J.5 deletion) |
| §K Locale Schedule | ✅ Carried from v4 (unchanged) | v4 §K |
| §L Athlete Network | ✅ Carried from v4 (unchanged) | v4 §L |
| Group 2 — Account Configuration (1 reframe; 2 role-clarify; 3 new disclosure_ids; 4 unchanged) | ✅ Drafted | v4 + D-58 + D-59 + D-60 |
| Group 3 — Plan Management (M.1 + M.2 expanded; rest carried from v4) | ✅ Drafted | v4 + D-58 + D-61 |
| Open Items | ✅ Updated (carry-forward + 10 new v5 items) | This spec |

---

*End of Athlete_Onboarding_Data_Spec_v5.md. Implementation PR is the next track — see `Project_Backlog_v15.md` D-58 / D-59 / D-60 / D-61 rows (now in "design landed; implementation pending" state) and the D-50 wiring track (unblocked by D-58).*
