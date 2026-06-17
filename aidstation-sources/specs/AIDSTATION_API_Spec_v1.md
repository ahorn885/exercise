# AIDSTATION API — structured endpoints over the canonical model (#682) — Spec v1

**Status:** RATIFIED v1 (Andy, 2026-06-17). **Co-designed with `Provider_Data_Translation_Layer_Spec` (#681)** in one planning arc so ingest and API speak one contract. This wave fixes the **response/request shape**, the **endpoint surface sketch** (non-binding per #682), the **native-client dependency**, and the **direction of security/versioning work** (now in scope per Andy — designed in `AIDSTATION_API_Security_and_Developer_Platform_Spec`). Concrete route signatures, auth wiring, and the OpenAPI document are later waves. Spec only.

**Type:** API contract. Reads **and writes** the canonical model (#681). Outbound push (calendar/workout) makes the API a writer, not only a reader.

**Purpose:** Expose AIDSTATION's canonical model over structured endpoints so clients (web, eventual native iOS/Android, third-party developers, an MCP server) and our own ingest/read paths speak **one contract** — the canonical keys defined in `Provider_Data_Translation_Layer_Spec` §2.

**Source decisions (planning session, 2026-06-17; Andy):**
- **D-3:** canonical keys are defined **once** in the translation-layer spec §2; this spec references them, never redefines.
- **D-7:** record-don't-drop surfaces through the API — completed endpoints include bucket-3 non-prescribed items; bucket-2 proprietary metrics are retrievable via a raw/by-provider view.
- **D-6:** the API includes **outbound** endpoints (push a plan session/workout to a connected calendar or training platform).
- **D-12 (expansion beyond #682's stated scope):** API **security is now designed**, not deferred — two credential planes (provider secrets we hold; consumer keys we issue), encryption, rotation, plus a **published API** with a developer **application → issuance** flow. Mechanics live in `AIDSTATION_API_Security_and_Developer_Platform_Spec`; this spec references it.
- **D-13:** an **MCP server** binds the same model/endpoints (`AIDSTATION_MCP_Server_Spec`).

**Cross-references:**
- `Provider_Data_Translation_Layer_Spec` (#681) — **the canonical model owner**; §2 = the key vocabulary; §4 = the store this API reads/writes; §6.4 = bucket-3 contract.
- `AIDSTATION_API_Security_and_Developer_Platform_Spec` (#682 wave, D-12) — auth, keys, encryption, published spec, issuance flow, versioning.
- `AIDSTATION_MCP_Server_Spec` (D-13) — MCP binding over these endpoints.
- `#251` OAuth-first onboarding, `#268` BYOK Anthropic key, `#279` API token TTL — touch the auth surface; reconciled in the security spec.

---

## 1. North-star principles (from #682)

1. **Canonical keys are the contract.** Endpoints speak our canonical vocabulary — layer0 EX-ids, modality/discipline ids, metric keys, units, zone schemes — the **same** definitions the translation layer resolves to. Defined once (translation spec §2), shared by ingest and API.
2. **One pipeline, one schema.** `provider → translation (#681) → canonical store → API read`. Adding a provider or a metric is a **data/seed change, not an API change**.
3. **Record-don't-drop surfaces through the API.** The "completed activities/exercises" endpoint includes **bucket-3** items we don't prescribe (the athlete did them); **bucket-2** proprietary/unmapped metrics are stored + retrievable (raw/by-provider view) even if no primary endpoint surfaces them yet.
4. **Provider attribution + mapping confidence + original raw value are first-class** in response shapes, so consumers can distinguish canonical vs. raw and we can light up dormant data later **without a breaking change**.

### 1.1 What this API spec does NOT do (boundaries)

1. It does **not** redefine canonical keys (translation spec §2 owns them).
2. It does **not** design the auth model, key issuance, encryption, versioning mechanics, or pagination scheme in detail — those are the security spec (referenced). This spec states *that* security is in scope and how responses carry attribution.
3. It does **not** finalize concrete route paths/verbs — the surface in §3 is the **non-binding sketch** #682 asked for; route design is a later wave.
4. It does **not** replace the Flask/Jinja server-rendered app; it's the structured contract alongside/under it.

---

## 2. Response & request shape — the canonical envelope

Every canonical value carries its provenance so canonical vs. raw is always distinguishable and dormant data can light up without a schema break.

**Canonical field envelope (read):**
```jsonc
"hrv_rmssd_ms": {
  "value": 62,                 // canonical value, canonical unit (translation spec §2.2/§2.3)
  "_source": "polar",          // provider attribution
  "_match_kind": "exact",      // exact | fuzzy | manual  (from provider_value_map)
  "_confidence": 1.0,          // 0..1
  "_raw": { "field": "hrv", "value": 62, "unit": "ms" }  // original, verbatim (record-don't-drop)
}
```

- A **bucket-1** field has `value` + provenance + `_raw`.
- A **bucket-2** metric appears only in the **raw/by-provider** view: `value: null`, `_raw` populated, no canonical key required.
- A **bucket-3** completed item appears in the completed list with `prescribed: false`, `_source`, raw retained, `canonical_ref` possibly null (translation spec §6.4).
- **Units** are always canonical SI (translation spec §2.2); display conversion is the client's job (or a `?units=imperial` convenience param resolved at the edge).

**Write/ingest** uses the same envelope inbound: a client (incl. the native app for SDK providers) posts provider-attributed values; the translation layer normalizes; the store records canonical + raw.

---

## 3. Endpoint surface (sketch — non-binding per #682)

Grouped by resource; verbs/paths illustrative.

**Athlete profile & metrics**
- `GET /athlete/{id}/profile` — identity, units pref, connected providers.
- `GET /athlete/{id}/metrics?keys=hrv_rmssd_ms,resting_hr_bpm&from=&to=` — canonical metric series (body, HR/HRV/VO₂max/FTP, sleep, wellness), enveloped.
- `GET /athlete/{id}/metrics/raw?provider=polar` — **bucket-2 raw/by-provider view** (proprietary metrics, dormant-but-retrievable).

**Plans & sessions (the generated prescription)**
- `GET /athlete/{id}/plans` , `GET /plans/{plan_id}` , `GET /plans/{plan_id}/sessions` — plan sessions with canonical exercise EX-ids, modality/discipline ids, zone targets, assigned locale.

**Completed activities & exercises (record-don't-drop)**
- `GET /athlete/{id}/completed?from=&to=` — completed strength + cardio, **including bucket-3** non-prescribed items (`prescribed:false`, provider-tagged). This is where Garmin lifts with no EX-id and unprogrammed sports surface (translation spec §6.4).

**Provider connections & ingest status**
- `GET /athlete/{id}/providers` — connected providers, mechanism, last-ingest, status (mirrors `provider_auth.status` + `webhook_events`).
- `POST /ingest/{provider}` — the inbound write path for SDK providers (native client) and webhook fan-in.

**Outbound push (D-6)**
- `POST /athlete/{id}/export/calendar` — push plan session(s) as **Tier-1** events to a connected calendar (Google/Outlook/Apple); idempotent via `provider_outbound_ref`; supports update/delete on plan change.
- `POST /athlete/{id}/export/workout` — push plan session(s) as **Tier-2** native structured workouts to a connected training platform (TrainingPeaks/Garmin/Zwift/Wahoo).
- Both honor manual-trigger and the opt-in auto-sync-on-plan-change toggle.

---

## 4. Native-client dependency (SDK providers)

Apple HealthKit, Samsung Health, and Google Health Connect are **on-device SDKs** — no server OAuth. Their data reaches the canonical store via the **native app → `POST /ingest/{provider}`**. Hence #682's note that a native iOS/Android client is the **prerequisite** for Apple Health / Samsung Health. The API contract is mechanism-agnostic (the envelope is the same), but ingest for these providers cannot be server-initiated. Documented so the roadmap sequences the native client before those providers go live.

---

## 5. Security, versioning, attribution (now in scope — D-12)

Per Andy, security is **designed, not deferred** (an expansion beyond #682's "out of scope until scoped" line). Detail lives in `AIDSTATION_API_Security_and_Developer_Platform_Spec`; this spec records the surface-level contract:

- **Two credential planes:** (i) **provider secrets we hold** — the OAuth tokens/secrets for Garmin/Strava/etc., **plaintext today** in `provider_auth` (the gap), to be encrypted-at-rest + rotated (coordinates #268 BYOK / #279 token TTL / #251 OAuth onboarding); (ii) **consumer keys we issue** — scoped, rate-limited, rotatable, revocable keys for third-party developers and the MCP server.
- **Published API:** an OpenAPI document published on the site + a developer **application → review → issuance → manage/rotate/revoke** lifecycle.
- **Versioning & pagination:** designed as a published product (scheme + deprecation policy) in the security/platform spec; flagged here, not finalized.
- **Attribution is a security-relevant feature too:** `_source`/`_raw` let consumers audit provenance.

---

## 6. Open items
1. Concrete route paths/verbs, status codes, error envelope — route-design wave.
2. Pagination + filtering grammar for metric series and completed lists.
3. Auth model finalization (consumer keys vs OAuth-for-3p) — security spec.
4. Write-scope policy for the MCP server (read-only vs log/export) — `AIDSTATION_MCP_Server_Spec`.
5. Whether `?units=` edge conversion lives in the API or only clients.

## 7. Gut check
- **Best argument against speccing the API now:** #682 calls endpoint/auth design out-of-scope-until-scoped, so detailed routes would be premature — which is why §3 is an explicit non-binding sketch and the real work is the **envelope (§2)** and the **shared-keys contract (§1)**, the parts that must not be designed twice.
- **Biggest risk:** the envelope's `_source/_match_kind/_confidence/_raw` adds weight to every field; if over-applied it bloats responses. Mitigation: envelope only where provenance matters (provider-derived metrics/activities), plain values for app-native fields.
- **Coupling risk:** if this spec and the translation spec drift on key names, we redefine twice (the failure #681's comment warns about). Mitigation: §1 principle 1 + every key reference points at translation spec §2.
