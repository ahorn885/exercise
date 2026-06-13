# Layer 4 Strength — Two-Template Restructure — Closing Handoff

**Session:** Deepened Layer 4 strength programming from the single economy-derived template (3–5 exercises) to a durability-weighted **two-template** model (programmed layered session vs failover muscular-endurance substitution), extracted to a shared source of truth and fanned into the refresh prompts. Addresses #541 (shallow strength). PR #571, squash-merged.
**Date:** 2026-06-13
**Predecessor handoff:** `V5_Implementation_T3RefreshPlanStartDateFix_2026_06_13_Closing_Handoff_v1.md`
**Branch:** `claude/vibrant-wright-4kcjku`
**Status:** 6 substantive files (1 new module + 3 prompt splices + 1 cache bump + design v2) + 1 new test file; **2370 passed / 30 skipped**; CI green; **merged**.

---

## 1. Session-start verification (Rule #9)

Non-standard start: this was a long research → design → implement arc (a deep-research strength-science pass + an extended design conversation with Andy), not a continuation of a deferred §8 table. No predecessor file-edit claims to anchor-check. The relevant pre-work state (v1 design's 3–5 template; the `_rule_strength_frequency_band` warning-only validator; the refresh prompts carrying their own strength instructions) was verified live by reading the on-disk files before editing.

**Reconciliation note:** clean. One mid-session surprise reconciled: `main` advanced under the branch (#566/#557/#208/#569), so the merge pulled in refresh terrain-feasibility + async refresh. Resolved the conflicts (all additive) and **corrected design v2's now-stale "failover dormant on refresh until PR 2" claims** — #557 makes the failover trigger reach refresh, so both templates are live on gen + refresh at merge.

---

## 2. Session narrative

- **Trigger #1 (prompt modification) gates honored throughout.** Andy drove the scope: pushed back that the v1 3–5 template "seems light for extreme endurance," prompting a second cited deep-research pass (5 angles: session depth, durability/load-carriage, interference, core, periodization). Findings: economy → *few heavy*; durability → *deeper, volume-dependent* (Lauersen 2018; Krabak 2011 day-3–4 MSK cluster); interference does **not** penalize strength volume (Schumann 2022) — I explicitly corrected my earlier over-weighting of interference.
- **Key design turns (all Andy-ratified before build):** (1) two templates — programmed (layered, deeper) vs failover (muscular-endurance substitution); (2) the frequency cap must stay **advisory** so the terminal failover is never starved; (3) the guidance must be a **shared source of truth** reaching the refresh prompts (he flagged the fan-out explicitly); (4) split — ship the prompt change now (PR 1), defer refresh-feasibility wiring (the "PR 2").
- **Investigations that shaped scope:** traced (a) per_phase vs T1/T2/T3 prompt ownership, (b) the deterministic failover cascade (`session_feasibility.py`) + that the frequency cap is already `warning`-only, (c) that refresh ran no feasibility resolution — which is what motivated the split. The "PR 2" then collapsed when #557+#208 landed mid-session.
- **5-file ceiling:** flagged up front; trimmed by deferring the `strength_substitution` schema marker + validator scoping to #573 (advisory-quality, naturally bundled with the marker), keeping PR 1 at 6 substantive files.

---

## 3. File-by-file edits

### 3.1 `layer4/strength_guidance.py` (new)
`STRENGTH_PROGRAMMING_GUIDANCE` — the shared two-template body (no markdown header; self-contained, caller-agnostic). Programmed: heavy core (2–3 compounds, 3×4–6, explosive, not to failure, RM/RPE) + durability layer (eccentric/unilateral knee, Nordic, calf/tib-ant) + 1 plyo + 1 trunk/carry; dose 2/wk Base-Build, 1/wk Peak-Taper, never >3; maintenance = cut volume, hold load. Failover: compose `[TERRAIN-INFEASIBLE]`/`[NO CRAFT]` slots as muscular endurance, keep the missing session's target hours, exempt from the dose cap.

### 3.2 `layer4/per_phase.py` (modified)
Import `STRENGTH_PROGRAMMING_GUIDANCE`; `SYSTEM_PROMPT` converted to parenthesized concatenation; the `# Strength programming` body replaced with the shared guidance + a per_phase tail (pool selection, no-history, attribution, placement). The old "3–5 multi-joint … 2–3 sets, 4–10 rep range" line is gone.

### 3.3 `layer4/plan_refresh_t1.py` / 3.4 `layer4/plan_refresh_t2.py` (modified)
Import the shared guidance; `SYSTEM_PROMPT` → parenthesized concatenation with a `# Strength programming` section appended = the shared body. (Both also carry main's #557 `_format_session_feasibility` render in `render_user_prompt` — so the failover annotations are present in the refresh user prompt.)

### 3.5 `layer4/hashing.py` (modified)
`LAYER4_PROMPT_REVISION = "2"` added to `plan_create_key` + `plan_refresh_key` components. The prompt body is not otherwise in the cache key (key = payload + model + sampling + DB-sourced `etl_version_set`), so a prompt-only change wouldn't invalidate cached plans without this. (Co-exists with #557's `terrain_feasibility_hash` on the refresh key — both kept in the merge.)

### 3.6 `aidstation-sources/designs/Layer4_StrengthProgramming_Phase2_Design_v2.md` (new; v1 archived)
Durability-weighted evidence sweep (§A with PMIDs/DOIs + dissent); §0 the economy-vs-durability framing; §4/§4b the two templates; §7b the refresh fan-out; §11 the cache bump. Corrected at merge to reflect #557/#208 (failover live on refresh; #573 = marker tail only). v1 → `archive/superseded-specs/`.

---

## 4. Code / tests

`tests/test_layer4_strength_templates.py` (new, 10 tests): both templates + trigger seam in the shared guidance; programmed dose/layers; failover = muscular-endurance + uncapped; **fan-out** (shared guidance embedded in all three `SYSTEM_PROMPT`s); superseded line absent from per_phase; `LAYER4_PROMPT_REVISION` changes both create + refresh keys (monkeypatch). Full suite post-merge: **2370 passed / 30 skipped**.

---

## 5. Manual §5.0 verification steps

Low-priority live spot-check (logged in `CARRY_FORWARD.md`): post-deploy, regenerate a plan / refresh a week and confirm (a) a Build strength day reads as the layered ~6–8-movement session (not the old ~4-exercise circuit), and (b) a terrain-infeasible discipline on refresh composes as a muscular-endurance circuit, not heavy lifting. The `LAYER4_PROMPT_REVISION` bump forces the first post-deploy plan/refresh to re-synthesize cold (automatic — no action).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
Continue the plan-quality batch: **#542** (low-protein macros) / **#543** (structured health conditions) — the siblings of #541 which this PR addresses. Then **#573** (the `strength_substitution` marker + validator source-scoping — small, advisory-quality). Then the compliance build-out (epics #353/#355/#356/#359).

### 6.2 Alternative pivots
- **#573 first** if the advisory frequency warning gets noisy on real plans with failover stacking (it counts all strength incl. failover until the marker lands).
- Live-verify the strength depth on Andy's actual pv before moving on, if dogfooding surfaces anything off.

### 6.3 Operating notes for next session
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — last shipped + focus. 3. `CARRY_FORWARD.md` — rolling items (the #571/#573 block is new). 4. This handoff. 5. `./scripts/verify-handoff.sh` — anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Go deeper than v1's 3–5 (two-template model) | Andy | Market is multi-day expedition/ultra; durability (not economy) is the objective — Lauersen 2018 volume dose-response, day-3–4 MSK cluster. |
| 2 | Frequency cap stays advisory (`warning`-only) | Andy | A hard cap would starve the terminal failover (forced empty day / validation error). |
| 3 | Failover strength = muscular endurance, exempt from cap | Andy | It replaces an infeasible *aerobic* session — must not add a heavy CNS day; keeps target hours. |
| 4 | Shared source of truth (`strength_guidance.py`) fanned into refresh | Andy | Refresh prompts must not drift back to the shallow template. |
| 5 | Split: prompt change now, marker/validator-scoping deferred | Andy + ceiling | Keep PR 1 ≤ ceiling; marker bundles naturally with #573. |
| 6 | Bump `LAYER4_PROMPT_REVISION` (not rely on `etl_version_set`) | architect | Prompt body isn't in the cache key; `etl_version_set` is DB-sourced (not code-bumpable here). |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/strength_guidance.py` exists; `STRENGTH_PROGRAMMING_GUIDANCE` defined | ✅ |
| Shared guidance embedded in all 3 `SYSTEM_PROMPT`s | ✅ test `test_*_embed_shared_guidance` |
| Old "3–5 … 2–3 sets" line removed from per_phase | ✅ test + grep |
| `LAYER4_PROMPT_REVISION` in both cache keys | ✅ tests + grep `hashing.py` |
| Design v1 archived; v2 in `designs/` | ✅ `git mv` + ls |
| Full suite green; CI green; PR merged | ✅ 2370 passed; squash-merged to `main` |
| Working tree clean | ✅ git status |

---

## 9. Files shipped this session

**Substantive (6):**
1. `layer4/strength_guidance.py` (new)
2. `layer4/per_phase.py` (prompt splice)
3. `layer4/plan_refresh_t1.py` (prompt splice)
4. `layer4/plan_refresh_t2.py` (prompt splice)
5. `layer4/hashing.py` (cache-revision bump)
6. `aidstation-sources/designs/Layer4_StrengthProgramming_Phase2_Design_v2.md` (new; v1 archived)

**Tests:** `tests/test_layer4_strength_templates.py` (new).
**Bookkeeping (not counted):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.
**Tracking:** issue #573 filed (marker tail); #541 addressed (not auto-closed — Andy's call on exact scope).
