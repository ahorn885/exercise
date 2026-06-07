# V5 Implementation — Track 2 Determinism-First Layer 4 Synthesis: slice 2d shipped (rx_engine post-hoc wiring + Rules 2/7 demoted) — Track 2 CLOSED

**Date:** 2026-06-06
**Branch:** `claude/eloquent-gauss-fE3PC`
**PR:** #462 (squash-merged to `main`, commit `a0b7b20`; prod deploy `dpl_9KhyJjWBe3L3BesWEesFcgvVuoBk` READY on `aidstation-pro.vercel.app`).
**Issues:** Track 2 (#429) of the 3-track redesign epic #427. Spec `Layer4_DeterminismFirst_Synthesis_Design_v1.md` v1 (APPROVED; status amended to "2a + 2b + 2c + 2d shipped — Track 2 closed"). Slice 2d shipped this session; 2c.2 (cardio routing) + layer0 vocab adds still owed (see §5).

---

## ⚡ Diagnostic token (read first — every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` — WebFetch 403s (Vercel deployment protection); fetch via the **Vercel MCP `web_fetch_vercel_url`** tool. Untruncated runtime logs: Vercel dashboard (team `team_rkZGxltBw2ykWtrIPCYy16JZ`, project `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`); the runtime-log MCP truncates the message column (Rule #14).

---

## 1. What this session was

Andy named slice 2d as the next move after 2c shipped. Slice 2d is the final slice of Track 2: post-hoc `rx_engine` wiring (precise baseline overwrites synthesizer-emitted `load_prescription` text; first-exposure exercises get a deterministic RPE template) + the remaining §8 validator demotions (Rules 2 + 7).

No stop-and-ask triggers fired — the spec (§7 + §8 table) had already locked the decisions during slice-spec sign-off; this session was straightforward execution. Track 3 dependency acknowledged at the call site (rx lookup keyed by exercise name in v1; Track 3 catalog migration will lift this to layer0 ids).

Suite 2051 → 2084 passed / 12 skipped (+33 net, -4 skipped; the 4 skipped re-baselined when the renamed retry-trigger sessions now pass a stricter validator path).

## 2. Shipped

### 2.1 — `rx_engine.py` new `current_rx` reader

```python
def current_rx(db, user_id, exercise_name) -> dict | None:
    """Returns {sets, reps, weight_lbs, duration_sec, movement_pattern} or None."""
```

- Pure SELECT against `current_rx WHERE user_id=? AND exercise=?`. No side effects.
- Returns None for the sparse case (row exists but both weight + duration are NULL) so the caller falls through cleanly to first-exposure rather than rendering an empty prescription.
- Track 3 dependency documented in-docstring: keyed by exercise NAME (not layer0 EX-id) in v1 because that's what the legacy `current_rx.exercise TEXT` column holds. After Track 3 migrates rx storage to layer0 ids, the reader bumps to id-keyed; until then a layer0-only exercise (not present in `public.exercise_inventory`) falls through to first-exposure (acceptable v1 behavior, per spec §7).

### 2.2 — `layer4/rx_wire.py` NEW (§7 pipeline)

```python
def apply_current_rx(payload, db, user_id, layer2c_payloads)
    -> tuple[Layer4Payload, RxWireDiagnostic]:
```

Per `StrengthExercise` across `payload.sessions[*].strength_exercises[*]`:

1. **`current_rx` hit** → overwrite `load_prescription` with `"{sets} × {reps} @ {lbs} lbs"` (or `"{sets} × {dur}s"` for duration-target exercises like Plank). Whole-number lbs rendering — `187.5 → "188 lbs"` reads cleaner than `"187.5 lbs"`.
2. **First-exposure** (no row, OR row with sparse data) → classify via `_classify_category` into one of 5 categories (compound_barbell / compound_dumbbell / accessory_dumbbell / accessory_cable / bodyweight), write the calibration template (e.g. `"Calibration set — pick a weight that feels RPE 6 for 8 reps; log to set baseline"`), append `first_exposure` to `coaching_flags` (idempotent — won't double-append if already present).

**Classifier (deterministic, no LLM):**
- Layer-2C `tier ∈ {0, 3}` → `bodyweight` (the substitution/improvised band — the most important signal).
- Else inspect canonical exercise NAME for equipment cue (`"barbell"` → compound_barbell; `"dumbbell"` → compound/accessory_dumbbell based on movement_patterns; `"cable"` / `"machine"` → accessory_cable; `"bodyweight"` → bodyweight).
- Compound = a movement pattern in `{squat, hinge, push, pull, lunge}`.
- Default when no cue is found: `bodyweight` (conservative — the template is "max reps with 2 RIR" which never asks the athlete to guess a load).

**Identity-preserving short-circuit (load-bearing):** when no exercises were touched (no current_rx hit + no first-exposure write), `apply_current_rx` returns the ORIGINAL payload object — not a `model_copy`. This matches `_apply_locale_assign`'s contract for orchestrator unit tests that round-trip a sentinel via `assert result is sentinel`.

**Degraded pass-through:** a per-exercise `try/except` around the `current_rx` lookup catches db errors; the exercise's original `load_prescription` survives + the outcome records `path=skipped`. An rx-wire defect can never wedge plan generation.

**`RxWireDiagnostic`** (Rule #14 observability): `outcomes[]` (per-exercise `ExerciseRxOutcome`) + `current_rx_hits` + `first_exposure_count` + `skipped_count`. `to_metadata()` returns a JSON-safe dict for `synthesis_metadata` inclusion under key `track2_slice2d_rx_wire`. Every decision is grep-prefixed `rx_wire:` in the logger.

### 2.3 — `layer4/orchestrator.py` wire-in

NEW `_apply_rx_wire(db, user_id, payload, layer2c_payloads)` mirrors `_apply_locale_assign`'s degraded pass-through pattern. Wired into both `orchestrate_plan_create` and `orchestrate_plan_refresh` AFTER `_apply_locale_assign` on the same hydrated payload — locale substitutions decided by 2c can change which exercise we look up rx for, so rx wiring must see the post-substitution exercise list.

The orchestrator is the natural call site for the same reason 2c picked it (already has `db` + `user_id` in scope without expanding the synthesizer signatures). The spec §10 slice-2d row was updated to reflect that — the original "Call from `plan_create.py` + `plan_refresh.py`" instruction is now superseded.

### 2.4 — `layer4/validator.py` demotions (Rules 2 + 7)

- `_rule_acwr` (Rule 2): blocker-tier collapsed to warning. Single tier now — anything outside the ±20pp band emits warning, not blocker. The deterministic periodization ramp + Bosquet taper (`layer4/periodization.py`) handle the real ACWR cases; this rule stays as advisory drift detection.
- `_rule_injury_violation` (Rule 7): severity blocker → warning. The 2D-exclusion is enforced structurally at the slice-2a tool-schema enum (`compute_feasible_pool_ids` subtracts excluded ids), so injury-excluded exercises can't reach the payload through the normal synthesis path. The rule stays as an edge-case advisory for hand-edited / legacy-cached payloads.
- Rule 7b (`_rule_injury_accommodation_violation` / `_check_modality`) was already warning-only — confirmed via code read; no edit needed. Spec §8 line 933 comment already documented this.

### 2.5 — `layer4/__init__.py` re-exports

New public names: `apply_current_rx`, `RxWireDiagnostic`, `ExerciseRxOutcome`.

### 2.6 — Tests

- **NEW `tests/test_layer4_rx_wire.py`** — 19 tests:
  - `TestCurrentRxHit` × 4 (lbs render, whole-number rounding, duration-only render, sparse-row fall-through)
  - `TestFirstExposure` × 7 (each of 5 templates + flag-idempotent + unknown-exercise → bodyweight default)
  - `TestClassifyCategory` × 4 (tier 0/3 override + machine cue + bodyweight default)
  - `TestNonStrengthUntouched` × 2 (cardio + rest pass-through, no diag outcomes)
  - `TestDegradedDb` × 1 (per-exercise try/except preserves original prescription)
  - `TestDiagnosticMetadata` × 1 (to_metadata shape)
- **Updated `tests/test_layer4_validator.py`** — 2 severity-assertion tests renamed (`_blocker` → `_warning`) for Rules 2 + 7; 1 driver test (`test_driver_accepted_false_on_blocker`) re-pointed to Rule 12 (`discipline_excluded`, still blocker) as the blocker-driving rule.
- **Updated `tests/test_layer4_plan_refresh.py`** + **`tests/test_layer4_single_session.py`** — `TestCappedRetry` switched retry-trigger blockers from Rule 7 (now warning) to Rule 12 (`discipline_excluded`, plan_refresh) / Rule 6c (`session_locale_not_in_cluster`, single_session). Helper name `_injury_violating_session` retained with an updated docstring (call sites read identically; the only thing tested is "validator blocker → retry fires").
- **Final suite: 2084 passed / 12 skipped (+33 net from slice 2c's 2051 / 16).**

## 3. Stop-and-asks this session

None. The spec §7 + §8 had locked the decisions during slice-spec sign-off; the trigger checks (LLM prompt design, data padding, cross-layer surface, HITL gate, architectural alternative, status promotion) all came up empty for slice 2d:
- No LLM in the rx_wire path — templates are deterministic; classification is a deterministic name+pattern lookup.
- No new vocabulary/exercise entries.
- No schema/DDL changes (the `current_rx` table already exists).
- No HITL gate touched.
- The single non-obvious architectural question (key rx lookup by exercise name vs layer0 EX-id) was already resolved in the spec §7 Track 3 dependency note.

## 4. Owed (Andy's hands)

> Slice 2d is pure-function + post-synth — no schema DDL. The slice-2a/2b/2c cold PGE plan run still owed (since the 2a+2b session) is the same proof + now ALSO covers 2d. New addition: confirm the `synthesis_metadata.track2_slice2d_rx_wire` block appears in the diag JSON.

1. **Re-run a cold PGE plan.** Combined Track 1 + slice 2a + 2b + 2c + 2d win condition:
   - **From slice 2c (existing, still owed):** `synthesis_metadata.track2_slice2c_locale_assign` block per session; `path=kept` most cases; LLM substitute counter 0-or-very-low; insufficient_rest_* warnings if a phase week is below expected; rest_spacing_* / schedule_violation_* rows are `severity=warning`.
   - **From slice 2d (NEW):** `synthesis_metadata.track2_slice2d_rx_wire` block per session; for Andy specifically (test athlete, has logged strength) most strength exercises should show `path=current_rx` with the precise lbs render. Layer0-only exercises (no public-catalog name match yet) should show `path=first_exposure` with a category-keyed template + `first_exposure` coaching flag.
   - **From slice 2d demotions:** any `acwr_*` or `injury_violation_*` rows in the diag should be `severity=warning`, not blocker.
2. **(Optional)** if `current_rx` lookup misses for an exercise Andy HAS logged (rendered as first-exposure unexpectedly), pull a sample exercise_name + check casing/punctuation drift between layer0 and `current_rx.exercise`. That's the Track 3 lift in advance — file as a 2d.QA observation.

## 5. Next move

Track 2 is closed. Remaining owed work in priority order:

- **Slice 2c.2 (final Track 2 follow-up, blocked on layer0 vocab):** cardio-session route-locale routing. Extend `assign_locales` with `_DISCIPLINE_REQUIRED_TERRAINS` map + nearest-cluster-locale lookup. Gated on the layer0 vocab adds below.
- **Layer 0 vocab adds (Andy 2026-06-06, slice 2c follow-up):**
  - NEW `TRN-017` row "Off-Trail / Bush" — overland nav through unmaintained brush.
  - RENAME `TRN-007` "Technical Rock" → "Technical Rock/Scree".
  - Trigger #3 cross-layer. Own micro-PR: `etl/layer0/extractors/vocabulary.py` + ETL migration + Neon re-run + Layer0_ETL_Spec edit.
- **Snow-sports routing semantics** (Andy 2026-06-06, open design call): D-018 Mountaineering route on Mountain/Alpine (TRN-005) OR Snow/Winter Alpine (TRN-012), or snow-only? Resolve before 2c.2 locks the map.
- **Track 3 (#430) — D-52 catalog migration** (parallel/after Track 2): retire `public.exercise_inventory`/`exercise_equipment`/`equipment_items` → `layer0.*`; restores the v1 references/purchases surfaces degraded in Track 1. Also unblocks the discipline→required_terrain layer0 column lift AND lets `rx_engine.current_rx` lift from name-keyed to id-keyed.

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (slice 2c.2 + layer0 vocab + Track 3 pending)
4. This handoff (diagnostic token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Slice 2d shipped, spec status updated | `aidstation-sources/Layer4_DeterminismFirst_Synthesis_Design_v1.md` | `grep -n "2a + 2b + 2c + 2d shipped — Track 2 closed" Layer4_DeterminismFirst_Synthesis_Design_v1.md` |
| Rx wire pipeline + classifier + templates | `layer4/rx_wire.py` | `grep -n "def apply_current_rx\|def _classify_category\|_FIRST_EXPOSURE_TEMPLATES\|class RxWireDiagnostic" layer4/rx_wire.py` |
| `current_rx` reader | `rx_engine.py` | `grep -n "def current_rx" rx_engine.py` (1 hit expected) |
| Orchestrator wire-in | `layer4/orchestrator.py` | `grep -n "_apply_rx_wire\|apply_current_rx" layer4/orchestrator.py` (6 hits expected — import + def + 2 docstring refs + 2 call sites) |
| Validator demotions | `layer4/validator.py` | `grep -n "Track 2 slice 2d" layer4/validator.py` (2 hits expected — Rules 2 and 7) |
| `__init__.py` re-exports | `layer4/__init__.py` | `grep -n "apply_current_rx\|RxWireDiagnostic\|ExerciseRxOutcome" layer4/__init__.py` |
| Test coverage | `tests/test_layer4_rx_wire.py` | full suite 2084 passed / 12 skipped (+33 net) |

## 7. Mechanically-applicable deferred edits

None at slice-2d scope. The 2c.2 cardio routing requires the layer0 vocab adds first; that's a separate spec-first session.

## 8. Track 2 closeout summary

After 4 slices (2a → 2b → 2c → 2d), Track 2 retires the feasibility-shaped half of the Layer 4 fragility / quality blockers from the 3-track redesign:

| Slice | Lever |
|---|---|
| 2a | Tool-schema enum on `exercise_id` — out-of-pool picks structurally impossible (Rule 6a deleted). |
| 2b | Deterministic session-count grid + phase-dependent intensity split; Rule 1 `volume_band` demoted to warning. |
| 2c | Deterministic STRENGTH locale assignment (majority-fit → pattern-match → tier-3 proxy → small-call Haiku LLM); deterministic rest detection; Rules 3 + 11 demoted to warning. |
| 2d | Deterministic rx wiring — `current_rx` overwrites synthesizer text; first-exposure category-keyed template. Rules 2 + 7 demoted to warning. |

Remaining blockers in the validator suite are now exclusively **structural** (`session_multi_locale`, `session_locale_not_in_cluster`, `two_per_day`, `discipline_excluded`, schema_violation) — the retry surface shrinks from ~10 classes to 4, all real integrity violations not heuristic misses. The "fragile validator-driven retry death loop" pattern from pv=39 → pv=56 is structurally retired.

The cold PGE plan run is the proof — owed Andy's-hands, win condition specified in §4 above.
