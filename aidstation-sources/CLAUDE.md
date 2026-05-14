# CLAUDE.md — AIDSTATION

This file is loaded at the start of every Claude Code session. It encodes project context, current state, working rules, and the decisions that require Andy's input before you proceed.

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

| Layer | Purpose | Status |
|---|---|---|
| **0** | Platform-level reference data (LLM-generated, human-reviewed, locked). 0A sport rule sets, 0B exercise library. | DEPLOYED |
| **1** | Athlete profile (form inputs + performance stats). Sourced from Onboarding spec + integration data. | In progress (D-51 field inventory pending) |
| **2** | Race + sport classification. 5 parallel sub-prompts: 2A discipline mix, 2B terrain, 2C equipment/modality, 2D injury risk, 2E nutrition baseline. | SPECS DONE |
| **3** | Athlete evaluation. 4 nodes: 3A athlete state, 3B viability + periodization, 3C cross-node conflict, 3D HITL gate. | 3A SPEC DONE; 3B NEXT |
| **3.5** | Hard HITL resolution gate before plan generation. | Designed; not yet implemented |
| **4** | Plan generation + periodization validator (capped correction loop). | Not yet specced |
| **5** | Parallel supplemental outputs: nutrition, supplements, 7-day clothing/conditions advisor. | Not yet specced |

Architecture overview lives in `Control_Spec` (resolve to highest `_vN.md`).

---

## Current state (as of 2026-05-13)

Last shipped session: **L3-Spec-Trio Round 2** — see `handoffs/L3_Spec_Trio_R2_Closing_Handoff_v1.md`.

**Authoritative current files** (always resolve by listing directory and viewing the highest `_vN`):
- Architecture: `Control_Spec_v6.md`
- Backlog: `Project_Backlog_v11.md`
- Onboarding data: `Athlete_Onboarding_Data_Spec_v4.md`
- Integration: `Athlete_Data_Integration_Spec_v2.md`
- Catalog migration: `Catalog_Migration_Plan_v2.md`
- Layer 0 ETL: `Layer0_ETL_Spec_v7.md`
- Layer 3 done: `Layer3_3A_Spec.md`
- Vocabulary audit: `Vocabulary_Audit_v3.md`
- Exercise DB: `data/AR_Exercise_Database_v19.xlsx` (245 exercises, 36 sports, 1,068 sport-exercise pairings)
- Sports framework: `data/Sports_Framework_v10.xlsx`

**Next forward move:** `Layer3_3B_Spec.md` (goal-timeline viability + periodization shape).

**Independent parallel tracks** (do not block Layer 3 spec writing):
- D-50 Phase 1 integration deployment (Vercel-app codebase, separate repo)
- D-52 Catalog Migration Phase 1 — fuzzy-match HITL alias audit
- D-57 Research re-evaluation cadence design
- D-58–D-61 onboarding architectural restructures (scope as a single design wave; they interact heavily)

---

## Rules of operation (NON-NEGOTIABLE)

These exist because handoff narrative has drifted from on-disk state before. Quality is enforced by mechanical verification, not by trust.

### Rule #9 — Session-start verification

Before continuing prior work, verify the previous handoff's claimed file updates actually landed in the files. Spot-check the specific edits the handoff claims using `grep` or anchor reads. Reconcile any gap as the **first action of the session**, before any new work. Do not proceed assuming the handoff narrative is accurate.

### Rule #10 — Session-end verification

Do not write a handoff claiming a file edit landed unless the edit is actually in the file. Verify each claimed update against the on-disk file before composing the handoff.

### Rule #11 — Mechanically-applicable deferred edits

When a handoff defers edits, include mechanically-applicable instructions:
- For surgical edits: `str_replace`-style old_string / new_string blocks
- For section rewrites: "replace section X with verbatim content: [...]"

**No narrative summaries** like "update §2/§3 of Control_Spec" without the new text. The next session executes spec'd edits; it does not re-derive them. Failure mode is loud (str_replace mismatch) not silent (interpretive drift).

### Rule #12 — Numeric version suffixes

Revised files save with a numeric version suffix (`_v1.md`, `_v2.md`, …). Each revision bumps N from the highest existing. Old versions accumulate as in-project history — do not delete. Cross-references cite the logical name without version; resolve via directory listing to the highest N at use time.

---

## Stop-and-ask trigger list

Your default is execution. **Exception:** the items below. For these, stop, enter `/plan` mode, and wait for Andy's explicit confirmation before implementing.

1. **Scoping a new prompt vs a query** — is this Layer 0 reference data (LLM-generated once, human-reviewed, locked) or a runtime athlete-specific query?
2. **Designing or significantly modifying an LLM prompt body**
3. **Adding a new vocabulary entry** — strict no-padding rule applies; only when no existing entry covers the same physical stimulus / technique / injury profile
4. **Adding a new exercise database entry** — same no-padding rule
5. **Schema changes** affecting an inter-layer contract or `etl_version_set` pinning
6. **Designing or modifying a HITL trigger** (Layer 3.5 gate logic)
7. **Creating or changing a partial-update invalidation rule** (which layers re-run when X changes)
8. **Architectural alternatives with real tradeoffs** — don't pick silently
9. **Promoting a Project_Backlog item from Deferred to Blocker**
10. **Any change to `Control_Spec` architecture**
11. **Any new D-row in the backlog with cross-layer scope**

For each, the expected output before stopping is: options considered, tradeoffs, your recommendation, your gut check (risks / what might be missing / best argument against). Then wait.

**Do not implement first and ask forgiveness.**

---

## Working principles

- **Spec-first sequencing.** Architecture → prompts → implementation. Resist shortcuts. Resist producing testable output before the spec is correct and complete.
- **Layer specs follow a depth standard.** 14 sections matching `Layer2C_Spec.md`: purpose, boundaries, function signature, validation, algorithm, payload schema, coaching flags, caching, edge cases, performance budget, open items, test scenarios, gut check. Do not skip per-node specs; do not let design decisions live only in handoff docs.
- **5-file quality ceiling per session.** Do not push more than ~5 files of substantive edits/creations in a single chat. Quality degrades past that. If a request exceeds the ceiling, propose splitting before starting.
- **Project_Backlog is the single source of truth for deferred work.** Update between sessions when items are deferred. Categories: Blocker / Deferred / Cleanup. Items can promote to Blocker but never demote silently.
- **Never invent file contents.** If a file is referenced and not yet viewed, view it first. If a function or table is referenced and not visible, search for it before assuming.
- **Andy makes all final architectural decisions.** You are a technical thought partner.

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
- **Database:** PostgreSQL with JSONB
- **ETL / data work:** Python (openpyxl, rapidfuzz, pandas)
- **Web app:** TBD (not yet scaffolded)
- **Athlete integrations planned:** Garmin, Strava, Wahoo, Whoop, Apple Health, Samsung Health, Polar, Coros

---

## Andy's active athlete context (May 2026)

Training for **Pocket Gopher Extreme 2026** (July 17–19, Nerstrand MN; 48–56 hour expedition AR). Disciplines: trail running, hiking, MTB, packrafting, outdoor rock climbing, abseiling.

**Active injury — left wrist:** painful and weak with wrist extension under load. Avoid all wrist-extension-loaded exercises. Pushups in fist position only. Climbing grip-dominant moves OK; wrist-loaded moves not.

This context matters because Andy dogfoods his own product — coaching guidance you draft may be tested against his actual training. If you draft a session for him, respect the wrist constraint.

---

## First-session checklist

When you start a fresh session, do this before anything else:

1. Read this CLAUDE.md fully.
2. Read `Project_Backlog_v11.md` (or highest `_vN`).
3. Read the most recent handoff in `handoffs/`.
4. Apply Rule #9 — verify the previous handoff's claimed edits actually landed.
5. Tell Andy: (a) what you understand current state to be, (b) what you understand the next focus to be, (c) any drift you found between handoff narrative and on-disk state.
6. **Do not start work** until Andy confirms scope.

---

*End of CLAUDE.md.*
