Compose a session-end handoff for this AIDSTATION session.

## Before writing — Rule #10 (session-end verification)

For every file you claim to have edited or created in this session, view the file and confirm the edit is actually present. Spot-check by grep/anchor strings, not by trusting your own narrative. If any drift exists between your narrative and on-disk state, fix the file first, then write the handoff.

## Format

Use the skeleton at `handoffs/_template.md`. Fill the mandatory sections (§1 Rule #9 verification table, §8 Rule #10 verification table, §9 files shipped). **Omit any section that has no content** — don't write "NONE this session" placeholders.

## Carry-forwards

Items that span sessions (manual §5.0 walkthrough scenarios, doc-sweep nits, orthogonal carry-forwards, parallel tracks) belong in `CARRY_FORWARD.md`. Edit it in place. The handoff §10 records what was appended; it doesn't restate the full list.

## State pointer

If this session shifts the project's current state (new "last shipped" position, layer status change, focus pivot), update `CURRENT_STATE.md` instead of writing a narrative block in `CLAUDE.md`. CLAUDE.md is for stable rules — leave it alone unless an operating rule actually changed.

## Filename

Save as `handoffs/<descriptive_name>_v1.md` (Rule #12 — bump N if a previous version exists with the same logical name). If you're unsure of the descriptive name, ask Andy.

## Branch

If the harness-pinned branch name doesn't match this session's scope, rename it at session start per the working-principles rule. Don't accumulate "harness-pinned; name mismatches scope" footnotes — they're lossy.
