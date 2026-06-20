# V5 Implementation — #780 Layer 2C built per cluster locale (lifts the `[primary_locale]` stub) — Closing Handoff

**Date:** 2026-06-20
**Branch:** `claude/gallant-mccarthy-slzh9i`
**PR:** pending Andy's go (PR-gated — Andy 2026-06-19)
**Entry task:** "work on GitHub issue #624 — I think it may be resolved, or already be under evaluation based on another issue."

---

## 1. What this session did

A direct-task session on **#624** ("[Plan-gen] Nearby groomed-trail location not detected (Cleburne State Park) while a farther park is, pv=71"). Andy's prompt hypothesized it might be resolved or tracked elsewhere.

**Investigation result — the hypothesis was right.** #624 shipped three surface-routing slices (#639 Slice 1, #641 Slice 2, #642 Slice 3) and was closed, then **reopened 6/17** because it recurred on the 6/17 plan (Trail Running placed @ `509 Williams Avenue` instead of Cleburne; *"nearby groomed-trail venues aren't making it into the candidate set"*). Two days later the plan-75 watch opened **#780** — the precise root cause — which `CURRENT_STATE` had **scheduled for "a new session."** This is that session. Andy: **link & reconcile, then fix it here.**

## 2. Root cause (#780)

`_upstream_full_cone` invoked **Layer 2C once, for the primary locale only**, and wrapped it as a one-entry dict `{primary_locale: payload}` (the documented "today stubbed to `[primary_locale]`" stub, `Locations_Consolidation_Design_v1.md:81`). But the whole downstream stack keys on a **per-locale** dict:

- `validator.py:991` rule 6c `session_locale_not_in_cluster`: `cluster = set(ctx.layer2c_payloads.keys())` → narrowed to `{home}`, so every nearby-locale session was a false-positive **blocker** (force-accepted via cap_hit, polluting every block + burning the retry budget).
- `locale_assign.assign_locales` (best-fit-first + cascade) — built for the full dict, **starved** with one entry.
- `skill_gated_disciplines`, `compute_layer2c_bundle_hash` — both already key by locale.

The feasibility cascade + synthesis prompt already saw the full cluster, so the synthesizer correctly spread sessions across nearby locales and the validator then rejected all but the gym — the #624 reopen symptom.

## 3. The fix (orchestrator-only — the downstream machinery was already correct)

`layer4/orchestrator.py`:
- `_upstream_full_cone` now loops `cluster_locale_ids` and calls 2C **once per locale**, each against that locale's own `locations.locale_effective_tags(...)` (was: a single primary call carrying the cluster-UNION pool). Empty cluster → falls back to `[primary_locale]` (preserves the primary entry).
- `_UpstreamFullCone.layer2c_payload: Layer2CPayload` → **`layer2c_payloads: dict[str, Layer2CPayload]`**.
- The three consumers pass the dict straight through: `orchestrate_race_week_brief` (`layer2c_payloads=`), `orchestrate_plan_refresh` (`Layer2Bundle.c=`), `orchestrate_plan_create` (`layer2c_payloads=`).
- `_gather_feasibility_inputs`: `pool_by_discipline` reads the **primary** entry (`cone.layer2c_payloads[cone.primary_locale]` — home-gym strength); `skill_gated_disciplines` now gets the **full** dict (matches `validator.py:1381`).
- Rule #15: per-locale fan-out `print()` (`cluster` + per-locale `effective_pool` sizes).

## 4. Decisions (the owed approach sign-off — CARRY_FORWARD §"#780 clustering")

- **One 2C call per locale**, each against its own equipment (per the 2C spec "one call per locale in the cluster" + #780's fix direction) — not a single full-cluster call. Matches what the validator/locale-assign already consume.
- **Cache-key invalidation is automatic, no `LAYER4_PROMPT_REVISION` bump.** `cached_wrappers._layer2c_bundle_hash` hashes each payload per locale, so the per-locale dict folds the locale SET into the bundle hash. **Single-locale-cluster athletes → byte-identical key (no gratuitous cold re-synth); multi-locale athletes → invalidate** (their plans were wrong and should re-synth). Prompt wording is unchanged, so a global revision bump (which would needlessly re-synth single-locale athletes too) is wrong here.
- **`pool_by_discipline` reads the primary entry** (#780's explicit note). Implication to verify: for a **multi-gym** athlete the primary entry's equipment narrows from cluster-union → primary-only — correct per-locale semantics (home-substitute strength is done at home; locale-assign can route to a better-equipped locale, which now has a payload). For pv=71 the nearby locales are outdoor (Cleburne, Lake Pat Cleburne) → no strength equipment → union ≈ primary, so negligible there.
- **`skill_gated_disciplines` broadened to the full cluster** for consistency with the post-synthesis validator (it already calls `skill_gated_disciplines(ctx.layer2c_payloads)`); locale-independent in practice.

## 5. Verification

- `tests/` **2831 passed / 30 skipped** (+1 `TestOrchestratePlanCreateHappyPath::test_layer2c_built_per_cluster_locale`: a 2-locale cluster → 2C called once per locale against its own pool; the full per-locale dict reaches the synthesizer).
- `etl/tests/` **90 passed**.
- Updated `_cone` mock in `tests/test_layer4_terrain_feasibility_wiring.py` (singular → `layer2c_payloads` dict) and the stale `{"home"}` comment in the plan-create happy-path test.
- No DDL, no schema/contract change (the orchestrator is aligned to an already-existing downstream contract), no prompt-body change.

## 6. Next steps

### 6.3 Operating notes for next session — read order
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — last shipped + focus
3. `CARRY_FORWARD.md` — rolling items (the #780 line is now "built, pending PR")
4. This handoff
5. `./scripts/verify-handoff.sh`

### Owed
- **LIVE-VERIFY (Andy-action — container can't reach Neon):** regenerate a **pv=71** plan → the Trail Running long run resolves to **Cleburne State Park** (groomed trail), not `509 Williams Avenue`; **no** `session_locale_not_in_cluster` blockers in the validator log; `/admin/logs` shows `_upstream_full_cone: … layer2c built per-locale for cluster=[…]` with the nearby locales present. This is also the natural place to re-check the **plan-75** clustering symptom (#780's origin).
- **#778 / #779** (plan-75 same-discipline / two-hard-day auto-repair) remain open and independent of #780.
- Carried live-verifies unchanged (see CARRY_FORWARD).

## 7. Issue reconciliation
- **#780** — commented with the fix; closes on merge.
- **#624** — commented: root cause traced to #780, fixed there; the three surface-routing slices stand (they were starved, not wrong). Closes on merge (the reopen is resolved by #780).

## 8. Anchors for next-session Rule #9 sweep

| Claim | File | Anchor / check |
|---|---|---|
| Cone carries a per-locale 2C dict | `layer4/orchestrator.py` | `layer2c_payloads: dict[str, Layer2CPayload]` (field on `_UpstreamFullCone`) |
| 2C built once per cluster locale | `layer4/orchestrator.py` | `for locale in cluster_for_2c` in `_upstream_full_cone` |
| Strength pool reads primary entry | `layer4/orchestrator.py` | `primary_l2c = cone.layer2c_payloads[cone.primary_locale]` |
| Rule #15 fan-out log | `layer4/orchestrator.py` | `layer2c built per-locale for cluster=` |
| Stub marked lifted | `aidstation-sources/designs/Locations_Consolidation_Design_v1.md` | `stub lifted #780` |
| New test | `tests/test_layer4_orchestrator.py` | `def test_layer2c_built_per_cluster_locale` |
