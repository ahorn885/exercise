# Session Handoff — 2026-05-13 (stub batch)

**Companion to** `HANDOFF-2026-05-13.md` (the provider-stub playbook).
This file covers a single session in which **four more provider stubs
were prepped** but **left uncommitted** for review, and the playbook's
schema was extended by one variant (Strava's `hub.challenge`
handshake).

**Branch:** `claude/review-handoff-integrations-DO96G`
**State at handoff:** working tree dirty, nothing committed, nothing
pushed. Stop hook has been ignored intentionally per session
agreement.

---

## What was prepped

Four new provider stubs, all following the playbook in
`HANDOFF-2026-05-13.md`:

| Slug | Module | Webhook URL | Notable spec quirk |
|---|---|---|---|
| `strava` | `routes/strava.py` | `/strava/webhook` | `hub.challenge` echo on GET (new schema variant — see below) |
| `whoop` | `routes/whoop.py` | `/whoop/webhook` | HMAC-SHA256 over body, `X-WHOOP-Signature` header |
| `trainingpeaks` | `routes/trainingpeaks.py` | `/trainingpeaks/webhook` | Push auth scheme unconfirmed (open question) |
| `zwift` | `routes/zwift.py` | `/zwift/webhook` | Push channel availability unconfirmed (open question) |

All four added to `_PROBED_AT_REGISTRATION` in
`routes/oauth_callbacks.py`, so `/auth/<slug>/callback` returns **200**
instead of 501. (Handoff said "no downside" to flipping
speculatively — choice was made up-front, not per-provider.)

All four wired in `app.py`:
- Imports near line 144
- `register_blueprint` near line 162
- One shared `csrf.exempt` block per webhook
- Four entries appended to `_AUTH_EXEMPT_ENDPOINTS`

---

## Schema extension: challenge-echo variant

The playbook's question #5 ("Verification handshake on URL
registration?") mentioned Stripe/Slack-style challenge tokens but had
no concrete shape. This session added one.

**Strava** subscribes via `POST /push_subscriptions` to their API,
which makes Strava **immediately GET the callback URL** with:

```
GET /strava/webhook?hub.mode=subscribe
                   &hub.verify_token=<our token>
                   &hub.challenge=<their nonce>
```

The endpoint must respond `200` with body `{"hub.challenge": "<their
nonce>"}` exactly — anything else and Strava refuses to create the
subscription.

The stub in `routes/strava.py` implements this handshake **today**, so
the moment we POST to `/push_subscriptions` in Phase 1 it will work
without a redeploy:

```python
if request.method == 'GET':
    challenge = request.args.get('hub.challenge')
    if challenge is not None:
        return jsonify({'hub.challenge': challenge}), 200
    return jsonify(status='ok'), 200
return jsonify(status='ok'), 200
```

**Schema rule going forward:** when a provider uses a challenge
handshake, bake the echo into the Phase 0 stub. It is the cheapest
piece of "Phase 1" work that pays off the day the OAuth connect ships.

**Known gap in the Strava stub:** it does NOT yet check
`hub.verify_token` against an expected value. Add that check when
`STRAVA_VERIFY_TOKEN` is set in env (Phase 1).

---

## Per-provider notes for whoever promotes these

### Strava
- One credential pair: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`.
- Plus a self-generated `STRAVA_VERIFY_TOKEN` we send to Strava when
  creating the subscription, and check on the inbound GET handshake.
- Webhook POSTs carry **no signature** — auth is by matching
  `subscription_id` in the body against the single subscription we own.
- Event shape: `{aspect_type, event_time, object_id, object_type,
  owner_id, subscription_id, updates}`.
- Strava is **one subscription per application**, not per user — keep
  the subscription id in env or a `provider_meta` row, not per-user.

### Whoop
- One credential pair: `WHOOP_CLIENT_ID`, `WHOOP_CLIENT_SECRET`.
- Webhook auth: HMAC-SHA256 over the **raw request body** using the
  client secret. Signature is base64 in `X-WHOOP-Signature`.
  Companion header `X-WHOOP-Signature-Timestamp` must be within a
  rolling window (Whoop docs say 5 min — confirm).
- Event shape: `{user_id, id, type, trace_id}` where `type` is e.g.
  `workout.updated`, `recovery.created`.
- No challenge handshake; subscription is configured in the dev
  portal, not via API.

### TrainingPeaks
- **Open questions before promotion:**
  1. Push auth scheme — bearer / basic / shared-secret? (Partner docs
     gated; confirm via TP partner support.)
  2. Single event or batch in the push body?
  3. Retry / dedupe behavior on non-2xx.
- Until those are answered, the stub returns generic `{"status":"ok"}`.

### Zwift
- **Open questions before promotion:**
  1. Is a push channel granted at our partner tier, or pull-only via
     activity export?
  2. If push: bearer or HMAC?
  3. Event shape — activity completion only, or richer event types?
- Stub returns generic `{"status":"ok"}` until confirmed.

---

## Files changed (uncommitted)

```
modified:   app.py
modified:   routes/oauth_callbacks.py
new file:   routes/strava.py
new file:   routes/trainingpeaks.py
new file:   routes/whoop.py
new file:   routes/zwift.py
```

Smoke-test result at handoff time: 12/12 endpoint probes returned
200, and `GET /strava/webhook?hub.challenge=abc123` returned
`{"hub.challenge":"abc123"}`. Test command in the playbook (`Recipe
step 5`) reproduces it.

---

## What's left

From `_PROVIDERS` in `routes/oauth_callbacks.py`, still no stub:

- **Master-plan v1 (highest priority):** `polar`, `wahoo`
- **Wave-2 remainder:** `google-health`, `apple-health`, `vo2`,
  `nike-run-club`, `decathlon`, `adidas-running`, `komoot`,
  `final-surge`, `myfitnesspal`
- **Garmin** — already has a route file (`routes/garmin.py`) for FIT
  debug; it is **not** a Phase-0 webhook stub. When the real Garmin
  PUSH API integration ships it goes into the same file.

Polar + Wahoo are the next two by master-plan priority. Both have
documented HMAC / retry semantics already noted in the playbook
(questions #2 and #4), so they're closer to "just do it" than TP /
Zwift.

---

## Working agreement carried into next session

- Stubs above are **uncommitted**. The user explicitly chose "files
  only, uncommitted" and "leave as-is, ignore hook" when the stop
  hook complained. Don't auto-commit on the next session without
  fresh confirmation.
- If the user says "ship the batch", do **one commit** covering all
  four stubs + wiring + `_PROBED_AT_REGISTRATION` edit, push, **one
  PR** (not four), merge with the **merge** method per playbook.
- If the user says "ship them one at a time", use `git add -p` to
  split into four commits per provider, then four PRs — but this is
  more work and not required by the playbook.

---

## Files to re-read at the start of the next session

1. `HANDOFF-2026-05-13.md` (the playbook — pattern itself)
2. This file (`HANDOFF-2026-05-13-stub-batch.md`)
3. `routes/strava.py` for the challenge-echo variant
4. `routes/oauth_callbacks.py` for the current `_PROVIDERS` and
   `_PROBED_AT_REGISTRATION` state
5. `app.py` lines 140-205 for the wiring
