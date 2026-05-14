Compose a session-end handoff for this AIDSTATION session.

Before writing the handoff, do session-end verification (Rule #10):
- For every file you claim to have edited or created in this session, view the file and confirm the edit is actually present.
- Spot-check by grep/anchor strings, not by trusting your own narrative.
- If any drift exists between your narrative and on-disk state, fix the file first, then write the handoff.

Handoff format:
1. Session header (name, date, predecessor handoff filename, status)
2. Session-start verification result (Rule #9 — what you verified at session start)
3. Work completed (files shipped with line counts and 1-sentence summaries)
4. Session-end verification (Rule #10 — anchor checks on each shipped file)
5. Mechanically-applicable instructions for next session (Rule #11) — str_replace-style or verbatim-content blocks, never narrative summaries
6. Next-session execution plan
7. Forward pointers
8. Gut check (what went right / risks / what might be missing / best argument against this session's scope)

Save the handoff as `handoffs/<descriptive_name>_v1.md` (Rule #12 — bump N if a previous version exists with that logical name). If you're unsure of the descriptive name, ask Andy.
