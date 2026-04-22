#!/usr/bin/env bash
# sprint-close-reminder.sh — Claude Code PreToolUse hook for the Bash tool.
#
# When a git commit command contains a version-like pattern in its message
# (e.g., "v1.5.0", "release", "chore: version bump"), this script prints a
# reminder to run /sprint-close before proceeding.
#
# This is a soft gate — it prints a message but does not block the commit.
# The operator decides whether to proceed or invoke the sprint-close skill
# first.
#
# Input: Claude Code pipes a JSON object to stdin containing the tool name
# and tool input. We inspect the `tool_input.command` field.
#
# Install: Add to your Claude Code settings.json under hooks.PreToolUse:
#
#   {
#     "hooks": {
#       "PreToolUse": [
#         {
#           "matcher": "Bash",
#           "command": "bash /path/to/sprint-close-reminder.sh"
#         }
#       ]
#     }
#   }
#
# Dependencies: jq is preferred for JSON parsing; a fallback grep path is
# provided for environments without jq.

set -u

# Read the tool-use JSON payload from stdin.
payload="$(cat 2>/dev/null || true)"
if [[ -z "$payload" ]]; then
  exit 0
fi

# Extract the bash command.
if command -v jq >/dev/null 2>&1; then
  command_text="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
else
  command_text="$(printf '%s' "$payload" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 || true)"
fi

if [[ -z "$command_text" ]]; then
  exit 0
fi

# Only act on git commit commands (not git log, git diff, etc.).
if ! printf '%s' "$command_text" | grep -qE 'git commit'; then
  exit 0
fi

# Check if the commit message contains a version pattern or release keyword.
# Patterns: v1.2.3, 1.2.3, "release", "chore: version", "chore(release)"
if printf '%s' "$command_text" | grep -qE 'v?[0-9]+\.[0-9]+\.[0-9]+|release|chore.*version'; then
  echo "Sprint close reminder: This commit looks like a release. Run /sprint-close before tagging if you haven't already."
fi

exit 0
