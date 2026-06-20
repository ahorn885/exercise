# V5 Implementation — #803 StrengthExercise resolution-tier crash (deterministic fix) — Closing Handoff (2026-06-20)

## 1. What shipped

Live-watch follow-through on **#803**: plan generation (pv76 / pv77) failed at the
first **Build** block. The synthesizer emitted **tier-1 (exact)** `StrengthExercise`
picks that *also* carried a `substitute_text`, violating the `StrengthExercise`
tier↔field validator (`payload.py` `_check_resolution_tier`). That rule is a
cross-field constraint the JSON tool schema can't express and the prompt only
half-stated, so the model got it wrong; with the per-block budget leaving no
retry, one malformed attempt fumbled the block and **failed the whole plan**.
#777 surfaced it by populating the MTB/packraft strength pool (0 → 37), which
turned the substitution path ON for Andy's PGE plan.

**Fix (option C — deterministic, Andy-ratified):** before `StrengthExercise(**e)`
construction, overwrite `resolution_tier` / `substitute_text` / `proxy_origin_id`
with the authoritative values derived from each pick's **enum-locked
`exercise_id` → 2C resolution at the session's locale**. The synthesizer no
longer transcribes metadata it kept getting wrong; the strict `model_validator`
stays as a backstop. Applied at **all four** synthesis construction sites.

## 2. Root cause + how the fix works

- **Tier model (`context.py` `ResolvedExercise.tier: Literal[0,1,2,3]`):** 0 =
  unresolved/infeasible at locale, 1 = exact, 2 = athlete-listed substitute
  (`resolution_detail.substitute_text`), 3 = nearest-neighbour proxy
  (`resolution_detail.proxy_exercise_id`). `StrengthExercise.resolution_tier` is
  `Literal[1,2,3]`, with the validator: tier 1 ⇒ both fields None; tier 2 ⇒
  `substitute_text` non-None; tier 3 ⇒ `proxy_origin_id` non-None.
- **`_strength_resolution_fields(rx)`** maps a `ResolvedExercise` → the
  `(tier, substitute_text, proxy_origin_id)` triplet (mirrors the shapes
  `locale_assign._swap_to_substitute/_swap_to_proxy` already produce). Unknown
  pick or tier-0 → exact (tier 1) so the payload still constructs; pick
  feasibility is a separate concern the rendered pool already steers.
- **`_apply_strength_resolution(raw_sessions, layer2c_payloads) -> list[str]`**
  builds a per-locale `{exercise_id: rx}` map (+ a cross-locale best-tier
  fallback for a pick whose session locale doesn't carry it — the `exercise_id`
  enum is the cluster-union, locale-agnostic), then mutates each emitted strength
  dict in place. Returns `id@locale` notes for picks that fell back to exact
  (Rule #15 — logged by each caller).
- Both helpers live in **`per_phase.py`** and are imported by the three siblings
  (which already depend on `per_phase`, so no new import cycle; no new module).

**Resolution is per session locale** — the same `exercise_id` can resolve tier-1
at a well-equipped locale and tier-2/3 at a sparse one, so the lookup keys on the
session's `locale_id`.

## 3. Files (4 substantive code + 1 test)

- **`layer4/per_phase.py`** — added `_strength_resolution_fields` +
  `_apply_strength_resolution`; called in `synthesize_phase` before the
  `_build_plan_session` loop; **`SYSTEM_PROMPT`** strength bullet rewritten to
  stop instructing the LLM to populate the tier fields (system derives them).
- **`layer4/single_session.py`** — import + applied to `[session_data]` with
  `{locale: payload}` **only when `layer2c_payload_for_locale is not None`** (the
  locale-agnostic path has no resolution surface — left untouched).
- **`layer4/plan_refresh.py`** — import + applied to `raw_sessions` with
  `dict(layer2_bundle.c)` before the construction loop.
- **`layer4/race_week_brief.py`** — import + applied to `override_data_list` with
  `layer2c_payloads`, after the recovery-repair pre-pass.
- **`tests/test_layer4_strength_resolution_803.py`** (NEW) — 16 cases: the
  helper per tier (incl. tier-0/unknown/empty-string-substitute defensives), the
  pv77 tier-1+`substitute_text` regression (now constructs), per-locale
  resolution, cross-locale fallback, skip of non-strength/empty sessions.

## 4. Tests

- New file + the per_phase/payload/strength-pool/plan-create suites green.
- **Full suite: 2844 passed / 30 skipped** (2 pre-existing Layer3B warnings,
  unrelated). All three sibling synth entry points are exercised end-to-end by
  their own suites **and** `test_layer4_smoke.py` → the wiring (imports +
  `layer2_bundle.c` / `layer2c_payloads` / `layer2c_payload_for_locale` scoping)
  is on covered paths, not just import-safe.

## 5. Live-verify owed (Andy-action — container can't run plan-gen)

- **Regenerate a plan** (Andy's MTB+packraft PGE set, post-#777). Confirm it
  reaches `ready` (no Build block-fumble) and `/admin/logs` shows no
  `StrengthExercise` `ValidationError`. The cache key shifted (prompt edit) so
  the next plan-gen re-synthesizes. This is the real end-to-end confirmation the
  unit suite can't give.
- Optional: a `synthesize_phase … strength resolution defaulted to exact …` line
  appearing would flag an out-of-locale/tier-0 pick worth a look (expected rare).

## 6. Owed / carried

- **Secondary fragility, NOT fixed here (per Rule #16 — separate concern):** an
  over-budget attempt-1 that parse-fails gets no retry, so a single bad block
  call fumbles the plan. #803 removes the *most likely* parse failure; the
  no-retry-on-overbudget structural issue is its own issue if it recurs.
- This fix is the latest in the **plan-#74/#75 generation arc** (#775/#776/#777);
  the Plan-75 regen owed in CARRY_FORWARD now also exercises this fix.
- Carried, unchanged: Plan-75 regen + redump-PR; #778/#779/#780; #767 live-verify
  set; #337 / #698 / #304 items per the prior entries.

### 6.3 Read order for next session (Rule #13)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 7. Session-end verification (Rule #10) — anchor table

| File | Anchor (grep) | Check |
|---|---|---|
| `layer4/per_phase.py` | `def _apply_strength_resolution(` and `def _strength_resolution_fields(` | both defs present |
| `layer4/per_phase.py` | `_apply_strength_resolution(raw_sessions, layer2c_payloads)` | call in `synthesize_phase` |
| `layer4/per_phase.py` | `the system finalizes the substitution tier deterministically` | prompt bullet rewritten |
| `layer4/single_session.py` | `_apply_strength_resolution(` (under `if layer2c_payload_for_locale is not None:`) | import + locale-gated call |
| `layer4/plan_refresh.py` | `_apply_strength_resolution(raw_sessions, dict(layer2_bundle.c))` | import + call |
| `layer4/race_week_brief.py` | `_apply_strength_resolution(override_data_list, layer2c_payloads)` | import + call |
| `tests/test_layer4_strength_resolution_803.py` | file exists | `pytest` full suite 2844 passed / 30 skipped |
