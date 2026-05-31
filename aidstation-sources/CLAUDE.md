# CLAUDE.md — AIDSTATION

This file is loaded at the start of every Claude Code session. It encodes the **stable** project context: identity, working rules, decision triggers, tone, and the first-session checklist.

It does **not** encode current state. For "what just shipped, what's next, where we are in the layer pipeline," read **`CURRENT_STATE.md`** (single-pointer rolling state) and **`CARRY_FORWARD.md`** (multi-session items: manual walkthroughs, doc nits, orthogonal tracks).

---

## What this project is

AIDSTATION is a commercial direct-to-athlete SaaS application providing AI-driven coaching for endurance and multi-sport athletes. The market focus is on disciplines underserved by existing training software: ultramarathons, skimo, modern pentathlon, Ironman triathlon, swimrun, marathon paddle sports, multi-sport, and adventure racing.

**Andy** is the product architect and sole decision-maker. He is also the test athlete (training for Pocket Gopher Extreme 2026, July 17–19, MN; 48–56 hour expedition AR; 15-week plan started 2026-04-01).

## Coaching voice

Direct, focused, evidence-grounded. No platitudes. No cheerleading. No hype. Tone matches a real endurance coach talking to a serious athlete. This applies to all user-facing copy you draft (prompt templates, UI text, error messages, marketing copy).

## Core differentiators (treat as launch commitments)

1. Plan iteration as situations change — only invalidated layers re-run (partial-update model)
2. Performance-driven auto-updates from incoming athlete data
3. Travel and on-the-go flexibility — plans adapt to athlete location and equipment
4. Multi-sport flexibility — first-class, not bolted-on
5. Team-based training — coordinated plans for teams training toward a shared race
6. Science-backed decisions — cited research, not practitioner heuristics
7. Real-life accommodation — injuries, moves, equipment changes, life disruptions as first-class inputs
8. Crowd-sourced data (eventual) — performance norms, injury patterns, gym equipment profiles

---

## Architecture

Spec-first, multi-layer LLM pipeline. Storage: PostgreSQL with JSONB. Versioning via row invalidation (not overwrite), keyed by user, layer, version. The partial-update model — surgical re-runs of only invalidated layers — is a core product differentiator and shapes every schema decision.

**Layer pipeline:**

| Layer | Purpose |
|---|---|
| **0** | Platform-level reference data (LLM-generated, human-reviewed, locked). 0A sport rule sets, 0B exercise library. |
| **1** | Athlete profile (form inputs + performance stats). Sourced from Onboarding spec + integration data. |
| **2** | Race + sport classification. 5 parallel sub-prompts: 2A discipline mix, 2B terrain, 2C equipment/modality, 2D injury risk, 2E nutrition baseline. |
| **3** | Athlete evaluation. 4 nodes: 3A athlete state, 3B viability + periodization, 3C cross-node conflict, 3D HITL gate. |
| **3.5** | Hard HITL resolution gate before plan generation. |
| **4** | Plan generation + periodization validator (capped correction loop). |
| **5** | Parallel supplemental outputs: nutrition, supplements, 7-day clothing/conditions advisor. |

Live per-layer status: `CURRENT_STATE.md`. Architecture canonical doc: `Control_Spec` (resolve to highest `_vN.md` by directory listing).

---

## Rules of operation (NON-NEGOTIABLE)

These exist because handoff narrative has drifted from on-disk state before. Quality is enforced by mechanical verification, not by trust.

### Rule #9 — Session-start verification

Before continuing prior work, verify the previous handoff's claimed file updates actually landed in the files. Run `./scripts/verify-handoff.sh` for the automated anchor sweep (file existence + backlog pointer drift + §8 table extraction). Then spot-check the specific content claims using `grep` or anchor reads. Reconcile any gap as the **first action of the session**, before any new work. Do not proceed assuming the handoff narrative is accurate.

### Rule #10 — Session-end verification

Do not write a handoff claiming a file edit landed unless the edit is actually in the file. Verify each claimed update against the on-disk file before composing the handoff. The handoff's §8 table is the input to the next session's Rule #9 sweep — keep it concrete (file paths + anchor strings + check method).

### Rule #11 — Mechanically-applicable deferred edits

When a handoff defers edits, include mechanically-applicable instructions:
- For surgical edits: `str_replace`-style old_string / new_string blocks
- For section rewrites: "replace section X with verbatim content: [...]"

**No narrative summaries** like "update §2/§3 of Control_Spec" without the new text. The next session executes spec'd edits; it does not re-derive them. Failure mode is loud (str_replace mismatch) not silent (interpretive drift).

### Rule #12 — Numeric version suffixes

Revised files save with a numeric version suffix (`_v1.md`, `_v2.md`, …). Each revision bumps N from the highest existing. Old versions accumulate as in-project history — do not delete. Cross-references cite the logical name without version; resolve via directory listing to the highest N at use time.

**Backlog (historical):** the `Project_Backlog_vN.md` chain is **frozen** under `archive/backlog/` as of 2026-05-27 — backlog now lives in GitHub issues (see Working principles). The old convention is recorded here only to read the archive: it bumped N on **structural** change, with status flips / Notes-column annotations / new D-row additions as **in-file edits** plus a `## Changelog` entry (most-recent first).

### Rule #13 — Every closing handoff names the session-start reads

Every closing handoff's §6.3 (Operating notes for next session) begins with the read order:

1. `CLAUDE.md` — stable rules (this file)
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. The latest handoff itself (this one)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

CLAUDE.md changes rarely now (it's stable rules only — see A2 process refactor 2026-05-19). When operating rules or framing change, the handoff that changes them flags it explicitly.

### Rule #14 — Log access: ask, don't infer (Andy 2026-05-31)

When diagnosing, treat logs as the source of truth — and never substitute a guess for a log you could have.

1. **Signal not yet logged → ask to add it.** If the fact you need isn't being captured anywhere (no log line, no persisted field, no instrumentation), do **not** infer it from surrounding behavior. Surface the gap and propose the specific instrumentation (the exact log line / persisted field), then ask Andy to add it — or ask permission to add it. We track it better rather than assume. Padding-style probing (guessing exception types by trial) is not a substitute for the missing signal.
2. **Log exists but you can't reach it → ask Andy to pull it.** If the signal *is* being logged but it's outside your reach (the Vercel runtime-log MCP truncates the message column / groups by request / has unreliable-negative full-text search; an admin page sits behind the app login wall), do **not** guess or reason around it. Tell Andy exactly which line/panel you need (e.g. "the line after `_advance_plan_generation: unexpected`", or the `/admin/plan/<id>/inspect` traceback panel) and have him paste it. A negative from a tool with a documented reliability gotcha is **not** evidence of absence.

Rationale: on the #47 triage (2026-05-31) the truncated MCP made log-probe negatives *look* like they excluded a `ValueError`, when the real fault was a pydantic `ValidationError` — invisible until Andy pasted the raw traceback. Inference around an unreadable log burns turns and lands wrong. (The log-visibility build that closes this gap natively is tracked in CARRY_FORWARD / GitHub issues.)

---

## Stop-and-ask triggers

Your default is execution. **Exception:** the items below. For these, stop, enter `/plan` mode, and wait for Andy's explicit confirmation before implementing.

1. **LLM prompt design or modification** — scoping a new prompt vs a runtime query, OR designing/significantly modifying an LLM prompt body.
2. **Data padding refusal** — adding a new vocabulary entry OR a new exercise database entry. Strict no-padding rule: only when no existing entry covers the same physical stimulus / technique / injury profile.
3. **Cross-layer surface change** — schema changes affecting inter-layer contracts, `etl_version_set` pinning, partial-update invalidation rules, OR new D-rows with cross-layer scope.
4. **HITL gate** — designing or modifying a Layer 3.5 trigger.
5. **Architectural alternatives with real tradeoffs** — don't pick silently.
6. **Status / architecture promotion** — Backlog item Deferred→Blocker, OR any `Control_Spec` architecture change.

For each, the expected output before stopping is: options considered, tradeoffs, your recommendation, your gut check (risks / what might be missing / best argument against). Then wait.

**Do not implement first and ask forgiveness.**

(Consolidated 2026-05-19 from the prior 11-trigger list; load-bearing semantics preserved.)

---

## Working principles

- **Spec-first sequencing.** Architecture → prompts → implementation. Resist shortcuts. Resist producing testable output before the spec is correct and complete.
- **Redesign work.** For redesign work, follow `docs/redesign/CONVENTIONS.md` and the phase specs alongside it.
- **Layer specs follow a depth standard.** 14 sections matching `Layer2C_Spec.md`: purpose, boundaries, function signature, validation, algorithm, payload schema, coaching flags, caching, edge cases, performance budget, open items, test scenarios, gut check. Do not skip per-node specs; do not let design decisions live only in handoff docs.
- **5-file ceiling = substantive files only.** "Substantive" means new/modified code, specs, designs, prompt bodies. Bookkeeping files (`CURRENT_STATE.md` edits, backlog in-file edits, `CARRY_FORWARD.md` edits, the closing handoff, `CLAUDE.md` rule edits) do not count against the ceiling. Quality degrades past ~5 substantive files. If a session needs more, propose splitting before starting.
- **`CURRENT_STATE.md` is the rolling pointer.** Update it on every shipped session (last-handoff name + focus + layer status). The closing handoff is the long-form record. Don't accumulate session narrative in `CLAUDE.md` — that file is for stable rules.
- **`CARRY_FORWARD.md` is the rolling carry-state.** Manual walkthroughs, doc-sweep nits, orthogonal/parallel tracks. Edit in place; don't restate in handoff narratives.
- **GitHub issues are the single source of truth for backlog, features, and bugs.** Tracked in `ahorn885/exercise` as epics + sub-issues, labelled by `layer:*` / `area:*` / `type:*` / `status:*` / `priority:*` and a `v1`/`v2` track. File new deferred work, feature ideas, and bugs as issues — not in docs. Preserve the `[D-NN]` ids in issue titles so older specs/handoffs still cross-reference. Close with a `completed` / `not_planned` reason + the PR/commit ref. The historical `Project_Backlog_vN.md` chain is frozen under `archive/backlog/` (migrated 2026-05-27); read it for context, don't reopen it.
- **Next-step prioritization (the 4-tier order).** When choosing what to work on next, go in this order: (1) **finish the in-flight task** — if the previous handoff left work unresolved, close it before starting anything new; (2) **resolve go-live / live-functionality blockers** — anything that prevents launch or degrades already-shipped behavior, including safety gaps; (3) **finish open-but-not-fully-live functions** — wire up built-but-unshipped code, de-stub, complete partially-shipped features; (4) **pursue new functionality.** The latest handoff §6 and `CURRENT_STATE.md` "Next moves" map the live issues onto these tiers.
- **Branch naming.** If the harness pins a branch name that mismatches this session's scope, rename it at session start (`git branch -m <new-name>`). Don't accumulate "harness-pinned; name mismatches scope" footnotes in handoffs — they're lossy bookkeeping and shrug at a fixable problem.
- **Never invent file contents.** If a file is referenced and not yet viewed, view it first. If a function or table is referenced and not visible, search for it before assuming.
- **Andy makes all final architectural decisions.** You are a technical thought partner.

### Periodic practices

- **`simplify` skill pass on `layer4/`** — quarterly or after a major sub-arc closes. The skill reviews changed code for reuse, quality, and efficiency. Use when implementation has accumulated a few sessions of additions and patterns are worth consolidating.

---

## Chat tone with Andy

- Direct. No filler. No hype. No "great question."
- Match confidence to reality. If uncertain or tradeoffs exist, say so briefly.
- If an idea is weak or flawed, say it plainly and explain why.
- End substantive recommendations with a gut check: risks / what might be missing / best argument against.
- If the session gets long or messy, remind Andy to create a handoff note and start fresh.

---

## Stack

- **AI backend:** Claude API (Sonnet/Opus latest)
- **Database:** PostgreSQL (Neon) — both production and dev. SQLite path retired 2026-05-16 (PR13).
- **ETL / data work:** Python (openpyxl, rapidfuzz, pandas).
- **Web app:** Flask + Jinja templates, deployed to Vercel (`aidstation-pro.vercel.app`). Code at the repo root (`app.py`, `routes/`, `init_db.py`, etc.). This is the **v1 app**, current production target for the v2 LLM-pipeline build being designed in `aidstation-sources/`. TrueNAS / Docker deployment path retired 2026-05-16 (PR13).
- **Athlete integrations:** COROS + Ride With GPS shipped (Phase-0 webhook stubs); Strava/Whoop/TrainingPeaks/Zwift stubs prepped on a separate branch; Polar + Wahoo next; Garmin paused (API closed); Apple Health + Samsung Health out of scope (need native iOS/Android clients).

---

## Environment quick-reference (stable infra + per-session lookups)

These are stable across sessions — look them up here, don't re-derive them each thread.

**Vercel (for the MCP tools — `list_teams`/`list_projects` return these every time):**
- Team: slug `andy-horns-projects` — id `team_rkZGxltBw2ykWtrIPCYy16JZ`
- Project: name `exercise` — id `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`
- Prod domain `aidstation-pro.vercel.app` (git-main alias `exercise-git-main-andy-horns-projects.vercel.app`); the current prod deployment is whichever `target: production` row is newest in `list_deployments`.
- **Function Max Duration = 800s** (Pro plan max available; Andy 2026-05-31). `vercel.json` can't set it (legacy `builds` array can't coexist with the `functions` key) — it's a dashboard setting. **Correction:** prior handoffs/this file said `300s`; that was wrong. It skewed the #48 504 triage ("a single LLM call exceeding the 300s cap, hard-killed before any `except`") — with an 800s cap a ~300s 504 is **not** the function ceiling but an earlier limit (Vercel gateway, or the SDK non-streaming guard #331 pinned). Re-validate that triage against real timings.
- **Runtime-log gotcha:** a `query timed out before all pages were fetched` warning makes a NEGATIVE log result UNRELIABLE (the search aborted mid-scan). Only clean negatives + any positive match are trustworthy. Narrow the time window or filter by `deploymentId` to get a clean query.

**Container env (true every web session):**
- DB egress to **Neon is blocked** from the container — can't run `init_db.py` / `psql` against Neon here, so schema migrations stay owed-Andy's-hands actions. PyPI egress works.
- `pytest` is **not** in `requirements.txt`: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`. Isolated single-file collection hits a circular-import quirk → run the full `tests/` (or front-load a `tests/test_layer4_*.py`).

---

## Operating context (v1 + v2, selective rebuild)

This repo holds **two parallel work tracks**:

1. **v1 Flask app at the repo root.** Live production AIDSTATION. Strength-training + cardio-logging + Garmin FIT ingestion + Claude-API-based coaching. Has no users in production — Andy is the only test athlete.
2. **v2 LLM-pipeline design in `aidstation-sources/`.** Layers 0–5 spec-first build.

**Selective rebuild (the v1→v2 path):**
- **Keep:** provider integration layer (`routes/`, `*_connect.py`, OAuth callback plumbing), auth + accounts, DB scaffolding pattern (`init_db.py`, `_PG_MIGRATIONS`, the `database.py` compatibility layer), and `rx_engine_spec.md` as the strength-progression algorithm spec.
- **Replace:** coaching + plan-generation. The current `coaching.py` is one big Claude call; v2 is the structured 0–5 layer pipeline.
- **Revisit later:** v1 strength UI, the broader v1 schema rot.

**Strangler-fig sequencing.** v2 modules ship into the running v1 app one at a time, replacing pieces. No parallel staging environment. v1 having no users (only Andy as test athlete) makes this safe — schema migrations and route swaps don't need backward-compatibility shims.

**"Push to production as we go" rule (Andy 2026-05-14):** prefer shipping working v2 code into v1 over accumulating more design ahead of any implementation. The 5-file ceiling and spec-first sequencing still apply, but specs should be scoped to what we're about to build, not everything ahead.

---

## Andy's active athlete context (May 2026)

Training for **Pocket Gopher Extreme 2026** (July 17–19, Nerstrand MN; 48–56 hour expedition AR). Disciplines: trail running, hiking, MTB, packrafting, outdoor rock climbing, abseiling.

**Active injury — left wrist:** painful and weak with wrist extension under load. Avoid all wrist-extension-loaded exercises. Pushups in fist position only. Climbing grip-dominant moves OK; wrist-loaded moves not.

This context matters because Andy dogfoods his own product — coaching guidance you draft may be tested against his actual training. If you draft a session for him, respect the wrist constraint.

---

## First-session checklist

When you start a fresh session, do this before anything else:

1. Read this `CLAUDE.md` fully.
2. Read `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. Read `CARRY_FORWARD.md` — rolling carry-forwards across sessions.
4. Read the latest handoff named by `CURRENT_STATE.md`.
5. Run `./scripts/verify-handoff.sh` — automated anchor sweep (file existence, backlog pointer drift, §8 table). If anything is ❌, run Rule #9 reconciliation as your first action.
6. Read `PR_Verification_Status.md` so you know which §5.0 steps Andy has already walked vs. genuinely owed. Don't re-list completed items as "still owed."
7. Tell Andy: (a) what you understand current state to be, (b) what you understand the next focus to be, (c) any drift you found between handoff narrative and on-disk state.
8. **Do not start work** until Andy confirms scope.

---

*End of CLAUDE.md.*
