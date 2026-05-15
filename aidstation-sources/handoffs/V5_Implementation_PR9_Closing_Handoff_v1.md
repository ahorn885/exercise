# V5 Onboarding Implementation PR9 — Closing Handoff

**Session:** Ninth substantive code session of the v5 onboarding implementation arc. Executes PR8 §5.1's recommended next — **Option E (14-day connect-provider nudge background job)** — closing the last unshipped v5 §A.2.4 onboarding mechanic. Ships a new `routes/nudges.py` blueprint with a token-gated Vercel-Cron-driven scanner (`GET /cron/nudges/connect_provider_14d`) + a per-user dismiss handler (`POST /nudges/<id>/dismiss`), plus a dismissable in-app banner (`templates/_account_nudges.html`) slotted into `templates/base.html` via an `active_nudges` context processor. Flips v20→v21 backlog per PR8 §5.4 mechanical spec.
**Date:** 2026-05-15
**Predecessor handoff:** `V5_Implementation_PR8_Closing_Handoff_v1.md` (its §5.1 Option E is exactly what this session executes; its §5.4 v20→v21 backlog bump runs here per Rule #11 mechanical spec).
**Branch:** `claude/v5-implementation-handoff-UqIvn` (per-session feature branch off `main`; PR8 was merged into `main` as `43ccedf` via PR #40 before this session started).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 live cron round-trip + banner render + dismiss round-trip + 401 on missing auth + Vercel `CRON_SECRET` env-var setup owed at deploy time (no Flask in sandbox, same gap as PR1–PR8).
**Time-on-task:** Single chat. Substantive files: **5** (`routes/nudges.py` new, `templates/_account_nudges.html` new, `templates/base.html` 1-line include, `app.py` +import +blueprint +auth-exempt +context-processor, `vercel.json` +crons array). Plus the v20→v21 backlog bump (`Project_Backlog_v21.md` new copy + 1-line `CLAUDE.md` edit) and this handoff = 7 total. At the substantive-file ceiling.

---

## 1. Session-start verification (Rule #9)

Verified the PR8 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/v5-implementation-handoff-UqIvn` clean off post-PR8 `main`; PR8 merged to `main` as `43ccedf` via PR #40 (PR8 commit `8b2e1dc`) | `git status` + `git log --oneline -15` | ✅ Verified |
| `routes/onboarding.py` has 2 new POST routes (`use_provider`, `keep_current`) + 4 new helpers (`_lookup_field`, `_resolve_candidates`, `_write_provider_provenance`, `_write_manual_override_provenance`) | grep | ✅ Verified (helpers at L138-205; routes at L265 + L305) |
| `routes/profile.py:_record_self_report_provenance` has 3-branch source-flip (None/self_report → 'self_report', 'provider_*' / 'manual_override' → 'manual_override') | grep | ✅ Verified (L112-156) |
| `templates/onboarding/prefill.html` has real action button forms + inline clear-override link | grep | ✅ Verified |
| `Project_Backlog_v20.md` exists with v19 archived to predecessor block; `CLAUDE.md` "Authoritative current files" backlog line reads v20 | grep | ✅ Verified |
| `account_nudges` table exists in `_PG_MIGRATIONS` with the right shape (`UNIQUE (user_id, nudge_type)` + nullable `dismissed_at`) | `init_db.py:1833-1841` | ✅ Verified — no schema change needed for PR9 |
| `vercel.json` is minimal (no existing `crons`) | cat | ✅ Verified |
| No existing scheduler/cron infrastructure in the repo (APScheduler / crontab / etc.) | find / grep | ✅ Verified — clean slate for the cron-host decision |

**No drift between PR8 handoff narrative and on-disk state.**

Stop-and-ask trigger #8 (cron host) resolved up front: Andy picked **Vercel Cron** over TrueNAS scheduled task and APScheduler in-process. Rationale: production is on Vercel; declarative cron in `vercel.json` is one file diff; idempotent scanner means re-runs are harmless if both Vercel and TrueNAS end up hitting the endpoint; APScheduler is fragile on serverless (cold-start scheduler state doesn't survive function teardown) and would mean Vercel can't run nudges at all.

---

## 2. Files shipped this turn

All on branch `claude/v5-implementation-handoff-UqIvn`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `routes/nudges.py` | New (~150 lines) | New blueprint with three public surfaces: (a) `NUDGE_REGISTRY` keyed by `nudge_type` → message/cta_label/cta_endpoint/category; one entry today (`'connect_provider_14d'`), structured for easy expansion. (b) `get_active_nudges(db, uid)` — public helper imported by `app.py`'s context processor; SELECT against `account_nudges WHERE user_id = ? AND dismissed_at IS NULL ORDER BY created_at DESC`, registry-decorated; PG-only (returns [] on SQLite or for logged-out uid). Unknown nudge_types fall back to the raw `nudge_type` as message so a writer that lands a new type before the registry catches up produces an ugly-but-visible banner rather than a silent miss. (c) `_cron_authorized()` — `hmac.compare_digest` check on `Authorization: Bearer $CRON_SECRET`; fails closed when `CRON_SECRET` env var is unset. (d) `GET /cron/nudges/connect_provider_14d` route — single `INSERT INTO account_nudges (user_id, nudge_type) SELECT u.id, 'connect_provider_14d' FROM users u WHERE (u.created_at IS NULL OR u.created_at <= NOW() - INTERVAL '14 days') AND NOT EXISTS (active provider_auth) AND NOT EXISTS (prior nudge row) ON CONFLICT DO NOTHING RETURNING id`. Returns JSON `{inserted: N}`. PG-only; SQLite dev returns `{inserted: 0, note: '…'}` so local probes don't 500. NULL `users.created_at` (legacy rows pre-dating the DEFAULT NOW() column) counts as old enough — safer than skipping silently. (e) `POST /nudges/<int:nudge_id>/dismiss` route — `UPDATE account_nudges SET dismissed_at = NOW() WHERE id = ? AND user_id = ?`; scoped to current_user_id so a crafted POST against another athlete's nudge_id is a no-op. Redirects to `request.referrer` (banner can appear on any page) with a dashboard fallback. |
| 2 | `templates/_account_nudges.html` | New (~25 lines) | Partial that renders one `<div class="alert alert-…">` per `active_nudges` entry. Banner has 3 elements: message text + optional `alert-link` CTA (when both `cta_label` and `cta_endpoint` are set) + dismiss `<form method="post">` styled as Bootstrap's `btn-close`. No JS: dismiss is a real form POST to `/nudges/<id>/dismiss` so the banner survives reloads until DB-dismissed (Bootstrap's `data-bs-dismiss="alert"` would only hide it visually until the next page render). Matches PR5–PR8's no-JS-required posture. Renders nothing when `active_nudges` is empty. |
| 3 | `templates/base.html` | Edit (1-line) | `{% include '_account_nudges.html' %}` inserted between the flash-messages `{% with %}` block and `{% block content %}{% endblock %}`. Banner sits below transient flashes (so a fresh form-submit flash stays the most attention-grabbing) and above the page content (so it's visible without scroll). Empty render is a single Jinja include + no markup, so no visual cost when there are no nudges. |
| 4 | `app.py` | Edit (~25 lines net across 4 spots) | (a) Import `bp as nudges_bp, get_active_nudges` from `routes.nudges`. (b) `app.register_blueprint(nudges_bp)`. (c) `_AUTH_EXEMPT_ENDPOINTS.add('nudges.scan_connect_provider_14d')` — Vercel Cron hits the endpoint with no session cookie; auth is via the bearer token inside the route, so it has to bypass the global `_require_login` gate (same pattern as `coros.webhook` / `polar.webhook` / etc.). The dismiss POST stays on the session-auth path because it needs `current_user_id` for the per-row scoping. (d) New `@app.context_processor _inject_active_nudges` — reads `getattr(g, 'current_user_row', None)`; when present, calls `get_active_nudges(get_db(), user['id'])` and returns `{'active_nudges': […]}`; on exception logs and returns `[]` (same defensive shape as `_inject_current_user`). Logged-out pages skip the SELECT entirely. |
| 5 | `vercel.json` | Edit (+3 lines) | New `"crons": [{ "path": "/cron/nudges/connect_provider_14d", "schedule": "0 14 * * *" }]` array. Daily at 14:00 UTC = 9 AM Central. Vercel Hobby tier allows up to once-per-day; Pro tier allows finer; either way the schedule fits the v5 §A.2.4 "one nudge after 14 days" semantic — daily is plenty. Vercel sends `Authorization: Bearer $CRON_SECRET` automatically when the env var is set in the project. |
| — | `aidstation-sources/Project_Backlog_v21.md` | New (copy of v20 + 4 surgical edits per PR8 §5.4 mechanical spec) | **File revision** header bumped v20→v21 with PR9 narrative (D-50 status flip catching up PR1–PR9; E shipped; PR8-merge placeholder filled with `43ccedf`). **Predecessor revisions** block prepends the v20 entry verbatim. **D-50 description column** updated: PR8's "(this revision)" annotation fixed to "(merge `43ccedf`)"; new "PR9 (this revision):" entry summarising E including the Vercel-Cron path + context processor + base.html slot + `vercel.json` cron entry. **D-50 status cell** rewritten: 🟢 PR1–PR9 shipped; E listed as shipped; D2c/D3/F/H/E-telemetry kept pending; `<PR8-merge-pending>` replaced with `43ccedf`. **D-50 Notes column** rewritten: handoff pointer flipped to `V5_Implementation_PR9_Closing_Handoff_v1.md`; PR9+ → PR10+ candidate menu; E entry removed (shipped), new E-telemetry entry added (Open Item #18 from v5 spec); recommended sequence flipped to "D3, with F as watch item …"; PR9-specific pre-deploy verification block (j-step) appended. |
| — | `aidstation-sources/CLAUDE.md` | Edit (1-line) | Per PR8 §5.4 step 5: "Authoritative current files" backlog line bumped from `Project_Backlog_v20.md` to `Project_Backlog_v21.md`. Single-line edit, same shape as the v19→v20 bump PR8 did. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR9_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `init_db.py` — unchanged. `account_nudges` (PR1's D-58 schema batch) already has the right shape. `UNIQUE (user_id, nudge_type)` makes the cron scanner idempotent. No CHECK constraint on `nudge_type` — the `NUDGE_REGISTRY` is the app-level enforcement layer, same pattern PR8 chose for `field_name`.
- `routes/onboarding.py` — unchanged. PR9's banner deep-links to `/onboarding/connect` (PR5's screen) which already exists. No edits needed.
- `routes/profile.py` / `routes/profile_extractors.py` / `routes/profile_fields.py` — unchanged. PR8's prefill work is orthogonal.
- `routes/coros.py` / `routes/polar.py` / `routes/oauth_callbacks.py` / `routes/provider_auth.py` — zero edits. PR9 reads `provider_auth.status='active'` rowcount but doesn't write provider rows.
- `database.py` — unchanged. Standard `?` placeholder + `_is_postgres()` guard pattern.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1–PR8 used.

---

## 3. What landed

### 3.1 Daily scanner (`routes/nudges.py:scan_connect_provider_14d`)

v5 §A.2.4 spec: "After **14 days** of self-report-only use (measured from account creation) AND zero connected providers, a single passive in-app banner appears … Dismissable. One nudge only — no further escalation. Stored as a row in `account_nudges` with `nudge_type='connect_provider_14d'`."

PR9 implementation: single SQL statement does eligibility filter + INSERT in one round-trip.

```sql
INSERT INTO account_nudges (user_id, nudge_type)
SELECT u.id, 'connect_provider_14d'
FROM users u
WHERE (u.created_at IS NULL OR u.created_at <= NOW() - INTERVAL '14 days')
  AND NOT EXISTS (
      SELECT 1 FROM provider_auth pa
      WHERE pa.user_id = u.id AND pa.status = 'active'
  )
  AND NOT EXISTS (
      SELECT 1 FROM account_nudges an
      WHERE an.user_id = u.id AND an.nudge_type = 'connect_provider_14d'
  )
ON CONFLICT (user_id, nudge_type) DO NOTHING
RETURNING id
```

Three eligibility predicates:

1. **Account age ≥ 14 days.** `users.created_at IS NULL OR created_at <= NOW() - INTERVAL '14 days'`. NULL `created_at` (legacy rows pre-dating the DEFAULT NOW() column) counts as old enough — safer than skipping silently.
2. **Zero active provider connections.** `NOT EXISTS (provider_auth WHERE status = 'active')`. Mirrors the `is_connected` semantic in `routes/profile.py:load_connections` (which checks `status == STATUS_ACTIVE`).
3. **No existing nudge of this type.** `NOT EXISTS (account_nudges WHERE nudge_type = 'connect_provider_14d')` — covers both un-dismissed and already-dismissed rows. One shot ever per spec.

The `ON CONFLICT DO NOTHING` is belt-and-suspenders: the third predicate alone makes the INSERT a no-op for already-nudged users, but a concurrent cron run + ON CONFLICT covers the race window between the SELECT and INSERT.

Returns JSON `{inserted: N}` where N is the count of newly-inserted rows (from `RETURNING id`). PG-only; SQLite dev short-circuits with `{inserted: 0, note: 'SQLite dev: account_nudges is PG-only'}`.

**Auth:** `hmac.compare_digest` against `Authorization: Bearer $CRON_SECRET`. Fails closed when CRON_SECRET is unset (production misconfiguration produces 401, not silent execution). Vercel Cron sends this header automatically once the env var is set in the project.

### 3.2 Dismiss handler (`routes/nudges.py:dismiss`)

```python
@bp.route('/nudges/<int:nudge_id>/dismiss', methods=['POST'])
def dismiss(nudge_id):
    db = get_db()
    uid = current_user_id()
    if database._is_postgres():
        db.execute(
            'UPDATE account_nudges SET dismissed_at = NOW() '
            'WHERE id = ? AND user_id = ?',
            (nudge_id, uid),
        )
        db.commit()
    return redirect(request.referrer or url_for('dashboard.index'))
```

Per-user scoping via the `user_id = ?` predicate — a crafted POST against another athlete's nudge_id (URL has the integer; the form is just a CSRF token) is a no-op. Redirects to `request.referrer` so the banner can appear on any page and dismissing returns the athlete to the same view. Dashboard fallback when no Referer header is set (rare; possible from a direct link or some privacy extensions).

Session-auth path (no exemption in `_AUTH_EXEMPT_ENDPOINTS`). CSRF token in the form is verified by the global Flask-WTF CSRFProtect — same flow as the rest of the app's POST handlers.

### 3.3 Banner partial + base.html slot

`templates/_account_nudges.html`:

```html
{% if active_nudges %}
  {% for n in active_nudges %}
    <div class="alert alert-{{ n.category }} d-flex align-items-center justify-content-between" role="alert">
      <div class="me-3">
        {{ n.message }}
        {% if n.cta_label and n.cta_endpoint %}
          <a href="{{ url_for(n.cta_endpoint) }}" class="alert-link ms-1">{{ n.cta_label }}</a>
        {% endif %}
      </div>
      <form method="post" action="{{ url_for('nudges.dismiss', nudge_id=n.id) }}" class="m-0">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="btn-close" aria-label="Dismiss"></button>
      </form>
    </div>
  {% endfor %}
{% endif %}
```

`{% include '_account_nudges.html' %}` slotted into `templates/base.html` between flashes and `{% block content %}{% endblock %}`. Persistent banner sits below transient flashes (a fresh form-submit flash stays the most attention-grabbing thing on the page) and above the page content (visible without scroll). Empty `active_nudges` renders nothing.

### 3.4 Context processor (`app.py:_inject_active_nudges`)

```python
@app.context_processor
def _inject_active_nudges():
    user = getattr(g, 'current_user_row', None)
    if not user:
        return {'active_nudges': []}
    try:
        return {'active_nudges': get_active_nudges(get_db(), user['id'])}
    except Exception as e:
        print(f'nudges: get_active_nudges failed: {e}')
        return {'active_nudges': []}
```

Reads from `g.current_user_row` (hydrated by `_require_login`) — no extra user query per render. The underlying SELECT is one indexed read (`account_nudges` has the `UNIQUE (user_id, nudge_type)` constraint backing a btree on `(user_id, nudge_type)`; the `dismissed_at IS NULL` filter is in-row). Negligible per-render cost. Exception catch + fallback to `[]` matches the defensive shape of `_inject_current_user` so a nudges-table outage doesn't 500 every page.

### 3.5 `NUDGE_REGISTRY` design

Single entry today; structured for expansion:

```python
NUDGE_REGISTRY = {
    'connect_provider_14d': {
        'message': 'AIDSTATION works best with a fitness provider connected. Want to set one up?',
        'cta_label': 'Connect a provider',
        'cta_endpoint': 'onboarding.connect',
        'category': 'info',
    },
}
```

Adding a new `nudge_type` means (a) adding a registry entry here, (b) wiring a writer somewhere (could be event-driven, not necessarily another cron). The partial reads everything from the registry overlay so it doesn't need to be touched.

`category` maps to Bootstrap's `alert-*` classes — `info` / `warning` / `danger` / `success` / etc. — so each nudge_type can carry its own visual weight without partial changes.

`cta_endpoint` is a Flask endpoint name resolvable by `url_for(...)` — keeps the deep-link target indirect (rename the target route, the registry value stays valid). Both `cta_label` and `cta_endpoint` must be set for the CTA to render — partial guards with `{% if n.cta_label and n.cta_endpoint %}`.

### 3.6 Vercel Cron entry (`vercel.json`)

```json
"crons": [
  { "path": "/cron/nudges/connect_provider_14d", "schedule": "0 14 * * *" }
]
```

Daily at 14:00 UTC = 9 AM Central. Vercel Hobby tier allows up to once-per-day max frequency; Pro allows finer. Daily fits the v5 spec's "14 days" semantic — finer granularity doesn't add value.

Vercel auto-sends `Authorization: Bearer $CRON_SECRET` when the env var is set in the project settings. No additional config in `vercel.json` — the cron config is just the path + schedule.

### 3.7 Auth-exemption surgical edit (`app.py:_AUTH_EXEMPT_ENDPOINTS`)

`'nudges.scan_connect_provider_14d'` added to the set. Same pattern as the COROS / Polar / RWGPS webhook endpoints — global session gate doesn't apply because the request comes from Vercel's cron infrastructure, not a browser. The bearer-token check inside the route is the auth boundary.

The dismiss endpoint stays on the session-auth path (no exemption). It needs `current_user_id` for per-row scoping, and athletes dismiss banners from authed pages anyway.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| `routes/nudges.py` AST-parses clean | `ast.parse` | ✅ Verified |
| `app.py` AST-parses clean after edits | `ast.parse` | ✅ Verified |
| `templates/_account_nudges.html` and `templates/base.html` Jinja-parse cleanly | `Environment.parse()` | ✅ Verified |
| `vercel.json` JSON-parses + has correct `crons` shape | `json.load` + assert | ✅ Verified — `path=/cron/nudges/connect_provider_14d`, `schedule=0 14 * * *` |
| `_cron_authorized` accepts correct token, rejects empty-secret / wrong-scheme / wrong-token / missing-header | Inline 5-case test | ✅ Verified 5/5 |
| `get_active_nudges` returns registry-decorated rows for known type, raw `nudge_type` fallback for unknown type, `[]` for logged-out, `[]` for SQLite dev | Inline 4-case stub | ✅ Verified 4/4 |
| Banner partial renders correctly across 4 variants: (a) one nudge with CTA + dismiss + correct deep-link, (b) empty list → zero markup, (c) unknown type → no CTA link but message + dismiss, (d) multiple nudges → two `alert-info` blocks with distinct dismiss URLs | Inline Jinja render | ✅ Verified 4/4 |
| `app.py` has `'nudges.scan_connect_provider_14d'` in `_AUTH_EXEMPT_ENDPOINTS` | grep | ✅ Verified |
| `app.py` registers `nudges_bp` and imports `get_active_nudges` from `routes.nudges` | grep | ✅ Verified |
| `app.py` has `_inject_active_nudges` context processor | grep | ✅ Verified |
| `templates/base.html` has `{% include '_account_nudges.html' %}` between flashes and content block | grep | ✅ Verified |
| `Project_Backlog_v21.md` exists; v20 archived to predecessor block; D-50 row narrative + status cell + Notes column updated per PR8 §5.4 mechanical spec; PR8-merge placeholder filled with `43ccedf` | grep + visual | ✅ Verified |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads `Project_Backlog_v21.md` | grep | ✅ Verified |
| Flask not installed in sandbox — full app import not exercisable | python3 import check | ⚠️ Same gap as PR1–PR8. Live cron round-trip + banner render + dismiss round-trip + 401-on-no-auth owed at deploy time |

No drift between this handoff's narrative and on-disk state.

The same "can't exec the Flask app without Flask" gap PR1–PR8 flagged applies. AST + Jinja + JSON parse + 5-case auth exercise + 4-case `get_active_nudges` exercise + 4-variant banner render are the offline guards. The PR9 §5.0 live-checks below are mandatory before this PR is "real."

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR9 reaches production)

PR9 ships zero schema changes + 1 new GET endpoint (cron-only) + 1 new POST endpoint (session-only) + 1 banner partial + a `vercel.json` cron entry. The risky bits are (a) the cron auth boundary (token leak / token missing) and (b) the banner showing up on every page render (regression surface across the whole app).

1. **Schema is unchanged.** No migration to verify. `account_nudges` shape unchanged since PR1.
2. **Env var setup.** Generate a random 32+ byte token (e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"`). On Vercel: Project Settings → Environment Variables → add `CRON_SECRET = <token>`. Redeploy. Optional but recommended: same token on TrueNAS via `.env` so manual `curl` works from there.
3. **Vercel Cron registered.** After deploy, Vercel UI → Project → Cron Jobs should list one entry: `/cron/nudges/connect_provider_14d`, `0 14 * * *`. If missing, `vercel.json` didn't deploy correctly — recheck the `crons` block.
4. **Cron auth happy path.** `curl -i -H "Authorization: Bearer $CRON_SECRET" https://aidstation-pro.vercel.app/cron/nudges/connect_provider_14d`. Expect `200 OK` + body `{"inserted": N}` where N is the count of newly-eligible users. (For the one-test-athlete state, Andy has COROS connected, so N=0 — he's not eligible. Manual: temporarily `UPDATE provider_auth SET status='revoked' WHERE user_id=<andys-uid>; curl …; SELECT * FROM account_nudges WHERE user_id=<andys-uid>` should show one new row. Restore status afterwards.)
5. **Cron auth failure paths.** (a) `curl -i https://aidstation-pro.vercel.app/cron/nudges/connect_provider_14d` (no auth header) → 401. (b) `curl -i -H "Authorization: Bearer wrong" …` → 401. (c) `curl -i -H "Authorization: Basic xyz" …` → 401. None of these should write to the DB.
6. **Idempotency.** After step 4 produces N=1 new row, re-run the same `curl`. Expect `{"inserted": 0}` — the third NOT EXISTS predicate skips already-nudged users.
7. **Banner render.** Log in as the test athlete after step 4 (with the nudge row inserted). On any authed page, expect the banner: blue info alert reading "AIDSTATION works best with a fitness provider connected. Want to set one up? **Connect a provider**" with a × close button on the right. Clicking the CTA text lands on `/onboarding/connect`.
8. **Banner dismiss round-trip.** Click the ×. Expect: page reloads (same URL via referrer); banner gone. `psql`: `SELECT dismissed_at FROM account_nudges WHERE user_id=<uid> AND nudge_type='connect_provider_14d'` shows a recent timestamp.
9. **Dismiss persistence across reloads.** Hard-reload after dismiss; banner stays gone (state lives in DB, not session). `UPDATE account_nudges SET dismissed_at = NULL WHERE id = <nudge_id>` → reload → banner re-appears.
10. **Empty-state hygiene.** Log out and load the login page; no banner renders (context processor guards on `current_user_row`). Log in as a user with no nudges; no banner renders.
11. **CSRF rejection.** `curl -X POST .../nudges/<id>/dismiss` without the CSRF token → 400 (Flask-WTF CSRFError surface). Browser POST from the partial includes the token automatically.
12. **Cross-user scoping.** `curl -X POST -b <session-cookie-for-user-A> .../nudges/<nudge-id-belonging-to-user-B>/dismiss` (with valid CSRF token) → silently no-op (the UPDATE's `user_id = ?` predicate doesn't match; `cur.rowcount` would be 0; the route doesn't surface this distinction, which is fine — the redirect happens either way). `psql`: user B's nudge row's `dismissed_at` stays NULL.
13. **Vercel Cron live trigger.** After 14:00 UTC the day after deploy, check Vercel UI → Cron Jobs → invocation log. Should show a successful 200 response. Function logs should show the `INSERT … RETURNING id` count. (Skippable if there are no newly-eligible users; the cron should still 200 with `{"inserted": 0}`.)
14. **Regression sweep on the rest of the app.** Browse to `/profile?tab=athlete`, `/onboarding/connect`, `/onboarding/prefill`, `/dashboard`, `/training`. None of those pages should look visually different from pre-PR9 except for the banner when present. (The `_account_nudges.html` include is a one-line addition to `base.html` between flashes and content; should be invisible when `active_nudges == []`.)
15. **Independent of PR9:** PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 + PR6 §5.0 + PR7 §5.0 + PR8 §5.0 are still owed if not yet completed.

### 5.1 PR10+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR9_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR8_Closing_Handoff_v1.md` (predecessor).
4. `aidstation-sources/Project_Backlog_v21.md` — current; PR10 may need to bump to v22 (see §5.4).
5. Domain spec for the picked candidate (e.g. `Onboarding_D59_Design_v1.md` for D3; `Onboarding_D58_Design_v1.md` §6 for E-telemetry; `Athlete_Onboarding_Data_Spec_v5.md` §A.2.7 for D2c tolerance).

D-50's frontend bucket — D1 + D2a + D2b + E — is now **complete**. The v5 §A.2 + §A.2.4 onboarding loop is fully wired end-to-end:

- Step 2 connect screen (D1, PR5)
- Read-side prefill UX (D2a, PR7)
- Write-side prefill UX + source-flip + clear-override (D2b, PR8)
- 14-day no-providers nudge (E, PR9)

The remaining work is independent of the onboarding flow itself.

#### Option D3 — Locale-creation flow with Mapbox chain detection (recommended next)

Carries forward unchanged from PR7 §5.1 / PR8 §5.1 / now PR9 §5.1. With v5 onboarding end-to-end wired, D3 is the next obvious step toward closing out the v5 implementation arc. Scope:

- **Mapbox API client** — small module wrapping the Mapbox Places API (Forward Geocoding). Env vars `MAPBOX_PUBLIC_TOKEN` + `MAPBOX_SECRET_TOKEN` (latter for any server-side calls; current client-side use is the public token only).
- **Chain detection** — call `chain_registry.py:detect_chain(place_payload)` (PR2 shipped this module). Maps Mapbox `place_name` / `properties.category` to one of the canonical `GYM_CHAINS[].chain_id` values, or NULL when no chain matches (athlete-supplied custom locale).
- **Locale-creation routes** — `GET /locales/new` (or refactor the existing `/locales/profiles/new`) renders a Mapbox-search-anchored form; `POST` writes a `locale_profiles` row with all the D-59 columns (lat, lng, mapbox_id, chain_id, chain_name, category, place_payload, place_fetched_at).
- **Locale UI** — D-60-spec'd shared-gym-profile inherit/override/dispute flow on top of `gym_profiles` + `locale_equipment_overrides` + `locale_toggle_overrides`.

Larger PR. Estimate 5+ files. Likely pushes the 5-file ceiling — consider splitting Mapbox-search-anchored creation (D3a) from the inherit/override UI (D3b).

#### Option F — Polar refresh-on-401

Carries forward unchanged. Watch item only — surfaces if any athlete hits a 401 from Polar with a valid refresh_token in `provider_auth.refresh_token`.

#### Option H — Provider blueprint roster expansion

Carries forward unchanged. Opportunistic per-provider PRs as integration partners come online (Wahoo / Strava / Whoop / TrainingPeaks / Zwift / RWGPS). The PR3/PR4 Polar pattern is the template.

#### Option D2c — Bulk "Apply all" + tolerance-based re-prefill

Carries forward from PR8 §5.1. Lands when athletes actually need bulk apply. Today's per-field-only is fine for the 1-test-athlete state.

#### Option E-telemetry — Display / dismiss / act-on rates on the connect-provider banner

**New** PR10+ candidate, surfacing Open Item #18 from `Athlete_Onboarding_Data_Spec_v5.md` §13. Scope:

- **`displayed_at` writes** — populate `account_nudges.displayed_at` the first time the banner renders (per-user, per-nudge). One UPDATE per first render; subsequent renders no-op. Could live in `_inject_active_nudges` or in a separate `mark_displayed` helper invoked from the partial via a small JS hit (don't add JS just for this — server-side write on first render with `displayed_at IS NULL` is cleaner).
- **`dismissed_at` already populated** by the existing dismiss handler — PR9 didn't need any new write here.
- **`acted_at`** — new column? Or use `dismissed_at = NOW()` + a separate flag? Spec doesn't define this precisely. Recommend: add a `clicked_cta_at` column to `account_nudges` and write it from a thin redirect-shim route `GET /nudges/<id>/click → 302 to CTA endpoint`. Then the banner CTA is `url_for('nudges.click', nudge_id=n.id)` instead of `url_for(n.cta_endpoint)`.
- **Reporting** — `SELECT nudge_type, COUNT(displayed_at), COUNT(clicked_cta_at), COUNT(dismissed_at) FROM account_nudges GROUP BY nudge_type` is the v1 metric query. No dashboard yet; Andy's admin page can grow it later.

Schema change (add `clicked_cta_at` column to `account_nudges`) — schema migration. Stop-and-ask trigger #5 if scope expands. Likely 2-3 files.

### 5.2 Recommended sequence (revised post-PR9)

**D3**, with **F** as a watch item and **E-telemetry** picked up after first real production traffic; **D2c** picked up if athletes find per-field-only too tedious; **H** providers as opportunistic adds whenever an integration partner is ready.

D3 is the next obvious step — the v5 onboarding flow is now fully wired end-to-end; the v5 implementation arc's next gap is the locale-creation UX D-59/D-60 designed for.

### 5.3 Standing items not on the critical path (carried from PR8 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged. Independent.
- **D-54 SQLite collapse** — unchanged. Catalog Migration Phase 5.
- **D-55 Garmin onto `provider_auth`** — paused.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. PR9 doesn't touch the webhook path. **Cross-cutting note:** PR9's `vercel.json` `crons` array is the natural home for the D-62 prune cron when it ships — same pattern (token-gated endpoint + Vercel Cron entry).
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — *closed by PR7*. Stays closed.
- **Open Item #18 — Telemetry on the 14-day connect-provider nudge** — surfaced by PR9's E ship. *Now a PR10+ candidate (E-telemetry).* Removed from carry-forward (decision: surfaced as candidate, not deferred).
- **DATABASE.md update** — unchanged.
- **PROVIDERS_SCHEMA.md update** — unchanged.
- **Provenance-row deletion on field clear** (carry-over from PR6/PR7/PR8) — *unchanged*. v5 §A.2.3 row 2 ("Athlete clears a prefilled field → source flips to manual_override; value becomes empty") is partially addressed by PR8's source-flip refactor but the empty-value flip is still missing. Documented in PR8 §5.3; tractable in a future small-scope PR.
- **Unused `_POST_STEP2_TARGET` alias** (carry-over from PR7/PR8) — unchanged. Cosmetic; doesn't block anything.
- **Per-field "from {provider}, {age}" tag** (carry-over from PR7/PR8) — unchanged.
- **`[Keep current]` writes `'manual_override'` even for prior `'self_report'`** (carry-over from PR8) — unchanged. Spec stretch, defensible per PR8 §6.
- **No retry/idempotency story for the apply endpoint** (carry-over from PR8) — unchanged.
- **`f.candidates[0]` divergence tag** (carry-over from PR8) — unchanged.
- **Confirmation dialogs on `[Use provider value]` for derived extractors** (carry-over from PR8) — unchanged.

### 5.4 Backlog row update (next PR's first action)

PR9 bumped v20→v21 (this revision). PR10 will need to bump v21→v22 if and only if it lands a state-changing event (e.g. D3 ships → D-50 row notes update; would acknowledge locale-creation flow in flight or shipped, or possibly a new D-row split for D3a/D3b).

**For PR10, owed v21 → v22 bump (mechanically-applicable per Rule #11):**

1. Copy `aidstation-sources/Project_Backlog_v21.md` to `aidstation-sources/Project_Backlog_v22.md`.
2. **Replace** the file-revision header on line 5:
   - Old text:
     ```
     **File revision:** v21 — 2026-05-15 (D-50 row status flip catching up PR9: D-50 status cell now reads 🟢 PR1 + PR2 + PR3 + PR4 + PR5 + PR6 + PR7 + PR8 + PR9 shipped 2026-05-14/15 (commits …, `43ccedf` PR8-merge, `<PR9-merge-pending>`); 🟢 Option E shipped — PR9 wires the v5 §A.2.4 14-day connect-provider nudge … per `V5_Implementation_PR9_Closing_Handoff_v1.md`. No new D-row work this revision — pure status tracking + E execution)
     ```
   - New text (assuming PR10 = D3):
     ```
     **File revision:** v22 — 2026-05-1X (D-50 row status flip catching up PR10: D-50 status cell now reads 🟢 PR1–PR10 shipped 2026-05-14/15/1X (commits …, `<PR9-merge>`, `<PR10-merge>`); 🟢 D3 locale-creation + Mapbox chain detection shipped PR10 — Mapbox client + chain detection + locale-creation routes + locale UI per `V5_Implementation_PR10_Closing_Handoff_v1.md`. No new D-row work this revision — pure status tracking)
     ```
3. **Prepend** to the predecessor revisions block:
   ```
   - v21 — 2026-05-15 (D-50 row status flip catching up PR9: …)  [verbatim from current v21 line 5 narrative]
   ```
4. **Update** the D-50 row status cell from PR1–PR9 → PR1–PR10 shipped, mark D3 as shipped, leave F/H/D2c/E-telemetry pending. Update Notes column "PR10+ candidate menu" → "PR11+ candidate menu" and shift the D3 entry from pending → shipped.
5. **Bump** `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line from `Project_Backlog_v21.md` to `Project_Backlog_v22.md`.

**If PR10 is something other than D3** (e.g. E-telemetry, D2c, F, H), the narrative text changes but the file mechanics are identical (copy → header replace → predecessor prepend → D-50 row update → CLAUDE.md bump). Write the v22 header narrative to reflect what actually shipped.

---

## 6. Open items / honest flags

- **No live verification.** Same risk class as PR1–PR8. Flask isn't installed in the sandbox. AST + Jinja + JSON parse + 5-case auth exercise + 4-case `get_active_nudges` exercise + 4-variant banner render confirmed the wiring + state-machine correctness. The PR9 §5.0 manual click-through is mandatory before this is real.
- **`CRON_SECRET` must be set before first cron firing.** If the env var is unset on Vercel at the time the first scheduled cron fires, the route returns 401 and no nudge rows are written. Vercel won't retry. Mitigation: §5.0 step 2 is "set the env var before deploy" — and the cron schedule is `0 14 * * *` so the first firing is at 14:00 UTC the day after deploy, giving room to spot the env var gap on the post-deploy checklist.
- **Cron auth uses constant-time compare but not request-replay protection.** A leaked CRON_SECRET would let an attacker insert nudge rows for eligible users. Blast radius: small (an attacker would just be inserting `account_nudges` rows that would have eventually been inserted anyway by the legitimate cron). Mitigation: rotate `CRON_SECRET` periodically (no in-code mechanism today; manual). Adding HMAC-signed request bodies with a timestamp + nonce would be overkill for the threat model.
- **`displayed_at` is never written.** v5 spec mentions it but doesn't require it. PR9 leaves it NULL on every row. Telemetry on display rate is impossible until E-telemetry (PR10+ candidate) lands.
- **No JS-free path for the dismiss button's accessibility.** The `btn-close` element has `aria-label="Dismiss"` but no visible text. Screen readers see the aria-label correctly. Sighted athletes recognize the × glyph. Keyboard nav works because it's a real `<button type="submit">`. Should be OK; called out for transparency.
- **The banner can stack if multiple `nudge_type`s ever exist for one user.** Today only one type exists, so this is moot. The partial loops over `active_nudges` so N>1 produces N alert blocks. If that becomes visually cluttered (rare — we're shipping with one type and have one possible new type planned), a future iteration could collapse to a single most-recent banner or batch multiple into one alert with a list.
- **`vercel.json` `crons` array doesn't gate the schedule by Vercel plan tier.** Hobby allows daily; Pro allows finer. The `0 14 * * *` daily schedule is Hobby-safe. If we ever drop to a Free/Hobby plan that disables crons entirely, the array becomes inert (Vercel ignores it) — TrueNAS could pick up by hitting the same endpoint via crontab. Flagged for transparency.
- **No tests added.** Inline `python3` exercises for AST parse + Jinja parse + JSON parse + 5-case auth check + 4-case nudge resolution + 4-variant banner render were the offline guards. Same framing as PR1–PR8: a real `tests/` directory still doesn't exist. PR9's auth boundary + the per-user dismiss scoping are good unit-test targets if a `tests/` infrastructure ever ships; carries forward as a flag.
- **5 substantive code files + 2 bookkeeping (v21 + CLAUDE.md) + 1 handoff = 8 total.** At the 5-substantive ceiling. PR9 deliberately stayed scoped to E proper — D2c bulk apply and E-telemetry are split out as PR10+ candidates.
- **Banner placement in `base.html` between flashes and content** is a styling judgement call. Spec says "passive in-app banner" — passive implies non-blocking, not specifically above-vs-below flashes. Placement could move if Andy thinks flashes should sit beneath the persistent nudge instead.

---

## 7. Gut check

**What this session got right.**

- **Closed the v5 §A.2.4 loop.** With PR9 shipped, the v5 onboarding flow is end-to-end wired: Step 1 acknowledgment → Step 2 connect → Step 3a prefill → Step 3 profile form → 14-day passive nudge for the no-providers path. Every spec'd mechanic has code.
- **Cron host stop-and-ask before coding.** Stop-and-ask trigger #8 was real: three host options (Vercel Cron / TrueNAS / APScheduler) with meaningful tradeoffs. Surfaced the choice; Andy picked Vercel Cron; documented the rationale.
- **Idempotent scanner.** Three NOT EXISTS predicates + ON CONFLICT DO NOTHING + UNIQUE constraint means re-running the cron is harmless. Vercel could double-fire on a deploy boundary or TrueNAS could chime in alongside — none of it produces duplicate rows or duplicate banners.
- **Re-uses existing patterns.** Bearer-token auth mirrors `coros.webhook` / `polar.webhook`. PG-only guard mirrors PR8's `_record_self_report_provenance`. Context processor mirrors `_inject_current_user`. No new architectural shape; the v5 onboarding implementation arc keeps a consistent surface.
- **Banner partial extensibility.** `NUDGE_REGISTRY` keyed by `nudge_type` means adding a new banner type is one entry + one writer. The partial loops over `active_nudges` with no per-type branching.
- **PG-only graceful degradation.** SQLite dev returns `[]` from `get_active_nudges` and the scanner returns `{inserted: 0, note: '…'}`. Local probes don't 500.
- **Came in at the ceiling.** 5 substantive files. No scope creep into telemetry or D2c.

**Risks.**

- **First cron-driven write path in the app.** PR3's webhook handlers receive POSTs from provider servers but are reactive; PR9's scanner is the first proactive scheduled write. A bug in the SQL could produce phantom nudge rows for ineligible users. Mitigation: the three NOT EXISTS predicates + UNIQUE constraint are belt-and-suspenders. The PR9 §5.0 step 4 manual smoke test against a real eligible user is the integration-level guard.
- **Banner renders on every authed page.** A regression in the partial markup or the context processor would surface site-wide. Mitigation: the partial is small and renders nothing when `active_nudges` is empty; the context processor's exception catch falls back to `[]` so a DB outage doesn't 500 every page. PR9 §5.0 step 14 regression sweep is the visual guard.
- **`CRON_SECRET` env var management is manual.** No code to enforce it's set. If a future Vercel project rebuild forgets the env var, the cron silently 401s and no nudges fire. Mitigation: §5.0 step 2 documents the requirement; the v21 backlog Notes column carries forward the requirement; future-PR vigilance is the only safeguard.

**What might be missing.**

- **Telemetry on display / dismiss / act-on rates** — Open Item #18 from the spec. Surfaced as PR10+ candidate E-telemetry. Not in PR9 by design — would have pushed the ceiling.
- **`clicked_cta_at` redirect shim** — counterpart to the dismiss UPDATE. Athletes who click the CTA today go straight to `/onboarding/connect`; no record of the click. Same reason as above — telemetry split out.
- **No batching of multiple nudges.** If future nudge_types proliferate, the page could end up with several banners stacked. Acceptable for now (single type).
- **No "do not show again for N days" snooze.** Spec says "one nudge only — no further escalation"; that's exactly what PR9 ships (dismissed_at populated permanently). If athletes want snooze rather than dismiss, that's a separate UX decision.

**Best argument against this session's scope.**

PR9 ships infrastructure (cron + banner + context processor) for a single use case (one nudge_type) against a population of one (Andy, who is already connected to COROS, so the nudge never fires for him until he disconnects). The immediate user-visible win is zero — no athletes will see this banner today.

Counter: the v5 spec's §A.2.4 was the last unshipped onboarding mechanic. Shipping it now means the v5 implementation arc has a clean "v5 onboarding fully wired end-to-end" milestone. The next athlete who signs up and skips the connect step gets a working passive nudge after 14 days. The infrastructure also pays for itself on the second nudge_type — adding one is now a registry entry plus a writer.

Counter to the counter: shipping infrastructure ahead of users means the cron will run daily against an empty result set for the foreseeable future. The cost is negligible (one Vercel function invocation per day; one indexed SELECT on `users` × `provider_auth` × `account_nudges`) but the value is zero until population grows. Mitigation: this is the right kind of pre-built infrastructure — small, low-risk, no migration, no athlete-facing change for existing users (Andy never sees the banner because he's connected). Sits idle harmlessly.

---

## 8. Forward pointers

- **Next session:** PR10 = Option D3 (locale-creation flow with Mapbox chain detection, recommended) or any of the PR9 §5.1 carry-forward candidates. PR9 closes the v5 §A.2.4 loop; D3 is the next obvious v5-implementation-arc step.
- **Before next code lands:** PR9 §5.0 spot-check on the deployed app (set `CRON_SECRET`, verify cron registered, run auth happy + failure paths, observe banner render + dismiss round-trip). PR1 §5.0 + PR3 §5.0 + PR4 §5.0 + PR5 §5.0 + PR6 §5.0 + PR7 §5.0 + PR8 §5.0 are still owed if not yet completed.
- **First action of next session:** Rule #9 reconciliation. Specifically: confirm PR9 commit landed on `claude/v5-implementation-handoff-UqIvn` (or merged to main with its own merge commit); confirm `routes/nudges.py` has the 2 routes + `get_active_nudges` + `_cron_authorized` + `NUDGE_REGISTRY`; confirm `templates/_account_nudges.html` exists with the dismiss form; confirm `templates/base.html` includes the partial; confirm `app.py` registers `nudges_bp` + exempts `nudges.scan_connect_provider_14d` + has `_inject_active_nudges` context processor; confirm `vercel.json` has the `crons` block; confirm `Project_Backlog_v21.md` exists with v20 archived to predecessor block + D-50 row reflects PR9 shipped; confirm `CLAUDE.md` "Authoritative current files" backlog line reads v21.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **PR9 has one deferred mechanical edit:** the v21 → v22 backlog bump for PR10's first action, spec'd verbatim in §5.4
- #12 numeric version suffixes (backlog now at v21; v22 lands in PR10 per §5.4)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR9 closing handoff. v5 onboarding Option E (14-day connect-provider nudge) shipped: `routes/nudges.py` blueprint with `GET /cron/nudges/connect_provider_14d` (token-gated daily scanner; idempotent INSERT … ON CONFLICT DO NOTHING) + `POST /nudges/<id>/dismiss` (per-user scoped UPDATE) + `get_active_nudges` helper exposed as the `active_nudges` template context; new `templates/_account_nudges.html` partial slotted into `base.html`; `vercel.json` `crons` entry on `0 14 * * *` daily. Deep-link target is PR5's `/onboarding/connect`. Closes the v5 §A.2.4 loop — the v5 onboarding flow is now end-to-end wired. Backlog bumped v20 → v21. Next: Andy's choice among PR10 candidates in §5.1 (D3 recommended — locale-creation flow with Mapbox chain detection, the next obvious v5-implementation-arc step); v21 → v22 backlog bump mechanically spec'd for PR10's first action.*
