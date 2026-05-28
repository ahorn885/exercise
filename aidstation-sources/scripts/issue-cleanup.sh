#!/usr/bin/env bash
#
# AIDSTATION — GitHub issue-tracker cleanup (ahorn885/exercise)
# Generated + applied 2026-05-28 (run via Claude CLI against ahorn885/exercise).
# Safe to re-run (idempotent) — kept in-repo as the record of the cleanup.
#
# Requires the GitHub CLI authenticated as a user with write access:
#   gh auth login        # once, if you haven't
#   gh auth status       # verify
#
# Run:
#   bash issue-cleanup.sh
#
# Sections 1, 2, 4(rename), 5 run automatically. Section 3 (sub-issue
# linkage + the #228/#234 merge) is intentionally NOT auto-run — it needs
# your per-item sign-off; read the proposed map at the bottom and uncomment.
#
# Every assigned priority / status / milestone is a sensible DEFAULT you can
# change; nothing here closes or deletes an issue.

REPO="ahorn885/exercise"

echo "Repo: $REPO"
gh auth status >/dev/null 2>&1 || { echo "ERROR: run 'gh auth login' first."; exit 1; }

# ─────────────────────────────────────────────────────────────────────────
# 1. LABEL HYGIENE
# ─────────────────────────────────────────────────────────────────────────
echo
echo "== [1] Label hygiene =="

# 1a. Delete the 8 unused stock GitHub labels + the duplicate priority twin.
#     (No open issue uses any of these — you use type:* / priority:med.)
echo "-- deleting unused labels"
for l in bug documentation duplicate enhancement "good first issue" \
         "help wanted" invalid question "priority:medium"; do
  if gh label delete "$l" --repo "$REPO" --yes >/dev/null 2>&1; then
    echo "   ✓ deleted: $l"
  else
    echo "   - absent (skip): $l"
  fi
done

# 1b. Upsert the canonical taxonomy with descriptions + one colour per
#     dimension (priority=red, layer=blue, area=green, type=purple,
#     status=amber, meta=greys). --force creates-or-updates, so this also
#     CREATES the two missing labels (layer:2b, layer:2c).
echo "-- upserting canonical labels (colour + description)"
LABELS=(
  # priority — red family
  "priority:high|B60205|Must-do: go-live blocker or breaks live behavior"
  "priority:med|EB6420|Important but not launch-blocking"
  "priority:low|E99695|Nice-to-have / backlog depth"
  # layer — blue (one hue for the whole dimension)
  "layer:0|1D76DB|Layer 0 — ETL / catalog / data tables"
  "layer:1|1D76DB|Layer 1 — athlete profile & onboarding capture"
  "layer:2a|1D76DB|Layer 2A — training volume / phase load"
  "layer:2b|1D76DB|Layer 2B — terrain / environment"
  "layer:2c|1D76DB|Layer 2C — gear / equipment"
  "layer:2d|1D76DB|Layer 2D — injury / accommodation"
  "layer:2e|1D76DB|Layer 2E — nutrition / supplements / heat"
  "layer:3|1D76DB|Layer 3 — athlete evaluation / HITL"
  "layer:4|1D76DB|Layer 4 — plan synthesis / orchestration"
  # area — green
  "area:infra|0E8A16|Cross-cutting: infrastructure / tooling"
  "area:injury|0E8A16|Cross-cutting: injury domain"
  "area:integrations|0E8A16|Cross-cutting: provider integrations"
  "area:notifications|0E8A16|Cross-cutting: notifications"
  "area:nutrition|0E8A16|Cross-cutting: nutrition domain"
  "area:onboarding|0E8A16|Cross-cutting: onboarding"
  "area:plan-gen|0E8A16|Cross-cutting: plan generation"
  # type — purple
  "type:bug|5319E7|Defect in shipped or in-flight behavior"
  "type:feature|5319E7|New capability"
  "type:spec|5319E7|Spec / design work"
  "type:cleanup|5319E7|Refactor / hygiene / docs"
  "type:test|5319E7|Test coverage / tooling"
  # status — amber
  "status:in-progress|FBCA04|Actively being worked"
  "status:designed|FBCA04|Design done; build not started"
  "status:blocked|FBCA04|Blocked on a dependency"
  "status:deferred|FBCA04|Backlog — not scheduled"
  # meta
  "epic|0E0E0E|Umbrella tracking issue with sub-issues"
  "v1|BFDADC|Legacy v1 Flask app"
  "v2|C2E0C6|v2 LLM pipeline (strangler-fig rebuild)"
  "icebox|CCCCCC|Not on the roadmap; revisit post-launch"
)
for spec in "${LABELS[@]}"; do
  IFS='|' read -r name color desc <<< "$spec"
  if gh label create "$name" --repo "$REPO" --color "$color" \
        --description "$desc" --force >/dev/null 2>&1; then
    echo "   ✓ $name"
  else
    echo "   ! failed: $name"
  fi
done

# ─────────────────────────────────────────────────────────────────────────
# 2. BACKFILL MISSING LABELS
# ─────────────────────────────────────────────────────────────────────────
echo
echo "== [2] Backfill missing priority / status / layer =="

add() {  # add <issue> <comma-labels>
  if gh issue edit "$1" --repo "$REPO" --add-label "$2" >/dev/null 2>&1; then
    echo "   ✓ #$1  += $2"
  else
    echo "   ! #$1  (failed: $2)"
  fi
}

# 2a. Orphaned-code cluster (#296–#308, children of epic #295) had no priority.
echo "-- priority on the orphaned-code cluster"
for n in 296 297 298 299 300 301 302 304 305 306; do add "$n" "priority:med"; done
add 308 "priority:low"   # pure dead-code removal — not urgent

# 2b. ...and no status. Mark the audit findings as backlog (matches convention).
echo "-- status on the cluster + the two status-less epics"
for n in 295 296 297 298 299 300 301 302 303 304 305 306 307 308; do
  add "$n" "status:deferred"
done
add 201 "status:in-progress"   # epic #201 is the live-fire D-77 work

# 2c. Missing layer tags (the labels didn't exist until §1b created them).
echo "-- layer tags now that layer:2b / layer:2c exist"
add 297 "layer:2b"
add 298 "layer:2c"

# 2d. #196 was completely unlabeled. Full set (reads as a Layer-1 multi-source
#     health-data item that #241 feeds). Adjust if you'd rather make it an epic.
echo "-- #196 (was fully unlabeled)"
add 196 "area:integrations,layer:1,type:feature,priority:med,status:deferred,v2"

# ─────────────────────────────────────────────────────────────────────────
# 4. TITLE FIX (the one safe, unambiguous rename)
# ─────────────────────────────────────────────────────────────────────────
echo
echo "== [4] Title fix =="
# #256 currently starts with a literal '#2b' which renders as a broken link.
if gh issue edit 256 --repo "$REPO" \
     --title "Onboarding: LLM race-URL pre-fill parser (form #2b)" >/dev/null 2>&1; then
  echo "   ✓ #256 renamed"
else
  echo "   ! #256 rename failed"
fi

# ─────────────────────────────────────────────────────────────────────────
# 5. MILESTONES
# ─────────────────────────────────────────────────────────────────────────
echo
echo "== [5] Milestones =="

ensure_milestone() {  # ensure_milestone <title> <description> [due_on ISO]
  local title="$1" desc="$2" due="${3:-}" num
  num=$(gh api "repos/$REPO/milestones?state=all" \
        --jq ".[] | select(.title==\"$title\") | .number" 2>/dev/null | head -1)
  if [[ -z "$num" ]]; then
    if [[ -n "$due" ]]; then
      gh api "repos/$REPO/milestones" -f title="$title" -f description="$desc" \
        -f due_on="$due" >/dev/null 2>&1
    else
      gh api "repos/$REPO/milestones" -f title="$title" -f description="$desc" >/dev/null 2>&1
    fi
    echo "   ✓ created milestone: $title"
  else
    echo "   - exists: $title (#$num)"
  fi
}

ensure_milestone "Go-live: PGE 2026" \
  "Launch blockers for the PGE 2026 plan (race 2026-07-17). Tiers 1–2 of the 4-tier triage." \
  "2026-07-17T00:00:00Z"
ensure_milestone "Post-launch" \
  "Deferred until after go-live. Tiers 3–4 + icebox."

mset() {  # mset <issue> <milestone-title>
  if gh issue edit "$1" --repo "$REPO" --milestone "$2" >/dev/null 2>&1; then
    echo "   ✓ #$1 → $2"
  else
    echo "   ! #$1 → $2 (failed)"
  fi
}

echo "-- go-live blockers (Tier 1 convergence + Tier 2 safety)"
for n in 201 202 205 206 303; do mset "$n" "Go-live: PGE 2026"; done

echo "-- post-launch seeds (icebox / vision epics — bulk-add the rest in the UI)"
for n in 262 286 287 288 289 290 291; do mset "$n" "Post-launch"; done

echo
echo "Done with sections 1, 2, 4, 5."
echo "Review section 3 (sub-issues + #228/#234) below before running it."

# ═════════════════════════════════════════════════════════════════════════
# 3. STRUCTURE — NEEDS YOUR SIGN-OFF (does NOT run; read, then uncomment)
# ═════════════════════════════════════════════════════════════════════════
#
# 3a. Likely duplicate: epic #228 "Upstream pipeline build-out (Layer 1–3)"
#     vs #234 "[D-73] Layer 1–3 implementation arc" — same scope. Either make
#     #234 a sub-issue of #228 (preferred), or close #234 as a duplicate:
#        gh issue close 234 --repo "$REPO" \
#          --comment "Duplicate of epic #228 (Layer 1–3 build-out). Tracking there."
#
# 3b. Native sub-issue linkage. GitHub's sub-issues give real parent→child
#     trees + progress bars (better than label-only grouping). Helper:
#
#     link_subissue() {  # link_subissue <parent#> <child#>
#       local cid
#       cid=$(gh api "repos/$REPO/issues/$2" --jq '.id')
#       gh api "repos/$REPO/issues/$1/sub_issues" -f sub_issue_id="$cid" \
#         >/dev/null 2>&1 && echo "linked #$2 under #$1" \
#         || echo "skip #$2→#$1 (already linked / not supported)"
#     }
#
#     Proposed map (CONFLICTS flagged — a child can have only ONE parent):
#       #201 ← 202 203 205 206 208 209
#       #210 ← 215 218 220 221 222 223 224 226 227
#       #211 ← 213 214 216 217 219
#       #212 ← 236 238 240 242 243 244
#       #225 ← 230 231
#       #241 ← 245 247 248 249 250 252
#       #246 ← 251 253 255 256 257 258
#       #259 ← 260
#       #261 ← 263 264 271 273 275 277 280 281
#       #262 ← 265 267 268 270 272 274 276 278 279 282 283 284 285
#       #286 ← 287 288 289 290 291
#       #295 ← 296 297 298 299 300 301 302 303 304 305 306 307 308
#       #228 ← 234 235 239           (after resolving 3a)
#     CONFLICTS to decide (dual-home; pick one parent each):
#       #229 #232 #233  → Layer 0 (#261) OR Layer 2E (#210)?
#       #266 #269       → Layer 0 (#261) OR Upstream (#228)?
#       #230            → Testing (#225) OR Layer 3 (#211)?
#       #206            → Plan-gen (#201) OR Testing (#225)?
#       #299 #300 #302 #304 → Orphan sweep (#295) OR their layer epic?
#
#     Once you've resolved the conflicts, e.g.:
#       # for c in 202 203 205 206 208 209; do link_subissue 201 "$c"; done
#       # ...
