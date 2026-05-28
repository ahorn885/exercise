# AIDSTATION

AI-driven coaching for endurance and multi-sport athletes. Spec-first, multi-layer LLM pipeline.

**See `CLAUDE.md` for project context, working rules, and the first-session checklist.** That file is what Claude Code loads at session start; `CURRENT_STATE.md` holds the rolling "what just shipped / what's next" state.

## Repo layout

```
.
├── CLAUDE.md                          # session-start context for Claude Code
├── CURRENT_STATE.md                   # rolling state pointer (last shipped + 4-tier next moves + layer status)
├── CARRY_FORWARD.md                   # live operational carry-state (owed deploys + §5.0 walkthrough ledger)
├── README.md                          # this file
├── *.md                               # current and historical specs at root (resolve to highest _vN — Rule #12)
│                                      #   - Control_Spec_v{1..8}.md
│                                      #   - Layer0_ETL_Spec_v{1..7}.md
│                                      #   - Layer2{A..E}_Spec.md
│                                      #   - Layer3_3A_Spec.md / Layer3_3B_Spec.md
│                                      #   - Athlete_Onboarding_Data_Spec_v{2..6}.md
│                                      #   - Athlete_Data_Integration_Spec[_v2..v6].md
│                                      #   - Catalog_Migration_Plan[_v2..v3].md
│                                      #   - Vocabulary_Audit_v{1..3}.md
│                                      #   - Supplement_Vocabulary_Spec.md
│                                      #   - DATABASE.md, AR_Exercise_Database_Documentation.md
├── archive/
│   └── backlog/                       # frozen Project_Backlog_v{1..62}.md chain (tracking → GitHub issues)
├── handoffs/                          # all session-end handoff docs (chronological history)
├── prompts/                           # LLM prompt bodies (Layer3A_v1.md, NLParser_v1.md, …)
├── scripts/                           # verify-handoff.sh + other tooling
├── patches/                           # patch / batch / section-rewrite docs from spec edits
├── reference/                         # curation references, audits, deployed-schema reports
├── migrations/                        # SQL migrations (Layer 0 ETL + sub-layer schema)
├── etl/                               # Python ETL scripts + parsed intermediate data
├── data/                              # xlsx data assets (exercise DB, sports framework)
└── .claude/
    ├── settings.json                  # CC permissions
    └── commands/
        └── handoff.md                 # /handoff slash command (Rules #9-12 enforcement)
```

The **live v1 Flask app lives at the actual repository root** (`app.py`, `routes/`, `init_db.py`, `templates/`, `static/`) — the v2 LLM-pipeline modules in this `aidstation-sources/` tree ship into it one slice at a time (strangler-fig; see `CLAUDE.md`).

## Versioning convention (Rule #12)

Revised files save with a numeric version suffix: `Control_Spec_v8.md` supersedes `Control_Spec_v7.md`. Old versions accumulate as history; do not delete. Cross-references in specs cite the logical name without version — Claude Code resolves to the highest N at use time. **Exception:** the `Project_Backlog_vN.md` chain is frozen under `archive/backlog/` (backlog moved to GitHub issues 2026-05-27).

## Current state pointers

- **Architecture:** `Control_Spec` — resolve to the highest `_vN.md` (currently `Control_Spec_v8.md`).
- **Backlog / features / bugs / deferred work:** GitHub issues in `ahorn885/exercise` (epics + sub-issues, labelled `layer:*` / `area:*` / `type:*` / `status:*` / `priority:*`; `[D-NN]` ids preserved in titles). The frozen `Project_Backlog_vN.md` chain is under `archive/backlog/`.
- **Current state + next moves:** `CURRENT_STATE.md` (rolling pointer; the 4-tier next-move framework lives in "Current focus") + `CARRY_FORWARD.md` (owed Andy's-hands deploys + the manual §5.0 walkthrough ledger).
- **Most recent session:** the latest handoff named at the top of `CURRENT_STATE.md` (under `handoffs/`).
