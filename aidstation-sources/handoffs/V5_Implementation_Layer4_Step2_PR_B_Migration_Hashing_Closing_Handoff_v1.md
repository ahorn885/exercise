# V5 Implementation — Layer 4 Step 2 (PR-B of 2) Migration + Hashing Closing Handoff

**Session:** Single chat. Second code PR of the Layer 4 implementation arc. Executes `Layer4_Spec.md` §14.3.4 Step 2 (second half) — `plan_versions` migration per §7.11 + `layer4/hashing.py` canonical-JSON + cache-key helpers per §9.1. Closes Step 2 entirely.
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_Layer4_Step2_PR_A_Payload_Closing_Handoff_v1.md` (Step 2 PR-A — payload schema scaffolding per §7 + D1 amendment).
**Branch:** `claude/implement-payload-closing-JfYd7` (harness-pinned for this session — deviates from the predecessor handoff §5 recommended `claude/layer4-hashing-5NYk8` per harness override; Andy confirmed leaving the harness-pinned name as-is at session start).
**Status:** 🟢 One substantive code commit + one bookkeeping commit on branch. 159 pytest cases green (65 PR-A + 94 PR-B; 0.26s combined). PR ready to open. Step 2 of `Layer4_Spec.md` §14.3.4 is now COMPLETE; implementation track advances to Step 3 (deterministic validator harness per §5.4).

---

## 1. Session-start verification (Rule #9)

Predecessor (Step 2 PR-A) handoff §3 + §7 claimed: `layer4/__init__.py` re-exports 32 public types; `layer4/payload.py` defines 20 §7 types + 9 IntensityTarget shapes + cross-field validators; `tests/test_layer4_payload.py` has 65 tests passing in 0.19s; `requirements.txt` includes `pydantic>=2.5`; `Layer4_Spec.md` §7.3 + §7.3.1 + §7.12 + §7.14 D1 amendment applied; PR #68 merged on `origin/main` at `0539857`; backlog at v39; CLAUDE.md last-shipped at PR-A.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `layer4/__init__.py` exists; imports cleanly | `python3 -c "from layer4 import ..."` | ✅ |
| `layer4/payload.py` has 20 §7 types + 9 IntensityTarget types | grep `^class` count | ✅ |
| `tests/test_layer4_payload.py` 65 tests pass | `pytest tests/test_layer4_payload.py` (0.19s) | ✅ |
| `requirements.txt` has `pydantic` | grep | ✅ |
| `Layer4_Spec.md` §7.11 plan_versions DDL present (line 587) | grep | ✅ |
| `Layer4_Spec.md` §9.1 cache-key formulas present (line 1155) | grep | ✅ |
| `init_db.py` `_PG_MIGRATIONS` exists at line 469 | grep | ✅ |
| PR #68 merged on `origin/main` at `0539857` | `git log origin/main` | ✅ |
| Backlog at v39 (latest file) | `ls Project_Backlog_v*.md` | ✅ |
| Working tree clean | `git status` | ✅ |
| No Layer 4 items in `PR_Verification_Status.md` | grep | ✅ |

**No drift found.** PR-A state on disk matches the handoff narrative. Branch is harness-pinned `claude/implement-payload-closing-JfYd7` (the handoff §5 recommended branch name was `claude/layer4-hashing-5NYk8`; flagged to Andy at session start; Andy confirmed leaving the harness-pinned name).

---

## 2. Session narrative — implementation pass, two judgment calls, no spec amendments

Andy opened with "lets work" after I confirmed PR-B scope from the predecessor handoff §5. No architectural picks needed — the scope was already settled (§7.11 verbatim DDL + §9.1 cache-key formulas). Implementation was the entire session.

### 2.1 Two silent judgment calls (flagged to Andy mid-session)

1. **Sort-key extension for `compute_prior_plan_session_window_hash`.** Spec §9.1 says sort by `(date, session_index_in_day)`. I extended to `(date, session_index_in_day, plan_version_id)`. Rationale: the ±7-day context window per §3.2 can span plan_version_id boundaries (a T3 refresh window that crosses a prior plan-revision boundary), and two `(date, idx)` pairs from different plan_version_ids would otherwise rely on Python's stable-sort + input-order determinism for hash stability. Spec-equivalent in the common case (a single plan_version_id window); safer in the cross-version edge. Flagged to Andy; no objection.

2. **Strict `{a,b,c,d,e}` validation in `compute_layer2_bundle_canonical_hash`.** Spec §9.1 narrative says "for attr ∈ {'a','b','c','d','e'} ... null entries preserved" — I read that as a closed-set contract and raise `ValueError` on subset or superset. Loud over silent stance. Flagged to Andy; no objection.

### 2.2 No spec amendments — trigger #5 didn't fire

The predecessor handoff §5 forward-pointer note flagged: "if any §9.1 cache-key formula surfaces a contract gap, route through `/plan` mode per the Andy 2026-05-17 directive." That activation case didn't materialize this session — the §9.1 formulas land as-spec'd. The §7.11 DDL is also verbatim implementation-of-spec, not a contract change. Trigger #5 had a clean don't-fire result.

This is the first session in the Layer 4 implementation arc with a clean don't-fire on trigger #5. The Andy 2026-05-17 amendment-authoring-also-goes-through-`/plan`-mode directive remains preserved going forward.

### 2.3 Branch deviation from handoff §5 recommendation

Harness pinned the session to `claude/implement-payload-closing-JfYd7` (the name carries the PR-A closing handoff stem, despite the PR-B scope). Handoff §5 recommended `claude/layer4-hashing-5NYk8`. Flagged to Andy at session start; Andy confirmed leaving the harness-pinned name as-is. No rename performed.

---

## 3. Files shipped this session

One substantive code commit + one bookkeeping commit on `claude/implement-payload-closing-JfYd7`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `init_db.py` | Modified | `plan_versions` table + 2 indexes appended to `_PG_MIGRATIONS` per `Layer4_Spec.md` §7.11 verbatim DDL. Wrapped with `IF NOT EXISTS` for migration idempotence per existing convention. 19 lines added. |
| 2 | `layer4/hashing.py` | New | ~250 lines. Pure-function module; 0 I/O, 0 state. Three layers: (1) `canonical_json` + `_to_jsonable` walker; (2) bundle-hash helpers (`compute_payload_hash`, `compute_layer2c_bundle_hash`, `compute_layer2_bundle_canonical_hash`, `compute_prior_plan_session_window_hash`); (3) per-entry-point cache-key builders (`plan_create_key`, `plan_refresh_key`, `single_session_synthesize_key`, `race_week_brief_key`) per §9.1 formulas. |
| 3 | `layer4/__init__.py` | Modified | 9 hashing re-exports added alongside the 32 existing payload re-exports; alphabetized in `__all__`. |
| 4 | `tests/test_layer4_hashing.py` | New | 94 tests, 100% pass. Coverage in §4.3 below. |
| 5 | `aidstation-sources/CLAUDE.md` | Modified | Layer 4 pipeline row updated ("Step 2 PR-A + PR-B landed 2026-05-17"); last-shipped narrative replaced with PR-B summary (PR-A demoted to predecessor); Backlog ref v39 → v40; new authoritative-current-files row for Layer 4 implementation; Next-forward-move points at Step 3 validator harness as the architect-recommended primary. |
| 6 | `aidstation-sources/Project_Backlog_v40.md` | New | Copy of v39 + new v40 file-revision-header entry; v39 demoted inline as most-recent predecessor; v37 moved under "Predecessor revisions:" header. |
| 7 | `aidstation-sources/handoffs/V5_Implementation_Layer4_Step2_PR_B_Migration_Hashing_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Over the 5-file ceiling intentionally** (7 files total — 4 substantive code + 3 bookkeeping in 1 commit; precedented by PR-A's 8-file bundle + PR17's 7-file bundle). Andy explicitly directed the bookkeeping bundle into this PR at end-of-session via "1" pick for the bundling option.

---

## 4. What the code now commits to

### 4.1 `plan_versions` schema (lifts D-64 §7.2 stub)

Per `Layer4_Spec.md` §7.11 verbatim. Columns: `id BIGSERIAL PRIMARY KEY`, `user_id INTEGER NOT NULL REFERENCES users(id)`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `created_via TEXT NOT NULL CHECK (created_via IN ('plan_create','plan_refresh_t1','plan_refresh_t2','plan_refresh_t3','single_session_synthesize'))`, `scope_start_date DATE NOT NULL`, `scope_end_date DATE NOT NULL`, `pattern CHAR(1) NOT NULL CHECK (pattern IN ('A','B'))`, `superseded_at TIMESTAMPTZ`, `superseded_by_version_id BIGINT REFERENCES plan_versions(id)`, `notes JSONB`. Two indexes: `plan_versions_user_created_idx ON (user_id, created_at DESC)` for recent-plan lookups; `plan_versions_user_scope_idx ON (user_id, scope_start_date, scope_end_date)` for date-range lookups. The denormalized `superseded_at` + `superseded_by_version_id` columns support the revert UX per the §7.11 narrative; the per-day version pointer (per D-64 §6.3) is implemented by `plan_session.date` + `plan_session.plan_version_id` (not by `superseded_at`).

### 4.2 `layer4.hashing` API surface

**`canonical_json(obj) -> str`** — Recursive `_to_jsonable` walker handles pydantic `BaseModel.model_dump(mode='json')` round-trip + dict + list/tuple (tuple → list) + set/frozenset → sorted list + date/datetime → ISO 8601 + Decimal → str. `json.dumps` with `sort_keys=True, separators=(',', ':'), ensure_ascii=False` for byte-stable output.

**Bundle-hash helpers** (callers compute these once per layer/window and pass the result to the per-entry-point cache-key builders):

- `compute_payload_hash(payload) -> str` — The per-layer-hash building block (e.g., `layer1_hash = compute_payload_hash(layer1_payload)`).
- `compute_layer2c_bundle_hash(locale_to_hash) -> str` — Used by `plan_create_key` + `race_week_brief_key`.
- `compute_layer2_bundle_canonical_hash(layer2_hashes) -> str` — Used by `plan_refresh_key`. STRICT key validation: `layer2_hashes` MUST have keys exactly `{'a','b','c','d','e'}`; subset / superset raises `ValueError`. Null entries preserved per §9.1's "T1-cascade-with-2A-re-run differentiates from T1-cascade-with-no-Layer-2-re-run" requirement.
- `compute_prior_plan_session_window_hash(sessions) -> str` — Used by `plan_refresh_key` + `race_week_brief_key`. Spec sort key is `(date, session_index_in_day)`; extended to `(date, session_index_in_day, plan_version_id)` for cross-version safety (see §2.1 above).

**Per-entry-point cache-key builders** (all use keyword-only args; all return SHA-256 hex string):

- `plan_create_key(...)` — 16 component args; concatenated via `||` then SHA-256.
- `plan_refresh_key(...)` — 16 component args. `model_seam_reviewer` is `str | None` (None on Pattern B refresh — T1, T2, T3 intra-phase); `parsed_intent_hash` is `str | None`. Both default-collapse `None → ''` per §9.1 to prevent gratuitous Pattern-B cache misses.
- `single_session_synthesize_key(...)` — 11 component args. `request` is canonical-JSON-encoded; `layer2c_locale_hash` is `str | None` (None on quick_equipment mode); collapses `None → ''`.
- `race_week_brief_key(...)` — 15 component args. `today()` intentionally absent — `days_to_event` shifts daily so the orchestrator invalidates `race_week_brief` caches at midnight UTC per §9.3.

**§9.4 rebinding semantics honored:** `plan_version_id` + `suggestion_id` intentionally absent from ALL key signatures (allocated per call by orchestrator; rebinding on hit). None of the helpers above accept them.

### 4.3 Test coverage notes

94 tests organized into 10 groups:

1. **canonical_json basics + type handling × 10** — sorted keys; no whitespace; date ISO; datetime ISO with tz; Decimal as str; set sorted; tuple to list; nested dict sorted; pydantic model dump; nested pydantic with IntensityTarget union.
2. **compute_payload_hash × 5** — determinism; field-level differentiation; IntensityTarget union shape differentiation (HRTarget vs PowerTarget at same numeric values flip the hash — smart-union shape is hashed, not just values); dict-form input ↔ model dump equivalence; pace target round-trip.
3. **compute_layer2c_bundle_hash × 3** — dict insertion order irrelevant; content differentiation; membership differentiation.
4. **compute_layer2_bundle_canonical_hash × 4** — strict {a,b,c,d,e} validation rejects subset + superset; null preservation (T1 with 2A re-run ≠ T1 with no re-run); dict order irrelevant.
5. **compute_prior_plan_session_window_hash × 4** — sort-order irrelevance (forward vs reverse input); content differentiation; empty list determinism; same-day different-index handling.
6. **plan_create_key × 18** — determinism; etl_version_set dict order irrelevant; parametrized dependency-on-each-component for all 16 inputs (mutating any input flips the hash).
7. **plan_refresh_key × 17** — determinism; None ≡ '' for `model_seam_reviewer` (Pattern B refresh) + `parsed_intent_hash`; Pattern A seam-reviewer model differentiation; parsed_intent set differentiation; parametrized dependency for 14 inputs.
8. **single_session_synthesize_key × 14** — determinism; request dict order irrelevant; None ≡ '' for `layer2c_locale_hash`; parametrized dependency for 11 inputs.
9. **race_week_brief_key × 16** — determinism; parametrized dependency for 15 inputs.
10. **cross-helper sanity × 1** — `plan_create_key` ≠ `race_week_brief_key` at overlapping inputs (component lists differ structurally — race_week_brief lacks `plan_start_date` + `model_seam_reviewer`; uses single `model` slot vs synthesizer/reviewer split).

Combined run with PR-A: 159 tests, 0.26s.

---

## 5. Next session pointers — Layer 4 implementation Step 3

Architect-recommended next per `Layer4_Spec.md` §14.3.4 step 3 + `CLAUDE.md` "Next forward move":

### Step 3 scope: deterministic validator harness per §5.4

§5.4 is now complete including the v38 retro-bundled C1 7-row validator rule rows (`taper_phase_intent_violation_*`, `kit_manifest_inputs_incomplete`, `race_plan_segments_unordered_*`, `fueling_strategy_2e_tier_mismatch_*`, `contingency_anchor_category_missing_*`, `phase_date_out_of_range_*`, `daily_window_fit_*`). No spec amendments expected for the validator harness.

Expected files (~3, well under ceiling):

1. **`layer4/validator.py`** — pure-function rule set. Each rule: `(payload: Layer4Payload, context: dict) -> list[RuleFailure]`. Rules grouped by category: volume bands (per phase × per discipline), ACWR forward projection, intensity distribution drift, injury exclusions, two-hards-with-recovery, weekly aggregates (T2 scope), C1 amendment rules (Taper-phase intent, kit manifest, race plan segments, fueling strategy, contingency anchors, phase date range, daily window fit).
2. **`layer4/__init__.py`** — re-export the validator entry point + the `RuleFailure` / `ValidatorResult` types (already exported from payload).
3. **`tests/test_layer4_validator.py`** — per-rule pytest fixtures + happy-path × N + failure-mode × N per rule. Match the parametric style established in `test_layer4_hashing.py` for the cache-key dependency tests.

### Operating notes for next session

1. **First re-read** (Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load. Rule #9 verification needs the full CLAUDE.md context.
2. **Second re-read**: this handoff.
3. **Third re-read**: `Layer4_Spec.md` §5.4 (the full deterministic validator rule list — both v1 rules + the retro-bundled C1 7 new rows) + §5.5 (capped retry semantics — informational; validator harness doesn't implement the retry loop, that's per-entry-point integration in Step 4) + §7 (payload schema — consumed as input shape by the validator).
4. **Branch:** cut `claude/layer4-validator-NEWSUFFIX` off `origin/main` after PR-B merges (or use whatever the harness pins for the next session).
5. **Stop-and-ask trigger #5:** §5.4 rule set is now complete after the v38 retro-bundled C1 amendments; validator harness implementation should NOT surface contract gaps. But if a rule's pseudo-code language in the spec is ambiguous enough to require a substantive interpretation choice (vs straightforward implementation), route through `/plan` mode per the Andy 2026-05-17 amendment-authoring directive.
6. **Test convention:** put `test_layer4_validator.py` at top-level `tests/` alongside `test_layer4_payload.py` + `test_layer4_hashing.py` (matches PR-A + PR-B convention).
7. **Per-rule severity:** §5.4 specifies `blocker` vs `warning` severity per rule. The harness must honor the per-rule severity in the `RuleFailure` emission; the capped-retry-with-best-effort path (§5.5) treats `blocker` as retry-triggering, `warning` as observation-bubbling.

---

## 6. Open items / decisions pinned this session

### 6.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Sort-key extension `(date, idx, plan_version_id)` for `compute_prior_plan_session_window_hash` | Claude 2026-05-17 (Andy notified mid-session; no objection) | Spec-equivalent in single-version window common case; safer in cross-version edge per §3.2 ±7-day context. |
| 2 | Strict `{a,b,c,d,e}` validation in `compute_layer2_bundle_canonical_hash` (raise on subset/superset) | Claude 2026-05-17 (Andy notified mid-session; no objection) | §9.1 closed-set contract; loud over silent stance. |
| 3 | Branch name stays harness-pinned `claude/implement-payload-closing-JfYd7` (not the handoff §5 recommended `claude/layer4-hashing-5NYk8`) | Andy 2026-05-17 (confirmed at session start) | Harness override; no rename performed. |
| 4 | Bookkeeping bundled into PR-B (CLAUDE.md + backlog v40 + closing handoff) | Andy 2026-05-17 end-of-session "1" pick | Precedented by PR-A's 8-file bundle + PR17's 7-file bundle. |

### 6.2 Open items (none blocking Step 3)

- The Pattern-A per-phase cache (`phase_key[i]` per §9.2) is NOT implemented in `layer4/hashing.py` this session — it's an orchestrator-side concern (the chain depends on the per-phase synthesis output; Layer 4 itself doesn't compose the chain). Will land when the Pattern-A orchestration code is built (per §14.3.4 Step 6). The cache-key builders shipped this session are the per-call keys per §9.1; the per-phase derivation is built on top.
- `SingleSessionRequest` shape (referenced in `single_session_synthesize_key`'s `request` arg) is not formally defined in this codebase yet — D-63 §4.3 specs it, but no Python `@dataclass` or pydantic model exists. Per `canonical_json`'s polymorphism, a dict or any pydantic model passes through cleanly. When D-63 implementation lands (per §14.3.4 Step 4a), define `SingleSessionRequest` and use it directly.
- The `etl_version_set` dict shape (used by all 4 cache-key builders) is also not formally typed — passed through as `dict[str, str]`. v1 implementation should standardize on a sealed `dataclass` or pydantic model when the orchestrator code lands; until then, the dict-shape contract is enforced only at runtime via `canonical_json`'s serialization.

---

## 7. Session-end verification (Rule #10)

Final pass before pushing the bookkeeping commit:

| Check | Result |
|---|---|
| `init_db.py` `_PG_MIGRATIONS` has `plan_versions` CREATE + 2 indexes | ✅ grep |
| `init_db.py` parses cleanly | ✅ `python3 -c "import ast; ast.parse(open('init_db.py').read())"` |
| `layer4/hashing.py` exports `canonical_json` + 4 cache-key builders + 4 helpers | ✅ inspection |
| `layer4/__init__.py` re-exports all 9 hashing names | ✅ inspection |
| `tests/test_layer4_hashing.py` 94 tests pass | ✅ `pytest tests/test_layer4_hashing.py` |
| `tests/test_layer4_payload.py` 65 tests still pass (regression) | ✅ `pytest tests/test_layer4_payload.py` |
| Combined: 159 tests pass | ✅ `pytest tests/` (0.26s) |
| `layer4` package imports cleanly | ✅ `python3 -c "from layer4 import plan_create_key, canonical_json, HRTarget"` |
| `aidstation-sources/CLAUDE.md` Backlog ref reads `Project_Backlog_v40.md` | ✅ grep |
| `aidstation-sources/CLAUDE.md` Layer 4 row mentions "Step 2 PR-A + PR-B landed" | ✅ grep |
| `aidstation-sources/CLAUDE.md` Last-shipped is PR-B; PR-A demoted to first Predecessor | ✅ inspection |
| `aidstation-sources/CLAUDE.md` Next-forward-move recommends Step 3 validator harness | ✅ grep |
| `aidstation-sources/Project_Backlog_v40.md` exists; file-revision-header is v40; v39 inline-demoted | ✅ inspection |
| PR-B substantive commit `2a5d221` pushed to `origin/claude/implement-payload-closing-JfYd7` | ✅ `git log origin/...` |

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned. Unchanged.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; no new PR §5.0 surface added (Layer 4 implementation PRs don't have a `/profile` UX walk; the `plan_versions` migration is a backend schema change with no UI surface yet — surfaces when Layer 4 LLM-call integration lands per §14.3.4 Step 4).

---

**End of handoff.**
