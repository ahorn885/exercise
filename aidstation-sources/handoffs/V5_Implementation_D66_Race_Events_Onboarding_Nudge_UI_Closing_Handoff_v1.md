# V5 Implementation — D-66 account_nudges Consumer-Side UI Closing Handoff

**Session:** Single chat. Scope: D-66 `account_nudges` consumer-side UI per `Race_Events_D66_Design_v1.md` §7.4 + carry-forward §8.4 + predecessor handoff §7.4 (Operating notes item 6). Closes the soft-reminder display loop for the `target_race_skipped` + `route_locales_incomplete` nudges that the onboarding §H.2 + §H.4 skip handlers now write at skip-time. Banner display gated by a new per-registry `display_delay_days` field (14 days for D-66 nudges; default 0 keeps PR9's `connect_provider_14d` unchanged).

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_D66_Race_Events_Onboarding_Closing_Handoff_v1.md` (D-66 onboarding §H.2/§H.4 shipped 2026-05-18 earlier same day; PR #84 merged via `a62d115`).

**Branch:** `claude/race-events-onboarding-bCY8z` (harness-pinned for this session — name carries over from the D-66 onboarding theme even though this session is the consumer-side follow-on; precedent: harness names mismatched with scope across every prior Layer 4 implementation session + the entire D-66 family).

**Status:** 🟢 5 files (2 substantive code + 3 bookkeeping). Combined `tests/` 717 → 736 net new in 1.13s (19 new tests in `tests/test_nudges.py`). **D-66 status flipped 🟢 Profile-tab UI + onboarding §H.2/§H.4 shipped → 🟢 Profile-tab UI + onboarding §H.2/§H.4 + account_nudges consumer-side UI shipped.** Layer 3B caller-side rewire + partial-update invalidation hooks per design §7.4 remain the last open D-66 carry-forwards.

**AT the 5-file ceiling** — first D-66 sub-session that hasn't blown through it (DB foundation 6 + profile-tab UI 11 + onboarding 7 all went over).

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| D-66 onboarding §H.2/§H.4 shipped on main per predecessor handoff | `git log --oneline -5` | ✅ `a62d115` (merge PR #84) + `df6752f` (D-66 race-event onboarding) |
| `routes/onboarding.py` has 8 new routes (target_race + route_locales family) | `python url_map iter` | ✅ 8 new endpoints registered |
| `_POST_STEP3B_TARGET = '/onboarding/target-race'` | grep | ✅ line 96 |
| `templates/onboarding/target_race.html` + `templates/onboarding/route_locales.html` exist | `ls` | ✅ |
| `tests/test_onboarding_race_events.py` has 22 tests | `grep -c "def test_"` | ✅ 22 |
| `tests/test_race_events_repo.py` has 33 tests (predecessor profile-tab UI) | grep | ✅ 33 |
| Combined `tests/` 717 green | `pytest tests/ -q` | ✅ 717 passed in 1.23s |
| Working tree clean on `claude/race-events-onboarding-bCY8z` | `git status` | ✅ |
| `Project_Backlog_v55.md` is current per CLAUDE.md last-shipped narrative | grep | ✅ |
| `routes/nudges.py` exists with PR9 connect_provider_14d pattern (the precedent) | `ls + Read` | ✅ |

**Environmental drift surfaced (not code drift):** the fresh container started without `pytest`/`pydantic`/`flask`/etc. installed in the active Python interpreter. Resolved by `uv tool install pytest --with pydantic --with anthropic --with flask --with flask-wtf --with flask-limiter --with psycopg2-binary --with bcrypt --with requests --with zxcvbn --with openpyxl --with garth --with garminconnect --with fit-tool --reinstall` and using `PYTHONPATH=/home/user/exercise` for pytest invocations (the `layer4/` package needs the repo root on path). All 717 baseline tests passed before any edits.

---

## 2. Session narrative — D-66 account_nudges consumer-side UI

Andy opened with the URL to the D-66 onboarding closing handoff + "lets work." Followed the operating model — read CLAUDE.md fully (Rule #13), ran Rule #9 verification (all green), surfaced state, and offered the architect-recommended next-forward-move set from the predecessor handoff §7.1.

### 2.1 Scope pick (Round 1)

Q1 (2026-05-18, 1-question gate): session scope. Andy picked **Layer 3B caller-side rewire AND account_nudges consumer-side UI** (over Layer 4 Step 7 live LLM / manual §5.0 walkthrough). The predecessor handoff §7.1 had recommended Layer 3B rewire as the single architect-pick next move + listed nudge consumer UI as a §8.4 carry-forward.

### 2.2 Scope reality (Round 2)

Before starting code, scoped the two picks against on-disk reality. Found that the predecessor handoff §7.1 had **underestimated rewire complexity**:

- **Handoff said:** "orchestrator currently reads `athlete_profile.target_event_*` for 3B's event-mode input; swap to `load_target_race_event_payload(db, user_id)`; ~3-4 files."
- **On-disk reality:** **no orchestrator code reads `target_event_*` for Layer 3B** today. Layer 3B isn't implemented yet. No production code calls `load_target_race_event_payload` (the helper exists in `race_events_repo.py:162` but has zero callers outside its own tests). What `grep` actually found:
  - `routes/profile.py:242-243` — write-side: legacy `target_event_name`/`target_event_date` form fields write into `athlete_profile` from the athlete tab
  - `templates/profile/edit.html:73-81` — renders those legacy form fields (now redundant with the race-events tab shipped earlier same day)
  - `athlete.py:21-22` — declares them as `KNOWN_PROFILE_FIELDS`
  - `init_db.py:1185-1213` — D-66 one-time migration copies them into `race_events`
- The "rewire" actually means: retire the legacy form UI (now redundant), drop from `KNOWN_PROFILE_FIELDS`, possibly drop the columns (Trigger #5 schema change), AND wire the partial-update invalidation hooks per design §7.4 which need new glue from web request handlers → `Layer4Cache` facade (the facade lives in `layer4/cache.py` but isn't accessible from `routes/race_events.py` writers today; no orchestrator module exists yet).
- Realistic rewire scope: 5-7 files on its own, with potential Trigger #5 + Trigger #7 routing depending on how much of the invalidation chain we want to land alongside.

Q2 (2026-05-18, 1-question gate): how to split given the scope reality. Andy picked **Nudge UI this session; rewire next**. Clean ~5 files at the ceiling, rewire becomes its own session where it can be scoped properly.

### 2.3 Implementation order

1. **Modified `routes/nudges.py`** — extended `NUDGE_REGISTRY` with `target_race_skipped` + `route_locales_incomplete` entries; added optional `display_delay_days` registry field (default 0 — backward-compat for PR9 `connect_provider_14d`); added `_past_display_delay(created_at, delay_days)` helper; extended `get_active_nudges` to filter rows still inside their grace window + strip `display_delay_days` from the per-row output overlay. Module docstring rewritten to explain the two coexisting writer patterns (insert-delayed for PR9 vs insert-immediate-display-delayed for D-66). See §3.
2. **New `tests/test_nudges.py`** — 19 tests using the `_FakeConn`/`_FakeCursor` pattern from `tests/test_race_events_repo.py` + `tests/test_onboarding_race_events.py`. See §4.
3. **Bookkeeping:** `Project_Backlog_v55.md` → `_v56.md` + CLAUDE.md update + this handoff.

### 2.4 Architectural choices on the record

- **Two writer patterns coexist on `account_nudges`.** PR9 `connect_provider_14d` uses the **insert-delayed** pattern: Vercel Cron INSERTs the row only after the account is 14 days old; banner shows immediately when the row exists. D-66 onboarding skip nudges use the **insert-immediate-display-delayed** pattern: `_write_account_nudge` in `routes/onboarding.py` writes the row synchronously with the skip click; the banner is suppressed for 14 days by the read-side `_past_display_delay` filter. The `display_delay_days` registry field is per-type so both patterns coexist without double-gating — PR9's entry omits the field (defaults to 0), so its display-side behavior is unchanged from the original PR9 ship.
- **Python-side filtering on read rather than SQL-side filter.** Keeps `NUDGE_REGISTRY` as the single source of truth for delay policy. Per-user nudge volume is small (≤10 active rows in v1's single-test-athlete reality) so the cost is negligible vs. the gain of not coupling SQL to specific nudge_type names. SQL-side filtering would require regenerating the WHERE clause whenever a new delay-bearing entry is added.
- **`display_delay_days` defaults to 0 (immediate display) when omitted.** Backward-compatible for existing registry entries (the only one today is `connect_provider_14d` which keeps its insert-side gate). Explicit nonzero opt-in for the D-66 entries makes the delay intent self-documenting.
- **`_past_display_delay` treats `created_at=None` as "very old" (fail-open).** Mirrors PR9 cron-side NULL handling for legacy rows pre-dating the column default. The alternative (fail-closed; suppress nudges with NULL created_at indefinitely) would hide reminders from users with old data.
- **Naive datetime from PG `TIMESTAMP` column normalized to UTC.** psycopg2 returns `TIMESTAMP` (not `TIMESTAMPTZ`) columns as **naive** datetime. The filter normalizes via `.replace(tzinfo=timezone.utc)` before comparing against `datetime.now(timezone.utc)` to avoid TypeError on aware-vs-naive subtract. The `account_nudges.created_at` schema is `TIMESTAMP NOT NULL DEFAULT NOW()` — `NOW()` returns timestamptz but the TIMESTAMP column strips TZ, leaving UTC-implicit naive values in the read path.
- **`display_delay_days` stripped from the per-row output overlay.** The banner partial (`templates/_account_nudges.html`) consumes `message` / `cta_label` / `cta_endpoint` / `category` — adding `display_delay_days` to the output would leak the internal delay knob into template context. Strip it via dict comprehension so the template surface stays stable as more delay-bearing entries land.
- **Tests reuse the `_FakeConn`/`_FakeCursor` pattern** from `tests/test_race_events_repo.py` + `tests/test_onboarding_race_events.py` rather than introducing a fresh mocking style. Consistency across the test suite outweighs marginal duplication — anyone reading the new file recognizes the pattern from prior D-66 work immediately.

### 2.5 Stop-and-ask triggers — none fired

- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire — `account_nudges` schema unchanged; registry shape extension is internal to `routes/nudges.py`.
- **Trigger #7 (new partial-update invalidation rule):** did NOT fire — nudge display logic is a downstream-of-write display surface, not a partial-update invalidation rule. (The actual §7.4 invalidation hooks land with the Layer 3B caller-side rewire next session.)
- **Trigger #8 (architectural alternatives with real tradeoffs):** the SQL-vs-Python filtering choice + the per-type delay default were implicit (Python-side filtering preserves the registry as SoT; 0 default preserves PR9 behavior). Not architect-significant enough to warrant a `/plan`-mode gate per CLAUDE.md "Stop-and-ask trigger list" framing.
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows.

Other triggers — none applicable.

---

## 3. `routes/nudges.py` modifications

### 3.1 NUDGE_REGISTRY extension

Added 2 new entries with `display_delay_days: 14`:

```python
'target_race_skipped': {
    'message': (
        "You skipped picking a target race during onboarding. "
        "Adding one unlocks race-week brief generation."
    ),
    'cta_label': 'Set a target race',
    'cta_endpoint': 'onboarding.target_race',
    'category': 'info',
    'display_delay_days': 14,
},
'route_locales_incomplete': {
    'message': (
        "Your target race is multi-day but the route locales aren't "
        "filled in yet. Add start/finish + aid stations so your "
        "race-week brief can include per-segment pacing + kit."
    ),
    'cta_label': 'Add route locales',
    'cta_endpoint': 'onboarding.route_locales',
    'category': 'info',
    'display_delay_days': 14,
},
```

PR9 `connect_provider_14d` entry left unchanged (no `display_delay_days` field → defaults to 0 immediate display).

### 3.2 `_past_display_delay(created_at, delay_days)` helper

New module-private function. Returns True iff `created_at` is at least `delay_days` days in the past. Short-circuits on `delay_days <= 0` and `created_at is None` (fail-open mirroring PR9 cron-side NULL handling). Normalizes naive datetime to UTC before comparing.

### 3.3 `get_active_nudges` extension

Iterates rows + checks each against the registry's `display_delay_days`. Rows still inside their grace window are filtered out. `display_delay_days` is stripped from the per-row output overlay via dict comprehension so the banner partial doesn't see the internal field.

### 3.4 Module docstring rewrite

Explains the two coexisting writer patterns + why `display_delay_days` is per-type rather than blanket-applied. References the predecessor handoff §7.4 for the design rationale + `routes/onboarding.py:_write_account_nudge` for the D-66 writer side.

---

## 4. Test additions

19 new tests in `tests/test_nudges.py` (combined `tests/` 717 → 736 in 1.13s). Uses the same `_FakeConn`/`_FakeCursor` pattern from prior D-66 work — no real DB.

| Test class | Count | Coverage |
|---|---|---|
| `TestNudgeRegistry` | 3 | `target_race_skipped` shape + `route_locales_incomplete` shape + unchanged-shape `connect_provider_14d` (no `display_delay_days`) |
| `TestPastDisplayDelay` | 6 | zero-delay short-circuit + None-created_at fail-open + recent suppression + old surfacing + boundary at exactly `delay_days` + naive-vs-aware datetime comparison |
| `TestGetActiveNudges` | 10 | falsy-uid no-query + zero-delay nudge surfaces immediately + recent D-66 nudge suppressed + old D-66 nudge surfaces + per-type CTA endpoints correct + mixed recent/old ordering + unknown nudge_type falls through + `display_delay_days` stripped from overlay + naive datetime from PG handled + SQL scopes to user + dismissed_at filter |

Out of scope (carry-forward; not tested this session):
- `/cron/nudges/connect_provider_14d` route + `_cron_authorized` helper — unchanged this session; PR9 surface
- `POST /nudges/<id>/dismiss` route — unchanged this session; PR9 surface
- End-to-end banner rendering in `templates/_account_nudges.html` — captured in §5 manual verification step rather than pytest

---

## 5. Manual §5.0 verification steps for Andy's walkthrough

Run on `https://aidstation-pro.vercel.app/` (or local dev) after PR merge. The D-66 §H.2/§H.4 onboarding walkthrough from the predecessor handoff §6 (12 scenarios) is still owed — these new nudge UI steps layer on top.

1. **Skip target race + immediate display suppression.** On `/onboarding/target-race` (fresh athlete, no target row), click "Skip for now". Confirm redirect to `/profile?tab=athlete` + info flash. Visit `/dashboard` or `/profile` immediately — the `target_race_skipped` banner should **NOT** appear (grace window in effect). Confirm a row exists in `account_nudges` with `nudge_type='target_race_skipped'` + `created_at = NOW()`.
2. **Skip route locales + immediate display suppression.** After multi-day target-race save, on `/onboarding/route-locales` click "Skip for now". Visit `/dashboard` — the `route_locales_incomplete` banner should **NOT** appear. Confirm the nudge row exists with `created_at = NOW()`.
3. **Manual delay-window bypass test.** Backdate the test nudge row in the DB: `UPDATE account_nudges SET created_at = NOW() - INTERVAL '15 days' WHERE user_id = <Andy> AND nudge_type = 'target_race_skipped';`. Refresh `/profile` — the banner should now appear with the "Set a target race" CTA pointing to `/onboarding/target-race`.
4. **Dismiss path.** Click the banner's close button. Should redirect back to the page + the banner disappears. Subsequent page loads don't re-show it (dismissed_at filter).
5. **PR9 connect_provider_14d unchanged.** Confirm that an athlete with the legacy `connect_provider_14d` nudge (inserted via cron after 14d account age) still sees the banner immediately — no double-gating from the new display-side filter.
6. **Mixed nudges layered.** With both `target_race_skipped` (>14d old) and `connect_provider_14d` active, both banners should render in the partial in `created_at DESC` order.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward moves

D-66 is nearly complete. New-athlete data-entry, existing-athlete CRUD, AND soft-reminder display are all shipped. Two follow-on candidates remain for D-66:

1. **Layer 3B caller-side rewire** (closes the D-66 family completely; the last open D-66 carry-forward) — see §2.2 above for the scope-reality analysis. Realistic 5-7 files on its own. Sub-scopes Andy could pick from in the next-session 1-question gate:
   - **Scope A (smallest, cleanest):** retire the legacy `target_event_*` form UI only. Drop from `templates/profile/edit.html:73-81` + `routes/profile.py:242-243` (write-side) + `athlete.py:21-22` `KNOWN_PROFILE_FIELDS`. Add forward-pointer comment in `race_events_repo.py:load_target_race_event_payload` noting the future Layer 3B caller pattern. ~3 files. Doesn't drop columns (Trigger #5 schema cleanup deferred to a follow-on); doesn't wire invalidation hooks.
   - **Scope B (medium):** Scope A + column drop migration in `init_db.py`. Trigger #5 fires (cross-layer schema change); needs `/plan`-mode gate before implementing. ~4 files.
   - **Scope C (full):** Scope B + partial-update invalidation hooks per design §7.4. Needs new web-handler → `Layer4Cache` facade glue (the cache lives in `layer4/cache.py` but isn't currently accessible from `routes/race_events.py` writers; needs an orchestrator helper or direct import depending on architectural choice). Trigger #7 fires (new partial-update invalidation rule wiring; the rules themselves are already designed in §9 but wiring is new). 5-7 files; over the ceiling. **Recommend splitting into Scope A this session + B + C as separate sessions** to stay under the ceiling.

Orthogonal candidates:

2. **Layer 4 Step 7 live LLM integration** — orthogonal to D-66. First end-to-end against real Anthropic API for `single_session_synthesize` at ~$0.075/call. Cache + telemetry from Steps 5/6 make it safer. Needs `ANTHROPIC_API_KEY` in the environment.

3. **Manual §5.0 walkthrough** of the D-66 onboarding 12-scenario suite from the predecessor handoff §6 + the new 6-scenario nudge UI suite from §5 above. Verify the just-shipped surface end-to-end on Vercel before piling on more D-66 work.

### 6.2 Carry-forward — D-72 still deferred

D-72 (`Layer2CPayload.locale_id: str` vs `Layer3BPayload.event_locale_id: str` vs `RaceEventPayload.event_locale_id: int`) — same as predecessor sessions. The nudge UI shipped this session doesn't touch any locale-FK; D-72 still lands when the Layer 3B caller-side rewire fires (whichever sub-scope picks first).

### 6.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff.
3. **Third re-read**: depends on scope. If Layer 3B rewire Scope A → just need to verify the 3 file targets (`templates/profile/edit.html` + `routes/profile.py` + `athlete.py`) + confirm no other callers grep up. If Scope B or C → also need `Control_Spec_v8` §4 (partial-update model) + `layer4/cache_invalidation.py` (existing eviction patterns).
4. **Branch**: cut fresh off post-merge main OR stay on the harness pin (precedent: this session also stayed harness-pinned from the predecessor's branch).
5. **`account_nudges` writer-side is now end-to-end tested**: athlete skips § H.2 or §H.4 → nudge row written by `_write_account_nudge` → 14 days later the banner displays via `get_active_nudges` → athlete clicks dismiss → row marked dismissed. The full loop works.

---

## 7. Open items / decisions pinned this session

### 7.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Q1 scope = Layer 3B rewire + nudge UI (both) | Andy 2026-05-18 | Architect-recommended from predecessor handoff §7.1 + §8.4 carry-forward |
| 2 | Q2 split = nudge UI this session, rewire next | Andy 2026-05-18 | Scope-reality found that rewire is realistically 5-7 files (not the 3-4 the predecessor handoff estimated); ceiling-respecting split keeps both pieces well-scoped |
| 3 | `display_delay_days` per-type registry field (default 0) | Architect-pick | Two writer patterns coexist without double-gating; PR9 entry unchanged |
| 4 | Python-side filtering on read (not SQL-side) | Architect-pick | Registry as single source of truth; per-user volume small |
| 5 | `_past_display_delay` fail-open on NULL `created_at` | Architect-pick | Mirrors PR9 cron-side handling for legacy rows |
| 6 | Naive datetime from PG normalized to UTC via `.replace(tzinfo=timezone.utc)` | Architect-pick | psycopg2 TIMESTAMP returns naive; need safe comparison |
| 7 | `display_delay_days` stripped from per-row output overlay | Architect-pick | Internal field shouldn't leak into template context |
| 8 | Tests reuse `_FakeConn`/`_FakeCursor` pattern from prior D-66 work | Architect-pick | Consistency across test suite outweighs marginal duplication |

### 7.2 Carry-forward — Layer 3B caller-side rewire (next session)

Last open D-66 carry-forward. See §6.1 + §2.2 above for scope analysis.

### 7.3 Carry-forward — D-72 type-alignment

Unchanged from prior sessions. Forced by the Layer 3B rewire whenever it fires.

### 7.4 Carry-forward — D-66 onboarding §5.0 walkthrough

12-scenario suite from the predecessor handoff §6 + 6-scenario nudge UI suite from §5 above. Andy walks through on Vercel after PR merge.

### 7.5 Carry-forward — `_v55.md` retained per Rule #12

`Project_Backlog_v55.md` preserved alongside the new `_v56.md` per the numeric-version-suffix rule. The historical chain stays intact.

---

## 8. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `routes/nudges.py` gains `target_race_skipped` + `route_locales_incomplete` registry entries | ✅ grep both keys |
| `routes/nudges.py` gains `_past_display_delay` helper | ✅ grep `def _past_display_delay` |
| `routes/nudges.py` `get_active_nudges` filters by `display_delay_days` | ✅ inspection — filter loop + `continue` on inside-grace-window |
| `routes/nudges.py` `display_delay_days` stripped from per-row overlay | ✅ inspection — `{k: v for k, v in entry.items() if k != 'display_delay_days'}` |
| `tests/test_nudges.py` exists with 19 tests | ✅ pytest -v confirms 19 passed |
| Combined `tests/` 736 green | ✅ `pytest tests/ -q` → 736 passed in 1.13s |
| `Project_Backlog_v56.md` exists; v55 retained | ✅ ls |
| `Project_Backlog_v56.md` D-66 row status updated 🟢 Profile-tab UI + onboarding §H.2/§H.4 + account_nudges consumer-side UI shipped | ✅ inspection |
| `CLAUDE.md` last-shipped-session bumped; onboarding §H.2/§H.4 demoted to predecessor | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v56.md` | ✅ grep |

---

## 9. Files shipped this session

**Substantive code (1 modified + 1 new = 2 files):**
1. Modified `routes/nudges.py` — `NUDGE_REGISTRY` extended with 2 new entries + new `display_delay_days` field + new `_past_display_delay` helper + `get_active_nudges` extended for delay filtering + module docstring rewrite explaining the two coexisting writer patterns.
2. New `tests/test_nudges.py` — 19 tests covering registry shape + delay-filter behavior + `get_active_nudges` end-to-end against the `_FakeConn` pattern.

**Bookkeeping (3 files):**
3. New `aidstation-sources/Project_Backlog_v56.md` (per Rule #12; v55 retained as predecessor) — D-66 row status flip + new file-revision header.
4. Modified `aidstation-sources/CLAUDE.md` — last-shipped-session bump; onboarding §H.2/§H.4 demoted to predecessor; First-session checklist Backlog ref `v11` → `v56` (stale placeholder updated).
5. New `aidstation-sources/handoffs/V5_Implementation_D66_Race_Events_Onboarding_Nudge_UI_Closing_Handoff_v1.md` (this file).

**5 files total. AT the 5-file ceiling.** First D-66 sub-session that hasn't blown through it (DB foundation 6 + profile-tab UI 11 + onboarding 7 all went over). Smaller scope = ceiling-respecting; precedent is healthy.

---

## 10. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **D-72 Locale-FK type alignment across typed payloads** — deferred; forced by the Layer 3B caller rewire whenever it fires.
- **Layer 4 Step 7 live LLM integration** — orthogonal carry-forward.
- **Partial-update invalidation hooks per design §7.4** — concrete carry-forward; lands with Layer 3B caller rewire (Scope C from §6.1).
- **D-66 onboarding §5.0 walkthrough** (12 scenarios from predecessor handoff §6 + 6 nudge UI scenarios from §5 above) — not actioned this session.

---

**End of handoff.**
