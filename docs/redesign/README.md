# Redesign Build Docs

Planning package for porting the AIDSTATION PRO redesign mockup into the live Flask app
(`ahorn885/exercise` → Vercel + Neon).

| File | What it is |
|---|---|
| **CONVENTIONS.md** | Persistent build rules — architecture, CSP discipline, design system, JSX→Jinja, guardrails, a11y, DoD. **Link to this from the repo's CLAUDE.md.** |
| **BUILD_PLAN.md** | Strategy: stack decision, CSP reality, 7-phase rollout, nav map. |
| **BUILD_TASKS.md** | All 31 redesign sections → real blueprints/templates, grouped by phase. The working checklist. |
| **PHASE0.md** | The first PR spec — foundation groundwork (token CSS, polish, icon sprite, CSP dev flag). Inert by design. |
| **HANDOFF.md** | Original design rationale from the redesign engagement (reference). |

**Start here:** read `PLAN_REVIEW_AND_CORRECTIONS.md` (code-verified corrections to the docs below — token collision, §22 backend gap, endpoint drift, two plan models), then `CONVENTIONS.md`, then execute `PHASE0.md`. Track progress in `BUILD_TASKS.md`.

| **PLAN_REVIEW_AND_CORRECTIONS.md** | Pre-build evaluation. What in these docs is wrong/incomplete for the live repo, with fixes. **Read before building.** |
