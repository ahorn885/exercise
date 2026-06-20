# V5 Implementation — #682/D-12: provider OAuth tokens encrypted at rest — Closing Handoff (2026-06-20)

**Branch:** `claude/provider-token-encryption-682` (off latest `origin/main` = the merged Wave-3b tip `a0d24ec`; PR pending Andy's go — PR-gated). **Suite:** 3042 passed / 30 skipped. Continues the provider-integrations arc — first slice of (C) #682, picked after the Wave-3b PR (#806) merged.

## 1. What this session did
"keep going" on (C) #682. **Scope-challenge (recorded, Trigger #5):** the API *contract* is already ratified (`specs/AIDSTATION_API_Spec_v1.md`, 2026-06-17 — envelope + principles + non-binding endpoint sketch). The remaining #682 surface (published developer platform, key issuance, OpenAPI, MCP server, full read/write routes) is **mostly speculative** for a single-user / no-third-party-developer / server-rendered-Jinja app with no JSON-API consumer yet. The one **real, non-speculative, tier-2 (safety)** gap is the spec's own §5/D-12 flag: `provider_auth.access_token`/`refresh_token` stored **plaintext** — every OAuth token wired across the provider arc (Strava/Whoop/Wahoo/Oura/RWGPS/TP) sat in the clear. **Andy's call (AskUserQuestion): encrypt provider tokens (recommended); defer the rest until a consumer exists.**

## 2. Shipped (commit `071db47`)
- **`routes/provider_token_crypto.py` (NEW):** `encrypt_token` / `decrypt_token` over **Fernet** (AES-128-CBC + HMAC), keyed by env `PROVIDER_TOKEN_ENC_KEY` (urlsafe-b64 32-byte Fernet key). **Transparent migration:**
  - **Key set:** new writes ciphertext; reads decrypt.
  - **Decrypt passthrough:** a value that isn't valid ciphertext (pre-existing plaintext row, or written before the key was set) is returned verbatim — reads never break.
  - **Key unset** (dev/test, or prod before the env var is set): both calls pass through unchanged (current plaintext behaviour) + a one-time `[provider-crypto] … unset` warning. **Safe rollout** — deploying this code does not break auth before the key is set; setting the key flips new writes to encrypted.
  - **Malformed key → RuntimeError** (operator error fails loud, never silent-plaintext fallback).
- **`routes/provider_auth.py`:** encrypt at the **write boundary** (`upsert_auth` ciphertexts `access_token`/`refresh_token` in `fields` before the SQL) + decrypt at the **read boundary** (`get_auth` and `get_auth_by_provider_user_id` via a new `_decrypt_row(row)` → `dict(row)` with the two token fields decrypted). `refresh_access_token` rides both (it reads via `get_auth`, writes via `upsert_auth`) so rotated tokens are stored encrypted.
- **`requirements.txt`:** `cryptography>=42.0`.
- **`tests/test_provider_token_crypto.py` (+10):** round-trip (key set), passthrough (no key), legacy-plaintext decrypt-to-self, None/'' passthrough, malformed-key RuntimeError, `upsert_auth` encrypts in params, `get_auth` decrypts, legacy passthrough via `get_auth`, None-row passthrough.

## 3. GATED on Andy (go-live) + known limits (Rule #14)
- **Set `PROVIDER_TOKEN_ENC_KEY` in the Vercel env** to engage encryption. Generate once (chat-only, never commit): `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Until set, tokens remain plaintext (no behaviour change).
- **Key stability:** the key must be stable across deploys. If it's lost/rotated without re-encrypting, stored tokens become undecryptable → affected providers must be reconnected.
- **Long-lived providers stay plaintext until reconnected:** COROS/Polar tokens never refresh, so they won't self-encrypt; disconnect/reconnect (or a future one-time re-encrypt migration) covers them. Short-lived (Strava ~6h / Whoop ~1h / Wahoo/Oura/RWGPS/TP) self-encrypt on the next refresh once the key is set.
- **Deferred follow-ups:** encrypt `session_blob` (Garmin garth session — API closed, skipped as out-of-scope); a one-time re-encrypt migration for the long-lived rows (needs DB egress / an admin route — not built).

## 4. NEXT
- **Rest of #682 deferred** until a real API consumer (native iOS/Android client) exists — the developer platform / MCP / full route surface have no consumer today.
- Other open threads: provider live-verifies (the OAuth-registration-gated go-lives), Wahoo `plan.json` Tier-2 outbound (matrix §10.2), Tier-1 calendar export (the other `provider_outbound_ref` consumer, lives in #682 when a client needs it).

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this entry). 3. `CARRY_FORWARD.md` → **(C) #682** bullet. 4. This handoff. 5. `routes/provider_token_crypto.py` + `routes/provider_auth.py`. 6. `./scripts/verify-handoff.sh`.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Crypto helpers | `routes/provider_token_crypto.py` | `encrypt_token` / `decrypt_token`; `PROVIDER_TOKEN_ENC_KEY`; `_fernet()` (None when unset, RuntimeError on malformed); decrypt `except (InvalidToken, ValueError, TypeError)` → passthrough |
| Write boundary | `routes/provider_auth.py` | `upsert_auth`: `for _tok in ('access_token','refresh_token'): fields[_tok] = encrypt_token(...)` |
| Read boundary | `routes/provider_auth.py` | `_decrypt_row`; `get_auth` + `get_auth_by_provider_user_id` return `_decrypt_row(cur.fetchone())` |
| Dependency | `requirements.txt` | `cryptography>=42.0` |
| Tests | `tests/test_provider_token_crypto.py` | +10 (round-trip / passthrough / legacy / malformed / upsert-encrypts / get-decrypts) |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 3042 passed / 30 skipped |
| Issue | #682 | comment: D-12 plaintext-token gap closed; rest deferred (no consumer); contract already ratified |
