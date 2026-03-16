#!/usr/bin/env bash
# vault-audit: Mechanical integrity checks for the Obsidian knowledge vault.
# Checks wiki links, index-to-disk consistency, frontmatter fields, and stale references.
# Exit code: 0 = all clean, 1 = issues found.
#
# Usage: bash audit.sh [VAULT_PATH]
#   VAULT_PATH defaults to the first argument or auto-detects from common locations.

set -uo pipefail

# --- Configuration ---
VAULT_PATH="${1:-}"
if [[ -z "$VAULT_PATH" ]]; then
  for candidate in \
    "/sessions/"*"/mnt/Claude Cowork/Claude Context/Obsidian" \
    "$HOME/Claude Cowork/Claude Context/Obsidian" \
    "$HOME/Documents/Claude Context/Obsidian"; do
    if [[ -d "$candidate" ]]; then
      VAULT_PATH="$candidate"
      break
    fi
  done
fi

if [[ -z "$VAULT_PATH" || ! -d "$VAULT_PATH" ]]; then
  echo "ERROR: Vault path not found. Pass it as the first argument."
  exit 2
fi

ISSUES_FILE=$(mktemp)
WARNINGS_FILE=$(mktemp)
echo "0" > "$ISSUES_FILE"
echo "0" > "$WARNINGS_FILE"
trap 'rm -f "$ISSUES_FILE" "$WARNINGS_FILE"' EXIT

issue() {
  local count
  count=$(cat "$ISSUES_FILE")
  echo $((count + 1)) > "$ISSUES_FILE"
  echo "  ISSUE: $1"
}

warn() {
  local count
  count=$(cat "$WARNINGS_FILE")
  echo $((count + 1)) > "$WARNINGS_FILE"
  echo "  WARN:  $1"
}

section() {
  echo ""
  echo "=== $1 ==="
}

# --- Check 1: Wiki Link Resolution ---
section "Wiki Link Resolution"
echo "Scanning all .md files for [[...]] links and verifying targets exist..."

find "$VAULT_PATH" -name "*.md" -not -path "*/.smart-env/*" -not -path "*/_templates/*" -print0 | while IFS= read -r -d '' mdfile; do
  rel_file="${mdfile#$VAULT_PATH/}"
  # Extract wiki links: [[target]] or [[target|display]]
  grep -oP '\[\[([^\]|]+)' "$mdfile" 2>/dev/null | sed 's/\[\[//' | while read -r target; do
    [[ -z "$target" ]] && continue
    [[ "$target" == http* ]] && continue
    [[ "$target" == "#"* ]] && continue

    found=false

    # Try vault-root-relative with and without .md
    if [[ -f "$VAULT_PATH/$target" || -d "$VAULT_PATH/$target" ]]; then
      found=true
    elif [[ -f "$VAULT_PATH/${target}.md" ]]; then
      found=true
    fi

    # Try file-directory-relative (Obsidian same-folder resolution)
    if [[ "$found" == false ]]; then
      file_dir=$(dirname "$mdfile")
      if [[ -f "$file_dir/$target" || -f "$file_dir/${target}.md" ]]; then
        found=true
      fi
    fi

    # Obsidian shortest-path resolution: search entire vault for basename match
    if [[ "$found" == false ]]; then
      basename_target=$(basename "$target")
      if find "$VAULT_PATH" -name "$basename_target" -o -name "${basename_target}.md" 2>/dev/null | grep -q .; then
        found=true
      fi
    fi

    if [[ "$found" == false ]]; then
      # Forward-reference story links in SDR files are expected (created at implementation time)
      if [[ "$target" == *"/stories/"* ]]; then
        warn "Forward-reference story link in $rel_file -> [[$target]]"
      else
        issue "Broken link in $rel_file -> [[$target]]"
      fi
    fi
  done
done

LINK_ISSUES=$(cat "$ISSUES_FILE")
if [[ "$LINK_ISSUES" == "0" ]]; then
  echo "  All wiki links resolve."
fi

# --- Check 2: Index-to-Disk Consistency ---
section "Index-to-Disk Consistency"
echo "Verifying every project folder appears in its tier index and vice versa..."

for tier in Personal Volcanix Claude; do
  tier_dir="$VAULT_PATH/projects/$tier"
  tier_index="$tier_dir/_index.md"

  if [[ ! -f "$tier_index" ]]; then
    issue "Missing tier index: projects/$tier/_index.md"
    continue
  fi

  # Check: every subdirectory (project) is mentioned in the tier index
  for project_dir in "$tier_dir"/*/; do
    [[ ! -d "$project_dir" ]] && continue
    project_name=$(basename "$project_dir")
    if ! grep -q "$project_name" "$tier_index" 2>/dev/null; then
      issue "Project folder '$tier/$project_name' exists on disk but not in $tier/_index.md"
    fi
  done

  # Check: every project linked in the index has a folder
  grep -oP '\[\[projects/'"$tier"'/([^/|]+)' "$tier_index" 2>/dev/null | \
    sed 's/.*\///' | sort -u | while read -r linked_project; do
    if [[ ! -d "$tier_dir/$linked_project" ]]; then
      issue "Project '$tier/$linked_project' listed in index but folder missing on disk"
    fi
  done
done

echo "  Index-to-disk check complete."

# --- Check 3: Bootstrap-to-Index Consistency ---
section "Bootstrap Manifest Consistency"
echo "Checking _bootstrap.md project list matches projects/_index.md..."

BOOTSTRAP="$VAULT_PATH/_bootstrap.md"
PROJECTS_INDEX="$VAULT_PATH/projects/_index.md"

if [[ ! -f "$BOOTSTRAP" ]]; then
  issue "_bootstrap.md is missing from vault root"
elif [[ ! -f "$PROJECTS_INDEX" ]]; then
  issue "projects/_index.md is missing"
else
  # Extract project names from bootstrap table rows (lines starting with |)
  # Bold project names appear as **Name** in the first column of data rows
  # Match against both display names and folder names in projects/_index.md
  grep '^|' "$BOOTSTRAP" | grep -oP '\*\*([^*]+)\*\*' | sed 's/\*\*//g' | sort -u | while read -r proj; do
    [[ -z "$proj" ]] && continue
    # Skip table header bold text
    [[ "$proj" == "Project" || "$proj" == "Phase" || "$proj" == "Next Action" ]] && continue
    # Normalize: lowercase, replace spaces and / with hyphens for folder-name matching
    normalized=$(echo "$proj" | tr '[:upper:]' '[:lower:]' | sed 's|[/ ]|-|g')
    if ! grep -qi "$proj" "$PROJECTS_INDEX" 2>/dev/null && \
       ! grep -qi "$normalized" "$PROJECTS_INDEX" 2>/dev/null; then
      warn "Project '$proj' in _bootstrap.md but not found in projects/_index.md"
    fi
  done

  echo "  Bootstrap consistency check complete."
fi

# --- Check 4: Stale Inbox References ---
section "Stale Research Inbox References"
echo "Scanning project files for references to research/inbox/..."

STALE_BEFORE=$(cat "$ISSUES_FILE")
find "$VAULT_PATH" -name "*.md" -not -path "*/.smart-env/*" -print0 | while IFS= read -r -d '' mdfile; do
  rel_file="${mdfile#$VAULT_PATH/}"
  # Skip research workflow docs, session logs, and readmes (all legitimate mentions)
  [[ "$rel_file" == "research/_index.md" ]] && continue
  [[ "$rel_file" == "research/readme.md" ]] && continue
  [[ "$rel_file" == *"/sessions/"* ]] && continue

  # Only flag wiki-link syntax [[research/inbox/...]], not prose mentions
  if grep -q '\[\[research/inbox/' "$mdfile" 2>/dev/null; then
    lines=$(grep -n '\[\[research/inbox/' "$mdfile" 2>/dev/null | head -3)
    issue "Stale inbox wiki link in $rel_file"
    echo "         $lines"
  fi
done

STALE_AFTER=$(cat "$ISSUES_FILE")
if [[ "$STALE_BEFORE" == "$STALE_AFTER" ]]; then
  echo "  No stale inbox references found."
fi

# --- Check 5: Frontmatter Field Presence ---
section "Frontmatter Validation"

# 5a: Status files need last-updated
echo "Checking status.md files for last-updated frontmatter..."
find "$VAULT_PATH/projects" -name "status.md" -print0 | while IFS= read -r -d '' status_file; do
  rel_file="${status_file#$VAULT_PATH/}"
  if ! head -20 "$status_file" | grep -q 'last-updated\|updated:' 2>/dev/null; then
    issue "Missing last-updated in $rel_file"
  fi
done

# 5b: Processed research notes need projects: field
echo "Checking processed research notes for projects: frontmatter..."
if [[ -d "$VAULT_PATH/research/processed" ]]; then
  find "$VAULT_PATH/research/processed" -name "*.md" -print0 | while IFS= read -r -d '' research_file; do
    rel_file="${research_file#$VAULT_PATH/}"
    if ! head -20 "$research_file" | grep -q '^projects:' 2>/dev/null; then
      issue "Missing projects: field in $rel_file"
    fi
  done
fi

echo "  Frontmatter validation complete."

# --- Check 6: Required Structural Files ---
section "Required Structural Files"
echo "Verifying critical vault files exist..."

for required_file in \
  "_bootstrap.md" \
  "_index.md" \
  "projects/_index.md" \
  "decisions/_index.md" \
  "research/_index.md" \
  "code/_index.md" \
  "business/_index.md" \
  "self/_index.md"; do
  if [[ ! -f "$VAULT_PATH/$required_file" ]]; then
    issue "Missing required file: $required_file"
  fi
done

# Check each project has _index.md and status.md
find "$VAULT_PATH/projects" -mindepth 2 -maxdepth 2 -type d -print0 | while IFS= read -r -d '' project_dir; do
  proj_rel="${project_dir#$VAULT_PATH/}"
  [[ ! -f "$project_dir/_index.md" ]] && issue "Missing _index.md in $proj_rel"
  [[ ! -f "$project_dir/status.md" ]] && issue "Missing status.md in $proj_rel"
done

echo "  Structural file check complete."

# --- Summary ---
section "Summary"
FINAL_ISSUES=$(cat "$ISSUES_FILE")
FINAL_WARNINGS=$(cat "$WARNINGS_FILE")
echo "  Issues:   $FINAL_ISSUES"
echo "  Warnings: $FINAL_WARNINGS"

if [[ "$FINAL_ISSUES" -gt 0 ]]; then
  echo ""
  echo "RESULT: FAIL — $FINAL_ISSUES issue(s) found."
  exit 1
else
  if [[ "$FINAL_WARNINGS" -gt 0 ]]; then
    echo ""
    echo "RESULT: PASS with $FINAL_WARNINGS warning(s)."
  else
    echo ""
    echo "RESULT: PASS — vault is clean."
  fi
  exit 0
fi
