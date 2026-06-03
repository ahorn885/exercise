# V5 Implementation — Redesign Phase 6 Finish-the-Open: manual `.FIT`-import flow onto the new shell — Closing Handoff

**Session:** Redesign track, "finish-the-open" (tier-3). Migrated the live manual-`.FIT`-upload path — `garmin/import`, `garmin/import_preview`, `garmin/import_wellness` — off `base_legacy.html` onto the new `.app` shell. Render-tested, CSP-clean. No backend/route/schema change.
**Date:** 2026-06-03
**Predecessor handoff:** `V5_Implementation_Redesign_Phase6_Polish_HandoffSync_Coaching30Blocked_2026_06_03_Closing_Handoff_v1.md`
**Branch:** `claude/great-lovelace-GuFhP` (harness-pinned; kept per the remote-session push contract)
**Status:** PR open to `main`. Redesign + auth render suites green (**64**, was 59 + 5 new); CSS braces balanced (855/855); no migration, no owed deploy.

---

## 1. Session-start verification (Rule #9)

Ran `aidstation-sources/scripts/verify-handoff.sh` — clean. Every predecessor §8 anchor lands on disk; `HEAD == origin/main` at `63f5df0`; working tree clean. No drift between the Phase-6-polish handoff narrative and on-disk state. The plan-gen chain was untouched (redesign track only).

**Scope decision:** Andy asked to stay on the **redesign track** ("our only focus in this thread"), then picked the **Garmin FIT-import forms** slice from the finish-the-open options.

---

## 2. Session narrative

1. **Read the redesign tracker** (`BUILD_TASKS.md`) to enumerate the genuinely-open finish-the-open items vs the decided out-of-scope ones (`purchases`/`references`/per-provider settings; `coaching/review` = ⛔ BLOCKED §30).
2. **Scoped the slice from the candidates.** The handoff named "operator `base_legacy` forms (garmin import/sync/wellness)". Reading the templates split that cleanly:
   - **Live manual-`.FIT`-upload path** (user-facing; the §07 workout rail + Connections hub link here): `garmin/import`, `garmin/import_preview`, `garmin/import_wellness` → **migrated this session.**
   - **Paused Garmin-Connect-API path** (`garmin/auth` = garth SSO login; `garmin/sync`, `garmin/sync_preview`): the **paused** API per CONVENTIONS §E.3 — low value to polish → **left legacy.**
   - **`garmin/wellness_log`**: a Chart.js data *viewer* on legacy `--ink` tokens — a distinct concern; deferred to keep the slice at the 5-file ceiling.
3. **Migrated the 3 templates** onto `base.html`, reusing the established redesign vocabulary (`.card`/`.card-pad`/`.field`/`.lbl`/`.stack`/`.data`/`.chip`/`.eyebrow.accent`/`.dash-head`), added a `.fit-*` CSS block, wrote a 5-case render test, ran the redesign+auth sweep green.

---

## 3. File-by-file edits

### 3.1 `templates/garmin/import.html` (migrated)
Bulk drop zone (`data-bulk-upload`/`-drop`/`-files`/`-folder`/`-start`/`-progress`/`-bar`/`-summary`/`-results` + `match_plan` checkbox) → `garmin.import_bulk`; single-activity parse form (`fit_file`/`activity_name`/`notes` → `garmin.import_fit`); supported-types `.data` table. All JS hooks preserved (the `data-bulk-*` controller already lives in `static/app.js`).

### 3.2 `templates/garmin/import_preview.html` (migrated)
Both branches preserved: **cardio** (activity-type select, disabled date, name override, the full metric `.data` table via the `row()` macro, notes) and **strength** (per-exercise set chips). The `resolve_section` macro keeps the **auto-match banner** (+ confidence `chip good`) vs the **no-match disposition radios** (`disposition`/`plan_item_id`/`swap_reason`), and its **nonced** toggle script is unchanged. Confirm POST → `garmin.import_confirm`.

### 3.3 `templates/garmin/import_wellness.html` (migrated)
Bulk uploader → `garmin.import_wellness_bulk`; single-file parse; preview summary (`counts`, date range) + sample `.data` table; confirm → `garmin.import_wellness_confirm`. **Brand-neutral (CONVENTIONS §E.4):** the "body battery" data type surfaces as **Recovery** in display copy (badge + sample column); underlying data keys (`preview.counts.body_battery`, `r.body_battery`) unchanged.

### 3.4 `static/style.css` (modified)
New `.fit-*` section (drop zone + `.u-drop-active` token override, plan-match row, progress/results, 2-col `.fit-grid`, metric-table `th` width, auto-match banner, disposition radios, wellness summary; responsive collapse < 860px). Replaces the legacy `u-border-dashed`/`u-scrollbox-200`/`u-w-40pct`/`u-mw-480` utilities (legacy-only, unstyled on the new shell). Braces **855/855**.

### 3.5 `tests/test_redesign_garmin_import_render.py` (new)
5 cases, all route-driven through the real app + fake DB (matcher/FIT-parser stubbed): import landing, wellness landing, wellness preview (asserts **Recovery** relabel + no "Body battery"), cardio no-match (disposition radios + nonced script), strength auto-match (banner + 91% chip + no radios). Each asserts `app-shell` + CSP-clean (`style="`/`onclick=` absent).

---

## 4. Copy decision (CONVENTIONS §E.4 — brand-neutral `.FIT`)

Neutralized **page chrome** (titles/intros: "Import Garmin FIT Files" → "Import .FIT files"; "from your device's MONITOR/ folder" → "monitoring export") and the one **named data-type mapping** the guardrail spells out (body battery → **Recovery**). **Kept** the remaining data-field labels (HR, Stress, Respiration, Steps, and the cardio metric rows) as-is — they name literal parsed FIT fields and changing them would misrepresent the operator preview. Documented here rather than relitigated in UI.

---

## 5. Manual verification steps (Vercel, post-merge)

Render-tested only; worth a smoke on the preview deploy:
1. Connections → **Upload .FIT** → the import landing renders on the new shell; drag a `.fit` → the bulk uploader counts files and the green progress bar runs (the `data-bulk-*` controller is unchanged).
2. Single-activity parse a cardio `.fit` → the preview shows the metric table; with no plan match, the disposition radios toggle the plan-item dropdown + reason field (nonced script).
3. **Import wellness .FIT** → parse a wellness file → the preview badges read **Recovery** (not "body battery"); confirm imports N records.
4. Light mode (§28) + keyboard roving (§29) still behave on these screens (they inherit the shell).

---

## 6. Next session pointers

### 6.1 Architect-recommended next move
Two coherent finish-the-open follow-ons remain, both low-priority/non-blocking: **(a)** the `garmin/wellness_log` viewer (Chart.js — remap the legacy `--ink`/`--orange` chart vars to the new `--fg`/`--accent` tokens; relabel the "Body battery" chart to Recovery for consistency with this slice); **(b)** print stylesheets (`@media print` for plan/workout — design says "confirm scope" first). The paused-Garmin-API forms (`auth`/`sync`/`sync_preview`) and admin `plan_inspect`/`plan_diag` are operator/paused surfaces — lowest value.

### 6.2 Higher-priority alternative (off this thread)
The **plan-gen go-live board** (tier-2): re-run the PGE e2e → read the diag endpoint → the #316/#350 wall-clock backstop → the still-owed §14 coherence read (#333). Mostly Andy's-hands (Neon egress blocked from the container).

### 6.3 Operating notes for next session
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — what just shipped + focus. 3. `CARRY_FORWARD.md` — rolling items. 4. This handoff. 5. `aidstation-sources/scripts/verify-handoff.sh` — anchor sweep. Redesign build rules: `docs/redesign/CONVENTIONS.md`; live tracker: `docs/redesign/BUILD_TASKS.md`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Stay on the redesign track this thread | Andy | "Our only focus in this thread." |
| 2 | Slice = manual `.FIT`-import flow (3 templates) | Andy | Most user-facing of the remaining redesign surface — the live data-in path the §07 rail links to. |
| 3 | Scope out the paused-API garmin forms + the wellness_log viewer | Claude (noted) | `auth`/`sync` are the **paused** Garmin-Connect-API path (§E.3) — low value to polish; `wellness_log` is a distinct viewer (Chart.js) — deferred to hold the 5-file ceiling. |
| 4 | Brand-neutral page chrome + "body battery → Recovery"; keep other data-field labels | Claude (noted) | Honors §E.4 where named; preserves operator-preview accuracy for literal FIT fields. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `garmin/import.html` extends `base.html` (not `base_legacy`) | ✅ grep |
| `garmin/import_preview.html` extends `base.html`; both cardio+strength branches present | ✅ grep + render test |
| `garmin/import_wellness.html` extends `base.html`; "Recovery" relabel, no "Body battery" | ✅ render test |
| `data-bulk-*` hooks + confirm endpoints preserved in all 3 | ✅ grep |
| `.fit-*` block in `static/style.css`; braces balanced (855/855) | ✅ |
| No inline `style="`/`onclick=` in the 3 templates | ✅ grep (0/0/0) |
| `tests/test_redesign_garmin_import_render.py` (5) present + green | ✅ pytest |
| Redesign + auth sweep green (64) | ✅ `pytest -k "redesign or auth_gate"` |
| Working tree clean after push | ⏳ (push pending) |

---

## 9. Files shipped this session

**Substantive (redesign UI/code):**
1. `templates/garmin/import.html` (migrated)
2. `templates/garmin/import_preview.html` (migrated)
3. `templates/garmin/import_wellness.html` (migrated)
4. `static/style.css` (`.fit-*` block)
5. `tests/test_redesign_garmin_import_render.py` (new)

**Bookkeeping:** `docs/redesign/BUILD_TASKS.md`, `aidstation-sources/CURRENT_STATE.md`, this handoff.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md`: noted the two remaining finish-the-open follow-ons (`wellness_log` viewer chart-token remap + relabel; print stylesheets) and that the paused-Garmin-API forms stay legacy by decision. No migration / no owed deploy from this slice.

---

**End of handoff.**
