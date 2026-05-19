# <Session title> — Closing Handoff

**Session:** <scope summary, 1-2 sentences>
**Date:** YYYY-MM-DD
**Predecessor handoff:** `<filename>`
**Branch:** `<branch-name>`
**Status:** <substantive file count vs ceiling; brief outcome>

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor handoff's §8 (Session-end verification) table claims against on-disk state. Mandatory.

| Claim | Anchor | Result |
|---|---|---|
| ... | grep / inspection / wc | ✅ / ❌ |

**Reconciliation note:** <drift found and how it was fixed, or "clean">

---

## 2. Session narrative

Scope-pick gate, /plan-mode gates, key turns. Skip ceremony — only record the load-bearing decisions, not every retrieval.

---

## 3. File-by-file edits

### 3.1 `<path>` (new / modified)

What changed, anchor line numbers, 1-2 sentence purpose. Skip files where the diff is mechanical (e.g., version bumps already covered in §9).

---

## 4. Code / tests *(omit section if none)*

Test count delta, paths, anchor of the new tests' shape.

---

## 5. Manual §5.0 verification steps *(omit section if none)*

Numbered list of testable steps Andy walks on Vercel. New scenarios get appended to `CARRY_FORWARD.md` under "Manual §5.0 walkthrough."

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
### 6.2 Alternative pivots
### 6.3 Operating notes for next session

Operating notes (1) Rule #13 — first re-read is `CLAUDE.md`; (2) read `CURRENT_STATE.md` + `CARRY_FORWARD.md`; (3) read this handoff; (4) `./scripts/verify-handoff.sh` for the anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| File exists; line count matches projection | ✅ |
| Anchor string present | ✅ grep |
| Working tree clean | ✅ git status |

---

## 9. Files shipped this session

**Substantive (N files):**
1. ...

**Bookkeeping (M files):**
N+1. ...

The 5-file ceiling applies to substantive files only. Bookkeeping (CLAUDE.md narrative bumps — now rare since A2; backlog updates; this handoff) is outside the count.

---

## 10. Carry-forward updates *(omit section if none)*

What was appended/edited in `CARRY_FORWARD.md` this session (e.g., new walkthrough scenarios, new doc-sweep nits, status flips).

---

**End of handoff.**
