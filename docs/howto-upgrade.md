# How-To: Upgrade OWB on an Existing Workspace

This guide covers upgrading from one OWB version to another (e.g., 0.4.0 to 0.5.0) when you already have a workspace built by OWB. If you have never run OWB against your vault before, see [howto-first-run.md](howto-first-run.md) instead.

## What Changes During an Upgrade

An OWB version bump can introduce changes in three areas:

1. **CLI and engine behavior** — new commands, changed defaults, new config fields.
2. **Shipped content** — ECC agents/commands/rules, vault templates, context file templates, cross-project policies.
3. **Workspace structure** — new directories, renamed files, new metadata.

The `owb diff` and `owb migrate` commands handle items 2 and 3 by comparing your workspace against the reference state the new version would produce. Item 1 takes effect immediately when you install the new package.

## Prerequisites

**Your vault is backed up.** Git remote is current, or you have a snapshot you can restore. The migrate command modifies files in place.

```bash
cd /path/to/your/vault
git status --short
git log origin/main -1 --format="Remote: %ci"
```

If there are uncommitted changes, commit and push before proceeding.

**You know your workspace root and vault path.** The workspace root is the directory containing `.claude/` (or `.ai/`). The vault is the Obsidian directory inside it.

```bash
WORKSPACE="/path/to/workspace"
VAULT="$WORKSPACE/Obsidian"  # adjust if your vault has a different name
```

## Step 1: Read the Changelog

Before upgrading, check what changed between your current version and the target.

```bash
owb --version  # current version
```

Read the [CHANGELOG.md](https://github.com/VolcanixLLC/open-workspace-builder/blob/main/CHANGELOG.md) for all entries between your current version and the target. Pay attention to:

- **Added** — new commands or config fields you may want to configure.
- **Changed** — renamed files, moved content, deprecated config keys. These are the items `owb migrate` will flag.
- **Removed** — anything dropped that you may have depended on.

If the changelog mentions config schema changes, you will need to update your config file (Step 3).

## Step 2: Upgrade the Package

```bash
pip install --upgrade open-workspace-builder
owb --version  # confirm new version
```

If you are using `uv`:

```bash
uv pip install --upgrade open-workspace-builder
```

If you installed from source (editable mode):

```bash
cd /path/to/open-workspace-builder
git pull
pip install -e .
```

For CLI wrappers, upgrade the wrapper too. It pins an OWB version in its dependencies, so upgrading the wrapper pulls the correct OWB.

## Step 3: Check Config Compatibility

If the changelog mentions new config fields or changed defaults, review your config:

```bash
cat ~/.owb/config.yaml   # or ~/.<wrapper>/config.yaml for CLI wrappers
```

OWB uses a three-layer config precedence: built-in defaults, config file, CLI flags. New fields always have sensible defaults, so your existing config will still work. However, you may want to opt in to new capabilities (e.g., a new secrets backend, a new marketplace format).

If the changelog mentions a deprecated config key, update it now. Deprecated keys typically work for one minor version before removal.

## Step 4: Diff the Workspace

See what the new version wants to change in your vault.

```bash
owb diff "$VAULT"
```

Review the output. Categories:

- **Missing** — new files the upgraded OWB ships that your workspace does not have yet (new templates, new policies, new ECC content).
- **Outdated** — files that exist in your workspace but differ from what the new version would produce (updated templates, policy revisions).
- **Modified** — files you have customized locally. OWB flags these so you can decide whether to keep your version or accept the upstream change.

For a detailed report:

```bash
owb diff "$VAULT" -o /tmp/upgrade-diff.json
python3 -m json.tool /tmp/upgrade-diff.json | less
```

Exit code 0 means no gaps (your workspace already matches the new reference). Exit code 1 means gaps exist, which is expected after a version bump.

## Step 5: Migrate

Apply the changes interactively. OWB walks through each changed file, shows you the diff, and asks whether to accept or reject.

```bash
owb migrate "$VAULT"
```

For each file, OWB runs security scanning (Layers 1 and 2 by default). Files that fail scanning are blocked and cannot be accepted until the issue is resolved.

If you trust the upgrade and want to accept all clean files without prompting:

```bash
owb migrate "$VAULT" --accept-all
```

To preview without writing anything:

```bash
owb migrate "$VAULT" --dry-run
```

**After migration, verify convergence:**

```bash
owb diff "$VAULT"
# Exit code 0 = fully converged
```

## Step 6: Rebuild ECC at Workspace Root

The migrate command updates vault content but does not redeploy ECC agents, commands, and rules to the workspace root. Rebuild the workspace to pick up any new or updated ECC content.

```bash
owb init -t "$WORKSPACE" --dry-run   # preview first
owb init -t "$WORKSPACE"              # deploy
```

The target is the workspace root (the directory that contains `.claude/` or `.ai/`), not the vault directory. See the [first-run guide](howto-first-run.md) troubleshooting section if you are unsure which directory to use.

**Verify ECC is current:**

```bash
ls "$WORKSPACE/.claude/agents/"    # or .ai/agents/ for generic OWB
ls "$WORKSPACE/.claude/commands/"
ls "$WORKSPACE/.claude/rules/"
```

## Step 7: Run a Security Scan

Confirm nothing was introduced that the scanner flags.

```bash
owb security scan "$VAULT"
```

Exit code 0 = clean. Exit code 2 = issues found. If issues appear on files that were just migrated, investigate before proceeding.

## Step 8: Verify in a Live Session

Start a new CLI session from the workspace root and confirm everything works.

```bash
cd "$WORKSPACE"
claude   # or your preferred CLI
```

Inside the session, verify:

- ECC commands appear in `/` autocomplete.
- Agents are listed when asked.
- New features from the changelog are available (e.g., new `owb` subcommands).

## Quick Reference

For a clean upgrade with no manual review:

```bash
pip install --upgrade open-workspace-builder
owb diff "$VAULT"                      # see what changed
owb migrate "$VAULT" --accept-all      # apply all clean changes
owb init -t "$WORKSPACE"               # rebuild ECC
owb security scan "$VAULT"             # verify clean
owb diff "$VAULT"                      # confirm converged
```

## Troubleshooting

**Migrate reports "blocked" files.** A file failed security scanning. Review the scan output. For known false positives on first-party ECC content, use `owb migrate --accept-all` which accepts clean files and skips blocked ones. Investigate blocked files separately.

**Config key not recognized.** You may have a config key that was removed in the new version. Check the changelog for deprecation notices. Remove or rename the key.

**Nested Obsidian/Obsidian/ directory.** You ran `owb init` targeting the vault instead of the workspace root. Delete the nested directory and re-run targeting the workspace root. See [howto-first-run.md](howto-first-run.md) troubleshooting for cleanup commands.

**Context files overwritten.** `owb init` skips existing context files (about-me.md, brand-voice.md, working-style.md). However, vault scaffold files (_bootstrap.md, _templates/) are currently overwritten. Always back up before running `init`. Tracked as OWB-S060.

**vault-meta.json version mismatch.** The differ uses `.owb/vault-meta.json` (or `.vault-meta.json`) to determine which builder version produced your workspace. If this file is missing or stale, the diff may report more changes than expected. This is cosmetic and does not affect the correctness of the migration.

**ECC not updated after upgrade.** The `owb migrate` command only touches vault content. You must also run `owb init -t <workspace>` (Step 6) to redeploy ECC content to the workspace root.
