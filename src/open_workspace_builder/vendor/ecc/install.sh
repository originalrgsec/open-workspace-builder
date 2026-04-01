#!/bin/bash
# ECC Curated Install Script
# Installs rules, agents, and commands to ~/.claude/ (global Claude Code config)
# Run from Mac terminal: cd "<your Claude Context folder>/ecc-curated" && bash install.sh

set -e

DEST="$HOME/.claude"
SRC="$(cd "$(dirname "$0")" && pwd)"

echo "=== ECC Curated Install ==="
echo "Source: $SRC"
echo "Destination: $DEST"
echo ""

# Create directories
mkdir -p "$DEST/rules/common" "$DEST/rules/python" "$DEST/rules/golang"
mkdir -p "$DEST/agents"
mkdir -p "$DEST/commands"

# Install rules (16 files, hooks excluded)
cp "$SRC/rules/common/"*.md "$DEST/rules/common/"
cp "$SRC/rules/python/"*.md "$DEST/rules/python/"
cp "$SRC/rules/golang/"*.md "$DEST/rules/golang/"
echo "✓ Rules installed (16 files, hooks excluded)"

# Install agents (16 files)
cp "$SRC/agents/"*.md "$DEST/agents/"
echo "✓ Agents installed (16 files)"

# Install commands (15 general-purpose, ECC orchestration excluded)
cp "$SRC/commands/"*.md "$DEST/commands/"
echo "✓ Commands installed (15 files)"

echo ""
echo "=== Summary ==="
echo "Rules:    $(find "$DEST/rules" -name '*.md' | wc -l | tr -d ' ') files"
echo "Agents:   $(find "$DEST/agents" -name '*.md' | wc -l | tr -d ' ') files"
echo "Commands: $(find "$DEST/commands" -name '*.md' | wc -l | tr -d ' ') files"
echo "Skills:   $(ls "$DEST/skills" 2>/dev/null | wc -l | tr -d ' ') dirs (previously installed)"
echo ""
echo "Done. Restart Claude Code for changes to take effect."
