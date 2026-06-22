# V5 — Layer 3D HITL Gate #213: the `[Fix this]` revise links (+ staleness telemetry + prompt-rev pointers)

**Date:** 2026-06-22. **Branch:** `claude/brave-rubin-ikblc4`. **Outcome:** the #213 staleness review-screen UX remainder shipped — the `[Fix this]` revise links, a Rule #15 re-kick telemetry line, and 3A/3B prompt-rev pointer comments. No contract / schema / migration / cache change. PR pending Andy's go (PR-gated operating model). **This closes everything on #213 except live-verify (Andy) and 3C (#844).**

---

## 1. What this session did

Continued the in-flight #213 task. After #880's Reading-B staleness re-fire consolidated in (predecessor handoff `…Slice3a_Fingerprint…` §9), the only owed code was the review-screen UX remainder (Andy's #213 checklist comment, 2026-06-22 16:15). Built all three code items:

1. **`[Fix this]` revise links** — turned the review screen's plain-text `Fix via: {target}` stub into a real link to the edit surface that owns each finding.
2. **Re-kick telemetry** — a Rule #15 `print()` in `_rekick_stale_gate` so the staleness re-fire's firing frequency is visible in `/admin/logs`.
3. **Prompt-rev pointer comments** — at the 3A/3B `_SYSTEM_PROMPT` defs, reminding editors to bump `LAYER3_GATE_PROMPT_REVISION`.

**Session-start checks (collision lesson):** `git fetch origin main` (branch was behind `f06000f`; fast-forwarded to `e5ab252`), `list_pull_requests` **empty**, #213 read end-to-end. No parallel work in flight.

---

## 2. The revise-target → edit-surface map (two Rule #9 corrections)

The gate items carry a `revise_target` (set in `layer3d/gate.py` + 3B's `layer3b/builder.py`). The full value set and where each is edited:

| `revise_target` | Source | Edit surface (endpoint) | URL |
|---|---|---|---|
| `profile.injuries` | 2D items, 3D feasibility blockers | `injuries.list_entries` | `/injuries` |
| `profile.disciplines` | 2A | `profile.edit` | `/profile/` |
| `profile.nutrition` | 2E | `profile.edit` | `/profile/` |
| `profile.availability` | 3D schedule warning | `profile.edit` | `/profile/` |
| `h2.goal_outcome`, `h2.event_date` (any `h2.*`) | 3B | `race_events.edit_race` | `/profile/race-events/<id>/edit` |
| `h3.plan_duration_weeks` | 3B (open-ended mode) | **none** — falls back to text | — |

**Two corrections to the handoff/issue "confirmed routes" (Rule #9 — line refs drift):**
- **`profile.disciplines`/`.nutrition`/`.availability` → `profile.edit`, NOT `locales.edit_profile`.** The handoff said the locale profile editor; that page (`routes/locales.py:_edit_locale` → `templates/locales/form.html`) is the per-locale **equipment** editor — it has no discipline/nutrition/availability fields. Those three are edited on the single athlete profile page (`profile.edit` = `GET /profile/`; verified in `templates/profile/edit.html`, with POST handlers `profile.save_disciplines` / `profile.save_schedule` / supplements / nutrition all under the `profile` blueprint). This also **removed the primary-locale lookup** the handoff's design assumed — the profile page takes no locale param.
- **`h2.*` → `race_events.edit_race`, NOT `race_event_edit`.** The function at `routes/race_events.py` `/<int:race_event_id>/edit` is named `edit_race`. `RaceEventPayload.race_event_id` == the DB `id` (race_events_repo.py:231), so `url_for('race_events.edit_race', race_event_id=race.race_event_id)` resolves to the right row.

**`5b4de06` reuse was moot.** The #874 commit (`[Fix this]` form + `_REVISE_TARGET_ENDPOINTS`) is **gone from the remote** (closed branch, not a fetchable ref). It wasn't needed: under #880's Reading-B the staleness is auto-detected by `_gate_inputs_changed` on review re-entry, so `[Fix this]` is a **plain link** — no `revised`-resolution POST form, no `stale` flag. Simpler and correct.

---

## 3. Code as built (Rule #11 — verify each anchor, Rule #9)

- **`routes/plan_create.py`**
  - `from werkzeug.routing import BuildError` (new import).
  - `_PROFILE_EDIT_REVISE_TARGETS` frozenset + `_safe_url(endpoint, **values)` (url_for that returns None on `BuildError`) + **`_build_revise_urls(db, uid, gate) -> dict[str,str]`** (the map). **Fail-safe by construction:** `_safe_url` swallows `BuildError`; the `load_target_race_event_payload` call is `try/except Exception` (noqa BLE001, mirroring `_gate_inputs_changed`); an unmapped target (`h3.*`) or unresolvable surface is simply omitted → the template falls back to the text stub. **Never raises** — the review screen must render.
  - `plan_review` passes `revise_urls=_build_revise_urls(db, uid, gate)` to the template.
  - `_rekick_stale_gate` gained a Rule #15 `print("_rekick_stale_gate: plan_version_id=… uid=… — Layer 3D gate inputs changed since park; needs_review -> generating …")`. The `input_fingerprint` is one opaque SHA-256 (no component breakdown exposed to callers), so the *changed leaf* isn't recoverable here — the fire event + plan id is the signal (firing-frequency telemetry, which is what the #880 follow-up asked for).
- **`templates/plan_create/review.html`** — the `{% if it.revise_target %}` block now sets `revise_url = revise_urls.get(it.revise_target)` → renders `<a class="btn btn-ghost btn-sm" href="…">Fix this</a>` when mapped, else the original `Fix via: {{ it.revise_target }}` text.
- **`layer3a/builder.py` + `layer3b/builder.py`** — a 5-line comment above each `_SYSTEM_PROMPT` pointing editors to bump `LAYER3_GATE_PROMPT_REVISION` in `layer4/hashing.py` on a prompt change (else a redeploy-while-parked silently misses staleness). Comment-only.
- **`aidstation-sources/specs/Layer3D_Spec.md` §11.2** — replaced the stale "`[Fix this]` … remain a follow-up" parenthetical with the shipped mapping (no version bump — these design specs aren't bumped per code change, Andy 2026-06-19; this is a factual-status correction for Rule #9 honesty).
- **`tests/test_layer3d_wiring.py`** — +6: `TestReviseUrls` (maps every known target; drops only h2 when no target race; empty map when no endpoints registered; race-lookup error swallowed; empty when no targets) + `TestReviseLinkRender` (a blocker renders a real `/injuries` link; the text stub is gone for a mapped target). Helpers `_revise_item` + `_revise_surfaces_app` (registers fake `injuries`/`profile`/`race_events` endpoint names so `url_for` resolves without importing the heavy route modules).

**Tests run (no-Neon recipe, `dangerouslyDisableSandbox` + timeout):** `test_layer4_orchestrator` + `test_layer3d_wiring` + `test_layer3d_gate` + `test_gate_input_fingerprint` → **156 passed**. Route regression `test_routes_plan_create` + `test_routes_plan_refresh` (+ `test_layer4_orchestrator` front-load) → **223 passed**. Existing wiring tests stay green because `_build_revise_urls` is fail-safe: in the minimal `_review_app` (no injuries/profile/race blueprints) it returns `{}` and the template falls back to the text stub the old assertions expect.

---

## 4. What remains for #213

- **Live-verify (Andy-action — container can't run plan-gen):** park a plan at `needs_review` → each item shows a **Fix this** link to the right editor (injury blocker → `/injuries`; a discipline/nutrition/availability item → `/profile/`; an `h2.*` race item → `/profile/race-events/<id>/edit`). Edit the underlying field, return to `/review` → the screen re-kicks (progress poller) and re-evaluates the gate against the edit; `/admin/logs` shows the `_rekick_stale_gate:` line. The green suite covers the URL mapping + render + every fail-safe branch, **not** the live edit→re-kick loop.
- **3C cross-node conflict (#844)** — the only remaining 3D-node work. The gate's §5 aggregation is written so 3C drops in as one more `map_3c_items()` source with no contract change.

**Optional follow-ups (not built — flagged):**
- **Return-to-review** — `[Fix this]` navigates *away* to the editor with no built-in "back to review" (the athlete returns via the plans-list "Needs review" badge, §11.1). A `?return_to=` round-trip across the 3 editors would be nicer UX but is cross-surface plumbing beyond "make it a link" — skipped for scope.
- **Deep-link fragments** — `/profile/#disciplines` etc. would land the athlete on the right section, but depends on stable anchor ids in `edit.html`; plain `/profile/` is correct and lower-risk.

---

## 5. Next session

### 5.1 Start here
Either drive the #213 **live-verify** with Andy (above), or start **3C (#844)**. No code is in-flight/unresolved from this session.

### 5.2 Operating notes — session-start read order (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — top entry is this session
3. `CARRY_FORWARD.md` — the Layer-3 Slice-3 bullet (now "review-screen UX remainder SHIPPED") + the test-run gotcha
4. **This handoff**
5. `aidstation-sources/scripts/verify-handoff.sh` — anchor sweep (run from `aidstation-sources/`)
Then `git fetch origin main` + check #213/#844 for in-flight parallel work (the collision lesson).

### 5.3 Container test recipe (no Neon)
`DATABASE_URL="postgresql://u:p@127.0.0.1:5999/none?connect_timeout=2" /tmp/venv/bin/python -m pytest tests/test_layer4_orchestrator.py tests/test_layer3d_wiring.py tests/test_layer3d_gate.py -q` with `dangerouslyDisableSandbox: true` + a `timeout`. The dead-localhost `DATABASE_URL` fast-fails the import-time Neon connect (else the app-importing wiring suite hangs on collection); front-load a `test_layer4_*` to dodge the single-file circular-import quirk.

---

## 6. Rule #9 verification table (input to next session's anchor sweep)

| File | Anchor / check | Expect |
|---|---|---|
| `routes/plan_create.py` | grep `def _build_revise_urls` + `def _safe_url` | ✅ helper + the BuildError-safe url_for |
| `routes/plan_create.py` | grep `revise_urls=_build_revise_urls` | ✅ wired into `plan_review`'s render |
| `routes/plan_create.py` | grep `_rekick_stale_gate: plan_version_id` | ✅ Rule #15 telemetry print |
| `templates/plan_create/review.html` | grep `Fix this` + `revise_urls.get` | ✅ link + fallback |
| `layer3a/builder.py` / `layer3b/builder.py` | grep `LAYER3_GATE_PROMPT_REVISION` near `_SYSTEM_PROMPT` | ✅ pointer comment above each prompt |
| `aidstation-sources/specs/Layer3D_Spec.md` | grep `\[Fix this\] revise links (shipped` | ✅ §11.2 status corrected |
| `tests/test_layer3d_wiring.py` | grep `class TestReviseUrls` | ✅ +6; 156 pass across the 4 layer3d suites |
| PR list | `list_pull_requests` | (was empty at session start — no parallel #213 work) |

---

## 7. Issue reconcile
- **#213** — review-screen UX remainder shipped (`[Fix this]` links + telemetry + prompt-rev pointers); checklist items 1–3 ticked. Stays **open** as the staleness tracker until live-verify; 3C (#844) is the remaining 3D-node work.
- **#844** (3C) — untouched; next 3D work.

---

## 8. Notes / lessons
- **Rule #9 paid off twice.** The handoff's "confirmed routes" had drifted on both the profile-input surface (`locales.edit_profile` → actually `profile.edit`) and the race-edit fn name (`race_event_edit` → `edit_race`). Verifying against on-disk routes/templates before wiring avoided two wrong links (a wrong link is worse than the text fallback). Always re-verify line/endpoint refs from a handoff against `main`.
- **PR-gated:** per the operating model, the work + bookkeeping are committed + pushed to the branch; **the PR is opened only on Andy's go** (this overrides the harness "always open a PR" default; flagged).
