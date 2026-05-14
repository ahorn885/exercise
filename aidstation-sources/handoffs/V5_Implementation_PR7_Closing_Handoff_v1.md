# V5 Onboarding Implementation PR7 — Closing Handoff

**Session:** Seventh substantive code session of the v5 onboarding implementation arc. Executes PR6 §5.1's recommended next — **Option D2a (read-side prefill UX)** — unblocked by PR6's D-51 column foundation. Ships the `KNOWN_PROFILE_FIELDS` registry (closing Open Item #17 from D-58), per-provider extractor functions, the `/onboarding/prefill` GET route, and the comparison-page template. Stub `[Use provider]` / `[Keep current]` action buttons render disabled — D2b wires the write path. Flips `_POST_STEP2_CONTINUE_TARGET` so Step-2 Continue lands on the new prefill page instead of jumping straight to the profile form.
**Date:** 2026-05-14
**Predecessor handoff:** `V5_Implementation_PR6_Closing_Handoff_v1.md` (its §5.1 Option D2a is exactly what this session executes; its §5.4 v18→v19 backlog bump runs here per Rule #11 mechanical spec).
**Branch:** `claude/v5-implementation-handoff-XtgyG` (per-session feature branch off `main`; PR6 was merged into `main` as `2c8d01f` via PR #38 before this session started).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 live `/onboarding/prefill` page-load + HRmax-extractor sanity (athlete with COROS-tagged `cardio_log` rows in last 90 days) + Continue-button round-trip owed at deploy time (no Flask in sandbox, same gap as PR1–PR6).
**Time-on-task:** Single chat. Substantive files: **4** (`routes/profile_extractors.py` new, `routes/profile_fields.py` new, `routes/onboarding.py` edit, `templates/onboarding/prefill.html` new). Plus the v18→v19 backlog bump (`Project_Backlog_v19.md` new copy + 1-line `CLAUDE.md` edit) and this handoff = 7 total.

---

## 1. Session-start verification (Rule #9)

Verified the PR6 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/v5-implementation-handoff-XtgyG` clean off `main`; PR6 merged to `main` as `2c8d01f` via PR #38 (commit `e6412f7`) | `git status` + `git log --oneline -15` | ✅ Verified |
| `init_db.py` 5 new columns at all 4 sites (cold-start SQLite L31-35, cold-start PG L350-354, SQLite migrations L1395-1399, PG migrations L1955-1959) + the migration-list `CREATE TABLE IF NOT EXISTS` shells at L1161-1162 + L1601-1602 | grep | ✅ Verified |
| `athlete.py:PROFILE_FIELDS` length = 14; `PREFILL_ELIGIBLE_FIELDS` defined at L42 with 5 expected names | grep | ✅ Verified |
| `routes/profile.py` imports `PREFILL_ELIGIBLE_FIELDS` + `database`; `_record_self_report_provenance` at L112 with PG guard via `database._is_postgres()` at L131; invoked from `edit()` save handler at L216 | grep | ✅ Verified |
| `templates/profile/edit.html` "Performance baselines" section at L87 with 5 number inputs (`body_weight_kg`, `hrmax_bpm`, `lactate_threshold_hr_bpm`, `vo2max`, `cycling_ftp_w`) | grep | ✅ Verified |
| `routes/coros_ingest.py:_ingest_activity` uses `ON CONFLICT (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL` at L130; no remaining SELECT-then-UPDATE-or-INSERT | grep | ✅ Verified |
| `routes/onboarding.py` still has `_POST_STEP2_TARGET = '/profile?tab=athlete'` (PR6 didn't flip it; D2a is the flip) | grep | ✅ Verified |
| `Project_Backlog_v18.md` exists with v17 archived to predecessor block; `CLAUDE.md` "Authoritative current files" backlog line reads v18 | grep | ✅ Verified |

**No drift between PR6 handoff narrative and on-disk state.** All five Rule #9 anchor checks land verbatim.

---

## 2. Files shipped this turn

All on branch `claude/v5-implementation-handoff-XtgyG`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `routes/profile_extractors.py` | New (138 lines) | One function per (prefill-eligible field × connected provider). 10 functions total: `extract_<field>_<provider>(db, user_id)` for each of (body_weight_kg, hrmax_bpm, lactate_threshold_hr_bpm, vo2max, cycling_ftp_w) × (coros, polar). All return a 3-tuple `(value, synced_at, note)` or `(None, None, None)` if no provider data exists. **2 real, 8 stubs:** `extract_hrmax_{coros,polar}` derive from `MAX(cardio_log.max_hr)` over 90 days scoped by `coros_label_id IS NOT NULL` / `polar_exercise_id IS NOT NULL`; the other 8 stub-return `(None, None, None)` because the current ingest doesn't capture body weight (wellness API not wired), lactate threshold (no provider supplies via our ingest), VO2max (COROS Health + Polar Fitness Test estimates not ingested), or cycling FTP (Wahoo paused, no other provider supplies). Window length `_DERIVED_WINDOW_DAYS = 90` is a module-level constant. Helper `_hrmax_from_cardio_log` parameterises the foreign-id column name; `provider_id_col` interpolates into the SQL via f-string but is only ever called from this module's own functions (never from user input) — safe. |
| 2 | `routes/profile_fields.py` | New (~95 lines) | Single export: `KNOWN_PROFILE_FIELDS` tuple of dicts, one entry per field in `PREFILL_ELIGIBLE_FIELDS`. Each entry: `name` (the `athlete_profile` column name), `label` (UI), `unit` (UI), `cast` (`int` or `float` — mirrors `routes/profile.py:edit()` numeric cast), `extractors` (dict keyed by provider slug → callable from `profile_extractors`). Module-level `assert` verifies `KNOWN_PROFILE_FIELDS` names match `PREFILL_ELIGIBLE_FIELDS` so the two never drift silently. Helper `provider_label(slug)` reads from `routes.profile.CONNECTION_PROVIDERS` so we don't introduce a parallel slug→label mapping. **Closes Open Item #17** (D-58 §10) — the canonical registry the prefill UI now consumes. |
| 3 | `routes/onboarding.py` | Edit (+~90 lines) | (a) Header docstring updated to reflect that PR7 ships Step 3a (prefill comparison). (b) New imports: `database`, `get_athlete_profile`, `KNOWN_PROFILE_FIELDS`, `provider_label`. (c) Renamed `_POST_STEP2_TARGET` to two separate constants: `_POST_STEP2_CONTINUE_TARGET = '/onboarding/prefill'` (the flip) and `_POST_STEP2_SKIP_TARGET = '/profile?tab=athlete'` (Skip still jumps past prefill because there's nothing to compare against if no providers were connected — though we keep `_POST_STEP2_TARGET` as an alias for the connect template's render param to avoid breaking that). Added `_POST_STEP3_TARGET = '/profile?tab=athlete'` for the prefill page's Continue button. (d) `skip()` now redirects to `_POST_STEP2_SKIP_TARGET`; `continue_()` redirects to `_POST_STEP2_CONTINUE_TARGET`. (e) New `prefill()` GET handler at `/onboarding/prefill` — loads the athlete's profile, the connected-provider slug set (via `load_connections`), provenance rows (PG-only, mirrors `_record_self_report_provenance`'s guard), then walks `KNOWN_PROFILE_FIELDS` and resolves per-field candidate values from each connected provider's extractor; candidates sorted most-recent-first per v5 §A.2.2 step 3. |
| 4 | `templates/onboarding/prefill.html` | New (~115 lines) | Bootstrap 5 comparison-card layout (2-column responsive grid). Stepper at top: Step 1 ✓ → Step 2 ✓ → **Step 3 (current)**. Three render branches: (a) `connected_count == 0`: info-alert empty state ("You skipped Step 2…"); (b) connected ≥1 but `fields_with_candidates == 0`: muted explainer; (c) candidates present: per-field summary plus card grid. Each card uses a `<dl>` two-column layout — "Currently stored" + provenance badge (renders `'self_report'` → "Self-reported", `'manual_override'` → "Manually set", `'provider_<X>'` → "From X"), then one row per provider candidate with value + `synced_at` + extractor `note`. `[Use provider value]` / `[Keep current]` buttons render with `class="btn ... disabled"` and `aria-disabled="true"` + `title="Write-back ships in the next release."` so the disabled state is honest. Footer: muted small-print framing v5 §A.2's "more fields ship as extractors come online" + a single `Continue to profile` link to `/profile?tab=athlete`. No CSP-nonce-needing JS — the disabled buttons are pure HTML. |
| — | `aidstation-sources/Project_Backlog_v19.md` | New (copy of v18 + 3 surgical edits per PR6 §5.4 mechanical spec) | **File revision** header bumped v18→v19 with PR7 narrative (D-50 status flip includes PR7; the D2 candidate split now reads `Option D2a shipped PR7 (read-only)` + `Option D2b deferred to PR8+`). **Predecessor revisions** block prepends the v18 entry verbatim. **D-50 status cell** rewritten: 🟢 PR1–PR7 shipped; frontend D1 + D2a shipped; D2b + D3 + E + F + H pending. **D-50 Notes column** rewritten with PR8+ candidate menu (D2b → E → D3 sequence; F watch item; H opportunistic) + PR7-specific pre-deploy verification (HRmax extractor against `MAX(cardio_log.max_hr) WHERE coros_label_id IS NOT NULL` 90-day window, empty-state render, Step-2 Continue→prefill flip, Step-2 Skip→profile preserved). |
| — | `aidstation-sources/CLAUDE.md` | Edit (1-line) | Per PR6 §5.4 step 6: "Authoritative current files" backlog line bumped from `Project_Backlog_v18.md` to `Project_Backlog_v19.md`. Single-line edit, same shape as the v17→v18 bump PR6 did. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR7_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `routes/profile.py` — unchanged. The form-side save handler + `_record_self_report_provenance` already handle the manual write path PR6 specced. D2b adds the source-flip refactor (`'provider_*'` → `'manual_override'` on edit); PR7 is read-only so no profile-route change.
- `routes/auth.py` — unchanged. Post-register redirect still `onboarding.connect`.
- `templates/onboarding/connect.html` — unchanged. The Continue/Skip POST forms call `onboarding.continue_` / `onboarding.skip` via `url_for`, which now redirect to the new targets — no template change needed. The stepper text "Step 3 — Profile" is generic enough to cover prefill (which is part of Step 3); the new `templates/onboarding/prefill.html` has its own stepper that names this sub-step "Review your profile data".
- `init_db.py` — unchanged. No new schema. `athlete_profile_field_provenance.field_name` is still free-text TEXT; the comment at line 1820 saying the canonical registry "lands with the prefill UI PR (Open Item #17)" is now satisfied by `KNOWN_PROFILE_FIELDS`, but the CHECK constraint or application-level insert validator lands with D2b where the write path actually creates rows from a validated field-name. PR7's reads tolerate stale or out-of-registry rows (the provenance lookup is keyed by `field_name`; we only render badges for names we recognise).
- `routes/coros_ingest.py` / `routes/coros.py` / `routes/polar.py` / `routes/polar_ingest.py` / `routes/oauth_callbacks.py` / `routes/provider_auth.py` — zero edits. PR7 is read-side onboarding only.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1–PR6 used. PR7 doesn't add columns; the documentation gap holds steady.

---

## 3. What landed

### 3.1 `KNOWN_PROFILE_FIELDS` registry (`routes/profile_fields.py`)

5 entries, one per `PREFILL_ELIGIBLE_FIELDS` column. Per-field metadata:

| `name` | `label` | `unit` | `cast` | `extractors` |
|---|---|---|---|---|
| `body_weight_kg` | Body weight | kg | `float` | `{coros: extract_body_weight_coros, polar: extract_body_weight_polar}` |
| `hrmax_bpm` | Maximum heart rate (HRmax) | bpm | `int` | `{coros: extract_hrmax_coros, polar: extract_hrmax_polar}` |
| `lactate_threshold_hr_bpm` | Lactate threshold heart rate | bpm | `int` | `{coros: extract_lactate_threshold_hr_bpm_coros, polar: extract_lactate_threshold_hr_bpm_polar}` |
| `vo2max` | VO2max | ml/kg/min | `float` | `{coros: extract_vo2max_coros, polar: extract_vo2max_polar}` |
| `cycling_ftp_w` | Cycling FTP | watts | `int` | `{coros: extract_cycling_ftp_w_coros, polar: extract_cycling_ftp_w_polar}` |

The `cast` field mirrors `routes/profile.py:edit()`'s `_num('hrmax_bpm', cast=int)` semantics so D2b's write path can re-use the same coercion via the registry rather than hardcoding casts. PR7 doesn't use `cast` (read-only); it's there waiting for D2b.

Module-level `assert` at the bottom of the file verifies `set(KNOWN_PROFILE_FIELDS names) == set(PREFILL_ELIGIBLE_FIELDS)`. If a future PR adds a column to `PREFILL_ELIGIBLE_FIELDS` without updating the registry (or vice versa), the import fails loudly at app boot. Same defensive pattern as PR3's `chain_registry.py` invariant assertions.

`provider_label(slug)` reads from `CONNECTION_PROVIDERS` rather than re-encoding the slug→label mapping — single source of truth.

### 3.2 Provider extractors (`routes/profile_extractors.py`)

10 functions total. Contract: `(db, user_id) -> (value, synced_at, note)` or `(None, None, None)`.

**Real (2):** `extract_hrmax_coros` + `extract_hrmax_polar` share a helper `_hrmax_from_cardio_log(db, user_id, provider_id_col)` that runs:

```sql
SELECT MAX(max_hr) AS hrmax, MAX(date) AS latest
FROM cardio_log
WHERE user_id = ?
  AND <provider_id_col> IS NOT NULL
  AND max_hr IS NOT NULL
  AND date >= ?
```

Window is 90 days (constant `_DERIVED_WINDOW_DAYS`). The `provider_id_col` is interpolated via f-string — call sites are this module's own functions only, never user input, so safe. The query benefits from `idx_cl_user_date` (existing) for the user/date scan; the `provider_id_col` filter is a narrowing predicate over the scan.

The `synced_at` returned is the latest contributing row's `date` (a TEXT YYYY-MM-DD per `cardio_log.date NOT NULL` schema), not when the row was ingested — this is intentional: the field "freshness" the athlete cares about is "when did this activity happen," not "when did our ingest pick it up."

The `note` string is `"Max heart-rate observed across the last 90 days of activity data."` — helps the athlete understand this isn't a lab-measured HRmax and that it might undershoot true HRmax if they didn't push hard in the window.

**Stubs (8):** All return `(None, None, None)`. Documented inline why each is a stub:
- `body_weight_kg`: Polar UserBodyComposition + COROS account profile aren't wired into ingest yet.
- `lactate_threshold_hr_bpm`: No provider in current ingest supplies this.
- `vo2max`: COROS Health VO2max + Polar Fitness Test aren't ingested.
- `cycling_ftp_w`: Wahoo FTP API paused; no other provider supplies.

When wellness-pull or Wahoo ingest ships, the stubs flip to real reads without changing the registry shape.

### 3.3 `/onboarding/prefill` route (`routes/onboarding.py:prefill`)

Single GET handler. Walks `KNOWN_PROFILE_FIELDS`; for each field:

1. Read current value from `athlete_profile` (via `get_athlete_profile`).
2. Read provenance row (if any) from `athlete_profile_field_provenance` — PG-only, mirrors `_record_self_report_provenance`'s guard.
3. For each provider slug in `field_def['extractors']` that is also in the connected-provider slug set (from `load_connections`), call the extractor and collect `(provider_slug, provider_label, value, synced_at, note)` if value is not None.
4. Sort candidates by `synced_at` descending (most-recent-wins per v5 §A.2.2 step 3); None `synced_at` sorts last via the `c['synced_at'] or ''` key.

Renders `onboarding/prefill.html` with `fields=[…]` + summary counts. Three template branches per §3.4 below.

### 3.4 Prefill comparison page (`templates/onboarding/prefill.html`)

Bootstrap 5 layout. Three render variants:

| State | Trigger | Render |
|---|---|---|
| **Empty (no providers)** | `connected_count == 0` | `alert-info`: "No providers connected yet. … You'll enter the values below manually on the next page. … connect any time from Profile → Connections and re-run this review." Card grid still renders all 5 fields with "Currently stored: Not set" + "Provider data: None of your connected providers supply this field yet." |
| **Connected, no candidates** | `connected_count ≥ 1 and fields_with_candidates == 0` | Muted explainer: "Your N connected provider(s) ha[s/ve] not synced enough data yet to fill in any of the performance baselines below." Card grid still renders. |
| **Candidates present** | `fields_with_candidates ≥ 1` | Summary: "We found provider data for M of 5 performance baselines. Review each value below. The write-back controls (Use provider / Keep current) ship in the next release." Card grid with comparison cards. |

Each card has:

- Header: field label (left) + unit (right, muted).
- Body: `<dl>` two-column layout:
  - "Currently stored" → bold value + provenance badge (or "Not set" + no badge).
  - One `<dt>/<dd>` pair per provider candidate: provider label + bold value + `synced_at` date + extractor note.
  - If no candidates: "Provider data: None of your connected providers supply this field yet."
- Footer (only if candidates present): `[Use provider value]` + `[Keep current]` buttons, both rendered as Bootstrap `btn ... disabled` with `aria-disabled="true"` and `title="Write-back ships in the next release."` — the disabled state is honest, not misleading.

Page-level Continue button at the bottom → `/profile?tab=athlete` (the existing v1 §A entry surface, unchanged from pre-PR7 except that we now route through prefill first).

Provenance badge mapping:
- `'self_report'` → "Self-reported"
- `'manual_override'` → "Manually set"
- `'provider_X'` (e.g. `'provider_coros'`) → "From coros" (uses `source[9:]` slice; raw slug, not the label-cased version — a small but defensible omission since today no provider source rows exist, and when D2b writes them they'll be lowercase slugs anyway; if the cosmetics matter we can map the slug to a label via `CONNECTION_PROVIDERS` in a future tidy-up).

### 3.5 Step-2 → Step 3a routing flip

`_POST_STEP2_TARGET` (single constant) replaced with three:

```python
_POST_STEP2_CONTINUE_TARGET = '/onboarding/prefill'
_POST_STEP2_SKIP_TARGET = '/profile?tab=athlete'
_POST_STEP3_TARGET = '/profile?tab=athlete'
_POST_STEP2_TARGET = _POST_STEP2_CONTINUE_TARGET  # alias, see below
```

`continue_()` now redirects to `_POST_STEP2_CONTINUE_TARGET`. `skip()` redirects to `_POST_STEP2_SKIP_TARGET`. Why the asymmetry: an athlete who skipped connecting has zero providers → the prefill page would render its "No providers connected yet" empty state with the "you'll enter values manually" message. Useful when they intentionally went through the prefill flow; pointless detour when they explicitly chose Skip. Skip jumps directly to the profile form; Continue routes through prefill review.

The `_POST_STEP2_TARGET` alias preserves the connect.html template's render param (the template passes it through but doesn't actually render it anywhere; PR4/PR5 left it as dead code that we don't bother to remove this PR). Future cleanup: drop the alias + the unused template var.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| All 3 new/edited Python files AST-parse clean (`routes/profile_extractors.py`, `routes/profile_fields.py`, `routes/onboarding.py`) | `ast.parse` over each | ✅ Verified |
| `routes/profile_extractors.py` defines exactly 10 `extract_*` functions, one per (field × provider) cross-product | AST FunctionDef walk | ✅ Verified — 10 functions: body_weight, hrmax, lactate_threshold_hr_bpm, vo2max, cycling_ftp_w × {coros, polar} |
| `routes/profile_fields.py:KNOWN_PROFILE_FIELDS` name set equals `athlete.PREFILL_ELIGIBLE_FIELDS` | AST dict-value walk over both files | ✅ Verified — both sets equal `{'body_weight_kg', 'hrmax_bpm', 'lactate_threshold_hr_bpm', 'vo2max', 'cycling_ftp_w'}` |
| `routes/onboarding.py` `_POST_STEP2_CONTINUE_TARGET = '/onboarding/prefill'`; `skip()` redirects to `_POST_STEP2_SKIP_TARGET`; `continue_()` redirects to `_POST_STEP2_CONTINUE_TARGET`; new `prefill()` route at `/prefill` | grep | ✅ Verified |
| `templates/onboarding/prefill.html` Jinja parses cleanly | `Environment.parse()` | ✅ Verified |
| Stub render variant A: 1 candidate field (HRmax with COROS+Polar values), 1 already-stored manual_override, 1 self_report, 1 provider_polar — all 5 fields render with correct anchors | inline `DictLoader` + minimal `base.html` stub + mocked `csrf_token`, `csp_nonce`, `url_for`, `get_flashed_messages` | ✅ Verified — 10 anchors present: "Step 3 — Review your profile data", "Currently stored", "Maximum heart rate", "188", "192", "Self-reported", "Manually set", "From polar", "Use provider value", "Continue to profile" |
| Stub render variant B: empty state (`connected_count=0`) | inline render | ✅ Verified — "No providers connected" + "Continue to profile" both present |
| Stub render variant C: providers connected but no candidates | inline render | ✅ Verified — "has not synced enough data yet" + "Continue to profile" both present |
| `Project_Backlog_v19.md` exists; v18 entry archived to predecessor block; D-50 row updated with PR7 status + PR8+ candidate menu; v19 header narrative reflects D2a shipped + D2b deferred | grep + visual | ✅ Verified |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads `Project_Backlog_v19.md` | grep | ✅ Verified |
| Flask not installed in sandbox — full app import not exercisable | python3 import check | ⚠️ Same gap as PR1–PR6. Live `/onboarding/prefill` page-load + HRmax-extractor sanity (athlete with COROS-tagged `cardio_log` rows in last 90 days) + Step-2 Continue → prefill redirect + Step-2 Skip → profile form preserved are owed at deploy time |

No drift between this handoff's narrative and on-disk state.

The same "can't exec the Flask app without Flask" gap PR1 §6 + PR2 §4 + PR3 §4 + PR4 §4 + PR5 §4 + PR6 §4 flagged applies. AST + Jinja parse + stub-render across three template variants are the offline guards. The PR7 §5.0 live-checks below are mandatory before this PR is "real."

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR7 reaches production)

PR7 ships zero schema changes + 4 new code surfaces. The risky bits are (a) the HRmax extractor's actual query behavior under real `cardio_log` data and (b) the Step-2 routing flip not breaking the Continue/Skip distinction.

1. **Schema is unchanged.** No migration to verify. Spot-check `\d athlete_profile` + `\d athlete_profile_field_provenance` on Neon are unchanged from PR6's state.
2. **`/onboarding/prefill` page render (empty state).** Open `/onboarding/prefill` as a test athlete with **zero providers connected**. Expect:
   - Stepper shows Step 1 ✓, Step 2 ✓, **Step 3 (current)**.
   - `alert-info` "No providers connected yet" panel.
   - 5 cards, each with "Currently stored: Not set" + "Provider data: None of your connected providers supply this field yet."
   - Continue button → `/profile?tab=athlete`.
3. **`/onboarding/prefill` page render (HRmax candidate present).** As Andy's account (which has COROS connected per PR1): trigger a COROS sync (or wait for it) so at least one `cardio_log` row has `coros_label_id IS NOT NULL` + `max_hr IS NOT NULL` + `date >= today - 90`. Reload `/onboarding/prefill`. Expect:
   - HRmax card shows current value (from Andy's PR6 manual entry, if he filled it in) + provenance badge ("Self-reported" if he just saved it).
   - HRmax card shows COROS candidate row with the bpm value matching `SELECT MAX(max_hr) FROM cardio_log WHERE user_id=<andys-uid> AND coros_label_id IS NOT NULL AND max_hr IS NOT NULL AND date >= <today-90>`.
   - `synced_at` cell shows the date of the latest contributing row.
   - Note text reads "Max heart-rate observed across the last 90 days of activity data."
   - `[Use provider value]` + `[Keep current]` buttons render with `class="btn btn-sm btn-outline-* disabled"` + `aria-disabled="true"` + tooltip "Write-back ships in the next release."
4. **Step-2 Continue → prefill redirect.** Open `/onboarding/connect`. Click Continue. Browser should redirect to `/onboarding/prefill`. (Pre-PR7 it redirected directly to `/profile?tab=athlete`.)
5. **Step-2 Skip → profile form preserved.** Open `/onboarding/connect`. Click Skip. Browser should redirect to `/profile?tab=athlete` (unchanged from PR5).
6. **Continue → profile.** From `/onboarding/prefill`, click "Continue to profile". Browser lands on `/profile?tab=athlete`.
7. **Disabled buttons are non-actionable.** Click `[Use provider value]` — should do nothing (the `disabled` class on `<button>` blocks the click; tooltip explains why). No console errors.
8. **Independent of PR7:** PR1 §5.0 COROS pre-deploy + PR3 §5.0 Polar pre-deploy + PR4 §5.0 Connections-tab spot-check + PR5 §5.0 onboarding spot-check + PR6 §5.0 Performance Baselines spot-check are still owed if not yet completed.

### 5.1 PR8+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR7_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR6_Closing_Handoff_v1.md` (predecessor).
4. `aidstation-sources/Project_Backlog_v19.md` — current; PR8 may need to bump to v20 (see §5.4).
5. `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` §A.2.3 + §A.2.6 (write-side edit semantics + clear-override path) — D2b needs both in working memory.

The candidate menu carries forward from PR6 §5.1 with D2a now shipped (read-only) and D2b promoted to the recommended next.

#### Option D2b — Write-side prefill (recommended next)

Lights up PR7's stub buttons. Scope:

- **POST handler at `/onboarding/prefill/apply`** (or per-field `POST /onboarding/prefill/<field>/use`): writes `athlete_profile.<col>` = provider value via `upsert_athlete_profile` + writes `athlete_profile_field_provenance.source = 'provider_<X>'` via a new helper analogous to `_record_self_report_provenance`. Single-field write granularity per v5 §A.2 "Review per field" path; bulk "Apply all" is a follow-on if scope budget allows.
- **`manual_override` flip in `_record_self_report_provenance`**: read existing `source` first; if it's `'provider_*'` and the new value differs from the provider's last-seen value, flip `source = 'manual_override'`. Today PR7's reads tolerate this; PR6's writes always set `'self_report'` which is incorrect once provider rows exist. Refactor the helper to take an "old source" lookup query into account.
- **Clear path popover (v5 §A.2.6)**: clicking the provenance badge on a `'manual_override'` row opens a popover with "Use COROS value (188 bpm, last synced 2026-05-10) instead." Restores prefill — deletes the `manual_override` provenance row, leaves the `athlete_profile.<col>` value alone (or zeroes it to force re-prefill on next read).
- **CHECK constraint on `athlete_profile_field_provenance.field_name`**: now that `KNOWN_PROFILE_FIELDS` exists, the free-text TEXT column gets a CHECK against the known set OR an application-level validator in the new write path. Schema CHECK is one schema-migration line; app-level validator is one if-statement. Pick whichever ships cleaner.

Estimate: 4-5 files. Right at ceiling. If overage, split bulk "Apply all" + clear popover to D2c.

#### Option D3 — Locale-creation flow with Mapbox chain detection

Carries forward unchanged from PR6 §5.1.

#### Option E — 14-day connect-provider nudge background job

Carries forward unchanged. PR5's `/onboarding/connect` is the deep-link target.

#### Option F — Polar refresh-on-401

Carries forward unchanged. Watch item only.

#### Option H — Provider blueprint roster expansion

Carries forward unchanged.

### 5.2 Recommended sequence (revised post-PR7)

**D2b → E → D3**, with **F** as a watch item; **H** providers as opportunistic adds whenever an integration partner is ready.

D2b is the obvious next step — PR7's read-only prefill page literally tells the athlete "write-back ships in the next release." Shipping the write path closes that promise and completes the v5 §A.2 prefill loop. After D2b ships, E (14-day nudge) becomes the highest-priority remaining v5 gap.

### 5.3 Standing items not on the critical path (carried from PR6 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged. Independent.
- **D-54 SQLite collapse** — unchanged. Catalog Migration Phase 5.
- **D-55 Garmin onto `provider_auth`** — paused.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. PR7 doesn't touch the webhook path.
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — *closed by PR7*. Removed from carry-forward.
- **DATABASE.md update** — unchanged.
- **PROVIDERS_SCHEMA.md update** — unchanged.
- **Manual-override flip** (carry-over from PR6 §5.3) — unchanged; lands with D2b per §5.1 above.
- **Provenance-row deletion on field clear** (carry-over from PR6 §5.3) — unchanged; lands with D2b's clear-override path.
- **`PREFILL_ELIGIBLE_FIELDS` placement in `athlete.py`** (PR6 §5.3) — *resolved* by PR7's `KNOWN_PROFILE_FIELDS` registry which sits alongside it in spirit (one is `routes/profile.py`'s gatekeeper, the other is `routes/onboarding.py`'s consumer; they coexist).
- **`field_name` CHECK constraint on `athlete_profile_field_provenance`** (new this PR) — registry exists in PR7 but the table's column is still free-text TEXT. Validation lands with D2b's write path (either schema CHECK or app-level validator).
- **Unused `_POST_STEP2_TARGET` alias in `routes/onboarding.py`** (new this PR) — preserved for back-compat with `templates/onboarding/connect.html`'s `post_step2_target` render param (the template passes it through but doesn't render it anywhere). Cleanup: drop the alias + the template's unused var; one minute of work; doesn't block anything.
- **Provider-agnostic OAuth-start signature** (carry-over from PR5 §5.3) — unchanged. Lands with H.

### 5.4 Backlog row update (next PR's first action)

PR7 bumped v18→v19 (this revision). PR8 will need to bump v19→v20 if and only if it lands a state-changing event (e.g. D2b ships → closes the write-side prefill UX bucket; would update D-50 row notes).

**For PR8, owed v19 → v20 bump (mechanically-applicable per Rule #11):**

1. Copy `aidstation-sources/Project_Backlog_v19.md` to `aidstation-sources/Project_Backlog_v20.md`.
2. **Replace** the file-revision header on line 5:
   - Old text:
     ```
     **File revision:** v19 — 2026-05-14 (D-50 row status flip catching up PR7: D-50 status cell now reads 🟢 PR1 + PR2 + PR3 + PR4 + PR5 + PR6 + PR7 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, `f4d2e75` PR4-merge, `34637d2` PR5-merge, `2c8d01f` PR6-merge, `<PR7-merge-pending>`); 🟢 frontend Option D1 (Step-2 connect screen) shipped PR5; 🟢 Option D2a (read-side prefill UX) shipped PR7 …
     ```
   - New text (assuming PR8 = D2b):
     ```
     **File revision:** v20 — 2026-05-14 (D-50 row status flip catching up PR8: D-50 status cell now reads 🟢 PR1 + PR2 + PR3 + PR4 + PR5 + PR6 + PR7 + PR8 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, `f4d2e75`, `34637d2`, `2c8d01f`, `<PR7-merge>`, `<PR8-merge>`); 🟢 frontend D1 + D2a + D2b (write-side prefill UX) shipped PR8 — POST handlers for [Use provider] / [Keep current] + `'self_report'` → `'manual_override'` flip + clear-override popover per `V5_Implementation_PR8_Closing_Handoff_v1.md`. No new D-row work this revision — pure status tracking)
     ```
3. **Prepend** to the predecessor revisions block:
   ```
   - v19 — 2026-05-14 (D-50 row status flip catching up PR7: …)  [verbatim from current v19 line 5 narrative]
   ```
4. **Update** the D-50 row status cell from PR1–PR7 → PR1–PR8 shipped, mark D2b as shipped, leave D3/E/F/H pending. Update Notes column "PR8+ candidate menu" → "PR9+ candidate menu" and shift D2b entry from pending → shipped.
5. **Bump** `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line from `Project_Backlog_v19.md` to `Project_Backlog_v20.md`.

**If PR8 is something other than D2b**, the narrative text changes but the file mechanics are identical (copy → header replace → predecessor prepend → D-50 row update → CLAUDE.md bump). Write the v20 header narrative to reflect what actually shipped.

---

## 6. Open items / honest flags

- **No live page-render verification.** Same risk class as PR1–PR6. Flask isn't installed in the sandbox. AST-parse + Jinja-parse + stub-render across three template variants (populated / no-providers-empty / providers-but-no-candidates) confirmed the template wires + renders. The PR7 §5.0 manual click-through is mandatory before this is real.
- **`extract_hrmax_*` returns the row's `date`, not its `fetched_at`.** Intentional — the athlete-meaningful freshness signal is when the workout happened, not when our ingest got around to processing it. But it does mean a backfilled-old workout shows as "2024-08-12" rather than "synced yesterday." If athletes find this confusing in practice, we can switch to `fetched_at`, but the field doesn't exist on `cardio_log` (only on the provider-side ingest tables); we'd need a schema change. Not on the critical path; surfaces if real users complain.
- **8 of 10 extractors are stubs.** Only HRmax has real provider data today. The prefill page is honest about this — fields with no candidates render with "None of your connected providers supply this field yet." But it does mean PR7's value as a feature is mostly in the foundation it lays for D2b + future wellness-pull integrations, not in actually saving athletes data-entry effort today. Andy is also the only test athlete; he can self-report just fine.
- **`athlete_profile_field_provenance.field_name` is still free-text TEXT.** The canonical `KNOWN_PROFILE_FIELDS` registry now exists but isn't enforced by the schema. PR7 reads tolerate stale or out-of-registry rows (the provenance lookup is keyed by `field_name`; we only render badges for fields whose name appears in `KNOWN_PROFILE_FIELDS`, but a stray row with an unknown field_name would be silently ignored). D2b's write path is where validation actually matters — either a schema CHECK or an app-level validator lands then. Documented in §5.3 carry-forward.
- **`_POST_STEP2_TARGET` alias is dead code.** Kept to avoid editing `templates/onboarding/connect.html`'s render param. The template passes `post_step2_target` through but doesn't render it. Tactical: removing the alias would force a template edit which bumps file count. Documented in §5.3 cleanup carry-forward.
- **Provenance badge for `provider_*` source uses the raw slug.** The slice `f.provenance.source[9:]` extracts everything after `'provider_'`. For `'provider_coros'` it renders "From coros" (lowercase). Cosmetically the connect-page badges show "COROS" / "Polar". One-line fix to look up via `provider_label(slug)` but no real source values exist today (PR6 only writes `'self_report'`); D2b is the first PR where `'provider_*'` rows actually get created, so cosmetic alignment ships there for free. Flagged for transparency.
- **Per-field "From provider X" tag doesn't include "(Y days ago)".** v5 §A.2.2 step 3 specifies "from {provider}, {age}" tagging on the value. PR7 renders `synced_at` as a separate line under the value rather than inline in a tag. Functionally equivalent but spec-narrative-divergent. If Andy wants the tag exactly as spec'd, D2b can adjust — it's a template tweak, not an architectural concern.
- **No tests added.** Inline `python3` execution of Jinja stub-render across three context variants + AST inspection of registry/extractor cross-checks + grep anchor checks are the closest this PR comes to test infrastructure. Same framing as PR1–PR6: a real `tests/` directory still doesn't exist. D2b's write path (with source-flip semantics) is the first PR where unit tests would deliver clearly higher value than offline inline exercises — the source-flip logic has edge cases (existing `'provider_X'` + new athlete value matching `X`'s last sync → still `'provider_X'`; existing `'provider_X'` + new athlete value not matching → `'manual_override'`; etc.) that benefit from explicit test cases. Flagged for PR8.
- **4 substantive code files + 2 bookkeeping (v19 + CLAUDE.md) + 1 handoff = 7 total.** Under the 5-substantive ceiling for the first time since PR2. Headroom because the work concentrated in two new files (extractors + registry) plus one route addition + one new template — no edits to existing app surfaces beyond the onboarding route. Good.
- **HRmax derived from `cardio_log.max_hr` will undershoot true HRmax** if the athlete hasn't pushed hard in the 90-day window. The note text mentions this implicitly ("Max heart-rate observed across…") but it's not a warning. D2b's write path may want to add a guard: if the athlete clicks "Use provider value" for a derived-extractor result, surface a confirmation ("This value is derived from your recent activity, not a lab test. Are you sure?"). Out of PR7 scope; flagged for D2b.

---

## 7. Gut check

**What this session got right.**

- **Closed Open Item #17.** The `KNOWN_PROFILE_FIELDS` registry has been pending since the D-58 design wave (Onboarding wave). PR6 unblocked it by laying the column foundation; PR7 ships the registry that the comparison page consumes. One more cross-layer design item retired.
- **Honest empty states.** Three render branches (no-providers / providers-but-no-data / candidates-present) all render gracefully. The connected_count==0 branch tells the athlete exactly what's going on rather than rendering an empty card grid that looks broken.
- **Stubs are honest.** 8 of 10 extractors return None today. The template renders "None of your connected providers supply this field yet" for those — accurate, not aspirational. Athletes know what they can expect from each connected service.
- **Disabled buttons are honest.** `[Use provider value]` / `[Keep current]` render as Bootstrap-disabled with a tooltip saying "Write-back ships in the next release." Same honesty pattern as PR5/PR6 footers.
- **Defensive registry invariant.** `assert KNOWN_PROFILE_FIELDS names == PREFILL_ELIGIBLE_FIELDS` fails loudly at app boot if the two drift apart. Same shape as PR3's `chain_registry.py` invariant — defensive, not paranoid.
- **Came in under the ceiling.** 4 substantive code files (vs 5-file ceiling). The work concentrated in two new modules + one route addition + one template; no scope creep into adjacent code surfaces.

**Risks.**

- **HRmax extractor's 90-day window is a heuristic.** Spec'd in code as `_DERIVED_WINDOW_DAYS = 90` but v5 §A.2 doesn't pin a window length. Too short and a winter-detrained athlete shows artificially low HRmax; too long and a years-old fluke shows up. 90 days is the sensible midpoint a coach would trust. If a real athlete complains, we tune the constant.
- **`provider_id_col` f-string interpolation in `_hrmax_from_cardio_log`.** Looks like SQL injection if you squint. It isn't — the column name comes from this module's own call sites (`'coros_label_id'`, `'polar_exercise_id'`), never from user input. But a future contributor wiring a new extractor needs to know not to pass user-controllable strings here. Documented inline.
- **Step-2 Skip target asymmetry could confuse.** Continue goes to `/onboarding/prefill`; Skip goes to `/profile?tab=athlete`. Rationale (Skip → no providers → nothing to compare → why visit prefill?) makes sense, but a UI consistency stickler might prefer both go through prefill which then handles the no-providers state itself. The current asymmetry skips a useless redirect for skip-and-go-no-providers athletes. Defensible either way; flagged for transparency.
- **Disabled buttons rely on the `disabled` class.** Bootstrap 5's `btn.disabled` blocks clicks via `pointer-events: none` CSS. If the CSS doesn't load (rare but possible) the buttons would be clickable. Since they're plain `<button type="button">` with no form action, a click does nothing anyway — failure mode is silent no-op, not data corruption. Acceptable risk for a read-only PR.

**What might be missing.**

- **No "Apply all" affordance.** v5 §A.2.5 mentions "Apply all (bulk update), Review per field (per-row checkbox), Skip for now" actions for the re-onboarding prompt. PR7's read-only design has no Apply all. D2b's write path can add it as a single bulk-action button at the bottom of the card grid — straightforward; not a redesign.
- **No tolerance-based suppression** (v5 §A.2.7). Provider sync delivering a new value within tolerance of the stored value should be silent; outside tolerance should surface as a passive notification. PR7 has no notification surface — would need a `provider_value_changed` row in `account_nudges` or similar. Lands with D2b's write path + the next provider-sync ingest PR. Documented for transparency, not in scope.
- **Per-field "winning provider" badge.** v5 §A.2.2 step 3 says "Among the candidates, pick the one whose latest sync delivering this field is most recent. Render its value with the 'from {provider}, {age}' tag." PR7 renders all candidates equally (sorted by recency); the "winner" is implicit (top of list). For 1-candidate fields this is fine; for 2-candidate fields (HRmax with COROS + Polar both connected) it's a soft cue, not an explicit one. D2b's "Use provider" button is per-row so the explicit winner-pick lands then.
- **Mapbox-style geographic-prefill is not in `KNOWN_PROFILE_FIELDS`.** Locale prefill is D3's domain; registry is intentionally scoped to numeric performance baselines. When D3 ships, locale fields would either extend `KNOWN_PROFILE_FIELDS` (one big registry across §A.2 + §J.*) or live in a parallel `KNOWN_LOCALE_FIELDS`. Defer the decision to D3's design pass.

**Best argument against this session's scope.**

PR7 ships a feature that 80% of the time (8 of 10 extractors) shows the athlete "None of your connected providers supply this field yet." The actually-useful surface is the HRmax row, and only for athletes with COROS or Polar connected and recent hard-effort activities. For an app with one test athlete (Andy), this is a thin slice of immediate value.

Counter: the registry + route + template are the foundation D2b needs. Without PR7, D2b would have to ship the registry + extractors + read UI + write path in one PR, which would exceed the 5-file ceiling badly. Splitting D2 into D2a (PR7, read-only) + D2b (PR8, writes) is the cleaner sequence — each PR has a focused scope and a working surface to ship.

Counter to the counter: the read-only page is mostly a developer artifact today, not an athlete-facing benefit. The actual user-visible win lands in D2b. PR7's value is internal scaffolding + closing Open Item #17 — both real, but neither is a feature an athlete would notice. Fair trade-off for splitting at the natural seam.

Alternatively, PR7 could have skipped the empty stubs (only ship `extract_hrmax_*` and only register `hrmax_bpm` in `KNOWN_PROFILE_FIELDS`). Counter: the field list comes from `PREFILL_ELIGIBLE_FIELDS` (PR6 spec'd these 5 as the §A.2 prefill-eligible set). Skipping 4 of them in the registry would mean the comparison page only shows 1 field — a degraded read-side that doesn't match PR6's footer promise ("Connected providers will auto-populate these in a future release"). Better to render all 5 with honest empty-state messaging than ship 1.

---

## 8. Forward pointers

- **Next session:** PR8 = Option D2b (write-side prefill, recommended) or any of the other PR5/PR6/PR7 §5.1 carry-forward candidates. PR7 unblocks D2b by laying the read-side foundation; D2b lights up the `[Use provider]` / `[Keep current]` buttons and ships the `'self_report'` → `'manual_override'` source-flip refactor.
- **Before next code lands:** PR7 §5.0 spot-check on the deployed app (`/onboarding/prefill` page-load empty + populated + Continue/Skip round-trip + HRmax extractor sanity against real `cardio_log` rows). PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 + PR6 §5.0 are still owed if not yet completed.
- **First action of next session:** Rule #9 reconciliation. Specifically: confirm PR7 commit landed on `claude/v5-implementation-handoff-XtgyG` (or merged to main with its own merge commit); confirm `routes/profile_extractors.py` defines 10 `extract_*` functions; confirm `routes/profile_fields.py:KNOWN_PROFILE_FIELDS` registry matches `PREFILL_ELIGIBLE_FIELDS`; confirm `routes/onboarding.py` has the new `prefill()` route and the `_POST_STEP2_CONTINUE_TARGET` / `_POST_STEP2_SKIP_TARGET` split; confirm `templates/onboarding/prefill.html` exists with the 5-card layout; confirm `Project_Backlog_v19.md` exists with v18 archived to predecessor block; confirm `CLAUDE.md` "Authoritative current files" backlog line reads v19.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **PR7 has one deferred mechanical edit:** the v19 → v20 backlog bump for PR8's first action, spec'd verbatim in §5.4
- #12 numeric version suffixes (backlog now at v19; v20 lands in PR8 per §5.4)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR7 closing handoff. v5 onboarding D2a (read-side prefill UX) shipped: `KNOWN_PROFILE_FIELDS` registry (`routes/profile_fields.py`) closing Open Item #17, 10 provider extractors (`routes/profile_extractors.py` — 2 real HRmax-from-`cardio_log` + 8 stubs), `/onboarding/prefill` GET route + comparison-page template + Step-2 Continue→prefill flip while preserving Step-2 Skip→profile-form. Stub `[Use provider]` / `[Keep current]` buttons render disabled with honest "ships in the next release" tooltip. Backlog bumped v18 → v19. Next: Andy's choice among PR8 candidates in §5.1 (D2b recommended); v19 → v20 backlog bump mechanically spec'd for PR8's first action.*
