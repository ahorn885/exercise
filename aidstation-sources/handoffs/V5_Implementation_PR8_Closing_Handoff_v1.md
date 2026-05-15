# V5 Onboarding Implementation PR8 — Closing Handoff

**Session:** Eighth substantive code session of the v5 onboarding implementation arc. Executes PR7 §5.1's recommended next — **Option D2b (write-side prefill UX)** — closing the v5 §A.2 prefill loop opened by PR6/PR7. Lights up PR7's stub action buttons via two new POST handlers (`/onboarding/prefill/<field>/use-provider` and `/keep-current`), refactors `_record_self_report_provenance` to honor v5 §A.2.3 source-flip stickiness (`'provider_*'` → `'manual_override'` when athlete edits a provider-sourced value), and adds the v5 §A.2.6 clear-override inline link beneath `'manual_override'` badges. App-level registry-driven field-name validation (no schema CHECK migration). Flips v19→v20 backlog per PR7 §5.4 mechanical spec.
**Date:** 2026-05-15
**Predecessor handoff:** `V5_Implementation_PR7_Closing_Handoff_v1.md` (its §5.1 Option D2b is exactly what this session executes; its §5.4 v19→v20 backlog bump runs here per Rule #11 mechanical spec).
**Branch:** `claude/v5-implementation-handoff-VXveb` (per-session feature branch off `main`; PR7 was merged into `main` as `df17f08` via PR #39 before this session started).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 live `/onboarding/prefill` apply/keep/clear-override round-trips + source-flip on profile-form save + 404 on bogus field name owed at deploy time (no Flask in sandbox, same gap as PR1–PR7).
**Time-on-task:** Single chat. Substantive files: **3** (`routes/profile.py` refactor + 2 helper additions, `routes/onboarding.py` +2 routes +4 helpers, `templates/onboarding/prefill.html` action buttons + clear-override link). Plus the v19→v20 backlog bump (`Project_Backlog_v20.md` new copy + 1-line `CLAUDE.md` edit) and this handoff = 5 total. Comfortably under ceiling.

---

## 1. Session-start verification (Rule #9)

Verified the PR7 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/v5-implementation-handoff-VXveb` clean off `main`; PR7 merged to `main` as `df17f08` via PR #39 (commit `500fd8e`) | `git status` + `git log --oneline -15` | ✅ Verified |
| `routes/profile_extractors.py` defines exactly 10 `extract_*` functions, one per (field × provider) cross-product | `grep -c "^def extract_"` = 10 | ✅ Verified |
| `routes/profile_fields.py:KNOWN_PROFILE_FIELDS` registry exists with 5 entries; `provider_label` helper at L101 | grep | ✅ Verified |
| `routes/onboarding.py:_POST_STEP2_CONTINUE_TARGET = '/onboarding/prefill'`; `_POST_STEP2_SKIP_TARGET = '/profile?tab=athlete'`; new `prefill()` route at `/prefill` | grep | ✅ Verified |
| `templates/onboarding/prefill.html` exists with the 5-card layout | ls | ✅ Verified |
| `Project_Backlog_v19.md` exists with v18 archived to predecessor block; `CLAUDE.md` "Authoritative current files" backlog line reads v19 | grep | ✅ Verified |
| **Branch-name drift surfaced:** PR7 handoff narrates branch `claude/v5-implementation-handoff-XtgyG` (already merged via PR #39 → `df17f08`); this session was started on `claude/v5-implementation-handoff-VXveb` per system-prompt assignment. Branch is off post-PR7 `main`, so on-disk state already includes PR7's commits. No drift in *content*, only in branch identity for the predecessor's work | git branch -a | ✅ Reconciled — proceeding on `claude/v5-implementation-handoff-VXveb` per session assignment |

**No drift between PR7 handoff narrative and on-disk state** beyond the expected branch-name change for this session.

---

## 2. Files shipped this turn

All on branch `claude/v5-implementation-handoff-VXveb`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `routes/profile.py` | Edit (~25 lines net inside `_record_self_report_provenance`) | Refactored the helper to read existing provenance source first before writing. Three branches per v5 §A.2.3: (a) prior `source` starts with `'provider_'` → new `source = 'manual_override'` (athlete is overriding a provider-prefilled value by typing); (b) prior `source = 'manual_override'` → stays `'manual_override'` (re-edit of an already-overridden value); (c) prior row missing OR `source = 'self_report'` → write `'self_report'` (PR6 behavior preserved for the never-prefilled-field case). Single batch SELECT over the user's provenance rows up front, dict-lookup per field — no N+1. Field-name validation tightened: only names in `PREFILL_ELIGIBLE_FIELDS` produce writes (the existing guard is now documented as the registry-driven enforcement layer until a CHECK constraint ships). |
| 2 | `routes/onboarding.py` | Edit (+5 helpers + 2 new POST routes; ~150 net lines added) | (a) Header docstring updated to reflect D2b shipped, source-flip + clear-override path. (b) Imports: added `abort` from Flask, added `upsert_athlete_profile` from `athlete`. (c) New private helpers: `_lookup_field(name)` (registry lookup → field_def or None for 404 path); `_resolve_candidates(db, uid, field_def, connected_slugs)` (extracted from PR7's `prefill()` loop — returns sorted candidates for a single field, used by both `prefill()` and `use_provider()`); `_write_provider_provenance(db, uid, field_name, provider_slug)` (UPSERT `'provider_<slug>'` row); `_write_manual_override_provenance(db, uid, field_name)` (UPSERT `'manual_override'` row). Both PG-only via `database._is_postgres()` guard, mirrors `routes/profile.py:_record_self_report_provenance`. (d) `prefill()` refactored to use `_resolve_candidates` — same render output, candidate-resolution logic now lives in one place. (e) New `POST /prefill/<field>/use-provider` → applies winning candidate via `upsert_athlete_profile` + writes `'provider_<slug>'` provenance. Re-resolves candidates at write time (form carries no value payload — a stale browser tab can't push a stale provider value). Aborts with flash on (i) unknown field name → 404, (ii) no candidate available right now → warning + redirect. (f) New `POST /prefill/<field>/keep-current` → writes `'manual_override'` provenance row without changing the stored value. Defensive guard against POSTs targeting empty current values (template hides the button in that case; crafted POSTs get a warning flash + redirect). |
| 3 | `templates/onboarding/prefill.html` | Edit (~35 lines net) | (a) Header doctstring updated — D2a/PR7 framing replaced with the D2b/PR8 story. (b) "Candidates present" intro copy rewritten — was "write-back controls ship in the next release" (PR7's honest read-only framing), now "Click *Use provider value* to apply a candidate, or *Keep current* to suppress re-prefill." (c) Provenance badge for `'provider_*'` source now renders `provider_label(slug)` instead of the raw slug — "From COROS" / "From Polar" instead of "From coros" / "From polar". The `provider_label` Python function is exposed to the template via the render_template context. (d) v5 §A.2.6 inline clear-override link added beneath the badge: surfaces only when `f.provenance.source == 'manual_override'` AND `f.candidates` (a live provider candidate exists to switch to). Renders as a small `<form method="post">` styled as a Bootstrap link button — no JS required, matches PR7's no-JS posture. (e) Action buttons replaced: was two `disabled` Bootstrap buttons with "ships in the next release" tooltips; now two real `<form method="post">` blocks. `[Use {provider} value]` button always renders when a candidate exists, labeled with the winning candidate's provider for clarity. `[Keep current]` button renders only when `f.current_value is not none` (you can't "keep" nothing — confirmed with Andy as the cleanest UX in the empty-value case). Each form ships a `csrf_token` hidden input matching the rest of the app's Flask-WTF CSRFProtect plumbing. |
| — | `aidstation-sources/Project_Backlog_v20.md` | New (copy of v19 + 4 surgical edits per PR7 §5.4 mechanical spec) | **File revision** header bumped v19→v20 with PR8 narrative (D-50 status flip catching up PR1–PR8; D1 + D2a + D2b shipped; D2b removed from pending). **Predecessor revisions** block prepends the v19 entry verbatim. **D-50 description column** updated: PR6's "(this revision)" annotation fixed to "(merge `2c8d01f`)"; new "PR7 (merge `df17f08`):" entry summarising D2a; new "PR8 (this revision):" entry summarising D2b including the source-flip refactor + clear-override inline link. **D-50 status cell** rewritten: 🟢 PR1–PR8 shipped; D1 + D2a + D2b all listed; D2b removed from pending list; `<PR7-merge-pending>` placeholder replaced with `df17f08`. **D-50 Notes column** rewritten: handoff pointer flipped to `V5_Implementation_PR8_Closing_Handoff_v1.md`; PR8+ → PR9+ candidate menu; D2b entry removed; new D2c entry added for bulk "Apply all" + tolerance-based re-prefill (split out from PR8 to stay under ceiling, picks up if athletes want bulk apply); recommended sequence flipped to "E → D3"; PR8-specific pre-deploy verification block appended. |
| — | `aidstation-sources/CLAUDE.md` | Edit (1-line) | Per PR7 §5.4 step 5: "Authoritative current files" backlog line bumped from `Project_Backlog_v19.md` to `Project_Backlog_v20.md`. Single-line edit, same shape as the v18→v19 bump PR7 did. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR8_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `routes/profile_fields.py` — unchanged. PR7's `KNOWN_PROFILE_FIELDS` registry is the source of truth PR8 consumes; no shape changes needed. The `cast` field on each entry was added in PR7 with D2b in mind; PR8 doesn't actually need it (the extractors already return correctly-typed values, and `upsert_athlete_profile` passes them through), but it stays as scaffolding for future write paths that might process raw form input.
- `routes/profile_extractors.py` — unchanged. The 10 extractor functions are pure reads; D2b consumes them via `_resolve_candidates`.
- `athlete.py` — unchanged. `upsert_athlete_profile` already accepts the 5 new columns via the `PROFILE_FIELDS` filter (PR6); D2b's apply path calls it as `upsert_athlete_profile(db, uid, **{field_def['name']: winner['value']})` which lands cleanly.
- `init_db.py` — unchanged. PR7 §5.1's D2b spec mentioned a CHECK constraint on `athlete_profile_field_provenance.field_name` as one option; PR8 ships the app-level alternative instead. No schema migration. `KNOWN_PROFILE_FIELDS` is the single source of truth; `_lookup_field` + the `PREFILL_ELIGIBLE_FIELDS` guard inside `_record_self_report_provenance` are the enforcement layer.
- `routes/coros_ingest.py` / `routes/coros.py` / `routes/polar.py` / `routes/polar_ingest.py` / `routes/oauth_callbacks.py` / `routes/provider_auth.py` — zero edits. PR8 is profile-side onboarding only.
- `templates/onboarding/connect.html` / `templates/profile/edit.html` — zero edits. Step-2 Continue/Skip targets unchanged from PR7. Profile-form edit now goes through the refactored `_record_self_report_provenance` automatically — no template change needed.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1–PR7 used. PR8 doesn't add columns; the documentation gap holds steady.

---

## 3. What landed

### 3.1 Source-flip refactor (`routes/profile.py:_record_self_report_provenance`)

PR6 always wrote `'self_report'`. v5 §A.2.3 row 1 ("Athlete types into a prefilled field") demands a flip to `'manual_override'` when the prior source was `'provider_*'`. PR8 implements the spec semantics.

Three-branch decision tree per call:

```
prior source             →  new source
─────────────────────────────────────────────
None (never written)     →  'self_report'      (first save)
'self_report'            →  'self_report'      (re-edit, athlete-only history)
'provider_<X>'           →  'manual_override'  (athlete is overriding a prefill)
'manual_override'        →  'manual_override'  (re-edit of an already-overridden value)
```

Offline verification covers all 5 cases (4 distinct outcomes; the 4th branch via two different prior sources):

```
prior=None                 -> 'self_report'      (first save, never prefilled)
prior='self_report'        -> 'self_report'      (re-edit of self-reported value)
prior='provider_coros'     -> 'manual_override'  (athlete overrides COROS prefill)
prior='provider_polar'     -> 'manual_override'  (athlete overrides Polar prefill)
prior='manual_override'    -> 'manual_override'  (re-edit of an already-overridden value)
```

Implementation: single batch `SELECT field_name, source FROM athlete_profile_field_provenance WHERE user_id = ?` up front (matches PR7's `prefill()` shape), dict-lookup per field name in the existing loop. No N+1 query risk; the existing UPSERT per field is preserved.

PG-only guard unchanged (early-return on SQLite). `field_name not in PREFILL_ELIGIBLE_FIELDS` guard unchanged — now documented as the registry-driven enforcement layer until a CHECK constraint ships.

### 3.2 POST handlers + helpers (`routes/onboarding.py`)

**`POST /onboarding/prefill/<field>/use-provider`**

The v5 §A.2.5 per-field "use this" + §A.2.6 clear-override "use {provider} value instead" both hit this endpoint. One write path, two UI entry points.

```python
@bp.route('/prefill/<field>/use-provider', methods=['POST'])
def use_provider(field):
    field_def = _lookup_field(field) or abort(404)
    db, uid = get_db(), current_user_id()
    connections = load_connections(db, uid)
    connected_slugs = {c['slug'] for c in connections if c['is_connected']}
    candidates = _resolve_candidates(db, uid, field_def, connected_slugs)
    if not candidates:
        flash(f'No provider value available for {field_def["label"]} right now.', 'warning')
        return redirect(url_for('onboarding.prefill'))
    winner = candidates[0]
    upsert_athlete_profile(db, uid, **{field_def['name']: winner['value']})
    _write_provider_provenance(db, uid, field_def['name'], winner['provider_slug'])
    db.commit()
    flash(f'{field_def["label"]} set from {winner["provider_label"]}.', 'success')
    return redirect(url_for('onboarding.prefill'))
```

Critical defensive choices:

- **Re-resolves candidates at write time.** The form ships only the CSRF token + the field name in the URL. The provider value isn't in the form payload — so a stale browser tab can't push a value the provider no longer reports. The extractor runs fresh against current `cardio_log` state.
- **404 on unknown field names.** `_lookup_field` returns None for any name not in `KNOWN_PROFILE_FIELDS`; `abort(404)` short-circuits the request. POSTs to `/onboarding/prefill/notarealfield/use-provider` fail loudly, not silently.
- **Flash warning on empty candidates.** If the provider data disappeared between page render and form POST (rare — would require a provider disconnect in the same session), the handler doesn't write anything; flashes a warning and redirects back to the prefill page.

**`POST /onboarding/prefill/<field>/keep-current`**

```python
@bp.route('/prefill/<field>/keep-current', methods=['POST'])
def keep_current(field):
    field_def = _lookup_field(field) or abort(404)
    db, uid = get_db(), current_user_id()
    profile = get_athlete_profile(db, uid) or {}
    if profile.get(field_def['name']) is None:
        flash(f'{field_def["label"]} has no current value to keep…', 'warning')
        return redirect(url_for('onboarding.prefill'))
    _write_manual_override_provenance(db, uid, field_def['name'])
    db.commit()
    flash(f'{field_def["label"]} marked as manually set…', 'info')
    return redirect(url_for('onboarding.prefill'))
```

Writes `'manual_override'` for the current stored value. Template hides the button when `current_value is None` (no "kept nothing" semantic); a crafted POST in that state hits the defensive guard and gets a warning + redirect, no DB write.

**Helpers (private to `routes/onboarding.py`):**

- `_lookup_field(name)` — linear scan over `KNOWN_PROFILE_FIELDS`. 5-entry registry; O(5) lookup; no need for a dict cache.
- `_resolve_candidates(db, uid, field_def, connected_slugs)` — extracted from PR7's `prefill()` loop. Returns sorted candidate list for one field. Reused by `prefill()` and `use_provider()`.
- `_write_provider_provenance(db, uid, field_name, provider_slug)` — UPSERT `'provider_<slug>'` row. PG-only.
- `_write_manual_override_provenance(db, uid, field_name)` — UPSERT `'manual_override'` row. PG-only.

Could have unified the two write helpers into one taking a `source` string; chose two for clarity of call sites. The cost is ~10 duplicate lines of SQL; the win is grep-ability (`_write_provider_provenance` immediately tells the reader what's being written).

### 3.3 Template: real buttons + clear-override link (`templates/onboarding/prefill.html`)

**Action button replacement.** PR7's two disabled `<button type="button">` stubs become two real `<form method="post">` blocks:

```html
<form method="post" action="{{ url_for('onboarding.use_provider', field=f.name) }}">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit" class="btn btn-sm btn-primary">
    Use {{ f.candidates[0].provider_label }} value
  </button>
</form>
{% if f.current_value is not none %}
<form method="post" action="{{ url_for('onboarding.keep_current', field=f.name) }}">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit" class="btn btn-sm btn-outline-secondary">Keep current</button>
</form>
{% endif %}
```

`[Use provider value]` now names the winning candidate's provider in the label ("Use COROS value", "Use Polar value") — makes it explicit which provider's data is being applied when multiple are connected.

`[Keep current]` only renders when there's a value to keep. Hides cleanly for empty fields where the action has no semantic — confirmed with Andy as the cleanest UX.

**v5 §A.2.6 clear-override inline link.** New form inside the "Currently stored" `<dd>`, beneath the provenance badge, surfaces only when `f.provenance.source == 'manual_override'` AND `f.candidates` is non-empty:

```html
{% if f.provenance and f.provenance.source == 'manual_override' and f.candidates %}
  <div class="mt-1">
    <form method="post" action="{{ url_for('onboarding.use_provider', field=f.name) }}">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" class="btn btn-link btn-sm p-0 text-decoration-underline align-baseline">
        Use {{ f.candidates[0].provider_label }} value
        ({{ f.candidates[0].value }} {{ f.unit }}{% if f.candidates[0].synced_at %}, as of {{ f.candidates[0].synced_at|string }}{% endif %})
        instead
      </button>
    </form>
  </div>
{% endif %}
```

Renders as an inline-style link button. Inline rather than a Bootstrap popover with JS (confirmed with Andy) — keeps the page CSP-nonce-free + matches PR7's no-JS posture. Posts to the same `use_provider` endpoint — one write path, two UI entry points.

**Provenance badge cosmetics.** PR7's badge for `'provider_<slug>'` source rendered `f.provenance.source[9:]` — raw lowercase slug ("From coros"). PR8 swaps to `provider_label(slug)` ("From COROS") using the `CONNECTION_PROVIDERS` label registry. The `provider_label` Python function is exposed to the template via `render_template(..., provider_label=provider_label)` in `prefill()`.

### 3.4 Field-name validation: app-level only

PR7 §5.1 mentioned the choice between schema CHECK constraint and app-level validation. PR8 ships app-level only, on three grounds:

1. **Single source of truth.** `KNOWN_PROFILE_FIELDS` is the registry; a CHECK constraint duplicates it in the schema (and would drift if the registry grows without a migration).
2. **No schema migration.** PR8 ships zero `init_db.py` edits. Less risk of migration-on-Neon surprises.
3. **Enforcement layered correctly.** `_lookup_field` 404s on the route (write path), `PREFILL_ELIGIBLE_FIELDS` guards `_record_self_report_provenance` (profile-form save path). Both are app-level reads of the same registry. The free-text TEXT column in PG tolerates stale or out-of-registry rows (renders fall back to displaying the raw source string per the badge fallback `{% else %}{{ f.provenance.source }}{% endif %}`) — graceful degradation rather than DB-level rejection.

If a future PR finds athlete-facing field_name corruption (e.g. someone manually editing rows on Neon), a CHECK constraint can be added then. For now, app-level is sufficient.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| `routes/profile.py` + `routes/onboarding.py` AST-parse clean | `ast.parse` over each | ✅ Verified |
| `templates/onboarding/prefill.html` Jinja parses cleanly | `Environment.parse()` | ✅ Verified |
| Source-flip logic conforms to v5 §A.2.3 across all 5 prior-source cases | Inline 5-case test | ✅ Verified — `(None, 'self_report', 'provider_coros', 'provider_polar', 'manual_override')` map to `('self_report', 'self_report', 'manual_override', 'manual_override', 'manual_override')` exactly |
| `routes/onboarding.py` has 2 new POST routes (`/prefill/<field>/use-provider`, `/prefill/<field>/keep-current`) + 4 new helpers (`_lookup_field`, `_resolve_candidates`, `_write_provider_provenance`, `_write_manual_override_provenance`) | grep | ✅ Verified |
| `routes/onboarding.py` imports `abort` and `upsert_athlete_profile` | grep | ✅ Verified |
| Stub render variant A (populated, mixed provenance — including `'manual_override'` with live candidate triggering the clear-override link): all 11 anchors present | inline Jinja render | ✅ Verified — "Use COROS value" button label, "Use Polar value" clear-override link, "Keep current" button, "Self-reported" / "Manually set" / "From COROS" badges, "/stub/onboarding.use_provider/field=hrmax_bpm" + "/stub/onboarding.keep_current/field=hrmax_bpm" form actions, "Continue to profile" link |
| Stub render variant B (empty state, `connected_count=0`): "No providers connected yet" alert renders; no action buttons surface | inline render | ✅ Verified |
| Stub render variant C (providers connected, no candidates anywhere): "have not synced enough data yet" copy + no action buttons | inline render | ✅ Verified |
| `Project_Backlog_v20.md` exists; v19 archived to predecessor block; D-50 row narrative + status cell + Notes column updated per PR7 §5.4 mechanical spec | grep + visual | ✅ Verified |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads `Project_Backlog_v20.md` | grep | ✅ Verified |
| Flask not installed in sandbox — full app import not exercisable | python3 import check | ⚠️ Same gap as PR1–PR7. Live `/onboarding/prefill` apply/keep/clear-override round-trips + source-flip on profile-form save + 404 on bogus field name owed at deploy time |

No drift between this handoff's narrative and on-disk state.

The same "can't exec the Flask app without Flask" gap PR1–PR7 flagged applies. AST + Jinja parse + 3-variant stub render + 5-case source-flip unit-test-style exercise are the offline guards. The PR8 §5.0 live-checks below are mandatory before this PR is "real."

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR8 reaches production)

PR8 ships zero schema changes + 2 new POST endpoints + 1 helper refactor. The risky bits are (a) the source-flip refactor in `_record_self_report_provenance` (touches the existing PR6/PR7 happy path) and (b) the new POST handlers correctly writing the right `source` string in the right state.

1. **Schema is unchanged.** No migration to verify. Spot-check `\d athlete_profile_field_provenance` on Neon shows no new columns.
2. **`/onboarding/prefill` page render (populated with HRmax candidate).** As Andy (COROS connected, ≥1 `cardio_log` row with `coros_label_id IS NOT NULL` + `max_hr IS NOT NULL` + `date >= today - 90`). Open `/onboarding/prefill`. Expect:
   - HRmax card shows `[Use COROS value]` (real button, not disabled) + `[Keep current]` (only if a current value is already stored).
   - Card has no JS — both forms POST through plain HTML.
3. **Apply round-trip: `[Use COROS value]`.** Click the button. Expect:
   - Flash: `Maximum heart rate (HRmax) set from COROS.`
   - Page reloads to `/onboarding/prefill`.
   - HRmax card "Currently stored" cell now shows the COROS-derived value + "From COROS" badge.
   - `psql`: `SELECT * FROM athlete_profile_field_provenance WHERE user_id=<andys-uid> AND field_name='hrmax_bpm'` returns one row with `source='provider_coros'` + `last_updated_at` recent.
   - `psql`: `SELECT hrmax_bpm FROM athlete_profile WHERE user_id=<andys-uid>` matches the COROS-derived value.
4. **Keep round-trip: `[Keep current]`.** After step 3 (HRmax is now `'provider_coros'` source), click `[Keep current]`. Expect:
   - Flash: `Maximum heart rate (HRmax) marked as manually set…`
   - Page reloads.
   - HRmax card now shows the same value + "Manually set" badge.
   - Beneath the badge: inline link `Use COROS value (188 bpm, as of 2026-05-12) instead`.
   - `psql`: provenance row `source='manual_override'` + bumped `last_updated_at`.
   - `athlete_profile.hrmax_bpm` unchanged from step 3.
5. **Clear-override round-trip: inline "Use COROS value instead" link.** Click the inline link beneath the "Manually set" badge. Expect:
   - Same flash + outcome as step 3 (one write path, two UI entry points).
   - Provenance source flips back to `'provider_coros'`.
6. **Source-flip from profile form.** After step 5 (HRmax is `'provider_coros'`), go to `/profile?tab=athlete`. Edit the HRmax value to something different (e.g. type 190). Save. Expect:
   - Flash: `Profile saved.`
   - `psql`: provenance row `source='manual_override'` (flipped from `'provider_coros'`) + bumped `last_updated_at`. `athlete_profile.hrmax_bpm = 190`.
   - Open `/onboarding/prefill` — HRmax card shows "Manually set" badge + the inline clear-override link to switch back to COROS.
7. **Empty-state `[Keep current]` defensive guard.** Visit `/onboarding/prefill` as an athlete with a brand-new profile (all 5 fields empty) + at least one provider connected with HRmax candidate. The `[Keep current]` button should NOT render on the HRmax card (no current value). A crafted `curl -X POST` to `/onboarding/prefill/hrmax_bpm/keep-current` should flash a warning and not write anything.
8. **404 on bogus field name.** `curl -X POST -i .../onboarding/prefill/notarealfield/use-provider` → `404 Not Found`. Same for `keep-current`.
9. **CSRF rejection.** `curl -X POST .../onboarding/prefill/hrmax_bpm/use-provider` without the CSRF token → 400 (Flask-WTF CSRFError surface, same as the existing profile form).
10. **Independent of PR8:** PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 + PR6 §5.0 + PR7 §5.0 are still owed if not yet completed.

### 5.1 PR9+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR8_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR7_Closing_Handoff_v1.md` (predecessor).
4. `aidstation-sources/Project_Backlog_v20.md` — current; PR9 may need to bump to v21 (see §5.4).
5. Domain spec for the picked candidate (e.g. v5 §A.2.5 + §A.2.7 for D2c; `Onboarding_D59_Design_v1.md` for D3; `Onboarding_D58_Design_v1.md` §6 for E).

D-50's frontend bucket — D1 + D2a + D2b — is now complete. The remaining work is independent of `/onboarding/prefill` mechanics.

#### Option E — 14-day connect-provider nudge background job (recommended next)

Carries forward unchanged from PR7 §5.1 / PR8 §5.1. Now the highest-priority remaining v5 onboarding gap with D2 closed. Scope:

- **Background job** that scans `users` for accounts older than 14 days with zero `provider_auth.status='active'` rows AND no `account_nudges` row of `nudge_type='connect_provider_14d'`. For each, inserts an `account_nudges` row + flips a server-side flag the next page render reads.
- **Passive in-app banner** triggered by the flag: "AIDSTATION works best with a fitness provider connected. Want to set one up?" Dismissable (writes `account_nudges.dismissed_at`). One-shot — no further escalation.
- **Deep-link target:** `/onboarding/connect` (PR5's screen).
- **Cron host decision** (Stop-and-ask trigger #8, if Vercel Cron + TrueNAS scheduled task + in-app scheduler diverge meaningfully): probably Vercel Cron since production is on Vercel; lightweight, no new infra.

Estimate: 3-4 files (`routes/nudges.py` new, `templates/_account_nudges.html` new partial, `init_db.py` no-op since `account_nudges` exists from PR1, plus a `templates/base.html` slot for the banner). Under ceiling.

#### Option D3 — Locale-creation flow with Mapbox chain detection

Carries forward unchanged. Independent of D2 / E / D-51 work. Larger PR (touches `chain_registry.py`, new locale-creation routes, Mapbox API client, locale UI).

#### Option D2c — Bulk "Apply all" + tolerance-based re-prefill

Split out from PR8 to stay under ceiling. Scope:

- **`POST /onboarding/prefill/apply-all`** — applies winning candidates for every field with one candidate. Single transaction. Skips fields with `'manual_override'` source (don't override the override).
- **Tolerance-based re-prefill (v5 §A.2.7)** — provider sync delivering a value within tolerance of stored is silent; outside tolerance surfaces as `account_nudges` row (`nudge_type='provider_value_changed'`). Per-field tolerance values in a new module-level constant (v5 spec says implementation-config, not spec-pinned).

Lands when athletes actually need bulk apply. Today's per-field-only is fine for the 1-test-athlete state.

#### Option F — Polar refresh-on-401

Carries forward unchanged. Watch item only.

#### Option H — Provider blueprint roster expansion

Carries forward unchanged. Opportunistic per-provider PRs as integration partners come online (Wahoo / Strava / Whoop / TrainingPeaks / Zwift / RWGPS).

### 5.2 Recommended sequence (revised post-PR8)

**E → D3**, with **F** as a watch item and **D2c** picked up if athletes find per-field-only too tedious; **H** providers as opportunistic adds whenever an integration partner is ready.

E is the next obvious step — the v5 onboarding "connect a provider or you're missing value" passive nudge is the last unshipped onboarding mechanic. After E, the v5 onboarding flow is fully wired end-to-end.

### 5.3 Standing items not on the critical path (carried from PR7 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged. Independent.
- **D-54 SQLite collapse** — unchanged. Catalog Migration Phase 5.
- **D-55 Garmin onto `provider_auth`** — paused.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. PR8 doesn't touch the webhook path.
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — *closed by PR7*. Stays closed.
- **DATABASE.md update** — unchanged.
- **PROVIDERS_SCHEMA.md update** — unchanged.
- **Manual-override flip** — *closed by PR8* (the source-flip refactor in `_record_self_report_provenance`). Removed from carry-forward.
- **`PREFILL_ELIGIBLE_FIELDS` placement in `athlete.py`** — resolved per PR7. Stays as carry-over note only.
- **`field_name` CHECK constraint on `athlete_profile_field_provenance`** (carry-over from PR7) — PR8 ships app-level validation instead, deliberately. CHECK constraint remains an option if athlete-facing field_name corruption ever surfaces. Documented in §3.4 above + §6 honest flags. Removed from carry-forward (decision made, not deferred).
- **Provenance-row deletion on field clear** (carry-over from PR6) — *unchanged*. v5 §A.2.3 row 2 ("Athlete clears a prefilled field → source flips to manual_override; value becomes empty") is partially addressed by PR8's source-flip refactor (if the prior source was `'provider_*'` and the athlete saves an empty value, the row is left as-is in PR8 because `_record_self_report_provenance` skips `None` values). The "flip to manual_override on clear" semantic isn't wired today — would require a separate write path that runs even for None values. Tactically: clearing a field today preserves the old `'provider_*'` provenance row (slightly wrong per spec but not user-visible because the field renders as "Not set" and the badge doesn't surface for empty values). Documented for visibility; tractable in a future small-scope PR.
- **Unused `_POST_STEP2_TARGET` alias** (carry-over from PR7) — unchanged. Cosmetic; doesn't block anything.
- **Per-field "from {provider}, {age}" tag** (carry-over from PR7) — PR8's button label is `Use {provider} value` and the candidate row shows synced_at separately; v5 §A.2.2 step 3's inline tag form is still slightly divergent. PR8 calls it out as "intentionally split into a value line + a synced_at line" for legibility on small cards. Functional, spec-narrative-divergent on phrasing only. Documented in §6.
- **No "Apply all" affordance** — *now Option D2c on the candidate menu*. Removed from informal flags.
- **Tolerance-based suppression** — *now Option D2c on the candidate menu*. Removed from informal flags.

### 5.4 Backlog row update (next PR's first action)

PR8 bumped v19→v20 (this revision). PR9 will need to bump v20→v21 if and only if it lands a state-changing event (e.g. E ships → D-50 row notes update; would acknowledge nudge job in flight or shipped).

**For PR9, owed v20 → v21 bump (mechanically-applicable per Rule #11):**

1. Copy `aidstation-sources/Project_Backlog_v20.md` to `aidstation-sources/Project_Backlog_v21.md`.
2. **Replace** the file-revision header on line 5:
   - Old text:
     ```
     **File revision:** v20 — 2026-05-15 (D-50 row status flip catching up PR8: D-50 status cell now reads 🟢 PR1 + PR2 + PR3 + PR4 + PR5 + PR6 + PR7 + PR8 shipped 2026-05-14/15 (commits `3628ca6`, `686bb40`, `b819f0a`, `f4d2e75` PR4-merge, `34637d2` PR5-merge, `2c8d01f` PR6-merge, `df17f08` PR7-merge, `<PR8-merge-pending>`); 🟢 frontend D1 (Step-2 connect) + D2a (read-side prefill UX) + D2b (write-side prefill UX) shipped — PR8 wires `[Use provider value]` / `[Keep current]` POST handlers at `/onboarding/prefill/<field>/use-provider` and `/keep-current`, refactors `routes/profile.py:_record_self_report_provenance` for the `'provider_*'` → `'manual_override'` source-flip per v5 §A.2.3, and ships the inline "Use {provider} value instead" clear-override link beneath `'manual_override'` badges per v5 §A.2.6 per `V5_Implementation_PR8_Closing_Handoff_v1.md`. Field-name validation is registry-driven (app-level guard inside `_record_self_report_provenance` + per-route `_lookup_field` 404 — `KNOWN_PROFILE_FIELDS` stays the single source of truth; no schema CHECK migration). No new D-row work this revision — pure status tracking)
     ```
   - New text (assuming PR9 = E):
     ```
     **File revision:** v21 — 2026-05-1X (D-50 row status flip catching up PR9: D-50 status cell now reads 🟢 PR1–PR9 shipped 2026-05-14/15/1X (commits …, `<PR8-merge>`, `<PR9-merge>`); 🟢 E 14-day connect-provider nudge background job shipped PR9 — `account_nudges` writer + dismissable in-app banner + deep-link to `/onboarding/connect` per `V5_Implementation_PR9_Closing_Handoff_v1.md`. No new D-row work this revision — pure status tracking)
     ```
3. **Prepend** to the predecessor revisions block:
   ```
   - v20 — 2026-05-15 (D-50 row status flip catching up PR8: …)  [verbatim from current v20 line 5 narrative]
   ```
4. **Update** the D-50 row status cell from PR1–PR8 → PR1–PR9 shipped, mark E as shipped, leave D3/F/H pending. Update Notes column "PR9+ candidate menu" → "PR10+ candidate menu" and shift the E entry from pending → shipped.
5. **Bump** `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line from `Project_Backlog_v20.md` to `Project_Backlog_v21.md`.

**If PR9 is something other than E**, the narrative text changes but the file mechanics are identical (copy → header replace → predecessor prepend → D-50 row update → CLAUDE.md bump). Write the v21 header narrative to reflect what actually shipped.

---

## 6. Open items / honest flags

- **No live page-render verification.** Same risk class as PR1–PR7. Flask isn't installed in the sandbox. AST-parse + Jinja-parse + stub-render across three template variants + 5-case offline source-flip exercise confirmed the wiring + state-machine correctness. The PR8 §5.0 manual click-through is mandatory before this is real.
- **Clearing a field on the profile form doesn't flip `'provider_*'` → `'manual_override'`.** v5 §A.2.3 row 2 says "Athlete clears a prefilled field → source flips to manual_override; value becomes empty." PR8's source-flip refactor only runs through fields with non-None values (the `if value is None: continue` guard). So clearing a `'provider_coros'`-sourced field today nulls the athlete_profile value but leaves the `'provider_coros'` provenance row intact. Tactically: the prefill page renders `'Not set'` for the empty value and doesn't surface the badge for missing current values, so the wrong row doesn't show up in the UI. But it IS technically off-spec. Tractable in a small-scope future PR (rewrite the `value is None` guard to keep the row-write for the clear-and-flip case). Documented in §5.3 carry-forward.
- **`[Keep current]` writes `'manual_override'` even if prior source was `'self_report'`.** Semantic stretch: v5 §A.2.3 row 2 only talks about flipping `'provider_*'` to `'manual_override'`. PR8's `_write_manual_override_provenance` writes unconditionally. For prior `'self_report'`, the effect is "athlete affirms current value as manually-set and explicitly suppresses future provider re-prefill." This is the right semantic for the prefill-page Keep button (the athlete is making a deliberate non-edit decision), but it's a small spec stretch — v5 §A.2 doesn't explicitly cover the "I have a self-reported value, please don't auto-prefill" pathway. Defensible: the athlete clicked Keep on a page that shows provider candidates, so the intent is explicit override. Flagged for transparency.
- **`use_provider` re-extracts at write time; consumes a small DB read.** A provider that disconnected between page render and form POST would result in zero candidates → flash warning + redirect. The alternative (trusting a hidden form value) avoids the re-read but is open to stale-tab and tampering risk. The re-read is the right trade.
- **Source-flip helper does a full provenance-table SELECT per save.** Reads all rows for the user even if only one field changed. For a 5-row table per user this is fine. If `athlete_profile_field_provenance` grows to 100+ rows per user (e.g. D-51's larger §A–§L field-by-field expansion), the SELECT could be scoped to just the fields being written. Not a perf concern today; flagged for future scaling consideration.
- **No tests added.** Inline `python3` exercises for Jinja stub-render + AST parse + 5-case source-flip rule check + 3-variant template render were the offline guards. Same framing as PR1–PR7: a real `tests/` directory still doesn't exist. PR8's source-flip refactor is genuinely the first PR where unit tests would deliver clearly higher value than inline exercises (the state machine has edge cases worth pinning), but committing to a `tests/` infrastructure here is overage for this PR's scope. Carries forward as a flag for D2c or E.
- **3 substantive code files + 2 bookkeeping (v20 + CLAUDE.md) + 1 handoff = 6 total.** Under the 5-substantive ceiling. Headroom came from PR7 having pre-built the registry + extractor scaffolding — PR8 is mostly writes + one source-flip refactor + a template edit.
- **`f.candidates[0]` for the winning candidate is the most-recent-synced one.** v5 §A.2.2 step 4 says "Surface divergence (when present). If a non-winning candidate's value differs from the winning value by more than the field-specific tolerance, append '; {alt-provider}: {alt-value}' to the tag." PR8's template renders all candidates as separate `<dt>/<dd>` rows but doesn't append the divergence-tag to the winner's display. Functionally equivalent (the athlete sees both values), spec-narrative-divergent (the inline tag form is more compact). Cosmetic tweak for D2c if Andy wants it.
- **Confirmation dialogs on `[Use provider value]` for derived extractors.** PR7 §6 flagged: HRmax derived from `cardio_log.max_hr` may undershoot true HRmax if the athlete hasn't pushed hard in 90 days. PR8 doesn't add a confirmation guard — the button just writes the value. The extractor `note` ("Max heart-rate observed across the last 90 days of activity data.") is visible beneath the candidate value, which is some communication of the derived-ness. If athletes hit this and complain about saving an under-estimate, D2c can add a `confirm()` step or a "this is derived, not lab-measured" interstitial. Flagged for transparency.

---

## 7. Gut check

**What this session got right.**

- **Closed the v5 §A.2 prefill loop.** PR6 added the columns; PR7 shipped the read side; PR8 shipped the write side. The user-visible promise from PR4 and PR5 ("Connected providers will auto-populate these in a future release") is now real for the HRmax field, and the foundation is in place for the other 4 fields when their extractors ship.
- **App-level validation chose registry over schema.** Adding a CHECK constraint would have duplicated `KNOWN_PROFILE_FIELDS` in two places. Picking app-level keeps the registry as the single source of truth and avoids a schema migration. Documented the reasoning explicitly so a future contributor doesn't need to re-derive it.
- **Source-flip rule is small + well-tested offline.** Three-branch decision tree with 5 prior-source cases covered. Each case has its own one-line outcome. The state machine is small enough that the offline 5-case exercise is meaningful coverage.
- **Re-resolves candidates at write time.** Stale-tab + tampering resistance. The form only carries a CSRF token + the field name; the value to write is determined from the provider's current data, not from form fields.
- **Came in well under the ceiling.** 3 substantive code files (vs 5-file ceiling). All three concentrate on a tight scope — the helper refactor + 2 route additions + the template wiring — with no scope creep into adjacent code surfaces.
- **Honest "no current value" UX.** Hiding `[Keep current]` on empty fields removes a no-op button that would have been visually confusing. The empty case naturally encourages the athlete to either click `[Use provider value]` or scroll past to the profile form.

**Risks.**

- **The source-flip refactor touches the existing PR6/PR7 happy path.** A regression in `_record_self_report_provenance` would silently corrupt provenance on every profile save. The 5-case offline exercise gives confidence in the state-machine logic; the PR8 §5.0 step 6 spot-check (edit a `'provider_coros'`-sourced field via the profile form, verify `source='manual_override'` on Neon) is the integration-level guard.
- **`[Keep current]` writes `'manual_override'` even for prior `'self_report'`.** Defensible per §6 above (athlete explicitly chose Keep on a page that surfaced a provider candidate, so the override intent is unambiguous) — but it does mean a previously-self-reported value gets a `'manual_override'` source if the athlete clicks Keep. Athletes who don't notice the difference are fine; athletes who scrutinise the badge see a "Manually set" tag that's slightly more pointed than "Self-reported." Cosmetic concern; the suppress-future-prefill semantic is what matters.
- **No retry/idempotency story for the apply endpoint.** A double-click on `[Use provider value]` will fire two POSTs. The second write is idempotent at the DB level (UPSERT) but produces two flash messages and two redirects. Functionally fine; visually slightly noisy in the rare double-click case. Not worth a debounce JS layer at this scale.

**What might be missing.**

- **Per-field comparison tag with divergence.** v5 §A.2.2 step 4 specifies appending `; {alt-provider}: {alt-value}` to the winning value's tag if the divergence exceeds tolerance. PR8 doesn't compute divergence (no tolerance values defined yet — those are D2c domain). The fallback (render every candidate as its own row) is functionally equivalent but more visually busy than the spec's compact tag form.
- **No "I changed my mind, undo my last apply" path.** Once an athlete clicks `[Use provider value]`, the previous value is overwritten. Could surface a flash with "Undo" link that restores the prior value, but that requires snapshotting the prior value in the flash session. Out of PR8 scope; not requested by Andy; tractable in D2c if desired.
- **No batch `[Apply all]` button.** Per Andy's response and per the candidate-menu split, D2c picks this up if needed. Today's per-field UX is good for 5 fields; would feel tedious for 20+ fields once D-51's broader scope ships.
- **The clear-override inline link doesn't preview the field-specific note** ("Max heart-rate observed across the last 90 days of activity data."). It shows value + unit + synced_at but not the derivation note. Athletes who see "Use COROS value (188 bpm, as of 2026-05-12) instead" don't see the caveat that this is a recent-activity-max, not a lab measurement. The full note is visible elsewhere on the card (under the candidate row), so it's not hidden — just not in the link itself. Spec-narrative says "popover with 'Use Polar value (78.2 kg, last synced 2 days ago) instead.'" — same level of detail. Acceptable.

**Best argument against this session's scope.**

PR8 ships D2b's write path but uses provider-derived data for only one field today (HRmax). Athletes with COROS or Polar connected get one usable prefill option; the other 4 fields' buttons (if they had candidates, which they don't until wellness-ingest or Wahoo ships) would behave identically. So PR8's *immediate* user-visible win is narrow: HRmax prefill for ~1 athlete (Andy).

Counter: the source-flip refactor and the clear-override path are the v5 §A.2 spec's load-bearing semantics. They have to work before any future extractor (body weight, VO2max, sleep, etc.) can light up — otherwise the new extractors would surface candidates but the override mechanics would be broken. PR8's value is the foundation for every future provider-prefill addition, not the HRmax field alone.

Counter to the counter: shipping the foundation when only 1 of 5 fields exercises it means the foundation is under-tested in production. The first provider-prefill addition that actually delivers data for one of the 4 stub fields will be the real test. Mitigation: PR8 §5.0 step 6 manually exercises the source-flip via the profile form against the HRmax field, which is the same code path the future fields will use.

---

## 8. Forward pointers

- **Next session:** PR9 = Option E (14-day connect-provider nudge background job, recommended) or any of the other PR7/PR8 §5.1 carry-forward candidates. PR8 closes the v5 §A.2 prefill loop; E ships the v5 §A.2.4 no-providers-connected nudge — the last unshipped onboarding mechanic.
- **Before next code lands:** PR8 §5.0 spot-check on the deployed app (`/onboarding/prefill` apply/keep/clear-override round-trips + profile-form source-flip + 404 on bogus field name + CSRF rejection). PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 + PR6 §5.0 + PR7 §5.0 are still owed if not yet completed.
- **First action of next session:** Rule #9 reconciliation. Specifically: confirm PR8 commit landed on `claude/v5-implementation-handoff-VXveb` (or merged to main with its own merge commit); confirm `routes/profile.py:_record_self_report_provenance` has the 3-branch source-flip decision tree; confirm `routes/onboarding.py` has the 2 new POST routes (`/prefill/<field>/use-provider`, `/prefill/<field>/keep-current`) + 4 new helpers; confirm `templates/onboarding/prefill.html` has the real action button forms + the inline clear-override link; confirm `Project_Backlog_v20.md` exists with v19 archived to predecessor block + D-50 row reflects PR8 shipped; confirm `CLAUDE.md` "Authoritative current files" backlog line reads v20.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **PR8 has one deferred mechanical edit:** the v20 → v21 backlog bump for PR9's first action, spec'd verbatim in §5.4
- #12 numeric version suffixes (backlog now at v20; v21 lands in PR9 per §5.4)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR8 closing handoff. v5 onboarding D2b (write-side prefill UX) shipped: `[Use provider value]` + `[Keep current]` POST handlers at `/onboarding/prefill/<field>/use-provider` and `/keep-current` (re-resolves candidates at write time, app-level field-name validation via `_lookup_field` 404 + `PREFILL_ELIGIBLE_FIELDS` guard), refactor of `_record_self_report_provenance` to flip `'provider_*'` → `'manual_override'` per v5 §A.2.3 source-flip stickiness, inline "Use {provider} value instead" clear-override link beneath `'manual_override'` badges per v5 §A.2.6 (no JS — matches PR7's no-CSP-nonce-needed posture). Closes the v5 §A.2 prefill loop. Backlog bumped v19 → v20. Next: Andy's choice among PR9 candidates in §5.1 (E recommended — 14-day connect-provider nudge, last unshipped v5 onboarding mechanic); v20 → v21 backlog bump mechanically spec'd for PR9's first action.*
