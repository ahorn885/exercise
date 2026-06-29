# V5 Implementation — #196 Phase 5 Track B Slice B4: Source-Precedence Picker UI — Closing Handoff (2026-06-29)

**Branch:** `claude/issue-196-canonical-source-wyhs08` (B3 + B4 ride this branch) · **Suite:** 3650 passed / 30 skipped · **PR:** not yet opened (push + bookkeep + wait for Andy's go) · **Design:** `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md` · **Predecessor:** B3 (`…Slice3…`, same branch, commit `fb4417d`) · **Epic:** #196 (Track B BUILD-COMPLETE; epic stays OPEN pending live-verify — Andy's call).

> **✅ TRACK B BUILD-COMPLETE.** B1 substrate → B2 wellness pin → B3 cardio pin → **B4 picker UI** all shipped. Phase 5 (the last open phase of #196) is now build-complete. **#196 still OPEN** — the Phase-4 LIVE-VERIFY (gated on Andy's wellness re-upload) and Track B's own first live exercise are owed, and **closing the epic is Andy's decision**, not this session's.

> **▶ IMMEDIATE NEXT (not a build slice):** **live-verify Track B** once Andy has ≥2 competing sources / re-uploads wellness — set a pin on Connections › Sources, confirm `[cardio-canon]`/`[wellness-canon]` logs show `pin=` and the canonical row flips to the pinned source, and a plan re-synth picks it up. Then decide whether to close #196. If no new #196 work, the next session is free to return to the **#884 gear/craft thread** (slice 4b PR-3 → 4.3).

---

## 1. What this slice did (one line)

Shipped the **user-facing source-precedence picker** — a two-dropdown (wellness / cardio) "Preferred sources" control on the Connections › Sources tab that writes the B1 pins and fires the B2/B3 re-materialize+evict apply helpers — the last buildable Track-B slice.

## 2. Decisions ratified this slice (Andy 2026-06-29, AskUserQuestion)

1. **Placement = the existing Connections › Sources tab** (NOT a re-introduced Preferences tab). The Connections hub's docstring notes the artboard's "configurable trust-order" controls were deliberately left unbuilt for lack of a backend (the Preferences tab was removed, #619); B4 is that backend, but Andy chose to keep the picker on Sources rather than resurrect the tab.
2. **Provider set = ALL valid-for-domain providers** (wellness: garmin/whoop/oura/polar/coros; cardio: garmin/wahoo/polar/coros/rwgps/strava), NOT filtered to currently-connected providers — plus an **Automatic (most complete)** default (= no pin). A pin on a not-yet-fed source is a harmless no-op until that source has data; the simpler unfiltered list was preferred over connection-gating.

## 3. What shipped

- **`routes/connections.py`** — new `POST /connections/source-precedence`: reads the current pins once (`get_source_preferences`), then for **each domain whose dropdown changed**, `set_source_preference` (a chosen provider) or `clear_source_preference` (Automatic), then the matching apply helper (`apply_wellness_pin_change` / `apply_cardio_pin_change`) built with `Layer4Cache(PostgresCacheBackend(lambda: db))` — the same cache-construction pattern as `athlete_gear_repo.evict_layer1_on_gear_change`. **Commits only when something changed** (the apply helpers run in the request transaction, so the new pin + the re-materialized canonical rows land atomically); a `SourcePreferenceError` (only reachable via a hand-crafted POST — the dropdown offers only valid providers) flashes + redirects without committing. Coaching-voice flash via `_precedence_flash`. New `_precedence_options(domain, current)` (Automatic-first, all valid providers sorted deterministically, current pin marked `selected`); `_hub_context` gains `source_precedence={wellness, cardio}` (one extra `get_source_preferences` read per hub render).
- **`templates/connections/hub.html`** — a two-dropdown **"Preferred sources"** `<section>` appended to the Sources tab (after the provider list, inside the tab's `stack`). Reuses existing `fit-source` / `form-select` / `btn` classes → no new CSS. Coaching-voice explainer: "When more than one device records the same day or workout, we merge them and pick the most complete record. Pin a preferred source to make it the primary whenever it has data — otherwise leave it on Automatic."
- **`tests/test_connections_source_precedence.py` (NEW, +5)** — `TestPrecedenceOptions` (all valid providers present, Automatic-first, current pin selected; Automatic-selected when no pin) + `TestSourcePrecedenceRoute` (set a pin → INSERT + apply + commit + redirect `tab=sources`; clear → DELETE + apply + commit; **no-change → no write / no apply / no commit**), apply helpers + cache monkeypatched, fake connection (no live PG / cache backend).

(3 substantive files within ceiling; bookkeeping exempt.)

## 4. Cache / cross-layer safety

- The route's apply helpers are exactly B2/B3's — re-materialize the user's canonical layer + `evict_on_layer_change(cache, uid, "layer3a")`. No NEW cache surface this slice; the picker is the trigger, the helpers are unchanged. Determinism (and thus 3A cache-key stability) is a property of the merge, not the UI.
- **No schema/DDL → no Neon apply owed** (code + template only; B1's `user_source_preferences` table is live since #981).

## 5. NEXT — live-verify, then decide on #196 closure

**5.1 Live-verify Track B (owed, gated on Andy's data — NOT a build task).** Once Andy has ≥2 competing sources for the same day/workout (or re-uploads wellness):
- On Connections › Sources, pick a non-Automatic wellness and/or cardio source, Save.
- Confirm `/admin/logs` shows `[source-pref] user=… set …`, then `[wellness-canon] … pin=…` / `[cardio-canon] … pin=…` on the re-materialize, and `[source-pref] user=… {wellness|cardio} pin applied: re-materialized N …, evicted M cache row(s)`.
- Confirm the canonical row's primary/source flips to the pinned provider, and a plan re-synth (or athlete-state read) reflects it.

**5.2 Phase-4 LIVE-VERIFY (still owed, shared carry-over).** After the wellness re-upload → 3A digests it → a refresh / plan build shows `[recovery-guidance] fresh=True` and eases load on a fatigued/overreach day.

**5.3 #196 closure — Andy's call.** All five phases are build-complete. Optional/deferred items remain (NOT blockers): Phase-3 Slice 5 conflict-surfacing UI; the parked Phase-2 `/wellness` chart repoint + `coaching.get_wellness_summary` (v1-only). If Andy closes #196, file a follow-up issue carrying the two live-verify items.

**5.4 Read order for the next session (Rule #13):** 1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this B4). 3. `CARRY_FORWARD.md` (#196 Phase 5 Track B entry — now BUILD-COMPLETE). 4. This handoff + the B3 handoff + `designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md`. 5. `routes/connections.py` (`source_precedence` route + `_precedence_options`) + `source_preference_apply.py` (both helpers) + `source_preferences_repo.py`. 6. `./scripts/verify-handoff.sh`.

## 6. Open items / decisions made this slice

- **Placement + provider-set — RESOLVED (Andy 2026-06-29, §2):** Sources tab, all valid providers. The alternatives (new Preferences tab / connection-filtered list) were presented and not taken.
- **B3 + B4 share one branch/PR** — they were built back-to-back this session on the harness-pinned `claude/issue-196-canonical-source-wyhs08`. Cohesive (the cardio pin + the UI that drives both pins); each commit is independently under the 5-file ceiling and the merge-commit convention keeps both visible. Andy may open them as one "Track B B3+B4" PR or split — flagged, his call.
- **Whether the Track is worth it** — unchanged from B1–B3: real power-user value, thin for a single-primary-device athlete; Andy chose to build it. Live value is unproven until §5.1 runs on real competing-source data.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Picker route | `routes/connections.py` | `@bp.route('/source-precedence', methods=['POST'])` + `def source_precedence`; per-domain `set_source_preference`/`clear_source_preference` then `apply_*_pin_change`; `if changed: db.commit()` |
| Options builder | `routes/connections.py` | `def _precedence_options(domain, current)`; `{'value': '', 'label': 'Automatic (most complete)', 'selected': not current}` then `sorted(VALID_PROVIDERS[domain])` |
| Context wiring | `routes/connections.py` | `source_precedence={'wellness': _precedence_options(WELLNESS, …), 'cardio': …}` in `_hub_context`'s `ctx` |
| Template | `templates/connections/hub.html` | `Preferred sources` `<section>` with `name="pin_wellness"` + `name="pin_cardio"` selects, `action="{{ url_for('connections.source_precedence') }}"` |
| Route tests | `tests/test_connections_source_precedence.py` | `class TestSourcePrecedenceRoute`; `test_no_change_does_not_apply_or_commit` (asserts `conn.commits == 0`, no INSERT/DELETE) |
| Options tests | `tests/test_connections_source_precedence.py` | `class TestPrecedenceOptions`; `test_lists_all_valid_providers_with_automatic_first` |
| Apply reuse | `source_preference_apply.py` | unchanged this slice — route calls `apply_wellness_pin_change` / `apply_cardio_pin_change` (B2/B3) |
| Cache key | — | unchanged; the picker triggers the B2/B3 helpers, no new cache surface |
| Neon | — | **No apply owed** — code + template; B1's table is live |
| Suite | — | `… pytest tests/ -q` → 3650 passed / 30 skipped (3 pre-existing #217 Layer3B warnings) |
| Epic | #196 | OPEN — Track B BUILD-COMPLETE (B1→B4); live-verify owed; closure is Andy's call |
