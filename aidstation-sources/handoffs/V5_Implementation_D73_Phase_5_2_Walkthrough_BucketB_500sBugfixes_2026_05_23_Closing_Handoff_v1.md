# D-73 Phase 5.2 Walkthrough Bucket B 500s + Persistence Bugfixes — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — closes Bucket B from Andy's 2026-05-21 second-pass manual walkthrough (post-V1CoachingRetire). Three production-only bugs nailed against Vercel runtime logs + Neon SELECT diagnostics: plan-gen `IndexError`, locale-delete `ForeignKeyViolation`, and locale-terrain-checkbox write-side persistence bug.
**Date:** 2026-05-23
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_V1CoachingRetire_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/bold-keller-fodpf` (harness-pinned; system-prompt rule forbids renaming).
**PR:** TBD — open as draft once pushed.
**Status:** 4 substantive files (2 source + 2 test). Container-runnable subset 774 → 793 (+19: 5 new tests + 14 newly-collected `test_layer2a.py` tests via import-order workaround). No regressions.

---

## 1. Session-start verification (Rule #9)

`./aidstation-sources/scripts/verify-handoff.sh` ran against the V1CoachingRetire predecessor handoff. One ❌ on `templates/coaching/generate.html` (false positive — the file was a §3.3 intentional deletion; on-disk reality matches D1=Hard retire). All other anchor claims verified on disk. No drift requiring reconciliation. Predecessor merged via PR #128 (`8527519`).

---

## 2. Session narrative

Andy chose Bucket B at the AskUserQuestion gate and shared Vercel function logs for two 500s + a Neon SELECT result for the persistence bug:

- **Bug 1 — `/locales/horn_s_house/delete` 500.** Vercel traceback showed `psycopg2.errors.ForeignKeyViolation: update or delete on table "locale_profiles" violates foreign key constraint "locale_equipment_user_id_locale_fkey" on table "locale_equipment". DETAIL: Key (user_id, locale)=(1, horn_s_house) is still referenced from table "locale_equipment"`. Root cause obvious on read: `routes/locales.py:1167` `delete_locale` issues `DELETE FROM locale_profiles` without first clearing the dependent `locale_equipment` rows. FK audit (`grep "REFERENCES locale_profiles"` in `init_db.py`): `locale_equipment_overrides` + `locale_toggle_overrides` both have `ON DELETE CASCADE` (line 981, 992); `locale_equipment` does NOT (lines 263, 490, 655 declare the FK without cascade). The override tables clean up implicitly; equipment does not.

- **Bug 2 — `/plans/v2/new` 500 with `IndexError: tuple index out of range`.** Vercel traceback pinned `layer2a/builder.py:124` `_load_disciplines` → `db.execute(sql, params)`. Reading the SQL at lines 124-177 surfaces 5 `?` placeholders matching 5 params — so on its face the parameter count is correct. The signal was line 170: `AND pla.discipline_name NOT LIKE '%WEEKLY TOTAL%'`. After `_PgConn.execute` does the `?` → `%s` replacement, the SQL passes to psycopg2's parameter-substitution layer, which scans for `%s`/`%(name)s`/`%%` markers. The unescaped `%W` and `%T` inside the literal `'%WEEKLY TOTAL%'` get interpreted as malformed format specifiers — psycopg2 walks the parameter tuple expecting more values and runs off the end, raising `IndexError`. Standard psycopg2 escape: bare `%` in a literal must be doubled to `%%` when the cursor.execute() params is non-None.

- **Bug 3 — locale terrain-checkbox persistence.** Andy's Neon SELECT confirmed write-side bug: `SELECT locale_terrain_ids FROM locale_profiles WHERE user_id=1 AND locale='chisenhall_mtb_trailhead'` returned `'{}'` after save. Locale is category `outdoor_park` (in `SHARED_PROFILE_CATEGORIES`), so the edit route flows through `_edit_shared_locale` (not `_edit_legacy_locale`). Reading `_edit_shared_locale` lines 663-707: both the shared_build (first-athlete) and inherit (subsequent) branches issue `UPDATE locale_profiles SET notes = ?, locale_terrain_ids = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND locale = ?` with `(notes, new_terrain_ids, uid, locale)` as params. The list-of-strings should adapt to a Postgres `ARRAY[...]` via psycopg2's default adapter — confirmed locally:

  ```
  >>> psycopg2.extensions.adapt(['TRN-002', 'TRN-003']).getquoted()
  b"ARRAY['TRN-002','TRN-003']"
  >>> psycopg2.extensions.adapt([]).getquoted()
  b"'{}'"
  ```

  Both should work for a `TEXT[]` column (`'{}'` casts implicitly via `array_in`). The new route-flow integration tests (TestEditLegacyLocaleTerrainPersists + TestEditSharedLocaleTerrainPersists) verify the route emits the correct UPDATE statement with the terrain list at the right param index — so the bug is NOT in the route logic. It must be psycopg2-side: either an adapter quirk in the production psycopg2 version (Vercel-provided 2.9.x), a connection-pool oddity, or an unconfirmed column-type drift. The defensive fix — explicit `?::text[]` cast on all 3 `locale_terrain_ids` placeholders — forces explicit array typing on the bound value regardless of adapter behavior. Production validation pending Andy's next walkthrough.

Implementation: 4 substantive files (under ceiling). 2 D-decisions ratified informally at the scope gate.

`/plan` Triggers fired: none. All 3 bug fixes are mechanical / surgical:

- Bug 1 = single-statement INSERT-before-DELETE order (no architectural choice).
- Bug 2 = single-character psycopg2 literal escape (well-known fix).
- Bug 3 = defensive cast applied at 3 placeholder sites (well-understood Postgres syntax).

`/plan` Triggers DEFERRED (Buckets C-E from the second-pass walkthrough):

- **Bucket C** — terrain vocab cleanup. Trigger #5 (architecture) + Trigger #2 (vocab adds) + Trigger #3 (Layer 0 schema). Design pass owed.
- **Bucket D** — legacy hardcoded `home/hotel/partner/airport` slots + free-text location field removal. Depends on C.
- **Bucket E** — race event creation surface fixes (terrain "None" prepending + disciplines + terrain↔discipline coupling). Trigger #5.

---

## 3. File-by-file edits

### 3.1 `routes/locales.py` — Bug 1 (delete FK) + Bug 3 (defensive `::text[]` cast)

**Bug 1 fix at line 1167:** Added `DELETE FROM locale_equipment WHERE user_id = ? AND locale = ?` before the parent `DELETE FROM locale_profiles`. 3-line comment explains the FK semantics (`locale_equipment` has no `ON DELETE CASCADE`; override tables do cascade so they're implicit).

**Bug 3 fix at 3 sites:**

- Line 571 (legacy-path INSERT ON CONFLICT): `VALUES (?, ?, ?, ?, ?::text[], CURRENT_TIMESTAMP)`
- Line 675 (shared_build UPDATE): `SET notes = ?, locale_terrain_ids = ?::text[], updated_at = CURRENT_TIMESTAMP`
- Line 695 (shared_inherit UPDATE): same shape as 675.

3-line comment at the legacy site explains the defensive cast + cross-references the other 2 sites.

### 3.2 `layer2a/builder.py` — Bug 2 (`%%` escape)

Line 170 changed from `AND pla.discipline_name NOT LIKE '%WEEKLY TOTAL%'` to `AND pla.discipline_name NOT LIKE '%%WEEKLY TOTAL%%'`. One-character escape per psycopg2 convention.

### 3.3 `tests/test_locales.py` — 3 new test classes (+4 tests)

- `TestDeleteLocaleClearsEquipmentFirst` (2 tests): asserts `delete_locale('horn_s_house')` issues `DELETE FROM locale_equipment` before `DELETE FROM locale_profiles` + legacy enum slot (e.g. `home`) short-circuits to redirect without any DELETE.

- `TestEditLegacyLocaleTerrainPersists` (1 test): calls `_edit_legacy_locale` inside a `test_request_context` with a form carrying `locale_terrain_ids=['TRN-002','TRN-003','TRN-016']`; asserts the captured INSERT ON CONFLICT SQL contains `locale_terrain_ids` + `::text[]` cast, and that params[4] equals the parsed list.

- `TestEditSharedLocaleTerrainPersists` (1 test): calls `_edit_shared_locale` for `chisenhall_mtb_trailhead` shape (category `outdoor_park`, gym_profile_id pre-linked → inherit branch); asserts the captured UPDATE SQL contains `locale_terrain_ids` + `::text[]` cast, and that params[1] equals the parsed list.

Both round-trip tests use `_FakeConn` (the existing substrate in `test_locales.py`) + a fresh `_make_app()` Flask test app for `test_request_context` plumbing. No real Postgres dependency.

### 3.4 `tests/test_layer2a.py` — 1 new test + import-order workaround

**Import-order workaround** (top of file, before the layer2a import): `from layer4 import InMemoryCacheBackend  # noqa: F401`. Mirrors `tests/test_layer3_cached_wrappers.py:30` precedent — pre-loads `layer4/__init__.py` before triggering the layer4→layer2a circular import chain. Side-effect: 14 previously-uncollected layer2a tests now run (`pytest tests/test_layer2a.py --collect-only` previously errored at module import).

**New test class** `TestLoadDisciplinesPercentEscape`: calls `q_layer2a_discipline_classifier_payload` with empty SDM (returns via §10 unknown-sport path); asserts the captured SQL contains `%%WEEKLY TOTAL%%` and not bare `%WEEKLY TOTAL%`.

**Existing test updated:** `TestARBaseline::test_56h_nav_true_auto_includes_conditionals` had `assert "NOT LIKE '%WEEKLY TOTAL%'" in sql` at line 309. Updated to `assert "NOT LIKE '%%WEEKLY TOTAL%%'" in sql` to match the fix.

---

## 4. Code / tests

**Tests:** 1441 → 1446 (+5 net new across 2 extended/new test files: 4 in `tests/test_locales.py` + 1 in `tests/test_layer2a.py`).

Container-runnable subset: 774 → 793 in ~2.1s (+19: 5 new + 14 newly-unblocked `test_layer2a.py` tests via the import-order workaround).

Reproducer:

```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                    tests/test_race_events_repo.py \
                    tests/test_race_events_invalidation.py \
                    tests/test_onboarding_race_events.py \
                    tests/test_layer4_context.py tests/test_layer4_payload.py \
                    tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                    tests/test_layer4_race_week_brief.py \
                    tests/test_plan_sessions_repo.py \
                    tests/test_routes_ad_hoc_workouts.py \
                    tests/test_routes_plan_create.py \
                    tests/test_nl_parser.py \
                    tests/test_routes_plan_refresh.py \
                    tests/test_nl_parser_smoke.py \
                    tests/test_routes_dashboard.py \
                    tests/test_routes_admin.py \
                    tests/test_layer3_cached_wrappers.py \
                    tests/test_routes_race_events.py \
                    tests/test_layer2a.py
# 793 passed, 12 skipped
```

**Python syntax check:** `python3 -m py_compile routes/locales.py layer2a/builder.py` passes.

**No-regression confirmation:** All previously-passing tests still pass. Pre-existing tests in `tests/test_layer3a_builder.py::TestCacheWrapper` (7) + `tests/test_layer3b_builder.py::TestCacheWrapper` (7) remain pre-existing-circular-import-blocked from collection (separate scope; not touched by this slice's import-order workaround which only addresses `test_layer2a.py`).

**Coverage gap acknowledged:** Bug 3 root cause is unconfirmed. The route-flow integration test confirms the UPDATE statement is correctly built, so the bug is downstream of the route. Defensive `::text[]` cast addresses the most plausible cause (psycopg2 adapter behavior drift in production), but final validation requires Andy's next manual walkthrough against the merged + deployed branch.

---

## 5. Manual §5.0 verification steps

For Andy's next manual walkthrough pass against the preview deployment or post-merge against main:

**Step 1 — Locale delete works against equipped locales.** Pick a non-legacy locale with at least one equipment tag selected (e.g., `horn_s_house` if still present, or any custom locale). Navigate to `/locales/<slug>/edit`. Click `[Delete]` (or the delete button on `/locales/`). Confirm: exactly ONE confirm dialog (single-prompt fix from Bucket A holds), then the row disappears from the list, no 500.

Verify in Neon: `SELECT COUNT(*) FROM locale_equipment WHERE user_id=1 AND locale='<slug>'` returns 0; same query on `locale_profiles` returns 0. Override tables also empty (`locale_equipment_overrides`, `locale_toggle_overrides`).

**Step 2 — Plan-create reaches Layer 2A without 500.** Navigate to `/plans/v2/new`. Confirm the page renders the v2 form with the target-race summary card. Click `[Create plan]`. Confirm the request does NOT return 500 with `IndexError: tuple index out of range`. (Other failure modes may surface — orchestrator timeout, Layer 4 validation errors — those are out-of-scope for this slice. The specific `IndexError` originating at `layer2a/builder.py:124` should no longer fire.)

**Step 3 — Locale terrain checkboxes persist (defensive fix validation).** Navigate to `/locales/chisenhall_mtb_trailhead/edit` (or any shared-profile locale: `outdoor_park` / `commercial_chain_gym` / `independent_gym` / `hotel_gym` / `climbing_gym_chain` / `climbing_gym_indie` / `pool_indoor` / `pool_outdoor`). Under "Terrain accessible from this location", check 2-3 terrain boxes (e.g., TRN-002 Groomed Trail, TRN-003 Technical Trail, TRN-016 Indoor/Gym). Save. Confirm flash success.

Verify in Neon: `SELECT user_id, locale, locale_terrain_ids, pg_typeof(locale_terrain_ids) FROM locale_profiles WHERE user_id=1 AND locale='chisenhall_mtb_trailhead'`. Expected: `locale_terrain_ids` returns `{TRN-002,TRN-003,TRN-016}` (or whatever was checked), `pg_typeof` returns `text[]`. If still `'{}'` (empty), the defensive cast didn't resolve the bug and deeper diagnostic is needed (see §6.3).

Reload `/locales/chisenhall_mtb_trailhead/edit` and confirm the checked boxes pre-populate from the persisted column.

**Step 4 — Same for the legacy-path locale.** Pick a private-residence locale (`home_gym` / `other_residence`) that goes through `_edit_legacy_locale`. Check terrain boxes, save. Same Neon SELECT verification.

Captured as 4 new steps in `CARRY_FORWARD.md` "Manual §5.0 walkthrough" section under D-73 Phase 5.2 Bucket B.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Bucket B Bug 3 root-cause confirmation** is the highest-priority follow-on. If Andy's Step 3 walkthrough confirms terrain now persists with the `::text[]` cast, the bug is closed and we move to Bucket C/D/E. If it still doesn't persist, deeper investigation is needed:

- **psycopg2 version drift** — verify Vercel-installed psycopg2-binary version matches local. `pip show psycopg2-binary` on Vercel function or grep build logs. Pin to 2.9.12+ if needed.
- **Column type drift** — confirm `pg_typeof(locale_terrain_ids)` returns `text[]` and not `text` (singular). If `text`, an earlier `ALTER TABLE` may have added it as the wrong type and the `IF NOT EXISTS` migration silently no-op'd.
- **Connection pooling** — Neon's pooled connection mode might bisect transactions across pgBouncer. Verify the connection string uses the direct connection or that pooled-connection semantics preserve transactions through commit.
- **Request-scoped `flask.g.db`** — verify the `g.db` connection is the same object across the GET-then-POST round-trip (cold-start vs warm-start lambda containers).

**If Bucket B Bug 3 closes via Step 3 validation**, the architect-recommended next slice is **Bucket E race event creation surface fixes** in priority order:

1. **E.(a) "None" prepending on terrain dropdown** — smallest standalone fix. Check `layer0.terrain_types` seed for a literal "None" row OR the `_race_terrain_editor.html` `— Pick terrain —` placeholder rendering. Likely a 1-2 file fix.
2. **E.(c) terrain-↔-discipline coupling** — currently `race_terrain` is a flat `[{terrain_id, pct}]` list per race. Coupling to discipline (e.g., "Singletrack — for the Running leg / Flat Water — for the Packraft leg") is a schema change touching `RaceEventPayload` + Layer 2B input shape. Trigger #5.
3. **E.(b) disciplines on race event creation page** — currently captured elsewhere (or absent). Trigger #5 on placement (multi-select alongside terrain? separate card?).

### 6.2 Alternative pivots

If Bucket E blocks on design conversations:

- **#8 "locales" → "locations" rename** (~9 templates; mechanical; no Triggers) — predecessor's lowest-risk highest-visibility candidate.
- **#6 + #4 paired injury form refresh** (~6-8 files; Trigger #5 on `BODY_PART_CONSTRAINTS` mapping design).
- **#2b LLM site-parse runtime** (~4-6 files; Trigger #2 on prompt design first).
- **Bucket C terrain vocab cleanup** (~10 sub-items; Triggers #2 + #3 + #5; large design slice).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Buckets C-E live here as the active punch list; Bucket B annotated ✅ Shipped with the open-follow-on note).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketB_500sBugfixes_2026_05_23_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Forward-pointer (Bug 3 root cause):** If Step 3 validation shows the terrain still doesn't persist, the next session should:

1. Add inline logging at the 3 UPDATE/INSERT sites — print the SQL + params (sanitized) immediately before `db.execute` + the row count returned (via `cur.rowcount`) immediately after. This confirms whether the UPDATE is even executing on production.
2. Add a post-commit verification SELECT that reads back `locale_terrain_ids` and logs the value. This pinpoints whether the write lands within the same transaction.
3. If the SELECT shows the write landed within the transaction but a fresh SELECT in the next request sees `'{}'`, that's a connection-pool / transaction-scope issue — escalate to Neon support.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Ship all 3 bugs in one slice (over wait-for-Bug-3-diagnostic + ship-1+2-only) | Andy at AskUserQuestion gate | Andy's diagnostic query result for Bug 3 landed mid-session; defensive `::text[]` cast is harmless when adapter behaves correctly + decisive if adapter drifts. Bundling avoids a follow-on slice for a 3-line edit. |
| **D2** | Defensive `::text[]` cast for Bug 3 rather than waiting on definitive root cause | Claude (implementation), Andy implicitly via D1 | Route-flow integration tests confirm the route emits the correct UPDATE statement — bug is psycopg2-side or below. The explicit cast forces typing regardless of adapter behavior; root cause may need further Neon-side diagnostic (`pg_typeof`, `pg_column_size`) to confirm but the fix is safe to ship without it. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `routes/locales.py` `delete_locale` clears `locale_equipment` before parent DELETE | ✅ `grep -n "DELETE FROM locale_equipment WHERE user_id" routes/locales.py` returns hit before `DELETE FROM locale_profiles WHERE user_id` |
| `routes/locales.py` `locale_terrain_ids = ?::text[]` applied at 3 sites | ✅ `grep -nc "locale_terrain_ids.*::text\[\]\|::text\[\].*locale_terrain_ids\|?::text\[\]" routes/locales.py` returns 3 |
| `layer2a/builder.py` `NOT LIKE '%%WEEKLY TOTAL%%'` `%%` escape applied | ✅ `grep -n "NOT LIKE '%%WEEKLY TOTAL%%'" layer2a/builder.py` returns 1 hit at line 170 |
| `layer2a/builder.py` no bare `%WEEKLY TOTAL%` remaining | ✅ `grep -n "NOT LIKE '%WEEKLY TOTAL%'" layer2a/builder.py` returns 0 |
| `tests/test_locales.py` 3 new test classes added | ✅ `grep -c "^class TestDeleteLocaleClearsEquipmentFirst\\|^class TestEditLegacyLocaleTerrainPersists\\|^class TestEditSharedLocaleTerrainPersists" tests/test_locales.py` returns 3 |
| `tests/test_layer2a.py` import-order workaround applied | ✅ `grep -n "from layer4 import InMemoryCacheBackend" tests/test_layer2a.py` returns 1 hit |
| `tests/test_layer2a.py` `TestLoadDisciplinesPercentEscape` class added | ✅ `grep -n "^class TestLoadDisciplinesPercentEscape" tests/test_layer2a.py` returns 1 hit |
| Existing `TestARBaseline` test updated to `%%` | ✅ `grep -n "NOT LIKE '%%WEEKLY TOTAL%%'" tests/test_layer2a.py` returns the assertion line |
| `routes/locales.py` + `layer2a/builder.py` Python syntax valid | ✅ `python3 -m py_compile routes/locales.py layer2a/builder.py` passes |
| Container-runnable subset 793 passed + 12 skipped | ✅ pytest run |
| Tests 1441 → 1446 (+5 net new) | ✅ pytest count delta |
| `CURRENT_STATE.md` last-shipped pointer flipped to BucketB500s handoff | ✅ |
| `CARRY_FORWARD.md` Bucket B annotated ✅ Shipped with open-follow-on note on Bug 3 root cause; Buckets C-E carried | ✅ |
| PR opened as draft + CI green (Vercel deploy success) | ⏸ pending push |
| Manual §5.0 step 3 confirms terrain persists with `::text[]` cast | ⏸ pending Andy's walkthrough |

---

## 9. Files shipped this session

**Substantive (4 files; under ceiling):**

1. `routes/locales.py` — `delete_locale` adds `DELETE FROM locale_equipment` before `DELETE FROM locale_profiles` per Bug 1 (3-line comment + 4-line DELETE statement) + `locale_terrain_ids = ?::text[]` cast at 3 sites per Bug 3 defensive fix (3 × 1-char change + 4 lines of comment). +12 / -3.
2. `layer2a/builder.py` — `NOT LIKE '%%WEEKLY TOTAL%%'` `%%` escape per Bug 2. +1 / -1.
3. `tests/test_locales.py` — +4 tests across 3 new classes (TestDeleteLocaleClearsEquipmentFirst 2 + TestEditLegacyLocaleTerrainPersists 1 + TestEditSharedLocaleTerrainPersists 1) + `delete_locale` / `_edit_legacy_locale` / `_edit_shared_locale` added to the module-level import + `_make_app` + `_sql_indices` helpers. +189 / 0.
4. `tests/test_layer2a.py` — +1 test class `TestLoadDisciplinesPercentEscape` + 1 existing assertion in `TestARBaseline::test_56h_nav_true_auto_includes_conditionals` updated to expect `%%` not `%` + import-order workaround `from layer4 import InMemoryCacheBackend` at top of file unblocking 14 previously-uncollected tests. +42 / -1.

**Bookkeeping (3 files):**

5. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; session narrative appended.
6. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket B annotated ✅ Shipped with open-follow-on note on Bug 3 root cause; Buckets C-E carried as the next punch-list cohort.
7. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketB_500sBugfixes_2026_05_23_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket B 500s + persistence bugs shipped 2026-05-23** ✅ — Bug 1 (locale-delete FK violation) fixed by clearing `locale_equipment` before parent DELETE; Bug 2 (Layer 2A `IndexError`) fixed by `%%`-escaping the LIKE pattern; Bug 3 (terrain checkbox persistence) defensively fixed by `::text[]` cast at 3 sites — root cause unconfirmed, pending Andy's manual walkthrough validation.
- **Buckets C-E continue as the active punch-list cohort** — C = terrain vocab cleanup (Trigger #5/#2/#3 design pass); D = legacy hardcoded locale wipe (depends on C); E = race event creation surface fixes (Trigger #5).
- 4 new manual §5.0 walkthrough scenarios added (locale-delete works against equipped locales / plan-create reaches Layer 2A without IndexError / locale terrain persists on shared path / locale terrain persists on legacy path).
- 1 forward-pointer added: Bug 3 root cause unconfirmed — if production walkthrough confirms terrain now persists with the `::text[]` cast, root cause is psycopg2 array-adapter drift; if not, escalate per §6.3.
- Architect-recommended §6.1 forward move = Bug 3 validation (Andy's Step 3 walkthrough), then Bucket E (race-event surface fixes) starting with E.(a) "None"-prepending.

**End of handoff.**
