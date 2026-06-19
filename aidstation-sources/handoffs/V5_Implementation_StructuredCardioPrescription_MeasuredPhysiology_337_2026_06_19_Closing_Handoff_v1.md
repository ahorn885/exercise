# #337 Layer 4 — structured cardio prescription (zone-by-duration + measured-physiology grounding) — Closing Handoff

**Issue:** [#337](https://github.com/ahorn885/exercise/issues/337) — "cardio sessions lack structured zone/interval prescription — only vague guidance" (parent #201; empirical from pv=46, 2026-05-30).
**Branch:** `claude/issue-337-8qen2m` — commit `974327b` (code+tests). **PR pending Andy's go (PR-gated).**
**Predecessor:** `handoffs/V5_Implementation_CardioDrillsPool_OtherPaths_SliceC1_C2_Track2_698_2026_06_19_Closing_Handoff_v1.md`.

> **Built across all three synthesizer paths, full suite green at 2752.** #337's structured-`CardioBlock` schema + render were already shipped; this session closed the two real gaps — **prompt-required session structure** and **grounding intensity targets in the athlete's measured HR/power/pace anchors**. Only live-verify is owed.

---

## 1. What happened (in order)

1. **Rule #9 session-start sweep clean** (`verify-handoff.sh` green; predecessor C1/C2 §8 anchors on-disk; tree clean on `claude/issue-337-8qen2m`).
2. **Assessed #337 against on-disk reality before touching anything** (the issue is from 2026-05-30; much structured-cardio work shipped since). Mapped the 3 checklist items:
   - **Item 1 (prompt requires zone-by-duration warm-up/work/cool-down):** *partially done* — the `CardioBlock` schema fully supports it (`block_kind` ∈ warmup/main_set/cooldown/interval_set/transition, `intensity_zone` Z1–Z5, `duration_min`, 9-shape `intensity_target` union, interval fields), but there was **no `# Cardio programming` prompt section** (cardio guidance was 2 terse bullets under `# Output discipline`).
   - **Item 2 (render structured zones):** *done* — `templates/plan_create/view.html:127-155` renders block_kind/duration/zone/intervals/all 9 target shapes; `refresh_view.html` + `suggestion_view.html` too.
   - **Item 3 (tie targets to measured HR zones / Layer 1):** *not done — the real gap.* `Layer1Performance` (`hrmax_bpm`, `lactate_threshold_hr_bpm`, `cycling_ftp_w`, `running_threshold_pace_sec_per_km`, `css_swim_sec_per_100m`) is present in `layer1_payload.performance` but was **never rendered into any synthesizer prompt** → emitted `HRTarget` bpm were ungrounded guesses. Exactly the pv=46 complaint.
3. **Surfaced the assessment + proposed verbatim prompt wording + gut check; Andy ratified (Trigger #1, AskUserQuestion): both items, wording as-is, ALL THREE paths.**
4. **Built** the shared prompt section + render helper and wired all three paths; bumped the cache revision; added tests; full suite green.

## 2. What shipped

Two shared primitives in `layer4/per_phase.py`, imported by the other two paths:

- **`CARDIO_PROGRAMMING_PROMPT_SECTION`** — the ratified `# Cardio programming` SYSTEM_PROMPT section: (1) structure each cardio session as a deliberate `cardio_blocks` sequence with a warm-up/work/cool-down arc where the intent warrants (easy aerobic may be a single main_set; quality sessions carry explicit warm-up+cool-down; durations sum to `duration_min`); (2) **ground every `intensity_target` in the athlete's measured physiology shown in the athlete-context section when present** (HRTarget from HR max / LT-HR, PowerTarget from FTP, PaceTarget from run threshold pace, SwimPaceTarget from CSS), else fall back to RPETarget / a zone-relative range. The athlete-context cross-reference is **path-neutral** (not the literal `=== Athlete context ===`) so one constant fits all three paths' differing section names.
- **`format_measured_physiology(layer1_payload) -> list[str]`** — renders the measured anchors into prompt lines (suppress-on-empty: `[]` when no anchor populated). Helper `_fmt_pace_mmss(sec)` formats pace anchors (`245 → "4:05"`). Lines: `Measured physiology (ground intensity targets in these where present):` + an HR line (`HR max … · LT-HR …`) and/or a power/pace line (`cycling FTP … W · run threshold pace … /km · swim CSS … /100m`).

Path wiring:

- **`layer4/per_phase.py` (plan-create):** `CARDIO_PROGRAMMING_PROMPT_SECTION` spliced into `SYSTEM_PROMPT` between `# Recovery programming` and `# Cardio drills`; `format_measured_physiology` rendered inside `=== Athlete context ===` in `_render_user_prompt` (+ Rule #15 `measured_physiology surfaced=` print).
- **`layer4/single_session.py`:** imports both shared symbols; section spliced into `_SYSTEM_PROMPT` (converted to a paren-wrapped concatenation) before `# Cardio drills`; anchors rendered into `# Athlete context` (+ Rule #15 print).
- **`layer4/plan_refresh.py` (T1/T2/T3):** imports both shared symbols; section appended **unconditionally** to `system_prompt` (general guidance, not pool-gated) + anchors appended as a `=== Measured physiology ===` block to `user_prompt`, both **centralized in `_synthesize_refresh_tier`** so the three tier modules stay untouched (+ Rule #15 print). (Distinct `=== Measured physiology ===` header chosen over `=== Athlete context ===` to avoid colliding with the tiers' existing `=== Athlete profile ===` section.)
- **`layer4/hashing.py`:** `LAYER4_PROMPT_REVISION "12" → "13"` (plan-create + refresh prompts changed → cached plans/refreshes regenerate). single_session needs no bump (ad-hoc, not cache-keyed).

## 3. Ratified decisions (Andy, this session)

1. **Scope:** build **both** item 1 (`# Cardio programming` structure section) **and** item 3 (surface measured anchors + grounding instruction), **wording as-is**, across **all three** synthesizer paths.

## 4. Validation

- **Full suite 2752 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/ -q`): +22 (12 in new `tests/test_layer4_structured_cardio_337.py` [`_fmt_pace_mmss`, `format_measured_physiology` empty/partial/full, `CARDIO_PROGRAMMING_PROMPT_SECTION` presence+coverage], +6 single_session render, +3 plan_refresh end-to-end via `_capturing_caller`, +1 reused).
- No DDL, no migration. Cache: `LAYER4_PROMPT_REVISION 12→13` only.
- **4 substantive code files** (per_phase/single_session/plan_refresh/hashing) + 3 test files — under the 5-file ceiling.

## 5. Manual verification owed + next pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Owed (Andy-action, live-verify — container can't drive plan-gen):**
1. With measured HR/FTP/threshold-pace/CSS set on the athlete profile, generate or refresh a plan → confirm `/admin/logs` (needs `DIAG_TOKEN`) shows `measured_physiology surfaced=True` for the per_phase/refresh path, and a cardio session's `HRTarget` `hr_bpm_low/high` lands inside the athlete's real measured zones (not generic numbers). With **no** anchors set, confirm `surfaced=False` and the synthesizer falls back to RPE/zone-relative ranges (no invented precise bpm).
2. Cache bumped to "13" → the next plan-gen / refresh regenerates.

**Next moves (work these next — Andy 2026-06-19):**
1. **#333 — Plan UI render gaps (pv=46).** The remaining open item is the "Sparse daily view" rendering (its cardio-zone render already shipped via #499; nutrition rendering blocked on #300, weather on #289). Close out what's renderable now.
2. **#295 / #304 — orphaned built-but-not-wired data sweep.** #337's item 3 was a textbook *flavor-B "captured-but-not-threaded Layer 1"* orphan: `Layer1Performance` (`hrmax_bpm`/`lactate_threshold_hr_bpm`/`cycling_ftp_w`/`running_threshold_pace_sec_per_km`/`css_swim_sec_per_100m`) was in `layer1_payload.performance` with zero prompt readers — and **#304's Layer-1 sweep missed it** (it lists pack-load history / network / disclosures, not the performance baselines). This session threaded those in, so note that on #304/#295 and work the rest of the per-field decisions (thread-or-stop-capturing) in the #295 epic.

**Earlier-stated follow-ons (lower priority):**
1. **Integration→`Layer1Performance` measured-zone wire** (#283 Garmin FIT HR decode + #196 unified health-data layer): today the #337 grounding only fires when the athlete *manually* entered their HR max / LT / FTP / threshold pace / CSS. Wiring integration-derived measured zones into `Layer1Performance` would make the grounding fire automatically — its own scope.
2. **`race_week_brief`** also emits intensity targets and was left out of scope here (consistent with the cardio_drills slicing) — a clean copy if ever wanted.

## 6. Deferred edits (Rule #11)

None — fully built across all three ratified paths.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Shared section | `layer4/per_phase.py` | `CARDIO_PROGRAMMING_PROMPT_SECTION = """# Cardio programming` (warm-up/work/cool-down + "ground every intensity_target in the athlete's measured physiology") |
| Shared helper | `layer4/per_phase.py` | `def format_measured_physiology(layer1_payload)` (suppress-on-empty) + `def _fmt_pace_mmss(sec)` |
| Plan-create splice | `layer4/per_phase.py` | `CARDIO_PROGRAMMING_PROMPT_SECTION` in assembled `SYSTEM_PROMPT` (between Recovery/Cardio-drills); `format_measured_physiology(layer1_payload)` in `=== Athlete context ===`; `measured_physiology surfaced=` print |
| single_session | `layer4/single_session.py` | imports `CARDIO_PROGRAMMING_PROMPT_SECTION` + `format_measured_physiology`; `# Cardio programming` in `_SYSTEM_PROMPT`; anchors in `# Athlete context` |
| plan_refresh | `layer4/plan_refresh.py` | imports both; `system_prompt + "\n\n" + CARDIO_PROGRAMMING_PROMPT_SECTION`; `=== Measured physiology ===` appended to `user_prompt` in `_synthesize_refresh_tier` |
| Cache | `layer4/hashing.py` | `LAYER4_PROMPT_REVISION = "13"` |
| Tests | `tests/test_layer4_structured_cardio_337.py` | `TestFormatMeasuredPhysiology`, `TestCardioProgrammingSection`, `TestFmtPaceMmss` |
| Tests | `tests/test_layer4_single_session.py` | `class TestStructuredCardio337` |
| Tests | `tests/test_layer4_plan_refresh.py` | `class TestStructuredCardio337` |
| Suite | `tests/` | `/tmp/venv/bin/python -m pytest tests/ -q` → 2752 passed / 30 skipped |
| Issue | #337 (commented; items 1+3 + render verified done) | — |

## 8. Carry-forward

- **#337 BUILT across all three paths, suite green at 2752.** PR pending Andy's go. Only live-verify owed.
- **race_week_brief = out of scope** (not deferred; clean copy if ever wanted).
- **STILL OWED (carried, unchanged):** #698 C1/C2 live-verify + Part-A item (b); post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.
