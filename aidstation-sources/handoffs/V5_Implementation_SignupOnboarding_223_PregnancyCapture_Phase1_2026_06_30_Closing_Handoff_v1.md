# Closing Handoff — Sign-up/Onboarding Phase 1: #223 — Pregnancy Status Capture
**Date:** 2026-06-30  
**Branch:** `claude/pack-load-weighting-phase1-uy2kfz`  
**Commit:** `dc840d5`  
**PR:** NOT opened — pushed + bookkept, awaiting Andy's go (project rule: no auto-open)  
**Issue:** [#223](https://github.com/ahorn885/exercise/issues/223)  
**Epic:** [#246](https://github.com/ahorn885/exercise/issues/246)  
**Predecessor handoff:** `V5_Implementation_SignupOnboarding_1067_PackLoadWeighting_Phase1_2026_06_30_Closing_Handoff_v1.md`

---

## §1 — What shipped

**Capture-only** implementation of issue #223 — the `layer2e` HITL-gate half is explicitly deferred (#518, stop-and-ask trigger #4).

The existing `health_screening.flags` JSONB array already captures pregnancy status as `PREGNANCY` flag (Q8 in the screening flow, constant `PREGNANCY_FLAG = "PREGNANCY"`). This session wired that data into Layer 1 and added an explicit profile-edit toggle so athletes can update their status mid-plan without re-running the full screening flow.

**5 substantive code files + 2 test files (under ceiling). No `layer0-apply` owed.**

---

## §2 — Files changed

### `health_screening_repo.py` (modified)
Added two new helpers at the end of the file:

- **`get_pregnancy_flag(db, user_id) -> bool | None`** — reads from ANY `health_screening` row (acknowledged or not); returns `None` if no row, `True` if `PREGNANCY` flag present, `False` if row exists but flag absent.
- **`set_pregnancy_flag(db, user_id, is_pregnant: bool) -> None`** — creates a bare unacknowledged row if none exists; otherwise toggles the flag in-place. Caller commits.

No schema change: the `health_screening` table and `PREGNANCY_FLAG` constant pre-date this session (Phase 0 shipped them).

### `layer4/context.py` (modified)
Added `pregnancy_status: bool | None = None` as the last field of `Layer1HealthStatus`:

```python
class Layer1HealthStatus(_Base):
    current_injuries: list[InjuryRecord] = Field(default_factory=list)
    ...
    resting_hr_bpm: int | None = None
    pregnancy_status: bool | None = None   # ← new (#223)
```

`True` = pregnant/postpartum, `False` = not, `None` = no screening row. Defaulting to `None` means existing code constructing `Layer1HealthStatus` without the keyword argument is backward-compatible.

### `layer1/builder.py` (modified)
- Added `from health_screening_repo import PREGNANCY_FLAG` import
- Added `_load_pregnancy_status(db, user_id) -> bool | None` function (SELECT on `health_screening.flags`) + Rule #15 print:
  ```python
  print(f"[layer1 pregnancy-status] user_id={user_id} pregnancy_status={status} records={len(flags)}")
  ```
- Wired as **SELECT #27** (the last SELECT) in `build_layer1_payload` — appended after `coaching_preferences = _load_coaching_preferences(...)` so no existing position numbers needed renumbering
- Passed `pregnancy_status=pregnancy_status` into `Layer1HealthStatus(...)` constructor

Positioning the new SELECT last was the key decision: inserting it at position 8 (physically near `_load_medications`) would have shifted 19 test queue-positions. At position 27 only one new `_queue_andy` response was needed.

### `routes/profile.py` (modified)
- Added `from health_screening_repo import get_pregnancy_flag, set_pregnancy_flag`
- In the `edit()` GET handler: `pregnancy_status = get_pregnancy_flag(db, uid)` after pack-load load; passed to `render_template` as `pregnancy_status=pregnancy_status`
- New route:
  ```python
  @bp.route('/pregnancy', methods=['POST'])
  def save_pregnancy():
      """Toggle the PREGNANCY screening flag from the profile health tab (#223)."""
      db = get_db()
      uid = current_user_id()
      is_pregnant = request.form.get('pregnancy_status') == 'yes'
      print(f"[profile pregnancy] user_id={uid} is_pregnant={is_pregnant}")
      set_pregnancy_flag(db, uid, is_pregnant)
      db.commit()
      return redirect(url_for('profile.edit', tab='health'))
  ```

**Unchecked-checkbox handling:** HTML checkboxes don't POST when unchecked. `request.form.get('pregnancy_status') == 'yes'` correctly evaluates to `False` when the field is absent — no extra logic needed.

### `templates/profile/edit.html` (modified)
Added a "Reproductive health" card in the health tab, between the nutrition form's closing `</form>` and the `{% include 'profile/_health_tab.html' %}` line. CSP-clean no-JS — plain HTML form with a single checkbox + Save button, mirroring the nutrition/pack-load card pattern:

```html
{# #223 — pregnancy status. Source of truth: health_screening.flags / PREGNANCY
   flag. Toggled here without re-running the full screening flow so athletes
   can update mid-plan. Layer 2E HITL-gate wiring deferred (#518). #}
<form method="post" action="{{ url_for('profile.save_pregnancy') }}">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <div class="card card-pad stack pf-nutrition">
    <div>
      <p class="eyebrow">● Reproductive health</p>
      <p class="pf-hint">Affects nutrition safety reviews. All optional.</p>
    </div>
    <label class="pf-chip pf-pregnancy">
      <input type="checkbox" name="pregnancy_status" value="yes"
             id="pf-pregnancy-check"
             {% if pregnancy_status %}checked{% endif %}>
      <span>Currently pregnant or within 6 months postpartum</span>
    </label>
    <div><button type="submit" class="btn btn-primary btn-sm">Save</button></div>
  </div>
</form>
```

---

## §3 — Tests

### `tests/test_layer1_builder.py` (modified)
- `_queue_empty_athlete`: `range(26)` → `range(27)`, comment updated to mention #223
- Renamed `test_26_selects_issued` → `test_27_selects_issued`; assert changed from `== 26` to `== 27`
- `_queue_andy` (in `TestFullyPopulated`): added 27th response — `conn.queue_response(row={"flags": []})` (Andy has no PREGNANCY flag)
- Updated comment in `test_explicit_off_rows_preserved`: "22 of 26" → "22 of 27 after #223 added the _load_pregnancy_status SELECT"
- Added **`TestPregnancyStatus`** class (6 tests):
  - `test_no_screening_row_returns_none` — `None` row → `pregnancy_status is None`
  - `test_empty_flags_returns_false` — `flags=[]` → `False`
  - `test_pregnancy_flag_returns_true` — `flags=["PREGNANCY"]` → `True`
  - `test_pregnancy_flag_among_others_returns_true` — mixed flags → `True`
  - `test_other_flags_only_returns_false` — only non-pregnancy flags → `False`
  - `test_andy_fixture_has_no_pregnancy_flag` — Andy's full `_queue_andy` fixture → `False`

### `tests/test_redesign_profile_render.py` (modified)
- `_Conn.__init__`: added `pregnancy_flags=None` param
- `_Conn.execute()`: added branch for `health_screening` table queries, returning the flags row or `None`
- Added 2 new tests:
  - `test_profile_pregnancy_field_renders_on_health_tab` — confirms `pf-pregnancy`, `pf-pregnancy-check`, `pregnancy_status` field name, "pregnant" text, and `/profile/pregnancy` action all appear in the rendered HTML
  - `test_profile_pregnancy_field_checked_when_flagged` — confirms `checked` attribute appears when `pregnancy_flags=["PREGNANCY"]`

**Result: 4031 passed / 30 skipped** (baseline 4022 + 9 new). Ruff: 0 new errors (4 pre-existing in `routes/profile.py`, untouched).

---

## §4 — What was NOT built (deferred)

- **Layer 2E HITL-gate wiring** (issue #518, stop-and-ask trigger #4) — gates 1-4 are dead-stubbed `return []` today. The pregnancy flag is now visible in `Layer1HealthStatus.pregnancy_status`, so a future HITL-gate session has the data it needs. That session needs to:
  1. Define when the gate should fire (which nutrition safety review scenarios)
  2. Design the stop-and-ask interaction for athletes who are flagged
  3. Wire `pregnancy_status` into the trigger logic in `layer3/hitl.py` (or equivalent)

---

## §5 — Architecture notes

**`layer1_hash` cold-recompute:** the new `pregnancy_status` field in `Layer1HealthStatus` changes the Layer 1 payload structure. Athletes who have a `health_screening` row (i.e., went through onboarding after Phase 0 shipped) will have their `layer1_hash` cold-recomputed on first plan-gen after this deploys — expected behavior under the partial-update model. Athletes with no screening row get `pregnancy_status=None`, which is the default, so their payload is byte-identical.

**No schema change:** `health_screening` table and `PREGNANCY_FLAG` constant both predate this session (Phase 0). The `set_pregnancy_flag` helper creates a bare unacknowledged row if none exists — this row differs from a full screening acknowledgment (no `acknowledged_at`, no `reassessment_due_at`) but is functionally correct for the pregnancy flag capture use case.

---

## §6 — Session-end checklist

### §6.1 — Verification
- [x] Full test suite: **4031 passed / 30 skipped**
- [x] Ruff: 0 new errors
- [x] 5-file ceiling: 5 substantive code files + 2 test files — at ceiling
- [x] No `layer0-apply` owed

### §6.2 — Bookkeeping
- [x] `CURRENT_STATE.md` updated (last-shipped entry = #223)
- [x] `CARRY_FORWARD.md` updated (#223 marked DONE; next = Phase 2 #394)
- [x] Closing handoff written (this file)
- [x] GitHub issue #223 reconciled (comment + closed with `completed` reason)
- [x] Branch pushed: `claude/pack-load-weighting-phase1-uy2kfz`
- [ ] PR: NOT opened — awaiting Andy's go (project rule: no auto-open)

### §6.3 — Operating notes for next session

**Read order:**
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

**Next work: Phase 2 → #394** (D-79..D-85 screening polish on the Phase 0 health-screening screen). The screening flow is at `/onboarding/health-screening` (route in `routes/onboarding.py`; template `templates/onboarding/health_screening.html`; repo `health_screening_repo.py`). Phase 2's D-79..D-85 issues polish this UI — confirm exact scope from the issue text before building.

**Both #1067 and #223 are on branch `claude/pack-load-weighting-phase1-uy2kfz`** — they share a branch (this session's work was appended to the session that shipped #1067). When Andy gives the go to open the PR, both will be in the same PR. Both are closeable on merge.

**Layer 2E HITL gate (#518)** remains deferred — don't build it without a stop-and-ask. The `pregnancy_status` field in `Layer1HealthStatus` is the data hook; the gate logic is a separate session.

---

## §7 — Decisions made this session

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Capture-only (no HITL gate) | Gate is stop-and-ask trigger #4; deferred to #518 |
| D2 | Source of truth = existing `health_screening.flags` / `PREGNANCY` flag | No new schema; re-uses Phase 0 infrastructure |
| D3 | SELECT #27 (last) in `build_layer1_payload` | Avoids renumbering 19+ test queue-position comments |
| D4 | Bare unacknowledged row for mid-plan updates | Athlete shouldn't re-run full screening to toggle pregnancy status |
| D5 | CSP-clean no-JS checkbox form | Consistent with nutrition/pack-load pattern on the same page |

---

## §8 — Rule #10 verification table

| File | Anchor string | Check method |
|------|--------------|-------------|
| `health_screening_repo.py` | `def get_pregnancy_flag(db, user_id)` | `grep -n get_pregnancy_flag health_screening_repo.py` |
| `health_screening_repo.py` | `def set_pregnancy_flag(db, user_id, is_pregnant:` | `grep -n set_pregnancy_flag health_screening_repo.py` |
| `layer4/context.py` | `pregnancy_status: bool \| None = None` | `grep -n pregnancy_status layer4/context.py` |
| `layer1/builder.py` | `def _load_pregnancy_status(db, user_id` | `grep -n _load_pregnancy_status layer1/builder.py` |
| `layer1/builder.py` | `pregnancy_status = _load_pregnancy_status(` | `grep -n "pregnancy_status = _load_pregnancy_status" layer1/builder.py` |
| `routes/profile.py` | `def save_pregnancy():` | `grep -n save_pregnancy routes/profile.py` |
| `routes/profile.py` | `pregnancy_status = get_pregnancy_flag(db, uid)` | `grep -n "pregnancy_status = get_pregnancy_flag" routes/profile.py` |
| `templates/profile/edit.html` | `pf-pregnancy` | `grep -n pf-pregnancy templates/profile/edit.html` |
| `tests/test_layer1_builder.py` | `class TestPregnancyStatus:` | `grep -n TestPregnancyStatus tests/test_layer1_builder.py` |
| `tests/test_layer1_builder.py` | `test_27_selects_issued` | `grep -n test_27_selects_issued tests/test_layer1_builder.py` |
| `tests/test_redesign_profile_render.py` | `test_profile_pregnancy_field_renders_on_health_tab` | `grep -n test_profile_pregnancy_field_renders_on_health_tab tests/test_redesign_profile_render.py` |
