#!/usr/bin/env bash
# Session-start anchor sweep for AIDSTATION.
#
# Usage:
#   ./scripts/verify-handoff.sh              # uses most-recently-modified handoff
#   ./scripts/verify-handoff.sh <path.md>    # specific handoff
#
# What it does:
#   1. Names the latest handoff (or the one you passed).
#   2. Extracts file paths the handoff mentions (.md / .py / .sh / .sql) and
#      checks each one exists on disk. Catches "claimed shipped, actually missing."
#   3. Reports the latest Project_Backlog version on disk vs. what CLAUDE.md /
#      CURRENT_STATE.md reference. Catches stale pointers.
#   4. Prints `git status --short` for working-tree state.
#
# Does NOT:
#   - Verify content correctness (you still need to grep for anchor strings the
#     handoff claims). The script lists §8 of the handoff so you have the table
#     visible.
#   - Run tests.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SOURCES_DIR/.." && pwd)"
HANDOFF_DIR="$SOURCES_DIR/handoffs"

if [[ $# -ge 1 && -n "$1" ]]; then
  HANDOFF="$1"
  if [[ ! -e "$HANDOFF" ]]; then
    echo "Handoff not found: $HANDOFF" >&2
    exit 1
  fi
else
  # Canonical pointer: `CURRENT_STATE.md` declares the latest handoff. Fall
  # back to the most recently modified file only if CURRENT_STATE.md is
  # missing or doesn't name one.
  if [[ -f "$SOURCES_DIR/CURRENT_STATE.md" ]]; then
    REF=$(grep -oE 'handoffs/[A-Za-z0-9_./-]+\.md' "$SOURCES_DIR/CURRENT_STATE.md" | head -1)
    if [[ -n "$REF" && -e "$SOURCES_DIR/$REF" ]]; then
      HANDOFF="$SOURCES_DIR/$REF"
    fi
  fi
  if [[ -z "${HANDOFF:-}" ]]; then
    HANDOFF="$(ls -t "$HANDOFF_DIR"/*.md 2>/dev/null | grep -v '/_template\.md$' | head -1)"
  fi
  if [[ -z "${HANDOFF:-}" ]]; then
    echo "No handoffs found in $HANDOFF_DIR" >&2
    exit 1
  fi
fi

bar() { printf '%.0s-' {1..72}; echo; }

bar
echo "Handoff: $(basename "$HANDOFF")"
echo "Modified: $(date -r "$HANDOFF" 2>/dev/null || stat -c %y "$HANDOFF" 2>/dev/null || echo '?')"
bar
echo

# --- 1. File-existence sweep ---
echo "[1] Files referenced in the handoff (existence check)"
echo

# Regex covers: aidstation-sources/..., layer4/..., tests/..., routes/...,
# templates/..., static/..., scripts/..., and a few top-level files we care about.
# We strip surrounding backticks/quotes and dedupe.
mapfile -t PATHS < <(
  grep -oE '`?(aidstation-sources/[A-Za-z0-9_./-]+\.(md|py|sh|sql|json|html|js|css|txt)|layer4/[A-Za-z0-9_./-]+\.(py|md)|tests/[A-Za-z0-9_./-]+\.py|routes/[A-Za-z0-9_./-]+\.py|templates/[A-Za-z0-9_./-]+\.html|static/[A-Za-z0-9_./-]+\.(js|css)|scripts/[A-Za-z0-9_./-]+\.sh|(init_db|database|app|chain_registry|race_events_repo|race_events_invalidation|athlete|coaching|email_helper|mapbox_client|plan_match|rx_engine|garmin_connect|garmin_fit_parser|fit_workout_generator|calculations|seed_workouts)\.py)`?' "$HANDOFF" \
  | tr -d '`' \
  | sort -u
)

if [[ ${#PATHS[@]} -eq 0 ]]; then
  echo "  (no recognizable paths found in handoff — check format)"
else
  miss=0
  for p in "${PATHS[@]}"; do
    # Resolve relative to repo root first, then sources dir as fallback
    if [[ -e "$REPO_ROOT/$p" ]]; then
      echo "  ✅ $p"
    elif [[ -e "$SOURCES_DIR/$p" ]]; then
      echo "  ✅ $p  (under aidstation-sources/)"
    else
      echo "  ❌ $p  (MISSING on disk — investigate)"
      miss=$((miss + 1))
    fi
  done
  echo
  if [[ $miss -gt 0 ]]; then
    echo "  ⚠️  $miss path(s) missing. Rule #9 reconciliation needed."
  fi
fi
echo

# --- 2. Backlog version pointer check ---
echo "[2] Project_Backlog version pointers"
echo

LATEST_BACKLOG="$(ls "$SOURCES_DIR"/Project_Backlog_v*.md 2>/dev/null | sed 's/.*_v\([0-9]\+\)\.md/\1 &/' | sort -n | tail -1 | awk '{print $2}')"
if [[ -n "$LATEST_BACKLOG" ]]; then
  echo "  Latest backlog on disk: $(basename "$LATEST_BACKLOG")"
else
  echo "  ⚠️  No Project_Backlog_v*.md files found in $SOURCES_DIR"
fi

for ref_file in "$SOURCES_DIR/CLAUDE.md" "$SOURCES_DIR/CURRENT_STATE.md"; do
  if [[ -f "$ref_file" ]]; then
    refs=$(grep -oE 'Project_Backlog_v[0-9]+' "$ref_file" | sort -u | tr '\n' ' ')
    name=$(basename "$ref_file")
    if [[ -z "$refs" ]]; then
      echo "  $name: (no backlog refs)"
    else
      echo "  $name refs: $refs"
    fi
  fi
done
echo

# --- 3. Handoff §8 anchor table (printed for manual sweep) ---
echo "[3] Predecessor §8 anchor table (verify each claim manually)"
echo

awk '
  # Section starts on a heading mentioning Rule #10 or Session-end verification.
  /^#{1,4} .*([Ss]ession-end verification|Rule #10)/ { in_sec = 1; print $0; next }
  # Any subsequent top-level heading ends the section.
  in_sec && /^## / && !/[Ss]ession-end verification|Rule #10/ { in_sec = 0 }
  in_sec { print $0 }
' "$HANDOFF" | sed 's/^/  /' | head -50

echo
echo "  (Truncated at 50 lines. Open the file for the full table.)"
echo

# --- 4. Git status ---
echo "[4] Working tree"
echo

if git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')
  echo "  Branch: $branch"
  status=$(git -C "$REPO_ROOT" status --short 2>/dev/null)
  if [[ -z "$status" ]]; then
    echo "  Clean."
  else
    echo "$status" | sed 's/^/    /'
  fi
else
  echo "  (not a git working tree)"
fi

echo
bar
echo "Done. If any ❌ above, run Rule #9 reconciliation before opening new work."
bar
