# AIDSTATION

AI-driven coaching for endurance and multi-sport athletes. Spec-first, multi-layer LLM pipeline.

**See `CLAUDE.md` at repo root for project context, current state, and working rules.** That file is also what Claude Code loads at session start.

## Repo layout

```
.
├── CLAUDE.md                          # session-start context for Claude Code
├── README.md                          # this file
├── *.md                               # current and historical specs at root
│                                      #   - Control_Spec_v{1..6}.md
│                                      #   - Project_Backlog_v{1..11}.md
│                                      #   - Layer0_ETL_Spec_v{1..7}.md
│                                      #   - Layer2{A..E}_Spec.md
│                                      #   - Layer3_3A_Spec.md
│                                      #   - Athlete_Onboarding_Data_Spec_v{2..4}.md
│                                      #   - Athlete_Data_Integration_Spec[_v2].md
│                                      #   - Catalog_Migration_Plan[_v2].md
│                                      #   - Vocabulary_Audit_v{1..3}.md
│                                      #   - Supplement_Vocabulary_Spec.md
│                                      #   - DATABASE.md, AR_Exercise_Database_Documentation.md
├── handoffs/                          # all session-end handoff docs (chronological history)
├── patches/                           # patch / batch / section-rewrite docs from spec edits
├── reference/                         # curation references, audits, deployed-schema reports
├── migrations/                        # SQL migrations (Layer 0 ETL + sub-layer schema)
├── etl/                               # Python ETL scripts + parsed intermediate data
├── data/                              # xlsx data assets (exercise DB, sports framework)
├── app/                               # web app (to be created)
└── .claude/
    ├── settings.json                  # CC permissions
    └── commands/
        └── handoff.md                 # /handoff slash command (Rules #9-12 enforcement)
```

## Versioning convention (Rule #12)

Revised files save with a numeric version suffix: `Control_Spec_v6.md` supersedes `Control_Spec_v5.md`. Old versions accumulate as history; do not delete. Cross-references in specs cite the logical name without version — Claude Code resolves to the highest N at use time.

## Current state pointers

- Architecture: `Control_Spec_v6.md`
- Backlog: `Project_Backlog_v11.md`
- Most recent session: `handoffs/L3_Spec_Trio_R2_Closing_Handoff_v1.md`
- Next forward move: `Layer3_3B_Spec.md` (to be created)
