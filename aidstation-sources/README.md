# AIDSTATION — project knowledge & working docs

AI-driven coaching for endurance and multi-sport athletes. This folder (`aidstation-sources/`) is the **brain of the project**: the rules Claude works by, the design specs for each part of the system, the research behind the decisions, and the running log of what's been built. The actual app code lives at the repository root (`app.py`, `routes/`, `layer2a/` … — see the bottom of this file).

> **New here? Read these three, in order:**
> 1. **`CLAUDE.md`** — the stable rulebook (who Andy is, how Claude should work, what to never do without asking). Claude loads this automatically every session.
> 2. **`CURRENT_STATE.md`** — "what just shipped and what's next." The single source of truth for where the project stands today.
> 3. **`CARRY_FORWARD.md`** — the running to-do list that spans sessions (e.g. database changes waiting on Andy to apply).

---

## Where do I find…?

| If you want… | Look in… |
|---|---|
| The rules Claude follows | `CLAUDE.md` |
| What's done and what's next | `CURRENT_STATE.md` |
| Outstanding to-dos across sessions | `CARRY_FORWARD.md` |
| How a part of the system is *meant* to work | **`specs/`** |
| The reasoning behind a specific feature or change | **`designs/`** |
| The research / data audits behind a decision | **`research/`** |
| A step-by-step plan for a piece of work | **`plans/`** |
| The exact wording sent to the AI models | **`prompts/`** |
| The write-up at the end of each work session | **`handoffs/`** |
| Old superseded versions / retired tooling | **`archive/`** |
| Backlog, features, bugs | **GitHub Issues** (`ahorn885/exercise`), not a file here |

---

## The folders

- **`specs/`** — the canonical specifications: how each layer of the coaching pipeline works (Layers 1–4), the master architecture (`Control_Spec`), the Layer 0 reference-data ETL spec, and the athlete data/onboarding specs. These are the "source of truth" for system behavior.
- **`designs/`** — design documents for specific features and changes (each usually tied to a `D-NN` work item): plan refresh, race events, on-demand workouts, onboarding waves, the discipline-mix rewrite (`X*`), the Layer 0 DB-authoring model, and so on. A spec says *what* the system does; a design says *how we decided to build a particular piece*.
- **`research/`** — the evidence and audits behind the data: sport bridge-band research, vocabulary and equipment reconciliation audits, the database/exercise-library documentation.
- **`plans/`** — step-by-step implementation and migration plans (e.g. the catalog migration plan, the upstream implementation plan).
- **`prompts/`** — the actual prompt text sent to the Claude models for each AI step (Layer 3A/3B, the plan synthesizers, the natural-language parser). **Referenced by live app code — do not move.**
- **`handoffs/`** — one closing write-up per work session, in date order. Each records what shipped, what's verified, and what's owed. The newest one (named at the top of `CURRENT_STATE.md`) is always the freshest detail.
- **`scripts/`** — tooling, most importantly `verify-handoff.sh`, which checks that a handoff's claims actually match the files on disk.
- **`.claude/`** — Claude Code settings + the `/handoff` command.

### `archive/` (kept for history, not active)
- **`archive/superseded-specs/`** — older numbered versions of specs/designs that have been replaced by a newer one (e.g. `Control_Spec_v1` … `_v7`, kept because `_v8` is current). Nothing here is live; it's history.
- **`archive/backlog/`** — the frozen `Project_Backlog_vN` chain. Backlog tracking moved to GitHub Issues on 2026-05-27.
- **`archive/etl-scratch/`** — retired one-off ETL scripts, old SQL, intermediate data, and superseded workbooks. The live Layer 0 data toolchain lives at the repo root under `etl/`.

---

## Versioning convention (Rule #12)

Revised docs get a numeric suffix — `Control_Spec_v8.md` replaces `Control_Spec_v7.md`. **The current version stays in its live folder (`specs/`, `designs/`, …); older versions move to `archive/superseded-specs/`.** Cross-references cite the logical name (e.g. "Control_Spec") and resolve to the highest-numbered copy in the live folder. History is preserved (in the archive and in git), so nothing is lost.

## Tracking (backlog, features, bugs)

All tracked in **GitHub Issues** in `ahorn885/exercise` (epics + sub-issues, labelled `layer:*` / `area:*` / `type:*` / `status:*` / `priority:*`; the old `[D-NN]` ids are preserved in issue titles so older docs still cross-reference). Don't file new work as files here — open an issue.

---

## How this maps to the running app

The **live v1 Flask app is at the repository root** (`app.py`, `routes/`, `init_db.py`, `templates/`, `static/`, and the `layer*/` Python modules). The v2 LLM-pipeline designed in this folder ships into that app one slice at a time (a "strangler-fig" rebuild — see `CLAUDE.md` → *Operating context*). So: **this folder is the plan and the memory; the repo root is the product.**
